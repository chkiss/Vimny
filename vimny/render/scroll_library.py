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
from vimny.engine.player import Player
import vimny.render.colors as C
import vimny.render.symbols as S
import vimny.render.netrw_chrome as NC
from vimny.content.scrolls import SCROLL_CATALOG, RELIC_SCROLL_IDS
from vimny.content.blessings import BLESSING_CATALOG
from vimny.render.utils import inner_w as _iw, subtree_lines, tree_glyph, print_size_notice

# Subtree labels (netrw directory style). Change these strings to rename
# the categories everywhere.
CODEX_LABEL     = 'codex/'
RELICS_LABEL    = 'relics/'
BLESSINGS_LABEL = 'blessings/'


def library_rows() -> list[dict]:
    """Ordered, flat list of navigable rows in the scroll library. Each row is
    a dict with a 'type': 'parent' | 'self' | 'subhdr' | 'scroll'. A subhdr
    carries 'label'; a scroll carries 'scroll' (catalog entry), 'last' (True
    for the final entry under its subtree, for the └ tree glyph) and 'group'
    ('codex' | 'relics' | 'blessings' — which discovered-set gates it)."""
    rows: list[dict] = [{'type': 'parent'}, {'type': 'self'}]
    codex  = [s for s in SCROLL_CATALOG if s['id'] not in RELIC_SCROLL_IDS]
    relics = [s for s in SCROLL_CATALOG if s['id'] in RELIC_SCROLL_IDS]

    def _tag(subtree_rows, group):
        for r in subtree_rows:
            if r['type'] == 'scroll':
                r['group'] = group
        return subtree_rows

    rows += _tag(subtree_lines(CODEX_LABEL,     codex,            'scroll', 'scroll'), 'codex')
    rows += _tag(subtree_lines(RELICS_LABEL,    relics,           'scroll', 'scroll'), 'relics')
    rows += _tag(subtree_lines(BLESSINGS_LABEL, BLESSING_CATALOG, 'scroll', 'scroll'), 'blessings')
    return rows


def row_label(r: dict, discovered=(), bless_seen=()) -> str:
    """The motion/search text of a library row (mirrors what's drawn): ``../``,
    ``./``, a subtree label, or a scroll title (``???`` while undiscovered)."""
    t = r['type']
    if t == 'parent':
        return '../'
    if t == 'self':
        return './'
    if t == 'subhdr':
        return r['label']
    disc = bless_seen if r.get('group') == 'blessings' else discovered
    return r['scroll']['title'] if r['scroll']['id'] in disc else '???'


def row_section_key(r: dict) -> str:
    """Grouping for `{`/`}` — the nav rows, then each subtree (its header and its
    scrolls share a key so a section spans the whole subtree)."""
    t = r['type']
    if t in ('parent', 'self'):
        return 'nav'
    if t == 'subhdr':
        return r['label'].rstrip('/')      # 'codex/' → 'codex' (matches scroll group)
    return r.get('group', 'scroll')


def _viewport_top(cursor: int, top: int, avail: int, n: int) -> int:
    """Vim-like viewport top: keep `top` unless the cursor has left the window."""
    max_off = max(0, n - avail)
    if cursor < top:
        top = cursor
    elif cursor >= top + avail:
        top = cursor - avail + 1
    return max(0, min(top, max_off))


def render_scroll_library(
    term: Terminal,
    player: Player,
    progress: dict,
    cursor_row: int,
    cmd_line: str | None = None,
    scroll_offset: int = 0,
    cmd_prefix: str = ':',
) -> int:
    """Render the library and return the (possibly adjusted) scroll_offset so the
    caller can keep the viewport in sync as the cursor moves."""
    discovered = set(progress.get('extras', []))
    seen       = set(progress.get('scrolls_seen', []))
    bless_seen = set(progress.get('blessings_seen', []))
    iw  = _iw(term)
    bfg = C.border_fg()
    rst = C.normal_fg()
    out = []
    sl_label = '-- SCROLLS --'

    # ── Top border / status bar / separator ────────────────────────────────────
    out.append(NC.border_h(iw, bfg, rst, S.BOX_TL, S.BOX_TR))
    out.append(NC.status_bar(iw, bfg, rst, player, sl_label, progress.get('horse_name', '')))
    out.append(NC.border_h(iw, bfg, rst, S.BOX_LT, S.BOX_RT))

    game_h  = term.height - 5
    n_disc  = (sum(1 for s in SCROLL_CATALOG if s['id'] in discovered)
               + sum(1 for b in BLESSING_CATALOG if b['id'] in bless_seen))
    n_total = len(SCROLL_CATALOG) + len(BLESSING_CATALOG)

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

    # ── Navigable rows: ../ ./ then the codex/ relics/ blessings/ subtrees ─────
    # The list can outgrow the window (many blessings), so scroll a viewport of
    # the navigable rows beneath the fixed header, netrw-style.
    rows  = library_rows()
    avail = max(1, game_h - len(hdr_rows))
    scroll_offset = _viewport_top(cursor_row, scroll_offset, avail, len(rows))
    vis_rows = list(enumerate(rows))[scroll_offset:scroll_offset + avail]
    for idx, r in vis_rows:
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

        # scroll row, indented under its subtree with a ├/└ tree glyph. A
        # blessing row is gated on blessings_seen instead of found-scroll extras.
        scroll    = r['scroll']
        disc_set  = bless_seen if r.get('group') == 'blessings' else discovered
        is_disc   = scroll['id'] in disc_set
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
    rows_used = len(hdr_rows) + len(vis_rows)
    for _ in range(max(0, game_h - rows_used)):
        out.append(NC.empty_row(iw, bfg, rst))

    # ── Statusline / command line / bottom border ──────────────────────────────
    out.append(NC.bottom_statusline(iw, bfg, rst, sl_label, cursor_row, len(rows),
                                    cmd_line, cmd_prefix))
    out.append(NC.border_h(iw, bfg, rst, S.BOX_BL, S.BOX_BR))

    if print_size_notice(term):
        return scroll_offset
    print(term.home + term.clear + '\n'.join(out), end='', flush=True)
    return scroll_offset
