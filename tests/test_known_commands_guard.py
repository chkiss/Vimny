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
    assert not action_allowed(action, known_commands(level_without)), \
        f"'{keys}' should be blocked at level {level_without}"


@pytest.mark.parametrize("keys,level_without,level_with", _MOTION_LEVEL_CASES)
def test_motion_allowed_at_unlock_level(keys, level_without, level_with):
    action = _parse(keys)
    assert action_allowed(action, known_commands(level_with)), \
        f"'{keys}' should be allowed at level {level_with}"


@pytest.mark.parametrize("keys", ['h', 'j', 'k', 'l'])
def test_hjkl_always_allowed(keys):
    action = _parse(keys)
    assert action_allowed(action, [])
    assert action_allowed(action, known_commands(0))


@pytest.mark.parametrize("keys", ['G', 'gg', '{', '}'])
def test_never_in_standard_known_commands(keys):
    """G, gg, paragraph motions never appear in levels 0-5."""
    action = _parse(keys)
    for level in range(6):
        assert not action_allowed(action, known_commands(level)), \
            f"'{keys}' should be blocked at level {level}"


def test_count_motion_blocked_below_level_2():
    action = _parse('3j')
    assert not action_allowed(action, known_commands(1))


def test_count_motion_allowed_at_level_2():
    action = _parse('3j')
    assert action_allowed(action, known_commands(2))


def test_count_1_not_gated_by_count_token():
    action = _parse('j')
    assert action_allowed(action, known_commands(0))


def test_admin_bypasses_all_motion_guards():
    for keys in ('^', 'w', 'G', 'gg', '{', '3j'):
        action = _parse(keys)
        assert action_allowed(action, ['admin']), f"admin should bypass guard for '{keys}'"


# ── Paste guard ────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("keys", ['p', 'P'])
def test_paste_blocked_for_all_standard_levels(keys):
    action = _parse(keys)
    for level in range(6):
        assert not action_allowed(action, known_commands(level)), \
            f"'{keys}' should be blocked at level {level}"


@pytest.mark.parametrize("keys", ['p', 'P'])
def test_paste_allowed_with_register(keys):
    action = _parse(keys)
    assert action_allowed(action, known_commands(0) + ['register'])


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
        assert not action_allowed(action, known_commands(level)), \
            f"'{keys}' should be blocked at level {level}"


@pytest.mark.parametrize("keys", ['i', 'a', 'o', 'I', 'A', 'O'])
def test_insert_mode_allowed_with_insert_token(keys):
    action = _parse(keys)
    assert action_allowed(action, ['insert'])
    assert action_allowed(action, known_commands(0) + ['insert'])


@pytest.mark.parametrize("keys", ['v', 'V', '\x16'])
def test_visual_mode_blocked_for_all_standard_levels(keys):
    action = _parse(keys)
    for level in range(6):
        assert not action_allowed(action, known_commands(level)), \
            f"'{keys!r}' should be blocked at level {level}"


@pytest.mark.parametrize("keys", ['v', 'V', '\x16'])
def test_visual_mode_allowed_with_visual_token(keys):
    action = _parse(keys)
    assert action_allowed(action, ['visual'])


def test_command_mode_always_allowed():
    action = _parse(':')
    assert action_allowed(action, [])
    assert action_allowed(action, known_commands(0))


# ── Operator / substitute guards ───────────────────────────────────────────────

@pytest.mark.parametrize("keys", ['dd', 'yy', 'cc', 'dw', 'yw', 'D', 'C'])
def test_operators_blocked_outside_edit_mode(keys):
    action = _parse(keys)
    assert not action_allowed(action, ['admin'], edit_mode=False)


@pytest.mark.parametrize("keys", ['dd', 'yy', 'cc', 'dw'])
def test_operators_allowed_in_edit_mode(keys):
    action = _parse(keys)
    assert action_allowed(action, known_commands(0), edit_mode=True)


def test_substitute_blocked_outside_edit_mode():
    assert not action_allowed(_parse('s'), ['admin'], edit_mode=False)


def test_substitute_allowed_in_edit_mode():
    assert action_allowed(_parse('s'), known_commands(0), edit_mode=True)


# ── Always-allowed actions ─────────────────────────────────────────────────────

@pytest.mark.parametrize("keys", ['x', 'u', '\x12'])
def test_interact_undo_redo_always_allowed(keys):
    action = _parse(keys)
    assert action_allowed(action, [])
    assert action_allowed(action, known_commands(0))


@pytest.mark.parametrize("keys", ['ma', "'a", '`a'])
def test_mark_commands_always_allowed(keys):
    action = _parse(keys)
    assert action_allowed(action, [])
    assert action_allowed(action, known_commands(0))
