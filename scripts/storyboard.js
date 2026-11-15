// Storyboard frames for the 30-second video: real screenshots of a running Slipday server, 1280x720.
//   NODE_PATH=/path/to/node_modules node scripts/storyboard.js http://127.0.0.1:8100/ demo
//   (set CHROME to the browser binary; on Windows e.g. "C:\Program Files\Google\Chrome\Application\chrome.exe")
// Five frames, 5 to 7 seconds each (29 seconds in all).  Every frame is opened from a shareable link with fixed
// dates, so the frames can be reproduced.  The text printed for each frame is what the captions in
// demo/STORYBOARD.md quote.  scripts/make_draft_video.py turns the frames and captions into a draft video.
const puppeteer = require('puppeteer-core');
const BASE = (process.argv[2] || 'http://127.0.0.1:8100/').replace(/\/$/, '') + '/';
const OUT = process.argv[3] || 'demo';
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const SITES = 's=robust_pick,shackleton,im2,im1';
const REST = '&earth=100&w=14&td=11&n=60&mast=2&m=total&st=min&sc=100';
const C1 = '#' + SITES + '&d=2026-11-18&h=0&sun=240' + REST + '&i=0&z=pole&l=margin';
// IM-1 Odysseus at its real landing hour with its own need: about seven days of surface operations (168 h)
const IM1 = '#' + SITES + '&d=2024-02-22&h=23&sun=168' + REST + '&i=3&z=pole&l=margin';

