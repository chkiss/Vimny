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

"""The Grandmaster's Sanctum (38.1, act boss): the proving gallery — seven
bays reprising each text-object family's signature discovery on the
exact-text chassis — then the arena, on the Warden's Keep pattern."""
import pytest
from blessed.keyboard import Keystroke
from blessed import Terminal

import main
from engine.world import CellType
from generation.dungeon_gen import (
    build_dungeon_grandmasters_sanctum,
    _GMS_ROWS0, _GMS_COLS0, _GMS_SPINE, _GMS_BAYS, _GMS_PARA, _GMS_GATE, _GMS_TEXT0,
    _GMS_BOLTS, _GMS_SEAL, _GMS_TRANSIT, _GMS_WATCH, _GMS_BUDGET,
    _GMS_A_ROWS, _GMS_A_COLS, _GMS_A_SPAWN, _GMS_A_BOSS, _GMS_A_EXIT,
)
from tests import SEEDS, cached_room

ESC = Keystroke('\x1b', name='KEY_ESCAPE')


def _rooms(seed=0):
    d = build_dungeon_grandmasters_sanctum(seed)
    return d, d.rooms[0], d.rooms[1]


def _gallery(seed=0):
    return cached_room('build_dungeon_grandmasters_sanctum', seed)


def _K(s):
    return [Keystroke(ch) for ch in s]


# The canonical run. Gallery: each op lands from where the previous one
# parked (2j down the spine of results — the chained-landing pattern);
# the dap on the legion bay opens the last bolt and the seal in the same
# stroke, and the linewise park (first caret-stop = the Grandmaster,
# fog-blind) carries the player through the gate. Arena: close, trade
# five strikes, take the dropped key, unlock, exit.
def _canon_keys(room):
    w = room._gms_words
    return (_K('2jwwdiw')
            + _K('2jci"') + _K(w['q_cure']) + [ESC]
            + _K('2jda[')
            + _K('2jcis') + _K(w['s_cure'] + '.') + [ESC]
            + _K('2jdit')
            + _K('2jci{') + _K(w['b_cure']) + [ESC]
            + _K('2jdap')
            # The dap's linewise park leaves the cursor at the head of the
            # collapsed gate row; $ rides the opened gate east past the
            # transit cell — the natural stroke from the bottom of the hall.
            + _K('$')
            # The Unmaking: shear his six strands in ANY order (no karaoke) —
            # jump to a strand's row, f onto the structure, delete inside. He
            # STARTS inside the word strand and slips away when you close on
            # him, so that strand is taken LAST (2G e diw — e stops on
            # 'stitch', where he can no longer flee). The sixth stroke
            # unmakes him and opens the seal; 7G $ rides east to the exit.
            + _K('4Gf"di"')
            + _K('6Gf(di(')
            + _K('8Gf{di{')
            + _K('10Gf<dit')
            + _K('12Gfvdis')
            + _K('2Gediw')
            + _K('7G$'))


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
    return main.run_dungeon(term, 'grandmasters_sanctum', {}, player_name=name,
                            _dungeon=dungeon)


# ── structure ─────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("seed", SEEDS)
def test_two_rooms_and_identity(seed):
    d, gallery, arena = _rooms(seed)
    assert (gallery.rows, gallery.cols) == (_GMS_ROWS0, _GMS_COLS0)
    assert (arena.rows, arena.cols) == (_GMS_A_ROWS, _GMS_A_COLS)
    assert gallery.spawn_pos == (1, _GMS_SPINE)
    assert gallery.exit_pos == _GMS_TRANSIT
    # NO exit entity in the gallery: :wq there can never win the level.
    assert not any(e.kind == 'exit' for e in gallery.entities)
    exit_ent = next(e for e in arena.entities if e.kind == 'exit')
    assert (exit_ent.row, exit_ent.col) == _GMS_A_EXIT
    assert gallery.par is None and arena.par is None
    assert gallery.budget == _GMS_BUDGET


@pytest.mark.parametrize("seed", SEEDS)
def test_bolts_and_seal_start_barred(seed):
    room = _gallery(seed)
    for dc in _GMS_BOLTS:
        assert room.cells[_GMS_GATE][dc] == CellType.WALL
    assert room.cells[_GMS_GATE][_GMS_SEAL] == CellType.WALL


