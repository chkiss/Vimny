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

"""
Parse Vim-grammar keystrokes: [count][operator][motion] or [count][motion].
Returns action dicts consumed by the game loop.
"""
from __future__ import annotations
from engine.modes import Mode

MOTIONS  = set('hjklwbeWBEGg0^${}()HML%|' + ';,' + '+-_')
OPERATORS = set('dyc><=')
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
    while i < len(buf) and (buf[i] in COUNTS or (i and buf[i] == '0')):
        i += 1
    if i >= len(buf):
        return None                                # digits only / empty → motion parser
    if buf[i] not in ('i', 'a'):
        return None
    count = int(buf[:i]) if i else 1
    if i + 1 >= len(buf):
        return 'pending'                           # have i/a, await the object char
    obj = _TEXTOBJ_NORMALIZE.get(buf[i+1], buf[i+1])
    return ('object', buf[i] + obj, count, i > 0)   # 4th: count was explicitly typed


def _cg(action: dict, count) -> dict:
    """Stamp ``count_given`` on a command action ONLY when an explicit count was typed
    (``count`` is the raw count string — truthy iff digits preceded the command).  Bare
    commands keep their original dict shape; cost code reads ``.get('count_given', False)``.
    This is what makes a redundant `1` real keystrokes: `1p`/`1J`/`1dd` pay for the digit."""
    if count:
        action['count_given'] = True
    return action


