"""Out of budget = end of the line.

Once `budget.remaining <= 0` the dungeon loop refuses every budget-costing action
(the player can't move, edit, search, …); only undo/redo and entering command mode
(:q / :edit) still go through, so the player can recover or leave.  The loop itself
reads keystrokes interactively, so we test the rule it delegates to
(`_budget_exhausted_blocks`) plus the `Budget.remaining` threshold it gates on."""
import pytest
from engine.budget import Budget
from main import _budget_exhausted_blocks


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
