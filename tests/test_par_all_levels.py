"""Par correctness across all levels.

For levels 0–4 each level's par equals its BFS/Dijkstra solver re-run on the
final room (trivially passes today; catches future solver regressions). The
universal budget-formula and answer-cost tests live in test_answer_paths.py
(auto-discovered over every builder); this file keeps the bespoke per-level
par references. Rooms come from the shared READ-ONLY build cache.

The Goblin Gauntlet par is checked against a hand-written reference
(_par_goblin_gauntlet_reference below) that models its cheapest command set:

  1. $ / 0 are water-crossing motions that reach any corridor connector in
     exactly 1 keystroke.

  2. last_f persists across corridors: the first right-going corridor needs fg
     (2 keys) to establish last_f; every subsequent one reuses it with ; (1 key).
"""
import math
import pytest
from generation.dungeon_gen import (
    _par_wardens_keep,
    _bfs_par, _bfs_par_line,
    _dijkstra_par_wbe, _dijkstra_par_ftFT,
    _GOBLIN_GAUNTLET_CORR_ROWS, _GOBLIN_GAUNTLET_RIGHT_GOING,
)

from tests import SEEDS, cached_room


# ── level-5 reference helpers ─────────────────────────────────────────────────


def _extract_goblin_gauntlet_data(room):
    """Reconstruct corr_data and gobs_17 from the generated room entities."""
    corr_data = [
        {
            'row': row,
            'right_going': row in _GOBLIN_GAUNTLET_RIGHT_GOING,
            'goblins': sorted(
                e.col for e in room.entities
                if e.alive and e.kind == 'goblin' and e.row == row
            ),
        }
        for row in _GOBLIN_GAUNTLET_CORR_ROWS
    ]
    gobs_17 = sorted(
        e.col for e in room.entities
        if e.alive and e.kind == 'goblin' and e.row == 17
    )
    return corr_data, gobs_17


def _par_goblin_gauntlet_reference(corr_data: list, gobs_17: list) -> int:
    """Reference par for The Goblin Gauntlet using the actual cheapest command set.

    Key differences from the original _par_goblin_gauntlet:
    - Entry move for right-going corridors: fg (2 keys) on the first corridor
      only; all later right-going corridors reuse last_f with ; (1 key).
    - Movement to connector after each kill chain: $ or 0 in 1 keystroke
      regardless of distance (both cross water, bounded only by walls).
    - Connector transition: j (step onto door) + x (open door) + j (enter
      corridor) = 3 keys.  2j cannot cross a fogged door.
    - Row-17 entry: ; (1 key) because last_f is already set.
    - Endgame: $ stops at col 52 (locked_door blocks _cross_water).  One p
      kills both doors via BFS.  $ reaches col 56.  j exits.
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
        total += kill + 1 + 3                      # $ or 0 (1) + j x j connector (3)

    n17 = len(gobs_17)
    if n17 > 0:
        kill17 = 1 + 1 + max(0, n17 - 1) * 2 + 1   # ; x ;x… + x to pick up key
        total += kill17
    total += 4   # $ p $ j

    return max(total, 10)


# ── The First Cave: par == BFS ────────────────────────────────────────────────

@pytest.mark.parametrize("seed", SEEDS)
def test_first_cave_par_matches_bfs(seed):
    room = cached_room('build_dungeon_first_cave', seed)   # _fog_unreachable never called for The First Cave
    expected = _bfs_par(room)
    assert expected is not None, f"seed={seed}: BFS found no path"
    assert room.par == expected, f"seed={seed}: par={room.par}, BFS={expected}"


# ── The Line Halls: par == BFS ────────────────────────────────────────────────

@pytest.mark.parametrize("seed", SEEDS)
def test_line_halls_par_matches_bfs(seed):
    room = cached_room('build_dungeon_line_halls', seed)   # _fog_unreachable never called for The Line Halls
    expected = _bfs_par_line(room)
    assert expected is not None, f"seed={seed}: BFS found no path"
    assert room.par == expected, f"seed={seed}: par={room.par}, BFS={expected}"


# ── The Rune Halls: par == Dijkstra ───────────────────────────────────────────

@pytest.mark.parametrize("seed", SEEDS)
def test_rune_halls_par_matches_dijkstra(seed):
    room = cached_room('build_dungeon_rune_halls', seed)   # _fog_unreachable never called for The Rune Halls
    expected = _dijkstra_par_wbe(room)
    assert expected is not None, f"seed={seed}: Dijkstra found no path"
    assert room.par == expected, f"seed={seed}: par={room.par}, Dijkstra={expected}"


# ── The Character Cataracts: par == Dijkstra ──────────────────────────────────

@pytest.mark.parametrize("seed", SEEDS)
def test_character_cataracts_par_matches_dijkstra(seed):
    room = cached_room('build_dungeon_character_cataracts', seed)   # _fog_unreachable never called for The Character Cataracts
    expected = _dijkstra_par_ftFT(room)
    assert expected is not None, f"seed={seed}: Dijkstra found no path"
    assert room.par == expected, f"seed={seed}: par={room.par}, Dijkstra={expected}"


# ── The Goblin Gauntlet: par == reference formula ─────────────────────────────

@pytest.mark.parametrize("seed", SEEDS)
def test_goblin_gauntlet_par_matches_reference(seed):
    """par must reflect the cheapest Goblin Gauntlet strategy: ; reuses last_f
    across right-going corridors (fg only on the first), and $ / 0 cross water
    to each connector in a single keystroke.
    """
    room = cached_room('build_dungeon_goblin_gauntlet', seed)
    corr_data, gobs_17 = _extract_goblin_gauntlet_data(room)
    expected = _par_goblin_gauntlet_reference(corr_data, gobs_17)
    assert room.par == expected, (
        f"seed={seed}: par={room.par}, reference={expected}"
    )


# ── The Warden's Keep: par == _par_wardens_keep() (seed-independent fixed layout) ──

def test_wardens_keep_completion_only():
    """The Warden's Keep is a boss fight — no par/stars, just completion.

    Budget is still derived from _par_wardens_keep() to allow a generous time limit,
    but room.par is None so no fireworks or star rating are awarded.
    """
    expected_budget = math.ceil(_par_wardens_keep() * 1.4)
    for seed in SEEDS:
        room = cached_room('build_dungeon_wardens_keep', seed)
        assert room.par is None, f"seed={seed}: boss level must have par=None"
        assert room.budget == expected_budget, (
            f"seed={seed}: budget={room.budget}, expected {expected_budget}"
        )
