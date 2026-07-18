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

"""Ex substitute & global — :s, :g / :v, and the & repeats.

Vim's :s and :g operate on LINES. Vimny rows ARE lines, so a "line" here is the
wall-bounded text of a row: its non-void glyphs in place, gaps read as spaces
(``line_text``). Substitution rewrites that string through the reflow primitives
(``set_line_text``) — content shoved past the right wall falls off the brink,
exactly like every other edit. Void runes and water are terrain: read as spaces
and left untouched (:s/:g levels are built without them in the worked lines).

Public surface (the only thing main.py needs):
    run_ex(cmd, room, player, *, confirm=None, insert_row=None, delete_row=None)
        -> (handled: bool, message: str|None, n_subs: int, n_lines: int)

`confirm(row, start, end) -> 'y'|'n'|'a'|'q'|'l'` drives the :s ``c`` flag.
`insert_row` / `delete_row` are callbacks into the host's reflow so marks/jumplist
shift with the rows; tests pass simple stand-ins.

Supported, matching Vim:
  ranges      (none=., %, N, ., $, 'x, '<'>, addr±N, a,b / a;b)
  :s flags    g  c  i  I  n  e  &(keep flags)   + a trailing count
  separator   any non-alnum, non-space, non-backslash char (:s#a#b#)
  empty pat   reuse the last search / substitute pattern
  replacement &  \\0-\\9  ~(last replacement)  \\u \\U \\l \\L \\E  \\r(split) \\t \\n \\\\
  repeats     :s  :&  (no flags)   :&&  g&  & (normal)   with last pat/rep/flags
  :g/:v       :g/pat/cmd  :g!/pat/cmd  :v/pat/cmd   over d, s///, and p(no-op)
"""
from __future__ import annotations
from engine.world import CellType, CharRun
from engine.vimregex import compile_sub

_WALLS = (CellType.WALL, CellType.WOOD_WALL)


# ── line text ↔ row ──────────────────────────────────────────────────────────
def _bounds(room, row: int):
    """(lo, hi): the writable column span of a row, just inside its border walls."""
    cols = room.cols
    lo = 0
    while lo < cols and room.cells[row][lo] in _WALLS:
        lo += 1
    hi = cols
    while hi > lo and room.cells[row][hi - 1] in _WALLS:
        hi -= 1
    return lo, hi


def _read_line(room, row: int):
    """(text, lo, hi, kinds): the row as ONE Vim line — EVERY glyph in place (void
    runes included; they are text, not terrain), gaps→spaces, trailing gap trimmed.
    `kinds[i]` is the glyph's colour-kind at column lo+i (None for a gap), aligned to
    text so a substitution can carry each unchanged character's kind through."""
    lo, hi = _bounds(room, row)
    chars = [' '] * max(0, hi - lo)
    kinds: list = [None] * max(0, hi - lo)
    for ru in room._char_runs_by_row.get(row, []):
        for i, s in enumerate(ru.symbols):
            c = ru.col + i
            if lo <= c < hi:
                chars[c - lo] = s
                kinds[c - lo] = ru.kind
    text = ''.join(chars).rstrip(' ')
    return text, lo, hi, kinds[:len(text)]


def line_text(room, row: int):
    """(text, lo, hi): the row as a Vim line string. See _read_line."""
    text, lo, hi, _kinds = _read_line(room, row)
    return text, lo, hi


def line_kind(room, row: int) -> str:
    """The default colour for replacement text: the line's first content (non-void)
    kind — so a substitution writes ordinary runes, and turning a void rune into
    text fills the hole (it no longer reads as the deadly void kind)."""
    for ru in room._char_runs_by_row.get(row, []):
        if ru.kind != 'void':
            return ru.kind
    return 'ancient'


def set_line_text(room, row: int, text: str, lo: int, hi: int,
                  kinds: list, default_kind: str) -> None:
    """Lay `text` (with its per-char `kinds`) onto the row from column lo; glyphs past
    hi fall off the brink. Removes EVERY old glyph on the row (void included) and
    re-lays from the new text, so void runes are real, editable text."""
    from engine.editor import _merge_adjacent_char_runs
    for ru in list(room._char_runs_by_row.get(row, [])):
        room.remove_char_run(ru)
    for i, ch in enumerate(text):
        c = lo + i
        if c >= hi:
            break
        if ch == ' ':
            continue
        k = kinds[i] if i < len(kinds) and kinds[i] is not None else default_kind
        room.add_char_run(CharRun(row, c, (ch,), k))
    _merge_adjacent_char_runs(room, row)


