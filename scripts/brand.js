// Renders profile pictures (1024x1024) and YouTube banners (2560x1440) for every channel.
// Usage: node scripts/brand.js   -> assets/brand/<channel>/{avatar.png,banner.png}
const { chromium } = require('playwright');
const fs = require('fs'), path = require('path');
const ROOT = path.resolve(__dirname, '..');
const { characterSVG } = require(path.join(ROOT, 'render/character.js'));
const theoBible = require(path.join(ROOT, 'channels/theo/bible.json'));
const b64 = (f) => fs.readFileSync(path.join(ROOT, f)).toString('base64');
const fontCSS = `@font-face{font-family:Anton;src:url(data:font/woff2;base64,${b64('assets/fonts/anton.woff2')})}
@font-face{font-family:Nunito;font-weight:900;src:url(data:font/woff2;base64,${b64('assets/fonts/nunito-900.woff2')})}body{margin:0}`;
const T = (t, x, y, s, fill, o = {}) => `<text x="${x}" y="${y}" font-family="${o.font || 'Anton'}" font-weight="${o.w || 400}" font-size="${s}" text-anchor="${o.a || 'middle'}" fill="${fill}" ${o.sw ? `stroke="${o.sc || '#111'}" stroke-width="${o.sw}" paint-order="stroke" stroke-linejoin="round"` : ''} letter-spacing="${o.ls || 0}">${t}</text>`;
const heart = (x, y, px, c) => ['01100110', '11111111', '11111111', '11111111', '01111110', '00111100', '00011000'].map((r, j) => [...r].map((ch, i) => ch === '1' ? `<rect x="${x + i * px}" y="${y + j * px}" width="${px}" height="${px}" fill="${c}"/>` : '').join('')).join('');

