"""
Parse Vim-grammar keystrokes: [count][operator][motion] or [count][motion].
Returns action dicts consumed by the game loop.
"""
from __future__ import annotations
from engine.modes import Mode

MOTIONS  = set('hjklwbeWBEGg0^${}()HML%|' + ';,')
OPERATORS = set('dyc><')
COUNTS   = set('123456789')
# text-object alias normalisation: ib/i)->i(, iB/i}->i{, i]->i[, i>->i<
_TEXTOBJ_NORMALIZE = {'b': '(', ')': '(', 'B': '{', '}': '{', ']': '[', '>': '<'}


def parse_visual_textobj(buf: str):
    """Parse a visual-mode text object: ``[count](i|a)(obj)`` — e.g. 'iw', 'a(', '2iw'.

    In visual mode `i`/`a` are text-object prefixes (never insert/append), so this is
    parsed directly rather than via the operator grammar.  Returns:
      ('object', textobj, count) — complete, textobj canonicalised ('iw', 'a(', …);
      'pending'                  — a valid `i`/`a` prefix awaiting its object char;
      None                       — not a text object (let the motion parser handle it,
                                    incl. a bare count like '2' that may become '2j').
    """
    i = 0
    while i < len(buf) and buf[i] in COUNTS:
        i += 1
    if i >= len(buf):
        return None                                # digits only / empty → motion parser
    if buf[i] not in ('i', 'a'):
        return None
    count = int(buf[:i]) if i else 1
    if i + 1 >= len(buf):
        return 'pending'                           # have i/a, await the object char
    obj = _TEXTOBJ_NORMALIZE.get(buf[i+1], buf[i+1])
    return ('object', buf[i] + obj, count)


def _operator_target(op: str, double_ch: str, buf: str, j0: int, count_n: int):
    """Parse the target (motion / text object / find / linewise) following an
    operator. Shared by d/y/c and the g-case operators (g~/gu/gU).

    `op` is the operator token ('d', 'gU', …); `double_ch` is the char whose
    doubling means linewise (e.g. 'd'→dd, 'U'→gUU); `j0` is the buffer index of
    the first char after the operator token. Returns (action|None, remaining).
    """
    if j0 >= len(buf):
        return None, buf
    if buf[j0] == double_ch:                       # doubled → linewise (dd / gUU)
        return {'type': 'operator', 'op': op, 'motion': 'line', 'count': count_n}, buf[j0+1:]

    motion_count = ''
    j = j0
    while j < len(buf) and buf[j] in COUNTS:
        motion_count += buf[j]
        j += 1
    if j >= len(buf):
        return None, buf
    mc = int(motion_count) if motion_count else 1
    m = buf[j]

    if m in ('i', 'a'):                            # text object
        if j + 1 >= len(buf):
            return None, buf
        obj = _TEXTOBJ_NORMALIZE.get(buf[j+1], buf[j+1])
        return {'type': 'operator', 'op': op, 'textobj': m + obj,
                'count': count_n, 'motion_count': mc}, buf[j+2:]
    if m == 'g':                                   # g-prefixed motion: gg / ge / gE
        if j + 1 >= len(buf):
            return None, buf
        g2 = buf[j+1]
        if g2 == 'g':
            return {'type': 'operator', 'op': op, 'motion': 'gg', 'count': count_n, 'motion_count': mc, 'motion_count_given': bool(motion_count)}, buf[j+2:]
        if g2 in 'eE':
            return {'type': 'operator', 'op': op, 'motion': 'g' + g2, 'count': count_n, 'motion_count': mc}, buf[j+2:]
        return {'type': 'unknown'}, buf[j+2:]
    if m in 'fFtT':                                # find/till with target char
        if j + 1 >= len(buf):
            return None, buf
        return {'type': 'operator', 'op': op, 'motion': m, 'target': buf[j+1],
                'count': count_n, 'motion_count': mc}, buf[j+2:]
    if m in MOTIONS:
        return {'type': 'operator', 'op': op, 'motion': m, 'count': count_n,
                'motion_count': mc, 'motion_count_given': bool(motion_count)}, buf[j+1:]
    return {'type': 'unknown'}, buf[j+1:]


