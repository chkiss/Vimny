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

"""Verify key/lock balance and pre-assignment for playable levels.

Rules enforced here:
  1. chest_key count == locked_door count — the FIRST FIVE levels only. Later
     levels source their keys elsewhere (a Warden drops one when he falls, a
     floor_key lies in the open, a `drops` field pays one out), so counting
     chests against locks says nothing true about them.
  2. No `chest_random` — EVERY level in the curriculum. Loot must be assigned at
     generation, because a chest that rolls its reward rolls the level's intent
     with it: the Stair Rail's undercroft chest was meant to pay out a relic
     scroll and did so one time in three, giving a useless key the rest.

The dummy dungeon is an admin sandbox and is intentionally excluded.
"""
import pytest
import vimny.generation.dungeon_gen as dg
from vimny.generation.dungeon_gen import (
    build_dungeon_first_cave, build_dungeon_line_halls, build_dungeon_counting_crypts,
    build_dungeon_rune_halls, build_dungeon_character_cataracts,
)

from vimny.content.levels import LEVELS
from tests import SEEDS

_BUILDERS = {
    0: build_dungeon_first_cave,
    1: build_dungeon_line_halls,
    2: build_dungeon_counting_crypts,
    3: build_dungeon_rune_halls,
    4: build_dungeon_character_cataracts,
}

#: Every shipped slug with a builder, minus the admin sandbox. Derived from
#: LEVELS rather than listed, so a level added tomorrow is checked tomorrow —
#: this file used to name five builders and quietly cover nothing else.
_ALL_SLUGS = [lv['slug'] for lv in LEVELS
              if lv['slug'] != 'dummy'
              and hasattr(dg, f"build_dungeon_{lv['slug']}")]


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
@pytest.mark.parametrize('slug', _ALL_SLUGS)
def test_no_chest_gambles_its_loot(slug, seed):
    """The whole curriculum, every room — not the first five levels."""
    rooms   = getattr(dg, f'build_dungeon_{slug}')(seed).rooms
    unnamed = [e for room in rooms for e in room.entities
               if e.kind == 'chest_random' and e.alive]
    assert not unnamed, (
        f'{slug} seed {seed}: {len(unnamed)} chest(s) that roll their loot — '
        'use chest_key or chest_scroll so the reward is the one you designed'
    )


def test_the_sweep_actually_reaches_the_whole_curriculum():
    """The bug this file had was SILENT: it named five builders and read as a
    rule about the game. Assert the coverage, so shrinking it has to be
    deliberate."""
    assert len(_ALL_SLUGS) > 30
    assert 'stair_rail' in _ALL_SLUGS and 'dummy' not in _ALL_SLUGS
