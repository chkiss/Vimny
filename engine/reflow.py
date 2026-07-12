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

"""Reflow — Vimny's editing model: every row flows like a real Vim line.

Editing is universal reflow (not an opt-in, and not an overlay grid). Inserting
and pasting slide content right; deleting pulls it left. Blanks are spaces, so
the shift travels THROUGH them — a word separated from the cursor by whitespace
is still pushed. What each thing does when shoved is decided by *what it is*:

  • a glyph  — slides.
  • WATER    — slides too (the one movable terrain); a wave shoved over ANY entity
               sweeps it into the void (a goblin drowns, a key is lost), the water
               rolling onto its cell.
  • a stone wall / a void rune — FIXED brinks. They never move; whatever is pushed
               into one is lost over the brink (off the wall / into the hole). A
               brink also BOUNDS the reflow: each wall-bounded stretch flows as its
               own line, so an edit never disturbs content on the far side of a wall
               (push and pull are symmetric here — see _push_one / close_gap).

The left wall anchors the line; the right brink is where content falls off.
`r`/`R` overwrite in place (correct Vim) and don't come through here.

Lost glyphs/water land in ``room._last_void_falls`` and swept entities in
``room._last_drowns`` so the presentation layer can animate them; the engine
never touches the terminal. ``is_ledge`` is universally True (the per-row
overlay-vs-ledge distinction is retired).
"""
from __future__ import annotations
from engine.world import CharRun, CellType
from engine.editor import _merge_adjacent_char_runs, _replace_row_runs

_FLOORS = (CellType.FLOOR, CellType.CORRIDOR)
_WALLS  = (CellType.WALL, CellType.WOOD_WALL)

# The edge of the world: A / J cannot build a ledge past this buffer width. The
# buffer doubles on demand up to here, then refuses (room._last_build_blocked).
_MAX_COLS = 200


def is_ledge(room, row: int) -> bool:
    """Reflow is universal: every row flows like a Vim line and content falls off
    its fixed brinks (all walls + void runes). Kept as a single hook for future
    per-row behaviour (e.g. the ledge-extending motions, task #15)."""
    return True


def _void_rune_at(room, row: int, c: int) -> bool:
    ru = room.char_run_at(row, c)
    return ru is not None and ru.kind == 'void'


def _fixed_sink(room, row: int, c: int) -> bool:
    """A cell content can't move into — it's lost there. Stone walls and void
    runes are FIXED; out of bounds counts as a sink (the edge of the buffer)."""
    if not (0 <= c < room.cols):
        return True
    if room.cells[row][c] in _WALLS:
        return True
    return _void_rune_at(room, row, c)


def void_col(room, row: int) -> int:
    """The first FIXED brink to the right (a wall or a void rune), used for cursor
    safety. Water is NOT a brink — it's movable, so the scan passes straight
    through it; treating water as a brink wrongly marks everything past a puddle
    as 'the void'."""
    vcols = [ru.col for ru in room._char_runs_by_row.get(row, []) if ru.kind == 'void']
    char_cols = [ru.col for ru in room._char_runs_by_row.get(row, []) if ru.kind != 'void']
    c = min(char_cols) if char_cols else 0
    while c < room.cols and room.cells[row][c] in _WALLS:
        c += 1                         # skip any leading wall into the corridor
    while c < room.cols and room.cells[row][c] not in _WALLS and not _void_rune_at(room, row, c):
        c += 1                         # pass through floor AND water to the first fixed brink
    return min(min(vcols), c) if vcols else c


def _row_glyphs(room, row: int) -> list:
    """``[[col, sym, kind], ...]`` for every non-void glyph symbol on the row."""
    out = []
    for ru in room._char_runs_by_row.get(row, []):
        if ru.kind == 'void':
            continue
        for i, s in enumerate(ru.symbols):
            out.append([ru.col + i, s, ru.kind])
    return out


