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

"""Tests for Block A (vimny/engine/text_object.py) and Block B (vimny/engine/operator.py):
the delete/yank operator system over the 2D grid, including the rule that
linewise yank/delete includes the spaces between runes (bounded by walls)."""
import pytest
from vimny.engine.world import Room, RoomType, CellType, CharRun
from vimny.engine.player import Player
from vimny.engine.text_object import (
    TextObject, TextObjectType, classify, compute_text_object,
)
from vimny.engine.operator import (
    line_extent, op_yank, op_delete, op_paste, op_case, op_join, case_char,
    apply_indent, INDENT_WIDTH,
)


def _sym(room, row, col):
    """The single symbol at (row, col), independent of cluster merging."""
    ru = room.char_run_at(row, col)
    return ru.symbols[col - ru.col] if ru else None

ROWS, COLS = 7, 24


def _room():
    room = Room(room_type=RoomType.ENTRY, rows=ROWS, cols=COLS)
    room.cells = [
        [CellType.FLOOR if (0 < r < ROWS - 1 and 0 < c < COLS - 1) else CellType.WALL
         for c in range(COLS)]
        for r in range(ROWS)
    ]
    room.spawn_pos    = (1, 1)
    room.exit_pos = (3, 20)
    room.rebuild_indexes()
    return room


def _player(row=3, col=1):
    return Player(row=row, col=col)


# ── Block A: classification ──────────────────────────────────────────────────

class TestClassify:
    @pytest.mark.parametrize("m", ['e', 'E', '$', 'f', 'F', 't', 'T', '%'])
    def test_inclusive(self, m):
        assert classify(m) is TextObjectType.INCLUSIVE

    @pytest.mark.parametrize("m", ['line', 'j', 'k', 'G', 'gg'])
    def test_linewise(self, m):
        assert classify(m) is TextObjectType.LINEWISE

    @pytest.mark.parametrize("m", ['h', 'l', 'w', 'b', 'W', 'B', '0', '^', 'ge', '{', ')'])
    def test_exclusive(self, m):
        assert classify(m) is TextObjectType.EXCLUSIVE


# ── Block A: compute_text_object ─────────────────────────────────────────────

class TestComputeTextObject:
    def test_dw_exclusive_span(self):
        room = _room()
        room.add_char_run(CharRun(3, 2, ('a',), 'ancient'))
        room.add_char_run(CharRun(3, 6, ('b',), 'ancient'))
        p = _player(3, 2)
        t = compute_text_object(p, {'op': 'd', 'motion': 'w', 'count': 1, 'motion_count': 1}, room)
        assert t.type is TextObjectType.EXCLUSIVE
        assert (t.start_col, t.end_col) == (2, 6)   # cursor → next word start
        assert (p.row, p.col) == (3, 2)             # player not moved

    def test_de_inclusive_span(self):
        room = _room()
        room.add_char_run(CharRun(3, 2, ('a', 'b', 'c'), 'ancient'))
        p = _player(3, 2)
        t = compute_text_object(p, {'op': 'd', 'motion': 'e', 'count': 1, 'motion_count': 1}, room)
        assert t.type is TextObjectType.INCLUSIVE
        assert (t.start_col, t.end_col) == (2, 4)

    def test_dd_linewise_single_row(self):
        room = _room()
        p = _player(3, 5)
        t = compute_text_object(p, {'op': 'd', 'motion': 'line', 'count': 1}, room)
        assert t.type is TextObjectType.LINEWISE
        assert (t.start_row, t.end_row) == (3, 3)

    def test_count_dd_spans_rows(self):
        room = _room()
        p = _player(2, 5)
        t = compute_text_object(p, {'op': 'd', 'motion': 'line', 'count': 3}, room)
        assert (t.start_row, t.end_row) == (2, 4)

    def test_dj_linewise_two_rows(self):
        room = _room()
        p = _player(2, 5)
        t = compute_text_object(p, {'op': 'd', 'motion': 'j', 'count': 1, 'motion_count': 1}, room)
        assert t.type is TextObjectType.LINEWISE
        assert (t.start_row, t.end_row) == (2, 3)

    def test_motion_that_cannot_move_returns_none(self):
        room = _room()
        p = _player(3, 1)   # at left wall edge; 'h' cannot move
        t = compute_text_object(p, {'op': 'd', 'motion': 'h', 'count': 1, 'motion_count': 1}, room)
        assert t is None


# ── Block B: delete ──────────────────────────────────────────────────────────

