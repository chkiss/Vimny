# Vimny — a Vim-teaching dungeon crawler.
# Copyright (C) 2026 Chas Kissick
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""The Register II — The Named Vault ("a).  The answer to Register I's clobber.

ONE quarry word must be laid into FOUR gap bays, with a cutting bay (whose daw
clobbers "") gating the way to each later gap.  A named register survives every
cut, so the quarry is visited ONCE; the unnamed player must climb back and
re-yank before gaps 2-4.  The `"a` prefix is charged its two real keystrokes, so
the named saving is earned by the re-yanks it avoids, not by free typing."""
import math
import pytest
from blessed.keyboard import Keystroke
from blessed import Terminal

import main
from engine.world import CellType
from content.levels import LEVELS, is_unlocked, _BY_SLUG
from generation.dungeon_gen import (build_dungeon_register_named_vault as _build,
                                    _R2_PAR, _R2_SPINE, _R2_GATE, _R2_EXIT,
                                    _R2_ROW_QUARRY, _R2_GAP_ROWS, _R2_DAW_ROWS,
                                    _R2_GATE_ROWS, _R2_QUARRY_WORD)
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
    return main.run_dungeon(term, 'register_named_vault', {}, player_name=name,
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


def _tape(s):
    keys = []
    for tok in s.split():
        keys += _K(tok)
    return keys


# The named (par) tape: yank ONCE into "a, then paste all four gaps from it,
# cutting a gate open between each. "a survives every cut.
_NAMED = ('j "aye 2j fo "ap 0 2j fq dw 0 2j fo "ap '
          '0 2j fq dw 0 2j fo "ap 0 2j fq dw 0 2j fo "ap G l')

# The unnamed rival: "" is clobbered by every gate-cut, so the quarry must be
# revisited before each later gap. Wins, but over par.
_UNNAMED = ('j ye 2j fo p 0 2j fq dw 0 4k ye 0 6j fo p 0 2j fq dw 0 8k ye '
            '0 10j fo p 0 2j fq dw 0 12k ye 0 14j fo p G l')


def test_named_tape_solves_at_two_stars(monkeypatch):
    result = _drive(_tape(_NAMED), monkeypatch)
    assert result['won'] and result['stars'] == 2, result


def test_par_equals_the_named_tape(monkeypatch):
    won, spent = _drive_spent(_tape(_NAMED), monkeypatch)
    assert won and spent == _R2_PAR, (won, spent)


def test_room_answer_is_the_named_tape():
    assert _build(0).room.answer == _NAMED


@pytest.mark.parametrize('seed', SEEDS)
def test_par_is_seed_invariant(seed, monkeypatch):
    won, spent = _drive_spent(_tape(_NAMED), monkeypatch, seed=seed)
    assert won and spent == _R2_PAR, (seed, won, spent)


def test_unnamed_reyank_rival_wins_but_drops_a_star(monkeypatch):
    """THE LAW, driven: the unnamed route still WINS (inside the standard budget)
    but pays a re-yank per gate-cut, so it lands over par at one star. That gap is
    the whole lesson — and it is earned AFTER paying the "a prefix's two keys."""
    result = _drive(_tape(_UNNAMED), monkeypatch)
    assert result['won'] and result['stars'] == 1, result


def test_named_route_is_strictly_cheaper_than_the_unnamed_one(monkeypatch):
    _w1, named = _drive_spent(_tape(_NAMED), monkeypatch)
    _w2, unnamed = _drive_spent(_tape(_UNNAMED), monkeypatch)
    assert named < unnamed, (named, unnamed)


def test_register_prefix_is_charged_its_two_keys():
    # "a is two real keypresses on top of the operation — a named register buys
    # persistence, not free typing.
    assert main._register_prefix_cost({'register': 'a'}) == 2
    assert main._register_prefix_cost({}) == 0
    plain = {'type': 'operator', 'op': 'y', 'motion': 'e'}
    named = dict(plain, register='a')
    assert main._operator_cost(named) == main._operator_cost(plain) + 2


# ── layout ───────────────────────────────────────────────────────────────────
@pytest.mark.parametrize('seed', SEEDS)
def test_layout_and_budget(seed):
    room = _build(seed).room
    assert room.par == _R2_PAR
    assert room.budget == math.ceil(_R2_PAR * 1.4)      # STANDARD
    assert main._wla_floor_text(room, _R2_ROW_QUARRY).strip() == _R2_QUARRY_WORD
    for g in _R2_GAP_ROWS:                               # every gap starts unfilled
        assert main._wla_floor_text(room, g).strip() == 'cleanliness is next to'
    for d in _R2_DAW_ROWS:                               # every cutting bay is corrupt
        assert main._wla_floor_text(room, d).strip() == 'look before you quill leap'


def test_gates_and_seal_start_shut():
    room = _build(0).room
    er, ec = room.exit_pos
    assert room.cells[er][ec] == CellType.WALL
    for gr in _R2_GATE_ROWS:
        assert room.cells[gr][_R2_SPINE] == CellType.WALL


def test_every_gate_forces_a_cut_between_two_pastes():
    # Structural proof of the lesson: each gate sits BETWEEN two gap bays, with a
    # cutting bay above it — so no route can fill all four gaps without cutting
    # (and clobbering "") in between.
    for gate, daw in zip(_R2_GATE_ROWS, _R2_DAW_ROWS):
        assert daw < gate                                   # the cut is above its gate
        assert any(g < gate for g in _R2_GAP_ROWS)          # a gap before it
        assert any(g > gate for g in _R2_GAP_ROWS)          # and a gap behind it


def test_spine_is_every_rows_first_standable():
    room = _build(0).room
    for r in (_R2_ROW_QUARRY, *_R2_GAP_ROWS, *_R2_DAW_ROWS, _R2_GATE):
        first = next((c for c in range(room.cols)
                      if room.cells[r][c] != CellType.WALL), None)
        assert first == _R2_SPINE, (r, first)


def test_exit_sits_beside_the_spine_behind_the_seal():
    assert _R2_EXIT == (_R2_GATE, _R2_SPINE + 1)


# ── curriculum / wing gating ─────────────────────────────────────────────────
def test_registry_wing_placement_after_register_one():
    lv = _BY_SLUG['register_named_vault']
    assert lv.get('wing') == 'registry'
    slugs = [l['slug'] for l in LEVELS]
    assert slugs.index('register_named_vault') > slugs.index('register_unnamed_hold')
    assert slugs.index('register_unnamed_hold') > slugs.index('warden_eternal')


def test_unlocks_after_register_one():
    assert is_unlocked('register_named_vault',
                       {'register_unnamed_hold': {'complete': True}})
    assert not is_unlocked('register_named_vault', {})
