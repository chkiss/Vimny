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

"""The Operator's Vault's passwords — is each one takeable by its own motion?

Every gate in the vault is a `fancy_door`, so the password's SPELLING is the
forcing device: the door opens for a register reading exactly those words, and
which motion produces exactly those words is decided by where the punctuation
and the spaces fall. That makes the pools load-bearing content, not flavour —
a `_OV_SPLIT` entry that someone "tidied up" by removing its full stop would
silently turn corridor 7's `dW` lesson back into a `dw` lesson, and every
existing test would still pass.

So these tests DRIVE THE REAL MOTIONS over the real words rather than eyeball
the strings. `w` and `W` disagreeing on a token is not a fact about punctuation
in the abstract; it is a fact about `engine.motion`, and it is the one the level
is built on.

The corridor audit (`test_operators_vault_corridors.py`) proves the doors are
forced once they are placed. This file proves the WORDS can carry that, which
is the part that has to hold before any geometry is cut around them.
"""
import random

import pytest

import generation.dungeon_gen as dg
from engine.motion import apply_motion
from engine.player import Player
from engine.world import CharRun, Room, RoomType, CellType
from tests import SEEDS

_START = 2          # where a test word is laid
_TAIL  = 'zz'       # a plain token laid AFTER it — see _row_with


def _row_with(word):
    """A one-row scratch room holding `word` followed by a plain tail token.

    THE TAIL IS NOT PADDING. `w`/`W` move to the start of the NEXT word, and a
    word motion with nothing ahead of it does not move at all — so a row
    holding only the password reports every motion landing on column `_START`
    and every one of these tests passes or fails for the wrong reason. The tail
    gives the motions somewhere to arrive, which is what makes "did `w` stop
    inside the token?" a question with an answer.

    Spaces in a phrase are laid as gaps, which is what they are on the floor.
    """
    tail_col = _START + len(word) + 2
    room = Room(room_type=RoomType.ENTRY, rows=3, cols=tail_col + len(_TAIL) + 4)
    room.cells = [[CellType.FLOOR] * room.cols for _ in range(3)]
    for c in range(room.cols):
        room.cells[0][c] = room.cells[2][c] = CellType.WALL
    for i, sym in enumerate(word):
        if sym != ' ':
            room.char_runs.append(CharRun(row=1, col=_START + i,
                                          symbols=(sym,), kind='ancient'))
    for i, sym in enumerate(_TAIL):
        room.char_runs.append(CharRun(row=1, col=tail_col + i,
                                      symbols=(sym,), kind='ancient'))
    room.rebuild_indexes()
    return room, tail_col


def _land(word, motion):
    """Where `motion` puts you, starting at the head of `word`."""
    room, _ = _row_with(word)
    player = Player()
    player.row, player.col = 1, _START
    apply_motion(player, motion, 1, room, count_given=False, game_h=36)
    return player.col


def _tail_col(word):
    """The column a motion that cleared the whole password arrives at."""
    return _row_with(word)[1]


# ── the pools keep their shapes ────────────────────────────────────────────

@pytest.mark.parametrize('word', dg._OV_SPLIT)
def test_a_split_password_is_takeable_only_by_the_big_word_motion(word):
    """THE ONE THAT MATTERS. `w` must stop short inside the token and `W` must
    run past it — that gap is the entire reason corridors 4, 5 and 7 can teach
    `dB`/`dE`/`dW` at all. Without it the small-word motion takes the same
    words, opens the same door, and the lesson is decorative."""
    assert _land(word, 'w') < _tail_col(word), (
        f'{word!r} has no punctuation that stops `w` — a `dw` would open its '
        f'door and the big-word lesson is lost')
    assert _land(word, 'W') == _tail_col(word), (
        f'{word!r} is broken by whitespace, so even `W` cannot take it whole')


@pytest.mark.parametrize('word', dg._OV_PLAIN + (dg._OV_FIRST,))
def test_a_plain_password_is_one_token_under_both_word_models(word):
    """The small-word corridors want a word the two models agree on, so the
    lesson rests on the guards and the direction rather than on a spelling
    trick the player has not been taught to read yet."""
    assert _land(word, 'w') == _land(word, 'W') == _tail_col(word)


@pytest.mark.parametrize('word', dg._OV_QUERY)
def test_a_query_password_leads_with_the_mark_dF_searches_for(word):
    """`dF?` cuts from the `?` up to the cursor, so the mark has to be at the
    START of the password — otherwise the cut that finds it takes only a tail."""
    assert word.startswith('?')
    assert '?' not in word[1:], f'{word!r} has a second ? for F to stop at first'


@pytest.mark.parametrize('phrase', dg._OV_PHRASE)
def test_a_phrase_password_cannot_be_taken_by_any_character_motion(phrase):
    """No character motion crosses a space, so a phrase is line-motion-only.
    This is what makes corridors 8, 9 and 10 teach `d0`/`d$`/`dd` instead of
    being solved with a `dW` the player already has."""
    assert ' ' in phrase
    assert _land(phrase, 'W') < _tail_col(phrase)


# ── the deal ───────────────────────────────────────────────────────────────

@pytest.mark.parametrize('seed', SEEDS)
def test_the_first_password_is_always_password(seed):
    """The model has to be legible the first time it is met. The puzzle is
    taking the word in one cut, not guessing which word — so corridor 1 spends
    none of the player's attention on the second question."""
    assert dg._ov_passwords(random.Random(seed))[1] == 'password'


@pytest.mark.parametrize('seed', SEEDS)
def test_no_password_is_used_twice(seed):
    """Two doors wanting the same words would let one corridor's cut open
    another's gate — and a player who noticed would be right to walk past
    every lesson in between."""
    dealt = dg._ov_passwords(random.Random(seed))
    assert len(set(dealt.values())) == len(dealt)


@pytest.mark.parametrize('seed', SEEDS)
def test_every_corridor_is_dealt_a_password_of_its_own_shape(seed):
    """The shuffle moves words WITHIN a shape and never across it. Dealing from
    one big pool would eventually hand a line-motion corridor a single token,
    which a character motion could take — the exact cheap substitution the
    doors exist to refuse."""
    dealt = dg._ov_passwords(random.Random(seed))
    assert set(dealt) == {1} | set(dg._OV_SHAPES)
    for corridor, pool in dg._OV_SHAPES.items():
        assert dealt[corridor] in pool


def test_the_seeds_do_not_all_deal_the_same_hand():
    """The point of shuffling. If the pools were ever narrowed to one entry
    each this would still pass corridor-by-corridor while the level became the
    same level every time."""
    hands = {tuple(sorted(dg._ov_passwords(random.Random(s)).items()))
             for s in SEEDS}
    assert len(hands) > 1


@pytest.mark.parametrize('corridor,pool', sorted(dg._OV_SHAPES.items()))
def test_every_pool_is_deep_enough_to_shuffle(corridor, pool):
    """A pool has to outnumber the corridors drawing from it, or the deal is
    forced and the seed stops meaning anything."""
    drawing = sum(1 for p in dg._OV_SHAPES.values() if p is pool)
    assert len(pool) > drawing
