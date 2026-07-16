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

"""The Brace & Square Enclosure (i[ a[ i{ a{): choose the object, and in the
nest choose the DEPTH — di{ and di[ carve different spans from one landing."""
import math

import pytest
from blessed.keyboard import Keystroke
from blessed import Terminal

import main
from engine.world import CellType
from generation.dungeon_gen import (
    build_dungeon_brace_square_enclosure,
    _BSQ_ROWS, _BSQ_COLS, _BSQ_SPINE, _BSQ_SHAFT_SEPS, _BSQ_THROAT,
    _BSQ_GATE, _BSQ_BOLTS, _BSQ_EXIT, _BSQ_PAR, _BSQ_TEXT0,
    _BSQ_C1_ROWS, _BSQ_C2_ROWS, _BSQ_C3_ROWS, _BSQ_C4_ROWS, _BSQ_C5_ROWS,
)
from tests import SEEDS, cached_room

ESC = Keystroke('\x1b', name='KEY_ESCAPE')


def _room(seed=0):
    return cached_room('build_dungeon_brace_square_enclosure', seed)


def _K(s):
    return [Keystroke(ch) for ch in s]


# The canonical tape (== room.answer with Esc placed): % entry, di[ husks
# chained by dot, ci[ cures, the family switch to di{ (fresh — a blind dot
# here would replay ci[+text), the NEST (di{ then di[ from the same landing
# column), the da{ scar. 45 keys; the cures vary by seed.
def _canon_keys(room):
    ca, cb = room._bsq_words['cures']
    return (_K('j%di[j.') + _K('2jci[') + _K(ca) + [ESC]
            + _K('jci[') + _K(cb) + [ESC]
            + _K('2jdi{j.') + _K('2jdi{jdi[') + _K('2jda{') + _K('G$'))


# The leanest old-only rival (WITH its own best dot usage): walks and edge-
# finds (dt] / ct] / dt} need the junk edge the landings don't give; the
# scar falls to h d% — a paid h, never a win). Wins, at 1★ (55 > par).
def _piecewise_rival_keys(room):
    ca, cb = room._bsq_words['cures']
    return (_K('jwwldt]jhdt]') + _K('2jhct]') + _K(ca) + [ESC]
            + _K('jhhct]') + _K(cb) + [ESC]
            + _K('2jhdt}jl.') + _K('2jh.jhdt]') + _K('2jhd%') + _K('G$'))


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
    return main.run_dungeon(term, 'brace_square_enclosure', {}, player_name=name,
                            _dungeon=dungeon)


def _drive_spent(keys, monkeypatch, seed=0):
    box = {}
    orig = main._calc_stars
    monkeypatch.setattr(main, '_calc_stars',
                        lambda won, budget, room, player, level='':
                            (box.__setitem__('spent', budget.spent),
                             orig(won, budget, room, player, level))[1])
    result = _drive(build_dungeon_brace_square_enclosure(seed), keys, monkeypatch)
    return result['won'], box.get('spent')


# ── dungeon structure ─────────────────────────────────────────────────────────

@pytest.mark.parametrize("seed", SEEDS)
def test_layout_and_identity(seed):
    room = _room(seed)
    assert (room.rows, room.cols) == (_BSQ_ROWS, _BSQ_COLS)
    assert room.spawn_pos == (2, _BSQ_SPINE)
    assert room.exit_pos == _BSQ_EXIT
    exit_ent = next(e for e in room.entities if e.kind == 'exit')
    assert (exit_ent.row, exit_ent.col) == _BSQ_EXIT and exit_ent.edit_immune


@pytest.mark.parametrize("seed", SEEDS)
def test_par_answer_budget(seed):
    room = _room(seed)
    assert room.par == _BSQ_PAR
    assert room.budget == math.ceil(_BSQ_PAR * 1.4)
    ca, cb = room._bsq_words['cures']
    assert room.answer == (f'j % di[ j . 2j ci[ {ca} j ci[ {cb} '
                           f'2j di{{ j . 2j di{{ j di[ 2j da{{ G $')


