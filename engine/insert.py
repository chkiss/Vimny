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

"""Block G — insert-mode entry (i a I A o O s S) and INSERT-mode editing.

Entry commands position the cursor (and, for o/O/s/S, mutate the room) before
INSERT begins. While in INSERT, printable keys place a one-cell character and the
cursor advances; Backspace removes the cell to the left. The grid is fixed, so
"insert" is overwrite-and-advance (matching the admin editor), not text-shift.
"""
from __future__ import annotations
from engine.world import CellType, CharRun
from engine.motion import _first_non_blank_col, _leftmost_passable, _rightmost_passable
from engine.editor import _merge_adjacent_char_runs, _split_run_at
from engine.reflow import is_ledge, open_gap, close_gap, extend_floor, _insert_blank_row

INSERT_KIND = 'ember'           # kind tag for player-typed characters
_PASTABLE = (CellType.FLOOR, CellType.CORRIDOR)
_VARIANTS_MUTATING = frozenset('oOsS')   # entry commands that change the room


def _delete_at(room, row: int, col: int) -> None:
    """Remove the single character at (row, col), splitting its run."""
    _split_run_at(room, row, col)


def _clear_row(room, row: int) -> None:
    """Clear the cursor LINE's content — the passable run between the stone walls
    (`line_extent`), leaving anything embedded in the walls untouched. `S` IS `cc`:
    both clear the line in place and are bounded by the wall segment, NOT the whole
    buffer row, so a plaque/clue set in a wall cell survives an `S` exactly as it
    survives a `cc` (the Change Annex / Extension plaque rule). The import is local
    to keep the engine module load order flat."""
    from engine.operator import line_extent, _delete_cols
    ext = line_extent(room, row)
    if ext is not None:
        _delete_cols(room, row, ext[0], ext[1])


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

    Reflow is universal (`is_ledge` always True): the line reflows so the cursor
    cell and everything right of it slide right by one, and any character shoved
    past the void brink falls in (see engine/reflow.py).

    WATER is writable — ink displaces the flood: typing at a water cell pushes
    the water rightward like any movable content (open_gap shifts water; a cell
    spilling into a wall is lost over the brink) and the vacated cell is left
    FLOOR with the new character on it. The cursor advances over water too, so
    a word typed at the bank reclaims the flood cell by cell (The Inscription
    Halls' river). The mirror of `A` carving floor into walls.

    The `else` overwrite-in-place branch is a retired-overlay future hook,
    currently unreachable. Returns False if the cursor is on a wall."""
    r, c = player.row, player.col
    writable = (*_PASTABLE, CellType.WATER)
    if not (0 <= c < room.cols) or room.cells[r][c] not in writable:
        return False
    if is_ledge(room, r):
        ru = room.char_run_at(r, c)
        if ru is not None and ru.kind == 'void':   # cursor sits on a void rune → glyph drops in
            room._last_void_falls.append((r, c, ch))
            return True
        open_gap(room, r, c, 1)                # push the line right; overflow falls
        # (a water cell at c slid right with the push; _push_one left c FLOOR)
    else:
        _delete_at(room, r, c)                 # overwrite the cell in place
    room.add_char_run(CharRun(r, c, (ch,), kind))
    _merge_adjacent_char_runs(room, r)
    if c + 1 < room.cols and room.cells[r][c + 1] in writable:
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


def insert_delete_word_back(room, player) -> bool:
    """<C-w>: delete the word before the cursor (and any spaces just before it),
    stopping at an empty cell, wall or line start. Returns True if anything went."""
    def _sym_left():
        c = player.col - 1
        if c < 0:
            return None
        ru = room.char_run_at(player.row, c)
        return ru.symbols[c - ru.col] if ru is not None else None

    moved = False
    while player.col > 0 and _sym_left() == ' ':       # eat trailing spaces
        if not insert_backspace(room, player):
            break
        moved = True
    while player.col > 0:                              # eat the word's characters
        s = _sym_left()
        if s is None or s == ' ':
            break
        if not insert_backspace(room, player):
            break
        moved = True
    return moved


def insert_delete_to_start(room, player) -> bool:
    """<C-u>: delete from the cursor back to the start of the line. Returns True
    if anything went."""
    moved = False
    while insert_backspace(room, player):
        moved = True
    return moved
