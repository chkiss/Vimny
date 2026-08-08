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
python3 -m pytest tests/test_web_terminal.py       # the shim, no browser needed
npm i puppeteer-core
node web/test/smoke.mjs                            # does the game work
node web/test/lifecycle.mjs                        # what happens at the edges
node web/test/probe.mjs                            # geometry diagnostics
```

`smoke.mjs` plays through the title screen into The First Cave, types at it, and
checks the save survives a reload. `lifecycle.mjs` covers what a terminal player
cannot do: quit and restart, reload mid-game, a second tab, a hidden tab,
resizing to a laptop and to something impossible. Both start their own server.

## Deliberately not in the browser build

Turned off in `web/py/boot.py` via `vimny/features.py`, because each would
otherwise fail in a way that reads as a bug rather than a boundary:

- **The forge.** Authoring ends in `:submit`, which needs a browser tab Vimny
  cannot open from a worker and writes a file into a virtual filesystem the
  author cannot reach. `forge/` is not listed, and `%` says
  *"Not in the browser build — `pip install vimny` to compose levels."*
- **The community shelf.** Its HTTPS fetch dies on `RuntimeError: TLS not
  supported in this environment` — WebAssembly Python has no TLS. The shelf
  browser already displays a one-line reason when it has nothing, so `boot.py`
  gives it that sentence rather than teaching the overworld a new refusal.
  Curated levels can be served from this origin later, when there are some.

## Window size

The game needs **80x45 characters**. 80 columns is documented; 45 rows is the
title screen's requirement — measured, not guessed: at 45 the menu is on screen
and at 42 it is not, because the logo and the wizard push it off the bottom. A
browser window is far shorter than a full-screen terminal (a 1366x768 laptop is
about 35 rows at 15px), so `app.js` shrinks the font until the game fits and
only warns if even 8px cannot manage it.

## Web vs the terminal build

The browser build runs the **same `vimny` wheel** — Pyodide executes the
identical game logic, level builders, pars, and command curriculum as the
terminal version, so a level you cannot clear here, you could not clear there
either. The only differences live at the input and persistence boundary:

- **Gameplay is identical.** Every `term.*` call the game makes — truecolor,
  alt-screen, cursor hiding, geometry — is implemented in `web_terminal.py`, so
  there is no gameplay gap between the two builds.
- **`<C-w>` was the one real input delta.** The terminal version receives
  Ctrl-W freely; the browser did not, until `app.js` began intercepting the
  keydown (above). All other control keys — `<C-v>`, `<C-r>`, `<C-d>`,
  `<C-u>`, `<C-o>`, `<C-f>`/`<C-b>` — come through in both.
- **Saves are per-browser, not on disk.** The terminal build writes real files
  to `~/.Vimny/saves/*.json`. The web build writes to the Pyodide FS, which the
  worker mirrors to `localStorage['vimny:saves']`. The save schema is the same,
  but a player clearing site data loses progress, and there is no cross-device
  sync.
- **First load is ~9 MB** of Pyodide/wasm (cached afterwards) — a one-time web
  tax the terminal build does not pay.

To exercise the port end-to-end without a browser, drive the real game through
the shim in plain CPython: `python3 -m pytest tests/test_web_terminal.py`.

## Known limitations

- **`<C-w>` is intercepted.** Chrome will not let xterm.js see Ctrl-W (it closes
  the tab), so `app.js` catches the keydown, `preventDefault`s it, and feeds the
  game the byte it expects (`\x17`). That enables insert-mode `<C-w>` (delete
  word back) and `<C-r><C-w>` (insert word under cursor) — both optional relic
  scrolls, required by no level. It is only active once the game is up; on the
  loading or failure overlay Ctrl-W reverts to its browser default.
- **Fonts are the browser's.** Vimny picks glyphs by measured width, so a font
  without the box-drawing or rune characters degrades rather than breaks, but
  it will not look like the terminal build.
- **Saves are per-browser**, in `localStorage`, and a player clearing site data
  clears their progress. There is no account and nothing leaves the machine.
- **First load is ~9 MB** (about a second on fibre, ~6 s on 10 Mbps), cached
  afterwards. A restart after `:q` re-runs `boot.py` in the same interpreter and
  takes ~0.3 s.
- **No service worker**, so an offline reload depends on the HTTP cache rather
  than on anything deliberate. Not offline-first.
- **Mobile has no keyboard.** The game is unplayable on a phone; nothing warns
  about that yet.
