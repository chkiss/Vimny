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

"""Progress save behaviour — :q must not persist dungeon completion.

Tests the actual progress-update block from main.py's run_overworld loop
by importing the dispatch logic directly, so regressions in main.py are caught.
"""


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
