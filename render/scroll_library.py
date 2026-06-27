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

"""Scroll library renderer — netrw-style listing of discovered scrolls.

The catalog is split into two subtrees, mirroring the overworld's ``custom/``
section: the act-gated codex scrolls on top, then the found relic scrolls.
``library_rows`` is the single source of truth for the on-screen row order;
both this renderer and run_scroll_library's navigation index into it."""
from __future__ import annotations
from blessed import Terminal
from engine.player import Player
import render.colors as C
import render.symbols as S
import render.netrw_chrome as NC
from content.scrolls import SCROLL_CATALOG, RELIC_SCROLL_IDS
from render.utils import inner_w as _iw, subtree_lines, tree_glyph

# Subtree labels (netrw directory style). Change these two strings to rename
# the categories everywhere.
CODEX_LABEL  = 'codex/'
RELICS_LABEL = 'relics/'


def library_rows() -> list[dict]:
    """Ordered, flat list of navigable rows in the scroll library. Each row is
    a dict with a 'type': 'parent' | 'self' | 'subhdr' | 'scroll'. A subhdr
    carries 'label'; a scroll carries 'scroll' (catalog entry) and 'last' (True
    for the final entry under its subtree, for the └ tree glyph)."""
    rows: list[dict] = [{'type': 'parent'}, {'type': 'self'}]
    codex  = [s for s in SCROLL_CATALOG if s['id'] not in RELIC_SCROLL_IDS]
    relics = [s for s in SCROLL_CATALOG if s['id'] in RELIC_SCROLL_IDS]
    rows += subtree_lines(CODEX_LABEL,  codex,  'scroll', 'scroll')
    rows += subtree_lines(RELICS_LABEL, relics, 'scroll', 'scroll')
    return rows


def render_scroll_library(
    term: Terminal,
    player: Player,
    progress: dict,
    cursor_row: int,
    cmd_line: str | None = None,
) -> None:
    discovered = set(progress.get('extras', []))
    seen       = set(progress.get('scrolls_seen', []))
    iw  = _iw(term)
    bfg = C.border_fg()
    rst = C.normal_fg()
    out = []
    sl_label = '-- SCROLLS --'

    # ── Top border / status bar / separator ────────────────────────────────────
    out.append(NC.border_h(iw, bfg, rst, S.BOX_TL, S.BOX_TR))
    out.append(NC.status_bar(iw, bfg, rst, player, sl_label))
    out.append(NC.border_h(iw, bfg, rst, S.BOX_LT, S.BOX_RT))

    game_h  = term.height - 5
    n_disc  = sum(1 for s in SCROLL_CATALOG if s['id'] in discovered)
    n_total = len(SCROLL_CATALOG)

    sb   = C.sel_bg()
    dfc  = C.dir_fg()
    enfc = C.entry_fg()

    def _row(is_cursor, vis, colored):
        return NC.listing_row(iw, bfg, rst, sb, is_cursor, vis, colored)

    _hdr, _div = NC.header_fns(iw, bfg, rst, dfc)

    ver    = '(netrw v13ny)'
    ndl    = '" Netrw Directory Listing'
    ndl_sp = max(0, iw - len(ndl) - len(ver))
    dc_lbl = '"   Discovered: '
    dc_val = f'{n_disc} of {n_total}'
    kc     = C.mode_insert()
    qh_pfx = '"   Quick Help: '
    qh_prs = [('j/k', 'move'), ('Enter', 'read'), ('-', 'go up dir'), (':q', 'back')]
    qh_pl  = qh_pfx + '  '.join(f'{k}:{d}' for k, d in qh_prs)
    qh_col = dfc + qh_pfx + ('  ' + dfc).join(kc + k + dfc + ':' + d for k, d in qh_prs)
    hdr_rows = [
        _div(),
        _hdr(ndl + ' ' * ndl_sp + ver),
        _hdr('"   ~/.vimny/scrolls/'),
        _hdr(dc_lbl + dc_val, dfc + dc_lbl + rst + dc_val),
        _hdr(qh_pl, qh_col),
        _div(),
    ]
    out.extend(hdr_rows)

    # ── Navigable rows: ../ ./ then the codex/ and relics/ subtrees ───────────
    rows = library_rows()
    for idx, r in enumerate(rows):
        is_cursor = idx == cursor_row
        t = r['type']
        if t == 'parent':
            out.append(_row(is_cursor, len('../'), dfc + '../'))
            continue
        if t == 'self':
            out.append(_row(is_cursor, len('./'), dfc + './'))
            continue
        if t == 'subhdr':
            out.append(_row(is_cursor, len(r['label']), dfc + r['label']))
            continue

        # scroll row, indented under its subtree with a ├/└ tree glyph
        scroll    = r['scroll']
        is_disc   = scroll['id'] in discovered
        is_new    = is_disc and scroll['id'] not in seen
        prefix    = '  ' + tree_glyph(r['last']) + ' '   # 4 visible columns

        if is_disc:
            glyph      = '◈  '
            title_text = scroll['title']
            meta       = '  ' + scroll['dropped_by']
            if is_new:
                badge     = '[NEW]'
                badge_col = C.mode_insert()
            else:
                badge     = ''
                badge_col = C.hint_fg()
        else:
            glyph      = '░  '
            title_text = '???'
            meta       = ''
            badge      = '[undiscovered]'
            badge_col  = C.hint_fg()

        nc  = enfc if is_cursor else (C.normal_fg() if is_disc else C.hint_fg())
        bc  = badge_col if badge else ''
        mc  = C.hint_fg() if meta else ''
        plain_len = len(prefix) + len(glyph) + len(title_text) + len(badge) + len(meta)
        spaces    = max(2, iw - plain_len)
        colored   = (C.hint_fg() + prefix + nc + glyph + title_text +
                     ' ' * spaces +
                     bc + badge +
                     mc + meta)
        out.append(_row(is_cursor, iw, colored))

    # ── Empty rows ────────────────────────────────────────────────────────────
    rows_used = len(hdr_rows) + len(rows)
    for _ in range(max(0, game_h - rows_used)):
        out.append(NC.empty_row(iw, bfg, rst))

    # ── Statusline / command line / bottom border ──────────────────────────────
    out.append(NC.bottom_statusline(iw, bfg, rst, sl_label, cursor_row, len(rows), cmd_line))
    out.append(NC.border_h(iw, bfg, rst, S.BOX_BL, S.BOX_BR))

    print(term.home + term.clear + '\n'.join(out), end='', flush=True)
