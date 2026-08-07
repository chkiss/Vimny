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

"""A blessed-shaped Terminal for hosts that have no tty — the browser build.

blessed imports `termios` at module load, which WebAssembly Python has not got,
so the browser cannot import it at all. What it CAN do is speak the same
language: xterm.js is a real terminal emulator, so `color_rgb(200, 30, 30)` is
answered here with the escape sequence blessed would have produced, and the
emulator on the other end paints it.

`install(io)` puts this class in `sys.modules` under blessed's own name, so the
seventeen `from blessed import Terminal` lines around the codebase keep working
untouched. It must run BEFORE `vimny.game` is imported.

The host supplies an `io` with three methods, which is the whole porting
surface:

    read(timeout) -> str   raw input; '' when `timeout` seconds elapse first.
                           timeout=None blocks forever.
    write(text)            emit text (escape sequences included).
    size() -> (rows, cols)

That indirection is what keeps this file testable: `tests/test_web_terminal.py`
drives the real game through a scripted io in plain CPython, no browser
involved.
"""
from __future__ import annotations

import re
import sys
import types

# Vimny reads only these five key names (`grep 'key.name'`), plus LEFT/RIGHT for
# the overworld. Anything else arrives as its literal character, which is what
# the vim parser wants — a control key like <C-v> IS '\x16' to it.
_SEQUENCES = {
    '\x1b[A': 'KEY_UP',
    '\x1b[B': 'KEY_DOWN',
    '\x1b[C': 'KEY_RIGHT',
    '\x1b[D': 'KEY_LEFT',
    '\x1b': 'KEY_ESCAPE',
    '\r': 'KEY_ENTER',
    '\n': 'KEY_ENTER',
    '\x7f': 'KEY_BACKSPACE',
    '\x08': 'KEY_BACKSPACE',
    '\t': 'KEY_TAB',
}

_ANSI_RE = re.compile(r'\x1b\[[0-9;?]*[A-Za-z]')
_LONE_LF = re.compile(r'(?<!\r)\n')


def _crlf(text: str) -> str:
    """Do what the tty driver would: turn `\\n` into `\\r\\n` (ONLCR).

    A terminal's LF moves DOWN and nothing else — the carriage return that also
    sends the cursor home is added by the kernel's line discipline, which no
    program running on a real tty ever has to think about. An emulator reached
    directly has no line discipline, so a frame written as `'\\n'.join(rows)`
    would staircase off the right edge: every row starting where the last one
    ended. Vimny renders whole rows, so this is the difference between a game
    and an empty box.
    """
    return _LONE_LF.sub('\r\n', text)


class Keystroke(str):
    """blessed's Keystroke: a string that also knows its key name."""

    def __new__(cls, ucs: str = '', name: str | None = None, code: int | None = None):
        ks = super().__new__(cls, ucs)
        ks._name = name
        ks._code = code
        return ks

    @property
    def name(self):
        return self._name

    @property
    def code(self):
        return self._code

    @property
    def is_sequence(self) -> bool:
        return self._name is not None


def _split(raw: str) -> list:
    """Raw terminal input → Keystrokes, longest sequence first.

    A lone ESC is the Escape key: the browser delivers one keypress per event,
    so unlike a real tty there is no ambiguity to time out on. An ESC that
    begins a sequence arrives with the rest of it in the same batch.
    """
    out, i = [], 0
    while i < len(raw):
        for span in (3, 2, 1):
            chunk = raw[i:i + span]
            if len(chunk) == span and chunk in _SEQUENCES:
                out.append(Keystroke(chunk, _SEQUENCES[chunk]))
                i += span
                break
        else:
            out.append(Keystroke(raw[i]))
            i += 1
    return out


class _Ctx:
    """A context manager that writes on the way in and on the way out —
    blessed's fullscreen / hidden_cursor / cbreak, minus the termios."""

    def __init__(self, term, enter: str = '', exit_: str = ''):
        self._term, self._enter, self._exit = term, enter, exit_

    def __enter__(self):
        self._term.stream_write(self._enter)
        return self._term

    def __exit__(self, *exc):
        self._term.stream_write(self._exit)
        return False


