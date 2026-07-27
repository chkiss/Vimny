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

"""Motion execution: apply_motion, move_player, and related helpers."""
from __future__ import annotations
from collections import deque
from engine.player import Player
from engine.modes import Mode
from engine.world import CellType, entity_letter, CARET_TRANSPARENT


def _apply_esc(player: Player) -> None:
    player.mode = Mode.NORMAL


def move_player(player, dr, dc, room):
    nr, nc = player.row + dr, player.col + dc
    if not room.is_passable(nr, nc):
        return False
    player.row, player.col = nr, nc
    return True


_FOG_BLOCK_KINDS = ('door', 'locked_door', 'seal_door', 'boss_seal')
_FOGGABLE_CELLS  = (CellType.FLOOR, CellType.CORRIDOR, CellType.WATER)


def _flood_reachable(room, start_r: int, start_c: int) -> set:
    """BFS flood of fog-visible cells (FLOOR/CORRIDOR/WATER) from a start cell.
    A closed door entity blocks the spread — its own cell is reached (visible)
    but the flood does not expand through it. Returns the reachable (r, c) set."""
    reachable = {(start_r, start_c)}
    q = deque([(start_r, start_c)])
    while q:
        r, c = q.popleft()
        ent = room.entity_at(r, c)
        if ent and ent.kind in _FOG_BLOCK_KINDS:
            continue
        for dr, dc in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            nr, nc = r + dr, c + dc
            if (nr, nc) in reachable:
                continue
            if not (0 <= nr < room.rows and 0 <= nc < room.cols
                    and room.cells[nr][nc] in _FOGGABLE_CELLS):
                continue
            if (nr, nc) in room.mist_cells:
                continue      # MIST: permanent haze is never reached NOR
                              # revealed — light stops at it, so a misted
                              # channel can't ladder a fog flood (nor a
                              # reveal) past a gate. Ordinary fogged water
                              # (a pool inside a to-be-revealed region)
                              # still conducts and clears normally.
            reachable.add((nr, nc))
            q.append((nr, nc))
    return reachable


def _fog_unreachable(room, start_r: int, start_c: int) -> None:
    """Initialise room.fog_cells: all floor/corridor/water cells not visible
    from start (visibility blocked at closed doors; see _flood_reachable)."""
    foggable = {(r, c) for r in range(room.rows) for c in range(room.cols)
                if room.cells[r][c] in _FOGGABLE_CELLS}
    room.fog_cells = foggable - _flood_reachable(room, start_r, start_c)


def _vision_flood(room, start_r: int, start_c: int) -> set:
    """BFS flood of STONE-bounded sight from a cell: spreads through every
    floor/corridor/water cell and straight past entities (a door is a grille
    you can see through — unlike _flood_reachable's door-blocked spread).
    Only wall cells stop the eye — every other cell type (a brazier
    pedestal, a lava rune floor) is transparent even if not foggable. This
    is the fog LAW's visibility model: what stone hides, fog hides; what a
    door or water merely bars, you see."""
    stone = (CellType.WALL, CellType.WOOD_WALL)
    seen = {(start_r, start_c)}
    q = deque([(start_r, start_c)])
    while q:
        r, c = q.popleft()
        for dr, dc in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            nr, nc = r + dr, c + dc
            if (nr, nc) in seen:
                continue
            if (0 <= nr < room.rows and 0 <= nc < room.cols
                    and room.cells[nr][nc] not in stone):
                seen.add((nr, nc))
                q.append((nr, nc))
    return seen


def stone_law(room) -> set:
    """Every foggable cell the eye cannot reach from spawn — the fog FLOOR.

    Derived from the geometry, never stored, so it cannot drift away from the
    walls the way a hand-kept fog set does.
    """
    if not room.spawn_pos:
        return set()
    foggable = {(r, c) for r in range(room.rows) for c in range(room.cols)
                if room.cells[r][c] in _FOGGABLE_CELLS}
    return foggable - _vision_flood(room, *room.spawn_pos)


def apply_stone_fog(room) -> None:
    """Initialise fog by the stone law, and mark the room `auto_fog` so the
    main loop re-reveals as walls open (a sealed pocket unfogs the moment its
    door becomes floor and sight crosses).
    Rooms with SCRIPTED fog (Manifold, Scrivener) must NOT use this: the
    auto-reveal would instantly clear their re-laid fog."""
    room.fog_cells |= stone_law(room)
    room.auto_fog = True


