// Vimny in the browser — the page side.
//
// Owns the terminal emulator and the keyboard, and hands keystrokes to the
// worker through shared memory. It never blocks: the worker does the waiting.

const KEY_CAPACITY = 4096;            // UTF-16 code units in flight at once
const CTRL_FLAG = 0, CTRL_LEN = 1, CTRL_DATA = 2;
const SAVE_KEY = 'vimny:saves';       // the whole ~/.Vimny tree, as JSON

// What the game needs to draw itself. 80 columns is its documented minimum;
// 45 ROWS is the title screen's — measured, not guessed: at 45 the menu
// (`:e saves/`, `:enew`, `quit`) is on screen and at 42 it is not, because the
// logo and the wizard fill the terminal and the menu falls off the bottom. A
// browser window is much shorter than a full-screen terminal — a 1366x768
// laptop is about 35 rows — so without this a first-time visitor gets a title
// screen with nothing to select.
const MIN_ROWS = 45, MIN_COLS = 80;
const MAX_FONT = 15, MIN_FONT = 8;

// Vimny's own subset of DejaVu Sans Mono, with Symbola behind it for the ~35
// runes DejaVu has no glyph for. Without these the runes and box-drawing are
// whatever the visitor happens to have installed. See web/subset_fonts.py.
const FONT_STACK = '"Vimny Mono", "Vimny Runes", "Vimny Extra", ' +
                   '"DejaVu Sans Mono", "Cascadia Mono", "Menlo", monospace';

const el = (id) => document.getElementById(id);

function fail(message, detail) {
  el('loading').hidden = true;
  el('failure').hidden = false;
  el('failure-message').textContent = message;
  el('failure-detail').textContent = detail || '';
}

// A dismissable line for things the page knows and the game cannot say: storage
// refused a save, `?level=` named nothing, an import landed.
function notice(text) {
  el('notice-text').textContent = text;
  el('notice').hidden = false;
}
el('notice-dismiss').addEventListener('click', () => { el('notice').hidden = true; });

// ── Storage ──────────────────────────────────────────────────────────────────
// Everything the player has done lives in one localStorage key, and there are
// two ordinary ways to have none: private browsing, and a full quota. Both used
// to fail into console.warn, which is to say silently — an hour of play thrown
// away without a word.

let storageBroken = false;            // said once, not once per save

function storageWorks() {
  try {
    localStorage.setItem('vimny:probe', '1');
    localStorage.removeItem('vimny:probe');
    return true;
  } catch (err) {
    return false;
  }
}

function readSaves() {
  try {
    return localStorage.getItem(SAVE_KEY) || '{}';
  } catch (err) {
    return '{}';
  }
}

function writeSaves(json) {
  try {
    localStorage.setItem(SAVE_KEY, json);
    return true;
  } catch (err) {
    console.warn('[vimny] could not save:', err);
    if (!storageBroken) {
      storageBroken = true;
      notice('This browser will not store your progress — private mode, or ' +
             'storage is full. You can still play, but nothing is being kept. ' +
             'Export save downloads what you have so far.');
    }
    return false;
  }
}

// ── Save export / import ─────────────────────────────────────────────────────
// The only copy of a browser player's progress is in this origin's
// localStorage: clearing site data ends it, and it does not follow them to
// another machine. So let them take it out and put it back — the file is the
// same {path: contents} tree the worker sends, and the same JSON the terminal
// build writes to ~/.Vimny.

function exportSave() {
  const json = readSaves();
  if (json === '{}') { notice('Nothing to export yet — no progress is stored.'); return; }
  const stamp = new Date().toISOString().slice(0, 10);
  const url = URL.createObjectURL(new Blob([json], { type: 'application/json' }));
  const a = document.createElement('a');
  a.href = url;
  a.download = `vimny-save-${stamp}.json`;
  a.click();
  URL.revokeObjectURL(url);
}

// A save file is {absolute path: file contents}. Anything else — an array, a
// nested object, a JPEG someone renamed — gets refused here rather than
// half-written into the Pyodide filesystem where it would surface as a Python
// traceback.
function validSaveTree(data) {
  if (!data || typeof data !== 'object' || Array.isArray(data)) return false;
  const paths = Object.keys(data);
  if (!paths.length) return false;
  return paths.every((p) => typeof data[p] === 'string' && p.includes('.Vimny'));
}