class TestDelete:
    def test_dw_closes_the_gap_pulling_next_word_left(self):
        room = _room()
        room.add_char_run(CharRun(3, 2, ('a',), 'ancient'))   # word A
        room.add_char_run(CharRun(3, 6, ('b',), 'ancient'))   # word B
        p = _player(3, 2)
        t = compute_text_object(p, {'op': 'd', 'motion': 'w', 'count': 1, 'motion_count': 1}, room)
        op_delete(room, p, t)
        assert room.char_run_at(3, 2).symbols == ('b',)   # gap closed: B pulled to the deletion start
        assert room.char_run_at(3, 6) is None              # B no longer trails
        assert p.col == 2                                  # cursor at start of deletion

    def test_de_closes_the_gap(self):
        room = _room()
        room.add_char_run(CharRun(3, 2, ('a', 'b', 'c'), 'ancient'))
        room.add_char_run(CharRun(3, 8, ('d',), 'ancient'))
        p = _player(3, 2)
        t = compute_text_object(p, {'op': 'd', 'motion': 'e', 'count': 1, 'motion_count': 1}, room)
        op_delete(room, p, t)
        assert room.char_run_at(3, 5).symbols == ('d',)   # 'abc' gone; 'd' pulled left by 3 (8→5)
        assert room.char_run_at(3, 8) is None

    def test_linewise_delete_without_collapse_clears_in_place(self):
        # op_delete(collapse=False) is the cc / S path: runes go, the row stays.
        room = _room()
        room.add_char_run(CharRun(3, 2, ('a',), 'ancient'))
        room.add_char_run(CharRun(3, 6, ('b',), 'ancient'))
        p = _player(3, 5)
        before = room.rows
        t = compute_text_object(p, {'op': 'd', 'motion': 'line', 'count': 1}, room)
        op_delete(room, p, t)
        assert room.rows == before                                  # row kept
        assert room.char_run_at(3, 2) is None and room.char_run_at(3, 6) is None
        assert p.row == 3

    def test_dd_collapses_row(self):
        # op_delete(collapse=True) is real dd / visual-line d: the row is removed
        # and the row below pulled up — the vertical inverse of o.
        room = _room()
        room.add_char_run(CharRun(2, 4, ('a',), 'ancient'))   # the row dd removes
        room.add_char_run(CharRun(3, 7, ('Z',), 'ancient'))   # the row below it
        p = _player(2, 5)
        before = room.rows
        t = compute_text_object(p, {'op': 'd', 'motion': 'line', 'count': 1}, room)
        op_delete(room, p, t, collapse=True)
        assert room.rows == before - 1                        # collapsed, not cleared
        assert room.char_run_at(2, 4) is None                 # old row-2 content gone
        assert room.char_run_at(2, 7).symbols == ('Z',)       # row 3 pulled up into row 2
        assert p.row == 2

    def test_delete_closes_a_cluster_gap(self):
        room = _room()
        room.add_char_run(CharRun(3, 2, ('a', 'b', 'c', 'd'), 'ancient'))
        p = _player(3, 3)
        # delete cols [3,3] only (exclusive l from col3 → dest col4 → [3,3])
        t = TextObject(3, 3, 3, 4, TextObjectType.EXCLUSIVE)
        op_delete(room, p, t)
        assert room.char_run_at(3, 2).symbols == ('a', 'c', 'd')   # 'b' gone, 'cd' pulled left into 'acd'
        assert room.char_run_at(3, 5) is None


# ── Block B: yank preserves spacing, paste reproduces it ─────────────────────

