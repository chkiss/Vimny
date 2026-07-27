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

"""Verify key/lock balance and pre-assignment for all playable levels.

Rules enforced here:
  1. chest_key count == locked_door count  (every lock has exactly one key)
  2. No plain 'chest_random' entities             (loot must be pre-assigned at generation)

The dummy dungeon is an admin sandbox and is intentionally excluded.
"""
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


def _room(level, seed):
    return _BUILDERS[level](seed).rooms[0]


@pytest.mark.parametrize('seed', SEEDS)
@pytest.mark.parametrize('level', sorted(_BUILDERS))
def test_chest_keys_match_locked_doors(level, seed):
    room    = _room(level, seed)
    n_keys  = sum(1 for e in room.entities if e.kind == 'chest_key'   and e.alive)
    n_locks = sum(1 for e in room.entities if e.kind == 'locked_door' and e.alive)
    assert n_keys == n_locks, (
        f'level {level} seed {seed}: {n_keys} chest_key(s) vs {n_locks} locked_door(s)'
    )


@pytest.mark.parametrize('seed', SEEDS)
@pytest.mark.parametrize('level', sorted(_BUILDERS))
def test_no_untyped_chests(level, seed):
    room    = _room(level, seed)
    unnamed = [e for e in room.entities if e.kind == 'chest_random' and e.alive]
    assert not unnamed, (
        f'level {level} seed {seed}: {len(unnamed)} untyped chest(s) — '
        'use chest_key or chest_scroll instead'
    )
