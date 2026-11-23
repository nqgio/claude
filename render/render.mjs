// Usage: node render/render.mjs <timeline.json> <out.mp4> [--frames a-b] [--still N out.png]
// Renders every frame in headless Chromium and pipes JPEGs into ffmpeg (silent video).
import { createRequire } from 'node:module';
const { chromium } = createRequire(import.meta.url)('playwright');
import { spawn } from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

const here = path.dirname(fileURLToPath(import.meta.url));
const [tlPath, outPath] = process.argv.slice(2);
const stillIdx = process.argv.indexOf('--still');
const tl = JSON.parse(fs.readFileSync(tlPath, 'utf8'));

const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: tl.width, height: tl.height } });
await page.goto(pathToFileURL(path.join(here, 'player.html')).href);
await page.evaluate(() => document.fonts.ready);
await page.evaluate((t) => window.loadTimeline(t), tl);

if (stillIdx > 0) {
  const n = +process.argv[stillIdx + 1];
  await page.evaluate((f) => window.renderFrame(f), n);
  await page.evaluate(() => document.fonts.ready);
  await page.screenshot({ path: process.argv[stillIdx + 2] });
  await browser.close();
  process.exit(0);
}

const ff = spawn('ffmpeg', ['-y', '-loglevel', 'error', '-f', 'image2pipe', '-framerate', String(tl.fps), '-c:v', 'mjpeg', '-i', '-',
  '-c:v', 'libx264', '-preset', 'medium', '-crf', '20', '-pix_fmt', 'yuv420p', outPath], { stdio: ['pipe', 'inherit', 'inherit'] });

const t0 = Date.now();
for (let f = 0; f < tl.total_frames; f++) {
  await page.evaluate((i) => window.renderFrame(i), f);
  const buf = await page.screenshot({ type: 'jpeg', quality: 92 });
  if (!ff.stdin.write(buf)) await new Promise((r) => ff.stdin.once('drain', r));
  if (f % 150 === 0) process.stderr.write(`frame ${f}/${tl.total_frames} (${((Date.now() - t0) / 1000).toFixed(0)}s)\n`);
}
ff.stdin.end();
await new Promise((r) => ff.on('close', r));
await browser.close();
console.log(`rendered ${tl.total_frames} frames -> ${outPath}`);
