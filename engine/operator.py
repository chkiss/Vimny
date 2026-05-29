"""Block B — operator application (d / y / c / > / <) over a TextObject.

The register clip preserves spacing: each captured rune records its column
*offset* from the span's left edge, so gaps between runes survive a paste.
This is how Vimny stays Vim-faithful — `yy` yanks the whole line including the
spaces between runes (bounded by stone walls), not just the rune clusters.
"""
from __future__ import annotations
from engine.world import CellType, RuneCluster, Entity
from engine.text_object import TextObjectType
from engine.editor import _merge_adjacent_runes

_PASTABLE = (CellType.FLOOR, CellType.CORRIDOR)


def line_extent(room, row: int):
    """(lo, hi) inclusive passable column extent of a row — the run between the
    stone walls — or None if the row has no passable cell."""
    lo = hi = None
    for c in range(room.cols):
        if room.is_passable(row, c):
            if lo is None:
                lo = c
            hi = c
    return (lo, hi) if lo is not None else None


def _capture_row(room, row: int, lo: int, hi: int) -> dict:
    """Capture runes overlapping [lo, hi] on `row`, split at the boundaries,
    each tagged with its column offset (dcol) from `lo`."""
    runes = []
    for ru in room._rune_by_row.get(row, []):
        rlo, rhi = ru.col, ru.col + len(ru.symbols) - 1
        if rhi < lo or rlo > hi:
            continue
        s, e = max(rlo, lo), min(rhi, hi)
        runes.append({'dcol': s - lo,
                      'symbols': tuple(ru.symbols[s - ru.col:e - ru.col + 1]),
                      'kind': ru.kind})
    runes.sort(key=lambda d: d['dcol'])
    return {'width': hi - lo + 1, 'runes': runes}


def _clip(text_obj) -> tuple:
    """Return (linewise, [(row, lo, hi), ...]) — the rows/cols a TextObject covers."""
    t = text_obj
    if t.type is TextObjectType.LINEWISE:
        return True, [(r, None, None) for r in range(t.start_row, t.end_row + 1)]
    hi = t.end_col if t.type is TextObjectType.INCLUSIVE else t.end_col - 1
    return False, [(t.start_row, t.start_col, hi)]


def capture(room, text_obj) -> dict:
    """Build a register clip from the span (no mutation)."""
    linewise, spans = _clip(text_obj)
    rows = []
    for row, lo, hi in spans:
        if linewise:
            ext = line_extent(room, row)
            if ext is None:
                rows.append({'width': 0, 'runes': []})
                continue
            lo, hi = ext
        if hi < lo:
            rows.append({'width': 0, 'runes': []})
        else:
            rows.append(_capture_row(room, row, lo, hi))
    return {'linewise': linewise, 'rows': rows}


def entity_clip(ent) -> dict:
    """A charwise clip holding a single cut creature, so `p` can place it back.

    Stores a template of the combat/identity fields; op_paste revives a fresh,
    live copy (full HP, new uid). Used when an enemy is killed — the slain
    creature lands in the unnamed register, exactly like cut text."""
    return {'linewise': False, 'rows': [{
        'width': 1,
        'runes': [],
        'entities': [{'dcol': 0, 'tmpl': {
            'kind': ent.kind, 'max_hp': ent.max_hp, 'hp': ent.hp,
            'ai': ent.ai, 'ai_speed': ent.ai_speed, 'tag': ent.tag,
            'summon_timer': ent.summon_timer,
        }}],
    }]}


def _revive_from_tmpl(t: dict, row: int, col: int) -> Entity:
    """Build a fresh, live Entity from a clip template: full HP, hostile, new
    identity (uid), independent of any summoner."""
    e = Entity(kind=t['kind'], row=row, col=col,
               max_hp=t.get('max_hp', 0), ai=t.get('ai', ''),
               ai_speed=t.get('ai_speed', 1), tag=t.get('tag', ''),
               summon_timer=t.get('summon_timer', 0))
    e.hp = e.max_hp if e.max_hp > 0 else t.get('hp', 1)
    e.origin_row = row
    return e


