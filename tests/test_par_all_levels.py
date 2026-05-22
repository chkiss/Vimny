"""Par correctness across all levels.

For levels 0–4 each level's par equals its BFS/Dijkstra solver re-run on the
final room (trivially passes today; catches future solver regressions).
Level 2 par is already validated in test_level_2.py; the universal budget test
here covers it alongside every other level.

Level 5 is the failing case: _par_l5 over-estimates par by not modelling two
cheaper techniques available in the level-5 command set:

  1. $ / 0 are water-crossing motions that reach any corridor connector in
     exactly 1 keystroke.  _par_l5 charges _l5_move_cost(dist) ≥ 2 instead.

  2. last_f persists across corridors.  The first right-going corridor (row 1)
     needs fg (2 keys) to establish last_f, but every subsequent right-going
     corridor can reuse it with ; (1 key).  _par_l5 charges fg every time.

test_level5_par_matches_reference is currently FAILING; patching _par_l5 makes
every test in this file pass.
"""
import math
import pytest
from generation.dungeon_gen import (
    build_dungeon_0, build_dungeon_1, build_dungeon_2,
    build_dungeon_3, build_dungeon_4, build_dungeon_5,
    build_dungeon_51, _par_l51,
    _bfs_par, _bfs_par_line,
    _dijkstra_par_level2,
    _dijkstra_par_wbe, _dijkstra_par_ftFT,
    _L5_CORR_ROWS, _L5_RIGHT_GOING,
)

SEEDS = [1, 42, 999, 12345, 2**20 + 7]


# ── level-5 reference helpers ─────────────────────────────────────────────────

def _move_cost(dist: int) -> int:
    """Keystrokes for an optimal count-hjkl move of dist cells."""
    if dist <= 0: return 0
    if dist == 1: return 1
    return len(str(dist)) + 1


def _extract_l5_data(room):
    """Reconstruct corr_data and gobs_17 from the generated room entities."""
    corr_data = [
        {
            'row': row,
            'right_going': row in _L5_RIGHT_GOING,
            'goblins': sorted(
                e.col for e in room.entities
                if e.alive and e.kind == 'goblin' and e.row == row
            ),
        }
        for row in _L5_CORR_ROWS
    ]
    gobs_17 = sorted(
        e.col for e in room.entities
        if e.alive and e.kind == 'goblin' and e.row == 17
    )
    return corr_data, gobs_17


def _par_l5_reference(corr_data: list, gobs_17: list) -> int:
    """Reference par for level 5 using the actual cheapest command set.

    Key differences from the original _par_l5:
    - Entry move for right-going corridors: fg (2 keys) on the first corridor
      only; all later right-going corridors reuse last_f with ; (1 key).
    - Movement to connector after each kill chain: $ or 0 in 1 keystroke
      regardless of distance (both cross water, bounded only by walls).
    - Row-17 entry: ; (1 key) because last_f is already set.
    - Row-17 connector approach: count-l via _move_cost ($ would overshoot the
      locked door at col 53).
    """
    total = 0
    first_right = True
    for c in corr_data:
        n = len(c['goblins'])
        if n == 0:
            continue
        if c['right_going']:
            entry = 2 if first_right else 1   # fg once; subsequent corridors use ;
            first_right = False
        else:
            entry = 1                          # , reverses the stored last_f
        kill   = entry + 1 + max(0, n - 1) * 2   # reach-first  x  chain…
        total += kill + 1 + 2                      # $ or 0 (1 key to connector) + 2j

    n17 = len(gobs_17)
    if n17 > 0:
        kill17    = 1 + 1 + max(0, n17 - 1) * 2 + 1   # ; x ;x… + x to pick up dropped key
        dist_door = 52 - max(gobs_17)
        total    += kill17 + _move_cost(dist_door)  # count-l; $ overshoots past door
    total += 1 + 1 + 1 + 2   # p door17  j  p door18  fE exit

    return max(total, 10)


# ── universal: budget == ceil(par × 1.4) for every level ─────────────────────