class WebTerminal:
    """blessed.Terminal's public surface, as far as Vimny uses it.

    Everything Vimny asks of a terminal is here; `grep -oh 'term\\.[a-z_]*'`
    over the package is the authority on that list, and it is twenty-one names
    long. Colours are truecolor SGR, which xterm.js renders.
    """

    number_of_colors = 1 << 24

    def __init__(self, io):
        self._io = io
        self._pending: list = []

    # ── output ────────────────────────────────────────────────────────────
    def stream_write(self, text: str) -> None:
        if text:
            self._io.write(_crlf(text))

    normal        = '\x1b[0m'
    bold          = '\x1b[1m'
    dim           = '\x1b[2m'
    bright_white  = '\x1b[97m'
    bright_yellow = '\x1b[93m'
    bright_green  = '\x1b[92m'
    home          = '\x1b[H'
    clear         = '\x1b[2J\x1b[H'
    civis         = '\x1b[?25l'
    cnorm         = '\x1b[?25h'
    cvvis         = '\x1b[?25h'

    @staticmethod
    def color_rgb(r: int, g: int, b: int) -> str:
        return f'\x1b[38;2;{r};{g};{b}m'

    @staticmethod
    def on_color_rgb(r: int, g: int, b: int) -> str:
        return f'\x1b[48;2;{r};{g};{b}m'

    @staticmethod
    def move_yx(y: int, x: int) -> str:
        return f'\x1b[{y + 1};{x + 1}H'

    @staticmethod
    def length(text: str) -> int:
        """Printable width, escape sequences excluded.

        `render/symbols.py` calls this to decide whether a glyph fits in one
        column, so it has to account for double-width characters rather than
        count code points.
        """
        plain = _ANSI_RE.sub('', text)
        try:
            from wcwidth import wcswidth          # noqa: PLC0415
            width = wcswidth(plain)
            if width >= 0:
                return width
        except ImportError:
            pass
        return len(plain)

    # ── geometry ──────────────────────────────────────────────────────────
    @property
    def height(self) -> int:
        return self._io.size()[0]

    @property
    def width(self) -> int:
        return self._io.size()[1]

    # ── modes ─────────────────────────────────────────────────────────────
    def fullscreen(self):
        # Alt screen, AND auto-wrap off (DECAWM, `?7`). A full-screen TUI paints
        # every cell itself and never wants the emulator inventing a line break:
        # with wrap on, a row that fills the last column pushes the next row's
        # first character onto a line of its own, and the whole frame walks one
        # column left as it goes down the screen.
        return _Ctx(self, '\x1b[?1049h\x1b[?7l', '\x1b[?7h\x1b[?1049l')

    def hidden_cursor(self):
        return _Ctx(self, self.civis, self.cnorm)

    def cbreak(self):
        # The browser has no line discipline to switch off; the host hands us
        # keys the moment they are pressed.
        return _Ctx(self)

    # ── input ─────────────────────────────────────────────────────────────
    def inkey(self, timeout=None, **_kw) -> Keystroke:
        """One keystroke. Empty Keystroke if `timeout` elapses first.

        Vimny polls with small timeouts to animate, so a batch of keys that
        arrives together is queued and served one per call — dropping the rest
        of the batch would eat keystrokes from anyone typing quickly.
        """
        if self._pending:
            return self._pending.pop(0)
        raw = self._io.read(timeout)
        if not raw:
            return Keystroke('')
        self._pending = _split(raw)
        return self._pending.pop(0) if self._pending else Keystroke('')


class _Stdout:
    """Frames reach the screen as `print(...)`, not through the terminal.

    `renderer.render_all` ends in a single `print(term.home + frame, flush=True)`
    — blessed builds escape sequences but never owns the stream. So the host has
    to be handed sys.stdout as well, or it would see nothing but the alt-screen
    switch.
    """

    def __init__(self, io):
        self._io = io

    def write(self, text: str) -> int:
        if text:
            self._io.write(_crlf(text))
        return len(text)

    def flush(self) -> None:
        pass

    def isatty(self) -> bool:
        return True


def install(io, capture_stdout: bool = True) -> WebTerminal:
    """Register this terminal under blessed's name and return the instance.

    Call before importing `vimny.game`. Every `from blessed import Terminal`
    then resolves here, and `Terminal()` — which `game.main()` calls with no
    arguments — hands back the terminal bound to `io`.
    """
    term = WebTerminal(io)
    if capture_stdout:
        sys.stdout = _Stdout(io)

    blessed = types.ModuleType('blessed')
    blessed.Terminal = lambda *a, **k: term
    keyboard = types.ModuleType('blessed.keyboard')
    keyboard.Keystroke = Keystroke
    blessed.keyboard = keyboard

    sys.modules['blessed'] = blessed
    sys.modules['blessed.keyboard'] = keyboard
    return term
