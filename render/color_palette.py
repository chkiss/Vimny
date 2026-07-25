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

"""Color palette renderer — ~/.vimny/colors/ (admin only).

Design: _META holds curated descriptions; _GROUPS holds curated ordering.
At render time the module introspects render.colors for zero-arg callables
so new colors appear automatically (in an 'Other' group if ungrouped, with
'?' hex if unmetadata'd).  Only _META and _GROUPS need editing for polish.
"""
from __future__ import annotations
import inspect
from blessed import Terminal
from engine.player import Player
import render.colors as C
import render.symbols as S
from render.utils import inner_w as _iw

_SWATCH = '███████'
_SW = 7   # swatch visible width
_NW = 22  # name column width
_HW = 12  # hex/label column width

# ── Curated metadata (hex label, role description, kind) ─────────────────────
# kind: 'fg' = foreground swatch on floor_bg, 'bg' = background block
_META: dict[str, tuple[str, str, str]] = {
    'wall_bg':              ('#0F0F14', 'Wall',              'bg'),
    'floor_bg':             ('#1C1C23', 'Floor',             'bg'),
    'visual_sel_bg':        ('#46285A', 'Visual selection',  'bg'),
    'statusline_bg':        ('#282837', 'Statusline',        'bg'),
    'error_bg':             ('#B41E1E', 'Error',             'bg'),
    'water_bg':             ('#041232', 'Water',             'bg'),
    'wood_wall_bg':         ('#5A3412', 'Wood wall',         'bg'),
    'wood_wall_damaged_bg': ('#371C06', 'Wood wall damaged', 'bg'),
    'sel_bg':               ('#28230F', 'Cursor line',       'bg'),
    'player_fg':            ('bright-white', 'Player',         'fg'),
    'enemy_fg':             ('#3CB43C',      'Enemy',          'fg'),
    'enemy_frozen':         ('#64B4FF',      'Enemy (frozen)', 'fg'),
    'boss_fg':              ('#C81E1E',      'Boss',           'fg'),
    'heart_full':           ('#DC2828', '♥ full',  'fg'),
    'heart_half':           ('#DCA01E', '♥ half',  'fg'),
    'heart_empty':          ('#3C3C3C', '♥ empty', 'fg'),
    'dynamite_fg':          ('#FF5000', 'Dynamite',       'fg'),
    'expl_near':            ('bold-wh', 'Explosion near', 'fg'),
    'expl_mid':             ('#FFA01E', 'Explosion mid',  'fg'),
    'expl_far':             ('#C8460A', 'Explosion far',  'fg'),
    'exit_fg':              ('bright-grn', 'Exit',          'fg'),
    'door_fg':              ('#505050',    'Door (open)',   'fg'),
    'locked_door_fg':       ('#A0821E',    'Door (locked)', 'fg'),
    'chest_fg':             ('#DCB428', 'Chest',      'fg'),
    'key_fg':               ('#DCB428', 'Key',        'fg'),
    'key_gold_fg':          ('#FFC314', 'Key (gold)', 'fg'),
    'key_red_fg':           ('#D23737', 'Key (red)',  'fg'),
    'rune_ancient':         ('#5050A0', 'Rune ancient', 'fg'),
    'rune_verdant':         ('#3C823C', 'Rune verdant', 'fg'),
    'rune_void':            ('#6E3CA0', 'Rune void',    'fg'),
    'rune_ember':           ('#A05A28', 'Rune ember',   'fg'),
    'budget_ok':            ('#3CC83C', 'Budget ok',   'fg'),
    'budget_low':           ('#DCC828', 'Budget low',  'fg'),
    'budget_crit':          ('#DC2828', 'Budget crit', 'fg'),
    'mode_normal':          ('#3CC83C', '-- NORMAL --', 'fg'),
    'mode_insert':          ('#DCC828', '-- INSERT --', 'fg'),
    'mode_visual':          ('#B43CC8', '-- VISUAL --', 'fg'),
    'mode_command':         ('white',   ':command',     'fg'),
    'statusline_fg':        ('#B4B4C8', 'Statusline text',   'fg'),
    'error_fg':             ('bright-wh', 'Error text',      'fg'),
    'answer_consumed':      ('#4B4B4B', 'Answer consumed',   'fg'),
    'answer_warn':          ('#DC6400', 'Answer warning',    'fg'),
    'hint_fg':              ('#5A5A5A', 'Hint bar',          'fg'),
    'border_fg':            ('#505064', 'Box borders',       'fg'),
    'wood_wall_damaged_fg': ('#A0692D', 'Wood wall damaged', 'fg'),
    'sealed_wall_fg':       ('#4A5062', 'Sealed wall (gate)', 'fg'),
    'dir_fg':               ('#64A0E6', 'Directory',         'fg'),
    'entry_fg':             ('#DCD7C8', 'Entry marker',      'fg'),
    'horse_fg':             ('#B2966E', "Horse (wizard's)",  'fg'),
}

