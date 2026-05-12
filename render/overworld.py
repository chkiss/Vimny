"""Netrw-style overworld renderer (read-only; never mutates game state)."""
from __future__ import annotations
from blessed import Terminal
from engine.player import Player
import render.colors as C
import render.symbols as S
from content.levels import LEVELS, is_unlocked
from render.utils import inner_w as _iw


def render_overworld(term: Terminal, player: Player, progress: dict,
                     cursor_row: int, cmd_line: str | None = None,
                     levels: list | None = None,
                     custom_layouts: list | None = None) -> None:
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
    title_plain   = '  ' + hearts_plain + '  Vimny  -- OVERWORLD --'
    pad           = max(0, iw - len(title_plain))
    out.append(bfg + S.BOX_V + rst +
               '  ' + hearts_col + '  ' +
               C.normal_fg() + 'Vimny  ' +
               C.mode_normal() + '-- OVERWORLD --' + rst +
               ' ' * pad +
               bfg + S.BOX_V + rst)

    # ── Row 2: separator ─────────────────────────────────────────────────────
    out.append(border_h(S.BOX_LT, S.BOX_RT))

    # ── Game area ────────────────────────────────────────────────────────────
    game_h = term.height - 7

    # netrw-style header
    header_lines = [
        '',
        '  === The Known World ===',
        '  /world/',
        '  Sorted by: discovery order',
    ]
    for line in header_lines:
        pad = max(0, iw - len(line))
        out.append(bfg + S.BOX_V + rst +
                   C.hint_fg() + line + rst +
                   ' ' * pad +
                   bfg + S.BOX_V + rst)

    # Divider line
    div = '  ' + '=' * (iw - 2)
    out.append(bfg + S.BOX_V + rst + C.hint_fg() + div + rst + bfg + S.BOX_V + rst)

    # Standard dungeon listing
    for idx, level in enumerate(visible_levels):
        prog     = progress.get(level['id'], {})
        complete = prog.get('complete', False)
        stars    = prog.get('stars', 0)
        unlocked = is_unlocked(level['id'], progress, player.name)

        if complete:
            star_str  = '★' * stars + '☆' * (2 - stars)
            badge     = f'[{star_str} COMPLETE]'
            badge_col = C.budget_ok()
        elif unlocked:
            badge     = '[AVAILABLE]'
            badge_col = C.mode_insert()
        else:
            badge     = '[LOCKED]'
            badge_col = C.hint_fg()

        cursor_sym = '► ' if idx == cursor_row else '  '
        key_text   = level['key']
        spaces     = max(2, iw - len(cursor_sym) - len(key_text) - len(badge))

        cursor_col = C.player_fg() if idx == cursor_row else rst
        key_col    = C.normal_fg() if unlocked else C.hint_fg()
        colored    = (cursor_col + cursor_sym + rst +
                      key_col + key_text + rst +
                      ' ' * spaces +
                      badge_col + badge + rst)
        out.append(bfg + S.BOX_V + rst + colored + bfg + S.BOX_V + rst)

    # Custom levels subheading + tree listing (admin only)
    custom_rows = 0
    if custom_layouts:
        heading      = '  Custom levels:'
        heading_pad  = max(0, iw - len(heading))
        out.append(bfg + S.BOX_V + rst +
                   C.hint_fg() + heading + rst +
                   ' ' * heading_pad +
                   bfg + S.BOX_V + rst)
        custom_rows += 1

        n_custom = len(custom_layouts)
        for ci, layout in enumerate(custom_layouts):
            idx        = len(visible_levels) + ci
            is_last    = ci == n_custom - 1
            tree_char  = '└' if is_last else '├'
            name       = layout.get('layout_name', '?')
            badge      = '[CUSTOM]'
            badge_col  = C.mode_insert()
            cursor_sym = '► ' if idx == cursor_row else '  '
            prefix     = cursor_sym + tree_char + ' '
            spaces     = max(1, iw - len(prefix) - len(name) - len(badge))

            cursor_col = C.player_fg() if idx == cursor_row else rst
            colored    = (cursor_col + cursor_sym + rst +
                          C.hint_fg() + tree_char + ' ' + rst +
                          C.normal_fg() + name + rst +
                          ' ' * spaces +
                          badge_col + badge + rst)
            out.append(bfg + S.BOX_V + rst + colored + bfg + S.BOX_V + rst)
        custom_rows += n_custom

    # Fill remaining game-area rows
    rows_used = len(header_lines) + 1 + len(visible_levels) + custom_rows
    for _ in range(max(0, game_h - rows_used)):
        out.append(bfg + S.BOX_V + rst + ' ' * iw + bfg + S.BOX_V + rst)

    # ── Vim statusline / command line ─────────────────────────────────────────
    sl_w  = iw + 2
    sl_bg = C.statusline_bg()
    sl_fg = C.statusline_fg()

    if player.error:
        err_pad = max(0, sl_w - len(player.error) - 1)
        out.append(C.error_bg() + C.error_fg() + ' ' + player.error +
                   ' ' * err_pad + rst)
    elif cmd_line is not None:
        cmd_text = ':' + cmd_line
        sl_pad   = max(0, sl_w - len(cmd_text))
        out.append(sl_bg + C.mode_command() + cmd_text +
                   sl_fg + ' ' * sl_pad + rst)
    else:
        sl_label = '-- OVERWORLD --'
        total_rows = len(visible_levels) + len(custom_layouts)
        sl_right = f'{cursor_row + 1}/{total_rows} '
        sl_mid   = max(0, sl_w - len(sl_label) - 2 - len(sl_right))
        out.append(sl_bg + C.mode_normal() + ' ' + sl_label + ' ' +
                   sl_bg + sl_fg + ' ' * sl_mid + sl_right + rst)

    # ── Bottom separator ──────────────────────────────────────────────────────
    out.append(border_h(S.BOX_LT, S.BOX_RT))

    # ── Hint bar ──────────────────────────────────────────────────────────────
    hint_text = 'j/k:move cursor  Enter:open dungeon  :q quit'
    out.append(bfg + S.BOX_V + rst +
               C.hint_fg() + hint_text + rst +
               ' ' * max(0, iw - len(hint_text)) +
               bfg + S.BOX_V + rst)

    # ── Bottom border ─────────────────────────────────────────────────────────
    out.append(border_h(S.BOX_BL, S.BOX_BR))

    print(term.home + '\n'.join(out), end='', flush=True)
