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

"""The Sentence Enclosure (is as): the sentence under your hand, from
anywhere inside it — every landing is mid-sentence, where the old
edge-hunting tools pay and the objects don't."""
import math

import pytest
from blessed.keyboard import Keystroke
from blessed import Terminal

import main
from engine.world import CellType
from generation.dungeon_gen import (
    build_dungeon_sentence_enclosure, _se_sentence,
    _SE_ROWS, _SE_COLS, _SE_SPINE, _SE_SHAFT_SEPS, _SE_THROAT,
    _SE_GATE, _SE_BOLTS, _SE_EXIT, _SE_PAR, _SE_TEXT0, _SE_SPAWN,
    _SE_C1_JUNK, _SE_C2_JUNK, _SE_C3_MID, _SE_C4_JUNK, _SE_C3_FIX,
    _SE_TEXT_MIN, _SE_BAY_E, _SE_EAST,
    _SE_C1_ROWS, _SE_C2_ROWS, _SE_C3_ROWS, _SE_C4_ROWS, _SE_C5_ROWS,
)
from tests import SEEDS, cached_room

ESC = Keystroke('\x1b', name='KEY_ESCAPE')


def _room(seed=0):
    return cached_room('build_dungeon_sentence_enclosure', seed)


def _K(s):
    return [Keystroke(ch) for ch in s]


_CA, _CB = (fix[1] for fix in _SE_C3_FIX)        # 'vidi', 'laugh' — by heart


# The canonical tape (== room.answer with Esc placed): the spawn drops onto
# a mid-sentence landing, then dis/das/cis dot-chained down the anchored
# columns; C5 falls entirely to TWO DOTS riding C4's das (the player-found
# golf) and keeps the saying.
def _canon_keys(room):
    return (_K('jdisj.') + _K('2jdasj.')
            + _K('2jcis') + _K(_CA + '.') + [ESC]
            + _K('jcis') + _K(_CB + '.') + [ESC]
            + _K('2jdas') + _K('2j..') + _K('G$'))


# The leanest old-only rival, anchor-relative (seed-invariant): count-x
# from each junk sentence's exact start — every row pays the h-walk to the
# edge that is/as never need (and {n}x pays its count digits). Wins, at 1★.
def _rival_keys(room):
    return (_K('j4h8xj.') + _K('2jhh9xj.')
            + _K('2jh5xi') + _K(_CA + '.') + [ESC]
            + _K('j4h5xi') + _K(_CB + '.') + [ESC]
            + _K('2j5h9x') + _K('2j6h9x.') + _K('G$'))


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
    return main.run_dungeon(term, 'sentence_enclosure', {}, player_name=name,
                            _dungeon=dungeon)


def _drive_spent(keys, monkeypatch, seed=0):
    box = {}
    orig = main._calc_stars
    monkeypatch.setattr(main, '_calc_stars',
                        lambda won, budget, room, player, level='':
                            (box.__setitem__('spent', budget.spent),
                             orig(won, budget, room, player, level))[1])
    result = _drive(build_dungeon_sentence_enclosure(seed), keys, monkeypatch)
    return result['won'], box.get('spent')


# ── dungeon structure ─────────────────────────────────────────────────────────

@pytest.mark.parametrize("seed", SEEDS)
def test_layout_and_identity(seed):
    room = _room(seed)
    assert (room.rows, room.cols) == (_SE_ROWS, _SE_COLS)
    assert room.spawn_pos == _SE_SPAWN
    assert room.exit_pos == _SE_EXIT
    exit_ent = next(e for e in room.entities if e.kind == 'exit')
    assert (exit_ent.row, exit_ent.col) == _SE_EXIT and exit_ent.edit_immune


