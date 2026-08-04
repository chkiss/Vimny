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
MIST              = '~'   # haze on water — still WATER, and it must read as water

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
#: The fancy door — a lock whose key is WORDS. It was drawn as a plain locked
#: door until 2026-08-02, on the argument that the player already knows that
#: glyph means "bring me the key"; what that missed is that they then go looking
#: for a key, and there isn't one. APL's quote-quad is a box you speak INTO,
#: which is the whole mechanic in one character, and it is unmistakably not the
#: padlock — so a room holding both reads as two locks, not one lock twice.
DOOR_SPOKEN  = '⍞'
#: What the unlock animation flashes where a key would flash. The gesture is the
#: same `p` a locked door takes, so the beat has to be the same beat — only the
#: thing held up is a closing quotation mark rather than a key, because what
#: opened this door was words. NOT an emoji, and not ⌨ either: 🗣 and its
#: neighbours measure one column and render as two in most terminals, which the
#: fallback below cannot catch (it only sees the measurement), and ⌨ is
#: emojified by enough terminals to have the same problem.
KEY_SPOKEN   = '❞'
EXIT         = '◉'
SHIELD       = '⛨'   # may be replaced by init() if terminal renders it as 2-wide
HAT          = 'Δ'   # the Warden's/wizard's hat (dropped by the final boss); → '^' if 2-wide
HORSE        = '♞'   # the wizard's horse (post-game, in the First Cave); → 'h' if 2-wide


def init(term) -> None:
    """Replace wide glyphs with single-width fallbacks when the terminal renders them as 2 columns."""
    global DOOR_LOCKED, SHIELD, HAT, HORSE, DOOR_SPOKEN, KEY_SPOKEN
    if term.length(DOOR_LOCKED) != 1:
        DOOR_LOCKED = '⊡'
    if term.length(DOOR_SPOKEN) != 1:
        DOOR_SPOKEN = '◫'
    if term.length(KEY_SPOKEN) != 1:
        KEY_SPOKEN = '"'
    if term.length(SHIELD) != 1:
        SHIELD = '◆'
    if term.length(HAT) != 1:
        HAT = '^'
    if term.length(HORSE) != 1:
        HORSE = 'h'

BOX_TL = '┌'; BOX_TR = '┐'; BOX_BL = '└'; BOX_BR = '┘'
BOX_H  = '─'; BOX_V  = '│'
BOX_LT = '├'; BOX_RT = '┤'