def enforce_fog_law(room) -> None:
    """Hold every room to the stone law — what the eye cannot reach from spawn
    is fogged — without disturbing anything a builder laid on top.

    The law was opt-in until now: each builder called `apply_stone_fog` for
    itself, and a room that never called it, or that grew a sealed pocket after
    it did, showed the player straight through the stone. That is a drift bug,
    not a style, and the evidence is unanimous — of the game's 62 rooms, every
    single one fogs at least the law's cells except two that simply never
    asked. So the law stops being something a builder remembers and becomes
    something the world is held to.

    Scripted fog is a SUPERSET, never a replacement, so this only ever adds —
    and it leaves `auto_fog` alone, because whether a room re-reveals is a
    design decision (the Manifold and the Scrivener re-lay their fog every turn
    and must not have it lifted). A room that had no fog at all is opted into
    auto-reveal, which is what every hand-written call to `apply_stone_fog`
    already chose.

    A WRAP BUFFER is exempt, and by what it IS rather than by name: one row of
    text, where sight stops at the first segment wall and the law would fog
    almost the whole line. A buffer is something you read, not a space you
    explore, and the eye does not walk it.
    """
    if getattr(room, 'wrap_buffer', False):
        return
    if room.fog_cells:
        room.fog_cells |= stone_law(room)      # scripted: keep its reveal rule
    else:
        apply_stone_fog(room)


def auto_fog_tick(room, player_r: int, player_c: int) -> None:
    """Re-reveal for auto_fog rooms: lift fog from every cell now visible
    from the player (walls-only sight). Called each tick by the main loop.

    MIST is never lifted. The two fogs are different things wearing one field:
    stone fog is ignorance, and looking cures it; mist is weather, and standing
    next to it does not. Without this a misted level that also auto-reveals
    would clear its own haze on turn one.
    """
    if getattr(room, 'auto_fog', False) and room.fog_cells:
        room.fog_cells -= (_vision_flood(room, player_r, player_c)
                           - (room.mist_cells or set()))


def _reveal_from(room, player_r: int, player_c: int) -> None:
    """After a door opens, remove all cells now visible from player from fog_cells."""
    if not room.fog_cells:
        return
    room.fog_cells -= _flood_reachable(room, player_r, player_c)


def _cell_char(room, r: int, c: int) -> str:
    """Return the printable character at (r, c) for f/F/t/T target matching.

    A glyph entity (the foe/NPC/dynamite the renderer draws ON TOP) wins over any
    char-run beneath it — so fA finds the Archivist and fW finds the Warden even
    when he stands on text (the wardenverse). Entities with no glyph of their own
    fall through to the character/terrain underneath. The entity→letter map lives
    in engine.world.entity_letter (shared with the renderer and search)."""
    ent = room.entity_at(r, c)
    if ent is not None:
        g = entity_letter(ent)
        if g is not None:
            return g
    ru = room.char_run_at(r, c)
    if ru:
        return ru.symbols[c - ru.col]
    if ent is not None:
        return '.'
    ct = room.cells[r][c]
    return '#' if ct in (CellType.WALL, CellType.WOOD_WALL) else '.'


# Vim's utf_class() (mbyte.c) class-1 PUNCTUATION ranges, reduced to a boolean.
# The crucial entry is {0x20a0, 0x27ff} "all kinds of symbols": every suit,
# planet, die, music note, gear and pentagram glyph this game uses is
# PUNCTUATION in Vim — w/b/e stop on them, W/B/E sail over (verified against
# `vim -u NONE`: a♠b → w stops on ♠; war☠den splits war|☠|den; an adjacent
# symbol run like ♠♥♦ is ONE punctuation word). Codepoints >= 0x100 outside
# these ranges default to word classes in Vim (Greek, Cyrillic, emoji, …).
# Boolean simplification: Vim's distinct own-classes (super/subscripts,
# braille — none appear in the game) are merged into "not a word char";
# exotic-script punctuation singletons from Vim's table and the CJK blocks
# are omitted as unreachable in the game's character universe.
_VIM_NONWORD_RANGES = (
    (0x2000, 0x206f),   # General Punctuation (†, ‡, ‽, ⁂, …)
    (0x2070, 0x207f),   # superscripts  (own class in vim)
    (0x2080, 0x2094),   # subscripts    (own class in vim)
    (0x20a0, 0x27ff),   # "all kinds of symbols": math, ⌘, ☆…⛧, suits, dice…
    (0x2800, 0x28ff),   # braille       (own class in vim)
    (0x2900, 0x2998),   # arrows, brackets
    (0x29d8, 0x29db), (0x29fc, 0x29fd),
    (0x2e00, 0x2e7f),   # Supplemental Punctuation
    (0x3001, 0x3020), (0x3030, 0x3030),   # ideographic punctuation
)


