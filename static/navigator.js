/* Slipday navigator: the core flow of the challenge on the first screen.
   1. choose a site (search, grouped list, the map, or your own coordinates);
   2. choose a date and time (date, hour and quick steps);
   3. read the Sun and the Earth against the real skyline, hour by hour, with a scrubber and Play;
   and compare up to four sites side by side.
   Every number comes from the server: /api/sites, /api/mission (verdict, hours, next good dates), /api/why (the hourly
   Sun and Earth track and the 360-degree skyline) and /api/addons/safety/site (slope).  The page's own site list and
   plan are used through window.SlipdayApp (app.js), so the navigator and the planner's view always agree. */
(function () {
  'use strict';
  var $ = function (id) { return document.getElementById(id); };
  var SVGNS = 'http://www.w3.org/2000/svg';
  var MON = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
  var LUNAR_DAY_MS = 29.530589 * 86400000;
  var GROUPS = [
    ['South pole', 'South pole candidates'],
    ['Apollo', 'Apollo landing sites'],
    ['CLPS', 'CLPS and commercial landers'],
    ['Other nations', 'Other nations: Chang’e, Chandrayaan, SLIM'],
    ['Reference', 'Reference points']
  ];
  var WORD = { yes: 'Yes', 'not sure': 'Not sure', no: 'No', 'n/a': 'Not worked out' };
  var ICON = { yes: '✓', 'not sure': '?', no: '✕', 'n/a': '–' };
  var C16 = ['N', 'NNE', 'NE', 'ENE', 'E', 'ESE', 'SE', 'SSE', 'S', 'SSW', 'SW', 'WSW', 'W', 'WNW', 'NW', 'NNW'];
  /* the learned estimate is used only when the server lists its endpoint (so an unregistered one never shows a 404) */
  var ESTIMATE_ON = false, SKYFAST_ON = false, estimateAsked = false;
  function checkEstimate() {
    if (estimateAsked) { return; }
    estimateAsked = true;
    fetch('/openapi.json').then(function (r) { return r.ok ? r.json() : null; }).then(function (o) {
      if (o && o.paths && o.paths['/api/addons/estimate']) { ESTIMATE_ON = true; renderVerdict(); }
      if (o && o.paths && o.paths['/api/addons/skyfast']) { SKYFAST_ON = true; }
    }).catch(function () {});
  }
  /* a number from the estimate's own test report: the share of verdicts it got right on held-out clicks */
  function estAccuracy(est) {
    var ma = est && est.measured_accuracy;
    if (ma && typeof ma.verdict_accuracy === 'number') { return (ma.verdict_accuracy <= 1 ? Math.round(ma.verdict_accuracy * 1000) / 10 : ma.verdict_accuracy) + ' %'; }
    var found = null;
    (function walk(o, path) {
      if (found !== null || !o || typeof o !== 'object') { return; }
      Object.keys(o).forEach(function (k) {
        var v = o[k], pth = path + '/' + k;
        if (found === null && typeof v === 'number' && /verdict.*acc|acc.*verdict/i.test(k) && /served|model|shipped|this/i.test(pth) && !/nearest|neighbour|always/i.test(pth)) { found = v; }
        else if (typeof v === 'object') { walk(v, pth); }
      });
    })(est.measured_accuracy, '');
    if (found === null) { return null; }
    return (found <= 1 ? Math.round(found * 1000) / 10 : Math.round(found * 10) / 10) + ' %';
  }
  var REDUCED = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  var nv = { why: null, whyKey: '', hour: 0, playing: null, filter: '', cmp: {}, safety: {}, lastSel: '' };

  function esc(s) {
    return String(s).replace(/[&<>"']/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]; });
  }
  function el(tag, attrs, text) {
    var n = document.createElementNS(SVGNS, tag);
    for (var k in attrs) { n.setAttribute(k, attrs[k]); }
    if (text !== undefined) { n.textContent = text; }
    return n;
  }
  function norm(az) { return ((az % 360) + 360) % 360; }
  function compass(az) { return C16[Math.round(norm(az) / 22.5) % 16]; }
  function fmtWhen(ms) {
    var d = new Date(ms);
    return d.getUTCDate() + ' ' + MON[d.getUTCMonth()] + ' ' + d.getUTCFullYear() + ', ' + ('0' + d.getUTCHours()).slice(-2) + ':' + ('0' + d.getUTCMinutes()).slice(-2) + ' UTC';
  }
  function fmtDay(iso) { var d = new Date(Date.parse(iso)); return d.getUTCDate() + ' ' + MON[d.getUTCMonth()] + (d.getUTCHours() ? ' ' + ('0' + d.getUTCHours()).slice(-2) + ':00' : ''); }
  function span(h) { return h < 72 ? (Math.round(h * 10) / 10) + ' h' : (h / 24).toFixed(1) + ' days'; }
  function plural(n, w) { return n + ' ' + w + (n === 1 ? '' : 's'); }
  function latLon(lat, lon) { return Math.abs(lat).toFixed(3) + '° ' + (lat < 0 ? 'S' : 'N') + ', ' + Math.abs(lon).toFixed(3) + '° ' + (lon < 0 ? 'W' : 'E'); }
  function app() { return window.SlipdayApp; }
  /* the navigator's own requests are marked, so the add-ons that follow the main card do not mistake them for it */
  function napi(path, body) {
    var opt = body ? { method: 'POST', headers: { 'Content-Type': 'application/json', 'X-Slipday-Addon': '1' }, body: JSON.stringify(body) } : { headers: { 'X-Slipday-Addon': '1' } };
    return fetch(path, opt).then(function (r) {
      return r.json().then(function (j) {
        if (!r.ok) { throw new Error(typeof j.detail === 'string' ? j.detail : 'The server could not answer (' + r.status + ').'); }
        return j;
      });
    });
  }
  /* the friendly name from the API (catalog or the mission answer), with its subtitle; the internal name stays as it is */
  function nameOf(s, m) {
    var A = app(), c = s && s.id && A ? A.catalog().filter(function (x) { return x.id === s.id; })[0] : null;
    var f = (c && c.friendly_name) || (m && m.site && m.site.friendly_name) || (s && s.friendly_name);
    return f || (s ? s.name : '');
  }
  function subOf(s, m) {
    var A = app(), c = s && s.id && A ? A.catalog().filter(function (x) { return x.id === s.id; })[0] : null;
    return (c && c.subtitle) || (m && m.site && m.site.subtitle) || (s ? latLon(s.lat, s.lon) : '');
  }
  function siteKey(s) { return s ? (s.id || (s.lat + ',' + s.lon)) : ''; }

  /* ---------- 1. choose a site ---------- */
  function buildSitePicker() {
    var box = $('nvSite');
    box.innerHTML =
      '<label class="nv-search">Search by name<input type="search" id="nvSearch" placeholder="e.g. Shackleton, Apollo 15, SLIM" autocomplete="off" aria-controls="nvList"></label>' +
      '<div class="nv-list" id="nvList" role="region" aria-label="Landing sites" aria-describedby="nvListHelp" tabindex="-1"></div>' +
      '<p class="nv-hint" id="nvListHelp">Up and down arrow keys move through the list; Enter picks a site.</p>' +
      '<p class="nv-hint" id="nvSiteMsg" role="status"></p>' +
      '<div class="nv-row"><button type="button" class="btn" id="nvMapPick">Pick on the map</button>' +
      '<details class="nv-own" id="nvOwn"><summary>Your own coordinates</summary>' +
      '<div class="nv-coords">' +
      '<label>Name (optional)<input type="text" id="nvName" maxlength="60" placeholder="My site"></label>' +
      '<fieldset class="nv-hemi"><legend>Latitude</legend><input type="number" id="nvLat" min="0" max="90" step="0.001" placeholder="89.2" aria-label="Latitude in degrees">' +
      '<span class="seg"><label><input type="radio" name="nvNS" value="S" checked> South</label><label><input type="radio" name="nvNS" value="N"> North</label></span></fieldset>' +
      '<fieldset class="nv-hemi"><legend>Longitude</legend><input type="number" id="nvLon" min="0" max="180" step="0.001" placeholder="122.8" aria-label="Longitude in degrees">' +
      '<span class="seg"><label><input type="radio" name="nvEW" value="E" checked> East</label><label><input type="radio" name="nvEW" value="W"> West</label></span></fieldset>' +
      '<button type="button" class="btn primary" id="nvUse">Check this site</button></div>' +
      '<p class="nv-hint">Terrain data covers the south pole to 80° S in most detail; elsewhere it is coarser (about 1.9 km per height).</p></details></div>';
    $('nvSearch').addEventListener('input', function () { nv.filter = this.value.trim().toLowerCase(); renderList(); });
    $('nvSearch').addEventListener('keydown', function (ev) {
      if (ev.key !== 'Enter') { return; }
      var hits = document.querySelectorAll('#nvList .nv-site');
      if (hits.length === 1) { ev.preventDefault(); hits[0].click(); say('Picked ' + hits[0].querySelector('.nm').textContent + '. Working it out, about 10 seconds.'); }
      else if (hits.length) { ev.preventDefault(); hits[0].focus(); }
    });
    $('nvMapPick').addEventListener('click', function () {
      var h = $('h-sites'); if (h) { h.scrollIntoView({ behavior: REDUCED ? 'auto' : 'smooth', block: 'start' }); }
      var p = $('polar'); if (p) { p.setAttribute('tabindex', '-1'); p.focus({ preventScroll: true }); }
      say('The map is open below. Click a point on it to add that place as a site.');
    });
    $('nvUse').addEventListener('click', function () {
      var a = parseFloat($('nvLat').value), o = parseFloat($('nvLon').value);
      var ns = document.querySelector('input[name="nvNS"]:checked').value, ew = document.querySelector('input[name="nvEW"]:checked').value;
      if (!(a >= 0 && a <= 90) || !(o >= 0 && o <= 180)) { $('nvSiteMsg').textContent = 'Type a latitude from 0 to 90 and a longitude from 0 to 180, then choose the hemisphere with the buttons.'; return; }
      var lat = ns === 'S' ? -a : a, lon = ew === 'W' ? -o : o;
      var name = $('nvName').value.trim() || ('Your site ' + latLon(lat, lon));
      app().pick({ name: name, lat: lat, lon: lon });
    });
  }
  function renderList() {
    var A = app(), list = $('nvList'); if (!A || !list) { return; }
    var cat = A.catalog(), sel = A.selected(), cur = sel[A.current()], f = nv.filter, h = '', n = 0;
    GROUPS.forEach(function (g) {
      var rows = cat.filter(function (s) { return s.group === g[0] && (!f || s.name.toLowerCase().indexOf(f) >= 0 || String(s.friendly_name || '').toLowerCase().indexOf(f) >= 0 || s.id.indexOf(f) >= 0); });
      if (!rows.length) { return; }
      h += '<div class="nv-group" role="group" aria-label="' + esc(g[1]) + '"><p class="nv-gname">' + esc(g[1]) + '</p>';
      rows.forEach(function (s) {
        var isCur = cur && cur.lat === s.lat && cur.lon === s.lon, inTray = sel.some(function (x) { return x.lat === s.lat && x.lon === s.lon; });
        n += 1;
        h += '<button type="button" class="nv-site' + (isCur ? ' cur' : '') + '" data-id="' + esc(s.id) + '" aria-pressed="' + (isCur ? 'true' : 'false') + '">' +
          '<span class="nm">' + esc(s.friendly_name || s.name) + '</span><span class="ll">' + esc(s.subtitle || latLon(s.lat, s.lon)) + (inTray && !isCur ? ' · in the comparison' : '') + '</span></button>';
      });
      h += '</div>';
    });
    if (!n) { h = '<p class="nv-hint">No site matches “' + esc(f) + '”. Try part of the name, or type your own coordinates below.</p>'; }
    var hadFocus = list.contains(document.activeElement) ? document.activeElement.getAttribute('data-id') : null;
    list.innerHTML = h;
    /* one Tab stop for the whole list; the arrow keys move inside it */
    var btns = Array.prototype.slice.call(list.querySelectorAll('.nv-site'));
    var stop = list.querySelector('.nv-site.cur') || btns[0];
    btns.forEach(function (b) { b.tabIndex = b === stop ? 0 : -1; });
    if (hadFocus) { var back = list.querySelector('.nv-site[data-id="' + hadFocus + '"]'); if (back) { back.tabIndex = 0; if (stop && stop !== back) { stop.tabIndex = -1; } back.focus(); } }
    if (!list._keys) {
      list._keys = true;
      list.addEventListener('keydown', function (ev) {
        var all = Array.prototype.slice.call(list.querySelectorAll('.nv-site')), i = all.indexOf(document.activeElement), j = -1;
        if (i < 0) { return; }
        if (ev.key === 'ArrowDown') { j = Math.min(all.length - 1, i + 1); } else if (ev.key === 'ArrowUp') { j = Math.max(0, i - 1); }
        else if (ev.key === 'Home') { j = 0; } else if (ev.key === 'End') { j = all.length - 1; }
        if (j < 0) { return; }
        ev.preventDefault();
        all.forEach(function (b, k) { b.tabIndex = k === j ? 0 : -1; });
        all[j].focus();
      });
    }
    Array.prototype.forEach.call(list.querySelectorAll('.nv-site'), function (b) {
      b.addEventListener('click', function () {
        var s = cat.filter(function (x) { return x.id === b.getAttribute('data-id'); })[0];
        if (s) { app().pick({ id: s.id, name: s.name, lat: s.lat, lon: s.lon }); }
      });
    });
  }

  /* ---------- 2. choose a date and time ---------- */
  function buildWhen() {
    var box = $('nvWhen'), hours = '';
    for (var k = 0; k < 24; k++) { hours += '<option value="' + k + '">' + ('0' + k).slice(-2) + ':00 UTC</option>'; }
    box.innerHTML = '<div class="nv-row nv-dt"><label>Date<input type="date" id="nvDate" min="2000-01-01" max="2049-12-31"></label>' +
      '<label>Time<select id="nvHour">' + hours + '</select></label></div>' +
      '<div class="nv-quick" role="group" aria-label="Quick date steps">' +
      '<button type="button" class="btn sm" data-q="today">Today</button>' +
      '<button type="button" class="btn sm" data-q="-1">− 1 day</button>' +
      '<button type="button" class="btn sm" data-q="1">+ 1 day</button>' +
      '<button type="button" class="btn sm" data-q="lunar" title="One lunar day is 29.5 Earth days: the Sun is back where it was">+ 1 lunar day</button>' +
      '<button type="button" class="btn sm" data-q="good" id="nvGood">Next good date</button>' +
      '<button type="button" class="btn sm" data-q="example" title="The fixed worked example the write-up uses">Worked example</button></div>';
    var push = function () {
      var d = $('nvDate').value; if (!/^\d{4}-\d{2}-\d{2}$/.test(d)) { return; }
      app().setPlan(d + 'T' + ('0' + $('nvHour').value).slice(-2) + ':00:00Z');
    };
    $('nvDate').addEventListener('change', push);
    $('nvHour').addEventListener('change', push);
    Array.prototype.forEach.call(box.querySelectorAll('[data-q]'), function (b) {
      b.addEventListener('click', function () {
        var q = b.getAttribute('data-q'), cfg = app().cfg(), t = cfg ? cfg.startMs : Date.now(), iso = null;
        if (q === 'today') { var n = new Date(); n.setUTCMinutes(0, 0, 0); iso = n.toISOString(); }
        else if (q === '-1' || q === '1') { iso = new Date(t + parseInt(q, 10) * 86400000).toISOString(); }
        else if (q === 'lunar') { iso = new Date(Math.round((t + LUNAR_DAY_MS) / 3600000) * 3600000).toISOString(); }
        else if (q === 'example') { iso = '2026-11-18T00:00:00Z'; }
        else if (q === 'good') { var m = curMission(); if (m && m.next_good_dates.length) { iso = m.next_good_dates[0]; } }
        if (iso) { app().setPlan(iso.slice(0, 19).replace(/\.\d+$/, '') + (iso.length > 19 && iso.charAt(19) === 'Z' ? '' : '')); }
      });
    });
  }
  function syncWhen() {
    var cfg = app().cfg(); if (!cfg) { return; }
    var iso = cfg.start;
    if (document.activeElement !== $('nvDate')) { $('nvDate').value = iso.slice(0, 10); }
    $('nvHour').value = String(parseInt(iso.slice(11, 13), 10));
    var m = curMission(), g = $('nvGood');
    g.disabled = !(m && m.next_good_dates.length);
    g.textContent = m && m.next_good_dates.length ? 'Next good date: ' + fmtDay(m.next_good_dates[0]) : 'Next good date';
  }

  /* ---------- 3. the Sun and the Earth against the skyline ---------- */
  function curMission() { var A = app(); return A ? A.mission(A.current()) : null; }
  function curSite() { var A = app(); return A ? A.selected()[A.current()] : null; }
  function whyBodyFor(s) {
    var b = app().body(s); b.day = 0; b.earth_stations = false;      /* geometry only: the skyline decides "in view" */
    return b;
  }
  function loadWhy() {
    var s = curSite(); if (!s || !app().cfg()) { return; }
    var body = whyBodyFor(s), key = JSON.stringify(body);
    if (key === nv.whyKey) { return; }
    nv.whyKey = key; nv.why = null; nv.hour = 0; stop();
    renderSky();
    if (SKYFAST_ON) {
      napi('/api/addons/skyfast?lat=' + s.lat + '&lon=' + s.lon).then(function (r) {
        if (nv.whyKey !== key || nv.why || !r || r.available === false || !r.skyline || !r.skyline.az_deg) { return; }
        nv.approxSky = { key: key, r: r }; renderSky();   /* skyline only: the Sun and Earth tracks come with the exact answer */
      }).catch(function () { /* the exact answer follows anyway */ });
    }
    napi('/api/why', body).then(function (w) { if (nv.whyKey === key) { nv.why = w; renderSky(); } })
      .catch(function (e) { if (nv.whyKey === key) { nv.why = { error: e.message }; renderSky(); } });
  }
  function renderVerdict() {
    var box = $('nvVerdict'), m = curMission(), s = curSite();
    $('nvSiteName').textContent = s ? nameOf(s, m) : 'the chosen site';
    if (!s || !m) { $('nvMetrics').innerHTML = ''; $('nvTags').innerHTML = ''; }
    if (!s) { box.innerHTML = '<p class="nv-hint">Choose a site to begin.</p>'; return; }
    if (!m) {
      box.innerHTML = '<div class="vband v-wait"><span class="vb-word">Working it out (about 10 s)…</span><span class="vb-sub">Full check at 13 touchdown points on the finest terrain</span></div>' + quickAnswer(s);
      return;
    }
    var cls, sub, slip = Math.min(nv.slip || 0, m.days.length - 1), d = m.days[slip], verdict = slip ? d.verdict : m.verdict;
    if (m.verdict === 'yes') {
      sub = m.slip_margin_days >= m.days.length - 1 ? 'holds for all ' + m.days.length + ' dates checked' :
        (m.slip_margin_days === 0 ? 'on this date, with no slip margin' : 'and the launch can slip up to ' + plural(m.slip_margin_days, 'day'));
      if (m.sure && m.sure.points > 1) { sub += ', if it touches down within ' + Math.round(m.sure.scatter_m) + ' m of the target'; }
    } else if (m.next_good_dates.length) {
      sub = 'next good landing date: ' + fmtDay(m.next_good_dates[0]);
    } else { sub = 'no clear-yes date in the ' + m.days.length + ' days checked'; }
    var subNow = !slip ? sub : (d.verdict === 'yes' ? 'it can still slip ' + plural(Math.max(0, marginFrom(m, slip)), 'more day') :
      ((d.reasons && d.reasons[0]) || (d.unsure_because && d.unsure_because[0]) || ''));
    cls = verdict.replace(' ', '').replace('/', '');
    var q = slip ? 'Launch slipped ' + plural(slip, 'day') + ': can it still land on ' + fmtDay(d.landing_utc) + '?' : 'Can a lander work here, landing ' + fmtDay(m.landing_utc) + '?';
    box.innerHTML = '<div class="vband v-' + cls + '" id="nvBand" role="group" aria-label="' + esc(q + ' ' + WORD[verdict] + ', ' + subNow) + '">' +
      '<span class="vb-icon" aria-hidden="true">' + ICON[verdict] + '</span><span class="vb-q">' + esc(q) +
      (m.terrain_grid && m.terrain_grid.resolution_m ? ' <span class="vb-grid">full check on ' + m.terrain_grid.resolution_m + ' m terrain</span>' : '') + '</span>' +
      '<span class="vb-word">' + esc(WORD[verdict]) + '</span><span class="vb-sub">Power and contact: ' + esc(WORD[verdict]) + ', ' + esc(String(subNow).replace(/^and /, '')) + '</span>' +
      '<span class="vb-ground" id="nvGround">Ground: checking the slope at 13 touchdown points…</span>' +
      '<span class="vb-combined" id="nvCombined" hidden></span>' +
      (slip ? '<span class="vb-plan">As planned (' + esc(fmtDay(m.landing_utc)) + '): ' + esc(WORD[m.verdict]) + ', ' + esc(sub) + '</span>' : '') + '</div>' +
      '<p class="nv-yesmeans">Yes means enough sunlight for power and the Earth in view for radio over the first ' + m.window_days + ' days, at all 13 touchdown points. The ground line checks the slope.</p>' +
      '<div class="nv-stand"><button type="button" class="btn sm" id="nvStand">Stand here: the sky view</button><a class="btn sm" href="#h-3d" id="nvSee3d">See this spot in 3-D</a></div>';
    $('nvStand').addEventListener('click', function () {
      var b = document.querySelector('.nv-viewtabs [data-view="sky"]'); if (b) { b.click(); }
      var c = $('nvChart'); if (c) { c.scrollIntoView({ behavior: REDUCED ? 'auto' : 'smooth', block: 'center' }); }
    });
    var tokV = nv.vTok = (nv.vTok || 0) + 1;
    safetyFor(s).then(function (sf) {
      if (tokV !== nv.vTok || !$('nvGround')) { return; }
      if (!sf || !sf.available || !sf.steepest) { $('nvGround').textContent = 'Ground: slope not known here (no fine terrain grid covers it).'; return; }
      var flat = sf.points_passing === sf.points_known;
      /* the closed fold still says the key number */
      var fk = document.querySelector('#foldSafety > summary .foldKey');
      if (!fk && document.querySelector('#foldSafety > summary')) { fk = document.createElement('span'); fk.className = 'foldKey'; document.querySelector('#foldSafety > summary b').insertAdjacentElement('afterend', fk); }
      if (fk) { fk.textContent = 'Here: steepest ' + sf.steepest.slope_deg.toFixed(1) + '°, ' + (flat ? 'flat enough' : 'too steep') + ' (limit ' + sf.limit_deg + '°)'; }
      $('nvGround').innerHTML = 'Ground: <b>' + (flat ? 'flat enough' : 'too steep') + '</b> (steepest of ' + sf.points_known + ' touchdown points ' + sf.steepest.slope_deg.toFixed(1) + '°, NASA’s limit ' + sf.limit_deg + '°)';
      if (!flat && verdict === 'yes') {
        var band = $('nvBand'); band.className = 'vband v-notsure';
        band.querySelector('.vb-icon').textContent = '!';
        var cmb = $('nvCombined'); cmb.hidden = false; cmb.textContent = 'Light and contact work, but the ground is too steep here.';
        band.setAttribute('aria-label', band.getAttribute('aria-label') + '. Light and contact work, but the ground is too steep here.');
      }
    });
    var d0 = m.days[0];
    $('nvTags').innerHTML = '' + (m.terrain_grid && m.terrain_grid.resolution_m ? '<span class="mtag ter" title="' + esc((m.terrain_grid.product || '') + '. ' + (m.horizon ? m.horizon.label : '')) + '">On ' + m.terrain_grid.resolution_m + ' m terrain (' + esc(m.terrain_grid.label || 'LOLA') + '), coarser beyond</span>' :
      m.horizon && m.horizon.kind === 'profile' ? '<span class="mtag ter" title="' + esc(m.horizon.label || '') + '">Measured terrain: ' + esc(String(m.horizon.dem_label || 'LOLA').split(';')[0]) + '</span>' :
        '<span class="mtag smo">Smooth Moon, no terrain here</span>') +
      (m.sure ? '<span class="mtag geo">' + m.sure.points_passing + ' of ' + m.sure.points + ' touchdown points within ' + Math.round(m.sure.scatter_m) + ' m pass</span>' : '') +
      (m.finer_grid_check ? '<span class="mtag ' + (m.finer_grid_check.agrees ? 'agree' : 'disagree') + '" title="' + esc(m.finer_grid_check.text) + '">' + esc(m.finer_grid_check.short) + '</span>' : '') +
      '<span class="mtag ill">Need: ' + m.need.sunlit_h + ' h sunlight, ' + m.need.earth_h + ' h Earth contact (illustrative unless a published plan is named)</span>';
    $('nvMetrics').innerHTML = '<h4 class="nv-mh">Power and radio over the first ' + m.window_days + ' days</h4><dl class="nv-metrics">' +
      '<div><dt>Sunlight for power</dt><dd><b>' + (d0.sunlit_h === null ? 'n/a' : d0.sunlit_h + ' h') + '</b> of ' + m.need.sunlit_h + ' h needed</dd></div>' +
      '<div><dt>Radio contact with Earth</dt><dd><b>' + (d0.earth_h === null ? 'n/a' : d0.earth_h + ' h') + '</b> of ' + m.need.earth_h + ' h needed</dd></div>' +
      '<div><dt>Window counted</dt><dd>first <b>' + m.window_days + '</b> days after landing</dd></div>' +
      '<div><dt>Touchdown points that pass</dt><dd><b>' + d0.points_passing + '</b> of ' + d0.points + '</dd></div></dl>' +
      '<p class="nv-cap">The need is set in <a href="#h-mission">Launch slipped?</a>; the 100 h of Earth contact is illustrative unless a published plan is named there. ' +
      (m.criteria && m.criteria.stations ? 'Radio contact also needs a Deep Space Network station to see the Moon. ' : '') +
      'Yes means all 13 touchdown points, a coarser grid and a finer sampling agree; Not sure means they do not.</p>';
  }
  /* the estimate is trained for one plan, which the API names in words, for example "landing 18 Nov 2026, 60 landing
     dates, 240 sunlit hours and 100 hours of Earth contact in the first 14 days"; it is used only when the page's plan matches */
  function estPlanMatches(plan, cfg) {
    if (typeof plan === 'object') { return plan.start === cfg.start && +plan.need_sun_h === +cfg.need.need_sun_h && +plan.need_earth_h === +cfg.need.need_earth_h && +plan.window_days === +cfg.need.window_days; }
    var p = String(plan), d = /landing (\d{1,2} \w+ \d{4})/.exec(p), sun = /(\d+) sunlit hours/.exec(p), earth = /(\d+) hours of Earth contact/.exec(p), win = /first (\d+) days/.exec(p);
    if (!d || !sun || !earth || !win) { return false; }
    var t = Date.parse(d[1] + ' UTC'), c = Date.parse(String(cfg.start).slice(0, 10) + 'T00:00:00Z');
    return isFinite(t) && isFinite(c) && Math.abs(t - c) < 86400000 && +sun[1] === +cfg.need.need_sun_h && +earth[1] === +cfg.need.need_earth_h &&
      (cfg.need.window_days === undefined || +win[1] === +cfg.need.window_days);
  }
  /* an instant first answer at a clicked point, from the precomputed map grids; the full check replaces it */
  function quickAnswer(s) {
    var A = app(), g = A && A.grids ? A.grids() : null;
    if (!g || !A.polarXY || !isFinite(s.lat) || s.lat > -60) { return ''; }
    var xy = A.polarXY(s.lat, s.lon), x = xy[0], y = xy[1], parts = [];
    var ek = s.lat.toFixed(4) + ',' + s.lon.toFixed(4);
    nv.est = nv.est || {};
    checkEstimate();
    if (ESTIMATE_ON && !(ek in nv.est)) {
      nv.est[ek] = null;
      napi('/api/addons/estimate?lat=' + s.lat + '&lon=' + s.lon).then(function (r) { nv.est[ek] = r || false; renderVerdict(); }).catch(function () { nv.est[ek] = false; });
    }
    var est = nv.est[ek], cfgE = A.cfg();
    var planOk = est && est.available && est.plan && cfgE && estPlanMatches(est.plan, cfgE);
    if (planOk) {
      var acc = estAccuracy(est);
      return '<p class="nv-quick-ans"><b>Learned estimate' + (acc ? ' (right ' + acc + ' of the time in testing)' : '') + '; the full check on the finest terrain follows:</b> ' + esc(est.verdict_words || est.verdict) +
        (est.verdict === 'yes' && est.margin_days_estimate !== null && est.margin_days_estimate !== undefined ? ', about ' + plural(est.margin_days_estimate, 'day') + ' of slip' : '') + '.</p>';
    }
    var km = function (dd) { return dd < 1 ? Math.round(dd * 1000) + ' m' : dd.toFixed(1) + ' km'; };
    var sm = g.slipmap;
    if (sm && sm.available && sm.layers && Math.abs(x) <= sm.half_km && Math.abs(y) <= sm.half_km) {
      var st = sm.step_m / 1000, n = sm.n, col = Math.min(n - 1, Math.floor((x + sm.half_km) / st)), row = Math.min(n - 1, Math.floor((sm.half_km - y) / st));
      var v = sm.layers.margin[row * n + col], d1 = Math.hypot(x - (-sm.half_km + (col + 0.5) * st), y - (sm.half_km - (row + 0.5) * st));
      parts.push('slip margin ' + (v < 0 ? 'none (the planned date fails)' : plural(v, 'day')) + ' at the nearest ' + sm.step_m + ' m map point, ' + km(d1) + ' away');
    } else if (g.fullmap && g.fullmap.available && g.fullKey === g.cfgFullKey) {
      var fm = g.fullmap, sp = fm.grid_spacing_m / 1000, c2 = Math.round((x - fm.first_centre_km.x) / sp), r2 = Math.round((fm.first_centre_km.y - y) / sp);
      if (c2 >= 0 && r2 >= 0 && c2 < fm.n && r2 < fm.n) {
        var v2 = fm.layers.slip_margin_days[r2 * fm.n + c2], d2 = Math.hypot(x - (fm.first_centre_km.x + c2 * sp), y - (fm.first_centre_km.y - r2 * sp));
        if (v2 !== null && v2 !== undefined) { parts.push('slip margin ' + (v2 < 0 ? 'none (the planned date fails)' : plural(v2, 'day')) + ' at the nearest ' + sp + ' km map point, ' + km(d2) + ' away'); }
      }
    }
    if (!nv.slopeP) { nv.slopeP = napi('/api/addons/slopemap').then(function (r) { nv.slopeMap = r; renderVerdict(); return r; }).catch(function () { return null; }); }
    var sl = nv.slopeMap;
    if (sl && sl.available && Math.abs(x) <= sl.half_km && Math.abs(y) <= sl.half_km) {
      var st3 = sl.step_m / 1000, c3 = Math.min(sl.n - 1, Math.floor((x + sl.half_km) / st3)), r3 = Math.min(sl.n - 1, Math.floor((sl.half_km - y) / st3)), k = sl['class'][r3 * sl.n + c3];
      parts.push('ground ' + (k === 2 ? 'flat' : k === 1 ? 'flat enough' : k === 0 ? 'too steep' : 'not known') + ' at that map point');
    }
    if (!parts.length) { return ''; }
    return '<p class="nv-quick-ans"><b>Precomputed, from the map grid:</b> ' + esc(parts.join('; ')) + '. The full check at 13 touchdown points on the finest terrain is running and will replace this.</p>';
  }
  function skyAt(w, az) {
    var sk = w.skyline; if (!sk) { return 0; }
    var n = sk.az_deg.length, k = Math.round(norm(az) / 360 * n) % n;
    return sk.el_deg[k];
  }
  /* hours to the next change of state along the hourly track (null: none within the window) */
  function nextChange(flags, i) {
    for (var k = i + 1; k < flags.length; k++) { if (!!flags[k] !== !!flags[i]) { return k - i; } }
    return null;
  }
  function renderSky() {
    renderVerdict();
    var w = nv.why, chart = $('nvChart');
    if (!curSite()) { chart.innerHTML = ''; $('nvTable').innerHTML = ''; $('nvStrip').innerHTML = ''; $('nvScrubBox').hidden = true; return; }
    renderSentence();
    if (!w && nv.approxSky && nv.approxSky.key === nv.whyKey) { drawApproxSky(nv.approxSky.r); $('nvScrubBox').hidden = true; return; }
    if (!w) { chart.innerHTML = '<div class="nv-wait">Drawing the skyline from NASA LOLA heights…</div>'; $('nvScrubBox').hidden = true; return; }
    if (w.error) { chart.innerHTML = '<p class="nv-hint">' + esc(w.error) + '</p>'; $('nvScrubBox').hidden = true; return; }
    $('nvScrubBox').hidden = false;
    var r = $('nvRange'); r.max = String(w.track.count - 1); r.value = String(nv.hour);
    drawChart(); drawTable(); drawStrip(); drawScrubLabel(); renderSentence();
  }
  /* the sky as you would see it standing at the site: black sky, the real skyline, the Sun and the Earth at the
     chosen hour.  Heights are stretched so that a hill a few degrees high can be seen; the ground hides whatever is
     behind it because it is drawn last. */
  function drawSky() {
    var w = nv.why, t = w.track, sk = w.skyline, box = $('nvChart'), i = nv.hour;
    var W = Math.max(300, Math.round(box.clientWidth || 640)), H = W < 520 ? 240 : 280, FOV = W < 520 ? 90 : 120, ppd = W / FOV, K = 4;
    var face = nv.face === 'earth' ? 'earth' : 'sun', c = norm(face === 'earth' ? t.earth_az[i] : t.sun_az[i]);
    var y0 = H * 0.66, X = function (az) { return W / 2 + (((az - c) % 360 + 540) % 360 - 180) * ppd; }, Y = function (e) { return y0 - e * ppd * K; };
    var svg = el('svg', { viewBox: '0 0 ' + W + ' ' + H, width: W, height: H, 'class': 'nv-svg nv-skyview', role: 'img',
      'aria-label': 'View from ' + w.site.name + ' facing the ' + (face === 'earth' ? 'Earth' : 'Sun') + ' at the chosen hour: the Sun is ' + (t.sun_lit[i] ? 'in view' : 'hidden') + ', the Earth is ' + (t.earth_up[i] ? 'in view' : 'hidden') });
    svg.appendChild(el('rect', { x: 0, y: 0, width: W, height: H, 'class': 'sv-sky' }));
    var disc = function (az, elv, rDeg, cls, label) {
      var x = X(az), y = Y(elv), r = Math.max(3, rDeg * ppd * K);
      if (x < -r || x > W + r) { return; }
      if (cls === 'sv-sun') { svg.appendChild(el('circle', { cx: x, cy: y, r: r * 2.4, 'class': 'sv-glow' })); }
      svg.appendChild(el('circle', { cx: x, cy: y, r: r, 'class': cls }));
      svg.appendChild(el('text', { x: x, y: Math.max(14, y - r - 8), 'text-anchor': 'middle', 'class': 'sv-lab' }, label));
    };
    disc(t.earth_az[i], t.earth_el[i], t.earth_radius_deg || 0.95, 'sv-earth', 'Earth' + (t.earth_up[i] ? '' : ' (behind the ground)'));
    disc(t.sun_az[i], t.sun_el[i], t.sun_radius_deg || 0.27, 'sv-sun', 'Sun' + (t.sun_lit[i] ? '' : ' (behind the ground)'));
    if (sk) {
      var pts = [];
      for (var k = 0; k < sk.az_deg.length; k++) { var x = X(sk.az_deg[k]); if (x >= -10 && x <= W + 10) { pts.push([x, Y(sk.el_deg[k])]); } }
      pts.sort(function (a, b) { return a[0] - b[0]; });
      var d = 'M0 ' + H + pts.map(function (q) { return 'L' + q[0].toFixed(1) + ' ' + q[1].toFixed(1); }).join('') + 'L' + W + ' ' + H + 'Z';
      svg.appendChild(el('path', { d: d, 'class': 'sv-ground' }));
    }
    svg.appendChild(el('line', { x1: 0, x2: W, y1: y0, y2: y0, 'class': 'sv-level' }));
    for (var a = 0; a < 360; a += 15) {
      var xx = X(a); if (xx < 8 || xx > W - 8) { continue; }
      var big = a % 90 === 0;
      svg.appendChild(el('line', { x1: xx, x2: xx, y1: H - 22, y2: H - (big ? 30 : 26), 'class': 'sv-tick' }));
      if (a % 30 === 0) { svg.appendChild(el('text', { x: xx, y: H - 8, 'text-anchor': 'middle', 'class': 'sv-comp' }, (big ? ['N', 'E', 'S', 'W'][a / 90] + ' ' : '') + a + '°')); }
    }
    box.innerHTML = ''; box.appendChild(svg);
    var cap = document.createElement('p'); cap.className = 'nv-cap';
    cap.textContent = 'Facing the ' + (face === 'earth' ? 'Earth' : 'Sun') + ' (azimuth ' + Math.round(c) + '°), ' + FOV + '° wide. Heights and the two discs are stretched ' + K +
      ' times so the low hills show; the dashed line is a flat horizon. The sky is black even by day: the Moon has no air to scatter sunlight.';
    box.appendChild(cap);
  }
  function drawChart() {
    if (nv.view === 'sky') { drawSky(); return; }
    var w = nv.why, t = w.track, sk = w.skyline, box = $('nvChart');
    var W = Math.max(300, Math.round(box.clientWidth || 640)), narrow = W < 520, H = narrow ? 230 : 270;
    var P = { l: 40, r: 12, t: 16, b: 34 }, x0 = P.l, x1 = W - P.r, y0 = P.t, y1 = H - P.b, i = nv.hour;
    var lo = -1, hi = 2;
    if (sk) { sk.el_deg.forEach(function (v) { if (v < lo) { lo = v; } if (v > hi) { hi = v; } }); }
    t.sun_el.forEach(function (v) { if (v > hi) { hi = v; } });
    t.earth_el.forEach(function (v) { if (v > hi) { hi = v; } });
    t.sun_el.forEach(function (v, k) { if (t.sun_lit[k] && v < lo) { lo = v; } });
    t.earth_el.forEach(function (v, k) { if (t.earth_up[k] && v < lo) { lo = v; } });
    hi = Math.min(Math.ceil(hi + 0.8), 90); lo = Math.max(Math.floor(lo - 0.6), -12);
    var rel = function (az) { return ((az + 180) % 360 + 360) % 360 - 180; };
    var sx = function (az) { return x0 + (rel(az) + 180) / 360 * (x1 - x0); };
    var sy = function (e) { return y1 - (Math.max(lo, Math.min(hi, e)) - lo) / (hi - lo) * (y1 - y0); };
    var svg = el('svg', { viewBox: '0 0 ' + W + ' ' + H, width: W, height: H, 'class': 'nv-svg', role: 'img',
      'aria-label': 'The skyline all round ' + w.site.name + ', with the paths of the Sun and the Earth over the ' + w.window_days + '-day window and their positions at the chosen hour' });
    var span = hi - lo, step = span <= 4 ? 1 : span <= 10 ? 2 : span <= 25 ? 5 : 10;
    for (var v = Math.ceil(lo / step) * step; v <= hi; v += step) {
      svg.appendChild(el('line', { x1: x0, x2: x1, y1: sy(v), y2: sy(v), 'class': v === 0 ? 'g0' : 'gl' }));
      svg.appendChild(el('text', { x: x0 - 6, y: sy(v) + 4, 'text-anchor': 'end', 'class': 'ax' }, v + '°'));
    }
    var ticks = narrow ? [[-180, 'S'], [-90, 'W'], [0, 'N'], [90, 'E'], [180, 'S']] :
      [[-180, 'S 180°'], [-135, 'SW'], [-90, 'W 270°'], [-45, 'NW'], [0, 'N 0°'], [45, 'NE'], [90, 'E 90°'], [135, 'SE'], [180, 'S 180°']];
    ticks.forEach(function (q) {
      var x = x0 + (q[0] + 180) / 360 * (x1 - x0);
      svg.appendChild(el('line', { x1: x, x2: x, y1: y1, y2: y1 + 4, 'class': 'tk' }));
      svg.appendChild(el('text', { x: x, y: y1 + 18, 'text-anchor': q[0] === -180 ? 'start' : (q[0] === 180 ? 'end' : 'middle'), 'class': 'ax' }, q[1]));
    });
    if (sk) {
      var pts = [];
      for (var k = 0; k < sk.az_deg.length; k++) { pts.push([rel(sk.az_deg[k]), sk.el_deg[k]]); }
      pts.sort(function (a, b) { return a[0] - b[0]; });
      var d = 'M' + x0 + ' ' + y1;
      pts.forEach(function (q) { d += 'L' + (x0 + (q[0] + 180) / 360 * (x1 - x0)).toFixed(1) + ' ' + sy(q[1]).toFixed(1); });
      d += 'L' + x1 + ' ' + sy(pts[0][1]).toFixed(1) + 'L' + x1 + ' ' + y1 + 'Z';
      svg.appendChild(el('path', { d: d, 'class': 'ground' }));
    }
    function track(az, elv, up, cls) {
      var dUp = '', dHid = '', px = null, pu = null;
      for (var k = 0; k < az.length; k++) {
        var x = sx(az[k]), y = sy(elv[k]), u = up[k] ? 1 : 0, jump = px !== null && Math.abs(x - px) > (x1 - x0) / 2;
        if (px === null || jump || u !== pu) {
          if (px !== null && !jump && u !== pu) { if (u) { dUp += 'M' + px.toFixed(1) + ' ' + sy(elv[k - 1]).toFixed(1); } else { dHid += 'M' + px.toFixed(1) + ' ' + sy(elv[k - 1]).toFixed(1); } }
          else if (u) { dUp += 'M' + x.toFixed(1) + ' ' + y.toFixed(1); } else { dHid += 'M' + x.toFixed(1) + ' ' + y.toFixed(1); }
        }
        if (u) { dUp += 'L' + x.toFixed(1) + ' ' + y.toFixed(1); } else { dHid += 'L' + x.toFixed(1) + ' ' + y.toFixed(1); }
        px = x; pu = u;
      }
      if (dHid) { svg.appendChild(el('path', { d: dHid, 'class': cls + ' hid' })); }
      if (dUp) { svg.appendChild(el('path', { d: dUp, 'class': cls })); }
    }
    track(t.earth_az, t.earth_el, t.earth_up, 'tr-earth');
    track(t.sun_az, t.sun_el, t.sun_lit, 'tr-sun');
    var se = [sx(t.sun_az[i]), sy(t.sun_el[i])], ee = [sx(t.earth_az[i]), sy(t.earth_el[i])];
    svg.appendChild(el('circle', { cx: ee[0], cy: ee[1], r: 9, 'class': 'b-earth' + (t.earth_up[i] ? '' : ' off') }));
    svg.appendChild(el('circle', { cx: se[0], cy: se[1], r: 9, 'class': 'b-sun' + (t.sun_lit[i] ? '' : ' off') }));
    /* the two labels: beside their body, flipped at the right edge, nudged apart if they would touch */
    var lab = function (p, text, dy) {
      var wd = text.length * 6.6, lim = x1 - (narrow ? 0 : 112), a = 'start', x = p[0] + 14, y = p[1] + dy;
      if (x + wd > lim) {
        if (p[0] - 14 - wd >= x0) { a = 'end'; x = p[0] - 14; }
        else { x = Math.max(x0 + 4, lim - wd); y = p[1] + (dy < 0 ? -16 : 22); }      /* neither side fits: above or below the dot */
      }
      y = Math.max(y0 + 10, Math.min(y1 - 6, y));
      return { x: x, y: y, a: a, t: text };
    };
    /* each label carries the numbers: height above level, and how far above (or below) the skyline */
    var says = function (name, elv, az, up) {
      var sky = i === 0 && w.touchdown ? (name === 'Sun' ? w.touchdown.sun_skyline_el : w.touchdown.earth_skyline_el) : skyAt(w, az), c = elv - sky;
      if (!up) { return name + ': ' + elv.toFixed(1) + '° up, but the ground in that direction rises to ' + sky.toFixed(1) + '°, so it is hidden'; }
      return name + ': ' + elv.toFixed(1) + '° up, ' + (c < 1 ? 'just ' : '') + Math.abs(c).toFixed(1) + '° ' + (c >= 0 ? 'above' : 'below') + ' the ground in that direction';
    };
    var ls = lab(se, narrow ? 'Sun' + (t.sun_lit[i] ? '' : ' (hidden)') : says('Sun', t.sun_el[i], t.sun_az[i], t.sun_lit[i]), -10),
      le = lab(ee, narrow ? 'Earth' + (t.earth_up[i] ? '' : ' (hidden)') : says('Earth', t.earth_el[i], t.earth_az[i], t.earth_up[i]), 18);
    if (Math.abs(ls.y - le.y) < 16 && Math.abs(ls.x - le.x) < 120) { le.y = Math.min(y1 - 6, ls.y + 18); }
    [ls, le].forEach(function (q, k) { svg.appendChild(el('text', { x: q.x, y: q.y, 'text-anchor': q.a, 'class': k ? 'l-earth' : 'l-sun' }, q.t)); });
    var hit = el('rect', { x: x0, y: y0, width: x1 - x0, height: y1 - y0, fill: 'transparent' });
    svg.appendChild(hit);
    var blk = null;
    (w.earth_hidden || []).concat(w.sun_hidden || []).forEach(function (st) { if (!blk && st.terrain && st.terrain.kind === 'terrain' && !st.terrain.near_field && st.terrain.dist_km) { blk = st; } });
    var blkTxt = blk ? 'The ground that hides the ' + (blk.body === 'sun' ? 'Sun' : 'Earth') + ' lies to the ' + compass(blk.terrain.az_deg) + ', ' + (blk.terrain.dist_km < 1 ? Math.round(blk.terrain.dist_km * 1000) + ' m' : Math.round(blk.terrain.dist_km) + ' km') + ' away.' : '';
    if (!narrow) {
      var R = 40, cx = x1 - R - 10, cy = y0 + R + 4, g = el('g', { 'class': 'ins', 'aria-hidden': 'true' });
      var pt = function (az, r) { var a = norm(az) * Math.PI / 180; return [cx + r * Math.sin(a), cy - r * Math.cos(a)]; };
      g.appendChild(el('circle', { cx: cx, cy: cy, r: R + 8, 'class': 'ins-bg' }));
      g.appendChild(el('circle', { cx: cx, cy: cy, r: R, 'class': 'ins-ring' }));
      [['N', 0], ['E', 90], ['S', 180], ['W', 270]].forEach(function (q) { var p2 = pt(q[1], R - 9); g.appendChild(el('text', { x: p2[0], y: p2[1] + 4, 'text-anchor': 'middle', 'class': 'ins-l' }, q[0])); });
      if (blk) {
        var a1 = pt(blk.terrain.az_deg - 12, R), a2 = pt(blk.terrain.az_deg + 12, R);
        g.appendChild(el('path', { d: 'M' + a1[0].toFixed(1) + ' ' + a1[1].toFixed(1) + 'A' + R + ' ' + R + ' 0 0 1 ' + a2[0].toFixed(1) + ' ' + a2[1].toFixed(1), 'class': 'ins-ridge' }));
      }
      [['sun', t.sun_az[i]], ['earth', t.earth_az[i]]].forEach(function (q) { var p3 = pt(q[1], R - 3); g.appendChild(el('line', { x1: cx, y1: cy, x2: p3[0], y2: p3[1], 'class': 'ins-' + q[0] })); });
      g.appendChild(el('circle', { cx: cx, cy: cy, r: 4, 'class': 'ins-you' }));
      g.appendChild(el('text', { x: cx, y: cy + R + 20, 'text-anchor': 'middle', 'class': 'ins-cap' }, 'seen from above'));
      svg.appendChild(g);
    }
    box.innerHTML = ''; box.appendChild(svg);
    if ($('nvRidge')) { $('nvRidge').textContent = (blkTxt ? blkTxt + ' ' : '') + (narrow ? 'Now the Sun is to the ' + compass(t.sun_az[i]) + ' and the Earth to the ' + compass(t.earth_az[i]) + '.' : 'The small circle shows the same from above: you in the middle, the Sun (orange) and the Earth (blue), and that ground as a grey arc.'); }
    if ($('nvApprox')) {
      var ap = w._approx ? approxDist(w) : null;
      $('nvApprox').hidden = !w._approx;
      $('nvApprox').textContent = w._approx ? 'Approximate: the nearest precomputed point' + (ap !== null ? ', ' + Math.round(ap) + ' m away' : '') + '. The exact skyline for this spot replaces it in a few seconds.' : '';
    }
  }
  /* the instant approximate skyline (from /api/addons/skyfast): the ground line only, labelled with its distance */
  function drawApproxSky(r) {
    var sk = r.skyline, az = sk.az_deg, elv = sk.el_deg, n = Math.min(az.length, elv.length), box = $('nvChart');
    var W = Math.max(280, Math.round(box.clientWidth || 600)), H = 200, L = 34, R = 8, T = 10, B = 24;
    var lo = Math.min(-2, Math.floor(Math.min.apply(null, elv))), hi = Math.max(2, Math.ceil(Math.max.apply(null, elv)));
    var sx = function (a) { return L + (W - L - R) * (((a % 360) + 360) % 360) / 360; }, sy = function (e) { return T + (H - T - B) * (hi - e) / (hi - lo); };
    var pts = [];
    for (var k = 0; k < n; k++) { pts.push(sx(az[k]).toFixed(1) + ',' + sy(elv[k]).toFixed(1)); }
    var ax = '';
    [[0, 'N'], [90, 'E'], [180, 'S'], [270, 'W']].forEach(function (q) { ax += '<text class="ax" x="' + sx(q[0]) + '" y="' + (H - 6) + '" text-anchor="middle">' + q[1] + '</text>'; });
    [lo, 0, hi].forEach(function (e) { ax += '<text class="ax" x="' + (L - 4) + '" y="' + (sy(e) + 4) + '" text-anchor="end">' + e + '°</text>'; });
    box.innerHTML = '<svg width="' + W + '" height="' + H + '" viewBox="0 0 ' + W + ' ' + H + '" role="img" aria-label="Approximate skyline all around the site">' +
      '<line x1="' + L + '" x2="' + (W - R) + '" y1="' + sy(0) + '" y2="' + sy(0) + '" stroke="currentColor" stroke-opacity=".35" stroke-dasharray="3 3"/>' +
      '<polygon points="' + L + ',' + sy(lo) + ' ' + pts.join(' ') + ' ' + (W - R) + ',' + sy(lo) + '" fill="currentColor" fill-opacity=".25" stroke="currentColor" stroke-width="1.5"/>' + ax + '</svg>' +
      '<p class="nv-hint">Approximate: the skyline of the nearest precomputed point' + (isFinite(r.distance_m) ? ', ' + Math.round(r.distance_m) + ' m away' : '') +
      '. The Sun and the Earth are added with the exact skyline for this spot in a few seconds.</p>';
  }
  function approxDist(w) {
    var found = null;
    (function walk(o) {
      if (found !== null || !o || typeof o !== 'object') { return; }
      Object.keys(o).forEach(function (k) { var v = o[k]; if (found === null && typeof v === 'number' && /dist.*_m$|_m_away|offset_m/.test(k)) { found = v; } else if (found === null && v && typeof v === 'object' && !Array.isArray(v) && /approx|nearest|source|from/i.test(k)) { walk(v); } });
    })(w);
    return found;
  }
  function bodyRow(name, az, elv, up, flags, i, w, apiNext) {
    var sky = i === 0 && w.touchdown ? (name === 'Sun' ? w.touchdown.sun_skyline_el : w.touchdown.earth_skyline_el) : skyAt(w, az);
    var clear = elv - sky, nxt;
    if (i === 0 && apiNext) {
      nxt = apiNext.hours_from_now <= w.window_hours || !up ? (up ? (name === 'Sun' ? 'sets' : 'sets') : 'rises') + ' in <b>' + span(apiNext.hours_from_now) + '</b> (' + esc(fmtWhen(apiNext.unix * 1000)) + ')' :
        'up for the whole ' + w.window_days + '-day window';
    } else {
      var h = nextChange(flags, i);
      nxt = h === null ? (up ? 'up' : 'hidden') + ' to the end of the ' + w.window_days + '-day window' :
        (up ? 'sets' : 'rises') + ' in about <b>' + span(h) + '</b> (to the hour)';
    }
    return '<tr><th scope="row"><i class="dot ' + (name === 'Sun' ? 'sun' : 'earth') + '" aria-hidden="true"></i>' + name + '</th>' +
      '<td class="num">' + Math.round(norm(az)) + '° <small>' + compass(az) + '</small></td>' +
      '<td class="num">' + elv.toFixed(1) + '°</td><td class="num">' + sky.toFixed(1) + '°</td>' +
      '<td class="num ' + (clear >= 0 ? 'pos' : 'neg') + '">' + (clear >= 0 ? '+' : '−') + Math.abs(clear).toFixed(1) + '°</td>' +
      '<td><span class="st ' + (up ? 'up' : 'down') + '">' + (up ? 'In view' : 'Hidden') + '</span></td><td>' + nxt + '</td></tr>';
  }
  function drawTable() {
    var w = nv.why, t = w.track, i = nv.hour, td = w.touchdown || {};
    $('nvTable').innerHTML = '<div class="tablewrap"><table class="nv-obj"><caption>Where the Sun and the Earth are at ' + esc(fmtWhen(Date.parse(t.start_utc) + i * 3600000)) +
      ', seen from the site</caption><thead><tr><th scope="col"></th><th scope="col">Direction <small>(azimuth)</small></th><th scope="col">Height above level</th>' +
      '<th scope="col">Skyline there</th><th scope="col">Above the skyline</th><th scope="col">Now</th><th scope="col">Next</th></tr></thead><tbody>' +
      bodyRow('Sun', t.sun_az[i], t.sun_el[i], !!t.sun_lit[i], t.sun_lit, i, w, t.sun_lit[i] ? td.next_sunset : td.next_sunrise) +
      bodyRow('Earth', t.earth_az[i], t.earth_el[i], !!t.earth_up[i], t.earth_up, i, w, t.earth_up[i] ? td.next_earthset : td.next_earthrise) +
      '</tbody></table></div><p class="nv-cap">Azimuth: compass direction, 0° north, 90° east. Height above level: degrees above a flat horizon. Skyline: the real terrain edge (' +
      esc(w.labels.real) + '). ' + esc(w.labels.derived) + '. The Sun counts as up when ' + esc(w.criteria.sun_rule.replace(/^at least /, 'at least ')) + '; the Earth when its centre clears the skyline (radio contact also needs a ground station).</p>';
  }
  function drawStrip() {
    var w = nv.why, t = w.track, box = $('nvStrip'), n = t.count;
    var W = Math.max(300, Math.round(box.clientWidth || 640)), H = 64, x0 = 52, x1 = W - 8, rowH = 14;
    var sx = function (k) { return x0 + k / (n - 1) * (x1 - x0); };
    var svg = el('svg', { viewBox: '0 0 ' + W + ' ' + H, width: W, height: H, 'class': 'nv-strip', role: 'img',
      'aria-label': 'Hour by hour over ' + w.window_days + ' days: when the Sun is up and when the Earth is above the skyline' });
    [['Sun', t.sun_lit, 6, 'r-sun'], ['Earth', t.earth_up, 26, 'r-earth']].forEach(function (row) {
      svg.appendChild(el('text', { x: x0 - 8, y: row[2] + 11, 'text-anchor': 'end', 'class': 'ax' }, row[0]));
      svg.appendChild(el('rect', { x: x0, y: row[2], width: x1 - x0, height: rowH, 'class': 'r-off' }));
      var k = 0;
      while (k < n) {
        if (row[1][k]) { var j = k; while (j < n && row[1][j]) { j++; } svg.appendChild(el('rect', { x: sx(k), y: row[2], width: Math.max(1, sx(j) - sx(k)), height: rowH, 'class': row[3] })); k = j; } else { k++; }
      }
    });
    var days = Math.round((n - 1) / 24), every = W < 520 ? 2 : 1;
    for (var d = 0; d <= days; d += every) {
      if (d === every && days > 3) { continue; }   /* the first tick after "day 0" would touch it */
      svg.appendChild(el('text', { x: sx(Math.min(d * 24, n - 1)), y: 60, 'text-anchor': d === 0 ? 'start' : (d === days ? 'end' : 'middle'), 'class': 'ax' }, d === 0 ? 'day 0' : String(d)));
    }
    svg.appendChild(el('line', { x1: sx(nv.hour), x2: sx(nv.hour), y1: 2, y2: 44, 'class': 'cursor' }));
    var hit = el('rect', { x: x0, y: 0, width: x1 - x0, height: 46, fill: 'transparent', style: 'cursor:pointer' });
    hit.addEventListener('click', function (ev) {
      var r = svg.getBoundingClientRect(), mx = (ev.clientX - r.left) / r.width * W;
      setHour(Math.round((mx - x0) / (x1 - x0) * (n - 1)));
    });
    svg.appendChild(hit);
    box.innerHTML = ''; box.appendChild(svg);
  }
  function drawScrubLabel() {
    var w = nv.why, i = nv.hour;
    $('nvWhenNow').textContent = fmtWhen(Date.parse(w.track.start_utc) + i * 3600000) + (i ? ' · ' + span(i) + ' after the chosen time' : ' · the chosen time');
    $('nvRange').setAttribute('aria-valuetext', fmtWhen(Date.parse(w.track.start_utc) + i * 3600000));
    var su = 0, eu = 0;
    for (var k = 0; k < i; k++) { su += w.track.sun_lit[k] ? 1 : 0; eu += w.track.earth_up[k] ? 1 : 0; }
    if ($('nvSoFar')) { $('nvSoFar').textContent = i ? 'So far: the Sun up ' + su + ' of ' + i + ' hours, the Earth in view ' + eu + ' of ' + i + ' hours. Now the Sun is ' + (w.track.sun_lit[i] ? 'up' : 'hidden') + ', the Earth ' + (w.track.earth_up[i] ? 'in view' : 'hidden') + '.' : ''; }
  }
  function setHour(i) {
    var w = nv.why; if (!w || w.error) { return; }
    nv.hour = Math.max(0, Math.min(w.track.count - 1, i));
    $('nvRange').value = String(nv.hour);
    drawChart(); drawTable(); drawStrip(); drawScrubLabel();
    sync3d();
  }
  /* the 3-D view shows the same site from the same landing time when no slip is picked: move its slider too */
  function sync3d() {
    try {
      var s3 = document.querySelector('#view3d input[type=range]'), slip = $('mSlip');
      if (!s3 || (slip && slip.value !== '0') || $('view3dPanel').hidden) { return; }
      var step = 6, v = String(Math.min(parseInt(s3.max, 10) || 0, Math.round(nv.hour / step)));
      if (s3.value !== v) { s3.value = v; s3.dispatchEvent(new Event('input', { bubbles: true })); }
    } catch (e) { /* the 3-D view keeps its own time */ }
  }
  function stop() {
    if (nv.playing) { clearInterval(nv.playing); nv.playing = null; }
    var b = $('nvPlay'); if (b) { b.textContent = 'Play'; b.setAttribute('aria-pressed', 'false'); }
  }
  function play() {
    if (nv.playing) { stop(); return; }
    var w = nv.why; if (!w || w.error) { return; }
    if (nv.hour >= w.track.count - 1) { nv.hour = 0; }
    var b = $('nvPlay'); b.textContent = 'Pause'; b.setAttribute('aria-pressed', 'true');
    /* reduced motion: bigger, slower steps instead of a smooth run */
    var sp = nv.speed || 24, stepH = sp <= 6 ? 1 : (sp <= 24 ? 2 : 6), ms = Math.round(1000 * stepH / sp);
    if (REDUCED) { stepH = Math.max(stepH, 6); ms = Math.max(400, Math.round(1000 * stepH / sp)); }
    nv.playing = setInterval(function () {
      if (!nv.why || nv.hour >= nv.why.track.count - 1) { stop(); return; }
      setHour(nv.hour + stepH);
    }, ms);
  }
  function buildScrub() {
    $('nvScrubBox').innerHTML = '<div class="nv-scrub"><button type="button" class="btn primary" id="nvPlay" aria-pressed="false">Play</button>' +
      '<input type="range" id="nvRange" min="0" max="336" step="1" value="0" aria-label="Hour after the chosen time">' +
      '<span class="nv-speed" role="group" aria-label="Playback speed">' +
      '<button type="button" class="btn sm" data-sp="6" aria-pressed="false">6 h/s</button>' +
      '<button type="button" class="btn sm" data-sp="24" aria-pressed="true">1 day/s</button>' +
      '<button type="button" class="btn sm" data-sp="72" aria-pressed="false">3 days/s</button></span>' +
      '<button type="button" class="btn sm" id="nvStep">Step +6 h</button>' +
      '<output id="nvWhenNow" for="nvRange"></output><p class="nv-sofar" id="nvSoFar" aria-live="off"></p></div>';
    $('nvRange').addEventListener('input', function () { stop(); setHour(parseInt(this.value, 10) || 0); });
    $('nvPlay').addEventListener('click', play);
    $('nvStep').addEventListener('click', function () { stop(); if (nv.why && !nv.why.error) { setHour(nv.hour >= nv.why.track.count - 1 ? 0 : nv.hour + 6); say($('nvWhenNow').textContent + '. ' + $('nvSoFar').textContent); } });
    if (REDUCED) { $('nvPlay').hidden = true; }      /* reduced motion: step instead of autoplay */
    Array.prototype.forEach.call(document.querySelectorAll('#nvScrubBox [data-sp]'), function (b) {
      b.addEventListener('click', function () {
        nv.speed = parseInt(b.getAttribute('data-sp'), 10);
        Array.prototype.forEach.call(document.querySelectorAll('#nvScrubBox [data-sp]'), function (x) { x.setAttribute('aria-pressed', x === b ? 'true' : 'false'); });
        if (nv.playing) { stop(); play(); }
      });
    });
  }

  /* ---------- the one-sentence summary, from the hourly track of the API ---------- */
  function longestRun(flags, W, want) {
    var best = 0, run = 0;
    for (var k = 0; k < W; k++) { if (!!flags[k] === want) { run += 1; if (run > best) { best = run; } } else { run = 0; } }
    return best;
  }
  function trackStats(w) {
    var t = w.track, W = Math.min(w.window_hours, t.count), sun = 0, earth = 0, both = 0;
    for (var k = 0; k < W; k++) { sun += t.sun_lit[k] ? 1 : 0; earth += t.earth_up[k] ? 1 : 0; both += (t.sun_lit[k] && t.earth_up[k]) ? 1 : 0; }
    return { W: W, sunPct: Math.round(100 * sun / W), earthPct: Math.round(100 * earth / W), bothPct: Math.round(100 * both / W),
      night: longestRun(t.sun_lit, W, false), gap: longestRun(t.earth_up, W, false) };
  }
  function renderSentence() {
    var p = $('nvSentence'), w = nv.why, s = curSite();
    if (!p) { return; }
    if (!s || !w || w.error) { p.textContent = ''; return; }
    var st = trackStats(w);
    p.innerHTML = 'Over the ' + w.window_days + ' days after landing, the Sun is up <b>' + st.sunPct + '%</b> of the time and the Earth is above the skyline <b>' +
      st.earthPct + '%</b>; the longest darkness is <b>' + span(st.night) + '</b>' + (st.night ? '' : ' (none)') + '. <small>Counted hour by hour from the track below; the Earth here is geometry only.</small>';
  }

  /* ---------- ready-made comparisons, so the first screen is never empty ---------- */
  var PRESETS = [
    { label: 'Worked example', title: 'The fixed example the write-up uses: four sites on 18 Nov 2026', ids: ['robust_pick', 'shackleton', 'im2', 'im1'], iso: '2026-11-18T00:00:00Z', need: true },
    { label: 'Ridge or crater', title: 'A ridge point against the floor of Shackleton crater, which the Sun never reaches', ids: ['robust_pick', 'shackleton_floor'], iso: '2026-11-18T00:00:00Z', need: true },
    { label: 'Apollo 11 or pole', title: 'Near the equator the Sun climbs high; near the pole it grazes the skyline', ids: ['apollo11', 'robust_pick'], iso: '2026-11-18T00:00:00Z', need: true },
    { label: 'IM-1 as flown', title: 'The real IM-1 landing time and site, with the need from its published plan', replay: 'im1' },
    { label: 'VIPER at Mons Mouton', title: 'VIPER\u2019s first good landing time in its published period, at a published candidate site (from the missions board)', mission: 'viper' },
    { label: 'Slip a week', title: 'Every compared site, seven days late', slip: 7 }
  ];
  function buildPresets() {
    var box = $('nvPresets'); if (!box) { return; }
    box.innerHTML = '<span class="nv-plabel">Try:</span>' + PRESETS.map(function (p, i) { return '<button type="button" class="btn chip" data-pre="' + i + '" title="' + esc(p.title) + '">' + esc(p.label) + '</button>'; }).join('');
    Array.prototype.forEach.call(box.querySelectorAll('[data-pre]'), function (b) {
      b.addEventListener('click', function () {
        var p = PRESETS[parseInt(b.getAttribute('data-pre'), 10)];
        if (p.mission) {
          say('Loading ' + p.label + ' from the missions board.');
          napi('/api/addons/impact').then(function (im) {
            var ms = (im.missions || []).filter(function (x) { return x.id === p.mission; })[0], mo = ms && ms.months && ms.months[0];
            if (!mo) { say('The missions board has no landing time for this mission.'); return; }
            $('needSun').value = 240; $('needEarth').value = 100; $('slipWindow').value = '14'; $('tdSun').checked = true; $('tdEarth').checked = true;
            app().pick({ name: ms.name.split(' on ')[0] + ' target ' + mo.site + ' (' + mo.region + ')', lat: mo.lat, lon: mo.lon });
            app().setPlan(mo.landing_utc);
          }).catch(function (e) { say('Could not load the missions board: ' + e.message); });
          return;
        }
        if (p.replay) { var r = document.querySelector('#replays [data-replay="' + p.replay + '"]'); if (r) { r.click(); } return; }
        if (p.slip !== undefined) {
          nv.slip = p.slip; app().setSlip(p.slip); renderCompare(true); nv.decideKey = ''; renderDecide();
          var c = $('comparePanel'); if (c) { c.scrollIntoView({ behavior: REDUCED ? 'auto' : 'smooth', block: 'start' }); }
          return;
        }
        if (p.need) { $('needSun').value = 240; $('needEarth').value = 100; $('slipWindow').value = '14'; $('tdSun').checked = true; $('tdEarth').checked = true; }
        nv.slip = 0; app().setSites(p.ids, 0, p.iso);
      });
    });
  }

  /* ---------- compare sites side by side ---------- */
  function safetyFor(s) {
    var k = siteKey(s);
    if (!nv.safety[k]) {
      var q = s.id ? 'id=' + encodeURIComponent(s.id) : 'lat=' + s.lat + '&lon=' + s.lon + '&name=' + encodeURIComponent(s.name || '');
      nv.safety[k] = napi('/api/addons/safety/site?' + q).catch(function () { return null; });
    }
    return nv.safety[k];
  }
  function whyFor(s, day) {
    var body = whyBodyFor(s); body.day = day || 0;      /* the slipped landing when a slip is set */
    var k = JSON.stringify(body);
    if (!nv.cmp[k]) { nv.cmp[k] = napi('/api/why', body).catch(function (e) { return { error: e.message }; }); }
    return nv.cmp[k];
  }
  var LETTERS = ['1', '2', '3', '4'];      /* the same numbers as the markers on the map and the site chips */
  var RANK = { yes: 2, 'not sure': 1, no: 0, 'n/a': -1 };
  /* how many more days of slip still give Yes, counted on the API's own day-by-day answers from day n */
  function marginFrom(m, n) {
    if (!m.days[n] || m.days[n].verdict !== 'yes') { return -1; }
    var k = n; while (k + 1 < m.days.length && m.days[k + 1].verdict === 'yes') { k++; }
    return k - n;
  }
  function miniSky(w) {
    var W = 168, H = 46, sk = w.skyline, t = w.track;
    if (!sk) { return '<small>no terrain skyline here</small>'; }
    var lo = -1, hi = 2;
    sk.el_deg.forEach(function (v) { if (v < lo) { lo = v; } if (v > hi) { hi = v; } });
    t.sun_el.forEach(function (v) { if (v > hi) { hi = v; } }); t.earth_el.forEach(function (v) { if (v > hi) { hi = v; } });
    hi = Math.min(hi + 0.5, 90); lo = Math.max(lo - 0.5, -12);
    var rel = function (az) { return ((az + 180) % 360 + 360) % 360 - 180; };
    var sx = function (az) { return ((rel(az) + 180) / 360 * W).toFixed(1); };
    var sy = function (e) { return (H - (Math.max(lo, Math.min(hi, e)) - lo) / (hi - lo) * H).toFixed(1); };
    var pts = sk.az_deg.map(function (a, k) { return [rel(a), sk.el_deg[k]]; }).sort(function (a, b) { return a[0] - b[0]; });
    var d = 'M0 ' + H + pts.map(function (q) { return 'L' + ((q[0] + 180) / 360 * W).toFixed(1) + ' ' + sy(q[1]); }).join('') + 'L' + W + ' ' + H + 'Z';
    var path = function (az, elv) {
      var s = '', px = null;
      for (var k = 0; k < az.length; k += 2) { var x = +sx(az[k]); s += (px === null || Math.abs(x - px) > W / 2 ? 'M' : 'L') + x + ' ' + sy(elv[k]); px = x; }
      return s;
    };
    return '<svg class="mini" viewBox="0 0 ' + W + ' ' + H + '" width="' + W + '" height="' + H + '" role="img" aria-label="Small skyline with the Sun and Earth paths">' +
      '<path class="ground" d="' + d + '"/><path class="tr-earth" d="' + path(t.earth_az, t.earth_el) + '"/><path class="tr-sun" d="' + path(t.sun_az, t.sun_el) + '"/>' +
      '<line class="g0" x1="0" x2="' + W + '" y1="' + sy(0) + '" y2="' + sy(0) + '"/></svg>';
  }
  function heat(m, slip) {
    return '<span class="heat" role="img" aria-label="Answer for each landing day: ' + m.days.filter(function (d) { return d.verdict === 'yes'; }).length + ' of ' + m.days.length + ' days are Yes">' +
      m.days.map(function (d, k) { return '<i class="v-' + d.verdict.replace(' ', '').replace('/', '') + (k === slip ? ' at' : '') + '"></i>'; }).join('') + '</span>';
  }
  /* one sentence on what hides the Sun or the Earth here, from the API's own hiding stretches */
  function whyDiffers(w) {
    var pick = null;
    (w.sun_hidden || []).concat(w.earth_hidden || []).forEach(function (s) { if (s.deepest_below_skyline_deg > 0 && (!pick || s.hours > pick.hours)) { pick = s; } });
    if (!pick) { return 'Neither the Sun nor the Earth goes behind the ground in the ' + w.window_days + ' days.'; }
    var name = pick.body === 'sun' ? 'Sun' : 'Earth', tr = pick.terrain || {};
    var where = tr.kind === 'terrain' && !tr.near_field && tr.dist_km ? ' behind ground ' + (tr.dist_km < 1 ? Math.round(tr.dist_km * 1000) + ' m' : tr.dist_km.toFixed(1) + ' km') + ' away to the ' + (tr.compass || compass(tr.az_deg || 0)) +
      (tr.skyline_el_deg !== undefined ? (tr.skyline_el_deg < 0 ? ', where the skyline sits ' + Math.abs(tr.skyline_el_deg).toFixed(1) + '° below a flat horizon' : ', where the skyline is ' + tr.skyline_el_deg.toFixed(1) + '° high') : '') : (tr.near_field ? ' behind the ground right beside the lander' : ' below the skyline');
    return 'The ' + name + ' goes' + where + (pick.from_hour === 0 ? ' from the start' : ' on day ' + (Math.floor(pick.from_hour / 24) + 1)) +
      (pick.runs_to_end_of_window ? ' and stays hidden to the end.' : ', for ' + span(pick.hours) + '.');
  }
  function renderCompare(force) {
    var A = app(), box = $('nvCompare'); if (!A || !box || !A.cfg()) { return; }
    var sel = A.selected(), cur = A.current();
    if (!sel.length) { box.innerHTML = '<p class="nv-hint">Pick a site above and it appears here. Up to four sit side by side.</p>'; return; }
    var cols = sel.map(function (s, i) { return { s: s, i: i, m: A.mission(i), w: null, sf: null }; });
    var maxDay = Math.min.apply(null, cols.map(function (c) { return c.m ? c.m.days.length - 1 : 59; }));
    nv.slip = Math.max(0, Math.min(nv.slip || 0, maxDay));
    var draw = function () {
      var focusId = document.activeElement && document.activeElement.id;
      var wait = '<span class="wait">…</span>';
      /* row(label, cell, score): score(c) gives a number to compare (higher is better) or null; the best is shaded */
      var row = function (label, f, score) {
        var best = null;
        if (score) { cols.forEach(function (c) { var v = score(c); if (v !== null && v !== undefined && (best === null || v > best)) { best = v; } }); }
        var ties = score ? cols.filter(function (c) { var v = score(c); return v !== null && v !== undefined && v === best; }).length : 0;
        return '<tr><th scope="row">' + label + '</th>' + cols.map(function (c) {
          var win = score && best !== null && ties < cols.length && score(c) === best;
          return '<td class="' + (c.i === cur ? 'cur' : '') + (win ? ' win' : '') + '">' + f(c) + (win ? '<span class="sr"> (best)</span>' : '') + '</td>';
        }).join('') + '</tr>';
      };
      var ok = function (c) { return c.w && !c.w.error; };
      var h = '<div class="nv-cmpbar"><label class="inline">Launch slipped by <input type="number" id="nvSlip" min="0" max="' + maxDay + '" step="1" value="' + nv.slip + '" aria-describedby="nvSlipHelp"> days</label>' +
        '<span class="nv-hint" id="nvSlipHelp">applies to every site in the table at once</span><button type="button" class="btn sm" id="nvCsv">Download this table (CSV)</button></div>';
      h += '<div class="tablewrap"><table class="nv-cmp"><caption>' + sel.length + ' of 4 sites, planned landing ' + esc(fmtWhen(A.cfg().startMs)) + '</caption><thead><tr><th scope="col"><span class="sr">Measure</span></th>' +
        cols.map(function (c) {
          return '<th scope="col"' + (c.i === cur ? ' class="cur"' : '') + '><span class="badge-l" aria-hidden="true">' + LETTERS[c.i] + '</span><span class="cn">' + esc(nameOf(c.s, c.m)) + '</span><small>' + esc(subOf(c.s, c.m)) + '</small>' +
            '<span class="cb">' + (c.i === cur ? '<span class="tag">Shown above</span>' : '<button type="button" class="btn sm" data-show="' + c.i + '">Show above</button>') +
            '<button type="button" class="btn sm ghost" data-rm="' + c.i + '" aria-label="Remove ' + esc(c.s.name) + ' from the comparison">Remove</button></span></th>';
        }).join('') + '</tr></thead><tbody>';
      h += row('Can a lander work here?', function (c) {
        if (!c.m) { return wait; }
        var cls = c.m.verdict.replace(' ', '').replace('/', '');
        return '<span class="vpill v-' + cls + '">' + ICON[c.m.verdict] + ' ' + WORD[c.m.verdict] + '</span>' + (c.m.verdict === 'yes' ? '<br><small>slip margin ' + plural(c.m.slip_margin_days, 'day') + '</small>' : '');
      }, function (c) { return c.m ? RANK[c.m.verdict] * 1000 + Math.max(0, c.m.slip_margin_days) : null; });
      if (nv.slip > 0) {
        h += row('After a slip of ' + plural(nv.slip, 'day'), function (c) {
          if (!c.m) { return wait; }
          var d = c.m.days[nv.slip]; if (!d) { return 'n/a'; }
          var cls = d.verdict.replace(' ', '').replace('/', ''), left = marginFrom(c.m, nv.slip);
          return '<span class="vpill v-' + cls + '">' + ICON[d.verdict] + ' ' + WORD[d.verdict] + '</span><br><small>' +
            (c.m.verdict === 'yes' && left >= 0 ? 'margin ' + c.m.slip_margin_days + ' → ' + plural(left, 'day') : (d.reasons && d.reasons.length ? esc(d.reasons[0]) : '')) + '</small>';
        }, function (c) { var d = c.m && c.m.days[nv.slip]; return d ? RANK[d.verdict] * 1000 + Math.max(0, marginFrom(c.m, nv.slip)) : null; });
      }
      h += row('Each landing day', function (c) { return c.m ? heat(c.m, nv.slip) + '<br><small>day 0 to ' + (c.m.days.length - 1) + '</small>' : wait; });
      h += row('Sunlit hours <small>(in the window)</small>', function (c) { return c.m ? (c.m.days[nv.slip].sunlit_h === null ? 'n/a' : '<b>' + c.m.days[nv.slip].sunlit_h + '</b> of ' + c.m.need.sunlit_h) : wait; },
        function (c) { return c.m ? c.m.days[nv.slip].sunlit_h : null; });
      h += row('Earth-contact hours', function (c) { return c.m ? (c.m.days[nv.slip].earth_h === null ? 'n/a' : '<b>' + c.m.days[nv.slip].earth_h + '</b> of ' + c.m.need.earth_h) : wait; },
        function (c) { return c.m ? c.m.days[nv.slip].earth_h : null; });
      h += row('Longest darkness', function (c) { return ok(c) ? span(trackStats(c.w).night) : (c.w ? 'n/a' : wait); }, function (c) { return ok(c) ? -trackStats(c.w).night : null; });
      h += row('Longest time without the Earth', function (c) { return ok(c) ? span(trackStats(c.w).gap) : (c.w ? 'n/a' : wait); }, function (c) { return ok(c) ? -trackStats(c.w).gap : null; });
      h += row(nv.slip ? 'Sun at the slipped landing' : 'Sun at landing', function (c) {
        if (!ok(c)) { return c.w ? 'n/a' : wait; }
        var td = c.w.touchdown; return td.sun_el.toFixed(1) + '° high, ' + (td.sun_up ? 'in view' : 'hidden');
      });
      h += row('Sunset in', function (c) {
        if (!ok(c)) { return c.w ? 'n/a' : wait; }
        var td = c.w.touchdown; return td.sun_up ? (td.next_sunset ? '<b>' + span(td.next_sunset.hours_from_now) + '</b><br><small>' + esc(fmtWhen(td.next_sunset.unix * 1000)) + '</small>' : 'not within ' + Math.round(td.searched_days) + ' days') :
          'already down' + (td.next_sunrise ? '<br><small>rises in ' + span(td.next_sunrise.hours_from_now) + '</small>' : '');
      }, function (c) { if (!ok(c)) { return null; } var td = c.w.touchdown; return td.sun_up ? (td.next_sunset ? td.next_sunset.hours_from_now : 1e6) : -1; });
      h += row(nv.slip ? 'Earth at the slipped landing' : 'Earth at landing', function (c) {
        if (!ok(c)) { return c.w ? 'n/a' : wait; }
        var td = c.w.touchdown; return td.earth_el.toFixed(1) + '° high, ' + (td.earth_up ? 'in view' : 'hidden');
      });
      h += row('Earthset in', function (c) {
        if (!ok(c)) { return c.w ? 'n/a' : wait; }
        var td = c.w.touchdown; return td.earth_up ? (td.next_earthset ? '<b>' + span(td.next_earthset.hours_from_now) + '</b><br><small>' + esc(fmtWhen(td.next_earthset.unix * 1000)) + '</small>' : 'not within ' + Math.round(td.searched_days) + ' days') :
          'already hidden' + (td.next_earthrise ? '<br><small>rises in ' + span(td.next_earthrise.hours_from_now) + '</small>' : '');
      }, function (c) { if (!ok(c)) { return null; } var td = c.w.touchdown; return td.earth_up ? (td.next_earthset ? td.next_earthset.hours_from_now : 1e6) : -1; });
      h += row('Skyline and paths', function (c) { return ok(c) ? miniSky(c.w) : (c.w ? 'n/a' : wait); });
      h += row('Why it differs', function (c) { return ok(c) ? '<small>' + esc(whyDiffers(c.w)) + '</small>' : (c.w ? 'n/a' : wait); });
      h += row('Flat enough to land?', function (c) {
        if (c.sf === null) { return wait; }
        if (!c.sf || !c.sf.available) { return '<small>not known here</small>'; }
        return esc(c.sf.word) + (c.sf.steepest ? '<br><small>steepest ' + c.sf.steepest.slope_deg.toFixed(1) + '° of 13 points (limit ' + c.sf.limit_deg + '°)</small>' : '');
      }, function (c) { return c.sf && c.sf.available && c.sf.steepest ? -c.sf.steepest.slope_deg : null; });
      h += row('Safe touchdown chance <small>(ground under the slope limit; lander accuracies assumed)</small>', function (c) {
        if (c.st === null || c.st === undefined) { return wait; }
        var k = c.st && c.st.available && c.st.classes ? c.st.classes.filter(function (q) { return q.available !== false && q.p8 !== undefined; }) : [];
        return k.length ? k.map(function (q) { return esc(q.label) + ' <b>' + q.p8 + '%</b>'; }).join('<br>') : '<small>not known here</small>';
      }, function (c) { var k = c.st && c.st.available && c.st.classes ? c.st.classes.filter(function (q) { return q.id === 'clps' && q.p8 !== undefined; })[0] : null; return k ? k.p8 : null; });
      h += row('Plan holds / flat / both, per lander class <small>(joint chance; accuracies assumed)</small>', function (c) {
        if (c.jt === null || c.jt === undefined) { return wait; }
        if (!c.jt || !c.jt.available || !c.jt.classes) { return '<small>not known here</small>' + ((c.jt && c.jt.reason) ? '<details class="cellWhy"><summary>Why not</summary><small>' + esc(c.jt.reason) + '</small></details>' : ''); }
        return c.jt.classes.map(function (q) { return esc(q.label) + ': ' + Math.round(q.plan_holds_pct) + ' / ' + Math.round(q.flat_pct) + ' / <b>' + Math.round(q.joint_pct) + '%</b>'; }).join('<br>');
      }, function (c) { var k = c.jt && c.jt.available && c.jt.classes ? c.jt.classes.filter(function (q) { return q.id === 'clps'; })[0] : null; return k ? k.joint_pct : null; });
      h += row('Next good dates', function (c) {
        if (!c.m) { return wait; }
        return c.m.next_good_dates.length ? c.m.next_good_dates.slice(0, 2).map(fmtDay).join(', ') : '<small>none in ' + c.m.days.length + ' days</small>';
      });
      h += '</tbody></table></div><p class="nv-cap">Verdict, hours and next good dates: the same calculation as “Launch slipped?”, with its need and rules. ' +
        'Darkness, Earth gaps, sunset and Earthset: from the landing time, behind the real skyline (Earth geometry only; radio contact also needs a ground station). ' +
        'Slope: the steepest of 13 touchdown points on the finest LOLA grid there, against NASA’s slope limit for landers; see <a href="#h-safe">Is it safe?</a>. ' +
        'Picking a fifth site replaces the last one.</p>';
      box.innerHTML = h;
      Array.prototype.forEach.call(box.querySelectorAll('[data-show]'), function (b) { b.addEventListener('click', function () { app().select(parseInt(b.getAttribute('data-show'), 10)); }); });
      Array.prototype.forEach.call(box.querySelectorAll('[data-rm]'), function (b) { b.addEventListener('click', function () { app().remove(parseInt(b.getAttribute('data-rm'), 10)); }); });
      $('nvCsv').addEventListener('click', function () {
        var q = function (v) { v = String(v).replace(/\s+/g, ' ').trim(); return /[",\n]/.test(v) ? '"' + v.replace(/"/g, '""') + '"' : v; };
        var lines = ['# Slipday site comparison, planned landing ' + A.cfg().start + (nv.slip ? ', launch slipped ' + nv.slip + ' days' : '') + '; every figure from the Slipday API; the need is illustrative unless a published plan is named'];
        lines.push(['measure'].concat(cols.map(function (c) { return c.s.name; })).map(q).join(','));
        Array.prototype.forEach.call(box.querySelectorAll('.nv-cmp tbody tr'), function (tr) {
          lines.push(Array.prototype.map.call(tr.children, function (cell) { return q(cell.textContent.replace(' (best)', ' [best]')); }).join(','));
        });
        var a = document.createElement('a'); a.href = URL.createObjectURL(new Blob([lines.join('\n') + '\n'], { type: 'text/csv' })); a.download = 'slipday_site_comparison.csv';
        document.body.appendChild(a); a.click(); setTimeout(function () { URL.revokeObjectURL(a.href); a.remove(); }, 1000);
      });
      $('nvSlip').addEventListener('change', function () {
        nv.slip = Math.max(0, Math.min(parseInt(this.value, 10) || 0, maxDay)); nv.slipSeen = nv.slip; renderCompare(); nv.decideKey = ''; renderDecide(); renderVerdict(); if (app().setSlip) { app().setSlip(nv.slip); }
        say('Launch slipped by ' + plural(nv.slip, 'day') + ': ' + cols.map(function (c) { var d = c.m && c.m.days[nv.slip]; return LETTERS[c.i] + ' ' + (d ? WORD[d.verdict] : 'not ready'); }).join(', ') + '.');
        var s2 = $('nvSlip'); if (s2) { s2.focus(); }
      });
      if (focusId && $(focusId) && focusId !== 'nvSlip') { $(focusId).focus(); }
    };
    draw();
    var token = nv.cmpToken = (nv.cmpToken || 0) + 1;
    cols.forEach(function (c) {
      whyFor(c.s, nv.slip).then(function (w) { if (token !== nv.cmpToken) { return; } c.w = w; draw(); });
      safetyFor(c.s).then(function (sf) { if (token !== nv.cmpToken) { return; } c.sf = sf || false; draw(); });
      var tq = c.s.id ? 'id=' + encodeURIComponent(c.s.id) : 'lat=' + c.s.lat + '&lon=' + c.s.lon + '&name=' + encodeURIComponent(c.s.name || '');
      var cfgJ = A.cfg(), jq = tq + '&landing=' + encodeURIComponent(cfgJ.start) + '&slip_days=' + (nv.slip || 0) + '&need_sun_h=' + cfgJ.need.need_sun_h + '&need_earth_h=' + cfgJ.need.need_earth_h + '&window_days=' + cfgJ.need.window_days;
      getOnce(dcache, 'jt' + jq, function () { return napi('/api/addons/planner/joint?' + jq); }).then(function (jt) { if (token !== nv.cmpToken) { return; } c.jt = jt || false; draw(); })
        .catch(function () { if (token !== nv.cmpToken) { return; } c.jt = false; draw(); });
      getOnce(dcache, 'st' + siteKey(c.s), function () { return napi('/api/addons/safetouch/site?' + tq); }).then(function (st) { if (token !== nv.cmpToken) { return; } c.st = st || false; draw(); })
        .catch(function () { if (token !== nv.cmpToken) { return; } c.st = false; draw(); });
    });
  }

  /* ---------- one decision path: answer, how sure, why, what to do ---------- */
  var MOON_R_KM = 1737.4;          /* mean lunar radius, for the distance between two sites */
  function kmBetween(a, b) {
    var r = Math.PI / 180, dLat = (b.lat - a.lat) * r, dLon = (b.lon - a.lon) * r;
    var h = Math.sin(dLat / 2) * Math.sin(dLat / 2) + Math.cos(a.lat * r) * Math.cos(b.lat * r) * Math.sin(dLon / 2) * Math.sin(dLon / 2);
    return 2 * MOON_R_KM * Math.asin(Math.min(1, Math.sqrt(h)));
  }
  function getOnce(store, key, make) { if (!store[key]) { store[key] = make().catch(function (e) { delete store[key]; throw e; }); } return store[key]; }
  var dcache = {};
  function decideKey() {
    var A = app(), s = curSite(), m = curMission();
    return s && m && A.cfg() ? JSON.stringify([siteKey(s), m.landing_utc, m.need, m.criteria, m.verdict, m.slip_margin_days, nv.slip || 0]) : '';
  }
  function renderDecide() {
    var box = $('nvDecide'); if (!box) { return; }
    var A = app(), s = curSite(), m = curMission(), key = decideKey();
    if (!s || !m) { box.innerHTML = '<li class="dp-step"><p class="nv-hint">Choose a site to see the decision path.</p></li>'; return; }
    if (key === nv.decideKey) { return; }
    nv.decideKey = key;
    var tok = nv.decideTok = (nv.decideTok || 0) + 1;
    var n = m.days.length, fail = nv.slip > 0 ? Math.min(nv.slip, n - 1) : (m.verdict === 'yes' ? m.slip_margin_days + 1 : 0), cls = m.verdict.replace(' ', '').replace('/', '');
    var failDay = fail < n ? m.days[fail] : null;
    var step = function (num, title, id, body) {
      return '<li class="dp-step" id="' + id + '"><h3><span class="stepn" aria-hidden="true">' + num + '</span>' + title + '</h3><div class="dp-body">' + body + '</div></li>';
    };
    var ans = '<p class="dp-big"><span class="vpill v-' + cls + '">' + ICON[m.verdict] + ' ' + WORD[m.verdict] + '</span></p><p>' +
      (m.verdict === 'yes' ? (m.slip_margin_days >= n - 1 ? 'Every one of the ' + n + ' landing days checked works.' : 'Landing ' + fmtDay(m.landing_utc) + ' works, and the launch can slip up to <b>' + plural(m.slip_margin_days, 'day') + '</b>.') :
        'Landing ' + fmtDay(m.landing_utc) + ' does not give a clear yes.' + (m.next_good_dates.length ? ' Next good date: <b>' + fmtDay(m.next_good_dates[0]) + '</b>.' : '')) + '</p>' +
      '<p class="nv-cap">' + m.days.filter(function (d) { return d.verdict === 'yes'; }).length + ' of ' + n + ' landing days are Yes; ' + m.unsure_dates + (m.unsure_dates === 1 ? ' is' : ' are') + ' Not sure.</p>';
    /* what was actually checked: the grid the answer is computed on, the next coarser grid, a finer sampling of the nearest ground */
    var gm = m.sure && m.sure.grid_resolution_m ? m.sure.grid_resolution_m : (m.terrain_grid && m.terrain_grid.resolution_m);
    var yn = function (b) { return b ? 'yes' : 'no'; };
    var sure = '<ul class="dp-list">' + (m.sure ? '<li><b>' + m.sure.points_passing + ' of ' + m.sure.points + '</b> touchdown points within ' + Math.round(m.sure.scatter_m) + ' m pass' + (gm ? ', on ' + (gm >= 1000 ? (gm / 1000).toFixed(2) + ' km' : Math.round(gm) + ' m') + ' terrain' : '') + '</li>' +
        (m.sure.coarse_label ? '<li>Next coarser grid (' + esc(String(m.sure.coarse_label).split(';')[0]) + '): ' + yn(m.sure.coarse_passes) + '; finer sampling of the nearest ground: ' + yn(m.sure.near_passes) + '</li>' : '') : '') +
      (m.finer_grid_check ? '<li>' + esc(m.finer_grid_check.short) + '</li>' : (gm && gm <= 5 ? '<li>This is the finest LOLA terrain there is for this spot.</li>' : '<li>No finer LOLA grid covers this spot.</li>')) +
      '<li id="dpSlope">Slope: checking…</li><li id="dpTouch">Safe touchdown: checking…</li></ul>';
    var why = failDay ? '<p>' + (fail === 0 ? 'The planned day itself' : 'A slip of <b>' + plural(fail, 'day') + '</b> (landing ' + fmtDay(failDay.landing_utc) + ')') + ' gives <span class="vpill v-' + failDay.verdict.replace(' ', '').replace('/', '') + '">' + WORD[failDay.verdict] + '</span>' +
      (failDay.reasons && failDay.reasons.length ? ': ' + esc(failDay.reasons[0]) : (failDay.unsure_because && failDay.unsure_because.length ? ': ' + esc(failDay.unsure_because[0]) : '')) + '.</p><p id="dpGround" class="nv-cap">Finding the ground that blocks…</p>' +
      '<button type="button" class="btn sm" id="dpShowDay">Show that day on the strip</button>' :
      '<p>No landing day in the ' + n + ' checked fails, so nothing ends the margin here.</p>';
    var todo = '<ol class="dp-opts" id="dpOpts"><li class="nv-hint">Checking other days and other south-pole sites…</li></ol>' +
      '<p class="nv-cap">Ranked by answer, then slip margin, then distance. Distances are along the surface between the coordinates the server gives, on a Moon of radius 1,737.4 km. The same need and rules as above.</p>';
    box.innerHTML = step(1, 'Answer', 'dp1', ans) + step(2, 'How sure', 'dp2', sure) + step(3, 'Why', 'dp3', why) + step(4, 'What to do' + (failDay && fail > 0 ? (nv.slip > 0 ? ' after a slip of ' + plural(fail, 'day') : ' if it slips ' + plural(fail, 'day') + ' or more') : ''), 'dp4', todo);
    if ($('dpShowDay')) { $('dpShowDay').addEventListener('click', function () { app().setSlip(fail); var h = $('h-mission'); if (h) { h.scrollIntoView({ block: 'start' }); } }); }
    /* 2: slope and safe touchdown, from the safety add-ons */
    safetyFor(s).then(function (sf) {
      if (tok !== nv.decideTok || !$('dpSlope')) { return; }
      $('dpSlope').innerHTML = sf && sf.available && sf.steepest ? 'Slope: <b>' + esc(sf.word) + '</b>, steepest of ' + sf.points_known + ' points ' + sf.steepest.slope_deg.toFixed(1) + '° against NASA’s ' + sf.limit_deg + '° limit <span class="mtag ter">' + esc(sf.grid_words || '') + '</span>' :
        'Slope: not known here (no fine terrain grid covers this site).';
    });
    getOnce(dcache, 'st' + siteKey(s), function () {
      var q = s.id ? 'id=' + encodeURIComponent(s.id) : 'lat=' + s.lat + '&lon=' + s.lon + '&name=' + encodeURIComponent(s.name || '');
      return napi('/api/addons/safetouch/site?' + q);
    }).then(function (st) {
      if (tok !== nv.decideTok || !$('dpTouch')) { return; }
      var c = st && st.available && st.classes ? st.classes.filter(function (k) { return k.available !== false && k.p8 !== undefined; }) : [];
      $('dpTouch').innerHTML = c.length ? 'Chance the ground under the lander is under ' + st.limit_deg + '°: ' + c.map(function (k) { return '<b>' + k.p8 + '%</b> for the ' + esc(k.label); }).join(', ') +
        ' <span class="mtag ill">landing accuracies assumed</span>' : 'Safe-touchdown chance: not known here (no 5 m grid).';
    }).catch(function () { if ($('dpTouch')) { $('dpTouch').textContent = 'Safe-touchdown chance: not known here.'; } });
    /* 3: the ground that blocks on the failing day (geometry only) */
    if (failDay) {
      var wb = whyBodyFor(s); wb.day = fail;
      getOnce(dcache, 'w' + JSON.stringify(wb), function () { return napi('/api/why', wb); }).then(function (w) {
        if (tok !== nv.decideTok || !$('dpGround')) { return; }
        $('dpGround').textContent = whyDiffers(w) + ' (' + w.labels.real.charAt(0).toUpperCase() + w.labels.real.slice(1) + '.)';
      }).catch(function () { if ($('dpGround')) { $('dpGround').textContent = ''; } });
    }
    /* 4: wait for a later day here, or move to another south-pole site on the failing day */
    var opts = [];
    var when = failDay || m.days[0];
    for (var k = fail + 1; k < n; k++) {
      if (m.days[k].verdict === 'yes') { opts.push({ kind: 'wait', verdict: 'yes', margin: marginFrom(m, k), days: k, name: s.name, landing: m.days[k].landing_utc, km: 0 }); break; }
    }
    if (!opts.length && m.next_good_dates.length) {
      var gd = m.next_good_dates.filter(function (d) { return Date.parse(d) > Date.parse(when.landing_utc); })[0];
      if (gd) { opts.push({ kind: 'wait', verdict: 'yes', margin: null, days: Math.round((Date.parse(gd) - Date.parse(m.landing_utc)) / 86400000), name: s.name, landing: gd, km: 0 }); }
    }
    var cands = A.catalog().filter(function (c) { return c.group === 'South pole' && c.terrain && !/always dark/.test(c.name) && !(c.lat === s.lat && c.lon === s.lon); });
    var draw = function (pending) {
      if (tok !== nv.decideTok || !$('dpOpts')) { return; }
      var list = opts.slice().sort(function (a, b) {
        return (RANK[b.verdict] - RANK[a.verdict]) || ((b.margin === null ? -1 : b.margin) - (a.margin === null ? -1 : a.margin)) || (a.km - b.km) || (a.days - b.days);
      }).slice(0, 5);
      $('dpOpts').innerHTML = list.map(function (o, i) {
        var c2 = o.verdict.replace(' ', '').replace('/', '');
        return '<li class="dp-opt' + (i === 0 ? ' best' : '') + '"><span class="vpill v-' + c2 + '">' + ICON[o.verdict] + ' ' + WORD[o.verdict] + '</span> ' +
          (o.kind === 'wait' ? '<b>Wait</b> and land here on ' + fmtDay(o.landing) + ' (' + plural(o.days, 'day') + ' after the plan)' :
            '<b>Move ' + Math.round(o.km) + ' km</b> to ' + esc(o.name) + ', landing ' + fmtDay(o.landing)) +
          (o.margin !== null && o.margin >= 0 && o.verdict === 'yes' ? '; slip margin then ' + plural(o.margin, 'day') : '') +
          (o.kind === 'move' ? ' <button type="button" class="btn sm" data-go="' + esc(o.id) + '">Show this site</button>' : '') + '</li>';
      }).join('') + (pending ? '<li class="nv-hint">Still checking ' + plural(pending, 'site') + '…</li>' : '') + (!list.length && !pending ? '<li>No option within the days and sites checked.</li>' : '');
      Array.prototype.forEach.call($('dpOpts').querySelectorAll('[data-go]'), function (b) {
        b.addEventListener('click', function () { var c = A.catalog().filter(function (x) { return x.id === b.getAttribute('data-go'); })[0]; if (c) { app().pick({ id: c.id, name: c.name, lat: c.lat, lon: c.lon }); } });
      });
    };
    draw(cands.length);
    /* the real missions that face this choice soon, from the missions board's API */
    getOnce(dcache, 'impact', function () { return napi('/api/addons/impact'); }).then(function (im) {
      if (tok !== nv.decideTok || !$('dp4') || !im || !im.available || !im.missions) { return; }
      var mm = A.catalog().filter(function (c) { return c.id === 'mouton'; })[0];
      var mou = im.missions.filter(function (x) { return /Mons Mouton/.test(x.place_text || ''); });
      var other = im.missions.filter(function (x) { return mou.indexOf(x) < 0; });
      var p = document.createElement('p'); p.className = 'dp-relay dp-real';
      p.innerHTML = '<b>Real missions facing this choice soon:</b> ' + mou.map(function (x) { return esc(x.name) + ' (' + esc(x.launch_text) + ')'; }).join(', ') +
        (mou.length ? ' plan to land at Mons Mouton' + (mm ? ', ' + Math.round(kmBetween(s, mm)) + ' km from this site' : '') + '. ' : '') +
        other.map(function (x) { return esc(x.name) + ' (' + esc(x.launch_text) + '): ' + esc(x.place_text); }).join('; ') + (other.length ? '. ' : '') +
        '<a href="#h-missions">What a week or a month of slip does to each</a>';
      var at = $('dpOpts'); if (at && at.parentNode) { at.parentNode.insertBefore(p, at); }
    }).catch(function () { /* the board is an extra */ });
    /* a relay satellite: the Earth-contact hours it would add on the failing day, from the relay add-on */
    if (failDay) {
      var rq = (s.id ? 'site=' + encodeURIComponent(s.id) : 'lat=' + s.lat + '&lon=' + s.lon + '&name=' + encodeURIComponent(s.name || '')) + '&landing=' + encodeURIComponent(failDay.landing_utc);
      getOnce(dcache, 'r' + rq, function () { return napi('/api/addons/relay/window?' + rq); }).then(function (r) {
        if (tok !== nv.decideTok || !$('dp4') || !r || !r.available || !r.hours) { return; }
        var p = document.createElement('p'); p.className = 'dp-relay';
        p.innerHTML = '<b>Or add a relay satellite</b> (it helps when Earth contact is short, not when sunlight is): on ' + fmtDay(failDay.landing_utc) + ' the lander could talk home for <b>' + r.hours.either +
          ' h</b> through the Earth or a relay, against ' + r.hours.earth + ' h direct. <span class="mtag ill">' + esc(r.label) + '</span> <a href="#foldRelay">More in Talking to Earth</a>';
        var opts2 = $('dpOpts'); if (opts2 && opts2.parentNode) { opts2.parentNode.insertBefore(p, opts2.nextSibling); }
      }).catch(function () { /* the relay figure is an extra */ });
    }
    var left = cands.length;
    cands.forEach(function (c) {
      var b = app().body({ id: c.id }); b.landing = when.landing_utc; b.slip_days = 30;
      getOnce(dcache, 'm' + JSON.stringify(b), function () { return napi('/api/mission', b); }).then(function (r) {
        opts.push({ kind: 'move', id: c.id, verdict: r.verdict, margin: r.verdict === 'yes' ? r.slip_margin_days : null, days: fail, name: c.friendly_name || c.name, landing: r.landing_utc, km: kmBetween(s, c) });
      }).catch(function () {}).then(function () { left -= 1; draw(left); });
    });
  }

  function say(t) { var s = $('nvSay'); if (s) { s.textContent = ''; setTimeout(function () { s.textContent = t; }, 30); } }

  function update() {
    if (!app() || !app().cfg()) { return; }
    var asl = app().slip ? app().slip() : 0;
    if (asl !== nv.slipSeen) { nv.slipSeen = asl; nv.slip = asl; nv.decideKey = ''; nv.lastSel = ''; }
    renderList(); syncWhen(); renderVerdict(); loadWhy(); renderDecide();
    clearTimeout(nv.syncT);
    nv.syncT = setTimeout(function () {
      var s1 = curSite(), m1 = curMission(), A1 = app(); if (!s1 || !m1 || !A1.cfg()) { return; }
      var loaded = A1.selected().filter(function (x, i) { return A1.mission(i); }).length;
      var k1 = siteKey(s1) + '|' + A1.cfg().start + '|' + JSON.stringify(m1.need) + '|' + loaded;
      if (k1 === nv.syncK) { return; }
      nv.syncK = k1;
      /* a plain request (no add-on header), answered from the server's cache, so brief, thermal and planner follow the shown site */
      fetch('/api/mission', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(A1.body(s1)) }).catch(function () {});
    }, 700);
    var key = JSON.stringify([app().selected().map(siteKey), app().current(), app().cfg().start, app().selected().map(function (s, i) { return app().mission(i) ? app().mission(i).verdict + app().mission(i).landing_utc : ''; })]);
    if (key !== nv.lastSel) { nv.lastSel = key; renderCompare(); }
  }
  function init() {
    if (!$('navigator')) { return; }
    buildSitePicker(); buildWhen(); buildScrub(); buildPresets(); checkEstimate();
    var hideStart = function () { var s = $('nvStart'); if (s) { s.hidden = true; } };
    try { if (window.localStorage.getItem('slipday.hideStart') === '1') { hideStart(); } } catch (e) { /* storage blocked: show the steps */ }
    if ($('nvHideStart')) { $('nvHideStart').addEventListener('click', function () { hideStart(); try { window.localStorage.setItem('slipday.hideStart', '1'); } catch (e) { /* fine */ } var h = $('h-site'); if (h) { h.setAttribute('tabindex', '-1'); h.focus(); } }); }
    document.addEventListener('slipday:update', update);
    Array.prototype.forEach.call(document.querySelectorAll('.nv-viewtabs [data-view]'), function (b) {
      b.addEventListener('click', function () {
        nv.view = b.getAttribute('data-view');
        Array.prototype.forEach.call(document.querySelectorAll('.nv-viewtabs [data-view]'), function (x) { x.setAttribute('aria-pressed', x === b ? 'true' : 'false'); });
        $('nvFace').hidden = nv.view !== 'sky'; $('nvKey').hidden = nv.view === 'sky';
        if (nv.why && !nv.why.error) { drawChart(); }
      });
    });
    Array.prototype.forEach.call(document.querySelectorAll('.nv-viewtabs [data-face]'), function (b) {
      b.addEventListener('click', function () {
        nv.face = b.getAttribute('data-face');
        Array.prototype.forEach.call(document.querySelectorAll('.nv-viewtabs [data-face]'), function (x) { x.setAttribute('aria-pressed', x === b ? 'true' : 'false'); });
        if (nv.why && !nv.why.error) { drawChart(); }
      });
    });
    /* the proof tiles: the headline figure stays in view; the long method text folds under it, nothing is removed */
    var tiles = $('validTiles');
    if (tiles && window.MutationObserver) {
      var foldTiles = function () {
        Array.prototype.forEach.call(tiles.querySelectorAll('.tile > .s'), function (s) {
          if (s.parentElement.tagName === 'DETAILS' || s.textContent.length < 140) { return; }
          var d = document.createElement('details'); d.className = 'tileMore';
          var sm = document.createElement('summary'); sm.textContent = 'How it was checked';
          s.parentNode.insertBefore(d, s); d.appendChild(sm); d.appendChild(s);
        });
      };
      new MutationObserver(foldTiles).observe(tiles, { childList: true, subtree: true });
      foldTiles();
    }
    if ($('nvDl')) { $('nvDl').addEventListener('click', function () { var d = $('dlAnswer'); if (d) { d.click(); say('Downloading this answer as CSV.'); } else { say('The answer is still being worked out; try again in a moment.'); } }); }
    if ($('nvLink')) {
      $('nvLink').addEventListener('click', function () {
        var b = $('nvLink'), done = function (ok) { b.textContent = ok ? 'Link copied' : 'Copy it from the address bar'; setTimeout(function () { b.textContent = 'Copy a link to this view'; }, 2000); };
        if (navigator.clipboard && navigator.clipboard.writeText) { navigator.clipboard.writeText(location.href).then(function () { done(true); }, function () { done(false); }); } else { done(false); }
      });
    }
    /* one-click colouring of the first-screen map: days of slip, slope, or plain relief */
    var mapTabs = function () {
      var lay = $('mapLayer') ? $('mapLayer').value : '', sl = $('sdS-toggle') && $('sdS-toggle').checked;
      var on = sl ? 'slope' : (lay === 'margin' ? 'margin' : (lay === '' ? '' : null));
      Array.prototype.forEach.call(document.querySelectorAll('.nv-maptabs [data-ml]'), function (b) { b.setAttribute('aria-pressed', b.getAttribute('data-ml') === on ? 'true' : 'false'); });
      var said = $('nvMapSay');
      if (said) {
        said.textContent = on === 'margin' ? 'Coloured by the days of slip the planned landing survives at each point: darker blue keeps the landing longer.' :
          on === 'slope' ? 'Coloured by slope at 13 touchdown points: green flat, amber flat enough, red too steep.' : 'Shaded relief from NASA LOLA heights. Click a point to check it as a site.';
      }
    };
    Array.prototype.forEach.call(document.querySelectorAll('.nv-maptabs [data-ml]'), function (b) {
      b.addEventListener('click', function () {
        var want = b.getAttribute('data-ml'), ml = $('mapLayer'), tg = $('sdS-toggle');
        var setLayer = function (v) { if (ml && ml.value !== v) { ml.value = v; ml.dispatchEvent(new Event('change')); } };
        var setSlope = function (on) {
          if (!tg || tg.checked === on) { return; }
          if (on) { var r = document.querySelector('input[name="sdS-mode"][value="slope"]'); if (r && !r.checked) { r.checked = true; r.dispatchEvent(new Event('change')); } }
          tg.checked = on; tg.dispatchEvent(new Event('change'));
        };
        if (want === 'slope') { setLayer(''); setSlope(true); } else { setSlope(false); setLayer(want); }
        mapTabs();
      });
    });
    document.addEventListener('change', function (ev) { if (ev.target && (ev.target.id === 'mapLayer' || ev.target.id === 'sdS-toggle')) { mapTabs(); } });
    setTimeout(mapTabs, 1500);
    if ($('nvCompute')) {
      var chipTries = 0;
      var chip = function () { if (!nv.why && chipTries++ < 20) { setTimeout(chip, 1500); return; }
      Promise.all([napi('/api/addons/fullmap/about'), napi('/api/map')]).then(function (r) {
        var fa = r[0], mp = r[1], w = nv.why, parts = [];
        var nClose = mp && mp.slip_field && mp.slip_field.available ? mp.slip_field.n * mp.slip_field.n : 0;
        var nFull = fa && fa.coverage ? fa.coverage.done : 0;
        if (!nFull && !nClose) { return; }
        var dirs = w && w.skyline ? w.skyline.az_deg.length : null, reach = w && w.horizon ? Math.round(w.horizon.min_coverage_km) : null;
        $('nvCompute').innerHTML = 'Behind this map: ' + (nFull + nClose).toLocaleString('en-US') + ' terrain skylines (' + nFull.toLocaleString('en-US') + ' every ' + (fa.grid_spacing_m / 1000) + ' km, ' +
          nClose.toLocaleString('en-US') + ' every ' + mp.slip_field.step_m + ' m near the pole)' + (dirs ? ', ' + dirs + ' directions each' : '') + (reach ? ', reaching at least ' + reach + ' km' : '') +
          ', on NASA LOLA heights' + (w && w.horizon ? ' (' + esc(String(w.horizon.dem_label).split(';')[0]) + ' at this site)' : '') + '.';
        $('nvCompute').hidden = false;
      }).catch(function () { /* a caption only */ }); };
      chip();
    }
    /* the planner add-on loads only when its box comes near the screen, so the first load never waits on it */
    var plBox = $('addon-planner');
    if (plBox && window.IntersectionObserver) {
      var plIo = new IntersectionObserver(function (ents) {
        if (!ents.some(function (en) { return en.isIntersecting; })) { return; }
        plIo.disconnect();
        var sc = document.createElement('script'); sc.src = '/static/addons/planner.js';
        /* it follows the page's own mission answers: ask once more for the shown site so it starts on the right one */
        sc.onload = function () { var s0 = curSite(); if (s0 && app().cfg()) { fetch('/api/mission', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(app().body(s0)) }).catch(function () {}); } };
        document.body.appendChild(sc);
      }, { rootMargin: '300px 0px' });
      plIo.observe(plBox);
    }
    if ($('nvBestGo')) {
      $('nvBestGo').addEventListener('click', function () {
        var cfg = app().cfg(), mon = cfg ? cfg.start.slice(0, 7) : '', out = $('nvBest'), b = $('nvBestGo');
        b.disabled = true; out.innerHTML = '<p class="nv-hint">Checking the best map points for ' + esc(mon) + '; the first time for a month this takes 7 to 40 seconds…</p>';
        napi('/api/addons/bestspots?month=' + encodeURIComponent(mon)).then(function (r) {
          b.disabled = false;
          if (!r || !r.available) { out.innerHTML = '<p class="nv-hint">' + esc((r && r.reason) || 'Not available.') + '</p>'; return; }
          if (!r.spots || !r.spots.length) { out.innerHTML = '<p class="nv-hint">No clear Yes, flat enough, was found for ' + esc(r.month) + ' among ' + r.candidates_checked + ' points checked.</p>'; return; }
          out.innerHTML = '<ol class="nv-bestlist">' + r.spots.map(function (sp, k) {
            return '<li><b>' + esc(sp.friendly_name) + '</b> <small>' + esc(sp.subtitle || '') + '</small><br>Yes on ' + esc(fmtDay(sp.landing_utc)) + ', can slip ' + plural(sp.slip_margin_days, 'day') +
              ' (' + sp.points_passing + ' of ' + sp.points + ' touchdown points)' + (sp.slope && sp.slope.known ? '; steepest slope ' + sp.slope.steepest_deg.toFixed(1) + '°' : '') +
              ' <button type="button" class="btn sm" data-best="' + k + '">Show on map</button></li>';
          }).join('') + '</ol><p class="nv-cap">' + esc(r.rule || '') + ' Need: ' + (r.need ? r.need.sunlit_h + ' sunlit h, ' + r.need.earth_h + ' h of Earth contact' + (r.need.illustrative ? ' (illustrative)' : '') : '') + '.</p>';
          Array.prototype.forEach.call(out.querySelectorAll('[data-best]'), function (bt) {
            bt.addEventListener('click', function () {
              var sp = r.spots[parseInt(bt.getAttribute('data-best'), 10)];
              if (sp.site_id) { var c = app().catalog().filter(function (x) { return x.id === sp.site_id; })[0]; if (c) { app().pick({ id: c.id, name: c.name, lat: c.lat, lon: c.lon }); } }
              else { app().pick({ name: sp.name_full || sp.friendly_name, friendly_name: sp.friendly_name, lat: sp.map.lat, lon: sp.map.lon }); }
              var hs = $('h-site'); if (hs) { hs.scrollIntoView({ behavior: REDUCED ? 'auto' : 'smooth', block: 'start' }); }
            });
          });
        }).catch(function (e) { b.disabled = false; out.innerHTML = '<p class="nv-hint">The server could not answer: ' + esc(e.message) + '</p>'; });
      });
    }
    /* other add-ons that load only when their box opens or comes near the screen */
    [['addon-findings', '/static/addons/findings.js']].forEach(function (q) {
      var bx = $(q[0]);
      if (!bx || !window.IntersectionObserver) { return; }
      var io2 = new IntersectionObserver(function (ents) {
        if (!ents.some(function (en) { return en.isIntersecting; })) { return; }
        io2.disconnect();
        var sc2 = document.createElement('script'); sc2.src = q[1]; document.body.appendChild(sc2);
      }, { rootMargin: '300px 0px' });
      io2.observe(bx);
    });
    /* one line at the top from the missions board and the regions calendar, every figure read from the API */
    if ($('nvHook')) {
      Promise.all([napi('/api/addons/impact'), napi('/api/region-availability')]).then(function (r) {
        var im = r[0], ra = r[1], hook = $('nvHook');
        var a4 = im && im.missions ? im.missions.filter(function (x) { return x.id === 'artemis4'; })[0] : null;
        var vp = im && im.missions ? im.missions.filter(function (x) { return x.id === 'viper'; })[0] : null;
        var cv = ra && ra.available && ra.main && ra.main.curve ? ra.main.curve : null;
        var pc = function (k) { var c = cv && cv.filter(function (q) { return q.k === k; })[0]; return c ? Math.round(100 * c.coverage) + ' %' : null; };
        var parts = [];
        if (a4 && pc(1) && pc(3)) { parts.push('NASA must keep more than one landing region open for ' + esc(a4.name) + ' (' + esc(a4.launch_text.toLowerCase()) + '): one region works at ' + pc(1) + ' of landing times, three at ' + pc(3) + '.'); }
        if (vp && vp.slip_week) { parts.push('If VIPER’s launch slips a week, ' + vp.slip_week.still_yes + ' of its ' + vp.slip_week.of + ' good landing times survive.'); }
        if (!parts.length) { return; }
        hook.innerHTML = parts.join(' ') + ' <a href="#foldMissions">See the missions</a>';
        hook.hidden = false;
      }).catch(function () { /* the hook is an extra */ });
    }
    /* the section bar marks the section in view */
    if (window.IntersectionObserver) {
      var links = Array.prototype.slice.call(document.querySelectorAll('#jumpBar a[href^="#"]'));
      var targets = links.map(function (a) { var el2 = document.getElementById(a.getAttribute('href').slice(1)); return el2 && el2.tagName !== 'H2' && el2.querySelector('h2') ? el2.querySelector('h2') : el2; });
      var hold = 0;
      links.forEach(function (a) { a.addEventListener('click', function () { hold = Date.now() + 1200; links.forEach(function (x) { if (x === a) { x.setAttribute('aria-current', 'true'); } else { x.removeAttribute('aria-current'); } }); }); });
      var seenTop = {};
      var io = new IntersectionObserver(function (ents) {
        ents.forEach(function (en) { seenTop[en.target.id] = en.isIntersecting ? en.boundingClientRect.top : null; });
        var best = null;
        targets.forEach(function (t, k) { if (t && seenTop[t.id] !== null && seenTop[t.id] !== undefined && best === null) { best = k; } });
        if (best === null || Date.now() < hold) { return; }
        links.forEach(function (a, k) { if (k === best) { a.setAttribute('aria-current', 'true'); } else { a.removeAttribute('aria-current'); } });
      }, { rootMargin: '-60px 0px -55% 0px' });
      targets.forEach(function (t) { if (t) { io.observe(t); } });
    }
    /* a link to something inside a closed fold opens the fold first */
    document.addEventListener('click', function (ev) {
      var a = ev.target.closest && ev.target.closest('a[href^="#"]'); if (!a) { return; }
      var t = document.getElementById(a.getAttribute('href').slice(1)); if (!t) { return; }
      for (var p = t; p; p = p.parentElement) { if (p.tagName === 'DETAILS') { p.open = true; } }
    });
    /* section bar: open the section's first fold (never close one), put the section in the address,
       and move focus to its heading so keyboard and screen-reader users land there too */
    Array.prototype.forEach.call(document.querySelectorAll('#jumpBar a[href^="#"]'), function (a) {
      a.addEventListener('click', function () {
        var id = a.getAttribute('href').slice(1), t = document.getElementById(id); if (!t) { return; }
        var fold = t.tagName === 'DETAILS' ? t : (t.querySelector && t.querySelector('details.fold'));
        if (!fold && /^H[1-3]$/.test(t.tagName)) {
          for (var s = t.nextElementSibling; s && !s.classList.contains('groupHead'); s = s.nextElementSibling) {
            if (s.matches('details.fold')) { fold = s; break; }
            var inner = s.querySelector && s.querySelector('details.fold'); if (inner && s.tagName !== 'SECTION') { fold = inner; break; }
          }
        }
        if (fold && !fold.open) { fold.open = true; }
        setTimeout(function () { setSectionInAddress(id); }, 400);   /* after the link's own jump and the plan's address update */
        var h = /^H[1-3]$/.test(t.tagName) ? t : (t.querySelector('h2, h3, summary') || t);
        if (!h.hasAttribute('tabindex') && !/^(SUMMARY|A|BUTTON)$/.test(h.tagName)) { h.setAttribute('tabindex', '-1'); }
        setTimeout(function () { try { h.focus({ preventScroll: true }); } catch (e) { /* focus is an extra */ } }, 60);
      });
    });
    /* opening a fold updates the address, so the open section can be shared and reloaded */
    Array.prototype.forEach.call(document.querySelectorAll('details.fold[id]'), function (d) {
      d.addEventListener('toggle', function () { if (d.open && sectionReady) { setSectionInAddress(d.id); } });
    });
    /* the plan lives in the address (s=…&d=…); the open section is kept beside it as at=<id>, never replacing it */
    function setSectionInAddress(id) {
      var parts = String(location.hash || '').replace(/^#/, '').split('&').filter(function (kv) { return kv && /=/.test(kv) && kv.indexOf('at=') !== 0; });
      parts.push('at=' + encodeURIComponent(id));
      try { history.replaceState(null, '', '#' + parts.join('&')); } catch (e) { /* the address is an extra */ }
    }
    var sectionReady = false;
    (function () {
      var m = /(?:^#|&)at=([^&]+)/.exec(location.hash || ''); var t = m ? document.getElementById(decodeURIComponent(m[1])) : null;
      setTimeout(function () {
        sectionReady = true;
        if (!t) { return; }
        for (var p = t; p; p = p.parentElement) { if (p.tagName === 'DETAILS') { p.open = true; } }
        if (t.tagName === 'DETAILS') { t.open = true; }
        t.scrollIntoView();
      }, 1500);
    })();
    /* back to top, shown after the first screen */
    var top = document.createElement('a');
    top.href = '#'; top.id = 'toTop'; top.className = 'btn'; top.textContent = 'Back to top'; top.hidden = true;
    top.addEventListener('click', function (ev) {
      ev.preventDefault(); window.scrollTo({ top: 0, behavior: matchMedia('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth' });
      var h1 = document.querySelector('header.top h1'); if (h1) { h1.setAttribute('tabindex', '-1'); h1.focus({ preventScroll: true }); }
    });
    document.body.appendChild(top);
    var tt = false;
    window.addEventListener('scroll', function () { if (tt) { return; } tt = true; requestAnimationFrame(function () { tt = false; top.hidden = window.scrollY < window.innerHeight * 1.5; }); }, { passive: true });
    /* one line on rocks under the slope check, in the API's own words */
    if ($('rocksLine')) {
      napi('/api/addons/rocks').then(function (r) {
        var t = r && (r.available === false ? (r.why ? 'Rocks and boulders: no value is shown. ' + r.why : '') : (r.summary || r.note || r.headline || ''));
        if (t) { $('rocksLine').textContent = t; $('rocksLine').hidden = false; }
      }).catch(function () { /* the line is an extra */ });
    }
    var rt = null;
    window.addEventListener('resize', function () { clearTimeout(rt); rt = setTimeout(function () { if (nv.why && !nv.why.error) { drawChart(); drawStrip(); } }, 120); });
    update();
  }
  if (document.readyState === 'loading') { document.addEventListener('DOMContentLoaded', init); } else { init(); }
  window.SlipdayNavigator = { state: function () { return nv; }, setHour: setHour };
})();
