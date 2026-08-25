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
(playtest 2026-07-19): the ONE wide cull — `:set nu<CR> 2l x $ p
:2,19v/that/d _<CR> $ p $`, par 23; the three-beat longhand (:2d _ · :5,9d _
· :6,13v _) still wins, at 1★ (35 spent)."""
from collections import deque

import math
import pytest
from blessed.keyboard import Keystroke
from blessed import Terminal

import vimny.game as main
from vimny.engine.world import CellType
from vimny.engine import substitute as S
from vimny.generation.dungeon_gen import (
    build_dungeon_culling_ledger,
    _CL_ROWS, _CL_COLS, _CL_CATCH, _CL_TX, _CL_SEP, _CL_WALL, _CL_GAP,
    _CL_COR, _CL_KEYCH, _CL_DOOR1, _CL_SEALDOOR, _CL_DOOR2, _CL_BRZ_COL,
    _CL_EXIT, _CL_KEEP_ROWS, _CL_BLIGHT_I, _CL_BLIGHT_II, _CL_JUNK_III,
    _CL_SACRED_III, _CL_GAPS, _CL_PAR, _CL_BUDGET,
)
from vimny.content.levels import LEVELS, known_commands
from tests import SEEDS, cached_room
from vimny.engine.tape import to_keys

ENTER = Keystroke('\r', code=343, name='KEY_ENTER')


def _room(seed=0):
    return cached_room('build_dungeon_culling_ledger', seed)


def _fresh(seed=0):
    return build_dungeon_culling_ledger(seed)


def _K(s):
    """Keystroke string → keys. `to_keys` is the ONE converter: tokens like
    `<CR>` and `<Space>` are several glyphs but one keystroke, so they can
    only be matched whole (vimny/engine/tape.py). `separators=False`: this is a
    hand-written keystroke string, not a tape, so a space in it is a space the
    player types (`:6s/^  //`), never display spacing."""
    return to_keys(s, separators=False)


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


def _spend_uncapped(dungeon, keys, monkeypatch, _drive_fn):
    """Drive a route with the budget UNCAPPED and return (won, spent).

    PAR-IS-THE-OPTIMUM (docs/ARCHITECTURE.md): the budget follows par at 1.4x and
    is never widened to keep a sub-optimal route alive, so a rival's claim to
    test is that it costs MORE THAN PAR — not that it squeaks inside a hand-set
    budget. Whether it also falls outside the standard budget is a consequence of
    how much worse it is, not a design knob."""
    box = {}
    orig = main._calc_stars
    monkeypatch.setattr(main, '_calc_stars',
                        lambda won, budget, room, player, level='':
                            (box.__setitem__('spent', budget.spent),
                             orig(won, budget, room, player, level))[1])
    for r in dungeon.rooms:
        r.budget = 99999
    result = _drive_fn(dungeon, keys, monkeypatch)
    return result['won'], box.get('spent')



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
    assert kinds[_CL_SEALDOOR] == 'seal_door'      # one cell east of the brazier
    assert _CL_SEALDOOR[1] == _CL_BRZ_COL + 1
    assert r.exit_pos == _CL_EXIT
    assert r.par == _CL_PAR and r.budget == math.ceil(_CL_PAR * 1.4)
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
def test_ledger_starts_underwater_and_keeps_are_ordered(seed):
    """The ledger starts SUNKEN from turn one — readable but never footing.
    No delayed veil; no door-one darkness addition."""
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
                assert cell in r.underwater_cells   # readable, unwalkable
                assert cell in r.fog_cells          # fog rides with water
                assert not r.is_passable(*cell)
    for row in list(_CL_GAPS) + [_CL_SEP]:         # the water course sleeps too
        for c in range(2, 54):
            if (row, c) in r.underwater_cells or room_cells_are_water(r, row, c):
                assert (row, c) in r.fog_cells
    for c in range(_CL_DOOR1[1] + 1, 50):          # and the corridor past door one
        assert (_CL_COR, c) in r.fog_cells
    # THE HOUSE THAT JACK BUILT: every stanza-III keep bears the chain-word
    # "that"; no intruder anywhere contains it (so :v/that/d reads true).
    for row in _CL_SACRED_III:
        assert _strip(S.line_text(r, row)[0]).startswith('that')
    for row in [_CL_BLIGHT_I] + list(_CL_BLIGHT_II) + list(_CL_JUNK_III):
        assert 'that' not in S.line_text(r, row)[0]


@pytest.mark.parametrize("seed", SEEDS)
def test_no_jump_can_land_on_a_ledger_row(seed):
    from vimny.engine.motion import apply_motion
    from vimny.engine.player import Player
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

def test_blind_cull_works_on_underwater_text():
    # The ledger starts sunken (readable): ranged deletes work immediately.
    d = _fresh(0)
    r = d.rooms[0]
    from vimny.engine.player import Player
    p = Player(name='t')
    p.row, p.col = r.spawn_pos
    handled, msg, _ns, nl = S.run_ex('2d', r, p)
    assert handled, f'unexpected refusal: {msg}'
    assert nl > 0


def test_key_chest_gives_only_a_key(monkeypatch):
    # A chest holds ONE thing: the key chest must never also mint a scroll.
    d = _fresh(0)
    called = []
    monkeypatch.setattr(main, '_pick_relic_scroll',
                        lambda *a, **k: called.append(1) or None)
    _drive(d, _K('2lx'), monkeypatch, finish=':q!\r')
    assert not called


def test_ledger_stays_underwater_after_door_one(monkeypatch):
    # The underwater status is there from BUILD; opening door one changes nothing.
    d = _fresh(0)
    r = d.rooms[0]
    pre = set(r.underwater_cells)
    _drive(d, _K('2lx$p'), monkeypatch, finish=':q!\r')
    for row in _CONTENT_ROWS:
        for ru in r._char_runs_by_row.get(row, []):
            if ru.kind == 'void':
                continue
            cell = (row, ru.col)
            assert cell in r.underwater_cells            # unchanged by play
            assert not r.is_passable(*cell)
    assert pre == set(r.underwater_cells)                # identical sets
    assert (_CL_COR, _CL_BRZ_COL) not in r.fog_cells   # the cold brazier, lit
    assert (_CL_COR, 45) in r.fog_cells            # past the boss door: dark
    assert any(e.kind == 'seal_door' and e.alive for e in r.entities)


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
    # a plain ranged :2d without _ overwrites the held key — door two never
    # opens.
    d = _fresh(0)
    tape = ':set<Space>nu<CR> 2l x $ p :2d<CR> :2,19v/that/d<Space>_<CR> $ p $'
    result = _drive(d, _tape_keys(tape), monkeypatch)
    assert not result['won']


def test_stashing_the_key_loses_it(monkeypatch):
    # KEYS ARE SLIPPERY (global paste law): pasting the key anywhere but onto
    # a locked door loses it outright — no floor copy lands, the hand
    # empties — so the stash never shields a plain cull.
    d = _fresh(0)
    r = d.rooms[0]
    tape = ':set<Space>nu<CR> 2l x $ p p :2,19v/that/d<CR> $ p $'   # drop a copy, cull plain
    result = _drive(d, _tape_keys(tape), monkeypatch)
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
    a = d.rooms[0].answer.replace('/d<Space>_<CR>', '/d<CR>')
    result = _drive(d, _tape_keys(a), monkeypatch)
    assert not result['won']


def test_three_beat_longhand_wins_one_star(monkeypatch):
    # The old canonical: :2d _ · :5,9d _ · :6,13v _ — three beats where one
    # wide :v does it all. Still lawful, still lights the brazier, but at
    # 35 spent it lands over par 23: 1★.
    d = _fresh(0)
    r = d.rooms[0]
    tape = ':set<Space>nu<CR> 2l x $ p :2d<Space>_<CR> :5,9d<Space>_<CR> :6,13v/that/d<Space>_<CR> $ p $'
    won, spent = _spend_uncapped(d, _tape_keys(tape), monkeypatch, _drive)
    assert won and spent > r.par, (won, spent)
    assert r._ledger_lit is True


def test_blackhole_register_needs_no_space(monkeypatch):
    # Vim-faithful: the command name stops at the first non-alphabetic
    # char, so :v//d_ is the same black-hole delete as :v//d _.
    d = _fresh(0)
    tape = '2l x $ p :2,19v/that/d_<CR> $ p $'
    result = _drive(d, _tape_keys(tape), monkeypatch)
    assert result['won'] and result['stars'] == 2


def test_blind_global_cull_works_on_sunken_text():
    # The ledger starts sunken (readable): even the widest :v cull works.
    d = _fresh(0)
    r = d.rooms[0]
    from vimny.engine.player import Player
    p = Player(name='t')
    p.row, p.col = r.spawn_pos
    handled, msg, _ns, nl = S.run_ex('2,19v/that/d _', r, p)
    assert handled, f'unexpected refusal: {msg}'
    assert nl > 0


# ── rivals ────────────────────────────────────────────────────────────────────

def test_global_delete_of_the_chain_word_wrecks_the_keeps(monkeypatch):
    # :g/that/d _ is the :v beat inverted — it culls the CHAIN and spares the
    # intruders. The seal never opens.
    d = _fresh(0)
    a = d.rooms[0].answer.replace(':2,19v/that/d<Space>_<CR>', ':2,19g/that/d<Space>_<CR>')
    result = _drive(d, _tape_keys(a), monkeypatch)
    assert not result['won']


def test_subst_blanking_longhand_wins_one_star(monkeypatch):
    # The register-safe longhand: blank the false lines with :s (no clobber,
    # no _ needed) — lawful, far over par, inside budget 60. The blind rows
    # still need door one first (the unseen law covers the ex-range family
    # and :g/:v deletes; the :v pattern needs the revealed word anyway).
    d = _fresh(0)
    s4 = d.rooms[0].answer.split('/')[1]
    keys = _K(f'2lx$p:2s/.*//<CR>:6,10s/.*//<CR>:12,19v/{s4}/s%.*%%<CR>$p$')
    won, spent = _spend_uncapped(d, keys, monkeypatch, _drive)
    assert won and spent > d.rooms[0].par, (won, spent)


def test_scorched_earth_never_opens_the_way(monkeypatch):
    d = _fresh(0)
    keys = _K('2lx$p:%d<Space>_<CR>$')
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


def room_cells_are_water(room, row, col):
    return room.cells[row][col] == __import__('vimny.engine.world', fromlist=['CellType']).CellType.WATER
