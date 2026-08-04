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

"""Tests for vimny/engine/budget.py — spend (frozen), remaining, is_over."""
from vimny.engine.budget import Budget


class TestFrozen:
    def test_spend_is_noop_when_frozen(self):
        b = Budget(10)
        b.frozen = True
        b.spend(3)
        assert b.spent == 0 and b.remaining == 10

    def test_spend_resumes_when_unfrozen(self):
        b = Budget(10)
        b.frozen = True
        b.spend(5)
        b.frozen = False
        b.spend(2)
        assert b.spent == 2


class TestRemaining:
    def test_full_at_start(self):
        b = Budget(10)
        assert b.remaining == 10

    def test_decreases_after_spend(self):
        b = Budget(10)
        b.spend(3)
        assert b.remaining == 7

    def test_zero_after_exact_spend(self):
        b = Budget(5)
        b.spend(5)
        assert b.remaining == 0

    def test_negative_when_overspent(self):
        b = Budget(5)
        b.spend(7)
        assert b.remaining == -2


class TestIsOver:
    def test_not_over_at_start(self):
        assert not Budget(10).is_over

    def test_not_over_when_exactly_at_total(self):
        b = Budget(5)
        b.spend(5)
        assert not b.is_over  # spent == total → remaining == 0 → NOT over

    def test_over_when_one_past(self):
        b = Budget(5)
        b.spend(6)
        assert b.is_over

    def test_over_accumulates_across_calls(self):
        b = Budget(3)
        b.spend(2)
        b.spend(2)  # total spent = 4 > 3
        assert b.is_over


class TestSpend:
    def test_default_cost_is_1(self):
        b = Budget(10)
        b.spend()
        assert b.spent == 1

    def test_explicit_cost(self):
        b = Budget(10)
        b.spend(4)
        assert b.spent == 4

    def test_multiple_spends_accumulate(self):
        b = Budget(20)
        b.spend(3)
        b.spend(5)
        b.spend(2)
        assert b.spent == 10
