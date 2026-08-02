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

"""Block L — named registers ("a-"z, "0, "_, append "A-"Z).

Routes yank/delete clips into the register store and reads them back, following
vim's rules: a yank with no register fills the unnamed `"` and the yank register
`"0`; a delete fills `"` but not `"0`; an explicit `"a` fills `a` and `"`; an
uppercase `"A` appends to `a`; `"_` is the black hole (writes vanish).

MACROS LIVE IN THE SAME REGISTERS.  There is no separate macro store: `qa`
records into register `a` (clobbering whatever text was there), `@a` replays
whatever register `a` holds — including text you merely YANKED, which is exactly
how vim behaves and is the whole reason `q`/`@` are spelled with register names.
Recording uses `record_register` rather than `write_register` because vim does
NOT touch the unnamed register or `"0` when it records.

Control characters are held in **caret notation** (`^[` for Esc, as vim displays
them), two glyphs wide.  Vim stores the raw byte and merely draws it this way;
we store the drawn form, so a macro register can be pasted into a buffer and
read on screen without a raw escape byte ever reaching the terminal.  Both
directions round-trip: paste a macro and you can yank it back and replay it.
"""
from __future__ import annotations

# the control chars engine/macro.py normalises recordings to
_CARET = {'\x1b': '^[', '\r': '^M', '\x7f': '^?'}
_UNCARET = {v: k for k, v in _CARET.items()}
#: The line break BETWEEN two rows of a register, played back as keys — the same
#: char `engine.macro` records <Enter> as.
_ENTER = '\r'


def _append_clip(old, new):
    """Concatenate two register clips (for uppercase "A append)."""
    if old is None:
        return new
    if new is None:
        return old
    if old['linewise'] or new['linewise']:
        return {'linewise': True, 'rows': old['rows'] + new['rows']}
    a, b = old['rows'][0], new['rows'][0]
    w = a['width']
    runes = list(a['char_runs']) + [dict(r, dcol=r['dcol'] + w) for r in b['char_runs']]
    return {'linewise': False, 'rows': [{'width': w + b['width'], 'char_runs': runes}]}


def write_register(player, reg: str, clip, is_delete: bool = False) -> None:
    """Store `clip` into register `reg` per vim rules. `reg` of '"'/None = unnamed."""
    if clip is None or reg == '_':            # black hole / nothing to store
        return
    regs = player.registers
    if reg and reg.isalpha() and reg.isupper():     # "A — append to "a
        low = reg.lower()
        regs[low] = _append_clip(regs.get(low), clip)
        regs['"'] = regs[low]
        return
    target = reg if (reg and reg != '"') else '"'
    regs[target] = clip
    regs['"'] = clip                                # unnamed always mirrors
    if target == '"' and not is_delete:
        regs['0'] = clip                            # last yank


def keys_to_clip(keys: str) -> dict:
    """A charwise one-row clip holding a recorded keystroke string, control
    chars in caret notation. This is what `q` stores — a register is a register."""
    syms = []
    for ch in keys:
        syms.extend(_CARET.get(ch, ch))
    return {'linewise': False,
            'rows': [{'width': len(syms),
                      'char_runs': [{'dcol': 0, 'symbols': tuple(syms),
                                     'kind': 'ancient'}] if syms else []}]}


def _row_to_text(row) -> str:
    """One clip row, laid back out as the characters that stood in it."""
    cells = [' '] * row.get('width', 0)
    for rd in row.get('char_runs', ()):
        for i, sym in enumerate(rd['symbols']):
            pos = rd['dcol'] + i
            if pos >= len(cells):
                cells.extend([' '] * (pos - len(cells) + 1))
            if pos >= 0:
                cells[pos] = sym
    return ''.join(cells)


def clip_to_text(clip) -> str:
    """Read a register back as the WORDS in it, for something that wants to
    know what you are carrying rather than replay it.

    This is the fancy door's reader. `clip_to_keys` is the wrong tool there: it
    is faithful to keystrokes, so it preserves the column padding a linewise cut
    drags along and encodes control characters as carets — a `dd` of a line
    holding one phrase comes back as that phrase wearing forty spaces. A door
    comparing that against its password would refuse every correct answer.

    So: rows joined with a single space, every run of whitespace collapsed to
    one, ends trimmed. What survives is what a reader would say the register
    holds, which is the only thing a password check can honestly compare.

    That collapsing is deliberately generous about WHITESPACE and about nothing
    else. `dw` (which takes the trailing space) and `de` (which does not) hand
    the door the same word, because the difference between them is not a
    difference in what you cut — but a cut that swept in one extra word reads
    as two words here, and no amount of trimming hides it. Whitespace is the
    layout; the words are the answer.
    """
    if not clip or not clip.get('rows'):
        return ''
    return ' '.join(' '.join(_row_to_text(r).split()) for r in clip['rows']).strip()


def clip_to_keys(clip) -> str:
    """Read a register back as a keystroke string for `@`. Any register works —
    text you yanked replays as keys, exactly as in vim.

    EVERY row, not just the first. A register can hold more than one line — `yy`
    a row of keystrokes off the floor, `2yy` two of them, `qA` append across
    lines — and vim runs all of it. Reading `rows[0]` alone silently executed
    the first line and dropped the rest, which is worse than refusing: the macro
    half-ran.

    Rows are joined with ENTER, because that is what the line break between them
    IS when the register is played as keys. A LINEWISE clip gets a trailing one
    as well: a linewise register ends with a newline in vim, so `yy@"` on a line
    holding `:s/old/new/` runs the command AND submits it, which is the whole
    point of being able to execute text you yanked.
    """
    if not clip or not clip.get('rows'):
        return ''
    text = _ENTER.join(_row_to_text(r) for r in clip['rows'])
    if clip.get('linewise'):
        text += _ENTER
    for caret, ch in _UNCARET.items():
        text = text.replace(caret, ch)
    return text


def record_register(player, reg: str, keys: str) -> None:
    """Store a recording into register `reg` — `qA` APPENDS to `a`, `qa`
    overwrites. Unlike a yank this leaves the unnamed register and "0 alone
    (vim does not disturb them while recording)."""
    if not reg or reg == '_':
        return
    clip = keys_to_clip(keys)
    if reg.isalpha() and reg.isupper():
        low = reg.lower()
        player.registers[low] = _append_clip(player.registers.get(low), clip)
    else:
        player.registers[reg] = clip


def read_register(player, reg: str):
    """Return the clip in register `reg` ('"'/None = unnamed), or None."""
    if reg == '_':
        return None
    r = reg.lower() if (reg and reg.isalpha()) else reg
    r = r if (r and r != '"') else '"'
    return player.registers.get(r)
