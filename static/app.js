/* Slipday front end. No dependencies; charts are hand-built SVG. */
(function () {
  'use strict';

  var $ = function (id) { return document.getElementById(id); };
  var SVGNS = 'http://www.w3.org/2000/svg';
  var MAX_SITES = 4;
  /* The page opens on a worked example chosen by a written rule (LOCAL_PASS_2_RESULTS.md, section H):
     the first scatter-robust map point whose full card is a clear Yes on the 80 m grid and on NASA's 20 m grid.
     The second site is the opposite case, kept on the page on purpose: Yes on 80 m, Not sure on 20 m. */
  var DEFAULT_SITES = ['robust_pick', 'shackleton', 'im2', 'im1'];
  var OPENING = { date: '2026-11-18', hour: 0 };
  var state = {
    catalog: [], selected: [], data: [], idx: 0, playing: null, slip: null,
    metricsTimer: null, metricsBusy: false, metricsWanted: false, lastCfg: null,
    terrain: null, map: null, maps: {}, layer: '', zoom: '', year: {}, reqId: 0,
    missions: [], mi: 0, slipmap: null, slipmapKey: '', replays: [], pairs: null,
    circles: {}, robust: null, robustKey: '', classes: {}, why: null, whyKey: '', whyDay: 0, ribbon: {},
    robustMap: null, robustMapKey: '', mapScatter: true, mapPsr: false, busyTries: 0
  };

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
  function fmtUtc(unix) {
    var d = new Date(unix * 1000);
    return d.toISOString().slice(0, 16).replace('T', ' ') + ' UTC';
  }
  var MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
  function fmtDay(unix) {
    var d = new Date(unix * 1000);
    return MONTHS[d.getUTCMonth()] + ' ' + d.getUTCDate();
  }
  function fmtHours(h) {
    if (h === null || h === undefined) { return 'n/a'; }
    if (h < 48) { return h.toFixed(1) + ' h'; }
    return (h / 24).toFixed(1) + ' d';
  }
  function fmtLatLon(lat, lon) {
    return Math.abs(lat).toFixed(3) + (lat < 0 ? ' S' : ' N') + ', ' + Math.abs(lon).toFixed(3) + (lon < 0 ? ' W' : ' E');
  }
  function api(path, body, tries) {
    var opt = body ? { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) } : {};
    return fetch(path, opt).then(function (r) {
      return r.json().then(function (j) {
        /* the server is working out skylines for other requests: ask again by itself a few times before saying so */
        if (r.status === 503 && j.busy && (tries || 0) < 3) {
          return new Promise(function (res) { setTimeout(res, 4000 * ((tries || 0) + 1)); }).then(function () { return api(path, body, (tries || 0) + 1); });
        }
        if (!r.ok) {
          var e = new Error(typeof j.detail === 'string' ? j.detail : JSON.stringify(j.detail));
          e.busy = r.status === 503; e.retryAfter = j.retry_after_s || 20;
          throw e;
        }
        return j;
      });
    });
  }
  function siteRef(s) { return s.id ? { id: s.id } : { name: s.name, lat: s.lat, lon: s.lon }; }
  function num(id, dflt) { var v = parseFloat($(id).value); return isFinite(v) ? v : dflt; }

  /* Settings. Returns null (and says why) when the date field is empty or
     unreadable; callers then keep what is on screen instead of throwing. */
  function settings() {
    var raw = $('start').value;
    var hour = parseInt($('mHour').value, 10) || 0;
    var t = Date.parse(raw + 'T00:00:00Z');
    if (!raw || !isFinite(t)) {
      $('siteMsg').textContent = 'Choose a landing date to update the page.';
      $('slipNote').textContent = 'Choose a landing date to update the grid.';
      $('missionOut').innerHTML = '<p class="note">Choose a landing date.</p>';
      return null;
    }
    t += hour * 3600000;
    return {
      start: new Date(t).toISOString().slice(0, 19) + 'Z', startMs: t,
      hours: parseInt($('span').value, 10),
      scatter: num('scatter', 100),
      need: {
        need_sun_h: Math.max(0, num('needSun', 240)), need_earth_h: Math.max(0, num('needEarth', 100)),
        window_days: parseFloat($('slipWindow').value),
        sun_at_touchdown: $('tdSun').checked, earth_at_touchdown: $('tdEarth').checked
      },
      opts: {
        mask_deg: num('mask', 0), min_sun_el: num('minSun', -90), min_earth_el: num('minEarth', -90),
        terrain: $('useTerrain').checked, mast_m: num('mast', 2),
        min_sun_fraction: num('sunRule', 0.5), earth_margin_deg: num('earthMargin', 0),
        earth_stations: $('earthStations') ? $('earthStations').checked : true
      }
    };
  }
  function withOpts(obj, cfg) { for (var k in cfg.opts) { obj[k] = cfg.opts[k]; } return obj; }
  function withNeed(obj, cfg) { for (var k in cfg.need) { obj[k] = cfg.need[k]; } return withOpts(obj, cfg); }
  function fmtDate(iso) {
    var t = Date.parse(iso) / 1000, d = new Date(t * 1000);
    return fmtDay(t) + (d.getUTCHours() ? ' ' + ('0' + d.getUTCHours()).slice(-2) + ':00' : '');
  }
  function plural(n, w) { return n + ' ' + w + (n === 1 ? '' : 's'); }
  function optQuery(cfg) {
    return Object.keys(cfg.opts).map(function (k) { return k + '=' + encodeURIComponent(cfg.opts[k]); }).join('&');
  }
  function scrubUnix() {
    var d = state.data[0];
    if (d) { return d.series.start_unix + state.idx * d.series.step_minutes * 60; }
    return (state.lastCfg ? state.lastCfg.startMs : Date.now()) / 1000;
  }
  /* Short provenance tag for one horizon: "terrain (LOLA, 80 m/px)" or "smooth sphere". */
  function modelTag(h) {
    if (!h) { return ''; }
    if (h.kind === 'profile') { return 'terrain (' + String(h.dem_label || 'DEM').split(';')[0] + ')' + (h.validated === false ? ', not validated' : ''); }
    if (h.kind === 'flat-mask') { return 'smooth sphere + ' + h.mask_deg + '° mask'; }
    return 'smooth sphere';
  }
  function tagHtml(h) {
    var cls = h && h.kind === 'profile' ? (h.synthetic ? 'mtag syn' : 'mtag ter') : 'mtag smo';
    return '<span class="' + cls + '">' + esc(modelTag(h)) + '</span>';
  }

  /* ---------- site picker ---------- */
  function renderPicker() {
    var groups = {};
    state.catalog.forEach(function (s) { (groups[s.group] = groups[s.group] || []).push(s); });
    var html = '';
    Object.keys(groups).forEach(function (g) {
      html += '<optgroup label="' + esc(g) + '">';
      groups[g].forEach(function (s) {
        html += '<option value="' + esc(s.id) + '">' + esc(s.name) + '</option>';
      });
      html += '</optgroup>';
    });
    $('sitePick').innerHTML = html;
  }
  function addSite(s) {
    var msg = $('siteMsg');
    var dup = state.selected.some(function (x) { return x.lat === s.lat && x.lon === s.lon; });
    if (dup) { msg.textContent = 'That site is already selected.'; state.mi = state.selected.findIndex(function (x) { return x.lat === s.lat && x.lon === s.lon; }); refreshAll(); return; }
    msg.textContent = '';
    if (state.selected.length >= MAX_SITES) {                 /* four fit side by side: replace the last one instead of refusing */
      var gone = state.selected.splice(MAX_SITES - 1, 1)[0];
      msg.textContent = 'Four sites fit side by side, so ' + gone.name + ' was replaced.';
    }
    state.selected.push(s);
    state.mi = state.selected.length - 1;
    refreshAll();
  }
  function renderChips() {
    var box = $('chips');
    box.innerHTML = '';
    state.selected.forEach(function (s, i) {
      var chip = document.createElement('span');
      chip.className = 'chip';
      var cat = s.id ? state.catalog.filter(function (x) { return x.id === s.id; })[0] : null;
      chip.innerHTML = '<b>' + (i + 1) + '</b> ' + esc(s.name) + ' <small>' + fmtLatLon(s.lat, s.lon) +
        (cat ? ' · ' + esc(cat.confidence) : ' · typed or picked') + '</small>';
      if (cat) { chip.title = cat.confidence + '. Source: ' + cat.source + (cat.relayed ? ' (copied from the web page)' : '') + (cat.note ? '. ' + cat.note : ''); }
      var b = document.createElement('button');
      b.type = 'button'; b.textContent = '×'; b.setAttribute('aria-label', 'Remove ' + s.name);
      b.addEventListener('click', function () {
        state.selected.splice(i, 1);
        if (state.mi >= state.selected.length) { state.mi = 0; }
        refreshAll();
      });
      chip.appendChild(b);
      box.appendChild(chip);
    });
  }
  function renderMap() {
    var W = 560, H = 190, box = $('map');
    box.innerHTML = '';
    var svg = el('svg', { viewBox: '0 0 ' + W + ' ' + H, role: 'img' });
    var x = function (lon) { return 30 + (lon + 180) / 360 * (W - 40); };
    var y = function (lat) { return 8 + (90 - lat) / 180 * (H - 30); };
    svg.appendChild(el('rect', { x: x(-90), y: y(90), width: x(90) - x(-90), height: y(-90) - y(90), 'class': 'near' }));
    [-180, -90, 0, 90, 180].forEach(function (lon) {
      svg.appendChild(el('line', { x1: x(lon), x2: x(lon), y1: y(90), y2: y(-90), 'class': 'gridl' }));
      svg.appendChild(el('text', { x: x(lon), y: H - 6, 'text-anchor': 'middle' }, lon + '°'));
    });
    [-90, -45, 0, 45, 90].forEach(function (lat) {
      svg.appendChild(el('line', { x1: x(-180), x2: x(180), y1: y(lat), y2: y(lat), 'class': 'gridl' }));
      svg.appendChild(el('text', { x: 24, y: y(lat) + 4, 'text-anchor': 'end' }, lat + '°'));
    });
    svg.appendChild(el('text', { x: x(0), y: y(90) + 12, 'text-anchor': 'middle' }, 'whole Moon; shaded half faces Earth'));
    state.selected.forEach(function (s, i) {
      svg.appendChild(el('circle', { cx: x(s.lon), cy: y(s.lat), r: 5, 'class': 'pt' }));
      var right = s.lon < 150;
      svg.appendChild(el('text', { x: x(s.lon) + (right ? 8 : -8), y: y(s.lat) + (i % 2 ? 13 : -4), 'text-anchor': right ? 'start' : 'end', 'class': 'lbl-strong' }, String(i + 1)));
    });
    box.appendChild(svg);
  }

  /* ---------- south polar map (shaded relief made from the DEM) ---------- */
  var R_KM = 1737.4;
  function polarXY(lat, lon) {
    var r = 2 * R_KM * Math.tan((Math.PI / 4) - Math.abs(lat) * Math.PI / 360);
    var lo = lon * Math.PI / 180;
    return [r * Math.sin(lo), r * Math.cos(lo)];
  }
  var SLIP_LAYERS = {
    margin: { label: 'days of slip the planned landing survives', unit: 'd', key: 'margin', zero: -1,
      legend: 'Coloured where a landing on the planned date meets the need. Darker: more days of slip before it stops meeting it.' },
    good: { label: 'number of good landing dates', unit: 'dates', key: 'good', zero: 0,
      legend: 'Number of the candidate landing dates that meet the need. Darker: more good dates.' },
    worst_sun: { label: 'sunlit hours on the worst landing date', unit: 'h', key: 'worst_sun', zero: 0,
      legend: 'Sunlit hours after the worst of the candidate landing dates. Darker: more hours.' },
    median_sun: { label: 'sunlit hours on a typical landing date', unit: 'h', key: 'median_sun', zero: 0,
      legend: 'Sunlit hours after the median candidate landing date. Darker: more hours.' },
    worst_total: { label: 'usable hours on the worst landing date', unit: 'h', key: 'worst_total', zero: 0,
      legend: 'Hours with Sun and Earth both up after the worst of the candidate landing dates. Darker: more hours.' }
  };
  function curMap() { return state.maps[state.zoom] || null; }
  function overlayUrl(vals, n, zero, vmax) {
    var c = document.createElement('canvas'); c.width = n; c.height = n;
    var ctx = c.getContext('2d'), img = ctx.createImageData(n, n);
    var lo = [150, 200, 250], hi = [10, 50, 115];
    for (var i = 0; i < vals.length; i++) {
      var v = vals[i];
      if (v <= zero) { img.data[4 * i + 3] = 0; continue; }
      var t = vmax > zero ? Math.min(1, (v - zero) / (vmax - zero)) : 1;
      t = 0.12 + 0.88 * t;
      for (var k = 0; k < 3; k++) { img.data[4 * i + k] = Math.round(lo[k] + (hi[k] - lo[k]) * t); }
      img.data[4 * i + 3] = 225;
    }
    ctx.putImageData(img, 0, 0);
    return c.toDataURL('image/png');
  }
  /* The margin that survives at all 13 touchdown points: five steps of one hue, light to dark, so that
     neighbouring classes can be told apart; a hollow amber cell where the margin is lost, a hollow grey
     one where the point was not re-checked. */
  var ROBUST_STEPS = [[7, '#0b3470', '7 or more'], [5, '#2466bd', '5 to 6'], [3, '#5a98e3', '3 to 4'], [1, '#9cc3f3', '1 to 2'], [0, '#d6e6fb', '0']];
  function robustClass(v) { for (var i = 0; i < ROBUST_STEPS.length; i++) { if (v >= ROBUST_STEPS[i][0]) { return i; } } return -1; }
  function robustOverlayUrl(vals, n, fine) {
    var K = 8, c = document.createElement('canvas'); c.width = n * K; c.height = n * K;
    var ctx = c.getContext('2d');
    for (var i = 0; i < vals.length; i++) {
      var v = vals[i];
      if (v === -1) { continue; }
      var x = (i % n) * K, y = Math.floor(i / n) * K;
      if (v >= 0) {
        ctx.fillStyle = ROBUST_STEPS[robustClass(v)][1]; ctx.fillRect(x, y, K, K);
        if (fine && fine[i] && !fine[i][1]) { ctx.strokeStyle = '#e11d48'; ctx.lineWidth = 2; ctx.beginPath(); ctx.moveTo(x + 1, y + 1); ctx.lineTo(x + K - 1, y + K - 1); ctx.moveTo(x + K - 1, y + 1); ctx.lineTo(x + 1, y + K - 1); ctx.stroke(); }
        continue;
      }
      if (v === -3 && fine && fine[i] && !fine[i][1]) { ctx.strokeStyle = '#e11d48'; ctx.lineWidth = 2; ctx.strokeRect(x + 1.5, y + 1.5, K - 3, K - 3); continue; }
      ctx.strokeStyle = v === -3 ? '#f5a623' : '#c9c7be'; ctx.lineWidth = 2;
      ctx.strokeRect(x + 1.5, y + 1.5, K - 3, K - 3);
      if (v === -3) { ctx.beginPath(); ctx.moveTo(x + 1.5, y + K - 1.5); ctx.lineTo(x + K - 1.5, y + 1.5); ctx.stroke(); }
    }
    return c.toDataURL('image/png');
  }
  function robustLegend(rm) {
    var c = rm.counts, hist = c.surviving_margin_histogram, cls = [0, 0, 0, 0, 0];
    Object.keys(hist).forEach(function (k) { cls[robustClass(parseInt(k, 10))] += hist[k]; });
    var h = '<span class="lhead">Days of slip that all ' + rm.members + ' touchdown points survive</span>';
    for (var i = ROBUST_STEPS.length - 1; i >= 0; i--) {
      h += '<span class="lsw" style="background:' + ROBUST_STEPS[i][1] + '"></span><span>' + ROBUST_STEPS[i][2] + ' <small>(' + cls[i] + ')</small></span>';
    }
    h += '<span class="lsw lost"></span><span>margin lost within ' + Math.round(rm.scatter_m) + ' m <small>(' + c.lose_their_margin + ')</small></span>';
    if (c.not_re_checked) { h += '<span class="lsw unchecked"></span><span>not re-checked <small>(' + c.not_re_checked + ')</small></span>'; }
    var oneDay = 0;
    Object.keys(hist).forEach(function (k) { if (parseInt(k, 10) >= 1) { oneDay += hist[k]; } });
    h += '<span class="lsum" id="robustSum"><b>' + c.keep_a_margin + ' of the ' + c.re_checked + '</b> map points that pass on the planned date (counting a margin of 0 days) keep a slip margin at all ' + rm.members +
      ' touchdown points; <b>' + c.lose_their_margin + ' lose it</b>. Of the ' + c.keep_a_margin + ', <b>' + oneDay + '</b> survive at least one day of slip. Largest margin: ' + c.largest_single_point_margin + ' days at a single point, ' +
      (c.largest_surviving_margin < 0 ? 'none' : c.largest_surviving_margin + ' days') + ' with the scatter.</span>';
    if (rm.finer) {
      var f = rm.finer;
      h += '<span class="lsw finesw"></span><span class="lsum" id="fineMap"><b>20 m grid check (' + (f.on_request ? 'worked out for this date from stored 20 m skylines' : (f.dates_checked ? 'one of ' + f.dates_checked.length + ' map dates checked, weekly from ' + f.dates_checked[0] : 'this date only')) + '): ' + f.agree + ' of ' + f.points_done + ' re-checked points agree (' +
        (100 * f.agree_share).toFixed(1) + '%)</b> on whether all 13 touchdown points pass on the planned date; ' + f.disagree + ' disagree (red cross); ' + f.equal_margins + ' keep the same margin' +
        (f.complete ? '.' : '; partial: ' + (100 * f.share_done).toFixed(0) + '% of the ' + f.points_total + ' points done.') + '</span>';
    }
    return h;
  }
  function nightLegend(r) {
    var h = '<span class="lhead">Longest night a lander rides through, worst over the 13 touchdown points and the slip days that still pass</span>';
    for (var i = NIGHT_STEPS.length - 1; i >= 0; i--) {
      var c = r.classes.filter(function (x) { return x.label === NIGHT_STEPS[i][2]; })[0];
      h += '<span class="lsw" style="background:' + NIGHT_STEPS[i][1] + '"></span><span>' + NIGHT_STEPS[i][2] + ' <small>(' + (c ? c.points : 0) + ')</small></span>';
    }
    h += '<span class="lsum" id="nightSum"><b>' + r.points + ' map points</b> keep a slip margin at all ' + r.members + ' touchdown points; their worst night ranges from ' + r.night_smallest_h + ' to ' + r.night_largest_h +
      ' h. At ' + r.night_grows_with_slip + ' of them it is longer on some slip day than on the planned date. Hours in the ' + 'window, not a battery model; uncoloured points lose their margin.</span>';
    return h;
  }
  function renderPolar() {
    var box = $('polar'), m = curMap();
    box.innerHTML = '';
    if (!m || !m.available) {
      box.innerHTML = '<p class="note">' + (state.mapFailed ? 'No terrain data is installed, so there is no polar map and every result uses the smooth sphere.' : 'Loading the map…') + '</p>';
      $('mapNote').textContent = ''; $('mapLegend').innerHTML = '';
      return;
    }
    var S = 1000, half = m.half_width_km;
    var px = function (km) { return S / 2 + km / half * (S / 2); };
    var py = function (km) { return S / 2 - km / half * (S / 2); };
    var svg = el('svg', { viewBox: '0 0 ' + S + ' ' + S, role: 'img', 'aria-label': 'South polar map with selected sites' });
    var layer = (m.layers || []).filter(function (l) { return l.id === state.layer; })[0];
    var slipLayer = SLIP_LAYERS[state.layer], sm = state.slipmap, rm = state.robustMap;
    var wantRobust = state.layer === 'margin' && state.mapScatter && state.maps[''] && state.maps[''].scatter_field && state.maps[''].scatter_field.available;
    var useRobust = !!(wantRobust && rm && rm.available && sm && sm.available && rm._key === state.slipmapKey);
    var svm = state.survMap, useNight = !!(slipLayer && slipLayer.survival && svm && svm.available && sm && sm.available && svm._key === state.slipmapKey);
    svg.appendChild(el('image', { x: 0, y: 0, width: S, height: S, href: layer ? layer.image : m.image, preserveAspectRatio: 'none' }));
    var psr = state.mapPsr && m.permanent_shadow && m.permanent_shadow.available ? m.permanent_shadow : null;
    if (psr) { svg.appendChild(el('image', { x: 0, y: 0, width: S, height: S, href: psr.image, preserveAspectRatio: 'none', 'class': 'psr' })); }
    var legend = '';
    if (slipLayer && sm && sm.available) {
      var vals = sm.layers[slipLayer.key], vmax = slipLayer.zero;
      vals.forEach(function (v) { if (v > vmax) { vmax = v; } });
      var w = sm.half_km / half * S;
      svg.appendChild(el('image', { x: S / 2 - w / 2, y: S / 2 - w / 2, width: w, height: w,
        href: useNight ? nightOverlayUrl(svm.layers.night, sm.n) : (useRobust ? robustOverlayUrl(rm.layers.robust, sm.n, rm.finer ? rm.finer.cells : null) : overlayUrl(vals, sm.n, slipLayer.zero, vmax)),
        preserveAspectRatio: 'none', 'class': 'overlay' + (useRobust || useNight ? ' crisp' : '') }));
      svg.appendChild(el('rect', { x: S / 2 - w / 2, y: S / 2 - w / 2, width: w, height: w, 'class': 'ovbox' }));
      var nPos = vals.filter(function (v) { return v > slipLayer.zero; }).length;
      legend = slipLayer.survival ? (useNight ? nightLegend(svm) : '<span class="small">' + (state.survMsg ? 'Not available: ' + esc(state.survMsg) : 'Working out the longest night at 13 touchdown points for every coloured point…') + '</span>') : useRobust ? robustLegend(rm) : '<span class="lz"></span><span>' + (slipLayer.key === 'margin' ? 'planned date fails' : '0') + '</span><span class="ramp"></span><span>' +
        (slipLayer.key === 'margin' ? '0 to ' + vmax + ' days of slip' : 'up to ' + vmax + ' ' + slipLayer.unit) + '</span>' +
        '<span class="small">' + Math.round(100 * nPos / vals.length) + '% of the mapped points are coloured' +
        (wantRobust ? (state.robustMsg ? '. Scatter check: ' + esc(state.robustMsg) : '. Re-checking each coloured point at 13 touchdown points…') : (slipLayer.key === 'margin' ? ' (one point each, no landing scatter)' : '')) + '</span>';
    } else if (slipLayer) {
      legend = '<span class="small">' + (sm && !sm.available ? 'Not available on this installation: ' + esc(sm.reason) : 'Working out ' + (state.mapPts || 'thousands of') + ' skylines against the landing dates…') + '</span>';
    }
    if (psr) { legend += '<span class="lsw psrsw"></span><span title="' + esc(psr.note) + '">permanent shadow: average sunlight zero on the LOLA team’s map, in 480 m cells</span>'; }
    $('mapLegend').innerHTML = legend;
    var rings = half > 150 ? [-88, -86, -84, -82] : (half > 60 ? [-89, -88] : [-89.75, -89.5, -89.25]);
    rings.forEach(function (lat) {
      var r = polarXY(lat, 0)[1] / half * (S / 2);
      svg.appendChild(el('circle', { cx: S / 2, cy: S / 2, r: r, 'class': 'grat' }));
      svg.appendChild(el('text', { x: S / 2 + 6, y: S / 2 - r - 6, 'class': 'gratl' }, Math.abs(lat) + '°S'));
    });
    [0, 90, 180, 270].forEach(function (lon) {
      var a = lon * Math.PI / 180;
      svg.appendChild(el('line', { x1: S / 2, y1: S / 2, x2: px(half * Math.sin(a)), y2: py(half * Math.cos(a)), 'class': 'grat' }));
    });
    svg.appendChild(el('text', { x: S / 2, y: 30, 'text-anchor': 'middle', 'class': 'gratl big' }, '0° · towards Earth ↑'));
    svg.appendChild(el('text', { x: S - 12, y: S / 2 - 10, 'text-anchor': 'end', 'class': 'gratl big' }, '90°E'));
    svg.appendChild(el('text', { x: 12, y: S / 2 - 10, 'class': 'gratl big' }, '90°W'));
    svg.appendChild(el('text', { x: S / 2, y: S - 14, 'text-anchor': 'middle', 'class': 'gratl big' }, '180° · ' + Math.round(2 * half) + ' km across'));
    var shw = state.shadow;
    if (shw && shw.available && half < 80) {
      shw.on_shadow_itself.forEach(function (x) { var p = polarXY(x.lat, x.lon); svg.appendChild(el('circle', { cx: px(p[0]), cy: py(p[1]), r: 9, 'class': 'shOn' })); });
      shw.rows.forEach(function (x, i) {
        var p = polarXY(x.lat, x.lon);
        svg.appendChild(el('circle', { cx: px(p[0]), cy: py(p[1]), r: 11, 'class': 'shRow' }));
        svg.appendChild(el('text', { x: px(p[0]) + 13, y: py(p[1]) - 9, 'class': 'shNum' }, String(i + 1)));
      });
    }
    var wy = state.why, ft = wy && !wy.error && wy.flip && wy.flip.stretch && wy.flip.stretch.terrain;
    if (ft && ft.lat !== undefined && !ft.near_field) {
      var fp = polarXY(ft.lat, ft.lon), fx = px(fp[0]), fy = py(fp[1]);
      if (fx > 0 && fx < S && fy > 0 && fy < S) {
        svg.appendChild(el('path', { d: 'M' + (fx - 12) + ' ' + (fy - 18) + 'L' + (fx + 12) + ' ' + (fy - 18) + 'L' + fx + ' ' + fy + 'Z', 'class': 'flipMark' }));
        svg.appendChild(el('text', { x: fx, y: fy - 24, 'text-anchor': 'middle', 'class': 'flipLab' }, ft.named ? 'ground ' + ft.named.phrase + ' ends the margin' : 'ground that ends the margin'));
      }
    }
    var off = 0;
    state.selected.forEach(function (s, i) {
      var p = polarXY(s.lat, s.lon), cx = px(p[0]), cy = py(p[1]);
      if (s.lat > -60 || cx < 0 || cx > S || cy < 0 || cy > S) { off += 1; return; }
      svg.appendChild(el('circle', { cx: cx, cy: cy, r: 19, 'class': 'ppt' + (i === state.mi ? ' cur' : '') }));
      svg.appendChild(el('text', { x: cx, y: cy + 9, 'text-anchor': 'middle', 'class': 'pnum' }, String(i + 1)));
    });
    function where(ev) {
      var r = svg.getBoundingClientRect();
      var xk = ((ev.clientX - r.left) / r.width * S - S / 2) / (S / 2) * half;
      var yk = (S / 2 - (ev.clientY - r.top) / r.height * S) / (S / 2) * half;
      var o = { xk: xk, yk: yk, cell: -1 };
      if (slipLayer && sm && sm.available && Math.abs(xk) < sm.half_km && Math.abs(yk) < sm.half_km) {
        /* snap to the centre of the mapped point, so the site added is the point that was computed */
        var st = sm.step_m / 1000, col = Math.floor((xk + sm.half_km) / st), row = Math.floor((sm.half_km - yk) / st);
        o.cell = row * sm.n + col;
        o.xk = -sm.half_km + (col + 0.5) * st; o.yk = sm.half_km - (row + 0.5) * st;
      }
      var rr = Math.sqrt(o.xk * o.xk + o.yk * o.yk);
      o.lat = Math.round(-(90 - 2 * Math.atan(rr / (2 * R_KM)) * 180 / Math.PI) * 10000) / 10000;
      o.lon = Math.round(Math.atan2(o.xk, o.yk) * 180 / Math.PI * 1000) / 1000;
      return o;
    }
    svg.addEventListener('click', function (ev) {
      var o = where(ev);
      $('cLat').value = o.lat; $('cLon').value = o.lon;
      addSite({ name: ($('cName').value.trim() || 'Map pick ' + fmtLatLon(o.lat, o.lon)), lat: o.lat, lon: o.lon });
    });
    svg.addEventListener('pointermove', function (ev) {
      var o = where(ev);
      var h = '<b>' + fmtLatLon(o.lat, o.lon) + '</b>';
      if (o.cell >= 0) {
        var L = sm.layers, mg = L.margin[o.cell];
        var rv = useRobust ? rm.layers.robust[o.cell] : -1;
        h += (mg < 0 ? 'Planned date does not meet the need here' : 'Planned landing survives a slip of ' + plural(mg, 'day') + (useRobust ? ' at this point' : '')) +
          (rv >= 0 ? '<br><b>With the landing scatter: ' + plural(rv, 'day') + '</b> at all ' + rm.members + ' touchdown points' :
            (rv === -3 ? '<br><b>With the landing scatter the margin is lost:</b> ' + rm.layers.points_passing[o.cell] + ' of ' + rm.members + ' touchdown points pass on the planned date' :
              (rv === -2 ? '<br>Not re-checked with the landing scatter (no stored skylines for this point)' : ''))) +
          (useNight && svm.layers.night[o.cell] >= 0 ? '<br><b>Longest night ' + svm.layers.night[o.cell] + ' h</b> (planned date: ' + svm.layers.night_day0[o.cell] + ' h), longest Earth outage ' + svm.layers.outage[o.cell] + ' h, worst over the slip days that pass' : '') +
          (useRobust && rm.finer && rm.finer.cells[o.cell] ? '<br><b>20 m ' + (rm.finer.cells[o.cell][1] ? 'agrees' : 'disagrees') + '</b> (20 m margin: ' +
            (rm.finer.cells[o.cell][0] < 0 ? 'lost' : plural(rm.finer.cells[o.cell][0], 'day')) + ')' : '') +
          '<br>Good landing dates: ' + L.good[o.cell] + ' of ' + sm.dates +
          '<br>Sunlit hours: worst date ' + L.worst_sun[o.cell] + ', typical ' + L.median_sun[o.cell] +
          '<br>Usable hours: worst date ' + L.worst_total[o.cell] + ', typical ' + L.median_total[o.cell] +
          '<br><u>terrain (' + esc(sm.dem_label.split(';')[0]) + '), ' + sm.mast_m + ' m observer</u>';
      }
      showTip(ev, h + '<br>Click to add this point as a site');
    });
    svg.addEventListener('pointerleave', hideTip);
    box.appendChild(svg);
    var src = slipLayer ? slipLayer.label : (layer ? layer.label : (m.kind + ' (' + m.dem_label.split(';')[0] + ')'));
    var note = (m.synthetic ? 'SYNTHETIC TEST SURFACE, not the Moon. ' : '') +
      'South pole, ' + Math.round(2 * half) + ' km across, polar stereographic. Shown: ' + src + '. Click the map to add a site there.';
    if (slipLayer && sm && sm.available) {
      note += ' ' + slipLayer.legend + ' Computed for the ' + sm.dates + ' landing dates and the need on the mission card, from one terrain skyline every ' +
        sm.step_m + ' m (' + sm.dem_label.split(';')[0] + ', observer ' + sm.mast_m + ' m above ground); a crest narrower than that can be missed. ' +
        (sm.notes || []).map(function (x) { return x.charAt(0).toUpperCase() + x.slice(1) + '. '; }).join('');
      if (useRobust) {
        note += ' ' + rm.what + ' Scatter skylines are stored for ' + rm.stored.points.toLocaleString('en-US') + ' map points (those that pass on at least one landing date from 14 Nov 2026 to 16 Jan 2027 for the default need)' +
          (rm.counts.not_re_checked ? '; ' + rm.counts.not_re_checked + ' coloured points are outside that set and are drawn hollow grey' : '') + '.';
      }
    }
    if (psr) { note += ' Purple: ' + psr.note; }
    if (off) { note += ' ' + off + ' selected site' + (off > 1 ? 's are' : ' is') + ' outside this map; see the whole-Moon grid.'; }
    $('mapNote').textContent = note;
  }
  function loadMap() {
    var z = state.zoom;
    if (z !== '' && !state.maps['']) { z = ''; }       /* the whole-cap answer lists the layers; fetch it first */
    if (state.maps[z]) { renderPolar(); return; }
    var fld = state.maps[''] && state.maps[''].slip_field;
    var half = z === 'pole' ? (fld && fld.available ? fld.half_km : 30) : null;
    api('/api/map' + (half ? '?half_km=' + half : '')).then(function (m) {
      state.maps[z] = m;
      if (z === '') {
        var html = '<option value="">nothing (shaded relief)</option>';
        (m.layers || []).forEach(function (l) { html += '<option value="' + esc(l.id) + '">published average sunlight (LOLA team map)</option>'; });
        if (m.slip_field && m.slip_field.available) {
          state.mapPts = (m.slip_field.n * m.slip_field.n).toLocaleString('en-US');
          if (state.firstVisit && !state.layer) { state.layer = 'margin'; state.zoom = 'pole'; $('mapZoom').value = 'pole'; }
          Object.keys(SLIP_LAYERS).forEach(function (k) { html += '<option value="' + k + '">' + esc(SLIP_LAYERS[k].label) + '</option>'; });
        }
        $('mapLayer').innerHTML = html;
        $('mapLayer').value = state.layer;
        if ($('mapLayer').value !== state.layer) { state.layer = ''; $('mapLayer').value = ''; }
      }
      if (state.zoom === z) { renderPolar(); }
      if (z === '' && state.zoom !== '') { loadMap(); }
      if (z === '' && !state.autoPlan) { loadSlipMap(); }
    }).catch(function () { state.mapFailed = true; renderPolar(); });
  }
  function loadRobustMap(body, key) {
    var m0 = state.maps[''];
    if (state.layer !== 'margin' || !state.mapScatter || !m0 || !m0.scatter_field || !m0.scatter_field.available) { return; }
    if (state.robustMap && state.robustMap._key === key) { renderPolar(); return; }
    state.robustMsg = '';
    api('/api/robust-map', body).then(function (r) {
      r._key = key;
      if (state.slipmapKey === key) {
        state.robustMap = r; if (!r.available) { state.robustMsg = r.reason || 'not available'; } renderPolar();
        /* no stored 20 m mark for this date: work it out from the stored 20 m skylines (a few seconds) */
        if (r.available && !r.finer) {
          api('/api/finer-map', body).then(function (f) { if (f.available && state.robustMap === r) { r.finer = f; renderPolar(); } }).catch(function () {});
        }
      }
    }).catch(function (e) { state.robustMsg = e.message; renderPolar(); });
  }
  var NIGHT_STEPS = [[288, '#7f1d1d', '12 days or more'], [168, '#c2410c', '7 to 12 days'], [72, '#f59e0b', '3 to 7 days'], [24, '#fcd34d', '1 to 3 days'], [0, '#fef3c7', 'under 1 day']];
  function nightClass(v) { for (var i = 0; i < NIGHT_STEPS.length; i++) { if (v >= NIGHT_STEPS[i][0]) { return i; } } return -1; }
  function nightOverlayUrl(vals, n) {
    var K = 8, c = document.createElement('canvas'); c.width = n * K; c.height = n * K;
    var ctx = c.getContext('2d');
    for (var i = 0; i < vals.length; i++) {
      if (vals[i] < 0) { continue; }
      ctx.fillStyle = NIGHT_STEPS[nightClass(vals[i])][1]; ctx.fillRect((i % n) * K, Math.floor(i / n) * K, K, K);
    }
    return c.toDataURL('image/png');
  }
  function loadSurvMap(body, key) {
    if (!SLIP_LAYERS[state.layer] || !SLIP_LAYERS[state.layer].survival) { return; }
    if (state.survMap && state.survMap._key === key) { renderPolar(); return; }
    state.survMsg = '';
    api('/api/survival-map', body).then(function (r) {
      r._key = key;
      if (state.slipmapKey === key) { state.survMap = r; if (!r.available) { state.survMsg = r.reason || 'not available'; } renderPolar(); }
    }).catch(function (e) { state.survMsg = e.message; renderPolar(); });
  }
  function loadSlipMap() {
    var cfg = state.lastCfg || settings();
    if (!cfg || !SLIP_LAYERS[state.layer]) { return; }
    var body = withNeed({ start: cfg.start, n_dates: Math.min(90, parseInt($('slipDates').value, 10)) }, cfg);
    var key = JSON.stringify(body);
    if (state.slipmapKey === key && state.slipmap) { renderPolar(); loadRobustMap(body, key); loadSurvMap(body, key); return; }
    state.slipmapKey = key; state.slipmap = null; renderPolar();
    api('/api/slipmap', body).then(function (r) {
      if (state.slipmapKey !== key) { return; }
      state.slipmap = r; renderPolar(); loadRobustMap(body, key); loadSurvMap(body, key);
    }).catch(function (e) {
      if (e.busy && state.slipmapKey === key) { state.slipmapKey = ''; $('mapLegend').innerHTML = '<span class="small">' + esc(e.message) + '</span>'; return; }
      showError(e);
    });
  }

  /* ---------- slip-robust site list: the best map points re-checked with the landing scatter ---------- */
  function robustBody(cfg) {
    return withNeed({ start: cfg.start, n_dates: Math.min(90, parseInt($('slipDates').value, 10)), scatter_m: cfg.scatter }, cfg);
  }
  function loadRobust() {
    var cfg = state.lastCfg || settings();
    if (!cfg) { return; }
    var body = robustBody(cfg), key = JSON.stringify(body);
    /* a visible clock: the first run for a date takes about 40 s */
    var t0 = Date.now(), tick = setInterval(function () {
      $('robustMsg').textContent = 'Re-checking the 12 best map points, 15 skylines each: ' + Math.round((Date.now() - t0) / 1000) + ' s so far (about 40 s the first time for a date, then instant)…';
    }, 1000);
    $('robustMsg').textContent = 'Re-checking the 12 best map points, 15 skylines each (about 40 s the first time for a date, then instant)…';
    api('/api/robust-sites', body).then(function (r) {
      clearInterval(tick); state.robust = r; state.robustKey = key; $('robustMsg').textContent = ''; renderRobust();
    }).catch(function (e) { clearInterval(tick); $('robustMsg').textContent = 'Could not list the sites: ' + e.message; });
  }
  function renderRobust() {
    var r = state.robust, box = $('robust');
    if (!r) { box.innerHTML = ''; return; }
    if (!r.available) { box.innerHTML = '<p class="note">Not available on this installation: ' + esc(r.reason) + '.</p>'; return; }
    var stale = state.lastCfg && state.robustKey !== JSON.stringify(robustBody(state.lastCfg));
    if (!r.candidates) {
      box.innerHTML = '<h3>No map point meets this need on the planned date</h3><p class="note">Planned landing ' + esc(r.start_utc.slice(0, 16).replace('T', ' ')) +
        ' UTC: at none of the mapped points within ' + r.map_half_km + ' km of the pole does the stated point itself pass, so there is nothing to re-check. Try one of the next good dates on the card.' +
        (stale ? ' <b>The plan has changed since this list was made: press the button again.</b>' : '') + '</p>';
      return;
    }
    var h = '<h3>' + r.stay_yes + ' of the ' + r.candidates + ' best map points stay a clear yes</h3>' +
      '<p class="note">' + esc(r.what) + ' Planned landing ' + esc(r.start_utc.slice(0, 16).replace('T', ' ')) + ' UTC, ' + r.dates + ' landing dates, need ' +
      r.need.sunlit_h + ' sunlit hours and ' + r.need.earth_h + ' hours of Earth contact in ' + r.need.window_days + ' days; candidates at least ' +
      (r.min_separation_m / 1000) + ' km apart, observer ' + r.mast_m + ' m above ground. ' +
      (r.notes || []).map(function (x) { return x.charAt(0).toUpperCase() + x.slice(1) + '. '; }).join('') +
      (stale ? '<b>The plan has changed since this list was made: press the button again.</b>' : '') + '</p>';
    h += '<div class="tablewrap"><table class="data"><tr><th>Map point</th><th>With the landing scatter</th><th>Slip margin (days)</th><th>Map alone said (days)</th>' +
      '<th>Clear-yes dates</th><th>Touchdown points passing</th><th>Sunlit / Earth hours as planned</th><th></th></tr>';
    r.rows.forEach(function (x, i) {
      var v = VERDICT[x.verdict];
      h += '<tr><td>' + esc(fmtLatLon(x.lat, x.lon)) + '<small>' + esc(x.grid) + '</small></td><td class="sbest v-' + x.verdict.replace(' ', '') + '">' + v[0] + ' ' + v[1] + '</td>' +
        '<td class="num">' + (x.slip_margin_days < 0 ? 'none' : x.slip_margin_days) + '</td><td class="num">' + x.map_margin_days + '</td>' +
        '<td class="num">' + x.good_dates + ' of ' + r.dates + (x.unsure_dates ? '<small>' + x.unsure_dates + ' not sure</small>' : '') + '</td>' +
        '<td class="num">' + x.points_passing + ' of ' + x.points + '<small>within ' + Math.round(x.scatter_m) + ' m</small></td>' +
        '<td class="num">' + x.sunlit_h + ' / ' + x.earth_h + '</td><td><button type="button" class="add" data-robust="' + i + '">Add</button></td></tr>';
    });
    h += '</table></div>';
    box.innerHTML = h;
    Array.prototype.forEach.call(box.querySelectorAll('[data-robust]'), function (b) {
      b.addEventListener('click', function () {
        var x = r.rows[parseInt(b.getAttribute('data-robust'), 10)];
        addSite({ name: 'Robust pick ' + fmtLatLon(x.lat, x.lon), lat: x.lat, lon: x.lon });
      });
    });
  }

  /* ---------- comparison charts ---------- */
  /* Charts are drawn at the size they are shown, so text stays legible on a phone. */
  var NARROW = window.innerWidth < 600;
  var CW = NARROW ? 350 : 520, CH = NARROW ? 220 : 230, PAD = { l: 34, r: 12, t: 10, b: 34 };
  function yRange(list) {
    var lo = 0, hi = 0;
    list.forEach(function (d) {
      var s = d.series;
      s.sun_el.concat(s.earth_el).forEach(function (v) { if (v < lo) { lo = v; } if (v > hi) { hi = v; } });
      if (d.terrain) { s.sun_horizon.forEach(function (v) { if (v < lo) { lo = v; } if (v > hi) { hi = v; } }); }
    });
    var pad = Math.max(1, (hi - lo) * 0.08);
    return [Math.floor(lo - pad), Math.ceil(hi + pad)];
  }
  function niceStep(span) {
    var steps = [1, 2, 5, 10, 15, 30, 45];
    for (var i = 0; i < steps.length; i++) { if (span / steps[i] <= 6) { return steps[i]; } }
    return 45;
  }
  function pathFor(vals, sx, sy) {
    var d = '';
    for (var i = 0; i < vals.length; i++) { d += (i ? 'L' : 'M') + sx(i).toFixed(1) + ' ' + sy(vals[i]).toFixed(1); }
    return d;
  }
  function runs(flags) {
    var out = [], startI = -1;
    for (var i = 0; i <= flags.length; i++) {
      var f = i < flags.length && flags[i];
      if (f && startI < 0) { startI = i; }
      if (!f && startI >= 0) { out.push([startI, i]); startI = -1; }
    }
    return out;
  }
  function stripRow(svg, flags, sx, n, y, h, cls) {
    runs(flags).forEach(function (r) {
      svg.appendChild(el('rect', { x: sx(r[0]), y: y, width: Math.max(1, sx(Math.min(r[1], n - 1)) - sx(r[0])), height: h, rx: 1.5, 'class': cls }));
    });
  }
  function renderCards() {
    var box = $('cards');
    box.innerHTML = '';
    if (!state.data.length) { box.innerHTML = '<p class="note">Add a site to begin.</p>'; return; }
    var shared = yRange(state.data);
    state.data.forEach(function (d, si) {
      var s = d.series;
      var card = document.createElement('div');
      card.className = 'card';
      var h = document.createElement('h3'); h.textContent = (si + 1) + '. ' + s.site.name; card.appendChild(h);
      var c = document.createElement('p'); c.className = 'coords';
      c.innerHTML = esc(fmtLatLon(s.site.lat, s.site.lon)) + ' · ' + tagHtml(s.horizon) +
        (d.terrain ? ' <span class="small">ground ' + (s.horizon.site_height_m >= 0 ? '+' : '') + Math.round(s.horizon.site_height_m) +
          ' m, observer ' + s.horizon.mast_m + ' m above it, skyline ' + s.horizon.min_el_deg.toFixed(1) + '° to ' + s.horizon.max_el_deg.toFixed(1) + '°</span>'
          : ' <span class="small">no terrain data covers this site</span>');
      card.appendChild(c);

      var yr = $('fitEach').checked ? yRange([d]) : shared;
      var n = s.count, x0 = PAD.l, x1 = CW - PAD.r, y0 = PAD.t, y1 = CH - PAD.b - 14;
      var sx = function (i) { return x0 + (x1 - x0) * i / (n - 1); };
      var sy = function (v) { return y1 - (y1 - y0) * (v - yr[0]) / (yr[1] - yr[0]); };
      var svg = el('svg', { viewBox: '0 0 ' + CW + ' ' + CH, role: 'img',
        'aria-label': 'Sun and Earth elevation over time at ' + s.site.name });

      runs(s.lit.map(function (v) { return !v; })).forEach(function (r) {
        svg.appendChild(el('rect', { x: sx(r[0]), y: y0, width: Math.max(1, sx(Math.min(r[1], n - 1)) - sx(r[0])), height: y1 - y0, 'class': 'nightr' }));
      });
      var step = niceStep(yr[1] - yr[0]);
      for (var v = Math.ceil(yr[0] / step) * step; v <= yr[1]; v += step) {
        svg.appendChild(el('line', { x1: x0, x2: x1, y1: sy(v), y2: sy(v), 'class': v === 0 ? 'zero' : 'gridl' }));
        svg.appendChild(el('text', { x: x0 - 5, y: sy(v) + 4, 'text-anchor': 'end' }, v + '°'));
      }
      var perDay = 1440 / s.step_minutes, days = n / perDay, dstep = days > 70 ? 15 : (days > 40 ? 10 : 5);
      if (NARROW) { dstep = days > 70 ? 30 : (days > 40 ? 15 : 10); }
      for (var dd = 0; dd <= days; dd += dstep) {
        var ii = dd * perDay;
        if (ii > n - 1) { break; }
        svg.appendChild(el('line', { x1: sx(ii), x2: sx(ii), y1: y1, y2: y1 + 4, 'class': 'axis' }));
        svg.appendChild(el('text', { x: sx(ii), y: y1 + 15, 'text-anchor': dd === 0 ? 'start' : (sx(ii) > x1 - 18 ? 'end' : 'middle') }, fmtDay(s.start_unix + dd * 86400)));
      }
      if (d.terrain) { svg.appendChild(el('path', { d: pathFor(s.sun_horizon, sx, sy), 'class': 'skyl' })); }
      svg.appendChild(el('path', { d: pathFor(s.earth_el, sx, sy), 'class': 'earthl' }));
      svg.appendChild(el('path', { d: pathFor(s.sun_el, sx, sy), 'class': 'sunl' }));
      /* strips under the chart: Sun up by model, then usable */
      var ys = y1 + 21;
      stripRow(svg, s.lit, sx, n, ys, 5, 'litr');
      svg.appendChild(el('text', { x: x0 - 5, y: ys + 5, 'text-anchor': 'end', 'class': 'tiny' }, d.terrain ? 'terr.' : 'Sun'));
      if (d.smooth) {
        stripRow(svg, d.smooth.lit, sx, n, ys + 8, 5, 'litr smo');
        svg.appendChild(el('text', { x: x0 - 5, y: ys + 13, 'text-anchor': 'end', 'class': 'tiny' }, 'sph.'));
      }
      stripRow(svg, s.usable, sx, n, ys + (d.smooth ? 16 : 8), 5, 'usabler');
      svg.appendChild(el('text', { x: x0 - 5, y: ys + (d.smooth ? 21 : 13), 'text-anchor': 'end', 'class': 'tiny' }, 'use'));

      var cross = el('line', { y1: y0, y2: y1, 'class': 'cross' });
      var dSun = el('circle', { r: 4.5, 'class': 'dot-sun' });
      var dEarth = el('circle', { r: 4.5, 'class': 'dot-earth' });
      svg.appendChild(cross); svg.appendChild(dSun); svg.appendChild(dEarth);
      var hit = el('rect', { x: x0, y: y0, width: x1 - x0, height: y1 - y0, fill: 'transparent' });
      svg.appendChild(hit);
      function pick(ev) {
        var r = svg.getBoundingClientRect();
        var pxx = (ev.clientX - r.left) / r.width * CW;
        var i2 = Math.round((pxx - x0) / (x1 - x0) * (n - 1));
        setIndex(Math.max(0, Math.min(n - 1, i2)));
        showTip(ev, '<b>' + esc(s.site.name) + '</b>' + fmtUtc(scrubUnix()) + '<br>Sun ' + s.sun_el[state.idx].toFixed(1) +
          '° · Earth ' + s.earth_el[state.idx].toFixed(1) + '°' +
          (d.terrain ? '<br>Skyline under the Sun ' + s.sun_horizon[state.idx].toFixed(1) + '°, disc ' + Math.round(s.sun_frac[state.idx] * 100) + '% visible' : ''));
      }
      hit.addEventListener('pointermove', pick);
      hit.addEventListener('pointerdown', pick);
      hit.addEventListener('pointerleave', hideTip);
      card.appendChild(svg);
      var cap = document.createElement('p'); cap.className = 'cap';
      cap.textContent = d.terrain
        ? 'Strips: Sun up with terrain (terr.), Sun up on the smooth sphere (sph.), usable with terrain (use). Grey line: terrain skyline in the Sun\'s direction.'
        : 'Strips: Sun up, and usable (Sun and Earth both up). Smooth sphere only.';
      card.appendChild(cap);

      var sky = null;
      if (d.profile) {
        var hs = document.createElement('h4'); hs.innerHTML = 'Skyline all round, with the Sun and Earth paths ' + tagHtml(s.horizon); card.appendChild(hs);
        sky = drawSkyline(card, d);
      }
      var tiles = document.createElement('div'); tiles.className = 'tiles'; card.appendChild(tiles);
      var yearBox = document.createElement('div'); yearBox.className = 'year'; card.appendChild(yearBox);
      /* on a phone only the first site's card is open; the others fold to one line each */
      if (NARROW && si > 0) {
        var fold = document.createElement('details'); fold.className = 'cardFold';
        var sum = document.createElement('summary'); sum.textContent = (si + 1) + '. ' + s.site.name + ': chart, skyline, numbers and year table';
        fold.appendChild(sum); fold.appendChild(card); box.appendChild(fold);
      } else { box.appendChild(card); }
      d._dom = { cross: cross, dSun: dSun, dEarth: dEarth, sx: sx, sy: sy, tiles: tiles, sky: sky, year: yearBox };
      renderYear(si);
    });
    updateScrub();
  }

  /* 360-degree skyline strip: terrain profile, the smooth-sphere line, and the
     Sun and Earth paths over the charted span. North is in the middle. */
  var SW = NARROW ? 350 : 520, SH = 150, SP = { l: 34, r: 12, t: 8, b: 22 };
  function drawSkyline(card, d) {
    var s = d.series, p = d.profile;
    var lo = Math.min(-1, p.min_el_deg), hi = Math.max(2, p.max_el_deg);
    s.sun_el.forEach(function (v) { if (v > hi) { hi = v; } });
    s.earth_el.forEach(function (v) { if (v > hi) { hi = v; } if (v < lo && v > -12) { lo = v; } });
    hi = Math.min(Math.ceil(hi + 0.5), 30); lo = Math.max(Math.floor(lo - 0.5), -12);
    var x0 = SP.l, x1 = SW - SP.r, y0 = SP.t, y1 = SH - SP.b;
    var rel = function (az) { return ((az + 180) % 360 + 360) % 360 - 180; };   // -180..180, north = 0
    var sx = function (az) { return x0 + (rel(az) + 180) / 360 * (x1 - x0); };
    var sy = function (e) { return y1 - (Math.max(lo, Math.min(hi, e)) - lo) / (hi - lo) * (y1 - y0); };
    var svg = el('svg', { viewBox: '0 0 ' + SW + ' ' + SH, role: 'img', 'class': 'skyline',
      'aria-label': 'Terrain skyline around ' + s.site.name + ' with the Sun and Earth paths' });
    var step = niceStep(hi - lo);
    for (var v = Math.ceil(lo / step) * step; v <= hi; v += step) {
      svg.appendChild(el('line', { x1: x0, x2: x1, y1: sy(v), y2: sy(v), 'class': 'gridl' }));
      svg.appendChild(el('text', { x: x0 - 5, y: sy(v) + 4, 'text-anchor': 'end' }, v + '°'));
    }
    [['S', -180], ['W', -90], ['N', 0], ['E', 90], ['S', 180]].forEach(function (t) {
      var x = x0 + (t[1] + 180) / 360 * (x1 - x0);
      svg.appendChild(el('line', { x1: x, x2: x, y1: y1, y2: y1 + 4, 'class': 'axis' }));
      svg.appendChild(el('text', { x: x, y: y1 + 16, 'text-anchor': t[1] === -180 ? 'start' : (t[1] === 180 ? 'end' : 'middle') }, t[0]));
    });
    /* skyline polygon, ordered from south round through north */
    var pts = [];
    for (var i = 0; i < p.az_deg.length; i++) { pts.push([rel(p.az_deg[i]), p.el_deg[i]]); }
    pts.sort(function (a, b) { return a[0] - b[0]; });
    pts.push([180, pts[0][1]]);
    var dpath = 'M' + x0 + ' ' + y1;
    pts.forEach(function (q) { dpath += 'L' + (x0 + (q[0] + 180) / 360 * (x1 - x0)).toFixed(1) + ' ' + sy(q[1]).toFixed(1); });
    dpath += 'L' + x1 + ' ' + y1 + 'Z';
    svg.appendChild(el('path', { d: dpath, 'class': 'skyfill' }));
    svg.appendChild(el('line', { x1: x0, x2: x1, y1: sy(0), y2: sy(0), 'class': 'sphl' }));
    svg.appendChild(el('text', { x: x1 - 2, y: sy(0) - 3, 'text-anchor': 'end', 'class': 'tiny' }, 'smooth sphere 0°'));
    function track(az, elv, cls) {
      var dd = '', prev = null;
      for (var k = 0; k < az.length; k++) {
        var xx = sx(az[k]), yy = sy(elv[k]);
        var jump = prev !== null && Math.abs(xx - prev) > (x1 - x0) / 2;
        var hidden = elv[k] < lo - 0.01;
        dd += ((prev === null || jump || hidden) ? 'M' : 'L') + xx.toFixed(1) + ' ' + yy.toFixed(1);
        prev = hidden ? null : xx;
      }
      svg.appendChild(el('path', { d: dd, 'class': cls }));
    }
    track(s.earth_az, s.earth_el, 'earthl thin');
    track(s.sun_az, s.sun_el, 'sunl thin');
    var mSun = el('circle', { r: 5.5, 'class': 'dot-sun' }), mEarth = el('circle', { r: 5.5, 'class': 'dot-earth' });
    svg.appendChild(mEarth); svg.appendChild(mSun);
    var hit = el('rect', { x: x0, y: y0, width: x1 - x0, height: y1 - y0, fill: 'transparent' });
    hit.addEventListener('pointermove', function (ev) {
      var r = svg.getBoundingClientRect();
      var az = ((ev.clientX - r.left) / r.width * SW - x0) / (x1 - x0) * 360 - 180;
      az = (az + 360) % 360;
      var k = Math.round(az / 360 * p.az_deg.length) % p.az_deg.length;
      showTip(ev, '<b>Skyline at azimuth ' + az.toFixed(0) + '°</b>' + p.el_deg[k].toFixed(2) + '° elevation' +
        (p.dist_km[k] !== null ? '<br>set by terrain ' + p.dist_km[k].toFixed(1) + ' km away' : '') + '<br>' + esc(modelTag(s.horizon)));
    });
    hit.addEventListener('pointerleave', hideTip);
    svg.appendChild(hit);
    card.appendChild(svg);
    return { mSun: mSun, mEarth: mEarth, sx: sx, sy: sy, lo: lo };
  }

  function nextEvent(events, type, t) {
    for (var i = 0; i < events.length; i++) {
      if (events[i].type === type && events[i].unix > t) { return events[i]; }
    }
    return null;
  }
  function tile(k, v, sub, tag) {
    return '<div class="tile"><div class="k">' + esc(k) + '</div><div class="v">' + esc(v) + '</div><div class="s">' + (sub || '') + '</div>' +
      (tag ? '<div class="t">' + tag + '</div>' : '') + '</div>';
  }
  /* "Time to sunset" for one model, from that model's event list. The list is
     searched 200 days past the chart, the same as the window figures. */
  function eventText(events, up, riseType, setType, t, untilUtc) {
    var ev = nextEvent(events, up ? setType : riseType, t);
    if (ev) { return { v: fmtHours((ev.unix - t) / 3600), s: fmtUtc(ev.unix) }; }
    var word = (up ? setType : riseType).replace('earth', 'Earth');
    return { v: '—', s: 'no ' + word + ' before ' + String(untilUtc).slice(0, 10) };
  }
  function updateScrub() {
    var t = scrubUnix();
    $('scrubLabel').textContent = fmtUtc(t);
    state.data.forEach(function (d) {
      var s = d.series, dom = d._dom; if (!dom) { return; }
      var i = Math.min(state.idx, s.count - 1);
      var x = dom.sx(i);
      dom.cross.setAttribute('x1', x); dom.cross.setAttribute('x2', x);
      dom.dSun.setAttribute('cx', x); dom.dSun.setAttribute('cy', dom.sy(s.sun_el[i]));
      dom.dEarth.setAttribute('cx', x); dom.dEarth.setAttribute('cy', dom.sy(s.earth_el[i]));
      if (dom.sky) {
        dom.sky.mSun.setAttribute('cx', dom.sky.sx(s.sun_az[i])); dom.sky.mSun.setAttribute('cy', dom.sky.sy(s.sun_el[i]));
        dom.sky.mSun.setAttribute('visibility', s.sun_el[i] < dom.sky.lo ? 'hidden' : 'visible');
        dom.sky.mEarth.setAttribute('cx', dom.sky.sx(s.earth_az[i])); dom.sky.mEarth.setAttribute('cy', dom.sky.sy(s.earth_el[i]));
        dom.sky.mEarth.setAttribute('visibility', s.earth_el[i] < dom.sky.lo ? 'hidden' : 'visible');
      }
      var tag = tagHtml(s.horizon), sm = d.smooth, geo = '<span class="mtag geo">geometry (JPL DE421)</span>';
      var sunUp = !!s.lit[i], earthUp = !!s.earth_vis[i];
      var html = '';
      html += tile('Sun elevation', s.sun_el[i].toFixed(1) + '°',
        'azimuth ' + s.sun_az[i].toFixed(0) + '°' + (d.terrain ? '; skyline there ' + s.sun_horizon[i].toFixed(1) + '°, ' + Math.round(s.sun_frac[i] * 100) + '% of disc visible' : (sunUp ? ', above horizon' : ', below horizon')), geo);
      html += tile('Earth elevation', s.earth_el[i].toFixed(1) + '°',
        'azimuth ' + s.earth_az[i].toFixed(0) + '°' + (d.terrain ? '; skyline there ' + s.earth_horizon[i].toFixed(1) + '°' : (earthUp ? ', in view' : ', out of view')), geo);
      var se = eventText(s.events, sunUp, 'sunrise', 'sunset', t, s.events_searched_until_utc);
      var sub = se.s;
      if (sm) {
        var smUp = !!sm.lit[i], se2 = eventText(sm.events, smUp, 'sunrise', 'sunset', t, s.events_searched_until_utc);
        sub += '<br>smooth sphere: ' + (smUp ? 'sunset' : 'sunrise') + ' in ' + se2.v;
      }
      html += tile(sunUp ? 'Time to sunset' : 'Time to sunrise', se.v, sub, tag);
      var ee = eventText(s.events, earthUp, 'earthrise', 'earthset', t, s.events_searched_until_utc);
      sub = (ee.v === '—' ? (earthUp ? 'Earth stays up; ' : 'Earth stays down; ') : '') + ee.s;
      if (sm) {
        var smE = !!sm.earth_vis[i], ee2 = eventText(sm.events, smE, 'earthrise', 'earthset', t, s.events_searched_until_utc);
        sub += '<br>smooth sphere: ' + (ee2.v === '—' ? (smE ? 'stays up' : 'stays down') : (smE ? 'Earthset' : 'Earthrise') + ' in ' + ee2.v);
      }
      html += tile(earthUp ? 'Time to Earthset' : 'Time to Earthrise', ee.v, sub, tag);
      var m = d.metrics, w = m && m.window, w2 = sm && sm.metrics && sm.metrics.window;
      if (w) {
        var span = 'next ' + w.days.toFixed(1) + ' d';
        html += tile('Sunlit, ' + span, w.sunlit_hours.toFixed(0) + ' h', Math.round(w.sunlit_share * 100) + '% of the time' +
          (w2 ? '<br>smooth sphere: ' + w2.sunlit_hours.toFixed(0) + ' h' : ''), tag);
        html += tile('Earth in view, ' + span, Math.round(w.earth_visible_share * 100) + '%', 'longest outage ' + fmtHours(w.longest_earth_outage_hours) +
          (w2 ? '<br>smooth sphere: ' + Math.round(w2.earth_visible_share * 100) + '%' : ''), tag);
        html += tile('Usable hours, ' + span, w.usable_hours.toFixed(0) + ' h', 'Sun and Earth both up' +
          (w2 ? '<br>smooth sphere: ' + w2.usable_hours.toFixed(0) + ' h' : ''), tag);
        html += tile('Longest darkness, ' + span, fmtHours(w.longest_dark_hours), 'peak Sun ' + w.max_sun_el.toFixed(1) + '°' +
          (w2 ? '<br>smooth sphere: ' + fmtHours(w2.longest_dark_hours) : ''), tag);
      }
      dom.tiles.innerHTML = html;
    });
  }
  function setIndex(i) {
    state.idx = i;
    $('scrub').value = i;
    updateScrub();
    scheduleMetrics();
  }
  /* Window figures follow the scrubber. Throttled, not debounced, so they keep
     refreshing while Play is running. */
  function scheduleMetrics() {
    if (state.metricsBusy) { state.metricsWanted = true; return; }
    if (state.metricsTimer) { return; }
    state.metricsTimer = setTimeout(function () { state.metricsTimer = null; loadMetrics(); }, state.playing ? 350 : 150);
  }
  function loadMetrics() {
    var cfg = state.lastCfg;
    if (!cfg || !state.data.length) { return; }
    var at = new Date(scrubUnix() * 1000).toISOString(), req = state.reqId;
    state.metricsBusy = true; state.metricsWanted = false;
    var jobs = state.selected.map(function (s) {
      var q = 'at=' + encodeURIComponent(at) + '&' + optQuery(cfg) +
        (s.id ? '&site=' + encodeURIComponent(s.id) : '&lat=' + s.lat + '&lon=' + s.lon + '&name=' + encodeURIComponent(s.name));
      return api('/api/metrics?' + q);
    });
    Promise.all(jobs).then(function (res) {
      if (req === state.reqId) {
        res.forEach(function (m, k) {
          var d = state.data[k]; if (!d) { return; }
          if (d.smooth && m.smooth) { d.smooth.metrics = m.smooth; }
          d.metrics = m;
        });
        updateScrub();
      }
    }).catch(showError).then(function () {
      state.metricsBusy = false;
      if (state.metricsWanted) { scheduleMetrics(); }
    });
  }

  /* ---------- a year at each site: terrain and smooth sphere side by side ---------- */
  function yearKey(s, cfg) { return (s.id || (s.lat + ',' + s.lon)) + '|' + cfg.start + '|' + cfg.scatter + '|' + JSON.stringify(cfg.opts); }
  function loadYear() {
    var cfg = state.lastCfg; if (!cfg) { return; }
    state.selected.forEach(function (s, k) {
      var key = yearKey(s, cfg);
      if (state.year[key]) { renderYear(k); return; }
      var q = 'start=' + encodeURIComponent(cfg.start) + '&days=365&ladder=true&scatter_m=' + cfg.scatter + '&' + optQuery(cfg) +
        (s.id ? '&site=' + encodeURIComponent(s.id) : '&lat=' + s.lat + '&lon=' + s.lon);
      api('/api/stats?' + q).then(function (r) { state.year[key] = r; renderYear(state.selected.indexOf(s)); }).catch(function () {});
    });
  }
  function rangeTxt(r, f) { return r[0] === r[1] ? '' : ' <span class="rng">' + f(r[0]) + ' to ' + f(r[1]) + '</span>'; }
  function renderYear(k) {
    var d = state.data[k], s = state.selected[k], cfg = state.lastCfg;
    if (!d || !d._dom || !s || !cfg) { return; }
    var y = state.year[yearKey(s, cfg)], box = d._dom.year;
    if (!y) { box.innerHTML = '<p class="cap">Working out the next 365 days…</p>'; return; }
    var t = y.terrain, m = y.smooth, b = y.band;
    var cols = y.ladder ? y.ladder.map(function (c, i) { return [c.label.replace('LOLA, ', '').replace('/px', '').replace('smooth sphere', 'sphere'), c, c.model === 'terrain' ? (i === 0 ? 'ter' : 'geo') : 'smo']; })
      : (t ? [[modelTag(t.horizon), t, 'ter'], ['smooth sphere', m, 'smo']] : [[modelTag(m.horizon), m, 'smo']]);
    var pc = function (v) { return v.toFixed(1) + '%'; };
    var rows = [
      ['Sunlit (' + y.criteria.sun_rule.replace(' above the horizon', '').replace('of the solar disc', 'of the disc') + ')', 'lit_pct', pc],
      ['Any part of the Sun visible', 'any_light_pct', pc],
      ['Longest darkness (no Sun at all)', 'longest_dark_h', fmtHours],
      ['Longest continuous light', 'longest_light_h', fmtHours],
      ['Earth in view', 'earth_visible_pct', pc],
      ['Longest Earth outage', 'longest_earth_outage_h', fmtHours]
    ];
    var html = '<h4>The 365 days from ' + esc(y.start_utc.slice(0, 10)) + (t ? ', observer ' + t.horizon.mast_m + ' m above ground: the same site on each elevation grid' : '') + '</h4>' +
      '<div class="tablewrap"><table class="data yeart"><tr><th></th>' + cols.map(function (c) {
        return '<th><span class="mtag ' + c[2] + '">' + esc(c[0]) + '</span></th>';
      }).join('') + '</tr>';
    rows.forEach(function (r) {
      html += '<tr><td>' + esc(r[0]) + '</td>' + cols.map(function (c, i) {
        return '<td class="num">' + esc(r[2](c[1][r[1]])) + (i === 0 && b && b[r[1]] ? rangeTxt(b[r[1]], r[2]) : '') + '</td>';
      }).join('') + '</tr>';
    });
    html += '</table></div>';
    var cap = 'Hourly samples. One year is a sample of the 18.6-year cycle, not a long-term average.';
    if (b) {
      cap = 'Small print under a figure: its range over ' + b.points + ' points within ' + b.scatter_m + ' m of the target. ' + cap;
      var dk = b.longest_dark_h;
      if (dk[1] - dk[0] >= 24) {
        cap += ' Longest darkness is the least reliable figure here: it runs from ' + fmtHours(dk[0]) + ' to ' + fmtHours(dk[1]) +
          ' within ' + b.scatter_m + ' m, because ground a few hundred metres away that this grid cannot resolve decides it.';
      }
    }
    if (t && t.horizon.validated === false) { cap += ' This site is outside the area where the terrain model was checked against the LOLA team\'s maps (80°S to the pole, grids of 474 m or finer).'; }
    box.innerHTML = html + '<p class="cap">' + cap + '</p>';
  }

  /* ---------- two sites as one power system ---------- */
  function loadPairs() {
    var cfg = state.lastCfg, box = $('pairs');
    if (!cfg || state.selected.length < 2) { box.innerHTML = ''; return; }
    var req = state.reqId;
    api('/api/pairs', withOpts({ sites: state.selected.map(siteRef), start: cfg.start, days: 365 }, cfg)).then(function (r) {
      if (req !== state.reqId) { return; }
      var h = '<h3>Two sites as one power system: the 365 days from ' + esc(cfg.start.slice(0, 10)) + '</h3>' +
        '<div class="tablewrap"><table class="data"><tr><th>Pair</th><th>Apart</th><th>At least one has Sun</th><th>Each alone</th><th>Longest time both are dark</th><th>Each alone</th></tr>';
      r.pairs.forEach(function (p) {
        var a = r.sites[p.a], b = r.sites[p.b];
        h += '<tr><td>' + (p.a + 1) + ' + ' + (p.b + 1) + ' <small>' + esc(a.name) + ' and ' + esc(b.name) + '</small></td><td class="num">' + p.distance_km.toFixed(1) + ' km</td><td class="num"><b>' +
          p.either_lit_pct.toFixed(1) + '%</b></td><td class="num">' + a.any_light_pct.toFixed(1) + '% · ' + b.any_light_pct.toFixed(1) + '%</td><td class="num"><b>' +
          fmtHours(p.longest_joint_dark_h) + '</b></td><td class="num">' + fmtHours(a.longest_dark_h) + ' · ' + fmtHours(b.longest_dark_h) + '</td></tr>';
      });
      box.innerHTML = h + '</table></div><p class="cap">Sun counts when any part of the disc is above the skyline. ' + esc(r.caveat) + '</p>';
    }).catch(function () { box.innerHTML = ''; });
  }

  /* ---------- slip grid ---------- */
  function mix(a, b, t) {
    var pa = [1, 3, 5].map(function (k) { return parseInt(a.substr(k, 2), 16); });
    var pb = [1, 3, 5].map(function (k) { return parseInt(b.substr(k, 2), 16); });
    return 'rgb(' + pa.map(function (v, k) { return Math.round(v + (pb[k] - v) * t); }).join(',') + ')';
  }
  function cssVar(name) { return getComputedStyle(document.documentElement).getPropertyValue(name).trim(); }
  var VERDICT = { yes: ['✓', 'Yes'], 'not sure': ['?', 'Not sure'], no: ['✕', 'No'], 'n/a': ['–', 'Not computed'] };
  function shortVerdict(m) {
    if (!m) { return '…'; }
    var v = VERDICT[m.verdict];
    if (m.verdict === 'yes') { return v[0] + ' Yes · ' + (m.slip_margin_days === 0 ? 'no slip margin' : 'slip up to ' + m.slip_margin_days + ' d'); }
    return v[0] + ' ' + v[1] + (m.next_good_dates.length ? ' · next ' + fmtDate(m.next_good_dates[0]) : ' · no clear yes');
  }
  function cellVals(row, metric, stat) {
    if (stat === 'min' && row.band) { return row.band[metric].min; }
    return row[metric];
  }
  function renderSlip() {
    var g = state.slip, box = $('slip');
    box.innerHTML = '';
    if (!g) { $('slipNote').textContent = state.selected.length ? '' : 'Add a site to see the grid.'; return; }
    var metric = $('slipMetric').value, stat = $('slipStat').value, lo = cssVar('--seq-lo'), hi = cssVar('--seq-hi'), zero = cssVar('--zero-cell');
    var slo = cssVar('--spread-lo'), shi = cssVar('--spread-hi');
    var n = g.dates.length, every = n > 60 ? 10 : 5;
    var colour = function (v) { return v === null ? 'transparent' : (v <= 0 ? zero : mix(lo, hi, Math.min(1, v / g.window_hours))); };
    var spreadColour = function (v) { return v === null ? 'transparent' : (v <= 0 ? zero : mix(slo, shi, Math.min(1, v / 96))); };
    var names = { total: 'Usable', sunlit: 'Sunlit', earth: 'Earth contact', continuous: 'Unbroken from touchdown' };
    var head = document.createElement('div'); head.className = 'srow shead';
    var axis = '<div class="slabel"></div><div class="strip axis">';
    g.dates.forEach(function (d, i) {
      axis += '<span class="tick">' + (i % every === 0 ? '<i>' + (i === 0 ? 'plan ' : '+' + i + ' d ') + esc(fmtDay(Date.parse(d) / 1000)) + '</i>' : '') + '</span>';
    });
    head.innerHTML = axis + '</div><div class="sbest">meets the need?</div>';
    box.appendChild(head);
    var anyTerrain = false, anySyn = false, anyBand = false, pts = 13, sc = 100;
    g.rows.forEach(function (row, ri) {
      var isT = row.horizon.kind === 'profile', bd = row.band;
      anyTerrain = anyTerrain || isT; anySyn = anySyn || row.horizon.synthetic;
      if (bd) { anyBand = true; pts = bd.points; sc = bd.scatter_m; }
      var vals = cellVals(row, metric, stat);
      var wrap = document.createElement('div'); wrap.className = 'srow' + (ri === state.mi ? ' cur' : '');
      var lab = document.createElement('button'); lab.type = 'button'; lab.className = 'slabel pick';
      lab.title = 'Show this site on the mission card';
      lab.innerHTML = '<b>' + (ri + 1) + '</b> ' + esc(row.site.name) + ' ' + tagHtml(row.horizon);
      lab.addEventListener('click', function () { state.mi = ri; $('mSite').value = String(ri); renderMission(); renderSlip(); renderPolar(); saveHash(); });
      var strip = document.createElement('div'); strip.className = 'strip';
      var mis = state.missions[ri];
      vals.forEach(function (v, i) {
        var b = document.createElement('button');
        b.type = 'button'; b.className = 'cell' + (v === null ? ' na' : '');
        b.style.background = colour(v);
        var day = fmtDay(Date.parse(g.dates[i]) / 1000);
        b.setAttribute('aria-label', row.site.name + ', land ' + day + ': ' + (v === null ? 'not computed' : v + ' of ' + g.window_hours + ' h') + ', ' + modelTag(row.horizon));
        b.addEventListener('pointermove', function (ev) { showTip(ev, slipTip(g, row, i, mis)); });
        b.addEventListener('pointerleave', hideTip);
        b.addEventListener('focus', function () { var r = b.getBoundingClientRect(); showTip({ clientX: r.right, clientY: r.bottom }, slipTip(g, row, i, mis)); });
        b.addEventListener('blur', hideTip);
        b.addEventListener('click', function () { jumpTo(Date.parse(g.dates[i]) / 1000); });
        strip.appendChild(b);
      });
      var best = document.createElement('div'); best.className = 'sbest num v-' + (mis ? mis.verdict.replace(' ', '') : 'wait');
      best.textContent = shortVerdict(mis);
      wrap.appendChild(lab); wrap.appendChild(strip); wrap.appendChild(best);
      function thin(label, cells, bestTxt, cls) {
        var l2 = document.createElement('div'); l2.className = 'slabel sub'; l2.innerHTML = label;
        var s2 = document.createElement('div'); s2.className = 'strip thin ' + (cls || ''); s2.setAttribute('aria-hidden', 'true');
        cells.forEach(function (bg) { var c = document.createElement('span'); c.className = 'cell'; c.style.background = bg; s2.appendChild(c); });
        var b2 = document.createElement('div'); b2.className = 'sbest sub num'; b2.textContent = bestTxt;
        wrap.appendChild(l2); wrap.appendChild(s2); wrap.appendChild(b2);
      }
      if (bd) {
        var spread = bd[metric].max.map(function (mx, i) { return mx === null ? null : mx - bd[metric].min[i]; });
        var worst = 0; spread.forEach(function (v) { if (v > worst) { worst = v; } });
        thin('how much it moves within ' + Math.round(bd.scatter_m) + ' m', spread.map(spreadColour), 'up to ' + worst + ' h', 'spread');
      }
      if (row.smooth) {
        var sv = row.smooth[metric], bi = -1;
        sv.forEach(function (v, i) { if (v !== null && (bi < 0 || v > sv[bi])) { bi = i; } });
        thin('<span class="mtag smo">smooth sphere</span> same site', sv.map(colour), bi < 0 || sv[bi] <= 0 ? 'none' : 'best ' + fmtDay(Date.parse(g.dates[bi]) / 1000), '');
      }
      box.appendChild(wrap);
    });
    /* the scatter the rows were worked out for: 100 m unless a grid cell is larger (then it differs by row) */
    var radii = {};
    g.rows.forEach(function (row) { if (row.band && row.band.points > 1) { radii[Math.round(row.band.scatter_m)] = 1; } });
    var rl = Object.keys(radii);
    var scTxt = rl.length === 1 ? rl[0] + ' m of the target' : 'the landing scatter (at least one grid cell: ' + rl.join(', ') + ' m)';
    $('slipStat').options[0].textContent = 'the worst case within ' + scTxt;
    var lg = document.createElement('div');
    lg.className = 'slipLegend';
    lg.innerHTML = '<span class="z"></span><span>0 h</span><span class="ramp"></span><span>' + g.window_hours + ' h (whole window)</span>' +
      (anyBand ? '<span class="gap"></span><span class="z"></span><span>same everywhere</span><span class="ramp spread"></span><span>moves by 4 days or more</span>' : '');
    box.appendChild(lg);
    $('slipNote').textContent = 'Each cell is one landing date: the planned one on the left, then one more day of slip per cell. Darker blue means more hours in the ' +
      g.window_days + ' days after landing (' + g.criteria.sun_rule + '; ' + g.criteria.earth_rule + '). ' +
      (anyTerrain ? 'Tall cells use the terrain skyline' + (anySyn ? ' (SYNTHETIC TEST DEM, not lunar data)' : ' ray-cast from LOLA elevation data') +
        (anyBand && stat === 'min' ? ' and show the worst of ' + pts + ' points within ' + scTxt : ' at the stated point') +
        (anyBand ? '; the grey strip shows how far the answer moves within that scatter' : '') +
        '; the thin blue strip is the same site on a smooth sphere with no terrain, for comparison. ' : 'Smooth-sphere horizon: no terrain data covers these sites. ') +
      'Click a cell to move the charts to that date, or a site name to put it on the mission card.' + (g.truncated_at_ephemeris_end ? ' Blank cells run past the end of the ephemeris (2050).' : '');
    roveRows(box, '.srow', 'button.cell');
  }
  /* keyboard: one Tab stop per row; the arrow keys, Home and End move along it */
  function roveRows(box, rowSel, cellSel) {
    Array.prototype.forEach.call(box.querySelectorAll(rowSel), function (row) {
      var cells = Array.prototype.slice.call(row.querySelectorAll(cellSel));
      if (!cells.length) { return; }
      cells.forEach(function (c, k) { c.tabIndex = k ? -1 : 0; });
      row.addEventListener('keydown', function (ev) {
        var i = cells.indexOf(document.activeElement);
        if (i < 0) { return; }
        var j = ev.key === 'ArrowRight' ? i + 1 : ev.key === 'ArrowLeft' ? i - 1 : ev.key === 'Home' ? 0 : ev.key === 'End' ? cells.length - 1 : null;
        if (j === null) { return; }
        ev.preventDefault();
        j = Math.max(0, Math.min(cells.length - 1, j));
        cells[i].tabIndex = -1; cells[j].tabIndex = 0; cells[j].focus();
      });
    });
  }
  function slipTip(g, row, i, mis) {
    var v = row.total[i];
    if (v === null) { return '<b>' + esc(row.site.name) + '</b>Land ' + esc(fmtDate(g.dates[i])) + '<br>Past the end of the ephemeris (2050); not computed.'; }
    var bd = row.band, h = '<b>' + esc(row.site.name) + '</b>Land ' + esc(g.dates[i].slice(0, 16).replace('T', ' ')) + ' UTC' + (i ? ' (slip ' + plural(i, 'day') + ')' : ' (as planned)');
    var line = function (label, key) {
      return '<br>' + label + ': ' + row[key][i] + ' h' + (bd && bd[key].min[i] !== bd[key].max[i] ? ' <span class="rng">(' + bd[key].min[i] + ' to ' + bd[key].max[i] + ' within ' + Math.round(bd.scatter_m) + ' m)</span>' : '');
    };
    h += '<br><u>' + esc(modelTag(row.horizon)) + '</u>' + line('Sunlit', 'sunlit') + line('Earth contact', 'earth') + line('Both (usable)', 'total');
    if (bd && bd.total.coarse) { h += '<br><u>terrain (' + esc(String(bd.coarse_horizon.dem_label).split(';')[0]) + ')</u><br>Sunlit ' + bd.sunlit.coarse[i] + ' h · Earth ' + bd.earth.coarse[i] + ' h · both ' + bd.total.coarse[i] + ' h'; }
    if (row.smooth) { h += '<br><u>smooth sphere</u><br>Sunlit ' + row.smooth.sunlit[i] + ' h · Earth ' + row.smooth.earth[i] + ' h · both ' + row.smooth.total[i] + ' h'; }
    h += '<br>At touchdown: Sun ' + row.sun_el_at_landing[i] + '° (' + (row.sun_up_at_landing[i] ? 'up' : 'behind the skyline') + '), Earth ' + row.earth_el_at_landing[i] + '° (' + (row.earth_up_at_landing[i] ? 'in view' : 'behind the skyline') + ')';
    if (mis && mis.days[i]) {
      var d = mis.days[i];
      h += '<br><b>Meets the need: ' + VERDICT[d.verdict][1] + '</b>' + esc((d.reasons.length ? d.reasons : (d.unsure_because || [])).join('; '));
    }
    return h;
  }

  /* ---------- mission card ---------- */
  function missionBody(cfg, s) {
    return withNeed({ site: siteRef(s), landing: cfg.start, scatter_m: cfg.scatter, slip_days: parseInt($('slipDates').value, 10) }, cfg);
  }
  function loadMissions() {
    var cfg = state.lastCfg; if (!cfg) { return; }
    var req = state.reqId;
    state.missions = [];
    renderMission();
    state.selected.forEach(function (s, k) {
      api('/api/mission', missionBody(cfg, s)).then(function (m) {
        if (req !== state.reqId) { return; }
        state.missions[k] = m;
        /* First visit with no link: if the default plan (today) does not work, start from the next good date, so the
           first thing on screen is a plan with a slip margin. Done once, and the page says so. */
        if (k === state.mi && state.autoPlan && m.verdict !== 'yes' && m.next_good_dates.length) {
          state.autoPlan = false; state.autoNote = 'The opening example (' + fmtDate(m.landing_utc) + ') is not a clear yes on this installation, so the plan starts at the next good date.';
          setPlan(m.next_good_dates[0]); return;
        }
        /* No clear yes anywhere in the span (the 240 m grid at a narrow ridge): rather than open on a "No" for
           today's date, start at the first date that is not a clear no, and say why. */
        if (k === state.mi && state.autoPlan && m.verdict === 'no') {
          var firstOpen = -1;
          m.days.forEach(function (d, i) { if (firstOpen < 0 && d.verdict === 'not sure') { firstOpen = i; } });
          if (firstOpen > 0) {
            state.autoPlan = false;
            state.autoNote = 'The opening example (' + fmtDate(m.landing_utc) + ') is not a good landing date on this installation, and no date in the next ' + m.days.length +
              ' days is a clear yes on this elevation grid, so the plan starts at the first date that is not a clear no.';
            setPlan(m.days[firstOpen].landing_utc); return;
          }
        }
        if (k === state.mi) {
          state.busyTries = 0;
          if (state.autoPlan) {
            state.autoPlan = false; loadSlipMap();
            if (state.firstVisit && m.finer_grid_check && m.finer_grid_check.agrees) {
              state.autoNote = 'The page opens on a worked example that NASA’s 80 m and 20 m grids both support (landing ' + fmtDate(m.landing_utc) +
                ' 2026). It is a fixed example, so the page keeps opening on it after that date has passed. Site 2, the Shackleton connecting ridge, shows a case where the two grids disagree.';
            }
          }
          renderMission();
        }
        renderSlip();
      }).catch(function (e) {
        if (k !== state.mi || req !== state.reqId) { return; }
        $('missionOut').innerHTML = '<p class="note">' + esc(e.message) + '</p>';
        /* the server is working out skylines for other visitors: say so, and ask again by itself a few times */
        if (e.busy && state.busyTries < 6) {
          state.busyTries += 1;
          setTimeout(function () { if (req === state.reqId) { loadMissions(); loadSlip(); } }, e.retryAfter * 1000);
        }
      });
    });
  }
  function setPlan(iso) {
    $('start').value = iso.slice(0, 10);
    $('mHour').value = String(parseInt(iso.slice(11, 13), 10));
    refreshAll();
  }
  function renderMission() {
    var box = $('missionOut'), m = state.missions[state.mi];
    var opts = '';
    state.selected.forEach(function (s, i) { opts += '<option value="' + i + '">' + esc(s.name) + '</option>'; });
    var more = (state.catalog || []).filter(function (c) { return !state.selected.some(function (x) { return x.lat === c.lat && x.lon === c.lon; }); });
    if (more.length) { opts += '<optgroup label="More sites (adds it)">' + more.map(function (c) { return '<option value="cat:' + esc(c.id) + '">' + esc(c.name) + '</option>'; }).join('') + '</optgroup>'; }
    opts += '<option value="custom">Your own coordinates…</option>';
    $('mSite').innerHTML = opts; $('mSite').value = String(state.mi);
    renderCircles();
    if (!state.selected.length) { box.innerHTML = '<p class="note">Add a site below to begin.</p>'; return; }
    if (!m) { box.innerHTML = '<p class="note">Working it out for 13 points around the target…</p>'; return; }
    var v = VERDICT[m.verdict], cls = m.verdict.replace(' ', '').replace('/', '');
    var sub;
    if (m.verdict === 'yes') {
      sub = m.slip_margin_days >= m.days.length - 1 ? 'holds for all ' + m.days.length + ' dates checked' :
        (m.slip_margin_days === 0 ? 'on the planned date, with <b>no slip margin</b>' : 'it survives a slip of up to <b>' + plural(m.slip_margin_days, 'day') + '</b>');
      /* the Yes is conditional on the landing scatter: say so in the headline, not in a footnote */
      if (m.sure && m.sure.points > 1) { sub += ' <span class="vCond">if it touches down within ' + Math.round(m.sure.scatter_m) + ' m of the target</span>'; }
    } else if (m.next_good_dates.length) {
      var dd = Math.round((Date.parse(m.next_good_dates[0]) - Date.parse(m.landing_utc)) / 86400000);
      sub = 'next good landing date: <b>' + esc(fmtDate(m.next_good_dates[0])) + '</b> (' + plural(dd, 'day') + ' later)';
    } else { sub = 'no clear-yes landing date in the ' + m.days.length + ' days checked'; }
    var h = '<div class="verdict v-' + cls + '"><span class="vIcon" aria-hidden="true">' + v[0] + '</span><span class="vWord">' + v[1] + '</span><span class="vSub">' + sub + '</span></div>';
    /* this very example was also worked out on a finer grid: say what that grid answers, right under the verdict */
    if (m.finer_grid_check) {
      h += '<p class="fineNote' + (m.finer_grid_check.agrees ? ' agree' : '') + '" id="fineNote" title="' + esc(m.finer_grid_check.text) + '">' + esc(m.finer_grid_check.short) + '</p>';
    }
    h += '<p class="objLine" id="objLine"></p>';
    h += '<div class="vAxis"><span>planned date</span><span>each cell: one more day of slip; click one to see why</span><span>+' + (m.days.length - 1) + ' days</span></div><div class="vstrip" id="vstrip"></div>';
    h += '<div class="vstrip thin" id="vstrip2" aria-hidden="true"></div>';
    h += '<p class="dayBanner" id="dayBanner" role="status" hidden></p>';
    /* where terrain changes the answer: count the dates on which a smooth-sphere tool would say something else */
    var wrongYes = 0, wrongNo = 0;
    m.days.forEach(function (d) {
      if (d.verdict === 'n/a') { return; }
      if (d.smooth_sphere_passes && d.verdict !== 'yes') { wrongYes += 1; }
      if (!d.smooth_sphere_passes && d.verdict === 'yes') { wrongNo += 1; }
    });
    var diffTitle = 'A smooth-sphere tool says yes on ' + wrongYes + ' dates where the terrain answer is no or not sure, and no on ' + wrongNo +
      ' dates where the terrain answer is yes. It has no way to say not sure; the terrain answer is not sure on ' + m.unsure_dates + ' dates.';
    h += '<div class="vLegend"><span><i class="k yes"></i>✓ yes</span><span><i class="k notsure"></i>? not sure: changes within the landing scatter or with the grid</span><span><i class="k no"></i>✕ no</span>' +
      '</div>';
    var smoothHtml = '<p class="cap" id="smoothDiff" title="' + esc(diffTitle) + '"><i class="k smo"></i>Thin strip: the answer if the Moon were a smooth ball, with no hills (a “smooth sphere”). ' + (m.sure && m.sure.terrain ?
        'Real hills change it on <b>' + (wrongYes + wrongNo) + ' of ' + m.days.length + '</b> dates (outlined), and the terrain answer is not sure on ' + m.unsure_dates + ' more.' :
        'No terrain data covers this site, so the two are the same.') + '</p>';
    h += '<div class="why" id="why"></div>';
    h += '<div class="nextGood">' + (m.next_good_dates.length ? '<span>' + (m.verdict === 'yes' ? 'Next days:' : 'Next good dates:') + '</span>' +
        m.next_good_dates.map(function (d) { return '<button type="button" data-plan="' + esc(d) + '">' + esc(fmtDate(d)) + '</button>'; }).join('') : '') +
      '<span class="winLine" id="winLine"></span></div><div class="winAlt" id="winAlt"></div>';
    h += '<div class="cardActions"><button type="button" id="dlAnswer">Download this answer (CSV)</button><button type="button" id="dlAnswerJson">JSON</button><span id="cardLinks"></span></div>';
    h += '<p class="planLine">These monthly windows belong to the planned date. Typing a new date makes it the plan, with its own windows; “Launch slipped by” keeps these.</p>';
    h += '<details class="explain mWords"><summary>More about this answer: the Earth margin, the smooth-ball strip, how sure, the answer in words, and this place in other tools</summary>' +
      '<div class="earthLine" id="earthLine"></div>' + smoothHtml + '<p class="sure">' + esc(m.sure.text) + ' ' + tagHtml(m.horizon) + '</p><p class="mText">' + esc(m.sentences.join(' ')) + '</p>' +
      '<p class="cap" id="siteLinks"></p></details>';
    /* a real landing with its own need on the card: say where the need comes from (also when opened from a link) */
    var sel = state.selected[state.mi], rp = state.replays.filter(function (x) {
      return sel && x.site === sel.id && x.landing === m.landing_utc && x.need_sun_h === m.need.sunlit_h && x.need_earth_h === m.need.earth_h && x.window_days === m.window_days;
    })[0];
    if (rp) {
      h += '<p class="cap replayCap"><b>' + esc(rp.label) + ', landed ' + esc(rp.landed_utc.slice(0, 16).replace('T', ' ')) + ' UTC</b> (' +
        (rp.need_kind === 'published plan' ? 'sunlit hours from the published plan' : 'illustrative need') + '). ' + esc(rp.need_note) + '</p>';
    }
    if ($('autoNote')) { $('autoNote').textContent = state.autoNote || ''; }
    box.innerHTML = h;
    renderEarthLine(); loadEarthMask(); loadSurvival(); renderWindows(); renderOptions(); loadWindows();
    if (state.whyDay >= m.days.length || m.days[state.whyDay].sunlit_h === null) { state.whyDay = 0; }
    var strip = $('vstrip'), strip2 = $('vstrip2');
    m.days.forEach(function (d, i) {
      var b = document.createElement('button');
      b.type = 'button'; b.className = 'vc v-' + d.verdict.replace(' ', '').replace('/', '') + (i === 0 ? ' plan' : '') + (i === state.whyDay ? ' sel' : '');
      b.setAttribute('aria-label', 'Slip ' + plural(i, 'day') + ', land ' + fmtDate(d.landing_utc) + ': ' + VERDICT[d.verdict][1]);
      var tipHtml = '<b>' + (i ? 'Slip ' + plural(i, 'day') : 'As planned') + ': land ' + esc(fmtDate(d.landing_utc)) + '</b>' + VERDICT[d.verdict][0] + ' ' + VERDICT[d.verdict][1] +
        (d.sunlit_h === null ? '' : '<br>Sunlit ' + d.sunlit_h + ' h' + (d.sunlit_range_h ? ' <span class="rng">(' + d.sunlit_range_h[0] + ' to ' + d.sunlit_range_h[1] + ')</span>' : '') + ', need ' + m.need.sunlit_h +
          '<br>Earth contact ' + d.earth_h + ' h' + (d.earth_range_h ? ' <span class="rng">(' + d.earth_range_h[0] + ' to ' + d.earth_range_h[1] + ')</span>' : '') + ', need ' + m.need.earth_h +
          '<br>' + d.points_passing + ' of ' + d.points + ' points pass' +
          (d.coarse_passes === undefined ? '' : ' · coarser grid: ' + (d.coarse_passes ? 'yes' : 'no')) +
          (d.reasons.length ? '<br>' + esc(d.reasons.join('; ')) : '') + '<br>Smooth sphere: ' + (d.smooth_sphere_passes ? 'yes' : 'no')) +
        '<br>Click to see the Sun and the Earth against the skyline for this date';
      b.addEventListener('pointermove', function (ev) { showTip(ev, tipHtml); });
      b.addEventListener('pointerleave', hideTip);
      b.addEventListener('click', function () { hideTip(); selectWhyDay(i); });
      strip.appendChild(b);
      var differs = d.verdict !== 'n/a' && (d.smooth_sphere_passes !== (d.verdict === 'yes')) && d.verdict !== 'not sure';
      var c = document.createElement('span'); c.className = 'vc ' + (d.smooth_sphere_passes ? 'v-yes' : 'v-no') + (differs ? ' diff' : ''); strip2.appendChild(c);
    });
    renderWhy(); loadWhy();
    renderRibbon(); loadRibbon();
    if (window.SlipdayLinks && $('siteLinks')) { $('siteLinks').innerHTML = window.SlipdayLinks.html(m.site.lat, m.site.lon, m.site.name); }
    Array.prototype.forEach.call(box.querySelectorAll('[data-plan]'), function (b) {
      b.addEventListener('click', function () { setPlan(b.getAttribute('data-plan')); });
    });
  }
  /* ---------- why it flips: the Sun and the Earth against the skyline for one landing window ---------- */
  function whyBody(cfg, s, day) { var b = missionBody(cfg, s); b.day = day; return b; }
  function selectWhyDay(i) {
    state.whyDay = i;
    Array.prototype.forEach.call(document.querySelectorAll('#vstrip .vc'), function (c, k) { c.classList.toggle('sel', k === i); });
    if ($('mSlip') && String($('mSlip').value) !== String(i)) { $('mSlip').value = String(i); }
    dayBanner();
    loadWhy(); renderWhy();
  }
  /* one plain line for the selected day of slip, so a click on a red day visibly answers */
  function answerData() {
    var m = state.missions[state.mi], s = state.selected[state.mi], cfg = state.lastCfg, w = state.win, o = state.opt;
    if (!m || !s) { return null; }
    var d = {
      made_by: 'Slipday', made_at_utc: new Date().toISOString().slice(0, 19) + 'Z', page: location.href,
      site: { name: s.name, lat: s.lat, lon: s.lon }, landing_utc: m.landing_utc,
      need: m.need, window_days: m.window_days, landing_scatter_m: m.sure ? m.sure.scatter_m : null,
      rules: m.criteria, terrain: m.horizon && m.horizon.dem_label,
      verdict: m.verdict, slip_margin_days: m.slip_margin_days, touchdown_points_passing: m.sure ? m.sure.points_passing + ' of ' + m.sure.points : null,
      finer_grid: m.finer_grid_check ? m.finer_grid_check.short : null,
      days: m.days.map(function (x) { return { slip_days: x.slip_days, landing_utc: x.landing_utc, verdict: x.verdict, sunlit_h: x.sunlit_h, earth_h: x.earth_h, points_passing: x.points_passing }; }),
      monthly_windows: w && w.rows ? w.rows.slice(1).map(function (x) { return { landing_utc: x.landing_utc, verdict: x.verdict, slip_margin_days: x.slip_margin_days, fails_on: x.fails_on }; }) : null,
      other_sites: o && o.rows ? o.rows.map(function (x) {
        return { window_landing_utc: x.landing_utc, best_hour_here: x.best_hour, sites_checked: x.sites_checked,
                 sites_yes: x.sites_yes.map(function (y) { return { name: y.name, landing_utc: y.landing_utc, slip_margin_days: y.slip_margin_days, fragile: y.fragile }; }) };
      }) : 'not asked yet (press "Other sites, other hours" first)',
      notes: 'The sunlit-hour and Earth-contact needs are illustrative unless a published plan is named. A Yes holds only for a landing within the stated scatter.'
    };
    return d;
  }
  function saveBlob(text, name, type) {
    var a = document.createElement('a'); a.href = URL.createObjectURL(new Blob([text], { type: type })); a.download = name;
    document.body.appendChild(a); a.click(); setTimeout(function () { URL.revokeObjectURL(a.href); a.remove(); }, 1000);
  }
  function answerCsv(d) {
    var q = function (v) { v = v === null || v === undefined ? '' : String(v); return /[",\n]/.test(v) ? '"' + v.replace(/"/g, '""') + '"' : v; };
    var L = [];
    L.push('# Slipday answer for ' + d.site.name + ' (' + d.site.lat + ', ' + d.site.lon + '), landing ' + d.landing_utc);
    L.push('# need: ' + d.need.sunlit_h + ' sunlit h and ' + d.need.earth_h + ' h of Earth contact in ' + d.window_days + ' days; landing within ' + d.landing_scatter_m + ' m; ' + (d.need.text || ''));
    L.push('# verdict: ' + d.verdict + '; slip margin: ' + d.slip_margin_days + ' days; touchdown points passing: ' + d.touchdown_points_passing + (d.finer_grid ? '; ' + d.finer_grid : ''));
    L.push('# ' + d.notes);
    L.push('section,slip_days_or_window,landing_utc,verdict,sunlit_h,earth_h,detail');
    d.days.forEach(function (x) { L.push(['day', x.slip_days, x.landing_utc, x.verdict, x.sunlit_h, x.earth_h, x.points_passing + ' of 13 points'].map(q).join(',')); });
    (d.monthly_windows || []).forEach(function (x, i) { L.push(['monthly window', i + 1, x.landing_utc, x.verdict, '', '', (x.fails_on || []).join('; ') || (x.slip_margin_days + ' days of margin')].map(q).join(',')); });
    if (Array.isArray(d.other_sites)) {
      d.other_sites.forEach(function (r, i) { r.sites_yes.forEach(function (y) { L.push(['other site, window ' + (i + 2), i + 2, y.landing_utc, 'yes' + (y.fragile ? ' (fragile)' : ''), '', '', y.name + ', ' + y.slip_margin_days + ' days'].map(q).join(',')); }); });
    }
    return L.join('\n') + '\n';
  }
  /* one convention for landing spread everywhere: where 99 % of touchdowns fall (3.035 standard deviations, 2-D) */
  function spread99(k) {
    var km = function (m) { return m >= 1000 ? (m / 1000).toFixed(1) + ' km' : Math.round(m) + ' m'; };
    if (k.sigma_major_m === k.sigma_minor_m) { return '99 % within ' + km(k.within_99_pct_m || 3.035 * k.sigma_major_m) + ' of the aim'; }
    return '99 % within an oval about ' + km(2 * 3.035 * k.sigma_major_m) + ' by ' + km(2 * 3.035 * k.sigma_minor_m);
  }
  function dayBanner() {
    var b = $('dayBanner'), m = state.missions[state.mi], i = state.whyDay;
    if (!b || !m || !m.days[i]) { return; }
    if (!i) { b.hidden = true; b.textContent = ''; return; }
    var d = m.days[i], word = { yes: 'Yes', no: 'No', 'not sure': 'Not sure', 'n/a': 'Not computed' }[d.verdict] || d.verdict;
    var why = d.verdict === 'yes' ? '' : ((d.reasons && d.reasons.length ? d.reasons[0] : '') || ((d.unsure_because || [])[0] || ''));
    b.hidden = false;
    b.textContent = 'Land on ' + fmtDay(Date.parse(d.landing_utc) / 1000) + ' (launch slipped ' + plural(i, 'day') + '): ' + word + (why ? ': ' + why : '') + '.';
  }
  /* the challenge's objective in numbers: where the Sun and the Earth stand, and how far above the skyline, at touchdown */
  function objectiveLine(w) {
    var o = $('objLine');
    if (!o || !w || !w.touchdown) { return; }
    var td = w.touchdown, c16 = function (az) { return ['N', 'NNE', 'NE', 'ENE', 'E', 'ESE', 'SE', 'SSE', 'S', 'SSW', 'SW', 'WSW', 'W', 'WNW', 'NW', 'NNW'][Math.round(((az % 360) + 360) % 360 / 22.5) % 16]; };
    var one = function (name, az, el, sky) {
      var c = el - sky;
      return name + ' azimuth ' + Math.round(((az % 360) + 360) % 360) + '° (' + c16(az) + '), ' + el.toFixed(1) + '° above level, ' +
        (c >= 0 ? c.toFixed(1) + '° above the skyline' : Math.abs(c).toFixed(1) + '° below the skyline (hidden)');
    };
    o.innerHTML = '<span class="objTag">Challenge objective</span>Sun and Earth against the horizon at touchdown, ' + esc(w.landing_utc.slice(0, 16).replace('T', ' ')) + ' UTC' +
      (w.day ? ' (slip of ' + plural(w.day, 'day') + ')' : '') + ': ' + esc(one('Sun', td.sun_az, td.sun_el, td.sun_skyline_el)) + ' · ' + esc(one('Earth', td.earth_az, td.earth_el, td.earth_skyline_el)) + '.';
  }
  function loadWhy() {
    var cfg = state.lastCfg, s = state.selected[state.mi];
    if (!cfg || !s || !state.missions[state.mi]) { return; }
    var body = whyBody(cfg, s, state.whyDay), key = JSON.stringify(body);
    if (state.whyKey === key) { return; }
    state.whyKey = key;
    api('/api/why', body).then(function (w) { if (state.whyKey === key) { w._key = key; state.why = w; renderWhy(); show3d(); showContrast(); renderPolar(); } })
      .catch(function (e) { if (state.whyKey === key) { state.why = { _key: key, error: e.message, busy: e.busy }; renderWhy(); } });
  }
  function span2(h) { return h < 72 ? Math.round(h) + ' h' : (h / 24).toFixed(1) + ' days'; }
  function fmtWhen(iso) { return fmtDay(Date.parse(iso) / 1000) + ' ' + iso.slice(11, 16); }
  function bodyNow(name, el, sky, up, nextSet, nextRise, wHours, setWord, riseWord) {
    var clear = el - sky;
    var t = '<b>' + name + '</b> ' + (name === 'Sun' ? 'at touchdown ' : '') + el.toFixed(1) + '° up, ' + Math.abs(clear).toFixed(1) + '° ' + (clear >= 0 ? 'above' : 'below') + ' the skyline';
    if (up) {
      if (nextSet && nextSet.hours_from_now <= wHours) { t += ': <b>' + setWord + ' in ' + span2(nextSet.hours_from_now) + '</b> (' + esc(fmtWhen(nextSet.utc)) + ' UTC)'; }
      else { t += ': <b>up for the whole window</b>'; }
    } else {
      t += nextRise ? ': hidden, <b>' + riseWord + ' in ' + span2(nextRise.hours_from_now) + '</b> (' + esc(fmtWhen(nextRise.utc)) + ' UTC)' : ': hidden for as far ahead as was searched';
    }
    return t + '.';
  }
  function renderWhy() {
    var box = $('why');
    if (!box) { return; }
    var w = state.why;
    if (!w || w._key !== state.whyKey) { box.innerHTML = '<p class="cap whyWait">Drawing the Sun and the Earth against the skyline for this landing date…</p>'; return; }
    if (w.error) { box.innerHTML = '<p class="cap">' + esc(w.error) + '</p>'; return; }
    box.innerHTML = '';
    objectiveLine(w); dayBanner();
    var head = document.createElement('p'); head.className = 'whyHead';
    head.innerHTML = '<b>Sun and Earth against the terrain skyline</b>, landing ' + esc(fmtDate(w.landing_utc)) + (w.day ? ' (slip of ' + plural(w.day, 'day') + ')' : ' (as planned)') +
      ' + ' + w.window_days + ' days; faint where hidden';
    head.title = w.labels.real + '. ' + w.labels.derived + '.';
    box.appendChild(head);
    box.appendChild(whyChart(w));
    var lg = document.createElement('p'); lg.className = 'whyLegend';
    lg.innerHTML = 'Grey: the skyline all round. Lines: the paths of the Sun (orange) and the Earth (blue) over the window,<i></i>in view<i class="dash"></i>hidden by the ground. Along the bottom: compass directions (S 180°, W 270°, N 0°, E 90°).';
    box.appendChild(lg);
    var td = w.touchdown, f = w.criteria.min_sun_fraction;
    var sunRule = f <= 0 ? 'any part of the Sun’s disc counts' : (f >= 1 ? 'the whole disc must show' : (f === 0.5 ? 'half' : (f * 100) + '% of') + ' the Sun’s disc must show');
    var earthRule = 'the Earth’s centre must clear the skyline' + (w.criteria.earth_margin_deg ? ' by ' + w.criteria.earth_margin_deg + '°' : '');
    var p1 = document.createElement('p'); p1.className = 'whyTxt';
    p1.innerHTML = bodyNow('Sun', td.sun_el, td.sun_skyline_el, td.sun_up, td.next_sunset, td.next_sunrise, w.window_hours, 'sunset', 'sunrise') + ' ' +
      bodyNow('Earth', td.earth_el, td.earth_skyline_el, td.earth_up, td.next_earthset, td.next_earthrise, w.window_hours, 'Earthset', 'Earthrise') +
      ' Window: <b>' + w.hours.sunlit + '</b> sunlit h of ' + w.need.sunlit_h + ' needed (' + sunRule + '), <b>' + w.hours.earth +
      '</b> h of Earth contact of ' + w.need.earth_h + ' (' + earthRule + ')' +
      (w.skyline ? '; a smooth sphere gives ' + w.hours.smooth_sunlit + ' and ' + w.hours.smooth_earth + '.' : '.');
    p1.title = 'Rules for these numbers: ' + w.labels.rules + '. The LOLA team’s Earth-visibility maps count any part of the Earth’s disc, which reads a few points higher than the centre rule used here.';
    var more = document.createElement('details'); more.className = 'whyMore whyHours';
    var sv = survNow(), sd = sv && sv.days[w.day];
    var grow = '';
    if (sv && sv.margin_days >= 1) {
      var d0 = sv.days[0], dm = sv.days[sv.margin_days], atl = function (f) { return f ? 'at least ' : ''; };
      var verb = function (a, b) { return b > a ? 'grows from ' + a + ' to ' : (b < a ? 'shrinks from ' + a + ' to ' : 'stays at '); };
      grow = ' <b title="Ride-through: how long the lander must last without sunlight or without contact">Ride-through: slip ' + sv.margin_days + ' day' + (sv.margin_days === 1 ? '' : 's') + ' and the longest night the lander meets ' + verb(d0.night_full_h, dm.night_full_h) +
        atl(dm.night_full_open) + dm.night_full_h + ' hours</b>; the longest Earth outage ' + verb(d0.outage_full_h, dm.outage_full_h) + atl(dm.outage_full_open) + dm.outage_full_h + ' h (whole runs, to their end).';
    }
    more.id = 'survLine';
    more.innerHTML = '<summary>Window: <b>' + w.hours.sunlit + '</b> sunlit h (needs ' + w.need.sunlit_h + '), <b>' + w.hours.earth + '</b> h of Earth contact (needs ' + w.need.earth_h + ')' +
      (sd ? '; it meets a <b>' + sd.night_full_h + ' h</b> night, a <b>' + sd.outage_full_h + ' h</b> outage.' : '.') + '</summary>' + (grow ? '<p class="cap">' + grow + '</p>' : '');
    more.appendChild(p1);
    var chartBox = document.createElement('div'); chartBox.id = 'survChartBox'; more.appendChild(chartBox);
    var p2 = document.createElement('div'); p2.className = 'whyFlip';
    var fl = w.flip, btn = '';
    if (fl && fl.day !== null && fl.day !== undefined && fl.day !== w.day) { btn += '<button type="button" id="whyGo">Show that date</button>'; }
    if (w.day > 0) { btn += '<button type="button" id="whyPlan">Plan for ' + esc(fmtDate(w.landing_utc)) + '</button>'; }
    /* which need ends the margin, and whether that need is a published figure or an illustrative one */
    var mNow = state.missions[state.mi], selNow = state.selected[state.mi], eb = fl && fl.ended_by, by = '';
    var rpNow = mNow && state.replays.filter(function (x) {
      return selNow && x.site === selNow.id && x.landing === mNow.landing_utc && x.need_sun_h === mNow.need.sunlit_h && x.need_earth_h === mNow.need.earth_h && x.window_days === mNow.window_days;
    })[0];
    if (eb) {
      if (eb.kind === 'sunlit hours') {
        by = 'Ended by the sunlit-hours need (' + eb.got_h + ' of ' + eb.need_h + ' h), ' +
          (rpNow && rpNow.need_kind === 'published plan' ? 'a figure from the mission’s published plan.' : 'an illustrative figure, not a published requirement.');
      } else if (eb.kind === 'earth contact hours') {
        by = 'Ended by the Earth-contact need (' + eb.got_h + ' of ' + eb.need_h + ' h), an illustrative figure, not a published requirement.';
      } else if (eb.kind === 'sun at touchdown') { by = 'Ended by the condition “landing in sunlight”, a choice on this card, not a published requirement.';
      } else if (eb.kind === 'earth at touchdown') { by = 'Ended by the condition “Earth in view at touchdown”, a choice on this card, not a published requirement.';
      } else { by = 'Ended by a disagreement between terrain grids, not by a mission need.'; }
    }
    var how = fl ? fl.text : '', cut = how.indexOf(': ');
    var tn = fl && fl.stretch && fl.stretch.terrain, where = '';
    if (tn && tn.kind === 'terrain' && !tn.near_field) {
      var c16 = ['N', 'NNE', 'NE', 'ENE', 'E', 'ESE', 'SE', 'SSE', 'S', 'SSW', 'SW', 'WSW', 'W', 'WNW', 'NW', 'NNW'][Math.round(((tn.az_deg % 360) + 360) % 360 / 22.5) % 16];
      where = ' The ' + (fl.stretch.body === 'sun' ? 'Sun' : 'Earth') + ' goes behind ground ' + (tn.named ? '<span title="' + esc(tn.named.phrase) + (tn.named.rim_also ? ': the point is at ' + Math.round(100 * tn.named.share_of_radius) + '% of the mountain’s radius and on the crater’s rim line' : '') + ' (IAU gazetteer: centre and diameter only)">' + esc(tn.named.phrase.split(', on the rim of')[0]) + '</span>, ' : '') +
        (tn.dist_km < 1 ? Math.round(tn.dist_km * 1000) + ' m' : tn.dist_km.toFixed(1) + ' km') + ' ' + c16 + '.';
    }
    p2.innerHTML = '<b>What ends the margin.</b> ' + (by ? '<b id="endedBy">' + esc(by) + '</b>' : '') + where +
      (how ? '<details class="whyMore"><summary>' + esc(cut > 0 ? how.slice(0, cut) : 'How') + ': how and where ' + btn + '</summary>' + esc(how) + '</details>' : ' ' + btn);
    box.appendChild(p2);
    box.appendChild(more);
    renderSurvival();
    if ($('whyGo')) { $('whyGo').addEventListener('click', function () { selectWhyDay(fl.day); }); }
    if ($('dlAnswer') && !$('dlAnswer')._on) {
      $('dlAnswer')._on = true;
      $('dlAnswer').addEventListener('click', function () { var d = answerData(); if (d) { saveBlob(answerCsv(d), 'slipday_answer.csv', 'text/csv'); } });
      $('dlAnswerJson').addEventListener('click', function () { var d = answerData(); if (d) { saveBlob(JSON.stringify(d, null, 1), 'slipday_answer.json', 'application/json'); } });
    }
    if ($('whyPlan')) { $('whyPlan').addEventListener('click', function () { setPlan(w.landing_utc); }); }
  }
  function whyChart(w) {
    var t = w.track, sk = w.skyline, W = NARROW ? 350 : 600, H = NARROW ? 200 : 126, P = { l: 30, r: 6, t: 10, b: 18 };
    var x0 = P.l, x1 = W - P.r, y0 = P.t, y1 = H - P.b;
    var lo = -1, hi = 2, i;
    if (sk) { sk.el_deg.forEach(function (v) { if (v < lo) { lo = v; } if (v > hi) { hi = v; } }); }
    t.sun_el.forEach(function (v, k) { if (v > hi) { hi = v; } if (v < lo && t.sun_lit[k]) { lo = v; } });
    t.earth_el.forEach(function (v, k) { if (v > hi) { hi = v; } if (v < lo && t.earth_up[k]) { lo = v; } });
    hi = Math.min(Math.ceil(hi + 0.6), 45); lo = Math.max(Math.floor(lo - 0.4), -10);
    var rel = function (az) { return ((az + 180) % 360 + 360) % 360 - 180; };
    var sx = function (az) { return x0 + (rel(az) + 180) / 360 * (x1 - x0); };
    var sy = function (e) { return y1 - (Math.max(lo, Math.min(hi, e)) - lo) / (hi - lo) * (y1 - y0); };
    var svg = el('svg', { viewBox: '0 0 ' + W + ' ' + H, role: 'img', 'class': 'whySvg',
      'aria-label': 'Terrain skyline around ' + w.site.name + ' with the paths of the Sun and the Earth through the landing window' });
    var step = niceStep(hi - lo);
    for (var v = Math.ceil(lo / step) * step; v <= hi; v += step) {
      svg.appendChild(el('line', { x1: x0, x2: x1, y1: sy(v), y2: sy(v), 'class': 'gridl' }));
      svg.appendChild(el('text', { x: x0 - 4, y: sy(v) + 3.5, 'text-anchor': 'end' }, v + '°'));
    }
    [['S', -180], ['W', -90], ['N', 0], ['E', 90], ['S', 180]].forEach(function (q) {
      var x = x0 + (q[1] + 180) / 360 * (x1 - x0);
      svg.appendChild(el('line', { x1: x, x2: x, y1: y1, y2: y1 + 3, 'class': 'axis' }));
      svg.appendChild(el('text', { x: x, y: y1 + 13, 'text-anchor': q[1] === -180 ? 'start' : (q[1] === 180 ? 'end' : 'middle') }, q[0]));
    });
    if (sk) {
      var pts = [];
      for (i = 0; i < sk.az_deg.length; i++) { pts.push([rel(sk.az_deg[i]), sk.el_deg[i]]); }
      pts.sort(function (a, b) { return a[0] - b[0]; });
      pts.push([180, pts[0][1]]);
      var d = 'M' + x0 + ' ' + y1;
      pts.forEach(function (q) { d += 'L' + (x0 + (q[0] + 180) / 360 * (x1 - x0)).toFixed(1) + ' ' + sy(q[1]).toFixed(1); });
      svg.appendChild(el('path', { d: d + 'L' + x1 + ' ' + y1 + 'Z', 'class': 'skyfill' }));
    }
    svg.appendChild(el('line', { x1: x0, x2: x1, y1: sy(0), y2: sy(0), 'class': 'sphl' }));
    /* labels are placed last, each moved clear of those already placed, so none overlaps another */
    var placed = [];
    function label(x, y, anchor, cls, text, optional) {
      var wd = text.length * (cls === 'tiny' ? 5.0 : 5.7) + 4, ht = 12;
      var bx = function (yy) { var l = anchor === 'end' ? x - wd : (anchor === 'middle' ? x - wd / 2 : x); return [l, yy - ht + 2, l + wd, yy + 2]; };
      var hits = function (b) { return placed.some(function (q) { return b[0] < q[2] && b[2] > q[0] && b[1] < q[3] && b[3] > q[1]; }); };
      var tries = optional ? [0, -11, 11] : [0, 13, -13, 26, -26, 39, -39], yy = y;
      for (var k = 0; k < tries.length; k++) {
        yy = Math.max(y0 + 9, Math.min(y1 - 3, y + tries[k]));
        if (!hits(bx(yy))) { break; }
        if (k === tries.length - 1) { if (optional) { return; } }
      }
      placed.push(bx(yy));
      svg.appendChild(el('text', { x: x, y: yy, 'text-anchor': anchor, 'class': cls }, text));
    }
    /* a track in two styles: solid where the body counts as up, faint where the skyline hides it */
    function track(az, elv, up, cls) {
      var seg = { 1: '', 0: '' }, prevX = null, prevUp = null;
      for (var k = 0; k < az.length; k++) {
        var xx = sx(az[k]), yy = sy(elv[k]), u = up[k] ? 1 : 0;
        var jump = prevX !== null && Math.abs(xx - prevX) > (x1 - x0) / 2, off = elv[k] < lo - 0.01;
        if (prevX === null || jump || off) { seg[u] += 'M' + xx.toFixed(1) + ' ' + yy.toFixed(1); }
        else {
          if (u !== prevUp) { seg[u] += 'M' + prevX.toFixed(1) + ' ' + sy(elv[k - 1]).toFixed(1); }
          seg[u] += 'L' + xx.toFixed(1) + ' ' + yy.toFixed(1);
        }
        prevX = off ? null : xx; prevUp = u;
      }
      if (seg[0]) { svg.appendChild(el('path', { d: seg[0], 'class': cls + ' hid' })); }
      if (seg[1]) { svg.appendChild(el('path', { d: seg[1], 'class': cls })); }
    }
    track(t.earth_az, t.earth_el, t.earth_up, 'earthl');
    track(t.sun_az, t.sun_el, t.sun_lit, 'sunl');
    /* the ground each body goes behind in this window */
    function mark(list, word) {
      if (!list.length || !sk) { return; }
      var st = list[0], tr = st.terrain;
      if (tr.skyline_el_deg === undefined) { return; }
      var x = sx(tr.az_deg), y = sy(tr.skyline_el_deg);
      svg.appendChild(el('path', { d: 'M' + (x - 4) + ' ' + (y - 9) + 'L' + (x + 4) + ' ' + (y - 9) + 'L' + x + ' ' + (y - 2) + 'Z', 'class': 'whyMark' }));
      var lab = word + (st.event === 'comes out from behind' ? ' rises' : ' sets') + ' here' + (tr.dist_km ? ', ' + (tr.dist_km < 1 ? Math.round(tr.dist_km * 1000) + ' m' : tr.dist_km.toFixed(1) + ' km') + ' away' : '');
      var right = x > (x0 + x1) / 2;
      later.push([right ? x - 7 : x + 7, Math.max(y - (word === 'Sun' ? 3 : 14), y0 + 8), right ? 'end' : 'start', 'whyLab', lab]);
    }
    var later = [];
    mark(w.sun_hidden, 'Sun'); mark(w.earth_hidden, 'Earth');
    var n = t.count - 1;
    svg.appendChild(el('circle', { cx: sx(t.earth_az[n]), cy: sy(t.earth_el[n]), r: 3, 'class': 'dot-end earth' }));
    svg.appendChild(el('circle', { cx: sx(t.sun_az[n]), cy: sy(t.sun_el[n]), r: 3, 'class': 'dot-end sun' }));
    svg.appendChild(el('circle', { cx: sx(t.earth_az[0]), cy: sy(t.earth_el[0]), r: 5, 'class': 'dot-earth' }));
    svg.appendChild(el('circle', { cx: sx(t.sun_az[0]), cy: sy(t.sun_el[0]), r: 5, 'class': 'dot-sun' }));
    var lx = function (az) { var x = sx(az); return x > x1 - 120 ? x - 9 : x + 9; }, la = function (az) { return sx(az) > x1 - 120 ? 'end' : 'start'; };
    label(lx(t.sun_az[0]), sy(t.sun_el[0]) - 7, la(t.sun_az[0]), 'lbl-strong', 'Sun at touchdown');
    label(lx(t.earth_az[0]), Math.min(sy(t.earth_el[0]) + 15, y1 - 3), la(t.earth_az[0]), 'lbl-strong', 'Earth at touchdown');
    later.forEach(function (q) { label(q[0], q[1], q[2], q[3], q[4]); });
    label(x0 + 0.42 * (x1 - x0), sy(0) - 3, 'middle', 'tiny', 'level horizon (smooth sphere)', true);
    var hit = el('rect', { x: x0, y: y0, width: x1 - x0, height: y1 - y0, fill: 'transparent' });
    var t0 = Date.parse(t.start_utc) / 1000;
    hit.addEventListener('pointermove', function (ev) {
      var r = svg.getBoundingClientRect(), mx = (ev.clientX - r.left) / r.width * W, my = (ev.clientY - r.top) / r.height * H;
      var best = null;
      [['Sun', t.sun_az, t.sun_el, t.sun_lit], ['Earth', t.earth_az, t.earth_el, t.earth_up]].forEach(function (b) {
        for (var k = 0; k < b[1].length; k++) {
          var dx = sx(b[1][k]) - mx, dy = sy(b[2][k]) - my, dd = dx * dx + dy * dy;
          if (!best || dd < best.d) { best = { d: dd, name: b[0], k: k, el: b[2][k], az: b[1][k], up: b[3][k] }; }
        }
      });
      var az = ((mx - x0) / (x1 - x0) * 360 - 180 + 360) % 360, html = '';
      if (best && best.d < 400) {
        html = '<b>' + best.name + ', ' + esc(fmtUtc(t0 + best.k * 3600)) + '</b>' + (best.k ? 'hour ' + best.k + ' after touchdown' : 'at touchdown') + '<br>' + best.el.toFixed(2) + '° elevation, azimuth ' + best.az.toFixed(0) +
          '°<br>' + (best.up ? 'above the skyline' : 'behind the skyline');
        az = best.az;
      }
      if (sk) {
        var k2 = Math.round(az / 360 * sk.az_deg.length) % sk.az_deg.length;
        html += (html ? '<br>' : '') + '<u>Skyline at azimuth ' + az.toFixed(0) + '°</u><br>' + sk.el_deg[k2].toFixed(2) + '°' + (sk.dist_km[k2] !== null ? ', set by ground ' + sk.dist_km[k2].toFixed(1) + ' km away' : '') + '<br>' + esc(modelTag(w.horizon));
      }
      showTip(ev, html);
    });
    hit.addEventListener('pointerleave', hideTip);
    svg.appendChild(hit);
    return svg;
  }
  /* ---------- the card's Earth margin: how far the Earth clears the skyline, and the station rule ---------- */
  function loadEarthMask() {
    var cfg = state.lastCfg, s = state.selected[state.mi];
    if (!cfg || !s || !state.missions[state.mi]) { return; }
    var body = missionBody(cfg, s), key = JSON.stringify(body);
    if (state.emKey === key) { return; }
    state.emKey = key; state.em = null;
    api('/api/earth-mask', body).then(function (r) { if (state.emKey === key) { r._key = key; state.em = r; renderEarthLine(); } })
      .catch(function () { /* the card stands without it */ });
  }
  function renderEarthLine() {
    var box = $('earthLine'), r = state.em, m = state.missions[state.mi];
    if (!box || !m) { return; }
    var st = state.lastCfg && state.lastCfg.opts.earth_stations;
    var stTxt = st ? '<span class="stLine" title="Goldstone, Madrid or Canberra must have the Moon at least 10 degrees up: the low-power transmit limit of the DSN Telecommunications Link Design Handbook 810-005, module 301 Rev. P.">Contact also needs a DSN station.</span> ' :
      '<span class="stLine">Station rule off: Earth contact is the Earth above the skyline only.</span> ';
    var links = '<button type="button" id="contactGo">Stations hour by hour</button><button type="button" id="shadowGo">Beside permanent shadow?</button>' +
      (window.SlipdayView3D ? '<button type="button" id="why3d">See this place in 3-D</button>' : '');
    if (!r || !r.available) {
      box.innerHTML = stTxt;
    } else {
      var cl = r.clearance_at_touchdown_deg, txt;
      if (r.verdict_at_zero === 'yes') {
        txt = '<b>Earth margin</b> (an Earth mask is the least height above the skyline a radio link is given)<b>:</b> the Earth’s centre is <b' + (r.thinnest_day === 0 ? ' title="the thinnest clearance of its ' + (r.margin_days_at_zero + 1) + ' yes-days"' : '') + '>' + cl.toFixed(2) + '°</b> above the skyline at touchdown' + (r.yes_up_to_deg >= r.max_deg ? '. Yes at every Earth mask up to <b>' + r.max_deg.toFixed(0) + '°</b> (the end of the sweep)' : '. Yes up to an Earth mask of <b>' + r.yes_up_to_deg.toFixed(2) + '°</b>') +
          (r.not_sure_from_deg !== null ? '; Not sure from ' + r.not_sure_from_deg.toFixed(2) + '°' : '') + (r.no_from_deg !== null ? ', No from ' + r.no_from_deg.toFixed(2) + '°' : '') +
          ' <span class="mtag" title="No published elevation mask for a direct-to-Earth link from the lunar surface was found (the LunaNet Interoperability Specification v5 is silent on one); every non-zero mask here is illustrative.">masks illustrative</span>.' +
          (r.yes_up_to_deg < 2 ? ' <span class="linkNote" title="JPL IPN Progress Report 42-243 (15 Nov 2025) on direct-with-Earth links from a lander: reflections off the surface make the signal fade at low elevation, and it treats angles under about 2 degrees as extremely low.">A real link would want more than ' + r.yes_up_to_deg.toFixed(1) + '° (our inference; JPL IPN 42-243).</span>' : '');
      } else {
        txt = '<b>Earth margin:</b> at touchdown the Earth’s centre is ' + Math.abs(cl).toFixed(2) + '° ' + (cl >= 0 ? 'above' : 'below') + ' the skyline.';
      }
      box.innerHTML = txt + ' ' + stTxt;
    }
    if ($('cardLinks')) { $('cardLinks').innerHTML = links; }
    $('contactGo').addEventListener('click', loadContact);
    if ($('why3d')) { $('why3d').addEventListener('click', function () { var t = $('view3dPanel'); if (t) { t.hidden = false; t.scrollIntoView({ behavior: 'smooth' }); } }); }
    $('shadowGo').addEventListener('click', function () { loadShadow(); var t = $('shadowSites'); if (t) { t.scrollIntoView({ behavior: 'smooth' }); } });
  }

  /* ---------- survival across slip days: hours to ride through on stored energy (slipday/survival.py) ---------- */
  function survNow() { var r = state.surv; return r && r.available && r._key === state.survKey ? r : null; }
  function loadSurvival() {
    var cfg = state.lastCfg, s = state.selected[state.mi];
    if (!cfg || !s || !state.missions[state.mi]) { return; }
    var body = missionBody(cfg, s), key = JSON.stringify(body);
    if (state.survKey === key) { return; }
    state.survKey = key; state.surv = null;
    api('/api/survival', body).then(function (r) { if (state.survKey === key) { r._key = key; state.surv = r; renderSurvival(); renderWhy(); } })
      .catch(function () { /* the card stands without it */ });
  }
  function renderSurvival() {
    var box = $('survChartBox'), r = survNow();
    if (!box) { return; }
    if (!r) { box.innerHTML = '<p class="cap">Working out the longest night and Earth outage for each day of slip…</p>'; return; }
    var h = '<h4>Hours to ride through on stored energy, for each day of slip</h4>';
    /* one bar pair per day of slip: night (amber) and Earth outage (blue), hours; days that pass are marked */
    var n = Math.min(r.days.length, 30), W = NARROW ? 350 : 600, H = 130, l = 30, rr = 6, t = 8, b = 22, bw = (W - l - rr) / n;
    var mx = 24; r.days.slice(0, n).forEach(function (d) { mx = Math.max(mx, d.night_full_h, d.outage_full_h); });
    mx = Math.ceil(mx / 24) * 24;
    var y = function (v) { return t + (1 - v / mx) * (H - t - b); };
    var svg = '<svg viewBox="0 0 ' + W + ' ' + H + '" class="survChart" role="img" aria-label="Longest night and longest Earth outage for each day of slip">';
    for (var v = 0; v <= mx; v += (mx > 168 ? 72 : 24)) { svg += '<line x1="' + l + '" x2="' + (W - rr) + '" y1="' + y(v) + '" y2="' + y(v) + '" class="gridl"/><text x="' + (l - 4) + '" y="' + (y(v) + 3.5) + '" text-anchor="end">' + v + ' h</text>'; }
    r.days.slice(0, n).forEach(function (d, i) {
      var x = l + i * bw;
      if (d.verdict === 'yes') { svg += '<rect x="' + x.toFixed(1) + '" y="' + (H - b + 3) + '" width="' + (bw - 1).toFixed(1) + '" height="4" class="survPass"/>'; }
      svg += '<rect x="' + (x + 1).toFixed(1) + '" y="' + y(d.night_full_h).toFixed(1) + '" width="' + Math.max(1, bw / 2 - 1.5).toFixed(1) + '" height="' + (H - b - y(d.night_full_h)).toFixed(1) + '" class="survNight"><title>slip ' + i + ' d: longest night ' + d.night_full_h + ' h (' + d.night_h + ' h of it inside the window)</title></rect>';
      svg += '<rect x="' + (x + bw / 2).toFixed(1) + '" y="' + y(d.outage_full_h).toFixed(1) + '" width="' + Math.max(1, bw / 2 - 1.5).toFixed(1) + '" height="' + (H - b - y(d.outage_full_h)).toFixed(1) + '" class="survOut"><title>slip ' + i + ' d: longest Earth outage ' + d.outage_full_h + ' h (' + d.outage_h + ' h of it inside the window)</title></rect>';
      if (i % (NARROW ? 5 : 3) === 0) { svg += '<text x="' + (x + bw / 2).toFixed(1) + '" y="' + (H - 4) + '" text-anchor="middle">+' + i + '</text>'; }
    });
    svg += '</svg>';
    h += svg + '<p class="vLegend"><span><i class="k survNightK"></i>longest night</span><span><i class="k survOutK"></i>longest Earth outage</span><span><i class="k yes"></i>slip day that still passes</span><span>x axis: days of slip</span></p>' +
      '<p class="cap">' + esc(r.rule) + ' Worst of the ' + r.points + ' touchdown points within the landing scatter. A run that begins inside the ' + r.window_days + '-day window is counted to its end, so a late landing shows the whole night it runs into; hover a bar for the part inside the window. No map of these hours is drawn: at 556 of the 574 map points that keep a margin the worst passing night is 12 days or more (the full lunar night a late landing runs into), so the map would be one colour.</p>';
    box.innerHTML = h;
  }

  /* ---------- next monthly launch windows (slipday/windows.py) ---------- */
  function failWords(list) {
    var w = { 'sunlight': 'sunlight', 'Earth contact': 'Earth', 'Sun at touchdown': 'Sun down', 'Earth at touchdown': 'Earth down' };
    return list.map(function (x) { return w[x] || x; }).join(', ');
  }
  /* rule R13: in each missed window, the best landing hour here and which other site is a clear yes */
  function loadOptions() {
    var cfg = state.lastCfg, s = state.selected[state.mi];
    if (!cfg || !s) { return; }
    var body = missionBody(cfg, s);
    body.alternatives = state.selected.map(siteRef);
    var key = JSON.stringify(body);
    if (state.optKey === key) { return; }
    state.optKey = key; state.opt = null;
    api('/api/window-options', body).then(function (r) { if (state.optKey === key) { r._key = key; state.opt = r; renderOptions(); } }).catch(function () {});
  }
  function renderOptions() {
    var box = $('winAlt'), r = state.opt, w = state.win;
    if (!box) { return; }
    if (!state.optShow) { box.innerHTML = ''; return; }
    if (!r || !r.available || r._key !== state.optKey || !w || !w.rows) { box.innerHTML = '<span class="small">Checking 20 other sites at every 6 h within 3 days of each of the next three windows (up to a few minutes the first time)…</span>'; return; }
    var site = state.selected[state.mi], parts = [];
    r.rows.forEach(function (o, i) {
      var me = w.rows[i + 1];
      if (!me) { return; }
      var mon = fmtDate(o.landing_utc.slice(0, 10) + 'T00:00:00Z');
      var here = me.verdict === 'yes' ? 'Yes here' : (o.best_hour.found ? 'here at ' + fmtDate(o.best_hour.landing_utc) + ' (' + o.best_hour.slip_margin_days + ' d' + (o.best_hour.fragile ? ', fragile' : '') + ')' : 'no hour within 3 days here');
      /* lead with the most robust option (the one whose touchdown points clear the skyline by the most), then the rest */
      var ys = o.sites_yes.slice().sort(function (a, b) { return (a.fragile - b.fragile) || (b.min_clearance_deg - a.min_clearance_deg) || (b.slip_margin_days - a.slip_margin_days); });
      var fy = ys[0], nm = fy ? esc(fy.name.replace(/ \(.*\)$/, '')) : '';
      var nfrag = ys.filter(function (y) { return y.fragile; }).length;
      var alt = fy ? 'steadiest: <span title="' + esc(fy.name) + '; smallest clearance at touchdown ' + fy.min_clearance_deg.toFixed(2) + '°">' + nm + '</span> ✓ at ' + esc(fmtDate(fy.landing_utc)) + ', ' + fy.slip_margin_days + ' d' +
        (fy.fragile ? ' <span class="frag">(fragile)</span>' : '') + '; ' + o.sites_yes.length + ' of ' + o.sites_checked + ' other sites have a Yes hour within 3 days, ' +
        '<span class="frag" title="Fragile: on a passing day a touchdown point has the Sun or the Earth less than 0.27° (the Sun’s radius) above the skyline at touchdown, so a small change in terrain or ephemeris can cost days of margin">' + nfrag + ' of them fragile</span>' :
        'no other site has a Yes hour within 3 days (' + o.sites_checked + ' checked)';
      if (me.verdict !== 'yes') { parts.push('<b>' + esc(mon) + ':</b> ' + here + '; ' + alt); }
    });
    box.innerHTML = parts.length ? '<span title="For this site and each other site (the page’s sites, then 18 well-placed map points), the clear-yes landing with the most margin, trying every 6 hours within 3 days of the window">Other options:</span> <small>(for the next monthly windows of the planned date, not for the day picked on the strip)</small> ' + parts.join(' · ') : 'Every next window is Yes here.';
  }
  function loadWindows() {
    var cfg = state.lastCfg, s = state.selected[state.mi];
    if (!cfg || !s || !state.missions[state.mi]) { return; }
    var body = missionBody(cfg, s), key = JSON.stringify(body);
    if (state.winKey === key) { return; }
    state.winKey = key; state.win = null;
    api('/api/windows', body).then(function (r) { if (state.winKey === key) { r._key = key; state.win = r; renderWindows(); renderOptions(); } }).catch(function () {});
  }
  function renderWindows() {
    var box = $('winLine'), r = state.win;
    if (!box) { return; }
    var h = '<span title="Real launch windows come a few days each month, built around the landing (Intuitive Machines on IM-1: each month has a window of about three to six days). That a missed window moves the landing one synodic month (29.5 days), to the same time of the lunar day, is our inference from those sources, not a published rule.">· <b>Missed the window? Next</b> <small>(inferred +29.5 d)</small><b>:</b></span> ';
    if (!r || !r.available || r._key !== state.winKey) { box.innerHTML = h + '<span class="small">working out…</span>'; return; }
    h += r.rows.slice(1).map(function (x) {
      var v = VERDICT[x.verdict] || ['', x.verdict];
      return '<button type="button" class="win v-' + x.verdict.replace(' ', '') + '" data-win="' + esc(x.landing_utc) + '" title="Landing ' + esc(x.landing_utc.slice(0, 16).replace('T', ' ')) + ' UTC: ' + v[1] +
        (x.fails_on && x.fails_on.length ? ' (fails on ' + esc(x.fails_on.join(', ')) + '; ' + x.sunlit_h + ' sunlit h, ' + x.earth_h + ' Earth h)' : '') +
        (x.verdict === 'yes' ? ', ' + x.slip_margin_days + ' days of margin' : '') + '; the lander meets a ' + x.night_met_h + ' h night and a ' + x.outage_met_h + ' h Earth outage">' +
        esc(fmtDate(x.landing_utc.slice(0, 10) + 'T00:00:00Z')) + ' ' + v[0] + (x.verdict === 'yes' ? ' ' + x.slip_margin_days + ' d' : (x.fails_on && x.fails_on.length ? ' ' + esc(failWords(x.fails_on)) : '')) + '</button>';
    }).join('') + ' <button type="button" id="optGo" title="For each missed window: the best landing hour here and which other site is a clear yes (about a minute the first time)">Other sites, other hours</button> <button type="button" id="realGo">Real missions</button>';
    box.innerHTML = h;
    Array.prototype.forEach.call(box.querySelectorAll('[data-win]'), function (b) { b.addEventListener('click', function () { setPlan(b.getAttribute('data-win')); }); });
    $('realGo').addEventListener('click', loadReal);
    $('optGo').addEventListener('click', function () { state.optShow = true; loadOptions(); renderOptions(); });
  }
  function loadReal() {
    var panel = $('realPanel');
    panel.hidden = false; panel.scrollIntoView({ behavior: 'smooth' });
    if (state.real) { renderReal(); return; }
    $('real').innerHTML = '<p class="note">Loading…</p>';
    api('/api/real-windows').then(function (r) { state.real = r; renderReal(); }).catch(function (e) { $('real').innerHTML = '<p class="note">' + esc(e.message) + '</p>'; });
    api('/api/artemis-regions').then(function (r) { state.artemis = r; renderReal(); }).catch(function () {});
  }
  function renderReal() {
    var r = state.real, box = $('real');
    if (!r) { return; }
    if (!r.available) { box.innerHTML = '<p class="note">' + esc(r.reason) + '</p>'; return; }
    var table = function (res, label, longCols) {
      var h = '<div class="tablewrap"><table class="data realT"><tr><th>Window</th><th>Landing (UTC)</th><th>Verdict</th><th>Slip margin</th><th>Sunlit / Earth h in 14 d</th><th>Night it meets</th><th>Earth outage it meets</th>' +
        (longCols ? '<th>In 100 days: Sun / Earth / both h</th><th>Longest night in 100 days</th>' : '') + '<th></th></tr>';
      res.rows.forEach(function (x) {
        var v = VERDICT[x.verdict] || ['', x.verdict];
        h += '<tr><td>' + esc(label(x)) + '</td><td>' + esc(x.landing_utc.slice(0, 16).replace('T', ' ')) + '</td><td class="sbest v-' + x.verdict.replace(' ', '') + '">' + v[0] + ' ' + v[1] + ' <small>' + x.points_passing + ' of ' + x.points + '</small></td>' +
          '<td class="num">' + (x.verdict === 'yes' ? x.slip_margin_days + ' d' : (x.next_good_utc ? '<small>next clear yes ' + esc(x.next_good_utc.slice(0, 16).replace('T', ' ')) + '</small>' : '<small>none in the next 15 days</small>')) + '</td><td class="num">' + x.sunlit_h + ' / ' + x.earth_h + '</td><td class="num">' + x.night_met_h + ' h</td><td class="num">' + x.outage_met_h + ' h</td>' +
          (longCols ? '<td class="num">' + x.long.sunlit_h_min + ' / ' + x.long.earth_h_min + ' / ' + x.long.sun_and_earth_h_min + '</td><td class="num">' + x.long.night_met_h_max + ' h</td>' : '') +
          '<td><button type="button" class="add" data-real="' + esc(res === r.im1 ? 'im1' : 'viper') + '|' + esc(x.landing_utc) + '">Plan this</button></td></tr>';
      });
      return h + '</table></div>';
    };
    var im = r.im1, vi = r.viper;
    var h = '<p class="note"><b>How real slips move.</b> A south-pole lander gets a launch window of a few days each month, built so that the landing falls when the Sun and the Earth suit the site: “each month has a window around three to six days” and “that landing site is helping to drive both the launch date and the length of the launch window” (Intuitive Machines on IM-1, Spaceflight Now, 27 Oct 2023). IM-1 had a “three-day window ... to land on the moon on Feb. 22” (Space.com, Feb 2024): it launched on the second day and still landed on the 22nd. It had first aimed at a January window. So a slip inside a window leaves the landing where it is. <b>Our inference</b> (no source states it): a missed window moves the landing about one synodic month (29.5 days), to the same time of the lunar day; south-polar lighting also shifts with the seasons (2 to 3 weeks a year, LPSC 2026), so a real planner re-picks the hour each month (the card’s line under the strip does that search). These tables judge each window with the card’s rules.</p>';
    h += '<h3>IM-1 Odysseus at Malapert A (retrospective)</h3><p class="note">' + esc(im.mission.need) + '. The January window was missed; February was flown (landed 22 Feb 2024 23:23 UTC). The January landing below (24 Jan 10:00) is <b>our model</b> (one synodic month before the flown landing), not a published date: at that time of the lunar day the site is a clear yes with the same one day of margin, and the lander would have met a lunar night of 422 hours, as it did (431 h). With the roughly ten days in NASA’s press kit (240 hours) the flown window would be No: terrain leaves 208 sunlit hours.</p>' +
      table(im, function (x) { return x.k === -1 ? 'January (missed; modelled date)' : (x.k === 0 ? 'February (flown)' : '+' + x.k + ' month' + (x.k > 1 ? 's' : '')); }, false);
    if (r.im1_january) {
      h += '<p class="note"><b>The January window IM-1 published, day by day.</b> ' + esc(r.im1_january.source) + ', so landings from 17 to 25 Jan. At 10:00 UTC each day: ' +
        r.im1_january.rows.map(function (x) { var v = VERDICT[x.verdict] || ['', x.verdict]; return esc(x.landing_utc.slice(8, 10)) + ' Jan ' + v[0] + (x.verdict === 'yes' ? ' ' + x.margin + ' d' : (x.fails_on.length ? ' (' + esc(x.fails_on.join(', ')) + ')' : '')); }).join(' · ') +
        '. So "January would also have been a Yes" holds only for a landing after local sunrise (from 21 Jan), which is what a lander aims for.</p>';
    }
    h += '<h3>VIPER on Blue Moon MK1 (prospective, late 2027)</h3><p class="note">NASA: “The rover has a targeted science window for its 100-day mission that requires a landing by late 2027” (19 Sep 2025); VIPER works “in an area west of Nobile crater” (NASA SVS 4937). <b>Assumptions, labelled:</b> ' +
      esc(vi.mission.assumptions.join('; ')) + '. The verdict uses the page’s illustrative 14-day need (240 sunlit, 100 Earth hours); the 100-day columns use the published mission length. Point: ' + vi.site.lat.toFixed(3) + ', ' + vi.site.lon.toFixed(3) + '.</p>' +
      table(vi, function (x) { return fmtDate(x.landing_utc); }, true);
    var ar = state.artemis;
    if (ar && ar.available) {
      var mat = function (blk, label) {
        var regs = ar.anchors.map(function (x) { return x.region; });
        var t = '<div class="tablewrap"><table class="data artT"><tr><th>' + esc(label) + '</th>' + regs.map(function (g) { return '<th>' + esc(g) + '</th>'; }).join('') + '<th>Regions with a Yes hour</th></tr>';
        blk.rows.forEach(function (w) {
          t += '<tr><td>' + esc(w.landing_utc.slice(0, 10)) + '</td>' + w.regions.map(function (g) {
            var b = g.best_hour;
            return b.found ? '<td class="v-yes" title="' + (g.best_site ? 'best site ' + esc(g.best_site) + ': ' : '') + 'landing ' + esc(b.landing_utc.slice(0, 16).replace('T', ' ')) + ' UTC, ' + b.slip_margin_days + ' days of margin' + (b.fragile ? ' (fragile)' : '') + (g.n_sites ? '; ' + g.sites_yes + ' of ' + g.n_sites + ' published sites have a Yes hour, ' + g.sites_yes_not_fragile + ' not fragile' : '') + '">✓ ' + b.slip_margin_days + ' d' + (b.fragile ? '*' : '') + '</td>' :
              '<td class="v-no" title="no clear-yes landing within 72 h' + (g.fails_on.length ? '; at the window it fails on ' + esc(g.fails_on.join(', ')) : '') + '">✕</td>';
          }).join('') + '<td class="num">' + w.regions_yes_within_72h + ' of ' + w.regions.length + (w.regions_yes_not_fragile !== undefined ? '<small>' + w.regions_yes_not_fragile + ' not fragile</small>' : '') + '</td></tr>';
        });
        return t + '</table></div>';
      };
      h += '<h3>Artemis III candidate regions in each window</h3><p class="note">NASA keeps nine candidate regions so that a launch date can be matched to a region (NASA, 28 Oct 2024). NASA names the regions but publishes no points, so <b>each region here is the set of published candidate landing sites of Wueller et al. 2026</b> (JGR Planets, 5 to 11 sites per region, 78 in all; CC BY 4.0), not NASA’s own sites. They replace the single best-lit point per region this table used before. A region’s cell shows its best site (point at it for the name): a clear Yes that is not fragile first, then the largest margin. A cell is ✓ when some landing within 72 hours of the window (every 6 h) is a clear Yes, with its margin; * marks a fragile margin.</p>' +
        mat(ar.opening, 'Opening example’s windows (240 / 100 h)') + mat(ar.im1, 'IM-1’s windows (168 / 100 h; January modelled)');
    }
    h += '<p class="cap">Sources, read first-hand and kept with URL and sha256 (data/reference/sources): Spaceflight Now 27 Oct 2023; Space.com Feb 2024; NASA 19 Sep 2025 (VIPER on Blue Moon MK1); NASA SVS 4937 (VIPER site); NASA 28 Oct 2024 and George et al., LPSC 2026 (Artemis III regions: sites chosen after the launch dates, several regions kept for launch-timing flexibility, surface stay about 5.75 to 6.25 days). Worst of 13 touchdown points within 100 m; station rule on; night and outage are whole runs.</p>';
    box.innerHTML = h;
    Array.prototype.forEach.call(box.querySelectorAll('[data-real]'), function (b) {
      b.addEventListener('click', function () {
        var p = b.getAttribute('data-real').split('|');
        if (p[0] === 'im1') { var i = state.selected.findIndex(function (s) { return s.id === 'im1'; }); if (i >= 0) { state.mi = i; } }
        else { addSite({ name: 'Nobile west rim (VIPER, illustrative)', lat: vi.site.lat, lon: vi.site.lon }); state.mi = state.selected.length - 1; }
        setPlan(p[1]); window.scrollTo(0, 0);
      });
    });
  }

  /* ---------- Earth contact as station visibility (slipday/contact.py) ---------- */
  var ST_COL = ['#c2410c', '#7c3aed', '#0f766e', '#d4d4d4'], ST_NAME = ['Goldstone', 'Madrid', 'Canberra', 'no station'];
  function loadContact() {
    var cfg = state.lastCfg, s = state.selected[state.mi], panel = $('contactPanel');
    if (!cfg || !s || !panel) { return; }
    panel.hidden = false; panel.scrollIntoView({ behavior: 'smooth' });
    var body = missionBody(cfg, s), key = JSON.stringify(body);
    if (state.contactKey === key && state.contact) { renderContact(); return; }
    state.contactKey = key; state.contact = null;
    $('contact').innerHTML = '<p class="note">Working out the Moon’s elevation at the three complexes for every hour…</p>';
    api('/api/stations', body).then(function (r) { if (state.contactKey === key) { state.contact = r; renderContact(); } })
      .catch(function (e) { $('contact').innerHTML = '<p class="note">' + esc(e.message) + '</p>'; });
  }
  function renderContact() {
    var r = state.contact, box = $('contact');
    if (!r) { return; }
    if (!r.available) { box.innerHTML = '<p class="note">Not available: ' + esc(r.reason || '') + '</p>'; return; }
    var wv = r.window, sp = wv.split, n = wv.hours;
    var h = '<p class="note"><b>' + esc(r.site.name) + '</b>, landing ' + esc(fmtDate(wv.start_utc)) + ', first ' + wv.window_days + ' days. The Earth’s centre is above the skyline for <b>' + sp.earth_above_skyline +
      ' of ' + n + ' hours</b>. Goldstone carries <b>' + sp.goldstone + '</b>, Madrid <b>' + sp.madrid + '</b>, Canberra <b>' + sp.canberra + '</b> (each hour credited to the complex where the Moon stands highest); ' +
      (sp.none_in_view ? '<b>' + sp.none_in_view + ' hours</b> have the Earth in view but no complex with the Moon above its limit (longest gap ' + wv.longest_gap_h + ' h).' : '<b>no hour</b> has the Earth in view without a complex.') + '</p>';
    /* one cell per hour */
    var W = NARROW ? 350 : 900, H = 46, x0 = 4, x1 = W - 4, cw = (x1 - x0) / n;
    var svg = '<svg viewBox="0 0 ' + W + ' ' + H + '" class="contactStrip" role="img" aria-label="Which station carries each hour of the landing window">';
    wv.code.forEach(function (c, i) {
      if (c < 0) { return; }
      svg += '<rect x="' + (x0 + i * cw).toFixed(2) + '" y="6" width="' + Math.max(cw, 0.8).toFixed(2) + '" height="20" fill="' + ST_COL[c] + '"/>';
    });
    for (var d = 0; d <= wv.window_days; d += (NARROW ? 7 : 2)) {
      var x = x0 + d * 24 * cw;
      svg += '<line x1="' + x.toFixed(1) + '" x2="' + x.toFixed(1) + '" y1="27" y2="31" class="axis"/><text x="' + x.toFixed(1) + '" y="42" text-anchor="' + (d === 0 ? 'start' : 'middle') + '">' + (d === 0 ? 'touchdown' : '+' + d + ' d') + '</text>';
    }
    svg += '</svg>';
    h += svg + '<p class="vLegend">' + [0, 1, 2, 3].map(function (k) { return '<span><i class="k" style="background:' + ST_COL[k] + '"></i>' + ST_NAME[k] + (k === 3 ? ' in view (Earth up)' : '') + '</span>'; }).join('') +
      '<span>blank: the Earth is behind the skyline</span></p>';
    /* the split year by year over one 18.6-year cycle */
    var rows = r.cycle.rows, CW2 = NARROW ? 350 : 900, CH2 = 170, l = 34, rr = 6, t = 8, b = 22, bw = (CW2 - l - rr) / rows.length;
    var y = function (v) { return t + (1 - v) * (CH2 - t - b); };
    var c = '<svg viewBox="0 0 ' + CW2 + ' ' + CH2 + '" class="contactCycle" role="img" aria-label="Share of Earth-in-view hours carried by each station, per year">';
    [0, 0.25, 0.5, 0.75, 1].forEach(function (v) { c += '<line x1="' + l + '" x2="' + (CW2 - rr) + '" y1="' + y(v) + '" y2="' + y(v) + '" class="gridl"/><text x="' + (l - 4) + '" y="' + (y(v) + 3.5) + '" text-anchor="end">' + Math.round(v * 100) + '%</text>'; });
    rows.forEach(function (row, i) {
      var acc = 0, xs = l + i * bw + 1;
      [row.goldstone_share, row.madrid_share, row.canberra_share, row.none_in_view_share].forEach(function (v, k) {
        c += '<rect x="' + xs.toFixed(1) + '" y="' + y(acc + v).toFixed(1) + '" width="' + (bw - 2).toFixed(1) + '" height="' + Math.max(0, y(acc) - y(acc + v)).toFixed(1) + '" fill="' + ST_COL[k] + '"><title>' + row.year + ': ' + ST_NAME[k] + ' ' + (100 * v).toFixed(1) + '%</title></rect>';
        acc += v;
      });
      if (!NARROW || i % 3 === 0) { c += '<text x="' + (xs + bw / 2 - 1).toFixed(1) + '" y="' + (CH2 - 7) + '" text-anchor="middle">' + (NARROW ? row.year : String(row.year).slice(2)) + '</text>'; }
    });
    c += '</svg>';
    var none = rows.map(function (q) { return q.none_in_view_share; }), cg = rows.map(function (q) { return q.canberra_share; });
    h += '<h3>The split over one 18.6-year cycle (' + rows[0].year + ' to ' + rows[rows.length - 1].year + ', every 2 hours)</h3>' + c +
      '<p class="note">Of the hours with the Earth above this site’s skyline, Canberra’s share moves between ' + Math.round(100 * Math.min.apply(null, cg)) + '% and ' + Math.round(100 * Math.max.apply(null, cg)) +
      '% as the Moon’s orbit swings north and south; the hours with no complex in view stay between ' + (100 * Math.min.apply(null, none)).toFixed(1) + '% and ' + (100 * Math.max.apply(null, none)).toFixed(1) + '%.</p>';
    h += '<p class="cap">Rule: ' + esc(r.rule) + ' Limit cited from the <a href="' + esc(r.mask_url) + '" target="_blank" rel="noopener">DSN Telecommunications Link Design Handbook 810-005, module 301 Rev. P</a>: “' + esc(r.mask_quote) +
      '” The transmit figure is used as one flat angle; per-antenna horizon masks are not applied. Station coordinates from its Table 5. Checked against JPL Horizons: largest difference in the Moon’s elevation ' +
      r.horizons_check.largest_diff_deg + '° over ' + r.horizons_check.rows + ' hourly rows. ' + esc(r.model) + '</p>';
    box.innerHTML = h;
  }

  /* ---------- slip-robust sites beside permanent shadow (slipday/shadowsites.py) ---------- */
  function loadShadow() {
    var cfg = state.lastCfg || settings();
    if (!cfg) { return; }
    var body = withNeed({ start: cfg.start, n_dates: Math.min(90, parseInt($('slipDates').value, 10)) }, cfg), key = JSON.stringify(body);
    if (state.shadowKey === key && state.shadow) { renderShadow(); return; }
    state.shadowKey = key;
    $('shadowSites').innerHTML = '<p class="note">Re-checking the slip-margin map at 13 touchdown points and crossing it with the LOLA permanent-shadow map; the first run for a date takes a while…</p>';
    api('/api/shadow-sites', body).then(function (r) { if (state.shadowKey === key) { state.shadow = r; renderShadow(); renderPolar(); } })
      .catch(function (e) { $('shadowSites').innerHTML = '<p class="note">Could not list the sites: ' + esc(e.message) + '</p>'; });
  }
  function renderShadow() {
    var r = state.shadow, box = $('shadowSites');
    if (!r || !box) { return; }
    if (!r.available) { box.innerHTML = '<p class="note">Not available on this installation: ' + esc(r.reason) + '.</p>'; return; }
    var c = r.counts, s1 = c.survive_a_slip_1_or_more, s5 = c.margin_5_or_more, ru = r.rule;
    var h = '<h3 id="shadowHead">' + r.qualifying + ' map points survive a slip of a day or more beside permanent shadow</h3>' +
      '<p class="note"><b>' + esc(r.note) + '</b> A point counts when all ' + r.members + ' touchdown points within ' + Math.round(r.scatter_m) + ' m keep at least one day of slip margin and at least ' + ru.area_ha +
      ' ha of permanently shadowed ground lies within ' + (ru.reach_m / 1000) + ' km. Of the ' + s1.all + ' points that survive a slip, ' + s1.beside_shadow + ' have shadow within reach; ' +
      s1.beside_shadow_but_on_it + ' of those stand on shadowed ground themselves and are listed apart. With 5 days or more: ' + s5.beside_shadow_not_on_it + '. Planned landing ' + esc(r.start_utc.slice(0, 10)) +
      ', ' + r.dates + ' landing dates; map points ' + (r.step_m) + ' m apart, shadow from 60 m pixels.</p>';
    var row = function (x, i, tag) {
      return '<tr><td class="num">' + (i + 1) + '</td><td>' + esc(fmtLatLon(x.lat, x.lon)) + '</td><td class="num">' + x.surviving_margin_days + '<small>' + x.single_point_margin_days + ' at the point alone</small></td>' +
        (r.finer ? '<td class="num">' + (x.margin_20m === null || x.margin_20m === undefined ? '-' : (x.margin_20m < 0 ? 'lost' : x.margin_20m)) + '</td>' : '') +
        '<td class="num">' + x.shadow_area_ha_within_reach + ' ha</td><td class="num">' + (x.nearest_shadow_m === null ? '-' : x.nearest_shadow_m + ' m') +
        (x.nearest_shadow_bearing_deg === null ? '' : '<small>towards ' + x.nearest_shadow_bearing_deg + '°</small>') + '</td><td><button type="button" class="add" data-shadow="' + tag + i + '">Add</button></td></tr>';
    };
    var head = '<tr><th>#</th><th>Map point</th><th>Slip margin, all 13 points (days)</th>' + (r.finer ? '<th>Same on NASA’s 20 m grid</th>' : '') + '<th>Permanent shadow within 1 km</th><th>Nearest shadowed ground</th><th></th></tr>';
    h += '<div class="tablewrap"><table class="data" id="shadowTable">' + head + r.rows.map(function (x, i) { return row(x, i, 'r'); }).join('') + '</table></div>';
    if (r.on_shadow_itself.length) {
      h += '<details class="explain"><summary>' + s1.beside_shadow_but_on_it + ' more stand on permanently shadowed ground themselves (not ranked: a 500 m map cannot tell them from the crest beside it)</summary>' +
        '<div class="tablewrap"><table class="data">' + head + r.on_shadow_itself.map(function (x, i) { return row(x, i, 'f'); }).join('') + '</table></div></details>';
    }
    h += '<p class="cap">Numbered rings on the polar map (close-up of the pole) mark the ranked points; grey rings the ones on shadow. Source: ' + esc(r.source.source_file) + ' (sha256 ' + esc(String(r.source.source_sha256).slice(0, 12)) + '…), cells that read zero.</p>';
    box.innerHTML = h;
    Array.prototype.forEach.call(box.querySelectorAll('[data-shadow]'), function (b) {
      b.addEventListener('click', function () {
        var tag = b.getAttribute('data-shadow'), list = tag.charAt(0) === 'r' ? r.rows : r.on_shadow_itself, x = list[parseInt(tag.slice(1), 10)];
        addSite({ name: 'Beside shadow ' + fmtLatLon(x.lat, x.lon), lat: x.lat, lon: x.lon });
      });
    });
  }

  /* the 3-D view lives in its own file (static/view3d.js); it is given the same site, date and blocking ground */
  function show3d() {
    var w = state.why, panel = $('view3dPanel');
    if (!panel || !window.SlipdayView3D || !w || w.error) { return; }
    if (!w.skyline) { panel.hidden = true; return; }
    panel.hidden = false;
    var marks = [];
    var add = function (tr, label) { if (tr && tr.lat !== undefined && !tr.near_field) { marks.push({ lat: tr.lat, lon: tr.lon, label: label + (tr.named && /ends the margin/.test(label) ? ', ' + tr.named.phrase : '') }); } };
    if (w.sun_hidden.length) { add(w.sun_hidden[0].terrain, 'ground the Sun goes behind'); }
    if (w.earth_hidden.length) { add(w.earth_hidden[0].terrain, 'ground the Earth goes behind'); }
    if (w.flip && w.flip.stretch) { add(w.flip.stretch.terrain, 'ground that ends the margin'); }
    var s = state.selected[state.mi];
    try {
      window.SlipdayView3D.show($('view3d'), { site: s && s.id ? { id: s.id, name: w.site.name, lat: w.site.lat, lon: w.site.lon } : { name: w.site.name, lat: w.site.lat, lon: w.site.lon },
        at: w.landing_utc, windowHours: w.window_hours, marks: marks, mastM: state.lastCfg ? state.lastCfg.opts.mast_m : 2 });
    } catch (e) { $('view3d').textContent = 'The 3-D view could not be drawn: ' + e.message; }
  }

  /* lunar against terrestrial conditions for the same days (static/contrast.js) */
  function showContrast() {
    var w = state.why, panel = $('contrastPanel'), s = state.selected[state.mi];
    if (!panel || !window.SlipdayContrast || !w || w.error || !s) { return; }
    var key = (s.id || (s.lat + ',' + s.lon)) + '|' + (state.lastCfg ? state.lastCfg.start : '');
    if (state.contrastKey === key) { return; }
    state.contrastKey = key;
    panel.hidden = false;
    var o = s.id ? { site: s.id } : { lat: s.lat, lon: s.lon, name: s.name };
    o.start = state.lastCfg.start; o.days = 60; o.mast_m = state.lastCfg.opts.mast_m; o.terrain = state.lastCfg.opts.terrain;
    try {
      var pr = window.SlipdayContrast.show($('contrast'), o);
      if (pr && pr.catch) { pr.catch(function (e) { $('contrast').textContent = 'This comparison could not be drawn: ' + e.message; }); }
    } catch (e) { $('contrast').textContent = 'This comparison could not be drawn: ' + e.message; }
  }

  /* ---------- a year of landing dates under the 60-day strip ---------- */
  function ribbonBody(cfg, s) { var b = missionBody(cfg, s); delete b.slip_days; b.days = 365; return b; }
  function loadRibbon() {
    var cfg = state.lastCfg, s = state.selected[state.mi];
    if (!cfg || !s) { return; }
    var body = ribbonBody(cfg, s), key = JSON.stringify(body);
    if (state.ribbon[key] !== undefined) { return; }
    if (Object.keys(state.ribbon).length > 12) { state.ribbon = {}; }
    state.ribbon[key] = null;
    api('/api/year-ribbon', body).then(function (r) { state.ribbon[key] = r; renderRibbon(); })
      .catch(function (e) { state.ribbon[key] = { error: e.message }; renderRibbon(); });
  }
  function monthRange(list) {
    if (!list.length) { return ''; }
    var nm = function (k) { return MONTHS[parseInt(k.slice(5, 7), 10) - 1]; };
    var idx = list.map(function (k) { return parseInt(k.slice(0, 4), 10) * 12 + parseInt(k.slice(5, 7), 10); });
    var runs = [], a = 0;
    for (var i = 1; i <= idx.length; i++) {
      if (i === idx.length || idx[i] !== idx[i - 1] + 1) { runs.push(a === i - 1 ? nm(list[a]) + ' ' + list[a].slice(0, 4) : nm(list[a]) + ' to ' + nm(list[i - 1]) + ' ' + list[i - 1].slice(0, 4)); a = i; }
    }
    return runs.join(', ');
  }
  function renderRibbon() {
    var box = $('ribbon'), cfg = state.lastCfg, s = state.selected[state.mi];
    if (!box || !cfg || !s) { return; }
    var r = state.ribbon[JSON.stringify(ribbonBody(cfg, s))];
    if (!r) { box.innerHTML = '<p class="cap">A year of landing dates: working it out…</p>'; return; }
    if (r.error) { box.innerHTML = '<p class="cap">A year of landing dates: ' + esc(r.error) + '</p>'; return; }
    var none = monthRange(r.months_without_a_yes.filter(function (k) { var m = r.months.filter(function (q) { return q.month === k; })[0]; return m && m.dates >= 10; }));
    box.innerHTML = '<p class="ribHead" title="' + esc(r.what) + '"><b>A year of landing dates:</b> ' + r.yes + ' clear yes of ' + r.days + ' (' + r.not_sure + ' not sure)' +
      (none ? '; <b>none in ' + esc(none) + '</b>' : '') + '</p>';
    var W = 730, H = 25, cw = W / r.days, svg = el('svg', { viewBox: '0 0 ' + W + ' ' + H, 'class': 'ribSvg', role: 'img', preserveAspectRatio: 'none',
      'aria-label': 'One cell per landing date for a year: ' + r.yes + ' clear yes, ' + r.not_sure + ' not sure, ' + r.no + ' no' });
    var t0 = Date.parse(r.start_utc), colour = { y: 'ribY', u: 'ribU', n: 'ribN' }, hgt = { y: 13, u: 8, n: 3 };
    for (var i = 0; i < r.days; i++) {
      var ch = r.verdicts.charAt(i);
      if (ch === '-') { continue; }
      svg.appendChild(el('rect', { x: (i * cw).toFixed(2), y: 13 - hgt[ch], width: Math.max(cw, 1).toFixed(2), height: hgt[ch], 'class': colour[ch] }));
    }
    for (i = 0; i < r.days; i++) {
      var d = new Date(t0 + i * 86400000);
      if (d.getUTCDate() === 1) {
        svg.appendChild(el('line', { x1: i * cw, x2: i * cw, y1: 0, y2: 16, 'class': 'ribTick' }));
        svg.appendChild(el('text', { x: i * cw + 2, y: 24, 'class': 'ribLab' }, MONTHS[d.getUTCMonth()] + (d.getUTCMonth() === 0 ? ' ' + d.getUTCFullYear() : '')));
      }
    }
    var names = { y: '✓ Yes', u: '? Not sure', n: '✕ No', '-': 'not computed' };
    var at = function (ev) { var b = svg.getBoundingClientRect(); return Math.max(0, Math.min(r.days - 1, Math.floor((ev.clientX - b.left) / b.width * r.days))); };
    svg.addEventListener('pointermove', function (ev) {
      var k = at(ev), dt = new Date(t0 + k * 86400000);
      showTip(ev, '<b>Land ' + dt.getUTCDate() + ' ' + MONTHS[dt.getUTCMonth()] + ' ' + dt.getUTCFullYear() + '</b>' + names[r.verdicts.charAt(k)] +
        '<br>smooth sphere: ' + (r.smooth_sphere.charAt(k) === 'y' ? 'yes' : 'no') + '<br>Click to plan for this date');
    });
    svg.addEventListener('pointerleave', hideTip);
    svg.addEventListener('click', function (ev) { hideTip(); setPlan(new Date(t0 + at(ev) * 86400000).toISOString().slice(0, 19) + 'Z'); });
    box.appendChild(svg);
  }

  /* ---------- landing circles: what the answer becomes if the landing is less precise ---------- */
  function circleBody(cfg, s) { var b = missionBody(cfg, s); delete b.scatter_m; return b; }
  function renderCircles() {
    var box = $('circles'), cfg = state.lastCfg, s = state.selected[state.mi], mis = state.missions[state.mi];
    if (!box) { return; }
    if (!cfg || !s || !mis || !mis.sure || mis.sure.points < 2) { box.innerHTML = ''; if ($('classes')) { $('classes').innerHTML = ''; } return; }   /* no card yet, or no terrain to scatter over */
    var body = circleBody(cfg, s), key = JSON.stringify(body), c = state.circles[key];
    var ask = function () {
      if (Object.keys(state.circles).length > 24) { state.circles = {}; state.classes = {}; }
      state.circles[key] = null; state.classes[key] = null;
      api('/api/landing-circles', body).then(function (r) { state.circles[key] = r; renderCircles(); })
        .catch(function (e) { state.circles[key] = { available: false, reason: e.message, busy: e.busy }; renderCircles(); });
      api('/api/lander-classes', body).then(function (r) { state.classes[key] = r; renderClasses(key); })
        .catch(function (e) { state.classes[key] = { available: false, reason: e.message, busy: e.busy }; renderClasses(key); });
      renderCircles();
    };
    renderClasses(key);
    if (c === undefined) {
      /* The default and example sites have their 93 skylines stored; any other site computes them on request,
         so a slow host is not tied up by a site somebody only clicked through. */
      var stored = s.id && (DEFAULT_SITES.indexOf(s.id) >= 0 || state.replays.some(function (x) { return x.site === s.id; }));
      if (stored) { ask(); return; }
      box.innerHTML = '<p class="cap"><button type="button" id="circleBtn">What if the landing is less precise?</button> ' +
        'Works out the chance that this plan still holds for three assumed lander classes, and the share of a 100 m, 250 m, 500 m and 1 km landing circle where it does (141 skylines; up to a minute for a new site).</p>';
      $('circleBtn').addEventListener('click', ask);
      return;
    }
    if (!c) { box.innerHTML = '<p class="cap">Working out what a less precise landing would do (up to 93 touchdown points)…</p>'; return; }
    if (!c.available) {
      box.innerHTML = '<p class="cap">Landing circles: ' + esc(c.reason || 'not available') + (c.busy ? ' <button type="button" id="circleRetry">Try again</button>' : '.') + '</p>';
      if ($('circleRetry')) { $('circleRetry').addEventListener('click', ask); }
      return;
    }
    if (!c.classes.some(function (k) { return k.resolvable; })) {
      box.innerHTML = '<p class="cap"><b>If the landing is less precise:</b> not resolvable here. Every landing circle up to 1 km is smaller than one ' +
        Math.ceil(c.grid_resolution_m) + ' m cell of the elevation grid under this site (' + esc(String(c.horizon.dem_label || '').split(';')[0]) + '), so touchdown points inside it cannot be told apart.</p>';
      return;
    }
    var h = '<p class="cHead"><b>By landing circle</b>, touchdown equally likely anywhere inside: share where the plan holds</p>';
    c.classes.forEach(function (k) {
      h += '<div class="cRow"><span class="cLab" title="' + esc(k.note || '') + '">' + esc(k.label) + '</span>';
      if (!k.resolvable) { h += '<span class="cNa">not resolvable: ' + esc(k.why) + '</span></div>'; return; }
      h += '<div class="cStrip" role="img" aria-label="' + esc(k.label + ': ' + k.planned_pct + ' percent of touchdown points pass on the planned date') + '">';
      k.share_pct.forEach(function (p, i) {
        var cls = p === null ? 'na' : (p >= 90 ? 'hi' : (p >= 50 ? 'mid' : 'lo'));
        h += '<span class="cc ' + cls + '" style="height:' + (p === null ? 8 : Math.max(8, p)) + '%" title="' + (i ? 'Slip ' + plural(i, 'day') : 'As planned') + ': ' + (p === null ? 'not computed' : p + '% of touchdown points pass') + '"></span>';
      });
      var rg = k.planned_range_pct;
      h += '</div><span class="cNum num"><b>' + (k.planned_pct === null ? 'n/a' : Math.round(k.planned_pct) + '%') + '</b> as planned' +
        (rg && rg[0] !== rg[1] ? ' <span class="rng" title="' + esc(c.range_note || '') + '">range ' + Math.round(rg[0]) + ' to ' + Math.round(rg[1]) + '</span>' :
          (k.margin_90_days >= 0 ? ' · 90%+ for ' + k.margin_90_days + ' d' : '')) + '</span></div>';
    });
    h += '<p class="cap" title="' + esc(c.assumption + ' ' + (c.range_note || '')) + '">One bar per day of slip; ' + c.points + ' touchdown points on ' + esc(String(c.horizon.dem_label || '').split(';')[0]) +
      '. A count on this grid, not a dispersion model of any lander. Ranges: 400 resamplings of the points.</p>';
    box.innerHTML = h;
  }
  /* ---------- chance by lander class: three ASSUMED Gaussian dispersions over the same touchdown points ---------- */
  function renderClasses(key) {
    var box = $('classes');
    if (!box) { return; }
    var c = state.classes[key];
    if (c === undefined) { box.innerHTML = ''; return; }
    if (!c) { box.innerHTML = '<p class="cap">Working out the chance by lander class (up to 141 touchdown points)…</p>'; return; }
    if (!c.available) { box.innerHTML = '<p class="cap">Chance by lander class: ' + esc(c.reason || 'not available') + '</p>'; return; }
    var h = '<p class="cHead"><b>If the landing is less precise:</b> chance the plan holds, by lander class <span class="mtag syn" title="' + esc(c.assumption) + '">assumed dispersions</span></p>';
    c.classes.forEach(function (k) {
      h += '<div class="cRow lRow"><span class="cLab" title="' + esc(k.basis) + '">' + esc(k.label.replace(' lander', '')) + ' <small>' +
        spread99(k) + '</small></span>';
      if (!k.resolvable) { h += '<span class="cNa">not resolvable: ' + esc(k.why) + '</span></div>'; return; }
      h += '<div class="cStrip" role="img" aria-label="' + esc(k.label + ': ' + k.planned_pct + ' percent chance on the planned date') + '">';
      k.chance_pct.forEach(function (p, i) {
        var cls = p === null ? 'na' : (p >= 90 ? 'hi' : (p >= 50 ? 'mid' : 'lo'));
        h += '<span class="cc ' + cls + '" style="height:' + (p === null ? 8 : Math.max(8, p)) + '%" title="' + (i ? 'Slip ' + plural(i, 'day') : 'As planned') + ': ' +
          (p === null ? 'not computed' : p + '% chance (range ' + k.range_lo_pct[i] + ' to ' + k.range_hi_pct[i] + ')') + '"></span>';
      });
      var rg = k.planned_range_pct;
      h += '</div><span class="cNum num"><b>' + Math.round(k.planned_pct) + '%</b> as planned' +
        (rg && rg[0] !== rg[1] ? ' <span class="rng" title="' + esc(c.range_note) + '">range ' + Math.round(rg[0]) + ' to ' + Math.round(rg[1]) + '</span>' :
          (k.margin_90_days >= 0 ? ' · 90%+ for ' + k.margin_90_days + ' d' : '')) + '</span></div>';
    });
    h += '<p class="cap" title="' + esc(c.classes.map(function (k) { return k.label + ': ' + k.basis; }).join(' ') + ' ' + c.range_note) + '">The dispersions are <b>assumptions</b>: Gaussians sized from one published figure each (' +
      c.classes.map(function (k) {
        var words = { precision: 'SLIM’s 100 m goal', clps: 'IM-2’s 250 m (820 ft) miss', wide: 'a third of Chandrayaan-3’s 4 × 2.4 km site' }[k.id] || k.figure;
        return esc(words) + ', <a href="' + esc(k.source_url) + '" target="_blank" rel="noopener" title="' + esc(k.figure + ' (' + k.source + ')') + '">' +
          esc(k.source.split(',')[0].replace(' press release', '').replace(' news release', '')) + '</a>';
      }).join('; ') + '), not a model of any named lander.</p>';
    box.innerHTML = h;
  }

  function loadReplays() {
    api('/api/replays').then(function (r) {
      state.replays = r.missions;
      var h = '<span>Try a real landing:</span>';
      r.missions.forEach(function (x) { h += '<button type="button" data-replay="' + esc(x.id) + '" title="Landed ' + esc(x.landed_utc) + '">' + esc(x.label) + '</button>'; });
      $('replays').innerHTML = h;
      $('replayNote').textContent = r.note;
      if (state.missions[state.mi]) { renderMission(); }      /* the card may already show one of these landings */
      Array.prototype.forEach.call($('replays').querySelectorAll('[data-replay]'), function (b) {
        b.addEventListener('click', function () {
          var x = state.replays.filter(function (q) { return q.id === b.getAttribute('data-replay'); })[0];
          var s = state.catalog.filter(function (q) { return q.id === x.site; })[0];
          if (!x || !s) { return; }
          var at = -1;
          state.selected.forEach(function (q, i) { if (q.id === s.id) { at = i; } });
          if (at < 0) {
            if (state.selected.length >= MAX_SITES) { state.selected.pop(); }
            state.selected.unshift({ id: s.id, name: s.name, lat: s.lat, lon: s.lon }); at = 0;
          }
          state.mi = at;
          $('needSun').value = x.need_sun_h; $('needEarth').value = x.need_earth_h; $('slipWindow').value = String(x.window_days);
          $('tdSun').checked = true; $('tdEarth').checked = true;
          state.autoNote = '';           /* each example carries its own need; the card says where the figure comes from */
          setPlan(x.landing);
        });
      });
    }).catch(function () {});
  }

  /* ---------- shareable link: the whole scenario lives in the address ---------- */
  function saveHash() {
    var cfg = state.lastCfg; if (!cfg) { return; }
    var sites = state.selected.map(function (s) { return s.id ? s.id : 'c:' + s.lat + ':' + s.lon + ':' + encodeURIComponent(s.name); }).join(',');
    var q = ['s=' + sites, 'd=' + $('start').value, 'h=' + $('mHour').value, 'sun=' + cfg.need.need_sun_h, 'earth=' + cfg.need.need_earth_h,
      'w=' + $('slipWindow').value, 'td=' + (cfg.need.sun_at_touchdown ? 1 : 0) + (cfg.need.earth_at_touchdown ? 1 : 0), 'i=' + state.mi,
      'n=' + $('slipDates').value, 'mast=' + $('mast').value, 'm=' + $('slipMetric').value, 'st=' + $('slipStat').value,
      'sc=' + $('scatter').value, 'z=' + state.zoom, 'l=' + state.layer];
    state.lastHash = '#' + q.join('&');
    try { history.replaceState(null, '', state.lastHash); } catch (e) { /* file:// or sandboxed frame */ }
  }
  function readHash() {
    var out = {};
    String(location.hash || '').replace(/^#/, '').split('&').forEach(function (kv) {
      var i = kv.indexOf('='); if (i > 0) { out[kv.slice(0, i)] = kv.slice(i + 1); }
    });
    return out;
  }
  function applyHash(h) {
    var setv = function (id, v) { if (v !== undefined && v !== '') { $(id).value = v; if ($(id).value !== v && $(id).tagName === 'SELECT') { $(id).selectedIndex = 0; } } };
    if (/^\d{4}-\d{2}-\d{2}$/.test(h.d || '')) { $('start').value = h.d; }
    setv('mHour', h.h); setv('needSun', h.sun); setv('needEarth', h.earth); setv('slipWindow', h.w); setv('slipDates', h.n);
    setv('mast', h.mast); setv('slipMetric', h.m); setv('slipStat', h.st); setv('scatter', h.sc);
    if (h.td && h.td.length === 2) { $('tdSun').checked = h.td.charAt(0) === '1'; $('tdEarth').checked = h.td.charAt(1) === '1'; }
    if (h.z === 'pole') { state.zoom = 'pole'; $('mapZoom').value = 'pole'; }
    if (h.l) { state.layer = h.l; }
    var picked = [];
    (h.s || '').split(',').forEach(function (tok) {
      if (!tok || picked.length >= MAX_SITES) { return; }
      if (tok.indexOf('c:') === 0) {
        var p = tok.split(':'), lat = parseFloat(p[1]), lon = parseFloat(p[2]);
        if (lat >= -90 && lat <= 90 && lon >= -180 && lon <= 360) {
          var nm = ''; try { nm = decodeURIComponent(p.slice(3).join(':')); } catch (e) { nm = ''; }
          picked.push({ name: nm || fmtLatLon(lat, lon), lat: lat, lon: lon });
        }
      } else {
        var s = state.catalog.filter(function (x) { return x.id === tok; })[0];
        if (s) { picked.push({ id: s.id, name: s.name, lat: s.lat, lon: s.lon }); }
      }
    });
    var mi = parseInt(h.i, 10);
    return { sites: picked, mi: isFinite(mi) ? mi : 0 };
  }

  function jumpTo(unix) {
    var d = state.data[0]; if (!d) { return; }
    var s = d.series, i = Math.round((unix - s.start_unix) / (s.step_minutes * 60));
    if (i < 0 || i > s.count - 1) { $('siteMsg').textContent = 'That date is outside the charted span; lengthen the span to see it.'; return; }
    setIndex(i);
    $('h-compare').scrollIntoView({ behavior: 'smooth' });
  }
  function slipBody(cfg) {
    return withOpts({
      sites: state.selected.map(siteRef), start: cfg.start, n_dates: parseInt($('slipDates').value, 10),
      window_days: cfg.need.window_days, scatter_m: cfg.scatter
    }, cfg);
  }
  function loadSlip() {
    var cfg = settings();
    if (!cfg) { return; }
    if (!state.selected.length) { state.slip = null; renderSlip(); return; }
    var req = state.reqId;
    api('/api/slipgrid', slipBody(cfg)).then(function (g) { if (req === state.reqId) { state.slip = g; renderSlip(); } }).catch(showError);
  }
  function compareBody(cfg) {
    return withOpts({
      sites: state.selected.map(siteRef), start: cfg.start, hours: cfg.hours, step_minutes: 60,
      at: new Date(cfg.startMs + Math.min(state.idx, cfg.hours) * 3600000).toISOString()
    }, cfg);
  }
  function download(path, body, name) {
    fetch(path, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) }).then(function (r) {
      if (!r.ok) { throw new Error('export failed (' + r.status + ')'); }
      return r.blob();
    }).then(function (blob) {
      var a = document.createElement('a');
      a.href = URL.createObjectURL(blob); a.download = name;
      document.body.appendChild(a); a.click();
      setTimeout(function () { URL.revokeObjectURL(a.href); a.remove(); }, 500);
    }).catch(showError);
  }

  /* ---------- validity ---------- */
  function table(cols, rows) {
    var h = '<tr>' + cols.map(function (c) { return '<th>' + esc(c) + '</th>'; }).join('') + '</tr>';
    rows.forEach(function (r) {
      h += '<tr>' + r.map(function (c, i) { return '<td' + (i > 0 && /^[-+0-9.]/.test(String(c)) ? ' class="num"' : '') + '>' + esc(c === null ? 'n/a' : c) + '</td>'; }).join('') + '</tr>';
    });
    return '<div class="tablewrap"><table class="data">' + h + '</table></div>';
  }
  function loadValidity() {
    api('/api/terrain/validation').then(function (v) {
      var box = $('terrainValid');
      if (!v.available) {
        box.innerHTML = '<h3>Terrain model against published results</h3><p class="note">Not available on this installation: ' + esc(v.reason || '') + '.</p>';
        return;
      }
      var html = '';
      if (v.headline) {
        $('validTiles').insertAdjacentHTML('afterbegin', v.headline.map(function (t) {
          return tile(t.k, t.v, esc(t.s || ''), t.tag ? '<span class="mtag ' + (t.pending ? 'syn' : 'ter') + '">' + esc(t.tag) + '</span>' : '');
        }).join(''));
      }
      if (!v.same_grid && v.ran_on) {
        html += '<p class="note warnnote">These checks were run on ' + esc(v.ran_on) + '. This installation computes with ' + esc(v.installed || 'no terrain') +
          ', so its numbers are not the validated ones; the resolution table below shows how far a coarser grid moves them.</p>';
      }
      (v.tables || []).forEach(function (t) {
        var body = (t.note ? '<p class="note">' + esc(t.note) + '</p>' : '') + table(t.columns, t.rows);
        html += t.collapsed ? '<details class="vt"><summary>' + esc(t.title) + '</summary>' + body + '</details>'
          : '<h3>' + esc(t.title) + '</h3>' + body;
      });
      box.innerHTML = html;
    }).catch(function () {});
    api('/api/validation').then(function (v) {
      var html = tile('Sun and Earth direction: largest difference from JPL Horizons', v.max_abs_el_deg === null ? 'n/a' : v.max_abs_el_deg.toExponential(1) + '°',
        v.rows + ' reference rows, 3 sites. This checks the ephemeris and frame only, not terrain.', '<span class="mtag geo">geometry (JPL DE421)</span>');
      $('validTiles').insertAdjacentHTML('beforeend', html);
      var rows = '<tr><th>Reference table</th><th>Orientation model</th><th>Rows</th><th>Max |elevation diff| (deg)</th><th>Max |azimuth diff| (deg)</th></tr>';
      v.results.forEach(function (r) {
        rows += '<tr><td>' + esc(r.fixture) + '</td><td>' + esc(r.orientation) + '</td><td class="num">' + r.rows + '</td><td class="num">' +
          r.max_abs_el_deg.toFixed(6) + '</td><td class="num">' + r.max_abs_az_deg.toFixed(6) + '</td></tr>';
      });
      $('validTable').innerHTML = rows;
    }).catch(showError);
    api('/api/finer-grid').then(function (f) {
      if (!f.available) { return; }
      var e = f.entries[0], a = e.used, b = e.fine, word = { yes: 'Yes', 'not sure': 'Not sure', no: 'No' };
      var circ = function (x) { return x.landing_circles_planned_pct['within 250 m'][0]; };
      var op = f.opening_example, ch = op && op.chosen && op.tried.filter(function (c) { return c.rank === op.chosen.rank; })[0];
      if (ch) {
        $('validTiles').insertAdjacentHTML('beforeend', tile('The opening example on both grids (20 m checked separately; the page computes on 80 m)',
          word[ch.card_20m.verdict] + ' on both', 'The first of the map’s ' + op.candidates +
          ' scatter-robust points (5 or more days of margin at all 13 touchdown points) whose full card is a clear Yes on both grids; ' + op.tried.length +
          ' candidate' + (op.tried.length === 1 ? '' : 's') + ' tried. 80 m: ' + word[ch.card_80m.verdict] + ', ' + ch.card_80m.points_passing_by_day[0] + ' of ' + ch.card_80m.points + ', ' +
          ch.card_80m.slip_margin_days + ' days of margin. 20 m: ' + word[ch.card_20m.verdict] + ', ' + ch.card_20m.points_passing_by_day[0] + ' of ' + ch.card_20m.points + ', ' +
          ch.card_20m.slip_margin_days + ' days. Rule: the card’s own (half the Sun’s disc, the Earth’s centre). One site, one landing date.',
          '<span class="mtag syn">terrain (' + esc(f.fine_grid.split(';')[0]) + '), checked separately</span>'));
      }
      $('validTiles').insertAdjacentHTML('beforeend', tile('Why resolution matters: the Shackleton connecting ridge on NASA’s 20 m grid (checked separately; the page computes on 80 m)',
        word[b.verdict] + ': ' + b.points_passing_by_day[0] + ' of ' + b.points,
        esc(e.text) + ' Clear-yes landing dates in 365: ' + b.clear_yes_dates_of_365 + ' on 20 m, ' + a.clear_yes_dates_of_365 + ' on 80 m. Within a 250 m circle the plan holds at ' +
        circ(b) + '% on 20 m and ' + circ(a) + '% on 80 m. Longest darkness at the point: ' + b.longest_darkness_h.at_the_point + ' h on 20 m, ' +
        a.longest_darkness_h.at_the_point + ' h on 80 m (published for this ridge: 112 h). Rule: the card’s own (half the Sun’s disc, the Earth’s centre). This is not what the page serves: every other number here is computed on 80 m.',
        '<span class="mtag syn">terrain (' + esc(f.fine_grid.split(';')[0]) + '), checked separately</span>'));
    }).catch(function () {});
    api('/api/hindcast').then(function (h) {
      $('hindNote').textContent = h.horizon + ' A positive difference means the prediction is later than the report. ' + h.size_rule;
      var rows = '<tr><th>Mission</th><th>Reported event</th><th>Reported (UTC)</th><th>Horizon model</th><th>Predicted (UTC)</th><th>Predicted minus reported</th><th>Size of the difference</th></tr>';
      h.missions.forEach(function (m) {
        rows += '<tr><td>' + esc(m.mission) + '<small>' + fmtLatLon(m.site.lat, m.site.lon) + '</small></td><td>Landing<small>Smooth-sphere sunrise before it: ' +
          esc(m.predicted.center.sunrise_before || 'n/a') + ', ' + m.hours_from_sunrise_to_landing + ' h earlier. Sun ' + m.sun_el_at_landing +
          '° and Earth ' + m.earth_el_at_landing + '° at touchdown' + (m.terrain ? '; terrain skyline under the Sun ' + m.sun_horizon_at_landing + '°' : '') +
          '.</small></td><td class="num">' + esc(m.landing_utc) + '</td><td></td><td></td><td></td><td></td></tr>';
        m.checks.forEach(function (c) {
          var names = Object.keys(c.models);
          names.forEach(function (name, k) {
            var p = c.models[name], hz = name === 'terrain' ? m.terrain : { kind: 'smooth-sphere' };
            rows += '<tr><td></td><td>' + (k === 0 ? esc(c.label) + '<small>' + esc(c.note) + (c.verified ? '' : ' Not confirmed.') + '</small>' : '') + '</td><td class="num">' +
              (k === 0 ? esc(c.reported_utc) : '') + '</td><td>' + tagHtml(hz) + '</td><td class="num">' + esc(p.predicted_utc || 'n/a') +
              '<small>' + esc(c.compare_to.replace(/_/g, ' ')) + '</small></td><td class="num">' +
              (p.predicted_minus_reported_h === null ? 'n/a' : (p.predicted_minus_reported_h > 0 ? '+' : '') + p.predicted_minus_reported_h + ' h') +
              '</td><td>' + esc(p.size) + '</td></tr>';
          });
        });
      });
      $('hindTable').innerHTML = rows;
    }).catch(showError);
  }
  function liveCheck() {
    var s = state.selected[0], cfg = settings(), msg = $('liveMsg');
    if (!s || !cfg) { msg.textContent = 'Add a site and a date first.'; return; }
    msg.textContent = 'Asking JPL Horizons…';
    var stop = new Date(cfg.startMs + 10 * 86400000).toISOString();
    var q = 'start=' + encodeURIComponent(cfg.start) + '&stop=' + encodeURIComponent(stop) + (s.id ? '&site=' + encodeURIComponent(s.id) : '&lat=' + s.lat + '&lon=' + s.lon);
    api('/api/horizons/check?' + q).then(function (r) {
      msg.textContent = r.results.map(function (x) {
        return x.target + ': ' + x.rows + ' rows, max elevation difference ' + x.max_abs_el_deg.toExponential(1) + '°, azimuth ' + x.max_abs_az_deg.toExponential(1) + '°';
      }).join(' · ');
    }).catch(function (e) { msg.textContent = 'Live check unavailable: ' + e.message; });
  }

  /* ---------- tooltip, errors, wiring ---------- */
  function showTip(ev, html) {
    var t = $('tip');
    t.innerHTML = html; t.hidden = false;
    var x = ev.clientX + 14, y = ev.clientY + 14;
    if (x + 270 > window.innerWidth) { x = ev.clientX - 270; }
    if (y + 170 > window.innerHeight) { y = ev.clientY - 170; }
    t.style.left = Math.max(4, x) + 'px'; t.style.top = Math.max(4, y) + 'px';
  }
  function hideTip() { $('tip').hidden = true; }
  function showError(e) { $('siteMsg').textContent = 'Something went wrong: ' + e.message; }

  function setBadge(t, cfg) {
    var b = $('horizonBadge');
    state.terrain = t;
    if (t && t.available && cfg.opts.terrain) {
      var first = t.dems[0];
      b.className = 'badge ' + (t.synthetic ? 'syn' : 'real');
      b.textContent = t.synthetic ? 'SYNTHETIC TEST TERRAIN (not lunar data)' :
        'Real Moon terrain: NASA LOLA laser heights, one every ' + Math.round(first.resolution_m || 80) + ' m (' + first.label.replace(/^LOLA, /, '') + ')';
      b.title = t.dems.map(function (d) { return d.label + ': ' + d.provenance; }).join('\n');
      $('footText').textContent = 'Sun and Earth directions: JPL DE421 ephemeris and lunar librations, Mean Earth frame, light-time and aberration applied; no refraction, because there is no atmosphere. ' +
        'Terrain skyline: ray-cast over the curved Moon from ' + t.dems.map(function (d) { return d.product + ' (' + d.label + ')'; }).join(', ') +
        '. Every figure is tagged with the horizon model it used.';
    } else {
      b.className = 'badge';
      b.textContent = 'Smooth-sphere horizon only: ' + (t && t.available ? 'terrain switched off' : 'no terrain data installed');
      b.title = 'Near the poles, real ridges and crater rims change sunrise and sunset by days. Treat polar results with care.';
    }
  }
  function refreshAll() {
    renderChips(); renderMap(); renderPolar();
    var cfg = settings();
    if (!cfg) { return; }
    $('siteMsg').textContent = '';
    state.lastCfg = cfg;
    var req = ++state.reqId;
    saveHash();
    renderRobust();
    if (!state.selected.length) { state.data = []; state.missions = []; renderCards(); renderMission(); loadSlip(); loadPairs(); return; }
    if (state.mi >= state.selected.length) { state.mi = 0; }
    loadMissions();
    loadSlip();
    if (!state.autoPlan) { loadSlipMap(); }
    api('/api/compare', compareBody(cfg)).then(function (res) {
      if (req !== state.reqId) { return; }
      state.data = res.sites;
      setBadge(res.terrain, cfg);
      var n = state.data[0].series.count;
      $('scrub').max = n - 1;
      if (state.idx > n - 1) { state.idx = 0; }
      $('scrub').value = state.idx;
      renderCards();
      loadYear();
      loadPairs();
    }).catch(showError);
  }
  function togglePlay() {
    var b = $('play');
    if (state.playing) { clearInterval(state.playing); state.playing = null; b.textContent = 'Play'; b.setAttribute('aria-pressed', 'false'); return; }
    b.textContent = 'Pause'; b.setAttribute('aria-pressed', 'true');
    state.playing = setInterval(function () {
      var n = state.data.length ? state.data[0].series.count : 1;
      setIndex((state.idx + 6) % n);
    }, 80);
  }
  /* ---------- how many of NASA's nine regions must stay open (slipday/regions.py; an addition, nothing depends on it) ---------- */
  function loadRegions() {
    var box = $('regions');
    if (!box) { return; }
    if (state.regions) { renderRegions(); return; }
    box.innerHTML = '<p class="note">Loading…</p>';
    api('/api/region-availability').then(function (r) { state.regions = r; renderRegions(); })
      .catch(function (e) { box.innerHTML = '<p class="note">' + esc(e.message) + '</p>'; });
  }
  function pct(x) { return (Math.round(x * 1000) / 10).toFixed(1).replace(/\.0$/, '') + '%'; }
  function renderRegions() {
    var r = state.regions, box = $('regions');
    if (!r) { return; }
    if (!r.available) { box.innerHTML = '<p class="note">' + esc(r.reason) + '</p>'; return; }
    var vk = state.regionsVariant || 'main', v = r[vk], ru = r.rule;
    var h = '<p class="note"><b>The question.</b> NASA: “' + esc(r.nasa_quote) + '” (LPSC 2026 abstract, NTRS 20250011660). ' +
      'Here: for every landing time from ' + esc(ru.first.slice(0, 10)) + ' to ' + esc(ru.last.slice(0, 10)) + ', every ' + ru.step_hours + ' hours (' + ru.n_times.toLocaleString('en-GB') + ' times), ' +
      'each of the 78 published candidate landing sites in the nine regions (Wueller et al. 2026) gets the card’s check: 13 touchdown points within 100 m, the coarser grid and the near-field sampling. ' +
      'Stay ' + ru.stay_days + ' days (' + ru.stay_hours + ' h, the top of NASA’s “approximately 5.75 to 6.25 days”); the Sun up for the whole stay; ' +
      (vk === 'main' ? 'at least ' + ru.need_earth_h + ' hours of Earth contact; ' : '<b>no Earth-contact need (sunlight only)</b>; ') +
      'the Sun and the Earth in view at touchdown. A region is open when at least one of its sites is a clear Yes that is not fragile. ' +
      'Fragile Yes results (the Sun’s centre within 0.27° of the skyline at a touchdown point during the stay, or the Earth’s at touchdown) are counted apart and never as open. On the 80 m grid; finer grids give fewer opportunities.</p>';
    h += '<p class="regVar"><label><input type="radio" name="regVar" value="main"' + (vk === 'main' ? ' checked' : '') + '> with the Earth need</label> ' +
      '<label><input type="radio" name="regVar" value="sun_only"' + (vk === 'sun_only' ? ' checked' : '') + '> sunlight only (NASA calls Earth visibility a preference)</label></p>';
    h += '<div class="regCal"><canvas id="regCanvas" aria-label="Calendar of the nine regions, 2027 to 2030: green where a region is open, amber where it has only fragile Yes sites"></canvas>' +
      '<p class="cap" id="regAt">Point at the calendar to read a date.</p>' +
      '<p class="cap"><span class="regKey" style="background:var(--good)"></span> open (darker: more of its sites) · <span class="regKey" style="background:var(--warn)"></span> only fragile Yes sites, not counted · blank: closed. Rows: share of landing times each region is open.</p></div>';
    var other = r[vk === 'main' ? 'sun_only' : 'main'], oname = vk === 'main' ? 'Sunlight only' : 'With the Earth need';
    var allBest = v.curve.every(function (c) { return c.best_coverage <= c.coverage + 1e-9; });
    var last = v.curve[v.curve.length - 1], yr1 = Object.keys(v.curve[0].by_year).map(function (y) { return v.curve[0].by_year[y]; });
    h += '<h3>How much of the time the best 1, 2, 3 … 9 regions cover</h3>' +
      '<p class="note">The regions are added one at a time: first the region open most often, then each time the one that adds the most landing times not yet covered' +
      (allBest ? '. Trying every set of the same size gives the same share at every size.' : '.') +
      ' The shares count landing times every ' + ru.step_hours + ' hours, not real launch opportunities: launch windows and the timing of the orbit the lander leaves from are not modelled.</p>' +
      '<div class="tablewrap"><table class="data regT"><tr><th>Regions kept</th><th>Added</th><th>Share of landing times open</th><th>' + oname + '</th></tr>';
    v.curve.forEach(function (c, k) {
      h += '<tr><td class="num">' + c.k + '</td><td>' + esc(c.added) + '</td><td class="num"><b>' + pct(c.coverage) + '</b></td><td class="num">' + pct(other.curve[k].coverage) + '</td></tr>';
    });
    h += '</table></div><p class="note">This panel covers 2027 to 2030. The yearly atlas below uses the same 78 sites and the same check for 2027 to 2035; over those nine years its shares come out about a point lower (27, 36, 39 and 43 %), and for 2027 to 2030 the two agree exactly. ' + (vk === 'main'
      ? 'With all nine regions the share stops at ' + pct(last.coverage) + '. That ceiling is set by the 100-hour Earth-contact need, an illustrative figure: with sunlight only it is ' + pct(other.curve[other.curve.length - 1].coverage) + '.'
      : 'With sunlight only, all nine regions give ' + pct(last.coverage) + '; with the illustrative 100-hour Earth-contact need, ' + pct(other.curve[other.curve.length - 1].coverage) + '.') +
      ' The best region alone, year by year: ' + pct(Math.min.apply(null, yr1)) + ' to ' + pct(Math.max.apply(null, yr1)) + '.</p>';
    var dr = r.drift;
    if (dr) {
      var same = dr.years.filter(function (y) { return y.midsummer_first === y.paper_first && y.midsummer_last === y.paper_last; }).length;
      h += '<h3>The good season comes earlier each year</h3><p class="note">The day the Sun stands highest over the south pole (the subsolar point furthest south), from our ephemeris: ' +
        dr.years.map(function (y) { return esc(fmtDay(Date.parse(y.lowest_on + 'T00:00:00Z') / 1000)) + ' ' + y.year; }).join(', ') +
        '. That is ' + dr.mean_shift_per_year_days + ' days earlier each year on average; single years jump because the Moon’s monthly wobble moves the day. The expected figure is ' + dr.expected_shift_days +
        ' days: the Moon’s seasons follow the 346.6-day eclipse year, not the calendar year. Midsummer (the subsolar point 1.5° S or further south) from our ephemeris matches Wueller et al.’s Table 2 to the day in ' +
        same + ' of ' + dr.years.length + ' years (' + dr.years[0].year + ' to ' + dr.years[dr.years.length - 1].year + '). ' +
        'The yearly atlas below reads the shift from its own landing times, 2027 to 2035, and gets about 18 days (18.1 with the Earth need, 18.65 with sunlight only); the figures differ by method, and all are close to the 18.6 expected.</p>';
    }
    var cc = r.cross_check;
    if (cc) {
      var big = 0, all = 0, near = 0, longer = 0;
      cc.rows.forEach(function (x) { Object.keys(cc.summary).forEach(function (y) { var d = x[y].ours - x[y].paper; all++; if (Math.abs(d) <= 1) { near++; } if (Math.abs(d) > 3) { big++; if (d > 0) { longer++; } } }); });
      var frac = function (a, b) { var f = a / b; return f > 0.6 && f < 0.72 ? 'about two in three' : f > 0.25 && f < 0.35 ? 'about three in ten' : Math.round(f * 100) + ' %'; };
      h += '<h3>Cross-check against the paper’s sunlight figures</h3><p class="note">' + esc(cc.what) + '. Of ' + all + ' comparisons (' + cc.rows.length + ' sites, ' + Object.keys(cc.summary).length + ' midsummers), ' +
        frac(near, all) + ' agree within a day (' + near + ') and ' + frac(big, all) + ' differ by more than 3 days (' + big + '), nearly always with our run the longer (' + longer + ' of ' + big + '). Our terrain model (80 m) is coarser than the paper’s (60 m). ' +
        'The large differences come in clusters by region and year, and we cannot tell from here which model is right there; where ours is longer, the availability above may be too high.</p>' +
        '<div class="tablewrap"><table class="data regT"><tr><th>Midsummer</th><th>Sites</th><th>Within 1 day</th><th>We find over 1 day more</th><th>We find over 1 day less</th><th>Disagree on the paper’s 10-day mark</th></tr>';
      Object.keys(cc.summary).forEach(function (y) {
        var s = cc.summary[y];
        h += '<tr><td>' + y + '</td><td class="num">' + s.sites + '</td><td class="num">' + s.within_1_day + '</td><td class="num">' + s.ours_longer + '</td><td class="num">' + s.ours_shorter + '</td><td class="num">' + s.disagree_on_10 + '</td></tr>';
      });
      h += '</table></div>';
    }
    if (r.sample_check) {
      h += '<p class="cap">Check of the shortcut used for speed: ' + r.sample_check.agree + ' of ' + r.sample_check.pairs + ' sampled site and time pairs give the same answer when judged one at a time with the card itself.</p>';
    }
    h += '<p class="cap">Sites: ' + esc(r.citation) + '. Computed by scripts/region_availability.py; not live for other plans.</p>';
    box.innerHTML = h;
    Array.prototype.forEach.call(box.querySelectorAll('input[name=regVar]'), function (el) {
      el.addEventListener('change', function () { state.regionsVariant = el.value; renderRegions(); });
    });
    drawRegions();
  }
  function drawRegions() {
    var r = state.regions, cv = $('regCanvas');
    if (!r || !cv) { return; }
    var v = r[state.regionsVariant || 'main'], regs = v.regions;
    var W = Math.max(300, cv.parentNode.clientWidth), narrow = W < 600, LW = narrow ? 92 : 190, top = 16, RH = narrow ? 15 : 17;
    var H = top + RH * regs.length + 4, dpr = window.devicePixelRatio || 1;
    cv.width = W * dpr; cv.height = H * dpr; cv.style.width = W + 'px'; cv.style.height = H + 'px';
    var g = cv.getContext('2d'); g.setTransform(dpr, 0, 0, dpr, 0, 0);
    var css = getComputedStyle(document.documentElement);
    var col = function (n, d) { return (css.getPropertyValue(n) || d).trim(); };
    var good = col('--good', '#0ca30c'), warn = col('--warn', '#fab219'), ink = col('--text2', '#444'), line = col('--line', '#ddd'), bg = col('--surface', '#fcfcfb');
    g.fillStyle = bg; g.fillRect(0, 0, W, H);
    var n = r.n_times, PW = W - LW - 2, t0 = Date.parse(r.first_time), step = r.step_hours * 3600000;
    g.font = '12px system-ui, sans-serif'; g.textBaseline = 'middle';
    regs.forEach(function (rg, i) {
      var rob = rg.robust_sites, fr = rg.fragile_sites, y = top + i * RH;
      g.fillStyle = ink; g.textAlign = 'left';
      g.fillText((narrow ? rg.code : rg.region) + ' ' + pct(rg.share_open), 2, y + RH / 2);
      g.fillStyle = line; g.fillRect(LW, y + RH - 1, PW, 1);
      for (var px = 0; px < PW; px++) {
        var a = Math.floor(px * n / PW), b = Math.max(a + 1, Math.floor((px + 1) * n / PW)), op = 0, fo = 0, ns = 0;
        for (var j = a; j < b; j++) {
          var k = parseInt(rob.charAt(j), 36);
          if (k > 0) { op++; ns += k; } else if (parseInt(fr.charAt(j), 36) > 0) { fo++; }
        }
        if (op) { g.globalAlpha = (0.35 + 0.65 * Math.min(1, (ns / op) / Math.max(1, rg.n_sites))) * (0.4 + 0.6 * op / (b - a)); g.fillStyle = good; g.fillRect(LW + px, y + 1, 1, RH - 3); }
        else if (fo) { g.globalAlpha = 0.85; g.fillStyle = warn; g.fillRect(LW + px, y + 1, 1, RH - 3); }
        g.globalAlpha = 1;
      }
    });
    g.fillStyle = ink; g.textAlign = 'left';
    var y0 = new Date(t0).getUTCFullYear();
    for (var yy = y0; yy <= y0 + 4; yy++) {
      var x = LW + (Date.UTC(yy, 0, 1) - t0) / step * PW / n;
      if (x < LW - 1 || x > W) { continue; }
      g.fillStyle = ink; g.fillRect(x, top - 4, 1, H - top + 4);
      if (yy < y0 + 4) { g.fillText(String(yy), x + 3, 7); }
      for (var mo = 1; mo < 12; mo++) {
        var xm = LW + (Date.UTC(yy, mo, 1) - t0) / step * PW / n;
        if (xm < W) { g.fillStyle = line; g.fillRect(xm, top - 2, 1, 3); }
      }
    }
    cv.onmousemove = function (ev) {
      var rc = cv.getBoundingClientRect(), px = ev.clientX - rc.left - LW;
      if (px < 0 || px >= PW) { return; }
      var j = Math.floor(px * n / PW), when = new Date(t0 + j * step).toISOString();
      var open = regs.filter(function (rg) { return parseInt(rg.robust_sites.charAt(j), 36) > 0; }).map(function (rg) { return rg.region + ' (' + parseInt(rg.robust_sites.charAt(j), 36) + ' of ' + rg.n_sites + ')'; });
      var fo = regs.filter(function (rg) { return parseInt(rg.robust_sites.charAt(j), 36) === 0 && parseInt(rg.fragile_sites.charAt(j), 36) > 0; }).map(function (rg) { return rg.region; });
      $('regAt').textContent = when.slice(0, 10) + ' ' + when.slice(11, 16) + ' UTC: ' + (open.length ? 'open: ' + open.join(', ') : 'no region open') + (fo.length ? '; only fragile: ' + fo.join(', ') : '') + '.';
    };
  }
  function init() {
    var hours = '';
    for (var hh = 0; hh < 24; hh++) { hours += '<option value="' + hh + '">' + ('0' + hh).slice(-2) + ':00</option>'; }
    $('mHour').innerHTML = hours;
    $('start').value = OPENING.date;            /* a first visit opens on the worked example; a link carries its own date */
    $('addSite').addEventListener('click', function () {
      var s = state.catalog.filter(function (x) { return x.id === $('sitePick').value; })[0];
      if (s) { addSite({ id: s.id, name: s.name, lat: s.lat, lon: s.lon }); }
    });
    $('addCustom').addEventListener('click', function () {
      var raw = parseFloat($('cLat').value), lon = parseFloat($('cLon').value), lat = -Math.abs(raw);
      if (!(raw >= -90 && raw <= 90) || !(lon >= -180 && lon <= 360)) {
        $('siteMsg').textContent = 'Enter a latitude from 0 to 90 (degrees south) and an east longitude from -180 to 360.'; return;
      }
      if (lon > 180) { lon -= 360; }
      addSite({ name: $('cName').value.trim() || fmtLatLon(lat, lon), lat: lat, lon: lon });
    });
    ['start', 'mHour', 'needSun', 'needEarth', 'slipWindow', 'tdSun', 'tdEarth', 'slipDates', 'scatter', 'span', 'mask', 'minSun', 'minEarth', 'mast', 'sunRule',
      'earthMargin', 'useTerrain', 'earthStations'].forEach(function (id) {
      $(id).addEventListener('change', function () { state.autoNote = ''; refreshAll(); });
    });
    $('mSite').addEventListener('change', function () {
      var v = $('mSite').value;
      if (v === 'custom') { $('mCoords').hidden = false; $('mLat').focus(); $('mSite').value = String(state.mi); return; }
      if (v.indexOf('cat:') === 0) {
        var c = state.catalog.filter(function (x) { return x.id === v.slice(4); })[0];
        if (c) { addSite({ id: c.id, name: c.name, lat: c.lat, lon: c.lon }); }
        return;
      }
      state.mi = parseInt(v, 10) || 0; renderMission(); renderSlip(); renderPolar(); saveHash();
    });
    /* your own coordinates on the card: latitude in degrees south (a minus sign is accepted and read the same way) */
    var southLat = function (inp, warnEl) {
      var raw = parseFloat(inp.value);
      if (!(raw >= -90 && raw <= 90)) { return null; }
      warnEl.textContent = raw < 0 ? 'Read as ' + Math.abs(raw) + '° south: Slipday covers the south pole only.' :
        (Math.abs(raw) < 60 ? 'That is far from the pole: no terrain data covers it, so the answer uses a smooth Moon.' : '');
      return -Math.abs(raw);
    };
    $('mUse').addEventListener('click', function () {
      var lat = southLat($('mLat'), $('mLatWarn')), lon = parseFloat($('mLon').value);
      if (lat === null || !(lon >= -180 && lon <= 360)) { $('mLatWarn').textContent = 'Enter a latitude from 0 to 90 (degrees south) and an east longitude from -180 to 360.'; return; }
      if (lon > 180) { lon -= 360; }
      addSite({ name: 'Your site ' + fmtLatLon(lat, lon), lat: lat, lon: lon });
    });
    /* landing scatter on the card, kept in step with the same setting in the rules */
    $('mScatter').value = $('scatter').value;
    $('mScatter').addEventListener('change', function () { $('scatter').value = $('mScatter').value; $('scatter').dispatchEvent(new Event('change')); });
    $('scatter').addEventListener('change', function () { $('mScatter').value = $('scatter').value; });
    /* launch slipped by N days: the same as clicking day N on the strip; the plan and its windows stay */
    $('mSlip').addEventListener('change', function () {
      var m = state.missions[state.mi], n = Math.max(0, Math.min(parseInt($('mSlip').value, 10) || 0, m ? m.days.length - 1 : 59));
      $('mSlip').value = String(n);
      if (m) { selectWhyDay(n); }
    });
    /* the sticky jump bar: open what a link points at */
    Array.prototype.forEach.call(document.querySelectorAll('#jumpBar a[data-open]'), function (a) {
      a.addEventListener('click', function () {
        var k = a.getAttribute('data-open');
        if (k === 'real') { loadReal(); }
        if (k === '3d') { var p3 = $('view3dPanel'); if (p3) { p3.hidden = false; } }
        if (k === 'fold') { var d = document.querySelector(a.getAttribute('href')); if (d) { d.open = true; } }
      });
    });
    /* opening a fold redraws what was laid out while it was closed */
    Array.prototype.forEach.call(document.querySelectorAll('details.fold'), function (d) {
      d.addEventListener('toggle', function () { if (d.open) { window.dispatchEvent(new Event('resize')); } });
    });
    $('slipMetric').addEventListener('change', function () { renderSlip(); saveHash(); });
    $('slipStat').addEventListener('change', function () { renderSlip(); saveHash(); });
    $('mapZoom').addEventListener('change', function () { state.zoom = $('mapZoom').value; loadMap(); saveHash(); });
    $('mapLayer').addEventListener('change', function () {
      state.layer = $('mapLayer').value;
      if (SLIP_LAYERS[state.layer] && state.zoom !== 'pole') { state.zoom = 'pole'; $('mapZoom').value = 'pole'; loadMap(); }
      loadSlipMap(); renderPolar(); saveHash();
    });
    $('mapScatter').addEventListener('change', function () { state.mapScatter = $('mapScatter').checked; loadSlipMap(); renderPolar(); });
    $('mapPsr').addEventListener('change', function () { state.mapPsr = $('mapPsr').checked; renderPolar(); });
    $('shadowBtn').addEventListener('click', loadShadow);
    $('copyLink').addEventListener('click', function () {
      saveHash();
      var b = $('copyLink'), done = function (ok) { b.textContent = ok ? 'Link copied' : 'Copy it from the address bar'; setTimeout(function () { b.textContent = 'Copy link to this scenario'; }, 2000); };
      if (navigator.clipboard && navigator.clipboard.writeText) { navigator.clipboard.writeText(location.href).then(function () { done(true); }, function () { done(false); }); } else { done(false); }
    });
    if (NARROW && $('validMore')) { $('validMore').open = false; }      /* a phone gets the tiles; the tables are one tap away */
    $('fitEach').addEventListener('change', renderCards);
    $('scrub').addEventListener('input', function () { setIndex(parseInt($('scrub').value, 10)); });
    $('play').addEventListener('click', togglePlay);
    $('liveCheck').addEventListener('click', liveCheck);
    api('/api/health').then(function (h) {
      if (h && h.horizons_crosscheck_enabled === false) {
        $('liveCheck').hidden = true;
        $('liveMsg').textContent = 'The live check against JPL Horizons is switched off on this server; the stored check above uses tables downloaded from JPL.';
      }
    }).catch(function () {});
    $('robustBtn').addEventListener('click', loadRobust);
    $('csvSlip').addEventListener('click', function () { var c = settings(); if (c && state.selected.length) { download('/api/export/slipgrid.csv', slipBody(c), 'slipday_slip_grid.csv'); } });
    $('csvCompare').addEventListener('click', function () { var c = settings(); if (c && state.selected.length) { download('/api/export/compare.csv', compareBody(c), 'slipday_comparison.csv'); } });
    $('csvSeries').addEventListener('click', function () { var c = settings(); if (c && state.selected.length) { download('/api/export/series.csv', compareBody(c), 'slipday_series.csv'); } });
    api('/api/sites').then(function (r) {
      state.catalog = r.sites;
      renderPicker();
      var fromLink = applyHash(readHash());
      if (fromLink.sites.length) {
        state.selected = fromLink.sites; state.mi = Math.min(fromLink.mi, fromLink.sites.length - 1);
      } else {
        state.autoPlan = true; state.firstVisit = true;
        DEFAULT_SITES.forEach(function (id) {
          var s = state.catalog.filter(function (x) { return x.id === id; })[0];
          if (s) { state.selected.push({ id: s.id, name: s.name, lat: s.lat, lon: s.lon }); }
        });
      }
      loadMap();
      refreshAll();
    }).catch(showError);
    loadReplays();
    loadValidity();
    if ($('regionsGo')) { $('regionsGo').addEventListener('click', function () { $('regionsGo').hidden = true; loadRegions(); }); }
    window.addEventListener('resize', function () { if (state.regions && $('regCanvas')) { drawRegions(); } });
    window.addEventListener('hashchange', function () {
      var cur = '#' + String(location.hash).replace(/^#/, '');
      if (state.lastHash === cur) { return; }
      var f = applyHash(readHash());
      if (f.sites.length) { state.selected = f.sites; state.mi = Math.min(f.mi, f.sites.length - 1); }
      refreshAll();
    });
  }
  document.addEventListener('DOMContentLoaded', init);
}());
