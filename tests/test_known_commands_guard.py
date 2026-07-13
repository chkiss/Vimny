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

"""
Verify that action_allowed() correctly gates every parser-reachable action
against the player's known_commands.  This is the canonical guard contract:
if a case is missing here, it is not guarded in the game loop.

Parametrised pairs test BOTH sides of each guard:
  - blocked when the required token is absent
  - allowed when it is present
"""
import pytest
from engine.vim_parser import parse
from engine.modes import Mode
from engine.command_guard import action_allowed
from content.levels import known_commands

# These guard tests address levels by their (legacy) display number; resolve
# each to a slug so the gating contract is checked by identity, not by number.
_SLUG_BY_NUM = {0: 'first_cave', 1: 'line_halls', 2: 'counting_crypts',
                3: 'rune_halls', 4: 'character_cataracts', 5: 'goblin_gauntlet',
                20: 'quartermaster'}


def _kc(num: int) -> list:
    """known_commands for the level historically numbered `num`."""
    return known_commands(_SLUG_BY_NUM[num])


def _parse(keys: str) -> dict:
    action, _ = parse(keys, Mode.NORMAL)
    assert action is not None and action['type'] != 'unknown', \
        f"'{keys}' did not produce a valid action"
    return action


# ── Motion guards ──────────────────────────────────────────────────────────────

# (keystroke, level_that_lacks_it, level_that_has_it)
_MOTION_LEVEL_CASES = [
    ('^',  0, 1),
    ('$',  0, 1),
    ('0',  0, 1),
    ('w',  2, 3),
    ('b',  2, 3),
    ('e',  2, 3),
    ('fa', 3, 4),
    ('Fa', 3, 4),
    ('ta', 3, 4),
    ('Ta', 3, 4),
    (';',  4, 5),
    (',',  4, 5),
]


@pytest.mark.parametrize("keys,level_without,level_with", _MOTION_LEVEL_CASES)
def test_motion_blocked_below_unlock_level(keys, level_without, level_with):
    action = _parse(keys)
    assert not action_allowed(action, _kc(level_without)), \
        f"'{keys}' should be blocked at level {level_without}"


@pytest.mark.parametrize("keys,level_without,level_with", _MOTION_LEVEL_CASES)
def test_motion_allowed_at_unlock_level(keys, level_without, level_with):
    action = _parse(keys)
    assert action_allowed(action, _kc(level_with)), \
        f"'{keys}' should be allowed at level {level_with}"


@pytest.mark.parametrize("keys", ['h', 'j', 'k', 'l'])
def test_hjkl_always_allowed(keys):
    action = _parse(keys)
    assert action_allowed(action, [])
    assert action_allowed(action, _kc(0))


@pytest.mark.parametrize("keys", ['G', 'gg', '{', '}'])
def test_never_in_standard__kc(keys):
    """G, gg, paragraph motions never appear in levels 0-5."""
    action = _parse(keys)
    for level in range(6):
        assert not action_allowed(action, _kc(level)), \
            f"'{keys}' should be blocked at level {level}"


def test_count_motion_blocked_below_level_2():
    action = _parse('3j')
    assert not action_allowed(action, _kc(1))


def test_count_motion_allowed_at_level_2():
    action = _parse('3j')
    assert action_allowed(action, _kc(2))


def test_count_1_not_gated_by_count_token():
    action = _parse('j')
    assert action_allowed(action, _kc(0))


def test_admin_bypasses_all_motion_guards():
    for keys in ('^', 'w', 'G', 'gg', '{', '3j'):
        action = _parse(keys)
        assert action_allowed(action, ['admin']), f"admin should bypass guard for '{keys}'"


# ── Paste guard ────────────────────────────────────────────────────────────────

def test_p_blocked_before_level_5():
    action = _parse('p')
    for level in range(5):
        assert not action_allowed(action, _kc(level)), \
            f"'p' should be blocked at level {level}"


def test_p_allowed_at_level_5():
    assert action_allowed(_parse('p'), _kc(5))


def test_P_blocked_before_level_20():
    action = _parse('P')
    for level in range(6):
        assert not action_allowed(action, _kc(level)), \
            f"'P' should be blocked at level {level}"


def test_P_allowed_at_level_20():
    assert action_allowed(_parse('P'), _kc(20))


@pytest.mark.parametrize("keys", ['p', 'P'])
def test_paste_allowed_in_edit_mode(keys):
    action = _parse(keys)
    assert action_allowed(action, [], edit_mode=True)


def test_admin_bypasses_paste_guard():
    assert action_allowed(_parse('p'), ['admin'])


# ── Mode-entry guards ──────────────────────────────────────────────────────────

@pytest.mark.parametrize("keys", ['i', 'a', 'o', 'I', 'A', 'O'])
def test_insert_mode_blocked_for_all_standard_levels(keys):
    action = _parse(keys)
    for level in range(6):
        assert not action_allowed(action, _kc(level)), \
            f"'{keys}' should be blocked at level {level}"


