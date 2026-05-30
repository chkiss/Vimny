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
               into one is lost over the brink (off the wall / into the hole).

The left wall anchors the line; the right brink is where content falls off.
`r`/`R` overwrite in place (correct Vim) and don't come through here.

Lost glyphs/water land in ``room._last_void_falls`` and swept entities in
``room._last_drowns`` so the presentation layer can animate them; the engine
never touches the terminal. ``is_ledge`` is universally True — ``room.ledge_rows``
is kept only as a hook for future per-row behaviour (the ledge-extending motions).
"""
from __future__ import annotations
from engine.world import CharRun, CellType
from engine.editor import _merge_adjacent_runes

_FLOORS = (CellType.FLOOR, CellType.CORRIDOR)
_WALLS  = (CellType.WALL, CellType.WOOD_WALL)


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
    runes = [ru.col for ru in room._char_runs_by_row.get(row, []) if ru.kind != 'void']
    c = min(runes) if runes else 0
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
    """Replace the row's non-void glyphs with one rune per ``[col, sym, kind]``,
    then merge. Void runes (and water cells) are untouched here."""
    for ru in [r for r in room._char_runs_by_row.get(row, []) if r.kind != 'void']:
        room.remove_char_run(ru)
    for c, sym, kind in cells:
        room.add_char_run(CharRun(row, c, (sym,), kind))
    _merge_adjacent_runes(room, row)


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
    — a glyph or a water cell — at or right of at_col slides right by one. Blanks
    are spaces: they shift implicitly as glyphs vacate and occupy cells, so a word
    separated from the cursor by whitespace is STILL pushed (the shift travels
    through the gap; it doesn't stop at it). Each mover's fate is set by its
    destination: a brink loses it (room._last_void_falls); an entity is swept away
    by water (room._last_drowns) but stops a glyph (which falls)."""
    glyphs = _row_glyphs(room, row)
    waters = [c for c in range(room.cols) if room.cells[row][c] == CellType.WATER]
    final_glyphs = [[c, s, k] for (c, s, k) in glyphs if c < at_col]      # left side stays put
    keep_water   = {c for c in waters if c < at_col}
    movers = ([('glyph', c, s, k) for (c, s, k) in glyphs if c >= at_col]
              + [('water', c, None, None) for c in waters if c >= at_col])
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
            if ent.kind == 'exit':
                room.exit_pos = None
            elif ent.kind == 'entry_marker':
                room.spawn_pos = (1, 1)
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
    column >= at_col+width move left by `width` (toward the anchored wall). Cells
    inside the hole are assumed already removed by the caller. Nothing falls."""
    kept = []
    for col, sym, k in _row_glyphs(room, row):
        if col >= at_col + width:
            kept.append([col - width, sym, k])
        elif col < at_col:
            kept.append([col, sym, k])
    _rewrite_glyphs(room, row, kept)