async function importSave(file) {
  let data;
  try {
    data = JSON.parse(await file.text());
  } catch (err) {
    notice(`That file is not a Vimny save — ${err.message}.`);
    return;
  }
  if (!validSaveTree(data)) {
    notice('That file is not a Vimny save: it should be the JSON that ' +
           '“Export save” produces.');
    return;
  }
  const names = Object.keys(data).length;
  if (!confirm(`Replace this browser's progress with ${names} file(s) from ` +
               `${file.name}?\n\nWhatever is stored here now will be lost.`)) return;
  if (!writeSaves(JSON.stringify(data))) return;
  // Reload rather than hot-swapping: the worker restores the save tree into the
  // Pyodide filesystem at boot, and while the game runs it is parked in
  // Atomics.wait and cannot be told anything.
  location.reload();
}

el('export-save').addEventListener('click', exportSave);
el('import-save').addEventListener('click', () => el('import-file').click());
el('import-file').addEventListener('change', (e) => {
  const file = e.target.files[0];
  e.target.value = '';               // so re-picking the same file fires again
  if (file) importSave(file);
});

// ── Gate ─────────────────────────────────────────────────────────────────────

if (!window.crossOriginIsolated) {
  // SharedArrayBuffer is gated on COOP/COEP. Without it the worker cannot block
  // on input, and the whole design falls over — so say so plainly rather than
  // failing later in a way that looks like a game bug.
  fail('This page is not cross-origin isolated.',
       'Vimny needs the COOP and COEP headers to use SharedArrayBuffer. ' +
       'Serve it with web/serve.py, or set those headers on your host.');
} else if (!hasKeyboard()) {
  // Say so BEFORE fetching 9 MB of WebAssembly over what is probably a phone
  // connection. A tablet with a keyboard attached reports fine pointers, so
  // this asks about the pointer rather than the screen width.
  el('loading').hidden = true;
  el('no-keyboard').hidden = false;
  el('play-anyway').addEventListener('click', () => {
    el('no-keyboard').hidden = true;
    el('loading').hidden = false;
    start();
  });
} else {
  start();
}

function hasKeyboard() {
  if (!window.matchMedia) return true;
  const coarse = matchMedia('(any-pointer: coarse)').matches;
  const fine   = matchMedia('(any-pointer: fine)').matches;
  const hover  = matchMedia('(any-hover: hover)').matches;
  return !coarse || fine || hover;
}

