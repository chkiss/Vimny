"""Netrw-style overworld renderer (read-only; never mutates game state)."""
from __future__ import annotations
from blessed import Terminal
from engine.player import Player
import render.colors as C
import render.symbols as S
from content.levels import LEVELS, is_unlocked, is_reliquary, level_type
from render.utils import inner_w as _iw


def render_overworld(term: Terminal, player: Player, progress: dict,
                     cursor_row: int, cmd_line: str | None = None,
                     levels: list | None = None,
                     custom_layouts: list | None = None,
                     deleting: bool = False) -> None:
    """
    progress: {level_id (int): {'stars': int, 'complete': bool}}
    cursor_row: index into combined list (standard levels then custom layouts)
    cmd_line: if not None, show command line in hint bar (command mode active)
    custom_layouts: list of layout dicts (admin only); shown under subheading
    """
    visible_levels  = levels if levels is not None else LEVELS
    custom_layouts  = custom_layouts or []
    iw  = _iw(term)
    bfg = C.border_fg()
    rst = C.normal_fg()
    out = []

    def border_h(left, right, fill=S.BOX_H):
        return bfg + left + fill * iw + right + rst

    # ── Row 0: top border ─────────────────────────────────────────────────────
    out.append(border_h(S.BOX_TL, S.BOX_TR))

    # ── Row 1: status bar ────────────────────────────────────────────────────
    full_h        = player.hp // 2
    empty_h       = player.max_hp // 2 - full_h
    hearts_plain  = S.HEART_FULL * full_h + S.HEART_EMPTY * empty_h
    hearts_col    = ((C.heart_full()  + S.HEART_FULL  + rst) * full_h +
                     (C.heart_empty() + S.HEART_EMPTY + rst) * empty_h)
    ow_label      = '-- OVERWORLD --'
    name_tag      = '⌨  <' + player.name + '>'
    left_cols     = len('Vimny  ') + len(name_tag) + 1 + len('  ') + len(hearts_plain) + len('  ')
    #                                               ↑ extra col for wide ⌨
    ow_start      = (iw - len(ow_label)) // 2
    mid_gap       = max(1, ow_start - left_cols)
    right_pad     = max(0, iw - left_cols - mid_gap - len(ow_label))
    out.append(bfg + S.BOX_V + rst +
               C.normal_fg() + 'Vimny  ' + name_tag + rst +
               '  ' + hearts_col + '  ' +
               ' ' * mid_gap +
               C.mode_normal() + ow_label + rst +
               ' ' * right_pad +
               bfg + S.BOX_V + rst)

    # ── Row 2: separator ─────────────────────────────────────────────────────
    out.append(border_h(S.BOX_LT, S.BOX_RT))

    # ── Game area ────────────────────────────────────────────────────────────
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

    def _cols3(left, mid, right):
        """Gaps to lay out left | centered mid | right within iw.

        Returns (gap1, gap2) with gap1+gap2 placing `mid` as centered as the
        left/right anchors allow (>=1 space each side). None if there's no room
        (caller falls back to the two-column layout).
        """
        if not mid or iw - len(left) - len(mid) - len(right) < 2:
            return None
        mid_start = (iw - len(mid)) // 2
        mid_start = max(len(left) + 1, mid_start)
        mid_start = min(mid_start, iw - len(right) - len(mid) - 1)
        if mid_start < len(left) + 1:
            return None
        return mid_start - len(left), iw - len(right) - (mid_start + len(mid))

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
    sb_val = 'discovery order'
    kc     = C.mode_insert()
    qh_pfx = '"   Quick Help: '
    qh_prs = [('j/k', 'move'), ('Enter', 'open'), ('-', 'go up dir'), (':q', 'quit')]
    qh_pl  = qh_pfx + '  '.join(f'{k}:{d}' for k, d in qh_prs)
    qh_col = dfc + qh_pfx + ('  ' + dfc).join(kc + k + dfc + ':' + d for k, d in qh_prs)
    hdr_rows = [
        _div(),
        _hdr(ndl + ' ' * ndl_sp + ver),
        _hdr('"   ~/.vimny/world/'),
        _hdr(sb_lbl + sb_val, dfc + sb_lbl + rst + sb_val),
        _hdr(qh_pl, qh_col),
        _div(),
    ]
    out.extend(hdr_rows)

    # ../ and ./ directory entries
    for di, dentry in enumerate(['../', './']):
        is_cursor = di == cursor_row
        out.append(_row(is_cursor, len(dentry), dfc + dentry))

    # Standard dungeon listing
    for idx, level in enumerate(visible_levels):
        prog     = progress.get(level['id'], {})
        complete = prog.get('complete', False)
        stars    = prog.get('stars', 0)
        unlocked = is_unlocked(level['id'], progress, player.name)

        if complete:
            if level_type(level['id']) != 'dungeon':
                badge = '[COMPLETE]'
            else:
                star_str = '★' * stars + '☆' * (2 - stars)
                badge    = f'[{star_str} COMPLETE]'
            badge_col = C.budget_ok()
        elif unlocked:
            badge     = '[AVAILABLE]'
            badge_col = C.mode_insert()
        else:
            badge     = '[LOCKED]'
            badge_col = C.hint_fg()

        is_cursor = (idx + 2) == cursor_row
        key_text  = level['key']
        cmds      = level.get('commands', '')
        nc        = enfc if is_cursor else (rst if unlocked else C.hint_fg())
        cmd_col   = kc if unlocked else C.hint_fg()   # new keys taught (key color)
        cols      = _cols3(key_text, cmds, badge)
        if cols is not None:
            gap1, gap2 = cols
            colored = (nc + key_text + ' ' * gap1 +
                       cmd_col + cmds + ' ' * gap2 +
                       badge_col + badge)
        else:
            spaces  = max(2, iw - len(key_text) - len(badge))
            colored = nc + key_text + ' ' * spaces + badge_col + badge
        out.append(_row(is_cursor, iw, colored))

    # Custom levels dir entry + tree listing (admin only)
    custom_rows = 0
    if custom_layouts:
        out.append(_row(False, len('custom/'), dfc + 'custom/'))
        custom_rows += 1

        n_custom = len(custom_layouts)
        for ci, layout in enumerate(custom_layouts):
            idx       = len(visible_levels) + ci
            is_last   = ci == n_custom - 1
            tree_char = '└' if is_last else '├'
            name      = layout.get('layout_name', '?')
            badge     = '[CUSTOM]'
            badge_col = C.mode_insert()
            is_cursor = (idx + 2) == cursor_row
            nc        = enfc if is_cursor else rst
            spaces    = max(1, iw - 4 - len(name) - len(badge))
            colored   = '  ' + C.hint_fg() + tree_char + ' ' + nc + name + ' ' * spaces + badge_col + badge
            out.append(_row(is_cursor, iw, colored))
        custom_rows += n_custom

    # Fill remaining game-area rows
    rows_used = len(hdr_rows) + 2 + len(visible_levels) + custom_rows
    for _ in range(max(0, game_h - rows_used)):
        out.append(bfg + S.BOX_V + rst + ' ' * iw + bfg + S.BOX_V + rst)

    # ── Vim statusline / command line ─────────────────────────────────────────
    sl_bg = C.statusline_bg()
    sl_fg = C.statusline_fg()

    if deleting:
        conf     = 'd again to confirm delete · any other key cancels'
        conf_pad = max(0, iw - len(conf) - 1)
        out.append(bfg + S.BOX_V + rst +
                   C.error_bg() + C.error_fg() + ' ' + conf + ' ' * conf_pad + rst +
                   bfg + S.BOX_V + rst)
    elif player.error:
        err_pad = max(0, iw - len(player.error) - 1)
        out.append(bfg + S.BOX_V + rst +
                   C.error_bg() + C.error_fg() + ' ' + player.error +
                   ' ' * err_pad + rst +
                   bfg + S.BOX_V + rst)
    elif cmd_line is not None:
        cmd_text = ':' + cmd_line
        sl_pad   = max(0, iw - len(cmd_text))
        out.append(bfg + S.BOX_V + rst +
                   sl_bg + C.mode_command() + cmd_text +
                   sl_fg + ' ' * sl_pad + rst +
                   bfg + S.BOX_V + rst)
    else:
        sl_label   = '-- OVERWORLD --'
        total_rows = len(visible_levels) + len(custom_layouts) + 2
        sl_right   = f'{cursor_row + 1}/{total_rows} '
        sl_mid     = max(0, iw - len(sl_label) - 2 - len(sl_right))
        out.append(bfg + S.BOX_V + rst +
                   sl_bg + C.mode_normal() + ' ' + sl_label + ' ' +
                   sl_bg + sl_fg + ' ' * sl_mid + sl_right + rst +
                   bfg + S.BOX_V + rst)

    # ── Bottom border ─────────────────────────────────────────────────────────
    out.append(border_h(S.BOX_BL, S.BOX_BR))

    print(term.home + '\n'.join(out), end='', flush=True)
