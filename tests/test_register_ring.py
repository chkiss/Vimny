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

"""The numbered delete ring ("1-"9) and its gate token — the engine half of
The Delete Ring (docs/blueprints/registry_wing.md, level II of the registry wing).

The ring is what makes a cut recoverable after later cuts have overwritten the
unnamed register. Two properties carry the level: a linewise delete PUSHES (so
the n-th most recent cut is always at "n), and nothing else does — a yank, a
charwise cut, or a black-hole delete must all leave the ring exactly as it was,
or the player's count of how far back a line sits would silently be wrong.
"""
import pytest
from vimny.engine.player import Player
from vimny.engine.registers import write_register, read_register, RING
from vimny.engine.command_guard import action_allowed, guard_message


def _clip(text, linewise=False):
    return {'linewise': linewise,
            'rows': [{'width': len(text),
                      'char_runs': [{'dcol': i, 'symbols': (c,), 'kind': 'ancient'}
                                    for i, c in enumerate(text)]}]}


def _cut(player, text, reg='"'):
    """A linewise delete — the thing that pushes the ring."""
    clip = _clip(text, linewise=True)
    write_register(player, reg, clip, is_delete=True)
    return clip


def _ring(player):
    """The ring read out newest-first, as plain text."""
    from vimny.engine.registers import clip_to_text
    return [clip_to_text(read_register(player, str(n))) for n in range(1, RING + 1)
            if read_register(player, str(n)) is not None]


class TestThePush:
    def test_a_linewise_delete_lands_in_one(self):
        p = Player()
        _cut(p, 'twinkle')
        assert _ring(p) == ['twinkle']

    def test_each_cut_pushes_the_last_one_older(self):
        p = Player()
        for line in ('first', 'second', 'third'):
            _cut(p, line)
        # The register number counts BACKWARDS along the cuts — this inversion is
        # the whole lesson of the level, so it is pinned literally.
        assert read_register(p, '1')['rows'][0]['width'] == len('third')
        assert _ring(p) == ['third', 'second', 'first']

    def test_the_oldest_falls_off_the_end(self):
        p = Player()
        for n in range(RING + 3):
            _cut(p, f'line{n}')
        assert len(_ring(p)) == RING
        from vimny.engine.registers import clip_to_text
        assert clip_to_text(read_register(p, '9')) == 'line3'   # 0..2 pushed out
        assert clip_to_text(read_register(p, '1')) == f'line{RING + 2}'

    def test_a_named_delete_still_pushes_the_ring(self):
        """Vim-true: "add fills BOTH "a and the ring — the ring records what was
        thrown away, not which register you aimed at."""
        p = Player()
        _cut(p, 'aimed', reg='a')
        from vimny.engine.registers import clip_to_text
        assert clip_to_text(read_register(p, 'a')) == 'aimed'
        assert _ring(p) == ['aimed']


class TestWhatMustNotPush:
    def test_a_yank_leaves_the_ring_alone(self):
        p = Player()
        _cut(p, 'cut')
        write_register(p, '"', _clip('yanked', linewise=True), is_delete=False)
        assert _ring(p) == ['cut']

    def test_a_charwise_delete_leaves_the_ring_alone(self):
        """Small cuts belong to "- (The Small Cut, level III). Until that ships
        they simply don't disturb the ring — the vim-true half."""
        p = Player()
        _cut(p, 'cut')
        write_register(p, '"', _clip('dw', linewise=False), is_delete=True)
        assert _ring(p) == ['cut']

    def test_the_black_hole_pushes_nothing(self):
        p = Player()
        _cut(p, 'kept')
        write_register(p, '_', _clip('gone', linewise=True), is_delete=True)
        assert _ring(p) == ['kept']


class TestZeroIsNotPartOfTheRing:
    def test_deletes_never_reach_the_yank_register(self):
        """The first chamber of the level rests entirely on this: three dd's
        clobber "" and push the ring, and "0 still holds the yank."""
        p = Player()
        write_register(p, '"', _clip('quarry'), is_delete=False)
        for junk in ('one', 'two', 'three'):
            _cut(p, junk)
        from vimny.engine.registers import clip_to_text
        assert clip_to_text(read_register(p, '0')) == 'quarry'
        assert clip_to_text(read_register(p, '"')) == 'three'   # clobbered, as taught


class TestTheGate:
    KNOWN = ['y', 'd', 'p', 'reg_named']

    @pytest.mark.parametrize('reg', [str(n) for n in range(RING + 1)])
    def test_a_numbered_register_needs_its_own_token(self, reg):
        """reg_named must NOT hand out the ring: everyone entering the registry
        wing already holds it, so the level would teach a key they had."""
        act = {'type': 'paste', 'register': reg}
        assert not action_allowed(act, self.KNOWN)
        assert action_allowed(act, self.KNOWN + ['reg_numbered'])

    def test_the_named_registers_are_unaffected(self):
        act = {'type': 'paste', 'register': 'a'}
        assert action_allowed(act, self.KNOWN)

    def test_the_unnamed_register_is_still_free(self):
        assert action_allowed({'type': 'paste', 'register': '"'}, ['p'])

    def test_the_horse_gate_still_applies(self):
        """The ring is a saddle register: knowing it is not enough if he is out."""
        act = {'type': 'paste', 'register': '1'}
        known = self.KNOWN + ['reg_numbered']
        assert action_allowed(act, known, horse_present=True)
        assert not action_allowed(act, known, horse_present=False)

    def test_the_refusal_names_the_register(self):
        msg = guard_message({'type': 'paste', 'register': '1'}, self.KNOWN)
        assert '"1' in msg