@pytest.mark.parametrize("seed", SEEDS)
def test_exit_and_bolts_start_sealed(seed):
    room = _room(seed)
    for dc in _BSQ_BOLTS.values():
        assert room.cells[_BSQ_GATE][dc] == CellType.WALL
    assert room.cells[_BSQ_EXIT[0]][_BSQ_EXIT[1]] == CellType.WALL


def test_nest_twin_bolts_are_the_centre_pair():
    # The C4 twins sit dead centre of the six-bolt run, adjacent — the
    # matched pair reads as one double door.
    cols = sorted(_BSQ_BOLTS.values())
    assert (_BSQ_BOLTS['c4a'], _BSQ_BOLTS['c4b']) == (cols[2], cols[3])
    assert _BSQ_BOLTS['c4b'] == _BSQ_BOLTS['c4a'] + 1
    assert _BSQ_EXIT[1] > max(cols)          # exit east of every bolt ($ finish)


@pytest.mark.parametrize("seed", SEEDS)
def test_spine_is_every_rows_first_standable(seed):
    room = _room(seed)
    for r in range(room.rows):
        cols = [c for c in range(room.cols) if room.is_passable(r, c)]
        if cols:
            assert cols[0] == _BSQ_SPINE, f"row {r} first standable {cols[0]}"


@pytest.mark.parametrize("seed", SEEDS)
def test_light_shafts_pierce_separators_but_not_the_throat(seed):
    room = _room(seed)
    for r, c in _BSQ_SHAFT_SEPS:
        assert room.cells[r][c] == CellType.FLOOR
        others = [cc for cc in range(room.cols)
                  if room.is_passable(r, cc) and cc not in (c, _BSQ_SPINE)]
        assert not others
    throat = [c for c in range(room.cols) if room.is_passable(_BSQ_THROAT, c)]
    assert throat == [_BSQ_SPINE]


@pytest.mark.parametrize("seed", SEEDS)
def test_no_chest(seed):
    room = _room(seed)
    assert not [e for e in room.entities
                if e.kind in ('chest', 'chest_key', 'chest_scroll')]


# ── plaques: full true readings, twin colours ────────────────────────────────

def _plaque_text(room, r):
    cells = {}
    for ru in room.char_runs:
        if ru.row == r and ru.col < _BSQ_SPINE:
            for i, s in enumerate(ru.symbols):
                cells[ru.col + i] = s
    if not cells:
        return ''
    lo, hi = min(cells), max(cells)
    return ''.join(cells.get(c, ' ') for c in range(lo, hi + 1))


@pytest.mark.parametrize("seed", SEEDS)
def test_plaques_carry_the_full_readings(seed):
    room = _room(seed)
    for targets, _dc in room._ss_doors:
        for t in targets:
            assert any(_plaque_text(room, r) == t for r in range(room.rows)), t


@pytest.mark.parametrize("seed", SEEDS)
def test_nest_plaques_are_the_coloured_pair(seed):
    room = _room(seed)
    kinds = {r: {ru.kind for ru in room.char_runs
                 if ru.row == r and ru.col < _BSQ_SPINE}
             for r in _BSQ_C4_ROWS}
    assert kinds[12] == {'ember'}
    assert kinds[13] == {'pedestal'}


@pytest.mark.parametrize("seed", SEEDS)
def test_vocab_slots_and_distinctness(seed):
    room = _room(seed)
    words = room._bsq_words
    picks = [w for row in words['rows'] for part in row for w in part.split(' ')]
    picks += list(words['cures']) + list(words['flanks'].values())
    assert len(set(picks)) == len(picks)
    assert all(len(c) == 3 for c in words['cures'])
    assert all(len(f) == 3 for f in words['flanks'].values())


