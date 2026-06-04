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
        nonlocal case_one, case_run
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


def _sub_line(text: str, kinds: list, default_kind: str, vp, rep: str,
              glob: bool, count_only: bool):
    """(new_text, new_kinds, n) for one line. Replaces the effective span of each match
    (zs/ze aware); non-`g` stops after the first. Unchanged characters keep their kind;
    replacement characters take `default_kind`."""
    tp: list = []
    kp: list = []
    last = 0
    n = 0
    for m in vp.match_iter(text):
        s, e = vp.eff_span(m)
        if s < last:                            # zero-width tangle — skip safely
            continue
        tp.append(text[last:s]); kp.append(kinds[last:s])
        gg = _grouper(m, s, e, text)

        if count_only:
            tp.append(text[s:e]); kp.append(kinds[s:e])
        else:
            rt = _expand(rep, gg)
            tp.append(rt); kp.append([default_kind] * len(rt))
        last = e
        n += 1
        if not glob:
            break
    if n == 0:
        return text, kinds, 0
    tp.append(text[last:]); kp.append(kinds[last:])
    return ''.join(tp), [k for part in kp for k in part], n


# ── addresses & ranges ───────────────────────────────────────────────────────
def _read_addr(s: str, i: int, room, player):
    """Parse one address at s[i:] → (row|None, new_i). None = absent address."""
    n = len(s)
    base = None
    if i < n and s[i] == '.':
        base = player.row; i += 1
    elif i < n and s[i] == '$':
        base = room.rows - 1; i += 1
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
        base = int(s[i:j]) - 1                  # 1-based line → 0-based row
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
def _split_sep(body: str, sep: str):
    """Split a /pat/rep/flags body on the separator, honouring backslash-escapes.
    Returns [pat, rep, flagtail] (missing parts as None)."""
    parts: list = []
    cur: list = []
    i, n = 0, len(body)
    while i < n:
        c = body[i]
        if c == '\\' and i + 1 < n:
            cur.append(c); cur.append(body[i + 1]); i += 2; continue
        if c == sep:
            parts.append(''.join(cur)); cur = []; i += 1
            if len(parts) == 2:                 # everything after the 2nd sep is the flag tail
                parts.append(body[i:]); cur = []; i = n
            continue
        cur.append(c); i += 1
    if cur or len(parts) < 1:
        parts.append(''.join(cur))
    while len(parts) < 3:
        parts.append(None)
    return parts[0], parts[1], parts[2]


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
        player.row = last_changed
        player.col = _first_nonblank_col(room, last_changed)

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
    """Like _sub_line but asks confirm(row, col_start, col_end) per match.
    Returns (new_text, new_kinds, n)."""
    tp, kp, last, n = [], [], 0, 0
    stop = False
    for m in vp.match_iter(text):
        s, e = vp.eff_span(m)
        if s < last:
            continue
        tp.append(text[last:s]); kp.append(kinds[last:s])
        ans = 'n' if stop else confirm(row, lo + s, lo + e)
        if ans == 'q':
            stop = True; ans = 'n'
        elif ans == 'a':
            ans = 'y'; confirm = (lambda *a: 'y')        # 'all' from here on this line
        if ans == 'l':                                   # last: do this one, then stop
            stop = True; ans = 'y'

        gg = _grouper(m, s, e, text)

        if ans == 'y':
            rt = _expand(rep, gg)
            tp.append(rt); kp.append([default_kind] * len(rt)); n += 1
        else:
            tp.append(text[s:e]); kp.append(kinds[s:e])
        last = e
        if not glob or stop:
            break
    tp.append(text[last:]); kp.append(kinds[last:])
    return ''.join(tp), [k for part in kp for k in part], n


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


def _first_nonblank_col(room, row):
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
    j, n, pat = 0, len(body), []
    while j < n:
        if body[j] == '\\' and j + 1 < n:
            pat.append(body[j:j + 2]); j += 2; continue
        if body[j] == sep:
            j += 1; break
        pat.append(body[j]); j += 1
    pattern = ''.join(pat)
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
            if delete_row is not None and delete_row(row):
                n += 1
            elif delete_row is None:
                from engine.reflow import remove_row
                if remove_row(room, row, player):
                    n += 1
        player.row = min(player.row, room.rows - 1)
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
