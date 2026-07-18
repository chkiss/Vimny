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

"""The Refrain Vault (42) — repeats + remote yank: & :&& :j :y.

A walkable scriptorium: one :s spoken in full, then & / :&& carry it — three
protected lines with the same blight bar every :% / :g / g& shortcut, and
their scattering bars any contiguous ranged :s. Above the water, the split
colophon: :1,2j mends it, :1y + p bring it to the floor (a :t slab arrives
misted and cannot serve). Canonical par 37."""
import pytest
from blessed.keyboard import Keystroke
from blessed import Terminal

import main
from engine.world import CellType
from engine import substitute as S
from generation.dungeon_gen import (
    build_dungeon_refrain_vault,
    _RV_ROWS, _RV_COLS, _RV_BAND, _RV_WTR, _RV_PROTECTED, _RV_MULTI,
    _RV_SINGLE, _RV_FILLER, _RV_SEAL_COL, _RV_EXIT_COL, _RV_PAR, _RV_BUDGET,
)
from tests import SEEDS, cached_room

ENTER = Keystroke('\r', code=343, name='KEY_ENTER')


def _room(seed=0):
    return cached_room('build_dungeon_refrain_vault', seed)


def _fresh(seed=0):
    return build_dungeon_refrain_vault(seed)


def _K(s):
    return [ENTER if ch == '⏎' else Keystroke(ch) for ch in s]


def _tape_keys(answer):
    keys = []
    for tok in answer.split(' '):
        keys += _K(tok)
    return keys


def _drive(dungeon, keys, monkeypatch, finish=':wq\r', player_name='Scribe'):
    keys = list(keys) + _K(finish)
    monkeypatch.setattr(main, 'render_all', lambda *a, **k: None)
    monkeypatch.setattr(main.time, 'sleep', lambda *a, **k: None)
    for anim in ('_fireworks_animation', '_win_animation', '_starfield_victory',
                 '_heart_container_animation', '_unlock_animation',
                 '_void_fall_animation', '_drown_animation'):
        monkeypatch.setattr(main, anim, lambda *a, **k: None)
    monkeypatch.setattr(Terminal, 'height', property(lambda self: 45))
    term = Terminal()
    it = iter(keys)
    monkeypatch.setattr(term, 'inkey', lambda *a, **k: next(it, Keystroke('')))
    return main.run_dungeon(term, 'refrain_vault', {}, player_name=player_name,
                            _dungeon=dungeon)


# ── structure ─────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("seed", SEEDS)
def test_dimensions_words_and_seal(seed):
    r = _room(seed)
    assert (r.rows, r.cols) == (_RV_ROWS, _RV_COLS)
    assert r.cells[_RV_FILLER][_RV_SEAL_COL] == CellType.WALL
    assert r.par == _RV_PAR and r.budget == _RV_BUDGET
    b = r._rv_blight
    for row in _RV_PROTECTED + _RV_MULTI + _RV_SINGLE:
        assert b in S.line_text(r, row)[0]
    for row in _RV_MULTI:
        assert S.line_text(r, row)[0].count(b) == 3
    for row in _RV_SINGLE:
        assert S.line_text(r, row)[0].count(b) == 1
    colo = r._rv_colophon
    assert colo.startswith(S.line_text(r, 1)[0].strip())
    assert colo.endswith(S.line_text(r, 2)[0].strip())
    assert b not in colo


@pytest.mark.parametrize("seed", SEEDS)
def test_chasm_is_misted_sightlined_and_unwalkable(seed):
    from engine.motion import _vision_flood
    r = _room(seed)
    visible = _vision_flood(r, *r.spawn_pos)
    for row in (1, 2):
        assert not any(r.is_passable(row, c) for c in range(r.cols))
        for ru in r._char_runs_by_row.get(row, []):
            for i in range(len(ru.symbols)):
                cell = (row, ru.col + i)
                assert cell in r.fog_cells and cell in r.mist_cells
                assert cell in visible                   # the stone law, earned


