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

"""The Quote Enclosure (i" a" i' a'): strike from the spine — the quote
objects seek forward — plus the a-quote whitespace quirk and the seek's
first-pair limit."""
import math

import pytest
from blessed.keyboard import Keystroke
from blessed import Terminal

import vimny.game as main
from vimny.engine.world import CellType
from vimny.generation.dungeon_gen import (
    build_dungeon_quote_enclosure,
    _QE_ROWS, _QE_COLS, _QE_SPINE, _QE_SHAFT_SEPS, _QE_THROAT,
    _QE_GATE, _QE_BOLTS, _QE_EXIT, _QE_PAR, _QE_ANCHOR, _QE_SHAPE,
    _QE_TEXT_MIN, _QE_BAY_E,
    _QE_C1_ROWS, _QE_C2_ROWS, _QE_C3_ROWS, _QE_C4_ROWS, _QE_C5_ROWS,
)
from vimny.content import proverbs as pv
from tests import SEEDS, cached_room, door_targets

ESC = Keystroke('\x1b', name='KEY_ESCAPE')


def _room(seed=0):
    return cached_room('build_dungeon_quote_enclosure', seed)


def _K(s):
    return [Keystroke(ch) for ch in s]


def _cures(room):
    return [m[2] for m in room._qe_texts['misquotes']]


# The canonical tape (== room.answer with Esc placed): every strike is
# thrown from wherever the chained landing sits — the quote objects seek
# forward, so the tape never walks into a setting except C5's aimed 2f".
def _canon_keys(room):
    ca, cb = _cures(room)
    return (_K('jdi"j.') + _K('2jci"') + _K(ca) + [ESC]
            + _K('jci"') + _K(cb) + [ESC]
            + _K("2jdi'j.") + _K('2jda"jda\'')
            + _K('2jwdi"') + _K('G$'))


# The leanest old-only rival: every row pays its walk-in (f" / h / l) before
# a count-x or ct" even starts, and the C4 tear-outs count their own cells.
# Wins, at 1★ (53 > par 47).
def _piecewise_rival_keys(room):
    ca, cb = _cures(room)
    return (_K('jf"l3xj4x') + _K('2jct"') + _K(ca) + [ESC]
            + _K('jhhct"') + _K(cb) + [ESC]
            + _K('2jhh4xj3x') + _K('2jh8xj7x')
            + _K('2j2f"l3x') + _K('G$'))


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
    return main.run_dungeon(term, 'quote_enclosure', {}, player_name=name,
                            _dungeon=dungeon)


def _drive_spent(keys, monkeypatch, seed=0):
    box = {}
    orig = main._calc_stars
    monkeypatch.setattr(main, '_calc_stars',
                        lambda won, budget, room, player, level='':
                            (box.__setitem__('spent', budget.spent),
                             orig(won, budget, room, player, level))[1])
    result = _drive(build_dungeon_quote_enclosure(seed), keys, monkeypatch)
    return result['won'], box.get('spent')


# ── dungeon structure ─────────────────────────────────────────────────────────

@pytest.mark.parametrize("seed", SEEDS)
def test_layout_and_identity(seed):
    room = _room(seed)
    assert (room.rows, room.cols) == (_QE_ROWS, _QE_COLS)
    assert room.spawn_pos == (2, _QE_SPINE)
    assert room.exit_pos == _QE_EXIT
    exit_ent = next(e for e in room.entities if e.kind == 'exit')
    assert (exit_ent.row, exit_ent.col) == _QE_EXIT and exit_ent.edit_immune


@pytest.mark.parametrize("seed", SEEDS)
def test_par_answer_budget(seed):
    room = _room(seed)
    assert room.par == _QE_PAR
    assert room.budget == math.ceil(_QE_PAR * 1.4)
    ca, cb = _cures(room)
    assert room.answer == (f'j di" j . 2j ci" {ca}<Esc> j ci" {cb}<Esc> '
                           f"2j di' j . 2j da\" j da' "
                           f'2j w di" G $')


@pytest.mark.parametrize("seed", SEEDS)
def test_exit_and_bolts_start_sealed(seed):
    room = _room(seed)
    for dc in _QE_BOLTS.values():
        assert room.cells[_QE_GATE][dc] == CellType.WALL
    assert room.cells[_QE_EXIT[0]][_QE_EXIT[1]] == CellType.WALL


@pytest.mark.parametrize("seed", SEEDS)
def test_spine_is_every_rows_first_standable(seed):
    room = _room(seed)
    for r in range(room.rows):
        cols = [c for c in range(room.cols) if room.is_passable(r, c)]
        if cols:
            assert cols[0] == _QE_SPINE, f"row {r} first standable {cols[0]}"


@pytest.mark.parametrize("seed", SEEDS)
def test_light_shafts_pierce_separators_but_not_the_throat(seed):
    room = _room(seed)
    for r, c in _QE_SHAFT_SEPS:
        assert room.cells[r][c] == CellType.FLOOR
        others = [cc for cc in range(room.cols)
                  if room.is_passable(r, cc) and cc not in (c, _QE_SPINE)]
        assert not others
    throat = [c for c in range(room.cols) if room.is_passable(_QE_THROAT, c)]
    assert throat == [_QE_SPINE]


@pytest.mark.parametrize("seed", SEEDS)
def test_no_chest(seed):
    room = _room(seed)
    assert not [e for e in room.entities
                if e.kind in ('chest_random', 'chest_key', 'chest_scroll')]


# ── the draw: anchored proverbs ───────────────────────────────────────────────

