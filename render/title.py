"""Title and save-select screen renderers (read-only; never mutate game state)."""
from __future__ import annotations
from blessed import Terminal
import render.colors as C
import render.symbols as S
from content.levels import LEVELS

FRAME_W  = 80
NAME_MAX = 20   # max adventurer name length

_LOGO = [
    '██╗   ██╗  ██╗  ███╗   ███╗  ███╗   ██╗  ██╗   ██╗',
    '██║   ██║  ██║  ████╗ ████║  ████╗  ██║  ╚██╗ ██╔╝',
    '██║   ██║  ██║  ██╔████╔██║  ██╔██╗ ██║   ╚████╔╝ ',
    '╚██╗ ██╔╝  ██║  ██║╚██╔╝██║  ██║╚██╗██║    ╚██╔╝  ',
    ' ╚████╔╝   ██║  ██║ ╚═╝ ██║  ██║ ╚████║     ██║   ',
    '  ╚═══╝    ╚═╝  ╚═╝     ╚═╝  ╚═╝  ╚═══╝     ╚═╝   ',
]
_LOGO_W = len(_LOGO[0])

_LOGO_COLORS = [
    lambda t: t.color_rgb(255, 215, 40) + t.bold,
    lambda t: t.color_rgb(255, 215, 40) + t.bold,
    lambda t: t.color_rgb(255, 215, 40) + t.bold,
    lambda t: t.color_rgb(255, 175, 30),
    lambda t: t.color_rgb(220, 110, 20),
    lambda t: t.color_rgb(100, 75, 35),
]

_WIZARD_PLAIN = [
    '     ▲    ',
    '    /█\\   ',
    '   ( ⊙⊙)  ',
    '    ╲█╱   ',
]

MENU_ITEMS: list[tuple[str, str]] = [
    ('begin new journey', 'new'),
    ('load saved game',   'load'),
    ('quit',              'quit'),
]

_BOX_INNER = NAME_MAX + 2


# ── Shared helpers ─────────────────────────────────────────────────────────────

def _iw(term: Terminal) -> int:
    return min(max(term.width, FRAME_W), 120) - 2


def _blank(term: Terminal, iw: int) -> str:
    bfg = C.border_fg()
    return bfg + S.BOX_V + term.normal + ' ' * iw + bfg + S.BOX_V + term.normal