// ---------- 2D marks (drawn in a 1024 box) ----------
const theoFace = () => `<g transform="translate(-28 -20) scale(1.35)">${characterSVG(theoBible.cast.theo.start_state, { expression: 'shocked' })}</g>`;
const MARKS = {
  theo: {
    fit: 0.72, cy: 745,
    avatar: () => `<rect width="1024" height="1024" fill="#1d2140"/><circle cx="512" cy="512" r="490" fill="#7ed6c4"/><clipPath id="c"><circle cx="512" cy="512" r="490"/></clipPath><g clip-path="url(#c)">${theoFace()}</g>` +
      `<g transform="translate(760 740)"><circle r="120" fill="#ff6fb5" stroke="#111" stroke-width="14"/>${T('100', 0, 22, 92, '#fff', { sw: 10 })}${T('DAYS', 0, 70, 34, '#fff', { font: 'Nunito', w: 900 })}</g>`,
    bannerBg: () => `<rect width="2560" height="1440" fill="#1d2140"/>${[...Array(30)].map((_, i) => `<circle cx="${(i * 397) % 2560}" cy="${(i * 211) % 1440}" r="${10 + (i % 4) * 6}" fill="#7ed6c4" opacity="0.15"/>`).join('')}`,
    banner: () => ``+
      `<g transform="translate(560 470) scale(0.48)">${characterSVG(theoBible.cast.theo.start_state, { expression: 'shocked' })}</g>` +
      T('THEO HAS', 1380, 660, 190, '#fff', { sw: 18 }) + T('100 DAYS', 1380, 850, 200, '#ff6fb5', { sw: 18 }) +
      T('YOU decide what he fixes. Top comment wins.', 1440, 930, 40, '#ffd23f', { font: 'Nunito', w: 900 }) + heart(1890, 515, 14, '#ff6fb5'),
  },
  pickwrong: {
    fit: 0.72, cy: 735,
    avatar: () => `<rect width="1024" height="1024" fill="#14101c"/><circle cx="512" cy="430" r="330" fill="#a6ff3d" opacity="0.07"/>` +
      `<g transform="translate(512 640)"><path d="M -120 -40 Q -160 -400 0 -410 Q 160 -400 120 -40 Z" fill="#2a2f36" stroke="#000" stroke-width="10"/><circle cx="0" cy="-230" r="100" fill="#0a0f0b"/><circle cx="-36" cy="-236" r="16" fill="#fff8c0"/><circle cx="36" cy="-236" r="16" fill="#fff8c0"/></g>` +
      `<g transform="translate(300 830) rotate(-4)"><rect x="-170" y="-70" width="340" height="140" rx="70" fill="#2f6fe0" stroke="#000" stroke-width="10"/>${T('A', 0, 38, 110, '#fff', { sw: 10 })}</g>` +
      `<g transform="translate(724 830) rotate(4)"><rect x="-170" y="-70" width="340" height="140" rx="70" fill="#e8384f" stroke="#000" stroke-width="10"/>${T('B', 0, 38, 110, '#fff', { sw: 10 })}</g>`,
    bannerBg: () => `<rect width="2560" height="1440" fill="#14101c"/><rect width="2560" height="1440" fill="url(#v)"/>`,
    banner: () => ``+
      `<g transform="translate(700 980)"><path d="M -90 -30 Q -120 -300 0 -310 Q 120 -300 90 -30 Z" fill="#2a2f36"/><circle cx="0" cy="-175" r="75" fill="#0a0f0b"/><circle cx="-27" cy="-180" r="12" fill="#fff8c0"/><circle cx="27" cy="-180" r="12" fill="#fff8c0"/></g>` +
      T('PICK', 1350, 700, 230, '#f2eee6', { sw: 16 }) + T('WRONG', 1350, 920, 230, '#a6ff3d', { sw: 16 }) +
      T('4-part horror stories. You choose. Choose carefully.', 1350, 1000, 48, '#cfc9da', { font: 'Nunito', w: 900 }),
  },
  modeltown: {
    fit: 0.8, cy: 740,
    avatar: () => `<rect width="1024" height="1024" fill="#1b2140"/>${[...Array(13)].map((_, i) => `<rect x="${i * 80}" width="40" height="1024" fill="#232a52"/>`).join('')}` +
      `<rect x="212" y="800" width="600" height="110" rx="10" fill="#5b3a26" stroke="#111" stroke-width="8"/><rect x="212" y="800" width="600" height="16" fill="#e6b53c"/>` +
      `<path d="M 232 805 L 232 520 Q 232 200 512 200 Q 792 200 792 520 L 792 805" fill="#cfe8ff" fill-opacity="0.1" stroke="#e8f4ff" stroke-opacity="0.7" stroke-width="10"/>` +
      `<ellipse cx="512" cy="795" rx="270" ry="28" fill="#eef3f7"/>` +
      `<rect x="330" y="560" width="70" height="230" fill="#d9c9a3" stroke="#111" stroke-width="5"/><path d="M 320 560 L 365 490 L 410 560 Z" fill="#7a5c3a" stroke="#111" stroke-width="5"/><circle cx="365" cy="610" r="24" fill="#fff" stroke="#111" stroke-width="5"/>` +
      `<rect x="440" y="620" width="230" height="170" fill="#6b2d5c" stroke="#111" stroke-width="5"/><path d="M 425 620 L 555 540 L 685 620 Z" fill="#8e3b7a" stroke="#111" stroke-width="5"/>` +
      [0, 1, 2].map((r) => [0, 1, 2, 3, 4].map((c) => `<rect x="${458 + c * 42}" y="${645 + r * 44}" width="28" height="26" fill="#ffe9a0" stroke="#111" stroke-width="3"/>`).join('')).join('') +
      `<path d="M 290 300 L 290 520 Q 292 340 420 270" stroke="#fff" stroke-opacity="0.35" stroke-width="22" fill="none" stroke-linecap="round"/>` +
      `<g transform="translate(720 70) rotate(18)"><rect x="-70" y="-400" width="140" height="300" fill="#1f2a44"/><rect x="-74" y="-110" width="148" height="40" fill="#f4f4f4"/><path d="M -60 -70 Q -70 30 -40 70 L 50 70 Q 70 10 60 -70 Z" fill="#f0c29a" stroke="#111" stroke-width="6"/><rect x="20" y="60" width="28" height="140" rx="14" fill="#f0c29a" stroke="#111" stroke-width="6"/></g>`,
    bannerBg: () => `<rect width="2560" height="1440" fill="#1b2140"/>${[...Array(32)].map((_, i) => `<rect x="${i * 80}" width="40" height="1440" fill="#232a52"/>`).join('')}`,
    banner: () => ``+
      T('THE MODEL TOWN', 1280, 720, 210, '#e6b53c', { sw: 0 }) +
      T('How the systems around you are built to steer you, one rule a day.', 1280, 820, 52, '#fff', { font: 'Nunito', w: 900 }),
  },
  lastexit: {
    fit: 0.8, cy: 665,
    avatar: () => `<rect width="1024" height="1024" fill="#070910"/><rect width="1024" height="1024" fill="url(#n)"/>` +
      `<path d="M 512 600 L 0 1024 L 1024 1024 Z" fill="#191b22"/>${[0, 1, 2].map((i) => `<rect x="${505 - i * 6}" y="${700 + i * 100}" width="${14 + i * 12}" height="${40 + i * 30}" fill="#e8e2c4" opacity="0.7"/>`).join('')}` +
      `<rect x="150" y="190" width="724" height="400" rx="34" fill="#126b3a" stroke="#f4f4f4" stroke-width="16"/>` +
      `<rect x="640" y="150" width="190" height="70" rx="10" fill="#126b3a" stroke="#f4f4f4" stroke-width="10"/>${T('EXIT', 735, 205, 52, '#fff')}` +
      T('LAST', 440, 370, 150, '#fff') + T('EXIT', 440, 530, 150, '#fff') +
      `<path d="M 680 470 L 780 330 L 800 400 L 860 360 L 820 500 Z" fill="#fff" transform="rotate(10 760 420)"/>` +
      `<rect x="160" y="590" width="20" height="440" fill="#666"/><rect x="844" y="590" width="20" height="440" fill="#666"/>`,
    bannerBg: () => `<rect width="2560" height="1440" fill="#070910"/><rect width="2560" height="1440" fill="url(#n)"/>`,
    banner: () => ``+
      `<rect x="700" y="430" width="1160" height="460" rx="40" fill="#126b3a" stroke="#f4f4f4" stroke-width="18"/>` +
      T('LAST EXIT', 1280, 720, 220, '#fff') + T('Your call. Every day.', 1280, 830, 60, '#ffd23f', { font: 'Nunito', w: 900 }) +
      `<rect x="2100" y="900" width="60" height="30" fill="#ff3040"/><rect x="380" y="900" width="60" height="30" fill="#ff3040"/>`,
  },
};

