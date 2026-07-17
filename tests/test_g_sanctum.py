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

"""The G-Sanctum (the g-family): three verses running east into water —
$ overshoots onto the flood and drowns; g_ lands the last glyph (water
carries no characters); counted e-walks pay two digits."""
import math

import pytest
from blessed.keyboard import Keystroke
from blessed import Terminal

import main
from engine.world import CellType
from generation.dungeon_gen import (
    build_dungeon_g_sanctum,
    _GS_ROWS, _GS_COLS, _GS_SPINE, _GS_BAYS, _GS_NWORDS, _GS_POOL,
    _GS_GATE, _GS_BOLTS, _GS_EXIT, _GS_PAR,
)
from tests import SEEDS, cached_room


def _room(seed=0):
    return cached_room('build_dungeon_g_sanctum', seed)


def _K(s):
    return [Keystroke(ch) for ch in s]


# The canonical tape (== room.answer): g_ from the spine lands the fused ◆
# at each verse's end; x (then the dot) mends it; + chains the bays.
CANON = 'jg_x+g_.+g_.G$'

# The counted-e rival: every verse is 10+ words, so the walk to the end
# pays two count digits per row where g_ pays two keys flat — and the ◆ is
# its own punctuation word-end, so the count is words+1; the rows are
# unequal, so no count transfers blind. Wins, at 1★ (17 ≤ 20 > 14).
RIVAL = 'j11ex+13e.+12e.G$'


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
    return main.run_dungeon(term, 'g_sanctum', {}, player_name=name,
                            _dungeon=dungeon)


def _drive_spent(keys, monkeypatch, seed=0):
    box = {}
    orig = main._calc_stars
    monkeypatch.setattr(main, '_calc_stars',
                        lambda won, budget, room, player, level='':
                            (box.__setitem__('spent', budget.spent),
                             orig(won, budget, room, player, level))[1])
    result = _drive(build_dungeon_g_sanctum(seed), keys, monkeypatch)
    return result['won'], box.get('spent')


# ── structure ─────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("seed", SEEDS)
def test_layout_and_identity(seed):
    room = _room(seed)
    assert (room.rows, room.cols) == (_GS_ROWS, _GS_COLS)
    assert room.spawn_pos == (1, _GS_SPINE)
    assert room.exit_pos == _GS_EXIT
    exit_ent = next(e for e in room.entities if e.kind == 'exit')
    assert (exit_ent.row, exit_ent.col) == _GS_EXIT and exit_ent.edit_immune


@pytest.mark.parametrize("seed", SEEDS)
def test_par_answer_budget(seed):
    room = _room(seed)
    assert room.par == _GS_PAR
    assert room.budget == math.ceil(_GS_PAR * 1.4)
    assert room.answer == 'j g_ x + g_ . + g_ . G $'


@pytest.mark.parametrize("seed", SEEDS)
def test_verses_end_in_a_fused_glyph_before_the_flood(seed):
    room = _room(seed)
    for i, r in enumerate(_GS_BAYS):
        runs = sorted((ru for ru in room.char_runs
                       if ru.row == r and _GS_SPINE < ru.col < _GS_POOL[0]),
                      key=lambda ru: ru.col)
        assert len(runs) == _GS_NWORDS[i]
        assert runs[-1].symbols[-1] == '◆'
        for c in _GS_POOL:                    # the drowning pool past the verse
            assert room.cells[r][c] == CellType.WATER


@pytest.mark.parametrize("seed", SEEDS)
def test_word_counts_are_two_digit_and_unequal(seed):
    assert all(n >= 10 for n in _GS_NWORDS)
    assert len(set(_GS_NWORDS)) == 3


@pytest.mark.parametrize("seed", SEEDS)
def test_exit_and_bolts_start_sealed(seed):
    room = _room(seed)
    for dc in _GS_BOLTS.values():
        assert room.cells[_GS_GATE][dc] == CellType.WALL
    assert room.cells[_GS_EXIT[0]][_GS_EXIT[1]] == CellType.WALL


# ── playthroughs ─────────────────────────────────────────────────────────────

@pytest.mark.parametrize("seed", SEEDS)
def test_canonical_g_run_wins_at_par(seed, monkeypatch):
    won, spent = _drive_spent(_K(CANON), monkeypatch, seed)
    assert won and spent == _GS_PAR


@pytest.mark.parametrize("seed", SEEDS)
def test_counted_e_rival_wins_at_one_star(seed, monkeypatch):
    room = _room(seed)
    won, spent = _drive_spent(_K(RIVAL), monkeypatch, seed)
    assert won and _GS_PAR < spent <= room.budget


def test_dollar_drowns_in_the_flood(monkeypatch):
    # The forcing terrain: $ overshoots the text onto the water.
    dungeon = build_dungeon_g_sanctum(0)
    result = _drive(dungeon, _K('j$'), monkeypatch, finish=':q!\r')
    assert not result['won']


def test_g_underscore_lands_the_last_glyph(monkeypatch):
    dungeon = build_dungeon_g_sanctum(0)
    room = dungeon.rooms[0]
    seen = {}
    orig = main._enemy_tick

    def spy(room_, player):
        seen['pos'] = (player.row, player.col)
        return orig(room_, player)

    monkeypatch.setattr(main, '_enemy_tick', spy)
    _drive(dungeon, _K('jg_'), monkeypatch, finish=':q!\r')
    r, c = seen['pos']
    assert r == _GS_BAYS[0]
    run = max((ru for ru in room.char_runs
               if ru.row == r and ru.kind == 'ancient'), key=lambda ru: ru.col)
    assert c == run.col + len(run.symbols) - 1      # the ◆, not the brink


def test_undo_rebars_an_open_bolt(monkeypatch):
    dungeon = build_dungeon_g_sanctum(0)
    room = dungeon.rooms[0]
    _drive(dungeon, _K('jg_xu'), monkeypatch, finish=':q!\r')
    assert room.cells[_GS_GATE][_GS_BOLTS[2]] == CellType.WALL


# ── teleport audit ───────────────────────────────────────────────────────────

def test_no_jump_lands_on_the_sealed_exit(monkeypatch):
    dungeon = build_dungeon_g_sanctum(0)
    seen = {}
    orig = main._calc_stars

    def spy(won, budget, room_, player, level=''):
        seen['pos'] = (player.row, player.col)
        return orig(won, budget, room_, player, level)

    monkeypatch.setattr(main, '_calc_stars', spy)
    result = _drive(dungeon, _K('G$'), monkeypatch, finish=':wq\r')
    assert not result['won']
    assert seen['pos'][1] < _GS_EXIT[1], seen


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
    assert _GS_EXIT not in seen