def _operator_target(op: str, double_ch: str, buf: str, j0: int, count_n: int,
                     count_given: bool = False):
    """Parse the target (motion / text object / find / linewise) following an
    operator. Shared by d/y/c and the g-case operators (g~/gu/gU).

    `op` is the operator token ('d', 'gU', …); `double_ch` is the char whose
    doubling means linewise (e.g. 'd'→dd, 'U'→gUU); `j0` is the buffer index of
    the first char after the operator token; `count_given` is True when an explicit
    operator count was typed (so `1dw` pays for its '1'). Returns (action|None, rest).
    """
    if j0 >= len(buf):
        return None, buf
    # `cg` stamps the OPERATOR-level count_given (the '3' in 3dw / the '1' in 1dd) only
    # when it was typed, so bare operators keep their dict shape.
    cg = (lambda d: {**d, 'count_given': True}) if count_given else (lambda d: d)
    if buf[j0] == double_ch:                       # doubled → linewise (dd / gUU)
        return cg({'type': 'operator', 'op': op, 'motion': 'line', 'count': count_n}), buf[j0+1:]

    motion_count = ''
    j = j0
    # '0' is a count digit only after a non-zero digit (else it's the 0 motion: d0)
    while j < len(buf) and (buf[j] in COUNTS or (motion_count and buf[j] == '0')):
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
        return cg({'type': 'operator', 'op': op, 'textobj': m + obj,
                   'count': count_n, 'motion_count': mc}), buf[j+2:]
    if m == 'g':                                   # g-prefixed motion: gg / ge / gE
        if j + 1 >= len(buf):
            return None, buf
        g2 = buf[j+1]
        if g2 == 'g':
            return cg({'type': 'operator', 'op': op, 'motion': 'gg', 'count': count_n,
                       'motion_count': mc, 'motion_count_given': bool(motion_count)}), buf[j+2:]
        if g2 in 'eE':
            return cg({'type': 'operator', 'op': op, 'motion': 'g' + g2,
                       'count': count_n, 'motion_count': mc}), buf[j+2:]
        return {'type': 'unknown'}, buf[j+2:]
    if m in 'fFtT':                                # find/till with target char
        if j + 1 >= len(buf):
            return None, buf
        return cg({'type': 'operator', 'op': op, 'motion': m, 'target': buf[j+1],
                   'count': count_n, 'motion_count': mc}), buf[j+2:]
    if m in MOTIONS:
        return cg({'type': 'operator', 'op': op, 'motion': m, 'count': count_n,
                   'motion_count': mc, 'motion_count_given': bool(motion_count)}), buf[j+1:]
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
            if count:                                  # counts on both sides multiply: 2"a3dd = 6 lines
                sub['count'] = sub.get('count', 1) * count_n
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
        if g2 in 'jk':                             # gj / gk — move by DISPLAY line (wrap)
            return {'type': 'motion', 'motion': 'g' + g2, 'count': count_n}, buf[i+2:]
        if g2 == 'v':                              # gv — reselect last visual span
            return {'type': 'enter_mode', 'mode': 'visual', 'reselect': True}, buf[i+2:]
        if g2 in ('~', 'u', 'U'):                  # case operator: g~{m} gu{m} gU{m}
            return _operator_target('g' + g2, g2, buf, i + 2, count_n, bool(count))
        if g2 == 'J':                              # gJ — join with no space at the seam
            return _cg({'type': 'join', 'gap': False, 'count': count_n}, count), buf[i+2:]
        if g2 == '&':                              # g& — repeat last :s over the whole file, with flags
            return {'type': 'sub_repeat', 'whole_file': True, 'keep_flags': True}, buf[i+2:]
        if g2 == '_':                              # g_ — last non-blank of the line
            return {'type': 'motion', 'motion': 'g_', 'count': count_n}, buf[i+2:]
        if g2 in '*#':                             # g* / g# — search word, NO boundaries
            return _cg({'type': 'search_word', 'forward': g2 == '*',
                        'literal': True, 'count': count_n}, count), buf[i+2:]
        if g2 == 'i':                              # gi — INSERT at the last insert spot
            return {'type': 'goto_insert'}, buf[i+2:]
        if g2 in 'pP':                             # gp / gP — paste, cursor AFTER it
            return _cg({'type': 'paste', 'before': g2 == 'P', 'after_cursor': True,
                        'count': count_n}, count), buf[i+2:]
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
        return _operator_target(ch, ch, buf, i + 1, count_n, bool(count))

    # Capital D/C — the to-line-end shorthands. Tagged so the command guard can
    # gate them behind their own curriculum tokens ('D'/'C'): the shorthand is a
    # SEPARATE lesson from d$/c$ (The Operator's Vault forces the two-key
    # grammar; the one-key shorthands unlock later).
    if ch in 'DC':
        op = ch.lower()
        return _cg({'type': 'operator', 'op': op, 'motion': '$', 'count': count_n,
                    'shorthand': ch}, count), buf[i+1:]

    # Y — Vim's default Y = yy. Tagged like D/C: the one-key shorthand is a
    # SEPARATE lesson from yy (it undercuts yy by a key — ungated it would
    # golf the Beacon Tiers' par), so it stays locked until taught.
    if ch == 'Y':
        return _cg({'type': 'operator', 'op': 'y', 'motion': 'line', 'count': count_n,
                    'shorthand': 'Y'}, count), buf[i+1:]

    # ZZ / ZQ — the sealed departure (:wq / :q!); granted by a relic scroll
    if ch == 'Z':
        if i + 1 >= len(buf):
            return None, buf
        if buf[i+1] in 'ZQ':
            return {'type': 'seal_exit', 'discard': buf[i+1] == 'Q'}, buf[i+2:]
        return {'type': 'unknown'}, buf[i+2:]

    # J — join the next line onto this one (gJ, no space, handled in the g-branch)
    if ch == 'J':
        return _cg({'type': 'join', 'gap': True, 'count': count_n}, count), buf[i+1:]

    # & — repeat the last :s on the current line (no flags); g& did the whole file
    if ch == '&':
        return {'type': 'sub_repeat', 'whole_file': False, 'keep_flags': False}, buf[i+1:]

    # p / P — paste (standalone commands, not operator+motion)
    if ch == 'p':
        return _cg({'type': 'paste', 'before': False, 'count': count_n}, count), buf[i+1:]
    if ch == 'P':
        return _cg({'type': 'paste', 'before': True, 'count': count_n}, count), buf[i+1:]

    # s / S — substitute char / line (game-loop decides behaviour by mode)
    if ch == 's':
        return _cg({'type': 'substitute', 'count': count_n}, count), buf[i+1:]
    if ch == 'S':
        return _cg({'type': 'substitute', 'line': True, 'count': count_n}, count), buf[i+1:]

    # r{char} — replace char(s); R — REPLACE (overtype) mode
    if ch == 'r':
        if i + 1 >= len(buf):
            return None, buf                           # waiting for the replacement char
        return _cg({'type': 'replace', 'char': buf[i+1], 'count': count_n}, count), buf[i+2:]
    if ch == 'R':
        return {'type': 'enter_mode', 'mode': 'replace'}, buf[i+1:]

    # Plain motion
    if ch in MOTIONS:
        return {'type': 'motion', 'motion': ch, 'count': count_n, 'count_given': bool(count)}, buf[i+1:]

    # x — interact (open door / loot chest)
    if ch == 'x':
        return _cg({'type': 'interact', 'count': count_n}, count), buf[i+1:]
    # X — delete BEFORE the cursor. Tagged with its own gate token (the Y/D/C
    # rule): it undercuts 'h x' by a key, so it stays locked until taught.
    if ch == 'X':
        return _cg({'type': 'interact', 'count': count_n, 'before': True,
                    'shorthand': 'X'}, count), buf[i+1:]

    # u / Ctrl-R
    if ch == 'u':
        return {'type': 'undo', 'count': count_n}, buf[i+1:]
    if ch == '\x12':  # Ctrl-R
        return {'type': 'redo', 'count': count_n}, buf[i+1:]

    # Ctrl-o / Ctrl-i (Tab) — jump list back / forward
    if ch == '\x0f':  # Ctrl-O
        return {'type': 'jump', 'dir': 'back', 'count': count_n}, buf[i+1:]
    if ch == '\t':  # Ctrl-I / Tab
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
        return _cg({'type': 'repeat', 'count': count_n}, count), buf[i+1:]

    # ~ — toggle case of char(s) under cursor, advancing
    if ch == '~':
        return _cg({'type': 'case_char', 'count': count_n}, count), buf[i+1:]

    # Macros: q{reg} start recording (stop handled by the game loop); @{reg}/@@ play
    if ch == 'q':
        if i + 1 >= len(buf):
            return None, buf                           # waiting for the register
        return {'type': 'macro_record', 'reg': buf[i+1]}, buf[i+2:]
    if ch == '@':
        if i + 1 >= len(buf):
            return None, buf
        return _cg({'type': 'macro_play', 'reg': buf[i+1], 'count': count_n}, count), buf[i+2:]

    # Search: / ? enter SEARCH mode; n/N repeat; * # search word under cursor
    if ch == '/':
        return {'type': 'enter_mode', 'mode': 'search', 'forward': True}, buf[i+1:]
    if ch == '?':
        return {'type': 'enter_mode', 'mode': 'search', 'forward': False}, buf[i+1:]
    if ch == 'n':
        return _cg({'type': 'search_repeat', 'reverse': False, 'count': count_n}, count), buf[i+1:]
    if ch == 'N':
        return _cg({'type': 'search_repeat', 'reverse': True, 'count': count_n}, count), buf[i+1:]
    if ch == '*':
        return _cg({'type': 'search_word', 'forward': True, 'count': count_n}, count), buf[i+1:]
    if ch == '#':
        return _cg({'type': 'search_word', 'forward': False, 'count': count_n}, count), buf[i+1:]

    return {'type': 'unknown'}, buf[i+1:]