def _is_word_char(ch: str) -> bool:
    """Vim's word-class rule (default 'iskeyword' + utf_class), as a boolean.
    ASCII: [0-9A-Za-z_]. Latin-1: 0xC0-0xFF are keyword chars (vim's default
    iskeyword includes 192-255), the rest (°, §, ¶, ·, …) is punctuation.
    Higher planes: punctuation per _VIM_NONWORD_RANGES, word otherwise."""
    o = ord(ch)
    if o < 0x80:
        return ch.isalnum() or ch == '_'
    if o < 0x100:
        return o >= 0xC0
    return not any(lo <= o <= hi for lo, hi in _VIM_NONWORD_RANGES)


# ── Word-motion scan helpers ──────────────────────────────────────────────────
# w/b/e/ge share the word-class scans; W/B/E/gE the WORD-cluster scans. The
# wall/fog/void semantics are LOAD-BEARING and differ by family: the small-word
# scans treat a void rune as whitespace (w leaps over the void — the Surveyor's
# hall), while the WORD scans stop dead at one (any char run ends the gap, and a
# void run blocks the leap). Both stop at the first impassable cell — no word
# motion sails over a wall.

# When True (set only for the duration of a NAVIGATION apply_motion — not an
# operator's span computation), a content entity on BARE FLOOR is a word cell,
# so w/b/e/ge/gE can jump straight onto a key or a goblin. An entity standing ON
# text keeps that text's class (it is part of the word it stands on, never its
# own word). Operators (dw/de/cw) run with this OFF, so deletes are unchanged.
_ENTITY_STOPS = False


def _glyph_class(room, row: int, c: int):
    """The word-class of the glyph at (row, c) — _is_word_char as a bool — or None
    when the cell is impassable, bare floor, or a void rune (not a word cell).
    With _ENTITY_STOPS on, a content entity on otherwise-blank floor counts as a
    word cell (a jump target), reusing the CARET_TRANSPARENT rule ^ already uses."""
    if not room.is_passable(row, c):
        return None
    ru = room.char_run_at(row, c)
    if ru is not None and ru.kind != 'void':
        return _is_word_char(ru.symbols[c - ru.col])
    if _ENTITY_STOPS and getattr(room, 'entity_word_stops', True):
        ent = room.entity_at(row, c)
        if ent is not None and ent.alive and ent.kind not in CARET_TRANSPARENT:
            return True
    return None


def _run_edge(room, row: int, col: int, step: int) -> int:
    """Furthest column of the same word-class run containing (row, col), walking
    `step` (+1/-1). Assumes (row, col) is a word cell."""
    wc = _glyph_class(room, row, col)
    c = col
    while _glyph_class(room, row, c + step) == wc:
        c += step
    return c


def _next_glyph_cell(room, row: int, col: int, step: int):
    """First word cell from `col` walking `step`, skipping floor gaps AND void
    runes; None at the first impassable cell (w/b/e stop at walls)."""
    c = col
    while 0 <= c < room.cols and room.is_passable(row, c):
        if _glyph_class(room, row, c) is not None:
            return c
        c += step
    return None


def _next_cluster_stop(room, row: int, col: int, step: int):
    """W/B/E's gap scan from `col`: skip floor-only cells to the first cell
    holding ANY char run. None if a wall/impassable cell comes first or the
    found run is a void rune (○ blocks the WORD leap)."""
    c = col
    while 0 <= c < room.cols and room.is_passable(row, c) and not room.char_run_at(row, c):
        c += step
    if not (0 <= c < room.cols) or not room.is_passable(row, c):
        return None
    ru = room.char_run_at(row, c)
    if ru is None or ru.kind == 'void':
        return None
    return c


def _WORD_edge(room, row: int, col: int, step: int) -> int:
    """Furthest column of the WORD containing (row, col) — the maximal run of
    ADJACENT non-void clusters (no floor gap) — walking `step`. Assumes (row, col)
    is on a non-void cluster."""
    ru = room.char_run_at(row, col)
    if ru is None:
        return col            # cursor sits on a bare entity cell (a 1-cell WORD)
    while True:
        edge = (ru.col + len(ru.symbols) - 1) if step > 0 else ru.col
        nxt = edge + step
        if not (0 <= nxt < room.cols) or not room.is_passable(row, nxt):
            return edge
        ru2 = room.char_run_at(row, nxt)
        if ru2 is None or ru2.kind == 'void':
            return edge
        ru = ru2


