/* Slipday glossary: plain-word definitions for the page's harder terms.
 *
 * Include with one tag, after the page's own scripts:  <script src="/static/addons/glossary.js" defer></script>
 * Self-contained: it adds its own CSS, finds the first use of each term in the page's text (and again when the page
 * redraws that part), and turns it into a small term button with a definition.  The definition opens on tap or
 * click, on keyboard focus, and on hover; Escape or a tap elsewhere closes it.  Screen readers get the definition as
 * the term's description.  It never changes inputs, links, buttons, menus, charts or code.
 */
(function () {
  'use strict';
  if (window.SlipdayGlossary) { return; }

  /* longest first, so "slip margin" wins over "slip"; flags: i = any case */
  var TERMS = [
    { key: 'slip-margin', re: /\bslip margins?\b/i, def: 'Slip margin: how many days the launch can be late and the plan still works.' },
    { key: 'touchdown-points', re: /\btouchdown points?\b/i, def: 'Touchdown points: 13 spots around the target where the lander might really come down; all must pass for a Yes.' },
    { key: 'not-sure', re: /\bNot sure\b/, def: 'Not sure: some touchdown points or terrain maps say yes and some say no, so the answer could go either way.' },
    { key: 'terrain-grid', re: /\b(?:5|20|80) m terrain\b/, def: '5 m / 20 m / 80 m terrain: how far apart NASA\'s height measurements are on the map used; smaller is more detailed.' },
    { key: 'permanent-shadow', re: /\bpermanent shadows?\b/i, def: 'Permanent shadow: ground the Sun never reaches, deep in craters. It is very cold and may hold ice.' },
    { key: 'lunar-day', re: /\blunar days?\b/i, def: 'Lunar day: one day and night on the Moon, about 29.5 Earth days from one sunrise to the next.' },
    { key: 'slip', re: /\bslip(?:s|ped)?\b/i, def: 'Slip: the launch is later than planned, so the landing moves too.' },
    { key: 'illustrative', re: /\billustrative\b/i, def: 'Illustrative: an example number chosen to show how it works, not a real mission requirement.' },
    { key: 'skyline', re: /\bskyline\b/i, def: 'Skyline: the line where the ground meets the sky, seen from the landing spot. Hills and crater rims raise it.' },
    { key: 'azimuth', re: /\bazimuth\b/i, def: 'Azimuth: the compass direction of something in the sky, from 0° (north) through 90° (east).' },
    { key: 'elevation', re: /\belevation\b/i, def: 'Elevation: how high something stands in the sky, in degrees; here often counted above the skyline.' },
    { key: 'utc', re: /\bUTC\b/, def: 'UTC: world time (the time in London in winter). All times on this page use it.' },
    { key: 'lola', re: /\bLOLA\b/, def: 'LOLA: a laser on NASA\'s Lunar Reconnaissance Orbiter that measured the height of the Moon\'s ground.' },
    { key: 'clps', re: /\bCLPS\b/, def: 'CLPS: Commercial Lunar Payload Services, NASA\'s program that buys rides to the Moon on company landers.' },
    { key: 'lcrns', re: /\bLCRNS\b/, def: 'LCRNS: NASA\'s planned network of relay satellites around the Moon (Lunar Communications Relay and Navigation Systems).' },
    { key: 'ephemeris', re: /\bephemeris\b/i, def: 'Ephemeris: a table of where the Sun, Earth and Moon are at every moment (here NASA JPL\'s).' },
    { key: 'libration', re: /\blibrations?\b/i, def: 'Libration: the Moon\'s slow wobble as seen from Earth, which moves the Earth a little in the lunar sky.' }
  ];
  var SKIP = /^(SCRIPT|STYLE|NOSCRIPT|TEXTAREA|INPUT|SELECT|OPTION|BUTTON|A|LABEL|CODE|PRE|SVG|CANVAS|TITLE|SUMMARY)$/;

  var css = '' +
    '.gloss{border:0;background:none;padding:0;margin:0;font:inherit;color:inherit;cursor:help;' +
    'text-decoration:underline dotted;text-decoration-thickness:1px;text-underline-offset:3px;}' +
    '.gloss:focus-visible{outline:3px solid var(--accent,#1d3f8f);outline-offset:2px;border-radius:3px;}' +
    '.gloss-sr{position:absolute!important;width:1px;height:1px;overflow:hidden;clip:rect(0 0 0 0);white-space:nowrap;}' +
    '#glossTip{position:absolute;z-index:9999;max-width:min(320px,calc(100vw - 32px));padding:8px 12px;border-radius:8px;' +
    'font:13px/1.45 system-ui,-apple-system,Segoe UI,sans-serif;background:#141820;color:#fff;' +
    'box-shadow:0 4px 16px rgba(0,0,0,.25);}' +
    '#glossTip[hidden]{display:none;}' +
    '@media (prefers-color-scheme:dark){#glossTip{background:#e9ecf1;color:#141820;}}' +
    ':root[data-theme="dark"] #glossTip{background:#e9ecf1;color:#141820;}' +
    ':root[data-theme="light"] #glossTip{background:#141820;color:#fff;}';

  var tip, current = null, busy = false, timer = null, shownAt = 0;

  function setup() {
    var st = document.createElement('style');
    st.id = 'glossCss';
    st.textContent = css;
    document.head.appendChild(st);
    tip = document.createElement('div');
    tip.id = 'glossTip';
    tip.setAttribute('role', 'tooltip');
    tip.hidden = true;
    document.body.appendChild(tip);
    /* the definitions screen readers announce, kept out of the page's own text (one per term) */
    var defs = document.createElement('div');
    defs.id = 'glossDefs';
    defs.className = 'gloss-sr';
    defs.setAttribute('data-no-gloss', '');
    TERMS.forEach(function (t) { var d = document.createElement('span'); d.id = 'glossDef-' + t.key; d.textContent = t.def; defs.appendChild(d); });
    document.body.appendChild(defs);
    document.addEventListener('keydown', function (e) { if (e.key === 'Escape') { hide(); } });
    document.addEventListener('click', function (e) {
      var g = e.target.closest && e.target.closest('.gloss');
      if (g) { e.preventDefault(); /* a tap focuses (which opens) and then clicks: only a later click closes */ if (current === g && !tip.hidden && Date.now() - shownAt > 400) { hide(); } else { show(g); } return; }
      if (!tip.contains(e.target)) { hide(); }
    });
    document.addEventListener('focusin', function (e) { if (e.target.classList && e.target.classList.contains('gloss')) { show(e.target); } });
    document.addEventListener('focusout', function (e) { if (e.target === current) { hide(); } });
    document.addEventListener('mouseover', function (e) { var g = e.target.closest && e.target.closest('.gloss'); if (g) { show(g); } });
    document.addEventListener('mouseout', function (e) { var g = e.target.closest && e.target.closest('.gloss'); if (g && g === current && document.activeElement !== g) { hide(); } });
    window.addEventListener('scroll', function () { if (current) { place(current); } }, { passive: true });
    window.addEventListener('resize', function () { if (current) { place(current); } });
  }

  function defOf(key) { for (var i = 0; i < TERMS.length; i++) { if (TERMS[i].key === key) { return TERMS[i].def; } } return ''; }

  function show(g) {
    if (current !== g || tip.hidden) { shownAt = Date.now(); }
    current = g;
    tip.textContent = defOf(g.getAttribute('data-gloss'));
    tip.hidden = false;
    g.setAttribute('aria-expanded', 'true');
    place(g);
  }

  function hide() {
    if (current) { current.setAttribute('aria-expanded', 'false'); }
    current = null;
    if (tip) { tip.hidden = true; }
  }

  function place(g) {
    tip.style.left = '0px';     /* measure at full width, not squeezed against the right edge */
    tip.style.top = '0px';
    var r = g.getBoundingClientRect();
    var w = tip.offsetWidth, h = tip.offsetHeight;
    var x = Math.max(16, Math.min(window.innerWidth - w - 16, r.left + r.width / 2 - w / 2));
    var y = r.bottom + 8;
    if (y + h > window.innerHeight - 8 && r.top - h - 8 > 0) { y = r.top - h - 8; }
    tip.style.left = (x + window.scrollX) + 'px';
    tip.style.top = (y + window.scrollY) + 'px';
  }

  function okNode(n) {
    for (var e = n.parentElement; e && e !== document.body; e = e.parentElement) {
      if (SKIP.test(e.tagName) || e.classList.contains('gloss') || e.id === 'glossTip' || e.isContentEditable ||
          e.getAttribute('aria-hidden') === 'true' || e.hasAttribute('data-no-gloss')) { return false; }
    }
    return true;
  }

  function wrap(node, m, term) {
    var text = node.nodeValue;
    var before = document.createTextNode(text.slice(0, m.index));
    var after = document.createTextNode(text.slice(m.index + m[0].length));
    var b = document.createElement('button');
    b.type = 'button';
    b.className = 'gloss';
    b.setAttribute('data-gloss', term.key);
    b.setAttribute('aria-expanded', 'false');
    b.setAttribute('aria-describedby', 'glossDef-' + term.key);
    b.textContent = m[0];
    var p = node.parentNode;
    p.insertBefore(before, node);
    p.insertBefore(b, node);
    p.insertBefore(after, node);
    p.removeChild(node);
  }

  /* mark the first use of each term that is not marked yet (a redraw may have removed the old mark) */
  function scan() {
    if (busy || !document.body) { return; }
    busy = true;
    try {
      var todo = TERMS.filter(function (t) { return !document.querySelector('.gloss[data-gloss="' + t.key + '"]'); });
      if (!todo.length) { return; }
      var root = document.querySelector('main') || document.body;
      var walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT, null);
      var nodes = [], n;
      while ((n = walker.nextNode())) { if (n.nodeValue && n.nodeValue.trim().length > 2) { nodes.push(n); } }
      for (var i = 0; i < nodes.length && todo.length; i++) {
        var node = nodes[i];
        if (!node.parentNode || !okNode(node)) { continue; }
        for (var k = 0; k < todo.length; k++) {
          var m = todo[k].re.exec(node.nodeValue);
          if (m) {
            /* a longer term already marked inside this text? ("slip margin" before "slip") */
            wrap(node, m, todo[k]);
            todo.splice(k, 1);
            break;
          }
        }
      }
    } finally {
      busy = false;
    }
  }

  function later() { clearTimeout(timer); timer = setTimeout(scan, 600); }

  function start() {
    setup();
    scan();
    new MutationObserver(function () { if (!busy) { later(); } }).observe(document.body, { childList: true, subtree: true, characterData: true });
  }

  window.SlipdayGlossary = { terms: TERMS.map(function (t) { return { key: t.key, definition: t.def }; }), rescan: scan };
  if (document.readyState === 'loading') { document.addEventListener('DOMContentLoaded', start); } else { start(); }
})();
