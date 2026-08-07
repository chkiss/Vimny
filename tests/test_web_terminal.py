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

"""The browser build's terminal shim — checked without a browser.

The end-to-end check (headless Chromium, real xterm.js) is
`web/test/smoke.mjs`, which needs node and a browser. These tests need neither:
the shim is written against a three-method `io`, so a scripted one drives the
real game in a subprocess and proves the port is complete.
"""
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from vimny.web_terminal import Keystroke, WebTerminal, _crlf, _split

ROOT = Path(__file__).resolve().parent.parent


# ── Key decoding ──────────────────────────────────────────────────────────────

@pytest.mark.parametrize('raw, name', [
    ('\x1b[A',  'KEY_UP'),
    ('\x1b[B',  'KEY_DOWN'),
    ('\x1b[C',  'KEY_RIGHT'),
    ('\x1b[D',  'KEY_LEFT'),
    ('\x1b',    'KEY_ESCAPE'),
    ('\r',      'KEY_ENTER'),
    ('\x7f',    'KEY_BACKSPACE'),
])
def test_named_keys(raw, name):
    keys = _split(raw)
    assert len(keys) == 1
    assert keys[0].name == name
    assert keys[0].is_sequence


def test_plain_characters_are_not_sequences():
    keys = _split('dw')
    assert [str(k) for k in keys] == ['d', 'w']
    assert all(k.name is None and not k.is_sequence for k in keys)


def test_control_characters_pass_through_raw():
    # <C-v> is '\x16' to the vim parser — it must arrive as itself, not as a name.
    keys = _split('\x16')
    assert str(keys[0]) == '\x16'
    assert keys[0].name is None


def test_a_batch_splits_into_every_keystroke():
    # Typing faster than the game redraws must not lose keys.
    keys = _split('j\x1b[Bk\r')
    assert [k.name or str(k) for k in keys] == ['j', 'KEY_DOWN', 'k', 'KEY_ENTER']


def test_escape_before_a_letter_stays_two_keystrokes():
    # Esc then i — leaving insert mode and entering it again — is two keys,
    # not an unrecognised sequence.
    keys = _split('\x1bi')
    assert keys[0].name == 'KEY_ESCAPE'
    assert str(keys[1]) == 'i'


# ── Output ────────────────────────────────────────────────────────────────────

def test_lone_newlines_become_crlf():
    # Without this the emulator's cursor keeps its column on a line feed and the
    # frame staircases off the screen.
    assert _crlf('a\nb') == 'a\r\nb'


def test_existing_crlf_is_not_doubled():
    assert _crlf('a\r\nb') == 'a\r\nb'


def test_colours_are_truecolor_sgr():
    assert WebTerminal.color_rgb(1, 2, 3) == '\x1b[38;2;1;2;3m'
    assert WebTerminal.on_color_rgb(1, 2, 3) == '\x1b[48;2;1;2;3m'


def test_move_yx_is_one_based():
    # blessed takes 0-based coordinates; the escape sequence is 1-based.
    assert WebTerminal.move_yx(0, 0) == '\x1b[1;1H'


def test_length_ignores_escape_sequences():
    assert WebTerminal.length('\x1b[38;2;1;2;3mab\x1b[0m') == 2


def test_length_counts_double_width_glyphs_as_two():
    pytest.importorskip('wcwidth')
    assert WebTerminal.length('漢') == 2


# ── The porting surface ───────────────────────────────────────────────────────

class _IO:
    def __init__(self, reads):
        self.reads  = list(reads)
        self.writes = []

    def read(self, timeout=None):
        return self.reads.pop(0) if self.reads else ''

    def write(self, text):
        self.writes.append(text)

    def size(self):
        return (24, 80)


def test_inkey_serves_a_batch_one_key_at_a_time():
    term = WebTerminal(_IO(['abc']))
    assert [str(term.inkey()) for _ in range(3)] == ['a', 'b', 'c']


def test_inkey_returns_an_empty_keystroke_on_timeout():
    term = WebTerminal(_IO([]))
    key = term.inkey(timeout=0.1)
    assert key == ''
    assert not key.name
    assert isinstance(key, Keystroke)


def test_fullscreen_turns_off_auto_wrap_and_puts_it_back():
    io = _IO([])
    term = WebTerminal(io)
    with term.fullscreen():
        pass
    assert io.writes[0] == '\x1b[?1049h\x1b[?7l'
    assert io.writes[1] == '\x1b[?7h\x1b[?1049l'


def test_size_comes_from_the_host():
    term = WebTerminal(_IO([]))
    assert (term.height, term.width) == (24, 80)


# ── The real game, through the shim ───────────────────────────────────────────

def test_the_game_runs_on_the_shim():
    """Play a level with a scripted io and check the frames are a real game.

    A subprocess because `install()` replaces `blessed` in `sys.modules` and
    `vimny.game` binds `Terminal` at import: the swap only works in a process
    where nothing has imported the real blessed yet. The browser always has one.
    """
    env = {**os.environ, 'PYTHONPATH': str(ROOT)}   # a script only gets its own dir
    proc = subprocess.run(
        [sys.executable, str(ROOT / 'tests' / '_web_smoke.py')],
        capture_output=True, text=True, timeout=180, cwd=str(ROOT), env=env,
    )
    assert proc.returncode == 0, proc.stderr[-2000:]
    report = json.loads(proc.stdout.strip().splitlines()[-1])

    assert report['frames'] > 5,      'the game barely drew anything'
    assert report['distinct'] > 3,    'frames never changed — input did not land'
    assert report['has_altscreen'],   'never switched to the alternate screen'
    assert report['has_truecolor'],   'no colour reached the host'
    assert report['has_box'],         'no frame border'
    assert report['has_player'],      'the player was not drawn'
    assert report['has_title'],       'the level name never appeared'
    assert report['has_hint'],        'the hint bar never appeared'
