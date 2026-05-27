"""Parent directory renderer — ~/.vimny/ hub between world/, scrolls/, saves/."""
from __future__ import annotations
from blessed import Terminal
from engine.player import Player
import render.colors as C
import render.symbols as S
from render.utils import inner_w as _iw

ENTRIES = ['saves/', 'scrolls/', 'world/']


def render_parent_dir(
    term: Terminal,
    player: Player,
    cursor_row: int,
    cmd_line: str | None = None,
) -> None:
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
    sl_label     = '-- OVERWORLD --'
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

    game_h = term.height - 5

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
    for idx, entry in enumerate(ENTRIES):
        is_cursor = (idx + 2) == cursor_row
        nc        = enfc if is_cursor else dfc
        out.append(_row(is_cursor, len(entry), nc + entry))

    # ── Empty rows ────────────────────────────────────────────────────────────
    rows_used = len(hdr_rows) + 2 + len(ENTRIES)
    for _ in range(max(0, game_h - rows_used)):
        out.append(bfg + S.BOX_V + rst + ' ' * iw + bfg + S.BOX_V + rst)

    # ── Statusline / command line ─────────────────────────────────────────────
    sl_w  = iw + 2
    sl_bg = C.statusline_bg()
    sl_fg = C.statusline_fg()

    if cmd_line is not None:
        cmd_text = ':' + cmd_line
        sl_pad   = max(0, sl_w - len(cmd_text))
        out.append(sl_bg + C.mode_command() + cmd_text +
                   sl_fg + ' ' * sl_pad + rst)
    else:
        sl_right = f'{cursor_row + 1}/{len(ENTRIES) + 2} '
        sl_mid   = max(0, sl_w - len(sl_label) - 2 - len(sl_right))
        out.append(sl_bg + C.mode_normal() + ' ' + sl_label + ' ' +
                   sl_bg + sl_fg + ' ' * sl_mid + sl_right + rst)

    # ── Bottom border ─────────────────────────────────────────────────────────
    out.append(border_h(S.BOX_BL, S.BOX_BR))

    print(term.home + term.clear + '\n'.join(out), end='', flush=True)
