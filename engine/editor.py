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

"""Admin editor helpers: snapshot/restore, cut/paste, range operations."""
from __future__ import annotations
from engine.world import (
    CellType, CharRun, Entity, Room, RoomType, canonical_kind, clone_entity,
    normalize_row_word_kinds,
)

#: What `:paint` can lay down, name → (cell type, misted, one-line description).
#:
#: This is the whole vocabulary of the terrain, in one place, because the thing
#: it replaced — the `s` cycle — could only ever be as complete as whoever last
#: remembered to extend it, and it had no way to SAY what it knew. Misted water
#: was reachable by no key at all. A named list is enumerable: the menu, the
#: error message and the docs are all read off it, so a terrain that exists is a
#: terrain an author can find.
#:
#: MIST is not a sixth CellType — it is water (or floor) under permanent fog,
#: which is a pair of facts about a cell, so it is spelled as one paint.
PAINT_KINDS = {
    'floor':    (CellType.FLOOR,     False, 'open ground'),
    'corridor': (CellType.CORRIDOR,  False, 'walkable, drawn as passage'),
    'wall':     (CellType.WALL,      False, 'stone — blocks feet, bounds a line'),
    'wood':     (CellType.WOOD_WALL, False, 'destructible wall — two hits of x'),
    'water':    (CellType.WATER,     False, 'unwalkable; line motions cross it'),
    'mist':     (CellType.WATER,     True,  'fogged water — hazy, never lit or crossed'),
}


def _replace_row_runs(room, r: int, merged: list) -> None:
    """Swap row r's CharRuns for `merged`, updating the spatial indexes row-locally.
    Every reflow push and paste funnels through the merge, so this must NOT pay a
    full rebuild_indexes (which re-walks every run in the room)."""
    for ru in room._char_runs_by_row.get(r, ()):
        for i in range(len(ru.symbols)):
            room._char_run_map.pop((r, ru.col + i), None)
    if r in room._char_run_rows:
        room.char_runs = [ru for ru in room.char_runs if ru.row != r]
    room.char_runs.extend(merged)
    for ru in merged:
        for i in range(len(ru.symbols)):
            room._char_run_map[(r, ru.col + i)] = ru
    if merged:
        room._char_runs_by_row[r] = list(merged)
        room._char_run_rows.add(r)
    else:
        room._char_runs_by_row.pop(r, None)
        room._char_run_rows.discard(r)


def _merge_adjacent_char_runs(room, r: int) -> None:
    """Merge adjacent same-kind CharRuns on row r into single clusters, then
    normalize the row's WORD colors — row-scoped (no full index rebuild)."""
    row_runes = sorted(room._char_runs_by_row.get(r, []), key=lambda ru: ru.col)
    if len(row_runes) < 2:
        return
    merged = []
    cur_col  = row_runes[0].col
    cur_kind = row_runes[0].kind
    cur_syms = list(row_runes[0].symbols)
    for nxt in row_runes[1:]:
        if nxt.kind == cur_kind and nxt.col == cur_col + len(cur_syms):
            cur_syms.extend(list(nxt.symbols))
        else:
            merged.append(CharRun(row=r, col=cur_col,
                                      symbols=tuple(cur_syms), kind=cur_kind))
            cur_col  = nxt.col
            cur_kind = nxt.kind
            cur_syms = list(nxt.symbols)
    merged.append(CharRun(row=r, col=cur_col,
                              symbols=tuple(cur_syms), kind=cur_kind))
    _replace_row_runs(room, r, merged)
    normalize_row_word_kinds(room, r)


def _split_run_at(room, row: int, col: int):
    """Remove the single character at (row, col), re-adding the parts of its run
    on either side as split remnants. Returns the removed one-cell CharRun, or
    None if no character run covers that cell."""
    ru = room.char_run_at(row, col)
    if ru is None:
        return None
    idx = col - ru.col
    room.remove_char_run(ru)
    if idx > 0:
        room.add_char_run(CharRun(row=row, col=ru.col,
                                  symbols=tuple(ru.symbols[:idx]), kind=ru.kind))
    if idx + 1 < len(ru.symbols):
        room.add_char_run(CharRun(row=row, col=col + 1,
                                  symbols=tuple(ru.symbols[idx + 1:]), kind=ru.kind))
    return CharRun(row=row, col=col, symbols=(ru.symbols[idx],), kind=ru.kind)


