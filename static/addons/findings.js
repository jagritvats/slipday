/* What we found: Slipday's science panel.  Self-contained: put <div id="addon-findings"></div> on the page and load
   this file.  It reads GET /api/addons/findings and draws small charts in plain SVG, coloured from the page's CSS
   variables (no libraries, no CDN). */
(function () {
  "use strict";
  var NS = "http://www.w3.org/2000/svg";

  function cssVar(name, fallback) {
    var v = getComputedStyle(document.documentElement).getPropertyValue(name);
    return (v && v.trim()) || fallback;
  }
  function C() {
    return {
      text: cssVar("--text", "#141820"), text2: cssVar("--text2", "#454d5a"), muted: cssVar("--muted", "#59626f"),
      line: cssVar("--line", "#d3d8df"), grid: cssVar("--grid", "#e4e8ed"), surface: cssVar("--surface", "#fff"),
      raised: cssVar("--raised", "#f6f7f9"), accent: cssVar("--accent", "#1d3f8f"), crit: cssVar("--crit", "#c62828"),
      good: cssVar("--good", "#1a7f37"), sun: cssVar("--sun", "#c2560f"), earth: cssVar("--earth", "#2364c4"),
      sky: cssVar("--sky", "#7d8796"), skyfill: cssVar("--skyfill", "#cdd3dc")
    };
  }
  function el(tag, attrs, parent, text) {
    var e = document.createElementNS(NS, tag);
    for (var k in attrs) e.setAttribute(k, attrs[k]);
    if (text != null) e.textContent = text;
    if (parent) parent.appendChild(e);
    return e;
  }
  function h(tag, cls, parent, text) {
    var e = document.createElement(tag);
    if (cls) e.className = cls;
    if (text != null) e.textContent = text;
    if (parent) parent.appendChild(e);
    return e;
  }
  function svg(parent, w, hgt, label) {
    var s = el("svg", { viewBox: "0 0 " + w + " " + hgt, width: "100%", role: "img", "aria-label": label,
      style: "max-width:" + w + "px;display:block;height:auto;font-family:inherit" }, parent);
    el("title", {}, s, label);
    return s;
  }
  function txt(s, x, y, t, o) {
    o = o || {};
    return el("text", { x: x, y: y, "font-size": o.size || 11, fill: o.fill || C().muted,
      "text-anchor": o.anchor || "start" }, s, t);
  }
  function pct(x) { return Math.round(x * 100) + " %"; }

  /* ---------------------------------------------------------------- charts */

  function datesBars(parent, rows) {
    var c = C(), W = 520, H = 190, L = 40, B = 34, T = 12, R = 8;
    var s = svg(parent, W, H, "Map points re-checked on 20 m terrain, by start date");
    var max = Math.max.apply(null, rows.map(function (r) { return r.points; }).concat([1]));
    var bw = (W - L - R) / rows.length;
    var y = function (v) { return T + (H - T - B) * (1 - v / max); };
    [0, max / 2, max].forEach(function (v) {
      el("line", { x1: L, x2: W - R, y1: y(v), y2: y(v), stroke: c.grid }, s);
      txt(s, L - 4, y(v) + 4, Math.round(v), { anchor: "end" });
    });
    rows.forEach(function (r, i) {
      var x = L + i * bw + 2, w = bw - 4, y0 = y(0);
      var parts = [[r.agree, c.skyfill], [r.coarse_yes_fine_no, c.crit], [r.coarse_no_fine_yes, c.accent]];
      parts.forEach(function (p) {
        if (!p[0]) return;
        var hh = (H - T - B) * p[0] / max;   /* this part's own height (stacked on the parts below it) */
        el("rect", { x: x, y: y0 - hh, width: w, height: hh, fill: p[1] }, s);
        y0 -= hh;
      });
      if (!r.points) txt(s, x + w / 2, y(0) - 3, "0", { anchor: "middle", size: 9 });
      if (i % 2 === 0) txt(s, x + w / 2, H - B + 14, r.start.slice(5), { anchor: "middle", size: 9 });
    });
    txt(s, L, H - 4, "start date (2026 to 2027)", { size: 10 });
    legend(parent, [[c.skyfill, "same answer"], [c.crit, "landable on 80 m, rejected on 20 m"],
      [c.accent, "rejected on 80 m, landable on 20 m"]]);
  }

  function polarMap(parent, mp) {
    var c = C(), W = 300, H = 300, cx = W / 2, cy = H / 2;
    var rows = mp.rows, ext = 1;
    rows.forEach(function (r) { ext = Math.max(ext, Math.abs(r[0]), Math.abs(r[1])); });
    ext *= 1.08;
    var sc = (W / 2 - 10) / ext;
    var s = svg(parent, W, H, "Where 80 m and 20 m terrain disagree, polar view around the south pole");
    el("rect", { x: 0, y: 0, width: W, height: H, fill: c.raised, rx: 8 }, s);
    [10, 20, 30].forEach(function (km) {
      if (km < ext) {
        el("circle", { cx: cx, cy: cy, r: km * sc, fill: "none", stroke: c.grid }, s);
        txt(s, cx + 3, cy - km * sc - 2, km + " km", { size: 9 });
      }
    });
    var order = rows.slice().sort(function (a, b) { return (a[3] + a[4] > 0) - (b[3] + b[4] > 0); });
    order.forEach(function (r) {
      var col = r[3] ? c.crit : (r[4] ? c.accent : c.sky);
      el("circle", { cx: cx + r[0] * sc, cy: cy - r[1] * sc, r: r[3] || r[4] ? 2.4 : 1.4, fill: col,
        "fill-opacity": r[3] || r[4] ? 0.9 : 0.45 }, s);
    });
    el("circle", { cx: cx, cy: cy, r: 2.5, fill: c.text }, s);
    txt(s, cx + 5, cy + 12, "pole", { size: 9, fill: c.text2 });
    txt(s, cx, 12, "0° E", { anchor: "middle", size: 9 });
    txt(s, W - 6, cy - 4, "90° E", { anchor: "end", size: 9 });
    legend(parent, [[c.sky, "re-checked, same answer"], [c.crit, "rejected on 20 m on some date"],
      [c.accent, "landable only on 20 m"]]);
  }

  function hbars(parent, items, unit, label) {
    var c = C(), W = 420, rowH = 26, L = 150, R = 50, H = items.length * rowH + 8;
    var s = svg(parent, W, H, label);
    var max = Math.max.apply(null, items.map(function (i) { return i[1] || 0; }).concat([1]));
    items.forEach(function (it, i) {
      var y = 4 + i * rowH, w = (W - L - R) * (it[1] || 0) / max;
      txt(s, L - 6, y + 15, it[0], { anchor: "end", fill: c.text2 });
      el("rect", { x: L, y: y + 4, width: Math.max(w, 1), height: rowH - 10, fill: it[2], rx: 3 }, s);
      txt(s, L + w + 5, y + 15, it[1] == null ? "n/a" : it[1] + unit, { fill: c.text });
    });
  }

  function coverageCurve(parent, data) {
    var c = C(), W = 520, H = 230, L = 40, B = 34, T = 10, R = 120;
    var s = svg(parent, W, H, "Share of landing times covered by the best 1 to 9 regions");
    var x = function (k) { return L + (W - L - R) * (k - 1) / 8; };
    var y = function (v) { return T + (H - T - B) * (1 - v); };
    [0, 0.25, 0.5, 0.75, 1].forEach(function (v) {
      el("line", { x1: L, x2: W - R, y1: y(v), y2: y(v), stroke: c.grid }, s);
      txt(s, L - 4, y(v) + 4, pct(v), { anchor: "end", size: 10 });
    });
    for (var k = 1; k <= 9; k++) txt(s, x(k), H - B + 14, k, { anchor: "middle", size: 10 });
    txt(s, L, H - 4, "regions kept open (best set for each number)", { size: 10 });
    var series = [["sunlight_only", "2027-2030", c.sun, "", "sunlight only"],
      ["sunlight_only", "2027-2035", c.sun, "4 3", ""],
      ["earth_need", "2027-2030", c.earth, "", "with Earth need"],
      ["earth_need", "2027-2035", c.earth, "4 3", ""]];
    series.forEach(function (sr) {
      var pts = data[sr[0]][sr[1]];
      el("polyline", { points: pts.map(function (p) { return x(p.k) + "," + y(p.share); }).join(" "), fill: "none",
        stroke: sr[2], "stroke-width": 2, "stroke-dasharray": sr[3] }, s);
      if (!sr[3]) pts.forEach(function (p) { el("circle", { cx: x(p.k), cy: y(p.share), r: 2.6, fill: sr[2] }, s); });
      if (sr[4]) {
        var last = pts[pts.length - 1];
        txt(s, x(9) + 6, y(last.share) + 4, sr[4] + " " + pct(last.share), { fill: sr[2], size: 10 });
      }
    });
    legend(parent, [[c.text2, "solid: 2027 to 2030"], [c.text2, "dashed: 2027 to 2035"]]);
  }

  function driftLine(parent, years) {
    var c = C(), W = 520, H = 190, L = 44, B = 30, T = 10, R = 10;
    var s = svg(parent, W, H, "Date each year when the Sun is furthest south, from Slipday's ephemeris");
    var y0 = years[0].year, y1 = years[years.length - 1].year;
    var x = function (yr) { return L + (W - L - R) * (yr - y0) / Math.max(y1 - y0, 1); };
    var y = function (d) { return T + (H - T - B) * (d - 1) / 365; };
    [1, 91, 182, 274, 365].forEach(function (d, i) {
      el("line", { x1: L, x2: W - R, y1: y(d), y2: y(d), stroke: c.grid }, s);
      txt(s, L - 4, y(d) + 4, ["Jan", "Apr", "Jul", "Oct", "Dec"][i], { anchor: "end", size: 10 });
    });
    // expected: 18.63 days earlier each year, anchored on the first year
    var e0 = years[0].day_of_year;
    var segs = [], prev = null;
    years.forEach(function (r) {
      var d = e0 - 18.63 * (r.year - y0);
      while (d < 1) d += 365.25;
      if (prev != null && d > prev + 100) segs.push(null);
      segs.push([x(r.year), y(d)]); prev = d;
    });
    var path = "", pen = false;
    segs.forEach(function (p) { if (!p) { pen = false; return; } path += (pen ? " L" : " M") + p[0] + "," + p[1]; pen = true; });
    el("path", { d: path, fill: "none", stroke: c.sky, "stroke-dasharray": "4 3", "stroke-width": 1.5 }, s);
    years.forEach(function (r) {
      el("circle", { cx: x(r.year), cy: y(r.day_of_year), r: 3.2, fill: c.sun }, s);
      txt(s, x(r.year), H - B + 14, String(r.year).slice(2), { anchor: "middle", size: 9 });
    });
    legend(parent, [[c.sun, "measured (Slipday ephemeris)"], [c.sky, "expected, 18.63 days earlier a year"]]);
  }

  function scatter(parent, maps) {
    var c = C();
    var wrap = h("div", "", parent);
    wrap.style.cssText = "display:flex;flex-wrap:wrap;gap:12px";
    maps.forEach(function (m) {
      var W = 200, H = 200, P = 26;
      var box = h("div", "", wrap);
      var s = svg(box, W, H, "Earth in view: LOLA map against Slipday, " + m.map);
      var x = function (v) { return P + (W - P - 6) * v; }, y = function (v) { return H - P - (H - P - 6) * v; };
      el("rect", { x: P, y: 6, width: W - P - 6, height: H - P - 6, fill: c.raised }, s);
      el("line", { x1: x(0), y1: y(0), x2: x(1), y2: y(1), stroke: c.sky, "stroke-dasharray": "3 3" }, s);
      m.pairs.forEach(function (p) {
        el("circle", { cx: x(p[0]), cy: y(p[1]), r: 1.8, fill: c.earth, "fill-opacity": 0.6 }, s);
      });
      txt(s, P, H - 8, "LOLA map", { size: 9 });
      txt(s, 2, 14, "Slipday", { size: 9 });
      h("div", "", box, m.map).style.cssText = "font-size:12px;color:" + c.muted;
    });
  }

  function legend(parent, items) {
    var d = h("div", "", parent);
    d.style.cssText = "display:flex;flex-wrap:wrap;gap:4px 14px;font-size:12px;margin:4px 0 8px;color:" + C().text2;
    items.forEach(function (it) {
      var sp = h("span", "", d);
      var sw = h("span", "", sp);
      sw.style.cssText = "display:inline-block;width:10px;height:10px;border-radius:2px;margin-right:5px;vertical-align:-1px;background:" + it[0];
      sp.appendChild(document.createTextNode(it[1]));
    });
  }

  function chart(parent, ch) {
    var c = C();
    if (ch.type === "dates_bars") return datesBars(parent, ch.data);
    if (ch.type === "polar_map") return polarMap(parent, ch.data);
    if (ch.type === "ridge_bars") return hbars(parent, [["80 m terrain", ch.data.coarse_80m, c.crit],
      ["20 m terrain", ch.data.fine_20m, c.accent], ["published", ch.data.published, c.sky]], " h",
      "Shackleton ridge: longest darkness in a year");
    if (ch.type === "coverage_curve") return coverageCurve(parent, ch.data);
    if (ch.type === "drift_line") return driftLine(parent, ch.data);
    if (ch.type === "scatter") return scatter(parent, ch.data);
  }

  function fmt(v) {
    if (v && typeof v === "object") {
      return Object.keys(v).map(function (k) { return pct(v[k]); }).join(" / ");
    }
    return String(v);
  }

  function render(root, d) {
    var c = C();
    root.innerHTML = "";
    root.style.color = c.text;
    var head = h("div", "", root);
    h("h2", "", head, "What we found").style.cssText = "margin:0 0 4px;font-size:var(--fs-xl,24px)";
    h("p", "", head, "Slipday's own measurements, recomputed from its stored data. Two findings, then the checks "
      + "that show the model can be trusted.").style.cssText = "margin:0 0 16px;color:" + c.text2;
    d.findings.forEach(function (f) {
      var card = h("section", "", root);
      card.style.cssText = "background:" + c.surface + ";border:1px solid " + c.line + ";border-radius:var(--r,12px);"
        + "padding:16px;margin:0 0 16px";
      var tag = h("div", "", card, f.kind === "check" ? "Validation" : "Finding");
      tag.style.cssText = "font-size:12px;text-transform:uppercase;letter-spacing:.06em;color:"
        + (f.kind === "check" ? c.muted : c.accent);
      h("h3", "", card, f.title).style.cssText = "margin:2px 0 6px;font-size:var(--fs-lg,18px)";
      h("p", "", card, f.headline).style.cssText = "margin:0 0 12px;font-size:var(--fs-md,15px);line-height:1.45";
      var charts = h("div", "", card);
      charts.style.cssText = "display:flex;flex-wrap:wrap;gap:16px;align-items:flex-start";
      f.charts.forEach(function (ch) {
        var box = h("div", "", charts);
        box.style.cssText = "flex:1 1 280px;min-width:0;max-width:540px";
        chart(box, ch);
      });
      var tbl = h("table", "", card);
      tbl.style.cssText = "border-collapse:collapse;font-size:13px;margin:8px 0;width:100%";
      f.numbers.forEach(function (n) {
        var tr = h("tr", "", tbl);
        var a = h("td", "", tr, n.label), b = h("td", "", tr, fmt(n.value));
        a.style.cssText = "padding:3px 8px 3px 0;color:" + c.text2 + ";border-top:1px solid " + c.grid;
        b.style.cssText = "padding:3px 0;font-variant-numeric:tabular-nums;border-top:1px solid " + c.grid;
      });
      var cv = h("ul", "", card);
      cv.style.cssText = "margin:8px 0 0;padding-left:18px;font-size:13px;color:" + c.muted;
      f.caveats.forEach(function (t) { h("li", "", cv, t); });
    });
    h("p", "", root, "Built " + d.built_utc + ". Shares with the Earth need use an illustrative 100 hours of Earth "
      + "contact, not a NASA requirement.").style.cssText = "font-size:12px;color:" + c.muted;
  }

  function start() {
    var root = document.getElementById("addon-findings");
    if (!root) return;
    root.textContent = "Loading findings…";
    fetch("/api/addons/findings").then(function (r) { return r.json(); }).then(function (d) {
      if (!d.available) { root.textContent = "Findings not built yet: " + (d.reason || ""); return; }
      render(root, d);
      var mq = window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)");
      if (mq && mq.addEventListener) mq.addEventListener("change", function () { render(root, d); });
      new MutationObserver(function () { render(root, d); }).observe(document.documentElement,
        { attributes: true, attributeFilter: ["data-theme", "class"] });
    }).catch(function (e) { root.textContent = "Could not load findings (" + e + ")."; });
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", start);
  else start();
  window.SlipdayFindings = { render: render };
})();
