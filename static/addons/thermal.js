/* Slipday add-on: "Temperature (NASA Diviner)"

   Include with one container and one script tag:
     <div id="addon-thermal"></div>
     <script src="/static/addons/thermal.js"></script>    (after /static/app.js)

   Shows, for the site on the card (the opening example until the card asks for another), the surface
   temperature measured by NASA's Diviner Lunar Radiometer on LRO: maximum, minimum, coldest night and
   whether the site is in or near a cold trap (ground that stays below 110 K).
   Asks:  GET /api/addons/thermal?lat=&lon=
   It follows the card by watching the page's own /api/mission answers (never changes them).
   Colours come from the page's CSS variables. */
(function () {
  'use strict';
  var ROOT_ID = 'addon-thermal';
  var DEFAULT = { lat: -89.0098, lon: 122.76389, name: 'Slip-robust ridge point (89.010 S, 122.764 E)' };
  var state = { want: null, key: '', data: null, err: '' };
  var root = null;
  var seen = [];

  function esc(s) {
    return String(s).replace(/[&<>"']/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
    });
  }
  function k(v) { return (typeof v === 'number') ? v.toFixed(0) + ' K' : 'no data'; }
  function c(v) { return (typeof v === 'number') ? ' (' + (v - 273.15).toFixed(0) + ' °C)' : ''; }

  function css() {
    if (document.getElementById('sd-thermal-style')) { return; }
    var s = document.createElement('style');
    s.id = 'sd-thermal-style';
    s.textContent = [
      '#addon-thermal,#addon-thermal *{box-sizing:border-box;}',
      '#addon-thermal .th-box{background:var(--surface,#fcfcfb);color:var(--text,#0b0b0b);border:1px solid var(--line,#dddbd3);',
      'border-radius:10px;padding:16px;margin-bottom:16px;max-width:100%;overflow-wrap:anywhere;}',
      '#addon-thermal h2{font-size:17px;margin:0 0 4px;}',
      '#addon-thermal .th-site{color:var(--text2,#52514e);font-size:14px;margin:0 0 10px;}',
      '#addon-thermal dl{display:grid;grid-template-columns:repeat(auto-fit,minmax(130px,1fr));gap:10px;margin:0 0 10px;}',
      '#addon-thermal dl div{border:1px solid var(--line,#dddbd3);border-radius:8px;padding:8px 10px;}',
      '#addon-thermal dt{font-size:12.5px;color:var(--text2,#52514e);}',
      '#addon-thermal dd{margin:2px 0 0;font-size:20px;font-weight:600;font-variant-numeric:tabular-nums;}',
      '#addon-thermal dd small{font-size:12.5px;font-weight:400;color:var(--muted,#7b7a74);}',
      '#addon-thermal .th-flag{font-weight:600;padding:8px 10px;border-left:4px solid var(--accent,#0e3f7e);margin:0 0 10px;',
      'background:var(--ok-bg,#e3eefb);color:var(--ok-ink,#0e3f7e);}',
      '#addon-thermal .th-flag.th-cold{border-left-color:var(--earth,#2a78d6);}',
      '#addon-thermal .th-flag.th-near{background:var(--warn-bg,#fff4dc);color:var(--warn-ink,#6b4a00);border-left-color:var(--warn,#c98a00);}',
      '#addon-thermal .th-note{color:var(--muted,#7b7a74);font-size:12.5px;margin:4px 0 0;max-width:80ch;}',
      '#addon-thermal a{color:var(--accent,#0e3f7e);}'
    ].join('');
    document.head.appendChild(s);
  }

  /* ---------- follow the card's chosen site ---------- */
  if (window.fetch) {
    var orig = window.fetch.bind(window);
    window.fetch = function (input, init) {
      var p = orig(input, init);
      try {
        var url = typeof input === 'string' ? input : (input && input.url) || '';
        var bare = url.replace(/^[a-z]+:\/\/[^/]+/i, '').split('?')[0];
        var fromAddon = init && init.headers && (init.headers['X-Slipday-Addon'] || (init.headers.get && init.headers.get('X-Slipday-Addon')));
        if (bare === '/api/mission' && !fromAddon) {
          p.then(function (r) {
            if (!r.ok) { return; }
            r.clone().json().then(function (j) {
              if (!j || !j.site || typeof j.site.lat !== 'number') { return; }
              var m = { lat: j.site.lat, lon: j.site.lon, name: j.site.name || '' };
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
  function follow() {
    var sel = document.getElementById('mSite');
    var name = sel && sel.selectedIndex >= 0 && sel.options[sel.selectedIndex] ? sel.options[sel.selectedIndex].text : null;
    var hit = null;
    seen.forEach(function (m) { if (name !== null && m.name === name) { hit = m; } });
    if (!hit && seen.length) { hit = seen[seen.length - 1]; }
    if (hit) { want(hit); }
  }
  document.addEventListener('change', function (ev) {
    if (ev.target && ev.target.id === 'mSite') { setTimeout(follow, 0); }
  });

  function want(w) {
    state.want = w;
    var key = w.lat + '|' + w.lon;
    if (key === state.key) { return; }
    state.key = key;
    load(key);
  }

  function load(key) {
    var w = state.want;
    if (!root) { return; }
    state.data = null; state.err = '';
    render();
    var get = window.fetch ? window.fetch.bind(window) : null;
    if (!get) { state.err = 'This browser cannot fetch data.'; render(); return; }
    get('/api/addons/thermal?lat=' + encodeURIComponent(w.lat) + '&lon=' + encodeURIComponent(w.lon))
      .then(function (r) {
        return r.json().then(function (j) { return { ok: r.ok, j: j }; });
      })
      .then(function (res) {
        if (key !== state.key) { return; }
        if (!res.ok) { state.err = (res.j && res.j.detail) || 'No Diviner data for this site.'; }
        else { state.data = res.j; }
        render();
      })
      .catch(function () { if (key === state.key) { state.err = 'Could not reach the server.'; render(); } });
  }

  function render() {
    if (!root) { return; }
    var w = state.want || DEFAULT;
    var h = '<section class="th-box" aria-labelledby="th-h"><h2 id="th-h">Temperature (NASA Diviner)</h2>';
    h += '<p class="th-site">' + esc(w.name || (w.lat.toFixed(3) + ', ' + w.lon.toFixed(3))) + '</p>';
    if (state.err) {
      h += '<p class="th-note">' + esc(state.err) + '</p>';
    } else if (!state.data) {
      h += '<p class="th-note">Loading measured temperatures…</p>';
    } else {
      var d = state.data;
      h += '<dl>' +
        '<div><dt>Highest measured</dt><dd>' + k(d.max_k) + '<small>' + c(d.max_k) + '</small></dd></div>' +
        '<div><dt>Lowest measured</dt><dd>' + k(d.min_k) + '<small>' + c(d.min_k) + '</small></dd></div>' +
        '<div><dt>Coldest night</dt><dd>' + k(d.coldest_night_k) + '<small>' + c(d.coldest_night_k) + '</small></dd></div>' +
        '<div><dt>Average</dt><dd>' + k(d.avg_k) + '<small>' + c(d.avg_k) + '</small></dd></div>' +
        '</dl>';
      var t = d.cold_trap;
      if (t) {
        var cls = t['in'] ? 'th-cold' : (t.near ? 'th-near' : '');
        var txt = t['in'] ? 'In a cold trap: the highest temperature measured here stays below 110 K.'
          : t.near ? 'Near a cold trap: ground below 110 K lies ' + t.nearest_km + ' km away.'
          : 'No cold trap within ' + t.within_km + ' km (no ground staying below 110 K).';
        h += '<p class="th-flag ' + cls + '">' + esc(txt) + '</p>';
      }
      h += '<p class="th-note">Measured by Diviner (NASA Lunar Reconnaissance Orbiter). Highest and average: Diviner polar ' +
        'resource product, several years of data. Lowest and coldest night: Diviner 240 m night-time maps of 2010 and 2016' +
        (typeof d.night_maps === 'number' ? ' (' + d.night_maps + ' maps cover this spot)' : '') +
        '. Source: <a href="https://pds-geosciences.wustl.edu/missions/lro/diviner.htm" rel="noopener">NASA PDS Geosciences Node</a>.</p>';
      if (d.note) { h += '<p class="th-note">' + esc(d.note) + '</p>'; }
    }
    h += '</section>';
    root.innerHTML = h;
  }

  function start() {
    root = document.getElementById(ROOT_ID);
    if (!root) { return; }
    css();
    if (!state.want) { want(DEFAULT); } else { var w = state.want; state.key = ''; want(w); }
  }
  if (document.readyState === 'loading') { document.addEventListener('DOMContentLoaded', start); } else { start(); }
})();
