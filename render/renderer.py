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

"""Pure read-only renderer. Never mutates game state."""
from __future__ import annotations
import time
from blessed import Terminal
from engine.world import Dungeon, CellType, Room, CharRun, Entity, entity_letter
from engine.player import Player
from engine.modes import Mode, MODE_LABELS
from engine.visual import in_selection as _in_visual_sel
from engine.search import match_cells as _match_cells, find_next as _find_next
from engine.budget import Budget
import render.colors as C
import render.symbols as S
from render.utils import inner_w as _inner_w
from render.hint_bar import hint_text as _hint_text


def _is_vertical_door(room: Room, r: int, c: int, kind: str) -> bool:
    """Return True if the door at (r, c) is part of a vertical wall.

    A door is vertical when it has a same-kind door neighbour directly above or
    below — i.e. it belongs to a stacked column group blocking east-west movement.
    """
    for dr in (-1, 1):
        nb = room.entity_at(r + dr, c)
        if nb and nb.kind == kind:
            return True
    return False

# ── Water animation ────────────────────────────────────────────────────────────
# Each frame: (char, rgb, duration_seconds).
# ~ frames hold their full duration; ≈ is brief — a passing wave crest.
_WATER_FRAMES = [
    ('~',  (30,  95, 200), 8.0),   # calm — mid-blue
    ('≈',  (50, 130, 230), 0.8),   # passing wave — lighter blue (brief)
    ('~',  (15,  65, 170), 8.0),   # calm — deeper blue
    ('∼',  (40, 110, 215), 8.0),   # calm — medium
]
_WATER_PERIOD   = sum(d for _, _, d in _WATER_FRAMES)  # 24.8 s
_OVERLAP_PERIOD = 0.7   # seconds per full blink cycle (player ↔ entity under feet)

# ── Flame flicker ──────────────────────────────────────────────────────────────
# kind='flame' glyphs (the Beacon Tiers' signal fire) flicker between shades
# of yellow and orange — color only, the glyph never changes shape.
_FLAME_FRAMES = [
    ((255, 200,  40), 0.45),   # bright yellow flare
    ((235, 140,  20), 0.60),   # orange body
    ((255, 170,  30), 0.35),   # amber lick
    ((205, 105,  10), 0.50),   # deep orange ebb
]
_FLAME_PERIOD = sum(d for _, d in _FLAME_FRAMES)


def _flame_color(row: int, col: int) -> tuple[int, int, int]:
    """(r, g, b) for a flame glyph at the current instant; spatial offset keeps
    neighbouring flames out of phase, like the water."""
    offset = (row * 0.83 + col * 0.41) % _FLAME_PERIOD
    phase  = (time.time() + offset) % _FLAME_PERIOD
    t = 0.0
    for rgb, dur in _FLAME_FRAMES:
        t += dur
        if phase < t:
            return rgb
    return _FLAME_FRAMES[-1][0]


def _water_glyph(row: int, col: int) -> tuple[str, int, int, int]:
    """Return (char, r, g, b) for a water cell at the current instant."""
    # Diagonal spatial offset so adjacent cells are out of phase (÷4 wave density)
    offset = (row * 0.1375 + col * 0.045) % _WATER_PERIOD
    phase  = (time.time() + offset) % _WATER_PERIOD
    t = 0.0
    for char, rgb, dur in _WATER_FRAMES:
        t += dur
        if phase < t:
            return char, *rgb
    char, rgb, _ = _WATER_FRAMES[-1]
    return char, *rgb

_REG_ENTITY: dict[str, tuple[str, object]] = {
    'goblin':         ('g',  lambda: C.enemy_fg()),
    'warden':         ('W',  lambda: C.boss_fg()),
    'dynamite':       ('!',  lambda: C.dynamite_fg()),
    'door':           ('▬',  lambda: C.door_fg()),
    'locked_door':    ('⊞',  lambda: C.locked_door_fg()),
    'chest':          ('🞔', lambda: C.chest_fg()),
    'chest_key':      ('🞔', lambda: C.chest_fg()),
    'chest_scroll':   ('🞔', lambda: C.chest_fg()),
    'wanderer':       ('♟',  lambda: C.enemy_fg()),
    'shield':         (S.SHIELD, lambda: C.boss_fg()),
    'heart_container':('♥',  lambda: C.heart_full()),
    'floor_key':      (S.KEY, lambda: C.key_fg()),
    'exit':           ('◉',  None),
}


def _clip_to_items(clip) -> list:
    """Adapt the unnamed-register clip to _reg_display items (read-only view)."""
    if not clip:
        return []
    items: list = []
    for rw in clip.get('rows', []):
        for rd in rw.get('char_runs', []):
            items.append({'type': 'rune', 'rune': CharRun(0, 0, rd['symbols'], rd['kind'])})
        for ed in rw.get('entities', []):
            t = ed['tmpl']
            items.append({'type': 'entity',
                          'entity': Entity(kind=t['kind'], row=0, col=0, tag=t.get('tag', ''))})
    return items


