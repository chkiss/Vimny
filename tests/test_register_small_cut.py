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

"""The small-delete register ("-) and its gate token — the engine half of
The Small Cut (docs/blueprints/registry_wing.md, level III of the registry wing).

"- is the ring's other half: a delete shorter than one line goes here and NOT
into "1, so the two slots never hold the same cut. That separation is the whole
lesson — a charwise fix survives a later `dd` that has long since taken "", and
it survives at a name the player can say, no matter how many lines were cut in
between.
"""
import pytest
from vimny.engine.player import Player
from vimny.engine.registers import (write_register, read_register, clip_to_text,
                                    RING)
from vimny.engine.command_guard import action_allowed, guard_message


def _clip(text, linewise=False):
    return {'linewise': linewise,
            'rows': [{'width': len(text),
                      'char_runs': [{'dcol': i, 'symbols': (c,), 'kind': 'ancient'}
                                    for i, c in enumerate(text)]}]}


def _cut(player, text, reg='"', linewise=False):
    write_register(player, reg, _clip(text, linewise=linewise), is_delete=True)


def _small(player):
    clip = read_register(player, '-')
    return None if clip is None else clip_to_text(clip)


class TestWhatLandsThere:
    def test_a_charwise_delete_lands_in_the_small_register(self):
        p = Player()
        _cut(p, 'horse')
        assert _small(p) == 'horse'

    def test_a_linewise_delete_does_not(self):
        """The ring's cut is the ring's. If a `dd` also filled "-, the level's
        promise — that the small cut is still there after it — would be a lie."""
        p = Player()
        _cut(p, 'horse')
        _cut(p, 'a whole line of stone', linewise=True)
        assert _small(p) == 'horse'
        assert clip_to_text(read_register(p, '1')) == 'a whole line of stone'

    def test_a_yank_does_not(self):
        p = Player()
        _cut(p, 'horse')
        write_register(p, '"', _clip('quarry'), is_delete=False)
        assert _small(p) == 'horse'
        assert clip_to_text(read_register(p, '0')) == 'quarry'

    def test_a_black_hole_delete_does_not(self):
        """"_x throws the cut away entirely — the void keeps no copy."""
        p = Player()
        _cut(p, 'horse')
        _cut(p, 'decoy', reg='_')
        assert _small(p) == 'horse'

    def test_a_named_small_cut_fills_it_too(self):
        """"- records what was THROWN AWAY, not which register you aimed at —
        the same law the ring keeps for `"add`."""
        p = Player()
        _cut(p, 'horse', reg='a')
        assert _small(p) == 'horse'
        assert clip_to_text(read_register(p, 'a')) == 'horse'

    def test_the_newest_small_cut_wins(self):
        """There is no small-delete ring in vim — one slot, last write wins."""
        p = Player()
        _cut(p, 'horse')
        _cut(p, 'saddle')
        assert _small(p) == 'saddle'

    def test_the_unnamed_register_still_mirrors_both(self):
        p = Player()
        _cut(p, 'horse')
        assert clip_to_text(read_register(p, '"')) == 'horse'
        _cut(p, 'a whole line of stone', linewise=True)
        assert clip_to_text(read_register(p, '"')) == 'a whole line of stone'

    def test_the_small_cut_outlives_a_full_ring(self):
        """The level's forcing argument, asserted: after enough `dd`s to roll the
        ring right over, "" and every numbered slot have lost the small cut and
        "- has not."""
        p = Player()
        _cut(p, 'horse')
        for n in range(RING + 2):
            _cut(p, f'line {n}', linewise=True)
        assert _small(p) == 'horse'
        assert all(clip_to_text(read_register(p, str(n))) != 'horse'
                   for n in range(1, RING + 1))


class TestTheGate:
    KNOWN = ['y', 'd', 'p', 'reg_named']

    def test_the_small_register_needs_its_own_token(self):
        """Like the ring, "- must not ride in on reg_named — everyone entering
        the registry wing already holds that."""
        act = {'type': 'paste', 'register': '-'}
        assert not action_allowed(act, self.KNOWN)
        assert not action_allowed(act, self.KNOWN + ['reg_numbered'])
        assert action_allowed(act, self.KNOWN + ['reg_small_delete'])

    def test_the_horse_gate_still_applies(self):
        act = {'type': 'paste', 'register': '-'}
        known = self.KNOWN + ['reg_small_delete']
        assert action_allowed(act, known, horse_present=True)
        assert not action_allowed(act, known, horse_present=False)

    def test_the_refusal_names_the_register(self):
        msg = guard_message({'type': 'paste', 'register': '-'}, self.KNOWN)
        assert '"-' in msg

    @pytest.mark.parametrize('reg', ['a', '"'])
    def test_the_other_registers_are_unaffected(self, reg):
        assert action_allowed({'type': 'paste', 'register': reg},
                              self.KNOWN + ['p'])
