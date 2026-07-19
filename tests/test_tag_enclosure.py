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

"""The Tag Enclosure (it at): name the element and the innermost answers —
tags don't seek, so the walk-in is paid once and the dot-chains ride the
aligned geometry."""
import math

import pytest
from blessed.keyboard import Keystroke
from blessed import Terminal

import main
from engine.world import CellType
from generation.dungeon_gen import (
    build_dungeon_tag_enclosure,
    _TE_ROWS, _TE_COLS, _TE_SPINE, _TE_SHAFT_SEPS, _TE_THROAT,
    _TE_GATE, _TE_BOLTS, _TE_EXIT, _TE_PAR, _TE_ANCHOR, _TE_NEST_ANCHOR,
    _TE_SHAPE, _TE_TEXT_MIN, _TE_BAY_E,
    _TE_C1_ROWS, _TE_C2_ROWS, _TE_C3_ROWS, _TE_C4_ROWS, _TE_C5_ROWS,
)
from content import proverbs as pv
from tests import SEEDS, cached_room

ESC = Keystroke('\x1b', name='KEY_ESCAPE')


def _room(seed=0):
    return cached_room('build_dungeon_tag_enclosure', seed)


def _K(s):
    return [Keystroke(ch) for ch in s]


def _cures(room):
    return [m[2] for m in room._te_texts['misquotes']]


# The canonical tape (== room.answer with Esc placed): one f> walk-in, then
# the dot-chains ride the aligned columns; the nest discriminates dit/dat
# from one landing; C5 aims with f< past the empty first element.
def _canon_keys(room):
    ca, cb = _cures(room)
    return (_K('jf>ditj.') + _K('2jcit') + _K(ca) + [ESC]
            + _K('jcit') + _K(cb) + [ESC]
            + _K('2jdatj.') + _K('2jditjdat')
            + _K('2jf<dit') + _K('G$'))


# The leanest old-only rival: every element pays its own F< / f> / l
# positioning before a count-x or d2f> even starts. Wins, at 1★ (> par).
def _piecewise_rival_keys(room):
    ca, cb = _cures(room)
    return (_K('jf>l3xj4x') + _K('2jct<') + _K(ca) + [ESC]
            + _K('jhhct<') + _K(cb) + [ESC]
            + _K('2jF<d2f>jd2f>') + _K('2jf>l3xjF<d2f>')
            + _K('2j2f>l3x') + _K('G$'))


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
    return main.run_dungeon(term, 'tag_enclosure', {}, player_name=name,
                            _dungeon=dungeon)


def _drive_spent(keys, monkeypatch, seed=0):
    box = {}
    orig = main._calc_stars
    monkeypatch.setattr(main, '_calc_stars',
                        lambda won, budget, room, player, level='':
                            (box.__setitem__('spent', budget.spent),
                             orig(won, budget, room, player, level))[1])
    result = _drive(build_dungeon_tag_enclosure(seed), keys, monkeypatch)
    return result['won'], box.get('spent')


# ── dungeon structure ─────────────────────────────────────────────────────────

@pytest.mark.parametrize("seed", SEEDS)
def test_layout_and_identity(seed):
    room = _room(seed)
    assert (room.rows, room.cols) == (_TE_ROWS, _TE_COLS)
    assert room.spawn_pos == (2, _TE_SPINE)
    assert room.exit_pos == _TE_EXIT
    exit_ent = next(e for e in room.entities if e.kind == 'exit')
    assert (exit_ent.row, exit_ent.col) == _TE_EXIT and exit_ent.edit_immune


@pytest.mark.parametrize("seed", SEEDS)
def test_par_answer_budget(seed):
    room = _room(seed)
    assert room.par == _TE_PAR
    assert room.budget == math.ceil(_TE_PAR * 1.4)
    ca, cb = _cures(room)
    assert room.answer == (f'j f> dit j . 2j cit {ca} j cit {cb} '
                           f'2j dat j . 2j dit j dat 2j f< dit G $')


@pytest.mark.parametrize("seed", SEEDS)
def test_exit_and_bolts_start_sealed(seed):
    room = _room(seed)
    for dc in _TE_BOLTS.values():
        assert room.cells[_TE_GATE][dc] == CellType.WALL
    assert room.cells[_TE_EXIT[0]][_TE_EXIT[1]] == CellType.WALL


@pytest.mark.parametrize("seed", SEEDS)
def test_spine_is_every_rows_first_standable(seed):
    room = _room(seed)
    for r in range(room.rows):
        cols = [c for c in range(room.cols) if room.is_passable(r, c)]
        if cols:
            assert cols[0] == _TE_SPINE, f"row {r} first standable {cols[0]}"


@pytest.mark.parametrize("seed", SEEDS)
def test_light_shafts_pierce_separators_but_not_the_throat(seed):
    room = _room(seed)
    for r, c in _TE_SHAFT_SEPS:
        assert room.cells[r][c] == CellType.FLOOR
        others = [cc for cc in range(room.cols)
                  if room.is_passable(r, cc) and cc not in (c, _TE_SPINE)]
        assert not others
    throat = [c for c in range(room.cols) if room.is_passable(_TE_THROAT, c)]
    assert throat == [_TE_SPINE]


@pytest.mark.parametrize("seed", SEEDS)
def test_no_chest(seed):
    room = _room(seed)
    assert not [e for e in room.entities
                if e.kind in ('chest', 'chest_key', 'chest_scroll')]


# ── the draw: anchored proverbs ───────────────────────────────────────────────