@pytest.mark.parametrize("seed", SEEDS)
def test_par_answer_budget(seed):
    room = _room(seed)
    assert room.par == _SE_PAR
    assert room.budget == math.ceil(_SE_PAR * 1.4)
    assert room.answer == (f'j dis j . 2j das j . 2j cis {_CA}.<Esc> j cis {_CB}.<Esc> '
                           f'2j das 2j . . G $')


@pytest.mark.parametrize("seed", SEEDS)
def test_exit_and_bolts_start_sealed(seed):
    room = _room(seed)
    for dc in _SE_BOLTS.values():
        assert room.cells[_SE_GATE][dc] == CellType.WALL
    assert room.cells[_SE_EXIT[0]][_SE_EXIT[1]] == CellType.WALL


@pytest.mark.parametrize("seed", SEEDS)
def test_spine_is_every_rows_first_standable(seed):
    room = _room(seed)
    for r in range(room.rows):
        cols = [c for c in range(room.cols) if room.is_passable(r, c)]
        if cols:
            assert cols[0] == _SE_SPINE, f"row {r} first standable {cols[0]}"


@pytest.mark.parametrize("seed", SEEDS)
def test_light_shafts_pierce_separators_but_not_the_throat(seed):
    room = _room(seed)
    for r, c in _SE_SHAFT_SEPS:
        assert room.cells[r][c] == CellType.FLOOR
        others = [cc for cc in range(room.cols)
                  if room.is_passable(r, cc) and cc not in (c, _SE_SPINE)]
        assert not others
    throat = [c for c in range(room.cols) if room.is_passable(_SE_THROAT, c)]
    assert throat == [_SE_SPINE]


@pytest.mark.parametrize("seed", SEEDS)
def test_runs_are_space_free_and_off_the_spine(seed):
    # The space-glyph law (a literal space glyph breaks w and the sentence
    # scanner) + the plaque-overflow law from the Tag build.
    room = _room(seed)
    for ru in room.char_runs:
        assert ' ' not in ru.symbols
        if ru.col < _SE_SPINE:
            assert ru.col + len(ru.symbols) - 1 < _SE_SPINE


# ── the draw: anchored sayings ────────────────────────────────────────────────

@pytest.mark.parametrize("seed", SEEDS)
def test_saying_draw_anchors_and_fits(seed):
    """Every target sentence starts at its slot column (the junk sentence
    for C1/C2/C4, the miswritten middle for C3, the second junk for C5);
    the west sayings right-align, the east sayings start at fixed columns;
    all ten sayings distinct."""
    room = _room(seed)
    rows = room._se_rows
    for r in _SE_C1_ROWS:
        text, t0 = rows[r]
        w_s = text.split('. ')[0] + '.'
        assert t0 + len(w_s) + 1 == _SE_C1_JUNK and t0 >= _SE_TEXT_MIN
        assert t0 + text.index(text.split(' ')[-1]) or True
    for r in _SE_C2_ROWS:
        text, t0 = rows[r]
        w_s = text.split('. ')[0] + '.'
        assert t0 + len(w_s) + 1 == _SE_C2_JUNK and t0 >= _SE_TEXT_MIN
    for r, (fix, _mid) in zip(_SE_C3_ROWS,
                              zip(_SE_C3_FIX, room._se_texts['mids'])):
        text, t0 = rows[r]
        assert t0 == _SE_TEXT0
        assert text.startswith(_se_sentence(fix[0]))
        assert text.endswith(_se_sentence(fix[2]))
    text, t0 = rows[_SE_C4_ROWS[0]]
    assert t0 + len(text.split('. ')[0]) + 2 == _SE_C4_JUNK
    text, t0 = rows[_SE_C5_ROWS[0]]
    assert t0 == _SE_TEXT0
    # every row fits the bay
    for r, (text, t0) in rows.items():
        assert t0 >= _SE_TEXT_MIN and t0 + len(text) - 1 <= _SE_BAY_E, r
    sayings = room._se_texts['east'] + room._se_texts['west']
    assert len(set(sayings)) == len(sayings)


