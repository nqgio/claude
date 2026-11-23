// "In This Town": 3D blocky-character stories rendered with three.js (original assets, no Roblox IP).
// Snowy suburb, streetlamps, houses, blocky avatars with face textures. SVG caption overlay.
import * as THREE from '../vendor/three.module.min.js';

const { esc, clamp, ease, back, lerp, sceneAt } = window.PU;
const W = 1080, H = 1920;
let TL, renderer, scene, camera, sun, hemi, lamps = [], actors = {}, signTex, windows = [];
window.__dbg = () => Object.fromEntries(Object.entries(actors).map(([k, a]) => [k, [a.visible, a.position.toArray().map((v) => +v.toFixed(2)), camera.position.toArray().map((v) => +v.toFixed(2))]]));

// ---------- helpers ----------
const mat = (c, o = {}) => new THREE.MeshLambertMaterial(Object.assign({ color: c }, o));
function box(w, h, d, m, x = 0, y = 0, z = 0, parent) {
  const me = new THREE.Mesh(new THREE.BoxGeometry(w, h, d), m);
  me.position.set(x, y, z); me.castShadow = true; me.receiveShadow = true;
  (parent || scene).add(me); return me;
}
function canvasTex(w, h, draw) {
  const c = document.createElement('canvas'); c.width = w; c.height = h;
  draw(c.getContext('2d'), w, h);
  const t = new THREE.CanvasTexture(c); t.colorSpace = THREE.SRGBColorSpace; t.anisotropy = 4; return t;
}

// ---------- faces ----------
const faceCache = {};
function faceTex(expr, talk, glasses, blink) {
  const key = `${expr}|${talk}|${glasses}|${blink}`;
  if (faceCache[key]) return faceCache[key];
  faceCache[key] = canvasTex(256, 256, (g) => {
    g.fillStyle = '#00000000'; g.clearRect(0, 0, 256, 256);
    g.fillStyle = '#1b1b1b'; g.strokeStyle = '#1b1b1b'; g.lineCap = 'round';
    const eyeY = 110, ex = [88, 168];
    // brows
    g.lineWidth = 9;
    const browTilt = { worried: [-10, 10], shocked: [-16, -16], angry: [12, -12], neutral: [0, 0], smile: [-4, -4], suspicious: [8, 0] }[expr] || [0, 0];
    g.beginPath(); g.moveTo(60, 72 + browTilt[1]); g.lineTo(112, 72 + browTilt[0]); g.stroke();
    g.beginPath(); g.moveTo(144, 72 + browTilt[0]); g.lineTo(196, 72 + browTilt[1]); g.stroke();
    // eyes
    for (const x of ex) {
      if (blink) { g.lineWidth = 7; g.beginPath(); g.moveTo(x - 14, eyeY); g.lineTo(x + 14, eyeY); g.stroke(); continue; }
      g.fillStyle = '#fff'; g.beginPath(); g.ellipse(x, eyeY, expr === 'shocked' ? 22 : 18, expr === 'shocked' ? 26 : 20, 0, 0, Math.PI * 2); g.fill();
      g.lineWidth = 4; g.stroke();
      g.fillStyle = '#1b1b1b'; g.beginPath(); g.arc(x + (expr === 'suspicious' ? 6 : 0), eyeY + 3, expr === 'shocked' ? 7 : 10, 0, Math.PI * 2); g.fill();
    }
    if (glasses) { g.lineWidth = 6; g.strokeRect(58, 84, 60, 50); g.strokeRect(138, 84, 60, 50); g.beginPath(); g.moveTo(118, 104); g.lineTo(138, 104); g.stroke(); }
    // mouth
    g.lineWidth = 8; g.fillStyle = '#3a1414';
    if (talk > 0.3 || expr === 'shocked') {
      const h = expr === 'shocked' ? 34 : 14 + talk * 22;
      g.beginPath(); g.ellipse(128, 182, expr === 'shocked' ? 20 : 26, h / 2, 0, 0, Math.PI * 2); g.fill();
    } else if (expr === 'smile') { g.beginPath(); g.arc(128, 160, 34, 0.2 * Math.PI, 0.8 * Math.PI); g.stroke(); }
    else if (expr === 'worried' || expr === 'angry') { g.beginPath(); g.arc(128, 205, 28, 1.2 * Math.PI, 1.8 * Math.PI); g.stroke(); }
    else { g.beginPath(); g.moveTo(104, 184); g.lineTo(152, 182); g.stroke(); }
  });
  return faceCache[key];
}

