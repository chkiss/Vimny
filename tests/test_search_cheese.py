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

"""Cheese probe for search-across-entities (search_glyph_entities is ON for every
room since 2026-07-21). A `/{letter}` search LANDS the cursor on a matching
entity, CROSSING WALLS to get there. The danger: if a creature sits in a region
that can reach the exit while the SPAWN cannot (a sealed level), then `/{letter}`
teleports the player into the winning region — a par-breaking shortcut the
answer-path audit (which only replays the canonical tape) never sees.

The invariant this pins: on any room whose exit is NOT walkable from the spawn at
start (i.e. gated/sealed), NO searchable entity may sit in a region from which
the exit IS walkable. If it did, `/{entity}` would skip the gate.
"""
from collections import deque

import pytest

import vimny.generation.dungeon_gen as dg
from vimny.content.levels import LEVELS, known_commands
from vimny.engine.world import CellType, entity_letter
from tests import SEEDS


def _reach(room, start):
    """Cells walkable from `start` (4-connected over passable cells)."""
    seen = {start}
    q = deque([start])
    while q:
        r, c = q.popleft()
        for dr, dc in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nr, nc = r + dr, c + dc
            if (0 <= nr < room.rows and 0 <= nc < room.cols
                    and (nr, nc) not in seen and room.is_passable(nr, nc)):
                seen.add((nr, nc))
                q.append((nr, nc))
    return seen


_SEARCH_LEVELS = [lv['slug'] for lv in LEVELS
                  if not lv.get('admin_only') and '/' in known_commands(lv['slug'])]


@pytest.mark.parametrize('slug', _SEARCH_LEVELS)
@pytest.mark.parametrize('seed', SEEDS)
def test_no_entity_search_jump_skips_a_sealed_exit(slug, seed):
    fn = getattr(dg, f'build_dungeon_{slug}', None)
    if fn is None:
        pytest.skip(f'{slug} has no builder yet')
    d = fn(seed)
    for room in d.rooms:
        exit_pos = getattr(room, 'exit_pos', None)
        spawn = getattr(room, 'spawn_pos', None)
        if not exit_pos or not spawn:
            continue
        from_spawn = _reach(room, spawn)
        if exit_pos in from_spawn:
            continue                                   # exit already open — nothing to skip
        # exit is SEALED from the spawn: no searchable entity may open a back door
        for e in room.entities:
            if not e.alive or entity_letter(e) is None or e.kind == 'exit':
                continue
            if (e.row, e.col) in room.fog_cells:       # fogged = unsearchable
                continue
            landed = _reach(room, (e.row, e.col))
            assert exit_pos not in landed, (
                f'{slug}: /{entity_letter(e)} lands on a {e.kind} at '
                f'({e.row},{e.col}) whose region reaches the sealed exit '
                f'{exit_pos} — a search-jump cheese.')
