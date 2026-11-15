/* Lunar against terrestrial conditions: the Sun's height at the chosen lunar site beside two places on Earth
   over the same days.  No dependencies; hand-built SVG.

     window.SlipdayContrast.show(container, opts)
       container   element or element id
       opts        { site: 'shackleton' } or { lat, lon, name }, with start (ISO date-time, required),
                   days (7 to 120, default 60), mast_m (default 2), terrain (default true)
       returns a Promise that resolves to the /api/contrast answer once the view is drawn

   What is what (also printed under the chart): the lunar curve is this app's model on NASA data (JPL DE421,
   LOLA skyline), model output and not an observation; the two Earth curves come from a textbook
   solar-position formula and are there for comparison only. */
(function () {
  'use strict';
  var SVGNS = 'http://www.w3.org/2000/svg';
  var CSS = '.contrast{font-size:13px;color:var(--text,#0b0b0b)}' +
    '.contrast h3{font-size:15px;margin:0 0 4px}' +
    '.contrast .cxLead{margin:0 0 8px;color:var(--text2,#3a3a37);max-width:86ch}' +
    '.contrast svg{display:block;width:100%;height:auto;max-width:980px}' +
    '.contrast svg text{font-size: 12px;fill:var(--muted,#7b7a74)}' +
    '.contrast .cxGrid{stroke:var(--grid,#e9e7e0);stroke-width:1}' +
    '.contrast .cxZero{stroke:var(--sky,#8d8b82);stroke-width:1;stroke-dasharray:4 3}' +
    '.contrast .cxMoon{fill:none;stroke:var(--sun,#eb6834);stroke-width:2.4}' +
    '.contrast .cxTown{fill:none;stroke:var(--earth,#2a78d6);stroke-width:1;opacity:.75}' +
    '.contrast .cxPole{fill:none;stroke:var(--earth,#2a78d6);stroke-width:2;stroke-dasharray:6 3}' +
    '.contrast .cxSky{fill:var(--skyfill,#cfcdc4);stroke:var(--sky,#8d8b82);stroke-width:1}' +
    '.contrast .cxDark{fill:var(--night,#e4e2da)}' +
    '.contrast .cxLegend{display:flex;flex-wrap:wrap;gap:4px 16px;margin:4px 0 8px;font-size:12px;color:var(--text2,#3a3a37)}' +
    '.contrast .cxLegend i{display:inline-block;width:22px;height:0;border-top:3px solid;margin-right:5px;vertical-align:3px}' +
    '.contrast .cxLegend i.m{border-color:var(--sun,#eb6834)}.contrast .cxLegend i.t{border-color:var(--earth,#2a78d6);border-top-width:1px}' +
    '.contrast .cxLegend i.p{border-color:var(--earth,#2a78d6);border-top-style:dashed}' +
    '.contrast .cxLegend i.s{border-color:var(--sky,#8d8b82);border-top-width:6px}' +
    '.contrast .cxFacts{max-width:980px;margin:6px 0}' +
    '.contrast .cxF{display:grid;grid-template-columns:190px minmax(0,250px) minmax(0,1fr) 130px;gap:1px 14px;padding:5px 0;border-top:1px solid var(--line,#dddbd3);font-size:12.5px}' +
    '.contrast .cxF.cxHead{border-top:0;font-weight:600;color:var(--muted,#7b7a74);padding-bottom:2px}' +
    '.contrast .cxM{font-weight:600}' +
    '.contrast .cxF small{grid-column:3;color:var(--muted,#7b7a74);font-size: 12px}' +
    '.contrast .cxKind{color:var(--muted,#7b7a74);font-size: 12px;grid-column:4;grid-row:1}' +
    '.contrast .cxNote{display:block;color:var(--muted,#7b7a74);font-size: 12px;margin:4px 0 0;max-width:110ch}' +
    '@media (max-width:600px){' +
    '.contrast .cxF{grid-template-columns:minmax(0,1fr) minmax(0,1fr);gap:1px 10px}' +
    '.contrast .cxF.cxHead{display:none}' +
    '.contrast .cxK{grid-column:1/3;font-weight:600}' +
    '.contrast .cxM::before{content:"here: ";font-weight:400;color:var(--muted,#7b7a74)}' +
    '.contrast .cxE::before{content:"on Earth: ";color:var(--muted,#7b7a74)}' +
    '.contrast .cxF small{grid-column:1/3}' +
    '.contrast .cxKind{grid-column:1/3;grid-row:auto}' +
    '.contrast .cxKind::before{content:"source: "}}';
  function esc(s) {
    return String(s).replace(/[&<>"']/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
    });
  }
  function el(tag, attrs, text) {
    var n = document.createElementNS(SVGNS, tag);
    for (var k in attrs) { n.setAttribute(k, attrs[k]); }
    if (text !== undefined) { n.textContent = text; }
    return n;
  }
  function path(vals, sx, sy) {
    var d = '';
    for (var i = 0; i < vals.length; i++) { d += (i ? 'L' : 'M') + sx(i).toFixed(1) + ' ' + sy(vals[i]).toFixed(1); }
    return d;
  }
  function niceStep(span) { var s = [0.5, 1, 2, 5, 10, 20, 30, 45], i = 0; while (i < s.length - 1 && span / s[i] > 7) { i++; } return s[i]; }
  var MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
  function dayLabel(unix) { var d = new Date(unix * 1000); return d.getUTCDate() + ' ' + MONTHS[d.getUTCMonth()]; }

  function chart(c, W, H, lo, hi, draw, label) {
    var P = { l: 40, r: 10, t: 10, b: 22 }, n = c.count;
    var sx = function (i) { return P.l + i / (n - 1) * (W - P.l - P.r); };
    var sy = function (v) { return H - P.b - (Math.max(lo, Math.min(hi, v)) - lo) / (hi - lo) * (H - P.t - P.b); };
    var svg = el('svg', { viewBox: '0 0 ' + W + ' ' + H, role: 'img', 'aria-label': label });
    var step = niceStep(hi - lo);
    for (var v = Math.ceil(lo / step) * step; v <= hi + 1e-9; v += step) {
      svg.appendChild(el('line', { x1: P.l, x2: W - P.r, y1: sy(v), y2: sy(v), 'class': Math.abs(v) < 1e-9 ? 'cxZero' : 'cxGrid' }));
      svg.appendChild(el('text', { x: P.l - 5, y: sy(v) + 4, 'text-anchor': 'end' }, (v > 0 ? '+' : '') + v + '°'));
    }
    var every = Math.max(1, Math.round(c.days / 6)) * 24;
    for (var i = 0; i < n; i += every) {
      svg.appendChild(el('text', { x: sx(i), y: H - 6, 'text-anchor': i === 0 ? 'start' : 'middle' }, dayLabel(c.start_unix + i * 3600)));
    }
    draw(svg, sx, sy, P);
    return svg;
  }

  function render(box, c) {
    if (!document.getElementById('slipdayContrastCss')) {
      var st = document.createElement('style'); st.id = 'slipdayContrastCss'; st.textContent = CSS; document.head.appendChild(st);
    }
    var m = c.moon, same = c.earth[0], town = c.earth[1], narrow = (box.clientWidth || 900) < 600;
    var W = narrow ? 360 : 900;
    box.className = (box.className ? box.className + ' ' : '') + 'contrast';
    box.innerHTML = '<h3>The same ' + Math.round(c.days) + ' days here and on Earth</h3>' +
      '<p class="cxLead">The Sun\'s height above the level horizon at <b>' + esc(m.label) + '</b>, at a place on Earth at the same latitude, ' +
      'and at a town at 45° N. On Earth the Sun climbs and falls every day. ' +
      (m.max_sun_el - m.min_sun_el < 12 ? 'Here it stays within ' + (m.max_sun_el - m.min_sun_el).toFixed(1) + '° of height for the whole span, so the terrain skyline decides when there is light.'
        : 'Here one day and night takes 29.5 Earth days, and there is no twilight at either end.') + '</p>' +
      '<div class="cxLegend"><span><i class="m"></i>Sun at the lunar site (derived: JPL DE421)</span>' +
      '<span><i class="p"></i>Sun on Earth, same latitude (textbook formula)</span>' +
      '<span><i class="t"></i>Sun on Earth, 45° N (textbook formula)</span></div><div class="cxA"></div>' +
      '<div class="cxLegend" style="margin-top:8px"><span><i class="m"></i>the lunar curve again, magnified</span>' +
      '<span><i class="s"></i>' + (m.terrain ? 'terrain skyline under the Sun (derived: LOLA)' : 'smooth-sphere horizon (no terrain data here)') + '</span>' +
      '<span>shaded: Sun down by this app\'s rule</span></div><div class="cxB"></div><div class="cxT"></div>';
    var lo = Math.min(-10, Math.floor(Math.min(m.min_sun_el, same.min_sun_el, town.min_sun_el) / 10) * 10);
    var hi = Math.max(10, Math.ceil(Math.max(m.max_sun_el, same.max_sun_el, town.max_sun_el) / 10) * 10);
    box.querySelector('.cxA').appendChild(chart(c, W, narrow ? 190 : 210, lo, hi, function (svg, sx, sy) {
      svg.appendChild(el('path', { d: path(town.sun_el, sx, sy), 'class': 'cxTown' }));
      svg.appendChild(el('path', { d: path(same.sun_el, sx, sy), 'class': 'cxPole' }));
      svg.appendChild(el('path', { d: path(m.sun_el, sx, sy), 'class': 'cxMoon' }));
    }, 'Sun elevation over ' + Math.round(c.days) + ' days at the lunar site and at two places on Earth'));
    /* the lunar curve by itself, on its own scale, against the skyline under the Sun */
    var sk = m.skyline_under_sun, lo2 = Infinity, hi2 = -Infinity;
    m.sun_el.forEach(function (v, i) { lo2 = Math.min(lo2, v, sk[i]); hi2 = Math.max(hi2, v, sk[i]); });
    var pad = Math.max(0.5, (hi2 - lo2) * 0.12); lo2 = Math.floor((lo2 - pad) * 2) / 2; hi2 = Math.ceil((hi2 + pad) * 2) / 2;
    box.querySelector('.cxB').appendChild(chart(c, W, narrow ? 150 : 160, lo2, hi2, function (svg, sx, sy, P) {
      var i = 0, n = c.count, H = narrow ? 150 : 160;
      while (i < n) {                                   /* shade the hours the app counts as dark */
        if (m.sun_up[i]) { i++; continue; }
        var j = i; while (j < n && !m.sun_up[j]) { j++; }
        svg.insertBefore(el('rect', { x: sx(i), y: P.t, width: Math.max(1, sx(Math.min(j, n - 1)) - sx(i)), height: H - P.t - P.b, 'class': 'cxDark' }), svg.firstChild);
        i = j;
      }
      var d = 'M' + sx(0).toFixed(1) + ' ' + (H - P.b);
      sk.forEach(function (v, k) { d += 'L' + sx(k).toFixed(1) + ' ' + sy(v).toFixed(1); });
      svg.appendChild(el('path', { d: d + 'L' + sx(n - 1).toFixed(1) + ' ' + (H - P.b) + 'Z', 'class': 'cxSky' }));
      svg.appendChild(el('path', { d: path(m.sun_el, sx, sy), 'class': 'cxMoon' }));
    }, 'The lunar Sun elevation magnified, against the skyline under the Sun'));
    var rows = '<div class="cxF cxHead"><span></span><span>At this lunar site</span><span>On Earth</span><span>Source</span></div>';
    c.facts.forEach(function (f) {
      rows += '<div class="cxF"><span class="cxK">' + esc(f.k) + '</span><span class="cxM">' + esc(f.moon) + '</span><span class="cxE">' + esc(f.earth) +
        '</span><span class="cxKind">' + esc(f.kind) + '</span><small>' + esc(f.note) + '</small></div>';
    });
    box.querySelector('.cxT').innerHTML = '<div class="cxFacts">' + rows + '</div><p class="cxNote">' + esc(c.notes.moon) + ' ' + esc(c.notes.earth) +
      ' Source column: derived = ' + esc(c.notes.kinds.derived) + '; formula = ' + esc(c.notes.kinds.formula) + '; constant = ' + esc(c.notes.kinds.constant) + '.</p>';
  }

  /* opts: { site: 'shackleton' } or { lat, lon, name }, plus start (ISO, required), days (7 to 120, default 60),
     mast_m (default 2), terrain (default true) */
  function show(container, opts) {
    var box = typeof container === 'string' ? document.getElementById(container) : container;
    opts = opts || {};
    if (!box || !opts.start) { return Promise.reject(new Error('a container and a start date are needed')); }
    var id = opts.site || opts.id;
    var q = 'start=' + encodeURIComponent(opts.start) + '&days=' + (opts.days || 60) + '&mast_m=' + (opts.mast_m === undefined ? 2 : opts.mast_m) +
      '&terrain=' + (opts.terrain === false ? 'false' : 'true') +
      (id ? '&site=' + encodeURIComponent(id)
        : '&lat=' + opts.lat + '&lon=' + opts.lon + (opts.name ? '&name=' + encodeURIComponent(opts.name) : ''));
    box.setAttribute('aria-busy', 'true');
    return fetch('/api/contrast?' + q).then(function (r) {
      return r.json().then(function (j) {
        if (!r.ok) { throw new Error(typeof j.detail === 'string' ? j.detail : JSON.stringify(j.detail)); }
        return j;
      });
    }).then(function (c) { render(box, c); box.removeAttribute('aria-busy'); return c; })
      .catch(function (e) {
        box.removeAttribute('aria-busy');
        box.innerHTML = '<p class="note">The lunar and terrestrial comparison is not available: ' + esc(e.message) + '</p>';
        throw e;
      });
  }
  window.SlipdayContrast = { show: show, render: render };
})();
