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

"""The Reliquary — the Sealed Ward (bonus room, par=None).

One test per property: structure, the seal CharRun, the warded doorway gate
(sanctum blocked until the seal is erased), x-erasure via the real engine
primitives, frieze placement, and per-seed randomization.
"""
import pytest
from collections import deque

import vimny.generation.dungeon_gen as dg
from main import _check_seal_broken
from vimny.engine.editor import _ed_cut
from vimny.engine.reflow import close_gap, is_ledge
from vimny.engine.world import CellType
from tests import SEEDS


def _room(seed):
    return dg.build_dungeon_reliquary(seed).rooms[0]


def _reachable(room, src, dst):
    seen, q = {src}, deque([src])
    while q:
        r, c = q.popleft()
        if (r, c) == dst:
            return True
        for dr, dc in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            nb = (r + dr, c + dc)
            if (nb not in seen and 0 <= nb[0] < room.rows and 0 <= nb[1] < room.cols
                    and room.cells[nb[0]][nb[1]] != CellType.WALL):
                seen.add(nb)
                q.append(nb)
    return False


def _seal_run(room):
    runs = [ru for ru in room.char_runs if ru.row == dg._RELIQUARY_ACTION_ROW]
    assert len(runs) == 1, f"expected exactly one CharRun on the action row, got {len(runs)}"
    return runs[0]


# ── Structure ────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("seed", SEEDS)
def test_dimensions_and_anchors(seed):
    room = _room(seed)
    assert (room.rows, room.cols) == (dg._RELIQUARY_ROWS, dg._RELIQUARY_COLS)
    assert room.spawn_pos == dg._RELIQUARY_SPAWN
    assert room.exit_pos == dg._RELIQUARY_EXIT
    # chest + exit entities present; exit is immediately right of the chest
    kinds = {(e.kind, e.row, e.col) for e in room.entities}
    assert ('chest_scroll', *dg._RELIQUARY_CHEST) in kinds
    assert ('exit', *dg._RELIQUARY_EXIT) in kinds
    assert dg._RELIQUARY_EXIT == (dg._RELIQUARY_CHEST[0], dg._RELIQUARY_CHEST[1] + 1)


@pytest.mark.parametrize("seed", SEEDS)
def test_no_par_reward_room(seed):
    room = _room(seed)
    assert room.par is None
    assert room.budget > 0


@pytest.mark.parametrize("seed", SEEDS)
def test_dividing_wall_is_full_height(seed):
    room = _room(seed)
    W = dg._RELIQUARY_WALL_COL
    for r in range(room.rows):
        assert room.cells[r][W] == CellType.WALL


# ── The seal ─────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("seed", SEEDS)
def test_seal_word_is_themed_and_right_aligned(seed):
    room = _room(seed)
    run = _seal_run(room)
    word = ''.join(run.symbols)
    assert run.kind == 'ember'
    assert word in dg._RELIQUARY_SEAL_WORDS
    # right-aligned against the dividing wall (last glyph at col W-1)
    assert run.col == dg._RELIQUARY_WALL_COL - len(word)
    assert run.col + len(word) == dg._RELIQUARY_WALL_COL
    # leaves at least one approach cell after the spawn
    assert run.col > dg._RELIQUARY_SPAWN[1]


@pytest.mark.parametrize("seed", SEEDS)
def test_seal_door_attribute(seed):
    room = _room(seed)
    assert room.seal_door == (dg._RELIQUARY_ACTION_ROW, dg._RELIQUARY_WALL_COL)


# ── The gate ─────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("seed", SEEDS)
def test_sanctum_blocked_while_sealed(seed):
    room = _room(seed)
    assert not _reachable(room, room.spawn_pos, room.exit_pos)
    assert not _reachable(room, room.spawn_pos, dg._RELIQUARY_CHEST)


