"""Block A — TextObject: the range an operator (d/y/c) acts on.

A motion run as an operator target produces a TextObject describing the grid
span to operate on. This is the Vimny (2D grid + RuneCluster) analogue of the
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
            r2 = room.rune_at(row, cc)
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
        cur = room.rune_at(sr, sc)
        if cur is not None and cur.kind != 'void':
            end_col = _word_end(room, sr, cur, WORD=(motion == 'W'))
            n = count * mc
            if n > 1:                       # c{n}w → end of the nth word
                save = (player.row, player.col, player.last_f)
                player.row, player.col = sr, end_col
                apply_motion(player, 'E' if motion == 'W' else 'e', n - 1, room)
                end_col = player.col
                player.row, player.col, player.last_f = save
            if end_col >= sc:
                return TextObject(sr, sc, sr, end_col, TextObjectType.INCLUSIVE)

    # Run the real motion on a cloned cursor to find where it lands.
    save_row, save_col, save_f = player.row, player.col, player.last_f
    apply_motion(player, motion, count * mc, room, action.get('target'),
                 count_given=action.get('motion_count_given', True))
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
# their canonical form). Tags (it/at) are deferred — they return None here.

_PAIRS = {'(': ('(', ')'), '[': ('[', ']'), '{': ('{', '}'), '<': ('<', '>')}


def _sym_at(room, row, col):
    ru = room.rune_at(row, col)
    return ru.symbols[col - ru.col] if ru is not None else None


def _row_bounds(room, row):
    """Passable [lo, hi] column extent of a row (between walls), or None."""
    cols = [c for c in range(room.cols) if room.is_passable(row, c)]
    return (cols[0], cols[-1]) if cols else None


def _row_blank(room, row) -> bool:
    """A text-blank row: passable but holding no runes. All-wall rows are not blank."""
    if _row_bounds(room, row) is None:
        return False
    return not any(room.rune_at(row, c) is not None for c in range(room.cols))


def _resolve_word(room, r, c, around):
    bounds = _row_bounds(room, r)
    if bounds is None:
        return None
    lo, hi = bounds
    ru = room.rune_at(r, c)
    if ru is not None and ru.kind != 'void':
        ws, we = ru.col, ru.col + len(ru.symbols) - 1
        if not around:
            return TextObject(r, ws, r, we, TextObjectType.INCLUSIVE)
        t = we + 1                                  # trailing whitespace run
        while t <= hi and room.is_passable(r, t) and room.rune_at(r, t) is None:
            t += 1
        if t - 1 > we:
            return TextObject(r, ws, r, t - 1, TextObjectType.INCLUSIVE)
        s = ws - 1                                  # else leading whitespace
        while s >= lo and room.is_passable(r, s) and room.rune_at(r, s) is None:
            s -= 1
        return TextObject(r, s + 1, r, we, TextObjectType.INCLUSIVE)
    # cursor on a blank cell: the contiguous blank run
    if not (lo <= c <= hi) or not room.is_passable(r, c) or room.rune_at(r, c) is not None:
        return None
    s = c
    while s - 1 >= lo and room.is_passable(r, s - 1) and room.rune_at(r, s - 1) is None:
        s -= 1
    e = c
    while e + 1 <= hi and room.is_passable(r, e + 1) and room.rune_at(r, e + 1) is None:
        e += 1
    if around and e + 1 <= hi and room.rune_at(r, e + 1) is not None:
        nru = room.rune_at(r, e + 1)
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
        return TextObject(r, o, r, cl, TextObjectType.INCLUSIVE)
    if o + 1 > cl - 1:
        return None
    return TextObject(r, o + 1, r, cl - 1, TextObjectType.INCLUSIVE)


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
        e = max((ru.col + len(ru.symbols) - 1 for ru in room._rune_by_row.get(r, [])), default=hi)
    if not around:                                  # trim trailing blanks for inner
        while e > s and room.rune_at(r, e) is None:
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
    if obj in _PAIRS:
        return _resolve_pair(room, r, c, around, *_PAIRS[obj])
    if obj in ('"', "'", '`'):
        return _resolve_quote(room, r, c, around, obj)
    if obj == 'p':
        return _resolve_paragraph(room, r, c, around)
    if obj == 's':
        return _resolve_sentence(room, r, c, around)
    return None                                     # 't' (tag) deferred
