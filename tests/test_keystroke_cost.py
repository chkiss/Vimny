"""Verify that budget cost == number of physical keys typed for every motion type.

The invariant: however many characters the player physically pressed to produce a
motion, that is exactly how many budget points it costs.  len(keystrokes) is the
ground truth — it is literally how many keys were on the keyboard.
"""
import pytest
from engine.vim_parser import parse
from engine.modes import Mode
from main import _keystroke_cost

# Each entry is a raw keystroke string whose len() is the expected cost.
CASES = [
    # ── single-character motions ──────────────────────────────────────────
    'h', 'j', 'k', 'l',
    'w', 'b', 'e',
    '0', '^', '$',
    ';', ',',
    'G',
    # ── count + single-character ──────────────────────────────────────────
    '5l', '10l', '99h', '5w', '10j', '100k',
    # ── f/F/t/T: two-character motions (motion key + mandatory target) ────
    'fg', 'Fg', 'tg', 'Tg',
    'f!', 't!', 'f0', 'fh',
    # ── count + f/F/t/T ───────────────────────────────────────────────────
    '3fg', '10fg', '5tg',
    # ── gg: two-character motion ──────────────────────────────────────────
    'gg',
]


@pytest.mark.parametrize("keystrokes", CASES)
def test_cost_equals_keys_typed(keystrokes):
    action, remaining = parse(keystrokes, Mode.NORMAL)

    assert action is not None and action.get('type') not in (None, 'unknown'), \
        f"'{keystrokes}' did not parse to a valid motion"
    assert remaining == '', \
        f"'{keystrokes}' left unconsumed input: {remaining!r}"

    motion = action.get('motion', '')
    count  = action.get('count', 1)
    cost   = _keystroke_cost(count, motion)

    assert cost == len(keystrokes), (
        f"'{keystrokes}': typed {len(keystrokes)} key(s) but budget cost = {cost}"
    )
