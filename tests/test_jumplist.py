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

"""Tests for Block J — engine/jumplist.py: record/back/forward navigation."""
from engine.player import Player
from engine.jumplist import record_jump, jump_back, jump_forward, _CAP


def _p(row=0, col=0):
    return Player(row=row, col=col)


def test_record_appends_and_sets_index():
    p = _p()
    record_jump(p, (1, 1))
    record_jump(p, (2, 2))
    assert p.jump_list == [(1, 1), (2, 2)]
    assert p.jump_idx == 2


def test_back_and_forward_walk():
    p = _p()
    record_jump(p, (1, 1)); p.row, p.col = 2, 2     # jumped A→B
    record_jump(p, (2, 2)); p.row, p.col = 3, 3     # jumped B→C  (now at C)

    d = jump_back(p)                                 # Ctrl-o: stash C, go to B
    assert d == (2, 2)
    assert p.jump_list == [(1, 1), (2, 2), (3, 3)]   # current C stashed for Ctrl-i
    p.row, p.col = d

    d = jump_back(p)                                 # → A
    assert d == (1, 1)
    p.row, p.col = d
    assert jump_back(p) is None                      # nothing older

    assert jump_forward(p) == (2, 2)                 # Ctrl-i → B
    assert jump_forward(p) == (3, 3)                 # → C
    assert jump_forward(p) is None                   # nothing newer


def test_new_jump_truncates_forward_history():
    p = _p()
    record_jump(p, (1, 1)); p.row, p.col = 2, 2
    record_jump(p, (2, 2)); p.row, p.col = 3, 3
    jump_back(p)                                     # at B, jl=[A,B,C]
    p.row, p.col = 2, 2
    record_jump(p, (2, 2))                           # new jump from B
    # forward entry (C) dropped; B re-recorded at the end
    assert (3, 3) not in p.jump_list
    assert p.jump_idx == len(p.jump_list)


def test_empty_list_navigation_is_none():
    p = _p()
    assert jump_back(p) is None
    assert jump_forward(p) is None


def test_cap_at_100():
    p = _p()
    for i in range(150):
        record_jump(p, (i, 0))
    assert len(p.jump_list) == _CAP
    assert p.jump_list[-1] == (149, 0)               # newest kept, oldest dropped


def test_consecutive_duplicate_not_recorded_twice():
    p = _p()
    record_jump(p, (5, 5))
    record_jump(p, (5, 5))
    assert p.jump_list == [(5, 5)]