def _place_entities(room, row: int, start_col: int, rclip: dict) -> bool:
    """Revive and place a captured row's entities at start_col + dcol, skipping
    walls/occupied cells. Returns True if any entity was placed."""
    placed = False
    for ed in rclip.get('entities', ()):
        c = start_col + ed['dcol']
        if 0 <= c < room.cols and room.is_passable(row, c) and not room.entity_at(row, c):
            room.add_entity(_revive_from_tmpl(ed['tmpl'], row, c))
            placed = True
    return placed


_WALL_CELLS = (CellType.WALL, CellType.WATER, CellType.WOOD_WALL)


def _delete_cols(room, row: int, lo: int, hi: int) -> None:
    """Remove everything visible in [lo, hi] on `row`: runes, wall cells, and entities."""
    affected = [ru for ru in room._rune_by_row.get(row, [])
                if not (ru.col + len(ru.symbols) - 1 < lo or ru.col > hi)]
    for ru in affected:
        room.remove_rune(ru)
        if ru.col < lo:                                   # left remnant
            room.add_rune(RuneCluster(row, ru.col, tuple(ru.symbols[:lo - ru.col]), ru.kind))
        rhi = ru.col + len(ru.symbols) - 1
        if rhi > hi:                                      # right remnant
            room.add_rune(RuneCluster(row, hi + 1, tuple(ru.symbols[hi + 1 - ru.col:]), ru.kind))
    for c in range(lo, hi + 1):
        if room.cells[row][c] in _WALL_CELLS:
            room.cells[row][c] = CellType.FLOOR
            room.wood_damage.pop((row, c), None)
    for ent in [e for e in room.entities if e.row == row and lo <= e.col <= hi]:
        room.remove_entity(ent)
        if ent.kind == 'exit':
            room.exit_pos = None
        elif ent.kind == 'entry_marker':
            room.spawn_pos = (1, 1)


def op_yank(room, player, text_obj) -> dict:
    """Copy the span into a clip. Cursor unchanged."""
    return capture(room, text_obj)


def op_delete(room, player, text_obj) -> dict:
    """Capture the span, remove its runes, reposition the cursor; return the clip."""
    clip = capture(room, text_obj)
    linewise, spans = _clip(text_obj)
    _ext_cache: dict = {}
    for row, lo, hi in spans:
        if linewise:
            if row not in _ext_cache:
                _ext_cache[row] = line_extent(room, row)
            ext = _ext_cache[row]
            if ext is None:
                continue
            lo, hi = ext
        if hi >= lo:
            _delete_cols(room, row, lo, hi)
    # Cursor → start of the deleted region (vim-faithful).
    if linewise:
        player.row = min(text_obj.start_row, room.rows - 1)
        ext = line_extent(room, player.row)   # fresh call — cells may have changed
        player.col = ext[0] if ext else player.col
    else:
        player.col = text_obj.start_col
    return clip


def _place_row(room, row: int, start_col: int, rclip: dict) -> int:
    """Lay a captured row's runes onto `row` starting at start_col + dcol,
    clipping at walls/bounds. Returns the rightmost column written (or -1)."""
    last = -1
    for rd in rclip['runes']:
        base = start_col + rd['dcol']
        syms = []
        c = base
        for sym in rd['symbols']:
            if 0 <= c < room.cols and room.cells[row][c] in _PASTABLE:
                syms.append(sym)
                c += 1
            else:
                break                       # stop this cluster at a wall/edge
        if syms:
            room.add_rune(RuneCluster(row, base, tuple(syms), rd['kind']))
            last = base + len(syms) - 1
    return last


INDENT_WIDTH = 2                                # one shiftwidth, in columns


