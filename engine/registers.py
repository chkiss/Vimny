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
"""
from __future__ import annotations


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


def read_register(player, reg: str):
    """Return the clip in register `reg` ('"'/None = unnamed), or None."""
    if reg == '_':
        return None
    r = reg.lower() if (reg and reg.isalpha()) else reg
    r = r if (r and r != '"') else '"'
    return player.registers.get(r)
