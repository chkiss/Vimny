// Diagnostic: boot the page, then report what the terminal and the game each
// think the geometry is. Not part of the smoke test — a tool for when the
// screen looks wrong.
//
//   PORT=8130 node web/test/probe.mjs

import { spawn } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import path from 'node:path';
import puppeteer from 'puppeteer-core';

const WEB = path.dirname(path.dirname(fileURLToPath(import.meta.url)));
const PORT = Number(process.env.PORT || 8130);
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

const server = spawn('python3', [path.join(WEB, 'serve.py'), String(PORT)],
                     { stdio: ['ignore', 'pipe', 'ignore'] });
await sleep(800);

const browser = await puppeteer.launch({
  executablePath: process.env.CHROME || '/usr/bin/chromium',
  headless: true,
  args: ['--no-sandbox', '--disable-dev-shm-usage'],
});
const page = await browser.newPage();
await page.setViewport({ width: 1400, height: 900 });
await page.goto(`http://localhost:${PORT}/`, { waitUntil: 'domcontentloaded' });
await page.waitForFunction('window.vimny !== undefined', { timeout: 30000 });
await sleep(12000);

const report = await page.evaluate(`(() => {
  const t = window.vimny.term;
  const b = t.buffer.active;
  const lines = [];
  for (let i = 0; i < Math.min(b.length, 12); i++) {
    const raw = b.getLine(i).translateToString(false);   // keep trailing blanks
    lines.push({ i, len: raw.replace(/\\s+$/, '').length, wrapped: b.getLine(i).isWrapped,
                 head: raw.slice(0, 12), tail: raw.replace(/\\s+$/, '').slice(-6) });
  }
  return { cols: t.cols, rows: t.rows, lines };
})()`);

const frame = await page.evaluate('window.vimny.lastFrame || ""');
console.log(`last frame from Python: ${frame.length} bytes, ` +
            `${(frame.match(/\n/g) || []).length + 1} lines, ` +
            `VIMNY present: ${frame.includes('VIMNY')}`);
console.log('  first 3 printable lines:');
for (const line of frame.split('\n').filter((l) => l.replace(/\x1b\[[0-9;?]*[A-Za-z]/g, '').trim()).slice(0, 3)) {
  console.log('   ', JSON.stringify(line.slice(0, 120)));
}

console.log(`xterm: ${report.cols} cols x ${report.rows} rows`);
console.log('row  len  wrapped  head            tail');
for (const l of report.lines) {
  console.log(`${String(l.i).padStart(3)}  ${String(l.len).padStart(3)}  ` +
              `${l.wrapped ? 'WRAP   ' : '       '}  ${JSON.stringify(l.head).padEnd(16)}  ${JSON.stringify(l.tail)}`);
}

await browser.close();
server.kill();
