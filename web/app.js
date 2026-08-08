// Vimny in the browser — the page side.
//
// Owns the terminal emulator and the keyboard, and hands keystrokes to the
// worker through shared memory. It never blocks: the worker does the waiting.

const KEY_CAPACITY = 4096;            // UTF-16 code units in flight at once
const CTRL_FLAG = 0, CTRL_LEN = 1, CTRL_DATA = 2;
const SAVE_KEY = 'vimny:saves';       // the whole ~/.Vimny tree, as JSON

const el = (id) => document.getElementById(id);

function fail(message, detail) {
  el('loading').hidden = true;
  el('failure').hidden = false;
  el('failure-message').textContent = message;
  el('failure-detail').textContent = detail || '';
}

if (!window.crossOriginIsolated) {
  // SharedArrayBuffer is gated on COOP/COEP. Without it the worker cannot block
  // on input, and the whole design falls over — so say so plainly rather than
  // failing later in a way that looks like a game bug.
  fail('This page is not cross-origin isolated.',
       'Vimny needs the COOP and COEP headers to use SharedArrayBuffer. ' +
       'Serve it with web/serve.py, or set those headers on your host.');
} else {
  start();
}

async function start() {
  const manifest = await (await fetch('vendor/manifest.json')).json();

  const term = new Terminal({
    fontFamily: '"DejaVu Sans Mono", "Cascadia Mono", "Menlo", monospace',
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
  window.vimny = { term, fit };

  const ctrlBuf = new SharedArrayBuffer(4 * (CTRL_DATA + KEY_CAPACITY));
  const geomBuf = new SharedArrayBuffer(8);
  const ctrl = new Int32Array(ctrlBuf);
  const geom = new Int32Array(geomBuf);

  const publishSize = () => {
    Atomics.store(geom, 0, term.rows);
    Atomics.store(geom, 1, term.cols);
    el('too-narrow').hidden = term.cols >= 80;
  };
  publishSize();

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
    Atomics.store(ctrl, CTRL_LEN, batch.length);
    Atomics.store(ctrl, CTRL_FLAG, 1);
    Atomics.notify(ctrl, CTRL_FLAG);
  }

  term.onData((data) => { pending += data; flush(); });
  setInterval(flush, 16);          // drains whatever the worker was too busy to take

  // Ctrl-W is reserved by the browser to close the tab, so xterm.js never
  // receives it and the game sees nothing. Intercept it at the keydown level,
  // stop the default, and hand the game the byte it expects ('\x17') — that is
  // insert-mode <C-w> (delete word back) and <C-r><C-w> (insert word under
  // cursor). Only act once the game is up; never swallow Ctrl-W on the failure
  // or loading overlays.
  window.addEventListener('keydown', (e) => {
    if (!e.ctrlKey || e.altKey || e.metaKey) return;
    if (e.key !== 'w' && e.key !== 'W' && e.code !== 'KeyW') return;
    if (!el('loading').hidden || !el('failure').hidden) return;
    e.preventDefault();
    pending += '\x17';
    flush();
  });

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
        try {
          localStorage.setItem(SAVE_KEY, msg.data);
        } catch (err) {
          console.warn('[vimny] could not save:', err);   // private mode, or full
        }
        break;
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
    saved = JSON.parse(localStorage.getItem(SAVE_KEY) || '{}');
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
  });

  window.addEventListener('resize', () => { fit.fit(); publishSize(); });
  el('terminal').addEventListener('click', () => term.focus());
}
