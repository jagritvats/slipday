/* Slipday add-on: "Chance of a safe touchdown"

   Include with one container and one script tag:
     <div id="addon-safetouch"></div>                       (in the "Flat enough to land?" panel, #safetyPanel)
     <script src="/static/addons/safetouch.js"></script>    (after /static/app.js)

   What it shows, for the site on the card:
     - per lander class (precision, CLPS-class, unguided): the chance that the ground under the lander is within
       8 degrees of level (NASA's limit) and within 5 degrees (NASA's goal), with the range, and what NASA's
       2-degree slope uncertainty does to it;
     - the patch of ground around the aim point coloured by slope, with the landing spread drawn over it;
     - a better aim point within 200 m, if one clearly does better and keeps the slip margin.
   Only where NASA's 5 m terrain exists; elsewhere it says plainly that 80 m terrain is too coarse.

   It reads nothing private from app.js.  It watches the page's own requests to /api/mission (answers are cloned,
   never changed) and asks GET /api/addons/safetouch/site?lat=&lon=&name=.  No library.  Works at phone width.
*/
(function () {
  'use strict';
  var $ = function (id) { return document.getElementById(id); };
  var missions = [], ui = {}, key = '', data = null, cache = {}, cls = 'precision';

  function esc(s) {
    return String(s).replace(/[&<>"']/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]; });
  }
  /* a share in per cent; "100 %" only when every draw passed (all = true), never from rounding */
  function pct(x, all) {
    if (x === null || x === undefined) { return '–'; }
    if (x >= 100) { return all === false ? 'over 99.9 %' : '100 %'; }
    if (x >= 99.5 || x < 1) { return x.toFixed(1) + ' %'; }
    return Math.round(x) + ' %';
  }
  function every(c, k) { return c[k + '_count'] === undefined ? undefined : c[k + '_count'] === c.draws_used; }
  function rng(r) { return r && r[0] !== null ? r[0].toFixed(1) + ' to ' + r[1].toFixed(1) + ' %' : '–'; }
  function km(m) { return m >= 1000 ? (m / 1000).toFixed(m % 1000 ? 1 : 0) + ' km' : Math.round(m) + ' m'; }

  /* ---------- watch the page's site card ---------- */
  if (window.fetch) {
    var orig = window.fetch.bind(window);
    window.fetch = function (input, init) {
      var p = orig(input, init);
      try {
        var url = typeof input === 'string' ? input : (input && input.url) || '';
        var bare = url.replace(/^[a-z]+:\/\/[^/]+/i, '').split('?')[0];
        var mine = init && init.headers && init.headers['X-Slipday-Addon'];
        if (!mine && bare === '/api/mission') {
          p.then(function (r) {
            if (!r.ok) { return; }
            r.clone().json().then(function (j) {
              if (!j || !j.site) { return; }
              missions = missions.filter(function (m) { return m.site.name !== j.site.name; });
              missions.push(j);
              update();
            }).catch(function () {});
          }).catch(function () {});
        }
      } catch (e) { /* never get in the page's way */ }
      return p;
    };
  }
  function current() {
    var sel = $('mSite');
    var name = sel && sel.selectedIndex >= 0 && sel.options[sel.selectedIndex] ? sel.options[sel.selectedIndex].text : null;
    var hit = null;
    missions.forEach(function (m) { if (name !== null && m.site.name === name) { hit = m; } });
    if (!hit && missions.length && (name === null || !sel)) { hit = missions[missions.length - 1]; }
    return hit;
  }

  /* ---------- styles ---------- */
  function css() {
    if ($('sdT-style')) { return; }
    var s = document.createElement('style');
    s.id = 'sdT-style';
    s.textContent =
      '#addon-safetouch{min-width:0;max-width:100%}' +
      '.sdT{min-width:0;overflow-wrap:anywhere;margin:.6rem 0 0;padding:.6rem .75rem;border:1px solid var(--line,#dddbd3);border-radius:8px;background:var(--surface,#fcfcfb);color:var(--text,#0b0b0b);font-size:.95rem;line-height:1.4;box-sizing:border-box}' +
      '.sdT h3{font-size:1rem;margin:0 0 .3rem;font-weight:700}' +
      '.sdT-sub{color:var(--muted,#7b7a74);font-size:.85rem;margin:.3rem 0 0}' +
      '.sdT-cls{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,13rem),1fr));gap:.5rem;margin:.4rem 0}' +
      '.sdT-c{border:1px solid var(--grid,#e9e7e0);border-radius:6px;padding:.45rem .55rem;min-width:0}' +
      '.sdT-c b.big{font-size:1.25rem;font-variant-numeric:tabular-nums}' +
      '.sdT-c .nm{font-weight:600}.sdT-c .sp{color:var(--muted,#7b7a74);font-size:.82rem}' +
      '.sdT-c .row{display:flex;flex-wrap:wrap;gap:.1rem .6rem;align-items:baseline;margin-top:.15rem}' +
      '.sdT-c .unc{font-size:.82rem;margin-top:.2rem}' +
      '.sdT details{margin-top:.4rem}.sdT summary{cursor:pointer;min-height:36px;display:flex;align-items:center;font-weight:600}' +
      '.sdT-tabs{display:flex;flex-wrap:wrap;gap:.35rem;margin:.3rem 0}' +
      '.sdT-tabs button{min-height:36px;padding:.25rem .7rem;border:1px solid var(--line,#dddbd3);border-radius:18px;background:transparent;color:var(--text,#0b0b0b);font:inherit;font-size:.88rem;cursor:pointer}' +
      '.sdT-tabs button[aria-pressed="true"]{background:var(--accent,#0e3f7e);border-color:var(--accent,#0e3f7e);color:var(--surface,#fff)}' +
      '.sdT-pic{display:flex;flex-wrap:wrap;gap:.6rem;align-items:flex-start}' +
      '.sdT canvas{width:100%;max-width:420px;height:auto;aspect-ratio:1/1;border-radius:4px;touch-action:manipulation;display:block}' +
      '.sdT-side{flex:1 1 14rem;min-width:0}' +
      '.sdT-leg{display:flex;flex-wrap:wrap;gap:.2rem .8rem;font-size:.82rem;margin:.2rem 0}' +
      '.sdT-sw{display:inline-block;width:12px;height:12px;vertical-align:-1px;margin-right:.3rem;border-radius:2px}' +
      '.sdT-hov{font-size:.85rem;min-height:1.3em;color:var(--muted,#7b7a74)}' +
      '.sdT-sug{margin:.35rem 0 0;padding:.35rem .5rem;border-left:3px solid var(--accent,#0e3f7e);background:var(--ok-bg,#e3eefb);color:var(--ok-ink,#0e3f7e);font-size:.88rem}' +
      '.sdT ul{margin:.2rem 0 0;padding-left:1.1rem}.sdT li{margin:.15rem 0;font-size:.85rem}' +
      '@media (max-width:760px){.sdT{font-size:.92rem;padding:.55rem .6rem}}';
    document.head.appendChild(s);
  }

  /* slope colours: within the 5 degree goal, between goal and limit, over the 8 degree limit, no 5 m terrain */
  var COL = { goal: [120, 196, 120], mid: [250, 178, 25], over: [208, 59, 59], none: [190, 188, 180] };

  /* ---------- fetch and draw ---------- */
  function update() {
    if (!ui.box) { return; }
    var m = current();
    if (!m) { if (!data) { ui.box.innerHTML = '<p class="sdT-sub">Chance of a safe touchdown: waiting for the site card…</p>'; } return; }
    var st = m.site, k = st.lat + ',' + st.lon;
    if (k === key) { return; }
    key = k;
    if (cache[k]) { data = cache[k]; render(); return; }
    ui.box.innerHTML = '<h3>Chance of a safe touchdown</h3><p class="sdT-sub">Working it out for ' + esc(st.name) + '…</p>';
    fetch('/api/addons/safetouch/site?lat=' + encodeURIComponent(st.lat) + '&lon=' + encodeURIComponent(st.lon) + '&name=' + encodeURIComponent(st.name),
      { headers: { 'X-Slipday-Addon': '1' } }).then(function (r) {
      return r.json().then(function (j) {
        if (!r.ok) { throw new Error(typeof j.detail === 'string' ? j.detail : 'The server could not answer (' + r.status + ').'); }
        return j;
      });
    }).then(function (j) {
      cache[k] = j;
      if (k !== key) { return; }
      data = j; render();
    }).catch(function (e) {
      if (k === key) { ui.box.innerHTML = '<h3>Chance of a safe touchdown</h3><p class="sdT-sub">Could not work it out: ' + esc(e.message) + '</p>'; }
    });
  }

  function classCard(c) {
    var spread = c.round ? '99 % of touchdowns within ' + km(c.within_99_pct_m) + ' of the aim'
      : '99 % within an oval about ' + km(2 * c.within_99_pct_m) + ' by ' + km(2 * c.within_99_pct_minor_m);
    if (!c.available) {
      return '<div class="sdT-c"><div class="nm">' + esc(c.label) + '</div><div class="sp">' + esc(spread) + '</div><div class="sdT-sub">' + esc(c.why) + '</div></div>';
    }
    var dir = c.p8_direction_span ? '<div class="sp">The long side of the oval can point any way: ' + c.p8_direction_span[0].toFixed(0) + ' to ' +
      c.p8_direction_span[1].toFixed(0) + ' % within 8°, depending on the direction (12 tried).</div>' : '';
    return '<div class="sdT-c"><div class="nm">' + esc(c.label) + '</div><div class="sp">' + esc(spread) + ' (' + esc(c.source) + ')</div>' +
      '<div class="row"><span>Within 8°: <b class="big">' + pct(c.p8, every(c, 'p8')) + '</b></span><span>Within 5°: <b class="big">' + pct(c.p5, every(c, 'p5')) + '</b></span></div>' +
      '<div class="sp">Range: ' + rng(c.p8_range) + ' and ' + rng(c.p5_range) + '.</div>' + dir +
      '<div class="unc">If NASA’s slopes are 2° off: <b>' + pct(c.p8_if_steeper, every(c, 'p8_if_steeper')) + ' to ' + pct(c.p8_if_flatter, every(c, 'p8_if_flatter')) +
      '</b> within 8°, <b>' + pct(c.p5_if_steeper, every(c, 'p5_if_steeper')) + ' to ' + pct(c.p5_if_flatter, every(c, 'p5_if_flatter')) + '</b> within 5°.</div></div>';
  }

  function suggestionText(c) {
    var s = c && c.suggestion;
    if (!c || !c.available || !s) { return ''; }
    if (s.offered) {
      return '<p class="sdT-sug"><b>A better aim point (a suggestion, not a site study):</b> ' + s.lat.toFixed(4) + ', ' + s.lon.toFixed(4) + ', ' +
        Math.round(s.distance_m) + ' m from the planned site (the ★ on the picture). For this lander it raises the chance within 8° from ' + pct(c.p8) +
        ' to ' + pct(s.p8) + ' (range ' + rng(s.p8_range) + ') and within 5° to ' + pct(s.p5) + '. ' +
        (s.slip_checked ? 'The slip-margin check gives the same answer there: ' + esc(s.slip.verdict) + ', ' + s.slip.slip_margin_days + ' days of slip.' :
          'The slip margin was not checked there.') + ' It looks only at slope and the slip margin, nothing else a site study checks.</p>';
    }
    return '<p class="sdT-sub"><b>Better aim point:</b> none suggested for this lander. ' + esc(s.why || '') + '</p>';
  }

  function render() {
    var r = data;
    if (!r.available) {
      ui.box.innerHTML = '<h3>Chance of a safe touchdown</h3><p class="sdT-sub">' + esc(r.reason || 'Not available.') + '</p>';
      return;
    }
    var avail = r.classes.filter(function (c) { return c.available; });
    if (!avail.some(function (c) { return c.id === cls; }) && avail.length) { cls = avail[0].id; }
    var tabs = r.classes.map(function (c) {
      return '<button type="button" data-c="' + esc(c.id) + '" aria-pressed="' + (c.id === cls) + '"' + (c.available ? '' : ' disabled') + '>' + esc(c.label) + '</button>';
    }).join('');
    ui.box.innerHTML =
      '<h3>Chance of a safe touchdown</h3>' +
      '<p class="sdT-sub" style="margin-top:0">Aim at ' + esc(r.site.name) + ': the chance that the ground under the lander is within NASA’s 8° limit (and its 5° goal), for three lander accuracies. From ' +
      esc(r.grid.label) + ', slope over ' + r.grid.baseline_m + ' m.</p>' +
      '<div class="sdT-cls">' + r.classes.map(classCard).join('') + '</div>' +
      '<details id="sdT-more"><summary>Show the ground and the landing spread</summary>' +
      '<div class="sdT-tabs" role="group" aria-label="Lander">' + tabs + '</div>' +
      '<div class="sdT-pic"><canvas id="sdT-cv" width="480" height="480" role="img" aria-label="Slope around the aim point with the landing spread"></canvas>' +
      '<div class="sdT-side"><div class="sdT-leg">' +
      '<span><i class="sdT-sw" style="background:rgb(' + COL.goal + ')"></i>within 5°</span>' +
      '<span><i class="sdT-sw" style="background:rgb(' + COL.mid + ')"></i>5° to 8°</span>' +
      '<span><i class="sdT-sw" style="background:rgb(' + COL.over + ')"></i>over 8°</span>' +
      '<span><i class="sdT-sw" style="background:rgb(' + COL.none + ')"></i>no 5 m terrain</span></div>' +
      '<div id="sdT-cap" class="sdT-sub"></div><div id="sdT-hov" class="sdT-hov" aria-live="polite"></div><div id="sdT-sug"></div></div></div></details>' +
      '<details><summary>How it is worked out, and what it cannot tell</summary>' +
      '<p class="sdT-sub">' + esc(r.how) + ' The range is the 95 % range from the random draws (and, for the unguided lander, the 12 directions of its oval). ' +
      'The “2° off” figures repeat the count with every slope 2° steeper, then 2° flatter, because NASA gives its 5 m slope maps about 2° of uncertainty per point. ' +
      'A better aim point is looked for on a 10 m grid within ' + r.aim_radius_m + ' m of the planned site; it is offered only if it does clearly better and the page’s own slip check (landing ' +
      esc(r.slip_rules.landing.slice(0, 10)) + ', the default need) gives the same verdict and at least the same days of slip.</p>' +
      '<ul>' + r.limits.map(function (t) { return '<li>' + esc(t) + '</li>'; }).join('') + '</ul></details>';
    Array.prototype.forEach.call(ui.box.querySelectorAll('.sdT-tabs button'), function (b) {
      b.addEventListener('click', function () { cls = b.getAttribute('data-c'); render(); var d = $('sdT-more'); if (d) { d.open = true; } });
    });
    var more = $('sdT-more');
    if (more) { more.open = !!ui.open; more.addEventListener('toggle', function () { ui.open = more.open; if (more.open) { draw(); } }); }
    if (ui.open) { draw(); }
  }

  function picture(c) { return c.id === 'precision' ? data.picture.near : data.picture.wide; }

  var decoded = {};
  function bytes(p) {
    var k = key + p.half_m;
    if (decoded[k]) { return decoded[k]; }
    var b = atob(p.data), a = new Uint8Array(b.length);
    for (var i = 0; i < b.length; i++) { a[i] = b.charCodeAt(i); }
    decoded[k] = a;
    return a;
  }

  function draw() {
    var cv = $('sdT-cv');
    if (!cv || !data || !data.available) { return; }
    var c = data.classes.filter(function (x) { return x.id === cls; })[0];
    if (!c || !c.available) { return; }
    var p = picture(c), n = p.n, a = bytes(p);
    var off = document.createElement('canvas'); off.width = n; off.height = n;
    var octx = off.getContext('2d'), img = octx.createImageData(n, n);
    for (var i = 0; i < n * n; i++) {
      var v = a[i], col = v === 255 ? COL.none : v <= 50 ? COL.goal : v <= 80 ? COL.mid : COL.over;
      var shade = v === 255 ? 1 : 1 - Math.min(v, 250) / 1000;     /* steeper ground slightly darker inside each colour */
      img.data[4 * i] = col[0] * shade; img.data[4 * i + 1] = col[1] * shade; img.data[4 * i + 2] = col[2] * shade; img.data[4 * i + 3] = 255;
    }
    octx.putImageData(img, 0, 0);
    var W = cv.width, ctx = cv.getContext('2d');
    ctx.imageSmoothingEnabled = false;
    ctx.clearRect(0, 0, W, W);
    ctx.drawImage(off, 0, 0, W, W);
    var span = 2 * p.half_m + p.step_m, s = W / span;               /* canvas pixels per metre */
    var ax = W / 2 + data.picture.aim_cell_offset_m[0] * s, ay = W / 2 - data.picture.aim_cell_offset_m[1] * s;
    ctx.lineWidth = 2;
    function ring(rm, dash, colr) {
      ctx.save(); ctx.setLineDash(dash); ctx.strokeStyle = colr; ctx.beginPath(); ctx.arc(ax, ay, rm * s, 0, 2 * Math.PI); ctx.stroke(); ctx.restore();
    }
    /* the landing spread: 99 % of touchdowns inside */
    if (c.round) { ring(c.within_99_pct_m, [], '#111'); ring(c.within_99_pct_m, [6, 6], '#fff'); }
    else { ring(c.within_99_pct_minor_m, [], '#111'); ring(c.within_99_pct_m, [8, 6], '#111'); }
    if (c.id === 'precision') { ring(data.aim_radius_m, [2, 5], 'rgba(17,17,17,.7)'); }
    /* aim point */
    ctx.strokeStyle = '#111'; ctx.lineWidth = 3;
    ctx.beginPath(); ctx.moveTo(ax - 9, ay); ctx.lineTo(ax + 9, ay); ctx.moveTo(ax, ay - 9); ctx.lineTo(ax, ay + 9); ctx.stroke();
    ctx.strokeStyle = '#fff'; ctx.lineWidth = 1.2;
    ctx.beginPath(); ctx.moveTo(ax - 8, ay); ctx.lineTo(ax + 8, ay); ctx.moveTo(ax, ay - 8); ctx.lineTo(ax, ay + 8); ctx.stroke();
    /* suggested aim point */
    var sg = c.suggestion;
    if (sg && sg.offered) {
      var sx = ax + sg.dx_m * s, sy = ay - sg.dy_m * s;
      ctx.font = 'bold 22px system-ui, sans-serif'; ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
      ctx.lineWidth = 3; ctx.strokeStyle = '#111'; ctx.strokeText('★', sx, sy); ctx.fillStyle = '#fff'; ctx.fillText('★', sx, sy);
    }
    /* scale bar and the direction of the pole */
    var bar = c.id === 'precision' ? 100 : 1000, bx = 14, by = W - 18;
    ctx.fillStyle = 'rgba(255,255,255,.85)'; ctx.fillRect(bx - 6, by - 20, bar * s + 12, 28);
    ctx.fillStyle = '#111'; ctx.fillRect(bx, by, bar * s, 4);
    ctx.font = '14px system-ui, sans-serif'; ctx.textAlign = 'left'; ctx.textBaseline = 'alphabetic'; ctx.fillText(km(bar), bx, by - 5);
    var pd = data.picture.pole_dir, px0 = W - 40, py0 = 40;
    ctx.fillStyle = 'rgba(255,255,255,.85)'; ctx.beginPath(); ctx.arc(px0, py0, 30, 0, 2 * Math.PI); ctx.fill();
    ctx.strokeStyle = '#111'; ctx.lineWidth = 2.5; ctx.beginPath(); ctx.moveTo(px0 - pd[0] * 18, py0 - pd[1] * 18); ctx.lineTo(px0 + pd[0] * 18, py0 + pd[1] * 18); ctx.stroke();
    ctx.beginPath(); ctx.arc(px0 + pd[0] * 18, py0 + pd[1] * 18, 4, 0, 2 * Math.PI); ctx.fillStyle = '#111'; ctx.fill();
    ctx.font = '11px system-ui, sans-serif'; ctx.textAlign = 'center'; ctx.fillText('pole', px0, py0 + 26);

    var cap = 'Ground ' + km(2 * p.half_m) + ' across around the aim point (+), coloured by the slope under a lander' +
      (p.every_nth_cell > 1 ? ' (one 5 m cell in every ' + p.every_nth_cell + ' each way is shown; the chances use every cell)' : '') + '. ' +
      (c.round ? 'The ring holds 99 % of this lander’s touchdowns.' : 'The inner ring is the short side of the oval, the dashed ring the long side; the oval can point any way.') +
      (c.id === 'precision' ? ' The dotted ring is the ' + data.aim_radius_m + ' m searched for a better aim point.' : '') +
      ' The arrow points toward the south pole.';
    $('sdT-cap').textContent = cap;
    $('sdT-sug').innerHTML = suggestionText(c);
    if (!cv.getAttribute('data-sdT')) {
      cv.setAttribute('data-sdT', '1');
      var hov = function (ev) {
        var cc = data && data.classes.filter(function (x) { return x.id === cls; })[0];
        if (!cc) { return; }
        var pp = picture(cc), r = cv.getBoundingClientRect();
        var col = Math.floor((ev.clientX - r.left) / r.width * pp.n), row = Math.floor((ev.clientY - r.top) / r.height * pp.n);
        if (col < 0 || row < 0 || col >= pp.n || row >= pp.n) { return; }
        var v = bytes(pp)[row * pp.n + col];
        $('sdT-hov').textContent = v === 255 ? 'No 5 m terrain here.' : 'Slope here: ' + (v / 10).toFixed(1) + '°' + (v > 80 ? ', over the 8° limit.' : v > 50 ? ', within 8° but over the 5° goal.' : ', within the 5° goal.');
      };
      cv.addEventListener('pointermove', hov);
      cv.addEventListener('pointerdown', hov);
    }
  }

  /* ---------- start ---------- */
  function init() {
    css();
    var root = $('addon-safetouch');
    if (!root) { return; }
    root.innerHTML = '<div class="sdT" id="sdT-box" aria-live="polite"><p class="sdT-sub">Chance of a safe touchdown: waiting for the site card…</p></div>';
    ui.box = $('sdT-box');
    var sel = $('mSite');
    if (sel) { sel.addEventListener('change', function () { setTimeout(update, 0); }); }
    var out = $('missionOut');
    if (out && window.MutationObserver) {
      var t = null;
      new MutationObserver(function () { clearTimeout(t); t = setTimeout(update, 300); }).observe(out, { childList: true });
    }
    update();
  }
  if (document.readyState === 'loading') { document.addEventListener('DOMContentLoaded', init); } else { init(); }
  window.SlipdaySafeTouch = { refresh: update, state: function () { return { data: data, cls: cls }; } };
})();
