/* Slipday add-on: "Be the mission planner", a five-scenario campaign for students (ages 12 and up) and anyone curious.

   Include with one script tag and one container:
     <div id="addon-game"></div>
     <script src="/static/addons/planner_game.js"></script>

   Each scenario is a briefing: what the mission needs, the original plan, and how many days the launch slipped.  The
   player inspects three or four options (stay, switch site, change the landing hour, wait for the next monthly window),
   each with real data from the server, then commits to one.  The real outcome is then shown with its reason, a 14-day
   timeline of the Sun and the Earth, and the best of the offered options.  Scenario settings (site, date, slip) are
   fixed; every number shown comes from the server (/api/mission, /api/why, /api/windows, /api/replays, /api/sites and
   the safety, safe-touchdown and relay add-on endpoints).  Scores live only in this browser.
*/
(function () {
  'use strict';

  /* ---------- shared tap: what the page itself asked the server for (same block as in listen.js) ---------- */
  if (!window.SlipdayAddonTap) {
    window.SlipdayAddonTap = (function () {
      var tap = { why: null, whyBody: null, missions: [], listeners: [] };
      var DEFAULT = {
        site: { id: 'robust_pick' }, landing: '2026-11-18T00:00:00Z', scatter_m: 100, slip_days: 60,
        need_sun_h: 240, need_earth_h: 100, window_days: 14, sun_at_touchdown: true, earth_at_touchdown: true,
        mask_deg: 0, min_sun_el: -90, min_earth_el: -90, terrain: true, mast_m: 2, min_sun_fraction: 0.5,
        earth_margin_deg: 0, earth_stations: true
      };
      function same(a, b) { return JSON.stringify(a) === JSON.stringify(b); }
      function rest(body) {
        var o = {};
        Object.keys(body).forEach(function (k) { if (k !== 'site' && k !== 'day' && k !== 'alternatives') { o[k] = body[k]; } });
        return o;
      }
      var seq = 0;
      function record(path, body, json, n) {
        if (path === '/api/why') { tap.whyBody = body; tap.why = json; }
        else {
          tap.missions = tap.missions.filter(function (m) { return !same(m.body.site, body.site); });
          tap.missions.push({ body: body, resp: json, n: n });
          tap.missions.sort(function (a, b) { return a.n - b.n; });     /* the order the page asked in */
        }
        tap.listeners.forEach(function (fn) { try { fn(path); } catch (e) { /* a listener's error is its own */ } });
      }
      if (window.fetch) {
        var orig = window.fetch.bind(window);
        window.fetch = function (input, init) {
          var p = orig(input, init);
          try {
            var url = typeof input === 'string' ? input : (input && input.url) || '';
            var path = url.replace(/^[a-z]+:\/\/[^/]+/i, '').split('?')[0];
            var mine = init && init.headers && init.headers['X-Slipday-Addon'];
            if ((path === '/api/why' || path === '/api/mission') && init && typeof init.body === 'string' && !mine) {
              var body = JSON.parse(init.body), n = seq++;
              p.then(function (r) {
                if (r.ok) { r.clone().json().then(function (j) { record(path, body, j, n); }).catch(function () {}); }
              }).catch(function () {});
            }
          } catch (e) { /* never get in the page's way */ }
          return p;
        };
      }
      return {
        /* The plan on the main card: the site the card shows, its landing, need and rules.  Before the page has
           asked for anything (or on a page without the app) it is the page's opening example. */
        plan: function () {
          var b = tap.whyBody;
          if (!b && tap.missions.length) {
            /* the page has not asked for the skyline view yet: take the card the page shows (its site menu) */
            var sel = document.getElementById('mSite'), shown = sel && sel.selectedIndex >= 0 ? sel.options[sel.selectedIndex].textContent : null;
            var hit = tap.missions.filter(function (m) { return shown && m.resp.site && m.resp.site.name === shown; })[0];
            b = (hit || tap.missions[0]).body;
          }
          if (!b) { var d = JSON.parse(JSON.stringify(DEFAULT)); d.day = 0; return d; }
          var out = JSON.parse(JSON.stringify(b));
          if (out.day === undefined) { out.day = 0; }
          delete out.alternatives;
          return out;
        },
        lastWhy: function () { return tap.why ? { body: tap.whyBody, resp: tap.why } : null; },
        /* the other sites the page has on its card list, for the same landing and rules as the plan */
        pageSites: function () {
          var p = this.plan(), r = rest(p); delete r.slip_days;
          return tap.missions.filter(function (m) {
            var mr = rest(m.body); delete mr.slip_days; return same(mr, r);
          }).map(function (m) { return { ref: m.body.site, name: m.resp.site && m.resp.site.name }; });
        },
        onChange: function (fn) { tap.listeners.push(fn); },
        api: function (path, body) {
          var opt = body ? { method: 'POST', headers: { 'Content-Type': 'application/json', 'X-Slipday-Addon': '1' }, body: JSON.stringify(body) }
            : { headers: { 'X-Slipday-Addon': '1' } };
          return fetch(path, opt).then(function (r) {
            return r.json().then(function (j) {
              if (!r.ok) { throw new Error(typeof j.detail === 'string' ? j.detail : 'The server could not answer (' + r.status + ').'); }
              return j;
            });
          });
        }
      };
    })();
  }
  var TAP = window.SlipdayAddonTap;

  var $ = function (id) { return document.getElementById(id); };
  var MON = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
  var WORD = { yes: 'Yes', 'not sure': 'Not sure', no: 'No', 'n/a': 'Not worked out' };
  var ICON = { yes: '✓', 'not sure': '?', no: '✕', 'n/a': '–' };
  var POINTS = { yes: 100, 'not sure': 40, no: 0, 'n/a': 0 };
  var SCRIPT_SRC = document.currentScript && document.currentScript.src;
  var BEST_KEY = 'slipday.planner.campaign.best';

  /* The campaign.  Only the settings are fixed here (site, planned landing, slip, the options offered); every number
     the player sees is asked from the server at play time.  The options were chosen so that each scenario has a real
     decision in it, but the answers are not stored anywhere in this file. */
  var SCENARIOS = [
    { id: 'warmup', title: 'A small slip', site: 'robust_pick', plan: '2026-11-18T00:00:00Z', slip: 4,
      story: 'The worked example from the top of the page. The launch is 4 days late. Is the plan still good, or is there a better move?',
      options: [{ kind: 'stay' }, { kind: 'hour', hours: -12 }, { kind: 'site', site: 'malapert_earth' }, { kind: 'wait' }] },
    { id: 'margin', title: 'Past the margin', site: 'robust_pick', plan: '2026-11-18T00:00:00Z', slip: 9,
      story: 'Same site, but now the launch is 9 days late. Something changes between day 8 and day 9.',
      options: [{ kind: 'stay' }, { kind: 'hour', hours: -12 }, { kind: 'site', site: 'malapert' }, { kind: 'wait' }] },
    { id: 'im1', title: 'Replay: IM-1 Odysseus', replay: 'im1', slip: 2,
      story: 'A real mission: Intuitive Machines\' IM-1 landed near Malapert A on 22 Feb 2024. Here its launch slips 2 days.',
      options: [{ kind: 'stay' }, { kind: 'hour', hours: -12 }, { kind: 'site', site: 'malapert_earth' }, { kind: 'wait' }] },
    { id: 'artemis', title: 'Choose a south-pole site', site: 'robust_pick', plan: '2026-12-17T13:00:00Z', slip: 3,
      story: 'The December window, 3 days late. The team asks you to pick one of four south-pole sites for the new date. Mons Mouton is one of NASA\'s candidate landing regions (its feature centre: NASA has published no landing coordinates); each option says where its point comes from.',
      options: [{ kind: 'site', site: 'shackleton' }, { kind: 'site', site: 'shackleton_rim' }, { kind: 'site', site: 'malapert_earth' }, { kind: 'site', site: 'mouton' }] },
    { id: 'lowsun', title: 'A low-Sun month', site: 'robust_pick', plan: '2027-01-16T01:00:00Z', slip: 2,
      story: 'January 2027: the Sun climbs less high over this ridge than in November. The launch is 2 days late.',
      options: [{ kind: 'stay' }, { kind: 'wait' }, { kind: 'site', site: 'shackleton' }, { kind: 'site', site: 'im2' }] }
  ];
  var DEFAULT_NEED = { need_sun_h: 240, need_earth_h: 100, window_days: 14 };

  function esc(s) {
    return String(s).replace(/[&<>"']/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]; });
  }
  function iso(ms) { return new Date(ms).toISOString().slice(0, 19) + 'Z'; }
  function addH(s, h) { return iso(Date.parse(s) + h * 3600000); }
  function dayText(s) {
    return parseInt(s.slice(8, 10), 10) + ' ' + MON[parseInt(s.slice(5, 7), 10) - 1] + ' ' + s.slice(0, 4) +
      (s.slice(11, 16) === '00:00' ? '' : ', ' + s.slice(11, 16) + ' UTC');
  }
  function plural(n, w) { return n + ' ' + w + (n === 1 ? '' : 's'); }
  function span(h) { return h >= 48 ? plural(Math.round(h / 24), 'day') : plural(h, 'hour'); }
  function key(o) { return JSON.stringify(o); }
  function css() {
    var base = SCRIPT_SRC ? SCRIPT_SRC.replace(/planner_game\.js(\?.*)?$/, '') : '/static/addons/';
    ['addons.css', 'game.css'].forEach(function (f) {
      if (document.querySelector('link[href*="addons/' + f + '"]')) { return; }
      var l = document.createElement('link'); l.rel = 'stylesheet'; l.href = base + f;
      document.head.appendChild(l);
    });
  }
  function store(k, v) {
    try { if (v === undefined) { return window.localStorage.getItem(k); } window.localStorage.setItem(k, v); } catch (e) { /* private window */ }
    return null;
  }

  /* ---------- the reason, in one plain sentence, from the server's own numbers ---------- */
  function where(t) {
    if (!t || t.kind !== 'terrain') { return 'the skyline to the ' + (t ? t.compass : 'horizon'); }
    if (t.near_field) { return 'the ground right beside the lander, to the ' + t.compass; }
    var s = 'the ground ' + (t.dist_km >= 1 ? Math.round(t.dist_km) + ' km away ' : '') + 'to the ' + t.compass;
    if (t.named && t.named.phrase) { s += ' (' + t.named.phrase.replace(/^on the /, 'the ').replace(/^inside /, 'in ') + ')'; }
    return s;
  }
  /* the longest stretch in which the ground really hides the body (not only a gap in radio-dish coverage) */
  function hidingStretch(list) {
    var best = null;
    (list || []).forEach(function (s) { if (s.deepest_below_skyline_deg > 0 && (!best || s.hours > best.hours)) { best = s; } });
    return best;
  }
  function stretchText(name, s, windowDays) {
    var day = Math.floor(s.from_hour / 24) + 1;
    var start = s.from_hour === 0 ? 'the ' + name + ' is already behind ' + where(s.terrain) + ' when the lander arrives'
      : 'the ' + name + ' goes behind ' + where(s.terrain) + ' on day ' + day + ' of the ' + windowDays;
    return start + (s.runs_to_end_of_window ? ' and stays hidden to the end' : ' and stays hidden for ' + span(s.hours));
  }
  function reason(card, d, w) {
    var need = card.need, wd = card.window_days;
    if (d.verdict === 'yes') {
      return 'It works: ' + d.sunlit_h + ' hours of sunlight (it needs ' + need.sunlit_h + ') and ' + d.earth_h +
        ' hours of radio contact with Earth (it needs ' + need.earth_h + '), at all ' + d.points + ' spots where it might come down.';
    }
    if (d.verdict === 'not sure') {
      var r = Math.round((card.sure && card.sure.scatter_m) || 100);
      if (d.points_passing > 0 && d.points_passing < d.points) {
        return 'Nobody can promise it: the plan works at ' + d.points_passing + ' of the ' + d.points + ' spots within ' + r +
          ' m where the lander might come down, but not at the others.';
      }
      return 'Nobody can promise it: ' + (d.points_passing === d.points ? 'every touchdown spot passes, but ' : 'the touchdown spots fail, but ') +
        'a coarser or a finer map of the ground gives the opposite answer.';
    }
    if (d.verdict !== 'no') { return 'This date was not worked out (it runs past 2050).'; }
    var txt = d.reasons.join(' ');
    var sunTd = /Sun is behind the skyline at touchdown/.test(txt), earthTd = /Earth is behind the skyline at touchdown/.test(txt);
    var sunShort = /sunlit hours/.test(txt), earthShort = /Earth contact/.test(txt);
    var body = (sunTd || sunShort) ? 'sun' : 'earth';
    var s = w ? hidingStretch(body === 'sun' ? w.sun_hidden : w.earth_hidden) : null;
    var lead = s ? stretchText(body === 'sun' ? 'Sun' : 'Earth', s, wd) : '';
    lead = lead ? lead.charAt(0).toUpperCase() + lead.slice(1) : '';
    if (body === 'sun' && sunShort) {
      return (lead ? lead + ', so it gets' : 'It gets') + ' only ' + d.sunlit_h + ' hours of sunlight for power; it needs ' + need.sunlit_h + '.';
    }
    if (body === 'sun') {
      return (lead ? lead + ': it' : 'The Sun is behind the ground at touchdown: the lander') + ' would land in the dark.';
    }
    if (earthShort) {
      if (!lead && w && !(w.earth_hidden || []).length && card.criteria && card.criteria.stations) {
        return 'The Earth stays in view, but a big radio dish on Earth cannot always see the Moon, so it can radio Earth for only ' +
          d.earth_h + ' hours; it needs ' + need.earth_h + '.';
      }
      return (lead ? lead + ', so it' : 'It') + ' can radio Earth for only ' + d.earth_h + ' hours; it needs ' + need.earth_h + '.';
    }
    if (earthTd) {
      return (lead ? lead + ': it' : 'The Earth is behind the ground at touchdown: the lander') + ' could not call home as it lands.';
    }
    return 'It does not meet the need: ' + d.reasons.join('; ') + '.';
  }

  /* ---------- talking to the server (each answer asked once per game) ---------- */
  var cache = {};
  function once(k, make, soft) {
    if (!cache[k]) {
      cache[k] = make();
      cache[k].catch(function () { delete cache[k]; });
      if (soft) { cache[k] = cache[k].catch(function () { return null; }); }
    }
    return cache[k];
  }
  /* the rules of the main card (Sun rule, Earth margin, ground-station rule, scatter, ...); the scenario sets the site,
     the landing and the need */
  function rules() {
    var p = TAP.plan(), o = {};
    Object.keys(p).forEach(function (k) {
      if (['site', 'landing', 'day', 'slip_days', 'alternatives', 'days', 'need_sun_h', 'need_earth_h', 'window_days'].indexOf(k) < 0) { o[k] = p[k]; }
    });
    return o;
  }
  function bodyFor(sc, opt) {
    var b = JSON.parse(JSON.stringify(game.rules));
    b.need_sun_h = sc.need.need_sun_h; b.need_earth_h = sc.need.need_earth_h; b.window_days = sc.need.window_days;
    b.site = { id: opt.site }; b.landing = opt.landing; b.slip_days = 30;
    return b;
  }
  function mission(sc, opt) { var b = bodyFor(sc, opt); return once('m' + key(b), function () { return TAP.api('/api/mission', b); }); }
  function why(sc, opt) {
    /* the Sun and Earth tracks with the radio-dish rule off, so "hidden" means hidden by the ground; the verdict itself
       always comes from /api/mission with the card's rules */
    var b = bodyFor(sc, opt); b.day = 0; b.earth_stations = false;
    return once('w' + key(b), function () { return TAP.api('/api/why', b); }, true);
  }
  function windows(sc, site, landing) {
    var b = bodyFor(sc, { site: site, landing: landing }); delete b.slip_days; delete b.scatter_m;
    b.scatter_m = game.rules.scatter_m;
    return once('n' + key(b), function () { return TAP.api('/api/windows', b); }, true);
  }
  function safety(site) { return once('s' + site, function () { return TAP.api('/api/addons/safety/site?id=' + encodeURIComponent(site)); }, true); }
  function touch(site) { return once('t' + site, function () { return TAP.api('/api/addons/safetouch/site?id=' + encodeURIComponent(site)); }, true); }
  function relay(site, landing) {
    return once('r' + site + landing, function () {
      return TAP.api('/api/addons/relay/window?site=' + encodeURIComponent(site) + '&landing=' + encodeURIComponent(landing) +
        '&stations=' + (game.rules.earth_stations === false ? 'false' : 'true'));
    }, true);
  }
  function catalog() {
    return once('sites', function () { return TAP.api('/api/sites'); }).then(function (r) {
      var o = {}; r.sites.forEach(function (s) { o[s.id] = s; }); return o;
    });
  }
  function replays() { return once('replays', function () { return TAP.api('/api/replays'); }); }

  /* ---------- the game ---------- */
  var game = { k: 0, total: 0, rounds: [], rules: null, sites: {}, sc: null, chosen: null, busy: false };
  var ui = {};

  function score(m, opt) {
    var margin = Math.max(0, m.slip_margin_days);
    var waited = opt.waitedDays || 0;
    return { points: POINTS[m.verdict] || 0, margin: Math.min(50, 5 * (m.verdict === 'yes' ? margin : 0)), waited: waited,
      total: Math.max(0, (POINTS[m.verdict] || 0) + Math.min(50, 5 * (m.verdict === 'yes' ? margin : 0)) - waited) };
  }

  function render(box) {
    var best = store(BEST_KEY);
    box.innerHTML =
      '<section class="sd-addon sd-game" aria-labelledby="sd-game-h">' +
      '<h2 id="sd-game-h">Be the mission planner</h2>' +
      '<p class="sd-lead" id="sd-game-intro">You run mission control for a robot lander going to the Moon\'s south pole. ' +
      'Down there the Sun and the Earth hang low over the hills, so a ridge can block sunlight (power) or the view of Earth (radio) for days. ' +
      'Your launch has slipped. In each of five scenarios you read the briefing, look at the real data for each option, and commit to one. ' +
      'Then Slipday shows what really happens, worked out from NASA\'s laser height map of the Moon. The scenarios get harder as you go.</p>' +
      '<ol class="sd-camp" id="sd-game-camp" aria-label="The five scenarios">' +
      SCENARIOS.map(function (s, i) { return '<li data-k="' + i + '"><span class="sd-camp-n">' + (i + 1) + '</span> ' + esc(s.title) + '<span class="sd-camp-s"></span></li>'; }).join('') +
      '</ol>' +
      '<div class="sd-row"><button type="button" class="sd-primary" id="sd-game-start">Start the campaign</button>' +
      '<span class="sd-score" id="sd-game-score" aria-live="off">' + (best ? 'Best campaign score in this browser: ' + esc(best) + ' points.' : '') + '</span></div>' +
      '<div class="sd-stage" id="sd-game-stage"></div>' +
      '<p class="sd-sr" id="sd-game-status" role="status" aria-live="polite" aria-atomic="true"></p>' +
      '<details class="sd-more sd-rules"><summary>How scoring works, and what is real</summary>' +
      '<p class="sd-note">Game rule: a Yes earns 100 points, a Not sure 40 and a No 0. A Yes also earns 5 points for each day of slip margin it keeps (up to 50). ' +
      'Waiting for a later window costs 1 point per day waited, because the team and the rocket sit idle. These point values are the game\'s own choice.</p>' +
      '<p class="sd-note">Real: the Sun and Earth positions (JPL DE421), the skyline (NASA LOLA elevation data), the verdict at 13 touchdown spots, slope from LOLA grids and relay hours from a published NASA reference orbit. ' +
      'Illustrative: the 240 sunlit hours and 100 hours of Earth contact, unless the briefing names a published plan. Assumed: that the landing hour can be moved by 12 hours. ' +
      'Yes: works at every touchdown spot. Not sure: works at some spots only, or a different map of the ground disagrees. No: works nowhere.</p></details>' +
      '</section>';
    ui.start = $('sd-game-start'); ui.stage = $('sd-game-stage'); ui.status = $('sd-game-status'); ui.score = $('sd-game-score'); ui.camp = $('sd-game-camp');
    ui.start.addEventListener('click', start);
  }
  function say(t) { ui.status.textContent = ''; setTimeout(function () { ui.status.textContent = t; }, 30); }
  function campaignMarks() {
    Array.prototype.forEach.call(ui.camp.querySelectorAll('li'), function (li, i) {
      var r = game.rounds[i];
      li.classList.toggle('sd-now', i === game.k && !game.done);
      li.querySelector('.sd-camp-s').textContent = r ? ' · ' + r.score.total + ' points' : '';
      if (i === game.k && !game.done) { li.setAttribute('aria-current', 'step'); } else { li.removeAttribute('aria-current'); }
    });
  }

  function start() {
    game.k = 0; game.total = 0; game.rounds = []; game.done = false; game.rules = rules();
    ui.start.textContent = 'Start again';
    ui.stage.innerHTML = '<p class="sd-wait">Getting the briefing ready…</p>';
    Promise.all([catalog(), replays()]).then(function (r) {
      game.sites = r[0]; game.replays = r[1];
      showScenario();
    }).catch(function (e) { ui.stage.innerHTML = '<p class="sd-wait">The game could not start: ' + esc(e.message) + '</p>'; });
  }

  /* turn a scenario's settings into (site, landing) options, using the server for the next monthly window */
  function prepare(sc0) {
    var sc = JSON.parse(JSON.stringify(sc0));
    sc.need = DEFAULT_NEED; sc.needKind = 'illustrative';
    if (sc.replay) {
      var rp = (game.replays.missions || []).filter(function (x) { return x.id === sc.replay; })[0];
      if (!rp) { return Promise.reject(new Error('the real landing ' + sc.replay + ' is not on this server')); }
      sc.site = rp.site; sc.plan = rp.landing; sc.rp = rp;
      sc.need = { need_sun_h: rp.need_sun_h, need_earth_h: rp.need_earth_h, window_days: rp.window_days }; sc.needKind = rp.need_kind;
    }
    sc.slipped = addH(sc.plan, 24 * sc.slip);
    var waitP = sc.options.some(function (o) { return o.kind === 'wait'; }) ? windows(sc, sc.site, sc.plan) : Promise.resolve(null);
    return waitP.then(function (w) {
      sc.options = sc.options.map(function (o) {
        var opt = { kind: o.kind, site: o.site || sc.site };
        var nm = function (id) { return (game.sites[id] && game.sites[id].name) || id; };
        if (o.kind === 'stay') { opt.landing = sc.slipped; opt.title = 'Stay with the plan'; opt.sub = 'Land at ' + nm(sc.site) + ' ' + plural(sc.slip, 'day') + ' late'; }
        if (o.kind === 'hour') {
          opt.landing = addH(sc.slipped, o.hours); opt.title = 'Land ' + Math.abs(o.hours) + ' hours ' + (o.hours < 0 ? 'earlier' : 'later');
          opt.sub = 'Same site, ' + dayText(opt.landing) + ' (assumes the flight path can be trimmed)';
        }
        if (o.kind === 'site') {
          var cf = game.sites[o.site] && game.sites[o.site].confidence;
          opt.landing = sc.slipped; opt.title = 'Switch to ' + nm(o.site); var CF = { 'DEM summit': 'the highest point on the elevation map', 'feature centre': 'centre of the named feature', 'literature point': 'a point from a published study', 'model-selected point': 'a point chosen by this project', 'landed point': 'where a lander came down' };
          opt.sub = 'Land there on the slipped date' + (cf ? ' (' + (CF[cf] || cf) + ')' : '');
        }
        if (o.kind === 'wait') {
          var row = w && w.rows ? w.rows.filter(function (r) { return Date.parse(r.landing_utc) > Date.parse(sc.slipped); })[0] : null;
          if (!row) { return null; }
          opt.landing = row.landing_utc; opt.waitedDays = Math.round((Date.parse(row.landing_utc) - Date.parse(sc.slipped)) / 86400000);
          opt.title = 'Wait for the next monthly window'; opt.sub = nm(sc.site) + ' on ' + dayText(row.landing_utc) + ', ' + plural(opt.waitedDays, 'day') + ' after the slipped date';
        }
        opt.siteName = nm(opt.site);
        return opt;
      }).filter(Boolean);
      return sc;
    });
  }

  function showScenario() {
    var sc0 = SCENARIOS[game.k];
    game.chosen = null; game.busy = false;
    campaignMarks();
    ui.stage.innerHTML = '<p class="sd-wait">Getting the briefing ready…</p>';
    prepare(sc0).then(function (sc) {
      game.sc = sc;
      var nm = game.sites[sc.site] ? game.sites[sc.site].name : sc.site;
      var needNote = sc.rp ? esc(sc.rp.need_note) :
        'The 240 sunlit hours and 100 hours of Earth contact are illustrative: no published requirement gives them.';
      var h = '<h3 class="sd-round" id="sd-game-q" tabindex="-1">Scenario ' + (game.k + 1) + ' of ' + SCENARIOS.length + ': ' + esc(sc.title) + '</h3>' +
        '<p class="sd-story">' + esc(sc.story) + '</p>' +
        '<div class="sd-brief" role="group" aria-label="Briefing">' +
        '<div class="sd-bcell"><span class="sd-bk">The mission needs</span><span class="sd-bv">' + sc.need.need_sun_h + ' h of sunlight</span>' +
        '<span class="sd-bv">' + sc.need.need_earth_h + ' h of Earth contact</span><span class="sd-bs">in the first ' + sc.need.window_days + ' days, landing in sunlight with the Earth in view' +
        (sc.needKind === 'published plan' ? ' (sunlight figure from the published plan)' : ' (illustrative)') + '</span></div>' +
        '<div class="sd-bcell"><span class="sd-bk">Original plan</span><span class="sd-bv">' + esc(nm) + '</span><span class="sd-bs">landing ' + esc(dayText(sc.plan)) + '</span></div>' +
        '<div class="sd-bcell sd-slipcell"><span class="sd-bk">What happened</span><span class="sd-bv">Your launch slipped ' + plural(sc.slip, 'day') + '</span>' +
        '<span class="sd-bs">the lander now arrives ' + esc(dayText(sc.slipped)) + '</span></div>' +
        '</div>' +
        '<p class="sd-note">' + needNote + '</p>' +
        '<fieldset class="sd-opts"><legend>Your options: pick one to inspect its data</legend>' +
        sc.options.map(function (o, i) {
          return '<label class="sd-opt" data-i="' + i + '"><input type="radio" name="sd-game-opt" value="' + i + '"' + '>' +
            '<span class="sd-opt-t">' + esc(o.title) + '</span><span class="sd-opt-s">' + esc(o.sub) + '</span></label>';
        }).join('') + '</fieldset>' +
        '<div class="sd-inspect" id="sd-game-inspect" aria-live="polite"><p class="sd-wait">Pick an option above to see its data.</p></div>' +
        '<div class="sd-row"><button type="button" class="sd-primary" id="sd-game-commit" disabled>Commit to this option</button>' +
        '<span class="sd-hint" id="sd-game-hint">Look at as many options as you like before you commit.</span></div>' +
        '<div class="sd-reveal" id="sd-game-reveal"></div>';
      ui.stage.innerHTML = h;
      Array.prototype.forEach.call(ui.stage.querySelectorAll('input[name="sd-game-opt"]'), function (r) {
        r.addEventListener('change', function () { inspect(parseInt(r.value, 10)); });
      });
      $('sd-game-commit').addEventListener('click', commit);
      sc.options.forEach(function (o) { mission(sc, o); why(sc, o); });       /* start asking now; the verdict stays hidden until the commit */
      var q = $('sd-game-q'); if (q) { q.focus(); }
      ui.score.textContent = 'Campaign score: ' + game.total + ' points after ' + plural(game.k, 'scenario') + '.';
      say('Scenario ' + (game.k + 1) + ' of ' + SCENARIOS.length + ': ' + sc.title + '. Your launch slipped ' + plural(sc.slip, 'day') + '. ' + sc.options.length + ' options.');
    }).catch(function (e) {
      ui.stage.innerHTML = '<p class="sd-wait">This scenario could not be set up: ' + esc(e.message) + '</p><button type="button" id="sd-game-retry">Try again</button>';
      $('sd-game-retry').addEventListener('click', showScenario);
    });
  }

  /* ---------- small pictures ---------- */
  function rel(az) { return ((az + 180) % 360 + 360) % 360 - 180; }
  function skyline(w) {
    if (!w || !w.track) { return '<p class="sd-wait">The skyline could not be drawn.</p>'; }
    var t = w.track, sk = w.skyline, lo = -1, hi = 2;
    if (sk) { sk.el_deg.forEach(function (v) { lo = Math.min(lo, v); hi = Math.max(hi, v); }); }
    t.sun_el.forEach(function (v) { hi = Math.max(hi, v); }); t.earth_el.forEach(function (v) { hi = Math.max(hi, v); });
    hi = Math.min(Math.ceil(hi + 0.5), 45); lo = Math.max(Math.floor(lo - 0.5), -10);
    var X = function (az) { return (rel(az) + 180); }, Y = function (e) { return 100 - (Math.max(lo, Math.min(hi, e)) - lo) / (hi - lo) * 100; };
    var path = function (az, el, up, want) {
      var d = '', prev = null;
      for (var k = 0; k < az.length; k++) {
        var x = X(az[k]), y = Y(el[k]), on = !!up[k] === want;
        if (on && prev !== null && Math.abs(x - prev) < 180) { d += 'L' + x.toFixed(1) + ' ' + y.toFixed(1); }
        else if (on) { d += 'M' + x.toFixed(1) + ' ' + y.toFixed(1); }
        prev = on ? x : null;
      }
      return d;
    };
    var g = '';
    if (sk) {
      var pts = sk.az_deg.map(function (a, i) { return [X(a), Y(sk.el_deg[i])]; }).sort(function (a, b) { return a[0] - b[0]; });
      g += '<path class="sd-sky" d="M0 100' + pts.map(function (p) { return 'L' + p[0].toFixed(1) + ' ' + p[1].toFixed(1); }).join('') + 'L360 ' + pts[0][1].toFixed(1) + 'L360 100Z"/>';
    }
    g += '<line class="sd-level" x1="0" x2="360" y1="' + Y(0).toFixed(1) + '" y2="' + Y(0).toFixed(1) + '"/>';
    g += '<path class="sd-trk sd-earth-h" d="' + path(t.earth_az, t.earth_el, t.earth_up, false) + '"/><path class="sd-trk sd-earth-t" d="' + path(t.earth_az, t.earth_el, t.earth_up, true) + '"/>';
    g += '<path class="sd-trk sd-sun-h" d="' + path(t.sun_az, t.sun_el, t.sun_lit, false) + '"/><path class="sd-trk sd-sun-t" d="' + path(t.sun_az, t.sun_el, t.sun_lit, true) + '"/>';
    var dot = function (az, el, cls, lab) {
      return '<span class="sd-dot ' + cls + '" style="left:' + (X(az) / 3.6).toFixed(2) + '%;top:' + Y(el).toFixed(2) + '%" title="' + esc(lab) + '"></span>';
    };
    return '<div class="sd-skyfig" role="img" aria-label="' + esc('Skyline all round ' + w.site.name + ' with the paths of the Sun (orange) and the Earth (blue) over ' + w.window_days + ' days. Elevation from ' + lo + ' to ' + hi + ' degrees.') + '">' +
      '<div class="sd-skybox"><svg viewBox="0 0 360 100" preserveAspectRatio="none" aria-hidden="true">' + g + '</svg>' +
      dot(t.sun_az[0], t.sun_el[0], 'sd-dsun', 'Sun at touchdown') + dot(t.earth_az[0], t.earth_el[0], 'sd-dearth', 'Earth at touchdown') +
      '<span class="sd-ylab sd-yt">' + hi + '°</span><span class="sd-ylab sd-yb">' + lo + '°</span></div>' +
      '<div class="sd-xaxis" aria-hidden="true"><span>S</span><span>W</span><span>N</span><span>E</span><span>S</span></div>' +
      '<p class="sd-key"><i class="sd-k-sun"></i>Sun path <i class="sd-k-earth"></i>Earth path <i class="sd-k-hid"></i>faint: hidden by the ground. Grey: the skyline. Dots: at touchdown.</p></div>';
  }
  function bar(label, got, need, cls) {
    var max = Math.max(got, need, 1) * 1.08, ok = got >= need;
    return '<div class="sd-bar"><span class="sd-bar-l">' + label + '</span><span class="sd-bar-t" role="img" aria-label="' + esc(label + ': ' + got + ' hours, needs ' + need) + '">' +
      '<span class="sd-bar-f ' + cls + '" style="width:' + (got / max * 100).toFixed(1) + '%"></span>' +
      '<span class="sd-bar-n" style="left:' + (need / max * 100).toFixed(1) + '%"></span></span>' +
      '<span class="sd-bar-v"><b>' + got + ' h</b> of ' + need + ' needed ' + (ok ? '' : '<span class="sd-short">(short)</span>') + '</span></div>';
  }
  /* 14 days, hour by hour: when the Sun and the Earth are above the skyline, with the first set of each marked */
  function timeline(w) {
    if (!w || !w.track) { return ''; }
    var t = w.track, n = Math.min(w.window_hours, t.count - 1);
    var row = function (flags, cls, name) {
      var stops = [], first = null;
      for (var k = 0; k < n; k++) {
        if (k > 0 && flags[k - 1] && !flags[k] && first === null) { first = k; }
      }
      var runs = [], cur = flags[0], from = 0;
      for (var j = 1; j <= n; j++) { if (j === n || flags[j] !== cur) { runs.push([from, j, cur]); from = j; cur = flags[j]; } }
      runs.forEach(function (r) {
        var a = (r[0] / n * 100).toFixed(2) + '%', b = (r[1] / n * 100).toFixed(2) + '%', c = r[2] ? 'var(--sd-' + cls + ')' : 'var(--sd-off)';
        stops.push(c + ' ' + a, c + ' ' + b);
      });
      var upH = 0; for (var u = 0; u < n; u++) { upH += flags[u] ? 1 : 0; }
      var mark = first === null ? '' : '<span class="sd-tl-mark" style="left:' + (first / n * 100).toFixed(2) + '%"><span' + (first / n > 0.6 ? ' class="sd-tl-r"' : '') + '>' + name + ' sets day ' + (Math.floor(first / 24) + 1) + '</span></span>';
      return '<div class="sd-tl-row"><span class="sd-tl-k">' + name + '</span><span class="sd-tl-bar" style="background:linear-gradient(90deg,' + stops.join(',') + ')">' + mark + '</span></div>' +
        '<p class="sd-sr">' + name + ' above the skyline for ' + upH + ' of ' + n + ' hours' + (first === null ? ', no setting in the window.' : ', first sets on day ' + (Math.floor(first / 24) + 1) + '.') + '</p>';
    };
    var days = '';
    for (var d = 1; d <= Math.round(n / 24); d++) { days += '<span>' + d + '</span>'; }
    return '<div class="sd-tl"><p class="sd-tl-h">The ' + Math.round(n / 24) + ' days after landing, hour by hour (coloured: above the skyline)</p>' +
      row(t.sun_lit, 'sun', 'Sun') + row(t.earth_up, 'earth', 'Earth') +
      '<div class="sd-tl-days" aria-hidden="true"><span class="sd-tl-k">Day</span><span class="sd-tl-dn">' + days + '</span></div>' +
      '<p class="sd-note">Earth here means above the skyline. Radio contact also needs a big dish on Earth that can see the Moon, so the Earth-contact hours can be lower.</p></div>';
  }

  /* ---------- inspect one option ---------- */
  function inspect(i) {
    var sc = game.sc, o = sc.options[i];
    game.chosen = i;
    Array.prototype.forEach.call(ui.stage.querySelectorAll('.sd-opt'), function (l, k) { l.classList.toggle('sd-sel', k === i); });
    $('sd-game-commit').disabled = false;
    var box = $('sd-game-inspect');
    box.removeAttribute('data-ready');
    box.innerHTML = '<p class="sd-wait">Getting the data for "' + esc(o.title) + '"…</p>';
    Promise.all([mission(sc, o), why(sc, o), safety(o.site), touch(o.site), relay(o.site, o.landing), windows(sc, o.site, sc.plan)]).then(function (r) {
      if (game.chosen !== i || game.sc !== sc) { return; }
      var m = r[0], w = r[1], sf = r[2], st = r[3], rl = r[4], wn = r[5], d = m.days[0];
      var td = w && w.touchdown;
      var clr = function (e, s) { var c = e - s; return c >= 0 ? c.toFixed(1) + '° above the skyline' : Math.abs(c).toFixed(1) + '° below the skyline (hidden)'; };
      var h = '<h4>' + esc(o.title) + ': ' + esc(o.siteName) + ', ' + esc(dayText(o.landing)) + '</h4><div class="sd-ins-grid"><div>' + skyline(w) + '</div><div>';
      h += bar('Sunlight', d.sunlit_h, m.need.sunlit_h, 'sd-f-sun') + bar('Earth contact', d.earth_h, m.need.earth_h, 'sd-f-earth');
      h += '<ul class="sd-facts">';
      if (td) {
        h += '<li><b>At touchdown:</b> Sun ' + clr(td.sun_el, td.sun_skyline_el) + '; Earth ' + clr(td.earth_el, td.earth_skyline_el) + '.</li>';
      }
      if (sf && sf.available) { h += '<li><b>Flat enough?</b> ' + esc(sf.headline) + '</li>'; }
      else { h += '<li><b>Flat enough?</b> Not known here: no fine slope map covers this site.</li>'; }
      var cl = st && st.available && st.classes ? st.classes.filter(function (c) { return c.id === 'clps' && c.available !== false; })[0] : null;
      if (cl && cl.p8 !== undefined) { h += '<li><b>Safe touchdown chance</b> for a CLPS-class lander (assumed accuracy): ' + cl.p8 + ' % of landings on ground under 8°.</li>'; }
      else { h += '<li><b>Safe touchdown chance:</b> not known here.</li>'; }
      /* the same field as the "wait" option: the plan's monthly windows, the first one after the slipped date */
      var nx = wn && wn.rows ? wn.rows.filter(function (r) { return Date.parse(r.landing_utc) > Date.parse(sc.slipped); })[0] : null;
      if (nx) { h += '<li><b>Next monthly window</b> at this site after the slipped date: ' + esc(dayText(nx.landing_utc)) + '.</li>'; }
      if (rl && rl.available && rl.hours) { h += '<li><b>Relay satellites</b> (a NASA reference orbit, not a live service) would give radio contact in ' + rl.hours.either + ' of ' + rl.window_hours + ' hours, against ' + rl.hours.earth + ' direct to Earth.</li>'; }
      h += '</ul><p class="sd-note">These hours are for the exact target. The final answer also checks 13 touchdown spots and a second elevation map, so it can still come out Not sure.</p></div></div>';
      box.innerHTML = h; box.setAttribute('data-ready', '1');
    }).catch(function (e) { if (game.chosen === i) { box.innerHTML = '<p class="sd-wait">The server could not answer: ' + esc(e.message) + '</p>'; } });
  }

  /* ---------- commit and reveal ---------- */
  function commit() {
    if (game.chosen === null || game.busy) { return; }
    game.busy = true;
    var sc = game.sc, i = game.chosen;
    $('sd-game-commit').disabled = true;
    Array.prototype.forEach.call(ui.stage.querySelectorAll('input[name="sd-game-opt"]'), function (r) { r.disabled = true; });
    var rv = $('sd-game-reveal');
    rv.innerHTML = '<p class="sd-wait">Working out what really happens…</p>';
    Promise.all(sc.options.map(function (o) {
      return Promise.all([mission(sc, o), why(sc, o)]).then(function (r) { return { o: o, m: r[0], w: r[1], s: score(r[0], o), body: bodyFor(sc, o) }; });
    })).then(function (res) { reveal(res, i); }).catch(function (e) {
      game.busy = false;
      rv.innerHTML = '<p class="sd-wait">The server could not answer: ' + esc(e.message) + '</p><button type="button" id="sd-game-retry">Try again</button>';
      $('sd-game-retry').addEventListener('click', function () { $('sd-game-commit').disabled = false; commit(); });
    });
  }
  function verdictText(m) {
    var v = WORD[m.verdict] || m.verdict;
    if (m.verdict === 'yes') { return v + (m.slip_margin_days > 0 ? ', and it could slip ' + plural(m.slip_margin_days, 'more day') : ', with no days to spare'); }
    return v;
  }
  function reveal(res, i) {
    var sc = game.sc, mine = res[i];
    var best = res.reduce(function (a, b) { return b.s.total > a.s.total ? b : a; }, res[0]);
    var isBest = mine.s.total >= best.s.total;
    game.total += mine.s.total;
    game.rounds.push({ id: sc.id, choice: mine.o, score: mine.s, best: best.s.total });
    var v = mine.m.verdict, cls = v.replace(' ', '').replace('/', ''), d = mine.m.days[0];
    var h = '<div class="sd-outcome v-' + cls + '" id="sd-game-outcome" data-site="' + esc(key({ id: mine.o.site })) + '" data-landing="' + esc(mine.m.landing_utc) +
      '" data-verdict="' + esc(v) + '" data-margin="' + mine.m.slip_margin_days + '" data-sun="' + d.sunlit_h + '" data-earth="' + d.earth_h + '" data-score="' + mine.s.total + '">' +
      '<h3 id="sd-game-out-h" tabindex="-1"><span class="sd-icon" aria-hidden="true">' + ICON[v] + '</span> Outcome: ' + esc(verdictText(mine.m)) + '</h3>' +
      '<p>' + esc(reason(mine.m, d, mine.w)) + '</p>' +
      '<p class="sd-pts"><b>' + mine.s.total + ' points</b> (' + mine.s.points + ' for the answer' + (mine.s.margin ? ', ' + mine.s.margin + ' for the margin kept' : '') +
      (mine.s.waited ? ', minus ' + mine.s.waited + ' for ' + plural(mine.s.waited, 'day') + ' of waiting' : '') + ').</p>' +
      timeline(mine.w) + '</div>';
    h += '<p class="sd-result ' + (isBest ? 'sd-good' : 'sd-bad') + '">' + (isBest ? (best.s.total > 0 ? 'Best call: no option here scores higher.' : 'No option here works: a real team would look further ahead.') :
      'The best option here was "' + esc(best.o.title) + '" (' + esc(best.o.siteName) + '): ' + esc(verdictText(best.m)) + ', ' + best.s.total + ' points.') + '</p>';
    h += '<div class="sd-tablewrap"><table class="sd-cmp"><caption>All options, with the real answers</caption><thead><tr><th scope="col">Option</th><th scope="col">Answer</th><th scope="col">Margin</th><th scope="col">Sunlight</th><th scope="col">Earth contact</th><th scope="col">Points</th></tr></thead><tbody>';
    res.forEach(function (r, k) {
      var dv = r.m.days[0], c = r.m.verdict.replace(' ', '').replace('/', '');
      h += '<tr class="sd-row-' + c + (k === i ? ' sd-mine' : '') + (r === best ? ' sd-best' : '') + '" data-site="' + esc(key({ id: r.o.site })) + '" data-landing="' + esc(r.m.landing_utc) +
        '" data-verdict="' + esc(r.m.verdict) + '" data-margin="' + r.m.slip_margin_days + '" data-sun="' + dv.sunlit_h + '" data-earth="' + dv.earth_h + '">' +
        '<th scope="row">' + esc(r.o.title) + '<small>' + esc(r.o.siteName) + ', ' + esc(dayText(r.m.landing_utc)) + (k === i ? ' · your pick' : '') + (r === best ? ' · best' : '') + '</small></th>' +
        '<td data-l="Answer"><span class="sd-vchip">' + ICON[r.m.verdict] + ' ' + esc(WORD[r.m.verdict]) + '</span></td><td data-l="Margin">' + (r.m.verdict === 'yes' ? plural(r.m.slip_margin_days, 'day') : '–') + '</td>' +
        '<td data-l="Sunlight">' + dv.sunlit_h + ' / ' + r.m.need.sunlit_h + ' h</td><td data-l="Earth contact">' + dv.earth_h + ' / ' + r.m.need.earth_h + ' h</td><td data-l="Points">' + r.s.total + '</td></tr>';
    });
    h += '</tbody></table></div>';
    var last = game.k + 1 >= SCENARIOS.length;
    h += '<div class="sd-row"><button type="button" class="sd-primary" id="sd-game-next">' + (last ? 'See my campaign score' : 'Next scenario') + '</button></div>';
    $('sd-game-reveal').innerHTML = h;
    game.last = { body: mine.body, verdict: v, margin: mine.m.slip_margin_days, sunlit_h: d.sunlit_h, earth_h: d.earth_h, score: mine.s.total, all: res.map(function (r) { return { body: r.body, verdict: r.m.verdict, score: r.s.total }; }) };
    ui.score.textContent = 'Campaign score: ' + game.total + ' points after ' + plural(game.k + 1, 'scenario') + '.';
    campaignMarks();
    say('Outcome: ' + verdictText(mine.m) + '. ' + reason(mine.m, d, mine.w) + ' ' + mine.s.total + ' points. ' + (isBest ? 'Best call.' : 'The best option was ' + best.o.title + '.'));
    $('sd-game-next').addEventListener('click', function () {
      game.k += 1;
      if (game.k >= SCENARIOS.length) { finish(); } else { showScenario(); }
    });
    $('sd-game-out-h').focus({ preventScroll: false });
  }

  function finish() {
    game.done = true;
    var prev = parseInt(store(BEST_KEY) || '0', 10) || 0;
    if (game.total > prev) { store(BEST_KEY, String(game.total)); }
    var max = game.rounds.reduce(function (a, r) { return a + r.best; }, 0);
    var msg = 'Campaign complete: ' + game.total + ' points. The best options offered would have scored ' + max + '. ' +
      (game.total >= max ? 'A perfect run: mission control would hire you.' : game.total >= 0.8 * max ? 'Very close to the best plan.' : game.total >= 0.5 * max ? 'Well planned: near the pole a few hours can change everything.' : 'Near the pole a few hours can change everything. Try again?');
    campaignMarks();
    ui.stage.innerHTML = '<h3 class="sd-round" id="sd-game-end" tabindex="-1">' + esc(msg) + '</h3>' +
      '<ol class="sd-sum">' + game.rounds.map(function (r, i) { return '<li>' + esc(SCENARIOS[i].title) + ': ' + esc(r.choice.title) + ', ' + r.score.total + ' points</li>'; }).join('') + '</ol>' +
      '<p>Every answer came from the same calculation as the main page. Each slip moves the Sun and the Earth to new places in the sky, and the hills around each site hide them at different times.</p>' +
      '<div class="sd-row"><button type="button" class="sd-primary" id="sd-game-again">Play again</button></div>';
    ui.score.textContent = 'Final score: ' + game.total + ' points. Best in this browser: ' + Math.max(prev, game.total) + ' points.';
    say(msg);
    $('sd-game-again').addEventListener('click', start);
    $('sd-game-end').focus();
  }

  function init() {
    css();
    var box = $('addon-game');
    if (box) { render(box); }
  }
  if (document.readyState === 'loading') { document.addEventListener('DOMContentLoaded', init); } else { init(); }
  window.SlipdayGame = { reason: reason, scenarios: SCENARIOS, state: function () { return game; } };
})();