# ── replacement expansion ────────────────────────────────────────────────────
def _expand(rep: str, get_group) -> str:
    """Vim :s replacement → string. get_group(i): i==0 the whole (effective) match,
    1-9 the capture. Honours & \\0-\\9 \\u\\U\\l\\L\\E \\r(→newline) \\t \\n(→NUL) \\\\."""
    out: list = []
    case_one = None        # 'u'|'l' — fold the next char
    case_run = None        # 'U'|'L' — fold until \E
    i, n = 0, len(rep)

    def emit(s: str):
        nonlocal case_one                  # case_run is only read here
        for ch in s:
            if case_one == 'u':
                ch = ch.upper(); case_one = None
            elif case_one == 'l':
                ch = ch.lower(); case_one = None
            elif case_run == 'U':
                ch = ch.upper()
            elif case_run == 'L':
                ch = ch.lower()
            out.append(ch)

    while i < n:
        c = rep[i]
        if c == '\\' and i + 1 < n:
            nx = rep[i + 1]; i += 2
            if nx.isdigit():
                emit(get_group(int(nx)))
            elif nx == 'r':
                out.append('\n')               # newline — splits the line (not folded)
            elif nx == 'n':
                emit('\x00')                   # Vim: \n in a replacement is a NUL
            elif nx == 't':
                emit('\t')
            elif nx == 'u':
                case_one = 'u'
            elif nx == 'l':
                case_one = 'l'
            elif nx == 'U':
                case_run = 'U'
            elif nx == 'L':
                case_run = 'L'
            elif nx in 'eE':
                case_run = None
            else:
                emit(nx)                       # \& \~ \\ \/ … → literal
            continue
        if c == '&':
            emit(get_group(0)); i += 1; continue
        emit(c); i += 1
    return ''.join(out)


def _grouper(m, s: int, e: int, text: str):
    """A replacement group-getter for `_expand`: 0 → the effective match text [s,e),
    1-9 → capture group n (or '' when the group didn't participate / doesn't exist)."""
    def gg(i):
        if i == 0:
            return text[s:e]
        try:
            g = m.group(i)
        except IndexError:
            g = None
        return g or ''
    return gg


def _sub_line_core(text, kinds, vp, glob, decide):
    """Rewrite one line by walking non-overlapping (zs/ze-aware) matches. For each
    match, `decide(m, s, e)` returns (out_text, out_kinds, counted, stop): the text
    and per-char kinds to emit for the match span, whether it counts toward `n`
    (a real change), and whether to stop after it (overriding `glob`). Returns
    (new_text, new_kinds, n)."""
    tp: list = []
    kp: list = []
    last = 0
    n = 0
    for m in vp.match_iter(text):
        s, e = vp.eff_span(m)
        if s < last:                            # zero-width tangle — skip safely
            continue
        tp.append(text[last:s]); kp.append(kinds[last:s])
        out_text, out_kinds, counted, stop = decide(m, s, e)
        tp.append(out_text); kp.append(out_kinds)
        last = e
        if counted:
            n += 1
        if stop or not glob:
            break
    tp.append(text[last:]); kp.append(kinds[last:])
    return ''.join(tp), [k for part in kp for k in part], n


def _sub_line(text: str, kinds: list, default_kind: str, vp, rep: str,
              glob: bool, count_only: bool):
    """(new_text, new_kinds, n) for one line. Replaces the effective span of each match
    (zs/ze aware); non-`g` stops after the first. Unchanged characters keep their kind;
    replacement characters take `default_kind`."""
    def decide(m, s, e):
        if count_only:                          # :s///n — count matches, change nothing
            return text[s:e], kinds[s:e], True, False
        rt = _expand(rep, _grouper(m, s, e, text))
        return rt, [default_kind] * len(rt), True, False
    return _sub_line_core(text, kinds, vp, glob, decide)


# ── addresses & ranges ───────────────────────────────────────────────────────
def _last_standable_row(room) -> int:
    """Grid row of the LAST buffer line — mirrors Room.first_standable_row()."""
    for r in range(room.rows - 1, -1, -1):
        if any(room.cells[r][c] in (CellType.FLOOR, CellType.CORRIDOR)
               for c in range(room.cols)):
            return r
    return room.rows - 1


