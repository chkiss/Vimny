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

"""The Stair Rail (+ - _): an east-drifting staircase where j strands the
cursor beside each word and + lands it; a long counted drop (8_) to a gate
that G undershoots (the undercroft below is the last line)."""
import math

import pytest
from blessed.keyboard import Keystroke
from blessed import Terminal

import main
from engine.world import CellType
from generation.dungeon_gen import (
    build_dungeon_stair_rail,
    _SR_ROWS, _SR_COLS, _SR_STEPS, _SR_TEXT0, _SR_STEP_DX, _SR_GATE,
    _SR_BOLTS, _SR_EXIT, _SR_CELLAR, _SR_CHEST, _SR_PAR,
)
from tests import SEEDS, cached_room


def _room(seed=0):
    return cached_room('build_dungeon_stair_rail', seed)


def _K(s):
    return [Keystroke(ch) for ch in s]


# The canonical tape (== room.answer): x the first fused glyph, then ride
# the rail — each + lands on the next step's word in one key — and take
# the whole drop with a single counted _.
CANON = 'jx' + '+x' * 4 + '8_$'

# The j-walker: every step pays j + ^ where the rail pays +, and the drop
# is walked with a counted j plus the caret. Wins, at 1★ (17 ≤ 19 > 13).
RIVAL = 'jx' + 'j^x' * 4 + '7j^$'


def _drive(dungeon, keys, monkeypatch, finish=':wq\r', name='Scribe'):
    keys = list(keys) + _K(finish)
    monkeypatch.setattr(main, 'render_all', lambda *a, **k: None)
    monkeypatch.setattr(main.time, 'sleep', lambda *a, **k: None)
    for anim in ('_fireworks_animation', '_win_animation', '_starfield_victory',
                 '_heart_container_animation', '_unlock_animation',
                 '_void_fall_animation', '_drown_animation'):
        monkeypatch.setattr(main, anim, lambda *a, **k: None)
    monkeypatch.setattr(Terminal, 'height', property(lambda self: 41))
    term = Terminal()
    it = iter(keys)
    monkeypatch.setattr(term, 'inkey', lambda *a, **k: next(it, Keystroke('')))
    return main.run_dungeon(term, 'stair_rail', {}, player_name=name,
                            _dungeon=dungeon)


def _drive_spent(keys, monkeypatch, seed=0):
    box = {}
    orig = main._calc_stars
    monkeypatch.setattr(main, '_calc_stars',
                        lambda won, budget, room, player, level='':
                            (box.__setitem__('spent', budget.spent),
                             orig(won, budget, room, player, level))[1])
    result = _drive(build_dungeon_stair_rail(seed), keys, monkeypatch)
    return result['won'], box.get('spent')


# ── structure ─────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("seed", SEEDS)
def test_layout_and_identity(seed):
    room = _room(seed)
    assert (room.rows, room.cols) == (_SR_ROWS, _SR_COLS)
    assert room.spawn_pos == (1, _SR_TEXT0)
    assert room.exit_pos == _SR_EXIT
    exit_ent = next(e for e in room.entities if e.kind == 'exit')
    assert (exit_ent.row, exit_ent.col) == _SR_EXIT and exit_ent.edit_immune


@pytest.mark.parametrize("seed", SEEDS)
def test_par_answer_budget(seed):
    room = _room(seed)
    assert room.par == _SR_PAR
    assert room.budget == math.ceil(_SR_PAR * 1.4)
    assert room.answer == 'j x + x + x + x + x 8_ $'


@pytest.mark.parametrize("seed", SEEDS)
def test_stair_drifts_east(seed):
    # Each step's word sits STEP_DX east of the one above — the geometry
    # that makes j strand the cursor on bare floor beside every landing.
    room = _room(seed)
    for k, r in enumerate(_SR_STEPS):
        run = next(ru for ru in room.char_runs
                   if ru.row == r and ru.col >= _SR_TEXT0)
        assert run.col == _SR_TEXT0 + k * _SR_STEP_DX
        assert run.symbols[0] == '◆'


