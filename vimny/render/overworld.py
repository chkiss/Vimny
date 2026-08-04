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

"""Netrw-style overworld renderer (read-only; never mutates game state).

The overworld is a netrw buffer: a flat list of lines (the `"` header comments,
``../`` / ``./``, the levels, then any custom layouts). Every line is selectable
— the cursor is an index into this list — and motions (j/k, gg/G, {n}G, H/M/L,
Ctrl-d/u) move over it just like a real buffer. ``:set number`` / ``relativenumber``
toggle the line-number gutter.
"""
from __future__ import annotations
from blessed import Terminal
from vimny.engine.player import Player
import vimny.render.colors as C
import vimny.render.symbols as S
import vimny.render.netrw_chrome as NC
from vimny.content.levels import is_unlocked, level_type, key_for_slug
from vimny.render.utils import inner_w as _iw, subtree_lines, tree_glyph


def build_lines(levels: list, custom_layouts: list, community: list = (),
                drafts: list = ()) -> list:
    """The netrw buffer as a flat list of line dicts (comments + dirs + entries).
    Each: {'type': 'comment'|'parent'|'self'|'level'|'subhdr'|'custom'
           |'community', ...}.

    `community` holds validated shelf entries from ~/.Vimny/levels/ — the bonus
    wing. It sits AFTER the curriculum and after custom/, because it is extra
    content rather than part of the designed sequence."""
    lines: list = [{'type': 'comment', 'tag': t}
                   for t in ('div', 'title', 'path', 'sort', 'help', 'div')]
    lines.append({'type': 'parent'})
    lines.append({'type': 'self'})
    for lv in levels:
        lines.append({'type': 'level', 'level': lv})
    lines += subtree_lines('custom/', custom_layouts, 'custom', 'layout')
    lines += subtree_lines('community/', list(community), 'community', 'shelf')
    # forge/ is last: it is the only section that is not something to PLAY.
    lines += subtree_lines('forge/', list(drafts), 'draft', 'draft')
    return lines


def entry_label(ln: dict) -> str:
    """The first-column text of a community or draft row: the level's name with
    its author trailing it.

    The author belongs to the NAME. It is part of how you refer to a level you
    downloaded — "Ana's maze" — whereas the middle column exists to answer one
    other question, what the level asks of you, and mixing the two put the
    command list on no consistent axis. Shared with `_content` under the
    single-source law above, so `/Ana` finds the row the renderer draws.
    """
    entry = ln.get('shelf') or ln.get('draft')
    if entry is None:
        return ''
    who = getattr(getattr(entry, 'level', None), 'author', '') or ''
    return f'{entry.name} by {who}' if who else entry.name


def line_search_text(ln: dict) -> str:
    """The text `/` searches for a buffer line.

    LAW (single source of truth): search must match what the
    renderer DRAWS — the label text, gutter excluded. Level and custom
    lines share their exact source strings with `_content` (key_for_slug /
    layout_name); comment lines use the width-INDEPENDENT core of their
    rendered text (the divider width and version tag vary with the
    terminal, and search must not depend on window size). If `_content`
    ever decorates a label, decorate it here too — a silent desync makes
    `/` lie about the screen.
    """
    t = ln['type']
    if t == 'level':
        return key_for_slug(ln['level']['slug'])
    if t == 'custom':
        return ln['layout'].get('layout_name', '?')
    if t in ('community', 'draft'):
        return entry_label(ln)
    if t == 'parent':
        return '../'
    if t == 'self':
        return './'
    if t == 'subhdr':
        return ln.get('label', 'custom/')
    if t == 'comment':
        return {
            'div':   '" ' + '=' * 20,
            'title': '" Netrw Directory Listing',
            'path':  '"   ~/.vimny/world/',
            'sort':  '"   Sorted by      discovery order',
            'help':  '"   Quick Help:',
        }.get(ln.get('tag', ''), '"')
    return ''


