// Headless browser check for the "Listen and play" add-ons (static/addons/listen.js, planner_game.js).
//
//   node tests/addons/listen_game_check.mjs
//
// It starts its own Slipday server on port 8131 (ADDON_PORT to change it, 8130-8139 only), opens
// /static/addons/demo.html (a copy of the app page plus the two add-ons) in headless Chrome or Edge, and checks:
//   1. the add-on buttons exist and each is reached with the Tab key;
//   2. the main card gets a short spoken summary, labels and arrow-key moves along the day strip;
//   3. "Read it as text" and "Play" update the live text region, and the words match the server's own numbers;
//   4. the game runs five rounds and every verdict shown equals the one the API gives for that site and slip;
//   5. at phone width nothing in the add-ons is wider than the screen.
// The server it started is stopped by PID at the end.  ADDON_BASE=http://127.0.0.1:PORT uses a running server instead.
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

const PORT = parseInt(process.env.ADDON_PORT || '8131', 10);
if (!process.env.ADDON_BASE && !((PORT >= 8130 && PORT <= 8139) || (PORT >= 8180 && PORT <= 8189))) { throw new Error('use a port from 8130 to 8139 or 8180 to 8189'); }
const BASE = process.env.ADDON_BASE || `http://127.0.0.1:${PORT}`;
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
  if (process.env.ADDON_BASE) { return; }
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
    // on Windows the venv python.exe is a launcher with a child process: stop the launcher and its child, by PID
    if (process.platform === 'win32') { spawnSync('taskkill', ['/PID', String(server.pid), '/T', '/F'], { stdio: 'ignore' }); }
    else { try { process.kill(server.pid); } catch (e) { /* gone */ } }
    console.log(`server PID ${server.pid} (and its child) stopped`);
  }
}

