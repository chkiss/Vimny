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

from blessed import Terminal

def inner_w(term: Terminal) -> int:
    """Inner playfield width: terminal width clamped to [80, 189], minus 2 borders.
    80 is the minimum supported terminal width; 189 the maximum we lay out to (wide
    enough for the overworld and The Archivist's Library)."""
    return min(max(term.width, 80), 189) - 2


def subtree_lines(label: str, items: list, entry_type: str, key: str = 'item') -> list[dict]:
    """Build a netrw-style subtree as flat row dicts: a 'subhdr' row carrying
    `label`, then one `entry_type` row per item (stored under `key`), each with
    a 'last' flag for the └/├ tree glyph. Empty `items` yields no rows.

    Shared by the overworld's custom/ section and the scroll library's
    codex//relics/ sections so the subtree shape lives in one place."""
    if not items:
        return []
    rows = [{'type': 'subhdr', 'label': label}]
    last = len(items) - 1
    for i, it in enumerate(items):
        rows.append({'type': entry_type, key: it, 'last': i == last})
    return rows


def tree_glyph(last: bool) -> str:
    """Branch character for a subtree entry: └ for the last item, ├ otherwise."""
    return '└' if last else '├'
