# Vimny — a Vim-teaching dungeon crawler.
# Copyright (C) 2026 Chas Kissick
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""The Register II — The Named Vault ("a / "b).

FORCED BY CAPACITY, NOT BY SURVIVAL.  Every bay wants TWO different words, and
the unnamed register holds exactly one thing — so no amount of protecting it
helps.  In particular "_ buys nothing here: nothing is ever cut.  Yank both
words once into "a and "b and the whole vault is pastes; carry one word at a
time and you must walk the room twice and re-land every tail.

The room is fully open from the spawn and the four bays are identical, so the
rhythm is visible as a rhythm — a macro replays it far under par.  That is the
reward, not the requirement: par is the plain named route."""
import math
import pytest
from blessed.keyboard import Keystroke
from blessed import Terminal

import main
from engine.world import CellType
from content.levels import LEVELS, is_unlocked, _BY_SLUG
from generation.dungeon_gen import (build_dungeon_register_named_vault as _build,
                                    _R2_PAR, _R2_SPINE, _R2_GATE, _R2_EXIT,
                                    _R2_QUARRY_ROWS, _R2_GAP_ROWS, _R2_HEAD,
                                    _R2_SAYING, _R2_QUARRY_WORDS)
from tests import SEEDS

# The horse rides with the player through the whole Registry wing, and the wing
# only exists once the Warden Eternal has fallen.
_PROGRESS = {'horse_name': 'Artax', 'warden_eternal': {'complete': True}}


def _K(s):
    return [Keystroke(ch) for ch in s]


def _drive(keys, monkeypatch, finish=':wq\r', name='Scribe', seed=0,
           progress=None):
    dungeon = _build(seed)
    keys = list(keys) + _K(finish)
    monkeypatch.setattr(main, 'render_all', lambda *a, **k: None)
    monkeypatch.setattr(main.time, 'sleep', lambda *a, **k: None)
    monkeypatch.setattr(main, '_prompt_horse_name', lambda *a, **k: 'Artax')
    for anim in ('_fireworks_animation', '_win_animation', '_starfield_victory',
                 '_heart_container_animation', '_unlock_animation',
                 '_void_fall_animation', '_drown_animation', '_sc_twinkle_animation'):
        monkeypatch.setattr(main, anim, lambda *a, **k: None)
    monkeypatch.setattr(Terminal, 'height', property(lambda self: 41))
    term = Terminal()
    it = iter(keys)
    monkeypatch.setattr(term, 'inkey', lambda *a, **k: next(it, Keystroke('')))
    return main.run_dungeon(term, 'register_named_vault',
                            dict(_PROGRESS if progress is None else progress),
                            player_name=name, _dungeon=dungeon)


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


# The named (par) tape: quarry BOTH words once, then every bay is two pastes.
_NAMED = ('j "aye j "bye 2j fe "ap "bp 0 2j fe "ap "bp '
          '0 2j fe "ap "bp 0 2j fe "ap "bp 0 2j l')

# The reward: the four bays are identical, so record one and replay it.
_MACRO = 'j "aye j "bye qq 0 2j fe "ap "bp q 3@q 0 2j l'

# The single-register rival at its BEST — not a naive re-yank per bay, but the
# clever batching route: lay "saves" in every bay, then re-yank and lay "nine".
# It still walks the room twice, and on the second pass `fe` no longer lands on
# the tail (the first paste moved it), so every bay costs an extra motion.
_BATCH = ('j ye 3j fe p 0 2j fe p 0 2j fe p 0 2j fe p '
          '0 8k ye 2j fe e p 0 2j fe e p 0 2j fe e p 0 2j fe e p 0 2j l')


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


def test_the_macro_replays_the_bay_far_under_par(monkeypatch):
    """THE REWARD: identical bays + registers that persist across playback."""
    won, spent = _drive_spent(_tape(_MACRO), monkeypatch)
    assert won and spent < _R2_PAR, (won, spent)


def test_recording_into_a_clobbers_the_word_stored_there(monkeypatch):
    """Macros and text share one register store (vim's own rule), so recording
    into `qa` destroys the word held in "a — and the run fails. The par tape
    records into `qq` for exactly this reason."""
    clobbered = _MACRO.replace('qq', 'qa').replace('3@q', '3@a')
    assert not _drive(_tape(clobbered), monkeypatch)['won']


def test_single_register_batching_wins_but_drops_a_star(monkeypatch):
    """THE LAW, driven: the best one-register route still WINS, but it must walk
    the vault twice and re-land every tail, so it lands over par at one star."""
    result = _drive(_tape(_BATCH), monkeypatch)
    assert result['won'] and result['stars'] == 1, result


def test_named_route_is_strictly_cheaper_than_the_batching_one(monkeypatch):
    _w1, named = _drive_spent(_tape(_NAMED), monkeypatch)
    _w2, batch = _drive_spent(_tape(_BATCH), monkeypatch)
    assert named < batch, (named, batch)


def test_register_prefix_is_charged_its_two_keys():
    # "a is two real keypresses on top of the operation — a named register buys
    # capacity, not free typing. The lesson has to survive paying for it.
    assert main._register_prefix_cost({'register': 'a'}) == 2
    assert main._register_prefix_cost({}) == 0
    plain = {'type': 'operator', 'op': 'y', 'motion': 'e'}
    named = dict(plain, register='a')
    assert main._operator_cost(named) == main._operator_cost(plain) + 2


# ── the shape of the forcing ─────────────────────────────────────────────────
def test_the_black_hole_cannot_help_because_nothing_is_ever_cut():
    """The first cut of this level forced "a by THREAT (a daw clobbered ""), and
    `"_daw` beat par by protecting "" for 2 keys. Capacity forcing has no such
    hole: there is no delete anywhere in the par route to redirect."""
    assert 'd' not in _build(0).room.answer.replace('godliness', '')


def test_every_bay_wants_both_quarry_words():
    room = _build(0).room
    head = ' '.join(_R2_HEAD)
    for g in _R2_GAP_ROWS:
        assert main._wla_floor_text(room, g).strip() == head
    for w in _R2_QUARRY_WORDS:                 # neither word is already present
        assert w not in head
    assert room._r2_gap_target == ' '.join(_R2_SAYING)


def test_quarry_words_sit_on_separate_rows():
    # So no single charwise yank can take both (a linewise 2yy pastes whole
    # lines, which fills no bay).
    assert len(set(_R2_QUARRY_ROWS)) == len(_R2_QUARRY_WORDS) == 2


@pytest.mark.parametrize('seed', SEEDS)
def test_layout_and_budget(seed):
    room = _build(seed).room
    assert room.par == _R2_PAR
    assert room.budget == math.ceil(_R2_PAR * 1.4)      # STANDARD
    for qrow, word in zip(_R2_QUARRY_ROWS, _R2_QUARRY_WORDS):
        assert main._wla_floor_text(room, qrow).strip() == word


def test_the_vault_is_open_from_the_spawn():
    """No gates and no fog: the bays are identical AND visible, which is what
    makes the rhythm legible as a macro."""
    room = _build(0).room
    assert not getattr(room, 'fog', None)
    for r in (*_R2_QUARRY_ROWS, *_R2_GAP_ROWS):
        assert room.cells[r][_R2_SPINE] != CellType.WALL


def test_only_the_seal_starts_shut():
    room = _build(0).room
    er, ec = room.exit_pos
    assert room.cells[er][ec] == CellType.WALL


def test_spine_is_every_rows_first_standable():
    room = _build(0).room
    for r in (*_R2_QUARRY_ROWS, *_R2_GAP_ROWS, _R2_GATE):
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
