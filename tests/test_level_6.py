"""Level 6 — The Warden's Precision: dungeon correctness and visual-mode undo tests."""
import math
import pytest
from generation.dungeon_gen import build_dungeon_6
from engine.world import Room, RoomType, CellType, RuneCluster, Entity
from engine.player import Player
from engine.budget import Budget
from engine.modes import Mode
from engine.motion import apply_motion
from engine.visual import apply_visual
from main import _pop_history_step, _snapshot


# ── helpers ──────────────────────────────────────────────────────────────────

def _dungeon():
    return build_dungeon_6(0)


def _budget(total=15, spent=0):
    b = Budget(total)
    b.spent = spent
    return b


# ── dungeon structure ─────────────────────────────────────────────────────────

def test_layout_dimensions():
    room = _dungeon().rooms[0]
    assert room.rows == 5
    assert room.cols == 21


def test_entry_position():
    room = _dungeon().rooms[0]
    assert room.entry == (1, 1)


def test_exit_entity_position():
    room = _dungeon().rooms[0]
    exit_ent = next((e for e in room.entities if e.kind == 'exit'), None)
    assert exit_ent is not None
    assert (exit_ent.row, exit_ent.col) == (3, 1)


def test_dynamite_position():
    room = _dungeon().rooms[0]
    dyn = next((e for e in room.entities if e.kind == 'dynamite'), None)
    assert dyn is not None
    assert (dyn.row, dyn.col) == (3, 2)


def test_top_corridor_void_runes_bounded():
    # Voids only appear in row 1 cols 2-19; entry cell (1,1) always clear.
    room = _dungeon().rooms[0]
    assert room.rune_at(1, 1) is None, "entry cell must not have a void rune"
    for col in range(2, 20):
        ru = room.rune_at(1, col)
        if ru is not None:
            assert ru.kind == 'void', f"(1,{col}) non-void rune unexpected"


def test_top_corridor_voids_spawn_at_roughly_60_pct():
    # Over many seeds, void coverage in row 1 should be ~60%.
    counts = []
    for seed in range(50):
        room = build_dungeon_6(seed).rooms[0]
        counts.append(sum(1 for c in range(2, 20) if room.rune_at(1, c) is not None))
    avg = sum(counts) / len(counts)
    assert 7 <= avg <= 13, f"expected ~10.8 voids on average, got {avg:.1f}"


def test_bottom_corridor_void_runes_bounded():
    # Voids only appear in row 3 cols 3-18; exit (3,1), dynamite (3,2), and (3,19) always clear.
    room = _dungeon().rooms[0]
    assert room.rune_at(3, 1) is None, "exit cell must not have a void rune"
    assert room.rune_at(3, 2) is None, "dynamite cell must not have a void rune"
    assert room.rune_at(3, 19) is None, "col 19 of row 3 must always be clear"
    for col in range(3, 19):
        ru = room.rune_at(3, col)
        if ru is not None:
            assert ru.kind == 'void', f"(3,{col}) non-void rune unexpected"


def test_gap_is_passable():
    room = _dungeon().rooms[0]
    assert room.cells[2][18] != CellType.WALL
    assert room.cells[2][19] != CellType.WALL


def test_row2_otherwise_wall():
    room = _dungeon().rooms[0]
    for col in range(0, 18):
        assert room.cells[2][col] == CellType.WALL, f"(2,{col}) should be wall"


def test_budget_and_par():
    room = _dungeon().rooms[0]
    assert room.par == 11
    assert room.budget == math.ceil(11 * 1.4)


# ── visual-mode undo: the anchor bug ─────────────────────────────────────────
#
# Sequence: v $ d   (enter visual at (1,1), extend to (1,19), delete)
# Bug: the undo snapshot captured the cursor position (1,19) and current budget
#      spend (2), so `u` returned the player to col 19 with 2 keystrokes already
#      charged — not to the anchor (1,1) with a clean slate.
# Fix: snapshot uses (row, col) = anchor and spent = value before v was pressed.
#
# These tests build a minimal room with a known void at (1,10) so they are
# independent of the randomised seed used by _dungeon().

