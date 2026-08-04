# Vimny — a Vim-teaching dungeon crawler.
# Copyright (C) 2026 Chas Kissick
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""The Register II — The Named Vault ("a / "b).

FORCED BY CAPACITY, ACROSS TWO SAYINGS.  Half the bays want one word and half
want another, they alternate, and every bay must CUT its junk word first — so
the unnamed register is clobbered on every single bay and can only ever hold
one of the two words anyway.  `"_` genuinely helps here (it saves the cut from
landing in ""), which is the point: it is a reward for knowing it, not a hole.
It still leaves you walking the vault twice to fetch the other saying's word.

The room is fully open from the spawn and the bays alternate, so the repeating
unit is a PAIR of bays — record the pair, replay it twice.  THAT IS PAR (34).
Par is the optimum or it is a lie, and the plain named route is 69, so pinning
par there would have handed two stars to every route in between.  The macro body
still carries the register lesson: it pastes from both names, and it is recorded
into `q` precisely because recording into `a` would destroy the word parked
there."""
import math
import pytest
from blessed.keyboard import Keystroke
from blessed import Terminal

import main
from vimny.engine.world import CellType
from vimny.content.levels import LEVELS, is_unlocked, _BY_SLUG
from vimny.generation.dungeon_gen import (build_dungeon_register_named_vault as _build,
                                    _R2_PAR, _R2_SPINE, _R2_GATE, _R2_EXIT,
                                    _R2_QUARRY_ROWS, _R2_BAY_ROWS, _R2_JUNK,
                                    _R2_SAYINGS, _R2_QUARRY_WORDS, _R2_STUBS,
                                    _r2_saying_for)
from tests import SEEDS

# The horse rides with the player through the whole Registry wing, and the wing
# only exists once the Warden Eternal has fallen.
_PROGRESS = {'horse_name': 'Artax', 'warden_eternal': {'complete': True}}
ESC = Keystroke('\x1b', name='KEY_ESCAPE')


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


# PAR IS THE MACRO ROUTE — the bays alternate, so the repeating unit is a PAIR,
# recorded at the earliest opportunity and replayed over the remaining four.
_MACRO = _build(0).room.answer

# Hand-repeating the vault with both named registers. It is the register lesson
# without the macro lesson, it costs 69, and at a standard 1.4x budget (48) it
# does NOT win. Par may not be a lie: a par of 69 would hand two stars to this.
_BY_HAND = ('j w "aye j "bye j $ b diw "aP j $ b diw "bP j $ b diw "aP '
            'j $ b diw "bP j $ b diw "aP j $ b diw "bP G l')

# The sub-optimal route that must still WIN, at one star: a ONE-REGISTER player
# who macros. "_ keeps the cut off "" and a macro per saying keeps the walking
# cheap — but there is still no way to hold both words, so the vault is walked
# twice. 38 against par 34.
_RIVAL = ('j w ye qq 2j $ b "_diw P q 2@q '
          '0 5k w ye qq 2j $ b "_diw P q 2@q G l')


def test_the_pair_macro_is_par_at_two_stars(monkeypatch):
    result = _drive(_tape(_MACRO), monkeypatch)
    assert result['won'] and result['stars'] == 2, result


def test_par_equals_the_macro_tape(monkeypatch):
    won, spent = _drive_spent(_tape(_MACRO), monkeypatch)
    assert won and spent == _R2_PAR, (won, spent)


@pytest.mark.parametrize('seed', SEEDS)
def test_par_is_seed_invariant(seed, monkeypatch):
    won, spent = _drive_spent(_tape(_MACRO), monkeypatch, seed=seed)
    assert won and spent == _R2_PAR, (seed, won, spent)


def test_par_is_the_optimum_not_the_comfortable_route(monkeypatch):
    """Hand-repeating the vault is the register lesson without the macro lesson.
    It is nearly TWICE par, so it may not be par — pinning par there would have
    handed two stars to it and to every route between."""
    won, spent = _drive_spent(_tape(_BY_HAND), monkeypatch)
    assert spent > _R2_PAR * 1.4 and not won, (won, spent)


def test_recording_into_a_clobbers_the_word_stored_there(monkeypatch):
    """Macros and text share one register store (vim's own rule), so recording
    into `qa` destroys the word held in "a — and the run fails. Par records into
    `qq` for exactly this reason."""
    clobbered = _MACRO.replace('qq', 'qa').replace('2@q', '2@a')
    assert not _drive(_tape(clobbered), monkeypatch)['won']


# ── the shape of the forcing ─────────────────────────────────────────────────
def test_the_best_single_register_route_wins_but_drops_a_star(monkeypatch):
    """THE LAW, driven: even armed with "_ and a macro, the one-register route
    must walk the vault twice, so it lands over par at one star. It still WINS —
    forcing is by par, never by budget."""
    result = _drive(_tape(_RIVAL), monkeypatch)
    assert result['won'] and result['stars'] == 1, result


def test_the_named_macro_is_strictly_cheaper_than_the_single_register_one(monkeypatch):
    _w1, named = _drive_spent(_tape(_MACRO), monkeypatch)
    _w2, rival = _drive_spent(_tape(_RIVAL), monkeypatch)
    assert _w1 and _w2 and named < rival, (named, rival)


def test_joining_the_quarry_rows_yields_a_clip_no_bay_wants(monkeypatch):
    """The playtest cheese that killed the previous cut: `J` the two quarry
    rows, take both words in one charwise yank, macro the vault with no named
    register at all. Dead by construction now — no bay wants both words."""
    join = 'j J 0 w y2e qa 2j $b diw P 0 4@a'
    assert not _drive(_tape(join), monkeypatch)['won']


def test_typing_the_word_costs_more_than_pasting_it(monkeypatch):
    """The register has to beat the keyboard. `$b cw<word>` is 4 keys plus the
    word; `$b diw "aP` is 8 flat — so the quarry words are LONG on purpose."""
    for word in _R2_QUARRY_WORDS:
        assert 4 + len(word) > 8, word


def test_every_bay_must_cut_before_it_can_paste():
    """The deletion is what puts the unnamed register under constant fire."""
    room = _build(0).room
    for b in _R2_BAY_ROWS:
        assert main._wla_floor_text(room, b).split()[-1] == _R2_JUNK


def test_the_two_sayings_alternate_and_share_no_quarry_word():
    assert len(_R2_SAYINGS) == 2 and len(_R2_BAY_ROWS) == 6
    assert [_r2_saying_for(r) for r in _R2_BAY_ROWS] == [0, 1, 0, 1, 0, 1]
    a, b = _R2_QUARRY_WORDS
    assert a != b
    assert a not in _R2_SAYINGS[1] and b not in _R2_SAYINGS[0]


def test_each_bay_wants_exactly_one_word():
    room = _build(0).room
    for r, target in room._r2_targets.items():
        stub = main._wla_floor_text(room, r).strip()
        assert stub == ' '.join(_R2_STUBS[_r2_saying_for(r)])
        missing = [w for w in _R2_QUARRY_WORDS if w in target.split()]
        assert len(missing) == 1, (r, missing)


@pytest.mark.parametrize('seed', SEEDS)
def test_layout_and_budget(seed):
    room = _build(seed).room
    assert room.par == _R2_PAR
    assert room.budget == math.ceil(_R2_PAR * 1.4)      # STANDARD
    for qrow, word in zip(_R2_QUARRY_ROWS, _R2_QUARRY_WORDS):
        assert main._wla_floor_text(room, qrow).strip() == word


def test_the_vault_is_open_from_the_spawn():
    """No gates and no fog: the bays are visible AND regular, which is what
    makes the alternating pair legible as a macro."""
    room = _build(0).room
    assert not getattr(room, 'fog', None)
    for r in (*_R2_QUARRY_ROWS, *_R2_BAY_ROWS):
        assert room.cells[r][_R2_SPINE] != CellType.WALL


def test_only_the_seal_starts_shut():
    room = _build(0).room
    er, ec = room.exit_pos
    assert room.cells[er][ec] == CellType.WALL


def test_spine_is_every_rows_first_standable():
    room = _build(0).room
    for r in (*_R2_QUARRY_ROWS, *_R2_BAY_ROWS, _R2_GATE):
        first = next((c for c in range(room.cols)
                      if room.cells[r][c] != CellType.WALL), None)
        assert first == _R2_SPINE, (r, first)


def test_exit_sits_beside_the_spine_behind_the_seal():
    assert _R2_EXIT == (_R2_GATE, _R2_SPINE + 1)


def test_register_prefix_is_charged_its_two_keys():
    # "a is two real keypresses on top of the operation — a named register buys
    # capacity, not free typing. The lesson has to survive paying for it.
    assert main._register_prefix_cost({'register': 'a'}) == 2
    assert main._register_prefix_cost({}) == 0
    plain = {'type': 'operator', 'op': 'y', 'motion': 'e'}
    named = dict(plain, register='a')
    assert main._operator_cost(named) == main._operator_cost(plain) + 2


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
