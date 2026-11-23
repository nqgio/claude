// "Last Exit": second-person crime saga. Night city, stats HUD (cash / heat / trust),
// karaoke captions (spoken words white, upcoming grey), vote stamps, A/B choice ending.
(function () {
  const { esc, clamp, ease, back, lerp, sceneAt, text } = window.PU;
  const W = 1080, H = 1920, INK = '#0c0d12';
  let TL;

  // ---------- backgrounds ----------
  function skyline(t, y0 = 900) {
    let g = `<rect width="${W}" height="${H}" fill="url(#night)"/>`;
    const bl = [[0, 520, 180], [160, 640, 140], [280, 450, 200], [470, 700, 150], [610, 560, 170], [770, 480, 160], [920, 620, 200]];
    for (const [x, top, w] of bl) {
      g += `<rect x="${x}" y="${top}" width="${w}" height="${y0 - top + 400}" fill="#141a2b"/>`;
      for (let yy = top + 30; yy < y0 + 200; yy += 46) for (let xx = x + 16; xx < x + w - 20; xx += 34)
        if (((xx * 7 + yy * 3) % 11) < 4) g += `<rect x="${xx}" y="${yy}" width="16" height="22" fill="#f5c46b" opacity="${0.55 + 0.3 * Math.sin(t + xx)}"/>`;
    }
    return g;
  }
  function streetlamp(x, y, t) {
    return `<rect x="${x - 8}" y="${y}" width="16" height="${1500 - y}" fill="#222733"/><path d="M ${x} ${y} q 0 -40 60 -40 l 30 0" stroke="#222733" stroke-width="14" fill="none"/>` +
      `<path d="M ${x + 70} ${y - 34} L ${x - 160} 1520 L ${x + 330} 1520 Z" fill="#ffd27a" opacity="${0.13 + 0.02 * Math.sin(t * 9)}"/><circle cx="${x + 80}" cy="${y - 34}" r="16" fill="#fff1c4"/>`;
  }
  function sedan(x, y, s, c, lights) {
    let g = `<g transform="translate(${x} ${y}) scale(${s})">`;
    g += `<path d="M -260 0 L -260 -80 Q -250 -110 -180 -120 L -110 -190 Q -90 -205 60 -205 Q 120 -205 160 -130 L 240 -115 Q 270 -105 270 -60 L 270 0 Z" fill="${c}" stroke="${INK}" stroke-width="8"/>`;
    g += `<path d="M -95 -180 L 40 -185 L 40 -128 L -150 -125 Z M 60 -185 Q 110 -183 140 -130 L 60 -128 Z" fill="#30405e" stroke="${INK}" stroke-width="6"/>`;
    g += `<circle cx="-160" cy="0" r="50" fill="#15171c" stroke="${INK}" stroke-width="8"/><circle cx="170" cy="0" r="50" fill="#15171c" stroke="${INK}" stroke-width="8"/><circle cx="-160" cy="0" r="18" fill="#777"/><circle cx="170" cy="0" r="18" fill="#777"/>`;
    if (lights) g += `<path d="M 270 -70 L 700 -150 L 700 40 Z" fill="#fff4c4" opacity="0.18"/><rect x="250" y="-85" width="24" height="22" fill="#fff4c4"/>`;
    g += `<rect x="-262" y="-80" width="14" height="22" fill="#ff3040"/>`;
    return g + `</g>`;
  }
  const BG = {
    street(sc, t) {
      return skyline(t) + `<rect y="1450" width="${W}" height="470" fill="#1b1d24"/><rect y="1440" width="${W}" height="20" fill="#2c2f3a"/>` +
        streetlamp(880, 760, t) + sedan(250, 1560, 0.9, '#5a1d24', false) + `<rect y="1450" width="${W}" height="470" fill="url(#wet)"/>`;
    },
    lot(sc, t) {
      return skyline(t, 820) + `<rect y="1380" width="${W}" height="540" fill="#202229"/>` +
        [0, 1, 2, 3].map((i) => `<path d="M ${120 + i * 260} 1400 L ${60 + i * 300} 1920" stroke="#e8e2c4" stroke-width="10" opacity="0.5"/>`).join('') +
        streetlamp(140, 700, t) + sedan(820, 1500, 0.85, '#2a2e3a', true);
    },
    car(sc, t) {
      // driver POV interior at night, road rushing toward camera
      let g = `<rect width="${W}" height="${H}" fill="#070910"/>`;
      g += `<path d="M 60 300 L 1020 300 L 1080 1000 L 0 1000 Z" fill="#0f1422"/>`;
      g += `<path d="M 540 560 L 0 1000 L 1080 1000 Z" fill="#191b22"/>`;
      for (let i = 0; i < 6; i++) {
        const p = ((t * 1.6 + i / 6) % 1), y = 560 + p * p * 440, w = 4 + p * 30, h = 10 + p * 70;
        g += `<rect x="${540 - w / 2}" y="${y}" width="${w}" height="${h}" fill="#e8e2c4" opacity="${0.3 + p * 0.6}"/>`;
      }
      for (let i = 0; i < 5; i++) {
        const p = ((t * 0.9 + i / 5) % 1), x = 540 + (i % 2 ? 1 : -1) * (60 + p * p * 700), y = 540 - p * 120;
        g += `<circle cx="${x}" cy="${y}" r="${4 + p * 26}" fill="#f5c46b" opacity="${0.25 + p * 0.5}"/>`;
      }
      g += `<path d="M 0 0 L 1080 0 L 1080 300 L 60 300 L 0 1000 Z" fill="#05060a"/><path d="M 1080 300 L 1020 300 L 1080 1000 Z" fill="#05060a"/>`;
      g += `<rect x="380" y="320" width="320" height="70" rx="14" fill="#0c0e15" stroke="#222" stroke-width="5"/>`;
      g += `<rect y="1000" width="${W}" height="920" fill="#0b0c11"/><path d="M 0 1000 Q 540 930 1080 1000 L 1080 1100 L 0 1100 Z" fill="#14161d"/>`;
      g += `<circle cx="300" cy="1060" r="40" fill="#0a0b10" stroke="#ff6b3d" stroke-width="3" opacity="0.8"/><circle cx="420" cy="1060" r="40" fill="#0a0b10" stroke="#ff6b3d" stroke-width="3" opacity="0.8"/>`;
      return g;
    },
  };

  function wheel(x, y, t) {
    const a = Math.sin(t * 1.3) * 4;
    return `<g transform="translate(${x} ${y}) rotate(${a})"><circle r="250" fill="none" stroke="#111318" stroke-width="54"/><circle r="250" fill="none" stroke="#2a2d36" stroke-width="10"/>` +
      `<path d="M -230 30 L -60 40 M 230 30 L 60 40 M 0 70 L 0 230" stroke="#111318" stroke-width="44"/><circle r="80" fill="#15171e" stroke="#2a2d36" stroke-width="8"/></g>`;
  }

  function actor(id, o, frame, t, sc) {
    const st = TL.cast_states[id];
    if (!st) return '';
    const talk = sc.speaker === id ? (sc.mouth[frame - sc.start_frame] || 0) : 0;
    const blink = ((frame + id.length * 31) % 97) < 3 ? 1 : 0;
    const s = o.s || 1.0;
    const x = (o.x === undefined ? 540 : o.x) - 400 * s, y = (o.y || H) - 1100 * s;
    return `<g transform="translate(${x} ${y}) scale(${s})">${window.characterSVG(st, { expression: o.expression || 'neutral', pose: o.pose, talk, blink, t, bob: Math.sin(t * 2 + x) * 4 })}</g>`;
  }

  // ---------- overlays ----------
  function hudValue(key, frame, sc) {
    const prev = TL.scenes[Math.max(0, TL.scenes.indexOf(sc) - 1)];
    const a = (prev === sc ? TL.ep.hud : prev.hud)[key], b = sc.hud[key];
    const k = ease((frame - sc.start_frame) / 18);
    if (typeof a === 'number' && typeof b === 'number') return lerp(a, b, k);
    return b;
  }
  function fmt(key, v) {
    if (typeof v !== 'number') return v;
    if (key === 'cash') return (v < 0 ? '-$' : '$') + Math.round(Math.abs(v)).toLocaleString('en-US');
    return Math.round(v) + '%';
  }
  function hud(frame, sc) {
    let g = '';
    const items = [['cash', 'CASH', 330], ['heat', 'HEAT', 220], ['trust', 'TRUST', 220]];
    let x = 50;
    for (const [k, label, w] of items) {
      const v = hudValue(k, frame, sc);
      const col = k === 'cash' ? (v < 0 ? '#ff5a6a' : '#f2f2f2') : k === 'heat' ? '#ff5a6a' : '#6be3ff';
      g += `<rect x="${x}" y="120" width="${w}" height="120" rx="14" fill="#0c0d12" opacity="0.82" stroke="#2c2f3a" stroke-width="3"/>`;
      g += text(label, x + 22, 158, 24, '#9aa0b4', { font: 'Inter', weight: 800, stroke: 0, anchor: 'start', ls: 3 });
      g += text(fmt(k, v), x + 22, 215, 50, col, { font: 'Inter', weight: 800, stroke: 0, anchor: 'start' });
      x += w + 20;
    }
    g += `<rect x="50" y="262" width="150" height="46" rx="8" fill="#e8384f"/>` + text(`PART ${TL.ep.part}`, 125, 296, 30, '#fff', { stroke: 0 });
    return g;
  }

  function caption(sc, frame) {
    const ws = sc.words || [];
    if (!ws.length || frame < ws[0].f0 || frame > ws[ws.length - 1].f1 + 8) return '';
    // fixed groups of up to 3 words, broken at punctuation
    const groups = []; let cur = [];
    ws.forEach((w) => { cur.push(w); if (cur.length === 3 || /[.!?,]$/.test(w.text)) { groups.push(cur); cur = []; } });
    if (cur.length) groups.push(cur);
    const grp = groups.find((g) => frame >= g[0].f0 && frame <= g[g.length - 1].f1 + 3) || groups.filter((g) => frame >= g[0].f0).pop();
    if (!grp) return '';
    const line = grp.map((w) => w.text).join(' ');
    const size = Math.min(86, Math.floor(940 / (line.length * 0.6)));
    const spans = grp.map((w, i) => `<tspan fill="${frame >= w.f0 ? (w.hl ? '#ffd23f' : '#ffffff') : '#7b7f8c'}">${esc(w.text)}${i < grp.length - 1 ? ' ' : ''}</tspan>`).join('');
    return `<text x="540" y="${sc.caption_y || 1600}" font-family="Inter" font-weight="800" font-size="${size}" text-anchor="middle" stroke="${INK}" stroke-width="12" stroke-linejoin="round" paint-order="stroke">${spans}</text>`;
  }

  function stamp(sc, frame) {
    if (!sc.stamp) return '';
    const local = frame - sc.start_frame - (sc.stamp_at || 10);
    if (local < 0) return '';
    const k = local < 5 ? 1.8 - 0.8 * (local / 5) : 1;
    return `<g transform="translate(540 900) rotate(-12) scale(${k})" opacity="${Math.min(1, local / 3)}"><rect x="-330" y="-70" width="660" height="140" rx="12" fill="none" stroke="#e8384f" stroke-width="12"/>` +
      text(sc.stamp, 0, 30, 84, '#e8384f', { font: 'Inter', weight: 800, stroke: 0, ls: 4 }) + `</g>`;
  }

  function choice(frame) {
    const c = TL.ep.cta;
    if (!c || frame < TL.cta_start_frame) return '';
    const local = frame - TL.cta_start_frame;
    let g = `<rect width="${W}" height="${H}" fill="#05060a" opacity="${Math.min(0.72, local / 10)}"/>`;
    g += `<g transform="translate(540 700) scale(${back(local / 9)})">` + text('YOUR CALL', 0, -40, 54, '#9aa0b4', { font: 'Inter', weight: 800, stroke: 0, ls: 8 });
    (c.question_lines || []).forEach((l, i) => { g += text(l, 0, 60 + i * 100, 88, '#fff', { font: 'Inter', weight: 800, stroke: 0 }); });
    g += `</g>`;
    c.options.forEach((o, i) => {
      const kk = back((local - 6 - i * 4) / 8), y = 1080 + i * 190;
      g += `<g transform="translate(540 ${y}) scale(${kk})"><rect x="-400" y="-70" width="800" height="140" rx="20" fill="#0c0d12" stroke="${o.color}" stroke-width="8"/>` +
        `<rect x="-400" y="-70" width="130" height="140" rx="20" fill="${o.color}"/>` + text(String.fromCharCode(65 + i), -335, 28, 80, '#fff', { stroke: 0 }) +
        text(o.label.toUpperCase(), 60, 24, 62, '#fff', { font: 'Inter', weight: 800, stroke: 0 }) + `</g>`;
    });
    if (local > 16) g += text(c.prompt || 'MOST COMMENTS DECIDE PART ' + (TL.ep.part + 1), 540, 1520, 40, '#ffd23f', { font: 'Inter', weight: 800, stroke: 0, ls: 2 });
    return g;
  }

  window.loadTimeline = (tl) => {
    TL = tl;
    TL.cast_states = Object.assign({}, TL.ep.characters || {});
    let h = Object.assign({}, TL.ep.hud);
    for (const sc of TL.scenes) { h = Object.assign({}, h, sc.hud || {}); sc.hud = h; }
  };
  window.renderFrame = (frame) => {
    const t = frame / TL.fps;
    const sc = sceneAt(TL, frame);
    const local = frame - sc.start_frame, dur = sc.end_frame - sc.start_frame;
    const z = 1 + (sc.zoom === undefined ? 0.05 : sc.zoom) * ease(local / dur);
    let sx = 0, sy = 0;
    if (sc.shake) { const a = Math.max(0, 1 - ((local % 20) / 10)); sx = Math.sin(frame * 3.1) * 14 * a; sy = Math.cos(frame * 2.3) * 10 * a; }
    let world = (BG[sc.bg] || BG.street)(sc, t);
    for (const [id, o] of Object.entries(sc.actors || {})) world += actor(id, o, frame, t, sc);
    if (sc.bg === 'car') world += wheel(sc.wheel_x || 600, 1700, t);
    world += `<rect width="${W}" height="${H}" fill="#0a1a3a" opacity="0.18"/>`;
    let body = `<defs><linearGradient id="night" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stop-color="#05070f"/><stop offset="100%" stop-color="#1c2340"/></linearGradient>` +
      `<linearGradient id="wet" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stop-color="#f5c46b" stop-opacity="0.12"/><stop offset="100%" stop-color="#000" stop-opacity="0"/></linearGradient>` +
      `<radialGradient id="vig" cx="50%" cy="50%" r="70%"><stop offset="60%" stop-color="#000" stop-opacity="0"/><stop offset="100%" stop-color="#000" stop-opacity="0.8"/></radialGradient></defs>`;
    body += `<g transform="translate(${540 + sx} ${960 + sy}) scale(${z}) translate(-540 -960)">${world}</g><rect width="${W}" height="${H}" fill="url(#vig)"/>`;
    if (sc.flash && local < 6) body += `<rect width="${W}" height="${H}" fill="#fff" opacity="${(6 - local) / 8}"/>`;
    body += hud(frame, sc) + caption(sc, frame) + stamp(sc, frame) + choice(frame);
    if (frame < 8) body += `<rect width="${W}" height="${H}" fill="#000" opacity="${1 - frame / 8}"/>`;
    document.getElementById('stage').innerHTML = `<svg xmlns="http://www.w3.org/2000/svg" width="${W}" height="${H}" viewBox="0 0 ${W} ${H}">${body}</svg>`;
  };
})();
