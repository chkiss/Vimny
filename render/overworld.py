"""Netrw-style overworld renderer (read-only; never mutates game state).

The overworld is a netrw buffer: a flat list of lines (the `"` header comments,
``../`` / ``./``, the levels, then any custom layouts). Every line is selectable
— the cursor is an index into this list — and motions (j/k, gg/G, {n}G, H/M/L,
Ctrl-d/u) move over it just like a real buffer. ``:set number`` / ``relativenumber``
toggle the line-number gutter.
"""
from __future__ import annotations
from blessed import Terminal
from engine.player import Player
import render.colors as C
import render.symbols as S
from content.levels import is_unlocked, level_type, key_for_slug
from render.utils import inner_w as _iw, subtree_lines, tree_glyph


def build_lines(levels: list, custom_layouts: list) -> list:
    """The netrw buffer as a flat list of line dicts (comments + dirs + entries).
    Each: {'type': 'comment'|'parent'|'self'|'level'|'subhdr'|'custom', ...}."""
    lines: list = [{'type': 'comment', 'tag': t}
                   for t in ('div', 'title', 'path', 'sort', 'help', 'div')]
    lines.append({'type': 'parent'})
    lines.append({'type': 'self'})
    for lv in levels:
        lines.append({'type': 'level', 'level': lv})
    lines += subtree_lines('custom/', custom_layouts, 'custom', 'layout')
    return lines


def default_cursor(lines: list) -> int:
    """The line the cursor rests on when the overworld opens: the first ``../``."""
    for i, ln in enumerate(lines):
        if ln['type'] == 'parent':
            return i
    return 0


def _scroll_offset(cursor: int, scroll_offset: int, avail: int, n_lines: int) -> int:
    """Vim-like viewport top: keep the previous offset unless the cursor has left
    the [offset, offset+avail) window, then scroll just enough to bring it back.
    The cursor moves freely inside the window — it does not cling to an edge."""
    max_off = max(0, n_lines - avail)
    if cursor < scroll_offset:
        scroll_offset = cursor
    elif cursor >= scroll_offset + avail:
        scroll_offset = cursor - avail + 1
    return max(0, min(scroll_offset, max_off))


