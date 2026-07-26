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

"""Reflow — universal Vim-line editing on every row (the overlay grid is retired).

Inserting pushes content right and shoves overflow past a fixed brink (wall/void);
deleting pulls the tail left. `is_ledge` is always True, so a row reflows whether or
not it carries a void rune — the regression tests at the bottom pin that down.
"""
from engine.world import Room, RoomType, CellType, CharRun, Entity
from engine.player import Player
from engine.reflow import (
    is_ledge, void_col, open_gap, close_gap, remove_row, extend_floor, _insert_blank_row,
    carve_floor, _double_cols, _MAX_COLS, split_line_down, _first_floor_col, _lands_on_floor,
    _blank_line_span,
)
from engine.insert import begin_insert
from engine.insert import insert_char
from engine.operator import op_delete
from engine.text_object import TextObject, TextObjectType


def _room(letters='abcd', start=5, void_start=9, void_n=5, cols=15, ledge=True):
    """Row 1 is a corridor (cols 1..cols-2); `letters` sit at `start`, and a run
    of void runes marks the brink at `void_start`. (`ledge` is a no-op kept for call
    sites — every row reflows now.)"""
    room = Room(room_type=RoomType.PUZZLE, rows=3, cols=cols)
    room.cells = [[CellType.FLOOR if (r == 1 and 0 < c < cols - 1) else CellType.WALL
                   for c in range(cols)] for r in range(3)]
    runes = [CharRun(1, start, tuple(letters), 'ancient')]
    if void_n:
        runes.append(CharRun(1, void_start, ('○',) * void_n, 'void'))
    room.char_runs = runes
    room.rebuild_indexes()
    return room


def _text(room, row):
    """{col: symbol} of the non-void runes on `row`."""
    out = {}
    for ru in room._char_runs_by_row.get(row, []):
        if ru.kind == 'void':
            continue
        for i, s in enumerate(ru.symbols):
            out[ru.col + i] = s
    return out


# ── detection ───────────────────────────────────────────────────────────────────

def test_reflow_is_universal():
    room = _room()
    assert is_ledge(room, 1) is True
    assert is_ledge(room, 0) is True           # every row reflows now (overlay retired)


def test_void_col_is_the_leftmost_void_rune():
    assert void_col(_room(), 1) == 9            # painted void margin (see wall-edge test below)


# ── open_gap (insert / push-right) ───────────────────────────────────────────────

def test_open_gap_shifts_right_dropping_overflow():
    room = _room()                              # abcd at 5-8, brink at 9
    fell = open_gap(room, 1, 5, 1)              # open a 1-wide gap at col 5
    assert _text(room, 1) == {6: 'a', 7: 'b', 8: 'c'}   # a/b/c slid right…
    assert room.char_run_at(1, 5) is None               # …col 5 is now empty
    assert fell == [(1, 9, 'd')]                         # d went over the brink
    assert room._last_void_falls == [(1, 9, 'd')]        # recorded for animation


def test_insert_pushes_whitespace_and_the_word_past_a_gap():
    """Vim faithfulness: inserting in the whitespace BEFORE a word still pushes the
    word — the shift travels THROUGH the blank cells, it doesn't stop at the gap."""
    room = _wave_room(cols=20)                   # floor 1..18, wall 19, ledge
    room.char_runs = [CharRun(1, 8, ('c', 'd'), 'ancient')]   # 'cd' at 8-9; blanks before it
    room.rebuild_indexes()
    p = Player(row=1, col=3)                      # cursor in the whitespace, left of the word
    insert_char(room, p, 'Z')
    assert _text(room, 1) == {3: 'Z', 9: 'c', 10: 'd'}   # word shifted right by one
    assert p.col == 4


def test_open_gap_no_fall_when_room_to_spare():
    room = _room(letters='ab', start=5)         # ab at 5-6, brink at 9
    fell = open_gap(room, 1, 5, 1)
    assert _text(room, 1) == {6: 'a', 7: 'b'}
    assert fell == []


