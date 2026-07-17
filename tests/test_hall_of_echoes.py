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

"""The Hall of Echoes (q @ "): five copies of one blighted verse; record
the two-part mend once, replay it down the hall. Replayed keys are
budget-free; the dot can only carry half of each mend."""
import math

import pytest
from blessed.keyboard import Keystroke
from blessed import Terminal

import main
from engine.world import CellType
from generation.dungeon_gen import (
    build_dungeon_hall_of_echoes,
    _HE_ROWS, _HE_COLS, _HE_SPINE, _HE_ECHOES, _HE_THROAT, _HE_GATE,
    _HE_BOLTS, _HE_EXIT, _HE_PAR, _HE_BUDGET,
)
from tests import SEEDS, cached_room


def _room(seed=0):
    return cached_room('build_dungeon_hall_of_echoes', seed)


def _K(s):
    return [Keystroke(ch) for ch in s]


# The canonical tape (== room.answer): mend the first echo while recording
# into "a — ^ renormalises the column, so the j that ends each mend makes
# the macro position-independent — then 4@a replays down the hall.
CANON = 'jqa^wdawwxjq4@aG$'

# The leanest old-only rival: the straight manual mend, five times over.
# The dot cannot ride here at all — each mend ends with x, so `.` never
# holds the daw when the next row needs it (the two-changes-per-row law).
# Wins, at 1★ (43 ≤ budget 45 > par 14).
RIVAL = 'j' + '^wdawwxj' * 5 + 'G$'


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
    return main.run_dungeon(term, 'hall_of_echoes', {}, player_name=name,
                            _dungeon=dungeon)


def _drive_spent(keys, monkeypatch, seed=0):
    box = {}
    orig = main._calc_stars
    monkeypatch.setattr(main, '_calc_stars',
                        lambda won, budget, room, player, level='':
                            (box.__setitem__('spent', budget.spent),
                             orig(won, budget, room, player, level))[1])
    result = _drive(build_dungeon_hall_of_echoes(seed), keys, monkeypatch)
    return result['won'], box.get('spent')


# ── structure ─────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("seed", SEEDS)
def test_layout_and_identity(seed):
    room = _room(seed)
    assert (room.rows, room.cols) == (_HE_ROWS, _HE_COLS)
    assert room.spawn_pos == (1, _HE_SPINE)
    assert room.exit_pos == _HE_EXIT
    exit_ent = next(e for e in room.entities if e.kind == 'exit')
    assert (exit_ent.row, exit_ent.col) == _HE_EXIT and exit_ent.edit_immune


@pytest.mark.parametrize("seed", SEEDS)
def test_par_answer_budget(seed):
    room = _room(seed)
    assert room.par == _HE_PAR
    assert room.budget == _HE_BUDGET          # GENEROUS hand-set (non-1.4)
    assert room.answer == 'j qa ^ w daw w x j q 4@a G $'


@pytest.mark.parametrize("seed", SEEDS)
def test_exit_and_bolts_start_sealed(seed):
    room = _room(seed)
    for dc in _HE_BOLTS.values():
        assert room.cells[_HE_GATE][dc] == CellType.WALL
    assert room.cells[_HE_EXIT[0]][_HE_EXIT[1]] == CellType.WALL


@pytest.mark.parametrize("seed", SEEDS)
def test_echo_rows_are_identical_but_for_the_tail(seed):
    room = _room(seed)
    w = room._he_words
    for i, r in enumerate(_HE_ECHOES):
        text = main._wla_floor_text(room, r).strip()
        assert text == f"{w['a']} {w['junk']} {w['b']} ◆{w['tails'][i]}"
    assert len(set(w['tails'])) == 5          # five DISTINCT doors


@pytest.mark.parametrize("seed", SEEDS)
def test_targets_are_distinct_and_not_already_true(seed):
    room = _room(seed)
    texts = {main._wla_floor_text(room, r).strip() for r in range(room.rows)}
    targets = [t for (ts, _dc) in room._ss_doors for t in ts]
    assert len(set(targets)) == 5
    for t in targets:
        assert t not in texts


