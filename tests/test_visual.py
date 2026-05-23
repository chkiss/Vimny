"""Tests for Block D2 — engine/visual.py: selection span, highlight membership,
and operator application (charwise / linewise / block)."""
import pytest
from engine.world import Room, RoomType, CellType, RuneCluster
from engine.player import Player
from engine.modes import Mode
from engine.text_object import TextObjectType
from engine.visual import visual_span, in_selection, block_bounds, apply_visual

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
    ru = room.rune_at(r, c)
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

    def test_multirow_charwise_is_linewise(self):
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


class TestApplyVisual:
    def test_charwise_delete(self):
        room = _room()
        room.add_rune(RuneCluster(3, 2, ('a', 'b', 'c', 'd', 'e'), 'ancient'))
        p = Player(row=3, col=5)
        apply_visual('d', (3, 3), (3, 5), Mode.VISUAL, room, p)   # delete b,c,d
        assert _cell(room, 3, 2) == 'a' and _cell(room, 3, 6) == 'e'
        assert all(room.rune_at(3, c) is None for c in (3, 4, 5))
        assert p.col == 3                                          # cursor to start

    def test_charwise_yank_no_mutation(self):
        room = _room()
        room.add_rune(RuneCluster(3, 2, ('a', 'b', 'c'), 'ancient'))
        p = Player(row=3, col=4)
        clip = apply_visual('y', (3, 2), (3, 4), Mode.VISUAL, room, p)
        assert _cell(room, 3, 2) == 'a'                            # unchanged
        assert clip['rows'][0]['runes'][0]['symbols'] == ('a', 'b', 'c')
        assert (p.row, p.col) == (3, 2)

    def test_linewise_delete_clears_rows(self):
        room = _room()
        room.add_rune(RuneCluster(2, 3, ('x',), 'ancient'))
        room.add_rune(RuneCluster(3, 5, ('y',), 'ancient'))
        p = Player(row=2, col=0)
        apply_visual('d', (2, 0), (3, 0), Mode.VISUAL_LINE, room, p)
        assert room.rune_at(2, 3) is None and room.rune_at(3, 5) is None

    def test_visual_case_toggle(self):
        room = _room()
        room.add_rune(RuneCluster(3, 2, ('a', 'B', 'c'), 'ancient'))
        p = Player(row=3, col=4)
        apply_visual('g~', (3, 2), (3, 4), Mode.VISUAL, room, p)
        assert (_cell(room, 3, 2), _cell(room, 3, 3), _cell(room, 3, 4)) == ('A', 'b', 'C')

    def test_block_delete_rectangle(self):
        room = _room()
        room.add_rune(RuneCluster(2, 2, ('a', 'b', 'c'), 'ancient'))
        room.add_rune(RuneCluster(3, 2, ('d', 'e', 'f'), 'ancient'))
        p = Player(row=2, col=2)
        apply_visual('d', (2, 3), (3, 4), Mode.VISUAL_BLOCK, room, p)   # cols 3-4 on rows 2-3
        assert _cell(room, 2, 2) == 'a' and _cell(room, 3, 2) == 'd'    # col 2 kept
        assert all(room.rune_at(r, c) is None for r in (2, 3) for c in (3, 4))
        assert (p.row, p.col) == (2, 3)