def in_fill(room, row: int, col: int):
    """The fill directive covering (row, col), or None.

    Duck-typed on `room.fills` so this stays in the engine: `sharing.format`
    imports this module, not the other way round, and a Room that was never
    built from a level file simply has no `fills` and is never locked.

    Text inside a fill region belongs to the DIRECTIVE, which regrows it from
    the level's seed on every build. Editing it is therefore not just futile but
    invisible: the export drops everything standing in a fill region and lets
    the directive speak for it, so a hand-edited word there would vanish at save
    time without a word of complaint. Refusing the edit is the honest answer, and
    `:fill!` is the way to take the words for yourself.
    """
    for f in getattr(room, 'fills', ()):
        if f.covers(row, col):
            return f
    return None


def slot_at(room, row: int, col: int):
    """`(fill, slot, word)` for the word under (row, col); None outside a fill.

    How an author finds out what to write in a tape. A solution may name a
    grown word — `<fill0.7>` — and counting words across a region by eye to
    arrive at "slot 7" is a chore with a wrong answer at the end of it, so the
    forge answers it by standing on the word instead.

    The index is recomputed from where the words ARE — laying order is row,
    then column, which is the order a fill puts them down in — rather than
    remembered per run. A row edit re-merges its runs into fresh objects, so
    anything pinned to an object's identity would evaporate on the first
    keystroke; a position survives.

    `slot` is None on a gap between words: inside the region, but on nothing.

    The fill number is the LEVEL's, not the room's: a tape counts fills across
    every hall in walking order, and `fill_index0` is where this hall's own
    fills start in that count. A hall that reported its fills from zero would
    hand the author a reference that names a different fill in the file.
    """
    base = getattr(room, 'fill_index0', 0)
    for i, f in enumerate(getattr(room, 'fills', ()), start=base):
        if not f.covers(row, col):
            continue
        laid = sorted((ru for ru in room.char_runs if f.covers(ru.row, ru.col)),
                      key=lambda ru: (ru.row, ru.col))
        for k, ru in enumerate(laid):
            if ru.row == row and ru.col <= col < ru.col + len(ru.symbols):
                return (i, k, ''.join(ru.symbols))
        return (i, None, '')
    return None


def _ed_cut(room, r, c):
    """Remove the character/entity/wall at (r, c); return a clip item or None.

    For character runs: extracts only the single symbol at column c, leaving
    any remaining symbols as split remnants.
    """
    if in_fill(room, r, c):
        return None
    cut = _split_run_at(room, r, c)
    if cut is not None:
        return {'type': 'rune', 'rune': cut}
    ent = room.entity_at(r, c)
    if ent:
        room.remove_entity(ent)
        room._on_entity_destroyed(ent)
        return {'type': 'entity', 'entity': ent}
    ct = room.cells[r][c]
    if ct in (CellType.WALL, CellType.WATER, CellType.WOOD_WALL):
        room.cells[r][c] = CellType.FLOOR
        room.wood_damage.pop((r, c), None)
        return {'type': 'cell', 'cell_type': ct}
    return None


def _ed_snapshot(room, player) -> dict:
    return {
        'cells':       [row[:] for row in room.cells],
        'char_runs':       [CharRun(ru.row, ru.col, ru.symbols, ru.kind) for ru in room.char_runs],
        'entities':    [clone_entity(e) for e in room.entities],
        'exit_pos':    room.exit_pos,
        'spawn_pos':   room.spawn_pos,
        'wood_damage': dict(room.wood_damage),
        'mist_cells':  set(room.mist_cells),
        'fog_cells':   set(room.fog_cells),
        'pr':          player.row,
        'pc':          player.col,
    }


def _ed_restore(room, player, snap: dict) -> None:
    room.cells       = snap['cells']
    room.char_runs       = snap['char_runs']
    room.entities    = snap['entities']
    room.exit_pos    = snap['exit_pos']
    room.spawn_pos    = snap['spawn_pos']
    room.wood_damage = snap.get('wood_damage', {})
    # A painted mist is two facts about a cell; an undo that restored only the
    # grid would leave the haze hanging over dry floor.
    if 'mist_cells' in snap:
        room.mist_cells = set(snap['mist_cells'])
        room.fog_cells  = set(snap['fog_cells'])
    player.row       = snap['pr']
    player.col       = snap['pc']
    room.rebuild_indexes()


