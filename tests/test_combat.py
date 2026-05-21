"""Tests for combat / enemy-tick behaviour in main.py."""
import pytest
from engine.world import Room, RoomType, CellType, Entity
from engine.player import Player
from main import _enemy_tick

ROWS, COLS = 7, 30


def _bare_room():
    room = Room(room_type=RoomType.ENTRY, rows=ROWS, cols=COLS)
    room.cells = [
        [CellType.FLOOR if (0 < r < ROWS - 1 and 0 < c < COLS - 1) else CellType.WALL
         for c in range(COLS)]
        for r in range(ROWS)
    ]
    room.entry    = (3, 1)
    room.exit_pos = (3, 28)
    room.rebuild_indexes()
    return room


# ── Goblin should not summon ──────────────────────────────────────────────────

def test_goblin_does_not_summon():
    """A goblin within alert range must never spawn additional goblins.

    Goblins default to summon_timer=0.  The bug: the summon-timer branch
    fires for any entity with summon_timer >= 0, so a goblin within alert
    range triggers _spawn_goblin on every tick.
    """
    room   = _bare_room()
    player = Player(row=3, col=1)
    goblin = Entity(kind='goblin', row=3, col=3, max_hp=1, ai='chase', ai_speed=1)
    room.add_entity(goblin)

    before = len(room.entities)
    _enemy_tick(room, player)
    after  = len(room.entities)

    assert after == before, (
        f"Goblin spawned {after - before} extra entity/entities; "
        "only wardens should be able to summon."
    )


# ── Warden outside alert radius must not summon ───────────────────────────────

def test_warden_no_summon_outside_alert_radius():
    """Warden with summon_timer=0 outside ALERT_RADIUS must not spawn anything."""
    room   = _bare_room()
    player = Player(row=3, col=1)
    # ALERT_RADIUS = 5; warden at col 20 → Manhattan distance = 19
    warden = Entity(kind='warden', row=3, col=20, max_hp=5, ai='', summon_timer=0)
    room.add_entity(warden)

    before = len(room.entities)
    _enemy_tick(room, player)
    after  = len(room.entities)

    assert after == before, (
        "Warden summoned goblins even though the player was outside the alert radius."
    )


# ── Warden inside alert radius must summon immediately on first tick ──────────

def test_warden_summons_immediately_on_alert():
    """When the player first enters alert range, warden (summon_timer=0) spawns
    goblins on that very tick."""
    room   = _bare_room()
    player = Player(row=3, col=1)
    # col 4 → Manhattan distance = 3, within ALERT_RADIUS=5
    warden = Entity(kind='warden', row=3, col=4, max_hp=5, ai='', summon_timer=0)
    room.add_entity(warden)

    before = len(room.entities)
    _enemy_tick(room, player)
    after  = len(room.entities)

    assert after > before, "Warden should have spawned goblins immediately upon being alerted."


# ── Goblins cannot share a cell ───────────────────────────────────────────────

def test_goblins_cannot_share_cell():
    """Two goblins chasing the player must not end up on the same cell."""
    room   = _bare_room()
    player = Player(row=3, col=1)
    # Both goblins are alerted and want to move left toward the player.
    # g1 at col 4, g2 at col 5 — g1 moves to col 3, g2 should be blocked at col 4.
    g1 = Entity(kind='goblin', row=3, col=4, max_hp=1, ai='chase', ai_speed=1)
    g2 = Entity(kind='goblin', row=3, col=5, max_hp=1, ai='chase', ai_speed=1)
    room.add_entity(g1)
    room.add_entity(g2)

    _enemy_tick(room, player)

    positions = [(e.row, e.col) for e in room.entities if e.alive]
    assert len(positions) == len(set(positions)), (
        "Two entities ended up on the same cell after _enemy_tick."
    )
