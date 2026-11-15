// Headless browser check for the mission-planner campaign (static/addons/planner_game.js).
//
//   node tests/addons/game_check.mjs
//
// It starts its own Slipday server on port 8182 (GAME_PORT to change it, 8180-8189 only), opens the app page in
// headless Chrome or Edge and plays the first scenario end to end with the keyboard:
//   1. Start with Enter, focus moves to the briefing heading, the briefing names the need, the plan and the slip;
//   2. the arrow keys choose an option, and its inspect panel shows hours that equal an independent API call;
//   3. Enter on "Commit" reveals the outcome, focus moves to it, and its verdict, slip margin, sunlit and Earth hours
//      equal an independent /api/mission call for that option's site and landing with the same rules;
//   4. every row of the comparison table equals the API too, the points follow the stated rule, and the best row is
//      the highest score;
//   5. no script errors, and at 390 px nothing in the game is wider than the screen.
// The server it started is stopped by PID at the end.  GAME_BASE=http://127.0.0.1:PORT uses a running server instead.
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

const PORT = parseInt(process.env.GAME_PORT || '8182', 10);
if (!process.env.GAME_BASE && (PORT < 8180 || PORT > 8189)) { throw new Error('use a port from 8180 to 8189'); }
const BASE = process.env.GAME_BASE || `http://127.0.0.1:${PORT}`;
const PAGE = process.env.GAME_PAGE || '/';
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
  if (process.env.GAME_BASE) { return; }
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
const RULE = { yes: 100, 'not sure': 40, no: 0, 'n/a': 0 };
function points(m, waited) {
  const margin = m.verdict === 'yes' ? Math.min(50, 5 * Math.max(0, m.slip_margin_days)) : 0;
  return Math.max(0, RULE[m.verdict] + margin - (waited || 0));
}

