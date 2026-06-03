#!/usr/bin/env python3
"""Vimny — entry point and main game loop."""
from __future__ import annotations
import random, time, argparse
from collections import deque
from blessed import Terminal
import render.colors as C
from render.renderer import render_all
import render.symbols as S
from render.utils import inner_w as _iw
from render.overworld import render_overworld, build_lines, default_cursor
from render.title import render_title, render_save_select, select_quote, select_quote_by_name, select_next_lesson_quote, MENU_ITEMS as _TITLE_MENU, NAME_MAX as _NAME_MAX
from render.wizard_blessing import run_wizard_blessing
from engine.player import Player
from engine.modes import Mode
from engine.budget import Budget
from engine.vim_parser import parse, parse_visual_textobj
from engine.command_guard import action_allowed as _action_allowed, guard_message as _guard_message
from engine.world import Entity, CellType, CharRun, Dungeon
from engine.motion import apply_motion, _apply_esc, _reveal_from, _first_non_blank_col
from engine.text_object import compute_text_object, resolve_text_object
from engine.search import find_next as _search_next, word_under_cursor as _word_under_cursor
from engine.options import apply_set as _apply_set, parse_modifier as _parse_set_mod
from engine.macro import synth_key as _synth_key, record_char as _record_char
from engine.jumplist import record_jump as _record_jump, jump_back as _jump_back, jump_forward as _jump_forward
from engine.registers import write_register as _reg_write, read_register as _reg_read
from engine.visual import apply_visual, block_bounds
from content.scrolls import (
    RELIQUARY_SCROLL, WARDEN_LEAP_SCROLL, WARDEN_SIGHT_SCROLL, WAYPOINT_SCROLL,
    OPERATOR_CODEX_SCROLL, ARCHIVISTS_METHOD_SCROLL,
    WHOLE_WORD_SCROLL, WARDEN_ACT_SCROLL,
    SETTERS_HAND_SCROLL, SEARCH_CRAFT_SCROLL, WANDERERS_THREAD_SCROLL,
    PLUMB_LINE_SCROLL, RECALLING_HAND_SCROLL, QUICK_ERASE_SCROLL,
    REGEX_CLASSES_SCROLL, REGEX_ANCHORS_SCROLL, REGEX_QUANTIFIERS_SCROLL,
    REGEX_COLLECTIONS_SCROLL, REGEX_MAGIC_SCROLL,
    pick_relic_scroll as _pick_relic_scroll,
)

_JUMP_MOTIONS = frozenset({'G', 'gg', '%', '{', '}', '(', ')'})
from engine.operator import op_delete, op_yank, op_paste, op_case, op_join, case_char, apply_indent, INDENT_WIDTH, entity_clip
from engine.reflow import is_ledge, close_gap, void_col
from engine.insert import (
    begin_insert, insert_char, insert_char_extend, insert_backspace,
    insert_delete_word_back, insert_delete_to_start,
    replace_chars, replace_overtype, replace_restore,
)
from engine.editor import (
    _merge_adjacent_char_runs, _ed_cut, _ed_snapshot, _ed_restore, _ed_subst,
    _ed_paste, _ed_row_items, _ed_clear_row, _ed_range_items, _ed_delete_range,
    _clip_desc, _serialize_room, _deserialize_room,
)
import generation.dungeon_gen as _dg
from content.levels import LEVELS, is_unlocked, level_type, known_commands as _known_commands
import save.save_manager as SM


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
_ATTACK_RADIUS          = 1   # Manhattan dist at which goblins attack each turn
_WARDEN_SUMMON_INTERVAL = 6   # turns between warden summons
_MSG_ROTATE_TTL         = 10  # ticks per combat message (~1 s at 0.1 s inkey timeout)

_SCROLL_TEXT_OPERATOR_CODEX = """\
The Operator's Codex
====================
In the Loom, they carved the grammar of unmaking.

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

_SCROLL_TEXT_ARCHIVISTS_METHOD = """\
The Archivist's Method
======================
The Archivist copied before erasing. That was the discipline.

  y{m}  ──  yank (copy without cutting)
  yy    ──  yank line
  p     ──  put after cursor
  P     ──  Put before cursor
  c{m}  ──  change text (delete + insert)

  d and y share the same register.
  Paste before deleting, or lose your copy.
