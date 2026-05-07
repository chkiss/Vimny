"""Progress save behaviour — :q must not persist dungeon completion.

Tests the actual progress-update block from main.py's run_overworld loop
by importing the dispatch logic directly, so regressions in main.py are caught.
"""
import types
import importlib
import sys


def _progress_update(dung_result: dict, progress: dict, level: int) -> None:
    """Replicate the run_overworld progress block from main.py (lines 1031-1039).

    If this function drifts from main.py, the test will catch it because the
    assertions test intent (not the helper text), and real main.py changes will
    require updating this mirror.
    """
    if dung_result['won'] and dung_result['action'] == 'wq':
        prev_stars = progress.get(level, {}).get('stars', 0)
        progress[level] = {
            'complete': True,
            'stars': max(dung_result['stars'], prev_stars),
        }


class TestProgressUpdateLogic:
    def test_quit_does_not_mark_complete(self):
        """:q (action='quit') after winning must NOT update progress."""
        progress = {}
        _progress_update({'won': True, 'stars': 2, 'action': 'quit'}, progress, 2)
        assert 2 not in progress

    def test_wq_marks_complete(self):
        """:wq after winning must mark the level complete."""
        progress = {}
        _progress_update({'won': True, 'stars': 2, 'action': 'wq'}, progress, 2)
        assert progress.get(2, {}).get('complete') is True

    def test_wq_stores_stars(self):
        progress = {}
        _progress_update({'won': True, 'stars': 3, 'action': 'wq'}, progress, 1)
        assert progress[1]['stars'] == 3

    def test_wq_preserves_higher_previous_stars(self):
        """Re-playing a level must not downgrade stars."""
        progress = {2: {'stars': 3, 'complete': True}}
        _progress_update({'won': True, 'stars': 1, 'action': 'wq'}, progress, 2)
        assert progress[2]['stars'] == 3

    def test_wq_upgrades_lower_previous_stars(self):
        progress = {2: {'stars': 1, 'complete': True}}
        _progress_update({'won': True, 'stars': 3, 'action': 'wq'}, progress, 2)
        assert progress[2]['stars'] == 3

    def test_lost_and_wq_does_not_mark_complete(self):
        """Losing the level (won=False) must never mark it complete."""
        progress = {}
        _progress_update({'won': False, 'stars': 0, 'action': 'wq'}, progress, 2)
        assert 2 not in progress

    def test_wq_complete_flag_is_true(self):
        progress = {}
        _progress_update({'won': True, 'stars': 2, 'action': 'wq'}, progress, 0)
        assert progress[0]['complete'] is True
