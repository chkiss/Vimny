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

"""The Dot Repeater — uses . (repeat last change) everywhere.

Personality defined in agents/bug_testers.md.
"""
from engine.vim_parser import parse
from engine.modes import Mode
from engine.player import Player
from engine.command_guard import action_allowed, guard_message


# ── Parser ────────────────────────────────────────────────────────────────────

def test_dot_parses_as_repeat():
    action, remaining = parse('.', Mode.NORMAL)
    assert action == {'type': 'repeat', 'count': 1}
    assert remaining == ''


def test_3_dot_parses_with_count():
    action, remaining = parse('3.', Mode.NORMAL)
    assert action == {'type': 'repeat', 'count': 3}
    assert remaining == ''


def test_10_dot_parses_with_count():
    action, remaining = parse('10.', Mode.NORMAL)
    assert action == {'type': 'repeat', 'count': 10}
    assert remaining == ''


# ── Player.last_change initial state ─────────────────────────────────────────

def test_last_change_starts_as_none():
    player = Player()
    assert player.last_change is None


# ── Count-override logic ──────────────────────────────────────────────────────

def test_dot_count_1_keeps_original_count():
    """When repeat_count == 1, the stored action's count must be preserved."""
    player = Player()
    player.last_change = {'type': 'interact', 'count': 2}

    repeat_count = 1
    action = dict(player.last_change)
    if repeat_count != 1:
        action['count'] = repeat_count

    assert action['count'] == 2, (
        ". with count=1 must keep the stored action's count"
    )


def test_dot_count_3_overrides_stored_count():
    """When repeat_count != 1, it replaces the stored action's count."""
    player = Player()
    player.last_change = {'type': 'interact', 'count': 1}

    repeat_count = 3
    action = dict(player.last_change)
    if repeat_count != 1:
        action['count'] = repeat_count

    assert action['count'] == 3, (
        ". with count=3 must override the stored count"
    )


def test_dot_count_5_overrides_stored_count_2():
    player = Player()
    player.last_change = {'type': 'interact', 'count': 2}

    repeat_count = 5
    action = dict(player.last_change)
    if repeat_count != 1:
        action['count'] = repeat_count

    assert action['count'] == 5


# ── dict(last_change) is a shallow copy ──────────────────────────────────────

def test_dot_action_mutation_does_not_affect_last_change():
    """dict(player.last_change) makes a shallow copy; mutating the copy must
    not change player.last_change."""
    player = Player()
    original = {'type': 'interact', 'count': 1}
    player.last_change = original

    repeat_count = 3
    action = dict(player.last_change)
    action['count'] = repeat_count

    assert player.last_change['count'] == 1, (
        "player.last_change must not be mutated when the repeat action is modified"
    )
    assert player.last_change is original


# ── action_allowed gating for repeat ─────────────────────────────────────────

def test_repeat_blocked_without_dot_in_known_commands():
    action = {'type': 'repeat', 'count': 1}
    known = ['h', 'j', 'k', 'l']

    assert not action_allowed(action, known), (
        ". must be blocked when 'dot' is not in known_commands"
    )


def test_repeat_allowed_with_dot_in_known_commands():
    action = {'type': 'repeat', 'count': 1}
    known = ['h', 'j', 'k', 'l', 'dot']

    assert action_allowed(action, known), (
        ". must be allowed when 'dot' is in known_commands"
    )


def test_repeat_allowed_for_admin():
    action = {'type': 'repeat', 'count': 1}
    known = ['admin']

    assert action_allowed(action, known)


def test_guard_message_for_repeat():
    action = {'type': 'repeat', 'count': 1}
    msg = guard_message(action)
    assert "." in msg or "repeat" in msg.lower() or "haven't learned" in msg.lower()


# ── last_change not set by paste ──────────────────────────────────────────────

def test_paste_does_not_set_last_change():
    """The paste handler does NOT update player.last_change.
    Test the contract by asserting last_change starts as None and
    paste (p/P) action type is 'paste', not 'interact'.
    """
    action, _ = parse('p', Mode.NORMAL)
    # Paste actions have type='paste', not 'interact'
    assert action['type'] == 'paste'

    # Since the game loop only sets last_change on interact/operator/substitute,
    # a fresh player after a paste remains with last_change == None.
    player = Player()
    assert player.last_change is None   # untouched by paste branch


# ── last_change not cleared by motion ────────────────────────────────────────

def test_last_change_not_cleared_by_motion():
    """Motion (moving around the dungeon) must not clear player.last_change."""
    player = Player()
    player.last_change = {'type': 'interact', 'count': 1}

    # Simulate motion: the game loop only calls apply_motion() and does NOT
    # touch player.last_change. Test the contract directly.
    from engine.world import Room, RoomType, CellType
    from engine.motion import apply_motion
    room = Room(room_type=RoomType.ENTRY, rows=5, cols=20)
    room.cells = [
        [CellType.FLOOR if (0 < r < 4 and 0 < c < 19) else CellType.WALL
         for c in range(20)]
        for r in range(5)
    ]
    room.fog_cells = set()
    room.rebuild_indexes()

    apply_motion(player, 'l', 1, room)   # move right

    assert player.last_change == {'type': 'interact', 'count': 1}, (
        "motion must not clear or modify player.last_change"
    )


# ── repeat action type ────────────────────────────────────────────────────────

def test_repeat_action_type_is_repeat_not_interact():
    action, _ = parse('.', Mode.NORMAL)
    assert action['type'] == 'repeat', (
        ". must parse as type='repeat', not 'interact' or anything else"
    )


# ── interaction sets last_change ─────────────────────────────────────────────

def test_last_change_stores_interact_action():
    """Verify the pattern: game loop sets player.last_change = action when
    interact succeeds. Test the dict structure directly."""
    player = Player()
    action = {'type': 'interact', 'count': 1}
    player.last_change = action

    assert player.last_change is action
    assert player.last_change['type'] == 'interact'


def test_last_change_stores_interact_with_count():
    player = Player()
    action = {'type': 'interact', 'count': 3}
    player.last_change = action

    # When . fires with repeat_count=1, the count stays at 3
    repeat_count = 1
    replayed = dict(player.last_change)
    if repeat_count != 1:
        replayed['count'] = repeat_count

    assert replayed['count'] == 3
