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

"""Warden boss mechanics — regression tests for two recently-fixed bugs.

Bug 1: Both goblins spawned in one _enemy_tick call now always land on the
       SAME horizontal side of the Warden (shared _side variable).

Bug 2: _reposition_warden_shield now FLIPS the shield to the OPPOSITE
       horizontal side from where it currently sits (alternating pattern).
"""

import random
from types import SimpleNamespace

from engine.world import CellType, Entity, Room, RoomType
from main import (
    _do_warden_move,
    _enemy_tick,
    _reposition_warden_shield,
)


# ── Shared fixture helpers ─────────────────────────────────────────────────────

ROWS = 7
COLS = 60
WARDEN_ROW = 3
WARDEN_COL = 27

# The shield starts to the LEFT (col 26) of the Warden (col 27) in the real dungeon.
SHIELD_COL_LEFT = WARDEN_COL - 1   # 26
SHIELD_COL_RIGHT = WARDEN_COL + 1  # 28

# Player well within _ALERT_RADIUS = 5; warden at (3,27), player at (3,10) → dist 17,
# which is OUTSIDE alert radius.  Tests that need the warden to summon use a player
# close enough: row 3, col 24 → dist 3, inside radius 5.
PLAYER_CLOSE = SimpleNamespace(row=WARDEN_ROW, col=WARDEN_COL - 3)   # dist 3
PLAYER_FAR   = SimpleNamespace(row=WARDEN_ROW, col=10)                # dist 17


def _make_room(warden_col=WARDEN_COL, shield_col=SHIELD_COL_LEFT,
               extra_entities=None) -> Room:
    """Build a minimal 7×60 BOSS room with a warden and a shield."""
    room = Room(room_type=RoomType.BOSS, rows=ROWS, cols=COLS)
    room.cells = [[CellType.FLOOR] * COLS for _ in range(ROWS)]

    warden = Entity(
        kind='warden', row=WARDEN_ROW, col=warden_col,
        hp=5, max_hp=5, ai='', summon_timer=0, goblin_free_turns=2,
    )
    shield = Entity(kind='shield', row=WARDEN_ROW, col=shield_col)

    entities = [warden, shield]
    if extra_entities:
        entities.extend(extra_entities)
    room.entities = entities
    room.rebuild_indexes()
    return room


def _get_warden(room: Room) -> Entity:
    return next(e for e in room.entities if e.kind == 'warden')


def _get_shield(room: Room) -> Entity:
    return next(e for e in room.entities if e.kind == 'shield' and e.alive)


# ── Bug 1 tests: goblins always spawn on the same side ────────────────────────

def test_goblin_pair_always_same_side_many_seeds():
    """Over 200 different random seeds, both goblins from one _enemy_tick call
    always land on the same horizontal side of the Warden.

    Before the fix, each _spawn_goblin used an independent random.choice((-1,1)),
    so goblins could end up on opposite sides.  After the fix a single _side
    variable is shared for both calls.
    """
    for seed in range(200):
        random.seed(seed)
        room = _make_room()
        warden = _get_warden(room)

        _enemy_tick(room, PLAYER_CLOSE)

        goblins = [e for e in room.entities if e.kind == 'goblin' and e.alive
                   and e.summoner_uid == warden.uid]

        # The warden may not have spawned if goblin_free_turns or summon_timer
        # state differs — only assert when exactly two goblins are present.
        if len(goblins) == 2:
            g1, g2 = goblins
            same_side = (
                (g1.col < warden.col and g2.col < warden.col) or
                (g1.col > warden.col and g2.col > warden.col)
            )
            assert same_side, (
                f"seed={seed}: goblins at cols {g1.col},{g2.col} with warden at "
                f"col {warden.col} — expected same side"
            )


def test_goblin_pair_both_left_or_both_right():
    """Deterministically check both possible _side values produce same-side pairs."""
    for forced_side in (-1, 1):
        random.seed(0)  # will be overridden by monkeypatching via random module
        room = _make_room()
        warden = _get_warden(room)

        # Patch random.choice to return a fixed side for this call.
        original_choice = random.choice
        calls = []
        def _fixed_choice(seq):
            result = forced_side
            calls.append(result)
            return result
        random.choice = _fixed_choice
        try:
            _enemy_tick(room, PLAYER_CLOSE)
        finally:
            random.choice = original_choice

        goblins = [e for e in room.entities if e.kind == 'goblin' and e.alive
                   and e.summoner_uid == warden.uid]

        if len(goblins) == 2:
            g1, g2 = goblins
            if forced_side == -1:
                assert g1.col < warden.col and g2.col < warden.col, (
                    f"side=-1: goblins {g1.col},{g2.col} should both be left of {warden.col}"
                )
            else:
                assert g1.col > warden.col and g2.col > warden.col, (
                    f"side=+1: goblins {g1.col},{g2.col} should both be right of {warden.col}"
                )


