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

"""The Berserker — kills everything before moving anywhere.

Personality defined in agents/bug_testers.md.
"""
from vimny.engine.world import Room, RoomType, CellType, Entity
from vimny.engine.player import Player
from main import (
    _enemy_tick,
    _remove_warden_shields, _on_kill, _spawn_goblin,
)

ROWS, COLS = 7, 30


def _bare_room():
    room = Room(room_type=RoomType.ENTRY, rows=ROWS, cols=COLS)
    room.cells = [
        [CellType.FLOOR if (0 < r < ROWS - 1 and 0 < c < COLS - 1) else CellType.WALL
         for c in range(COLS)]
        for r in range(ROWS)
    ]
    room.spawn_pos    = (3, 1)
    room.exit_pos = (3, 28)
    room.fog_cells = set()
    room.rebuild_indexes()
    return room


def _combat_room(rows=9, cols=40):
    room = Room(room_type=RoomType.COMBAT, rows=rows, cols=cols)
    room.cells = [
        [CellType.FLOOR if (0 < r < rows - 1 and 0 < c < cols - 1) else CellType.WALL
         for c in range(cols)]
        for r in range(rows)
    ]
    room.spawn_pos    = (4, 1)
    room.exit_pos = (4, 38)
    room.fog_cells = set()
    room.rebuild_indexes()
    return room


# ── Multi-hit goblin ──────────────────────────────────────────────────────────

def test_goblin_survives_first_hit_dies_on_second():
    """A goblin with hp=2 must survive one hit and die on the second."""
    room = _bare_room()
    goblin = Entity(kind='goblin', row=3, col=5, hp=2, max_hp=2, ai='chase')
    room.add_entity(goblin)

    goblin.hp -= 1
    assert goblin.hp == 1 and goblin.alive, "goblin must survive first hit"

    goblin.hp -= 1
    assert goblin.hp == 0
    room.kill_entity(goblin)
    assert not goblin.alive
    assert room.entity_at(3, 5) is None, "dead goblin must be removed from entity_map"


# ── Dead entities do not attack ───────────────────────────────────────────────

def test_dead_goblin_does_not_attack_via_enemy_tick():
    """_enemy_tick must skip dead entities and never move/attack with them."""
    room = _bare_room()
    player = Player(row=3, col=1)
    goblin = Entity(kind='goblin', row=3, col=2, hp=1, max_hp=1, ai='chase',
                    ai_speed=1)
    room.add_entity(goblin)
    room.kill_entity(goblin)   # kill before tick

    before_hp = player.hp
    _enemy_tick(room, player)

    assert player.hp == before_hp, (
        "_enemy_tick must not deal damage via dead entities"
    )


# ── _on_kill key drops ────────────────────────────────────────────────────────

def test_on_kill_warden_drops_floor_key_at_goblin_gauntlet():
    """_on_kill for a warden at the Goblin Gauntlet (non-boss) must drop a floor_key.

    The game loop kills the entity before calling _on_kill so the cell is free
    for _drop_key to place the floor_key.
    """
    room = _bare_room()
    warden = Entity(kind='warden', row=3, col=20, max_hp=5, ai='')
    room.add_entity(warden)
    player = Player(row=3, col=5)

    room.kill_entity(warden)   # mirrors game loop: kill before _on_kill
    msg = _on_kill(warden, player, room, level='goblin_gauntlet')

    key = room.entity_at(warden.row, warden.col)
    assert key is not None, "floor_key should be placed at warden position"
    assert key.kind == 'floor_key'
    assert 'Warden' in msg or 'key' in msg.lower()


def test_on_kill_warden_drops_key_at_wardens_keep():
    """Every Warden — including The Warden's Keep boss — drops a floor_key to its
    keep's locked exit door (the seal no longer auto-crumbles; the key is the way)."""
    room = _bare_room()
    warden = Entity(kind='warden', row=3, col=20, max_hp=5, ai='')
    room.add_entity(warden)
    player = Player(row=3, col=5)

    room.kill_entity(warden)   # mirrors game loop
    msg = _on_kill(warden, player, room, level='wardens_keep')

    key = room.entity_at(warden.row, warden.col)
    assert key is not None and key.kind == 'floor_key', "boss warden must drop a key"
    assert 'key' in msg.lower()


