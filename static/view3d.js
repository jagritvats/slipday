/* Slipday 3-D view: the real elevation grid around a site as a lit surface you can turn, with the
   directions to the Sun and the Earth and the shadow at a chosen time.

   No library.  The surface is drawn by a small WebGL renderer written here (smooth per-vertex normals,
   light from the Sun's true direction, the server's ray-cast shadow as a smooth texture, height contours,
   landing rings draped on the ground).  WebGL draws to a canvas that is never put in the page; every
   frame its picture is copied into the one visible 2-D canvas, and the arrows and labels are drawn on
   top with the 2-D context.  Where WebGL is not available (or gives a blank picture) the same scene is
   drawn by a painter's-algorithm renderer on the 2-D canvas alone.

   window.SlipdayView3D.show(container, {
     site: { id } or { lat, lon, name },   at: 'ISO time of the landing (UTC)',
     windowHours: 336,                      // the landing window the time slider steps through
     marks: [{ lat, lon, label }],          // optional points to flag, e.g. the ridge that hides the Sun
     mastM: 2, minSunFraction: 0.5, earthMarginDeg: 0,     // the same rules as the rest of the page
     scatterM: 100,                         // radius of the landing-scatter ring round the site (0: none)
     circlesM: [250, 500, 1000],            // optional further rings round the site, metres
     exaggeration: 2,                       // optional starting vertical scale (1, 2 or 3)
     renderer: 'canvas2d'                   // optional: do not use WebGL
   })
   Data: GET /api/terrain3d (slipday/view3d.py).  Heights are real; the shadow is a ray-cast on the same grid. */
