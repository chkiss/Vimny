// Vimny in the browser — the Python side.
//
// This runs in a Web Worker for one reason: `term.inkey()` BLOCKS, and there
// are ~26 call sites inside an 11,000-line game loop. Rewriting that loop to be
// async would be a rewrite of the game. Instead the worker blocks for real —
// `Atomics.wait` on a SharedArrayBuffer the main thread writes keystrokes into —
// while the page stays responsive, because the page is a different thread.
//
// That is what needs `crossOriginIsolated`, and so the COOP/COEP headers in
// serve.py. Without them SharedArrayBuffer does not exist and nothing here runs.

// ESM, and loaded as `{type: 'module'}`: Pyodide 314 dropped classic workers,
// so importScripts is not an option.
import { loadPyodide } from './vendor/pyodide/pyodide.mjs';

let ctrl;        // Int32Array: [0] flag, [1] length, [2..] UTF-16 code units
let geom;        // Int32Array: [0] rows, [1] cols
let idle;        // Int32Array: a word that never changes, purely to sleep on

const CTRL_FLAG = 0;
const CTRL_LEN  = 1;
const CTRL_DATA = 2;

// ── The porting surface, as three functions Python calls ──────────────────────

// Blocking read. `timeoutMs < 0` means "wait forever" — blessed's inkey(None).
// Returns '' on timeout, which the shim turns into an empty Keystroke.
self.vimnyRead = function (timeoutMs) {
  if (Atomics.load(ctrl, CTRL_FLAG) === 0) {
    Atomics.wait(ctrl, CTRL_FLAG, 0, timeoutMs < 0 ? Infinity : timeoutMs);
  }
  if (Atomics.load(ctrl, CTRL_FLAG) === 0) return '';   // timed out
  const n = Atomics.load(ctrl, CTRL_LEN);
  let out = '';
  for (let i = 0; i < n; i++) out += String.fromCharCode(Atomics.load(ctrl, CTRL_DATA + i));
  Atomics.store(ctrl, CTRL_LEN, 0);
  Atomics.store(ctrl, CTRL_FLAG, 0);
  return out;
};

self.vimnyWrite = function (text) {
  self.postMessage({ type: 'out', data: text });
};

self.vimnySize = function () {
  return [Atomics.load(geom, 0), Atomics.load(geom, 1)];
};

// A real sleep, for the game's animations. Emscripten's own is a busy-wait;
// this one parks the thread the same way the input read does.
self.vimnySleep = function (ms) {
  Atomics.wait(idle, 0, 0, ms);
};

// Saves go OUT to the page, which owns storage.
//
// The obvious design — mount IDBFS and call FS.syncfs — cannot work here, and
// the reason is the same one that makes this worker exist. syncfs is
// asynchronous: it queues IndexedDB work and waits for the event loop. This
// thread is parked in Atomics.wait inside the game loop and will not return to
// its event loop until the player quits, so those callbacks never run and every
// save silently piles up "in flight". postMessage has no such problem — it
// hands the bytes to a thread that IS running its event loop.
self.vimnyPersist = function (json) {
  self.postMessage({ type: 'persist', data: json });
};

const status = (text) => self.postMessage({ type: 'status', data: text });

// ── Boot ─────────────────────────────────────────────────────────────────────

async function boot(base, wheels, saved) {
  status('Loading Python…');
  self.pyodide = await loadPyodide({ indexURL: `${base}vendor/pyodide/` });

  status('Installing Vimny…');
  await self.pyodide.loadPackage(wheels.map((w) => `${base}vendor/wheels/${w}`));

  // Restore the save files the page kept for us, before any Python runs.
  const FS = self.pyodide.FS;
  try {
    for (const [path, text] of Object.entries(saved || {})) {
      const dir = path.slice(0, path.lastIndexOf('/'));
      FS.mkdirTree(dir);
      FS.writeFile(path, text);
    }
  } catch (err) {
    self.postMessage({ type: 'warn', data: `could not restore saves: ${err}` });
  }

  status('Starting…');
  bootSource = await (await fetch(`${base}py/boot.py`)).text();
  self.postMessage({ type: 'ready' });
  await runGame();
}

// `:q` RETURNS from main() — it does not kill anything. On a terminal that
// hands you back your shell; here it would leave a blank page that looks like a
// crash, so the page is told, and can offer to start again.
//
// Restarting re-runs boot.py in this same interpreter, which is why boot.py has
// to be idempotent: a second Pyodide boot would be another 6 seconds and
// another 9 MB of parsing for something the player experiences as "play again".
let bootSource = '';

async function runGame() {
  try {
    await self.pyodide.runPythonAsync(bootSource);
    self.postMessage({ type: 'exited' });
  } catch (err) {
    self.postMessage({ type: 'error', data: String(err) });
  }
}

self.onmessage = (event) => {
  const msg = event.data;
  // Only reachable once the game has returned: while it runs this thread is
  // parked in Atomics.wait and messages simply queue.
  if (msg.type === 'restart') {
    runGame();
    return;
  }
  if (msg.type !== 'init') return;
  ctrl = new Int32Array(msg.ctrl);
  geom = new Int32Array(msg.geom);
  idle = new Int32Array(new SharedArrayBuffer(4));
  boot(msg.base, msg.wheels, msg.saved).catch((err) =>
    self.postMessage({ type: 'error', data: String(err) }));
};