def apply_indent(room, row: int, amount: int) -> int:
    """Shift every rune cluster on `row` by `amount` columns (right > 0, left < 0),
    clamped within the row's passable extent (between the stone walls). Returns the
    net amount actually applied."""
    clusters = list(room._rune_by_row.get(row, []))
    ext = line_extent(room, row)
    if not clusters or ext is None:
        return 0
    lo, hi = ext
    leftmost = min(ru.col for ru in clusters)
    rightmost = max(ru.col + len(ru.symbols) - 1 for ru in clusters)
    if amount < 0:
        amount = max(amount, lo - leftmost)        # don't cross the left wall
    else:
        amount = min(amount, hi - rightmost)        # don't cross the right wall
    if amount == 0:
        return 0
    for ru in clusters:
        room.remove_rune(ru)
    for ru in clusters:
        room.add_rune(RuneCluster(row, ru.col + amount, ru.symbols, ru.kind))
    return amount


def _case_transform(op: str, sym: str) -> str:
    if op == 'gU':
        return sym.upper()
    if op == 'gu':
        return sym.lower()
    return sym.swapcase()                       # g~


def _case_cols(room, row: int, lo: int, hi: int, op: str) -> bool:
    """Transform the case of rune symbols in [lo, hi] on `row`. Returns changed."""
    changed = False
    for ru in room._rune_by_row.get(row, []):
        rlo, rhi = ru.col, ru.col + len(ru.symbols) - 1
        if rhi < lo or rlo > hi:
            continue
        new = list(ru.symbols)
        for k in range(len(ru.symbols)):
            if lo <= ru.col + k <= hi:
                t = _case_transform(op, ru.symbols[k])
                if t != new[k]:
                    new[k] = t
                    changed = True
        ru.symbols = tuple(new)
    return changed


def op_case(room, player, text_obj, op: str) -> bool:
    """Apply a case operator (gU/gu/g~) over the span; cursor → span start."""
    linewise, spans = _clip(text_obj)
    changed = False
    for row, lo, hi in spans:
        if linewise:
            ext = line_extent(room, row)
            if ext is None:
                continue
            lo, hi = ext
        if hi >= lo:
            changed |= _case_cols(room, row, lo, hi, op)
    if linewise:
        player.row = min(text_obj.start_row, room.rows - 1)
        ext = line_extent(room, player.row)
        player.col = ext[0] if ext else player.col
    else:
        player.col = text_obj.start_col
    return changed


def case_char(room, player, count: int = 1) -> bool:
    """`~`: toggle case of `count` symbols from the cursor, advancing each time."""
    changed = False
    for _ in range(count):
        r, c = player.row, player.col
        ru = room.rune_at(r, c)
        if ru is not None:
            k = c - ru.col
            new = list(ru.symbols)
            new[k] = new[k].swapcase()
            ru.symbols = tuple(new)
            changed = True
        if c + 1 < room.cols and room.is_passable(r, c + 1):
            player.col += 1
        else:
            break
    return changed


def op_paste(room, player, clip: dict, before: bool) -> bool:
    """Place a clip into the room. Charwise: at cursor (P) / cursor+1 (p).
    Linewise: overlay onto the cursor row (P) / row below (p), preserving the
    runes' relative columns. Returns True if anything was placed."""
    if not clip or not clip.get('rows'):
        return False
    placed_any = False
    if clip['linewise']:
        base_row = player.row if before else player.row + 1
        first_row = None
        for i, rclip in enumerate(clip['rows']):
            row = base_row + i
            if row < 0 or row >= room.rows:
                break
            ext = line_extent(room, row)
            if ext is None:
                continue
            rune_last = _place_row(room, row, ext[0], rclip)
            ent_placed = _place_entities(room, row, ext[0], rclip)
            if rune_last >= 0 or ent_placed:
                placed_any = True
                if first_row is None:
                    first_row = row
            _merge_adjacent_runes(room, row)
        if first_row is not None:
            player.row = first_row
            ext = line_extent(room, first_row)
            player.col = ext[0] if ext else player.col
    else:
        rclip = clip['rows'][0]
        start = player.col if before else player.col + 1
        last = _place_row(room, player.row, start, rclip)
        _merge_adjacent_runes(room, player.row)
        if last >= 0:
            placed_any = True
            player.col = last            # vim leaves cursor on last pasted cell
        # Creatures respawn live & hostile; the cursor stays put — never landing
        # the player on top of a pasted enemy.
        if _place_entities(room, player.row, start, rclip):
            placed_any = True
    return placed_any
