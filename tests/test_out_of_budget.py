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

"""Out of budget = end of the line.

Once `budget.remaining <= 0` the dungeon loop refuses every budget-costing action
(the player can't move, edit, search, …); only undo/redo and entering command mode
(:q / :edit) still go through, so the player can recover or leave.  The loop itself
reads keystrokes interactively, so we test the rule it delegates to
(`_budget_exhausted_blocks`) plus the `Budget.remaining` threshold it gates on."""
import pytest
from vimny.engine.budget import Budget
from vimny.game import _budget_exhausted_blocks


# ── the recovery / exit actions that stay allowed when out of budget ─────────────
@pytest.mark.parametrize('action', [
    {'type': 'undo'},
    {'type': 'redo'},
    {'type': 'enter_mode', 'mode': 'command'},     # ':' → :q to quit, :edit
])
def test_recovery_and_quit_actions_are_never_blocked(action):
    assert _budget_exhausted_blocks(action) is False


# ── everything that spends budget (i.e. moves you on) is blocked ────────────────
@pytest.mark.parametrize('action', [
    {'type': 'motion', 'motion': 'l'},
    {'type': 'motion', 'motion': 'j', 'count': 9},
    {'type': 'jump'},
    {'type': 'mark'},
    {'type': 'search_word'},
    {'type': 'interact'},
    {'type': 'paste'},
    {'type': 'substitute'},
    {'type': 'repeat'},
    {'type': 'enter_mode', 'mode': 'insert'},      # can't START editing when spent
    {'type': 'enter_mode', 'mode': 'visual'},      # can't START a selection when spent
    {'type': 'enter_mode', 'mode': 'search'},      # can't START a search when spent
])
def test_budget_costing_actions_are_blocked(action):
    assert _budget_exhausted_blocks(action) is True


# ── the threshold the loop gates on ──────────────────────────────────────────────
def test_remaining_is_zero_exactly_at_budget():
    b = Budget(total=5)
    b.spend(4)
    assert b.remaining == 1            # last keystroke still affordable -> move allowed
    b.spend(1)
    assert b.remaining == 0            # spent the lot -> loop now blocks (<= 0)
    assert not b.is_over               # exactly at budget is not yet "over"


def test_remaining_goes_negative_on_an_overshooting_count_move():
    b = Budget(total=5)
    b.spend(4)
    b.spend(3)                         # a 2-digit count move from remaining 1
    assert b.remaining == -2 <= 0      # overshot -> subsequent moves blocked
