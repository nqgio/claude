// Composes one full 1080x1920 frame as SVG from a timeline (built by scripts/build.py).
(function () {
  const W = 1080, H = 1920, INK = '#2a1d14';
  let TL = null;

  const esc = (s) => String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
  const ease = (x) => 1 - Math.pow(1 - Math.max(0, Math.min(1, x)), 3);
  const back = (x) => { x = Math.max(0, Math.min(1, x)); const c = 1.7; return 1 + (c + 1) * Math.pow(x - 1, 3) + c * Math.pow(x - 1, 2); };

  function outlined(text, x, y, size, fill, opts = {}) {
    const font = opts.font || 'Anton';
    const sw = opts.stroke || Math.round(size * 0.16);
    return `<text x="${x}" y="${y}" font-family="${font}" font-weight="${opts.weight || 400}" font-size="${size}" text-anchor="middle" fill="${fill}" stroke="${INK}" stroke-width="${sw}" stroke-linejoin="round" paint-order="stroke" letter-spacing="${opts.ls || 1}">${esc(text)}</text>`;
  }

  function blinkAt(frame, seed) {
    const p = (frame + seed * 37) % 104;
    return p < 2 ? 1 : p < 4 ? 0.6 : 0;
  }

  function theoStateAt(frame) {
    let s = Object.assign({}, TL.cast.theo);
    for (const sc of TL.scenes) if (sc.transform && frame >= sc.transform.frame) Object.assign(s, sc.transform.set);
    return s;
  }

  function titleCard(frame) {
    const k = back(frame / 9);
    const [l1, l2] = TL.title;
    return `<g transform="translate(540 330) scale(${k}) translate(-540 -330)">` +
      `<rect x="70" y="110" width="940" height="430" rx="34" fill="#1d2140" fill-opacity="0.92" stroke="${INK}" stroke-width="10"/>` +
      outlined(`DAY ${TL.day}`, 540, 235, 118, '#ffd23f') +
      outlined(l1, 540, 365, l1.length > 14 ? 96 : 112, '#ffffff') +
      outlined(l2, 540, 495, l2.length > 14 ? 100 : 118, TL.accent || '#7cfc5a') +
      `</g>` +
      `<g transform="translate(860 600) rotate(4)"><rect x="-150" y="-40" width="300" height="76" rx="38" fill="#e84a5f" stroke="${INK}" stroke-width="7"/>` +
      `<text x="0" y="14" font-family="Anton" font-size="44" fill="#fff" text-anchor="middle">${TL.days_left} DAYS LEFT</text></g>`;
  }

  function creditBadge(frame) {
    if (!TL.credit || frame > TL.scenes[0].end_frame) return '';
    const k = back((frame - 6) / 8);
    return `<g transform="translate(250 600) scale(${k}) rotate(-3)"><rect x="-200" y="-40" width="400" height="76" rx="38" fill="#fff" stroke="${INK}" stroke-width="7"/>` +
      `<path d="M -165 -8 c 0 -14 22 -14 22 0 c 0 -14 22 -14 22 0 c 0 16 -22 26 -22 30 c 0 -4 -22 -14 -22 -30 Z" fill="#e84a5f"/>` +
      `<text x="20" y="14" font-family="Nunito" font-weight="900" font-size="34" fill="${INK}" text-anchor="middle">${esc(TL.credit)}</text></g>`;
  }

  function nameTag(x, y, tag) {
    const w = Math.max(220, tag.length * 30 + 60);
    return `<g transform="translate(${x} ${y}) rotate(-3)"><rect x="${-w / 2}" y="-44" width="${w}" height="80" rx="18" fill="#fff" stroke="${INK}" stroke-width="7"/>` +
      `<rect x="${-w / 2}" y="-44" width="${w}" height="26" rx="12" fill="#3d7bd9"/>` +
      `<text x="0" y="-24" font-family="Nunito" font-weight="900" font-size="18" fill="#fff" text-anchor="middle" letter-spacing="3">HELLO MY NAME IS</text>` +
      `<text x="0" y="24" font-family="Nunito" font-weight="900" font-size="36" fill="${INK}" text-anchor="middle">${esc(tag)}</text></g>`;
  }

  function placeChar(state, o, x, y, sc) {
    return `<g transform="translate(${x} ${y}) scale(${sc})">${window.characterSVG(state, o)}</g>`;
  }

  function prop(name, local, t) {
    if (name === 'letter') {
      const k = ease(local / 12);
      const x = -300 + k * 420, y = 1380;
      return `<g transform="translate(${x} ${y}) rotate(${-12 + 6 * Math.sin(t * 2)})"><rect x="0" y="0" width="300" height="190" rx="10" fill="#fff6e0" stroke="${INK}" stroke-width="8"/>` +
        `<path d="M 0 0 L 150 105 L 300 0" fill="none" stroke="${INK}" stroke-width="7"/>` +
        `<path d="M 130 120 c 0 -16 20 -16 20 0 c 0 -16 20 -16 20 0 c 0 18 -20 28 -20 32 c 0 -4 -20 -14 -20 -32 Z" fill="#e84a5f"/>` +
        `<text x="150" y="178" font-family="Anton" font-size="30" fill="${INK}" text-anchor="middle">FROM: MOM</text></g>`;
    }
    return '';
  }

  function sparkles(cx, cy, local) {
    let out = '';
    for (let i = 0; i < 9; i++) {
      const a = i * 0.7 + local * 0.05, r = 330 + (i % 3) * 70;
      const x = cx + Math.cos(a) * r, y = cy + Math.sin(a) * r * 0.9;
      const s = (0.5 + 0.5 * Math.sin(local * 0.4 + i * 1.3)) * (1 - local / 70) * 40;
      if (s <= 1) continue;
      out += `<path d="M ${x} ${y - s} Q ${x} ${y} ${x + s} ${y} Q ${x} ${y} ${x} ${y + s} Q ${x} ${y} ${x - s} ${y} Q ${x} ${y} ${x} ${y - s} Z" fill="#fff" stroke="#ffe680" stroke-width="3"/>`;
    }
    return out;
  }

  function transformFX(sc, frame, headX, headY) {
    if (!sc.transform) return { pre: '', post: '' };
    const d = frame - sc.transform.frame;
    let post = '';
    if (d >= -6 && d <= 14) {
      const a = d < 0 ? (d + 6) / 6 : Math.max(0, 1 - d / 14);
      for (let i = 0; i < 10; i++) {
        const ang = i * 0.628, r = 160 + (d + 6) * 9;
        post += `<circle cx="${headX + Math.cos(ang) * r}" cy="${headY + Math.sin(ang) * r * 0.8}" r="${110 - Math.abs(d) * 4}" fill="#fff" opacity="${a * 0.95}" stroke="#ddd" stroke-width="6"/>`;
      }
      post += `<rect width="${W}" height="${H}" fill="#fff" opacity="${Math.max(0, 0.8 - Math.abs(d) / 6)}"/>`;
    }
    if (d >= 0 && d < 70) post += sparkles(headX, headY, d);
    if (d >= 0 && d < 30 && sc.transform.label) {
      const k = back(d / 7) * (d > 24 ? 1 - (d - 24) / 6 : 1);
      post += `<g transform="translate(${headX + 220} ${headY - 260}) rotate(-12) scale(${k})">` + outlined(sc.transform.label, 0, 0, 150, '#ffd23f', { stroke: 22 }) + `</g>`;
    }
    return { pre: '', post };
  }

  function captions(sc, frame) {
    const c = (sc.captions || []).find((c) => frame >= c.start_frame && frame < c.end_frame);
    if (!c) return '';
    const k = back((frame - c.start_frame) / 4);
    return `<g transform="translate(540 735) scale(${k})">` + outlined(c.text.toUpperCase(), 0, 0, 66, '#ffffff', { font: 'Nunito', weight: 900, stroke: 16, ls: 0 }) + `</g>`;
  }

  function cta(frame) {
    if (!TL.cta || frame < TL.cta.start_frame) return '';
    const local = frame - TL.cta.start_frame;
    const k = back(local / 9);
    const bounce = Math.abs(Math.sin(local * 0.25)) * 26;
    const [a, b] = TL.cta.lines;
    return `<g transform="translate(540 1600) scale(${k}) rotate(-2)">` +
      `<rect x="-470" y="-150" width="940" height="290" rx="36" fill="#ffd23f" stroke="${INK}" stroke-width="10"/>` +
      `<text x="0" y="-55" font-family="Anton" font-size="78" fill="${INK}" text-anchor="middle">${esc(a)}</text>` +
      `<text x="0" y="45" font-family="Anton" font-size="98" fill="#e84a5f" text-anchor="middle" stroke="${INK}" stroke-width="5" paint-order="stroke">${esc(b)}</text>` +
      `<text x="0" y="110" font-family="Nunito" font-weight="900" font-size="34" fill="${INK}" text-anchor="middle">WANT A CAMEO? COMMENT WHO YOU'D BE</text>` +
      `</g><g transform="translate(540 ${1800 + bounce})"><path d="M -40 0 L 40 0 L 40 40 L 75 40 L 0 110 L -75 40 L -40 40 Z" fill="#fff" stroke="${INK}" stroke-width="8"/></g>`;
  }

  window.loadTimeline = (tl) => { TL = tl; };

  window.renderFrame = (frame) => {
    const t = frame / TL.fps;
    const sc = TL.scenes.find((s) => frame >= s.start_frame && frame < s.end_frame) || TL.scenes[TL.scenes.length - 1];
    const local = frame - sc.start_frame;
    const talkOf = (who) => (sc.speaker === who ? (sc.mouth[local] || 0) : 0);
    const theo = theoStateAt(frame);
    let theoEx = sc.theo.expression || 'neutral';
    if (sc.transform && frame >= sc.transform.frame && sc.transform.after_expression) theoEx = sc.transform.after_expression;
    const others = sc.others || [];
    const pop = 1 + 0.06 * Math.max(0, 1 - local / 6) * Math.sin(local * 1.2);

    let body = (window.BACKGROUNDS[sc.bg] || window.BACKGROUNDS.studio)(t);
    let headX = 540, headY = 1040;

    if (others.length === 0) {
      const scale = 1.25 * pop, x = 540 - 400 * scale, y = H - 1100 * scale;
      body += placeChar(theo, { expression: theoEx, pose: sc.theo.pose, talk: talkOf('theo'), blink: blinkAt(frame, 1), t, bob: Math.sin(t * 2.2) * 6 + talkOf('theo') * 8 }, x, y, scale);
      headX = x + 400 * scale; headY = y + 400 * scale;
    } else {
      const slots = others.length === 1 ? [{ x: -110, y: 980, s: 0.92 }] : [{ x: -170, y: 1100, s: 0.78 }, { x: 640, y: 1100, s: 0.78 }];
      const tScale = (others.length === 1 ? 1.0 : 0.9) * pop;
      const tx = others.length === 1 ? 300 : 540 - 400 * tScale, ty = H - 1100 * tScale;
      others.forEach((o, i) => {
        const st = TL.cast[o.who];
        const sl = slots[i];
        body += placeChar(st, { expression: o.expression || 'neutral', pose: o.pose, talk: talkOf(o.who), blink: blinkAt(frame, i + 3), t, bob: Math.sin(t * 2 + i) * 5 }, sl.x, sl.y, sl.s);
        if (st.tag) body += nameTag(sl.x + 400 * sl.s, sl.y + 120 * sl.s - 40, st.tag);
      });
      body += placeChar(theo, { expression: theoEx, pose: sc.theo.pose, talk: talkOf('theo'), blink: blinkAt(frame, 1), t, bob: Math.sin(t * 2.2) * 6 }, tx, ty, tScale);
      headX = tx + 400 * tScale; headY = ty + 400 * tScale;
    }
    if (sc.prop) body += prop(sc.prop, local, t);
    const fx = transformFX(sc, frame, headX, headY);
    body += fx.post;
    body += titleCard(frame) + creditBadge(frame) + captions(sc, frame) + cta(frame);
    document.getElementById('stage').innerHTML = `<svg xmlns="http://www.w3.org/2000/svg" width="${W}" height="${H}" viewBox="0 0 ${W} ${H}">${body}</svg>`;
  };
})();
