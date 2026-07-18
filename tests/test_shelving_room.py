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

"""The Shelving Room (41) — the movers: :m :t :> :<.

The Culling Ledger's chasm chassis: a misted shelf no foot can reach, the
true stanza carved in the west wall. Canonical :2m4 + :5t7 + :3< + :6> + $,
par 17. :m/:t are structural row surgery (fog and mist ride along); the
_shelving_tick re-mists any bare shelf floor and re-rights the plaque
column after row inserts drag it."""
from collections import deque

import pytest
from blessed.keyboard import Keystroke
from blessed import Terminal

import main
from engine.world import CellType
from engine import substitute as S
from generation.dungeon_gen import (
    build_dungeon_shelving_room,
    _SHR_ROWS, _SHR_COLS, _SHR_PLQ, _SHR_TX, _SHR_BAND, _SHR_WTR, _SHR_GAL,
    _SHR_SEAL_COL, _SHR_EXIT_COL, _SHR_INDENTS, _SHR_INIT, _SHR_PAR,
    _SHR_BUDGET,
)
from tests import SEEDS, cached_room

ENTER = Keystroke('\r', code=343, name='KEY_ENTER')


def _room(seed=0):
    return cached_room('build_dungeon_shelving_room', seed)


def _fresh(seed=0):
    return build_dungeon_shelving_room(seed)


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
                 '_void_fall_animation', '_drown_animation',
                 '_sc_twinkle_animation'):
        monkeypatch.setattr(main, anim, lambda *a, **k: None)
    monkeypatch.setattr(Terminal, 'height', property(lambda self: 45))
    term = Terminal()
    it = iter(keys)
    monkeypatch.setattr(term, 'inkey', lambda *a, **k: next(it, Keystroke('')))
    return main.run_dungeon(term, 'shelving_room', {}, player_name=player_name,
                            _dungeon=dungeon)


# ── structure ─────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("seed", SEEDS)
def test_dimensions_and_seal(seed):
    r = _room(seed)
    assert (r.rows, r.cols) == (_SHR_ROWS, _SHR_COLS)
    assert r.cells[_SHR_GAL][_SHR_SEAL_COL] == CellType.WALL
    assert r.exit_pos == (_SHR_GAL, _SHR_EXIT_COL)
    assert r.par == _SHR_PAR and r.budget == _SHR_BUDGET


@pytest.mark.parametrize("seed", SEEDS)
def test_shelf_reads_misshelved_and_plaque_reads_true(seed):
    r = _room(seed)
    targets = r._shr_targets
    assert len(targets) == 8
    assert targets[7].strip() == targets[4].strip()      # the closing refrain
    for i, t in enumerate(targets):
        assert len(t) - len(t.lstrip()) == _SHR_INDENTS[i]
    # shelf rows 1..7 carry the misshelved stanza, indent as designed
    lines = [ln.strip() for ln in (t.strip() for t in targets)]
    for row, (ti, ind) in enumerate(_SHR_INIT, start=1):
        t = S.line_text(r, row)[0]
        assert t.rstrip() == (' ' * ind) + lines[ti]
    # the plaque column (wall glyphs west of the band) shows every target
    plq = {}
    for ru in r.char_runs:
        if ru.kind == 'verdant' and ru.col < _SHR_TX:
            plq.setdefault(ru.row, []).append(ru)
    for i in range(8):
        runs = sorted(plq[i + 1], key=lambda ru: ru.col)
        assert runs[0].col == _SHR_PLQ + _SHR_INDENTS[i]
        assert ' '.join(''.join(ru.symbols) for ru in runs) == targets[i].strip()


@pytest.mark.parametrize("seed", SEEDS)
def test_shelf_is_misted_sightlined_and_unwalkable(seed):
    from engine.motion import _vision_flood
    r = _room(seed)
    visible = _vision_flood(r, *r.spawn_pos)
    for row in range(1, 8):
        for c in range(*_SHR_BAND):
            assert (row, c) in r.fog_cells and (row, c) in r.mist_cells
            assert not r.is_passable(row, c)
            assert (row, c) in visible                   # the stone law, earned
    seen = {r.spawn_pos}
    q = deque(seen)
    while q:
        cr, cc = q.popleft()
        for dr, dc in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nxt = (cr + dr, cc + dc)
            if nxt not in seen and r.is_passable(*nxt):
                seen.add(nxt)
                q.append(nxt)
    assert all(row == _SHR_GAL for row, _ in seen)
    assert max(c for _, c in seen) < _SHR_SEAL_COL


# ── the driven canonical ──────────────────────────────────────────────────────

@pytest.mark.parametrize("seed", SEEDS)
def test_canonical_run_wins_at_par(seed, monkeypatch):
    d = _fresh(seed)
    result = _drive(d, _tape_keys(d.rooms[0].answer), monkeypatch)
    assert result['won'] and result['stars'] == 2


def test_par_boundary_is_exact(monkeypatch):
    d = _fresh(0)
    d.rooms[0].par = _SHR_PAR - 1
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


def test_fresh_rows_stay_misted_and_plaques_re_right(monkeypatch):
    # After the full canonical run the buffer has grown a row: no bare shelf
    # floor anywhere (the tick re-mists) and the plaque column still reads
    # the eight targets at rows 1..8.
    d = _fresh(0)
    result = _drive(d, _tape_keys(d.rooms[0].answer), monkeypatch)
    assert result['won']
    r = d.rooms[0]
    gal = S._last_standable_row(r)
    for row in range(1, gal):
        for c in range(r.cols):
            if r.cells[row][c] == CellType.FLOOR:
                assert (row, c) in r.fog_cells
    plq_rows = {ru.row for ru in r.char_runs
                if ru.kind == 'verdant' and ru.col < _SHR_TX}
    assert plq_rows == set(range(1, 9))


# ── rivals ────────────────────────────────────────────────────────────────────

def test_copy_delete_rival_to_the_move_loses_a_star(monkeypatch):
    # :t + :d imitates :m for 9 keys where :m pays 5.
    d = _fresh(0)
    keys = _K(':2t4⏎:2d⏎:5t7⏎:3<⏎:6>⏎$')
    result = _drive(d, keys, monkeypatch)
    assert result['won'] and result['stars'] == 1


def test_substitute_rival_to_the_indents_loses_a_star(monkeypatch):
    # :s/^ anchors imitate :> and :< at several times the cost.
    d = _fresh(0)
    keys = _K(':2m4⏎:5t7⏎:3s/^  //⏎:6s/^/  /⏎$')
    result = _drive(d, keys, monkeypatch)
    assert result['won'] and result['stars'] == 1


def test_scorched_shelf_never_opens_the_seal(monkeypatch):
    d = _fresh(0)
    result = _drive(d, _K(':1,7d⏎$'), monkeypatch)
    assert not result['won']


# ── curriculum ────────────────────────────────────────────────────────────────

def test_curriculum_entry():
    from content.levels import _BY_SLUG, known_commands
    lv = _BY_SLUG['shelving_room']
    assert lv['display'] == '41'
    assert lv['teaches'] == []                     # the ex_range kit, second lesson
    assert 'ex_range' in set(known_commands('shelving_room'))