def test_open_gap_leaves_cells_left_of_the_cursor_untouched():
    room = _room()                              # abcd at 5-8
    open_gap(room, 1, 7, 1)                      # gap at col 7 → only c,d move
    assert _text(room, 1) == {5: 'a', 6: 'b', 8: 'c'}   # a,b fixed; c→8; d fell
    assert room._last_void_falls == [(1, 9, 'd')]


def test_open_gap_push_stops_at_a_mid_row_wall():
    """The push is SEGMENT-BOUNDED, symmetric with the pull: a mid-row wall is a
    hard line boundary. The glyph shoved against the wall falls INTO it (the void
    animation), but a run BEYOND the wall is a separate line and stays put — the
    plaque-door family's east-of-a-wall plaque is safe from an edit to its west."""
    room = _room(letters='', void_n=0)
    room.cells[1][8] = CellType.WALL             # a bolt mid-row
    room.char_runs = [CharRun(1, 6, ('a', 'b'), 'ancient'),   # ab at 6-7, hard against the wall
                      CharRun(1, 10, ('z',), 'ancient')]      # beyond the wall — a separate line
    room.rebuild_indexes()
    fell = open_gap(room, 1, 6, 1)               # push at col 6
    assert _text(room, 1) == {7: 'a', 10: 'z'}   # a→7; b fell into the wall; z untouched
    assert fell == [(1, 8, 'b')]                 # b fell INTO the wall cell (col 8)


def test_open_gap_push_stops_at_a_void_rune():
    """A void rune bounds the push too: content past the hole does not slide over
    it, and the glyph tipped into the rune is lost there."""
    room = _room(letters='', void_n=0)
    room.char_runs = [CharRun(1, 6, ('a', 'b'), 'ancient'),
                      CharRun(1, 8, ('○',), 'void'),
                      CharRun(1, 10, ('z',), 'ancient')]
    room.rebuild_indexes()
    fell = open_gap(room, 1, 6, 1)
    assert _text(room, 1) == {7: 'a', 10: 'z'}   # a→7; b fell into the rune; z safe
    assert fell == [(1, 8, 'b')]
    assert room.char_run_at(1, 8).kind == 'void' # the rune itself stays


# ── close_gap (delete / pull-left) ───────────────────────────────────────────────

def test_close_gap_pulls_the_tail_left():
    # a 5, hole at 6, c 7, d 8 — as a caller leaves things after removing 'b'.
    room = _room(letters='', void_n=5)
    room.char_runs = [CharRun(1, 5, ('a',), 'ancient'),
                      CharRun(1, 7, ('c',), 'ancient'),
                      CharRun(1, 8, ('d',), 'ancient'),
                      CharRun(1, 9, ('○',) * 5, 'void')]
    room.rebuild_indexes()
    close_gap(room, 1, 6, 1)                     # close the 1-wide hole at col 6
    assert _text(room, 1) == {5: 'a', 6: 'c', 7: 'd'}
    assert room._last_void_falls == []           # deletion never drops anything


def test_close_gap_pull_stops_at_a_mid_row_wall():
    """The pull mirrors the push's FIXED brinks: text beyond a mid-row wall is a
    separate line and does NOT slide across it (the Cipher Cell's bolts shield
    each beat's cipher from the previous beat's shear)."""
    room = _room(letters='', void_n=0)
    room.cells[1][8] = CellType.WALL             # a bolt mid-row
    room.char_runs = [CharRun(1, 5, ('a',), 'ancient'),
                      CharRun(1, 10, ('z',), 'ancient')]   # beyond the wall
    room.rebuild_indexes()
    close_gap(room, 1, 6, 1)
    assert _text(room, 1) == {5: 'a', 10: 'z'}   # z did not cross the wall


def test_close_gap_pull_stops_at_a_void_rune():
    """A void rune is a FIXED brink for the pull too: text beyond the hole in
    the world doesn't slide over it."""
    room = _room(letters='', void_n=0)
    room.char_runs = [CharRun(1, 5, ('a',), 'ancient'),
                      CharRun(1, 8, ('○',), 'void'),
                      CharRun(1, 10, ('z',), 'ancient')]
    room.rebuild_indexes()
    close_gap(room, 1, 6, 1)
    assert _text(room, 1) == {5: 'a', 10: 'z'}
    assert room.char_run_at(1, 8).kind == 'void'           # the hole itself stays


