// Headless browser check for the navigator on the first screen (static/navigator.js).
//
//   node tests/navigator_check.mjs
//
// It starts its own Slipday server on port 8184 (NAV_PORT to change it, 8180-8189 only), opens the page in headless
// Chrome or Edge and checks, each against an independent API call with the same rules:
//   1. the Sun and Earth table at the chosen time (azimuth, height above level) equals /api/why;
//   2. moving the time slider with the keyboard shows the API's hourly track at that hour;
//   3. the verdict band equals /api/mission;
//   4. search finds a site by name, picking it makes it the shown site, and its verdict equals the API;
//   5. own coordinates with the South and West buttons give a site at negative latitude and longitude;
//   6. every column of the comparison table shows the API's verdict and sunlit hours, and "Remove" takes one click;
//   7. the decision path ranks options whose verdicts equal the API for that site and landing;
//   8. no script errors, no sideways scroll at 1920, 1280, 768 and 390 px, light and dark.
// The server it started is stopped by PID at the end.  NAV_BASE=http://127.0.0.1:PORT uses a running server instead.
import { createRequire } from 'node:module';
import { spawn, spawnSync } from 'node:child_process';
import path from 'node:path';
import fs from 'node:fs';
import { fileURLToPath } from 'node:url';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const ENTRY = path.resolve(HERE, '..');
const NODETOOLS = path.resolve(ENTRY, '..', '..', 'reviews_local', 'work', 'nodetools');
const require = createRequire(path.join(NODETOOLS, 'package.json'));
const puppeteer = require('puppeteer-core');

const PORT = parseInt(process.env.NAV_PORT || '8184', 10);
if (!process.env.NAV_BASE && (PORT < 8180 || PORT > 8189)) { throw new Error('use a port from 8180 to 8189'); }
const BASE = process.env.NAV_BASE || `http://127.0.0.1:${PORT}`;
const BROWSERS = ['C:/Program Files/Google/Chrome/Application/chrome.exe', 'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe',
  'C:/Program Files/Microsoft/Edge/Application/msedge.exe'];

const results = [];
function check(name, ok, detail = '') {
  results.push({ name, ok: !!ok, detail });
  console.log(`${ok ? 'PASS' : 'FAIL'}  ${name}${detail ? '  -- ' + detail : ''}`);
}
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
async function api(p, body) {
  const r = await fetch(BASE + p, body ? { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) } : {});
  if (!r.ok) { throw new Error(`${p}: ${r.status} ${await r.text()}`); }
  return r.json();
}
let server = null;
async function startServer() {
  if (process.env.NAV_BASE) { return; }
  const py = fs.existsSync(path.join(ENTRY, '.venv', 'Scripts', 'python.exe')) ? path.join(ENTRY, '.venv', 'Scripts', 'python.exe') : 'python';
  server = spawn(py, ['-m', 'uvicorn', 'slipday.api:app', '--host', '127.0.0.1', '--port', String(PORT)], { cwd: ENTRY, stdio: ['ignore', 'ignore', 'pipe'] });
  let err = '';
  server.stderr.on('data', (d) => { err += d; });
  for (let i = 0; i < 90; i++) {
    try { const r = await fetch(BASE + '/api/health'); if (r.ok) { console.log(`server started on ${BASE} (PID ${server.pid})`); return; } } catch (e) { /* not yet */ }
    if (server.exitCode !== null) { throw new Error('server exited: ' + err.slice(-800)); }
    await sleep(1000);
  }
  throw new Error('server did not answer within 90 s');
}
function stopServer() {
  if (server && server.exitCode === null) {
    if (process.platform === 'win32') { spawnSync('taskkill', ['/PID', String(server.pid), '/T', '/F'], { stdio: 'ignore' }); }
    else { try { process.kill(server.pid); } catch (e) { /* gone */ } }
    console.log(`server PID ${server.pid} (and its child) stopped`);
  }
}
const norm = (a) => ((a % 360) + 360) % 360;
const WORD = { yes: 'Yes', 'not sure': 'Not sure', no: 'No', 'n/a': 'Not worked out' };

