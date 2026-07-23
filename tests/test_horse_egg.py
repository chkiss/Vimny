# Vimny — a Vim-teaching dungeon crawler.
# Copyright (C) 2026 Chas Kissick
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""The wizard's horse — a post-game Easter egg in the First Cave.

He appears only once the Warden Eternal is beaten, stands on a free floor cell
near the entry, blocks nothing, and the cursor passes through him (he is not a
puzzle piece). His glyph is the chess knight ♞ (→ 'h' on 2-wide terminals)."""
import pytest

from generation.dungeon_gen import build_dungeon_first_cave
from engine.world import CARET_TRANSPARENT
from main import _place_first_cave_horse
from tests import SEEDS


def _horse(room):
    hs = [e for e in room.entities if e.kind == 'horse']
    return hs[0] if hs else None


@pytest.mark.parametrize('seed', SEEDS)
def test_horse_stands_on_a_free_floor_cell(seed):
    room = build_dungeon_first_cave(seed).room
    _place_first_cave_horse(room)
    h = _horse(room)
    assert h is not None
    # a passable floor cell, not the spawn or the exit, with room to breathe
    assert room.is_passable(h.row, h.col)
    assert (h.row, h.col) != room.spawn_pos
    assert (h.row, h.col) != room.exit_pos
    assert abs(h.row - room.spawn_pos[0]) + abs(h.col - room.spawn_pos[1]) >= 2


@pytest.mark.parametrize('seed', SEEDS)
def test_horse_blocks_nothing_and_is_caret_transparent(seed):
    room = build_dungeon_first_cave(seed).room
    _place_first_cave_horse(room)
    h = _horse(room)
    # passable (the player walks onto him) and floor-like to ^/first-non-blank
    assert room.is_passable(h.row, h.col)
    assert 'horse' in CARET_TRANSPARENT


def test_placement_is_idempotent():
    room = build_dungeon_first_cave(SEEDS[0]).room
    _place_first_cave_horse(room)
    _place_first_cave_horse(room)
    assert sum(1 for e in room.entities if e.kind == 'horse') == 1


def test_horse_only_appears_post_game():
    # run_dungeon injects the horse only when warden_eternal is complete; the
    # builder itself never places one (so the fresh First Cave stays clean).
    room = build_dungeon_first_cave(SEEDS[0]).room
    assert _horse(room) is None
