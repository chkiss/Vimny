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

"""A level of several chambers — `then`, and the door that joins them.

A level is a DESCENT: chambers are walked in order, each one's exit is the next
one's door, and there is no going back. That is the shape the Grandmaster's
Sanctum and the Warden Pathfinder already have in code, and this is it said in
a file instead.

CHAMBER is the word on purpose. `Room` is the engine's buffer class — the grid
of cells that 60 of 62 levels have exactly one of — and "hall" is the name of
six shipped levels, one of them a slug. A segment of a descent is a chamber.

What has to hold, and what is tested here:

  * the first chamber is the level's own `geometry` — a one-chamber level is
    untouched, in the file and in the build;
  * standing on a chamber's exit opens the NEXT chamber rather than winning the
    level, and only the last one's exit wins;
  * the tape is the level's, not a chamber's: one route walks them all, and par
    is the whole descent;
  * everything the validator says names the chamber it is about;
  * nothing that only holds a room — a crop, a fill's number, an editor's
    export — quietly forgets the chambers after the first.
"""
from __future__ import annotations

import pytest

from sharing import draft as DRAFT
from sharing import format as F
from sharing.replay import replay_tape
from sharing.validate import validate


def _chamber(rows=6, cols=20, spawn=(1, 1), exit=(4, 1), **kw) -> F.Chamber:
    return F.Chamber(rows=rows, cols=cols,
                     cells=[f'{cols}W'] + [f'W{cols - 2}FW'] * (rows - 2)
                           + [f'{cols}W'],
                     spawn=spawn, exit=exit, **kw)


def _level(solution: str, chambers=1, **kw) -> F.Level:
    """A level of plain chambers. Chamber 0 is crossed downward, the rest
    rightward, so a route through two cannot be mistaken for a route through
    one."""
    first = _chamber()
    rest  = [_chamber(spawn=(1, 1), exit=(1, 5), where=f'then[{i}].geometry')
             for i in range(chambers - 1)]
    return F.Level(name='Chamber Test', seed=7,
                   rows=first.rows, cols=first.cols, cells=first.cells,
                   spawn=first.spawn, exit=first.exit,
                   then=rest, solution=solution, **kw)


#: Down the first chamber to its door, then right along the second to the way out.
_ROUTE = 'jjj llll'


# ── The shape of the thing ────────────────────────────────────────────────────

def test_a_level_with_no_then_is_one_chamber_and_reads_as_it_always_did():
    lvl = _level('l')
    assert len(lvl.chambers) == 1
    assert 'then' not in F.dumps(lvl), 'a one-chamber level carries no machinery'
    assert len(F.build(lvl).rooms) == 1


def test_the_first_chamber_is_the_levels_own_geometry():
    """Not `then[0]`, and not a `rooms[0]` the author has to write: the common
    level is one chamber, and it must not pay for the rare one."""
    lvl = _level('l', chambers=2)
    assert lvl.chambers[0].cells == lvl.cells
    assert lvl.chambers[0].where == 'geometry'
    assert lvl.chambers[1].where == 'then[0].geometry'


def test_every_chamber_becomes_a_room_in_walking_order():
    d = F.build(_level('l', chambers=3))
    assert len(d.rooms) == 3
    assert d.current_room == 0
    assert [r.exit_pos for r in d.rooms] == [(4, 1), (1, 5), (1, 5)]


def test_the_chambers_survive_a_round_trip_through_the_file():
    lvl  = _level('l', chambers=2)
    back = F.loads(F.dumps(lvl))
    assert len(back.then) == 1
    assert back.then[0].cells == lvl.then[0].cells
    assert back.then[0].exit == (1, 5)
    assert back.then[0].where == 'then[0].geometry', 'it must know where it lives'


# ── The door ──────────────────────────────────────────────────────────────────

def test_every_chamber_but_the_last_is_a_door():
    rooms = F.build(_level('l', chambers=3)).rooms
    assert [getattr(r, 'advance_on_exit', False) for r in rooms] == [True, True, False]


def test_the_exit_of_a_middle_chamber_does_not_win_the_level():
    """The whole point of the flag. A chamber's exit entity would otherwise end
    the level on the first door, which is a two-chamber level that is really
    one."""
    lvl = _level('jjj', chambers=2, requires=[], teaches=[])
    rep = validate(lvl)
    assert not rep.ok
    assert any('reach the exit' in e or 'reaching the exit' in e
               for e in rep.errors), rep.errors


def test_a_route_through_both_chambers_wins_and_par_is_the_whole_descent():
    rep = validate(_level(_ROUTE, chambers=2, requires=[], teaches=[]))
    assert rep.ok, rep.errors
    assert rep.par == 7, 'three down the first chamber, four along the second'


def test_the_karaoke_tape_belongs_to_the_level_not_to_a_chamber():
    """One route walks every chamber, so the tape is written once, on the room
    the player starts in, and travels through the doors with them."""
    rooms = F.build(_level(_ROUTE, chambers=2)).rooms
    assert rooms[0].answer == _ROUTE
    assert not rooms[1].answer, 'a second tape would restart the karaoke sheet'


# ── Fills are numbered across the level ───────────────────────────────────────

def _filled(solution: str) -> F.Level:
    """Two chambers, one fill each: the first grows four-letter words, the
    second five."""
    lvl = _level(solution, chambers=2, requires=['insert'], teaches=[])
    lvl.fills = [F.Fill(region=(1, 2, 3, 17), pool='plain', length=(4, 4))]
    lvl.then[0].fills = [F.Fill(region=(2, 2, 3, 17), pool='plain', length=(5, 5))]
    return lvl


