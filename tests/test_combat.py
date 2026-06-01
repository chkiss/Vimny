"""Tests for combat / enemy-tick behaviour in main.py."""
import pytest
from engine.world import Room, RoomType, CellType, Entity
from engine.player import Player
from main import _enemy_tick, _try_warden_move, _do_warden_move, _reposition_warden_shield, _on_kill, _remove_warden_shields

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


# ── Warden movement mechanic ──────────────────────────────────────────────────

def _combat_room():
    """Wider room for Warden fight tests: all interior cells are floor."""
    rows, cols = 9, 40
    room = Room(room_type=RoomType.ENTRY, rows=rows, cols=cols)
    room.cells = [
        [CellType.FLOOR if (0 < r < rows - 1 and 0 < c < cols - 1) else CellType.WALL
         for c in range(cols)]
        for r in range(rows)
    ]
    room.spawn_pos    = (4, 1)
    room.exit_pos = (4, 38)
    room.rebuild_indexes()
    return room


def test_warden_moves_on_last_spawn_kill():
    """Killing the last Warden-spawned goblin triggers Warden row movement."""
    room   = _combat_room()
    player = Player(row=4, col=1)
    warden = Entity(kind='warden', row=4, col=25, max_hp=5, ai='')
    room.add_entity(warden)
    goblin = Entity(kind='goblin', row=4, col=20, max_hp=1, ai='chase',
                    summoner_uid=warden.uid)
    room.add_entity(goblin)

    room.kill_entity(goblin)  # mirrors game loop: kill before calling _try_warden_move
    msg = _try_warden_move(room, goblin, player)

    assert msg == 'The Warden leaps!'
    assert abs(warden.row - 4) >= 2, "Warden must leap at least 2 rows"


def test_warden_no_move_when_spawns_remain():
    """Killing one of two Warden-spawned goblins must NOT trigger movement."""
    room   = _combat_room()
    player = Player(row=4, col=1)
    warden = Entity(kind='warden', row=4, col=25, max_hp=5, ai='')
    room.add_entity(warden)
    g1 = Entity(kind='goblin', row=4, col=18, max_hp=1, ai='chase', summoner_uid=warden.uid)
    g2 = Entity(kind='goblin', row=4, col=20, max_hp=1, ai='chase', summoner_uid=warden.uid)
    room.add_entity(g1)
    room.add_entity(g2)

    room.kill_entity(g1)  # g2 still alive
    msg = _try_warden_move(room, g1, player)

    assert msg == ''
    assert warden.row == 4


def test_warden_no_move_for_non_spawn_goblin():
    """Killing a goblin that was NOT spawned by a Warden must not trigger movement."""
    room   = _combat_room()
    player = Player(row=4, col=1)
    warden = Entity(kind='warden', row=4, col=25, max_hp=5, ai='')
    room.add_entity(warden)
    pre_placed = Entity(kind='goblin', row=4, col=10, max_hp=1, ai='chase')
    # summoner_uid defaults to 0 — not linked to any Warden
    room.add_entity(pre_placed)

    msg = _try_warden_move(room, pre_placed, player)

    assert msg == ''
    assert warden.row == 4


def test_shield_repositions_right_when_player_right():
    """When player is to the right of the Warden, shield moves to Warden's right."""
    room   = _combat_room()
    player = Player(row=4, col=30)          # player is to the RIGHT
    warden = Entity(kind='warden', row=4, col=20, max_hp=5, ai='')
    shield = Entity(kind='shield',  row=4, col=19)  # starts on left
    room.add_entity(warden)
    room.add_entity(shield)

    _do_warden_move(room, warden, player)

    assert shield.col == warden.col + 1, (
        f"Shield should be right of Warden (col {warden.col + 1}), got {shield.col}"
    )


def test_shield_repositions_left_when_player_left():
    """When player is to the left of the Warden, shield moves to Warden's left."""
    room   = _combat_room()
    player = Player(row=4, col=5)           # player is to the LEFT
    warden = Entity(kind='warden', row=4, col=20, max_hp=5, ai='')
    shield = Entity(kind='shield',  row=4, col=21)  # starts on right
    room.add_entity(warden)
    room.add_entity(shield)

    _do_warden_move(room, warden, player)

    assert shield.col == warden.col - 1, (
        f"Shield should be left of Warden (col {warden.col - 1}), got {shield.col}"
    )


