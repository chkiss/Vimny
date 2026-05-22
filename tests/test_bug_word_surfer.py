"""The Word Surfer — bug tester personality that defaults to w/b/e for all navigation.

Uncovers: w/b/e through rune clusters, void rune skipping, count-word,
b-at-first-rune, w-blocked-by-wall.
"""
import pytest
from engine.world import Room, RoomType, CellType, RuneCluster
from engine.player import Player
from engine.motion import apply_motion


def _make_room(rows=5, cols=40):
    room = Room(room_type=RoomType.ENTRY, rows=rows, cols=cols)
    room.cells = [
        [CellType.FLOOR if (0 < r < rows - 1 and 0 < c < cols - 1) else CellType.WALL
         for c in range(cols)]
        for r in range(rows)
    ]
    room.entry = (2, 1)
    room.exit_pos = (2, cols - 2)
    room.fog_cells = set()
    room.rebuild_indexes()
    return room


def _add_rune(room, row, col, length, kind='ancient'):
    ru = RuneCluster(row=row, col=col, symbols=tuple('∘' * length), kind=kind)
    room.runes.append(ru)
    room.rebuild_indexes()
    return ru


# ── w ─────────────────────────────────────────────────────────────────────────

def test_w_from_start_of_rune_goes_to_start_of_next_rune():
    room = _make_room()
    _add_rune(room, row=2, col=5, length=3)    # occupies 5-7
    _add_rune(room, row=2, col=12, length=2)   # occupies 12-13
    player = Player(row=2, col=5)

    moved = apply_motion(player, 'w', 1, room)

    assert moved
    assert player.col == 12, f"expected col 12, got {player.col}"


def test_w_from_middle_of_rune_goes_to_start_of_next_rune():
    room = _make_room()
    _add_rune(room, row=2, col=5, length=3)
    _add_rune(room, row=2, col=12, length=2)
    player = Player(row=2, col=6)   # interior of first rune

    moved = apply_motion(player, 'w', 1, room)

    assert moved
    assert player.col == 12, f"expected col 12, got {player.col}"


def test_w_with_no_next_rune_does_not_move():
    """w when there is no rune to the right must leave the player in place."""
    room = _make_room()
    _add_rune(room, row=2, col=5, length=3)
    player = Player(row=2, col=5)

    moved = apply_motion(player, 'w', 1, room)

    assert not moved, "w should return False when no next rune exists"
    assert player.col == 5


def test_w_skips_void_rune():
    """w must skip void runes and land on the next regular rune."""
    room = _make_room(cols=40)
    _add_rune(room, row=2, col=5, length=3, kind='ancient')
    _add_rune(room, row=2, col=10, length=2, kind='void')
    _add_rune(room, row=2, col=18, length=3, kind='ancient')
    player = Player(row=2, col=5)

    moved = apply_motion(player, 'w', 1, room)

    assert moved
    assert player.col == 18, f"w should skip void and land at 18, got {player.col}"


def test_count_2_w_jumps_two_runes():
    """2w from a floor cell advances past two rune starts."""
    room = _make_room(cols=40)
    _add_rune(room, row=2, col=5, length=3)
    _add_rune(room, row=2, col=12, length=3)
    _add_rune(room, row=2, col=20, length=3)
    player = Player(row=2, col=1)   # floor, no rune

    moved = apply_motion(player, 'w', 2, room)

    assert moved
    assert player.col == 12, f"2w should land at col 12, got {player.col}"


def test_w_blocked_by_wall_between_runes():
    """w must not cross a wall cell."""
    room = _make_room(cols=40)
    _add_rune(room, row=2, col=5, length=3)
    room.cells[2][15] = CellType.WALL
    _add_rune(room, row=2, col=18, length=3)
    player = Player(row=2, col=5)

    moved = apply_motion(player, 'w', 1, room)

    assert not moved, "w should not cross the wall"
    assert player.col == 5


# ── b ─────────────────────────────────────────────────────────────────────────

def test_b_from_start_of_rune_goes_to_start_of_previous_rune():
    room = _make_room()
    _add_rune(room, row=2, col=5, length=3)
    _add_rune(room, row=2, col=12, length=2)
    player = Player(row=2, col=12)

    moved = apply_motion(player, 'b', 1, room)

    assert moved
    assert player.col == 5, f"expected col 5, got {player.col}"


def test_b_from_middle_of_rune_goes_to_start_of_that_rune():
    """b from interior of a rune snaps back to that rune's start col."""
    room = _make_room()
    _add_rune(room, row=2, col=5, length=3)   # occupies 5-7
    player = Player(row=2, col=7)             # interior (end)

    moved = apply_motion(player, 'b', 1, room)

    assert moved
    assert player.col == 5, f"expected col 5, got {player.col}"


def test_b_with_no_previous_rune_does_not_move():
    """b when there is no rune to the left must leave the player in place."""
    room = _make_room()
    _add_rune(room, row=2, col=5, length=3)
    player = Player(row=2, col=5)   # at start of only rune

    moved = apply_motion(player, 'b', 1, room)

    assert not moved, "b should return False when no previous rune exists"
    assert player.col == 5


# ── e ─────────────────────────────────────────────────────────────────────────

def test_e_from_start_of_rune_goes_to_end_of_that_rune():
    room = _make_room()
    _add_rune(room, row=2, col=5, length=4)   # occupies 5-8
    player = Player(row=2, col=5)

    moved = apply_motion(player, 'e', 1, room)

    assert moved
    assert player.col == 8, f"expected col 8, got {player.col}"


def test_e_from_end_of_rune_skips_to_end_of_next_rune():
    """e at a rune's end col must scan forward to the next rune's end."""
    room = _make_room(cols=40)
    _add_rune(room, row=2, col=5, length=3)    # end at col 7
    _add_rune(room, row=2, col=12, length=4)   # end at col 15
    player = Player(row=2, col=7)              # at end of first rune

    moved = apply_motion(player, 'e', 1, room)

    assert moved
    assert player.col == 15, f"expected col 15, got {player.col}"


def test_e_skips_void_rune_to_next_regular_rune_end():
    """e must skip void runes and land at the end of the next regular rune."""
    room = _make_room(cols=40)
    _add_rune(room, row=2, col=5, length=3, kind='ancient')   # end at 7
    _add_rune(room, row=2, col=12, length=2, kind='void')
    _add_rune(room, row=2, col=18, length=4, kind='ancient')  # end at 21
    player = Player(row=2, col=7)   # at end of first rune

    moved = apply_motion(player, 'e', 1, room)

    assert moved
    assert player.col == 21, f"e should skip void and land at 21, got {player.col}"


def test_e_with_no_next_rune_does_not_move():
    """e when already at the end of the last rune must not move."""
    room = _make_room()
    _add_rune(room, row=2, col=5, length=3)   # end at col 7
    player = Player(row=2, col=7)

    moved = apply_motion(player, 'e', 1, room)

    assert not moved, "e should return False when no next rune end exists"
    assert player.col == 7
