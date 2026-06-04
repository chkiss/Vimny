"""Tests for Block G — engine/insert.py: insert-entry positioning (i a I A o O s S),
INSERT typing/backspace, and blank-row insertion bookkeeping."""
import pytest
from engine.world import Room, RoomType, CellType, CharRun, Entity
from engine.player import Player
from engine.insert import (
    begin_insert, insert_char, insert_char_extend, insert_backspace,
    _insert_blank_row,
    replace_chars, replace_overtype, replace_restore,
)


def _syms(room, row, col):
    ru = room.char_run_at(row, col)
    return ''.join(ru.symbols) if ru else None


def _cell(room, row, col):
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


def _player(row=3, col=5):
    return Player(row=row, col=col)


# ── Entry positioning (non-mutating: i a I A) ────────────────────────────────

class TestEntryPositioning:
    def test_i_keeps_cursor(self):
        room = _room(); p = _player(3, 5)
        begin_insert(room, p, 'i')
        assert (p.row, p.col) == (3, 5)

    def test_a_moves_right(self):
        room = _room(); p = _player(3, 5)
        begin_insert(room, p, 'a')
        assert p.col == 6

    def test_I_jumps_to_first_non_blank(self):
        room = _room()
        room.add_char_run(CharRun(3, 8, ('x',), 'ancient'))
        p = _player(3, 15)
        begin_insert(room, p, 'I')
        assert p.col == 8

    def test_A_jumps_to_line_end_past_trailing_floor(self):
        room = _room()                                                 # floor 1..22, wall at 23
        room.add_char_run(CharRun(3, 2, ('a', 'b', 'c'), 'ancient'))   # content at cols 2-4
        p = _player(3, 0)
        begin_insert(room, p, 'A')
        assert p.col == 23                  # end of the LINE (past trailing floor), not col 5

    def test_A_on_empty_row_goes_to_line_end(self):
        room = _room(); p = _player(3, 10)
        begin_insert(room, p, 'A')
        assert p.col == 23                  # rightmost passable (22) + 1

    def test_A_sets_extend_flag_other_variants_clear_it(self):
        room = _room(); p = _player(3, 5)
        begin_insert(room, p, 'A')
        assert p.insert_extend is True          # A is the lone ledge-builder
        begin_insert(room, p, 'i')
        assert p.insert_extend is False
        begin_insert(room, p, 'a')
        assert p.insert_extend is False


# ── A's ledge-building (insert_char_extend) ───────────────────────────────────

class TestAppendExtend:
    def test_A_typing_carves_new_floor_at_the_wall(self):
        # content fills to the last floor; A then builds out through the wall,
        # doubling the buffer when it reaches the right border.
        room = _room()                                              # floor 1..22, wall at 23
        room.add_char_run(CharRun(3, 20, ('x', 'y', 'z'), 'ancient'))   # ends at col 22
        p = _player(3, 0)
        begin_insert(room, p, 'A')
        assert p.col == 23                                          # after content = the border wall
        assert insert_char_extend(room, p, 'Q') is True
        assert room.cols == COLS * 2                                # hit the border → world doubled
        assert room.cells[3][23] == CellType.FLOOR                  # carved
        assert _cell(room, 3, 23) == 'Q'
        assert p.col == 24

    def test_A_skips_trailing_floor_to_the_line_end(self):
        # A jumps PAST trailing floor to the line end (Vim-faithful), then builds
        # into the void — it does not fill the gap between content and the wall.
        room = _room()
        room.add_char_run(CharRun(3, 2, ('a',), 'ancient'))         # content at col 2; floor to 22
        p = _player(3, 0)
        begin_insert(room, p, 'A')
        assert p.col == 23                                          # line end, past the trailing floor
        insert_char_extend(room, p, 'Q')                            # builds at the end (doubles the world)
        assert _cell(room, 3, 23) == 'Q'
        assert all(_cell(room, 3, c) is None for c in range(3, 23)) # trailing floor left untouched

    def test_A_extend_stops_at_a_void_rune(self):
        room = _room()
        room.add_char_run(CharRun(3, 5, ('○',), 'void'))            # a permanent void cell
        p = _player(3, 5)                                          # cursor on the void
        p.insert_extend = True
        assert insert_char_extend(room, p, 'Q') is False           # plank refused
        assert _cell(room, 3, 5) == '○'                            # void unchanged
        assert p.col == 5                                          # cursor held

    def test_A_extend_stops_at_the_edge_of_the_world(self):
        from engine.reflow import _MAX_COLS
        room = Room(room_type=RoomType.ENTRY, rows=3, cols=_MAX_COLS)
        room.cells = [[CellType.FLOOR if (0 < r < 2 and 0 < c < _MAX_COLS - 1) else CellType.WALL
                       for c in range(_MAX_COLS)] for r in range(3)]
        room.rebuild_indexes()
        p = _player(1, _MAX_COLS - 1)                              # at the world's last column
        p.insert_extend = True
        assert insert_char_extend(room, p, 'Z') is False           # cannot build past the edge
        assert room._last_build_blocked == 'edge'
        assert room.cols == _MAX_COLS                              # the world did not grow