def test_warden_leaps_at_least_two_rows_each_move():
    """Every Warden move is a random leap of ≥2 rows, staying on floor within bounds."""
    import random
    random.seed(12345)            # deterministic trajectory for the roam assertion
    room   = _combat_room()       # interior floor rows 1..7
    player = Player(row=4, col=1)
    warden = Entity(kind='warden', row=4, col=20, max_hp=5, ai='')
    room.add_entity(warden)

    positions = [warden.row]
    for _ in range(8):
        prev = warden.row
        msg  = _do_warden_move(room, warden, player)
        assert msg == 'The Warden leaps!'
        assert abs(warden.row - prev) >= 2, (
            f"Warden hopped <2 rows: {prev} → {warden.row}"
        )
        assert 1 <= warden.row <= 7, f"Warden left the floor: row {warden.row}"
        positions.append(warden.row)

    # Must roam, not park on one row
    assert len(set(positions)) > 1, "Warden never moved from its origin row"


def test_warden_leap_distance_varies_with_randomness():
    """Across many leaps the Warden uses more than one jump distance."""
    import random
    random.seed(7)
    room   = _combat_room()       # interior floor rows 1..7
    player = Player(row=4, col=1)
    warden = Entity(kind='warden', row=4, col=20, max_hp=5, ai='')
    room.add_entity(warden)

    dists = set()
    for _ in range(20):
        prev = warden.row
        _do_warden_move(room, warden, player)
        dists.add(abs(warden.row - prev))

    assert all(d >= 2 for d in dists), f"every leap must be ≥2 rows; saw {dists}"
    assert len(dists) > 1, f"leap distance should vary; only saw {dists}"


def test_warden_direction_reverses_when_walled_in():
    """A walled-in Warden can only leap toward open floor."""
    room   = _combat_room()       # interior floor rows 1..7
    player = Player(row=4, col=1)
    warden = Entity(kind='warden', row=7, col=20, max_hp=5, ai='', move_dir=1)
    room.add_entity(warden)

    # From the bottom floor row, every valid landing (≥2 away) is upward.
    _do_warden_move(room, warden, player)
    assert warden.move_dir == -1, "Warden must reverse to leap up off the bottom row"
    assert warden.row <= 5


# ── Warden death drops the key to its locked exit (no auto-opening seal) ──────

def _boss_room():
    """Minimal Warden's-Keep-style room."""
    rows, cols = 7, 44
    room = Room(room_type=RoomType.COMBAT, rows=rows, cols=cols)
    room.cells = [
        [CellType.FLOOR if (0 < r < rows - 1 and 0 < c < cols - 1) else CellType.WALL
         for c in range(cols)]
        for r in range(rows)
    ]
    room.spawn_pos = (3, 0)
    room.exit_pos  = (3, 39)
    room.fog_cells = set()
    room.rebuild_indexes()
    return room


def test_warden_death_drops_a_key_and_leaves_the_door():
    """The Warden drops a key on its cell; the locked exit door is NOT auto-opened."""
    room   = _boss_room()
    player = Player(row=3, col=10)
    warden = Entity(kind='warden', row=3, col=27, max_hp=5, ai='')
    door   = Entity(kind='locked_door', row=3, col=38)
    room.add_entity(warden)
    room.add_entity(door)

    room.kill_entity(warden)
    msg = _on_kill(warden, player, room, 'wardens_keep')

    assert 'key' in msg.lower()
    assert any(e.alive and e.kind == 'floor_key' and (e.row, e.col) == (3, 27)
               for e in room.entities), "a key should drop on the Warden's cell"
    assert any(e.alive and e.kind == 'locked_door' for e in room.entities), \
        "the exit door stays locked until the key is used"


# ── Shield removal on Warden death ───────────────────────────────────────────

def test_shield_removed_when_warden_dies():
    """All shield entities disappear when _remove_warden_shields is called."""
    room   = _boss_room()
    shield = Entity(kind='shield', row=3, col=26)
    room.add_entity(shield)

    _remove_warden_shields(room)

    assert not any(e.alive and e.kind == 'shield' for e in room.entities)


def test_shield_removal_does_not_affect_other_entities():
    """_remove_warden_shields leaves non-shield entities untouched."""
    room   = _boss_room()
    shield = Entity(kind='shield', row=3, col=26)
    warden = Entity(kind='warden', row=3, col=27, max_hp=5, ai='')
    room.add_entity(shield)
    room.add_entity(warden)

    _remove_warden_shields(room)

    assert warden.alive
    assert not any(e.alive and e.kind == 'shield' for e in room.entities)