def _centred(term: Terminal, iw: int, plain: str, colored: str = '') -> str:
    bfg = C.border_fg()
    if not colored:
        colored = plain
    pad_l = max(0, (iw - len(plain)) // 2)
    pad_r = max(0, iw - pad_l - len(plain))
    return bfg + S.BOX_V + term.normal + ' ' * pad_l + colored + ' ' * pad_r + bfg + S.BOX_V + term.normal


def _logo_content(term: Terminal, iw: int) -> list[str]:
    bfg = C.border_fg()
    rst = term.normal
    rows = []
    for i, line in enumerate(_LOGO):
        pad_l = max(0, (iw - _LOGO_W) // 2)
        pad_r = max(0, iw - pad_l - len(line))
        color = _LOGO_COLORS[i](term)
        rows.append(bfg + S.BOX_V + rst + ' ' * pad_l + color + line + rst + ' ' * pad_r + bfg + S.BOX_V + rst)
    return rows


def _render_frame(term: Terminal, iw: int, content: list[str],
                  cmd_line: str | None = None,
                  hint_text: str | None = None) -> None:
    """Wrap content in the standard title-screen chrome and print."""
    bfg   = C.border_fg()
    rst   = term.normal
    stamp = term.color_rgb(55, 55, 55)
    muted = term.color_rgb(145, 145, 145)
    out: list[str] = []

    def border_h(left: str, right: str) -> str:
        return bfg + left + S.BOX_H * iw + right + rst

    # Top border
    out.append(border_h(S.BOX_TL, S.BOX_TR))

    # Status bar: version stamp right-aligned
    ver = 'version 1.0 · 2026'
    out.append(bfg + S.BOX_V + rst +
               ' ' * max(0, iw - len(ver)) +
               stamp + ver + rst +
               bfg + S.BOX_V + rst)

    # Top separator
    out.append(border_h(S.BOX_LT, S.BOX_RT))

    # Game area: pad/crop content to exactly game_h rows
    game_h = term.height - 6
    blank  = _blank(term, iw)
    while len(content) < game_h:
        content.append(blank)
    out.extend(content[:game_h])

    # Bottom separator
    out.append(border_h(S.BOX_LT, S.BOX_RT))

    # Hint bar: command line while typing, otherwise navigation hints
    if cmd_line is not None:
        cmd_text = ':' + cmd_line
        out.append(C.mode_command() + cmd_text +
                   ' ' * max(0, term.width - len(cmd_text)) + rst)
    elif hint_text is not None:
        out.append(bfg + S.BOX_V + rst +
                   muted + hint_text + rst +
                   ' ' * max(0, iw - len(hint_text)) +
                   bfg + S.BOX_V + rst)
    else:
        out.append(bfg + S.BOX_V + rst + ' ' * iw + bfg + S.BOX_V + rst)

    # Bottom border
    out.append(border_h(S.BOX_BL, S.BOX_BR))

    print(term.home + '\n'.join(out), end='', flush=True)


# ── Title screen ───────────────────────────────────────────────────────────────

def render_title(term: Terminal, cursor: int, has_save: bool,
                 cmd_line: str | None = None,
                 name_prompt: str | None = None,
                 confirm_name: str | None = None) -> None:
    """Main title screen.

    cmd_line     — when set, show ':' + cmd_line in the hint bar.
    name_prompt  — when set, replace wizard+menu with the name-input UI.
    confirm_name — when set, replace name-input with overwrite confirmation.
    """
    iw  = _iw(term)
    rst = term.normal
    dim = term.color_rgb(145, 145, 145)

    blank   = lambda: _blank(term, iw)
    centred = lambda p, c='': _centred(term, iw, p, c)

    # Fixed header: 1 blank + 6 logo + 1 blank + 1 subtitle = 9 rows
    content: list[str] = [blank()]
    content.extend(_logo_content(term, iw))
    content.append(blank())

    sub = 'a vim-teaching dungeon crawler'
    content.append(centred(sub, dim + sub + rst))

    # Variable section: 8 rows (hints live in the hint bar, not here)
    if confirm_name is not None:
        # Overwrite confirmation — 8 rows
        content.append(blank())
        content.append(blank())
        warn = f'Overwrite the current save at "{confirm_name}"?'
        content.append(centred(warn, dim + warn + rst))
        content.append(blank())
        prompt = 'y = yes · n = no'
        content.append(centred(prompt, term.bold + prompt + rst))
        content.append(blank())
        content.append(blank())
        content.append(blank())
        hint = 'y overwrite · n cancel'

    elif name_prompt is not None:
        # Name-input UI — 8 rows: 2 blank + 1 label + 1 blank + 3 box + 1 blank
        content.append(blank())
        content.append(blank())

        label = 'Name your adventurer:'
        content.append(centred(label, dim + label + rst))
        content.append(blank())

        box_w     = _BOX_INNER + 4
        box_top   = '┌' + '─' * (box_w - 2) + '┐'
        box_bot   = '└' + '─' * (box_w - 2) + '┘'
        inner_pad = max(0, _BOX_INNER - len(name_prompt) - 1)
        box_mid_p = '│ ' + name_prompt + '█' + ' ' * inner_pad + ' │'
        box_mid_c = (C.border_fg() + '│ ' + rst +
                     term.bold + name_prompt + rst +
                     C.mode_normal() + '█' + rst +
                     ' ' * inner_pad +
                     C.border_fg() + ' │' + rst)

        content.append(centred(box_top, C.border_fg() + box_top + rst))
        content.append(centred(box_mid_p, box_mid_c))
        content.append(centred(box_bot, C.border_fg() + box_bot + rst))
        content.append(blank())
        hint = 'Enter to begin · Esc to cancel'

    else:
        # Wizard + menu — 8 rows: 4 wizard + 1 blank + 3 menu
        cyan = term.color_rgb(55, 155, 175)
        eyes = term.color_rgb(135, 200, 55)

        wiz_colored = [
            cyan + _WIZARD_PLAIN[0] + rst,
            cyan + '    /█\\   ' + rst,
            cyan + '   ( ' + eyes + '⊙⊙' + rst + cyan + ')  ' + rst,
            cyan + _WIZARD_PLAIN[3] + rst,
        ]
        wiz_hint = '~ the dungeons await ~'

        for i, (wp, wc) in enumerate(zip(_WIZARD_PLAIN, wiz_colored)):
            if i == 2:
                gap = '     '
                content.append(centred(wp + gap + wiz_hint,
                                       wc + gap + dim + wiz_hint + rst))
            else:
                content.append(centred(wp, wc))

        content.append(blank())

        for idx, (label, action) in enumerate(MENU_ITEMS):
            is_cur = (idx == cursor)
            active = not (action == 'load' and not has_save)

            pfx_p = '▶  ' if is_cur else '   '
            pfx_c = (C.player_fg() + term.bold + '▶  ' + rst) if is_cur else '   '

            if not active:
                label_c = term.color_rgb(60, 60, 60) + label + rst
            elif is_cur:
                label_c = term.bold + label + rst
            else:
                label_c = term.color_rgb(150, 150, 150) + label + rst

            content.append(centred(pfx_p + label, pfx_c + label_c))

        hint = 'j/k navigate · enter select · :q quit'

    _render_frame(term, iw, content, cmd_line, hint_text=hint)


# ── Save-select screen ─────────────────────────────────────────────────────────

def render_save_select(term: Terminal, saves: list[dict], cursor: int) -> None:
    """Show all existing saves with completion % so the player can pick one."""
    iw  = _iw(term)
    rst = term.normal
    dim = term.color_rgb(145, 145, 145)

    blank   = lambda: _blank(term, iw)
    centred = lambda p, c='': _centred(term, iw, p, c)

    total_possible = 2 * len(LEVELS)
    BAR_W = 12

    content: list[str] = [blank()]
    content.extend(_logo_content(term, iw))
    content.append(blank())

    hdr = '─── Saved Adventurers ───'
    content.append(centred(hdr, term.color_rgb(120, 120, 120) + hdr + rst))
    content.append(blank())

    if not saves:
        msg = 'No saved games found.'
        content.append(centred(msg, dim + msg + rst))
    else:
        for idx, save_data in enumerate(saves):
            name     = save_data.get('player_name', 'Unknown')
            progress = save_data.get('progress', {})
            earned   = sum(v.get('stars', 0) for v in progress.values())
            pct      = min(100, int(earned / total_possible * 100)) if total_possible else 0
            filled   = round(pct / 100 * BAR_W)
            bar      = '█' * filled + '░' * (BAR_W - filled)
            pct_str  = f'{pct:3d}%'

            is_cur  = (idx == cursor)
            pfx_p   = '▶  ' if is_cur else '   '
            pfx_c   = (C.player_fg() + term.bold + '▶  ' + rst) if is_cur else '   '
            name_f  = name[:16].ljust(16)
            plain   = pfx_p + name_f + '  ' + bar + '  ' + pct_str

            if is_cur:
                name_c = term.bold + name_f + rst
                bar_c  = C.budget_ok() + bar + rst
                pct_c  = C.hint_fg() + pct_str + rst
            else:
                name_c = term.color_rgb(150, 150, 150) + name_f + rst
                bar_c  = term.color_rgb(70, 70, 70) + bar + rst
                pct_c  = dim + pct_str + rst

            content.append(centred(plain, pfx_c + name_c + '  ' + bar_c + '  ' + pct_c))

    _render_frame(term, iw, content,
                  hint_text='j/k navigate · enter select · Esc back')
