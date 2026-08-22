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

"""Block B — operator application (d / y / c / > / <) over a TextObject.

The register clip preserves spacing: each captured character records its column
*offset* from the span's left edge, so gaps between characters survive a paste.
This is how Vimny stays Vim-faithful — `yy` yanks the whole line including the
spaces between characters (bounded by stone walls), not just the character runs.
"""
from __future__ import annotations
from vimny.engine.world import (CellType, CharRun, Entity, strike_disguise,
                          blocked_by_entity)
from vimny.engine.text_object import TextObjectType
from vimny.engine.editor import _merge_adjacent_char_runs
from vimny.engine.reflow import (
    is_ledge, close_gap, open_gap, remove_row, _insert_blank_row, carve_floor, _row_glyphs, _MAX_COLS,
)

_PASTABLE = (CellType.FLOOR, CellType.CORRIDOR)


INDENT_WIDTH = 2   # columns one >>/<< shift adds or removes


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


def _cursor_to_line_start(room, player, row: int) -> None:
    """Park the cursor on the FIRST NON-BLANK of `row` (Vim's linewise landing
    spot — dd/>>/V-ops land on the first character, not the first column),
    falling back to the first passable column on a bare row; keeps the current
    column when the row has no passable cell."""
    from vimny.engine.motion import _first_non_blank_col, _caret_stop
    player.row = min(row, room.rows - 1)
    fnb = _first_non_blank_col(room, player.row)
    if fnb is None:
        # A collapse may drop the cursor onto a row the fog still hides
        # (the Operator's Vault ledge): the fall is physical, so park by
        # the SAME first-non-blank rule IGNORING fog — first character,
        # else first floor cell — and let the level's reveal tick light
        # the room from where the player lands.
        left = None
        for c in range(room.cols):
            if room.cells[player.row][c] in (CellType.FLOOR, CellType.CORRIDOR):
                if left is None:
                    left = c
                if _caret_stop(room, player.row, c):
                    left = c
                    break
        fnb = left
    player.col = fnb if fnb is not None else player.col


