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

"""The Sight Sanctum (v + operators on the selection): structure, forcing law,
seal/bolt discipline, karaoke tape, and the per-token visual gate."""
import math

import pytest
from blessed.keyboard import Keystroke
from blessed import Terminal

import main
from engine.command_guard import action_allowed
from engine.vim_parser import parse
from engine.modes import Mode
from engine.world import CellType
from engine.search import _match_positions
from content.levels import known_commands
from generation.dungeon_gen import (
    build_dungeon_sight_sanctum,
    _SS_ROWS, _SS_COLS, _SS_SPINE, _SS_BAY_W, _SS_BAY_E, _SS_CHAPELS,
    _SS_PLAQUES, _SS_CHEST, _SS_GATE, _SS_BOLT0, _SS_EXIT, _SS_PAR, _SS_ANSWER,
)
from tests import SEEDS, cached_room

ESC = Keystroke('\x1b', name='KEY_ESCAPE')


def _room(seed=0):
    return cached_room('build_dungeon_sight_sanctum', seed)


def _K(s):
    return [Keystroke(ch) for ch in s]


def _bolt(i):
    return (_SS_GATE, _SS_BOLT0 + i)


# The canonical tape (== room.answer with Esc placed): select first, act
# second — v 2j ts d (Cut), v 2j tg c sigil (Word), v j ~ (Case),
# v /q⏎ h d (Seal). 42 keys.
def _canon_keys():
    return (_K('jwelv2jtsd0') + _K('4jwv2jtgc') + _K('sigil') + [ESC] + _K('0')
            + _K('4jvj~') + _K('3jelv') + _K('/q\r') + _K('hd') + _K('G$'))


# The piecewise no-visual rival: D / dd / ^dt{ch} / cc per chapel, g~j for the
# Case rows. Wins — inside the standard budget — but over par: 1 star.
def _piecewise_rival_keys():
    return (_K('jwelDjdd^dts0') + _K('2jw') + _K('cc') + _K('sigil') + [ESC]
            + _K('jdd^dtg0') + _K('2j') + _K('g~j') + _K('3jelDjdd^dtq')
            + _K('G$'))


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
    return main.run_dungeon(term, 'sight_sanctum', {}, player_name=name,
                            _dungeon=dungeon)


def _drive_spent(keys, monkeypatch, seed=0):
    box = {}
    orig = main._calc_stars
    monkeypatch.setattr(main, '_calc_stars',
                        lambda won, budget, room, player, level='':
                            (box.__setitem__('spent', budget.spent),
                             orig(won, budget, room, player, level))[1])
    result = _drive(build_dungeon_sight_sanctum(seed), keys, monkeypatch)
    return result['won'], box.get('spent')


# ── dungeon structure ─────────────────────────────────────────────────────────

@pytest.mark.parametrize("seed", SEEDS)
def test_layout_and_identity(seed):
    room = _room(seed)
    assert (room.rows, room.cols) == (_SS_ROWS, _SS_COLS)
    assert room.spawn_pos == (2, _SS_SPINE)
    assert room.exit_pos == _SS_EXIT
    exit_ent = next(e for e in room.entities if e.kind == 'exit')
    assert (exit_ent.row, exit_ent.col) == _SS_EXIT and exit_ent.edit_immune


@pytest.mark.parametrize("seed", SEEDS)
def test_par_answer_budget(seed):
    room = _room(seed)
    assert room.par == _SS_PAR
    assert room.budget == math.ceil(_SS_PAR * 1.4)
    assert room.answer == _SS_ANSWER


@pytest.mark.parametrize("seed", SEEDS)
def test_exit_and_bolts_start_sealed(seed):
    """The FINAL SEAL law: bolts and exit are STONE until their text holds."""
    room = _room(seed)
    for i in range(len(_SS_CHAPELS)):
        assert room.cells[_bolt(i)[0]][_bolt(i)[1]] == CellType.WALL
    assert room.cells[_SS_EXIT[0]][_SS_EXIT[1]] == CellType.WALL


@pytest.mark.parametrize("seed", SEEDS)
def test_spine_is_every_rows_first_standable(seed):
    """The teleport audit: no jump may land east of the spine — every floor
    row's westmost passable cell is the spine (except the chest nook row)."""
    room = _room(seed)
    for r in range(room.rows):
        cols = [c for c in range(room.cols) if room.is_passable(r, c)]
        if not cols:
            continue
        expect = _SS_CHEST[1] if r == _SS_CHEST[0] else _SS_SPINE
        assert cols[0] == expect, f"row {r} first standable {cols[0]}"


@pytest.mark.parametrize("seed", SEEDS)
def test_q_is_pristine_level_wide(seed):
    """The Seal's search anchor: 'q' occurs in exactly one FLOOR position (the
    'q' of quill) — the plaque copy is sealed in the wall, which search skips."""
    room = _room(seed)
    positions = _match_positions(room, 'q')
    assert len(positions) == 1, positions
    (r, c), = positions
    assert room.is_passable(r, c)
    # and the wall copy exists but is not a landing
    assert any(ru.col == 2 and ''.join(ru.symbols) == 'quill'
               for ru in room.char_runs), "the plaque carries the true word"


def test_chest_grants_the_wardens_sight():
    room = _room(0)
    chest = next(e for e in room.entities if e.kind == 'chest_scroll')
    assert (chest.row, chest.col) == _SS_CHEST
    assert chest.scroll_id == 'visual'
    from content.scrolls import SCROLL_CATALOG
    entry = next(s for s in SCROLL_CATALOG if s['id'] == 'visual')
    assert entry['level_slug'] == 'sight_sanctum'


