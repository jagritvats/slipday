// Recording of the running page for the draft video: for each step, the region of the live page it shows is
// captured again and again at twice the pixel density while the page runs (about five pictures a second; the
// 3-D view keeps playing), so that the video is zoomed into the card or the map and its text stays readable.  scripts/make_recorded_video.py cuts, crops and captions it.
//   NODE_PATH=/path/to/node_modules CHROME=/path/to/chrome node scripts/record_demo.js http://127.0.0.1:8100/ out_dir
// Steps (each a segment of the video, named as in demo/STORYBOARD.md): answer, objective, why, missions, safety, regions, map.
// Written for the overhauled page (navigator at the top, the card further down).
// Nothing is drawn or edited: these are the page's own pixels.
const puppeteer = require('puppeteer-core');
const fs = require('fs');
const path = require('path');
const BASE = (process.argv[2] || 'http://127.0.0.1:8100/').replace(/\/$/, '') + '/';
const OUT = process.argv[3] || 'recording';
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
(async () => {
  fs.mkdirSync(path.join(OUT, 'frames'), { recursive: true });
  const browser = await puppeteer.launch({ executablePath: process.env.CHROME, headless: 'new',
    args: ['--no-sandbox', '--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--window-size=1280,800'] });
  const page = await browser.newPage();
  await page.setViewport({ width: 1280, height: 800, deviceScaleFactor: 2 });
  await page.emulateMediaFeatures([{ name: 'prefers-color-scheme', value: 'light' }]);
  await page.goto(BASE, { waitUntil: 'networkidle0', timeout: 180000 });
  await sleep(800);
  const frames = [];
  let n = 0;
  const events = [];
  // the region to show: the union of the elements' boxes in the viewport (CSS px), with a margin
  const region = (sels, pad) => page.evaluate((sels, pad) => {
    let x0 = 1e9, y0 = 1e9, x1 = -1e9, y1 = -1e9;
    sels.forEach((s) => { const e = document.querySelector(s); if (!e) return; const b = e.getBoundingClientRect(); x0 = Math.min(x0, b.left); y0 = Math.min(y0, b.top); x1 = Math.max(x1, b.right); y1 = Math.max(y1, b.bottom); });
    if (x0 > x1) return null;
    /* page (document) coordinates, which is what a screenshot clip takes; kept inside the visible viewport */
    const X0 = Math.max(0, x0 - pad), Y0 = Math.max(0, y0 - pad), X1 = Math.min(1280, x1 + pad), Y1 = Math.min(800, y1 + pad);
    return { x: X0 + window.scrollX, y: Y0 + window.scrollY, w: X1 - X0, h: Y1 - Y0 };
  }, sels, pad);
  /* film a step: grab the step's region of the live page again and again (at twice the pixel density) for ms */
  const film = async (name, sels, pad, ms) => {
    let crop = await region(sels, pad || 10);
    if (!crop || crop.h < 40 || crop.w < 40) {
      /* the element was not in view (the page moved under the recorder): bring the first one to the top and measure again */
      await page.evaluate((s) => { const e = document.querySelector(s); if (e) { e.scrollIntoView({ block: 'start', behavior: 'instant' }); window.scrollBy(0, -10); } }, sels[0]);
      await sleep(500);
      crop = await region(sels, pad || 10);
      console.log('re-aimed ' + name + ' ' + JSON.stringify(crop));
    }
    const t0 = Date.now() / 1000;
    events.push({ name, t: t0, crop: null, region: crop });
    while (Date.now() / 1000 - t0 < ms / 1000) {
      const file = 'f' + String(n++).padStart(5, '0') + '.jpg';
      const t = Date.now() / 1000;
      await page.screenshot({ path: path.join(OUT, 'frames', file), type: 'jpeg', quality: 90, clip: { x: crop.x, y: crop.y, width: crop.w, height: crop.h } });
      frames.push({ file, t });
    }
  };
  const mark = async (name) => events.push({ name, t: Date.now() / 1000, crop: null });
  /* the sticky bars would sit over zoomed regions while recording */
  await page.addStyleTag({ content: 'nav.jump, .jump, header.top { position: static !important; }' });
  const top = async (sel, off) => { await page.evaluate((sel, off) => { const e = document.querySelector(sel); if (e) { for (let q = e; q; q = q.parentElement) { if (q.tagName === 'DETAILS' && !q.open) { q.open = true; } } e.scrollIntoView({ block: 'start', behavior: 'instant' }); window.scrollBy(0, -(off || 10)); } }, sel, off); await sleep(500); };
  const texts = {};
  const keep = async (name, sels) => { texts[name] = await page.evaluate((sels) => sels.map((s) => { const e = document.querySelector(s); return e ? e.innerText : ''; }).join('\n'), sels); };
  // 1. the question and the answer: the navigator's heading, date and time, the site and the verdict
  await page.waitForFunction(() => /Yes|No|Not sure/.test((document.getElementById('nvVerdict') || {}).textContent || ''), { timeout: 120000 }).catch(() => {});
  await top('#h-nav', 12);
  await keep('answer', ['#h-nav', '#nvWhen', '#nvSiteName', '#nvVerdict']);
  await film('answer', ['#h-nav', '#nvWhen', '#nvSiteName', '#nvVerdict'], 10, 5300);
  // 2. the challenge objective: the Sun and the Earth against the real skyline, in numbers, on the chart
  await top('#nvSentence', 12);
  await keep('objective', ['#nvChart']);
  await film('objective', ['#nvSentence', '#nvChart', '#nvTags'], 10, 5300);
  // 3. the launch slipped 9 days: the card's day banner and what ends the margin
  await page.evaluate(() => { const e = document.getElementById('mSlip'); e.value = '9'; e.dispatchEvent(new Event('change', { bubbles: true })); });
  await page.waitForFunction(() => /slip of 9 day/.test((document.querySelector('#why .whyHead') || {}).textContent || ''), { timeout: 90000 }).catch(() => {});
  await sleep(1200);
  await top('#missionOut .verdict', 10);
  await keep('why', ['#dayBanner', '#why .whyFlip']);
  await film('why', ['#dayBanner', '#why .whyHead', '#why svg.whySvg', '#why .whyFlip'], 10, 4300);
  await page.evaluate(() => { const e = document.getElementById('mSlip'); e.value = '0'; e.dispatchEvent(new Event('change', { bubbles: true })); });
  // 4. a real mission facing this choice: the decision path's line from the missions board (VIPER, Mons Mouton, late 2027)
  await page.waitForFunction(() => !!document.querySelector('#decidePanel .dp-real'), { timeout: 90000 }).catch(() => {});
  await sleep(600);
  await top('#h-decide', 10);
  await keep('missions', ['#decidePanel .dp-real']);
  await film('missions', ['#h-decide', '#decidePanel .dp-real'], 10, 3300);
  // 5. flat enough to land?
  /* the page folds the later sections; open the ones the video shows */
  await page.evaluate(() => { ['#addon-safety', '#regionsGo', '#regions'].forEach((s) => { const e = document.querySelector(s); for (let q = e; q; q = q.parentElement) { if (q.tagName === 'DETAILS' && !q.open) { q.open = true; } } }); });
  await sleep(800);
  await page.waitForFunction(() => /Flat enough/.test((document.getElementById('addon-safety') || {}).textContent || ''), { timeout: 60000 }).catch(() => {});
  await top('#safetyPanel', 8);
  await keep('safety', ['#addon-safety']);
  await film('safety', ['#h-safe', '#addon-safety'], 10, 3300);
  // 6. NASA's nine south-pole landing regions
  await page.evaluate(() => { const b = document.getElementById('regionsGo'); if (b) { b.scrollIntoView(); b.click(); } });
  await page.waitForSelector('#regCanvas', { timeout: 60000 }).catch(() => {});
  await sleep(1000);
  await top('#regions .regVar', 6);
  await keep('regions', ['#regions table.regT']);
  await film('regions', ['#regCanvas', '#regions table.regT'], 10, 4300);
  // 7. the slip-margin map with the 20 m crosses
  await page.select('#mapLayer', 'margin').catch(() => {});
  await page.waitForFunction(() => !!document.getElementById('fineMap'), { timeout: 200000 }).catch(() => {});
  await sleep(800);
  await page.evaluate(() => { const f = document.getElementById('fineMap') || document.getElementById('polar'); f.scrollIntoView({ block: 'end', behavior: 'instant' }); window.scrollBy(0, 12); });
  await sleep(800);
  await keep('map', ['#fineMap', '#mapLegend']);
  await film('map', ['#polar svg', '#fineMap'], 8, 3300);
  await mark('end');
  fs.writeFileSync(path.join(OUT, 'frames.json'), JSON.stringify({ frames, events, texts, dpr: 1 }, null, 1));
  console.log(frames.length + ' frames; events ' + events.map((e) => e.name + (e.region ? '[' + Math.round(e.region.w) + 'x' + Math.round(e.region.h) + ']' : '')).join(', '));
  console.log(JSON.stringify(texts, null, 1));
  await browser.close();
})();