class TestYankSpacing:
    def test_line_extent_between_walls(self):
        room = _room()
        assert line_extent(room, 3) == (1, COLS - 2)   # cols 1..22

    def test_yy_captures_full_line_including_gaps(self):
        room = _room()
        room.add_char_run(CharRun(3, 2, ('a',), 'ancient'))
        room.add_char_run(CharRun(3, 6, ('b',), 'ancient'))
        p = _player(3, 1)
        t = compute_text_object(p, {'op': 'y', 'motion': 'line', 'count': 1}, room)
        clip = op_yank(room, p, t)
        assert clip['linewise'] is True
        runes = clip['rows'][0]['char_runs']
        # offsets relative to line start (col 1): A at 1, B at 5 → 3-cell gap kept
        assert [(r['dcol'], r['symbols']) for r in runes] == [(1, ('a',)), (5, ('b',))]

    def test_linewise_paste_preserves_spacing(self):
        room = _room()
        room.add_char_run(CharRun(3, 2, ('a',), 'ancient'))
        room.add_char_run(CharRun(3, 6, ('b',), 'ancient'))
        p = _player(3, 1)
        clip = op_yank(room, p, compute_text_object(p, {'op': 'y', 'motion': 'line', 'count': 1}, room))
        p.row, p.col = 4, 1
        op_paste(room, p, clip, before=True)        # P → insert a real line at row 4
        assert room.char_run_at(4, 2) is not None        # A back at col 2
        assert room.char_run_at(4, 6) is not None        # B back at col 6
        assert all(room.char_run_at(4, c) is None for c in (3, 4, 5))   # gap survived

    def test_charwise_paste_preserves_relative_gap(self):
        room = _room()
        clip = {'linewise': False,
                'rows': [{'width': 5, 'char_runs': [{'dcol': 0, 'symbols': ('a',), 'kind': 'ancient'},
                                                {'dcol': 4, 'symbols': ('b',), 'kind': 'ancient'}]}]}
        p = _player(3, 10)
        op_paste(room, p, clip, before=False)        # p → start at col 11
        assert room.char_run_at(3, 11) is not None
        assert room.char_run_at(3, 15) is not None
        assert all(room.char_run_at(3, c) is None for c in (12, 13, 14))
        assert p.col == 15                            # cursor on the last pasted cell (Vim)

    def test_paste_stops_at_wall(self):
        room = _room()
        clip = {'linewise': False,
                'rows': [{'width': 5, 'char_runs': [{'dcol': 0, 'symbols': ('a', 'b', 'c'), 'kind': 'ancient'}]}]}
        p = _player(3, 21)        # cols 22 is last floor; 23 is wall
        op_paste(room, p, clip, before=False)        # start col 22: only 1 cell fits
        assert room.char_run_at(3, 22) is not None
        assert room.char_run_at(3, 23) is None            # wall, not written


def _op(op, motion, **kw):
    d = {'op': op, 'motion': motion, 'count': kw.get('count', 1),
         'motion_count': kw.get('motion_count', 1),
         'motion_count_given': kw.get('motion_count_given', 'motion_count' in kw)}
    if 'target' in kw:
        d['target'] = kw['target']
    return d


# ── Block A: compute_text_object — backward, inclusive-backward, edges, counts ──

class TestComputeTextObjectMore:
    def test_db_backward_span_orders_low_to_high(self):
        room = _room()
        room.add_char_run(CharRun(3, 2, ('a',), 'ancient'))
        room.add_char_run(CharRun(3, 6, ('b',), 'ancient'))
        p = _player(3, 6)                       # on B
        t = compute_text_object(p, _op('d', 'b'), room)
        assert t.type is TextObjectType.EXCLUSIVE
        assert (t.start_col, t.end_col) == (2, 6)   # sorted(cursor=6, dest=2)

    def test_dF_inclusive_backward(self):
        room = _room()
        room.add_char_run(CharRun(3, 4, (';',), 'ancient'))
        p = _player(3, 10)
        t = compute_text_object(p, _op('d', 'F', target=';'), room)
        assert t.type is TextObjectType.INCLUSIVE
        assert (t.start_col, t.end_col) == (4, 10)

    def test_d_dollar_inclusive_to_eol(self):
        room = _room()
        p = _player(3, 5)
        t = compute_text_object(p, _op('d', '$'), room)
        assert t.type is TextObjectType.INCLUSIVE
        assert (t.start_col, t.end_col) == (5, COLS - 2)   # rightmost passable

    def test_dG_linewise_to_last_row(self):
        # bare dG → linewise from cursor row to last passable row (row 5 in a 7-row room)
        room = _room()
        p = _player(1, 5)
        t = compute_text_object(p, _op('d', 'G'), room)
        assert t.type is TextObjectType.LINEWISE
        assert (t.start_row, t.end_row) == (1, ROWS - 2)

    def test_dgg_linewise_to_entry_row(self):
        room = _room()                          # entry row is 1
        p = _player(4, 5)
        t = compute_text_object(p, _op('d', 'gg'), room)
        assert (t.start_row, t.end_row) == (1, 4)

    def test_dk_linewise_upward(self):
        room = _room()
        p = _player(3, 5)
        t = compute_text_object(p, _op('d', 'k'), room)
        assert (t.start_row, t.end_row) == (2, 3)

    def test_operator_count_multiplies_motion(self):
        room = _room()
        for c in (2, 6, 10, 14):
            room.add_char_run(CharRun(3, c, ('x',), 'ancient'))
        p = _player(3, 2)
        t = compute_text_object(p, _op('d', 'w', count=2), room)   # 2dw → 2 words forward
        assert t.end_col == 10
        p = _player(3, 2)
        t = compute_text_object(p, _op('d', 'w', motion_count=3), room)  # d3w
        assert t.end_col == 14

    def test_df_inclusive_with_target(self):
        room = _room()
        room.add_char_run(CharRun(3, 8, (';',), 'ancient'))
        p = _player(3, 2)
        t = compute_text_object(p, _op('d', 'f', target=';'), room)
        assert t.type is TextObjectType.INCLUSIVE
        assert (t.start_col, t.end_col) == (2, 8)


