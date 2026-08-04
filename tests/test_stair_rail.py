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

"""The Stair Rail (+ - _): a VALLEY of five steps (spawn on the middle one)
whose columns zigzag, so j/k strand the cursor beside each word while +/-
land it. The valley sits LOW, so a relative {n}+/{n}- (1-digit) beats the
absolute {nn}G (2-digit) that would otherwise tie it. A counted {n}_ drop
lands straight on the exit at the gate row's own first non-blank; G
undershoots to the undercroft below."""
import math

import pytest
from blessed.keyboard import Keystroke
from blessed import Terminal

import vimny.game as main
from vimny.engine.world import CellType
from vimny.generation.dungeon_gen import (
    build_dungeon_stair_rail,
    _SR_ROWS, _SR_COLS, _SR_STEP_ROWS, _SR_STEP_COLS, _SR_SPAWN_IDX, _SR_GATE,
    _SR_BOLT_COLS, _SR_EXIT, _SR_UNDERCROFT, _SR_CHEST, _SR_PAR,
)
from tests import SEEDS, cached_room


def _room(seed=0):
    return cached_room('build_dungeon_stair_rail', seed)


def _K(s):
    return [Keystroke(ch) for ch in s]


_SPAWN = (_SR_STEP_ROWS[_SR_SPAWN_IDX], _SR_STEP_COLS[_SR_SPAWN_IDX])

# The canonical tape (== room.answer): x the middle step, climb with - to the
# two steps above, descend with + to the two below, then a counted + drops
# straight onto the exit at the gate's first non-blank ({n}_ only ever TIES
# {n-1}+, so the tape takes the +).
CANON = 'x2-xHx6+x2+x4+'

# The k/j-walker: every step pays k/j + ^ where the rail pays -/+, and the
# drop is walked with a counted j plus the caret. (The {nn}G route ties this
# — both are one key dearer per step than the relative rail.) Wins, at 1★.
RIVAL = 'x2k^x2k^x6j^x2j^x4j^'


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
    assert room.spawn_pos == _SPAWN          # on the MIDDLE step
    assert room.exit_pos == _SR_EXIT
    exit_ent = next(e for e in room.entities if e.kind == 'exit')
    assert (exit_ent.row, exit_ent.col) == _SR_EXIT and exit_ent.edit_immune


@pytest.mark.parametrize("seed", SEEDS)
def test_par_answer_budget(seed):
    room = _room(seed)
    assert room.par == _SR_PAR
    assert room.budget == math.ceil(_SR_PAR * 1.4)
    assert room.answer == 'x 2- x H x 6+ x 2+ x 4+'


@pytest.mark.parametrize("seed", SEEDS)
def test_steps_zigzag_at_two_digit_rows(seed):
    # Each step's word sits at its own zigzag column (so j/k strand the
    # cursor on bare floor beside a landing), and every step's line number
    # is TWO digits (so {nn}G can't undercut the 1-digit relative rail).
    room = _room(seed)
    for k, r in enumerate(_SR_STEP_ROWS):
        run = next(ru for ru in room.char_runs
                   if ru.row == r and ru.col >= _SR_STEP_COLS[k])
        assert run.col == _SR_STEP_COLS[k]
        assert run.symbols[0] == '◆'
        assert r >= 10                       # two-digit line number
    # neighbouring steps never share a column — the zigzag
    for a, b in zip(_SR_STEP_COLS, _SR_STEP_COLS[1:]):
        assert a != b


@pytest.mark.parametrize("seed", SEEDS)
def test_undercroft_is_below_the_gate(seed):
    # The last standable line is the undercroft, not the gate — G undershoots;
    # only a counted _ (or the k/j-walk) lands the gate row.
    room = _room(seed)
    standable = [r for r in range(room.rows)
                 if any(room.is_passable(r, c) for c in range(room.cols))]
    assert standable[-1] == _SR_UNDERCROFT > _SR_GATE
    # chest_SCROLL: the undercroft reward is a relic scroll, and a random chest
    # paid it out only one time in three.
    chest = next(e for e in room.entities if e.kind == 'chest_scroll')
    assert (chest.row, chest.col) == _SR_CHEST


