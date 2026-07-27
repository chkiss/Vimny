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

"""Test suite package. Shared constants live here so they can't drift per-file."""
from functools import lru_cache

# Canonical seed set for parametrized dungeon tests (reachability, par, budget,
# command necessity, void safety) — see docs/ARCHITECTURE.md → Test conventions.
SEEDS = [1, 42, 999, 12345, 2**20 + 7]


@lru_cache(maxsize=None)
def cached_dungeon(builder_name: str, seed: int):
    """ONE shared build per (builder, seed), for READ-ONLY property tests.

    Building a dungeon can be expensive (the Screen Vault's answer Dijkstra runs
    seconds), and the property tests — par match, budget formula, structure,
    answer cost — all read the same build. NEVER mutate a cached room (no
    apply_motion / editing / kill_entity); a test that simulates play must call
    its builder directly for a private copy."""
    import generation.dungeon_gen as _dg
    return getattr(_dg, builder_name)(seed)


def cached_room(builder_name: str, seed: int):
    """First room of the shared build — see cached_dungeon's READ-ONLY rule."""
    return cached_dungeon(builder_name, seed).rooms[0]


def door_targets(room):
    """The chassis bolts' target words, in gate order.

    The seventeen chassis levels lay a row of bolts and then a FINAL SEAL that
    requires all of them; the final seal reads no text of its own, so it is the
    one seal with an empty `match` and it drops out here. Tests want the doors,
    and they want them at the index the level built them at."""
    return [s.match for s in room.seals if s.match]
