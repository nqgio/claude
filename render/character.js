// Code-drawn cartoon character. Every visual trait is driven by a `state` object,
// so a "glow up" is just a state change (e.g. { unibrow: false }).
// Local coordinate space: 800 x 1100, head centered around (400, 400).

const INK = '#2a1d14';
const SW = 9; // outline stroke width

const DEFAULT_STATE = {
  name: 'Theo',
  skin: '#f1c08f',
  hair: 'greasy_mess',      // greasy_mess | buzz | fade | styled | curly_top
  hair_color: '#3b2a1e',
  unibrow: true,
  brows: 'bushy',           // bushy | groomed
  acne: 3,                  // 0..3
  eye_bags: true,
  glasses: 'taped',         // taped | none | stylish
  nose_hair: true,
  facial_hair: 'patchy',    // patchy | none | mustache_fuzz | goatee
  teeth: 'yellow',          // yellow | white | braces
  body: 'chubby',           // chubby | average | fit
  outfit: 'stained_hoodie', // stained_hoodie | tshirt | jacket | gym | suit
  outfit_color: null,       // optional hex override
  smelly: true,             // stink lines
  posture: 'slouch',        // slouch | straight
  accessories: [],          // e.g. ["chain", "watch", "headphones"]
};

function mergeState(s) { return Object.assign({}, DEFAULT_STATE, s || {}); }

function shade(hex, amt) {
  const n = parseInt(hex.slice(1), 16);
  let r = (n >> 16) + amt, g = ((n >> 8) & 255) + amt, b = (n & 255) + amt;
  r = Math.max(0, Math.min(255, r)); g = Math.max(0, Math.min(255, g)); b = Math.max(0, Math.min(255, b));
  return '#' + ((r << 16) | (g << 8) | b).toString(16).padStart(6, '0');
}

// ---------- body ----------
function torsoPath(body) {
  if (body === 'fit') return 'M 115 1100 L 130 770 Q 140 690 250 680 L 550 680 Q 660 690 670 770 L 685 1100 Z';
  if (body === 'average') return 'M 150 1100 L 160 770 Q 170 695 270 685 L 530 685 Q 630 695 640 770 L 650 1100 Z';
  return 'M 95 1100 Q 80 900 140 770 Q 175 695 280 688 L 520 688 Q 625 695 660 770 Q 720 900 705 1100 Z'; // chubby
}

const OUTFIT_COLORS = { stained_hoodie: '#7d8b69', tshirt: '#3d7bd9', jacket: '#2f3b52', gym: '#e04848', suit: '#23262e',
  lab_coat: '#fbfbfb', hoodie: '#2b2d33', apron: '#2b2b2b', tracksuit: '#1f7a4d', chef: '#ffffff', cardigan: '#c9708a', uniform: '#2c4a8a' };