@pytest.mark.parametrize("seed", SEEDS)
@pytest.mark.parametrize("builder,level_id", [
    (build_dungeon_0, 0), (build_dungeon_1, 1), (build_dungeon_2, 2),
    (build_dungeon_3, 3), (build_dungeon_4, 4), (build_dungeon_5, 5),
    (build_dungeon_51, 51),
])
def test_budget_is_ceil_par_times_1_4(builder, level_id, seed):
    room = builder(seed).room
    assert room.budget == math.ceil(room.par * 1.4), (
        f"level={level_id} seed={seed}: budget={room.budget}, "
        f"ceil(par*1.4)={math.ceil(room.par * 1.4)}"
    )


# ── level 0: par == BFS ───────────────────────────────────────────────────────

@pytest.mark.parametrize("seed", SEEDS)
def test_level0_par_matches_bfs(seed):
    room = build_dungeon_0(seed).room   # _fog_unreachable never called for level 0
    expected = _bfs_par(room)
    assert expected is not None, f"seed={seed}: BFS found no path"
    assert room.par == expected, f"seed={seed}: par={room.par}, BFS={expected}"


# ── level 1: par == BFS ───────────────────────────────────────────────────────

@pytest.mark.parametrize("seed", SEEDS)
def test_level1_par_matches_bfs(seed):
    room = build_dungeon_1(seed).room   # _fog_unreachable never called for level 1
    expected = _bfs_par_line(room)
    assert expected is not None, f"seed={seed}: BFS found no path"
    assert room.par == expected, f"seed={seed}: par={room.par}, BFS={expected}"


# ── level 3: par == Dijkstra ──────────────────────────────────────────────────

@pytest.mark.parametrize("seed", SEEDS)
def test_level3_par_matches_dijkstra(seed):
    room = build_dungeon_3(seed).room   # _fog_unreachable never called for level 3
    expected = _dijkstra_par_wbe(room)
    assert expected is not None, f"seed={seed}: Dijkstra found no path"
    assert room.par == expected, f"seed={seed}: par={room.par}, Dijkstra={expected}"


# ── level 4: par == Dijkstra ──────────────────────────────────────────────────

@pytest.mark.parametrize("seed", SEEDS)
def test_level4_par_matches_dijkstra(seed):
    room = build_dungeon_4(seed).room   # _fog_unreachable never called for level 4
    expected = _dijkstra_par_ftFT(room)
    assert expected is not None, f"seed={seed}: Dijkstra found no path"
    assert room.par == expected, f"seed={seed}: par={room.par}, Dijkstra={expected}"


# ── level 5: par == reference formula (currently failing) ────────────────────

@pytest.mark.parametrize("seed", SEEDS)
def test_level5_par_matches_reference(seed):
    """par must reflect the cheapest level-5 strategy.

    Currently failing because _par_l5:
    - re-charges fg (2 keys) on every right-going corridor instead of ; (1 key)
      after last_f is established on the first corridor
    - uses count-hjkl (_l5_move_cost) to reach connectors instead of
      $ / 0 (always 1 key regardless of distance)
    """
    room = build_dungeon_5(seed).room
    corr_data, gobs_17 = _extract_l5_data(room)
    expected = _par_l5_reference(corr_data, gobs_17)
    assert room.par == expected, (
        f"seed={seed}: par={room.par}, reference={expected}"
    )


# ── level 51: par == _par_l51() (seed-independent fixed layout) ──────────────

def test_level51_par_matches_formula():
    """_par_l51() is the simulated minimum keystroke cost for The Warden's Keep.

    Strategy: $ x $ k $ j 0 (7 keys) → combat (~78 keys, seed-dependent) → G (1 key).
    Simulated across 20 seeds: min=86, max=95.
    """
    expected = _par_l51()
    assert 55 <= expected <= 90, f"par={expected} outside sanity range [55, 90]"
    # All seeds produce the same par (layout is fixed, no random elements)
    for seed in SEEDS:
        room = build_dungeon_51(seed).room
        assert room.par == expected, (
            f"seed={seed}: room.par={room.par}, _par_l51()={expected}"
        )
        assert room.budget == math.ceil(expected * 1.4), (
            f"seed={seed}: budget={room.budget}, ceil(par*1.4)={math.ceil(expected * 1.4)}"
        )
