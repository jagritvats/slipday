/* Slipday add-on: "Launch windows from orbital mechanics"

   Include with one container and one script tag (nothing else is created in the page):
     <div id="addon-trajwindows"></div>
     <script src="/static/addons/trajwindows.js"></script>

   Asks GET /api/addons/trajwindows/windows?site=|lat=&lon=&landing=&transfer_days=&months=
   and shows, per lighting window: when it opens, the Sun at opening, the Moon's declination, the daily launch
   periods from Kennedy (UTC) and the step from the previous window next to the card's one-synodic-month rule.
   Every assumption is labelled where it appears.  Uses the classes of /static/addons/addons.css when that file
   is loaded; the few extra styles are scoped to #addon-trajwindows.  No library.
*/
(function () {
  'use strict';
  var ROOT_ID = 'addon-trajwindows';
  var root = document.getElementById(ROOT_ID);
  if (!root) return;

  function esc(s) {
    return String(s).replace(/[&<>"']/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
    });
  }
  function t(iso) { return esc(String(iso).replace('T', ' ').replace(':00Z', ' UTC')); }

  var css = document.createElement('style');
  css.textContent =
    '#' + ROOT_ID + ' .tw-tab{border-collapse:collapse;font-size:13.5px;margin:6px 0;max-width:100%}' +
    '#' + ROOT_ID + ' .tw-tab th,#' + ROOT_ID + ' .tw-tab td{border-bottom:1px solid var(--line,#dddbd3);' +
    'padding:4px 8px;text-align:left;vertical-align:top}' +
    '#' + ROOT_ID + ' .tw-scroll{overflow-x:auto;max-width:100%}' +
    '#' + ROOT_ID + ' .tw-lab{font-size:11.5px;color:var(--muted,#7b7a74);font-style:italic}' +
    '#' + ROOT_ID + ' input,#' + ROOT_ID + ' select{font:inherit;padding:3px 6px}';
  document.head.appendChild(css);

  root.classList.add('sd-addon');
  root.innerHTML =
    '<h2>Launch windows from orbital mechanics</h2>' +
    '<p class="sd-what">If the landing is missed, when is the next one? The card assumes one synodic month ' +
    '(29.53 days, <span class="tw-lab">our inference</span>). Here the windows are worked out from the Sun at ' +
    'the site (DE421, terrain skyline), the Moon at arrival and Earth\'s rotation under the launch site. ' +
    '<span class="tw-lab">Simplified patched conic: a geometry check, not a mission design.</span></p>' +
    '<div class="sd-row">' +
    '<label>Site <select data-k="site"><option value="robust_pick">Slip-robust ridge point</option>' +
    '<option value="shackleton">Shackleton connecting ridge (C1)</option></select></label>' +
    '<label>Landing <input data-k="landing" value="2026-11-18T00:00:00Z" size="21"></label>' +
    '<label>Transfer days <input data-k="transfer_days" type="number" min="2.5" max="6" step="0.5" value="4" ' +
    'style="width:4.5em"></label> <span class="tw-lab">assumption: direct transfer</span>' +
    '<button class="sd-primary" type="button" data-go>Work out</button></div>' +
    '<div data-out aria-live="polite"></div>';

  var out = root.querySelector('[data-out]');

  function val(k) { return root.querySelector('[data-k="' + k + '"]').value; }

  function render(d) {
    var h = '<p class="sd-lead">' + esc(d.site.name) + ' (' + esc(d.site.horizon) + '). Launch from ' +
      esc(d.launch_site.label) + ' ' + d.launch_site.lat + ', ' + d.launch_site.lon + '.</p>';
    if (!d.windows.length) {
      out.innerHTML = h + '<p>No lighting window inside the scanned months with these assumptions.</p>';
      return;
    }
    h += '<div class="tw-scroll"><table class="tw-tab"><thead><tr><th>#</th><th>Lighting window opens</th>' +
      '<th>Sun at opening</th><th>Moon declination at arrival</th><th>Launch periods (UTC, best = azimuth nearest 90&deg;)</th>' +
      '<th>Step from previous</th></tr></thead><tbody>';
    d.windows.forEach(function (w) {
      var lp = w.launch_periods.map(function (p) {
        return t(p.launch_from) + ' &ndash; ' + t(p.launch_to).replace(/^\S+ /, '') + ' (best ' +
          t(p.best_launch).replace(/^\S+ /, '') + ', az ' + p.best_azimuth_deg + '&deg;, ' + esc(p.heading) + ')';
      }).join('<br>') || 'none inside the azimuth limits';
      var step = w.step_from_previous_days == null ? '&mdash;' :
        w.step_from_previous_days + ' d<br><span class="tw-lab">rule: ' + d.synodic_rule_days.toFixed(2) +
        ' d; differs by ' + w.differs_from_synodic_rule_days + ' d from k &times; 29.53</span>';
      h += '<tr><td>' + w.k + '</td><td>' + t(w.window_open) + '<br><span class="tw-lab">' + w.window_hours +
        ' h in band; touchdown allowed to ' + t(w.landing_band[1]) + '</span></td><td>' +
        w.sun_elevation_at_open_deg + '&deg; elevation, ' + w.sun_clearance_at_open_deg +
        '&deg; above skyline</td><td>' + w.moon_declination_deg[0] + '&deg; to ' + w.moon_declination_deg[1] +
        '&deg;' + (w.declination_check.ok ? '' : ' <b>beyond reach</b>') + '</td><td>' + lp + '</td><td>' + step +
        '</td></tr>';
    });
    h += '</tbody></table></div>';
    h += '<p class="sd-note">Steps between windows: ' + (d.steps_days.length ? d.steps_days.join(' d, ') + ' d' : 'n/a') +
      ', against the card\'s ' + d.synodic_rule_days.toFixed(2) + ' d rule.</p>';
    h += '<details class="sd-more"><summary>Assumptions and limits</summary><ul class="sd-list">' +
      '<li>Landing Sun band ' + d.sun_band_deg[0] + ' to ' + d.sun_band_deg[1] + '&deg; above the skyline and rising ' +
      '<span class="tw-lab">' + esc(d.sun_band_label) + '</span></li>' +
      '<li>Touchdown in the first ' + d.landing_band_h + ' h of a window; touchdown = arrival, no time in lunar orbit ' +
      '<span class="tw-lab">illustrative / assumption</span></li>' +
      '<li>Transfer ' + d.transfer_days + ' days <span class="tw-lab">' + esc(d.transfer_label) + '</span></li>' +
      '<li>Launch azimuth ' + d.azimuth_limits_deg[0] + ' to ' + d.azimuth_limits_deg[1] + '&deg; ' +
      '<span class="tw-lab">' + esc(d.azimuth_label) + '</span></li>' +
      '<li>Two-body legs, the Moon\'s direction as the target, no rocket performance, range or weather rules; ' +
      'J2000 equator as equator of date, UT1 = UTC <span class="tw-lab">assumption</span></li>' +
      '</ul></details>';
    out.innerHTML = h;
  }

  function go() {
    var q = new URLSearchParams({ site: val('site'), landing: val('landing'), transfer_days: val('transfer_days'),
                                  months: '3' });
    out.innerHTML = '<p class="sd-note">Working out&hellip;</p>';
    fetch('/api/addons/trajwindows/windows?' + q.toString()).then(function (r) {
      return r.json().then(function (j) { if (!r.ok) throw new Error(j.detail || r.status); return j; });
    }).then(render).catch(function (e) {
      out.innerHTML = '<p>Could not work out the windows: ' + esc(e.message) + '</p>';
    });
  }
  root.querySelector('[data-go]').addEventListener('click', go);
  go();
})();