// ---------- avatar ----------
function avatar(o) {
  const root = new THREE.Group();
  const skin = mat(o.skin || '#f2c94c'), shirt = mat(o.shirt || '#3d7bd9'), pants = mat(o.pants || '#2c3e50');
  const torso = box(2, 2, 1, shirt, 0, 3, 0, root);
  const mk = (x, y, m, h = 2) => { const pivot = new THREE.Group(); pivot.position.set(x, y, 0); root.add(pivot); box(1, h, 1, m, 0, -h / 2, 0, pivot); return pivot; };
  const armL = mk(-1.5, 4, o.sleeves === false ? skin : shirt), armR = mk(1.5, 4, o.sleeves === false ? skin : shirt);
  // hands
  box(0.98, 0.5, 0.98, skin, 0, -1.75, 0, armL); box(0.98, 0.5, 0.98, skin, 0, -1.75, 0, armR);
  const legL = mk(-0.5, 2, pants), legR = mk(0.5, 2, pants);
  const head = new THREE.Group(); head.position.set(0, 4.65, 0); root.add(head);
  box(1.3, 1.3, 1.3, skin, 0, 0, 0, head);
  const faceMat = new THREE.MeshBasicMaterial({ map: faceTex('neutral', 0, o.glasses, 0), transparent: true });
  const face = new THREE.Mesh(new THREE.PlaneGeometry(1.25, 1.25), faceMat); face.position.set(0, 0, 0.66); head.add(face);
  const hc = mat(o.hair_color || '#3b2a1e');
  if (o.hair === 'short') { box(1.4, 0.35, 1.4, hc, 0, 0.62, 0, head); box(1.4, 0.7, 0.3, hc, 0, 0.35, -0.55, head); }
  if (o.hair === 'beanie') { box(1.42, 0.6, 1.42, hc, 0, 0.55, 0, head); box(1.46, 0.22, 1.46, mat('#ffffff'), 0, 0.3, 0, head); }
  if (o.hair === 'bald_gray') { box(1.36, 0.4, 1.0, hc, 0, 0.2, -0.2, head); box(0.2, 0.5, 1.0, hc, -0.64, 0.05, 0, head); box(0.2, 0.5, 1.0, hc, 0.64, 0.05, 0, head); }
  if (o.hair === 'cap') { box(1.42, 0.45, 1.42, hc, 0, 0.6, 0, head); box(1.2, 0.12, 0.7, hc, 0, 0.42, 0.95, head); }
  if (o.scarf) box(1.6, 0.4, 1.2, mat(o.scarf), 0, 4.05, 0, root);
  root.userData = { armL, armR, legL, legR, head, faceMat, glasses: o.glasses };
  scene.add(root);
  return root;
}

function poseAvatar(av, a, t, talk, blink) {
  const u = av.userData;
  const walking = a.walk;
  const sw = walking ? Math.sin(t * 8) * 0.7 : Math.sin(t * 1.5) * 0.04;
  u.armL.rotation.x = sw; u.armR.rotation.x = -sw; u.legL.rotation.x = -sw; u.legR.rotation.x = sw;
  if (a.pose === 'phone') { u.armR.rotation.x = -1.9; u.armR.rotation.z = 0.25; }
  if (a.pose === 'scared') { u.armL.rotation.x = -2.6; u.armR.rotation.x = -2.6; u.armL.rotation.z = -0.3; u.armR.rotation.z = 0.3; }
  if (a.pose === 'point') { u.armR.rotation.x = -1.6; }
  if (a.pose === 'wave') { u.armR.rotation.z = 2.6 + Math.sin(t * 8) * 0.3; }
  u.head.rotation.y = (a.look || 0) * Math.PI / 180 + (walking ? 0 : Math.sin(t * 0.7) * 0.05);
  u.head.rotation.x = talk > 0.2 ? Math.sin(t * 9) * 0.04 : 0;
  av.position.y = walking ? Math.abs(Math.sin(t * 8)) * 0.15 : 0;
  u.faceMat.map = faceTex(a.expression || 'neutral', talk > 0.3 ? Math.round(talk * 3) / 3 : 0, u.glasses, blink);
}

