// End-to-end check of the browser build: drive a headless Chromium, type at
// the game, and read the screen back out of xterm.js.
//
// Needs puppeteer-core and a Chromium on the box:
//   npm i puppeteer-core && CHROME=/usr/bin/chromium node web/test/smoke.mjs
//
// It starts its own server (serve.py), so the headers are the real ones.

import { spawn } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import path from 'node:path';
import puppeteer from 'puppeteer-core';

const WEB   = path.dirname(path.dirname(fileURLToPath(import.meta.url)));
const PORT  = Number(process.env.PORT || 8111);
const CHROME = process.env.CHROME || '/usr/bin/chromium';

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

// Everything xterm.js currently has on screen, as text.
const SCREEN = `(() => {
  const b = window.vimny.term.buffer.active;
  const rows = [];
  for (let i = 0; i < b.length; i++) rows.push(b.getLine(i).translateToString(true));
  return rows.join('\\n');
})()`;

async function waitFor(page, predicate, { timeout = 120000, label = 'condition' } = {}) {
  const deadline = Date.now() + timeout;
  while (Date.now() < deadline) {
    const screen = await page.evaluate(SCREEN);
    if (predicate(screen)) return screen;
    await sleep(500);
  }
  const screen = await page.evaluate(SCREEN);
  console.log('   last screen:\n' + screen.split('\n').filter((l) => l.trim())
                                           .map((l) => '   | ' + l).join('\n'));
  const shot = `/tmp/vimny-smoke-${label.replace(/\W+/g, '-')}.png`;
  await page.screenshot({ path: shot });
  console.log(`   screenshot: ${shot}`);
  throw new Error(`timed out waiting for ${label}`);
}

const server = spawn('python3', [path.join(WEB, 'serve.py'), String(PORT)], {
  stdio: ['ignore', 'pipe', 'inherit'],
});
await sleep(800);

let browser;
let failures = 0;
const check = (name, ok, detail = '') => {
  console.log(`${ok ? '  ok  ' : ' FAIL '} ${name}${detail && !ok ? ` — ${detail}` : ''}`);
  if (!ok) failures++;
};

try {
  browser = await puppeteer.launch({
    executablePath: CHROME,
    headless: true,
    args: ['--no-sandbox', '--disable-dev-shm-usage', '--window-size=1400,900'],
  });
  const page = await browser.newPage();
  await page.setViewport({ width: 1400, height: 900 });
  page.on('console', (m) => {
    if (m.type() === 'error' || m.text().startsWith('[vimny]')) {
      console.log('   console:', m.text());
    }
  });
  page.on('pageerror', (e) => console.log('   pageerror:', e.message));

  await page.goto(`http://localhost:${PORT}/`, { waitUntil: 'domcontentloaded' });

  check('cross-origin isolated', await page.evaluate('window.crossOriginIsolated'));

  const t0 = Date.now();
  await page.waitForFunction('window.vimny !== undefined', { timeout: 30000 });
  const title = await waitFor(page, (s) => s.includes('VIMNY') || s.includes('New game'),
                              { label: 'the title screen' });
  const bootMs = Date.now() - t0;
  check('boots to the title screen', true);
  console.log(`   boot: ${(bootMs / 1000).toFixed(1)}s`);

  // Start a new game: the menu opens on `:e saves/`, so step down to `:enew`,
  // then type a name at the prompt.
  await page.keyboard.type('j');          // the menu is vim-keyed: j/k, not arrows
  await sleep(300);
  await page.keyboard.press('Enter');
  await waitFor(page, (s) => /Name your adventurer/i.test(s),
                { label: 'the name prompt', timeout: 20000 });
  for (const ch of 'Tester') { await page.keyboard.type(ch); await sleep(60); }
  await page.keyboard.press('Enter');

  const overworld = await waitFor(page, (s) => s.includes('OVERWORLD') || s.includes('dungeon_00'),
                                  { label: 'the overworld' });
  check('reaches the overworld', overworld.includes('dungeon_00'));

  // The overworld opens on a netrw root — saves/, scrolls/, world/ — and the
  // dungeons live in world/. Walk down to it and open it.
  await page.keyboard.type('jj');
  await sleep(400);

  // From here to the level there are a couple of screens that just want a key:
  // the dungeon listing, then the wizard's blessing ("press any key"). Rather
  // than encode that sequence — which is content, and will change — press
  // Enter until the level is on screen.
  let level = '';
  for (let attempt = 0; attempt < 8 && !level; attempt++) {
    await page.keyboard.press('Enter');
    await sleep(1500);
    const screen = await page.evaluate(SCREEN);
    if (screen.includes('The First Cave') && screen.includes('Budget')) level = screen;
  }
  check('enters The First Cave', Boolean(level), 'never reached the level');
  if (!level) throw new Error('could not reach The First Cave');
  check('draws the hint bar', /:q\s*quit/.test(level));

  // Move, and prove the cursor actually moved: the status line reports 1,1
  // until it doesn't.
  const before = await page.evaluate(SCREEN);
  for (const key of ['l', 'l', 'l', 'j']) { await page.keyboard.type(key); await sleep(120); }
  const after = await page.evaluate(SCREEN);
  check('responds to hjkl', before !== after, 'screen unchanged after motion');

  const keysLine = after.split('\n').find((l) => l.includes('Keys:')) || '';
  check('counts keystrokes', /Keys:\s*[1-9]/.test(keysLine), keysLine.trim());

  // Colour: the game is truecolor throughout, so a cell should carry one.
  const coloured = await page.evaluate(`(() => {
    const b = window.vimny.term.buffer.active;
    for (let y = 0; y < b.length; y++) {
      const line = b.getLine(y);
      for (let x = 0; x < line.length; x++) {
        if (line.getCell(x)?.isFgRGB()) return true;
      }
    }
    return false;
  })()`);
  check('renders truecolor', coloured);

  await page.screenshot({ path: '/tmp/vimny-web-level.png' });

  // Saves must survive a reload — that is the IndexedDB mount doing its job.
  await page.keyboard.type(':w');
  await page.keyboard.press('Enter');
  await sleep(1500);
  await page.reload({ waitUntil: 'domcontentloaded' });
  await page.waitForFunction('window.vimny !== undefined', { timeout: 30000 });
  await waitFor(page, (s) => s.includes(':enew'), { label: 'the title screen after reload' });
  // Saves are behind `:e saves/`, the menu item the cursor already sits on.
  await page.keyboard.press('Enter');
  await sleep(1500);
  const saves = await page.evaluate(SCREEN);
  check('save survives a reload', /Tester/i.test(saves), 'no Tester in the save browser');

} catch (err) {
  console.log(` FAIL  ${err.message}`);
  failures++;
} finally {
  if (browser) await browser.close();
  server.kill();
}

console.log(failures ? `\n${failures} failing` : '\nall checks passed');
process.exit(failures ? 1 : 0);
