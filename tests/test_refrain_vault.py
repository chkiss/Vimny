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

"""The Refrain Vault (42) — repeats + remote yank, sung to London Bridge.

The falling verses were written "falling up"; the build and key verses keep
"up" rightly, so :%s/up/down/g wrecks them and no contiguous range spans
both falling verses while sparing the middle. Canonical: :s/up/down/g on
the double line, ranged :&& over each falling verse while /g is fresh, then
:1j + :1y + p to lay the torn "my fair lady." where the reprise goes
without one. Par 38."""
import pytest
from blessed.keyboard import Keystroke
from blessed import Terminal

import main
from engine.world import CellType
from engine import substitute as S
from generation.dungeon_gen import (
    build_dungeon_refrain_vault,
    _RV_ROWS, _RV_COLS, _RV_BAND, _RV_WTR, _RV_SONG, _RV_CORRUPT,
    _RV_SEAL_ROW, _RV_SEAL_COL, _RV_EXIT_COL, _RV_TRUE, _RV_PAR, _RV_BUDGET,
)
from tests import SEEDS, cached_room

ENTER = Keystroke('\r', code=343, name='KEY_ENTER')


def _room(seed=0):
    return cached_room('build_dungeon_refrain_vault', seed)


def _fresh(seed=0):
    return build_dungeon_refrain_vault(seed)


def _K(s):
    out = []
    for ch in s:
        if ch == '⏎':
            out.append(ENTER)
        elif ch == '␣':
            out.append(Keystroke(' '))
        else:
            out.append(Keystroke(ch))
    return out


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
    monkeypatch.setattr(main, '_show_catalog_scroll', lambda *a, **k: None)
    monkeypatch.setattr(main, '_show_scroll_by_id', lambda *a, **k: None)
    monkeypatch.setattr(Terminal, 'height', property(lambda self: 45))
    term = Terminal()
    it = iter(keys)
    monkeypatch.setattr(term, 'inkey', lambda *a, **k: next(it, Keystroke('')))
    return main.run_dungeon(term, 'refrain_vault', {}, player_name=player_name,
                            _dungeon=dungeon)


# ── structure ─────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("seed", SEEDS)
def test_the_song_stands_written_wrong(seed):
    r = _room(seed)
    assert (r.rows, r.cols) == (_RV_ROWS, _RV_COLS)
    assert r.cells[_RV_SEAL_ROW][_RV_SEAL_COL] == CellType.WALL
    assert r.par == _RV_PAR and r.budget == _RV_BUDGET
    for i, true_line in enumerate(_RV_TRUE[:-1]):
        row = _RV_SONG[0] + i
        writ = S.line_text(r, row)[0].strip()
        if row in _RV_CORRUPT:
            assert writ == true_line.replace('down', 'up')
            kinds = {ru.kind for ru in r._char_runs_by_row[row]}
            assert kinds == {'ember'}
        else:
            assert writ == true_line
            assert {ru.kind for ru in r._char_runs_by_row[row]} == {'verdant'}
    # the torn final line waits in the chasm; it appears NOWHERE in the room
    assert S.line_text(r, 1)[0].strip() == 'my fair'
    assert S.line_text(r, 2)[0].strip() == 'lady.'
    # "up" is TRUE in the build and key verses (the :%s trap)
    for row in (8, 10, 12, 13, 14):
        assert 'up' in S.line_text(r, row)[0]


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


# ── rivals: the shortcut roads all lose or wreck the song ─────────────────────

def test_blanket_substitute_wrecks_the_build_verse(monkeypatch):
    # :%s/up/down/g → "Build it down with wood and clay" — the seal stays shut.
    d = _fresh(0)
    keys = _K(':%s/up/down/g⏎:1j⏎:1y⏎12jpj$')
    result = _drive(d, keys, monkeypatch)
    assert not result['won']
    r = d.rooms[0]
    assert any('Build it down' in S.line_text(r, row)[0]
               for row in range(r.rows))


def test_global_mend_wrecks_the_key_verse(monkeypatch):
    d = _fresh(0)
    keys = _K(':g/up/s//down/g⏎:1j⏎:1y⏎12jpj$')
    result = _drive(d, keys, monkeypatch)
    assert not result['won']


def test_wide_ranged_repeat_wrecks_the_middle(monkeypatch):
    # :4,18&& sweeps the build and key verses too — no single range serves.
    d = _fresh(0)
    keys = _K(':s/up/down/g⏎:4,18&&⏎:1j⏎:1y⏎12jpj$')
    result = _drive(d, keys, monkeypatch)
    assert not result['won']


def test_ranged_substitute_longhand_wins_one_star(monkeypatch):
    # Retyping the full :s per falling verse: lawful, 43 > par 38, inside 60.
    # (The second ranged :s already parks the scribe at the reprise's end.)
    d = _fresh(0)
    keys = _K(':4,6s/up/down/g⏎:16,18s/up/down/g⏎:1j⏎:1y⏎pj$')
    result = _drive(d, keys, monkeypatch)
    assert result['won'] and result['stars'] == 1


def test_copied_chasm_slab_cannot_serve(monkeypatch):
    # :t ferries the joined line into the hall still MISTED — text off the
    # floor never completes the song; only :1y + p lays it down.
    d = _fresh(0)
    keys = _K(':s/up/down/g⏎:16,18&&⏎:4,6&&⏎:1j⏎:1t17⏎13j$')
    result = _drive(d, keys, monkeypatch)
    assert not result['won']


# ── curriculum ────────────────────────────────────────────────────────────────

def test_curriculum_entry():
    from content.levels import _BY_SLUG, known_commands
    lv = _BY_SLUG['refrain_vault']
    assert lv['display'] == '42'
    assert lv['teaches'] == []                     # the ex_range kit + & family
    known = set(known_commands('refrain_vault'))
    assert 'ex_range' in known and 'subst' in known