def test_warden_moves_on_hit_regardless_of_live_goblins():
    """Warden moves every time it is hit (hp > 0), even while goblins are alive.

    New mechanic: _do_warden_move is called directly on hit rather than after
    the last goblin is killed, so live goblins do not block the warden's move.
    """
    goblin = Entity(
        kind='goblin', row=WARDEN_ROW, col=WARDEN_COL + 3,
        hp=1, max_hp=1, ai='chase', ai_speed=1,
    )
    room = _make_room(extra_entities=[goblin])
    warden = _get_warden(room)
    original_row = warden.row

    msg = _do_warden_move(room, warden, PLAYER_CLOSE)

    assert msg != '', "_do_warden_move returned '' — warden should move on hit"
    warden_after = _get_warden(room)
    assert warden_after.row != original_row, (
        f"Warden should have changed row after being hit; still at {warden_after.row}"
    )


# ── Bug 2 tests: shield alternates sides on each Warden move ──────────────────

def test_shield_flips_to_opposite_side_after_one_reposition():
    """After one call to _reposition_warden_shield, the shield is on the
    OPPOSITE horizontal side from where it started.

    Before the fix, the shield always moved to the player's side.
    """
    # Shield starts LEFT of the warden.
    room = _make_room(shield_col=SHIELD_COL_LEFT)
    warden = _get_warden(room)
    shield = _get_shield(room)

    assert shield.col < warden.col, "Shield should start to the left"

    _reposition_warden_shield(room, warden, PLAYER_CLOSE)

    shield_after = _get_shield(room)
    assert shield_after.col > warden.col, (
        f"Shield at col {shield_after.col} should be to the RIGHT of warden at "
        f"col {warden.col} after flipping from LEFT"
    )


def test_shield_flips_to_opposite_side_starting_right():
    """Shield starting on the RIGHT should flip to the LEFT."""
    room = _make_room(shield_col=SHIELD_COL_RIGHT)
    warden = _get_warden(room)
    shield = _get_shield(room)

    assert shield.col > warden.col, "Shield should start to the right"

    _reposition_warden_shield(room, warden, PLAYER_CLOSE)

    shield_after = _get_shield(room)
    assert shield_after.col < warden.col, (
        f"Shield at col {shield_after.col} should be to the LEFT of warden at "
        f"col {warden.col} after flipping from RIGHT"
    )


def test_shield_alternates_symmetrically_two_repositions():
    """After two calls to _reposition_warden_shield the shield is back on its
    original side (alternation is symmetric).
    """
    room = _make_room(shield_col=SHIELD_COL_LEFT)
    warden = _get_warden(room)
    shield = _get_shield(room)

    original_side_col = shield.col

    _reposition_warden_shield(room, warden, PLAYER_CLOSE)
    shield_mid = _get_shield(room)
    # Verify it flipped once.
    assert (shield_mid.col > warden.col) != (original_side_col > warden.col), (
        "Shield should have flipped after first reposition"
    )

    _reposition_warden_shield(room, warden, PLAYER_CLOSE)
    shield_final = _get_shield(room)

    # After two flips, should be back on original side.
    original_was_left = original_side_col < warden.col
    final_is_left = shield_final.col < warden.col
    assert original_was_left == final_is_left, (
        f"Shield ended at col {shield_final.col}; expected same side as original "
        f"col {original_side_col} (warden at col {warden.col})"
    )


def test_do_warden_move_places_shield_on_opposite_side():
    """_do_warden_move (which internally calls _reposition_warden_shield) results
    in the shield being on the opposite horizontal side from where it started.
    """
    room = _make_room(shield_col=SHIELD_COL_LEFT)
    warden = _get_warden(room)
    shield_before = _get_shield(room)

    assert shield_before.col < warden.col, "Shield should start LEFT of warden"

    msg = _do_warden_move(room, warden, PLAYER_CLOSE)

    # _do_warden_move may return '' if the warden cannot move (e.g. blocked).
    # It should succeed in a clear room.
    assert msg != '', "_do_warden_move returned '' in a clear room — warden should be able to move"

    # The warden may have shifted row; compare shield vs warden column positions.
    warden_after = _get_warden(room)
    shield_after = _get_shield(room)

    assert shield_after.col > warden_after.col, (
        f"After _do_warden_move, shield at col {shield_after.col} should be RIGHT "
        f"of warden at col {warden_after.col} (was originally LEFT)"
    )