function drawOutfit(s, pose) {
  const c = s.outfit_color || OUTFIT_COLORS[s.outfit] || '#777';
  const d = torsoPath(s.body);
  let out = '';
  if (s.outfit === 'gym') {
    // skin torso, tank top on top
    out += `<path d="${d}" fill="${s.skin}" stroke="${INK}" stroke-width="${SW}"/>`;
    const w = s.body === 'fit' ? 0 : 20;
    out += `<path d="M ${235 - w} 1100 L ${245 - w} 760 Q 300 690 330 690 Q 400 790 470 690 Q 500 690 ${555 + w} 760 L ${565 + w} 1100 Z" fill="${c}" stroke="${INK}" stroke-width="${SW}"/>`;
    if (s.body === 'fit') out += `<path d="M 330 860 Q 400 885 470 860 M 400 870 L 400 990" stroke="${shade(c, -50)}" stroke-width="6" fill="none" stroke-linecap="round"/>`;
    return out;
  }
  out += `<path d="${d}" fill="${c}" stroke="${INK}" stroke-width="${SW}" stroke-linejoin="round"/>`;
  if (s.outfit === 'stained_hoodie') {
    out += `<path d="M 275 690 Q 400 800 525 690 Q 470 740 400 745 Q 330 740 275 690 Z" fill="${shade(c, -35)}" stroke="${INK}" stroke-width="6"/>`;
    out += `<path d="M 365 745 L 355 860 M 435 745 L 445 860" stroke="#eee" stroke-width="7" stroke-linecap="round"/>`;
    out += `<circle cx="355" cy="866" r="8" fill="#ddd" stroke="${INK}" stroke-width="4"/><circle cx="445" cy="866" r="8" fill="#ddd" stroke="${INK}" stroke-width="4"/>`;
    out += `<path d="M 270 980 Q 400 1010 530 980 L 530 1100 L 270 1100 Z" fill="${shade(c, -20)}" stroke="${INK}" stroke-width="6"/>`;
    for (const [x, y, rx, ry] of [[230, 860, 34, 22], [520, 820, 26, 18], [470, 940, 20, 14], [300, 930, 14, 10], [585, 905, 18, 26]])
      out += `<ellipse cx="${x}" cy="${y}" rx="${rx}" ry="${ry}" fill="#6b5326" opacity="0.55"/>`;
    for (const [x, y] of [[330, 800], [480, 780], [260, 900], [560, 860], [410, 900]])
      out += `<rect x="${x}" y="${y}" width="9" height="7" rx="2" fill="#d9a441" stroke="${INK}" stroke-width="2" transform="rotate(${x % 40} ${x} ${y})"/>`;
  } else if (s.outfit === 'hoodie') {
    out += `<path d="M 275 690 Q 400 800 525 690 Q 470 740 400 745 Q 330 740 275 690 Z" fill="${shade(c, -18)}" stroke="${INK}" stroke-width="6"/>`;
    out += `<path d="M 368 745 L 362 850 M 432 745 L 438 850" stroke="#ddd" stroke-width="6" stroke-linecap="round"/>`;
    out += `<path d="M 270 980 Q 400 1010 530 980 L 530 1100 L 270 1100 Z" fill="${shade(c, -12)}" stroke="${INK}" stroke-width="6"/>`;
  } else if (s.outfit === 'tshirt') {
    out += `<path d="M 300 688 Q 400 760 500 688" fill="none" stroke="${INK}" stroke-width="${SW}"/>`;
  } else if (s.outfit === 'jacket') {
    out += `<path d="M 300 688 L 400 860 L 500 688 Z" fill="#f4f4f4" stroke="${INK}" stroke-width="6"/>`;
    out += `<path d="M 285 690 L 400 880 L 330 1100 M 515 690 L 400 880 L 470 1100" fill="none" stroke="${INK}" stroke-width="7"/>`;
    out += `<path d="M 285 690 L 250 760 L 330 800 Z M 515 690 L 550 760 L 470 800 Z" fill="${shade(c, 25)}" stroke="${INK}" stroke-width="6"/>`;
  } else if (s.outfit === 'suit') {
    out += `<path d="M 305 688 L 400 900 L 495 688 Z" fill="#fff" stroke="${INK}" stroke-width="6"/>`;
    out += `<path d="M 385 720 L 415 720 L 425 870 L 400 900 L 375 870 Z" fill="#c0392b" stroke="${INK}" stroke-width="5"/>`;
    out += `<path d="M 290 690 L 255 790 L 345 830 L 400 920 M 510 690 L 545 790 L 455 830 L 400 920" fill="none" stroke="${INK}" stroke-width="7"/>`;
  } else if (s.outfit === 'lab_coat') {
    out += `<path d="M 300 688 L 400 800 L 500 688 Z" fill="#7fb7e6" stroke="${INK}" stroke-width="6"/>`;
    out += `<path d="M 290 690 L 360 880 L 360 1100 M 510 690 L 440 880 L 440 1100" fill="none" stroke="${INK}" stroke-width="7"/>`;
    out += `<path d="M 330 760 Q 300 880 360 900 Q 420 905 430 860" stroke="#333" stroke-width="8" fill="none"/><circle cx="430" cy="852" r="16" fill="#aab" stroke="${INK}" stroke-width="5"/>`;
    out += `<rect x="470" y="880" width="70" height="60" rx="6" fill="#eee" stroke="${INK}" stroke-width="5"/><path d="M 490 880 L 490 860 M 515 880 L 515 865" stroke="#2b6cd4" stroke-width="7"/>`;
  } else if (s.outfit === 'apron') {
    out += `<path d="M 300 688 Q 400 760 500 688" fill="none" stroke="${INK}" stroke-width="${SW}"/>`;
    out += `<path d="M 290 820 L 510 820 L 540 1100 L 260 1100 Z" fill="#c0392b" stroke="${INK}" stroke-width="7"/>`;
    out += `<path d="M 330 820 L 300 700 M 470 820 L 500 700" stroke="#c0392b" stroke-width="16"/>`;
    out += `<path d="M 370 900 l 25 60 M 395 900 l -25 60" stroke="#ddd" stroke-width="7" stroke-linecap="round"/><circle cx="365" cy="968" r="10" fill="none" stroke="#ddd" stroke-width="5"/><circle cx="400" cy="968" r="10" fill="none" stroke="#ddd" stroke-width="5"/>`;
  } else if (s.outfit === 'tracksuit') {
    out += `<path d="M 400 700 L 400 1100" stroke="#ddd" stroke-width="6"/><path d="M 290 690 Q 400 740 510 690" fill="none" stroke="#fff" stroke-width="10"/>`;
    out += `<path d="M 160 800 L 140 1100 M 640 800 L 660 1100" stroke="#fff" stroke-width="10"/>`;
    out += `<path d="M 340 700 Q 360 800 330 840" stroke="#ddd" stroke-width="4" fill="none"/><rect x="315" y="840" width="30" height="20" rx="6" fill="#bbb" stroke="${INK}" stroke-width="4"/>`;
  } else if (s.outfit === 'chef') {
    out += `<path d="M 300 688 L 400 760 L 500 688" fill="none" stroke="${INK}" stroke-width="7"/>`;
    for (const y of [790, 860, 930]) out += `<circle cx="370" cy="${y}" r="9" fill="#333"/><circle cx="430" cy="${y}" r="9" fill="#333"/>`;
  } else if (s.outfit === 'cardigan') {
    out += `<path d="M 300 688 Q 400 770 500 688 L 470 1100 L 330 1100 Z" fill="#f3e6c8" stroke="${INK}" stroke-width="6"/>`;
    for (const y of [800, 880, 960]) out += `<circle cx="490" cy="${y}" r="9" fill="#f3d36b" stroke="${INK}" stroke-width="3"/>`;
  } else if (s.outfit === 'uniform') {
    out += `<path d="M 300 688 L 400 790 L 500 688" fill="none" stroke="${INK}" stroke-width="7"/><path d="M 460 780 l 30 0 l 0 34 l -15 10 l -15 -10 Z" fill="#f2c230" stroke="${INK}" stroke-width="4"/>`;
  }
  return out;
}