# ── Substitute entry (s / S) ─────────────────────────────────────────────────

class TestSubstituteEntry:
    def test_s_deletes_char_and_closes_the_gap(self):
        room = _room()
        room.add_char_run(CharRun(3, 5, ('a', 'b', 'c'), 'ancient'))
        p = _player(3, 5)
        begin_insert(room, p, 's')
        assert room.char_run_at(3, 5).symbols == ('b', 'c')   # 'a' gone; 'bc' pulled left
        assert room.char_run_at(3, 7) is None
        assert p.col == 5                                     # cursor at the deletion point

    def test_s_with_count_deletes_n_and_closes_the_gap(self):
        room = _room()
        room.add_char_run(CharRun(3, 2, ('a', 'b', 'c', 'd'), 'ancient'))
        p = _player(3, 2)
        begin_insert(room, p, 's', count=2)
        assert room.char_run_at(3, 2).symbols == ('c', 'd')   # 'ab' gone; 'cd' pulled left
        assert room.char_run_at(3, 4) is None

    def test_S_clears_whole_row(self):
        room = _room()
        room.add_char_run(CharRun(3, 2, ('a',), 'ancient'))
        room.add_char_run(CharRun(3, 9, ('b',), 'ancient'))
        p = _player(3, 9)
        begin_insert(room, p, 'S')
        assert room.char_run_at(3, 2) is None and room.char_run_at(3, 9) is None
        assert p.col == 1                         # first passable


# ── INSERT typing / backspace ────────────────────────────────────────────────

class TestInsertTyping:
    def test_insert_char_places_and_advances(self):
        room = _room(); p = _player(3, 5)
        assert insert_char(room, p, 'x') is True
        assert room.char_run_at(3, 5).symbols == ('x',)
        assert p.col == 6

    def test_consecutive_chars_merge(self):
        room = _room(); p = _player(3, 5)
        insert_char(room, p, 'x')
        insert_char(room, p, 'y')
        merged = room.char_run_at(3, 5)
        assert merged.symbols == ('x', 'y') and merged.col == 5
        assert p.col == 7

    def test_insert_char_overwrites_existing(self):
        room = _room()
        room.add_char_run(CharRun(3, 5, ('a',), 'ancient'))
        p = _player(3, 5)
        insert_char(room, p, 'z')
        assert room.char_run_at(3, 5).symbols == ('z',)

    def test_insert_char_blocked_on_wall(self):
        room = _room(); p = _player(3, 23)   # col 23 is wall
        assert insert_char(room, p, 'x') is False

    def test_backspace_removes_left(self):
        room = _room(); p = _player(3, 5)
        insert_char(room, p, 'x')             # x@5, cursor 6
        insert_char(room, p, 'y')             # y@6, cursor 7
        assert insert_backspace(room, p) is True
        assert p.col == 6
        assert room.char_run_at(3, 6) is None
        assert room.char_run_at(3, 5) is not None

    def test_backspace_at_line_start_noop(self):
        room = _room(); p = _player(3, 1)
        assert insert_backspace(room, p) is False
        assert p.col == 1


# ── Blank-row insertion (o / O) ──────────────────────────────────────────────

