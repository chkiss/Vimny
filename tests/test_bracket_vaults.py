"""The Bracket Vaults: dungeon correctness tests.

Layout: three-corridor snake (9 rows × 60 cols).  Rows 1 and 5 are corridors whose
( ... ) span is word-filled; rows 2, 3 and 4 are flooded with WATER except the turn
cells and the row-3 bracket landing cells (( col 4, ) col 54).  WATER blocks manual h/l
(is_passable is False), so % is the only way across.  Every snake row (2-5) has a col-1
pocket (unmatched ) + WALL at col 2) that traps a {N}G teleport.  The exit is gated by a
locked door at (5,54) opened with the floor_key at (2,54); the exit sits at (5,55).

Optimal path (par=10):  % j x j % 2j $ p l
  (1,1) % → (1,54) ).  j → (2,54) key, x grabs it.  j → (3,54).  % → (3,4) (.  2j → (5,4) (.
  $ → (5,53) ) [door halts $].  p unlocks the door, stepping onto (5,54).  l → (5,55) EXIT.

Without %: par_no_% = None (the water band is uncrossable by hand).
"""
import math
import pytest
from engine.world import CellType
from generation.dungeon_gen import (
    build_dungeon_bracket_vaults,
    _par_bracket_vaults,
    _BRACKET_VAULTS_ROWS, _BRACKET_VAULTS_COLS, _BRACKET_VAULTS_CORR_ROWS,
    _BRACKET_VAULTS_BRACKET_OPEN, _BRACKET_VAULTS_BRACKET_CLOSE, _BRACKET_VAULTS_CLOSE_R5,
    _BRACKET_VAULTS_ENTRY, _BRACKET_VAULTS_EXIT_POS, _BRACKET_VAULTS_PAR, _BRACKET_VAULTS_ANSWER,
)

from tests import SEEDS


@pytest.mark.parametrize("seed", SEEDS)
def test_entry_and_exit_passable(seed):
    d = build_dungeon_bracket_vaults(seed)
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
    d = build_dungeon_bracket_vaults(seed)
    room = d.rooms[0]
    computed = _par_bracket_vaults(room, use_percent=True)
    assert room.par == computed, (
        f"seed={seed}: room.par={room.par} but Dijkstra computed {computed}"
    )


@pytest.mark.parametrize("seed", SEEDS)
def test_budget_is_ceil_par_times_1_4(seed):
    d = build_dungeon_bracket_vaults(seed)
    room = d.rooms[0]
    assert room.budget == math.ceil(room.par * 1.4), (
        f"seed={seed}: budget={room.budget} != ceil(par*1.4)={math.ceil(room.par * 1.4)}"
    )


@pytest.mark.parametrize("seed", SEEDS)
def test_answer_uses_percent(seed):
    """The optimal answer must contain the % motion."""
    d = build_dungeon_bracket_vaults(seed)
    room = d.rooms[0]
    tokens = room.answer.split()
    assert '%' in tokens, (
        f"seed={seed}: '%' not found in answer {room.answer!r}"
    )


@pytest.mark.parametrize("seed", SEEDS)
def test_bracket_structure_corridor_rows(seed):
    """( must be at col _BRACKET_VAULTS_BRACKET_OPEN and ) at col _BRACKET_VAULTS_BRACKET_CLOSE on each
    corridor row.  Each bracket must be a single-char CharRun."""
    d = build_dungeon_bracket_vaults(seed)
    room = d.rooms[0]
    for r in _BRACKET_VAULTS_CORR_ROWS:
        open_ru = room.char_run_at(r, _BRACKET_VAULTS_BRACKET_OPEN)
        assert open_ru is not None, (
            f"seed={seed}: no rune at ({r},{_BRACKET_VAULTS_BRACKET_OPEN}) — expected '('"
        )
        assert open_ru.symbols == ('(',), (
            f"seed={seed}: rune at ({r},{_BRACKET_VAULTS_BRACKET_OPEN}) symbols={open_ru.symbols}, expected ('(',)"
        )
        close_col = _BRACKET_VAULTS_CLOSE_R5 if r == 5 else _BRACKET_VAULTS_BRACKET_CLOSE
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
    d = build_dungeon_bracket_vaults(seed)
    room = d.rooms[0]
    par_no_pct = _par_bracket_vaults(room, use_percent=False)
    assert par_no_pct is None or par_no_pct > room.budget, (
        f"seed={seed}: par without % = {par_no_pct}, budget = {room.budget}; "
        f"% should be required"
    )


@pytest.mark.parametrize("seed", SEEDS)
def test_exit_entity_at_exit_pos(seed):
    d = build_dungeon_bracket_vaults(seed)
    room = d.rooms[0]
    exit_ents = [e for e in room.entities if e.kind == 'exit']
    assert len(exit_ents) == 1, f"seed={seed}: expected 1 exit entity, got {len(exit_ents)}"
    e = exit_ents[0]
    assert (e.row, e.col) == room.exit_pos, (
        f"seed={seed}: exit entity at ({e.row},{e.col}) != exit_pos {room.exit_pos}"
    )


