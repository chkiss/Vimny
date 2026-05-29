"""Wizard blessing animation — shown after first dungeon completion with save."""
from __future__ import annotations
import time
from pathlib import Path
from blessed import Terminal
import render.colors as C
import render.symbols as S
from render.utils import inner_w as _iw
from render.title import _BOX_INNER_W as _BOX_INNER

_ART_PATH  = Path(__file__).parent.parent / 'art' / 'wizard.txt'

_AMBER_CHARS = frozenset('^${}')
_EYE_LINE    = 7       # 0-based index of the "0  0" eye line within each frame
_EYE_OPEN    = '0  0'
_EYE_BLINK   = '^  ^'


def _parse_frames() -> dict[str, list[str]]:
    """Parse named art frames from wizard.txt into a name→lines dict."""
    try:
        text = _ART_PATH.read_text()
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


def _colour_line(term: Terminal, line: str) -> str:
    """Colour one wizard art line: amber for ^${}; cyan for everything else."""
    amber = term.color_rgb(200, 140, 30)
    cyan  = term.color_rgb(75, 156, 211)
    rst   = term.normal
    parts: list[str] = []
    for ch in line:
        if ch == ' ':
            parts.append(rst + ch)
        elif ch in _AMBER_CHARS:
            parts.append(amber + ch)
        else:
            parts.append(cyan + ch)
    return (''.join(parts) + rst) if parts else ''


def _draw(
    term: Terminal,
    art: list[str],
    quote_lines: tuple[str, str, str, str] | None,
    hint: str,
) -> None:
    """Render one blessing frame using the standard title-screen chrome."""
    from render.title import _render_frame, _blank, _centred  # noqa: PLC0415

    iw     = _iw(term)
    rst    = term.normal
    bfg    = C.border_fg()
    amber  = term.color_rgb(200, 140, 30)
    game_h = term.height - 7

    art_w = max((len(l) for l in art), default=0)
    pad_l = max(0, (iw - art_w) // 2)

    content: list[str] = []

    if quote_lines is not None:
        # Poem box: top border + 4 poem lines + bottom border, then blank separator
        top = '╔' + '═' * _BOX_INNER + '╗'
        bot = '╚' + '═' * _BOX_INNER + '╝'
        content.append(_centred(term, iw, top, amber + top + rst))
        for ql in quote_lines:
            plain   = '║' + ql + '║'
            colored = amber + '║' + rst + ql + amber + '║' + rst
            content.append(_centred(term, iw, plain, colored))
        content.append(_centred(term, iw, bot, amber + bot + rst))
        content.append(_blank(term, iw))
    else:
        # Vertically centre the wizard art in the game area
        top_pad = max(0, (game_h - len(art)) // 2)
        for _ in range(top_pad):
            content.append(_blank(term, iw))

    for line in art:
        pad_r   = max(0, iw - pad_l - len(line))
        colored = _colour_line(term, line)
        content.append(
            bfg + S.BOX_V + rst +
            ' ' * pad_l + colored +
            ' ' * pad_r +
            bfg + S.BOX_V + rst
        )

    _render_frame(term, iw, content, hint_text=hint)


def _blink(art: list[str]) -> list[str]:
    """Return a copy of art with the eye line set to the blink expression."""
    result = list(art)
    if _EYE_LINE < len(result):
        result[_EYE_LINE] = result[_EYE_LINE].replace(_EYE_OPEN, _EYE_BLINK)
    return result


def run_wizard_blessing(
    term: Terminal,
    quote_lines: tuple[str, str, str, str],
) -> None:
    """Animate the wizard blessing and wait for a keypress to dismiss.

    The arm unfolds bottom-up across four cascade frames, with a brief
    eye-blink mid-animation, before the poem box is revealed.

    Cascade logic: each frame is art0[:cutoff] + art_end[cutoff:].
    Only lines 10-15 differ between the two source frames, so the cascade
    progressively replaces arm lines from the bottom (line 15 = wrist)
    upward to line 11 (shoulder), then the final frame shows art_end in full.
    """
    art0    = _FRAMES.get('blessing-0', [])
    art_end = _FRAMES.get('blessing-end', [])

    # ── Cascade frames ────────────────────────────────────────────────────────
    # (cutoff, delay_s, blink)
    # cutoff: blend point — art0[:n] + art_end[n:]
    # blink:  if True, show a brief eye-close before the main delay
    _STEPS: list[tuple[int, float, bool]] = [
        (len(art0), 0.40, False),   # establishing shot   — full blessing-0
        (15,        0.22, False),   # wrist extends       — line 15 from art_end
        (13,        0.12, True),    # forearm extends     — lines 13-15; blink here
        (11,        0.22, False),   # upper arm extends   — lines 11-15
    ]

    for cutoff, delay, do_blink in _STEPS:
        frame = art0[:cutoff] + art_end[cutoff:]
        if do_blink:
            _draw(term, _blink(frame), None, hint='')
            time.sleep(0.12)
        _draw(term, frame, None, hint='')
        time.sleep(delay)

    # ── Final frame: full blessing-end pose + revealed poem ───────────────────
    _draw(term, art_end, quote_lines, hint='  ─── press any key ───  ')
    term.inkey()