def _cross_water(room, r: int, c: int) -> bool:
    """Like is_passable but also allows landing on water (for $, 0, ^ scans)."""
    if r < 0 or r >= room.rows or c < 0 or c >= room.cols:
        return False
    if room.cells[r][c] not in (CellType.FLOOR, CellType.CORRIDOR, CellType.WATER):
        return False
    if (r, c) in room.fog_cells:
        return False
    ent = room.entity_at(r, c)
    # Same blocker set as f/F/t/T (_SCAN_BLOCK): an unbroken seal_door stops $ / 0 / ^ too.
    return ent is None or ent.kind not in ('locked_door', 'shield', 'seal_door', 'boss_seal')


_PAIRS_OPEN  = {'(': ')', '[': ']', '{': '}'}
_PAIRS_CLOSE = {')': '(', ']': '[', '}': '{'}


def _leftmost_passable(room, row: int):
    """First passable column on a row, or None if the row has none."""
    for c in range(room.cols):
        if room.is_passable(row, c):
            return c
    return None


def _segment_left(room, row: int, col: int):
    """Leftmost floor cell contiguous with `col` on `row` — the left edge of the
    player's own segment. Bounded by terrain only (walls/water), so a paragraph
    jump stays out of separate rooms but still reaches the leftmost blank past a
    blocking ENTITY like the Warden's shield. None if `col` isn't on floor (the
    caller falls back to the row's global leftmost)."""
    def _floor(c: int) -> bool:
        return (room.cells[row][c] in (CellType.FLOOR, CellType.CORRIDOR)
                and (row, c) not in room.fog_cells)
    if not _floor(col):
        return None
    c = col
    while c - 1 >= 0 and _floor(c - 1):
        c -= 1
    return c


def _rightmost_passable(room, row: int):
    """Last passable column on a row, or None if the row has none — the end of the
    line (the corridor / ledge edge), used by `A` to append at the line's end."""
    for c in range(room.cols - 1, -1, -1):
        if room.is_passable(row, c):
            return c
    return None


def _caret_stop(room, row: int, c: int) -> bool:
    """True if column c on `row` is 'non-blank' for ^: it carries a character, or a
    notable entity (a key, foe, or loot — not a floor-like door/exit you stand on).
    The pass-through set lives in engine.world.CARET_TRANSPARENT."""
    if room.char_run_at(row, c) is not None:
        return True
    ent = room.entity_at(row, c)
    return ent is not None and ent.kind not in CARET_TRANSPARENT


def _first_non_blank_col(room, row: int):
    """First-non-blank column on a row: the first character if any, else the
    leftmost passable column. None if the row has no passable cell."""
    left = None
    for c in range(room.cols):
        if room.is_passable(row, c):
            if left is None:
                left = c
            if _caret_stop(room, row, c):     # a character or a notable entity (key, foe…)
                return c
    return left


def _bracket_at(room, row: int, c: int):
    """The bracket char ()[]{} at (row, c) if a character there is one, else None."""
    ru = room.char_run_at(row, c)
    if ru is not None:
        ch = ru.symbols[c - ru.col]
        if ch in _PAIRS_OPEN or ch in _PAIRS_CLOSE:
            return ch
    return None


def _row_has_rune(room, row: int) -> bool:
    return row in room._char_run_rows


def _sentence_terminates(room, row: int, c: int) -> bool:
    """A '.!?' at (row, c) ends a sentence only if followed by whitespace, the
    end of the line, or a single closing bracket/quote then whitespace/EOL —
    Vim-faithful. So a decimal point (the '.' in '17.3', followed by a digit)
    does NOT split the sentence."""
    nc = c + 1
    if nc < room.cols:
        ru = room.char_run_at(row, nc)
        if ru is not None and ru.symbols[nc - ru.col] in ')]}"\'':
            nc += 1                       # skip one closing bracket/quote
    if nc >= room.cols:
        return True                       # end of line
    ru = room.char_run_at(row, nc)
    return ru is None or ru.symbols[nc - ru.col] == ' '   # gap/floor or a space