# ── the doors ────────────────────────────────────────────────────────────────

def _floor_texts(room):
    return {main._wla_floor_text(room, r).strip() for r in range(room.rows)}


@pytest.mark.parametrize("seed", SEEDS)
def test_targets_are_not_already_true(seed):
    room = _room(seed)
    texts = _floor_texts(room)
    for targets, _dc in room._ss_doors:
        for t in targets:
            assert t not in texts


@pytest.mark.parametrize("seed", SEEDS)
def test_nest_discrimination_di_bracket_cannot_open_the_brace_door(seed):
    # di[ on row 12 yields 'w1 [] w2' — the row-13 door's SHAPE but never its
    # WORDS (the draw is distinct), so C4a stays barred and C4b can't false-fire.
    room = _room(seed)
    tgt_a = room._ss_doors[3][0][0]                 # c4a target
    tgt_b = room._ss_doors[4][0][0]                 # c4b target
    w1_12, w2_12 = (t for t in (room._bsq_words['rows'][6][0],
                                room._bsq_words['rows'][6][2]))
    wrong = f'{w1_12} [] {w2_12}'                   # di[ on row 12
    assert wrong != tgt_a and wrong != tgt_b


# ── playthroughs ─────────────────────────────────────────────────────────────

@pytest.mark.parametrize("seed", SEEDS)
def test_canonical_run_wins_at_par(seed, monkeypatch):
    room = build_dungeon_brace_square_enclosure(seed).rooms[0]
    won, spent = _drive_spent(_canon_keys(room), monkeypatch, seed)
    assert won and spent == _BSQ_PAR


@pytest.mark.parametrize("seed", SEEDS)
def test_piecewise_rival_wins_at_one_star(seed, monkeypatch):
    dungeon = build_dungeon_brace_square_enclosure(seed)
    room = dungeon.rooms[0]
    won, spent = _drive_spent(_piecewise_rival_keys(room), monkeypatch, seed)
    assert won and _BSQ_PAR < spent <= room.budget


def test_blind_dot_off_c2_is_a_costed_noop(monkeypatch):
    # After the ci[ cures, '.' replays ci[+text; the brace rows hold no [ so
    # the replay changes nothing — the family switch must be deliberate.
    dungeon = build_dungeon_brace_square_enclosure(0)
    room = dungeon.rooms[0]
    ca, cb = room._bsq_words['cures']
    keys = (_K('j%di[j.') + _K('2jci[') + _K(ca) + [ESC]
            + _K('jci[') + _K(cb) + [ESC] + _K('2j.'))
    _drive(dungeon, keys, monkeypatch, finish=':q!\r')
    texts = _floor_texts(room)
    c3_targets = room._ss_doors[2][0]
    assert not any(t in texts for t in c3_targets)


def test_undo_rebars_an_open_bolt(monkeypatch):
    dungeon = build_dungeon_brace_square_enclosure(0)
    room = dungeon.rooms[0]
    keys = _K('j%di[j.') + _K('u')                  # open C1, then undo row 4
    _drive(dungeon, keys, monkeypatch, finish=':q!\r')
    assert room.cells[_BSQ_GATE][_BSQ_BOLTS['c1']] == CellType.WALL


# ── teleport audit ───────────────────────────────────────────────────────────

def test_no_jump_lands_on_the_sealed_exit(monkeypatch):
    dungeon = build_dungeon_brace_square_enclosure(0)
    seen = {}
    orig = main._calc_stars
    def spy(won, budget, room_, player, level=''):
        seen['pos'] = (player.row, player.col)
        return orig(won, budget, room_, player, level)
    monkeypatch.setattr(main, '_calc_stars', spy)
    result = _drive(dungeon, _K('G$'), monkeypatch, finish=':wq\r')
    assert not result['won']
    assert seen['pos'] == (_BSQ_GATE, _BSQ_SPINE), seen


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
    assert _BSQ_EXIT not in seen