async function main() {
  await startServer();
  const exe = BROWSERS.find((p) => fs.existsSync(p));
  if (!exe) { throw new Error('no Chrome or Edge found'); }
  const browser = await puppeteer.launch({ executablePath: exe, headless: true, args: ['--no-first-run', '--mute-audio'] });
  try {
    const page = await browser.newPage();
    const errors = [];
    page.on('pageerror', (e) => errors.push(String(e.message || e)));
    await page.setViewport({ width: 1280, height: 900 });
    await page.goto(BASE + PAGE, { waitUntil: 'domcontentloaded' });
    await page.waitForSelector('#sd-game-start', { timeout: 60000 });
    // open whatever fold or tab holds the game, then start with the keyboard
    await page.evaluate(() => {
      let n = document.getElementById('addon-game');
      while (n) { if (n.tagName === 'DETAILS') { n.open = true; } if (n.hidden) { n.hidden = false; } n = n.parentElement; }
    });
    await page.focus('#sd-game-start');
    await page.keyboard.press('Enter');
    await page.waitForSelector('#sd-game-q', { timeout: 180000 });
    const brief = await page.evaluate(() => ({ focus: document.activeElement && document.activeElement.id, text: document.getElementById('sd-game-stage').textContent,
      sc: window.SlipdayGame.state().sc }));
    check('Start (Enter) opens scenario 1 and moves focus to its heading', brief.focus === 'sd-game-q', brief.focus);
    check('the briefing names the need, the plan and the slip, and says the need is illustrative',
      brief.text.includes(`${brief.sc.need.need_sun_h} h of sunlight`) && brief.text.includes(`Your launch slipped ${brief.sc.slip} day`) &&
      /illustrative/.test(brief.text), brief.text.replace(/\s+/g, ' ').slice(0, 160));

    // ---- choose the second option with the arrow keys
    await page.focus('input[name="sd-game-opt"][value="0"]');
    await page.keyboard.press('Space');
    await page.keyboard.press('ArrowDown');
    const chosen = await page.evaluate(() => window.SlipdayGame.state().chosen);
    check('the arrow keys move the choice to the next option', chosen === 1, String(chosen));
    await page.waitForSelector('#sd-game-inspect[data-ready]', { timeout: 180000 });
    const sc = await page.evaluate(() => window.SlipdayGame.state().sc);
    const rules = await page.evaluate(() => { const g = window.SlipdayGame.state(); return g.rules; });
    const opt = sc.options[1];
    const body = { ...rules, need_sun_h: sc.need.need_sun_h, need_earth_h: sc.need.need_earth_h, window_days: sc.need.window_days,
      site: { id: opt.site }, landing: opt.landing, slip_days: 30 };
    const m = await api('/api/mission', body);
    const ins = await page.evaluate(() => document.getElementById('sd-game-inspect').textContent.replace(/\s+/g, ' '));
    check('the inspect panel shows the API hours against the need', ins.includes(`${m.days[0].sunlit_h} h of ${m.need.sunlit_h} needed`) &&
      ins.includes(`${m.days[0].earth_h} h of ${m.need.earth_h} needed`), ins.slice(0, 200));
    const hidden = await page.evaluate(() => !document.getElementById('sd-game-outcome'));
    check('the answer stays hidden until the player commits', hidden);

    // ---- commit with the keyboard
    await page.focus('#sd-game-commit');
    await page.keyboard.press('Enter');
    await page.waitForSelector('#sd-game-outcome', { timeout: 240000 });
    await page.waitForFunction(() => /Outcome:/.test(document.getElementById('sd-game-status').textContent), { timeout: 5000 }).catch(() => {});
    const out = await page.evaluate(() => {
      const o = document.getElementById('sd-game-outcome');
      return { focus: document.activeElement && document.activeElement.id, site: JSON.parse(o.getAttribute('data-site')), landing: o.getAttribute('data-landing'),
        verdict: o.getAttribute('data-verdict'), margin: +o.getAttribute('data-margin'), sun: +o.getAttribute('data-sun'), earth: +o.getAttribute('data-earth'),
        score: +o.getAttribute('data-score'), text: o.textContent.replace(/\s+/g, ' '),
        rows: Array.from(document.querySelectorAll('.sd-cmp tbody tr')).map((tr) => ({ site: JSON.parse(tr.getAttribute('data-site')), landing: tr.getAttribute('data-landing'),
          verdict: tr.getAttribute('data-verdict'), margin: +tr.getAttribute('data-margin'), sun: +tr.getAttribute('data-sun'), earth: +tr.getAttribute('data-earth'),
          pts: +tr.lastElementChild.textContent, best: tr.classList.contains('sd-best') })),
        status: document.getElementById('sd-game-status').textContent };
    });
    check('Commit moves focus to the outcome heading', out.focus === 'sd-game-out-h', out.focus);
    const okOut = out.site.id === opt.site && out.landing === m.landing_utc && out.verdict === m.verdict && out.margin === m.slip_margin_days &&
      out.sun === m.days[0].sunlit_h && out.earth === m.days[0].earth_h;
    check('the outcome equals an independent /api/mission call (verdict, slip margin, sunlit and Earth hours)', okOut,
      `page ${out.verdict}/${out.margin} d/${out.sun} h/${out.earth} h; API ${m.verdict}/${m.slip_margin_days} d/${m.days[0].sunlit_h} h/${m.days[0].earth_h} h at ${m.landing_utc}`);
    check('the points follow the stated rule', out.score === points(m, opt.waitedDays), `${out.score} vs ${points(m, opt.waitedDays)}`);
    if (m.verdict === 'yes') { check('a Yes reason carries the API hours', out.text.includes(`${m.days[0].sunlit_h} hours of sunlight`) && out.text.includes(`${m.days[0].earth_h} hours of radio contact`)); }
    let rowsOk = out.rows.length === sc.options.length, bad = [];
    for (let k = 0; k < out.rows.length; k++) {
      const r = out.rows[k], o = sc.options[k];
      const mm = await api('/api/mission', { ...body, site: { id: o.site }, landing: o.landing });
      if (r.verdict !== mm.verdict || r.margin !== mm.slip_margin_days || r.sun !== mm.days[0].sunlit_h || r.earth !== mm.days[0].earth_h || r.pts !== points(mm, o.waitedDays)) {
        rowsOk = false; bad.push(`${o.site} ${o.landing}: page ${r.verdict} ${r.pts}, API ${mm.verdict} ${points(mm, o.waitedDays)}`);
      }
    }
    const topPts = Math.max(...out.rows.map((r) => r.pts));
    check('every option in the comparison equals the API, and its points follow the rule', rowsOk, bad.join('; ') || out.rows.map((r) => `${r.site.id}:${r.verdict}:${r.pts}`).join(', '));
    check('the row marked best has the highest score', out.rows.some((r) => r.best && r.pts === topPts));
    check('the outcome is announced in the live region', /Outcome:/.test(out.status), out.status.slice(0, 120));
    if (sc.options.some((o) => o.kind === 'wait')) {
      const w = await api('/api/windows', { ...body, site: { id: sc.site }, landing: sc.plan });
      const next = w.rows.find((r) => Date.parse(r.landing_utc) > Date.parse(sc.slipped));
      const wo = sc.options.find((o) => o.kind === 'wait');
      check('the "wait" option is the next monthly window from /api/windows', next && wo.landing === next.landing_utc, `${wo.landing} vs ${next && next.landing_utc}`);
    }
    console.log('      scenario 1: ' + out.rows.map((r) => `${r.site.id} ${r.landing.slice(0, 16)} ${r.verdict} ${r.pts}`).join(' | '));

    // ---- next scenario loads
    await page.focus('#sd-game-next');
    await page.keyboard.press('Enter');
    await page.waitForFunction(() => window.SlipdayGame.state().k === 1 && document.getElementById('sd-game-q'), { timeout: 180000 });
    check('Next scenario opens scenario 2', true);

    // ---- phone width
    await page.setViewport({ width: 390, height: 844 });
    await sleep(400);
    const over = await page.evaluate(() => Array.from(document.querySelectorAll('#addon-game *')).filter((e) => {
      const r = e.getBoundingClientRect(); if (!r.width) { return false; }
      let p = e.parentElement; while (p) { if (getComputedStyle(p).overflowX === 'auto') { return false; } p = p.parentElement; }
      return r.right > window.innerWidth + 1;
    }).map((e) => e.className || e.tagName).slice(0, 5));
    check('at 390 px nothing in the game is wider than the screen', over.length === 0, over.join(', '));
    const tap = await page.evaluate(() => Array.from(document.querySelectorAll('#addon-game .sd-opt, #addon-game button')).filter((e) => e.offsetParent).map((e) => e.getBoundingClientRect().height));
    check('tap targets in the game are at least 44 px high', tap.length > 0 && Math.min(...tap) >= 43.5, `min ${Math.min(...tap)}`);
    check('no script errors on the page', errors.length === 0, errors.join(' | ').slice(0, 300));
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
