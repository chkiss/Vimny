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

"""Shared netrw chrome — the border, status bar, listing rows, header banner,
and bottom statusline drawn identically by the three netrw buffers (the
overworld, the ~/.vimny/ parent dir, and the scroll library).

Each helper returns a fully-rendered (already-coloured) line string; callers
join them into the frame. Centralising them keeps the netrw buffers visually
identical and removes what used to be three verbatim copies. `bfg`/`rst` are the
caller's border-fg / normal-fg escape strings (passed in so a helper never
re-queries colour state mid-frame)."""
from __future__ import annotations
import render.colors as C
import render.symbols as S


def border_h(iw, bfg, rst, left, right, fill=S.BOX_H):
    """A horizontal border row: corner/tee `left`, `iw` fill chars, `right`."""
    return bfg + left + fill * iw + right + rst


def empty_row(iw, bfg, rst):
    """A blank content row bounded by the left/right border."""
    return bfg + S.BOX_V + rst + ' ' * iw + bfg + S.BOX_V + rst


def status_bar(iw, bfg, rst, player, label, companion=''):
    """Top status bar: 'Vimny  ⌨ <name>   ♥♥♥ ♞   -- LABEL --', `label` centred.
    The horse icon appears when the player has named the wizard's horse."""
    full_h       = player.hp // 2
    empty_h      = player.max_hp // 2 - full_h
    hearts_plain = S.HEART_FULL * full_h + S.HEART_EMPTY * empty_h
    hearts_col   = ((C.heart_full()  + S.HEART_FULL  + rst) * full_h +
                    (C.heart_empty() + S.HEART_EMPTY + rst) * empty_h)
    # Companion horse: his glyph rides beside your hearts (matches dungeon status bar)
    horse_plain  = f' {S.HORSE}' if companion else ''
    horse_col    = (C.horse_fg() + S.HORSE + rst) if companion else ''
    name_tag     = '⌨  <' + player.name + '>'
    left_cols    = len('Vimny  ') + len(name_tag) + 1 + len('  ') + len(hearts_plain) + len(horse_plain) + len('  ')
    lbl_start    = (iw - len(label)) // 2
    mid_gap      = max(1, lbl_start - left_cols)
    right_pad    = max(0, iw - left_cols - mid_gap - len(label))
    return (bfg + S.BOX_V + rst +
            C.normal_fg() + 'Vimny  ' + name_tag + rst +
            '  ' + hearts_col + ((' ' + horse_col) if horse_col else '') + '  ' +
            ' ' * mid_gap +
            C.mode_normal() + label + rst +
            ' ' * right_pad +
            bfg + S.BOX_V + rst)


def listing_row(iw, bfg, rst, sb, is_cursor, vis, colored):
    """A selectable listing row (parent-dir & scroll-library share this exactly).
    `vis` is the colour-stripped visible width of `colored`; `sb` the selection bg."""
    if is_cursor:
        return (bfg + S.BOX_V + rst +
                sb + colored + rst + sb +
                ' ' * max(0, iw - vis) + rst +
                bfg + S.BOX_V + rst)
    return (bfg + S.BOX_V + rst +
            colored +
            ' ' * max(0, iw - vis) +
            bfg + S.BOX_V + rst)


def header_fns(iw, bfg, rst, dfc):
    """Return (_hdr, _div): the netrw '"'-comment banner row builders. `_hdr`
    draws one comment line (optionally pre-coloured); `_div` draws the `=` rule."""
    def _hdr(plain, colored=None):
        pad = max(0, iw - len(plain))
        return (bfg + S.BOX_V + rst +
                (dfc + plain if colored is None else colored) + rst +
                ' ' * pad + bfg + S.BOX_V + rst)

    def _div():
        return _hdr('" ' + '=' * (iw - 2))

    return _hdr, _div


def bottom_statusline(iw, bfg, rst, label, cursor_row, total, cmd_line,
                      cmd_prefix=':'):
    """Bottom bar: the command line when `cmd_line` is set — prompted with
    `cmd_prefix` (':' for commands, '/' or '?' for a search, Vim-true) —
    else '-- LABEL --' on the left and 'cursor/total' on the right."""
    if cmd_line is not None:
        cmd_text = cmd_prefix + cmd_line
        return (bfg + S.BOX_V + rst +
                C.mode_command() + cmd_text +
                rst + ' ' * max(0, iw - len(cmd_text)) +
                bfg + S.BOX_V + rst)
    sl_right = f'{cursor_row + 1}/{total} '
    sl_mid   = max(0, iw - len(label) - 2 - len(sl_right))
    return (bfg + S.BOX_V + rst +
            C.mode_normal() + ' ' + label + ' ' +
            rst + ' ' * sl_mid + sl_right +
            bfg + S.BOX_V + rst)