def _read_addr(s: str, i: int, room, player):
    """Parse one address at s[i:] → (row|None, new_i). None = absent address.
    Line numbers follow the gutter: line 1 = first_standable_row() (borders are
    not lines), exactly as {n}G lands — so :3d strikes the row `:set nu` calls 3."""
    n = len(s)
    base = None
    if i < n and s[i] == '.':
        base = player.row; i += 1
    elif i < n and s[i] == '$':
        base = _last_standable_row(room); i += 1
    elif i < n and s[i] == "'" and i + 1 < n:
        mk = s[i + 1]; i += 2
        if mk == '<' and player.last_visual_anchor is not None:
            base = min(player.last_visual_anchor[0], player.last_visual_cursor[0])
        elif mk == '>' and player.last_visual_anchor is not None:
            base = max(player.last_visual_anchor[0], player.last_visual_cursor[0])
        elif mk in player.marks:
            base = player.marks[mk][0]
        else:
            return None, i
    elif i < n and s[i].isdigit():
        j = i
        while j < n and s[j].isdigit():
            j += 1
        base = room.first_standable_row() + int(s[i:j]) - 1   # gutter line → row
        i = j
    # offsets:  +N / -N (repeatable)
    while i < n and s[i] in '+-':
        sign = 1 if s[i] == '+' else -1
        i += 1
        j = i
        while j < n and s[j].isdigit():
            j += 1
        step = int(s[i:j]) if j > i else 1
        base = (player.row if base is None else base) + sign * step
        i = j
    return base, i


def split_range(cmd: str, room, player):
    """(lo, hi, rest): consume a leading line range, return the 0-based inclusive
    row span and the remaining command. No range → current line. `%` → whole file."""
    i = 0
    if cmd[:1] == '%':
        return 0, room.rows - 1, cmd[1:]
    a, i = _read_addr(cmd, 0, room, player)
    if i < len(cmd) and cmd[i] in ',;':
        if cmd[i] == ';' and a is not None:
            player_row0 = player.row
            player.row = a                      # ';' moves the cursor before addr2
            b, i = _read_addr(cmd, i + 1, room, player)
            player.row = player_row0
        else:
            b, i = _read_addr(cmd, i + 1, room, player)
        lo = player.row if a is None else a
        hi = player.row if b is None else b
    else:
        lo = hi = (player.row if a is None else a)
    lo = max(0, min(lo, room.rows - 1))
    hi = max(0, min(hi, room.rows - 1))
    if lo > hi:
        lo, hi = hi, lo
    return lo, hi, cmd[i:]


# ── :s parsing ───────────────────────────────────────────────────────────────
def _scan_field(body: str, sep: str, i: int = 0):
    """Scan one separator-delimited field from `body` starting at `i`, honouring
    backslash-escapes (an escaped sep is kept literally). Returns
    (field_text, next_i, found_sep): next_i is just past the consumed separator,
    or len(body) when the field ran to the end with no separator."""
    cur: list = []
    n = len(body)
    while i < n:
        c = body[i]
        if c == '\\' and i + 1 < n:
            cur.append(c); cur.append(body[i + 1]); i += 2; continue
        if c == sep:
            return ''.join(cur), i + 1, True
        cur.append(c); i += 1
    return ''.join(cur), i, False


def _split_sep(body: str, sep: str):
    """Split a /pat/rep/flags body on the separator, honouring backslash-escapes.
    Returns (pat, rep, flagtail) with missing parts as None (a rep that ends the
    body with no closing sep, e.g. ':s/a/', counts as absent)."""
    pat, i, found1 = _scan_field(body, sep, 0)
    if not found1:
        return pat, None, None
    rep, i, found2 = _scan_field(body, sep, i)
    if not found2:
        return pat, (rep or None), None
    return pat, rep, body[i:]


def parse_sub(rest: str, player):
    """Parse the substitute command body (rest begins at 's', '&', or a separator).
    Returns dict(pat, rep, flags:set, count:int|None) or None if not a substitute."""
    flags_keep = False
    if rest[:2] == '&&':
        flags_keep = True; body_is_repeat = True; tail = rest[2:]
    elif rest[:1] == '&':
        body_is_repeat = True; tail = rest[1:]
    elif rest[:1] == 's':
        body_is_repeat = False; tail = rest[1:]
    else:
        return None

    if body_is_repeat or tail == '' or tail[0].isalnum() or tail[0] in ' \t':
        # :s / :& / :&& / :s g3 — repeat last substitute; parse trailing flags+count
        if player.last_sub is None:
            return {'repeat': True, 'pat': None, 'rep': None,
                    'flags': set(), 'count': None, 'keep': flags_keep}
        flags, count = _parse_flagtail(tail)
        return {'repeat': True, 'pat': None, 'rep': None,
                'flags': flags, 'count': count, 'keep': flags_keep}

    sep = tail[0]
    pat, rep, ftail = _split_sep(tail[1:], sep)
    flags, count = _parse_flagtail(ftail or '')
    return {'repeat': False, 'pat': pat, 'rep': rep or '',
            'flags': flags, 'count': count, 'keep': flags_keep}


