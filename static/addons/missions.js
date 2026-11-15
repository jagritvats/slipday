/* Upcoming missions, who this helps, and open data (add-on).
   Self-contained: include this script once and put <div id="addon-missions"></div> where the board should appear.
   It reads /api/addons/impact (stored results; nothing is computed in the browser) and draws:
   one card per upcoming south-pole mission with a published place and launch period, the missions left out and
   why, who this helps (each line linked to the part of the page that backs it), and how to use the data. */
(function () {
  'use strict';
  var ROOT_ID = 'addon-missions';
  var MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];

  var CSS = [
    '.msn{color:var(--text,#0b0b0b);background:var(--surface,#fcfcfb);border:1px solid var(--line,#dddbd3);border-radius:8px;',
    'padding:16px;margin:16px 0;font:14px/1.5 system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;max-width:100%;box-sizing:border-box}',
    '.msn *{box-sizing:border-box}',
    '.msn h2{font-size:1.15rem;margin:0 0 6px;line-height:1.3}',
    '.msn h3{font-size:1rem;margin:0 0 4px;line-height:1.3}',
    '.msn h4{font-size:.95rem;margin:14px 0 6px}',
    '.msn p{margin:0 0 8px;max-width:72ch}',
    '.msn .msn-muted{color:var(--text2,#52514e);font-size:13px}',
    '.msn .msn-cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,400px),1fr));gap:12px;margin:12px 0}',
    '.msn .msn-card{border:1px solid var(--line,#dddbd3);border-radius:8px;padding:12px;background:var(--page,#f4f3ef);min-width:0}',
    '.msn .msn-tag{display:inline-block;font-size:12px;padding:1px 6px;border-radius:4px;background:var(--warn-bg,#fff4d6);',
    'color:var(--warn-ink,#5c4300);margin:2px 0 6px}',
    '.msn .msn-facts{display:grid;grid-template-columns:auto 1fr;gap:2px 10px;font-size:13px;margin:6px 0}',
    '.msn .msn-facts dt{color:var(--text2,#52514e)}.msn .msn-facts dd{margin:0}',
    '.msn .msn-keys{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:6px;margin:8px 0}',
    '.msn .msn-key{border:1px solid var(--line,#dddbd3);border-radius:6px;padding:6px 8px;background:var(--surface,#fcfcfb)}',
    '.msn .msn-key b{display:block;font-size:1.15rem;font-variant-numeric:tabular-nums}',
    '.msn .msn-key span{font-size:12px;color:var(--text2,#52514e)}',
    '.msn .msn-tw{overflow-x:auto;margin:6px 0}',
    '.msn table{border-collapse:collapse;font-size:12.5px;width:100%;font-variant-numeric:tabular-nums}',
    '.msn caption{text-align:left;font-size:12px;color:var(--text2,#52514e);padding-bottom:4px}',
    '.msn th,.msn td{text-align:left;padding:3px 6px;border-bottom:1px solid var(--line,#dddbd3);white-space:nowrap}',
    '.msn th{font-weight:600}',
    '.msn .v-yes{color:var(--ok-ink,#145c2c);font-weight:600}.msn .v-no{color:var(--crit,#a3262a);font-weight:600}',
    '.msn .v-ns{color:var(--warn-ink,#5c4300);font-weight:600}',
    '.msn ul{margin:4px 0 8px;padding-left:20px}.msn li{margin:3px 0;max-width:80ch}',
    '.msn details{margin:8px 0}.msn summary{cursor:pointer;font-weight:600}',
    '.msn code{font:12.5px ui-monospace,Consolas,monospace;background:var(--page,#f4f3ef);padding:0 3px;border-radius:3px;word-break:break-all}',
    '.msn a{color:var(--accent,#0e3f7e)}',
    '.msn .msn-who{display:grid;gap:8px;margin:8px 0}',
    '.msn .msn-who > div{border-left:3px solid var(--accent,#0e3f7e);padding:2px 10px}',
    '.msn blockquote{margin:4px 0;padding:0 0 0 10px;border-left:2px solid var(--line,#dddbd3);color:var(--text2,#52514e);font-size:12.5px}',
    '@media (max-width:420px){.msn{padding:12px}.msn .msn-keys{grid-template-columns:1fr 1fr}}'
  ].join('');

  function esc(s) {
    return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
    });
  }
  function pct(x) { return x == null ? 'n/a' : Math.round(x * 100) + ' %'; }
  function day(iso) {
    if (!iso) return '';
    var d = new Date(iso);
    return d.getUTCDate() + ' ' + MONTHS[d.getUTCMonth()] + ' ' + String(d.getUTCFullYear()).slice(2) + ', ' +
      String(d.getUTCHours()).padStart(2, '0') + 'h';
  }
  function verdict(v) {
    var cls = v === 'yes' ? 'v-yes' : v === 'no' ? 'v-no' : 'v-ns';
    var word = v === 'yes' ? 'Yes' : v === 'no' ? 'No' : v === 'not sure' ? 'Not sure' : v;
    return '<span class="' + cls + '">' + esc(word) + '</span>';
  }

  function lostLine(l, homeWord) {
    if (!l || !l.times) return '';
    var top = l.by_region.filter(function (r) { return r.open_times > 0; }).slice(0, 3)
      .map(function (r) { return esc(r.region); });
    return 'When it is lost (' + l.times + ' cases), another region is open in ' + l.any_other_open + ' of them' +
      (top.length ? ', most often ' + top.join(', ') : '') + '.';
  }

  function missionCard(m) {
    var home = m.home_regions.length === 1 ? m.home_regions[0] : m.home_regions.length + ' regions';
    var h = '<article class="msn-card" aria-labelledby="msn-' + esc(m.id) + '">';
    h += '<h3 id="msn-' + esc(m.id) + '">' + esc(m.name) + '</h3>';
    h += '<div class="msn-tag">Approximate, from NASA\'s published place and period</div>';
    h += '<dl class="msn-facts"><dt>Who</dt><dd>' + esc(m.who) + '</dd>' +
      '<dt>Launch</dt><dd>Published: ' + esc(m.launch_text) + '. We spread landing times over ' + esc(m.span_note) + '.</dd>' +
      '<dt>Place</dt><dd>Published: ' + esc(m.place_text) + '. Checked on the ' + m.home_sites +
      ' published candidate sites of NASA\'s ' + esc(home) + (m.home_regions.length === 1 ? ' region' : '') + '.</dd>' +
      '<dt>Need</dt><dd>' + esc(m.need) + '</dd></dl>';
    h += '<div class="msn-keys">' +
      '<div class="msn-key"><b>' + pct(m.good_share) + '</b><span>of landing times work (' + m.good_times + ' of ' + m.landing_times + ')</span></div>' +
      '<div class="msn-key"><b>' + pct(m.slip_week.share) + '</b><span>still work after a week\'s slip</span></div>' +
      '<div class="msn-key"><b>' + pct(m.slip_month.share) + '</b><span>still work after a month\'s slip</span></div></div>';
    var lw = lostLine(m.slip_week.lost), lm = lostLine(m.slip_month.lost);
    if (m.home_regions.length > 1) {
      h += '<p class="msn-muted">Here the "place" is all nine regions, so a lost landing has nowhere else to go on this list.</p>';
    } else {
      if (lw) h += '<p class="msn-muted"><b>A week late:</b> ' + lw + '</p>';
      if (lm) h += '<p class="msn-muted"><b>A month late:</b> ' + lm + '</p>';
    }
    if (m.months && m.months.length) {
      h += '<p class="msn-muted">First good landing time in each month, re-run through the card ' +
        '(13 touchdown points, two grids). "Can slip" is the slip margin in days from the card. ' + m.months_with_a_good_time + ' of ' + m.months_in_span + ' months have one.</p><div class="msn-tw"><table>' +
        '<thead><tr><th scope="col">Landing (UTC)</th><th scope="col">Site</th><th scope="col">Answer</th>' +
        '<th scope="col">Can slip</th><th scope="col">+1 week</th><th scope="col">+1 month</th></tr></thead><tbody>';
      m.months.forEach(function (r) {
        h += '<tr><td>' + day(r.landing_utc) + '</td><td>' + esc(r.site) + '</td><td>' +
          verdict(r.verdict) + '</td><td>' + (r.verdict === 'yes' ? r.slip_margin_days + ' d' : '') + '</td><td>' +
          verdict(r.week_later.verdict) + '</td><td>' + verdict(r.month_later.verdict) + '</td></tr>';
      });
      h += '</tbody></table></div>';
    } else {
      h += '<p><b>No landing time in the period works at the published place under this need.</b></p>';
    }
    if (m.long_days && m.months && m.months.length && m.months[0].long) {
      var lg = m.months[0].long;
      h += '<p class="msn-muted">Over the published ' + m.long_days + '-day mission from the first good landing: ' +
        lg.sunlit_h_min + ' hours of Sun, ' + lg.earth_h_min + ' hours of Earth contact, longest night ' +
        lg.night_met_h_max + ' hours (worst touchdown point). Hours, not a battery model.</p>';
    }
    h += '<details><summary>What the sources say</summary>';
    m.quotes.forEach(function (q) {
      h += '<blockquote>"' + esc(q.text) + '" <a href="' + esc(q.url) + '" target="_blank" rel="noopener">source</a></blockquote>';
    });
    h += '<p class="msn-muted">' + esc(m.label) + '</p></details>';
    return h + '</article>';
  }

  function render(root, d) {
    var h = '<section class="msn" aria-labelledby="msn-h">';
    h += '<h2 id="msn-h">Upcoming missions: what a slip would do</h2>';
    if (!d.available) {
      h += '<p class="msn-muted">' + esc(d.reason) + '</p>';
    } else {
      h += '<p>Real missions planned for the lunar south pole, 2026 to 2028. For each one, the place and launch period ' +
        'NASA publishes, run through the same check as the card. The question: if the launch slips a week, or a month, ' +
        'can it still land there, and where else could it go?</p>';
      h += '<p class="msn-muted">Approximate. No mission has published its exact landing date or point, so we check every ' +
        '6 hours across the published period at the published candidate sites (Wueller et al. 2026). The needs are ' +
        'illustrative unless marked published. This is not any mission\'s own plan.</p>';
      var mm = d.missions.filter(function (m) { return m.home_regions.length === 1 && m.slip_week.share != null; });
      if (mm.length) {
        var wk = mm.map(function (m) { return m.slip_week.share; }), mo = mm.map(function (m) { return m.slip_month.share; });
        var lo = function (a) { return pct(Math.min.apply(null, a)); }, hi = function (a) { return pct(Math.max.apply(null, a)); };
        h += '<p><b>What it shows:</b> at ' + esc(mm[0].home_regions[0]) + ', where ' + mm.length +
          ' of these missions go, a landing time that works there mostly fails if it slips a week (only ' + lo(wk) + ' to ' + hi(wk) +
          ' still work), but mostly works again a month later (' + lo(mo) + ' to ' + hi(mo) +
          '). So after a slip, waiting for next month\'s window usually beats landing late in this one, ' +
          'and the board says which other regions are open when it does not.</p>';
      }
      h += '<div class="msn-cards">' + d.missions.map(missionCard).join('') + '</div>';
      h += '<h4>Looked for, but left out</h4><ul>';
      d.listed_without_a_point.forEach(function (x) {
        h += '<li><b>' + esc(x.name) + '</b> (' + esc(x.launch_text) + '): ' + esc(x.why) +
          ' <a href="' + esc(x.url) + '" target="_blank" rel="noopener">source</a></li>';
      });
      h += '</ul>';
    }
    // who this helps
    h += '<h4 id="addon-missions-who">Who this helps</h4><div class="msn-who">';
    (d.who || []).forEach(function (w) {
      var links = w.where.map(function (x) { return '<a href="#' + esc(x.id) + '">' + esc(x.label) + '</a>'; }).join(' · ');
      h += '<div><b>' + esc(w.who) + '.</b> ' + esc(w.how) + '<br><span class="msn-muted">On this page: ' + links + '</span></div>';
    });
    h += '</div>';
    // open data
    var od = d.open_data;
    if (od) {
      h += '<h4 id="addon-missions-data">Use the data</h4><p class="msn-muted">' + esc(od.note) + '</p>';
      h += '<details><summary>API endpoints</summary><ul>';
      od.endpoints.forEach(function (e) {
        h += '<li><code>' + esc(e.method) + ' ' + esc(e.path) + '</code>: ' + esc(e.what) + '</li>';
      });
      h += '</ul><p class="msn-muted">Full list: <a href="/docs">' + esc(od.docs) + '</a></p></details>';
      h += '<p><b>Download:</b> ';
      h += '<a href="/api/addons/impact/missions.csv" download>this board as CSV</a> · ' +
        '<a href="/api/addons/impact/missions.json" download>as JSON</a>. ' +
        '<span class="msn-muted">The card\'s "Download this answer" button gives any site and date. ' + esc(od.licence) + '</span></p>';
    }
    if (d.available && d.sources) {
      h += '<details><summary>Sources, read first-hand (with sha256 of the saved page)</summary><ul>';
      Object.keys(d.sources).forEach(function (k) {
        var s = d.sources[k];
        h += '<li><a href="' + esc(s.url) + '" target="_blank" rel="noopener">' + esc(s.title) + '</a>' +
          (s.sha256 ? ' <code>' + esc(s.sha256.slice(0, 16)) + '…</code>' : '') + '</li>';
      });
      h += '</ul><p class="msn-muted">' + esc(d.citation) + '</p></details>';
    }
    root.innerHTML = h + '</section>';
  }

  function start() {
    var root = document.getElementById(ROOT_ID);
    if (!root) return;
    if (!document.getElementById('msn-css')) {
      var st = document.createElement('style');
      st.id = 'msn-css';
      st.textContent = CSS;
      document.head.appendChild(st);
    }
    root.innerHTML = '<p class="msn-muted" role="status">Loading upcoming missions…</p>';
    fetch('/api/addons/impact').then(function (r) { return r.json(); }).then(function (d) { render(root, d); })
      .catch(function () { root.innerHTML = '<p role="status">The upcoming-missions board could not be loaded.</p>'; });
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', start); else start();
})();