def test_close_gap_pull_slides_past_an_entity():
    """Entities are PERMEABLE to the pull (The Operator's Vault's par path
    relies on corridor text sliding past its chests and keys) — a deliberate
    asymmetry with the push, which loses a glyph shoved onto an entity."""
    room = _room(letters='', void_n=0)
    room.entities.append(Entity(kind='chest', row=1, col=8))
    room.char_runs = [CharRun(1, 5, ('a',), 'ancient'),
                      CharRun(1, 10, ('z',), 'ancient')]
    room.rebuild_indexes()
    close_gap(room, 1, 6, 1)
    assert _text(room, 1) == {5: 'a', 9: 'z'}    # z slid past the chest


# ── insert_char end-to-end ───────────────────────────────────────────────────────

def test_insert_char_on_ledge_pushes_right_and_advances():
    room = _room(letters='ab', start=5)
    p    = Player(row=1, col=5)
    assert insert_char(room, p, 'Z') is True
    assert _text(room, 1) == {5: 'Z', 6: 'a', 7: 'b'}   # Z placed, a/b pushed right
    assert p.col == 6                                    # cursor advanced past Z


def test_insert_char_on_ledge_shoves_a_glyph_over_the_brink():
    room = _room()                              # abcd at 5-8, brink at 9
    p    = Player(row=1, col=5)
    insert_char(room, p, 'Z')                    # Z a b c | d→void
    assert _text(room, 1) == {5: 'Z', 6: 'a', 7: 'b', 8: 'c'}
    assert room._last_void_falls == [(1, 9, 'd')]


# ── op_delete end-to-end (dl / x-style on a ledge) ───────────────────────────────

def test_charwise_delete_closes_the_gap_on_a_ledge():
    room = _room()                              # abcd at 5-8
    p    = Player(row=1, col=6)
    op_delete(room, p, TextObject(1, 6, 1, 6, TextObjectType.INCLUSIVE))   # delete 'b'
    assert _text(room, 1) == {5: 'a', 6: 'c', 7: 'd'}   # c,d pulled left
    assert p.col == 6                                    # cursor at the deletion point
    assert room._last_void_falls == []


# ── reflow is universal — even an unmarked row flows (overlay retired) ────────────

def test_insert_reflows_even_without_explicit_ledge_marking():
    room = _room(ledge=False)                    # abcd at 5-8, void at 9; ledge_rows NOT set
    p    = Player(row=1, col=5)
    insert_char(room, p, 'X')                    # still reflows: X in, abc shift right, d into the void
    assert _text(room, 1) == {5: 'X', 6: 'a', 7: 'b', 8: 'c'}
    assert p.col == 6


# ── brink styles: painted void margin vs. bare wall edge ─────────────────────────

def test_insert_never_overwrites_a_void_rune():
    """Bugfix: typing must not erode the painted void. The glyph at the last
    editable cell is shoved over the brink (falls); the chasm stays intact and the
    cursor advances ONTO the brink — main.py then falls the player in."""
    room = _room()                              # abcd at 5-8, void at 9-13
    p    = Player(row=1, col=8)                 # the last editable cell
    insert_char(room, p, 'Z')                   # Z lands at 8; old 'd' → 9 → falls
    assert _text(room, 1) == {5: 'a', 6: 'b', 7: 'c', 8: 'Z'}
    for c in range(9, 14):                      # the chasm is untouched, never overwritten
        ru = room.char_run_at(1, c)
        assert ru is not None and ru.kind == 'void'
    assert p.col == 9 and room.char_run_at(1, 9).kind == 'void'   # cursor sits on the brink


