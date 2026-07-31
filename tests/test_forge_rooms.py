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

"""The forge builds a `then` room.

Phase 4 put rooms in the schema but left the forge editing room 0 and
passing the rest through, so a multi-room level could be hand-written and
played but never AUTHORED. `draft.room_index` closes that: it is which room the
author is standing in, the forge renders that one, and `sync` folds the edited
room back into that slot and no other.

The property that matters most is ISOLATION — editing room 2 must not touch
room 1 — because the failure is silent: an author paints a second room and
discovers later that the first one lost its text.
"""
import pytest

from engine.world import CharRun
from sharing import draft as D
from sharing import format as F


def _draft(name='Two Rooms'):
    return D.new(name, 'tester')


def _paint(room, text, row=2, col=3):
    room.add_char_run(CharRun(row=row, col=col, symbols=tuple(text),
                              kind='ancient'))
    room.rebuild_indexes()
    return room


def _text_of(room):
    return ''.join(''.join(r['symbols']) for r in room.char_runs)


# ── the model ────────────────────────────────────────────────────────────────
def test_a_new_draft_is_one_room_and_you_are_in_it():
    d = _draft()
    assert len(d.level.rooms) == 1 and d.room_index == 0


def test_adding_a_room_returns_its_index_and_lengthens_the_descent():
    d = _draft()
    assert D.add_room(d) == 1
    assert len(d.level.rooms) == 2
    assert D.add_room(d) == 2


def test_a_new_room_opens_on_somewhere_to_stand():
    """Blank means the canvas `new()` opens on. An author made to carve a room
    out of solid rock before they can put anything in it would reasonably
    conclude the feature was unfinished."""
    d = _draft()
    D.add_room(d)
    room = d.build().rooms[1]
    assert room.cells[1][1] != room.cells[0][0]      # floor inside, wall at the rim
    assert room.spawn_pos == (1, 1)


def test_a_level_may_not_grow_past_the_room_cap():
    d = _draft()
    while len(d.level.rooms) < F.MAX_ROOMS:
        D.add_room(d)
    with pytest.raises(ValueError):
        D.add_room(d)


# ── building ─────────────────────────────────────────────────────────────────
def test_every_room_becomes_a_room_and_each_one_opens_the_next():
    d = _draft()
    D.add_room(d)
    D.add_room(d)
    dungeon = d.build()
    assert len(dungeon.rooms) == 3
    assert [getattr(r, 'advance_on_exit', False) for r in dungeon.rooms] \
        == [True, True, False]                        # the last one is the way out


# ── sync isolation: the whole point ──────────────────────────────────────────
def test_editing_a_later_room_leaves_the_first_alone():
    d = _draft()
    D.add_room(d)
    dungeon = d.build()

    d.room_index = 1
    D.sync(d, _paint(dungeon.rooms[1], 'second'))

    assert _text_of(d.level.rooms[1]) == 'second'
    assert d.level.char_runs == []                    # room 1 untouched


def test_editing_the_first_room_leaves_the_later_ones_alone():
    d = _draft()
    D.add_room(d)
    dungeon = d.build()
    d.room_index = 1
    D.sync(d, _paint(dungeon.rooms[1], 'second'))

    d.room_index = 0
    D.sync(d, _paint(d.build().rooms[0], 'first'))

    assert _text_of(d.level.rooms[0]) == 'first'
    assert _text_of(d.level.rooms[1]) == 'second'  # rode through untouched


def test_the_level_wide_claims_survive_editing_a_later_room():
    """Name, tape, vocabulary and metadata belong to the LEVEL. A sync of
    room 3 that reached them would quietly rewrite the level from a room."""
    d = _draft()
    D.add_room(d)
    d.level.solution = 'jjl'
    d.level.vocabulary = ['salt', 'stair']
    d.level.teaches = ['w']
    dungeon = d.build()

    d.room_index = 1
    D.sync(d, _paint(dungeon.rooms[1], 'second'))

    assert d.level.solution == 'jjl'
    assert d.level.vocabulary == ['salt', 'stair']
    assert d.level.teaches == ['w']
    assert d.level.name == 'Two Rooms'


# ── the file ─────────────────────────────────────────────────────────────────
def test_an_authored_room_round_trips_through_the_file():
    d = _draft()
    D.add_room(d)
    d.room_index = 1
    D.sync(d, _paint(d.build().rooms[1], 'second'))

    back = F.loads(F.dumps(d.level))
    assert len(back.rooms) == 2
    assert _text_of(back.then[0]) == 'second'


def test_which_room_is_open_is_not_saved_to_the_file():
    """It is a fact about the editing SESSION. A draft that reopened into
    room 4 because that is where its author left off would be a file that
    renders differently for the next reader."""
    d = _draft()
    D.add_room(d)
    d.room_index = 1
    assert 'room' not in F.dumps(d.level)


# ── removal ──────────────────────────────────────────────────────────────────
def test_the_first_room_cannot_be_removed():
    """It is the level's own geometry and where the player spawns. A level with
    no first room is not a level with one fewer room — it is nothing."""
    d = _draft()
    D.add_room(d)
    with pytest.raises(ValueError):
        D.delete_room(d, 0)


def test_removing_a_room_shortens_the_descent_and_renumbers_the_rest():
    """`where` names a room's place in the FILE, and everything after the
    hole just moved — left stale, the next parse error sends its author to a key
    that is not the one they are looking at."""
    d = _draft()
    D.add_room(d)
    D.add_room(d)
    d.room_index = 1
    D.sync(d, _paint(d.build().rooms[1], 'second'))

    D.delete_room(d, 1)
    assert len(d.level.rooms) == 2
    assert [h.where for h in d.level.then] == ['then[0].geometry']
    assert _text_of(d.level.rooms[1]) == ''        # the painted one is gone


def test_removing_the_room_you_are_standing_in_moves_you_somewhere_real():
    d = _draft()
    D.add_room(d)
    d.room_index = 1
    D.delete_room(d, 1)
    assert d.room_index < len(d.level.rooms)


def test_removing_a_room_that_is_not_there_is_refused():
    d = _draft()
    with pytest.raises(ValueError):
        D.delete_room(d, 3)
