# Vimny — a Vim-teaching dungeon crawler.
# Copyright (C) 2026 Chas Kissick
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""MACRO PAR SWEEP — par is the optimum, so every level a player can reach WITH
`q`/`@` in hand must have had its par golfed against a macro route.

The Register II shipped par 69 against a 34-key macro because nobody checked.
This file pins the SCOPE of that check so it cannot silently rot: `q`/`@` are
taught at `hall_of_echoes` (display 47), so only the levels from there on can be
macro-golfed at all. Everything earlier is out of reach by curriculum, not by
luck — a macro route there would be un-runnable, so its par is safe from this
class of error.

The sweep itself:
  - hall_of_echoes, gauntlet — their par tapes ALREADY record and replay macros,
    so par was set with macros in hand (asserted below, per seed).
  - register_named_vault — par IS the macro route (34).
  - register_unnamed_hold — 16 keys, one paste, nothing repeats: a macro cannot
    pay for its own `q…q`, asserted by structure below.
  - warden_eternal — a boss, `par is None` (flat 1-star win), so no 2-star to
    cheese.
"""
import pytest

import generation.dungeon_gen as dg
from content.levels import LEVELS, known_commands
from tests import SEEDS

# Every level a player reaches at or after macros are taught, in curriculum order.
_MACRO_SLUG = 'hall_of_echoes'
_AFTER_MACROS = [l for l in LEVELS[[l['slug'] for l in LEVELS].index(_MACRO_SLUG):]
                 if not l.get('admin_only')]

# Levels whose par tape must itself use a macro, because their work repeats.
_MUST_MACRO = ('hall_of_echoes', 'gauntlet', 'register_named_vault')


def test_macros_are_taught_exactly_once_and_late():
    """The sweep's scope depends on this: if `q`/`@` ever move earlier, the set
    of levels needing a macro-golfed par grows, and this test fails first."""
    teach = [l['slug'] for l in LEVELS if 'q' in (l.get('teaches') or [])]
    assert teach == [_MACRO_SLUG], teach
    assert '@' in known_commands(_MACRO_SLUG)


def test_no_level_before_macros_can_be_macro_cheesed():
    """Everything before the Hall of Echoes is out of reach of this bug class —
    `q` is not permitted there, so no macro route exists to beat par."""
    for l in LEVELS[:[x['slug'] for x in LEVELS].index(_MACRO_SLUG)]:
        assert 'q' not in known_commands(l['slug']), l['slug']


@pytest.mark.parametrize('slug', _MUST_MACRO)
@pytest.mark.parametrize('seed', SEEDS)
def test_repeating_levels_have_a_macro_in_their_par_tape(slug, seed):
    """PAR IS THE OPTIMUM: on a level whose work repeats, a par tape with no
    `q`/`@` in it is the signature of the Register II bug — par pinned to the
    comfortable route while a macro undercuts it."""
    answer = getattr(dg, 'build_dungeon_' + slug)(seed).rooms[0].answer
    assert 'q' in answer and '@' in answer, (slug, seed, answer)


@pytest.mark.parametrize('seed', SEEDS)
def test_the_unnamed_hold_is_too_short_for_a_macro_to_pay(seed):
    """The Register I is 16 keys with a single paste. `q{reg}` + `q` + `@{reg}`
    costs 4 before the body runs, so no macro can pay for itself here — its par
    needs no macro golf, and that is a property of the level, not an oversight."""
    room = dg.build_dungeon_register_unnamed_hold(seed).rooms[0]
    assert room.par <= 20
    # `@` is the tell — a recording nobody replays is never cheaper. (Don't test
    # for `q`: this tape contains `fq`, a find, not a record.)
    assert '@' not in room.answer


def test_the_boss_after_macros_has_no_two_star_to_cheese():
    room = dg.build_dungeon_warden_eternal(0).rooms[0]
    assert room.par is None


def test_the_sweep_covers_every_post_macro_level():
    """If a level is ever added after the Hall of Echoes, it lands here and must
    be classified — macro-in-par, too-short, or par-less boss."""
    classified = set(_MUST_MACRO) | {'register_unnamed_hold', 'warden_eternal'}
    assert {l['slug'] for l in _AFTER_MACROS} == classified
