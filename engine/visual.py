"""Block D2 — visual-mode selection → operator application.

A visual selection runs from the anchor (where v/V/Ctrl-v was pressed) to the
cursor. d/y/c/~/>/< act on that span. Charwise (v) on one row is an INCLUSIVE
column span; linewise (V) is whole rows; block (Ctrl-v) is a rectangle.
"""
from __future__ import annotations
from engine.modes import Mode
from engine.text_object import TextObject, TextObjectType
from engine.operator import (
    op_delete, op_yank, op_case, apply_indent, line_extent, _delete_cols, _capture_row,
)


def block_bounds(anchor, cursor):
    ar, ac = anchor
    cr, cc = cursor
    return min(ar, cr), max(ar, cr), min(ac, cc), max(ac, cc)


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
    # charwise: single row → col span; multi-row → whole rows
    if ar == cr:
        return min(ac, cc) <= c <= max(ac, cc)
    return True


def apply_visual(op: str, anchor, cursor, vmode, room, player):
    """Apply `op` to the visual selection. Returns a register clip for d/y/c
    (None for ~ / > / <). Repositions the cursor to the selection start."""
    if vmode == Mode.VISUAL_BLOCK:
        return _apply_block(op, anchor, cursor, room, player)

    tobj = visual_span(anchor, cursor, vmode, room)
    if op == 'y':
        clip = op_yank(room, player, tobj)
        player.row, player.col = tobj.start_row, tobj.start_col
        return clip
    if op in ('d', 'c'):
        return op_delete(room, player, tobj)       # repositions cursor to start
    if op == 'g~':
        op_case(room, player, tobj, 'g~')
        return None
    if op in ('>', '<'):
        amount = 2 if op == '>' else -2
        for r in range(tobj.start_row, tobj.end_row + 1):
            apply_indent(room, r, amount)
        player.row = tobj.start_row
        ext = line_extent(room, player.row)
        player.col = ext[0] if ext else player.col
        return None
    return None


def _apply_block(op: str, anchor, cursor, room, player):
    r1, r2, c1, c2 = block_bounds(anchor, cursor)
    rows = [_capture_row(room, r, c1, c2) for r in range(r1, r2 + 1)]
    if op in ('d', 'c'):
        for r in range(r1, r2 + 1):
            _delete_cols(room, r, c1, c2)
    elif op == 'g~':
        for r in range(r1, r2 + 1):
            op_case(room, player, TextObject(r, c1, r, c2, TextObjectType.INCLUSIVE), 'g~')
    player.row, player.col = r1, c1
    if op in ('d', 'y', 'c'):
        return {'linewise': r1 != r2, 'rows': rows}
    return None