class TestRowInsertion:
    def test_insert_blank_row_shifts_content_below(self):
        room = _room()
        room.add_char_run(CharRun(2, 3, ('a',), 'ancient'))
        room.add_char_run(CharRun(4, 3, ('b',), 'ancient'))
        room.add_entity(Entity(kind='exit', row=3, col=20))
        room.exit_pos = (3, 20)
        _insert_blank_row(room, 3, template_row=2)
        assert room.rows == ROWS + 1
        assert room.char_run_at(2, 3) is not None      # above insertion: unchanged
        assert room.char_run_at(5, 3) is not None      # was row 4 → shifted to 5
        assert room.exit_pos == (4, 20)            # exit shifted down
        assert room.entity_at(4, 20) is not None

    def test_o_opens_below_and_moves_there(self):
        room = _room()
        room.add_char_run(CharRun(3, 3, ('a',), 'ancient'))
        p = _player(2, 5)
        begin_insert(room, p, 'o')
        assert room.rows == ROWS + 1
        assert p.row == 3                          # new blank row below original
        assert room.char_run_at(4, 3) is not None       # old row-3 content pushed to 4

    def test_O_opens_above_keeping_row_index(self):
        room = _room()
        room.add_char_run(CharRun(2, 3, ('a',), 'ancient'))
        p = _player(2, 5)
        begin_insert(room, p, 'O')
        assert room.rows == ROWS + 1
        assert p.row == 2                          # cursor on the new blank row
        assert room.char_run_at(3, 3) is not None       # old row-2 content pushed to 3
        assert room.char_run_at(2, 3) is None           # row 2 is now blank

    def test_fog_cells_shift_on_insert(self):
        room = _room()
        room.fog_cells = {(4, 10), (2, 10)}
        _insert_blank_row(room, 3, template_row=2)
        assert (5, 10) in room.fog_cells           # row 4 → 5
        assert (2, 10) in room.fog_cells           # row 2 unchanged


# ── r{char} single/count replace ──────────────────────────────────────────────

class TestReplaceChars:
    def test_replace_one_char_cursor_stays(self):
        room = _room()
        room.add_char_run(CharRun(3, 2, ('a', 'X', 'c'), 'ancient'))
        p = _player(3, 3)
        assert replace_chars(room, p, 'b', 1) is True
        assert [_cell(room, 3, c) for c in (2, 3, 4)] == ['a', 'b', 'c']
        assert p.col == 3                          # r does not advance

    def test_count_replace_advances_to_last(self):
        room = _room()
        room.add_char_run(CharRun(3, 2, ('a', 'b', 'c', 'd'), 'ancient'))
        p = _player(3, 2)
        replace_chars(room, p, 'x', 3)
        assert [_cell(room, 3, c) for c in (2, 3, 4, 5)] == ['x', 'x', 'x', 'd']
        assert p.col == 4                          # last replaced cell

    def test_replace_on_blank_places_rune(self):
        room = _room()
        p = _player(3, 5)                          # floor, no rune
        assert replace_chars(room, p, 'z', 1) is True
        assert _syms(room, 3, 5) == 'z'

    def test_replace_stops_at_wall(self):
        room = _room()
        room.add_char_run(CharRun(3, 22, ('a',), 'ancient'))   # col 23 is wall
        p = _player(3, 22)
        replace_chars(room, p, 'x', 3)
        assert _syms(room, 3, 22) == 'x'
        assert room.char_run_at(3, 23) is None


# ── R (REPLACE mode) overtype + restore ─────────────────────────────────────

class TestReplaceMode:
    def test_overtype_records_original_and_advances(self):
        room = _room()
        room.add_char_run(CharRun(3, 5, ('a',), 'verdant'))
        p = _player(3, 5)
        rec = replace_overtype(room, p, 'b')
        assert _syms(room, 3, 5) == 'b'
        assert rec == (5, ('a', 'verdant'))
        assert p.col == 6

    def test_overtype_on_blank_records_none(self):
        room = _room()
        p = _player(3, 5)
        rec = replace_overtype(room, p, 'b')
        assert rec == (5, None)
        assert _syms(room, 3, 5) == 'b'

    def test_backspace_restores_sequence(self):
        room = _room()
        room.add_char_run(CharRun(3, 5, ('a',), 'verdant'))   # only col 5 had content
        p = _player(3, 5)
        stack = [replace_overtype(room, p, 'x')]   # 'a'->x at 5
        stack.append(replace_overtype(room, p, 'y'))   # blank->y at 6
        assert _cell(room, 3, 5) == 'x' and _cell(room, 3, 6) == 'y'
        replace_restore(room, p, stack.pop())      # undo y@6
        assert room.char_run_at(3, 6) is None and p.col == 6
        replace_restore(room, p, stack.pop())      # undo x@5 → original 'a'
        assert _cell(room, 3, 5) == 'a' and p.col == 5


def test_A_in_goblin_gauntlet_row1_lands_at_line_end():
    """Regression: A on a sparse corridor row goes to the line END (the corridor
    edge), not just past the lone rune. The Goblin Gauntlet (58 cols) row-1
    corridor ends at col 56, so A lands at col 57."""
    from generation.dungeon_gen import build_dungeon_goblin_gauntlet
    room = build_dungeon_goblin_gauntlet(42).rooms[0]
    p = _player(1, 10)
    begin_insert(room, p, 'A')
    assert p.col == 57         # rightmost passable (56) + 1 — the corridor's end, not after the rune
