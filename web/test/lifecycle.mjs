// Lifecycle checks: what the browser build does at the edges a terminal has no
// equivalent for — quitting, restarting, reloading mid-game, a second tab, a
// backgrounded tab, resizing, going offline.
//
// Separate from smoke.mjs, which asks "does the game work". This asks "what
// happens when the player does something a terminal player cannot do".
//
//   CHROME=/usr/bin/chromium PORT=8152 node web/test/lifecycle.mjs

import { spawn } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import path from 'node:path';
import puppeteer from 'puppeteer-core';

const WEB    = path.dirname(path.dirname(fileURLToPath(import.meta.url)));
const PORT   = Number(process.env.PORT || 8152);
const CHROME = process.env.CHROME || '/usr/bin/chromium';
const sleep  = (ms) => new Promise((r) => setTimeout(r, ms));

const SCREEN = `(() => {
  const b = window.vimny.term.buffer.active;
  const rows = [];
  for (let i = 0; i < b.length; i++) rows.push(b.getLine(i).translateToString(true));
  return rows.join('\\n');
})()`;

let failures = 0;
const check = (name, ok, detail = '') => {
  console.log(`${ok ? '  ok  ' : ' FAIL '} ${name}${ok || !detail ? '' : ` — ${detail}`}`);
  if (!ok) failures++;
};

async function booted(page) {
  await page.waitForFunction('window.vimny !== undefined', { timeout: 30000 });
  const deadline = Date.now() + 90000;
  let last = '';
  while (Date.now() < deadline) {
    last = await page.evaluate(SCREEN);
    if (last.includes(':enew')) return;
    await sleep(500);
  }
  const rows = last.split('\n');
  console.log(`   rows=${rows.length} 'enew' present=${last.includes('enew')} ` +
              `'quit' present=${last.includes('quit')}`);
  console.log(rows.filter((l) => l.trim()).slice(-10)
                  .map((l) => '   | ' + l.slice(0, 110)).join('\n'));
  throw new Error('never reached the title screen');
}

const server = spawn('python3', [path.join(WEB, 'serve.py'), String(PORT)], { stdio: 'ignore' });
await sleep(800);

