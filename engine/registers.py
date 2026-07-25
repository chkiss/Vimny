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


def clip_to_keys(clip) -> str:
    """Read a register back as a keystroke string for `@`. Any register works —
    text you yanked replays as keys, exactly as in vim."""
    if not clip or not clip.get('rows'):
        return ''
    row = clip['rows'][0]
    cells = [' '] * row.get('width', 0)
    for rd in row.get('char_runs', ()):
        for i, sym in enumerate(rd['symbols']):
            pos = rd['dcol'] + i
            if pos >= len(cells):
                cells.extend([' '] * (pos - len(cells) + 1))
            if pos >= 0:
                cells[pos] = sym
    text = ''.join(cells)
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
