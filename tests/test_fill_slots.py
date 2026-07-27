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

"""Slot references — a tape that names a grown word instead of spelling it.

A `fill` grows different words for every player, so a route that TYPES one of
them could not be written down: `cerune<Esc>` solves the author's roll and
nobody else's. `<fill0.3>` says which word instead of which letters, and the
build resolves it against the words that fill actually laid.

What the mechanism has to hold, and what is tested here:

  * the tape the player sees is real letters — resolution happens once, at
    build, so nothing downstream has to know slots exist;
  * it follows the roll: a different seed types a different word;
  * it costs the same anyway, which is why a fill a tape reads from must grow
    words of ONE length — par is a single number;
  * a reference that names nothing is refused, loudly, rather than typed into
    the buffer letter by letter.
"""
from __future__ import annotations

import pytest

from engine import tape as T
from engine.editor import slot_at
from sharing import format as F
from sharing.validate import validate


def _level(solution: str, **kw) -> F.Level:
    """A plain hall with a wall of four-letter words on rows 2..4."""
    rows, cols = 8, 30
    fills = kw.pop('fills', [F.Fill(region=(2, 2, 4, 25), pool='plain',
                                    length=(4, 4))])
    return F.Level(name='Slot Test', seed=7, rows=rows, cols=cols,
                   cells=['30W'] + [f'W{cols - 2}FW'] * (rows - 2) + ['30W'],
                   spawn=(1, 1), exit=(6, 1), fills=fills,
                   solution=solution, **kw)


#: Walk to the exit, then write a grown word there. Typing LAST is what makes
#: the route survive its own edit: an insert reflows the row it is on, and a
#: route that had to walk afterwards would be walking over shifted ground.
_ROUTE = 'jjjjji<fill0.0><Esc>'


# ── The record a build leaves ─────────────────────────────────────────────────

def test_a_build_writes_down_what_each_fill_grew():
    room = F.build(_level('l')).room
    assert len(room.fill_slots) == 1, 'one list of words per fill directive'
    assert room.fill_slots[0], 'the fill laid nothing'
    laid = [''.join(ru.symbols) for ru in room.char_runs]
    assert room.fill_slots[0] == laid, 'slots are the words in laying order'


def test_a_second_fill_gets_its_own_slots():
    room = F.build(_level('l', fills=[
        F.Fill(region=(2, 2, 2, 25), pool='plain', length=(4, 4)),
        F.Fill(region=(4, 2, 4, 25), pool='plain', length=(5, 5))])).room
    assert all(len(w) == 4 for w in room.fill_slots[0])
    assert all(len(w) == 5 for w in room.fill_slots[1])


# ── Resolution ────────────────────────────────────────────────────────────────

def test_the_tape_the_player_reads_is_letters_not_a_reference():
    """The karaoke sheet is matched keystroke by keystroke against what the
    player types, so a reference left in it would be four keys of `<fil`."""
    room = F.build(_level('i<fill0.2><Esc>')).room
    assert room.answer == f'i{room.fill_slots[0][2]}<Esc>'
    assert '<fill' not in room.answer


def test_the_reference_follows_the_roll():
    a = F.build(_level('i<fill0.0><Esc>'), seed=11).room
    b = F.build(_level('i<fill0.0><Esc>'), seed=12).room
    assert a.fill_slots != b.fill_slots, 'the two builds grew the same wall'
    assert a.answer != b.answer, 'the tape did not follow the words'
    assert a.answer == f'i{a.fill_slots[0][0]}<Esc>'
    assert T.keystroke_cost(a.answer) == T.keystroke_cost(b.answer), (
        'a fixed-length fill must cost the same however it rolled')


def test_a_fixed_length_fill_lays_the_SAME_WALL_for_every_player():
    """The quiet consequence of the single-length law, and the thing that makes
    a counted motion authorable at all. Word length is what decides where the
    next word starts, so fixing it fixes every position and the count itself:
    only the LETTERS are re-rolled. `3e` versus `4e` is therefore a decision an
    author makes once, looking at their own build, and it is right for
    everybody — which is why counts need no notation of their own.
    """
    def layout(length):
        f = [F.Fill(region=(2, 2, 4, 25), pool='plain', length=length)]
        return [[(ru.row, ru.col, len(ru.symbols))
                 for ru in sorted(F.build(_level('l', fills=f), seed=s).room.char_runs,
                                  key=lambda r: (r.row, r.col))]
                for s in (11, 12)]

    fixed_a, fixed_b = layout((4, 4))
    assert fixed_a == fixed_b and fixed_a, 'a fixed-length fill must not move'
    loose_a, loose_b = layout((3, 6))
    assert loose_a != loose_b, (
        'and a rolled-length one does move — which is the whole reason a tape '
        'may not read from it')