def _sentence_starts(room, row: int) -> list:
    """Columns on `row` where a sentence begins. The first non-void rune starts
    a sentence; a '.!?' followed by whitespace/EOL ends one, so the next
    non-void rune after it starts the next. Row-scoped (cross-row flow can be
    added later)."""
    starts = []
    pending = True
    for c in range(room.cols):
        ent = room.entity_at(row, c)
        if ent is not None and ent.kind == 'dynamite':
            # a !-charge renders as '!' and ends a sentence when followed by space/EOL
            if _sentence_terminates(room, row, c):
                pending = True
            continue
        ru = room.char_run_at(row, c)
        if ru is None or ru.kind == 'void':
            continue
        # NOTE: wall-embedded glyphs DO seed sentence starts here — a
        # deliberate exception to the glyphs-in-stone law: the Inscription
        # Halls' ( ) route counts its wall-carved word bridges, and the
        # is_passable landing filter already keeps sealed starts unreachable.
        # (A west-wall plaque ahead of a row's text merely adds starts left
        # of the floor text; sentence objects pick the nearest start ≤ the
        # cursor, so floor resolution is unaffected.)
        if pending:
            starts.append(c)
            pending = False
        if ru.symbols[c - ru.col] in '.!?' and _sentence_terminates(room, row, c):
            pending = True
    return starts


def _sentence_starts_all(room) -> list:
    """Every sentence start in the buffer, in reading order — (row, col) tuples,
    top row to bottom and left to right within a row. Buffer-wide companion to
    _sentence_starts (which stays row-scoped for the is/as text objects)."""
    out = []
    for r in range(room.rows):
        for c in _sentence_starts(room, r):
            out.append((r, c))
    return out


def apply_motion(player, motion, count, room, target=None, count_given: bool = True,
                 game_h: int = 0, entity_stops: bool = True):
    """Navigation motions default to entity_stops=True: w/b/e/ge may land on a
    key or foe. Operator span computation (compute_text_object) passes
    entity_stops=False so dw/de/cw keep pure text-word boundaries."""
    global _ENTITY_STOPS
    _saved, _ENTITY_STOPS = _ENTITY_STOPS, entity_stops
    try:
        return _apply_motion_impl(player, motion, count, room, target, count_given, game_h)
    finally:
        _ENTITY_STOPS = _saved


