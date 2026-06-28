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

"""Gating ↔ hint-bar PARITY — the structural guard against unlocked-but-invisible keys.

The hint bar derives its tiers from known_commands token diffs and expands family
gates (render.hint_bar._FAMILY) / bundled keys cells (vim_commands.md).  That display
path is independent of the gating path (engine.command_guard.action_allowed), so the
two can drift: a single token may unlock several keys while the bar shows only one
(the bug that hid `{a}/'{a}, dd, yy, append, and o/O/I/A).

This test couples the two: for every level, every command that action_allowed NEWLY
permits at that level must appear on that level's hint bar.  action_allowed is the
source of truth for "usable"; the bar must show exactly what becomes usable.  A new
multi-key gate that forgets its _FAMILY entry (or a sibling row missing from the keys
cell) fails here the day it lands.

To add a command: drop a (keystrokes, 'keys:desc') row in _GATED.  `keys:desc` is the
exact hint-bar fragment (CMD renders each entry as 'keys:desc'); a bundled cell like
'd{m}  dd:delete' still contains the fragment 'dd:delete' as a substring.
"""
import pytest
from engine.vim_parser import parse
from engine.modes import Mode
from engine.command_guard import action_allowed
from content.levels import LEVELS, known_commands, level_type
from render.hint_bar import hint_text


def _act(keys: str) -> dict:
    action, _ = parse(keys, Mode.NORMAL)
    assert action is not None and action.get('type') != 'unknown', \
        f"{keys!r} did not parse to a gated action"
    return action


# (keystrokes to parse → action,  distinctive 'keys:desc' fragment the bar must show)
# Concrete operands stand in for placeholders: dw for d{m}, ma for m{a}, fx for f{c}.
_GATED = [
    ('2j', '[N]hjkl:count move'),
    ('fx', 'f{c}:jump to char'),  ('Fx', 'F{c}:jump back to char'),
    ('tx', 't{c}:before next char'), ('Tx', 'T{c}:after prev char'),
    (';',  ';:repeat'),  (',', ',:reverse'),  ('p', 'p:paste'),
    ('/',  '/{pat}:search'), ('?', '?{pat}:search back'),
    ('n',  'n:next match'),  ('N', 'N:prev match'),  ('*', '*:search word'),
    ('ma', 'm{a}:set mark'), ('`a', '`{a}:to mark'), ("'a", "'{a}:to mark ↑"),
    ('dw', 'd{m}'),  ('dd', 'dd:delete'),
    ('rx', 'r{c}:replace char'), ('D', 'D:delete to line end'),
    ('yw', 'y{m}'),  ('yy', 'yy:yank'),  ('P', 'P:paste before'),
    ('.',  '.:repeat change'),
    ('i',  'i:insert'), ('a', 'a:append'),
    ('cw', 'c{m}'),  ('cc', 'cc:change'),  ('s', 's:substitute'),
    ('S',  'S:substitute line'), ('C', 'C:change to end'),
    ('I',  'I:insert at start'), ('A', 'A:append at end'),
    ('o',  'o:new line below'), ('O', 'O:new line above'),
]


def test_every_gated_command_parses_and_is_eventually_unlocked():
    """Sanity: each registry entry is a real gated action that admin always allows
    (guards against a typo'd keystroke silently never matching)."""
    for keys, _frag in _GATED:
        assert action_allowed(_act(keys), ['admin']), f"{keys!r} not allowed even for admin"


def test_bar_shows_every_newly_unlocked_command():
    """For every level, each command action_allowed newly permits there is on the bar.

    Walks the curriculum in order tracking the previous level's known_commands; a
    command 'newly unlocked' at L (allowed now, blocked before) must appear in L's
    hint bar.  Boss levels are skipped — their bar shows the whole act, not the diff.
    """
    prev: set = set()
    failures = []
    for lv in LEVELS:
        if lv.get('admin_only'):
            continue
        slug = lv['slug']
        known = set(known_commands(slug))
        if level_type(slug) != 'boss':
            bar = hint_text(list(known), slug)
            for keys, frag in _GATED:
                action = _act(keys)
                if action_allowed(action, known) and not action_allowed(action, prev):
                    if frag not in bar:
                        failures.append(f"{slug}: {keys!r} newly unlocked but "
                                        f"{frag!r} missing from bar\n      bar={bar!r}")
        prev = known
    assert not failures, "unlocked-but-invisible keys:\n  " + "\n  ".join(failures)


@pytest.mark.parametrize("slug,blocked", [
    ('inscription_halls', ['o', 'O', 'I', 'A']),   # the line-open variants wait for Sculpting
])
def test_deferred_commands_are_neither_usable_nor_shown_early(slug, blocked):
    """The converse guard: a command deferred to a LATER lesson must be both gated
    out AND absent from the bar at the earlier level — never usable-but-hidden."""
    known = known_commands(slug)
    bar = hint_text(known, slug)
    for keys in blocked:
        assert not action_allowed(_act(keys), known), f"{slug}: {keys!r} should still be gated"
        # its descriptive fragment must not be on this level's bar
        frag = {'o': 'new line below', 'O': 'new line above',
                'I': 'insert at start', 'A': 'append at end'}[keys]
        assert frag not in bar, f"{slug}: {frag!r} shown before its lesson"