def line_label_offset(ln: dict) -> int:
    """Screen column where a line's searchable label begins (companion to
    line_search_text — same single-source law): custom layouts draw a
    2-space + tree-glyph indent before the name; everything else starts
    flush after the gutter."""
    return 4 if ln['type'] in ('custom', 'community', 'draft') else 0


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
                     cmd_line: str | None = None, cmd_prefix: str = ':',
                     number_mode: str = 'number',
                     deleting: bool = False, renaming: str | None = None,
                     naming_new: bool = False,
                     scroll_offset: int = 0, col: int = 0) -> tuple[int, int, int]:
    """Render the overworld; returns (scroll_offset, cursor_y, cursor_x) so the
    caller can place the live cursor. ``number_mode`` ∈ {'number','relativenumber','none'}."""
    iw  = _iw(term)
    # The box width is capped (inner_w maxes at 189-2); on a wider terminal, left-anchoring
    # it would shove everything — including the centred columns — off to the left. Pad it
    # so the whole box sits in the middle of the player's actual viewport.
    pad = ' ' * max(0, (term.width - (iw + 2)) // 2)
    bfg = C.border_fg()
    rst = C.normal_fg()
    out = []
    ow_label = '-- OVERWORLD --'

    # ── Rows 0–2: top border / status bar / separator ──────────────────────────
    out.append(NC.border_h(iw, bfg, rst, S.BOX_TL, S.BOX_TR))
    out.append(NC.status_bar(iw, bfg, rst, player, ow_label, progress.get('horse_name', '')))
    out.append(NC.border_h(iw, bfg, rst, S.BOX_LT, S.BOX_RT))

    # ── Line area ──────────────────────────────────────────────────────────────
    game_h = term.height - 5                  # rows available for the buffer
    sb     = C.sel_bg()
    dfc    = C.dir_fg()
    enfc   = C.entry_fg()
    kc     = C.mode_insert()

    GW = 0 if number_mode == 'none' else 4    # gutter width ("123 ")
    cw = max(1, iw - GW)                       # content width to the right of the gutter

    # Fixed left/right columns so the command list reads as a centred MIDDLE column,
    # independent of each row's own name length: the longest dungeon name defines the
    # left column, the widest completion badge the right column. The command is then
    # centred in the gap between them (names run longer than badges, so this sits right
    # of the box centre — where it visually belongs).
    name_col  = max((len(key_for_slug(ln['level']['slug'])) for ln in lines
                     if ln['type'] == 'level'), default=0)
    badge_col = len('[★★ COMPLETE]')

    ver    = '(netrw v.132y)'
    ndl    = '" Netrw Directory Listing'
    qh_pfx = '"   Quick Help: '
    qh_prs = [('j/k', 'move'), ('gg/G', 'top/bot'), ('Enter', 'open'),
              ('D', 'del'), ('R', 'rename'), ('-', 'up'), (':q', 'quit')]
    # `%` is netrw's "new file", and here it forges a new level. It is the ONLY
    # way to start one and it is admin-only, so it is listed for the admin and
    # for nobody else — a key everyone can see but only one player may press is
    # worse than one that is simply not advertised. It goes NEAR THE FRONT
    # rather than at the end because the line is trimmed from the end on a
    # narrow terminal, and the hint that exists to be discovered is the one that
    # must not be the first casualty.
    if player.name == 'admin':
        qh_prs.insert(3, ('%', 'new'))

    def _help_line() -> str:
        """The hint row, never wider than the box.

        `_row` pads with `max(0, cw - vis)` and does nothing when a row is too
        long, so an over-wide line does not clip — it pushes the right border
        out, which reads as the frame being broken rather than the text being
        long. This row was already 82 columns against a 74-column content width
        on an 80-column terminal, so it was doing exactly that before `%` was
        ever added to it. Pairs are dropped from the END until it fits: a
        shorter list of hints is honest, half a border is not.
        """
        prs = list(qh_prs)
        while prs:
            line = qh_pfx + '  '.join(f'{k}:{d}' for k, d in prs)
            if len(line) <= cw:
                return line
            prs.pop()
        return qh_pfx.rstrip()[:cw]

    comment_text = {
        'div':   '" ' + '=' * max(0, cw - 2),
        'title': ndl + ' ' * max(0, cw - len(ndl) - len(ver)) + ver,
        'path':  '"   ~/.vimny/world/',
        'sort':  '"   Sorted by      discovery order',
        'help':  _help_line(),
    }

    def _cols3(left, mid, right):
        """Gaps to lay left | mid | right, with mid centred in the gap BETWEEN the fixed
        left column (longest name) and right column (widest badge) — so the commands form
        a true middle column instead of drifting with each row's name length."""
        if not mid:
            return None
        region_l = max(name_col, len(left)) + 1
        region_r = cw - max(badge_col, len(right)) - 1
        if region_r - region_l < len(mid):
            return None
        mid_start = region_l + (region_r - region_l - len(mid)) // 2
        mid_start = max(len(left) + 1, mid_start)
        mid_start = min(mid_start, cw - len(right) - len(mid) - 1)
        if mid_start < len(left) + 1:
            return None
        return mid_start - len(left), cw - len(right) - (mid_start + len(mid))

    def _subtree_row(name, mid, badge, badge_col, tree, is_cursor):
        """One custom//community//forge row: name, a middle column, a badge.

        The middle column is dropped rather than truncated when the terminal is
        narrow — a half-written command list reads as a level that requires `w`,
        `b`, `e` when it also requires `f`, and a wrong claim is worse than no
        claim. The name and the badge always survive.

        It is laid out with the SAME `_cols3` the curriculum rows use, so a
        community level's `requires`/`+teaches` lands in the one middle column
        rather than trailing its own name. That column is the answer to a single
        question — what does this level ask of me — and a reader compares down
        it; a list that starts at a different x on every row cannot be read that
        way. `_cols3` returns None when the name is too long to leave the column
        clear, which falls through to the badge-only form below."""
        nc     = enfc if is_cursor else rst
        left   = '  ' + tree + ' ' + name
        cols   = _cols3(left, mid, badge) if mid else None
        if cols is not None:
            gap_l, gap_r = cols
            body  = (C.hint_fg() + tree + ' ' + nc + name + ' ' * gap_l +
                     dfc + mid + ' ' * gap_r + badge_col + badge)
        else:
            body = (C.hint_fg() + tree + ' ' + nc + name +
                    ' ' * max(1, cw - 4 - len(name) - len(badge)) +
                    badge_col + badge)
        return '  ' + body, cw

    def _shelf_mid(level) -> str:
        """The middle column for a community level or draft: what it asks of
        you — `requires`, then `teaches` marked with a leading +.

        Both command lists, not one. `requires` is what the level assumes you
        already know and `teaches` is what it introduces, and a row showing only
        one of them cannot answer the question the player is actually asking:
        whether this is a level they can play yet. Shipped levels get the same
        information from the curriculum; a community level has nowhere else to
        say it. The author is NOT here — it rides with the name in column one,
        so this column holds commands and nothing else and can be read down."""
        if level is None:
            return ''
        return ' '.join(list(level.requires) + [f'+{t}' for t in level.teaches])

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
            # A layout is a saved ROOM, not a level: it has no author block and
            # no command list to show, so its middle column stays empty.
            return _subtree_row(name, '', '[CUSTOM]', C.mode_insert(),
                                tree, is_cursor)
        if t == 'community':
            shelf = line['shelf']
            name  = entry_label(line)
            tree  = tree_glyph(line.get('last'))
            # A broken level says so ON THE ROW. Hiding it would leave a player
            # wondering where the file they downloaded went; naming the fault is
            # what lets them fix it or tell the author.
            if shelf.ok:
                badge, badge_col = f'[par {shelf.report.par}]', C.chest_fg()
            else:
                badge, badge_col = '[BROKEN]', C.error_fg()
            return _subtree_row(name, _shelf_mid(shelf.level), badge, badge_col,
                                tree, is_cursor)
        if t == 'draft':
            d    = line['draft']
            name = entry_label(line)
            tree = tree_glyph(line.get('last'))
            # The badge is the draft's STATE, because that is the only thing an
            # author wants from this row: whether it has a tape yet, and if so
            # what it cost. A draft with no tape is the normal early condition,
            # not a fault, so it does not wear the community shelf's [BROKEN].
            if not d.ok:
                badge, badge_col = '[UNREADABLE]', C.error_fg()
            elif not d.level.solution:
                badge, badge_col = '[NO TAPE]', C.hint_fg()
            else:
                badge, badge_col = '[DRAFT]', C.mode_insert()
            return _subtree_row(name, _shelf_mid(d.level), badge, badge_col,
                                tree, is_cursor)
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
        out.append(NC.empty_row(iw, bfg, rst))

    # ── Vim statusline / command line ──────────────────────────────────────────
    def _bar(prefix_col, text):
        pad = max(0, iw - len(text) - 1)
        return (bfg + S.BOX_V + rst + prefix_col + ' ' + text + ' ' * pad + rst +
                bfg + S.BOX_V + rst)

    cur_y = 3 + (cursor - scroll_offset)        # default: the live cursor sits on its line
    cur_x = 1 + GW + line_label_offset(lines[cursor]) + max(0, col)
    sl_y  = 3 + avail
    if deleting:
        out.append(_bar(C.error_bg() + C.error_fg(),
                        'Delete this custom layout?  y to confirm · any other key cancels'))
    elif renaming is not None:
        text = ('Enter filename: ' if naming_new else 'Rename to: ') + renaming
        out.append(_bar(C.mode_command(), text))
        cur_y, cur_x = sl_y, 1 + 1 + len(text)
    elif player.error:
        out.append(_bar(C.error_bg() + C.error_fg(), player.error))
    elif cmd_line is not None:
        # cmd_prefix is ':' for commands, '/' or '?' for a search — Vim
        # never shows ':' before a search prompt.
        out.append(NC.bottom_statusline(iw, bfg, rst, ow_label, cursor,
                                        len(lines), cmd_line,
                                        cmd_prefix=cmd_prefix))
        cur_y, cur_x = sl_y, 1 + len(cmd_prefix + cmd_line)
    else:
        out.append(NC.bottom_statusline(iw, bfg, rst, ow_label, cursor, len(lines), None))

    # ── Bottom border ──────────────────────────────────────────────────────────
    out.append(NC.border_h(iw, bfg, rst, S.BOX_BL, S.BOX_BR))

    print(term.home + pad + ('\n' + pad).join(out), end='', flush=True)
    return scroll_offset, cur_y, cur_x + len(pad)