async function main() {
  await startServer();
  const exe = BROWSERS.find((p) => fs.existsSync(p));
  if (!exe) { throw new Error('no Chrome or Edge found'); }
  const browser = await puppeteer.launch({ executablePath: exe, headless: true,
    args: ['--autoplay-policy=no-user-gesture-required', '--mute-audio', '--no-first-run'] });
  try {
    const page = await browser.newPage();
    const errors = [];
    page.on('pageerror', (e) => errors.push(String(e.message || e)));
    await page.setViewport({ width: 1280, height: 900 });
    await page.goto(BASE + '/static/addons/demo.html', { waitUntil: 'domcontentloaded' });

    // ---- the app's own card has to be there first
    await page.waitForSelector('#missionOut .verdict', { timeout: 180000 });
    await page.waitForFunction(() => window.SlipdayAddonTap && window.SlipdayAddonTap.lastWhy(), { timeout: 180000 });
    check('the main card drew its answer and the add-ons saw the page ask for it', true);

    // ---- 1. controls exist and are reached with the Tab key
    const ids = ['sd-listen-play', 'sd-listen-stop', 'sd-listen-vol', 'sd-listen-text', 'sd-a11y-jump', 'sd-a11y-say', 'sd-game-start'];
    const present = await page.evaluate((ids) => ids.filter((i) => !!document.getElementById(i)), ids);
    check('all add-on controls exist', present.length === ids.length, `${present.length} of ${ids.length}`);
    await page.evaluate(() => { document.activeElement && document.activeElement.blur(); window.scrollTo(0, 0); });
    const seen = new Set();
    for (let k = 0; k < 700 && seen.size < ids.length; k++) {
      await page.keyboard.press('Tab');
      const id = await page.evaluate(() => document.activeElement && document.activeElement.id);
      if (ids.includes(id)) { seen.add(id); }
    }
    check('every add-on control is reached with the Tab key', seen.size === ids.length, [...seen].join(', '));

    // ---- 2. main card: summary, labels, arrow keys
    await page.waitForFunction(() => { const s = document.getElementById('sd-a11y-status'); return s && /Answer/.test(s.textContent); }, { timeout: 30000 });
    const card = await page.evaluate(() => ({
      status: document.getElementById('sd-a11y-status').textContent,
      word: document.querySelector('#missionOut .vWord').textContent,
      live: document.getElementById('missionOut').getAttribute('aria-live'),
      vlabel: document.querySelector('#missionOut .verdict').getAttribute('aria-label'),
      strip: document.getElementById('vstrip') && document.getElementById('vstrip').getAttribute('role'),
      stops: Array.from(document.querySelectorAll('#vstrip button')).filter((b) => b.tabIndex === 0).length
    }));
    check('the card answer is announced in a live region', card.status.includes(': ' + card.word + '.'), card.status.slice(0, 160));
    check('the verdict has a label and the long card is no longer read out whole', !!card.vlabel && card.live === 'off', card.vlabel);
    check('the day strip is one labelled group with one Tab stop', card.strip === 'group' && card.stops === 1);
    await page.waitForFunction(() => document.querySelectorAll('#winLine button[data-win]').length > 0, { timeout: 120000 }).catch(() => {});
    await sleep(1200);
    const winSaid = await page.evaluate(() => ({ s: document.getElementById('sd-a11y-status').textContent,
      lab: (document.querySelector('#winLine button[data-win]') || {}).getAttribute ? document.querySelector('#winLine button[data-win]').getAttribute('aria-label') : null }));
    check('the next monthly windows are announced and labelled', /Next monthly launch windows/.test(winSaid.s) && /Landing on/.test(winSaid.lab || ''), (winSaid.lab || '').slice(0, 90));
    const moved = await page.evaluate(() => {
      const b = document.querySelector('#vstrip button[tabindex="0"]'); b.focus();
      b.dispatchEvent(new KeyboardEvent('keydown', { key: 'ArrowRight', bubbles: true }));
      const list = Array.from(document.querySelectorAll('#vstrip button'));
      return list.indexOf(document.activeElement) - list.indexOf(b);
    });
    check('the right-arrow key moves along the day strip', moved === 1);
    await page.click('#sd-a11y-jump');
    const focusedVerdict = await page.evaluate(() => document.activeElement && document.activeElement.classList.contains('verdict'));
    check('"Go to the answer" moves focus to the verdict', focusedVerdict);

    // ---- 3. listen: text first, then sound with the live region following it
    const plan = await page.evaluate(() => window.SlipdayAddonTap.plan());
    const w = await api('/api/why', plan);
    const geo = await api('/api/why', { ...plan, earth_stations: false });
    const W = Math.min(w.window_hours, w.track.count);
    const sunH = w.track.sun_lit.slice(0, W).reduce((a, b) => a + b, 0);
    const earthH = geo.track.earth_up.slice(0, W).reduce((a, b) => a + b, 0);
    await page.click('#sd-listen-text');
    await page.waitForFunction(() => /Day 1/.test(document.getElementById('sd-listen-now').textContent), { timeout: 60000 });
    const txt = await page.evaluate(() => ({ now: document.getElementById('sd-listen-now').textContent,
      items: Array.from(document.querySelectorAll('#sd-listen-list li')).map((l) => l.textContent) }));
    const day1 = txt.items[0] || '';
    const d1ok = day1.includes(w.track.sun_lit[0] ? 'Sun up' : 'Sun hidden') && day1.includes(geo.track.earth_up[0] ? 'Earth up' : 'Earth hidden');
    check('"Read it as text" fills the live region and the day list', txt.items.length === Math.ceil(W / 24) + 1, `${txt.items.length} lines for ${Math.ceil(W / 24)} days`);
    check('day 1 in words matches the API (Sun and Earth up or hidden at touchdown)', d1ok, day1);
    check('the hour counts in words match the API', txt.now.includes(`Sun was up for ${sunH} of ${W} hours`) && txt.now.includes(`above the skyline for ${earthH} of ${W} hours`),
      `Sun ${sunH} h, Earth ${earthH} h of ${W}`);
    const sets = txt.items.filter((l) => /sets behind the ground|rises over the ground|dips in and out/.test(l));
    if (sets.length) { console.log('      e.g. ' + sets[0]); }

    await page.focus('#sd-listen-vol');
    await page.keyboard.press('ArrowLeft');
    const vol = await page.evaluate(() => [document.getElementById('sd-listen-vol').value, document.getElementById('sd-listen-vol').getAttribute('aria-valuetext')]);
    check('the volume slider works from the keyboard', vol[0] === '45' && vol[1] === '45 percent', vol.join(' / '));

    const heard = new Set();
    await page.focus('#sd-listen-play');
    await page.keyboard.press('Enter');
    const t0 = Date.now();
    while (Date.now() - t0 < 12000 && heard.size < 3) {
      const s = await page.evaluate(() => document.getElementById('sd-listen-now').textContent);
      const m = /^Day (\d+)/.exec(s); if (m) { heard.add(m[1]); }
      await sleep(150);
    }
    const ctxState = await page.evaluate(() => document.getElementById('sd-listen-play').getAttribute('aria-pressed'));
    check('Play starts the sound and the live text moves from day to day', heard.size >= 3 && ctxState === 'true', 'days heard: ' + [...heard].join(', '));
    await page.click('#sd-listen-stop');
    const stopped = await page.evaluate(() => document.getElementById('sd-listen-now').textContent);
    check('the Stop button stops it and says where', /^Stopped on day \d+/.test(stopped), stopped);

    await page.click('#sd-listen-play');
    await page.waitForFunction(() => /^End of the/.test(document.getElementById('sd-listen-now').textContent), { timeout: 45000 });
    const dur = (Date.now() - t0) / 1000;
    check('a full play ends by itself with the summary', true);
    await page.click('#sd-listen-play');
    await page.waitForFunction(() => /^Day/.test(document.getElementById('sd-listen-now').textContent), { timeout: 20000 });
    await page.focus('#sd-listen-vol');
    await page.keyboard.press('Escape');
    const esc = await page.evaluate(() => document.getElementById('sd-listen-now').textContent);
    check('Escape stops the sound', /^Stopped/.test(esc), esc);
    void dur;

    // ---- 4. the game: a five-scenario campaign, every answer shown checked against the API
    await page.click('#sd-game-start');
    let rounds = 0, verdictsChecked = 0, mismatches = [], reasonsChecked = 0, optionsOk = true;
    const reasonBad = [];
    for (let r = 0; r < 5; r++) {
      await page.waitForSelector('input[name="sd-game-opt"]:not([disabled])', { timeout: 180000 });
      const sc = await page.evaluate(() => window.SlipdayGame.state().sc);
      const grules = await page.evaluate(() => window.SlipdayGame.state().rules);
      if (sc.options.length < 3 || sc.options.length > 4) { optionsOk = false; }
      const k = r % sc.options.length;
      if (r === 0) {                                     // the first pick is made with the keyboard
        await page.focus('input[name="sd-game-opt"][value="0"]');
        await page.keyboard.press('Space');
        for (let j = 0; j < k; j++) { await page.keyboard.press('ArrowDown'); }
        await page.focus('#sd-game-commit');
        await page.keyboard.press('Enter');
      } else {
        await page.click(`.sd-opt[data-i="${k}"]`);
        await page.click('#sd-game-commit');
      }
      await page.waitForSelector('#sd-game-outcome', { timeout: 240000 });
      const ans = await page.evaluate(() => Array.from(document.querySelectorAll('.sd-cmp tbody tr')).map((tr) => ({
        site: JSON.parse(tr.getAttribute('data-site')), verdict: tr.getAttribute('data-verdict'), landing: tr.getAttribute('data-landing'),
        mine: tr.classList.contains('sd-mine') })));
      const outText = await page.evaluate(() => document.getElementById('sd-game-outcome').textContent.replace(/\s+/g, ' '));
      for (let i = 0; i < ans.length; i++) {
        const a = ans[i], o = sc.options[i];
        const body = { ...grules, need_sun_h: sc.need.need_sun_h, need_earth_h: sc.need.need_earth_h, window_days: sc.need.window_days,
          site: { id: o.site }, landing: o.landing, slip_days: 30 };
        const m = await api('/api/mission', body);
        const d = m.days[0];
        verdictsChecked++;
        if (a.verdict !== m.verdict || a.landing !== m.landing_utc || a.site.id !== o.site) { mismatches.push(`${o.site} ${o.landing}: page ${a.verdict}, API ${m.verdict}`); continue; }
        if (!a.mine) { continue; }
        // the reason's numbers and direction come from the API too
        const t = outText;
        const sunM = /only (\d+) hours of sunlight/.exec(t), earthM = /for only (\d+) hours; it needs/.exec(t);
        if (sunM && +sunM[1] !== d.sunlit_h) { reasonBad.push(`${o.site}: sunlight ${sunM[1]} vs ${d.sunlit_h}`); }
        if (earthM && +earthM[1] !== d.earth_h) { reasonBad.push(`${o.site}: Earth ${earthM[1]} vs ${d.earth_h}`); }
        if (a.verdict === 'yes' && !(t.includes(`${d.sunlit_h} hours of sunlight`) && t.includes(`${d.earth_h} hours of radio contact`))) { reasonBad.push(`${o.site}: yes numbers`); }
        const dir = /behind the ground (?:[\d]+ km away )?to the ([a-z-]+)/.exec(t);
        if (dir) {
          const g = await api('/api/why', { ...body, day: 0, earth_stations: false });
          const dirs = [...g.sun_hidden, ...g.earth_hidden].map((s) => s.terrain && s.terrain.compass);
          if (!dirs.includes(dir[1])) { reasonBad.push(`${o.site}: direction ${dir[1]} not in ${dirs.join('/')}`); }
        }
        reasonsChecked++;
      }
      console.log(`      scenario ${r + 1} (${sc.id}, slip ${sc.slip} d) -> ` + ans.map((a) => `${a.site.id}: ${a.verdict}${a.mine ? ' (picked)' : ''}`).join(', '));
      rounds++;
      await page.click('#sd-game-next');
    }
    await page.waitForSelector('#sd-game-end', { timeout: 10000 });
    const end = await page.evaluate(() => document.getElementById('sd-game-end').textContent + ' | ' + document.getElementById('sd-game-score').textContent);
    check('the game runs five scenarios to a final campaign score', rounds === 5 && /Campaign complete: \d+ points/.test(end), end);
    check('each scenario offers three or four options', optionsOk);
    check('every outcome reason uses the API numbers and the direction of the hiding ground', reasonsChecked === 5 && reasonBad.length === 0,
      `${reasonsChecked} checked` + (reasonBad.length ? '; ' + reasonBad.join('; ') : ''));
    check('every verdict in the game equals the API answer for that site and landing', verdictsChecked >= 15 && mismatches.length === 0,
      `${verdictsChecked} checked` + (mismatches.length ? '; ' + mismatches.join('; ') : ''));
    // ---- 4b. pressed early (before the page has asked for its skyline view), Listen still uses the card's site
    await page.reload({ waitUntil: 'domcontentloaded' });
    await page.waitForSelector('#missionOut .verdict', { timeout: 180000 });
    await page.click('#sd-listen-text');
    await page.waitForFunction(() => /^Now set to/.test(document.getElementById('sd-listen-what').textContent) &&
      /End of the/.test(document.getElementById('sd-listen-now').textContent), { timeout: 60000 });
    const early = await page.evaluate(() => ({ what: document.getElementById('sd-listen-what').textContent,
      shown: document.getElementById('mSite').options[document.getElementById('mSite').selectedIndex].textContent,
      now: document.getElementById('sd-listen-now').textContent, plan: window.SlipdayAddonTap.plan() }));
    const w2 = await api('/api/why', early.plan);
    const sun2 = w2.track.sun_lit.slice(0, Math.min(w2.window_hours, w2.track.count)).reduce((a, b) => a + b, 0);
    check('pressed at once after loading, Listen plays the site the card shows', early.what.includes(early.shown) && w2.site.name === early.shown &&
      early.now.includes(`Sun was up for ${sun2} of`), early.what.slice(0, 110));

    // ---- 5. phone width, reduced motion
    await page.setViewport({ width: 375, height: 800 });           // isMobile would reload the page
    await page.click('#sd-game-start');
    await page.waitForSelector('.sd-opt', { timeout: 180000 });
    const phone = await page.evaluate(() => {
      const over = Array.from(document.querySelectorAll('#addon-listen *, #addon-game *')).filter((e) => { if (e.closest('.sd-tablewrap')) { return false; } return e.getBoundingClientRect().right > window.innerWidth + 1; }).length;
      const xs = Array.from(document.querySelectorAll('.sd-opt')).map((b) => Math.round(b.getBoundingClientRect().left));
      return { over, oneColumn: new Set(xs).size === 1 };
    });
    check('at 375 px nothing in the add-ons is wider than the screen, and the choices stack', phone.over === 0 && phone.oneColumn, JSON.stringify(phone));
    await page.emulateMediaFeatures([{ name: 'prefers-reduced-motion', value: 'reduce' }]);
    const rm = await page.evaluate(() => getComputedStyle(document.querySelector('.sd-opt')).transitionDuration);
    check('reduced motion: no transitions in the add-ons', /^0s/.test(rm), rm);

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