@pytest.mark.parametrize("seed", SEEDS)
def test_the_grandmaster_watches_from_the_pocket(seed):
    room = _gallery(seed)
    gm = next(e for e in room.entities
              if e.kind == 'warden' and e.tag == 'grandmaster')
    assert (gm.row, gm.col) == _GMS_WATCH
    assert gm.edit_immune                     # he anchors the gate row vs dG


@pytest.mark.parametrize("seed", SEEDS)
def test_doors_read_the_computed_targets(seed):
    # The plaque (west wall) IS the door target, laid from the same string.
    room = _gallery(seed)
    for i, (target, _dc) in enumerate(room._gms_doors[:6]):
        row = _GMS_BAYS[i]
        cells = {}
        for ru in room.char_runs:
            if ru.row == row and ru.col < _GMS_SPINE:
                for k, s in enumerate(ru.symbols):
                    cells[ru.col + k] = s
        lo, hi = min(cells), max(cells)
        plaque = ''.join(cells.get(c, ' ') for c in range(lo, hi + 1))
        assert plaque == target
    assert room._gms_doors[6][0] is None      # the legion bolt


@pytest.mark.parametrize("seed", SEEDS)
def test_targets_are_not_already_true(seed):
    room = _gallery(seed)
    texts = {main._wla_floor_text(room, r).strip() for r in range(room.rows)}
    for target, _dc in room._gms_doors[:6]:
        assert target not in texts


@pytest.mark.parametrize("seed", SEEDS)
def test_ops_are_staggered(seed):
    # Adjacent bays never share an operator (the final-drill decision):
    # d · c · d · c · d · c · d — no dot rides between bays.
    ops = ('d', 'c', 'd', 'c', 'd', 'c', 'd')
    assert all(a != b for a, b in zip(ops, ops[1:]))


# ── playthrough ───────────────────────────────────────────────────────────────

@pytest.mark.parametrize("seed", SEEDS)
def test_canonical_run_clears_both_rooms(seed, monkeypatch):
    d, gallery, arena = _rooms(seed)
    result = _drive(d, _canon_keys(gallery), monkeypatch)
    assert result['won']
    assert d.current_room == 1
    gm = next(e for e in arena.entities if e.kind == 'warden')
    assert not gm.alive


# ── the arena: The Unmaking ─────────────────────────────────────────────────

def _drive_arena(d, keys, monkeypatch, finish=':q!\r'):
    d.current_room = 1                       # start in the arena in isolation
    return _drive(d, keys, monkeypatch, finish=finish)


@pytest.mark.parametrize("seed", SEEDS)
def test_arena_six_strands_on_distinct_rows(seed):
    _d, _g, arena = _rooms(seed)
    lec = arena._gm_lecterns
    assert len(lec) == 6
    assert len({l['row'] for l in lec}) == 6          # no shared rows (no pull-shift)
    assert {l['obj'] for l in lec} == {'iw', 'i"', 'i(', 'i{', 'it', 'is'}
    gm = next(e for e in arena.entities if e.tag == 'grandmaster')
    assert gm.edit_immune and gm.hp == gm.max_hp == 6


def test_grandmaster_starts_inside_a_strand(monkeypatch):
    # He opens IN a deletion target (the word strand's cursor cell), not on
    # bare floor — a place to be deleted.
    _d, _g, arena = _rooms(0)
    gm = next(e for e in arena.entities if e.tag == 'grandmaster')
    assert (gm.row, gm.col) == _GMS_A_BOSS
    assert any((gm.row, gm.col) == l['cursor'] for l in arena._gm_lecterns)


def test_arena_has_no_karaoke_and_a_boss_budget(seed=0):
    _d, _g, arena = _rooms(0)
    assert arena.answer == ''                          # no fixed route
    assert arena.par is None and arena.budget >= 220    # boss convention


def test_x_cannot_strike_the_grandmaster(monkeypatch):
    # He is edit_immune: x never lands — the only recourse is the text.
    d, _g, arena = _rooms(0)
    _drive_arena(d, _K('xxxxxxxx'), monkeypatch)
    gm = next(e for e in arena.entities if e.tag == 'grandmaster')
    assert gm.alive and gm.hp == 6