def parse(buf: str, mode: Mode) -> tuple[dict | None, str]:
    """
    Returns (action, remaining_buf).
    action is None if input is incomplete (need more keys).
    action is {'type': 'unknown'} for unrecognised sequences.
    """
    if not buf:
        return None, buf

    if mode != Mode.NORMAL:
        return None, buf

    i = 0
    count = ''

    # Count prefix — '0' is only a count digit after a non-zero digit has started
    while i < len(buf) and (buf[i] in COUNTS or (count and buf[i] == '0')):
        count += buf[i]
        i += 1

    if i >= len(buf):
        return None, buf  # incomplete

    count_n = int(count) if count else 1
    ch = buf[i]

    # "{reg} prefix — select a register for the following operator / paste
    if ch == '"':
        if i + 1 >= len(buf):
            return None, buf                           # waiting for the register name
        reg = buf[i+1]
        sub, rest = parse(buf[i+2:], mode)
        if sub is None:
            return None, buf                           # waiting for the command
        if sub.get('type') in ('operator', 'paste', 'substitute'):
            sub['register'] = reg
        return sub, rest

    # g-prefix: gg / ge / gE motions, and g~ / gu / gU case operators
    if ch == 'g':
        if i + 1 >= len(buf):
            return None, buf
        g2 = buf[i+1]
        if g2 == 'g':
            return {'type': 'motion', 'motion': 'gg', 'count': count_n, 'count_given': bool(count)}, buf[i+2:]
        if g2 in 'eE':
            return {'type': 'motion', 'motion': 'g' + g2, 'count': count_n}, buf[i+2:]
        if g2 == 'v':                              # gv — reselect last visual span
            return {'type': 'enter_mode', 'mode': 'visual', 'reselect': True}, buf[i+2:]
        if g2 in ('~', 'u', 'U'):                  # case operator: g~{m} gu{m} gU{m}
            return _operator_target('g' + g2, g2, buf, i + 2, count_n)
        if g2 == 'J':                              # gJ — join with no space at the seam
            return {'type': 'join', 'gap': False, 'count': count_n}, buf[i+2:]
        return {'type': 'unknown'}, buf[i+2:]

    # f/F/t/T — need one more char
    if ch in 'fFtT':
        if i + 1 >= len(buf):
            return None, buf
        target = buf[i+1]
        return {'type': 'motion', 'motion': ch, 'target': target, 'count': count_n}, buf[i+2:]

    # m/'/` — mark commands
    if ch in "m'`":
        if i + 1 >= len(buf):
            return None, buf
        reg = buf[i+1]
        return {'type': 'mark', 'cmd': ch, 'reg': reg}, buf[i+2:]

    # Operators: d / y / c
    if ch in OPERATORS:
        return _operator_target(ch, ch, buf, i + 1, count_n)

    # Capital D/C
    if ch in 'DC':
        op = ch.lower()
        return {'type': 'operator', 'op': op, 'motion': '$', 'count': count_n}, buf[i+1:]

    # J — join the next line onto this one (gJ, no space, handled in the g-branch)
    if ch == 'J':
        return {'type': 'join', 'gap': True, 'count': count_n}, buf[i+1:]

    # p / P — paste (standalone commands, not operator+motion)
    if ch == 'p':
        return {'type': 'paste', 'before': False, 'count': count_n}, buf[i+1:]
    if ch == 'P':
        return {'type': 'paste', 'before': True, 'count': count_n}, buf[i+1:]

    # s / S — substitute char / line (game-loop decides behaviour by mode)
    if ch == 's':
        return {'type': 'substitute', 'count': count_n}, buf[i+1:]
    if ch == 'S':
        return {'type': 'substitute', 'line': True, 'count': count_n}, buf[i+1:]

    # r{char} — replace char(s); R — REPLACE (overtype) mode
    if ch == 'r':
        if i + 1 >= len(buf):
            return None, buf                           # waiting for the replacement char
        return {'type': 'replace', 'char': buf[i+1], 'count': count_n}, buf[i+2:]
    if ch == 'R':
        return {'type': 'enter_mode', 'mode': 'replace'}, buf[i+1:]

    # Plain motion
    if ch in MOTIONS:
        return {'type': 'motion', 'motion': ch, 'count': count_n, 'count_given': bool(count)}, buf[i+1:]

    # x — interact (open door / loot chest)
    if ch == 'x':
        return {'type': 'interact', 'count': count_n}, buf[i+1:]

    # u / Ctrl-R
    if ch == 'u':
        return {'type': 'undo', 'count': count_n}, buf[i+1:]
    if ch == '\x12':  # Ctrl-R
        return {'type': 'redo', 'count': count_n}, buf[i+1:]

    # Ctrl-o / Ctrl-i (Tab) — jump list back / forward
    if ch == '\x0f':  # Ctrl-O
        return {'type': 'jump', 'dir': 'back', 'count': count_n}, buf[i+1:]
    if ch == '\t' or ch == '\x09':  # Ctrl-I / Tab
        return {'type': 'jump', 'dir': 'forward', 'count': count_n}, buf[i+1:]

    # : — enter command mode
    if ch == ':':
        return {'type': 'enter_mode', 'mode': 'command'}, buf[i+1:]

    # i/a/o/I/A/O — enter insert mode
    if ch in 'iaoIAO':
        return {'type': 'enter_mode', 'mode': 'insert', 'variant': ch}, buf[i+1:]

    # v/V/Ctrl-V
    if ch == 'v':
        return {'type': 'enter_mode', 'mode': 'visual'}, buf[i+1:]
    if ch == 'V':
        return {'type': 'enter_mode', 'mode': 'visual_line'}, buf[i+1:]
    if ch == '\x16':  # Ctrl-V
        return {'type': 'enter_mode', 'mode': 'visual_block'}, buf[i+1:]

    # . — repeat last change
    if ch == '.':
        return {'type': 'repeat', 'count': count_n}, buf[i+1:]

    # ~ — toggle case of char(s) under cursor, advancing
    if ch == '~':
        return {'type': 'case_char', 'count': count_n}, buf[i+1:]

    # Macros: q{reg} start recording (stop handled by the game loop); @{reg}/@@ play
    if ch == 'q':
        if i + 1 >= len(buf):
            return None, buf                           # waiting for the register
        return {'type': 'macro_record', 'reg': buf[i+1]}, buf[i+2:]
    if ch == '@':
        if i + 1 >= len(buf):
            return None, buf
        return {'type': 'macro_play', 'reg': buf[i+1], 'count': count_n}, buf[i+2:]

    # Search: / ? enter SEARCH mode; n/N repeat; * # search word under cursor
    if ch == '/':
        return {'type': 'enter_mode', 'mode': 'search', 'forward': True}, buf[i+1:]
    if ch == '?':
        return {'type': 'enter_mode', 'mode': 'search', 'forward': False}, buf[i+1:]
    if ch == 'n':
        return {'type': 'search_repeat', 'reverse': False, 'count': count_n}, buf[i+1:]
    if ch == 'N':
        return {'type': 'search_repeat', 'reverse': True, 'count': count_n}, buf[i+1:]
    if ch == '*':
        return {'type': 'search_word', 'forward': True, 'count': count_n}, buf[i+1:]
    if ch == '#':
        return {'type': 'search_word', 'forward': False, 'count': count_n}, buf[i+1:]

    return {'type': 'unknown'}, buf[i+1:]