@pytest.mark.parametrize("seed", SEEDS)
def test_key_and_door_gate_the_exit(seed):
    """Exactly one floor_key (at KEY_POS) and one locked_door (at DOOR_POS, one cell left of
    the exit) must gate the exit — the mechanism that makes par the true minimum."""
    from generation.dungeon_gen import _BRACKET_VAULTS_KEY_POS, _BRACKET_VAULTS_DOOR_POS
    d = build_dungeon_bracket_vaults(seed)
    room = d.rooms[0]
    keys  = [e for e in room.entities if e.kind == 'floor_key']
    doors = [e for e in room.entities if e.kind == 'locked_door']
    assert len(keys) == 1 and (keys[0].row, keys[0].col) == _BRACKET_VAULTS_KEY_POS
    assert len(doors) == 1 and (doors[0].row, doors[0].col) == _BRACKET_VAULTS_DOOR_POS
    assert _BRACKET_VAULTS_DOOR_POS == (room.exit_pos[0], room.exit_pos[1] - 1)


@pytest.mark.parametrize("seed", SEEDS)
def test_outer_paren_pair_matches_row1(seed):
    """% from ( col _BRACKET_VAULTS_BRACKET_OPEN on row 1 must jump to ) col _BRACKET_VAULTS_BRACKET_CLOSE."""
    d = build_dungeon_bracket_vaults(seed)
    room = d.rooms[0]
    # Simulate what _par_bracket_vaults's _pct() does for row 1 at BRACKET_OPEN.
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
    c = _BRACKET_VAULTS_BRACKET_OPEN
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
    assert target == _BRACKET_VAULTS_BRACKET_CLOSE, (
        f"seed={seed}: % from ( col {c} row {row} should jump to col {_BRACKET_VAULTS_BRACKET_CLOSE}, "
        f"got {target}"
    )


# Anti-teleport pocket on every snake row: col 1 = CORRIDOR (holds an unmatched ) glyph),
# col 2 = WALL. These exempt cols 1-2 from the water-barrier invariants below.
_POCKET_CORRIDOR = 1
_POCKET_WALL     = 2


@pytest.mark.parametrize("seed", SEEDS)
def test_water_barrier_on_row3(seed):
    """Row 3 must be WATER at all cols except the two bracket cells (CORRIDOR, so % can
    land on them) and the col-1/col-2 anti-teleport pocket."""
    d = build_dungeon_bracket_vaults(seed)
    room = d.rooms[0]
    row = 3
    for c in range(1, _BRACKET_VAULTS_COLS - 1):
        if c == _POCKET_CORRIDOR:
            want = CellType.CORRIDOR
        elif c == _POCKET_WALL:
            want = CellType.WALL
        elif c == _BRACKET_VAULTS_BRACKET_OPEN or c == _BRACKET_VAULTS_BRACKET_CLOSE:
            want = CellType.CORRIDOR
        else:
            want = CellType.WATER
        assert room.cells[row][c] == want, (
            f"seed={seed}: ({row},{c}) should be {want}, got {room.cells[row][c]}"
        )


@pytest.mark.parametrize("seed", SEEDS)
def test_water_gap_rows_2_and_4(seed):
    """Rows 2 and 4 must be WATER except their single CORRIDOR turn cell (col 54 on row 2,
    col 4 on row 4) and the col-1/col-2 anti-teleport pocket."""
    d = build_dungeon_bracket_vaults(seed)
    room = d.rooms[0]
    for row, turn_col in {2: _BRACKET_VAULTS_BRACKET_CLOSE, 4: _BRACKET_VAULTS_BRACKET_OPEN}.items():
        for c in range(1, _BRACKET_VAULTS_COLS - 1):
            if c == _POCKET_CORRIDOR:
                want = CellType.CORRIDOR
            elif c == _POCKET_WALL:
                want = CellType.WALL
            elif c == turn_col:
                want = CellType.CORRIDOR
            else:
                want = CellType.WATER
            assert room.cells[row][c] == want, (
                f"seed={seed}: ({row},{c}) should be {want}, got {room.cells[row][c]}"
            )


@pytest.mark.parametrize("seed", SEEDS)
def test_corridor_rows_carved(seed):
    """Rows 1 and 5 must be CORRIDOR for cols 1..COLS-2, except the row-5 anti-teleport
    pocket WALL at col 2 (row 3 is water except its two bracket cells — see
    test_water_barrier_on_row3). Row 1 has no pocket."""
    d = build_dungeon_bracket_vaults(seed)
    room = d.rooms[0]
    walls = {(5, _POCKET_WALL)}            # stone plug sealing the (5,1) teleport pocket
    for r in (1, 5):
        for c in range(1, _BRACKET_VAULTS_COLS - 1):
            want = CellType.WALL if (r, c) in walls else CellType.CORRIDOR
            assert room.cells[r][c] == want, (
                f"seed={seed}: row {r} col {c} should be {want}, got {room.cells[r][c]}"
            )


