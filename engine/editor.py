"""Admin editor helpers: snapshot/restore, cut/paste, range operations."""
from __future__ import annotations
from engine.world import CellType, CharRun, Entity

_SUBST_CYCLE = {
    CellType.FLOOR:     CellType.WALL,
    CellType.WALL:      CellType.WOOD_WALL,
    CellType.WOOD_WALL: CellType.WATER,
    CellType.WATER:     CellType.FLOOR,
    CellType.CORRIDOR:  CellType.WALL,
}


def _merge_adjacent_char_runs(room, r: int) -> None:
    """Merge adjacent same-kind CharRuns on row r into single clusters."""
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
    room.char_runs = [ru for ru in room.char_runs if ru.row != r] + merged
    room.rebuild_indexes()


def _ed_cut(room, r, c):
    """Remove the character/entity/wall at (r, c); return a clip item or None.

    For character runs: extracts only the single symbol at column c, leaving
    any remaining symbols as split remnants.
    """
    ru = room.char_run_at(r, c)
    if ru:
        idx = c - ru.col
        room.remove_char_run(ru)
        if idx > 0:
            room.add_char_run(CharRun(row=r, col=ru.col,
                                      symbols=tuple(ru.symbols[:idx]), kind=ru.kind))
        if idx + 1 < len(ru.symbols):
            room.add_char_run(CharRun(row=r, col=c + 1,
                                      symbols=tuple(ru.symbols[idx + 1:]), kind=ru.kind))
        return {'type': 'rune',
                'rune': CharRun(row=r, col=c,
                                    symbols=(ru.symbols[idx],), kind=ru.kind)}
    ent = room.entity_at(r, c)
    if ent:
        room.remove_entity(ent)
        if ent.kind == 'exit':
            room.exit_pos = None
        elif ent.kind == 'entry_marker':
            room.spawn_pos = (1, 1)
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
        'entities':    [Entity(kind=e.kind, row=e.row, col=e.col, hp=e.hp, alive=e.alive)
                        for e in room.entities],
        'exit_pos':    room.exit_pos,
        'spawn_pos':   room.spawn_pos,
        'wood_damage': dict(room.wood_damage),
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
    player.row       = snap['pr']
    player.col       = snap['pc']
    room.rebuild_indexes()


def _ed_subst(room, r, c):
    """Cycle cell type FLOOR→WALL→WATER→FLOOR; also cut any character/entity."""
    items = []
    if room.char_run_at(r, c) or room.entity_at(r, c):
        item = _ed_cut(room, r, c)
        if item:
            items.append(item)
    ct = room.cells[r][c]
    room.cells[r][c] = _SUBST_CYCLE.get(ct, CellType.WALL)
    items.append({'type': 'cell', 'cell_type': ct})
    return items


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
            new_e = Entity(kind=ent.kind, row=r, col=c, hp=ent.hp)
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
    room.char_runs    = [ru for ru in room.char_runs    if ru.row != r]
    room.entities = [e  for e  in room.entities if not (e.row == r and e.alive)]
    room.rebuild_indexes()
    for e in removed:
        if e.kind == 'exit':
            room.exit_pos = None
        elif e.kind == 'entry_marker':
            room.spawn_pos = (1, 1)


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
        if e.kind == 'exit':
            room.exit_pos = None
        elif e.kind == 'entry_marker':
            room.spawn_pos = (1, 1)
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


def _deserialize_room(data: dict):
    """Reconstruct a Room from a dict produced by _serialize_room / save_layout."""
    from engine.world import Room, RoomType, CellType, CharRun, Entity
    cell_map = {'W': CellType.WALL, 'F': CellType.FLOOR, 'C': CellType.CORRIDOR,
                'A': CellType.WATER, 'X': CellType.WOOD_WALL}
    rows  = data['rows']
    cols  = data['cols']
    cells = [[cell_map.get(c, CellType.FLOOR) for c in row] for row in data['cells']]
    room  = Room(room_type=RoomType.ENTRY, rows=rows, cols=cols)
    room.cells    = cells
    room.char_runs    = [CharRun(row=r['row'], col=r['col'],
                                 symbols=tuple(r['symbols']), kind=r['kind'])
                     for r in data.get('char_runs', [])]
    room.entities = [Entity(kind=e['kind'], row=e['row'], col=e['col'])
                     for e in data.get('entities', [])]
    ep = data.get('exit_pos')
    room.exit_pos = tuple(ep) if ep else None
    en = data.get('spawn_pos', [1, 1])
    room.spawn_pos = tuple(en)
    room.rebuild_indexes()
    return room


def _serialize_room(room) -> dict:
    """Serialise a Room to a JSON-safe dict for :save."""
    cell_map = {CellType.WALL: 'W', CellType.FLOOR: 'F', CellType.CORRIDOR: 'C',
                CellType.WATER: 'A', CellType.WOOD_WALL: 'X'}
    return {
        'rows':     room.rows,
        'cols':     room.cols,
        'cells':    [[cell_map.get(c, 'F') for c in row] for row in room.cells],
        'char_runs':    [{'row': ru.row, 'col': ru.col,
                      'symbols': list(ru.symbols), 'kind': ru.kind}
                     for ru in room.char_runs],
        'entities': [{'kind': e.kind, 'row': e.row, 'col': e.col}
                     for e in room.entities if e.alive],
        'spawn_pos': list(room.spawn_pos),
        'exit_pos': list(room.exit_pos) if room.exit_pos else None,
    }