@pytest.mark.parametrize("seed", SEEDS)
def test_x_erase_opens_ward_on_final_glyph(seed):
    """Faithful to gameplay: x-spam on the leftmost glyph (cursor fixed; reflow
    feeds the next letter under it) breaks the seal exactly on the last cut."""
    room = _room(seed)
    ar = dg._RELIQUARY_ACTION_ROW
    run = _seal_run(room)
    word, seal_col = ''.join(run.symbols), run.col

    for i in range(len(word)):
        item = _ed_cut(room, ar, seal_col)
        assert item and item['type'] == 'rune'
        if is_ledge(room, ar):
            close_gap(room, ar, seal_col, 1)
        msg = _check_seal_broken(room)
        door_open = room.cells[ar][dg._RELIQUARY_WALL_COL] == CellType.FLOOR
        if i < len(word) - 1:
            assert not msg and not door_open, f"seal opened early at cut {i}"
        else:
            assert msg and door_open, "final glyph should open the ward"

    assert _reachable(room, room.spawn_pos, room.exit_pos)
    assert _reachable(room, room.spawn_pos, dg._RELIQUARY_CHEST)


@pytest.mark.parametrize("seed", SEEDS)
def test_check_seal_broken_idempotent_when_open(seed):
    room = _room(seed)
    room.char_runs = [ru for ru in room.char_runs if ru.row != dg._RELIQUARY_ACTION_ROW]
    assert _check_seal_broken(room)        # first call opens
    assert _check_seal_broken(room) == ''  # already open → no-op


# ── Decoration ───────────────────────────────────────────────────────────────

@pytest.mark.parametrize("seed", SEEDS)
def test_friezes_only_off_the_action_row(seed):
    room = _room(seed)
    decor = [ru for ru in room.char_runs if ru.row != dg._RELIQUARY_ACTION_ROW]
    assert decor, "expected ornamental friezes"
    assert all(ru.row in dg._RELIQUARY_FRIEZE_ROWS for ru in decor)
    assert all(ru.kind in ('ancient', 'verdant') for ru in decor)
    # never overlap the dividing wall or the room borders
    for ru in decor:
        for c in range(ru.col, ru.col + len(ru.symbols)):
            assert room.cells[ru.row][c] == CellType.FLOOR


# ── Fog of war (playtest 2026-07-17: the sanctum was visible from spawn) ─────

@pytest.mark.parametrize("seed", SEEDS)
def test_sanctum_sleeps_under_fog_until_the_seal_breaks(seed):
    room = _room(seed)
    W = dg._RELIQUARY_WALL_COL
    # Everything right of the divider — chest, exit, friezes — starts fogged...
    for r in range(1, room.rows - 1):
        for c in range(W + 1, room.cols - 1):
            assert (r, c) in room.fog_cells, (r, c)
    assert (dg._RELIQUARY_CHEST in room.fog_cells)
    # ...and nothing on the approach side is.
    for r in range(1, room.rows - 1):
        for c in range(1, W):
            assert (r, c) not in room.fog_cells, (r, c)
    # Breaking the seal lifts the fog with the ward.
    room.char_runs = [ru for ru in room.char_runs
                      if ru.row != dg._RELIQUARY_ACTION_ROW]
    assert _check_seal_broken(room)
    assert not room.fog_cells


@pytest.mark.parametrize("seed", SEEDS)
def test_approach_friezes_are_symmetric(seed):
    # The masons' discipline: the approach chamber's top and bottom courses
    # are identical, and each is a palindrome about the chamber's centre.
    room = _room(seed)
    c0, c1 = 1, dg._RELIQUARY_WALL_COL - 1
    width = c1 - c0 + 1
    rows = {}
    for fr in dg._RELIQUARY_FRIEZE_ROWS:
        cells = {}
        for ru in room.char_runs:
            if ru.row == fr and ru.col <= c1:
                for i, _s in enumerate(ru.symbols):
                    cells[ru.col + i] = ru.kind
        rows[fr] = cells
    a, b = (rows[fr] for fr in dg._RELIQUARY_FRIEZE_ROWS)
    assert a == b, "top and bottom courses must match"
    assert a, "expected approach friezes"
    mirrored = {c0 + (width - 1 - (c - c0)): k for c, k in a.items()}
    assert a == mirrored, "each course must be a palindrome"


def test_randomizes_across_seeds():
    words   = {''.join(_seal_run(_room(s)).symbols) for s in range(40)}
    friezes = {tuple((ru.row, ru.col, ru.symbols) for ru in sorted(
        (r for r in _room(s).char_runs if r.row in dg._RELIQUARY_FRIEZE_ROWS),
        key=lambda r: (r.row, r.col))) for s in range(40)}
    assert len(words) > 1, "seal word should vary by seed"
    assert len(friezes) > 1, "friezes should vary by seed"
