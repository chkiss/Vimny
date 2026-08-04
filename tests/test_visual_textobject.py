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

"""Visual-mode text objects: `v` then `iw`/`aw`/`i(`/`a"`/… selects the object span
(staying in visual mode), exactly like Vim — `i`/`a` are object prefixes, not
insert/append.  Parser-level tests for parse_visual_textobj, plus an integration
test driving the real run_dungeon loop for `viw`."""
import pytest
from blessed.keyboard import Keystroke
from blessed import Terminal

import main
from vimny.engine.vim_parser import parse_visual_textobj as pv
from vimny.engine.world import Dungeon, Room, RoomType, CellType, CharRun
from vimny.engine.modes import Mode


# ── parser: [count](i|a)(obj), with alias normalisation ──────────────────────────
@pytest.mark.parametrize('buf,expected', [
    # 4th element = count_given (was an explicit count typed?) — for the keystroke cost.
    ('iw', ('object', 'iw', 1, False)),
    ('aw', ('object', 'aw', 1, False)),
    ('i(', ('object', 'i(', 1, False)),
    ('ib', ('object', 'i(', 1, False)),     # alias ib -> i(
    ('i)', ('object', 'i(', 1, False)),     # alias i) -> i(
    ('iB', ('object', 'i{', 1, False)),     # alias iB -> i{
    ('i]', ('object', 'i[', 1, False)),     # alias i] -> i[
    ('a"', ('object', 'a"', 1, False)),
    ('2iw', ('object', 'iw', 2, True)),     # count kept (cost), object resolved singly
])
def test_complete_objects(buf, expected):
    assert pv(buf) == expected


@pytest.mark.parametrize('buf', ['i', 'a', '2i', '9a'])
def test_pending_prefixes(buf):
    assert pv(buf) == 'pending'


@pytest.mark.parametrize('buf', ['', '2', 'w', 'gg', '2j', 'd', '$'])
def test_not_a_text_object(buf):
    assert pv(buf) is None


# ── integration: v · iw selects the word under the cursor ────────────────────────
def _ks(ch, name=None):
    return Keystroke(ch, name=name)


def _word_dungeon():
    room = Room(rows=5, cols=20, room_type=RoomType.ENTRY)
    room.cells = [[CellType.WALL] * 20 for _ in range(5)]
    for c in range(1, 19):
        room.cells[2][c] = CellType.CORRIDOR
    room.spawn_pos = (2, 12)                       # inside the word (cols 10-15)
    room.exit_pos  = (2, 18)
    room.char_runs = [CharRun(row=2, col=10, symbols=tuple('cipher'), kind='ember')]
    room.par, room.budget, room.answer = 10, 40, ''
    room.rebuild_indexes()
    d = Dungeon(name='Test', seed=1)
    d.rooms, d.current_room = [room], 0
    return d


def test_viw_selects_the_word(monkeypatch):
    snaps = []
    monkeypatch.setattr(main, 'render_all',
                        lambda term, d, p, b, *a, **k: snaps.append((p.mode, (p.row, p.col), p.visual_anchor)))
    term = Terminal()
    script = [_ks('v'), _ks('i'), _ks('w'),
              _ks('\x1b', name='KEY_ESCAPE'), _ks(':'), _ks('q'), _ks('\r')]
    it = iter(script)
    monkeypatch.setattr(term, 'inkey', lambda *a, **k: next(it, _ks('')))

    main.run_dungeon(term, 'dummy', {}, player_name='admin', _dungeon=_word_dungeon())

    # `iw` from inside the word: selection spans the whole word, anchor on its first
    # cell (col 10), cursor on its last (col 15) — still in visual mode.
    assert (Mode.VISUAL, (2, 15), (2, 10)) in snaps
