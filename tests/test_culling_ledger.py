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

"""The Culling Ledger (40) — the ex-range family's first lesson, v3.

A dark ledger across a chasm, a key chest, and two locked doors. The key
lives in the unnamed register, every register-writing cull clobbers it, and
there is only one key — the black hole (:d _) is the lesson. The unseen-line
law bars culling the still-dark ledger, so door one must open first (which
parts the mist); when the ledger reads true, the corridor brazier catches
the verdant lines' fire and its light unveils the exit pocket. Canonical
`2l x $ p :2d _ :5,9d _ :6,13v/{s4}/d _ $ p 4l`, par 36."""
from collections import deque

import pytest
from blessed.keyboard import Keystroke
from blessed import Terminal

import main
from engine.world import CellType
from engine import substitute as S
from generation.dungeon_gen import (
    build_dungeon_culling_ledger,
    _CL_ROWS, _CL_COLS, _CL_CATCH, _CL_TX, _CL_SEP, _CL_WALL, _CL_GAP,
    _CL_COR, _CL_KEYCH, _CL_DOOR1, _CL_DOOR2, _CL_BRZ_COL, _CL_EXIT,
    _CL_KEEP_ROWS, _CL_BLIGHT_I, _CL_BLIGHT_II, _CL_JUNK_III,
    _CL_SACRED_III, _CL_GAPS, _CL_PAR, _CL_BUDGET,
)
from content.levels import LEVELS, known_commands
from tests import SEEDS, cached_room

ENTER = Keystroke('\r', code=343, name='KEY_ENTER')


def _room(seed=0):
    return cached_room('build_dungeon_culling_ledger', seed)


def _fresh(seed=0):
    return build_dungeon_culling_ledger(seed)


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
    # chest pickups pop scroll overlays that would eat tape keys
    monkeypatch.setattr(main, '_show_catalog_scroll', lambda *a, **k: None)
    monkeypatch.setattr(main, '_show_scroll_by_id', lambda *a, **k: None)
    monkeypatch.setattr(Terminal, 'height', property(lambda self: 45))
    term = Terminal()
    it = iter(keys)
    monkeypatch.setattr(term, 'inkey', lambda *a, **k: next(it, Keystroke('')))
    return main.run_dungeon(term, 'culling_ledger', {}, player_name=player_name,
                            _dungeon=dungeon)


_CONTENT_ROWS = (list(_CL_KEEP_ROWS) + [_CL_BLIGHT_I] + list(_CL_BLIGHT_II)
                 + list(_CL_JUNK_III) + list(_CL_SACRED_III))


def _strip(t):
    for junk in ('○', '🜂', '…'):
        t = t.replace(junk, '')
    return t.strip()


# ── structure ─────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("seed", SEEDS)
def test_dimensions_doors_and_braziers(seed):
    r = _room(seed)
    assert (r.rows, r.cols) == (_CL_ROWS, _CL_COLS)
    kinds = {(e.row, e.col): e.kind for e in r.entities}
    assert kinds[_CL_KEYCH] == 'chest_key'
    assert kinds[_CL_DOOR1] == 'locked_door' and kinds[_CL_DOOR2] == 'locked_door'
    assert r.exit_pos == _CL_EXIT
    assert r.par == _CL_PAR and r.budget == _CL_BUDGET
    # the stone course is solid but for the one gap, east of door one
    for c in range(1, r.cols - 1):
        want = CellType.FLOOR if (_CL_WALL, c) == _CL_GAP else CellType.WALL
        assert r.cells[_CL_WALL][c] == want
    assert _CL_GAP[1] > _CL_DOOR1[1]
    # lit braziers on every verdant line, a cold one on the corridor
    for row in list(_CL_KEEP_ROWS) + list(_CL_SACRED_III):
        ru = r.char_run_at(row, _CL_BRZ_COL)
        assert ru is not None and ru.kind == 'flame'
    ped = r.char_run_at(_CL_COR, _CL_BRZ_COL)
    assert ped is not None and ped.kind == 'pedestal'


@pytest.mark.parametrize("seed", SEEDS)
def test_ledger_starts_dark_and_keeps_are_ordered(seed):
    r = _room(seed)
    keeps = r._ledger_keeps
    assert len(keeps) == 6
    rows_true = list(_CL_KEEP_ROWS) + list(_CL_SACRED_III)
    for row, k in zip(rows_true, keeps):
        assert _strip(S.line_text(r, row)[0]) == k
    for row in _CONTENT_ROWS:
        for ru in r._char_runs_by_row.get(row, []):
            for i in range(len(ru.symbols)):
                cell = (row, ru.col + i)
                assert cell in r.fog_cells
                assert cell not in r.mist_cells    # DARK until door one opens
                assert not r.is_passable(*cell)
    s4 = r.answer.split('/')[1]
    b5 = r._ledger_blight
    for row in _CL_SACRED_III:
        assert _strip(S.line_text(r, row)[0]).startswith(s4)
    for row in _CL_BLIGHT_II:
        assert b5 in S.line_text(r, row)[0]
    for row in _CL_JUNK_III:
        assert s4 not in S.line_text(r, row)[0]


@pytest.mark.parametrize("seed", SEEDS)
def test_no_jump_can_land_on_a_ledger_row(seed):
    from engine.motion import apply_motion
    from engine.player import Player
    r = _room(seed)
    for row in range(0, _CL_SEP + 1):
        assert not any(r.is_passable(row, c) for c in range(r.cols))
    p = Player(name='t')
    p.row, p.col = r.spawn_pos
    for count in (2, 5, 9, 13):
        apply_motion(p, 'G', count, r, None, count_given=True)
        assert p.row > _CL_SEP          # at worst the gap perch — never the ledger
        p.row, p.col = r.spawn_pos


