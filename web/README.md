# Vimny in the browser

The real game — the same `vimny` wheel that goes to PyPI — running as Python
compiled to WebAssembly, drawing into xterm.js. No server does any of the work:
once the page loads, everything happens in the tab.

```bash
./web/build.sh          # fetch Pyodide + xterm.js, build the wheel  (~17 MB, once)
./web/serve.py          # http://localhost:8000
```

## How it fits together

| Piece | Job |
|---|---|
| `vimny/web_terminal.py` | A blessed-shaped `Terminal` that emits ANSI. Ships in the wheel. |
| `web/worker.js` | Runs Pyodide in a Web Worker. Owns the blocking read. |
| `web/py/boot.py` | Binds the shim to the page and starts the game. |
| `web/app.js` | The page: xterm.js, the keyboard, and storage. |
| `web/serve.py` | Dev server with the two headers this needs. |

Three things make it work, and each is the answer to a problem that has no
smaller answer:

**blessed cannot load.** It imports `termios` at module scope, which
WebAssembly Python has not got. But xterm.js is a real terminal emulator, so
the shim answers `color_rgb(200, 30, 30)` with the escape sequence blessed
would have produced and lets the emulator paint it. `install()` registers the
shim in `sys.modules` under blessed's name, so the seventeen
`from blessed import Terminal` lines in the codebase are untouched.

**`term.inkey()` blocks**, in ~26 places inside an 11,000-line game loop.
Rewriting that to be async would be a rewrite of the game. So Python runs in a
Web Worker and blocks for real, on `Atomics.wait` against a SharedArrayBuffer
the page writes keystrokes into. The page never blocks, because the page is a
different thread. This is why the COOP/COEP headers below are mandatory rather
than advisory: without them there is no SharedArrayBuffer and nothing runs.

**The worker cannot store anything.** Parked in `Atomics.wait`, it never
returns to its event loop, so every asynchronous storage API — IndexedDB,
`FS.syncfs` — queues work whose callback can never fire. Saves are therefore
posted out to the page, which owns `localStorage` and is free to run.

## Deploying

Any static host will do, but it **must** send:

```
Cross-Origin-Opener-Policy: same-origin
Cross-Origin-Embedder-Policy: require-corp
```

Without them the page loads and then refuses to start, with an explanation on
screen. GitHub Pages cannot set headers at all and is therefore not an option;
Cloudflare Pages, Netlify and any nginx can.

nginx, serving from a checkout where `build.sh` has been run:

```nginx
location / {
    root /srv/vimny/web;
    add_header Cross-Origin-Opener-Policy   same-origin;
    add_header Cross-Origin-Embedder-Policy require-corp;

    # The wasm is 9 MB and the stdlib 2.5 MB. Compress once, cache hard —
    # the filenames are version-stamped by build.sh's manifest.
    gzip_static on;
    types { application/wasm wasm; }
}
```

Server load is a rounding error: it serves static files and nothing else. The
computing is on the player's machine, however many players there are.

## Testing

```bash
python3 -m pytest tests/test_web_terminal.py     # the shim, no browser needed
npm i puppeteer-core && node web/test/smoke.mjs  # the real thing, headless Chromium
node web/test/probe.mjs                          # geometry diagnostics
```

`smoke.mjs` starts its own server, plays through the title screen into The
First Cave, types at it, and checks the save survives a reload.

## Known limitations

- **`<C-w>` never arrives.** Chrome will not let a page intercept it. It is an
  insert-mode convenience that no level requires, and everything else —
  `<C-v>`, `<C-r>`, `<C-d>` — comes through.
- **Fonts are the browser's.** Vimny picks glyphs by measured width, so a font
  without the box-drawing or rune characters degrades rather than breaks, but
  it will not look like the terminal build.
- **Saves are per-browser**, in `localStorage`, and a player clearing site data
  clears their progress. There is no account and nothing leaves the machine.
- **First load is ~9 MB** (about a second on fibre, ~6 s on 10 Mbps), cached
  afterwards.