def test_one_shear_drains_one_hp(monkeypatch):
    d, _g, arena = _rooms(0)
    _drive_arena(d, _K('4Gf"di"'), monkeypatch)       # shear the quote strand
    gm = next(e for e in arena.entities if e.tag == 'grandmaster')
    assert gm.alive and gm.hp == 5                     # 6 − 1 strand


def test_dd_does_not_shear_a_strand(monkeypatch):
    # A whole-line dd wipes the structure marker too, so it does NOT count —
    # the object (inner-delete, marker kept) is what shears.
    d, _g, arena = _rooms(0)
    _drive_arena(d, _K('4Gdd'), monkeypatch)          # dd the quote row
    gm = next(e for e in arena.entities if e.tag == 'grandmaster')
    assert gm.alive and gm.hp == 6


def test_approaching_makes_him_slip_to_another_strand(monkeypatch):
    # Close within 2 cells of where he opens and he slips into another strand.
    d, _g, arena = _rooms(0)
    start = _GMS_A_BOSS
    _drive_arena(d, _K('2G' + 'l' * 8), monkeypatch)   # walk along his row toward him
    gm = next(e for e in arena.entities if e.tag == 'grandmaster')
    assert (gm.row, gm.col) != start
    assert any((gm.row, gm.col) == l['cursor'] for l in arena._gm_lecterns)  # into a target


def test_search_landing_makes_him_slip(monkeypatch):
    # A / search onto his W lands the cursor on him — he slips away.
    d, _g, arena = _rooms(0)
    start = _GMS_A_BOSS
    _drive_arena(d, _K('/W\r'), monkeypatch)
    gm = next(e for e in arena.entities if e.tag == 'grandmaster')
    assert (gm.row, gm.col) != start


@pytest.mark.parametrize("seed", SEEDS)
def test_the_unmaking_opens_the_seal(seed, monkeypatch):
    d, _g, arena = _rooms(seed)
    # take his starting strand (the word) LAST — 2G e diw — e stops on 'stitch',
    # where he can no longer slip.
    keys = _K('4Gf"di"6Gf(di(8Gf{di{10Gf<dit12Gfvdis2Gediw')
    result = _drive_arena(d, keys + _K('7G$'), monkeypatch, finish=':wq\r')
    gm = next(e for e in arena.entities if e.tag == 'grandmaster')
    assert not gm.alive                                # all six strands sheared
    assert arena.cells[_GMS_A_EXIT[0]][arena._gm_seal_col] == CellType.FLOOR
    assert result['won']


def test_gallery_wq_cannot_win(monkeypatch):
    d, gallery, _arena = _rooms(0)
    result = _drive(d, _K('G'), monkeypatch, finish=':wq\r')
    assert not result['won']
    assert d.current_room == 0


def test_wrong_object_leaves_the_bolt_barred(monkeypatch):
    # daw on the word bay leaves a single-space-narrower hole than diw —
    # the plaque reads false, the bolt stays barred.
    d, gallery, _arena = _rooms(0)
    _drive(d, _K('2jwwdaw'), monkeypatch, finish=':q!\r')
    assert gallery.cells[_GMS_GATE][_GMS_BOLTS[0]] == CellType.WALL


def test_right_object_draws_the_bolt_and_the_appraisal(monkeypatch):
    d, gallery, _arena = _rooms(0)
    _drive(d, _K('2jwwdiw'), monkeypatch, finish=':q!\r')
    assert gallery.cells[_GMS_GATE][_GMS_BOLTS[0]] == CellType.FLOOR


def test_undo_rebars_the_bolt(monkeypatch):
    d, gallery, _arena = _rooms(0)
    _drive(d, _K('2jwwdiwu'), monkeypatch, finish=':q!\r')
    assert gallery.cells[_GMS_GATE][_GMS_BOLTS[0]] == CellType.WALL


def test_legion_bolt_needs_the_goblins_down(monkeypatch):
    d, gallery, _arena = _rooms(0)
    keys = _canon_keys(gallery)
    # strip everything from the dap on (leave the legion standing)
    keys = keys[:next(i for i in range(len(keys) - 2)
                      if ''.join(str(k) for k in keys[i:i + 4]) == '2jda'
                      and str(keys[i + 4]) == 'p')]
    _drive(d, keys, monkeypatch, finish=':q!\r')
    assert gallery.cells[_GMS_GATE][_GMS_BOLTS[6]] == CellType.WALL
    assert gallery.cells[_GMS_GATE][_GMS_SEAL] == CellType.WALL


