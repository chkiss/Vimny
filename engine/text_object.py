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

"""Block A — TextObject: the range an operator (d/y/c) acts on.

A motion run as an operator target produces a TextObject describing the grid
span to operate on. This is the Vimny (2D grid + CharRun) analogue of the
prompt_toolkit pattern — re-implemented here, not copied: the span is computed
by running the existing, tested `apply_motion` on a cloned cursor position.
"""
from __future__ import annotations
from dataclasses import dataclass
from enum import Enum, auto

from engine.motion import apply_motion, _sentence_starts


class TextObjectType(Enum):
    EXCLUSIVE = auto()   # charwise; the cell the motion lands on is NOT included
    INCLUSIVE = auto()   # charwise; the landing cell IS included
    LINEWISE  = auto()   # whole rows start_row..end_row


@dataclass
class TextObject:
    start_row: int
    start_col: int
    end_row:   int
    end_col:   int
    type:      TextObjectType


# Motion → operator-target classification. Charwise only; linewise handled below.
_INCLUSIVE = frozenset({'e', 'E', '$', 'f', 'F', 't', 'T', '%'})
_LINEWISE  = frozenset({'line', 'j', 'k', 'G', 'gg'})
# everything else charwise (h l w b W B 0 ^ ge gE { } ( )) is EXCLUSIVE


def _word_end(room, row: int, cur, WORD: bool) -> int:
    """End column of the word/WORD the cursor's cluster `cur` belongs to.
    For a WORD, coalesce adjacent non-void clusters with no floor gap."""
    end = cur.col + len(cur.symbols) - 1
    if WORD:
        cc = end + 1
        while cc < room.cols and room.is_passable(row, cc):
            r2 = room.char_run_at(row, cc)
            if r2 is not None and r2.kind != 'void':
                end = r2.col + len(r2.symbols) - 1
                cc = end + 1
            else:
                break
    return end


def classify(motion: str) -> TextObjectType:
    if motion in _LINEWISE:
        return TextObjectType.LINEWISE
    if motion in _INCLUSIVE:
        return TextObjectType.INCLUSIVE
    return TextObjectType.EXCLUSIVE


def compute_text_object(player, action: dict, room) -> TextObject | None:
    """Build the TextObject an operator action targets, without moving the player.

    `action` is an operator dict: {'op','motion','count','motion_count','target'?}.
    Returns None if the motion produces no span (e.g. it could not move).
    """
    motion = action['motion']
    count  = action.get('count', 1)
    mc     = action.get('motion_count', 1)
    sr, sc = player.row, player.col

    # dd / yy / cc : `count` whole rows starting at the cursor row.
    if motion == 'line':
        er = min(sr + count - 1, room.rows - 1)
        return TextObject(sr, 0, er, room.cols - 1, TextObjectType.LINEWISE)

    # Vim special case: cw/cW with the cursor *in* a word change only up to the
    # end of the word (like ce/cE) — NOT the trailing whitespace that dw eats.
    # (Only when the cursor sits on a non-void rune; on blanks cw behaves as dw.)
    if action.get('op') == 'c' and motion in ('w', 'W'):
        cur = room.char_run_at(sr, sc)
        if cur is not None and cur.kind != 'void':
            end_col = _word_end(room, sr, cur, WORD=(motion == 'W'))
            n = count * mc
            if n > 1:                       # c{n}w → end of the nth word
                save = (player.row, player.col, player.last_f)
                player.row, player.col = sr, end_col
                apply_motion(player, 'E' if motion == 'W' else 'e', n - 1, room,
                             entity_stops=False)
                end_col = player.col
                player.row, player.col, player.last_f = save
            if end_col >= sc:
                return TextObject(sr, sc, sr, end_col, TextObjectType.INCLUSIVE)

    # Run the real motion on a cloned cursor to find where it lands.
    save_row, save_col, save_f = player.row, player.col, player.last_f
    apply_motion(player, motion, count * mc, room, action.get('target'),
                 count_given=action.get('motion_count_given', True),
                 entity_stops=False)
    dr, dc = player.row, player.col
    player.row, player.col, player.last_f = save_row, save_col, save_f

    if motion in _LINEWISE:        # j k G gg — whole-row span
        lo_r, hi_r = sorted((sr, dr))
        return TextObject(lo_r, 0, hi_r, room.cols - 1, TextObjectType.LINEWISE)

    if dr != sr:                   # a charwise motion that crossed rows: treat linewise
        lo_r, hi_r = sorted((sr, dr))
        return TextObject(lo_r, 0, hi_r, room.cols - 1, TextObjectType.LINEWISE)

    if dc == sc:                   # motion did not move → empty span
        return None
    lo, hi = sorted((sc, dc))
    return TextObject(sr, lo, sr, hi, classify(motion))


