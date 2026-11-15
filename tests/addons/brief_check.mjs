// Headless browser check for the review-board brief (static/brief.html, static/addons/brief.js).
//
//   node tests/addons/brief_check.mjs
//
// Starts its own server on port 8481 (BRIEF_PORT, 8480-8489 only) from tests/addons/brief_app.py (the app with the
// brief router included), opens /static/brief.html?site=robust_pick&date=2026-11-18&slip=3 and checks:
//   1. the brief renders, with no console errors or page errors;
//   2. the slip margin and the planned sunlit hours on the page equal an independent /api/mission call;
//   3. the page fits at 390 px with no sideways scroll; it prints to an A4 PDF (page count reported);
//   4. the brief.js container renders a button whose link opens brief.html for the opening example.
// Writes screenshots/brief_opening.png and the PDF to screenshots/brief_opening.pdf. Stops the server it started by PID.
// BRIEF_BASE=http://127.0.0.1:PORT uses a running server instead.
import { createRequire } from 'node:module';
import { spawn, spawnSync } from 'node:child_process';
import path from 'node:path';
import fs from 'node:fs';
import { fileURLToPath } from 'node:url';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const ENTRY = path.resolve(HERE, '..', '..');
const NODETOOLS = path.resolve(ENTRY, '..', '..', 'reviews_local', 'work', 'nodetools');
const require = createRequire(path.join(NODETOOLS, 'package.json'));
const puppeteer = require('puppeteer-core');

const PORT = Number(process.env.BRIEF_PORT || 8481);
if (PORT < 8480 || PORT > 8489) { throw new Error('use a port from 8480 to 8489'); }
const BASE = process.env.BRIEF_BASE || `http://127.0.0.1:${PORT}`;
const BROWSERS = ['C:/Program Files/Google/Chrome/Application/chrome.exe', 'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe',
  'C:/Program Files/Microsoft/Edge/Application/msedge.exe'];
const OUT = path.join(ENTRY, 'screenshots');
let server = null;
const fails = [];
function check(ok, what) { console.log((ok ? 'PASS ' : 'FAIL ') + what); if (!ok) fails.push(what); }

async function up() {
  for (let i = 0; i < 240; i++) {
    try { const r = await fetch(BASE + '/api/health'); if (r.ok) return; } catch (e) { /* not yet */ }
    await new Promise((r) => setTimeout(r, 500));
  }
  throw new Error('server did not start');
}

async function main() {
  if (!process.env.BRIEF_BASE) {
    const py = path.join(ENTRY, '.venv', 'Scripts', 'python.exe');
    server = spawn(py, ['-m', 'uvicorn', 'tests.addons.brief_app:app', '--host', '127.0.0.1', '--port', String(PORT)],
      { cwd: ENTRY, stdio: ['ignore', 'ignore', 'pipe'] });
  }
  await up();
  const mission = await (await fetch(BASE + '/api/mission', { method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ site: { id: 'robust_pick' }, landing: '2026-11-18T00:00:00Z', slip_days: 15 }) })).json();

  const exe = BROWSERS.find((p) => fs.existsSync(p));
  if (!exe) { throw new Error('no Chrome or Edge found'); }
  const browser = await puppeteer.launch({ executablePath: exe, headless: true, args: ['--no-first-run', '--mute-audio'] });
  try {
    const page = await browser.newPage();
    const errors = [];
    page.on('console', (m) => { if (m.type() === 'error') errors.push(m.text()); });
    page.on('pageerror', (e) => errors.push(String(e)));
    await page.setViewport({ width: 1000, height: 1400 });
    await page.goto(BASE + '/static/brief.html?site=robust_pick&date=2026-11-18&slip=3', { waitUntil: 'load' });
    await page.waitForFunction('window.__briefReady !== undefined', { timeout: 600000 });
    check(await page.evaluate('window.__briefReady === true'), 'brief rendered');
    const text = await page.evaluate(() => document.getElementById('brief').innerText);
    check(text.includes('Slip margin') && text.includes(mission.slip_margin_days + ' d'), `slip margin ${mission.slip_margin_days} d shown`);
    check(text.includes(mission.days[0].sunlit_h + ' h'), `planned sunlit ${mission.days[0].sunlit_h} h shown`);
    for (const h of ['Next launch windows', 'Longest night', 'Slope and safe-touchdown', 'Descent lighting', 'Relay contact',
      'Best alternative sites', 'NASA terrain grid used', 'Validation checks', 'Assumptions', 'Data sources']) {
      check(text.toLowerCase().includes(h.toLowerCase()), 'section: ' + h);
    }
    fs.mkdirSync(OUT, { recursive: true });
    await page.screenshot({ path: path.join(OUT, 'brief_opening.png'), fullPage: true });
    await page.emulateMediaType('print');
    await page.setViewport({ width: 718, height: 1000 });
    const hp = await page.evaluate(() => document.documentElement.scrollHeight);
    console.log('print height at A4 width: ' + hp + ' px of 1047 px per page');
    await page.screenshot({ path: path.join(OUT, 'brief_opening_print.png'), fullPage: true });
    const pdf = await page.pdf({ path: path.join(OUT, 'brief_opening.pdf'), format: 'A4', printBackground: true });
    const count = (buf) => Math.max(0, ...[...Buffer.from(buf).toString('latin1').matchAll(/\/Count (\d+)/g)].map((m) => Number(m[1])));
    const pages = count(pdf);
    console.log('A4 PDF pages: ' + pages);
    const letter = await page.pdf({ format: 'Letter', printBackground: true });
    console.log('Letter PDF pages: ' + count(letter));
    await page.emulateMediaType('screen');
    await page.setViewport({ width: 390, height: 900 });
    const wide = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
    check(wide <= 1, `no sideways scroll at 390 px (${wide})`);

    // the container module on a blank page of the same origin
    const p2 = await browser.newPage();
    p2.on('pageerror', (e) => errors.push(String(e)));
    p2.on('console', (m) => { if (m.type() === 'error') errors.push(m.text()); });
    await p2.setContent('<!doctype html><div id="addon-brief"></div><script src="' + BASE + '/static/addons/brief.js"></script>',
      { waitUntil: 'load', timeout: 60000 });
    const link = await p2.evaluate(() => { const a = document.querySelector('#addon-brief a'); return a && [a.textContent, a.getAttribute('href')]; });
    check(!!link && link[0] === 'Make a review-board brief' && link[1].startsWith('/static/brief.html?site=robust_pick&date=2026-11-18'),
      'container button: ' + (link && link[1]));
    check(errors.length === 0, 'no console errors' + (errors.length ? ': ' + errors.join(' | ') : ''));
  } finally {
    await browser.close();
  }
}

main().catch((e) => { console.log('FAIL ' + e.message); fails.push(e.message); }).finally(() => {
  if (server) { spawnSync('taskkill', ['/PID', String(server.pid), '/T', '/F']); }
  console.log(fails.length ? `${fails.length} failed` : 'all passed');
  process.exit(fails.length ? 1 : 0);
});
