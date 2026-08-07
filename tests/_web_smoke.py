# Vimny — a Vim-teaching dungeon crawler.
# Copyright (C) 2026 Chas Kissick
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Play a level through the web terminal, in a FRESH interpreter, and report.

Run by `tests/test_web_terminal.py` as a subprocess, not imported: `install()`
replaces `blessed` in `sys.modules`, and `vimny.game` binds `Terminal` at import
time — so the swap only works in a process where nothing has imported the real
blessed yet. A subprocess is the cheap way to guarantee that; in the browser the
interpreter is always fresh.

Prints one JSON object on stdout. The game's own output goes to the scripted io,
never to the real stdout, so the two cannot tangle.
"""
import json
import os
import sys
import tempfile


class _Done(Exception):
    """The key script ran out — the only way we stop a game loop that is
    designed never to return."""


class ScriptedIO:
    """The porting surface, fed from a list instead of a browser."""

    def __init__(self, keys, rows=30, cols=100):
        self.keys    = list(keys)
        self.frames  = []
        self._rows   = rows
        self._cols   = cols

    def read(self, timeout=None):
        if not self.keys:
            raise _Done
        return self.keys.pop(0)

    def write(self, text):
        self.frames.append(text)

    def size(self):
        return (self._rows, self._cols)


def main() -> int:
    # A throwaway HOME: the game writes saves, and a smoke test must not touch
    # the real ~/.Vimny.
    tmp = tempfile.mkdtemp(prefix='vimny-web-smoke-')
    os.environ['HOME'] = tmp
    report_to = sys.stdout          # install() is about to take sys.stdout

    from vimny.web_terminal import install            # noqa: PLC0415

    keys = [
        '\r',                       # dismiss whatever greets us
        'l', 'l', 'l', 'j', 'j',    # move: proves motion + redraw
        'k', 'h',
        ':', 'q', '!', '\r',        # leave the level
    ]
    io = ScriptedIO(keys)
    install(io)

    sys.argv = ['vimny', '--level', 'first_cave']
    from vimny.game import main as game_main          # noqa: PLC0415

    try:
        game_main()
    except _Done:
        pass

    joined = ''.join(io.frames)
    # The frame the player would be looking at when the keys ran out.
    last = io.frames[-1] if io.frames else ''
    # install() took sys.stdout — the report goes to the real one.
    print(json.dumps({
        'frames':      len(io.frames),
        'bytes':       len(joined),
        'has_truecolor': '\x1b[38;2;' in joined,
        'has_altscreen': '\x1b[?1049h' in joined,
        'has_box':     '┌' in joined and '└' in joined,
        'has_player':  '@' in joined,
        'has_hint':    ':q quit' in joined,
        'has_title':   'The First Cave' in joined,
        'distinct':    len({f for f in io.frames if len(f) > 200}),
        'last_len':    len(last),
    }), file=report_to)
    return 0


if __name__ == '__main__':
    sys.exit(main())