def test_curriculum_teaches_visual_and_visual_op():
    known = known_commands('sight_sanctum')
    assert 'visual' in known and 'visual_op' in known
    # and neither sibling mode leaks in early (the per-token gate)
    assert 'visual_line' not in known and 'visual_block' not in known


# ── the per-token visual gate ─────────────────────────────────────────────────

def test_v_gates_but_V_and_block_stay_locked():
    known = known_commands('sight_sanctum')
    v_action, _ = parse('v', Mode.NORMAL)
    V_action, _ = parse('V', Mode.NORMAL)
    b_action, _ = parse('\x16', Mode.NORMAL)
    assert action_allowed(v_action, known)
    assert not action_allowed(V_action, known), "V is the Selection Halls' own"
    assert not action_allowed(b_action, known), "<C-v> is the Selection Halls' own"
    prev = known_commands('warden_scrivener')
    assert not action_allowed(v_action, prev), "v unlearned before the Sanctum"


# ── the forcing law, driven ──────────────────────────────────────────────────

@pytest.mark.parametrize("seed", SEEDS)
def test_full_sight_route_wins_par_perfect(seed, monkeypatch):
    dungeon = build_dungeon_sight_sanctum(seed)
    room = dungeon.rooms[0]
    result = _drive(dungeon, _canon_keys(), monkeypatch)
    assert result['won'] and result['stars'] == 2, result
    for i in range(len(_SS_CHAPELS)):
        assert room.cells[_bolt(i)[0]][_bolt(i)[1]] == CellType.FLOOR


def test_canonical_route_costs_exactly_par(monkeypatch):
    won, spent = _drive_spent(_canon_keys(), monkeypatch)
    assert won and spent == _SS_PAR, (won, spent)


@pytest.mark.parametrize("seed", SEEDS)
def test_piecewise_route_wins_at_one_star(seed, monkeypatch):
    """THE LAW, driven: the no-visual D/dd/^dt/cc route WINS — inside the
    standard budget — but over par: 1 star. The sight is forced by PAR."""
    dungeon = build_dungeon_sight_sanctum(seed)
    result = _drive(dungeon, _piecewise_rival_keys(), monkeypatch)
    assert result['won'] and result['stars'] == 1, result


def test_admin_karaoke_tape_tracks_to_the_end(monkeypatch):
    """The answer is the literal tape: driving it as admin never diverges and
    consumes every char (⏎ marks the search Enter; Esc is skipped)."""
    dungeon = build_dungeon_sight_sanctum(0)
    room = dungeon.rooms[0]
    _drive(dungeon, _canon_keys(), monkeypatch, name='admin')
    assert not room.answer_diverged
    assert room.answer_pos == len(room.answer.replace(' ', ''))


# ── seal / bolt discipline ───────────────────────────────────────────────────

def test_undo_rebars_bolt_and_seal(monkeypatch):
    dungeon = build_dungeon_sight_sanctum(0)
    room = dungeon.rooms[0]
    _drive(dungeon, _canon_keys()[:-2] + _K('l'), monkeypatch, finish=':q!\r')
    assert room.cells[_bolt(3)[0]][_bolt(3)[1]] == CellType.FLOOR
    assert room.cells[_SS_EXIT[0]][_SS_EXIT[1]] == CellType.FLOOR, "the seal parted"

    dungeon = build_dungeon_sight_sanctum(0)
    room = dungeon.rooms[0]
    # uu: the walk pushes its own snapshot; the second u reaches the Seal's d —
    # one u refunds the WHOLE selection (anchor + spent ride the snapshot)
    _drive(dungeon, _canon_keys()[:-2] + _K('luu'), monkeypatch, finish=':q!\r')
    assert room.cells[_bolt(3)[0]][_bolt(3)[1]] == CellType.WALL, "re-bars"
    assert room.cells[_SS_EXIT[0]][_SS_EXIT[1]] == CellType.WALL, "re-seals"


def test_linewise_cut_that_eats_a_kept_word_is_a_dead_route(monkeypatch):
    """The anti-cheese: dj on the Cut chapel's head row eats 'veil' — the
    exact-text door must NOT open however much blight also died."""
    dungeon = build_dungeon_sight_sanctum(0)
    room = dungeon.rooms[0]
    _drive(dungeon, _K('jdj'), monkeypatch, finish=':q!\r')
    gr = room.exit_pos[0]           # dj collapsed rows — the gate rode the shift
    assert room.cells[gr][_SS_BOLT0] == CellType.WALL
    assert room.cells[gr][room.exit_pos[1]] == CellType.WALL


def test_half_cleared_chapel_stays_shut(monkeypatch):
    """Exact-row matching: clearing only the head row ('veil' true, 'sill'
    still buried) leaves the bolt barred."""
    dungeon = build_dungeon_sight_sanctum(0)
    room = dungeon.rooms[0]
    _drive(dungeon, _K('jwelD'), monkeypatch, finish=':q!\r')
    assert room.cells[_bolt(0)[0]][_bolt(0)[1]] == CellType.WALL


def test_no_jump_lands_on_the_sealed_exit(monkeypatch):
    """G / $ discipline while the seal holds: G lands the gate row ON the
    spine, and $ stops at the first shut bolt."""
    dungeon = build_dungeon_sight_sanctum(0)
    room = dungeon.rooms[0]

    seen = {}
    orig = main._calc_stars
    def spy(won, budget, room_, player, level=''):
        seen['pos'] = (player.row, player.col)
        return orig(won, budget, room_, player, level)
    monkeypatch.setattr(main, '_calc_stars', spy)
    result = _drive(dungeon, _K('G$'), monkeypatch, finish=':wq\r')
    assert not result['won']
    assert seen['pos'] == (_SS_GATE, _SS_SPINE), seen