def test_typing_into_the_void_drops_without_placing():
    """If the cursor is already over the brink, the glyph just drops — nothing is
    written onto the void."""
    room = _room()                              # void begins at col 9
    p    = Player(row=1, col=10)                # cursor in the void
    insert_char(room, p, 'Z')
    assert room.char_run_at(1, 10).kind == 'void'    # still void, not 'Z'
    assert room._last_void_falls == [(1, 10, 'Z')]


def test_void_col_falls_back_to_the_wall_edge():
    room = _room(void_n=0)                       # no painted void; floor 1..13, wall at 14
    assert void_col(room, 1) == 14


def test_wall_edge_content_falls_off_against_the_wall():
    """Bare wall-edge ledge: a glyph tipped against the stone wall falls off."""
    room = _room(letters='ab', start=12, void_n=0)   # a@12 b@13, wall at 14
    fell = open_gap(room, 1, 12, 1)              # push right → b hits the wall
    assert _text(room, 1) == {13: 'a'}
    assert fell == [(1, 14, 'b')]


def test_wall_edge_cursor_clamps_and_never_falls():
    """On a wall edge the cursor stops at the last floor cell — walls aren't
    passable, so (unlike the void margin) the player can't step off the edge."""
    room = _room(letters='ab', start=12, void_n=0)   # floor 1..13, wall at 14
    p    = Player(row=1, col=13)                 # last floor cell
    insert_char(room, p, 'Z')                    # Z at 13; old 'b' falls off the wall
    assert p.col == 13                           # clamped — did NOT advance onto the wall
    assert room.cells[1][14] == CellType.WALL


# ── water is the one MOVABLE terrain: a wave shoves along and drowns goblins ──────

def _wave_room(cols=15):
    """Row 1: floor 1..cols-2, wall at cols-1. The caller drops in glyphs / a water
    puddle / a goblin, then calls rebuild_indexes()."""
    room = Room(room_type=RoomType.PUZZLE, rows=3, cols=cols)
    room.cells = [[CellType.FLOOR if (r == 1 and 0 < c < cols - 1) else CellType.WALL
                   for c in range(cols)] for r in range(3)]
    return room


def test_water_is_pushed_along_by_a_wave():
    room = _wave_room()
    room.char_runs   = [CharRun(1, 5, ('a',), 'verdant')]
    room.cells[1][6] = CellType.WATER            # a@5, water@6, open floor beyond
    room.rebuild_indexes()
    open_gap(room, 1, 5, 1)                       # insert at 5 → a→6, water→7
    assert _text(room, 1) == {6: 'a'}
    assert room.cells[1][6] == CellType.FLOOR and room.cells[1][7] == CellType.WATER
    assert room._last_void_falls == [] and room._last_drowns == []


def test_water_wave_drowns_a_goblin():
    room = _wave_room()
    room.char_runs   = [CharRun(1, 5, ('a',), 'verdant')]
    room.cells[1][6] = CellType.WATER
    room.entities    = [Entity(kind='goblin', row=1, col=7, hp=1, max_hp=1, ai='')]
    room.rebuild_indexes()
    open_gap(room, 1, 5, 1)                       # a→6; the wave rolls onto the goblin@7
    assert room.entity_at(1, 7) is None           # drowned
    assert room.cells[1][7] == CellType.WATER     # water rolled onto its cell
    assert room.cells[1][6] == CellType.FLOOR
    assert _text(room, 1) == {6: 'a'}
    assert room._last_drowns == [(1, 7)]


def test_water_wave_sweeps_any_entity_not_just_goblins():
    """A wave sweeps away whatever it reaches — a key in its path is lost."""
    room = _wave_room()
    room.char_runs   = [CharRun(1, 5, ('a',), 'verdant')]
    room.cells[1][6] = CellType.WATER
    room.entities    = [Entity(kind='floor_key', row=1, col=7)]   # not a creature
    room.rebuild_indexes()
    open_gap(room, 1, 5, 1)
    assert room.entity_at(1, 7) is None           # the key is gone
    assert room.cells[1][7] == CellType.WATER
    assert room._last_drowns == [(1, 7)]


