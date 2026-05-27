"""Level 9 (id=9) — The File Vaults: dungeon correctness tests.

Teaching goal: G (last row), gg (first row), {n}G (specific row).

Layout: 15 rows × 58 cols, wall at row 4 separating top (rows 0-3) and
bottom (rows 5-14) sections.  Two keystones must be collected before the
exit completes:
  KS1 at (14,55) — collected via G then x
  KS2 at (4,28)  — collected by navigating to the wall gap

Optimal path (par = 11):  G x 5G 27h x gg l
  G(1)  → (14,55), x(1) → KS1
  5G(2) → (4,55),  27h(3) → (4,28), x(1) → KS2
  gg(2) → (0,1),   l(1)   → exit at (0,2)

Key cost savings:
  G   beats 14j+54l (1 vs 6 ks) — strictly necessary
  5G  beats 10k     (2 vs 3 ks) — strictly cheaper from row 14
  gg  beats 4k+26h  (3 vs 5 ks) — strictly cheaper to reach exit
"""
import math
import pytest
from engine.world import CellType
from generation.dungeon_gen import (
    build_dungeon_9,
    _dijkstra_par_LGG,
    _LGG_TOTAL_ROWS, _LGG_TOTAL_COLS,
    _LGG_ENTRY, _LGG_EXIT_POS, _LGG_EXIT_ENTITY,
    _LGG_KS1, _LGG_KS2,
    _LGG_WALL_ROW, _LGG_DOOR_COL, _LGG_GAP_COLS,
)

SEEDS = [1, 42, 999, 12345, 2**20 + 7]


# ── Structural tests ──────────────────────────────────────────────────────────

@pytest.mark.parametrize("seed", SEEDS)
def test_entry_and_exit_pos_passable(seed):
    d = build_dungeon_9(seed)
    room = d.rooms[0]
    r0, c0 = room.entry
    r1, c1 = room.exit_pos
    assert room.cells[r0][c0] == CellType.CORRIDOR, (
        f"seed={seed}: entry ({r0},{c0}) is not CORRIDOR"
    )
    assert room.cells[r1][c1] == CellType.CORRIDOR, (
        f"seed={seed}: exit_pos ({r1},{c1}) is not CORRIDOR"
    )


@pytest.mark.parametrize("seed", SEEDS)
def test_dimensions(seed):
    d = build_dungeon_9(seed)
    room = d.rooms[0]
    assert room.rows == _LGG_TOTAL_ROWS, (
        f"seed={seed}: expected {_LGG_TOTAL_ROWS} rows, got {room.rows}"
    )
    assert room.cols == _LGG_TOTAL_COLS, (
        f"seed={seed}: expected {_LGG_TOTAL_COLS} cols, got {room.cols}"
    )


@pytest.mark.parametrize("seed", SEEDS)
def test_exit_entity_at_exit_entity_pos(seed):
    d = build_dungeon_9(seed)
    room = d.rooms[0]
    exit_ents = [e for e in room.entities if e.kind == 'exit']
    assert len(exit_ents) == 1, (
        f"seed={seed}: expected 1 exit entity, got {len(exit_ents)}"
    )
    e = exit_ents[0]
    assert (e.row, e.col) == _LGG_EXIT_ENTITY, (
        f"seed={seed}: exit entity at ({e.row},{e.col}) != {_LGG_EXIT_ENTITY}"
    )


@pytest.mark.parametrize("seed", SEEDS)
def test_exit_entity_not_at_exit_pos(seed):
    """exit entity must be different from exit_pos so G doesn't win immediately."""
    d = build_dungeon_9(seed)
    room = d.rooms[0]
    assert room.exit_pos != _LGG_EXIT_ENTITY, (
        f"seed={seed}: exit_pos {room.exit_pos} must differ from "
        f"exit_entity {_LGG_EXIT_ENTITY}"
    )


# ── Par and budget tests ──────────────────────────────────────────────────────

@pytest.mark.parametrize("seed", SEEDS)
def test_par_matches_dijkstra(seed):
    d = build_dungeon_9(seed)
    room = d.rooms[0]
    computed = _dijkstra_par_LGG(room)
    assert room.par == computed, (
        f"seed={seed}: room.par={room.par} but Dijkstra computed {computed}"
    )