@pytest.mark.parametrize("seed", SEEDS)
def test_proverb_draw_anchors_and_fits(seed):
    """The opening quote sits at _QE_ANCHOR on every row; junk lengths fixed
    per slot; sayings distinct; junk foreign to its own saying; misquote
    cures len 3 for the pinned typed cost."""
    room = _room(seed)
    texts = room._qe_texts
    shape_by_row = {r: (jl, q) for r, jl, q in _QE_SHAPE}
    junks = []
    for (r, words, k, junk, q) in texts['intruders']:
        jl, sq = shape_by_row[r]
        assert (len(junk), q) == (jl, sq)
        t0 = _QE_ANCHOR - (pv.prefix_len(words, k) + 1)
        assert t0 >= _QE_TEXT_MIN
        fitlen = jl + 5 if r in _QE_C5_ROWS else jl + 2
        assert _QE_ANCHOR + fitlen + len(' '.join(words[k:])) <= _QE_BAY_E
        assert junk not in words
        junks.append(junk)
        # the laid opening quote really is at the anchor
        ru = next(u for u in room.char_runs
                  if u.row == r and u.col == _QE_ANCHOR)
        assert ru.symbols[0] == q
    assert len(set(junks)) == len(junks)
    for r, (words, idx, cure) in zip(_QE_C2_ROWS, texts['misquotes']):
        assert len(cure) == 3 and len(words[idx]) >= 2
        ru = next(u for u in room.char_runs
                  if u.row == r and u.col == _QE_ANCHOR)
        assert ''.join(ru.symbols) == f'"{words[idx]}"'
    sayings = [w for _r, w, *_ in texts['intruders']]
    assert len({' '.join(w) for w in sayings}) == len(sayings)


@pytest.mark.parametrize("seed", SEEDS)
def test_targets_are_not_already_true(seed):
    room = _room(seed)
    texts = {main._wla_floor_text(room, r).strip() for r in range(room.rows)}
    for targets in door_targets(room):
        for t in targets:
            assert t not in texts


@pytest.mark.parametrize("seed", SEEDS)
def test_c4_targets_are_the_single_gap(seed):
    # THE WHITESPACE QUIRK: a-quote spans the trailing space, so the tear-out
    # heals to a SINGLE gap — the C4 doors read the PRISTINE saying, no scar
    # anywhere (where da( left the double gap).
    room = _room(seed)
    for t in door_targets(room)[3]:
        assert '  ' not in t


# ── playthroughs ─────────────────────────────────────────────────────────────

@pytest.mark.parametrize("seed", SEEDS)
def test_canonical_run_wins_at_par(seed, monkeypatch):
    room = build_dungeon_quote_enclosure(seed).rooms[0]
    won, spent = _drive_spent(_canon_keys(room), monkeypatch, seed)
    assert won and spent == _QE_PAR


@pytest.mark.parametrize("seed", SEEDS)
def test_piecewise_rival_wins_at_one_star(seed, monkeypatch):
    dungeon = build_dungeon_quote_enclosure(seed)
    room = dungeon.rooms[0]
    won, spent = _drive_spent(_piecewise_rival_keys(room), monkeypatch, seed)
    assert won and _QE_PAR < spent <= room.budget


def test_blind_dot_off_c2_is_a_costed_noop(monkeypatch):
    # After the ci" cures, '.' replays ci"+text; the single-quote rows hold
    # no double quote, so the replay changes nothing — the mark switch must
    # be deliberate.
    dungeon = build_dungeon_quote_enclosure(0)
    room = dungeon.rooms[0]
    ca, cb = _cures(room)
    keys = (_K('jdi"j.') + _K('2jci"') + _K(ca) + [ESC]
            + _K('jci"') + _K(cb) + [ESC] + _K('2j.'))
    _drive(dungeon, keys, monkeypatch, finish=':q!\r')
    texts = {main._wla_floor_text(room, r).strip() for r in range(room.rows)}
    assert not any(t in texts for t in door_targets(room)[2])


def test_blind_seek_on_c5_hits_the_empty_first_pair(monkeypatch):
    # THE SEEK'S LIMIT: from the spine, di" resolves the FIRST pair — which
    # is already empty — so the lazy strike is a no-op and the second pair
    # keeps its rot.
    dungeon = build_dungeon_quote_enclosure(0)
    room = dungeon.rooms[0]
    keys = _K('j') * 13 + _K('di"')          # walk the spine to row 15; strike
    _drive(dungeon, keys, monkeypatch, finish=':q!\r')
    assert main._wla_floor_text(room, 15).strip() != door_targets(room)[4][0]
    junk15 = next(n[3] for n in room._qe_texts['intruders'] if n[0] == 15)
    assert junk15 in main._wla_floor_text(room, 15)


def test_undo_rebars_an_open_bolt(monkeypatch):
    dungeon = build_dungeon_quote_enclosure(0)
    room = dungeon.rooms[0]
    keys = _K('jdi"j.') + _K('u')            # open C1, then undo row 4
    _drive(dungeon, keys, monkeypatch, finish=':q!\r')
    assert room.cells[_QE_GATE][_QE_BOLTS['c1']] == CellType.WALL


# ── teleport audit ───────────────────────────────────────────────────────────

def test_no_jump_lands_on_the_sealed_exit(monkeypatch):
    dungeon = build_dungeon_quote_enclosure(0)
    seen = {}
    orig = main._calc_stars
    def spy(won, budget, room_, player, level=''):
        seen['pos'] = (player.row, player.col)
        return orig(won, budget, room_, player, level)
    monkeypatch.setattr(main, '_calc_stars', spy)
    result = _drive(dungeon, _K('G$'), monkeypatch, finish=':wq\r')
    assert not result['won']
    assert seen['pos'] == (_QE_GATE, _QE_SPINE), seen


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
    assert _QE_EXIT not in seen