def _parse_flagtail(tail: str):
    """A trailing 'g3', ' c', 'gic 5' … → (flagset, count|None)."""
    flags: set = set()
    count = None
    tail = (tail or '').strip()
    num = ''
    for ch in tail:
        if ch in 'gciIne&':
            flags.add(ch)
        elif ch.isdigit():
            num += ch
        elif ch == ' ':
            if num:
                count = int(num); num = ''
        # unknown flags ignored (Vim would error; we're lenient)
    if num:
        count = int(num)
    return flags, count


# ── apply :s ─────────────────────────────────────────────────────────────────
def _resolve_pattern(pat, player):
    """Empty pattern → the last search/substitute pattern (Vim-faithful)."""
    if pat:
        return pat
    if player.last_sub is not None and player.last_sub[0]:
        return player.last_sub[0]
    if player.last_search is not None:
        return player.last_search[0]
    return None


def substitute(room, player, lo, hi, spec, *, confirm=None,
               insert_row=None, delete_row=None):
    """Run a parsed :s over rows [lo, hi]. Returns (message, n_subs, n_lines)."""
    if spec.get('repeat'):
        if player.last_sub is None:
            return 'E33: No previous substitute regular expression', 0, 0
        pat, rep, last_flags = player.last_sub
        flags = set(last_flags) if spec.get('keep') else set()
        flags |= (spec['flags'] - {'&'})        # any flags typed on the repeat add in
    else:
        pat = _resolve_pattern(spec['pat'], player)
        rep = spec['rep']
        flags = spec['flags']
        if '&' in flags and player.last_sub is not None:
            flags = (flags - {'&'}) | set(player.last_sub[2])

    if not pat:
        return 'E35: No previous regular expression', 0, 0

    ignorecase = True if 'i' in flags else (False if 'I' in flags else None)
    vp = compile_sub(pat, ignorecase)
    if vp is None:
        return f'E486: Pattern not found: {pat}', 0, 0

    glob       = 'g' in flags
    count_only = 'n' in flags
    confirming = 'c' in flags and confirm is not None
    rep = _resolve_replacement(rep, player)

    count = spec.get('count')
    if count:                                   # a trailing count: act on `count` lines from hi
        lo = hi
        hi = min(room.rows - 1, lo + count - 1)

    n_subs = n_lines = 0
    last_changed = None
    # Descending so a \r line-split (which inserts rows below) never reindexes a
    # row we have yet to visit.
    for row in range(hi, lo - 1, -1):
        text, l0, l1, kinds = _read_line(room, row)
        dkind = line_kind(room, row)
        if confirming:
            new_text, new_kinds, n = _sub_line_confirm(
                text, kinds, dkind, vp, rep, glob, confirm, row, l0)
        else:
            new_text, new_kinds, n = _sub_line(
                text, kinds, dkind, vp, rep, glob, count_only)
        if n == 0:
            continue
        n_subs += n
        n_lines += 1
        if last_changed is None:
            last_changed = row
        if not count_only:
            _write_line(room, player, row, new_text, new_kinds, l0, l1, dkind, insert_row)

    if n_subs == 0:
        if 'e' in flags:                        # the 'e' flag: no error when nothing matched
            return None, 0, 0
        return f'E486: Pattern not found: {pat}', 0, 0

    player.last_sub = (pat, rep, ''.join(sorted(flags & set('gcInie'))))
    player.last_search = (pat, True)            # :s sets the last search pattern too
    if last_changed is not None and not count_only:
        c = _first_glyph_col(room, last_changed)
        if room.is_passable(last_changed, c):    # the avatar has feet: a ranged
            player.row = last_changed            # :s onto unwalkable ground (a
            player.col = c                       # misted ledger) never ferries it

    if count_only:
        return f'{n_subs} matches on {n_lines} lines', n_subs, n_lines
    if n_subs == 1:
        return None, n_subs, n_lines
    return f'{n_subs} substitutions on {n_lines} lines', n_subs, n_lines


def _resolve_replacement(rep, player):
    """Resolve an unescaped ~ to the previous replacement string (Vim-faithful)."""
    if rep is None:
        return ''
    if '~' not in rep:
        return rep
    prev = player.last_sub[1] if player.last_sub is not None else ''
    out, i, n = [], 0, len(rep)
    while i < n:
        if rep[i] == '\\' and i + 1 < n:
            out.append(rep[i:i + 2]); i += 2; continue
        if rep[i] == '~':
            out.append(prev); i += 1; continue
        out.append(rep[i]); i += 1
    return ''.join(out)


