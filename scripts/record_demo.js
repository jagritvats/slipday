// Recording of the running page for the draft video: for each step, the region of the live page it shows is
// captured again and again at twice the pixel density while the page runs (about five pictures a second; the
// 3-D view keeps playing), so that the video is zoomed into the card or the map and its text stays readable.  scripts/make_recorded_video.py cuts, crops and captions it.
//   NODE_PATH=/path/to/node_modules CHROME=/path/to/chrome node scripts/record_demo.js http://127.0.0.1:8100/ out_dir
// Steps (each a segment of the video, named as in demo/STORYBOARD.md): answer, objective, why, view3d, windows, real, regions, map.
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
  await page.waitForFunction(() => document.querySelectorAll('#winLine [data-win]').length >= 3 && /Ride-through/.test((document.getElementById('survLine') || {}).textContent || ''), { timeout: 90000 }).catch(() => {});
  await sleep(800);
  /* the sticky jump bar would sit over the zoomed regions: let it scroll away with the page while recording */
  await page.addStyleTag({ content: 'nav.jump { position: static !important; }' });
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
    const crop = await region(sels, pad || 10);
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
  // 1. the question and the answer: the input sentence and the verdict together
  await film('answer', ['#h-mission', '.sentence', '#missionOut .verdict', '#fineNote'], 12, 5300);
  // 2. the challenge objective: the Sun and the Earth against the horizon, in numbers, and the skyline chart
  await film('objective', ['#objLine', '#why .whyHead', '#why svg.whySvg', '#why .whyLegend'], 12, 5300);
  // 3. why it flips: click the first day that fails; the day banner and the chart answer
  await page.evaluate(() => { const cells = Array.from(document.querySelectorAll('#vstrip .vc')); const k = cells.findIndex((c, i) => i > 0 && !c.classList.contains('v-yes')); if (k > 0) { cells[k].click(); } });
  await sleep(1800);
  await film('why', ['#dayBanner', '#why .whyHead', '#why svg.whySvg', '#why .whyFlip'], 10, 4300);
  // 4. the 3-D view playing
  await page.evaluate(() => { const p = document.getElementById('view3dPanel'); p.hidden = false; p.scrollIntoView(); });
  await sleep(600);
  await page.evaluate(() => { const b = document.querySelector('#view3dPanel .v3dPlay'); if (b) { b.click(); } });
  await sleep(1200);
  await film('view3d', ['#view3dPanel .v3dStage', '#view3dPanel .v3dTime'], 6, 3300);
  await page.evaluate(() => { const b = document.querySelector('#view3dPanel .v3dPlay'); if (b && b.getAttribute('aria-pressed') === 'true') { b.click(); } });
  // 5. the next monthly launch windows (back on the plan)
  await page.evaluate(() => { const c = document.querySelector('#vstrip .vc'); if (c) { c.click(); } window.scrollTo(0, 0); });
  await sleep(1500);
  await page.evaluate(() => { const e = document.querySelector('#missionOut .nextGood'); e.scrollIntoView({ block: 'center', behavior: 'instant' }); });
  await sleep(400);
  await film('windows', ['#missionOut .nextGood', '#missionOut .cardActions'], 12, 4300);
  // 5b. flat enough to land? the slope line for the card's site
  await page.waitForFunction(() => /Flat enough/.test((document.getElementById('addon-safety') || {}).textContent || ''), { timeout: 60000 }).catch(() => {});
  await page.evaluate(() => { const e = document.getElementById('safetyPanel'); e.scrollIntoView({ block: 'start', behavior: 'instant' }); window.scrollBy(0, -8); });
  await sleep(500);
  await film('safety', ['#h-safe', '#addon-safety'], 10, 3300);
  // 6. real missions: IM-1, the window it missed and the one it flew
  await page.evaluate(() => { window.scrollTo(0, 0); document.getElementById('realGo').click(); });
  await page.waitForFunction(() => document.querySelectorAll('#real table').length === 2, { timeout: 60000 }).catch(() => {});
  await sleep(1500);
  await page.evaluate(() => { const h = document.querySelector('#real h3'); h.scrollIntoView({ block: 'start', behavior: 'instant' }); window.scrollBy(0, -10); });
  await sleep(400);
  await film('real', ['#real h3', '#real table'], 10, 4300);
  // 6. how many of NASA's nine regions must stay open: the calendar and the coverage table
  await page.evaluate(() => { const b = document.getElementById('regionsGo'); b.scrollIntoView(); b.click(); });
  await page.waitForSelector('#regCanvas', { timeout: 60000 }).catch(() => {});
  await sleep(800);
  await page.evaluate(() => { const v = document.querySelector('#regions .regVar'); v.scrollIntoView({ block: 'start', behavior: 'instant' }); window.scrollBy(0, -6); });
  await sleep(400);
  await film('regions', ['#regCanvas', '#regions table.regT'], 10, 5300);
  // 7. the map with the 20 m crosses
  await page.select('#mapLayer', 'margin');
  await page.waitForFunction(() => !!document.getElementById('fineMap'), { timeout: 150000 }).catch(() => {});
  await page.evaluate(() => { const f = document.getElementById('fineMap') || document.getElementById('polar'); f.scrollIntoView({ block: 'end', behavior: 'instant' }); window.scrollBy(0, 12); });
  await sleep(600);
  const box = await page.$eval('#polar svg', (s) => { const r = s.getBoundingClientRect(); return { x: r.left, y: r.top, w: r.width, h: r.height }; });
  await page.mouse.move(box.x + box.w * 0.62, box.y + box.h * 0.36);
  await sleep(500);
  await film('map', ['#polar svg', '#fineMap'], 8, 3300);
  await mark('end');
  await sleep(300);
  const text = await page.evaluate(() => ({
    verdict: (document.querySelector('#missionOut .verdict') || {}).textContent, win: (document.getElementById('winLine') || {}).textContent,
    flip: (document.querySelector('#why .whyFlip') || {}).textContent, real: ((document.querySelector('#real table') || {}).textContent || '').slice(0, 400),
    fine: (document.getElementById('fineMap') || {}).textContent,
    regions: ((document.querySelector('#regions table.regT') || {}).textContent || '').slice(0, 400) }));
  fs.writeFileSync(path.join(OUT, 'frames.json'), JSON.stringify({ frames, events, text, dpr: 1 }, null, 1));
  console.log(frames.length + ' frames; events ' + events.map((e) => e.name + (e.region ? '[' + Math.round(e.region.w) + 'x' + Math.round(e.region.h) + ']' : '')).join(', '));
  console.log(JSON.stringify(text, null, 1));
  await browser.close();
})();
