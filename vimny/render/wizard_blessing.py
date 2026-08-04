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

"""Wizard blessing animation — shown after first dungeon completion with save."""
from __future__ import annotations
import time
from pathlib import Path
from blessed import Terminal
import vimny.render.colors as C
import vimny.render.symbols as S
from vimny.render.utils import inner_w as _iw
from vimny.render.title import _BOX_INNER_W as _BOX_INNER

_ART_PATH  = Path(__file__).parent.parent / 'art' / 'wizard.txt'

_AMBER_CHARS = frozenset('^${}')
_EYE_LINE    = 7       # 0-based index of the "0  0" eye line within each frame
_EYE_OPEN    = '0  0'
_EYE_BLINK   = '^  ^'

# ── Wand sweep ────────────────────────────────────────────────────────────────
# The wand occupies cols 0-6 of rows 10-15. The line-slice cascade couldn't
# carry the "a" tip between rows, so the wand is animated as a rigid rod
# pivoting on the wrist (15, 6): explicit keyframes where every glyph moves
# together, the tip (farthest from the pivot) travelling the most so it leads
# the swing instead of lagging. Each keyframe is the 6-row wand region (rows
# 10-15, ≤7 cols) stamped onto a static background; the last equals the
# blessing-end wand exactly, so the hand-off to the held frame is seamless.
_WAND_ROW0 = 10
_TIP_REST  = (12, 0)   # the "a" tip in blessing-end (the fully-out wand)

_WAND_KEYFRAMES: list[list[str]] = [
    [   # upright (= blessing-0): tip at (10, 6)
        '      a', '      i', '      i', '      i', '      i', '      I',
    ],
    [   # easing left: tip at (10, 4)
        '    a  ', '    i  ', '     i ', '     i ', '      i', '      I',
    ],
    [   # ~45°: tip at (11, 2)
        '       ', '  a    ', '   i   ', '    i  ', '     i ', '      I',
    ],
    [   # lying down: tip at (12, 1)
        '       ', '       ', ' a     ', '  i    ', '   ii  ', '    iiI',
    ],
    [   # at rest (= blessing-end): tip at (12, 0)
        '       ', '       ', 'a      ', ' i     ', '  ii   ', '    iiI',
    ],
]

# Tip twinkle: a subtle shimmer cycling through white / periwinkle / blue /
# soft purple (the "magic still lingering" once the wand is fully out).
_TWINKLE_RGB = [
    (235, 240, 255),   # near-white
    (255, 255, 255),   # white
    (168, 178, 240),   # periwinkle
    (135, 160, 240),   # blue
    (190, 168, 242),   # lavender
    (158, 132, 222),   # soft purple
]


def _parse_frames() -> dict[str, list[str]]:
    """Parse named art frames from wizard.txt into a name→lines dict."""
    try:
        text = _ART_PATH.read_text(encoding='utf-8')
    except FileNotFoundError:
        return {}

    frames: dict[str, list[str]] = {}
    current: str | None = None
    buf: list[str] = []

    def _flush() -> None:
        while buf and not buf[0].strip():
            buf.pop(0)
        while buf and not buf[-1].strip():
            buf.pop()
        if current is not None:
            frames[current] = list(buf)

    for raw in text.splitlines():
        line = raw.rstrip()
        if line.startswith('# ') and line.endswith(':'):
            _flush()
            current = line[2:-1].lower()   # "Blessing-0:" → "blessing-0"
            buf.clear()
        elif current is not None:
            buf.append(line)

    _flush()
    return frames


_FRAMES: dict[str, list[str]] = _parse_frames()


def _colour_line(term: Terminal, line: str, accents: dict[int, str] | None = None) -> str:
    """Colour one wizard art line: amber for ^${}; cyan for everything else.

    `accents` maps a column index to an explicit colour escape (used to
    twinkle the wand tip); those cells override the amber/cyan defaults.
    """
    amber = term.color_rgb(200, 140, 30)
    cyan  = term.color_rgb(75, 156, 211)
    rst   = term.normal
    accents = accents or {}
    parts: list[str] = []
    for i, ch in enumerate(line):
        if i in accents:
            parts.append(accents[i] + ch)
        elif ch == ' ':
            parts.append(rst + ch)
        elif ch in _AMBER_CHARS:
            parts.append(amber + ch)
        else:
            parts.append(cyan + ch)
    return (''.join(parts) + rst) if parts else ''


# Side-by-side layout (mirrors the title screen): the poem box sits to the
# left of the wizard, its top border aligned with art row _BOX_ROW0 so the
# box straddles the wizard's face (eyes on art row 7), exactly as on the
# title screen. The wand (art rows 10-15) hangs just past the box's bottom.
_BOX_ROW0 = 4    # art-row index where the poem box's top border sits
_BOX_LEAD = 1    # spaces before the box (matches the title's ' ╔')
_BOX_GAP  = 3    # spaces between the box and the wizard


