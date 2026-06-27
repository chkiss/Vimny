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

"""Tests for Block D2 — engine/visual.py: selection span, highlight membership,
and operator application (charwise / linewise / block)."""
from engine.world import Room, RoomType, CellType, CharRun
from engine.player import Player
from engine.modes import Mode
from engine.text_object import TextObjectType
from engine.visual import visual_span, in_selection, apply_visual

ROWS, COLS = 7, 24


def _room():
    room = Room(room_type=RoomType.ENTRY, rows=ROWS, cols=COLS)
    room.cells = [
        [CellType.FLOOR if (0 < r < ROWS - 1 and 0 < c < COLS - 1) else CellType.WALL
         for c in range(COLS)]
        for r in range(ROWS)
    ]
    room.rebuild_indexes()
    return room


def _cell(room, r, c):
    ru = room.char_run_at(r, c)
    return ru.symbols[c - ru.col] if ru else None


class TestSpan:
    def test_charwise_single_row_inclusive(self):
        room = _room()
        t = visual_span((3, 3), (3, 6), Mode.VISUAL, room)
        assert t.type is TextObjectType.INCLUSIVE
        assert (t.start_row, t.start_col, t.end_row, t.end_col) == (3, 3, 3, 6)

    def test_charwise_orders_endpoints(self):
        room = _room()
        t = visual_span((3, 6), (3, 3), Mode.VISUAL, room)
        assert (t.start_col, t.end_col) == (3, 6)

    def test_linewise(self):
        room = _room()
        t = visual_span((2, 5), (4, 1), Mode.VISUAL_LINE, room)
        assert t.type is TextObjectType.LINEWISE
        assert (t.start_row, t.end_row) == (2, 4)

    def test_multirow_charwise_still_linewise_for_indent(self):
        # visual_span still returns LINEWISE for multi-row (used by >/<)
        room = _room()
        t = visual_span((2, 5), (4, 1), Mode.VISUAL, room)
        assert t.type is TextObjectType.LINEWISE


class TestInSelection:
    def test_charwise_col_span(self):
        assert in_selection((3, 2), (3, 5), Mode.VISUAL, 3, 4) is True
        assert in_selection((3, 2), (3, 5), Mode.VISUAL, 3, 6) is False
        assert in_selection((3, 2), (3, 5), Mode.VISUAL, 4, 4) is False

    def test_linewise_whole_rows(self):
        assert in_selection((2, 9), (4, 0), Mode.VISUAL_LINE, 3, 0) is True
        assert in_selection((2, 9), (4, 0), Mode.VISUAL_LINE, 5, 0) is False

    def test_block_rectangle(self):
        assert in_selection((2, 2), (4, 5), Mode.VISUAL_BLOCK, 3, 4) is True
        assert in_selection((2, 2), (4, 5), Mode.VISUAL_BLOCK, 3, 6) is False

    def test_no_anchor(self):
        assert in_selection(None, (3, 3), Mode.VISUAL, 3, 3) is False

    def test_charwise_multirow_partial_rows(self):
        # anchor=(2,3) cursor=(4,7): top row starts at col 3, bottom ends at col 7
        assert in_selection((2, 3), (4, 7), Mode.VISUAL, 2, 2) is False  # before anchor col
        assert in_selection((2, 3), (4, 7), Mode.VISUAL, 2, 3) is True   # at anchor col
        assert in_selection((2, 3), (4, 7), Mode.VISUAL, 2, 9) is True   # past anchor col
        assert in_selection((2, 3), (4, 7), Mode.VISUAL, 3, 0) is True   # middle row: any col
        assert in_selection((2, 3), (4, 7), Mode.VISUAL, 4, 7) is True   # at cursor col
        assert in_selection((2, 3), (4, 7), Mode.VISUAL, 4, 8) is False  # past cursor col

    def test_charwise_multirow_reversed(self):
        # cursor above anchor: same logic, just swapped
        assert in_selection((4, 7), (2, 3), Mode.VISUAL, 2, 2) is False
        assert in_selection((4, 7), (2, 3), Mode.VISUAL, 2, 3) is True
        assert in_selection((4, 7), (2, 3), Mode.VISUAL, 4, 7) is True
        assert in_selection((4, 7), (2, 3), Mode.VISUAL, 4, 8) is False