def _sub_line_confirm(text, kinds, default_kind, vp, rep, glob, confirm, row, lo):
    """Like _sub_line but asks confirm(row, col_start, col_end) per match
    (the `c` flag's y/n/q/a/l flow). Returns (new_text, new_kinds, n)."""
    state = {'stop': False, 'confirm': confirm}

    def decide(m, s, e):
        ans = 'n' if state['stop'] else state['confirm'](row, lo + s, lo + e)
        if ans == 'q':
            state['stop'] = True; ans = 'n'
        elif ans == 'a':
            ans = 'y'; state['confirm'] = lambda *a: 'y'   # 'all' from here on this line
        if ans == 'l':                                     # last: do this one, then stop
            state['stop'] = True; ans = 'y'

        if ans == 'y':
            rt = _expand(rep, _grouper(m, s, e, text))
            return rt, [default_kind] * len(rt), True, state['stop']
        return text[s:e], kinds[s:e], False, state['stop']

    return _sub_line_core(text, kinds, vp, glob, decide)


def _write_line(room, player, row, new_text, new_kinds, lo, hi, default_kind, insert_row):
    """Write new_text (+ its kinds) to a row; a '\\n' (from \\r) splits it into rows below."""
    if '\n' not in new_text:
        set_line_text(room, row, new_text, lo, hi, new_kinds, default_kind)
        return
    seg_t, seg_k, ct, ck = [], [], [], []       # split text & kinds together on each newline
    for ch, k in zip(new_text, new_kinds):
        if ch == '\n':
            seg_t.append(''.join(ct)); seg_k.append(ck); ct, ck = [], []
        else:
            ct.append(ch); ck.append(k)
    seg_t.append(''.join(ct)); seg_k.append(ck)
    set_line_text(room, row, seg_t[0], lo, hi, seg_k[0], default_kind)
    for idx in range(1, len(seg_t)):
        if insert_row is not None:
            insert_row(row + idx - 1)
        set_line_text(room, row + idx, seg_t[idx], lo, hi, seg_k[idx], default_kind)


def _first_glyph_col(room, row):
    """Leftmost non-void glyph column on a row (0 if the row has no glyph). Note
    this differs from motion._first_non_blank_col, which falls back to the leftmost
    passable cell — here we want the first written character after a :s rewrite."""
    runs = [ru for ru in room._char_runs_by_row.get(row, []) if ru.kind != 'void']
    return min((ru.col for ru in runs), default=0)


# ── :g / :v ──────────────────────────────────────────────────────────────────
def run_global(room, player, lo, hi, rest, *, confirm=None,
               insert_row=None, delete_row=None):
    """:[range]g/pat/cmd  — run cmd on each matching line (g! / v: non-matching).
    Supported cmd: d (delete line), s/// (substitute), p / empty (no-op)."""
    invert = False
    i = 0
    if rest[:1] == 'v':
        invert = True; i = 1
    elif rest[:1] == 'g':
        i = 1
        if i < len(rest) and rest[i] == '!':
            invert = True; i += 1
    else:
        return 'E', 0, 0
    if i >= len(rest):
        return 'E147: Cannot do :g — missing pattern', 0, 0
    sep = rest[i]
    body = rest[i + 1:]
    # split off pattern (up to the next unescaped sep); the rest is the command
    pattern, j, _ = _scan_field(body, sep, 0)
    subcmd = body[j:].strip()
    pattern = _resolve_pattern(pattern, player)
    if not pattern:
        return 'E35: No previous regular expression', 0, 0
    vp = compile_sub(pattern, None)
    if vp is None:
        return f'E486: Pattern not found: {pattern}', 0, 0
    player.last_search = (pattern, True)

    # Mark all matching (or non-matching) lines in the range FIRST.
    marked = []
    for row in range(lo, hi + 1):
        text, _l0, _l1 = line_text(room, row)
        hit = vp.first_in(text) is not None
        if hit != invert:
            marked.append(row)
    if not marked:
        return None, 0, 0

    if subcmd in ('', 'p', 'print', 'nu', 'number'):
        return f'{len(marked)} lines matched', 0, len(marked)

    if subcmd in ('d', 'delete'):
        n = 0
        for row in sorted(marked, reverse=True):    # delete bottom-up
            done = (delete_row(row) if delete_row is not None else None)
            if done is None:
                from engine.reflow import remove_row
                done = remove_row(room, row, player)
            if done:
                n += 1
                if row < player.row:                # the avatar rides its row up
                    player.row -= 1
        player.row = max(0, min(player.row, room.rows - 1))
        return f'{n} fewer lines', 0, n

    if subcmd[:1] == 's':
        spec = parse_sub(subcmd, player)
        if spec is None:
            return f'E492: Not an editor command: {subcmd}', 0, 0
        total = lines = 0
        for row in sorted(marked):              # apply per marked line (ascending)
            _msg, ns, nl = substitute(room, player, row, row, dict(spec),
                                      confirm=confirm, insert_row=insert_row,
                                      delete_row=delete_row)
            total += ns; lines += nl
        if total:
            return f'{total} substitutions on {lines} lines', total, lines
        return None, 0, 0

    return f'E492: Not an editor command: {subcmd}', 0, 0


