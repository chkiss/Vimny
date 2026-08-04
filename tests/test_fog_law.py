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

"""The stone law, held over every room of every level.

What the eye cannot reach from spawn is fogged. That was the rule from the
beginning, but it was OPT-IN: each builder called `apply_stone_fog` for itself,
and a room that never called it — or that grew a sealed pocket after it did —
showed the player straight through the stone. The Grandmaster's arena did
exactly that: 52 cells behind the seal at column 48, the exit among them, in
plain sight from the spawn.

It is not opt-in any more. `_build_dungeon` holds every room to the law and
`format.build` does the same for downloaded levels, so the fog is DERIVED from
the walls rather than remembered alongside them. These tests are the proof, and
they are written over every level rather than over the one that was wrong,
because the bug was never really about the Sanctum.
"""
from __future__ import annotations

import pytest

import vimny.game as main
from vimny.content.levels import LEVELS
from vimny.engine.motion import stone_law, _FOG_BLOCK_KINDS
from vimny.sharing import format as F

SEED = 4242
SLUGS = [e['slug'] for e in LEVELS]


def _rooms(slug):
    """Every room of one level, built the way the game builds it."""
    return main._build_dungeon(slug, SEED).rooms


@pytest.mark.parametrize('slug', SLUGS)
def test_no_room_is_short_of_the_stone_law(slug):
    """The law is a FLOOR, not a setting.

    A room may fog more than the law — scripted fog is a superset, and about a
    third of the game uses it. What no room may do is fog less: a cell the eye
    cannot reach from spawn, drawn lit, is the player seeing through stone.
    """
    for i, room in enumerate(_rooms(slug)):
        if getattr(room, 'wrap_buffer', False):
            continue         # a buffer is read, not explored — see below
        missed = stone_law(room) - room.fog_cells
        assert not missed, (
            f'{slug}[{i}]: {len(missed)} cell(s) the eye cannot reach from '
            f'spawn are drawn lit, e.g. {sorted(missed)[:4]}')


def test_a_wrap_buffer_is_exempt_by_what_it_is():
    """The Wardenverse is one row of text with segment walls in it, so sight
    stops at the first of them and the law would fog 93% of the line.

    The exemption is derived from the room BEING a buffer, not from a list of
    names — a list is a thing that goes stale, and the next buffer anybody
    writes would not be on it.
    """
    verse = _rooms('warden_pathfinder')[1]
    assert verse.wrap_buffer
    assert verse.rows == 1
    assert stone_law(verse), 'the law would have had plenty to say here'
    assert not verse.fog_cells, 'and it was rightly not asked'


def test_the_grandmasters_arena_hides_its_exit_again():
    """The bug that started this: the arena's exit sits in a four-column pocket
    east of the seal, and was visible from the spawn across the room."""
    arena = _rooms('grandmasters_sanctum')[1]
    assert tuple(arena.exit_pos) in arena.fog_cells
    assert arena.auto_fog, 'and it lifts as the seal opens, not by hand'


def test_a_downloaded_level_gets_the_same_law():
    """One law, both materialisers — otherwise the forge would be building
    rooms that the game would never have shipped."""
    lvl = F.Level(name='Pocket', seed=7, rows=5, cols=12,
                  # a sealed pocket: the east three cells are walled off
                  cells=['12W', 'W7FWFFW', 'W7FW3F', 'W7FWFFW', '12W'],
                  spawn=(1, 1), exit=(2, 10))
    room = F.build(lvl).room
    assert (2, 10) in room.fog_cells, 'the exit pocket is behind stone'
    assert (1, 1) not in room.fog_cells, 'and the spawn is not'


# ── darkness said with DOORS, not with a list of cells ───────────────────────
#: Levels whose fog used to be a hand-laid list and is now derived from the
#: walls plus `opaque` doors (`dungeon_gen._doors_block_sight`, 2026-08-01).
#: Their old `_fog_unreachable` flood blocked at every closed door, so what it
#: laid was never a darkness at all — it was "everything behind a shut door",
#: a rule written down as its own answer. "Door" is `_FOG_BLOCK_KINDS`: the
#: plain and locked ones, and the seal doors and boss seals too, which is what
#: the two keeps turn on.
_DOOR_DARK = ('counting_crypts', 'goblin_gauntlet', 'lineheads',
              'wardens_keep', 'warden_surveyor', 'culling_ledger')


@pytest.mark.parametrize('slug', _DOOR_DARK)
def test_door_dark_levels_fog_exactly_the_law(slug):
    """DERIVED, not remembered. If one of these ever fogs more than the law
    again, its fog has stopped being a consequence of its doors — and it owes
    `tests/test_round_trip.py` a KNOWN_GAPS line, because the file cannot say
    darkness that is neither wall nor door."""
    for room in _rooms(slug):
        assert set(room.fog_cells) == stone_law(room), slug


@pytest.mark.parametrize('slug', _DOOR_DARK)
def test_their_doors_are_what_stops_the_eye(slug):
    """The rule itself. Without `opaque` the law would see straight through a
    door — a grille you can look through — and the crypt would be lit."""
    for room in _rooms(slug):
        doors = [e for e in room.entities
                 if e.kind in _FOG_BLOCK_KINDS]
        assert doors, f'{slug} has no doors to carry its darkness'
        assert all(e.opaque for e in doors), slug


@pytest.mark.parametrize('slug', _DOOR_DARK)
def test_the_darkness_is_real_and_not_a_no_op(slug):
    """Guards the guard: if the doors stopped hiding anything, the two tests
    above would both pass over an empty set and prove nothing."""
    for room in _rooms(slug):
        if room.fog_cells:
            return
    raise AssertionError(f'{slug} fogs nothing at all')


def test_mist_survives_the_re_reveal():
    """Two fogs wear one field. Stone fog is ignorance and looking cures it;
    mist is weather and standing beside it does not. Before the law was applied
    to level files, nothing auto-revealed and the distinction never came up."""
    from vimny.engine.motion import auto_fog_tick
    lvl = F.Level(name='Haze', seed=7, rows=5, cols=12,
                  cells=['12W', 'W10FW', 'W3F4M3FW', 'W10FW', '12W'],
                  spawn=(1, 1), exit=(3, 10))
    room = F.build(lvl).room
    assert room.mist_cells, 'the row of M is misted water'
    auto_fog_tick(room, 1, 1)                     # stand and look at it
    assert room.mist_cells <= room.fog_cells, 'the haze did not burn off'
