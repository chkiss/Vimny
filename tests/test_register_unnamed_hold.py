# Vimny — a Vim-teaching dungeon crawler.
# Copyright (C) 2026 Chas Kissick
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""The Register I — The Unnamed Hold ("").  The first Registry bonus level.

Three open bays down a spine — QUARRY (the lone word), DAW (an intruder saying),
GAP (a saying missing its last word) — ALL reachable from the start, so the layout
tempts the ruinous order yank -> daw -> paste: the daw overwrites "" with the junk,
so P lays the junk and the gap stays false.  The fix is to reorder (yank+paste
first, then daw) or re-yank; nothing is walled off, so the sting only costs a retry.
See blueprints/registry_wing.md and dungeon_gen.build_dungeon_register_unnamed_hold."""
import math
import pytest
from blessed.keyboard import Keystroke
from blessed import Terminal

import main
from engine.world import CellType
from engine.motion import _vision_flood, _FOGGABLE_CELLS
from content.levels import LEVELS, is_unlocked, _BY_SLUG
from generation.dungeon_gen import (build_dungeon_register_unnamed_hold as _build,
                                    _R1_PAR, _R1_BUDGET, _R1_GATE, _R1_SPINE,
                                    _R1_EXIT, _R1_ROW_QUARRY, _R1_ROW_DAW,
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


# ── the canonical (par) tape — the adversarially-found optimum: ye grabs the
# quarry WITH its leading space in one stroke, fo p lays it past "to" while "" is
# clean, THEN climb back (- k) and cut the intruder (dw), then G l to the seal.
def _canon():
    return _K('j') + _K('ye') + _K('4j') + _K('fo') + _K('p') \
        + _K('-') + _K('k') + _K('fq') + _K('dw') + _K('G') + _K('l')


def test_canonical_tape_solves_at_two_stars(monkeypatch):
    result = _drive(_canon(), monkeypatch)
    assert result['won'] and result['stars'] == 2, result


def test_par_equals_the_driven_tape(monkeypatch):
    won, spent = _drive_spent(_canon(), monkeypatch)
    assert won and spent == _R1_PAR, (won, spent)


def test_room_answer_matches_the_canonical_tape():
    room = _build(0).room
    assert room.answer == 'j ye 4j fo p - k fq dw G l'
    assert room.budget == _R1_BUDGET               # GENEROUS hand-set (see builder)


def test_yank_paste_last_also_wins_a_hair_dearer(monkeypatch):
    # The other clobber-safe order (cut first, THEN yank+paste) also wins — proof
    # the sting is about ORDER, not the keys. It costs one key more than par.
    tape = (_K('3j') + _K('fq') + _K('dw') + _K('-') + _K('k') + _K('ye')
            + _K('4j') + _K('fo') + _K('p') + _K('G') + _K('l'))
    result = _drive(tape, monkeypatch)
    assert result['won'], result


def test_manual_register_run_wins_at_one_star(monkeypatch):
    # A clean, non-golf register solve (yiw + 4e l p, spine-nav) is well over the
    # golf par but well inside the generous budget → it WINS at 1 star. The level
    # never punishes plain-Vim play; the golf tricks only earn the 2nd star.
    manual = (_K('j') + _K('^') + _K('yiw')
              + _K('0') + _K('4j') + _K('^') + _K('4e') + _K('l') + _K('p')
              + _K('0') + _K('2k') + _K('fq') + _K('dw')
              + _K('0') + _K('4j') + _K('l'))
    result = _drive(manual, monkeypatch)
    assert result['won'] and result['stars'] == 1, result


def test_retyping_the_word_wins_but_drops_a_star(monkeypatch):
    # necessity by par: complete the gap by TYPING the missing word instead of
    # yank+paste, then cut the intruder. It still wins (inside the generous budget)
    # but overpays the typed letters → more than par, so it lands at 1 star.
    rival = (_K('j') + _K('4j') + _K('fo') + _K('l')
             + _K('a') + _K('godliness') + [ESC]
             + _K('-') + _K('k') + _K('fq') + _K('dw') + _K('G') + _K('l'))
    result = _drive(rival, monkeypatch)
    assert result['won'] and result['stars'] == 1, result


def test_the_tempting_order_clobbers_and_fails(monkeypatch):
    # The sting the layout tempts: meet the word first (yank), walk down cutting
    # the intruder on the way (daw — clobbers "" with the junk), then paste into
    # the gap — P lays the junk, the gap stays false, the level is not won.
    tempting = (_K('j') + _K('^') + _K('yiw')            # grab the word into ""
                + _K('0') + _K('2j') + _K('fq') + _K('daw')  # daw en route — clobbers ""
                + _K('0') + _K('2j') + _K('^') + _K('4e') + _K('l') + _K('p')  # P lays junk
                + _K('0') + _K('2j') + _K('l'))
    result = _drive(tempting, monkeypatch)
    assert not result['won'], result


def test_reyank_after_the_clobber_recovers(monkeypatch):
    # Nothing is walled off: after the clobber, re-yank the quarry and paste — wins.
    fix = (_K('j') + _K('^') + _K('yiw')                # (clobbered next)
           + _K('0') + _K('2j') + _K('fq') + _K('daw')   # "" = junk
           + _K('0') + _K('2k') + _K('^') + _K('yiw')    # re-yank the quarry word
           + _K('0') + _K('4j') + _K('^') + _K('4e') + _K('l') + _K('p')
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
    assert room.budget == _R1_BUDGET               # generous hand-set (non-1.4)
    assert main._wla_floor_text(room, _R1_ROW_QUARRY).strip() == 'godliness'
    assert main._wla_floor_text(room, _R1_ROW_DAW).strip() == 'look before you quill leap'
    assert main._wla_floor_text(room, _R1_ROW_GAP).strip() == 'cleanliness is next to'


def test_all_lines_reachable_from_the_start_no_fog():
    # No gate, no fog: every bay is visible/reachable from spawn so the layout can
    # tempt the yank. (The exit is WALL behind the seal, so it isn't foggable.)
    room = _build(0).room
    assert not room.fog_cells
    foggable = {(r, c) for r in range(room.rows) for c in range(room.cols)
                if room.cells[r][c] in _FOGGABLE_CELLS}
    assert foggable <= _vision_flood(room, *room.spawn_pos)


def test_seal_starts_shut():
    room = _build(0).room
    er, ec = room.exit_pos
    assert room.cells[er][ec] == CellType.WALL


def test_exit_is_behind_the_seal_not_a_jump_target():
    room = _build(0).room
    er, ec = _R1_EXIT
    assert ec == _R1_SPINE + 1
    for r in (_R1_ROW_QUARRY, _R1_ROW_DAW, _R1_ROW_GAP, _R1_GATE):
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