def _rewrite_glyphs(room, row: int, cells: list) -> None:
    """Replace the row's non-void glyphs with one character per ``[col, sym, kind]``,
    then merge. Void runes (and water cells) are untouched here."""
    kept_void = [r for r in room._char_runs_by_row.get(row, []) if r.kind == 'void']
    _replace_row_runs(room, row,
                      kept_void + [CharRun(row, c, (sym,), kind) for c, sym, kind in cells])
    _merge_adjacent_char_runs(room, row)


def _dest_fate(room, row: int, c: int) -> str:
    """Classify a rightward mover's DESTINATION cell:
    'sink'   — a wall, void rune, or the edge: the mover is lost over the brink.
    'entity' — an entity sits there: water drowns it, a glyph falls.
    'free'   — floor / water / blank: the mover simply slides in."""
    if _fixed_sink(room, row, c):
        return 'sink'
    if room.entity_at(row, c) is not None:
        return 'entity'
    return 'free'


def _push_one(room, row: int, at_col: int) -> None:
    """One-cell rightward push at at_col (the Vim line model). Every movable cell
    — a glyph or a water cell — at or right of at_col slides right by one, UP TO
    the first fixed brink east of at_col (a wall or a void rune). Blanks are
    spaces: they shift implicitly as glyphs vacate and occupy cells, so a word
    separated from the cursor by whitespace is STILL pushed (the shift travels
    through the gap; it doesn't stop at it). Each mover's fate is set by its
    destination: a brink loses it (room._last_void_falls); an entity is swept away
    by water (room._last_drowns) but stops a glyph (which falls).

    SEGMENT-BOUNDED, mirroring close_gap: the wall (or void rune) is a hard line
    boundary. Only the brink-bounded stretch containing at_col reflows — the glyph
    shoved against the wall falls INTO that wall cell (the void animation), but any
    run BEYOND the wall stays put. Each wall-bounded stretch flows as its own line,
    so a plaque set east of a wall is safe from an edit to its west (push and pull
    are now symmetric on this point)."""
    glyphs = _row_glyphs(room, row)
    waters = [c for c in range(room.cols) if room.cells[row][c] == CellType.WATER]
    brink = room.cols                                  # first fixed brink at/east of at_col
    for c in range(at_col, room.cols):
        if _fixed_sink(room, row, c):
            brink = c
            break
    final_glyphs = [[c, s, k] for (c, s, k) in glyphs if c < at_col or c >= brink]  # outside stays put
    keep_water   = {c for c in waters if c < at_col or c >= brink}
    movers = ([('glyph', c, s, k) for (c, s, k) in glyphs if at_col <= c < brink]
              + [('water', c, None, None) for c in waters if at_col <= c < brink])
    for kind, c, s, k in movers:
        nc   = c + 1
        fate = _dest_fate(room, row, nc)
        if kind == 'glyph':
            if fate == 'free':
                final_glyphs.append([nc, s, k])
            else:                                       # sink or entity — the glyph is lost
                room._last_void_falls.append((row, nc, s))
        elif fate == 'entity':                          # a wave sweeps the entity away
            ent = room.entity_at(row, nc)
            room.kill_entity(ent)
            room._on_entity_destroyed(ent)
            keep_water.add(nc)                          # water rolls onto the swept cell
            room._last_drowns.append((row, nc))
        elif fate == 'sink':
            room._last_void_falls.append((row, nc, '~'))   # water spills off the brink
        else:
            keep_water.add(nc)
    for c in waters:                                    # clear old water, then lay survivors
        room.cells[row][c] = CellType.FLOOR
    for c in keep_water:
        room.cells[row][c] = CellType.WATER
    _rewrite_glyphs(room, row, final_glyphs)


def open_gap(room, row: int, at_col: int, width: int = 1) -> list:
    """Open a `width`-cell gap at at_col (a single-cell push, repeated). Returns
    the cells lost over the brink (room._last_void_falls)."""
    for _ in range(max(1, width)):
        _push_one(room, row, at_col)
    return room._last_void_falls


