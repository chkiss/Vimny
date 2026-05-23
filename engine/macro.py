"""Block F — macro recording/playback helpers.

Recorded macros are plain strings of single chars (printable keys plus a few
control chars for Esc/Enter/Backspace). On playback each char is turned back
into a minimal key object that mimics blessed's Keystroke interface
(str value + .name + .is_sequence), so it flows through the same input loop.
"""
from __future__ import annotations

# normalised control chars used in recorded macro strings
ESC, ENTER, BACKSPACE = '\x1b', '\r', '\x7f'
_NAME_OF = {ESC: 'KEY_ESCAPE', ENTER: 'KEY_ENTER', BACKSPACE: 'KEY_BACKSPACE'}


class SynthKey(str):
    """A str subclass standing in for a blessed Keystroke during macro replay."""
    name: str
    is_sequence: bool

    def __new__(cls, value: str, name: str = '', is_sequence: bool = False):
        obj = super().__new__(cls, value)
        obj.name = name
        obj.is_sequence = is_sequence
        return obj


def synth_key(ch: str) -> SynthKey:
    """Reconstruct a key object from a recorded macro char."""
    return SynthKey(ch, name=_NAME_OF.get(ch, ''), is_sequence=False)


def record_char(key) -> str | None:
    """Normalise a pressed key to the single char to store in a macro, or None
    to skip it (unhandled multi-byte sequences such as arrow keys)."""
    name = getattr(key, 'name', '') or ''
    if name == 'KEY_ESCAPE':
        return ESC
    if name == 'KEY_ENTER':
        return ENTER
    if name == 'KEY_BACKSPACE':
        return BACKSPACE
    if getattr(key, 'is_sequence', False):
        return None
    s = str(key)
    return s if len(s) == 1 else None
