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

"""Block D2 — visual-mode selection → operator application.

A visual selection runs from the anchor (where v/V/Ctrl-v was pressed) to the
cursor. d/y/c/~/>/< act on that span. Charwise (v) on one row is an INCLUSIVE
column span; linewise (V) is whole rows; block (Ctrl-v) is a rectangle.
"""
from __future__ import annotations
from vimny.engine.modes import Mode
from vimny.engine.text_object import TextObject, TextObjectType
from vimny.engine.operator import (
    op_delete, op_yank, op_case, apply_indent, line_extent, _delete_cols, _capture_row,
    _cursor_to_line_start, INDENT_WIDTH,
)
from vimny.engine.reflow import is_ledge, close_gap


def block_bounds(anchor, cursor):
    ar, ac = anchor
    cr, cc = cursor
    return min(ar, cr), max(ar, cr), min(ac, cc), max(ac, cc)


def swap_ends(anchor, cursor, vmode, corner: bool = False):
    """`o` / `O` — move the cursor to the other end of the selection.

    Returns the new `(anchor, cursor)`.

    `o` trades the two ends outright, in every visual mode. `O` does the same
    EXCEPT in block mode, where it swaps only the columns: the cursor stays on
    its own row and crosses to the other side of the rectangle, which is what
    makes it worth having — it is the only way to widen a block from the edge
    you did not start on without leaving visual mode.

    This is selection SHAPING and nothing more. Every operator reads the span
    through `block_bounds` / `visual_span`, both of which take min and max of
    the two ends, so no arrangement of the same two corners can change what an
    operator does. That is what `test_visual_corner_swap.py` pins, and it is
    why the verb can be handed out without re-auditing a single par.
    """
    if corner and vmode == Mode.VISUAL_BLOCK:
        return (anchor[0], cursor[1]), (cursor[0], anchor[1])
    return cursor, anchor


def visual_span(anchor, cursor, vmode, room) -> TextObject:
    """TextObject for a charwise/linewise selection (not block)."""
    ar, ac = anchor
    cr, cc = cursor
    r1, r2 = (ar, cr) if ar <= cr else (cr, ar)
    if vmode == Mode.VISUAL_LINE or ar != cr:     # linewise, or multi-row charwise ≈ linewise
        return TextObject(r1, 0, r2, room.cols - 1, TextObjectType.LINEWISE)
    return TextObject(ar, min(ac, cc), ar, max(ac, cc), TextObjectType.INCLUSIVE)


def in_selection(anchor, cursor, vmode, r, c) -> bool:
    """Whether grid cell (r, c) lies within the visual selection (for highlight)."""
    if anchor is None:
        return False
    ar, ac = anchor
    cr, cc = cursor
    r1, r2 = min(ar, cr), max(ar, cr)
    if not (r1 <= r <= r2):
        return False
    if vmode == Mode.VISUAL_LINE:
        return True
    if vmode == Mode.VISUAL_BLOCK:
        return min(ac, cc) <= c <= max(ac, cc)
    # charwise single row
    if ar == cr:
        return min(ac, cc) <= c <= max(ac, cc)
    # charwise multi-row: top row from anchor col, bottom row to cursor col
    c_top = ac if ar <= cr else cc
    c_bot = cc if ar <= cr else ac
    if r == r1: return c_top <= c
    if r == r2: return c <= c_bot
    return True


def _apply_charwise_multi(op: str, anchor, cursor, room, player):
    """Delete/yank a charwise multi-row selection with per-row column bounds.

    Top row:    from anchor_col to passable end.
    Middle rows: full passable extent.
    Bottom row: from passable start to cursor_col.
    """
    ar, ac = anchor
    cr, cc = cursor
    if ar <= cr:
        r1, c_top, r2, c_bot = ar, ac, cr, cc
    else:
        r1, c_top, r2, c_bot = cr, cc, ar, ac

    rows = []
    for r in range(r1, r2 + 1):
        ext = line_extent(room, r)
        if ext is None:
            rows.append({'width': 0, 'char_runs': []})
            continue
        lo = c_top if r == r1 else ext[0]
        hi = c_bot if r == r2 else ext[1]
        lo = max(lo, ext[0])
        hi = min(hi, ext[1])
        if lo <= hi:
            rows.append(_capture_row(room, r, lo, hi))
            if op in ('d', 'c'):
                _delete_cols(room, r, lo, hi)
        else:
            rows.append({'width': 0, 'char_runs': []})

    if op in ('d', 'c'):
        player.row = r1
        ext = line_extent(room, r1)
        player.col = max(c_top, ext[0]) if ext else c_top
    elif op == 'y':
        player.row, player.col = r1, c_top
    return {'linewise': False, 'rows': rows}