# ── Block K: text objects (iw aw, brackets, quotes, angle, sentence, paragraph) ─
#
# resolve_text_object computes a span from the cursor position (not a motion).
# `textobj` is a canonical 2-char string: kind ('i'|'a') + object char, where the
# parser has already normalised aliases (ib->i(, iB->i{, close brackets/quotes to
# their canonical form). Tags (it/at) resolve single-row <name>…</name> pairs.

_PAIRS = {'(': ('(', ')'), '[': ('[', ']'), '{': ('{', '}'), '<': ('<', '>')}


def _sym_at(room, row, col):
    ru = room.char_run_at(row, col)
    return ru.symbols[col - ru.col] if ru is not None else None


def _row_bounds(room, row):
    """Passable [lo, hi] column extent of a row (between walls), or None."""
    cols = [c for c in range(room.cols) if room.is_passable(row, c)]
    return (cols[0], cols[-1]) if cols else None


def _row_blank(room, row) -> bool:
    """A text-blank row: passable but holding no characters. All-wall rows are not blank."""
    if _row_bounds(room, row) is None:
        return False
    return not any(room.char_run_at(row, c) is not None for c in range(room.cols))


def _resolve_word(room, r, c, around, big=False):
    """iw/aw (small word: one glyph CLASS — Vim's iskeyword vs punctuation)
    and iW/aW (big WORD: any contiguous glyphs, whitespace-bounded)."""
    from engine.motion import _is_word_char
    bounds = _row_bounds(room, r)
    if bounds is None:
        return None
    lo, hi = bounds

    def _cls(col):
        if not (lo <= col <= hi) or not room.is_passable(r, col):
            return None
        rr = room.char_run_at(r, col)
        if rr is None or rr.kind == 'void':
            return None
        if big:
            return 'G'                              # any glyph: one WORD
        ch = rr.symbols[col - rr.col]
        return 'w' if _is_word_char(ch) else 'p'    # Vim's word classes

    ru = room.char_run_at(r, c)
    if ru is not None and ru.kind != 'void':
        k = _cls(c)
        ws = c
        while _cls(ws - 1) == k:
            ws -= 1
        we = c
        while _cls(we + 1) == k:
            we += 1
        if not around:
            return TextObject(r, ws, r, we, TextObjectType.INCLUSIVE)
        t = we + 1                                  # trailing whitespace run
        while t <= hi and room.is_passable(r, t) and room.char_run_at(r, t) is None:
            t += 1
        if t - 1 > we:
            return TextObject(r, ws, r, t - 1, TextObjectType.INCLUSIVE)
        s = ws - 1                                  # else leading whitespace
        while s >= lo and room.is_passable(r, s) and room.char_run_at(r, s) is None:
            s -= 1
        return TextObject(r, s + 1, r, we, TextObjectType.INCLUSIVE)
    # cursor on a blank cell: the contiguous blank run
    if not (lo <= c <= hi) or not room.is_passable(r, c) or room.char_run_at(r, c) is not None:
        return None
    s = c
    while s - 1 >= lo and room.is_passable(r, s - 1) and room.char_run_at(r, s - 1) is None:
        s -= 1
    e = c
    while e + 1 <= hi and room.is_passable(r, e + 1) and room.char_run_at(r, e + 1) is None:
        e += 1
    if around and e + 1 <= hi and room.char_run_at(r, e + 1) is not None:
        nru = room.char_run_at(r, e + 1)
        e = nru.col + len(nru.symbols) - 1
    return TextObject(r, s, r, e, TextObjectType.INCLUSIVE)