// ---------- world ----------
function house(x, z, c, roofC, rotY = 0) {
  const g = new THREE.Group(); g.position.set(x, 0, z); g.rotation.y = rotY; scene.add(g);
  box(10, 7, 8, mat(c), 0, 3.5, 0, g);
  for (let i = 0; i < 6; i++) box(10.05, 0.12, 8.05, mat('#00000022', { transparent: true, opacity: 0.12 }), 0, 1 + i * 1.1, 0, g);
  const roof = new THREE.Mesh(new THREE.CylinderGeometry(0.01, 7.6, 4, 4, 1), mat('#f4f6f8'));
  roof.rotation.y = Math.PI / 4; roof.scale.set(1.0, 1, 0.8); roof.position.set(0, 9, 0); roof.castShadow = true; g.add(roof);
  const eave = new THREE.Mesh(new THREE.CylinderGeometry(0.01, 7.7, 4, 4, 1, true), mat(roofC, { side: THREE.DoubleSide }));
  eave.rotation.y = Math.PI / 4; eave.scale.set(1.0, 1, 0.8); eave.position.set(0, 8.95, 0); g.add(eave);
  box(2.2, 4, 0.3, mat('#5a3a24'), 0, 2, 4.05, g);
  for (const wx of [-3.2, 3.2]) {
    const wm = new THREE.MeshLambertMaterial({ color: '#9fd0ff', emissive: '#ffcf6b', emissiveIntensity: 0 });
    box(2, 2, 0.3, wm, wx, 4.2, 4.05, g); windows.push(wm);
    box(2.4, 0.3, 0.5, mat('#ffffff'), wx, 3.1, 4.1, g);
  }
  box(4, 0.4, 2.4, mat('#cfd6dc'), 0, 0.2, 5.3, g);
  return g;
}
function tree(x, z, s = 1) {
  const g = new THREE.Group(); g.position.set(x, 0, z); g.scale.setScalar(s); scene.add(g);
  box(0.8, 2, 0.8, mat('#5a3a24'), 0, 1, 0, g);
  [[3.2, 3, 2.6], [2.5, 2.6, 4.4], [1.7, 2.2, 6]].forEach(([r, h, y]) => {
    const c = new THREE.Mesh(new THREE.ConeGeometry(r, h, 6), mat('#2f6b4a')); c.position.y = y; c.castShadow = true; g.add(c);
    const sn = new THREE.Mesh(new THREE.ConeGeometry(r * 0.55, h * 0.45, 6), mat('#f4f6f8')); sn.position.y = y + h * 0.3; g.add(sn);
  });
}
function lamp(x, z) {
  const g = new THREE.Group(); g.position.set(x, 0, z); scene.add(g);
  box(0.35, 9, 0.35, mat('#2b2f36'), 0, 4.5, 0, g);
  box(0.3, 0.3, 2, mat('#2b2f36'), 0, 9, 0.9, g);
  const bulbM = new THREE.MeshLambertMaterial({ color: '#555', emissive: '#fff1b8', emissiveIntensity: 0 });
  box(0.9, 0.5, 0.9, bulbM, 0, 8.7, 1.8, g);
  const light = new THREE.PointLight('#ffd27a', 0, 22, 1.6); light.position.set(x, 8.2, z + 1.8); scene.add(light);
  lamps.push({ bulbM, light });
}
function sign(x, z, lines) {
  const g = new THREE.Group(); g.position.set(x, 0, z); scene.add(g);
  box(0.3, 3, 0.3, mat('#5a3a24'), -1.6, 1.5, 0, g); box(0.3, 3, 0.3, mat('#5a3a24'), 1.6, 1.5, 0, g);
  signTex = canvasTex(512, 320, (c, w, h) => {
    c.fillStyle = '#7a5230'; c.fillRect(0, 0, w, h); c.strokeStyle = '#4a2f1a'; c.lineWidth = 18; c.strokeRect(9, 9, w - 18, h - 18);
    c.fillStyle = '#f4ead6'; c.font = 'bold 54px Anton, Impact, sans-serif'; c.textAlign = 'center';
    lines.forEach((l, i) => c.fillText(l, w / 2, 90 + i * 70));
  });
  const board = new THREE.Mesh(new THREE.BoxGeometry(4.4, 2.75, 0.25), [mat('#7a5230'), mat('#7a5230'), mat('#7a5230'), mat('#7a5230'), new THREE.MeshLambertMaterial({ map: signTex }), mat('#7a5230')]);
  board.position.set(0, 3.6, 0); board.castShadow = true; g.add(board);
}

