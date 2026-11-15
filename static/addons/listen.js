/* Slipday add-on: "Listen to the landing window", plus a screen-reader and keyboard pass on the main card.

   Include with one script tag and one container:
     <div id="addon-listen"></div>
     <script src="/static/addons/listen.js"></script>

   No library, no audio files: the sound is made in the browser with the Web Audio API.
   Data: the page's own /api/why answer for the site and date on the main card (Sun and Earth positions every hour
   from JPL DE421, the skyline ray-cast from NASA LOLA elevation data).  Nothing here is a new model.

   What it adds:
     1. a Play button that turns the landing window into sound: one tone follows the Sun's height above the
        skyline, another the Earth's; a tone goes quiet while the ground hides that body; a soft tick marks each day.
        A visible Stop button, a volume slider, and the same window as plain text (a live region and a list).
        Sound never starts by itself.
     2. at run time, on the main card (#missionOut): a short spoken summary of the answer, the slip margin and the
        next monthly windows in a polite live region; labels for the verdict, the day strip and the window buttons;
        arrow keys to move along the day strip (one Tab stop instead of sixty).
*/
(function () {
  'use strict';

  /* ---------- shared tap: what the page itself asked the server for (also in planner_game.js) ---------- */
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

  /* ---------- small helpers ---------- */
  var $ = function (id) { return document.getElementById(id); };
  var COMPASS = ['north', 'north-north-east', 'north-east', 'east-north-east', 'east', 'east-south-east', 'south-east',
    'south-south-east', 'south', 'south-south-west', 'south-west', 'west-south-west', 'west', 'west-north-west',
    'north-west', 'north-north-west'];
  var MON = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
  function compass(az) { return COMPASS[Math.round((((az % 360) + 360) % 360) / 22.5) % 16]; }
  function esc(s) {
    return String(s).replace(/[&<>"']/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]; });
  }
  function dayText(iso) {
    return parseInt(iso.slice(8, 10), 10) + ' ' + MON[parseInt(iso.slice(5, 7), 10) - 1] + ' ' + iso.slice(0, 4) +
      (iso.slice(11, 16) === '00:00' ? '' : ' at ' + iso.slice(11, 16) + ' UTC');
  }
  function deg(x) { var r = Math.round(x * 2) / 2; return (r === Math.floor(r) ? r.toFixed(0) : r.toFixed(1)) + ' degree' + (r === 1 ? '' : 's'); }
  function reducedMotion() { return !!(window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches); }
  function css() {
    if (document.querySelector('link[href*="addons/addons.css"]')) { return; }
    var l = document.createElement('link'); l.rel = 'stylesheet';
    l.href = SCRIPT_SRC ? SCRIPT_SRC.replace(/listen\.js(\?.*)?$/, 'addons.css') : '/static/addons/addons.css';
    document.head.appendChild(l);
  }
  var SCRIPT_SRC = document.currentScript && document.currentScript.src;

  /* ---------- the window, hour by hour, from an /api/why answer ---------- */
  /* w: the answer for the card's rules (Sun flags, skyline, counts).  geo: the same window with the radio-station
     rule off, so that its Earth flag means only "the Earth's centre is above the skyline". */
  function model(w, geo) {
    var t = w.track, W = Math.min(w.window_hours, t.count), sky = w.skyline;
    var mask = (w.horizon && w.horizon.mask_deg) || 0;
    var skyAt = function () { return mask; };
    if (sky && sky.az_deg && sky.az_deg.length > 1) {
      var n = sky.az_deg.length, a0 = sky.az_deg[0], step = 360 / n;
      skyAt = function (az) {
        var x = ((((az - a0) % 360) + 360) % 360) / step, i = Math.floor(x) % n, f = x - Math.floor(x);
        return sky.el_deg[i] * (1 - f) + sky.el_deg[(i + 1) % n] * f;
      };
    }
    var hours = [];
    for (var i = 0; i < W; i++) {
      hours.push({
        sunClear: t.sun_el[i] - skyAt(t.sun_az[i]), earthClear: t.earth_el[i] - skyAt(t.earth_az[i]),
        sunUp: !!t.sun_lit[i], earthUp: !!(geo || w).track.earth_up[i], sunAz: t.sun_az[i], earthAz: t.earth_az[i]
      });
    }
    return { hours: hours, W: W, days: Math.ceil(W / 24), w: w, geo: geo };
  }

  function bodyEvents(hours, h0, h1, key, azKey, name) {
    var ev = [];
    for (var h = Math.max(1, h0); h < h1; h++) {
      if (hours[h][key] !== hours[h - 1][key]) { ev.push({ up: hours[h][key], az: hours[hours[h][key] ? h : h - 1][azKey] }); }
    }
    if (!ev.length) { return { text: name + (hours[h0][key] ? ' stays up' : ' stays hidden'), changed: false }; }
    if (ev.length > 2) {
      var dips = ev.filter(function (e) { return !e.up; }).length;
      return { text: name + ' goes behind the ground to the ' + compass(ev[0].az) + ' and back again, ' + dips + ' time' + (dips === 1 ? '' : 's') +
        ', and ends the day ' + (hours[h1 - 1][key] ? 'up' : 'hidden'), changed: true };
    }
    return {
      text: ev.map(function (e, k) {
        return (k ? 'then ' : name + ' ') + (e.up ? 'rises over the ground in the ' : 'sets behind the ground to the ') + compass(e.az);
      }).join(', '), changed: true
    };
  }

  /* one plain line per day; day 1 is the landing day */
  function dayLines(m) {
    var out = [], H = m.hours;
    for (var d = 0; d < m.days; d++) {
      var h0 = d * 24, h1 = Math.min(m.W, h0 + 24), line;
      if (d === 0) {
        var a = H[0];
        line = 'Day 1, touchdown: ' + (a.sunUp ? 'Sun up, ' + deg(Math.max(0, a.sunClear)) + ' above the skyline' : 'Sun hidden behind the ground') + '. ' +
          (a.earthUp ? 'Earth up, ' + deg(Math.max(0, a.earthClear)) + ' above the skyline' : 'Earth hidden behind the ground') + '.';
        var s1 = bodyEvents(H, 1, h1, 'sunUp', 'sunAz', 'Sun'), e1 = bodyEvents(H, 1, h1, 'earthUp', 'earthAz', 'Earth');
        var later = [s1, e1].filter(function (x) { return x.changed; }).map(function (x) { return x.text; });
        if (later.length) { line += ' Later that day: ' + later.join('; ') + '.'; }
        out.push({ day: 1, text: line, changed: true, hour: 0 });
        continue;
      }
      var s = bodyEvents(H, h0, h1, 'sunUp', 'sunAz', 'Sun'), e = bodyEvents(H, h0, h1, 'earthUp', 'earthAz', 'Earth');
      if (!s.changed && !e.changed) {
        line = 'Day ' + (d + 1) + ': ' + (H[h0].sunUp ? 'Sun up' : 'Sun hidden') + ', ' + (H[h0].earthUp ? 'Earth up' : 'Earth hidden') + '.';
      } else {
        var parts = [s, e].filter(function (x) { return x.changed; }).map(function (x) { return x.text; });
        var still = [s, e].filter(function (x) { return !x.changed; }).map(function (x) { return x.text; });
        line = 'Day ' + (d + 1) + ': ' + parts.join('. ') + '.' + (still.length ? ' ' + still.join('. ') + '.' : '');
      }
      out.push({ day: d + 1, text: line, changed: s.changed || e.changed, hour: h0 });
    }
    return out;
  }

  function summary(m) {
    var sun = 0, earth = 0;
    m.hours.forEach(function (h) { sun += h.sunUp ? 1 : 0; earth += h.earthUp ? 1 : 0; });
    var w = m.w, txt = 'End of the ' + (Math.round(m.W / 24 * 10) / 10) + ' days. The Sun was up for ' + sun + ' of ' + m.W +
      ' hours. The Earth was above the skyline for ' + earth + ' of ' + m.W + ' hours.';
    if (w.criteria && w.criteria.stations && w.hours) {
      txt += ' A radio link also needs a big dish on Earth that can see the Moon; counting that, the card finds ' + w.hours.earth + ' hours of contact.';
    }
    txt += ' The card asks for ' + w.need.sunlit_h + ' sunlit hours and ' + w.need.earth_h + ' hours of contact.';
    return txt;
  }

  /* ---------- the sound ---------- */
  function pitch(clear, lo, hi) {
    var c = Math.max(0, Math.min(6, clear)) / 6;       /* 0 to 6 degrees above the skyline; higher saturates */
    return lo * Math.pow(hi / lo, c);
  }
  function makePlayer(ctx, m, volume, onEnd) {
    var W = m.W, T = Math.max(15, Math.min(30, m.days * 1.6)), dt = T / W;
    var master = ctx.createGain(); master.gain.value = volume; master.connect(ctx.destination);
    var t0 = ctx.currentTime + 0.25;
    function voice(type, key, clearKey, lo, hi, level) {
      var o = ctx.createOscillator(), g = ctx.createGain();
      o.type = type; o.connect(g); g.connect(master); g.gain.value = 0;
      var H = m.hours;
      o.frequency.setValueAtTime(pitch(H[0][clearKey], lo, hi), t0);
      g.gain.setValueAtTime(0, t0);
      for (var i = 0; i < W; i++) {
        var t = t0 + i * dt;
        o.frequency.linearRampToValueAtTime(pitch(H[i][clearKey], lo, hi), t);
        if (i === 0 || H[i][key] !== H[i - 1][key]) { g.gain.setTargetAtTime(H[i][key] ? level : 0, t, 0.03); }
      }
      g.gain.setTargetAtTime(0, t0 + W * dt, 0.05);
      o.start(t0); o.stop(t0 + W * dt + 0.4);
      return o;
    }
    var sun = voice('sine', 'sunUp', 'sunClear', 440, 1320, 0.16);
    var earth = voice('triangle', 'earthUp', 'earthClear', 147, 330, 0.22);
    /* a soft tick at the start of each day: a 25 ms burst of filtered noise */
    var len = Math.floor(ctx.sampleRate * 0.025), buf = ctx.createBuffer(1, len, ctx.sampleRate), ch = buf.getChannelData(0);
    for (var k = 0; k < len; k++) { ch[k] = (Math.random() * 2 - 1) * Math.pow(1 - k / len, 3); }
    var hp = ctx.createBiquadFilter(); hp.type = 'highpass'; hp.frequency.value = 2500;
    var tg = ctx.createGain(); tg.gain.value = 0.5; hp.connect(tg); tg.connect(master);
    var ticks = [];
    for (var d = 0; d < m.days; d++) {
      var s = ctx.createBufferSource(); s.buffer = buf; s.connect(hp); s.start(t0 + d * 24 * dt); ticks.push(s);
    }
    var ended = false;
    sun.onended = function () { if (!ended) { ended = true; onEnd(); } };
    return {
      t0: t0, dt: dt, T: T,
      hourAt: function () { return Math.floor((ctx.currentTime - t0) / dt); },
      setVolume: function (v) { master.gain.setTargetAtTime(v, ctx.currentTime, 0.05); },
      stop: function () {
        ended = true;
        [sun, earth].concat(ticks).forEach(function (n) { try { n.stop(); } catch (e) { /* already stopped */ } });
        try { master.disconnect(); } catch (e) { /* gone */ }
      }
    };
  }

  /* ---------- the panel ---------- */
  var ui = {}, current = null, playing = null;

  function render(box) {
    box.innerHTML =
      '<section class="sd-addon sd-listen" aria-labelledby="sd-listen-h">' +
      '<h2 id="sd-listen-h">Listen to the landing window</h2>' +
      '<p class="sd-lead">Hear the days after landing in about 20 seconds. The <b>high, clear tone is the Sun</b>. The <b>low, soft tone is the Earth</b>. ' +
      'The higher a tone, the higher that body stands above the skyline: the line where the ground meets the sky, seen from the landing spot. ' +
      'A tone goes quiet while the ground hides it. A soft tick marks each new day. Sound only starts when you press Play.</p>' +
      '<p class="sd-what" id="sd-listen-what">Site and date: the ones on the main card above.</p>' +
      '<div class="sd-row">' +
      '<button type="button" id="sd-listen-play" class="sd-primary">Play the sound</button>' +
      '<button type="button" id="sd-listen-stop">Stop</button>' +
      '<label class="sd-vol" for="sd-listen-vol">Volume <input type="range" id="sd-listen-vol" min="0" max="100" step="5" value="50" aria-valuetext="50 percent"></label>' +
      '<button type="button" id="sd-listen-text">Read it as text</button>' +
      '</div>' +
      '<p class="sd-now" id="sd-listen-now" role="status" aria-live="polite" aria-atomic="true">Press Play to hear the window, or Read it as text.</p>' +
      '<div class="sd-strip" id="sd-listen-strip" aria-hidden="true"></div>' +
      '<details class="sd-more" id="sd-listen-more"><summary>Day by day, in words</summary><ol class="sd-list" id="sd-listen-list"><li>Not loaded yet.</li></ol></details>' +
      '<div class="sd-row sd-help" role="group" aria-label="Screen reader help for the main card">' +
      '<button type="button" id="sd-a11y-jump">Go to the answer on the main card</button>' +
      '<button type="button" id="sd-a11y-say">Say the answer again</button>' +
      '</div>' +
      '<p class="sd-note">Made from the same numbers as the skyline view on the card: Sun and Earth positions every hour (JPL DE421) and the skyline ray-cast from NASA LOLA elevation data. ' +
      'One degree is about the width of your little finger held at arm\'s length. The Earth tone follows only the ground; the card also asks that a big radio dish on Earth can see the Moon. ' +
      'Press Escape to stop the sound.</p>' +
      '</section>';
    ['play', 'stop', 'vol', 'text', 'now', 'strip', 'list', 'what', 'more'].forEach(function (k) { ui[k] = $('sd-listen-' + k); });
    ui.play.addEventListener('click', play);
    ui.stop.addEventListener('click', function () { stop(true); });
    ui.text.addEventListener('click', readText);
    ui.vol.addEventListener('input', function () {
      ui.vol.setAttribute('aria-valuetext', ui.vol.value + ' percent');
      if (playing) { playing.player.setVolume(vol()); }
    });
    box.addEventListener('keydown', function (e) { if (e.key === 'Escape' && playing) { stop(true); e.preventDefault(); } });
    $('sd-a11y-jump').addEventListener('click', jumpToAnswer);
    $('sd-a11y-say').addEventListener('click', function () { announce(cardSummary() || 'The main card has no answer yet.', true); });
    describePlan();
  }
  function vol() { var v = parseInt(ui.vol.value, 10) / 100; return v * v; }
  function say(text) { ui.now.textContent = text; }

  /* says which window the sound is for: the one loaded when there is one for the current plan, else the page's */
  function describePlan() {
    if (!ui.what) { return; }
    var key = JSON.stringify(TAP.plan()), lw = TAP.lastWhy();
    var w = current && current.key === key ? current.w : (lw && JSON.stringify(lw.body) === key ? lw.resp : null);
    if (!w) { ui.what.textContent = 'Site and date: the ones on the main card above (still loading).'; return; }
    ui.what.textContent = 'Now set to: ' + w.site.name + ', landing ' + dayText(w.landing_utc) +
      (w.day ? ' (after a slip of ' + w.day + ' day' + (w.day === 1 ? '' : 's') + ')' : '') +
      ', the first ' + w.window_days + ' days. Pick another site, date or day of slip on the main card to change it.';
  }

  /* the window to play: the page's own /api/why answer when it is for the current plan, and the same window with
     the radio-station rule off for the Earth tone */
  function load() {
    var p = TAP.plan(), lw = TAP.lastWhy();
    var first = (lw && JSON.stringify(lw.body) === JSON.stringify(p)) ? Promise.resolve(lw.resp) : TAP.api('/api/why', p);
    return first.then(function (w) {
      if (!(w.criteria && w.criteria.stations)) { return model(w, null); }
      var q = JSON.parse(JSON.stringify(p)); q.earth_stations = false;
      return TAP.api('/api/why', q).then(function (g) { return model(w, g); });
    }).then(function (m) {
      m.lines = dayLines(m); m.summary = summary(m); m.key = JSON.stringify(p);
      current = m; fillList(m); drawStrip(m); describePlan(); return m;
    });
  }
  function ready() {
    var key = JSON.stringify(TAP.plan());
    return current && current.key === key ? Promise.resolve(current) : load();
  }
  function fillList(m) {
    ui.list.innerHTML = m.lines.map(function (l) { return '<li>' + esc(l.text) + '</li>'; }).join('') + '<li>' + esc(m.summary) + '</li>';
  }
  function drawStrip(m) {
    var h = '<div class="sd-stripRow"><span class="sd-k">Sun</span>';
    var cells = function (key) {
      var s = '';
      for (var d = 0; d < m.days; d++) {
        var up = 0, n = 0;
        for (var i = d * 24; i < Math.min(m.W, d * 24 + 24); i++) { up += m.hours[i][key] ? 1 : 0; n++; }
        s += '<i class="sd-c" data-day="' + (d + 1) + '" style="--f:' + (up / n).toFixed(2) + '"></i>';
      }
      return s;
    };
    h += '<span class="sd-cells sd-sun">' + cells('sunUp') + '</span></div><div class="sd-stripRow"><span class="sd-k">Earth</span><span class="sd-cells sd-earth">' + cells('earthUp') + '</span></div>' +
      '<div class="sd-stripAxis"><span>day 1</span><span>filled: share of the day the body is up</span><span>day ' + m.days + '</span></div>';
    ui.strip.innerHTML = h;
  }
  function markDay(d) {
    Array.prototype.forEach.call(ui.strip.querySelectorAll('.sd-c'), function (c) { c.classList.toggle('sd-on', +c.getAttribute('data-day') === d); });
  }

  function play() {
    if (playing) { say('It is already playing. Press Stop or Escape to stop it.'); return; }
    var AC = window.AudioContext || window.webkitAudioContext;
    if (!AC) { say('This browser cannot make sound. Use Read it as text instead.'); readText(); return; }
    var ctx = new AC();                       /* made inside the click, so the browser allows sound */
    var token = {}; playing = { ctx: ctx, token: token, player: null, timer: null };
    ui.play.setAttribute('aria-pressed', 'true');
    say('Getting the Sun and Earth positions for this window…');
    ready().then(function (m) {
      if (!playing || playing.token !== token) { return; }
      var startPlay = function () {
        var lastDay = 0;
        var player = makePlayer(ctx, m, vol(), function () { finish(token, m); });
        playing.player = player;
        playing.timer = setInterval(function () {
          var h = player.hourAt();
          if (h < 0 || h >= m.W) { return; }
          var d = Math.floor(h / 24) + 1;
          if (d !== lastDay) { lastDay = d; say(m.lines[d - 1].text); markDay(d); }
        }, reducedMotion() ? 200 : 100);
      };
      if (ctx.state === 'suspended') { ctx.resume().then(startPlay, startPlay); } else { startPlay(); }
    }).catch(function (e) {
      say('Could not get the window: ' + e.message);
      cleanup();
    });
  }
  function finish(token, m) {
    if (!playing || playing.token !== token) { return; }
    cleanup();
    say(m.summary);
  }
  function cleanup() {
    if (!playing) { return; }
    clearInterval(playing.timer);
    if (playing.player) { playing.player.stop(); }
    try { playing.ctx.close(); } catch (e) { /* closed */ }
    playing = null;
    if (ui.play) { ui.play.setAttribute('aria-pressed', 'false'); }
    markDay(0);
  }
  function stop(byUser) {
    if (!playing) { if (byUser) { say('Nothing is playing.'); } return; }
    var h = playing.player ? playing.player.hourAt() : -1;
    cleanup();
    if (byUser) { say('Stopped' + (h >= 0 ? ' on day ' + (Math.floor(h / 24) + 1) : '') + '.'); }
  }
  function readText() {
    say('Getting the window as text…');
    ready().then(function (m) {
      ui.more.open = true;
      var changes = m.lines.filter(function (l) { return l.changed; }).map(function (l) { return l.text; });
      say(changes.join(' ') + ' ' + m.summary + ' Every day is listed below, under Day by day.');
    }).catch(function (e) { say('Could not get the window: ' + e.message); });
  }

  /* ---------- the main card: labels, live summary, keyboard ---------- */
  var announcer = null, lastCard = '', lastWin = '';
  function announce(text, force) {
    if (!announcer) {
      announcer = document.createElement('div');
      announcer.id = 'sd-a11y-status'; announcer.className = 'sd-sr';
      announcer.setAttribute('role', 'status'); announcer.setAttribute('aria-live', 'polite'); announcer.setAttribute('aria-atomic', 'true');
      document.body.appendChild(announcer);
    }
    announcer.textContent = '';
    setTimeout(function () { announcer.textContent = text; }, force ? 60 : 30);
  }
  function plain(node) { return node ? node.textContent.replace(/\s+/g, ' ').trim() : ''; }
  function cardSummary() {
    var box = $('missionOut'), v = box && box.querySelector('.verdict');
    if (!v) { return ''; }
    var sel = $('mSite'), site = sel && sel.selectedIndex >= 0 ? plain(sel.options[sel.selectedIndex]) : '';
    var date = $('start') ? $('start').value : '', hour = $('mHour') ? $('mHour').value : '';
    var word = plain(v.querySelector('.vWord')), sub = plain(v.querySelector('.vSub'));
    var txt = 'Answer' + (site ? ' for ' + site : '') + (date ? ', landing ' + date + (hour !== '' ? ' at ' + ('0' + hour).slice(-2) + ':00 UTC' : '') : '') + ': ' + word + '. ' +
      (sub ? sub.charAt(0).toUpperCase() + sub.slice(1) + '.' : '');
    var fine = $('fineNote');
    if (fine) { txt += ' ' + plain(fine); }
    var w = windowsSummary();
    if (w) { txt += ' ' + w; }
    return txt;
  }
  function winLabel(b) {
    var t = (b.getAttribute('title') || '').split(';')[0].replace(/^Landing /, 'Landing on ');
    return t || plain(b);
  }
  function windowsSummary() {
    var bs = document.querySelectorAll('#winLine button[data-win]');
    if (!bs.length) { return ''; }
    return 'Next monthly launch windows: ' + Array.prototype.map.call(bs, winLabel).join('. ') + '.';
  }
  function labelCard() {
    var box = $('missionOut');
    var v = box.querySelector('.verdict');
    if (v) {
      v.setAttribute('tabindex', '-1');
      v.setAttribute('role', 'group');
      v.setAttribute('aria-label', 'The answer: ' + plain(v.querySelector('.vWord')) + ', ' + plain(v.querySelector('.vSub')));
    }
    var strip = $('vstrip');
    if (strip && !strip.getAttribute('data-sd')) {
      strip.setAttribute('data-sd', '1');
      strip.setAttribute('role', 'group');
      strip.setAttribute('aria-label', 'The answer for each day of slip, from the planned date onwards. Use the left and right arrow keys to move, Enter to see why.');
      var cells = strip.querySelectorAll('button');
      var on = strip.querySelector('button.sel') || cells[0];
      Array.prototype.forEach.call(cells, function (c) { c.setAttribute('tabindex', c === on ? '0' : '-1'); });
      strip.addEventListener('keydown', function (e) {
        var list = Array.prototype.slice.call(strip.querySelectorAll('button'));
        var i = list.indexOf(document.activeElement), j = i;
        if (i < 0) { return; }
        if (e.key === 'ArrowRight' || e.key === 'ArrowDown') { j = Math.min(list.length - 1, i + 1); }
        else if (e.key === 'ArrowLeft' || e.key === 'ArrowUp') { j = Math.max(0, i - 1); }
        else if (e.key === 'Home') { j = 0; } else if (e.key === 'End') { j = list.length - 1; } else { return; }
        e.preventDefault();
        list[i].setAttribute('tabindex', '-1'); list[j].setAttribute('tabindex', '0'); list[j].focus();
      });
    }
    Array.prototype.forEach.call(box.querySelectorAll('#winLine button[data-win]'), function (b) { b.setAttribute('aria-label', winLabel(b) + '. Press to make it the plan.'); });
    Array.prototype.forEach.call(box.querySelectorAll('button[data-plan]'), function (b) {
      b.setAttribute('aria-label', 'Make ' + plain(b) + ' the planned landing date');
    });
  }
  function cardChanged() {
    var box = $('missionOut');
    if (!box) { return; }
    labelCard();
    var v = box.querySelector('.verdict');
    if (!v) { return; }
    var sum = cardSummary(), base = sum.replace(/ Next monthly launch windows:.*$/, ''), win = windowsSummary();
    if (base !== lastCard) { lastCard = base; lastWin = win; announce(sum); }
    else if (win && win !== lastWin) { lastWin = win; announce(win); }
  }
  function jumpToAnswer() {
    var v = document.querySelector('#missionOut .verdict');
    if (!v) { announce('The main card has no answer yet.', true); return; }
    labelCard();
    v.focus();
    if (v.scrollIntoView) { v.scrollIntoView({ block: 'center', behavior: reducedMotion() ? 'auto' : 'smooth' }); }
  }
  function cardPass() {
    var box = $('missionOut');
    if (!box || box.getAttribute('data-sd')) { return; }
    box.setAttribute('data-sd', '1');
    /* the card replaces all of its HTML at each update; read out as a whole it is a long list of buttons.
       A short summary goes to our own live region instead. */
    box.setAttribute('aria-live', 'off');
    var t = null;
    new MutationObserver(function () { clearTimeout(t); t = setTimeout(cardChanged, 400); }).observe(box, { childList: true, subtree: true });
    cardChanged();
  }

  function init() {
    css();
    var box = $('addon-listen');
    if (box) { render(box); }
    cardPass();
    TAP.onChange(function (path) {
      if (path === '/api/why') {
        describePlan();
        if (current && current.key !== JSON.stringify(TAP.plan()) && ui.list) {
          ui.list.innerHTML = '<li>The main card changed. Press Play or Read it as text to load the new window.</li>';
          ui.strip.innerHTML = '';
        }
      }
      if (!$('missionOut') || !$('missionOut').getAttribute('data-sd')) { cardPass(); }
    });
  }
  if (document.readyState === 'loading') { document.addEventListener('DOMContentLoaded', init); } else { init(); }

  window.SlipdayListen = { model: model, dayLines: dayLines, summary: summary, ready: ready, stop: function () { stop(false); }, src: SCRIPT_SRC };
})();
