/* Slipday add-on: "Flat enough to land?"

   Include with one container and one script tag:
     <div id="addon-safety"></div>                         (directly under the site card, #missionOut)
     <script src="/static/addons/safety.js"></script>      (after /static/app.js)

   What it adds:
     1. Under the site card: one line, "Flat enough to land?", for the site and landing scatter the card shows,
        with the slope at each of the 13 touchdown points behind a "Show the 13 points" toggle.
     2. On the south-polar map: a switch for a slope layer over the scatter-checked slip-margin map
        (slip-tolerant and flat enough / slip-tolerant but too steep / not slip-tolerant).

   It reads nothing private from app.js.  It watches the page's own requests to /api/mission, /api/robust-map and
   /api/map (the answers are cloned, never changed), and asks the add-on API:
     GET  /api/addons/safety/site?lat=&lon=&scatter_m=&name=
     POST /api/addons/safety/map-layer   (the same body the page sent to /api/robust-map)
   No library.  Works at phone width.
*/
(function () {
  'use strict';
  var $ = function (id) { return document.getElementById(id); };
  var seen = { missions: [], robustBody: null, maps: {} };
  /* 'slope only' draws the full-coverage slope map (every close-up point); the address is the one place to change it */
  var SLOPE_SOURCE = '/api/addons/slopemap';
  var mode = 'slope', goalDeg = null, slope = null, slopeBusy = false;
  var ui = {}, cardKey = '', cardData = null, cardCache = {}, layerOn = false, layer = null, layerKey = '', layerBusy = false;

  function esc(s) {
    return String(s).replace(/[&<>"']/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]; });
  }
  /* one decimal; two when one would hide which side of NASA's 5 or 8 degrees it is on */
  function deg(x) {
    if (x === null || x === undefined) { return 'not known'; }
    var nd = Math.min(Math.abs(x - 8), Math.abs(x - 5)) < 0.05 ? 2 : 1;
    return x.toFixed(nd) + '°';
  }

  /* ---------- watch what the page asks the server ---------- */
  if (window.fetch) {
    var orig = window.fetch.bind(window);
    window.fetch = function (input, init) {
      var p = orig(input, init);
      try {
        var url = typeof input === 'string' ? input : (input && input.url) || '';
        var path = url.replace(/^[a-z]+:\/\/[^/]+/i, '');
        var bare = path.split('?')[0];
        var mine = init && init.headers && init.headers['X-Slipday-Addon'];
        if (!mine && (bare === '/api/mission' || bare === '/api/robust-map' || bare === '/api/map')) {
          var body = init && typeof init.body === 'string' ? JSON.parse(init.body) : null;
          p.then(function (r) {
            if (!r.ok) { return; }
            r.clone().json().then(function (j) { record(bare, path, body, j); }).catch(function () {});
          }).catch(function () {});
        }
      } catch (e) { /* never get in the page's way */ }
      return p;
    };
  }
  function record(bare, path, body, j) {
    if (bare === '/api/mission' && j && j.site) {
      seen.missions = seen.missions.filter(function (m) { return m.resp.site.name !== j.site.name; });
      seen.missions.push({ body: body, resp: j });
      updateCard();
    } else if (bare === '/api/robust-map' && body) {
      seen.robustBody = body;
      if (layerOn && mode !== 'slope') { loadLayer(); }
    } else if (bare === '/api/map' && j && j.available) {
      seen.maps[/half_km=/.test(path) ? 'pole' : ''] = j;
    }
  }
  function api(path, body) {
    var opt = body ? { method: 'POST', headers: { 'Content-Type': 'application/json', 'X-Slipday-Addon': '1' }, body: JSON.stringify(body) }
      : { headers: { 'X-Slipday-Addon': '1' } };
    return fetch(path, opt).then(function (r) {
      return r.json().then(function (j) {
        if (!r.ok) { throw new Error(typeof j.detail === 'string' ? j.detail : 'The server could not answer (' + r.status + ').'); }
        return j;
      });
    });
  }

  /* ---------- styles (scoped, using the page's colours where it has them) ---------- */
  function css() {
    if ($('sdS-style')) { return; }
    var s = document.createElement('style');
    s.id = 'sdS-style';
    s.textContent =
      /* the site card sits in a two-column grid (.mission: "in out" / "more out"); put the line under the card */
      '#addon-safety{min-width:0;max-width:100%}' +
      '.mission>#addon-safety{grid-column:2;grid-row:3}' +
      '@media (max-width:900px){.mission:has(>#addon-safety){grid-template-areas:"in" "out" "safety" "more"}.mission>#addon-safety{grid-area:safety}}' +
      'body.sdS-layer-on #mapLegend{display:none}' +
      '.sdS{min-width:0;overflow-wrap:anywhere;margin:.6rem 0 0;padding:.55rem .7rem;border:1px solid var(--line,#dddbd3);border-radius:8px;background:var(--surface,#fcfcfb);color:var(--text,#0b0b0b);font-size:.95rem;line-height:1.4;max-width:100%;box-sizing:border-box}' +
      '.sdS-line{display:flex;flex-wrap:wrap;gap:.25rem .5rem;align-items:baseline}' +
      '.sdS-q{font-weight:600}' +
      '.sdS-w{font-weight:700;padding:0 .4rem;border-radius:4px}' +
      '.sdS-w.flat{background:var(--ok-bg,#e3eefb);color:var(--ok-ink,#0e3f7e)}' +
      '.sdS-w.steep{background:var(--warn-bg,#fff4d6);color:var(--warn-ink,#5c4300)}' +
      '.sdS-w.unknown{background:var(--grid,#e9e7e0);color:var(--text,#0b0b0b)}' +
      '.sdS-sub{color:var(--muted,#7b7a74);font-size:.85rem;margin:.25rem 0 0}' +
      '.sdS details{margin-top:.35rem}.sdS summary{cursor:pointer;min-height:32px;display:flex;align-items:center}' +
      '.sdS-tw{overflow-x:auto;-webkit-overflow-scrolling:touch;max-width:100%}' +
      '.sdS table{border-collapse:collapse;font-size:.85rem;min-width:100%}' +
      '.sdS th,.sdS td{padding:.2rem .45rem;border-bottom:1px solid var(--grid,#e9e7e0);text-align:left;white-space:nowrap;overflow-wrap:normal}' +
      '.sdS td:first-child,.sdS th{white-space:normal}' +
      '.sdS td.n{text-align:right;font-variant-numeric:tabular-nums}' +
      '.sdS .bad{color:var(--crit,#d03b3b);font-weight:600}' +
      '.sdS-map{margin:.5rem 0}.sdS-map label.sdS-tg{display:flex;flex-direction:row;align-items:center;gap:.5rem;min-height:40px;cursor:pointer;font-size:.95rem;color:var(--text,#0b0b0b)}' +
      '.sdS-map label.sdS-tg input{width:20px;height:20px;margin:0;flex:none}' +
      '.sdS-leg{display:flex;flex-wrap:wrap;gap:.3rem .9rem;align-items:center;font-size:.85rem;margin-top:.25rem}' +
      '.sdS-sw{display:inline-block;width:14px;height:14px;vertical-align:-2px;margin-right:.3rem;box-sizing:border-box}' +
      '.sdS-sw.flat{background:#0ca30c}.sdS-sw.steep{background:#d03b3b;background-image:repeating-linear-gradient(45deg,transparent 0 3px,rgba(255,255,255,.75) 3px 5px)}' +
      '.sdS-sw.not{border:2px solid #9a988f;background:transparent}.sdS-sw.mid{background:#e8a33d}.sdS-sw.none{background:rgba(200,200,200,.45);border:1px solid #9a988f}.sdS-mode{display:flex;flex-wrap:wrap;gap:4px 14px;margin:4px 0 0 26px}' +
      '.sdS-hover{font-size:.85rem;min-height:1.3em;color:var(--muted,#7b7a74)}' +
      '#polar.sdS-on image.overlay{opacity:0}' +
      '#polar image.sdS-ov{image-rendering:pixelated;image-rendering:crisp-edges}' +
      '@media (max-width:760px){.sdS{font-size:.92rem}.sdS th,.sdS td{padding:.2rem .3rem}}';
    document.head.appendChild(s);
  }

  /* ---------- 1. the line under the site card ---------- */
  function currentMission() {
    var sel = $('mSite');
    var name = sel && sel.selectedIndex >= 0 && sel.options[sel.selectedIndex] ? sel.options[sel.selectedIndex].text : null;
    var hit = null;
    seen.missions.forEach(function (m) { if (name !== null && m.resp.site.name === name) { hit = m; } });
    if (!hit && name === null && seen.missions.length) { hit = seen.missions[seen.missions.length - 1]; }
    return hit;
  }
  /* the site the page shows now, read from the page itself; the mission answer is used only for a widened scatter */
  function currentSite() {
    var A = window.SlipdayApp, s = A && A.selected ? A.selected()[A.current()] : null;
    if (s && isFinite(s.lat) && isFinite(s.lon)) {
      var mm = currentMission(), c = A.cfg ? A.cfg() : null;
      var sc = (mm && mm.resp.site.name === s.name && mm.resp.sure && mm.resp.sure.points > 1) ? mm.resp.sure.scatter_m : ((c && c.scatter) || 100);
      return { name: s.name, lat: s.lat, lon: s.lon, sc: sc };
    }
    var m = currentMission();
    if (!m) { return null; }
    return { name: m.resp.site.name, lat: m.resp.site.lat, lon: m.resp.site.lon,
      sc: (m.resp.sure && m.resp.sure.points > 1) ? m.resp.sure.scatter_m : ((m.body && m.body.scatter_m) || 100) };
  }
  function updateCard() {
    if (!ui.card) { return; }
    var st = currentSite();
    /* never leave the previous site's answer on screen */
    if (!st) { cardKey = ''; cardData = null; ui.card.innerHTML = '<p class="sdS-sub">Flat enough to land? Waiting for the site card…</p>'; return; }
    var sc = st.sc;
    var key = st.lat + ',' + st.lon + ',' + sc;
    if (key === cardKey) { return; }
    cardKey = key;
    if (cardCache[key]) { cardData = cardCache[key]; renderCard(cardData); return; }
    cardData = null;
    ui.card.innerHTML = '<p class="sdS-sub">Flat enough to land? Measuring the slope at 13 touchdown points around ' + esc(st.name) + '…</p>';
    api('/api/addons/safety/site?lat=' + encodeURIComponent(st.lat) + '&lon=' + encodeURIComponent(st.lon) +
        '&scatter_m=' + encodeURIComponent(sc) + '&name=' + encodeURIComponent(st.name)).then(function (r) {
      cardCache[key] = r;
      if (key !== cardKey) { return; }
      cardData = r; renderCard(r);
    }).catch(function (e) { if (key === cardKey) { cardKey = ''; ui.card.innerHTML = '<p class="sdS-sub">Flat enough to land? Could not check ' + esc(st.name) + ': ' + esc(e.message) + '</p>'; } });
  }
  function renderCard(r) {
    if (!r.available) { ui.card.innerHTML = '<p class="sdS-sub">Flat enough to land? ' + esc(r.reason || 'Not available.') + '</p>'; return; }
    var rows = r.points.map(function (p) {
      return '<tr><td>' + esc(p.point) + '</td><td class="n' + (p.passes === false ? ' bad' : '') + '">' + deg(p.slope_deg) + '</td><td>' +
        (p.passes === null ? 'not known' : p.passes ? 'yes' : '<span class="bad">no, too steep</span>') + '</td><td class="n">' +
        (p.grid_m ? p.grid_m + ' m' : '–') + '</td><td class="n">' + (p.baseline_m ? p.baseline_m + ' m' : '–') + '</td></tr>';
    }).join('');
    var t = r.points[0], other = (t.by_grid || []).filter(function (b) { return b.grid_m !== t.grid_m; });
    var cmp = other.length ? 'At the target, the coarser grids read ' + other.map(function (b) { return deg(b.slope_deg) + ' on ' + b.grid_m + ' m'; }).join(' and ') +
      ' (a wider square smooths the ground).' : '';
    ui.card.innerHTML =
      '<div class="sdS-line"><span class="sdS-q">Flat enough to land?</span> <span class="sdS-sub">(' + esc(r.site && r.site.name ? r.site.name : '') + ')</span><span class="sdS-w ' + esc(r.verdict) + '">' + esc(r.word) + '</span>' +
      '<span>' + esc(r.headline) + '</span></div>' +
      (r.verdict === 'steep' && /20 m/.test(r.grid_words || '') ? '<p class="sdS-sub">Much of the ground near the pole really is this steep: the best-lit points sit on ridges and crater rims, so a flat spot in the light is rare and worth finding.</p>' : '') +
      (/80 m/.test(r.grid_words || '') ? '<p class="sdS-sub">80 m terrain is too coarse to judge slope at lander scale; treat this as a rough guide.</p>' : '') +
      '<p class="sdS-sub">Slope from ' + esc(r.grid_words || 'no grid') + '. NASA’s limit for its crewed lander: it must stand within ' + r.limit_deg +
      '° of upright (5° is the goal); site studies use this as the limit on ground slope.</p>' +
      '<details><summary>Show the 13 points</summary><div class="sdS-tw"><table><thead><tr><th>Touchdown point</th><th>Slope</th><th>Under ' + r.limit_deg +
      '°?</th><th>Grid</th><th>Measured over</th></tr></thead><tbody>' + rows + '</tbody></table></div>' +
      '<p class="sdS-sub">' + esc(r.how) + ' ' + esc(cmp) + '</p>' +
      '<p class="sdS-sub"><b>What it cannot tell:</b> ' + esc(r.limits.join(' ')) + '</p>' +
      '<p class="sdS-sub">Source: ' + esc(r.source.limit) + ' ' + esc(r.source.accuracy) + ' ' + esc(r.source.study) + '</p></details>';
  }

  /* ---------- 2. the slope layer on the map ---------- */
  function mountMapControl() {
    if ($('sdS-map')) { return; }
    var box = document.createElement('div');
    box.id = 'sdS-map'; box.className = 'sdS sdS-map';
    box.innerHTML = '<label class="inline sdS-tg"><input type="checkbox" id="sdS-toggle"> <span><b>Flat enough to land?</b> Show the slope layer on the map</span></label>' +
      '<span class="sdS-mode" role="radiogroup" aria-label="What the slope layer shows"><label class="inline"><input type="radio" name="sdS-mode" value="slope" checked> slope only (5° and 8° bands)</label>' +
      '<label class="inline"><input type="radio" name="sdS-mode" value="both"> slip and slope together</label></span>' +
      '<div id="sdS-leg" class="sdS-leg" hidden></div><div id="sdS-hover" class="sdS-hover" aria-live="polite"></div>';
    var anchor = $('mapLegend');
    if (anchor && anchor.parentNode) { anchor.parentNode.insertBefore(box, anchor.nextSibling); } else if (ui.root) { ui.root.appendChild(box); } else { return; }
    ui.toggle = $('sdS-toggle'); ui.leg = $('sdS-leg'); ui.hover = $('sdS-hover');
    ui.toggle.addEventListener('change', function () {
      layerOn = ui.toggle.checked;
      ui.leg.hidden = !layerOn;
      if (layerOn) { loadActive(); } else { ui.hover.textContent = ''; }
      draw();
    });
    Array.prototype.forEach.call(box.querySelectorAll('input[name="sdS-mode"]'), function (r) {
      r.addEventListener('change', function () { if (r.checked) { mode = r.value; urlCache.key = null; if (layerOn) { loadActive(); } legend(); draw(); } });
    });
    var polar = $('polar');
    if (polar && window.MutationObserver) {
      new MutationObserver(function () { if (layerOn) { draw(); } }).observe(polar, { childList: true });
    }
  }
  /* the data the overlay draws now: the full-coverage slope map, or the slip-and-slope layer */
  function active() { return mode === 'slope' ? slope : layer; }
  function loadActive() { if (mode === 'slope') { loadSlope(); } else { loadLayer(); } }
  function loadSlope() {
    if (slope || slopeBusy) { legend(); draw(); return; }
    slopeBusy = true;
    ui.leg.innerHTML = '<span>Loading the slope at 13 touchdown points for each map point…</span>';
    api(SLOPE_SOURCE).then(function (r) {
      slopeBusy = false; slope = r;
      if (r && r.goal_deg !== undefined) { goalDeg = r.goal_deg; }
      urlCache.key = null; legend(); draw();
    }).catch(function (e) { slopeBusy = false; if (mode === 'slope') { ui.leg.innerHTML = '<span>Could not load the slope map: ' + esc(e.message) + '</span>'; } });
  }
  function loadLayer() {
    if (!seen.robustBody) { ui.leg.innerHTML = '<span>Waiting for the slip-margin map to load (choose “days of slip the planned landing survives”).</span>'; return; }
    var key = JSON.stringify(seen.robustBody);
    if (key === layerKey && (layer || layerBusy)) { legend(); draw(); return; }
    layerKey = key; layer = null; layerBusy = true;
    ui.leg.innerHTML = '<span>Measuring the slope at 13 touchdown points for each map point…</span>';
    api('/api/addons/safety/map-layer', seen.robustBody).then(function (r) {
      if (key !== layerKey) { return; }
      layerBusy = false; layer = r; legend(); draw();
    }).catch(function (e) { if (key === layerKey) { layerBusy = false; layerKey = ''; ui.leg.innerHTML = '<span>Could not load the slope layer: ' + esc(e.message) + '</span>'; } });
  }
  function legend() {
    var d = active();
    if (!d) { return; }
    if (!d.available) { ui.leg.innerHTML = '<span>' + esc(d.reason || 'Not available.') + '</span>'; return; }
    if (mode === 'slope') {
      var n = { '2': 0, '1': 0, '0': 0, '-1': 0 };
      d['class'].forEach(function (c) { n[String(c)] = (n[String(c)] || 0) + 1; });
      var grids = (d.points_by_coarsest_grid_m ? Object.keys(d.points_by_coarsest_grid_m) : []).map(function (g) { return g + ' m'; });
      ui.leg.innerHTML =
        '<span><i class="sdS-sw flat"></i>Flat (' + d.goal_deg + '° or less, NASA’s goal): ' + n['2'] + '</span>' +
        '<span><i class="sdS-sw mid"></i>Flat enough (up to ' + d.limit_deg + '°, NASA’s limit): ' + n['1'] + '</span>' +
        '<span><i class="sdS-sw steeplite"></i>Too steep (light red tint): ' + n['0'] + '</span>' +
        (n['-1'] ? '<span><i class="sdS-sw none"></i>Not known: ' + n['-1'] + '</span>' : '') +
        '<span style="flex-basis:100%">Each point is checked at 13 touchdown points within ' + d.scatter_m + ' m, on ' + (grids.length ? grids.join(' or ') : 'the finest') +
        ' terrain; boulders are too small to see at this scale. One point every ' + d.step_m + ' m, on the close-up only. ' + esc(d.summary || '') + '</span>';
      return;
    }
    var c = d.counts, C = d.codes;
    ui.leg.innerHTML =
      '<span><i class="sdS-sw flat"></i>slip-tolerant and flat enough (' + c[C['2']] + ')</span>' +
      '<span><i class="sdS-sw steep"></i>slip-tolerant but too steep (' + c[C['1']] + ')</span>' +
      '<span><i class="sdS-sw not"></i>not slip-tolerant (' + c[C['0']] + ')</span>' +
      '<span style="flex-basis:100%">' + esc(d.summary) + ' Slip-tolerant here means the planned landing survives at least ' + d.min_slip_days +
      ' day' + (d.min_slip_days === 1 ? '' : 's') + ' of slip at all 13 touchdown points. Flat enough means every one of the 13 is under NASA’s ' + d.limit_deg +
      '°. Slope from ' + esc(d.grids_used.map(function (g) { return g.grid_m + ' m terrain (over ' + g.baseline_m + ' m)'; })
        .filter(function (t, i, a) { return a.indexOf(t) === i; }).join(' and ')) +
      '. Points where the planned date already fails are left blank, as on the map.</span>';
  }
  var urlCache = { key: null, url: null };
  function overlayUrl() {
    var d = active(), n = d.n, K = 8, key = (mode === 'slope' ? 'slope' : layerKey) + '|' + mode;
    if (urlCache.key === key) { return urlCache.url; }
    var c = document.createElement('canvas'); c.width = n * K; c.height = n * K;
    var ctx = c.getContext('2d');
    var stripe = function (x, y) { ctx.strokeStyle = 'rgba(255,255,255,.85)'; ctx.lineWidth = 1.5; ctx.beginPath(); ctx.moveTo(x + 1, y + K - 1); ctx.lineTo(x + K - 1, y + 1); ctx.stroke(); };
    if (mode === 'slope') {
      for (var j = 0; j < d['class'].length; j++) {
        var k = d['class'][j], px = (j % n) * K, py = Math.floor(j / n) * K;
        if (k === 2) { ctx.fillStyle = '#0ca30c'; ctx.fillRect(px, py, K, K); }
        else if (k === 1) { ctx.fillStyle = '#e8a33d'; ctx.fillRect(px, py, K, K); }
        else if (k === 0) { ctx.fillStyle = 'rgba(208,59,59,.42)'; ctx.fillRect(px, py, K, K); }
        else { ctx.fillStyle = 'rgba(200,200,200,.35)'; ctx.fillRect(px, py, K, K); }
      }
    } else {
      for (var i = 0; i < d.layer.length; i++) {
        var v = d.layer[i], x = (i % n) * K, y = Math.floor(i / n) * K;
        if (v === 2) { ctx.fillStyle = '#0ca30c'; ctx.fillRect(x, y, K, K); }
        else if (v === 1) { ctx.fillStyle = '#d03b3b'; ctx.fillRect(x, y, K, K); stripe(x, y); }
        else if (v === 0) { ctx.strokeStyle = '#9a988f'; ctx.lineWidth = 2; ctx.strokeRect(x + 1.5, y + 1.5, K - 3, K - 3); }
      }
    }
    urlCache = { key: key, url: c.toDataURL('image/png') };
    return urlCache.url;
  }
  function geometry(svg) {
    var box = svg.querySelector('rect.ovbox');
    if (box) { return { x: +box.getAttribute('x'), y: +box.getAttribute('y'), w: +box.getAttribute('width') }; }
    var z = $('mapZoom') ? $('mapZoom').value : '';
    var m = seen.maps[z] || seen.maps.pole || null;
    if (!m || !m.half_width_km) { return null; }
    var S = 1000, w = active().half_km / m.half_width_km * S;
    return { x: S / 2 - w / 2, y: S / 2 - w / 2, w: w };
  }
  function draw() {
    var polar = $('polar'), svg = polar && polar.querySelector('svg');
    if (!polar) { return; }
    var old = svg && svg.querySelector('.sdS-ov');
    if (old) { old.parentNode.removeChild(old); }
    var d = active(), show = layerOn && d && d.available && svg;
    polar.classList.toggle('sdS-on', !!show);
    document.body.classList.toggle('sdS-layer-on', !!show);
    if (!show) { return; }
    var g = geometry(svg);
    if (!g) { return; }
    var NS = 'http://www.w3.org/2000/svg', img = document.createElementNS(NS, 'image');
    img.setAttribute('x', g.x); img.setAttribute('y', g.y); img.setAttribute('width', g.w); img.setAttribute('height', g.w);
    img.setAttribute('href', overlayUrl()); img.setAttribute('preserveAspectRatio', 'none'); img.setAttribute('class', 'sdS-ov');
    img.style.pointerEvents = 'none';
    var marks = svg.querySelector('circle, g');          /* under the site markers, above the shaded relief */
    if (marks) { svg.insertBefore(img, marks); } else { svg.appendChild(img); }
    if (!svg.getAttribute('data-sdS')) {
      svg.setAttribute('data-sdS', '1');
      var hover = function (ev) { describe(ev, svg); };
      svg.addEventListener('pointermove', hover);
      svg.addEventListener('pointerdown', hover);
    }
  }
  function describe(ev, svg) {
    var d = active();
    if (!layerOn || !d || !d.available) { return; }
    var g = geometry(svg), r = svg.getBoundingClientRect();
    if (!g || !r.width) { return; }
    var sx = (ev.clientX - r.left) / r.width * 1000, sy = (ev.clientY - r.top) / r.height * 1000;
    var n = d.n, col = Math.floor((sx - g.x) / g.w * n), row = Math.floor((sy - g.y) / g.w * n);
    if (col < 0 || row < 0 || col >= n || row >= n) { ui.hover.textContent = ''; return; }
    var i = row * n + col;
    if (mode === 'slope') {
      var k = d['class'][i], s = d.steepest_deg[i];
      ui.hover.textContent = 'Point under the pointer: ' + (k === 2 ? 'flat' : k === 1 ? 'flat enough' : k === 0 ? 'too steep' : 'not known') +
        (s !== null && s !== undefined ? '; steepest of its 13 touchdown points ' + deg(s) + ' on ' + d.coarsest_grid_m[i] + ' m terrain' : '') +
        '; ' + d.points_passing[i] + ' of 13 under ' + d.limit_deg + '°.';
      return;
    }
    var v = d.layer[i], s2 = d.steepest_deg[i];
    ui.hover.textContent = 'Point under the pointer: ' + d.codes[String(v)] + (s2 !== null ? '; steepest of its 13 touchdown points ' + deg(s2) : '') + '.';
  }

  /* ---------- start ---------- */
  function init() {
    css();
    ui.root = $('addon-safety');
    if (ui.root) {
      ui.root.innerHTML = '<div class="sdS" id="sdS-card" aria-live="polite"><p class="sdS-sub">Flat enough to land? Waiting for the site card…</p></div>';
      ui.card = $('sdS-card');
    }
    mountMapControl();
    var sel = $('mSite');
    if (sel) { sel.addEventListener('change', function () { setTimeout(updateCard, 0); }); }
    document.addEventListener('slipday:update', function () { setTimeout(updateCard, 0); });
    var out = $('missionOut');
    if (out && window.MutationObserver) {
      var t = null;
      new MutationObserver(function () { clearTimeout(t); t = setTimeout(updateCard, 300); }).observe(out, { childList: true });
    }
    updateCard();
  }
  if (document.readyState === 'loading') { document.addEventListener('DOMContentLoaded', init); } else { init(); }
  window.SlipdaySafety = { refresh: updateCard, state: function () { return { card: cardData, layer: layer, on: layerOn }; } };
})();