(async () => {
  const browser = await puppeteer.launch({ executablePath: process.env.CHROME || '/usr/bin/google-chrome', headless: 'new', args: ['--no-sandbox'] });
  async function open(hash) {
    const page = await browser.newPage();
    await page.setViewport({ width: 1280, height: 720, deviceScaleFactor: 1 });
    await page.emulateMediaFeatures([{ name: 'prefers-color-scheme', value: 'light' }]);
    await page.goto(BASE + hash, { waitUntil: 'networkidle0', timeout: 180000 });
    await page.waitForFunction(() => !!document.querySelector('#missionOut .verdict'), { timeout: 60000 });
    await page.waitForFunction(() => document.querySelectorAll('#circles .cRow').length === 4 && document.querySelectorAll('#classes .lRow').length === 3 &&
      !!document.querySelector('#why svg .sunl') && !!document.querySelector('#ribbon svg'), { timeout: 180000 });
    await sleep(700);
    return page;
  }
  const say = async (page, name) => {
    const t = await page.evaluate(() => ({ word: (document.querySelector('#missionOut .vWord') || {}).textContent, sub: (document.querySelector('#missionOut .vSub') || {}).textContent,
      legend: (document.querySelector('#missionOut .vLegend span:last-child') || {}).textContent,
      why: ['.whyHead', '.whyTxt', '.whyFlip'].map((q) => (document.querySelector('#why ' + q) || {}).textContent || '').join(' | '),
      ribbon: (document.querySelector('#ribbon .ribHead') || {}).textContent || '',
      classes: Array.from(document.querySelectorAll('#classes .lRow')).map((r) => r.innerText.replace(/\n+/g, ' ')).join(' ; '),
      circles: Array.from(document.querySelectorAll('#circles .cRow')).map((r) => r.textContent.replace(/\s+/g, ' ')).join(' ; '),
      tip: document.getElementById('tip').hidden ? '' : document.getElementById('tip').innerText.replace(/\n+/g, ' | ') }));
    console.log(name + ': ' + t.word + ', ' + t.sub + '\n    ' + t.legend + '\n    skyline view: ' + t.why + '\n    ' + t.ribbon + '\n    lander classes: ' + t.classes +
      '\n    circles (folded): ' + t.circles + (t.tip ? '\n    tooltip: ' + t.tip : ''));
  };

  // 1. the answer: a verdict, a slip margin in days, the Sun and the Earth against the skyline, the chance by lander class
  let page = await open(C1);
  await page.screenshot({ path: OUT + '/01_answer.png' }); await say(page, '01_answer');

  // 2. why it flips: click the first day of slip that is not a clear yes
  const day = await page.evaluate(() => { const c = Array.from(document.querySelectorAll('#vstrip .vc')); const i = c.findIndex((x) => !x.classList.contains('v-yes')); c[i].click(); return i; });
  await page.waitForFunction((d) => new RegExp('slip of ' + d + ' day').test((document.querySelector('#why .whyHead') || {}).textContent || ''), { timeout: 60000 }, day);
  await sleep(500);
  await page.screenshot({ path: OUT + '/02_why_it_flips.png' }); await say(page, '02_why_it_flips (day ' + day + ' of slip)');
  await page.evaluate(() => document.querySelector('#vstrip .vc').click());
  await sleep(500);

  // 4. the real ground in 3-D with the Sun, the Earth and the shadow at touchdown
  await page.evaluate(() => { document.getElementById('view3dPanel').scrollIntoView(); window.scrollBy(0, -8); });
  await page.waitForFunction(() => { const c = document.querySelector('#view3d canvas'); return !!c && c.width > 100; }, { timeout: 120000 });
  await sleep(2500);
  await page.screenshot({ path: OUT + '/04_terrain_3d.png' });
  console.log('04_terrain_3d: ' + (await page.$eval('#view3d', (n) => n.innerText.replace(/\n+/g, ' ').slice(0, 700))));
  // nine more real screenshots of the same view: the time slider stepped through the first 60 % of the landing
  // window (the shadows move) and the view turned 15 degrees each time; the draft video plays them in frame 4's slot
  const STEPS = 9;
  for (let k = 1; k <= STEPS; k++) {
    const label = await page.evaluate((k, n) => {
      const box = document.getElementById('view3d'), sl = box.querySelector('input[type=range]');
      const max = parseInt(sl.max, 10) || 0;
      sl.value = String(Math.round(max * 0.6 * k / n));
      sl.dispatchEvent(new Event('input', { bubbles: true }));
      const turn = Array.from(box.querySelectorAll('button')).find((b) => b.textContent === 'Turn right');
      if (turn) { turn.click(); }
      return sl.value + ' of ' + max;
    }, k, STEPS);
    await sleep(2200);
    await page.screenshot({ path: OUT + '/04_terrain_3d_' + String(k).padStart(2, '0') + '.png' });
    console.log('    04_terrain_3d_' + String(k).padStart(2, '0') + ': slider at step ' + label);
  }

  // 5. closing frame: the slip-margin map with every coloured point re-checked at 13 touchdown points
  await page.evaluate(() => { document.getElementById('h-sites').scrollIntoView(); window.scrollBy(0, -10); });
  await page.waitForFunction(() => !!document.getElementById('robustSum'), { timeout: 180000 });
  await page.evaluate(() => { document.getElementById('robustSum').scrollIntoView({ block: 'end' }); window.scrollBy(0, 14); });   // keep the legend and its counts in shot
  await sleep(400);
  const m = await page.$eval('#polar svg', (s) => { const r = s.getBoundingClientRect(); return { x: r.left, y: r.top, w: r.width, h: r.height }; });
  const best = await page.evaluate(async () => {
    const r = await (await fetch('/api/robust-map', { method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ start: '2026-11-18T00:00:00Z', n_dates: 60, need_sun_h: 240, need_earth_h: 100, window_days: 14 }) })).json();
    let k = 0; r.layers.robust.forEach((v, i) => { if (v > r.layers.robust[k]) { k = i; } });
    return { fx: ((k % r.n) + 0.5) / r.n, fy: (Math.floor(k / r.n) + 0.5) / r.n };
  });
  await page.mouse.move(m.x + m.w * best.fx, m.y + m.h * best.fy); await sleep(300);
  await page.screenshot({ path: OUT + '/05_slip_margin_map.png' });
  console.log('05_slip_margin_map: ' + (await page.$eval('#mapLegend', (n) => n.innerText.replace(/\n+/g, ' '))) +
    '\n    tooltip: ' + (await page.$eval('#tip', (t) => t.hidden ? '' : t.innerText.replace(/\n+/g, ' | '))));
  await page.close();

  // 3. a real landing with its own need
  page = await open(IM1);
  await page.screenshot({ path: OUT + '/03_real_landing_im1.png' }); await say(page, '03_real_landing_im1');
  console.log('    note: ' + await page.$eval('#missionOut .replayCap', (n) => n.textContent));
  await page.close();
  await browser.close();
})().catch((e) => { console.error(e); process.exit(1); });