def apply_visual(op: str, anchor, cursor, vmode, room, player):
    """Apply `op` to the visual selection. Returns a register clip for d/y/c
    (None for ~ / > / <). Repositions the cursor to the selection start."""
    # A delete whose span covers an edit-immune boss is parried: the rest of the
    # span still dies (handled below), the boss survives, and the caller reports it.
    player.last_parry = (op in ('d', 'c') and any(
        e.alive and e.edit_immune and in_selection(anchor, cursor, vmode, e.row, e.col)
        for e in room.entities))
    if vmode == Mode.VISUAL_BLOCK:
        return _apply_block(op, anchor, cursor, room, player)

    ar, ac = anchor
    cr, cc = cursor

    # Charwise multi-row: use per-row column bounds, not linewise
    if vmode == Mode.VISUAL and ar != cr and op in ('d', 'c', 'y'):
        return _apply_charwise_multi(op, anchor, cursor, room, player)
    if vmode == Mode.VISUAL and ar != cr and op in ('g~', 'gU', 'gu'):
        # Vim-true: v-selection ~/U/u case-ops ONLY the selected span — top
        # row from the anchor column to line end, middle rows whole, bottom
        # row from line start to the cursor column (never the full lines:
        # text outside the selection keeps its case).
        if ar <= cr:
            r1, c_top, r2, c_bot = ar, ac, cr, cc
        else:
            r1, c_top, r2, c_bot = cr, cc, ar, ac
        for r in range(r1, r2 + 1):
            ext = line_extent(room, r)
            if ext is None:
                continue
            lo = max(c_top, ext[0]) if r == r1 else ext[0]
            hi = min(c_bot, ext[1]) if r == r2 else ext[1]
            if lo <= hi:
                op_case(room, player, TextObject(r, lo, r, hi,
                                                 TextObjectType.INCLUSIVE), op)
        player.row, player.col = r1, c_top
        return None

    tobj = visual_span(anchor, cursor, vmode, room)
    if op == 'y':
        clip = op_yank(room, player, tobj)
        player.row, player.col = tobj.start_row, tobj.start_col
        return clip
    if op in ('d', 'c'):
        if op == 'd' and tobj.type is TextObjectType.LINEWISE:
            return op_delete(room, player, tobj, collapse=True)   # remove_row drops the rows' entities
        clip = op_delete(room, player, tobj)   # op_delete → _delete_cols removes/unmasks span entities
        return clip
    if op in ('g~', 'gU', 'gu'):
        op_case(room, player, tobj, op)
        return None
    if op in ('>', '<'):
        amount = INDENT_WIDTH if op == '>' else -INDENT_WIDTH
        for r in range(tobj.start_row, tobj.end_row + 1):
            apply_indent(room, r, amount)
        _cursor_to_line_start(room, player, tobj.start_row)
        return None
    return None


def apply_visual_replace(room, player, anchor, cursor, vmode, ch: str) -> bool:
    """v/V/<C-v> + r{ch}: overstrike every selected CHARACTER with `ch`
    (blank floor has no glyph and stays blank; voids are not text). The
    cursor parks on the selection's start. Returns True if anything changed."""
    r1, r2 = min(anchor[0], cursor[0]), max(anchor[0], cursor[0])
    changed = False
    for r in range(r1, r2 + 1):
        for c in range(room.cols):
            if not in_selection(anchor, cursor, vmode, r, c):
                continue
            if not room.is_passable(r, c):
                continue
            ru = room.char_run_at(r, c)
            if ru is None or ru.kind == 'void':
                continue
            k = c - ru.col
            syms = list(ru.symbols)
            if syms[k] != ch:
                syms[k] = ch
                ru.symbols = tuple(syms)
                changed = True
    start = anchor if (anchor[0], anchor[1]) <= (cursor[0], cursor[1]) else cursor
    if vmode == Mode.VISUAL_LINE:
        _cursor_to_line_start(room, player, r1)
    elif vmode == Mode.VISUAL_BLOCK:
        player.row, player.col = r1, min(anchor[1], cursor[1])
    else:
        player.row, player.col = start
    return changed


def _apply_block(op: str, anchor, cursor, room, player):
    r1, r2, c1, c2 = block_bounds(anchor, cursor)
    if op in ('>', '<'):                  # block indent shifts the whole LINES (Vim)
        amount = INDENT_WIDTH if op == '>' else -INDENT_WIDTH
        for r in range(r1, r2 + 1):
            apply_indent(room, r, amount)
        _cursor_to_line_start(room, player, r1)
        return None
    rows = [_capture_row(room, r, c1, c2) for r in range(r1, r2 + 1)]
    if op in ('d', 'c'):
        for r in range(r1, r2 + 1):
            _delete_cols(room, r, c1, c2)
            if is_ledge(room, r):
                close_gap(room, r, c1, c2 - c1 + 1)   # Vim-true: each row's
                # tail pulls left independently after a block delete
    elif op in ('g~', 'gU', 'gu'):
        for r in range(r1, r2 + 1):
            op_case(room, player, TextObject(r, c1, r, c2, TextObjectType.INCLUSIVE), op)
    player.row, player.col = r1, c1
    if op in ('d', 'y', 'c'):
        return {'linewise': r1 != r2, 'rows': rows}
    return None
