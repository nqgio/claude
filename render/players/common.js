// Shared helpers for all channel players.
window.PU = (function () {
  const INK = '#151018';
  const esc = (s) => String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
  const clamp = (x) => Math.max(0, Math.min(1, x));
  const ease = (x) => 1 - Math.pow(1 - clamp(x), 3);
  const back = (x) => { x = clamp(x); const c = 1.7; return 1 + (c + 1) * Math.pow(x - 1, 3) + c * Math.pow(x - 1, 2); };
  const lerp = (a, b, t) => a + (b - a) * t;
  function sceneAt(TL, frame) {
    if (frame < TL.scenes[0].start_frame) return TL.scenes[0];
    return TL.scenes.find((s) => frame >= s.start_frame && frame < s.end_frame) || TL.scenes[TL.scenes.length - 1];
  }
  // Word-pop captions: shows a rolling group of up to `n` words ending at the current word.
  function wordGroup(sc, frame, n = 3) {
    const ws = sc.words || [];
    let idx = -1;
    for (let i = 0; i < ws.length; i++) if (frame >= ws[i].f0) idx = i;
    if (idx < 0 || frame > ws[ws.length - 1].f1 + 6) return null;
    // group boundaries: every n words or at punctuation
    let start = idx;
    while (start > 0 && idx - start + 1 < n && !/[.!?,]$/.test(ws[start - 1].text)) start--;
    const group = ws.slice(start, idx + 1);
    return { words: group, cur: ws[idx], local: frame - ws[idx].f0 };
  }
  function text(t, x, y, size, fill, o = {}) {
    const sw = o.stroke === undefined ? Math.round(size * 0.14) : o.stroke;
    return `<text x="${x}" y="${y}" font-family="${o.font || 'Anton'}" font-weight="${o.weight || 400}" font-size="${size}" text-anchor="${o.anchor || 'middle'}" fill="${fill}" ${sw ? `stroke="${o.strokeColor || INK}" stroke-width="${sw}" stroke-linejoin="round" paint-order="stroke"` : ''} letter-spacing="${o.ls || 0}" ${o.extra || ''}>${esc(t)}</text>`;
  }
  // Approximate text width (good enough for layout of bold caps fonts).
  function width(t, size, font) {
    const k = font === 'Anton' ? 0.47 : font === 'Inter' ? 0.62 : 0.6;
    return t.length * size * k;
  }
  return { INK, esc, clamp, ease, back, lerp, sceneAt, wordGroup, text, width };
})();
