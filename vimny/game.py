#!/usr/bin/env python3
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

"""Vimny — entry point and main game loop."""
from __future__ import annotations
import random, time, argparse, re, sys
from collections import deque
from pathlib import Path
from blessed import Terminal
import vimny.render.colors as C
from vimny.render.renderer import render_all
import vimny.render.symbols as S
from vimny.render.utils import inner_w as _iw
from vimny.render.overworld import (render_overworld, build_lines, default_cursor,
                              line_search_text)
from vimny.sharing.library import build_shelved, list_levels as community_levels
from vimny.sharing import remote as REMOTE
import vimny.sharing.draft as DRAFT
import vimny.sharing.format as LF
import vimny.sharing.submit as SUBMIT
from vimny.sharing.vocab import (POOLS as _VOCAB_POOLS, LINE_POOLS as _VOCAB_LINE_POOLS,
                           min_saying_width as _min_saying_width)
from vimny.engine.vimregex import compile_vim as _vre_compile
from vimny.render.title import render_title, render_save_select, select_quote, select_quote_by_name, select_next_lesson_quote, next_lesson_quote_entry, format_quote, MENU_ITEMS as _TITLE_MENU, NAME_MAX as _NAME_MAX
from vimny.render.wizard_blessing import run_wizard_blessing
from vimny.engine.player import Player
from vimny.engine.modes import Mode
from vimny.engine.tape import (ESC as _TAPE_ESC, ENTER as _TAPE_ENTER,
                         SPACE as _TAPE_SPACE, CTRL_V as _TAPE_CTRL_V,
                         from_keystroke as _tape_key)
from vimny.engine.budget import Budget
from vimny.engine.vim_parser import parse, parse_visual_textobj
from vimny.engine.command_guard import (action_allowed as _action_allowed_raw,
                                  guard_message as _guard_message_raw,
                                  _MOTION_GUARD as _MOTION_GUARD_TABLE)
from vimny.engine.world import (DROPPABLE, Entity, CellType, CharRun, Dungeon, Seal,
                          SEAL_OPENED, canonical_kind, clone_entity,
                          entity_letter, strike_disguise)
from vimny.engine.motion import (apply_motion, _apply_esc, _reveal_from,
                           _first_non_blank_col, auto_fog_tick as _auto_fog_tick,
                           enforce_fog_law as _enforce_fog_law, unhide_region)
from vimny.engine.text_object import compute_text_object, resolve_text_object, TextObjectType
from vimny.engine.search import find_next as _search_next, word_under_cursor as _word_under_cursor
from vimny.engine.warden_mega import mega_tick
from vimny.engine.options import apply_set as _apply_set, parse_modifier as _parse_set_mod
from vimny.engine.macro import synth_key as _synth_key, record_char as _record_char
from vimny.engine.jumplist import record_jump as _record_jump, jump_back as _jump_back, jump_forward as _jump_forward
from vimny.engine.registers import (write_register as _reg_write, read_register as _reg_read,
                              record_register as _reg_record, clip_to_keys as _reg_keys,
                              clip_to_text as _reg_text)
from vimny.engine.visual import (apply_visual, block_bounds, apply_visual_replace,
                                 in_selection, swap_ends as _swap_ends)
from vimny.content.scrolls import (
    # Codex scroll content rendered by _show_scroll_by_id (_STD_SCROLLS map);
    # every other catalogue scroll renders via _show_catalog_scroll.
    RELIQUARY_SCROLL, WARDEN_LEAP_SCROLL, WARDEN_SIGHT_SCROLL, SURVEYORS_PATH_SCROLL,
    WAYPOINT_SCROLL,
    OPERATOR_CODEX_SCROLL, INSCRIBERS_HAND_SCROLL,
    WHOLE_WORD_SCROLL, REWRITING_WORD_SCROLL,
    pick_relic_scroll as _pick_relic_scroll,
)

_JUMP_MOTIONS = frozenset({'G', 'gg', '%', '{', '}', '(', ')'})
from vimny.engine.operator import op_delete, op_yank, op_paste, op_case, op_join, case_char, apply_indent, apply_equalize, law_column, INDENT_WIDTH, entity_clip
from vimny.engine.reflow import is_ledge, close_gap, void_col, _insert_blank_row, remove_row, split_line_down
from vimny.engine import substitute as _subst
from vimny.engine.insert import (
    begin_insert, insert_char, insert_char_extend, insert_backspace,
    insert_delete_word_back, insert_delete_to_start,
    replace_chars, replace_overtype, replace_restore,
)
from vimny.engine.editor import (
    _merge_adjacent_char_runs, _split_run_at, _ed_cut, _ed_snapshot, _ed_restore, _ed_paint,
    PAINT_KINDS,
    _ed_paste, _ed_row_items, _ed_clear_row, _ed_range_items, _ed_delete_range,
    _clip_desc, _serialize_room, _deserialize_room, in_fill as _in_fill,
    slot_at as _slot_at,
)
import vimny.generation.dungeon_gen as _dg
from vimny.generation.room_gen import RUNE_CHAR as _RUNE_CHAR
from vimny.content.levels import LEVELS, is_unlocked, level_type, known_commands as _known_commands
import vimny.save.save_manager as SM
import vimny.features as FEAT


_WATER_SETTLE_SECS = 60   # stop animating water after this many idle seconds
# Shown when A's ledge-build or a J join would run past the buffer's max width.
_EDGE_OF_WORLD_MSG = 'The edge of the world — no stone lies beyond it.'


def _cmd_append(cmd_line: str, key) -> str:
    """Append key to cmd_line only for non-sequence (printable) keys.

    Sequence keys (arrow keys, F-keys, Home/End, …) carry terminal escape
    codes in str(key).  If those bytes reach a print() call they are
    interpreted by the terminal as cursor-movement commands, corrupting the
    display.  Always route cmd_line growth through this helper.
    """
    if key.is_sequence:
        return cmd_line
    return cmd_line + str(key)


def _cmd_insert(player, text: str) -> None:
    """Insert `text` into player.cmd_line at the cursor (Vim's command line is
    editable mid-string), advancing the cursor past it."""
    c = player.cmd_cursor
    player.cmd_line = player.cmd_line[:c] + text + player.cmd_line[c:]
    player.cmd_cursor = c + len(text)


def _cmd_backspace(player) -> None:
    """Delete the char BEFORE the cursor (Vim's <BS>); no-op at column 0."""
    c = player.cmd_cursor
    if c > 0:
        player.cmd_line = player.cmd_line[:c - 1] + player.cmd_line[c:]
        player.cmd_cursor = c - 1


def _cmd_arrow(player, key) -> bool:
    """Handle Left/Right/Home/End cursor motion on the command line. Returns
    True if the key was a recognised cursor motion (and was applied)."""
    name = key.name
    n = len(player.cmd_line)
    if name == 'KEY_LEFT':
        player.cmd_cursor = max(0, player.cmd_cursor - 1)
    elif name == 'KEY_RIGHT':
        player.cmd_cursor = min(n, player.cmd_cursor + 1)
    elif name == 'KEY_HOME':
        player.cmd_cursor = 0
    elif name == 'KEY_END':
        player.cmd_cursor = n
    else:
        return False
    return True

class _CmdLine:
    """Shared ':' command-line state for the netrw-style screens (overworld,
    scroll library, parent dir, colors): accumulates typed input and Tab-completes
    ':e <path>' against a fixed completion list. ``feed`` handles one key while
    active; it returns the submitted command on Enter ('' on Escape / empty
    Enter), or None while entry continues."""

    def __init__(self, completions: list[str] | None = None):
        self.completions = completions or []
        self.active = False
        self.line   = ''
        self._reset_tab()

    def _reset_tab(self) -> None:
        self._matches: list[str] = []
        self._idx = -1

    def open(self) -> None:
        self.active = True
        self.line   = ''
        self._reset_tab()

    def feed(self, key) -> str | None:
        if key.name == 'KEY_ESCAPE':
            self.active = False
            self.line   = ''
            self._reset_tab()
            return ''
        if str(key) == '\t':
            if self.line == 'e' or self.line.startswith('e '):
                partial = self.line[2:] if self.line.startswith('e ') else ''
                new_m   = [c for c in self.completions if c.startswith(partial)]
                if new_m:
                    if new_m != self._matches:
                        self._matches, self._idx = new_m, 0
                    else:
                        self._idx = (self._idx + 1) % len(self._matches)
                    self.line = 'e ' + self._matches[self._idx]
            return None
        if key.name == 'KEY_ENTER' or str(key) in ('\n', '\r'):
            cmd = self.line.strip()
            self.active = False
            self.line   = ''
            self._reset_tab()
            return cmd
        if key.name == 'KEY_BACKSPACE' or str(key) == '\x7f':
            self.line = self.line[:-1]
        else:
            self.line = _cmd_append(self.line, key)
        self._reset_tab()
        return None


def _clip_to_text(clip) -> str:
    """Flatten a register clip into plain text for INSERT-mode <C-r> paste.

    Charwise/linewise clips store per-row char_runs at relative `dcol` offsets;
    gaps become spaces. Rows join with newline (the insert handler inserts the
    first row only, the common single-line case)."""
    if not clip or not clip.get('rows'):
        return ''
    lines = []
    for row in clip['rows']:
        cells = [' '] * row.get('width', 0)
        for rd in row.get('char_runs', ()):
            for i, sym in enumerate(rd['symbols']):
                pos = rd['dcol'] + i
                if pos >= len(cells):
                    cells.extend([' '] * (pos - len(cells) + 1))
                if pos >= 0:
                    cells[pos] = sym
        lines.append(''.join(cells))
    return '\n'.join(lines)


# Explosion damage in half-hearts by Manhattan distance from centre
_EXPL_DAMAGE = {0: 3, 1: 3, 2: 2, 3: 1}   # 0-1: 1.5♥  2: 1♥  3: 0.5♥

_ALERT_RADIUS           = 5   # Manhattan dist at which goblins start chasing


def _sight_radius(ent) -> int:
    """How far a chaser can see the player. Egg creatures see farther: a demon
    (:s/g/&/) is relentless — it hunts from anywhere; a swelled Goblin
    (:s/g/G/ or ~) has doubled sight."""
    if getattr(ent, 'tag', '') == 'demon':
        return 10 ** 9
    if getattr(ent, 'swole', False):
        return _ALERT_RADIUS * 2
    return _ALERT_RADIUS
_ATTACK_RADIUS          = 1   # Manhattan dist at which goblins attack each turn
_WARDEN_SUMMON_INTERVAL = 6   # turns between warden summons
_MSG_ROTATE_TTL         = 20  # ticks per combat message (~2 s) — multi-message (1/3…) cycles at this pace
_INTRO_ROTATE_TTL       = 60  # ticks per intro part (~6 s) — prose needs longer on the bar than a combat line


def _wrap_message(text: str, width: int) -> list[str]:
    """Word-wrap a banner into parts that each fit the message bar.

    The pool's own `(x/n)` prefix has to fit alongside the text, and how wide
    that prefix is depends on how many parts there are — so grow the reservation
    until the part count stops changing. Returns a single part when it already
    fits, so short banners never gain a counter.
    """
    words = text.split()
    if not words:
        return []
    reserve = 0
    while True:
        avail = max(16, width - reserve)
        parts, cur = [], ''
        for w in words:
            if cur and len(cur) + 1 + len(w) > avail:
                parts.append(cur)
                cur = w
            else:
                cur = f'{cur} {w}' if cur else w
        if cur:
            parts.append(cur)
        need = len(f'({len(parts)}/{len(parts)}) ') if len(parts) > 1 else 0
        if need <= reserve:
            return parts
        reserve = need

_SCROLL_TEXT_OPERATOR_CODEX = """\
The Operator's Codex
====================
In the dark, they carved the grammar of unmaking.

  d{m}  ──  delete to motion
  dd    ──  delete line
  y{m}  ──  yank (copy without cutting)
  yy    ──  yank line
  c{m}  ──  change text (delete + insert)

  "  holds what you cut and what you copy.

  The operator takes a motion.
  The motion sets the range.
  The register is the vessel.
"""

_SCROLL_TEXT_INSCRIBERS_HAND = """\
The Inscriber's Hand
====================
You cut, copied, repeated. Now the hand learns to write.

  i     ──  insert — write before the cursor
  a     ──  append — write after it
  c{m}  ──  change text (delete + insert)
  o/O   ──  open a fresh line, below or above
  R     ──  Replace mode — overtype as you go

  Esc seals the ink.
"""

_SCROLL_TEXT_WHOLE_WORD = """\
The Whole Word
==============
Position within the word ceased to matter.

  v   ──  select by sight, then strike
  V   ──  whole lines in a single gaze
  iw  ──  inner word  (from anywhere inside)
  aw  ──  around word (includes adjacent space)
  i(  ──  inner parens
  a(  ──  around parens
  i"  ──  inside quotes
  it  ──  inside tag

  diw works at start, middle, or end.
  The boundary is the rune, not where you stand.
"""

_SCROLL_TEXT_REWRITING_WORD = """\
The Rewriting Word
==================
Every word taken clean. Now take them all at once.

  :s     ──  change a word where it stands
  :%s    ──  every line, every hit at once
  :g     ──  strike each line that matches
  &      ──  do the same once more, unbidden

  q@     ──  record once, replay a hundredfold
  "a     ──  a register called by its name

  One breath, and the whole page turns true.
  The hand need not repeat itself.
"""

def _chest_loot(kind: str) -> str:
    """Return the item type yielded by looting a chest.

    `chest_random` rolls 50% key / 30% scroll / 20% heart. Those odds are quoted
    verbatim in the `:entity` palette, so keep the two together."""
    if kind == 'chest_key':
        return 'key'
    if kind == 'chest_scroll':
        return 'scroll'
    r = random.random()
    if r < 0.5:
        return 'key'
    if r < 0.8:
        return 'scroll'
    return 'heart'

# ── Scroll overlays ───────────────────────────────────────────────────────────

def _known_from_progress(progress: dict) -> set:
    """Commands the player has learned across all completed levels.

    A scroll's smudged lines clarify once the command they preview appears
    here. A level counts as completed once it has been beaten with ≥1 star
    (which is also what unlocks the levels that follow it), so this is the
    cumulative set of commands the player has actually been taught.
    """
    known: set = {'h', 'j', 'k', 'l'}
    for slug, rec in progress.items():
        # Level records are slug-keyed dicts with complete/stars; the non-level
        # fields (extras, flags, max_hp, …) fail this check and are skipped.
        if isinstance(rec, dict) and (rec.get('complete') or rec.get('stars', 0) >= 1):
            known.update(_known_commands(slug))
    return known


def _record_blessing_seen(progress: dict, player_name: str, name: str) -> None:
    """Bind a just-recited blessing into progress['blessings_seen'] so it appears
    in the scroll library's blessings/ subtree and the Codex blessings fold."""
    from vimny.content.blessings import blessing_id_for_name
    bid = blessing_id_for_name(name)
    if not bid:
        return
    seen = list(progress.get('blessings_seen', []))
    if bid not in seen:
        seen.append(bid)
        progress['blessings_seen'] = seen
        SM.save_progress(progress, player_name)


def _smudge_gate_met(gate, known) -> bool:
    """True if every command token in `gate` is in the player's known set."""
    if gate is None:
        return False
    tokens = (gate,) if isinstance(gate, str) else tuple(gate)
    return all(t in known for t in tokens)


_STAIN_BLEED = 4    # how far the wet edge creeps past the solid stain


def _water_stain(text: str, solid: int):
    """Mask `text` as ink run from a water-damaged left edge — the scroll was
    DIPPED from the left, so the stain is one solid block over the first
    `solid` characters (left margin + the hidden command), then a SHORT wet
    edge of at most _STAIN_BLEED speckled characters, and the rest of the
    line reads clean. (An earlier fade speckled the WHOLE tail with decaying
    probability, eating random letters deep into the clear text — the clear
    tail is the meaningful hint and must actually read.) Darker shades (▓▒)
    at the wet edge, lighter (░) at its far side; spaces are never smudged
    (the stain runs through ink, not gaps). Returns (chars, smudged) parallel
    lists; deterministic per `text`.
    """
    rnd  = random.Random(text)          # stable pattern for a given line
    chars, smudged = [], []
    for i, ch in enumerate(text):
        if i < solid:                   # the dip: margin + command, always hidden
            chars.append(rnd.choice('▒▓'))
            smudged.append(True)
            continue
        d = i - solid
        p = (1 - d / _STAIN_BLEED) if d < _STAIN_BLEED else 0.0
        if ch != ' ' and rnd.random() < p:
            r = rnd.random()
            chars.append('▓' if r < p * 0.5 else ('▒' if r < p * 0.85 else '░'))
            smudged.append(True)
        else:
            chars.append(ch)
            smudged.append(False)
    return chars, smudged


def _show_reliquary_scroll(term: Terminal, iw: int, game_h: int,
                           known: set | None = None) -> None:
    """Amber floating box explaining the \" register. d and c rows are smudged."""
    C_ = RELIQUARY_SCROLL
    BOX_IW = 54
    BOX_BW = BOX_IW + 4

    box_bg  = term.on_color_rgb(10, 8, 2)
    amber_b = term.color_rgb(220, 175, 35) + term.bold
    amber   = term.color_rgb(220, 175, 35)
    body    = term.color_rgb(185, 150, 55)
    smudge  = term.color_rgb(120, 92, 38)   # murky ink — visible as a stain, dimmer than body
    hi      = term.color_rgb(255, 220, 60) + term.bold
    rst     = term.normal

    col_off = max(1, (iw + 2 - BOX_BW) // 2)

    bdr = box_bg + amber_b
    inn = box_bg

    def row(vis: int, colored: str) -> str:
        return (bdr + '║ ' + rst +
                inn + colored +
                inn + ' ' * max(0, BOX_IW - vis) +
                bdr + ' ║' + rst)

    blank = row(0, '')

    T  = _popup_fit(C_['title'], BOX_IW)     # never wider than its own box
    lT = (BOX_IW - len(T)) // 2
    rT = BOX_IW - len(T) - lT
    title = row(BOX_IW, ' ' * lT + hi + T + inn + ' ' * rT)

    # The description column is DERIVED from the box, not a second magic number
    # that would not follow it: the row is `    {key}{sep}{desc}{suf}"`, so what
    # is left for the description is whatever the fixed parts do not take. A
    # description too long for it is elided rather than sliced — the same rule
    # the forge pickers follow.
    _SEP, _SUF = '  ────>  ', 'lands in  '
    _KEYW = max((len(r[0]) for r in C_['kv_rows']), default=1)
    _DESCW = BOX_IW - (4 + _KEYW + len(_SEP) + len(_SUF) + 1)

    def _desc_cell(desc: str) -> str:
        return _popup_fit(desc, _DESCW).ljust(_DESCW)

    def kv_clear(key: str, desc: str) -> str:
        d25     = _desc_cell(desc)
        sep     = _SEP
        suf     = _SUF
        sym     = '"'
        colored = ('    ' + hi + key + rst +
                   inn + body + sep + d25 + suf + rst +
                   inn + amber + sym + rst + inn)
        return row(4 + len(key) + len(sep) + len(d25) + len(suf) + 1, colored)

    def kv_smudged(key: str, desc: str) -> str:
        sep    = _SEP
        suf    = _SUF
        d25    = _desc_cell(desc)
        text   = '    ' + key + sep + d25            # command stays under the wet edge
        solid  = 4 + len(key) + len(sep)
        chars, smudged = _water_stain(text, solid)   # same ink-run fade as the lines-based scrolls
        painted, prev = '', None
        for ch, is_s in zip(chars, smudged):
            col = smudge if is_s else body
            if col != prev:
                painted += col
                prev = col
            painted += ch
        colored = painted + rst + inn + body + suf + rst + inn + amber + '"' + rst + inn
        return row(4 + len(key) + len(sep) + len(d25) + len(suf) + 1, colored)

    p_text  = C_['p_text']
    p_plain = ' "' + p_text
    p_col   = (body + ' ' + rst +
               inn + amber + '"' + rst +
               inn + body + p_text + rst + inn)
    p_row   = row(len(p_plain), p_col)

    AK  = '[ any key ]'
    lAK = (BOX_IW - len(AK)) // 2
    footer = row(BOX_IW, ' ' * lAK + body + AK + inn + ' ' * (BOX_IW - len(AK) - lAK))

    known = known or set()
    kv_lines = []
    for key, desc, gate in C_['kv_rows']:
        if gate is None or _smudge_gate_met(gate, known):
            kv_lines.append(kv_clear(key, desc))
        else:
            kv_lines.append(kv_smudged(key, desc))

    sep_h = '═' * (BOX_IW + 2)
    lines = [
        bdr + '╔' + sep_h + '╗' + rst,
        blank,
        title,
        blank,
        row(len(C_['intro']), body + C_['intro'] + rst),
        blank,
        *kv_lines,
        blank,
        p_row,
        blank,
        row(len(C_['outro']), body + C_['outro'] + rst),
        blank,
        footer,
        blank,
        bdr + '╚' + sep_h + '╝' + rst,
    ]

    # Center on the actual box height so the box tracks any added/removed lines.
    row_off = 3 + max(0, (game_h - len(lines)) // 2)
    for i, line in enumerate(lines):
        print(term.move_yx(row_off + i, col_off) + line, end='', flush=True)

    term.inkey()


def _prompt_horse_name(term: Terminal, iw: int, game_h: int) -> str:
    """A centred amber popup the first time the horse reaches your side: type a
    name and press Enter, or Esc to leave him nameless. Returns the entered name
    (stripped) or '' if skipped/blank."""
    BOX_IW = 54; BOX_BW = BOX_IW + 4
    box_bg  = term.on_color_rgb(10, 8, 2)
    amber_b = term.color_rgb(220, 175, 35) + term.bold
    amber   = term.color_rgb(220, 175, 35)
    body    = term.color_rgb(185, 150, 55)
    hi      = term.color_rgb(255, 220, 60) + term.bold
    rst     = term.normal
    col_off = max(1, (iw + 2 - BOX_BW) // 2)
    bdr = box_bg + amber_b; inn = box_bg

    def row(vis, colored):
        return (bdr + '║ ' + rst + inn + colored +
                inn + ' ' * max(0, BOX_IW - vis) + bdr + ' ║' + rst)

    blank = row(0, '')

    def centred(text, col):
        l = (BOX_IW - len(text)) // 2; r = BOX_IW - len(text) - l
        return row(BOX_IW, ' ' * l + col + text + inn + ' ' * r)

    sep_h = '═' * (BOX_IW + 2)
    _PROMPT = [
        "The wizard's old horse noses your open hand,",
        "patient as the road behind you.",
        '',
        'What name will you give him?',
    ]

    name_buf = ''
    while True:
        field = (name_buf + '_')[:BOX_IW - 4]
        lF = (BOX_IW - len(field)) // 2; rF = BOX_IW - len(field) - lF
        input_row = row(BOX_IW, ' ' * lF + hi + field + inn + ' ' * rF)
        foot = '[ Enter ] name him   ·   [ Esc ] not yet'
        footer = centred(foot, body)
        lines = [
            bdr + '╔' + sep_h + '╗' + rst, blank,
            *[centred(t, amber) if t else blank for t in _PROMPT],
            blank, input_row, blank, footer, blank,
            bdr + '╚' + sep_h + '╝' + rst,
        ]
        row_off = 3 + max(0, (game_h - len(lines)) // 2)
        for i, line in enumerate(lines):
            print(term.move_yx(row_off + i, col_off) + line, end='', flush=True)

        key = term.inkey()
        raw = str(key) if not key.is_sequence else ''
        if key.name == 'KEY_ESCAPE':
            return ''
        if key.name == 'KEY_ENTER' or raw in ('\n', '\r'):
            return name_buf.strip()
        if key.name == 'KEY_BACKSPACE' or raw == '\x7f':
            name_buf = name_buf[:-1]
        elif raw and raw.isprintable() and len(name_buf) < _NAME_MAX:
            name_buf += raw


#: The forge's entity palette: kind → (preset, what it is, the fields worth setting).
#:
#: One table, three consumers — the picker draws it, `:entity` validates against
#: it, and `:entity` with no argument prints it. Before this, the presets lived
#: inside the command handler and the list of kinds was a `'|'.join` in an error
#: message, so the only way to learn what could be placed was to place something
#: wrong. The `notes` column is the part an author actually needs: `locked_door`
#: and `floor_key` are useless facts until you know they pair on `tag`.
_ENTITY_PALETTE = {
    'goblin':          (dict(hp=1, alive=True, max_hp=1, ai='chase', ai_speed=1),
                        'chases you; x to fight',
                        ('hp', 'ai_speed', 'tag', 'drops', 'group')),
    'wanderer':        (dict(hp=1, alive=True, max_hp=1, ai='chase', ai_speed=2),
                        'chases at half speed; never strikes',
                        ('hp', 'ai_speed', 'drops', 'group')),
    'warden':          (dict(hp=5, alive=True, max_hp=5, ai='', ai_speed=1),
                        'stationary boss, 5 hp',
                        ('hp', 'edit_immune', 'drops', 'group')),
    'floor_key':       (dict(hp=1, alive=True),
                        'x picks it up into "; p/P it onto a locked_door',
                        ('tag',)),
    'locked_door':     (dict(hp=1, alive=True),
                        'BLOCKS; stand beside it and p (east) / P (west) a '
                        'floor_key of the same tag',
                        ('tag', 'opaque', 'edit_immune')),
    'fancy_door':      (dict(hp=1, alive=True),
                        'BLOCKS; stand beside it and p (east) / P (west) a '
                        'register whose TEXT reads its password — the key is '
                        'words you cut off the floor. Spaces as _ '
                        '(password=speak_friend_and_enter)',
                        ('password', 'opaque', 'edit_immune')),
    'door':            (dict(hp=1, alive=True),
                        'does NOT block — stand on it and x; opaque=1 to darken '
                        'what is beyond', ('opaque',)),
    'chest_random':    (dict(hp=1, alive=True),
                        'x to open; random loot — 50% key, 30% scroll, 20% heart',
                        ()),
    'chest_key':       (dict(hp=1, alive=True),
                        'a chest holding a key of the same tag', ('tag',)),
    'chest_scroll':    (dict(hp=1, alive=True), 'a chest holding a scroll',
                        ('scroll_id',)),
    'heart_container': (dict(hp=1, alive=True),
                        'restores hp and increases max health', ()),
    'gold':            (dict(hp=1, alive=True), 'a coin', ()),
    'dynamite':        (dict(hp=1, alive=True), 'blows up', ()),
    'brazier':         (dict(hp=1, alive=True, max_hp=0, ai=''),
                        'a standing flame; lit=0 for cold embers a pasted 🜂 '
                        'lights. A mode="braziers" seal opens its bolt once every '
                        'brazier in its region burns', ('lit',)),
    'exit':            (dict(hp=1, alive=True), 'the way out (:exit moves it)', ()),
}

#: Fields `:entity` will set. A curated subset of `_ENTITY_FIELDS`: `kind`, `row`
#: and `col` are what the command and the cursor already say, and the rest
#: (`ai_tick`, `move_dir`, `shade`, `summoner_uid`) are running state no author
#: has a reason to hand-set — offering them would only invite a level whose
#: creatures start mid-stride.
_ENTITY_SETTABLE = ('hp', 'max_hp', 'ai', 'ai_speed', 'tag', 'scroll_id',
                    'swole', 'edit_immune', 'drops', 'group', 'opaque', 'lit',
                    'password')
_ENTITY_INT_FIELDS  = ('hp', 'max_hp', 'ai_speed')
_ENTITY_BOOL_FIELDS = ('swole', 'edit_immune', 'opaque', 'lit')

#: The COLOURS the renderer actually paints on a key or a lock. Tag pairing is
#: pure string equality, so `tag=orange` pairs perfectly well — it just draws in
#: the default brass, because there is no orange in `vimny/render/colors.py`. That gap
#: is invisible from inside the game (you get a key; it is simply the wrong
#: colour), which is exactly why the picker names the three it knows.
_KEY_COLOURS = ('gold', 'red', 'blue')

#: `(kind, field)` → the values the game recognises, for the picker to offer.
#: A `('…', '(type your own)')` row is present wherever the field is genuinely
#: open-ended, so the list narrows the choice without pretending to close it.
#: Keyed by kind first, then by field alone, because `tag` means a colour on a
#: key and a creature variant on a goblin.
_ENTITY_CHOICES = {
    ('floor_key',   'tag'): ('',) + _KEY_COLOURS,
    ('locked_door', 'tag'): ('',) + _KEY_COLOURS,
    ('chest_key',   'tag'): ('',) + _KEY_COLOURS,
    ('goblin',      'tag'): ('', 'echo', 'zombie', 'demon'),
    'opaque':    ('0', '1'),
    'lit':       ('1', '0'),
    'ai':        ('chase', ''),
    'drops':     ('',) + tuple(f'floor_key:{c}' for c in _KEY_COLOURS)
                 + ('floor_key',) + tuple(f'chest_key:{c}' for c in _KEY_COLOURS)
                 + ('chest_key', 'chest_random', 'chest_scroll',
                    'heart_container', 'gold', 'dynamite'),
    # 'scroll_id' and 'password' are filled on demand — see _entity_choices.
}

#: What each offered value means, where the value alone does not say. Only the
#: rows a reader would otherwise have to guess at.
_CHOICE_NOTES = {
    ('tag', ''):          'untagged — a door with no tag takes ANY key',
    ('ai', ''):           'stationary',
    ('ai', 'chase'):      'walks toward the player',
    ('drops', ''):        'nothing',
    ('scroll_id', ''):    'unassigned — draws from the relic pool',
    ('tag', 'echo'):      'a false Warden: looks like a W',
    ('tag', 'zombie'):    'risen dead',
    ('tag', 'demon'):     'relentless — hunts from anywhere',
    ('opaque', '1'):      'the eye stops here: everything beyond starts fogged',
    ('opaque', '0'):      'a grille — you see straight through it',
    ('lit', '1'):         'burning — the 🜂 flame',
    ('lit', '0'):         'cold embers, waiting for a pasted flame',
}


def _entity_choices(kind: str, field: str, custom=()):
    """The offered values for a field, or () when it is free-form (a number, a
    group id, a name only the author knows).

    `scroll_id` is read from the catalogue rather than listed, so a scroll added
    tomorrow is offered tomorrow — a hand-copied list would drift, and an id
    that does not match one silently shows no scroll at all.

    `custom` is the level's OWN word pool — its `:vocab` block, the same words
    `:fill custom` lays on the floor. A door's password and the words in the
    room it stands in are the same fiction, and an author who has already told
    the level what its words are should not have to type one of them again by
    hand at the one place it matters most."""
    if field == 'scroll_id':
        from vimny.content.scrolls import SCROLL_CATALOG
        return ('',) + tuple(s['id'] for s in SCROLL_CATALOG)
    if field == 'password':
        # The author's OWN words first, then the shipped pools. First because a
        # level that has declared a vocabulary has declared what it is about,
        # and its door should want one of ITS words — the shipped pools are the
        # fallback for a level that never said. Phrases are offered with
        # underscores because the picker hands its answer back as `:entity`
        # text, which splits on whitespace — the same substitution an author
        # would have to type, offered rather than explained. The free-text row
        # below the list stays, because neither pool has to be the answer.
        from vimny.content.passwords import POOLS
        shipped = tuple(w for _name, words, _note in POOLS for w in words)
        mine    = tuple(w for w in custom if w and w not in shipped)
        return tuple(w.replace(' ', '_') for w in mine + shipped)
    return _ENTITY_CHOICES.get((kind, field), _ENTITY_CHOICES.get(field, ()))


def _choice_note(field: str, value: str, custom=()) -> str:
    """The note beside one offered value.

    `password` is noted by POOL rather than by word: what an author needs to
    know is not what `p1g.sn0ut` is a reference to but that its punctuation is
    what makes it a `dW` lesson and not a `dw` one. The pool IS the note. A word
    from the level's own `:vocab` is named as such, so the two sources never
    read as one undifferentiated list."""
    fixed = _CHOICE_NOTES.get((field, value), '')
    if fixed or field != 'password':
        return fixed
    from vimny.content.passwords import POOLS
    plain = value.replace('_', ' ')
    for name, words, note in POOLS:
        if plain in words:
            return f'{name} — {note}'
    if plain in tuple(custom):
        return ":vocab — this level's own word"
    return ''


def _entity_field(ent, field: str, raw: str) -> str:
    """Set one `:entity` field from its typed text. Returns '' or the complaint.

    Typed rather than assigned blind: `hp=lots` would otherwise store the string
    'lots' on a dataclass that never type-checks it, and the level would build,
    export, publish, and only fall over when something tried to subtract from it.
    """
    if field in _ENTITY_INT_FIELDS:
        if not raw.lstrip('-').isdigit():
            return f'{field} wants a number, got {raw!r}'
        setattr(ent, field, int(raw))
    elif field in _ENTITY_BOOL_FIELDS:
        if raw.lower() not in ('true', 'false', '1', '0', 'yes', 'no'):
            return f'{field} wants true or false, got {raw!r}'
        setattr(ent, field, raw.lower() in ('true', '1', 'yes'))
    elif field == 'password':
        # `:entity` splits its arguments on whitespace, so a phrase password
        # ('speak friend and enter' — the shape a line motion produces) could
        # not be typed at all. Underscores stand in for the spaces. The door
        # itself never sees an underscore: it is stored, shown and compared as
        # the phrase, so what an author types and what a player must cut stay
        # the same words.
        if not raw:
            return 'password wants the words that open the door'
        ent.password = raw.replace('_', ' ')
    elif field == 'drops':
        if raw and canonical_kind(raw.partition(':')[0]) not in DROPPABLE:
            return (f'nothing drops {raw!r} — try '
                    + ', '.join(sorted(DROPPABLE)))
        ent.drops = raw
    else:
        setattr(ent, field, raw)
    return ''


#: Cells an entity may stand on. Walls, wood and water are skipped by a ranged
#: `:entity` rather than refused, so a selection swept across a room places into
#: the room and not into its masonry — the author drew the region they could
#: see, and the parts of it that are stone were never the point.
_ENTITY_CELLS = (CellType.FLOOR, CellType.CORRIDOR)


def _entity_cells(room, player) -> list:
    """The cells of the last VISUAL selection an entity could occupy."""
    return [(r, c) for r, c in _range_cells(room, player)
            if room.cells[r][c] in _ENTITY_CELLS]


def _bolt_cells(room, player) -> list:
    """The MASONRY of the last VISUAL selection — what a ranged `:bolt` turns
    into one door.

    Walls only, where `:entity` takes the standable cells: each command takes
    the half of the selection it can mean anything about. A seal writes its
    `opens` cells out as stone and the tick swings them, so bolting a floor cell
    would quietly wall off a square the author was standing on, and sweeping a
    selection across a doorway would do it several times over. The author drew
    the wall; the wall is what crumbles."""
    return [(r, c) for r, c in _range_cells(room, player)
            if room.cells[r][c] in (CellType.WALL, CellType.WOOD_WALL)]


def _range_cells(room, player) -> list:
    """Every in-bounds cell of the last VISUAL selection, in reading order —
    exactly the shape the renderer highlights (`in_selection`), because every
    command that spells its range `'<,'>` must mean the same cells the author
    can see selected. LINEWISE (V) is whole rows; BLOCK (Ctrl-v) is the
    rectangle between the ends; charwise (v) is the flowing span — top row from
    the anchor column, whole middle rows, bottom row up to the cursor — NOT the
    rectangle, which is what block already means."""
    a, b = player.last_visual_anchor, player.last_visual_cursor
    if a is None or b is None:
        return []
    mode = player.last_visual_mode
    return [(r, c)
            for r in range(max(0, min(a[0], b[0])), min(room.rows - 1, max(a[0], b[0])) + 1)
            for c in range(room.cols)
            if in_selection(a, b, mode, r, c)]


def _paint_name(room, r: int, c: int) -> str:
    """What `:paint` would call the cell at (r, c)."""
    ct = room.cells[r][c]
    if (r, c) in getattr(room, 'underwater_cells', ()):
        return 'underwater'          # the smart kind keeps any terrain
    if (r, c) in getattr(room, 'veiled_cells', ()):
        return 'veil'                # a carving not legible yet
    for name, (kind_ct, layer, _) in PAINT_KINDS.items():
        if kind_ct is not None and kind_ct == ct and layer is None:
            return name
    return ct.name.lower()


def _paint_complaint(kind: str) -> str:
    """What `:paint <something it cannot lay>` should say.

    A door is a THING STANDING ON a cell, not a kind of ground, so it is placed
    with `:entity`. Worth answering by name rather than listing the terrains,
    because "Unknown paint: door" beside a palette with no door in it reads as
    "this game has no doors" — and the author's next question, whether a door
    stops anyone, has a terrain answer (`wood`) that they will never find from
    an error message about what `paint` is not.
    """
    if kind in _ENTITY_PALETTE:
        return (f'{kind} is a thing, not ground — :entity {kind}'
                + ('   (a barrier you break through instead: :paint wood)'
                   if kind in ('door', 'locked_door') else ''))
    return f'Unknown paint: {kind}  ({"|".join(PAINT_KINDS)})'


def _warn_display(w: str) -> str:
    """A validator warning as the author should READ it on the bar.

    The stored form carries a `[rule]` tag for the tests and the log; on the
    banner it is noise in front of the one sentence that matters, so strip it
    and lead with a plain 'Warning:'."""
    return 'Warning: ' + re.sub(r'^\[[^\]]*\]\s*', '', w)


def _paint_cells(room, cells: list, kind: str) -> str:
    """Paint every cell, and report what actually landed.

    A fill owns its own region and refuses the brush, so a selection swept over
    one paints around it — and the count SAYS so, because "12 cells painted" over
    a 20-cell selection is the only sign the author gets that eight of them
    belong to a directive."""
    done = sum(1 for r, c in cells if _ed_paint(room, r, c, kind))
    room.rebuild_indexes()
    if not done:
        return ('A fill grows those cells — :fill! to make them yours.'
                if cells else 'Nothing selected.')
    skipped = len(cells) - done
    return (f'Painted {done} cell{"" if done == 1 else "s"} {kind}.'
            + (f'  {skipped} owned by a fill.' if skipped else ''))


def _describe_entity(ent) -> str:
    """`:entity?` — the creature under the cursor, and only what is true of it.

    Every non-default field, none of the defaults. A dump of all fifteen would
    bury `tag=gold` in a wall of `move_dir=1`, and the one thing an author opens
    this for is to check the field they just set actually took."""
    bits = [f'{f}={getattr(ent, f)}' for f in _ENTITY_SETTABLE
            if getattr(ent, f) not in ('', 0, False, 1)]
    return f'{ent.kind}' + (f'  {" ".join(bits)}' if bits else '  (defaults)')


#: ONE inner width for every forge picker (`:entity`, `:paint`, `:fill`, `:rune`,
#: `:teaches`, `:requires` — each of which opens its menu when typed bare).
#: They were 62 and their contents are prose, so the longest palette note ran to
#: 152 columns and was sliced mid-word: an author reading "…stand beside it and p
#: (east) / P (" had been told less than nothing.
#:
#: 74 is the widest that still fits the narrowest terminal the game supports.
#: `render.utils.inner_w` floors at 78 (an 80-column screen less its two frame
#: borders) and a box is `BOX_IW + 4` wide including its own, so 74 gives 78 —
#: exactly the playfield, sitting between the frame rather than on top of it.
#: Widening is only half the answer; `_popup_fit` / `_popup_wrap` are the other
#: half, because prose will outgrow any width you pick.
POPUP_IW = 74


def _popup_fit(text: str, width: int) -> str:
    """`text` for one row, cut at a WORD boundary with an ellipsis if it must be.

    A hard slice at the box edge is what produced "…and p (east) / P (". Cutting
    at a space and saying so with `…` at least tells the reader that there is
    more, and the full line is under their cursor in the detail pane."""
    if len(text) <= width:
        return text
    cut = text[:max(0, width - 2)]
    if ' ' in cut[1:]:
        cut = cut[:cut.rindex(' ')]
    return cut.rstrip(' ,;:') + ' …'


def _popup_wrap(text: str, width: int, limit: int = 3) -> list:
    """`text` wrapped to `width`, at most `limit` lines (the last one elided).

    Used for the detail pane under a picker's list, which is where the prose the
    row could not hold actually gets read."""
    words, lines, cur = str(text).split(), [], ''
    for w in words:
        if cur and len(cur) + 1 + len(w) > width:
            lines.append(cur)
            cur = w
            if len(lines) == limit:
                break
        else:
            cur = f'{cur} {w}'.strip()
    if len(lines) < limit and cur:
        lines.append(cur)
    if len(lines) == limit and words:
        used = sum(len(l.split()) for l in lines)
        if used < len(words):
            lines[-1] = _popup_fit(lines[-1] + ' …', width)
    return lines


def _pick_entity(term: Terminal, iw: int, game_h: int, custom=()) -> str:
    """The palette, as two panes you walk with j/k. Returns the ARGUMENT TAIL of
    the `:entity` command it built — `'goblin tag=red drops=floor_key:red'` — or
    '' if the author backed out.

    It returns the command rather than performing the placement because that is
    the whole defence for having a menu in a Vim-teaching game: the command is
    the mechanism and the menu is one view of it. `:entity goblin tag=red` is
    always available, always typeable, and recordable in a tape; this only
    answers "what can I place, and what can I set on it?" — and it answers by
    composing the very line the author could have typed, which the caller then
    echoes back so the menu teaches its way out of being needed.

    Pane one is the kinds. Pane two is that kind's notable fields, because a
    picker that could only place the DEFAULT goblin cannot make a red key, and a
    red key is the first thing anyone wants from it.
    """
    BOX_IW = POPUP_IW; BOX_BW = BOX_IW + 4
    box_bg  = term.on_color_rgb(6, 8, 12)
    edge    = box_bg + term.color_rgb(120, 170, 210) + term.bold
    head    = term.color_rgb(190, 215, 240) + term.bold
    body    = term.color_rgb(130, 150, 170)
    dim     = term.color_rgb(105, 120, 140)
    pick    = term.color_rgb(255, 220, 60) + term.bold
    rst     = term.normal
    col_off = max(1, (iw + 2 - BOX_BW) // 2)
    kinds   = list(_ENTITY_PALETTE)

    def row(vis, colored):
        return (edge + '║ ' + rst + box_bg + colored +
                box_bg + ' ' * max(0, BOX_IW - vis) + edge + ' ║' + rst)

    sep_h = '═' * (BOX_IW + 2)

    def show(title, rows, sel, foot, detail=''):
        # A long list (28 scrolls) is WINDOWED, not drawn whole: the box is
        # centred in the game area, so overflowing it would push its own top
        # border off the screen and leave the author steering a list they
        # cannot see the selected row of.
        # Only when the row actually had to be cut — an author reading a line
        # that fits does not need it repeated underneath.
        clipped = sel < len(rows) and len(rows[sel]) > BOX_IW
        detail_lines = _popup_wrap(detail, BOX_IW - 3) if detail and clipped else []
        win   = max(3, game_h - 9 - (len(detail_lines) + 1 if detail_lines else 0))
        first = 0 if len(rows) <= win else min(max(0, sel - win // 2),
                                               len(rows) - win)
        lines = [edge + '╔' + sep_h + '╗' + rst, row(0, '')]
        # The title is FITTED like any other row. Unfitted it was the one string
        # in the box that could not clip — it would have pushed the right border
        # out instead, which reads as the box being broken rather than the text
        # being long.
        _t = _popup_fit(title, BOX_IW - 1)
        lines.append(row(BOX_IW, head + ' ' + _t
                         + box_bg + ' ' * max(0, BOX_IW - len(_t) - 1)))
        lines.append(row(0, ''))
        for i in range(first, min(len(rows), first + win)):
            text = _popup_fit(rows[i], BOX_IW)
            lines.append(row(len(text), (pick if i == sel else body) + text))
        if len(rows) > win:
            more = f' … {sel + 1}/{len(rows)}'
            lines.append(row(len(more), body + more))
        # The DETAIL PANE — the selected row's prose in full, wrapped. The rows
        # are one line each so the list stays walkable; this is where the part
        # that did not fit on the row is actually read, which is what makes the
        # word-boundary cut above honest rather than a nicer-looking lie.
        if detail_lines:
            lines.append(row(0, ''))
            for d in detail_lines:
                lines.append(row(len(d) + 2, dim + '  ' + d))
        lines.append(row(0, ''))
        lines.append(row(len(foot), body + foot))
        lines.append(row(0, ''))
        lines.append(edge + '╚' + sep_h + '╝' + rst)
        row_off = 3 + max(0, (game_h - len(lines)) // 2)
        for i, line in enumerate(lines):
            print(term.move_yx(row_off + i, col_off) + line, end='', flush=True)

    def read_value(current):
        """Type a field's value. Enter commits, Esc keeps what was there."""
        buf = current
        while True:
            show('type a value, ⏎ to keep it', [f' > {buf}▏'], 0,
                 ' ⏎ accept   Esc leave it unchanged')
            key = term.inkey()
            raw = str(key) if not key.is_sequence else ''
            if key.name == 'KEY_ESCAPE':
                return current
            if key.name == 'KEY_ENTER' or raw in ('\n', '\r'):
                return buf
            if key.name == 'KEY_BACKSPACE' or raw in ('\x7f', '\b'):
                buf = buf[:-1]
            elif raw and raw.isprintable():
                buf += raw

    def pick_value(kind, field, current):
        """Choose a field's value from what the game actually recognises.

        This is the difference between a menu and a form. `tag=orange` pairs a
        key to a door perfectly well — pairing is string equality — but the
        renderer knows three colours, so an orange key comes out brass and
        nothing anywhere says why. A list of the values that DO something turns
        that silent gap into a visible one. The last row still opens the free
        text field, because the narrow set is what the game paints, not what it
        permits, and an author pairing on `tag=vault_b` is doing nothing wrong.
        """
        choices = _entity_choices(kind, field, custom)
        if not choices:
            return read_value(current)
        sel = choices.index(current) if current in choices else 0
        while True:
            rows, notes = [], []
            for v in choices:
                note = _choice_note(field, v, custom)
                notes.append(note)
                rows.append(f' {(v or "(none)"):<20}{note}')
            rows.append(' » type something else')
            notes.append('')
            show(f'{kind}.{field}', rows, sel,
                 ' j/k move   ⏎ choose   Esc leave it unchanged',
                 detail=notes[sel] if sel < len(notes) else '')
            key = term.inkey()
            raw = str(key) if not key.is_sequence else ''
            if key.name == 'KEY_ESCAPE':
                return current
            if raw == 'j' or key.name == 'KEY_DOWN':
                sel = (sel + 1) % len(rows)
            elif raw == 'k' or key.name == 'KEY_UP':
                sel = (sel - 1) % len(rows)
            elif key.name == 'KEY_ENTER' or raw in ('\n', '\r'):
                return read_value(current) if sel == len(rows) - 1 else choices[sel]

    sel = 0
    while True:
        rows = [f' {k:<16}{_ENTITY_PALETTE[k][1]}' for k in kinds]
        show('place an entity', rows, sel, ' j/k move   ⏎ choose   Esc cancel',
             detail=_ENTITY_PALETTE[kinds[sel]][1])
        key = term.inkey()
        raw = str(key) if not key.is_sequence else ''
        if key.name == 'KEY_ESCAPE':
            return ''
        if raw == 'j' or key.name == 'KEY_DOWN':
            sel = (sel + 1) % len(kinds)
            continue
        if raw == 'k' or key.name == 'KEY_UP':
            sel = (sel - 1) % len(kinds)
            continue
        if not (key.name == 'KEY_ENTER' or raw in ('\n', '\r')):
            continue

        kind   = kinds[sel]
        fields = list(_ENTITY_PALETTE[kind][2])
        if not fields:
            return kind                       # nothing to tune — place it as-is
        vals   = {f: '' for f in fields}
        fsel   = 0
        while True:
            # The place row is the LAST row, so Enter-Enter straight through the
            # menu still places a plain one: the fields are opt-in, not a gauntlet.
            rows = [f' {f:<14}{vals[f] or "—"}' for f in fields]
            rows.append(f' » place the {kind}')
            show(f'{kind} — set what you need', rows, fsel,
                 ' j/k move   ⏎ edit / place   Esc back')
            key = term.inkey()
            raw = str(key) if not key.is_sequence else ''
            if key.name == 'KEY_ESCAPE':
                break                         # back to the kinds
            if raw == 'j' or key.name == 'KEY_DOWN':
                fsel = (fsel + 1) % len(rows)
            elif raw == 'k' or key.name == 'KEY_UP':
                fsel = (fsel - 1) % len(rows)
            elif key.name == 'KEY_ENTER' or raw in ('\n', '\r'):
                if fsel == len(rows) - 1:
                    return ' '.join([kind] + [f'{f}={vals[f]}'
                                              for f in fields if vals[f]])
                vals[fields[fsel]] = pick_value(kind, fields[fsel],
                                                vals[fields[fsel]])


def _pick_one(term: Terminal, iw: int, game_h: int,
              title: str, options) -> str:
    """A one-pane picker over a fixed list. Returns the chosen VALUE, or '' if
    the author backed out. `options` is [(value, description), ...].

    Every forge command whose argument comes from a list the game already knows
    — `:paint`, `:rune`, `:fill` — opens this when typed bare, because that is
    the shape of the question they are being asked ("which ones are there?") and
    a list is the only honest answer. `:entity` keeps its own two-pane picker: a
    kind has FIELDS, and a menu that could only place the default goblin cannot
    make a red key. The value is returned rather than acted on, so the caller can
    echo back the command it stands for and the menu teaches its way out of
    being needed.
    """
    BOX_IW = POPUP_IW; BOX_BW = BOX_IW + 4
    box_bg  = term.on_color_rgb(6, 8, 12)
    edge    = box_bg + term.color_rgb(120, 170, 210) + term.bold
    head    = term.color_rgb(190, 215, 240) + term.bold
    body    = term.color_rgb(130, 150, 170)
    dim     = term.color_rgb(105, 120, 140)
    pick    = term.color_rgb(255, 220, 60) + term.bold
    rst     = term.normal
    col_off = max(1, (iw + 2 - BOX_BW) // 2)
    values  = [v for v, _ in options]
    sep_h   = '═' * (BOX_IW + 2)
    width   = max([len(v) for v in values] or [1]) + 2

    def row(vis, colored):
        return (edge + '║ ' + rst + box_bg + colored +
                box_bg + ' ' * max(0, BOX_IW - vis) + edge + ' ║' + rst)

    sel = 0
    while True:
        rows  = [f' {v:<{width}}{d}' for v, d in options]
        foot  = ' j/k move   ⏎ choose   Esc cancel'
        lines = [edge + '╔' + sep_h + '╗' + rst, row(0, '')]
        # The title is FITTED like any other row. Unfitted it was the one string
        # in the box that could not clip — it would have pushed the right border
        # out instead, which reads as the box being broken rather than the text
        # being long.
        _t = _popup_fit(title, BOX_IW - 1)
        lines.append(row(BOX_IW, head + ' ' + _t
                         + box_bg + ' ' * max(0, BOX_IW - len(_t) - 1)))
        lines.append(row(0, ''))
        for i, text in enumerate(rows):
            text = _popup_fit(text, BOX_IW)
            lines.append(row(len(text), (pick if i == sel else body) + text))
        if options and len(rows[sel]) > BOX_IW:      # only what had to be cut
            for d in _popup_wrap(options[sel][1], BOX_IW - 3):
                lines.append(row(len(d) + 2, dim + '  ' + d))
        lines.append(row(0, ''))
        lines.append(row(len(foot), body + foot))
        lines.append(row(0, ''))
        lines.append(edge + '╚' + sep_h + '╝' + rst)
        row_off = 3 + max(0, (game_h - len(lines)) // 2)
        for i, line in enumerate(lines):
            print(term.move_yx(row_off + i, col_off) + line, end='', flush=True)

        key = term.inkey()
        raw = str(key) if not key.is_sequence else ''
        if key.name == 'KEY_ESCAPE':
            return ''
        if raw == 'j' or key.name == 'KEY_DOWN':
            sel = (sel + 1) % len(values)
        elif raw == 'k' or key.name == 'KEY_UP':
            sel = (sel - 1) % len(values)
        elif key.name == 'KEY_ENTER' or raw in ('\n', '\r'):
            return values[sel]


def _pick_many(term: Terminal, iw: int, game_h: int,
               title: str, options, chosen) -> list | None:
    """A multi-select over a fixed list. Space toggles, ⏎ accepts, Esc cancels
    (returning None, which is NOT the same as accepting an empty list).

    The single-choice `_pick_one` cannot serve `:teaches` and `:requires`: those
    fields hold a SET, and a picker that closed on the first pick would make the
    two-token level harder to declare than typing it. `options` is
    [(value, description), ...]; `chosen` is what is already set.
    """
    BOX_IW = POPUP_IW; BOX_BW = BOX_IW + 4
    box_bg  = term.on_color_rgb(6, 8, 12)
    edge    = box_bg + term.color_rgb(120, 170, 210) + term.bold
    head    = term.color_rgb(190, 215, 240) + term.bold
    body    = term.color_rgb(130, 150, 170)
    pick    = term.color_rgb(255, 220, 60) + term.bold
    on      = term.color_rgb(120, 210, 140)
    rst     = term.normal
    col_off = max(1, (iw + 2 - BOX_BW) // 2)
    values  = [v for v, _ in options]
    have    = [v for v in chosen if v in values] + [v for v in chosen if v not in values]
    sep_h   = '═' * (BOX_IW + 2)
    width   = max([len(v) for v in values] or [1]) + 2

    def row(vis, colored):
        return (edge + '║ ' + rst + box_bg + colored +
                box_bg + ' ' * max(0, BOX_IW - vis) + edge + ' ║' + rst)

    sel = 0
    while True:
        # WINDOWED: a hundred tokens will not fit on any terminal, and a list
        # that overflows pushes its own border off the screen.
        rows = [f' [{"x" if v in have else " "}] {v:<{width}}{d}'
                for v, d in options]
        win   = max(3, game_h - 10)
        first = 0 if len(rows) <= win else min(max(0, sel - win // 2),
                                               len(rows) - win)
        foot  = ' j/k move   space toggle   ⏎ accept   Esc cancel'
        lines = [edge + '╔' + sep_h + '╗' + rst, row(0, '')]
        # The title is FITTED like any other row. Unfitted it was the one string
        # in the box that could not clip — it would have pushed the right border
        # out instead, which reads as the box being broken rather than the text
        # being long.
        _t = _popup_fit(title, BOX_IW - 1)
        lines.append(row(BOX_IW, head + ' ' + _t
                         + box_bg + ' ' * max(0, BOX_IW - len(_t) - 1)))
        lines.append(row(0, ''))
        for i in range(first, min(len(rows), first + win)):
            text = _popup_fit(rows[i], BOX_IW)
            lines.append(row(len(text),
                             (pick if i == sel else
                              on if values[i] in have else body) + text))
        picked = ' '.join(have) or '(none)'
        lines.append(row(0, ''))
        # WRAPPED, not sliced: this line is the answer to "what have I chosen",
        # and a `:teaches` set of eight tokens overran 61 columns and silently
        # lost its tail — so the author could not see the very thing they were
        # picking. It is the one place in the box that may take more than a row.
        for p in _popup_wrap(picked, BOX_IW - 1, limit=3):
            lines.append(row(len(p) + 1, body + ' ' + p))
        lines.append(row(len(foot), body + foot))
        lines.append(row(0, ''))
        lines.append(edge + '╚' + sep_h + '╝' + rst)
        row_off = 3 + max(0, (game_h - len(lines)) // 2)
        for i, line in enumerate(lines):
            print(term.move_yx(row_off + i, col_off) + line, end='', flush=True)

        key = term.inkey()
        raw = str(key) if not key.is_sequence else ''
        if key.name == 'KEY_ESCAPE':
            return None
        if raw == 'j' or key.name == 'KEY_DOWN':
            sel = (sel + 1) % len(values)
        elif raw == 'k' or key.name == 'KEY_UP':
            sel = (sel - 1) % len(values)
        elif raw == ' ':
            if values[sel] in have:
                have.remove(values[sel])
            else:
                have.append(values[sel])
        elif key.name == 'KEY_ENTER' or raw in ('\n', '\r'):
            return have


#: Every token the curriculum gates on, in the order the game teaches them —
#: which is the order an author wants to read them in, since a level's
#: `requires` is nearly always "everything up to about here". Descriptions come
#: from the same table the hint bar is built from, so the picker cannot drift
#: from what the keys actually do.
def _teachable_tokens() -> list:
    from vimny.render.hint_bar import CMD as _CMD
    out, seen = [], set()
    for _lv in LEVELS:
        for _t in _lv.get('teaches', ()):
            if _t not in seen:
                seen.add(_t)
                _keys, _desc = _CMD.get(_t, (_t, ''))
                out.append((_t, f'{_keys}  {_desc}'.strip() if _keys != _t else _desc))
    return out


#: The rune kinds, as the bare-`:rune` picker lists them. `void` is the only one
#: that carries a rule rather than a colour, so it is the only one whose line has
#: to say anything: landing on it kills, though a line motion passes over it.
_RUNE_NOTES = [
    ('ancient', 'indigo — the default glyph'),
    ('verdant', 'green — living text'),
    ('void',    'violet — LETHAL to land on; jumps pass over it'),
    ('ember',   'amber — the wizard\'s own hand'),
]

#: What each `:fill` pool draws from — the descriptions the bare-`:fill` picker
#: shows. Keyed off `sharing.vocab.POOLS`, which stays the authority on which
#: pools exist; a pool added there with no line here still lists, undescribed.
_POOL_NOTES = {
    'plain':     'the shipped plain-word list',
    'mixed':     'MIXED case — the ~ and gU levels feed on these',
    'proverbs':  'real proverbs, whole lines',
    'misquotes': 'proverbs with one word wrong — something to mend',
    'custom':    "the level's own :vocab words",
}


def _render_standard_scroll(term: Terminal, iw: int, game_h: int, content: dict,
                            known: set | None = None) -> None:
    """Render any scroll whose 'lines' list uses blank/dim/amber/cmd/smudge specs.

    A ('smudge', key, prefix, tail, gate) line is drawn obscured until every
    command token in `gate` is in `known`; once known it renders as a clear
    ('cmd') row revealing the key and full description."""
    known = known or set()
    BOX_IW = 54; BOX_BW = BOX_IW + 4
    box_bg  = term.on_color_rgb(10, 8, 2)
    amber_b = term.color_rgb(220, 175, 35) + term.bold
    amber   = term.color_rgb(220, 175, 35)
    body    = term.color_rgb(185, 150, 55)
    smudge  = term.color_rgb(120, 92, 38)   # murky ink — visible as a stain, dimmer than body
    hi      = term.color_rgb(255, 220, 60) + term.bold
    rst     = term.normal
    col_off = max(1, (iw + 2 - BOX_BW) // 2)
    bdr = box_bg + amber_b; inn = box_bg

    def row(vis, colored):
        return (bdr + '║ ' + rst + inn + colored +
                inn + ' ' * max(0, BOX_IW - vis) + bdr + ' ║' + rst)

    blank = row(0, '')

    T = content['title']
    lT = (BOX_IW - len(T)) // 2; rT = BOX_IW - len(T) - lT
    title = row(BOX_IW, ' ' * lT + hi + T + inn + ' ' * rT)

    # Pad every key to a common width so the ──> arrows and descriptions line
    # up in clean columns (whether a row is smudged or revealed).
    key_w  = max(([len(s[1]) for s in content['lines'] if s[0] in ('cmd', 'smudge', 'smudge_seg')]
                  + [sum(len(t) for t, _ in s[1]) for s in content['lines'] if s[0] == 'segs']),
                 default=0)
    indent = '  '

    def cmd_row(key, desc):
        sep = '  ────>  '
        k   = key.ljust(key_w)
        plain = f'{indent}{k}{sep}{desc}'
        return row(len(plain),
                   indent + hi + k + rst + inn + body + sep + rst + inn + amber + desc + rst + inn)

    def seg_row(segments, desc):
        # render a key as (text, bold) segments — bold the typable abbreviation
        # letters, dim the optional remainder of the full option name.
        sep = '  ────>  '
        key = ''.join(t for t, _ in segments)
        pad = ' ' * max(0, key_w - len(key))
        plain = f'{indent}{key}{pad}{sep}{desc}'
        colored = indent
        for txt, bold in segments:
            colored += (hi if bold else body) + txt + rst + inn
        colored += body + pad + sep + rst + inn + amber + desc + rst + inn
        return row(len(plain), colored)

    def smudge_row(key, smudge_prefix, clear_tail):
        sep    = '  ────>  '
        k      = key.ljust(key_w)
        text   = f'{indent}{k}{sep}{smudge_prefix}{clear_tail}'
        solid  = len(indent) + len(k) + len(sep) + len(smudge_prefix)
        chars, smudged = _water_stain(text, solid)
        painted, prev = '', None
        for ch, is_s in zip(chars, smudged):
            col = smudge if is_s else body
            if col != prev:
                painted += col
                prev = col
            painted += ch
        return row(len(text), painted + rst + inn)

    def smudge_seg_row(key_text, hide_prefix, desc):
        # a 'segs'-style key/desc line whose key HEAD is blotted out: the indent +
        # hide_prefix become an ink stain, the key tail + arrow + desc stay clean.
        sep   = '  ────>  '
        k     = key_text.ljust(key_w)
        text  = f'{indent}{k}{sep}{desc}'
        solid = len(indent) + len(hide_prefix)
        chars, smudged = _water_stain(text, solid)   # the same dip as every scroll
        painted, prev = '', None
        for ch, is_s in zip(chars, smudged):
            col = smudge if is_s else body
            if col != prev:
                painted += col
                prev = col
            painted += ch
        return row(len(text), painted + rst + inn)

    def body_row(s):  return row(len(s), body + s + rst)
    def amber_row(s): return row(len(s), amber + s + rst)

    def _build(spec):
        k = spec[0]
        if k == 'blank':  return blank
        if k == 'dim':    return body_row(spec[1])
        if k == 'amber':  return amber_row(spec[1])
        if k == 'cmd':    return cmd_row(spec[1], spec[2])
        if k == 'segs':   return seg_row(spec[1], spec[2])
        if k == 'smudge_seg': return smudge_seg_row(spec[1], spec[2], spec[3])
        if k == 'smudge':
            key, prefix, tail = spec[1], spec[2], spec[3]
            gate = spec[4] if len(spec) > 4 else None
            if _smudge_gate_met(gate, known):     # command learned → reveal
                return cmd_row(key, prefix + tail)
            return smudge_row(key, prefix, tail)
        raise ValueError(k)

    AK = '[ any key ]'; lAK = (BOX_IW - len(AK)) // 2
    footer = row(BOX_IW, ' ' * lAK + body + AK + inn + ' ' * (BOX_IW - len(AK) - lAK))
    sep_h = '═' * (BOX_IW + 2)

    lines = [
        bdr + '╔' + sep_h + '╗' + rst,
        blank, title, blank,
        *[_build(s) for s in content['lines']],
        blank, footer, blank,
        bdr + '╚' + sep_h + '╝' + rst,
    ]

    # Center on the actual box height so the box tracks any added/removed lines.
    row_off = 3 + max(0, (game_h - len(lines)) // 2)
    for i, line in enumerate(lines):
        print(term.move_yx(row_off + i, col_off) + line, end='', flush=True)
    term.inkey()


#: The admin notice, once per save. Signing in as `admin` unlocks every level,
#: opens the forge, AND prints each level's solution across the screen as you
#: play — and the last of those cannot be undone by turning it back off, because
#: you have already read the answer.
#:
#: Deliberately NOT drawn as a scroll. Every other full-screen box in this game
#: is parchment-and-amber, in the wizard's voice, and a player skims those for
#: flavour — which is exactly the wrong reflex here. This one is plain,
#: unstyled, and says "answers" in as many words. A warning that reads as
#: atmosphere is a warning nobody heeds.
_ADMIN_NOTICE = (
    'ADMIN MODE',
    '',
    'You have signed in as `admin`. This unlocks every level,',
    'opens the level forge, and shows the solution to each',
    'puzzle as you play.',
    '',
    'It is meant for authoring and testing. If you came here to',
    'PLAY Vimny, quit and start again under any other name — the',
    'game will not be the same with the answers on screen.',
)


def _plain_box(term: Terminal, iw: int, game_h: int, texts, *,
               bg, edge_rgb, head_rgb, body_rgb, footer: str) -> str:
    """Draw a plain, centred, unstyled box and wait for one key; return it.

    Deliberately shares no chrome with the parchment scrolls. The two things
    drawn this way — the admin warning and the submission page — are the game
    speaking as a program rather than as a wizard, and both are decisions the
    player must actually read before making. `texts[0]` is centred as a title;
    an empty string is a blank line.
    """
    BOX_IW = 62; BOX_BW = BOX_IW + 4
    box_bg = term.on_color_rgb(*bg)
    edge   = box_bg + term.color_rgb(*edge_rgb) + term.bold
    head   = term.color_rgb(*head_rgb) + term.bold
    body   = term.color_rgb(*body_rgb)
    rst    = term.normal
    col_off = max(1, (iw + 2 - BOX_BW) // 2)

    def row(vis, colored):
        return (edge + '║ ' + rst + box_bg + colored +
                box_bg + ' ' * max(0, BOX_IW - vis) + edge + ' ║' + rst)

    sep_h = '═' * (BOX_IW + 2)
    lines = [edge + '╔' + sep_h + '╗' + rst, row(0, '')]
    for i, text in enumerate(texts):
        text = text[:BOX_IW]
        if not text:
            lines.append(row(0, ''))
        elif i == 0:                                   # the title, centred
            pad = (BOX_IW - len(text)) // 2
            lines.append(row(BOX_IW, ' ' * pad + head + text
                             + box_bg + ' ' * (BOX_IW - len(text) - pad)))
        else:
            lines.append(row(len(text), body + text))
    pad = (BOX_IW - len(footer)) // 2
    lines += [row(0, ''),
              row(BOX_IW, ' ' * pad + body + footer
                  + box_bg + ' ' * (BOX_IW - len(footer) - pad)),
              row(0, ''),
              edge + '╚' + sep_h + '╝' + rst]

    row_off = 3 + max(0, (game_h - len(lines)) // 2)
    print(term.home + term.clear, end='')
    for i, line in enumerate(lines):
        print(term.move_yx(row_off + i, col_off) + line, end='', flush=True)
    return term.inkey()


def _show_admin_notice(term: Terminal, iw: int, game_h: int) -> None:
    """A plain, unmissable box shown once per save. Any key dismisses it."""
    _plain_box(term, iw, game_h, _ADMIN_NOTICE,
               bg=(28, 6, 6),                         # not parchment: a warning
               edge_rgb=(235, 90, 70), head_rgb=(255, 210, 120),
               body_rgb=(230, 210, 200), footer='[ any key ]')


def maybe_admin_notice(term: Terminal, player, progress: dict) -> None:
    """Show the admin notice if this save has not seen it, then remember.

    Keyed on the SAVE, not on the session, so it fires once per player rather
    than once per launch — and it is written down immediately, so a crash on the
    way to the overworld does not turn "once" into "every time"."""
    if player.name != 'admin' or progress.get('admin_notice_seen'):
        return
    _show_admin_notice(term, _iw(term), term.height - 8)
    progress['admin_notice_seen'] = True
    SM.save_progress(progress, player.name)


def submission_dir():
    """Where `:submit` leaves the link and the file it points at.

    The link is thousands of characters — far too long to read off a terminal,
    and unselectable once wrapped — so it is written down rather than printed.
    The `.json` beside it is the fallback for a level too big to ride inside a
    URL: open the (unfilled) form and paste the file in.
    """
    return SM.SAVE_DIR / 'submit'


def prepare_submission(level, slug: str):
    """Build the link and write both files. Returns `(url, prefilled, url_path)`.

    Nothing here talks to the network — it composes a URL and touches the disk.
    Opening it is a separate, confirmed step, so an author who types `:submit`
    to see what it says has not yet sent anything anywhere.
    """
    url, prefilled = SUBMIT.build_url(level, slug)
    out = submission_dir()
    out.mkdir(parents=True, exist_ok=True)
    url_path = out / f'{slug}.url'
    url_path.write_text(url + '\n', encoding='utf-8')
    (out / f'{slug}.json').write_text(LF.dumps(level), encoding='utf-8')
    return url, prefilled, url_path


def _tilde(path) -> str:
    """`~/.Vimny/…` rather than a home directory nobody needs to read."""
    try:
        return '~/' + str(Path(path).relative_to(Path.home()))
    except ValueError:
        return str(path)


def run_submit(term: Terminal, iw: int, game_h: int, level, slug: str,
               report, opener=None) -> str:
    """Show the submission page and, only on `o`, open the link. Returns a
    one-line result for the forge's message bar.

    Opening a browser is the one outward-facing thing the forge does, so it is
    behind an explicit keypress and a screen that says where the level is going
    and under whose name. `opener` is `webbrowser.open` — injected so a test can
    prove the link is right without a browser appearing.
    """
    try:
        url, prefilled, url_path = prepare_submission(level, slug)
    except OSError as exc:
        return f'Could not write the submission: {exc}'
    if opener is None:
        import webbrowser
        opener = webbrowser.open

    texts = [
        'SUBMIT A LEVEL',
        '',
        f'{level.name[:52]}  —  par {report.par}, budget {report.budget}',
        f'by {level.author}',
        '',
        f'This opens a "new file" form on github.com/{SUBMIT.repo()}',
        f'at {SUBMIT.file_path(slug)}, ready to become a pull request.',
        'GitHub makes the fork and the branch; you sign in and',
        'press the button, so the level arrives under your name.',
        '',
        'Vimny sends nothing itself and holds no account of yours.',
        '',
    ]
    if prefilled:
        texts.append('The form arrives already filled in.')
    else:
        # Honest about the one thing that can degrade, and what to do about it.
        texts.append('This level is too long to carry in a link, so the form')
        texts.append('opens EMPTY. Paste the file saved beside the link:')
    texts.append(f'  {_tilde(url_path)}')

    key = _plain_box(term, iw, game_h, texts,
                     bg=(8, 20, 28), edge_rgb=(110, 180, 220),
                     head_rgb=(255, 210, 120), body_rgb=(210, 225, 235),
                     footer='[ o ] open in browser   [ any other key ] not now')
    if str(key).lower() != 'o':
        return f'Not sent. The link is saved at {_tilde(url_path)}'
    try:
        opened = opener(url)
    except Exception as exc:                      # noqa: BLE001 — any browser fault
        return f'Could not open a browser ({exc}) — the link is at {_tilde(url_path)}'
    if opened is False:
        return f'No browser to open — the link is at {_tilde(url_path)}'
    return 'Opened GitHub. Sign in, review it, and press Propose new file.'


def _show_catalog_scroll(term: Terminal, iw: int, game_h: int,
                         scroll_id: str, known: set | None = None) -> None:
    """Render any SCROLL_CATALOG scroll by id via the standard renderer — used
    for the relic (randomly dropped) scrolls, which all use the 'lines'
    format."""
    from vimny.content.scrolls import SCROLL_CATALOG
    for s in SCROLL_CATALOG:
        if s['id'] == scroll_id:
            _render_standard_scroll(term, iw, game_h, s['content'], known)
            return


# The codex scrolls rendered by _render_standard_scroll, keyed by scroll id.
# 'register' is the one bespoke renderer (_show_reliquary_scroll).
_STD_SCROLLS = {
    'leap':      WARDEN_LEAP_SCROLL,
    'visual':    WARDEN_SIGHT_SCROLL,   # orphaned: re-homes to the relocated v-lesson
    'search':    SURVEYORS_PATH_SCROLL,
    'setnum':    WAYPOINT_SCROLL,
    'd_op':      OPERATOR_CODEX_SCROLL,
    'writers':   INSCRIBERS_HAND_SCROLL,
    'text_obj':  WHOLE_WORD_SCROLL,
    'subst': REWRITING_WORD_SCROLL,
}


def _show_scroll_by_id(term: Terminal, iw: int, game_h: int,
                       sid: str, known: set | None = None) -> None:
    """Render any scroll by its id: 'register' gets the bespoke amber box, the
    codex ids their _STD_SCROLLS content, anything else the catalogue renderer."""
    if sid == 'register':
        _show_reliquary_scroll(term, iw, game_h, known)
    elif sid in _STD_SCROLLS:
        _render_standard_scroll(term, iw, game_h, _STD_SCROLLS[sid], known)
    elif sid.startswith('blessing_'):
        from vimny.content.blessings import blessing_scroll_content
        _bc = blessing_scroll_content(sid)
        if _bc is not None:
            _render_standard_scroll(term, iw, game_h, _bc, known)
    else:
        _show_catalog_scroll(term, iw, game_h, sid, known)


# Each boss chest drops the scroll previewing the next act's commands; smudged
# lines clarify as those commands are learned.  level → (scroll/extras id,
# full-text title|None, full-text body|None).  The id is also the command the
# boss GATES: it stays locked on the boss level until its scroll is read (see
# run_dungeon's level-start extras injection); rendering is _show_scroll_by_id.
_SCROLL_DROPS = {
    'reliquary':            ('register',  None,                     None),
    'wardens_keep':         ('leap',      None,                     None),
    'warden_surveyor':      ('search',    None,                     None),
    'warden_pathfinder':    ('d_op',      "The Operator's Codex",   _SCROLL_TEXT_OPERATOR_CODEX),
    'warden_manifold':      ('writers',   "The Inscriber's Hand",   _SCROLL_TEXT_INSCRIBERS_HAND),
    'warden_scrivener':     ('text_obj',  'The Whole Word',         _SCROLL_TEXT_WHOLE_WORD),
    'grandmasters_sanctum': ('subst',     'The Rewriting Word',      _SCROLL_TEXT_REWRITING_WORD),
}


def _unlock_animation(term: Terminal, room, player,
                      door_r: int, door_c: int, iw: int, game_h: int,
                      key_color: str | None = None, icon: str | None = None) -> None:
    """Flash key icon at door position, then blank it — door + key both vanish.

    `icon` overrides the key glyph. A fancy door is opened by the same gesture
    and deserves the same beat, but holding up a KEY at a door that never
    wanted one is the one frame in the game that would contradict its own
    mechanic — so it flashes what it did take: something typed."""
    vr_start = max(0, min(player.row - game_h // 2, room.rows - game_h))
    vc_start = max(0, min(player.col - iw    // 2,  room.cols - iw))
    scr_r = door_r - vr_start + 3
    scr_c = door_c - vc_start + 1 + _gutter_w(player)
    if not (0 <= scr_r < term.height and 0 <= scr_c < iw):
        return
    key_clr = key_color if key_color is not None else C.key_fg()
    rst  = term.normal
    fbg  = C.floor_bg()
    glyph = icon if icon is not None else S.KEY
    print(term.move_yx(scr_r, scr_c) + fbg + key_clr + glyph + rst, end='', flush=True)
    time.sleep(0.35)
    print(term.move_yx(scr_r, scr_c) + fbg + '  ' + rst, end='', flush=True)
    time.sleep(0.08)


def _sc_twinkle_animation(term, room, player, moved, iw: int, game_h: int) -> None:
    """The Sculpting Chambers plaques following the engine as o/O insert rows.
    `moved` = [(old_row, new_row, col, symbols), ...]. Two beats: (1) the plaque
    SLIDES from its old row to its new one (clearing its trail); (2) at the new
    row each letter is re-inked one-by-one in bright white and COOLS to verdant.
    A transient overlay — the next _render restores the settled plaque."""
    vr = max(0, min(player.row - game_h // 2, room.rows - game_h))
    vc = max(0, min(player.col - iw    // 2,  room.cols - iw))

    def _cell_bg(rr, c):
        """The TRUE background under (rr, c), so every animation frame blends
        into the terrain instead of stamping one flat colour."""
        if not (0 <= rr < room.rows and 0 <= c < room.cols):
            return C.wall_bg()
        ct = room.cells[rr][c]
        if ct == CellType.WATER:
            return C.water_bg()
        if ct == CellType.WOOD_WALL:
            return C.wood_wall_bg()
        if ct == CellType.WALL or (rr, c) in room.fog_cells:
            return C.wall_bg()
        return C.floor_bg()

    def _draw(rr, c0, text, clr):
        sr = rr - vr + 3
        if not (3 <= sr < 3 + game_h):
            return
        gut = _gutter_w(player)
        for k, ch in enumerate(text):
            sc = c0 + k - vc + 1 + gut
            if 1 <= sc < 1 + iw:
                print(term.move_yx(sr, sc) + _cell_bg(rr, c0 + k) + clr + ch
                      + term.normal, end='', flush=True)

    dim_green = term.dim + C.rune_verdant()
    # ── beat 1: slide each plaque from old row → new row, clearing the trail ──
    for (old_r, new_r, c0, syms) in moved:
        text = ''.join(syms)
        step = 1 if new_r >= old_r else -1
        path = list(range(old_r, new_r + step, step))
        for i, rr in enumerate(path):
            if i > 0:
                _draw(path[i - 1], c0, ' ' * len(text), '')   # wipe the last frame
            _draw(rr, c0, text, dim_green)
            time.sleep(0.09)
    # ── beat 2: re-ink each landed plaque letter-by-letter, white cooling to green
    for (old_r, new_r, c0, syms) in moved:
        text = ''.join(syms)
        for k in range(len(text)):
            _draw(new_r, c0 + k, text[k], term.bright_white + term.bold)
            time.sleep(0.06)
        _draw(new_r, c0, text, C.rune_verdant())                       # cools to verdant
        time.sleep(0.05)


# ── Animations ────────────────────────────────────────────────────────────────

def _explosion_animation(term, room, expl_r, expl_c, scr_r, scr_c, iw, game_h):
    """Expanding * rings centred on screen position (scr_r, scr_c) = room (expl_r, expl_c).

    Walls stop the visual rings (no * drawn on a wall cell) but do not shift
    or re-centre the pattern — each ring remains anchored to (expl_r, expl_c).
    """
    # Each frame: {distance: color}  — inner rings dim as the wave expands outward
    frames = [
        ({0: term.bold + term.bright_white},                                         0.05),
        ({0: term.color_rgb(255, 200, 50) + term.bold,
          1: term.bold + term.bright_white},                                          0.07),
        ({0: term.color_rgb(220,  80, 10),
          1: term.color_rgb(255, 170, 40) + term.bold,
          2: term.bold + term.bright_white},                                          0.08),
        ({0: term.color_rgb(120,  30,  5),
          1: term.color_rgb(200,  70, 15),
          2: term.color_rgb(255, 140, 30) + term.bold,
          3: term.bold + term.bright_white},                                          0.10),
        ({1: term.color_rgb( 80,  15,  0),
          2: term.color_rgb(160,  50, 10),
          3: term.color_rgb(230, 110, 25) + term.bold},                              0.10),
    ]
    for colors, delay in frames:
        max_d = max(colors)
        for dr in range(-max_d, max_d + 1):
            for dc in range(-max_d, max_d + 1):
                dist = abs(dr) + abs(dc)
                color = colors.get(dist)
                if not color:
                    continue
                rr, rc = expl_r + dr, expl_c + dc
                if not (0 <= rr < room.rows and 0 <= rc < room.cols):
                    continue
                if room.cells[rr][rc] == CellType.WALL:
                    continue
                sr, sc = scr_r + dr, scr_c + dc
                if not (3 <= sr < 3 + game_h and 1 <= sc < 1 + iw):
                    continue
                print(term.move_yx(sr, sc) + color + '*' + term.normal,
                      end='', flush=True)
        time.sleep(delay)


# ── The tumble: a glyph shoved over a ledge, or swept away by water ───────────
#
# The pace below is the original one — an unhurried 0.12s a frame, a full second
# and a bit of fall. What changed is WHO WAITS FOR IT. This used to be played
# INLINE: every insert that shoved a glyph into the void slept its way through
# the whole animation before the next keystroke was read, per fallen cell, so a
# 0.72s drop was a ~17 WPM typing limit and an edit that pushed five glyphs over
# the brink stalled the game for three and a half seconds.
#
# A reflow's falls are now QUEUED (`room._falling`) and repainted by _render off
# the clock — so the tumble takes exactly as long as it always did to watch, and
# costs the typist nothing. That decoupling is also what makes a longer ladder
# free: the fall reads longer than the old six-frame drop and still delays
# nobody. Only the PLAYER's own fall (stepping onto a void rune, drowning) still
# blocks, and should: the game is stopping to take a heart off them.
_FALL_FRAME_S = 0.12                    # the original pace, restored
_FALL_GLYPHS  = ('@', '◉', '◉', 'o', 'o', '·', '·', '˙', '˙', ' ')
_VOID_HOT,  _VOID_COLD  = (110, 60, 160), (20,  5, 30)   # wizard-violet, guttering
_DROWN_HOT, _DROWN_COLD = ( 60, 140, 210), ( 5, 25, 75)  # water-blue, sinking


def _fall_frames(term, hot, cold):
    """(escape, glyph) per frame — the colour ramps hot → cold down the ladder."""
    n, out = len(_FALL_GLYPHS), []
    for i, sym in enumerate(_FALL_GLYPHS):
        if sym == ' ':
            out.append((term.normal, sym))
            continue
        f   = i / (n - 1)
        rgb = tuple(int(h + (c - h) * f) for h, c in zip(hot, cold))
        out.append((term.color_rgb(*rgb) + (term.bold if i < 3 else ''), sym))
    return out


def _play_falls(term, cells, hot, cold):
    """Tumble every screen cell in `cells` together, BLOCKING — one sleep per
    frame rather than per cell. Only the player's own fall uses this."""
    if not cells:
        return
    for color, sym in _fall_frames(term, hot, cold):
        out = ''.join(term.move_yx(sr, sc) + color + sym + term.normal
                      for (sr, sc) in cells)
        print(out, end='', flush=True)
        time.sleep(_FALL_FRAME_S)


def _queue_falls(room, cells, hot, cold) -> None:
    """Hand a batch of BUFFER cells to the render loop to tumble on its own time.

    Buffer coordinates, not screen ones: the viewport can scroll out from under
    a fall that is still in the air, and the drop has to stay over the cell it
    is falling from."""
    if not cells:
        return
    room._falling = getattr(room, '_falling', [])
    room._falling.append({'cells': list(cells), 'hot': hot, 'cold': cold,
                          't0': time.time()})


def _draw_falls(term, room, player) -> bool:
    """Paint the frame each queued fall is up to; drop the ones that have landed.

    Called from _render, so a fall repaints over every redraw for as long as it
    is in the air. Returns True while any fall is still going, which is what
    keeps the idle loop rendering when the player has stopped typing."""
    queue = getattr(room, '_falling', None)
    if not queue:
        return False
    n, out, still = len(_FALL_GLYPHS), [], []
    for fall in queue:
        i = int((time.time() - fall['t0']) / _FALL_FRAME_S)
        if i >= n:
            continue                       # landed — the next render clears it
        still.append(fall)
        color, sym = _fall_frames(term, fall['hot'], fall['cold'])[i]
        out += [term.move_yx(*_void_screen_xy(term, room, player, r, c))
                + color + sym + term.normal for (r, c) in fall['cells']]
    room._falling = still
    if out:
        print(''.join(out), end='', flush=True)
    return bool(still)


def _void_fall_animation(term, screen_r, screen_c):
    _play_falls(term, [(screen_r, screen_c)], _VOID_HOT, _VOID_COLD)


def _gutter_w(player) -> int:
    """The :set nu gutter width the renderer prepends — every overlay
    animation must shift right by the same amount or it draws 4 cells west."""
    return 0 if getattr(player, 'number_mode', 'none') == 'none' else 4


def _void_screen_xy(term, room, player, r, c):
    """Buffer (r, c) → screen (row, col) within the player-centred viewport
    (the same transform the renderer and the normal-mode void fall use)."""
    iw       = _iw(term)
    game_h   = term.height - 8
    vr_start = max(0, min(player.row - game_h // 2, room.rows - game_h))
    vc_start = max(0, min(player.col - iw  // 2,    room.cols - iw))
    return r - vr_start + 3, c - vc_start + 1 + _gutter_w(player)


def _play_void_falls(term, dungeon, room, player):
    """Animate any characters the last reflow shoved over a ledge into the void.

    Reads room._last_void_falls (populated by vimny/engine/reflow.py), queues the drop
    at each fallen cell, then clears the list. Returns True if anything fell."""
    falls = getattr(room, '_last_void_falls', None)
    if not falls:
        return False
    _queue_falls(room, [(fr, fc) for (fr, fc, _sym) in falls],
                 _VOID_HOT, _VOID_COLD)
    room._last_void_falls = []
    return True


def _drown_animation(term, screen_r, screen_c):
    _play_falls(term, [(screen_r, screen_c)], _DROWN_HOT, _DROWN_COLD)


def _heart_container_animation(term, dungeon, player, budget, old_max_hp, message):
    """Fill the new hearts half-by-half, then flash all hearts gold, then back to red."""
    new_max_hp = player.max_hp
    player.hp  = old_max_hp
    for hp in range(old_max_hp, new_max_hp + 1):
        player.hp = hp
        render_all(term, dungeon, player, budget, message)
        time.sleep(0.09)
    for _ in range(3):
        render_all(term, dungeon, player, budget, message, heart_flash=True)
        time.sleep(0.13)
        render_all(term, dungeon, player, budget, message, heart_flash=False)
        time.sleep(0.07)


def _win_animation(term, iw, dungeon, player):
    """Non-par finish: a brief 'DUNGEON CLEARED' banner, blended into the room via
    the same per-cell-background draw as the fireworks/starfield (helpers below)."""
    bg_at     = _victory_cell_bg(term, dungeon.room, player, iw, term.height - 8)
    rows_text = [
        '✦  ★  ✦  ★  ✦  ★  ✦  ★  ✦',
        ' D U N G E O N   C L E A R E D ',
        '★  ✦  ★  ✦  ★  ✦  ★  ✦  ★',
    ]
    palettes = [
        (term.bright_yellow + term.bold, term.bright_green  + term.bold),
        (term.bright_white  + term.bold, term.bright_yellow + term.bold),
        (term.bright_green  + term.bold, term.bright_white  + term.bold),
    ]
    center = term.height // 2 - 1
    for frame in range(16):
        star_col, text_col = palettes[frame % 3]
        _draw_victory_banner(term, iw, center, rows_text,
                             [star_col, text_col, star_col], bg_at)
        time.sleep(0.1)


def _spaced_title(text: str) -> str:
    """Letter-space an all-caps banner title: 'VIM AD ASTRA' -> 'V I M   A D   A S T R A'."""
    return '   '.join(' '.join(word) for word in text.split())


def _victory_cell_bg(term, room, player, iw, game_h):
    """Return bg_at(term_r, term_c) -> the dungeon cell's background under that
    terminal cell, so overlaid victory glyphs blend into the room (not a flat band)."""
    vr_start = max(0, min(player.row - game_h // 2, room.rows - game_h))
    vc_start = max(0, min(player.col - iw // 2, room.cols - iw))
    # A soft-wrapped buffer (e.g. The Archivist's Library) is ONE logical row whose view
    # fills the whole screen with floor; walking room.cells by row would paint every line
    # past the first as wall_bg, so the banner backdrop wouldn't match the room. Flat floor.
    wrap = getattr(room, 'wrap_buffer', False)

    def bg_at(term_r, term_c):
        if not (3 <= term_r < 3 + game_h and 1 <= term_c <= iw):
            return C.floor_bg()
        if wrap:
            return C.floor_bg()
        room_r = (term_r - 3) + vr_start
        room_c = (term_c - 1) + vc_start - _gutter_w(player)
        if room_r >= room.rows or room_c >= room.cols:
            return C.wall_bg()
        if (room_r, room_c) in room.fog_cells:
            return C.wall_bg()
        ct = room.cells[room_r][room_c]
        if ct == CellType.WATER:
            return C.water_bg()
        if ct == CellType.WALL:
            return C.wall_bg()
        if ct == CellType.WOOD_WALL:
            return C.wood_wall_bg()
        return C.floor_bg()

    return bg_at


def _draw_victory_banner(term, iw, center, banner_rows, row_colors, bg_at):
    """Draw centered banner rows; each cell sits on its dungeon background."""
    for i, line in enumerate(banner_rows):
        pad     = max(0, (iw - len(line)) // 2)
        content = ' ' * pad + line + ' ' * max(0, iw - pad - len(line))
        col     = row_colors[i]
        term_r  = center + i
        out = term.move_yx(term_r, 1)
        for j, ch in enumerate(content):
            out += bg_at(term_r, 1 + j) + col + ch
        print(out + term.normal, end='', flush=True)


def _fireworks_animation(term, iw, dungeon, player):
    """Par-perfect (non-boss) finish: multicolour fireworks + the Horace banner
    'VIM PROMOVET INSITAM' ("training draws out the inborn force"; see CREDITS.md)."""
    h      = term.height
    room   = dungeon.room
    game_h = h - 8
    bg_at  = _victory_cell_bg(term, room, player, iw, game_h)

    bursts  = [
        (h // 4,     iw // 6),
        (h // 3,     iw * 5 // 6),
        (h // 2 - 1, iw // 2),
        (h * 2 // 3, iw // 4),
        (h * 2 // 3, iw * 3 // 4),
    ]
    star_chars = ['*', '+', '·', '˙', ' ']
    offsets    = [(0,-2),(0,2),(-1,-1),(-1,0),(-1,1),(1,-1),(1,0),(1,1),(-2,0),(2,0)]
    colors     = [
        term.color_rgb(255, 220,  60) + term.bold,
        term.color_rgb(255, 100, 100) + term.bold,
        term.color_rgb(100, 255, 150) + term.bold,
        term.color_rgb(120, 180, 255) + term.bold,
        term.color_rgb(255, 140, 255) + term.bold,
    ]
    banner_rows = [
        '✦ ★ ✦ ★ ✦ ★ ✦ ★ ✦ ★ ✦ ★ ✦ ★ ✦',
        '  ' + _spaced_title('VIM PROMOVET INSITAM') + '  ',
        '  Not a stroke wasted. You meant every key.  ',
        '★ ✦ ★ ✦ ★ ✦ ★ ✦ ★ ✦ ★ ✦ ★ ✦ ★',
    ]
    banner_palettes = [
        (term.bright_yellow + term.bold, term.bright_white  + term.bold, term.color_rgb(180,255,180) + term.bold),
        (term.bright_white  + term.bold, term.bright_green  + term.bold, term.bright_yellow + term.bold),
        (term.bright_green  + term.bold, term.bright_yellow + term.bold, term.bright_white  + term.bold),
    ]
    center = h // 2 - 2

    def _banner(frame):
        sp, tc, mc = banner_palettes[frame % 3]
        _draw_victory_banner(term, iw, center, banner_rows, [sp, tc, mc, sp], bg_at)

    for frame in range(20):
        sc = star_chars[min(frame // 4, len(star_chars) - 1)]
        for bi, (br, bc_) in enumerate(bursts):
            color = colors[bi % len(colors)]
            for dr, dc in offsets:
                rr = br + dr * (1 + frame // 5)
                cc = bc_ + dc * (1 + frame // 4)
                if 3 <= rr < h - 3 and 1 <= cc < iw:
                    print(term.move_yx(rr, cc) + bg_at(rr, cc) + color + sc + term.normal,
                          end='', flush=True)
        _banner(frame)
        if term.inkey(timeout=0.1):    # any key skips (the key is absorbed here)
            return
    _banner(19)             # settle on a final frame and hold ~1s so the motto can
    term.inkey(timeout=1.1)  # be read — or skipped (fires after every par-perfect finish)


def _starfield_victory(term, iw, dungeon, player, level):
    """Boss-completion finish: a lasting, sky-accurate twinkling starfield behind
    the 'VIM AD ASTRA' banner. Held until the player presses a key — a permanent
    celebration rather than a passing burst (see CREDITS.md)."""
    h      = term.height
    room   = dungeon.room
    game_h = h - 8
    bg_at  = _victory_cell_bg(term, room, player, iw, game_h)
    center = h // 2 - 1

    # Final boss gets the completion message; other bosses get the journey-continues message
    subtitle = '  Go among the stars!  ' if level == 'warden_eternal' else '  Onward and upward — the stars draw nearer.  '
    banner_rows = [
        '  ' + _spaced_title('VIM AD ASTRA') + '  ',
        subtitle,
    ]
    banner_band = set(range(center, center + len(banner_rows)))
    title_col   = term.bright_white + term.bold
    sub_col     = term.color_rgb(190, 205, 255)

    # A fixed field: mostly white stars, a touch of blue and red, twinkling in
    # brightness — sky-accurate (stars shimmer in brightness, not in hue).
    rng = random.Random(0x5A17)
    WHITE, BLUE, RED = 0, 1, 2
    palette = {
        WHITE: (term.bright_white + term.bold, term.color_rgb(205, 205, 220), term.color_rgb(120, 120, 145)),
        BLUE:  (term.color_rgb(175, 200, 255) + term.bold, term.color_rgb(120, 150, 215), term.color_rgb(75, 95, 150)),
        RED:   (term.color_rgb(255, 170, 150) + term.bold, term.color_rgb(215, 130, 115), term.color_rgb(150, 90, 80)),
    }
    glyphs  = ('★', '✦', '·')       # bright, mid, dim
    n_stars = max(24, (iw * game_h) // 26)
    stars = []
    for _ in range(n_stars):
        sr = rng.randint(3, 3 + game_h - 1)
        sc = rng.randint(1, iw)
        if sr in banner_band:
            continue
        roll = rng.random()
        hue  = BLUE if roll < 0.12 else (RED if roll < 0.22 else WHITE)
        stars.append((sr, sc, hue, rng.randint(0, 13)))

    hint     = '· · ·   press any key   · · ·'
    hint_row = min(h - 2, center + len(banner_rows) + 2)
    hint_col = term.color_rgb(95, 100, 130)

    frame = 0
    while True:
        for (sr, sc, hue, phase) in stars:
            v = (frame * 2 + sr * 7 + sc * 5 + phase) % 14
            if   v < 1: lvl = 0          # bright twinkle
            elif v < 5: lvl = 1          # mid
            elif v < 9: lvl = 2          # dim
            else:       lvl = None       # dark this frame (the shimmer)
            ch = ' ' if lvl is None else glyphs[lvl]
            fg = ''  if lvl is None else palette[hue][lvl]
            print(term.move_yx(sr, sc) + bg_at(sr, sc) + fg + ch + term.normal,
                  end='', flush=True)
        _draw_victory_banner(term, iw, center, banner_rows, [title_col, sub_col], bg_at)
        _draw_victory_banner(term, iw, hint_row, [hint], [hint_col], bg_at)
        frame += 1
        if term.inkey(timeout=0.13):
            break


# ── Small helpers ──────────────────────────────────────────────────────────────

_ATTACK_FLASH_TTL = 3   # no-key ticks per frame (~0.3 s at 0.1 s timeout)

_SPEAR_DIRS = {
    ( 1,  0): '↓',   # attacker above → attack comes downward
    (-1,  0): '↑',   # attacker below → attack comes upward
    ( 0,  1): '→',   # attacker left  → attack comes rightward
    ( 0, -1): '←',   # attacker right → attack comes leftward
}


def _count_prefix_cost(count: int, count_given: bool = False) -> int:
    """Keystrokes spent on a typed count prefix: 0 when no count was typed (a bare
    command), else the digits.  An *explicitly typed* count is real keypresses even
    when it is 1 — `1p`/`1J`/`1dd` cost their digit; a redundant `1` is never free.
    Solver-built actions omit count_given (default False), so a modelled count of 1
    keeps the no-count price — only real keystrokes that typed a `1` pay for it."""
    return len(str(count)) if (count_given or count > 1) else 0


def _keystroke_cost(count: int, motion: str = '', count_given: bool = False) -> int:
    # A bare motion (no count typed) is one keystroke; an *explicitly typed* count
    # is real keypresses, even when it is 1 — `G`=1 but `1G`=2.  Typing a redundant
    # `1` is never free: it's a wasteful 2-key way to do what `gg` does, so it must
    # not undercut the count==1 discount that only a no-count motion earns.
    base = 1 + _count_prefix_cost(count, count_given)
    # multi-character motions: one extra keypress per extra character required
    # NOTE: gj/gk are deliberately unpriced — pricing them would reprice the
    # Archivist's Library.
    if motion in ('f', 'F', 't', 'T', 'gg', 'ge', 'gE', 'gJ', 'g_'):
        base += 1
    return base


def _register_prefix_cost(action: dict) -> int:
    """`"{reg}` is TWO real keypresses (the quote and the register letter), so it
    is charged like any other keystrokes — a named register buys persistence, not
    free typing. 0 when no prefix was typed (the implicit unnamed register)."""
    return 2 if action.get('register') is not None else 0


def _operator_cost(action: dict) -> int:
    """Keystroke cost of an operator command, e.g. dw=2, d3w=4, dd=2, gUiw=4, gUU=3.
    A typed `"{reg}` prefix adds its two keys ("ayw=4)."""
    count = action.get('count', 1)
    cg    = action.get('count_given', False)
    reg = _register_prefix_cost(action)
    if 'shorthand' in action:              # D / C — ONE physical keypress, not d+$
        return reg + _count_prefix_cost(count, cg) + 1
    c = reg + len(action['op'])            # 'd'=1, 'gU'=2
    c += _count_prefix_cost(count, cg)
    if 'textobj' in action:                # diw, ci( … (i/a + obj char)
        return c + 2
    motion = action['motion']
    if motion == 'line':                   # dd / yy / gUU
        return c + 1
    c += _keystroke_cost(action.get('motion_count', 1), motion,
                         action.get('motion_count_given', False))
    return c


def _calc_stars(won: bool, budget: Budget, room, player, level: str = '') -> int:
    if not won:
        return 0
    if level_type(level) != 'dungeon':
        return 0
    par = room.par or 0
    if par > 0 and budget.spent <= par and player.hp >= 6:
        return 2
    return 1


def _build_dungeon(slug: str, seed: int, game_h: int = 33, admin: bool = False):
    # Builders are named by slug (vimny/content/levels.py): build_dungeon_<slug>.
    builder = getattr(_dg, f'build_dungeon_{slug}', _dg.build_dungeon_first_cave)
    if slug == 'screen_vault':
        # The Screen Vault: only solve the (admin-only) answer path when admin —
        # its par-Dijkstra is too slow to run on every load (par is locked).
        dungeon = builder(seed, game_h=game_h, compute_answer=admin)
    else:
        dungeon = builder(seed)
    # The fog law, applied to EVERY room of every level, here rather than sixty
    # times in sixty builders. A builder may still lay scripted fog on top; what
    # it may no longer do is forget the floor. (engine.motion.enforce_fog_law)
    for _room in dungeon.rooms:
        _enforce_fog_law(_room)
    return dungeon


# The Warden Manifold's boss ward state rides the undo snapshot — UNLIKE the
# Pathfinder convention (boss state survives undo), and deliberately: with the
# ward counter outside the snapshot, undoing past a stamp restored a world
# where the NEXT ward's check read vacuously broken (no rot = ward 3
# "sheared"), so the bolt stood open and the Warden could be ground down
# strike after strike without re-solving anything. Undo now rewinds the ward
# with the world.
_WM_UNDO_ATTRS = ('_wm_ward', '_wm_rot0', '_wm_r2_spent0', '_wm_r3_spent0',
                  '_wsc_ward', '_wsc_r2_spent0')   # + the Scrivener's press


def _snapshot(room, player, budget, *, row=None, col=None, spent=None, ans=None) -> dict:
    """Undo/redo snapshot of all mutable game state.

    Pass row/col/spent explicitly only when the player has already moved and
    the snapshot must record the *previous* position (dynamite upgrade path).
    All entity-killing actions must call this before mutating state so that
    'u' can fully restore the world, including player inventory.
    ans: (answer_pos, answer_diverged) to store; defaults to room's current values.
    """
    ap = ans[0] if ans is not None else room.answer_pos
    ad = ans[1] if ans is not None else room.answer_diverged
    if hasattr(room, '_wm_stamps') or hasattr(room, '_wsc_stamps'):   # a boss press
        return dict(_base_snapshot(room, player, budget, row, col, spent, ap, ad),
                    wm_state={k: getattr(room, k) for k in _WM_UNDO_ATTRS
                              if hasattr(room, k)})
    return _base_snapshot(room, player, budget, row, col, spent, ap, ad)


def _base_snapshot(room, player, budget, row, col, spent, ap, ad) -> dict:
    return {
        'row':      player.row  if row   is None else row,
        'col':      player.col  if col   is None else col,
        'spent':    budget.spent if spent is None else spent,
        'entities': [clone_entity(e) for e in room.entities],
        'char_runs': [CharRun(ru.row, ru.col, ru.symbols, ru.kind) for ru in room.char_runs],
        'cells':    [r[:] for r in room.cells],
        'rows':     room.rows,
        'cols':     room.cols,
        'exit_pos': room.exit_pos,
        'spawn_pos': room.spawn_pos,
        'fog_cells': set(room.fog_cells),
        'underwater_cells': set(room.underwater_cells),
        'answer_pos':      ap,
        'answer_diverged': ad,
    }


def _pop_history_step(src: list, dst: list, room, player, budget, is_redo: bool = False) -> bool:
    """Pop one normal-mode undo/redo entry from src, restore state, push inverse to dst.

    A movement entry may carry a 6th element ('f'|'s', recost) tagging the find/search
    that established the ;/, or n/N repeat register. Undoing it arms pending_recost so the
    next repeat re-pays the full cost (it can't inherit a refunded find/search for 1 key);
    redoing it clears the arm again. The tag rides along to the inverse so undo/redo stay
    symmetric."""
    if not src:
        return False
    item = src.pop()
    if isinstance(item, dict):
        marker = item.get('recost')           # ('c', recost): a tagged change (see the dot accounting)
        inv = _snapshot(room, player, budget)
        if marker is not None:
            inv['recost'] = marker
        dst.append(inv)
        if marker is not None:
            reg, recost = marker
            setattr(player, f'pending_recost_{reg}', 0 if is_redo else recost)
        player.row, player.col = item['row'], item['col']
        budget.spent  = item['spent']
        room.entities = item['entities']
        if 'char_runs' in item:
            room.char_runs = item['char_runs']
        if 'cells' in item:
            room.cells = item['cells']
            room.rows  = item['rows']
            room.cols  = item.get('cols', room.cols)
            room.exit_pos = item['exit_pos']
            room.spawn_pos = item['spawn_pos']
        room.fog_cells = item['fog_cells']
        if 'underwater_cells' in item:
            room.underwater_cells = item['underwater_cells']
        if 'wm_state' in item:                   # the Manifold's boss ward state
            for k in _WM_UNDO_ATTRS:
                if k in item['wm_state']:
                    setattr(room, k, item['wm_state'][k])
                elif hasattr(room, k):
                    delattr(room, k)
        room.rebuild_indexes()
        if 'answer_pos' in item:
            room.answer_pos      = item['answer_pos']
            room.answer_diverged = item['answer_diverged']
    else:
        marker = item[5] if len(item) >= 6 else None
        inv = (player.row, player.col, budget.spent, room.answer_pos, room.answer_diverged)
        dst.append(inv + (marker,) if marker is not None else inv)
        r, c, s = item[0], item[1], item[2]
        player.row, player.col, budget.spent = r, c, s
        if len(item) >= 5:
            room.answer_pos, room.answer_diverged = item[3], item[4]
        if marker is not None:
            reg, recost = marker
            setattr(player, f'pending_recost_{reg}', 0 if is_redo else recost)
    return True


def _ed_step_n(src: list, dst: list, n: int, room, player) -> int:
    """Apply up to n editor undo/redo steps (src→dst). Returns how many were applied."""
    done = 0
    for _ in range(n):
        if not src:
            break
        dst.append(_ed_snapshot(room, player))
        _ed_restore(room, player, src.pop())
        done += 1
    return done


def _manhattan(r1, c1, r2, c2) -> int:
    return abs(r1 - r2) + abs(c1 - c2)


def _hearts_note(hp: int, remaining: bool = True) -> str:
    """'(2½ ♥ remaining)' — the damage report every hazard appends. One source
    of truth so the five hazard messages can't drift apart (they did once)."""
    h, hh = hp // 2, '½' if hp % 2 else ''
    return f'({h}{hh} ♥{" remaining" if remaining else ""})'


def _kill_door_group(room, row: int, col: int, kind: str = 'door') -> None:
    """Kill the entity at (row, col) and all contiguous adjacent entities of the same kind.

    Uses BFS so a 2-cell horizontal connector or N-cell vertical barrier are
    each treated as one unit — but matching entities in a non-adjacent row/col
    are left untouched.
    """
    seen: set = set()
    q: deque = deque([(row, col)])
    while q:
        r, c = q.popleft()
        if (r, c) in seen:
            continue
        seen.add((r, c))
        ent = room.entity_at(r, c)
        if ent and ent.kind == kind:
            room.kill_entity(ent)
            for dr, dc in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                nb = (r + dr, c + dc)
                if nb not in seen:
                    q.append(nb)


def _operators_vault_tick(room, player) -> list:
    # Fog reveal, per key: a door-blocked flood from wherever
    # the player stands — so a corridor's pockets surface with its gate, and
    # the C10 collapse that drops the player onto the sealed ledge lights it
    # from where they land. (The player's own cell is always cleared first:
    # a fall may park INSIDE fog, and the flood must start somewhere.)
    room.fog_cells.discard((player.row, player.col))
    _reveal_from(room, player.row, player.col)
    """The vault door: IT OPENS WHEN EVERY PASSWORD HAS BEEN SPOKEN.

    The level used to be a combat gauntlet, and the vault opened on the last
    guard falling. That was the wrong lock for what the corridors teach. A guard
    can only punish a cut that reaches TOO LITTLE — he survives it — and every
    guard a `dw` kills a `d$` kills too, so a pack could never punish a cut that
    took too much. Half the corridors were beaten by the wrong operator for less
    than par, and no arrangement of goblins was going to fix it.

    A `fancy_door` is the whole lock in one entity: it opens for a register
    reading exactly its password, so a narrow cut hands it a fragment and a wide
    cut hands it the password plus whatever it swept up. Both are refused. With
    that in place the guards had nothing left to do, and the vault's condition
    follows the corridors: every gate in the level open.

    STATELESS, hence undo-safe — the vault is re-derived from the doors every
    turn, so undoing the last paste re-bars it and redoing it re-opens it.
    Returns banner messages for anything that just changed."""
    msgs = []
    # Looked up LIVE: undo replaces room.entities with snapshot copies, so a
    # reference held across a turn would go stale after the first u.
    door = next((e for e in room._entity_by_kind.get('seal_door', []) if e.alive),
                None)
    if door is not None:
        gates_left = any(e.alive
                         for e in room._entity_by_kind.get('fancy_door', []))
        if not gates_left:
            room.kill_entity(door)
            room._on_entity_destroyed(door)
            msgs.append('The last word is spoken — the vault door swings wide!')
        elif (abs(door.row - player.row) + abs(door.col - player.col) <= 2
                and not getattr(room, '_ov_vault_hinted', False)):
            room._ov_vault_hinted = True
            msgs.append('The vault holds while a gate above still stands shut.')
    return msgs


def _wm_row_text(room, r: int) -> str:
    """The full text of row r (spaces where no character sits)."""
    line = [' '] * room.cols
    for ru in room._char_runs_by_row.get(r, []):
        for k, sym in enumerate(ru.symbols):
            if 0 <= ru.col + k < room.cols:
                line[ru.col + k] = sym
    return ''.join(line)


def _drop_spec(ent) -> tuple:
    """`drops` parsed: ('floor_key', 'gold') from 'floor_key:gold'. ('', '') if
    the field is empty or names something outside `world.DROPPABLE` — the runtime
    honours the same allowlist the validator enforces, so a file that slipped past
    an older validator still cannot hatch anything here."""
    kind, _, tag = (ent.drops or '').partition(':')
    kind = canonical_kind(kind)
    return (kind, tag) if kind in DROPPABLE else ('', '')


def _drop_tick(room, player) -> list:
    """Leave behind what the dead were carrying — the generic form of a rule the
    game had written twice, incompatibly.

    `_on_kill` had a literal `level == 'goblin_gauntlet'` branch, which only fires
    on `x` combat: a goblin cut down with `dw` dropped nothing, because an editing
    delete never reaches that hook. The Operator's Vault did it the durable way
    instead — a per-turn tick recomputed from who is alive right now. This is that
    way, generalised off goblins and out of the level table, so an author can hang
    a drop on a zombie, a wanderer or a Warden with the same field.

    STATELESS, hence undo-safe (the vault-tick principle): the drop is a statement
    about the current roster, not an event that fired. Undo revives the creature
    and takes its snapshot of the room back — the key goes with it — and re-killing
    lays the key down again. Nothing is remembered, so nothing can desync.

    A `group` makes the drop conditional on the WHOLE group being down; without
    one, each creature answers for itself. The landing cell is the dead members'
    own positions in (row, col) order, which is derived from the file rather than
    from whichever one happened to die last — so the key falls in the same place
    for every player, and in the same place after an undo.
    """
    msgs = []
    # A carrier that has ALREADY left its drop is done — even if the thing it
    # dropped is now gone from the world (picked up and then spent, e.g. a key
    # pasted onto a lock). Without this the tick, recomputing from the roster,
    # sees no key lying about and no key held and lays a fresh one down every
    # turn, at the dead carrier's cell — the "a key keeps appearing where the
    # goblin died" bug. `dropped` rides the entity through undo, so reviving the
    # carrier clears it and re-killing drops afresh.
    carriers = [e for e in room.entities if _drop_spec(e)[0] and not e.dropped]
    if not carriers:
        return msgs
    held = _held_key(player)
    held_tag = held.get('tag', '') if held is not None else None
    groups: dict = {}
    for e in carriers:
        groups.setdefault((e.group or f'#{e.row},{e.col}'), []).append(e)

    for members in groups.values():
        if any(e.alive for e in members):
            continue
        kind, tag = _drop_spec(members[0])
        # Still lying about, or in the player's hands? Then this tick has nothing
        # to add. (The `dropped` mark above is what covers the third case — spent.)
        if any(e.alive and e.kind == kind and e.tag == tag for e in room.entities):
            continue
        if kind == 'floor_key' and held_tag == tag:
            continue
        for e in sorted(members, key=lambda e: (e.row, e.col)):
            if not room.entity_at(e.row, e.col):
                room.add_entity(Entity(kind=kind, row=e.row, col=e.col, tag=tag))
                msgs.append(_DROP_BANNER.get(kind, 'Something falls from the fallen.'))
                for m in members:
                    m.dropped = True         # the deed is done — do not respawn it
                break
    return msgs


#: What the room says when a drop lands. Keyed by kind so the line describes the
#: THING, not the level — an author gets the right sentence without writing one.
_DROP_BANNER = {
    'floor_key':       'The last of them falls — a key clatters to the floor.  🗝',
    'chest_random':    'The last of them falls, and a chest is left standing.',
    'chest_key':       'The last of them falls, and a chest is left standing.',
    'heart_container': 'The last of them falls — something quick and red is left behind.',
    'gold':            'The last of them falls, and coin spills across the stone.',
    'dynamite':        'The last of them falls, and drops what it was going to use.',
}


def _seal_region_text(room, seal) -> str:
    """The text standing in a seal's region, whitespace-normalised.

    FLOOR and CORRIDOR cells only — the same restriction every hardcoded
    text-match door in the game already applies, and for the same reason: the
    target word is usually written on a plaque set into the wall beside the door,
    and a scan that read the wall would find the door already satisfied by its own
    label. An author who selects a strip that happens to include a plaque gets the
    behaviour they wanted without knowing why.
    """
    r1, c1, r2, c2 = seal.region
    out = []
    for r in range(max(0, r1), min(room.rows, r2 + 1)):
        line = [' '] * room.cols
        for ru in room._char_runs_by_row.get(r, []):
            for k, sym in enumerate(ru.symbols):
                c = ru.col + k
                if 0 <= c < room.cols and room.cells[r][c] in _WM_FLOORS:
                    line[c] = sym
        out.append(''.join(line[max(0, c1):c2 + 1]))
    return ' '.join(' '.join(t.split()) for t in out).strip()


def _seal_row_reads_true(seal, target, raw) -> bool:
    """Does ONE raw floor row satisfy ONE anyrow target? Three readings:

      at    — the PIN law: the target's first glyph stands exactly at this
              column, and whatever sits WEST of it is invisible (the plumb-
              line family — i+junk shoving a word onto the register is a
              legal route, because junk never moved the word off its pin).
      head  — the MARGIN law: the row's first glyph sits exactly at this
              column; exact then wants the whole row there, contains the
              phrase east of it (the left-align law — the << door).
      none  — plain exact / contains over the whole raw row."""
    if seal.at >= 0:
        return raw[seal.at:seal.at + len(target)] == target
    if seal.head >= 0:
        if len(raw) - len(raw.lstrip()) != seal.head:
            return False
        return raw.strip() == target if seal.mode == 'exact' \
            else target in raw[seal.head:]
    return (target in raw) if seal.mode == 'contains' else (raw.strip() == target)


def _seal_anyrow_reads(seal, rows) -> bool:
    """EVERY of a seal's targets reads true — each on its OWN row.

    The distinctness is the point, not a technicality: a door wanting a verse
    on TWO rows (the Gauntlet's Y p proof) is match=(verse, verse) — one verse
    satisfying both targets would be one proof counted twice. Different words
    can never share a row anyway, so single-target and unlike-target seals
    read exactly as they always did."""
    if not seal.match:
        return True          # pure conjunction; only its requires speaks
    cand = [[i for i, raw in enumerate(rows)
             if _seal_row_reads_true(seal, t, raw)] for t in seal.match]
    # A system of distinct representatives: assign targets to rows so no two
    # share. Kuhn's algorithm — k targets against room.rows candidates, tiny.
    taken = {}                                       # row index -> target index

    def augment(i, seen):
        for r in cand[i]:
            if r in seen:
                continue
            seen.add(r)
            if r not in taken or augment(taken[r], seen):
                taken[r] = i
                return True
        return False

    return all(augment(i, set()) for i in range(len(cand)))


def _braziers_in(room, region) -> list:
    """The live braziers standing inside a seal's rectangle."""
    r1, c1, r2, c2 = region
    return [e for e in room.entities if e.alive and e.kind == 'brazier'
            and r1 <= e.row <= r2 and c1 <= e.col <= c2]


def _seal_reads_true(room, seal, truths=(), rows=None) -> bool:
    """Every target reads true, AND every seal this one requires does too."""
    if seal.mode == 'braziers':
        # The brazier gate: open only while EVERY brazier in the region burns.
        # Snuffing one (a cut darkens a brazier, it is not carried off) leaves it
        # standing but cold, so `all(lit)` fails and the bolt re-bars — the run is
        # lost until it is relit. An empty region never opens (nothing to light).
        brz = _braziers_in(room, seal.region)
        if not brz or not all(e.lit for e in brz):
            return False
        return all(truths[i] for i in seal.requires if i < len(truths))
    if seal.mode == 'gone':
        # The legion gate: open only while NO live entity of a named kind
        # stands anywhere in the room. Like the brazier gate it reads the
        # ENTITY layer, not the buffer — and like every seal it is recomputed
        # each turn, so `u` restoring a slain goblin re-bars the bolt.
        for kind in seal.match:
            if any(e.alive for e in room._entity_by_kind.get(kind, ())):
                return False
        return all(truths[i] for i in seal.requires if i < len(truths))
    if rows is None:
        rows = [_wla_floor_text(room, r) for r in range(room.rows)]
    # Row-agnostic on purpose: charwise edits do not shift rows, but `dd`,
    # `J`, `o` and `p` all do, and a door that named a row number would be
    # undone by the first line removed above it.
    if seal.scope == 'anyrow':
        if not _seal_anyrow_reads(seal, rows):
            return False
    else:
        for t in seal.match:
            want = ' '.join(t.split())
            have = _seal_region_text(room, seal)
            ok = (want in have) if seal.mode == 'contains' else (have == want)
            if not ok:
                return False
    return all(truths[i] for i in seal.requires if i < len(truths))


def _seal_cells(room, seal) -> tuple:
    """Where a seal's door actually IS this turn — see `Seal.anchor`."""
    if seal.anchor == 'exit_row' and room.exit_pos:
        return tuple((room.exit_pos[0], c) for (_r, c) in seal.opens)
    return seal.opens


def _seal_tick(room, player) -> list:
    """The text-match doors (`room.seals`) — the plaque rule, made into data.

    This is the ONE tick behind every content gate that is a reading of the
    buffer: the ten exact-text chassis levels, the seven substring-label ones,
    and anything an author declares in a file. A bolt stands open exactly while
    its seal reads true, and is re-barred the instant it does not. Seals are
    evaluated in order so that a `requires` can only look backwards, which is
    what makes the final seal a one-pass conjunction with no cycle to guard
    against. No-ops on a room with no seals.
    """
    msgs = []
    if not room.seals:
        return msgs
    rows = [_wla_floor_text(room, r) for r in range(room.rows)]
    # Band every seal cell so a shut bolt reads as stonework rather than blank
    # wall. Derived each tick, never authoritative — see Room.sealed_cells.
    room.sealed_cells = {rc for s in room.seals for rc in _seal_cells(room, s)}
    truths = []
    for seal in room.seals:
        true_now = _seal_reads_true(room, seal, truths, rows)
        truths.append(true_now)
        opened  = False
        for (r, c) in _seal_cells(room, seal):
            if not (0 <= r < room.rows and 0 <= c < room.cols):
                continue
            if true_now and room.cells[r][c] != CellType.FLOOR:
                # A bolt that reads true HOLDS its cell as walkable stone,
                # whatever drifted onto it — the Inscription Halls' river can
                # slide through an opened gate row while its last word is
                # still being typed; an open door is floor, not a pond.
                room.cells[r][c] = CellType.FLOOR
                opened = True          # ONE banner per seal, however wide the door
            elif not true_now and room.cells[r][c] != CellType.WALL \
                    and (player.row, player.col) != (r, c):
                # Never re-wall the cell the player is standing in: the annex
                # doors have carried this guard since they were written, because
                # sealing someone inside stone is not a puzzle, it is a crash.
                room.cells[r][c] = CellType.WALL
        if opened:
            msgs.append(seal.message or SEAL_OPENED)
    return msgs


def _wla_floor_text(room, r: int) -> str:
    """Row r's text restricted to FLOOR/CORRIDOR cells — the Change Annex's
    door scans must read what stands WRITTEN on walkable stone, never the
    plaques (verdant targets set in the wall cells of the door rows)."""
    line = [' '] * room.cols
    for ru in room._char_runs_by_row.get(r, []):
        for k, sym in enumerate(ru.symbols):
            c = ru.col + k
            if 0 <= c < room.cols and room.cells[r][c] in _WM_FLOORS:
                line[c] = sym
    return ''.join(line)


def _ce_y_plaque_tick(room, player) -> list:
    """The Change Extension's Y hall: after `Yp` inserts the echo row, the row-
    shift bumps the second-verse plaque down one; slide it back with the restore
    twinkle (the Sculpting glitter, ported to the paste).

    All this level's DOORS are seals now (`_seal_tick`); what is left here is
    the one thing that is not a reading of the buffer but a rearrangement of it.
    """
    if getattr(room, '_ce_y_stump', None):
        moved = _ce_realign_y_plaque(room)
        if moved:
            room._sc_twinkle = moved
    return []


def _ce_realign_y_plaque(room) -> list:
    """Keep the Y hall's second-verse plaque one row below the first-half line
    (the echo's landing). A `Yp`/`YP` paste inserts a row and _shift_rows drifts
    the plaque; re-lay it onto its slot and return the move so the render layer
    can TWINKLE it (the guidance visibly following the paste). The first-half
    row is the anchor — found by its stump, so this is shift-proof. STATELESS:
    undoing the paste drops the row and the plaque settles back with no drift."""
    stump = getattr(room, '_ce_y_stump', None)
    if not stump:
        return []
    fool_rows = [r for r in range(room.rows) if stump in _wla_floor_text(room, r)]
    if not fool_rows:
        return []
    y_row = min(fool_rows)
    want = y_row + 1
    if not (0 <= want < room.rows):
        return []
    # the Y plaque = the verdant runs at/below the Y row (door prefixes all sit
    # ABOVE it, on the lesson rows), so they are never mistaken for it.
    plaque = [ru for ru in room.char_runs if ru.kind == 'verdant' and ru.row >= y_row]
    if not plaque or all(ru.row == want for ru in plaque):
        return []
    moved = []
    for ru in plaque:
        moved.append((ru.row, want, ru.col, ru.symbols))
        room.char_runs.remove(ru)
        room.char_runs.append(CharRun(want, ru.col, ru.symbols, ru.kind))
    room.rebuild_indexes()
    return moved


def _codex_feed(player, key):
    """One keystroke into the open Codex pane (:help semantics — the pane has
    focus). Motions over visible rows (a closed fold is ONE line), za/zR/zM
    folds, / ? n N search, and :q to close the window. Everything is free."""
    pane = player.codex_pane
    k = str(key)

    # active /search input
    if pane.search_input is not None:
        if key.name == 'KEY_ESCAPE':
            pane.search_input = None
        elif key.name == 'KEY_ENTER' or k in ('\n', '\r'):
            pat = pane.search_input
            pane.search_input = None
            if not pane.search(pat):
                pane.message = f'E486: Pattern not found: {pat or pane.search_pat}'
        elif key.name == 'KEY_BACKSPACE' or k == '\x7f':
            pane.search_input = pane.search_input[:-1]
        elif not key.is_sequence:
            pane.search_input += k
        return

    # active :command input
    if pane.cmd_input is not None:
        if key.name == 'KEY_ESCAPE':
            pane.cmd_input = None
        elif key.name == 'KEY_ENTER' or k in ('\n', '\r'):
            cmd = pane.cmd_input.strip()
            pane.cmd_input = None
            if cmd in ('q', 'q!', 'wq', 'x'):
                player.codex_pane = None       # :q closes the WINDOW (Vim-true)
            else:
                pane.message = f'E492: Not a codex command: {cmd}'
        elif key.name == 'KEY_BACKSPACE' or k == '\x7f':
            pane.cmd_input = pane.cmd_input[:-1]
        elif not key.is_sequence:
            pane.cmd_input += k
        return

    pane.message = ''
    if key.is_sequence and key.name not in ('KEY_ESCAPE',):
        return
    pending = getattr(pane, '_pending', '')
    count   = getattr(pane, '_count', '')

    if pending == 'z':
        pane._pending = ''
        if k == 'a':
            pane.toggle_fold()
        elif k == 'R':
            pane.open_all()
        elif k == 'M':
            pane.close_all()
        return
    if pending == 'g':
        pane._pending = ''
        if k == 'g':
            pane.to_top()
        return

    if k.isdigit() and (k != '0' or count):
        pane._count = count + k
        return
    n = int(count) if count else 1
    pane._count = ''

    if k == 'j':
        pane.move(n)
    elif k == 'k':
        pane.move(-n)
    elif k == 'G':
        pane.to_bottom()
    elif k in ('z', 'g'):
        pane._pending = k
    elif k == '/':
        pane.search_input = ''
    elif k == 'n':
        pane.search('')
    elif k == 'N':
        pane.search('', backward=True)
    elif k == ':':
        pane.cmd_input = ''


def _hall_of_echoes_tick(room, player) -> list:
    """The Hall of Echoes gauntlet — chambers are RUNS of text rows split by
    stone bands. `room._heg_chain` holds one (done-texts, head-col) spec per
    chamber, in map order; each intermediate band's west gate grinds open
    while its chamber reads true, and the final seal (room.exit_pos)
    demands EVERY chamber true. STATELESS + undo-aware; runs are re-derived
    each tick, so J-collapses and dd-culls ride correctly (rows shift, the
    bands shift with them)."""
    chain = getattr(room, '_heg_chain', None)
    if chain is None:
        return []
    msgs = []
    runs, cur = [], []
    for r in range(room.rows):
        t = _wla_floor_text(room, r)
        if t.strip():
            cur.append((r, t))
        elif cur:
            runs.append(cur)
            cur = []
    if cur:
        runs.append(cur)
    oks = []
    for k, spec in enumerate(chain):
        texts, colreq = spec[0], spec[1]
        combat = spec[2] if len(spec) > 2 else False
        if k >= len(runs):
            oks.append(False)
            continue
        if combat:
            # the goblin lair reads true when every foe on its row is felled
            rows_k = {r for r, _t in runs[k]}
            ok = not any(e.alive and e.kind == 'goblin' and e.row in rows_k
                         for e in room.entities)
        else:
            got = tuple(t.strip() for _r, t in runs[k])
            ok = got == tuple(texts)
            if ok and colreq is not None:
                ok = all(len(t) - len(t.lstrip()) == colreq for _r, t in runs[k])
        oks.append(ok)
    gcol = _dg._HE_GATE_COL
    # Band the live gates as stonework. Derived here, not at build: the bands
    # ride the row shifts, so each gate row is re-read from the live runs.
    room.sealed_cells = set()
    for k in range(min(len(chain) - 1, len(runs))):    # intermediate gates
        gr = runs[k][-1][0] + 1
        if gr >= room.rows - 1:
            continue
        room.sealed_cells.add((gr, gcol))
        is_open = room.cells[gr][gcol] != CellType.WALL
        if oks[k] and not is_open:
            room.cells[gr][gcol] = CellType.FLOOR
            msgs.append('The chamber rings true — the way south grinds open!')
        elif not oks[k] and is_open and (player.row, player.col) != (gr, gcol):
            room.cells[gr][gcol] = CellType.WALL       # undone — it re-bars
    er, ec = room.exit_pos
    if not (0 <= er < room.rows):
        return msgs                    # a mangled buffer — never crash the tick
    room.sealed_cells.add((er, ec))                     # the final seal
    all_ok = len(runs) == len(chain) and all(oks)
    is_open = room.cells[er][ec] != CellType.WALL
    if all_ok and not is_open:
        room.cells[er][ec] = CellType.FLOOR
        msgs.append('Every hall rings true — the last seal parts!')
    elif not all_ok and is_open and (player.row, player.col) != (er, ec):
        room.cells[er][ec] = CellType.WALL             # undone — it returns
    return msgs


def _paragraph_enclosure_tick(room, player) -> list:
    """The Warden's Sigil — the Paragraph Enclosure's seal. Six brazier
    flames ride the three rows that must survive (spawn row · the rest
    between the cantos · the gate row); when exactly the right paragraphs
    fall, the survivors stack into the sigil (▲ / ▲ ▲ / ▲ ▲ ▲) and the
    seal parts, provided no goblin still stands. The win condition is
    VISIBLE: a cut through a wrong row extinguishes its flames — the cut
    itself succeeds (no un-Vim parrying), the hole in the sigil shows what
    went wrong, and undo relights it. STATELESS + undo-aware (the seal
    re-walls), the hardened-chassis pattern; entity rows shift with the
    collapses, so the check is pure geometry on live positions."""
    msgs = []
    legion = any(e.alive for e in room._entity_by_kind.get('goblin', []))
    flames = [e for e in room._entity_by_kind.get('brazier', []) if e.alive]
    sigil = False
    if len(flames) == 6:
        tops = [e for e in flames if e.row == min(f.row for f in flames)]
        if len(tops) == 1:
            r0, c0 = tops[0].row, tops[0].col
            from vimny.generation.dungeon_gen import _PE_SIGIL
            sigil = ({(e.row, e.col) for e in flames}
                     == {(r0 + dr, c0 + dc) for dr, dc in _PE_SIGIL})
    all_true = sigil and not legion
    er, ec = room.exit_pos
    # Band the shut seal as stonework; derived here because exit_pos rides the
    # paragraph collapses.
    room.sealed_cells = {(er, ec)}
    seal_open = room.cells[er][ec] != CellType.WALL
    if all_true and not seal_open:
        room.cells[er][ec] = CellType.FLOOR
        msgs.append('The legion is fallen and the six flames stand as one '
                    'sign — the seal parts!')
    elif not all_true and seal_open and (player.row, player.col) != (er, ec):
        room.cells[er][ec] = CellType.WALL         # undone — the seal returns
    return msgs


def _grandmasters_arena_tick(room, player) -> list:
    """The Unmaking (arena, room 1): the Grandmaster is the master of the
    written word — edit_immune, unkillable by blade. He is woven from six
    strands, each a text object on a lectern (room._gm_lecterns), and he
    STARTS inside one. Shear a strand with its object (di" di( di{ dit dis
    diw) — in ANY order — and it empties while the structure survives (a
    whole-line dd wipes the marker too and does NOT count). Whenever you
    close on him (within 2 cells) or land on his cell — a / search onto his
    W, say — he SLIPS into another strand still standing (the farthest from
    you). Empty all six and the last strand parts: he is unmade and the
    sanctum seal opens. Stateless (HP derives from the floor each tick, so
    undo restores a strand and his health together); no fixed route."""
    msgs = []
    lecterns = getattr(room, '_gm_lecterns', None)
    if not lecterns:
        return msgs
    # Band the shut sanctum seal as stonework. Derived here rather than at build
    # time because the seal rides exit_pos through the row shifts.
    sc0 = getattr(room, '_gm_seal_col', None)
    room.sealed_cells = {(room.exit_pos[0], sc0)} if sc0 is not None else set()
    blob = ' '.join(_wla_floor_text(room, r) for r in range(room.rows))

    def sheared(lc):                         # inner gone, the structure kept —
        return lc['gone'] not in blob and lc['keep'] in blob   # a dd wipes both
    count = sum(sheared(lc) for lc in lecterns)
    gm = next((e for e in room.entities
               if e.kind == 'warden' and e.tag == 'grandmaster' and e.alive), None)
    if gm is None:
        return msgs
    gm.max_hp = len(lecterns)
    gm.hp     = max(1, len(lecterns) - count)     # 1 while a strand stands

    # He slips away when you crowd him (approach or land on his cell), or if
    # the strand he sits in was somehow emptied — always INTO another strand.
    crowded = max(abs(gm.row - player.row), abs(gm.col - player.col)) <= 2
    on_dead = any(sheared(lc) and lc['cursor'] == (gm.row, gm.col)
                  for lc in lecterns)
    if count < len(lecterns) and (crowded or on_dead):
        far, best = None, -1
        for lc in lecterns:                       # slip to the standing strand
            if sheared(lc):                        # farthest from the player
                continue
            g = lc['cursor']                       # a cell INSIDE the structure
            if g in ((gm.row, gm.col), (player.row, player.col)):
                continue
            if room.cells[g[0]][g[1]] == CellType.WALL:
                continue
            d = abs(g[0] - player.row) + abs(g[1] - player.col)
            if d > best:
                best, far = d, g
        if far is not None:
            room.move_entity(gm, far[0], far[1])
            if crowded:
                msgs.append('You reach for him — and he slips into another strand.')

    if count >= len(lecterns):                     # the unmaking
        room.kill_entity(gm)
        sc = getattr(room, '_gm_seal_col', None)
        if sc is not None:
            room.cells[room.exit_pos[0]][sc] = CellType.FLOOR
        msgs.append('The last strand parts. The Grandmaster is unmade — '
                    'the sanctum opens.')
    return msgs


def _warden_eternal_tick(room, player) -> list:
    """The Warden Eternal (final boss): the six-warden descent, then the
    Unmasking. Each chamber's stone band opens its spine passage once every
    'eternal'-tagged foe in that chamber's rows is dead (and reveals the
    chamber below). When the player reaches the finale the wizard unmasks —
    the W was the Warden all along — and the horde is loosed. The seal to the
    exit parts only when the Warden AND his whole horde are dead; he leaves
    his hat on the stone (player.has_hat, persisted on the win-save). Stateless
    per turn, so undo restores the world and the gates together. par=None."""
    msgs = []
    gates = getattr(room, '_wde_gates', None)
    if gates is None:
        return msgs
    if room.rows < _dg._WDE_ROWS:
        # The floor has been dug clean away (dG and the like collapsed rows out
        # from under the arena). A NetHack/Dwarf-Fortress wink instead of a crash
        # — there is nothing left to stand on, so the run is void.
        if not getattr(room, '_floor_gone', False):
            room._floor_gone = True
            msgs.append('You have dug too greedily and too deep — there is no '
                        'floor left here. Type  :e  to reload the dungeon.')
        return msgs

    # Band the chamber bands + the exit seal as stonework. Kept in the tick so
    # a dug-away floor simply drops the out-of-range cells from the set.
    seal0 = getattr(room, '_wde_seal', None)
    room.sealed_cells = {(g['band'], g['col']) for g in gates
                         if g['band'] < room.rows and g['col'] < room.cols}
    if seal0 and seal0['col'] < room.cols:
        room.sealed_cells |= {(r, seal0['col']) for r in seal0['rows']
                              if r < room.rows}

    # 1) open each cleared chamber's passage, revealing the chamber below
    for g in gates:
        band, col = g['band'], g['col']
        if room.cells[band][col] != CellType.WALL:
            continue
        top, bot = g['rows']
        if any(e.alive and e.tag == 'eternal' and top <= e.row <= bot
               for e in room.entities if e.kind in ('warden', 'goblin')):
            continue
        room.cells[band][col] = CellType.FLOOR
        rev = g.get('reveal')
        if rev:
            rtop, rbot, _b = rev
            room.fog_cells = {(fr, fc) for (fr, fc) in room.fog_cells
                              if not (rtop <= fr <= rbot)}
        room.rebuild_indexes()
        msgs.append('The stone grinds aside — the way down opens.')

    # 2) the Unmasking, when the player steps into the finale hall
    if not getattr(room, '_wde_revealed', False) and player.row >= _dg._WDE_FINALE_TOP:
        room._wde_revealed = True
        room.fog_cells = {(fr, fc) for (fr, fc) in room.fog_cells
                          if fr < _dg._WDE_FINALE_TOP}
        room.rebuild_indexes()
        msgs.append('The wizard lowers his hood — and it is the Warden, who '
                    'blessed your every step. "Now," he breathes. "Show me."')

    # 3) the seal parts when the Warden AND his whole horde are dead — and he
    #    LEAVES HIS HAT on the stone where he fell (a lootable Δ the player
    #    walks over on the way out; picking it up is step 4).
    seal = getattr(room, '_wde_seal', None)
    if seal and (seal['rows'][0] >= room.rows or seal['col'] >= room.cols):
        # The arena floor has been dug clean away (dG and the like collapsed the
        # rows out from under the seal). A NetHack/Dwarf-Fortress wink instead of
        # a crash — there is nothing left to stand on, so the run is void.
        if not getattr(room, '_floor_gone', False):
            room._floor_gone = True
            msgs.append('You have dug too greedily and too deep — there is no '
                        'floor left here. Type  :e  to reload the dungeon.')
    elif seal and room.cells[seal['rows'][0]][seal['col']] == CellType.WALL:
        boss = next((e for e in room.entities
                     if e.tag == room._wde_boss_tag and e.alive), None)
        horde = any(e.alive for e in room.entities if e.kind == 'goblin')
        if boss is None and not horde:
            for r in seal['rows']:
                if r < room.rows:
                    room.cells[r][seal['col']] = CellType.FLOOR
            drop = getattr(room, '_wde_hat_drop', (seal['rows'][len(seal['rows']) // 2],
                                                   seal['col'] - 7))
            if not any(e.kind == 'hat' for e in room.entities):
                room.entities.append(Entity(kind='hat', row=drop[0], col=drop[1]))
            room.rebuild_indexes()
            msgs.append("The Warden falls still at last, and lays his hat upon "
                        "the stone. The way out is open — x the hat to take it up.")
    # (The hat is looted with x / dl like any other item — see the interact block.)
    return msgs


def _gauntlet_tick(room, player) -> list:
    """The Gauntlet's goal-column band — the one thing here that is not a
    reading of the buffer but a rearrangement of it. Every DOOR is a file
    riding `Seal` now (`_seal_tick`): sub → contains-anyrow, row →
    exact-anyrow, dup → the target twice (distinct-row law), col → head=TX,
    and the exit behind them all via `requires`.

    What remains: the west wall paints the FINISHED manuscript relative to
    the yanked line — that line TWICE, the O verse two below its head, the o
    verse five below. Row inserts (Y-p / O / o) shift the wall plaques with
    the world; this re-rights them to the goal rows — the sculpting
    re-align, with its twinkle (room._sc_twinkle is read by the render loop)."""
    msgs: list = []
    floor_rows = [_wla_floor_text(room, r) for r in range(room.rows)]
    stripped = [t.strip() for t in floor_rows]

    band = getattr(room, '_gnt_band', None)
    if band:
        yline, ow1, ow2, nkw = band
        anchor = next((r for r, t in enumerate(stripped) if t == yline), None)
        if anchor is not None:
            spine = _dg._GNT_SPINE
            want: dict = {}
            for dr, t in ((0, yline), (1, yline), (2, ow1), (3, ow2),
                          (5, nkw)):
                if anchor + dr < room.rows:
                    want.setdefault(t, []).append(anchor + dr)
            have: dict = {}
            runs_at: dict = {}
            for r in range(room.rows):
                runs = sorted((ru for ru in room._char_runs_by_row.get(r, [])
                               if ru.kind == 'verdant' and ru.col < spine),
                              key=lambda ru: ru.col)
                if not runs:
                    continue
                text = ' '.join(''.join(ru.symbols) for ru in runs)
                if text in (yline, ow1, ow2, nkw):
                    have.setdefault(text, []).append(r)
                    runs_at[r] = runs
            if have != want:
                moved = []
                for t, rows_w in want.items():
                    rows_h = have.get(t, [])
                    for i, nr in enumerate(rows_w):
                        old = rows_h[i] if i < len(rows_h) else nr
                        if old != nr:
                            moved.append((old, nr, _dg._GNT_PLQ_COL, tuple(t)))
                for rows_h in have.values():
                    for r in rows_h:
                        for ru in runs_at.get(r, ()):
                            room.remove_char_run(ru)
                for t, rows_w in want.items():
                    for nr in rows_w:
                        c = _dg._GNT_PLQ_COL
                        for part in t.split(' '):
                            if part:
                                room.add_char_run(CharRun(nr, c, tuple(part),
                                                          'verdant'))
                            c += len(part) + 1
                if moved:
                    room._sc_twinkle = moved
    return msgs


def _indentation_sanctum_tick(room, player) -> list:
    """The Indentation Sanctum bolts. Gallery bolts are the Alignment rule (a
    noun seated at the plumb register, exact col, any floor row). The RITE
    bolt calls the SAME `law_column` the `=` operator applies — every rite
    row's text intact and standing exactly where the law reads — so the
    solver and the judge can never drift. Row-agnostic via the rite's anchor
    line, STATELESS + FINAL SEAL (the hardened-chassis pattern)."""
    msgs = []
    reg = room._is_register
    floor_rows = [_wla_floor_text(room, r) for r in range(room.rows)]

    def seated(word):
        return any(t[reg:reg + len(word)] == word for t in floor_rows)

    def rite_lawful():
        texts = room._is_rite_texts
        anchor = next((r for r, t in enumerate(floor_rows)
                       if t.strip() == texts[0]), None)
        if anchor is None or anchor + len(texts) > room.rows:
            return False
        for k, expect in enumerate(texts):
            r = anchor + k
            line = floor_rows[r]
            if line.strip() != expect:
                return False
            start = len(line) - len(line.lstrip())
            if law_column(room, r) != start:
                return False
        return True

    gr = room.exit_pos[0]
    # Band the live bolts + final seal as stonework. Derived here rather than at
    # build time because `gr` rides the rite's row shifts.
    room.sealed_cells = {(gr, dc) for dc in room._is_bolts}
    room.sealed_cells.add(room.exit_pos)
    conditions = (all(seated(w) for w in room._is_g1_words),
                  all(seated(w) for w in room._is_g2_words),
                  rite_lawful())
    for ok, dc in zip(conditions, room._is_bolts):
        is_open = room.cells[gr][dc] != CellType.WALL
        if ok and not is_open:
            room.cells[gr][dc] = CellType.FLOOR
            msgs.append('The bay stands as the law reads — the bolt grinds back!')
        elif not ok and is_open and (player.row, player.col) != (gr, dc):
            room.cells[gr][dc] = CellType.WALL     # disturbed — the bolt re-bars
    er, ec = room.exit_pos
    seal_open = room.cells[er][ec] != CellType.WALL
    if all(conditions) and not seal_open:
        room.cells[er][ec] = CellType.FLOOR
        msgs.append('Every bay obeys its law — the final seal parts!')
    elif not all(conditions) and seal_open and (player.row, player.col) != (er, ec):
        room.cells[er][ec] = CellType.WALL         # undone — the seal returns
    return msgs


def _sc_leading_verse(room, r: int, c0: int, c1: int) -> str:
    """The leftmost verse WRITTEN on floor within the band [c0, c1] of row r —
    the first whitespace-delimited token of the floor text. The A-breach glyphs
    sit east of a bare-floor gap, so the seal line still leads with 'seal'."""
    return next(iter(_wla_floor_text(room, r)[c0:c1 + 1].split()), '')


def _sc_seal_row(room, c0: int, c1: int):
    """The row whose floor verse leads with the votive's ANCHOR (the line
    whose HEAD is given from build — 'merrily' in the Row Your Boat tablet);
    the tablet's other slots are relative to it."""
    idx = getattr(room, '_sc_anchor', 1)
    anchor = getattr(room, '_sc_target', ('', 'seal'))[idx]
    return next((r for r in range(room.rows)
                 if _sc_leading_verse(room, r, c0, c1) == anchor), None)


def _sc_realign_plaques(room) -> list:
    """Keep each WEST-wall plaque on the SAME row as the verse it names — o/O row-
    inserts drift them, so re-lay any that moved and return those cells so the
    render layer can TWINKLE them (the guidance visibly follows the engine). Slots
    are relative to the 'seal' anchor verse on the floor, so this is shift-proof."""
    target = getattr(room, '_sc_target', ())
    c0, c1 = room._sc_band
    seal_row = _sc_seal_row(room, c0, c1)
    if seal_row is None:
        return []
    base = getattr(room, '_sc_anchor', 1)  # the anchor line's index in the votive
    slot = {w: seal_row + (target.index(w) - base) for w in target}
    moved = []
    for ru in [r for r in room.char_runs if r.kind == 'verdant']:
        word = (''.join(ru.symbols).split() or [''])[0]
        want = slot.get(word)
        if want is None or not (0 <= want < room.rows) or ru.row == want:
            continue
        old_row = ru.row
        room.char_runs.remove(ru)
        room.char_runs.append(CharRun(want, ru.col, ru.symbols, ru.kind))
        moved.append((old_row, want, ru.col, ru.symbols))   # slide old→new, then re-ink
    if moved:
        room.rebuild_indexes()
    return moved


def _sculpting_chambers_tick(room, player) -> list:
    """The Sculpting Chambers votive: the vault door (a single gated cell at
    room.exit_pos) unseals exactly while the tablet READS TRUE — the leading verse
    of each inscribed row, top to bottom, equals the target (keep · seal · sesame
    · amen) AND the seal row's second token is the carved word (`hew`). Each turn
    the plaques RE-ALIGN to their verses (o/O drift them) and twinkle. Text- and
    exit_pos-relative, so it rides the row shifts o/O/I cause (the Manifold
    discipline); STATELESS, hence undo-safe (undoing a verse re-seals the door)."""
    target = getattr(room, '_sc_target', ())
    if not target:
        return []
    moved = _sc_realign_plaques(room)
    if moved:
        room._sc_twinkle = moved       # the render layer sparkles the re-laid plaques
    c0, c1 = room._sc_band
    lines = getattr(room, '_sc_lines', None)
    if lines:
        # The FULL-POEM tablet: every inscribed row's floor text, top to
        # bottom, must equal its line word for word (the A launch cell is a
        # single bare col, so token-joining normalises it away).
        seq = [' '.join(_wla_floor_text(room, r)[c0:c1 + 1].split())
               for r in range(room.rows)]
        done = [t for t in seq if t] == list(lines)
    else:
        seq = [v for v in (_sc_leading_verse(room, r, c0, c1) for r in range(room.rows)) if v]
        votive = tuple(seq) == tuple(target)
        carve = getattr(room, '_sc_carve', '')
        seal_row = _sc_seal_row(room, c0, c1)
        toks = _wla_floor_text(room, seal_row)[c0:c1 + 1].split() if seal_row is not None else []
        carved = bool(carve) and len(toks) >= 2 and toks[1] == carve
        done = votive and carved
    er, ec = room.exit_pos
    # Band the shut vault door as stonework; derived here because exit_pos rides
    # the o/O/I row shifts.
    room.sealed_cells = {(er, ec)}
    is_open = room.cells[er][ec] != CellType.WALL
    if done and not is_open:
        room.cells[er][ec] = CellType.FLOOR
        return ['The votive reads true, the stone is hewn — the vault door grinds open!']
    if not done and is_open and (player.row, player.col) != (er, ec):
        room.cells[er][ec] = CellType.WALL         # a verse undone — the door re-seals
    return []


def _wm_ward_broken(room, k: int) -> bool:
    """Ward k's state — shift-proof by design (kind-counts on floor cells,
    substring scans across rows; never stored coordinates):
      1: every warding word is gone (no 'ancient' text on the floor)
      2: his stamp reads TRUE four times (the warped copies mended with r/.)
      3: the rot is sheared (also 'ancient' — safe by TIME, ward 1's words
         predate ward 3; NOT 'ember', which r-typed mends are repainted to)
      4: THREE rows read 🜂🜂🜂 — his stamped flame row plus two linewise
         copies (yy + p + p), the 3×3 grid. Only copying HIS row can do it:
         the fuel rule locks charwise flames to the braziers (no adjacent
         pair can be assembled by hand) and every other yankable row holds
         at most one flame.
    Floor-glyph checks use the CELL TYPE, not is_passable — fog makes a
    cell impassable, and the ward-words sleep under the hall fog until the
    ritual (an is_passable check read ward 1 as broken at level entry)."""
    if k in (1, 3):
        return not any(ru.kind == 'ancient'
                       and room.cells[ru.row][ru.col] in _WM_FLOORS
                       for ru in room.char_runs)
    if k == 2:
        word = getattr(room, '_wm_word2', None)
        if not word:
            return False
        return sum(_wm_row_text(room, r).count(word)
                   for r in range(room.rows)) >= 4
    if k == 4:
        triple = _dg._QM_FLAME * 3
        return sum(1 for r in range(room.rows)
                   if triple in _wm_row_text(room, r)) >= 3
    return False


_WM_FLOORS = (CellType.FLOOR, CellType.CORRIDOR)


def _wm_rot_cells(room) -> int:
    """Cells of 'ancient' rot standing on floor (fog-independent)."""
    return sum(len(ru.symbols) for ru in room.char_runs
               if ru.kind == 'ancient'
               and room.cells[ru.row][ru.col] in _WM_FLOORS)


def _wm_set_char(room, r: int, c: int, ch: str) -> None:
    """Overwrite one glyph in place (no reflow — the tick's own r, in effect)."""
    ru = room.char_run_at(r, c)
    if ru is not None:
        i = c - ru.col
        ru.symbols = ru.symbols[:i] + (ch,) + ru.symbols[i + 1:]


def _wm_recorrupt(room) -> int:
    """Ward 2's punishment: every TRUE copy of his stamp warps again (index 0 →
    the warp glyph). Returns how many copies blackened. Positions come from
    a per-row text snapshot, so all copies found in one pass are warped."""
    word = getattr(room, '_wm_word2', '')
    warp = getattr(room, '_wm_warp', '')
    if not word or not warp:
        return 0
    n = 0
    for r in range(room.rows):
        text = _wm_row_text(room, r)
        i = text.find(word)
        while i != -1:
            _wm_set_char(room, r, i, warp)
            n += 1
            i = text.find(word, i + len(word))
    return n


def _wm_crumble_posts(room) -> list:
    """Ward 1: a wall post crumbles once the warding word WEST of it (its own
    post-bounded segment of the ward row) is cut. Undo-safe for free: the
    pre-edit cell snapshot holds the post as WALL, so undoing the cut
    restores word and post together."""
    msgs = []
    row = _dg._WM_WARD1[0]
    lo = _dg._WM_HALL_LO
    for post in _dg._WM_WARD1_POSTS:
        if room.cells[row][post] != CellType.WALL:
            lo = post + 1
            continue
        if not any(ru.kind == 'ancient' and lo <= ru.col < post
                   for ru in room._char_runs_by_row.get(row, [])):
            room.cells[row][post] = CellType.FLOOR
            msgs.append('The warding word is cut — its post crumbles to dust!')
        lo = post + 1
    return msgs


def _wm_double_rank(room, player, spent: int) -> list:
    """Ward 3's pressure: once the rot is FIRST cut, every keystroke DOUBLES
    the rank of stamp-Wardens while any rot remains (one D never primes it —
    the rot dies whole and the stagger gutters the rank). New copies flood
    outward from the rank over free floor, deterministic BFS order."""
    cells0 = getattr(room, '_wm_rot0', None)
    if cells0 is None:
        return []
    cur = _wm_rot_cells(room)
    if cur == 0 or cur >= cells0:
        room._wm_r3_spent0 = None              # whole, or sheared — not primed
        return []
    t0 = getattr(room, '_wm_r3_spent0', None)
    if t0 is None:
        room._wm_r3_spent0 = spent
        return ['The half-cut rot SEETHES — finish it in one stroke, '
                'or he multiplies!']
    stamps = [e for e in room.entities
              if e.alive and e.kind == 'warden' and e.tag == 'stamp']
    target = min(len(_dg._WM_WARD3_RANK) * (2 ** max(0, spent - t0)), 256)
    need = target - len(stamps)
    if need <= 0 or not stamps:
        return []
    q = deque((e.row, e.col) for e in stamps)
    seen = set(q)
    placed = 0
    while q and placed < need:
        r, c = q.popleft()
        for dr, dc in ((0, 1), (0, -1), (1, 0), (-1, 0)):
            nb = (r + dr, c + dc)
            if nb in seen or not room.is_passable(*nb):
                continue
            seen.add(nb)
            q.append(nb)
            if nb == (player.row, player.col) or room.entity_at(*nb) is not None:
                continue
            room.add_entity(Entity(kind='warden', row=nb[0], col=nb[1],
                                   hp=1, max_hp=1, ai='', tag='stamp'))
            placed += 1
            if placed >= need:
                break
    if placed:
        return [f'The press ROARS — the Wardens redouble! '
                f'({len(stamps) + placed} stand)']
    return []


def _wm_bolt_cell(room, warden) -> tuple:
    """The active podium's bolt — DERIVED from the warden entity (entities
    ride row shifts), facing the aisle."""
    side = 1 if warden.row < _dg._WM_AXIS else -1
    return (warden.row + side, warden.col)


def _wm_pressure(room, player) -> list:
    """Pressure hook — deliberately empty at ship. Candidates (decide after
    the framework plays): goblin trickle between wards, echo aggression
    during edit wards, the Pathfinder's mega. Returns banner messages."""
    return []


def _wsc_alcove_pos(room, k: int) -> tuple:
    """Alcove k's niche cell, DERIVED from its GEOMETRY: scan the alcove's own
    column (columns never shift) for the niche silhouette — a non-wall cell
    walled on both sides with its back to the wall. The structure rides
    _shift_rows intact, so a mid-fight J cannot strand the re-manifest the
    way static podium coords would; the walls stay plain stone (no
    sigils). CELL-TYPE checks, not is_passable — the niche sleeps under
    fog (the Manifold law). Falls back to the build coords if a collapse
    somehow ate the silhouette."""
    col = _dg._WSC_ALCOVES[k][1]
    side = _dg._WSC_SIDES[k]
    for r in range(1, room.rows - 1):
        if (room.cells[r][col] not in (CellType.WALL,)
                and room.cells[r][col - 1] == CellType.WALL
                and room.cells[r][col + 1] == CellType.WALL
                and 0 <= r - side < room.rows
                and room.cells[r - side][col] == CellType.WALL):
            return (r, col)
    return _dg._WSC_ALCOVES[k]


def _wsc_bolt_cell(room, warden) -> tuple:
    """The active alcove's bolt — derived from the warden entity, facing the
    aisle (entities ride row shifts)."""
    side = 1 if warden.row < _dg._WSC_AXIS else -1
    return (warden.row + side, warden.col)


def _wsc_rite_lawful(room) -> bool:
    """Ward 5: the rite block stands as the LAW reads — anchored by its first
    line's text, judged with the same law_column the `=` operator applies
    (solver == judge; row-agnostic, so join-shifts cannot stale it)."""
    texts = getattr(room, '_wsc_rite', ())
    if not texts:
        return False
    floor_rows = [_wla_floor_text(room, r) for r in range(room.rows)]
    anchor = next((r for r, t in enumerate(floor_rows)
                   if t.strip() == texts[0]), None)
    if anchor is None or anchor + len(texts) > room.rows:
        return False
    for k, expect in enumerate(texts):
        line = floor_rows[anchor + k]
        if line.strip() != expect:
            return False
        start = len(line) - len(line.lstrip())
        if law_column(room, anchor + k) != start:
            return False
    return True


def _wsc_ward_broken(room, k: int) -> bool:
    """Ward k's state — ALL text-derived (substring scans across every floor
    row / the law check), so no stored coordinate can go stale under J."""
    if k == 5:
        return _wsc_rite_lawful(room)
    target = getattr(room, '_wsc_targets', {}).get(k)
    if not target:
        return False
    return any(target in _wla_floor_text(room, r) for r in range(room.rows))


def _wsc_recorrupt(room) -> int:
    """Ward 2's punishment: every mended copy of the stream re-rots (its three
    mid glyphs blacken again). Returns how many copies rotted."""
    word = getattr(room, '_wsc_word2', '')
    rot  = getattr(room, '_wsc_rot2', '')
    mid  = getattr(room, '_wsc_rotmid', 0)
    if not word or not rot:
        return 0
    n = 0
    for r in range(room.rows):
        text = _wla_floor_text(room, r)
        i = text.find(word)
        while i != -1:
            for j, ch in enumerate(rot):
                _wm_set_char(room, r, i + mid + j, ch)
            n += 1
            i = text.find(word, i + len(word))
    return n


def _warden_scrivener_tick(room, player, spent: int = 0) -> list:
    """The Unfinished Manuscript — the Warden Scrivener's ward machine (the
    Manifold press, JOIN-HARDENED: J and = are live all fight, so every ward
    check is text-derived, the bolt derives from the warden entity, the
    re-manifest alcove derives from its wall marker, and the later stamps
    are laid RELATIVE to the derived alcove row).

    THE THRESHOLD: the antechamber lintel carries a word; while it is
    written on any floor row, the gate stands open and the page's fog is
    parted (stateless — cut the word and the gate re-bars).
    THE WARDS (see _wsc_ward_broken): the Lie (c), the Rot (R, TIMED — the
    mends re-rot _WSC_W2_WINDOW keystrokes after the solve), the Voice
    (case), the Torn Page (J), the Rule (= — the act's capstone). Breaking
    the ward jams the press: echoes gutter, his bolt draws, his alcove's fog
    parts, /W finds him, one x lands — and he re-manifests at the next
    alcove and stamps the next passage. The ward counter and the rot timer
    ride the undo snapshot (the Manifold convention)."""
    msgs = []
    # Band the threshold gate + the final seal as stonework (the live alcove
    # bolt joins below, once the warden it derives from is known).
    room.sealed_cells = {c for c in (getattr(room, '_wsc_gate', None),
                                     getattr(room, '_wsc_seal', None)) if c}

    # ── the threshold: the lintel's word, written on the desk ──
    word = getattr(room, '_wsc_threshold', '')
    if word:
        written = any(word in _wla_floor_text(room, r) for r in range(room.rows))
        gr, gc = room._wsc_gate
        gate_open = room.cells[gr][gc] != CellType.WALL
        if written and not gate_open:
            room.cells[gr][gc] = CellType.FLOOR
            unhide_region(room, getattr(room, '_wsc_hall_fog', frozenset()))
            msgs.append('The threshold word stands in fresh ink — the gate '
                        'draws, and the fog of the great page parts!')
        elif not written and gate_open and (player.row, player.col) != (gr, gc):
            room.cells[gr][gc] = CellType.WALL

    warden = next((e for e in room.entities
                   if e.kind == 'warden' and e.tag == 'scrivener' and e.alive),
                  None)

    # ── the manuscript stands finished: the seal draws, the pocket parts ──
    if warden is None:
        for e in [e for e in room.entities if e.alive
                  and e.kind == 'goblin' and e.tag == 'chorus']:
            room.kill_entity(e)
            room._on_entity_destroyed(e)
        sr, sc = room._wsc_seal
        if room.cells[sr][sc] == CellType.WALL:
            room.cells[sr][sc] = CellType.FLOOR
            unhide_region(room, getattr(room, '_wsc_pocket_fog', frozenset()))
            # silent: _on_kill announced the fall + the seal this same turn
        return msgs

    # ── the ward machine ──
    ward = getattr(room, '_wsc_ward', 1)
    hits = warden.max_hp - warden.hp
    bolt = _wsc_bolt_cell(room, warden)
    room.sealed_cells.add(bolt)       # the alcove bolt derives from the warden
    if hits >= ward:
        # Struck — he re-manifests at the next alcove and STAMPS.
        if (player.row, player.col) not in (bolt, (warden.row, warden.col)):
            room.cells[bolt[0]][bolt[1]] = CellType.WALL   # the old niche seals
        room._wsc_ward = ward + 1
        room._wsc_r2_spent0 = None
        nr, nc = _wsc_alcove_pos(room, ward)               # next alcove (0-based)
        room.move_entity(warden, nr, nc)
        room.fog_cells.add((nr, nc))                       # he shelters in fog
        anchors = _dg._WSC_STAMP_ANCHORS.get(ward + 1, ())
        stamps  = getattr(room, '_wsc_stamps', {}).get(ward + 1, ())
        for (dr, col), (text, kind) in zip(anchors, stamps):
            srow = nr + dr
            if not (0 <= srow < room.rows):
                continue
            c = col
            for piece in text.split(' '):
                if piece:
                    room.add_char_run(CharRun(srow, c, tuple(piece), kind))
                c += len(piece) + 1
        for (dr, ec) in _dg._WSC_SPAWNS.get(ward + 1, ()):
            er = nr + dr                                   # alcove-relative, like the stamps
            if 0 <= er < room.rows and room.is_passable(er, ec) \
                    and room.entity_at(er, ec) is None \
                    and (er, ec) != (player.row, player.col):
                room.add_entity(Entity(kind='goblin', row=er, col=ec, hp=1,
                                       max_hp=1, ai='', tag='chorus'))
        msgs.append('The quill SCREAMS across the page — he re-manifests '
                    'and stamps an unfinished passage!')
        msgs.extend(_wm_pressure(room, player))
    elif _wsc_ward_broken(room, ward):
        # Ward 2's window: the solve arms a timer; dawdle past it and the
        # mends re-rot, the bolt re-bars, his fog re-laid.
        if ward == 2:
            t0 = getattr(room, '_wsc_r2_spent0', None)
            if t0 is None:
                room._wsc_r2_spent0 = spent
            elif (spent - t0 >= _dg._WSC_W2_WINDOW
                  and (player.row, player.col)
                  not in (bolt, (warden.row, warden.col))):
                _wsc_recorrupt(room)
                room._wsc_r2_spent0 = None
                room.cells[bolt[0]][bolt[1]] = CellType.WALL
                room.fog_cells.add((warden.row, warden.col))
                msgs.append('Too slow — the rot crawls back through the '
                            'fresh ink!')
                return msgs
        # Staggered — echoes gutter, the bolt draws, the alcove fog parts:
        # the x window. /W now jumps the player straight onto him.
        room.fog_cells.discard((warden.row, warden.col))
        for e in [e for e in room.entities if e.alive
                  and e.kind == 'goblin' and e.tag == 'chorus']:
            room.kill_entity(e)
            room._on_entity_destroyed(e)
        if room.cells[bolt[0]][bolt[1]] == CellType.WALL:
            room.cells[bolt[0]][bolt[1]] = CellType.FLOOR
            msgs.append('The passage stands finished — the quill FALTERS. '
                        'His alcove opens: strike now!')
    else:
        # Mid-ward (or an undo restored it): the alcove stands sealed.
        room._wsc_r2_spent0 = None
        if room.cells[bolt[0]][bolt[1]] != CellType.WALL \
                and (player.row, player.col) != bolt:
            room.cells[bolt[0]][bolt[1]] = CellType.WALL

    return msgs


def _warden_manifold_tick(room, player, spent: int = 0) -> list:
    """The Stamping Press — the Warden Manifold's ward machine.

    The Warden is edit_immune and shelters in a FOGGED podium niche behind
    each of his four WARDS in turn. Breaking the ward (each keyed to one
    Act-IV verb — see _wm_ward_broken) jams the press: the ward's copies
    gutter, his bolt draws, his niche fog parts (only a revealed Warden is
    searchable — /W jumps straight onto him), and ONE x lands before he
    re-manifests at the next podium and stamps the next ward. Ward twists:
    ward 1's wall posts crumble word by word; ward 2's mends RE-CORRUPT
    (and his fog re-laid) if the strike is more than _WM_WARD2_WINDOW
    keystrokes behind the solve; ward 3's rank of stamp-Wardens doubles per
    keystroke once the rot is half-cut. `spent` is the running keystroke
    total (budget.spent) driving both timers.

    Ward checks and the bolt are shift-proof. The ward counter and timers
    (_WM_UNDO_ATTRS) ride the undo snapshot — undo rewinds the fight to the
    ward the world shows (deliberately NOT the Pathfinder convention: a
    surviving counter let undo open later bolts against earlier worlds and
    grind him without re-solving). The antechamber ritual (four braziers →
    the gate + the HALL fog parts) and the final seal (+ the treasure-pocket
    fog) are text-derived and stateless."""
    msgs = []
    # Band the ritual gate + the final seal as stonework (the live niche bolt
    # joins below, once the warden it derives from is known).
    room.sealed_cells = {c for c in (getattr(room, '_wm_gate', None),
                                     getattr(room, '_wm_seal', None)) if c}

    # ── the opening ritual: four braziers → the gate + the hall's fog ──
    braziers = getattr(room, '_wm_braziers', ())
    if braziers:
        def lit(r, c):
            ru = room.char_run_at(r, c)
            return ru is not None and ru.symbols[c - ru.col] == _dg._QM_FLAME
        unlit = {rc for rc in braziers if not lit(*rc)}
        for ru in [ru for ru in room.char_runs if ru.kind == 'pedestal']:
            if (ru.row, ru.col) not in unlit:
                room.remove_char_run(ru)
        for (r, c) in unlit:
            if room.is_passable(r, c) and room.char_run_at(r, c) is None:
                room.add_char_run(CharRun(r, c, (_dg._QM_EMBERS,), 'pedestal'))
        gr, gc = room._wm_gate
        gate_open = room.cells[gr][gc] != CellType.WALL
        if not unlit and not gate_open:
            room.cells[gr][gc] = CellType.FLOOR
            unhide_region(room, getattr(room, '_wm_hall_fog', frozenset()))
            msgs.append('Five flames burn as one — the gate draws, and the '
                        'fog of the great hall parts!')
        elif unlit and gate_open and (player.row, player.col) != (gr, gc):
            room.cells[gr][gc] = CellType.WALL

    warden = next((e for e in room.entities
                   if e.kind == 'warden' and e.tag == 'manifold' and e.alive),
                  None)

    # ── the press has fallen: every copy gutters, the seal draws, the
    # treasure pocket's fog parts ──
    if warden is None:
        for e in [e for e in room.entities if e.alive
                  and (e.kind == 'goblin'
                       or (e.kind == 'warden' and e.tag == 'stamp'))]:
            room.kill_entity(e)
            room._on_entity_destroyed(e)
        sr, sc = room._wm_seal
        if room.cells[sr][sc] == CellType.WALL:
            room.cells[sr][sc] = CellType.FLOOR
            unhide_region(room, getattr(room, '_wm_pocket_fog', frozenset()))
            # silent: _on_kill announced the fall + the seal this same turn
        return msgs

    # ── the ward machine ──
    ward = getattr(room, '_wm_ward', 1)
    hits = warden.max_hp - warden.hp
    bolt = _wm_bolt_cell(room, warden)
    room.sealed_cells.add(bolt)       # the niche bolt derives from the warden
    if hits >= ward:
        # Struck — he re-manifests at the next podium and STAMPS.
        if (player.row, player.col) not in (bolt, (warden.row, warden.col)):
            room.cells[bolt[0]][bolt[1]] = CellType.WALL  # the old niche seals
            # (never onto the player — striking from inside leaves it ajar)
        room._wm_ward = ward + 1
        room._wm_r2_spent0 = None
        nr, nc = _dg._WM_PODIUMS[ward]                    # next podium (0-based)
        room.move_entity(warden, nr, nc)                  # re-indexes _entity_map
        if ward + 1 in room._wm_stamps:
            srow, scol, text, kind = room._wm_stamps[ward + 1]
            c = scol
            for piece in text.split(' '):
                if piece:
                    room.add_char_run(CharRun(srow, c, tuple(piece), kind))
                c += len(piece) + 1
        if ward + 1 == 3:
            # arm the doubling timer's baseline: the rot as stamped
            room._wm_rot0 = _wm_rot_cells(room)
            room._wm_r3_spent0 = None
        kind, tag, spawn_cells = getattr(room, '_wm_spawns', {}).get(
            ward + 1, ('', '', ()))
        for i, (er, ec) in enumerate(spawn_cells):
            # hp=1: one strike gutters a copy outright, so one D erases a
            # whole rank like text (stamp-Wardens are NOT edit_immune).
            room.add_entity(Entity(kind=kind, row=er, col=ec, hp=1,
                                   max_hp=1, ai='', tag=tag, shade=i % 8))
        msgs.append(('The press SLAMS — he re-manifests across the hall '
                     'and stamps a new ward!'))
        msgs.extend(_wm_pressure(room, player))
    elif _wm_ward_broken(room, ward):
        # Ward 2's window: the solve arms a timer; dawdle past it (without
        # standing in the niche, one keystroke from the strike) and the
        # mends re-corrupt, the bolt re-bars, his fog re-laid.
        if ward == 2:
            t0 = getattr(room, '_wm_r2_spent0', None)
            if t0 is None:
                room._wm_r2_spent0 = spent
            elif (spent - t0 >= _dg._WM_WARD2_WINDOW
                  and (player.row, player.col)
                  not in (bolt, (warden.row, warden.col))):
                _wm_recorrupt(room)
                room._wm_r2_spent0 = None
                room.cells[bolt[0]][bolt[1]] = CellType.WALL
                room.fog_cells.add((warden.row, warden.col))
                msgs.append('Too slow — the corruption crawls back into '
                            'his stamps!')
                return msgs
        # Staggered — copies gutter, the bolt draws, the niche fog parts:
        # the x window. /W now jumps the player straight onto him.
        room.fog_cells.discard((warden.row, warden.col))
        for e in [e for e in room.entities if e.alive
                  and ((e.kind == 'goblin' and e.tag == 'echo')
                       or (e.kind == 'warden' and e.tag == 'stamp'))]:
            room.kill_entity(e)
            room._on_entity_destroyed(e)
        if room.cells[bolt[0]][bolt[1]] == CellType.WALL:
            room.cells[bolt[0]][bolt[1]] = CellType.FLOOR
            msgs.append('The ward breaks — the press JAMS. The fog in his '
                        'niche parts: strike now!')
    else:
        # Mid-ward (or an undo restored it): the niche stands sealed.
        room._wm_r2_spent0 = None
        if room.cells[bolt[0]][bolt[1]] != CellType.WALL \
                and (player.row, player.col) != bolt:
            room.cells[bolt[0]][bolt[1]] = CellType.WALL

    msgs.extend(_wm_crumble_posts(room))
    if ward == 3:
        msgs.extend(_wm_double_rank(room, player, spent))
    return msgs


def _flame_paste_blocked(room, player, clip, before: bool, count: int) -> bool:
    """The Beacon Tiers' fuel rule — a deliberate exception to Vim paste:
    a CHARWISE paste may lay a flame only onto a brazier; anywhere else
    "there is no fuel to hold that flame". Linewise paste is exempt (a
    yanked row's flames are conceptually already held by their braziers —
    and the rule is exactly why nine flames pasted along ONE row can never
    stand in for three tiers: the beacon row only has three braziers).
    True = block; the caller makes it a FREE no-op (no budget, no undo,
    no register change). Mirrors op_paste's landing arithmetic."""
    chain    = getattr(room, '_qm_chain', None)
    braziers = getattr(room, '_qm_braziers', None)
    if not chain or not clip or clip.get('linewise') or not clip.get('rows'):
        return False
    allowed = set(chain) | set(braziers or ())
    rclip = clip['rows'][0]
    width = max(rclip.get('width', 0), 1)
    base  = player.col if before else player.col + 1
    for copy in range(count):
        for rd in rclip.get('char_runs', ()):
            for k, sym in enumerate(rd['symbols']):
                if sym == _dg._QM_FLAME and \
                        (player.row, base + copy * width + rd['dcol'] + k) not in allowed:
                    return True
    return False


def _clip_is_fire(clip) -> bool:
    """True if the register holds fire — a light taken off a lit brazier.

    A lit brazier IS the flame; there is no flame without one. Yanking one (`yl`,
    `y3l`, `yy`, `yiw`…) flags the clip as fire (see `operator.op_yank`) WITHOUT
    moving the brazier, and p/P sets that light onto a cold brazier. Carrying a
    light is therefore a normal yank, not a special verb."""
    return bool(clip and clip.get('fire'))


def _quartermaster_tick(room, player) -> list:
    """The Beacon Tiers' doors — every cold brazier shows … embers; feed
    each one a flame. STATELESS, hence undo-safe (the vault-tick principle):
    everything is recomputed from the text each turn. Anchors are the stored
    build coordinates (the Cipher Cell convention) — a self-inflicted dd or
    linewise paste above them desyncs the doors until u.

    Three door families:
      chain bolts — bolt k stands open while braziers 0..k ALL burn
        (cut the source and the hall darkens: copy, don't cut);
      embers      — every unlit brazier shows … (kind='pedestal'), laid/swept
        here so a paste's open_gap can only shove them aside for one turn and
        lighting one reads as embers → flame;
      the seal    — on the LAST row, with the exit at the row's far end, so
        every line jump (G/{n}G/H/M/L lands on a first non-blank) arrives
        WEST of it; draws open while the beacon burns in three tiers
        (yy + paste ×2) AND the whole depot chain burns.
    """
    msgs = []
    chain    = getattr(room, '_qm_chain', ())
    braziers = getattr(room, '_qm_braziers', ())
    if not chain or not braziers:
        return msgs

    def lit(r, c):
        if not (0 <= r < room.rows and 0 <= c < room.cols):
            return False
        ru = room.char_run_at(r, c)
        return ru is not None and ru.symbols[c - ru.col] == _dg._QM_FLAME

    # Embers: lay at every unlit brazier, sweep strays.
    unlit = {rc for rc in (*chain, *braziers) if not lit(*rc)}
    for ru in [ru for ru in room.char_runs if ru.kind == 'pedestal']:
        if (ru.row, ru.col) not in unlit:
            room.remove_char_run(ru)
    for (r, c) in unlit:
        if room.is_passable(r, c) and room.char_run_at(r, c) is None:
            room.add_char_run(CharRun(r, c, (_dg._QM_EMBERS,), 'pedestal'))

    # Chain bolts (cumulative) on the hall row.
    hall_row = chain[0][0]
    # Band the shut chain bolts as stonework (the seal joins below). Derived
    # here because the hall row and the seal both ride the exit's row.
    room.sealed_cells = {(hall_row, bc)
                         for bc in getattr(room, '_qm_bolt_cols', ())}
    burning  = [lit(r, c) for r, c in chain]
    for i, bc in enumerate(getattr(room, '_qm_bolt_cols', ())):
        open_ = all(burning[:i + 1])
        cur_open = room.cells[hall_row][bc] != CellType.WALL
        if open_ and not cur_open:
            room.cells[hall_row][bc] = CellType.FLOOR
            msgs.append('The flame takes — the bolt grinds back!')
        elif not open_ and cur_open and (player.row, player.col) != (hall_row, bc):
            room.cells[hall_row][bc] = CellType.WALL
            msgs.append('The chain is broken — the bolts grind shut!')

    # The seal: same row as the exit (the exit rides any row shift with it).
    exit_e = next((e for e in room.entities if e.kind == 'exit'), None)
    if exit_e is not None:
        base  = braziers[0][0]
        tiers = all(lit(base + k, c) for k in (0, 1, 2) for (_, c) in braziers)
        sr, sc = exit_e.row, getattr(room, '_qm_seal_col', exit_e.col - 1)
        room.sealed_cells.add((sr, sc))
        open_ = tiers and all(burning)
        cur_open = room.cells[sr][sc] != CellType.WALL
        if open_ and not cur_open:
            room.cells[sr][sc] = CellType.FLOOR
            msgs.append('The beacon burns in three tiers — the seal draws open!')
        elif not open_ and cur_open and (player.row, player.col) != (sr, sc):
            room.cells[sr][sc] = CellType.WALL
        # One-shot nudge: the beacon row burns, but one tier alone is no beacon.
        # Deliberately names no command — the cold does the teaching.
        if (not open_ and all(lit(r, c) for r, c in braziers)
                and not getattr(room, '_qm_tier_hinted', False)):
            room._qm_tier_hinted = True
            msgs.append('The seal seems to be melting, but needs more heat! '
                        'Alas, there are no more braziers...')
    return list(dict.fromkeys(msgs))


def _wet_ink_tick(room, player) -> list:
    """The Wet Ink braziers — the inscription reveals by FIRELIGHT.
    STATELESS (the vault-tick principle): recomputed from the text each
    turn. Three laws:
      the fuel gate — a cold brazier joins the paste-allowed set
        (room._qm_chain, read by _flame_paste_blocked) only once the
        quarters BEFORE its own read true on the ledge, so the scribe
        must write, walk, light, and gi back — no lighting ahead;
      embers       — every unlit brazier shows … (kind='pedestal'),
        laid/swept here so lighting reads as embers → flame;
      firelight    — brazier k burning lifts the fog on plaque quarter
        k+1, one-way (what the fire has shown cannot be unseen)."""
    msgs = []
    words = getattr(room, '_wi_words', None)
    seg_fog = getattr(room, '_wi_seg_fog', None)
    if not words or not seg_fog:
        return msgs
    braziers = _dg._WI_BRAZIERS

    def lit(r, c):
        ru = room.char_run_at(r, c)
        return ru is not None and ru.symbols[c - ru.col] == _dg._QM_FLAME

    ledge = _wla_floor_text(room, _dg._WI_LEDGE).strip()

    # The fuel gate: the source always holds; brazier k opens with its prefix.
    allowed = [_dg._WI_SOURCE]
    for k, rc in enumerate(braziers, start=1):
        if lit(*rc) or ledge.startswith(' '.join(words[:k])):
            allowed.append(rc)
    room._qm_chain = tuple(allowed)

    # Embers: lay at every unlit brazier, sweep strays.
    unlit = {rc for rc in braziers if not lit(*rc)}
    for ru in [ru for ru in room.char_runs if ru.kind == 'pedestal']:
        if (ru.row, ru.col) not in unlit:
            room.remove_char_run(ru)
    for (r, c) in unlit:
        if room.is_passable(r, c) and room.char_run_at(r, c) is None:
            room.add_char_run(CharRun(r, c, (_dg._QM_EMBERS,), 'pedestal'))

    # Firelight: brazier k reveals quarter k+1.
    for k, rc in enumerate(braziers, start=1):
        if lit(*rc) and room.veiled_cells & seg_fog[k - 1]:
            unhide_region(room, seg_fog[k - 1])
            # Only the FIRST brazier gets a line. The reveal is on screen; after
            # one telling, the rule is learned and the render says the rest.
            if not getattr(room, '_qm_firelight_told', False):
                room._qm_firelight_told = True
                msgs.append('The firelight spills up the stone — more of the '
                            'inscription wakes.')
    return msgs


def _spawn_goblin(room, row, col, summoner_uid: int = 0) -> Entity | None:
    for c in (col, col - 1, col + 1):
        if 0 <= c < room.cols and room.is_passable(row, c) and not room.entity_at(row, c):
            e = Entity('goblin', row, c, max_hp=1, ai='chase', ai_speed=1,
                       summoner_uid=summoner_uid)
            room.add_entity(e)
            return e
    return None


# Level-entry banner: slug → (message, msg_ttl).
_LEVEL_INTROS = {
    'line_halls':          ('The Line Halls — the corridors run long, and there is no patience for crawling. Learn to reach a line by its ends.', 50),
    'reliquary':           ('The Reliquary — a relic waits behind a brittle ward. Break the seal, and it is yours.', 60),
    'counting_crypts':     ('The Counting Crypts — the passages run deep, and a step at a time wastes a life. Move in numbers.', 50),
    'rune_halls':          ('The Rune Halls — the runes gather into words. Learn to stride between them, not crawl letter by letter.', 60),
    'character_cataracts': ('The Character Cataracts — a torrent of glyphs races past. Fix your eye on one and leap straight to it.', 60),
    'wardens_keep':        ("The Warden's Keep — the shield follows you. Find the unguarded side.", 60),
    'cipher_cell':         ('The Cipher Cell — every row is enciphered false. The true words are set in the walls; make the stone agree.', 60),
    'quartermaster':       ('The Beacon Tiers — one flame survives, and the braziers stand cold. Carry the fire without snuffing it, and raise the beacon in its tiers.', 60),
    'echo_vault':          ('The Echo Vault — old tongue-twisters carved down the hall, and one blight stamped again and again through their letters. Mend it once, and let the fix echo after.', 60),
    'inscription_halls':   ('The Inscription Halls — the words were never finished, and a river bars the way. Make them whole, and the water itself will yield.', 70),
    'whole_line_annex':    ('The Change Annex — old sayings run out of the carved stone onto the floor, and where they touch the floor they go wrong. You know every one. Change cuts what is wrong and writes what is right, in a single breath.', 70),
    'change_extension':    ('The Change Extension — deeper into the halls of broken sayings. Two strokes was the novice\'s way; a practised hand needs but one. Find where a single keystroke serves.', 70),
    'sculpting_chambers':  ('The Sculpting Chambers — a boatman\'s round lies half-cut in the stone — a line gone above, a line gone below, and what remains wounded at either end. You have sung it since childhood; the vault keeps faith with the whole song, and nothing less.', 70),
    'overwrite_halls':     ('The Overwrite Halls — old sayings run from the carved stone onto the floor, and their last words have rotted: some by a single stone, some in long streaks. You know how each one ends; mind which rot runs on.', 70),
    'case_chambers':       ('The Case Chambers — every word survives letter-perfect, yet every door stays shut. Look closer: the shapes of the letters lie. The plaques keep the true forms, small and tall.', 70),
    'joiners_gate':        ('The Joiner\'s Gate — the old inscriptions were split, line from line, and scattered down the stacks. What was one line must be one line again; the plaques remember how each read whole.', 70),
    'alignment_halls':     ('The Alignment Halls — a plumb line falls through the hall, and every word has slid from its station. The plaques remember where each belongs.', 70),
    'indentation_sanctum': ('The Indentation Sanctum — the law presides from the lintel, and the verses below have slid from their stations.', 70),
    'sentence_corridor': ('The Sentence Corridor — two verses parted by still water that clings to the pool like fog. The far shore reads clear, but you can\'t reliably jump to the far wall from here.', 70),
    'sight_sanctum': ('The Sight Sanctum — old sayings interrupted mid-breath by rot no single stroke can span. You know how each one should finish. The keepers of this place had one law: first behold, then strike.', 70),
    'selection_halls': ('The Selection Halls — a gallery of corrupt panels: some rotted whole lines at a time, some down a single seam. The restorers here took each span in one grasp.', 70),
    'word_enclosure': ('The Word Enclosure — old sayings hang in these bays, every one spoken wrong. You know how they truly run. The wardens here did not aim their cuts; they named the shape, and the shape was taken whole.', 70),
    'bracket_enclosure': ('The Bracket Enclosure — a jeweller\'s gallery: old sayings carved with a stone in a setting, and every stone has gone bad. You know each saying by heart; no two doors ask alike.', 70),
    'brace_square_enclosure': ('The Brace & Square Enclosure — deeper vaults, the same old sayings: square fittings, braced caskets, and at the heart a casket WITHIN a fitting. The old jewellers read the metal under their hands before they cut.', 70),
    'sentence_enclosure': ('The Sentence Enclosure — old sayings carved as full sentences, and a stray sentence has wormed into every line. You know which words belong; the rot takes a whole verse at a time.', 70),
    'tag_enclosure': ('The Tag Enclosure — old sayings here wear a named case at their heart, and some cases sit within cases. The names are carved plain on every seam; the keepers trusted them entirely.', 70),
    'quote_enclosure': ('The Quote Enclosure — old sayings shelved with a word held between quote marks, and every held word has gone wrong. The aisle runs the gallery\'s whole length, and the shelves keep their distance from it.', 70),
    'paragraph_enclosure': ('The Paragraph Enclosure — the goblin legion stands mustered in two long cantos, chanting the tally of everything they have plundered, and six flames burn scattered down the hall among them. The gate keeps the Warden\'s Sigil: sign and seal are one.', 70),
    'buried_word': ('The Buried Word — one word stands alone at the hall\'s mouth, and nowhere else does it stand: down the hall it only hides, seamed into longer names. The seams are fused shut.', 70),
    'wet_ink': ('The Wet Ink — a writing ledge, an old saying mostly lost in the dark, and a gallery of cold braziers beneath it. Write its opening and you will know the rest. The scribes here wrote by firelight, and the fire answers only words already written.', 70),
    'g_sanctum': ('The Last Reach — three old sayings run east toward the flood. The keepers of this place went to the end of the line many times a day, and never once over it.', 70),
    'register_unnamed_hold': ('The Unnamed Hold — the horse waits at the mouth, and his saddle bears whatever you last took up. What it holds, it holds only until your hand closes on the next thing; and a blade closes a hand as surely as a grasp.', 70),
    'register_named_vault': ('The Named Vault — the vault stands open, and grey dust has settled over the end of every saying in it. An open hand carries one thing, and cannot set it down and keep it.', 70),
    'stair_rail': ('The Stair Rail — a broken stair winds down the shaft, each step\'s word set a little east of the last, and below the steps the floor falls a long way. The masons who cut these stairs never missed a landing.', 70),
    'hall_of_echoes': ('The Hall of Echoes — hall opens onto hall, and every hall repeats itself. The stone remembers.', 70),
    'grandmasters_sanctum': ('The Grandmaster\'s Sanctum — a long gallery of seven proofs, and the master himself beyond the last stone, listening to every stroke. Nothing here is new; everything here is asked properly.', 70),
    'gauntlet': ('The Gauntlet — every hall you have walked, folded into one long descent. Two of its chambers have no doors at all, and two of its verses have not been written yet. Sixteen bolts, one seal. Nothing here is new. Everything here is final.', 70),
    'warden_eternal': ('The Warden Eternal — six wardens you have already beaten wait in the dark, one behind each stone, and something older waits below them all. It has walked beside you the whole way, and blessed every door. Go down and meet it.', 70),
    'binders_reliquary': ('The Binder\'s Reliquary — still water splits the vault, too wide to step and too deep to wade. On the far shore a single word is legible, and beyond it, the binder\'s last work.', 70),
    'warden_scrivener':    ('The Warden Scrivener — he has copied these halls for an age and finished nothing. The great page waits, passage by passage, for a truer hand.', 70),
    'warden_manifold':     ('The Warden Manifold — he does not meet you, he multiplies. Every copy stands as the last one stood, and the dark keeps his count for him. Only one of them can bleed.', 70),
    'warden_surveyor':     ('The Warden Surveyor — he keeps a long hall where the floor falls away between the words. Cross it word by word, over the void.', 60),
    'spellwrights_forge':  ('The Spellwright\'s Forge — three rhymes you know are carved here, and '
                            'each is wronged its own way: a duck lows like a cow, a mouse runs the '
                            'wrong way, and nonsense static breaks a rhyme apart. Mend what is corrupt, '
                            'strike what is noise, and spare what already rings true.', 70),
    'culling_ledger':      ('The Culling Ledger — other rhymes have crept into the house that '
                            'Jack built. Set the numbers before you judge.', 60),
    'shelving_room':       ('The Shelving Room — a round of four voices on a shelf no foot can '
                            'reach: every voice sings twice, its echo one step deeper.', 60),
    'refrain_vault':       ('The Refrain Vault — the old song is carved wrong where it falls, '
                            'and right where it builds.', 60),
    'dummy':               ('Sandbox — all mechanics active. Type :edit to enter editor mode.', 60),
    'archivists_library':  ("The Archivist's Library — the whole catalogue has spilled "
                            'into a single endless line.', 80),
}

# Flavour shown when a cut creature is pasted back (op_paste revives it live).
_PASTE_SPAWN_MSG = {
    'goblin': 'The goblin springs back to life and lunges!',
    'warden': 'The Warden re-forms, wreathed in menace!',
    'shield': 'A shield clatters back into place.',
}


def _clip_from_cut_chars(items: list, base_col: int) -> dict:
    """Build a charwise register clip from x/cut character items (each a single cell),
    preserving column gaps via dcol from their original positions — so a cut
    letter pastes back through the same op_paste path as d/dw. One Vim register
    for every cut, yank, and paste."""
    runes = [{'dcol': it['rune'].col - base_col,
              'symbols': it['rune'].symbols, 'kind': it['rune'].kind}
             for it in items if it.get('type') == 'rune']
    width = max((rd['dcol'] + len(rd['symbols']) for rd in runes), default=0)
    return {'linewise': False, 'rows': [{'width': width, 'char_runs': runes}]}


# ── Easter egg: the hat-wearer may :s/g/X/ a goblin into something else ───────
# The goblins answer only their master; wearing the Warden's hat makes you him.
# Each effect REMOVES the goblin (so seals/combat still resolve — no softlock);
# they differ in flavour and what letter, if any, is left on the floor. Nods to
# Dwarf Fortress (the cat that plots your downfall; the goblin that bursts into
# cheerful flame) and the roguelikes (the NetHack pet dog, the pile of gold).
# REMOVE effects: the goblin vanishes (optionally leaving a letter on the floor).
_GOBLIN_SUB_EGGS = {
    'f': ('The {name} unclenches, waves once, and wanders off.', None),
    'h': ('The {name} loses its head about it. An h is left.',   'h'),
    '@': ('The {name} is now an adventurer, as lost as you are.', None),
}
# Every transformable egg-creature kind — matched by glyph, uniformly.
_EGG_CREATURE_KINDS = ('goblin', 'ally', 'critter', 'elf', 'gold', 'warden')
_BASE_NAMES = {'g': 'goblin', 'd': 'hound', 'c': 'cat', 'z': 'zombie',
               '&': 'demon', 'e': 'elf', '$': 'coin', 'w': 'warden'}
_SWELLABLE_LETTERS = ('g', 'd', 'c')             # the ones with a "big" (uppercase) form

# (HP, attack) per creature glyph. HP = x-hits to fell
# it; attack = half-hearts of damage it deals per hit (the player has 6 = 3♥).
_CREATURE_HP_ATK = {'g': (1, 1), 'G': (2, 1), '&': (3, 2), 'Z': (1, 1),
                    'z': (1, 1), 'c': (1, 0), 'C': (2, 3), 'd': (1, 2),
                    'D': (2, 3), 'e': (2, 2)}


def _hp_atk(glyph: str) -> tuple:
    return _CREATURE_HP_ATK.get(glyph, (1, 1))


def _entity_glyph(e) -> str:
    return entity_letter(e) or 'g'


def _arrow_key(e) -> str:
    """Attack-arrow colour key = the attacker's glyph identity."""
    if e.kind == 'ally':
        return 'ally'
    if e.kind == 'warden':
        return 'warden'
    if e.kind == 'critter':
        return 'critter'
    if e.kind == 'elf':
        return 'elf'
    if e.kind == 'goblin' and e.tag in ('demon', 'zombie'):
        return e.tag
    return 'goblin'


def _creature_name(glyph: str) -> str:
    """A creature's spoken name from its glyph — the uppercase (swelled) form of a
    swellable letter reads "big X" (big cat, big goblin, big hound)."""
    base = _BASE_NAMES.get(glyph.lower(), 'creature')
    if glyph.isupper() and glyph.lower() in _SWELLABLE_LETTERS:
        return 'big ' + base
    return base
# TRANSFORM effects: the goblin STAYS, as a new hostile that chases and attacks.
#   (tag, hp, ai, ai_speed, message)
_GOBLIN_SUB_TRANSFORM = {
    'z': ('zombie', 2, 'chase', 2, 'The goblin greys, groans, and rises — undead now.'),
    '&': ('demon',  3, 'chase', 1, "A demon uncoils where it stood. You shouldn't have."),
}
# The elf's shitty trades (offer, consequence-key, result-line). Opt-in via y.
# (offer, gold cost, consequence-key, result-line). The elf charges gold you
# picked up from :s/g/$/, then swindles you anyway.
_ELF_TRADES = [
    ('a vial of healing', 2, 'hp',       'The vial was poison. (-1 heart, chump.)'),
    ('a map to treasure', 1, 'register', 'The "map" was your own notes. Pockets emptied.'),
    ('a charm of safety', 3, 'demon',    'The charm summons a demon at your side. Safe!'),
]
_GOBLIN_SUB_RE = re.compile(r'^\s*(%?)\s*(?:\d+\s*,\s*\d+\s*)?s/([^/]*)/([^/]*)/?[gcinp]*\s*$')


def _swell(e, want: bool) -> None:
    """Set a creature's swelled state (uppercase glyph): bigger + tougher.
    Mirrors engine.operator.case_entities but on a known entity (no cell lookup,
    so it is robust to an entity sharing a cell with, e.g., a chest)."""
    if want == e.swole:
        return
    e.swole = want
    if want:
        e.max_hp += 2; e.hp += 2
    else:
        e.max_hp = max(1, e.max_hp - 2); e.hp = max(1, e.hp - 2)


def _goblin_substitute(cmd: str, room, player, push) -> bool:
    """Handle `:s/g/X/` as a creature Easter egg. Returns True if it consumed the
    command (a goblin was targeted), False to fall through to normal substitute.
    '!' marks goblins in room._pending_boom for the caller to detonate; 'e' arms
    room._elf_trade for the caller's y/n prompt."""
    m = _GOBLIN_SUB_RE.match(cmd)
    if not m:
        return False
    whole, pat, rep = m.group(1), m.group(2), m.group(3)
    if len(pat) == 2 and pat[0] == '\\':            # a backslash-escaped glyph (\$)
        pat = pat[1]
    if len(pat) != 1:                                # single-glyph patterns only
        return False
    rows = range(room.rows) if whole == '%' else (player.row,)
    _fog    = getattr(room, 'fog_cells', set())
    _sunken = getattr(room, 'underwater_cells', set())
    # ONE unified match: every transformable creature by its CURRENT glyph, so
    # :s/g/…, :s/G/…, :s/d/…, :s/Z/…, :s/e/…, :s/$/…, :s/W/… all target the right
    # beasts (case-sensitive, Vim-true). Fogged cells are skipped — you cannot
    # transform what you cannot see.
    gobs = [e for e in room.entities if e.alive and e.row in rows
            and e.kind in _EGG_CREATURE_KINDS
            and entity_letter(e) == pat
            and ((e.row, e.col) not in _fog or (e.row, e.col) in _sunken)]
    if not gobs:
        return False                                 # no matching creatures → normal :s
    if not (getattr(player, 'hat_worn', False) or 'admin' in player.known_commands):
        push('They only heed the hand beneath the hat. Not yours.')
        return True
    rep1 = rep[:1]
    n = len(gobs)
    tail = f'  (×{n})' if n > 1 else ''
    name = _creature_name(pat)                       # the SOURCE creature's name

    if rep1 == '!':                                  # burst into cheerful flame
        room._pending_boom = [(g.row, g.col) for g in gobs]   # caller detonates
        return True

    def _reset(g, kind, tag, ai, hp, speed=1):
        g.kind, g.tag, g.ai, g.ai_speed = kind, tag, ai, speed
        g.max_hp = g.hp = hp
        g.swole = g.edit_immune = False              # a transformed Warden loses its ward

    # ── in-place transforms: the creature STAYS ──────────────────────────────
    # Uppercase swellable letters (G/D/C) are the "big" form, routed through the
    # shared case rule so they are bigger + sharper-eyed exactly like ~ or gU.
    base, up = rep1.lower(), rep1.isupper()

    def _sethp(g, glyph):
        g.max_hp = g.hp = _hp_atk(glyph)[0]

    if base == 'g':                                  # goblin (G = big)
        for g in gobs:
            if g.kind != 'goblin' or g.tag in ('zombie', 'demon'):
                _reset(g, 'goblin', '', 'chase', 1)
            _swell(g, up)
            _sethp(g, 'G' if up else 'g')
        room.rebuild_indexes()
        push(f'The {name} is now a {_creature_name("G" if up else "g")}.' + tail)
        return True
    if base == 'd':                                  # a hound on YOUR side (D = big)
        for g in gobs:
            _reset(g, 'ally', 'dog', 'hunt', 2)
            _swell(g, up)
            _sethp(g, 'D' if up else 'd')
        room.rebuild_indexes()
        push(f'The {name} becomes a {_creature_name("D" if up else "d")} and takes your side.' + tail)
        return True
    if base == 'c':                                  # a cat (c = friendly, C = a big aggressor)
        for g in gobs:
            _reset(g, 'critter', 'cat', 'wander', 1)
            g.summon_timer = random.randint(3, 10)   # turns until its next meow
            _swell(g, up)
            _sethp(g, 'C' if up else 'c')
        room.rebuild_indexes()
        push(f'The {name} is now a {_creature_name("C" if up else "c")}. '
             + ('It bares its claws.' if up else 'It purrs, and plots your downfall.') + tail)
        return True
    if rep1 == '$':                                  # a coin of gold to pick up
        for g in gobs:
            _reset(g, 'gold', 'gold', '', 1)
        room.rebuild_indexes()
        push(f'The {name} clinks into a coin of gold — step on it to pocket it.' + tail)
        return True
    if base == 'e':                                  # a merchant elf (it STAYS)
        for g in gobs:
            _reset(g, 'elf', 'elf', '', 1)
            _sethp(g, 'e')
        room.rebuild_indexes()
        push(f'The {name} becomes an elf, keen to make you a deal.' + tail)
        return True
    if base == 'z' or rep1 == '&':                   # raise the dead / summon worse
        tag, hp, ai, spd, _msg = _GOBLIN_SUB_TRANSFORM['z' if base == 'z' else '&']
        verb = 'greys, groans, and rises — undead now.' if base == 'z' \
            else "twists into a demon. You shouldn't have."
        for g in gobs:
            _reset(g, 'goblin', tag, ai, hp, spd)
            _sethp(g, 'Z' if base == 'z' else '&')
        room.rebuild_indexes()
        push(f'The {name} {verb}' + tail)
        return True

    # ── REMOVE effects (default: turn into that harmless letter) ─────────────
    msg, drop = _GOBLIN_SUB_EGGS.get(
        rep1, (f'The {name} is now a harmless {rep1}.' if rep1 else
               f'The {name} simply is not, any more.', rep1 or None))
    for g in gobs:
        gr, gc = g.row, g.col
        room.kill_entity(g)
        if drop and room.char_run_at(gr, gc) is None:
            room.add_char_run(CharRun(gr, gc, (drop,), 'ancient'))
    room.rebuild_indexes()
    push(msg.format(name=name) + tail)
    return True


def _drop_key(room, row: int, col: int, tag: str = '') -> bool:
    """Place a floor_key (optionally colour-tagged) at (row, col) if free.
    Returns True if a key was placed."""
    if not room.entity_at(row, col):
        room.add_entity(Entity(kind='floor_key', row=row, col=col, tag=tag))
        return True
    return False


def _held_key(player):
    """If the unnamed register is carrying a floor_key, return its template
    (so its colour tag survives a drop); otherwise None."""
    clip = _reg_read(player, '"')
    if not clip:
        return None
    for rw in clip.get('rows', []):
        for ed in rw.get('entities', ()):
            if ed.get('tmpl', {}).get('kind') == 'floor_key':
                return ed['tmpl']
    return None


def _on_kill(ent, player, room=None, level: str = '') -> str:
    if ent.kind == 'warden':
        if level == 'warden_manifold':
            if ent.tag == 'stamp':
                return 'A stamped copy gutters out.'
            # The ONE death banner — the tick opens the seal the same turn
            # and stays silent (two stacked messages read as a bug).
            return ('The Warden Manifold is undone — every copy gutters '
                    'out, and the seal draws open.')
        if level == 'warden_scrivener':
            return ('The Warden Scrivener is undone — the manuscript stands '
                    'finished, and the seal draws open.')
        if level == 'warden_eternal':
            # No keys here — the gates open on clearing, the seal on the kill.
            # A felled warden simply falls; the way down opens itself.
            return 'A Warden falls — and the stone above his brother stirs.' \
                if ent.tag == 'eternal' else ''
        # Every Warden drops the key to its keep's locked exit door (no auto-open).
        if room is not None:
            _drop_key(room, ent.row, ent.col)
        return 'The Warden falls! A key drops to the floor. 🗝'
    if ent.kind == 'goblin' and level == 'goblin_gauntlet' and room is not None:
        if not any(e.alive for e in room._entity_by_kind.get('goblin', [])):
            _drop_key(room, ent.row, ent.col)
            return 'Last goblin down! A key clatters to the floor. 🗝'
    return ''


def _remove_warden_shields(room) -> None:
    """Kill all shield entities in the room (called when the Warden dies)."""
    for sh in [e for e in room._entity_by_kind.get('shield', []) if e.alive]:
        room.kill_entity(sh)


def _check_seal_broken(room) -> str:
    """Open the Reliquary's warded doorway once its seal-word is fully erased.

    The dividing wall blocks the sanctum until the seal CharRun on the action
    row is cut away with x; then the doorway cell (room.seal_door) opens.
    Returns a message to display, or '' if nothing changed.
    """
    sd = getattr(room, 'seal_door', None)
    if sd is None:
        return ''
    sr, sc = sd
    if room.cells[sr][sc] != CellType.WALL:
        return ''                                      # already open
    if any(ru.row == sr for ru in room.char_runs):
        return ''                                      # seal not fully erased
    room.cells[sr][sc] = CellType.FLOOR
    room.fog_cells.clear()                             # the sanctum is revealed
    return 'The seal is broken — the ward dissolves and the way opens!'


# ── The Warden Surveyor — Phase-1 attack (pure helpers; orchestrated below) ───
def _ws_bounds():
    """Dry-interior bounds (top, bot, left, right) of the Surveyor's hall."""
    return _dg._WS_INNER_TOP, _dg._WS_INNER_BOT, _dg._WS_TEXT_COL, _dg._WS_INNER_RIGHT


def _ws_paren_cells(room) -> list:
    """Dry interior cells sitting between a '(' and its matching ')'."""
    top, bot, l, r = _ws_bounds()
    out = []
    for rr in range(top, bot + 1):
        stack = []
        for c in range(l, r + 1):
            ru = room.char_run_at(rr, c)
            ch = ru.symbols[c - ru.col] if ru else None
            if ch == '(':
                stack.append(c)
            elif ch == ')' and stack:
                o = stack.pop()
                out += [(rr, cc) for cc in range(o + 1, c)]
    return out


def _ws_threat_span(warden_col: int, player_col: int) -> tuple:
    """The warden's v-sweep: (c0, c1) from himself to the dry edge on the side
    the adventurer stands — v$ (right) or v0 (left)."""
    _, _, l, r = _ws_bounds()
    return (warden_col, r) if player_col >= warden_col else (l, warden_col)


def _ws_landable(room, player, r: int, c: int) -> bool:
    """A dry interior floor cell the warden may leap to (clear, ≥3 from player)."""
    top, bot, l, rr = _ws_bounds()
    return (top <= r <= bot and l <= c <= rr
            and room.cells[r][c] == CellType.FLOOR
            and room.entity_at(r, c) is None
            and abs(r - player.row) + abs(c - player.col) >= 3)


def _ws_erase_row(room, row: int, c0: int, c1: int) -> None:
    """Erase char-runs in [c0, c1] on `row` (the warden eats the verse there)."""
    kept = []
    for ru in room.char_runs:
        if ru.row != row:
            kept.append(ru); continue
        seg, seg_col = [], None
        for i, sym in enumerate(ru.symbols):
            cc = ru.col + i
            if c0 <= cc <= c1:
                if seg:
                    kept.append(CharRun(row, seg_col, tuple(seg), ru.kind)); seg, seg_col = [], None
            else:
                if seg_col is None:
                    seg_col = cc
                seg.append(sym)
        if seg:
            kept.append(CharRun(row, seg_col, tuple(seg), ru.kind))
    room.char_runs = kept
    room.rebuild_indexes()


def _reposition_warden_shield(room, warden: Entity, player) -> None:
    """Move the shield to the warden's new row, flipping it to the opposite horizontal side."""
    candidates = [e for e in room.entities if e.alive and e.kind == 'shield']
    if not candidates:
        return
    shield = min(candidates, key=lambda e: abs(e.row - warden.row) + abs(e.col - warden.col))
    current_side = 1 if shield.col >= warden.col else -1
    preferred = warden.col + (-current_side)   # flip to opposite side
    fallback  = warden.col + current_side      # stay same side if blocked
    for tc in (preferred, fallback):
        if (0 <= tc < room.cols
                and room.cells[warden.row][tc] in (CellType.FLOOR, CellType.CORRIDOR)
                and not room.entity_at(warden.row, tc)):
            room.move_entity(shield, warden.row, tc)
            return


_WARDEN_MIN_JUMP = 2   # the Warden never hops a single row — it leaps
_WARDEN_MAX_JUMP = 6   # ...but won't teleport across an arbitrarily tall arena


def _do_warden_move(room, warden: Entity, player) -> str:
    """Leap the warden to a random row a minimum of 2 rows away, then reposition shield.

    The Warden bounds unpredictably off the arena's floor boundaries rather
    than shuffling between nearby rows: each move it picks a random open row
    that is at least _WARDEN_MIN_JUMP and at most _WARDEN_MAX_JUMP rows away,
    in either direction. Lazy-initialises origin_row on first call. Returns a
    non-empty message on success, '' if no landing ≥2 rows away exists.
    """
    if warden.origin_row < 0:
        warden.origin_row = warden.row
    col = warden.col

    candidates = [
        nr for nr in range(room.rows)
        if _WARDEN_MIN_JUMP <= abs(nr - warden.row) <= _WARDEN_MAX_JUMP
        and room.cells[nr][col] in (CellType.FLOOR, CellType.CORRIDOR)
        and not room.entity_at(nr, col)
    ]
    if not candidates:
        return ''

    nr = random.choice(candidates)
    warden.move_dir = 1 if nr > warden.row else -1
    room.move_entity(warden, nr, col)
    _reposition_warden_shield(room, warden, player)
    return 'The Warden leaps!'


_ORTHO = ((-1, 0), (1, 0), (0, -1), (0, 1))  # up, down, left, right (vertical first)


def _steppable(room, player, r: int, c: int) -> bool:
    """True if (r, c) is a cell an enemy may move onto this turn."""
    if (r, c) == (player.row, player.col):
        return False  # the player's cell is attacked, never stepped onto
    return room.is_passable(r, c) and not room.entity_at(r, c)


def _greedy_step_toward(room, player, ent, goal):
    """A last-resort single step toward `goal` (dominant axis first, then the
    other, then any free neighbour). None only if fully boxed in."""
    gr, gc = goal
    dr, dc = gr - ent.row, gc - ent.col
    if abs(dr) >= abs(dc):
        cands = [(ent.row + ((dr > 0) - (dr < 0)), ent.col),
                 (ent.row, ent.col + ((dc > 0) - (dc < 0)))]
    else:
        cands = [(ent.row, ent.col + ((dc > 0) - (dc < 0))),
                 (ent.row + ((dr > 0) - (dr < 0)), ent.col)]
    cands += [(ent.row + a, ent.col + b) for a, b in _ORTHO]
    for nr, nc in cands:
        if (nr, nc) != (ent.row, ent.col) and _steppable(room, player, nr, nc):
            return (nr, nc)
    return None


def _bfs_step(room, player, start, goal, cap: int = 1400):
    """The first step of the shortest walkable path from `start` to a cell
    ADJACENT to `goal`, routing AROUND stone walls (unlike a goblin's greedy
    lunge). None if already adjacent or no path within `cap` explored cells."""
    ok = _steppable
    sr, sc = start
    gr, gc = goal
    if abs(sr - gr) + abs(sc - gc) <= 1:
        return None                                  # already at the goal's side
    prev = {(sr, sc): None}
    q = deque([(sr, sc)])
    while q and len(prev) < cap:
        r, c = q.popleft()
        for dr, dc in _ORTHO:
            nr, nc = r + dr, c + dc
            if (nr, nc) in prev or not ok(room, player, nr, nc):
                continue
            prev[(nr, nc)] = (r, c)
            if abs(nr - gr) + abs(nc - gc) <= 1:     # reached the goal's side
                cur = (nr, nc)
                while prev[cur] != (sr, sc):
                    cur = prev[cur]
                return cur
            q.append((nr, nc))
    return None


_HORSE_TRAIL = 3        # trails the player at 2-3 cells; only closes past this
_HORSE_MOTIONS = ('w', 'W', 'e', 'E', 'b', 'B', 'ge', '^', '0', '$', '%', '+', '-')


def _horse_vim_landing(room, ent, motion, count):
    """Where a Vim motion would carry a cursor placed on the horse's cell —
    (row, col), or None if it doesn't move (or the motion errors on this buffer)."""
    shim = Player(row=ent.row, col=ent.col)
    try:
        apply_motion(shim, motion, count, room)
    except Exception:
        return None
    if (shim.row, shim.col) == (ent.row, ent.col):
        return None
    return (shim.row, shim.col)


def _horse_step(room, player, ent):
    """The wizard's horse RIDES Vim to follow: each turn it picks the word/line
    motion (w/b/e/^/0/$/% and count-j/k across rows) that best keeps it trailing
    the player at 2-3 cells. Returns a landing (r, c), or None to hold station.

    It holds once within the trail band, closes the gap when it grows, and never
    treads on the player. A plain BFS step is the last resort so a corridor with
    no useful horizontal motion can't strand it."""
    cur = _manhattan(player.row, player.col, ent.row, ent.col)
    if cur <= _HORSE_TRAIL:
        return None                                  # at heel — hold
    cands = [_horse_vim_landing(room, ent, m, 1) for m in _HORSE_MOTIONS]
    dr = player.row - ent.row                        # count-j / count-k to change rows
    if dr:
        cands.append(_horse_vim_landing(room, ent, 'j' if dr > 0 else 'k',
                                        min(abs(dr), 4)))
    best = None
    for p in cands:
        if p is None or not _steppable(room, player, *p):
            continue
        nd = _manhattan(player.row, player.col, *p)
        if nd >= cur:
            continue                                 # must close the gap
        key = (0 if 2 <= nd <= _HORSE_TRAIL else 1, abs(nd - 2), nd)
        if best is None or key < best[0]:
            best = (key, p)
    if best is not None:
        return best[1]
    return _bfs_step(room, player, (ent.row, ent.col), (player.row, player.col))


def _detour_step(room, player, ent, dist: int):
    """First cell of a 2-move path that ends no farther from the player, or None.

    Called only when the goblin's greedy step is blocked (e.g. by the Warden's
    shield). Lets it route around the obstacle instead of stalling: it commits to
    a first step if some second step lands at distance <= its current distance.
    First steps that reduce distance are tried first; vertical wins ties (matching
    the greedy row-first bias).
    """
    firsts = []
    for dr, dc in _ORTHO:
        fr, fc = ent.row + dr, ent.col + dc
        if _steppable(room, player, fr, fc):
            firsts.append((_manhattan(player.row, player.col, fr, fc), fr, fc))
    firsts.sort(key=lambda t: t[0])  # _ORTHO order is the stable tie-break
    for _fd, fr, fc in firsts:
        for dr, dc in _ORTHO:
            sr, sc = fr + dr, fc + dc
            if (sr, sc) == (ent.row, ent.col):
                continue  # stepping back to start is not progress
            if (sr, sc) == (player.row, player.col):
                return (fr, fc)  # second move reaches the player — an approach
            if (_steppable(room, player, sr, sc)
                    and _manhattan(player.row, player.col, sr, sc) <= dist):
                return (fr, fc)
    return None


def _ally_foes(room) -> list:
    """Everything a hound will bite — every live hostile it can smell.

    An impostor Warden (a goblin wearing tag='echo') is a hostile like any
    other, and the hound smells it like one; its first bite tears the disguise
    off exactly as the player's own x does.
    """
    return [e for e in room.entities
            if e.alive and e.kind in ('goblin', 'warden')]


def _bites_allies(ent) -> bool:
    """True if `ent` is something that mauls a hound standing next to it."""
    return (ent.kind in ('goblin', 'warden')
            or (ent.kind == 'critter' and ent.swole))


def _bite_ally(room, ent) -> list:
    """`ent` strikes one adjacent hound, if there is one.  Returns messages.

    Whatever would bite the PLAYER bites a hound in its way.  Without this a
    hound was untouchable — it struck first every turn and nothing in the game
    could ever strike back, so a single dog walked a room clean.  A STATIONARY
    hostile (ai='') bites too: a creature that cannot path to you can still
    defend the cell it is standing in.
    """
    msgs = []
    for a in room._entity_by_kind.get('ally', []):
        if not a.alive or _manhattan(ent.row, ent.col, a.row, a.col) > _ATTACK_RADIUS:
            continue
        a.hp -= (1 if ent.kind == 'warden'
                 else max(1, _hp_atk(_entity_glyph(ent))[1]))
        room._atk_arrows = getattr(room, '_atk_arrows', [])
        room._atk_arrows.append((ent.row, ent.col, a.row, a.col, _arrow_key(ent)))
        if a.hp <= 0:
            room.kill_entity(a)
            msgs.append('Your hound falls.')
        break                                    # one bite per hostile per turn
    return msgs


_TICK_KINDS = frozenset(('ally', 'horse', 'critter', 'archivist',
                         'warden', 'goblin'))


def _enemy_tick(room, player) -> list:
    # Early-out for rooms where nothing can act: the per-entity branches cover
    # exactly these kinds plus any entity with its own ai (a wandering elf,
    # a summoned chorus). The Pathfinder's mega is ROOM-level state, though —
    # it must tick even in an empty room, so it vetoes the short-circuit.
    if not getattr(room, 'mega', None) and not any(
            e.alive and (e.kind in _TICK_KINDS or e.ai)
            for e in room.entities):
        return []
    msgs = []
    for ent in list(room.entities):
        if not ent.alive:
            continue
        if ent.kind == 'ally':
            # A hound on your side (:s/g/d/): FAST (double speed; a big Hound
            # triple). It FOLLOWS the player, biting any adjacent foe and
            # diverting only to a nearby, reachable hostile — and it NEVER stands
            # still: if the path is blocked it greedily shuffles toward you.
            _dmg = _hp_atk('D' if ent.swole else 'd')[1]     # D=3, d=2 per BITE
            _fog = getattr(room, 'fog_cells', set())
            # It moves up to `speed` cells; the moment it reaches a foe it bites
            # ONCE (not once per step) and its turn ends — so a big Hound deals 3,
            # not 9, a turn.
            for _ in range(3 if ent.swole else 2):           # moves per turn
                foes = [e for e in _ally_foes(room)
                        if (e.row, e.col) not in _fog]
                adj = next((e for e in foes
                            if _manhattan(ent.row, ent.col, e.row, e.col) <= 1), None)
                if adj is not None:
                    _ar, _ac = adj.row, adj.col
                    if adj.kind == 'goblin' and adj.tag == 'echo':
                        # Same price as the player's own x: one strike tears the
                        # disguise off, the next one kills.
                        if strike_disguise(adj):
                            room.kill_entity(adj)
                            msgs.append('Your hound fells a foe!')
                        else:
                            msgs.append('Your hound tears the disguise off a false Warden!')
                    else:
                        adj.hp -= _dmg
                        if adj.hp <= 0:
                            room.kill_entity(adj)
                            msgs.append('Your hound fells a foe!')
                    # a colored direction arrow at the hound, pointing at the bite
                    room._atk_arrows = getattr(room, '_atk_arrows', [])
                    room._atk_arrows.append((ent.row, ent.col, _ar, _ac, 'ally'))
                    break                                # one bite, turn over
                # divert only to a CLOSE, reachable hostile; else follow the player
                step = None
                for f in sorted((e for e in foes
                                 if _manhattan(ent.row, ent.col, e.row, e.col) <= 5),
                                key=lambda e: _manhattan(ent.row, ent.col, e.row, e.col)):
                    step = _bfs_step(room, player, (ent.row, ent.col), (f.row, f.col))
                    if step is not None:
                        break
                if step is None:
                    if _manhattan(ent.row, ent.col, player.row, player.col) <= 1:
                        break                            # at heel — hold
                    step = (_bfs_step(room, player, (ent.row, ent.col),
                                      (player.row, player.col))
                            or _greedy_step_toward(room, player, ent,
                                                   (player.row, player.col)))
                if step is None:
                    break
                room.move_entity(ent, *step)
            continue
        if ent.kind == 'horse':
            # Named (ent.tag holds his name), he trails you at 2-3 cells, riding Vim
            # motions. Un-adopted, he ambles at random like a stray cat until you
            # name him — approach and x him for the naming popup.
            if ent.tag:
                step = _horse_step(room, player, ent)
                if step is not None:
                    room.move_entity(ent, *step)
            else:
                ent.ai_tick += 1
                if ent.ai_tick % 2 == 0:
                    dr, dc = random.choice(_ORTHO)
                    nr, nc = ent.row + dr, ent.col + dc
                    if (nr, nc) != (player.row, player.col) and _steppable(room, player, nr, nc):
                        room.move_entity(ent, nr, nc)
            continue
        if ent.kind == 'critter' or (ent.kind == 'elf' and ent.ai == 'wander'):
            # A cat (:s/g/c/) ambles and yowls; a big Cat ROARS. A spent elf
            # (post-trade) wanders the same way, but silently.
            ent.ai_tick += 1
            if ent.kind == 'critter':
                ent.summon_timer -= 1
                if ent.summon_timer <= 0:
                    ent.summon_timer = random.randint(3, 10)
                    msgs.append('ROAR' if ent.swole else 'Meow.')
            if ent.ai_tick % 2 == 0:
                dr, dc = random.choice(_ORTHO)
                nr, nc = ent.row + dr, ent.col + dc
                if (nr, nc) != (player.row, player.col) and _steppable(room, player, nr, nc):
                    room.move_entity(ent, nr, nc)
            continue
        if ent.kind == 'archivist':
            w = getattr(room, '_wrap_w', 0) or 1
            if getattr(room, 'lib_hostile', False):
                # Furious: quickest path in the WRAPPED view — gj/gk straight to the
                # player's display row (even one row away, never circling the file),
                # then single/double steps along it, halting adjacent.
                d = player.col - ent.col
                pr, ar = player.col // w, ent.col // w
                if pr != ar:                            # different display rows → hop toward it
                    nc = ent.col + (w if pr > ar else -w)
                    if (0, nc) == (player.row, player.col):   # would land on him → sidestep first
                        nc = ent.col + (1 if d > 0 else -1)
                elif abs(d) > 1:                        # same row → close in (up to two cells)
                    nc = ent.col + (1 if d > 0 else -1) * min(2, abs(d) - 1)
                else:
                    nc = ent.col                        # adjacent → the combat block strikes
                nc = min(max(0, nc), room.cols - 1)
                if nc != ent.col and (0, nc) != (player.row, player.col):
                    room.move_entity(ent, 0, nc)
            elif getattr(room, 'lib_done', None) == 'win':
                # Won: settle back beside his desk and stay within 0-4 cells of it (to
                # the right, clear of the reward chests on its left).
                home = getattr(room, '_lib_desk_col', ent.col)
                if ent.col < home:
                    nc = min(ent.col + 2, home)
                elif ent.col > home + 4:
                    nc = ent.col - 2
                elif random.random() < 0.3:
                    nc = min(max(home, ent.col + random.choice([-1, 1])), home + 4)
                else:
                    nc = ent.col
                nc = min(max(1, nc), room.cols - 2)
                if (0, nc) != (player.row, player.col) and nc != ent.col:
                    room.move_entity(ent, 0, nc)
            elif ent.ai:
                # Discrete gait: two cells per tick (a brisk, even pace), with the
                # occasional gj/gk display-row hop. (summon_timer = ticks left in this run.)
                ent.ai_tick += 1
                if ent.ai_tick % ent.ai_speed == 0:
                    if ent.summon_timer <= 0:
                        if random.random() < 0.2:
                            ent.move_dir, ent.summon_timer = random.choice([-w, w]), 1
                        else:
                            ent.move_dir, ent.summon_timer = random.choice([-2, 2]), 2
                    ent.summon_timer -= 1
                    nc = min(max(1, ent.col + ent.move_dir), room.cols - 2)
                    if (0, nc) != (player.row, player.col) and nc != ent.col:
                        room.move_entity(ent, 0, nc)
                        room._lib_arch_paced = True   # he has stepped off his desk
            continue
        if ent.kind == 'warden' and ent.tag == 'verse':
            # He approaches the player THROUGH the wrapped display: gj/gk a whole fold toward
            # the player's display row (so he comes UP when you're above him), then closes
            # along that row. In nowrap the fold is the whole line, so he just walks it. He
            # hits and is hit regardless of wrap.
            w = getattr(room, '_wrap_w', 0) or room.cols
            pr, ar = player.col // w, ent.col // w        # display rows
            d = player.col - ent.col
            if pr != ar:
                nc = ent.col + (w if pr > ar else -w)     # gj (down) / gk (up) toward him
            elif abs(d) > 1:
                nc = ent.col + (1 if d > 0 else -1)       # same display row → close along it
            else:
                nc = ent.col
            step = 1 if nc >= ent.col else -1
            hops = 0
            while 1 <= nc <= room.cols - 2 and not room.is_passable(0, nc) and hops < 8:
                nc += step; hops += 1                      # skip over a segment wall
            if (nc != ent.col and 1 <= nc <= room.cols - 2 and room.is_passable(0, nc)
                    and (0, nc) != (player.row, player.col)):
                room.move_entity(ent, 0, nc)
            continue
        if _bites_allies(ent):
            msgs += _bite_ally(room, ent)
        dist = _manhattan(player.row, player.col, ent.row, ent.col)
        if ent.kind == 'warden' \
                and ent.tag not in ('surveyor', 'verse', 'manifold', 'stamp',
                                    'scrivener', 'grandmaster',
                                    'eternal', 'eternal_boss') \
                and dist <= _ALERT_RADIUS:
            has_goblins = any(
                e.alive and e.summoner_uid == ent.uid
                for e in room._entity_by_kind.get('goblin', [])
            )
            if has_goblins:
                ent.goblin_free_turns = 0
            else:
                ent.goblin_free_turns += 1
            if ent.summon_timer > 0:
                ent.summon_timer -= 1
            if ent.summon_timer == 0 and ent.goblin_free_turns >= 2:
                _side = random.choice((-1, 1))
                _spawn_goblin(room, ent.row, ent.col + _side * 3, summoner_uid=ent.uid)
                ent.summon_timer = _WARDEN_SUMMON_INTERVAL
                msgs.append('The Warden summoned a goblin minion!')
        if not ent.ai:
            continue
        if dist > _sight_radius(ent):
            continue
        ent.ai_tick += 1
        if ent.ai_tick % ent.ai_speed != 0:
            continue
        dr = player.row - ent.row
        dc = player.col - ent.col
        # Orthogonal step: dominant axis wins; row-first on tie
        if abs(dr) >= abs(dc):
            nr, nc = ent.row + ((dr > 0) - (dr < 0)), ent.col
        else:
            nr, nc = ent.row, ent.col + ((dc > 0) - (dc < 0))
        if (nr, nc) == (player.row, player.col):
            continue  # adjacent → attack handled elsewhere; don't step on player
        if _steppable(room, player, nr, nc):
            room.move_entity(ent, nr, nc)
            continue
        # Greedy step blocked (e.g. by the Warden's shield) — try a 2-move detour.
        step = _detour_step(room, player, ent, dist)
        if step is not None:
            room.move_entity(ent, *step)
    if getattr(room, 'mega', None):          # The Warden Pathfinder's floor-cut cadence
        msgs += mega_tick(room, player, random)
    return msgs


def _budget_exhausted_blocks(action: dict) -> bool:
    """Once the budget is spent, the path is over: every budget-costing action is
    blocked so the player can't move (or edit / search / etc.) any further.  Only
    undo/redo (to recover the spent budget) and entering command mode (:q to quit,
    :edit) may still proceed.  Callers gate with `budget.remaining <= 0 and not
    edit_mode`; this answers "is THIS action one of the blocked ones?\""""
    if action['type'] in ('undo', 'redo'):
        return False
    if action['type'] == 'enter_mode' and action.get('mode') == 'command':
        return False
    return True


def _visual_mode_toggle(raw: str, key_str: str):
    """While in a visual mode, the target mode for a v / V / Ctrl-v keypress (which
    toggles or switches), or None if the key isn't one of those switches.

    `raw` is '' for every *sequence* key (Enter, arrows, Home, …).  Those must return
    None — a regression once used `raw in 'vV'`, and since '' is a substring of any
    string that flipped <enter> (and friends) into VISUAL_BLOCK."""
    if raw in ('v', 'V'):
        return {'v': Mode.VISUAL, 'V': Mode.VISUAL_LINE}[raw]
    if key_str == '\x16':                       # Ctrl-v
        return Mode.VISUAL_BLOCK
    return None


# Levels that bar the companion horse. Bosses are climactic one-on-ones (a horse
# trotting through would break the staging); the two pure-combat crushes and the
# admin dummy have no room for him. A level can also opt out at runtime by setting
# room.no_horse = True. Everywhere else, a named horse tags along.
_HORSE_BLOCKED_SLUGS = {'goblin_gauntlet', 'gauntlet', 'dummy'}


def _horse_blocked(level: str, room) -> bool:
    """True if this level flags the companion horse out (boss / combat / opt-out)."""
    if getattr(room, 'no_horse', False):
        return True
    if level_type(level) == 'boss':
        return True
    return level in _HORSE_BLOCKED_SLUGS


def _place_first_cave_horse(room) -> None:
    """Stand the wizard's horse (♞) on an empty floor cell near the entry — a
    post-game Easter egg. No-op if one is already there or no free cell exists."""
    from vimny.engine.world import CellType
    if any(e.kind == 'horse' for e in room.entities):
        return
    sr, sc = room.spawn_pos
    er, ec = room.exit_pos if room.exit_pos else (-1, -1)
    best = None
    for r in range(room.rows):
        for c in range(room.cols):
            if room.cells[r][c] not in (CellType.FLOOR, CellType.CORRIDOR):
                continue
            if (r, c) in ((sr, sc), (er, ec)):
                continue
            if room.entity_at(r, c) is not None or room.char_run_at(r, c) is not None:
                continue
            d = abs(r - sr) + abs(c - sc)
            if d < 2:                      # give the player a step of breathing room
                continue
            if best is None or d < best[0]:
                best = (d, r, c)
    if best is not None:
        _, r, c = best
        room.entities.append(Entity(kind='horse', row=r, col=c))
        room.rebuild_indexes()


def _meta_name(lv, v):
    """The one metadata field with no empty state: a level's file is named after
    it, so clearing it would leave the draft with nowhere to be saved."""
    if v:
        lv.name = v


#: The forge's metadata block: field → (read, write). Every one of them answers
#: `:field?` as well as taking a value, which is the half Vim has always had and
#: an authoring UI needs more than most — you cannot correct what you cannot read
#: back, and `:meta` only summarises.
_FORGE_META = {
    'name':      (lambda lv: lv.name,                _meta_name),
    'author':    (lambda lv: lv.author,              lambda lv, v: setattr(lv, 'author', v)),
    'intro':     (lambda lv: lv.intro,               lambda lv, v: setattr(lv, 'intro', v)),
    'alternate': (lambda lv: lv.alternate or '',     lambda lv, v: setattr(lv, 'alternate', v or None)),
    'teaches':   (lambda lv: ' '.join(lv.teaches),   lambda lv, v: setattr(lv, 'teaches', v.split())),
    'requires':  (lambda lv: ' '.join(lv.requires),  lambda lv, v: setattr(lv, 'requires', v.split())),
    'vocab':     (lambda lv: ' '.join(lv.vocabulary), lambda lv, v: setattr(lv, 'vocabulary', v.split())),
}


# ── Dungeon game loop ──────────────────────────────────────────────────────────

def run_dungeon(term: Terminal, level: str, progress: dict,
                player_name: str = 'Normand',
                _dungeon: Dungeon | None = None,
                _start_edit: bool = False,
                _known: list | None = None,
                _record: dict | None = None,
                _notice: str | None = None,
                _draft=None) -> dict:
    """Run one dungeon level.

    Returns {'won': bool, 'stars': int, 'action': 'wq'|'quit',
             'first_written_completion': bool}.
    first_written_completion is True when the player saved (:w or :wq) and it
    was the first time this level reached ≥1 star (prev stars == 0).
    _dungeon: pre-built Dungeon (used for custom layouts from the overworld).
    _start_edit: if True, enter edit mode immediately (admin custom levels).
    _known: override the learned-command set. The curriculum derives it from the
    slug, but a COMMUNITY level declares its own `requires` + `teaches` (there is
    no curriculum position to read it from), so the loader and the tape validator
    pass it explicitly. None = the curriculum answer, unchanged.
    _draft: the `sharing.draft.Draft` this room was rendered from, when the forge
    opened it. It — not the room — is the level: fills, vocabulary and the
    metadata block live on it, and `:w` folds the room back into it and writes
    a level file. Absent for every ordinary level.
    _record: the forge's tape recorder — `{'tape': [...], 'error': ''}`. When set,
    every real keystroke is appended in tape notation and NOTHING is written to
    the player's save file: a recording take is a rehearsal, not a playthrough.
    The tape comes back on the result as 'tape'.
    """
    if _dungeon is not None:
        dungeon = _dungeon
        seed    = dungeon.seed or 0
    else:
        seed    = random.randint(0, 2**31)
        dungeon = _build_dungeon(level, seed, game_h=term.height - 8, admin=(player_name == 'admin'))
    room    = dungeon.room
    if player_name != 'admin':
        room.answer = ''

    _sp     = room.spawn_pos
    player  = Player(row=_sp[0], col=_sp[1])
    player.max_hp = progress.get('max_hp', 6)
    player.hp     = player.max_hp
    player.known_commands = list(_known) if _known is not None else _known_commands(level)
    if player_name == 'admin':
        player.known_commands = player.known_commands + ['admin', 'register']
    # On a boss level, the command its scroll gates stays LOCKED on entry — even
    # if a past playthrough already banked it in extras — until the player reads
    # this boss's scroll again (which re-adds it below, on chest loot).
    _gated = _SCROLL_DROPS.get(level, (None,))[0] if level_type(level) == 'boss' else None
    for _cmd in progress.get('extras', []):
        if _cmd != _gated and _cmd not in player.known_commands:
            player.known_commands = player.known_commands + [_cmd]
    # The Warden Eternal's hat — a permanent post-game unlock. Once looted it is
    # saved to progress; wearing it (`:set hat`) grants admin-like all-command
    # access in ANY level. The worn state persists across levels too.
    player.gold     = progress.get('gold', 0)
    player.has_hat  = progress.get('has_hat', False)
    player.hat_worn = player.has_hat and progress.get('hat_worn', False)
    if player.hat_worn and 'admin' not in player.known_commands:
        player.known_commands = player.known_commands + ['admin']
    if _record is not None:
        # A take is played under the level's DECLARED command set and nothing
        # else. The forge's author is the admin, and very likely wearing the
        # hat — both of which hand out the `admin` token that makes
        # `action_allowed` say yes to everything. Leave it in and the take
        # cheerfully records a key the level never declared, which then fails
        # for the first stranger who downloads it. Refusing here is the whole
        # value of recording by playing.
        player.known_commands = [c for c in player.known_commands if c != 'admin']
    dungeon.level_slug = level   # lets the renderer show the act's hint on bosses
    dungeon.forge      = _draft is not None   # → the authoring cheat-sheet

    # Remove heart containers already collected by this player.
    _collected = progress.get('collected_hearts', [])
    for _e in list(room.entities):
        if _e.kind == 'heart_container' and [level, _e.row, _e.col] in _collected:
            room.kill_entity(_e)

    # Post-game companion: the wizard's horse. Once the Warden Eternal is beaten he
    # waits in the First Cave (where you meet and name him); once named he follows
    # you into every level, save those flagged to bar him (see _horse_blocked).
    # …but never into a draft. A forge room is a level being written, and anything
    # standing in it at save time is written into the file (see
    # `format._TRANSIENT_KINDS`, which catches the ones already shipped).
    if (_draft is None and progress.get('warden_eternal', {}).get('complete')
            and not _horse_blocked(level, room)):
        if level == 'first_cave' or progress.get('horse_name'):
            _place_first_cave_horse(room)
            _hname = progress.get('horse_name')
            if _hname:                          # tag = his name → he follows (see _enemy_tick)
                for _e in room.entities:
                    if _e.kind == 'horse':
                        _e.tag = _hname

    budget  = Budget(room.budget or 20)

    key_buf       = ''
    message       = ''
    msg_ttl       = 0
    cmd_start_ans: tuple = (0, False)   # (answer_pos, answer_diverged) at start of current command
    undo_stack: list[tuple[int, int, int]] = []
    redo_stack: list[tuple[int, int, int]] = []
    edit_mode  = _start_edit
    ed_undo:   list = []
    ed_redo:   list = []
    replace_stack: list = []   # REPLACE-mode per-char restore records (Block F)
    recording_reg = None       # register currently being recorded into, or None
    macro_buf     = ''         # keystrokes captured for the in-progress recording
    macro_last    = None       # last register played (for @@)
    macro_pending: deque = deque()   # queued macro keystrokes awaiting playback
    macro_run_keys = 0         # keys replayed since last real keypress (recursion guard)
    _MACRO_MAX     = 10000
    count_tutorial_shown = False
    search_return_mode = None  # visual mode to resume after a / ? search launched from it
    block_ins = None           # live <C-v> I/c: {'rows': [...], 'col': c, 'buf': typed}
                               # — the typed run replays into every row on Esc
    insert_typed = ''          # chars typed this INSERT session — attached to
                               # last_change on Esc so '.' replays them (Vim-true)
    visual_r_pending = False   # visual r typed; the next key is the overstrike char
    insert_creg_pending = False  # INSERT <C-r> typed; next key names the register to paste
    insert_co_buf = None         # INSERT <C-o> active; accumulates one Normal command, then resumes INSERT
    search_creg_pending = False  # SEARCH <C-r> typed; next key names the register / <C-w> to insert
    last_saved_stars = progress.get(level, {}).get('stars', 0)
    won             = False  # win animation has been triggered
    _first_written_completion = False  # set on first :w/:wq that earns ≥1 star from 0
    pending_hearts: list = []  # heart containers grabbed this run, not yet written (:w/:wq commit)

    def _commit_hearts() -> None:
        """Persist heart containers grabbed this run into progress (max_hp + the
        collected list). Called by :w / :wq only — :q discards them."""
        if not pending_hearts:
            return
        ch = progress.setdefault('collected_hearts', [])
        for hp in pending_hearts:
            if hp not in ch:
                ch.append(hp)
        progress['max_hp'] = player.max_hp
        pending_hearts.clear()
    spotted_goblins: set = set()   # id(ent) of goblins the player has seen
    spotted_wardens: set = set()   # id(ent) of wardens the player has seen
    engaged_entities: set = set()  # id(ent) of entities currently co-located with player
    door_hint_shown: set = set()   # id(ent) of locked doors that showed "requires a key"
    door_open_hint_shown: set = set()  # id(ent) of locked doors that showed "type p"
    seal_door_col: int = -1   # set when seal_door is opened; seals the cell once player crosses
    seal_door_row: int = -1
    msg_pool: list = []            # combat messages for this turn (rotation buffer)
    msg_idx:  int  = 0             # current rotation index into msg_pool
    pool_ttl: int  = _MSG_ROTATE_TTL   # dwell per pool part; intros slow it to reading pace
    attack_flash_sym: str   = ''      # directional arrow; '' = no flash active
    attack_flash_pos: tuple = (0, 0)  # goblin cell to flash on
    attack_flash_on:  bool  = True    # True → show arrow, False → show normal g
    attack_flash_ttl: int   = 0

    def _attack_sym() -> str:
        return attack_flash_sym if (attack_flash_sym and attack_flash_on) else ''

    def _attack_pos() -> tuple | None:
        return attack_flash_pos if attack_flash_sym else None

    def _goblin_boom(r, c):
        """The :s/g/!/ egg: detonate the goblin at (r,c) with the real explosion
        animation, then remove it."""
        g = room.entity_at(r, c)
        iw_now     = _iw(term)
        game_h_now = term.height - 8
        vr = max(0, min(player.row - game_h_now // 2, room.rows - game_h_now))
        vc = max(0, min(player.col - iw_now     // 2, room.cols - iw_now))
        vr, vc = max(0, vr), max(0, vc)
        scr_r = 3 + (r - vr)
        scr_c = 1 + (c - vc) + _gutter_w(player)
        _explosion_animation(term, room, r, c, scr_r, scr_c, iw_now, game_h_now)
        if g is not None and g.kind == 'goblin':
            room.kill_entity(g)
        # Stand too close to the blast and it hurts — you can die by your own fire.
        _dist = abs(player.row - r) + abs(player.col - c)
        if _dist in _EXPL_DAMAGE:
            player.take_damage(_EXPL_DAMAGE[_dist])
        room.rebuild_indexes()

    def _detonate(ent, message):
        """Set off a dynamite charge at ent's cell: animate, damage nearby wood
        walls, and hurt the player by blast proximity (centre 1.5♥ → falls off).
        Returns (message, msg_ttl). Shared by step-on and cut-to-detonate."""
        expl_r, expl_c = ent.row, ent.col
        room.kill_entity(ent)
        iw_now     = _iw(term)
        game_h_now = term.height - 8
        vr = max(0, min(player.row - game_h_now // 2, room.rows - game_h_now))
        vc = max(0, min(player.col - iw_now     // 2, room.cols - iw_now))
        vr, vc = max(0, vr), max(0, vc)
        scr_r = 3 + (expl_r - vr)
        scr_c = 1 + (expl_c - vc) + _gutter_w(player)
        _render(message)
        _explosion_animation(term, room, expl_r, expl_c, scr_r, scr_c, iw_now, game_h_now)
        for _dr in range(-3, 4):
            for _dc in range(-3, 4):
                _dist = abs(_dr) + abs(_dc)
                if _dist not in _EXPL_DAMAGE:
                    continue
                _wr, _wc = expl_r + _dr, expl_c + _dc
                if (0 <= _wr < room.rows and 0 <= _wc < room.cols
                        and room.cells[_wr][_wc] == CellType.WOOD_WALL):
                    room.damage_wood_wall(_wr, _wc, _EXPL_DAMAGE[_dist])
        # The blast scorches any Warden in range — the minefield cuts both ways.
        for _w in list(room._entity_by_kind.get('warden', [])):
            if not _w.alive:
                continue
            _wdmg = _EXPL_DAMAGE.get(abs(_w.row - expl_r) + abs(_w.col - expl_c), 0)
            if not _wdmg:
                continue
            _w.hp -= _wdmg
            if _w.hp <= 0:
                room.kill_entity(_w)
                _remove_warden_shields(room)
                room.surveyor_threat = None
                _drop_key(room, _w.row, _w.col)          # keep the exit openable
                _push('The Warden is blown apart by his own minefield! A key drops. 🗝')
            else:
                _push(f'The blast scorches the Warden! ({_w.hp}/{_w.max_hp} HP)')
        pdist = abs(player.row - expl_r) + abs(player.col - expl_c)
        dmg   = _EXPL_DAMAGE.get(pdist, 0)
        if dmg:
            player.take_damage(dmg)
        if player.is_dead:
            return 'You set off a dynamite charge!  GAME OVER  (:e to reload)', 2
        return f'BOOM! Dynamite!  {_hearts_note(player.hp)}', 30

    # ── The Warden Surveyor's two-phase visual attack (Phase 1) ───────────────
    def _surveyor_warden():
        for e in room.entities:
            if e.alive and e.kind == 'warden' and e.tag == 'surveyor':
                return e
        return None

    def _surveyor_teleport(warden):
        """Leap the warden to a fresh cell — 60% inside a parenthetical — then
        plant the shield between him and the adventurer."""
        top, bot, l, r = _ws_bounds()
        paren = [p for p in _ws_paren_cells(room) if _ws_landable(room, player, *p)]
        anyc  = [(rr, c) for rr in range(top, bot + 1) for c in range(l, r + 1)
                 if _ws_landable(room, player, rr, c)]
        pool = paren if (paren and random.random() < 0.6) else (anyc or paren)
        if not pool:
            return
        room.move_entity(warden, *random.choice(pool))
        shield = next((e for e in room.entities if e.alive and e.kind == 'shield'), None)
        if shield:
            side = 1 if player.col >= warden.col else -1     # face the adventurer
            for sc in (warden.col + side, warden.col - side):
                if (l <= sc <= r and room.cells[warden.row][sc] == CellType.FLOOR
                        and not room.entity_at(warden.row, sc)):
                    room.move_entity(shield, warden.row, sc)
                    break

    def _surveyor_regen():
        """Phase-2 onset: the eaten verse regrows (reshuffled), then clear any
        fresh charge that landed on the player/warden/shield."""
        _dg.regen_surveyor_hall(room, random.Random(room.seed * 131 + 7))
        protect = {(player.row, player.col)}
        for e in room.entities:
            if e.alive and e.kind in ('warden', 'shield'):
                protect.add((e.row, e.col))
        room.entities = [e for e in room.entities
                         if not (e.kind == 'dynamite' and (e.row, e.col) in protect)]
        room.rebuild_indexes()

    def _surveyor_resolve(threat):
        """Detonate charges the selection crosses, erase the verse within it, and
        dock a heart if the adventurer didn't step out of the box."""
        nonlocal message, msg_ttl
        r0, r1, c0, c1 = threat['r0'], threat['r1'], threat['c0'], threat['c1']
        caught = (r0 <= player.row <= r1 and c0 <= player.col <= c1)
        for r in range(r0, r1 + 1):
            for c in range(c0, c1 + 1):
                ent = room.entity_at(r, c)
                if ent and ent.kind == 'dynamite':
                    message, msg_ttl = _detonate(ent, message)
            _ws_erase_row(room, r, c0, c1)
        if caught and not player.is_dead:
            player.take_damage(2)                            # 1 heart
            if player.is_dead:
                message, msg_ttl = 'The Warden erases you!  GAME OVER  (:e to reload)', 2
            else:
                message, msg_ttl = f"The Warden's selection erases you!  {_hearts_note(player.hp, remaining=False)}", 30

    def _surveyor_tick():
        warden = _surveyor_warden()
        last = getattr(room, 'surveyor_last_player', (player.row, player.col))
        room.surveyor_last_player = (player.row, player.col)   # remember for next tick
        if warden is None or (warden.row, warden.col) in room.fog_cells \
                or player.col < _dg._WS_TEXT_COL:
            return                                      # dormant until you've entered
        threat = getattr(room, 'surveyor_threat', None)
        step = threat.get('step') if threat else None
        anchor = {'r0': warden.row, 'r1': warden.row, 'c0': warden.col, 'c1': warden.col}
        if step == 'recover':
            # one tick to regain focus after being struck; no telegraph this beat
            room.surveyor_threat = None
        elif step is None:
            # v — enter visual mode: the anchor lands on his own cell
            room.surveyor_threat = {**anchor, 'step': 'aim'}
            _push("The Warden's eye opens — his gaze begins to span.")
        elif step == 'aim':
            if warden.hp > 3:
                # Phase 1 ($/0): he commits to the side you were on LAST turn
                c0, c1 = _ws_threat_span(warden.col, last[1])
                room.surveyor_threat = {'step': 'scoped', 'r0': warden.row,
                                        'r1': warden.row, 'c0': c0, 'c1': c1}
                _push('His sight sweeps your row — step clear!')
            else:
                # Phase 2 (/): one more wind-up beat — he searches for you
                room.surveyor_threat = {**anchor, 'step': 'search'}
                _push('The Warden searches for you...')
        elif step == 'search':
            # Phase 2 lock (@): the block aims true to where you are NOW
            r0, r1, c0, c1 = block_bounds((warden.row, warden.col),
                                          (player.row, player.col))
            room.surveyor_threat = {'step': 'scoped', 'r0': r0, 'r1': r1, 'c0': c0, 'c1': c1}
            _push('He frames you in a block — break out of it!')
        else:                                           # 'scoped' → cut (x)
            _surveyor_resolve(threat)
            room.surveyor_threat = None

    def _pool_msg() -> str:
        if not msg_pool:
            return ''
        n = len(msg_pool)
        return (f'({msg_idx+1}/{n}) ' if n > 1 else '') + msg_pool[msg_idx]

    def _save_progress(data: dict, who: str) -> None:
        """Persist progress — unless this is a recording take, which persists
        nothing.

        A take runs under the AUTHOR's own name, so an unguarded write here
        would not merely record a level nobody asked to have recorded: it would
        overwrite that player's real save with the throwaway progress dict the
        forge handed the take. Every write inside run_dungeon goes through this.
        """
        if _record is None:
            SM.save_progress(data, who)

    def _forge_rebuild(reseed: bool = False) -> str:
        """Re-render the open draft after a DIRECTIVE changed. Returns '' on
        success, or the reason it could not be built.

        A directive can be legal to write and impossible to grow — `:fill custom`
        with no `:vocab` behind it is the honest example. The build raises, and
        raising out of a command handler takes the whole game down with the
        author's unsaved room inside it. So the failure is caught, the previous
        room is left standing, and the caller undoes whatever it had already put
        on the level. Callers must therefore treat a non-empty return as "that
        did not happen".

        A fill is not a thing you can paint on: it grows its words at build time
        from the level's seed, so the only honest way to show an author what
        they just asked for is to build the level again and stand them back
        where they were. Cheap enough to do per command — this runs on `:fill`,
        never on a keystroke.

        It deliberately does NOT sync the room back first. Sync takes the fill
        list from the ROOM, which is one build behind, so syncing here would
        undo the very directive the caller just added. Callers capture the
        author's painting with an explicit `DRAFT.sync` BEFORE they touch the
        level, and then call this.
        """
        nonlocal dungeon, room, player, budget
        _r, _c = player.row, player.col
        try:
            _built = _draft.build(
                seed=random.randint(0, 2 ** 31 - 1) if reseed else None)
        except (ValueError, LF.LevelFormatError) as _exc:
            return str(_exc)
        dungeon = _built
        # Stand the author back in the room they are editing. `build` always
        # opens on the first — that is where a PLAYER starts — but the forge
        # shows whichever one `:room` last selected.
        dungeon.current_room = min(_draft.room_index, len(dungeon.rooms) - 1)
        room    = dungeon.room
        dungeon.name        = _draft.level.name
        dungeon.level_slug  = level
        dungeon.forge       = True
        room.passable_walls = edit_mode
        player.row = min(_r, room.rows - 1)
        player.col = min(_c, room.cols - 1)
        budget = Budget(room.budget or 20)
        return ''

    def _push(text: str) -> None:
        nonlocal pool_ttl
        if text not in msg_pool:
            msg_pool.append(text)
            pool_ttl = _MSG_ROTATE_TTL   # live events pace faster than an intro

    def _room_door() -> bool:
        """The DECLARATIVE room change: a level of several rooms, in order.

        Standing on the exit of any room but the last opens the next one, so
        that exit is a door and not the way out — which is why this is asked at
        the win check itself rather than in the per-turn ticks. A room's exit
        is reached and the level ends on the same instant, and a rule that ran a
        moment later would be answering a level that had already been won.

        A shut seal on the exit cell is what makes a door conditional; you cannot
        stand on stone, so there is no second condition to write here.
        """
        nonlocal room
        if edit_mode:
            # Painting is not walking. An author who drags the cursor over the
            # exit of the room they are building must not be carried into the
            # next one — `:room` is how you move between them deliberately, and
            # a room you arrived in by dragging is one you did not mean to open.
            return False
        _exit = getattr(room, 'exit_pos', None)
        if _exit is None or (player.row, player.col) != tuple(_exit):
            return False
        if not (getattr(room, 'advance_on_exit', False)
                and dungeon.current_room < len(dungeon.rooms) - 1):
            return False
        tape_state = (room.answer, room.answer_pos, room.answer_diverged)
        dungeon.current_room += 1
        room = dungeon.room
        player.row, player.col = room.spawn_pos
        # The tape is the LEVEL's, not the room's: one route walks them all,
        # so the karaoke sheet and how far along it the player is travel through
        # the door with them.
        room.answer, room.answer_pos, room.answer_diverged = tape_state
        undo_stack.clear()                 # each room keeps its own past
        redo_stack.clear()
        # Not narration of the door — the door is on screen. What is NOT is that
        # the room behind you took its undo stack with it.
        _push('The way closes behind you — that room is past mending.')
        return True

    def _content_ticks() -> None:
        nonlocal room                 # the Sanctum's gate swaps the live room
        """Run the buffer-content gate ticks (the plaque / votive / word gates that
        open the instant their text READS TRUE) and surface their messages. Called
        both in the per-turn dispatch AND on leaving INSERT/REPLACE (Esc), so an
        edit that completes a gate opens it THIS turn — no one-Normal-action lag."""
        # The two DECLARATIVE gates run for every level, shipped or downloaded:
        # they are driven by fields on the room, so they no-op unless something
        # placed them. Every rule below this pair is slug-keyed because it was
        # written before there was a way to say it in a file.
        for _m in _drop_tick(room, player):
            _push(_m)
        for _m in _seal_tick(room, player):
            _push(_m)
        if level == 'quartermaster':
            for _m in _quartermaster_tick(room, player):
                _push(_m)
        if level == 'warden_manifold':
            for _m in _warden_manifold_tick(room, player, budget.spent):
                _push(_m)
        if level == 'warden_scrivener':
            for _m in _warden_scrivener_tick(room, player, budget.spent):
                _push(_m)
        if level == 'change_extension':
            _ce_y_plaque_tick(room, player)
            _tw = getattr(room, '_sc_twinkle', None)
            if _tw:                       # the plaque followed the paste: glitter
                _sc_twinkle_animation(term, room, player, _tw, _iw(term), term.height - 8)
                room._sc_twinkle = []
        if level == 'indentation_sanctum':
            for _m in _indentation_sanctum_tick(room, player):
                _push(_m)
        if level == 'hall_of_echoes':
            for _m in _hall_of_echoes_tick(room, player):  # per-room south seal
                _push(_m)
            # Through an open seal: the gauntlet advances to the next chamber.
            if ((player.row, player.col) == tuple(room.exit_pos)
                    and dungeon.current_room < len(dungeon.rooms) - 1
                    and room.cells[room.exit_pos[0]][room.exit_pos[1]]
                        != CellType.WALL):
                dungeon.current_room += 1
                room = dungeon.room
                player.row, player.col = room.spawn_pos
                undo_stack.clear()              # each chamber keeps its own past
                redo_stack.clear()
                # The open passage is on screen; what is NOT is that the chambers
                # keep separate undo stacks, so the one behind you is now final.
                _push('The passage closes behind you — that chamber is past '
                      'mending.')
        if level == 'paragraph_enclosure':
            for _m in _paragraph_enclosure_tick(room, player):
                _push(_m)
        if level == 'waypoint_sanctum':
            # The waking stone: plugh's scripted fog lifts when the ? leg
            # lands the player inside pocket 1 (fogged text is unsearchable,
            # so ?plugh from the spawn finds nothing until then).
            _pf = getattr(room, '_wp_plugh_fog', None)
            if (_pf and room.fog_cells & _pf and player.row == 2
                    and _dg._WP_PKT1_SPAN[0] <= player.col <= _dg._WP_PKT1_SPAN[1]):
                room.fog_cells -= _pf
                _push('In the pocket\'s shadow, a second word wakes.')
        if level == 'wet_ink':
            for _m in _wet_ink_tick(room, player):    # braziers, fuel gate, fog
                _push(_m)
        if level == 'warden_eternal':
            for _m in _warden_eternal_tick(room, player):
                _push(_m)
        if level == 'gauntlet':
            for _m in _gauntlet_tick(room, player):
                _push(_m)
            _tw = getattr(room, '_sc_twinkle', None)
            if _tw:                       # the goal column re-rights: glitter
                _sc_twinkle_animation(term, room, player, _tw, _iw(term), term.height - 8)
                room._sc_twinkle = []
        if level == 'grandmasters_sanctum' and dungeon.current_room == 0:
            # The descent needs the SEAL OPEN, not just the position: a
            # jump (G on the collapsed gate row) can park the player past
            # a barred seal — standing beyond stone is lawful, passing
            # through it is not.
            if (player.row == room.exit_pos[0]
                    and player.col >= room.exit_pos[1]
                    and room.cells[room.exit_pos[0]][room.exit_pos[1] - 1]
                        != CellType.WALL
                    and len(dungeon.rooms) > 1):
                dungeon.current_room = 1                 # through the gate
                room = dungeon.room
                player.row, player.col = room.spawn_pos
                undo_stack.clear()                       # gallery snapshots stay behind
                redo_stack.clear()
                _push('The Grandmaster withdraws before you into the arena. '
                      'His shadow does not hurry.')
        if level == 'grandmasters_sanctum' and dungeon.current_room == 1:
            for _m in _grandmasters_arena_tick(room, player):
                _push(_m)
        if level == 'sculpting_chambers':
            for _m in _sculpting_chambers_tick(room, player):
                _push(_m)
            _tw = getattr(room, '_sc_twinkle', None)
            if _tw:
                _sc_twinkle_animation(term, room, player, _tw, _iw(term), term.height - 8)
                room._sc_twinkle = []

    def _render(msg='', **kw):
        """Render the dungeon. Drops the repeated (term, dungeon, player, budget) prefix
        and defaults attack_pos/attack_sym to the live attack-flash state; any other
        args (heart_flash, …) pass through."""
        kw.setdefault('attack_pos', _attack_pos())
        kw.setdefault('attack_sym', _attack_sym())
        kw.setdefault('recording', recording_reg or '')   # Vim's showmode indicator
        kw.setdefault('companion', progress.get('horse_name', '')
                      if any(e.kind == 'horse' for e in dungeon.room.entities) else '')
        # Stone-law fog re-reveal (auto_fog rooms only): what the eye can now
        # reach — through opened doors, over water — sheds its fog per frame.
        _auto_fog_tick(dungeon.room, player.row, player.col)
        render_all(term, dungeon, player, budget, msg, **kw)
        # Glyphs still in the air from an earlier reflow, painted over the top of
        # the frame that just landed. Nothing here sleeps — the fall advances on
        # the wall clock, so typing through it neither stalls nor skips it.
        _draw_falls(term, dungeon.room, player)

    def _horse_here() -> bool:
        """Is the horse in the room? The saddle registers ride with him."""
        return any(e.kind == 'horse' for e in dungeon.room.entities)

    def _action_allowed(action, known, edit_mode=False):
        # Wrap the pure guard with the live horse state so the saddle registers
        # are gated on the horse's presence (blocked on boss / horse-free levels).
        return _action_allowed_raw(action, known, edit_mode, horse_present=_horse_here())

    def _guard_message(action, known=()):
        return _guard_message_raw(action, known, horse_present=_horse_here())

    def _blocked(action) -> bool:
        """A gated command the player hasn't learned: explain why, render, and return
        True so the call site reads `if not _action_allowed(...) and _blocked(action): continue`."""
        nonlocal message, msg_ttl
        _push(_guard_message(action, player.known_commands))
        message = _pool_msg(); msg_ttl = _MSG_ROTATE_TTL
        _render(message)
        return True

    def _animate_reflow_falls() -> None:
        """Queue the void-fall / drown animations the last reflow op left behind
        (room._last_void_falls / _last_drowns) and set the banner message.

        Queue, not play: _draw_falls tumbles them off the clock, so the render
        goes AFTER the queueing — otherwise the first frame of the drop would
        not appear until the player's next keystroke."""
        nonlocal message, msg_ttl
        if room._last_void_falls:              # a glyph went over the brink
            _play_void_falls(term, dungeon, room, player)
            _render(message)
            message = 'Over the brink — into the void it tumbles!'
            msg_ttl = 25
        if room._last_drowns:                  # a wave of water swept an entity away
            _queue_falls(room, list(room._last_drowns),
                         _DROWN_HOT, _DROWN_COLD)
            room._last_drowns = []
            _render(message)
            message = 'A wave sweeps it away into the void!'
            msg_ttl = 25

    # ── :s / :g — buffer-shifting + confirm (c flag) callbacks ──────────────
    def _sub_insert_row(at):
        _insert_blank_row(room, at + 1, at, player)

    def _sub_delete_row(at):
        return remove_row(room, at, player)

    def _sub_confirm(row, c0, c1):
        """The :s/c flag: show the match under the cursor, ask y/n/a/q/l."""
        player.row, player.col = row, c0
        _render('replace with (y)es (n)o (a)ll (q)uit (l)ast?')
        while True:
            k = term.inkey(timeout=0.2)
            if not k:
                continue
            if k.name == 'KEY_ESCAPE':
                return 'q'
            ch = str(k).lower()
            if ch in 'ynaql':
                return ch

    def _forge_check():
        """The Spellwright's Forge: dissolve the sanctum seal once the spellwork RINGS
        TRUE across all three chambers — every line that must REMAIN reads its exact text
        (Chamber A mended old→new with /g, Chamber B's two verses mended pale→pure, B's
        TRUE pale line untouched, Chamber C's sacred lines intact) AND no cursed line
        survives.  Testing for the exact text (not merely the absence of 'old'/'cursed')
        is deliberate: it forbids the snip mangle (`:%s/l//g` …) that once satisfied a bare
        substring check for pennies, and it makes a whole-buffer `:%s/pale/pure/g` self-
        defeating — it would wreck B's protected line, so its exact text would go missing."""
        seal = getattr(room, '_forge_seal', None)
        if seal is None:
            return
        texts  = [_subst.line_text(room, r)[0] for r in range(room.rows)]
        mended = getattr(room, '_forge_mended', None) or []
        # The WHOLE phrase must appear (substring tolerates the line's leading indent); a
        # one-letter mangle ('the od gods…') or a half-mended /g-less ward can never match.
        #
        # ONE LINE CANNOT ANSWER TWO DEMANDS. Chamber B's verses are 'the mouse
        # ran up the clock' and 'the mouse ran up the clock again' — the first is
        # a SUBSTRING of the second, so a bare `any()` let the mended second
        # verse satisfy both and the first verse never had to be touched at all.
        # That is what made `&` skippable on the level whose whole job is
        # `:s` / `&` / `:g` (found by `sharing jumpgolf`, closed 2026-08-03).
        # Each demand must claim its OWN line: longest first, because a longer
        # phrase can only be housed by the longer line, and letting it choose
        # first is what leaves the right line for the shorter one.
        unclaimed = list(texts)
        for m in sorted(mended, key=len, reverse=True):
            hit = next((i for i, t in enumerate(unclaimed) if m in t), None)
            if hit is None:
                return                                # a line is unmended, mangled, or wrecked
            unclaimed.pop(hit)
        purge = getattr(room, '_forge_purge', 'curse')
        if any(purge in t for t in texts):
            return                                    # a purge line still stands
        sr, sc = seal
        if room.cells[sr][sc] == CellType.WALL:
            room.cells[sr][sc] = CellType.FLOOR
        room._forge_seal = None
        _push('The wards dissolve — the spellwork rings true. The way opens!')

    def _ledger_check():
        """The Culling Ledger (v3). Each tick, statelessly:
        1. once door ONE is open, part the water — the dark ledger goes
           underwater — readable, still unwalkable. This is design, not an engine
           rule: nothing stops a fogged line being culled, so the ledger is
           revealed first to keep the :v cull a reading task, not a guess;
        2. once the ledger reads EXACTLY its true lines, in order, the cold
           corridor brazier catches the verdant lines' fire and its light
           unveils the exit pocket (door TWO still wants the key).
        (Key stashing is dead GLOBALLY: a key pasted anywhere but onto a
        locked door is lost — see the keys-are-slippery paste law.)
        Blank residue rows are ignored — the :s-blanking longhand stays a
        lawful 1★ route; forcing is by PAR."""
        keeps = getattr(room, '_ledger_keeps', None)
        if keeps is None:
            return
        # No ledge below the corridor: a linewise paste there clones the
        # corridor WITHOUT its doors — a bridge around door two. The void
        # swallows it (stateless; the paster snaps back to the corridor).
        if room.exit_pos is None:
            return                      # the corridor itself was culled — undo it
        exit_row = room.exit_pos[0]
        for r in range(room.rows - 2, exit_row, -1):
            if any(room.cells[r][c] == CellType.FLOOR for c in range(room.cols)):
                from vimny.engine.reflow import remove_row as _rm_row
                if _rm_row(room, r, player):
                    if player.row >= r:
                        player.row = exit_row
                    # Told once: the fall is animated, so a repeat only narrates
                    # what the player is already watching.
                    if not getattr(room, '_cl_ledge_told', False):
                        room._cl_ledge_told = True
                        _push('The void swallows the false ledge!')
        _chasm_resubmerge()             # a :t/:m'd row must never become footing
        cor = _subst._last_standable_row(room)     # the corridor rides up
        door1_shut = any(e.kind == 'locked_door' and e.alive
                         and e.col < _dg._CL_BRZ_COL
                         for e in room.entities)
        lit = getattr(room, '_ledger_lit', None)
        if not door1_shut:
            # THE WATER PARTS (stateless, re-asserted every tick — the
            # unlock's own reveal flood strips too much): everything ABOVE the
            # stone course goes underwater (readable, unwalkable); the
            # corridor lights up to the boss door; past it stays dark until
            # the brazier burns.
            for fr in range(1, cor - 1):
                for fc in range(room.cols):
                    if room.cells[fr][fc] in (CellType.FLOOR, CellType.WATER):
                        room.fog_cells.add((fr, fc))
                        room.underwater_cells.add((fr, fc))
            sd_col = _dg._CL_SEALDOOR[1]
            for fc in range(room.cols):
                cell = (cor, fc)
                if fc < sd_col:
                    room.fog_cells.discard(cell)   # lit corridor, up to the seal
                    room.underwater_cells.discard(cell)
                elif not lit and room.cells[cor][fc] in (CellType.FLOOR,
                                                         CellType.CORRIDOR):
                    room.fog_cells.add(cell)       # the dark holds past the seal
                    room.underwater_cells.discard(cell)
            # (No message: the reveal is on screen — narration would only
            # distract from what the player can already see.)
        if lit is not False:
            return                                 # already lit (or not this level)
        texts = []
        for r in range(room.rows):
            t = _subst.line_text(room, r)[0]
            for junk in ('○', _dg._QM_FLAME, _dg._QM_EMBERS):
                t = t.replace(junk, '')
            if t.strip():
                texts.append(t.strip())
        if texts != list(keeps):
            return
        room._ledger_lit = True
        for ru in list(room._char_runs_by_row.get(cor, [])):
            if ru.kind == 'pedestal':              # the cold brazier catches fire
                room.remove_char_run(ru)
        room.add_char_run(CharRun(cor, _dg._CL_BRZ_COL, (_dg._QM_FLAME,), 'flame'))
        for e in [e for e in room.entities         # the boss door burns open
                  if e.kind == 'seal_door' and e.alive]:
            room.remove_entity(e)
        room.fog_cells = {(fr, fc) for (fr, fc) in room.fog_cells
                          if fr != cor}            # firelight unveils the way
        room.rebuild_indexes()
        _push('The braziers answer as one — firelight finds the way out!')

    def _chasm_resubmerge():
        """The chasm law, stateless: any BARE floor above the gallery (a row a
        :t/:m just shelved arrives unfogged) is re-sunken each turn — the far
        bank never becomes footing."""
        gal = _subst._last_standable_row(room)
        for r in range(1, gal - 1):     # gal-1 = the wall/water course (its gap
            if any(room.cells[r][c] in (CellType.FLOOR, CellType.CORRIDOR)  # perch
                   for c in range(room.cols)):      # stays lawful footing)
                for c in range(room.cols):
                    if (room.cells[r][c] == CellType.FLOOR
                            and (r, c) not in room.fog_cells):
                        room.fog_cells.add((r, c))
                        room.underwater_cells.add((r, c))

    def _shelving_tick():
        """The Shelving Room: re-submerge fresh shelf rows; each mended misfiling
        grinds back its own gallery bolt (STATELESS, any order); the seal
        parts once the whole round reads true — indent included, blank rows
        ignored. No plaque: the round is an echo, and the shelf's own sound
        pairs carry the convention (every voice twice, the echo a step
        deep)."""
        targets = getattr(room, '_shr_targets', None)
        if targets is None:
            return
        _chasm_resubmerge()
        gal = _subst._last_standable_row(room)
        lines = []                       # (indent, stripped text), shelf order
        for r in range(1, gal - 1):
            t = _subst.line_text(room, r)[0].rstrip()
            if t.strip():
                lines.append((len(t) - len(t.lstrip()), t.strip()))
        calls = _dg._SHR_CALLS
        texts = [t for _, t in lines]

        def paired(call):                # the voice's rows read call-then-echo
            return tuple(i for i, t in lines if t == call) == (0, 2)

        collapsed = [t for i, t in enumerate(texts)
                     if i == 0 or texts[i - 1] != t]
        conds = (collapsed == list(calls),        # voices adjacent, song order
                 paired(calls[2]),                # the Sonnez echo at its step
                 texts.count(calls[3]) == 2,      # the last echo shelved
                 paired(calls[3]))                # ...and at its step
        for ok, dc in zip(conds, _dg._SHR_BOLT_COLS):
            is_open = room.cells[gal][dc] != CellType.WALL
            if ok and not is_open:
                room.cells[gal][dc] = CellType.FLOOR
                _push('A voice finds its shelf — a bolt grinds back!')
            elif not ok and is_open and (player.row, player.col) != (gal, dc):
                room.cells[gal][dc] = CellType.WALL    # undone — it re-bars
        if getattr(room, '_shr_seal_col', None) is None:
            return
        full = [t.rstrip() for r in range(1, gal - 1)
                for t in (_subst.line_text(room, r)[0],) if t.rstrip()]
        if full != list(targets):
            return
        sc = room._shr_seal_col
        if room.cells[gal][sc] == CellType.WALL:
            room.cells[gal][sc] = CellType.FLOOR
        _unveil = {(fr, fc) for (fr, fc) in room.fog_cells
                   if fr == gal and fc > sc}
        room.fog_cells -= _unveil                  # unveil the pocket —
        room.underwater_cells -= _unveil                 # its haze lifts with it
        room._shr_seal_col = None
        _push('The round sings in order, echo under call. The way opens!')

    def _refrain_tick():
        """The Refrain Vault (London Bridge): re-submerge the torn chasm, then
        open the seal once the song below the water reads EXACTLY as it should
        — every "falling up" mended to "falling down", the build and key
        verses untouched ("up" is TRUE there: a blanket :%s wrecks them), and
        the torn final line laid down on walkable floor (a :t'd chasm slab
        arrives sunken and cannot serve). Blank rows are ignored."""
        true_song = getattr(room, '_rv_true', None)
        if true_song is None:
            return
        wtr = next((r for r in range(room.rows)
                    if any(room.cells[r][cc] == CellType.WATER
                           for cc in range(room.cols))), None)
        if wtr:
            for r in range(1, wtr):
                for cc in range(room.cols):
                    if (room.cells[r][cc] == CellType.FLOOR
                            and (r, cc) not in room.fog_cells):
                        room.fog_cells.add((r, cc))
                        room.underwater_cells.add((r, cc))
        if getattr(room, '_rv_seal_col', None) is None or wtr is None:
            return
        # Band the shut seal as stonework; derived here rather than at build
        # because its row rides exit_pos through the :t row inserts.
        room.sealed_cells = {(room.exit_pos[0], room._rv_seal_col)}
        sung = []
        for r in range(wtr + 1, room.rows - 1):
            t = _subst.line_text(room, r)[0].strip()
            if t:
                sung.append((t, any(room.is_passable(r, cc)
                                    for cc in range(room.cols))))
        if [t for t, _ in sung] != list(true_song):
            return
        if not all(on_floor for _, on_floor in sung):
            return                              # sung, but not on the floor
        sr, sc = room.exit_pos[0], room._rv_seal_col
        if room.cells[sr][sc] == CellType.WALL:
            room.cells[sr][sc] = CellType.FLOOR
        room.fog_cells = {(fr, fc) for (fr, fc) in room.fog_cells
                          if not (fr == sr and fc > sc)}   # unveil the pocket
        room._rv_seal_col = None
        _push('The song stands whole, verse for verse. The way opens!')

    def _advance_answer(tok: str):
        """Admin karaoke: advance the answer tape by one typed key.

        `tok` is a tape token, so keys with no printable form arrive already
        spelled Vim's way (`_TAPE_ENTER`, `_TAPE_ESC`) and are matched WHOLE —
        `<CR>` is four glyphs on the sheet but one keystroke, and matching it a
        character at a time would let the playhead stop half way inside a token.
        Plain spaces in the tape are visual separators, stripped for matching.
        Used for COMMAND-mode typing — the NORMAL-mode tracker at the top of the
        loop never sees `:`-command chars — mirroring the INSERT-mode advance.
        Caller guarantees admin + a live tape."""
        if room.answer_diverged:
            return
        if tok == ' ':
            tok = _TAPE_SPACE             # a TYPED space: the tape marks it <Space>
        _ap = room.answer.replace(' ', '')
        if room.answer_pos < len(_ap):
            if _ap.startswith(tok, room.answer_pos):
                room.answer_pos += len(tok)
            else:
                room.answer_diverged = True

    # ── The Archivist's Library — reload loop + reckoning ───────────────────
    def _lib_w():
        gut = 0 if getattr(player, 'number_mode', 'none') == 'none' else 4
        return max(12, _iw(term) - gut)

    def _lib_relayout():
        _dg._lib_layout(room, _lib_w())
        if player.col >= room.cols:
            player.col = room.cols - 1

    def _lib_sync():
        # Re-tighten the page frame to the viewport whenever its width changes.
        if level == 'archivists_library' and getattr(room, '_lib_w', None) != _lib_w():
            _lib_relayout()

    def _lib_vandalize_step():
        # One pass of the ransacking, across the per-row runs: pull books off a few
        # full shelves (▤→□) — but leave plenty standing — and pile the tables with a
        # MIX of stacks (≡) and open books (◫).
        if not room.char_runs:
            return
        syml  = [list(ru.symbols) for ru in room.char_runs]
        shelf = [(r, j) for r, s in enumerate(syml) for j, ch in enumerate(s) if ch == '▤']
        books = [(r, j) for r, s in enumerate(syml) for j, ch in enumerate(s) if ch in ('≡', '◫')]
        spill = [(r, nb) for r, j in books for nb in (j - 1, j + 1)
                 if 0 <= nb < len(syml[r]) and syml[r][nb] == ' ']
        if len(shelf) > 30:                       # stop once half the shelves are bare
            for r, j in random.sample(shelf, min(len(shelf), random.randint(1, 3))):
                syml[r][j] = '□'
        for r, j in random.sample(spill, min(len(spill), random.randint(1, 3))):
            syml[r][j] = random.choice(['≡', '◫', '◫'])   # a mix, leaning open
        room.char_runs = [CharRun(ru.row, ru.col, tuple(syml[r]), ru.kind)
                          for r, ru in enumerate(room.char_runs)]
        room.rebuild_indexes()

    def _lib_scramble():
        # The vandal at work: a fresh page, then the Archivist darts all over it,
        # ransacking some shelves and cluttering the tables, in front of the reader.
        if not getattr(term, 'is_a_tty', False) or not room.char_runs:
            return
        import time as _t
        _lib_relayout()
        arch = next((e for e in room.entities if e.kind == 'archivist'), None)
        for _f in range(12):
            _lib_vandalize_step()
            if arch is not None:
                spots = [ru.col + j for ru in room.char_runs
                         for j, ch in enumerate(ru.symbols) if ch in ('▤', '□', '◫', '≡')]
                if spots:
                    arch.col = random.choice(spots)
                    room.rebuild_indexes()
            _render('')
            _t.sleep(0.05)

    def _lib_form_folio():
        # Morph the current page into the new folio in front of the reader: the
        # Archivist darts about, pulling books off the shelves to pile the tables with
        # the folio's glyphs. (Skipped headless — just settle on the folio.)
        if not getattr(term, 'is_a_tty', False) or not room.char_runs:
            _lib_relayout()
            return
        import time as _t
        cur = [list(ru.symbols) for ru in room.char_runs]
        _lib_relayout()                               # build the target folio
        tgt = [list(ru.symbols) for ru in room.char_runs]
        if len(cur) != len(tgt) or any(len(a) != len(b) for a, b in zip(cur, tgt)):
            return                                    # structure mismatch → already there
        work = [c[:] for c in cur]                    # start from the old page
        for i, ru in enumerate(room.char_runs):
            room.char_runs[i] = CharRun(ru.row, ru.col, tuple(work[i]), ru.kind)
        diff = [(i, j) for i in range(len(cur)) for j in range(len(cur[i]))
                if cur[i][j] != tgt[i][j]]
        random.shuffle(diff)
        arch = next((e for e in room.entities if e.kind == 'archivist'), None)
        frames, per = 12, max(1, -(-len(diff) // 12))
        for f in range(frames):
            for i, j in diff[f * per:(f + 1) * per]:
                work[i][j] = tgt[i][j]
            for i, ru in enumerate(room.char_runs):
                room.char_runs[i] = CharRun(ru.row, ru.col, tuple(work[i]), ru.kind)
            if arch is not None:
                arch.col = random.randrange(1, max(2, room.cols - 1))
            room.rebuild_indexes()
            _render('')
            _t.sleep(0.05)
        _lib_relayout()                               # settle exactly on the folio

    def _lib_reload(force):
        if getattr(room, 'lib_hostile', False):
            return                                    # no leafing while he hunts you
        if getattr(room, 'lib_done', None):
            _push('The library is whole again — nothing left to reload.')
            return
        if not force:
            player.error = 'E37: No write since last change (add ! to override)'
            return
        room.lib_idx  = (room.lib_idx + 1) % len(room.lib_seq)
        room.lib_view = 'leaf'
        _lib_form_folio()
        _push('"library" 1 line  --reloaded--')

    def _lib_file(name):
        if getattr(room, 'lib_done', None) or getattr(room, 'lib_hostile', False):
            return
        if room.lib_idx < 0 or getattr(room, 'lib_view', 'catalog') != 'leaf':
            _push('No manuscript open — press  :e!  to leaf to one.')
            return
        room.lib_filed[name] = room.lib_seq[room.lib_idx]['suit']
        room.lib_view = 'catalog'                 # back to the floor — the stack fills in
        _lib_relayout()
        _push(f'"{name}" [New] 1 line written')
        if len(room.lib_filed) >= 4:              # four files named → the reckoning
            if all(room.lib_filed.get(s) == s for s in _dg._LIB_SUITS):
                _lib_win()                        # the four folios are cleanly archived
            else:
                _lib_strike('"So YOU\'RE the vandal! I\'ll deal with you MYSELF!"')

    def _lib_finale():
        room.lib_done = 'win'
        _lib_relayout()                          # draw the restored-library page + the desk
        # Lay the rewards just behind the Archivist's desk (to its left); he settles
        # back beside it (see _enemy_tick), to the right, clear of the chests.
        dc = room._lib_desk_col
        room.add_entity(Entity(kind='chest_scroll', row=0, col=dc - 2, scroll_id='display_move'))
        room.add_entity(Entity(kind='chest_scroll', row=0, col=dc - 4, scroll_id='edit_name'))
        room.add_entity(Entity(kind='exit',         row=0, col=dc - 6))
        room.rebuild_indexes()

    def _lib_win():
        _lib_finale()
        _push("Great Vim! You've gone and cleanly archived the right folios!")
        _push('Help yourself to anything in those chests over there.')

    _LIB_BRIEF = ["Great Vim — you've fixed my library!",
                  'Some of my folios are still missing... a vandal is about...',
                  'Might I trouble a young reader to seek them out? My old eyes fail me so.']
    _LIB_W11   = 'W11: Warning: File "library" has changed since editing started'

    def _lib_brief_step(near):
        # Post-wrap brief: line 1 on approach, each later line on the next step, then
        # the Archivist tears into the shelves (scramble) and Vim warns W11.
        d = room.lib_dlg
        if d == 0:
            if near:
                room.lib_dlg, room.lib_dlg_col = 1, player.col
                _push(_LIB_BRIEF[0])
        elif d < 3:
            if player.col != room.lib_dlg_col:
                room.lib_dlg, room.lib_dlg_col = d + 1, player.col
                _push(_LIB_BRIEF[d])
        elif d == 3:
            if player.col != room.lib_dlg_col:
                room.lib_dlg      = 4          # the editing begins
                room.lib_step_col = player.col
                room.lib_steps    = 0
                room.lib_scramble_at = random.randint(6, 12)
                _lib_scramble()               # he ransacks the shelves, in front of you
                player.error = _LIB_W11       # ...and Vim warns the file changed
        # Linger in the hall without reloading and he ransacks it again — only THEN
        # (right after a scramble) does the red W11 warning appear.
        if room.lib_dlg >= 4 and player.col != getattr(room, 'lib_step_col', player.col):
            room.lib_step_col = player.col
            room.lib_steps += 1
            if room.lib_steps >= room.lib_scramble_at:
                room.lib_steps = 0
                room.lib_scramble_at = random.randint(6, 12)
                _lib_scramble()
                player.error = _LIB_W11

    def _lib_strike(line):
        # The Archivist turns on the player and GIVES CHASE (he hunts you down the hall
        # with gj/gk and strikes when adjacent — see _enemy_tick + the combat block).
        if getattr(room, 'lib_done', None) or getattr(room, 'lib_hostile', False):
            return
        room.lib_hostile = True
        room.lib_view    = 'catalog'      # back to the hall for the chase
        _lib_relayout()
        _push(line)

    if _start_edit:
        room.passable_walls = True
        if 'editor' not in player.known_commands:
            player.known_commands = player.known_commands + ['editor']

    if level in _LEVEL_INTROS:
        message, msg_ttl = _LEVEL_INTROS[level]
        # Intros are prose and routinely outrun the bar, which would clip them to
        # an ellipsis. Wrap to the live terminal width and hand the parts to the
        # rotation pool, which numbers them (1/3…) and cycles at reading pace.
        _intro_parts = _wrap_message(message, _iw(term))
        if len(_intro_parts) > 1:
            msg_pool.extend(_intro_parts)
            pool_ttl = _INTRO_ROTATE_TTL
            message  = _pool_msg()
    # A forge NOTICE (a `:play` rehearsal carrying a validator warning) opens the
    # banner: the author is standing in the very room it names, which is the whole
    # point of moving it off the bench. It leads the rotation and dwells at intro
    # pace so it is read, not clipped.
    if _notice:
        msg_pool.insert(0, _notice)
        msg_idx  = 0
        message  = _notice
        msg_ttl  = _INTRO_ROTATE_TTL
        pool_ttl = _INTRO_ROTATE_TTL

    # Return to the First Cave wearing the Warden's hat, and the stone knows you.
    if level == 'first_cave' and getattr(player, 'has_hat', False):
        msg_pool.clear()          # this greeting REPLACES the intro; drop its parts
        pool_ttl = _MSG_ROTATE_TTL
        message = "You've walked these stones before, haven't you? Welcome back, master."
        msg_ttl = _MSG_ROTATE_TTL

    def _room_has_water() -> bool:
        return any(ct == CellType.WATER for cells_row in room.cells for ct in cells_row)

    any_water     = _room_has_water()
    last_activity = time.time()

    def _goblin_msg(base: str) -> str:
        """Append 'Cut them down!' the very first time goblins are ever spotted."""
        if not progress.get('flags', {}).get('seen_goblins'):
            progress.setdefault('flags', {})['seen_goblins'] = True
            return base + ' Cut them down!'
        return base

    def _goblin_sighting(n: int) -> str:
        """Base sighting line for n newly-spotted goblins — a horde once it's > 9."""
        if n == 1:
            return 'You spotted a goblin!'
        if n > 9:
            return 'You see a goblin horde!'
        return f'You see {n} goblins!'

    # Spot any enemies already visible at level entry
    _entry_goblins = [e for e in room._entity_by_kind.get('goblin', [])
                      if e.alive and (e.row, e.col) not in room.fog_cells]
    for e in _entry_goblins:
        spotted_goblins.add(id(e))
    if _entry_goblins:
        if level == 'warden_pathfinder':
            # Two echoes disguised as the Warden — suppress the goblin count. The player
            # sees a few red Ws. All echoes auto-unmask after the verse collapse.
            msg_pool.append('You see a myriad of Wardens!')
        else:
            msg_pool.append(_goblin_msg(_goblin_sighting(len(_entry_goblins))))
    for e in room._entity_by_kind.get('warden', []):
        if e.alive and (e.row, e.col) not in room.fog_cells:
            spotted_wardens.add(id(e))
            msg_pool.append('You spotted a Warden!')
    if msg_pool:
        message = _pool_msg()
        msg_ttl = pool_ttl     # the pool may hold intro parts; don't clip part 1 to combat pace

    if level == 'archivists_library':
        _lib_relayout()                          # fit the page frame to the real viewport
    # Prime the content gates before the FIRST frame: the ticks are what register
    # room.sealed_cells, so without this the bands only appear once the player has
    # pressed a key. Their messages are discarded — nothing has happened yet, and
    # the level's own intro owns the banner.
    _pool_save, _msg_save, _ttl_save = msg_pool[:], message, msg_ttl
    _content_ticks()
    msg_pool[:], message, msg_ttl = _pool_save, _msg_save, _ttl_save
    _render(message)

    while True:
        if level == 'archivists_library':
            _lib_sync()                          # re-tighten the frame on terminal resize
        # Macro playback: drain queued keystrokes before reading the terminal.
        if macro_pending:
            macro_run_keys += 1
            if macro_run_keys > _MACRO_MAX:
                macro_pending.clear()
                macro_run_keys = 0
                budget.frozen = False
                _push('Macro aborted (too long / recursion).')
                _render(_pool_msg())
                continue
            key = _synth_key(macro_pending.popleft())
            from_macro = True
        else:
            key = term.inkey(timeout=0.1)
            from_macro = False
            macro_run_keys = 0
        budget.frozen = from_macro            # replayed keys don't re-charge budget

        # Macro recording: bare 'q' in NORMAL stops; otherwise capture real keys.
        if recording_reg is not None and not from_macro:
            if (player.mode == Mode.NORMAL and not key_buf
                    and not key.is_sequence and str(key) == 'q'):
                # A macro IS a register: `qa` clobbers whatever text "a held.
                _reg_record(player, recording_reg, macro_buf)
                recording_reg = None
                macro_buf = ''
                if player_name == 'admin' and room.answer:
                    _advance_answer('q')    # the stop-q is a tape token too
                _render(message)
                continue
            rc = _record_char(key)
            if rc is not None:
                macro_buf += rc

        prev_message = message
        if player.is_dead:
            message = '** GAME OVER ** Type  :e  to re-load the dungeon.'
            msg_ttl = 2
        elif msg_ttl > 0:
            msg_ttl -= 1
            if msg_ttl == 0:
                if msg_pool:
                    msg_idx = (msg_idx + 1) % len(msg_pool)
                    message = _pool_msg()
                    msg_ttl = pool_ttl
                else:
                    message = ''

        if not key:
            water_active    = any_water and (time.time() - last_activity < _WATER_SETTLE_SECS)
            overlap_active  = room.entity_at(player.row, player.col) is not None
            needs_render    = (message != prev_message or water_active
                               or overlap_active
                               or bool(getattr(room, '_falling', None)))
            if attack_flash_sym:
                attack_flash_ttl -= 1
                if attack_flash_ttl <= 0:
                    attack_flash_on  = not attack_flash_on
                    attack_flash_ttl = _ATTACK_FLASH_TTL
                    needs_render     = True
            if needs_render:
                _render(message)
            continue

        last_activity = time.time()
        player.error = ''   # clear any statusline error on the next keypress
        room._ward_flash = set()   # a shield-flash lives for one action only
        room._atk_arrows = []      # attack-direction arrows live for one action only

        # Content seals re-read the buffer once per KEYPRESS, not per idle poll:
        # these ticks scan every row and column, and idling on a finished ledger
        # used to burn CPU ten times a second. A key arrived, so an action may
        # have changed what the seals read.
        if level == 'spellwrights_forge':
            _forge_check()                       # open the sanctum seal once the rites are true
        elif level == 'culling_ledger':
            _ledger_check()                      # open the seal once the ledger reads true
        elif level == 'shelving_room':
            _shelving_tick()                     # re-submerge, bolts, seal check
        elif level == 'refrain_vault':
            _refrain_tick()                      # re-submerge the chasm, seal check

        # ── The elf's shitty trade (from :s/g/e/) awaits a y/n ────────────────
        # Only y/n resolve it; every other key (x to attack the elf, a step away)
        # falls through and is handled normally, leaving the offer standing.
        if (getattr(room, '_elf_trade', None) and player.mode == Mode.NORMAL
                and not key.is_sequence and str(key).lower() in ('y', 'n')):
            _trade = room._elf_trade
            room._elf_trade = None
            msg_pool.clear()                             # drop the persistent offer
            msg_idx = 0
            msg_ttl = _MSG_ROTATE_TTL
            _elf = next((e for e in room.entities if id(e) == _trade.get('elf_id')), None)
            if str(key).lower() == 'y' and player.gold < _trade['cost']:
                _push(f'"No coin, no deal." The elf sniffs. (you have {player.gold} gold)')
                if _elf is not None:
                    _elf.tag = 'elf'                     # still open to a later offer
            elif str(key).lower() == 'y':
                player.gold -= _trade['cost']            # debited whether or not it's a swindle
                progress['gold'] = player.gold
                _tk = _trade['key']
                if _tk == 'hp':
                    player.take_damage(2)
                elif _tk == 'register':
                    player.registers.pop('"', None)
                elif _tk == 'demon':
                    for _dr, _dc in ((0, 1), (0, -1), (1, 0), (-1, 0)):
                        _nr, _nc = player.row + _dr, player.col + _dc
                        if room.is_passable(_nr, _nc) and room.entity_at(_nr, _nc) is None:
                            room.add_entity(Entity(kind='goblin', row=_nr, col=_nc,
                                                   hp=3, max_hp=3, ai='chase',
                                                   ai_speed=1, tag='demon'))
                            break
                _push(_trade['result'])
                if _elf is not None:                     # dealt — now it wanders off
                    _elf.tag, _elf.ai = 'spent', 'wander'
                room.rebuild_indexes()
                if player.is_dead:
                    message = '** GAME OVER ** Type  :e  to re-load the dungeon.'
            else:
                _push('The elf shrugs and wanders off.')
                if _elf is not None:                     # declined — wanders, no re-offer
                    _elf.tag, _elf.ai = 'spent', 'wander'
            message = message if player.is_dead else _pool_msg()
            _render(message)
            continue

        # ── The Codex pane has focus while open (:help semantics) ────────────
        # Reading is free: no pane key spends budget, and no pane key reaches
        # the dungeon (or the karaoke tracker) until :q closes the window.
        if getattr(player, 'codex_pane', None) is not None:
            _codex_feed(player, key)
            _render(message)
            continue

        # ── Tape recording (the forge's :record) ──────────────────────────────
        # One capture point, ahead of every mode's dispatch, so a tape holds the
        # keys in the order the game read them whatever mode they were read in —
        # a route's `:%s/…<CR>` leg is as much of it as its motions.
        #
        # Replayed macro keys are skipped for the same reason the karaoke tracker
        # skips them: the tape records `@b`, and recording what `@b` expanded to
        # as well would make the tape play the macro's body twice.
        # The take is over the moment the exit is reached: a tape ends at the
        # win, and `replay_tape` supplies the closing `:wq` itself. Recording the
        # author's own way out would put a second one on the tape.
        # A REHEARSAL (`:play`) is a take with the recorder switched off: it
        # wants everything else a take does — the fresh build, the declared
        # command set, the untouched save file — and none of the tape. Nothing
        # is written down, so a key the notation cannot spell is not a problem
        # worth ending the run over.
        if (_record is not None and not _record.get('off') and not from_macro
                and not _record.get('error') and not won):
            _tok = _tape_key(key)
            if _tok is None:
                _record['error'] = (
                    f'{key.name or "that key"} cannot be written on a tape — '
                    f'use its Vim spelling and start the take again.')
            else:
                # Group the tape into commands the way a hand-written karaoke
                # sheet is: a space BETWEEN commands, none WITHIN one. A key read
                # in NORMAL mode with the parse buffer empty is the first key of a
                # new command; a count's tail, an operator's motion, a typed
                # word (INSERT) or a `:`-line (COMMAND) all arrive with a pending
                # buffer or in another mode, so each stays one unbroken run. The
                # spaces are separators (engine.tape.strip_separators strips them
                # on every replay and tokenise), so this changes only how the tape
                # READS — never how it plays, nor the par it earns.
                if (_record['tape'] and not key_buf
                        and player.mode == Mode.NORMAL):
                    _record['tape'].append(' ')
                _record['tape'].append(_tok)

        # ── Admin answer tracking ─────────────────────────────────────────────
        # from_macro keys are skipped: the tape shows '@b', not the replayed
        # keystrokes — matching them against the tape after the '@b' token
        # falsely diverged every tape with a macro leg.
        if (player_name == 'admin' and room.answer and not from_macro
                and not key.is_sequence and str(key) != ':'
                and player.mode in (Mode.NORMAL, Mode.VISUAL,
                                    Mode.VISUAL_LINE, Mode.VISUAL_BLOCK)):
            # '\x16' appears on the tape as `<C-v>`. It is LOAD-BEARING
            # (unlike Esc, a player following the tape cannot infer it), so it
            # must be shown; the tracker consumes the whole token for the one
            # keystroke.
            _tk = _TAPE_CTRL_V if str(key) == '\x16' else str(key)
            if key_buf == '':
                cmd_start_ans = (room.answer_pos, room.answer_diverged)
            if not room.answer_diverged:
                _ans_plain = room.answer.replace(' ', '')
                if room.answer_pos < len(_ans_plain):
                    if _ans_plain.startswith(_tk, room.answer_pos):
                        room.answer_pos += len(_tk)
                    else:
                        room.answer_diverged = True

        # ── Command mode ──────────────────────────────────────────────────────
        if player.mode == Mode.COMMAND:
            if key.name == 'KEY_ESCAPE':
                player.mode = Mode.NORMAL
                player.cmd_line = ''
                player.cmd_cursor = 0
                room._cmd_karaoke = False
            elif key.name == 'KEY_ENTER' or str(key) in ('\n', '\r'):
                if getattr(room, '_cmd_karaoke', False):
                    _advance_answer(_TAPE_ENTER)          # the tape marks Enter <CR>
                    room._cmd_karaoke = False
                cmd = player.cmd_line.strip()
                # `:` from VISUAL prefills the `'<,'>` range vim prefills. Most
                # of the forge's commands are not addressed by a range at all,
                # so rather than teach each one to ignore a prefix, the prefix
                # is stripped ONCE here for the one command that wants it
                # (`:fill`) and CAUGHT at the bottom for the ones that do not —
                # the answer to `:'<,'>entity` is "Esc first", not a guess at
                # what the author meant. Substitute and the ex ranges are left
                # the raw `cmd`: they parse `'<` themselves, properly.
                _vrange = cmd.startswith("'<,'>")
                _rcmd   = cmd[5:].lstrip() if _vrange else cmd
                player.mode    = Mode.NORMAL
                player.cmd_line = ''
                player.cmd_cursor = 0
                msg_pool.clear()
                msg_idx = 0
                if cmd:
                    # The `:` register — vim's record of the last Ex command, and
                    # the reason `@:` repeats it. `.` deliberately does NOT: it
                    # repeats the last CHANGE, and an Ex command is not one, so
                    # an author who has just placed an entity with `:entity` and
                    # wants another reaches for `@:` (then `@@`). Stored as the
                    # bare command text, the way vim stores it, so `":p` pastes
                    # something readable; the leading `:` and the <CR> are put
                    # back at replay time.
                    _reg_record(player, ':', cmd)

                # THE :bar LAW — one line, several statements (`:1j|1y`). The
                # head runs this turn through the ordinary dispatch; every
                # statement after it queues as its own `:` line on the macro
                # queue, so each rides the very same pipeline it would alone —
                # its gates, its ticks, its messages, its undo — instead of the
                # chain being re-implemented here. :g/:v own their bars (pattern
                # and body may contain one), so a global never splits. The LINE
                # pays for itself once, here, whatever the statement count —
                # typed keys are the cost model, and this line typed what it
                # typed — so the two charge sites below stand down this turn.
                _bar_paid = False
                if ('|' in cmd and not edit_mode
                        and not _subst._bar_exempt(cmd, room, player)
                        and (_subst.looks_like_ex_range(cmd, room, player)
                             or _subst.looks_like_sg(cmd, room, player))):
                    # The law chains the EDITOR command family — the same
                    # statements run_ex has always chained. Other dialects
                    # that read a literal `|` (:seal's pin flag, forge args)
                    # pass through untouched.
                    _head, _rest = _subst._split_bar(cmd)
                    if _rest is not None and _head.strip():
                        parts, seg = [], _rest
                        while seg is not None:
                            if _subst._bar_exempt(seg, room, player):
                                parts.append(seg)
                                seg = None
                            else:
                                h2, seg = _subst._split_bar(seg)
                                parts.append(h2)
                        parts = [p for p in parts if p.strip()]
                        if parts:
                            if not edit_mode:
                                budget.spend(len(cmd) + 1)   # the line, once
                            _bar_paid = True
                            for p in parts:                  # FIFO: top to bottom
                                macro_pending.extend(':' + p + '\r')
                            cmd, _rcmd = _head, _head

                if level == 'warden_pathfinder' and cmd == 'e wardenverse':
                    if getattr(room, 'verse_collapsed', False):
                        _push('The wardenverse has collapsed — there is nothing left to enter.')
                    elif (getattr(room, 'warden_fled', False)
                            and dungeon.current_room == 0 and len(dungeon.rooms) > 1):
                        dungeon.current_room = 1             # follow him into the wardenverse
                        room = dungeon.room
                        player.row, player.col = room.spawn_pos
                        player.wrap = False                  # opens nowrap
                        undo_stack.clear()                   # old snapshots belong to the arena room
                        redo_stack.clear()
                        any_water = _room_has_water()
                        _push('You plunge into the wardenverse — it reshapes to your terminal.  '
                              ':set wrap to fold the line, gj/gk to chase him, :set nowrap to still him.')
                    elif dungeon.current_room != 0:
                        _push('You are already in the wardenverse.')
                    else:
                        _push('There is no wardenverse yet — break his shields first.')

                elif (level == 'archivists_library' and cmd in ('e', 'e!')
                        and not player.is_dead):
                    _lib_reload(force=(cmd == 'e!'))

                elif (level == 'archivists_library' and cmd.startswith('w ')
                        and cmd[2:].strip()):
                    _lib_file(cmd[2:].strip())   # :w {any filename} — only the suit names win

                elif cmd == 'w' and _draft is not None:
                    DRAFT.sync(_draft, room)
                    try:
                        _push(f'Draft saved: {DRAFT.save(_draft).name}')
                    except DRAFT.DraftNameCollision as exc:
                        _push(str(exc))

                elif cmd == 'w':
                    if edit_mode and player_name == 'admin':
                        path = SM.save_layout(dungeon.name, _serialize_room(room))
                        _push(f'Layout saved: {path.name}')
                    else:
                        if won:
                            stars = _calc_stars(won, budget, room, player, level)
                            prev  = progress.get(level, {}).get('stars', 0)
                            if prev == 0 and stars >= 1:
                                _first_written_completion = True
                            progress[level] = {'complete': True,
                                               'stars': max(stars, prev)}
                            last_saved_stars = max(stars, last_saved_stars)
                            if player.has_hat:       # the Warden Eternal's gift
                                progress['has_hat'] = True
                        _commit_hearts()
                        _save_progress(progress, player_name)
                        _push('Saved.')

                elif cmd == 'wq':
                    if _draft is not None:
                        DRAFT.sync(_draft, room)
                        try:
                            DRAFT.save(_draft)
                        except DRAFT.DraftNameCollision as exc:
                            _push(str(exc))
                    elif edit_mode and player_name == 'admin':
                        path = SM.save_layout(dungeon.name, _serialize_room(room))
                        _push(f'Layout saved: {path.name}')
                    stars = _calc_stars(won, budget, room, player, level)
                    if won:
                        prev = progress.get(level, {}).get('stars', 0)
                        if prev == 0 and stars >= 1:
                            _first_written_completion = True
                    if player.has_hat:                       # the Warden Eternal's gift
                        progress['has_hat'] = True           # (caller persists progress)
                    _commit_hearts()                         # caller saves on 'wq'
                    return {'won': won, 'stars': stars, 'action': 'wq',
                            'spent': budget.spent, 'par': room.par,
                            'first_written_completion': _first_written_completion}

                elif cmd == 'q':
                    stars = _calc_stars(won, budget, room, player, level)
                    if (player_name != 'admin'
                            and ((won and stars > last_saved_stars) or pending_hearts)):
                        player.error = 'E37: No write since last change (add ! to override)'
                    else:
                        return {'won': won, 'stars': stars, 'action': 'quit',
                                'spent': budget.spent, 'par': room.par,
                                'first_written_completion': _first_written_completion}

                elif cmd == 'q!':
                    return {'won': False, 'stars': 0, 'action': 'quit',
                            'spent': budget.spent, 'par': room.par,
                            'first_written_completion': False}

                elif _draft is not None and cmd in ('e', 'e!'):
                    # `:e` on a draft re-reads the FILE, like `:e` everywhere
                    # else. It cannot mean the admin `:e` below — that rebuilds
                    # the level named by the slug, and a draft's slug is the
                    # placeholder 'community', so the admin branch would land the
                    # author in The First Cave with their draft unopened.
                    DRAFT.sync(_draft, room)
                    _disk  = (_draft.path.read_text(encoding='utf-8')
                              if _draft.path.exists() else '')
                    _dirty = LF.dumps(_draft.level) != _disk
                    if _dirty and cmd == 'e':
                        player.error = 'E37: No write since last change (add ! to override)'
                    else:
                        _fresh = DRAFT.load(_draft.path)
                        if not _fresh.ok:
                            _push(f'Cannot re-read the draft: {_fresh.error}')
                        else:
                            _draft.level = _fresh.level
                            # Reseeded, because a shipped level is: every player
                            # who opens it grows their own words. `:e` is the one
                            # place an author can see that happen, and a fill that
                            # only ever reads back the arrangement it was born
                            # with is a fill the author cannot judge.
                            _err = _forge_rebuild(reseed=True)
                            _push(_err or (f'"{_draft.level.name}" re-read from disk'
                                           + (' — fills regrown.' if _draft.level.fills
                                              else '.')))

                elif cmd == 'e' and (player_name == 'admin' or player.is_dead
                                     or _record is not None):
                    seed    = random.randint(0, 2**31)
                    if _record is not None and _record.get('rebuild') is not None:
                        # A TAKE reloads THE LEVEL BEING PLAYED. `level` here is
                        # whatever slug the overworld happened to open the forge
                        # from, and rebuilding that would answer `:e` — restart
                        # this — by putting the author in a different dungeon
                        # altogether, with their draft nowhere on screen.
                        # A new seed is still a new seed: the fills re-roll, so
                        # `:e` is also how an author asks what somebody else's
                        # copy of the room looks like.
                        dungeon = _record['rebuild'](seed)
                        room    = dungeon.room
                        # Whatever was on the tape was played in a room that no
                        # longer exists. Keeping it would splice two routes
                        # through two different roomsful of words into one take.
                        _record['tape'] = []
                    else:
                        dungeon = _build_dungeon(level, seed,
                                                 admin=(player_name == 'admin'))
                        room    = dungeon.room
                        if player_name != 'admin':
                            room.answer = ''
                    _sp2    = room.spawn_pos
                    player  = Player(row=_sp2[0], col=_sp2[1])
                    player.max_hp = progress.get('max_hp', 6)   # keep heart-container upgrades
                    player.hp     = player.max_hp
                    # A level that declared its own command set is reloaded under
                    # it — the curriculum has no answer for a slug it never had.
                    player.known_commands = (list(_known) if _known is not None
                                             else _known_commands(level))
                    if player_name == 'admin' and _record is None:
                        player.known_commands = player.known_commands + ['admin', 'register']
                    dungeon.level_slug = level
                    budget        = Budget(room.budget or 20)
                    cmd_start_ans = (0, False)
                    undo_stack.clear()
                    redo_stack.clear()
                    edit_mode = False
                    player.edit_clip.clear()
                    ed_undo.clear()
                    ed_redo.clear()
                    key_buf         = ''
                    won             = False
                    spotted_goblins      = set()
                    spotted_wardens      = set()
                    engaged_entities     = set()
                    door_hint_shown      = set()
                    door_open_hint_shown = set()
                    msg_pool             = []
                    msg_idx              = 0
                    any_water            = _room_has_water()
                    _push('Your level, from the top.' if _record is not None else
                          'Dungeon restarted. Good luck.' if player_name != 'admin'
                          else 'New dungeon loaded.')

                elif cmd == 'edit' and player_name == 'admin':
                    edit_mode = not edit_mode
                    room.passable_walls = edit_mode
                    if edit_mode:
                        if 'editor' not in player.known_commands:
                            player.known_commands = player.known_commands + ['editor']
                        _push('EDIT mode ON — x:cut  :paint  dd/yy  d/y{m}  p/P  :save <name>')
                    else:
                        player.known_commands = [c for c in player.known_commands if c != 'editor']
                        _push('EDIT mode OFF.')

                elif cmd.startswith('save ') and player_name == 'admin':
                    name = cmd[5:].strip()
                    if name:
                        path = SM.save_layout(name, _serialize_room(room))
                        _push(f'Layout saved: {path.name}')
                    else:
                        _push('Usage:  :save <name>')

                elif (cmd == 'rune' or cmd.startswith('rune ')) \
                        and edit_mode and player_name == 'admin':
                    kind = cmd[4:].strip().lower()
                    _via = ''
                    if not kind:
                        # Bare `:rune` asks which runes exist, and the list is
                        # the answer — same as a bare `:paint` or `:entity`.
                        kind = _pick_one(term, _iw(term), term.height - 8,
                                         'place a rune', _RUNE_NOTES)
                        _via = f'   (:rune {kind})' if kind else ''
                    if not kind:
                        _push('')                     # backed out of the picker
                    elif kind not in _RUNE_CHAR:
                        _push(f'Unknown rune kind: {kind}  ({"|".join(_RUNE_CHAR)})')
                    elif _in_fill(room, player.row, player.col):
                        _push('A fill grows that text — :fill! to make it yours.')
                    else:
                        r, c = player.row, player.col
                        ed_undo.append(_ed_snapshot(room, player))
                        ed_redo.clear()
                        existing = room.char_run_at(r, c)
                        if existing:
                            room.remove_char_run(existing)
                        room.add_char_run(CharRun(row=r, col=c,
                                                  symbols=(_RUNE_CHAR[kind],), kind=kind))
                        _merge_adjacent_char_runs(room, r)
                        _push(f'Placed {kind} rune.' + _via)

                elif (_rcmd.rstrip('?') == 'paint' or _rcmd.startswith('paint ')) \
                        and edit_mode and player_name == 'admin':
                    # `:paint <kind>` lays terrain down by NAME, where `s` used to
                    # walk a fixed ring. A ring can only reach what someone
                    # remembered to thread onto it — sunken water was in the
                    # engine, drawn by the renderer, reachable by no key — and it
                    # cannot answer "what else is there?". A name can, and takes
                    # the `'<,'>` range the way `:fill` does, so a river is one
                    # command and not a lap of the cycle per cell.
                    _kind = _rcmd[6:].strip().lower()
                    _cells = (_range_cells(room, player) if _vrange
                              else [(player.row, player.col)])
                    if _rcmd.endswith('?'):
                        _tally = {}
                        for _pr, _pc in _cells:
                            _tally[_paint_name(room, _pr, _pc)] = \
                                _tally.get(_paint_name(room, _pr, _pc), 0) + 1
                        _push(', '.join(f'{_n} × {_k}' if _n > 1 else _k
                                        for _k, _n in sorted(_tally.items()))
                              or 'Nothing there.')
                    elif not _kind:
                        # A bare `:paint` is the question "what can I lay down?",
                        # and the palette answers it by composing the command.
                        _kind = _pick_one(
                            term, _iw(term), term.height - 8, 'paint a cell',
                            [(_k, _v[2]) for _k, _v in PAINT_KINDS.items()])
                        if not _kind:
                            _push('')                    # backed out of the picker
                        else:
                            ed_undo.append(_ed_snapshot(room, player))
                            ed_redo.clear()
                            # Name the line that would have done the same thing —
                            # the one thing the screen cannot show.
                            _push(_paint_cells(room, _cells, _kind)
                                  + f'   (:paint {_kind})')
                    elif _kind not in PAINT_KINDS:
                        _push(_paint_complaint(_kind))
                    else:
                        ed_undo.append(_ed_snapshot(room, player))
                        ed_redo.clear()
                        _push(_paint_cells(room, _cells, _kind))

                elif (_rcmd.rstrip('?!') == 'entity' or _rcmd.startswith('entity ')) \
                        and edit_mode and player_name == 'admin':
                    # `:entity` is `:set`, applied to the cell under the cursor:
                    #
                    #   :entity goblin tag=echo hp=3   place, configured
                    #   :entity tag=gold               retune what is already here
                    #   :entity?                       what is here, non-defaults only
                    #   :entity!                       remove it
                    #   :entity                        the palette, as a picker
                    #
                    # Same read/write/clear split the forge's metadata commands
                    # already use, and the same one the game teaches at the
                    # Archivist's Library — so the authoring bench is not a
                    # second language bolted onto a Vim game.
                    _r, _c = player.row, player.col
                    _here  = room.entity_at(_r, _c)
                    _bare  = _rcmd.rstrip('?!') == 'entity'
                    _toks  = _rcmd[7:].split()
                    # `?` and `!` take the range too. A question asked of a
                    # selection is answered about the selection (a tally, not the
                    # one cell the cursor happens to be on), and `:'<,'>entity!`
                    # is the eraser the ranged placement needs — put a rank down,
                    # look at it, sweep it away.
                    _sel = _entity_cells(room, player) if _vrange else []
                    if _bare and _rcmd.endswith('?'):
                        if _vrange:
                            _tally = {}
                            for _sr, _sc in _sel:
                                _e = room.entity_at(_sr, _sc)
                                if _e is not None:
                                    _tally[_e.kind] = _tally.get(_e.kind, 0) + 1
                            _push(f'Nothing in those {len(_sel)} cells.'
                                  if not _tally else
                                  ', '.join(f'{_n} × {_k}' for _k, _n
                                            in sorted(_tally.items()))
                                  + f'  ({len(_sel)} cells)')
                        else:
                            _push(_describe_entity(_here) if _here
                                  else 'Nothing here.')
                    elif _bare and _rcmd.endswith('!'):
                        _gone = ([e for e in room.entities
                                  if (e.row, e.col) in set(_sel)] if _vrange
                                 else ([_here] if _here is not None else []))
                        if not _gone:
                            _push('Nothing here to remove.')
                        else:
                            ed_undo.append(_ed_snapshot(room, player))
                            ed_redo.clear()
                            for _e in _gone:
                                room.entities.remove(_e)
                            room.rebuild_indexes()
                            _push(f'Removed {_gone[0].kind}.' if len(_gone) == 1
                                  else f'Removed {len(_gone)} entities.')
                    else:
                        # A bare `:entity` opens the palette. It is a question
                        # ("what can I place?"), and a list is the answer — but
                        # the answer is delivered by running the command, so
                        # nothing here is reachable only through the menu.
                        _kind = ''
                        _via  = ''            # the line the picker composed
                        if _bare:
                            _via  = _pick_entity(
                                term, _iw(term), term.height - 8,
                                custom=(_draft.level.vocabulary
                                        if _draft is not None else ()))
                            _toks = _via.split()
                            if _toks:
                                _kind, _toks = _toks[0], _toks[1:]
                            else:
                                _push('')
                        elif '=' not in _toks[0]:
                            # …through the rename map, so `:entity chest` still
                            # means what it meant when the docs said it did.
                            _kind = canonical_kind(_toks[0].lower())
                            _toks = _toks[1:]
                        if _bare and not _kind:
                            pass                      # cancelled out of the picker
                        elif _kind and _kind not in _ENTITY_PALETTE:
                            _push(f'Unknown entity kind: {_kind}  '
                                  f'({"|".join(_ENTITY_PALETTE)})')
                        elif not _kind and _here is None:
                            _push('Nothing here to change — name a kind '
                                  'to place one (:entity for the list).')
                        elif _vrange and not _entity_cells(room, player):
                            _push('Nothing standable in that selection.')
                        else:
                            # WITH a range, the command addresses every standable
                            # cell of the selection instead of the one under the
                            # cursor — a rank of goblins, a row of chests, a wall
                            # of coins, in one command. It is the same region
                            # `:fill` takes, and it means the same thing: the
                            # shape you drew. Without one, the cursor cell, as
                            # before. Walls and water are skipped rather than
                            # refused, so a selection swept across a room places
                            # into the room and not into its masonry.
                            ed_undo.append(_ed_snapshot(room, player))
                            ed_redo.clear()
                            _targets = (_entity_cells(room, player) if _vrange
                                        else [(_r, _c)])
                            _bad, _made = [], []
                            for _r, _c in _targets:
                                _here = room.entity_at(_r, _c)
                                if _kind:
                                    if _here is not None:
                                        room.entities.remove(_here)
                                        room.rebuild_indexes()
                                    _here = Entity(kind=_kind, row=_r, col=_c,
                                                   **_ENTITY_PALETTE[_kind][0])
                                    room.add_entity(_here)
                                elif _here is None:
                                    continue      # retune skips an empty cell
                                _made.append(_here)
                                for _t in _toks:
                                    _f, _eq, _v = _t.partition('=')
                                    if not _eq or _f not in _ENTITY_SETTABLE:
                                        _bad.append(f'{_t} (try '
                                                    f'{"/".join(_ENTITY_SETTABLE)})')
                                        continue
                                    _why = _entity_field(_here, _f, _v)
                                    if _why:
                                        _bad.append(_why)
                                if _bad:
                                    break         # one bad field is bad for all
                            _bad = list(dict.fromkeys(_bad))
                            _here = _made[-1] if _made else _here
                            # After a MENU placement, name the command that would
                            # have done the same thing. It is the one piece of
                            # information the screen cannot show, and it is how
                            # the picker teaches its own way out of being needed.
                            # Over a RANGE, the count is that piece instead: a `V`
                            # across a wide room holds more cells than it looks
                            # like it does, and `u` is the answer if it is wrong.
                            if _bad:
                                _push('; '.join(_bad))
                            elif len(_made) > 1:
                                _push(f'{len(_made)} × {_here.kind} '
                                      f'{"placed" if _kind else "set"} '
                                      f'over {len(_targets)} cells.')
                            elif not _made:
                                _push('Nothing in that selection to change.')
                            else:
                                _push(f'Placed by  :entity {_via}' if _via
                                      else f'{"Placed" if _kind else "Set"}: '
                                           f'{_describe_entity(_here)}')

                # ── The forge: authoring a shareable level ────────────────────
                # These only exist when a DRAFT is open. Everything they touch is
                # the thing a Room cannot hold — the declarative half of a level
                # (fills, vocabulary, who it is for, what it teaches) — plus the
                # two positions the editor could never set at all.
                elif _draft is not None and cmd in ('spawn', 'exit') and edit_mode:
                    ed_undo.append(_ed_snapshot(room, player))
                    ed_redo.clear()
                    if cmd == 'spawn':
                        room.spawn_pos = (player.row, player.col)
                    else:
                        for _e in [e for e in room.entities if e.kind == 'exit']:
                            room.remove_entity(_e)
                        room.exit_pos = (player.row, player.col)
                        room.add_entity(Entity(kind='exit', row=player.row,
                                               col=player.col, hp=1, alive=True))
                        room.rebuild_indexes()
                    _push(f'{cmd.capitalize()} moved here.')

                elif _draft is not None and _rcmd == 'fill?' and edit_mode:
                    # What grows here — the directive, not the words. The words
                    # are re-rolled on every build; the directive is the thing
                    # the author wrote and the only thing they can change.
                    _f = _in_fill(room, player.row, player.col)
                    if _f is None:
                        _push('No fill here. '
                              + (f'{len(_draft.level.fills)} in this level.'
                                 if _draft.level.fills else 'None in this level.'))
                    else:
                        _r1, _c1, _r2, _c2 = _f.region
                        _push(f':fill {_f.pool}'
                              + ('' if _f.pool in _VOCAB_LINE_POOLS
                                 else f' {_f.length[0]}-{_f.length[1]}')
                              + (f' {_f.spacing}' if _f.spacing != 1 else '')
                              + f'   rows {_r1}-{_r2}, cols {_c1}-{_c2}'
                              + f'  ({(_r2 - _r1 + 1) * (_c2 - _c1 + 1)} cells)')
                        # And, standing on a word: the reference a tape would
                        # use for it. Nobody can count to slot 23 by eye, and a
                        # tape that names the wrong word fails at :check with a
                        # message about par rather than about miscounting.
                        _n, _k, _w = _slot_at(room, player.row, player.col)
                        if _k is None:
                            _push('Stand on a word to be told its slot.')
                        elif _f.length[0] != _f.length[1]:
                            _push(f'This is {_w!r} — but a tape cannot name it '
                                  f'while this fill grows {_f.length[0]}-'
                                  f'{_f.length[1]} letter words: par would be a '
                                  f'different number for every player. '
                                  f':fill length={len(_w)} to settle it.')
                        else:
                            _push(f'{_w!r} is <fill{_n}.{_k}> — write that in the '
                                  f'solution and every player types their own.')

                elif (_draft is not None and edit_mode
                      and _rcmd.split()[0:1] == ['fill']
                      and _rcmd.split()[1:]
                      and all('=' in _a3 for _a3 in _rcmd.split()[1:])):
                    # `:fill length=4` — retune the fill under the cursor IN
                    # PLACE, the way `:entity field=value` retunes an entity.
                    # Without this the only way to change a directive was to
                    # re-select the region and `:fill` again, which APPENDS: two
                    # overlapping directives growing words over each other. The
                    # fill keeps its index in the list, because that index is
                    # what a `<fill0.3>` in the solution is pointing at.
                    _f = _in_fill(room, player.row, player.col)
                    if _f is None:
                        _push('No fill under the cursor. Stand in one to retune '
                              'it, or select a region and :fill <pool> to make '
                              'a new one.')
                    else:
                        _i    = _draft.level.fills.index(_f)
                        _kw   = dict(pool=_f.pool, length=_f.length,
                                     spacing=_f.spacing, kind=_f.kind)
                        _bad  = ''
                        for _a3 in _rcmd.split()[1:]:
                            _k3, _, _v3 = _a3.partition('=')
                            if _k3 == 'pool':
                                if _v3 not in _VOCAB_POOLS:
                                    _bad = (f'Unknown pool: {_v3}  '
                                            f'({"|".join(_VOCAB_POOLS)})')
                                _kw['pool'] = _v3
                            elif _k3 == 'length':
                                _p3 = _v3.split('-')
                                if not all(_x.isdigit() for _x in _p3) or len(_p3) > 2:
                                    _bad = (f'length={_v3}: write one number for '
                                            f'words all the same length, or lo-hi '
                                            f'for a range.')
                                else:
                                    _kw['length'] = (int(_p3[0]), int(_p3[-1]))
                            elif _k3 == 'spacing' and _v3.isdigit():
                                _kw['spacing'] = int(_v3)
                            else:
                                _bad = (f'{_a3}: a fill has pool, length and '
                                        f'spacing.')
                        if _bad:
                            _push(_bad)
                        else:
                            _new = LF.Fill(region=_f.region, **_kw)
                            DRAFT.sync(_draft, room)       # keep what was painted
                            _draft.level.fills[_i] = _new
                            _err = _forge_rebuild()
                            if _err:
                                _draft.level.fills[_i] = _f
                                _forge_rebuild()
                                _push(f'Fill refused — {_err}')
                            else:
                                _lo3, _hi3 = _new.length
                                _push(f'fill[{_i}]: {_new.pool} '
                                      + (f'{_lo3}' if _lo3 == _hi3
                                         else f'{_lo3}-{_hi3}')
                                      + f' letters, spacing {_new.spacing} — '
                                      + ('a tape may name these words now.'
                                         if _lo3 == _hi3 else
                                         'a tape cannot name words of a rolled '
                                         'length.'))

                elif _draft is not None and _rcmd.split()[0:1] == ['fill'] and edit_mode:
                    # `:fill <pool> [lo-hi] [spacing]` over the last VISUAL
                    # selection — the same region `gv` would bring back, which is
                    # what `'<,'>` means everywhere else in Vim. Written with or
                    # without that range: `:'<,'>fill plain` is what typing `:`
                    # straight from the selection gives you, and it says out loud
                    # the thing the bare form only implies.
                    _args = _rcmd.split()[1:]
                    _a, _b = player.last_visual_anchor, player.last_visual_cursor
                    if _a is None or _b is None:
                        _push('Select the region in VISUAL first, then :fill <pool>.')
                    else:
                        # A bare `:fill` used to mean `:fill plain` silently.
                        # It is a question — which pools are there? — and the
                        # picker answers it, then names the line it stood for.
                        _via, _picked_len = '', ''
                        if _args:
                            _pool = _args[0]
                        else:
                            _pool = _pick_one(
                                term, _iw(term), term.height - 8,
                                'fill the selection from',
                                [(_p, _POOL_NOTES.get(_p, '')) for _p in _VOCAB_POOLS])
                            _via = f'   (:fill {_pool})' if _pool else ''
                            # Second step: how long the words are. It belongs in
                            # the menu because it is not a detail — a single
                            # length is what lets a solution NAME one of these
                            # words (`<fill0.3>`), and an author who never learns
                            # that meets it as a refusal at :check instead. A
                            # saying pool has no say in its own lengths, and a
                            # custom pool takes them from the author's own words,
                            # so neither is asked.
                            if (_pool and _pool not in _VOCAB_LINE_POOLS
                                    and not (_pool == 'custom'
                                             and _draft.level.vocabulary)):
                                _picked_len = _pick_one(
                                    term, _iw(term), term.height - 8,
                                    'how long are the words',
                                    [('3-6', 'mixed — no tape can name these '
                                             'words')]
                                    + [(f'{_n3}-{_n3}',
                                        f'all {_n3} letters — a tape can name '
                                        f'them')
                                       for _n3 in (3, 4, 5, 6)])
                                if not _picked_len:
                                    _pool = ''          # backed out of the step
                                else:
                                    _via = f'   (:fill {_pool} {_picked_len})'
                        if not _pool:
                            _push('')                 # backed out of the picker
                        elif _pool not in _VOCAB_POOLS:
                            _push(f'Unknown pool: {_pool}  ({"|".join(_VOCAB_POOLS)})')
                        else:
                            # A custom pool defaults to the lengths the author's
                            # own words HAVE. The stock 3-6 is right for the
                            # shipped pools and wrong for a hand-written list:
                            # `:vocab chat chien oiseau` has nothing 3 long, and
                            # a fill asking for one would quietly get the
                            # nearest-length fallback instead of the words the
                            # author just typed.
                            if _pool == 'custom' and _draft.level.vocabulary:
                                _lens = [len(w) for w in _draft.level.vocabulary]
                                _lo, _hi, _sp = min(_lens), max(_lens), 1
                            else:
                                _lo, _hi, _sp = 3, 6, 1
                            for _a2 in ([_picked_len] if _picked_len else _args[1:]):
                                if '-' in _a2:
                                    _p = _a2.split('-')
                                    _lo, _hi = int(_p[0]), int(_p[1])
                                elif _a2.isdigit():
                                    _sp = int(_a2)
                            # A LINEWISE selection means the whole line, so its
                            # columns are the row's full width — not the two
                            # cells the cursor happened to sit between, which is
                            # all `'<,'>` records for it. Reading them literally
                            # is how `V` came out as "cols 1-1".
                            if player.last_visual_mode == Mode.VISUAL_LINE:
                                _c1, _c2 = 0, room.cols - 1
                            else:
                                _c1, _c2 = min(_a[1], _b[1]), max(_a[1], _b[1])
                            _reg = (min(_a[0], _b[0]), _c1,
                                    max(_a[0], _b[0]), _c2)
                            _f = LF.Fill(region=_reg, pool=_pool,
                                         length=(_lo, _hi), spacing=_sp)
                            _need = (_min_saying_width(_pool)
                                     if _pool in _VOCAB_LINE_POOLS else 0)
                            if _need and _c2 - _c1 + 1 < _need:
                                # A line pool lays whole sayings. Too narrow and
                                # nothing at all would grow — which reads, on
                                # screen, exactly like a fill that did not take.
                                _push(f'{_pool} lays whole sayings — the shortest '
                                      f'needs {_need} columns and this selection '
                                      f'is {_c2 - _c1 + 1} wide.')
                                _render(message)
                                continue
                            DRAFT.sync(_draft, room)     # keep what was painted
                            _draft.level.fills.append(_f)
                            _err = _forge_rebuild()
                            if _err:
                                _draft.level.fills.remove(_f)
                                _push(f'Fill refused — {_err}')
                            else:
                                _push(f'Fill: {_pool} {_lo}-{_hi} over '
                                      f'rows {_reg[0]}-{_reg[2]}, '
                                      f'cols {_c1}-{_c2}.' + _via)

                elif _draft is not None and cmd == 'fill!' and edit_mode:
                    # Bake the fill under the cursor: its words stop being grown
                    # from the seed and become text the author owns and can edit.
                    _f = LF.in_fill(room, player.row, player.col)
                    if _f is None:
                        _push('No fill under the cursor.')
                    else:
                        _kept = [{'row': ru.row, 'col': ru.col,
                                  'symbols': list(ru.symbols), 'kind': ru.kind}
                                 for ru in room.char_runs if _f.covers(ru.row, ru.col)]
                        DRAFT.sync(_draft, room)         # keep what was painted
                        _draft.level.fills.remove(_f)
                        _draft.level.char_runs = list(_draft.level.char_runs) + _kept
                        _forge_rebuild()
                        _push(f'Fill dropped — its {len(_kept)} word(s) are yours to edit now.')

                elif _draft is not None and edit_mode and (
                        _rcmd.rstrip('?!') == 'seal' or _rcmd.startswith('seal ')):
                    # `:seal <text>` over the last VISUAL selection arms a
                    # text-match door: while that region reads <text>, the cells
                    # you then `:bolt` stand open. Two commands, because the
                    # condition and the door are in two different places and no
                    # single gesture can point at both — the selection says where
                    # to read, the cursor says what to open.
                    #
                    # A leading `*` means "somewhere in the region" rather than
                    # "the region reads exactly this" — the glob sense it has
                    # everywhere else. Write a literal one as `\*`.
                    _a, _b = player.last_visual_anchor, player.last_visual_cursor
                    _txt = _rcmd[5:].strip()
                    if _rcmd.rstrip('?!') == 'seal' and _rcmd.endswith('?'):
                        _ss = list(getattr(room, 'seals', ()))
                        _suffix = {'exact': '', 'contains': ' (contains)',
                                   'braziers': ' (braziers)', 'gone': ' (gone)'}
                        _push('; '.join(
                            f'{s.match!r} @ ' + ' '.join(f'{r},{c}' for r, c in s.opens)
                            + _suffix.get(s.mode, f' ({s.mode})')
                            + (f', col{s.head}' if s.head >= 0 else '')
                            + (f', pin{s.at}' if s.at >= 0 else '')
                            + (f' ← after {len(s.requires)}' if s.requires else '')
                            for s in _ss) or 'No seals in this level.')
                    elif _rcmd.rstrip('?!') == 'seal' and _rcmd.endswith('!'):
                        _ss = [s for s in getattr(room, 'seals', ())
                               if (player.row, player.col) in s.opens]
                        if not _ss:
                            _push('No seal bolts this cell.')
                        else:
                            DRAFT.sync(_draft, room)
                            for _s in _ss:
                                _draft.level.seals.remove(_s)
                            _forge_rebuild()
                            _push(f'Seal removed — {len(_ss)} condition(s) gone.')
                    elif not _txt:
                        _push('Usage: :seal [xN] [@col] [|col] [*]<text> — over '
                              'a VISUAL selection it reads that region; with no '
                              'selection, ANY floor row.')
                    else:
                        # Grammar, in the order the usage line prints:
                        # [xN] [@col] [|col] [*]<text>. Flags first, then the
                        # glob star, then the words. A leading `\` quotes the
                        # rest, so a password may begin flag-shaped ('\\x2 mark
                        # it' reads the words, not a count).
                        _mode = 'exact'
                        _times, _head, _pin = 1, -1, -1
                        if _txt.startswith('\\'):
                            _txt = _txt[1:]
                        else:
                            #   xN — N DISTINCT floor rows must read true (the
                            #        Y p door: the source verse is not a proof)
                            #   @C — a reading row's first glyph sits at column
                            #        C (the << door: the margin IS the test)
                            #   |C  — the target stands with its first glyph AT
                            #        column C, west of it invisible (the plumb-
                            #        line doors: i+junk shoving the word onto
                            #        the line is a legal route)
                            while True:
                                _m = re.match(r'x(\d+)(?=\s|$)', _txt)
                                if _m:
                                    _times = max(1, int(_m.group(1)))
                                    _txt = _txt[_m.end():].lstrip()
                                    continue
                                _m = re.match(r'@(\d+)(?=\s|$)', _txt)
                                if _m:
                                    _head = int(_m.group(1))
                                    _txt = _txt[_m.end():].lstrip()
                                    continue
                                _m = re.match(r'\|(\d+)(?=\s|$)', _txt)
                                if _m:
                                    _pin = int(_m.group(1))
                                    _txt = _txt[_m.end():].lstrip()
                                    continue
                                break
                            if _txt.startswith('*'):
                                _mode, _txt = 'contains', _txt[1:].strip()
                        _txt = _txt.strip()
                        if not _txt:
                            _push('Armed nothing — after any x/@/| flags, :seal '
                                  'still needs the text itself.')
                        elif _head >= 0 and _pin >= 0:
                            _push('A seal may name a margin (@) or a pin (|), '
                                  'not both — one wants the row to START there, '
                                  'the other only the target.')
                        elif _a is None or _b is None:
                            # No selection: the whole floor is the page. This
                            # is how every exact-chassis door reads — floor
                            # rows only, never plaques, and row-agnostic
                            # because dd, J, o and p all shift rows.
                            _draft._pending_seal = ((), (_txt,) * _times,
                                                    _mode, _head, _pin)
                            _push('Seal armed on ANY floor row'
                                  + ('' if _times == 1
                                     else f' — on {_times} of them at once')
                                  + ('' if _head < 0
                                     else f', first glyph at column {_head}')
                                  + ('' if _pin < 0
                                     else f', pinned to column {_pin}')
                                  + ' — stand on the door and :bolt.')
                        elif _head >= 0 or _pin >= 0 or _times > 1:
                            # A region seal reads its rectangle as ONE
                            # collapsed page: no margin to name, no column to
                            # pin, and one page standing twice is still one
                            # page. Refused where the meaning dies — never a
                            # silent no-op.
                            _push('@col, |col and xN need the whole-floor form '
                                  '— a region seal reads its rectangle as one '
                                  'collapsed page.')
                        else:
                            if player.last_visual_mode == Mode.VISUAL_LINE:
                                _c1, _c2 = 0, room.cols - 1   # V means the whole row
                            else:
                                _c1, _c2 = min(_a[1], _b[1]), max(_a[1], _b[1])
                            _draft._pending_seal = (
                                (min(_a[0], _b[0]), _c1, max(_a[0], _b[0]), _c2),
                                (_txt,) * _times, _mode, _head, _pin)
                            _push(f'Seal armed on rows {min(_a[0], _b[0])}-'
                                  f'{max(_a[0], _b[0])}, cols {_c1}-{_c2} — '
                                  f'stand on the door and :bolt.')

                elif _draft is not None and edit_mode and (
                        _rcmd.rstrip('?!') == 'gone'
                        or _rcmd.startswith('gone ')):
                    # `:gone <kind|group> [more...]` arms the LEGION condition:
                    # the bolt stands open while NO live entity of a named kind
                    # stands anywhere in the room. No selection is read — this
                    # condition has no region; extinction is a whole-room fact,
                    # which is what makes `u`-restoring a slain goblin re-bar
                    # the door. A name may also be a GROUP (`:entity goblin
                    # group=patrol`): a patrol dies as one, so naming it arms
                    # one condition over every kind marching in it — mixed
                    # kinds, one named banner.
                    _names = [w for w in _rcmd[5:].split() if w != '?']
                    _kinds = sorted({e.kind for e in room.entities})
                    _groups = sorted({e.group for e in room.entities if e.group})
                    if _rcmd.endswith('?') or not _names:
                        _push(':gone <kind|group> [more...] arms "none of these '
                              'still stands"; :bolt then arms the door itself. '
                              'Here now — kinds: ' + (', '.join(_kinds) or '(none)')
                              + '; groups: ' + (', '.join(_groups) or '(none)') + '.')
                    else:
                        _want, _bad = [], []
                        for _n in _names:
                            if _n in _kinds:
                                if _n not in _want:
                                    _want.append(_n)
                            elif _n in _groups:
                                for _e in room.entities:
                                    if _e.group == _n and _e.kind not in _want:
                                        _want.append(_e.kind)
                            else:
                                _bad.append(_n)
                        if _bad:
                            _push('Nothing here is called ' + ', '.join(_bad)
                                  + ' — a bolt naming it would stand open at '
                                  'once. Kinds: ' + (', '.join(_kinds) or '(none)')
                                  + '; groups: ' + (', '.join(_groups) or '(none)') + '.')
                        elif not _want:
                            _push('No entities are placed yet — :entity puts '
                                  'something on the floor for :gone to name.')
                        else:
                            _draft._pending_seal = ((), tuple(_want), 'gone',
                                                    -1, -1)
                            _push('Legion armed — no '
                                  + ' nor '.join(_want)
                                  + ' may stand. Stand on the door and :bolt.')

                elif _draft is not None and edit_mode and _rcmd.rstrip('?!') == 'final':
                    # THE FINAL SEAL — the Gauntlet's last door, made into a
                    # gesture. Individual bolts open one proof at a time; the
                    # way out wants ALL of them. Stand on the final door and
                    # `:final`: it bolts this cell behind every seal already in
                    # the level, in file order. (:seal! on this cell removes it
                    # again, like any other bolt.)
                    #
                    # The cell-sharing refusal is the same rule :bolt enforces
                    # against a seal's own region, said from the other side:
                    # two doors cannot share one stone.
                    _cell = (player.row, player.col)
                    _n = len(_draft.level.seals)
                    if not _n:
                        _push('Nothing to require yet — arm the bolts first '
                              '(:seal/:gone, then :bolt).')
                    elif any(_cell in s.opens for s in _draft.level.seals):
                        _push('A seal already bolts this cell — two doors '
                              'cannot share one stone.')
                    else:
                        DRAFT.sync(_draft, room)
                        _new = Seal(requires=tuple(range(_n)), opens=(_cell,))
                        _draft.level.seals.append(_new)
                        _err = _forge_rebuild()
                        if _err:
                            _draft.level.seals.remove(_new)
                            _push(f'Final refused — {_err}')
                        else:
                            _push(f'The final seal stands: this door wants '
                                  f'all {_n} bolt(s) open first.')

                elif _draft is not None and edit_mode and _rcmd == 'bolt':
                    # Attach cells to the armed seal. The cursor cell on its own,
                    # or — with the `'<,'>` range — every cell of the selection,
                    # which is how a whole WALL is wired to one trigger instead
                    # of being bolted a cell at a time. Repeatable either way: a
                    # second `:bolt` widens the same seal rather than making a
                    # second one.
                    _pend = getattr(_draft, '_pending_seal', None)
                    _want = (_bolt_cells(room, player) if _vrange
                             else [(player.row, player.col)])
                    if _pend is None:
                        _push('Nothing armed — :seal <text> over a selection, '
                              'or :gone <kind>, first.')
                    elif not _want:
                        _push('Nothing in that selection to bolt.')
                    else:
                        _reg, _txt, _mode, _head, _pin = _pend
                        # A text seal's pending carries the target tuple (one
                        # entry per required reading); a gone seal's carries
                        # the kind tuple as-is.
                        _mtch = _txt if isinstance(_txt, tuple) else (_txt,)
                        # An empty region means a WHOLE-FLOOR door — the
                        # anyrow scope, which reads floor rows wherever they
                        # now stand instead of pinning a rectangle of stone.
                        _scope = ('gone' if _mode == 'gone'
                                  else 'anyrow' if not _reg else 'region')
                        _inside = []
                        if _reg:
                            _r1, _c1, _r2, _c2 = _reg
                            _inside = [(r, c) for r, c in _want
                                       if _r1 <= r <= _r2 and _c1 <= c <= _c2]
                        if _inside:
                            # See the validator: a door inside its own condition
                            # opens, becomes walkable, gets written on, and then
                            # re-shuts on whatever was written. Catch it here so
                            # the author hears it while they can see both. The
                            # overlap is REFUSED rather than quietly dropped —
                            # the selection is the author saying which cells they
                            # mean, and silently meaning fewer is how a wall ends
                            # up with a hole in it nobody put there.
                            _push(f'{len(_inside)} of those cells lie inside the '
                                  "seal's own region — a door cannot be part of "
                                  'the text that opens it.')
                        else:
                            DRAFT.sync(_draft, room)
                            _old = [s for s in _draft.level.seals
                                    if (s.region, s.match, s.mode, s.scope,
                                        s.head, s.at)
                                    == (_reg, _mtch, _mode, _scope, _head, _pin)]
                            _cells = tuple(_old[0].opens) if _old else ()
                            if _old:
                                _draft.level.seals.remove(_old[0])
                            _add = tuple(c for c in _want if c not in _cells)
                            _new = Seal(region=_reg, match=_mtch, mode=_mode,
                                        scope=_scope, opens=_cells + _add,
                                        head=_head, at=_pin)
                            _draft.level.seals.append(_new)
                            _err = _forge_rebuild()
                            if _err:
                                _draft.level.seals.remove(_new)
                                _push(f'Bolt refused — {_err}')
                            elif _mode == 'gone':
                                _push(f'Bolted: {len(_new.opens)} cell(s) open '
                                      f'while no ' + ' nor '.join(_mtch)
                                      + ' stands.')
                            else:
                                _extra = ''
                                if len(_mtch) > 1 and not _reg:
                                    _extra += f' — on {len(_mtch)} distinct rows'
                                if _head >= 0:
                                    _extra += f', first glyph at column {_head}'
                                if _pin >= 0:
                                    _extra += f', pinned to column {_pin}'
                                _push(f'Bolted: {len(_new.opens)} cell(s) open while '
                                      + ('that region reads ' if _reg
                                         else 'some floor row reads ')
                                      + repr(_mtch[0])
                                      + ('' if _mode == 'exact' else ' (anywhere in it)')
                                      + _extra + '.')

                elif (_draft is not None and edit_mode
                      and (_rcmd.rstrip('?!') == 'room'
                           or _rcmd.startswith('room '))):
                    # A level is a DESCENT: walk the exit of one room and the
                    # next begins. The forge shows ONE at a time — there is one
                    # cursor and one screen — so this is how an author moves
                    # between them, adds one, or drops one.
                    #
                    # ROOM, not "chamber": a chamber is part of one map joined to
                    # the rest by a hallway or a door, all inside a single grid.
                    # These are separate grids, and they are what `dungeon.rooms`
                    # has always held.
                    #
                    # Rooms are numbered from ONE here and from zero in the file
                    # (`then[0]` is the second room), because the author's count
                    # should be the one they can see.
                    _arg   = _rcmd.partition(' ')[2].strip()
                    _total = len(_draft.level.rooms)
                    _cur   = _draft.room_index
                    if _rcmd.endswith('!') and not _arg:
                        # Drop the one on screen.
                        try:
                            DRAFT.delete_room(_draft, _cur)
                        except ValueError as _exc:
                            _push(str(_exc))
                        else:
                            _err = _forge_rebuild()
                            _push(f'Room {_cur + 1} removed — '
                                  f'{len(_draft.level.rooms)} left.'
                                  if not _err else f'Refused — {_err}')
                    elif not _arg or _rcmd.endswith('?'):
                        _push(f'Room {_cur + 1} of {_total}. '
                              ':room <n> to move, :room new to add'
                              + (', :room! to remove this one' if _cur else '')
                              + '.')
                    elif _arg == 'new':
                        DRAFT.sync(_draft, room)      # keep what is on screen
                        try:
                            _new_i = DRAFT.add_room(_draft)
                        except ValueError as _exc:
                            _push(str(_exc))
                        else:
                            _was, _draft.room_index = _draft.room_index, _new_i
                            _err = _forge_rebuild()
                            if _err:
                                _draft.room_index = _was
                                _draft.level.then.pop()
                                _forge_rebuild()
                                _push(f'Refused — {_err}')
                            else:
                                _push(f'Room {_new_i + 1} of '
                                      f'{len(_draft.level.rooms)} — a blank '
                                      'room. The one before it opens onto this.')
                    elif _arg.isdigit() and 1 <= int(_arg) <= _total:
                        DRAFT.sync(_draft, room)      # before we leave the room
                        _draft.room_index = int(_arg) - 1
                        _err = _forge_rebuild()
                        if _err:
                            _draft.room_index = _cur
                            _forge_rebuild()
                            _push(f'Refused — {_err}')
                        else:
                            player.row, player.col = room.spawn_pos
                            _push(f'Room {_draft.room_index + 1} of {_total}.')
                    else:
                        _push(f'No room {_arg!r} — there '
                              f'{"is" if _total == 1 else "are"} {_total}.')

                elif (_draft is not None and edit_mode
                      and cmd.partition(' ')[0].rstrip('?!') in _FORGE_META):
                    # `:field value` sets, `:field?` asks, `:field!` clears —
                    # Vim's `:set opt=v` / `:set opt?` split, with the
                    # destructive form spelled out. A bare `:author` used to
                    # CLEAR, which meant a mistyped query silently threw away
                    # what it was asking about; it asks now.
                    _head, _, _val = cmd.partition(' ')
                    _field = _head.rstrip('?!')
                    _val   = _val.strip()
                    _lv    = _draft.level
                    _get, _set = _FORGE_META[_field]
                    if _head == _field and not _val and _field in ('teaches', 'requires'):
                        # …except these two, which hold a SET drawn from a list
                        # the game already knows. A bare one opens that list as
                        # a multi-select, preloaded with what is set: nobody
                        # remembers that the text-object tokens are spelled `iw`
                        # and `a(`, and a field you cannot spell is a field that
                        # ships empty. `:teaches?` is still the plain question.
                        _picked = _pick_many(
                            term, _iw(term), term.height - 8,
                            f'{_field} — space to toggle',
                            _teachable_tokens(), _get(_lv).split())
                        if _picked is None:
                            _push('')                 # backed out of the picker
                        else:
                            _set(_lv, ' '.join(_picked))
                            _push(f'{_field}: {_get(_lv) or "(none)"}'
                                  + (f'   (:{_field} {" ".join(_picked)})'
                                     if _picked else ''))
                    elif _head.endswith('!'):
                        _set(_lv, '')
                        _push(f'{_field}: (cleared)')
                    elif _val and not _head.endswith('?'):
                        _set(_lv, _val)
                        if _field == 'name':
                            # The chrome names the level, so a rename that does
                            # not reach it leaves the author looking at the old
                            # title and doubting the command took.
                            dungeon.name = _lv.name
                        _push(f'{_field}: {_get(_lv)}')
                    else:
                        _push(f'{_field}={_get(_lv) or "(unset)"}')

                elif _draft is not None and cmd == 'meta':
                    _lv = _draft.level
                    _push(f'"{_lv.name}" by {_lv.author or "(nobody)"} — seed {_lv.seed}')
                    _push(f'teaches {_lv.teaches or "nothing"} · '
                          f'requires {_lv.requires or "nothing"}'
                          + (f' · stands in for {_lv.alternate}' if _lv.alternate else ''))
                    _push(f'{len(_lv.fills)} fill(s) · tape: '
                          + (f'{len(_lv.solution)} chars' if _lv.solution else 'not recorded'))

                elif _draft is not None and (cmd == 'canvas'
                                             or cmd.startswith('canvas ')):
                    # THE CANVAS IS A COMMAND. A draft opens on a big field of
                    # stone to carve into precisely because you cannot select a
                    # region larger than the room you are standing in — but a
                    # draft that opened small (or a level imported from one) had
                    # no way to grow, and an author was capped at a size they
                    # never chose. Cropping can be silent because it only ever
                    # takes stone off; growing cannot be, because nothing in a
                    # level says how much room its author still wants.
                    _arg = cmd[len('canvas'):].strip().lower()
                    if not _arg or _arg == '?':
                        _push(f'canvas {room.rows}x{room.cols}'
                              '   (:canvas 40x120 to change it)')
                    else:
                        _m = re.fullmatch(r'(\d+)\s*[x, ]\s*(\d+)', _arg)
                        if not _m:
                            _push('Usage:  :canvas <rows>x<cols>')
                        else:
                            DRAFT.sync(_draft, room)
                            _was = _draft.level
                            try:
                                _draft.level = LF.resize(
                                    _was, int(_m[1]), int(_m[2]))
                            except LF.LevelFormatError as _exc:
                                _push(str(_exc))
                            else:
                                _err = _forge_rebuild()
                                if _err:
                                    _draft.level = _was
                                    _push(f'Canvas unchanged — {_err}')
                                else:
                                    _push(f'Canvas {room.rows}x{room.cols}. '
                                          'The new ground is stone — carve it '
                                          'with :paint floor.')

                elif _draft is not None and cmd in ('play', 'play!'):
                    # PLAYTEST. `:record` was the only way to walk your own level
                    # as a player, and it is the wrong tool for the job: every
                    # take that is not the definitive one still overwrites the
                    # tape you already had, so an author who just wanted to feel
                    # the room out had to either lose their solution or solve the
                    # level perfectly on every rehearsal.
                    #
                    # A rehearsal is a take with the recorder off: the same fresh
                    # build a player downloads, the same declared `requires` +
                    # `teaches` gate, the same untouched save file — and nothing
                    # written down at the end. Losing is allowed, and is in fact
                    # the information you came for.
                    DRAFT.sync(_draft, room)
                    # Under the real budget when the level knows one, because
                    # "can it be done in the budget" is most of the question.
                    # `:play!` is the roam: par None leaves the budget generous,
                    # which is what a half-built level wants.
                    _rep0 = None if cmd.endswith('!') else _draft.report()
                    _ppar = _rep0.par if _rep0 is not None and _rep0.ok else None
                    # A rehearsal is where you first WALK the level, so it is where
                    # a furniture-can't-be-worked problem finally bites — the forge
                    # never gates, so a locked door with no `p`/`P` declared looks
                    # fine on the bench and only fails when someone plays. The
                    # warning rides IN as the level's opening banner, where the
                    # author is standing in the room it names — not as a line back
                    # at the bench after they have already quit the run.
                    _notice = ' '.join(_warn_display(_w)
                                       for _w in (_rep0.warnings[:2]
                                                  if _rep0 is not None else ()))
                    _res  = run_dungeon(term, level, {}, player_name,
                                        _dungeon=_draft.build(par=_ppar),
                                        _known=_draft.level.known,
                                        _notice=_notice or None,
                                        _record={'tape': [], 'error': '', 'off': True,
                                                 'rebuild': lambda s: _draft.build(
                                                     par=_ppar, seed=s)})
                    if _res['won']:
                        _push(f'Playtest cleared — {_res["stars"]} star'
                              f'{"" if _res["stars"] == 1 else "s"}'
                              + (f' against par {_ppar}.' if _ppar else
                                 ' (no budget — :play once there is a tape).'))
                    else:
                        _push('Playtest ended without reaching the exit.'
                              + (f' Budget was {_rep0.budget}.' if _ppar else ''))
                    _forge_rebuild()

                elif _draft is not None and cmd == 'record':
                    # Record the tape by PLAYING the level, not by typing out the
                    # keys you think would solve it.
                    #
                    # The take deliberately does not run here, in the editor: an
                    # editor room has passable walls, no budget and no command
                    # gating, so a route recorded in it would be one no player
                    # could ever follow. It runs on a FRESH build of the level —
                    # the same one a player downloads — under the level's own
                    # declared `requires`+`teaches`, so a key the author forgot
                    # to declare is refused during the take rather than
                    # discovered by a stranger later.
                    DRAFT.sync(_draft, room)
                    # `:e` during a take starts the take again, and deliberately
                    # on the level's OWN seed: a tape holds the letters the
                    # author typed, so re-rolling the fills mid-take would write
                    # down a route through words that no copy of the level has.
                    # (A rehearsal has no such worry and does re-roll.)
                    _rec  = {'tape': [], 'error': '',
                             'rebuild': lambda _s: _draft.build()}
                    _take = _draft.build()
                    _res  = run_dungeon(term, level, {}, player_name,
                                        _dungeon=_take, _known=_draft.level.known,
                                        _record=_rec)
                    _tape = ''.join(_rec['tape'])
                    if _rec['error']:
                        _push(f'Take discarded — {_rec["error"]}')
                    elif not _res['won']:
                        _push('Take discarded — that run never reached the exit.')
                    else:
                        _draft.level.solution = _tape
                        _rep = _draft.report()
                        if _rep.ok:
                            _push(f'Tape recorded — par {_rep.par}, budget {_rep.budget}.')
                            for _w in _rep.warnings[:2]:
                                _push(_warn_display(_w))
                        else:
                            # The take won on screen but will not replay. Almost
                            # always the level moved under it (an edit since the
                            # last build), and the tape is worth less than the
                            # warning, so say so and keep it for inspection.
                            _push(f'Take kept, but it does not replay: {_rep.errors[0]}')
                    try:
                        DRAFT.save(_draft)
                    except DRAFT.DraftNameCollision as exc:
                        _push(str(exc))
                    _forge_rebuild()

                elif _draft is not None and cmd in ('check', 'publish'):
                    DRAFT.sync(_draft, room)
                    _rep = _draft.report()
                    for _e in _rep.errors[:3]:
                        _push(_e)
                    for _w in _rep.warnings[:2]:
                        _push(_warn_display(_w))
                    if not _rep.ok:
                        _push('Not shippable yet.' if cmd == 'publish' else 'Not valid yet.')
                    elif cmd == 'check':
                        _push(f'Valid — par {_rep.par}, budget {_rep.budget}.')
                    else:
                        try:
                            _dest = DRAFT.publish(_draft)[0]
                            DRAFT.save(_draft)
                        except DRAFT.DraftNameCollision as exc:
                            _push(str(exc))
                        else:
                            _push(f'Published to {_dest.name} — par {_rep.par}, '
                                  f'budget {_rep.budget}. It is on the shelf.')

                elif _draft is not None and cmd == 'submit':
                    # Same gate as `:publish` — the forge only opens for the
                    # admin, and the validator has to have replayed the tape to
                    # a win before anything leaves this machine. A level that
                    # does not validate is one a stranger cannot finish, and a
                    # pull request is a person's time.
                    DRAFT.sync(_draft, room)
                    _rep = _draft.report()
                    if not _rep.ok:
                        for _e in _rep.errors[:3]:
                            _push(_e)
                        _push('Not shippable yet — nothing submitted.')
                    elif not _draft.level.author.strip():
                        # Never guessed from the save name. The byline goes in a
                        # public repo under whatever the author wants to be
                        # called there, which is theirs to decide and nobody
                        # else's to assume.
                        _push('Set a byline first: :author <name> — it is how '
                              'you will be credited.')
                    else:
                        for _w in _rep.warnings[:2]:
                            _push(_warn_display(_w))
                        _push(run_submit(term, _iw(term), term.height - 8,
                                         _draft.level,
                                         SUBMIT.submit_slug(_draft.level), _rep))

                elif cmd in ('noh', 'nohl', 'nohls', 'nohlsearch'):
                    # :noh — clear the search highlight until the next search.
                    if '/' in player.known_commands or player_name == 'admin':
                        player.hl_suppressed = True
                        _push(':nohlsearch')
                    else:
                        _push("You haven't learned search yet.")

                elif cmd.split()[0:1] == ['set'] and cmd[len('set'):].strip() in (
                        'hat', 'nohat', 'hat!', 'invhat', 'hat?'):
                    # The Warden's hat — worn via `:set hat` once looted (The
                    # Warden Eternal). Vim-faithful `:set` idiom; wearing it makes
                    # every spell available anywhere (admin sentinel) and shimmers
                    # the cursor. Gated behind actually holding the hat.
                    _hb = cmd[len('set'):].strip()
                    if not (player.has_hat or player_name == 'admin'):
                        _push("You have no hat to wear.")
                    elif _hb == 'hat?':
                        _push('hat' if player.hat_worn else 'nohat')
                    else:
                        _worn = (not player.hat_worn) if _hb in ('hat!', 'invhat') \
                                else (_hb == 'hat')
                        player.hat_worn = _worn
                        if _worn and 'admin' not in player.known_commands:
                            player.known_commands = player.known_commands + ['admin']
                        elif not _worn and player_name != 'admin':
                            player.known_commands = [c for c in player.known_commands
                                                     if c != 'admin']
                        progress['has_hat']  = player.has_hat
                        progress['hat_worn'] = player.hat_worn
                        _save_progress(progress, player_name)
                        _push("The Warden's hat settles on your brow — every spell is yours."
                              if _worn else "You doff the hat; the old bounds return.")

                elif cmd.split()[0:1] == ['set']:
                    # :set number/relativenumber + the boolean hlsearch/incsearch,
                    # each with toggle (!/inv), reset (&) and query (?) forms.
                    # Unlocked by the Waypoint Sanctum scroll ('setnum').
                    if ('setnum' not in player.known_commands and player_name != 'admin'
                            and level != 'archivists_library'):
                        _push("You haven't learned :set yet.")
                    else:
                        _core, _act = _parse_set_mod(cmd[len('set'):])
                        _flag = ('hlsearch'  if _core in ('hlsearch', 'hls') else
                                 'incsearch' if _core in ('incsearch', 'is') else
                                 'wrap'      if _core in ('wrap',)            else None)
                        if _flag is not None:
                            _cur = getattr(player, _flag)
                            _new = {'on': True, 'off': False, 'reset': True,
                                    'toggle': not _cur, 'query': _cur}[_act]
                            setattr(player, _flag, _new)
                            if _flag == 'hlsearch':
                                player.hl_suppressed = False
                            _lib_wrap = (level == 'archivists_library' and _flag == 'wrap')
                            if _act == 'query':
                                _push(_flag if _cur else 'no' + _flag)
                            elif not _lib_wrap:
                                _push((':set ' if _act in ('on', 'reset') else '')
                                      + (_flag if _new else 'no' + _flag))
                            if _lib_wrap and _new and not getattr(room, 'lib_done', None):
                                _push('You see someone pacing among the shelves!')
                        else:
                            player.number_mode, _set_msg = _apply_set(
                                player.number_mode, cmd[len('set'):])
                            _push(_set_msg)

                elif cmd == 'h' or cmd == 'help' or cmd.startswith(('h ', 'help ')):
                    # :h [{name}] — open the Codex read-only in a split and move
                    # focus into it (Vim's :help, made diegetic). Reading is
                    # free: neither the command nor any pane key spends budget.
                    # Gated on actually HOLDING the Codex ('readers_key', the
                    # Binder's chest grant) — the level's 'help' token alone
                    # isn't a book in your hands.
                    if 'help' not in player.known_commands and player_name != 'admin':
                        _push("You haven't learned :h yet.")
                    elif ('readers_key' not in player.known_commands
                          and player_name != 'admin'):
                        _push('You carry no codex to open.')
                    else:
                        from vimny.engine.codex import CodexPane, scroll_sections
                        from vimny.content.scrolls import SCROLL_CATALOG, RELIC_SCROLL_IDS
                        from vimny.content.blessings import blessing_sections
                        _extras = progress.get('extras', [])
                        _codex_cat  = [s for s in SCROLL_CATALOG if s['id'] not in RELIC_SCROLL_IDS]
                        _relic_cat  = [s for s in SCROLL_CATALOG if s['id'] in RELIC_SCROLL_IDS]
                        _codex_secs = (scroll_sections(_codex_cat, _extras)
                                       + list(getattr(room, '_codex_extra', ())))
                        _relic_secs = scroll_sections(_relic_cat, _extras)
                        _bless_secs = blessing_sections(progress.get('blessings_seen', []))
                        _groups = [g for g in (('codex', _codex_secs),
                                               ('relics', _relic_secs),
                                               ('blessings', _bless_secs)) if g[1]]
                        if not _groups:
                            _push('The Codex is empty — no pages bound yet.')
                        else:
                            _arg = cmd.split(' ', 1)[1].strip() if ' ' in cmd else ''
                            _pane = CodexPane(groups=_groups)
                            if _arg and not _pane.jump_to(_arg):
                                _push(f'E149: Sorry, no help for {_arg}')
                            else:
                                player.codex_pane = _pane

                elif cmd == 'help!':
                    player.error = "E478: Don't panic!"      # Vim's own joke
                elif cmd in ('smile', 'smile!'):
                    _push('ᕕ( ᐛ )ᕗ  the old wizard grins back at you.')
                elif cmd in ('Ni', 'Ni!'):
                    _push('The wizard blinks. "We demand... a shrubbery!"')
                elif cmd == 'xyzzy':
                    _push('Nothing happens.')                # Colossal Cave, honoured

                elif cmd.isdigit():
                    # :{n} — go to line n (Vim-true). Same semantics as {n}G
                    # (lands on the row's first non-blank), gated on G, and
                    # always a key dearer than {n}G (the colon) — never a golf.
                    if 'G' not in player.known_commands and player_name != 'admin':
                        _push("You haven't learned G/gg yet.")
                    elif not edit_mode and budget.remaining <= 0:
                        _push('Out of budget!  (u to undo)')
                    else:
                        _gn_from  = (player.row, player.col)
                        _gn_spent = budget.spent
                        moved = apply_motion(player, 'G', int(cmd), room, None,
                                             count_given=True,
                                             game_h=term.height - 8)
                        if moved and not edit_mode:
                            _record_jump(player, _gn_from)
                            if not _bar_paid:
                                budget.spend(len(cmd) + 1)
                            undo_stack.append((_gn_from[0], _gn_from[1], _gn_spent,
                                               cmd_start_ans[0], cmd_start_ans[1]))
                            redo_stack.clear()

                elif (_subst.looks_like_sg(cmd, room, player)
                      and _goblin_substitute(cmd, room, player, _push)):
                    _boom = getattr(room, '_pending_boom', None)
                    if _boom:                        # :s/g/!/ — cheerful flame
                        room._pending_boom = []
                        _push('The goblins burst into cheerful flame. !!')
                        _render(_pool_msg())
                        for (_br, _bc) in _boom:
                            _goblin_boom(_br, _bc)
                        if player.is_dead:
                            message = '** GAME OVER ** Type  :e  to re-load the dungeon.'
                            msg_ttl = 2
                            _render(message)

                elif (_subst.looks_like_sg(cmd, room, player)
                      or _subst.looks_like_ex_range(cmd, room, player)):
                    _ex_tok = ('subst' if _subst.looks_like_sg(cmd, room, player)
                               else 'ex_range')
                    if _ex_tok not in player.known_commands and player_name != 'admin':
                        player.error = 'E492: Not an editor command: ' + cmd
                    else:
                        _pre = _snapshot(room, player, budget, ans=cmd_start_ans)
                        _sg_h, _sg_msg, _ns, _nl = _subst.run_ex(
                            cmd, room, player, confirm=_sub_confirm,
                            insert_row=_sub_insert_row, delete_row=_sub_delete_row)
                        if _sg_h and (_ns or _nl):
                            undo_stack.append(_pre)
                            redo_stack.clear()
                            if not edit_mode and not _bar_paid:
                                budget.spend(len(cmd) + 1)
                            room.rebuild_indexes()
                            _animate_reflow_falls()      # :> can shove glyphs off the brink
                            _content_ticks()   # an ex edit opens its gate THIS turn
                            if _sg_msg:
                                _push(_sg_msg)
                        elif _sg_msg and _sg_msg.startswith('E'):
                            player.error = _sg_msg
                        elif _sg_msg:
                            _push(_sg_msg)

                elif _vrange:
                    # Caught, not parsed. `:` from VISUAL hands you a range
                    # because most of what you do to a selection wants one; the
                    # commands addressed to the DRAFT rather than to any part of
                    # the map (`:w`, `:teaches`, `:name`) have nothing a region
                    # could mean, and running one with the range ignored would
                    # teach the author that the prefix is decoration.
                    _push(f":{_rcmd.split()[0] if _rcmd else '(nothing)'} does not "
                          'take a range — Esc the command line and type it plain.')

                else:
                    _push(f'Unknown command: :{cmd}')

            elif key.name == 'KEY_BACKSPACE' or str(key) == '\x7f':
                _cmd_backspace(player)
            elif _cmd_arrow(player, key):                  # ←/→/Home/End: edit mid-line
                pass
            elif search_creg_pending:
                # second key after <C-r>: <C-w> pulls the word under the cursor,
                # otherwise the named register's text, into the search line.
                search_creg_pending = False
                if not key.is_sequence:
                    if str(key) == '\x17':
                        _cmd_insert(player, _word_under_cursor(room, player) or '')
                    else:
                        _cmd_insert(player, _clip_to_text(_reg_read(player, str(key))))
            elif str(key) == '\x12':                       # <C-r> — insert into the search line
                search_creg_pending = True
            elif not key.is_sequence:
                _cmd_insert(player, str(key))              # insert AT the cursor
                if (getattr(room, '_cmd_karaoke', False)
                        and len(str(key)) == 1):
                    _advance_answer(str(key))              # karaoke: advance per typed cmd char
            if msg_pool:
                msg_idx = 0
                message = _pool_msg()
                msg_ttl = _MSG_ROTATE_TTL
            _render(message)
            continue

        # ── SEARCH mode (/ or ? pattern entry) ────────────────────────────────
        if player.mode == Mode.SEARCH:
            if key.name == 'KEY_ESCAPE':
                player.mode = search_return_mode or Mode.NORMAL   # back to visual if launched there
                search_return_mode = None
                player.cmd_line = ''
                player.cmd_cursor = 0
                room._search_karaoke = False
            elif key.name == 'KEY_ENTER' or str(key) in ('\n', '\r'):
                if getattr(room, '_search_karaoke', False):
                    _advance_answer(_TAPE_ENTER)          # the tape marks Enter <CR>
                    room._search_karaoke = False
                pattern = player.cmd_line
                fwd     = player.search_forward
                # A search launched from visual mode is a MOTION that extends the
                # selection: resume that visual mode (anchor intact) and just move the
                # cursor — no jumplist/undo entry, exactly like any visual-mode motion.
                from_visual     = search_return_mode is not None
                player.mode     = search_return_mode or Mode.NORMAL
                search_return_mode = None
                player.cmd_line = ''
                player.cmd_cursor = 0
                if pattern:
                    player.last_search = (pattern, fwd)
                    player.hl_suppressed = False        # a fresh search re-lights matches
                    dest = _search_next(room, player, pattern, fwd)
                    if dest is not None:
                        pre = (player.row, player.col, budget.spent,
                               cmd_start_ans[0], cmd_start_ans[1])
                        if not from_visual:
                            _record_jump(player, (player.row, player.col))
                        player.row, player.col = dest
                        if not edit_mode:
                            _scost = len(pattern) + 1   # '/' charged, closing Enter free (terminator is free everywhere)
                            budget.spend(_scost)
                            player.pending_recost_s = 0      # a fresh search is paid
                            if not from_visual:
                                undo_stack.append(pre + (('s', _scost),))
                                redo_stack.clear()
                            # A search LANDING fires the gate ticks THIS turn
                            # (the insert-Esc pattern): the Waypoint's plugh
                            # reveal must wake on the ? that lands you in the
                            # pocket, not one keystroke later.
                            _content_ticks()
                    else:
                        _push(f'Pattern not found: {pattern}')
            elif key.name == 'KEY_BACKSPACE' or str(key) == '\x7f':
                _cmd_backspace(player)
            elif _cmd_arrow(player, key):                  # ←/→/Home/End on the search line
                pass
            elif not key.is_sequence:
                _cmd_insert(player, str(key))
                if (getattr(room, '_search_karaoke', False)
                        and len(str(key)) == 1):
                    _advance_answer(str(key))              # karaoke: advance per pattern char
            _render(message)
            continue

        # ── INSERT mode (admin text placement) ───────────────────────────────
        if player.mode == Mode.INSERT:
            if key.name == 'KEY_ESCAPE':
                # Karaoke: the tape marks Esc `<Esc>`. It used to be omitted (a
                # player following the sheet can infer that typing ends), but an
                # omitted key cannot be REPLAYED — see vimny/engine/tape.py. Esc spends
                # no budget, so writing it changes no level's par.
                if player_name == 'admin' and room.answer:
                    _advance_answer(_TAPE_ESC)
                if block_ins is not None:
                    # Block insert (<C-v> I… / c…): on Esc the typed run
                    # replays into every other selected row at the anchor
                    # column, each row reflowing independently (Vim-true).
                    # The replay is not typing: it spends no budget and does
                    # not advance the karaoke tape.
                    _br, _bc = player.row, player.col
                    for _row in block_ins['rows']:
                        if not room.is_passable(_row, block_ins['col']):
                            continue        # Vim skips lines the block misses
                        player.row, player.col = _row, block_ins['col']
                        for _bch in block_ins['buf']:
                            insert_char(room, player, _bch)
                    player.row, player.col = _br, _bc
                    block_ins = None
                    if not edit_mode:
                        _animate_reflow_falls()
                if not edit_mode and isinstance(player.last_change, dict):
                    # '.' replays the whole change INCLUDING the typed text
                    # (Vim-true — every INSERT entry records last_change first)
                    player.last_change = {**player.last_change,
                                          'typed': insert_typed}
                insert_typed = ''
                player.mode = Mode.NORMAL
                # gi's anchor: where INSERT was last left, recorded BEFORE
                # the Esc retreat (Vim-true — gi resumes at the ink, not a
                # column shy of it).
                player.last_insert = (player.row, player.col)
                # Vim retreats one column on leaving INSERT. Also the safety
                # net for water-writing: `a` at a bank hovers the cursor on
                # the flood; the retreat steps back onto written ground.
                if not edit_mode and player.col > 0 \
                        and room.is_passable(player.row, player.col - 1):
                    player.col -= 1
                key_buf = ''
                insert_creg_pending = False
                insert_co_buf = None
                if not edit_mode:
                    _content_ticks()    # a completed write opens its gate THIS turn
                    if msg_pool:        # surface its "bolt grinds back" this render
                        msg_idx = 0
                        message = _pool_msg(); msg_ttl = _MSG_ROTATE_TTL
            elif edit_mode:
                r, c = player.row, player.col
                if key.name == 'KEY_BACKSPACE' or str(key) == '\x7f':
                    if c > 0:
                        ed_undo.append(_ed_snapshot(room, player))
                        player.col -= 1
                        _ed_cut(room, r, player.col)
                        _merge_adjacent_char_runs(room, r)
                elif not key.is_sequence:
                    ch = str(key)
                    if _in_fill(room, r, c):
                        _push('A fill grows that text — :fill! to make it yours.')
                    elif ch.isprintable() and len(ch) == 1:
                        ed_undo.append(_ed_snapshot(room, player))
                        _ed_cut(room, r, c)
                        room.add_char_run(CharRun(row=r, col=c,
                                                  symbols=(ch,), kind='ember'))
                        _merge_adjacent_char_runs(room, r)
                        if c + 1 < room.cols:
                            player.col += 1
            else:
                # Player INSERT typing (one undo snapshot was pushed on entry).
                _ins_ok = lambda tok: tok in player.known_commands or 'admin' in player.known_commands
                _kstr = '' if key.is_sequence else str(key)

                if insert_co_buf is not None:
                    # <C-o>: accumulate ONE Normal-mode motion, apply it, resume INSERT.
                    if key.name == 'KEY_ESCAPE':
                        insert_co_buf = None
                    elif not key.is_sequence:
                        insert_co_buf += str(key)
                        _co_act, _ = parse(insert_co_buf, Mode.NORMAL)
                        if _co_act is not None:
                            if _co_act.get('type') == 'motion' and (
                                    edit_mode or _action_allowed(_co_act, player.known_commands)):
                                apply_motion(player, _co_act['motion'], _co_act.get('count', 1),
                                             room, _co_act.get('target'),
                                             count_given=_co_act.get('count_given', True))
                            insert_co_buf = None
                    _render(message)
                    continue

                if insert_creg_pending:
                    # second key after <C-r>: the register name (or <C-w> for the word).
                    insert_creg_pending = False
                    if not key.is_sequence:
                        if str(key) == '\x17':                  # <C-r><C-w> → word under cursor
                            _ins_text = _word_under_cursor(room, player) or ''
                        else:
                            _ins_text = _clip_to_text(_reg_read(player, str(key)))
                        for _tch in _ins_text:
                            if _tch == '\n':
                                break
                            if insert_char(room, player, _tch):
                                budget.spend(1)
                    _render(message)
                    continue

                if _kstr == '\x12' and _ins_ok('ins_paste'):     # <C-r> — paste a register
                    insert_creg_pending = True
                    _render(message)
                    continue
                if _kstr == '\x0f' and _ins_ok('ins_edit'):      # <C-o> — one Normal command
                    insert_co_buf = ''
                    _render(message)
                    continue
                if _kstr == '\x17' and _ins_ok('ins_edit'):      # <C-w> — delete word back
                    insert_delete_word_back(room, player)
                    _render(message)
                    continue
                if _kstr == '\x15' and _ins_ok('ins_edit'):      # <C-u> — delete to line start
                    insert_delete_to_start(room, player)
                    _render(message)
                    continue

                if key.name == 'KEY_ENTER' or str(key) in ('\n', '\r'):
                    # <Enter> in INSERT — the bounded vertical line-split (mirror of
                    # open_gap). The tail drops to the next line at col 0; rows below
                    # shift straight down; the dungeon never grows, so anything pushed
                    # over a wall / void rune falls into the void. Walls/entities stay
                    # fixed. The whole insert session is one undo, so no extra snapshot.
                    room._last_void_falls = []
                    room._last_drowns     = []
                    split_line_down(room, player)
                    budget.spend(1)
                    insert_typed += '\n'
                    _animate_reflow_falls()
                elif key.name == 'KEY_BACKSPACE' or str(key) == '\x7f':
                    insert_backspace(room, player)
                    if block_ins is not None and block_ins['buf']:
                        block_ins['buf'] = block_ins['buf'][:-1]
                    insert_typed = insert_typed[:-1]
                elif not key.is_sequence:
                    ch = str(key)
                    if ch.isprintable() and len(ch) == 1:
                        # Admin karaoke: typed INSERT chars advance the answer
                        # tape too (the NORMAL-mode tracker at the top of the
                        # loop never sees them), so a c{m}/i/a answer that
                        # includes its typed text stays in sync. Esc is a
                        # sequence key and is skipped, exactly as in NORMAL.
                        if (player_name == 'admin' and room.answer
                                and not room.answer_diverged):
                            _ap = room.answer.replace(' ', '')
                            # a TYPED space is marked <Space> in the tape (plain
                            # spaces are separators, stripped above)
                            _ck = _TAPE_SPACE if ch == ' ' else ch
                            if room.answer_pos < len(_ap):
                                if _ap.startswith(_ck, room.answer_pos):
                                    room.answer_pos += len(_ck)
                                else:
                                    room.answer_diverged = True
                        prev_ins = (player.row, player.col)
                        room._last_void_falls = []
                        room._last_drowns     = []
                        if player.insert_extend:               # A: build new ledge into the void
                            if insert_char_extend(room, player, ch):
                                budget.spend(1)
                            elif room._last_build_blocked == 'edge':
                                message = _EDGE_OF_WORLD_MSG; msg_ttl = 25
                        elif insert_char(room, player, ch):
                            budget.spend(1)
                            if block_ins is not None:
                                block_ins['buf'] += ch   # replayed per row on Esc
                            insert_typed += ch           # '.' replays this on Esc
                        _animate_reflow_falls()
                        cur_ru = room.char_run_at(player.row, player.col)
                        if cur_ru is not None and cur_ru.kind == 'void':   # typed yourself off the ledge
                            _render(message)
                            _void_fall_animation(term, *_void_screen_xy(term, room, player, player.row, player.col))
                            player.take_damage(2)                          # 1 full heart
                            # From the cursor's OWN column: a row split by stone
                            # has more than one brink, and the nearest one west
                            # belongs to a segment the typist was never in.
                            safe_c = min(prev_ins[1],
                                         void_col(room, prev_ins[0], prev_ins[1]) - 1)
                            player.row, player.col = prev_ins[0], max(safe_c, 0)   # stumble back to safe ground
                            player.mode = Mode.NORMAL
                            if player.is_dead:
                                message = '** GAME OVER ** Type  :e  to re-load the dungeon.'; msg_ttl = 2
                            else:
                                message = f'You typed yourself off the ledge!  {_hearts_note(player.hp)}'; msg_ttl = 25
            _render(message)
            continue

        # ── REPLACE mode (overtype; Backspace restores originals) ─────────────
        if player.mode == Mode.REPLACE:
            if key.name == 'KEY_ESCAPE':
                if player_name == 'admin' and room.answer:
                    _advance_answer(_TAPE_ESC)      # the tape marks Esc <Esc>
                player.mode = Mode.NORMAL
                if player.col > 0 and room.is_passable(player.row, player.col - 1):
                    player.col -= 1                    # vim retreats one on Esc
                replace_stack = []
                key_buf = ''
                if not edit_mode:
                    _content_ticks()    # a completed overtype opens its gate THIS turn
                    if msg_pool:        # surface its gate message this render
                        msg_idx = 0
                        message = _pool_msg(); msg_ttl = _MSG_ROTATE_TTL
            elif key.name == 'KEY_BACKSPACE' or str(key) == '\x7f':
                if replace_stack:
                    replace_restore(room, player, replace_stack.pop())
            elif not key.is_sequence:
                ch = str(key)
                if ch.isprintable() and len(ch) == 1:
                    rec = replace_overtype(room, player, ch)
                    if rec is not None:
                        replace_stack.append(rec)
                        if not edit_mode:
                            budget.spend(1)
                    _advance_answer(ch)     # karaoke: R-mode chars advance the tape too
            _render(message)
            continue

        # ── VISUAL modes (v / V / Ctrl-v): extend selection, operate ────────────
        if player.mode in (Mode.VISUAL, Mode.VISUAL_LINE, Mode.VISUAL_BLOCK):
            vmode = player.mode
            if key.name == 'KEY_ESCAPE':
                if player.visual_anchor is not None:
                    # Remember the area being abandoned. Vim's `gv` reselects
                    # the last visual area whether an operator was applied to it
                    # or not, and anything else that reads `'<,'>` after the
                    # fact — the forge's `:fill` — needs the selection the
                    # player just made rather than the one before it. Saved
                    # BEFORE the cursor is walked back to the anchor, or the two
                    # ends of the selection would collapse into one.
                    player.last_visual_anchor = player.visual_anchor
                    player.last_visual_cursor = (player.row, player.col)
                    player.last_visual_mode   = vmode
                    player.row, player.col = player.visual_anchor
                player.mode = Mode.NORMAL
                player.visual_anchor = None
                key_buf = ''
                visual_r_pending = False
                _render(message)
                continue
            raw = str(key) if not key.is_sequence else ''
            anchor = player.visual_anchor or (player.row, player.col)
            cursor = (player.row, player.col)
            if visual_r_pending:
                # the overstrike char for a visual r
                visual_r_pending = False
                if raw and raw.isprintable() and len(raw) == 1:
                    undo_stack.append(_snapshot(room, player, budget,
                                                row=anchor[0], col=anchor[1],
                                                spent=player.visual_start_spent,
                                                ans=cmd_start_ans))
                    redo_stack.clear()
                    apply_visual_replace(room, player, anchor, cursor, vmode, raw)
                    budget.spend(2)                     # r + the char
                    player.last_visual_anchor = anchor
                    player.last_visual_cursor = cursor
                    player.last_visual_mode = vmode
                    player.visual_anchor = None
                    player.mode = Mode.NORMAL
                    player.last_change = {'type': 'visual_op', 'op': 'r'}
                    if not edit_mode:
                        _content_ticks()
                        message = _pool_msg() or message
                _render(message)
                continue
            # `:` from VISUAL — vim leaves visual mode and opens the command
            # line prefilled with `'<,'>`, having stamped the selection into
            # those two marks on the way out. That is what makes `:fill` (and
            # `:'<,'>s/…`) reachable without the Esc dance: the selection does
            # not have to still be OPEN, it has to still be REMEMBERED. The
            # prefilled range is also the only thing on screen that says the
            # selection survived the keystroke that visibly cleared it.
            if not key_buf and raw == ':':
                player.last_visual_anchor = anchor
                player.last_visual_cursor = cursor
                player.last_visual_mode   = vmode
                player.visual_anchor = None
                player.mode = Mode.COMMAND
                player.cmd_line = "'<,'>"
                player.cmd_cursor = len(player.cmd_line)
                room._cmd_karaoke = False   # no shipped tape enters `:` from visual
                _render(message)
                continue
            # Single-key visual commands (only when not mid multi-key motion)
            if not key_buf and raw in ('o', 'O'):          # swap ends / corners
                # Both live in engine/visual.swap_ends: selection shaping is
                # that module's job, and a rule kept in the key loop is a rule
                # no unit test can reach.
                player.visual_anchor, (player.row, player.col) = _swap_ends(
                    anchor, cursor, vmode, corner=(raw == 'O'))
                _render(message)
                continue
            want = _visual_mode_toggle(raw, str(key)) if not key_buf else None
            if want is not None:                           # v / V / Ctrl-v toggle / exit
                # Switching INTO a sibling mode is gated per token, same as
                # entering it from NORMAL (pressing the current mode's own key
                # exits, which is always allowed).
                _wtok = {Mode.VISUAL: 'visual', Mode.VISUAL_LINE: 'visual_line',
                         Mode.VISUAL_BLOCK: 'visual_block'}[want]
                if want != vmode and not (_wtok in player.known_commands
                                          or 'admin' in player.known_commands):
                    _push(f"You haven't learned {_wtok} mode yet.")
                    _render(message)
                    continue
                player.mode = Mode.NORMAL if want == vmode else want
                if player.mode == Mode.NORMAL:
                    player.visual_anchor = None
                _render(message)
                continue
            if not key_buf and raw in ('/', '?'):          # search extends the selection
                if not ('/' in player.known_commands or 'admin' in player.known_commands):
                    _push('Search not learned yet.')
                elif not edit_mode and budget.remaining <= 0:
                    _push('Out of budget!  (Esc, then u to undo)')
                    message = _pool_msg(); msg_ttl = _MSG_ROTATE_TTL
                else:
                    search_return_mode = vmode             # resume this visual mode on <enter>
                    player.mode = Mode.SEARCH
                    player.cmd_line = ''
                    player.search_forward = (raw == '/')
                    room._search_karaoke = (player_name == 'admin' and bool(room.answer)
                                            and not room.answer_diverged)
                _render(message)
                continue
            if raw == 'r' and not key_buf:
                # visual r{ch} — overstrike every selected character
                if not ('visual_op' in player.known_commands
                        or 'admin' in player.known_commands):
                    _push("You haven't learned visual operators yet.")
                elif not edit_mode and budget.remaining <= 0:
                    _push('Out of budget!  (Esc, then u to undo)')
                    message = _pool_msg(); msg_ttl = _MSG_ROTATE_TTL
                else:
                    visual_r_pending = True
                _render(message)
                continue
            if raw == 'J' and key_buf in ('', 'g'):
                # visual J / gJ — join every line the selection touches
                _vj_gap = (key_buf == '')
                key_buf = ''
                if not ('visual_op' in player.known_commands
                        or 'admin' in player.known_commands):
                    _push("You haven't learned visual operators yet.")
                    _render(message)
                    continue
                if not edit_mode and budget.remaining <= 0:
                    _push('Out of budget!  (Esc, then u to undo)')
                    message = _pool_msg(); msg_ttl = _MSG_ROTATE_TTL
                    _render(message)
                    continue
                undo_stack.append(_snapshot(room, player, budget,
                                            row=anchor[0], col=anchor[1],
                                            spent=player.visual_start_spent,
                                            ans=cmd_start_ans))
                redo_stack.clear()
                _r1 = min(anchor[0], cursor[0])
                _joins = max(abs(anchor[0] - cursor[0]), 1)
                player.row, player.col = _r1, min(anchor[1], cursor[1])
                player.last_visual_anchor = anchor
                player.last_visual_cursor = cursor
                player.last_visual_mode = vmode
                player.visual_anchor = None
                player.mode = Mode.NORMAL
                if op_join(room, player, gap=_vj_gap, count=_joins):
                    budget.spend(1 if _vj_gap else 2)
                    player.last_change = {'type': 'visual_op', 'op': 'J'}
                    _push('Joined.')
                else:
                    undo_stack.pop()
                    _push('Nothing to join.')
                if not edit_mode:
                    _content_ticks()
                    message = _pool_msg() or message
                _render(message)
                continue
            if raw == 'p' and not key_buf:
                # visual p — paste OVER the selection: the selection dies to
                # the unnamed register (Vim-true) and the held clip lands in
                # its place
                if not ('visual_op' in player.known_commands
                        or 'admin' in player.known_commands):
                    _push("You haven't learned visual operators yet.")
                    _render(message)
                    continue
                if not edit_mode and budget.remaining <= 0:
                    _push('Out of budget!  (Esc, then u to undo)')
                    message = _pool_msg(); msg_ttl = _MSG_ROTATE_TTL
                    _render(message)
                    continue
                _vp_clip = _reg_read(player, '"')
                if _vp_clip is None:
                    _push('Nothing in the register.')
                    _render(message)
                    continue
                undo_stack.append(_snapshot(room, player, budget,
                                            row=anchor[0], col=anchor[1],
                                            spent=player.visual_start_spent,
                                            ans=cmd_start_ans))
                redo_stack.clear()
                _vp_cut = apply_visual('d', anchor, cursor, vmode, room, player)
                _reg_write(player, '"', _vp_cut, is_delete=True)
                op_paste(room, player, _vp_clip, True, 1)
                budget.spend(1)
                player.last_visual_anchor = anchor
                player.last_visual_cursor = cursor
                player.last_visual_mode = vmode
                player.visual_anchor = None
                player.mode = Mode.NORMAL
                player.last_change = {'type': 'visual_op', 'op': 'p'}
                if not edit_mode:
                    _content_ticks()
                    message = _pool_msg() or message
                _render(message)
                continue
            if not key_buf and raw in ('I', 'A') and vmode == Mode.VISUAL_BLOCK:
                # Block insert/append: INSERT opens at the block's top-left
                # (I) or one past its right edge (A); on Esc the typed run
                # replays into every other selected row (the block_ins state;
                # see the INSERT Esc handler).
                if not ('visual_op' in player.known_commands
                        or 'admin' in player.known_commands):
                    _push("You haven't learned visual operators yet.")
                    _render(message)
                    continue
                if not edit_mode and budget.remaining <= 0:
                    _push('Out of budget!  (Esc, then u to undo)')
                    message = _pool_msg(); msg_ttl = _MSG_ROTATE_TTL
                    _render(message)
                    continue
                _r1, _r2, _c1, _c2 = block_bounds(anchor, cursor)
                _icol = _c1 if raw == 'I' else min(_c2 + 1, room.cols - 1)
                undo_stack.append(_snapshot(room, player, budget,
                                            row=anchor[0], col=anchor[1],
                                            spent=player.visual_start_spent,
                                            ans=cmd_start_ans))
                redo_stack.clear()
                player.row, player.col = _r1, _icol
                player.visual_anchor = None
                player.mode = Mode.INSERT
                insert_typed = ''
                block_ins = {'rows': list(range(_r1 + 1, _r2 + 1)),
                             'col': _icol, 'buf': ''}
                budget.spend(1)
                key_buf = ''
                _render(message)
                continue
            if not key_buf and raw and raw in 'dycx~<>Uu':
                # U / u on a live selection are the case SETS (gU / gu) —
                # Vim-true: u with a selection lowercases, it is NOT undo.
                op = {'x': 'd', '~': 'g~', 'U': 'gU', 'u': 'gu'}.get(raw, raw)
                if raw in 'dyc~<>Uu' and not (
                        'visual_op' in player.known_commands or 'admin' in player.known_commands):
                    _push("You haven't learned visual operators yet.")
                    _render(message)
                    continue
                if not edit_mode and budget.remaining <= 0:
                    _push('Out of budget!  (Esc, then u to undo)')
                    message = _pool_msg(); msg_ttl = _MSG_ROTATE_TTL
                    _render(message)
                    continue
                undo_stack.append(_snapshot(room, player, budget,
                                            row=anchor[0], col=anchor[1],
                                            spent=player.visual_start_spent,
                                            ans=cmd_start_ans))
                redo_stack.clear()
                clip = apply_visual(op, anchor, cursor, vmode, room, player)
                if op == 'y':
                    _reg_write(player, '"', clip, is_delete=False)
                elif op in ('d', 'c'):
                    _reg_write(player, '"', clip, is_delete=True)
                if player.last_parry:
                    msg_pool.clear()
                    _immune_wardens = [e for e in room.entities
                                       if e.alive and e.kind == 'warden' and e.edit_immune]
                    if _immune_wardens:
                        # The Warden is a creature, not text — a line-cut can't pin him.
                        # He twists out of the selection (bounds away); only x lands.
                        for _w in _immune_wardens:
                            if room.rows > 2:
                                _do_warden_move(room, _w, player)
                        room._ward_flash = {(_w.row, _w.col) for _w in _immune_wardens}
                        _push('The Warden twists out of your cut — only a precise x can land on him!')
                    else:
                        # A warded door (or other anchored fixture) parried instead.
                        _push('The cut is parried — something in the selection is anchored fast.')
                    message = _pool_msg(); msg_ttl = _MSG_ROTATE_TTL
                budget.spend(1)
                player.last_visual_anchor = anchor
                player.last_visual_cursor = cursor
                player.last_visual_mode = vmode
                player.visual_anchor = None
                player.mode = Mode.INSERT if op == 'c' else Mode.NORMAL
                if op == 'c':
                    insert_typed = ''
                if op == 'c' and vmode == Mode.VISUAL_BLOCK:
                    # Block change: like block insert, the typed cure replays
                    # into every other selected row on Esc.
                    _r1, _r2, _c1, _c2 = block_bounds(anchor, cursor)
                    block_ins = {'rows': list(range(_r1 + 1, _r2 + 1)),
                                 'col': _c1, 'buf': ''}
                if op != 'y':                  # visual yank is not a change either
                    player.last_change = {'type': 'visual_op', 'op': op}
                key_buf = ''
                if not edit_mode and player.mode == Mode.NORMAL:
                    _content_ticks()   # the strike opens its gate THIS turn (the
                    message = _pool_msg() or message   # insert-Esc rule; c ticks on its own Esc)
                _render(message)
                continue
            key_buf += raw
            # Text object: i/a (+ optional count) + object char selects the span
            # (viw, vaw, vi(, va", …).  In visual mode i/a are object prefixes.
            vt = parse_visual_textobj(key_buf)
            if vt == 'pending':
                _render(message)
                continue
            if vt is not None:
                _, textobj, tcount, tcg = vt
                key_buf = ''
                if not (textobj in player.known_commands or 'admin' in player.known_commands):
                    _push("You haven't learned that text object yet.")
                    message = _pool_msg(); msg_ttl = _MSG_ROTATE_TTL
                elif not edit_mode and budget.remaining <= 0:
                    _push('Out of budget!  (Esc, then u to undo)')
                    message = _pool_msg(); msg_ttl = _MSG_ROTATE_TTL
                else:
                    tobj = resolve_text_object(textobj, room, player)
                    if tobj is None:
                        _push('No text object here.')
                        message = _pool_msg(); msg_ttl = _MSG_ROTATE_TTL
                    else:
                        player.visual_anchor = (tobj.start_row, tobj.start_col)
                        player.row, player.col = tobj.end_row, tobj.end_col
                        if not edit_mode:
                            budget.spend(2 + _count_prefix_cost(tcount, tcg))
                _render(message)
                continue
            # Otherwise: a motion that extends the selection (costs same as normal mode)
            v_action, key_buf = parse(key_buf, Mode.NORMAL)
            if v_action is not None and v_action.get('type') == 'motion':
                if not edit_mode and budget.remaining <= 0:
                    _push('Out of budget!  (Esc, then u to undo)')
                    message = _pool_msg(); msg_ttl = _MSG_ROTATE_TTL
                else:
                    v_count = v_action.get('count', 1)
                    v_motion = v_action['motion']
                    moved = apply_motion(player, v_motion, v_count, room, v_action.get('target'),
                                         count_given=v_action.get('count_given', True),
                                         game_h=term.height - 8)
                    if moved and not edit_mode:
                        budget.spend(_keystroke_cost(v_count, v_motion, v_action.get('count_given', False)))
            elif v_action is not None:
                key_buf = ''                               # ignore non-motion keys in visual
            _render(message)
            continue

        # ── Normal mode ───────────────────────────────────────────────────────
        if key.name == 'KEY_ESCAPE':
            _apply_esc(player)
            key_buf = ''
            _render(message)
            continue

        if (key.name == 'KEY_ENTER' or str(key) in ('\n', '\r')) and not key_buf:
            # NORMAL-mode Enter ≡ + (Vim-true): one line down to the first
            # non-blank. Gated with the line-step lesson token.
            _enter_action = {'type': 'motion', 'motion': '+', 'count': 1}
            if not edit_mode and not _action_allowed(_enter_action, player.known_commands):
                _blocked(_enter_action)
                continue
            if not edit_mode and budget.remaining <= 0:
                _push('Out of budget!  (u to undo)')
                _render(message)
                continue
            _ent_pre = (player.row, player.col, budget.spent,
                        cmd_start_ans[0], cmd_start_ans[1])
            if apply_motion(player, '+', 1, room, None, game_h=term.height - 8):
                if not edit_mode:
                    budget.spend(1)
                    undo_stack.append(_ent_pre)
                    redo_stack.clear()
            _render(message)
            continue

        raw     = str(key) if not key.is_sequence else ''
        key_buf += raw
        action, key_buf = parse(key_buf, player.mode)

        if action is None:
            _render(message)
            continue

        # Dead players may only enter command mode to type :e
        if player.is_dead and not (action['type'] == 'enter_mode'
                                   and action.get('mode') == 'command'):
            _render(message)
            continue

        # Out of budget: the path is spent.  No budget-costing action may proceed —
        # only undo/redo (to recover) or :command (to quit / :edit).
        if not edit_mode and budget.remaining <= 0 and _budget_exhausted_blocks(action):
            _push('Out of budget!  (u to undo)')
            message = _pool_msg(); msg_ttl = _MSG_ROTATE_TTL
            _render(message)
            continue

        cur_combat_target = room.entity_at(player.row, player.col)
        if not (cur_combat_target and cur_combat_target.max_hp > 0):
            cur_combat_target = None

        # New turn: clear rotation pool and attack flash
        msg_pool.clear()
        msg_idx = 0
        attack_flash_sym = ''
        attack_flash_pos = (0, 0)
        attack_flash_on  = True
        attack_flash_ttl = 0

        prev_pos = (player.row, player.col, budget.spent,
                    cmd_start_ans[0], cmd_start_ans[1])
        # Baselines for the centralised '.'-cost + change re-cost accounting below.
        _spent_before = budget.spent
        _lc_before    = player.last_change
        _undo_len0    = len(undo_stack)
        _dot_active   = False
        _dot_cost     = 0
        prev_adjacent_ids = {
            id(e) for e in room.entities
            if e.alive and e.max_hp
            and _manhattan(player.row, player.col, e.row, e.col) <= _ATTACK_RADIUS
        }
        count    = action.get('count', 1)

        # . — repeat last change
        if action['type'] == 'repeat':
            if not _action_allowed(action, player.known_commands) and _blocked(action):
                continue
            if not player.last_change:
                _push('Nothing to repeat.')
                message = _pool_msg(); msg_ttl = _MSG_ROTATE_TTL
                _render(message)
                continue
            repeat_count = action.get('count', 1)
            repeat_cg    = action.get('count_given', False)   # was a count typed on the '.'?
            action = dict(player.last_change)
            if repeat_count != 1:
                action['count'] = repeat_count
            count = action.get('count', 1)
            # '.' is ONE keystroke: it should cost its own keypress(es), not the change's
            # full price — unless its change was undone, in which case it re-pays in full
            # (pending_recost_c). The re-dispatched handler charges full below; the
            # centralised settle (before the combat block) refunds down to the dot's cost.
            _dot_active = True
            _dot_cost   = player.pending_recost_c or _keystroke_cost(repeat_count, '', repeat_cg)
            player.pending_recost_c = 0

        if action['type'] == 'motion':
            motion = action['motion']
            target = action.get('target')

            if not edit_mode and not _action_allowed(action, player.known_commands) and _blocked(action):
                continue

            jump_from = (player.row, player.col)
            moved = apply_motion(player, motion, count, room, target,
                                 count_given=action.get('count_given', True),
                                 game_h=term.height - 8)
            if moved:
                if motion in _JUMP_MOTIONS:
                    _record_jump(player, jump_from)
                if not edit_mode:
                    # Find-register accounting (anti-exploit): an f/F/t/T pays the full
                    # find cost and tags its undo entry; undoing that find arms
                    # pending_recost_f so the next ;/, re-pays the full cost instead of
                    # inheriting the refunded find for 1 key. A ;/, that settles that
                    # re-cost is tagged in turn, so undoing IT re-arms.
                    _cg = action.get('count_given', False)
                    if motion in ('f', 'F', 't', 'T'):
                        cost, player.pending_recost_f, mark = _keystroke_cost(count, motion, _cg), 0, 'f'
                    elif motion in (';', ',') and player.pending_recost_f:
                        cost, player.pending_recost_f, mark = player.pending_recost_f, 0, 'f'
                    else:
                        cost, mark = _keystroke_cost(count, motion, _cg), None
                    budget.spend(cost)
                    undo_stack.append(prev_pos + ((mark, cost),) if mark else prev_pos)
                    redo_stack.clear()

                if count > 1 and not count_tutorial_shown and not edit_mode and level == 'counting_crypts':
                    count_tutorial_shown = True
                    _push(f'{count}{motion} moved {count} steps in 2 keystrokes — count is efficient!')

                # Void rune: fall animation, lose heart, respawn (skip in edit mode)
                ru = room.char_run_at(player.row, player.col)
                if not edit_mode and ru and ru.kind == 'void':
                    _render(message)
                    _void_fall_animation(term, *_void_screen_xy(term, room, player,
                                                                player.row, player.col))
                    player.take_damage(2)  # 1 full heart
                    player.row, player.col = prev_pos[0], prev_pos[1]
                    if player.is_dead:
                        message = '** GAME OVER ** Type  :e  to re-load the dungeon.'
                        msg_ttl = 2
                    else:
                        message = f'You fell into the void!  {_hearts_note(player.hp)}'
                        msg_ttl = 25
                    _render(message)
                    continue

                # Water: drown if landed on water cell (e.g. via $, 0, ^)
                if not edit_mode and room.cells[player.row][player.col] == CellType.WATER:
                    _render(message)
                    _drown_animation(term, *_void_screen_xy(term, room, player,
                                                            player.row, player.col))
                    player.take_damage(2)  # 1 full heart
                    player.row, player.col = prev_pos[0], prev_pos[1]
                    if player.is_dead:
                        message = '** GAME OVER ** Type  :e  to re-load the dungeon.'
                        msg_ttl = 2
                    else:
                        message = f'You drowned!  {_hearts_note(player.hp)}'
                        msg_ttl = 25
                    _render(message)
                    continue

                # Dynamite: explode if stepped on
                ent = room.entity_at(player.row, player.col)
                if not edit_mode and ent and ent.kind == 'dynamite':
                    if undo_stack and isinstance(undo_stack[-1], tuple):
                        _dyn_t = undo_stack.pop()
                        pr, pc, ps = _dyn_t[0], _dyn_t[1], _dyn_t[2]
                        undo_stack.append(_snapshot(room, player, budget,
                                                    row=pr, col=pc, spent=ps,
                                                    ans=cmd_start_ans))
                    message, msg_ttl = _detonate(ent, message)
                    ent = None  # consumed; fall through to normal render

                # Seal door: wall forms the moment the player steps off the threshold
                if seal_door_col >= 0 and not edit_mode and player.col != seal_door_col:
                    room.cells[seal_door_row][seal_door_col] = CellType.WALL
                    seal_door_col = -1
                    undo_stack.clear()
                    redo_stack.clear()
                    _push('The door seals shut behind you — there is no going back.')

                # The Archivist's Library: in the hall (catalogue), approaching the
                # pacing Archivist drives his dialogue / the reckoning. Not while
                # reading a manuscript, and not once the level is decided.
                if (level == 'archivists_library'
                        and getattr(room, 'lib_view', 'catalog') != 'leaf'
                        and not getattr(room, 'lib_done', None)
                        and not getattr(room, 'lib_hostile', False)):
                    _arch = next((e for e in room.entities
                                  if e.kind == 'archivist' and e.alive), None)
                    _near = _arch is not None and abs(player.col - _arch.col) <= 2
                    # (Win/lose is decided in _lib_file after the fourth :w.)
                    if not player.wrap:                       # pre-wrap panic
                        if _near and not room._lib_arch_flag:
                            room._lib_arch_flag = True
                            _push('MY LIBRARY! All on ONE LINE!')
                            _push('A whole catalogue, spilled end to end — put it right!')
                        elif not _near:
                            room._lib_arch_flag = False
                    else:                                     # post-wrap step-wise brief
                        _lib_brief_step(_near)

                # Win / exit check
                if ent is None:
                    ent = room.entity_at(player.row, player.col)
                if _room_door():
                    # The door is the POSITION, not the marker: a transit room
                    # carries no exit entity at all (the format synthesises one
                    # only on the last room), so standing on its exit_pos must
                    # advance on its own. If a door entity does sit here (an
                    # older file, or an author who placed one), it is eaten —
                    # that exit was a door, not the way out.
                    if ent and ent.kind == 'exit':
                        ent = None
                elif ent and ent.kind == 'exit' and not won:
                    won = True
                    _render('')
                    iw  = _iw(term)
                    if level_type(level) == 'boss':
                        _starfield_victory(term, iw, dungeon, player, level)
                        message = 'VIM AD ASTRA — the way upward opens. Type :wq to return to the overworld.'
                    elif (room.par or 0) > 0 and budget.spent <= room.par:
                        _fireworks_animation(term, iw, dungeon, player)
                        message = 'Par-perfect — not a stroke wasted!  Type :wq to return to the overworld.'
                    else:
                        _win_animation(term, iw, dungeon, player)
                        message = 'Dungeon cleared!  Type :wq to return to the overworld.'
                    msg_ttl = 200

        elif action['type'] == 'goto_insert':
            # gi — return to where INSERT was last left, and resume there.
            if not edit_mode and not _action_allowed(action, player.known_commands) and _blocked(action):
                continue
            li = getattr(player, 'last_insert', None)
            if li is None or li[0] >= room.rows or not room.is_passable(*li):
                _push('No previous insertion.')
            else:
                undo_stack.append(_snapshot(room, player, budget, ans=cmd_start_ans))
                redo_stack.clear()
                player.row, player.col = li
                begin_insert(room, player, 'i', 1)
                player.mode = Mode.INSERT
                insert_typed = ''
                budget.spend(2)                      # 'g' + 'i'
                player.last_change = action

        elif action['type'] == 'enter_mode':
            m = action['mode']
            if m == 'command':
                # Admin karaoke: track a `:`-command against the tape ONLY when the tape
                # actually expects a ':' here — so the player's own :wq / :q! finish (after
                # the tape is consumed) never diverges it, exactly as before.  cmd_start_ans
                # snapshots the pre-`:` tape state so a :s/:g undo rewinds the playhead.
                room._cmd_karaoke = False
                if player_name == 'admin' and room.answer and not room.answer_diverged:
                    cmd_start_ans = (room.answer_pos, room.answer_diverged)
                    _ap = room.answer.replace(' ', '')
                    if room.answer_pos < len(_ap) and _ap[room.answer_pos] == ':':
                        room._cmd_karaoke = True
                        room.answer_pos += 1                # consume the ':'
                player.mode     = Mode.COMMAND
                player.cmd_line = ''
                player.cmd_cursor = 0
            elif m == 'insert':
                if edit_mode:
                    player.mode = Mode.INSERT          # admin map-editing placement
                elif 'insert' in player.known_commands or 'admin' in player.known_commands:
                    undo_stack.append(_snapshot(room, player, budget, ans=cmd_start_ans))
                    redo_stack.clear()
                    begin_insert(room, player, action.get('variant', 'i'), count)
                    player.mode = Mode.INSERT
                    insert_typed = ''
                    budget.spend(1)
                    player.last_change = action
                else:
                    _push('INSERT mode not learned yet.')
            elif m == 'replace':
                if edit_mode or 'R' in player.known_commands or 'admin' in player.known_commands:
                    if not edit_mode:
                        undo_stack.append(_snapshot(room, player, budget, ans=cmd_start_ans))
                        redo_stack.clear()
                        budget.spend(1)
                    else:
                        ed_undo.append(_ed_snapshot(room, player))
                        ed_redo.clear()
                    replace_stack = []
                    player.mode = Mode.REPLACE
                    player.last_change = action
                else:
                    _push('REPLACE mode not learned yet.')
            elif m == 'search':
                if '/' in player.known_commands or 'admin' in player.known_commands:
                    player.mode = Mode.SEARCH
                    player.cmd_line = ''
                    player.cmd_cursor = 0
                    player.search_forward = action.get('forward', True)
                    # Karaoke: the '/' or '?' was already matched by the NORMAL tracker
                    # (it isn't excluded like ':'); now track the pattern + Enter that
                    # follow in SEARCH mode (which the top-of-loop tracker never sees).
                    room._search_karaoke = (player_name == 'admin' and bool(room.answer)
                                            and not room.answer_diverged)
                else:
                    _push('Search not learned yet.')
            elif m in ('visual', 'visual_line', 'visual_block'):
                # Per-token gate (the insert-variant rule): v at the Sight
                # Sanctum; V / <C-v> are the Selection Halls' own tokens.
                # gv restores whichever mode was last used, so it gates on the
                # base 'visual' token.
                _vtok = 'visual' if action.get('reselect') else m
                if _vtok in player.known_commands or 'admin' in player.known_commands:
                    if action.get('reselect'):                # gv — restore last selection
                        if player.last_visual_anchor is not None:
                            player.mode = player.last_visual_mode or Mode.VISUAL
                            player.visual_anchor = player.last_visual_anchor
                            player.row, player.col = player.last_visual_cursor
                        else:
                            _push('No previous visual selection.')
                    else:
                        player.mode = {'visual': Mode.VISUAL,
                                       'visual_line': Mode.VISUAL_LINE,
                                       'visual_block': Mode.VISUAL_BLOCK}[m]
                        player.visual_anchor = (player.row, player.col)
                        if not edit_mode:
                            player.visual_start_spent = budget.spent
                            budget.spend(1)
                else:
                    _push('VISUAL mode not learned yet.')

        elif action['type'] == 'jump':
            if not edit_mode and not _action_allowed(action, player.known_commands) and _blocked(action):
                continue
            dest = _jump_back(player) if action['dir'] == 'back' else _jump_forward(player)
            if dest is not None:
                player.row, player.col = dest
                budget.spend(1)
                undo_stack.append(prev_pos)
                redo_stack.clear()
            else:
                _push('Jump list: nothing that way.')

        elif action['type'] == 'mark':
            if not edit_mode and not _action_allowed(action, player.known_commands) and _blocked(action):
                continue
            cmd, reg = action['cmd'], action['reg']
            if cmd == 'm':
                player.marks[reg] = (player.row, player.col)
                if not edit_mode:
                    budget.spend(2)
                _push(f"Mark '{reg}' set.")
            elif reg not in player.marks:
                _push(f"Mark '{reg}' not set.")
            else:
                mr, mc = player.marks[reg]
                if cmd == "'":                         # ' → first non-blank of the row
                    nb = _first_non_blank_col(room, mr) if 0 <= mr < room.rows else None
                    dest = (mr, nb) if nb is not None else None
                else:                                  # ` → exact position
                    dest = (mr, mc)
                if dest is None or not room.is_passable(dest[0], dest[1]):
                    _push(f"Mark '{reg}': can't land there.")
                else:
                    _record_jump(player, (player.row, player.col))
                    player.row, player.col = dest
                    if not edit_mode:
                        budget.spend(2)
                        undo_stack.append(prev_pos)
                        redo_stack.clear()

        elif action['type'] == 'macro_record':
            if not edit_mode and not _action_allowed(action, player.known_commands) and _blocked(action):
                continue
            recording_reg = action['reg']
            macro_buf = ''
            _push(f'recording @{recording_reg}')

        elif action['type'] == 'seal_exit':
            # ZZ / ZQ — the sealed departure (relic scroll): replay the exact
            # :wq / :q! ritual through the key queue, so the win/quit logic
            # lives in one place. Free, like the : commands it abbreviates.
            if not edit_mode and not _action_allowed(action, player.known_commands) and _blocked(action):
                continue
            macro_pending.extendleft(reversed(
                ':q!\r' if action.get('discard') else ':wq\r'))

        elif action['type'] == 'macro_play':
            if not edit_mode and not _action_allowed(action, player.known_commands) and _blocked(action):
                continue
            reg = macro_last if action['reg'] == '@' else action['reg']
            # Any register replays — including one you merely YANKED. Vim's `@`
            # runs a register's contents as keystrokes, whatever put them there.
            keys = _reg_keys(_reg_read(player, reg)) if reg else None
            if keys and reg == ':':
                # `@:` re-runs the last Ex command. The `:` register holds the
                # bare text (that is what vim shows you), so the colon and the
                # <CR> that make it a command again are added here rather than
                # baked into the stored value.
                keys = ':' + keys + '\r'
            if not keys:
                _push('No macro to play.')
            else:
                macro_last = reg
                add = keys * count
                if len(macro_pending) + len(add) > _MACRO_MAX:
                    _push('Macro too long (recursion?).')
                else:
                    macro_pending.extendleft(reversed(add))   # play next, in order
                    budget.spend(2 + _count_prefix_cost(count, action.get('count_given', False)))

        elif action['type'] in ('search_repeat', 'search_word'):
            if not edit_mode and not _action_allowed(action, player.known_commands) and _blocked(action):
                continue
            if action['type'] == 'search_word':
                word = _word_under_cursor(room, player)
                if word is None:
                    _push('No character under cursor.')
                    pattern, fwd = None, True
                else:
                    fwd = action.get('forward', True)
                    if action.get('literal') or not word.isalnum():
                        # g* / g# — the word literally, NO boundaries: the
                        # substring form (\V = every char literal). Also the
                        # form for punctuation 'words', which have no
                        # boundary to speak of.
                        pattern = '\\V' + word
                    else:
                        # * / # — Vim-true whole-word search: \<word\>.
                        pattern = '\\<' + word + '\\>'
                    player.last_search = (pattern, fwd)
            else:                                  # n / N
                if not player.last_search:
                    _push('No previous search.')
                    pattern, fwd = None, True
                else:
                    pattern, base_fwd = player.last_search
                    fwd = (not base_fwd) if action.get('reverse') else base_fwd
            if pattern:
                moved = False
                player.hl_suppressed = False            # n/N/*/# re-light matches
                search_from = (player.row, player.col)
                for _ in range(count):
                    dest = _search_next(room, player, pattern, fwd)
                    if dest is None:
                        break
                    player.row, player.col = dest
                    moved = True
                if moved:
                    _record_jump(player, search_from)
                    # Same anti-exploit accounting as f/;/, (see the motion branch): * / #
                    # establish the n/N register and tag their entry; an n/N that settles a
                    # re-cost (after the search was undone) re-pays the full search cost.
                    _scg = action.get('count_given', False)
                    if action['type'] == 'search_word':
                        # g* / g# are two physical keys; * / # are one.
                        cost = (_keystroke_cost(count, '', _scg)
                                + (1 if action.get('literal') else 0))
                        player.pending_recost_s, smark = 0, True
                    elif player.pending_recost_s:
                        cost, player.pending_recost_s, smark = player.pending_recost_s, 0, True
                    else:
                        cost, smark = _keystroke_cost(count, '', _scg), False
                    budget.spend(cost)
                    undo_stack.append(prev_pos + (('s', cost),) if smark else prev_pos)
                    redo_stack.clear()
                else:
                    _push(f'Pattern not found: {pattern}')

        elif action['type'] == 'undo':
            if edit_mode:
                done = _ed_step_n(ed_undo, ed_redo, count, room, player)
                _push(f'{done} change(s) undone.' if done else 'Nothing to undo.')
            else:
                held = _held_key(player)
                spot = (player.row, player.col)     # where the key slips, pre-undo
                done = sum(_pop_history_step(undo_stack, redo_stack, room, player, budget)
                           for _ in range(count))
                # Keys are slippery: undoing while carrying one drops it where you
                # stood — the undo STILL happens (you snap back to your previous
                # position), but you must walk back for the key. A precision tax.
                # Drop AFTER the undo so the entity-restore can't wipe the key.
                if held is not None and done and _drop_key(room, spot[0], spot[1],
                                                           held.get('tag', '')):
                    player.registers['"'] = None
                    _push('The key clatters to the floor! 🗝')
                else:
                    _push(f'{done} change(s) undone.' if done else 'Nothing to undo.')

        elif action['type'] == 'redo':
            # <C-r> is relic-gated ('redo' scroll); u stays the always-on rope.
            if not edit_mode and not _action_allowed(action, player.known_commands) \
                    and _blocked(action):
                continue
            if edit_mode:
                done = _ed_step_n(ed_redo, ed_undo, count, room, player)
            else:
                done = sum(_pop_history_step(redo_stack, undo_stack, room, player, budget, is_redo=True)
                           for _ in range(count))
            _push(f'{done} change(s) redone.' if done else 'Already at newest change')

        elif action['type'] == 'interact':
            if action.get('before'):
                # X — delete BEFORE the cursor (Vim-true: the strike lands one
                # west; the pull leaves the cursor on its own character, one
                # column left). Gated on its own 'X' token (the Y/D/C rule).
                if not edit_mode and not _action_allowed(action, player.known_commands) \
                        and _blocked(action):
                    continue
                if player.col == 0 or not room.is_passable(player.row, player.col - 1):
                    _push('Nothing before the cursor.')
                    _render(message)
                    continue
                player.col = max(0, player.col - count)   # {n}X: the n chars west;
                # the delete-count runs east from here = exactly those chars
            if edit_mode:
                ed_undo.append(_ed_snapshot(room, player))
                ed_redo.clear()
                cut_items = []
                for _ci in range(count):
                    item = _ed_cut(room, player.row, player.col + _ci)
                    if item:
                        cut_items.append(item)
                if cut_items:
                    player.edit_clip = cut_items
                    if len(cut_items) > 1:
                        _push(f'Cut {len(cut_items)} characters')
                    else:
                        _push(f'Cut 1: {_clip_desc(cut_items[0])}')
                    player.last_change = action
                else:
                    ed_undo.pop()
                    _push('Nothing to cut here.')
            elif (level == 'archivists_library' and not getattr(room, 'lib_done', None)
                  and not getattr(room, 'lib_hostile', False)
                  and any((lambda ru: ru and ru.symbols[player.col + _i - ru.col] != ' ')(
                              room.char_run_at(player.row, player.col + _i))
                          for _i in range(count))):
                # x-ing anything but whitespace defaces the library — he turns on you.
                _lib_strike('"You DARE deface my library, VANDAL?!"')
                _render(_pool_msg())
                continue
            else:
                interacted = False
                cur = room.entity_at(player.row, player.col)
                if cur and cur.kind in ('chest_random', 'chest_key', 'chest_scroll'):
                    undo_stack.append(_snapshot(room, player, budget, ans=cmd_start_ans))
                    redo_stack.clear()
                    item = _chest_loot(cur.kind)
                    _chest_sid = cur.scroll_id            # a chest may name its own scroll
                    room.kill_entity(cur)
                    budget.spend(1)
                    if item == 'key':
                        # The chest's tag rides onto the key. A `chest_key` with
                        # tag='red' has to yield a RED key or the pairing an author
                        # set up on the chest quietly dissolves at the moment of
                        # looting, and the red door it was cut for never opens.
                        _reg_write(player, '"',
                                   entity_clip(Entity(kind='floor_key', row=cur.row,
                                                      col=cur.col, tag=cur.tag)),
                                   is_delete=True)
                        _push('You found a key!')
                    elif item == 'heart':
                        player.heal(2)
                        _push('You found a heart! HP restored.')
                    else:
                        _push('You found a scroll!')
                    interacted = True
                    _drop = _SCROLL_DROPS.get(level)
                    if item != 'scroll':
                        # A chest holds ONE thing: only a scroll loot opens
                        # the scroll machinery — a key chest gives a key,
                        # a heart chest a heart, full stop.
                        pass
                    elif _chest_sid:
                        # This chest names a specific scroll (e.g. the Waypoint
                        # nook → the Numbered Ledger). Grant it and show it via
                        # the standard catalog renderer.
                        extras = progress.get('extras', [])
                        if _chest_sid not in extras:
                            progress['extras'] = extras + [_chest_sid]
                        if _chest_sid not in player.known_commands:
                            player.known_commands = player.known_commands + [_chest_sid]
                        _render(_pool_msg())
                        _show_catalog_scroll(term, _iw(term), term.height - 8, _chest_sid,
                                             _known_from_progress(progress))
                    elif _drop is not None:
                        _sid, _txt_title, _txt_body = _drop
                        # Discovery is recorded by extras membership, NOT by
                        # known_commands — admin has some ids (e.g. 'register')
                        # pre-injected, so gating on known_commands would skip
                        # the discovery record entirely.
                        extras = progress.get('extras', [])
                        if _sid not in extras:
                            progress['extras'] = extras + [_sid]
                            if _txt_body is not None:
                                SM.save_scroll_text(_txt_title, _txt_body)
                        if _sid not in player.known_commands:
                            player.known_commands = player.known_commands + [_sid]
                        _render(_pool_msg())
                        # Gate the scroll's smudged lines on what the player has
                        # actually learned (their whole progress), not this level's
                        # frozen command set — otherwise replaying an early boss
                        # re-smudges commands learned in later levels.
                        _show_scroll_by_id(term, _iw(term), term.height - 8, _sid,
                                           _known_from_progress(progress))
                    else:
                        # No scroll assigned to this level: pull a random, not-yet-
                        # discovered "safe" relic scroll from the library.
                        _wid = _pick_relic_scroll(progress.get('extras', []),
                                                  known=_known_from_progress(progress))
                        if _wid is not None:
                            progress['extras'] = progress.get('extras', []) + [_wid]
                            if _wid not in player.known_commands:
                                player.known_commands = player.known_commands + [_wid]
                            _render(_pool_msg())
                            _show_catalog_scroll(term, _iw(term), term.height - 8, _wid,
                                                 _known_from_progress(progress))
                        else:
                            _push('The scroll case is empty — you hold every relic scroll.')
                elif cur and cur.kind == 'door':
                    undo_stack.append(_snapshot(room, player, budget, ans=cmd_start_ans))
                    redo_stack.clear()
                    _kill_door_group(room, cur.row, cur.col)
                    _reveal_from(room, player.row, player.col)
                    budget.spend(1)
                    _push('Door opened.')
                    interacted = True
                elif cur and cur.kind == 'seal_door':
                    undo_stack.append(_snapshot(room, player, budget, ans=cmd_start_ans))
                    redo_stack.clear()
                    seal_door_col = cur.col
                    seal_door_row = cur.row
                    room.remove_entity(cur)
                    _reveal_from(room, player.row, player.col)
                    budget.spend(1)
                    _push('The door opens.')
                    interacted = True
                elif cur and cur.kind == 'floor_key':
                    undo_stack.append(_snapshot(room, player, budget, ans=cmd_start_ans))
                    redo_stack.clear()
                    room.kill_entity(cur)
                    _reg_write(player, '"', entity_clip(cur), is_delete=True)
                    budget.spend(1)
                    _push('Key picked up — use p to unlock a door.')
                    interacted = True
                elif cur and cur.kind == 'hat':
                    # The Warden's hat is looted like any item — x it (or dl).
                    undo_stack.append(_snapshot(room, player, budget, ans=cmd_start_ans))
                    redo_stack.clear()
                    room.kill_entity(cur); room.rebuild_indexes()
                    player.has_hat = True
                    budget.spend(1)
                    _push("You take up the Warden's hat. (Type  :set hat  to wear "
                          "it — every command, in any hall.)")
                    interacted = True
                elif cur and cur.kind == 'ally':
                    _push('The dog pets you back.')      # your own hound — no harm
                    interacted = True
                elif cur and cur.kind == 'critter' and not cur.swole:
                    _push('The cat purrs.')              # a friendly cat — no harm
                    interacted = True
                elif cur and cur.kind == 'horse':        # the wizard's horse — post-game
                    _hn = progress.get('horse_name')
                    if _hn:
                        _push(f"{_hn} leans into your hand. He'll carry you home "
                              "whenever you're ready.")
                    else:
                        # Not yet named (you waved him off): x re-opens the naming
                        # popup so you can take him up when you're ready.
                        _nm = _prompt_horse_name(term, _iw(term), term.height - 8)
                        if _nm:
                            progress['horse_name'] = cur.tag = _nm
                            progress['horse_met'] = True
                            _save_progress(progress, player_name)
                            _push(f'{_nm} lifts his head. He stays at your heel now.')
                        else:
                            _push("The horse waits, patient. Name him when you're ready.")
                    interacted = True
                elif cur and (cur.kind in ('goblin', 'warden', 'wanderer', 'elf')
                              or (cur.kind == 'critter' and cur.swole)
                              or (cur.kind == 'archivist' and getattr(room, 'lib_hostile', False))):
                    undo_stack.append(_snapshot(room, player, budget, ans=cmd_start_ans))
                    redo_stack.clear()
                    cur.hp -= 1
                    budget.spend(1)
                    interacted = True
                    # The Surveyor uses its own two-phase visual/teleport AI
                    # (wired separately); it never leaps-and-summons like the Keep.
                    # The Manifold re-manifests via its own ward machine — the
                    # tick moves him to the next podium, never a random leap.
                    # The Grandmaster does not flinch: he stands his ground
                    # and trades blows — a deterministic duel, no leap.
                    if cur.kind == 'warden' and cur.hp > 0 \
                            and cur.tag not in ('surveyor', 'verse',
                                                'manifold', 'stamp',
                                                'scrivener', 'grandmaster',
                                                'eternal', 'eternal_boss'):
                        move_msg = _do_warden_move(room, cur, player)
                        if move_msg:
                            _push(move_msg)
                        if cur.tag == 'pathfinder':
                            # A real swarm, right where you stand — so `/W x` spam is punished.
                            n = 0
                            for (dr, dc) in ((0, 2), (0, -2), (2, 0), (-2, 0), (1, 2), (-1, -2)):
                                if _spawn_goblin(room, player.row + dr, player.col + dc,
                                                 summoner_uid=cur.uid):
                                    n += 1
                                if n >= 3:
                                    break
                            _push('The Warden howls — minions swarm in around you!')
                        else:
                            _side = random.choice((-1, 1))
                            _spawn_goblin(room, cur.row, cur.col + _side * 3, summoner_uid=cur.uid)
                            _push('The Warden summoned a goblin minion!')
                        cur.summon_timer = _WARDEN_SUMMON_INTERVAL
                    elif cur.kind == 'warden' and cur.hp > 0 and cur.tag == 'surveyor':
                        if cur.hp == 3:                      # just entered Phase 2 (2 HP spent)
                            _surveyor_regen()                # the eaten verse regrows
                            _push('The sentences regrow — his sight will frame you in blocks!')
                        _surveyor_teleport(cur)              # leap away (60% into a parenthetical)
                        room.surveyor_threat = {'step': 'recover'}   # a tick to regain focus before re-entering visual mode
                        _push('The Warden leaps — you broke his focus!')
                    elif cur.kind == 'warden' and cur.hp > 0 and cur.tag == 'verse':
                        player.take_damage(2)                # 2 half-hearts (1 full heart) — he trades blows hard on every exchange
                        attack_flash_pos = (cur.row, cur.col)
                        attack_flash_sym = '✕'
                        attack_flash_on  = True
                        attack_flash_ttl = _ATTACK_FLASH_TTL
                        if player.is_dead:
                            message = '** GAME OVER ** Type  :e  to re-load the dungeon.'
                            msg_ttl = 2
                    if cur.hp <= 0:
                        if (cur.kind == 'warden' and cur.tag == 'pathfinder'
                                and not getattr(room, 'warden_fled', False)):
                            # Act 1 over: shields fall, the Warden flees the arena.
                            room.warden_fled = True
                            room.mega = None                 # the floor-cuts stop
                            room.kill_entity(cur)
                            _remove_warden_shields(room)
                            _push('His shields shatter — the Warden retreated into the '
                                  'wardenverse!  Try to follow him:  :e wardenverse')
                        else:
                            # An elf spills its coins when felled; every other egg
                            # creature just vanishes (as goblins always have).
                            if cur.kind == 'elf':
                                room.add_entity(Entity(kind='gold', row=cur.row,
                                                       col=cur.col, tag='gold'))
                                _push('The elf drops its coins as it falls.')
                                _et = getattr(room, '_elf_trade', None)
                                if _et and _et.get('elf_id') == id(cur):
                                    room._elf_trade = None   # its offer dies with it
                            room.kill_entity(cur)
                            _reg_write(player, '"', entity_clip(cur), is_delete=True)
                            if cur.kind == 'warden' and cur.tag == 'verse':
                                # The wardenverse collapses — fling the player back to the arena.
                                arena = dungeon.rooms[0]
                                arena.verse_collapsed = True
                                dungeon.current_room = 0
                                room = dungeon.room
                                player.row, player.col = (12, 60)
                                player.wrap = False
                                # Unmask all remaining echoes — the Warden's illusions fail
                                for e in arena.entities:
                                    if e.kind == 'goblin' and e.tag == 'echo' and e.alive:
                                        e.tag = ''       # no longer disguised as 'W'
                                        e.hp = 1         # revealed goblins have 1 HP
                                        e.max_hp = 1
                                undo_stack.clear()           # verse snapshots can't restore the arena
                                redo_stack.clear()
                                any_water = _room_has_water()
                                msg_pool.clear()
                                if any(e.alive and e.kind == 'goblin' for e in room.entities):
                                    # minions remain — the key drops when the last one falls (per-turn check)
                                    _push('You cut him down and the wardenverse collapses — you are '
                                          'flung back into the arena!  The Warden\'s illusions fail: '
                                          'his echoes stand revealed as goblins.')
                                else:
                                    # already clear — the collapse itself shakes the key loose
                                    room.key_dropped = True
                                    _drop_key(room, 12, 40)
                                    _push('You cut him down and the wardenverse collapses — its '
                                          'fall shakes a key loose onto the arena floor.  🗝')
                                message = _pool_msg(); msg_ttl = _MSG_ROTATE_TTL
                            else:
                                if cur.kind == 'warden':
                                    _remove_warden_shields(room)
                                    room.surveyor_threat = None  # clear any lingering telegraph
                                _push(_on_kill(cur, player, room, level) or 'Enemy defeated!')
                    else:
                        _push(f'Hit! ({cur.hp}/{cur.max_hp} HP)')
                elif cur and cur.kind == 'shield':
                    undo_stack.append(_snapshot(room, player, budget, ans=cmd_start_ans))
                    redo_stack.clear()
                    room.kill_entity(cur)
                    _reg_write(player, '"', entity_clip(cur), is_delete=True)
                    budget.spend(1)
                    _push('Shield destroyed!')
                    interacted = True
                elif cur and cur.kind == 'heart_container':
                    old_max_hp = player.max_hp
                    heart_pos  = [level, cur.row, cur.col]
                    player.max_hp += 2
                    room.kill_entity(cur)
                    budget.spend(1)
                    # The upgrade is an undo BARRIER (like the seal door): snapshots
                    # don't carry max_hp, so undoing past the pickup would revive the
                    # heart while keeping the +2 — re-grab it and stack hearts forever.
                    undo_stack.clear()
                    redo_stack.clear()
                    # The +HP is yours for this run, but the upgrade only PERSISTS when
                    # the player writes (:w / :wq) — quitting with :q discards it, like
                    # any unsaved change.  Stage it here; commit at write time.
                    if heart_pos not in pending_hearts:
                        pending_hearts.append(heart_pos)
                    _heart_container_animation(term, dungeon, player, budget, old_max_hp, message)
                    player.hp = player.max_hp
                    _push('Max HP increased!  ♥  (:w to keep it)')
                    interacted = True
                if interacted:
                    player.last_change = action
                if not interacted:
                    # Cutting a dynamite charge sets it off — a deliberate break
                    # from vim-faithfulness: it detonates instead of cutting to
                    # the register. (A count-cut can reach one a cell or more away.)
                    _dyn = None
                    for _ci in range(count):
                        _e2 = room.entity_at(player.row, player.col + _ci)
                        if _e2 and _e2.kind == 'dynamite':
                            _dyn = _e2
                            break
                    if _dyn is not None:
                        budget.spend(1)
                        message, msg_ttl = _detonate(_dyn, message)
                        player.last_change = action
                        interacted = True

                if not interacted:
                    # Normal-mode x cuts TEXT (Vim's x) — char runs only. Walls,
                    # doors and creatures are NOT cuttable here: entities die by
                    # the combat/interact branches above and dynamite by its scan
                    # (a count-x once carved walls and deleted locked doors /
                    # goblins at range via the admin editor's _ed_cut — a cheese
                    # that bypassed keys, combat, and geometry on every level).
                    # Snapshot BEFORE the cut mutates — it removes the character on
                    # the spot, so a snapshot taken afterwards captures the
                    # already-cut state and 'u' would refund the keystroke without
                    # restoring the character (a free delete). Push it only if
                    # something was actually cut.
                    pre_cut   = _snapshot(room, player, budget, ans=cmd_start_ans)
                    cut_items = []
                    for _ci in range(count):
                        cut = _split_run_at(room, player.row, player.col + _ci)
                        if cut is not None:
                            cut_items.append({'type': 'rune', 'rune': cut})
                    if cut_items:
                        undo_stack.append(pre_cut)
                        redo_stack.clear()
                        _reg_write(player, '"',
                                   _clip_from_cut_chars(cut_items, player.col), is_delete=True)
                        if is_ledge(room, player.row):
                            close_gap(room, player.row, player.col, count)   # ledge: pull the tail left
                        # `x`=1; `{n}x` pays its count digits — the count-s
                        # law (a flat 1 would make {n}x undercut the quote
                        # objects and invert the Enclosure forcing).
                        budget.spend(_keystroke_cost(count, '',
                                                     action.get('count_given', False)))
                        if len(cut_items) > 1:
                            _push(f'Cut {len(cut_items)} characters')
                        else:
                            _push(f'Cut 1: {_clip_desc(cut_items[0])}')
                        player.last_change = action
                        seal_msg = _check_seal_broken(room)
                        if seal_msg:
                            _push(seal_msg)

        elif not edit_mode and action['type'] == 'substitute':
            if not _action_allowed(action, player.known_commands) and _blocked(action):
                continue
            undo_stack.append(_snapshot(room, player, budget, ans=cmd_start_ans))
            redo_stack.clear()
            begin_insert(room, player, 'S' if action.get('line') else 's', count)
            player.mode = Mode.INSERT
            insert_typed = ''
            budget.spend(_keystroke_cost(count, '', action.get('count_given', False)))   # `s`=1; `{n}s` / `1s` pay their digits
            player.last_change = action

        elif edit_mode and action['type'] == 'substitute':
            # `s` is vim's `s` again — cut what is here, then type. It used to
            # walk a ring of cell types instead, which is the one thing `s` does
            # not mean anywhere else in this game; `:paint` took that job, and
            # the key went back to the buffer where the author's fingers expect
            # it. `S` takes the whole line, as it does everywhere.
            ed_undo.append(_ed_snapshot(room, player))
            ed_redo.clear()
            if action.get('line'):
                _ed_clear_row(room, player.row)
                player.col = 0
            else:
                for _si in range(count):
                    _ed_cut(room, player.row, player.col + _si)
            player.mode = Mode.INSERT          # admin map-editing placement
            player.last_change = action

        elif not edit_mode and action['type'] == 'paste' and _action_allowed(action, player.known_commands):
            before = action.get('before', False)
            count  = action.get('count', 1)
            dc     = -1 if before else 1          # P → left, p → right
            target = room.entity_at(player.row, player.col + dc)
            clip   = _reg_read(player, action.get('register', '"'))
            clip_entities = [ed for rw in (clip['rows'] if clip else ())
                             for ed in rw.get('entities', ())]
            if target and target.kind == 'locked_door':
                # Unlock with a key held in the unnamed register. The register is
                # NOT consumed — p never empties " in Vim — so one key opens as
                # many doors as you paste on, until a later cut overwrites it.
                key_tmpl = next(
                    (ed['tmpl'] for ed in clip_entities
                     if ed['tmpl'].get('kind') == 'floor_key'
                     and (not target.tag or ed['tmpl'].get('tag', '') == target.tag)),
                    None,
                )
                if key_tmpl is not None:
                    _ktag = key_tmpl.get('tag', '')
                    _kclr = (C.key_gold_fg() if _ktag == 'gold' else
                             C.key_red_fg()  if _ktag == 'red'  else
                             C.key_blue_fg() if _ktag == 'blue' else None)
                    undo_stack.append(_snapshot(room, player, budget, ans=cmd_start_ans))
                    redo_stack.clear()
                    _render(_pool_msg())
                    _unlock_animation(term, room, player,
                                      target.row, target.col,
                                      _iw(term), term.height - 8, _kclr)
                    _kill_door_group(room, target.row, target.col, kind='locked_door')
                    player.row, player.col = target.row, target.col   # paste moves you over: step onto the unlocked door
                    _reveal_from(room, player.row, player.col)
                    budget.spend(_keystroke_cost(count, 'p', action.get('count_given', False))
                                 + _register_prefix_cost(action))
                    _push('Door unlocked!')
                else:
                    _has_key = any(ed['tmpl'].get('kind') == 'floor_key' for ed in clip_entities)
                    player.error = 'E: Wrong key for this door' if _has_key else 'E: No key held'
            elif target and target.kind == 'fancy_door':
                # THE FANCY DOOR. Same gesture as a locked door — stand beside it
                # and paste — but the key is words you cut out of the floor
                # instead of an object you picked up off it. See Entity.password.
                #
                # The comparison is on the REGISTER, never on the cells in front
                # of the door, so shoving the right word into the doorway with
                # inserted spaces does nothing: a key lying next to a lock has
                # never opened it either, and this is the same rule.
                held = _reg_text(clip)
                if held and held.lower() == target.password.lower():
                    undo_stack.append(_snapshot(room, player, budget, ans=cmd_start_ans))
                    redo_stack.clear()
                    _render(_pool_msg())
                    _unlock_animation(term, room, player, target.row, target.col,
                                      _iw(term), term.height - 8, None,
                                      icon=S.KEY_SPOKEN)
                    _kill_door_group(room, target.row, target.col, kind='fancy_door')
                    player.row, player.col = target.row, target.col
                    _reveal_from(room, player.row, player.col)
                    budget.spend(_keystroke_cost(count, 'p', action.get('count_given', False))
                                 + _register_prefix_cost(action))
                    _push('The door hears the word and opens!')
                elif held:
                    # NAME WHAT WAS HEARD, NEVER WHAT WAS WANTED. Quoting the
                    # register back is the whole diagnostic: the player sees
                    # that the door weighed the entire cut, fragment or extra
                    # words and all, which is the model. Quoting the PASSWORD
                    # back would hand over the answer to any door whose word is
                    # not lying in plain sight — a door across a room, or one
                    # an author placed in the forge with a word of their own.
                    player.error = f'E: It hears "{held}" — and does not budge'
                else:
                    player.error = 'E: You hold no words to speak'
            elif _clip_is_fire(clip):
                # Fire carried off a lit brazier. It LIGHTS a cold brazier and
                # does nothing else: a brazier is too heavy to set down, so a fire
                # paste never lays a second one — wherever it lands that is not a
                # cold brazier, it is a free no-op. Like a key, the register is not
                # consumed, so one light kindles a whole gallery.
                if target and target.kind == 'brazier':
                    if target.lit:
                        _push('That brazier already burns.')
                    else:
                        undo_stack.append(_snapshot(room, player, budget, ans=cmd_start_ans))
                        redo_stack.clear()
                        target.lit = True
                        budget.spend(_keystroke_cost(count, 'p', action.get('count_given', False))
                                     + _register_prefix_cost(action))
                        _push('The brazier catches — a flame stands.')
                else:
                    _push('There is no brazier here to hold the flame.')
            elif _flame_paste_blocked(room, player, clip, before, count):
                # The Beacon Tiers' fuel rule: flames lie only in braziers.
                # A FREE no-op — nothing paid, nothing snapshotted.
                _push(getattr(room, '_flame_block_msg',
                              'There is no fuel to hold that flame.'))
            elif clip and any(ed['tmpl'].get('kind') == 'floor_key'
                              for ed in clip_entities):
                # KEYS ARE SLIPPERY (global law): loosed anywhere
                # but onto a locked door, the key is gone — no pasted copy
                # lands AND the hand empties. (p never consumes a register, so
                # a floor paste would MINT a duplicate no cut could touch —
                # the register-stash exploit.) Undo far enough to re-loot.
                undo_stack.append(_snapshot(room, player, budget, ans=cmd_start_ans))
                redo_stack.clear()
                player.registers['"'] = None
                budget.spend(_keystroke_cost(count, 'p', action.get('count_given', False))
                             + _register_prefix_cost(action))
                _push('You lost the key!')
            elif clip and any(rw.get('char_runs') or rw.get('entities') for rw in clip['rows']):
                # One register for everything cut/yanked: lay characters back down and
                # respawn cut creatures. count fans out copies (3p = 3 in a row).
                undo_stack.append(_snapshot(room, player, budget, ans=cmd_start_ans))
                redo_stack.clear()
                if op_paste(room, player, clip, before, count):
                    if action.get('after_cursor') and player.col + 1 < room.cols \
                            and room.is_passable(player.row, player.col + 1):
                        # gp / gP: the cursor rests one cell PAST the pasted
                        # text — the stamp-run idiom (paste on, never step).
                        player.col += 1
                    budget.spend(_keystroke_cost(count, 'p', action.get('count_given', False))
                                 + (1 if action.get('after_cursor') else 0)
                                 + _register_prefix_cost(action))
                    spawned = next((ed['tmpl']['kind'] for ed in clip_entities), None)
                    _push(_PASTE_SPAWN_MSG[spawned] if spawned in _PASTE_SPAWN_MSG else 'Pasted.')
                    # A linewise paste is an EDIT like any other: a verse laid
                    # down can complete a gate THIS turn (the Refrain's last
                    # refrain opens its seal here — no extra step to wake it).
                    _content_ticks()
                else:
                    undo_stack.pop()
                    _push('Nothing pasted (no room).')
            else:
                _push('Nothing to paste here.')

        elif edit_mode and action['type'] == 'paste':
            if player.edit_clip:
                ed_undo.append(_ed_snapshot(room, player))
                ed_redo.clear()
                before = action.get('before', False)
                reg    = player.edit_clip
                items  = reg * count
                r      = player.row

                def _col_open(c, _r=r):
                    return (0 <= c < room.cols and
                            room.cells[_r][c] not in (CellType.WALL, CellType.WOOD_WALL))

                if before:  # P: left primary (cursor inclusive), overflow right
                    left_cols = []
                    for _c in range(player.col, -1, -1):
                        if _col_open(_c): left_cols.append(_c)
                        else: break
                    right_cols = []
                    for _c in range(player.col + 1, room.cols):
                        if _col_open(_c): right_cols.append(_c)
                        else: break
                    lc = min(count, len(left_cols))
                    rc = min(count - lc, len(right_cols))
                    if lc > 0:
                        _ed_paste(room, r, left_cols[lc - 1], list(reversed(items[:lc])))
                    if rc > 0:
                        _ed_paste(room, r, player.col + 1, items[lc:lc + rc])
                        new_c = player.col + rc + 1
                        while new_c < room.cols and not _col_open(new_c):
                            new_c += 1
                        if new_c < room.cols:
                            player.col = new_c
                else:  # p: right primary (cursor+1), overflow left
                    right_cols = []
                    for _c in range(player.col + 1, room.cols):
                        if _col_open(_c): right_cols.append(_c)
                        else: break
                    left_cols = []
                    for _c in range(player.col, -1, -1):
                        if _col_open(_c): left_cols.append(_c)
                        else: break
                    rc = min(count, len(right_cols))
                    lc = min(count - rc, len(left_cols))
                    if rc > 0:
                        _ed_paste(room, r, player.col + 1, items[:rc])
                    if lc > 0:
                        _ed_paste(room, r, left_cols[lc - 1],
                                  list(reversed(items[rc:rc + lc])))
                        new_c = player.col - lc
                        while new_c >= 0 and not _col_open(new_c):
                            new_c -= 1
                        if new_c >= 0:
                            player.col = new_c

                _push(f'Pasted {lc + rc} item(s) {"before" if before else "after"} cursor.')
            else:
                _push('Clipboard is empty.')

        elif action['type'] == 'replace':
            if not edit_mode and not _action_allowed(action, player.known_commands) and _blocked(action):
                continue
            (ed_undo if edit_mode else undo_stack).append(
                _ed_snapshot(room, player) if edit_mode else _snapshot(room, player, budget))
            (ed_redo if edit_mode else redo_stack).clear()
            if replace_chars(room, player, action['char'], count):
                if not edit_mode:
                    budget.spend(2 + _count_prefix_cost(count, action.get('count_given', False)))
                player.last_change = action
            else:
                (ed_undo if edit_mode else undo_stack).pop()
                _push('Nothing to replace.')

        elif action['type'] == 'case_char':
            if not edit_mode and not _action_allowed(action, player.known_commands) and _blocked(action):
                continue
            # (~ on a creature swells/shrinks it g<->G — handled inside case_char
            # via the shared engine.operator.case_entities rule.)
            (ed_undo if edit_mode else undo_stack).append(
                _ed_snapshot(room, player) if edit_mode else _snapshot(room, player, budget))
            (ed_redo if edit_mode else redo_stack).clear()
            if case_char(room, player, count):
                if not edit_mode:
                    budget.spend(_keystroke_cost(count, '~', action.get('count_given', False)))
                player.last_change = action
            else:
                (ed_undo if edit_mode else undo_stack).pop()
                _push('Nothing to toggle.')

        elif action['type'] == 'join' and not edit_mode:
            if not _action_allowed(action, player.known_commands) and _blocked(action):
                continue
            undo_stack.append(_snapshot(room, player, budget))
            redo_stack.clear()
            gap = action.get('gap', True)
            if op_join(room, player, gap=gap, count=count):
                budget.spend(_keystroke_cost(count, 'J' if gap else 'gJ', action.get('count_given', False)))
                player.last_change = action
                _push(_EDGE_OF_WORLD_MSG if room._last_build_blocked == 'edge' else 'Joined.')
            else:
                undo_stack.pop()
                _push(_EDGE_OF_WORLD_MSG if room._last_build_blocked == 'edge' else 'Nothing to join.')

        elif action['type'] == 'sub_repeat' and not edit_mode:
            if not _action_allowed(action, player.known_commands) and _blocked(action):
                continue
            _pre = _snapshot(room, player, budget, ans=cmd_start_ans)
            _sr_msg, _ns, _nl = _subst.repeat_normal(
                room, player, action['whole_file'], action['keep_flags'],
                confirm=_sub_confirm, insert_row=_sub_insert_row, delete_row=_sub_delete_row)
            if _ns or _nl:
                undo_stack.append(_pre)
                redo_stack.clear()
                budget.spend(2 if action['whole_file'] else 1)
                room.rebuild_indexes()
                player.last_change = action
                if _sr_msg:
                    _push(_sr_msg)
            elif _sr_msg and _sr_msg.startswith('E'):
                player.error = _sr_msg
            elif _sr_msg:
                _push(_sr_msg)

        elif action['type'] == 'operator' and action['op'] == '=':
            if not edit_mode and not _action_allowed(action, player.known_commands) and _blocked(action):
                continue
            tobj = (resolve_text_object(action['textobj'], room, player)
                    if 'textobj' in action else compute_text_object(player, action, room))
            if tobj is None:
                _push('Nothing to equalize.')
            else:
                (ed_undo if edit_mode else undo_stack).append(
                    _ed_snapshot(room, player) if edit_mode else _snapshot(room, player, budget))
                (ed_redo if edit_mode else redo_stack).clear()
                room._last_void_falls = []
                room._last_drowns     = []
                changed = False
                for _ir in range(tobj.start_row, tobj.end_row + 1):
                    changed |= apply_equalize(room, _ir)   # each row to the LAW's column
                player.row = min(tobj.start_row, room.rows - 1)
                nb = _first_non_blank_col(room, player.row)
                if nb is not None:
                    player.col = nb
                if not edit_mode:
                    budget.spend(_operator_cost(action))
                    _animate_reflow_falls()
                player.last_change = action
                if not changed:
                    _push('The lines already stand as the law reads.')

        elif action['type'] == 'operator' and action['op'] in ('>', '<'):
            if not edit_mode and not _action_allowed(action, player.known_commands) and _blocked(action):
                continue
            tobj = (resolve_text_object(action['textobj'], room, player)
                    if 'textobj' in action else compute_text_object(player, action, room))
            if tobj is None:
                _push('Nothing to indent.')
            else:
                (ed_undo if edit_mode else undo_stack).append(
                    _ed_snapshot(room, player) if edit_mode else _snapshot(room, player, budget))
                (ed_redo if edit_mode else redo_stack).clear()
                amount = INDENT_WIDTH if action['op'] == '>' else -INDENT_WIDTH
                room._last_void_falls = []
                room._last_drowns     = []
                for _ir in range(tobj.start_row, tobj.end_row + 1):
                    apply_indent(room, _ir, amount)        # `>` reflows: overflow tumbles off the brink
                player.row = min(tobj.start_row, room.rows - 1)
                nb = _first_non_blank_col(room, player.row)
                if nb is not None:
                    player.col = nb
                if not edit_mode:
                    budget.spend(_operator_cost(action))
                    _animate_reflow_falls()
                player.last_change = action

        elif action['type'] == 'operator' and action['op'] in ('g~', 'gu', 'gU'):
            if not edit_mode and not _action_allowed(action, player.known_commands) and _blocked(action):
                continue
            tobj = (resolve_text_object(action['textobj'], room, player)
                    if 'textobj' in action else compute_text_object(player, action, room))
            if tobj is None:
                _push('Nothing to operate on.')
            else:
                (ed_undo if edit_mode else undo_stack).append(
                    _ed_snapshot(room, player) if edit_mode else _snapshot(room, player, budget))
                (ed_redo if edit_mode else redo_stack).clear()
                op_case(room, player, tobj, action['op'])
                if not edit_mode:
                    budget.spend(_operator_cost(action))
                player.last_change = action

        elif not edit_mode and action['type'] == 'operator':
            if not _action_allowed(action, player.known_commands) and _blocked(action):
                continue
            op   = action['op']
            if 'textobj' in action:
                tobj = resolve_text_object(action['textobj'], room, player)
            else:
                tobj = compute_text_object(player, action, room)
            if tobj is None:
                _push('Nothing to operate on.')
            else:
                undo_stack.append(_snapshot(room, player, budget, ans=cmd_start_ans))
                redo_stack.clear()
                reg = action.get('register', '"')
                _op_blocked = False
                if op == 'y':
                    _reg_write(player, reg, op_yank(room, player, tobj), is_delete=False)
                    undo_stack.pop()          # yank does not mutate; drop snapshot
                    budget.spend(_operator_cost(action))
                    _push('Yanked.')
                elif op == 'c':
                    # change = delete the span, then INSERT at the deletion start
                    # (op_delete already repositions the cursor there).
                    _reg_write(player, reg, op_delete(room, player, tobj), is_delete=True)
                    budget.spend(_operator_cost(action))
                    player.mode = Mode.INSERT
                    insert_typed = ''
                else:                          # 'd'
                    _rows_before = room.rows
                    # note any warded wardens in the cut's span — if they outlive
                    # the cut (edit-immune), they flash their shield this frame.
                    _warded = [e for e in room.entities
                               if e.alive and e.kind == 'warden' and e.edit_immune
                               and tobj.start_row <= e.row <= tobj.end_row]
                    _clip = op_delete(room, player, tobj, collapse=True)
                    _survived = [e for e in _warded if e.alive]
                    if _survived:
                        room._ward_flash = {(e.row, e.col) for e in _survived}
                    if tobj.type is TextObjectType.LINEWISE and room.rows == _rows_before:
                        # The line-cut was PARRIED: an edit-immune door or boss
                        # anchors this row (or it is the dungeon's last line) and
                        # remove_row refused. Nothing was deleted — so nothing is
                        # paid, the register keeps what it held, no undo entry is
                        # left behind, and we say what happened instead of a
                        # false 'Deleted.'.
                        undo_stack.pop()
                        _op_blocked = True
                        if any(e.alive and e.edit_immune
                               and tobj.start_row <= e.row <= tobj.end_row
                               for e in room.entities):
                            _push('The cut is parried — something on this line is anchored fast.')
                        else:
                            _push("The dungeon's last line resists the cut.")
                    else:
                        _reg_write(player, reg, _clip, is_delete=True)
                        budget.spend(_operator_cost(action))
                        _push('Deleted.')
                if not _op_blocked and op != 'y':
                    # Yank is NOT a change (Vim): '.' must never repeat it, nor
                    # may a stray y disarm the echo of a real change.
                    player.last_change = action

        elif edit_mode and action['type'] == 'operator':
            op     = action['op']
            ed_undo.append(_ed_snapshot(room, player))
            ed_redo.clear()
            if 'textobj' in action:
                tobj = resolve_text_object(action['textobj'], room, player)
                if tobj is None:
                    ed_undo.pop()
                    _push('No text object here.')
                    _render(_pool_msg())
                    continue
                if op in ('d', 'c'):
                    items = _ed_delete_range(room, tobj.start_row, tobj.start_col, tobj.end_row, tobj.end_col)
                else:
                    items = _ed_range_items(room, tobj.start_row, tobj.start_col, tobj.end_row, tobj.end_col)
                player.edit_clip = items
                _push(f"{'Cut' if op in ('d', 'c') else 'Yanked'} {len(items)} item(s).")
            else:
                motion = action['motion']
                if motion == 'line':
                    all_items: list = []
                    for dr in range(count):
                        r = player.row + dr
                        if r >= room.rows:
                            break
                        all_items.extend(_ed_row_items(room, r))
                        if op in ('d', 'c'):
                            _ed_clear_row(room, r)
                    player.edit_clip = all_items
                    verb    = 'Cut' if op in ('d', 'c') else 'Yanked'
                    _push(f'{verb} {len(all_items)} item(s) from {count} row(s).')
                else:
                    orig_r, orig_c = player.row, player.col
                    mc = action.get('motion_count', 1)
                    apply_motion(player, motion, mc, room, action.get('target'),
                                 count_given=action.get('motion_count_given', True),
                                 game_h=term.height - 8)
                    new_r, new_c = player.row, player.col
                    player.row, player.col = orig_r, orig_c
                    if op in ('d', 'c'):
                        items = _ed_delete_range(room, orig_r, orig_c, new_r, new_c)
                    else:
                        items = _ed_range_items(room, orig_r, orig_c, new_r, new_c)
                    player.edit_clip = items
                    verb    = 'Cut' if op in ('d', 'c') else 'Yanked'
                    _push(f'{verb} {len(items)} item(s).')
            if op == 'y':
                ed_undo.pop()
            else:
                player.last_change = action

        # ── '.' of an insert-family change: replay the RECORDED TEXT ─────────
        # Vim-true: '.' after i…/a…/c{m}…/s… replays the whole change including
        # the typed run and the implicit Esc — it does not park the player in
        # INSERT. The re-dispatched action has already positioned the cursor
        # and (for c/s) cut the span; here the recorded text types itself.
        # The replay's spends are refunded by the settle below (dot = 1 key).
        if (_dot_active and player.mode == Mode.INSERT
                and not edit_mode and action.get('typed') is not None):
            for _rch in action['typed']:
                if _rch == '\n':
                    split_line_down(room, player)
                else:
                    insert_char(room, player, _rch)
            _animate_reflow_falls()
            player.mode = Mode.NORMAL
            insert_typed = ''
            if player.col > 0 and room.is_passable(player.row, player.col - 1):
                player.col -= 1                # the Esc retreat
            _content_ticks()                   # the change completes THIS turn

        # ── '.' repeat cost + change re-cost accounting (centralised) ────────
        # If a change ran this iteration (last_change changed and an undo entry was
        # pushed): for '.', refund the change's full price down to the dot's own keypress
        # cost; and tag the change's undo entry with its EFFECTIVE cost so undoing it arms
        # pending_recost_c — the next '.' then re-pays in full, closing the undo-refund
        # cheat (the same principle as f/;/ and search n/N).
        if (not edit_mode and not budget.frozen
                and player.last_change is not _lc_before and len(undo_stack) > _undo_len0):
            if _dot_active:
                budget.spent = _spent_before + _dot_cost
            _top = undo_stack[-1]
            if isinstance(_top, dict):
                _top['recost'] = ('c', budget.spent - _spent_before)

        # ── Combat: enemy movement then adjacency attacks ────────────────────
        if not edit_mode:
            xd_id     = (id(cur_combat_target)
                         if action['type'] == 'interact' and cur_combat_target
                         else None)
            tick_msgs = _enemy_tick(room, player)
            # Easter-egg economy: pocket a coin underfoot; an adjacent untraded
            # elf opens a bargain (one at a time, only within a cell).
            _coin = room.entity_at(player.row, player.col)
            if _coin is not None and _coin.kind == 'gold':
                room.kill_entity(_coin); room.rebuild_indexes()
                player.gold += 1
                progress['gold'] = player.gold
                tick_msgs.insert(0, f'You pocket a coin. (gold: {player.gold})')
            # First meeting with the wizard's horse: he comes to your side and you
            # name him. Once named (or waved off), his name colours every message.
            if not progress.get('horse_met'):
                _hz = next((e for e in room.entities if e.kind == 'horse'), None)
                if _hz is not None and _manhattan(player.row, player.col,
                                                  _hz.row, _hz.col) <= 1:
                    _hname = _prompt_horse_name(term, _iw(term), term.height - 8)
                    progress['horse_met'] = True
                    if _hname:
                        progress['horse_name'] = _hz.tag = _hname
                    _save_progress(progress, player_name)
                    tick_msgs = [f'{_hname} falls in at your heel.' if _hname
                                 else 'The horse stays put, unhurried. '
                                      '(x him when you have a name.)']
            if not getattr(room, '_elf_trade', None):
                for _elf in list(room._entity_by_kind.get('elf', [])):
                    if (_elf.alive and _elf.tag == 'elf'
                            and _manhattan(player.row, player.col, _elf.row, _elf.col) <= 1):
                        _offer, _cost, _key, _res = random.choice(_ELF_TRADES)
                        _prompt = (f'The elf offers {_offer} for {_cost} gold. '
                                   'Deal? (y = yes, n = no)')
                        room._elf_trade = {'elf_id': id(_elf), 'cost': _cost,
                                           'key': _key, 'result': _res, 'prompt': _prompt}
                        _elf.tag = 'offering'
                        break
            _surveyor_tick()                  # the Surveyor's telegraph → resolve cadence
            _mega = getattr(room, 'mega', None)   # the floor-cut has no creature — flash where it hit
            if _mega and _mega.get('hit_player'):
                attack_flash_pos = _mega['hit_player']
                attack_flash_sym = '✶'
                attack_flash_on  = True
                attack_flash_ttl = _ATTACK_FLASH_TTL

            # Any enemy now adjacent attacks (except the one the player just hit,
            # and except enemies that only became adjacent this turn — player gets
            # one free turn when landing next to a new enemy via fg/motion).
            _arch_atk = (room._entity_by_kind.get('archivist', [])
                         if getattr(room, 'lib_hostile', False) else [])
            attackers = []
            for ent in (*room._entity_by_kind.get('goblin', []),
                        *room._entity_by_kind.get('warden', []),
                        *room._entity_by_kind.get('critter', []), *_arch_atk):
                if not ent.alive:
                    continue
                if ent.kind == 'critter' and not ent.swole:
                    continue                          # a small cat is harmless
                if id(ent) == xd_id:
                    continue
                if id(ent) not in prev_adjacent_ids:
                    continue
                if _manhattan(player.row, player.col, ent.row, ent.col) <= _ATTACK_RADIUS:
                    attackers.append(ent)
                    if ent.kind == 'archivist':
                        _dmg = 10
                    elif ent.kind in ('goblin', 'critter'):
                        _dmg = _hp_atk(_entity_glyph(ent))[1]   # &=2 Z=1 C=3 g=1
                    else:
                        _dmg = 1                       # a warden
                    player.take_damage(max(1, _dmg))
                    room._atk_arrows.append((ent.row, ent.col, player.row,
                                             player.col, _arrow_key(ent)))
                    if player.is_dead:
                        message = '** GAME OVER ** Type  :e  to re-load the dungeon.'
                        msg_ttl = 2
                        break
            if attackers and not player.is_dead:
                ent = attackers[0]
                dr  = player.row - ent.row
                dc  = player.col - ent.col
                attack_flash_sym = _SPEAR_DIRS.get((dr, dc), '✕')
                attack_flash_pos = (ent.row, ent.col)
                attack_flash_on  = True
                attack_flash_ttl = _ATTACK_FLASH_TTL

            # Pathfinder Act 3: once the verse has collapsed AND the minions are cleared
            # (whichever is later), the Warden's key clatters to the arena floor.
            if (level == 'warden_pathfinder' and getattr(room, 'verse_collapsed', False)
                    and not getattr(room, 'key_dropped', False)
                    and not any(e.alive and e.kind == 'goblin' for e in room.entities)):
                room.key_dropped = True
                if _drop_key(room, 12, 40):
                    _push('The last minion falls — a key clatters to the floor!  🗝  '
                          '(step onto it, then  p  it onto the treasure door)')

            # The Operator's Vault: drop gate/vault keys as guard groups fall
            # (guards die by d{motion}, which never routes through _on_kill).
            if level == 'operators_vault':
                for _ov_msg in _operators_vault_tick(room, player):
                    _push(_ov_msg)
                # There is deliberately NO overhang hint. One used to fire here
                # — "…This floor is one rotten line: dd cuts it out from under
                # you." — which is the answer said out loud at the one corridor
                # whose lesson is hardest to see coming. The level shows it
                # instead: a seep of water hangs at the foot of corridor 8's
                # gate column, and the line it lies in is the line `dd` takes
                # out. See _OV_SEEP in the builder.

            # The buffer-content gate ticks (Cipher Cell · Beacon Tiers · Echo
            # Vault · Warden Manifold · Inscription Halls · Change Annex/Extension ·
            # Overwrite Halls · Sculpting Chambers) — a bolt/door opens the instant
            # its plaque/verse READS TRUE on the floor. Also fired on INSERT/REPLACE
            # Esc so an edit opens its gate the same turn (see _content_ticks).
            _content_ticks()

            # Warden summon message
            if tick_msgs and not player.is_dead:
                _push(tick_msgs[0])
            # A pending elf bargain PRE-EMPTS the message queue so it is never
            # buried — it shows every turn until you answer y or n.
            _et = getattr(room, '_elf_trade', None)
            if _et:
                msg_pool[:] = [_et['prompt']]
                msg_idx = 0
                message = _et['prompt']
                msg_ttl = 999

            # Engagement: fire for any attacker now adjacent
            if attackers:
                for _ae in attackers:
                    if id(_ae) not in engaged_entities:
                        engaged_entities.add(id(_ae))
                        _aname = ('Warden' if _ae.kind == 'warden' else
                                  'Archivist' if _ae.kind == 'archivist' else
                                  _creature_name(_entity_glyph(_ae)))   # zombie/demon/cat
                        _push(f'The {_aname} is engaging you in combat!')
            else:
                engaged_entities.clear()

            # Spotted: new enemies now visible (not in fog)
            if not player.is_dead:
                new_g = [e for e in room._entity_by_kind.get('goblin', [])
                         if e.alive
                         and id(e) not in spotted_goblins
                         and (e.row, e.col) not in room.fog_cells]
                for e in new_g:
                    spotted_goblins.add(id(e))
                if new_g:
                    _push(_goblin_msg(_goblin_sighting(len(new_g))))

                for e in room._entity_by_kind.get('warden', []):
                    if (e.alive
                            and id(e) not in spotted_wardens
                            and (e.row, e.col) not in room.fog_cells):
                        spotted_wardens.add(id(e))
                        _push('You spotted a Warden!')

        if not edit_mode and budget.is_over:
            _push('Over budget! Try a more efficient path. (u to undo)')

        # Locked-door proximity hints (first time within 1 cell of each door)
        if not edit_mode and not player.is_dead:
            for ent in room._entity_by_kind.get('locked_door', []):
                if (ent.alive
                        and abs(ent.row - player.row) + abs(ent.col - player.col) <= 1):
                    has_reg_key = any(
                        ed['tmpl'].get('kind') == 'floor_key'
                        for rw in (_reg_read(player, '"') or {}).get('rows', [])
                        for ed in rw.get('entities', ())
                    )
                    if has_reg_key and id(ent) not in door_open_hint_shown:
                        door_open_hint_shown.add(id(ent))
                        _push('The lock waits — the key is in your hand, not in the door.')
                    elif not has_reg_key and id(ent) not in door_hint_shown:
                        door_hint_shown.add(id(ent))
                        _push('This door requires a key.')

        # ── Pool finalization: display rotation or clear message ──────────────
        if not player.is_dead and not won:
            if msg_pool:
                msg_idx = 0
                message = _pool_msg()
                msg_ttl = _MSG_ROTATE_TTL
            else:
                message = ''
                msg_ttl = 0

        _render(message)


# ── Save-select screen loop ───────────────────────────────────────────────────

def run_save_select(term: Terminal) -> tuple[str, str]:
    """Show the save-selection screen.

    Returns ('load', player_name) or ('back', '').
    """
    saves    = SM.list_saves()
    cursor   = 0
    pending_d = False

    render_save_select(term, saves, cursor)

    while True:
        key = term.inkey(timeout=0.1)
        if not key:
            continue

        raw = str(key) if not key.is_sequence else ''

        if pending_d:
            pending_d = False
            if raw == 'd' and saves:
                name = SM.load_player_name(saves[cursor])
                SM.delete_save(name)
                saves  = SM.list_saves()
                cursor = min(cursor, max(0, len(saves) - 1))
                render_save_select(term, saves, cursor)
                continue
            # fall through to handle the key normally

        if key.name == 'KEY_ESCAPE':
            return ('back', '')
        elif raw == 'j':
            cursor = min(cursor + 1, max(0, len(saves) - 1))
        elif raw == 'k':
            cursor = max(cursor - 1, 0)
        elif raw == 'd' and saves:
            pending_d = True
        elif key.name == 'KEY_ENTER' or raw in ('\n', '\r'):
            if saves:
                name = SM.load_player_name(saves[cursor])
                SM.touch_loaded(name)
                return ('load', name)

        render_save_select(term, saves, cursor, deleting=pending_d)


# ── Scroll library loop ───────────────────────────────────────────────────────

def run_scroll_library(term: Terminal, player: Player, progress: dict) -> str | None:
    """Show the scroll library (~/.vimny/scrolls/). Marks opened scrolls as seen.

    Returns None  → back to overworld
            'parent' → go up to ~/.vimny/ parent view
            'saves'  → open character select
    """
    from vimny.render.scroll_library import (render_scroll_library, library_rows,
                                        row_label, row_section_key)

    _rows = library_rows()

    _SL_COMPLETIONS = ['../', 'saves/', 'world/']

    _known    = _known_from_progress(progress)
    is_admin  = player.name == 'admin'

    def _gate(tok, label):
        if is_admin or tok in _known:
            return True
        player.error = f"You haven't learned {label} yet."
        return False

    discovered = set(progress.get('extras', []))
    bless_seen = set(progress.get('blessings_seen', []))

    def _label(r):        return row_label(r, discovered, bless_seen)
    def _avail():         return max(1, (term.height - 5) - 6)   # game_h − header rows

    # Buffer-local marks, session-scoped on the player (like the overworld's).
    if not hasattr(player, 'scroll_marks'):
        player.scroll_marks = {}

    # start on the first actual scroll (skip ../ ./ and the first subtree header)
    start = next((i for i, r in enumerate(_rows) if r['type'] == 'scroll'), 0)
    nav = NetrwNav(player=player, get_lines=lambda: _rows, label=_label,
                   section_key=row_section_key, gate=_gate, avail=_avail,
                   completions=_SL_COMPLETIONS, marks=player.scroll_marks,
                   cursor=start)

    def _render():
        cmd_line = (nav.searching['buf'] if nav.searching
                    else nav.cmdline.line if nav.cmdline.active else None)
        cmd_pfx  = nav.searching['pfx'] if nav.searching else ':'
        nav.scroll_offset = render_scroll_library(
            term, player, progress, nav.cursor, cmd_line, nav.scroll_offset, cmd_pfx)

    _render()

    while True:
        key = term.inkey(timeout=0.1)
        if not key:
            continue

        out = nav.feed(key)
        if out is None:
            _render()
            continue

        if out[0] == 'cmd':
            cmd = out[1]
            if cmd in ('q', 'q!'):
                return None
            _e_path = cmd[2:].rstrip('/') if cmd.startswith('e ') else ''
            if _e_path in ('..', '../'):
                return 'parent'
            if _e_path in ('saves',):
                return 'saves'
            if _e_path in ('world',):
                return None
            _render()
            continue

        raw = out[1]
        if key.name == 'KEY_ESCAPE':
            return None
        elif raw == '-':
            return 'parent'
        elif key.name == 'KEY_ENTER' or raw in ('\n', '\r'):
            _r = _rows[nav.cursor]
            if _r['type'] == 'parent':
                return 'parent'
            elif _r['type'] in ('self', 'subhdr'):
                pass  # ./ or a subtree header — stay
            else:
                scroll = _r['scroll']
                _disc  = bless_seen if _r.get('group') == 'blessings' else discovered
                if scroll['id'] in _disc:
                    iw     = _iw(term)
                    game_h = term.height - 5
                    _render()
                    _show_scroll_by_id(term, iw, game_h, scroll['id'], _known)
                    seen = list(progress.get('scrolls_seen', []))
                    if scroll['id'] not in seen:
                        seen.append(scroll['id'])
                        progress['scrolls_seen'] = seen
                        SM.save_progress(progress, player.name)

        _render()


# ── Color palette loop (~/.vimny/colors/) ────────────────────────────────────

def run_colors(term: Terminal, player: Player) -> None:
    """Show the color palette (admin only). Returns when the player exits.

    Admin-only, so every motion is ungated — but it drives the same shared
    NetrwNav engine as the overworld and scroll library, so gg/G/{n}G, H/M/L,
    {/}, w, /-search, counts and the rest all work over the colour list."""
    from vimny.render.color_palette import (render_color_palette, palette_rows,
                                       row_label, row_section_key)

    _rows = palette_rows()
    if not hasattr(player, 'color_marks'):
        player.color_marks = {}

    nav = NetrwNav(player=player, get_lines=lambda: _rows, label=row_label,
                   section_key=row_section_key, gate=lambda tok, label: True,
                   avail=lambda: max(1, (term.height - 5) - 6),   # game_h − header
                   completions=['../', 'saves/', 'scrolls/', 'world/'],
                   marks=player.color_marks, cursor=0)

    def _render():
        cmd_line = (nav.searching['buf'] if nav.searching
                    else nav.cmdline.line if nav.cmdline.active else None)
        cmd_pfx  = nav.searching['pfx'] if nav.searching else ':'
        nav.scroll_offset = render_color_palette(
            term, player, nav.cursor, nav.scroll_offset, cmd_line, cmd_pfx)

    _render()

    while True:
        key = term.inkey(timeout=0.1)
        if not key:
            continue

        out = nav.feed(key)
        if out is None:
            _render()
            continue

        if out[0] == 'cmd':
            cmd = out[1]
            if cmd in ('q', 'q!') or cmd.startswith('e '):
                return
            _render()
            continue

        raw = out[1]
        if key.name == 'KEY_ESCAPE' or raw == '-':
            return

        _render()


# ── Parent directory loop (~/.vimny/) ─────────────────────────────────────────

def run_parent_dir(term: Terminal, player: Player, progress: dict) -> str | None:
    """Show the ~/.vimny/ parent directory.

    Returns None       → back to overworld (Esc or 'world/' selected)
            'scrolls'  → open scroll library
            'saves'    → open character select
            'colors'   → open color palette (admin only)
    """
    from vimny.render.parent_dir import render_parent_dir, entries_for

    entries = entries_for(player)
    _PD_COMPLETIONS = ['saves/', 'scrolls/', 'world/'] + (
        ['colors/'] if player.name == 'admin' else []
    )

    cursor_row  = 2  # 0=../ 1=./ 2+=entries
    cmdline     = _CmdLine(_PD_COMPLETIONS)

    def _render():
        render_parent_dir(term, player, progress, cursor_row,
                          cmdline.line if cmdline.active else None)

    _render()

    while True:
        key = term.inkey(timeout=0.1)
        if not key:
            continue

        if cmdline.active:
            cmd = cmdline.feed(key)
            if cmd:
                if cmd in ('q', 'q!'):
                    return None
                _e_path = cmd[2:].rstrip('/') if cmd.startswith('e ') else ''
                if _e_path in ('scrolls',):
                    return 'scrolls'
                if _e_path in ('saves',):
                    return 'saves'
                if _e_path in ('colors',) and player.name == 'admin':
                    return 'colors'
                if _e_path in ('world',):
                    return None
            _render()
            continue

        raw = str(key) if not key.is_sequence else ''

        if key.name == 'KEY_ESCAPE':
            return None
        elif raw == ':':
            cmdline.open()
        elif raw == 'j':
            cursor_row = min(cursor_row + 1, len(entries) + 1)
        elif raw == 'k':
            cursor_row = max(cursor_row - 1, 0)
        elif key.name == 'KEY_ENTER' or raw in ('\n', '\r'):
            if cursor_row <= 1:
                pass  # ../ or ./ — no-op in parent dir
            else:
                entry = entries[cursor_row - 2].rstrip('/')
                if entry == 'scrolls':
                    return 'scrolls'
                if entry == 'saves':
                    return 'saves'
                if entry == 'colors':
                    return 'colors'
                return None  # 'world' → back to overworld

        _render()


def run_remote_shelf(term: Terminal, player: Player, progress: dict) -> None:
    """Browse the online community shelf (chkiss/vimny-levels) and install a
    level onto the local shelf.

    Netrw browses remote paths for real, so `community/remote/` is not a bolt-on
    — it is the most Vim-accurate directory the overworld has. j/k move; Enter
    downloads the level under the cursor, validates it, and drops it on the local
    shelf (where it turns up under `community/`); r re-fetches the manifest;
    Esc / - go back. A level is inert JSON that the validator vets before it
    lands, so nothing downloaded here can run on the player's machine.

    Returns None — always back to the overworld, which re-lists `community/` so
    a freshly installed level appears at once.
    """
    from vimny.render.remote_shelf import render_remote_shelf

    entries: list = []
    status         = 'fetching the shelf…'
    cursor_row     = 0
    cmdline        = _CmdLine([])

    def _installed_slugs() -> set:
        try:
            return {s.path.stem for s in community_levels()}
        except Exception:                          # noqa: BLE001
            return set()

    installed = _installed_slugs()

    def _render():
        render_remote_shelf(term, player, progress, entries, installed,
                            cursor_row, status,
                            cmdline.line if cmdline.active else None)

    def _refresh():
        nonlocal entries, status, cursor_row
        status = 'fetching the shelf…'
        _render()                                  # show the "fetching" note first
        entries, err = REMOTE.fetch_manifest()
        cursor_row   = 0
        if err:
            status = err
        elif not entries:
            status = 'the shelf is empty'
        else:
            status = f'{len(entries)} level(s) — Enter to install'

    _refresh()
    _render()

    while True:
        key = term.inkey(timeout=0.1)
        if not key:
            continue

        if cmdline.active:
            cmd = cmdline.feed(key)
            if cmd:
                if cmd in ('q', 'q!'):
                    return None
                _e_path = cmd[2:].rstrip('/') if cmd.startswith('e ') else ''
                if _e_path in ('..', '../', 'world', 'community'):
                    return None
            _render()
            continue

        raw = str(key) if not key.is_sequence else ''

        if key.name == 'KEY_ESCAPE' or raw == '-':
            return None
        elif raw == ':':
            cmdline.open()
        elif raw == 'r':
            _refresh()
        elif raw == 'j':
            cursor_row = min(cursor_row + 1, max(0, len(entries) - 1))
        elif raw == 'k':
            cursor_row = max(cursor_row - 1, 0)
        elif raw == 'g':
            cursor_row = 0
        elif raw == 'G':
            cursor_row = max(0, len(entries) - 1)
        elif key.name == 'KEY_ENTER' or raw in ('\n', '\r'):
            if entries:
                entry  = entries[cursor_row]
                status = f'installing {entry.name}…'
                _render()
                shelf = REMOTE.install_entry(entry)
                if shelf.ok:
                    installed = _installed_slugs()
                    status    = f'installed {shelf.name} → community/'
                else:
                    status    = f'{entry.name}: {shelf.error}'

        _render()


# ── Title screen loop ─────────────────────────────────────────────────────────

def run_title(term: Terminal, has_save: bool) -> tuple[str, str]:
    """Show the title screen.

    Returns ('new', name), ('load', name), or ('quit', '').
    'new'  — player chose "begin new journey" and entered a name; progress wiped.
    'load' — player chose "load saved game" and selected a save.
    'quit' — player quit.
    """
    state        = 'menu'   # 'menu' | 'naming' | 'confirm'
    cursor       = 0
    cmd_buf      = ''       # ':' + chars typed in command mode
    name_buf     = ''       # chars typed in naming state
    pending_name = ''       # name awaiting overwrite confirmation
    _blink       = False    # current eye state; updated by timer

    # First-time open (no saves yet): show the :wq poem so the player knows
    # how to save and quit before they've touched anything.
    # Returning players: pick randomly from quotes unlocked across all saves.
    if not has_save:
        _quote_lines = select_quote_by_name('save and quit')
    else:
        _unlocked_slugs: set[str] = set()
        for _sd in SM.list_saves():
            _prog = SM.load_progress(_sd)
            for _lv in LEVELS:
                if is_unlocked(_lv['slug'], _prog):
                    _unlocked_slugs.add(_lv['slug'])
        _quote_lines = select_quote(_unlocked_slugs)

    def _render():
        cl = cmd_buf[1:]  if cmd_buf.startswith(':') else None
        np = name_buf     if state == 'naming'        else None
        cn = pending_name if state == 'confirm'       else None
        render_title(term, cursor, has_save, cmd_line=cl, name_prompt=np,
                     confirm_name=cn, blink=_blink, quote_lines=_quote_lines)

    _blink = (time.time() % 5) < 0.5
    _render()

    while True:
        key = term.inkey(timeout=0.1)

        # Blink: eyes closed for 0.5 s once every 5 s
        new_blink = (time.time() % 5) < 0.5
        if new_blink != _blink:
            _blink = new_blink
            _render()

        if not key:
            continue

        raw = str(key) if not key.is_sequence else ''

        # ── Confirm overwrite state ───────────────────────────────────────────
        if state == 'confirm':
            if raw in ('y', 'Y'):
                SM.save_for(pending_name, {'player_name': pending_name, 'progress': {}})
                return ('new', pending_name)
            elif raw in ('n', 'N') or key.name == 'KEY_ESCAPE':
                name_buf     = pending_name
                pending_name = ''
                state        = 'naming'
            _render()
            continue

        # ── Naming state ──────────────────────────────────────────────────────
        if state == 'naming':
            if key.name == 'KEY_ESCAPE':
                state    = 'menu'
                name_buf = ''
            elif key.name == 'KEY_ENTER' or raw in ('\n', '\r'):
                name = name_buf.strip() or 'Normand'
                if SM.load_for(name) is not None:
                    pending_name = name
                    state        = 'confirm'
                else:
                    SM.save_for(name, {'player_name': name, 'progress': {}})
                    return ('new', name)
            elif key.name == 'KEY_BACKSPACE' or raw == '\x7f':
                name_buf = name_buf[:-1]
            elif raw and raw.isprintable() and len(name_buf) < _NAME_MAX:
                name_buf += raw
            _render()
            continue

        # ── Command-line mode (:q, :q!, :wq all quit) ────────────────────────
        if cmd_buf.startswith(':'):
            if key.name == 'KEY_ENTER' or raw in ('\n', '\r'):
                cmd     = cmd_buf[1:].strip()
                cmd_buf = ''
                if cmd in ('q', 'q!', 'wq'):
                    return ('quit', '')
            elif key.name == 'KEY_ESCAPE':
                cmd_buf = ''
            elif key.name == 'KEY_BACKSPACE' or raw == '\x7f':
                cmd_buf = cmd_buf[:-1]
            elif raw:
                cmd_buf += raw
            _render()
            continue

        # ── Normal menu navigation ────────────────────────────────────────────
        if raw == ':':
            cmd_buf = ':'
        elif key.name == 'KEY_ESCAPE':
            cmd_buf = ''
        elif raw == 'j':
            cursor = (cursor + 1) % len(_TITLE_MENU)
        elif raw == 'k':
            cursor = (cursor - 1) % len(_TITLE_MENU)
        elif key.name == 'KEY_ENTER' or raw in ('\n', '\r'):
            _, action = _TITLE_MENU[cursor]
            if action == 'quit':
                return ('quit', '')
            elif action == 'load' and not has_save:
                pass  # dimmed — ignore
            elif action == 'load':
                sel_action, sel_name = run_save_select(term)
                if sel_action == 'load':
                    return ('load', sel_name)
                # 'back' — fall through and re-render title
            elif action == 'new':
                state    = 'naming'
                name_buf = ''

        _render()


# ── Overworld loop ─────────────────────────────────────────────────────────────

_OW_GRP = {'comment': 'c', 'parent': 'd', 'self': 'd', 'level': 'l',
           'subhdr': 'x', 'custom': 'x', 'community': 'x', 'draft': 'x'}


def _ow_section_key(ln: dict) -> str:
    """Section grouping for `{`/`}` over the overworld (comments → dirs →
    levels → customs)."""
    return _OW_GRP.get(ln['type'])


def _ow_section(lines: list, cursor: int, direction: int) -> int:
    """{ / } over the overworld buffer: the first line of the prev/next section."""
    starts = _section_starts(lines, _ow_section_key)
    if direction < 0:
        before = [s for s in starts if s < cursor]
        return before[-1] if before else 0
    after = [s for s in starts if s > cursor]
    return after[0] if after else len(lines) - 1


# ── Overworld string motions ──────────────────────────────────────────────────
# Vim word/find motions over a plain label string (the netrw buffer has no
# Room, so these mirror engine/motion's class rules on text: word chars are
# [A-Za-z0-9_], punctuation is its own class, WORD is whitespace-bounded).

def _owm_class(ch: str) -> int:
    if ch.isspace():
        return 0
    return 1 if (ch.isalnum() or ch == '_') else 2


def _owm_w(text: str, c: int, big: bool) -> int:
    n = len(text)
    if c >= n - 1:
        return c
    k = _owm_class(text[c]) if not big else (0 if text[c].isspace() else 1)
    i = c
    while i < n and ((0 if text[i].isspace() else 1) if big else _owm_class(text[i])) == k and k != 0:
        i += 1
    while i < n and text[i].isspace():
        i += 1
    return i if i < n else c


def _owm_b(text: str, c: int, big: bool) -> int:
    i = c - 1
    while i >= 0 and text[i].isspace():
        i -= 1
    if i < 0:
        return c
    k = (1 if not text[i].isspace() else 0) if big else _owm_class(text[i])
    while i - 1 >= 0 and ((0 if text[i-1].isspace() else 1) if big else _owm_class(text[i-1])) == k:
        i -= 1
    return i


def _owm_e(text: str, c: int, big: bool) -> int:
    n = len(text)
    i = c + 1
    while i < n and text[i].isspace():
        i += 1
    if i >= n:
        return c
    k = (1 if not text[i].isspace() else 0) if big else _owm_class(text[i])
    while i + 1 < n and ((0 if text[i+1].isspace() else 1) if big else _owm_class(text[i+1])) == k:
        i += 1
    return i


def _owm_find(text: str, c: int, ch: str, fwd: bool, till: bool) -> int | None:
    if fwd:
        i = text.find(ch, c + 1 + (1 if till else 0))
        if i < 0:
            return None
        return i - (1 if till else 0)
    i = text.rfind(ch, 0, c - (1 if till else 0))
    if i < 0:
        return None
    return i + (1 if till else 0)


def _owm_word_at(text: str, c: int) -> str | None:
    """The word under (or after, Vim-true) the cursor — for * / g*."""
    n = len(text)
    i = c
    while i < n and _owm_class(text[i]) != 1:
        i += 1
    if i >= n:
        return None
    lo = i
    while lo - 1 >= 0 and _owm_class(text[lo - 1]) == 1:
        lo -= 1
    hi = i
    while hi + 1 < n and _owm_class(text[hi + 1]) == 1:
        hi += 1
    return text[lo:hi + 1]


def _section_starts(lines: list, key_of) -> list:
    """Indices where a new section begins, given a per-line grouping key. Shared
    by `{`/`}` across every netrw buffer (overworld, scroll library, …)."""
    starts, prev = [], object()
    for i, ln in enumerate(lines):
        g = key_of(ln)
        if g != prev:
            starts.append(i); prev = g
    return starts


class NetrwNav:
    """The shared netrw motion engine for the overworld / scroll library / any
    read-only, cursor-over-lines buffer. It owns the Vim navigation state —
    cursor, viewport offset, curswant column, counts, marks, the jump list,
    pending g/z/f/mark prefixes, and the `/`/`?` + `:` command lines — so every
    such screen gets gg, G, {n}G, H/M/L, {/}, w/b/e, f/F/t/T, ;/,, `*`/`#`, marks,
    Ctrl-o/i, Ctrl-d/u/f/b and `/`-search identically.

    The host supplies the buffer-specific pieces via callables: `get_lines()`
    (the live line list), `label(ln)` (a line's motion/search text), `section_key(ln)`
    (grouping for `{`/`}`), `gate(tok, label)` (learned-command gating — returns
    True/sets player.error), `avail()` (viewport height), plus a `marks` dict and
    the `:`-completion list.

    `feed(key)` handles one keypress and returns:
      * ``None`` — fully consumed (motion/search/count/…); the host re-renders.
      * ``('cmd', text)`` — a completed `:` command for the host to interpret.
      * ``('key', raw, key)`` — a key the engine doesn't own (Enter, D, R, -,
        Esc, …); the host dispatches it.
    The host keeps `self.scroll_offset` in sync by writing back whatever its
    renderer computes each frame.
    """

    def __init__(self, *, player, get_lines, label, section_key, gate, avail,
                 completions=None, marks=None, cursor=0):
        self.player       = player
        self._get_lines   = get_lines
        self._label_of    = label
        self._section_key = section_key
        self._gate        = gate
        self._avail       = avail
        self.marks        = marks if marks is not None else {}
        self.cmdline      = _CmdLine(completions or [])

        self.cursor        = cursor
        self.scroll_offset = 0
        self.want_col      = 0
        self.count_buf     = ''
        self.pending_g     = False
        self.pending_z     = False
        self.pending_mark  = ''
        self.pending_find  = ''
        self.searching     = None       # None | {'pfx': '/'|'?', 'buf': str}
        self.last_f        = None       # (cmd, char) for ; and ,

        self.jump_list: list = []
        self.jump_idx        = 0
        self.last_jump       = None

    # ── cursor helpers ────────────────────────────────────────────────────────
    def _lines(self):           return self._get_lines()
    def _lbl(self, i=None):
        lines = self._lines()
        return self._label_of(lines[self.cursor if i is None else i])
    def _eff(self, i=None):     return min(self.want_col, max(0, len(self._lbl(i)) - 1))
    def col(self):              return self._eff()

    def _mgate(self, mkey, label):
        tok = _MOTION_GUARD_TABLE.get(mkey)
        return tok is None or self._gate(tok, label)

    def _jump_to(self, target):
        """A JUMP motion (G / { } / search / mark / :{n}): record the origin in
        the jump list + '' mark, exactly like Vim."""
        if target == self.cursor:
            return
        self.last_jump = self.cursor
        del self.jump_list[self.jump_idx:]
        self.jump_list.append(self.cursor)
        self.jump_idx = len(self.jump_list)
        self.cursor = target

    # ── search over the visible buffer text ───────────────────────────────────
    def _match_cols(self, pattern, text):
        """Columns where `pattern` matches, ignoring case.

        A netrw buffer searches with 'ignorecase' on: these labels are FILE
        NAMES — `dungeon_03_the_rune_halls`, `Maze of Ana by Ana` — and their
        capitalisation is the renderer's business, not something a player should
        have to guess before they can jump to a row.

        `\\c` is PREPENDED rather than forced with a regex flag so that `\\C`
        still works: `_translate` walks the pattern in order and the last of the
        pair wins, which is exactly Vim's rule for overriding 'ignorecase' from
        inside a pattern. The literal fallback (an untranslatable pattern) folds
        both sides instead, so the two paths agree."""
        if not pattern:
            return []
        pat = _vre_compile('\\c' + pattern)
        if pat is not None:
            return sorted({s for s, _e in pat.finditer(text)})
        low, text = pattern.lower(), text.lower()
        cols, k = [], text.find(low)
        while k >= 0:
            cols.append(k)
            k = text.find(low, k + 1)
        return cols

    def _search_from(self, pattern, fwd, start, start_col):
        lines = self._lines()
        n = len(lines)
        here = self._match_cols(pattern, self._label_of(lines[start]))
        if fwd:
            after = [c for c in here if c > start_col]
            if after:
                return (start, after[0]), False
            for step in range(1, n + 1):
                i = (start + step) % n
                cols = self._match_cols(pattern, self._label_of(lines[i]))
                if cols:
                    return (i, cols[0]), (i <= start)
            return None, False
        before = [c for c in here if c < start_col]
        if before:
            return (start, before[-1]), False
        for step in range(1, n + 1):
            i = (start - step) % n
            cols = self._match_cols(pattern, self._label_of(lines[i]))
            if cols:
                return (i, cols[-1]), (i >= start)
        return None, False

    def _run_search(self, pattern, fwd):
        if not pattern:
            self.player.error = 'E35: No previous regular expression'
            return
        self.player.last_search = (pattern, fwd)
        hit, wrapped = self._search_from(pattern, fwd, self.cursor, self._eff())
        if hit is None:
            self.player.error = f'E486: Pattern not found: {pattern}'
        else:
            self._jump_to(hit[0])
            self.want_col = hit[1]
            if wrapped:
                self.player.error = ('search hit BOTTOM, continuing at TOP'
                                     if fwd else 'search hit TOP, continuing at BOTTOM')

    # ── the keypress state machine ────────────────────────────────────────────
    def feed(self, key):
        # ── search input (/ ?) ────────────────────────────────────────────────
        if self.searching is not None:
            if key.name == 'KEY_ESCAPE':
                self.searching = None
            elif key.name == 'KEY_ENTER' or str(key) in ('\n', '\r'):
                pat = self.searching['buf'] or (self.player.last_search or ('', True))[0]
                fwd = self.searching['pfx'] == '/'
                self.searching = None
                self._run_search(pat, fwd)
            elif key.name == 'KEY_BACKSPACE' or str(key) == '\x7f':
                if self.searching['buf']:
                    self.searching['buf'] = self.searching['buf'][:-1]
                else:
                    self.searching = None
            elif not key.is_sequence and len(str(key)) == 1 and str(key).isprintable():
                self.searching['buf'] += str(key)
            return None

        # ── command line (:) ──────────────────────────────────────────────────
        if self.cmdline.active:
            cmd = self.cmdline.feed(key)
            if cmd:
                if cmd.isdigit():                       # :{n} — line address
                    if self._gate('line_addr', ':{n}'):
                        self._jump_to(max(0, min(int(cmd) - 1, len(self._lines()) - 1)))
                    return None
                return ('cmd', cmd)
            return None

        raw  = str(key) if not key.is_sequence else ''
        self.player.error = ''
        lines = self._lines()
        last  = len(lines) - 1

        # gg / g* / g# / g_ (falls through to normal handling if not a g-seq)
        if self.pending_g:
            self.pending_g = False
            if raw == 'g':
                self._jump_to(0); self.count_buf = ''; return None
            if raw in ('*', '#'):
                if self._gate('g_family', 'the g-family'):
                    word = _owm_word_at(self._lbl(), self._eff())
                    if word is None:
                        self.player.error = 'E348: No string under cursor'
                    else:
                        self._run_search('\\V' + word, raw == '*')
                self.count_buf = ''; return None
            if raw == '_':
                if self._gate('g_family', 'the g-family'):
                    self.want_col = max(0, len(self._lbl().rstrip()) - 1)
                self.count_buf = ''; return None
            # else: not a g-sequence → continue below

        # z{z,t,b} — view scroll (free)
        if self.pending_z:
            self.pending_z = False
            avail = self._avail()
            max_off = max(0, len(lines) - avail)
            if raw == 'z':
                self.scroll_offset = max(0, min(self.cursor - avail // 2, max_off))
            elif raw == 't':
                self.scroll_offset = max(0, min(self.cursor, max_off))
            elif raw == 'b':
                self.scroll_offset = max(0, min(self.cursor - avail + 1, max_off))
            self.count_buf = ''; return None

        # f/F/t/T — awaiting the target char
        if self.pending_find:
            pf, self.pending_find = self.pending_find, ''
            if not key.is_sequence and len(raw) == 1 and raw.isprintable():
                fwd, till = pf in 'ft', pf in 'tT'
                hit = _owm_find(self._lbl(), self._eff(), raw, fwd, till)
                self.last_f = (pf, raw)
                if hit is not None:
                    self.want_col = hit
            self.count_buf = ''; return None

        # count prefix ('0' alone is not a count)
        if raw.isdigit() and (raw != '0' or self.count_buf):
            self.count_buf += raw
            return None
        n_given = bool(self.count_buf)
        n = int(self.count_buf) if self.count_buf else 1
        self.count_buf = ''

        # m{a} / '{a} / `{a}
        if self.pending_mark:
            pm, self.pending_mark = self.pending_mark, ''
            if pm == 'm':
                if raw.isalpha() and raw.islower():
                    self.marks[raw] = (self.cursor, self._eff())
            elif raw in ("'", '`') and pm in ("'", '`'):
                if self.last_jump is not None:
                    self._jump_to(self.last_jump)
            elif raw.isalpha() and raw.islower():
                if raw in self.marks:
                    mr, mc = self.marks[raw]
                    self._jump_to(min(mr, last))
                    if pm == '`':
                        self.want_col = mc
                    else:
                        t = self._lbl()
                        self.want_col = len(t) - len(t.lstrip()) if t.strip() else 0
                else:
                    self.player.error = f'E20: Mark not set: {raw}'
            return None

        if raw == ':':
            self.cmdline.open()
        elif raw in ('/', '?'):
            if self._gate('/', 'search'):
                self.searching = {'pfx': raw, 'buf': ''}
        elif raw in ('n', 'N'):
            if self._gate('/', 'search'):
                if not self.player.last_search:
                    self.player.error = 'E35: No previous regular expression'
                else:
                    pat, base_fwd = self.player.last_search
                    self._run_search(pat, base_fwd if raw == 'n' else not base_fwd)
        elif raw == 'h':
            if n <= 1 or self._gate('count', 'counts'):
                self.want_col = max(0, self._eff() - n)
        elif raw == 'l':
            if n <= 1 or self._gate('count', 'counts'):
                self.want_col = min(max(0, len(self._lbl()) - 1), self._eff() + n)
        elif raw == '0' and not n_given:
            self.want_col = 0
        elif raw == '^':
            t = self._lbl()
            self.want_col = len(t) - len(t.lstrip()) if t.strip() else 0
        elif raw == '$':
            self.want_col = 10 ** 9
        elif raw and raw in 'wbeWBE':
            if self._mgate(raw, raw):
                fn = {'w': _owm_w, 'b': _owm_b, 'e': _owm_e,
                      'W': _owm_w, 'B': _owm_b, 'E': _owm_e}[raw]
                c = self._eff()
                for _ in range(n):
                    c = fn(self._lbl(), c, raw.isupper())
                self.want_col = c
        elif raw and raw in 'fFtT':
            if self._mgate(raw, raw):
                self.pending_find = raw
        elif raw in (';', ','):
            if self._mgate(raw, raw) and self.last_f:
                pf, ch = self.last_f
                if raw == ',':
                    pf = {'f': 'F', 'F': 'f', 't': 'T', 'T': 't'}[pf]
                hit = _owm_find(self._lbl(), self._eff(), ch, pf in 'ft', pf in 'tT')
                if hit is not None:
                    self.want_col = hit
        elif raw in ('*', '#'):
            if self._gate('*', '* (search word)'):
                word = _owm_word_at(self._lbl(), self._eff())
                if word is None:
                    self.player.error = 'E348: No string under cursor'
                else:
                    self._run_search('\\<' + word + '\\>', raw == '*')
        elif raw == 'z':
            self.pending_z = True
        elif raw in ("m'`") and raw:
            if self._gate('mark', 'marks'):
                self.pending_mark = raw
        elif raw == '\x0f':                             # Ctrl-o
            if self._gate('jump', 'the jump list'):
                if self.jump_idx > 0:
                    if self.jump_idx == len(self.jump_list):
                        self.jump_list.append(self.cursor)
                    self.jump_idx -= 1
                    self.cursor = min(self.jump_list[self.jump_idx], last)
        elif raw == '\t':                               # Ctrl-i (Tab)
            if self._gate('jump', 'the jump list'):
                if self.jump_idx + 1 < len(self.jump_list):
                    self.jump_idx += 1
                    self.cursor = min(self.jump_list[self.jump_idx], last)
        elif raw == 'j':
            if n <= 1 or self._gate('count', 'counts'):
                self.cursor = min(self.cursor + n, last)
        elif raw == 'k':
            if n <= 1 or self._gate('count', 'counts'):
                self.cursor = max(self.cursor - n, 0)
        elif raw == 'g':
            self.pending_g = True
        elif raw == 'G':
            if (n <= 1 or self._gate('count', 'counts')) and self._gate('G', 'G'):
                self._jump_to(max(0, min(n - 1, last)) if n_given else last)
        elif raw == 'H':
            if self._gate('H', 'H'):
                self.cursor = min(self.scroll_offset, last)
        elif raw == 'M':
            if self._gate('M', 'M'):
                vc = min(self._avail(), last - self.scroll_offset + 1)
                self.cursor = min(self.scroll_offset + (vc - 1) // 2, last)
        elif raw == 'L':
            if self._gate('L', 'L'):
                self.cursor = min(self.scroll_offset + self._avail() - 1, last)
        elif raw == '{':
            if self._gate('{', '{'):
                self._jump_to(self._section(-1))
        elif raw == '}':
            if self._gate('}', '}'):
                self._jump_to(self._section(+1))
        elif raw == '\x04':                             # Ctrl-d
            self.cursor = min(self.cursor + self._avail() // 2, last)
        elif raw == '\x15':                             # Ctrl-u
            self.cursor = max(self.cursor - self._avail() // 2, 0)
        elif raw == '\x06':                             # Ctrl-f
            self.cursor = min(self.cursor + self._avail(), last)
        elif raw == '\x02':                             # Ctrl-b
            self.cursor = max(self.cursor - self._avail(), 0)
        else:
            return ('key', raw, key)                    # host's to handle
        return None

    def _section(self, direction):
        lines = self._lines()
        starts = _section_starts(lines, self._section_key)
        if direction < 0:
            before = [s for s in starts if s < self.cursor]
            return before[-1] if before else 0
        after = [s for s in starts if s > self.cursor]
        return after[0] if after else len(lines) - 1


def run_overworld(term: Terminal, player: Player, progress: dict,
                  initial_cursor: int | None = None) -> dict:
    """The netrw overworld (~/.vimny/world/) as a real netrw buffer.

    Every line — the `"` comments, ../ ./, the levels, custom layouts — is a
    selectable cursor position. Motions match what the player has learned: j/k
    always; counts, gg/G, {n}G, H/M/L, {/} once learned; Ctrl-d/u/f/b page the
    view. D deletes a custom layout (y to confirm), R renames it, d/dd hit the
    read-only buffer; :set number/relativenumber/nonumber toggle the gutter.

    Returns {'action': 'enter'|'open_custom'|'browse_saves'|'scrolls'
             |'browse_remote'|'parent_view'|'quit', ...}.
    """
    _OW_COMPLETIONS = ['../', 'saves/', 'scrolls/', 'remote/']

    def _wing_shown(l):
        # The Registry wing hides in the world/ menu until the horse is adopted
        # (his saddle holds the registers). Admin sees everything.
        if l.get('wing') == 'registry' and player.name != 'admin':
            return bool(progress.get('horse_name'))
        return True

    visible = [l for l in LEVELS
               if (not l.get('admin_only') or player.name == 'admin') and _wing_shown(l)]

    def _layouts():
        return SM.list_layouts() if player.name == 'admin' else []

    def _community():
        # Validated on every listing, not cached: a level file the player edits
        # between visits gets re-checked, which is the whole point of validating
        # on LOAD rather than only on submission.
        try:
            return community_levels()
        except Exception:                    # noqa: BLE001 — a bad shelf must
            return []                        # never keep the overworld from opening

    def _drafts():
        # Admin-only, like custom/: authoring is a designer's bench, not part of
        # the game a player is here to play.
        if player.name != 'admin':
            return []
        try:
            return DRAFT.list_drafts()
        except OSError:
            return []

    customs = _layouts()
    shelf   = _community()
    drafts  = _drafts()
    lines   = build_lines(visible, customs, shelf, drafts)
    start   = default_cursor(lines) if initial_cursor is None else initial_cursor
    start   = max(0, min(start, len(lines) - 1))

    learned  = _known_from_progress(progress)
    is_admin = player.name == 'admin'
    def _gate(tok, label):
        if is_admin or tok in learned:
            return True
        player.error = f"You haven't learned {label} yet."
        return False

    number_mode    = 'number'
    renaming       = None        # None, or the in-progress new-name buffer
    naming_new     = False       # that buffer is naming a NEW draft (netrw %)
    pending_delete = False

    # Buffer-local marks, netrw-style: session-scoped on the player (the
    # overworld is one buffer; re-entering it keeps your marks).
    if not hasattr(player, 'ow_marks'):
        player.ow_marks = {}

    # All Vim navigation — gg/G/{n}G, H/M/L, { }, w b e, f F t T, ; ,, * #,
    # marks, Ctrl-o/i, Ctrl-d/u/f/b, counts, and the / ? + : lines — lives in
    # the shared NetrwNav engine (the same one the scroll library uses).
    nav = NetrwNav(player=player, get_lines=lambda: lines, label=line_search_text,
                   section_key=_ow_section_key, gate=_gate,
                   avail=lambda: max(1, term.height - 5),
                   completions=_OW_COMPLETIONS, marks=player.ow_marks, cursor=start)

    def _rebuild():
        nonlocal customs, lines, shelf, drafts
        customs = _layouts()
        shelf   = _community()
        drafts  = _drafts()
        lines   = build_lines(visible, customs, shelf, drafts)
        nav.cursor = max(0, min(nav.cursor, len(lines) - 1))

    def _render():
        cmd_line = (nav.searching['buf'] if nav.searching
                    else nav.cmdline.line if nav.cmdline.active else None)
        cmd_pfx  = nav.searching['pfx'] if nav.searching else ':'
        scroll, cy, cx = render_overworld(
            term, player, progress, nav.cursor, lines,
            cmd_line=cmd_line, cmd_prefix=cmd_pfx,
            number_mode=number_mode, deleting=pending_delete,
            renaming=renaming, naming_new=naming_new,
            scroll_offset=nav.scroll_offset, col=nav.col())
        nav.scroll_offset = scroll
        print(term.move_yx(cy, cx) + (term.cvvis or term.cnorm), end='', flush=True)  # blinking cursor

    def _done(result):
        print(term.civis, end='', flush=True)   # re-hide the cursor for the dungeon
        return result

    _render()

    while True:
        key = term.inkey(timeout=0.1)
        if not key:
            continue

        # ── Rename input (netrw R) ──────────────────────────────────────────────
        if renaming is not None:
            if key.name == 'KEY_ESCAPE':
                renaming, naming_new = None, False
            elif key.name == 'KEY_ENTER' or str(key) in ('\n', '\r'):
                ln = lines[nav.cursor]
                if naming_new and renaming.strip():
                    # netrw's % — a new file in forge/. It is written straight
                    # away so it exists on disk before a single edit, which is
                    # what lets the author walk away from it and come back.
                    _d = DRAFT.new(renaming.strip(), author=player.name)
                    DRAFT.save(_d)
                    renaming, naming_new = None, False
                    _rebuild()
                    return _done({'action': 'open_draft', 'draft': _d,
                                  'cursor': nav.cursor})
                if ln['type'] == 'draft' and renaming.strip() and ln['draft'].ok:
                    _d = ln['draft']
                    _d.level.name = renaming.strip()
                    DRAFT.save(_d)
                    _rebuild()
                elif ln['type'] == 'custom' and renaming.strip():
                    SM.rename_layout(ln['layout'].get('layout_name', ''), renaming.strip())
                    _rebuild()
                renaming, naming_new = None, False
            elif key.name == 'KEY_BACKSPACE' or str(key) == '\x7f':
                renaming = renaming[:-1]
            elif not key.is_sequence and len(str(key)) == 1 and str(key).isprintable():
                renaming += str(key)
            _render()
            continue

        # ── D — delete a custom layout (netrw); the next key confirms with y ────
        if pending_delete:
            pending_delete = False
            ln = lines[nav.cursor]
            if str(key) == 'y' and ln['type'] == 'custom':
                SM.delete_layout(ln['layout'].get('layout_name', ''))
                _rebuild()
            elif str(key) == 'y' and ln['type'] == 'draft':
                DRAFT.delete(ln['draft'])
                _rebuild()
            _render()
            continue                                   # any non-y key cancels

        # ── Everything else: the shared netrw motion engine ────────────────────
        out = nav.feed(key)
        if out is None:
            _render()
            continue

        if out[0] == 'cmd':
            cmd = out[1]
            if cmd in ('q', 'q!', 'wq'):
                if cmd == 'wq':
                    SM.save_progress(progress, player.name)
                return _done({'action': 'quit', 'cursor': nav.cursor})
            if cmd in ('set number', 'set nu'):
                number_mode = 'number'
            elif cmd in ('set relativenumber', 'set rnu'):
                number_mode = 'relativenumber'
            elif cmd in ('set nonumber', 'set nonu'):
                number_mode = 'none'
            elif cmd in ('set norelativenumber', 'set nornu'):
                number_mode = 'number'
            else:
                _e_path = cmd[2:].rstrip('/') if cmd.startswith('e ') else ''
                if _e_path in ('saves',):
                    return _done({'action': 'browse_saves', 'cursor': nav.cursor})
                if _e_path in ('scrolls',):
                    return _done({'action': 'scrolls', 'cursor': nav.cursor})
                if _e_path in ('remote', 'community/remote'):
                    return _done({'action': 'browse_remote', 'cursor': nav.cursor})
                if _e_path in ('..', '../'):
                    return _done({'action': 'parent_view', 'cursor': nav.cursor})
                # Unknown commands silently ignored
            _render()
            continue

        # out[0] == 'key' — a keystroke the engine doesn't own (Enter / D / R /
        # d / - and the like); dispatch the overworld-specific actions.
        raw       = out[1]
        ln        = lines[nav.cursor]
        on_custom = ln['type'] == 'custom'
        on_draft  = ln['type'] == 'draft'
        if raw == '-':
            return _done({'action': 'parent_view', 'cursor': nav.cursor})
        elif raw == '%':                               # netrw new file — a new draft
            if not FEAT.FORGE:
                player.error = FEAT.message('compose levels')
            elif player.name == 'admin':
                renaming, naming_new = '', True
            else:
                player.error = 'Only the admin can forge new levels.'
        elif raw == 'D':                               # netrw delete (custom / draft)
            if on_custom or on_draft:
                pending_delete = True
            else:
                player.error = "Can't delete a built-in dungeon — only your own custom layouts."
        elif raw == 'R':                               # netrw rename (custom / draft)
            if on_custom:
                renaming = ln['layout'].get('layout_name', '')
            elif on_draft:
                renaming = ln['draft'].name
            else:
                player.error = "Can't rename a built-in dungeon — only your own custom layouts."
        elif raw == 'd':                               # read-only buffer (netrw is read-only)
            player.error = 'The overworld is read-only — press D to delete a custom layout.'
        elif key.name == 'KEY_ENTER' or raw in ('\n', '\r'):
            t = ln['type']
            if t == 'parent':
                return _done({'action': 'parent_view', 'cursor': nav.cursor})
            elif t == 'level':
                lid = ln['level']['slug']
                if is_unlocked(lid, progress, player.name):
                    return _done({'action': 'enter', 'level': lid, 'cursor': nav.cursor})
            elif t == 'custom':
                return _done({'action': 'open_custom', 'layout': ln['layout'], 'cursor': nav.cursor})
            elif t == 'community':
                if ln['shelf'].ok:
                    return _done({'action': 'open_community', 'shelf': ln['shelf'],
                                  'cursor': nav.cursor})
                player.error = ln['shelf'].error
            elif t == 'draft':
                if ln['draft'].ok:
                    return _done({'action': 'open_draft', 'draft': ln['draft'],
                                  'cursor': nav.cursor})
                player.error = ln['draft'].error
            # comment / self / subhdr → no-op

        _render()


# ── Main ───────────────────────────────────────────────────────────────────────

def _ensure_utf8_stdout():
    # Glyph-heavy frames need a UTF-8 stdout: on a C-locale box (3.9-3.14,
    # locale coercion unavailable or disabled) the default codec is ASCII and
    # the first dungeon glyph would raise UnicodeEncodeError mid-frame.
    # Mojibake on a truly non-UTF-8 terminal beats a crash.
    for stream in (sys.stdout, sys.stderr):
        if getattr(stream, 'encoding', '').lower().replace('-', '') != 'utf8':
            try:
                stream.reconfigure(encoding='utf-8')
            except Exception:
                pass


def main():
    _ensure_utf8_stdout()
    # prog is pinned: argparse otherwise names whichever file was invoked, so
    # `-m vimny` advertises itself as `__main__.py`.
    ap = argparse.ArgumentParser(prog='vimny',
                                 description='Vimny — Vim dungeon crawler')
    ap.add_argument('--level', type=str, default=None,
                    choices=[lv['slug'] for lv in LEVELS],
                    help='skip overworld and start at this level slug (debug)')
    args = ap.parse_args()

    term = Terminal()
    C.init(term)
    S.init(term)

    player    = Player()
    progress: dict = {}

    with term.fullscreen(), term.cbreak(), term.hidden_cursor():
        start_level = args.level  # None → show title then overworld

        # Show title screen unless jumping straight to a level for debugging.
        if start_level is None:
            has_save = bool(SM.list_saves())
            title_action, player_name = run_title(term, has_save)
            if title_action == 'quit':
                return
            player.name = player_name or 'Normand'
            if title_action == 'load':
                save_data = SM.load_for(player.name) or {}
                progress  = SM.load_progress(save_data)
            # 'new': progress stays empty (fresh save already written in run_title)
            maybe_admin_notice(term, player, progress)

        ow_cursor = None
        while True:
            if start_level is not None:
                ow_result  = {'action': 'enter', 'level': start_level}
                start_level = None
            else:
                player.max_hp = progress.get('max_hp', 6)
                player.hp     = player.max_hp
                ow_result = run_overworld(term, player, progress,
                                          initial_cursor=ow_cursor)
            ow_cursor = ow_result.get('cursor')

            if ow_result['action'] == 'quit':
                break

            # ── Auxiliary screen dispatch (browse_saves / scrolls / parent_view) ──
            aux = ow_result['action']
            if aux == 'browse_remote':
                run_remote_shelf(term, player, progress)
                continue                           # back to the overworld (re-lists community/)
            if aux in ('browse_saves', 'scrolls', 'parent_view', 'colors'):
                while aux in ('browse_saves', 'scrolls', 'parent_view', 'colors'):
                    if aux == 'browse_saves':
                        sel_action, sel_name = run_save_select(term)
                        if sel_action == 'load' and sel_name:
                            player.name = sel_name
                            save_data   = SM.load_for(player.name) or {}
                            progress    = SM.load_progress(save_data)
                            # Switching saves is the OTHER way to become admin;
                            # the notice belongs wherever the name changes, not
                            # only on the title screen.
                            maybe_admin_notice(term, player, progress)
                        aux = None
                    elif aux == 'scrolls':
                        result = run_scroll_library(term, player, progress)
                        aux = ('parent_view' if result == 'parent'
                               else 'browse_saves' if result == 'saves'
                               else None)
                    elif aux == 'colors':
                        run_colors(term, player)
                        aux = 'parent_view'
                    elif aux == 'parent_view':
                        result = run_parent_dir(term, player, progress)
                        aux = (result if result in ('scrolls', 'saves', 'colors') else None)
                        if aux == 'saves':
                            aux = 'browse_saves'
                continue

            if ow_result['action'] == 'open_community':
                shelf   = ow_result['shelf']
                dungeon = build_shelved(shelf)
                # Played as ITSELF, not as a stand-in for first_cave: its par
                # came from replaying the author's tape, and its command set is
                # the one the level declares — a community level has no
                # curriculum position to derive either from. Progress keys by the
                # namespaced slug, so it can never collide with a shipped level.
                res = run_dungeon(term, shelf.slug, progress, player.name,
                                  _dungeon=dungeon, _known=shelf.level.known)
                if res['action'] == 'wq':
                    if res['won']:
                        prev = progress.get(shelf.slug, {}).get('stars', 0)
                        progress[shelf.slug] = {
                            'complete': True,
                            'stars': max(res['stars'], prev),
                        }
                    SM.save_progress(progress, player.name)
                continue

            if ow_result['action'] == 'open_draft':
                draft = ow_result['draft']
                # The forge opens under the 'community' slug for the same reason
                # the shelf does: a draft has no curriculum position, so its
                # command set comes from what it DECLARES, and nothing here may
                # key progress against a shipped level's name.
                run_dungeon(term, 'community', progress, player.name,
                            _dungeon=draft.build(), _start_edit=True,
                            _known=draft.level.known, _draft=draft)
                continue

            if ow_result['action'] == 'open_custom':
                layout  = ow_result['layout']
                room    = _deserialize_room(layout)
                dungeon = Dungeon(name=layout.get('layout_name', 'Custom'), seed=0)
                dungeon.rooms        = [room]
                dungeon.current_room = 0
                # An inert slug, exactly like the forge's 'community': a custom
                # layout has no curriculum position, so nothing may key progress,
                # scroll drops or first_cave's gating against a shipped level's
                # name. known_commands('custom') is the full union — admin context.
                run_dungeon(term, 'custom', progress, player.name,
                            _dungeon=dungeon, _start_edit=True)
                continue

            level = ow_result['level']

            # Pre-game blessing: wizard bestows hjkl poem before every attempt
            # at the First Cave until the player has earned at least 1 star there.
            if level == 'first_cave' and progress.get('first_cave', {}).get('stars', 0) == 0:
                run_wizard_blessing(term, select_quote_by_name('home row'))
                _record_blessing_seen(progress, player.name, 'home row')

            dung_result = run_dungeon(term, level, progress, player.name)

            # Always persist on :wq; only update level completion if won.
            # (:w mid-dungeon already updated progress and saved inline.)
            if dung_result['action'] == 'wq':
                if dung_result['won']:
                    prev_stars = progress.get(level, {}).get('stars', 0)
                    progress[level] = {
                        'complete': True,
                        'stars': max(dung_result['stars'], prev_stars),
                    }
                SM.save_progress(progress, player.name)

            if dung_result.get('first_written_completion'):
                # After the final level, the wizard gives his farewell (the
                # Warden unmasked); every other level previews the next lesson.
                if level == 'warden_eternal':
                    run_wizard_blessing(term, select_quote_by_name('final blessing'))
                    _record_blessing_seen(progress, player.name, 'final blessing')
                else:
                    _entry = next_lesson_quote_entry(level)
                    if _entry is not None:
                        run_wizard_blessing(term, format_quote(_entry))
                        _record_blessing_seen(progress, player.name, _entry['name'])
                    else:
                        run_wizard_blessing(term, select_next_lesson_quote(level))



if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        pass
