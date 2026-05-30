"""Level 10 (id=10) — The Bracket Vaults: dungeon correctness tests.

Layout: three-corridor snake (7 rows × 60 cols).  Rows 1 and 5 are open
corridors; rows 2, 3 and 4 are flooded with WATER except the turn cells and the
row-3 bracket landing cells (( col 4, ) col 54).  WATER blocks manual h/l
(is_passable is False), so % is the only way across.  Row 5's ) is at col 53
with the exit one cell right at (5,54).

Optimal path (par=8):  % 2j % 2j % l
  (1,1): % → (1,54) ).  2j → (3,54).  % → (3,4) (.  2j → (5,4) (.
  % → (5,53) ).  l → (5,54) EXIT.

Without %: par_no_% = None (the water band is uncrossable by hand).
"""
import math
import pytest
from engine.world import CellType
from generation.dungeon_gen import (
    build_dungeon_10,
    _dijkstra_par_L11,
    _L11_ROWS, _L11_COLS, _L11_CORR_ROWS,
    _L11_BRACKET_OPEN, _L11_BRACKET_CLOSE, _L11_CLOSE_R5,
    _L11_ENTRY, _L11_EXIT_POS, _L11_PAR, _L11_ANSWER,
)

SEEDS = [1, 42, 999, 12345, 2**20 + 7]


@pytest.mark.parametrize("seed", SEEDS)
def test_entry_and_exit_passable(seed):
    d = build_dungeon_10(seed)
    room = d.rooms[0]
    r0, c0 = room.spawn_pos
    r1, c1 = room.exit_pos
    assert room.cells[r0][c0] == CellType.CORRIDOR, (
        f"seed={seed}: entry {room.spawn_pos} is not CORRIDOR"
    )
    assert room.cells[r1][c1] == CellType.CORRIDOR, (
        f"seed={seed}: exit {room.exit_pos} is not CORRIDOR"
    )


@pytest.mark.parametrize("seed", SEEDS)
def test_par_matches_dijkstra(seed):
    d = build_dungeon_10(seed)
    room = d.rooms[0]
    computed = _dijkstra_par_L11(room, use_percent=True)
    assert room.par == computed, (
        f"seed={seed}: room.par={room.par} but Dijkstra computed {computed}"
    )


@pytest.mark.parametrize("seed", SEEDS)
def test_budget_is_ceil_par_times_1_4(seed):
    d = build_dungeon_10(seed)
    room = d.rooms[0]
    assert room.budget == math.ceil(room.par * 1.4), (
        f"seed={seed}: budget={room.budget} != ceil(par*1.4)={math.ceil(room.par * 1.4)}"
    )


@pytest.mark.parametrize("seed", SEEDS)
def test_answer_uses_percent(seed):
    """The optimal answer must contain the % motion."""
    d = build_dungeon_10(seed)
    room = d.rooms[0]
    tokens = room.answer.split()
    assert '%' in tokens, (
        f"seed={seed}: '%' not found in answer {room.answer!r}"
    )


@pytest.mark.parametrize("seed", SEEDS)
def test_bracket_structure_corridor_rows(seed):
    """( must be at col _L11_BRACKET_OPEN and ) at col _L11_BRACKET_CLOSE on each
    corridor row.  Each bracket must be a single-char CharRun."""
    d = build_dungeon_10(seed)
    room = d.rooms[0]
    for r in _L11_CORR_ROWS:
        open_ru = room.char_run_at(r, _L11_BRACKET_OPEN)
        assert open_ru is not None, (
            f"seed={seed}: no rune at ({r},{_L11_BRACKET_OPEN}) — expected '('"
        )
        assert open_ru.symbols == ('(',), (
            f"seed={seed}: rune at ({r},{_L11_BRACKET_OPEN}) symbols={open_ru.symbols}, expected ('(',)"
        )
        close_col = _L11_CLOSE_R5 if r == 5 else _L11_BRACKET_CLOSE
        close_ru = room.char_run_at(r, close_col)
        assert close_ru is not None, (
            f"seed={seed}: no rune at ({r},{close_col}) — expected ')'"
        )
        assert close_ru.symbols == (')',), (
            f"seed={seed}: rune at ({r},{close_col}) symbols={close_ru.symbols}, expected (')',)"
        )


@pytest.mark.parametrize("seed", SEEDS)
def test_percent_required(seed):
    """BFS with % disabled cannot reach the exit within budget.

    The water band on rows 2-4 makes it impossible to cross without %,
    so par_no_% is None (no path exists).
    """
    d = build_dungeon_10(seed)
    room = d.rooms[0]
    par_no_pct = _dijkstra_par_L11(room, use_percent=False)
    assert par_no_pct is None or par_no_pct > room.budget, (
        f"seed={seed}: par without % = {par_no_pct}, budget = {room.budget}; "
        f"% should be required"
    )


@pytest.mark.parametrize("seed", SEEDS)
def test_exit_entity_at_exit_pos(seed):
    d = build_dungeon_10(seed)
    room = d.rooms[0]
    exit_ents = [e for e in room.entities if e.kind == 'exit']
    assert len(exit_ents) == 1, f"seed={seed}: expected 1 exit entity, got {len(exit_ents)}"
    e = exit_ents[0]
    assert (e.row, e.col) == room.exit_pos, (
        f"seed={seed}: exit entity at ({e.row},{e.col}) != exit_pos {room.exit_pos}"
    )


