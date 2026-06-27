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

"""Prove every hjkl direction is required to complete the First Cave."""
from collections import deque
import pytest
from generation.dungeon_gen import build_dungeon_first_cave

from tests import SEEDS
DELTA = {'h': (0, -1), 'j': (1, 0), 'k': (-1, 0), 'l': (0, 1)}
FIRST_CAVE_COMMANDS = set('hjkl')


def can_reach(room, entry, goal, allowed_keys):
    moves = [DELTA[k] for k in allowed_keys]
    void = {
        (ru.row, ru.col + i)
        for ru in room.char_runs if ru.kind == 'void'
        for i in range(len(ru.symbols))
    }
    seen = {entry}
    q = deque([entry])
    while q:
        pos = q.popleft()
        if pos == goal:
            return True
        r, c = pos
        for dr, dc in moves:
            nb = (r + dr, c + dc)
            if nb not in seen and room.is_passable(*nb) and nb not in void:
                seen.add(nb)
                q.append(nb)
    return False


@pytest.mark.parametrize("seed", SEEDS)
def test_exit_is_reachable(seed):
    d = build_dungeon_first_cave(seed)
    room = d.room
    assert can_reach(room, room.spawn_pos, room.exit_pos, FIRST_CAVE_COMMANDS), \
        f"seed={seed}: exit unreachable with full hjkl"


@pytest.mark.parametrize("seed,omit", [(s, c) for s in SEEDS for c in sorted(FIRST_CAVE_COMMANDS)])
def test_each_command_is_necessary(seed, omit):
    d = build_dungeon_first_cave(seed)
    room = d.room
    restricted = FIRST_CAVE_COMMANDS - {omit}
    assert not can_reach(room, room.spawn_pos, room.exit_pos, restricted), \
        f"seed={seed}: exit reachable without '{omit}' — command is not required"