function drawArms(s, pose) {
  const sleeve = s.outfit === 'gym' ? s.skin : (s.outfit_color || OUTFIT_COLORS[s.outfit] || '#777');
  const fit = s.body === 'fit';
  if (pose === 'flex') {
    const bic = fit ? 70 : 40;
    const arm = (m) => {
      const X = (x) => (m < 0 ? 800 - x : x);
      return `<path d="M ${X(195)} 760 Q ${X(60)} 760 ${X(70)} 640 Q ${X(70 - bic * 0.3)} ${600 - bic} ${X(125)} 520 L ${X(190)} 545 Q ${X(150)} 610 ${X(160)} 650 Q ${X(170)} 690 ${X(235)} 700 Z" fill="${sleeve}" stroke="${INK}" stroke-width="${SW}" stroke-linejoin="round"/>` +
        `<circle cx="${X(155)}" cy="510" r="48" fill="${s.skin}" stroke="${INK}" stroke-width="${SW}"/>` +
        `<path d="M ${X(130)} 495 Q ${X(150)} 485 ${X(170)} 495" stroke="${INK}" stroke-width="5" fill="none"/>`;
    };
    return arm(1) + arm(-1);
  }
  if (pose === 'wave') {
    return `<path d="M 190 760 Q 120 900 135 1100 L 225 1100 Q 220 900 250 790 Z" fill="${sleeve}" stroke="${INK}" stroke-width="${SW}"/>` +
      `<path d="M 610 760 Q 720 700 700 560 L 640 560 Q 640 660 570 720 Z" fill="${sleeve}" stroke="${INK}" stroke-width="${SW}"/>` +
      `<ellipse cx="672" cy="520" rx="46" ry="54" fill="${s.skin}" stroke="${INK}" stroke-width="${SW}"/>`;
  }
  // idle / slouch: arms hang at sides
  const w = s.body === 'chubby' ? 18 : 0;
  return `<path d="M ${175 - w} 760 Q ${110 - w} 900 ${120 - w} 1100 L ${215 - w} 1100 Q ${210 - w} 920 ${245 - w} 800 Z" fill="${sleeve}" stroke="${INK}" stroke-width="${SW}" stroke-linejoin="round"/>` +
    `<path d="M ${625 + w} 760 Q ${690 + w} 900 ${680 + w} 1100 L ${585 + w} 1100 Q ${590 + w} 920 ${555 + w} 800 Z" fill="${sleeve}" stroke="${INK}" stroke-width="${SW}" stroke-linejoin="round"/>`;
}

// ---------- head ----------
function facePath(body) {
  const j = body === 'chubby' ? 28 : body === 'fit' ? -8 : 8;
  return `M 228 385 C 228 235 300 180 400 180 C 500 180 572 235 572 385 C ${572 + j} 520 ${505 + j} 618 400 622 C ${295 - j} 618 ${228 - j} 520 228 385 Z`;
}