def _reg_display(items: list) -> tuple[str, int]:
    """Returns (colored_string, visible_len) for the \" register statusline slot."""
    if not items:
        return '', 0

    # Collect (symbol, color_fn_or_None) pairs
    syms: list[tuple[str, object]] = []
    for item in items:
        if item['type'] == 'rune':
            for sym in item['rune'].symbols:
                syms.append((sym, None))
        elif item['type'] == 'entity':
            ent_e = item['entity']
            if ent_e.kind == 'floor_key' and ent_e.tag == 'gold':
                syms.append((S.KEY, lambda: C.key_gold_fg()))
            elif ent_e.kind == 'floor_key' and ent_e.tag == 'red':
                syms.append((S.KEY, lambda: C.key_red_fg()))
            elif ent_e.kind == 'floor_key' and ent_e.tag == 'blue':
                syms.append((S.KEY, lambda: C.key_blue_fg()))
            else:
                sym, col_fn = _REG_ENTITY.get(ent_e.kind, ('?', None))
                syms.append((sym, col_fn))
        elif item['type'] == 'cell':
            sym = {CellType.WALL: '█', CellType.WATER: '~',
                   CellType.WOOD_WALL: '░'}.get(item['cell_type'], ' ')
            syms.append((sym, None))

    truncated = len(syms) > 8
    display   = syms[:7] if truncated else syms

    parts: list[str] = []
    for sym, col_fn in display:
        if col_fn is not None:
            parts.append(col_fn() + sym + C.key_fg())
        else:
            parts.append(sym)
    if truncated:
        parts.append('…')

    vis = len(display) + (1 if truncated else 0)
    return ''.join(parts), vis


_ARROW_DIRS = {(1, 0): '↓', (-1, 0): '↑', (0, 1): '→', (0, -1): '←'}


def _arrow_color(ckey: str) -> str:
    """Attack-arrow colour = the attacker's normal glyph colour."""
    return {'ally':    C.ally_fg(),   'goblin':  C.enemy_fg(),
            'demon':   C.boss_fg(),   'critter': C.critter_fg(),
            'elf':     C.zombie_fg(), 'warden':  C.boss_fg(),
            'zombie':  C.zombie_fg()}.get(ckey, C.enemy_fg())


