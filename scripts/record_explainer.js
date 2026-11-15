// Screen recording of the running page for the explainer video (demo/slipday_explainer.mp4), in the way of
// scripts/record_demo.js: for each scene the page is driven (clicks, typing), the part of the page the scene
// shows is captured again and again at twice the pixel density, and its text is saved so every number in the
// script can be checked against the screen.  Nothing is drawn into the page.
//   NODE_PATH=... CHROME=... node scripts/record_explainer.js http://127.0.0.1:8101/ out_dir [durations.json]
// durations.json: {"scene_id": milliseconds, ...} (default 2500 ms each, for a quick check).
const puppeteer = require('puppeteer-core');
const fs = require('fs');
const path = require('path');
const BASE = (process.argv[2] || 'http://127.0.0.1:8101/').replace(/\/$/, '') + '/';
const OUT = process.argv[3] || 'recording_explainer';
const DUR = process.argv[4] ? JSON.parse(fs.readFileSync(process.argv[4], 'utf8')) : {};
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
(async () => {
  fs.mkdirSync(path.join(OUT, 'frames'), { recursive: true });
  const browser = await puppeteer.launch({ executablePath: process.env.CHROME, headless: 'new',
    args: ['--no-sandbox', '--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--window-size=1280,800'] });
  const page = await browser.newPage();
  await page.setViewport({ width: 1280, height: 800, deviceScaleFactor: 2 });
  await page.emulateMediaFeatures([{ name: 'prefers-color-scheme', value: 'light' }]);
  const errors = [];
  page.on('pageerror', (e) => errors.push(e.message));
  page.on('console', (m) => { if (m.type() === 'error') { errors.push(m.text()); } });
  await page.goto(BASE, { waitUntil: 'networkidle0', timeout: 180000 });
  await page.waitForFunction(() => document.querySelectorAll('#winLine [data-win]').length >= 3, { timeout: 120000 }).catch(() => {});
  await sleep(1000);
  const frames = [], events = [], texts = {};
  let n = 0;
  const region = (sels, pad) => page.evaluate((sels, pad) => {
    let x0 = 1e9, y0 = 1e9, x1 = -1e9, y1 = -1e9;
    sels.forEach((s) => { const e = document.querySelector(s); if (!e) return; const b = e.getBoundingClientRect(); x0 = Math.min(x0, b.left); y0 = Math.min(y0, b.top); x1 = Math.max(x1, b.right); y1 = Math.max(y1, b.bottom); });
    if (x0 > x1) return null;
    const X0 = Math.max(0, x0 - pad), Y0 = Math.max(0, y0 - pad), X1 = Math.min(1280, x1 + pad), Y1 = Math.min(800, y1 + pad);
    return { x: X0 + window.scrollX, y: Y0 + window.scrollY, w: X1 - X0, h: Y1 - Y0 };
  }, sels, pad);
  const textOf = (sels) => page.evaluate((sels) => sels.map((s) => { const e = document.querySelector(s); return e ? e.innerText : ''; }).join('\n'), sels);
  const top = (sel, off) => page.evaluate((sel, off) => { const e = document.querySelector(sel); if (e) { e.scrollIntoView({ block: 'start', behavior: 'instant' }); window.scrollBy(0, -(off || 8)); } }, sel, off);
  const film = async (name, sels, pad) => {
    const ms = DUR[name] || 2500;
    /* bring the scene's elements into view: their top 70 px from the top of the window when they fit */
    await page.evaluate((sels) => {
      let y0 = 1e9, y1 = -1e9;
      sels.forEach((s) => { const e = document.querySelector(s); if (!e) return; const b = e.getBoundingClientRect(); y0 = Math.min(y0, b.top + window.scrollY); y1 = Math.max(y1, b.bottom + window.scrollY); });
      if (y0 > y1) return;
      const vt = y0 - window.scrollY, vb = y1 - window.scrollY;
      if (vt < 0 || vb > 800) { window.scrollTo(0, Math.max(0, y1 - y0 < 720 ? y0 - 70 : y0 - 10)); }
    }, sels);
    await sleep(300);
    const crop = await region(sels, pad || 10);
    if (!crop) { throw new Error('nothing to film for ' + name); }
    texts[name] = await textOf(sels);
    const t0 = Date.now() / 1000;
    events.push({ name, t: t0, region: crop });
    while (Date.now() / 1000 - t0 < ms / 1000) {
      const file = 'f' + String(n++).padStart(5, '0') + '.jpg';
      const t = Date.now() / 1000;
      await page.screenshot({ path: path.join(OUT, 'frames', file), type: 'jpeg', quality: 88, clip: { x: crop.x, y: crop.y, width: crop.w, height: crop.h } });
      frames.push({ file, t });
    }
    console.log('filmed', name, Math.round(crop.w) + 'x' + Math.round(crop.h));
  };
  const pickSite = async (i) => {
    await page.evaluate((i) => { const s = document.getElementById('mSite'); s.value = String(i); s.dispatchEvent(new Event('change', { bubbles: true })); }, i);
    await page.waitForFunction(() => !!document.querySelector('#missionOut .verdict') && !/working|Loading/.test(document.getElementById('missionOut').innerText.slice(0, 80)), { timeout: 120000 }).catch(() => {});
    await sleep(2500);
  };

  const openFold = async (id) => { await page.evaluate((id) => { const d = document.getElementById(id); if (d) { d.open = true; } window.dispatchEvent(new Event('resize')); }, id); await sleep(1200); };
  await page.addStyleTag({ content: 'nav.jump, .jump, header.top { position: static !important; }' });   /* the sticky bar would cover zoomed regions */
  /* the page folds its later sections; open the ones the scenes show (not the slip grid, compare-over-time or home folds) */
  await page.evaluate(() => { ['foldMissions', 'foldSites', 'foldSafety', 'foldPrecise', 'foldRelay', 'foldRegions', 'foldAtlas', 'foldGame', 'foldListen'].forEach((id) => { const d = document.getElementById(id); if (d) { d.open = true; } }); });
  await sleep(1500);
  // 1. the question: title, challenge, the plain intro, the jump bar and the input sentence
  await page.waitForFunction(() => /Yes|No|Not sure/.test((document.getElementById('nvVerdict') || {}).textContent || ''), { timeout: 120000 }).catch(() => {});
  await page.evaluate(() => window.scrollTo(0, 0));
  await film('question', ['#h-nav', '#nvStart', '#nvPresets'], 12);
  // 2. the answer and the slip margin (the navigator's verdict)
  await film('card', ['#nvSiteName', '#nvVerdict', '#nvSentence'], 12);
  // 3. the challenge objective in numbers, on the skyline chart
  await film('objective', ['#nvChart', '#nvTags'], 12);
  // 4. launch slipped by 9 days: the strip, the day banner and the reason
  await page.evaluate(() => { const e = document.getElementById('mSlip'); e.value = '9'; e.dispatchEvent(new Event('change')); });
  await page.waitForFunction(() => /slip of 9 day/.test((document.querySelector('#why .whyHead') || {}).textContent || ''), { timeout: 60000 }).catch(() => {});
  await sleep(800);
  await film('slipped', ['#dayBanner', '#why .whyHead', '#why svg.whySvg', '#why .whyFlip'], 12);
  await page.evaluate(() => { const e = document.getElementById('mSlip'); e.value = '0'; e.dispatchEvent(new Event('change')); });
  await sleep(2500);
  // 5. next windows, other sites and hours, and Download
  await page.click('#optGo');
  await page.waitForFunction(() => /Other options:/.test((document.getElementById('winAlt') || {}).textContent || ''), { timeout: 400000 }).catch(() => {});
  await sleep(600);
  await film('windows', ['#missionOut .nextGood', '#winAlt', '#missionOut .cardActions'], 14);
  // 6. 3-D
  await page.evaluate(() => { const p = document.getElementById('view3dPanel'); p.hidden = false; p.scrollIntoView(); });
  await sleep(800);
  await page.evaluate(() => { const b = document.querySelector('#view3dPanel .v3dPlay'); if (b) { b.click(); } });
  await sleep(1200);
  await film('view3d', ['#view3dPanel .v3dStage', '#view3dPanel .v3dTime'], 6);
  await page.evaluate(() => { const b = document.querySelector('#view3dPanel .v3dPlay'); if (b && b.getAttribute('aria-pressed') === 'true') { b.click(); } });
  // 7. your own site, typed on the card
  await page.evaluate(() => { window.scrollTo(0, 0); const s = document.getElementById('mSite'); s.value = 'custom'; s.dispatchEvent(new Event('change')); });
  await sleep(500);
  await page.evaluate(() => { document.getElementById('mLat').value = '86.0'; document.getElementById('mLon').value = '-160.0'; document.getElementById('mUse').click(); });
  await page.waitForFunction(() => /Your site/.test((document.getElementById('mSite').selectedOptions[0] || {}).textContent || '') && !!document.querySelector('#why .whyFlip'), { timeout: 120000 }).catch(() => {});
  await sleep(2500);
  await film('custom', ['.sentence', '#mCoords', '#missionOut .verdict', '#objLine'], 12);
  console.log('custom site option:', await page.evaluate(() => (document.getElementById('mSite').selectedOptions[0] || {}).textContent));
  await pickSite(0);
  // 8. the slip-margin map with the 20 m check
  await page.select('#mapLayer', 'margin');
  await page.waitForFunction(() => !!document.getElementById('fineMap'), { timeout: 200000 }).catch(() => {});
  await page.evaluate(() => { const f = document.getElementById('fineMap') || document.getElementById('polar'); f.scrollIntoView({ block: 'end', behavior: 'instant' }); window.scrollBy(0, 12); });
  await sleep(800);
  await film('map', ['#polar svg', '#fineMap'], 8);
  // 9. 80 / 20 / 5 m: the Shackleton ridge
  await pickSite(1);
  await page.evaluate(() => window.scrollTo(0, 0));
  await sleep(600);
  await film('grids', ['.sentence', '#missionOut .verdict', '#fineNote'], 14);
  await pickSite(0);
  // 10. flat enough to land?
  await page.waitForFunction(() => /Flat enough/.test((document.getElementById('addon-safety') || {}).textContent || ''), { timeout: 60000 }).catch(() => {});
  await sleep(2500);
  await film('slope', ['#h-safe', '#addon-safety', '#slopeNote'], 10);
  // 11. chance of a safe touchdown
  await page.waitForFunction(() => /Within 8/.test((document.getElementById('addon-safetouch') || {}).textContent || ''), { timeout: 60000 }).catch(() => {});
  await film('touchdown', ['#addon-safetouch', '#touchNote'], 10);
  // 12. IM-1
  await page.evaluate(() => { window.scrollTo(0, 0); document.getElementById('realGo').click(); });
  await page.waitForFunction(() => document.querySelectorAll('#real table').length >= 2, { timeout: 90000 }).catch(() => {});
  await sleep(1500);
  await film('im1', ['#real h3', '#real table'], 10);
  // 13. regions
  await page.evaluate(() => { const b = document.getElementById('regionsGo'); b.scrollIntoView(); b.click(); });
  await page.waitForSelector('#regCanvas', { timeout: 60000 }).catch(() => {});
  await sleep(800);
  await film('regions', ['#regCanvas', '#regions table.regT'], 10);
  // 14. the atlas, 2027 to 2035
  await openFold('foldAtlas');
  await page.waitForFunction(() => /2028/.test((document.getElementById('addon-atlas') || {}).textContent || ''), { timeout: 60000 }).catch(() => {});
  await film('atlas', ['#addon-atlas h2', '#addon-atlas .atl-ov'], 10);
  // 15. relay satellites
  await openFold('foldRelay');
  await page.waitForFunction(() => /336/.test((document.getElementById('addon-relay') || {}).textContent || ''), { timeout: 90000 }).catch(() => {});
  await film('relay', ['#addon-relay'], 10);
  // 16. listen to the landing window
  await openFold('foldListen');
  await page.evaluate(() => { const b = document.getElementById('sd-listen-play'); if (b) { b.click(); } });
  await sleep(2500);
  await film('listen', ['#addon-listen'], 10);
  await page.evaluate(() => { const b = document.getElementById('sd-listen-stop'); if (b) { b.click(); } });
  // 17. be the mission planner
  await openFold('foldGame');
  await page.evaluate(() => { const b = document.getElementById('sd-game-start'); if (b) { b.click(); } });
  await page.waitForFunction(() => !!document.getElementById('sd-game-q'), { timeout: 60000 }).catch(() => {});
  await sleep(1500);
  await film('game', ['#addon-game'], 10);
  // 18. what it cannot tell you
  await film('limits', ['#h-valid', '#validTiles'], 10);
  events.push({ name: 'end', t: Date.now() / 1000 });
  fs.writeFileSync(path.join(OUT, 'frames.json'), JSON.stringify({ frames, events, texts, errors }, null, 1));
  console.log(frames.length + ' frames; errors: ' + errors.length);
  await browser.close();
})().catch((e) => { console.error(e); process.exit(1); });