@pytest.mark.parametrize("seed", SEEDS)
def test_walk_stops_at_door_one(seed):
    r = _room(seed)
    seen = {r.spawn_pos}
    q = deque(seen)
    while q:
        cr, cc = q.popleft()
        for dr, dc in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nxt = (cr + dr, cc + dc)
            if nxt not in seen and r.is_passable(*nxt):
                seen.add(nxt)
                q.append(nxt)
    assert max(c for _, c in seen) < _CL_DOOR1[1]
    assert all(row == _CL_COR for row, _ in seen)


# ── the unseen-line law ───────────────────────────────────────────────────────

def test_blind_cull_is_refused():
    # The ledger is dark: ranged deletes are refused until the mist parts.
    d = _fresh(0)
    r = d.rooms[0]
    from engine.player import Player
    p = Player(name='t')
    p.row, p.col = r.spawn_pos
    handled, msg, _ns, nl = S.run_ex('2d', r, p)
    assert handled and nl == 0 and 'dark' in msg
    assert r.rows == _CL_ROWS


# ── the driven canonical ──────────────────────────────────────────────────────

@pytest.mark.parametrize("seed", SEEDS)
def test_canonical_run_wins_at_par(seed, monkeypatch):
    d = _fresh(seed)
    result = _drive(d, _tape_keys(d.rooms[0].answer), monkeypatch)
    assert result['won'] and result['stars'] == 2


def test_par_boundary_is_exact(monkeypatch):
    d = _fresh(0)
    d.rooms[0].par = _CL_PAR - 1
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


def test_finale_lights_the_brazier(monkeypatch):
    d = _fresh(0)
    result = _drive(d, _tape_keys(d.rooms[0].answer), monkeypatch)
    assert result['won']
    r = d.rooms[0]
    cor = S._last_standable_row(r)
    ru = r.char_run_at(cor, _CL_BRZ_COL)
    assert ru is not None and ru.kind == 'flame'   # the cold brazier caught fire


# ── the register lesson: skip the black hole and the key is ash ───────────────

def test_clobbering_delete_loses_the_key(monkeypatch):
    # :2d without _ overwrites the held key — door two never opens.
    d = _fresh(0)
    a = d.rooms[0].answer.replace(':2d␣_⏎', ':2d⏎')
    result = _drive(d, _tape_keys(a), monkeypatch)
    assert not result['won']


def test_stashing_the_key_loses_it(monkeypatch):
    # KEYS ARE SLIPPERY (global paste law): pasting the key anywhere but onto
    # a locked door loses it outright — no floor copy lands, the hand
    # empties — so the stash never shields a plain cull.
    d = _fresh(0)
    r = d.rooms[0]
    a = r.answer
    a = a.replace('$ p :2d␣_⏎', '$ p p :2d⏎')     # try to drop a copy
    a = a.replace(':5,9d␣_⏎', ':5,9d⏎')
    result = _drive(d, _tape_keys(a), monkeypatch)
    assert not result['won']
    assert not any(e.kind == 'floor_key' and e.alive for e in r.entities)


def test_undo_dropped_key_persists_on_the_floor(monkeypatch):
    # The undo precision-tax (a WORLD drop, not a paste) still leaves the key
    # on the floor to be re-fetched — the paste law never touches it.
    d = _fresh(0)
    r = d.rooms[0]
    _drive(d, _K('2lx$plu'), monkeypatch, finish=':q!\r')   # step, then undo: slip
    assert any(e.kind == 'floor_key' and e.alive for e in r.entities)


def test_global_delete_also_clobbers(monkeypatch):
    # :v//d without _ is register-writing too (Vim-faithful) — key lost.
    d = _fresh(0)
    a = d.rooms[0].answer.replace('/d␣_⏎', '/d⏎')
    result = _drive(d, _tape_keys(a), monkeypatch)
    assert not result['won']


# ── rivals ────────────────────────────────────────────────────────────────────

def test_global_delete_rival_loses_a_star(monkeypatch):
    # :g/{b5}/d _ clears the block for 12 where :5,9d _ pays 7.
    d = _fresh(0)
    b5 = d.rooms[0]._ledger_blight
    a = d.rooms[0].answer.replace(':5,9d␣_⏎', f':g/{b5}/d␣_⏎')
    result = _drive(d, _tape_keys(a), monkeypatch)
    assert result['won'] and result['stars'] == 1


def test_subst_blanking_longhand_wins_one_star(monkeypatch):
    # The register-safe longhand: blank the false lines with :s (no clobber,
    # no _ needed) — lawful, far over par, inside budget 60. The blind rows
    # still need door one first (the unseen law covers only the ex-range
    # family, but the :v pattern needs the revealed sacred word anyway).
    d = _fresh(0)
    s4 = d.rooms[0].answer.split('/')[1]
    keys = _K(f'2lx$p:2s/.*//⏎:6,10s/.*//⏎:12,19v/{s4}/s%.*%%⏎$p4l')
    result = _drive(d, keys, monkeypatch)
    assert result['won'] and result['stars'] == 1


def test_scorched_earth_never_opens_the_way(monkeypatch):
    d = _fresh(0)
    keys = _K('2lx$p:%d␣_⏎$')
    result = _drive(d, keys, monkeypatch)
    assert not result['won']


# ── curriculum ────────────────────────────────────────────────────────────────

def test_curriculum_entry():
    lv = next(l for l in LEVELS if l['slug'] == 'culling_ledger')
    assert lv['teaches'] == ['ex_range', 'setnum']
    known = known_commands('culling_ledger')
    assert 'ex_range' in known and 'subst' in known
    assert 'setnum' in known                       # :set nu is guaranteed here
    assert 'q' not in known                        # macros come later