function drawHairBack(s) {
  if (s.hair === 'greasy_mess') return `<path d="M 215 420 Q 190 250 290 185 Q 400 120 520 180 Q 610 240 585 420 L 560 330 L 240 330 Z" fill="${s.hair_color}" stroke="${INK}" stroke-width="${SW}"/>`;
  if (s.hair === 'long') return `<path d="M 215 330 Q 200 200 300 175 Q 400 140 500 175 Q 600 200 585 330 L 600 650 L 520 600 L 560 380 L 240 380 L 280 600 L 200 650 Z" fill="${s.hair_color}" stroke="${INK}" stroke-width="${SW}" stroke-linejoin="round"/>`;
  return '';
}

function drawHairFront(s) {
  const c = s.hair_color;
  switch (s.hair) {
    case 'greasy_mess':
      return `<path d="M 228 300 Q 220 200 330 170 Q 420 140 500 175 Q 590 215 572 300 Q 545 235 505 262 Q 490 215 445 255 Q 425 205 380 258 Q 350 210 320 268 Q 290 222 260 285 Z" fill="${c}" stroke="${INK}" stroke-width="${SW}" stroke-linejoin="round"/>` +
        `<path d="M 330 262 Q 322 278 326 290 M 455 255 Q 466 272 458 284" stroke="${c}" stroke-width="10" fill="none" stroke-linecap="round"/>` +
        `<path d="M 300 205 Q 360 180 420 185 M 470 195 Q 520 205 545 235" stroke="#9fae6a" stroke-width="7" fill="none" stroke-linecap="round" opacity="0.7"/>`;
    case 'buzz':
      return `<path d="M 232 330 Q 235 190 400 182 Q 565 190 568 330 Q 520 250 400 248 Q 280 250 232 330 Z" fill="${c}" opacity="0.85" stroke="${INK}" stroke-width="6"/>`;
    case 'fade':
      return `<path d="M 233 345 Q 228 300 242 270 L 262 285 Q 252 315 256 345 Z M 567 345 Q 572 300 558 270 L 538 285 Q 548 315 544 345 Z" fill="${c}" opacity="0.35"/>` +
        `<path d="M 240 280 Q 230 175 400 160 Q 570 175 560 280 Q 520 245 400 245 Q 280 245 240 280 Z" fill="${c}" stroke="${INK}" stroke-width="${SW}" stroke-linejoin="round"/>` +
        `<path d="M 300 205 Q 380 180 470 195" stroke="${shade(c, 50)}" stroke-width="6" fill="none" stroke-linecap="round"/>`;
    case 'styled':
      return `<path d="M 236 300 Q 225 180 360 150 Q 470 115 560 190 Q 600 230 565 300 Q 540 255 470 250 Q 430 270 380 255 Q 300 245 236 300 Z" fill="${c}" stroke="${INK}" stroke-width="${SW}" stroke-linejoin="round"/>` +
        `<path d="M 330 175 Q 430 140 520 185 M 360 205 Q 440 180 510 215" stroke="${shade(c, 55)}" stroke-width="7" fill="none" stroke-linecap="round"/>`;
    case 'bun':
      return `<path d="M 236 330 Q 225 190 400 178 Q 575 190 564 330 Q 540 250 400 240 Q 260 250 236 330 Z" fill="${c}" stroke="${INK}" stroke-width="${SW}"/>` +
        `<circle cx="400" cy="150" r="58" fill="${c}" stroke="${INK}" stroke-width="${SW}"/>`;
    case 'long':
      return `<path d="M 232 330 Q 225 185 400 175 Q 575 185 568 330 Q 520 240 400 236 Q 280 240 232 330 Z" fill="${c}" stroke="${INK}" stroke-width="${SW}"/>`;
    case 'beanie':
      return `<path d="M 226 330 Q 215 150 400 140 Q 585 150 574 330 Z" fill="${c}" stroke="${INK}" stroke-width="${SW}" stroke-linejoin="round"/>` +
        `<rect x="215" y="295" width="370" height="58" rx="22" fill="${shade(c, -25)}" stroke="${INK}" stroke-width="${SW}"/>` +
        [0, 1, 2, 3, 4, 5].map((i) => `<path d="M ${262 + i * 55} 303 L ${262 + i * 55} 345" stroke="${shade(c, -50)}" stroke-width="5"/>`).join('');
    case 'cap':
      return `<path d="M 232 320 Q 225 170 400 165 Q 575 170 568 320 Z" fill="${c}" stroke="${INK}" stroke-width="${SW}"/>` +
        `<path d="M 380 300 Q 520 285 640 330 Q 600 350 380 335 Z" fill="${shade(c, -30)}" stroke="${INK}" stroke-width="${SW}"/>`;
    case 'bald':
      return `<path d="M 300 210 Q 360 190 420 195" stroke="#fff" stroke-width="10" fill="none" opacity="0.5" stroke-linecap="round"/>`;
    case 'chef_hat':
      return `<path d="M 260 290 L 540 290 L 540 230 Q 600 150 520 120 Q 480 60 400 90 Q 320 60 280 120 Q 200 150 260 230 Z" fill="#fff" stroke="${INK}" stroke-width="${SW}"/>`;
    case 'curly_top': {
      let p = '';
      for (const [x, y, r] of [[270, 270, 48], [330, 215, 55], [400, 195, 58], [470, 215, 55], [530, 270, 48], [300, 300, 30], [500, 300, 30]])
        p += `<circle cx="${x}" cy="${y}" r="${r}" fill="${c}" stroke="${INK}" stroke-width="${SW}"/>`;
      return p;
    }
  }
  return '';
}