def test_water_spills_off_a_wall():
    room = _wave_room()                           # floor 1..13, wall at 14
    room.char_runs    = [CharRun(1, 12, ('a',), 'verdant')]
    room.cells[1][13] = CellType.WATER            # a@12, water@13, wall@14
    room.rebuild_indexes()
    open_gap(room, 1, 12, 1)                       # a→13; water spills off the wall
    assert _text(room, 1) == {13: 'a'}
    assert room.cells[1][13] == CellType.FLOOR     # the water is gone (spilled)
    assert room._last_void_falls == [(1, 14, '~')]


def test_water_is_not_a_brink_so_cells_past_it_arent_void():
    """Regression: water (non-floor) must not poison void_col. Inserting to the
    RIGHT of a puddle reflows normally — it is NOT treated as 'over the brink'."""
    room = _wave_room(cols=20)
    room.char_runs   = [CharRun(1, 5, ('a',), 'verdant')]
    room.cells[1][6] = CellType.WATER             # puddle at 6; floor 7..18, wall 19
    room.rebuild_indexes()
    assert void_col(room, 1) == 19                # the wall — NOT the water at col 6
    p = Player(row=1, col=10)                     # well to the right of the puddle
    insert_char(room, p, 'Z')                     # just places Z and advances; nothing drops
    assert room.char_run_at(1, 10).symbols == ('Z',)
    assert p.col == 11
    assert room._last_void_falls == []


def test_void_col_stays_in_the_cursors_own_segment():
    """Regression: a row split by stone has more than one brink.

    Scanning from the row's leftmost glyph finds whichever brink THAT segment
    hits, which can be far west of the cursor and on the far side of a wall.
    The dummy dungeon's row 22 is exactly this shape — a label buried in the
    west wall band, a wall at 75, then the typing floor at 76+ and the void
    runes at 85 — and a typist who fell off the ledge anywhere past 76 was set
    down at 74, in a segment they had never walked to.
    """
    room = _wave_room(cols=30)
    room.char_runs = [CharRun(1, 2, ('l', 'a', 'b'), 'ancient'),   # west segment
                      CharRun(1, 20, ('o', 'o'), 'void')]          # east brink
    room.cells[1][10] = CellType.WALL             # the divider
    room.rebuild_indexes()

    assert void_col(room, 1) == 10                # unscoped: the divider, west segment
    assert void_col(room, 1, 12) == 20            # from the east segment: the void runes
    assert void_col(room, 1, 2) == 10             # from the west segment: still the divider


# ── remove_row (vertical collapse — the inverse of o; powers dd) ──────────────────

def _col_room(rows=6, cols=10):
    """A rows×cols room: all-FLOOR interior bounded by a wall border, no runes."""
    room = Room(room_type=RoomType.PUZZLE, rows=rows, cols=cols)
    room.cells = [[CellType.FLOOR if (0 < r < rows - 1 and 0 < c < cols - 1) else CellType.WALL
                   for c in range(cols)] for r in range(rows)]
    room.rebuild_indexes()
    return room


def test_remove_row_collapses_and_shifts_runes_up():
    room = _col_room()
    room.char_runs = [CharRun(2, 3, ('a',), 'ancient'), CharRun(3, 4, ('b',), 'ancient')]
    room.rebuild_indexes()
    before = room.rows
    assert remove_row(room, 2) is True
    assert room.rows == before - 1
    assert room.char_run_at(2, 3) is None              # the removed row's rune is gone
    assert room.char_run_at(2, 4).symbols == ('b',)    # row 3 pulled up into row 2


def test_remove_row_drops_its_entities_and_shifts_those_below():
    room = _col_room()
    room.add_entity(Entity(kind='goblin', row=2, col=3, max_hp=2))
    room.add_entity(Entity(kind='goblin', row=4, col=5, max_hp=2))
    assert remove_row(room, 2) is True
    assert room.entity_at(2, 3) is None                # entity on the removed row goes with it
    shifted = room.entity_at(3, 5)                     # the row-4 goblin shifted up to row 3
    assert shifted is not None and shifted.kind == 'goblin'


