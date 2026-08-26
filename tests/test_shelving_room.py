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

The Culling Ledger's chasm chassis: a misted shelf no foot can reach, NO
plaque (the round is an echo — the true shelf is known by sense). Each
mended misfiling grinds back its own gallery bolt, in any order; the seal
parts when the whole round reads true. Canonical :set nu + :6m3 + :6< +
:7t7 + :8> + $, par 15. :m/:t are structural row surgery (fog and mist
ride along); _shelving_tick re-mists any bare shelf floor each turn."""
from collections import deque

import math
import pytest
from blessed.keyboard import Keystroke
from blessed import Terminal

import vimny.game as main
from vimny.engine.world import CellType
from vimny.engine import substitute as S
from vimny.generation.dungeon_gen import (
    build_dungeon_shelving_room,
    _SHR_ROWS, _SHR_COLS, _SHR_TX, _SHR_BAND, _SHR_WTR, _SHR_GAL,
    _SHR_SEAL_COL, _SHR_EXIT_COL, _SHR_BOLT_COLS, _SHR_CALLS, _SHR_INIT,
    _SHR_PAR, _SHR_BUDGET,
)
from vimny.engine.tape import to_keys
from tests import SEEDS, cached_room

ENTER = Keystroke('\r', code=343, name='KEY_ENTER')


def _room(seed=0):
    return cached_room('build_dungeon_shelving_room', seed)


def _fresh(seed=0):
    return build_dungeon_shelving_room(seed)


def _K(s):
    """Keystroke string → keys. `to_keys` is the ONE converter: tokens like
    `<CR>` and `<Space>` are several glyphs but one keystroke, so they can
    only be matched whole (vimny/engine/tape.py). `separators=False`: this is a
    hand-written keystroke string, not a tape, so a space in it is a space the
    player types (`:6s/^  //`), never display spacing."""
    return to_keys(s, separators=False)


def _tape_keys(answer):
    """room.answer → keystrokes, via the one shared translator (vimny/engine/tape.py)."""
    return to_keys(answer)


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



# ── structure ─────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("seed", SEEDS)
def test_dimensions_and_seal(seed):
    r = _room(seed)
    assert (r.rows, r.cols) == (_SHR_ROWS, _SHR_COLS)
    assert r.cells[_SHR_GAL][_SHR_SEAL_COL] == CellType.WALL
    for dc in _SHR_BOLT_COLS:                       # the four bolts, all barred
        assert r.cells[_SHR_GAL][dc] == CellType.WALL
    assert r.exit_pos == (_SHR_GAL, _SHR_EXIT_COL)
    assert r.par == _SHR_PAR and r.budget == math.ceil(_SHR_PAR * 1.4)


@pytest.mark.parametrize("seed", SEEDS)
def test_the_round_is_misfiled_but_known_by_heart(seed):
    r = _room(seed)
    targets = r._shr_targets
    assert len(targets) == 8
    # Frère Jacques, the echo round: every call repeats as an echo one step
    # deep — order and duplication by SENSE, the score only confirms it.
    for i in range(0, 8, 2):
        assert targets[i] == targets[i].lstrip()          # the call, flush
        assert targets[i + 1] == '  ' + targets[i]        # the echo, a step deep
    # shelf rows 1..7 carry the misfiled round, indent as designed
    for row, (text, ind) in enumerate(_SHR_INIT, start=1):
        t = S.line_text(r, row)[0]
        assert t.rstrip() == (' ' * ind) + text
    # the last echo was never shelved: three Ding lines will be needed,
    # only one stands
    dings = sum(1 for row in range(1, 8)
                if 'Ding' in S.line_text(r, row)[0])
    assert dings == 1
    # NO plaque (playtest 2026-07-19): the shelf's own sound pairs carry
    # the echo convention — nothing carved west of the band
    assert not any(ru.col < _SHR_TX for ru in r.char_runs)


@pytest.mark.parametrize("seed", SEEDS)
def test_shelf_is_misted_sightlined_and_unwalkable(seed):
    from vimny.engine.motion import _vision_flood
    r = _room(seed)
    visible = _vision_flood(r, *r.spawn_pos)
    for row in range(1, 8):
        for c in range(*_SHR_BAND):
            assert (row, c) in r.fog_cells and (row, c) in r.underwater_cells
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


def test_fresh_rows_stay_misted(monkeypatch):
    # After the full canonical run the buffer has grown a row: no bare shelf
    # floor anywhere (the tick re-mists).
    d = _fresh(0)
    result = _drive(d, _tape_keys(d.rooms[0].answer), monkeypatch)
    assert result['won']
    r = d.rooms[0]
    gal = S._last_standable_row(r)
    for row in range(1, gal):
        for c in range(r.cols):
            if r.cells[row][c] == CellType.FLOOR:
                assert (row, c) in r.fog_cells


# ── the orderless bolts ───────────────────────────────────────────────────────

def test_bolts_open_only_when_round_is_complete(monkeypatch):
    # The per-line seals are read-only predicates; the full-round 'lines' seal
    # opens all four gallery bolts + the exit gate at once.  A single fix in
    # isolation does NOT open any bolt — only the completed round does.
    fixes = (':6m3<CR>',      # the stray echo rejoins its pair
             ':5<<CR>',       # the Sonnez echo un-deepens
             ':7t7<CR>')      # the last echo shelved
    for tape in fixes:
        d = _fresh(0)
        r = d.rooms[0]
        _drive(d, _K(tape), monkeypatch, finish=':q!\r')
        gal = S._last_standable_row(r)
        for i, dc in enumerate(_SHR_BOLT_COLS):
            assert r.cells[gal][dc] == CellType.WALL, (tape, i)
    # All three + :8> + $ → bolts and seal open
    d = _fresh(0)
    r = d.rooms[0]
    _drive(d, _K(':6m3<CR>:6<<CR>:7t7<CR>:8><CR>$'), monkeypatch)
    gal = S._last_standable_row(r)
    for dc in _SHR_BOLT_COLS:
        assert r.cells[gal][dc] == CellType.FLOOR


def test_fixes_in_any_order_still_win_at_par(monkeypatch):
    # The scrambled route: shelve the last echo first, set it, then the
    # Sonnez step, then the stray — same spend, same 2★.
    d = _fresh(0)
    r = d.rooms[0]
    result = _drive(d, _K(':7t7<CR>:8><CR>:5<<CR>:6m3<CR>$'), monkeypatch)
    assert result['won'] and result['stars'] == 2
    gal = S._last_standable_row(r)
    for dc in _SHR_BOLT_COLS:
        assert r.cells[gal][dc] == CellType.FLOOR


def test_undo_rebars_a_ground_bolt(monkeypatch):
    d = _fresh(0)
    r = d.rooms[0]
    _drive(d, _K(':7t7<CR>u'), monkeypatch, finish=':q!\r')
    gal = S._last_standable_row(r)
    assert r.cells[gal][_SHR_BOLT_COLS[2]] == CellType.WALL


# ── rivals ────────────────────────────────────────────────────────────────────

def test_copy_delete_rival_to_the_move_loses_a_star(monkeypatch):
    # :t + :d imitates :m at nearly twice the price.
    d = _fresh(0)
    keys = _K(':6t3<CR>:7d<CR>:6<<CR>:7t7<CR>:8><CR>$')
    result = _drive(d, keys, monkeypatch)
    assert result['won'] and result['stars'] == 1


def test_substitute_rival_to_the_indents_loses_a_star(monkeypatch):
    # :s/^ anchors imitate :> and :< at several times the cost.
    d = _fresh(0)
    keys = _K(':6m3<CR>:6s/^  //<CR>:7t7<CR>:8s/^/  /<CR>$')
    won, spent = _spend_uncapped(d, keys, monkeypatch, _drive)
    assert won and spent > d.rooms[0].par, (won, spent)


def test_scorched_shelf_never_opens_the_seal(monkeypatch):
    d = _fresh(0)
    result = _drive(d, _K(':1,7d<CR>$'), monkeypatch)
    assert not result['won']


# ── curriculum ────────────────────────────────────────────────────────────────

def test_curriculum_entry():
    from vimny.content.levels import _BY_SLUG, known_commands
    lv = _BY_SLUG['shelving_room']
    assert lv['display'] == '41'
    assert lv['teaches'] == []                     # the ex_range kit, second lesson
    assert 'ex_range' in set(known_commands('shelving_room'))


@pytest.mark.parametrize("seed", SEEDS)
def test_the_shelf_lines_are_readable_through_the_mist(
        seed, monkeypatch, capsys):
    """REGRESSION 2026-08-23: a misted floor cell carrying text rendered only
    once _discovered() — some OPEN revealed cell beside it — and most shelf
    lines touch no open floor at all until the player edits them, so six of
    eight verses shipped invisible: the par route manipulated lines the player
    could never see. The law now reads: the haze hides TERRAIN, never
    WRITING. Bare channels keep the discovery gate (that gate hides the
    channel's shape); ink shows through the weather."""
    dungeon = build_dungeon_shelving_room(seed)
    room = dungeon.rooms[0]
    line1 = next(ru for ru in room.char_runs if ru.row == 1)
    assert (line1.row, line1.col) in room.underwater_cells, 'precondition: under mist'
    monkeypatch.setattr(main.time, 'sleep', lambda *a, **k: None)
    monkeypatch.setattr(Terminal, 'height', property(lambda self: 45))
    monkeypatch.setattr(Terminal, 'width', property(lambda self: 120))
    term = Terminal()
    import vimny.render.colors as _C
    _C.init(term)                       # the real renderer paints this frame
    it = iter(_K(':wq\r'))
    monkeypatch.setattr(term, 'inkey', lambda *a, **k: next(it, Keystroke('')))
    main.run_dungeon(term, 'shelving_room', {}, player_name='Scribe',
                     _dungeon=dungeon)
    frame = capsys.readouterr().out
    assert ''.join(line1.symbols) in frame, \
        'the first shelf verse must render on frame one, discovered or not'


@pytest.mark.parametrize("seed", SEEDS)
def test_one_open_bolt_never_unblinds_the_pocket(seed):
    """REGRESSION 2026-08-23 (playtest): the four bolts open STATELESSLY as
    their misfiling is mended — and the first open bolt gave the reveal flood
    a sightline straight down the gallery, unveiling the chest and exit past
    the three still-shut bolts. G/gg then teleported the player east across
    stone to the chest, because a fogged cell is impassable and the pocket's
    fog had lifted. The pocket is now MIST as well as fog: weather does not
    lift because a gap opened somewhere on its row, so no jump or scan can
    land there until the tick unveils it at seal-open."""
    r = _room(seed)
    gal = 9
    pocket = [(gal, c) for c in range(62, 71)]
    assert all((gal, c) in r.underwater_cells for (gal, c) in pocket), \
        'precondition: the pocket rides the mist'
    # One bolt grinds back — exactly what the stateless tick does.
    from vimny.engine.world import CellType
    from vimny.engine import motion
    r.cells[gal][57] = CellType.FLOOR
    motion.auto_fog_tick(r, *r.spawn_pos)
    assert all((gal, c) in r.fog_cells for (gal, c) in pocket), \
        'an open bolt must not unveil the pocket past the shut ones'
    assert all((gal, c) in r.underwater_cells for (gal, c) in pocket)
    # Every jump/scan stays west of the pocket; the one OPEN bolt is itself
    # lawful footing ($ parks there), but nothing beyond it is reachable.
    from vimny.engine.player import Player
    p = Player(row=r.spawn_pos[0], col=r.spawn_pos[1])
    for keys in ('G', 'gg', '$', 'W'):
        p.row, p.col = r.spawn_pos
        for k in keys:
            motion.apply_motion(p, k, 1, r)
        assert p.col <= 57, f'{keys!r} landed at col {p.col}, past the bolts'
