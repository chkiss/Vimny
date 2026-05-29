"""Block G — insert-mode entry (i a I A o O s S) and INSERT-mode editing.

Entry commands position the cursor (and, for o/O/s/S, mutate the room) before
INSERT begins. While in INSERT, printable keys place a one-cell rune and the
cursor advances; Backspace removes the cell to the left. The grid is fixed, so
"insert" is overwrite-and-advance (matching the admin editor), not text-shift.
"""
from __future__ import annotations
from engine.world import CellType, RuneCluster
from engine.motion import _first_non_blank_col, _leftmost_passable
from engine.editor import _merge_adjacent_runes

INSERT_KIND = 'ember'           # kind tag for player-typed runes
_PASTABLE = (CellType.FLOOR, CellType.CORRIDOR)
_VARIANTS_MUTATING = frozenset('oOsS')   # entry commands that change the room


def _last_content_col(room, row: int):
    """Rightmost column on `row` holding a rune symbol, or None."""
    ends = [ru.col + len(ru.symbols) - 1 for ru in room.runes if ru.row == row]
    return max(ends) if ends else None


def _delete_at(room, row: int, col: int) -> None:
    """Remove the single rune symbol at (row, col), splitting its cluster."""
    ru = room.rune_at(row, col)
    if ru is None:
        return
    idx = col - ru.col
    room.remove_rune(ru)
    if idx > 0:
        room.add_rune(RuneCluster(row, ru.col, tuple(ru.symbols[:idx]), ru.kind))
    if idx + 1 < len(ru.symbols):
        room.add_rune(RuneCluster(row, col + 1, tuple(ru.symbols[idx + 1:]), ru.kind))


def _clear_row(room, row: int) -> None:
    """Remove all rune clusters on a row (direct mutation; no operator system)."""
    room.runes = [ru for ru in room.runes if ru.row != row]
    room.rebuild_indexes()


def _insert_blank_row(room, at_row: int, template_row: int) -> None:
    """Insert a blank row at index `at_row`, copying the wall pattern of
    `template_row`, and shift all content at/below `at_row` down by one."""
    template_row = max(0, min(template_row, room.rows - 1))
    new_row = [CellType.WALL if room.cells[template_row][c] in (CellType.WALL, CellType.WOOD_WALL)
               else CellType.FLOOR
               for c in range(room.cols)]
    room.cells.insert(at_row, new_row)
    room.rows += 1
    for ru in room.runes:
        if ru.row >= at_row:
            ru.row += 1
    for e in room.entities:
        if e.row >= at_row:
            e.row += 1
    if room.exit_pos and room.exit_pos[0] >= at_row:
        room.exit_pos = (room.exit_pos[0] + 1, room.exit_pos[1])
    if room.spawn_pos and room.spawn_pos[0] >= at_row:
        room.spawn_pos = (room.spawn_pos[0] + 1, room.spawn_pos[1])
    room.fog_cells = {((r + 1) if r >= at_row else r, c) for (r, c) in room.fog_cells}
    room.rebuild_indexes()


def begin_insert(room, player, variant: str, count: int = 1) -> None:
    """Apply an insert-entry command: position the cursor and perform any
    pre-edit (o/O insert a row, s deletes chars, S clears the row)."""
    r = player.row
    if variant == 'i':
        return
    if variant == 'a':
        if player.col + 1 < room.cols:
            player.col += 1
        return
    if variant == 'I':
        c = _first_non_blank_col(room, r)
        if c is not None:
            player.col = c
        return
    if variant == 'A':
        last = _last_content_col(room, r)
        if last is not None:
            player.col = min(last + 1, room.cols - 1)
        else:
            c = _leftmost_passable(room, r)
            if c is not None:
                player.col = c
        return
    if variant == 'o':
        _insert_blank_row(room, r + 1, r)
        player.row = r + 1
        c = _leftmost_passable(room, player.row)
        player.col = c if c is not None else 0
        return
    if variant == 'O':
        _insert_blank_row(room, r, r)
        c = _leftmost_passable(room, r)
        player.col = c if c is not None else 0
        return
    if variant == 's':
        for i in range(count):
            _delete_at(room, r, player.col + i)
        return
    if variant == 'S':
        _clear_row(room, r)
        c = _leftmost_passable(room, r)
        if c is not None:
            player.col = c
        return


def insert_char(room, player, ch: str, kind: str = INSERT_KIND) -> bool:
    """Place a one-cell rune at the cursor (overwriting any rune there) and
    advance. Returns False if the cursor is not on a pastable cell."""
    r, c = player.row, player.col
    if not (0 <= c < room.cols) or room.cells[r][c] not in _PASTABLE:
        return False
    _delete_at(room, r, c)
    room.add_rune(RuneCluster(r, c, (ch,), kind))
    _merge_adjacent_runes(room, r)
    if c + 1 < room.cols and room.cells[r][c + 1] in _PASTABLE:
        player.col += 1
    return True


def _cell_rune(room, row: int, col: int):
    """(symbol, kind) at (row, col) or None if the cell holds no rune."""
    ru = room.rune_at(row, col)
    return (ru.symbols[col - ru.col], ru.kind) if ru is not None else None


def replace_chars(room, player, ch: str, count: int = 1) -> bool:
    """`r{ch}`: overwrite `count` cells from the cursor with `ch` (no INSERT).
    Cursor ends on the last replaced cell. Stops at a wall."""
    r, c = player.row, player.col
    last, changed = c, False
    for i in range(count):
        col = c + i
        if col >= room.cols or room.cells[r][col] not in _PASTABLE:
            break
        _delete_at(room, r, col)
        room.add_rune(RuneCluster(r, col, (ch,), INSERT_KIND))
        last, changed = col, True
    _merge_adjacent_runes(room, r)
    if changed:
        player.col = last
    return changed


def replace_overtype(room, player, ch: str):
    """R-mode keystroke: record the cell's original content, overwrite with `ch`,
    advance. Returns a restore record (col, original|None) or None if not pastable."""
    r, c = player.row, player.col
    if c >= room.cols or room.cells[r][c] not in _PASTABLE:
        return None
    rec = (c, _cell_rune(room, r, c))
    _delete_at(room, r, c)
    room.add_rune(RuneCluster(r, c, (ch,), INSERT_KIND))
    _merge_adjacent_runes(room, r)
    if c + 1 < room.cols and room.cells[r][c + 1] in _PASTABLE:
        player.col += 1
    return rec


def replace_restore(room, player, rec) -> None:
    """R-mode Backspace: move to rec's column and restore its original content."""
    col, orig = rec
    player.col = col
    _delete_at(room, player.row, col)
    if orig is not None:
        sym, kind = orig
        room.add_rune(RuneCluster(player.row, col, (sym,), kind))
    _merge_adjacent_runes(room, player.row)


def insert_backspace(room, player) -> bool:
    """Step left and remove the rune cell there. Returns False at line start."""
    if player.col <= 0 or not room.is_passable(player.row, player.col - 1):
        return False
    player.col -= 1
    _delete_at(room, player.row, player.col)
    _merge_adjacent_runes(room, player.row)
    return True
