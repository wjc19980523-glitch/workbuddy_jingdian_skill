/* City scenic film — every frame is a pure function of time t.
 * window.TL (timeline.js, written by tools/build_timeline.py) holds the data; this file holds the look.
 * API for the renderer: __ready (promise), __seek(t), __motion(t0, t1) → px travelled on screen, __shotsAt(t).
 * Do not edit per city: everything city-specific lives in timeline.js.
 */
(function () {
  'use strict';
  const TL = window.TL;
  const W = TL.W, H = TL.H, P = 1400;
  const $ = (s) => document.querySelector(s);
  const clamp = (x, a = 0, b = 1) => Math.min(b, Math.max(a, x));
  const lerp = (a, b, t) => a + (b - a) * t;
  const seg = (t, a, b) => clamp((t - a) / (b - a));
  const E = {
    lin: (t) => t,
    inOut: (t) => (t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2),
    out: (t) => 1 - Math.pow(1 - t, 3),
    in: (t) => t * t * t,
    sine: (t) => -(Math.cos(Math.PI * t) - 1) / 2,
    expoOut: (t) => (t >= 1 ? 1 : 1 - Math.pow(2, -10 * t)),
    expoIn: (t) => (t <= 0 ? 0 : Math.pow(2, 10 * t - 10)),
    expoInOut: (t) => (t <= 0 ? 0 : t >= 1 ? 1 : t < 0.5 ? Math.pow(2, 20 * t - 10) / 2 : (2 - Math.pow(2, -20 * t + 10)) / 2),
    backOut: (t) => 1 + 2.4 * Math.pow(t - 1, 3) + 1.4 * Math.pow(t - 1, 2),
  };
  function spring(t, f = 1.6, z = 0.45) {   // 0 → 1 with overshoot; t in seconds
    if (t <= 0) return 0;
    const w = 2 * Math.PI * f, wd = w * Math.sqrt(1 - z * z);
    return 1 - Math.exp(-z * w * t) * (Math.cos(wd * t) + (z * w / wd) * Math.sin(wd * t));
  }
  // keyframes: [[t, {k: v}, ease?], ...] → interpolated object; ease belongs to the segment that ENDS at that key
  function keyed(t, ks) {
    if (t <= ks[0][0]) return Object.assign({}, ks[0][1]);
    for (let i = 1; i < ks.length; i++) {
      if (t <= ks[i][0]) {
        const [t0, a] = ks[i - 1], [t1, b, e] = ks[i];
        const u = (E[e || 'inOut'])(seg(t, t0, t1));
        const o = {};
        for (const k in b) o[k] = k === 'z' ? Math.exp(lerp(Math.log(a[k]), Math.log(b[k]), u)) : lerp(a[k], b[k], u);
        return o;
      }
    }
    return Object.assign({}, ks[ks.length - 1][1]);
  }
  function el(tag, cls, parent, html) {
    const e = document.createElement(tag);
    if (cls) e.className = cls;
    if (html != null) e.innerHTML = html;
    if (parent) parent.appendChild(e);
    return e;
  }
  const esc = (s) => String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;');

  // ------------------------------------------------------------------ motion probes (for the renderer's shutter)
  let PROBE = null, ROOTM = null, PFX = '';
  function project(m, x, y) {
    const p = m.transformPoint(new DOMPoint(x, y, 0, 1));
    const k = P / Math.max(60, P - p.z / p.w);
    return [540 + (p.x / p.w - 540) * k, 960 + (p.y / p.w - 960) * k];
  }
  function setM(e, m, key, w, h) {
    e.style.transform = m.toString();
    if (PROBE && key) {
      const G = [];
      for (let i = 0; i <= 8; i++) for (let j = 0; j <= 8; j++) G.push([(w * i) / 8, (h * j) / 8]);
      const pts = G.map(([x, y]) => {
        const s = project(m, x, y);
        return ROOTM ? (() => { const q = ROOTM.transformPoint(new DOMPoint(s[0], s[1])); return [q.x, q.y]; })() : s;
      });
      PROBE[PFX + key] = pts;
    }
  }
  function probePoint(key, x, y) { if (PROBE) PROBE[PFX + key] = [[x, y]]; }

  // ------------------------------------------------------------------ photos
  const IMG = {};   // src → {w,h}
  function photo(parent, im, frame) {
    frame = frame || { w: W, h: H };
    const e = el('div', 'ph grade', parent);
    const c0 = Math.max(frame.w / im.w, frame.h / im.h);
    e._w0 = im.w * c0; e._h0 = im.h * c0; e._fr = frame;
    e.style.width = e._w0 + 'px'; e.style.height = e._h0 + 'px';
    const i = el('img', null, e); i.src = im.src; i.decoding = 'sync';
    e._img = i;
    return e;
  }
  // camera on a photo: fx,fy focus (0..1) at frame centre, s zoom (1 = cover), r roll°, rx/ry tilt°, tx/ty/tz offsets
  function cam(e, c, key, extra) {
    const fr = e._fr, w0 = e._w0, h0 = e._h0;
    let s = c.s == null ? 1 : c.s, fx = c.fx == null ? 0.5 : c.fx, fy = c.fy == null ? 0.5 : c.fy;
    const th = Math.abs((c.r || 0) * Math.PI / 180);
    if (c.clamp !== false) {
      s *= Math.cos(th) + Math.max(fr.h / fr.w, fr.w / fr.h) * Math.sin(th) * 0.62 + Math.abs(c.rx || 0) / 90 + Math.abs(c.ry || 0) / 70;
      const hx = fr.w / 2 / (s * w0), hy = fr.h / 2 / (s * h0);
      fx = hx >= 0.5 ? 0.5 : clamp(fx, hx, 1 - hx);
      fy = hy >= 0.5 ? 0.5 : clamp(fy, hy, 1 - hy);
    }
    let m = new DOMMatrix();
    if (extra) m = m.multiply(extra);
    m = m.translate(fr.w / 2 + (c.tx || 0), fr.h / 2 + (c.ty || 0), c.tz || 0)
      .rotate(c.rx || 0, c.ry || 0, c.r || 0).scale(s).translate(-fx * w0, -fy * h0);
    setM(e, m, key, w0, h0);
  }

  // ------------------------------------------------------------------ text helpers
  function chars(parent, text, cls) {
    const box = el('div', 'txt ' + (cls || ''), parent);
    box._ch = [...text].map((c) => el('span', 'ch', box, c === ' ' ? '&nbsp;' : esc(c)));
    return box;
  }
  // per-character entrance: drop + blur + overshoot, staggered
  function animChars(box, lt, t0, opt) {
    opt = opt || {};
    const st = opt.stagger == null ? 0.055 : opt.stagger, dy = opt.dy == null ? 70 : opt.dy;
    box._ch.forEach((c, i) => {
      const u = lt - t0 - i * st;
      const sp = spring(u, opt.f || 1.7, opt.z || 0.5);
      const a = clamp(u / 0.18);
      const bl = (1 - clamp(u / 0.3)) * 14;
      c.style.opacity = a;
      c.style.transform = `translate(${(opt.dx || 0) * (1 - sp)}px, ${dy * (1 - sp)}px) scale(${lerp(opt.s0 || 1.35, 1, sp)})`;
      c.style.filter = bl > 0.2 ? `blur(${bl}px)` : 'none';
    });
  }
  function wipe(e, lt, t0, dur) {   // left → right reveal
    const u = E.out(seg(lt, t0, t0 + (dur || 0.45)));
    e.style.clipPath = `inset(-20px ${(1 - u) * 100}% -20px 0)`;
    e.style.opacity = u > 0 ? 1 : 0;
    e.style.transform = `translate(${(1 - u) * -30}px, 0)`;
  }
  function fade(e, lt, t0, dur, dy) {
    const u = E.out(seg(lt, t0, t0 + (dur || 0.4)));
    e.style.opacity = u;
    e.style.transform = `translate(0, ${(1 - u) * (dy == null ? 24 : dy)}px)`;
  }

  // ------------------------------------------------------------------ map
  const MAP = TL.map;
  const R = 6378137;
  const mx = (lon) => R * lon * Math.PI / 180;
  const my = (lat) => R * Math.log(Math.tan(Math.PI / 4 + lat * Math.PI / 360));
  const L = MAP.local;
  const Lx0 = mx(L.lon0), Lx1 = mx(L.lon1), Ly0 = my(L.lat0), Ly1 = my(L.lat1);
  const toPx = (lon, lat) => [(mx(lon) - Lx0) / (Lx1 - Lx0) * L.w, (Ly1 - my(lat)) / (Ly1 - Ly0) * L.h];
  TL.spots.forEach((s) => { const p = toPx(s.lon, s.lat); s.px = p[0]; s.py = p[1]; });

  function buildMap(root) {
    // each map image is its own layer at native size; the camera matrix (× its placement) is applied per frame —
    // one giant container would exceed Chrome's raster limits and drop tiles
    const M = {};
    if (MAP.wide) {
      const Wd = MAP.wide;
      const a = toPx(Wd.lon0, Wd.lat1), b = toPx(Wd.lon1, Wd.lat0);
      const wi = el('img', 'ph', root); wi.src = Wd.src;
      wi.style.width = Wd.w + 'px'; wi.style.height = Wd.h + 'px';
      M.wide = wi; M.wideM = new DOMMatrix().translate(a[0], a[1]).scale((b[0] - a[0]) / Wd.w, (b[1] - a[1]) / Wd.h);
    }
    const li = el('img', 'ph', root); li.src = MAP.local.src;
    li.style.width = L.w + 'px'; li.style.height = L.h + 'px';
    li.style.webkitMaskImage = 'radial-gradient(ellipse 50% 50% at 50% 50%, #000 86%, transparent 100%)';
    M.localImg = li; M.plane = li;
    root.style.background = 'linear-gradient(180deg, #9fb3c4 0%, #6d8296 30%, #233040 100%)';
    const fog = el('div', null, root);   // aerial haze towards the horizon
    fog.style.cssText = 'position:absolute;inset:0;pointer-events:none;background:linear-gradient(180deg, rgba(190,205,220,.85) 0%, rgba(190,205,220,.35) 14%, rgba(190,205,220,0) 32%)';
    M.fog = fog;
    const cv = el('canvas', null, root); cv.width = W; cv.height = H;
    M.cv = cv; M.ctx = cv.getContext('2d');
    M.show = (on) => { for (const e of [li, cv, M.wide, fog]) if (e) e.style.display = on ? 'block' : 'none'; };
    return M;
  }
  function mapMatrix(c) {   // c: cx, cy (local px), z, tilt°, head°, oy (screen y of the focus)
    return new DOMMatrix().translate(540, c.oy == null ? 1060 : c.oy).rotate(c.tilt || 0, 0, c.head || 0).scale(c.z).translate(-c.cx, -c.cy);
  }
  function mapDraw(M, c, opt) {
    const m = mapMatrix(c);
    setM(M.localImg, m, opt.key, L.w, L.h);
    if (M.wide) setM(M.wide, m.multiply(M.wideM), null);
    M.fog.style.opacity = clamp((c.tilt || 0) / 40);
    M.localImg.style.opacity = clamp((Math.log(c.z) - Math.log(0.17)) / (Math.log(0.3) - Math.log(0.17)));
    const ctx = M.ctx;
    ctx.clearRect(0, 0, W, H);
    const pr = (x, y) => project(m, x, y);
    // route
    const sp = TL.spots;
    if (opt.route > 0) {
      const n = sp.length - 1;
      const upto = opt.route * n;
      ctx.save();
      ctx.lineCap = 'round'; ctx.lineJoin = 'round';
      for (const pass of [[18, 'rgba(255,214,120,0.18)'], [5, 'rgba(255,226,150,0.95)']]) {
        ctx.beginPath(); ctx.lineWidth = pass[0]; ctx.strokeStyle = pass[1];
        if (pass[0] < 10) ctx.setLineDash([16, 12]);
        for (let i = 0; i <= Math.min(n, Math.ceil(upto)); i++) {
          let x = sp[i].px, y = sp[i].py;
          if (i > upto) { const f = upto - (i - 1); x = lerp(sp[i - 1].px, sp[i].px, f); y = lerp(sp[i - 1].py, sp[i].py, f); }
          const q = pr(x, y);
          if (i === 0) ctx.moveTo(q[0], q[1]); else ctx.lineTo(q[0], q[1]);
        }
        ctx.stroke();
      }
      ctx.restore();
    }
    // pins (the highlighted one first, so its label wins)
    const placed = [];
    const order = sp.map((_, i) => i).sort((a, b) => (b === opt.hi) - (a === opt.hi));
    order.forEach((i) => { const s = sp[i];
      const a = opt.pins ? opt.pins(i) : 0;
      if (a <= 0) return;
      const q = pr(s.px, s.py);
      const hi = opt.hi === i;
      const r = (hi ? 17 : 12) * (0.6 + 0.4 * E.backOut(clamp(a)));
      ctx.save();
      ctx.globalAlpha = clamp(a * 1.5);
      ctx.beginPath(); ctx.arc(q[0], q[1], r * 2.4, 0, 7); ctx.fillStyle = hi ? 'rgba(255,90,60,0.28)' : 'rgba(255,220,140,0.22)'; ctx.fill();
      ctx.beginPath(); ctx.arc(q[0], q[1], r, 0, 7); ctx.fillStyle = hi ? '#ff5a3c' : '#ffd36e'; ctx.fill();
      ctx.lineWidth = 4; ctx.strokeStyle = '#fff'; ctx.stroke();
      if (opt.labels) {
        const la = opt.labels(i);
        if (la > 0) {
          ctx.globalAlpha = clamp(la);
          ctx.font = `700 ${hi ? 46 : 36}px "Noto Serif CJK SC"`;
          const txt = s.name;
          const tw = ctx.measureText(txt).width, bh = hi ? 58 : 48;
          // try right, left, below, above of the pin; skip the label if every place collides with one already drawn
          const tries = [[30, -16], [-tw - 34, -16], [-tw / 2, 52], [-tw / 2, -40]];
          if (q[0] > 760) tries.unshift(tries.splice(1, 1)[0]);
          let spot = null;
          for (const [dx, dy] of tries) {
            const r = [q[0] + dx - 12, q[1] + dy - (hi ? 42 : 34), tw + 24, bh];
            if (r[0] < 20 || r[0] + r[2] > W - 20) continue;
            if (!placed.some((o) => r[0] < o[0] + o[2] && o[0] < r[0] + r[2] && r[1] < o[1] + o[3] && o[1] < r[1] + r[3])) { spot = [dx, dy, r]; break; }
          }
          if (spot) {
            placed.push(spot[2]);
            const lx = q[0] + spot[0], ly = q[1] + spot[1] + (1 - E.out(clamp(la))) * 20;
            ctx.fillStyle = 'rgba(0,0,0,0.5)';
            ctx.fillRect(lx - 12, ly - (hi ? 42 : 34), tw + 24, bh);
            ctx.fillStyle = '#fff'; ctx.fillText(txt, lx, ly + 2);
          }
        }
      }
      ctx.restore();
    });
    return m;
  }

  // ------------------------------------------------------------------ spot text layouts
  function buildText(root, spot, k) {
    const T = { k };
    const n = String(spot.index).padStart(2, '0'), N = String(TL.spots.length).padStart(2, '0');
    T.shade = el('div', null, root);
    T.shade.style.cssText = 'position:absolute;inset:0;pointer-events:none;';
    T.chip = el('div', 'txt shadow', root, `<span style="font:700 34px 'Noto Sans CJK SC';letter-spacing:2px">${n}</span><span style="font:400 24px 'Noto Sans CJK SC';opacity:.7"> / ${N}</span>`);
    T.name = chars(root, spot.name, 'serif shadow');
    T.where = el('div', 'txt shadow', root, `<span style="display:inline-block;width:14px;height:14px;border-radius:7px;background:#ff5a3c;margin-right:12px;vertical-align:2px"></span>${esc(spot.where)}`);
    T.where.style.font = "500 32px 'Noto Sans CJK SC'";
    T.facts = spot.facts.map((f) => {
      const d = el('div', 'txt shadow', root, esc(f));
      d.style.font = "500 44px 'Noto Sans CJK SC'"; d.style.lineHeight = '60px';
      return d;
    });
    T.src = el('div', 'txt shadow', root, '资料：' + esc(spot.src));
    T.src.style.font = "400 23px 'Noto Sans CJK SC'"; T.src.style.opacity = 0.8;
    T.credit = el('div', 'txt shadow', root);
    T.credit.style.cssText += "font:400 21px 'Noto Sans CJK SC';left:0;top:0;color:rgba(255,255,255,.82);";
    T.ai = el('div', 'tag', root, 'AI生成画面'); T.ai.style.left = '820px'; T.ai.style.top = '150px'; T.ai.style.display = 'none';
    const nameLen = [...spot.name].length;
    const L = ['lower', 'vertical', 'top', 'center'][k % 4];
    T.L = L;
    const pos = (e, x, y) => { e.style.left = x + 'px'; e.style.top = y + 'px'; };
    if (L === 'lower') {
      T.shade.style.background = 'linear-gradient(180deg, rgba(0,0,0,0) 45%, rgba(0,0,0,.62) 78%, rgba(0,0,0,.72) 100%)';
      pos(T.chip, 72, 1040);
      T.name.style.fontSize = (nameLen > 4 ? 128 : 150) + 'px'; pos(T.name, 64, 1085);
      pos(T.where, 76, 1290); T.facts.forEach((d, i) => pos(d, 76, 1350 + i * 66)); pos(T.src, 76, 1360 + T.facts.length * 66);
    } else if (L === 'vertical') {
      T.shade.style.background = 'linear-gradient(90deg, rgba(0,0,0,.55) 0%, rgba(0,0,0,0) 38%), linear-gradient(180deg, rgba(0,0,0,0) 55%, rgba(0,0,0,.66) 85%)';
      T.name.style.writingMode = 'vertical-rl'; T.name.style.fontSize = '160px'; T.name.style.letterSpacing = '6px';
      pos(T.chip, 78, 250); pos(T.name, 52, 310);
      pos(T.where, 76, 1240); T.facts.forEach((d, i) => pos(d, 76, 1300 + i * 66)); pos(T.src, 76, 1310 + T.facts.length * 66);
    } else if (L === 'top') {
      T.shade.style.background = 'linear-gradient(180deg, rgba(0,0,0,.66) 0%, rgba(0,0,0,.25) 32%, rgba(0,0,0,0) 48%), linear-gradient(180deg, rgba(0,0,0,0) 75%, rgba(0,0,0,.45) 100%)';
      pos(T.chip, 72, 230);
      T.name.style.fontSize = '150px'; pos(T.name, 64, 270);
      pos(T.where, 76, 475); T.facts.forEach((d, i) => pos(d, 76, 535 + i * 66)); pos(T.src, 76, 545 + T.facts.length * 66);
    } else {
      T.shade.style.background = 'radial-gradient(ellipse 90% 34% at 50% 50%, rgba(0,0,0,.6) 0%, rgba(0,0,0,0) 100%)';
      T.name.style.fontSize = '150px'; T.name.style.letterSpacing = '10px';
      T.center = true;
      pos(T.chip, 0, 700); T.chip.style.width = W + 'px'; T.chip.style.textAlign = 'center';
      T.name.style.width = W + 'px'; T.name.style.textAlign = 'center'; pos(T.name, 0, 740);
      T.where.style.width = W + 'px'; T.where.style.textAlign = 'center'; pos(T.where, 0, 945);
      T.facts.forEach((d, i) => { d.style.width = W + 'px'; d.style.textAlign = 'center'; pos(d, 0, 1005 + i * 66); });
      T.src.style.width = W + 'px'; T.src.style.textAlign = 'center'; pos(T.src, 0, 1015 + T.facts.length * 66);
    }
    pos(T.credit, 60, 1548);
    return T;
  }
  function animText(T, lt, D, img) {
    const out = E.in(seg(lt, D - 0.32, D + 0.05));
    T.shade.style.opacity = clamp(lt / 0.4) * (1 - out * 0.5);
    fade(T.chip, lt, 0.1, 0.35, 0);
    animChars(T.name, lt, 0.2, T.L === 'vertical' ? { dy: 0, dx: -60, stagger: 0.07 } : { stagger: 0.06 });
    if (T.center) {   // tracking tightens as it lands
      const u = E.expoOut(seg(lt, 0.2, 1.4));
      T.name.style.letterSpacing = lerp(60, 10, u) + 'px';
    }
    fade(T.where, lt, 0.55, 0.4);
    T.facts.forEach((d, i) => { wipe(d, lt, 0.8 + i * 0.32, 0.5); if (T.center) d.style.transform = 'none'; });
    fade(T.src, lt, 1.2 + T.facts.length * 0.2, 0.4, 0);
    if (img) {
      T.credit.textContent = (img.caption ? img.caption + '｜' : '') + img.credit;
      T.credit.style.opacity = 0.85 * clamp((lt - 0.4) / 0.3);
      T.ai.style.display = img.ai ? 'block' : 'none';
    }
    // exit: the block lifts and fades just before the cut
    for (const e of [T.chip, T.name, T.where, T.src, ...T.facts]) {
      if (out > 0) { e.style.opacity = (parseFloat(e.style.opacity) || 0) * (1 - out); }
    }
    T.name.style.transform = `translate(0, ${-60 * out}px)`;
    T.name.style.opacity = 1 - out;
  }

  // ------------------------------------------------------------------ recipes
  // each recipe: build(root, spot) → state; update(state, lt, D) → main image (for the credit line)
  const RECIPES = {};

  // ring: A settles with a roll, B opens inside a growing ring (iris) and trucks sideways
  RECIPES.ring = {
    build(root, s) {
      const st = { a: photo(root, s.images[0]) };
      if (s.images[1]) {
        st.b = photo(root, s.images[1]);
        st.ring = el('div', null, root);
        st.ring.style.cssText = 'position:absolute;left:0;top:0;border-radius:50%;border:6px solid rgba(255,255,255,.9);box-shadow:0 0 40px rgba(255,255,255,.6)';
      }
      return st;
    },
    update(st, lt, D, s) {
      const sp = spring(lt + 0.1, 0.9, 0.55);
      cam(st.a, { fx: 0.5, fy: 0.45, s: lerp(1.35, 1.06, sp) + 0.03 * lt / D, r: lerp(-9, 0, sp) }, 'a');
      if (!st.b) return s.images[0];
      const t1 = D * 0.48, u = seg(lt, t1, t1 + 0.75), ue = E.expoInOut(u);
      const rad = lerp(0, 1250, ue);
      st.b.style.display = u > 0 ? 'block' : 'none';
      st.b.style.clipPath = `circle(${rad}px at 540px 900px)`;
      const v = seg(lt, t1, D + 0.3);
      cam(st.b, { fx: lerp(0.25, 0.75, E.sine(v)), fy: 0.5, s: lerp(1.5, 1.12, E.expoOut(u)), r: lerp(8, 0, ue) }, 'b');
      st.ring.style.display = u > 0 && u < 1 ? 'block' : 'none';
      st.ring.style.width = st.ring.style.height = 2 * rad + 'px';
      st.ring.style.transform = `translate(${540 - rad - 6}px, ${900 - rad - 6}px)`;
      st.ring.style.opacity = 1 - u;
      probePoint('ring', 540 + rad, 900);
      return u > 0.5 ? s.images[1] : s.images[0];
    },
  };

  // tilt: crane up a tall subject, then punch into its centre and open the second image from inside (塔中塔)
  RECIPES.tilt = {
    build(root, s) {
      const st = { a: photo(root, s.images[0], { w: W, h: H * 1.0 }) };
      if (s.images[1]) st.b = photo(root, s.images[1]);
      return st;
    },
    update(st, lt, D, s) {
      const t1 = st.b ? D * 0.55 : D;
      const u = E.sine(seg(lt, -0.2, t1));
      const punch = st.b ? E.expoIn(seg(lt, t1 - 0.45, t1 + 0.1)) : 0;
      cam(st.a, { fx: 0.5, fy: lerp(0.95, 0.12, u), s: lerp(1.28, 1.1, u) * lerp(1, 3.2, punch), rx: lerp(12, 0, u) }, 'a');
      st.a.style.filter = punch > 0.01 ? `blur(${punch * 10}px)` : '';
      if (!st.b) return s.images[0];
      const v = seg(lt, t1 - 0.1, t1 + 0.6);
      st.b.style.display = v > 0 ? 'block' : 'none';
      st.b.style.clipPath = `circle(${lerp(0, 1300, E.expoOut(v))}px at 540px 960px)`;
      cam(st.b, { fx: 0.5, fy: 0.45, s: lerp(2.2, 1.12, E.expoOut(v)) - 0.06 * seg(lt, t1 + 0.6, D), r: lerp(-14, 0, E.expoOut(v)) }, 'b');
      return v > 0.3 ? s.images[1] : s.images[0];
    },
  };

  // bands: three horizontal bands of different photos slide in from alternate sides, the middle one takes over
  RECIPES.bands = {
    build(root, s) {
      const ims = s.images.slice(0, 3);
      while (ims.length < 3) ims.push(s.images[ims.length % s.images.length]);
      return { p: ims.map((im) => photo(root, im)), ims: [ims[1], ims[0], ims[2]] };
    },
    update(st, lt, D, s) {
      const t1 = D * 0.5, g = E.expoInOut(seg(lt, t1, t1 + 0.7));
      // order: band 0 top, 1 middle (drawn last = on top), 2 bottom
      const order = [0, 2, 1];
      order.forEach((k, z) => { st.p[k].style.zIndex = z; });
      [0, 1, 2].forEach((k) => {
        const e = st.p[k];
        const ent = E.expoOut(seg(lt, -0.15 + k * 0.12, 0.65 + k * 0.12));
        const dir = k % 2 ? -1 : 1;
        let top = (k * H) / 3, bot = H - ((k + 1) * H) / 3;
        if (k === 1) { top = lerp(top, 0, g); bot = lerp(bot, 0, g); }
        e.style.clipPath = `inset(${top}px 0 ${bot}px 0)`;
        const drift = seg(lt, 0, D);
        cam(e, { fx: 0.5 + dir * (0.18 - 0.36 * drift) * (k === 1 ? 0.6 : 1), fy: 0.5, s: k === 1 ? lerp(1.18, 1.08, g) : 1.15,
                 tx: dir * (1 - ent) * W * 1.1 }, 'b' + k);
        e.style.display = k !== 1 && g >= 1 ? 'none' : 'block';
      });
      return g > 0.5 ? st.ims[0] : st.ims[0];
    },
  };

  // pano: a very wide picture trucked end to end with a speed ramp and a slight orbit
  RECIPES.pano = {
    build(root, s) {
      let k = 0; s.images.forEach((im, i) => { if (im.w / im.h > s.images[k].w / s.images[k].h) k = i; });
      const st = { k, a: photo(root, s.images[k]) };
      const rest = s.images.filter((_, i) => i !== k);
      if (rest[0]) { st.b = photo(root, rest[0]); st.bi = rest[0]; }
      return st;
    },
    update(st, lt, D, s) {
      const t1 = st.b ? D * 0.68 : D + 0.3;
      const u = seg(lt, -0.3, t1);
      const ramp = (x) => 0.5 - 0.5 * Math.cos(Math.PI * x) * 0.75 + (x - 0.5) * 0.25;   // fast-slow-fast
      cam(st.a, { fx: lerp(0.0, 1.0, ramp(u)), fy: 0.5, s: 1.04 + 0.05 * Math.sin(u * Math.PI), ry: lerp(-7, 7, u), r: lerp(-1.5, 1.5, u) }, 'a');
      if (!st.b) return s.images[st.k];
      // whip out of the panorama into the second picture (inside the shot)
      const v = seg(lt, t1 - 0.15, t1 + 0.25), ve = E.expoInOut(v);
      st.b.style.display = v > 0 ? 'block' : 'none';
      cam(st.b, { fx: 0.5, fy: 0.5, s: 1.12 + 0.06 * seg(lt, t1, D), tx: (1 - ve) * W * 1.15 }, 'b');
      if (v > 0) cam(st.a, { fx: 1, fy: 0.5, s: 1.04, ry: 7, r: 1.5, tx: -ve * W * 1.15 }, 'a');
      return v > 0.5 ? st.bi : s.images[st.k];
    },
  };

  // carousel: cards on a turning ring in 3D, blurred backdrop; the last card flies forward to fill the frame
  RECIPES.carousel = {
    build(root, s) {
      const ims = s.images.slice(0, 4);
      const st = { ims, n: ims.length };
      st.bg = el('div', 'bgblur', root); st.bg.style.backgroundImage = `url("${ims[0].src}")`;
      st.ringEl = el('div', 'layer', root); st.ringEl.style.transformStyle = 'preserve-3d';
      st.cards = ims.map((im) => {
        const c = el('div', 'card', st.ringEl);
        c.style.width = '760px'; c.style.height = '1100px';
        const i = el('img', 'grade', c); i.src = im.src;
        const k = Math.max(760 / im.w, 1100 / im.h);
        i.style.width = im.w * k + 'px'; i.style.height = im.h * k + 'px';
        i.style.left = (760 - im.w * k) / 2 + 'px'; i.style.top = (1100 - im.h * k) / 2 + 'px';
        c._i = i; c._k = k; c._im = im;
        return c;
      });
      st.full = photo(root, ims[0]);
      return st;
    },
    update(st, lt, D, s) {
      const n = st.n, step = 360 / n, Rr = n > 2 ? 620 : 520;
      // turns: dwell, snap to the next card on the beat
      const tEnd = D * 0.72, turns = n;
      let ang = 0;
      for (let j = 1; j <= turns; j++) {
        const tj = (tEnd * j) / (turns + 0.4) - 0.25;
        ang += step * E.expoInOut(seg(lt, tj, tj + 0.55));
      }
      ang -= 18 * (1 - E.out(seg(lt, -0.3, 0.8)));
      const front = Math.round(ang / step) % n;
      const ringM = new DOMMatrix().translate(540, 1000, -Rr - 250).rotate(lerp(-8, 6, seg(lt, 0, D)), -ang, 0);
      st.ringEl.style.transform = ringM.toString();
      st.cards.forEach((c, i) => {
        const m = new DOMMatrix().rotate(0, step * i, 0).translate(-380, -550, Rr);
        c.style.transform = m.toString();
        const a = ((((step * i - ang) % 360) + 540) % 360) - 180;   // angle from the viewer
        c.style.opacity = clamp(1.25 - Math.abs(a) / 150);
        c.style.filter = `brightness(${lerp(1, 0.55, Math.abs(a) / 180)})`;
        if (PROBE) { const mm = ringM.multiply(m); PROBE[PFX + 'c' + i] = [project(mm, 0, 0), project(mm, 760, 1100)]; }
      });
      st.bg.style.backgroundImage = `url("${st.ims[front].src}")`;
      // finale: the front card becomes the frame
      const f = E.expoInOut(seg(lt, tEnd, tEnd + 0.6));
      st.full.style.display = f > 0 ? 'block' : 'none';
      if (f > 0) {
        const im = st.ims[front];
        if (st.full._img.src !== new URL(im.src, location.href).href) {
          st.full._img.src = im.src;
          const c0 = Math.max(W / im.w, H / im.h); st.full._w0 = im.w * c0; st.full._h0 = im.h * c0;
          st.full.style.width = st.full._w0 + 'px'; st.full.style.height = st.full._h0 + 'px';
        }
        const ins = lerp(1, 0, f);
        st.full.style.clipPath = `inset(${ins * 410}px ${ins * 160}px ${ins * 410}px ${ins * 160}px round ${ins * 26}px)`;
        cam(st.full, { fx: 0.5, fy: 0.5, s: lerp(1.0, 1.1, f) + 0.05 * seg(lt, tEnd + 0.6, D) }, 'full');
      }
      return st.ims[front];
    },
  };

  // strips: vertical slices of several photos scroll against each other, then one slice opens to full frame
  RECIPES.strips = {
    build(root, s) {
      const ims = s.images.slice(0, 4);
      while (ims.length < 3) ims.push(s.images[ims.length % s.images.length]);
      return { ims, p: ims.map((im) => photo(root, im)) };
    },
    update(st, lt, D, s) {
      const n = st.p.length, sw = W / n, t1 = D * 0.5;
      const g = E.expoInOut(seg(lt, t1, t1 + 0.65));
      st.p.forEach((e, k) => {
        const dir = k % 2 ? 1 : -1;
        const ent = E.expoOut(seg(lt, -0.2 + k * 0.09, 0.6 + k * 0.09));
        let l = k * sw, r = W - (k + 1) * sw;
        if (k === 0) { r = lerp(r, 0, g); }
        e.style.zIndex = k === 0 ? 5 : 1;
        e.style.clipPath = `inset(0 ${r}px 0 ${l}px)`;
        const scroll = seg(lt, 0, t1 + 0.6);
        cam(e, { fx: 0.5 + (k - (n - 1) / 2) * 0.08 * (1 - g), fy: 0.5 + dir * (0.25 - 0.5 * scroll) * (1 - g) + (k === 0 ? -0.2 * seg(lt, t1, D) : 0),
                 s: k === 0 ? lerp(1.35, 1.12, g) : 1.35, ty: dir * (1 - ent) * H }, 's' + k);
        e.style.display = k > 0 && g >= 1 ? 'none' : 'block';
      });
      return st.ims[0];
    },
  };

  // bloom: the picture starts as ink (grey), colour spreads out from the centre; optional second picture after
  RECIPES.bloom = {
    build(root, s) {
      const st = { g: photo(root, s.images[0]), c: photo(root, s.images[0]) };
      st.g.style.filter = 'grayscale(1) contrast(1.35) brightness(1.05)';
      st.ringc = el('div', null, root);
      st.ringc.style.cssText = 'position:absolute;left:0;top:0;border-radius:50%;box-shadow:0 0 120px 40px rgba(170,255,200,.28), inset 0 0 80px 20px rgba(170,255,200,.22)';
      if (s.images[1]) st.b = photo(root, s.images[1]);
      return st;
    },
    update(st, lt, D, s) {
      const t1 = st.b ? D * 0.6 : D + 1;
      const u = E.inOut(seg(lt, 0.35, 2.0));
      const rad = lerp(0, 1500, u);
      const c = { fx: 0.5, fy: 0.5, s: lerp(1.04, 1.2, seg(lt, -0.3, t1 + 0.3)), r: lerp(-2.5, 0.5, seg(lt, -0.3, t1)) };
      cam(st.g, c, 'g'); cam(st.c, c, null);
      // the mask lives in the photo's own (unscaled) box: divide the screen radius by the zoom
      const k = c.s;
      st.c.style.webkitMaskImage = u >= 1 ? '' : `radial-gradient(circle at 50% 50%, #000 ${Math.max(0, rad - 260) / k}px, transparent ${rad / k}px)`;
      st.ringc.style.display = u > 0 && u < 1 ? 'block' : 'none';
      st.ringc.style.width = st.ringc.style.height = rad * 1.1 + 'px';
      st.ringc.style.transform = `translate(${540 - rad * 0.55}px, ${960 - rad * 0.55}px)`;
      st.ringc.style.opacity = (1 - u) * 0.9;
      if (!st.b) return s.images[0];
      const v = seg(lt, t1 - 0.2, t1 + 0.5), ve = E.expoOut(v);
      st.b.style.display = v > 0 ? 'block' : 'none';
      st.b.style.opacity = clamp(v * 2.5);
      cam(st.b, { fx: 0.5, fy: 0.5, s: lerp(1.5, 1.1, ve) + 0.06 * seg(lt, t1 + 0.5, D), r: lerp(4, 0, ve) }, 'b');
      return v > 0.4 ? s.images[1] : s.images[0];
    },
  };

  // truck: single landscape picture panned sideways (fallback)
  RECIPES.truck = {
    build(root, s) { return { a: photo(root, s.images[0]) }; },
    update(st, lt, D, s) {
      const u = seg(lt, -0.3, D + 0.3);
      cam(st.a, { fx: lerp(0.15, 0.85, E.sine(u)), fy: 0.5, s: lerp(1.08, 1.18, u), r: lerp(1.5, -1.5, u) }, 'a');
      return s.images[0];
    },
  };

  // card: text-only spot (no licensed photo found) — satellite map close-up behind big type
  RECIPES.card = {
    build(root, s) { return { M: buildMap(root) }; },
    update(st, lt, D, s) {
      const i = TL.spots.indexOf(s);
      mapDraw(st.M, { cx: s.px, cy: s.py, z: lerp(1.3, 1.6, seg(lt, 0, D)), tilt: 40, head: lerp(-8, 4, seg(lt, 0, D)) },
        { key: 'm', pins: (j) => (j === i ? 1 : 0), hi: i });
      return null;
    },
  };

  // ------------------------------------------------------------------ shots
  function spotShot(spec) {
    const s = TL.spots[spec.spot];
    const root = el('div', 'shot', $('#shots'));
    const rec = RECIPES[spec.recipe];
    const st = rec.build(root, s);
    const T = buildText(root, s, spec.layout);
    return {
      root, spec,
      update(lt) {
        const D = spec.t1 - spec.t0;
        const img = rec.update(st, lt, D, s);
        animText(T, lt, D, img);
      },
    };
  }

  function introShot(spec) {
    const root = el('div', 'shot', $('#shots'));
    const D = spec.t1 - spec.t0;
    const M = buildMap(root);
    // hook montage: one picture per spot, hard cuts, the title assembles one character per cut
    const mont = el('div', 'layer', root);
    const pics = TL.spots.map((s) => photo(mont, s.images[0] || { src: MAP.local.src, w: L.w, h: L.h }));
    const frame = el('div', null, root);
    frame.style.cssText = 'position:absolute;left:60px;top:60px;right:60px;bottom:60px;border:3px solid rgba(255,255,255,.85);border-radius:8px';
    const hookChars = [...TL.hook];
    const hook = chars(root, TL.hook, 'serif shadow');
    hook.style.fontSize = (hookChars.length > 4 ? 170 : 200) + 'px'; hook.style.width = W + 'px'; hook.style.textAlign = 'center'; hook.style.top = '780px';
    hook.style.letterSpacing = '8px';
    const title = chars(root, TL.city, 'serif shadow');
    title.style.fontSize = '230px'; title.style.width = W + 'px'; title.style.textAlign = 'center'; title.style.top = '420px'; title.style.letterSpacing = '40px';
    const sub = chars(root, TL.subtitle, 'kai shadow');
    sub.style.fontSize = '54px'; sub.style.width = W + 'px'; sub.style.textAlign = 'center'; sub.style.top = '720px';
    const credit = el('div', 'txt shadow', root, esc(TL.mapCredit));
    credit.style.cssText += "font:400 21px 'Noto Sans CJK SC';left:60px;top:1548px;opacity:.8";
    const cut = TL.hookCut;                       // seconds per montage picture
    const nm = pics.length, tm = nm * cut;        // montage length
    const sp0 = TL.spots[0];
    const cxL = L.w / 2, cyL = L.h / 2;
    return {
      root, spec,
      update(lt) {
        // --- montage
        const k = Math.floor(lt / cut);
        mont.style.display = lt < tm ? 'block' : 'none';
        frame.style.display = lt < tm ? 'block' : 'none';
        pics.forEach((p, i) => {
          const on = i === k && lt < tm;
          p.style.display = on ? 'block' : 'none';
          if (on) { const u = (lt - i * cut) / cut; cam(p, { fx: 0.5, fy: 0.5, s: lerp(1.45, 1.18, E.expoOut(u)), r: (i % 2 ? 1 : -1) * lerp(4, 1, u) }, 'm' + i); }
        });
        const per = tm / hookChars.length;
        hook._ch.forEach((c, i) => {
          const u = lt - i * per;
          const sp = spring(u, 2.4, 0.4);
          c.style.opacity = u > 0 && lt < tm + 0.05 ? 1 : 0;
          c.style.transform = `scale(${lerp(1.8, 1, sp)})`;
          c.style.filter = 'none';
        });
        // --- satellite descent
        const t0 = tm;
        const zA = 0.15, zB = 0.42;
        const ks = [
          [t0, { cx: cxL - 700, cy: cyL + 900, z: zA, tilt: 0, head: 28 }],
          [t0 + 2.2, { cx: cxL - 150, cy: cyL + 250, z: zB * 0.7, tilt: 26, head: 6 }, 'out'],
          [D - 1.9, { cx: cxL, cy: cyL, z: zB * 1.15, tilt: 50, head: -14 }, 'sine'],
          [D + 0.35, { cx: sp0.px, cy: sp0.py, z: 2.8, tilt: 58, head: -24 }, 'expoIn'],
        ];
        const c = keyed(lt, ks);
        const pinT = (i) => (lt - (D - 2.15) - i * 0.1) / 0.25;
        mapDraw(M, c, {
          key: 'map', route: E.inOut(seg(lt, D - 2.0, D - 0.8)), pins: pinT, labels: (i) => pinT(i) - 0.6, hi: lt > D - 1 ? 0 : -1,
        });
        M.show(lt >= t0 - 0.02);
        // --- title + subtitle over the descent
        const ta = lt - t0 - 0.15;
        animChars(title, lt, t0 + 0.1, { stagger: 0.12, dy: -90, s0: 1.6, f: 1.3, z: 0.42 });
        animChars(sub, lt, t0 + 0.75, { stagger: 0.045, dy: 26, s0: 1.0 });
        const go = E.in(seg(lt, D - 2.5, D - 2.0));
        title.style.transform = `translate(0, ${-80 * go}px)`; title.style.opacity = 1 - go;
        sub.style.transform = `translate(0, ${-60 * go}px)`; sub.style.opacity = 1 - go;
        title.style.display = sub.style.display = ta > -0.2 ? 'block' : 'none';
        credit.style.opacity = lt > t0 ? 0.8 : 0;
      },
    };
  }

  function hopShot(spec) {
    const root = el('div', 'shot', $('#shots'));
    const M = buildMap(root);
    const a = TL.spots[spec.from], b = TL.spots[spec.to];
    const nx = el('div', 'txt shadow', root, `<span style="font:500 34px 'Noto Sans CJK SC';opacity:.85">下一站</span><br><span style="font:700 92px 'Noto Serif CJK SC'">${esc(b.where.split(' · ')[0])}</span>`);
    nx.style.left = '76px'; nx.style.top = '300px'; nx.style.lineHeight = '1.25';
    const credit = el('div', 'txt shadow', root, esc(TL.mapCredit));
    credit.style.cssText += "font:400 21px 'Noto Sans CJK SC';left:60px;top:1548px;opacity:.8";
    return {
      root, spec,
      update(lt) {
        const D = spec.t1 - spec.t0;
        const mx_ = (a.px + b.px) / 2, my_ = (a.py + b.py) / 2;
        const dist = Math.hypot(a.px - b.px, a.py - b.py);
        const zMid = clamp(700 / Math.max(dist, 1), 0.25, 1.4);
        const c = keyed(lt, [
          [-0.3, { cx: a.px, cy: a.py, z: 2.4, tilt: 55, head: 10 }],
          [D * 0.5, { cx: mx_, cy: my_, z: zMid, tilt: 35, head: 0 }, 'out'],
          [D + 0.35, { cx: b.px, cy: b.py, z: 2.6, tilt: 55, head: -12 }, 'expoIn'],
        ]);
        const seg0 = (spec.from + E.inOut(seg(lt, 0.1, D - 0.4))) / (TL.spots.length - 1);
        mapDraw(M, c, { key: 'map', route: seg0, pins: (i) => (i <= spec.to ? (i === spec.to ? (lt - 0.6) / 0.3 : 1) : 0), labels: (i) => (i === spec.to || i === spec.from ? 1 : 0), hi: spec.to });
        animChars({ _ch: [nx] }, lt, 0.15, { dy: 30, s0: 1 });
        nx.style.opacity = Math.min(parseFloat(nx.style.opacity), 1 - seg(lt, D - 0.35, D));
      },
    };
  }

  function finaleShot(spec) {
    const root = el('div', 'shot', $('#shots'));
    const D = spec.t1 - spec.t0;
    const M = buildMap(root);
    // mosaic wall
    const wall = el('div', 'layer', root); wall.style.transformStyle = 'preserve-3d';
    const tiles = [];
    const pool = [];
    TL.spots.forEach((s) => s.images.forEach((im, j) => pool.push([j, im])));
    pool.sort((x, y) => x[0] - y[0]);
    const cols = 3, tw = 520, th = 700, gap = 34;
    const rows = Math.min(5, Math.ceil(Math.min(pool.length, 15) / cols));
    for (let i = 0; i < rows * cols; i++) {
      const im = pool[i % pool.length][1];
      const c = el('div', 'card', wall);
      c.style.width = tw + 'px'; c.style.height = th + 'px'; c.style.borderRadius = '18px';
      const k = Math.max(tw / im.w, th / im.h);
      const ii = el('img', 'grade', c); ii.src = im.src;
      ii.style.width = im.w * k + 'px'; ii.style.height = im.h * k + 'px';
      ii.style.left = (tw - im.w * k) / 2 + 'px'; ii.style.top = (th - im.h * k) / 2 + 'px';
      c._x = (i % cols) * (tw + gap); c._y = Math.floor(i / cols) * (th + gap);
      tiles.push(c);
    }
    const WW = cols * (tw + gap) - gap, WH = rows * (th + gap) - gap;
    const q = TL.question.split('\n');
    const qbox = el('div', null, root);
    qbox.style.cssText = 'position:absolute;left:0;top:0;width:1080px';
    const qlines = q.map((line, i) => {
      const b = chars(qbox, line, 'serif shadow');
      b.style.fontSize = '84px'; b.style.width = W + 'px'; b.style.textAlign = 'center'; b.style.top = 300 + i * 120 + 'px';
      return b;
    });
    const qshade = el('div', null, root);
    qshade.style.cssText = 'position:absolute;inset:0;background:linear-gradient(180deg, rgba(0,0,0,.7) 0%, rgba(0,0,0,.45) 30%, rgba(0,0,0,0) 45%, rgba(0,0,0,0) 68%, rgba(0,0,0,.6) 85%);';
    root.insertBefore(qshade, qbox);
    const fin = el('div', 'txt shadow', root, TL.endCredits.map(esc).join('<br>'));
    fin.style.cssText += "font:400 22px 'Noto Sans CJK SC';left:60px;top:1420px;line-height:34px;opacity:.85";
    const tWall = Math.min(3.2, D * 0.4);
    return {
      root, spec,
      update(lt) {
        // wall fly-over
        const wu = seg(lt, -0.3, tWall + 0.4);
        const wallOn = lt < tWall + 0.5;
        wall.style.display = wallOn ? 'block' : 'none';
        if (wallOn) {
          const out = E.expoIn(seg(lt, tWall - 0.4, tWall + 0.5));
          const wm = new DOMMatrix().translate(540, 960, lerp(-300, 200, E.sine(wu)) - out * 2600).rotate(lerp(38, 22, wu), 0, lerp(-16, -8, wu))
            .translate(-WW / 2 + lerp(380, -380, E.sine(wu)), -WH / 2 + lerp(WH * 0.35, -WH * 0.35, E.sine(wu)));
          wall.style.transform = wm.toString();
          wall.style.opacity = 1 - seg(lt, tWall, tWall + 0.5);
          tiles.forEach((c, i) => {
            const f = E.expoOut(seg(lt, -0.2 + (i % 7) * 0.06, 0.5 + (i % 7) * 0.06));
            const m = new DOMMatrix().translate(c._x + tw / 2, c._y + th / 2).rotate(0, lerp(90, 0, f), 0).translate(-tw / 2, -th / 2);
            c.style.transform = m.toString();
            if (PROBE && i % 4 === 0) { const mm = wm.multiply(m); PROBE[PFX + 't' + i] = [project(mm, 0, 0), project(mm, tw, th)]; }
          });
        }
        // map: full overview with the whole route
        const xs = TL.spots.map((s) => s.px), ys = TL.spots.map((s) => s.py);
        const cx = (Math.min(...xs) + Math.max(...xs)) / 2, cy = (Math.min(...ys) + Math.max(...ys)) / 2;
        const span = Math.max(Math.max(...xs) - Math.min(...xs), (Math.max(...ys) - Math.min(...ys)) * 0.56, 300);
        const zf = 760 / span;
        const c = keyed(lt, [[tWall - 0.4, { cx, cy, z: zf * 2.2, tilt: 50, head: 20 }], [tWall + 1.6, { cx, cy: cy + 80 / zf, z: zf, tilt: 30, head: 0 }, 'expoOut'], [D, { cx, cy: cy + 80 / zf, z: zf * 1.06, tilt: 26, head: -4 }, 'lin']]);
        const mOn = lt > tWall - 0.5;
        M.show(mOn);
        if (mOn) mapDraw(M, Object.assign(c, { oy: 1020 }), { key: 'map', route: 1, pins: (i) => (lt - tWall - i * 0.08) / 0.25, labels: (i) => (lt - tWall - 0.3 - i * 0.08) / 0.3, hi: -1 });
        // question
        const tq = tWall + 0.9;
        qlines.forEach((b, i) => animChars(b, lt, tq + i * 0.45, { stagger: 0.05, dy: 50 }));
        qshade.style.opacity = E.out(seg(lt, tq - 0.3, tq + 0.5));
        fade(fin, lt, tq + 1.2, 0.6, 0);
      },
    };
  }

  // ------------------------------------------------------------------ transitions between shots
  // fx(type, p, side) → {m: DOMMatrix, op, clip, blur}; side 'in' for the incoming shot, 'out' for the outgoing one
  function fx(type, p, side) {
    const r = { m: new DOMMatrix(), op: 1, clip: '', blur: 0 };
    const c = (m) => new DOMMatrix().translate(540, 960).multiply(m).translate(-540, -960);
    const e = E.inOut(p);
    if (type === 'whip' || type === 'whipV' || type === 'whipD') {
      const ee = E.expoInOut(p);
      const dx = type === 'whip' ? W : type === 'whipD' ? W * 0.9 : 0, dy = type === 'whipV' ? H : type === 'whipD' ? H * 0.55 : 0;
      const k = side === 'out' ? -ee : 1 - ee;
      r.m = new DOMMatrix().translate(dx * k, dy * k).rotate(0, 0, type === 'whipD' ? 6 * k : 0);
    } else if (type === 'zoom') {
      // fly through: the old shot rushes past the lens, the new one arrives from behind it and settles
      if (side === 'out') { const u = E.expoIn(p); r.m = c(new DOMMatrix().scale(lerp(1, 5, u))); r.op = 1 - seg(p, 0.45, 0.7); }
      else { const u = E.expoOut(seg(p, 0.45, 1)); r.m = c(new DOMMatrix().scale(lerp(2.2, 1, u)).rotate(0, 0, lerp(6, 0, u))); r.op = seg(p, 0.45, 0.62); }
    } else if (type === 'roll') {
      if (side === 'out') { const u = E.expoIn(p); r.m = c(new DOMMatrix().rotate(0, 0, 100 * u).scale(lerp(1, 1.7, u))); r.op = 1 - seg(p, 0.6, 1); r.blur = u * 10; }
      else { const u = E.expoOut(seg(p, 0.4, 1)); r.m = c(new DOMMatrix().rotate(0, 0, -100 * (1 - u)).scale(lerp(1.7, 1, u))); r.op = seg(p, 0.4, 0.6); }
    } else if (type === 'iris') {
      if (side === 'in') r.clip = `circle(${lerp(0, 1150, E.expoInOut(p))}px at 540px 960px)`;
      else r.m = c(new DOMMatrix().scale(lerp(1, 1.18, e)));
    } else if (type === 'dive') {   // map → photo: map dives, the photo grows out of the pin
      if (side === 'out') { r.op = 1 - seg(p, 0.55, 1); r.blur = E.expoIn(p) * 8; }
      else { const u = E.expoOut(seg(p, 0.3, 1)); r.m = c(new DOMMatrix().rotate(0, 0, lerp(-10, 0, u)).scale(lerp(0.12, 1, u))); r.op = seg(p, 0.3, 0.45); r.clip = `inset(0 round ${lerp(80, 0, u)}px)`; }
    } else if (type === 'pull') {   // photo → map: the photo shrinks into a card and falls away
      if (side === 'out') { const u = E.expoIn(p); r.m = c(new DOMMatrix().rotate(0, 0, 8 * u).scale(lerp(1, 0.18, u))); r.op = 1 - seg(p, 0.75, 1); r.clip = `inset(0 round ${u * 90}px)`; }
      else { const u = E.expoOut(p); r.m = c(new DOMMatrix().scale(lerp(1.6, 1, u))); r.op = seg(p, 0, 0.3); }
    } else if (type === 'flash') {
      r.op = side === 'out' ? (p < 0.5 ? 1 : 0) : (p >= 0.5 ? 1 : 0);
    }
    return r;
  }
  const HALF = { whip: 0.2, whipV: 0.2, whipD: 0.22, zoom: 0.28, roll: 0.3, iris: 0.35, dive: 0.4, pull: 0.35, flash: 0.04, cut: 0 };

  // ------------------------------------------------------------------ global overlays
  const grain = $('#grain').getContext('2d');
  const tiles = [];
  (function makeGrain() {
    let seed = 12345;
    const rnd = () => ((seed = (seed * 1103515245 + 12345) & 0x7fffffff) / 0x7fffffff);
    for (let k = 0; k < 6; k++) {
      const c = document.createElement('canvas'); c.width = c.height = 256;
      const x = c.getContext('2d'), d = x.createImageData(256, 256);
      for (let i = 0; i < d.data.length; i += 4) { const v = rnd() * 255; d.data[i] = d.data[i + 1] = d.data[i + 2] = v; d.data[i + 3] = 255; }
      x.putImageData(d, 0, 0); tiles.push(x.createPattern(c, 'repeat'));
    }
  })();
  const leak = $('#leak'), flash = $('#flash');

  const SHOTS = TL.shots.map((s) => (s.kind === 'intro' ? introShot(s) : s.kind === 'hop' ? hopShot(s) : s.kind === 'finale' ? finaleShot(s) : spotShot(s)));

  function seek(t) {
    for (let i = 0; i < SHOTS.length; i++) {
      const S = SHOTS[i], sp = S.spec;
      const aIn = HALF[sp.inT] || 0;
      const nxt = TL.shots[i + 1];
      const aOut = nxt ? HALF[nxt.inT] || 0 : 0;
      const vis = t >= sp.t0 - aIn && (t < sp.t1 + aOut || (!nxt && t <= sp.t1 + 1));
      PFX = i + ':';
      if (!vis) { S.root.style.display = 'none'; continue; }
      S.root.style.display = 'block'; S.root.style.zIndex = i;
      let m = new DOMMatrix(), op = 1, clip = '', blur = 0;
      if (aIn > 0 && t < sp.t0 + aIn) { const r = fx(sp.inT, (t - sp.t0 + aIn) / (2 * aIn), 'in'); m = m.multiply(r.m); op *= r.op; clip = r.clip; blur += r.blur; }
      if (nxt && aOut > 0 && t > sp.t1 - aOut) { const r = fx(nxt.inT, (t - sp.t1 + aOut) / (2 * aOut), 'out'); m = m.multiply(r.m); op *= r.op; if (r.clip) clip = r.clip; blur += r.blur; }
      if (nxt && aOut === 0 && t >= sp.t1) { S.root.style.display = 'none'; continue; }
      S.root.style.transform = m.isIdentity ? '' : m.toString();
      S.root.style.opacity = op;
      S.root.style.clipPath = clip;
      S.root.style.filter = blur > 0.3 ? `blur(${blur}px)` : '';
      ROOTM = m.isIdentity ? null : m; PFX = i + ':';
      if (PROBE) probePoint('root' + i, m.transformPoint(new DOMPoint(540, 960)).x, m.transformPoint(new DOMPoint(540, 960)).y);
      S.update(t - sp.t0);
      ROOTM = null;
    }
    // flashes and light leaks on the hits
    let fl = 0, lk = 0;
    for (const ev of TL.events) {
      if (ev.kind === 'flash') fl = Math.max(fl, ev.a * (t >= ev.t ? Math.exp(-(t - ev.t) / 0.09) : 0));
      if (ev.kind === 'leak') lk = Math.max(lk, Math.sin(Math.PI * seg(t, ev.t - 0.35, ev.t + 0.45)));
    }
    flash.style.opacity = fl;
    leak.style.opacity = lk * 0.55;
    leak.style.background = `radial-gradient(circle at ${30 + 40 * Math.sin(t * 0.7)}% ${20 + 30 * Math.cos(t * 0.5)}%, rgba(255,150,60,.9), rgba(255,80,40,0) 45%), radial-gradient(circle at ${70 - 30 * Math.sin(t * 0.6)}% 80%, rgba(80,200,255,.6), rgba(0,0,0,0) 40%)`;
    const f = Math.floor(t * TL.fps + 1e-6);
    grain.setTransform(1, 0, 0, 1, 0, 0);
    grain.clearRect(0, 0, W, H);
    grain.fillStyle = tiles[f % tiles.length];
    grain.translate((f * 37) % 256, (f * 91) % 256);
    grain.fillRect(-256, -256, W + 512, H + 512);
  }

  window.__seek = async (t) => { seek(t); };
  // which shots are on screen at t (a transition keeps both; only a hard cut changes the set → no shutter across it)
  window.__shotsAt = (t) => TL.shots.map((s, i) => {
    const nxt = TL.shots[i + 1], aIn = HALF[s.inT] || 0, aOut = nxt ? HALF[nxt.inT] || 0 : 0;
    const montage = s.kind === 'intro' && t < TL.spots.length * TL.hookCut ? ':' + Math.floor(t / TL.hookCut) : '';
    return t >= s.t0 - aIn && t < s.t1 + aOut ? i + montage : '';
  }).filter((x) => x !== '').join(',');
  window.__motion = (t0, t1) => {
    PROBE = {}; seek(t0); const a = PROBE;
    PROBE = {}; seek(t1); const b = PROBE;
    PROBE = null;
    let mmax = 0;
    for (const k in a) {
      if (!b[k]) continue;
      a[k].forEach((p, i) => {
        const q = b[k][i];
        if (!q) return;
        const on = (r) => r[0] > -150 && r[0] < W + 150 && r[1] > -150 && r[1] < H + 150;   // only what is (nearly) on screen
        if (!on(p) && !on(q)) return;
        const d = Math.hypot(p[0] - q[0], p[1] - q[1]);
        if (d < 3000) mmax = Math.max(mmax, d);
      });
    }
    return mmax;
  };
  window.__meta = { dur: TL.dur, fps: TL.fps, W, H };
  window.__ready = (async () => {
    await document.fonts.load("700 100px 'Noto Serif CJK SC'", TL.allText);
    await document.fonts.load("500 40px 'Noto Sans CJK SC'", TL.allText);
    await document.fonts.load("400 40px 'Noto Sans CJK SC'", TL.allText);
    await document.fonts.load("40px 'LXGW WenKai'", TL.allText);
    const imgs = [...document.images];
    await Promise.all(imgs.map((i) => (i.complete ? i.decode().catch(() => {}) : new Promise((r) => { i.onload = () => i.decode().then(r, r); i.onerror = r; }))));
    seek(0);
    return true;
  })();
  if (/[?&]t=/.test(location.search)) window.__ready.then(() => seek(parseFloat(location.search.match(/[?&]t=([\d.]+)/)[1])));
})();