@pytest.mark.parametrize("seed", SEEDS)
def test_proverb_draw_anchors_and_fits(seed):
    """Standard elements open at _TE_ANCHOR, nest/C5 at _TE_NEST_ANCHOR
    (their inner/second '<' rides the chained landing); junk lengths fixed;
    sayings distinct; junk foreign; misquote cures len 3."""
    room = _room(seed)
    texts = room._te_texts
    shape_by_row = dict(_TE_SHAPE)
    junks = []
    for (r, words, k, junk, tag) in texts['intruders']:
        assert len(junk) == shape_by_row[r]
        anchor = (_TE_NEST_ANCHOR if r in _TE_C4_ROWS + _TE_C5_ROWS
                  else _TE_ANCHOR)
        t0 = anchor - (pv.prefix_len(words, k) + 1)
        assert t0 >= _TE_TEXT_MIN
        ru = next(u for u in room.char_runs if u.row == r and u.col == anchor)
        assert ru.symbols[0] == '<'
        assert ru.col + len(ru.symbols) - 1 <= _TE_BAY_E
        assert junk not in words
        junks.append(junk)
        assert all(len(n) == 3 for n in tag)
    assert len(set(junks)) == len(junks)
    for name, (words, idx, cure) in zip(texts['c2_names'],
                                        texts['misquotes']):
        assert len(cure) == 3 and len(words[idx]) >= 3 and len(name) == 3
    sayings = [w for _r, w, *_ in texts['intruders']]
    assert len({' '.join(w) for w in sayings}) == len(sayings)


@pytest.mark.parametrize("seed", SEEDS)
def test_targets_are_not_already_true(seed):
    room = _room(seed)
    texts = {main._wla_floor_text(room, r).strip() for r in range(room.rows)}
    for targets, _dc in room._ss_doors:
        for t in targets:
            assert t not in texts


@pytest.mark.parametrize("seed", SEEDS)
def test_c3_targets_are_the_double_gap(seed):
    # at spans the TAGS ONLY (no whitespace rule), so the tear-out reads
    # 'w1  w2' with TWO spaces — the da( scar, where da" left the single.
    room = _room(seed)
    for t in room._ss_doors[2][0]:
        assert '  ' in t


# ── playthroughs ─────────────────────────────────────────────────────────────

@pytest.mark.parametrize("seed", SEEDS)
def test_canonical_run_wins_at_par(seed, monkeypatch):
    room = build_dungeon_tag_enclosure(seed).rooms[0]
    won, spent = _drive_spent(_canon_keys(room), monkeypatch, seed)
    assert won and spent == _TE_PAR


@pytest.mark.parametrize("seed", SEEDS)
def test_piecewise_rival_wins_at_one_star(seed, monkeypatch):
    dungeon = build_dungeon_tag_enclosure(seed)
    room = dungeon.rooms[0]
    won, spent = _drive_spent(_piecewise_rival_keys(room), monkeypatch, seed)
    assert won and _TE_PAR < spent <= room.budget


def test_spine_strike_is_nothing_here(monkeypatch):
    # Tags do NOT seek: dit thrown from the spine (outside the element)
    # resolves no pair — the walk-in is the lesson's price.
    dungeon = build_dungeon_tag_enclosure(0)
    room = dungeon.rooms[0]
    _drive(dungeon, _K('jdit'), monkeypatch, finish=':q!\r')
    texts = {main._wla_floor_text(room, r).strip() for r in range(room.rows)}
    assert not any(t in texts for t in room._ss_doors[0][0])


def test_nest_resolves_the_innermost(monkeypatch):
    # From the same landing column: dit empties the inner element on row 12;
    # dat on row 13 tears the whole inner element out, leaving the outer husk.
    dungeon = build_dungeon_tag_enclosure(0)
    room = dungeon.rooms[0]
    ca, cb = _cures(room)
    keys = (_K('jf>ditj.') + _K('2jcit') + _K(ca) + [ESC]
            + _K('jcit') + _K(cb) + [ESC]
            + _K('2jdatj.') + _K('2jditjdat'))
    _drive(dungeon, keys, monkeypatch, finish=':q!\r')
    tgt_a, tgt_b = room._ss_doors[3][0]
    r12, r13 = _TE_C4_ROWS
    assert main._wla_floor_text(room, r12).strip() == tgt_a
    assert main._wla_floor_text(room, r13).strip() == tgt_b


def test_undo_rebars_an_open_bolt(monkeypatch):
    dungeon = build_dungeon_tag_enclosure(0)
    room = dungeon.rooms[0]
    keys = _K('jf>ditj.') + _K('u')          # open C1, then undo row 4
    _drive(dungeon, keys, monkeypatch, finish=':q!\r')
    assert room.cells[_TE_GATE][_TE_BOLTS['c1']] == CellType.WALL


# ── teleport audit ───────────────────────────────────────────────────────────

def test_no_jump_lands_on_the_sealed_exit(monkeypatch):
    dungeon = build_dungeon_tag_enclosure(0)
    seen = {}
    orig = main._calc_stars
    def spy(won, budget, room_, player, level=''):
        seen['pos'] = (player.row, player.col)
        return orig(won, budget, room_, player, level)
    monkeypatch.setattr(main, '_calc_stars', spy)
    result = _drive(dungeon, _K('G$'), monkeypatch, finish=':wq\r')
    assert not result['won']
    assert seen['pos'] == (_TE_GATE, _TE_SPINE), seen


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
    assert _TE_EXIT not in seen
