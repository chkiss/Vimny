"""Guard: sequence keys must not contaminate cmd_line in any command mode.

Terminal escape sequences embedded in cmd_line reach print() calls and are
interpreted by the terminal as cursor-movement commands, causing visible
display corruption (hint bar jumping, screen tearing).  Every cmd_line
append must go through _cmd_append, which silently drops sequence keys.
"""
import pytest
from unittest.mock import MagicMock
from main import _cmd_append


# ── helpers ───────────────────────────────────────────────────────────────────

def _key(is_seq: bool, raw: str) -> MagicMock:
    k = MagicMock()
    k.is_sequence = is_seq
    k.__str__ = lambda self: raw
    return k


# ── sequence keys must be dropped ────────────────────────────────────────────

_SEQUENCE_KEYS = [
    ('KEY_UP',    '\x1b[A'),
    ('KEY_DOWN',  '\x1b[B'),
    ('KEY_LEFT',  '\x1b[D'),
    ('KEY_RIGHT', '\x1b[C'),
    ('KEY_F1',    '\x1bOP'),
    ('KEY_F5',    '\x1b[15~'),
    ('KEY_HOME',  '\x1b[H'),
    ('KEY_END',   '\x1b[F'),
    ('KEY_PGUP',  '\x1b[5~'),
    ('KEY_PGDN',  '\x1b[6~'),
    ('KEY_IC',    '\x1b[2~'),   # Insert
    ('KEY_DC',    '\x1b[3~'),   # Delete
]

@pytest.mark.parametrize('name,raw', _SEQUENCE_KEYS)
def test_sequence_key_does_not_modify_cmd_line(name, raw):
    key = _key(is_seq=True, raw=raw)
    before = 'wq'
    assert _cmd_append(before, key) == before

@pytest.mark.parametrize('name,raw', _SEQUENCE_KEYS)
def test_sequence_key_on_empty_cmd_line_stays_empty(name, raw):
    key = _key(is_seq=True, raw=raw)
    assert _cmd_append('', key) == ''

def test_sequence_key_result_contains_no_escape_bytes():
    for _, raw in _SEQUENCE_KEYS:
        key = _key(is_seq=True, raw=raw)
        result = _cmd_append('q', key)
        assert '\x1b' not in result, f'escape byte leaked for sequence {raw!r}'


# ── printable keys must be appended ──────────────────────────────────────────

@pytest.mark.parametrize('char', list('abcdefghijklmnopqrstuvwxyz0123456789!/.'))
def test_printable_key_appends(char):
    key = _key(is_seq=False, raw=char)
    assert _cmd_append('', key) == char

def test_printable_key_appends_to_existing():
    key = _key(is_seq=False, raw='q')
    assert _cmd_append('w', key) == 'wq'