def test_par_is_correct():
    """Sanity check: par=_BRACKET_VAULTS_PAR=10 and answer matches the constant for all seeds.

    The optimal path is: % j x j % 2j $ p l (10 ks)
      (1,1) % → (1,54).  j → (2,54) key, x grabs it.  j → (3,54).  % → (3,4).  2j → (5,4).
      $ → (5,53) ) [door halts $].  p unlocks the door, stepping onto (5,54).  l → (5,55) EXIT.
    """
    for seed in SEEDS:
        d = build_dungeon_bracket_vaults(seed)
        room = d.rooms[0]
        assert room.par == _BRACKET_VAULTS_PAR, (
            f"seed={seed}: expected par={_BRACKET_VAULTS_PAR}, got {room.par}"
        )
        assert room.answer == _BRACKET_VAULTS_ANSWER, (
            f"seed={seed}: expected answer={_BRACKET_VAULTS_ANSWER!r}, got {room.answer!r}"
        )


def test_room_dimensions():
    """Room must be exactly _BRACKET_VAULTS_ROWS × _BRACKET_VAULTS_COLS."""
    d = build_dungeon_bracket_vaults(42)
    room = d.rooms[0]
    assert room.rows == _BRACKET_VAULTS_ROWS, f"expected {_BRACKET_VAULTS_ROWS} rows, got {room.rows}"
    assert room.cols == _BRACKET_VAULTS_COLS, f"expected {_BRACKET_VAULTS_COLS} cols, got {room.cols}"


@pytest.mark.parametrize("seed", SEEDS)
def test_moat_and_decoy_goblin_pit(seed):
    """Below the snake: a full-water moat (row 6) seals off a decoy corridor (row 7)
    that holds goblins — so G/L land there, not on the (interior) exit row."""
    from generation.dungeon_gen import (_BRACKET_VAULTS_MOAT_ROW, _BRACKET_VAULTS_DECOY_ROW,
                                        _BRACKET_VAULTS_DECOY_GOBLINS)
    d = build_dungeon_bracket_vaults(seed)
    room = d.rooms[0]
    for c in range(1, _BRACKET_VAULTS_COLS - 1):
        assert room.cells[_BRACKET_VAULTS_MOAT_ROW][c] == CellType.WATER   # the moat seals the pit
        assert room.cells[_BRACKET_VAULTS_DECOY_ROW][c] == CellType.CORRIDOR
    pit = {e.col for e in room.entities if e.kind == 'goblin' and e.row == _BRACKET_VAULTS_DECOY_ROW}
    assert pit == set(_BRACKET_VAULTS_DECOY_GOBLINS)
    # the exit row (5) is NOT the last row anymore → G/L can't teleport onto it
    assert _BRACKET_VAULTS_EXIT_POS[0] < _BRACKET_VAULTS_DECOY_ROW


@pytest.mark.parametrize("path", [
    'G % l', 'G w l', 'L % l', 'L w l',     # G/L land in the decoy goblin pit (row 7)
    '6G $ l', '6G f) l',                     # {N}G onto a snake rung → col-1 pocket / decoy pit
    '5G j $ p l',                            # reaches the door area but has no key
    '3G x 5G j $ p l', '3G x 4G 2j $ p l',   # {N}G can't reach the key (lands in a pocket)
])
def test_teleport_cheese_no_longer_wins(path):
    """Regression: par is the true minimum (10). No teleport beats the % snake.

    G/L land in the decoy goblin pit; every {N}G lands in a snake row's col-1 WALL pocket
    (so it can't reach the snake OR the key at (2,54)); and the locked door means reaching
    the exit cell without the key is impossible. So none of these routes may complete it.
    """
    import main
    from blessed import Terminal
    from blessed.keyboard import Keystroke
    for fn in ('render_all', '_win_animation', '_fireworks_animation', '_starfield_victory',
               '_void_fall_animation', '_drown_animation', '_heart_container_animation',
               '_play_void_falls', '_unlock_animation'):
        setattr(main, fn, lambda *a, **k: None)
    d = build_dungeon_bracket_vaults(42)
    keys = [Keystroke(c) for tok in path.split() for c in tok]
    it = iter(keys + [Keystroke(':'), Keystroke('w'), Keystroke('q'), Keystroke('\r')])
    term = Terminal(force_styling=False)
    term.inkey = lambda *a, **k: next(it, Keystroke(''))
    res = main.run_dungeon(term, 'bracket_vaults', {}, player_name='p', _dungeon=d)
    assert not (res and res.get('won')), f"{path!r} should not complete the level, but won"