def test_remove_row_shifts_exit_and_spawn_below_the_cut():
    room = _col_room()
    room.spawn_pos = (1, 1)
    room.exit_pos  = (4, 6)
    assert remove_row(room, 2) is True
    assert room.exit_pos == (3, 6)                      # exit below the cut shifts up by one
    assert room.spawn_pos == (1, 1)                     # spawn above the cut is unchanged


def test_remove_row_refuses_solid_border_rows():
    room = _col_room()
    assert remove_row(room, 0) is False                # top border is all wall
    assert remove_row(room, room.rows - 1) is False    # bottom border too
    assert room.rows == 6                              # nothing collapsed


def test_remove_row_refuses_the_last_row():
    room = Room(room_type=RoomType.PUZZLE, rows=1, cols=5)
    room.cells = [[CellType.FLOOR] * 5]
    room.rebuild_indexes()
    assert remove_row(room, 0) is False


# ── extend_floor (horizontal ledge-build — powers A; J's append half) ────────────

def test_extend_floor_carves_a_wall_into_floor():
    room = _col_room(rows=3, cols=12)
    room.cells[1][6] = CellType.WALL                  # a wall mid-row
    assert extend_floor(room, 1, 6, 'X') is True
    assert room.cells[1][6] == CellType.FLOOR         # carved into the ledge
    assert room.char_run_at(1, 6).symbols == ('X',)


def test_extend_floor_places_on_plain_floor_without_carving():
    room = _col_room(rows=3, cols=12)                 # col 5 is already floor
    assert extend_floor(room, 1, 5, 'Y') is True
    assert room.cells[1][5] == CellType.FLOOR
    assert room.char_run_at(1, 5).symbols == ('Y',)


def test_extend_floor_stops_at_a_void_rune():
    room = _col_room(rows=3, cols=12)
    room.char_runs = [CharRun(1, 6, ('○',), 'void')]
    room.rebuild_indexes()
    assert extend_floor(room, 1, 6, 'Z') is False     # permanent void refuses the plank
    assert room.char_run_at(1, 6).symbols == ('○',)   # unchanged


def test_extend_floor_doubles_the_buffer_at_the_right_border():
    room = _col_room(rows=3, cols=10)                 # border wall at col 9
    assert extend_floor(room, 1, 9, 'E') is True      # building on the border grows the world
    assert room.cols == 20
    assert room.cells[1][9] == CellType.FLOOR         # old border carved to floor
    assert room.char_run_at(1, 9).symbols == ('E',)
    assert room.cells[1][19] == CellType.WALL         # fresh border at the new right edge


def test_double_cols_caps_at_the_edge_of_the_world():
    room = _col_room(rows=3, cols=_MAX_COLS - 10)
    _double_cols(room)
    assert room.cols == _MAX_COLS                     # 2× would overshoot → capped at the edge


def test_carve_floor_refuses_past_the_edge_of_the_world():
    room = _col_room(rows=3, cols=_MAX_COLS)          # already at max width
    assert carve_floor(room, 1, _MAX_COLS - 1) is False   # the border of a maxed world
    assert room._last_build_blocked == 'edge'
    assert room.cols == _MAX_COLS                     # the world did not grow
    assert carve_floor(room, 1, 5) is True            # interior still builds fine
    assert room._last_build_blocked is None


# ── mark / jumplist row fixups (player anchors move with the rows) ───────────────

def test_insert_blank_row_shifts_player_marks_and_jumps_down():
    room = _col_room()
    p = Player(row=1, col=1)
    p.marks     = {'a': (1, 2), 'b': (3, 4)}          # 'a' above the insert, 'b' below
    p.jump_list = [(0, 0), (3, 5)]
    _insert_blank_row(room, 2, 1, p)                  # insert a row at index 2
    assert p.marks == {'a': (1, 2), 'b': (4, 4)}      # above stays; at/below shifts down
    assert p.jump_list == [(0, 0), (4, 5)]


