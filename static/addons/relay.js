/* Slipday add-on: "Relay satellites: contact when the Earth is hidden"

   Include with one container and one script tag:
     <div id="addon-relay"></div>                       (next to the Deep Space Network panel, #contactPanel)
     <script src="/static/addons/relay.js"></script>    (after /static/app.js)

   What it shows, for the site and landing on the card (the opening example until the card loads):
     - one plain sentence: contact hours with relays of NASA's reference design, against the Earth alone;
     - the 14-day window as 14 rows of 24 hours, each hour coloured Earth only / relay only / both / none;
     - the slip margin of the stated point with the Earth alone and if contact through a relay counted;
     - the source label, and what it cannot tell.
   The card's own verdict is never changed.

   It reads nothing private from app.js.  It watches the page's own requests to /api/mission (the answer is
   cloned, never changed) and asks:  GET /api/addons/relay/window?lat=&lon=&name=&landing=&stations=
   No library.  Works at phone width.  Styles are injected and scoped to #addon-relay.
*/
(function () {
  'use strict';
  var ROOT_ID = 'addon-relay';
  var DEFAULT = { lat: -89.0098, lon: 122.76389, name: 'Slip-robust ridge point (89.010 S, 122.764 E)',
                  landing: '2026-11-18T00:00:00Z', stations: true };
  var state = { want: null, key: '', data: null, view: 'two', busy: false };
  var root = null;

  function esc(s) {
    return String(s).replace(/[&<>"']/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
    });
  }
  function days(n) { return n + ' day' + (n === 1 ? '' : 's'); }
  var MON = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
  function day(isoUtc) {
    var d = parseInt(isoUtc.slice(8, 10), 10) + ' ' + MON[parseInt(isoUtc.slice(5, 7), 10) - 1] + ' ' + isoUtc.slice(0, 4);
    return /T00:00:00Z$/.test(isoUtc) ? d : d + ' ' + isoUtc.slice(11, 16) + ' UTC';
  }

  function css() {
    if (document.getElementById('sd-relay-style')) { return; }
    var s = document.createElement('style');
    s.id = 'sd-relay-style';
    s.textContent = [
      '#addon-relay{--r-none:#d03b3b;--r-earth:var(--earth,#2a78d6);--r-relay:#1f9e89;--r-both:#6a4fc0;}',
      '@media (prefers-color-scheme: dark){#addon-relay{--r-none:#e06666;--r-relay:#3cbfa8;--r-both:#9d86e8;}}',
      '#addon-relay,#addon-relay *{box-sizing:border-box;}',
      '#addon-relay .rl-box{max-width:100%;overflow-wrap:anywhere;}',
      '#addon-relay .rl-box{background:var(--surface,#fcfcfb);color:var(--text,#0b0b0b);border:1px solid var(--line,#dddbd3);',
      'border-radius:10px;padding:16px;margin-bottom:16px;}',
      '#addon-relay h2{font-size:17px;margin:0 0 8px;}',
      '#addon-relay p{margin:0 0 8px;max-width:78ch;}',
      '#addon-relay .rl-what{color:var(--text2,#52514e);font-size:14px;}',
      '#addon-relay .rl-lead{font-size:16px;font-weight:600;padding:8px 10px;border-left:4px solid var(--accent,#0e3f7e);',
      'background:var(--ok-bg,#e3eefb);color:var(--ok-ink,#0e3f7e);}',
      '#addon-relay .rl-row{display:flex;flex-wrap:wrap;gap:8px;align-items:center;margin:8px 0;}',
      '#addon-relay button{font:inherit;font-weight:600;color:var(--text,#0b0b0b);background:var(--surface,#fcfcfb);',
      'border:1px solid var(--line,#dddbd3);border-radius:6px;padding:8px 12px;min-height:44px;cursor:pointer;}',
      '#addon-relay button[aria-pressed="true"]{background:var(--accent,#0e3f7e);border-color:var(--accent,#0e3f7e);color:var(--surface,#fff);}',
      '#addon-relay button:focus-visible{outline:3px solid var(--accent,#0e3f7e);outline-offset:2px;}',
      '#addon-relay .rl-grid{display:grid;grid-template-columns:3.2em repeat(24,minmax(0,1fr));gap:1px;max-width:720px;margin:6px 0;}',
      '#addon-relay .rl-d{font-size: 12px;color:var(--text2,#52514e);line-height:14px;}',
      '#addon-relay .rl-c{height:14px;border-radius:1px;}',
      '#addon-relay .rl-c0{background:var(--r-none);}',
      '#addon-relay .rl-c1{background:var(--r-earth);}',
      '#addon-relay .rl-c2{background:var(--r-relay);}',
      '#addon-relay .rl-c3{background:var(--r-both);}',
      '#addon-relay .rl-axis{display:grid;grid-template-columns:3.2em 1fr 1fr;max-width:720px;font-size: 12px;color:var(--muted,#7b7a74);}',
      '#addon-relay .rl-axis span:last-child{text-align:right;}',
      '#addon-relay .rl-key{display:flex;flex-wrap:wrap;gap:6px 14px;font-size:13px;margin:6px 0;padding:0;list-style:none;}',
      '#addon-relay .rl-key i{display:inline-block;width:12px;height:12px;border-radius:2px;margin-right:5px;vertical-align:-1px;}',
      '#addon-relay .rl-note{color:var(--muted,#7b7a74);font-size:12.5px;}',
      '#addon-relay details summary{cursor:pointer;font-weight:600;padding:6px 0;}',
      '#addon-relay ul.rl-list{margin:4px 0 0;padding-left:1.4em;font-size:14px;max-width:80ch;}',
      '#addon-relay ul.rl-list li{margin:3px 0;}',
      '#addon-relay a{color:var(--accent,#0e3f7e);}'
    ].join('');
    document.head.appendChild(s);
  }

  /* ---------- watch the card's own request ---------- */
  if (window.fetch) {
    var orig = window.fetch.bind(window);
    window.fetch = function (input, init) {
      var p = orig(input, init);
      try {
        var url = typeof input === 'string' ? input : (input && input.url) || '';
        var bare = url.replace(/^[a-z]+:\/\/[^/]+/i, '').split('?')[0];
        var mine = init && init.headers && init.headers['X-Slipday-Addon'];
        if (!mine && bare === '/api/mission') {
          var body = init && typeof init.body === 'string' ? JSON.parse(init.body) : null;
          p.then(function (r) {
            if (!r.ok) { return; }
            r.clone().json().then(function (j) {
              if (!j || !j.site || typeof j.site.lat !== 'number') { return; }
              var m = { lat: j.site.lat, lon: j.site.lon, name: j.site.name || '',
                        landing: j.landing_utc || (body && body.landing) || DEFAULT.landing,
                        stations: body && body.earth_stations === false ? false : true };
              seen = seen.filter(function (x) { return x.name !== m.name; });
              seen.push(m);
              follow();
            }).catch(function () {});
          }).catch(function () {});
        }
      } catch (e) { /* never get in the page's way */ }
      return p;
    };
  }

  /* The card asks for one mission per chosen site and shows the one picked in its site menu (#mSite). */
  var seen = [];
  function follow() {
    var sel = document.getElementById('mSite');
    var name = sel && sel.selectedIndex >= 0 && sel.options[sel.selectedIndex] ? sel.options[sel.selectedIndex].text : null;
    var hit = null;
    seen.forEach(function (m) { if (name !== null && m.name === name) { hit = m; } });
    if (!hit && name === null && seen.length) { hit = seen[seen.length - 1]; }
    if (hit) { want(hit); }
  }
  document.addEventListener('change', function (ev) {
    if (ev.target && ev.target.id === 'mSite') { setTimeout(follow, 0); }
  });

  function want(w) {
    state.want = w;
    var key = [w.lat, w.lon, w.landing, w.stations].join('|');
    if (key === state.key) { return; }
    state.key = key;
    load(key);
  }

  function load(key) {
    var w = state.want;
    if (!root) { return; }
    state.busy = true;
    render();
    var q = '/api/addons/relay/window?lat=' + encodeURIComponent(w.lat) + '&lon=' + encodeURIComponent(w.lon) +
      '&name=' + encodeURIComponent(w.name) + '&landing=' + encodeURIComponent(w.landing) +
      '&stations=' + (w.stations ? 'true' : 'false');
    fetch(q, { headers: { 'X-Slipday-Addon': '1' } }).then(function (r) {
      return r.json().then(function (j) { return { ok: r.ok, j: j }; });
    }).then(function (res) {
      if (key !== state.key) { return; }
      state.busy = false;
      state.data = res.ok ? res.j : { error: (res.j && res.j.detail) || 'The relay check failed.' };
      render();
    }).catch(function () {
      if (key !== state.key) { return; }
      state.busy = false;
      state.data = { error: 'The relay check could not reach the server.' };
      render();
    });
  }

  /* ---------- drawing ---------- */
  function strip(code) {
    var h = ['<div class="rl-grid" role="img" aria-label="' + esc(stripText(code)) + '">'];
    for (var d = 0; d < Math.ceil(code.length / 24); d++) {
      h.push('<span class="rl-d">day ' + (d + 1) + '</span>');
      for (var k = 0; k < 24; k++) {
        var i = d * 24 + k;
        h.push(i < code.length ? '<span class="rl-c rl-c' + code[i] + '"></span>' : '<span></span>');
      }
    }
    h.push('</div><div class="rl-axis" aria-hidden="true"><span></span><span>hour 0</span><span>hour 23</span></div>');
    return h.join('');
  }
  function stripText(code) {
    var n = [0, 0, 0, 0];
    code.forEach(function (c) { n[c]++; });
    return 'Hours of the landing window: ' + n[3] + ' with the Earth and a relay, ' + n[1] + ' with the Earth only, ' +
      n[2] + ' with a relay only, ' + n[0] + ' with neither.';
  }
  function key(h) {
    return '<ul class="rl-key">' +
      '<li><i class="rl-c3"></i>Earth and relay: ' + h.both + ' h</li>' +
      '<li><i class="rl-c1"></i>Earth only: ' + h.earth_only + ' h</li>' +
      '<li><i class="rl-c2"></i>relay only: ' + h.relay_only + ' h</li>' +
      '<li><i class="rl-c0"></i>neither: ' + h.none + ' h</li></ul>';
  }
  function range(r, unit) {
    return r.lowest === r.highest ? r.lowest + unit + ' in every run' : 'from ' + r.lowest + ' to ' + r.highest + unit;
  }

  function spreadNote(two) {
    var s = two.spread && two.spread.either_h;
    if (!s) { return ''; }
    return s.lowest === s.highest ? 'At this site, two relays give the same count from every starting position tried.'
      : 'At this site, two relays give from ' + s.lowest + ' to ' + s.highest + ' hours, depending on where they start.';
  }

  function render() {
    if (!root) { return; }
    var d = state.data, w = state.want || DEFAULT;
    var h = ['<section class="rl-box" aria-labelledby="rl-h">',
      '<h2 id="rl-h">Relay satellites: contact when the Earth is hidden</h2>',
      '<p class="rl-what">A relay is a satellite circling the Moon that passes messages between a lander and Earth. ',
      'When the Earth is behind the skyline, a relay above the skyline could still carry the link. ',
      'This counts the hours each would give at the site on the card. It does not change the card\'s answer.</p>'];
    if (state.busy && !d) {
      h.push('<p aria-live="polite">Working out where the relays are, hour by hour…</p>');
    } else if (d && d.error) {
      h.push('<p aria-live="polite">' + esc(d.error) + '</p>');
    } else if (d) {
      var two = d, one = d.one_relay || null;
      var cur = state.view === 'one' && one ? one : two;
      var n = two.window_hours, hE = two.hours.earth;
      var lead = (state.view === 'one' && one ? 'With one relay' : 'With two relays') + ' of this design, contact covers ' +
        cur.hours.either + ' of ' + n + ' hours instead of ' + hE + ' with the Earth alone.';
      h.push('<p class="rl-what">' + esc(two.site.name) + ', landing ' + esc(day(two.landing_utc)) + ', the ' +
        Math.round(n / 24) + ' days after touchdown.' + (state.busy ? ' Updating…' : '') + '</p>');
      h.push('<p class="rl-lead" aria-live="polite">' + esc(lead) + '</p>');
      if (one) {
        h.push('<div class="rl-row" role="group" aria-label="How many relays">' +
          '<button type="button" data-v="two" aria-pressed="' + (state.view !== 'one') + '">Two relays</button>' +
          '<button type="button" data-v="one" aria-pressed="' + (state.view === 'one') + '">One relay</button></div>');
      }
      h.push(strip(cur.code), key(cur.hours));

      var sl = two.slip, osl = one ? one.slip : null;
      var mE = sl.margin_earth_days, mX = (state.view === 'one' && osl) ? osl.margin_either_days : sl.margin_either_days;
      var why = (state.view === 'one' && osl) ? osl.either_ends_because : sl.either_ends_because;
      var cap = sl.days_checked - 1;
      var txt = 'Slip margin at the stated point: ' + (mE < 0 ? 'none' : days(mE)) + ' with the Earth alone';
      txt += mX >= cap ? '; at least ' + days(cap) + ' if contact through a relay also counted (every day checked holds).'
        : '; ' + (mX < 0 ? 'none' : days(mX)) + ' if contact through a relay also counted' +
          (why && why.length ? ' (then: ' + why.join('; ') + ').' : '.');
      h.push('<p>' + esc(txt) + '</p>');
      var sp = state.view === 'one' && one ? one.spread : two.spread;
      if (sp) {
        h.push('<p class="rl-what">Where a relay is at a given hour cannot be predicted from this model (see below). ' +
          'Started from 144 other positions, ' + (state.view === 'one' ? 'one relay gives ' : 'two relays give ') +
          esc(range(sp.either_h, ' hours of contact')) + ', and a slip margin of ' +
          esc(range(sp.margin_either_days, ' days')) + '.</p>');
      }
      h.push('<p class="rl-note">The need is the card\'s default: ' + esc(sl.rule) +
        '. The 100 hours of contact are an illustrative figure. The card\'s own margin needs 13 touchdown points ' +
        'and two terrain grids to agree; this line uses the stated point only, for both counts. ' +
        (two.stations ? 'Both paths also need a Deep Space Network station with the Moon in view, as on the card.' :
          'No ground-station rule is applied, as on the card with that box unticked.') + '</p>');
      h.push('<p class="rl-note"><strong>Source:</strong> ' + esc(two.label) +
        '. <a href="https://ntrs.nasa.gov/citations/20250002698" target="_blank" rel="noopener">NASA NTRS 20250002698</a>.</p>');
      h.push('<details><summary>What this cannot tell</summary><ul class="rl-list">',
        '<li>No relay is in service. NASA says this design "is not final"; the company building the service makes the final choice.</li>',
        '<li>Here the relays move on fixed ovals, as if the Moon pulled the same way everywhere and nothing else pulled at all. The real orbits are bent by the Moon\'s uneven gravity, ',
        'the Earth and the Sun; NASA\'s document says a full model is needed to keep them as designed. So the hour-by-hour colours show ',
        'the kind of coverage, not a timetable. ' + spreadNote(two) + '</li>',
        '<li>"In view" means above the skyline. It says nothing about radio power, antennas, data rates or who may use the relay.</li>',
        '<li>The slip margin with relays assumes a lander could talk through the relay. Many landers cannot.</li></ul></details>');
    }
    h.push('</section>');
    root.innerHTML = h.join('');
    var btns = root.querySelectorAll('button[data-v]');
    for (var i = 0; i < btns.length; i++) {
      btns[i].addEventListener('click', function (ev) {
        state.view = ev.currentTarget.getAttribute('data-v');
        render();
        var b = root.querySelector('button[data-v="' + state.view + '"]');
        if (b) { b.focus(); }
      });
    }
  }

  function start() {
    root = document.getElementById(ROOT_ID);
    if (!root) { return; }
    css();
    if (state.want) { state.key = ''; want(state.want); } else { want(DEFAULT); }
  }
  if (document.readyState === 'loading') { document.addEventListener('DOMContentLoaded', start); } else { start(); }
})();
