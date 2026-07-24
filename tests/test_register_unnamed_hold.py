# Vimny — a Vim-teaching dungeon crawler.
# Copyright (C) 2026 Chas Kissick
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""The Register I — The Unnamed Hold ("").  The first Registry bonus level.

The geometry forces a delete BETWEEN the word's only source and where it must be
laid: a spine gate (opened only by daw-ing the intruder bay) bars the gap bay, so
the word yanked at the quarry cannot reach the gap without a clobbering cut.  The
taught order is cut → yank → paste (the yank AFTER the delete).  See
blueprints/registry_wing.md and dungeon_gen.build_dungeon_register_unnamed_hold."""
import math
import pytest
from blessed.keyboard import Keystroke
from blessed import Terminal

import main
from engine.world import CellType
from content.levels import LEVELS, is_unlocked, _BY_SLUG
from generation.dungeon_gen import (build_dungeon_register_unnamed_hold as _build,
                                    _R1_PAR, _R1_GATE, _R1_SPINE, _R1_EXIT,
                                    _R1_GATE_ROW, _R1_ROW_DAW, _R1_ROW_QUARRY,
                                    _R1_ROW_GAP)
from tests import SEEDS

ESC = Keystroke('\x1b', code=361, name='KEY_ESCAPE')


def _K(s):
    return [Keystroke(ch) for ch in s]


def _drive(keys, monkeypatch, finish=':wq\r', name='Scribe', seed=0):
    dungeon = _build(seed)
    keys = list(keys) + _K(finish)
    monkeypatch.setattr(main, 'render_all', lambda *a, **k: None)
    monkeypatch.setattr(main.time, 'sleep', lambda *a, **k: None)
    for anim in ('_fireworks_animation', '_win_animation', '_starfield_victory',
                 '_heart_container_animation', '_unlock_animation',
                 '_void_fall_animation', '_drown_animation', '_sc_twinkle_animation'):
        monkeypatch.setattr(main, anim, lambda *a, **k: None)
    monkeypatch.setattr(Terminal, 'height', property(lambda self: 41))
    term = Terminal()
    it = iter(keys)
    monkeypatch.setattr(term, 'inkey', lambda *a, **k: next(it, Keystroke('')))
    return main.run_dungeon(term, 'register_unnamed_hold', {}, player_name=name,
                            _dungeon=dungeon)


def _drive_spent(keys, monkeypatch, **kw):
    box = {}
    orig = main._calc_stars
    monkeypatch.setattr(main, '_calc_stars',
                        lambda won, budget, room, player, level='':
                            (box.__setitem__('spent', budget.spent),
                             orig(won, budget, room, player, level))[1])
    result = _drive(keys, monkeypatch, **kw)
    return result['won'], box.get('spent')


# ── the canonical (par) tape: cut the intruder (opens the gate), yank the quarry
# on the way down, paste it into the gap, then out — all vertical hops via the spine.
def _canon():
    return _K('j') + _K('fq') + _K('daw') \
        + _K('0') + _K('2j') + _K('^') + _K('yiw') \
        + _K('0') + _K('2j') + _K('^') + _K('4e') + _K('l') + _K('p') \
        + _K('0') + _K('2j') + _K('l')


def test_canonical_tape_solves_at_two_stars(monkeypatch):
    result = _drive(_canon(), monkeypatch)
    assert result['won'] and result['stars'] == 2, result


def test_par_equals_the_driven_tape(monkeypatch):
    won, spent = _drive_spent(_canon(), monkeypatch)
    assert won and spent == _R1_PAR, (won, spent)


def test_room_answer_matches_the_canonical_tape():
    room = _build(0).room
    assert room.answer == 'j fq daw 0 2j ^ yiw 0 2j ^ 4e l p 0 2j l'


def test_retyping_the_word_wins_but_drops_a_star(monkeypatch):
    # necessity by par: heal the gate (daw), skip the quarry, and TYPE the missing
    # word into the gap. It still wins (inside the 1.4 budget) but overpays the 9
    # typed letters → 1 star; yank + paste is par.
    rival = (_K('j') + _K('fq') + _K('daw')
             + _K('0') + _K('4j') + _K('^') + _K('4e') + _K('l')
             + _K('a') + _K('godliness') + [ESC]
             + _K('0') + _K('2j') + _K('l'))
    won, spent = _drive_spent(rival, monkeypatch)
    assert won and spent > _R1_PAR, (won, spent)


def test_the_clobber_is_forced_and_strands_the_paste(monkeypatch):
    # The sting: grab the quarry word (yiw) first, then — to pass the spine gate —
    # you must daw the intruder, which overwrites "" with the junk. P then lays the
    # junk into the gap, so the paste bay never reads true → the level is not won.
    wrong = (_K('3j') + _K('^') + _K('yiw')            # grab the word into ""
             + _K('0') + _K('2k') + _K('fq') + _K('daw')  # daw to open the gate — clobbers ""
             + _K('0') + _K('4j') + _K('^') + _K('4e') + _K('l') + _K('p')  # P lays junk
             + _K('0') + _K('2j') + _K('l'))
    result = _drive(wrong, monkeypatch)
    assert not result['won'], result


def test_reyank_after_the_clobber_recovers(monkeypatch):
    # Recoverable, never stranding: after the clobber, go back up to the quarry,
    # re-yank the word (now that the gate is open), descend and paste — it wins.
    fix = (_K('3j') + _K('^') + _K('yiw')              # (clobbered later)
           + _K('0') + _K('2k') + _K('fq') + _K('daw')   # gate opens, "" = junk
           + _K('0') + _K('2j') + _K('^') + _K('yiw')   # re-yank the quarry word
           + _K('0') + _K('2j') + _K('^') + _K('4e') + _K('l') + _K('p')
           + _K('0') + _K('2j') + _K('l'))
    result = _drive(fix, monkeypatch)
    assert result['won'], result


# ── layout / identity ────────────────────────────────────────────────────────
@pytest.mark.parametrize('seed', SEEDS)
def test_dimensions_and_bays(seed):
    room = _build(seed).room
    ref = _build(0).room
    assert (room.rows, room.cols) == (ref.rows, ref.cols)
    assert room.par == _R1_PAR
    assert room.budget == math.ceil(_R1_PAR * 1.4)
    assert main._wla_floor_text(room, _R1_ROW_DAW).strip() == 'look before you quill leap'
    assert main._wla_floor_text(room, _R1_ROW_QUARRY).strip() == 'godliness'
    assert main._wla_floor_text(room, _R1_ROW_GAP).strip() == 'cleanliness is next to'


def test_gate_and_seal_start_shut():
    room = _build(0).room
    er, ec = room.exit_pos
    assert room.cells[er][ec] == CellType.WALL                      # the final seal
    assert room.cells[_R1_GATE_ROW][_R1_SPINE] == CellType.WALL      # the spine gate


def test_gate_bars_the_gap_until_the_daw(monkeypatch):
    # The gap bay lies below the gate; without healing the daw bay the gate is
    # stone, so a straight descent to the gap can't win (it can't even paste).
    stuck = (_K('3j') + _K('^') + _K('yiw')   # grab the quarry (gate still shut)
             + _K('0') + _K('2j'))            # try to descend past the gate — blocked
    result = _drive(stuck, monkeypatch)
    assert not result['won'], result


def test_exit_is_behind_the_seal_not_a_jump_target():
    # The exit sits just east of the spine on the gate row; every bay/spine row's
    # first standable is the spine, so no line jump lands in the exit cell.
    room = _build(0).room
    er, ec = _R1_EXIT
    assert ec == _R1_SPINE + 1
    for r in (_R1_ROW_DAW, _R1_ROW_QUARRY, _R1_ROW_GAP, _R1_GATE):
        first = next((c for c in range(room.cols)
                      if room.cells[r][c] != CellType.WALL), None)
        assert first == _R1_SPINE, (r, first)


# ── curriculum / overworld gating ────────────────────────────────────────────
def test_registry_wing_tag_and_placement():
    lv = _BY_SLUG['register_unnamed_hold']
    assert lv.get('wing') == 'registry'
    slugs = [l['slug'] for l in LEVELS]
    assert slugs.index('register_unnamed_hold') > slugs.index('warden_eternal')


def test_unlocks_only_after_beating_the_game():
    beaten = {'warden_eternal': {'complete': True}}
    assert is_unlocked('register_unnamed_hold', beaten)
    assert not is_unlocked('register_unnamed_hold', {})
