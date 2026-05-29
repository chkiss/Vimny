"""Level 8 (id=8) — The Long Plumb: dungeon correctness tests.

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
    build_dungeon_9,
    _dijkstra_par_LGG,
    _LGG_ROWS, _LGG_COLS,
    _LGG_ENTRY, _LGG_EXIT,
    _LGG_KEYS, _LGG_DOORS, _LGG_PASSABLE,
)

SEEDS = [1, 42, 999, 12345, 2**20 + 7]

_PASSABLE_CELLS = {(r, c) for r, cols in _LGG_PASSABLE.items() for c in cols}


# ── Structural tests ──────────────────────────────────────────────────────────

@pytest.mark.parametrize("seed", SEEDS)
def test_dimensions(seed):
    room = build_dungeon_9(seed).rooms[0]
    assert room.rows == _LGG_ROWS
    assert room.cols == _LGG_COLS


@pytest.mark.parametrize("seed", SEEDS)
def test_entry_and_exit_passable(seed):
    room = build_dungeon_9(seed).rooms[0]
    assert room.gg_pos == _LGG_ENTRY
    assert room.exit_pos == _LGG_EXIT
    for (r, c) in (room.gg_pos, room.exit_pos):
        assert room.cells[r][c] == CellType.CORRIDOR, f"seed={seed}: ({r},{c}) not CORRIDOR"


@pytest.mark.parametrize("seed", SEEDS)
def test_passable_layout(seed):
    """Exactly the _LGG_PASSABLE cells are CORRIDOR; every other cell is WALL."""
    room = build_dungeon_9(seed).rooms[0]
    for r in range(room.rows):
        for c in range(room.cols):
            expect = CellType.CORRIDOR if (r, c) in _PASSABLE_CELLS else CellType.WALL
            assert room.cells[r][c] == expect, (
                f"seed={seed}: ({r},{c}) is {room.cells[r][c]}, expected {expect}"
            )


@pytest.mark.parametrize("seed", SEEDS)
def test_keys_present(seed):
    room = build_dungeon_9(seed).rooms[0]
    keys = sorted((e.row, e.col) for e in room.entities if e.kind == 'floor_key')
    assert keys == sorted(_LGG_KEYS), f"seed={seed}: floor_keys {keys} != {sorted(_LGG_KEYS)}"


@pytest.mark.parametrize("seed", SEEDS)
def test_doors_present(seed):
    room = build_dungeon_9(seed).rooms[0]
    doors = sorted((e.row, e.col) for e in room.entities if e.kind == 'locked_door')
    assert doors == sorted(_LGG_DOORS), f"seed={seed}: doors {doors} != {sorted(_LGG_DOORS)}"


@pytest.mark.parametrize("seed", SEEDS)
def test_single_exit_at_exit_pos(seed):
    room = build_dungeon_9(seed).rooms[0]
    exits = [e for e in room.entities if e.kind == 'exit']
    assert len(exits) == 1
    assert (exits[0].row, exits[0].col) == _LGG_EXIT == room.exit_pos


# ── Par / budget ────────────────────────────────────────────────────────────

@pytest.mark.parametrize("seed", SEEDS)
def test_par_matches_dijkstra(seed):
    room = build_dungeon_9(seed).rooms[0]
    assert room.par == _dijkstra_par_LGG(room)


@pytest.mark.parametrize("seed", SEEDS)
def test_budget_is_ceil_par_times_1_4(seed):
    room = build_dungeon_9(seed).rooms[0]
    assert room.budget == math.ceil(room.par * 1.4)


def test_par_is_deterministic():
    """Fixed, seed-independent layout → a stable par (regression guard)."""
    pars = {build_dungeon_9(s).rooms[0].par for s in SEEDS}
    assert pars == {15}, f"expected par 15 for all seeds, got {pars}"


# ── Command necessity ─────────────────────────────────────────────────────────

@pytest.mark.parametrize("seed", SEEDS)
def test_answer_uses_G(seed):
    """G (1 ks) is the strictly-cheapest way to the bottom of the shaft, so every
    optimal path uses it."""
    room = build_dungeon_9(seed).rooms[0]
    assert 'G' in room.answer.split(), f"seed={seed}: 'G' not in answer {room.answer!r}"


@pytest.mark.parametrize("seed", SEEDS)
def test_line_jumps_reduce_keystrokes(seed):
    """G/gg/{n}G are the OPTIMAL tool here: solving with count-hjkl only (no line
    jumps) costs strictly more than par.  NB the no-jump route still fits the
    ×1.4 budget, so the forcing is soft (the shaft is short) — see build_dungeon_9."""
    room = build_dungeon_9(seed).rooms[0]
    cost_no_jumps = _dijkstra_par_LGG(room, disable_line_jumps=True)
    assert cost_no_jumps is not None and cost_no_jumps > room.par, (
        f"seed={seed}: no-line-jump cost {cost_no_jumps} not greater than par {room.par}"
    )