function buildWorld(ep) {
  scene = new THREE.Scene();
  scene.fog = new THREE.Fog('#cfd8e3', 40, 140);
  hemi = new THREE.HemisphereLight('#dfe9ff', '#9aa3ad', 1.0); scene.add(hemi);
  sun = new THREE.DirectionalLight('#ffffff', 1.6); sun.position.set(30, 50, 25); sun.castShadow = true;
  sun.shadow.mapSize.set(2048, 2048); Object.assign(sun.shadow.camera, { left: -60, right: 60, top: 60, bottom: -60, near: 1, far: 160 });
  scene.add(sun);
  const ground = new THREE.Mesh(new THREE.PlaneGeometry(400, 400), mat('#f1f4f7')); ground.rotation.x = -Math.PI / 2; ground.receiveShadow = true; scene.add(ground);
  const road = new THREE.Mesh(new THREE.PlaneGeometry(400, 9), mat('#8d939b')); road.rotation.x = -Math.PI / 2; road.position.y = 0.02; road.receiveShadow = true; scene.add(road);
  for (let x = -120; x < 120; x += 8) { const d = new THREE.Mesh(new THREE.PlaneGeometry(3, 0.35), mat('#f4f4f4')); d.rotation.x = -Math.PI / 2; d.position.set(x, 0.03, 0); scene.add(d); }
  for (const zz of [-6, 6]) { const s = new THREE.Mesh(new THREE.PlaneGeometry(400, 3), mat('#c9cfd6')); s.rotation.x = -Math.PI / 2; s.position.set(0, 0.04, zz); s.receiveShadow = true; scene.add(s); }
  const cols = ['#d98c8c', '#8cb3d9', '#e8d18f', '#9fcfa4', '#c7a3d9', '#e6b089', '#a7c0c9'];
  for (let i = -5; i <= 5; i++) {
    house(i * 16, -17, cols[(i + 7) % cols.length], '#6a4a3a');
    house(i * 16 + 8, 17, cols[(i + 10) % cols.length], '#4a5a6a', Math.PI);
  }
  for (let i = -6; i <= 6; i++) { tree(i * 16 + 7, -24, 1.1); tree(i * 16 - 2, 25, 1.0); }
  for (let i = -6; i <= 6; i++) { lamp(i * 16 + 4, -7.5); }
  sign(ep.sign_pos?.[0] ?? 6, ep.sign_pos?.[2] ?? -7.5, ep.sign_lines || ['BE HOME', 'BEFORE THE', 'LIGHTS COME ON']);
  // snow particles
  const n = 1500, pos = new Float32Array(n * 3);
  for (let i = 0; i < n; i++) { pos[i * 3] = (Math.random() - 0.5) * 120; pos[i * 3 + 1] = Math.random() * 40; pos[i * 3 + 2] = (Math.random() - 0.5) * 80; }
  const pg = new THREE.BufferGeometry(); pg.setAttribute('position', new THREE.BufferAttribute(pos, 3));
  const snow = new THREE.Points(pg, new THREE.PointsMaterial({ color: '#ffffff', size: 0.25 })); snow.userData.base = pos.slice(); scene.add(snow); scene.userData.snow = snow;
  for (const [id, o] of Object.entries(ep.characters || {})) actors[id] = avatar(o);
}