def _resolve_pair(room, r, c, around, open_ch, close_ch):
    bounds = _row_bounds(room, r)
    if bounds is None:
        return None
    lo, hi = bounds
    open_col, depth = None, 0
    cc = c
    while cc >= lo:                                 # scan left for enclosing open
        s = _sym_at(room, r, cc)
        if cc == c:
            if s == open_ch:
                open_col = cc
                break
        elif s == close_ch:
            depth += 1
        elif s == open_ch:
            if depth == 0:
                open_col = cc
                break
            depth -= 1
        cc -= 1
    if open_col is None:
        return None
    close_col, depth = None, 0
    cc = open_col + 1
    while cc <= hi:                                 # scan right for its match
        s = _sym_at(room, r, cc)
        if s == open_ch:
            depth += 1
        elif s == close_ch:
            if depth == 0:
                close_col = cc
                break
            depth -= 1
        cc += 1
    if close_col is None:
        return None
    if around:
        return TextObject(r, open_col, r, close_col, TextObjectType.INCLUSIVE)
    if open_col + 1 > close_col - 1:
        return None                                 # empty pair: nothing inside
    return TextObject(r, open_col + 1, r, close_col - 1, TextObjectType.INCLUSIVE)


def _resolve_quote(room, r, c, around, q):
    bounds = _row_bounds(room, r)
    if bounds is None:
        return None
    lo, hi = bounds
    quotes = [cc for cc in range(lo, hi + 1) if _sym_at(room, r, cc) == q]
    pairs = [(quotes[i], quotes[i + 1]) for i in range(0, len(quotes) - 1, 2)]
    chosen = next((p for p in pairs if p[0] <= c <= p[1]), None)
    if chosen is None:
        chosen = next((p for p in pairs if p[0] > c), None)
    if chosen is None:
        return None
    o, cl = chosen
    if around:
        # Vim-true a-quote whitespace: a" spans the quotes PLUS the trailing
        # whitespace (all of it, up to the next glyph) — or, when nothing
        # trails, the leading whitespace instead. This is why da" leaves the
        # single gap `w1 w2` where da( left the double-gap scar.
        end = cl
        cc = cl + 1
        while (cc <= hi and _sym_at(room, r, cc) is None
               and room.is_passable(r, cc)):
            end = cc
            cc += 1
        if end > cl:
            return TextObject(r, o, r, end, TextObjectType.INCLUSIVE)
        start = o
        cc = o - 1
        while (cc >= lo and _sym_at(room, r, cc) is None
               and room.is_passable(r, cc)):
            start = cc
            cc -= 1
        return TextObject(r, start, r, cl, TextObjectType.INCLUSIVE)
    if o + 1 > cl - 1:
        return None
    return TextObject(r, o + 1, r, cl - 1, TextObjectType.INCLUSIVE)