function drawBrows(s, ex) {
  // per-expression offsets: [innerY, outerY]
  const B = -14; // global brow lift
  const E = { neutral: [0, 0], happy: [-14, -8], sad: [-18, 10], shocked: [-30, -22], determined: [16, -10], smug: [0, 0], angry: [22, -12] }[ex] || [0, 0];
  const thick = s.brows === 'groomed' && !s.unibrow ? 11 : 22;
  const c = s.hair_color;
  if (s.unibrow) {
    return `<path d="M 285 ${318 + B + E[1]} Q 330 ${296 + B + E[0]} 372 ${312 + B + E[0]} Q 400 ${322 + B + E[0]} 428 ${312 + B + E[0]} Q 470 ${296 + B + E[0]} 515 ${318 + B + E[1]}" stroke="${c}" stroke-width="${thick + 4}" fill="none" stroke-linecap="round"/>` +
      `<path d="M 375 ${312 + B + E[0]} L 372 ${300 + B + E[0]} M 400 ${318 + B + E[0]} L 400 ${304 + B + E[0]} M 425 ${312 + B + E[0]} L 428 ${300 + B + E[0]}" stroke="${c}" stroke-width="5" stroke-linecap="round"/>`;
  }
  const rb = ex === 'smug' ? -16 : 0;
  return `<path d="M 290 ${320 + B + E[1]} Q 325 ${300 + B + E[0]} 370 ${315 + B + E[0]}" stroke="${c}" stroke-width="${thick}" fill="none" stroke-linecap="round"/>` +
    `<path d="M 510 ${320 + B + E[1] + rb} Q 475 ${300 + B + E[0] + rb} 430 ${315 + B + E[0] + rb}" stroke="${c}" stroke-width="${thick}" fill="none" stroke-linecap="round"/>`;
}

function drawEyes(s, ex, blink) {
  const open = Math.max(0.08, 1 - blink);
  let ry = 36 * open, pr = 15;
  if (ex === 'shocked') { ry = 44 * open; pr = 9; }
  if (ex === 'smug' || ex === 'determined') ry = Math.min(ry, 22);
  if (ex === 'happy' && blink < 0.5) ry = 30;
  let out = '';
  for (const x of [330, 470]) {
    out += `<ellipse cx="${x}" cy="375" rx="36" ry="${ry}" fill="#fff" stroke="${INK}" stroke-width="7"/>`;
    if (open > 0.3) {
      out += `<circle cx="${x + (ex === 'smug' ? 8 : 0)}" cy="${378 + (ex === 'sad' ? 6 : 0)}" r="${Math.min(pr, ry - 4)}" fill="${INK}"/>`;
      out += `<circle cx="${x + 5}" cy="370" r="4" fill="#fff"/>`;
    }
    if (ex === 'smug' || ex === 'determined') out += `<path d="M ${x - 40} ${375 - ry} L ${x + 40} ${375 - ry}" stroke="${INK}" stroke-width="7" stroke-linecap="round"/>`;
  }
  if (s.eye_bags) out += `<path d="M 300 418 Q 330 432 360 418 M 440 418 Q 470 432 500 418" stroke="#8e6aa8" stroke-width="6" fill="none" stroke-linecap="round" opacity="0.8"/>`;
  return out;
}