(async () => {
  const b = await chromium.launch({ args: ['--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--allow-file-access-from-files'] });
  const p = await b.newPage();
  const defs = `<defs><radialGradient id="v" cx="50%" cy="50%" r="70%"><stop offset="50%" stop-color="#000" stop-opacity="0"/><stop offset="100%" stop-color="#000" stop-opacity="0.8"/></radialGradient>
    <linearGradient id="n" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stop-color="#05070f"/><stop offset="100%" stop-color="#1c2340"/></linearGradient></defs>`;
  for (const [name, m] of Object.entries(MARKS)) {
    const dir = path.join(ROOT, 'assets/brand', name); fs.mkdirSync(dir, { recursive: true });
    for (const [kind, w, h] of [['avatar', 1024, 1024], ['banner', 2560, 1440]]) {
      await p.setViewportSize({ width: w, height: h });
      // banners: foreground is fitted into YouTube's always-visible safe area (1546x423, centered)
      const body = kind === 'banner' ? m.bannerBg() + `<g transform="translate(1280 720) scale(${m.fit || 0.7}) translate(-1280 ${-(m.cy || 720)})">${m.banner()}</g>` : m[kind]();
      await p.setContent(`<html><head><style>${fontCSS}</style></head><body><div style="font-family:Anton;position:absolute;opacity:0">a</div><div style="font-family:Nunito;font-weight:900;position:absolute;opacity:0">a</div><svg width="${w}" height="${h}" viewBox="0 0 ${w} ${h}">${defs}${body}</svg></body></html>`);
      await p.evaluate(() => document.fonts.ready);
      await p.waitForTimeout(200);
      await p.screenshot({ path: path.join(dir, `${kind}.png`) });
    }
    console.log('ok', name);
  }
  await b.close();
})();
