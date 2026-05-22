"""Single source of truth for known_commands gating.

action_allowed() is the only guard callers need; guard_message() provides
a human-readable explanation when it returns False.
"""
from __future__ import annotations

# motion key → token that must appear in known_commands to execute it.
# Motions absent from this dict (h j k l) are always permitted.
_MOTION_GUARD: dict[str, str] = {
    '^': '^',  '$': '$',  '0': '0',
    'w': 'w',  'b': 'b',  'e': 'e',
    'W': 'W',  'B': 'B',  'E': 'E',
    'f': 'f',  'F': 'F',  't': 't',  'T': 'T',
    ';': ';',  ',': ',',
    'G': 'G',  'gg': 'G',
    'ge': 'ge', 'gE': 'gE',
    '{': '{',  '}': '}',
}


def action_allowed(action: dict, known: list | set, edit_mode: bool = False) -> bool:
    """Return True iff the player may execute action given their known_commands."""
    t = action['type']

    # edit_mode is a hard requirement regardless of admin status
    if t in ('operator', 'substitute') and not edit_mode:
        return False

    if 'admin' in known:
        return True

    count     = action.get('count', 1)
    known_set = set(known)

    if t == 'motion':
        if count > 1 and 'count' not in known_set:
            return False
        guard_key = _MOTION_GUARD.get(action['motion'])
        return guard_key is None or guard_key in known_set

    if t == 'paste' and not edit_mode:
        return 'register' in known_set

    if t == 'enter_mode':
        m = action.get('mode', '')
        if m == 'insert':
            return 'insert' in known_set
        if m in ('visual', 'visual_line', 'visual_block'):
            return 'visual' in known_set

    if t == 'repeat':
        return 'dot' in known_set

    # interact (x), undo (u), redo (^R), command (:), mark — always allowed
    return True


def guard_message(action: dict, known: list | set = ()) -> str:
    """Human-readable reason why action_allowed returned False."""
    t = action['type']
    if t == 'motion':
        known_set = set(known)
        m = action['motion']
        if action.get('count', 1) > 1 and 'count' not in known_set:
            return "You haven't learned count motions yet."
        if m in ('G', 'gg'):
            return "You haven't learned G/gg yet."
        return f"You haven't learned '{m}' yet."
    if t == 'paste':
        return 'You haven\'t learned the " register yet.'
    if t == 'enter_mode':
        return f"You haven't learned {action.get('mode', '')} mode yet."
    if t in ('operator', 'substitute'):
        return 'Editor commands require :edit mode.'
    if t == 'repeat':
        return "You haven't learned . yet."
    return 'Command not available.'
