"""Level 13 (id 13) — The Runic Archives: dungeon correctness tests.

Tests cover structure, par/budget, and motion-necessity for
{ } ( ) (paragraph and sentence jumps).
"""
import math
import pytest
from engine.world import CellType
from generation.dungeon_gen import (
    build_dungeon_13,
    _dijkstra_par_L12,
    _L12_ROWS, _L12_COLS,
    _L12_ENTRY, _L12_EXIT,
    _L12_BLANK_ROW_1, _L12_BLANK_ROW_2,
    _L12_SENT_ROW,
    _L12_VOID_ROWS_A, _L12_VOID_ROWS_B,
    _L12_S1_COLS, _L12_S2_COLS, _L12_S3_COLS,
    _L12_SENT_CLUSTERS,
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
    assert room.rows == _L12_ROWS, f"seed={seed}: expected {_L12_ROWS} rows, got {room.rows}"
    assert room.cols == _L12_COLS, f"seed={seed}: expected {_L12_COLS} cols, got {room.cols}"


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
    assert room.exit_pos == _L12_EXIT, (
        f"seed={seed}: exit_pos {room.exit_pos} != expected {_L12_EXIT}"
    )


# ── blank rows (paragraph dividers) ─────────────────────────────────────────

@pytest.mark.parametrize("seed", SEEDS)
def test_blank_rows_present(seed):
    """Rows 9 and 19 must have no rune clusters (paragraph dividers for } {}.)"""
    d = build_dungeon_13(seed)
    room = d.rooms[0]
    for blank_row in (_L12_BLANK_ROW_1, _L12_BLANK_ROW_2):
        for c in range(room.cols):
            ru = room.rune_at(blank_row, c)
            assert ru is None, (
                f"seed={seed}: unexpected rune at ({blank_row},{c}) on blank row {blank_row}"
            )


@pytest.mark.parametrize("seed", SEEDS)
def test_blank_rows_are_passable(seed):
    d = build_dungeon_13(seed)
    room = d.rooms[0]
    for blank_row in (_L12_BLANK_ROW_1, _L12_BLANK_ROW_2):
        passable = any(room.is_passable(blank_row, c) for c in range(room.cols))
        assert passable, f"seed={seed}: blank row {blank_row} has no passable cells"


# ── void barrier rows ─────────────────────────────────────────────────────────

@pytest.mark.parametrize("seed", SEEDS)
def test_void_barriers_block_all_corridor_cols(seed):
    """Each void-barrier row must have a void rune at every corridor cell."""
    d = build_dungeon_13(seed)
    room = d.rooms[0]
    for void_row in _L12_VOID_ROWS_A + _L12_VOID_ROWS_B:
        for c in range(1, room.cols - 1):
            ru = room.rune_at(void_row, c)
            assert ru is not None and ru.kind == 'void', (
                f"seed={seed}: void barrier row {void_row} col {c} has no void rune"
            )


# ── sentence section structure ───────────────────────────────────────────────

@pytest.mark.parametrize("seed", SEEDS)
def test_sentence_section_corridors(seed):
    d = build_dungeon_13(seed)
    room = d.rooms[0]
    row = _L12_SENT_ROW
    for seg_cols in (_L12_S1_COLS, _L12_S2_COLS, _L12_S3_COLS):
        for c in range(seg_cols[0], seg_cols[1] + 1):
            assert room.cells[row][c] == CellType.CORRIDOR, (
                f"seed={seed}: sentence section ({row},{c}) is not CORRIDOR"
            )


@pytest.mark.parametrize("seed", SEEDS)
def test_sentence_section_wall_gaps(seed):
    d = build_dungeon_13(seed)
    room = d.rooms[0]
    row = _L12_SENT_ROW
    s1_end  = _L12_S1_COLS[1]   # col 10
    s2_beg  = _L12_S2_COLS[0]   # col 23
    s2_end  = _L12_S2_COLS[1]   # col 36
    s3_beg  = _L12_S3_COLS[0]   # col 49
    for c in range(s1_end + 1, s2_beg):     # cols 11-22
        assert room.cells[row][c] == CellType.WALL, (
            f"seed={seed}: gap col ({row},{c}) should be WALL, got {room.cells[row][c]}"
        )
    for c in range(s2_end + 1, s3_beg):     # cols 37-48
        assert room.cells[row][c] == CellType.WALL, (
            f"seed={seed}: gap col ({row},{c}) should be WALL, got {room.cells[row][c]}"
        )


@pytest.mark.parametrize("seed", SEEDS)
def test_sentence_terminators_present(seed):
    """At least 2 rune clusters on sentence row whose last symbol is in '.!?'."""
    d = build_dungeon_13(seed)
    room = d.rooms[0]
    terminators = [
        ru for ru in room.runes
        if ru.row == _L12_SENT_ROW and ru.symbols[-1] in '.!?'
    ]
    assert len(terminators) >= 2, (
        f"seed={seed}: expected >= 2 sentence-terminator runes, got {len(terminators)}"
    )


@pytest.mark.parametrize("seed", SEEDS)
def test_fixed_sentence_clusters_present(seed):
    """All three fixed sentence clusters must be present at their specified positions."""
    d = build_dungeon_13(seed)
    room = d.rooms[0]
    for row, col, syms in _L12_SENT_CLUSTERS:
        ru = room.rune_at(row, col)
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
def test_par_matches_dijkstra(seed):
    d = build_dungeon_13(seed)
    room = d.rooms[0]
    computed = _dijkstra_par_L12(room)
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


# ── answer uses correct motions ──────────────────────────────────────────────

@pytest.mark.parametrize("seed", SEEDS)
def test_answer_uses_brace_motion(seed):
    """`}` or `{` must appear in room.answer."""
    d = build_dungeon_13(seed)
    room = d.rooms[0]
    tokens = room.answer.split()
    assert '}' in tokens or '{' in tokens, (
        f"seed={seed}: neither '}}' nor '{{' in answer {room.answer!r}"
    )


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
def test_brace_required(seed):
    """Dijkstra with } and { disabled cannot reach exit within budget.

    The void barriers in rows 3-8 and 12-18 physically prevent j/k counting
    from crossing between paragraph sections; without }, the player is stranded
    in rows 0-2 and cannot reach the sentence section.
    """
    d = build_dungeon_13(seed)
    room = d.rooms[0]
    cost_no_brace = _dijkstra_par_L12(room, disable_brace=True)
    assert cost_no_brace is None or cost_no_brace > room.budget, (
        f"seed={seed}: without {{/}}, cost={cost_no_brace} fits in budget={room.budget}; "
        f"brace motions are not required"
    )


@pytest.mark.parametrize("seed", SEEDS)
def test_paren_required(seed):
    """Dijkstra with ) and ( disabled cannot reach exit within budget.

    Wall gaps between sentence sections (cols 11-22 and 37-48 on row 20) block
    l/h/W/w counting across sentences; without ), the player is trapped in the
    first sentence section (S1, cols 1-10) and cannot reach the exit at col 49.
    """
    d = build_dungeon_13(seed)
    room = d.rooms[0]
    cost_no_paren = _dijkstra_par_L12(room, disable_paren=True)
    assert cost_no_paren is None or cost_no_paren > room.budget, (
        f"seed={seed}: without (/), cost={cost_no_paren} fits in budget={room.budget}; "
        f"paren motions are not required"
    )