# ── the ex-range family: :[range]d y m t > < j ───────────────────────────────
_PARRY_MSG = "The Warden's shield defended him from your cut!"


def _parse_ex_range(rest: str, room, player):
    """Parse the command tail of an ex-range command (everything after the
    range). Returns a spec dict or None if `rest` is not one of ours. Strict:
    trailing junk → None, so unknown colon commands fall through untouched."""
    for name, cmd in (('delete', 'd'), ('yank', 'y'), ('move', 'm'),
                      ('copy', 't'), ('co', 't'), ('mo', 'm'),
                      ('join', 'j'), ('t', 't'), ('m', 'm'),
                      ('d', 'd'), ('y', 'y'), ('j', 'j')):
        if not rest.startswith(name):
            continue
        tail = rest[len(name):]
        if cmd in 'dy':                        # :[range]d [reg] / :[range]y [reg]
            tail = tail.strip()
            if tail == '':
                return {'cmd': cmd, 'reg': None}
            if len(tail) == 1 and (tail.isalpha() or tail == '"'):
                return {'cmd': cmd, 'reg': tail}
            return None
        if cmd in 'mt':                        # :[range]m{addr} / :[range]t{addr}
            tail = tail.lstrip()
            dest, i = _read_addr(tail, 0, room, player)
            if dest is None or tail[i:].strip():
                return None                    # E14-territory: bad/absent address
            return {'cmd': cmd, 'dest': dest}
        if cmd == 'j':                         # :[range]j[!]
            bang = tail.startswith('!')
            if tail[1 if bang else 0:].strip():
                return None
            return {'cmd': 'j', 'bang': bang}
    if rest and rest[0] in '><' and set(rest) == {rest[0]}:
        return {'cmd': rest[0], 'depth': len(rest)}   # :[range]> / :[range]>> …
    return None


def looks_like_ex_range(cmd: str, room, player) -> bool:
    """True if cmd (after a leading range) is a d/y/m/t/>/</j ex command."""
    try:
        _lo, _hi, rest = split_range(cmd, room, player)
    except Exception:                          # noqa: BLE001
        return False
    return bool(rest) and _parse_ex_range(rest, room, player) is not None


def _rows_parried(room, lo: int, hi: int) -> bool:
    """A structural row removal is refused when any row in the span carries an
    edit-immune entity (the boss-parry rule, same as remove_row's guard)."""
    return any(e.edit_immune and lo <= e.row <= hi for e in room.entities)


def _snapshot_rows(room, lo: int, hi: int) -> list:
    """Full structural copies of rows lo..hi: cells, glyphs, fog/mist columns.
    :m/:t are ROW SURGERY, not a reflow paste — a fogged (misted-chasm) line
    moves with its terrain and its mist, so it arrives exactly as it stood
    (a reflow capture would read a fogged row as empty: line_extent is
    passability-based by design)."""
    snap = []
    for r in range(lo, hi + 1):
        snap.append((
            [room.cells[r][c] for c in range(room.cols)],
            [(ru.col, tuple(ru.symbols), ru.kind)
             for ru in room._char_runs_by_row.get(r, [])],
            {c for (fr, c) in room.fog_cells if fr == r},
            {c for (fr, c) in room.mist_cells if fr == r},
        ))
    return snap


def _lay_rows_below(room, player, snap: list, dest: int) -> int:
    """Insert structural row copies just below 0-based row `dest` (dest -1 =
    above the first line). Returns nrows.

    THE PLAYER STAYS PUT (same content row). Real Vim parks the cursor on the
    moved/copied text, but here the cursor is an avatar with feet: letting :t/:m
    carry it would be a free ferry onto any island in the game. Precedent:
    run_global's :g//d already keeps the player in place."""
    from engine.reflow import _shift_rows
    from engine.world import CellType as _CT, CharRun as _CR
    n = len(snap)
    at = max(0, dest + 1)
    for _ in range(n):
        room.cells.insert(at, [_CT.WALL] * room.cols)
    room.rows += n
    _shift_rows(room, player, lambda r: r >= at, +n)
    if at <= player.row:
        player.row = min(player.row + n, room.rows - 1)
    for k, (cells_row, runs, fogc, mistc) in enumerate(snap):
        room.cells[at + k] = list(cells_row)
        for (col, syms, kind) in runs:
            room.char_runs.append(_CR(at + k, col, syms, kind))
        room.fog_cells  |= {(at + k, c) for c in fogc}
        room.mist_cells |= {(at + k, c) for c in mistc}
    room.rebuild_indexes()
    return n


