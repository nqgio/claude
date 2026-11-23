// "The Model Town": a tiny town under a glass dome, a giant hand demonstrating how
// systems steer people. Top captions with yellow keyword highlight, gold rule plaque.
(function () {
  const { esc, clamp, ease, back, lerp, sceneAt, wordGroup, text } = window.PU;
  const W = 1080, H = 1920, INK = '#1a1410', GOLD = '#e6b53c';
  let TL;

  function curtain(t) {
    let g = `<rect width="${W}" height="${H}" fill="#1b2140"/>`;
    for (let i = 0; i < 14; i++) {
      const x = i * 80 + Math.sin(t * 0.6 + i) * 4;
      g += `<rect x="${x}" y="0" width="40" height="${H}" fill="#232a52" opacity="0.8"/><rect x="${x + 34}" y="0" width="8" height="${H}" fill="#141935" opacity="0.7"/>`;
    }
    g += `<rect width="${W}" height="${H}" fill="url(#spot)"/>`;
    return g;
  }

  function table() {
    return `<rect x="0" y="1360" width="${W}" height="560" fill="#5a3a24"/><rect x="0" y="1360" width="${W}" height="16" fill="#8a5c38"/>` +
      [...Array(6)].map((_, i) => `<path d="M 0 ${1420 + i * 80} Q 540 ${1400 + i * 80} 1080 ${1430 + i * 80}" stroke="#4a2f1c" stroke-width="4" fill="none" opacity="0.6"/>`).join('');
  }

  function person(x, y, c, t, ph) {
    const bob = Math.abs(Math.sin(t * 6 + ph)) * 3;
    return `<g transform="translate(${x} ${y - bob})"><rect x="-7" y="-26" width="14" height="22" rx="4" fill="${c}"/><circle cx="0" cy="-33" r="7" fill="#f0c9a0"/><rect x="-6" y="-4" width="5" height="10" fill="#333"/><rect x="1" y="-4" width="5" height="10" fill="#333"/></g>`;
  }

  function building(x, y, w, h, c, roof, o = {}) {
    let g = `<rect x="${x}" y="${y - h}" width="${w}" height="${h}" fill="${c}" stroke="${INK}" stroke-width="3"/>`;
    if (roof) g += `<path d="M ${x - 8} ${y - h} L ${x + w / 2} ${y - h - w * 0.45} L ${x + w + 8} ${y - h} Z" fill="${roof}" stroke="${INK}" stroke-width="3"/><path d="M ${x - 8} ${y - h} L ${x + w / 2} ${y - h - w * 0.45} L ${x + w + 8} ${y - h}" stroke="#fff" stroke-width="5" fill="none" opacity="0.85"/>`;
    const rows = Math.max(1, Math.floor(h / 34)), cols = Math.max(1, Math.floor(w / 26));
    for (let r = 0; r < rows; r++) for (let cI = 0; cI < cols; cI++) {
      const wx = x + 8 + cI * ((w - 16) / cols), wy = y - h + 10 + r * 32;
      const bricked = o.windows === 'bricked';
      g += `<rect x="${wx}" y="${wy}" width="${(w - 16) / cols - 6}" height="18" fill="${bricked ? '#7a4a3a' : (o.lit ? '#ffe9a0' : '#9fd0ff')}" stroke="${INK}" stroke-width="2"/>`;
      if (bricked) g += `<path d="M ${wx} ${wy + 9} L ${wx + (w - 16) / cols - 6} ${wy + 9}" stroke="#5a3428" stroke-width="2"/>`;
    }
    return g;
  }

  function town(sc, t) {
    const st = Object.assign({ clock: true, windows: 'open', casino: true }, TL.ep.town || {}, sc.town || {});
    const base = 1175;
    let g = `<ellipse cx="540" cy="${base}" rx="345" ry="38" fill="#eef3f7"/>`;
    // houses
    g += building(250, base - 6, 70, 70, '#c0504d', '#8a2f2c') + building(330, base - 4, 60, 56, '#4f81bd', '#2c4f7a');
    g += building(700, base - 6, 64, 62, '#f2c94c', '#a07a1c') + building(770, base - 4, 70, 76, '#6aa36a', '#3d6b3d');
    // clock tower
    g += `<rect x="410" y="${base - 260}" width="54" height="256" fill="#d9c9a3" stroke="${INK}" stroke-width="3"/><path d="M 402 ${base - 260} L 437 ${base - 310} L 472 ${base - 260} Z" fill="#7a5c3a" stroke="${INK}" stroke-width="3"/>`;
    if (st.clock) {
      const a = t * 0.8;
      g += `<circle cx="437" cy="${base - 225}" r="20" fill="#fff" stroke="${INK}" stroke-width="3"/><path d="M 437 ${base - 225} L ${437 + Math.sin(a) * 12} ${base - 225 - Math.cos(a) * 12} M 437 ${base - 225} L ${437 + Math.sin(a / 12) * 8} ${base - 225 - Math.cos(a / 12) * 8}" stroke="${INK}" stroke-width="3"/>`;
    } else g += `<circle cx="437" cy="${base - 225}" r="20" fill="#3a2c20" stroke="${INK}" stroke-width="3"/>`;
    // casino (centerpiece)
    if (st.casino) {
      g += `<rect x="480" y="${base - 170}" width="190" height="166" fill="#6b2d5c" stroke="${INK}" stroke-width="3"/>`;
      g += `<path d="M 470 ${base - 170} L 575 ${base - 230} L 680 ${base - 170} Z" fill="#8e3b7a" stroke="${INK}" stroke-width="3"/>`;
      g += building(492, base - 18, 166, 110, '#6b2d5c', null, { windows: st.windows, lit: true });
      const on = Math.floor(t * 4) % 2;
      g += `<rect x="505" y="${base - 205}" width="140" height="34" rx="6" fill="#1a0f1a" stroke="${GOLD}" stroke-width="3"/>`;
      g += text('CASINO', 575, base - 180, 26, on ? '#ffe36b' : '#ff6bd2', { font: 'Anton', stroke: 0, ls: 3 });
      for (let i = 0; i < 8; i++) g += `<circle cx="${490 + i * 24}" cy="${base - 168}" r="4" fill="${(i + Math.floor(t * 6)) % 2 ? '#ffe36b' : '#ff6bd2'}"/>`;
      g += `<rect x="560" y="${base - 46}" width="30" height="42" fill="#2a1424" stroke="${INK}" stroke-width="3"/>`;
    }
    // trees
    for (const x of [225, 860, 680]) g += `<path d="M ${x} ${base - 8} l -22 0 l 22 -60 l 22 60 Z" fill="#2f6b4a" stroke="${INK}" stroke-width="3"/><path d="M ${x - 12} ${base - 38} l 12 -30 l 12 30" fill="none" stroke="#fff" stroke-width="5"/>`;
    // people
    const cols = ['#e05a5a', '#3d7bd9', '#2fa36b', '#e0a83d', '#8e5ad9', '#d95aa0', '#5ac2d9', '#d9d05a'];
    const mode = sc.people || 'walk';
    for (let i = 0; i < 12; i++) {
      let x, y;
      if (mode === 'loop') { const a = t * 0.9 + i * 0.52; x = 575 + Math.cos(a) * 200; y = base + 8 + Math.sin(a) * 22; }
      else { const span = 560, p = ((t * (18 + i * 3) + i * 97) % (span * 2)); const d = p < span ? p : span * 2 - p; x = 260 + d; y = base + 4 + (i % 3) * 9; }
      g += person(x, y, cols[i % cols.length], t, i);
    }
    return g;
  }

  function dome(sc, t) {
    let g = '';
    // base
    g += `<rect x="170" y="1180" width="740" height="150" rx="10" fill="#5b3a26" stroke="${INK}" stroke-width="5"/><rect x="170" y="1180" width="740" height="18" fill="${GOLD}"/><rect x="170" y="1312" width="740" height="18" fill="${GOLD}"/>`;
    for (let i = 0; i < 4; i++) g += `<circle cx="${230 + i * 45}" cy="1255" r="13" fill="none" stroke="${GOLD}" stroke-width="4"/><circle cx="${850 - i * 45}" cy="1255" r="13" fill="none" stroke="${GOLD}" stroke-width="4"/>`;
    const plaque = sc.plaque || TL.ep.plaque || '';
    if (plaque) {
      const lit = sc.plaque_pulse ? 0.6 + 0.4 * Math.sin(t * 8) : 1;
      g += `<rect x="410" y="1222" width="260" height="68" rx="12" fill="${GOLD}" stroke="#7a5a12" stroke-width="5" opacity="${lit}"/>` + text(plaque, 540, 1272, 46, '#3a2a08', { stroke: 0 });
    }
    // glass + snow (snow behind/inside, drawn over town)
    g += `<clipPath id="glass"><path d="M 195 1185 L 195 760 Q 195 440 540 440 Q 885 440 885 760 L 885 1185 Z"/></clipPath>`;
    g += `<g clip-path="url(#glass)"><g transform="translate(540 1182) scale(1.7) translate(-540 -1175)">${town(sc, t)}</g>`;
    for (let i = 0; i < 70; i++) {
      const x = 200 + ((i * 137) % 680) + Math.sin(t + i) * 10, y = 440 + ((t * (30 + (i % 5) * 8) + i * 53) % 760);
      g += `<circle cx="${x}" cy="${y}" r="${2 + (i % 3)}" fill="#fff" opacity="0.8"/>`;
    }
    g += `</g>`;
    g += `<path d="M 195 1185 L 195 760 Q 195 440 540 440 Q 885 440 885 760 L 885 1185" fill="#cfe8ff" fill-opacity="0.07" stroke="#e8f4ff" stroke-opacity="0.55" stroke-width="6"/>`;
    g += `<path d="M 250 1100 L 250 780 Q 252 540 420 488" stroke="#fff" stroke-opacity="0.35" stroke-width="16" fill="none" stroke-linecap="round"/>`;
    return g;
  }

  // Giant hand. pose: hover | point | pinch ; held: 'clock' | 'brick' | null
  function hand(pose, x, y, held, t) {
    const skin = '#f0c29a', sk2 = '#d9a47a';
    let g = `<g transform="translate(${x} ${y}) scale(1.35)">`;
    g += `<rect x="-95" y="-1000" width="190" height="760" fill="#1f2a44" stroke="${INK}" stroke-width="6"/><rect x="-100" y="-260" width="200" height="50" rx="8" fill="#f4f4f4" stroke="${INK}" stroke-width="6"/><circle cx="60" cy="-235" r="10" fill="${GOLD}"/>`;
    g += `<path d="M -80 -215 Q -95 -80 -60 -20 L 70 -20 Q 100 -90 85 -215 Z" fill="${skin}" stroke="${INK}" stroke-width="6"/>`;
    const finger = (fx, len, w = 34, curl = false) => curl
      ? `<rect x="${fx - w / 2}" y="-40" width="${w}" height="48" rx="${w / 2}" fill="${skin}" stroke="${INK}" stroke-width="6"/>`
      : `<rect x="${fx - w / 2}" y="-40" width="${w}" height="${len}" rx="${w / 2}" fill="${skin}" stroke="${INK}" stroke-width="6"/><path d="M ${fx - 10} ${len - 62} q 10 6 20 0" stroke="${sk2}" stroke-width="4" fill="none"/>`;
    if (pose === 'point') {
      g += finger(-52, 0, 34, true) + finger(-17, 0, 34, true) + finger(18, 0, 34, true) + finger(54, 200, 36);
      g += `<path d="M -85 -150 Q -140 -110 -110 -60 Q -80 -40 -60 -80" fill="${skin}" stroke="${INK}" stroke-width="6"/>`;
    } else if (pose === 'pinch') {
      g += finger(-50, 80) + finger(-15, 95) + finger(20, 95) + finger(55, 85);
      g += `<path d="M -85 -150 Q -150 -80 -70 30 L -40 20 Q -90 -60 -55 -110" fill="${skin}" stroke="${INK}" stroke-width="6"/>`;
    } else {
      g += finger(-55, 150) + finger(-18, 175) + finger(19, 170) + finger(56, 140);
      g += `<path d="M -80 -140 Q -160 -90 -150 -20 Q -130 0 -110 -30 Q -110 -80 -60 -100" fill="${skin}" stroke="${INK}" stroke-width="6"/>`;
    }
    g += `<rect x="12" y="-10" width="16" height="10" rx="3" fill="${GOLD}" stroke="${INK}" stroke-width="3"/>`;
    if (held === 'clock') g += `<g transform="translate(-60 60)"><circle r="26" fill="#fff" stroke="${INK}" stroke-width="4"/><path d="M 0 0 L 0 -16 M 0 0 L 10 4" stroke="${INK}" stroke-width="4"/></g>`;
    if (held === 'brick') g += `<rect x="-90" y="40" width="60" height="30" fill="#7a4a3a" stroke="${INK}" stroke-width="4"/>`;
    return g + `</g>`;
  }

  function handLayer(sc, frame, t) {
    const h = sc.hand;
    if (!h) return '';
    const local = frame - sc.start_frame, dur = sc.end_frame - sc.start_frame;
    const k = ease(local / Math.min(dur, (h.move || 0.7) * TL.fps));
    const from = h.from || h.to, to = h.to || h.from;
    let x = lerp(from[0], to[0], k), y = lerp(from[1], to[1], k);
    if (h.tap) y += Math.max(0, Math.sin(local * 0.5)) * 18;
    y += Math.sin(t * 1.5) * 6;
    return hand(h.pose || 'hover', x, y, h.held, t);
  }

  function caption(sc, frame) {
    const g = wordGroup(sc, frame, 4);
    if (!g) return '';
    const size = 82, y = sc.caption_y || 330;
    const ws = g.words.map((w) => ({ t: w.text, hl: w.hl, w: w.text.length * size * 0.56 + (w.hl ? 30 : 0) }));
    const gap = 22;
    let total = ws.reduce((a, w) => a + w.w, 0) + gap * (ws.length - 1);
    const scale = Math.min(1, 960 / total);
    let x = 540 - (total * scale) / 2;
    let out = `<g transform="translate(0 ${y})">`;
    ws.forEach((w, i) => {
      const cx = x + (w.w * scale) / 2;
      const pop = i === ws.length - 1 ? back(g.local / 4) * 0.15 + 0.85 : 1;
      out += `<g transform="translate(${cx} 0) scale(${scale * pop})">`;
      if (w.hl) out += `<rect x="${-w.w / 2}" y="${-size * 0.82}" width="${w.w}" height="${size * 1.08}" rx="14" fill="#f2c230"/>`;
      out += text(w.t, 0, 0, size, w.hl ? '#1a1410' : '#ffffff', { font: 'Nunito', weight: 900, stroke: w.hl ? 0 : 10, strokeColor: '#11152b' });
      out += `</g>`;
      x += (w.w + gap) * scale;
    });
    return out + `</g>`;
  }

  function topLabel(frame) {
    return `<rect x="70" y="120" width="940" height="66" rx="33" fill="#11152b" opacity="0.85"/>` +
      text(`${TL.ep.topic.toUpperCase()} · ${TL.ep.progress || ''}`, 540, 166, 34, GOLD, { font: 'Nunito', weight: 900, stroke: 0, ls: 2 });
  }

  function cta(frame) {
    const c = TL.ep.cta;
    if (!c || frame < TL.cta_start_frame) return '';
    const local = frame - TL.cta_start_frame, k = back(local / 9);
    return `<rect width="${W}" height="${H}" fill="#0b0e1f" opacity="${Math.min(0.55, local / 12)}"/>` +
      `<g transform="translate(540 760) scale(${k})"><rect x="-450" y="-170" width="900" height="360" rx="30" fill="#11152b" stroke="${GOLD}" stroke-width="8"/>` +
      text(c.line1, 0, -60, 84, GOLD, { stroke: 0 }) + text(c.line2, 0, 40, 38, '#fff', { font: 'Nunito', weight: 900, stroke: 0 }) +
      text(c.line3 || '', 0, 120, 34, '#c9d2ff', { font: 'Nunito', weight: 900, stroke: 0 }) + `</g>`;
  }

  window.loadTimeline = (tl) => { TL = tl; };
  window.renderFrame = (frame) => {
    const t = frame / TL.fps;
    const sc = sceneAt(TL, frame);
    const local = frame - sc.start_frame, dur = sc.end_frame - sc.start_frame;
    const z = 1 + (sc.zoom || 0.04) * ease(local / dur);
    const fx = sc.focus || [540, 960];
    let body = `<defs><radialGradient id="spot" cx="50%" cy="48%" r="60%"><stop offset="0%" stop-color="#fff3d0" stop-opacity="0.16"/><stop offset="100%" stop-color="#000" stop-opacity="0.55"/></radialGradient></defs>`;
    body += `<g transform="translate(${fx[0]} ${fx[1]}) scale(${z}) translate(${-fx[0]} ${-fx[1]})">` + curtain(t) + `<g transform="translate(0 140)">` + table() +
      `<ellipse cx="540" cy="1345" rx="420" ry="30" fill="#000" opacity="0.35"/>` + dome(sc, t) + `</g>` + handLayer(sc, frame, t) + `</g>`;
    body += topLabel(frame) + caption(sc, frame) + cta(frame);
    if (frame < 8) body += `<rect width="${W}" height="${H}" fill="#000" opacity="${1 - frame / 8}"/>`;
    document.getElementById('stage').innerHTML = `<svg xmlns="http://www.w3.org/2000/svg" width="${W}" height="${H}" viewBox="0 0 ${W} ${H}">${body}</svg>`;
  };
})();