# ── Curated groups (function names only — no duplicated data) ─────────────────
_GROUPS: list[tuple[str, list[str]]] = [
    ('Backgrounds', [
        'wall_bg', 'floor_bg', 'visual_sel_bg', 'statusline_bg',
        'error_bg', 'water_bg', 'wood_wall_bg', 'wood_wall_damaged_bg',
        'wood_wall_damaged_fg', 'sealed_wall_fg', 'sel_bg',
    ]),
    ('Entities',   ['player_fg', 'enemy_fg', 'enemy_frozen', 'boss_fg']),
    ('Hearts',     ['heart_full', 'heart_half', 'heart_empty']),
    ('Combat',     ['dynamite_fg', 'expl_near', 'expl_mid', 'expl_far']),
    ('Navigation', ['exit_fg', 'door_fg', 'locked_door_fg']),
    ('Keys & Chests', ['chest_fg', 'key_fg', 'key_gold_fg', 'key_red_fg']),
    ('Companions', ['horse_fg']),
    ('Runes',      ['rune_ancient', 'rune_verdant', 'rune_void', 'rune_ember']),
    ('Budget',     ['budget_ok', 'budget_low', 'budget_crit']),
    ('Modes',      ['mode_normal', 'mode_insert', 'mode_visual', 'mode_command']),
    ('UI', [
        'statusline_fg', 'error_fg', 'answer_consumed', 'answer_warn',
        'hint_fg', 'border_fg', 'dir_fg', 'entry_fg',
    ]),
]


def _discover_color_fns() -> set[str]:
    """All zero-arg callable names in render.colors (skips private + water_fg)."""
    found = set()
    for name in dir(C):
        if name.startswith('_') or name in ('init', 't', 'water_fg', 'normal_fg'):
            continue
        obj = getattr(C, name)
        if not callable(obj):
            continue
        try:
            if not inspect.signature(obj).parameters:
                found.add(name)
        except (ValueError, TypeError):
            pass
    return found


def _resolved_groups() -> list[tuple[str, list[str]]]:
    """Merge curated groups with discovered functions; append 'Other' for new ones."""
    discovered = _discover_color_fns()
    known: set[str] = set()
    result: list[tuple[str, list[str]]] = []
    for group_name, names in _GROUPS:
        valid = [n for n in names if n in discovered]
        if valid:
            result.append((group_name, valid))
            known.update(valid)
    ungrouped = sorted(discovered - known)
    if ungrouped:
        result.append(('Other', ungrouped))
    return result


def _entry_meta(name: str) -> tuple[str, str, str]:
    """Return (hex_str, role, kind) for a color function name."""
    if name in _META:
        return _META[name]
    kind = 'bg' if name.endswith('_bg') else 'fg'
    return ('?', '', kind)


def palette_rows() -> list[dict]:
    """The navigable buffer for the colors screen — a flat list of row dicts the
    shared NetrwNav engine drives (mirrors the scroll library's `library_rows`).
    Row types: 'parent' (../), 'section' (a colour group header), 'entry' (one
    colour), 'blank'. Each carries a 'group' key for `{`/`}` and a 'plain' label
    for `/`-search and word motions."""
    rows: list[dict] = [{'type': 'parent', 'group': 'nav', 'plain': '../'},
                        {'type': 'blank',  'group': 'nav', 'plain': ''}]
    for gi, (group_name, names) in enumerate(_resolved_groups()):
        rows.append({'type': 'section', 'group': gi, 'title': group_name,
                     'plain': group_name})
        for name in names:
            _hex, role, _kind = _entry_meta(name)
            rows.append({'type': 'entry', 'group': gi, 'name': name,
                         'plain': f'{name} {role}'.strip()})
        rows.append({'type': 'blank', 'group': gi, 'plain': ''})
    return rows


def row_label(r: dict) -> str:
    """Motion/search text of a palette row (mirrors what's drawn)."""
    return r.get('plain', '')


def row_section_key(r: dict) -> str:
    """Grouping for `{`/`}` — the ../ nav rows, then one section per colour group."""
    return r['group']


def _row_colored(r: dict, iw: int, is_cursor: bool) -> str:
    """One palette row as a colour-coded, iw-wide string; the cursor row is laid
    on the cursor-line background (swatches keep their own colour)."""
    floor = C.floor_bg()
    dfc   = C.dir_fg()
    rst   = C.normal_fg()
    bg    = C.sel_bg() if is_cursor else ''
    restore = rst + bg                       # after a swatch: clear, reapply row bg

    t = r['type']
    if t == 'parent':
        return bg + dfc + '../' + restore + ' ' * max(0, iw - 3) + rst
    if t == 'blank':
        return bg + ' ' * iw + rst
    if t == 'section':
        plain = f'" {r["title"]}'
        return bg + dfc + plain + restore + ' ' * max(0, iw - len(plain)) + rst

    name = r['name']
    fn   = getattr(C, name)
    hex_str, role, kind = _entry_meta(name)
    if kind == 'bg':
        swatch = fn() + ' ' * _SW + restore
    else:
        swatch = floor + fn() + _SWATCH + restore
    visible = 2 + _SW + 2 + _NW + 2 + _HW + 2 + len(role)
    pad     = max(0, iw - visible)
    return (bg + '  ' + swatch +
            '  ' + restore + f'{name:<{_NW}}' +
            '  ' + dfc + f'{hex_str:<{_HW}}' + restore +
            '  ' + C.hint_fg() + role + restore +
            ' ' * pad + rst)


