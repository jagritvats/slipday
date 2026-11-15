/* Add-on: review-board brief (brief-1).
   Container: <div id="addon-brief"></div>
   Renders a "Make a review-board brief" button that opens /static/brief.html for the current site and landing date.
   It follows the page's own /api/mission requests (request body read, answer cloned; nothing is changed). Until the page
   asks one, it uses the opening example (robust_pick, 18 Nov 2026). */
(function () {
  'use strict';
  var cur = { site: 'robust_pick', lat: null, lon: null, name: '', date: '2026-11-18', slip: 3, label: 'the opening example' };
  var box = null;

  if (window.fetch) {
    var orig = window.fetch.bind(window);
    window.fetch = function (input, init) {
      var p = orig(input, init);
      try {
        var url = typeof input === 'string' ? input : (input && input.url) || '';
        var fromAddon = init && init.headers && (init.headers['X-Slipday-Addon'] || (init.headers.get && init.headers.get('X-Slipday-Addon')));
        if (!fromAddon && url.replace(/^[a-z]+:\/\/[^/]+/i, '').split('?')[0] === '/api/mission') {
          var req = null;
          try { req = init && typeof init.body === 'string' ? JSON.parse(init.body) : null; } catch (e) { req = null; }
          p.then(function (r) {
            if (!r.ok) { return; }
            r.clone().json().then(function (j) {
              if (!j || !j.site) { return; }
              var ref = (req && req.site) || {};
              /* latest-site guard: answers for other compared sites, or ones that arrive late, never replace the shown site */
              var A = window.SlipdayApp, shown = A && A.selected && A.current ? A.selected()[A.current()] : null;
              if (shown) {
                var same = shown.id ? ref.id === shown.id : (!ref.id && Math.abs(j.site.lat - shown.lat) < 1e-4 && Math.abs(j.site.lon - shown.lon) < 1e-4);
                if (!same) { return; }
              }
              cur.site = ref.id || null;
              cur.lat = ref.id ? null : j.site.lat; cur.lon = ref.id ? null : j.site.lon;
              cur.name = ref.id ? '' : (j.site.name || '');
              cur.date = j.landing_utc || cur.date;
              cur.label = j.site.friendly_name || j.site.name || 'this site';
              draw();
            }).catch(function () {});
          }).catch(function () {});
        }
      } catch (e) { /* never get in the page's way */ }
      return p;
    };
  }

  function esc(s) { return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]; }); }

  function href() {
    var q = new URLSearchParams();
    if (cur.site) { q.set('site', cur.site); } else if (cur.lat != null) { q.set('lat', cur.lat); q.set('lon', cur.lon); if (cur.name) { q.set('name', cur.name); } }
    q.set('date', cur.date);
    var s = box && box.querySelector('#br-slip');
    q.set('slip', s && s.value !== '' ? s.value : cur.slip);
    return '/static/brief.html?' + q.toString();
  }

  var CSS = '#addon-brief{color:var(--text,#16181d);font-size:14px;line-height:1.45}' +
    '#addon-brief .br-card{border:1px solid var(--line,#d5d9e0);background:var(--surface,#fff);border-radius:8px;padding:12px;margin:10px 0}' +
    '#addon-brief .br-row{display:flex;flex-wrap:wrap;gap:10px;align-items:center}' +
    '#addon-brief .br-m{color:var(--muted,#535a66);font-size:12.5px;margin-top:6px}' +
    '#addon-brief input{width:4.5em;padding:3px 5px;border:1px solid var(--line,#d5d9e0);background:var(--surface,#fff);color:var(--text,#16181d);border-radius:4px}' +
    '#addon-brief a.br-btn{display:inline-block;border:1px solid var(--accent,#1f4e8c);background:var(--accent,#1f4e8c);color:#fff;border-radius:4px;padding:5px 12px;text-decoration:none;font-weight:600}';

  function draw() {
    if (!box) { return; }
    var a = box.querySelector('#br-go'), t = box.querySelector('#br-for');
    if (a) { a.href = href(); }
    if (t) { t.textContent = cur.label + ', landing ' + String(cur.date).slice(0, 10); }
  }

  function init() {
    box = document.getElementById('addon-brief');
    if (!box || box.dataset.ready) { return; }
    box.dataset.ready = '1';
    var st = document.createElement('style'); st.textContent = CSS; document.head.appendChild(st);
    box.innerHTML = '<div class="br-card"><div class="br-row">' +
      '<a id="br-go" class="br-btn" target="_blank" rel="noopener" href="#">Make a review-board brief</a>' +
      '<label>Slip to defend (days) <input id="br-slip" type="number" min="0" max="120" step="1" value="' + esc(cur.slip) + '"></label></div>' +
      '<div class="br-m">One printable page for <span id="br-for"></span>: verdict, slip margin, windows, hours, slope, lighting, relay, ' +
      'alternatives, checks, assumptions and sources. Save it as a PDF from the print dialog.</div></div>';
    box.querySelector('#br-slip').addEventListener('input', draw);
    box.querySelector('#br-go').addEventListener('click', function () { this.href = href(); });
    draw();
  }

  if (document.readyState === 'loading') { document.addEventListener('DOMContentLoaded', init); } else { init(); }
})();