class TestApplyVisual:
    def test_charwise_delete(self):
        room = _room()
        room.add_char_run(CharRun(3, 2, ('a', 'b', 'c', 'd', 'e'), 'ancient'))
        p = Player(row=3, col=5)
        apply_visual('d', (3, 3), (3, 5), Mode.VISUAL, room, p)   # delete b,c,d
        assert _cell(room, 3, 2) == 'a' and _cell(room, 3, 3) == 'e'   # gap closed: e pulled left
        assert all(room.char_run_at(3, c) is None for c in (4, 5, 6))
        assert p.col == 3                                          # cursor to start

    def test_charwise_yank_no_mutation(self):
        room = _room()
        room.add_char_run(CharRun(3, 2, ('a', 'b', 'c'), 'ancient'))
        p = Player(row=3, col=4)
        clip = apply_visual('y', (3, 2), (3, 4), Mode.VISUAL, room, p)
        assert _cell(room, 3, 2) == 'a'                            # unchanged
        assert clip['rows'][0]['char_runs'][0]['symbols'] == ('a', 'b', 'c')
        assert (p.row, p.col) == (3, 2)

    def test_linewise_delete_clears_rows(self):
        room = _room()
        room.add_char_run(CharRun(2, 3, ('x',), 'ancient'))
        room.add_char_run(CharRun(3, 5, ('y',), 'ancient'))
        p = Player(row=2, col=0)
        apply_visual('d', (2, 0), (3, 0), Mode.VISUAL_LINE, room, p)
        assert room.char_run_at(2, 3) is None and room.char_run_at(3, 5) is None

    def test_visual_case_toggle(self):
        room = _room()
        room.add_char_run(CharRun(3, 2, ('a', 'B', 'c'), 'ancient'))
        p = Player(row=3, col=4)
        apply_visual('g~', (3, 2), (3, 4), Mode.VISUAL, room, p)
        assert (_cell(room, 3, 2), _cell(room, 3, 3), _cell(room, 3, 4)) == ('A', 'b', 'C')

    def test_charwise_multirow_delete_partial_rows(self):
        # anchor=(2,3) cursor=(4,5): top row deletes cols 3+, bottom row deletes up to col 5
        room = _room()
        room.add_char_run(CharRun(2, 1, ('a', 'b', 'c', 'd', 'e'), 'ancient'))  # cols 1-5
        room.add_char_run(CharRun(3, 1, ('f', 'g', 'h'), 'ancient'))             # cols 1-3
        room.add_char_run(CharRun(4, 1, ('i', 'j', 'k', 'l', 'm'), 'ancient'))  # cols 1-5
        p = Player(row=2, col=3)
        apply_visual('d', (2, 3), (4, 5), Mode.VISUAL, room, p)
        # row 2: cols 1-2 kept (a,b), cols 3-5 deleted (c,d,e)
        assert _cell(room, 2, 1) == 'a' and _cell(room, 2, 2) == 'b'
        assert all(room.char_run_at(2, c) is None for c in (3, 4, 5))
        # row 3: whole passable extent deleted
        assert all(room.char_run_at(3, c) is None for c in (1, 2, 3))
        # row 4: cols 1-5 deleted (up to cursor col 5)
        assert all(room.char_run_at(4, c) is None for c in (1, 2, 3, 4, 5))
        assert p.row == 2 and p.col == 3

    def test_charwise_multirow_top_row_not_col_zero(self):
        # anchor col must be respected — col 0 on top row NOT deleted
        room = _room()
        room.add_char_run(CharRun(2, 1, ('x', 'y', 'z'), 'ancient'))  # cols 1-3
        room.add_char_run(CharRun(3, 1, ('a', 'b', 'c'), 'ancient'))  # cols 1-3
        p = Player(row=2, col=2)
        apply_visual('d', (2, 2), (3, 3), Mode.VISUAL, room, p)
        # row 2 col 1 ('x') is BEFORE anchor col 2 — must survive
        assert _cell(room, 2, 1) == 'x'
        assert room.char_run_at(2, 2) is None and room.char_run_at(2, 3) is None

    def test_block_delete_rectangle(self):
        room = _room()
        room.add_char_run(CharRun(2, 2, ('a', 'b', 'c'), 'ancient'))
        room.add_char_run(CharRun(3, 2, ('d', 'e', 'f'), 'ancient'))
        p = Player(row=2, col=2)
        apply_visual('d', (2, 3), (3, 4), Mode.VISUAL_BLOCK, room, p)   # cols 3-4 on rows 2-3
        assert _cell(room, 2, 2) == 'a' and _cell(room, 3, 2) == 'd'    # col 2 kept
        assert all(room.char_run_at(r, c) is None for r in (2, 3) for c in (3, 4))
        assert (p.row, p.col) == (2, 3)

    def test_block_indent_shifts_spanned_lines(self):
        # Block > indents every line the block spans (whole lines, like Vim).
        room = _room()
        room.add_char_run(CharRun(2, 3, ('a', 'b'), 'ancient'))
        room.add_char_run(CharRun(3, 3, ('c', 'd'), 'ancient'))
        room.add_char_run(CharRun(4, 3, ('e', 'f'), 'ancient'))         # outside the block
        p = Player(row=2, col=3)
        clip = apply_visual('>', (2, 3), (3, 4), Mode.VISUAL_BLOCK, room, p)
        assert clip is None                                             # indent yields no register clip
        assert _cell(room, 2, 5) == 'a' and _cell(room, 3, 5) == 'c'    # shifted by shiftwidth (2)
        assert _cell(room, 4, 3) == 'e'                                 # row below the block untouched
        assert p.row == 2

    def test_block_dedent_clamps_at_wall(self):
        room = _room()
        room.add_char_run(CharRun(2, 2, ('a', 'b'), 'ancient'))         # 1 col off the left wall
        p = Player(row=2, col=2)
        apply_visual('<', (2, 2), (2, 3), Mode.VISUAL_BLOCK, room, p)
        assert _cell(room, 2, 1) == 'a'                                 # pulled to the wall, not past it
