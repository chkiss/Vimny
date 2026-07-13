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
    'gj': 'display_move', 'gk': 'display_move',
    'H': 'H',  'M': 'M',  'L': 'L',
    '%': '%',
    '{': '{',  '}': '}',  '(': '(',  ')': ')',
    '|': 'col_motion',
}


def action_allowed(action: dict, known: list | set, edit_mode: bool = False) -> bool:
    """Return True iff the player may execute action given their known_commands."""
    t = action['type']
    count     = action.get('count', 1)
    known_set = set(known)

    # substitute: s (char) / S (line). Editor cell-cycle in edit mode; otherwise a
    # player insert-entry once the key is learned.
    if t == 'substitute':
        if edit_mode or 'admin' in known_set:
            return True
        return ('S' if action.get('line') else 's') in known_set

    if 'admin' in known_set:
        return True

    # Using an explicit (non-unnamed) register requires learning named registers.
    reg = action.get('register')
    if reg is not None and reg != '"' and 'reg_named' not in known_set:
        return False

    if t == 'operator':
        if edit_mode:
            return True
        if action.get('op') not in known_set:        # 'd' / 'y' / 'c' learned?
            return False
        # D / C — the one-key to-line-end shorthands are their own lessons,
        # gated separately from the d$/c$ grammar they abbreviate.
        sh = action.get('shorthand')
        if sh is not None and sh not in known_set:
            return False
        if count > 1 and 'count' not in known_set:
            return False
        if action.get('motion_count', 1) > 1 and 'count' not in known_set:
            return False
        to = action.get('textobj')
        if to is not None:                            # text object must be learned
            return to in known_set
        motion = action.get('motion')
        if motion and motion != 'line':
            gk = _MOTION_GUARD.get(motion)
            if gk is not None and gk not in known_set:
                return False
        return True

    if t == 'case_char':                          # ~ toggle
        if count > 1 and 'count' not in known_set:
            return False
        return '~' in known_set

    if t == 'replace':                            # r{char}
        if count > 1 and 'count' not in known_set:
            return False
        return 'r' in known_set

    if t == 'join':                               # J / gJ
        if count > 1 and 'count' not in known_set:
            return False
        return ('J' if action.get('gap', True) else 'gJ') in known_set

    if t == 'motion':
        if count > 1 and 'count' not in known_set:
            return False
        guard_key = _MOTION_GUARD.get(action['motion'])
        return guard_key is None or guard_key in known_set

    if t == 'paste' and not edit_mode:
        if action.get('before'):
            return 'P' in known_set   # P — taught at The Beacon Tiers
        return 'p' in known_set       # p — taught at The Goblin Gauntlet

    if t == 'enter_mode':
        m = action.get('mode', '')
        if m == 'insert':
            # One gate per lesson: the basic insert lesson teaches i/a; the line-open
            # and line-anchored variants (o O I A) are their own lesson (The Sculpting
            # Chambers) and gate on their own tokens, so the hint bar's tier for each
            # level shows exactly the keys that level unlocks (no silent early unlock).
            var = action.get('variant', 'i')
            if var in ('i', 'a'):
                return 'insert' in known_set
            return var in known_set
        if m == 'replace':
            return 'R' in known_set
        if m == 'search':
            return '/' in known_set
        if m in ('visual', 'visual_line', 'visual_block'):
            # One gate per lesson (the insert-variant rule): charwise v is the
            # Sight Sanctum's token; V and <C-v> are the Selection Halls' own.
            return m in known_set

    if t == 'search_repeat':                      # n / N
        return '/' in known_set
    if t == 'search_word':                        # * / #
        return '*' in known_set
    if t == 'macro_record':                       # q{reg}
        return 'q' in known_set
    if t == 'macro_play':                         # @{reg} / @@
        return '@' in known_set
    if t == 'jump':                               # Ctrl-o / Ctrl-i
        return 'jump' in known_set
    if t == 'mark':                               # m{a} / '{a} / `{a}
        return 'mark' in known_set

    if t == 'repeat':
        return 'dot' in known_set

    if t == 'sub_repeat':                         # & / g& — repeat last :s
        return 'subst' in known_set

    if t == 'redo':                               # <C-r> — granted by a relic scroll;
        return 'redo' in known_set                # u stays the always-on rope

    if t == 'interact' and action.get('shorthand') == 'X':
        return 'X' in known_set                   # X — own lesson (the Y/D/C rule)

    if t == 'seal_exit':                          # ZZ / ZQ — relic scroll
        return 'ZZ' in known_set

    # interact (x), undo (u), command (:) — always allowed
    return True


def guard_message(action: dict, known: list | set = ()) -> str:
    """Human-readable reason why action_allowed returned False."""
    t = action['type']
    reg = action.get('register')
    if reg is not None and reg != '"' and 'reg_named' not in set(known):
        return f"You haven't learned the \"{reg} register yet."
    if t == 'motion':
        known_set = set(known)
        m = action['motion']
        if action.get('count', 1) > 1 and 'count' not in known_set:
            return "You haven't learned count motions yet."
        if m in ('G', 'gg'):
            return "You haven't learned G/gg yet."
        return f"You haven't learned '{m}' yet."
    if t == 'paste':
        if action.get('before'):
            return "You haven't learned 'P' yet."
        return "You haven't learned 'p' yet."
    if t == 'enter_mode':
        return f"You haven't learned {action.get('mode', '')} mode yet."
    if t == 'operator':
        op = action.get('op', '')
        if op and op not in set(known):
            return f"You haven't learned the '{op}' operator yet."
        to = action.get('textobj')
        if to and to not in set(known):
            return f"You haven't learned the '{to}' text object yet."
        return 'Editor commands require :edit mode.'
    if t == 'substitute':
        k = 'S' if action.get('line') else 's'
        if k not in set(known):
            return f"You haven't learned '{k}' yet."
        return 'Editor commands require :edit mode.'
    if t == 'repeat':
        return "You haven't learned . yet."
    if t == 'case_char':
        return "You haven't learned ~ yet."
    if t == 'replace':
        return "You haven't learned r yet."
    if t == 'join':
        return "You haven't learned J (join) yet."
    if t in ('search_repeat', 'search_word'):
        return "You haven't learned search yet."
    if t == 'macro_record':
        return "You haven't learned q (macros) yet."
    if t == 'macro_play':
        return "You haven't learned @ (macros) yet."
    if t == 'jump':
        return "You haven't learned the jump list yet."
    if t == 'redo':
        return "You haven't learned <C-r> (redo) yet."
    if t == 'mark':
        return "You haven't learned marks yet."
    if t == 'sub_repeat':
        return "You haven't learned :s (substitute) yet."
    if t == 'interact' and action.get('shorthand') == 'X':
        return "You haven't learned X yet."
    if t == 'seal_exit':
        return "You haven't learned ZZ/ZQ yet."
    return 'Command not available.'