def test_a_tape_counts_fills_across_the_chambers():
    """`<fill1.0>` is the level's SECOND fill, wherever it stands. Numbering
    per chamber would make one reference mean two different words."""
    d = F.build(_filled('l'))
    assert all(len(w) == 4 for w in d.rooms[0].fill_slots[0])
    assert all(len(w) == 5 for w in d.rooms[1].fill_slots[0])
    room = F.build(_filled('i<fill1.0><Esc>')).rooms[0]
    assert room.answer == f'i{d.rooms[1].fill_slots[0][0]}<Esc>'


def test_a_chamber_reports_its_own_fills_by_the_levels_numbering():
    """What `:fill?` answers with. A chamber that counted from zero would hand
    the author a reference naming a different fill in the file."""
    from engine.editor import slot_at
    d = F.build(_filled('l'))
    assert d.rooms[0].fill_index0 == 0
    assert d.rooms[1].fill_index0 == 1
    ru = sorted(d.rooms[1].char_runs, key=lambda r: (r.row, r.col))[0]
    assert slot_at(d.rooms[1], ru.row, ru.col)[0] == 1


def test_a_reference_past_the_levels_last_fill_is_refused():
    with pytest.raises(F.LevelFormatError, match='fill directive'):
        F.build(_filled('i<fill2.0><Esc>'))


def test_two_chambers_do_not_grow_the_same_wall_twice():
    """One rng, drawn on chamber by chamber: a second one seeded alike would
    read as a copy of the first rather than another room in the same dungeon."""
    lvl = _level('l', chambers=2)
    lvl.fills = [F.Fill(region=(1, 2, 3, 17), pool='plain', length=(4, 4))]
    lvl.then[0].fills = [F.Fill(region=(1, 2, 3, 17), pool='plain', length=(4, 4))]
    d = F.build(lvl)
    assert d.rooms[0].fill_slots[0] != d.rooms[1].fill_slots[0]


# ── Every message names its chamber ───────────────────────────────────────────

def test_a_broken_later_chamber_is_named_by_where_it_lives():
    lvl = _level('l', chambers=2)
    lvl.then[0].spawn = (99, 99)
    rep = validate(lvl)
    assert not rep.ok
    assert any('then[0].geometry.spawn' in e for e in rep.errors), rep.errors


def test_a_bad_cell_code_in_a_later_chamber_names_that_chamber():
    lvl = _level('l', chambers=2)
    lvl.then[0].cells = list(lvl.then[0].cells)
    lvl.then[0].cells[1] = 'W18ZW'
    rep = validate(lvl)
    assert any('then[0].geometry.cells[1]' in e for e in rep.errors), rep.errors


def test_a_chamber_may_not_carry_a_tape_of_its_own():
    """There is one route through a level, so there is one `solution`, and it
    lives on the level. A second one inside a chamber would be a route with no
    beginning."""
    data = {'schema': F.SCHEMA, 'name': 'X',
            'geometry': {'rows': 3, 'cols': 3, 'cells': ['3W'] * 3},
            'then': [{'geometry': {'rows': 3, 'cols': 3, 'cells': ['3W'] * 3},
                      'solution': 'l'}]}
    with pytest.raises(F.LevelFormatError, match='then\\[0\\]'):
        F.parse(data)


def test_a_level_may_not_be_an_endless_corridor_of_chambers():
    data = {'schema': F.SCHEMA, 'name': 'X',
            'geometry': {'rows': 3, 'cols': 3, 'cells': ['3W'] * 3},
            'then': [{'geometry': {'rows': 3, 'cols': 3, 'cells': ['3W'] * 3}}]
                    * (F.MAX_CHAMBERS + 1)}
    with pytest.raises(F.LevelFormatError, match='at most'):
        F.parse(data)


# ── Nothing that holds one room may forget the rest ───────────────────────────

def test_each_chamber_is_cropped_on_its_own_margins():
    """Separate grids that only ever share a level: a chamber padded out to its
    neighbour's width would be stone added for tidiness alone."""
    lvl = _level('l', chambers=2)
    lvl.then[0] = _chamber(rows=6, cols=40, spawn=(1, 1), exit=(1, 5),
                           where='then[0].geometry')
    lvl.then[0].cells = ['40W', 'W9F30W'] + ['40W'] * 4
    tight = F.crop(lvl)
    assert tight.rows == 6 and tight.cols == 20, 'the first was already tight'
    assert (tight.then[0].rows, tight.then[0].cols) == (3, 11), (
        'the second carried 29 columns and three rows of stone')


def test_the_forge_hands_back_the_chambers_it_never_opened():
    """The forge edits the chamber the author is standing in, which is always
    the first. Saving must not be an edit to a room they never saw."""
    d = DRAFT.new('Chamber Draft')
    d.level.then = [_chamber(where='then[0].geometry')]
    room = d.build().room
    DRAFT.sync(d, room)
    assert len(d.level.then) == 1, 'saving the draft dropped a chamber'
    assert d.level.then[0].exit == (4, 1)


def test_from_room_is_told_about_the_chambers_or_it_writes_none():
    """The sharp edge, named where the caller meets it: `from_room` captures ONE
    room, so a caller that forgets `then` saves a two-chamber level as one."""
    room = F.build(_level('l', chambers=2)).room
    assert F.from_room(room, 'X').then == []
    assert len(F.from_room(room, 'X', then=[_chamber()]).then) == 1
