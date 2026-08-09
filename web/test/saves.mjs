// The things a browser player has that a terminal player does not: one copy of
// their progress inside one origin's localStorage, a browser that may refuse to
// store it at all, a phone with no keyboard, and a URL that can carry options.
//
//   CHROME=/usr/bin/chromium PORT=8156 node web/test/saves.mjs

import { spawn } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import puppeteer from 'puppeteer-core';

const WEB    = path.dirname(path.dirname(fileURLToPath(import.meta.url)));
const PORT   = Number(process.env.PORT || 8156);
const CHROME = process.env.CHROME || '/usr/bin/chromium';
const sleep  = (ms) => new Promise((r) => setTimeout(r, ms));

const SCREEN = `(() => {
  const b = window.vimny.term.buffer.active;
  const rows = [];
  for (let i = 0; i < b.length; i++) rows.push(b.getLine(i).translateToString(true));
  return rows.join('\\n');
})()`;

// A save tree of the shape boot.py posts out: absolute paths under ~/.Vimny.
const FAKE_SAVE = {
  '/home/pyodide/.Vimny/saves/tester.json': JSON.stringify({
    player_name: 'Tester',
    progress: { first_cave: { stars: 2, spent: 11 } },
    extras: [], scrolls_seen: [], flags: {}, max_hp: 6, collected_hearts: [],
  }),
};

let failures = 0;
const check = (name, ok, detail = '') => {
  console.log(`${ok ? '  ok  ' : ' FAIL '} ${name}${ok || !detail ? '' : ` — ${detail}`}`);
  if (!ok) failures++;
};

async function booted(page, wanted = ':enew') {
  await page.waitForFunction('window.vimny !== undefined', { timeout: 30000 });
  const deadline = Date.now() + 90000;
  while (Date.now() < deadline) {
    if ((await page.evaluate(SCREEN)).includes(wanted)) return true;
    await sleep(500);
  }
  return false;
}

const notice = (page) =>
  page.evaluate(`document.getElementById('notice').hidden ? '' :
                 document.getElementById('notice-text').textContent`);

const server = spawn('python3', [path.join(WEB, 'serve.py'), String(PORT)], { stdio: 'ignore' });
await sleep(800);