def _yank_rows_clip(room, lo: int, hi: int) -> dict:
    """A linewise register clip built GLYPH-WISE from rows lo..hi (dcol
    relative to each row's writable start), so :y reaches fogged (chasm) rows
    that a reflow capture would read as empty."""
    rows = []
    for r in range(lo, hi + 1):
        b_lo, b_hi = _bounds(room, r)
        runs = sorted(({'dcol': ru.col - b_lo, 'symbols': tuple(ru.symbols),
                        'kind': ru.kind}
                       for ru in room._char_runs_by_row.get(r, [])
                       if b_lo <= ru.col < b_hi), key=lambda d: d['dcol'])
        width = max((d['dcol'] + len(d['symbols']) for d in runs), default=0)
        rows.append({'width': width, 'char_runs': runs})
    return {'linewise': True, 'rows': rows}


def _join_rows(room, player, lo: int, hi: int, gap: bool = True) -> int:
    """The : form of J: join lines lo..hi TEXTUALLY (fog-agnostic — the
    normal-mode op_join pulls only passable glyphs and parks the cursor,
    neither of which a ranged join across a chasm may do; the avatar stays
    put via _remove_rows). Returns the number of joins performed."""
    if hi <= lo:
        return 0
    text0, l0, h0, kinds0 = _read_line(room, lo)
    base = text0.rstrip()
    text, kinds = base, list(kinds0)[:len(base)]
    for r in range(lo + 1, hi + 1):
        t, _l, _h, k = _read_line(room, r)
        ts = t.strip()
        if not ts:
            continue
        lead = len(t) - len(t.lstrip())
        if gap and text:
            text += ' '
            kinds.append(None)
        text += ts
        kinds += list(k)[lead:lead + len(ts)]
    gone = _remove_rows(room, player, lo + 1, hi)
    if not gone:
        return 0
    set_line_text(room, lo, text, l0, h0, kinds, line_kind(room, lo))
    room.rebuild_indexes()
    return gone


def _indent_rows(room, lo: int, hi: int, amount: int) -> int:
    """Shift each row's in-bounds glyphs by `amount` columns (the : form of
    >>/<<). Glyph-wise, so it reaches fogged (chasm) rows that the reflow
    apply_indent cannot (its line_extent is passability-based); dedent clamps
    at the row's writable start, indent drops glyphs pushed past its end.
    Glyphs WEST of the writable span (wall-carved plaques) never move.
    Returns how many rows changed."""
    moved = 0
    for row in range(lo, hi + 1):
        b_lo, b_hi = _bounds(room, row)
        tgt = [ru for ru in room._char_runs_by_row.get(row, [])
               if b_lo <= ru.col < b_hi]
        if not tgt:
            continue
        amt = amount
        if amt < 0:
            amt = -min(-amt, min(ru.col for ru in tgt) - b_lo)
        if amt == 0:
            continue
        for ru in tgt:
            room.remove_char_run(ru)
        for (col, syms, kind) in [(ru.col, tuple(ru.symbols), ru.kind)
                                  for ru in tgt]:
            new = col + amt
            keep = syms[:max(0, b_hi - new)]      # past the brink: dropped
            if keep:
                room.add_char_run(CharRun(row, new, keep, kind))
        moved += 1
    room.rebuild_indexes()
    return moved


def _remove_rows(room, player, lo: int, hi: int) -> int:
    """Collapse rows hi..lo (bottom-up, skipping refusals), keeping the PLAYER
    on the same content row (see _paste_rows_below on why the avatar stays put).
    Returns how many rows actually collapsed."""
    from engine.reflow import remove_row
    gone = 0
    for row in range(hi, lo - 1, -1):
        if remove_row(room, row, player):
            gone += 1
            if row < player.row:
                player.row -= 1
    player.row = max(0, min(player.row, room.rows - 1))
    return gone