(function () {
  'use strict';

  var R_M = 1737400;
  var SIZES = [4, 8, 16];                      /* half-width of the patch, km */
  var SCALE_BAR = { 4: 1, 8: 2, 16: 5 };       /* km */
  var MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
  var DEFAULT_VE = 2;                          /* heights are drawn twice as tall unless the reader chooses otherwise; the picture says so */
  var LIT = [227, 221, 207], DARK = [38, 45, 69], WALL = [104, 100, 92];
  var SUN = '#ff9d4d', EARTH = '#6fb1ff', INK = '#f4f3ee', INK2 = '#c3c1b7', MARK = '#ffd166';
  var EXPOSURE = 0.07;                         /* brightness = c / (c + EXPOSURE), c the cosine between the slope's normal and the Sun */
  var FRAME_MS = 900;                          /* playing: time given to one step of the slider */
  var AHEAD = 4, MAX_INFLIGHT = 2;             /* frames asked for ahead of the playhead; requests open at once */
  var SPIN = 3.2 * Math.PI / 180;              /* gentle turn while playing, radians a second */
  var UP = 4;                                  /* the shadow texture has this many texels per grid cell (Catmull-Rom) */
  var PITCH0 = 27, FOVY = 26 * Math.PI / 180;

  function make(tag, cls, text) {
    var e = document.createElement(tag);
    if (cls) { e.className = cls; }
    if (text !== undefined) { e.textContent = text; }
    return e;
  }
  function rad(d) { return d * Math.PI / 180; }
  function clamp(v, a, b) { return Math.max(a, Math.min(b, v)); }
  function smooth(a, b, x) { var t = clamp((x - a) / (b - a), 0, 1); return t * t * (3 - 2 * t); }
  function fmtTime(ms) {
    var d = new Date(ms);
    return d.getUTCDate() + ' ' + MONTHS[d.getUTCMonth()] + ' ' + d.getUTCFullYear() + ' ' +
      ('0' + d.getUTCHours()).slice(-2) + ':' + ('0' + d.getUTCMinutes()).slice(-2) + ' UTC';
  }
  function fmtDist(m) { return m < 1000 ? Math.round(m) + ' m' : (m / 1000).toFixed(m % 1000 ? 1 : 0) + ' km'; }
  function compass(az) {
    return ['N', 'NNE', 'NE', 'ENE', 'E', 'ESE', 'SE', 'SSE', 'S', 'SSW', 'SW', 'WSW', 'W', 'WNW', 'NW', 'NNW'][Math.round(((az % 360) + 360) % 360 / 22.5) % 16];
  }
  /* east/north offset (m) of a point from the site, along the great circle (the frame the API lays the patch out in) */
  function localXY(lat0, lon0, lat, lon) {
    var p1 = rad(lat0), p2 = rad(lat), dl = rad(lon - lon0);
    var c = clamp(Math.sin(p1) * Math.sin(p2) + Math.cos(p1) * Math.cos(p2) * Math.cos(dl), -1, 1);
    var d = Math.acos(c) * R_M;
    var b = Math.atan2(Math.sin(dl) * Math.cos(p2), Math.cos(p1) * Math.sin(p2) - Math.sin(p1) * Math.cos(p2) * Math.cos(dl));
    return { x: d * Math.sin(b), y: d * Math.cos(b), d: d, az: (b * 180 / Math.PI + 360) % 360 };
  }
  function sunVec(b) { var a = rad(b.az_deg), e = rad(b.el_deg); return [Math.sin(a) * Math.cos(e), Math.cos(a) * Math.cos(e), Math.sin(e)]; }
  function fillVec(s) { var l = Math.sqrt(s[0] * s[0] + s[1] * s[1] + 0.3025) || 1; return [-s[0] / l, -s[1] / l, 0.55 / l]; }

  /* ---------- 4 x 4 matrices, column-major ---------- */
  function mul(a, b) {
    var o = new Float32Array(16), c, r;
    for (c = 0; c < 4; c++) { for (r = 0; r < 4; r++) { o[c * 4 + r] = a[r] * b[c * 4] + a[4 + r] * b[c * 4 + 1] + a[8 + r] * b[c * 4 + 2] + a[12 + r] * b[c * 4 + 3]; } }
    return o;
  }
  function perspective(fovy, aspect, near, far) {
    var f = 1 / Math.tan(fovy / 2), o = new Float32Array(16);
    o[0] = f / aspect; o[5] = f; o[10] = (far + near) / (near - far); o[11] = -1; o[14] = 2 * far * near / (near - far);
    return o;
  }
  function lookAt(e, t) {                       /* up is +z */
    var fx = t[0] - e[0], fy = t[1] - e[1], fz = t[2] - e[2], fl = Math.sqrt(fx * fx + fy * fy + fz * fz);
    fx /= fl; fy /= fl; fz /= fl;
    var sx = fy, sy = -fx, sl = Math.sqrt(sx * sx + sy * sy) || 1; sx /= sl; sy /= sl;      /* f x up */
    var ux = sy * fz, uy = -sx * fz, uz = sx * fy - sy * fx;                                  /* s x f */
    var o = new Float32Array(16);
    o[0] = sx; o[1] = ux; o[2] = -fx; o[4] = sy; o[5] = uy; o[6] = -fy; o[8] = 0; o[9] = uz; o[10] = -fz;
    o[12] = -(sx * e[0] + sy * e[1]); o[13] = -(ux * e[0] + uy * e[1] + uz * e[2]); o[14] = fx * e[0] + fy * e[1] + fz * e[2]; o[15] = 1;
    return o;
  }

  /* ---------- the shadow as a smooth field: one value per grid node, made four times finer ---------- */
  function upsample(a, n) {                    /* a: Float32Array n*n in 0..1; returns Uint8Array T*T, T = (n-1)*UP+1; passes through the nodes */
    var T = (n - 1) * UP + 1, tmp = new Float32Array(n * T), out = new Uint8Array(T * T), w = [], p, t, i, j, X, Y, k, v;
    for (p = 0; p < UP; p++) {
      t = p / UP;
      w.push([-0.5 * t * t * t + t * t - 0.5 * t, 1.5 * t * t * t - 2.5 * t * t + 1, -1.5 * t * t * t + 2 * t * t + 0.5 * t, 0.5 * t * t * t - 0.5 * t * t]);
    }
    for (j = 0; j < n; j++) {
      for (X = 0; X < T; X++) {
        i = Math.floor(X / UP); k = w[X % UP]; var r = j * n;
        tmp[j * T + X] = k[0] * a[r + Math.max(0, i - 1)] + k[1] * a[r + i] + k[2] * a[r + Math.min(n - 1, i + 1)] + k[3] * a[r + Math.min(n - 1, i + 2)];
      }
    }
    for (Y = 0; Y < T; Y++) {
      j = Math.floor(Y / UP); k = w[Y % UP];
      var r0 = Math.max(0, j - 1) * T, r1 = j * T, r2 = Math.min(n - 1, j + 1) * T, r3 = Math.min(n - 1, j + 2) * T;
      for (X = 0; X < T; X++) {
        v = k[0] * tmp[r0 + X] + k[1] * tmp[r1 + X] + k[2] * tmp[r2 + X] + k[3] * tmp[r3 + X];
        out[Y * T + X] = v <= 0 ? 0 : (v >= 1 ? 255 : Math.round(v * 255));
      }
    }
    return out;
  }

  /* ---------- WebGL ---------- */
  var VS_T = 'attribute vec4 aPos; attribute vec2 aGrad; uniform mat4 uMVP; uniform float uVe; uniform float uHalf;' +
    'varying vec3 vN; varying vec2 vUV; varying vec2 vXY; varying float vH;' +
    'void main(){ vN = vec3(-aGrad, 1.0); vXY = aPos.xy / uHalf; vUV = vec2(aPos.x, -aPos.y) / (2.0 * uHalf) + 0.5; vH = aPos.w;' +
    ' gl_Position = uMVP * vec4(aPos.xy, aPos.z * uVe, 1.0); }';
  var FS_T = '#ifdef GL_FRAGMENT_PRECISION_HIGH\nprecision highp float;\n#else\nprecision mediump float;\n#endif\n' +
    'varying vec3 vN; varying vec2 vUV; varying vec2 vXY; varying float vH;' +
    'uniform sampler2D uA; uniform sampler2D uB; uniform float uMix; uniform float uT; uniform float uCont; uniform float uPx;' +
    'uniform vec3 uSun; uniform vec3 uFill; uniform float uRing[5];' +
    'void main(){' +
    ' vec3 n = normalize(vN);' +
    ' float lam = max(dot(n, uSun), 0.0);' +
    ' float tone = lam / (lam + ' + EXPOSURE.toFixed(3) + ');' +
    ' vec2 uv = (vUV * (uT - 1.0) + 0.5) / uT;' +
    ' float f = mix(texture2D(uA, uv).r, texture2D(uB, uv).r, uMix);' +
    ' float lit = smoothstep(0.15, 0.85, f);' +
    ' float fill = 0.52 + 0.48 * max(dot(n, uFill), 0.0);' +
    ' vec3 col = mix(vec3(' + (DARK[0] / 255).toFixed(3) + ',' + (DARK[1] / 255).toFixed(3) + ',' + (DARK[2] / 255).toFixed(3) + ') * fill,' +
    '   vec3(' + (LIT[0] / 255).toFixed(3) + ',' + (LIT[1] / 255).toFixed(3) + ',' + (LIT[2] / 255).toFixed(3) + ') * (0.20 + 0.95 * tone), lit);' +
    '\n#ifdef DERIV\n' +
    ' float hc = vH / uCont; float wc = max(fwidth(hc), 0.00001);' +
    ' float dc = abs(fract(hc - 0.5) - 0.5) / wc;' +
    ' float ca = (1.0 - smoothstep(0.35, 1.25, dc)) * clamp(1.5 - wc * 4.0, 0.0, 1.0);' +
    ' col = mix(col, mix(vec3(0.44, 0.50, 0.66), vec3(0.30, 0.27, 0.23), lit), ca * 0.42);' +
    ' float dr = length(vXY); float wr = max(fwidth(dr), 0.000001);' +
    '\n#else\n' +
    ' float dr = length(vXY); float wr = uPx;' +
    '\n#endif\n' +
    ' for (int k = 0; k < 5; k++) { float r = uRing[k]; if (r > 0.0) {' +
    '   float wpx = (k == 0) ? 1.5 : 0.9;' +
    '   float a = 1.0 - smoothstep(wpx, wpx + 1.2, abs(dr - r) / wr);' +
    '   col = mix(col, (k == 0) ? vec3(1.0) : vec3(0.80, 0.86, 0.95), a * ((k == 0) ? 0.95 : 0.62)); } }' +
    ' gl_FragColor = vec4(col, 1.0); }';
  var VS_W = 'attribute vec3 aPos; attribute float aT; uniform mat4 uMVP; uniform float uVe; varying float vT;' +
    'void main(){ vT = aT; gl_Position = uMVP * vec4(aPos.xy, aPos.z * uVe, 1.0); }';
  var FS_W = 'precision mediump float; varying float vT; uniform vec3 uCol; void main(){ gl_FragColor = vec4(uCol * (1.0 - 0.5 * vT), 1.0); }';

  function initGL(onLost) {
    var c = document.createElement('canvas'), gl = null, attrs = { antialias: true, alpha: true, premultipliedAlpha: true, depth: true, stencil: false };
    try { gl = c.getContext('webgl', attrs) || c.getContext('experimental-webgl', attrs); } catch (e) { gl = null; }
    if (!gl) { return null; }
    var deriv = !!gl.getExtension('OES_standard_derivatives');
    function shader(type, src) {
      var s = gl.createShader(type); gl.shaderSource(s, src); gl.compileShader(s);
      return gl.getShaderParameter(s, gl.COMPILE_STATUS) ? s : null;
    }
    function program(vs, fs, names, attribs) {
      var a = shader(gl.VERTEX_SHADER, vs), b = shader(gl.FRAGMENT_SHADER, fs);
      if (!a || !b) { return null; }
      var p = gl.createProgram(); gl.attachShader(p, a); gl.attachShader(p, b);
      attribs.forEach(function (nm, i) { gl.bindAttribLocation(p, i, nm); });
      gl.linkProgram(p);
      if (!gl.getProgramParameter(p, gl.LINK_STATUS)) { return null; }
      var o = { p: p, u: {} };
      names.forEach(function (nm) { o.u[nm] = gl.getUniformLocation(p, nm); });
      return o;
    }
    var pt = program(VS_T, (deriv ? '#extension GL_OES_standard_derivatives : enable\n#define DERIV 1\n' : '') + FS_T,
      ['uMVP', 'uVe', 'uHalf', 'uA', 'uB', 'uMix', 'uT', 'uCont', 'uPx', 'uSun', 'uFill', 'uRing'], ['aPos', 'aGrad']);
    var pwl = program(VS_W, FS_W, ['uMVP', 'uVe', 'uCol'], ['aPos', 'aT']);
    if (!pt || !pwl) { return null; }
    function tex() {
      var t = gl.createTexture(); gl.bindTexture(gl.TEXTURE_2D, t);
      gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.LINEAR); gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.LINEAR);
      gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE); gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE);
      return t;
    }
    gl.pixelStorei(gl.UNPACK_ALIGNMENT, 1);
    var g = { gl: gl, canvas: c, deriv: deriv, pt: pt, pw: pwl, vb: gl.createBuffer(), ib: gl.createBuffer(), wb: gl.createBuffer(),
      tA: tex(), tB: tex(), inA: null, inB: null, mesh: null, checked: false };
    c.addEventListener('webglcontextlost', function (ev) { ev.preventDefault(); onLost(); });
    return g;
  }

  function build(container) {
    var st = {
      opts: null, half: 4, n: 81, ve: DEFAULT_VE, yaw: rad(-28), pitch: rad(PITCH0), zoom: 1, autoView: true,
      data: null, frames: {}, pending: {}, inflight: 0, gen: 0, pos: 0, want: 0, stepH: 6, steps: 0, t0: 0,
      playing: false, spin: false, key: '', raf: 0, lastTs: 0, textIdx: -1, glx: null, glTried: false, renderer: '',
      placed: [], off: false, failed: false, veChosen: false
    };
    var calm = !!(window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches);
    container.innerHTML = '';
    var root = make('div', 'v3d');
    var bar = make('div', 'v3dBar');
    var lSize = make('label', 'inline', 'Area ');
    var selSize = make('select'); selSize.setAttribute('aria-label', 'Size of the terrain patch');
    SIZES.forEach(function (h) { var o = make('option', '', (2 * h) + ' km across'); o.value = String(h); selSize.appendChild(o); });
    lSize.appendChild(selSize);
    var lVe = make('label', 'inline', 'Heights ');
    var selVe = make('select'); selVe.setAttribute('aria-label', 'Vertical scale');
    [[1, 'true scale (1x)'], [2, 'exaggerated 2x'], [3, 'exaggerated 3x']].forEach(function (v) { var o = make('option', '', v[1]); o.value = String(v[0]); selVe.appendChild(o); });
    selVe.value = String(st.ve);
    lVe.appendChild(selVe);
    var btns = make('span', 'v3dBtns');
    function btn(text, label, fn) {
      var b = make('button', '', text); b.type = 'button'; b.setAttribute('aria-label', label); b.title = label;
      b.addEventListener('click', function () { st.spin = false; fn(); schedule(); });
      btns.appendChild(b); return b;
    }
    btn('Turn left', 'Turn the terrain to the left', function () { st.yaw -= rad(15); });
    btn('Turn right', 'Turn the terrain to the right', function () { st.yaw += rad(15); });
    btn('Higher', 'Look from higher up', function () { st.pitch = clamp(st.pitch + rad(8), rad(6), rad(85)); });
    btn('Lower', 'Look from lower down', function () { st.pitch = clamp(st.pitch - rad(8), rad(6), rad(85)); });
    btn('+', 'Zoom in', function () { st.zoom = clamp(st.zoom * 1.25, 0.5, 6); });
    btn('-', 'Zoom out', function () { st.zoom = clamp(st.zoom / 1.25, 0.5, 6); });
    btn('Reset view', 'Reset the view', function () { var c = cur(); st.pitch = rad(PITCH0); st.zoom = 1; st.yaw = c ? sunSide(c.sun.az_deg) : rad(-28); });
    bar.appendChild(lSize); bar.appendChild(lVe); bar.appendChild(btns);

    var stage = make('div', 'v3dStage');
    var canvas = make('canvas'); canvas.tabIndex = 0; canvas.setAttribute('role', 'img');
    canvas.setAttribute('aria-label', '3-D view of the terrain around the site');
    var msg = make('div', 'v3dMsg'); msg.setAttribute('role', 'status'); msg.hidden = true;
    stage.appendChild(canvas); stage.appendChild(msg);

    var timeRow = make('div', 'v3dTime');
    var play = make('button', 'v3dPlay', 'Play'); play.type = 'button'; play.setAttribute('aria-pressed', 'false');
    var slider = make('input'); slider.type = 'range'; slider.min = '0'; slider.max = '0'; slider.step = '1'; slider.value = '0';
    slider.setAttribute('aria-label', 'Time within the landing window');
    var out = make('output', 'v3dWhen');
    timeRow.appendChild(play); timeRow.appendChild(slider); timeRow.appendChild(out);

    var stateP = make('p', 'v3dState'); stateP.setAttribute('aria-live', 'polite');
    var cap = make('p', 'v3dCap note');
    var more = make('details', 'v3dMore'), moreSum = make('summary', '', 'What is real and what is derived in this picture'), moreP = make('p', 'note');
    more.appendChild(moreSum); more.appendChild(moreP);
    root.appendChild(bar); root.appendChild(stage); root.appendChild(timeRow); root.appendChild(stateP); root.appendChild(cap); root.appendChild(more);
    container.appendChild(root);
    var ctx = canvas.getContext('2d');

    /* The starting view has the Sun ahead and to the left, so that ridges are lit from the side and their shadows fall across the picture. */
    function sunSide(sunAz) { return rad(((sunAz + 62) % 360 + 540) % 360 - 180); }

    /* ---------- data ---------- */
    function timeAt(i) { return st.t0 + i * st.stepH * 3600000; }
    function url(i, withHeights) {
      var o = st.opts, s = o.site, q = 'at=' + encodeURIComponent(new Date(timeAt(i)).toISOString().slice(0, 19) + 'Z') +
        '&half_km=' + st.half + '&n=' + st.n + '&mast_m=' + (o.mastM === undefined ? 2 : o.mastM);
      q += s.id ? '&site=' + encodeURIComponent(s.id) : '&lat=' + s.lat + '&lon=' + s.lon + (s.name ? '&name=' + encodeURIComponent(s.name) : '');
      if (o.minSunFraction !== undefined) { q += '&min_sun_fraction=' + o.minSunFraction; }
      if (o.earthMarginDeg !== undefined) { q += '&earth_margin_deg=' + o.earthMarginDeg; }
      if (!withHeights) { q += '&heights=false'; }
      return '/api/terrain3d?' + q;
    }
    function sayLater(text) {                 /* only if the wait turns out to be noticeable: no flicker while playing */
      if (st.sayText === text) { return; }
      st.sayText = text; clearTimeout(st.sayTimer);
      st.sayTimer = setTimeout(function () { say(text); }, 450);
    }
    function say(text, withRetry) {
      clearTimeout(st.sayTimer); st.sayText = text || '';
      msg.textContent = text || '';
      msg.hidden = !text;
      if (withRetry) {
        var b = make('button', '', 'Try again'); b.type = 'button';
        b.addEventListener('click', function () { st.failed = false; say(''); pump(); });
        msg.appendChild(document.createTextNode(' ')); msg.appendChild(b);
      }
    }
    function setData(j) {
      var n = j.n, half = j.half_km * 1000, sp = j.spacing_m, z = new Float32Array(n * n), raw = new Float32Array(n * n), i, k, q;
      for (k = 0; k < n * n; k++) {             /* display height: true metres in the site's level frame (the Moon's curve lowers the far ground) */
        var x = -half + (k % n) * sp, y = half - Math.floor(k / n) * sp, v = j.heights_m[k];
        raw[k] = (v === null || v === undefined) ? j.height_range_m[0] : v;
        z[k] = raw[k] - (x * x + y * y) / (2 * R_M);
      }
      var qx = new Float32Array((n - 1) * (n - 1)), qy = new Float32Array((n - 1) * (n - 1));
      for (k = 0; k < n - 1; k++) {
        for (i = 0; i < n - 1; i++) {
          q = k * n + i;
          qx[k * (n - 1) + i] = ((z[q + 1] - z[q]) + (z[q + n + 1] - z[q + n])) / (2 * sp);
          qy[k * (n - 1) + i] = ((z[q] - z[q + n]) + (z[q + 1] - z[q + n + 1])) / (2 * sp);      /* row k is north of row k + 1 */
        }
      }
      var span = j.height_range_m[1] - j.height_range_m[0];
      st.data = { z: z, raw: raw, qx: qx, qy: qy, n: n, half: half, spacing: sp, dem: j.dem, site: j.site, range: j.height_range_m, skyline: j.skyline,
        contour: span < 400 ? 20 : (span < 900 ? 50 : (span < 2500 ? 100 : 200)) };
    }
    function makeFrame(j) {
      var s = j.shadow.shade, a = new Float32Array(s.length), k;
      for (k = 0; k < s.length; k++) { a[k] = (s.charCodeAt(k) - 48 + 0.5) / 10; }     /* digit d: between d and d + 1 tenths of the disc */
      return { frac: a, tex: null, sun: j.sun, earth: j.earth, shadow: j.shadow, at: j.at_utc };
    }
    function fetchFrame(i, withHeights, tries) {
      var gen = st.gen;
      st.pending[i] = true; st.inflight += 1;
      function done() { if (gen === st.gen) { st.inflight -= 1; delete st.pending[i]; } }
      fetch(url(i, withHeights), st.abort ? { signal: st.abort.signal } : undefined).then(function (r) {
        return r.json().then(function (j) { return { ok: r.ok, status: r.status, j: j, wait: parseInt(r.headers.get('Retry-After') || '20', 10) }; });
      }).then(function (res) {
        if (gen !== st.gen) { return; }
        if (res.status === 503 && tries < 4) {          /* the queue for new work is full: a frame is short, so ask again soon */
          var wait = Math.min(isFinite(res.wait) ? res.wait : 20, 6);
          if (i === st.want || !st.data) { say('The server is busy with other requests; trying again in ' + wait + ' s.'); }
          st.retry = setTimeout(function () { if (gen !== st.gen) { return; } done(); fetchFrame(i, withHeights, tries + 1); }, wait * 1000);
          return;
        }
        done();
        if (!res.ok) { st.failed = true; stopPlay(); say(typeof res.j.detail === 'string' ? res.j.detail : 'The terrain could not be loaded (' + res.status + ').', true); return; }
        var j = res.j;
        if (!j.available) {
          stopPlay(); st.data = null; st.frames = {}; st.off = true; say('No 3-D view here: ' + (j.reason || 'not available') + '.');
          root.classList.add('off'); schedule(); texts(); return;
        }
        root.classList.remove('off');
        if (withHeights) { setData(j); }
        if (!st.data) { return; }
        st.frames[i] = makeFrame(j);
        if (st.autoView && i === st.want) { st.autoView = false; st.yaw = sunSide(j.sun.az_deg); }
        if (!st.playing && i === st.want) { st.pos = i; say(''); }
        texts(); schedule(); pump();
      }).catch(function (e) {
        if (gen !== st.gen) { return; }
        done();
        if (e && e.name === 'AbortError') { return; }
        st.failed = true; stopPlay(); say('The terrain could not be loaded: ' + e.message + '.', true);
      });
    }
    /* Ask for what is needed next, never more than MAX_INFLIGHT requests at a time. */
    function pump() {
      if (!st.opts || !st.t0 || st.off || st.failed) { return; }
      if (!st.data) { if (!st.inflight) { say('Loading the terrain...'); fetchFrame(st.want, true, 0); } return; }
      var base = st.playing ? Math.floor(st.pos + 1e-6) : st.want, k, i;
      for (k = 0; k <= (st.playing ? AHEAD : 1); k++) {
        i = base + k;
        if (i >= 0 && i <= st.steps && !st.frames[i] && !st.pending[i] && st.inflight < MAX_INFLIGHT) { fetchFrame(i, false, 0); }
      }
      if (!st.playing && !st.frames[st.want]) { sayLater('Working out the shadow for ' + fmtTime(timeAt(st.want)) + '...'); }
    }
    function reload() {                       /* new site, plan, patch size or resolution */
      stopPlay();
      if (st.abort) { try { st.abort.abort(); } catch (e) { /* nothing to stop */ } }
      st.abort = window.AbortController ? new AbortController() : null;
      clearTimeout(st.retry);
      st.gen += 1; st.inflight = 0; st.pending = {}; st.frames = {}; st.data = null; st.off = false; st.failed = false; st.pos = st.want; st.textIdx = -1;
      schedule(); texts();
      pump();
    }

    /* ---------- what is on show: two neighbouring frames and how far between them the playhead is ---------- */
    function mixBody(p, q, m) {
      if (!q || !m) { return p; }
      var daz = ((q.az_deg - p.az_deg + 540) % 360) - 180, src = m < 0.5 ? p : q;
      return { az_deg: (p.az_deg + daz * m + 360) % 360, el_deg: p.el_deg + (q.el_deg - p.el_deg) * m, up: src.up, skyline_km: src.skyline_km };
    }
    function cur() {
      var a = Math.min(Math.floor(st.pos + 1e-9), st.steps), m = st.pos - a, A = st.frames[a], B = st.frames[a + 1];
      if (!A) { return null; }
      if (!B || m < 0.001) { B = A; m = 0; }
      return { A: A, B: B, m: m, near: m >= 0.5 ? B : A, nearIdx: m >= 0.5 ? a + 1 : a, sun: mixBody(A.sun, B.sun, m), earth: mixBody(A.earth, B.earth, m) };
    }

    /* ---------- the camera ---------- */
    function camera(W, H) {
      var d = st.data, half = d.half, ve = st.ve;
      var zLo = d.range[0] - half * half / R_M, zHi = d.range[1];
      var baseT = zLo - Math.max(40, 0.08 * (zHi - zLo)), base = baseT * ve, top = zHi * ve;
      var t = Math.tan(FOVY / 2), aspect = W / H, cp = Math.cos(st.pitch), sp = Math.sin(st.pitch);
      var D = Math.max(1.66 * half / (t * aspect), (1.5 * half * sp + 0.56 * (top - base) * cp + 0.08 * half) / (t * 0.80)) / st.zoom;
      var target = [0, 0, (top + base) / 2];
      var eye = [-D * cp * Math.sin(st.yaw), -D * cp * Math.cos(st.yaw), target[2] + D * sp];
      var m = mul(perspective(FOVY, aspect, Math.max(D * 0.03, 1), D + 3.4 * half + (top - base)), lookAt(eye, target));
      m[1] -= m[3] * 14 / H; m[5] -= m[7] * 14 / H; m[9] -= m[11] * 14 / H; m[13] -= m[15] * 14 / H;      /* the block sits 7 px low: room for the notes on top */
      return { m: m, eye: eye, D: D, base: base, baseT: baseT, W: W, H: H, px: 2 * D * t / H };
    }
    function proj(cam, x, y, z) {               /* z already exaggerated; returns [screen x, screen y, depth] */
      var m = cam.m, w = m[3] * x + m[7] * y + m[11] * z + m[15];
      if (w < 1e-6) { w = 1e-6; }
      return [(0.5 + 0.5 * (m[0] * x + m[4] * y + m[8] * z + m[12]) / w) * cam.W, (0.5 - 0.5 * (m[1] * x + m[5] * y + m[9] * z + m[13]) / w) * cam.H, w];
    }
    function rings() {                          /* metres: the landing scatter first, then the caller's circles */
      var o = st.opts || {}, r = [o.scatterM === undefined ? 100 : +o.scatterM], half = st.data ? st.data.half : 4000;
      (o.circlesM || []).forEach(function (v) { v = +v; if (isFinite(v) && v > 0 && r.length < 5 && r.indexOf(v) < 0) { r.push(v); } });
      return r.map(function (v) { return isFinite(v) && v > 0 && v < half ? v : 0; });
    }

    /* ---------- the surface, with WebGL ---------- */
    function meshGL(g) {
      var gl = g.gl, d = st.data, n = d.n, half = d.half, sp = d.spacing, v = new Float32Array(n * n * 6), i, j, k, a;
      for (j = 0; j < n; j++) {
        for (i = 0; i < n; i++) {
          k = j * n + i; a = k * 6;
          var zl = d.z[j * n + Math.max(0, i - 1)], zr = d.z[j * n + Math.min(n - 1, i + 1)], zn = d.z[Math.max(0, j - 1) * n + i], zs = d.z[Math.min(n - 1, j + 1) * n + i];
          v[a] = -half + i * sp; v[a + 1] = half - j * sp; v[a + 2] = d.z[k]; v[a + 3] = d.raw[k];
          v[a + 4] = (zr - zl) / ((Math.min(n - 1, i + 1) - Math.max(0, i - 1)) * sp);
          v[a + 5] = (zn - zs) / ((Math.min(n - 1, j + 1) - Math.max(0, j - 1)) * sp);
        }
      }
      var idx = new Uint16Array((n - 1) * (n - 1) * 6), q = 0;
      for (j = 0; j < n - 1; j++) {
        for (i = 0; i < n - 1; i++) { k = j * n + i; idx[q++] = k; idx[q++] = k + n; idx[q++] = k + 1; idx[q++] = k + 1; idx[q++] = k + n; idx[q++] = k + n + 1; }
      }
      gl.bindBuffer(gl.ARRAY_BUFFER, g.vb); gl.bufferData(gl.ARRAY_BUFFER, v, gl.STATIC_DRAW);
      gl.bindBuffer(gl.ELEMENT_ARRAY_BUFFER, g.ib); gl.bufferData(gl.ELEMENT_ARRAY_BUFFER, idx, gl.STATIC_DRAW);
      /* four walls down to the plinth: top and bottom vertex for every node of each edge (z in true metres, like the surface) */
      var zLo = d.range[0] - half * half / R_M, baseT = zLo - Math.max(40, 0.08 * (d.range[1] - zLo)), w = new Float32Array(4 * n * 2 * 4), p = 0;
      function edge(i0, j0, di, dj) {
        for (var e = 0; e < n; e++) {
          var ii = i0 + e * di, jj = j0 + e * dj, x = -half + ii * sp, y = half - jj * sp;
          w[p++] = x; w[p++] = y; w[p++] = d.z[jj * n + ii]; w[p++] = 0;
          w[p++] = x; w[p++] = y; w[p++] = baseT; w[p++] = 1;
        }
      }
      edge(0, n - 1, 1, 0); edge(0, 0, 1, 0); edge(0, 0, 0, 1); edge(n - 1, 0, 0, 1);       /* south, north, west, east */
      gl.bindBuffer(gl.ARRAY_BUFFER, g.wb); gl.bufferData(gl.ARRAY_BUFFER, w, gl.STATIC_DRAW);
      g.mesh = d; g.count = idx.length;
    }
    function texGL(g, unit, t, frame, slot) {
      var gl = g.gl, d = st.data, T = (d.n - 1) * UP + 1;
      gl.activeTexture(unit); gl.bindTexture(gl.TEXTURE_2D, t);
      if (g[slot] !== frame) {
        if (!frame.tex) { frame.tex = upsample(frame.frac, d.n); }
        gl.texImage2D(gl.TEXTURE_2D, 0, gl.LUMINANCE, T, T, 0, gl.LUMINANCE, gl.UNSIGNED_BYTE, frame.tex);
        g[slot] = frame;
      }
      return T;
    }
    function wallTone(nx, ny, s) { var l = Math.sqrt(s[0] * s[0] + s[1] * s[1]) || 1; return 0.42 + 0.50 * Math.max(0, (nx * s[0] + ny * s[1]) / l); }
    function drawGL(cam, c, pw, ph) {
      var g = st.glx, gl = g.gl, d = st.data, n = d.n;
      if (gl.isContextLost()) { return false; }
      if (g.canvas.width !== pw || g.canvas.height !== ph) { g.canvas.width = pw; g.canvas.height = ph; }
      gl.viewport(0, 0, pw, ph); gl.clearColor(0, 0, 0, 0); gl.clear(gl.COLOR_BUFFER_BIT | gl.DEPTH_BUFFER_BIT);
      gl.enable(gl.DEPTH_TEST); gl.disable(gl.BLEND); gl.disable(gl.CULL_FACE);
      if (g.mesh !== d) { meshGL(g); g.inA = g.inB = null; }
      var s = sunVec(c.sun), f = fillVec(s), u = g.pt.u, r = rings(), k;
      gl.useProgram(g.pt.p);
      var T = texGL(g, gl.TEXTURE0, g.tA, c.A, 'inA'); texGL(g, gl.TEXTURE1, g.tB, c.B, 'inB');
      gl.uniformMatrix4fv(u.uMVP, false, cam.m); gl.uniform1f(u.uVe, st.ve); gl.uniform1f(u.uHalf, d.half);
      gl.uniform1i(u.uA, 0); gl.uniform1i(u.uB, 1); gl.uniform1f(u.uMix, c.m); gl.uniform1f(u.uT, T);
      gl.uniform1f(u.uCont, d.contour); gl.uniform1f(u.uPx, cam.px * (cam.H / ph) / d.half);
      gl.uniform3f(u.uSun, s[0], s[1], s[2]); gl.uniform3f(u.uFill, f[0], f[1], f[2]);
      gl.uniform1fv(u.uRing, new Float32Array([0, 1, 2, 3, 4].map(function (q) { return (r[q] || 0) / d.half; })));
      gl.bindBuffer(gl.ARRAY_BUFFER, g.vb);
      gl.enableVertexAttribArray(0); gl.enableVertexAttribArray(1);
      gl.vertexAttribPointer(0, 4, gl.FLOAT, false, 24, 0); gl.vertexAttribPointer(1, 2, gl.FLOAT, false, 24, 16);
      gl.bindBuffer(gl.ELEMENT_ARRAY_BUFFER, g.ib);
      gl.drawElements(gl.TRIANGLES, g.count, gl.UNSIGNED_SHORT, 0);
      gl.useProgram(g.pw.p);
      gl.uniformMatrix4fv(g.pw.u.uMVP, false, cam.m); gl.uniform1f(g.pw.u.uVe, st.ve);
      gl.bindBuffer(gl.ARRAY_BUFFER, g.wb);
      gl.vertexAttribPointer(0, 3, gl.FLOAT, false, 16, 0); gl.vertexAttribPointer(1, 1, gl.FLOAT, false, 16, 12);
      var tones = [wallTone(0, -1, s), wallTone(0, 1, s), wallTone(-1, 0, s), wallTone(1, 0, s)];
      for (k = 0; k < 4; k++) {
        gl.uniform3f(g.pw.u.uCol, WALL[0] / 255 * tones[k], WALL[1] / 255 * tones[k], WALL[2] / 255 * tones[k]);
        gl.drawArrays(gl.TRIANGLE_STRIP, k * 2 * n, 2 * n);
      }
      if (!g.checked) {                         /* once: is there really a picture?  If not, the 2-D renderer takes over. */
        g.checked = true;
        var t = document.createElement('canvas'); t.width = 16; t.height = 16;
        var tc = t.getContext('2d'); tc.drawImage(g.canvas, 0, 0, 16, 16);
        var px = tc.getImageData(0, 0, 16, 16).data, seen = 0;
        for (k = 3; k < px.length; k += 4) { if (px[k] > 0) { seen += 1; } }
        if (seen < 4) { return false; }
      }
      return true;
    }

    /* ---------- the surface, without WebGL: quads painted far to near ---------- */
    function drawFlat(cam, c) {
      var d = st.data, n = d.n, half = d.half, sp = d.spacing, ve = st.ve, i, j, k;
      var px = new Float32Array(n * n), py = new Float32Array(n * n);
      for (j = 0; j < n; j++) {
        for (i = 0; i < n; i++) { var p = proj(cam, -half + i * sp, half - j * sp, d.z[j * n + i] * ve); px[j * n + i] = p[0]; py[j * n + i] = p[1]; }
      }
      var s = sunVec(c.sun), fl = fillVec(s), A = c.A.frac, B = c.B.frac, m = c.m;
      ctx.lineWidth = 0.7; ctx.lineJoin = 'round';
      function quad(i, j) {
        var a = j * n + i, b = a + 1, e = a + n, cc = e + 1, q = j * (n - 1) + i, gx = d.qx[q], gy = d.qy[q], nl = Math.sqrt(gx * gx + gy * gy + 1);
        var lam = Math.max(0, (-gx * s[0] - gy * s[1] + s[2]) / nl), tone = lam / (lam + EXPOSURE);
        var f = (A[a] + A[b] + A[e] + A[cc]) / 4;
        if (m) { f = f * (1 - m) + m * (B[a] + B[b] + B[e] + B[cc]) / 4; }
        var lit = smooth(0.15, 0.85, f), fill = 0.52 + 0.48 * Math.max(0, (-gx * fl[0] - gy * fl[1] + fl[2]) / nl), bl = (0.20 + 0.95 * tone) * lit, bd = fill * (1 - lit);
        var col = 'rgb(' + Math.round(DARK[0] * bd + LIT[0] * bl) + ',' + Math.round(DARK[1] * bd + LIT[1] * bl) + ',' + Math.round(DARK[2] * bd + LIT[2] * bl) + ')';
        ctx.beginPath(); ctx.moveTo(px[a], py[a]); ctx.lineTo(px[b], py[b]); ctx.lineTo(px[cc], py[cc]); ctx.lineTo(px[e], py[e]); ctx.closePath();
        ctx.fillStyle = col; ctx.strokeStyle = col; ctx.fill(); ctx.stroke();
      }
      /* far to near on both sides of the viewer's own row and column: right for any viewpoint above a height field */
      var ic = clamp(Math.round((cam.eye[0] + half) / sp), 0, n - 1), jc = clamp(Math.round((half - cam.eye[1]) / sp), 0, n - 1);
      function rowOf(j) { for (i = 0; i < ic; i++) { quad(i, j); } for (i = n - 2; i >= ic; i--) { quad(i, j); } }
      for (j = 0; j < jc; j++) { rowOf(j); }
      for (j = n - 2; j >= jc; j--) { rowOf(j); }
      function wall(i0, j0, di, dj, tone) {
        ctx.beginPath();
        var p0 = proj(cam, -half + i0 * sp, half - j0 * sp, cam.base); ctx.moveTo(p0[0], p0[1]);
        for (k = 0; k < n; k++) { var a = (j0 + k * dj) * n + (i0 + k * di); ctx.lineTo(px[a], py[a]); }
        var p1 = proj(cam, -half + (i0 + (n - 1) * di) * sp, half - (j0 + (n - 1) * dj) * sp, cam.base); ctx.lineTo(p1[0], p1[1]); ctx.closePath();
        ctx.fillStyle = 'rgb(' + Math.round(WALL[0] * tone * 0.8) + ',' + Math.round(WALL[1] * tone * 0.8) + ',' + Math.round(WALL[2] * tone * 0.8) + ')';
        ctx.fill();
      }
      if (cam.eye[1] < -half) { wall(0, n - 1, 1, 0, wallTone(0, -1, s)); } else if (cam.eye[1] > half) { wall(0, 0, 1, 0, wallTone(0, 1, s)); }
      if (cam.eye[0] < -half) { wall(0, 0, 0, 1, wallTone(-1, 0, s)); } else if (cam.eye[0] > half) { wall(n - 1, 0, 0, 1, wallTone(1, 0, s)); }
    }

    /* ---------- drawing ---------- */
    function schedule() { if (!st.raf) { st.raf = requestAnimationFrame(tick); } }
    function tick(ts) {
      st.raf = 0;
      var dt = Math.min(120, st.lastTs ? ts - st.lastTs : 16); st.lastTs = ts;
      if (st.playing) {
        var lim = Math.floor(st.pos + 1e-9);
        while (lim < st.steps && st.frames[lim + 1]) { lim += 1; }
        var np = Math.min(st.pos + dt / FRAME_MS, lim);
        if (np < st.pos) { np = st.pos; }
        if (np >= lim && lim < st.steps) { sayLater('Working out the shadow for ' + fmtTime(timeAt(lim + 1)) + '...'); } else if (st.sayText) { say(''); }
        st.pos = np; st.want = Math.round(np);
        if (st.spin && !calm) { st.yaw += SPIN * dt / 1000; }
        timeUI();
        if (np >= st.steps) { stopPlay(); } else { pump(); }
      }
      var c = st.data ? cur() : null;
      if (c && c.nearIdx !== st.textIdx) { texts(); }
      draw(c);
      if (st.playing) { schedule(); } else { st.lastTs = 0; }
    }
    function sky(W, H) {
      var g = ctx.createRadialGradient(W / 2, H, 0, W / 2, H, Math.max(W, H) * 0.95);
      g.addColorStop(0, '#262930'); g.addColorStop(0.6, '#131418'); g.addColorStop(1, '#0b0b0d');
      ctx.fillStyle = g; ctx.fillRect(0, 0, W, H);
    }
    function draw(c) {
      var W = canvas.clientWidth, H = canvas.clientHeight, dpr = Math.min(2, window.devicePixelRatio || 1);
      if (!W || !H) { return; }
      var pw = Math.round(W * dpr), ph = Math.round(H * dpr);
      if (canvas.width !== pw || canvas.height !== ph) { canvas.width = pw; canvas.height = ph; }
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      ctx.clearRect(0, 0, W, H);
      sky(W, H);
      st.placed = [];
      var d = st.data;
      if (!d || !c) { return; }
      var cam = camera(W, H), ok = false;
      if (!st.glTried) {
        st.glTried = true;
        var force = (st.opts && st.opts.renderer) || window.SlipdayView3D.renderer || (/[?&]v3d=2d\b/.test(window.location.search) ? 'canvas2d' : '');
        if (force !== 'canvas2d' && force !== '2d') { st.glx = initGL(function () { st.glx = null; schedule(); }); }
      }
      if (st.glx) {
        try { ok = drawGL(cam, c, pw, ph); } catch (e) { ok = false; }
        if (ok) { ctx.drawImage(st.glx.canvas, 0, 0, W, H); } else { st.glx = null; }
      }
      if (!ok) { drawFlat(cam, c); }
      st.renderer = ok ? 'webgl' : 'canvas2d';
      overlays(cam, c, W, H, !ok);
    }

    function overlays(cam, c, W, H, flat) {
      var d = st.data, n = d.n, half = d.half, sp = d.spacing, ve = st.ve, narrow = W < 520, labels = [], blocks = [];
      function P(x, y, z) { return proj(cam, x, y, z); }
      function ground(x, y) {                  /* display height at an east/north offset inside the patch */
        var fi = clamp((x + half) / sp, 0, n - 1.001), fj = clamp((half - y) / sp, 0, n - 1.001);
        var i0 = Math.floor(fi), j0 = Math.floor(fj), u = fi - i0, v = fj - j0, a = j0 * n + i0;
        return (d.z[a] * (1 - u) * (1 - v) + d.z[a + 1] * u * (1 - v) + d.z[a + n] * (1 - u) * v + d.z[a + n + 1] * u * v) * ve;
      }
      function edgeDist(az) { var a = rad(az); return half / Math.max(Math.abs(Math.sin(a)), Math.abs(Math.cos(a))); }
      /* pr: lower is kept first.  fixed: a corner note that is not moved.  wrap: widest line in px. */
      function label(text, x, y, o) {
        labels.push({ text: text, x: x, y: y, col: o.col || INK, al: o.al || 'left', bold: !!o.bold, pr: o.pr === undefined ? 5 : o.pr,
          fixed: !!o.fixed, pill: o.pill || '', wrap: o.wrap || (narrow ? 150 : 300), size: o.size || 12 });
      }
      function block(x, y, r) { blocks.push([x - r, y - r, x + r, y + r]); }
      function arrowHead(p, ang, colour, size) {
        ctx.fillStyle = colour; ctx.beginPath();
        ctx.moveTo(p[0] + size * Math.cos(ang), p[1] + size * Math.sin(ang));
        ctx.lineTo(p[0] + size * 0.64 * Math.cos(ang + 2.5), p[1] + size * 0.64 * Math.sin(ang + 2.5));
        ctx.lineTo(p[0] + size * 0.64 * Math.cos(ang - 2.5), p[1] + size * 0.64 * Math.sin(ang - 2.5)); ctx.closePath(); ctx.fill();
      }
      function line(a, b, colour, width, dash, alpha) {
        ctx.save(); ctx.globalAlpha = alpha === undefined ? 1 : alpha; ctx.strokeStyle = colour; ctx.lineWidth = width; ctx.setLineDash(dash || []); ctx.lineCap = 'round';
        ctx.beginPath(); ctx.moveTo(a[0], a[1]); ctx.lineTo(b[0], b[1]); ctx.stroke(); ctx.restore();
      }

      /* rings on the ground: with WebGL they are part of the surface; without it they are drawn here */
      var rr = rings();
      if (flat) {
        rr.forEach(function (r, k) {
          if (!r) { return; }
          ctx.beginPath();
          for (var a = 0; a <= 72; a++) { var x = r * Math.sin(a * Math.PI / 36), y = r * Math.cos(a * Math.PI / 36), p = P(x, y, ground(x, y)); if (a) { ctx.lineTo(p[0], p[1]); } else { ctx.moveTo(p[0], p[1]); } }
          ctx.strokeStyle = k === 0 ? 'rgba(255,255,255,.95)' : 'rgba(204,219,242,.62)'; ctx.lineWidth = k === 0 ? 1.8 : 1.1; ctx.stroke();
        });
      }
      rr.forEach(function (r, k) {               /* each ring is named where it is furthest to the right in the picture */
        if (!r || (narrow && k > 0)) { return; }
        var x = r * Math.cos(st.yaw), y = -r * Math.sin(st.yaw), p = P(x, y, ground(x, y));
        label(k === 0 ? (narrow ? 'scatter ' + fmtDist(r) : 'landing scatter ' + fmtDist(r)) : fmtDist(r), p[0] + 5, p[1] + (k === 0 ? 11 : 0),
          { col: k === 0 ? INK : '#cddbf2', pr: k === 0 ? 4.5 : 8, size: 11 });
      });

      /* compass on the plinth; north has an arrow */
      var off = half * 1.1;
      var nA = P(0, half * 1.015, cam.base), nB = P(0, half * 1.075, cam.base);
      line(nA, nB, INK, 2); arrowHead(nB, Math.atan2(nB[1] - nA[1], nB[0] - nA[0]), INK, 9);
      (narrow ? [['N', 0, half * 1.17]] : [['N', 0, half * 1.17], ['E', off, 0], ['S', 0, -off], ['W', -off, 0]]).forEach(function (q) {
        var p = P(q[1], q[2], cam.base);
        label(q[0] === 'N' && !narrow ? 'N (north)' : q[0], p[0], p[1], { col: q[0] === 'N' ? INK : INK2, al: 'center', bold: q[0] === 'N', pr: q[0] === 'N' ? 3 : 7 });
      });
      /* scale bar along the edge of the plinth that faces the viewer */
      var barKm = SCALE_BAR[Math.round(half / 1000)] || Math.max(1, Math.round(half / 4000)), bl = barKm * 1000, e0, e1;
      var cy = Math.cos(st.yaw), sy = Math.sin(st.yaw);
      if (Math.abs(cy) >= Math.abs(sy)) { var ys = cy >= 0 ? -half : half; e0 = P(-half, ys, cam.base); e1 = P(-half + bl, ys, cam.base); }
      else { var xs = sy >= 0 ? -half : half; e0 = P(xs, -half, cam.base); e1 = P(xs, -half + bl, cam.base); }
      e0[1] += 9; e1[1] += 9;
      line(e0, e1, INK, 3);
      line([e0[0], e0[1] - 4], [e0[0], e0[1] + 4], INK, 1.5); line([e1[0], e1[1] - 4], [e1[0], e1[1] + 4], INK, 1.5);
      label(barKm + ' km', (e0[0] + e1[0]) / 2, Math.max(e0[1], e1[1]) + 12, { al: 'center', pr: 3.5, size: 11.5 });

      /* rays from the site to the Sun and to the Earth: straight lines in this frame */
      var mast = (st.opts.mastM === undefined ? 2 : st.opts.mastM) * ve;
      function ray(body, colour, name, pr) {
        /* the ray keeps one length in space, so a body high in the sky does not run off the picture */
        var az = rad(body.az_deg), tanEl = Math.tan(rad(body.el_deg)), far = edgeDist(body.az_deg) * 0.97 * Math.cos(rad(body.el_deg));
        function at(dd) { return P(dd * Math.sin(az), dd * Math.cos(az), mast + dd * tanEl * ve); }
        /* a body behind the skyline: the line of sight is solid up to where it meets the ground of this patch, dashed beyond */
        var stop = null, dd;
        if (!body.up) {
          for (dd = sp; dd < far; dd += sp / 2) { if (ground(dd * Math.sin(az), dd * Math.cos(az)) > mast + dd * tanEl * ve) { stop = dd; break; } }
        }
        var p0 = at(0), p1 = at(stop === null ? far : stop), p2 = at(far);
        line(p0, p1, 'rgba(8,8,10,.55)', 5);
        line(p0, p1, colour, 2.6, body.up || stop !== null ? [] : [7, 5]);
        if (stop !== null) {                   /* past the terrain that hides it: dashed */
          line(p1, p2, colour, 1.6, [3, 6]);
          ctx.fillStyle = colour; ctx.beginPath(); ctx.arc(p1[0], p1[1], 4, 0, 6.2832); ctx.fill();
        }
        /* a thin line from the end of the ray to the ground under it shows how low over the terrain the ray runs */
        var gx = far * Math.sin(az), gy = far * Math.cos(az), pg = P(gx, gy, ground(gx, gy));
        line(p2, pg, colour, 1, [2, 3], 0.6);
        var ang = Math.atan2(p2[1] - p0[1], p2[0] - p0[0]);
        arrowHead(p2, ang, colour, 11);
        var gxp = p2[0] + 24 * Math.cos(ang), gyp = p2[1] + 24 * Math.sin(ang);          /* a small sign for the body itself: direction only, not its size or distance */
        gxp = clamp(gxp, 14, W - 14); gyp = clamp(gyp, 30, H - 14);
        ctx.save();
        if (name === 'Sun') {
          var gl = ctx.createRadialGradient(gxp, gyp, 2, gxp, gyp, 17);
          gl.addColorStop(0, body.up ? 'rgba(255,214,140,.85)' : 'rgba(255,170,90,.25)'); gl.addColorStop(1, 'rgba(255,170,90,0)');
          ctx.fillStyle = gl; ctx.beginPath(); ctx.arc(gxp, gyp, 17, 0, 6.2832); ctx.fill();
        }
        ctx.beginPath(); ctx.arc(gxp, gyp, 6, 0, 6.2832);
        if (body.up) { ctx.fillStyle = name === 'Sun' ? '#ffd58a' : colour; ctx.fill(); }
        else { ctx.fillStyle = 'rgba(12,12,14,.7)'; ctx.fill(); ctx.setLineDash([3, 2.5]); }
        ctx.strokeStyle = colour; ctx.lineWidth = 1.6; ctx.stroke();
        if (name === 'Earth' && body.up) { ctx.setLineDash([]); ctx.strokeStyle = 'rgba(255,255,255,.75)'; ctx.lineWidth = 1.2; ctx.beginPath(); ctx.arc(gxp, gyp, 3.2, 3.5, 5.6); ctx.stroke(); }
        ctx.restore();
        block(gxp, gyp, 9);
        var el = Math.abs(body.el_deg).toFixed(1) + '°', txt;
        if (narrow) { txt = name + ' ' + (body.el_deg < 0 ? '-' : '') + el + (body.up ? '' : ', hidden'); }
        else {
          txt = name + ' ' + el + (body.el_deg >= 0 ? ' above level' : ' below level') + (body.up ? (name === 'Sun' ? ', up' : ', in view') : ', behind the skyline') +
            (!body.up && stop === null && body.skyline_km ? ' (ground ' + body.skyline_km.toFixed(1) + ' km away)' : '');
        }
        var left = Math.cos(ang) < 0;
        label(txt, gxp + (left ? -12 : 12), gyp, { col: colour, al: left ? 'right' : 'left', bold: true, pr: pr, wrap: narrow ? 120 : 230, size: 12.5 });
      }
      ray(c.earth, EARTH, 'Earth', 1.2);
      ray(c.sun, SUN, 'Sun', 1.1);

      /* marks passed in by the page (for example the ridge that hides the Sun): one label for marks at the same place */
      var groups = [], tol = 0.02 * half;        /* 1% of the width of the patch */
      (st.opts.marks || []).forEach(function (m) {
        if (!m || typeof m.lat !== 'number' || typeof m.lon !== 'number') { return; }
        var q = localXY(d.site.lat, d.site.lon, m.lat, m.lon), inside = Math.abs(q.x) <= half && Math.abs(q.y) <= half, x = q.x, y = q.y;
        if (!inside) { var ed = edgeDist(q.az); x = ed * Math.sin(rad(q.az)); y = ed * Math.cos(rad(q.az)); }
        var text = String(m.label || 'mark').replace(/\s+/g, ' ').trim() || 'mark', g = null, k;
        for (k = 0; k < groups.length; k++) { if (groups[k].inside === inside && Math.hypot(groups[k].x - x, groups[k].y - y) <= tol) { g = groups[k]; break; } }
        if (!g) { g = { inside: inside, x: x, y: y, az: q.az, items: [] }; groups.push(g); }
        if (!g.items.some(function (it) { return it.text === text; })) { g.items.push({ text: text, d: q.d }); }
      });
      groups.forEach(function (g, gi) {
        var ds = g.items.map(function (it) { return it.d; }), same = Math.max.apply(null, ds) - Math.min.apply(null, ds) < 100, p, text;
        if (same) { text = g.items.map(function (it) { return it.text; }).join('; ') + (g.inside ? ' (' + fmtDist(ds[0]) + ')' : ', ' + (ds[0] / 1000).toFixed(1) + ' km' + (narrow ? '' : ' that way')); }
        else { text = g.items.map(function (it) { return it.text + ' (' + (it.d / 1000).toFixed(1) + ' km)'; }).join('; ') + (g.inside || narrow ? '' : ', that way'); }
        if (g.inside) {
          var gz = ground(g.x, g.y), top; p = P(g.x, g.y, gz); top = [p[0], p[1] - 26];
          line(p, top, 'rgba(8,8,10,.55)', 4); line(p, top, MARK, 2);
          ctx.fillStyle = MARK; ctx.strokeStyle = 'rgba(8,8,10,.7)'; ctx.lineWidth = 1; ctx.beginPath(); ctx.arc(top[0], top[1], 4.5, 0, 6.2832); ctx.fill(); ctx.stroke();
          block(top[0], top[1], 6);
          label(text, top[0] + 9, top[1] - 4, { col: MARK, bold: true, pr: 2 + gi * 0.01, wrap: narrow ? 140 : 250 });
        } else {
          var gz2 = ground(g.x * 0.999, g.y * 0.999), p2 = P(g.x * 1.07, g.y * 1.07, gz2); p = P(g.x, g.y, gz2);
          var an = Math.atan2(p2[1] - p[1], p2[0] - p[0]), lf = Math.cos(an) < 0;
          line(p, p2, 'rgba(8,8,10,.55)', 4); line(p, p2, MARK, 2); arrowHead(p2, an, MARK, 9);
          block(p2[0], p2[1], 7);
          label(text, p2[0] + (lf ? -12 : 12), p2[1] + 12 * Math.sin(an), { col: MARK, al: lf ? 'right' : 'left', bold: true, pr: 2 + gi * 0.01, wrap: narrow ? 140 : 250 });
        }
      });

      /* the landing point itself */
      var s0 = P(0, 0, 0), s1 = [s0[0], s0[1] - 30];
      line(s0, s1, 'rgba(8,8,10,.55)', 4); line(s0, s1, INK, 2);
      ctx.fillStyle = '#ffffff'; ctx.strokeStyle = '#141414'; ctx.lineWidth = 1.5; ctx.beginPath(); ctx.arc(s1[0], s1[1], 5, 0, 6.2832); ctx.fill(); ctx.stroke();
      block(s1[0], s1[1], 7);
      var nm = String(d.site.name || 'landing point');
      if (narrow) { nm = nm.replace(/\s*\(.*\)\s*$/, ''); if (nm.length > 26) { nm = nm.slice(0, 25) + '…'; } }
      label(nm, s1[0] + 9, s1[1] - 6, { bold: true, pr: 1.5, wrap: narrow ? 150 : 280 });

      /* corner notes: the vertical scale (always, and loud when it is not true scale), the time, the data */
      label(ve === 1 ? 'Heights at true scale (1x)' : 'Heights exaggerated ' + ve + 'x', 10, 19,
        { col: ve === 1 ? INK : '#1c1a12', bold: true, pr: 0, fixed: true, pill: ve === 1 ? 'rgba(255,255,255,.13)' : MARK, size: narrow ? 12 : 13 });
      label(fmtTime(timeAt(Math.round(st.pos))), W - 10, 19, { col: INK, al: 'right', pr: 0.1, fixed: true, pill: 'rgba(255,255,255,.10)', size: narrow ? 11.5 : 12.5 });
      var grid = String(d.dem.label).split(';')[0].replace(/,/g, '');
      label(d.dem.synthetic ? 'SYNTHETIC TEST SURFACE, not the Moon' : (narrow ? grid + ' real heights; shadow ray-cast' : grid + ' elevation, real data; shadow ray-cast; contour lines every ' + d.contour + ' m'),
        10, H - 13, { col: d.dem.synthetic ? MARK : INK2, bold: !!d.dem.synthetic, pr: 0.2, fixed: true, size: 11.5, wrap: W - 20 });
      if (!narrow) { label('drag to turn; click, then scroll to zoom', W - 10, H - 13, { col: '#8f8e87', al: 'right', pr: 9, fixed: true, size: 11 }); }

      /* place the labels: most important first; one that would cover another is moved, or left out */
      labels.sort(function (a, b) { return a.pr - b.pr; });
      var boxes = blocks.slice();
      function hits(b) { for (var k = 0; k < boxes.length; k++) { var o = boxes[k]; if (b[0] < o[2] && b[2] > o[0] && b[1] < o[3] && b[3] > o[1]) { return true; } } return false; }
      labels.forEach(function (L) {
        ctx.font = (L.bold ? '600 ' : '') + L.size + 'px system-ui, -apple-system, "Segoe UI", Roboto, sans-serif';
        var words = L.text.split(' '), lines = [], curL = '', k;
        for (k = 0; k < words.length; k++) {
          var tryL = curL ? curL + ' ' + words[k] : words[k];
          if (curL && ctx.measureText(tryL).width > L.wrap) { lines.push(curL); curL = words[k]; } else { curL = tryL; }
        }
        lines.push(curL);
        var lh = Math.round(L.size * 1.25), padX = L.pill ? 8 : 2, padY = L.pill ? 4 : 1, w = 0;
        lines.forEach(function (t) { w = Math.max(w, ctx.measureText(t).width); });
        var bw = w + 2 * padX, bh = lines.length * lh + 2 * padY, flip = L.al === 'left' ? 'right' : (L.al === 'right' ? 'left' : 'center');
        var tries = L.fixed ? [[L.al, 0]] : [[L.al, 0], [L.al, -(bh + 3)], [L.al, bh + 3], [flip, 0], [L.al, -2 * (bh + 3)], [L.al, 2 * (bh + 3)], [flip, -(bh + 3)], [flip, bh + 3]];
        for (k = 0; k < tries.length; k++) {
          var al = tries[k][0], x0 = al === 'center' ? L.x - bw / 2 : (al === 'right' ? L.x - bw - (al !== L.al ? 22 : 0) : L.x + (al !== L.al ? 22 : 0));
          var y0 = L.y - bh / 2 + tries[k][1];
          x0 = clamp(x0, 4, Math.max(4, W - bw - 4)); y0 = clamp(y0, 4, Math.max(4, H - bh - 4));
          var box = [x0 - 1, y0 - 1, x0 + bw + 1, y0 + bh + 1];
          if (hits(box)) { continue; }
          boxes.push(box);
          if (L.pill) {
            ctx.fillStyle = L.pill; ctx.beginPath();
            if (ctx.roundRect) { ctx.roundRect(x0, y0, bw, bh, 6); } else { ctx.rect(x0, y0, bw, bh); }
            ctx.fill();
          }
          ctx.textAlign = 'left'; ctx.textBaseline = 'middle'; ctx.lineJoin = 'round';
          lines.forEach(function (t, li) {
            var ty = y0 + padY + lh * (li + 0.5) + 0.5;
            if (!L.pill || L.pill !== MARK) { ctx.lineWidth = 3.2; ctx.strokeStyle = 'rgba(10,10,12,.86)'; ctx.strokeText(t, x0 + padX, ty); }
            ctx.fillStyle = L.col; ctx.fillText(t, x0 + padX, ty);
          });
          st.placed.push({ text: L.text, box: box.map(Math.round) });
          break;
        }
      });
    }

    /* ---------- words under the picture ---------- */
    function timeUI() {
      /* the time of the frame whose shadow and words are shown (the nearest step), not the in-between position */
      var i = Math.round(st.pos), h = i * st.stepH;
      slider.value = String(i);
      out.textContent = st.t0 ? fmtTime(timeAt(i)) + (h > 0.01 ? ' (touchdown + ' + (Math.abs(h - Math.round(h)) < 0.01 ? Math.round(h) : h.toFixed(1)) + ' h)' : ' (touchdown)') : '';
    }
    function texts() {
      var d = st.data, c = d ? cur() : null, f = c ? c.near : null;
      if (!st.playing) { out.textContent = st.t0 ? fmtTime(timeAt(st.want)) + (st.want ? ' (touchdown + ' + (st.want * st.stepH) + ' h)' : ' (touchdown)') : ''; }
      more.hidden = !(d && f);
      if (!d || !f) { stateP.textContent = ''; cap.textContent = ''; return; }
      st.textIdx = c.nearIdx;
      function line(b, name, upWord, downWord) {
        var sky = b.skyline_el_deg === undefined ? '' : '; the terrain skyline in that direction at this moment is at ' + b.skyline_el_deg.toFixed(2) + '°' +
          (b.skyline_el_deg < 0 ? ' (from high ground the skyline can dip below level)' : '') +
          (b.skyline_km !== null && b.skyline_km !== undefined ? ', set by ground ' +
            (b.skyline_km < 1 ? Math.round(b.skyline_km * 1000) + ' m' : b.skyline_km.toFixed(1) + ' km') + ' away' : '');
        return name + ': azimuth ' + b.az_deg.toFixed(0) + '° (' + compass(b.az_deg) + '), ' + Math.abs(b.el_deg).toFixed(2) + '° ' +
          (b.el_deg >= 0 ? 'above' : 'below') + ' the horizontal' + sky +
          ', so it is ' + (b.up ? upWord : downWord) + ' (' + (b.clear_deg >= 0 ? 'clears' : 'misses') + ' the skyline by ' + Math.abs(b.clear_deg).toFixed(2) + '°).';
      }
      stateP.textContent = fmtTime(Date.parse(f.at)) + '. ' + line(f.sun, 'Sun', 'up', 'behind the skyline') + ' ' + line(f.earth, 'Earth', 'in view', 'behind the skyline') +
        ' ' + f.shadow.lit_share_pct + '% of this patch is sunlit at this time.';
      canvas.setAttribute('aria-label', '3-D view of the terrain around ' + (d.site.name || 'the site') + '. ' + stateP.textContent);
      var drop = Math.round(d.half * d.half / (2 * R_M)), grid = String(d.dem.label).split(';')[0], rr = rings().filter(function (v) { return v > 0; });
      var veWords = st.ve === 1 ? 'drawn at true scale (1x)' : 'drawn exaggerated ' + st.ve + ' times so the relief reads (the picture says so; choose 1x for true scale)';
      var ringWords = rr.length ? ' The white ring round the landing point is the landing scatter, ' + fmtDist(rr[0]) + ' in radius' +
        (rr.length > 1 ? '; the paler rings are ' + rr.slice(1).map(fmtDist).join(', ') + ' from it' : '') + '.' : '';
      cap.textContent = (d.dem.synthetic ? 'SYNTHETIC TEST SURFACE, not the Moon. Heights ' + veWords + '. ' : 'Real: the heights, ' + grid + ' elevation data, ' + veWords +
        (d.dem.interpolated ? '; this grid is coarser than the picture’s cells, so the surface between grid points is interpolated' : '') + '. ') +
        'Derived: the shadow at the chosen time, ray-cast over the same grid from ' + f.shadow.observer_m + ' m above every cell (a cell counts as lit when the centre of the Sun’s disc clears the terrain), ' +
        'and the directions to the Sun and the Earth (JPL DE421). A rendering, not a measurement: how bright the ground looks.' + ringWords +
        ' Drag to turn the view; Play steps through the landing window.';
      moreP.textContent = 'Real: the heights, ' + grid + ', sampled every ' + Math.round(d.spacing) + ' m over ' + (2 * d.half / 1000) + ' km' +
        (d.dem.interpolated ? ' (these cells are finer than the grid, so the surface between grid points is interpolated)' : '') +
        '. Derived: the shadow. A ray goes from ' + f.shadow.observer_m + ' m above every cell towards the Sun, over the same grid out to ' + f.shadow.max_km +
        ' km on the curved Moon; a cell is dark when the centre of the Sun’s disc is behind terrain, and the edge of the shadow is soft where a cell sees part of the disc ' +
        '(taking the skyline as level across the disc). Between cells the shadow is interpolated smoothly; it passes through every cell’s own value. ' +
        'The far part of each ray is sampled more coarsely than the skyline behind the card’s numbers, ' +
        'so the picture is a guide and the card is the answer. Derived: the directions to the Sun and the Earth, from JPL DE421; "up" and "in view" use the ' +
        'same site skyline as the card; the small Sun and Earth signs show direction only. A rendering: the brightness of sunlit ground. Each point is shaded by the angle between its real slope ' +
        '(at true scale, whatever the vertical scale of the picture) and the real direction of the Sun, which grazes at ' + f.sun.el_deg.toFixed(1) + '° here; the result is brightened by a fixed curve so that grazing light shows, ' +
        'and shadowed ground is given a weak fill light so its shape stays readable. The thin lines are height contours every ' + d.contour + ' m' + (st.renderer === 'canvas2d' ? ' (not drawn by this browser)' : '') + '. ' +
        'While Play runs, shadows are worked out every ' + st.stepH + ' hours and the picture blends from one to the next; when it stops it shows a worked-out time. ' +
        (st.ve === 1 ? 'Heights are at true scale. ' : 'Heights are exaggerated ' + st.ve + ' times; the picture says so. ') +
        'The block is drawn in the site’s own level frame, so the Moon’s curvature lowers the ground by ' + drop + ' m at the middle of each edge. ' +
        (st.renderer === 'webgl' ? 'Drawn with WebGL.' : (st.renderer === 'canvas2d' ? 'Drawn without WebGL.' : ''));
    }

    /* ---------- time ---------- */
    function stopPlay() {
      var was = st.playing;
      st.playing = false; st.spin = false;
      play.textContent = 'Play'; play.setAttribute('aria-pressed', 'false');
      if (was) {                               /* rest on a worked-out frame, not between two */
        st.want = clamp(Math.round(st.pos), 0, st.steps);
        if (st.frames[st.want]) { st.pos = st.want; }
        if (st.sayText) { say(''); }
        texts(); schedule(); pump();
      }
    }
    play.addEventListener('click', function () {
      if (st.playing) { stopPlay(); return; }
      if (!st.data) { return; }
      if (st.want >= st.steps) { st.want = 0; }
      if (!st.frames[st.want]) { pump(); return; }
      st.pos = st.want; st.playing = true; st.spin = true; st.lastTs = 0;
      play.textContent = 'Pause'; play.setAttribute('aria-pressed', 'true');
      pump(); schedule();
    });
    slider.addEventListener('input', function () {       /* the label follows the thumb at once; the frame is asked for when it rests */
      stopPlay(); var i = parseInt(slider.value, 10) || 0; st.want = i;
      out.textContent = fmtTime(timeAt(i)) + (i ? ' (touchdown + ' + (i * st.stepH) + ' h)' : ' (touchdown)');
      if (st.frames[i]) { st.pos = i; say(''); texts(); schedule(); pump(); return; }
      clearTimeout(st.slideTimer);
      st.slideTimer = setTimeout(pump, 140);
    });
    selSize.addEventListener('change', function () { st.half = parseInt(selSize.value, 10) || 4; reload(); });
    selVe.addEventListener('change', function () { st.ve = parseInt(selVe.value, 10) || 1; st.veChosen = true; texts(); schedule(); });

    /* ---------- turning the view ---------- */
    var ptrs = {}, pinch = null, drag = null;
    function count() { return Object.keys(ptrs).length; }
    canvas.addEventListener('pointerdown', function (ev) {
      ptrs[ev.pointerId] = { x: ev.clientX, y: ev.clientY };
      st.spin = false;
      if (count() === 2) {
        var k = Object.keys(ptrs), a = ptrs[k[0]], b = ptrs[k[1]];
        pinch = { dist: Math.max(10, Math.hypot(a.x - b.x, a.y - b.y)), zoom: st.zoom }; drag = null;
      } else { drag = { x: ev.clientX, y: ev.clientY, id: ev.pointerId, touch: ev.pointerType === 'touch' }; }
      try { canvas.setPointerCapture(ev.pointerId); } catch (e) { /* older browsers */ }
      canvas.classList.add('drag');
    });
    canvas.addEventListener('pointermove', function (ev) {
      if (!ptrs[ev.pointerId]) { return; }
      ptrs[ev.pointerId] = { x: ev.clientX, y: ev.clientY };
      if (pinch && count() >= 2) {
        var k = Object.keys(ptrs), a = ptrs[k[0]], b = ptrs[k[1]];
        st.zoom = clamp(pinch.zoom * Math.hypot(a.x - b.x, a.y - b.y) / pinch.dist, 0.5, 6); schedule(); return;
      }
      if (!drag || ev.pointerId !== drag.id) { return; }
      st.yaw += (ev.clientX - drag.x) * 0.008;
      if (!drag.touch) { st.pitch = clamp(st.pitch + (ev.clientY - drag.y) * 0.006, rad(6), rad(85)); }   /* on touch, up and down scroll the page */
      drag.x = ev.clientX; drag.y = ev.clientY;
      schedule();
    });
    function endDrag(ev) {
      delete ptrs[ev.pointerId]; pinch = null; drag = null;
      var k = Object.keys(ptrs);
      if (k.length === 1) { drag = { x: ptrs[k[0]].x, y: ptrs[k[0]].y, id: +k[0], touch: ev.pointerType === 'touch' }; }
      if (!k.length) { canvas.classList.remove('drag'); }
    }
    canvas.addEventListener('pointerup', endDrag);
    canvas.addEventListener('pointercancel', endDrag);
    canvas.addEventListener('wheel', function (ev) {      /* the wheel zooms once the picture has been clicked; before that it scrolls the page as usual */
      if (document.activeElement !== canvas && !ev.ctrlKey) { return; }
      ev.preventDefault(); st.spin = false;
      st.zoom = clamp(st.zoom * Math.exp(-ev.deltaY * (ev.deltaMode === 1 ? 0.05 : 0.0016)), 0.5, 6); schedule();
    }, { passive: false });
    canvas.addEventListener('keydown', function (ev) {
      var used = true;
      if (ev.key === 'ArrowLeft') { st.yaw -= rad(6); } else if (ev.key === 'ArrowRight') { st.yaw += rad(6); }
      else if (ev.key === 'ArrowUp') { st.pitch = clamp(st.pitch + rad(4), rad(6), rad(85)); }
      else if (ev.key === 'ArrowDown') { st.pitch = clamp(st.pitch - rad(4), rad(6), rad(85)); }
      else if (ev.key === '+' || ev.key === '=') { st.zoom = clamp(st.zoom * 1.15, 0.5, 6); }
      else if (ev.key === '-') { st.zoom = clamp(st.zoom / 1.15, 0.5, 6); }
      else if (ev.key === ' ') { play.click(); used = true; } else { used = false; }
      if (used) { if (ev.key !== ' ') { st.spin = false; } ev.preventDefault(); schedule(); }
    });
    if (window.ResizeObserver) { new ResizeObserver(schedule).observe(stage); } else { window.addEventListener('resize', schedule); }

    st.setOptions = function (opts) {
      var s = opts.site || {}, t0 = Date.parse(opts.at);
      if (!st.veChosen && [1, 2, 3].indexOf(+opts.exaggeration) >= 0) { st.ve = +opts.exaggeration; selVe.value = String(st.ve); }
      if (!isFinite(t0) || (!s.id && (typeof s.lat !== 'number' || typeof s.lon !== 'number'))) {
        stopPlay(); st.opts = opts; st.key = ''; st.t0 = 0; st.data = null; st.frames = {}; say('Choose a site and a landing date to see the terrain.'); schedule(); texts(); return;
      }
      var hours = Math.max(0, Math.round(opts.windowHours || 0));
      var key = JSON.stringify([s.id || [s.lat, s.lon], opts.at, hours, opts.mastM, opts.minSunFraction, opts.earthMarginDeg]);
      st.opts = opts;
      if (key === st.key) { texts(); schedule(); return; }  /* same plan: only the marks or the rings may have changed */
      st.key = key; st.t0 = t0;
      st.stepH = hours > 15 * 24 ? 12 : 6;
      st.steps = Math.floor(hours / st.stepH);
      st.n = (container.clientWidth || window.innerWidth) < 520 ? 57 : 81;
      st.want = 0; st.pos = 0; slider.max = String(st.steps); slider.value = '0'; st.autoView = true;
      timeRow.hidden = st.steps < 1;
      reload();
    };
    st.handle = {
      update: function (o) { st.setOptions(o); },
      redraw: schedule,
      state: function () {
        var c = st.data ? cur() : null;
        return { ready: !!(st.data && c), half_km: st.half, n: st.n, timeIndex: Math.round(st.pos), position: st.pos, steps: st.steps, ve: st.ve, playing: st.playing,
          renderer: st.renderer, inFlight: st.inflight, framesHeld: Object.keys(st.frames).length, labels: st.placed.slice(),
          frameAt: c ? c.near.at : null, sunUp: c ? c.near.sun.up : null, earthUp: c ? c.near.earth.up : null };
      }
    };
    return st;
  }

  window.SlipdayView3D = {
    renderer: '',                               /* set to 'canvas2d' before show() to do without WebGL */
    show: function (container, opts) {
      if (!container) { return null; }
      /* the fold is open by default, so wait until the view comes near the screen before building
         the 3-D scene: the first screen never pays for it. The latest options are kept and used then. */
      if (!container.__slipday3d && !container.__v3dSeen && 'IntersectionObserver' in window) {
        container.__v3dOpts = opts || {};
        if (!container.__v3dObs) {
          var self = this;
          container.__v3dObs = new IntersectionObserver(function (ents) {
            if (!ents.some(function (e) { return e.isIntersecting; })) { return; }
            container.__v3dObs.disconnect(); container.__v3dSeen = true;
            self.show(container, container.__v3dOpts);
          }, { rootMargin: '300px 0px' });
          container.__v3dObs.observe(container);
        }
        return null;
      }
      var st = container.__slipday3d;
      if (!st) { st = container.__slipday3d = build(container); }
      st.setOptions(opts || {});
      return st.handle;
    }
  };
})();