const downloads = fs.mkdtempSync(path.join(os.tmpdir(), 'vimny-dl-'));
let browser;
try {
  browser = await puppeteer.launch({
    executablePath: CHROME, headless: true,
    args: ['--no-sandbox', '--disable-dev-shm-usage'],
  });

  // ── Storage the browser refuses ─────────────────────────────────────────
  // Private browsing and a full quota both throw from setItem. That used to go
  // to console.warn, which is to say nowhere: you could play for an hour and
  // find out at the end.
  {
    const page = await browser.newPage();
    await page.setViewport({ width: 1200, height: 800 });
    await page.evaluateOnNewDocument(`
      Storage.prototype.setItem = function () { throw new DOMException('denied'); };`);
    await page.goto(`http://localhost:${PORT}/`, { waitUntil: 'domcontentloaded' });
    await page.waitForFunction('window.vimny !== undefined', { timeout: 30000 });
    await sleep(500);
    const text = await notice(page);
    check('a browser that will not store says so', /not store your progress/.test(text),
          `notice was ${JSON.stringify(text)}`);
    await page.close();
  }

  // ── Export ──────────────────────────────────────────────────────────────
  {
    const page = await browser.newPage();
    await page.setViewport({ width: 1200, height: 800 });
    await page.evaluateOnNewDocument(
      `localStorage.setItem('vimny:saves', ${JSON.stringify(JSON.stringify(FAKE_SAVE))});`);
    await page.goto(`http://localhost:${PORT}/`, { waitUntil: 'domcontentloaded' });
    await page.waitForFunction('window.vimny !== undefined', { timeout: 30000 });

    const client = await page.createCDPSession();
    await client.send('Browser.setDownloadBehavior',
                      { behavior: 'allow', downloadPath: downloads });
    await page.click('#export-save');
    let file = null;
    for (let i = 0; i < 40 && !file; i++) {
      file = fs.readdirSync(downloads).find((f) => f.endsWith('.json')) || null;
      if (!file) await sleep(100);
    }
    check('export writes a save file', Boolean(file), 'nothing downloaded');
    if (file) {
      const written = JSON.parse(fs.readFileSync(path.join(downloads, file), 'utf8'));
      check('and it is the save tree, unchanged',
            JSON.stringify(written) === JSON.stringify(FAKE_SAVE));
      check('named for the day it was taken', /^vimny-save-\d{4}-\d{2}-\d{2}\.json$/.test(file),
            file);
    }
    await page.close();
  }

  // ── Import ──────────────────────────────────────────────────────────────
  // Including the file that is not a save: it has to be refused before it
  // reaches the Pyodide filesystem, where it would surface as a traceback.
  {
    const page = await browser.newPage();
    await page.setViewport({ width: 1200, height: 800 });
    await page.goto(`http://localhost:${PORT}/`, { waitUntil: 'domcontentloaded' });
    await page.waitForFunction('window.vimny !== undefined', { timeout: 30000 });
    await page.evaluate('localStorage.clear()');    // the export block left one behind
    page.on('dialog', (d) => d.accept());

    const drop = async (name, text) => {
      await page.evaluate(`(() => {
        const dt = new DataTransfer();
        dt.items.add(new File([${JSON.stringify(text)}], ${JSON.stringify(name)},
                              { type: 'application/json' }));
        const input = document.getElementById('import-file');
        input.files = dt.files;
        input.dispatchEvent(new Event('change', { bubbles: true }));
      })()`);
      await sleep(600);
    };

    await drop('holiday.json', '{"not":"a save"}');
    check('a JSON file that is not a save is refused',
          /not a Vimny save/.test(await notice(page)));
    await drop('holiday.jpg', 'not json at all');
    check('and so is a file that is not JSON',
          /not a Vimny save/.test(await notice(page)));
    check('neither one touched what is stored',
          await page.evaluate(`localStorage.getItem('vimny:saves')`) === null);

    // The real thing reloads the page, which is how the save tree reaches the
    // Pyodide filesystem — the worker restores it at boot.
    await Promise.all([
      page.waitForNavigation({ waitUntil: 'domcontentloaded', timeout: 30000 }),
      drop('vimny-save-2026-08-09.json', JSON.stringify(FAKE_SAVE)),
    ]);
    check('a real save is stored and the page reloads',
          await page.evaluate(`localStorage.getItem('vimny:saves')`) ===
          JSON.stringify(FAKE_SAVE));
    await page.close();
  }

  // ── ?level= ─────────────────────────────────────────────────────────────
  {
    const page = await browser.newPage();
    await page.setViewport({ width: 1200, height: 800 });
    await page.goto(`http://localhost:${PORT}/?level=first_cave`,
                    { waitUntil: 'domcontentloaded' });
    await page.waitForFunction('window.vimny !== undefined', { timeout: 30000 });
    await page.evaluate('localStorage.clear()');   // the import block left one behind
    // Straight past the title screen to the wizard's poem for that level, then
    // into the level itself — whose hint bar names what it teaches.
    const poem = await booted(page, 'press any key');
    check('?level=<slug> skips the title screen', poem, 'no level poem appeared');
    if (poem) {
      await page.keyboard.press('Space');
      check('and lands in that level',
            await booted(page, 'h:left'), 'the first cave never drew');

      // A ?level= link never asks who is playing, so it plays as the default
      // Normand with empty progress. If that wrote anything back, handing
      // someone a preview link would overwrite whatever they had.
      check('and says nothing will be saved',
            /Nothing you do here is saved/.test(await notice(page)),
            `notice was ${JSON.stringify(await notice(page))}`);
      await page.keyboard.type(':w');
      await page.keyboard.press('Enter');
      await sleep(1500);
      check('and a preview really does not write',
            await page.evaluate(`localStorage.getItem('vimny:saves')`) === null,
            'a preview wrote to storage');
    }
    await page.close();
  }
  {
    const page = await browser.newPage();
    await page.setViewport({ width: 1200, height: 800 });
    await page.goto(`http://localhost:${PORT}/?level=the_moon`,
                    { waitUntil: 'domcontentloaded' });
    const arrived = await booted(page);           // falls back to the title
    check('an unknown slug falls back to the title screen', arrived);
    check('and says why', /No level is called/.test(await notice(page)),
          `notice was ${JSON.stringify(await notice(page))}`);
    await page.close();
  }

  // ── No keyboard ─────────────────────────────────────────────────────────
  // Said before 9 MB of WebAssembly is fetched over a phone connection.
  {
    const page = await browser.newPage();
    await page.emulate({
      viewport: { width: 390, height: 844, isMobile: true, hasTouch: true,
                  deviceScaleFactor: 3, isLandscape: false },
      userAgent: 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) ' +
                 'AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148',
    });
    await page.goto(`http://localhost:${PORT}/`, { waitUntil: 'domcontentloaded' });
    await sleep(500);
    check('a touch device is told it needs a keyboard',
          await page.evaluate(`!document.getElementById('no-keyboard').hidden`));
    check('and nothing has booted yet',
          await page.evaluate('window.vimny === undefined'));
    await page.click('#play-anyway');
    check('but it can be loaded anyway',
          await page.evaluate(`document.getElementById('no-keyboard').hidden`));
    await page.close();
  }
} catch (err) {
  console.log(` FAIL  ${err.stack || err.message}`);
  failures++;
} finally {
  if (browser) await browser.close();
  server.kill();
  fs.rmSync(downloads, { recursive: true, force: true });
}

console.log(failures ? `\n${failures} failing` : '\nall checks passed');
process.exit(failures ? 1 : 0);