# ── Block B: yank non-mutation, backward/linewise delete cursor, paste edges ───

class TestYankNonMutation:
    def test_yank_does_not_change_room_or_cursor(self):
        room = _room()
        room.add_char_run(CharRun(3, 2, ('a', 'b', 'c'), 'ancient'))
        p = _player(3, 2)
        t = compute_text_object(p, _op('y', 'e'), room)
        clip = op_yank(room, p, t)
        assert room.char_run_at(3, 2) is not None and room.char_run_at(3, 4) is not None
        assert (p.row, p.col) == (3, 2)
        assert clip['rows'][0]['char_runs'][0]['symbols'] == ('a', 'b', 'c')


class TestDeleteMore:
    def test_db_closes_the_gap_cursor_to_start(self):
        room = _room()
        room.add_char_run(CharRun(3, 2, ('a',), 'ancient'))
        room.add_char_run(CharRun(3, 6, ('b',), 'ancient'))
        p = _player(3, 6)
        op_delete(room, p, compute_text_object(p, _op('d', 'b'), room))
        assert room.char_run_at(3, 2).symbols == ('b',)   # 'a' + gap gone; 'b' pulled to the start
        assert room.char_run_at(3, 6) is None
        assert p.col == 2

    def test_dj_clears_both_rows_and_repositions(self):
        room = _room()
        room.add_char_run(CharRun(2, 3, ('a',), 'ancient'))
        room.add_char_run(CharRun(3, 5, ('b',), 'ancient'))
        p = _player(2, 5)
        op_delete(room, p, compute_text_object(p, _op('d', 'j'), room))
        assert room.char_run_at(2, 3) is None and room.char_run_at(3, 5) is None
        assert p.row == 2 and p.col == 1          # start row, first passable col

    def test_delete_returns_clip_matching_yank(self):
        room = _room()
        room.add_char_run(CharRun(3, 2, ('a', 'b'), 'ancient'))
        p = _player(3, 2)
        clip = op_delete(room, p, _td_inclusive(3, 2, 3))
        assert clip['rows'][0]['char_runs'][0]['symbols'] == ('a', 'b')


class TestPasteMore:
    def test_P_before_inserts_at_cursor_shifting_right(self):
        room = _room()
        room.add_char_run(CharRun(3, 10, ('X',), 'ancient'))   # something under the cursor
        clip = {'linewise': False,
                'rows': [{'width': 1, 'char_runs': [{'dcol': 0, 'symbols': ('a',), 'kind': 'ancient'}]}]}
        p = _player(3, 10)
        op_paste(room, p, clip, before=True)      # P → insert 'a' at the cursor; X shifts right
        assert room.char_run_at(3, 10).symbols == ('a', 'X')   # 'a' inserted at cursor, X shifted right (merged)
        assert p.col == 10                        # cursor on the pasted char

    def test_paste_empty_clip_is_noop(self):
        room = _room()
        p = _player(3, 5)
        assert op_paste(room, p, None, before=False) is False
        empty = {'linewise': False, 'rows': [{'width': 0, 'char_runs': []}]}
        assert op_paste(room, p, empty, before=False) is False

    def test_paste_merges_adjacent_same_kind(self):
        room = _room()
        room.add_char_run(CharRun(3, 5, ('a',), 'ancient'))
        clip = {'linewise': False,
                'rows': [{'width': 1, 'char_runs': [{'dcol': 0, 'symbols': ('b',), 'kind': 'ancient'}]}]}
        p = _player(3, 5)
        op_paste(room, p, clip, before=False)      # places 'b' at col 6, adjacent to 'a'
        merged = room.char_run_at(3, 5)
        assert merged.symbols == ('a', 'b') and merged.col == 5

    def test_linewise_paste_below_with_p_inserts_a_real_row(self):
        room = _room()
        room.add_char_run(CharRun(3, 2, ('a',), 'ancient'))
        room.add_char_run(CharRun(3, 6, ('b',), 'ancient'))
        p = _player(3, 1)
        clip = op_yank(room, p, compute_text_object(p, _op('y', 'line'), room))
        before = room.rows
        op_paste(room, p, clip, before=False)      # p → opens a real new line below (row 4)
        assert room.rows == before + 1             # a row was inserted (Vim-faithful), not overlaid
        assert room.char_run_at(4, 2) is not None and room.char_run_at(4, 6) is not None
        assert (p.row, p.col) == (4, 2)            # cursor → first non-blank of the pasted line

    def test_count_linewise_paste_inserts_rows_and_shifts_map_down(self):
        room = _room()
        room.add_char_run(CharRun(3, 2, ('a',), 'ancient'))     # the line to yank
        room.add_char_run(CharRun(4, 7, ('Z',), 'ancient'))     # content below — must shift down
        p = _player(3, 1)
        clip = op_yank(room, p, compute_text_object(p, _op('y', 'line'), room))
        before = room.rows
        op_paste(room, p, clip, before=False, count=3)          # 3p → 3 new lines below
        assert room.rows == before + 3                          # three real rows inserted
        for r in (4, 5, 6):
            assert room.char_run_at(r, 2) is not None           # 'a' on each pasted line
        assert room.char_run_at(7, 7).symbols == ('Z',)         # old row-4 content pushed down 3