# ── the driven canonical ──────────────────────────────────────────────────────

@pytest.mark.parametrize("seed", SEEDS)
def test_canonical_run_wins_at_par(seed, monkeypatch):
    d = _fresh(seed)
    result = _drive(d, _tape_keys(d.rooms[0].answer), monkeypatch)
    assert result['won'] and result['stars'] == 2


def test_par_boundary_is_exact(monkeypatch):
    d = _fresh(0)
    d.rooms[0].par = _RV_PAR - 1
    result = _drive(d, _tape_keys(d.rooms[0].answer), monkeypatch)
    assert result['won'] and result['stars'] == 1


@pytest.mark.parametrize("seed", SEEDS)
def test_admin_karaoke_stays_in_sync(seed, monkeypatch):
    d = _fresh(seed)
    room = d.rooms[0]
    result = _drive(d, _tape_keys(room.answer), monkeypatch, player_name='admin')
    assert result['won']
    assert not room.answer_diverged
    assert room.answer_pos == len(room.answer.replace(' ', ''))


# ── rivals: the shortcut roads all lose or fail ───────────────────────────────

def _spent_probe(monkeypatch, box):
    orig = main._calc_stars
    monkeypatch.setattr(main, '_calc_stars',
                        lambda won, budget, room_, player, level='':
                            (box.__setitem__('spent', budget.spent),
                             orig(won, budget, room_, player, level))[1])


def test_contiguous_ranged_s_mix_loses_a_star(monkeypatch):
    # The best repeat-free mend: two-row ranged :s + two ranged :&& — the
    # scattered wards bar anything wider. 39 > par 37.
    d = _fresh(0)
    r = d.rooms[0]
    b, c = r._rv_blight, r._rv_mended[0].split()[0]
    keys = _K(f':5,6s/{b}/{c}/g⏎:8,9&&⏎:11&&⏎:1,2j⏎:1y⏎p j$')
    result = _drive(d, keys, monkeypatch)
    assert result['won'] and result['stars'] == 1


def test_global_mend_wrecks_a_ward(monkeypatch):
    # :g/{b}/s//{c}/g matches the protected lines too — the seal stays shut.
    d = _fresh(0)
    r = d.rooms[0]
    b, c = r._rv_blight, r._rv_mended[0].split()[0]
    keys = _K(f':g/{b}/s//{c}/g⏎:1,2j⏎:1y⏎p j$')
    result = _drive(d, keys, monkeypatch)
    assert not result['won']


def test_percent_mend_wrecks_a_ward(monkeypatch):
    d = _fresh(0)
    r = d.rooms[0]
    b, c = r._rv_blight, r._rv_mended[0].split()[0]
    result = _drive(d, _K(f':%s/{b}/{c}/g⏎:1,2j⏎:1y⏎p j$'), monkeypatch)
    assert not result['won']


def test_copied_chasm_slab_cannot_serve_the_colophon(monkeypatch):
    # :t ferries the joined colophon into the hall still MISTED — text off the
    # floor never opens the seal (only :1y + p lays it on walkable ground).
    d = _fresh(0)
    box = {}
    _spent_probe(monkeypatch, box)
    keys = _tape_keys(d.rooms[0].answer.replace(':1y⏎ p', ':1t11⏎'))
    result = _drive(d, keys, monkeypatch)
    assert (not result['won']) or box.get('spent', 0) > _RV_PAR


# ── curriculum ────────────────────────────────────────────────────────────────

def test_curriculum_entry():
    from content.levels import _BY_SLUG, known_commands
    lv = _BY_SLUG['refrain_vault']
    assert lv['display'] == '42'
    assert lv['teaches'] == []                     # the ex_range kit + & family
    known = set(known_commands('refrain_vault'))
    assert 'ex_range' in known and 'subst' in known