def _room_with_void():
    """5×21 room matching Level 6 layout, with a single known void at (1,10)."""
    room = Room(rows=5, cols=21, room_type=RoomType.ENTRY)
    cells = [[CellType.WALL] * 21 for _ in range(5)]
    for c in range(1, 20):
        cells[1][c] = CellType.CORRIDOR
    cells[2][18] = CellType.CORRIDOR
    cells[2][19] = CellType.CORRIDOR
    for c in range(1, 20):
        cells[3][c] = CellType.CORRIDOR
    room.cells = cells
    room.runes.append(RuneCluster(row=1, col=10, symbols=('○',), kind='void'))
    room.entities.append(Entity(kind='exit',     row=3, col=1))
    room.entities.append(Entity(kind='dynamite', row=3, col=2))
    room.entry = (1, 1)
    room.rebuild_indexes()
    return room


def test_visual_delete_undo_restores_to_anchor_not_cursor_end():
    """u after v$d must land the player at (1,1) (anchor), not (1,19) (cursor-end)."""
    room = _room_with_void()
    player = Player(row=1, col=1)
    budget = _budget(spent=0)
    undo_stack, redo_stack = [], []

    pre_v_spent = budget.spent          # 0
    player.mode = Mode.VISUAL
    player.visual_anchor = (1, 1)
    player.visual_start_spent = pre_v_spent
    budget.spend(1)

    apply_motion(player, '$', 1, room)
    budget.spend(1)
    assert player.col == 19

    anchor = player.visual_anchor       # (1, 1)
    cursor = (player.row, player.col)   # (1, 19)

    undo_stack.append(_snapshot(room, player, budget,
                                row=anchor[0], col=anchor[1],
                                spent=player.visual_start_spent))
    apply_visual('d', anchor, cursor, Mode.VISUAL, room, player)
    budget.spend(1)
    player.mode = Mode.NORMAL
    player.visual_anchor = None

    assert player.col == 1, "apply_visual repositions cursor to selection start"
    assert room.rune_at(1, 10) is None, "void rune must be cleared after delete"

    _pop_history_step(undo_stack, redo_stack, room, player, budget)

    assert player.row == 1
    assert player.col == 1, (
        f"undo must return to anchor (1,1), not cursor-end; got col={player.col}"
    )
    assert budget.spent == 0, (
        f"undo must restore pre-v budget (0), got {budget.spent}"
    )
    assert room.rune_at(1, 10) is not None, "void rune must be restored by undo"


def test_visual_delete_undo_restores_dynamite():
    """u after vF!x in bottom corridor must restore the dynamite entity."""
    room = _room_with_void()
    player = Player(row=3, col=19)
    budget = _budget(spent=6)
    undo_stack, redo_stack = [], []

    pre_v_spent = budget.spent
    player.mode = Mode.VISUAL
    player.visual_anchor = (3, 19)
    player.visual_start_spent = pre_v_spent
    budget.spend(1)

    # F! — move cursor left to dynamite at (3,2)
    from engine.motion import _apply_find
    _apply_find(player, 'F', '!', room)
    budget.spend(1)
    assert player.col == 2, f"F! must land on dynamite at col 2, got {player.col}"

    anchor = player.visual_anchor
    cursor = (player.row, player.col)

    undo_stack.append(_snapshot(room, player, budget,
                                row=anchor[0], col=anchor[1],
                                spent=player.visual_start_spent))
    apply_visual('d', anchor, cursor, Mode.VISUAL, room, player)
    budget.spend(1)
    player.mode = Mode.NORMAL
    player.visual_anchor = None

    assert room.entity_at(3, 2) is None or not room.entity_at(3, 2).alive

    _pop_history_step(undo_stack, redo_stack, room, player, budget)

    dyn = room.entity_at(3, 2)
    assert dyn is not None and dyn.alive, "undo must restore the dynamite entity"
    assert player.col == 19, "undo must return to anchor col 19"
    assert budget.spent == pre_v_spent, "undo must restore pre-v budget"
