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

"""The Pacifist — navigates past enemies without ever engaging them.

Personality defined in agents/bug_testers.md.
"""
from vimny.engine.world import Room, RoomType, CellType, Entity
from vimny.engine.player import Player
from vimny.engine.motion import apply_motion, move_player, _apply_find


def _bare_room(rows=7, cols=40):
    room = Room(room_type=RoomType.ENTRY, rows=rows, cols=cols)
    room.cells = [
        [CellType.FLOOR if (0 < r < rows - 1 and 0 < c < cols - 1) else CellType.WALL
         for c in range(cols)]
        for r in range(rows)
    ]
    room.spawn_pos    = (3, 1)
    room.exit_pos = (3, 38)
    room.fog_cells = set()
    room.rebuild_indexes()
    return room


# ── Goblin passability ────────────────────────────────────────────────────────

def test_goblin_does_not_block_l_motion():
    """Player can walk onto a goblin's cell — goblins are passable."""
    room = _bare_room()
    room.add_entity(Entity(kind='goblin', row=3, col=5, max_hp=1, ai='chase'))
    player = Player(row=3, col=4)

    moved = apply_motion(player, 'l', 1, room)

    assert moved
    assert player.col == 5, f"player should land on goblin cell 5, got {player.col}"


def test_goblin_does_not_block_dollar():
    """$ scan must pass over a goblin and reach the rightmost floor cell."""
    room = _bare_room()
    room.add_entity(Entity(kind='goblin', row=3, col=15, max_hp=1, ai='chase'))
    player = Player(row=3, col=1)

    apply_motion(player, '$', 1, room)

    assert player.col == 38, f"$ should pass goblin and reach col 38, got {player.col}"


# ── locked_door passability ───────────────────────────────────────────────────

def test_locked_door_blocks_l_motion():
    """locked_door entities make a cell impassable; l must stop before them."""
    room = _bare_room()
    room.add_entity(Entity(kind='locked_door', row=3, col=5))
    player = Player(row=3, col=4)

    moved = apply_motion(player, 'l', 1, room)

    assert not moved, "l must fail into locked_door"
    assert player.col == 4


def test_locked_door_blocks_dollar_scan():
    """$ must stop one cell before a locked_door."""
    room = _bare_room()
    room.add_entity(Entity(kind='locked_door', row=3, col=20))
    player = Player(row=3, col=1)

    apply_motion(player, '$', 1, room)

    assert player.col == 19, (
        f"$ should stop at col 19 (before locked_door at 20), got {player.col}"
    )


# ── shield passability ────────────────────────────────────────────────────────

def test_shield_blocks_l_motion():
    room = _bare_room()
    room.add_entity(Entity(kind='shield', row=3, col=5))
    player = Player(row=3, col=4)

    moved = apply_motion(player, 'l', 1, room)

    assert not moved, "l must fail into shield"
    assert player.col == 4


def test_shield_blocks_dollar_scan():
    room = _bare_room()
    room.add_entity(Entity(kind='shield', row=3, col=20))
    player = Player(row=3, col=1)

    apply_motion(player, '$', 1, room)

    assert player.col == 19, (
        f"$ should stop at col 19 (before shield at 20), got {player.col}"
    )


# ── boss_seal passability ─────────────────────────────────────────────────────

def test_boss_seal_blocks_l_motion():
    room = _bare_room()
    room.add_entity(Entity(kind='boss_seal', row=3, col=5))
    player = Player(row=3, col=4)

    moved = apply_motion(player, 'l', 1, room)

    assert not moved, "l must fail into boss_seal"
    assert player.col == 4


# ── count motion onto goblin ──────────────────────────────────────────────────

def test_count_l_onto_goblin_cell():
    """2l from col 1 with goblin at col 3 should pass through col 2 and land on col 3."""
    room = _bare_room()
    room.add_entity(Entity(kind='goblin', row=3, col=3, max_hp=1, ai='chase'))
    player = Player(row=3, col=1)

    apply_motion(player, 'l', 2, room)   # 1→2→3 (goblin passable)

    assert player.col == 3, f"player should land on goblin cell col 3, got {player.col}"


# ── fog passability ───────────────────────────────────────────────────────────

def test_fog_cell_blocks_l_motion():
    """l must not enter a fogged cell."""
    room = _bare_room()
    room.fog_cells = {(3, 5)}
    player = Player(row=3, col=4)

    moved = apply_motion(player, 'l', 1, room)

    assert not moved, "l must fail into fog cell"
    assert player.col == 4


def test_fog_cells_truncate_dollar_scan():
    """$ must stop at the last non-fog cell."""
    room = _bare_room()
    room.fog_cells = {(3, c) for c in range(15, 39)}
    player = Player(row=3, col=1)

    apply_motion(player, '$', 1, room)

    assert player.col == 14, (
        f"$ should stop at col 14 (first fogged is 15), got {player.col}"
    )


# ── wall boundaries ───────────────────────────────────────────────────────────

def test_move_player_into_wall_fails():
    room = _bare_room()
    player = Player(row=3, col=38)   # rightmost floor cell (col 39 is wall)

    result = move_player(player, 0, 1, room)

    assert not result, "move_player must fail into wall"
    assert player.col == 38


def test_move_player_into_top_wall_fails():
    room = _bare_room()
    player = Player(row=1, col=10)

    result = move_player(player, -1, 0, room)

    assert not result, "move_player must fail into top wall"
    assert player.row == 1


# ── f-scan stops at wall ──────────────────────────────────────────────────────

def test_f_scan_stops_at_wall_before_goblin():
    """f{g} must not jump past a wall cell even if a goblin is beyond it."""
    room = _bare_room()
    room.cells[3][15] = CellType.WALL
    room.add_entity(Entity(kind='goblin', row=3, col=20, max_hp=1, ai='chase'))
    player = Player(row=3, col=1)

    moved = _apply_find(player, 'f', 'g', room)

    assert not moved, "f should not find goblin beyond a wall"
    assert player.col == 1


def test_f_scan_stops_at_locked_door_before_goblin():
    """f{g} must not jump past a locked_door entity."""
    room = _bare_room()
    room.add_entity(Entity(kind='locked_door', row=3, col=15))
    room.add_entity(Entity(kind='goblin', row=3, col=20, max_hp=1, ai='chase'))
    player = Player(row=3, col=1)

    moved = _apply_find(player, 'f', 'g', room)

    assert not moved, "f should not find goblin beyond a locked_door"
    assert player.col == 1


def test_f_can_land_on_goblin_cell():
    """f{g} can land directly on a goblin's cell (no wall/locked_door between)."""
    room = _bare_room()
    room.add_entity(Entity(kind='goblin', row=3, col=10, max_hp=1, ai='chase'))
    player = Player(row=3, col=1)

    moved = _apply_find(player, 'f', 'g', room)

    assert moved
    assert player.col == 10
