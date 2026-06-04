"""Title and save-select screen renderers (read-only; never mutate game state)."""
from __future__ import annotations
import json
import random as _random
from pathlib import Path
from blessed import Terminal
import render.colors as C
import render.symbols as S
from content.levels import LEVELS
from render.utils import inner_w as _iw

FRAME_W      = 80
NAME_MAX     = 20   # max adventurer name length
_BOX_INNER_W = 48   # inner width of the wizard's quote box

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

# ── Wizard wisdom quotes ────────────────────────────────────────────────────────

_WISDOM_PATH = Path(__file__).parent.parent / 'art' / 'wizard_wisdom.txt'


def _load_wisdom() -> list[dict]:
    try:
        text  = _WISDOM_PATH.read_text()
        start = text.index('{')
        end   = text.rindex('}') + 1
        return json.loads(text[start:end])['levels']
    except (OSError, ValueError, KeyError):
        return []


_QUOTES: list[dict] = _load_wisdom()


def _fmt_quote(chosen: dict) -> tuple[str, str, str, str]:
    """Format a wisdom entry into a 4-tuple of _BOX_INNER_W-padded strings."""
    pad   = ' ' * _BOX_INNER_W
    lines = [l.ljust(_BOX_INNER_W)[:_BOX_INNER_W] for l in chosen['quote']]
    if len(lines) >= 4:
        return (lines[0], lines[1], lines[2], lines[3])
    elif len(lines) == 3:
        return (lines[0], lines[1], lines[2], pad)
    elif len(lines) == 2:
        return (pad, lines[0], lines[1], pad)
    else:
        return (pad, lines[0], pad, pad)


def _generic_pool() -> list[dict]:
    """Poems with no specific level (title flavour + blessing fallback)."""
    return [q for q in _QUOTES if q.get('introduces_slug') is None]


def select_quote(unlocked_slugs: set[str]) -> tuple[str, str, str, str]:
    """Return 4 box-inner strings for the title-screen quote box.

    Picks from the generic pool plus any lesson poem whose introduced level
    the player has already unlocked, so the wisdom never spoils a level the
    player has not yet reached.
    """
    pool = _generic_pool() + [
        q for q in _QUOTES if q.get('introduces_slug') in unlocked_slugs
    ]
    pool = pool or _QUOTES
    if not pool:
        blank = ' ' * _BOX_INNER_W
        return (blank, blank, blank, blank)
    return _fmt_quote(_random.choice(pool))


def select_quote_by_name(name: str) -> tuple[str, str, str, str]:
    """Return the formatted quote for the corpus entry with the given name field."""
    for q in _QUOTES:
        if q['name'] == name:
            return _fmt_quote(q)
    blank = ' ' * _BOX_INNER_W
    return (blank, blank, blank, blank)


def select_next_lesson_quote(completed_slug: str) -> tuple[str, str, str, str]:
    """Return the wisdom quote that introduces the level after completed_slug.

    Finds the next visible level in curriculum order and fires the poem tagged
    with that level's slug (introduces_slug). Falls back to the generic pool when
    no dedicated poem exists (e.g. after the final level). Keying by slug — not by
    ordinal position — keeps the corpus aligned across reorders and renumbers.
    """
    visible_slugs = [l['slug'] for l in LEVELS if not l.get('admin_only')]
    try:
        nxt = visible_slugs.index(completed_slug) + 1
        next_slug = visible_slugs[nxt] if nxt < len(visible_slugs) else None
    except ValueError:
        next_slug = None

    pool = [q for q in _QUOTES if q.get('introduces_slug') == next_slug] if next_slug is not None else []
    if not pool:
        pool = _generic_pool()
    if not pool:
        blank = ' ' * _BOX_INNER_W
        return (blank, blank, blank, blank)
    return _fmt_quote(_random.choice(pool))


_WIZARD_ART: tuple[str, ...] = (
    '                                                                         k',
    '                                                                        h',
    '                                                                      j  l',
    '                                                                    j     l',
    ' ╔════════════════════════════════════════════════╗            ::jj         l',
    ' ║ vim, vum!                                      ║        :wq               gg',
    ' ║         h left, l right, j down, k up.         ║         :q     ^ ^      G',
    ' ║ Arrow keys are a long road. Stay by the hearth.║          :w   0  0  $  e',
    ' ║Each key a step. Conserve them like lantern oil.║               {        b',
    ' ║    The cursor is your wand. Keep it steady.    ║              {  }     w',
    ' ╚════════════════════════════════════════════════╝   a          y        yp',
    '                                                       i       yy         p p',
    '                                                        i      u        CTRL-R',
    '                                                         i    u    u   C  -  V',
    '                                                          i   A     :e i      i',
    '                                                           I  o o    :e O    o o',
    '                                                            :e :e      :e   :set',
    '                                                             :set relativenumber',
    '                                                             :set number / ? nn',
    '                                                              n n        /     N',
    '                                                             / /    ?   m{a-z)',
    '                                                             f  f    F   F  tTt',
    '                                                             (       %       )',
    '                                                             :s/dungeon/FUN!/g',
    '                                                            :%s/            /g',
    '                                                             q               @',
)
_EYE_IDX   = 7       # 0-based index of the eye line in _WIZARD_ART
_EYE_OPEN  = '0  0'
_EYE_BLINK = '^  ^'

