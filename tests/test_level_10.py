"""Level 9 (id=9) — The Screen Vault: dungeon correctness tests.

Teaching goal: H/M/L (viewport-relative top/middle/bottom jumps), distinct from
G (which lands on a void row and is punished).  Viewport-filling layout with
three colored floor_keys matched to three colored locked_doors.

The M row is filled with vocab, so M lands on its leftmost rune and the player
must then $ to reach the M key at the right edge — i.e. "M $", not just "M".
"""
import math
import pytest
from engine.world import CellType
from generation.dungeon_gen import (
    build_dungeon_10,
    _dijkstra_par_L10,
    _l10_key_rows,
    _L10_COLS, _L10_DEFAULT_GAME_H,
    _L10_H_KEY_COL, _L10_M_KEY_COL, _L10_L_KEY_COL,
    _L10_DOOR_COLS, _L10_EXIT_COL,
    _L10_SPAWN, _L10_COLORS,
)

SEEDS = [1, 42, 999, 12345, 2**20 + 7]
_GH = _L10_DEFAULT_GAME_H

# The par Dijkstra is moderately expensive, so build each seed's room once and
# share it (these tests only read the room — never mutate it).
_ROOM_CACHE: dict = {}


def _room(seed):
    if seed not in _ROOM_CACHE:
        _ROOM_CACHE[seed] = build_dungeon_10(seed).rooms[0]
    return _ROOM_CACHE[seed]


# ── Structural ────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("seed", SEEDS)
def test_dimensions(seed):
    room = _room(seed)
    assert room.rows == _GH + 4
    assert room.cols == _L10_COLS


@pytest.mark.parametrize("seed", SEEDS)
def test_spawn(seed):
    room = _room(seed)
    assert room.spawn_pos == _L10_SPAWN
    assert room.is_passable(*room.spawn_pos), f"seed={seed}: spawn not passable"


@pytest.mark.parametrize("seed", SEEDS)
def test_exit(seed):
    room = _room(seed)
    exits = [e for e in room.entities if e.kind == 'exit']
    assert len(exits) == 1
    assert (exits[0].row, exits[0].col) == (1, _L10_EXIT_COL) == room.exit_pos


@pytest.mark.parametrize("seed", SEEDS)
def test_three_keys_at_hml_positions(seed):
    room = _room(seed)
    m_row, l_row = _l10_key_rows(_GH)
    keys = {(e.row, e.col): e.tag for e in room.entities if e.kind == 'floor_key'}
    assert set(keys) == {(1, _L10_H_KEY_COL), (m_row, _L10_M_KEY_COL), (l_row, _L10_L_KEY_COL)}
    assert sorted(keys.values()) == sorted(_L10_COLORS)   # each color used once


@pytest.mark.parametrize("seed", SEEDS)
def test_three_doors_colored(seed):
    room = _room(seed)
    doors = {(e.row, e.col): e.tag for e in room.entities if e.kind == 'locked_door'}
    assert set(doors) == {(1, dc) for dc in _L10_DOOR_COLS}
    assert sorted(doors.values()) == sorted(_L10_COLORS)   # each color used once


@pytest.mark.parametrize("seed", SEEDS)
def test_keys_match_doors(seed):
    """Every door color has exactly one matching key color (so it is solvable)."""
    room = _room(seed)
    key_colors  = sorted(e.tag for e in room.entities if e.kind == 'floor_key')
    door_colors = sorted(e.tag for e in room.entities if e.kind == 'locked_door')
    assert key_colors == door_colors == sorted(_L10_COLORS)


@pytest.mark.parametrize("seed", SEEDS)
def test_top_corridor_clear_between_doors_and_exit(seed):
    """No vocab runes on row 1 from the first door through the exit (cols 26-41)."""
    room = _room(seed)
    cols = [ru.col for ru in room.char_runs if ru.row == 1 and 26 <= ru.col <= _L10_EXIT_COL]
    assert cols == [], f"seed={seed}: unexpected row-1 runes at cols {cols}"


@pytest.mark.parametrize("seed", SEEDS)
def test_void_row_is_circles(seed):
    """The row G lands on (L_ROW+3) is filled with standard void runes (○) —
    using G is punished."""
    room = _room(seed)
    _, l_row = _l10_key_rows(_GH)
    void_row = l_row + 3
    voids = [ru for ru in room.char_runs if ru.row == void_row]
    assert voids, f"seed={seed}: no runes on void row {void_row}"
    assert all(ru.kind == 'void' for ru in voids), f"seed={seed}: non-void rune on void row"
    assert all(''.join(ru.symbols) == '○' for ru in voids), f"seed={seed}: void rune is not a ○"


# ── M-key requires M then $ ───────────────────────────────────────────────────

@pytest.mark.parametrize("seed", SEEDS)
def test_M_does_not_reach_key_alone(seed):
    """The M row is filled, so M lands on its leftmost rune (not the M key at
    col 25): the player must follow M with $.  The optimal answer uses both."""
    room = _room(seed)
    m_row, _ = _l10_key_rows(_GH)
    fnb = min(ru.col for ru in room.char_runs if ru.row == m_row)   # where M lands
    assert fnb != _L10_M_KEY_COL, f"seed={seed}: M lands directly on the key (col {fnb})"
    toks = room.answer.split()
    assert 'M' in toks and '$' in toks, f"seed={seed}: answer lacks M/$ {room.answer!r}"


# ── Par / budget ──────────────────────────────────────────────────────────────

@pytest.mark.parametrize("seed", SEEDS)
def test_par_matches_dijkstra(seed):
    room = _room(seed)
    assert room.par == _dijkstra_par_L10(room)


@pytest.mark.parametrize("seed", SEEDS)
def test_budget_is_ceil_par_times_1_4(seed):
    room = _room(seed)
    assert room.budget == math.ceil(room.par * 1.4)


def test_par_is_17_for_seeds():
    """Regression guard: with the M row filled (M then $ to reach the M key) the
    design solves in 17 for the test seeds."""
    pars = {_room(s).par for s in SEEDS}
    assert pars == {17}, f"expected par 17 for all test seeds, got {pars}"


# ── Command usage ─────────────────────────────────────────────────────────────

@pytest.mark.parametrize("seed", SEEDS)
def test_answer_uses_H_M_L(seed):
    """The three keys sit on the viewport top/middle/bottom rows, so the optimal
    solution collects them with H, M, and L."""
    room = _room(seed)
    toks = room.answer.split()
    for cmd in ('H', 'M', 'L'):
        assert cmd in toks, f"seed={seed}: '{cmd}' not in answer {room.answer!r}"


@pytest.mark.parametrize("seed", SEEDS)
def test_answer_avoids_G(seed):
    """G lands on the void row (lethal), so the optimal path never uses bare G."""
    room = _room(seed)
    assert 'G' not in room.answer.split(), f"seed={seed}: G used in answer {room.answer!r}"
