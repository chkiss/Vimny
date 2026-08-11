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
| `web/subset_fonts.py` | Cuts three fonts down to the characters Vimny draws. |
| `web/sw.js` | Service worker: makes the second visit work with no network. |
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

    # The wasm is 9 MB and the stdlib 2.5 MB. Compress once, cache hard.
    gzip_static on;
    types { application/wasm wasm; font/woff2 woff2; }
}
```

Server load is a rounding error: it serves static files and nothing else. The
computing is on the player's machine, however many players there are.

One caching caveat: the font subsets are not version-stamped, and they change
whenever a rune joins the game. Either serve `vendor/fonts/` with a short
max-age, or purge it on deploy.

## Testing

```bash
python3 -m pytest tests/test_web_terminal.py       # the shim, no browser needed
cd web && npm i
node test/smoke.mjs                                # does the game work
node test/lifecycle.mjs                            # what happens at the edges
node test/saves.mjs                                # progress in and out, ?level=, mobile
DISPLAY=:0 node test/keys.mjs                      # control keys, in a real window
node test/probe.mjs                                # geometry diagnostics
```

Each starts its own server on its own port, so they can run at once.

- `smoke.mjs` plays through the title screen into The First Cave, types at it,
  and checks the save survives a reload.
- `lifecycle.mjs` covers what a terminal player cannot do: quit and restart,
  reload mid-game, a second tab, a hidden tab, resizing to a laptop and to
  something impossible.
- `saves.mjs` covers what a browser player has instead of a home directory:
  export, import, an import that is not a save, a browser that refuses to
  store, `?level=`, and a phone.
- `keys.mjs` **needs a display and opens a visible window**, and that is the
  whole point. Headless Chrome enforces none of the browser's own keyboard
  shortcuts — no tab to close on Ctrl-W, no find bar on Ctrl-F — so it will
  cheerfully report that all eight control keys work and be unable to tell you
  which mechanism made that true. Run headless, it skips itself.

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

## Fonts

Vimny's dungeons are built out of runes from the chess, card, dice, planetary
and alchemical blocks — `vimny/art/vocab_mixed.txt` is the vocabulary, and a
missing glyph is a puzzle with a hole in it. A terminal player has a font they
chose; a visitor gets whatever their browser calls "monospace", which very often
does not cover those.

So `build.sh` subsets and ships the three faces it takes to cover the 259
non-ASCII characters in the package, each cut to only what the one before it
could not supply:

| Face | Source | Glyphs | Size |
|---|---|---|---|
| Vimny Mono | DejaVu Sans Mono | 316 | 32 KB |
| Vimny Runes | Symbola (public domain) | 35 | 4 KB |
| Vimny Extra | DejaVu Sans | 3 | 4 KB |

The last three are Canadian Syllabics, and exist because of `ᕕ( ᐛ )ᕗ`. Symbola
carries what DejaVu has no glyph for at all, which is mostly pentagrams,
trigrams and alchemical fire — 134 uses of `⛧` alone.

`subset_fonts.py` prints anything no bundled font covers, so adding a rune that
nothing can draw is a build-time complaint rather than a tofu box in a dungeon.

**Why not one font?** Nothing installed here covers all 354 characters, and the
one thing that does — GNU Unifont, which spans the whole BMP — is a 16-pixel
bitmap design that draws 105 of them double-width, so the grid would come apart
wherever a rune landed. The two fallback faces are proportional, which is its
own version of that problem: Symbola draws a pentagram a full em wide against
DejaVu Sans Mono's 0.602 em cell, and a terminal emulator draws at the cell
origin regardless, so the glyph paints over its neighbour. `subset_fonts.py`
measures both faces and emits a `size-adjust` that shrinks each fallback until
its widest glyph fits the cell. The runes come out a little smaller than the
text around them. That is the price of them being in the right column.

## Web vs the terminal build

The browser build runs the **same `vimny` wheel** — Pyodide executes the
identical game logic, level builders, pars, and command curriculum as the
terminal version, so a level you cannot clear here, you could not clear there
either. The only differences live at the input and persistence boundary:

- **Gameplay is identical.** Every `term.*` call the game makes — truecolor,
  alt-screen, cursor hiding, geometry — is implemented in `web_terminal.py`, so
  there is no gameplay gap between the two builds.
- **Every control key arrives.** `<C-v>`, `<C-r>`, `<C-o>`, `<C-u>`, `<C-d>`,
  `<C-f>`, `<C-b>` and `<C-w>` all reach the game in a real Chrome window, even
  though the browser would rather reload, view source, bookmark, find, or close
  the tab. xterm.js cancels its own shortcut and emits the byte; nothing here
  intercepts anything. `web/test/keys.mjs` presses all eight.
- **Saves are per-browser, not on disk.** The terminal build writes real files
  to `~/.Vimny/saves/*.json`. The web build writes to the Pyodide FS, which the
  worker mirrors to `localStorage['vimny:saves']`. The save schema is the same,
  so **Export save** hands back a file you could drop into `~/.Vimny` — but
  there is no account and no cross-device sync, and clearing site data without
  exporting first ends a run.
- **First load is ~9 MB** of Pyodide/wasm (cached afterwards) — a one-time web
  tax the terminal build does not pay.

To exercise the port end-to-end without a browser, drive the real game through
the shim in plain CPython: `python3 -m pytest tests/test_web_terminal.py`.

## Known limitations

- **Ctrl-W closes the tab on any overlay.** While the game has focus xterm.js
  cancels it; on the loading, failure or quit overlay it does not, so Ctrl-W is
  the browser's again. That is the right way round — a page you could not close
  would be worse — but it means Ctrl-W during the 6-second boot ends the visit.
- **Saves are per-browser**, in `localStorage`, and a player clearing site data
  clears their progress unless they exported it. There is no account and
  nothing leaves the machine.
- **First load is ~9 MB** (about a second on fibre, ~6 s on 10 Mbps), cached
  afterwards. A restart after `:q` re-runs `boot.py` in the same interpreter and
  takes ~0.3 s.
- **Mobile is turned away, not supported.** A touch device with no fine pointer
  is told it needs a keyboard before any WebAssembly is fetched — 9 MB over a
  phone connection for a game that cannot be played is worse than a refusal.
  "Load it anyway" is there for the tablet with a keyboard attached that guessed
  wrong.

## Offline

Vimny computes in the tab and saves in the browser, so needing a server to
*start* was the odd part. After one visit it does not: `sw.js` caches the 9 MB,
and a reload with the network unplugged boots to the title screen — verified in
`lifecycle.mjs`, not assumed.

Two strategies, split by what the file is. `vendor/` is **cache-first** — 9 MB
that only changes when `build.sh` runs, and revalidating it would throw away
the whole point. Everything else is **network-first with a cache fallback**:
`index.html`, `app.js`, `worker.js` and `py/boot.py` are small and are what
actually gets edited, and a stale one of those against a fresh wheel is a
wasted afternoon.

Freshness across builds is a whole-cache swap, not per-file cleverness:
`build.sh` stamps `manifest.json` with a build id, the page hands it to the
worker, and any cache under a different id is deleted. A rebuild costs one
refetch of everything, which beats reasoning about half-stale mixtures.

While developing, `serve.py` sends `no-store` and the app shell is
network-first, so edits land on reload. If a service worker ever does get in
your way: DevTools → Application → Service Workers → Unregister.

## URL options

`?level=<slug>` is the desktop build's `--level` debug flag: it skips the title
screen and starts there, wizard's poem and all. `boot.py` checks the slug
against the curriculum and says so on the page if it is not one, rather than
letting argparse exit into a black rectangle.

**A preview is read-only, and has to be.** `--level` skips the title screen, so
nobody was asked who is playing: the game runs as the default Normand with
empty progress, and on `:wq` it would write that emptiness over whatever
`normand.json` held. On a desktop that flag is typed by the person who owns the
save directory. A URL is not — it can be handed to anyone. So `boot.py` lets
the game write to the Pyodide filesystem as usual, and posts none of it to the
page, which is where localStorage lives. The player is told on arrival.

That is also the shape a "featured community level" link wants: play it, no
account, nothing touched.
