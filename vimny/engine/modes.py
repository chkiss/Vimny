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

from enum import Enum, auto

class Mode(Enum):
    NORMAL  = auto()
    INSERT  = auto()
    REPLACE = auto()
    VISUAL  = auto()
    VISUAL_LINE  = auto()
    VISUAL_BLOCK = auto()
    COMMAND = auto()
    SEARCH       = auto()   # / and ? entry
    MACRO_RECORD = auto()   # q{char} recording

MODE_LABELS = {
    Mode.NORMAL:       '-- NORMAL --',
    Mode.INSERT:       '-- INSERT --',
    Mode.REPLACE:      '-- REPLACE --',
    Mode.VISUAL:       '-- VISUAL --',
    Mode.VISUAL_LINE:  '-- VISUAL LINE --',
    Mode.VISUAL_BLOCK: '-- VISUAL BLOCK --',
    Mode.COMMAND:      ':',
    Mode.SEARCH:       '/',
    Mode.MACRO_RECORD: '-- RECORDING --',
}
