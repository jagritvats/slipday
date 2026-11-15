/* Links out from a Slipday site to the same place in the two map tools the challenge lists:
   LROC QuickMap and NASA Moon Trek.  No dependencies.

     window.SlipdayLinks.urls(lat, lon)        -> { quickmap, moontrek, projection }
     window.SlipdayLinks.html(lat, lon, name)  -> HTML string with both links and the coordinates

   Link formats, each loaded once in headless Chrome on 14 Nov 2026 and checked on a screenshot:

   South of 80 S both tools are opened in their south polar stereographic view, centred on the site.
   Both take projected metres with x = r sin(lon), y = r cos(lon), r = 2 R tan((90 - |lat|) / 2),
   R = 1737.4 km (checked by centring each tool on Shackleton crater, 89.67 S 129.78 E: the crater was
   in the middle of the view in both).
     QuickMap   ?prjExtent=xmin,ymin,xmax,ymax&proj=17
     Moon Trek  #v=0.1&x=<x>&y=<y>&z=8&p=urn:ogc:def:crs:IAU2000::30120&d=

   Anywhere else both are opened in their equirectangular view (checked at the Apollo 11 site):
     QuickMap   ?extent=lonmin,latmin,lonmax,latmax&proj=10
     Moon Trek  #v=0.1&x=<lon>&y=<lat>&z=8&p=urn:ogc:def:crs:EPSG::104903&d=
   North of 80 N that view is badly stretched; the tools' north polar views were not checked, so the
   coordinates are printed beside the links to type in.

   Both tools show a welcome dialog on a first visit; the map behind it is already at the site. */
(function () {
  'use strict';
  var R_M = 1737400;
  var QUICKMAP = 'https://quickmap.lroc.im-ldi.com/';
  var MOONTREK = 'https://trek.nasa.gov/moon/';
  var HALF_KM = 20;          /* half the height of the view asked for, km */
  var ASPECT = 1.6;          /* width over height of the view asked for */

  function esc(s) {
    return String(s).replace(/[&<>"']/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
    });
  }
  function normLon(lon) { var v = ((lon + 180) % 360 + 360) % 360 - 180; return v === -180 ? 180 : v; }
  function polarXY(lat, lon) {
    var r = 2 * R_M * Math.tan((90 - Math.abs(lat)) * Math.PI / 360), lo = lon * Math.PI / 180;
    return [r * Math.sin(lo), r * Math.cos(lo)];
  }
  function urls(lat, lon) {
    lat = Number(lat); lon = normLon(Number(lon));
    if (!isFinite(lat) || !isFinite(lon) || lat < -90 || lat > 90) { return null; }
    if (lat <= -80) {
      var p = polarXY(lat, lon), h = HALF_KM * 1000, w = h * ASPECT;
      return {
        projection: 'south polar stereographic',
        quickmap: QUICKMAP + '?prjExtent=' + [p[0] - w, p[1] - h, p[0] + w, p[1] + h].map(Math.round).join(',') + '&proj=17',
        moontrek: MOONTREK + '#v=0.1&x=' + Math.round(p[0]) + '&y=' + Math.round(p[1]) +
          '&z=8&p=urn%3Aogc%3Adef%3Acrs%3AIAU2000%3A%3A30120&d='
      };
    }
    var dLat = HALF_KM * 1000 / (R_M * Math.PI / 180), dLon = dLat * ASPECT;
    var f = function (v) { return v.toFixed(4); };
    return {
      projection: 'equirectangular',
      quickmap: QUICKMAP + '?extent=' + [f(lon - dLon), f(Math.max(-90, lat - dLat)), f(lon + dLon), f(Math.min(90, lat + dLat))].join(',') + '&proj=10',
      moontrek: MOONTREK + '#v=0.1&x=' + lon.toFixed(5) + '&y=' + lat.toFixed(5) +
        '&z=8&p=urn%3Aogc%3Adef%3Acrs%3AEPSG%3A%3A104903&d='
    };
  }
  function coords(lat, lon) {
    lon = normLon(Number(lon));
    return Math.abs(lat).toFixed(4) + (lat < 0 ? ' S' : ' N') + ', ' + Math.abs(lon).toFixed(4) + (lon < 0 ? ' W' : ' E');
  }
  function html(lat, lon, name) {
    var u = urls(lat, lon);
    if (!u) { return ''; }
    var a = function (href, text, tool) {
      return '<a href="' + esc(href) + '" target="_blank" rel="noopener noreferrer" title="Opens ' + esc(tool) + ' in a new tab, ' +
        esc(u.projection) + ' view centred on this site">' + esc(text) + '</a>';
    };
    return '<span class="linksOut">' + (name ? esc(name) + ': ' : '') + 'the same place in ' +
      a(u.quickmap, 'LROC QuickMap', 'LROC QuickMap') + ' and ' + a(u.moontrek, 'NASA Moon Trek', 'NASA Moon Trek') +
      ' <span class="linksCoords">(' + esc(coords(Number(lat), Number(lon))) + (lat >= 80 ? '; near the north pole these views are stretched, so type the coordinates in' : '') + ')</span></span>';
  }
  var api = { urls: urls, html: html, coords: coords };
  if (typeof window !== 'undefined') { window.SlipdayLinks = api; }
  if (typeof module !== 'undefined' && module.exports) { module.exports = api; }
})();
