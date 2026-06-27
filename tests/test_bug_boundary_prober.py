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

"""The Boundary Prober — moves to corners, edges, and extreme cells.

Personality defined in agents/bug_testers.md.
"""
from engine.world import Room, RoomType, CellType, CharRun
from engine.player import Player
from engine.motion import apply_motion, move_player


def _bare_room(rows=7, cols=30):
    room = Room(room_type=RoomType.ENTRY, rows=rows, cols=cols)
    room.cells = [
        [CellType.FLOOR if (0 < r < rows - 1 and 0 < c < cols - 1) else CellType.WALL
         for c in range(cols)]
        for r in range(rows)
    ]
    room.spawn_pos = (3, 1)
    room.exit_pos = (3, 28)
    room.fog_cells = set()
    room.rebuild_indexes()
    return room


# ── $ and 0 at boundaries ─────────────────────────────────────────────────────

def test_dollar_at_rightmost_cell_is_noop():
    room = _bare_room()
    player = Player(row=3, col=28)   # rightmost floor cell

    moved = apply_motion(player, '$', 1, room)

    assert not moved, "$ at rightmost cell must return False"
    assert player.col == 28


def test_zero_at_leftmost_cell_is_noop():
    room = _bare_room()
    player = Player(row=3, col=1)    # leftmost floor cell

    moved = apply_motion(player, '0', 1, room)

    assert not moved, "0 at leftmost cell must return False"
    assert player.col == 1


def test_dollar_entire_row_fogged_is_noop():
    """$ when all cells to the right are fogged must not move the player."""
    room = _bare_room()
    room.fog_cells = {(3, c) for c in range(2, 29)}
    player = Player(row=3, col=1)

    moved = apply_motion(player, '$', 1, room)

    assert not moved, "$ with fully fogged row must return False"
    assert player.col == 1


def test_dollar_passes_through_void_rune_mid_row():
    """$ scan ignores void CharRuns — only walls/entities stop it.
    A void rune in the middle of a row does not stop $; it lands at rightmost cell."""
    room = _bare_room()
    mid_void = CharRun(row=3, col=10, symbols=('○',), kind='void')
    room.char_runs.append(mid_void)
    room.rebuild_indexes()
    player = Player(row=3, col=1)

    moved = apply_motion(player, '$', 1, room)

    assert moved
    assert player.col == 28   # rightmost floor cell, not stopped at void col 10


def test_dollar_lands_on_void_at_rightmost_cell():
    """$ does not stop before a void CharRun mid-scan — it lands on the
    rightmost passable cell even when that cell has a void rune."""
    room = _bare_room()
    end_void = CharRun(row=3, col=28, symbols=('○',), kind='void')
    room.char_runs.append(end_void)
    room.rebuild_indexes()
    player = Player(row=3, col=1)

    moved = apply_motion(player, '$', 1, room)

    assert moved
    assert player.col == 28   # $ lands on void (in-game death follows)


# ── hjkl wall boundaries ──────────────────────────────────────────────────────

def test_l_into_right_wall_fails():
    room = _bare_room()
    player = Player(row=3, col=28)

    moved = apply_motion(player, 'l', 1, room)

    assert not moved
    assert player.col == 28


def test_h_into_left_wall_fails():
    room = _bare_room()
    player = Player(row=3, col=1)

    moved = apply_motion(player, 'h', 1, room)

    assert not moved
    assert player.col == 1


def test_j_into_bottom_wall_fails():
    room = _bare_room()
    player = Player(row=5, col=10)   # last floor row (6 is wall)

    moved = apply_motion(player, 'j', 1, room)

    assert not moved
    assert player.row == 5


def test_k_into_top_wall_fails():
    room = _bare_room()
    player = Player(row=1, col=10)   # first floor row (0 is wall)

    moved = apply_motion(player, 'k', 1, room)

    assert not moved
    assert player.row == 1


# ── move_player boundary ──────────────────────────────────────────────────────

def test_move_player_into_wall_returns_false():
    room = _bare_room()
    player = Player(row=3, col=28)

    result = move_player(player, 0, 1, room)

    assert result is False
    assert player.col == 28


# ── w/b/e with no runes ───────────────────────────────────────────────────────

def test_w_with_no_runes_does_not_move():
    room = _bare_room()
    player = Player(row=3, col=1)

    moved = apply_motion(player, 'w', 1, room)

    assert not moved, "w with no runes must return False"
    assert player.col == 1


def test_b_with_no_runes_does_not_move():
    room = _bare_room()
    player = Player(row=3, col=15)

    moved = apply_motion(player, 'b', 1, room)

    assert not moved, "b with no runes must return False"
    assert player.col == 15


def test_e_with_no_runes_does_not_move():
    room = _bare_room()
    player = Player(row=3, col=5)

    moved = apply_motion(player, 'e', 1, room)

    assert not moved, "e with no runes must return False"
    assert player.col == 5


def test_w_after_last_rune_does_not_move():
    """w from the only rune (nothing to the right) must not move."""
    room = _bare_room()
    ru = CharRun(row=3, col=5, symbols=('∘',), kind='ancient')
    room.char_runs.append(ru)
    room.rebuild_indexes()
    player = Player(row=3, col=5)

    moved = apply_motion(player, 'w', 1, room)

    assert not moved, "w with no next rune must return False"
    assert player.col == 5


def test_b_before_first_rune_does_not_move():
    """b from a floor cell before any rune must not move."""
    room = _bare_room()
    ru = CharRun(row=3, col=15, symbols=('∘',), kind='ancient')
    room.char_runs.append(ru)
    room.rebuild_indexes()
    player = Player(row=3, col=1)   # col 1 has no rune and nothing to the left

    moved = apply_motion(player, 'b', 1, room)

    assert not moved, "b before all runes must return False"
    assert player.col == 1


# ── gg / G teleportation ──────────────────────────────────────────────────────

def test_gg_jumps_to_first_line():
    room = _bare_room()
    player = Player(row=5, col=25)

    apply_motion(player, 'gg', 1, room, count_given=False)

    # gg → first line, leftmost passable (no runes); independent of spawn_pos
    assert (player.row, player.col) == (1, 1)


def test_G_jumps_to_last_passable_row():
    # bare G → last passable row (row 5 in a 7-row room), first non-blank col
    room = _bare_room()
    player = Player(row=1, col=1)

    apply_motion(player, 'G', 1, room, count_given=False)

    assert player.row == 5   # last passable row (rows 0 and 6 are walls)
    assert player.col == 1   # leftmost passable col (no runes in bare room)


def test_G_exit_pos_irrelevant():
    """bare G goes to last passable row regardless of exit_pos."""
    room = _bare_room()
    room.exit_pos = None
    player = Player(row=3, col=5)

    moved = apply_motion(player, 'G', 1, room, count_given=False)

    assert moved
    assert player.row == 5
    assert player.col == 1