async function tableRows(page) {
  return page.evaluate(() => Array.from(document.querySelectorAll('.nv-obj tbody tr')).map((tr) => Array.from(tr.children).map((c) => c.textContent.trim())));
}
async function waitShown(page, name) {
  await page.waitForFunction((n) => {
    const A = window.SlipdayApp, s = A && A.selected()[A.current()], m = A && A.mission(A.current());
    return s && s.name === n && m && document.querySelector('#nvVerdict .vb-word') && document.querySelector('#nvVerdict .vb-word').textContent !== 'Working it out…' &&
      document.querySelector('.nv-obj') && window.SlipdayNavigator.state().why && !window.SlipdayNavigator.state().why.error && window.SlipdayNavigator.state().why.site.name === m.site.name;
  }, { timeout: 180000 }, name);
}

async function main() {
  await startServer();
  const exe = BROWSERS.find((p) => fs.existsSync(p));
  if (!exe) { throw new Error('no Chrome or Edge found'); }
  const browser = await puppeteer.launch({ executablePath: exe, headless: true, args: ['--no-first-run', '--mute-audio', '--use-angle=swiftshader'] });
  try {
    const page = await browser.newPage();
    const errors = [];
    page.on('pageerror', (e) => errors.push(String(e.message || e)));
    await page.setViewport({ width: 1280, height: 800 });
    await page.goto(BASE + '/', { waitUntil: 'domcontentloaded' });
    await page.waitForFunction(() => window.SlipdayApp && window.SlipdayApp.selected().length && window.SlipdayApp.mission(window.SlipdayApp.current()), { timeout: 180000 });
    const first = await page.evaluate(() => window.SlipdayApp.selected()[window.SlipdayApp.current()].name);
    await waitShown(page, first);

    // ---- 1. the objective table at the chosen time
    const body = await page.evaluate(() => { const A = window.SlipdayApp; const b = A.body(A.selected()[A.current()]); b.day = 0; b.earth_stations = false; return b; });
    const w = await api('/api/why', body);
    let rows = await tableRows(page);
    const td = w.touchdown;
    const sunOk = rows[0][1].startsWith(Math.round(norm(td.sun_az)) + '°') && rows[0][2] === td.sun_el.toFixed(1) + '°' && rows[0][3] === td.sun_skyline_el.toFixed(1) + '°';
    const earthOk = rows[1][1].startsWith(Math.round(norm(td.earth_az)) + '°') && rows[1][2] === td.earth_el.toFixed(1) + '°' && rows[1][3] === td.earth_skyline_el.toFixed(1) + '°';
    check('the Sun row at the chosen time equals /api/why (azimuth, height, skyline)', sunOk, rows[0].slice(0, 4).join(' | '));
    check('the Earth row at the chosen time equals /api/why', earthOk, rows[1].slice(0, 4).join(' | '));
    check('the next sunset or sunrise is the API time to the minute', rows[0][6].includes(td.sun_up ? 'sets in' : 'rises in') &&
      rows[0][6].includes((td.sun_up ? td.next_sunset : td.next_sunrise).utc.slice(11, 16)), rows[0][6]);

    // ---- 2. the slider by keyboard
    await page.focus('#nvRange');
    for (let k = 0; k < 30; k++) { await page.keyboard.press('ArrowRight'); }
    await sleep(300);
    rows = await tableRows(page);
    const t = w.track;
    const at30 = rows[0][2] === t.sun_el[30].toFixed(1) + '°' && rows[1][2] === t.earth_el[30].toFixed(1) + '°' && rows[0][1].startsWith(Math.round(norm(t.sun_az[30])) + '°') &&
      rows[0][5] === (t.sun_lit[30] ? 'In view' : 'Hidden') && rows[1][5] === (t.earth_up[30] ? 'In view' : 'Hidden');
    const when = await page.evaluate(() => document.getElementById('nvWhenNow').textContent);
    check('30 presses of the right arrow show the hourly track at hour 30', at30 && /30 h after/.test(when), when + ' | ' + rows.map((r) => r.slice(1, 3).join(' ')).join(' / '));

    // ---- 3. the verdict band
    const m = await api('/api/mission', await page.evaluate(() => { const A = window.SlipdayApp; return A.body(A.selected()[A.current()]); }));
    const band = await page.evaluate(() => document.querySelector('#nvVerdict .vb-word').textContent);
    check('the verdict band equals /api/mission', band === WORD[m.verdict], `${band} / ${m.verdict}, margin ${m.slip_margin_days}`);
    const sent = await page.evaluate(() => document.getElementById('nvSentence').textContent);
    const W = Math.min(w.window_hours, t.count);
    const sunPct = Math.round(100 * t.sun_lit.slice(0, W).reduce((a, b) => a + b, 0) / W);
    check('the summary sentence counts the API track (Sun up share)', sent.includes(`the Sun is up ${sunPct}%`), sent.slice(0, 120));

    // ---- 4. search by name and pick
    await page.click('#nvSearch');
    await page.keyboard.type('apollo 15');
    await sleep(200);
    const found = await page.evaluate(() => Array.from(document.querySelectorAll('#nvList .nv-site .nm')).map((e) => e.textContent));
    check('search by name narrows the list', found.length === 1 && /Apollo 15/.test(found[0]), found.join(', '));
    await page.click('#nvList .nv-site');
    await waitShown(page, 'Apollo 15 (Hadley)');
    const m15 = await api('/api/mission', await page.evaluate(() => { const A = window.SlipdayApp; return A.body(A.selected()[A.current()]); }));
    const band15 = await page.evaluate(() => document.querySelector('#nvVerdict .vb-word').textContent);
    check('picking Apollo 15 shows it, with the API verdict', band15 === WORD[m15.verdict], band15);

    // ---- 5. own coordinates with hemisphere buttons
    await page.evaluate(() => { document.getElementById('nvOwn').open = true; });
    await page.type('#nvLat', '85.4'); await page.type('#nvLon', '31.6');
    await page.click('input[name="nvEW"][value="W"]');
    await page.click('#nvUse');
    await page.waitForFunction(() => { const A = window.SlipdayApp, s = A.selected()[A.current()]; return s && s.lat === -85.4 && s.lon === -31.6; }, { timeout: 30000 }).then(() => check('own coordinates: 85.4 South, 31.6 West give -85.4, -31.6', true))
      .catch(() => check('own coordinates: 85.4 South, 31.6 West give -85.4, -31.6', false));

    // ---- 6. the comparison table
    await page.waitForFunction(() => { const A = window.SlipdayApp; return A.selected().every((s, i) => A.mission(i)) && document.querySelectorAll('.nv-cmp thead th[scope=col]').length === A.selected().length + 1 && !document.querySelector('.nv-cmp tbody tr:first-child .wait'); }, { timeout: 180000 });
    const cols = await page.evaluate(() => {
      const A = window.SlipdayApp, cells = Array.from(document.querySelectorAll('.nv-cmp tbody tr'));
      const rowOf = (label) => cells.find((r) => r.querySelector('th').textContent.startsWith(label));
      return A.selected().map((s, i) => ({ body: A.body(s), name: s.name, verdict: rowOf('Can a lander').children[i + 1].querySelector('.vpill').textContent, sun: rowOf('Sunlit hours').children[i + 1].textContent }));
    });
    let bad = [];
    for (const c of cols) {
      const r = await api('/api/mission', c.body);
      if (!c.verdict.includes(WORD[r.verdict]) || !c.sun.startsWith(String(r.days[0].sunlit_h))) { bad.push(`${c.name}: page ${c.verdict} ${c.sun}, API ${r.verdict} ${r.days[0].sunlit_h}`); }
    }
    check('every comparison column shows the API verdict and sunlit hours', cols.length >= 2 && !bad.length, `${cols.length} columns` + (bad.length ? '; ' + bad.join('; ') : ''));
    const before = cols.length;
    await page.click('.nv-cmp [data-rm="1"]');
    await page.waitForFunction((n) => window.SlipdayApp.selected().length === n - 1, { timeout: 30000 }, before).then(() => check('"Remove" takes a site out in one click', true))
      .catch(() => check('"Remove" takes a site out in one click', false));

    // ---- 7. the decision path, back on the worked example
    await page.evaluate(() => document.querySelector('#nvPresets [data-pre="0"]').click());
    await waitShown(page, first);
    await page.waitForFunction(() => document.querySelectorAll('#dpOpts .dp-opt').length > 0 && !/Still checking/.test(document.getElementById('dpOpts').textContent), { timeout: 240000 });
    const opts = await page.evaluate(() => Array.from(document.querySelectorAll('#dpOpts .dp-opt')).map((li) => ({ text: li.textContent, go: li.querySelector('[data-go]') && li.querySelector('[data-go]').getAttribute('data-go') })));
    const mv = opts.find((o) => o.go);
    let mvOk = false, mvDetail = 'no move option';
    if (mv) {
      const mm = await api('/api/mission', await page.evaluate(() => { const A = window.SlipdayApp; return A.body(A.selected()[A.current()]); }));
      const fail = mm.verdict === 'yes' ? mm.slip_margin_days + 1 : 0;
      const b = await page.evaluate((id) => { const A = window.SlipdayApp; const x = A.body({ id: id }); return x; }, mv.go);
      b.landing = mm.days[fail].landing_utc; b.slip_days = 30;
      const r = await api('/api/mission', b);
      mvOk = mv.text.includes(WORD[r.verdict]); mvDetail = `${mv.go}: page "${mv.text.slice(0, 80)}", API ${r.verdict}`;
    }
    check('a "move" option in the decision path has the API verdict for that site on the failing day', mvOk, mvDetail);

    // ---- 7b. the slip input and a map click, with the headline following the slip and an instant precomputed answer
    await page.$eval('#nvSlip', (i) => { i.value = '10'; i.dispatchEvent(new Event('change')); });
    await page.waitForFunction(() => /Launch slipped 10 days/.test(document.getElementById('nvVerdict').textContent), { timeout: 120000 })
      .then(() => check('with a slip set, the verdict band shows the slipped answer', true)).catch(() => check('with a slip set, the verdict band shows the slipped answer', false));
    await page.$eval('#nvSlip', (i) => { i.value = '0'; i.dispatchEvent(new Event('change')); });
    const mb = await (await page.$('#polar svg')).boundingBox();
    await page.mouse.click(mb.x + mb.width * 0.62, mb.y + mb.height * 0.3);
    await page.waitForFunction(() => /Precomputed|Can a lander work here|Launch slipped/.test(document.getElementById('nvVerdict').textContent), { timeout: 30000 })
      .then(() => check('a map click answers at once (precomputed first, then the full check)', true)).catch(() => check('a map click answers at once (precomputed first, then the full check)', false));
    await sleep(2000);

    check('no script errors', errors.length === 0, errors.join(' | ').slice(0, 300));

    // ---- 8. widths and modes
    const wide = [];
    for (const [vw, vh] of [[1920, 1080], [1280, 800], [768, 1024], [390, 844]]) {
      for (const mode of ['light', 'dark']) {
        await page.emulateMediaFeatures([{ name: 'prefers-color-scheme', value: mode }]);
        await page.setViewport({ width: vw, height: vh });
        await sleep(600);
        const sw = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
        if (sw > 0) { wide.push(`${vw} ${mode}: ${sw} px`); }
      }
    }
    check('no sideways scroll at 1920, 1280, 768 and 390 px, light and dark', !wide.length, wide.join('; '));
  } finally {
    await browser.close();
  }
}

main().catch((e) => { check('test run finished without an exception', false, String(e && e.stack || e)); })
  .finally(() => {
    stopServer();
    const bad = results.filter((r) => !r.ok).length;
    console.log(`\n${results.length - bad} passed, ${bad} failed`);
    process.exitCode = bad ? 1 : 0;
  });