def _ed_paint(room, r, c, kind: str) -> bool:
    """Lay one cell down as `kind`. False if a fill owns the cell.

    Paint touches the CELL and nothing standing on it. The `s` cycle it replaced
    cut the character and the entity along with the terrain, which made the one
    thing the architecture asks for — a plaque set INTO a wall, where no `cc` can
    wipe it and no floor scan reads it — impossible to paint: the wall arrived
    and took the words with it. Removing things is what `x` and `d` are for.
    """
    if in_fill(room, r, c):
        return False                 # a fill owns this cell — see in_fill
    ct, misted, _ = PAINT_KINDS[kind]
    room.cells[r][c] = ct
    if misted:
        # Mist is a subset of the fog, always: the renderer reads the haze off
        # `fog_cells` first and only then asks whether it is the permanent kind.
        room.mist_cells.add((r, c))
        room.fog_cells.add((r, c))
    else:
        room.mist_cells.discard((r, c))
        room.fog_cells.discard((r, c))
    return True


def _ed_paste(room, r, start_c, items):
    c = start_c
    for item in items:
        if c < 0 or c >= room.cols:
            break
        if item['type'] == 'rune':
            ru = item['rune']
            w  = len(ru.symbols)
            if c + w <= room.cols:
                room.add_char_run(CharRun(row=r, col=c, symbols=ru.symbols, kind=ru.kind))
                c += w
        elif item['type'] == 'entity':
            ent   = item['entity']
            new_e = clone_entity(ent, fresh_uid=True, row=r, col=c)
            room.add_entity(new_e)
            if ent.kind == 'exit':
                room.exit_pos = (r, c)
            elif ent.kind == 'entry_marker':
                room.spawn_pos = (r, c)
            c += 1
        elif item['type'] == 'cell':
            room.cells[r][c] = item['cell_type']
            c += 1
    _merge_adjacent_char_runs(room, r)


def _ed_row_items(room, r):
    tagged = []
    for ru in room._char_runs_by_row.get(r, []):
        tagged.append((ru.col, {'type': 'rune', 'rune': ru}))
    for e in room.entities:
        if e.row == r and e.alive:
            tagged.append((e.col, {'type': 'entity', 'entity': e}))
    return [item for _, item in sorted(tagged)]


def _ed_clear_row(room, r):
    removed = [e for e in room.entities if e.row == r and e.alive]
    room.char_runs    = [ru for ru in room.char_runs
                         if ru.row != r or in_fill(room, ru.row, ru.col)]
    room.entities = [e  for e  in room.entities if not (e.row == r and e.alive)]
    room.rebuild_indexes()
    for e in removed:
        room._on_entity_destroyed(e)


def _ed_range_items(room, r1, c1, r2, c2):
    if r1 == r2:
        lo, hi = min(c1, c2), max(c1, c2)
        runes = [{'type': 'rune',   'rune': ru}
                 for ru in room._char_runs_by_row.get(r1, []) if lo <= ru.col <= hi]
        ents  = [{'type': 'entity', 'entity': e} for e in room.entities
                 if e.row == r1 and e.alive and lo <= e.col <= hi]
    else:
        rlo, rhi = min(r1, r2), max(r1, r2)
        runes = [{'type': 'rune',   'rune': ru}
                 for r in range(rlo, rhi + 1) for ru in room._char_runs_by_row.get(r, [])]
        ents  = [{'type': 'entity', 'entity': e} for e in room.entities
                 if e.alive and rlo <= e.row <= rhi]
    # A range that sweeps over a fill leaves the fill standing. Operators are
    # where this matters most — a `dG` down an authored level would otherwise
    # take the fills' words with it and then have them grow back on the next
    # build, which reads as the delete having silently failed.
    runes = [i for i in runes if not in_fill(room, i['rune'].row, i['rune'].col)]
    return runes + ents


def _ed_delete_range(room, r1, c1, r2, c2):
    items    = _ed_range_items(room, r1, c1, r2, c2)
    rune_ids = {id(i['rune'])   for i in items if i['type'] == 'rune'}
    ent_ids  = {id(i['entity']) for i in items if i['type'] == 'entity'}
    removed  = [e for e in room.entities if id(e) in ent_ids]
    room.char_runs    = [ru for ru in room.char_runs    if id(ru) not in rune_ids]
    room.entities = [e  for e  in room.entities if id(e)  not in ent_ids]
    room.rebuild_indexes()
    for e in removed:
        room._on_entity_destroyed(e)
    return items


def _clip_desc(item) -> str:
    if item['type'] == 'rune':
        ru = item['rune']
        if all(s == ' ' for s in ru.symbols):
            return 'space'
        return f"{ru.kind} rune"
    if item['type'] == 'entity':
        return item['entity'].kind
    ct = item.get('cell_type')
    if ct == CellType.WALL:      return 'wall'
    if ct == CellType.WOOD_WALL: return 'wood wall'
    if ct == CellType.WATER:     return 'water'
    return 'floor'


