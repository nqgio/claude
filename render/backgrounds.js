// Code-drawn backgrounds for a 1080x1920 vertical frame.
const BINK = '#2a1d14';

function floorWall(wall, floor, horizon = 1350) {
  return `<rect width="1080" height="1920" fill="${wall}"/>` +
    `<rect y="${horizon}" width="1080" height="${1920 - horizon}" fill="${floor}"/>` +
    `<path d="M 0 ${horizon} L 1080 ${horizon}" stroke="${BINK}" stroke-width="8"/>`;
}

const BACKGROUNDS = {
  basement(t) {
    const flicker = 0.75 + 0.25 * Math.sin(t * 9) * Math.sin(t * 2.3);
    return floorWall('#4a4a6a', '#5b4636') +
      // concrete wall blocks
      [...Array(9)].map((_, r) => [...Array(5)].map((_, c) => `<rect x="${(r % 2) * -110 + c * 220 + 10}" y="${560 + r * 88}" width="210" height="80" fill="#525276" opacity="0.6"/>`).join('')).join('') +
      // tiny high window
      `<rect x="760" y="600" width="220" height="110" fill="#9fd3ff" stroke="${BINK}" stroke-width="8"/><path d="M 870 600 L 870 710" stroke="${BINK}" stroke-width="6"/>` +
      `<rect x="760" y="660" width="220" height="50" fill="#6fa86a" opacity="0.8"/>` +
      // poster
      `<rect x="70" y="620" width="190" height="250" fill="#e8574a" stroke="${BINK}" stroke-width="7" transform="rotate(-4 165 745)"/>` +
      `<text x="165" y="720" font-family="Anton" font-size="54" fill="#ffe14d" text-anchor="middle" transform="rotate(-4 165 745)">GAME</text><text x="165" y="790" font-family="Anton" font-size="54" fill="#fff" text-anchor="middle" transform="rotate(-4 165 745)">ON</text>` +
      // desk + glowing monitor
      `<rect x="700" y="1080" width="360" height="30" fill="#6b4a2f" stroke="${BINK}" stroke-width="7"/>` +
      `<rect x="760" y="900" width="240" height="160" rx="10" fill="#1b1b2b" stroke="${BINK}" stroke-width="8"/>` +
      `<rect x="775" y="915" width="210" height="130" fill="#57d6ff" opacity="${flicker}"/>` +
      `<rect x="860" y="1060" width="40" height="22" fill="#333" stroke="${BINK}" stroke-width="5"/>` +
      // pizza boxes + cans on floor
      `<rect x="40" y="1430" width="250" height="40" fill="#e9c08a" stroke="${BINK}" stroke-width="6"/><rect x="60" y="1392" width="250" height="40" fill="#e9c08a" stroke="${BINK}" stroke-width="6" transform="rotate(-5 185 1412)"/>` +
      `<rect x="860" y="1440" width="34" height="56" rx="6" fill="#3fbf6a" stroke="${BINK}" stroke-width="5"/><rect x="910" y="1462" width="56" height="34" rx="6" fill="#d94a4a" stroke="${BINK}" stroke-width="5"/>` +
      // hanging bulb
      `<path d="M 540 0 L 540 470" stroke="${BINK}" stroke-width="5"/><circle cx="540" cy="495" r="30" fill="#ffe680" stroke="${BINK}" stroke-width="6"/>` +
      `<circle cx="540" cy="495" r="${80 + 6 * Math.sin(t * 3)}" fill="#ffe680" opacity="0.18"/>`;
  },

  bathroom() {
    let tiles = '';
    for (let y = 520; y < 1350; y += 90) for (let x = 0; x < 1080; x += 90) tiles += `<rect x="${x + 3}" y="${y + 3}" width="84" height="84" fill="#bfe6e0"/>`;
    return floorWall('#9fd2ca', '#e7e2d6') + tiles +
      `<rect x="250" y="560" width="580" height="420" rx="30" fill="#dff3ff" stroke="${BINK}" stroke-width="10"/>` +
      `<path d="M 300 620 L 380 560 M 330 680 L 470 570" stroke="#fff" stroke-width="16" stroke-linecap="round" opacity="0.8"/>` +
      `<rect x="760" y="1110" width="260" height="60" rx="16" fill="#fff" stroke="${BINK}" stroke-width="8"/>` +
      `<rect x="80" y="1080" width="34" height="90" rx="8" fill="#5bb0f0" stroke="${BINK}" stroke-width="6"/><rect x="130" y="1100" width="30" height="70" rx="8" fill="#f07a8a" stroke="${BINK}" stroke-width="6"/>`;
  },

  barber() {
    return floorWall('#f4e3c3', '#2d2d2d') +
      [...Array(8)].map((_, i) => `<rect x="${i * 135}" y="1350" width="68" height="570" fill="#f4f4f4"/>`).join('') +
      `<rect x="200" y="560" width="680" height="440" rx="20" fill="#e3f4ff" stroke="${BINK}" stroke-width="10"/>` +
      `<rect x="60" y="560" width="70" height="320" rx="35" fill="#fff" stroke="${BINK}" stroke-width="8"/>` +
      [0, 1, 2, 3].map((i) => `<path d="M 60 ${600 + i * 70} L 130 ${640 + i * 70}" stroke="#d63031" stroke-width="22"/><path d="M 60 ${635 + i * 70} L 130 ${675 + i * 70}" stroke="#0984e3" stroke-width="10"/>`).join('') +
      `<text x="1000" y="700" font-family="Anton" font-size="70" fill="#d63031" text-anchor="middle" transform="rotate(90 1000 700)">BARBER</text>`;
  },

  gym() {
    return floorWall('#3a3f4b', '#6b5d4f') +
      `<rect x="0" y="560" width="1080" height="70" fill="#ff7a2f"/><text x="540" y="618" font-family="Anton" font-size="58" fill="#fff" text-anchor="middle">NO PAIN NO GAIN</text>` +
      `<rect x="60" y="1180" width="300" height="24" rx="12" fill="#888" stroke="${BINK}" stroke-width="6"/><rect x="40" y="1130" width="44" height="124" rx="10" fill="#222"/><rect x="336" y="1130" width="44" height="124" rx="10" fill="#222"/>` +
      `<rect x="800" y="760" width="220" height="520" rx="10" fill="#cfd6e0" stroke="${BINK}" stroke-width="8"/>` +
      [0, 1, 2, 3].map((i) => `<rect x="830" y="${800 + i * 110}" width="160" height="60" rx="8" fill="#556" stroke="${BINK}" stroke-width="5"/>`).join('');
  },

  kitchen() {
    return floorWall('#f7d9a8', '#c98f5a') +
      `<rect x="0" y="1080" width="1080" height="270" fill="#e8e1d4" stroke="${BINK}" stroke-width="8"/>` +
      `<rect x="0" y="1060" width="1080" height="30" fill="#8a6a50" stroke="${BINK}" stroke-width="6"/>` +
      `<rect x="80" y="560" width="300" height="300" fill="#bfe8ff" stroke="${BINK}" stroke-width="10"/><path d="M 230 560 L 230 860 M 80 710 L 380 710" stroke="${BINK}" stroke-width="8"/>` +
      `<rect x="760" y="560" width="260" height="200" fill="#f4f4f4" stroke="${BINK}" stroke-width="8"/>` +
      `<circle cx="890" cy="980" r="60" fill="#f4f4f4" stroke="${BINK}" stroke-width="8"/><path d="M 890 940 L 890 980 L 920 1000" stroke="${BINK}" stroke-width="6"/>`;
  },

  street() {
    return `<rect width="1080" height="1920" fill="#8fd3ff"/>` +
      `<circle cx="900" cy="300" r="90" fill="#ffe066" opacity="0.9"/>` +
      `<rect x="0" y="700" width="420" height="650" fill="#f2a65a" stroke="${BINK}" stroke-width="8"/><path d="M -20 700 L 210 520 L 440 700 Z" fill="#b5523b" stroke="${BINK}" stroke-width="8"/>` +
      `<rect x="160" y="1100" width="110" height="250" fill="#7a4b2a" stroke="${BINK}" stroke-width="7"/><rect x="60" y="820" width="110" height="110" fill="#ffe9a8" stroke="${BINK}" stroke-width="7"/><rect x="260" y="820" width="110" height="110" fill="#ffe9a8" stroke="${BINK}" stroke-width="7"/>` +
      `<rect x="660" y="740" width="420" height="610" fill="#9ad1a0" stroke="${BINK}" stroke-width="8"/><path d="M 640 740 L 870 560 L 1100 740 Z" fill="#4f7a8a" stroke="${BINK}" stroke-width="8"/>` +
      `<rect x="820" y="1110" width="110" height="240" fill="#4a3a6a" stroke="${BINK}" stroke-width="7"/>` +
      `<rect x="0" y="1350" width="1080" height="570" fill="#7c7c86"/><path d="M 0 1350 L 1080 1350" stroke="${BINK}" stroke-width="8"/>` +
      [0, 1, 2, 3, 4].map((i) => `<rect x="${i * 240 + 40}" y="1620" width="140" height="20" fill="#fff" opacity="0.7"/>`).join('');
  },

  doctor_office() {
    return floorWall('#e6f2f2', '#b8c4c8') +
      `<rect x="80" y="600" width="260" height="340" fill="#fff" stroke="${BINK}" stroke-width="8"/>` +
      [0, 1, 2, 3, 4].map((i) => `<text x="210" y="${670 + i * 60}" font-family="Anton" font-size="${56 - i * 9}" fill="#333" text-anchor="middle">${['E', 'F P', 'T O Z', 'L P E D', 'P E C F D'][i]}</text>`).join('') +
      `<path d="M 840 620 l 0 160 M 760 700 l 160 0" stroke="#e05050" stroke-width="44"/>` +
      `<rect x="720" y="1120" width="340" height="80" rx="12" fill="#7fb7e6" stroke="${BINK}" stroke-width="8"/>`;
  },

  studio(t) {
    let dots = '';
    for (let y = 0; y < 1920; y += 120) for (let x = (y / 120) % 2 ? 60 : 0; x < 1080; x += 120) dots += `<circle cx="${x}" cy="${y + (t * 30) % 120}" r="10" fill="#fff" opacity="0.18"/>`;
    return `<rect width="1080" height="1920" fill="#7ed6c4"/>` + dots;
  },
};

if (typeof module !== 'undefined') module.exports = { BACKGROUNDS };
if (typeof window !== 'undefined') window.BACKGROUNDS = BACKGROUNDS;
