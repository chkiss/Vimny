"""The Line Ender — obsessed with $, 0, and ^; never uses h/l if a line-end command will do.

Personality defined in agents/bug_testers.md.
"""
import pytest
from engine.world import Room, RoomType, CellType, Entity, CharRun
from engine.player import Player
from engine.motion import apply_motion
from main import _keystroke_cost


def _bare_room(rows=7, cols=30):
    room = Room(room_type=RoomType.ENTRY, rows=rows, cols=cols)
    room.cells = [
        [CellType.FLOOR if (0 < r < rows - 1 and 0 < c < cols - 1) else CellType.WALL
         for c in range(cols)]
        for r in range(rows)
    ]
    room.spawn_pos = (3, 1)
    room.exit_pos = (3, 28)
    room.fog_cells = set()
    room.rebuild_indexes()
    return room


# ── $ motion ──────────────────────────────────────────────────────────────────

def test_dollar_stops_before_fog_wall():
    """$ must halt at the last non-fog column, not pass through fogged cells."""
    room = _bare_room()
    room.fog_cells = {(3, c) for c in range(15, 29)}
    player = Player(row=3, col=1)

    apply_motion(player, '$', 1, room)

    assert player.col == 14, (
        f"$ should stop at col 14 (last non-fog cell), got {player.col}"
    )


def test_dollar_stops_before_locked_door():
    """$ must stop one cell before a locked_door entity."""
    room = _bare_room()
    room.add_entity(Entity(kind='locked_door', row=3, col=15))
    player = Player(row=3, col=1)

    apply_motion(player, '$', 1, room)

    assert player.col == 14, (
        f"$ should stop at col 14 (before locked_door at 15), got {player.col}"
    )


def test_dollar_stops_before_shield():
    """$ must stop one cell before a shield entity (same blocking rule as locked_door)."""
    room = _bare_room()
    room.add_entity(Entity(kind='shield', row=3, col=15))
    player = Player(row=3, col=1)

    apply_motion(player, '$', 1, room)

    assert player.col == 14, (
        f"$ should stop at col 14 (before shield at 15), got {player.col}"
    )


def test_dollar_at_rightmost_passable_cell_is_noop():
    """$ from the rightmost passable cell must not move the player."""
    room = _bare_room()
    player = Player(row=3, col=28)

    moved = apply_motion(player, '$', 1, room)

    assert not moved, "$ from rightmost cell should return False"
    assert player.col == 28


def test_dollar_passes_over_floor_key():
    """floor_key entity must not block $; it should reach the rightmost cell."""
    room = _bare_room()
    room.add_entity(Entity(kind='floor_key', row=3, col=15))
    player = Player(row=3, col=1)

    apply_motion(player, '$', 1, room)

    assert player.col == 28, (
        f"$ should pass floor_key and reach col 28, got {player.col}"
    )


def test_dollar_passes_over_goblin():
    """Goblin entity must not block $."""
    room = _bare_room()
    room.add_entity(Entity(kind='goblin', row=3, col=15, max_hp=1, ai='chase'))
    player = Player(row=3, col=1)

    apply_motion(player, '$', 1, room)

    assert player.col == 28, (
        f"$ should pass goblin and reach col 28, got {player.col}"
    )


def test_dollar_lands_on_water_cell():
    """$ scans through water cells (game loop handles the drown check separately)."""
    room = _bare_room()
    room.cells[3][20] = CellType.WATER
    player = Player(row=3, col=1)

    apply_motion(player, '$', 1, room)

    assert player.col == 28, (
        f"$ should move through water and land at col 28, got {player.col}"
    )
    # Confirm cell type at landing is NOT water (player stops at last floor cell)
    # — the water is in the middle, not at the end


def test_dollar_with_count_does_not_crash():
    """2$ must not crash; player lands at rightmost passable cell."""
    room = _bare_room()
    player = Player(row=3, col=1)

    apply_motion(player, '$', 2, room)

    assert player.col == 28, (
        f"2$ should land at col 28, got {player.col}"
    )


# ── 0 motion ──────────────────────────────────────────────────────────────────

def test_zero_stops_before_fog_on_left():
    """0 scanning left must halt at the last non-fog column going leftward."""
    room = _bare_room()
    room.fog_cells = {(3, c) for c in range(1, 8)}
    player = Player(row=3, col=20)

    apply_motion(player, '0', 1, room)

    assert player.col == 8, (
        f"0 should stop at col 8 (first non-fog cell to the left), got {player.col}"
    )


def test_zero_at_leftmost_passable_cell_is_noop():
    """0 from the leftmost passable cell must not move the player."""
    room = _bare_room()
    player = Player(row=3, col=1)

    moved = apply_motion(player, '0', 1, room)

    assert not moved, "0 from leftmost cell should return False"
    assert player.col == 1


# ── ^ motion ──────────────────────────────────────────────────────────────────

def test_caret_lands_on_first_rune():
    """^ must jump to the first rune cluster on the row."""
    room = _bare_room()
    ru = CharRun(row=3, col=8, symbols=('∘', '∘'), kind='ancient')
    room.char_runs.append(ru)
    room.rebuild_indexes()
    player = Player(row=3, col=20)

    apply_motion(player, '^', 1, room)

    assert player.col == 8, (
        f"^ should land at first rune col 8, got {player.col}"
    )


def test_caret_no_runes_falls_back_to_leftmost():
    """^ with no runes on the row must fall back to the leftmost passable column."""
    room = _bare_room()
    player = Player(row=3, col=20)

    apply_motion(player, '^', 1, room)

    assert player.col == 1, (
        f"^ with no runes should fall back to leftmost passable col (1), got {player.col}"
    )


def test_caret_noop_when_already_at_first_rune():
    """^ when already at the first rune should not move the player."""
    room = _bare_room()
    ru = CharRun(row=3, col=5, symbols=('∘',), kind='ancient')
    room.char_runs.append(ru)
    room.rebuild_indexes()
    player = Player(row=3, col=5)

    moved = apply_motion(player, '^', 1, room)

    assert not moved, "^ at first rune position should return False"
    assert player.col == 5


# ── _keystroke_cost ───────────────────────────────────────────────────────────

def test_keystroke_cost_dollar_count_1():
    assert _keystroke_cost(1, '$') == 1


def test_keystroke_cost_dollar_count_3():
    # len('3') + 1 = 2
    assert _keystroke_cost(3, '$') == 2


def test_keystroke_cost_dollar_count_10():
    # len('10') + 1 = 3
    assert _keystroke_cost(10, '$') == 3


def test_keystroke_cost_f_adds_extra():
    """f/F/t/T/gg add 1 extra keystroke (the target character)."""
    assert _keystroke_cost(1, 'f') == 2
    assert _keystroke_cost(1, 'F') == 2
    assert _keystroke_cost(1, 't') == 2
    assert _keystroke_cost(1, 'T') == 2
    assert _keystroke_cost(1, 'gg') == 2


def test_keystroke_cost_hjkl_no_extra():
    """h/j/k/l do NOT add the extra +1 for target char."""
    assert _keystroke_cost(1, 'h') == 1
    assert _keystroke_cost(5, 'l') == 2