def _apply_motion_impl(player, motion, count, room, target=None, count_given: bool = True, game_h: int = 0):
    moved = False
    _start = (player.row, player.col)     # word-motion landing guard (see return)
    for _ in range(count):
        if motion == 'h':
            moved |= move_player(player, 0, -1, room)
        elif motion == 'j':
            moved |= move_player(player, 1,  0, room)
        elif motion == 'k':
            moved |= move_player(player, -1, 0, room)
        elif motion == 'l':
            moved |= move_player(player, 0,  1, room)
        elif motion in ('+', '-'):
            # + / - (and NORMAL Enter ≡ +): one line down/up, landing on the
            # row's FIRST NON-BLANK (Vim-true). No move if the target row has
            # no standable fnb.
            nr = player.row + (1 if motion == '+' else -1)
            if 0 <= nr < room.rows:
                fnb = _first_non_blank_col(room, nr)
                if fnb is not None and room.is_passable(nr, fnb):
                    player.row, player.col = nr, fnb
                    moved = True
        elif motion == '_':
            # _ : first non-blank, [count]-1 lines down ({1}_ ≡ ^)
            nr = player.row + (count - 1)
            if 0 <= nr < room.rows:
                fnb = _first_non_blank_col(room, nr)
                if fnb is not None and room.is_passable(nr, fnb):
                    player.row, player.col = nr, fnb
                    moved = True
            break                                    # count is the target, not a repeat
        elif motion in ('gj', 'gk'):
            # gj/gk — move by DISPLAY line. On a wrapped single-line buffer that is
            # ±(wrap width) columns; on an ordinary grid it falls back to j/k.
            if getattr(room, 'wrap_buffer', False) and room.rows == 1:
                w  = getattr(room, '_wrap_w', 0) or room.cols
                nc = player.col + (w if motion == 'gj' else -w)
                nc = max(0, min(nc, room.cols - 1))
                if nc != player.col:
                    player.col = nc
                    moved = True
            else:
                moved |= move_player(player, 1 if motion == 'gj' else -1, 0, room)
        elif motion == '0':
            row = player.row
            left = player.col
            for c in range(player.col - 1, -1, -1):
                if not _cross_water(room, row, c):
                    break
                left = c
            if left != player.col:
                player.col = left
                moved = True
        elif motion == '$':
            row = player.row
            best = None
            for c in range(player.col + 1, room.cols):
                if not _cross_water(room, row, c):
                    break
                best = c
            if best is not None:
                player.col = best
                moved = True
        elif motion in ('^', 'g_'):
            # ^ — first non-blank of the segment; g_ — LAST non-blank (the
            # mirror). Both segment-bounded and caret-stop based, so g_
            # lands on the final glyph where $ would land on the final
            # PASSABLE cell (bare floor, a void brink, a drowning pool).
            row = player.row
            left = player.col
            for c in range(player.col - 1, -1, -1):
                if not _cross_water(room, row, c):
                    break
                left = c
            right = player.col
            for c in range(player.col + 1, room.cols):
                if not _cross_water(room, row, c):
                    break
                right = c
            if motion == '^':
                target = left
                for c in range(left, right + 1):
                    if _caret_stop(room, row, c):     # a character or a notable entity
                        target = c
                        break
            else:
                target = right
                for c in range(right, left - 1, -1):
                    if _caret_stop(room, row, c):
                        target = c
                        break
            if target != player.col:
                player.col = target
                moved = True
        elif motion == '|':
            # {n}| → column n (1-indexed); bare | → column 1. Count is the target,
            # not a repeat, so walk toward it and stop at a wall/water brink, then
            # break out of the count loop (mirrors G / gg). Column 1 is the first
            # standable column (the left border isn't a column).
            row = player.row
            target_col = max(0, min(room.first_standable_col() + count - 1, room.cols - 1))
            best = player.col
            step = 1 if target_col > player.col else -1
            for c in range(player.col + step, target_col + step, step):
                if not _cross_water(room, row, c):
                    break
                best = c
            if best != player.col:
                player.col = best
                moved = True
            break
        elif motion == 'w':
            row = player.row
            if _glyph_class(room, row, player.col) is not None:
                scan = _run_edge(room, row, player.col, +1) + 1   # past the current word
            else:
                scan = player.col + 1
            best = _next_glyph_cell(room, row, scan, +1)
            if best is not None:
                player.col = best
                moved = True
            else:
                break
        elif motion == 'b':
            row = player.row
            if _glyph_class(room, row, player.col) is not None:
                run_start = _run_edge(room, row, player.col, -1)
                if run_start < player.col:                # inside a word: to its start
                    player.col = run_start
                    moved = True
                    continue
            sc = _next_glyph_cell(room, row, player.col - 1, -1)
            if sc is not None:
                player.col = _run_edge(room, row, sc, -1)   # start of the previous word
                moved = True
            else:
                break
        elif motion == 'e':
            row = player.row
            if _glyph_class(room, row, player.col) is not None:
                end = _run_edge(room, row, player.col, +1)
                if end > player.col:                      # inside a word: to its end
                    player.col = end
                    moved = True
                    continue
                scan = end + 1
            else:
                scan = player.col + 1
            nc = _next_glyph_cell(room, row, scan, +1)
            if nc is not None:
                player.col = _run_edge(room, row, nc, +1)   # end of the next word
                moved = True
            else:
                break
        elif motion == 'W':
            row = player.row
            cur = room.char_run_at(row, player.col)
            scan = (cur.col + len(cur.symbols)) if (cur and cur.kind != 'void') \
                else player.col + 1
            # Skip the REST of the current WORD from scan — even off a void/blank
            # start: a cluster touching the cursor cell is the same WORD (no gap).
            if (scan < room.cols and room.is_passable(row, scan)
                    and _glyph_class(room, row, scan) is not None):
                scan = _WORD_edge(room, row, scan, +1) + 1
            found = _next_cluster_stop(room, row, scan, +1)
            if found is not None:
                player.col = found
                moved = True
            else:
                break
        elif motion == 'B':
            row = player.row
            pos = player.col
            cur = room.char_run_at(row, pos)
            if cur and cur.kind != 'void':
                word_start = _WORD_edge(room, row, pos, -1)
                if word_start < pos:                      # inside a WORD: to its start
                    player.col = word_start
                    moved = True
                    continue
                pos = word_start - 1                      # at the start: seek the previous WORD
            else:
                pos = pos - 1
            found = _next_cluster_stop(room, row, pos, -1)
            if found is not None:
                player.col = _WORD_edge(room, row, found, -1)
                moved = True
            else:
                break
        elif motion == 'E':
            row = player.row
            cur = room.char_run_at(row, player.col)
            if cur and cur.kind != 'void':
                end = _WORD_edge(room, row, player.col, +1)
                if end > player.col:                      # inside a WORD: to its end
                    player.col = end
                    moved = True
                    continue
                pos = end + 1
            else:
                pos = player.col + 1
            found = _next_cluster_stop(room, row, pos, +1)
            if found is not None:
                player.col = _WORD_edge(room, row, found, +1)
                moved = True
            else:
                break
        elif motion == 'G':
            # nG → line n; bare G → last line. Always land on first non-blank.
            # Scan inward from the target row if it is a wall (no passable cells).
            # Line 1 is the first standable row (the top border wall isn't a line).
            if count_given:
                target_row = max(0, min(room.first_standable_row() + count - 1, room.rows - 1))
                direction = 1
            else:
                target_row = room.rows - 1
                direction = -1
            col = None
            r = target_row
            while 0 <= r < room.rows:
                col = _first_non_blank_col(room, r)
                if col is not None:
                    target_row = r
                    break
                r += direction
            if col is not None:
                player.row = target_row
                player.col = col
                moved = True
            break
        elif motion == 'gg':
            # {n}gg → line n (like {n}G); bare gg → first line. Always land on
            # first non-blank, scanning downward to the first passable row.
            # Mirror of the G branch; independent of spawn/exit (Vim-faithful).
            if count_given:
                target_row = max(0, min(room.first_standable_row() + count - 1, room.rows - 1))
            else:
                target_row = room.first_standable_row()
            col = None
            r = target_row
            while 0 <= r < room.rows:
                col = _first_non_blank_col(room, r)
                if col is not None:
                    target_row = r
                    break
                r += 1
            if col is not None:
                player.row = target_row
                player.col = col
                moved = True
            break
        elif motion == 'ge':
            # Backward to the end of the previous word. Uses the word-class scan
            # (not raw char runs), so with entity_stops it also lands on a key or
            # foe sitting on bare floor (its own 1-cell word).
            row = player.row
            best = None
            nc = player.col - 1
            while nc >= 0:
                if not room.is_passable(row, nc):
                    break
                if _glyph_class(room, row, nc) is not None:
                    end_col = _run_edge(room, row, nc, +1)
                    if end_col < player.col:
                        best = end_col
                        break
                    nc = _run_edge(room, row, nc, -1) - 1   # skip left of this word
                    continue
                nc -= 1
            if best is not None:
                player.col = best
                moved = True
            else:
                break
        elif motion == 'gE':
            # Backward to the end of the previous WORD (maximal run of adjacent
            # non-void clusters, delimited by a floor gap or wall).
            row = player.row
            best = None
            nc = player.col - 1
            while nc >= 0:
                if not room.is_passable(row, nc):
                    break
                ru = room.char_run_at(row, nc)
                if ru and ru.kind != 'void':
                    end = _WORD_edge(room, row, nc, +1)   # extend right to WORD end
                    if end < player.col:
                        best = end
                        break
                    nc = ru.col - 1   # cursor within this WORD: skip left of its start
                    continue
                nc -= 1
            if best is not None:
                player.col = best
                moved = True
            else:
                break
        elif motion in ('H', 'M', 'L'):
            # Viewport-relative when game_h is provided and room exceeds it;
            # otherwise room-relative (H=first, L=last, M=middle passable row).
            if game_h > 0 and room.rows > game_h:
                vr_s = max(0, min(player.row - game_h // 2, room.rows - game_h))
                row_range = range(vr_s, min(vr_s + game_h, room.rows))
            else:
                row_range = range(room.rows)
            prows = []
            for _r in row_range:
                if _first_non_blank_col(room, _r) is not None:
                    prows.append(_r)
            if not prows:
                break
            if motion == 'H':
                tr = prows[0]
            elif motion == 'L':
                tr = prows[-1]
            else:
                tr = prows[len(prows) // 2]
            tc = _first_non_blank_col(room, tr)
            if (tr, tc) != (player.row, player.col):
                player.row, player.col = tr, tc
                moved = True
            else:
                break
        elif motion == '%':
            # Jump to the matching bracket. If not on a bracket, scan right on the
            # row for the first one (vim behaviour). Row-scoped, nesting-aware.
            row = player.row
            bch = _bracket_at(room, row, player.col)
            start = player.col if bch is not None else None
            if start is None:
                for c in range(player.col + 1, room.cols):
                    if room.cells[row][c] in (CellType.WALL, CellType.WOOD_WALL):
                        break
                    b = _bracket_at(room, row, c)
                    if b is not None:
                        start, bch = c, b
                        break
            tgt = None
            if start is not None:
                forward = bch in _PAIRS_OPEN
                want    = _PAIRS_OPEN[bch] if forward else _PAIRS_CLOSE[bch]
                scan    = range(start, room.cols) if forward else range(start, -1, -1)
                depth = 0
                for c in scan:
                    if room.cells[row][c] in (CellType.WALL, CellType.WOOD_WALL):
                        break
                    b = _bracket_at(room, row, c)
                    if b == bch:
                        depth += 1
                    elif b == want:
                        depth -= 1
                        if depth == 0:
                            tgt = c
                            break
            if tgt is not None and tgt != player.col:
                player.col = tgt
                moved = True
            else:
                break
        elif motion in ('{', '}'):
            # Paragraph jump: a blank row = a passable row with no characters.
            # The TARGET is Vim's — the first blank row in the direction — but
            # the LANDING is the left edge of the segment holding the player's
            # own column on that row, or NO MOVE if that column is walled
            # there. `}`/`{` can never vault a wall/moat sideways into a
            # sealed pocket, the entry, or the treasure room (a deliberate
            # deviation from Vim, where blank-line jumps ignore obstructions;
            # the old leftmost-cell and extreme-row fallbacks leaked exactly
            # those teleports, and skipping ahead to a further blank row
            # would mint long-range wormholes instead).
            row = player.row
            rng = range(row + 1, room.rows) if motion == '}' else range(row - 1, -1, -1)
            target_row = None
            for r in rng:
                if _leftmost_passable(room, r) is not None and not _row_has_rune(room, r):
                    target_row = r
                    break
            if target_row is None:
                break
            tc = _segment_left(room, target_row, player.col)
            if tc is None or (target_row, tc) == (player.row, player.col):
                break
            player.row, player.col = target_row, tc
            moved = True
        elif motion in ('(', ')'):
            # Sentence jump (buffer-wide): the next/previous sentence start
            # anywhere in the buffer — Vim-faithful, since sentences span lines.
            # Only PASSABLE starts are landings: a plaque word sealed in a
            # wall (or text across water/fog) begins a sentence the cursor
            # can never stand on — without this filter, ) hopped the player
            # into walls and straight past the Inscription Halls' bank gates.
            starts = [s for s in _sentence_starts_all(room)
                      if room.is_passable(*s)]
            cur = (player.row, player.col)
            if motion == ')':
                nxt = [s for s in starts if s > cur]
                if nxt:
                    player.row, player.col = nxt[0]
                    moved = True
                else:
                    break
            else:
                prev_s = [s for s in starts if s < cur]
                if prev_s:
                    player.row, player.col = prev_s[-1]
                    moved = True
                else:
                    break
        elif motion in ('f', 'F', 't', 'T'):
            if target is None:
                break
            if _apply_find(player, motion, target, room):
                player.last_f = (motion, target)
                moved = True
        elif motion == ';':
            if player.last_f:
                m, tgt = player.last_f
                moved |= _apply_find(player, m, tgt, room)
        elif motion == ',':
            if player.last_f:
                m, tgt = player.last_f
                rev = {'f': 'F', 'F': 'f', 't': 'T', 'T': 't'}[m]
                moved |= _apply_find(player, rev, tgt, room)
    if moved and motion in ('w', 'b', 'e', 'W', 'B', 'E', 'ge', 'gE') \
            and not room.is_passable(player.row, player.col):
        # Word-motion landing guard: the scan helpers stop at walls, but the
        # IN-WORD edge moves (b/B to a word's start, e/E to its end) walk the
        # run itself — and a run may straddle floor and wall (the Inscription
        # Halls' plaque crossing the promenade gap let B step INTO the wall
        # band). A landing the cursor cannot stand on fails the whole motion
        # (same rule as f/t, line jumps, search and the sentence jumps).
        player.row, player.col = _start
        moved = False
    return moved


_SCAN_BLOCK = frozenset(('shield', 'locked_door', 'seal_door', 'boss_seal'))


def _apply_find(player, motion: str, target: str, room) -> bool:
    """Raw f/F/t/T scan without updating player.last_f. Used by ; and ,."""
    row = player.row
    fwd = motion in ('f', 't')
    scan = range(player.col + 1, room.cols) if fwd else range(player.col - 1, -1, -1)
    for nc in scan:
        if room.cells[row][nc] in (CellType.WALL, CellType.WOOD_WALL):
            break
        if (row, nc) in room.fog_cells:
            break            # fog stops scans — the $ / 0 / ^ / search law
        ent = room.entity_at(row, nc)
        if ent and ent.kind in _SCAN_BLOCK:
            break
        if _cell_char(room, row, nc) == target:
            if motion in ('f', 'F'):
                dest = nc
            elif motion == 't':
                dest = nc - 1
            else:  # T
                dest = nc + 1
            if dest != player.col and room.is_passable(row, dest):
                player.col = dest
                return True
            break
    return False