def _draw(
    term: Terminal,
    art: list[str],
    quote_lines: tuple[str, str, str, str] | None,
    hint: str,
    accents: dict[int, dict[int, str]] | None = None,
) -> None:
    """Render one blessing frame using the standard title-screen chrome.

    The poem box is composed to the LEFT of the wizard (side-by-side, like
    the title screen). When `quote_lines` is None no box is drawn at all
    (its column width is still reserved), so the wizard never shifts and the
    whole box — borders and text — simply appears in place once the swing
    completes.

    `accents` maps an art-row index to a {col: colour} dict for per-cell
    overrides (the twinkling wand tip); columns are art-local.
    """
    from vimny.render.title import _render_frame  # noqa: PLC0415

    iw     = _iw(term)
    rst    = term.normal
    bfg    = C.border_fg()
    amber  = term.color_rgb(200, 140, 30)
    game_h = term.height - 7
    accents = accents or {}

    # ── Poem box rows (left column) — reserved-but-blank until inscribed ──────
    box_w = _BOX_INNER + 2
    box_plain: list[str] = []
    box_color: list[str] = []
    if quote_lines is not None:
        top = '╔' + '═' * _BOX_INNER + '╗'
        bot = '╚' + '═' * _BOX_INNER + '╝'
        box_plain = [top, *('║' + ql + '║' for ql in quote_lines), bot]
        box_color = [
            amber + top + rst,
            *(amber + '║' + rst + ql + amber + '║' + rst for ql in quote_lines),
            amber + bot + rst,
        ]

    def _box_at(idx: int) -> tuple[str, str]:
        """(plain, coloured) box segment for art row idx — spaces off-box."""
        li = idx - _BOX_ROW0
        if 0 <= li < len(box_plain):
            return box_plain[li], box_color[li]
        return ' ' * box_w, ' ' * box_w

    # ── Compose box | wizard, row by row ──────────────────────────────────────
    lead = ' ' * _BOX_LEAD
    gap  = ' ' * _BOX_GAP
    rows_plain: list[str] = []
    rows_color: list[str] = []
    for idx, line in enumerate(art):
        bp, bc = _box_at(idx)
        rows_plain.append(lead + bp + gap + line)
        rows_color.append(lead + bc + gap + _colour_line(term, line, accents.get(idx)))

    block_w = max((len(p) for p in rows_plain), default=0)
    pad_l   = max(0, (iw - block_w) // 2)
    top_pad = max(0, (game_h - len(art)) // 2)

    content: list[str] = [_blank_row(term, iw) for _ in range(top_pad)]
    for plain, color in zip(rows_plain, rows_color):
        pad_r = max(0, iw - pad_l - len(plain))
        content.append(
            bfg + S.BOX_V + rst +
            ' ' * pad_l + color + ' ' * pad_r +
            bfg + S.BOX_V + rst
        )

    _render_frame(term, iw, content, hint_text=hint)


def _blank_row(term: Terminal, iw: int) -> str:
    from vimny.render.title import _blank  # noqa: PLC0415
    return _blank(term, iw)


def _blink(art: list[str]) -> list[str]:
    """Return a copy of art with the eye line set to the blink expression."""
    result = list(art)
    if _EYE_LINE < len(result):
        result[_EYE_LINE] = result[_EYE_LINE].replace(_EYE_OPEN, _EYE_BLINK)
    return result


def _set_cell(lines: list[str], row: int, col: int, ch: str) -> None:
    """Overwrite a single cell in `lines`, right-padding the row if short."""
    if not (0 <= row < len(lines)):
        return
    line = lines[row]
    if col >= len(line):
        line = line + ' ' * (col - len(line))
    lines[row] = line[:col] + ch + line[col + 1:]


def _wand_background(art_end: list[str]) -> list[str]:
    """Copy of blessing-end with the wand region (cols 0-6, rows 10-15) blanked,
    so a keyframe wand can be stamped on top without doubling glyphs."""
    bg = list(art_end)
    for r in range(_WAND_ROW0, _WAND_ROW0 + len(_WAND_KEYFRAMES[0])):
        if r < len(bg):
            bg[r] = ' ' * 7 + bg[r][7:]
    return bg


def _stamp_wand(frame: list[str], region: list[str]) -> None:
    """Stamp a wand keyframe (rows 10-15, cols 0-6) onto frame in place."""
    for dr, line in enumerate(region):
        for c, ch in enumerate(line):
            if ch != ' ':
                _set_cell(frame, _WAND_ROW0 + dr, c, ch)


def run_wizard_blessing(
    term: Terminal,
    quote_lines: tuple[str, str, str, str],
) -> None:
    """Animate the wizard blessing, then hold for a keypress to dismiss.

    The wand swings as one rigid rod from upright to its laid-down rest,
    every glyph (tip included) moving together each frame so nothing lags.
    Only once the swing completes does the poem box appear (whole — borders
    and text) to the wizard's left, side-by-side like the title screen; its
    column is reserved throughout, so the wizard never shifts. The tip then
    twinkles through _TWINKLE_RGB and the wizard blinks 0.5 s every 5 s
    (matching the title screen). No blink fires during the swing itself.
    """
    art_end = _FRAMES.get('blessing-end', [])
    bg      = _wand_background(art_end)

    # ── Wand swing — rigid rod, all glyphs move together ──────────────────────
    # (keyframe, delay_s); the last keyframe stamped on bg reproduces art_end.
    delays = (0.35, 0.12, 0.12, 0.12, 0.15)
    for region, delay in zip(_WAND_KEYFRAMES, delays):
        frame = list(bg)
        _stamp_wand(frame, region)
        _draw(term, frame, None, hint='')   # no box during the swing
        time.sleep(delay)

    # ── Held frame: full blessing-end pose + revealed poem ────────────────────
    tip_r, tip_c = _TIP_REST
    hint = '  ─── press any key ───  '
    i = 0
    while True:
        blink   = (time.time() % 5) < 0.5
        art     = _blink(art_end) if blink else art_end
        r, g, b = _TWINKLE_RGB[i % len(_TWINKLE_RGB)]
        accents = {tip_r: {tip_c: term.color_rgb(r, g, b)}}
        _draw(term, art, quote_lines, hint=hint, accents=accents)
        if term.inkey(timeout=0.45):
            break
        i += 1
