"""Horizontal reflow for ledge rows (PILOT) — the sanctioned exception to the
fixed overlay grid.

On a ledge row (opt-in via ``room.ledge_rows``) editing flows like a real Vim
line. Inserting opens a one-cell gap and pushes everything to its right along in
a single cascade. What each thing does when shoved is decided by *what it is*,
uniformly — no per-row options:

  • a glyph  — slides right.
  • WATER    — slides right too (it's the one movable terrain); a wave of water
               shoved over a goblin DROWNS it, the water rolling onto its cell.
  • a stone wall / a void rune — FIXED. They never move; whatever is pushed into
               them is lost over the brink (off the edge / into the hole).
  • bare floor — absorbs the push (the cascade stops; nothing is lost).

Deleting (close_gap) pulls the tail left toward the anchored wall; nothing falls.

Lost glyphs/water are recorded on ``room._last_void_falls`` and drowned goblins
on ``room._last_drowns`` so the presentation layer can animate them; the engine
never touches the terminal. Non-ledge rows never reach this module, so the whole
shipped curriculum keeps the overlay grid untouched.
"""
from __future__ import annotations
from engine.world import CharRun, CellType
from engine.editor import _merge_adjacent_runes

_FLOORS = (CellType.FLOOR, CellType.CORRIDOR)
_WALLS  = (CellType.WALL, CellType.WOOD_WALL)


def is_ledge(room, row: int) -> bool:
    """True if `row` reflows (opens onto the void) instead of overlaying."""
    return row in getattr(room, 'ledge_rows', ())


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


def _glyph_at(room, row: int, c: int):
    ru = room.char_run_at(row, c)
    if ru is not None and ru.kind != 'void':
        return ru.symbols[c - ru.col], ru.kind
    return None


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


def _push_one(room, row: int, at_col: int) -> None:
    """Open a one-cell gap at at_col and cascade the push right by one cell."""
    # 1. Gather the movable run (glyphs + water) from at_col until a stop.
    chain, c, stop = [], at_col, None
    while stop is None:
        if _fixed_sink(room, row, c):
            stop = ('sink', c)
        elif room.cells[row][c] == CellType.WATER:
            chain.append(['water', c, None, None]); c += 1
        else:
            g = _glyph_at(room, row, c)
            if g is not None:
                chain.append(['glyph', c, g[0], g[1]]); c += 1
            elif room.entity_at(row, c) is not None:
                stop = ('entity', c)
            else:
                stop = ('empty', c)            # bare floor absorbs the push
    kind, sp = stop

    # 2. Resolve the right end — which token (if any) is consumed.
    survivors = chain
    if kind == 'sink' and chain:
        last, survivors = chain[-1], chain[:-1]
        if last[0] == 'water':
            room.cells[row][last[1]] = CellType.FLOOR
            room._last_void_falls.append((row, sp, '~'))         # water spills off the brink
        else:
            room._last_void_falls.append((row, sp, last[2]))     # glyph falls over the brink
    elif kind == 'entity' and chain:
        last = chain[-1]; survivors = chain[:-1]
        if last[0] == 'water':                                   # a wave sweeps the entity away
            ent = room.entity_at(row, sp)
            room.kill_entity(ent)
            if ent.kind == 'exit':
                room.exit_pos = None
            elif ent.kind == 'entry_marker':
                room.spawn_pos = (1, 1)
            room.cells[row][last[1]] = CellType.FLOOR
            room.cells[row][sp]      = CellType.WATER            # water rolls onto the swept cell
            room._last_drowns.append((row, sp))
        else:                                                    # text can't shove an entity → it falls
            room._last_void_falls.append((row, sp, last[2]))

    # 3. Shift the survivors right by one (glyphs via rewrite, water via cells).
    chain_cols = {t[1] for t in chain}
    final = [[col, sym, k] for (col, sym, k) in _row_glyphs(room, row) if col not in chain_cols]
    final += [[t[1] + 1, t[2], t[3]] for t in survivors if t[0] == 'glyph']
    _rewrite_glyphs(room, row, final)
    for t in chain:                                              # clear every chain water source first
        if t[0] == 'water':
            room.cells[row][t[1]] = CellType.FLOOR
    for t in survivors:                                          # then lay surviving water one cell right
        if t[0] == 'water':
            room.cells[row][t[1] + 1] = CellType.WATER


def open_gap(room, row: int, at_col: int, width: int = 1) -> list:
    """Open a `width`-cell gap at at_col, cascading the push right each time.
    Returns the list of cells lost over the brink (room._last_void_falls)."""
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