def close_gap(room, row: int, at_col: int, width: int) -> None:
    """Pull the tail left to close a `width`-wide hole at at_col: glyphs at
    column >= at_col+width move left by `width` (toward the anchored wall).

    The pull stops at the first FIXED brink right of the hole — a wall or a void
    rune — exactly as the rightward push does (open_gap is segment-bounded too:
    it loses the glyph shoved into the brink and leaves the next segment put), so
    text beyond a mid-row wall segment or a void hole does NOT slide across it in
    EITHER direction: each brink-bounded stretch flows as its own line. Entities stay
    PERMEABLE to the pull (text slides past a door or a creature — shipped
    behaviour The Operator's Vault's par path relies on), a deliberate
    asymmetry with the push, which loses a glyph shoved onto an entity. Cells
    inside the hole are assumed already removed by the caller. Nothing falls."""
    limit = room.cols
    for c in range(at_col + width, room.cols):
        if _fixed_sink(room, row, c):
            limit = c
            break
    kept = []
    for col, sym, k in _row_glyphs(room, row):
        if at_col + width <= col < limit:
            kept.append([col - width, sym, k])
        elif col < at_col or col >= limit:
            kept.append([col, sym, k])
    _rewrite_glyphs(room, row, kept)


def _first_floor_col(room, row: int):
    """The row's 'column 0' — its first FLOOR/CORRIDOR cell (where `0`/`^` land),
    or None for an all-wall row."""
    if not (0 <= row < room.rows):
        return None
    for c in range(room.cols):
        if room.cells[row][c] in _FLOORS:
            return c
    return None


def _lands_on_floor(room, row: int, col: int) -> bool:
    """A glyph pushed to (row, col) survives only on BARE floor — never a wall, a
    void rune, an entity, or out of bounds (otherwise it falls into the void)."""
    if not (0 <= row < room.rows and 0 <= col < room.cols):
        return False
    if room.cells[row][col] not in _FLOORS:
        return False
    if _void_rune_at(room, row, col):
        return False
    return room.entity_at(row, col) is None


def split_line_down(room, player) -> list:
    """Insert-mode <Enter>: the bounded vertical line-split — the vertical mirror of
    `open_gap`. The HEAD (the cursor row's glyphs left of the cursor) stays put; the
    TAIL (its glyphs at/after the cursor) becomes the next line, re-aligned to
    column 0 (the row-below's first floor cell, Vim-faithful); every glyph in the
    rows BELOW shifts straight DOWN one row, same columns. The dungeon NEVER grows
    (unlike `o`/`_insert_blank_row`): a glyph pushed onto a wall / void rune /
    entity, or off the bottom, falls into the void (`room._last_void_falls`). Walls,
    void runes, and entities stay FIXED. The cursor moves to the new line's column
    0 (where Vim parks it). Returns the fallen cells."""
    r, c = player.row, player.col
    dest0 = _first_floor_col(room, r + 1)
    # The split is BOUNDED, like its horizontal mirror: the downward cascade
    # stops at the first all-wall row below the cursor (a hard line boundary,
    # exactly as a mid-row wall bounds open_gap) — rows past it are the far
    # side of the wall and stay untouched. And GLYPHS IN STONE ARE NEVER
    # TEXT: a wall-embedded carving (a plaque, a margin gloss) on any row
    # stays fixed instead of riding the shift into the void (an insert-mode
    # <Enter> once pushed a boss hall's border glosses off the world).
    boundary = room.rows
    for gr in range(r + 1, room.rows):
        if all(room.cells[gr][cc] in _WALLS for cc in range(room.cols)):
            boundary = gr
            break
    keep, moves = [], []
    for gr in range(room.rows):
        for col, sym, kind in _row_glyphs(room, gr):
            if room.cells[gr][col] in _WALLS:
                keep.append((gr, col, sym, kind))                 # carved in stone — fixed
            elif gr < r or (gr == r and col < c) or gr >= boundary:
                keep.append((gr, col, sym, kind))                 # above / head / past the wall
            elif gr == r:                                         # the tail → next line, col 0
                ncol = (dest0 + (col - c)) if dest0 is not None else col
                moves.append((r + 1, ncol, sym, kind))
            else:                                                 # below — straight down
                moves.append((gr + 1, col, sym, kind))
    falls, placed = [], list(keep)
    for nrow, ncol, sym, kind in moves:
        if _lands_on_floor(room, nrow, ncol):
            placed.append((nrow, ncol, sym, kind))
        else:                                                     # off the brink → the void
            rr = nrow if 0 <= nrow < room.rows else min(r + 1, room.rows - 1)
            cc = ncol if 0 <= ncol < room.cols else max(0, room.cols - 1)
            falls.append((rr, cc, sym))
    for gr in range(r, room.rows):                                # rewrite only the changed rows
        glyphs = [[col, sym, kind] for (pr, col, sym, kind) in placed if pr == gr]
        _rewrite_glyphs(room, gr, glyphs)
    room._last_void_falls = falls
    nr = min(r + 1, room.rows - 1)
    nc = _first_floor_col(room, nr)
    if nc is None:                                                # no floor below — cursor stays
        nr, nc = r, _first_floor_col(room, r)
    player.row, player.col = nr, (nc if nc is not None else player.col)
    return falls


