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

    def border_h(left, right, fill=S.BOX_H):
        return bfg + left + fill * iw + right + rst

    # ── Top border ────────────────────────────────────────────────────────────
    out.append(border_h(S.BOX_TL, S.BOX_TR))

    # ── Status bar ────────────────────────────────────────────────────────────
    full_h       = player.hp // 2
    empty_h      = player.max_hp // 2 - full_h
    hearts_plain = S.HEART_FULL * full_h + S.HEART_EMPTY * empty_h
    hearts_col   = ((C.heart_full()  + S.HEART_FULL  + rst) * full_h +
                    (C.heart_empty() + S.HEART_EMPTY + rst) * empty_h)
    sl_label     = '-- SCROLLS --'
    name_tag     = '⌨  <' + player.name + '>'
    left_cols    = len('Vimny  ') + len(name_tag) + 1 + len('  ') + len(hearts_plain) + len('  ')
    sl_start     = (iw - len(sl_label)) // 2
    mid_gap      = max(1, sl_start - left_cols)
    right_pad    = max(0, iw - left_cols - mid_gap - len(sl_label))
    out.append(bfg + S.BOX_V + rst +
               C.normal_fg() + 'Vimny  ' + name_tag + rst +
               '  ' + hearts_col + '  ' +
               ' ' * mid_gap +
               C.mode_normal() + sl_label + rst +
               ' ' * right_pad +
               bfg + S.BOX_V + rst)

    # ── Separator ─────────────────────────────────────────────────────────────
    out.append(border_h(S.BOX_LT, S.BOX_RT))

    game_h  = term.height - 5
    n_disc  = sum(1 for s in SCROLL_CATALOG if s['id'] in discovered)
    n_total = len(SCROLL_CATALOG)

    sb   = C.sel_bg()
    dfc  = C.dir_fg()
    enfc = C.entry_fg()

    def _row(is_cursor, vis, colored):
        if is_cursor:
            return (bfg + S.BOX_V + rst +
                    sb + colored + rst + sb +
                    ' ' * max(0, iw - vis) + rst +
                    bfg + S.BOX_V + rst)
        return (bfg + S.BOX_V + rst +
                colored +
                ' ' * max(0, iw - vis) +
                bfg + S.BOX_V + rst)

    def _hdr(plain, colored=None):
        pad = max(0, iw - len(plain))
        return (bfg + S.BOX_V + rst +
                (dfc + plain if colored is None else colored) + rst +
                ' ' * pad + bfg + S.BOX_V + rst)

    def _div():
        return _hdr('" ' + '=' * (iw - 2))

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
        out.append(bfg + S.BOX_V + rst + ' ' * iw + bfg + S.BOX_V + rst)

    # ── Statusline / command line ─────────────────────────────────────────────
    sl_w  = iw

    if cmd_line is not None:
        cmd_text = ':' + cmd_line
        sl_pad   = max(0, sl_w - len(cmd_text))
        out.append(bfg + S.BOX_V + rst +
                   C.mode_command() + cmd_text +
                   rst + ' ' * sl_pad +
                   bfg + S.BOX_V + rst)
    else:
        sl_right = f'{cursor_row + 1}/{len(rows)} '
        sl_mid   = max(0, sl_w - len(sl_label) - 2 - len(sl_right))
        out.append(bfg + S.BOX_V + rst +
                   C.mode_normal() + ' ' + sl_label + ' ' +
                   rst + ' ' * sl_mid + sl_right +
                   bfg + S.BOX_V + rst)

    # ── Bottom border ─────────────────────────────────────────────────────────
    out.append(border_h(S.BOX_BL, S.BOX_BR))

    print(term.home + term.clear + '\n'.join(out), end='', flush=True)
