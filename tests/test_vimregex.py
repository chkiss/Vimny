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

"""Blocks B–F — Vim-magic regex translation (vimny/engine/vimregex.py) and its use
in vimny/engine/search.py. Verifies the atoms the scrolls teach, plus backward
compatibility: a plain word still behaves like a literal substring search."""
from vimny.engine.vimregex import compile_vim
from vimny.engine.search import _match_positions, find_next, match_cells
from vimny.engine.world import Room, CharRun, RoomType, CellType


def _first(pattern, s):
    """First effective match span of `pattern` in `s`, or None."""
    vp = compile_vim(pattern)
    assert vp is not None, f'pattern failed to compile: {pattern!r}'
    return vp.first_in(s)


# ── character classes ──────────────────────────────────────────────────────
def test_class_w_d_s():
    assert _first(r'\d', 'ab3cd') == (2, 3)
    assert _first(r'\w', '  x') == (2, 3)
    assert _first(r'\s', 'ab cd') == (2, 3)
    assert _first(r'\a', '12ab') == (2, 3)
    assert _first(r'\u', 'abAB') == (2, 3)
    assert _first(r'\l', 'ABab') == (2, 3)

def test_negated_classes():
    assert _first(r'\D', '123x') == (3, 4)
    assert _first(r'\S', '   y') == (3, 4)


# ── anchors & boundaries ───────────────────────────────────────────────────
def test_anchors():
    assert _first('^ab', 'abc') == (0, 2)
    assert _first('^ab', 'xabc') is None
    assert _first('c$', 'abc') == (2, 3)

def test_word_boundary():
    # \< start of word: 'cat' inside 'cat cathedral' — first standalone start
    assert _first(r'\<cat', 'a cat') == (2, 5)


# ── quantifiers ────────────────────────────────────────────────────────────
def test_quantifiers():
    assert _first(r'ab\+', 'abbbc') == (0, 4)
    assert _first(r'ab\?c', 'ac') == (0, 2)
    assert _first(r'a\{2,3}', 'baaaa') == (1, 4)        # greedy, up to 3
    assert _first('xy*z', 'xz') == (0, 2)               # bare * = 0+

def test_dot():
    assert _first('a.c', 'axc') == (0, 3)
    assert _first(r'a\.c', 'axc') is None               # escaped dot is literal
    assert _first(r'a\.c', 'a.c') == (0, 3)


# ── collections & alternation ──────────────────────────────────────────────
def test_collection():
    assert _first('[xyz]', 'abq z') == (4, 5)
    assert _first('[^abc]', 'aabx') == (3, 4)
    assert _first('[0-9]', 'ab7') == (2, 3)

def test_alternation_and_group():
    assert _first(r'cat\|dog', 'a dog') == (2, 5)
    assert _first(r'\(ab\)\+', 'zababq') == (1, 5)


# ── \zs / \ze shift the effective match ────────────────────────────────────
def test_zs_ze():
    # match 'foobar' but land on / cover only 'bar'
    assert _first(r'foo\zsbar', 'xfoobar') == (4, 7)
    # \ze ends the match early: cover only 'foo'
    assert _first(r'foo\zebar', 'foobar') == (0, 3)


# ── magic levels & case ────────────────────────────────────────────────────
def test_very_magic():
    assert _first(r'\v(ab)+', 'zabab') == (1, 5)
    assert _first(r'\va+', 'baaa') == (1, 4)

def test_case_flags():
    assert _first(r'\cABC', 'xabc') == (1, 4)           # \c → case-insensitive
    assert _first(r'ABC', 'xabc') is None               # default case-sensitive


# ── backward compatibility: plain words = literal substring ────────────────
def test_plain_word_is_literal():
    assert _first('ab', 'xxabxx') == (2, 4)
    # in magic mode a bare '(' is literal, so it still compiles
    assert _first('(', 'a(b') == (1, 2)
    # an unbalanced group in very-magic fails → None → caller uses literal fallback
    assert compile_vim(r'\v(') is None


# ── integration with the grid matcher ──────────────────────────────────────
def _room_with(runs):
    room = Room(room_type=RoomType.ENTRY, rows=10, cols=40)
    # All-floor grid: search landings are passable-filtered (a match starting
    # on an impassable cell is not a landing), so the scaffold needs real cells.
    room.cells = [[CellType.FLOOR] * 40 for _ in range(10)]
    for (r, c, text) in runs:
        room.add_char_run(CharRun(r, c, tuple(text), 'ancient'))
    room.rebuild_indexes()
    return room


class _P:
    def __init__(self, r, c): self.row, self.col = r, c


def test_match_positions_regex():
    room = _room_with([(3, 2, 'foo7'), (5, 4, 'bar')])
    # \d lands on the digit in 'foo7' at col 2+3 = 5
    assert _match_positions(room, r'\d') == [(3, 5)]

def test_find_next_regex_wraps():
    room = _room_with([(3, 0, 'a1'), (3, 5, 'b2')])
    assert find_next(room, _P(3, 0), r'\d', True) == (3, 1)
    assert find_next(room, _P(3, 1), r'\d', True) == (3, 6)
    assert find_next(room, _P(3, 6), r'\d', True) == (3, 1)   # wrap

def test_match_cells_regex():
    room = _room_with([(3, 2, 'a1b2')])
    # \d highlights both digit cells: cols 3 and 5
    assert match_cells(room, r'\d') == {(3, 3), (3, 5)}