def _ent_cell_str(ent, room, r: int, c: int, mode, floor_bg: str) -> str:
    """Return the colored terminal string for one entity cell (no trailing reset needed)."""
    rst = C.normal_fg()
    if ent.kind == 'exit':
        # A gated exit sits on a WALL cell until its puzzle is solved — it is just
        # STONE until then (don't draw the open portal over a wall). It becomes the
        # portal the instant the cell is carved/opened to floor.
        if room.cells[r][c] == CellType.WALL:
            return C.wall_bg() + ' ' + rst
        return floor_bg + C.exit_fg() + S.EXIT + rst
    if ent.kind in ('chest', 'chest_key', 'chest_scroll'):
        return floor_bg + C.chest_fg() + S.CHEST + rst
    if ent.kind == 'hat':                       # the Warden's hat on the ground
        return floor_bg + C.shimmer_fg(time.time() * 0.5) + S.HAT + rst
    if ent.kind == 'horse':                     # the wizard's horse, post-game (Easter egg)
        return floor_bg + C.horse_fg() + S.HORSE + rst
    if ent.kind == 'door':
        sym = S.DOOR_V if _is_vertical_door(room, r, c, 'door') else S.DOOR_H
        return floor_bg + C.door_fg() + sym + rst
    if ent.kind == 'seal_door':
        return floor_bg + C.door_fg() + S.DOOR_H + rst
    if ent.kind == 'boss_seal':
        return floor_bg + C.locked_door_fg() + S.DOOR_LOCKED + rst
    if ent.kind == 'locked_door':
        sym = S.DOOR_V if _is_vertical_door(room, r, c, 'locked_door') else S.DOOR_LOCKED
        if ent.tag == 'gold':
            return floor_bg + C.key_gold_fg() + sym + rst
        if ent.tag == 'red':
            return floor_bg + C.key_red_fg() + sym + rst
        if ent.tag == 'blue':
            return floor_bg + C.key_blue_fg() + sym + rst
        return floor_bg + C.locked_door_fg() + sym + rst
    if ent.kind == 'dynamite':
        return floor_bg + C.dynamite_fg() + entity_letter(ent) + rst
    if ent.kind == 'wanderer':
        efg = C.enemy_frozen() if mode == Mode.VISUAL else C.enemy_fg()
        return floor_bg + efg + S.ENEMY_WANDERER + rst
    if ent.kind == 'goblin':
        if ent.tag == 'echo':                       # a false Warden — looks like a W, a shade off
            return floor_bg + C.boss_echo_fg(ent.shade) + entity_letter(ent) + rst
        if ent.tag == 'zombie':                     # sickly green, risen dead (Easter egg)
            return floor_bg + C.zombie_fg() + entity_letter(ent) + rst
        if ent.tag == 'demon':                      # hot red, summoned worse (Easter egg)
            return floor_bg + C.boss_fg() + entity_letter(ent) + rst
        return floor_bg + C.enemy_fg() + entity_letter(ent) + rst
    if ent.kind == 'ally':                          # a hound on your side (Easter egg)
        return floor_bg + C.ally_fg() + entity_letter(ent) + rst
    if ent.kind == 'critter':                       # a harmless cat (Easter egg)
        return floor_bg + C.critter_fg() + entity_letter(ent) + rst
    if ent.kind == 'gold':                          # a coin (Easter egg)
        return floor_bg + C.key_gold_fg() + entity_letter(ent) + rst
    if ent.kind == 'elf':                           # a merchant elf (Easter egg)
        return floor_bg + C.zombie_fg() + entity_letter(ent) + rst
    if ent.kind == 'warden':
        # A remote cut just glanced off him: he throws up his shield this frame
        # (the tell for edit-immunity — struck from afar and unharmed).
        if (r, c) in getattr(room, '_ward_flash', ()):
            return floor_bg + C.boss_fg() + S.SHIELD + rst
        # The Warden Eternal, once unmasked, wears his aura: a slow violet→blue
        # shimmer — the wizard/warden/W revealed in all his majesty.
        if ent.tag == 'eternal_boss' and getattr(room, '_wde_revealed', False):
            return floor_bg + C.shimmer_fg(time.time() * 0.5) + entity_letter(ent) + rst
        return floor_bg + C.boss_fg() + entity_letter(ent) + rst
    if ent.kind == 'shield':
        return floor_bg + C.boss_fg() + S.SHIELD + rst
    if ent.kind == 'brazier':
        # A standing flame (the Sigil) — the SAME flame the Beacon Tiers
        # introduced: the 🜂 glyph with the flicker, just entity-borne here
        # (an entity leaves its row blank; a flame CharRun would not).
        return floor_bg + C.rgb_fg(_flame_color(r, c)) + '🜂' + rst
    if ent.kind == 'heart_container':
        return floor_bg + C.heart_full() + '♥' + rst
    if ent.kind == 'floor_key':
        if ent.tag == 'gold':
            return floor_bg + C.key_gold_fg() + S.KEY + rst
        if ent.tag == 'red':
            return floor_bg + C.key_red_fg() + S.KEY + rst
        if ent.tag == 'blue':
            return floor_bg + C.key_blue_fg() + S.KEY + rst
        return floor_bg + C.key_fg() + S.KEY + rst
    if ent.kind == 'entry_marker':
        return floor_bg + C.hint_fg() + S.PLAYER + rst
    if ent.kind == 'archivist':                       # friendly NPC (The Archivist's Library)
        return floor_bg + C.key_gold_fg() + entity_letter(ent) + rst
    return floor_bg + '?' + rst


# ── Soft-wrap layout helpers (':set wrap' on a single-line buffer) ──────────
# Pure functions (no Terminal) so the wrap math is unit-testable in isolation.