MENU_ITEMS: list[tuple[str, str]] = [
    (':e saves/',          'load'),
    (':enew',             'new'),
    ('quit',              'quit'),
]

_BOX_INNER = NAME_MAX + 2


# ── Shared helpers ─────────────────────────────────────────────────────────────

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
    game_h = term.height - 7
    blank  = _blank(term, iw)
    while len(content) < game_h:
        content.append(blank)
    out.extend(content[:game_h])

    # Vim statusline / command line
    sl_w  = iw
    if cmd_line is not None:
        cmd_text = ':' + cmd_line
        sl_pad   = max(0, sl_w - len(cmd_text))
        out.append(bfg + S.BOX_V + rst +
                   C.mode_command() + cmd_text +
                   rst + ' ' * sl_pad +
                   bfg + S.BOX_V + rst)
    else:
        sl_label = '-- VIMNY --'
        sl_mid   = max(0, sl_w - len(sl_label) - 2)
        out.append(bfg + S.BOX_V + rst +
                   stamp + ' ' + sl_label + rst + ' ' * sl_mid +
                   bfg + S.BOX_V + rst)

    # Bottom separator
    out.append(border_h(S.BOX_LT, S.BOX_RT))

    # Hint bar: always show navigation hints
    if hint_text is not None:
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
                 confirm_name: str | None = None,
                 blink: bool = False,
                 quote_lines: tuple[str, str, str, str] | None = None) -> None:
    """Main title screen.

    cmd_line     — when set, show ':' + cmd_line in the hint bar.
    name_prompt  — when set, replace wizard+menu with the name-input UI.
    confirm_name — when set, replace name-input with overwrite confirmation.
    quote_lines  — 4 box-inner strings (48 chars each) for the wizard's quote.
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
        # Wizard + menu
        box_col  = term.color_rgb(200, 140, 30)    # amber box + wizard face
        wiz_col = term.color_rgb(75,  156, 211)    # cyan robe (lines 11-25)
        eye_col = term.color_rgb(75, 156, 211)     # carolina blue (eyes)

        _BOX_CLOSE_CHARS = frozenset('╗║╝')
        _AMBER_CHARS     = frozenset('^${}')
        _BLUE_CHARS      = frozenset('0')
        bfg         = C.border_fg()
        box_ref_len = len(_WIZARD_ART[4])
        box_pad_l   = max(0, (iw - box_ref_len) // 2)

        for idx, line in enumerate(_WIZARD_ART):
            # Split at the right-side closing border char so left stays amber
            # and right side is coloured per-character
            matches = [i for i, c in enumerate(line) if c in _BOX_CLOSE_CHARS]
            split_idx = max(matches) if matches else -1
            left  = line[:split_idx + 1] if split_idx >= 0 else ''
            right = line[split_idx + 1:] if split_idx >= 0 else line
            left  = line[:split_idx + 1]
            right = line[split_idx + 1:]
            # Substitute dynamic quote text into box content lines 6-9
            if quote_lines is not None and 6 <= idx <= 9:
                ql   = quote_lines[idx - 6]
                left = ' ║' + ql + '║'
            if idx == _EYE_IDX and blink:
                right = right.replace(_EYE_OPEN, _EYE_BLINK)
            colored_right = ''.join((eye_col if ch in _BLUE_CHARS else
                box_col if ch in _AMBER_CHARS else
                wiz_col) + ch
                for ch in right
            )
            pad_r = max(0, iw - box_pad_l - len(line))
            content.append(
                bfg + S.BOX_V + rst +
                ' ' * box_pad_l + box_col + left + colored_right + rst +
                ' ' * pad_r +
                bfg + S.BOX_V + rst
            )

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

        hint = 'j/k:move cursor · enter:select · :q quit'

    _render_frame(term, iw, content, cmd_line, hint_text=hint)


# ── Save-select screen ─────────────────────────────────────────────────────────

def render_save_select(term: Terminal, saves: list[dict], cursor: int,
                       deleting: bool = False) -> None:
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

    if deleting:
        hint = term.color_rgb(220, 80, 80) + 'd again to delete · any other key cancels' + term.normal
    else:
        hint = 'j/k:move cursor · enter:select · dd:delete · Esc:go back'
    _render_frame(term, iw, content, hint_text=hint)