def _resolve_tag(room, r, c, around):
    """it/at — the innermost <name>…</name> pair enclosing the cursor, on the
    cursor's row (dungeon tags are single-row inscriptions). `it` spans the
    content between the tags; `at` spans open tag through close tag. Nesting
    honoured: a stack pairs each </name> with its matching <name>."""
    bounds = _row_bounds(room, r)
    if bounds is None:
        return None
    lo, hi = bounds
    line = ''.join(_sym_at(room, r, cc) or ' ' for cc in range(lo, hi + 1))

    import re
    stack, pairs = [], []
    for m in re.finditer(r'<(/?)([A-Za-z][A-Za-z0-9]*)>', line):
        closing, name = m.group(1), m.group(2)
        if not closing:
            stack.append((name, m.start(), m.end()))       # open: '<' .. past '>'
        elif stack and stack[-1][0] == name:
            _n, o_start, o_end = stack.pop()
            pairs.append((o_start, o_end, m.start(), m.end()))
    if not pairs:
        return None
    cur = c - lo
    # innermost pair containing the cursor (anywhere from '<' of the open tag
    # to '>' of the close tag) — smallest enclosing span wins
    containing = [p for p in pairs if p[0] <= cur < p[3]]
    if not containing:
        return None
    o_s, o_e, c_s, c_e = min(containing, key=lambda p: p[3] - p[0])
    if around:
        return TextObject(r, lo + o_s, r, lo + c_e - 1, TextObjectType.INCLUSIVE)
    if o_e > c_s - 1:
        return None                                        # empty content: <a></a>
    return TextObject(r, lo + o_e, r, lo + c_s - 1, TextObjectType.INCLUSIVE)


def _resolve_paragraph(room, r, c, around):
    if _row_blank(room, r):
        top = bot = r
        while top - 1 >= 0 and _row_blank(room, top - 1):
            top -= 1
        while bot + 1 < room.rows and _row_blank(room, bot + 1):
            bot += 1
        return TextObject(top, 0, bot, room.cols - 1, TextObjectType.LINEWISE)
    top = bot = r
    while top - 1 >= 0 and _row_bounds(room, top - 1) is not None and not _row_blank(room, top - 1):
        top -= 1
    while bot + 1 < room.rows and _row_bounds(room, bot + 1) is not None and not _row_blank(room, bot + 1):
        bot += 1
    if around:
        b = bot
        while b + 1 < room.rows and _row_blank(room, b + 1):
            b += 1
        if b > bot:
            bot = b
        else:
            t = top
            while t - 1 >= 0 and _row_blank(room, t - 1):
                t -= 1
            top = t
    return TextObject(top, 0, bot, room.cols - 1, TextObjectType.LINEWISE)


def _resolve_sentence(room, r, c, around):
    starts = _sentence_starts(room, r)
    bounds = _row_bounds(room, r)
    if not starts or bounds is None:
        return None
    lo, hi = bounds
    s = lo
    for st in starts:
        if st <= c:
            s = st
        else:
            break
    nxt = next((st for st in starts if st > s), None)
    if nxt is not None:
        e = nxt - 1
    else:
        e = max((ru.col + len(ru.symbols) - 1 for ru in room._char_runs_by_row.get(r, [])), default=hi)
        if around:
            # Vim-true as on the LAST sentence: nothing trails, so the
            # object eats the LEADING whitespace instead (the a-quote rule,
            # sentence flavour) — das leaves no straggling gap at line end.
            while (s > lo and room.char_run_at(r, s - 1) is None
                   and room.is_passable(r, s - 1)):
                s -= 1
    if not around:                                  # trim trailing blanks for inner
        while e > s and room.char_run_at(r, e) is None:
            e -= 1
    return TextObject(r, s, r, e, TextObjectType.INCLUSIVE)


def resolve_text_object(textobj: str, room, player) -> TextObject | None:
    """Resolve a canonical text object (e.g. 'iw', 'i(', 'a"', 'ip') at the cursor."""
    if not textobj or len(textobj) < 2:
        return None
    around = textobj[0] == 'a'
    obj = textobj[1]
    r, c = player.row, player.col
    if obj == 'w':
        return _resolve_word(room, r, c, around)
    if obj == 'W':
        return _resolve_word(room, r, c, around, big=True)
    if obj in _PAIRS:
        return _resolve_pair(room, r, c, around, *_PAIRS[obj])
    if obj in ('"', "'", '`'):
        return _resolve_quote(room, r, c, around, obj)
    if obj == 'p':
        return _resolve_paragraph(room, r, c, around)
    if obj == 's':
        return _resolve_sentence(room, r, c, around)
    if obj == 't':
        return _resolve_tag(room, r, c, around)
    return None
