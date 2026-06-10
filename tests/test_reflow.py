"""Reflow — universal Vim-line editing on every row (the overlay grid is retired).

Inserting pushes content right and shoves overflow past a fixed brink (wall/void);
deleting pulls the tail left. `is_ledge` is always True, so a row reflows whether or
not it carries a void rune — the regression tests at the bottom pin that down.
"""
from engine.world import Room, RoomType, CellType, CharRun, Entity
from engine.player import Player
from engine.reflow import (
    is_ledge, void_col, open_gap, close_gap, remove_row, extend_floor, _insert_blank_row,
    carve_floor, _double_cols, _MAX_COLS,
)
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