@pytest.mark.parametrize("seed", SEEDS)
def test_undercroft_is_below_the_gate(seed):
    # The last standable line is the cellar, not the gate — G undershoots;
    # only a counted _ (or the j-walk) lands the gate row.
    room = _room(seed)
    standable = [r for r in range(room.rows)
                 if any(room.is_passable(r, c) for c in range(room.cols))]
    assert standable[-1] == _SR_CELLAR[-1] > _SR_GATE
    chest = next(e for e in room.entities if e.kind == 'chest')
    assert (chest.row, chest.col) == _SR_CHEST


@pytest.mark.parametrize("seed", SEEDS)
def test_exit_and_bolts_start_sealed(seed):
    room = _room(seed)
    for dc in _SR_BOLTS.values():
        assert room.cells[_SR_GATE][dc] == CellType.WALL
    assert room.cells[_SR_EXIT[0]][_SR_EXIT[1]] == CellType.WALL


# ── playthroughs ─────────────────────────────────────────────────────────────

@pytest.mark.parametrize("seed", SEEDS)
def test_canonical_rail_run_wins_at_par(seed, monkeypatch):
    won, spent = _drive_spent(_K(CANON), monkeypatch, seed)
    assert won and spent == _SR_PAR


@pytest.mark.parametrize("seed", SEEDS)
def test_j_walker_rival_wins_at_one_star(seed, monkeypatch):
    room = _room(seed)
    won, spent = _drive_spent(_K(RIVAL), monkeypatch, seed)
    assert won and _SR_PAR < spent <= room.budget


def test_G_undershoots_into_the_undercroft(monkeypatch):
    dungeon = build_dungeon_stair_rail(0)
    seen = {}
    orig = main._calc_stars

    def spy(won, budget, room_, player, level=''):
        seen['pos'] = (player.row, player.col)
        return orig(won, budget, room_, player, level)

    monkeypatch.setattr(main, '_calc_stars', spy)
    result = _drive(dungeon, _K('G'), monkeypatch, finish=':wq\r')
    assert not result['won']
    assert seen['pos'][0] in _SR_CELLAR       # the decoy landing


def test_undo_rebars_an_open_bolt(monkeypatch):
    dungeon = build_dungeon_stair_rail(0)
    room = dungeon.rooms[0]
    _drive(dungeon, _K('jxu'), monkeypatch, finish=':q!\r')
    assert room.cells[_SR_GATE][_SR_BOLTS[2]] == CellType.WALL


# ── teleport audit ───────────────────────────────────────────────────────────

def test_no_jump_lands_on_the_sealed_exit(monkeypatch):
    dungeon = build_dungeon_stair_rail(0)
    seen = {}
    orig = main._calc_stars

    def spy(won, budget, room_, player, level=''):
        seen['pos'] = (player.row, player.col)
        return orig(won, budget, room_, player, level)

    monkeypatch.setattr(main, '_calc_stars', spy)
    result = _drive(dungeon, _K('13G$'), monkeypatch, finish=':wq\r')
    assert not result['won']
    assert seen['pos'][1] < _SR_EXIT[1], seen


@pytest.mark.parametrize("seed", SEEDS)
def test_exit_unreachable_until_all_true(seed):
    from collections import deque
    room = _room(seed)
    seen, dq = {room.spawn_pos}, deque([room.spawn_pos])
    while dq:
        r, c = dq.popleft()
        for dr, dc in ((0, 1), (0, -1), (1, 0), (-1, 0)):
            nr, nc = r + dr, c + dc
            if (nr, nc) not in seen and 0 <= nr < room.rows and 0 <= nc < room.cols \
                    and room.is_passable(nr, nc):
                seen.add((nr, nc))
                dq.append((nr, nc))
    assert _SR_EXIT not in seen
