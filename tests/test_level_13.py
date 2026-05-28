"""Level 13 (id 13) — The Void Rift: dungeon correctness tests.

Tests cover structure, par/budget, and motion-necessity for
} { (paragraph jumps).
"""
import math
import pytest
from engine.world import CellType
from generation.dungeon_gen import (
    build_dungeon_13,
    _dijkstra_par_L13,
    _L13_ROWS, _L13_COLS,
    _L13_ENTRY, _L13_EXIT,
    _L13_BLANK_ROW_1,
    _L13_VOID_ROWS_A,
    _L13_PARA1_ROWS, _L13_PARA2_ROWS,
)

SEEDS = [1, 42, 999, 12345, 2**20 + 7]


# ── structural tests ─────────────────────────────────────────────────────────

@pytest.mark.parametrize("seed", SEEDS)
def test_entry_and_exit_passable(seed):
    d = build_dungeon_13(seed)
    room = d.rooms[0]
    r0, c0 = room.entry
    r1, c1 = room.exit_pos
    assert room.cells[r0][c0] == CellType.CORRIDOR, (
        f"seed={seed}: entry ({r0},{c0}) is not CORRIDOR"
    )
    assert room.cells[r1][c1] == CellType.CORRIDOR, (
        f"seed={seed}: exit ({r1},{c1}) is not CORRIDOR"
    )


@pytest.mark.parametrize("seed", SEEDS)
def test_dimensions(seed):
    d = build_dungeon_13(seed)
    room = d.rooms[0]
    assert room.rows == _L13_ROWS, f"seed={seed}: expected {_L13_ROWS} rows, got {room.rows}"
    assert room.cols == _L13_COLS, f"seed={seed}: expected {_L13_COLS} cols, got {room.cols}"


@pytest.mark.parametrize("seed", SEEDS)
def test_exit_entity_at_exit_pos(seed):
    d = build_dungeon_13(seed)
    room = d.rooms[0]
    exit_ents = [e for e in room.entities if e.kind == 'exit']
    assert len(exit_ents) == 1, f"seed={seed}: expected 1 exit entity, got {len(exit_ents)}"
    e = exit_ents[0]
    assert (e.row, e.col) == room.exit_pos, (
        f"seed={seed}: exit entity at ({e.row},{e.col}) != exit_pos {room.exit_pos}"
    )
    assert room.exit_pos == _L13_EXIT, (
        f"seed={seed}: exit_pos {room.exit_pos} != expected {_L13_EXIT}"
    )


# ── blank row (paragraph divider) ────────────────────────────────────────────

@pytest.mark.parametrize("seed", SEEDS)
def test_blank_row_present(seed):
    """Row 9 must have no rune clusters (paragraph divider for } jump)."""
    d = build_dungeon_13(seed)
    room = d.rooms[0]
    for c in range(room.cols):
        ru = room.rune_at(_L13_BLANK_ROW_1, c)
        assert ru is None, (
            f"seed={seed}: unexpected rune at ({_L13_BLANK_ROW_1},{c}) on blank row"
        )


@pytest.mark.parametrize("seed", SEEDS)
def test_blank_row_is_passable(seed):
    d = build_dungeon_13(seed)
    room = d.rooms[0]
    passable = any(room.is_passable(_L13_BLANK_ROW_1, c) for c in range(room.cols))
    assert passable, f"seed={seed}: blank row {_L13_BLANK_ROW_1} has no passable cells"


# ── void barrier rows ─────────────────────────────────────────────────────────

@pytest.mark.parametrize("seed", SEEDS)
def test_void_barriers_block_all_corridor_cols(seed):
    """Each void-barrier row must have a void rune at every corridor cell."""
    d = build_dungeon_13(seed)
    room = d.rooms[0]
    for void_row in _L13_VOID_ROWS_A:
        for c in range(1, room.cols - 1):
            ru = room.rune_at(void_row, c)
            assert ru is not None and ru.kind == 'void', (
                f"seed={seed}: void barrier row {void_row} col {c} has no void rune"
            )


# ── par and budget ────────────────────────────────────────────────────────────

@pytest.mark.parametrize("seed", SEEDS)
def test_par_matches_dijkstra(seed):
    d = build_dungeon_13(seed)
    room = d.rooms[0]
    computed = _dijkstra_par_L13(room, disable_paren=True)
    assert room.par == computed, (
        f"seed={seed}: room.par={room.par} but Dijkstra computed {computed}"
    )


@pytest.mark.parametrize("seed", SEEDS)
def test_budget_is_ceil_par_times_1_4(seed):
    d = build_dungeon_13(seed)
    room = d.rooms[0]
    assert room.budget == math.ceil(room.par * 1.4), (
        f"seed={seed}: budget={room.budget} but ceil(par*1.4)={math.ceil(room.par * 1.4)}"
    )


# ── answer uses correct motion ───────────────────────────────────────────────

@pytest.mark.parametrize("seed", SEEDS)
def test_answer_uses_brace_motion(seed):
    """`}` or `{` must appear in room.answer."""
    d = build_dungeon_13(seed)
    room = d.rooms[0]
    tokens = room.answer.split()
    assert '}' in tokens or '{' in tokens, (
        f"seed={seed}: neither '}}' nor '{{' in answer {room.answer!r}"
    )


# ── motion necessity ─────────────────────────────────────────────────────────

@pytest.mark.parametrize("seed", SEEDS)
def test_brace_required(seed):
    """Dijkstra with } and { disabled cannot reach exit within budget.

    The void barriers in rows 3-8 physically prevent j/k counting from
    crossing into the blank row and Para 2; without }, the player is
    stranded in rows 0-2 and cannot reach the exit.
    """
    d = build_dungeon_13(seed)
    room = d.rooms[0]
    cost_no_brace = _dijkstra_par_L13(room, disable_brace=True, disable_paren=True)
    assert cost_no_brace is None or cost_no_brace > room.budget, (
        f"seed={seed}: without {{/}}, cost={cost_no_brace} fits in budget={room.budget}; "
        f"brace motions are not required"
    )