def test_a_reference_to_a_fill_that_is_not_there_is_refused():
    with pytest.raises(F.LevelFormatError, match='fill directive'):
        F.build(_level('i<fill3.0><Esc>'))


def test_a_reference_past_the_end_of_a_fill_is_refused():
    """A fill lays no word on stone and stops short of the right margin, so
    asking for the hundredth word of a short row is the ordinary mistake."""
    with pytest.raises(F.LevelFormatError, match='grew only'):
        F.build(_level('i<fill0.900><Esc>'))


def test_the_written_tape_survives_being_saved_again():
    """`from_room` must write back the reference, not the one word this build
    happened to roll — otherwise saving a level pins it to its author's luck."""
    room = F.build(_level('i<fill0.1><Esc>')).room
    again = F.from_room(room, 'Slot Test', fills=room.fills)
    assert again.solution == 'i<fill0.1><Esc>'


# ── The notation ──────────────────────────────────────────────────────────────

def test_a_reference_is_one_atom_to_a_reader():
    """Nothing may consume half of one — the same rule that makes `<Space>`
    safe to write with six glyphs."""
    assert T.token_at('i<fill0.12>x', 1) == '<fill0.12>'
    assert T.slot_refs('i<fill0.1><Esc>A<fill1.20>') == [(0, 1), (1, 20)]


def test_a_reference_reads_as_the_word_it_stands_for():
    """The karaoke sheet colours typed WORDS differently from keys, and a slot
    ref is standing in for a word, so all of it has to colour as one."""
    tape = 'i<fill0.1><Esc>'
    assert T.literal_spans(tape) == [(1, len(tape) - len(T.ESC))]


# ── Finding the slot in the first place ───────────────────────────────────────

def test_the_slot_under_the_cursor_can_be_asked_for():
    """`:fill?` answers it, because nobody counts to slot 23 by eye."""
    room = F.build(_level('l')).room
    for k, word in enumerate(room.fill_slots[0]):
        ru = sorted((r for r in room.char_runs), key=lambda r: (r.row, r.col))[k]
        assert slot_at(room, ru.row, ru.col) == (0, k, word)
        assert slot_at(room, ru.row, ru.col + 1)[1] == k, 'anywhere in the word'


def test_a_gap_between_words_is_inside_the_fill_but_on_nothing():
    room = F.build(_level('l')).room
    first = sorted(room.char_runs, key=lambda r: (r.row, r.col))[0]
    gap   = first.col + len(first.symbols)
    assert slot_at(room, first.row, gap) == (0, None, '')


def test_outside_every_fill_there_is_no_slot():
    room = F.build(_level('l')).room
    assert slot_at(room, 1, 1) is None, 'row 1 is outside the region'


# ── The law that keeps par one number ─────────────────────────────────────────

def _validated(solution=_ROUTE, *, pool='plain', length=(4, 4)):
    fills = [F.Fill(region=(2, 2, 4, 25), pool=pool, length=length)]
    return validate(_level(solution, fills=fills, requires=['insert'], teaches=[]))


def test_typing_a_longer_word_costs_more_keys():
    """Why the law below exists at all. Par is one number per level, and the
    length of the word the route types is part of it."""
    assert [_validated(length=(n, n)).par for n in (3, 4, 6)] == [9, 10, 12]


def test_a_tape_may_not_read_a_fill_that_rolls_its_length():
    rep = _validated(length=(3, 6))
    assert not rep.ok
    assert any('single length' in f for f in rep.errors)


def test_a_tape_may_not_read_a_saying():
    rep = _validated(pool='proverbs')
    assert not rep.ok
    assert any('saying pool' in f for f in rep.errors)


def test_a_fixed_length_fill_is_a_tape_a_level_may_ship_with():
    """The end of the argument: a route that types a grown word passes the
    stability check, which replays it against eight fresh arrangements and
    demands the same par from every one."""
    rep = _validated()
    assert rep.ok, rep.errors


def test_the_validator_replays_the_words_that_grew_not_the_reference():
    """The trap this feature sets: replaying the tape AS WRITTEN feeds
    `<fill0.0>` to the game as ten keypresses — `f` finds a character, `0`
    jumps to the margin — and the level reports a par for a route nobody could
    play. Every replay has to take the tape the build resolved."""
    assert _validated().par == 10