@pytest.mark.parametrize("seed", SEEDS)
def test_throat_is_spine_only(seed):
    room = _room(seed)
    cols = [c for c in range(room.cols) if room.is_passable(_HE_THROAT, c)]
    assert cols == [_HE_SPINE]


# ── playthroughs ─────────────────────────────────────────────────────────────

@pytest.mark.parametrize("seed", SEEDS)
def test_canonical_macro_run_wins_at_par(seed, monkeypatch):
    won, spent = _drive_spent(_K(CANON), monkeypatch, seed)
    assert won and spent == _HE_PAR


@pytest.mark.parametrize("seed", SEEDS)
def test_dot_manual_rival_wins_at_one_star(seed, monkeypatch):
    room = _room(seed)
    won, spent = _drive_spent(_K(RIVAL), monkeypatch, seed)
    assert won and _HE_PAR < spent <= room.budget


def test_replayed_keys_are_budget_free(monkeypatch):
    # The whole point of the pricing: 4@a costs 3, not 4× the macro body.
    dungeon = build_dungeon_hall_of_echoes(0)
    box = {}
    orig = main._calc_stars
    monkeypatch.setattr(main, '_calc_stars',
                        lambda won, budget, room, player, level='':
                            (box.__setitem__('spent', budget.spent),
                             orig(won, budget, room, player, level))[1])
    _drive(dungeon, _K(CANON), monkeypatch)
    assert box['spent'] == _HE_PAR


def test_macro_records_the_mend(monkeypatch):
    dungeon = build_dungeon_hall_of_echoes(0)
    room = dungeon.rooms[0]
    seen = {}
    orig = main._enemy_tick

    def spy(room_, player):
        seen['p'] = player
        return orig(room_, player)

    monkeypatch.setattr(main, '_enemy_tick', spy)
    _drive(dungeon, _K('jqa^wdawwxjq'), monkeypatch, finish=':q!\r')
    assert seen['p'].macros.get('a') == '^wdawwxj'


def test_one_mended_row_opens_only_its_own_bolt(monkeypatch):
    # Distinct tails: the row-agnostic matcher must not open sibling bolts.
    dungeon = build_dungeon_hall_of_echoes(0)
    room = dungeon.rooms[0]
    _drive(dungeon, _K('j^wdawwx'), monkeypatch, finish=':q!\r')
    assert room.cells[_HE_GATE][_HE_BOLTS[2]] == CellType.FLOOR
    for r in _HE_ECHOES[1:]:
        assert room.cells[_HE_GATE][_HE_BOLTS[r]] == CellType.WALL


def test_half_mend_leaves_the_bolt_barred(monkeypatch):
    # daw alone (the dot's share) is not the mend — the ◆ still stands.
    dungeon = build_dungeon_hall_of_echoes(0)
    room = dungeon.rooms[0]
    _drive(dungeon, _K('j^wdaw'), monkeypatch, finish=':q!\r')
    assert room.cells[_HE_GATE][_HE_BOLTS[2]] == CellType.WALL


def test_undo_rebars_an_open_bolt(monkeypatch):
    dungeon = build_dungeon_hall_of_echoes(0)
    room = dungeon.rooms[0]
    _drive(dungeon, _K('j^wdawwxu'), monkeypatch, finish=':q!\r')
    assert room.cells[_HE_GATE][_HE_BOLTS[2]] == CellType.WALL


# ── teleport audit ───────────────────────────────────────────────────────────

def test_no_jump_lands_on_the_sealed_exit(monkeypatch):
    dungeon = build_dungeon_hall_of_echoes(0)
    seen = {}
    orig = main._calc_stars

    def spy(won, budget, room_, player, level=''):
        seen['pos'] = (player.row, player.col)
        return orig(won, budget, room_, player, level)

    monkeypatch.setattr(main, '_calc_stars', spy)
    result = _drive(dungeon, _K('G$'), monkeypatch, finish=':wq\r')
    assert not result['won']
    assert seen['pos'][1] < _HE_EXIT[1], seen


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
    assert _HE_EXIT not in seen