@pytest.mark.parametrize("keys", ['i', 'a'])
def test_basic_insert_allowed_with_insert_token(keys):
    # The basic insert lesson (Inscription Halls) teaches i/a under the 'insert' gate.
    action = _parse(keys)
    assert action_allowed(action, ['insert'])
    assert action_allowed(action, _kc(0) + ['insert'])


@pytest.mark.parametrize("key", ['o', 'O', 'I', 'A'])
def test_line_open_insert_needs_its_own_token_not_insert(key):
    # One gate per lesson: o/O/I/A are The Sculpting Chambers' lesson, so the 'insert'
    # token alone must NOT unlock them (else they'd be usable at Inscription Halls yet
    # only shown three levels later — the unlocked-but-invisible bug).
    action = _parse(key)
    assert not action_allowed(action, ['insert'])
    assert action_allowed(action, ['insert', key])


@pytest.mark.parametrize("keys", ['v', 'V', '\x16'])
def test_visual_mode_blocked_for_all_standard_levels(keys):
    action = _parse(keys)
    for level in range(6):
        assert not action_allowed(action, _kc(level)), \
            f"'{keys!r}' should be blocked at level {level}"


@pytest.mark.parametrize("keys,token", [('v', 'visual'), ('V', 'visual_line'),
                                        ('\x16', 'visual_block')])
def test_visual_mode_gates_per_token(keys, token):
    """One gate per lesson: v is the Sight Sanctum's; V and <C-v> are the
    Selection Halls' own tokens — learning v must NOT pre-unlock them."""
    action = _parse(keys)
    assert action_allowed(action, [token])
    if token != 'visual':
        assert not action_allowed(action, ['visual'])


def test_command_mode_always_allowed():
    action = _parse(':')
    assert action_allowed(action, [])
    assert action_allowed(action, _kc(0))


# ── Operator / substitute guards ───────────────────────────────────────────────

@pytest.mark.parametrize("keys", ['dd', 'dw', 'yy', 'yw', 'cc', 'cw', 'C'])
def test_operators_blocked_until_learned(keys):
    # Player without the operator command learned cannot use it outside edit mode.
    action = _parse(keys)
    assert not action_allowed(action, _kc(0), edit_mode=False)


@pytest.mark.parametrize("keys,op", [
    ('dd', 'd'), ('dw', 'd'), ('yy', 'y'), ('yw', 'y'),
    ('cc', 'c'), ('cw', 'c'),
])
def test_operators_allowed_once_learned(keys, op):
    # Once the operator (and its motion) are in known_commands, it works outside edit mode.
    action = _parse(keys)
    known = ['h', 'j', 'k', 'l', 'w', '$', op]
    assert action_allowed(action, known, edit_mode=False)


@pytest.mark.parametrize("keys,op,tok", [('D', 'd', 'D'), ('C', 'c', 'C')])
def test_line_end_shorthands_need_their_own_token(keys, op, tok):
    # D/C are one-key shorthands for d$/c$ and are gated as their OWN lessons:
    # knowing the operator + '$' is not enough until the shorthand is learned
    # (The Operator's Vault forces the two-key grammar; D unlocks at the Cipher
    # Cell, C at the Change Annex).
    action = _parse(keys)
    known = ['h', 'j', 'k', 'l', 'w', '$', op]
    assert not action_allowed(action, known, edit_mode=False)
    assert action_allowed(action, known + [tok], edit_mode=False)


@pytest.mark.parametrize("keys,tok", [('diw', 'iw'), ('ci(', 'i('), ('da"', 'a"')])
def test_text_objects_blocked_until_learned(keys, tok):
    action = _parse(keys)
    op = action['op']
    assert not action_allowed(action, ['h', op], edit_mode=False)        # op known, object not
    assert action_allowed(action, ['h', op, tok], edit_mode=False)        # both known


@pytest.mark.parametrize("keys,op", [('>>', '>'), ('<<', '<'), ('>j', '>')])
def test_indent_gated_on_token(keys, op):
    action = _parse(keys)
    assert not action_allowed(action, ['h', 'j'], edit_mode=False)
    assert action_allowed(action, ['h', 'j', op], edit_mode=False)


@pytest.mark.parametrize("keys", ['"ayy', '"ap', '"0p', '"_dw'])
def test_named_register_gated_on_reg_named(keys):
    action = _parse(keys)
    base = ['h', 'd', 'y', 'w', 'p', 'P', 'register']  # operator/motion/paste tokens, no reg_named
    assert not action_allowed(action, base, edit_mode=False)
    assert action_allowed(action, base + ['reg_named'], edit_mode=False)


@pytest.mark.parametrize("keys", ['\x0f', '\t'])
def test_jump_gated_on_jump_token(keys):
    assert not action_allowed(_parse(keys), _kc(0), edit_mode=False)
    assert action_allowed(_parse(keys), ['h', 'jump'], edit_mode=False)