const TIMES = {
  day: { sky: '#a9cdf2', fog: '#cfdbe8', sun: 2.2, hemi: 1.35 },
  dusk: { sky: '#e9a07a', fog: '#c99a8f', sun: 0.7, hemi: 0.65 },
  night: { sky: '#1c2440', fog: '#1c2440', sun: 0.12, hemi: 0.28 },
};

function applyTime(name, lampsOn, t) {
  const T = TIMES[name] || TIMES.day;
  scene.background = new THREE.Color(T.sky); scene.fog.color = new THREE.Color(T.fog);
  sun.intensity = T.sun; hemi.intensity = T.hemi;
  sun.color = new THREE.Color(name === 'dusk' ? '#ffb48a' : '#ffffff');
  let on = lampsOn === 'on' ? 1 : lampsOn === 'flicker' ? (Math.sin(t * 37) * Math.sin(t * 13) > 0.2 ? 0.8 : 0.05) : 0;
  for (const l of lamps) { l.light.intensity = on * 60; l.bulbM.emissiveIntensity = on * 2; }
  for (const w of windows) w.emissiveIntensity = name === 'day' ? 0 : name === 'dusk' ? 0.5 : 0.9;
}

// ---------- overlay ----------
function captionSVG(sc, frame) {
  const g = PU.wordGroup(sc, frame, 3);
  if (!g) return '';
  const words = g.words.map((w, i) => ({ t: w.text.toUpperCase(), i }));
  // two-line layout: first ~half on line 1
  const lines = words.length > 2 ? [words.slice(0, 2), words.slice(2)] : [words];
  let out = '';
  const k = back(g.local / 4) * 0.12 + 0.88;
  lines.forEach((ln, li) => {
    const str = ln.map((w) => w.t).join(' ');
    const size = Math.min(118, Math.floor(980 / (str.length * 0.62)));
    const spans = ln.map((w, j) => `<tspan fill="${(w.i % 2) ? '#ffd23f' : '#ffffff'}">${esc(w.t)}${j < ln.length - 1 ? ' ' : ''}</tspan>`).join('');
    out += `<text x="540" y="${(sc.caption_y || 1180) + li * 120}" font-family="Nunito" font-weight="900" font-size="${size}" text-anchor="middle" stroke="#111" stroke-width="20" stroke-linejoin="round" paint-order="stroke">${spans}</text>`;
  });
  return `<g transform="translate(540 1180) scale(${k}) translate(-540 -1180)">${out}</g>`;
}

function ctaSVG(frame) {
  const c = TL.ep.cta;
  if (!c || frame < TL.cta_start_frame) return '';
  const local = frame - TL.cta_start_frame;
  let out = `<rect width="${W}" height="${H}" fill="#0b0e1a" opacity="${Math.min(0.6, local / 10)}"/>`;
  out += `<g transform="translate(540 760) scale(${back(local / 9)})">` +
    (c.question_lines || []).map((l, i) => PU.text(l, 0, i * 120, 110, i ? '#ffd23f' : '#fff', { font: 'Nunito', weight: 900, stroke: 18, strokeColor: '#111' })).join('') + `</g>`;
  c.options.forEach((o, i) => {
    const kk = back((local - 6 - i * 4) / 8), x = i ? 790 : 290;
    out += `<g transform="translate(${x} 1120) scale(${kk})"><rect x="-230" y="-80" width="460" height="160" rx="30" fill="${o.color}" stroke="#111" stroke-width="10"/>` +
      PU.text(o.label.toUpperCase(), 0, 24, 66, '#fff', { font: 'Nunito', weight: 900, stroke: 10, strokeColor: '#111' }) + `</g>`;
  });
  if (local > 14) out += PU.text(c.prompt || 'COMMENT WHAT HE SHOULD DO', 540, 1330, 48, '#fff', { font: 'Nunito', weight: 900, stroke: 10, strokeColor: '#111' });
  return out;
}

