/* Slipday add-on: "Battery through the night" (and the darkness check, if its container is present)

   Include with one or two containers and one script tag:
     <div id="addon-power"></div>        battery: per slip day, survives with X % left, or empties after N hours
     <div id="addon-darkness"></div>      darkness: longest total darkness per slip day against an hour limit
     <script src="/static/addons/power.js"></script>    (after /static/app.js)

   It follows the site and landing on the card the same way relay.js does: it watches the page's own requests to
   /api/mission (the answer is cloned, never changed) and asks
     GET /api/addons/power/site?lat=&lon=&name=&landing=&battery_kwh=&night_load_w=&day_load_w=&array_w=&panel=
     GET /api/addons/darkness/site?lat=&lon=&name=&landing=&limit_h=
   Every lander figure is shown with its label: its source, or "illustrative".  The card's verdict is never changed.
   No library.  Styles are injected and scoped to the two containers.
*/
(function () {
  'use strict';
  var DEFAULT = { lat: -89.0098, lon: 122.76389, name: 'Slip-robust ridge point (89.010 S, 122.764 E)',
                  landing: '2026-11-18T00:00:00Z' };
  var want = DEFAULT, over = {}, limitH = '';
  var pRoot = null, tRoot = null, seq = 0;

  function esc(s) {
    return String(s).replace(/[&<>"']/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
    });
  }

  function style() {
    var s = document.createElement('style');
    s.textContent = [
      '.pw-box{font-size:14px;line-height:1.45;max-width:760px;}',
      '.pw-head{font-weight:600;margin:4px 0 8px;}',
      '.pw-days{display:grid;grid-template-columns:repeat(auto-fill,minmax(22px,1fr));gap:2px;max-width:720px;}',
      '.pw-d{height:22px;border-radius:2px;font-size:10px;text-align:center;line-height:22px;color:#fff;}',
      '.pw-ok{background:#2f6f4f;}.pw-bad{background:#a23b2a;}.pw-na{background:#8a8a85;}',
      '.pw-note{color:var(--muted,#7b7a74);font-size:12.5px;}',
      '.pw-form{display:flex;flex-wrap:wrap;gap:6px 12px;margin:8px 0;}',
      '.pw-form label{font-size:13px;display:flex;flex-direction:column;}',
      '.pw-form input,.pw-form select{width:8em;font:inherit;padding:2px 4px;}',
      '.pw-tab{border-collapse:collapse;font-size:13px;margin:6px 0;}',
      '.pw-tab td,.pw-tab th{border-bottom:1px solid rgba(128,128,128,.25);padding:2px 8px 2px 0;text-align:left;vertical-align:top;}',
      '.pw-ill{color:#a23b2a;font-weight:600;}',
      '.pw-svg{width:100%;max-width:720px;height:90px;display:block;}',
      '.pw-box details summary{cursor:pointer;font-weight:600;padding:6px 0;}'
    ].join('');
    document.head.appendChild(s);
  }

  function getJSON(url) {
    return fetch(url, { headers: { 'X-Slipday-Addon': '1' } }).then(function (r) {
      return r.json().then(function (j) { return { ok: r.ok, j: j }; });
    });
  }

  function q(obj) {
    return Object.keys(obj).filter(function (k) { return obj[k] !== '' && obj[k] !== null && obj[k] !== undefined; })
      .map(function (k) { return k + '=' + encodeURIComponent(obj[k]); }).join('&');
  }

  function curve(pcts, lit) {
    var n = pcts.length; if (n < 2) { return ''; }
    var W = 720, H = 90, pts = [];
    for (var i = 0; i < n; i++) { pts.push((i / (n - 1) * W).toFixed(1) + ',' + (H - 4 - pcts[i] / 100 * (H - 8)).toFixed(1)); }
    var bands = '';
    for (var t = 0; t < lit.length; t++) {
      if (!lit[t]) { bands += '<rect x="' + (t / (n - 1) * W).toFixed(1) + '" y="0" width="' + (W / (n - 1) + 0.5).toFixed(1) + '" height="' + H + '" fill="rgba(60,60,90,.18)"/>'; }
    }
    return '<svg class="pw-svg" viewBox="0 0 ' + W + ' ' + H + '" preserveAspectRatio="none" role="img" aria-label="battery charge over the first landing window">' +
      bands + '<polyline fill="none" stroke="currentColor" stroke-width="1.6" points="' + pts.join(' ') + '"/></svg>';
  }

  function renderPower(j) {
    if (!pRoot) { return; }
    if (!j) { pRoot.innerHTML = '<div class="pw-box pw-note">Working out the battery...</div>'; return; }
    if (j.detail) { pRoot.innerHTML = '<div class="pw-box pw-note">' + esc(typeof j.detail === 'string' ? j.detail : 'request refused') + '</div>'; return; }
    var cells = j.days.map(function (d) {
      return '<div class="pw-d ' + (d.survives ? 'pw-ok' : 'pw-bad') + '" title="slip ' + d.day + ': ' + esc(d.text) + '">' + d.day + '</div>';
    }).join('');
    var rows = Object.keys(j.figures).map(function (k) {
      var f = j.figures[k];
      var lab = f.label === 'illustrative' ? '<span class="pw-ill">illustrative</span>' : esc(f.label);
      return '<tr><td>' + esc(f.what) + '</td><td>' + esc(j.used[k]) + ' ' + esc(f.unit) + '</td><td>' + lab +
        (j.changed_by_user.indexOf(k) >= 0 ? ' (changed by you)' : '') + (f.quote ? '<br><span class="pw-note">"' + esc(f.quote) + '"</span>' : '') + '</td></tr>';
    }).join('');
    var u = j.used;
    pRoot.innerHTML = '<div class="pw-box">' +
      '<div class="pw-head">' + esc(j.site.name) + ', landing ' + esc(j.landing_utc.slice(0, 10)) + ': ' + esc(j.headline) + '.</div>' +
      '<div>' + j.days_surviving + ' of ' + j.slip_days_checked + ' slip days survive' +
      (j.first_failing_slip_day !== null ? '; the first that does not is slip day ' + j.first_failing_slip_day : '') + '.</div>' +
      '<div class="pw-days" aria-label="slip days">' + cells + '</div>' +
      '<div class="pw-note">Each square is a landing on that day of slip: green survives the window and the night under way at its end, red empties. Hover for the figure.</div>' +
      '<div style="margin-top:8px">Charge after a landing on the planned date (shaded: Sun down):</div>' + curve(j.day0_curve_pct, j.day0_sunlit) +
      '<div class="pw-note"><b>' + esc(j.no_flown_figures) + '</b> Lander: ' + esc(j.lander) + '.</div>' +
      '<form class="pw-form" onsubmit="return false">' +
      '<label>battery kWh<input type="number" step="0.1" min="0.1" name="battery_kwh" value="' + (u.battery_wh / 1000) + '"></label>' +
      '<label>night load W<input type="number" step="1" min="0" name="night_load_w" value="' + u.night_load_w + '"></label>' +
      '<label>day load W<input type="number" step="1" min="0" name="day_load_w" value="' + u.day_load_w + '"></label>' +
      '<label>array W<input type="number" step="1" min="0" name="array_w" value="' + u.array_w + '"></label>' +
      '<label>panels<select name="panel">' + ['vertical_fixed', 'vertical_tracking', 'horizontal'].map(function (p) {
        return '<option value="' + p + '"' + (u.panel === p ? ' selected' : '') + '>' + p.replace('_', ' ') + '</option>'; }).join('') + '</select></label>' +
      '<label>&nbsp;<button type="button" data-pw="go">Work it out</button></label></form>' +
      '<details><summary>Figures and their sources</summary><table class="pw-tab"><tr><th>figure</th><th>used</th><th>label</th></tr>' + rows + '</table></details>' +
      '<details><summary>How it is worked out, and what it leaves out</summary><p class="pw-note">' + esc(j.rule) + '</p></details>' +
      '</div>';
  }

  function renderDarkness(j) {
    if (!tRoot) { return; }
    if (!j) { tRoot.innerHTML = '<div class="pw-box pw-note">Counting the darkness...</div>'; return; }
    if (j.detail) { tRoot.innerHTML = '<div class="pw-box pw-note">' + esc(typeof j.detail === 'string' ? j.detail : 'request refused') + '</div>'; return; }
    var cells = j.days.map(function (d) {
      var c = d.within_limit === null ? 'pw-na' : (d.within_limit ? 'pw-ok' : 'pw-bad');
      return '<div class="pw-d ' + c + '" title="slip ' + d.day + ': ' + esc(d.text) + '">' + d.darkness_h + '</div>';
    }).join('');
    tRoot.innerHTML = '<div class="pw-box">' +
      '<div class="pw-head">' + esc(j.site.name) + ', landing ' + esc(j.landing_utc.slice(0, 10)) + ': ' + esc(j.headline) + '.</div>' +
      '<div class="pw-days" style="grid-template-columns:repeat(auto-fill,minmax(30px,1fr))">' + cells + '</div>' +
      '<div class="pw-note">Each square is a landing on that day of slip; the number is the longest run of hours with no part of the Sun above the skyline. ' +
      (j.limit_h === null ? 'No limit is set: no first-hand survival-in-darkness figure is stored, so enter your own.' : 'Limit: ' + j.limit_h + ' h (' + esc(j.limit_label) + ').') +
      (j.context ? ' For context only: ' + esc(j.context.what) + '.' : '') + '</div>' +
      '<form class="pw-form" onsubmit="return false"><label>limit, hours<input type="number" min="0" step="1" name="limit_h" value="' + esc(limitH) + '"></label>' +
      '<label>&nbsp;<button type="button" data-th="go">Check</button></label></form>' +
      '<details><summary>How it is worked out</summary><p class="pw-note">' + esc(j.rule) + '</p></details></div>';
  }

  function load() {
    var my = ++seq;
    var base = { lat: want.lat, lon: want.lon, name: want.name, landing: want.landing };
    if (pRoot) {
      renderPower(null);
      getJSON('/api/addons/power/site?' + q(Object.assign({}, base, over))).then(function (r) {
        if (my === seq) { renderPower(r.j); }
      }).catch(function () { if (pRoot) { pRoot.innerHTML = '<div class="pw-box pw-note">The battery model did not answer.</div>'; } });
    }
    if (tRoot) {
      renderDarkness(null);
      getJSON('/api/addons/darkness/site?' + q(Object.assign({}, base, { limit_h: limitH }))).then(function (r) {
        if (my === seq) { renderDarkness(r.j); }
      }).catch(function () { if (tRoot) { tRoot.innerHTML = '<div class="pw-box pw-note">The darkness check did not answer.</div>'; } });
    }
  }

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
                        landing: j.landing_utc || (body && body.landing) || DEFAULT.landing };
              if ([m.lat, m.lon, m.landing].join('|') !== [want.lat, want.lon, want.landing].join('|')) { want = m; load(); }
            }).catch(function () {});
          }).catch(function () {});
        }
      } catch (e) { /* never get in the page's way */ }
      return p;
    };
  }

  function start() {
    pRoot = document.getElementById('addon-power');
    tRoot = document.getElementById('addon-darkness');
    if (!pRoot && !tRoot) { return; }
    style();
    document.addEventListener('click', function (ev) {
      var b = ev.target;
      if (!b || !b.getAttribute) { return; }
      if (b.getAttribute('data-pw') === 'go' && pRoot) {
        over = {};
        Array.prototype.forEach.call(pRoot.querySelectorAll('input,select'), function (el) { over[el.name] = el.value; });
        load();
      } else if (b.getAttribute('data-th') === 'go' && tRoot) {
        var el = tRoot.querySelector('input[name=limit_h]');
        limitH = el ? el.value : '';
        load();
      }
    });
    load();
  }
  if (document.readyState === 'loading') { document.addEventListener('DOMContentLoaded', start); } else { start(); }
})();
