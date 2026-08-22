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

from vimny.render import colors as C
from vimny.render import symbols as S

def inner_w(term: Terminal) -> int:
    """Inner playfield width: terminal width clamped to [80, 189], minus 2 borders.
    80 is the minimum supported terminal width; 189 the maximum we lay out to (wide
    enough for the overworld and The Archivist's Library)."""
    return min(max(term.width, 80), 189) - 2

MIN_COLS = 80
MIN_ROWS = 24

def print_size_notice(term: Terminal) -> bool:
    """Guard for terminals below Vimny's minimum size. When the window is too
    small to hold an 80-column frame (which would wrap into garbage), paints a
    plain notice instead — every frame-flush site calls this first and bails
    out when it returns True. Re-evaluated on every render, so widening the
    window resumes the game on the next keystroke with no special handling.

    Fail-open: if the terminal reports no size at all (pipes, some embedded
    hosts), we assume it knows what it's doing rather than blocking play."""
    w = getattr(term, 'width', None)
    h = getattr(term, 'height', None)
    if not isinstance(w, int) or not isinstance(h, int):
        return False
    if w >= MIN_COLS and h >= MIN_ROWS:
        return False
    msg = (f'Vimny needs a {MIN_COLS}x{MIN_ROWS} terminal to play. '
           f'This window is {w}x{h} - widen or grow it.')
    if w < len(msg) + 4 or h < 5:
        # Too cramped even for the box: one truncated line, no positioning.
        print(msg[:max(1, w)], end='', flush=True)
        return True
    left = ' ' * max(0, (w - len(msg) - 4) // 2)
    top_pad = [''] * max(0, min(2, (h - 3) // 2))
    frame = '\n'.join(top_pad + [
        left + S.BOX_TL + S.BOX_H * (len(msg) + 2) + S.BOX_TR,
        left + S.BOX_V + ' ' + msg + ' ' + S.BOX_V,
        left + S.BOX_BL + S.BOX_H * (len(msg) + 2) + S.BOX_BR,
    ])
    print(term.home + term.clear + frame, end='', flush=True)
    return True


def heart_counts(hp: int, max_hp: int) -> tuple[int, int, int]:
    """(full, half, empty) heart glyphs for an HP total. ONE source of truth —
    the dungeon status bar and the netrw aux screens used to disagree by half
    a heart whenever hp was odd (the aux bars floored, the dungeon showed ♡)."""
    full, half = divmod(max(0, hp), 2)
    return full, half, max(0, max_hp // 2 - full - half)


def hearts_plain(full: int, half: int, empty: int) -> str:
    """The colour-stripped heart run — for width maths (padding, centring)."""
    return S.HEART_FULL * full + S.HEART_HALF * half + S.HEART_EMPTY * empty


def hearts_colored(full: int, half: int, empty: int, rst: str, *,
                   full_c: str = '', half_c: str = '', empty_c: str = '') -> str:
    """The same run, each heart in its palette colour (rst after every glyph,
    so a truncated draw can't bleed colour past the cell). Pass all three
    overrides to recolour the whole run — the heart-flash does that in gold."""
    fc = full_c or C.heart_full()
    hc = half_c or C.heart_half()
    ec = empty_c or C.heart_empty()
    return ((fc + S.HEART_FULL + rst) * full +
            (hc + S.HEART_HALF + rst) * half +
            (ec + S.HEART_EMPTY + rst) * empty)


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
