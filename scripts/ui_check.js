// Browser checks and screenshots against a running Slipday server.
//   NODE_PATH=/path/to/node_modules node scripts/ui_check.js http://127.0.0.1:8100/ /tmp/slipday_shots
// Needs puppeteer-core and a Chrome at /usr/bin/google-chrome (or CHROME=...).
const puppeteer = require('puppeteer-core');
const URL = process.argv[2] || 'http://127.0.0.1:8100/';
const OUT = process.argv[3] || '/tmp/slipday_shots';
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
let failures = 0;
function check(name, ok, detail) {
  console.log((ok ? 'PASS ' : 'FAIL ') + name + (detail !== undefined ? '  [' + detail + ']' : ''));
  if (!ok) { failures += 1; }
}

(async () => {
  const browser = await puppeteer.launch({ executablePath: process.env.CHROME || '/usr/bin/google-chrome', headless: 'new', args: ['--no-sandbox'] });
  const log = [];
  async function open(w, h, mobile, scheme, url) {
    const page = await browser.newPage();
    await page.setViewport({ width: w, height: h, deviceScaleFactor: mobile ? 2 : 1, isMobile: !!mobile, hasTouch: !!mobile });
    if (scheme) { await page.emulateMediaFeatures([{ name: 'prefers-color-scheme', value: scheme }]); }
    page.on('console', (m) => { if (m.type() === 'error') { log.push('console.error: ' + m.text()); } });
    page.on('pageerror', (e) => log.push('pageerror: ' + e.message));
    page.on('response', (r) => { if (r.status() >= 400) { log.push('http ' + r.status() + ' ' + r.url()); } });
    const t0 = Date.now();
    await page.goto(url || URL, { waitUntil: 'networkidle0', timeout: 120000 });
    await sleep(600);
    return { page, ms: Date.now() - t0 };
  }
  const idle = (page) => page.waitForNetworkIdle({ idleTime: 500, timeout: 60000 }).catch(() => {});
  const setVal = async (page, id, v) => {
    await page.evaluate((i, val) => { const e = document.getElementById(i); e.value = val; e.dispatchEvent(new Event('change', { bubbles: true })); }, id, v);
    await idle(page); await sleep(300);
  };
  const card = (page) => page.evaluate(() => {
    const v = document.querySelector('#missionOut .verdict');
    return { word: (document.querySelector('#missionOut .vWord') || {}).textContent, sub: (document.querySelector('#missionOut .vSub') || {}).textContent,
      bottom: v ? Math.round(v.getBoundingClientRect().bottom) : null, cells: document.querySelectorAll('#vstrip .vc').length,
      text: (document.querySelector('#missionOut .mText') || {}).textContent, sure: (document.querySelector('#missionOut .sure') || {}).textContent,
      next: Array.from(document.querySelectorAll('#missionOut [data-plan]')).map((b) => b.textContent), date: document.getElementById('start').value,
      hour: document.getElementById('mHour').value, hash: location.hash };
  });
  const tiles = (page) => page.$$eval('.card .tiles', (n) => n.map((x) => x.innerText.replace(/\n+/g, ' | ')));

  // ---- desktop 1280x800, first visit
  let { page, ms } = await open(1280, 800, false, 'light');
  console.log('desktop load to network idle: ' + ms + ' ms');
  await page.screenshot({ path: OUT + '/desktop_1280x800_top.png' });
  await page.screenshot({ path: OUT + '/desktop_1280_full.png', fullPage: true });
  const first = await page.evaluate(() => {
    const grid = document.getElementById('slip').getBoundingClientRect();
    return { firstHeading: document.querySelector('section.panel h2').textContent, gridTop: Math.round(grid.top), vh: window.innerHeight,
      cells: document.querySelectorAll('#slip button.cell').length, rows: document.querySelectorAll('#slip .srow').length - 1,
      spread: document.querySelectorAll('#slip .strip.thin.spread').length, verdicts: Array.from(document.querySelectorAll('#slip .srow > .sbest:not(.sub)')).slice(1).map((x) => x.textContent),
      badge: document.getElementById('horizonBadge').textContent, metric: document.getElementById('slipMetric').value };
  });
  const c0 = await card(page);
  /* UX pass: the first screen holds the inputs, the verdict, the objective line, the chart, the next windows and the actions */
  await page.waitForFunction(() => /Challenge objective/.test((document.getElementById('objLine') || {}).textContent || ''), { timeout: 60000 }).catch(() => {});
  const fs = await page.evaluate(() => {
    const b = (id) => { const e = document.getElementById(id); return e ? Math.round(e.getBoundingClientRect().bottom) : 9999; };
    const wl = document.querySelector('#winLine [data-win]');
    return { obj: (document.getElementById('objLine') || {}).textContent || '', objB: b('objLine'), chartB: Math.round((document.querySelector('#why svg.whySvg') || { getBoundingClientRect: () => ({ bottom: 9999 }) }).getBoundingClientRect().bottom),
      winB: wl ? Math.round(wl.getBoundingClientRect().bottom) : 9999, dlB: b('dlAnswer'), optB: b('optGo'), jump: document.querySelectorAll('#jumpBar a').length,
      legend: (document.querySelector('#why .whyLegend') || {}).textContent || '', main: !!document.querySelector('main#main'), skip: document.querySelectorAll('a.skip').length };
  });
  check('first screen: an objective line with the Sun and the Earth direction and height above the skyline, in numbers',
    /Challenge objective/.test(fs.obj) && /Sun azimuth \d+° \(\w+\), -?\d+\.\d° above level, \d+\.\d° (above|below) the skyline/.test(fs.obj) && /Earth azimuth \d+°/.test(fs.obj) && fs.objB < 800, fs.obj);
  check('first screen: the skyline chart with a legend, the next windows, Other sites and Download',
    fs.chartB < 800 && /hidden by the ground/.test(fs.legend) && fs.winB < 800 && fs.optB < 800 && fs.dlB < 800, JSON.stringify({ chart: fs.chartB, win: fs.winB, other: fs.optB, dl: fs.dlB }));
  check('a jump bar, skip links and a main landmark', fs.jump >= 7 && fs.skip >= 2 && fs.main, fs.jump + ' links, ' + fs.skip + ' skip links');
  /* the specialist panels start folded; open them all for the checks that follow */
  await page.evaluate(() => { document.querySelectorAll('details.fold, #validMore').forEach((d) => { d.open = true; }); window.dispatchEvent(new Event('resize')); });
  await sleep(800);
  check('the mission card is the first panel', /^Can this mission still land/.test(first.firstHeading), first.firstHeading);
  check('the verdict is on the first 1280x800 screen without scrolling', c0.bottom !== null && c0.bottom < 800, c0.word + ', ' + c0.sub + ' (bottom ' + c0.bottom + ' px)');
  check('first visit lands on a plan with a slip margin', c0.word === 'Yes' && /survives a slip of up to/.test(c0.sub), c0.sub + ' | planned ' + c0.date);
  check('one verdict cell per day of slip, and three next good dates', c0.cells === 60 && c0.next.length === 3, c0.cells + ' cells; next ' + c0.next.join(', '));
  check('the card says how sure it is', /How sure: \d+ of 13 points within \d+ m/.test(c0.sure), c0.sure);
  check('the headline says which landing scatter the Yes assumes', /if it touches down within \d+ m of the target/.test(c0.sub), c0.sub);
  await page.waitForFunction(() => document.querySelectorAll('#circles .cRow').length === 4, { timeout: 120000 }).catch(() => {});
  const circ = await page.evaluate(() => ({ rows: Array.from(document.querySelectorAll('#circles .cRow')).map((r) => r.innerText.replace(/\n+/g, ' ')),
    bars: document.querySelectorAll('#circles .cStrip .cc').length, cap: (document.querySelector('#circles .cap') || {}).textContent || '' }));
  check('landing circles: four circle sizes, one bar per day of slip, with the stated assumption', circ.rows.length === 4 && /within 100 m/.test(circ.rows[0]) &&
    /within 1 km/.test(circ.rows[3]) && circ.rows.every((r) => /\d+% as planned|not resolvable/.test(r)) && circ.bars % 60 === 0 && /not a dispersion model/.test(circ.cap), circ.rows.join(' ; '));
  console.log('card text: ' + c0.text);
  // pass 2: the Sun and the Earth against the skyline, on the first screen, for the chosen cell of the strip
  await page.waitForFunction(() => !!document.querySelector('#why svg .sunl') && !!document.querySelector('#ribbon svg') &&
    document.querySelectorAll('#classes .lRow').length === 3, { timeout: 120000 }).catch(() => {});
  const why0 = await page.evaluate(() => {
    const svg = document.querySelector('#why svg'), b = svg ? svg.getBoundingClientRect() : null;
    return { bottom: b ? Math.round(b.bottom) : null, sun: document.querySelectorAll('#why svg path.sunl').length, earth: document.querySelectorAll('#why svg path.earthl').length,
      sky: document.querySelectorAll('#why svg path.skyfill').length, head: (document.querySelector('#why .whyHead') || {}).textContent || '',
      txt: (document.querySelector('#why .whyTxt') || {}).textContent || '', flip: (document.querySelector('#why .whyFlip') || {}).textContent || '',
      diff: (document.getElementById('smoothDiff') || {}).textContent || '', outlined: document.querySelectorAll('#vstrip2 .vc.diff').length,
      ribbon: (document.querySelector('#ribbon .ribHead') || {}).textContent || '', ribCells: document.querySelectorAll('#ribbon svg rect').length,
      classes: Array.from(document.querySelectorAll('#classes .lRow')).map((r) => r.innerText.replace(/\n+/g, ' ')), classCap: (document.querySelector('#classes .cap') || {}).textContent || '',
      classHead: (document.querySelector('#classes .cHead') || {}).textContent || '', circlesText: document.getElementById('circles').textContent,
      links: Array.from(document.querySelectorAll('#siteLinks a')).map((a) => a.href) };
  });
  check('the Sun and the Earth against the terrain skyline are on the first 1280x800 screen', why0.bottom !== null && why0.bottom < 800 && why0.sun >= 1 && why0.earth >= 1 && why0.sky === 1 &&
    /as planned/.test(why0.head), 'chart bottom ' + why0.bottom + ' px; ' + why0.head);
  check('time left to sunset and Earthset is said beside the skyline, with the rule each number uses', /Sun at touchdown [-\d.]+° up/.test(why0.txt) && /(Earthset in|up for the whole window)/.test(why0.txt) &&
    /sunlit h of \d+ needed/.test(why0.txt) && /centre must clear the skyline/.test(why0.txt) && /disc/.test(why0.txt), why0.txt.slice(0, 230));
  check('the card names what ends the margin: which touchdown point, which body, which ground', /What ends the margin/.test(why0.flip) && /A slip of \d+ days?/.test(why0.flip) &&
    /azimuth \d+ deg/.test(why0.flip) && /(Sun|Earth) (goes behind|comes out from behind|is behind)/.test(why0.flip), why0.flip.slice(0, 260));
  check('the card says on how many dates terrain changes a smooth-sphere answer, and outlines them', /(Terrain changes its answer|Real hills change it) on \d+ of 60 dates/.test(why0.diff) && why0.outlined >= 1, why0.diff + ' | ' + why0.outlined + ' outlined');
  check('a year of landing dates under the inputs', /\d+ clear yes of 365/.test(why0.ribbon) && why0.ribCells >= 300, why0.ribbon + ' | ' + why0.ribCells + ' cells');
  check('chance by lander class: three assumed dispersions, a range beside each chance', why0.classes.length === 3 && /assumed dispersions/.test(why0.classHead) && /assumptions/.test(why0.classCap) &&
    /not a model of any named lander/.test(why0.classCap) && why0.classes.every((r) => /\d+% as planned/.test(r)) && why0.classes.some((r) => /range \d+ to \d+/.test(r)), why0.classes.join(' ; '));
  check('the landing-circle shares carry a sampling range', /range \d+ to \d+/.test(why0.circlesText) && /resamplings/.test(why0.circlesText), (why0.circlesText.match(/within 250 m.{0,60}/) || [''])[0]);
  check('each site links out to QuickMap and Moon Trek', why0.links.length === 2 && /quickmap/.test(why0.links[0]) && /trek\.nasa\.gov/.test(why0.links[1]), why0.links.map((u) => u.slice(0, 60)).join(' | '));
  const fine = await page.evaluate(() => (document.getElementById('fineNote') || {}).textContent || '');
  const fineTop = await page.evaluate(() => { const e = document.getElementById('fineNote'); return e ? Math.round(e.getBoundingClientRect().bottom) : null; });
  check('the default example says, under the verdict, what NASA\'s 20 m grid answers for it', /On the 20 m grid: (Yes|Not sure|No) as planned \(\d+ of 13 touchdown points\)/.test(fine) &&
    fineTop !== null && fineTop < 800, fine);
  const open0 = await page.evaluate(() => ({ site: document.getElementById('mSite').options[document.getElementById('mSite').selectedIndex].textContent,
    note: (document.getElementById('autoNote') || {}).textContent || '', agree: !!document.querySelector('#fineNote.agree'),
    ended: (document.getElementById('endedBy') || {}).textContent || '', links: Array.from(document.querySelectorAll('#classes .cap a')).map((a) => a.href) }));
  check('the page opens on an example that the 80 m and the 20 m grid both support, and says so', c0.word === 'Yes' && /^Both grids agree\. On the 20 m grid: Yes as planned \(13 of 13 touchdown points\), \d+ days of margin\./.test(fine) &&
    open0.agree && /worked example/.test(open0.note) && /both support/.test(open0.note) && c0.date === '2026-11-18', open0.site + ' | ' + fine);
  check('the card says which need ends the margin and whether that need is published or illustrative', /^Ended by (the Earth-contact need|the sunlit-hours need) \(\d+ of \d+ h\), (an illustrative figure, not a published requirement|a figure from the mission’s published plan)\./.test(open0.ended), open0.ended);
  check('each assumed lander class links to the page its figure was read on', open0.links.length === 3 && /jaxa\.jp/.test(open0.links[0]) && /nasa\.gov/.test(open0.links[1]) && /isro\.gov\.in/.test(open0.links[2]), open0.links.join(' | '));
  // the case kept beside it: the Shackleton connecting ridge, Yes on 80 m and Not sure on 20 m
  await page.evaluate(() => { const s = document.getElementById('mSite'); s.value = '1'; s.dispatchEvent(new Event('change', { bubbles: true })); });
  await page.waitForFunction(() => /Not sure as planned/.test((document.getElementById('fineNote') || {}).textContent || ''), { timeout: 30000 }).catch(() => {});
  const old1 = await page.evaluate(() => ({ site: document.getElementById('mSite').options[document.getElementById('mSite').selectedIndex].textContent,
    word: (document.querySelector('#missionOut .vWord') || {}).textContent, fine: (document.getElementById('fineNote') || {}).textContent || '', agree: !!document.querySelector('#fineNote.agree') }));
  check('the old example stays on the page as the case where the two grids disagree', /Shackleton connecting ridge/.test(old1.site) && old1.word === 'Yes' && !old1.agree &&
    /^On the 20 m grid: Not sure as planned \(11 of 13 touchdown points\)/.test(old1.fine), old1.site + ' | ' + old1.word + ' | ' + old1.fine);
  await page.screenshot({ path: OUT + '/desktop_1280x800_grids_disagree.png' });
  await page.evaluate(() => { const s = document.getElementById('mSite'); s.value = '0'; s.dispatchEvent(new Event('change', { bubbles: true })); });
  await page.waitForFunction(() => /Both grids agree/.test((document.getElementById('fineNote') || {}).textContent || ''), { timeout: 30000 }).catch(() => {});
  await sleep(600);
  // click the first cell that is not a clear yes: the view is redrawn for that landing date
  const flipDay = await page.evaluate(() => { const c = Array.from(document.querySelectorAll('#vstrip .vc')); const i = c.findIndex((x) => !x.classList.contains('v-yes')); c[i].click(); return i; });
  await page.waitForFunction((d) => new RegExp('slip of ' + d + ' day').test((document.querySelector('#why .whyHead') || {}).textContent || ''), { timeout: 30000 }, flipDay).catch(() => {});
  const why1 = await page.evaluate(() => ({ head: (document.querySelector('#why .whyHead') || {}).textContent || '', sel: Array.from(document.querySelectorAll('#vstrip .vc')).findIndex((x) => x.classList.contains('sel')),
    plan: !!document.getElementById('whyPlan'), date: document.getElementById('start').value }));
  check('clicking a day of slip redraws the skyline view for that landing date without changing the plan', new RegExp('slip of ' + flipDay + ' day').test(why1.head) && why1.sel === flipDay && why1.plan && why1.date === c0.date, why1.head);
  await page.screenshot({ path: OUT + '/desktop_1280x800_why_flip.png' });
  await page.evaluate(() => document.querySelector('#vstrip .vc').click());
  await sleep(400);
  check('the slip grid (4 rows x 60 dates) is built, in its fold under "More tools"', first.rows === 4 && first.cells === 240, first.rows + ' rows, ' + first.cells + ' cells');
  // ---- pass 3: the Earth margin on the card, station contact, sites beside permanent shadow, the skyline chart, 3-D play
  await page.evaluate(() => window.scrollTo(0, 0));
  await page.waitForFunction(() => /Yes up to an Earth mask of [\d.]+°/.test((document.getElementById('earthLine') || {}).textContent || ''), { timeout: 60000 }).catch(() => {});
  const eln3 = await page.evaluate(() => (document.getElementById('earthLine') || {}).textContent || '');
  check('the card says how far the Earth clears the skyline and up to which mask the Yes holds, masks labelled illustrative',
    /[\d.]+° above the skyline at touchdown/.test(eln3) && /Yes up to an Earth mask of [\d.]+°/.test(eln3) && /masks illustrative/.test(eln3) && /DSN station/.test(eln3), eln3.slice(0, 220));
  const chart3 = await page.evaluate(() => {
    const svg = document.querySelector('#why svg.whySvg'); if (!svg) { return null; }
    const boxes = Array.from(svg.querySelectorAll('text')).map((t) => t.getBoundingClientRect()).filter((b) => b.width > 0);
    let overlaps = 0;
    for (let i = 0; i < boxes.length; i++) { for (let j = i + 1; j < boxes.length; j++) {
      const a = boxes[i], b = boxes[j];
      if (a.left < b.right - 1 && a.right > b.left + 1 && a.top < b.bottom - 1 && a.bottom > b.top + 1) { overlaps += 1; } } }
    return { h: Math.round(svg.getBoundingClientRect().height), labels: boxes.length, overlaps };
  });
  check('the skyline chart is at least 130 px tall and none of its labels overlap', chart3 && chart3.h >= 130 && chart3.overlaps === 0, JSON.stringify(chart3));
  await page.click('#contactGo');
  await page.waitForFunction(() => !!document.querySelector('#contact svg.contactCycle'), { timeout: 90000 }).catch(() => {});
  const stc = await page.evaluate(() => ({ text: ((document.querySelector('#contact p.note') || {}).textContent || ''), bars: document.querySelectorAll('#contact svg.contactCycle rect').length,
    hours: document.querySelectorAll('#contact svg.contactStrip rect').length, cap: ((document.querySelector('#contact p.cap') || {}).textContent || '') }));
  check('station contact: which Deep Space Network complex carries each hour, and the split over the 18.6-year cycle',
    /Goldstone carries \d+, Madrid \d+, Canberra \d+/.test(stc.text) && stc.bars >= 19 * 3 && stc.hours >= 100 && /810-005/.test(stc.cap) && /Horizons/.test(stc.cap), stc.text.slice(0, 200) + ' | ' + stc.bars + ' bars');
  await page.screenshot({ path: OUT + '/desktop_1280x800_stations.png' });
  await page.evaluate(() => window.scrollTo(0, 0));
  await page.click('#shadowGo');
  await page.waitForFunction(() => !!document.querySelector('#shadowTable'), { timeout: 150000 }).catch(() => {});
  const shd = await page.evaluate(() => ({ head: ((document.getElementById('shadowHead') || {}).textContent || ''), rows: document.querySelectorAll('#shadowTable tr').length - 1,
    adds: document.querySelectorAll('#shadowTable button.add').length, note: ((document.querySelector('#shadowSites p.note') || {}).textContent || '') }));
  check('slip-robust sites beside permanent shadow: a ranked list with Add buttons, and it says shadow is not ice',
    /\d+ map points survive a slip of a day or more beside permanent shadow/.test(shd.head) && shd.rows >= 1 && shd.adds === shd.rows && /not where ice is/.test(shd.note), shd.head + ' | ' + shd.rows + ' rows');
  await page.screenshot({ path: OUT + '/desktop_1280x800_shadow_sites.png' });
  // ---- deep pass: the next monthly launch windows and the real-missions panel
  await page.evaluate(() => window.scrollTo(0, 0));
  await page.waitForFunction(() => document.querySelectorAll('#winLine [data-win]').length >= 3, { timeout: 60000 }).catch(() => {});
  const win5 = await page.evaluate(() => ({ t: (document.getElementById('winLine') || {}).textContent || '', n: document.querySelectorAll('#winLine [data-win]').length }));
  check('the card says what the next monthly launch windows give (missed window: next landing a synodic month later)', /Missed the window\? Next/.test(win5.t) && win5.n === 3, win5.t.slice(0, 160));
  await page.click('#optGo');
  await page.waitForFunction(() => /Other options:|Every next window is Yes/.test((document.getElementById('winAlt') || {}).textContent || ''), { timeout: 600000 }).catch(() => {});
  const alt5 = await page.evaluate(() => (document.getElementById('winAlt') || {}).textContent || '');
  check('for each missed window: which need fails, the best landing hour here, and which other site is Yes',
    /✕ sunlight/.test(win5.t) && (/Other options:.*(no hour within 3 days here|here at ).*(✓ at .+, \d+ d.*\d+ of \d+ other sites have a Yes hour within 3 days|no other site has a Yes hour)/.test(alt5) && !/site \d ✓/.test(alt5) || /Every next window is Yes/.test(alt5)), alt5.slice(0, 200));
  await page.click('#realGo');
  await page.waitForFunction(() => document.querySelectorAll('#real table').length === 4, { timeout: 30000 }).catch(() => {});
  const real5 = await page.evaluate(() => ({ tables: document.querySelectorAll('#real table').length, rows: document.querySelectorAll('#real table tr').length,
    t: (document.getElementById('real') || {}).textContent || '' }));
  check('real missions: IM-1 (the window it missed and the one it flew) and VIPER (late 2027), with sources and assumptions labelled',
    real5.tables === 4 && real5.rows >= 9 && /January \(missed/.test(real5.t) && /February \(flown\)/.test(real5.t) && /late 2027/.test(real5.t) && /Assumptions, labelled/.test(real5.t), real5.rows + ' rows');
  await page.screenshot({ path: OUT + '/desktop_1280x800_real_missions.png' });
  const art6 = await page.evaluate(() => ({ t: (document.getElementById('real') || {}).textContent || '', cells: document.querySelectorAll('#real table.artT td.v-yes, #real table.artT td.v-no').length }));
  check('Artemis III regions in each missed window, each region the published candidate landing sites (not NASA sites)',
    /Artemis III candidate regions in each window/.test(art6.t) && /set of published candidate landing sites of Wueller et al\. 2026/.test(art6.t) && /not NASA’s own sites/.test(art6.t) && art6.cells === 54, art6.cells + ' cells');
  /* feature build: the separate "how many regions must stay open" panel */
  await page.$eval('#regionsGo', (e) => e.scrollIntoView());
  await page.click('#regionsGo');
  await page.waitForSelector('#regCanvas', { timeout: 60000 }).catch(() => {});
  const reg7 = await page.evaluate(() => {
    const c = document.getElementById('regCanvas'), t = (document.getElementById('regions') || {}).textContent || '';
    let lit = 0;
    if (c) { const d = c.getContext('2d').getImageData(0, 0, c.width, c.height).data; for (let i = 0; i < d.length; i += 4) { if (d[i + 1] > 120 && d[i] < 150 && d[i + 2] < 150) { lit++; } } }
    return { lit, rows: document.querySelectorAll('#regions table.regT tr').length, t };
  });
  check('regions panel: calendar drawn, coverage for 1 to 9 regions added one at a time, cross-check and citation shown',
    reg7.lit > 1000 && reg7.rows >= 10 && /added one at a time/.test(reg7.t) && /not real launch opportunities/.test(reg7.t) && /illustrative figure/.test(reg7.t) && /Wueller/.test(reg7.t) && /10\.1029\/2025JE009434/.test(reg7.t) && /Cross-check against the paper/.test(reg7.t) && /never as open/.test(reg7.t),
    reg7.lit + ' green px, ' + reg7.rows + ' table rows');
  await page.screenshot({ path: OUT + '/desktop_1280x800_regions.png' });
  await page.evaluate(() => window.scrollTo(0, 0));

  // ---- pass 4: ride-through hours across slip days, the link-margin note, the night layer
  await page.evaluate(() => window.scrollTo(0, 0));
  await page.waitForFunction(() => /Ride-through: slip \d+ days? and the longest night the lander meets (grows|shrinks|stays)/.test((document.getElementById('survLine') || {}).textContent || ''), { timeout: 60000 }).catch(() => {});
  const surv4 = await page.evaluate(() => ({ t: (document.querySelector('#survLine') || {}).textContent || '', bars: document.querySelectorAll('#survChartBox svg.survChart rect.survNight').length,
    note: (document.querySelector('#earthLine .linkNote') || {}).textContent || '' }));
  check('the card says how the whole night and Earth outage the lander meets change with the slip, with a chart for every slip day',
    /Ride-through: slip \d+ days? and the longest night the lander meets (grows from \d+ to |shrinks from \d+ to |stays at )(at least )?\d+ hours/.test(surv4.t) && /longest Earth outage (grows from \d+ to |shrinks from \d+ to |stays at )(at least )?\d+ h \(whole runs, to their end\)/.test(surv4.t) && surv4.bars >= 20, surv4.t.slice(0, 220));
  check('the card says a real link would want more than the Yes holds for, with a cited source', /A real link would want more than [\d.]+°/.test(surv4.note) && /JPL IPN 42-243/.test(surv4.note), surv4.note);
  /* follow-up: the night map layer was withdrawn (one colour: 556 of 574 points 12 days or more); the card says why */
  const night4 = await page.evaluate(() => ({ opt: !!document.querySelector('#mapLayer option[value=night]'), cap: (document.querySelector('#survChartBox p.cap') || {}).textContent || '' }));
  check('the night map layer is withdrawn, and the card says why (it would be one colour)', !night4.opt && /No map of these hours is drawn/.test(night4.cap), night4.cap.slice(-160));
  await page.select('#mapLayer', 'margin');
  await page.evaluate(() => window.scrollTo(0, 0));
  const v3p = await page.$('#view3dPanel .v3dPlay');
  if (v3p) {
    await page.evaluate(() => document.getElementById('view3dPanel').scrollIntoView());
    const v3t0 = await page.$eval('#view3dPanel .v3dWhen', (o) => o.textContent);
    await v3p.click(); await sleep(4500);
    const v3t1 = await page.$eval('#view3dPanel .v3dWhen', (o) => o.textContent);
    /* pass 4: while it plays, the time shown is the time of the frame drawn (the words under it say which) */
    const v3pair = [];
    for (let k = 0; k < 6; k++) {
      v3pair.push(await page.evaluate(() => [document.querySelector('#view3dPanel .v3dWhen').textContent.split(' (')[0],
        document.querySelector('#view3dPanel .v3dState').textContent.split('. ')[0]]));
      await sleep(350);
    }
    await v3p.click();
    check('while the 3-D view plays, its time label is the time of the frame shown', v3pair.filter((x) => x[0] === x[1]).length >= 5, JSON.stringify(v3pair.slice(0, 3)));
    check('the 3-D view plays: the time (and with it the Sun and the shadow) moves', v3t0 !== v3t1, v3t0 + ' -> ' + v3t1);
  } else { check('the 3-D view plays: the time (and with it the Sun and the shadow) moves', false, 'no play button'); }

  await page.evaluate(() => window.scrollTo(0, 0));
  check('default measure is total usable hours, not the unbroken run', first.metric === 'total', first.metric);
  check('each terrain row has a landing-scatter strip and a verdict', first.spread === 4 && first.verdicts.length === 4 && first.verdicts.every((v) => /Yes|No|Not sure/.test(v)), first.verdicts.join(' ; '));
  console.log('badge: ' + first.badge);
  const tags = await page.evaluate(() => ({
    slip: Array.from(document.querySelectorAll('#slip .slabel.pick .mtag')).map((x) => x.textContent),
    tileTags: document.querySelectorAll('.card .tile .mtag').length, tilesN: document.querySelectorAll('.card .tile').length }));
  check('every slip row is tagged terrain(...) or smooth sphere', tags.slip.length === 4 && tags.slip.every((t) => /^terrain \(|^smooth sphere/.test(t)), tags.slip.join(' ; '));
  check('every tile carries a provenance tag', tags.tilesN > 0 && tags.tileTags === tags.tilesN, tags.tileTags + ' of ' + tags.tilesN);

  // hover a slip cell: the tooltip gives the range within the scatter and the verdict
  // (the rows start just under the first 800 px since the landing circles joined the card, so bring them into view)
  await page.evaluate(() => { document.getElementById('h-slip').scrollIntoView(); window.scrollBy(0, -10); });
  await sleep(200);
  const cellBox = await page.$eval('#slip .srow:nth-child(2) button.cell:nth-child(9)', (b) => { const r = b.getBoundingClientRect(); return { x: r.left + r.width / 2, y: r.top + r.height / 2 }; });
  await page.mouse.move(cellBox.x, cellBox.y); await sleep(200);
  const tip = await page.$eval('#tip', (t) => t.hidden ? '' : t.innerText.replace(/\n+/g, ' | '));
  check('slip-cell tooltip shows hours, the scatter range and the verdict', /Sunlit: \d+ h/.test(tip) && /Meets the need: /.test(tip) && /smooth sphere/.test(tip), tip.slice(0, 260));
  await page.screenshot({ path: OUT + '/desktop_slip_tooltip.png' });
  await page.mouse.move(5, 5);
  await page.evaluate(() => window.scrollTo(0, 0));

  // sites panel: the slip-margin map
  await page.evaluate(() => document.getElementById('h-sites').scrollIntoView());
  await page.waitForFunction(() => !!document.querySelector('#polar image.overlay'), { timeout: 60000 }).catch(() => {});
  await sleep(300);
  await page.screenshot({ path: OUT + '/desktop_1280x800_sites.png' });
  const mapInfo = await page.evaluate(() => ({ overlay: !!document.querySelector('#polar image.overlay'), zoom: document.getElementById('mapZoom').value,
    layer: document.getElementById('mapLayer').value, legend: document.getElementById('mapLegend').innerText.replace(/\n+/g, ' '),
    layers: document.getElementById('mapLayer').options.length, note: document.getElementById('mapNote').textContent }));
  check('first visit shows the slip-margin map of the pole', mapInfo.overlay && mapInfo.zoom === 'pole' && mapInfo.layer === 'margin', mapInfo.legend);
  check('the map says what it is made from', /one terrain skyline every 500 m/.test(mapInfo.note) && /LOLA, 80 m\/px/.test(mapInfo.note), mapInfo.layers + ' layer choices');
  // pass 2: every coloured map point re-checked at 13 touchdown points, coloured by the margin that survives
  await page.waitForFunction(() => !!document.getElementById('robustSum'), { timeout: 120000 }).catch(() => {});
  const rmap = await page.evaluate(() => ({ sum: (document.getElementById('robustSum') || {}).textContent || '', swatches: document.querySelectorAll('#mapLegend .lsw').length,
    crisp: !!document.querySelector('#polar image.overlay.crisp'), note: document.getElementById('mapNote').textContent }));
  const mm = /(\d+) of the (\d+) map points .* keep a slip margin at all 13 touchdown points; (\d+) lose it/.exec(rmap.sum) || [];
  check('the slip-margin map is re-checked with the landing scatter and says how many points lose their margin', mm.length === 4 && parseInt(mm[1], 10) + parseInt(mm[3], 10) === parseInt(mm[2], 10) &&
    rmap.swatches >= 6 && rmap.crisp && /13 touchdown points/.test(rmap.note), rmap.sum);
  await page.evaluate(() => { document.getElementById('polar').scrollIntoView(); window.scrollBy(0, -50); });
  await sleep(300);
  await page.screenshot({ path: OUT + '/desktop_1280x800_map_scatter.png' });
  await page.evaluate(() => document.getElementById('mapPsr').click());
  await page.waitForFunction(() => !!document.querySelector('#polar image.psr'), { timeout: 20000 }).catch(() => {});
  const psr = await page.evaluate(() => ({ img: !!document.querySelector('#polar image.psr'), legend: document.getElementById('mapLegend').textContent, note: document.getElementById('mapNote').textContent }));
  check('permanent shadow can be marked on the map, labelled as derived from the LOLA illumination map', psr.img && /permanent shadow/.test(psr.legend) && /DERIVED/.test(psr.note), psr.legend.slice(-90));
  await page.screenshot({ path: OUT + '/desktop_1280x800_map_shadow.png' });
  await page.evaluate(() => document.getElementById('mapPsr').click());
  await page.evaluate(() => document.getElementById('mapScatter').click());
  await sleep(500);
  const single = await page.evaluate(() => ({ legend: document.getElementById('mapLegend').textContent, crisp: !!document.querySelector('#polar image.overlay.crisp') }));
  check('the single-point map is still there with the scatter check switched off, and says it has no scatter', !single.crisp && /% of the mapped points are coloured/.test(single.legend) && /no landing scatter/.test(single.legend), single.legend);
  await page.evaluate(() => document.getElementById('mapScatter').click());
  await sleep(500);
  // pass 2: the 3-D view of the real grid, and the lunar against terrestrial comparison
  await page.evaluate(() => { document.getElementById('view3dPanel').scrollIntoView(); window.scrollBy(0, -10); });
  await page.waitForFunction(() => { const c = document.querySelector('#view3d canvas'); return !!c && c.width > 100; }, { timeout: 60000 }).catch(() => {});
  await sleep(1500);
  const v3 = await page.evaluate(() => {
    const c = document.querySelector('#view3d canvas'); let painted = 0, tones = 0;
    if (c) { const d = c.getContext('2d').getImageData(0, 0, c.width, c.height).data, seen = {}; for (let i = 0; i < d.length; i += 4 * 97) { if (d[i + 3] > 0) { painted += 1; } seen[(d[i] >> 4) + ',' + (d[i + 1] >> 4) + ',' + (d[i + 2] >> 4)] = 1; } tones = Object.keys(seen).length; }
    return { hidden: document.getElementById('view3dPanel').hidden, canvas: !!c, painted, tones, text: document.getElementById('view3d').innerText.replace(/\n+/g, ' ') };
  });
  check('3-D view of the real LOLA grid with the Sun, the Earth and the shadow, labelled', !v3.hidden && v3.canvas && v3.painted > 500 && v3.tones > 12 && /LOLA/.test(v3.text) && /true scale|exaggerat/i.test(v3.text) &&
    /Sun/.test(v3.text) && /Earth/.test(v3.text) && /shadow/i.test(v3.text), v3.tones + ' tones; ' + v3.text.slice(0, 160));
  await page.screenshot({ path: OUT + '/desktop_1280x800_3d.png' });
  await page.evaluate(() => { document.getElementById('contrastPanel').scrollIntoView(); window.scrollBy(0, -10); });
  await page.waitForFunction(() => !!document.querySelector('#contrast svg, #contrast canvas'), { timeout: 30000 }).catch(() => {});
  await sleep(500);
  const ct = await page.evaluate(() => ({ hidden: document.getElementById('contrastPanel').hidden, chart: !!document.querySelector('#contrast svg, #contrast canvas'), text: document.getElementById('contrast').innerText.replace(/\n+/g, ' ') }));
  check('lunar against terrestrial conditions for the same days, with the Earth curves labelled as a formula', !ct.hidden && ct.chart && /Earth/.test(ct.text) && /(formula|computed)/i.test(ct.text), ct.text.slice(0, 200));
  await page.screenshot({ path: OUT + '/desktop_1280x800_contrast.png' });
  await page.evaluate(() => document.getElementById('h-sites').scrollIntoView());
  await sleep(300);
  const mbox = await page.$eval('#polar svg', (s) => { const r = s.getBoundingClientRect(); return { x: r.left, y: r.top, w: r.width, h: r.height }; });
  await page.mouse.move(mbox.x + mbox.w * 0.62, mbox.y + mbox.h * 0.42); await sleep(200);
  const mtip = await page.$eval('#tip', (t) => t.hidden ? '' : t.innerText.replace(/\n+/g, ' | '));
  check('map tooltip gives the numbers of the point under the cursor', /Good landing dates: \d+ of 60/.test(mtip) && /Sunlit hours: worst date/.test(mtip), mtip.slice(0, 200));
  await page.mouse.move(5, 5);
  // the slip-robust site list: the best map points re-checked with the landing scatter (first-visit plan)
  await page.evaluate(() => document.getElementById('robustBtn').click());
  await page.waitForFunction(() => !!document.querySelector('#robust h3, #robust .note'), { timeout: 300000 }).catch(() => {});
  const rob = await page.evaluate(() => ({ head: (document.querySelector('#robust h3') || {}).textContent || '', rows: document.querySelectorAll('#robust table tr').length - 1,
    first: (document.querySelector('#robust table tr:nth-child(2)') || {}).innerText || '' }));
  check('slip-robust site list: the best map points re-checked with the scatter', /\d+ of the \d+ best map points stay a clear yes/.test(rob.head) && rob.rows >= 1 && /Yes|Not sure|No/.test(rob.first),
    rob.head + ' | ' + rob.first.replace(/\s+/g, ' ').slice(0, 140));
  await page.evaluate(() => { document.getElementById('robust').scrollIntoView(); window.scrollBy(0, -10); });
  await sleep(300);
  await page.screenshot({ path: OUT + '/desktop_1280x800_robust_sites.png' });

  // compare panel
  await page.evaluate(() => document.getElementById('h-compare').scrollIntoView());
  await sleep(400);
  await page.screenshot({ path: OUT + '/desktop_1280x800_compare.png' });
  const cmp = await page.evaluate(() => ({ sky: document.querySelectorAll('svg.skyline').length, year: document.querySelectorAll('.year table').length,
    cols: document.querySelectorAll('.card:first-child .year table tr:first-child th').length, rng: document.querySelectorAll('.card:first-child .year .rng').length,
    cap: (document.querySelector('.card:first-child .year .cap') || {}).textContent, pairs: document.querySelectorAll('#pairs table tr').length - 1 }));
  check('a skyline strip and a year table per terrain site', cmp.sky === 4 && cmp.year === 4, JSON.stringify({ sky: cmp.sky, year: cmp.year }));
  check('year table is a resolution ladder (80 m, 240 m, 474 m, 1.9 km, sphere) with ranges', cmp.cols === 6 && cmp.rng >= 3, cmp.cols - 1 + ' columns, ' + cmp.rng + ' ranges');
  check('longest darkness carries its caveat on the ridge site', /Longest darkness is the least reliable figure/.test(cmp.cap || ''), (cmp.cap || '').slice(0, 200));
  check('site pairs table (6 pairs of 4 sites)', cmp.pairs === 6, cmp.pairs + ' rows');
  await page.evaluate(() => document.getElementById('pairs').scrollIntoView());
  await sleep(200);
  await page.screenshot({ path: OUT + '/desktop_1280x800_pairs.png' });

  // validation panel
  await page.evaluate(() => document.getElementById('h-valid').scrollIntoView());
  await sleep(300);
  await page.screenshot({ path: OUT + '/desktop_1280x800_valid.png' });
  const vt = await page.$$eval('#validTiles .tile', (n) => n.map((x) => x.innerText.replace(/\n+/g, ' | ')));
  check('a validation tile shows the default example on the 20 m grid beside the 80 m answer', vt.some((t) => /20 m grid/.test(t) && /checked separately/.test(t) && /\d+ of 13/.test(t) && /on 80 m/.test(t) && /not what the page serves/.test(t)),
    (vt.filter((t) => /20 m grid/.test(t))[0] || '').slice(0, 220));
  check('validation tiles: ordinary terrain, ridge pixels, C1 with its range, Earth check status', vt.length >= 5 && /ordinary terrain/.test(vt[0]) && /ridge pixels/.test(vt[1]) &&
    vt.some((t) => /not firm/.test(t)) && vt.some((t) => /Earth-visibility/.test(t)), vt.map((t) => t.slice(0, 60)).join(' || '));
  const pending = vt.filter((t) => /needs official data download/.test(t)).length;
  console.log('Earth check tile: ' + (pending ? 'labelled "needs official data download"' : 'run against the reference maps'));

  // scrub and play
  await page.evaluate(() => { const s = document.getElementById('scrub'); s.value = 700; s.dispatchEvent(new Event('input', { bubbles: true })); });
  await sleep(900);
  console.log('scrub label at 700 h: ' + await page.$eval('#scrubLabel', (n) => n.textContent));
  const before = await page.$$eval('.card .tiles .tile:nth-child(5) .v', (n) => n.map((x) => x.textContent));
  await page.click('#play'); await sleep(2600);
  const during = await page.$$eval('.card .tiles .tile:nth-child(5) .v', (n) => n.map((x) => x.textContent));
  await page.click('#play'); await sleep(700);
  check('window tiles refresh while Play is running', JSON.stringify(before) !== JSON.stringify(during), before.join(',') + ' -> ' + during.join(','));
  const lbl0 = await page.$eval('#scrubLabel', (n) => n.textContent);
  await page.evaluate(() => document.querySelectorAll('#slip button.cell')[20].click());
  await sleep(600);
  const lbl1 = await page.$eval('#scrubLabel', (n) => n.textContent);
  check('clicking a slip cell moves the scrubber', lbl0 !== lbl1, lbl0 + ' -> ' + lbl1);

  // the card reacts: a next-good-date button, an impossible need, a real mission, and the link
  await page.evaluate(() => window.scrollTo(0, 0));
  const wanted = c0.next[0];
  await page.evaluate(() => document.querySelector('#missionOut [data-plan]').click());
  await idle(page); await sleep(400);
  const c1 = await card(page);
  check('a next-good-date button re-plans for that date', c1.date !== c0.date && c1.word === 'Yes', wanted + ' -> ' + c1.date + ': ' + c1.word + ', ' + c1.sub);
  await setVal(page, 'needSun', '400');
  const c2 = await card(page);
  check('asking for more sunlight than the window holds gives a plain No with the reason', c2.word === 'No' && /only \d+ sunlit hours of the 400 needed/.test(c2.text), c2.text.slice(0, 160));
  await page.evaluate(() => document.querySelector('[data-replay=im2]').click());
  await idle(page); await sleep(500);
  const c3 = await card(page);
  check('real-landing replay: IM-2 Athena, 6 Mar 2025 17:00 UTC', c3.date === '2025-03-06' && c3.hour === '17' && c3.word === 'Yes' && /2 days/.test(c3.sub), c3.word + ', ' + c3.sub + ' | ' + c3.sure);
  await page.screenshot({ path: OUT + '/desktop_1280x800_replay_im2.png' });
  check('the address carries the scenario', /d=2025-03-06/.test(c3.hash) && /h=17/.test(c3.hash) && /s=[a-z0-9_,]*im2/.test(c3.hash) && /sun=240/.test(c3.hash), c3.hash);
  const shared = await open(1280, 800, false, 'light', URL.replace(/\/$/, '') + '/' + c3.hash);
  const c4 = await card(shared.page);
  const onCard = await shared.page.$eval('#mSite', (e) => e.options[e.selectedIndex].textContent);
  check('opening that link in a new tab reproduces the scenario', c4.date === c3.date && c4.hour === c3.hour && c4.word === c3.word && c4.sub === c3.sub && /^IM-2/.test(onCard), c4.word + ', ' + c4.sub + ' | card site: ' + onCard);
  await shared.page.close();
  // IM-1 with its own need (about seven days of surface operations): a landing that happened must not read "No"
  await page.evaluate(() => document.querySelector('[data-replay=im1]').click());
  await idle(page); await sleep(500);
  const c5 = await card(page);
  const im1 = await page.evaluate(() => ({ sun: document.getElementById('needSun').value, note: (document.querySelector('#missionOut .replayCap') || {}).textContent || '' }));
  check('real-landing replay: IM-1 Odysseus with its own need is not a No', c5.date === '2024-02-22' && c5.hour === '23' && im1.sun === '168' && c5.word !== 'No' &&
    /seven days/.test(im1.note) && /10 days/.test(im1.note) && /illustrative/.test(im1.note), c5.word + ', ' + c5.sub + ' | need ' + im1.sun + ' h | ' + im1.note.slice(0, 120));
  await page.screenshot({ path: OUT + '/desktop_1280x800_replay_im1.png' });
  await page.evaluate(() => document.querySelector('[data-replay=im2]').click());
  await idle(page); await sleep(400);

  // clearing the date must not throw
  const errsBefore = log.filter((l) => l.startsWith('pageerror')).length;
  await page.evaluate(() => { const s = document.getElementById('start'); s.value = ''; s.dispatchEvent(new Event('change', { bubbles: true })); });
  await sleep(400);
  const cleared = await page.evaluate(() => ({ msg: document.getElementById('siteMsg').textContent, cells: document.querySelectorAll('#slip button.cell').length }));
  check('clearing the date throws nothing and explains itself', log.filter((l) => l.startsWith('pageerror')).length === errsBefore && /Choose a landing date/.test(cleared.msg), cleared.msg + ' | cells kept: ' + cleared.cells);
  await setVal(page, 'start', '2027-04-20');
  const recovered = await page.evaluate(() => document.querySelectorAll('#slip button.cell').length);
  check('setting a date again recovers', recovered === 240, recovered + ' cells');

  // 10 m mast, map click, other map layers
  await page.select('#mast', '10');
  await page.waitForFunction(() => /observer 10 m/.test((document.querySelector('.card .coords .small') || {}).textContent || ''), { timeout: 20000 }).catch(() => {});
  const tag10 = await page.$$eval('.card .coords .small', (n) => n.map((x) => x.textContent)[0]);
  check('height above ground switches to 10 m', /observer 10 m/.test(tag10), tag10);
  await page.select('#mast', '2'); await idle(page);
  await page.evaluate(() => { document.querySelectorAll('.chip button')[3].click(); });
  await idle(page);
  await page.evaluate(() => document.getElementById('h-sites').scrollIntoView());
  await page.waitForFunction(() => !!document.querySelector('#polar image.overlay'), { timeout: 60000 }).catch(() => {});
  const box2 = await page.$eval('#polar svg', (s) => { const r = s.getBoundingClientRect(); return { x: r.left, y: r.top, w: r.width, h: r.height }; });
  await page.mouse.click(box2.x + box2.w * 0.62, box2.y + box2.h * 0.42);
  await idle(page); await sleep(500);
  const picked = await page.evaluate(() => Array.from(document.querySelectorAll('.chip')).map((c) => c.textContent.replace('×', '').trim()));
  check('clicking the map adds a site there', picked.length === 4 && /Map pick/.test(picked[3]), picked[3]);
  for (const lay of ['good', 'worst_sun', 'avgvis']) {
    if (await page.$('#mapLayer option[value=' + lay + ']')) {
      await page.select('#mapLayer', lay); await idle(page); await sleep(400);
      await page.screenshot({ path: OUT + '/desktop_1280x800_map_' + lay + '.png' });
    }
  }
  await page.select('#mapZoom', ''); await idle(page); await sleep(400);
  const wide = await page.$eval('#mapNote', (n) => n.textContent);
  check('the map zooms out to 80 S', /608 km across/.test(wide), wide.slice(0, 80));
  await page.screenshot({ path: OUT + '/desktop_1280x800_map_wide.png' });

  // CSV export goes out with labels
  const csv = await page.evaluate(async () => {
    const r = await fetch('/api/export/slipgrid.csv', { method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ sites: [{ id: 'shackleton' }], start: '2027-01-01', n_dates: 5, window_days: 7, scatter_m: 100 }) });
    return { status: r.status, type: r.headers.get('content-type'), head: (await r.text()).split('\n').filter((l) => l.charAt(0) !== '#').slice(0, 2).join('\n') };
  });
  check('slip grid CSV export with the scatter band', csv.status === 200 && /text\/csv/.test(csv.type) && /horizon_model/.test(csv.head) && /usable_hours_min_in_scatter/.test(csv.head), csv.type);
  await page.close();

  // ---- dark theme
  ({ page } = await open(1280, 800, false, 'dark'));
  await page.screenshot({ path: OUT + '/desktop_dark_1280x800_top.png' });
  await page.close();

  // ---- phone 390x844
  ({ page, ms } = await open(390, 844, true, 'light'));
  console.log('phone load to network idle: ' + ms + ' ms');
  await page.screenshot({ path: OUT + '/phone_390x844_top.png' });
  const ph = await page.evaluate(() => {
    const vw = window.innerWidth;
    const cells = Array.from(document.querySelectorAll('#slip .srow:nth-child(2) button.cell')).map((c) => c.getBoundingClientRect());
    const best = document.querySelector('#slip .srow:nth-child(2) > .sbest:not(.sub)').getBoundingClientRect();
    const v = document.querySelector('#missionOut .verdict').getBoundingClientRect();
    const vc = Array.from(document.querySelectorAll('#vstrip .vc')).map((c) => c.getBoundingClientRect());
    const wideTables = Array.from(document.querySelectorAll('table')).filter((t) => { const w = t.parentElement; return t.scrollWidth > w.clientWidth + 1 && getComputedStyle(w).overflowX !== 'auto'; }).length;
    return { vw, n: cells.length, visible: cells.filter((r) => r.left >= 0 && r.right <= vw + 0.5).length,
      minW: Math.min.apply(null, cells.map((r) => r.width)), bestRight: best.right, bestLeft: best.left, verdictBottom: Math.round(v.bottom),
      vcVisible: vc.filter((r) => r.left >= 0 && r.right <= vw + 0.5).length, wideTables,
      vcMinW: Math.min.apply(null, vc.map((r) => r.width)), vcN: vc.length, stripScrolls: (function () { const st = document.getElementById('vstrip'); return st.scrollWidth > st.clientWidth + 1 && getComputedStyle(st).overflowX === 'auto'; }()),
      pageW: document.documentElement.scrollWidth,
      axisFont: parseFloat(getComputedStyle(document.querySelector('.card svg text')).fontSize) *
        (document.querySelector('.card svg').getBoundingClientRect().width / document.querySelector('.card svg').viewBox.baseVal.width) };
  });
  check('phone: the verdict is on the first screen', ph.verdictBottom < 844, 'bottom ' + ph.verdictBottom + ' px');
  /* UX pass: on a phone the card's 60 days are 24 px targets in a strip that scrolls sideways (the page itself does not) */
  check('phone: the card has 60 day cells of at least 24 px in a scrolling strip, and a grid row shows all 60 days', ph.vcN === 60 && ph.vcMinW >= 23.5 && ph.stripScrolls && ph.pageW <= ph.vw + 1 && ph.n === 60 && ph.visible === 60,
    ph.vcN + ' card cells, narrowest ' + (ph.vcMinW || 0).toFixed(1) + ' px, strip scrolls: ' + ph.stripScrolls + '; grid ' + ph.visible + ' of 60 visible');
  check('phone: the verdict column of the grid is on screen', ph.bestLeft >= 0 && ph.bestRight <= ph.vw + 0.5, Math.round(ph.bestLeft) + '..' + Math.round(ph.bestRight));
  check('phone: no horizontal page overflow', ph.pageW <= ph.vw + 1, ph.pageW + ' vs ' + ph.vw);
  check('phone: every wide table sits in a sideways-scrolling box', ph.wideTables === 0, ph.wideTables + ' tables overflow without a scroll box');
  check('phone: chart axis text is at least 9.5 px', ph.axisFont >= 9.5, ph.axisFont.toFixed(1) + ' px');
  const phw = await page.evaluate(() => { const r = (sel) => { const e = document.querySelector(sel); return e ? e.getBoundingClientRect() : null; };
    const w = r('#why svg'), c = r('#view3d canvas'), t = document.querySelector('#why svg text');
    return { why: w ? [Math.round(w.left), Math.round(w.right)] : null, v3: c ? [Math.round(c.left), Math.round(c.right)] : null,
      font: t && w ? parseFloat(getComputedStyle(t).fontSize) * (w.width / document.querySelector('#why svg').viewBox.baseVal.width) : 0, docH: document.documentElement.scrollHeight }; });
  check('phone: the skyline view and the 3-D view fit the screen width', phw.why && phw.why[0] >= 0 && phw.why[1] <= 391 && phw.v3 && phw.v3[0] >= 0 && phw.v3[1] <= 391 && phw.font >= 9.5,
    JSON.stringify(phw.why) + ' ' + JSON.stringify(phw.v3) + ', skyline axis text ' + phw.font.toFixed(1) + ' px');
  console.log('phone page height: ' + phw.docH + ' px');
  for (const [id, name] of [['h-slip', 'grid'], ['h-sites', 'sites'], ['h-compare', 'compare'], ['h-valid', 'valid']]) {
    await page.evaluate((i) => document.getElementById(i).scrollIntoView(), id);
    await sleep(300);
    await page.screenshot({ path: OUT + '/phone_390x844_' + name + '.png' });
  }
  // once more after every panel has drawn (a validation tile that arrives late once pushed the page to 461 px)
  const late = await page.evaluate(() => ({ w: document.documentElement.scrollWidth, vw: window.innerWidth, tiles: document.querySelectorAll('#validTiles .tile').length }));
  check('phone: no horizontal page overflow after every panel has loaded', late.w <= 391 && late.vw <= 391 && late.tiles >= 6, late.w + ' px wide, ' + late.tiles + ' validation tiles');
  await page.close();

  const bad = log.filter((l) => !/favicon/.test(l));
  check('no console errors, page errors or failed requests', bad.length === 0, bad.slice(0, 5).join(' || '));
  await browser.close();
  console.log(failures === 0 ? 'ALL UI CHECKS PASSED' : failures + ' UI CHECK(S) FAILED');
  process.exit(failures ? 1 : 0);
})().catch((e) => { console.error(e); process.exit(2); });