class TestRoundTrip:
    def test_yank_then_paste_reproduces_layout(self):
        room = _room()
        room.add_char_run(CharRun(3, 2, ('x',), 'ancient'))
        room.add_char_run(CharRun(3, 5, ('y', 'z'), 'verdant'))   # gap at 3,4
        p = _player(3, 1)
        clip = op_yank(room, p, compute_text_object(p, _op('y', 'line'), room))
        p.row, p.col = 5, 1
        op_paste(room, p, clip, before=True)        # P → insert a real line at row 5
        assert room.char_run_at(5, 2) is not None        # x at same offset
        assert room.char_run_at(5, 5) is not None        # yz at same offset
        assert all(room.char_run_at(5, c) is None for c in (3, 4))   # gap preserved


def _td_inclusive(row, lo, hi):
    return TextObject(row, lo, row, hi, TextObjectType.INCLUSIVE)


def _syms(room, row, col):
    ru = room.char_run_at(row, col)
    return ''.join(ru.symbols) if ru else None


class TestCaseOperators:
    def test_gU_uppercases_span(self):
        room = _room()
        room.add_char_run(CharRun(3, 2, ('a', 'b', 'c'), 'ancient'))
        p = _player(3, 2)
        op_case(room, p, _td_inclusive(3, 2, 4), 'gU')
        assert _syms(room, 3, 2) == 'ABC'
        assert p.col == 2                          # cursor → span start

    def test_gu_lowercases_span(self):
        room = _room()
        room.add_char_run(CharRun(3, 2, ('A', 'B', 'C'), 'ancient'))
        op_case(room, _player(3, 2), _td_inclusive(3, 2, 4), 'gu')
        assert _syms(room, 3, 2) == 'abc'

    def test_gtilde_swaps_case(self):
        room = _room()
        room.add_char_run(CharRun(3, 2, ('a', 'B', 'c'), 'ancient'))
        op_case(room, _player(3, 2), _td_inclusive(3, 2, 4), 'g~')
        assert _syms(room, 3, 2) == 'AbC'

    def test_gU_partial_span_only(self):
        room = _room()
        room.add_char_run(CharRun(3, 2, ('a', 'b', 'c', 'd'), 'ancient'))
        op_case(room, _player(3, 2), _td_inclusive(3, 2, 3), 'gU')   # only cols 2-3
        assert _syms(room, 3, 2) == 'ABcd'

    def test_gUw_via_compute(self):
        room = _room()
        room.add_char_run(CharRun(3, 2, ('a', 'b', 'c'), 'ancient'))
        room.add_char_run(CharRun(3, 7, ('x',), 'ancient'))
        p = _player(3, 2)
        t = compute_text_object(p, _op('gU', 'w'), room)
        op_case(room, p, t, 'gU')
        assert _syms(room, 3, 2) == 'ABC'

    def test_gUiw_via_textobj(self):
        from vimny.engine.text_object import resolve_text_object
        room = _room()
        room.add_char_run(CharRun(3, 2, ('a', 'b', 'c'), 'ancient'))
        p = _player(3, 3)
        t = resolve_text_object('iw', room, p)
        op_case(room, p, t, 'gU')
        assert _syms(room, 3, 2) == 'ABC'

    def test_gU_linewise(self):
        room = _room()
        room.add_char_run(CharRun(3, 2, ('a',), 'ancient'))
        room.add_char_run(CharRun(3, 8, ('b', 'c'), 'ancient'))
        p = _player(3, 8)
        t = TextObject(3, 0, 3, COLS - 1, TextObjectType.LINEWISE)
        op_case(room, p, t, 'gU')
        assert _syms(room, 3, 2) == 'A' and _syms(room, 3, 8) == 'BC'
        assert p.col == 2                          # Vim-true: first NON-BLANK