@pytest.mark.parametrize("seed", SEEDS)
def test_budget_is_ceil_par_times_1_4(seed):
    d = build_dungeon_9(seed)
    room = d.rooms[0]
    expected = math.ceil(room.par * 1.4)
    assert room.budget == expected, (
        f"seed={seed}: budget={room.budget} but ceil(par*1.4)={expected}"
    )


# ── Answer path tests ─────────────────────────────────────────────────────────

@pytest.mark.parametrize("seed", SEEDS)
def test_answer_uses_G_to_collect_ks1(seed):
    """The optimal path must use bare G to teleport to exit_pos (KS1 location)."""
    d = build_dungeon_9(seed)
    room = d.rooms[0]
    tokens = room.answer.split()
    assert 'G' in tokens, (
        f"seed={seed}: bare 'G' not in answer {room.answer!r}"
    )


@pytest.mark.parametrize("seed", SEEDS)
def test_answer_uses_nG_from_bottom(seed):
    """The optimal path must use a counted {n}G to jump from row 14 to row 4
    (5G), which is strictly cheaper than 10k (2 vs 3 ks)."""
    d = build_dungeon_9(seed)
    room = d.rooms[0]
    tokens = room.answer.split()
    # Any token matching digit(s)+G (not bare G) counts as {n}G
    nG_tokens = [t for t in tokens if t.endswith('G') and t[:-1].isdigit()]
    assert nG_tokens, (
        f"seed={seed}: no '{{n}}G' token in answer {room.answer!r}"
    )


@pytest.mark.parametrize("seed", SEEDS)
def test_answer_uses_gg(seed):
    """The optimal path must use gg to teleport back to entry — strictly cheaper
    than 4k+26h (3 vs 5 ks) for reaching the exit near (0,2)."""
    d = build_dungeon_9(seed)
    room = d.rooms[0]
    tokens = room.answer.split()
    assert 'gg' in tokens, (
        f"seed={seed}: 'gg' not in answer {room.answer!r}"
    )


# ── Wall layout tests ─────────────────────────────────────────────────────────

def test_wall_row_structure():
    """Row 4 must be wall everywhere except the gap cols (26,27,28)."""
    d = build_dungeon_9(42)
    room = d.rooms[0]
    for c in range(1, _LGG_TOTAL_COLS - 1):
        if c in _LGG_GAP_COLS:
            assert room.cells[_LGG_WALL_ROW][c] == CellType.CORRIDOR, (
                f"Gap col {c} in wall row {_LGG_WALL_ROW} must be CORRIDOR"
            )
        else:
            assert room.cells[_LGG_WALL_ROW][c] == CellType.WALL, (
                f"Col {c} in wall row {_LGG_WALL_ROW} must be WALL"
            )


def test_locked_door_at_gap():
    """locked_door entity must be at (_LGG_WALL_ROW, _LGG_DOOR_COL)."""
    d = build_dungeon_9(42)
    room = d.rooms[0]
    door_ents = [e for e in room.entities if e.kind == 'locked_door']
    assert len(door_ents) == 1, f"Expected 1 locked_door, got {len(door_ents)}"
    e = door_ents[0]
    assert (e.row, e.col) == (_LGG_WALL_ROW, _LGG_DOOR_COL), (
        f"locked_door at ({e.row},{e.col}), expected ({_LGG_WALL_ROW},{_LGG_DOOR_COL})"
    )


def test_keystones_at_correct_positions():
    """KS1 at (14,55) and KS2 at (4,28) must be present."""
    d = build_dungeon_9(42)
    room = d.rooms[0]
    ks_ents = [(e.row, e.col) for e in room.entities if e.kind == 'keystone']
    assert _LGG_KS1 in ks_ents, f"KS1 at {_LGG_KS1} missing; keystones={ks_ents}"
    assert _LGG_KS2 in ks_ents, f"KS2 at {_LGG_KS2} missing; keystones={ks_ents}"
