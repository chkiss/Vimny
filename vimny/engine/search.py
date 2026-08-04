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

"""Block F — search (/ ? n N * #).

Searches character runs by **Vim regular expression** over the grid in reading
order (row-major), wrapping around. A match lands the cursor on the first cell
of the (effective) match. Plain words contain no regex metacharacters, so they
behave exactly like the substring search Vimny shipped before regex landed; a
pattern that can't be translated falls back to a literal substring too.

See vimny/engine/vimregex.py for the supported atoms (\\w \\d . ^ $ \\< \\> * \\+
[..] \\| \\(\\) \\zs \\ze \\c \\v …).
"""
from __future__ import annotations
from vimny.engine.vimregex import compile_vim
from vimny.engine.world import entity_letter


def _spans(s: str, pattern: str):
    """All non-overlapping (start, end) match spans of `pattern` in `s`."""
    vp = compile_vim(pattern)
    if vp is not None:
        return list(vp.finditer(s))
    out, start = [], 0                                  # literal fallback
    while True:
        i = s.find(pattern, start)
        if i < 0:
            return out
        out.append((i, i + len(pattern)))
        start = i + max(1, len(pattern))


def _line_string(room, row: int):
    """(text, base_col): the row read as ONE Vim line — every glyph in place, gaps
    between runs as spaces — so a pattern can span consecutive character runs (e.g.
    '/foo bar' across two words). All kinds are included (void glyphs are searchable
    text, as before). base_col maps an offset back to an absolute column.

    On a ``room.search_glyph_entities`` room (The Warden Pathfinder, The Warden
    Manifold), entity glyphs are overlaid too — so ``/W`` finds the Warden and its
    echoes wherever they leap. A FOGGED entity is skipped: the renderer draws blank
    stone there, and what you cannot see you cannot search (the Manifold's niched
    boss is unsearchable until his bolt draws and the fog parts).
    Default off: shipped levels search the char-run layer only (par stays identical)."""
    runs = room._char_runs_by_row.get(row, [])
    glyphs = []
    if getattr(room, 'search_glyph_entities', False):
        for e in room.entities:
            if e.alive and e.row == row and (e.row, e.col) not in room.fog_cells:
                g = entity_letter(e)             # shared map (engine.world) — same letters as f/t + render
                if g is not None:
                    glyphs.append((e.col, g))
    if not runs and not glyphs:
        return '', 0
    lo = min([ru.col for ru in runs] + [c for c, _ in glyphs])
    hi = max([ru.col + len(ru.symbols) for ru in runs] + [c + 1 for c, _ in glyphs])
    chars = [' '] * (hi - lo)
    for ru in runs:
        for i, s in enumerate(ru.symbols):
            chars[ru.col - lo + i] = s
    for c, g in glyphs:                      # entity glyph renders on top of the text layer
        chars[c - lo] = g
    return ''.join(chars), lo


def _match_positions(room, pattern: str) -> list:
    """All (row, col) match starts of `pattern`, matched per LINE (so a pattern may
    span consecutive runs and the same line may yield several matches), sorted in
    reading order. A match starting on an IMPASSABLE cell is skipped — the
    search jump lands the cursor on the match start, and a cell you cannot
    stand on is not a landing (fog, walls, water alike: plaque words sealed
    in wall bands used to teleport the player INTO the wall and past closed
    bolts). Same rule as line jumps (`_first_non_blank_col`) and `)`/`(`."""
    out = []
    for row in range(room.rows):
        s, base = _line_string(room, row)
        for start, _end in _spans(s, pattern):
            if room.is_passable(row, base + start):
                out.append((row, base + start))
    out.sort()
    return out


def find_next(room, player, pattern: str, forward: bool):
    """Next match from the cursor (wrapping) → (row, col), or None if no match."""
    if not pattern:
        return None
    positions = _match_positions(room, pattern)
    if not positions:
        return None
    cur = (player.row, player.col)
    if forward:
        ahead = [p for p in positions if p > cur]
        return ahead[0] if ahead else positions[0]          # wrap to first
    behind = [p for p in positions if p < cur]
    return behind[-1] if behind else positions[-1]          # wrap to last


def match_cells(room, pattern: str) -> set:
    """Every (row, col) covered by a NON-overlapping match of `pattern`, matched per
    LINE — the cell set for hlsearch / incsearch highlighting. A match spanning two
    runs lights the gap between them too (correct Vim behaviour)."""
    cells: set = set()
    if not pattern:
        return cells
    for row in range(room.rows):
        s, base = _line_string(room, row)
        for start, end in _spans(s, pattern):
            for k in range(start, max(start + 1, end)):     # ≥1 cell even if zero-width
                cells.add((row, base + k))
    return cells


def word_under_cursor(room, player):
    """Full symbol string of the cluster under the cursor (for * / #), or None."""
    ru = room.char_run_at(player.row, player.col)
    return ''.join(ru.symbols) if ru is not None else None
