"""Ledge-row reflow (PILOT) — the sanctioned exception to the fixed overlay grid.

On a ledge row (opt-in via room.ledge_rows) editing flows like a real Vim line:
inserting pushes content right and shoves overflow into the void; deleting pulls
the tail left. Every *non*-ledge row keeps the overlay behaviour — the two
regression tests at the bottom pin that down (a row is NOT a ledge just because
it happens to carry a void rune; only membership in room.ledge_rows matters).
"""
import pytest
from engine.world import Room, RoomType, CellType, CharRun, Entity
from engine.player import Player
from engine.reflow import is_ledge, void_col, open_gap, close_gap
from engine.insert import insert_char
from engine.operator import op_delete
from engine.text_object import TextObject, TextObjectType


def _room(letters='abcd', start=5, void_start=9, void_n=5, cols=15, ledge=True):
    """Row 1 is a corridor (cols 1..cols-2); `letters` sit at `start`, and a run
    of void runes marks the brink at `void_start`. Row 1 is a ledge iff `ledge`."""
    room = Room(room_type=RoomType.PUZZLE, rows=3, cols=cols)
    room.cells = [[CellType.FLOOR if (r == 1 and 0 < c < cols - 1) else CellType.WALL
                   for c in range(cols)] for r in range(3)]
    runes = [CharRun(1, start, tuple(letters), 'ancient')]
    if void_n:
        runes.append(CharRun(1, void_start, ('○',) * void_n, 'void'))
    room.char_runs = runes
    if ledge:
        room.ledge_rows = {1}
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

def test_is_ledge_only_for_marked_rows():
    room = _room()
    assert is_ledge(room, 1) is True
    assert is_ledge(room, 0) is False          # an ordinary stone row


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


# ── regressions: non-ledge rows keep the overlay grid ────────────────────────────

def test_overlay_insert_overwrites_in_place():
    room = _room(ledge=False)                   # abcd at 5-8, NOT a ledge
    p    = Player(row=1, col=5)
    insert_char(room, p, 'X')
    assert _text(room, 1) == {5: 'X', 6: 'b', 7: 'c', 8: 'd'}   # overwrote, no shift
    assert p.col == 6


def test_a_void_rune_alone_does_not_make_a_ledge():
    room = _room(ledge=False)                   # has a void rune, but unmarked
    assert is_ledge(room, 1) is False
    p = Player(row=1, col=8)
    insert_char(room, p, 'X')                    # overwrites 'd' in place; nothing moves
    assert _text(room, 1) == {5: 'a', 6: 'b', 7: 'c', 8: 'X'}
    assert room._last_void_falls == []


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
    """Row 1: floor 1..cols-2, wall at cols-1, marked a ledge. The caller drops in
    glyphs / a water puddle / a goblin, then calls rebuild_indexes()."""
    room = Room(room_type=RoomType.PUZZLE, rows=3, cols=cols)
    room.cells = [[CellType.FLOOR if (r == 1 and 0 < c < cols - 1) else CellType.WALL
                   for c in range(cols)] for r in range(3)]
    room.ledge_rows = {1}
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
