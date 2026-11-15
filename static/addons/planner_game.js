/* Slipday add-on: "Be the mission planner", a five-round game for students (ages 12 and up).

   Include with one script tag and one container:
     <div id="addon-game"></div>
     <script src="/static/addons/planner_game.js"></script>

   Each round the launch slips by a random number of days and the player picks one of three landing sites: the
   site on the main card and two others from the page's own site list (the sites the card was asked about; the
   app's curated south-pole sites when the page has fewer than two others).  Then the real answer for all three
   is shown, with the reason in one plain sentence.  Every answer comes from the server (/api/mission for the
   verdict, /api/why for the ground that hides the Sun or the Earth); nothing is made up.  The score lives only in
   this browser tab; the best score is kept in this browser's local storage when it is allowed.
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
  var ROUNDS = 5, MAX_SLIP = 12;   /* 1 to 12 days: past that this plan is mostly in the lunar night everywhere */
  var WORD = { yes: 'Yes', 'not sure': 'Not sure', no: 'No', 'n/a': 'Not worked out' };
  var ICON = { yes: '✓', 'not sure': '?', no: '✕', 'n/a': '–' };
  var RANK = { yes: 2, 'not sure': 1, no: 0, 'n/a': -1 };
  var SCRIPT_SRC = document.currentScript && document.currentScript.src;

  function esc(s) {
    return String(s).replace(/[&<>"']/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]; });
  }
  function dayText(iso) {
    return parseInt(iso.slice(8, 10), 10) + ' ' + MON[parseInt(iso.slice(5, 7), 10) - 1] + ' ' + iso.slice(0, 4) +
      (iso.slice(11, 16) === '00:00' ? '' : ' at ' + iso.slice(11, 16) + ' UTC');
  }
  function plural(n, w) { return n + ' ' + w + (n === 1 ? '' : 's'); }
  function span(h) { return h >= 48 ? plural(Math.round(h / 24), 'day') : plural(h, 'hour'); }
  function shuffle(a) {
    a = a.slice();
    for (var i = a.length - 1; i > 0; i--) { var j = Math.floor(Math.random() * (i + 1)), t = a[i]; a[i] = a[j]; a[j] = t; }
    return a;
  }
  function key(ref) { return JSON.stringify(ref); }
  function css() {
    if (document.querySelector('link[href*="addons/addons.css"]')) { return; }
    var l = document.createElement('link'); l.rel = 'stylesheet';
    l.href = SCRIPT_SRC ? SCRIPT_SRC.replace(/planner_game\.js(\?.*)?$/, 'addons.css') : '/static/addons/addons.css';
    document.head.appendChild(l);
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

  /* ---------- talking to the server ---------- */
  var cache = {};
  function bodyFor(ref) {
    var b = JSON.parse(JSON.stringify(game.plan));
    b.site = ref; b.slip_days = 30; delete b.day;
    return b;
  }
  function card(ref) {
    var k = 'm' + key(ref) + game.planKey;
    if (!cache[k]) { cache[k] = TAP.api('/api/mission', bodyFor(ref)); cache[k].catch(function () { delete cache[k]; }); }
    return cache[k];
  }
  function why(ref, slip) {
    var k = 'w' + key(ref) + slip + game.planKey;
    if (!cache[k]) {
      /* the ground that hides the Sun or the Earth, read with the radio-dish rule off, so that "hidden" means
         hidden by the ground only; the verdict itself always comes from /api/mission with the card's rules */
      var b = bodyFor(ref); b.day = slip; b.earth_stations = false;
      cache[k] = TAP.api('/api/why', b).catch(function () { return null; });   /* the verdict stands without it */
    }
    return cache[k];
  }
  var catalog = null;
  function southPole() {
    if (!catalog) {
      catalog = TAP.api('/api/sites').then(function (r) {
        return r.sites.filter(function (s) { return s.group === 'South pole' && s.terrain && !/always dark/.test(s.name); })
          .map(function (s) { return { ref: { id: s.id }, name: s.name }; });
      });
      catalog.catch(function () { catalog = null; });
    }
    return catalog;
  }

  /* ---------- the game ---------- */
  var game = { round: 0, score: 0, slips: [], plan: null, planKey: '', planned: null, pool: [], choices: [], picked: null };
  var ui = {};

  function render(box) {
    var best = store('slipday.planner.best');
    box.innerHTML =
      '<section class="sd-addon sd-game" aria-labelledby="sd-game-h">' +
      '<h2 id="sd-game-h">Be the mission planner</h2>' +
      '<div class="sd-intro" id="sd-game-intro">' +
      '<p>A robot lander is set to touch down near the Moon\'s south pole. There, the Sun and the Earth always stay low in the sky, ' +
      'so a hill or the rim of a crater can hide them for days. The lander needs <b>sunlight</b> for power and the <b>Earth in view</b> to radio home.</p>' +
      '<p>Rockets often launch late. That delay is called a <b>slip</b>: if the launch slips, the landing is later too, and the Sun and the Earth are in different places. ' +
      'In each round the launch slips by a few days. You pick one of three landing sites. Then you see the real answer for all three, worked out from NASA\'s height map of the Moon.</p>' +
      '<p>Five rounds. You score a point when your pick is as good as the best of the three: Yes beats Not sure, and Not sure beats No.</p>' +
      '</div>' +
      '<div class="sd-row"><button type="button" class="sd-primary" id="sd-game-start">Start the game</button>' +
      '<span class="sd-score" id="sd-game-score" aria-live="off">' + (best ? 'Best score in this browser: ' + esc(best) + ' of ' + ROUNDS + '.' : '') + '</span></div>' +
      '<div class="sd-stage" id="sd-game-stage"></div>' +
      '<p class="sd-now sd-sr" id="sd-game-status" role="status" aria-live="polite" aria-atomic="true"></p>' +
      '<p class="sd-note">The answers use the main card\'s plan and rules, and the same calculation: Sun and Earth positions from JPL DE421 and the skyline from NASA LOLA elevation data, checked at 13 touchdown spots. ' +
      'Yes: works at every spot. Not sure: works at some spots only, or a different map of the ground disagrees. No: works nowhere.</p>' +
      '</section>';
    ui.start = $('sd-game-start'); ui.stage = $('sd-game-stage'); ui.status = $('sd-game-status'); ui.score = $('sd-game-score');
    ui.start.addEventListener('click', start);
  }
  function say(t) { ui.status.textContent = ''; setTimeout(function () { ui.status.textContent = t; }, 30); }

  function start() {
    game.plan = TAP.plan();
    game.planKey = JSON.stringify(game.plan);
    game.planned = { ref: game.plan.site, name: null };
    game.round = 0; game.score = 0; game.picked = null; game.voided = 0;
    var all = [];
    for (var i = 1; i <= MAX_SLIP; i++) { all.push(i); }
    game.slips = shuffle(all).slice(0, ROUNDS);
    ui.start.textContent = 'Start again';
    ui.stage.innerHTML = '<p class="sd-wait">Getting the sites ready…</p>';
    var own = TAP.pageSites().filter(function (s) { return key(s.ref) !== key(game.planned.ref); });
    var mine = TAP.pageSites().filter(function (s) { return key(s.ref) === key(game.planned.ref); })[0];
    var fill = own.length >= 2 ? Promise.resolve([]) : southPole();
    Promise.all([fill, card(game.planned.ref)]).then(function (res) {
      game.planned.name = (mine && mine.name) || res[1].site.name;
      var seen = {}; seen[key(game.planned.ref)] = 1;
      game.pool = own.concat(res[0]).filter(function (s) { var k = key(s.ref); if (seen[k]) { return false; } seen[k] = 1; return true; });
      game.pool = game.pool.filter(function (s) { return s.name !== res[1].site.name; });
      if (game.pool.length < 2) { throw new Error('Fewer than two other sites are available.'); }
      showRound();
    }).catch(function (e) {
      ui.stage.innerHTML = '<p class="sd-wait">The game could not start: ' + esc(e.message) + '</p>';
    });
  }

  function showRound() {
    var slip = game.slips[game.round];
    var two = shuffle(game.pool).slice(0, 2);
    game.choices = shuffle([game.planned].concat(two));
    game.picked = null;
    var land = new Date(Date.parse(game.plan.landing) + slip * 86400000).toISOString().slice(0, 19) + 'Z';
    var h = '<p class="sd-round" id="sd-game-q" tabindex="-1"><b>Round ' + (game.round + 1) + ' of ' + ROUNDS + '.</b> The launch slips by <b>' + plural(slip, 'day') + '</b>. ' +
      'The lander was meant to touch down on ' + esc(dayText(game.plan.landing)) + '; now it arrives on <b>' + esc(dayText(land)) + '</b>. Where should it land?</p>' +
      '<div class="sd-choices" role="group" aria-labelledby="sd-game-q">';
    game.choices.forEach(function (c, i) {
      h += '<button type="button" class="sd-choice" data-i="' + i + '">' + esc(c.name || c.ref.id || 'site') +
        (key(c.ref) === key(game.planned.ref) ? ' <small>(the planned site)</small>' : '') + '</button>';
    });
    h += '</div><div class="sd-reveal" id="sd-game-reveal"></div>';
    ui.stage.innerHTML = h;
    Array.prototype.forEach.call(ui.stage.querySelectorAll('.sd-choice'), function (b) {
      b.addEventListener('click', function () { pick(parseInt(b.getAttribute('data-i'), 10)); });
    });
    ui.score.textContent = 'Score: ' + game.score + ' of ' + game.round + '.';
    game.choices.forEach(function (c) { card(c.ref); why(c.ref, slip); });      /* start asking now; shown after the pick */
    var q = $('sd-game-q'); if (q) { q.focus(); }
    say('Round ' + (game.round + 1) + ' of ' + ROUNDS + '. The launch slips by ' + plural(slip, 'day') + '. Pick one of three sites.');
  }

  function pick(i) {
    if (game.picked !== null) { return; }
    game.picked = i;
    var slip = game.slips[game.round];
    Array.prototype.forEach.call(ui.stage.querySelectorAll('.sd-choice'), function (b, k) {
      b.setAttribute('aria-disabled', 'true'); b.disabled = true;
      if (k === i) { b.classList.add('sd-picked'); b.setAttribute('aria-pressed', 'true'); }
    });
    var rv = $('sd-game-reveal');
    rv.innerHTML = '<p class="sd-wait">Checking all three with the real calculation…</p>';
    Promise.all(game.choices.map(function (c) {
      return Promise.all([card(c.ref), why(c.ref, slip)]).then(function (r) {
        var cd = r[0], d = cd.days[slip];
        return { c: c, card: cd, d: d, why: r[1] && r[1].day === slip ? r[1] : null };
      });
    })).then(function (res) { reveal(res, slip); }).catch(function (e) {
      rv.innerHTML = '<p class="sd-wait">The server could not answer: ' + esc(e.message) + '</p><button type="button" id="sd-game-retry">Try again</button>';
      $('sd-game-retry').addEventListener('click', function () { game.picked = null; pick(i); });
    });
  }

  function reveal(res, slip) {
    var best = Math.max.apply(null, res.map(function (r) { return RANK[r.d.verdict]; }));
    var mine = res[game.picked], good = RANK[mine.d.verdict] === best;
    if (best === 0) { game.voided += 1; } else if (good) { game.score += 1; }
    var head = best === 0 ? 'No point this round. ' : (good ? (best === 2 ? 'Good call! ' : 'Fair call. ') : 'Not this time. ');
    if (best === 0) { head += 'None of the three works after this slip, so this round does not count. A real planner would have to wait for a later date.'; }
    else if (good) { head += 'Your pick is as good as it gets this round.'; }
    else { head += 'Another site does better after this slip.'; }
    var h = '<p class="sd-result ' + (good ? 'sd-good' : 'sd-bad') + '"><b>' + esc(head) + '</b></p><ul class="sd-answers">';
    res.forEach(function (r, k) {
      var v = r.d.verdict, cls = v.replace(' ', '').replace('/', '');
      h += '<li class="sd-ans v-' + cls + (k === game.picked ? ' sd-mine' : '') + '" data-site="' + esc(key(r.c.ref)) + '" data-slip="' + slip +
        '" data-landing="' + esc(r.d.landing_utc) + '" data-verdict="' + esc(v) + '">' +
        '<span class="sd-icon" aria-hidden="true">' + ICON[v] + '</span><span class="sd-body"><b>' + esc(r.c.name || r.card.site.name) + ': ' + WORD[v] + '</b>' +
        (k === game.picked ? ' <small>(your pick)</small>' : '') + '<br>' + esc(reason(r.card, r.d, r.why)) + '</span></li>';
    });
    h += '</ul>';
    var last = game.round + 1 >= ROUNDS;
    h += '<div class="sd-row"><button type="button" class="sd-primary" id="sd-game-next">' + (last ? 'See my score' : 'Next round') + '</button></div>';
    $('sd-game-reveal').innerHTML = h;
    ui.score.textContent = 'Score: ' + game.score + ' of ' + (game.round + 1 - game.voided) + '.';
    var spoken = head + ' ' + res.map(function (r) { return (r.c.name || r.card.site.name) + ': ' + WORD[r.d.verdict] + '.'; }).join(' ');
    say(spoken);
    $('sd-game-next').addEventListener('click', function () {
      game.round += 1;
      if (game.round >= ROUNDS) { finish(); } else { showRound(); }
    });
    $('sd-game-next').focus({ preventScroll: true });
  }

  function finish() {
    var prev = parseInt(store('slipday.planner.best') || '0', 10) || 0;
    if (game.score > prev) { store('slipday.planner.best', String(game.score)); }
    var counted = ROUNDS - (game.voided || 0);
    var msg = 'You scored ' + game.score + ' of ' + counted + (game.voided ? ' (' + game.voided + ' round' + (game.voided === 1 ? '' : 's') + ' had no working site and did not count)' : '') + '. ' +
      (game.score === counted ? 'A perfect run: mission control would hire you.' :
      game.score >= 3 ? 'Well planned. The hills near the pole are hard to beat.' : 'Near the pole, a few days can change everything. Try again?');
    ui.stage.innerHTML = '<p class="sd-round" id="sd-game-end" tabindex="-1"><b>' + esc(msg) + '</b></p>' +
      '<p>Every answer you saw came from the same calculation as the main card. Each slip moves the Sun and the Earth to new places in the sky, and the hills around each site hide them at different times.</p>' +
      '<div class="sd-row"><button type="button" class="sd-primary" id="sd-game-again">Play again</button></div>';
    ui.score.textContent = 'Final score: ' + game.score + ' of ' + ROUNDS + '. Best in this browser: ' + Math.max(prev, game.score) + ' of ' + ROUNDS + '.';
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
  window.SlipdayGame = { reason: reason, state: function () { return game; } };
})();