function drawGlasses(s) {
  if (s.glasses === 'taped') {
    return `<rect x="270" y="320" width="120" height="105" rx="14" fill="#cfe8ff" fill-opacity="0.18" stroke="${INK}" stroke-width="12"/>` +
      `<rect x="410" y="320" width="120" height="105" rx="14" fill="#cfe8ff" fill-opacity="0.18" stroke="${INK}" stroke-width="12"/>` +
      `<path d="M 390 360 L 410 360" stroke="${INK}" stroke-width="12"/>` +
      `<rect x="383" y="342" width="34" height="34" rx="4" fill="#f5f0e1" stroke="${INK}" stroke-width="4" transform="rotate(8 400 359)"/>` +
      `<path d="M 270 350 L 232 340 M 530 350 L 568 340" stroke="${INK}" stroke-width="10"/>` +
      `<path d="M 290 335 L 315 360" stroke="#fff" stroke-width="6" opacity="0.7" stroke-linecap="round"/>`;
  }
  if (s.glasses === 'stylish') {
    return `<rect x="280" y="335" width="105" height="80" rx="34" fill="none" stroke="#111" stroke-width="9"/>` +
      `<rect x="415" y="335" width="105" height="80" rx="34" fill="none" stroke="#111" stroke-width="9"/>` +
      `<path d="M 385 365 Q 400 352 415 365" stroke="#111" stroke-width="8" fill="none"/>`;
  }
  if (s.glasses === 'shades') {
    return `<path d="M 268 340 L 392 340 Q 392 410 330 412 Q 272 410 268 340 Z" fill="#111" stroke="${INK}" stroke-width="7"/>` +
      `<path d="M 408 340 L 532 340 Q 528 410 470 412 Q 408 410 408 340 Z" fill="#111" stroke="${INK}" stroke-width="7"/>` +
      `<path d="M 392 350 L 408 350 M 268 345 L 232 335 M 532 345 L 568 335" stroke="${INK}" stroke-width="8"/>` +
      `<path d="M 290 355 L 320 385" stroke="#fff" stroke-width="6" opacity="0.5" stroke-linecap="round"/>`;
  }
  return '';
}

function drawNose(s) {
  let out = `<path d="M 388 400 Q 372 455 392 462 Q 400 466 412 460" stroke="${INK}" stroke-width="7" fill="none" stroke-linecap="round"/>`;
  out += `<ellipse cx="400" cy="446" rx="30" ry="22" fill="${shade(s.skin, -18)}" opacity="0.5"/>`;
  if (s.nose_hair) out += `<path d="M 385 462 L 378 478 M 392 465 L 391 482 M 410 464 L 414 480 M 417 461 L 425 475" stroke="${INK}" stroke-width="4" stroke-linecap="round"/>`;
  return out;
}

function teethFill(s) { return s.teeth === 'yellow' ? '#e9d36b' : '#ffffff'; }

function drawMouth(s, ex, talk) {
  const t = Math.max(0, Math.min(1, talk));
  const tf = teethFill(s);
  const braces = s.teeth === 'braces' ? `<path d="M 352 522 L 448 522" stroke="#9aa3ad" stroke-width="5"/>` +
    [362, 384, 406, 428].map((x) => `<rect x="${x}" y="517" width="10" height="10" fill="#c5ccd4" stroke="${INK}" stroke-width="2"/>`).join('') : '';
  const yellowSpots = s.teeth === 'yellow' ? `<circle cx="372" cy="522" r="3" fill="#b89a2e"/><circle cx="420" cy="524" r="3" fill="#b89a2e"/>` : '';

  if (ex === 'shocked') {
    const h = 34 + t * 18;
    return `<ellipse cx="400" cy="540" rx="34" ry="${h}" fill="#5a1f1f" stroke="${INK}" stroke-width="7"/>` +
      `<path d="M 375 ${540 - h + 10} Q 400 ${540 - h + 2} 425 ${540 - h + 10} L 425 ${540 - h + 20} L 375 ${540 - h + 20} Z" fill="${tf}"/>`;
  }
  if (t > 0.12) {
    // talking: open mouth whose base shape follows the expression
    const h = 18 + t * 42;
    const curve = ex === 'sad' ? -10 : ex === 'happy' ? 14 : 6;
    return `<path d="M 345 515 Q 400 ${510 - curve} 455 515 Q 448 ${515 + h} 400 ${520 + h} Q 352 ${515 + h} 345 515 Z" fill="#5a1f1f" stroke="${INK}" stroke-width="7" stroke-linejoin="round"/>` +
      `<path d="M 352 517 Q 400 ${513 - curve} 448 517 L 446 532 Q 400 ${528 - curve} 354 532 Z" fill="${tf}"/>` + braces + yellowSpots +
      `<ellipse cx="400" cy="${514 + h}" rx="22" ry="${Math.min(10, h / 4)}" fill="#c9575a"/>`;
  }
  switch (ex) {
    case 'happy':
      return `<path d="M 340 508 Q 400 590 460 508 Z" fill="#5a1f1f" stroke="${INK}" stroke-width="7" stroke-linejoin="round"/>` +
        `<path d="M 348 512 Q 400 520 452 512 L 448 528 Q 400 536 352 528 Z" fill="${tf}"/>` + braces + yellowSpots;
    case 'sad':
      return `<path d="M 355 545 Q 400 510 445 545" stroke="${INK}" stroke-width="8" fill="none" stroke-linecap="round"/>`;
    case 'determined':
      return `<path d="M 360 528 L 440 524" stroke="${INK}" stroke-width="8" stroke-linecap="round"/>`;
    case 'smug':
      return `<path d="M 360 530 Q 410 540 448 512" stroke="${INK}" stroke-width="8" fill="none" stroke-linecap="round"/>`;
    case 'angry':
      return `<path d="M 345 520 L 455 520 L 450 545 L 350 545 Z" fill="${tf}" stroke="${INK}" stroke-width="7"/><path d="M 372 520 L 372 545 M 400 520 L 400 545 M 428 520 L 428 545" stroke="${INK}" stroke-width="3"/>`;
    default:
      return `<path d="M 360 525 Q 400 540 440 525" stroke="${INK}" stroke-width="8" fill="none" stroke-linecap="round"/>`;
  }
}