@pytest.mark.parametrize("seed", SEEDS)
def test_outer_paren_pair_matches_row1(seed):
    """% from ( col _L11_BRACKET_OPEN on row 1 must jump to ) col _L11_BRACKET_CLOSE."""
    d = build_dungeon_10(seed)
    room = d.rooms[0]
    # Simulate what _dijkstra_par_L11's _pct() does for row 1 at BRACKET_OPEN.
    _PAIRS_OPEN  = {'(': ')', '[': ']', '{': '}'}
    _PAIRS_CLOSE = {')': '(', ']': '[', '}': '{'}

    def _bracket_here(r, c):
        ru = room.char_run_at(r, c)
        if ru is not None:
            ch = ru.symbols[c - ru.col]
            if ch in _PAIRS_OPEN or ch in _PAIRS_CLOSE:
                return ch
        return None

    row = 1
    c = _L11_BRACKET_OPEN
    bch = _bracket_here(row, c)
    assert bch == '(', f"seed={seed}: expected '(' at ({row},{c}), got {bch!r}"
    # Scan forward for matching ')'
    want = _PAIRS_OPEN['(']
    depth = 0
    target = None
    for cc in range(c, room.cols):
        if room.cells[row][cc] in (CellType.WALL,):
            break
        b = _bracket_here(row, cc)
        if b == '(':
            depth += 1
        elif b == ')':
            depth -= 1
            if depth == 0:
                target = cc
                break
    assert target == _L11_BRACKET_CLOSE, (
        f"seed={seed}: % from ( col {c} row {row} should jump to col {_L11_BRACKET_CLOSE}, "
        f"got {target}"
    )


@pytest.mark.parametrize("seed", SEEDS)
def test_water_barrier_on_row3(seed):
    """Row 3 must be WATER at all cols except the two bracket cells (which stay
    CORRIDOR so % can land on them)."""
    d = build_dungeon_10(seed)
    room = d.rooms[0]
    row = 3
    for c in range(1, _L11_COLS - 1):
        if c == _L11_BRACKET_OPEN or c == _L11_BRACKET_CLOSE:
            assert room.cells[row][c] == CellType.CORRIDOR, (
                f"seed={seed}: bracket cell ({row},{c}) should be CORRIDOR, got {room.cells[row][c]}"
            )
        else:
            assert room.cells[row][c] == CellType.WATER, (
                f"seed={seed}: ({row},{c}) should be WATER (water barrier), got {room.cells[row][c]}"
            )


@pytest.mark.parametrize("seed", SEEDS)
def test_water_gap_rows_2_and_4(seed):
    """Rows 2 and 4 must be WATER except their single CORRIDOR turn cell
    (col 54 on row 2, col 4 on row 4)."""
    d = build_dungeon_10(seed)
    room = d.rooms[0]
    for row, turn_col in {2: _L11_BRACKET_CLOSE, 4: _L11_BRACKET_OPEN}.items():
        for c in range(1, _L11_COLS - 1):
            want = CellType.CORRIDOR if c == turn_col else CellType.WATER
            assert room.cells[row][c] == want, (
                f"seed={seed}: ({row},{c}) should be {want}, got {room.cells[row][c]}"
            )


@pytest.mark.parametrize("seed", SEEDS)
def test_corridor_rows_carved(seed):
    """Rows 1 and 5 must be CORRIDOR for cols 1..COLS-2 (row 3 is now water
    except its two bracket cells — see test_water_barrier_on_row3)."""
    d = build_dungeon_10(seed)
    room = d.rooms[0]
    for r in (1, 5):
        for c in range(1, _L11_COLS - 1):
            assert room.cells[r][c] == CellType.CORRIDOR, (
                f"seed={seed}: row {r} col {c} should be CORRIDOR"
            )


def test_par_is_correct():
    """Sanity check: par=_L11_PAR=8 and answer matches the constant for all seeds.

    The optimal path is: % 2j % 2j % l (8 ks)
      (1,1): % → ) col 54.  2j → (3,54).  % → (3,4).  2j → (5,4).
      % → (5,53) ).  l → (5,54) EXIT.
    """
    for seed in SEEDS:
        d = build_dungeon_10(seed)
        room = d.rooms[0]
        assert room.par == _L11_PAR, (
            f"seed={seed}: expected par={_L11_PAR}, got {room.par}"
        )
        assert room.answer == _L11_ANSWER, (
            f"seed={seed}: expected answer={_L11_ANSWER!r}, got {room.answer!r}"
        )


def test_room_dimensions():
    """Room must be exactly _L11_ROWS × _L11_COLS."""
    d = build_dungeon_10(42)
    room = d.rooms[0]
    assert room.rows == _L11_ROWS, f"expected {_L11_ROWS} rows, got {room.rows}"
    assert room.cols == _L11_COLS, f"expected {_L11_COLS} cols, got {room.cols}"
