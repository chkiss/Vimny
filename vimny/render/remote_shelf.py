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

"""Remote-shelf renderer — the online community catalogue as a netrw listing.

Mirrors `render_parent_dir`'s chrome (the shared netrw box) but lists manifest
rows instead of directories: `name by author  |  +teaches  |  [badge]`. The
badge is the one thing the row can say about a level it has not downloaded —
whether it is already on the local shelf ([ON SHELF]) or not ([GET]) — because
par only exists after the validator has replayed the tape, which needs the file.
"""
from __future__ import annotations
from blessed import Terminal
from vimny.engine.player import Player
import vimny.render.colors as C
import vimny.render.symbols as S
import vimny.render.netrw_chrome as NC
from vimny.render.utils import inner_w as _iw, print_size_notice


def render_remote_shelf(
    term: Terminal,
    player: Player,
    progress: dict,
    entries: list,
    installed_slugs: set,
    cursor_row: int,
    status: str = '',
    cmd_line: str | None = None,
) -> None:
    iw       = _iw(term)
    bfg      = C.border_fg()
    rst      = C.normal_fg()
    out      = []
    sl_label = '-- REMOTE SHELF --'

    out.append(NC.border_h(iw, bfg, rst, S.BOX_TL, S.BOX_TR))
    out.append(NC.status_bar(iw, bfg, rst, player, sl_label, progress.get('horse_name', '')))
    out.append(NC.border_h(iw, bfg, rst, S.BOX_LT, S.BOX_RT))

    game_h = term.height - 5
    sb     = C.sel_bg()
    dfc    = C.dir_fg()
    enfc   = C.entry_fg()
    kc     = C.mode_insert()

    def _row(is_cursor, vis, colored):
        return NC.listing_row(iw, bfg, rst, sb, is_cursor, vis, colored)

    _hdr, _div = NC.header_fns(iw, bfg, rst, dfc)

    ver     = '(netrw v13ny)'
    ndl     = '" Netrw Directory Listing'
    ndl_sp  = max(0, iw - len(ndl) - len(ver))
    qh_pfx  = '"   Quick Help: '
    qh_prs  = [('j/k', 'move'), ('Enter', 'install'), ('r', 'refresh'), ('-/Esc', 'back')]
    qh_pl   = qh_pfx + '  '.join(f'{k}:{d}' for k, d in qh_prs)
    qh_col  = dfc + qh_pfx + ('  ' + dfc).join(kc + k + dfc + ':' + d for k, d in qh_prs)

    # The status line answers "what just happened" — fetching, an install
    # result, or a network error — in the netrw comment slot the parent dir
    # spends on a sort order it does not have.
    stat_plain = '"   ' + (status or 'community/remote/')
    hdr_rows = [
        _div(),
        _hdr(ndl + ' ' * ndl_sp + ver),
        _hdr('"   ~/.vimny/world/community/remote/'),
        _hdr(stat_plain, dfc + stat_plain),
        _hdr(qh_pl, qh_col),
        _div(),
    ]
    out.extend(hdr_rows)

    def _badge(entry):
        if entry.slug in installed_slugs:
            return '[ON SHELF]', C.budget_ok()
        return '[GET]', C.mode_insert()

    if entries:
        for idx, entry in enumerate(entries):
            is_cursor = idx == cursor_row
            who   = f' by {entry.author}' if entry.author else ''
            teach = ' '.join(f'+{t}' for t in entry.teaches)
            badge, bcol = _badge(entry)
            nc    = enfc if is_cursor else rst
            left  = entry.name + who
            # left name (+dim author) … teaching column … badge, right-aligned.
            mid_gap  = max(2, iw - len(left) - len(teach) - len(badge) - 2)
            colored  = (nc + entry.name + C.hint_fg() + who + ' ' +
                        dfc + teach + ' ' * mid_gap + bcol + badge)
            vis = len(left) + 1 + len(teach) + mid_gap + len(badge)
            out.append(_row(is_cursor, vis, colored))
    else:
        empty = '(nothing here — press r to refresh)'
        out.append(_row(False, len(empty), C.hint_fg() + empty))

    rows_used = len(hdr_rows) + max(1, len(entries))
    for _ in range(max(0, game_h - rows_used)):
        out.append(NC.empty_row(iw, bfg, rst))

    total = max(1, len(entries))
    out.append(NC.bottom_statusline(iw, bfg, rst, sl_label, cursor_row, total, cmd_line))
    out.append(NC.border_h(iw, bfg, rst, S.BOX_BL, S.BOX_BR))

    if print_size_notice(term):
        return
    print(term.home + term.clear + '\n'.join(out), end='', flush=True)
