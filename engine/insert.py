"""Block G — insert-mode entry (i a I A o O s S) and INSERT-mode editing.

Entry commands position the cursor (and, for o/O/s/S, mutate the room) before
INSERT begins. While in INSERT, printable keys place a one-cell character and the
cursor advances; Backspace removes the cell to the left. The grid is fixed, so
"insert" is overwrite-and-advance (matching the admin editor), not text-shift.
"""
from __future__ import annotations
from engine.world import CellType, CharRun
from engine.motion import _first_non_blank_col, _leftmost_passable, _rightmost_passable
from engine.editor import _merge_adjacent_char_runs
from engine.reflow import is_ledge, open_gap, close_gap, extend_floor, _insert_blank_row

INSERT_KIND = 'ember'           # kind tag for player-typed characters
_PASTABLE = (CellType.FLOOR, CellType.CORRIDOR)
_VARIANTS_MUTATING = frozenset('oOsS')   # entry commands that change the room


def _last_content_col(room, row: int):
    """Rightmost column on `row` holding a character, or None."""
    ends = [ru.col + len(ru.symbols) - 1 for ru in room.char_runs if ru.row == row]
    return max(ends) if ends else None


def _delete_at(room, row: int, col: int) -> None:
    """Remove the single character at (row, col), splitting its run."""
    ru = room.char_run_at(row, col)
    if ru is None:
        return
    idx = col - ru.col
    room.remove_char_run(ru)
    if idx > 0:
        room.add_char_run(CharRun(row, ru.col, tuple(ru.symbols[:idx]), ru.kind))
    if idx + 1 < len(ru.symbols):
        room.add_char_run(CharRun(row, col + 1, tuple(ru.symbols[idx + 1:]), ru.kind))


def _clear_row(room, row: int) -> None:
    """Remove all character runs on a row (direct mutation; no operator system)."""
    room.char_runs = [ru for ru in room.char_runs if ru.row != row]
    room.rebuild_indexes()


def begin_insert(room, player, variant: str, count: int = 1) -> None:
    """Apply an insert-entry command: position the cursor and perform any
    pre-edit (o/O insert a row, s deletes chars, S clears the row).

    `A` is the lone ledge-builder: it sets player.insert_extend so each typed
    char carves new floor into the void (see insert_char_extend); every other
    variant clears the flag."""
    player.insert_extend = (variant == 'A')
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
        # End of the LINE = just past the rightmost passable cell (the corridor /
        # ledge edge), NOT just past the last character: trailing floor counts as
        # trailing spaces, and Vim's A skips past them. Typing there builds new
        # ledge into the void.
        right = _rightmost_passable(room, r)
        if right is not None:
            player.col = min(right + 1, room.cols - 1)
        else:
            c = _leftmost_passable(room, r)
            if c is not None:
                player.col = c
        return
    if variant == 'o':
        _insert_blank_row(room, r + 1, r, player)
        player.row = r + 1
        c = _leftmost_passable(room, player.row)
        player.col = c if c is not None else 0
        return
    if variant == 'O':
        _insert_blank_row(room, r, r, player)
        c = _leftmost_passable(room, r)
        player.col = c if c is not None else 0
        return
    if variant == 's':
        for i in range(count):
            _delete_at(room, r, player.col + i)
        close_gap(room, r, player.col, count)   # reflow: pull the tail left before INSERT
        return
    if variant == 'S':
        _clear_row(room, r)
        c = _leftmost_passable(room, r)
        if c is not None:
            player.col = c
        return


def insert_char(room, player, ch: str, kind: str = INSERT_KIND) -> bool:
    """Place a one-cell character at the cursor and advance.

    Overlay rows (the default everywhere) overwrite the cell in place. On a
    ledge row the line reflows: the cursor cell and everything right of it slide
    right by one, and any character shoved past the void brink falls in (see
    engine/reflow.py). Returns False if the cursor is not on a pastable cell."""
    r, c = player.row, player.col
    if not (0 <= c < room.cols) or room.cells[r][c] not in _PASTABLE:
        return False
    if is_ledge(room, r):
        ru = room.char_run_at(r, c)
        if ru is not None and ru.kind == 'void':   # cursor sits on a void rune → glyph drops in
            room._last_void_falls.append((r, c, ch))
            return True
        open_gap(room, r, c, 1)                # push the line right; overflow falls
    else:
        _delete_at(room, r, c)                 # overwrite the cell in place
    room.add_char_run(CharRun(r, c, (ch,), kind))
    _merge_adjacent_char_runs(room, r)
    if c + 1 < room.cols and room.cells[r][c + 1] in _PASTABLE:
        player.col += 1
    return True


def insert_char_extend(room, player, ch: str, kind: str = INSERT_KIND) -> bool:
    """`A`'s ledge-building keystroke: build a floor tile at the cursor (carving a
    wall, doubling the buffer at the right border) and advance onto the next cell.
    Unlike insert_char this never reflows or drops content over the brink — A only
    *adds* ledge. Returns False only when a void rune blocks the build."""
    r, c = player.row, player.col
    if not extend_floor(room, r, c, ch, kind):
        return False
    if c + 1 < room.cols:
        player.col = c + 1
    return True


def _cell_rune(room, row: int, col: int):
    """(symbol, kind) at (row, col) or None if the cell holds no character."""
    ru = room.char_run_at(row, col)
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
        room.add_char_run(CharRun(r, col, (ch,), INSERT_KIND))
        last, changed = col, True
    _merge_adjacent_char_runs(room, r)
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
    room.add_char_run(CharRun(r, c, (ch,), INSERT_KIND))
    _merge_adjacent_char_runs(room, r)
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
        room.add_char_run(CharRun(player.row, col, (sym,), kind))
    _merge_adjacent_char_runs(room, player.row)


def insert_backspace(room, player) -> bool:
    """Step left and remove the character cell there. Returns False at line start."""
    if player.col <= 0 or not room.is_passable(player.row, player.col - 1):
        return False
    player.col -= 1
    _delete_at(room, player.row, player.col)
    _merge_adjacent_char_runs(room, player.row)
    return True
