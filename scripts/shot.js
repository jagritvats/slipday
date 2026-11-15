// One screenshot of a Slipday page.
//   NODE_PATH=/opt/npm-tools/node_modules node scripts/shot.js <url> <out.png> [width] [height] [scrollToId] [waitMs] [fullPage]
const puppeteer = require('puppeteer-core');
const [url, out, w, h, scrollId, waitMs, full] = process.argv.slice(2);
(async () => {
  const browser = await puppeteer.launch({ executablePath: process.env.CHROME || '/usr/bin/google-chrome', headless: 'new', args: ['--no-sandbox'] });
  const page = await browser.newPage();
  const W = parseInt(w || '1280', 10), H = parseInt(h || '800', 10);
  await page.setViewport({ width: W, height: H, deviceScaleFactor: W < 600 ? 2 : 1, isMobile: W < 600, hasTouch: W < 600 });
  await page.emulateMediaFeatures([{ name: 'prefers-color-scheme', value: 'light' }]);
  const log = [];
  page.on('console', (m) => { if (m.type() === 'error') { log.push('console.error: ' + m.text()); } });
  page.on('pageerror', (e) => log.push('pageerror: ' + e.message));
  page.on('response', (r) => { if (r.status() >= 400) { log.push('http ' + r.status() + ' ' + r.url()); } });
  await page.goto(url, { waitUntil: 'networkidle0', timeout: 120000 });
  await new Promise((r) => setTimeout(r, parseInt(waitMs || '800', 10)));
  if (scrollId && scrollId !== '-') {
    await page.evaluate((i) => { const e = document.getElementById(i); if (e) { e.scrollIntoView(); window.scrollBy(0, -8); } }, scrollId);
    await new Promise((r) => setTimeout(r, 400));
  }
  await page.screenshot({ path: out, fullPage: full === 'full' });
  const info = await page.evaluate(() => ({ scrollW: document.documentElement.scrollWidth, innerW: window.innerWidth,
    docH: document.documentElement.scrollHeight }));
  console.log(JSON.stringify(info) + (log.length ? '\n' + log.join('\n') : ''));
  await browser.close();
})().catch((e) => { console.error(e); process.exit(1); });
