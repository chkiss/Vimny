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

WOOD_WALL_DAMAGED = '░'
SEALED_WALL       = '╬'   # a gate: banded stone that some tick draws back

FLOOR        = ' '
CORRIDOR     = ' '

PLAYER       = '@'
ENEMY_WANDERER = '♟'

HEART_FULL   = '♥'
HEART_HALF   = '♡'
HEART_EMPTY  = '░'
KEY          = '🗝'
CHEST        = '🞔'
DOOR_H       = '▬'
DOOR_V       = '▮'
DOOR_LOCKED  = '🔒'   # may be replaced by init() if terminal renders it as 2-wide
EXIT         = '◉'
SHIELD       = '⛨'   # may be replaced by init() if terminal renders it as 2-wide
HAT          = 'Δ'   # the Warden's/wizard's hat (dropped by the final boss); → '^' if 2-wide
HORSE        = '♞'   # the wizard's horse (post-game, in the First Cave); → 'h' if 2-wide


def init(term) -> None:
    """Replace wide glyphs with single-width fallbacks when the terminal renders them as 2 columns."""
    global DOOR_LOCKED, SHIELD, HAT, HORSE
    if term.length(DOOR_LOCKED) != 1:
        DOOR_LOCKED = '⊡'
    if term.length(SHIELD) != 1:
        SHIELD = '◆'
    if term.length(HAT) != 1:
        HAT = '^'
    if term.length(HORSE) != 1:
        HORSE = 'h'

BOX_TL = '┌'; BOX_TR = '┐'; BOX_BL = '└'; BOX_BR = '┘'
BOX_H  = '─'; BOX_V  = '│'
BOX_LT = '├'; BOX_RT = '┤'