"""

_SCROLL_TEXT_WHOLE_WORD = """\
The Whole Word
==============
Position within the word ceased to matter.

  iw  ──  inner word  (from anywhere inside)
  aw  ──  around word (includes adjacent space)
  i(  ──  inner parens
  a(  ──  around parens
  i"  ──  inside quotes
  it  ──  inside tag

  diw works at start, middle, or end.
  The boundary is the rune, not where you stand.
"""

_SCROLL_TEXT_WARDENS_ACT = """\
The Warden's Act
================
The Sight became the Hand.
What the eye marks, the hand unmakes.

  v{m}d  ──  select range, delete
  v{m}y  ──  select range, yank
  v{m}c  ──  select range, change
  gv     ──  reselect last visual span

  See. Select. Strike.
  The eye and the hand are one.
"""

def _chest_loot(kind: str) -> str:
    """Return the item type yielded by looting a chest."""
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


def _smudge_gate_met(gate, known) -> bool:
    """True if every command token in `gate` is in the player's known set."""
    if gate is None:
        return False
    tokens = (gate,) if isinstance(gate, str) else tuple(gate)
    return all(t in known for t in tokens)


def _water_stain(text: str, solid: int):
    """Mask `text` as ink run from a water-damaged left edge.

    The first `solid` characters (left margin + the hidden command) are fully
    obscured; from there the smudge bleeds rightward, heavy at the wet edge and
    fading to clean text on the right, with an organic random speckle. Darker
    shades (▓▒) cluster near the wet edge, lighter (░) toward the dry side.
    Spaces are never smudged (the stain runs through ink, not gaps). Returns
    (chars, smudged) parallel lists; deterministic per `text`.
    """
    rnd  = random.Random(text)          # stable pattern for a given line
    n    = len(text)
    span = max(1, n - solid)
    chars, smudged = [], []
    for i, ch in enumerate(text):
        if i < solid:                   # wet edge: margin + command, always hidden
            chars.append(rnd.choice('▒▓'))
            smudged.append(True)
            continue
        p = (1 - (i - solid) / span) ** 1.4      # fade probability, 1 → 0
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

    T  = C_['title']
    lT = (BOX_IW - len(T)) // 2
    rT = BOX_IW - len(T) - lT
    title = row(BOX_IW, ' ' * lT + hi + T + inn + ' ' * rT)

    def kv_clear(key: str, desc: str) -> str:
        d25     = desc.ljust(25)[:25]
        sep     = '  ────>  '
        suf     = 'lands in  '
        sym     = '"'
        colored = ('    ' + hi + key + rst +
                   inn + body + sep + d25 + suf + rst +
                   inn + amber + sym + rst + inn)
        return row(50, colored)

    def kv_smudged(key: str, desc: str) -> str:
        sep    = '  ────>  '
        suf    = 'lands in  '
        sym    = '"'
        d25    = desc.ljust(25)[:25]
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
        colored = painted + rst + inn + body + suf + rst + inn + amber + sym + rst + inn
        return row(50, colored)

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


def _show_register_tutorial(term: Terminal, iw: int, game_h: int, progress: dict | None = None) -> None:
    """Amber floating box explaining the \" register. Blocks until any key.

    The d / c rows clarify once those commands have been learned (i.e. the
    levels teaching them have been completed)."""
    known = _known_from_progress(progress or {})
    _show_reliquary_scroll(term, iw, game_h, known)


def _show_warden_leap_scroll(term: Terminal, iw: int, game_h: int,
                             known: set | None = None) -> None:
    """Amber floating box previewing Act II structural motions (smudged)."""
    _render_standard_scroll(term, iw, game_h, WARDEN_LEAP_SCROLL, known)


def _show_warden_sight_scroll(term: Terminal, iw: int, game_h: int,
                              known: set | None = None) -> None:
    """Amber floating box introducing v (Visual mode)."""
    _render_standard_scroll(term, iw, game_h, WARDEN_SIGHT_SCROLL, known)


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
        rnd   = random.Random(text)        # stable speckle for a given line
        painted, prev = '', None
        for i, ch in enumerate(text):
            if i < solid:
                col, out = smudge, rnd.choice('▒▓')   # wet edge: blotted, spaces too
            else:
                col, out = body, ch                   # tail reads clean
            if col != prev:
                painted += col
                prev = col
            painted += out
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


def _show_waypoint_scroll(term: Terminal, iw: int, game_h: int,
                          known: set | None = None) -> None:
    """Amber scroll teaching :set number (the Waypoint Sanctum's left-room reward)."""
    _render_standard_scroll(term, iw, game_h, WAYPOINT_SCROLL, known)


def _show_operator_codex_scroll(term: Terminal, iw: int, game_h: int,
                                known: set | None = None) -> None:
    """Operator's Codex (171) — d/dd clear; y/c clarify once learned."""
    _render_standard_scroll(term, iw, game_h, OPERATOR_CODEX_SCROLL, known)


def _show_archivists_method_scroll(term: Terminal, iw: int, game_h: int,
                                   known: set | None = None) -> None:
    """Archivist's Method (221) — y/yy/p clear; c clarifies once learned."""
    _render_standard_scroll(term, iw, game_h, ARCHIVISTS_METHOD_SCROLL, known)


def _show_whole_word_scroll(term: Terminal, iw: int, game_h: int,
                            known: set | None = None) -> None:
    """The Whole Word (291) — iw/aw clear; bracket/quote objects clarify once learned."""
    _render_standard_scroll(term, iw, game_h, WHOLE_WORD_SCROLL, known)


def _show_warden_act_scroll(term: Terminal, iw: int, game_h: int,
                            known: set | None = None) -> None:
    """The Warden's Act (361) — visual operators clear; gv clarifies once learned."""
    _render_standard_scroll(term, iw, game_h, WARDEN_ACT_SCROLL, known)


def _show_catalog_scroll(term: Terminal, iw: int, game_h: int,
                         scroll_id: str, known: set | None = None) -> None:
    """Render any SCROLL_CATALOG scroll by id via the standard renderer — used
    for the relic (randomly dropped) scrolls, which all use the 'lines'
    format."""
    from content.scrolls import SCROLL_CATALOG
    for s in SCROLL_CATALOG:
        if s['id'] == scroll_id:
            _render_standard_scroll(term, iw, game_h, s['content'], known)
            return


# Each boss chest drops the scroll previewing the next act's commands; smudged
# lines clarify as those commands are learned.  level → (scroll/extras id,
# full-text title|None, full-text body|None, overlay fn).  The id is also the
# command the boss GATES: it stays locked on the boss level until its scroll is
# read (see run_dungeon's level-start extras injection).
_SCROLL_DROPS = {
    'reliquary':            ('register',  None,                     None,                          _show_reliquary_scroll),
    'wardens_keep':         ('leap',      None,                     None,                          _show_warden_leap_scroll),
    'warden_surveyor':      ('visual',    None,                     None,                          _show_warden_sight_scroll),
    'warden_pathfinder':    ('d_op',      "The Operator's Codex",   _SCROLL_TEXT_OPERATOR_CODEX,    _show_operator_codex_scroll),
    'warden_manifold':      ('y_op',      "The Archivist's Method", _SCROLL_TEXT_ARCHIVISTS_METHOD, _show_archivists_method_scroll),
    'warden_scrivener':     ('text_obj',  'The Whole Word',         _SCROLL_TEXT_WHOLE_WORD,        _show_whole_word_scroll),
    'grandmasters_sanctum': ('visual_op', "The Warden's Act",       _SCROLL_TEXT_WARDENS_ACT,       _show_warden_act_scroll),
}


def _unlock_animation(term: Terminal, room, player,
                      door_r: int, door_c: int, iw: int, game_h: int,
                      key_color: str | None = None) -> None:
    """Flash key icon at door position, then blank it — door + key both vanish."""
    vr_start = max(0, min(player.row - game_h // 2, room.rows - game_h))
    vc_start = max(0, min(player.col - iw    // 2,  room.cols - iw))
    scr_r = door_r - vr_start + 3
    scr_c = door_c - vc_start + 1
    if not (0 <= scr_r < term.height and 0 <= scr_c < iw):
        return
    key_clr = key_color if key_color is not None else C.key_fg()
    rst  = term.normal
    fbg  = C.floor_bg()
    print(term.move_yx(scr_r, scr_c) + fbg + key_clr + S.KEY + rst, end='', flush=True)
    time.sleep(0.35)
    print(term.move_yx(scr_r, scr_c) + fbg + '  ' + rst, end='', flush=True)
    time.sleep(0.08)


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


def _void_fall_animation(term, screen_r, screen_c):
    frames = [
        (term.color_rgb(110, 60, 160) + term.bold, '@'),
        (term.color_rgb(80,  30, 120) + term.bold, '◉'),
        (term.color_rgb(60,  20,  90),              'o'),
        (term.color_rgb(40,  10,  60),              '·'),
        (term.color_rgb(20,   5,  30),              '˙'),
        (term.normal,                               ' '),
    ]
    for color, sym in frames:
        print(term.move_yx(screen_r, screen_c) + color + sym + term.normal,
              end='', flush=True)
        time.sleep(0.12)


def _void_screen_xy(term, room, player, r, c):
    """Buffer (r, c) → screen (row, col) within the player-centred viewport
    (the same transform the renderer and the normal-mode void fall use)."""
    iw       = _iw(term)
    game_h   = term.height - 8
    vr_start = max(0, min(player.row - game_h // 2, room.rows - game_h))
    vc_start = max(0, min(player.col - iw  // 2,    room.cols - iw))
    return r - vr_start + 3, c - vc_start + 1


def _play_void_falls(term, dungeon, room, player):
    """Animate any characters the last reflow shoved over a ledge into the void.

    Reads room._last_void_falls (populated by engine/reflow.py), plays the drop at
    each fallen cell, then clears the list. Returns True if anything fell."""
    falls = getattr(room, '_last_void_falls', None)
    if not falls:
        return False
    for (fr, fc, _sym) in falls:
        _void_fall_animation(term, *_void_screen_xy(term, room, player, fr, fc))
    room._last_void_falls = []
    return True


def _drown_animation(term, screen_r, screen_c):
    frames = [
        (term.color_rgb(60, 140, 210) + term.bold, '@'),
        (term.color_rgb(40, 100, 175) + term.bold, '◉'),
        (term.color_rgb(20,  70, 145),              'o'),
        (term.color_rgb(10,  45, 110),              '·'),
        (term.color_rgb( 5,  25,  75),              '˙'),
        (term.normal,                               ' '),
    ]
    for color, sym in frames:
        print(term.move_yx(screen_r, screen_c) + color + sym + term.normal,
              end='', flush=True)
        time.sleep(0.12)


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

    def bg_at(term_r, term_c):
        if not (3 <= term_r < 3 + game_h and 1 <= term_c <= iw):
            return C.floor_bg()
        room_r = (term_r - 3) + vr_start
        room_c = (term_c - 1) + vc_start
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
        time.sleep(0.1)
    _banner(19)             # settle on a final frame and hold ~1s so the motto can
    time.sleep(1.1)         # be read (this fires after every par-perfect finish)


def _starfield_victory(term, iw, dungeon, player):
    """Boss-completion finish: a lasting, sky-accurate twinkling starfield behind
    the 'VIM AD ASTRA' banner. Held until the player presses a key — a permanent
    celebration rather than a passing burst (see CREDITS.md)."""
    h      = term.height
    room   = dungeon.room
    game_h = h - 8
    bg_at  = _victory_cell_bg(term, room, player, iw, game_h)
    center = h // 2 - 1

    banner_rows = [
        '  ' + _spaced_title('VIM AD ASTRA') + '  ',
        '  Onward and upward — the stars draw nearer.  ',
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


def _keystroke_cost(count: int, motion: str = '') -> int:
    base = 1 if count == 1 else len(str(count)) + 1
    # multi-character motions: one extra keypress per extra character required
    if motion in ('f', 'F', 't', 'T', 'gg', 'ge', 'gE', 'gJ'):
        base += 1
    return base


def _operator_cost(action: dict) -> int:
    """Keystroke cost of an operator command, e.g. dw=2, d3w=4, dd=2, gUiw=4, gUU=3."""
    count = action.get('count', 1)
    c = len(action['op'])                  # 'd'=1, 'gU'=2
    if count > 1:
        c += len(str(count))
    if 'textobj' in action:                # diw, ci( … (i/a + obj char)
        return c + 2
    motion = action['motion']
    if motion == 'line':                   # dd / yy / gUU
        return c + 1
    c += _keystroke_cost(action.get('motion_count', 1), motion)
    return c


def _calc_stars(won: bool, budget: Budget, room, player, level: int = 0) -> int:
    if not won:
        return 0
    if level_type(level) != 'dungeon':
        return 0
    par = room.par or 0
    if par > 0 and budget.spent <= par and player.hp >= 6:
        return 2
    return 1


def _build_dungeon(slug: str, seed: int, game_h: int = 33, admin: bool = False):
    # Builders are named by slug (content/levels.py): build_dungeon_<slug>.
    builder = getattr(_dg, f'build_dungeon_{slug}', _dg.build_dungeon_first_cave)
    if slug == 'screen_vault':
        # The Screen Vault: only solve the (admin-only) answer path when admin —
        # its par-Dijkstra is too slow to run on every load (par is locked).
        return builder(seed, game_h=game_h, compute_answer=admin)
    return builder(seed)


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
    return {
        'row':      player.row  if row   is None else row,
        'col':      player.col  if col   is None else col,
        'spent':    budget.spent if spent is None else spent,
        'entities': [Entity(kind=e.kind, row=e.row, col=e.col, hp=e.hp, alive=e.alive,
                            max_hp=e.max_hp, ai=e.ai, ai_speed=e.ai_speed,
                            ai_tick=e.ai_tick, summon_timer=e.summon_timer,
                            goblin_free_turns=e.goblin_free_turns,
                            uid=e.uid, summoner_uid=e.summoner_uid,
                            origin_row=e.origin_row, move_dir=e.move_dir,
                            tag=e.tag, scroll_id=e.scroll_id)
                     for e in room.entities],
        'char_runs': [CharRun(ru.row, ru.col, ru.symbols, ru.kind) for ru in room.char_runs],
        'cells':    [r[:] for r in room.cells],
        'rows':     room.rows,
        'cols':     room.cols,
        'exit_pos': room.exit_pos,
        'spawn_pos': room.spawn_pos,
        'fog_cells': set(room.fog_cells),
        'answer_pos':      ap,
        'answer_diverged': ad,
    }


def _pop_history_step(src: list, dst: list, room, player, budget) -> bool:
    """Pop one normal-mode undo/redo entry from src, restore state, push inverse to dst."""
    if not src:
        return False
    item = src.pop()
    if isinstance(item, dict):
        dst.append(_snapshot(room, player, budget))
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
        room.rebuild_indexes()
        if 'answer_pos' in item:
            room.answer_pos      = item['answer_pos']
            room.answer_diverged = item['answer_diverged']
    else:
        dst.append((player.row, player.col, budget.spent,
                    room.answer_pos, room.answer_diverged))
        r, c, s = item[0], item[1], item[2]
        player.row, player.col, budget.spent = r, c, s
        if len(item) == 5:
            room.answer_pos, room.answer_diverged = item[3], item[4]
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


def _kill_door_group(room, row: int, col: int, kind: str = 'door') -> None:
    """Kill the entity at (row, col) and all contiguous adjacent entities of the same kind.

    Uses BFS so a 2-cell horizontal connector or N-cell vertical barrier are
    each treated as one unit — but matching entities in a non-adjacent row/col
    are left untouched.
    """
    from collections import deque
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


def _spawn_goblin(room, row, col, summoner_uid: int = 0) -> Entity | None:
    for c in (col, col - 1, col + 1):
        if 0 <= c < room.cols and room.is_passable(row, c) and not room.entity_at(row, c):
            e = Entity('goblin', row, c, max_hp=1, ai='chase', ai_speed=1,
                       summoner_uid=summoner_uid)
            room.add_entity(e)
            return e
    return None


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


def _try_warden_move(room, killed_goblin: Entity, player) -> str:
    """After a goblin is killed, check if it was the last spawn of a living Warden.
    If so, trigger that Warden's movement and shield reposition.
    Returns a message string or '' if no movement occurred.
    """
    if not killed_goblin.summoner_uid:
        return ''
    warden = next(
        (e for e in room._entity_by_kind.get('warden', [])
         if e.alive and e.uid == killed_goblin.summoner_uid),
        None,
    )
    if warden is None:
        return ''
    if any(e.alive and e.summoner_uid == warden.uid
           for e in room._entity_by_kind.get('goblin', [])):
        return ''
    return _do_warden_move(room, warden, player)


_ORTHO = ((-1, 0), (1, 0), (0, -1), (0, 1))  # up, down, left, right (vertical first)


def _steppable(room, player, r: int, c: int) -> bool:
    """True if (r, c) is a cell an enemy may move onto this turn."""
    if (r, c) == (player.row, player.col):
        return False  # the player's cell is attacked, never stepped onto
    return room.is_passable(r, c) and not room.entity_at(r, c)


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


def _enemy_tick(room, player) -> list:
    msgs = []
    for ent in list(room.entities):
        if not ent.alive:
            continue
        dist = _manhattan(player.row, player.col, ent.row, ent.col)
        if ent.kind == 'warden' and ent.tag != 'surveyor' and dist <= _ALERT_RADIUS:
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
        if dist > _ALERT_RADIUS:
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


# ── Dungeon game loop ──────────────────────────────────────────────────────────

def run_dungeon(term: Terminal, level: str, progress: dict,
                player_name: str = 'Normand',
                _dungeon: Dungeon | None = None,
                _start_edit: bool = False) -> dict:
    """Run one dungeon level.

    Returns {'won': bool, 'stars': int, 'action': 'wq'|'quit',
             'first_written_completion': bool}.
    first_written_completion is True when the player saved (:w or :wq) and it
    was the first time this level reached ≥1 star (prev stars == 0).
    _dungeon: pre-built Dungeon (used for custom layouts from the overworld).
    _start_edit: if True, enter edit mode immediately (admin custom levels).
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
    player.known_commands = _known_commands(level)
    if player_name == 'admin':
        player.known_commands = player.known_commands + ['admin', 'register']
    # On a boss level, the command its scroll gates stays LOCKED on entry — even
    # if a past playthrough already banked it in extras — until the player reads
    # this boss's scroll again (which re-adds it below, on chest loot).
    _gated = _SCROLL_DROPS.get(level, (None,))[0] if level_type(level) == 'boss' else None
    for _cmd in progress.get('extras', []):
        if _cmd != _gated and _cmd not in player.known_commands:
            player.known_commands = player.known_commands + [_cmd]
    dungeon.level_slug = level   # lets the renderer show the act's hint on bosses

    # Remove heart containers already collected by this player.
    _collected = progress.get('collected_hearts', [])
    for _e in list(room.entities):
        if _e.kind == 'heart_container' and [level, _e.row, _e.col] in _collected:
            room.kill_entity(_e)

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
    insert_creg_pending = False  # INSERT <C-r> typed; next key names the register to paste
    insert_co_buf = None         # INSERT <C-o> active; accumulates one Normal command, then resumes INSERT
    search_creg_pending = False  # SEARCH <C-r> typed; next key names the register / <C-w> to insert
    at_exit  = False   # player has stepped on the exit at some point
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
    attack_flash_sym: str   = ''      # directional arrow; '' = no flash active
    attack_flash_pos: tuple = (0, 0)  # goblin cell to flash on
    attack_flash_on:  bool  = True    # True → show arrow, False → show normal g
    attack_flash_ttl: int   = 0

    def _attack_sym() -> str:
        return attack_flash_sym if (attack_flash_sym and attack_flash_on) else ''

    def _attack_pos() -> tuple | None:
        return attack_flash_pos if attack_flash_sym else None

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
        scr_c = 1 + (expl_c - vc)
        render_all(term, dungeon, player, budget, message,
                   attack_pos=_attack_pos(), attack_sym=_attack_sym())
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
        h, hh = player.hp // 2, '½' if player.hp % 2 else ''
        return f'BOOM! Dynamite!  ({h}{hh} ♥ remaining)', 30

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
                h, hh = player.hp // 2, '½' if player.hp % 2 else ''
                message, msg_ttl = f"The Warden's selection erases you!  ({h}{hh} ♥)", 30

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
            _push("The Warden's eye opens — he enters visual mode.")
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

    def _push(text: str) -> None:
        if text not in msg_pool:
            msg_pool.append(text)

    # ── The Archivist's Library (L17) — reload loop + reckoning ─────────────
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

    def _lib_animate():
        # The Archivist scurries the hall, scrambling the leaf in front of the
        # reader, before it settles into the next manuscript. Skipped when there is
        # no live terminal (tests / headless).
        if not getattr(term, 'is_a_tty', False) or not room.char_runs:
            return
        import time as _t
        arch = next((e for e in room.entities if e.kind == 'archivist'), None)
        base = list(room.char_runs[0].symbols)
        kind = room.char_runs[0].kind
        frame_glyphs = '▌▐▎█░▒▓·∘◦~≋'
        n = len(base)
        for _f in range(14):
            syms = base[:]
            for _ in range(20):
                c = random.randrange(n)
                if syms[c] not in '┌┐└┘─│':
                    syms[c] = random.choice(frame_glyphs)
            room.char_runs = [CharRun(0, 0, tuple(syms), kind)]
            if arch is not None:
                arch.col = random.randrange(1, max(2, room.cols - 1))
            room.rebuild_indexes()
            render_all(term, dungeon, player, budget, 'The Archivist is tidying the shelves…')
            _t.sleep(0.05)

    def _lib_reload(force):
        if getattr(room, 'lib_done', None):
            _push('The library is whole again — nothing left to reload.')
            return
        if not force:
            player.error = 'E37: No write since last change (add ! to override)'
            _push('E37: No write since last change (add ! to override)')
            return
        room.lib_idx  = (room.lib_idx + 1) % len(room.lib_seq)
        room.lib_view = 'leaf'
        _lib_animate()
        _lib_relayout()
        _push('"library" 1 line  --reloaded--')

    def _lib_file(name):
        if getattr(room, 'lib_done', None):
            return
        if room.lib_idx < 0 or getattr(room, 'lib_view', 'catalog') != 'leaf':
            _push('No manuscript open — press  :e!  to leaf to one.')
            return
        room.lib_filed[name] = room.lib_seq[room.lib_idx]['suit']
        room.lib_view = 'catalog'                 # back to the floor — the stack fills in
        _lib_relayout()
        _push(f'"{name}" [New] 1 line written')
        if all(s in room.lib_filed for s in _dg._LIB_SUITS):
            _push('All four stacks filled.')
            _push('Press  $  to bring them to the Archivist.')
        else:
            _push('The stack fills. Press  :e!  to leaf on.')

    def _lib_finale():
        room.lib_done = 'win'
        room.entities = [e for e in room.entities if e.kind != 'archivist']
        _lib_relayout()                          # draw the restored-library page
        # Place the rewards a few steps LEFT of where $ left the player (the far
        # corner): two chests first, then the exit — open, then step on to win.
        last = room.cols - 1
        room.add_entity(Entity(kind='chest_scroll', row=0, col=last - 2, scroll_id='display_move'))
        room.add_entity(Entity(kind='chest_scroll', row=0, col=last - 4, scroll_id='edit_name'))
        room.add_entity(Entity(kind='exit',         row=0, col=last - 8))
        room.rebuild_indexes()

    def _lib_on_archivist():
        if getattr(room, 'lib_done', None):
            return
        if not all(s in room.lib_filed for s in _dg._LIB_SUITS):
            if not player.wrap:
                _push('MY LIBRARY! All on ONE LINE!')
                _push('Some fiend ran  :set nowrap  — put it right!')
            elif not room.lib_briefed:
                room.lib_briefed = True
                _push('A reader, at last!')
                _push('A vandal corrupted my shelves.')
                _push(':e!  leafs onward;  :w <suit>  files a folio.')
                _push('Bring me hearts, diamonds, spades and clubs.')
            else:
                _push('File all four suits, then return to me.')
            return
        if all(room.lib_filed.get(s) == s for s in _dg._LIB_SUITS):
            _lib_finale()
            _push('"Flawless! My library is whole again."')
            _push('Open my two chests, then  :wq  to leave.')
        else:
            _push('"So YOU\'RE the pest mangling my folios!"')
            _push('The Archivist strikes you down.')
            player.take_damage(player.max_hp + 20)

    if _start_edit:
        room.passable_walls = True
        if 'editor' not in player.known_commands:
            player.known_commands = player.known_commands + ['editor']

    if level == 'line_halls':
        message = 'The Line Halls — navigate to the corridor, then use $ and ^'
        msg_ttl = 50
    elif level == 'reliquary':
        message = 'The Reliquary — break the ward: x away the seal to reach the relic.'
        msg_ttl = 60
    elif level == 'counting_crypts':
        message = 'The Counting Crypts — type [N] before hjkl: try 5j or 3l'
        msg_ttl = 50
    elif level == 'rune_halls':
        message = 'The Rune Halls — w:next word  b:prev word  e:end of word'
        msg_ttl = 60
    elif level == 'character_cataracts':
        message = 'The Character Cataracts — f{c}:jump to char  t{c}:just before  F/T:backward'
        msg_ttl = 60
    elif level == 'wardens_keep':
        message = "The Warden's Keep — the shield follows you. Find the unguarded side."
        msg_ttl = 60
    elif level == 'warden_surveyor':
        message = "The Warden Surveyor — survey his hall; w/b/e leap word to word, over the void."
        msg_ttl = 60
    elif level == 'dummy':
        message = 'Sandbox — all mechanics active. Type :edit to enter editor mode.'
        msg_ttl = 60
    elif level == 'archivists_library':
        message = ("The Archivist's Library — the catalogue is one ruined line. "
                   "Type  :set wrap  to shelve it.")
        msg_ttl = 80

    any_water     = any(ct == CellType.WATER for row in room.cells for ct in row)
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
        msg_pool.append(_goblin_msg(_goblin_sighting(len(_entry_goblins))))
    for e in room._entity_by_kind.get('warden', []):
        if e.alive and (e.row, e.col) not in room.fog_cells:
            spotted_wardens.add(id(e))
            msg_pool.append('You spotted a Warden!')
    if msg_pool:
        message = _pool_msg()
        msg_ttl = _MSG_ROTATE_TTL

    if level == 'archivists_library':
        _lib_relayout()                          # fit the page frame to the real viewport

    render_all(term, dungeon, player, budget, message, attack_pos=_attack_pos(), attack_sym=_attack_sym())

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
                render_all(term, dungeon, player, budget, _pool_msg(), attack_pos=_attack_pos(), attack_sym=_attack_sym())
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
                player.macros[recording_reg] = macro_buf
                recording_reg = None
                macro_buf = ''
                render_all(term, dungeon, player, budget, message, attack_pos=_attack_pos(), attack_sym=_attack_sym())
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
                    msg_ttl = _MSG_ROTATE_TTL
                else:
                    message = ''

        if not key:
            water_active    = any_water and (time.time() - last_activity < _WATER_SETTLE_SECS)
            overlap_active  = room.entity_at(player.row, player.col) is not None
            needs_render    = message != prev_message or water_active or overlap_active
            if attack_flash_sym:
                attack_flash_ttl -= 1
                if attack_flash_ttl <= 0:
                    attack_flash_on  = not attack_flash_on
                    attack_flash_ttl = _ATTACK_FLASH_TTL
                    needs_render     = True
            if needs_render:
                render_all(term, dungeon, player, budget, message,
                           attack_pos=_attack_pos(), attack_sym=_attack_sym())
            continue

        last_activity = time.time()
        player.error = ''   # clear any statusline error on the next keypress

        # ── Admin answer tracking ─────────────────────────────────────────────
        if (player_name == 'admin' and room.answer
                and not key.is_sequence and str(key) != ':'
                and player.mode in (Mode.NORMAL, Mode.VISUAL,
                                    Mode.VISUAL_LINE, Mode.VISUAL_BLOCK)):
            if key_buf == '':
                cmd_start_ans = (room.answer_pos, room.answer_diverged)
            if not room.answer_diverged:
                _ans_plain = room.answer.replace(' ', '')
                if room.answer_pos < len(_ans_plain):
                    if str(key) == _ans_plain[room.answer_pos]:
                        room.answer_pos += 1
                    else:
                        room.answer_diverged = True

        # ── Command mode ──────────────────────────────────────────────────────
        if player.mode == Mode.COMMAND:
            if key.name == 'KEY_ESCAPE':
                player.mode = Mode.NORMAL
                player.cmd_line = ''
            elif key.name == 'KEY_ENTER' or str(key) in ('\n', '\r'):
                cmd = player.cmd_line.strip()
                player.mode    = Mode.NORMAL
                player.cmd_line = ''
                msg_pool.clear()
                msg_idx = 0

                if (level == 'archivists_library' and cmd in ('e', 'e!')
                        and not player.is_dead):
                    _lib_reload(force=(cmd == 'e!'))

                elif (level == 'archivists_library' and cmd.startswith('w ')
                        and cmd[2:].strip() in _dg._LIB_SUITS):
                    _lib_file(cmd[2:].strip())

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
                        _commit_hearts()
                        SM.save_progress(progress, player_name)
                        _push('Saved.')

                elif cmd == 'wq':
                    if edit_mode and player_name == 'admin':
                        path = SM.save_layout(dungeon.name, _serialize_room(room))
                        _push(f'Layout saved: {path.name}')
                    stars = _calc_stars(won, budget, room, player, level)
                    if won:
                        prev = progress.get(level, {}).get('stars', 0)
                        if prev == 0 and stars >= 1:
                            _first_written_completion = True
                    _commit_hearts()                         # caller saves on 'wq'
                    return {'won': won, 'stars': stars, 'action': 'wq',
                            'first_written_completion': _first_written_completion}

                elif cmd == 'q':
                    stars = _calc_stars(won, budget, room, player, level)
                    if (player_name != 'admin'
                            and ((won and stars > last_saved_stars) or pending_hearts)):
                        player.error = 'E37: No write since last change (add ! to override)'
                    else:
                        return {'won': won, 'stars': stars, 'action': 'quit',
                                'first_written_completion': _first_written_completion}

                elif cmd == 'q!':
                    return {'won': False, 'stars': 0, 'action': 'quit',
                            'first_written_completion': False}

                elif cmd == 'e' and (player_name == 'admin' or player.is_dead):
                    seed    = random.randint(0, 2**31)
                    dungeon = _build_dungeon(level, seed, admin=(player_name == 'admin'))
                    room    = dungeon.room
                    if player_name != 'admin':
                        room.answer = ''
                    _sp2    = room.spawn_pos
                    player  = Player(row=_sp2[0], col=_sp2[1])
                    player.max_hp = progress.get('max_hp', 6)   # keep heart-container upgrades
                    player.hp     = player.max_hp
                    player.known_commands = _known_commands(level)
                    if player_name == 'admin':
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
                    at_exit         = False
                    won             = False
                    spotted_goblins      = set()
                    spotted_wardens      = set()
                    engaged_entities     = set()
                    door_hint_shown      = set()
                    door_open_hint_shown = set()
                    msg_pool             = []
                    msg_idx              = 0
                    _push('Dungeon restarted. Good luck.' if player_name != 'admin' else 'New dungeon loaded.')

                elif cmd == 'edit' and player_name == 'admin':
                    edit_mode = not edit_mode
                    room.passable_walls = edit_mode
                    if edit_mode:
                        if 'editor' not in player.known_commands:
                            player.known_commands = player.known_commands + ['editor']
                        _push('EDIT mode ON — x:cut  s:subst  dd/yy  d/y{m}  p/P  :save <name>')
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

                elif cmd.startswith('rune ') and edit_mode and player_name == 'admin':
                    _RUNE_SYMS = {'ancient': '∘', 'verdant': '·', 'void': '○', 'ember': '◦'}
                    kind = cmd[5:].strip().lower()
                    if kind not in _RUNE_SYMS:
                        _push(f'Unknown rune kind: {kind}  (ancient|verdant|void|ember)')
                    else:
                        r, c = player.row, player.col
                        ed_undo.append(_ed_snapshot(room, player))
                        ed_redo.clear()
                        existing = room.char_run_at(r, c)
                        if existing:
                            room.remove_char_run(existing)
                        room.add_char_run(CharRun(row=r, col=c,
                                                  symbols=(_RUNE_SYMS[kind],), kind=kind))
                        _merge_adjacent_char_runs(room, r)
                        _push(f'Placed {kind} rune.')

                elif cmd.startswith('entity ') and edit_mode and player_name == 'admin':
                    _ENTITY_PRESETS = {
                        'exit':         dict(hp=1, alive=True),
                        'door':         dict(hp=1, alive=True),
                        'locked_door':  dict(hp=1, alive=True),
                        'chest':        dict(hp=1, alive=True),
                        'chest_key':    dict(hp=1, alive=True),
                        'chest_scroll': dict(hp=1, alive=True),
                        'dynamite':     dict(hp=1, alive=True),
                        'wanderer':     dict(hp=1, alive=True, max_hp=1, ai='chase', ai_speed=2),
                        'goblin':       dict(hp=1, alive=True, max_hp=1, ai='chase', ai_speed=1),
                        'warden':       dict(hp=5, alive=True, max_hp=5, ai='',      ai_speed=1),
                    }
                    kind = cmd[7:].strip().lower()
                    if kind not in _ENTITY_PRESETS:
                        kinds_str = '|'.join(_ENTITY_PRESETS)
                        _push(f'Unknown entity kind: {kind}  ({kinds_str})')
                    else:
                        r, c = player.row, player.col
                        ed_undo.append(_ed_snapshot(room, player))
                        ed_redo.clear()
                        existing = room.entity_at(r, c)
                        if existing:
                            room.entities.remove(existing)
                            room.rebuild_indexes()
                        room.add_entity(Entity(kind=kind, row=r, col=c,
                                               **_ENTITY_PRESETS[kind]))
                        _push(f'Placed {kind}.')

                elif cmd in ('noh', 'nohl', 'nohls', 'nohlsearch'):
                    # :noh — clear the search highlight until the next search.
                    if '/' in player.known_commands or player_name == 'admin':
                        player.hl_suppressed = True
                        _push(':nohlsearch')
                    else:
                        _push("You haven't learned search yet.")

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
                            if _act == 'query':
                                _push(_flag if _cur else 'no' + _flag)
                            else:
                                _push((':set ' if _act in ('on', 'reset') else '')
                                      + (_flag if _new else 'no' + _flag))
                            if (level == 'archivists_library' and _flag == 'wrap'
                                    and _new and not getattr(room, 'lib_done', None)):
                                _push('The hall folds into view.')
                                _push('The Archivist waits at his desk —')
                                _push('press  $  to cross to him.')
                        else:
                            player.number_mode, _set_msg = _apply_set(
                                player.number_mode, cmd[len('set'):])
                            _push(_set_msg)

                else:
                    _push(f'Unknown command: :{cmd}')

            elif key.name == 'KEY_BACKSPACE' or str(key) == '\x7f':
                player.cmd_line = player.cmd_line[:-1]
            elif search_creg_pending:
                # second key after <C-r>: <C-w> pulls the word under the cursor,
                # otherwise the named register's text, into the search line.
                search_creg_pending = False
                if not key.is_sequence:
                    if str(key) == '\x17':
                        player.cmd_line += _word_under_cursor(room, player) or ''
                    else:
                        player.cmd_line += _clip_to_text(_reg_read(player, str(key)))
            elif str(key) == '\x12':                       # <C-r> — insert into the search line
                search_creg_pending = True
            else:
                player.cmd_line = _cmd_append(player.cmd_line, key)
            if msg_pool:
                msg_idx = 0
                message = _pool_msg()
                msg_ttl = _MSG_ROTATE_TTL
            render_all(term, dungeon, player, budget, message, attack_pos=_attack_pos(), attack_sym=_attack_sym())
            continue

        # ── SEARCH mode (/ or ? pattern entry) ────────────────────────────────
        if player.mode == Mode.SEARCH:
            if key.name == 'KEY_ESCAPE':
                player.mode = search_return_mode or Mode.NORMAL   # back to visual if launched there
                search_return_mode = None
                player.cmd_line = ''
            elif key.name == 'KEY_ENTER' or str(key) in ('\n', '\r'):
                pattern = player.cmd_line
                fwd     = player.search_forward
                # A search launched from visual mode is a MOTION that extends the
                # selection: resume that visual mode (anchor intact) and just move the
                # cursor — no jumplist/undo entry, exactly like any visual-mode motion.
                from_visual     = search_return_mode is not None
                player.mode     = search_return_mode or Mode.NORMAL
                search_return_mode = None
                player.cmd_line = ''
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
                            budget.spend(len(pattern) + 2)
                            if not from_visual:
                                undo_stack.append(pre)
                                redo_stack.clear()
                    else:
                        _push(f'Pattern not found: {pattern}')
            elif key.name == 'KEY_BACKSPACE' or str(key) == '\x7f':
                player.cmd_line = player.cmd_line[:-1]
            else:
                player.cmd_line = _cmd_append(player.cmd_line, key)
            render_all(term, dungeon, player, budget, message, attack_pos=_attack_pos(), attack_sym=_attack_sym())
            continue

        # ── INSERT mode (admin text placement) ───────────────────────────────
        if player.mode == Mode.INSERT:
            if key.name == 'KEY_ESCAPE':
                player.mode = Mode.NORMAL
                key_buf = ''
                insert_creg_pending = False
                insert_co_buf = None
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
                    if ch.isprintable() and len(ch) == 1:
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
                    render_all(term, dungeon, player, budget, message, attack_pos=_attack_pos(), attack_sym=_attack_sym())
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
                    render_all(term, dungeon, player, budget, message, attack_pos=_attack_pos(), attack_sym=_attack_sym())
                    continue

                if _kstr == '\x12' and _ins_ok('ins_paste'):     # <C-r> — paste a register
                    insert_creg_pending = True
                    render_all(term, dungeon, player, budget, message, attack_pos=_attack_pos(), attack_sym=_attack_sym())
                    continue
                if _kstr == '\x0f' and _ins_ok('ins_edit'):      # <C-o> — one Normal command
                    insert_co_buf = ''
                    render_all(term, dungeon, player, budget, message, attack_pos=_attack_pos(), attack_sym=_attack_sym())
                    continue
                if _kstr == '\x17' and _ins_ok('ins_edit'):      # <C-w> — delete word back
                    insert_delete_word_back(room, player)
                    render_all(term, dungeon, player, budget, message, attack_pos=_attack_pos(), attack_sym=_attack_sym())
                    continue
                if _kstr == '\x15' and _ins_ok('ins_edit'):      # <C-u> — delete to line start
                    insert_delete_to_start(room, player)
                    render_all(term, dungeon, player, budget, message, attack_pos=_attack_pos(), attack_sym=_attack_sym())
                    continue

                if key.name == 'KEY_BACKSPACE' or str(key) == '\x7f':
                    insert_backspace(room, player)
                elif not key.is_sequence:
                    ch = str(key)
                    if ch.isprintable() and len(ch) == 1:
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
                        if room._last_void_falls:          # ledge: a glyph went over the brink
                            render_all(term, dungeon, player, budget, message,
                                       attack_pos=_attack_pos(), attack_sym=_attack_sym())
                            _play_void_falls(term, dungeon, room, player)
                            message = 'Over the brink — into the void it tumbles!'
                            msg_ttl = 25
                        if room._last_drowns:              # ledge: a wave of water swept an entity away
                            render_all(term, dungeon, player, budget, message,
                                       attack_pos=_attack_pos(), attack_sym=_attack_sym())
                            for (dr, dc) in room._last_drowns:
                                _drown_animation(term, *_void_screen_xy(term, room, player, dr, dc))
                            room._last_drowns = []
                            message = 'A wave sweeps it away into the void!'
                            msg_ttl = 25
                        cur_ru = room.char_run_at(player.row, player.col)
                        if cur_ru is not None and cur_ru.kind == 'void':   # typed yourself off the ledge
                            render_all(term, dungeon, player, budget, message,
                                       attack_pos=_attack_pos(), attack_sym=_attack_sym())
                            _void_fall_animation(term, *_void_screen_xy(term, room, player, player.row, player.col))
                            player.take_damage(2)                          # 1 full heart
                            safe_c = min(prev_ins[1], void_col(room, prev_ins[0]) - 1)
                            player.row, player.col = prev_ins[0], max(safe_c, 0)   # stumble back to safe ground
                            player.mode = Mode.NORMAL
                            if player.is_dead:
                                message = '** GAME OVER ** Type  :e  to re-load the dungeon.'; msg_ttl = 2
                            else:
                                h, hh = player.hp // 2, '½' if player.hp % 2 else ''
                                message = f'You typed yourself off the ledge!  ({h}{hh} ♥ remaining)'; msg_ttl = 25
            render_all(term, dungeon, player, budget, message, attack_pos=_attack_pos(), attack_sym=_attack_sym())
            continue

        # ── REPLACE mode (overtype; Backspace restores originals) ─────────────
        if player.mode == Mode.REPLACE:
            if key.name == 'KEY_ESCAPE':
                player.mode = Mode.NORMAL
                if player.col > 0 and room.is_passable(player.row, player.col - 1):
                    player.col -= 1                    # vim retreats one on Esc
                replace_stack = []
                key_buf = ''
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
            render_all(term, dungeon, player, budget, message, attack_pos=_attack_pos(), attack_sym=_attack_sym())
            continue

        # ── VISUAL modes (v / V / Ctrl-v): extend selection, operate ────────────
        if player.mode in (Mode.VISUAL, Mode.VISUAL_LINE, Mode.VISUAL_BLOCK):
            vmode = player.mode
            if key.name == 'KEY_ESCAPE':
                if player.visual_anchor is not None:
                    player.row, player.col = player.visual_anchor
                player.mode = Mode.NORMAL
                player.visual_anchor = None
                key_buf = ''
                render_all(term, dungeon, player, budget, message, attack_pos=_attack_pos(), attack_sym=_attack_sym())
                continue
            raw = str(key) if not key.is_sequence else ''
            anchor = player.visual_anchor or (player.row, player.col)
            cursor = (player.row, player.col)
            # Single-key visual commands (only when not mid multi-key motion)
            if not key_buf and raw == 'o':                 # swap ends
                player.row, player.col = anchor
                player.visual_anchor = cursor
                render_all(term, dungeon, player, budget, message, attack_pos=_attack_pos(), attack_sym=_attack_sym())
                continue
            want = _visual_mode_toggle(raw, str(key)) if not key_buf else None
            if want is not None:                           # v / V / Ctrl-v toggle / exit
                player.mode = Mode.NORMAL if want == vmode else want
                if player.mode == Mode.NORMAL:
                    player.visual_anchor = None
                render_all(term, dungeon, player, budget, message, attack_pos=_attack_pos(), attack_sym=_attack_sym())
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
                render_all(term, dungeon, player, budget, message, attack_pos=_attack_pos(), attack_sym=_attack_sym())
                continue
            if not key_buf and raw and raw in 'dycx~<>':
                op = {'x': 'd', '~': 'g~'}.get(raw, raw)
                if raw in 'dyc~<>' and not (
                        'visual_op' in player.known_commands or 'admin' in player.known_commands):
                    _push("You haven't learned visual operators yet.")
                    render_all(term, dungeon, player, budget, message, attack_pos=_attack_pos(), attack_sym=_attack_sym())
                    continue
                if not edit_mode and budget.remaining <= 0:
                    _push('Out of budget!  (Esc, then u to undo)')
                    message = _pool_msg(); msg_ttl = _MSG_ROTATE_TTL
                    render_all(term, dungeon, player, budget, message, attack_pos=_attack_pos(), attack_sym=_attack_sym())
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
                budget.spend(1)
                player.last_visual_anchor = anchor
                player.last_visual_cursor = cursor
                player.last_visual_mode = vmode
                player.visual_anchor = None
                player.mode = Mode.INSERT if op == 'c' else Mode.NORMAL
                player.last_change = {'type': 'visual_op', 'op': op}
                key_buf = ''
                render_all(term, dungeon, player, budget, message, attack_pos=_attack_pos(), attack_sym=_attack_sym())
                continue
            key_buf += raw
            # Text object: i/a (+ optional count) + object char selects the span
            # (viw, vaw, vi(, va", …).  In visual mode i/a are object prefixes.
            vt = parse_visual_textobj(key_buf)
            if vt == 'pending':
                render_all(term, dungeon, player, budget, message, attack_pos=_attack_pos(), attack_sym=_attack_sym())
                continue
            if vt is not None:
                _, textobj, tcount = vt
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
                            budget.spend(2 + (len(str(tcount)) if tcount > 1 else 0))
                render_all(term, dungeon, player, budget, message, attack_pos=_attack_pos(), attack_sym=_attack_sym())
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
                        budget.spend(_keystroke_cost(v_count, v_motion))
            elif v_action is not None:
                key_buf = ''                               # ignore non-motion keys in visual
            render_all(term, dungeon, player, budget, message, attack_pos=_attack_pos(), attack_sym=_attack_sym())
            continue

        # ── Normal mode ───────────────────────────────────────────────────────
        if key.name == 'KEY_ESCAPE':
            _apply_esc(player)
            key_buf = ''
            render_all(term, dungeon, player, budget, message, attack_pos=_attack_pos(), attack_sym=_attack_sym())
            continue

        raw     = str(key) if not key.is_sequence else ''
        key_buf += raw
        action, key_buf = parse(key_buf, player.mode)

        if action is None:
            render_all(term, dungeon, player, budget, message, attack_pos=_attack_pos(), attack_sym=_attack_sym())
            continue

        # Dead players may only enter command mode to type :e
        if player.is_dead and not (action['type'] == 'enter_mode'
                                   and action.get('mode') == 'command'):
            render_all(term, dungeon, player, budget, message, attack_pos=_attack_pos(), attack_sym=_attack_sym())
            continue

        # Out of budget: the path is spent.  No budget-costing action may proceed —
        # only undo/redo (to recover) or :command (to quit / :edit).
        if not edit_mode and budget.remaining <= 0 and _budget_exhausted_blocks(action):
            _push('Out of budget!  (u to undo)')
            message = _pool_msg(); msg_ttl = _MSG_ROTATE_TTL
            render_all(term, dungeon, player, budget, message, attack_pos=_attack_pos(), attack_sym=_attack_sym())
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
        prev_adjacent_ids = {
            id(e) for e in room.entities
            if e.alive and e.max_hp
            and _manhattan(player.row, player.col, e.row, e.col) <= _ATTACK_RADIUS
        }
        count    = action.get('count', 1)

        # . — repeat last change
        if action['type'] == 'repeat':
            if not _action_allowed(action, player.known_commands):
                _push(_guard_message(action, player.known_commands))
                message = _pool_msg(); msg_ttl = _MSG_ROTATE_TTL
                render_all(term, dungeon, player, budget, message, attack_pos=_attack_pos(), attack_sym=_attack_sym())
                continue
            if not player.last_change:
                _push('Nothing to repeat.')
                message = _pool_msg(); msg_ttl = _MSG_ROTATE_TTL
                render_all(term, dungeon, player, budget, message, attack_pos=_attack_pos(), attack_sym=_attack_sym())
                continue
            repeat_count = action.get('count', 1)
            action = dict(player.last_change)
            if repeat_count != 1:
                action['count'] = repeat_count
            count = action.get('count', 1)

        if action['type'] == 'motion':
            motion = action['motion']
            target = action.get('target')

            if not edit_mode and not _action_allowed(action, player.known_commands):
                _push(_guard_message(action, player.known_commands))
                message = _pool_msg(); msg_ttl = _MSG_ROTATE_TTL
                render_all(term, dungeon, player, budget, message, attack_pos=_attack_pos(), attack_sym=_attack_sym())
                continue

            jump_from = (player.row, player.col)
            moved = apply_motion(player, motion, count, room, target,
                                 count_given=action.get('count_given', True),
                                 game_h=term.height - 8)
            if moved:
                if motion in _JUMP_MOTIONS:
                    _record_jump(player, jump_from)
                if not edit_mode:
                    budget.spend(_keystroke_cost(count, motion))
                    undo_stack.append(prev_pos)
                    redo_stack.clear()

                if count > 1 and not count_tutorial_shown and not edit_mode and level == 'counting_crypts':
                    count_tutorial_shown = True
                    _push(f'{count}{motion} moved {count} steps in 2 keystrokes — count is efficient!')

                # Void rune: fall animation, lose heart, respawn (skip in edit mode)
                ru = room.char_run_at(player.row, player.col)
                if not edit_mode and ru and ru.kind == 'void':
                    iw    = _iw(term)
                    game_h = term.height - 8
                    vr_start = max(0, min(player.row - game_h // 2, room.rows - game_h))
                    vc_start = max(0, min(player.col - iw  // 2,    room.cols - iw))
                    scr_r    = player.row - vr_start + 3
                    scr_c    = player.col - vc_start + 1
                    render_all(term, dungeon, player, budget, message, attack_pos=_attack_pos(), attack_sym=_attack_sym())
                    _void_fall_animation(term, scr_r, scr_c)
                    player.take_damage(2)  # 1 full heart
                    player.row, player.col = prev_pos[0], prev_pos[1]
                    if player.is_dead:
                        message = '** GAME OVER ** Type  :e  to re-load the dungeon.'
                        msg_ttl = 2
                    else:
                        h, hh = player.hp // 2, '½' if player.hp % 2 else ''
                        message = f'You fell into the void!  ({h}{hh} ♥ remaining)'
                        msg_ttl = 25
                    render_all(term, dungeon, player, budget, message, attack_pos=_attack_pos(), attack_sym=_attack_sym())
                    continue

                # Water: drown if landed on water cell (e.g. via $, 0, ^)
                if not edit_mode and room.cells[player.row][player.col] == CellType.WATER:
                    iw    = _iw(term)
                    game_h = term.height - 8
                    vr_start = max(0, min(player.row - game_h // 2, room.rows - game_h))
                    vc_start = max(0, min(player.col - iw  // 2,    room.cols - iw))
                    scr_r    = player.row - vr_start + 3
                    scr_c    = player.col - vc_start + 1
                    render_all(term, dungeon, player, budget, message, attack_pos=_attack_pos(), attack_sym=_attack_sym())
                    _drown_animation(term, scr_r, scr_c)
                    player.take_damage(2)  # 1 full heart
                    player.row, player.col = prev_pos[0], prev_pos[1]
                    if player.is_dead:
                        message = '** GAME OVER ** Type  :e  to re-load the dungeon.'
                        msg_ttl = 2
                    else:
                        h, hh = player.hp // 2, '½' if player.hp % 2 else ''
                        message = f'You drowned!  ({h}{hh} ♥ remaining)'
                        msg_ttl = 25
                    render_all(term, dungeon, player, budget, message, attack_pos=_attack_pos(), attack_sym=_attack_sym())
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

                # The Archivist's Library: reaching the hall's end ($) calls the
                # Archivist over — to brief you, or to receive the filed folios.
                if level == 'archivists_library':
                    _at_end = player.col == room.cols - 1
                    if _at_end and not room._lib_arch_flag:
                        room._lib_arch_flag = True
                        _lib_on_archivist()
                    elif not _at_end:
                        room._lib_arch_flag = False

                # Win / exit check
                if ent is None:
                    ent = room.entity_at(player.row, player.col)
                if ent and ent.kind == 'exit' and not won:
                    # Keystone-gated exit: blocked until all keystone entities are collected.
                    _ks_alive = [e for e in room._entity_by_kind.get('keystone', []) if e.alive]
                    if _ks_alive:
                        _push(f'{len(_ks_alive)} keystone(s) still uncollected.')
                        ent = None
                if ent and ent.kind == 'exit' and not won:
                    won = True
                    at_exit = True
                    render_all(term, dungeon, player, budget, '', attack_pos=_attack_pos(), attack_sym=_attack_sym())
                    iw  = _iw(term)
                    if level_type(level) == 'boss':
                        _starfield_victory(term, iw, dungeon, player)
                        message = 'VIM AD ASTRA — the way upward opens. Type :wq to return to the overworld.'
                    elif (room.par or 0) > 0 and budget.spent <= room.par:
                        _fireworks_animation(term, iw, dungeon, player)
                        message = 'Par-perfect — not a stroke wasted!  Type :wq to return to the overworld.'
                    else:
                        _win_animation(term, iw, dungeon, player)
                        message = 'Dungeon cleared!  Type :wq to return to the overworld.'
                    msg_ttl = 200

        elif action['type'] == 'enter_mode':
            m = action['mode']
            if m == 'command':
                player.mode     = Mode.COMMAND
                player.cmd_line = ''
            elif m == 'insert':
                if edit_mode:
                    player.mode = Mode.INSERT          # admin map-editing placement
                elif 'insert' in player.known_commands or 'admin' in player.known_commands:
                    undo_stack.append(_snapshot(room, player, budget, ans=cmd_start_ans))
                    redo_stack.clear()
                    begin_insert(room, player, action.get('variant', 'i'), count)
                    player.mode = Mode.INSERT
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
                    player.search_forward = action.get('forward', True)
                else:
                    _push('Search not learned yet.')
            elif m in ('visual', 'visual_line', 'visual_block'):
                if 'visual' in player.known_commands or 'admin' in player.known_commands:
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
            if not edit_mode and not _action_allowed(action, player.known_commands):
                _push(_guard_message(action, player.known_commands))
                message = _pool_msg(); msg_ttl = _MSG_ROTATE_TTL
                render_all(term, dungeon, player, budget, message, attack_pos=_attack_pos(), attack_sym=_attack_sym())
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
            if not edit_mode and not _action_allowed(action, player.known_commands):
                _push(_guard_message(action, player.known_commands))
                message = _pool_msg(); msg_ttl = _MSG_ROTATE_TTL
                render_all(term, dungeon, player, budget, message, attack_pos=_attack_pos(), attack_sym=_attack_sym())
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
            if not edit_mode and not _action_allowed(action, player.known_commands):
                _push(_guard_message(action, player.known_commands))
                message = _pool_msg(); msg_ttl = _MSG_ROTATE_TTL
                render_all(term, dungeon, player, budget, message, attack_pos=_attack_pos(), attack_sym=_attack_sym())
                continue
            recording_reg = action['reg']
            macro_buf = ''
            _push(f'recording @{recording_reg}')

        elif action['type'] == 'macro_play':
            if not edit_mode and not _action_allowed(action, player.known_commands):
                _push(_guard_message(action, player.known_commands))
                message = _pool_msg(); msg_ttl = _MSG_ROTATE_TTL
                render_all(term, dungeon, player, budget, message, attack_pos=_attack_pos(), attack_sym=_attack_sym())
                continue
            reg = macro_last if action['reg'] == '@' else action['reg']
            keys = player.macros.get(reg) if reg else None
            if not keys:
                _push('No macro to play.')
            else:
                macro_last = reg
                add = keys * count
                if len(macro_pending) + len(add) > _MACRO_MAX:
                    _push('Macro too long (recursion?).')
                else:
                    macro_pending.extendleft(reversed(add))   # play next, in order
                    budget.spend(2 + (len(str(count)) if count > 1 else 0))

        elif action['type'] in ('search_repeat', 'search_word'):
            if not edit_mode and not _action_allowed(action, player.known_commands):
                _push(_guard_message(action, player.known_commands))
                message = _pool_msg(); msg_ttl = _MSG_ROTATE_TTL
                render_all(term, dungeon, player, budget, message, attack_pos=_attack_pos(), attack_sym=_attack_sym())
                continue
            if action['type'] == 'search_word':
                word = _word_under_cursor(room, player)
                if word is None:
                    _push('No character under cursor.')
                    pattern, fwd = None, True
                else:
                    fwd = action.get('forward', True)
                    # * / # search the word literally (not as a regex) — \V makes
                    # every char of the word a literal in the matcher.
                    pattern = '\\V' + word
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
                    budget.spend(_keystroke_cost(count, ''))
                    undo_stack.append(prev_pos)
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
            if edit_mode:
                done = _ed_step_n(ed_redo, ed_undo, count, room, player)
            else:
                done = sum(_pop_history_step(redo_stack, undo_stack, room, player, budget)
                           for _ in range(count))
            _push(f'{done} change(s) redone.' if done else 'Nothing to redo.')

        elif action['type'] == 'interact':
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
                    descs = ', '.join(_clip_desc(i) for i in cut_items)
                    _push(f'Cut {len(cut_items)}: {descs}')
                    player.last_change = action
                else:
                    ed_undo.pop()
                    _push('Nothing to cut here.')
            else:
                interacted = False
                cur = room.entity_at(player.row, player.col)
                if cur and cur.kind in ('chest', 'chest_key', 'chest_scroll'):
                    undo_stack.append(_snapshot(room, player, budget, ans=cmd_start_ans))
                    redo_stack.clear()
                    item = _chest_loot(cur.kind)
                    _chest_sid = cur.scroll_id            # a chest may name its own scroll
                    room.kill_entity(cur)
                    budget.spend(1)
                    if item == 'key':
                        _reg_write(player, '"',
                                   entity_clip(Entity(kind='floor_key', row=cur.row, col=cur.col)),
                                   is_delete=True)
                        _push('You found a key!')
                    elif item == 'heart':
                        player.heal(2)
                        _push('You found a heart! HP restored.')
                    else:
                        _push('You found a scroll!')
                    interacted = True
                    _drop = _SCROLL_DROPS.get(level)
                    if _chest_sid:
                        # This chest names a specific scroll (e.g. the Waypoint
                        # nook → the Numbered Ledger). Grant it and show it via
                        # the standard catalog renderer.
                        extras = progress.get('extras', [])
                        if _chest_sid not in extras:
                            progress['extras'] = extras + [_chest_sid]
                        if _chest_sid not in player.known_commands:
                            player.known_commands = player.known_commands + [_chest_sid]
                        render_all(term, dungeon, player, budget, _pool_msg(), attack_pos=_attack_pos(), attack_sym=_attack_sym())
                        _show_catalog_scroll(term, _iw(term), term.height - 8, _chest_sid,
                                             _known_from_progress(progress))
                    elif _drop is not None:
                        _sid, _txt_title, _txt_body, _show_fn = _drop
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
                        render_all(term, dungeon, player, budget, _pool_msg(), attack_pos=_attack_pos(), attack_sym=_attack_sym())
                        # Gate the scroll's smudged lines on what the player has
                        # actually learned (their whole progress), not this level's
                        # frozen command set — otherwise replaying an early boss
                        # re-smudges commands learned in later levels.
                        _show_fn(term, _iw(term), term.height - 8, _known_from_progress(progress))
                    else:
                        # No scroll assigned to this level: pull a random, not-yet-
                        # discovered "safe" relic scroll from the library.
                        _wid = _pick_relic_scroll(progress.get('extras', []))
                        if _wid is not None:
                            progress['extras'] = progress.get('extras', []) + [_wid]
                            if _wid not in player.known_commands:
                                player.known_commands = player.known_commands + [_wid]
                            render_all(term, dungeon, player, budget, _pool_msg(), attack_pos=_attack_pos(), attack_sym=_attack_sym())
                            _show_catalog_scroll(term, _iw(term), term.height - 8, _wid,
                                                 _known_from_progress(progress))
                        else:
                            _push('The scroll case is empty — you hold every relic scroll.')
                elif cur and cur.kind == 'keystone':
                    undo_stack.append(_snapshot(room, player, budget, ans=cmd_start_ans))
                    redo_stack.clear()
                    room.kill_entity(cur)
                    budget.spend(1)
                    remaining = sum(
                        1 for e in room._entity_by_kind.get('keystone', [])
                        if e.alive
                    )
                    if remaining == 0:
                        _push('All keystones collected — the exit is open!')
                    else:
                        _push(f'Keystone collected ({remaining} remaining).')
                    interacted = True
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
                elif cur and cur.kind in ('goblin', 'warden'):
                    cur.hp -= 1
                    budget.spend(1)
                    interacted = True
                    # The Surveyor uses its own two-phase visual/teleport AI
                    # (wired separately); it never leaps-and-summons like the Keep.
                    if cur.kind == 'warden' and cur.hp > 0 and cur.tag != 'surveyor':
                        move_msg = _do_warden_move(room, cur, player)
                        if move_msg:
                            _push(move_msg)
                        _side = random.choice((-1, 1))
                        _spawn_goblin(room, cur.row, cur.col + _side * 3, summoner_uid=cur.uid)
                        cur.summon_timer = _WARDEN_SUMMON_INTERVAL
                        _push('The Warden summoned a goblin minion!')
                    elif cur.kind == 'warden' and cur.hp > 0 and cur.tag == 'surveyor':
                        if cur.hp == 3:                      # just entered Phase 2 (2 HP spent)
                            _surveyor_regen()                # the eaten verse regrows
                            _push('The sentences regrow — his sight will frame you in blocks!')
                        _surveyor_teleport(cur)              # leap away (60% into a parenthetical)
                        room.surveyor_threat = {'step': 'recover'}   # a tick to regain focus before re-entering visual mode
                        _push('The Warden leaps — you broke his focus!')
                    if cur.hp <= 0:
                        room.kill_entity(cur)
                        _reg_write(player, '"', entity_clip(cur), is_delete=True)
                        if cur.kind == 'warden':
                            _remove_warden_shields(room)
                            room.surveyor_threat = None      # clear any lingering telegraph
                        _push(_on_kill(cur, player, room, level) or 'Enemy defeated!')
                    else:
                        _push(f'Hit! ({cur.hp}/{cur.max_hp} HP)')
                elif cur and cur.kind == 'shield':
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
                    cut_items = []
                    for _ci in range(count):
                        item = _ed_cut(room, player.row, player.col + _ci)
                        if item:
                            cut_items.append(item)
                    if cut_items:
                        undo_stack.append(_snapshot(room, player, budget, ans=cmd_start_ans))
                        redo_stack.clear()
                        _reg_write(player, '"',
                                   _clip_from_cut_chars(cut_items, player.col), is_delete=True)
                        if is_ledge(room, player.row):
                            close_gap(room, player.row, player.col, count)   # ledge: pull the tail left
                        budget.spend(1)
                        descs = ', '.join(_clip_desc(i) for i in cut_items)
                        _push(f'Cut {len(cut_items)}: {descs}')
                        player.last_change = action
                        seal_msg = _check_seal_broken(room)
                        if seal_msg:
                            _push(seal_msg)

        elif not edit_mode and action['type'] == 'substitute':
            if not _action_allowed(action, player.known_commands):
                _push(_guard_message(action, player.known_commands))
                message = _pool_msg(); msg_ttl = _MSG_ROTATE_TTL
                render_all(term, dungeon, player, budget, message, attack_pos=_attack_pos(), attack_sym=_attack_sym())
                continue
            undo_stack.append(_snapshot(room, player, budget, ans=cmd_start_ans))
            redo_stack.clear()
            begin_insert(room, player, 'S' if action.get('line') else 's', count)
            player.mode = Mode.INSERT
            budget.spend(1)
            player.last_change = action

        elif edit_mode and action['type'] == 'substitute':
            ed_undo.append(_ed_snapshot(room, player))
            ed_redo.clear()
            all_items: list = []
            for _si in range(count):
                all_items.extend(_ed_subst(room, player.row, player.col + _si))
            player.edit_clip = all_items
            _push('Substituted: ' + ', '.join(_clip_desc(i) for i in all_items))
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
                    render_all(term, dungeon, player, budget, _pool_msg(), attack_pos=_attack_pos(), attack_sym=_attack_sym())
                    _unlock_animation(term, room, player,
                                      target.row, target.col,
                                      _iw(term), term.height - 8, _kclr)
                    _kill_door_group(room, target.row, target.col, kind='locked_door')
                    player.row, player.col = target.row, target.col   # paste moves you over: step onto the unlocked door
                    _reveal_from(room, player.row, player.col)
                    budget.spend(_keystroke_cost(count, 'p'))
                    _push('Door unlocked!')
                else:
                    _has_key = any(ed['tmpl'].get('kind') == 'floor_key' for ed in clip_entities)
                    player.error = 'E: Wrong key for this door' if _has_key else 'E: No key held'
            elif clip and any(rw.get('char_runs') or rw.get('entities') for rw in clip['rows']):
                # One register for everything cut/yanked: lay characters back down and
                # respawn cut creatures. count fans out copies (3p = 3 in a row).
                undo_stack.append(_snapshot(room, player, budget, ans=cmd_start_ans))
                redo_stack.clear()
                if op_paste(room, player, clip, before, count):
                    budget.spend(_keystroke_cost(count, 'p'))
                    spawned = next((ed['tmpl']['kind'] for ed in clip_entities), None)
                    _push(_PASTE_SPAWN_MSG[spawned] if spawned in _PASTE_SPAWN_MSG else 'Pasted.')
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
            if not edit_mode and not _action_allowed(action, player.known_commands):
                _push(_guard_message(action, player.known_commands))
                message = _pool_msg(); msg_ttl = _MSG_ROTATE_TTL
                render_all(term, dungeon, player, budget, message, attack_pos=_attack_pos(), attack_sym=_attack_sym())
                continue
            (ed_undo if edit_mode else undo_stack).append(
                _ed_snapshot(room, player) if edit_mode else _snapshot(room, player, budget))
            (ed_redo if edit_mode else redo_stack).clear()
            if replace_chars(room, player, action['char'], count):
                if not edit_mode:
                    budget.spend(2 + (len(str(count)) if count > 1 else 0))
                player.last_change = action
            else:
                (ed_undo if edit_mode else undo_stack).pop()
                _push('Nothing to replace.')

        elif action['type'] == 'case_char':
            if not edit_mode and not _action_allowed(action, player.known_commands):
                _push(_guard_message(action, player.known_commands))
                message = _pool_msg(); msg_ttl = _MSG_ROTATE_TTL
                render_all(term, dungeon, player, budget, message, attack_pos=_attack_pos(), attack_sym=_attack_sym())
                continue
            (ed_undo if edit_mode else undo_stack).append(
                _ed_snapshot(room, player) if edit_mode else _snapshot(room, player, budget))
            (ed_redo if edit_mode else redo_stack).clear()
            if case_char(room, player, count):
                if not edit_mode:
                    budget.spend(_keystroke_cost(count, '~'))
                player.last_change = action
            else:
                (ed_undo if edit_mode else undo_stack).pop()
                _push('Nothing to toggle.')

        elif action['type'] == 'join' and not edit_mode:
            if not _action_allowed(action, player.known_commands):
                _push(_guard_message(action, player.known_commands))
                message = _pool_msg(); msg_ttl = _MSG_ROTATE_TTL
                render_all(term, dungeon, player, budget, message, attack_pos=_attack_pos(), attack_sym=_attack_sym())
                continue
            undo_stack.append(_snapshot(room, player, budget))
            redo_stack.clear()
            gap = action.get('gap', True)
            if op_join(room, player, gap=gap, count=count):
                budget.spend(_keystroke_cost(count, 'J' if gap else 'gJ'))
                player.last_change = action
                _push(_EDGE_OF_WORLD_MSG if room._last_build_blocked == 'edge' else 'Joined.')
            else:
                undo_stack.pop()
                _push(_EDGE_OF_WORLD_MSG if room._last_build_blocked == 'edge' else 'Nothing to join.')

        elif action['type'] == 'operator' and action['op'] in ('>', '<'):
            if not edit_mode and not _action_allowed(action, player.known_commands):
                _push(_guard_message(action, player.known_commands))
                message = _pool_msg(); msg_ttl = _MSG_ROTATE_TTL
                render_all(term, dungeon, player, budget, message, attack_pos=_attack_pos(), attack_sym=_attack_sym())
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
                    if room._last_void_falls:
                        render_all(term, dungeon, player, budget, message, attack_pos=_attack_pos(), attack_sym=_attack_sym())
                        _play_void_falls(term, dungeon, room, player)
                        message = 'Over the brink — into the void it tumbles!'; msg_ttl = 25
                    if room._last_drowns:
                        render_all(term, dungeon, player, budget, message, attack_pos=_attack_pos(), attack_sym=_attack_sym())
                        for (dr, dc) in room._last_drowns:
                            _drown_animation(term, *_void_screen_xy(term, room, player, dr, dc))
                        room._last_drowns = []
                        message = 'A wave sweeps it away into the void!'; msg_ttl = 25
                player.last_change = action

        elif action['type'] == 'operator' and action['op'] in ('g~', 'gu', 'gU'):
            if not edit_mode and not _action_allowed(action, player.known_commands):
                _push(_guard_message(action, player.known_commands))
                message = _pool_msg(); msg_ttl = _MSG_ROTATE_TTL
                render_all(term, dungeon, player, budget, message, attack_pos=_attack_pos(), attack_sym=_attack_sym())
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
            if not _action_allowed(action, player.known_commands):
                _push(_guard_message(action, player.known_commands))
                message = _pool_msg(); msg_ttl = _MSG_ROTATE_TTL
                render_all(term, dungeon, player, budget, message, attack_pos=_attack_pos(), attack_sym=_attack_sym())
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
                else:                          # 'd'
                    _reg_write(player, reg, op_delete(room, player, tobj, collapse=True), is_delete=True)
                    budget.spend(_operator_cost(action))
                    _push('Deleted.')
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
                    render_all(term, dungeon, player, budget, _pool_msg(), attack_pos=_attack_pos(), attack_sym=_attack_sym())
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

        # ── Combat: enemy movement then adjacency attacks ────────────────────
        if not edit_mode:
            xd_id     = (id(cur_combat_target)
                         if action['type'] == 'interact' and cur_combat_target
                         else None)
            tick_msgs = _enemy_tick(room, player)
            _surveyor_tick()                  # the Surveyor's telegraph → resolve cadence

            # Any enemy now adjacent attacks (except the one the player just hit,
            # and except enemies that only became adjacent this turn — player gets
            # one free turn when landing next to a new enemy via fg/motion).
            attackers = []
            for ent in (*room._entity_by_kind.get('goblin', []),
                        *room._entity_by_kind.get('warden', [])):
                if not ent.alive:
                    continue
                if id(ent) == xd_id:
                    continue
                if id(ent) not in prev_adjacent_ids:
                    continue
                if _manhattan(player.row, player.col, ent.row, ent.col) <= _ATTACK_RADIUS:
                    attackers.append(ent)
                    player.take_damage(1)
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

            # Warden summon message
            if tick_msgs and not player.is_dead:
                _push(tick_msgs[0])

            # Engagement: fire for any attacker now adjacent
            if attackers:
                for _ae in attackers:
                    if id(_ae) not in engaged_entities:
                        engaged_entities.add(id(_ae))
                        _aname = 'Warden' if _ae.kind == 'warden' else _ae.kind
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
                        _push('Type p to put the key in the lock.')
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

        render_all(term, dungeon, player, budget, message, attack_pos=_attack_pos(), attack_sym=_attack_sym())


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
                return ('load', name)

        render_save_select(term, saves, cursor, deleting=pending_d)


# ── Scroll library loop ───────────────────────────────────────────────────────

def run_scroll_library(term: Terminal, player: Player, progress: dict) -> str | None:
    """Show the scroll library (~/.vimny/scrolls/). Marks opened scrolls as seen.

    Returns None  → back to overworld
            'parent' → go up to ~/.vimny/ parent view
            'saves'  → open character select
    """
    from render.scroll_library import render_scroll_library, library_rows

    _rows = library_rows()

    _SL_COMPLETIONS = ['../', 'saves/', 'world/']

    _known = _known_from_progress(progress)
    _SCROLL_DISPATCH = {
        'register':  lambda t, iw, gh: _show_register_tutorial(t, iw, gh, progress),
        'leap':      lambda t, iw, gh: _show_warden_leap_scroll(t, iw, gh, _known),
        'visual':    lambda t, iw, gh: _show_warden_sight_scroll(t, iw, gh, _known),
        'setnum':    lambda t, iw, gh: _show_waypoint_scroll(t, iw, gh, _known),
        'd_op':      lambda t, iw, gh: _show_operator_codex_scroll(t, iw, gh, _known),
        'y_op':      lambda t, iw, gh: _show_archivists_method_scroll(t, iw, gh, _known),
        'text_obj':  lambda t, iw, gh: _show_whole_word_scroll(t, iw, gh, _known),
        'visual_op': lambda t, iw, gh: _show_warden_act_scroll(t, iw, gh, _known),
        # Relic scrolls — all use the standard lines/segs/cmd renderer.
        'set_more':          lambda t, iw, gh: _render_standard_scroll(t, iw, gh, SETTERS_HAND_SCROLL, _known),
        'regex_classes':     lambda t, iw, gh: _render_standard_scroll(t, iw, gh, REGEX_CLASSES_SCROLL, _known),
        'regex_anchors':     lambda t, iw, gh: _render_standard_scroll(t, iw, gh, REGEX_ANCHORS_SCROLL, _known),
        'regex_quant':       lambda t, iw, gh: _render_standard_scroll(t, iw, gh, REGEX_QUANTIFIERS_SCROLL, _known),
        'regex_collections': lambda t, iw, gh: _render_standard_scroll(t, iw, gh, REGEX_COLLECTIONS_SCROLL, _known),
        'regex_magic':       lambda t, iw, gh: _render_standard_scroll(t, iw, gh, REGEX_MAGIC_SCROLL, _known),
        'searchcraft':       lambda t, iw, gh: _render_standard_scroll(t, iw, gh, SEARCH_CRAFT_SCROLL, _known),
        'jump':              lambda t, iw, gh: _render_standard_scroll(t, iw, gh, WANDERERS_THREAD_SCROLL, _known),
        'col_motion':        lambda t, iw, gh: _render_standard_scroll(t, iw, gh, PLUMB_LINE_SCROLL, _known),
        'ins_paste':         lambda t, iw, gh: _render_standard_scroll(t, iw, gh, RECALLING_HAND_SCROLL, _known),
        'ins_edit':          lambda t, iw, gh: _render_standard_scroll(t, iw, gh, QUICK_ERASE_SCROLL, _known),
    }

    discovered  = set(progress.get('extras', []))
    # start on the first actual scroll (skip ../ ./ and the first subtree header)
    cursor_row  = next((i for i, r in enumerate(_rows) if r['type'] == 'scroll'), 0)
    cmd_active  = False
    cmd_line    = ''
    tab_matches: list[str] = []
    tab_idx     = -1

    def _render():
        render_scroll_library(term, player, progress, cursor_row,
                              cmd_line if cmd_active else None)

    _render()

    while True:
        key = term.inkey(timeout=0.1)
        if not key:
            continue

        if cmd_active:
            if key.name == 'KEY_ESCAPE':
                cmd_active  = False
                cmd_line    = ''
                tab_matches = []
                tab_idx     = -1
            elif str(key) == '\t':
                if cmd_line == 'e' or cmd_line.startswith('e '):
                    partial = cmd_line[2:] if cmd_line.startswith('e ') else ''
                    new_m   = [c for c in _SL_COMPLETIONS if c.startswith(partial)]
                    if new_m:
                        if new_m != tab_matches:
                            tab_matches, tab_idx = new_m, 0
                        else:
                            tab_idx = (tab_idx + 1) % len(tab_matches)
                        cmd_line = 'e ' + tab_matches[tab_idx]
            elif key.name == 'KEY_ENTER' or str(key) in ('\n', '\r'):
                cmd         = cmd_line.strip()
                cmd_active  = False
                cmd_line    = ''
                tab_matches = []
                tab_idx     = -1
                if cmd in ('q', 'q!'):
                    return None
                _e_path = cmd[2:].rstrip('/') if cmd.startswith('e ') else ''
                if _e_path in ('..', '../'):
                    return 'parent'
                if _e_path in ('saves',):
                    return 'saves'
                if _e_path in ('world',):
                    return None
            elif key.name == 'KEY_BACKSPACE' or str(key) == '\x7f':
                cmd_line    = cmd_line[:-1]
                tab_matches = []
                tab_idx     = -1
            else:
                cmd_line    = _cmd_append(cmd_line, key)
                tab_matches = []
                tab_idx     = -1
            _render()
            continue

        raw = str(key) if not key.is_sequence else ''

        if key.name == 'KEY_ESCAPE':
            return None
        elif raw == ':':
            cmd_active = True
            cmd_line   = ''
        elif raw == '-':
            return 'parent'
        elif raw == 'j':
            cursor_row = min(cursor_row + 1, len(_rows) - 1)
        elif raw == 'k':
            cursor_row = max(cursor_row - 1, 0)
        elif key.name == 'KEY_ENTER' or raw in ('\n', '\r'):
            _r = _rows[cursor_row]
            if _r['type'] == 'parent':
                return 'parent'
            elif _r['type'] in ('self', 'subhdr'):
                pass  # ./ or a subtree header — stay
            else:
                scroll = _r['scroll']
                if scroll['id'] in discovered:
                    iw     = _iw(term)
                    game_h = term.height - 5
                    _render()
                    _SCROLL_DISPATCH[scroll['id']](term, iw, game_h)
                    seen = list(progress.get('scrolls_seen', []))
                    if scroll['id'] not in seen:
                        seen.append(scroll['id'])
                        progress['scrolls_seen'] = seen
                        SM.save_progress(progress, player.name)

        _render()


# ── Color palette loop (~/.vimny/colors/) ────────────────────────────────────

def run_colors(term: Terminal, player: Player) -> None:
    """Show the color palette (admin only). Returns when the player exits."""
    from render.color_palette import render_color_palette, content_row_count

    scroll_top = 0
    cmd_active = False
    cmd_line   = ''

    def _max_scroll() -> int:
        from render.utils import inner_w as _iw
        game_h    = term.height - 5
        reserved  = 7  # 6 hdr rows + ../
        visible_h = max(0, game_h - reserved)
        return max(0, content_row_count() - visible_h)

    def _render():
        render_color_palette(term, player, scroll_top,
                             cmd_line if cmd_active else None)

    _render()

    while True:
        key = term.inkey(timeout=0.1)
        if not key:
            continue

        if cmd_active:
            if key.name == 'KEY_ESCAPE':
                cmd_active = False
                cmd_line   = ''
            elif key.name == 'KEY_ENTER' or str(key) in ('\n', '\r'):
                cmd        = cmd_line.strip()
                cmd_active = False
                cmd_line   = ''
                if cmd in ('q', 'q!') or cmd.startswith('e '):
                    return
            elif key.name == 'KEY_BACKSPACE' or str(key) == '\x7f':
                cmd_line = cmd_line[:-1]
            else:
                cmd_line = _cmd_append(cmd_line, key)
            _render()
            continue

        raw = str(key) if not key.is_sequence else ''

        if key.name == 'KEY_ESCAPE' or raw == '-':
            return
        elif raw == ':':
            cmd_active = True
            cmd_line   = ''
        elif raw == 'j':
            scroll_top = min(scroll_top + 1, _max_scroll())
        elif raw == 'k':
            scroll_top = max(scroll_top - 1, 0)

        _render()


# ── Parent directory loop (~/.vimny/) ─────────────────────────────────────────

def run_parent_dir(term: Terminal, player: Player, progress: dict) -> str | None:
    """Show the ~/.vimny/ parent directory.

    Returns None       → back to overworld (Esc or 'world/' selected)
            'scrolls'  → open scroll library
            'saves'    → open character select
            'colors'   → open color palette (admin only)
    """
    from render.parent_dir import render_parent_dir, entries_for

    entries = entries_for(player)
    _PD_COMPLETIONS = ['saves/', 'scrolls/', 'world/'] + (
        ['colors/'] if player.name == 'admin' else []
    )

    cursor_row  = 2  # 0=../ 1=./ 2+=entries
    cmd_active  = False
    cmd_line    = ''
    tab_matches: list[str] = []
    tab_idx     = -1

    def _render():
        render_parent_dir(term, player, cursor_row,
                          cmd_line if cmd_active else None)

    _render()

    while True:
        key = term.inkey(timeout=0.1)
        if not key:
            continue

        if cmd_active:
            if key.name == 'KEY_ESCAPE':
                cmd_active  = False
                cmd_line    = ''
                tab_matches = []
                tab_idx     = -1
            elif str(key) == '\t':
                if cmd_line == 'e' or cmd_line.startswith('e '):
                    partial = cmd_line[2:] if cmd_line.startswith('e ') else ''
                    new_m   = [c for c in _PD_COMPLETIONS if c.startswith(partial)]
                    if new_m:
                        if new_m != tab_matches:
                            tab_matches, tab_idx = new_m, 0
                        else:
                            tab_idx = (tab_idx + 1) % len(tab_matches)
                        cmd_line = 'e ' + tab_matches[tab_idx]
            elif key.name == 'KEY_ENTER' or str(key) in ('\n', '\r'):
                cmd         = cmd_line.strip()
                cmd_active  = False
                cmd_line    = ''
                tab_matches = []
                tab_idx     = -1
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
            elif key.name == 'KEY_BACKSPACE' or str(key) == '\x7f':
                cmd_line    = cmd_line[:-1]
                tab_matches = []
                tab_idx     = -1
            else:
                cmd_line    = _cmd_append(cmd_line, key)
                tab_matches = []
                tab_idx     = -1
            _render()
            continue

        raw = str(key) if not key.is_sequence else ''

        if key.name == 'KEY_ESCAPE':
            return None
        elif raw == ':':
            cmd_active = True
            cmd_line   = ''
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

def _ow_section(lines: list, cursor: int, direction: int) -> int:
    """{ / } over the overworld buffer: the first line of the prev/next section
    (comments → dirs → levels → customs)."""
    grp = {'comment': 'c', 'parent': 'd', 'self': 'd', 'level': 'l',
           'subhdr': 'x', 'custom': 'x'}
    starts, prev = [], None
    for i, ln in enumerate(lines):
        g = grp.get(ln['type'])
        if g != prev:
            starts.append(i); prev = g
    if direction < 0:
        before = [s for s in starts if s < cursor]
        return before[-1] if before else 0
    after = [s for s in starts if s > cursor]
    return after[0] if after else len(lines) - 1


def run_overworld(term: Terminal, player: Player, progress: dict,
                  initial_cursor: int | None = None) -> dict:
    """The netrw overworld (~/.vimny/world/) as a real netrw buffer.

    Every line — the `"` comments, ../ ./, the levels, custom layouts — is a
    selectable cursor position. Motions match what the player has learned: j/k
    always; counts, gg/G, {n}G, H/M/L, {/} once learned; Ctrl-d/u/f/b page the
    view. D deletes a custom layout (y to confirm), R renames it, d/dd hit the
    read-only buffer; :set number/relativenumber/nonumber toggle the gutter.

    Returns {'action': 'enter'|'open_custom'|'browse_saves'|'scrolls'|'parent_view'|'quit', ...}.
    """
    _OW_COMPLETIONS = ['../', 'saves/', 'scrolls/']

    visible = [l for l in LEVELS if not l.get('admin_only') or player.name == 'admin']

    def _layouts():
        return SM.list_layouts() if player.name == 'admin' else []

    customs = _layouts()
    lines   = build_lines(visible, customs)
    cursor  = default_cursor(lines) if initial_cursor is None else initial_cursor
    cursor  = max(0, min(cursor, len(lines) - 1))

    learned  = _known_from_progress(progress)
    is_admin = player.name == 'admin'
    def _has(tok): return is_admin or tok in learned
    def _gate(tok, label):
        if _has(tok):
            return True
        player.error = f"You haven't learned {label} yet."
        return False

    number_mode    = 'number'
    cmd_active     = False
    cmd_line       = ''
    renaming       = None        # None, or the in-progress new-name buffer
    pending_delete = False
    pending_g      = False
    count_buf      = ''
    scroll_offset  = 0
    tab_matches: list[str] = []
    tab_idx        = -1
    avail          = max(1, term.height - 5)

    def _rebuild():
        nonlocal customs, lines, cursor
        customs = _layouts()
        lines   = build_lines(visible, customs)
        cursor  = max(0, min(cursor, len(lines) - 1))

    def _render():
        nonlocal scroll_offset
        scroll_offset, cy, cx = render_overworld(
            term, player, progress, cursor, lines,
            cmd_line=cmd_line if cmd_active else None,
            number_mode=number_mode, deleting=pending_delete,
            renaming=renaming, scroll_offset=scroll_offset)
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
                renaming = None
            elif key.name == 'KEY_ENTER' or str(key) in ('\n', '\r'):
                ln = lines[cursor]
                if ln['type'] == 'custom' and renaming.strip():
                    SM.rename_layout(ln['layout'].get('layout_name', ''), renaming.strip())
                    _rebuild()
                renaming = None
            elif key.name == 'KEY_BACKSPACE' or str(key) == '\x7f':
                renaming = renaming[:-1]
            elif not key.is_sequence and len(str(key)) == 1 and str(key).isprintable():
                renaming += str(key)
            _render()
            continue

        # ── Command mode ──────────────────────────────────────────────────────
        if cmd_active:
            if key.name == 'KEY_ESCAPE':
                cmd_active  = False
                cmd_line    = ''
                tab_matches = []
                tab_idx     = -1
            elif str(key) == '\t':
                if cmd_line == 'e' or cmd_line.startswith('e '):
                    partial  = cmd_line[2:] if cmd_line.startswith('e ') else ''
                    new_m    = [c for c in _OW_COMPLETIONS if c.startswith(partial)]
                    if new_m:
                        if new_m != tab_matches:
                            tab_matches, tab_idx = new_m, 0
                        else:
                            tab_idx = (tab_idx + 1) % len(tab_matches)
                        cmd_line = 'e ' + tab_matches[tab_idx]
            elif key.name == 'KEY_ENTER' or str(key) in ('\n', '\r'):
                cmd         = cmd_line.strip()
                cmd_active  = False
                cmd_line    = ''
                tab_matches = []
                tab_idx     = -1
                if cmd in ('q', 'q!', 'wq'):
                    if cmd == 'wq':
                        SM.save_progress(progress, player.name)
                    return _done({'action': 'quit', 'cursor': cursor})
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
                        return _done({'action': 'browse_saves', 'cursor': cursor})
                    if _e_path in ('scrolls',):
                        return _done({'action': 'scrolls', 'cursor': cursor})
                    if _e_path in ('..', '../'):
                        return _done({'action': 'parent_view', 'cursor': cursor})
                    # Unknown commands silently ignored
            elif key.name == 'KEY_BACKSPACE' or str(key) == '\x7f':
                cmd_line    = cmd_line[:-1]
                tab_matches = []
                tab_idx     = -1
            else:
                cmd_line    = _cmd_append(cmd_line, key)
                tab_matches = []
                tab_idx     = -1
            _render()
            continue

        # ── Navigation ──────────────────────────────────────────────────────────
        raw = str(key) if not key.is_sequence else ''
        player.error = ''                              # clear any transient message
        ln        = lines[cursor]
        on_custom = ln['type'] == 'custom'
        last      = len(lines) - 1

        # D — delete a custom layout (netrw deletes with D); confirm with y.
        if pending_delete:
            pending_delete = False
            count_buf = ''
            if raw == 'y' and on_custom:
                SM.delete_layout(ln['layout'].get('layout_name', ''))
                _rebuild()
            _render()
            continue                                   # any non-y key cancels

        # gg — jump to the first line
        if pending_g:
            pending_g = False
            if raw == 'g':
                cursor    = 0
                count_buf = ''
                _render()
                continue
            # not 'gg' → fall through

        # count prefix ('0' alone is not a count)
        if raw.isdigit() and (raw != '0' or count_buf):
            count_buf += raw
            _render()
            continue
        n_given = bool(count_buf)
        n = int(count_buf) if count_buf else 1
        count_buf = ''

        if raw == ':':
            cmd_active = True
            cmd_line   = ''
        elif raw == '-':
            return _done({'action': 'parent_view', 'cursor': cursor})
        elif raw == 'j':
            if n <= 1 or _gate('count', 'counts'):
                cursor = min(cursor + n, last)
        elif raw == 'k':
            if n <= 1 or _gate('count', 'counts'):
                cursor = max(cursor - n, 0)
        elif raw == 'g':
            pending_g = True
        elif raw == 'G':                               # {n}G → line n; bare G → last line
            if (n <= 1 or _gate('count', 'counts')) and _gate('G', 'G'):
                cursor = max(0, min(n - 1, last)) if n_given else last
        elif raw == 'H':
            if _gate('H', 'H'):
                cursor = min(scroll_offset, last)
        elif raw == 'M':
            if _gate('M', 'M'):
                vc = min(avail, last - scroll_offset + 1)
                cursor = min(scroll_offset + (vc - 1) // 2, last)
        elif raw == 'L':
            if _gate('L', 'L'):
                cursor = min(scroll_offset + avail - 1, last)
        elif raw == '{':
            if _gate('{', '{'):
                cursor = _ow_section(lines, cursor, -1)
        elif raw == '}':
            if _gate('}', '}'):
                cursor = _ow_section(lines, cursor, +1)
        elif raw == '\x04':                            # Ctrl-d — half page down
            cursor = min(cursor + avail // 2, last)
        elif raw == '\x15':                            # Ctrl-u — half page up
            cursor = max(cursor - avail // 2, 0)
        elif raw == '\x06':                            # Ctrl-f — page down
            cursor = min(cursor + avail, last)
        elif raw == '\x02':                            # Ctrl-b — page up
            cursor = max(cursor - avail, 0)
        elif raw == 'D':                               # netrw delete (custom only)
            if on_custom:
                pending_delete = True
            else:
                player.error = "Can't delete a built-in dungeon — only your own custom layouts."
        elif raw == 'R':                               # netrw rename (custom only)
            if on_custom:
                renaming = ln['layout'].get('layout_name', '')
            else:
                player.error = "Can't rename a built-in dungeon — only your own custom layouts."
        elif raw == 'd':                               # read-only buffer (netrw is read-only)
            player.error = 'The overworld is read-only — press D to delete a custom layout.'
        elif key.name == 'KEY_ENTER' or raw in ('\n', '\r'):
            t = ln['type']
            if t == 'parent':
                return _done({'action': 'parent_view', 'cursor': cursor})
            elif t == 'level':
                lid = ln['level']['slug']
                if is_unlocked(lid, progress, player.name):
                    return _done({'action': 'enter', 'level': lid, 'cursor': cursor})
            elif t == 'custom':
                return _done({'action': 'open_custom', 'layout': ln['layout'], 'cursor': cursor})
            # comment / self / subhdr → no-op

        _render()


# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser(description='Vimny — Vim dungeon crawler')
    ap.add_argument('--level', type=str, default=None,
                    choices=['first_cave', 'line_halls', 'reliquary', 'counting_crypts',
                             'rune_halls', 'character_cataracts', 'goblin_gauntlet',
                             'wardens_keep', 'word_forge', 'backward_vaults', 'lineheads',
                             'warden_surveyor', 'sight_sanctum', 'seekers_labyrinth',
                             'waypoint_sanctum', 'archivists_library', 'dummy'],
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
            if aux in ('browse_saves', 'scrolls', 'parent_view', 'colors'):
                while aux in ('browse_saves', 'scrolls', 'parent_view', 'colors'):
                    if aux == 'browse_saves':
                        sel_action, sel_name = run_save_select(term)
                        if sel_action == 'load' and sel_name:
                            player.name = sel_name
                            save_data   = SM.load_for(player.name) or {}
                            progress    = SM.load_progress(save_data)
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

            if ow_result['action'] == 'open_custom':
                layout  = ow_result['layout']
                room    = _deserialize_room(layout)
                dungeon = Dungeon(name=layout.get('layout_name', 'Custom'), seed=0)
                dungeon.rooms        = [room]
                dungeon.current_room = 0
                run_dungeon(term, 'first_cave', progress, player.name,
                            _dungeon=dungeon, _start_edit=True)
                continue

            level = ow_result['level']

            # Pre-game blessing: wizard bestows hjkl poem before every attempt
            # at the First Cave until the player has earned at least 1 star there.
            if level == 'first_cave' and progress.get('first_cave', {}).get('stars', 0) == 0:
                run_wizard_blessing(term, select_quote_by_name('home row'))

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
                run_wizard_blessing(
                    term,
                    select_next_lesson_quote(level),
                )



if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        pass