class TestIndent:
    def test_indent_right_shifts_clusters(self):
        room = _room()
        room.add_char_run(CharRun(3, 2, ('a', 'b', 'c'), 'ancient'))
        assert apply_indent(room, 3, INDENT_WIDTH) == 2
        assert room.char_run_at(3, 2) is None
        assert _syms(room, 3, 4) == 'abc'              # shifted to cols 4-6

    def test_dedent_left_shifts_clusters(self):
        room = _room()
        room.add_char_run(CharRun(3, 5, ('a', 'b'), 'ancient'))
        apply_indent(room, 3, -INDENT_WIDTH)
        assert _syms(room, 3, 3) == 'ab'

    def test_dedent_clamps_at_first_passable(self):
        room = _room()
        room.add_char_run(CharRun(3, 2, ('a',), 'ancient'))   # leftmost at col 2
        applied = apply_indent(room, 3, -5)                    # would go negative
        assert applied == -1                                    # clamped: 2 → 1
        assert room.char_run_at(3, 1) is not None

    def test_indent_shoves_content_off_the_right_brink(self):
        room = _room()
        room.add_char_run(CharRun(3, 22, ('a',), 'ancient'))   # at the last passable col (wall at 23)
        room._last_void_falls = []
        apply_indent(room, 3, INDENT_WIDTH)                     # `>` pushes it past the brink
        assert room.char_run_at(3, 22) is None                 # 'a' tumbled off the ledge
        assert room._last_void_falls                           # it fell into the void

    def test_indent_drops_only_the_overflow(self):
        room = _room()
        room.add_char_run(CharRun(3, 20, ('a', 'b', 'c'), 'ancient'))  # 20-22; wall at 23
        room._last_void_falls = []
        apply_indent(room, 3, INDENT_WIDTH)                     # >> by 2: a→22, b/c fall off
        assert _sym(room, 3, 22) == 'a'                        # 'a' slid to the brink
        assert room.char_run_at(3, 23) is None                 # nothing past the wall
        assert len(room._last_void_falls) == 2                 # 'b' and 'c' went over

    def test_indent_moves_all_clusters_equally(self):
        room = _room()
        room.add_char_run(CharRun(3, 2, ('a',), 'ancient'))
        room.add_char_run(CharRun(3, 6, ('b',), 'ancient'))
        apply_indent(room, 3, INDENT_WIDTH)
        assert room.char_run_at(3, 4) is not None and room.char_run_at(3, 8) is not None
        assert room.char_run_at(3, 2) is None and room.char_run_at(3, 6) is None

    def test_indent_empty_row_is_noop(self):
        room = _room()
        assert apply_indent(room, 3, INDENT_WIDTH) == 0


class TestTildeToggle:
    def test_tilde_toggles_and_advances(self):
        room = _room()
        room.add_char_run(CharRun(3, 5, ('a',), 'ancient'))
        p = _player(3, 5)
        assert case_char(room, p, 1) is True
        assert _syms(room, 3, 5) == 'A'
        assert p.col == 6

    def test_count_tilde_toggles_run(self):
        room = _room()
        room.add_char_run(CharRun(3, 2, ('a', 'B', 'c'), 'ancient'))
        p = _player(3, 2)
        case_char(room, p, 3)
        assert _syms(room, 3, 2) == 'AbC'
        assert p.col == 5                          # advanced past all three

    def test_tilde_on_blank_just_advances(self):
        room = _room()
        p = _player(3, 5)                          # floor, no rune
        case_char(room, p, 1)
        assert p.col == 6


