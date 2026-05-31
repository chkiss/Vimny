"""Level 8 (id=8) — The Lineheads: dungeon correctness tests.

Teaching goal: G (last line), gg (first line), {n}G (nth line).

A fixed 16×11 vertical shaft (restored from an admin design layout): the exit is
on the top row behind two locked doors; the two keys are buried near the top and
bottom of a 2-wide left shaft, so the solve rides G/gg/{n}G up and down to fetch
a key, open a door, and repeat.  The layout is seed-independent.
"""
import math
import pytest
from engine.world import CellType
from generation.dungeon_gen import (
    build_dungeon_lineheads,
    _par_lineheads,
    _LINEHEADS_ROWS, _LINEHEADS_COLS,
    _LINEHEADS_ENTRY, _LINEHEADS_EXIT,
    _LINEHEADS_KEYS, _LINEHEADS_DOORS, _LINEHEADS_PASSABLE,
)

SEEDS = [1, 42, 999, 12345, 2**20 + 7]

_PASSABLE_CELLS = {(r, c) for r, cols in _LINEHEADS_PASSABLE.items() for c in cols}


# ── Structural tests ──────────────────────────────────────────────────────────

@pytest.mark.parametrize("seed", SEEDS)
def test_dimensions(seed):
    room = build_dungeon_lineheads(seed).rooms[0]
    assert room.rows == _LINEHEADS_ROWS
    assert room.cols == _LINEHEADS_COLS


@pytest.mark.parametrize("seed", SEEDS)
def test_entry_and_exit_passable(seed):
    room = build_dungeon_lineheads(seed).rooms[0]
    assert room.spawn_pos == _LINEHEADS_ENTRY
    assert room.exit_pos == _LINEHEADS_EXIT
    for (r, c) in (room.spawn_pos, room.exit_pos):
        assert room.cells[r][c] == CellType.CORRIDOR, f"seed={seed}: ({r},{c}) not CORRIDOR"


@pytest.mark.parametrize("seed", SEEDS)
def test_passable_layout(seed):
    """Exactly the _LINEHEADS_PASSABLE cells are CORRIDOR; every other cell is WALL."""
    room = build_dungeon_lineheads(seed).rooms[0]
    for r in range(room.rows):
        for c in range(room.cols):
            expect = CellType.CORRIDOR if (r, c) in _PASSABLE_CELLS else CellType.WALL
            assert room.cells[r][c] == expect, (
                f"seed={seed}: ({r},{c}) is {room.cells[r][c]}, expected {expect}"
            )


@pytest.mark.parametrize("seed", SEEDS)
def test_keys_present(seed):
    room = build_dungeon_lineheads(seed).rooms[0]
    keys = sorted((e.row, e.col) for e in room.entities if e.kind == 'floor_key')
    assert keys == sorted(_LINEHEADS_KEYS), f"seed={seed}: floor_keys {keys} != {sorted(_LINEHEADS_KEYS)}"


@pytest.mark.parametrize("seed", SEEDS)
def test_doors_present(seed):
    room = build_dungeon_lineheads(seed).rooms[0]
    doors = sorted((e.row, e.col) for e in room.entities if e.kind == 'locked_door')
    assert doors == sorted(_LINEHEADS_DOORS), f"seed={seed}: doors {doors} != {sorted(_LINEHEADS_DOORS)}"


@pytest.mark.parametrize("seed", SEEDS)
def test_single_exit_at_exit_pos(seed):
    room = build_dungeon_lineheads(seed).rooms[0]
    exits = [e for e in room.entities if e.kind == 'exit']
    assert len(exits) == 1
    assert (exits[0].row, exits[0].col) == _LINEHEADS_EXIT == room.exit_pos


# ── Colored keys / doors (fixed door sequence, shuffled key colors) ───────────

@pytest.mark.parametrize("seed", SEEDS)
def test_doors_are_a_fixed_gold_red_sequence(seed):
    """Doors are always gold (left, (1,3)) then red (right, (1,6))."""
    room = build_dungeon_lineheads(seed).rooms[0]
    doors = {(e.row, e.col): e.tag for e in room.entities if e.kind == 'locked_door'}
    assert doors == {(1, 3): 'gold', (1, 6): 'red'}, f"seed={seed}: {doors}"


@pytest.mark.parametrize("seed", SEEDS)
def test_keys_are_gold_and_red_one_each(seed):
    """The two keys are gold + red — one each (position↔color shuffled per seed)."""
    room = build_dungeon_lineheads(seed).rooms[0]
    assert sorted(e.tag for e in room.entities if e.kind == 'floor_key') == ['gold', 'red']


def test_key_colors_vary_with_seed():
    """The top key is gold on some seeds and red on others (the shuffle is live)."""
    top = {next(e.tag for e in build_dungeon_lineheads(s).rooms[0].entities
                if e.kind == 'floor_key' and (e.row, e.col) == (4, 1))
           for s in range(1, 40)}
    assert top == {'gold', 'red'}, f"top-key color did not vary: {top}"


# ── Par / budget ────────────────────────────────────────────────────────────

@pytest.mark.parametrize("seed", SEEDS)
def test_par_matches_dijkstra(seed):
    room = build_dungeon_lineheads(seed).rooms[0]
    assert room.par == _par_lineheads(room)


@pytest.mark.parametrize("seed", SEEDS)
def test_budget_is_ceil_par_times_1_4(seed):
    room = build_dungeon_lineheads(seed).rooms[0]
    assert room.budget == math.ceil(room.par * 1.4)


def test_par_is_deterministic():
    """Key colors shuffle per seed, but both assignments are balanced — par stays
    15 for every seed (regression guard)."""
    pars = {build_dungeon_lineheads(s).rooms[0].par for s in SEEDS}
    assert pars == {15}, f"expected par 15 for all seeds, got {pars}"


# ── Command necessity ─────────────────────────────────────────────────────────

@pytest.mark.parametrize("seed", SEEDS)
def test_answer_uses_G(seed):
    """G (1 ks) is the strictly-cheapest way to the bottom of the shaft, so every
    optimal path uses it."""
    room = build_dungeon_lineheads(seed).rooms[0]
    assert 'G' in room.answer.split(), f"seed={seed}: 'G' not in answer {room.answer!r}"


@pytest.mark.parametrize("seed", SEEDS)
def test_line_jumps_reduce_keystrokes(seed):
    """G/gg/{n}G are the OPTIMAL tool here: solving with count-hjkl only (no line
    jumps) costs strictly more than par.  NB the no-jump route still fits the
    ×1.4 budget, so the forcing is soft (the shaft is short) — see build_dungeon_lineheads."""
    room = build_dungeon_lineheads(seed).rooms[0]
    cost_no_jumps = _par_lineheads(room, disable_line_jumps=True)
    assert cost_no_jumps is not None and cost_no_jumps > room.par, (
        f"seed={seed}: no-line-jump cost {cost_no_jumps} not greater than par {room.par}"
    )