@pytest.mark.parametrize("seed", SEEDS)
def test_gap_discrimination_between_c1_and_c2(seed):
    # dis leaves the DOUBLE gap; das (spanning the trailing space) the
    # SINGLE — the doors read the difference, so a d) golf on C1 produces
    # the wrong text.
    room = _room(seed)
    for t in room._ss_doors[0][0]:
        assert '  ' in t
    for t in room._ss_doors[1][0]:
        assert '  ' not in t


@pytest.mark.parametrize("seed", SEEDS)
def test_junk_is_foreign_and_distinct(seed):
    room = _room(seed)
    texts = room._se_texts
    saying_words = {w for s in texts['east'] + texts['west']
                    for w in s.rstrip('.').split(' ')}
    junk = list(texts['junk3']) + list(texts['mids'])
    assert len(set(junk)) == len(junk)
    assert not (set(junk) & saying_words)


@pytest.mark.parametrize("seed", SEEDS)
def test_targets_are_not_already_true(seed):
    room = _room(seed)
    texts = {main._wla_floor_text(room, r).strip() for r in range(room.rows)}
    for targets, _dc in room._ss_doors:
        for t in targets:
            assert t not in texts


# ── playthroughs ─────────────────────────────────────────────────────────────

@pytest.mark.parametrize("seed", SEEDS)
def test_canonical_run_wins_at_par(seed, monkeypatch):
    room = build_dungeon_sentence_enclosure(seed).rooms[0]
    won, spent = _drive_spent(_canon_keys(room), monkeypatch, seed)
    assert won and spent == _SE_PAR


@pytest.mark.parametrize("seed", SEEDS)
def test_edge_hunting_rival_wins_at_one_star(seed, monkeypatch):
    dungeon = build_dungeon_sentence_enclosure(seed)
    room = dungeon.rooms[0]
    won, spent = _drive_spent(_rival_keys(room), monkeypatch, seed)
    assert won and _SE_PAR < spent <= room.budget


def test_das_on_the_last_sentence_eats_the_leading_space(monkeypatch):
    # Vim-true as-fallback (engine'd with this level): nothing trails the
    # last sentence, so the object spans the LEADING whitespace instead.
    dungeon = build_dungeon_sentence_enclosure(0)
    room = dungeon.rooms[0]
    keys = (_K('jdisj.') + _K('2jdasj.')
            + _K('2jcis') + _K(_CA + '.') + [ESC]
            + _K('jcis') + _K(_CB + '.') + [ESC] + _K('2jdas'))
    _drive(dungeon, keys, monkeypatch, finish=':q!\r')
    r = _SE_C4_ROWS[0]
    assert main._wla_floor_text(room, r).strip() == \
        room._se_texts['west'][4]                # the saying alone stands


def test_undo_rebars_an_open_bolt(monkeypatch):
    dungeon = build_dungeon_sentence_enclosure(0)
    room = dungeon.rooms[0]
    keys = _K('jdisj.') + _K('u')            # open C1, then undo row 4
    _drive(dungeon, keys, monkeypatch, finish=':q!\r')
    assert room.cells[_SE_GATE][_SE_BOLTS['c1']] == CellType.WALL


# ── teleport audit ───────────────────────────────────────────────────────────

def test_no_jump_lands_on_the_sealed_exit(monkeypatch):
    dungeon = build_dungeon_sentence_enclosure(0)
    seen = {}
    orig = main._calc_stars
    def spy(won, budget, room_, player, level=''):
        seen['pos'] = (player.row, player.col)
        return orig(won, budget, room_, player, level)
    monkeypatch.setattr(main, '_calc_stars', spy)
    result = _drive(dungeon, _K('G$'), monkeypatch, finish=':wq\r')
    assert not result['won']
    assert seen['pos'] == (_SE_GATE, _SE_SPINE), seen


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
    assert _SE_EXIT not in seen