async function start() {
  const manifest = await (await fetch('vendor/manifest.json')).json();

  // The game's own fonts have to be measured before xterm.js sizes a cell off
  // them, or the first fit() runs against the fallback and every row is wrong.
  if (document.fonts) {
    try {
      await Promise.all([document.fonts.load('15px "Vimny Mono"'),
                         document.fonts.load('15px "Vimny Runes"')]);
    } catch (err) {
      console.warn('[vimny] bundled fonts unavailable:', err);
    }
  }

  const term = new Terminal({
    fontFamily: FONT_STACK,
    fontSize: 15,
    cursorBlink: false,
    // The game draws its own cursor as `@`; a second one blinking over the
    // status line is just noise.
    cursorStyle: 'underline',
    theme: { background: '#0c0c14', foreground: '#d0d0d8' },
    allowProposedApi: true,
    scrollback: 0,          // a TUI redraws; a scrollback would only collect junk
  });
  const fit = new FitAddon.FitAddon();
  term.loadAddon(fit);
  term.open(el('terminal'));
  fit.fit();
  // The handle the smoke test reads the screen through, and the one to reach
  // for in a console when something looks wrong.
  window.vimny = { term, fit, sent: '' };

  if (!storageWorks()) {
    notice('This browser will not store your progress — private mode, or ' +
           'storage is full. You can play, but nothing will be kept when you ' +
           'close the tab.');
  }

  const ctrlBuf = new SharedArrayBuffer(4 * (CTRL_DATA + KEY_CAPACITY));
  const geomBuf = new SharedArrayBuffer(8);
  const ctrl = new Int32Array(ctrlBuf);
  const geom = new Int32Array(geomBuf);

  // Shrink the type until the game fits, rather than cropping the game. Only
  // if even MIN_FONT cannot manage it do we fall back to telling the player.
  const fitToGame = () => {
    let size = MAX_FONT;
    for (;;) {
      term.options.fontSize = size;
      fit.fit();
      if ((term.rows >= MIN_ROWS && term.cols >= MIN_COLS) || size <= MIN_FONT) break;
      size -= 1;
    }
    Atomics.store(geom, 0, term.rows);
    Atomics.store(geom, 1, term.cols);

    const short = [];
    if (term.cols < MIN_COLS) short.push(`${MIN_COLS} columns`);
    if (term.rows < MIN_ROWS) short.push(`${MIN_ROWS} rows`);
    const banner = el('too-narrow');
    banner.hidden = short.length === 0;
    if (short.length) {
      banner.textContent =
        `Window is too small — Vimny needs ${short.join(' and ')} ` +
        `(this one is ${term.cols}x${term.rows}). Try a bigger window or zooming out.`;
    }
  };
  fitToGame();

  // Keystrokes queue here whenever the shared slot is still full — the worker
  // may be mid-frame. Dropping them instead would eat input from anyone typing
  // faster than the game redraws.
  let pending = '';

  function flush() {
    if (!pending) return;
    if (Atomics.load(ctrl, CTRL_FLAG) !== 0) return;      // worker hasn't taken the last batch
    const batch = pending.slice(0, KEY_CAPACITY);
    pending = pending.slice(batch.length);
    for (let i = 0; i < batch.length; i++) {
      Atomics.store(ctrl, CTRL_DATA + i, batch.charCodeAt(i));
    }
    window.vimny.sent += batch;      // what the game actually received; web/test/keys.mjs
    Atomics.store(ctrl, CTRL_LEN, batch.length);
    Atomics.store(ctrl, CTRL_FLAG, 1);
    Atomics.notify(ctrl, CTRL_FLAG);
  }

  term.onData((data) => { pending += data; flush(); });
  setInterval(flush, 16);          // drains whatever the worker was too busy to take

  // Control keys are xterm.js's business, and it is better at it than a hand-
  // rolled keydown handler: it cancels the browser's own shortcut and emits the
  // byte, for every combination the game reads — including Ctrl-W, which closes
  // the tab everywhere else. It also stops propagation, so a window-level
  // listener never sees these at all. web/test/keys.mjs presses all eight in a
  // real browser window; headless Chrome enforces none of the shortcuts and so
  // cannot answer the question.

  const worker = new Worker('worker.js', { type: 'module' });
  worker.onmessage = ({ data: msg }) => {
    if (msg.type !== 'out') console.debug('[vimny]', msg.type, msg.data ?? '');
    switch (msg.type) {
      case 'out':
        window.vimny.lastFrame = msg.data;    // for web/test/probe.mjs
        term.write(msg.data);
        break;
      case 'status': el('loading-status').textContent = msg.data; break;
      case 'ready':
        el('loading').hidden = true;
        term.focus();
        break;
      case 'persist':
        // The worker cannot store anything itself — see worker.js. Saves are a
        // few KB of JSON, well inside localStorage's budget.
        writeSaves(msg.data);
        break;
      case 'exited':
        // `:q` returns from main() rather than killing anything. Say so —
        // an untouched black rectangle reads as a crash.
        el('exited').hidden = false;
        break;
      case 'notice': notice(msg.data); break;
      case 'warn':   console.warn('[vimny]', msg.data); break;
      case 'error':
        fail('Vimny stopped.', msg.data);
        console.error('[vimny]', msg.data);
        break;
    }
  };
  worker.onerror = (err) => fail('The worker failed to start.', err.message);

  let saved = {};
  try {
    saved = JSON.parse(readSaves());
  } catch (err) {
    console.warn('[vimny] stored saves unreadable, starting fresh:', err);
  }

  worker.postMessage({
    type: 'init',
    base: new URL('.', window.location.href).href,
    wheels: manifest.wheels,
    ctrl: ctrlBuf,
    geom: geomBuf,
    saved,
    // The desktop build's `--level <slug>` debug flag, as a query parameter.
    // boot.py checks the slug against the curriculum and says so if it is not
    // one, rather than letting argparse exit into a blank screen.
    level: new URLSearchParams(location.search).get('level'),
  });

  el('play-again').addEventListener('click', () => {
    el('exited').hidden = true;
    term.reset();                     // the quit cleared the alt screen
    worker.postMessage({ type: 'restart' });
    term.focus();
  });

  window.addEventListener('resize', fitToGame);
  el('terminal').addEventListener('click', () => term.focus());
}
