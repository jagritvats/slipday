/* Slip-tolerant atlas, 2027 to 2035 (add-on).
   Self-contained: include this script once and put <div id="addon-atlas"></div> where the atlas should appear.
   It reads /api/addons/atlas and /api/addons/atlas/heat, and draws one block per year: a row per region (or per
   curated site), a column per month, each cell coloured by the share of landing times that work. */
(function () {
  'use strict';
  var ROOT_ID = 'addon-atlas';
  var MONTHS = ['J', 'F', 'M', 'A', 'M', 'J', 'J', 'A', 'S', 'O', 'N', 'D'];
  var MONTH_NAMES = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September',
    'October', 'November', 'December'];
  var state = { variant: 'main', group: 'regions', summary: null, heat: {} };

  var CSS = [
    '.atl{--atl-lo:var(--seq-lo,#e3eefb);--atl-hi:var(--seq-hi,#0e3f7e);--atl-zero:var(--zero-cell,#efeee9);',
    'color:var(--text,#0b0b0b);background:var(--surface,#fcfcfb);border:1px solid var(--line,#dddbd3);border-radius:8px;',
    'padding:16px;margin:16px 0;font:14px/1.45 system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;max-width:100%;box-sizing:border-box}',
    '.atl *{box-sizing:border-box}',
    '.atl h2{font-size:1.15rem;margin:0 0 8px;line-height:1.3}',
    '.atl p{margin:0 0 10px;max-width:70ch}',
    '.atl .atl-muted{color:var(--text2,#52514e);font-size:13px}',
    '.atl .atl-keys{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:8px;margin:12px 0}',
    '.atl .atl-key{border:1px solid var(--line,#dddbd3);border-radius:6px;padding:8px 10px}',
    '.atl .atl-key b{display:block;font-size:1.2rem;font-variant-numeric:tabular-nums}',
    '.atl .atl-key span{font-size:12px;color:var(--text2,#52514e)}',
    '.atl .atl-bar{display:flex;flex-wrap:wrap;gap:6px;margin:10px 0}',
    '.atl button{font:inherit;font-size:13px;padding:6px 10px;min-height:36px;border-radius:6px;cursor:pointer;',
    'border:1px solid var(--line,#dddbd3);background:var(--page,#f4f3ef);color:var(--text,#0b0b0b)}',
    '.atl button[aria-pressed="true"]{background:var(--accent,#0e3f7e);border-color:var(--accent,#0e3f7e);color:#fff}',
    '.atl .atl-legend{display:flex;align-items:center;gap:6px;font-size:12px;color:var(--text2,#52514e);margin:6px 0 12px;flex-wrap:wrap}',
    '.atl .atl-legend i{display:inline-block;width:22px;height:12px;border-radius:2px}',
    '.atl .atl-years{display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:14px}',
    '.atl .atl-year h3{font-size:14px;margin:0 0 2px}',
    '.atl .atl-year .atl-sub{font-size:12px;color:var(--text2,#52514e);margin:0 0 4px;min-height:2.6em}',
    '.atl .atl-grid{display:grid;grid-template-columns:minmax(0,8.5em) repeat(12,minmax(0,1fr));gap:2px;align-items:center}',
    '.atl .atl-lab{font-size: 12px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;padding-right:4px}',
    '.atl .atl-mh{font-size: 12px;text-align:center;color:var(--muted,#7b7a74)}',
    '.atl .atl-c{height:16px;border-radius:2px;border:0;padding:0;min-height:0;cursor:pointer;background:var(--atl-zero)}',
    '.atl .atl-c:focus-visible{outline:2px solid var(--text,#0b0b0b);outline-offset:1px}',
    '.atl .atl-any{font-weight:600}',
    '.atl .atl-ov{max-width:560px;margin-bottom:6px}.atl .atl-ov .atl-c{height:20px}',
    '.atl .atl-h3{font-size:14px;margin:16px 0 8px}',
    '.atl .atl-sep{grid-column:1/-1;height:3px}',
    '.atl .atl-detail{position:sticky;bottom:0;background:var(--surface,#fcfcfb);border-top:1px solid var(--line,#dddbd3);',
    'padding:8px 0;margin-top:10px;font-size:13px;min-height:2.2em}',
    '.atl table{border-collapse:collapse;width:100%;font-size:13px;font-variant-numeric:tabular-nums}',
    '.atl th,.atl td{text-align:right;padding:4px 6px;border-bottom:1px solid var(--grid,#e9e7e0)}',
    '.atl th:first-child,.atl td:first-child{text-align:left}',
    '.atl .atl-tw{overflow-x:auto;margin:10px 0}',
    '.atl details{margin:10px 0}.atl summary{cursor:pointer;font-weight:600}',
    '.atl ul{margin:6px 0 10px;padding-left:20px}.atl li{margin:3px 0}',
    '@media (max-width:480px){.atl{padding:12px}.atl .atl-years{grid-template-columns:1fr}',
    '.atl .atl-grid{grid-template-columns:minmax(0,6.5em) repeat(12,minmax(0,1fr))}.atl .atl-c{height:18px}}'
  ].join('');

  function el(tag, attrs, kids) {
    var e = document.createElement(tag);
    if (attrs) Object.keys(attrs).forEach(function (k) {
      if (k === 'text') e.textContent = attrs[k];
      else if (k === 'cls') e.className = attrs[k];
      else e.setAttribute(k, attrs[k]);
    });
    (kids || []).forEach(function (c) { if (c) e.appendChild(typeof c === 'string' ? document.createTextNode(c) : c); });
    return e;
  }
  function pct(x) { return x == null ? 'n/a' : Math.round(x * 100) + ' %'; }
  function shortName(n) { var i = n.indexOf(' ('); return i > 0 ? n.slice(0, i) : n; }

  function rgb(s, fallback) {
    s = (s || '').trim();
    var m = /^#([0-9a-f]{6})$/i.exec(s);
    if (!m) s = fallback;
    m = /^#([0-9a-f]{6})$/i.exec(s);
    var v = parseInt(m[1], 16);
    return [v >> 16 & 255, v >> 8 & 255, v & 255];
  }
  function ramp(root) {
    var cs = getComputedStyle(root);
    var lo = rgb(cs.getPropertyValue('--seq-lo'), '#e3eefb'), hi = rgb(cs.getPropertyValue('--seq-hi'), '#0e3f7e');
    return function (x) {
      if (!x) return null;
      var t = 0.15 + 0.85 * Math.min(1, x);
      var c = lo.map(function (a, i) { return Math.round(a + (hi[i] - a) * t); });
      return 'rgb(' + c.join(',') + ')';
    };
  }

  function getJSON(url) {
    return fetch(url).then(function (r) { if (!r.ok) throw new Error('HTTP ' + r.status); return r.json(); });
  }

  function intro(s) {
    var m = s.variants.main, so = s.variants.sun_only;
    var py = function (v, y) { return v.per_year.filter(function (r) { return r.year === y; })[0]; };
    var best = py(m, m.best_year), worst = py(m, m.worst_year);
    return 'This chart shows when NASA’s nine Artemis III landing regions, each judged on its published candidate ' +
      'sites, let a lander touch down and stay 6.25 days with the Sun up the whole time and at least 100 hours with the ' +
      'Earth in view for radio contact. Each row is a region, each column a month, and the stronger the colour, the larger the ' +
      'share of landing times in that month that work. Landing times are tried every 6 hours, so the shares count landing ' +
      'times, not real launch opportunities. The Moon’s path around the Earth is tilted, and that tilt slowly turns, ' +
      'repeating every 18.6 years (the 18.6-year cycle). Because of it, the pole’s best-lit season returns every ' +
      '346.6 days, a little under a year, so it comes about 18.6 days earlier in the calendar each year; in the first ' +
      'chart below, the faint patch moves left from one year to the next. With all nine regions kept open, the best year is ' +
      m.best_year + ' (' + pct(best.all_nine) + ' of landing times work) and the worst is ' + m.worst_year + ' (' +
      pct(worst.all_nine) + '), so the years differ, but not by a lot. The 100-hour Earth need is an example figure: with ' +
      'sunlight only, all nine regions together work at ' + pct(so.all_nine_whole_span) + ' of landing times in 2027 to ' +
      '2035, against ' + pct(m.all_nine_whole_span) + ' with it.';
  }

  function keyTiles(s) {
    var v = s.variants[state.variant], wb = v.whole_span_best;
    var d = v.season_drift.earlier_per_year_days;
    var tiles = [
      [v.best_year + ' / ' + v.worst_year, 'best / worst year, all nine regions kept open'],
      [pct(wb[0].share), 'best single region over 2027 to 2035 (' + wb[0].regions.join(', ') + ')'],
      [pct(wb[1].share) + ' / ' + pct(wb[2].share), 'best two / best three regions together'],
      [pct(v.all_nine_whole_span), 'all nine regions together'],
      [(d == null ? 'n/a' : d.toFixed(1)) + ' days', 'how much earlier the season comes each year, read from this chart (' +
        s.subsolar_drift.same_fit_as_atlas.earlier_per_year_days.toFixed(1) + ' from the Sun’s path alone; 18.6 expected)']
    ];
    return el('div', { cls: 'atl-keys' }, tiles.map(function (t) {
      return el('div', { cls: 'atl-key' }, [el('b', { text: t[0] }), el('span', { text: t[1] })]);
    }));
  }

  function toggles(root) {
    function btn(label, key, val) {
      var b = el('button', { type: 'button', 'aria-pressed': String(state[key] === val), text: label });
      b.addEventListener('click', function () { state[key] = val; render(root); });
      return b;
    }
    return el('div', {}, [
      el('div', { cls: 'atl-bar', role: 'group', 'aria-label': 'What the mission needs' }, [
        btn('Sunlight + 100 h Earth contact', 'variant', 'main'), btn('Sunlight only', 'variant', 'sun_only')]),
      el('div', { cls: 'atl-bar', role: 'group', 'aria-label': 'Which places' }, [
        btn('NASA’s nine regions', 'group', 'regions'), btn('This entry’s south-pole sites', 'group', 'curated')])
    ]);
  }

  function legend(color) {
    var kids = [el('span', { text: 'Share of landing times that work:' })];
    [0, 0.1, 0.25, 0.5, 0.75, 1].forEach(function (x) {
      var i = el('i', {});
      i.style.background = color(x) || 'var(--atl-zero)';
      kids.push(i, el('span', { text: Math.round(x * 100) + '%' }));
    });
    return el('div', { cls: 'atl-legend' }, kids);
  }

  /* keyboard: each heat grid is one Tab stop; the arrow keys move by month (left, right) and by row (up, down),
     Home and End go to the row's ends, and the value is read into the live line below the charts */
  function roveGrid(grid, detail) {
    var cells = Array.prototype.slice.call(grid.querySelectorAll('.atl-c'));
    if (!cells.length) return grid;
    cells.forEach(function (c, k) {
      c.tabIndex = k ? -1 : 0;
      c.addEventListener('focus', function () { detail.textContent = c.getAttribute('aria-label') + '.'; });
    });
    grid.addEventListener('keydown', function (ev) {
      var i = cells.indexOf(document.activeElement);
      if (i < 0) return;
      var col = i % 12, j = null;
      if (ev.key === 'ArrowRight') j = i + 1; else if (ev.key === 'ArrowLeft') j = i - 1;
      else if (ev.key === 'ArrowDown') j = i + 12; else if (ev.key === 'ArrowUp') j = i - 12;
      else if (ev.key === 'Home') j = i - col; else if (ev.key === 'End') j = i - col + 11;
      if (j === null) return;
      ev.preventDefault();
      j = Math.max(0, Math.min(cells.length - 1, j));
      cells[i].tabIndex = -1; cells[j].tabIndex = 0; cells[j].focus();
    });
    grid.setAttribute('aria-roledescription', 'heat chart');
    return grid;
  }

  function yearBlock(yi, year, rows, anyRow, py, color, detail) {
    var grid = el('div', { cls: 'atl-grid', role: 'grid', 'aria-label': 'Year ' + year });
    grid.appendChild(el('span', {}));
    MONTHS.forEach(function (m) { grid.appendChild(el('span', { cls: 'atl-mh', 'aria-hidden': 'true', text: m })); });
    function addRow(name, months, extra) {
      grid.appendChild(el('span', { cls: 'atl-lab' + (extra || ''), title: name, text: shortName(name) }));
      months.forEach(function (x, mi) {
        var msg = name + ', ' + MONTH_NAMES[mi] + ' ' + year + ': ' + pct(x) + ' of landing times work';
        var c = el('button', { type: 'button', cls: 'atl-c', title: msg, 'aria-label': msg });
        var bg = color(x);
        if (bg) c.style.background = bg;
        c.addEventListener('click', function () { detail.textContent = msg + '.'; });
        c.addEventListener('mouseenter', function () { detail.textContent = msg + '.'; });
        grid.appendChild(c);
      });
    }
    rows.forEach(function (r) { addRow(r.name, r.months[yi]); });
    if (anyRow) { grid.appendChild(el('span', { cls: 'atl-sep' })); addRow('Any of the nine', anyRow[yi], ' atl-any'); }
    var sub = py ? 'All nine: ' + pct(py.all_nine) + '. Best one: ' + pct(py.best[0].share) + ' (' + py.best[0].regions[0] +
      '), best two: ' + pct(py.best[1].share) + ', best three: ' + pct(py.best[2].share) + '.' : '';
    grid.setAttribute('aria-label', 'Year ' + year + '. ' + sub + ' One Tab stop: use the arrow keys to read each region and month.');
    return el('div', { cls: 'atl-year' }, [el('h3', { text: String(year) }), el('p', { cls: 'atl-sub', text: sub }), roveGrid(grid, detail)]);
  }

  function overview(h, color, detail) {
    var grid = el('div', { cls: 'atl-grid atl-ov', role: 'grid', 'aria-label': 'All nine regions together, one row per year' });
    grid.appendChild(el('span', {}));
    MONTHS.forEach(function (m) { grid.appendChild(el('span', { cls: 'atl-mh', 'aria-hidden': 'true', text: m })); });
    h.years.forEach(function (y, yi) {
      grid.appendChild(el('span', { cls: 'atl-lab atl-any', text: String(y) }));
      h.any_of_nine[yi].forEach(function (x, mi) {
        var msg = 'Any of the nine regions, ' + MONTH_NAMES[mi] + ' ' + y + ': ' + pct(x) + ' of landing times work';
        var c = el('button', { type: 'button', cls: 'atl-c', title: msg, 'aria-label': msg });
        var bg = color(x);
        if (bg) c.style.background = bg;
        c.addEventListener('click', function () { detail.textContent = msg + '.'; });
        c.addEventListener('mouseenter', function () { detail.textContent = msg + '.'; });
        grid.appendChild(c);
      });
    });
    return el('div', { cls: 'atl-year' }, [el('h3', { text: 'All nine regions together, one row per year' }),
      el('p', { cls: 'atl-sub', text: 'Read down the rows: the weak stretch (faint cells) comes a little earlier each year.' }), roveGrid(grid, detail)]);
  }

  function yearTable(s) {
    var v = s.variants[state.variant];
    var head = el('tr', {}, ['Year', 'All nine', 'Best 1', 'Best 2', 'Best 3', 'Regions needed to match all nine',
      'Best single region'].map(function (h) { return el('th', { scope: 'col', text: h }); }));
    var body = v.per_year.map(function (r) {
      return el('tr', {}, [String(r.year), pct(r.all_nine), pct(r.best[0].share), pct(r.best[1].share), pct(r.best[2].share),
        String(r.regions_to_match_all_nine), r.best[0].regions[0]].map(function (t, i) { return el(i ? 'td' : 'th', { text: t }); }));
    });
    return el('div', { cls: 'atl-tw' }, [el('table', {}, [el('thead', {}, [head]), el('tbody', {}, body)])]);
  }

  function notes(s) {
    var ov = s.overlap, li = [];
    li.push('Landing times are tried every ' + s.rule.step_hours + ' hours from ' + s.rule.first.slice(0, 10) + ' to ' +
      s.rule.last.slice(0, 10) + ' (' + s.rule.n_times.toLocaleString('en') + ' landing times). The shares count those ' +
      'landing times, not real launch opportunities.');
    li.push('Each site is judged with the same check as the mission card: 13 touchdown points within 100 m, a coarser ' +
      'terrain grid and a finer sampling of the nearest ground must all pass. A region counts as open when at least one ' +
      'of its published sites passes with room to spare (the Sun and the Earth not grazing the skyline).');
    li.push('The 100 hours of Earth contact is an example figure, not a NASA requirement. The “Sunlight only” ' +
      'button shows the same chart without it.');
    if (ov && ov.available) {
      var a = ov.variants.main, b = ov.variants.sun_only;
      li.push('Check against the 2027 to 2030 region calendar already on this page: ' +
        (a.all_identical && b.all_identical ? 'every one of its ' + ov.n_times.toLocaleString('en') +
          ' landing times gives the same answer in all nine regions, with and without the Earth need.' :
          'the two differ; see the hand-over notes.'));
    }
    li.push('A best set of regions is found by trying every combination, separately for each year. The “regions ' +
      'needed” column is the smallest number of regions that covers every landing time that any of the nine covers in that year.');
    var sd = s.variants.main.season_drift, so = s.variants.sun_only.season_drift;
    li.push('How the drift is read: the landing times are cut into whole lunar months (29.5 days, one cycle of sunlight ' +
      'at the pole), so the month-to-month pattern drops out, and a wave is fitted to see how long the season takes to ' +
      'come back. All nine regions: ' + sd.season_period_days + ' days, so ' + sd.earlier_per_year_days.toFixed(1) +
      ' days earlier each year (' + so.earlier_per_year_days.toFixed(1) + ' with sunlight only). On made-up test signals ' +
      'this reading is right to within about 2 days.');
    li.push('The terrain is NASA’s LOLA elevation data at 80 m per pixel. Finer terrain would most likely show fewer ' +
      'good landing times. Some of this entry’s ' + s.n_sites.curated + ' south-pole sites never pass: three crater ' +
      'floors and the LCROSS impact site are always dark, and the Shackleton rim point fails the full check. Their rows stay empty.');
    li.push('Sites: ' + s.n_sites.published + ' published candidate landing sites in NASA’s nine regions, from ' +
      'Wueller et al. 2026 (JGR Planets, CC BY 4.0).');
    return el('details', {}, [el('summary', { text: 'How this was worked out, and what it cannot tell' }), el('ul', {},
      li.map(function (t) { return el('li', { text: t }); }))]);
  }

  function render(root) {
    var s = state.summary;
    var h = state.heat[state.variant];
    if (!s || !h) return;
    var color = ramp(root);
    root.textContent = '';
    var detail = el('div', { cls: 'atl-detail', 'aria-live': 'polite', text: 'Tap or point at a cell to read its value.' });
    var v = s.variants[state.variant];
    var rows = state.group === 'regions' ? h.regions : h.curated;
    var years = el('div', { cls: 'atl-years' }, h.years.map(function (y, yi) {
      return yearBlock(yi, y, rows, state.group === 'regions' ? h.any_of_nine : null,
        state.group === 'regions' ? v.per_year[yi] : null, color, detail);
    }));
    root.appendChild(el('h2', { text: 'Which years suit a south-pole landing, 2027 to 2035' }));
    root.appendChild(el('p', { text: intro(s) }));
    root.appendChild(toggles(root));
    root.appendChild(keyTiles(s));
    root.appendChild(legend(color));
    root.appendChild(overview(h, color, detail));
    root.appendChild(el('h3', { cls: 'atl-h3', text: state.group === 'regions' ? 'Each region, year by year' :
      'This entry’s south-pole sites, year by year (each judged on its own)' }));
    root.appendChild(years);
    root.appendChild(detail);
    root.appendChild(el('h3', { text: 'Year by year: how much of the year the best regions cover' }));
    root.appendChild(yearTable(s));
    root.appendChild(notes(s));
  }

  function start() {
    var root = document.getElementById(ROOT_ID);
    if (!root || root.getAttribute('data-atlas') === 'on') return;
    root.setAttribute('data-atlas', 'on');
    root.classList.add('atl');
    if (!document.getElementById('atl-style')) {
      var st = document.createElement('style');
      st.id = 'atl-style';
      st.textContent = CSS;
      document.head.appendChild(st);
    }
    root.textContent = 'Loading the 2027 to 2035 atlas…';
    Promise.all([getJSON('/api/addons/atlas'), getJSON('/api/addons/atlas/heat?variant=main'),
      getJSON('/api/addons/atlas/heat?variant=sun_only')]).then(function (r) {
      if (!r[0].available) { root.textContent = 'The 2027 to 2035 atlas has not been built on this installation.'; return; }
      state.summary = r[0];
      state.heat.main = r[1];
      state.heat.sun_only = r[2];
      render(root);
    }).catch(function (e) { root.textContent = 'The 2027 to 2035 atlas could not be loaded (' + e.message + ').'; });
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', start);
  else start();
})();
