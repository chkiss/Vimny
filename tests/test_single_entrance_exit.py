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

"""All levels must have exactly one entrance and one exit entity."""
import pytest
from generation.dungeon_gen import (
    build_dungeon_first_cave, build_dungeon_line_halls, build_dungeon_counting_crypts,
    build_dungeon_rune_halls, build_dungeon_character_cataracts,
)

from tests import SEEDS

_BUILDERS = {
    0: build_dungeon_first_cave,
    1: build_dungeon_line_halls,
    2: build_dungeon_counting_crypts,
    3: build_dungeon_rune_halls,
    4: build_dungeon_character_cataracts,
}


@pytest.mark.parametrize("level", sorted(_BUILDERS))
@pytest.mark.parametrize("seed", SEEDS)
def test_exactly_one_exit_entity(level, seed):
    room = _BUILDERS[level](seed).room
    exits = [e for e in room.entities if e.kind == 'exit']
    assert len(exits) == 1, (
        f"level={level} seed={seed}: expected 1 exit entity, got {len(exits)} "
        f"at {[(e.row, e.col) for e in exits]}"
    )


@pytest.mark.parametrize("level", sorted(_BUILDERS))
@pytest.mark.parametrize("seed", SEEDS)
def test_exit_entity_matches_exit_pos(level, seed):
    room = _BUILDERS[level](seed).room
    exits = [e for e in room.entities if e.kind == 'exit']
    assert len(exits) >= 1, f"level={level} seed={seed}: no exit entity"
    assert (exits[0].row, exits[0].col) == room.exit_pos, (
        f"level={level} seed={seed}: exit entity at ({exits[0].row},{exits[0].col}) "
        f"!= exit_pos {room.exit_pos}"
    )


@pytest.mark.parametrize("level", sorted(_BUILDERS))
@pytest.mark.parametrize("seed", SEEDS)
def test_entry_is_passable(level, seed):
    room = _BUILDERS[level](seed).room
    r, c = room.spawn_pos
    assert room.is_passable(r, c), (
        f"level={level} seed={seed}: entry {room.spawn_pos} is not passable"
    )