let browser;
try {
  browser = await puppeteer.launch({
    executablePath: CHROME, headless: true,
    args: ['--no-sandbox', '--disable-dev-shm-usage'],
  });
  const page = await browser.newPage();
  page.on('pageerror', (e) => console.log('   pageerror:', e.message));
  page.on('console', (m) => {
    if (m.type() === 'error' || m.text().startsWith('[vimny]')) console.log('   console:', m.text().slice(0, 200));
  });
  await page.setViewport({ width: 1200, height: 800 });
  await page.goto(`http://localhost:${PORT}/`, { waitUntil: 'domcontentloaded' });
  await booted(page);

  // ── Quit ────────────────────────────────────────────────────────────────
  await page.keyboard.type('jj');            // menu: :e saves/ → :enew → quit
  await sleep(300);
  await page.keyboard.press('Enter');
  await sleep(2500);

  const quitOverlay = await page.evaluate(`!document.getElementById('exited').hidden`);
  check('quitting says so instead of leaving a blank page', quitOverlay);

  // ── Restart ─────────────────────────────────────────────────────────────
  const t0 = Date.now();
  await page.click('#play-again');
  const deadline = Date.now() + 30000;
  let back = false;
  while (Date.now() < deadline && !back) {
    back = (await page.evaluate(SCREEN)).includes(':enew');
    if (!back) await sleep(300);
  }
  check('play again returns to the title screen', back);
  if (back) console.log(`   restart: ${((Date.now() - t0) / 1000).toFixed(1)}s ` +
                        `(vs ~6s for a fresh Pyodide boot)`);
  check('restart hides the quit overlay',
        await page.evaluate(`document.getElementById('exited').hidden`));

  // ── Reload mid-game ─────────────────────────────────────────────────────
  await page.reload({ waitUntil: 'domcontentloaded' });
  await booted(page);
  check('reload mid-game comes back up', true);

  // ── A second tab ────────────────────────────────────────────────────────
  const tab2 = await browser.newPage();
  await tab2.setViewport({ width: 1200, height: 800 });
  await tab2.goto(`http://localhost:${PORT}/`, { waitUntil: 'domcontentloaded' });
  await booted(tab2);
  check('a second tab boots independently', true);
  await tab2.close();

  // ── Backgrounded tab ────────────────────────────────────────────────────
  // Browsers throttle timers in hidden tabs. The worker blocks on Atomics.wait
  // rather than a timer, but the page's 16 ms input flush IS a timer — so a key
  // pressed while hidden might not be handed over until the tab is visible.
  const tab3 = await browser.newPage();
  await tab3.goto(`http://localhost:${PORT}/`, { waitUntil: 'domcontentloaded' });  // steals focus
  await sleep(3000);
  const beforeHidden = await page.evaluate(SCREEN);
  await page.evaluate(`window.vimny.term.textarea.dispatchEvent(
      new KeyboardEvent('keydown', { key: 'j', bubbles: true }))`);
  await sleep(1500);
  const afterHidden = await page.evaluate(SCREEN);
  check('a hidden tab does not crash', typeof afterHidden === 'string' && afterHidden.length > 0);
  console.log(`   (hidden-tab keypress changed the screen: ${beforeHidden !== afterHidden})`);
  await tab3.close();
  await page.bringToFront();

  // ── Resize ──────────────────────────────────────────────────────────────
  // A laptop-shaped window: the font shrinks and the game still fits, which is
  // the whole point of fitToGame — 80x45 without the player doing anything.
  await page.setViewport({ width: 1366, height: 768 });
  await sleep(2000);
  const laptop = await page.evaluate('[window.vimny.term.cols, window.vimny.term.rows]');
  check('a 1366x768 laptop still fits the game',
        laptop[0] >= 80 && laptop[1] >= 45, `got ${laptop[0]}x${laptop[1]}`);
  check('and needs no warning',
        await page.evaluate(`document.getElementById('too-narrow').hidden`));

  // Small enough that even 8px type cannot make 80x45 — now it must say so.
  await page.setViewport({ width: 420, height: 320 });
  await sleep(2000);
  check('an impossible window warns instead of mangling the screen',
        await page.evaluate(`!document.getElementById('too-narrow').hidden`),
        'no too-small warning');
  console.log(`   (tiny viewport = ${await page.evaluate('window.vimny.term.cols')}x` +
              `${await page.evaluate('window.vimny.term.rows')})`);

  await page.setViewport({ width: 1400, height: 900 });
  await sleep(2500);
  check('widening clears the warning',
        await page.evaluate(`document.getElementById('too-narrow').hidden`));
  const wide = await page.evaluate(SCREEN);
  check('the game redraws at the new width', wide.split('\n').some((l) => l.includes('│')),
        'no frame after resize');

  // ── Offline ─────────────────────────────────────────────────────────────
  // The game computes in the tab and saves in the browser, so needing a server
  // to start was the odd part. Kill the network and it should still boot — not
  // because the HTTP cache happens to have held on to 9 MB, but because sw.js
  // put it somewhere deliberate.
  await page.evaluate('navigator.serviceWorker.ready');
  await sleep(3000);                       // let the shell precache settle
  check('a service worker is controlling the page',
        await page.evaluate('navigator.serviceWorker.controller !== null'));

  await page.setOfflineMode(true);
  const reloaded = await page.reload({ waitUntil: 'domcontentloaded' })
                             .then(() => true).catch(() => false);
  check('the page loads with the network down', reloaded);
  if (reloaded) {
    // booted() throws if it never arrives, so reaching the next line IS the pass.
    await booted(page);
    check('and the game boots offline, all 9 MB of it', true);
  }
  await page.setOfflineMode(false);
} catch (err) {
  console.log(` FAIL  ${err.message}`);
  failures++;
} finally {
  if (browser) await browser.close();
  server.kill();
}

console.log(failures ? `\n${failures} failing` : '\nall checks passed');
process.exit(failures ? 1 : 0);