window.loadTimeline = async (tl) => {
  TL = tl;
  const stage = document.getElementById('stage');
  const canvas = document.createElement('canvas'); stage.appendChild(canvas);
  const svgHost = document.createElement('div'); svgHost.id = 'overlay'; svgHost.style.position = 'absolute'; svgHost.style.left = '0'; svgHost.style.top = '0'; stage.appendChild(svgHost);
  renderer = new THREE.WebGLRenderer({ canvas, antialias: true, preserveDrawingBuffer: true });
  renderer.setPixelRatio(1); renderer.setSize(W, H, false);
  renderer.shadowMap.enabled = true; renderer.shadowMap.type = THREE.PCFSoftShadowMap;
  renderer.outputColorSpace = THREE.SRGBColorSpace;
  camera = new THREE.PerspectiveCamera(45, W / H, 0.1, 400);
  await document.fonts.ready;
  buildWorld(tl.ep);
};

window.renderFrame = (frame) => {
  const t = frame / TL.fps;
  const sc = sceneAt(TL, frame);
  const local = frame - sc.start_frame, dur = Math.max(1, sc.end_frame - sc.start_frame);
  const k = ease(local / dur);
  applyTime(sc.time || TL.ep.time || 'day', sc.lamps || 'off', t);
  if (sc.lamps_on_at !== undefined && local / TL.fps >= sc.lamps_on_at) applyTime(sc.time || 'dusk', 'on', t);
  for (const [id, av] of Object.entries(actors)) {
    const a = (sc.actors || {})[id];
    av.visible = !!a;
    if (!a) continue;
    const p0 = a.pos || [0, 0, 0], p1 = a.to || p0;
    const kk = a.to ? clamp(local / (dur * (a.walk_frac || 1))) : 0;
    av.position.x = lerp(p0[0], p1[0], kk); av.position.z = lerp(p0[2], p1[2], kk);
    av.rotation.y = (a.face || 0) * Math.PI / 180;
    const talk = sc.speaker === id ? (sc.mouth[local] || 0) : 0;
    const blink = ((frame + id.length * 17) % 90) < 3 ? 1 : 0;
    poseAvatar(av, Object.assign({}, a, { walk: a.walk && kk < 1 }), t, talk, blink);
  }
  const sh = sc.shot || {};
  const c0 = sh.cam || [20, 10, 20], c1 = sh.cam_to || c0, l0 = sh.look || [0, 2, 0], l1 = sh.look_to || l0;
  camera.fov = sh.fov || 45; camera.updateProjectionMatrix();
  camera.position.set(lerp(c0[0], c1[0], k), lerp(c0[1], c1[1], k), lerp(c0[2], c1[2], k));
  camera.lookAt(lerp(l0[0], l1[0], k), lerp(l0[1], l1[1], k), lerp(l0[2], l1[2], k));
  if (sh.follow && actors[sh.follow.id]) {
    const p = actors[sh.follow.id].position, o = sh.follow.offset || [0, 2, 8], lo = sh.follow.look_offset || [0, 3, 0];
    camera.position.set(p.x + o[0], o[1], p.z + o[2]);
    camera.lookAt(p.x + lo[0], lo[1], p.z + lo[2]);
  }
  if (sc.shake) { camera.position.x += Math.sin(frame * 2.7) * 0.08; camera.position.y += Math.cos(frame * 3.3) * 0.08; }
  const snow = scene.userData.snow, arr = snow.geometry.attributes.position.array, base = snow.userData.base;
  for (let i = 0; i < arr.length; i += 3) { arr[i + 1] = (base[i + 1] - t * 3 + 400) % 40; arr[i] = base[i] + Math.sin(t + i) * 0.3; }
  snow.geometry.attributes.position.needsUpdate = true;
  renderer.render(scene, camera);
  let svg = '';
  if (sc.flash && local < 6) svg += `<rect width="${W}" height="${H}" fill="#fff" opacity="${(6 - local) / 7}"/>`;
  svg += captionSVG(sc, frame) + ctaSVG(frame);
  if (frame < 8) svg += `<rect width="${W}" height="${H}" fill="#000" opacity="${1 - frame / 8}"/>`;
  document.getElementById('overlay').innerHTML = `<svg xmlns="http://www.w3.org/2000/svg" width="${W}" height="${H}" viewBox="0 0 ${W} ${H}">${svg}</svg>`;
};
