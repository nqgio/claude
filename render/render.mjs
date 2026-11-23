// Usage: node render/render.mjs <timeline.json> <out.mp4> [--frames a-b] [--still N out.png]
// Renders every frame in headless Chromium and pipes JPEGs into ffmpeg (silent video).
import { createRequire } from 'node:module';
const { chromium } = createRequire(import.meta.url)('playwright');
import { spawn } from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import http from 'node:http';

const here = path.dirname(fileURLToPath(import.meta.url));
const [tlPath, outPath] = process.argv.slice(2);
const stillIdx = process.argv.indexOf('--still');
const tl = JSON.parse(fs.readFileSync(tlPath, 'utf8'));

// tiny static server (ES modules can't load from file://)
const root = path.resolve(here, '..');
const types = { '.html': 'text/html', '.js': 'text/javascript', '.mjs': 'text/javascript', '.woff2': 'font/woff2', '.png': 'image/png', '.json': 'application/json' };
const server = http.createServer((req, res) => {
  const p = path.join(root, decodeURIComponent(new URL(req.url, 'http://x').pathname));
  if (!p.startsWith(root) || !fs.existsSync(p) || fs.statSync(p).isDirectory()) { res.writeHead(404); return res.end(); }
  res.writeHead(200, { 'Content-Type': types[path.extname(p)] || 'application/octet-stream' });
  fs.createReadStream(p).pipe(res);
});
await new Promise((r) => server.listen(0, '127.0.0.1', r));
const base = `http://127.0.0.1:${server.address().port}`;

const browser = await chromium.launch({ args: ['--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist'] });
const page = await browser.newPage({ viewport: { width: tl.width, height: tl.height } });
page.on('pageerror', (e) => process.stderr.write(`pageerror: ${e.message}\n`));
await page.goto(`${base}/render/player.html?style=${tl.style || 'theo'}`);
await page.waitForFunction(() => typeof window.renderFrame === 'function' && typeof window.loadTimeline === 'function', null, { timeout: 30000 });
await page.evaluate(() => document.fonts.ready);
await page.evaluate(async (t) => { await window.loadTimeline(t); }, tl);

if (stillIdx > 0) {
  const n = +process.argv[stillIdx + 1];
  await page.evaluate(async (f) => { await window.renderFrame(f); }, n);
  await page.evaluate(() => document.fonts.ready);
  await page.screenshot({ path: process.argv[stillIdx + 2] });
  await browser.close();
  server.close();
  process.exit(0);
}

const ff = spawn('ffmpeg', ['-y', '-loglevel', 'error', '-f', 'image2pipe', '-framerate', String(tl.fps), '-c:v', 'mjpeg', '-i', '-',
  '-c:v', 'libx264', '-preset', 'medium', '-crf', '20', '-pix_fmt', 'yuv420p', outPath], { stdio: ['pipe', 'inherit', 'inherit'] });

const t0 = Date.now();
for (let f = 0; f < tl.total_frames; f++) {
  await page.evaluate(async (i) => { await window.renderFrame(i); }, f);
  const buf = await page.screenshot({ type: 'jpeg', quality: 92 });
  if (!ff.stdin.write(buf)) await new Promise((r) => ff.stdin.once('drain', r));
  if (f % 150 === 0) process.stderr.write(`frame ${f}/${tl.total_frames} (${((Date.now() - t0) / 1000).toFixed(0)}s)\n`);
}
ff.stdin.end();
await new Promise((r) => ff.on('close', r));
await browser.close();
server.close();
console.log(`rendered ${tl.total_frames} frames -> ${outPath}`);
