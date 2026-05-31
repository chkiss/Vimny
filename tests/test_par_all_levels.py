"""Par correctness across all levels.

For levels 0–4 each level's par equals its BFS/Dijkstra solver re-run on the
final room (trivially passes today; catches future solver regressions). The
Counting Crypts par is also validated in test_counting_crypts.py; the universal
budget test here covers it alongside every other level.

The Goblin Gauntlet (level 5) par is checked against a hand-written reference
(_par_l5_reference below) that models its cheapest command set:

  1. $ / 0 are water-crossing motions that reach any corridor connector in
     exactly 1 keystroke.

  2. last_f persists across corridors: the first right-going corridor needs fg
     (2 keys) to establish last_f; every subsequent one reuses it with ; (1 key).
"""
import math
import pytest
from generation.dungeon_gen import (
    build_dungeon_first_cave, build_dungeon_line_halls, build_dungeon_counting_crypts,
    build_dungeon_rune_halls, build_dungeon_character_cataracts, build_dungeon_goblin_gauntlet,
    build_dungeon_word_forge, build_dungeon_backward_vaults, build_dungeon_lineheads,
    build_dungeon_wardens_keep, _par_wardens_keep,
    _bfs_par, _bfs_par_line,
    _par_counting_crypts,
    _dijkstra_par_wbe, _dijkstra_par_ftFT,
    _GOBLIN_GAUNTLET_CORR_ROWS, _GOBLIN_GAUNTLET_RIGHT_GOING,
)

from tests import SEEDS


# ── level-5 reference helpers ─────────────────────────────────────────────────


def _extract_l5_data(room):
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


def _par_l5_reference(corr_data: list, gobs_17: list) -> int:
    """Reference par for level 5 using the actual cheapest command set.

    Key differences from the original _par_l5:
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


# ── universal: budget == ceil(par × 1.4) for every level ─────────────────────

@pytest.mark.parametrize("seed", SEEDS)
@pytest.mark.parametrize("builder,level_id", [
    (build_dungeon_first_cave, 0), (build_dungeon_line_halls, 1), (build_dungeon_counting_crypts, 2),
    (build_dungeon_rune_halls, 3), (build_dungeon_character_cataracts, 4), (build_dungeon_goblin_gauntlet, 5),
    (build_dungeon_word_forge, 6), (build_dungeon_backward_vaults, 7), (build_dungeon_lineheads, 8),
])
def test_budget_is_ceil_par_times_1_4(builder, level_id, seed):
    room = builder(seed).room
    assert room.budget == math.ceil(room.par * 1.4), (
        f"level={level_id} seed={seed}: budget={room.budget}, "
        f"ceil(par*1.4)={math.ceil(room.par * 1.4)}"
    )


# ── universal: answer key length == par (catches Dijkstra cost-model bugs) ───

@pytest.mark.parametrize("seed", SEEDS)
@pytest.mark.parametrize("builder,level_id", [
    (build_dungeon_first_cave, 0), (build_dungeon_line_halls, 1), (build_dungeon_counting_crypts, 2),
    (build_dungeon_rune_halls, 3), (build_dungeon_character_cataracts, 4), (build_dungeon_goblin_gauntlet, 5),
    (build_dungeon_word_forge, 6), (build_dungeon_backward_vaults, 7), (build_dungeon_lineheads, 8),
])
def test_answer_key_length_matches_par(builder, level_id, seed):
    """Non-space chars in room.answer must equal room.par.

    Each character in the answer string is one keypress; the par is the total
    keystroke budget cost for the optimal solution.  A mismatch means the
    Dijkstra cost model diverges from _keystroke_cost in main.py.
    """
    room = builder(seed).room
    if not room.answer:
        return  # level has no answer key (e.g. the Warden's Keep boss)
    ans_len = len(room.answer.replace(' ', ''))
    assert ans_len == room.par, (
        f"level={level_id} seed={seed}: answer has {ans_len} keypresses "
        f"but par={room.par}"
    )


# ── level 0: par == BFS ───────────────────────────────────────────────────────

@pytest.mark.parametrize("seed", SEEDS)
def test_level0_par_matches_bfs(seed):
    room = build_dungeon_first_cave(seed).room   # _fog_unreachable never called for level 0
    expected = _bfs_par(room)
    assert expected is not None, f"seed={seed}: BFS found no path"
    assert room.par == expected, f"seed={seed}: par={room.par}, BFS={expected}"


# ── level 1: par == BFS ───────────────────────────────────────────────────────

@pytest.mark.parametrize("seed", SEEDS)
def test_level1_par_matches_bfs(seed):
    room = build_dungeon_line_halls(seed).room   # _fog_unreachable never called for level 1
    expected = _bfs_par_line(room)
    assert expected is not None, f"seed={seed}: BFS found no path"
    assert room.par == expected, f"seed={seed}: par={room.par}, BFS={expected}"


# ── level 3: par == Dijkstra ──────────────────────────────────────────────────

@pytest.mark.parametrize("seed", SEEDS)
def test_level3_par_matches_dijkstra(seed):
    room = build_dungeon_rune_halls(seed).room   # _fog_unreachable never called for level 3
    expected = _dijkstra_par_wbe(room)
    assert expected is not None, f"seed={seed}: Dijkstra found no path"
    assert room.par == expected, f"seed={seed}: par={room.par}, Dijkstra={expected}"


# ── level 4: par == Dijkstra ──────────────────────────────────────────────────

@pytest.mark.parametrize("seed", SEEDS)
def test_level4_par_matches_dijkstra(seed):
    room = build_dungeon_character_cataracts(seed).room   # _fog_unreachable never called for level 4
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
    room = build_dungeon_goblin_gauntlet(seed).room
    corr_data, gobs_17 = _extract_l5_data(room)
    expected = _par_l5_reference(corr_data, gobs_17)
    assert room.par == expected, (
        f"seed={seed}: par={room.par}, reference={expected}"
    )


# ── level 51: par == _par_wardens_keep() (seed-independent fixed layout) ──────────────

def test_level51_completion_only():
    """The Warden's Keep is a boss fight — no par/stars, just completion.

    Budget is still derived from _par_wardens_keep() to allow a generous time limit,
    but room.par is None so no fireworks or star rating are awarded.
    """
    expected_budget = math.ceil(_par_wardens_keep() * 1.4)
    for seed in SEEDS:
        room = build_dungeon_wardens_keep(seed).room
        assert room.par is None, f"seed={seed}: boss level must have par=None"
        assert room.budget == expected_budget, (
            f"seed={seed}: budget={room.budget}, expected {expected_budget}"
        )