def _viewport_top(cursor: int, top: int, avail: int, n: int) -> int:
    """Vim-like viewport top: keep `top` unless the cursor has left the window."""
    max_off = max(0, n - avail)
    if cursor < top:
        top = cursor
    elif cursor >= top + avail:
        top = cursor - avail + 1
    return max(0, min(top, max_off))


def render_color_palette(
    term: Terminal,
    player: Player,
    cursor: int = 0,
    scroll_offset: int = 0,
    cmd_line: str | None = None,
    cmd_prefix: str = ':',
) -> int:
    iw  = _iw(term)
    bfg = C.border_fg()
    rst = C.normal_fg()
    out = []

    def border_h(left, right, fill=S.BOX_H):
        return bfg + left + fill * iw + right + rst

    def _box_row(content: str) -> str:
        return bfg + S.BOX_V + rst + content + bfg + S.BOX_V + rst

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
               rst + 'Vimny  ' + name_tag + rst +
               '  ' + hearts_col + '  ' +
               ' ' * mid_gap +
               C.mode_normal() + sl_label + rst +
               ' ' * right_pad +
               bfg + S.BOX_V + rst)

    # ── Separator ─────────────────────────────────────────────────────────────
    out.append(border_h(S.BOX_LT, S.BOX_RT))

    game_h = term.height - 5

    # ── Netrw header ──────────────────────────────────────────────────────────
    dfc    = C.dir_fg()
    kc     = C.mode_insert()
    ver    = '(netrw v13ny)'
    ndl    = '" Netrw Directory Listing'
    ndl_sp = max(0, iw - len(ndl) - len(ver))
    sb_lbl = '"   Sorted by      '
    sb_val = 'category'
    qh_pfx = '"   Quick Help: '
    qh_prs = [('j/k', 'scroll'), ('Esc', 'back')]
    qh_pl  = qh_pfx + '  '.join(f'{k}:{d}' for k, d in qh_prs)
    qh_col = (dfc + qh_pfx +
               ('  ' + dfc).join(kc + k + dfc + ':' + d for k, d in qh_prs))

    def _div() -> str:
        plain = '" ' + '=' * (iw - 2)
        return _box_row(dfc + plain + rst + ' ' * max(0, iw - len(plain)))

    def _hdr(plain, colored=None) -> str:
        pad = max(0, iw - len(plain))
        return _box_row((dfc + plain if colored is None else colored) + rst + ' ' * pad)

    hdr_rows = [
        _div(),
        _hdr(ndl + ' ' * ndl_sp + ver),
        _hdr('"   ~/.vimny/colors/'),
        _hdr(sb_lbl + sb_val, dfc + sb_lbl + rst + sb_val),
        _hdr(qh_pl, qh_col),
        _div(),
    ]
    out.extend(hdr_rows)

    # ── Navigable content (../ + colour groups), scrolled as a viewport ────────
    rows      = palette_rows()
    reserved  = len(hdr_rows)
    visible_h = max(1, game_h - reserved)
    scroll_offset = _viewport_top(cursor, scroll_offset, visible_h, len(rows))
    window    = list(enumerate(rows))[scroll_offset:scroll_offset + visible_h]

    for idx, r in window:
        out.append(_box_row(_row_colored(r, iw, idx == cursor)))
    for _ in range(visible_h - len(window)):
        out.append(_box_row(' ' * iw))

    # ── Statusline ────────────────────────────────────────────────────────────
    sl_w   = iw
    sl_lbl = '-- COLORS --'

    if cmd_line is not None:
        cmd_text = cmd_prefix + cmd_line
        sl_pad   = max(0, sl_w - len(cmd_text))
        out.append(bfg + S.BOX_V + rst +
                   C.mode_command() + cmd_text + rst + ' ' * sl_pad +
                   bfg + S.BOX_V + rst)
    else:
        total    = len(rows)
        sl_right = f'{cursor + 1}/{total} '
        sl_mid   = max(0, sl_w - len(sl_lbl) - 2 - len(sl_right))
        out.append(bfg + S.BOX_V + rst +
                   C.mode_normal() + ' ' + sl_lbl + ' ' +
                   rst + ' ' * sl_mid + sl_right +
                   bfg + S.BOX_V + rst)

    # ── Bottom border ─────────────────────────────────────────────────────────
    out.append(border_h(S.BOX_BL, S.BOX_BR))

    print(term.home + term.clear + '\n'.join(out), end='', flush=True)
    return scroll_offset