const ACNE = [[300, 455], [520, 460], [360, 262], [440, 252], [285, 488], [515, 492], [412, 432], [380, 578],
  [322, 505], [482, 506], [400, 285], [428, 572], [268, 420], [535, 425], [470, 240], [335, 240]];
function drawAcne(s) {
  const n = [0, 4, 9, 16][Math.max(0, Math.min(3, s.acne | 0))];
  let out = '';
  for (let i = 0; i < n; i++) {
    const [x, y] = ACNE[i];
    const r = 7 + (i % 3) * 2;
    out += `<circle cx="${x}" cy="${y}" r="${r + 4}" fill="#e07a6a" opacity="0.45"/><circle cx="${x}" cy="${y}" r="${r}" fill="#d9483b"/>`;
    if (s.acne >= 3 && i % 3 === 0) out += `<circle cx="${x}" cy="${y}" r="3.5" fill="#fff7d6"/>`;
  }
  return out;
}

function drawFacialHair(s) {
  const c = s.hair_color;
  if (s.facial_hair === 'patchy') {
    let out = '';
    const pts = [[290, 545], [305, 565], [320, 583], [470, 580], [490, 562], [505, 540], [395, 600], [410, 604], [380, 596], [300, 520], [500, 515], [372, 488], [430, 490]];
    for (const [x, y] of pts) out += `<circle cx="${x}" cy="${y}" r="3.5" fill="${c}" opacity="0.8"/><circle cx="${x + 8}" cy="${y + 5}" r="3" fill="${c}" opacity="0.7"/>`;
    return out;
  }
  if (s.facial_hair === 'mustache_fuzz') return `<path d="M 355 492 Q 400 480 445 492" stroke="${c}" stroke-width="8" fill="none" opacity="0.6" stroke-dasharray="3 5" stroke-linecap="round"/>`;
  if (s.facial_hair === 'goatee') return `<path d="M 370 575 Q 400 620 430 575 Q 400 590 370 575 Z" fill="${c}" stroke="${INK}" stroke-width="4"/><path d="M 360 495 Q 400 482 440 495" stroke="${c}" stroke-width="10" fill="none" stroke-linecap="round"/>`;
  return '';
}

function drawCheeks(ex) {
  if (ex !== 'happy' && ex !== 'smug') return '';
  return `<ellipse cx="290" cy="470" rx="28" ry="15" fill="#ff8a8a" opacity="0.5"/><ellipse cx="510" cy="470" rx="28" ry="15" fill="#ff8a8a" opacity="0.5"/>`;
}

function drawExtras(s, ex, t) {
  let out = '';
  if (s.smelly) {
    for (const [x, ph] of [[150, 0], [650, 1.6], [110, 3.1]]) {
      const dy = ((t * 40 + ph * 30) % 60);
      out += `<path d="M ${x} ${330 - dy} q 18 -20 0 -40 q -18 -20 0 -40 q 18 -20 0 -40" stroke="#7fae3a" stroke-width="8" fill="none" stroke-linecap="round" opacity="${0.85 - dy / 120}"/>`;
    }
  }
  if (ex === 'sad') out += `<path d="M 565 300 q 14 26 0 36 q -14 -10 0 -36 Z" fill="#7cc7ff" stroke="${INK}" stroke-width="4"/>`;
  if (ex === 'shocked') out += `<path d="M 240 250 l -30 -30 M 230 290 l -40 -10 M 560 250 l 30 -30 M 570 290 l 40 -10" stroke="${INK}" stroke-width="7" stroke-linecap="round"/>`;
  if ((s.accessories || []).includes('chain')) out += `<path d="M 300 700 Q 400 820 500 700" stroke="#f2c230" stroke-width="12" fill="none" stroke-dasharray="14 6"/>`;
  return out;
}

