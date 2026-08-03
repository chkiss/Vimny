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

"""Signing in as `admin` must SAY what it just did.

The name unlocks every level, opens the forge, and prints each level's solution
across the screen as you play. The first two are reversible; the third is not —
you cannot un-read an answer. `admin` is also an ordinary thing to type at a
name prompt, so the cost of finding out by accident is the whole game spoiled.

Once per SAVE, not once per session: a player who deliberately authors in admin
should not be nagged every launch, and a player who typed it by mistake finds
out on the first run, which is the only run that matters.
"""
import pytest

import main


class _FakeTerm:
    """Enough terminal to render into and to answer one keypress."""
    def __init__(self):
        self.printed = []
        self.keys_read = 0
        self.height = 41
        self.width = 100
        self.normal = ''
        self.home = ''
        self.clear = ''

    def on_color_rgb(self, *a):  return ''
    def color_rgb(self, *a):     return ''
    @property
    def bold(self):              return ''
    def move_yx(self, y, x):     return ''
    def inkey(self, *a, **k):
        self.keys_read += 1
        return 'x'


class _P:
    def __init__(self, name):
        self.name = name


@pytest.fixture
def term(monkeypatch):
    t = _FakeTerm()
    monkeypatch.setattr('builtins.print',
                        lambda *a, **k: t.printed.append(' '.join(map(str, a))))
    return t


@pytest.fixture(autouse=True)
def _no_disk(monkeypatch):
    """Never touch a real save file."""
    saved = {}
    monkeypatch.setattr(main.SM, 'save_progress',
                        lambda prog, who: saved.update({who: dict(prog)}))
    return saved


def _screen(term):
    return '\n'.join(term.printed)


def test_admin_gets_the_notice_on_a_fresh_save(term, _no_disk):
    progress = {}
    main.maybe_admin_notice(term, _P('admin'), progress)
    assert term.keys_read == 1, 'the notice must WAIT for a key, not flash past'
    assert progress.get('admin_notice_seen') is True
    assert _no_disk['admin']['admin_notice_seen'] is True, 'not written down'


def test_it_says_the_three_things_that_matter(term):
    main.maybe_admin_notice(term, _P('admin'), {})
    screen = _screen(term).lower()
    assert 'admin mode' in screen
    # the reversible two…
    assert 'unlocks every level' in screen
    assert 'forge' in screen
    # …and the one that is not: it must use the word, not imply it
    assert 'solution' in screen
    # and it must tell them the way out
    assert 'any other name' in screen


def test_it_does_not_read_as_flavour(term):
    """Every other full-screen box in this game is the wizard's voice, and
    players skim those. This one is plain — no scroll framing, no in-world
    narrator — because a warning that reads as atmosphere is not heeded."""
    main.maybe_admin_notice(term, _P('admin'), {})
    screen = _screen(term).lower()
    for flavour in ('warden', 'wizard', 'dungeon keeps', 'thou', 'hark'):
        assert flavour not in screen, f'{flavour!r} makes it read as a scroll'


def test_it_fires_once_per_save_not_once_per_session(term):
    progress = {}
    main.maybe_admin_notice(term, _P('admin'), progress)
    main.maybe_admin_notice(term, _P('admin'), progress)
    main.maybe_admin_notice(term, _P('admin'), progress)
    assert term.keys_read == 1


def test_a_second_save_gets_its_own_notice(term):
    """The flag lives in the SAVE, so a different admin save has not seen it."""
    main.maybe_admin_notice(term, _P('admin'), {'admin_notice_seen': True})
    assert term.keys_read == 0
    main.maybe_admin_notice(term, _P('admin'), {})       # a fresh save
    assert term.keys_read == 1


@pytest.mark.parametrize('name', ['Normand', 'Admin', 'ADMIN', 'admin2', ''])
def test_no_notice_for_anyone_else(term, name):
    """The gate is the exact name the privilege check uses (`main.py`'s
    `player_name == 'admin'`). If these ever diverge, one of them is wrong."""
    progress = {}
    main.maybe_admin_notice(term, _P(name), progress)
    assert term.keys_read == 0
    assert 'admin_notice_seen' not in progress


def test_the_notice_name_matches_the_privilege_name():
    """A guard against the two drifting apart: the notice must fire for exactly
    the name that grants the privileges, or a player is spoiled in silence."""
    import inspect
    src = inspect.getsource(main.maybe_admin_notice)
    assert "player.name != 'admin'" in src
    # and the privilege check still keys on the same literal
    whole = inspect.getsource(main)
    assert "player_name == 'admin'" in whole
