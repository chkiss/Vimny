# Vimny — a Vim-teaching dungeon crawler.
# Copyright (C) 2026 Chas Kissick
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""The Backward Vaults: dungeon correctness tests."""
import pytest
from vimny.engine.world import CellType
from vimny.generation.dungeon_gen import (
    build_dungeon_backward_vaults,
    _par_backward_vaults,
    _BACKWARD_VAULTS_CORR_ROWS, _BACKWARD_VAULTS_TURN_SPANS,
)

from tests import SEEDS


@pytest.mark.parametrize("seed", SEEDS)
def test_entry_and_exit_passable(seed):
    d = build_dungeon_backward_vaults(seed)
    room = d.rooms[0]
    r0, c0 = room.spawn_pos
    r1, c1 = room.exit_pos
    assert room.cells[r0][c0] == CellType.CORRIDOR, f"seed={seed}: entry is not passable"
    assert room.cells[r1][c1] == CellType.CORRIDOR, f"seed={seed}: exit is not passable"


@pytest.mark.parametrize("seed", SEEDS)
def test_par_matches_dijkstra(seed):
    d = build_dungeon_backward_vaults(seed)
    room = d.rooms[0]
    computed = _par_backward_vaults(room)
    assert room.par == computed, (
        f"seed={seed}: room.par={room.par} but Dijkstra computed {computed}"
    )


# (Budget formula: covered by the universal test in test_answer_paths.py.)


@pytest.mark.parametrize("seed", SEEDS)
def test_answer_uses_ge_or_gE_for_LT2(seed):
    """The optimal path must use a backward-end motion to cross the LT2 gap (C4 anchor end=5)."""
    d = build_dungeon_backward_vaults(seed)
    room = d.rooms[0]
    tokens = room.answer.split()
    assert 'ge' in tokens or 'gE' in tokens, (
        f"seed={seed}: neither 'ge' nor 'gE' in answer {room.answer!r}"
    )


@pytest.mark.parametrize("seed", SEEDS)
def test_answer_uses_gE_for_LT3(seed):
    """The optimal path must use gE (no count) to hop the baphomet/behemoth WORD to LT3 gap.

    gE (2 ks) beats 2ge (3 ks) and 19h (3 ks) because the WORD spans two adjacent
    clusters; gE jumps both in one shot while ge stops at each cluster boundary.
    """
    d = build_dungeon_backward_vaults(seed)
    room = d.rooms[0]
    tokens = room.answer.split()
    assert 'gE' in tokens and '8gE' not in tokens, (
        f"seed={seed}: expected plain 'gE' for C6 crossing, got {room.answer!r}"
    )


@pytest.mark.parametrize("seed", SEEDS)
def test_exit_entity_at_exit_pos(seed):
    d = build_dungeon_backward_vaults(seed)
    room = d.rooms[0]
    exit_ents = [e for e in room.entities if e.kind == 'exit']
    assert len(exit_ents) == 1, f"seed={seed}: expected 1 exit entity, got {len(exit_ents)}"
    e = exit_ents[0]
    assert (e.row, e.col) == room.exit_pos, (
        f"seed={seed}: exit entity at ({e.row},{e.col}) != exit_pos {room.exit_pos}"
    )


@pytest.mark.parametrize("seed", SEEDS)
def test_corridors_carved(seed):
    d = build_dungeon_backward_vaults(seed)
    room = d.rooms[0]
    for r in _BACKWARD_VAULTS_CORR_ROWS:
        for c in range(1, 39):
            assert room.cells[r][c] == CellType.CORRIDOR, (
                f"seed={seed}: corridor row {r} col {c} is not CORRIDOR"
            )


_BACKWARD_VAULTS_GUARD_WALLS = {(2, 38), (4, 1)}  # RT1 and LT1 narrow-turn walls


@pytest.mark.parametrize("seed", SEEDS)
def test_turn_spans_carved(seed):
    d = build_dungeon_backward_vaults(seed)
    room = d.rooms[0]
    for r0, r1, c0, c1 in _BACKWARD_VAULTS_TURN_SPANS:
        for r in range(r0, r1 + 1):
            for c in range(c0, c1 + 1):
                if (r, c) in _BACKWARD_VAULTS_GUARD_WALLS:
                    continue  # guard walls intentionally narrow these turns
                assert room.cells[r][c] == CellType.CORRIDOR, (
                    f"seed={seed}: turn span ({r0},{r1},{c0},{c1}) cell ({r},{c}) not CORRIDOR"
                )


def test_RT1_and_LT1_guard_walls():
    """(2,38) and (4,1) must be WALL — they narrow RT1 and LT1 to force 4e and ^."""
    d = build_dungeon_backward_vaults(42)
    room = d.rooms[0]
    assert room.cells[2][38] == CellType.WALL, "(2,38) must be wall (RT1 guard)"
    assert room.cells[4][1]  == CellType.WALL, "(4,1) must be wall (LT1 guard)"
    # Adjacent cells in the turns must still be open
    assert room.cells[2][37] == CellType.CORRIDOR, "(2,37) must remain open"
    assert room.cells[2][36] == CellType.CORRIDOR, "(2,36) must remain open"
    assert room.cells[4][2]  == CellType.CORRIDOR, "(4,2) must remain open"
    assert room.cells[4][3]  == CellType.CORRIDOR, "(4,3) must remain open"


def test_LT2_gap_is_cols_5_6_only():
    """LT2 turn (rows 7-9) is only passable at cols 5-6 — the ge lesson gap."""
    d = build_dungeon_backward_vaults(42)
    room = d.rooms[0]
    # cols 5-6 must be open in row 8
    assert room.cells[8][5] == CellType.CORRIDOR, "LT2 gap col 5 must be open"
    assert room.cells[8][6] == CellType.CORRIDOR, "LT2 gap col 6 must be open"
    # col 2 (where b would land on C4 anchor) must be wall in row 8
    assert room.cells[8][2] == CellType.WALL, (
        "col 2 in row 8 must be wall (b-landing blocked, forcing ge)"
    )
    # col 3 and 4 must also be wall in row 8
    assert room.cells[8][3] == CellType.WALL, "col 3 in row 8 must be wall"
    assert room.cells[8][4] == CellType.WALL, "col 4 in row 8 must be wall"


def test_LT3_exit_at_col_19():
    """LT3 turn (rows 11-12): only col 19 is passable in row 12 — the exit cell."""
    d = build_dungeon_backward_vaults(42)
    room = d.rooms[0]
    # Only the exit cell is open in row 12
    assert room.cells[12][19] == CellType.CORRIDOR, "exit cell (12,19) must be open"
    assert room.cells[12][18] == CellType.WALL, "col 18 in row 12 must be wall"
    assert room.cells[12][20] == CellType.WALL, "col 20 in row 12 must be wall"
    assert room.cells[12][21] == CellType.WALL, "col 21 in row 12 must be wall"
    # Col 20 in row 11 must be empty (gap between anchor and big WORD)
    assert room.char_run_at(11, 20) is None, "col 20 in row 11 must be empty (gap before big WORD)"


def test_C4_ge_anchor_at_correct_position():
    """4-char C4 anchor at (7,2): cols 2-5; ge from col 9+ lands at end=5 (in LT2 gap)."""
    d = build_dungeon_backward_vaults(42)
    room = d.rooms[0]
    anchor = room.char_run_at(7, 2)
    assert anchor is not None, "Expected 4-char C4 anchor at (7,2)"
    assert len(anchor.symbols) == 4, (
        f"C4 anchor should be 4 chars wide, got {len(anchor.symbols)}"
    )
    end_col = anchor.col + len(anchor.symbols) - 1
    assert end_col == 5, f"C4 anchor end should be col 5, got {end_col}"


def test_C6_baphomet_behemoth_word():
    """C6 row 11: the baphomet/behemoth WORD is three adjacent clusters spanning cols 21-38.

    Cluster A 'b4¶♯∘m3†'  at cols 21-28 (8 chars).
    Cluster S '!='          at cols 29-30 (2 chars, separator).
    Cluster B 'b3♯3m∘†♯'  at cols 31-38 (8 chars).
    All adjacent → one WORD: gE hops all in 1 shot; ge needs 3 hops.
    """
    d = build_dungeon_backward_vaults(42)
    room = d.rooms[0]

    # ── Cluster A: cols 21-28 ─────────────────────────────────────────────────
    ca = room.char_run_at(11, 21)
    assert ca is not None, "Cluster A must start at (11,21)"
    assert ca.col == 21, f"Cluster A col={ca.col}, expected 21"
    assert len(ca.symbols) == 8, f"Cluster A must be 8 chars, got {len(ca.symbols)}"
    assert ca.col + len(ca.symbols) - 1 == 28, "Cluster A must end at col 28"

    # ── Separator cluster: cols 29-30 ────────────────────────────────────────
    cs = room.char_run_at(11, 29)
    assert cs is not None, "Separator cluster must start at (11,29)"
    assert len(cs.symbols) == 2, f"Separator must be 2 chars, got {len(cs.symbols)}"
    assert cs.col + len(cs.symbols) - 1 == 30, "Separator must end at col 30"

    # ── Cluster B: cols 31-38 ─────────────────────────────────────────────────
    cb = room.char_run_at(11, 31)
    assert cb is not None, "Cluster B must start at (11,31)"
    assert cb.col == 31, f"Cluster B col={cb.col}, expected 31"
    assert len(cb.symbols) == 8, f"Cluster B must be 8 chars, got {len(cb.symbols)}"
    assert cb.col + len(cb.symbols) - 1 == 38, "Cluster B must end at col 38"

    # ── All adjacent, all same color ─────────────────────────────────────────
    assert ca.col + len(ca.symbols) == cs.col, "A and S must be adjacent"
    assert cs.col + len(cs.symbols) == cb.col, "S and B must be adjacent"
    assert ca.kind == cs.kind == cb.kind, "All clusters must share color"

    # ── Col 20 is empty (gap between anchor and the big WORD) ────────────────
    assert room.char_run_at(11, 20) is None, "Col 20 must be empty (gap before big WORD)"

    # ── Anchor rune ends at col 19 (gE landing) ──────────────────────────────
    anchor = room.char_run_at(11, 18)
    assert anchor is not None, "Anchor cluster must start at (11,18)"
    assert anchor.col + len(anchor.symbols) - 1 == 19, (
        f"Anchor must end at col 19, got {anchor.col + len(anchor.symbols) - 1}"
    )
    assert room.char_run_at(11, 17) is None or room.char_run_at(11, 17) is anchor, (
        "Col 17 must not have a separate cluster before the anchor"
    )

    # ── Filler exists in cols 2-16 ───────────────────────────────────────────
    filler_cols = [c for c in range(2, 17) if room.char_run_at(11, c) is not None]
    assert len(filler_cols) > 0, "Expected some filler runes in cols 2-16"