def _shift_rows(room, player, moves, delta: int) -> None:
    """Re-index every row coordinate of map state by ``delta`` for each row where
    ``moves(row)`` is True: glyphs, the entities still present, exit/spawn, fog,
    and (when ``player`` is given) marks and jumps. The caller is responsible for
    the physical row insert/delete and for any on-pivot content removal; this only
    slides what remains. Shared by ``_insert_blank_row`` (delta +1) and
    ``remove_row`` (delta −1), which are vertical inverses."""
    for ru in room.char_runs:
        if moves(ru.row):
            ru.row += delta
    for e in room.entities:
        if moves(e.row):
            e.row += delta
    if room.exit_pos and moves(room.exit_pos[0]):
        room.exit_pos = (room.exit_pos[0] + delta, room.exit_pos[1])
    if room.spawn_pos and moves(room.spawn_pos[0]):
        room.spawn_pos = (room.spawn_pos[0] + delta, room.spawn_pos[1])
    room.fog_cells = {((r + delta) if moves(r) else r, c) for (r, c) in room.fog_cells}
    if player is not None:
        for nm, (r, c) in list(player.marks.items()):
            if moves(r):
                player.marks[nm] = (r + delta, c)
        player.jump_list = [((r + delta) if moves(r) else r, c) for (r, c) in player.jump_list]


def _blank_line_span(room, row: int, col: int):
    """The cursor's contiguous floor SEGMENT on ``row`` — the maximal run of
    walkable cells (FLOOR/CORRIDOR) containing ``col`` — as ``(left, right)``, or
    ``None`` if the cursor is not on floor. This is the width of the blank line
    o/O open: Vim's 'empty line', framed by the walls that bound the cursor's own
    segment (never wider than the floor already there)."""
    if not (0 <= row < room.rows) or not (0 <= col < room.cols):
        return None
    if room.cells[row][col] not in _FLOORS:
        return None
    left = right = col
    while left - 1 >= 0 and room.cells[row][left - 1] in _FLOORS:
        left -= 1
    while right + 1 < room.cols and room.cells[row][right + 1] in _FLOORS:
        right += 1
    return (left, right)


def _insert_blank_row(room, at_row: int, template_row: int, player=None,
                      blank: bool = False) -> None:
    """Insert a row at index ``at_row`` and shift all content at/below ``at_row``
    down by one — the vertical-ADD primitive. When ``player`` is given, its
    marks/jumps at or below the insert shift down too. Two shapes of new row:

      • ``blank=False`` (default) — CLONE the wall/floor structure of
        ``template_row``. This is the row-copy behind linewise paste (p/P) and the
        :s/:g line split, which reproduce an existing row's shape.
      • ``blank=True`` — a Vim BLANK line for o/O: FLOOR across the cursor's
        contiguous floor segment on ``template_row`` (``player.col`` the anchor),
        WALL elsewhere. It never copies interior walls and is never wider than the
        floor already there, so o/O can neither breach a border nor bridge a wall
        column — that horizontal axis is A's (``extend_floor``). Falls back to the
        clone shape when there is no player or the cursor is off floor.
    """
    template_row = max(0, min(template_row, room.rows - 1))
    span = (_blank_line_span(room, template_row, player.col)
            if (blank and player is not None) else None)
    if span is not None:
        left, right = span
        new_row = [CellType.FLOOR if left <= c <= right else CellType.WALL
                   for c in range(room.cols)]
    else:
        new_row = [CellType.WALL if room.cells[template_row][c] in _WALLS
                   else CellType.FLOOR
                   for c in range(room.cols)]
    room.cells.insert(at_row, new_row)
    room.rows += 1
    _shift_rows(room, player, lambda r: r >= at_row, +1)
    room.rebuild_indexes()