def test_remove_row_shifts_player_marks_and_jumps_up():
    room = _col_room()
    p = Player(row=1, col=1)
    p.marks     = {'a': (1, 2), 'b': (4, 4), 'c': (2, 3)}   # 'c' sits on the removed row
    p.jump_list = [(1, 1), (2, 7), (4, 0)]
    remove_row(room, 2, p)                            # remove row 2
    assert p.marks == {'a': (1, 2), 'b': (3, 4), 'c': (2, 3)}   # below shifts up; on-cut clamps to row 2
    assert p.jump_list == [(1, 1), (2, 7), (3, 0)]


# ── o / O open a Vim BLANK line (segment-width floor, no interior walls) ─────────

def _pillar_room():
    """A 5×12 room whose row 2 is split by a wall pillar at col 6: floor 1..5,
    WALL 6, floor 7..10. The left and right segments never touch."""
    room = Room(room_type=RoomType.PUZZLE, rows=5, cols=12)
    room.cells = [[CellType.FLOOR if (0 < r < 4 and 0 < c < 11) else CellType.WALL
                   for c in range(12)] for r in range(5)]
    for r in range(5):
        room.cells[r][6] = CellType.WALL          # a full wall column at col 6
    room.rebuild_indexes()
    return room


def test_blank_line_span_is_the_cursor_segment():
    room = _pillar_room()
    assert _blank_line_span(room, 2, 3) == (1, 5)       # left segment, up to the pillar
    assert _blank_line_span(room, 2, 8) == (7, 10)       # right segment, from the pillar
    assert _blank_line_span(room, 2, 6) is None          # the pillar is not floor


def test_o_opens_a_blank_line_the_width_of_the_cursor_segment():
    """o opens a Vim blank line: FLOOR across the cursor's own floor segment and
    WALL everywhere else. It copies NO interior walls and never bridges the wall
    column (that is A's axis) — the far segment stays wall on the new row."""
    room = _pillar_room()
    p = Player(row=2, col=3)                              # left segment
    begin_insert(room, p, 'o')
    new = room.cells[3]                                   # the fresh blank line
    assert [c for c in range(12) if new[c] == CellType.FLOOR] == [1, 2, 3, 4, 5]
    assert new[6] == CellType.WALL                        # the column is NOT breached
    assert all(new[c] == CellType.WALL for c in range(7, 12))  # far segment not cloned
    assert new[0] == CellType.WALL and new[11] == CellType.WALL  # borders intact


def test_O_opens_a_blank_line_no_interior_walls_from_the_right_segment():
    room = _pillar_room()
    p = Player(row=2, col=8)                              # right segment
    begin_insert(room, p, 'O')
    new = room.cells[2]                                   # O's blank line sits at the old row index
    assert [c for c in range(12) if new[c] == CellType.FLOOR] == [7, 8, 9, 10]
    assert new[6] == CellType.WALL and new[0] == CellType.WALL and new[11] == CellType.WALL


def test_paste_clone_still_copies_the_row_structure():
    """The default (blank=False) path — linewise paste / :s line split — is
    untouched: it CLONES the template's wall pattern, pillar and all."""
    room = _pillar_room()
    _insert_blank_row(room, 3, template_row=2)            # no blank flag → clone
    new = room.cells[3]
    assert new[6] == CellType.WALL                        # pillar preserved…
    assert new[1] == CellType.FLOOR and new[7] == CellType.FLOOR   # …and BOTH segments floor


# ── split_line_down (insert-mode <Enter> — bounded vertical line-split) ──────────

def test_split_line_down_drops_the_tail_to_the_next_line_col0():
    """Head stays; the tail drops to the row below, re-aligned to that row's column 0
    (its first floor cell — Vim-faithful), and the cursor parks there."""
    room = _col_room(rows=6, cols=12)                 # floor interior cols 1..10
    room.char_runs = [CharRun(1, 3, tuple('hello'), 'ancient')]   # 'hello' at 3..7 on row 1
    room.rebuild_indexes()
    p = Player(row=1, col=5)                           # cursor on the second 'l' (col 5)
    fell = split_line_down(room, p)
    assert _text(room, 1) == {3: 'h', 4: 'e'}          # head 'he' stays on row 1
    assert _text(room, 2) == {1: 'l', 2: 'l', 3: 'o'}  # tail 'llo' → row 2 at col 0 (=1)
    assert fell == []                                  # full-width row below: nothing lost
    assert (p.row, p.col) == (2, 1)                    # cursor at the new line's col 0