def wrap_total_rows(cols: int, width: int) -> int:
    """Display rows a single logical line of `cols` columns occupies at `width`."""
    if width <= 0:
        return 1
    return max(1, -(-cols // width))   # ceil division


def wrap_scroll_start(cursor_col: int, cols: int, width: int, view_h: int) -> int:
    """First display row to show so the cursor's display row sits centred, clamped
    to [0, total_rows - view_h]."""
    if width <= 0 or view_h <= 0:
        return 0
    total       = wrap_total_rows(cols, width)
    cursor_drow = cursor_col // width
    start       = cursor_drow - view_h // 2
    return max(0, min(start, max(0, total - view_h)))


def wrap_room_col(drow: int, screen_c: int, width: int) -> int:
    """Logical column shown at display row `drow`, screen column `screen_c`."""
    return drow * width + screen_c


def _cmdline_with_cursor(prefix: str, text: str, cursor: int, width: int,
                         sl_bg: str, sl_fg: str) -> str:
    """Render an ex/search command line with a reverse-video block cursor at
    `cursor` (an index into `text`, so the prefix offsets it). Past the end of
    the text the cursor sits on a trailing space — Vim's cmdline cursor."""
    rst = C.normal_fg()
    cur = max(0, min(cursor, len(text)))
    body = text + ' '                                   # room for the end-cursor
    idx  = len(prefix) + cur                            # cursor's column in the full line
    full = prefix + body
    cur_ch = full[idx] if idx < len(full) else ' '
    left, right = full[:idx], full[idx + 1:]
    pad = max(0, width - len(full))
    return (sl_bg + C.mode_command() + left +
            C.cmd_cursor_bg() + C.cmd_cursor_fg() + cur_ch +
            sl_bg + C.mode_command() + right +
            sl_fg + ' ' * pad + rst)


def _wrap_cheatsheet(text: str, iw: int, max_rows: int = 2) -> list[str]:
    """Wrap a hint cheat-sheet into up to `max_rows` lines, breaking ONLY at
    command boundaries (the double space between entries), never mid-command.
    If content still remains past the last allowed row, that row is
    ellipsis-truncated so nothing overflows the box."""
    if len(text) <= iw:
        return [text]
    lines: list[str] = []
    rest = text
    while rest and len(lines) < max_rows:
        if len(rest) <= iw:
            lines.append(rest)
            rest = ''
            break
        cut = rest[:iw]
        sp  = cut.rfind('  ')
        if sp > iw // 3:
            lines.append(rest[:sp].rstrip())
            rest = rest[sp:].lstrip()
        else:                                   # no clean boundary → hard cut
            lines.append(rest[:iw])
            rest = rest[iw:]
    if rest:                                    # overflowed max_rows → ellipsize
        last = lines[-1]
        if len(last) >= iw:
            last = last[:iw - 1]
        lines[-1] = last.rstrip() + '…'
    return lines


def render_all(term: Terminal, dungeon: Dungeon, player: Player,
               budget: Budget, message: str = '',
               attack_pos: tuple | None = None, attack_sym: str = '',
               heart_flash: bool = False, recording: str = ''):
    room   = dungeon.room
    iw     = _inner_w(term)
    output = []

    bfg = C.border_fg()
    rst = C.normal_fg()

    def border_h(left, right, fill=S.BOX_H):
        line = bfg + left + fill * iw + right + rst
        return line

    # ── Row 0: top border ──────────────────────────────────────────────────
    output.append(border_h(S.BOX_TL, S.BOX_TR))

    # ── Row 1: status bar ─────────────────────────────────────────────────
    full_h  = player.hp // 2
    half_h  = player.hp % 2
    empty_h = player.max_hp // 2 - full_h - half_h
    if heart_flash:
        gold   = term.color_rgb(255, 210, 0)
        hp_str  = (gold + S.HEART_FULL  + rst) * full_h
        hp_str += (gold + S.HEART_HALF  + rst) * half_h
        hp_str += (gold + S.HEART_EMPTY + rst) * empty_h
    else:
        hp_str  = (C.heart_full()  + S.HEART_FULL  + rst) * full_h
        hp_str += (C.heart_half()  + S.HEART_HALF  + rst) * half_h
        hp_str += (C.heart_empty() + S.HEART_EMPTY + rst) * empty_h

    mode    = player.mode
    ml      = MODE_LABELS[mode]
    if mode == Mode.NORMAL:
        mode_s = C.mode_normal() + ml + rst
    elif mode == Mode.INSERT:
        mode_s = C.mode_insert() + ml + rst
    elif mode in (Mode.VISUAL, Mode.VISUAL_LINE, Mode.VISUAL_BLOCK):
        mode_s = C.mode_visual() + ml + rst
    else:
        mode_s = C.mode_command() + ml + rst

    par_val  = room.par or 0
    spent    = budget.spent
    if par_val > 0:
        if spent <= par_val:
            keys_color = C.budget_ok()
        elif spent <= int(par_val * 1.5):
            keys_color = C.budget_low()
        else:
            keys_color = C.budget_crit()
    else:
        keys_color = C.normal_fg()

    keys_s   = keys_color + f'Keys:{spent:2d}' + rst
    budget_s = C.hint_fg() + f' Budget:{budget.total:2d}' + rst
    par_s    = C.hint_fg() + f' Par:{room.par or "-"}' + rst
    # Gold (Easter-egg coins picked up from :s/g/$/) shows only once you have some.
    _gold = getattr(player, 'gold', 0)
    gold_plain = f'  ${_gold}' if _gold else ''
    gold_s     = (C.key_gold_fg() + f'  ${_gold}' + rst) if _gold else ''

    dname = dungeon.name[:30]      # 30 fits the longest names (Brace & Square
                                   # Enclosure = 28, Grandmaster's Sanctum = 25)
    status_plain = f'  {"♥"*full_h}{"♡"*half_h}{"░"*empty_h}  {dname}  {ml}  Keys:{spent:2d} Budget:{budget.total:2d}  Par:{room.par or "-"}{gold_plain}'
    padding = max(0, iw - len(status_plain))
    status_line = (bfg + S.BOX_V + rst +
                   f'  {hp_str}  ' +
                   C.normal_fg() + dname + '  ' +
                   mode_s + '  ' + keys_s + ' ' + budget_s + par_s + gold_s +
                   ' ' * padding +
                   bfg + S.BOX_V + rst)
    output.append(status_line)

    # ── Row 2: separator ──────────────────────────────────────────────────
    output.append(border_h(S.BOX_LT, S.BOX_RT))

    # ── Hint cheat-sheet (computed early: it may take a 2nd row, which steals
    #    one row from the game area so the box height still fits the terminal) ──
    known = player.known_commands
    if 'editor' in known:
        _hint_raw = 's:toggle wall  :rune ancient|verdant|void|ember  :entity exit|door|locked_door|chest|dynamite|wanderer|goblin|warden  :save <name>  :wq write+quit'
    else:
        _hint_raw = _hint_text(known, getattr(dungeon, 'level_slug', None))
    if 'admin' in known:
        _hint_raw += '  :e refresh'
    hint_lines = _wrap_cheatsheet(_hint_raw, iw, max_rows=2)

    # ── Game area ─────────────────────────────────────────────────────────
    # 8 fixed rows: top_border, status, top_sep, [game_h rows], statusline,
    # message, bot_sep, hint, bot_border — plus one per EXTRA hint row.
    game_h  = term.height - 8 - (len(hint_lines) - 1)
    # :set number gutter (dungeon line numbers) — opt-in via player.number_mode;
    # default 'none' leaves the layout exactly as before (no gutter).
    number_mode = getattr(player, 'number_mode', 'none')
    gutter_w  = 0 if number_mode == 'none' else 4      # "123 "
    content_w = max(1, iw - gutter_w)

    # Viewport: centre on player (over the content width, right of the gutter)
    vr_start = max(0, min(player.row - game_h // 2,    room.rows - game_h))
    vc_start = max(0, min(player.col - content_w // 2, room.cols - content_w))
    vr_start = max(0, vr_start)
    vc_start = max(0, vc_start)

    gnum_fg = C.hint_fg()                              # dim gutter ink
    base_row = room.first_standable_row()              # grid row of line 1 (border isn't a line)
    def _gutter(room_r):
        if gutter_w == 0:
            return ''
        # Rows at/above the border (before line 1) get a blank gutter — they aren't lines.
        if room_r >= room.rows or room_r < base_row:
            return wall_bg + ' ' * gutter_w + rst
        if number_mode == 'relativenumber':
            n = 0 if room_r == player.row else abs(room_r - player.row)
        else:
            n = room_r - base_row + 1
        return gnum_fg + f'{n:>{gutter_w - 1}} ' + rst

    # ── Soft-wrap (':set wrap' on a single-line Room.wrap_buffer) ────────────
    wrap_active = (getattr(player, 'wrap', False)
                   and getattr(room, 'wrap_buffer', False)
                   and room.rows == 1)
    if wrap_active:
        # A room may pin a FIXED fold width (room.wrap_width) so the line wraps the same
        # on any terminal (the Wardenverse needs its stone walls to land at fold edges);
        # otherwise wrap to the live content width. Never exceed the visible width.
        wrap_w = min(getattr(room, 'wrap_width', 0) or content_w, content_w)
        total_drows = wrap_total_rows(room.cols, wrap_w)
        dr_start    = wrap_scroll_start(player.col, room.cols, wrap_w, game_h)
        room._wrap_w = wrap_w      # stash the live wrap width for gj/gk display-line motion

    def _gutter_wrap(drow):
        # The wrap buffer is ONE logical line: number only its first display row,
        # blank gutter on continuation rows (Vim behaviour).
        if gutter_w == 0:
            return ''
        if drow != 0:
            return gnum_fg + ' ' * gutter_w + rst
        n = 0 if number_mode == 'relativenumber' else 1
        return gnum_fg + f'{n:>{gutter_w - 1}} ' + rst

    base_floor_bg = C.floor_bg()
    wall_bg  = C.wall_bg()
    vis_bg   = C.visual_sel_bg()
    threat_bg = C.threat_sel_bg()
    hl_bg     = C.search_hl_bg()
    cur_bg    = C.search_cur_bg()
    _threat   = getattr(room, 'surveyor_threat', None)   # warden's telegraphed v-selection
    _mega      = getattr(room, 'mega', None)             # Warden Pathfinder floor-tear
    _mega_warn = (_mega['band'] if (_mega and _mega.get('phase') == 'warn') else set())
    _torn      = getattr(room, 'torn', set())
    _vis_active = (mode in (Mode.VISUAL, Mode.VISUAL_LINE, Mode.VISUAL_BLOCK)
                   and getattr(player, 'visual_anchor', None) is not None)
    _vis_cursor = (player.row, player.col)

    # Search highlighting: incsearch (live, while typing /…?…) takes precedence
    # over hlsearch (all matches of the last confirmed pattern). _cur_cells is the
    # match the cursor would jump to (the incsearch preview target).
    _hl_cells: set = set()
    _cur_cells: set = set()
    if mode == Mode.SEARCH and player.cmd_line and getattr(player, 'incsearch', True):
        _hl_cells = _match_cells(room, player.cmd_line)
        dest = _find_next(room, player, player.cmd_line, player.search_forward)
        if dest is not None:
            _cur_cells = {(dest[0], dest[1] + k) for k in range(len(player.cmd_line))}
    elif (getattr(player, 'last_search', None) and getattr(player, 'hlsearch', True)
          and not getattr(player, 'hl_suppressed', False)):
        _hl_cells = _match_cells(room, player.last_search[0])

    def _cell(room_r, room_c):
        """Render one IN-BOUNDS room cell to its coloured string fragment.
        Shared verbatim by the nowrap and wrap screen-row loops."""
        if room_r in _mega_warn:                          # telegraphed doomed rows — clear off!
            floor_bg = threat_bg
        elif (_threat is not None and 'r0' in _threat
                and _threat['r0'] <= room_r <= _threat['r1']
                and _threat['c0'] <= room_c <= _threat['c1']):
            floor_bg = threat_bg
        elif _vis_active and _in_visual_sel(
                player.visual_anchor, _vis_cursor, mode, room_r, room_c):
            floor_bg = vis_bg
        elif (room_r, room_c) in _cur_cells:
            floor_bg = cur_bg
        elif (room_r, room_c) in _hl_cells:
            floor_bg = hl_bg
        else:
            floor_bg = base_floor_bg
        ct = room.cells[room_r][room_c]

        # Player?
        if room_r == player.row and room_c == player.col:
            ent_under  = room.entity_at(room_r, room_c)
            show_under = ent_under and (
                time.time() % _OVERLAP_PERIOD >= _OVERLAP_PERIOD / 2
            )
            if show_under:
                return _ent_cell_str(ent_under, room, room_r, room_c, mode, floor_bg)
            # Wearing the Warden's hat shimmers the cursor with his aura.
            _pfg = (C.shimmer_fg(time.time() * 0.5)
                    if getattr(player, 'hat_worn', False) else C.player_fg())
            return floor_bg + _pfg + S.PLAYER + C.normal_fg()

        # Torn floor (Warden mega-attack) — a void pit until he pastes it back
        if (room_r, room_c) in _torn:
            return wall_bg + C.hint_fg() + '·' + C.normal_fg()

        # Fog?
        if (room_r, room_c) in room.fog_cells:
            if (room.cells[room_r][room_c] == CellType.WATER
                    and (room_r, room_c) in room.mist_cells):
                # MIST on water reads as hazy water, not stone — the channel
                # stays visibly a channel (scans still stop at the fog).
                # Plain-fogged water is DARK like any hidden cell: an
                # unrevealed pool gives nothing away.
                return C.water_bg() + C.hint_fg() + '~' + C.normal_fg()
            if ((room_r, room_c) not in room.mist_cells
                    or room.char_run_at(room_r, room_c) is None):
                return wall_bg + ' ' + C.normal_fg()
            # MISTED FLOOR carrying a glyph: text across a chasm — readable in
            # full colour but never standable, searchable, or cuttable (the fog
            # bars feet and match-landings; only ranged ex commands reach it).
            # Fall through to the ordinary char-run rendering.

        # Attack-direction arrows (room._atk_arrows): every attacker — goblin,
        # hound, elf, big cat, Warden — flashes a directional arrow in the colour
        # of its own glyph, pointing at what it struck.
        for (_fr, _fc, _tr, _tc, _ck) in getattr(room, '_atk_arrows', ()):
            if (_fr, _fc) == (room_r, room_c):
                _dr = (_tr > _fr) - (_tr < _fr)
                _dc = (_tc > _fc) - (_tc < _fc)
                return (floor_bg + _arrow_color(_ck)
                        + _ARROW_DIRS.get((_dr, _dc), '✕') + C.normal_fg())

        # Entity?
        ent = room.entity_at(room_r, room_c)
        if ent and attack_sym and attack_pos == (room_r, room_c):
            return floor_bg + term.color_rgb(220, 50, 50) + attack_sym + C.normal_fg()
        if ent:
            return _ent_cell_str(ent, room, room_r, room_c, mode, floor_bg)

        # Character run?
        ru = room.char_run_at(room_r, room_c)
        if ru:
            idx = room_c - ru.col
            sym = ru.symbols[idx]
            if ru.kind == 'flame':
                return (floor_bg + term.color_rgb(*_flame_color(room_r, room_c))
                        + sym + C.normal_fg())
            rfg = {'ancient': C.rune_ancient(), 'verdant': C.rune_verdant(),
                   'void': C.rune_void(), 'ember': C.rune_ember(),
                   'pedestal': C.rune_pedestal()}.get(ru.kind, C.normal_fg())
            # A glyph takes the BACKGROUND of the terrain it sits on, so a plaque
            # carved into a wall reads as stone (matching the empty wall cells
            # around it), not as floor. Floor/corridor glyphs keep floor_bg with
            # its cursor-line / selection / search-highlight state.
            if ct == CellType.WALL:
                glyph_bg = wall_bg
            elif ct == CellType.WOOD_WALL:
                glyph_bg = C.wood_wall_bg()
            elif ct == CellType.WATER:
                glyph_bg = C.water_bg()
            else:
                glyph_bg = floor_bg
            return glyph_bg + rfg + sym + C.normal_fg()

        # Cell type
        if ct == CellType.WATER:
            ch, wr, wg, wb = _water_glyph(room_r, room_c)
            return C.water_bg() + C.water_fg(wr, wg, wb) + ch + C.normal_fg()
        elif ct == CellType.WALL:
            return wall_bg + ' ' + C.normal_fg()
        elif ct == CellType.WOOD_WALL:
            if room.wood_damage.get((room_r, room_c), 0):
                return (C.wood_wall_damaged_bg() + C.wood_wall_damaged_fg()
                        + S.WOOD_WALL_DAMAGED + C.normal_fg())
            return C.wood_wall_bg() + ' ' + C.normal_fg()
        return floor_bg + ' ' + C.normal_fg()

    for screen_r in range(game_h):
        if wrap_active:
            # One logical line wrapped across screen rows (':set wrap'). The room
            # stays 1×cols; only the view wraps, so _cell is reused unchanged.
            drow = screen_r + dr_start
            line = bfg + S.BOX_V + rst + _gutter_wrap(drow)
            if drow >= total_drows:
                # Past the wrapped line's end → Vim '~' filler row.
                line += C.hint_fg() + '~' + rst + base_floor_bg + ' ' * (content_w - 1) + rst
            else:
                for screen_c in range(content_w):
                    if screen_c >= wrap_w:
                        line += base_floor_bg + ' ' + rst   # right of the fixed fold width
                        continue
                    room_c = wrap_room_col(drow, screen_c, wrap_w)
                    if room_c >= room.cols:
                        line += base_floor_bg + ' ' + rst   # past line end on its last display row
                    else:
                        line += _cell(0, room_c)
            line += bfg + S.BOX_V + rst
            output.append(line)
            continue

        room_r = screen_r + vr_start
        line   = bfg + S.BOX_V + rst + _gutter(room_r)
        if room_r >= room.rows:
            line += wall_bg + ' ' * content_w + rst
        else:
            for screen_c in range(content_w):
                room_c = screen_c + vc_start
                if room_c >= room.cols:
                    line += wall_bg + ' ' + rst
                else:
                    line += _cell(room_r, room_c)
        line += bfg + S.BOX_V + rst
        output.append(line)

    # ── The Codex pane (:h) — a horizontal split over the game area ────────
    # :help opens another file read-only in a split and moves focus into it.
    # Vim's default puts help at the TOP; ours opens BELOW — the 'splitbelow'
    # house style (user preference 2026-07-17: the dungeon stays put up top).
    # The pane replaces the BOTTOM rows of the game area (a pure view).
    pane = getattr(player, 'codex_pane', None)
    if pane is not None:
        pane_h = max(6, min(game_h // 2, game_h - 2))
        body_h = pane_h - 1                     # row 0 is the pane's statusline
        title  = '  THE CODEX  [RO]  '
        bar = (bfg + S.BOX_V + rst
               + C.mode_command() + title + rst
               + C.hint_fg() + '─' * max(0, iw - len(title)) + rst
               + bfg + S.BOX_V + rst)
        pane_lines = [bar]
        rows = pane.render_rows(body_h, iw - 2)
        # An active /search or :cmd input takes over the pane's last row.
        input_line = None
        if pane.search_input is not None:
            input_line = '/' + pane.search_input
        elif pane.cmd_input is not None:
            input_line = ':' + pane.cmd_input
        if input_line is not None:
            rows = rows[:-1]
        for text, is_cur, is_ridge in rows:
            fg = C.rune_ember() if is_ridge else C.normal_fg()
            bg = C.visual_sel_bg() if is_cur else C.floor_bg()
            body = ' ' + text[:iw - 2].ljust(iw - 2) + ' '
            pane_lines.append(bfg + S.BOX_V + rst + bg + fg + body
                              + rst + bfg + S.BOX_V + rst)
        if input_line is not None:
            body = ' ' + input_line[:iw - 2].ljust(iw - 2) + ' '
            pane_lines.append(bfg + S.BOX_V + rst + C.floor_bg()
                              + C.mode_command() + body + rst
                              + bfg + S.BOX_V + rst)
        output[3 + game_h - pane_h: 3 + game_h] = pane_lines

    # ── Vim statusline / command line ─────────────────────────────────────
    # 1-based line,col anchored at the first standable cell — matches the gutter and
    # {N}G / {N}| (the border walls aren't line/column 1).
    pos_str  = f'{player.row - room.first_standable_row() + 1},{player.col - room.first_standable_col() + 1}'

    if wrap_active:
        if total_drows <= game_h:
            scroll = 'All'
        elif dr_start == 0:
            scroll = 'Top'
        elif dr_start + game_h >= total_drows:
            scroll = 'Bot'
        else:
            scroll = f'{int((dr_start + game_h // 2) / total_drows * 100)}%'
    elif room.rows <= game_h:
        scroll = 'All'
    elif vr_start == 0:
        scroll = 'Top'
    elif vr_start + game_h >= room.rows:
        scroll = 'Bot'
    else:
        pct    = int((vr_start + game_h // 2) / room.rows * 100)
        scroll = f'{pct}%'

    sl_bg  = C.statusline_bg()
    sl_fg  = C.statusline_fg()
    sl_w   = iw

    if player.error:
        # Vim-style error: red background, white text
        err_pad = max(0, sl_w - len(player.error) - 1)
        output.append(bfg + S.BOX_V + rst +
                      C.error_bg() + C.error_fg() + ' ' + player.error +
                      ' ' * err_pad + rst +
                      bfg + S.BOX_V + rst)
    elif mode == Mode.COMMAND:
        # Command line: prefix + typed command, with a block cursor at the
        # edit position (Vim's cmdline cursor — arrow-editable mid-string).
        output.append(bfg + S.BOX_V + rst +
                      _cmdline_with_cursor(':', player.cmd_line,
                                           player.cmd_cursor, sl_w,
                                           sl_bg, sl_fg) +
                      bfg + S.BOX_V + rst)
    elif mode == Mode.SEARCH:
        # Search line: '/' or '?' prefix + typed pattern, with the block cursor
        prefix = '/' if player.search_forward else '?'
        output.append(bfg + S.BOX_V + rst +
                      _cmdline_with_cursor(prefix, player.cmd_line,
                                           player.cmd_cursor, sl_w,
                                           sl_bg, sl_fg) +
                      bfg + S.BOX_V + rst)
    else:
        # Statusline: mode label left, position+scroll right. Vim's showmode
        # appends `recording @a` while a macro is being recorded (and keeps it
        # there until the stop-q), so we do the same.
        sl_label = MODE_LABELS[mode]
        if recording:
            sl_label = f'{sl_label}  recording @{recording}'
        if mode == Mode.NORMAL:
            sl_mode_color = C.mode_normal()
        elif mode == Mode.INSERT:
            sl_mode_color = C.mode_insert()
        else:
            sl_mode_color = C.mode_visual()
        sl_right = f'{pos_str}   {scroll} '
        if 'register' in player.known_commands:
            reg_colored, reg_vis_len = _reg_display(
                _clip_to_items(player.registers.get('"')))
            reg_s   = C.key_fg() + '  "' + reg_colored + sl_fg
            reg_vis = 3 + reg_vis_len  # len('  "') + visible content
        else:
            reg_s   = ''
            reg_vis = 0
        sl_mid   = max(0, sl_w - len(sl_label) - 2 - reg_vis - len(sl_right))
        output.append(bfg + S.BOX_V + rst +
                      sl_bg + sl_mode_color + ' ' + sl_label + ' ' +
                      sl_bg + sl_fg + reg_s + ' ' * sl_mid + sl_right + rst +
                      bfg + S.BOX_V + rst)

    # ── Bottom separator (answer sheet for admin) ─────────────────────────
    if room.answer:
        prefix   = ' ▸ '
        ans      = room.answer
        pos      = room.answer_pos
        diverged = room.answer_diverged

        # Find split: index of the pos-th non-space char in ans
        count = 0
        split = len(ans)
        for i, ch in enumerate(ans):
            if count >= pos:
                split = i
                break
            if ch != ' ':
                count += 1

        # Karaoke tape: pin the playhead at ANCHOR chars from the left of the
        # display window, so consumed text scrolls off left and upcoming always
        # fills the remaining width.
        ANCHOR   = 8                   # chars of consumed tail shown at left
        up_w     = iw - len(prefix)    # display chars after the prefix arrow
        win_start = max(0, split - ANCHOR)
        win_text  = ans[win_start : win_start + up_w]
        win_split = split - win_start  # split col within the window (≤ ANCHOR)

        up_color  = C.answer_warn() if diverged else C.budget_ok()
        pad       = ' ' * max(0, up_w - len(win_text))
        output.append(
            bfg + S.BOX_LT + rst +
            C.budget_ok()       + prefix +
            C.answer_consumed() + win_text[:win_split] +
            up_color            + win_text[win_split:] + pad + rst +
            bfg + S.BOX_RT + rst)
    else:
        output.append(border_h(S.BOX_LT, S.BOX_RT))

    # ── Message bar ───────────────────────────────────────────────────────
    if message:
        # Truncate to the viewport with an ellipsis; long dialogue is split into
        # short pushes that rotate via the (n/m) pool, so each part fits on the bar.
        msg_text = message if len(message) <= iw else message[:max(1, iw - 1)] + '…'
        msg_pad  = max(0, iw - len(msg_text))
        output.append(bfg + S.BOX_V + rst +
                      C.budget_low() + msg_text + rst + ' ' * msg_pad +
                      bfg + S.BOX_V + rst)
    else:
        output.append(bfg + S.BOX_V + rst + ' ' * iw + bfg + S.BOX_V + rst)

    # ── Hint bar (wraps to a 2nd row when the cheat sheet is long) ──────────
    for _line in hint_lines:
        hint = C.hint_fg() + _line + rst
        output.append(bfg + S.BOX_V + rst + hint +
                      ' ' * max(0, iw - len(_line)) + bfg + S.BOX_V + rst)

    # ── Bottom border ──────────────────────────────────────────────────────
    output.append(border_h(S.BOX_BL, S.BOX_BR))

    print(term.home + '\n'.join(output), end='', flush=True)