def remove_row(room, at_row: int, player=None) -> bool:
    """Collapse a ledge row — the vertical inverse of ``_insert_blank_row``.
    Drop row ``at_row`` and pull everything below it up by one (cells, glyphs,
    entities, exit/spawn, fog); ``room.rows`` shrinks. Entities on the removed
    row go with it (exit/spawn reset, mirroring the rest of the engine). When
    ``player`` is given, its marks/jumps below the cut shift up (an anchor on the
    cut row clamps to that slot). Refuses an all-wall border row or the last
    remaining row. Returns True if it collapsed. Powers ``dd`` / visual-line
    ``d`` (and the ``J`` join)."""
    if not (0 <= at_row < room.rows) or room.rows <= 1:
        return False
    if all(room.cells[at_row][c] in _WALLS for c in range(room.cols)):
        return False                                  # structural border row — never collapse
    if any(e.alive and e.edit_immune for e in room.entities if e.row == at_row):
        return False                                  # a boss stands here — its shield parries the cut
    del room.cells[at_row]
    room.rows -= 1
    # Drop the cut row's own content, then slide everything below it up by one.
    room.char_runs = [ru for ru in room.char_runs if ru.row != at_row]
    for e in list(room.entities):
        if e.row == at_row:
            room.remove_entity(e)
            room._on_entity_destroyed(e)
    room.fog_cells = {(r, c) for (r, c) in room.fog_cells if r != at_row}
    _shift_rows(room, player, lambda r: r > at_row, -1)
    room.rebuild_indexes()
    return True


def _double_cols(room) -> None:
    """Grow the buffer toward 2× its width, capped at the edge of the world
    (``_MAX_COLS``), padding every row with WALL — A makes the world wider."""
    target = min(room.cols * 2, _MAX_COLS)
    extra  = target - room.cols
    if extra <= 0:
        return
    for r in range(room.rows):
        room.cells[r].extend([CellType.WALL] * extra)
    room.cols = target
    room.rebuild_indexes()


def carve_floor(room, row: int, col: int) -> bool:
    """Make (row, col) buildable floor — the bare ledge-build, no glyph. Carves a
    wall into floor and DOUBLES the buffer at the right border (A makes the world
    wider); STOPS (returns False) at a void rune (○ is permanent). Shared by A's
    typing and J's join (the seam space / inter-glyph gaps)."""
    if not (0 <= row < room.rows) or col < 0:
        return False
    if _void_rune_at(room, row, col):
        room._last_build_blocked = 'void'             # permanent void — building stops here
        return False
    if col >= room.cols - 1:                          # at the right border — try to grow the world
        if room.cols >= _MAX_COLS:
            room._last_build_blocked = 'edge'         # the world cannot grow any wider
            return False
        _double_cols(room)
        if col >= room.cols - 1:                      # capped at the edge and still at the border
            room._last_build_blocked = 'edge'
            return False
    if room.cells[row][col] in _WALLS:
        room.cells[row][col] = CellType.FLOOR         # carve the ledge outward
        room.wood_damage.pop((row, col), None)
    room._last_build_blocked = None
    return True


def extend_floor(room, row: int, col: int, ch: str, kind: str = 'ember') -> bool:
    """Build one floor tile at (row, col) and lay ``ch`` on it — A's keystroke and
    J's append. On a wall it carves; on plain floor it just places. Returns False
    if a void rune blocks the build. Assumes the target holds no glyph (A is always
    past the last content)."""
    if not carve_floor(room, row, col):
        return False
    room.add_char_run(CharRun(row, col, (ch,), kind))
    _merge_adjacent_char_runs(room, row)
    return True