# Serialised cell encoding — single source of truth; the two directions are inverses.
_CELL_CODE = {CellType.WALL: 'W', CellType.FLOOR: 'F', CellType.CORRIDOR: 'C',
              CellType.WATER: 'A', CellType.WOOD_WALL: 'X'}
_CODE_CELL = {code: cell for cell, code in _CELL_CODE.items()}

#: Misted water, in a shared level file. Mist is a property OF a cell — it draws
#: as one, it is painted as one — so it rides the grid rather than a second list
#: of coordinates that could disagree with it. Not a CellType, and so not in
#: `_CELL_CODE`: only `sharing.format`'s row codec knows it, and only there does
#: it split back into WATER + a mist entry.
_MIST_CODE = 'M'
assert _MIST_CODE not in _CODE_CELL

# The Entity fields a save round-trips. `uid` is deliberately absent — it is
# per-run identity, minted fresh on load, exactly as a paste-back mints one.
_ENTITY_FIELDS = ('kind', 'row', 'col', 'hp', 'max_hp', 'ai', 'ai_speed',
                  'summon_timer', 'origin_row', 'move_dir', 'tag',
                  'scroll_id', 'swole', 'edit_immune', 'shade',
                  'drops', 'group')


def _deserialize_room(data: dict):
    """Reconstruct a Room from a dict produced by _serialize_room / save_layout."""
    rows  = data['rows']
    cols  = data['cols']
    cells = [[_CODE_CELL.get(c, CellType.FLOOR) for c in row] for row in data['cells']]
    room  = Room(room_type=RoomType.ENTRY, rows=rows, cols=cols)
    room.cells    = cells
    room.char_runs    = [CharRun(row=r['row'], col=r['col'],
                                 symbols=tuple(r['symbols']), kind=r['kind'])
                     for r in data.get('char_runs', [])]
    # `canonical_kind` on the way in: a layout saved before a kind was renamed
    # still names the old one, and a save file that stops loading is a level the
    # author simply loses.
    room.entities = [Entity(**{k: (canonical_kind(v) if k == 'kind' else v)
                               for k, v in e.items() if k in _ENTITY_FIELDS})
                     for e in data.get('entities', [])]
    ep = data.get('exit_pos')
    room.exit_pos = tuple(ep) if ep else None
    en = data.get('spawn_pos', [1, 1])
    room.spawn_pos = tuple(en)
    room.seed        = data.get('seed')
    room.answer      = data.get('answer', '')
    room.par         = data.get('par')
    room.budget      = data.get('budget', 0)
    room.no_horse    = bool(data.get('no_horse', False))
    room.fog_cells   = {tuple(p) for p in data.get('fog_cells', ())}
    room.mist_cells  = {tuple(p) for p in data.get('mist_cells', ())}
    room.sealed_cells = {tuple(p) for p in data.get('sealed_cells', ())}
    room.rebuild_indexes()
    return room


def _serialize_room(room) -> dict:
    """Serialise a Room to a JSON-safe dict for :save."""
    return {
        'rows':     room.rows,
        'cols':     room.cols,
        'cells':    [[_CELL_CODE.get(c, 'F') for c in row] for row in room.cells],
        'char_runs':    [{'row': ru.row, 'col': ru.col,
                      'symbols': list(ru.symbols), 'kind': ru.kind}
                     for ru in room.char_runs],
        # Every field that makes an entity what it IS. Listing only kind/row/col
        # used to bring a saved goblin back stationary at hp=1 with no AI, no
        # tag and no immunity — a different creature wearing the same letter.
        'entities': [{f: getattr(e, f) for f in _ENTITY_FIELDS}
                     for e in room.entities if e.alive],
        'spawn_pos': list(room.spawn_pos),
        'exit_pos': list(room.exit_pos) if room.exit_pos else None,
        'seed':     room.seed,
        'answer':   room.answer,
        'par':      room.par,
        'budget':   room.budget,
        'no_horse': bool(getattr(room, 'no_horse', False)),
        # Fog is not derivable from the grid — a level may lay it scripted — so
        # a layout that does not carry it comes back with the dark burned off.
        'fog_cells':    sorted(list(p) for p in room.fog_cells),
        'mist_cells':   sorted(list(p) for p in room.mist_cells),
        'sealed_cells': sorted(list(p) for p in room.sealed_cells),
    }
