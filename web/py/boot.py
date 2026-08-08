# Vimny — a Vim-teaching dungeon crawler.
# Copyright (C) 2026 Chas Kissick
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""What the browser worker runs. Binds the shim to the page and starts the game.

Everything platform-specific is `js.vimny*` — four functions the worker exposes.
The game itself is imported unmodified from the wheel.
"""
import json
import sys
import time

import js

from vimny.web_terminal import install


class BrowserIO:
    """`vimny.web_terminal`'s three-method porting surface, over the worker."""

    def read(self, timeout=None):
        # -1 is "block forever": Infinity does not survive the trip as an int.
        return js.vimnyRead(-1 if timeout is None else int(timeout * 1000))

    def write(self, text):
        js.vimnyWrite(text)

    def size(self):
        rows, cols = js.vimnySize()
        return (int(rows), int(cols))


# This file is re-run to restart the game after `:q` (see worker.js), in the
# same interpreter — so everything below the guard happens exactly once, and
# only `main()` at the end happens again.
_FIRST_RUN = not getattr(sys, '_vimny_web_booted', False)
sys._vimny_web_booted = True

if _FIRST_RUN:
    # The game animates with time.sleep. Emscripten's is a busy-wait that would
    # peg a core; the worker can park the thread properly, so use that instead.
    time.sleep = lambda seconds: js.vimnySleep(int(seconds * 1000))

    install(BrowserIO())

# Imported AFTER install(), which is the whole trick: `game` binds `Terminal`
# from `blessed` at import time, and by now `blessed` is the shim.
import vimny.features as FEAT             # noqa: E402
import vimny.save.save_manager as SM      # noqa: E402
import vimny.sharing.remote as REMOTE     # noqa: E402
from vimny.game import main               # noqa: E402

# What this build does not carry. Both would otherwise fail in ways that read as
# bugs rather than as boundaries: the forge writes a submission into a virtual
# filesystem nobody can reach, and the shelf's HTTPS fetch dies on
# `RuntimeError: TLS not supported in this environment`.
FEAT.FORGE = False
FEAT.REMOTE_SHELF = False

# The shelf browser already knows how to show a one-line reason it has nothing —
# so give it one, rather than teaching the overworld a new kind of refusal.
REMOTE.fetch_manifest = lambda: ([], FEAT.message('browse the community shelf'))

SM.SAVE_DIR.mkdir(parents=True, exist_ok=True)
SM.SAVES_DIR.mkdir(parents=True, exist_ok=True)


def _snapshot() -> str:
    """Everything under ~/.Vimny, as {path: text} JSON.

    Small by construction — a save is a few KB of JSON — so sending the whole
    tree after each write is cheaper than tracking which file changed.
    """
    files = {}
    for path in SM.SAVE_DIR.rglob('*'):
        if path.is_file():
            try:
                files[str(path)] = path.read_text(encoding='utf-8')
            except (OSError, UnicodeDecodeError):
                pass                      # not text, not ours to persist
    return json.dumps(files)


def _persist(fn):
    """Hand the save tree to the page after anything that writes to it.

    The page owns storage: this thread blocks inside the game loop and never
    returns to its event loop, so it cannot run an async storage API itself.
    """
    def wrapped(*args, **kwargs):
        result = fn(*args, **kwargs)
        js.vimnyPersist(_snapshot())
        return result
    return wrapped


if _FIRST_RUN:
    # Guarded, or a restart would wrap the wrappers and persist twice per save.
    for _name in ('save_for', 'save_progress', 'delete_save', 'save_layout',
                  'delete_layout', 'rename_layout', 'save_scroll_text',
                  'touch_loaded'):
        if hasattr(SM, _name):
            setattr(SM, _name, _persist(getattr(SM, _name)))

sys.argv = ['vimny']
main()      # returns on `:q` — the worker tells the page, which offers a restart
