"""Level 13 (id 13) — The Sentence Corridor: dungeon correctness tests.

Tests cover structure, par/budget, and motion-necessity for
) ( (sentence jumps).
"""
import math
import pytest
from engine.world import CellType
from generation.dungeon_gen import (
    build_dungeon_13,
    _dijkstra_par_L12,   # L12's brace/paren Dijkstra, reused here for the ')' necessity check
    _L13_ROWS, _L13_COLS,
    _L13_ENTRY, _L13_EXIT,
    _L13_SENT_ROW,
    _L13_S1_COLS, _L13_S2_COLS, _L13_S3_COLS,
    _L13_SENT_CLUSTERS,
)

SEEDS = [1, 42, 999, 12345, 2**20 + 7]


# ── structural tests ─────────────────────────────────────────────────────────

@pytest.mark.parametrize("seed", SEEDS)
def test_entry_and_exit_passable(seed):
    d = build_dungeon_13(seed)
    room = d.rooms[0]
    r0, c0 = room.spawn_pos
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


# ── sentence section structure ───────────────────────────────────────────────

@pytest.mark.parametrize("seed", SEEDS)
def test_sentence_section_corridors(seed):
    d = build_dungeon_13(seed)
    room = d.rooms[0]
    row = _L13_SENT_ROW
    for seg_cols in (_L13_S1_COLS, _L13_S2_COLS, _L13_S3_COLS):
        for c in range(seg_cols[0], seg_cols[1] + 1):
            assert room.cells[row][c] == CellType.CORRIDOR, (
                f"seed={seed}: sentence section ({row},{c}) is not CORRIDOR"
            )


@pytest.mark.parametrize("seed", SEEDS)
def test_sentence_section_wall_gaps(seed):
    d = build_dungeon_13(seed)
    room = d.rooms[0]
    row = _L13_SENT_ROW
    s1_end = _L13_S1_COLS[1]   # col 10
    s2_beg = _L13_S2_COLS[0]   # col 23
    s2_end = _L13_S2_COLS[1]   # col 36
    s3_beg = _L13_S3_COLS[0]   # col 49
    for c in range(s1_end + 1, s2_beg):   # cols 11-22
        assert room.cells[row][c] == CellType.WALL, (
            f"seed={seed}: gap col ({row},{c}) should be WALL, got {room.cells[row][c]}"
        )
    for c in range(s2_end + 1, s3_beg):   # cols 37-48
        assert room.cells[row][c] == CellType.WALL, (
            f"seed={seed}: gap col ({row},{c}) should be WALL, got {room.cells[row][c]}"
        )


@pytest.mark.parametrize("seed", SEEDS)
def test_sentence_terminators_present(seed):
    """At least 2 rune clusters on sentence row whose last symbol is in '.!?'."""
    d = build_dungeon_13(seed)
    room = d.rooms[0]
    terminators = [
        ru for ru in room.char_runs
        if ru.row == _L13_SENT_ROW and ru.symbols[-1] in '.!?'
    ]
    assert len(terminators) >= 2, (
        f"seed={seed}: expected >= 2 sentence-terminator runes, got {len(terminators)}"
    )


@pytest.mark.parametrize("seed", SEEDS)
def test_fixed_sentence_clusters_present(seed):
    """All three fixed sentence clusters must be present at their specified positions."""
    d = build_dungeon_13(seed)
    room = d.rooms[0]
    for row, col, syms in _L13_SENT_CLUSTERS:
        ru = room.char_run_at(row, col)
        assert ru is not None, f"seed={seed}: no rune at ({row},{col})"
        assert ru.symbols == syms, (
            f"seed={seed}: rune at ({row},{col}) has symbols {ru.symbols!r}, "
            f"expected {syms!r}"
        )
        assert ru.symbols[-1] in '.!?', (
            f"seed={seed}: rune at ({row},{col}) last symbol {ru.symbols[-1]!r} "
            f"not a sentence terminator"
        )


# ── par and budget ────────────────────────────────────────────────────────────

@pytest.mark.parametrize("seed", SEEDS)
def test_par_is_2(seed):
    """The Sentence Corridor always has par=2 (fixed layout, hardcoded path '3)')."""
    d = build_dungeon_13(seed)
    room = d.rooms[0]
    assert room.par == 2, f"seed={seed}: expected par=2, got {room.par}"
    assert room.answer == '3)', f"seed={seed}: expected '3)', got {room.answer!r}"


@pytest.mark.parametrize("seed", SEEDS)
def test_budget_is_ceil_par_times_1_4(seed):
    d = build_dungeon_13(seed)
    room = d.rooms[0]
    assert room.budget == math.ceil(room.par * 1.4), (
        f"seed={seed}: budget={room.budget} but ceil(par*1.4)={math.ceil(room.par * 1.4)}"
    )


# ── answer uses correct motion ───────────────────────────────────────────────

@pytest.mark.parametrize("seed", SEEDS)
def test_answer_uses_paren_motion(seed):
    """`)`  or `(` must appear in room.answer."""
    d = build_dungeon_13(seed)
    room = d.rooms[0]
    tokens = room.answer.split()
    assert any(t in (')', '(') or t.endswith(')') or t.endswith('(')
               for t in tokens), (
        f"seed={seed}: neither ')' nor '(' in answer {room.answer!r}"
    )


# ── motion necessity ─────────────────────────────────────────────────────────

@pytest.mark.parametrize("seed", SEEDS)
def test_paren_required(seed):
    """Dijkstra with ) and ( disabled cannot reach exit within budget.

    Wall gaps between sentence sections (cols 11-22 and 37-48 on row 1)
    block l/h/w counting across sentences; without ), the player is trapped
    in S1 (cols 1-10) and cannot reach the exit at col 49.
    """
    d = build_dungeon_13(seed)
    room = d.rooms[0]
    cost_no_paren = _dijkstra_par_L12(room, disable_brace=True, disable_paren=True)
    assert cost_no_paren is None or cost_no_paren > room.budget, (
        f"seed={seed}: without (/), cost={cost_no_paren} fits in budget={room.budget}; "
        f"paren motions are not required"
    )
