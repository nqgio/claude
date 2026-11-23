// "Pick Wrong" horror anthology: dark flat rooms, stick-figure POV character,
// doorbell-cam shots, big captions with green keywords, choice card ending.
(function () {
  const { esc, clamp, ease, back, sceneAt, wordGroup, text } = window.PU;
  const W = 1080, H = 1920, INK = '#0d0a12', GREEN = '#a6ff3d';
  let TL;

  // ---------- figure ----------
  function stick(x, y, s, o = {}) {
    const c = o.color || '#c9c6d1', t = o.t || 0, pose = o.pose || 'stand';
    const sw = 13;
    const breathe = Math.sin(t * 2) * 3;
    let arms, legs;
    if (pose === 'phone') arms = `M 0 -150 L -45 -95 L -10 -70 M 0 -150 L 40 -80`;
    else if (pose === 'scared') arms = `M 0 -150 L -55 -190 L -40 -235 M 0 -150 L 55 -190 L 40 -235`;
    else if (pose === 'walk') { const k = Math.sin(t * 7) * 30; arms = `M 0 -150 L ${-20 - k} -70 M 0 -150 L ${20 + k} -70`; }
    else arms = `M 0 -150 L -38 -60 M 0 -150 L 38 -60`;
    if (pose === 'walk') { const k = Math.sin(t * 7) * 34; legs = `M 0 -60 L ${-k} 40 M 0 -60 L ${k} 40`; }
    else legs = `M 0 -60 L -32 40 M 0 -60 L 32 40`;
    let g = `<g transform="translate(${x} ${y + breathe * 0.3}) scale(${s})">`;
    g += `<ellipse cx="0" cy="44" rx="70" ry="12" fill="#000" opacity="0.35"/>`;
    g += `<path d="M 0 -175 L 0 -60 ${arms} ${legs}" stroke="${c}" stroke-width="${sw}" stroke-linecap="round" stroke-linejoin="round" fill="none"/>`;
    if (pose === 'phone') g += `<rect x="-24" y="-92" width="26" height="40" rx="5" fill="#222" stroke="${c}" stroke-width="4"/><rect x="-21" y="-88" width="20" height="30" fill="#9fe3ff" opacity="0.8"/>`;
    if (o.hood) g += `<path d="M -60 -150 Q -78 -280 0 -285 Q 78 -280 60 -150 Z" fill="${o.hood}" stroke="#0a0f0b" stroke-width="5"/><path d="M -50 -150 L 50 -150 L 44 -70 L -44 -70 Z" fill="${o.hood}" stroke="#0a0f0b" stroke-width="5"/>`;
    g += `<circle cx="0" cy="-215" r="42" fill="${c}"/>`;
    const ey = o.eyes === 'glow' ? '#fff8c0' : INK;
    if (o.eyes !== 'none') g += `<circle cx="-14" cy="-218" r="${o.eyes === 'glow' ? 7 : 5}" fill="${ey}"/><circle cx="14" cy="-218" r="${o.eyes === 'glow' ? 7 : 5}" fill="${ey}"/>`;
    if (pose === 'scared') g += `<ellipse cx="0" cy="-196" rx="9" ry="12" fill="${INK}"/>`;
    return g + `</g>`;
  }

  // ---------- backgrounds ----------
  function room(wall, floor, horizon) {
    return `<rect width="${W}" height="${H}" fill="${wall}"/><rect y="${horizon}" width="${W}" height="${H - horizon}" fill="${floor}"/>` +
      [...Array(12)].map((_, i) => `<path d="M 0 ${horizon + 40 + i * 50} L ${W} ${horizon + 40 + i * 50}" stroke="#000" stroke-opacity="0.18" stroke-width="3"/>`).join('');
  }

  const BG = {
    bedroom(sc, t) {
      let g = room('#3a3150', '#3b2b24', 1300);
      g += `<rect x="640" y="520" width="300" height="380" fill="#1d2440" stroke="#211a2c" stroke-width="16"/><path d="M 790 520 L 790 900 M 640 710 L 940 710" stroke="#211a2c" stroke-width="10"/>`;
      g += `<circle cx="720" cy="610" r="40" fill="#e9e6c8" opacity="0.9"/><circle cx="735" cy="600" r="40" fill="#1d2440"/>`;
      g += `<rect x="40" y="1080" width="560" height="200" rx="16" fill="#4b3f66"/><rect x="40" y="1040" width="160" height="80" rx="30" fill="#d9d4e8"/><rect x="190" y="1060" width="410" height="100" rx="20" fill="#5d4d82"/>`;
      g += `<rect x="640" y="1120" width="170" height="180" fill="#2a2034"/><rect x="660" y="1070" width="130" height="60" rx="8" fill="#111"/>`;
      g += text(TL.ep.clock_short || '3:17', 725, 1117, 44, '#ff3b3b', { font: 'Nunito', weight: 900, stroke: 0 });
      g += `<circle cx="725" cy="1100" r="${120 + Math.sin(t * 3) * 6}" fill="#ff3b3b" opacity="0.07"/>`;
      return g;
    },
    hallway(sc, t) {
      let g = `<rect width="${W}" height="${H}" fill="#2a2338"/>`;
      g += `<path d="M 0 300 L 400 760 L 680 760 L 1080 300 L 1080 1920 L 680 1180 L 400 1180 L 0 1920 Z" fill="#3a3150"/>`;
      g += `<path d="M 0 1920 L 400 1180 L 680 1180 L 1080 1920 Z" fill="#33251f"/><path d="M 0 300 L 400 760 L 680 760 L 1080 300 Z" fill="#241d30"/>`;
      g += `<rect x="470" y="880" width="140" height="300" fill="#2a1d18" stroke="#120d16" stroke-width="8"/><circle cx="590" cy="1040" r="7" fill="#c9a34a"/>`;
      g += `<rect x="470" y="1172" width="140" height="10" fill="#ffe7a8" opacity="${0.5 + 0.4 * Math.sin(t * 5)}"/>`;
      g += `<rect x="150" y="760" width="120" height="160" fill="#1b1524" stroke="#5a4a3a" stroke-width="8" transform="skewY(20)"/>`;
      g += `<rect x="810" y="1050" width="110" height="150" fill="#1b1524" stroke="#5a4a3a" stroke-width="8" transform="skewY(-20)"/>`;
      return g;
    },
    door(sc, t) {
      let g = room('#352c47', '#33251f', 1500);
      g += `<rect x="290" y="560" width="500" height="940" fill="#4a2f22" stroke="#140e12" stroke-width="16"/>`;
      g += `<rect x="340" y="620" width="400" height="360" fill="none" stroke="#2c1c14" stroke-width="10"/><rect x="340" y="1040" width="400" height="400" fill="none" stroke="#2c1c14" stroke-width="10"/>`;
      g += `<circle cx="540" cy="760" r="14" fill="#c9a34a" stroke="#140e12" stroke-width="5"/><circle cx="720" cy="1080" r="20" fill="#c9a34a" stroke="#140e12" stroke-width="5"/>`;
      g += `<rect x="290" y="1494" width="500" height="14" fill="#ffe7a8" opacity="0.7"/>`;
      if (sc.visitor && sc.visitor !== 'none') g += `<rect x="420" y="1494" width="70" height="14" fill="#000"/><rect x="590" y="1494" width="70" height="14" fill="#000"/>`;
      return g;
    },
    doorcam(sc, t, frame) {
      // night-vision doorbell camera feed
      let g = `<rect width="${W}" height="${H}" fill="#0b120d"/>`;
      g += `<g opacity="0.95"><rect x="0" y="380" width="${W}" height="1240" fill="#1f3326"/>`;
      g += `<path d="M -100 1620 Q 540 1300 1180 1620 Z" fill="#2c4634"/>`;
      g += `<path d="M 0 1080 L 1080 1080" stroke="#3d5e47" stroke-width="10"/>`;
      for (let i = 0; i < 9; i++) g += `<rect x="${i * 130 + 10}" y="980" width="16" height="140" fill="#3d5e47"/>`;
      g += `<rect x="0" y="960" width="${W}" height="20" fill="#3d5e47"/>`;
      g += `<path d="M 330 1620 L 420 1250 L 660 1250 L 750 1620 Z" fill="#26402f"/><path d="M 380 1450 L 700 1450 M 400 1350 L 680 1350" stroke="#1a2c20" stroke-width="10"/>`;
      g += `<circle cx="540" cy="700" r="${260 + Math.sin(t * 2) * 8}" fill="#9fffb0" opacity="0.06"/>`;
      if (sc.visitor === 'far') g += stick(540, 1250, 0.85, { color: '#0a0f0b', eyes: 'glow', t });
      if (sc.visitor === 'close') g += stick(540, 1650, 2.3, { color: '#0a0f0b', eyes: 'glow', hood: '#2a2f36', t });
      if (sc.visitor === 'you') g += stick(540, 1650, 2.3, { color: '#b9c9bd', eyes: 'none', hood: TL.ep.you_color || '#4a5a8a', t });
      g += `</g>`;
      // scanlines, vignette, noise, HUD
      for (let y = 0; y < H; y += 6) g += `<rect y="${y}" width="${W}" height="2" fill="#000" opacity="0.18"/>`;
      g += `<rect width="${W}" height="${H}" fill="url(#vig)"/>`;
      const s = Math.floor(frame / 30) % 60;
      g += `<circle cx="80" cy="335" r="14" fill="#ff3030" opacity="${frame % 30 < 18 ? 1 : 0.2}"/>`;
      g += text('FRONT DOOR · LIVE', 110, 347, 38, '#e8ffe9', { font: 'Nunito', weight: 900, stroke: 0, anchor: 'start' });
      g += text(`${TL.ep.clock_cam || '03:17'}:${String(s).padStart(2, '0')}`, 1000, 347, 38, '#e8ffe9', { font: 'Nunito', weight: 900, stroke: 0, anchor: 'end' });
      if (frame % 47 < 2) g += `<rect width="${W}" height="${H}" fill="#e8ffe9" opacity="0.12"/>`;
      return g;
    },
    black() { return `<rect width="${W}" height="${H}" fill="#050307"/>`; },
  };

  // ---------- overlays ----------
  function hud(frame) {
    let g = text(TL.ep.clock || '3:17 AM', 60, 200, 92, '#f2eee6', { font: 'Anton', stroke: 0, anchor: 'start' });
    g += text((TL.ep.place || '').toUpperCase(), 64, 240, 26, '#a59fb3', { font: 'Nunito', weight: 900, stroke: 0, anchor: 'start', ls: 4 });
    g += `<rect x="760" y="150" width="260" height="62" rx="12" fill="#e8384f"/>` + text(`PART ${TL.ep.part}/${TL.ep.parts}`, 890, 196, 40, '#fff', { stroke: 0 });
    return g;
  }

  function titleCard(frame) {
    if (frame > 52) return '';
    const a = frame < 40 ? 1 : 1 - (frame - 40) / 12;
    const k = back(frame / 10);
    return `<g opacity="${a}"><rect width="${W}" height="${H}" fill="#050307" opacity="0.75"/>` +
      `<g transform="translate(540 900) scale(${k})">` + text(TL.ep.title.toUpperCase(), 0, 0, 110, '#f2eee6', { stroke: 14 }) +
      text(`PART ${TL.ep.part}`, 0, 110, 60, GREEN, { stroke: 10 }) + `</g></g>`;
  }

  function caption(sc, frame) {
    const g = wordGroup(sc, frame, 3);
    if (!g) return '';
    const parts = g.words.map((w) => ({ t: w.text.toUpperCase(), hl: w.hl }));
    const chars = parts.reduce((a, p) => a + p.t.length + 1, -1);
    const size = Math.min(104, Math.floor(960 / (chars * 0.66)));
    const k = back(g.local / 4) * 0.12 + 0.88;
    let tspans = parts.map((p, i) => `<tspan fill="${p.hl ? GREEN : '#ffffff'}">${esc(p.t)}${i < parts.length - 1 ? ' ' : ''}</tspan>`).join('');
    return `<g transform="translate(540 ${sc.caption_y || 1420}) scale(${k})"><text x="0" y="0" font-family="Nunito" font-weight="900" font-size="${size}" text-anchor="middle" stroke="${INK}" stroke-width="18" stroke-linejoin="round" paint-order="stroke">${tspans}</text></g>`;
  }

  function choiceCard(frame) {
    const c = TL.ep.cta;
    if (!c || frame < TL.cta_start_frame) return '';
    const local = frame - TL.cta_start_frame;
    let g = `<rect width="${W}" height="${H}" fill="#050307" opacity="${Math.min(0.7, local / 10)}"/>`;
    const k = back(local / 9);
    g += `<g transform="translate(540 640) scale(${k})">`;
    (c.question_lines || [c.question]).forEach((l, i) => { g += text(l.toUpperCase(), 0, i * 108, 96, '#f2eee6', { stroke: 14 }); });
    g += `</g>`;
    c.options.forEach((o, i) => {
      const kk = back((local - 6 - i * 4) / 8);
      const x = i === 0 ? 290 : 790, y = 1000;
      g += `<g transform="translate(${x} ${y}) scale(${kk}) rotate(${i ? 2 : -2})">` +
        `<rect x="-235" y="-75" width="470" height="150" rx="75" fill="${o.color}" stroke="${INK}" stroke-width="10"/>` +
        text(o.label.toUpperCase(), 0, 22, o.label.length > 12 ? 50 : 62, '#fff', { stroke: 8 }) +
        text(String.fromCharCode(65 + i), -190, -88, 54, '#fff', { stroke: 10 }) + `</g>`;
    });
    if (local > 14) g += text(c.prompt || 'COMMENT A OR B', 540, 1260, 54, GREEN, { stroke: 10 });
    if (local > 18) g += text('MOST COMMENTS DECIDE PART ' + (TL.ep.part + 1), 540, 1340, 40, '#cfc9da', { font: 'Nunito', weight: 900, stroke: 8 });
    return g;
  }

  window.loadTimeline = (tl) => { TL = tl; };
  window.renderFrame = (frame) => {
    const t = frame / TL.fps;
    const sc = sceneAt(TL, frame);
    const local = frame - sc.start_frame;
    const dur = sc.end_frame - sc.start_frame;
    const z = 1 + (sc.zoom || 0.06) * ease(local / dur);
    const fig = sc.figure;
    let world = (BG[sc.bg] || BG.black)(sc, t, frame);
    if (fig) world += stick(fig.x || 540, fig.y || 1560, fig.s || 1.6, { pose: fig.pose, t, hood: fig.hood });
    let body = `<defs><radialGradient id="vig" cx="50%" cy="45%" r="70%"><stop offset="55%" stop-color="#000" stop-opacity="0"/><stop offset="100%" stop-color="#000" stop-opacity="0.85"/></radialGradient></defs>`;
    body += `<g transform="translate(540 960) scale(${z}) translate(-540 -960)">${world}</g>`;
    if (sc.bg !== 'doorcam') body += `<rect width="${W}" height="${H}" fill="url(#vig)"/>`;
    if (sc.flash && local < 6) body += `<rect width="${W}" height="${H}" fill="#fff" opacity="${(6 - local) / 8}"/>`;
    body += hud(frame) + caption(sc, frame) + choiceCard(frame) + titleCard(frame);
    document.getElementById('stage').innerHTML = `<svg xmlns="http://www.w3.org/2000/svg" width="${W}" height="${H}" viewBox="0 0 ${W} ${H}">${body}</svg>`;
  };
})();