def run_ex_range(room, player, lo, hi, spec):
    """Execute a parsed ex-range spec. Returns (message, n_lines_touched)."""
    from engine.operator import INDENT_WIDTH
    from engine.registers import write_register
    from engine.text_object import TextObject, TextObjectType
    c = spec['cmd']
    n = hi - lo + 1
    tobj = TextObject(lo, 0, hi, 0, TextObjectType.LINEWISE)

    if c == 'y':
        clip = _yank_rows_clip(room, lo, hi)
        write_register(player, spec['reg'], clip)
        return (f'{n} lines yanked' if n > 1 else None), n

    if c == 'd':
        if _rows_parried(room, lo, hi):
            return _PARRY_MSG, 0
        clip = _yank_rows_clip(room, lo, hi)   # capture before the collapse
        gone = _remove_rows(room, player, lo, hi)
        if not gone:
            return None, 0
        write_register(player, spec['reg'], clip, is_delete=True)
        return (f'{gone} fewer lines' if gone > 1 else None), gone

    if c == 'm':
        dest = min(spec['dest'], room.rows - 1)
        if lo <= dest <= hi:
            return 'E134: Cannot move a range of lines into itself', 0
        if _rows_parried(room, lo, hi):
            return _PARRY_MSG, 0
        snap = _snapshot_rows(room, lo, hi)    # registers untouched (:m is not a cut)
        if _remove_rows(room, player, lo, hi) != n:
            return 'E21: Cannot make changes here', 0   # a row refused to collapse
        if dest > hi:
            dest -= n
        _lay_rows_below(room, player, snap, dest)
        return (f'{n} lines moved' if n > 1 else None), n

    if c == 't':
        dest = min(spec['dest'], room.rows - 1)
        snap = _snapshot_rows(room, lo, hi)    # registers untouched
        _lay_rows_below(room, player, snap, dest)
        return (f'{n} more lines' if n > 1 else None), n

    if c in '><':
        amount = (INDENT_WIDTH * spec['depth']) * (1 if c == '>' else -1)
        moved = _indent_rows(room, lo, hi, amount)
        if not moved:
            return None, 0
        times = spec['depth']
        return (f"{moved} line{'s' if moved > 1 else ''} {c}ed "
                f"{times} time{'s' if times > 1 else ''}"), moved

    if c == 'j':
        if hi == lo:                           # bare :j joins with the next line
            hi = min(lo + 1, room.rows - 1)
        if _rows_parried(room, lo, hi):
            return _PARRY_MSG, 0
        gone = _join_rows(room, player, lo, hi, gap=not spec['bang'])
        return None, gone

    return None, 0


# ── public entry ─────────────────────────────────────────────────────────────
def looks_like_sg(cmd: str, room, player) -> bool:
    """True if cmd (after a leading range) is a substitute or global command."""
    try:
        _lo, _hi, rest = split_range(cmd, room, player)
    except Exception:                          # noqa: BLE001
        return False
    return bool(rest) and (rest[0] in 'sgv&')


def run_ex(cmd, room, player, *, confirm=None, insert_row=None, delete_row=None):
    """Execute a :s / :g / :v / :& command. Returns (handled, message, n_subs, n_lines)."""
    lo, hi, rest = split_range(cmd, room, player)
    if not rest:
        return False, None, 0, 0
    c0 = rest[0]
    if c0 in 's&':
        spec = parse_sub(rest, player)
        if spec is None:
            return False, None, 0, 0
        msg, ns, nl = substitute(room, player, lo, hi, spec,
                                 confirm=confirm, insert_row=insert_row,
                                 delete_row=delete_row)
        return True, msg, ns, nl
    if c0 in 'gv':
        k = 1
        if c0 == 'g' and k < len(rest) and rest[k] == '!':
            k += 1
        if not _is_sep(rest, k):                # a global needs g[!]<sep> or v<sep>
            return False, None, 0, 0
        if len(rest) == len(cmd):               # no explicit range → :g defaults to the WHOLE file
            lo, hi = 0, room.rows - 1
        msg, ns, nl = run_global(room, player, lo, hi, rest,
                                 confirm=confirm, insert_row=insert_row,
                                 delete_row=delete_row)
        return True, msg, ns, nl
    spec = _parse_ex_range(rest, room, player)
    if spec is not None:
        msg, nl = run_ex_range(room, player, lo, hi, spec)
        return True, msg, 0, nl
    return False, None, 0, 0


def _is_sep(s, i):
    return i < len(s) and not s[i].isalnum() and s[i] not in ' \t\\'


# ── & in normal mode / g& ─────────────────────────────────────────────────────
def repeat_normal(room, player, whole_file: bool, keep_flags: bool, *,
                  confirm=None, insert_row=None, delete_row=None):
    """& (whole_file=False, keep_flags=False) / g& (True, True): repeat last :s."""
    if player.last_sub is None:
        return 'E33: No previous substitute regular expression', 0, 0
    lo, hi = (0, room.rows - 1) if whole_file else (player.row, player.row)
    spec = {'repeat': True, 'pat': None, 'rep': None, 'flags': set(),
            'count': None, 'keep': keep_flags}
    return substitute(room, player, lo, hi, spec, confirm=confirm,
                      insert_row=insert_row, delete_row=delete_row)[0:3]
