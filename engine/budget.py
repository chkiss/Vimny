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

class Budget:
    """Keystroke budget. Undo/redo of `spent` is handled by the game loop's snapshot
    history (main._pop_history_step restores `spent` directly), so Budget itself only
    needs to spend; it carries no per-action history."""

    def __init__(self, total: int):
        self.total  = total
        self.spent  = 0
        self.frozen = False             # when True, spend() is a no-op (macro replay)

    @property
    def remaining(self) -> int:
        return self.total - self.spent

    def spend(self, cost: int = 1):
        if self.frozen:                 # replayed macro keys don't re-charge budget
            return
        self.spent += cost

    @property
    def is_over(self) -> bool:
        return self.spent > self.total