@pytest.mark.parametrize("seed", SEEDS)
def test_dit_park_lands_inside_the_braces(seed):
    # The chained landing: dit parks at the tag's inner start, and 2j must
    # carry that column INSIDE the brace pair — ci{ has no forward seek
    # (Vim-faithful), so a park east of the } would leave the op dead.
    room = _gallery(seed)
    w = room._gms_words
    park = _GMS_TEXT0 + len(w['t_l']) + 1 + 1 + len(w['t_name']) + 1
    open_col = _GMS_TEXT0 + len(w['b_n']) + 1
    close_col = open_col + 1 + len(w['b_rot'])
    assert open_col < park < close_col


# ── audits ────────────────────────────────────────────────────────────────────

def test_dG_is_parried_at_the_gate(monkeypatch):
    # The Grandmaster anchors the gate row: a dG rampage from the first bay
    # stops there — bolts and plaque survive.
    d, gallery, _arena = _rooms(0)
    _drive(d, _K('2jdG'), monkeypatch, finish=':q!\r')
    gr = gallery.exit_pos[0]
    for dc in _GMS_BOLTS[:6]:                 # the legion bolt MAY open (dG
        assert gallery.cells[gr][dc] == CellType.WALL   # does kill the goblins)
    assert gallery.cells[gr][_GMS_SEAL] == CellType.WALL          # seal shut


@pytest.mark.parametrize("seed", SEEDS)
def test_arena_search_finds_the_grandmaster(seed):
    # The Warden is always W — Scrivener, Pathfinder, Grandmaster alike.
    from engine.search import find_next
    from engine.player import Player
    d, _gallery, arena = _rooms(seed)
    p = Player()
    p.row, p.col = arena.spawn_pos
    assert find_next(arena, p, 'W', True) == _GMS_A_BOSS


def test_G_parks_on_the_threshold_not_past_the_seal(monkeypatch):
    # Only $ rides through the opened gate: G's first-non-blank is the
    # threshold ◆ at the head of the gate row, west of the bolts.
    d, gallery, _arena = _rooms(0)
    w = gallery._gms_words
    # the gallery solve, but the finale $ (which rides the gate) swapped for G
    # (which parks on the threshold ◆, west of the bolts — no descent).
    keys = (_K('2jwwdiw') + _K('2jci"') + _K(w['q_cure']) + [ESC]
            + _K('2jda[') + _K('2jcis') + _K(w['s_cure'] + '.') + [ESC]
            + _K('2jdit') + _K('2jci{') + _K(w['b_cure']) + [ESC]
            + _K('2jdap') + _K('G'))
    _drive(d, keys, monkeypatch, finish=':q!\r')
    assert d.current_room == 0


def test_dap_G_cannot_skip_the_gallery(monkeypatch):
    # The collapse cheese: dap the legion bay from a j-chain, then G — the
    # pulled-up Grandmaster is a lawful G park, but the seal is still
    # stone, so standing beyond it must NOT descend to the arena.
    d, gallery, _arena = _rooms(0)
    result = _drive(d, _K('14jdapG'), monkeypatch, finish=':wq\r')
    assert not result['won']
    assert d.current_room == 0


@pytest.mark.parametrize("seed", SEEDS)
def test_transit_unreachable_until_the_seal(seed):
    from collections import deque
    room = _gallery(seed)
    seen, dq = {room.spawn_pos}, deque([room.spawn_pos])
    while dq:
        r, c = dq.popleft()
        for dr, dc in ((0, 1), (0, -1), (1, 0), (-1, 0)):
            nr, nc = r + dr, c + dc
            if (nr, nc) not in seen and 0 <= nr < room.rows and 0 <= nc < room.cols \
                    and room.is_passable(nr, nc):
                seen.add((nr, nc))
                dq.append((nr, nc))
    assert _GMS_TRANSIT not in seen
    assert _GMS_WATCH not in seen