def _capture_row(room, row: int, lo: int, hi: int) -> dict:
    """Capture characters overlapping [lo, hi] on `row`, split at the boundaries,
    each tagged with its column offset (dcol) from `lo`."""
    char_runs = []
    for ru in room._char_runs_by_row.get(row, []):
        rlo, rhi = ru.col, ru.col + len(ru.symbols) - 1
        if rhi < lo or rlo > hi:
            continue
        s, e = max(rlo, lo), min(rhi, hi)
        char_runs.append({'dcol': s - lo,
                          'symbols': tuple(ru.symbols[s - ru.col:e - ru.col + 1]),
                          'kind': ru.kind})
    char_runs.sort(key=lambda d: d['dcol'])
    return {'width': hi - lo + 1, 'char_runs': char_runs}


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
                rows.append({'width': 0, 'char_runs': []})
                continue
            lo, hi = ext
        if hi < lo:
            rows.append({'width': 0, 'char_runs': []})
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
        'char_runs': [],
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
    walls/occupied cells and never reaching past a shut door. Returns True if
    any entity was placed.

    `is_passable` already refuses the door's OWN cell; the extra bound is that
    nothing lands BEYOND it either, or a pasted creature would stand on the far
    side of a lock and take the cursor with it (op_paste lands on the last
    pasted cell, character or creature alike)."""
    placed = False
    stop = next((c for c in range(start_col, room.cols)
                 if blocked_by_entity(room, row, c)), room.cols)
    for ed in rclip.get('entities', ()):
        c = start_col + ed['dcol']
        if c < stop and room.is_passable(row, c) and not room.entity_at(row, c):
            room.add_entity(_revive_from_tmpl(ed['tmpl'], row, c))
            placed = True
    return placed


_WALL_CELLS = (CellType.WALL, CellType.WATER, CellType.WOOD_WALL)


def _delete_cols(room, row: int, lo: int, hi: int) -> None:
    """Remove everything visible in [lo, hi] on `row`: characters, wall cells, and entities."""
    affected = [ru for ru in room._char_runs_by_row.get(row, [])
                if not (ru.col + len(ru.symbols) - 1 < lo or ru.col > hi)]
    for ru in affected:
        room.remove_char_run(ru)
        if ru.col < lo:                                   # left remnant
            room.add_char_run(CharRun(row, ru.col, tuple(ru.symbols[:lo - ru.col]), ru.kind))
        rhi = ru.col + len(ru.symbols) - 1
        if rhi > hi:                                      # right remnant
            room.add_char_run(CharRun(row, hi + 1, tuple(ru.symbols[hi + 1 - ru.col:]), ru.kind))
    for c in range(lo, hi + 1):
        if room.cells[row][c] in _WALL_CELLS:
            room.cells[row][c] = CellType.FLOOR
            room.wood_damage.pop((row, c), None)
    for ent in [e for e in room.entities if e.row == row and lo <= e.col <= hi
                and not e.edit_immune]:                    # a boss parries editing-delete
        if not strike_disguise(ent):                       # impostor W unmasks to 'g', survives
            continue
        room.remove_entity(ent)
        room._on_entity_destroyed(ent)


def _span_has_lit_brazier(room, text_obj) -> bool:
    """True if the yanked span covers a LIT brazier — a lit brazier is fire, and
    yanking one (by any motion/count) takes a light off it."""
    linewise, spans = _clip(text_obj)
    for row, lo, hi in spans:
        for e in room.entities:
            if not (e.alive and e.kind == 'brazier' and e.lit and e.row == row):
                continue
            if linewise or lo is None or (lo <= e.col <= hi):
                return True
    return False


def op_yank(room, player, text_obj) -> dict:
    """Copy the span into a clip. Cursor unchanged. A span that covers a lit
    brazier carries FIRE (the clip is flagged), which p/P uses to light a cold
    brazier — the brazier itself never enters the clip and is never moved."""
    clip = capture(room, text_obj)
    if _span_has_lit_brazier(room, text_obj):
        clip['fire'] = True
    return clip


def op_delete(room, player, text_obj, collapse: bool = False) -> dict:
    """Capture the span, remove it, reposition the cursor; return the clip.

    Charwise: characters are deleted and the tail pulled left (``close_gap``).
    Linewise with ``collapse=True`` (``dd`` / visual-line ``d``) structurally
    removes the row(s) — the vertical inverse of ``o`` (rows below shift up);
    ``collapse=False`` (``cc`` / ``S``) clears the line content in place and
    keeps the row."""
    clip = capture(room, text_obj)
    linewise, spans = _clip(text_obj)
    if linewise and collapse:
        start = min(r for r, _, _ in spans)
        for _ in range(len(spans)):
            if not remove_row(room, start, player):
                break                                  # hit a border guard — stop collapsing
        _cursor_to_line_start(room, player, start)
        return clip
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
            if not linewise and is_ledge(room, row):
                close_gap(room, row, lo, hi - lo + 1)   # ledge: pull the tail left
    # Cursor → start of the deleted region (vim-faithful).
    if linewise:
        _cursor_to_line_start(room, player, text_obj.start_row)   # fresh call — cells may have changed
    else:
        player.col = text_obj.start_col
    return clip


def _place_row(room, row: int, start_col: int, rclip: dict) -> int:
    """Lay a captured row's characters onto `row` starting at start_col + dcol,
    clipping at walls/bounds AND at shut doors. Returns the rightmost column
    written (or -1).

    A SHUT DOOR IS A WALL THAT OPENS. It stands on ordinary floor, so a paste
    that only asked the CELL laid its text straight across one — and since the
    cursor lands on the last pasted cell, the player rode the text through a
    lock they never opened (`5p` beside a gate walked them into the corridor
    beyond it). The push has always dropped a glyph shoved onto an entity into
    the void; this is the same law read from the other side."""
    last = -1
    # The bound is on the WHOLE placement, not per cluster: a clip cut from a
    # row with gaps holds one run per cluster, and stopping each run at the door
    # would still let the run that BEGINS past it land on the far side.
    stop = next((c for c in range(start_col, room.cols)
                 if blocked_by_entity(room, row, c)), room.cols)
    for rd in rclip['char_runs']:
        base = start_col + rd['dcol']
        syms = []
        c = base
        for sym in rd['symbols']:
            if (0 <= c < stop and room.cells[row][c] in _PASTABLE):
                syms.append(sym)
                c += 1
            else:
                break                       # stop this cluster at a wall/door/edge
        if syms:
            room.add_char_run(CharRun(row, base, tuple(syms), rd['kind']))
            last = base + len(syms) - 1
    return last


def apply_indent(room, row: int, amount: int) -> int:
    """Shift the row's content by `amount` columns. A RIGHT indent (`>`, amount>0)
    REFLOWS: content slides right and whatever crosses the right brink falls into
    the void (`open_gap`, recorded in room._last_void_falls). A LEFT dedent (`<`,
    amount<0) pulls content toward the left wall, clamped there (nothing falls —
    you cannot dedent past the wall). Returns the amount applied."""
    ext = line_extent(room, row)
    if ext is None:
        return 0
    lo, hi = ext
    # The LINE is the passable extent — glyphs embedded in walls (a west-wall
    # plaque on the same row) are not part of any line and must neither move
    # nor anchor the shift (a plaque at col 1 made `leftmost` land inside the
    # wall: >> opened its gap in the wall segment — a no-op — and <<'s clamp
    # math inverted). Column overlap alone is NOT enough: a wall-embedded
    # glyph WITHIN the extent's column range (an alcove marker mid-row) must
    # stay in its stone too — cell-type checked, like _floor_tokens (a `=`
    # dedent once dragged the Scrivener's ☿ marker out of its wall onto the
    # floor).
    clusters = [ru for ru in room._char_runs_by_row.get(row, [])
                if ru.col + len(ru.symbols) - 1 >= lo and ru.col <= hi
                and any(room.cells[row][ru.col + k] in _LAW_FLOORS
                        for k in range(len(ru.symbols))
                        if lo <= ru.col + k <= hi)]
    if not clusters:
        return 0
    leftmost = min(ru.col for ru in clusters)
    if amount > 0:
        open_gap(room, row, leftmost, amount)       # reflow: overflow tumbles off the brink
        return amount
    amount = max(amount, lo - leftmost)             # don't cross the left wall
    if amount == 0:
        return 0
    for ru in clusters:
        room.remove_char_run(ru)
    for ru in clusters:
        room.add_char_run(CharRun(row, ru.col + amount, ru.symbols, ru.kind))
    return amount


_LAW_FLOORS = (CellType.FLOOR, CellType.CORRIDOR)


def _floor_tokens(room, row: int):
    """The row's LINE as text: glyphs on FLOOR cells within the passable extent
    (gaps as spaces), returned as (start_col, stripped_text). (None, '') for a
    wall row or a bare-floor row. A glyph in stone is not part of any line —
    wall-embedded carvings (plaques, alcove markers) inside the extent's
    column range must neither feed the law nor anchor it; the check reads the
    CELL TYPE, not is_passable, because fog makes floor impassable (the
    Manifold lesson)."""
    ext = line_extent(room, row)
    if ext is None:
        return None, ''
    lo, hi = ext
    cells = {}
    for ru in room._char_runs_by_row.get(row, []):
        for k, sym in enumerate(ru.symbols):
            c = ru.col + k
            if lo <= c <= hi and room.cells[row][c] in _LAW_FLOORS:
                cells[c] = sym
    if not cells:
        return None, ''
    start = min(cells)
    text = ''.join(cells.get(c, ' ') for c in range(start, max(cells) + 1))
    return start, text


def law_column(room, row: int):
    """Vimny's `=` — the indentexpr socket. A room may post its own law as
    `room._indent_law(room, row) -> col|None`; with none posted, the BLOCK LAW
    governs (the dungeon's one built-in policy, the analogue of Vim's C
    fallback — bare `=` is never policy-free):

      a verse under a line ending in ':' stands one step (INDENT_WIDTH) deeper;
      a verse whose first word is 'end' returns to its opener's station;
      any other verse keeps its neighbor's station;
      UNGOVERNED verse (a block with no ':' / 'end' structure) stands at the
      wall — which is exactly how `=` mauls plain prose (the gg=G-in-markdown
      disaster, kept faithfully).

    The block is the maximal run of contiguous rows carrying text; the station
    base is the row's segment start. Returns the lawful start column for `row`,
    or None when the row has no line / no text (nothing to govern)."""
    law = getattr(room, '_indent_law', None)
    if law is not None:
        return law(room, row)
    ext = line_extent(room, row)
    if ext is None or _floor_tokens(room, row)[0] is None:
        return None
    top = row
    while top - 1 >= 0 and _floor_tokens(room, top - 1)[0] is not None:
        top -= 1
    base = ext[0]
    depth = 0
    for r in range(top, row + 1):
        _, text = _floor_tokens(room, r)
        stripped = text.strip()
        words = stripped.split()
        if words and words[0] == 'end':               # space-only text has floor tokens but no words
            depth = max(depth - 1, 0)
        if r == row:
            return base + INDENT_WIDTH * depth
        if stripped.endswith(':'):
            depth += 1
    return base


def apply_equalize(room, row: int) -> bool:
    """`=` on one row: shift the line to the column the law assigns it.
    Returns True if the row moved."""
    target = law_column(room, row)
    if target is None:
        return False
    start, _ = _floor_tokens(room, row)
    if start is None or start == target:
        return False
    return apply_indent(room, row, target - start) != 0


def _case_transform(op: str, sym: str) -> str:
    if op == 'gU':
        return sym.upper()
    if op == 'gu':
        return sym.lower()
    return sym.swapcase()                       # g~


def _case_cols(room, row: int, lo: int, hi: int, op: str) -> bool:
    """Transform the case of characters in [lo, hi] on `row`. Returns changed."""
    changed = False
    for ru in room._char_runs_by_row.get(row, []):
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


_SWELLABLE = ('goblin', 'ally', 'critter')


def case_entities(room, cells, op: str) -> int:
    """Case ops act on CREATURES too, from whatever command: uppercasing a
    goblin's `g` into a `G` swells it (bigger, sharper-eyed); lowercasing shrinks
    it back; `~`/`g~` toggles. Applies to any swellable creature (goblin/ally/
    critter, but not the impostor echo Ws) whose cell is in `cells`. Returns the
    number of creatures changed. This is the SINGLE home of the g<->G rule, so
    ~, gU, gUU, gu, visual U/u/~ and :s all produce the same entity."""
    seen, n = set(), 0
    upper = True if op in ('gU', 'U') else False if op in ('gu', 'u') else None
    for (r, c) in cells:
        e = room.entity_at(r, c)
        if e is None or id(e) in seen or e.kind not in _SWELLABLE or e.tag == 'echo':
            continue
        seen.add(id(e))
        want = (not e.swole) if upper is None else upper
        if want == e.swole:
            continue
        e.swole = want
        if want:
            e.max_hp += 2; e.hp += 2
        else:
            e.max_hp = max(1, e.max_hp - 2); e.hp = max(1, e.hp - 2)
        n += 1
    return n


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
            changed |= case_entities(room, [(row, c) for c in range(lo, hi + 1)], op) > 0
    if linewise:
        _cursor_to_line_start(room, player, text_obj.start_row)
    else:
        player.col = text_obj.start_col
    return changed


def case_char(room, player, count: int = 1) -> bool:
    """`~`: toggle case of `count` symbols from the cursor, advancing each time.
    Toggles a creature under the cursor too (g<->G, d<->D, c<->C) via the shared
    case_entities rule."""
    changed = False
    for _ in range(count):
        r, c = player.row, player.col
        ru = room.char_run_at(r, c)
        if ru is not None:
            k = c - ru.col
            new = list(ru.symbols)
            new[k] = new[k].swapcase()
            ru.symbols = tuple(new)
            changed = True
        if case_entities(room, [(r, c)], 'g~'):
            changed = True
        if c + 1 < room.cols and room.is_passable(r, c + 1):
            player.col += 1
        else:
            break
    return changed


def op_paste(room, player, clip: dict, before: bool, count: int = 1) -> bool:
    """Paste a clip `count` times (3p → 3 copies; x on g + 3p → ggg).

    Charwise paste reflows like real Vim: `p` inserts AFTER the cursor (col+1),
    `P` BEFORE it (col); existing content slides right to make room (overflow
    falls off the brink) and the cursor lands on the LAST pasted cell. A cut
    creature respawns live; a cut letter lays back down — both shift the line.
    Linewise paste inserts REAL new rows (Vim-faithful): `p` opens line(s) below,
    `P` at the cursor row (the map below shifts down); the cursor lands on the
    first non-blank of the first pasted line. Returns True if anything was
    placed."""
    if not clip or not clip.get('rows'):
        return False
    placed_any = False
    if clip['linewise']:
        nrows    = len(clip['rows'])
        total    = nrows * count
        base_row = player.row if before else player.row + 1
        tmpl     = player.row
        for k in range(total):
            # A pasted line is TEXT, not a terrain photocopy: the new row is a
            # Vim BLANK line across the cursor's segment (the o/O shape), and
            # the yanked glyphs are laid onto it. A full-cell clone leaks
            # far-side structure through walls (P parks on the pasted row's
            # first standable, which could be a cloned pocket behind a seal).
            _insert_blank_row(room, base_row + k, tmpl, player, blank=True)
        for copy in range(count):
            for i, rclip in enumerate(clip['rows']):
                row = base_row + copy * nrows + i
                ext = line_extent(room, row)
                if ext is None:
                    continue
                _place_row(room, row, ext[0], rclip)
                _place_entities(room, row, ext[0], rclip)
                _merge_adjacent_char_runs(room, row)
        if total > 0:
            placed_any = True                                 # inserting rows is itself a change
            player.row = min(base_row, room.rows - 1)          # cursor → first pasted line (Vim)
            ext   = line_extent(room, player.row)
            char_runs = room._char_runs_by_row.get(player.row, [])
            player.col = min((ru.col for ru in char_runs), default=(ext[0] if ext else player.col))
    else:
        rclip = clip['rows'][0]
        width = max(rclip.get('width', 0), 1)               # ≥1 cell per copy
        base  = player.col if before else player.col + 1
        total = width * count
        open_gap(room, player.row, base, total)             # reflow: slide existing content right
        for copy in range(count):
            col_k = base + copy * width
            if _place_row(room, player.row, col_k, rclip) >= 0:
                placed_any = True
            if _place_entities(room, player.row, col_k, rclip):
                placed_any = True
        _merge_adjacent_char_runs(room, player.row)
        if placed_any:                                      # cursor on the last pasted cell (Vim)
            last = base + total - 1
            while last >= base and (blocked_by_entity(room, player.row, last)
                                    or not (room.char_run_at(player.row, last)
                                            or room.entity_at(player.row, last))):
                last -= 1       # skip cells that got nothing (fell off the brink)
                                # — and the shut door itself, which is an entity
                                # the walk-back would otherwise read as "pasted"
                                # and park the cursor inside the lock
            if last >= base:
                player.col = last                           # land on the last pasted cell — character OR creature
    return placed_any


def op_join(room, player, gap: bool = True, count: int = 1) -> bool:
    """`J` / `gJ` — join the next line(s) onto the cursor line. Each next line is
    cut (``remove_row`` — the dd half) and its glyphs appended to this line from
    just past its rightmost content, building floor into the void (``carve_floor``
    — the A half) while preserving the joined line's internal spacing (leading
    blanks dropped). `J` leaves one space at the seam and lands the cursor there;
    `gJ` leaves none. `nJ` joins n lines. Returns True if any join happened."""
    joins  = max(1, count - 1)
    seam   = None
    joined = False
    room._last_build_blocked = None
    for _ in range(joins):
        src = player.row + 1
        if src >= room.rows or line_extent(room, src) is None:
            break                                           # no next line (bottom wall / edge)
        # GLYPHS IN STONE ARE NEVER TEXT (fifth enforcement site): a join
        # pulls only FLOOR glyphs up — wall-carved plaques stay in the wall,
        # and they don't count as the target row's content end either.
        glyphs = sorted((g for g in _row_glyphs(room, src)
                         if room.is_passable(src, g[0])), key=lambda g: g[0])
        ends = [c for (c, _s, _k) in _row_glyphs(room, player.row)
                if room.is_passable(player.row, c)]
        ext      = line_extent(room, player.row)
        seam_col = (max(ends) + 1) if ends else (ext[0] if ext else 0)
        base     = seam_col + (1 if gap else 0)             # where the joined glyphs begin
        span     = (glyphs[-1][0] - glyphs[0][0]) if glyphs else 0
        needed_end = (base + span) if glyphs else seam_col
        if needed_end > _MAX_COLS - 2:                      # would build past the edge of the world
            room._last_build_blocked = 'edge'
            break
        if gap and not carve_floor(room, player.row, seam_col):
            break                                           # seam space blocked (void / edge)
        if glyphs:
            first = glyphs[0][0]
            stop  = base + span
            for col in range(base, base + span + 1):        # carve the run so inter-word gaps are real floor
                if not carve_floor(room, player.row, col):
                    stop = col - 1
                    break
            for (c, s, k) in glyphs:
                dest = base + (c - first)
                if dest <= stop:
                    room.add_char_run(CharRun(player.row, dest, (s,), k))
            _merge_adjacent_char_runs(room, player.row)
        remove_row(room, src, player)
        if seam is None:
            seam = seam_col
        joined = True
    if joined and seam is not None:
        player.col = min(seam, room.cols - 1)
    return joined
