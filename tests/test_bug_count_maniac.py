"""The Count Maniac — spams large counts everywhere.

Uncovers: count parsing edge cases (30l, 0 ambiguity), motion clamping at
room boundaries, and _keystroke_cost formula for extreme counts.
"""
import pytest
from engine.vim_parser import parse
from engine.modes import Mode
from engine.world import Room, RoomType, CellType
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
    room.entry    = (3, 1)
    room.exit_pos = (3, 28)
    room.fog_cells = set()
    room.rebuild_indexes()
    return room


# ── Parser: count + motion ────────────────────────────────────────────────────

def test_30l_parses_as_count_30():
    """30l must parse as count=30, motion='l' (regression: was split as '3','0','l')."""
    action, remaining = parse('30l', Mode.NORMAL)
    assert action == {'type': 'motion', 'motion': 'l', 'count': 30}
    assert remaining == ''


def test_100j_parses_as_count_100():
    action, remaining = parse('100j', Mode.NORMAL)
    assert action == {'type': 'motion', 'motion': 'j', 'count': 100}
    assert remaining == ''


def test_9999h_parses_as_count_9999():
    action, remaining = parse('9999h', Mode.NORMAL)
    assert action == {'type': 'motion', 'motion': 'h', 'count': 9999}
    assert remaining == ''


def test_20l_trailing_zero_parses_correctly():
    """20l must parse as count=20, not count=2 + motion='0' then 'l'."""
    action, remaining = parse('20l', Mode.NORMAL)
    assert action == {'type': 'motion', 'motion': 'l', 'count': 20}
    assert remaining == ''


def test_300j_multiple_trailing_zeros():
    action, remaining = parse('300j', Mode.NORMAL)
    assert action == {'type': 'motion', 'motion': 'j', 'count': 300}
    assert remaining == ''


def test_0_alone_is_motion_not_count():
    """'0' alone must parse as the go-to-start-of-line motion, not a count digit."""
    action, remaining = parse('0', Mode.NORMAL)
    assert action == {'type': 'motion', 'motion': '0', 'count': 1}
    assert remaining == ''


def test_10_without_motion_is_incomplete():
    """'10' with no motion yet must return (None, '10') — still awaiting input."""
    action, remaining = parse('10', Mode.NORMAL)
    assert action is None
    assert remaining == '10'


def test_f_with_count_parses_correctly():
    """3fa must parse as count=3 f-motion with target 'a'."""
    action, remaining = parse('3fa', Mode.NORMAL)
    assert action == {'type': 'motion', 'motion': 'f', 'target': 'a', 'count': 3}
    assert remaining == ''


def test_gg_with_count_parses_correctly():
    """5gg must parse as count=5, motion='gg'."""
    action, remaining = parse('5gg', Mode.NORMAL)
    assert action == {'type': 'motion', 'motion': 'gg', 'count': 5}
    assert remaining == ''


# ── Motion clamping at room boundaries ───────────────────────────────────────

def test_99l_clamps_to_right_boundary():
    """99l must stop at the rightmost passable cell, not go out of bounds."""
    room = _bare_room()
    player = Player(row=3, col=1)

    apply_motion(player, 'l', 99, room)

    assert player.col == 28, f"99l should stop at col 28, got {player.col}"


def test_99h_clamps_to_left_boundary():
    room = _bare_room()
    player = Player(row=3, col=28)

    apply_motion(player, 'h', 99, room)

    assert player.col == 1, f"99h should stop at col 1, got {player.col}"


def test_99j_clamps_to_bottom_boundary():
    """99j must stop at the last floor row (row 5 in a 7-row room)."""
    room = _bare_room()
    player = Player(row=1, col=10)

    apply_motion(player, 'j', 99, room)

    assert player.row == 5, f"99j should stop at row 5, got {player.row}"


def test_99k_clamps_to_top_boundary():
    room = _bare_room()
    player = Player(row=5, col=10)

    apply_motion(player, 'k', 99, room)

    assert player.row == 1, f"99k should stop at row 1, got {player.row}"


def test_count_1_l_normal_step():
    """Sanity: count=1 l moves one cell right."""
    room = _bare_room()
    player = Player(row=3, col=5)

    apply_motion(player, 'l', 1, room)

    assert player.col == 6


# ── _keystroke_cost formula ───────────────────────────────────────────────────

def test_keystroke_cost_count_1():
    assert _keystroke_cost(1) == 1


def test_keystroke_cost_count_5():
    # len('5') + 1 = 2
    assert _keystroke_cost(5) == 2


def test_keystroke_cost_count_9():
    assert _keystroke_cost(9) == 2


def test_keystroke_cost_count_10():
    # len('10') + 1 = 3
    assert _keystroke_cost(10) == 3


def test_keystroke_cost_count_99():
    # len('99') + 1 = 3
    assert _keystroke_cost(99) == 3


def test_keystroke_cost_count_100():
    # len('100') + 1 = 4
    assert _keystroke_cost(100) == 4


def test_keystroke_cost_count_999():
    # len('999') + 1 = 4
    assert _keystroke_cost(999) == 4


def test_keystroke_cost_count_1000():
    # len('1000') + 1 = 5
    assert _keystroke_cost(1000) == 5
