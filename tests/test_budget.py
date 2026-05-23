"""Tests for engine/budget.py — spend, undo, redo, remaining, is_over, status_color."""
import pytest
from engine.budget import Budget


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


class TestUndo:
    def test_undo_reverses_last_spend(self):
        b = Budget(10)
        b.spend(3)
        result = b.undo()
        assert result is True
        assert b.spent == 0

    def test_undo_reverses_correct_cost(self):
        b = Budget(20)
        b.spend(2)
        b.spend(5)
        b.undo()
        assert b.spent == 2

    def test_undo_empty_history_returns_false(self):
        b = Budget(10)
        result = b.undo()
        assert result is False
        assert b.spent == 0

    def test_undo_after_all_undone_returns_false(self):
        b = Budget(10)
        b.spend(3)
        b.undo()
        result = b.undo()
        assert result is False

    def test_multiple_undos_unwind_in_order(self):
        b = Budget(20)
        b.spend(1)
        b.spend(3)
        b.spend(2)
        b.undo()
        assert b.spent == 4
        b.undo()
        assert b.spent == 1
        b.undo()
        assert b.spent == 0


class TestRedo:
    def test_redo_adds_cost(self):
        b = Budget(10)
        b.spend(3)
        b.undo()
        b.redo(3)
        assert b.spent == 3

    def test_redo_default_cost_is_1(self):
        b = Budget(10)
        b.spend(2)
        b.undo()
        b.redo()
        assert b.spent == 1

    def test_redo_appends_to_history(self):
        b = Budget(10)
        b.spend(4)
        b.undo()
        b.redo(4)
        b.undo()
        assert b.spent == 0


class TestStatusColor:
    def test_ok_when_plenty_remaining(self):
        b = Budget(20)
        b.spend(5)   # remaining = 15
        assert b.status_color() == 'ok'

    def test_ok_at_boundary_4(self):
        b = Budget(10)
        b.spend(6)   # remaining = 4
        assert b.status_color() == 'ok'

    def test_low_at_3(self):
        b = Budget(10)
        b.spend(7)   # remaining = 3
        assert b.status_color() == 'low'

    def test_low_at_2(self):
        b = Budget(10)
        b.spend(8)   # remaining = 2
        assert b.status_color() == 'low'

    def test_crit_at_1(self):
        b = Budget(10)
        b.spend(9)   # remaining = 1
        assert b.status_color() == 'crit'

    def test_crit_at_0(self):
        b = Budget(10)
        b.spend(10)  # remaining = 0
        assert b.status_color() == 'crit'

    def test_crit_when_overspent(self):
        b = Budget(5)
        b.spend(8)   # remaining = -3
        assert b.status_color() == 'crit'
