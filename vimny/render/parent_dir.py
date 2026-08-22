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

"""Parent directory renderer — ~/.vimny/ hub between world/, scrolls/, saves/."""
from __future__ import annotations
from blessed import Terminal
from vimny.engine.player import Player
import vimny.render.colors as C
import vimny.render.symbols as S
import vimny.render.netrw_chrome as NC
from vimny.render.utils import inner_w as _iw, print_size_notice

_BASE_ENTRIES = ['saves/', 'scrolls/', 'world/']


def entries_for(player: Player) -> list[str]:
    if player.name == 'admin':
        return _BASE_ENTRIES + ['colors/']
    return _BASE_ENTRIES


def render_parent_dir(
    term: Terminal,
    player: Player,
    progress: dict,
    cursor_row: int,
    cmd_line: str | None = None,
) -> None:
    iw       = _iw(term)
    bfg      = C.border_fg()
    rst      = C.normal_fg()
    out      = []
    entries  = entries_for(player)
    sl_label = '-- OVERWORLD --'

    # ── Top border / status bar / separator ────────────────────────────────────
    out.append(NC.border_h(iw, bfg, rst, S.BOX_TL, S.BOX_TR))
    out.append(NC.status_bar(iw, bfg, rst, player, sl_label, progress.get('horse_name', '')))
    out.append(NC.border_h(iw, bfg, rst, S.BOX_LT, S.BOX_RT))

    game_h = term.height - 5

    sb   = C.sel_bg()
    dfc  = C.dir_fg()
    enfc = C.entry_fg()

    def _row(is_cursor, vis, colored):
        return NC.listing_row(iw, bfg, rst, sb, is_cursor, vis, colored)

    _hdr, _div = NC.header_fns(iw, bfg, rst, dfc)

    ver    = '(netrw v13ny)'
    ndl    = '" Netrw Directory Listing'
    ndl_sp = max(0, iw - len(ndl) - len(ver))
    sb_lbl = '"   Sorted by      '
    sb_val = 'name'
    kc     = C.mode_insert()
    qh_pfx = '"   Quick Help: '
    qh_prs = [('j/k', 'move'), ('Enter', 'open'), (':e', 'directory/'), ('Esc', 'back')]
    qh_pl  = qh_pfx + '  '.join(f'{k}:{d}' for k, d in qh_prs)
    qh_col = dfc + qh_pfx + ('  ' + dfc).join(kc + k + dfc + ':' + d for k, d in qh_prs)
    hdr_rows = [
        _div(),
        _hdr(ndl + ' ' * ndl_sp + ver),
        _hdr('"   ~/.vimny/'),
        _hdr(sb_lbl + sb_val, dfc + sb_lbl + rst + sb_val),
        _hdr(qh_pl, qh_col),
        _div(),
    ]
    out.extend(hdr_rows)

    # ── ../ and ./ directory entries ─────────────────────────────────────────
    for di, dentry in enumerate(['../', './']):
        is_cursor = di == cursor_row
        out.append(_row(is_cursor, len(dentry), dfc + dentry))

    # ── Directory entries ─────────────────────────────────────────────────────
    for idx, entry in enumerate(entries):
        is_cursor = (idx + 2) == cursor_row
        nc        = enfc if is_cursor else dfc
        out.append(_row(is_cursor, len(entry), nc + entry))

    # ── Empty rows ────────────────────────────────────────────────────────────
    rows_used = len(hdr_rows) + 2 + len(entries)
    for _ in range(max(0, game_h - rows_used)):
        out.append(NC.empty_row(iw, bfg, rst))

    # ── Statusline / command line / bottom border ──────────────────────────────
    out.append(NC.bottom_statusline(iw, bfg, rst, sl_label, cursor_row, len(entries) + 2, cmd_line))
    out.append(NC.border_h(iw, bfg, rst, S.BOX_BL, S.BOX_BR))

    if print_size_notice(term):
        return
    print(term.home + term.clear + '\n'.join(out), end='', flush=True)