class TestChangeWordSpecialCase:
    """vim-exact: cw/cW with the cursor in a word change to the word END (like
    ce/cE), excluding trailing whitespace — unlike dw which includes the gap."""
    def _two_words(self):
        room = _room()
        room.add_char_run(CharRun(3, 2, ('a', 'b', 'c'), 'ancient'))   # cols 2-4
        room.add_char_run(CharRun(3, 7, ('d', 'e', 'f'), 'ancient'))   # cols 7-9
        return room

    def test_cw_changes_to_word_end_not_gap(self):
        room = self._two_words()
        p = _player(3, 2)
        t = compute_text_object(p, _op('c', 'w'), room)
        assert t.type is TextObjectType.INCLUSIVE
        assert (t.start_col, t.end_col) == (2, 4)        # word only, no trailing gap

    def test_dw_still_includes_trailing_gap(self):
        room = self._two_words()
        p = _player(3, 2)
        t = compute_text_object(p, _op('d', 'w'), room)
        assert t.type is TextObjectType.EXCLUSIVE
        assert (t.start_col, t.end_col) == (2, 7)        # dw unchanged: through the gap

    def test_cw_from_mid_word(self):
        room = self._two_words()
        p = _player(3, 3)                                 # on 'b'
        t = compute_text_object(p, _op('c', 'w'), room)
        assert (t.start_col, t.end_col) == (3, 4)

    def test_cw_on_last_char_changes_only_it(self):
        room = self._two_words()
        p = _player(3, 4)                                 # on 'c', the word's last char
        t = compute_text_object(p, _op('c', 'w'), room)
        assert (t.start_col, t.end_col) == (4, 4)

    def test_cw_on_blank_behaves_like_dw(self):
        room = self._two_words()
        p = _player(3, 5)                                 # gap between words
        t = compute_text_object(p, _op('c', 'w'), room)
        assert t.type is TextObjectType.EXCLUSIVE         # falls through to dw behaviour
        assert (t.start_col, t.end_col) == (5, 7)

    def test_cW_coalesces_to_WORD_end(self):
        room = _room()
        room.add_char_run(CharRun(3, 2, ('a', 'b'), 'ancient'))   # adjacent → one WORD
        room.add_char_run(CharRun(3, 4, ('c', 'd'), 'verdant'))
        room.add_char_run(CharRun(3, 8, ('e',), 'ancient'))
        p = _player(3, 2)
        t = compute_text_object(p, _op('c', 'W'), room)
        assert (t.start_col, t.end_col) == (2, 5)         # through the coalesced WORD

    def test_c2w_to_end_of_second_word(self):
        room = _room()
        for c in (2, 6, 10):
            room.add_char_run(CharRun(3, c, ('x',), 'ancient'))
        p = _player(3, 2)
        t = compute_text_object(p, _op('c', 'w', count=2), room)
        assert t.type is TextObjectType.INCLUSIVE
        assert (t.start_col, t.end_col) == (2, 6)         # end of 2nd word, no gap


class TestFindOperators:
    """dt/df/dT/dF and ct/cf share one path; df/dF live in TestComputeTextObjectMore."""
    def _cluster(self):
        room = _room()
        room.add_char_run(CharRun(3, 2, ('a', 'b', ';', 'c', 'd'), 'ancient'))   # ; at col 4
        return room

    def test_dt_stops_before_char(self):
        room = self._cluster()
        p = _player(3, 2)
        t = compute_text_object(p, _op('d', 't', target=';'), room)
        assert t.type is TextObjectType.INCLUSIVE
        assert (t.start_col, t.end_col) == (2, 3)         # up to but not incl ';'

    def test_ct_same_span_as_dt(self):
        room = self._cluster()
        p = _player(3, 2)
        t = compute_text_object(p, _op('c', 't', target=';'), room)
        assert (t.start_col, t.end_col) == (2, 3)

    def test_cf_through_char(self):
        room = self._cluster()
        p = _player(3, 2)
        t = compute_text_object(p, _op('c', 'f', target=';'), room)
        assert (t.start_col, t.end_col) == (2, 4)         # includes ';'

    def test_dt_then_delete_closes_the_prefix_gap(self):
        room = self._cluster()
        p = _player(3, 2)
        op_delete(room, p, compute_text_object(p, _op('d', 't', target=';'), room))
        assert room.char_run_at(3, 2).symbols == (';', 'c', 'd')   # 'ab' gone; ';cd' pulled to the start
        assert room.char_run_at(3, 5) is None


class TestChangeComposition:
    """`c{motion}` is op_delete over the span + entering INSERT at the deletion
    start. This locks the contract the game-loop wiring relies on."""
    def test_ce_deletes_word_and_lands_cursor_for_insert(self):
        room = _room()
        room.add_char_run(CharRun(3, 2, ('o', 'l', 'd'), 'ancient'))
        p = _player(3, 2)
        t = compute_text_object(p, _op('c', 'e'), room)
        op_delete(room, p, t)
        assert all(room.char_run_at(3, c) is None for c in (2, 3, 4))
        assert (p.row, p.col) == (3, 2)        # INSERT begins at the change start

    def test_cc_clears_line_and_lands_at_first_passable(self):
        room = _room()
        room.add_char_run(CharRun(3, 2, ('a',), 'ancient'))
        room.add_char_run(CharRun(3, 8, ('b',), 'ancient'))
        p = _player(3, 8)
        t = compute_text_object(p, _op('c', 'line'), room)
        op_delete(room, p, t)
        assert room.char_run_at(3, 2) is None and room.char_run_at(3, 8) is None
        assert (p.row, p.col) == (3, 1)


# ── J / gJ (join: remove_row of the next line + extend_floor append) ──────────

