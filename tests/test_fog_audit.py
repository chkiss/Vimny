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

"""The stone-law fog audit (user law, 2026-07-17): what stone hides from the
spawn, fog must hide too. Vision is walls-only (_vision_flood) — a door is a
grille you can see through, and water is open sight (the Seekers' key behind
its door, the Binder's word across the water, both stay visible). Every
builder is auto-discovered; a new level is audited the day it lands."""
import re

import pytest

import generation.dungeon_gen as dg
from engine.motion import _vision_flood, _FOGGABLE_CELLS
from tests import SEEDS, cached_room

# Levels with SCRIPTED fog choreography that manages its own reveals — the
# stone law is enforced by their own tests / mechanics, not this audit.
_SCRIPTED_FOG = {
    'build_dungeon_warden_pathfinder',   # two-room boss; arena fog scripted
    'build_dungeon_warden_manifold',     # ward-machine fog, re-laid per round
    'build_dungeon_warden_scrivener',    # hall/pocket fog lifted per beat
    'build_dungeon_dummy',               # admin sandbox
}

# Levels whose DESIGN enters walk-unreachable areas by jump or search —
# fogging them breaks their tuned physics (fog = impassable, so } / ( ) / }
# landings shift and searches into the area die). Documented, not fixed:
# a redesign under the stone law would be a level rework, not a fog patch.
_JUMP_ENTRY_DESIGN = {
    'build_dungeon_operators_vault',     # own fog choreography (corridor-by-
                                         # corridor reveal); the oubliette pits
                                         # are deliberately unfogged so the dd
                                         # fall can land (west-face water makes
                                         # the col-1 pits visible pools)
    'build_dungeon_sentence_corridor',   # ( ) jump-entry pockets
    # waypoint_sanctum left the list 2026-07-18: the waterworks conversion
    # (misted water seals/pocket/vault boxes) made every hall visible.
}
_SCRIPTED_FOG |= _JUMP_ENTRY_DESIGN


def _builders():
    return sorted(n for n in dir(dg)
                  if re.match(r'^build_dungeon_\w+$', n)
                  and n not in _SCRIPTED_FOG)


@pytest.mark.parametrize("name", _builders())
@pytest.mark.parametrize("seed", SEEDS)
def test_stone_hidden_cells_start_fogged(name, seed):
    try:
        room = cached_room(name, seed)
    except TypeError:
        pytest.skip('builder needs extra args')
    foggable = {(r, c) for r in range(room.rows) for c in range(room.cols)
                if room.cells[r][c] in _FOGGABLE_CELLS}
    visible = _vision_flood(room, *room.spawn_pos)
    missing = foggable - visible - room.fog_cells
    assert not missing, (
        f'{name} seed={seed}: {len(missing)} stone-hidden cells are not '
        f'fogged, e.g. {sorted(missing)[:5]}')