def render_overworld(term: Terminal, player: Player, progress: dict,
                     cursor: int, lines: list, *,
                     cmd_line: str | None = None, number_mode: str = 'number',
                     deleting: bool = False, renaming: str | None = None,
                     scroll_offset: int = 0) -> tuple[int, int, int]:
    """Render the overworld; returns (scroll_offset, cursor_y, cursor_x) so the
    caller can place the live cursor. ``number_mode`` ∈ {'number','relativenumber','none'}."""
    iw  = _iw(term)
    bfg = C.border_fg()
    rst = C.normal_fg()
    out = []

    def border_h(left, right, fill=S.BOX_H):
        return bfg + left + fill * iw + right + rst

    # ── Row 0: top border ─────────────────────────────────────────────────────
    out.append(border_h(S.BOX_TL, S.BOX_TR))

    # ── Row 1: status bar ──────────────────────────────────────────────────────
    full_h        = player.hp // 2
    empty_h       = player.max_hp // 2 - full_h
    hearts_plain  = S.HEART_FULL * full_h + S.HEART_EMPTY * empty_h
    hearts_col    = ((C.heart_full()  + S.HEART_FULL  + rst) * full_h +
                     (C.heart_empty() + S.HEART_EMPTY + rst) * empty_h)
    ow_label      = '-- OVERWORLD --'
    name_tag      = '⌨  <' + player.name + '>'
    left_cols     = len('Vimny  ') + len(name_tag) + 1 + len('  ') + len(hearts_plain) + len('  ')
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

    # ── Row 2: separator ───────────────────────────────────────────────────────
    out.append(border_h(S.BOX_LT, S.BOX_RT))

    # ── Line area ──────────────────────────────────────────────────────────────
    game_h = term.height - 5                  # rows available for the buffer
    sb     = C.sel_bg()
    dfc    = C.dir_fg()
    enfc   = C.entry_fg()
    kc     = C.mode_insert()

    GW = 0 if number_mode == 'none' else 4    # gutter width ("123 ")
    cw = max(1, iw - GW)                       # content width to the right of the gutter

    ver    = '(netrw v13ny)'
    ndl    = '" Netrw Directory Listing'
    qh_pfx = '"   Quick Help: '
    qh_prs = [('j/k', 'move'), ('gg/G', 'top/bot'), ('Enter', 'open'),
              ('D', 'del'), ('R', 'rename'), ('-', 'up'), (':q', 'quit')]
    comment_text = {
        'div':   '" ' + '=' * max(0, cw - 2),
        'title': ndl + ' ' * max(0, cw - len(ndl) - len(ver)) + ver,
        'path':  '"   ~/.vimny/world/',
        'sort':  '"   Sorted by      discovery order',
        'help':  qh_pfx + '  '.join(f'{k}:{d}' for k, d in qh_prs),
    }

    def _cols3(left, mid, right):
        """Gaps to lay left | centred mid | right within the content width."""
        if not mid or cw - len(left) - len(mid) - len(right) < 2:
            return None
        mid_start = (cw - len(mid)) // 2
        mid_start = max(len(left) + 1, mid_start)
        mid_start = min(mid_start, cw - len(right) - len(mid) - 1)
        if mid_start < len(left) + 1:
            return None
        return mid_start - len(left), cw - len(right) - (mid_start + len(mid))

    def _content(idx, line):
        """(colored, visible_width) for a buffer line. is_cursor brightens it."""
        is_cursor = idx == cursor
        t = line['type']
        if t == 'comment':
            txt = comment_text[line['tag']]
            return dfc + txt, len(txt)
        if t in ('parent', 'self'):
            txt = '../' if t == 'parent' else './'
            return dfc + txt, len(txt)
        if t == 'subhdr':
            label = line.get('label', 'custom/')
            return dfc + label, len(label)
        if t == 'custom':
            name = line['layout'].get('layout_name', '?')
            tree = tree_glyph(line.get('last'))
            badge, badge_col = '[CUSTOM]', C.mode_insert()
            nc = enfc if is_cursor else rst
            spaces = max(1, cw - 4 - len(name) - len(badge))
            return ('  ' + C.hint_fg() + tree + ' ' + nc + name + ' ' * spaces +
                    badge_col + badge), cw
        # level
        lv       = line['level']
        prog     = progress.get(lv['slug'], {})
        complete = prog.get('complete', False)
        stars    = prog.get('stars', 0)
        unlocked = is_unlocked(lv['slug'], progress, player.name)
        if complete:
            if level_type(lv['slug']) != 'dungeon':
                badge = '[COMPLETE]'
            else:
                badge = f"[{'★' * stars}{'☆' * (2 - stars)} COMPLETE]"
            badge_col = C.budget_ok()
        elif unlocked:
            badge, badge_col = '[AVAILABLE]', C.mode_insert()
        else:
            badge, badge_col = '[LOCKED]', C.hint_fg()
        nc       = enfc if is_cursor else (rst if unlocked else C.hint_fg())
        cmd_col  = kc if unlocked else C.hint_fg()
        key_text = key_for_slug(lv['slug'])
        cmds     = lv.get('commands', '')
        cols     = _cols3(key_text, cmds, badge)
        if cols is not None:
            gap1, gap2 = cols
            colored = (nc + key_text + ' ' * gap1 +
                       cmd_col + cmds + ' ' * gap2 + badge_col + badge)
        else:
            spaces  = max(2, cw - len(key_text) - len(badge))
            colored = nc + key_text + ' ' * spaces + badge_col + badge
        return colored, cw

    def _lineno(idx):
        if number_mode == 'none':
            return ''
        if number_mode == 'relativenumber':
            n = 0 if idx == cursor else abs(idx - cursor)
        else:
            n = idx + 1
        return f'{n:>3} '

    def _row(idx, line):
        colored, vis = _content(idx, line)
        g   = _lineno(idx)
        pad = ' ' * max(0, cw - vis)
        if idx == cursor:                                 # full-line selection
            gtxt = (enfc + g) if g else ''
            return (bfg + S.BOX_V + rst + sb + gtxt + colored + pad + rst +
                    bfg + S.BOX_V + rst)
        gtxt = (C.hint_fg() + g + rst) if g else ''
        return (bfg + S.BOX_V + rst + gtxt + colored + pad +
                bfg + S.BOX_V + rst)

    avail         = max(1, game_h)
    scroll_offset = _scroll_offset(cursor, scroll_offset, avail, len(lines))
    vis_lines     = lines[scroll_offset : scroll_offset + avail]
    for k, line in enumerate(vis_lines):
        out.append(_row(scroll_offset + k, line))
    for _ in range(max(0, avail - len(vis_lines))):
        out.append(bfg + S.BOX_V + rst + ' ' * iw + bfg + S.BOX_V + rst)

    # ── Vim statusline / command line ──────────────────────────────────────────
    def _bar(prefix_col, text):
        pad = max(0, iw - len(text) - 1)
        return (bfg + S.BOX_V + rst + prefix_col + ' ' + text + ' ' * pad + rst +
                bfg + S.BOX_V + rst)

    cur_y = 3 + (cursor - scroll_offset)        # default: the live cursor sits on its line
    cur_x = 1 + GW
    sl_y  = 3 + avail
    if deleting:
        out.append(_bar(C.error_bg() + C.error_fg(),
                        'Delete this custom layout?  y to confirm · any other key cancels'))
    elif renaming is not None:
        text = 'Rename to: ' + renaming
        out.append(_bar(C.mode_command(), text))
        cur_y, cur_x = sl_y, 1 + 1 + len(text)
    elif player.error:
        out.append(_bar(C.error_bg() + C.error_fg(), player.error))
    elif cmd_line is not None:
        text = ':' + cmd_line
        out.append(bfg + S.BOX_V + rst + C.mode_command() + text + rst +
                   ' ' * max(0, iw - len(text)) + bfg + S.BOX_V + rst)
        cur_y, cur_x = sl_y, 1 + len(text)
    else:
        sl_label = '-- OVERWORLD --'
        sl_right = f'{cursor + 1}/{len(lines)} '
        sl_mid   = max(0, iw - len(sl_label) - 2 - len(sl_right))
        out.append(bfg + S.BOX_V + rst +
                   C.mode_normal() + ' ' + sl_label + ' ' +
                   rst + ' ' * sl_mid + sl_right +
                   bfg + S.BOX_V + rst)

    # ── Bottom border ──────────────────────────────────────────────────────────
    out.append(border_h(S.BOX_BL, S.BOX_BR))

    print(term.home + '\n'.join(out), end='', flush=True)
    return scroll_offset, cur_y, cur_x