def test_last_goblin_at_goblin_gauntlet_drops_key():
    """At the Goblin Gauntlet, killing the last goblin must drop a floor_key; earlier kills do not."""
    room = _bare_room()
    player = Player(row=3, col=1)
    g1 = Entity(kind='goblin', row=3, col=5, max_hp=1, ai='chase')
    g2 = Entity(kind='goblin', row=3, col=8, max_hp=1, ai='chase')
    room.add_entity(g1)
    room.add_entity(g2)

    # Kill first goblin — key must NOT drop yet
    room.kill_entity(g1)
    msg1 = _on_kill(g1, player, room, level='goblin_gauntlet')
    assert not any(e.alive and e.kind == 'floor_key' for e in room.entities), (
        "key must not drop while second goblin still lives"
    )

    # Kill second goblin — key must drop now
    room.kill_entity(g2)
    msg2 = _on_kill(g2, player, room, level='goblin_gauntlet')
    assert any(e.alive and e.kind == 'floor_key' for e in room.entities), (
        "floor_key must drop after the last goblin is killed at the Goblin Gauntlet"
    )


# ── Warden summon uid ─────────────────────────────────────────────────────────

def test_warden_spawned_goblins_carry_correct_summoner_uid():
    """_enemy_tick-spawned goblins must have summoner_uid == warden.uid."""
    room = _combat_room()
    player = Player(row=4, col=1)
    warden = Entity(kind='warden', row=4, col=4, max_hp=5, ai='', summon_timer=0)
    room.add_entity(warden)

    before = len(room.entities)
    _enemy_tick(room, player)

    new_goblins = [
        e for e in room.entities
        if e.kind == 'goblin' and e.alive
    ]
    assert len(new_goblins) > 0, "warden should have summoned at least one goblin"
    for g in new_goblins:
        assert g.summoner_uid == warden.uid, (
            f"spawned goblin must have summoner_uid={warden.uid}, got {g.summoner_uid}"
        )


# ── enemy_tick does not directly deal damage ─────────────────────────────────

def test_enemy_tick_does_not_reduce_player_hp():
    """_enemy_tick moves enemies; actual damage is handled by the game loop."""
    room = _bare_room()
    player = Player(row=3, col=1)
    goblin = Entity(kind='goblin', row=3, col=2, max_hp=1, ai='chase', ai_speed=1)
    room.add_entity(goblin)

    before_hp = player.hp
    _enemy_tick(room, player)

    assert player.hp == before_hp, (
        "_enemy_tick must not modify player.hp; damage belongs to the game loop"
    )


# ── Shield cleanup ────────────────────────────────────────────────────────────

def test_remove_warden_shields_kills_shields_but_not_goblin():
    """_remove_warden_shields must kill all shield entities and nothing else."""
    room = _bare_room()
    s1 = Entity(kind='shield', row=3, col=10)
    s2 = Entity(kind='shield', row=3, col=12)
    g  = Entity(kind='goblin', row=3, col=15, max_hp=1, ai='chase')
    room.add_entity(s1)
    room.add_entity(s2)
    room.add_entity(g)

    _remove_warden_shields(room)

    assert not s1.alive and not s2.alive, "both shields must be dead"
    assert g.alive, "goblin must be unaffected"


# ── Spawn goblin collision avoidance ─────────────────────────────────────────

def test_spawn_goblin_avoids_occupied_column():
    """_spawn_goblin must use a fallback column when the primary is blocked."""
    room = _bare_room()
    blocker = Entity(kind='goblin', row=3, col=15, max_hp=1, ai='chase')
    room.add_entity(blocker)

    spawned = _spawn_goblin(room, 3, 15)

    assert spawned is not None, "_spawn_goblin must find an alternative column"
    assert spawned.col != 15, (
        f"spawned goblin must not land on occupied col 15, got {spawned.col}"
    )


# ── Alert radius ──────────────────────────────────────────────────────────────

def test_goblin_does_not_chase_outside_alert_radius():
    """A goblin more than 5 Manhattan distance from the player must not move."""
    room = _combat_room()
    player = Player(row=4, col=1)
    # Manhattan distance = |4-4| + |15-1| = 14 >> ALERT_RADIUS=5
    goblin = Entity(kind='goblin', row=4, col=15, max_hp=1, ai='chase', ai_speed=1)
    room.add_entity(goblin)
    start_pos = (goblin.row, goblin.col)

    for _ in range(5):
        _enemy_tick(room, player)

    assert (goblin.row, goblin.col) == start_pos, (
        "goblin must not move when player is outside alert radius"
    )
