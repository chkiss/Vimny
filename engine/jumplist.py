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

"""Block J — the jump list (Ctrl-o / Ctrl-i).

Large-distance motions (G, gg, %, { } ( ), search, marks) record the position
they jump *from*. Ctrl-o walks to older positions, Ctrl-i back to newer.
`jump_idx` is where the cursor sits in the list; it equals len(jump_list) when
the cursor is at a fresh position past the newest entry.
"""
from __future__ import annotations

_CAP = 100


def record_jump(player, pos) -> None:
    """Record `pos` (the position being jumped from). Drops any forward history.

    Also sets the implicit ``'`` mark (Vim-true): ``''`` / ``` `` ``` jump
    back to the spot you last jumped FROM — and since a mark-jump records a
    jump itself, ``''`` toggles between the two positions."""
    player.marks["'"] = pos
    jl = player.jump_list
    if player.jump_idx < len(jl):
        del jl[player.jump_idx:]          # leaving the middle: discard newer entries
    if not jl or jl[-1] != pos:
        jl.append(pos)
    while len(jl) > _CAP:
        jl.pop(0)
    player.jump_idx = len(jl)


def jump_back(player):
    """Ctrl-o: move to an older position. Returns (row, col) or None."""
    jl = player.jump_list
    if not jl:
        return None
    cur = (player.row, player.col)
    if player.jump_idx >= len(jl):
        # First step back from a fresh position: stash current so Ctrl-i can return.
        if jl[-1] != cur:
            jl.append(cur)
            while len(jl) > _CAP + 1:
                jl.pop(0)
        player.jump_idx = len(jl) - 1
    if player.jump_idx <= 0:
        return None
    player.jump_idx -= 1
    return jl[player.jump_idx]


def jump_forward(player):
    """Ctrl-i: move to a newer position. Returns (row, col) or None."""
    jl = player.jump_list
    if player.jump_idx + 1 >= len(jl):
        return None
    player.jump_idx += 1
    return jl[player.jump_idx]
