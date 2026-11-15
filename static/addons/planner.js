/* Slipday add-on: planner checks
   Include with one container and one script tag:
     <div id="addon-planner"></div>
     <script src="/static/addons/planner.js"></script>    (after /static/app.js)
   For the site on the card it shows: the Sun at touchdown and where it sits relative to the approach, the share of
   the landing spread in shadow, the joint chance (plan holds AND ground flat enough) per lander class, and, for a
   slip of N days, the other south-pole sites judged at the slipped date itself.
   It watches the page's own /api/mission answers (cloned, never changed) and asks GET /api/addons/planner/*.
   No library.  Styled with the page's CSS variables.  Works at phone width. */
(function () {
  'use strict';
  var site = null, landing = '2026-11-18T00:00:00Z', box = null, seq = 0;
  function esc(s) { return String(s).replace(/[&<>"']/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]; }); }
  function pct(x) { return x === null || x === undefined ? '–' : (x >= 99.5 || x < 1 ? x.toFixed(1) : Math.round(x)) + ' %'; }
  function day(iso) { return iso ? iso.slice(0, 10) + (iso.slice(11, 16) !== '00:00' ? ' ' + iso.slice(11, 16) + ' UTC' : '') : ''; }

  if (window.fetch) {
    var orig = window.fetch.bind(window);
    window.fetch = function (input, init) {
      var p = orig(input, init);
      try {
        var url = typeof input === 'string' ? input : (input && input.url) || '';
        if (url.replace(/^[a-z]+:\/\/[^/]+/i, '').split('?')[0] === '/api/mission') {
          p.then(function (r) {
            if (!r.ok) { return; }
            r.clone().json().then(function (j) {
              if (!j || !j.site) { return; }
              site = j.site; landing = j.landing_utc || landing; run();
            }).catch(function () {});
          }).catch(function () {});
        }
      } catch (e) { /* never get in the page's way */ }
      return p;
    };
  }

  var CSS = '#addon-planner{color:var(--text);font-size:14px;line-height:1.45;max-width:100%}' +
    '#addon-planner .pl-card{border:1px solid var(--line);background:var(--surface);border-radius:8px;padding:12px;margin:10px 0}' +
    '#addon-planner h4{margin:0 0 6px;font-size:15px}#addon-planner .pl-m{color:var(--muted);font-size:12.5px}' +
    '#addon-planner .pl-row{display:flex;flex-wrap:wrap;gap:10px;align-items:center;margin:6px 0}' +
    '#addon-planner input{width:5.5em;padding:3px 5px;border:1px solid var(--line);background:var(--surface);color:var(--text);border-radius:4px}' +
    '#addon-planner table{border-collapse:collapse;width:100%;font-size:13px}#addon-planner .pl-scroll{overflow-x:auto}' +
    '#addon-planner th,#addon-planner td{border-bottom:1px solid var(--line);padding:4px 6px;text-align:left;white-space:nowrap}' +
    '#addon-planner .pl-yes{color:var(--ok-ink);background:var(--ok-bg);padding:0 4px;border-radius:3px}' +
    '#addon-planner .pl-tag{font-size:11px;border:1px solid var(--line);border-radius:3px;padding:0 4px;color:var(--muted)}' +
    '#addon-planner button{border:1px solid var(--accent);color:var(--accent);background:var(--surface);border-radius:4px;padding:3px 9px;cursor:pointer}';

  function init() {
    box = document.getElementById('addon-planner');
    if (!box || box.dataset.ready) { return; }
    box.dataset.ready = '1';
    var st = document.createElement('style'); st.textContent = CSS; document.head.appendChild(st);
    box.innerHTML = '<div class="pl-card"><h4>Planner checks</h4>' +
      '<div class="pl-row"><label>Approach from (degrees, 0 = north) <input id="pl-head" type="number" min="0" max="360" step="5" value="0"></label>' +
      '<label>Launch slipped by (days) <input id="pl-slip" type="number" min="0" max="120" step="1" value="0"></label>' +
      '<button id="pl-go" type="button">Check</button></div>' +
      '<div class="pl-m">The approach heading and the camera lighting limits are illustrative assumptions, not published figures.</div></div>' +
      '<div id="pl-light" class="pl-card"></div><div id="pl-joint" class="pl-card"></div><div id="pl-alt" class="pl-card"></div>';
    document.getElementById('pl-go').addEventListener('click', run);
    if (!site) { site = { name: 'Opening example (89.010 S, 122.764 E)', lat: -89.0098, lon: 122.76389 }; }
    run();
  }

  function get(path, q) {
    var s = Object.keys(q).map(function (k) { return k + '=' + encodeURIComponent(q[k]); }).join('&');
    return fetch(path + '?' + s, { headers: { 'X-Slipday-Addon': 'planner' } }).then(function (r) {
      if (!r.ok) { throw new Error('the server answered ' + r.status); } return r.json();
    });
  }
  function fail(el) { return function (e) { el.innerHTML = '<span class="pl-m">Not available: ' + esc(e.message) + '</span>'; }; }

  function run() {
    if (!box || !site) { return; }
    var my = ++seq;
    var head = Math.max(0, Math.min(360, +document.getElementById('pl-head').value || 0));
    var slip = Math.max(0, Math.min(120, Math.round(+document.getElementById('pl-slip').value || 0)));
    var q = { lat: site.lat, lon: site.lon, name: site.name || '', landing: landing, slip_days: slip };
    var L = document.getElementById('pl-light'), J = document.getElementById('pl-joint'), A = document.getElementById('pl-alt');
    L.innerHTML = J.innerHTML = '<span class="pl-m">Working…</span>';
    A.innerHTML = '<span class="pl-m">' + (slip ? 'Checking the other sites at the slipped date (about 20 s)…' : 'Enter a slip in days to check the other sites at the slipped date.') + '</span>';
    get('/api/addons/planner/lighting', Object.assign({ heading_from_deg: head }, q)).then(function (r) { if (my === seq) { light(L, r); } }).catch(fail(L));
    get('/api/addons/planner/joint', q).then(function (r) { if (my === seq) { joint(J, r); } }).catch(fail(J));
    if (slip) {
      get('/api/addons/planner/alternatives', { landing: landing, slip_days: slip, lat: site.lat, lon: site.lon }).then(function (r) { if (my === seq) { alts(A, r); } }).catch(fail(A));
    }
  }

  function light(el, r) {
    var s = r.sun, a = r.approach, h = '<h4>Descent lighting at touchdown <span class="pl-tag">illustrative limits</span></h4>' +
      '<div class="pl-row"><b>Sun ' + s.el_deg.toFixed(2) + '° up, azimuth ' + s.az_deg.toFixed(1) + '°</b>' +
      '<span>' + (s.above_skyline ? 'clears the local skyline' : 'hidden by the local skyline') + '</span>' +
      '<span>' + Math.round(a.sun_from_behind_deg) + '° from straight behind: <b>' + esc(a.sun_side) + '</b></span>' +
      '<span>' + (r.camera.good ? '<span class="pl-yes">good for a descent camera</span>' : 'poor for a descent camera') + '</span></div>' +
      '<div>' + esc(r.text) + '</div>';
    if (r.shadow && r.shadow.available) {
      h += '<div class="pl-scroll"><table><tr><th>Lander class (assumed)</th><th>Landing spread in shadow</th></tr>';
      r.shadow.classes.forEach(function (c) { h += '<tr><td>' + esc(c.label) + '</td><td>' + (c.available ? pct(c.in_shadow_pct) : '–') + '</td></tr>'; });
      h += '</table></div><div class="pl-m">Terrain: ' + esc(r.shadow.terrain || '') + '. ' + esc(r.shadow.rule) + '. Observer ' + r.shadow.observer_m + ' m above the ground.</div>';
    }
    el.innerHTML = h;
  }

  function joint(el, r) {
    if (!r.available) { el.innerHTML = '<h4>Plan holds and ground flat enough</h4><div class="pl-m">' + esc(r.reason) + '</div>'; return; }
    var h = '<h4>Plan holds and ground flat enough (8°)</h4><div class="pl-scroll"><table><tr><th>Lander class (assumed)</th><th>Plan holds</th><th>Flat enough</th><th>Both</th><th>95 % range</th></tr>';
    r.classes.forEach(function (c) {
      h += c.available ? '<tr><td>' + esc(c.label) + '</td><td>' + pct(c.plan_holds_pct) + '</td><td>' + pct(c.flat_pct) + '</td><td><b>' + pct(c.joint_pct) + '</b></td><td>' + c.joint_range[0].toFixed(1) + ' to ' + c.joint_range[1].toFixed(1) + ' %</td></tr>'
        : '<tr><td>' + esc(c.label) + '</td><td colspan="4" class="pl-m">' + esc(c.why) + '</td></tr>';
    });
    el.innerHTML = h + '</table></div><div class="pl-m">Touchdown ' + esc(day(r.touchdown_utc)) + '. ' + esc(r.how) + '</div>';
  }

  function alts(el, r) {
    var h = '<h4>Other sites at the slipped date, ' + esc(day(r.touchdown_utc)) + '</h4><div class="pl-m">' + r.sites_yes + ' of ' + r.sites_checked + ' sites are a clear yes. Ranked: ' + esc(r.rank_rule) + '.</div>' +
      '<div class="pl-scroll"><table><tr><th>#</th><th>Site</th><th>Answer</th><th>Slip margin</th><th>Points passing</th><th>Sunlit h</th></tr>';
    r.rows.slice(0, 12).forEach(function (x) {
      var v = x.verdict === 'yes' ? '<span class="pl-yes">yes</span>' : esc(x.verdict);
      h += '<tr><td>' + x.rank + '</td><td>' + esc(x.name) + (x.kind === 'map' ? ' <span class="pl-tag">map</span>' : '') + '</td><td>' + v + '</td><td>' +
        (x.slip_margin_days === null ? '–' : x.slip_margin_days < 0 ? 'none' : x.slip_margin_days + ' d') + '</td><td>' +
        (x.points ? x.points_passing + ' of ' + x.points : '–') + '</td><td>' + (x.sunlit_h === undefined ? '–' : x.sunlit_h) + '</td></tr>';
    });
    el.innerHTML = h + '</table></div>';
  }

  if (document.readyState === 'loading') { document.addEventListener('DOMContentLoaded', init); } else { init(); }
  new MutationObserver(function () { if (!box || !document.body.contains(box)) { box = null; init(); } }).observe(document.documentElement, { childList: true, subtree: true });
})();