@pytest.mark.parametrize("keys", ['ma', "'a", '`a'])
def test_marks_gated_on_mark_token(keys):
    assert not action_allowed(_parse(keys), _kc(0), edit_mode=False)
    assert action_allowed(_parse(keys), ['h', 'mark'], edit_mode=False)


def test_macro_record_gated_on_q():
    assert not action_allowed(_parse('qa'), _kc(0), edit_mode=False)
    assert action_allowed(_parse('qa'), ['h', 'q'], edit_mode=False)


def test_macro_play_gated_on_at():
    assert not action_allowed(_parse('@a'), ['h', 'q'], edit_mode=False)
    assert action_allowed(_parse('@a'), ['h', '@'], edit_mode=False)


@pytest.mark.parametrize("keys", ['/', '?', 'n', 'N'])
def test_search_gated_on_slash_token(keys):
    assert not action_allowed(_parse(keys), _kc(0), edit_mode=False)
    assert action_allowed(_parse(keys), ['h', '/'], edit_mode=False)


@pytest.mark.parametrize("keys", ['*', '#'])
def test_search_word_gated_on_star_token(keys):
    assert not action_allowed(_parse(keys), ['h', '/'], edit_mode=False)
    assert action_allowed(_parse(keys), ['h', '*'], edit_mode=False)


def test_replace_char_gated_on_token():
    assert not action_allowed(_parse('rx'), _kc(0), edit_mode=False)
    assert action_allowed(_parse('rx'), ['h', 'r'], edit_mode=False)


def test_replace_mode_gated_on_token():
    assert not action_allowed(_parse('R'), _kc(0), edit_mode=False)
    assert action_allowed(_parse('R'), ['h', 'R'], edit_mode=False)


def test_tilde_gated_on_token():
    assert not action_allowed(_parse('~'), _kc(0), edit_mode=False)
    assert action_allowed(_parse('~'), ['h', '~'], edit_mode=False)


@pytest.mark.parametrize("keys,op", [('gUw', 'gU'), ('guw', 'gu'), ('g~w', 'g~')])
def test_case_ops_gated_on_token(keys, op):
    action = _parse(keys)
    assert not action_allowed(action, ['h', 'w'], edit_mode=False)        # op not learned
    assert action_allowed(action, ['h', 'w', op], edit_mode=False)         # op learned


@pytest.mark.parametrize("keys", ['dd', 'yy', 'cc', 'dw'])
def test_operators_allowed_in_edit_mode(keys):
    action = _parse(keys)
    assert action_allowed(action, _kc(0), edit_mode=True)


@pytest.mark.parametrize("keys", ['dd', 'dw', 'yy'])
def test_operators_allowed_for_admin(keys):
    # admin (level designer) may operate anywhere.
    assert action_allowed(_parse(keys), ['admin'], edit_mode=False)


def test_substitute_allowed_for_admin_or_edit():
    assert action_allowed(_parse('s'), ['admin'], edit_mode=False)
    assert action_allowed(_parse('S'), _kc(0), edit_mode=True)


def test_substitute_blocked_until_key_learned():
    assert not action_allowed(_parse('s'), _kc(0), edit_mode=False)
    assert not action_allowed(_parse('S'), _kc(0), edit_mode=False)


def test_substitute_allowed_once_key_learned():
    assert action_allowed(_parse('s'), ['h', 's'], edit_mode=False)
    assert action_allowed(_parse('S'), ['h', 'S'], edit_mode=False)
    # learning 's' does not grant 'S'
    assert not action_allowed(_parse('S'), ['h', 's'], edit_mode=False)


def test_substitute_allowed_in_edit_mode():
    assert action_allowed(_parse('s'), _kc(0), edit_mode=True)


# ── Always-allowed actions ─────────────────────────────────────────────────────

@pytest.mark.parametrize("keys", ['x', 'u'])
def test_interact_and_undo_always_allowed(keys):
    action = _parse(keys)
    assert action_allowed(action, [])
    assert action_allowed(action, _kc(0))


def test_redo_requires_the_relic_token():
    """<C-r> is granted by the 'redo' relic scroll (the Undo Sanctum level was
    cancelled); u stays the always-on rope."""
    action = _parse('\x12')
    assert not action_allowed(action, [])
    assert not action_allowed(action, _kc(0))
    assert action_allowed(action, ['redo'])
    assert action_allowed(action, ['admin'])


@pytest.mark.parametrize("keys", ['ma', "'a", '`a'])
def test_mark_commands_require_mark_token(keys):
    # Marks are gated (taught at the marks level), not always-allowed.
    action = _parse(keys)
    assert not action_allowed(action, _kc(0))
    assert action_allowed(action, ['h', 'mark'])
    assert action_allowed(action, ['admin'])