def test_split_line_down_never_grows_the_dungeon():
    room = _col_room(rows=6, cols=12)
    room.char_runs = [CharRun(1, 3, tuple('abc'), 'ancient')]
    room.rebuild_indexes()
    before = room.rows
    split_line_down(room, Player(row=1, col=4))
    assert room.rows == before                         # height is FIXED (unlike o / _insert_blank_row)


def test_split_line_down_pushes_the_rows_below_straight_down():
    room = _col_room(rows=6, cols=12)
    room.char_runs = [CharRun(1, 3, tuple('ab'), 'ancient'),
                      CharRun(2, 5, ('x',), 'ancient'),      # a row below
                      CharRun(3, 6, ('y',), 'ancient')]
    room.rebuild_indexes()
    split_line_down(room, Player(row=1, col=5))         # split row 1 (cursor past 'ab' → empty tail)
    assert _text(room, 1) == {3: 'a', 4: 'b'}           # head intact
    assert _text(room, 3) == {5: 'x'}                   # row 2 → row 3, SAME column
    assert _text(room, 4) == {6: 'y'}                   # row 3 → row 4, SAME column


def test_split_line_down_spills_a_narrow_throat_tail_into_the_void():
    """When the row below is a narrow throat (only the spine is floor), the tail's
    first glyph lands on the spine and the rest fall into the void — the confirmed
    'fist|gate' behaviour, the vertical mirror of open_gap's wall spill."""
    room = _col_room(rows=6, cols=12)
    for c in range(1, 11):                              # wall off row 2 except the spine col 1
        if c != 1:
            room.cells[2][c] = CellType.WALL
    room.char_runs = [CharRun(1, 3, tuple('gate'), 'ancient')]   # 'gate' at 3..6 on row 1
    room.rebuild_indexes()
    p = Player(row=1, col=3)                            # cursor on 'g' → whole word is the tail
    fell = split_line_down(room, p)
    assert _text(room, 1) == {}                         # head empty (cursor at word start)
    assert _text(room, 2) == {1: 'g'}                   # 'g' lands on the spine (col 0)
    assert [s for _, _, s in fell] == ['a', 't', 'e']   # 'ate' fell into the void
    assert (p.row, p.col) == (2, 1)


def test_split_line_down_a_glyph_pushed_onto_an_entity_falls():
    room = _col_room(rows=6, cols=12)
    room.char_runs = [CharRun(1, 3, ('a',), 'ancient'),
                      CharRun(2, 5, ('b',), 'ancient')]
    room.add_entity(Entity(kind='goblin', row=3, col=5, max_hp=2))   # blocks where 'b' would land
    room.rebuild_indexes()
    fell = split_line_down(room, Player(row=1, col=4))   # row 2's 'b' shifts to row 3 col 5 → onto goblin
    assert room.entity_at(3, 5).kind == 'goblin'         # the entity stays FIXED
    assert (3, 5, 'b') in fell                            # the glyph fell instead of overwriting it
    assert _text(room, 3) == {}


def test_first_floor_col_and_lands_on_floor_helpers():
    room = _col_room(rows=4, cols=10)                    # floor cols 1..8 on interior rows
    assert _first_floor_col(room, 1) == 1                # column 0 of a corridor row
    assert _first_floor_col(room, 0) is None             # all-wall border row
    assert _lands_on_floor(room, 1, 1) is True
    assert _lands_on_floor(room, 1, 0) is False          # the wall border
    room.char_runs = [CharRun(1, 4, ('○',), 'void')]
    room.rebuild_indexes()
    assert _lands_on_floor(room, 1, 4) is False          # a void rune is not bare floor