// Main entry. opts: { expression, talk (0..1), blink (0..1), pose, t (seconds), bob (px) }
function characterSVG(stateIn, opts = {}) {
  const s = mergeState(stateIn);
  const ex = opts.expression || 'neutral';
  const pose = opts.pose || 'idle';
  const slouch = s.posture === 'slouch' ? 1 : 0;
  const headTilt = slouch ? 4 : 0;
  const headDrop = slouch ? 22 : 0;
  const bob = opts.bob || 0;
  const head =
    drawHairBack(s) +
    `<ellipse cx="228" cy="410" rx="30" ry="44" fill="${s.skin}" stroke="${INK}" stroke-width="${SW}"/>` +
    `<ellipse cx="572" cy="410" rx="30" ry="44" fill="${s.skin}" stroke="${INK}" stroke-width="${SW}"/>` +
    `<path d="${facePath(s.body)}" fill="${s.skin}" stroke="${INK}" stroke-width="${SW}" stroke-linejoin="round"/>` +
    (s.body === 'chubby' ? `<path d="M 340 640 Q 400 668 460 640" stroke="${INK}" stroke-width="6" fill="none" stroke-linecap="round" opacity="0.7"/>` : '') +
    drawAcne(s) + drawFacialHair(s) + drawCheeks(ex) +
    drawEyes(s, ex, opts.blink || 0) + drawNose(s) + drawMouth(s, ex, opts.talk || 0) +
    drawHairFront(s) + drawGlasses(s) + drawBrows(s, ex);

  return `<g transform="translate(0 ${bob})">` +
    (pose === 'flex' ? '' : drawArms(s, pose)) +
    `<rect x="345" y="575" width="110" height="130" fill="${shade(s.skin, -15)}" stroke="${INK}" stroke-width="${SW}"/>` +
    drawOutfit(s, pose) +
    (pose === 'flex' ? drawArms(s, 'flex') : '') +
    `<g transform="translate(0 ${headDrop}) rotate(${headTilt} 400 600)">${head}</g>` +
    drawExtras(s, ex, opts.t || 0) +
    `</g>`;
}

if (typeof module !== 'undefined') module.exports = { characterSVG, DEFAULT_STATE, mergeState };
if (typeof window !== 'undefined') Object.assign(window, { characterSVG, DEFAULT_STATE, mergeState });

// ---------- cameo guests ----------
// A commenter's cartoon look is derived deterministically from their handle,
// so the same person always looks the same if they come back.
function hashStr(str) { let h = 2166136261; for (const ch of str) { h ^= ch.charCodeAt(0); h = Math.imul(h, 16777619); } return h >>> 0; }
const GUEST_SKINS = ['#f6d1b0', '#f1c08f', '#e0a979', '#c98e62', '#a86b45', '#7a4a2e', '#5c3a24'];
const GUEST_HAIR = ['buzz', 'fade', 'styled', 'curly_top', 'bun', 'long', 'bald'];
const GUEST_HAIR_COLORS = ['#1f1611', '#3b2a1e', '#6b4226', '#a0522d', '#e3b23c', '#d9d9d9', '#b5344a', '#3a5fcd'];
const GUEST_TEES = ['#e76f51', '#2a9d8f', '#8e44ad', '#f4a261', '#3d7bd9', '#e84393'];
function guestState(username, role, roleOutfits) {
  const h = hashStr((username || 'guest').toLowerCase());
  const pick = (arr, k) => arr[(h >>> k) % arr.length];
  const r = (role || '').toLowerCase();
  const outfit = (roleOutfits && roleOutfits[r]) || 'tshirt';
  const s = {
    name: username, skin: pick(GUEST_SKINS, 0), hair: pick(GUEST_HAIR, 3), hair_color: pick(GUEST_HAIR_COLORS, 6),
    unibrow: false, brows: 'groomed', acne: 0, eye_bags: false, glasses: (h >>> 9) % 4 === 0 ? 'stylish' : 'none',
    nose_hair: false, facial_hair: ['none', 'none', 'goatee', 'mustache_fuzz'][(h >>> 11) % 4], teeth: 'white',
    body: ['average', 'fit', 'chubby'][(h >>> 13) % 3], outfit, outfit_color: outfit === 'tshirt' ? pick(GUEST_TEES, 15) : null,
    smelly: false, posture: 'straight', accessories: [],
  };
  if (outfit === 'chef') s.hair = 'chef_hat';
  return s;
}
if (typeof module !== 'undefined') Object.assign(module.exports, { guestState });
if (typeof window !== 'undefined') window.guestState = guestState;