@pytest.mark.parametrize("seed", SEEDS)
def test_exit_and_bolts_start_sealed(seed):
    room = _room(seed)
    for dc in _SR_BOLT_COLS:
        assert room.cells[_SR_GATE][dc] == CellType.WALL
    assert room.cells[_SR_EXIT[0]][_SR_EXIT[1]] == CellType.WALL
    # the exit sits AT the gate row's first non-blank (west of the bolts)
    assert _SR_EXIT[1] < min(_SR_BOLT_COLS)


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
    assert seen['pos'][0] == _SR_UNDERCROFT   # the decoy landing


def test_undo_rebars_an_open_bolt(monkeypatch):
    dungeon = build_dungeon_stair_rail(0)
    room = dungeon.rooms[0]
    # spawn is ON S3 — its mend carves the FIRST corridor cell (nearest the
    # valley); undo re-walls it
    _drive(dungeon, _K('x'), monkeypatch, finish=':q!\r')
    assert room.cells[_SR_GATE][_SR_BOLT_COLS[0]] == CellType.FLOOR
    dungeon2 = build_dungeon_stair_rail(0)
    room2 = dungeon2.rooms[0]
    _drive(dungeon2, _K('xu'), monkeypatch, finish=':q!\r')
    assert room2.cells[_SR_GATE][_SR_BOLT_COLS[0]] == CellType.WALL


def test_each_mend_carves_the_corridor_east_to_west(monkeypatch):
    # Following the canonical route, every x extends the stone-cut corridor
    # one contiguous cell further west toward the seal.
    legs = ['x', 'x2-x', 'x2-xHx', 'x2-xHx6+x', 'x2-xHx6+x2+x']
    for n, tape in enumerate(legs, start=1):
        d = build_dungeon_stair_rail(0)
        _drive(d, _K(tape), monkeypatch, finish=':q!\r')
        r = d.rooms[0]
        for i, dc in enumerate(_SR_BOLT_COLS):
            want = CellType.FLOOR if i < n else CellType.WALL
            assert r.cells[_SR_GATE][dc] == want


def test_ex_substitute_opens_gates_the_same_turn(monkeypatch):
    # An ex edit fires the gate ticks THIS turn (no one-key lag): the pasted
    # :%s strike opens every bolt AND the seal immediately, so the very next
    # {n}+ (from the last substituted row, where :%s parks the cursor) lands
    # straight on the exit and :wq wins.
    dungeon = build_dungeon_stair_rail(0)
    result = _drive(dungeon, _K(':%s/◆//\r4+'), monkeypatch, finish=':wq\r')
    assert result['won']
    r = dungeon.rooms[0]
    for dc in _SR_BOLT_COLS:
        assert r.cells[_SR_GATE][dc] == CellType.FLOOR
    assert r.cells[_SR_EXIT[0]][_SR_EXIT[1]] == CellType.FLOOR


# ── teleport audit ───────────────────────────────────────────────────────────

def test_no_jump_lands_on_the_sealed_exit(monkeypatch):
    dungeon = build_dungeon_stair_rail(0)
    seen = {}
    orig = main._calc_stars

    def spy(won, budget, room_, player, level=''):
        seen['pos'] = (player.row, player.col)
        return orig(won, budget, room_, player, level)

    monkeypatch.setattr(main, '_calc_stars', spy)
    # jump straight to the gate row and try to reach the exit while sealed
    result = _drive(dungeon, _K(f'{_SR_GATE}G0'), monkeypatch, finish=':wq\r')
    assert not result['won']
    assert seen['pos'] != _SR_EXIT, seen      # the sealed exit is never a landing


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