class TestJoin:
    def test_J_joins_next_line_with_a_space_and_collapses_it(self):
        room = _room()
        room.add_char_run(CharRun(3, 2, ('a', 'b'), 'ancient'))
        room.add_char_run(CharRun(4, 2, ('c', 'd'), 'ancient'))
        p = _player(3, 2)
        before = room.rows
        assert op_join(room, p, gap=True, count=1) is True
        assert room.rows == before - 1                       # the joined line is removed (collapse)
        assert (_sym(room, 3, 2), _sym(room, 3, 3)) == ('a', 'b')
        assert _sym(room, 3, 4) is None                      # one space at the seam
        assert (_sym(room, 3, 5), _sym(room, 3, 6)) == ('c', 'd')
        assert p.col == 4                                    # cursor on the seam space (Vim J)

    def test_gJ_joins_without_a_space(self):
        room = _room()
        room.add_char_run(CharRun(3, 2, ('a', 'b'), 'ancient'))
        room.add_char_run(CharRun(4, 2, ('c', 'd'), 'ancient'))
        p = _player(3, 2)
        assert op_join(room, p, gap=False, count=1) is True
        assert (_sym(room, 3, 2), _sym(room, 3, 3), _sym(room, 3, 4), _sym(room, 3, 5)) == ('a', 'b', 'c', 'd')
        assert p.col == 4                                    # cursor on the first joined glyph (gJ)

    def test_count_J_joins_multiple_lines(self):
        room = _room()
        room.add_char_run(CharRun(3, 2, ('a',), 'ancient'))
        room.add_char_run(CharRun(4, 2, ('b',), 'ancient'))
        room.add_char_run(CharRun(5, 2, ('c',), 'ancient'))
        p = _player(3, 2)
        before = room.rows
        assert op_join(room, p, gap=True, count=3) is True   # 3J → join the next two lines
        assert room.rows == before - 2
        assert (_sym(room, 3, 2), _sym(room, 3, 4), _sym(room, 3, 6)) == ('a', 'b', 'c')

    def test_J_preserves_the_joined_lines_internal_spacing(self):
        room = _room()
        room.add_char_run(CharRun(3, 2, ('a',), 'ancient'))
        room.add_char_run(CharRun(4, 2, ('p',), 'ancient'))   # 'p  q' — a 2-cell internal gap
        room.add_char_run(CharRun(4, 5, ('q',), 'ancient'))
        p = _player(3, 2)
        op_join(room, p, gap=True, count=1)
        # a(2) space(3) p(4) gap(5,6) q(7)
        assert _sym(room, 3, 4) == 'p' and _sym(room, 3, 7) == 'q'
        assert _sym(room, 3, 5) is None and _sym(room, 3, 6) is None

    def test_J_builds_into_the_void_doubling_cols(self):
        room = _room()                                        # floor 1..22, wall at 23
        room.add_char_run(CharRun(3, 1, tuple('abcdefghijklmnopqrstuv'), 'ancient'))  # fills to col 22
        room.add_char_run(CharRun(4, 2, ('Y', 'Z'), 'ancient'))
        p = _player(3, 1)
        assert op_join(room, p, gap=True, count=1) is True
        assert room.cols == COLS * 2                          # ran off the brink → world doubled
        assert _sym(room, 3, 24) == 'Y' and _sym(room, 3, 25) == 'Z'   # joined past the old wall

    def test_J_at_last_row_does_nothing(self):
        room = _room()
        room.add_char_run(CharRun(5, 2, ('a',), 'ancient'))   # last passable row (row 5 in a 7-row room)
        p = _player(5, 2)
        before = room.rows
        assert op_join(room, p, gap=True, count=1) is False   # no next line to join
        assert room.rows == before

    def test_J_refuses_past_the_edge_of_the_world(self):
        from vimny.engine.reflow import _MAX_COLS
        room = Room(room_type=RoomType.PUZZLE, rows=5, cols=_MAX_COLS)
        room.cells = [[CellType.FLOOR if (0 < r < 4 and 0 < c < _MAX_COLS - 1) else CellType.WALL
                       for c in range(_MAX_COLS)] for r in range(5)]
        room.add_char_run(CharRun(1, _MAX_COLS - 2, ('a',), 'ancient'))   # fills to the last buildable col
        room.add_char_run(CharRun(2, 1, ('b',), 'ancient'))               # a line below to join
        room.rebuild_indexes()
        p = _player(1, _MAX_COLS - 2)
        before = room.rows
        assert op_join(room, p, gap=True, count=1) is False               # would build past the world's edge
        assert room._last_build_blocked == 'edge'
        assert room.rows == before                                        # nothing collapsed
