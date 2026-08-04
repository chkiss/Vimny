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

"""Tests for combat / enemy-tick behaviour in vimny/game.py."""
from vimny.engine.world import Room, RoomType, CellType, Entity
from vimny.engine.player import Player
from vimny.game import (_enemy_tick, _do_warden_move, _on_kill, _remove_warden_shields,
                  _drop_tick)

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


def test_a_spent_drop_does_not_respawn_every_turn():
    """The report: 'the east goblin drops a key at the position of the west
    goblin'. `_drop_tick` recomputes drops from the roster each turn and only
    suppressed a re-drop while the key was lying about or in hand — so a key
    picked up AND spent (pasted onto a lock) was neither, looked never-dropped,
    and fell again at the dead carrier's cell every turn. `dropped` marks the
    deed done."""
    room   = _bare_room()
    player = Player(row=3, col=1)
    gob    = Entity(kind='goblin', row=3, col=10, drops='floor_key')
    room.add_entity(gob)

    room.kill_entity(gob)
    assert _drop_tick(room, player)                       # key drops
    key = [e for e in room.entities if e.kind == 'floor_key' and e.alive]
    assert [(e.row, e.col) for e in key] == [(3, 10)]

    for e in key:                                         # picked up and SPENT
        room.kill_entity(e)
    room.rebuild_indexes()
    assert not _drop_tick(room, player), 'the spent key respawned'
    assert not _drop_tick(room, player)
    assert not [e for e in room.entities if e.kind == 'floor_key' and e.alive]


def test_reviving_a_carrier_lets_it_drop_again():
    """Undo-safety of the `dropped` mark: it rides the entity through the
    `clone_entity` snapshot, so a revived carrier (undo of its kill) has a clear
    slate and re-killing drops afresh — the drop is never permanently spent."""
    from vimny.engine.world import clone_entity
    room   = _bare_room()
    player = Player(row=3, col=1)
    gob    = Entity(kind='goblin', row=3, col=10, drops='floor_key')
    room.add_entity(gob)
    room.kill_entity(gob)
    _drop_tick(room, player)
    assert gob.dropped is True

    # An undo restores the pre-kill snapshot: the carrier alive, dropped clear.
    revived = clone_entity(gob, dropped=False)
    revived.hp, revived.alive = 1, True
    room.entities = [e for e in room.entities
                     if not (e.kind == 'floor_key')] + [revived]
    room.entities.remove(gob)
    room.rebuild_indexes()
    room.kill_entity(revived)
    assert _drop_tick(room, player), 'the revived carrier would not drop again'


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


# ── A hound is a combatant, not an invulnerable one ──────────────────────────
#
# The bug both of these pin: NOTHING in the game could ever damage an ally.
# Hostiles only ever struck the player, so a hound bit first every turn and
# took no answer — one dog walked a room clean.  And the hound could not even
# see an impostor Warden, so an echo neither fought it nor was fought.

def _hound_and_foe(foe, hound_hp=1):
    """A hound and one hostile standing next to each other, far from the player."""
    room   = _bare_room()
    player = Player(row=5, col=1)
    hound = Entity(kind='ally', row=1, col=10, hp=hound_hp, max_hp=hound_hp,
                   tag='dog', ai='hunt')
    foe.row, foe.col = 1, 11
    room.add_entity(hound)
    room.add_entity(foe)
    room.rebuild_indexes()
    return room, player, hound, foe


def test_a_goblin_bites_the_hound_back():
    goblin = Entity(kind='goblin', hp=3, max_hp=3, row=0, col=0, ai='chase')
    room, player, hound, goblin = _hound_and_foe(goblin)

    _enemy_tick(room, player)

    assert goblin.hp < 3, 'the hound should have bitten'
    assert not hound.alive, 'and a 1-HP hound should not survive the answer'


def test_a_stationary_foe_still_defends_its_cell():
    """ai='' means it cannot path to you — not that it is harmless up close."""
    zombie = Entity(kind='goblin', hp=3, max_hp=3, row=0, col=0, ai='', tag='zombie')
    room, player, hound, zombie = _hound_and_foe(zombie)

    _enemy_tick(room, player)

    assert not hound.alive


def test_the_hound_smells_an_impostor_warden():
    """An echo is a hostile: the hound bites it, and its first bite unmasks."""
    echo = Entity(kind='goblin', hp=2, max_hp=2, row=0, col=0, ai='', tag='echo')
    room, player, hound, echo = _hound_and_foe(echo, hound_hp=4)

    _enemy_tick(room, player)

    assert echo.tag == '' and echo.alive, 'one strike tears the disguise, as x does'
    assert hound.hp < 4, 'and the echo answers'
