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

"""Tests for the overworld viewport scroll (render.overworld._scroll_offset).

The cling bug: the old formula recomputed the offset from the cursor every frame,
pinning the cursor to the bottom edge once scrolled. The fix keeps a stateful
offset and scrolls only when the cursor leaves the window.
"""
from render.overworld import _scroll_offset, build_lines, default_cursor


def _levels(n=3):
    return [{'id': i, 'key': f'dungeon_{i}', 'commands': ''} for i in range(n)]


# ── flat-line buffer model (comments selectable; cursor defaults to ../) ─────────

def test_build_lines_structure_and_default_cursor():
    lines = build_lines(_levels(3), [])
    assert [l['type'] for l in lines] == ['comment'] * 6 + ['parent', 'self', 'level', 'level', 'level']
    assert default_cursor(lines) == 6                       # the ../ line, after the 6 comments
    assert lines[default_cursor(lines)]['type'] == 'parent'


def test_build_lines_with_customs_marks_last():
    lines = build_lines(_levels(1), [{'layout_name': 'a'}, {'layout_name': 'b'}])
    assert [l['type'] for l in lines][-3:] == ['subhdr', 'custom', 'custom']
    assert lines[-1]['last'] is True and lines[-2]['last'] is False


def test_ow_section_jumps_between_sections():
    from main import _ow_section
    lines = build_lines(_levels(3), [{'layout_name': 'a'}])
    # sections start at 0 (comments), 6 (dirs ../), 8 (levels), 11 (custom subhdr)
    assert _ow_section(lines, 9, -1) == 8                   # up to the levels section top
    assert _ow_section(lines, 8, -1) == 6                   # then up to the dirs
    assert _ow_section(lines, 9, +1) == 11                  # down to the customs
    assert _ow_section(lines, 2, +1) == 6                   # from the comments, down to dirs


def test_no_scroll_when_cursor_fits_in_window():
    assert _scroll_offset(3, 0, 10, 30) == 0


def test_scrolls_down_only_at_the_bottom_edge():
    assert _scroll_offset(10, 0, 10, 30) == 1      # cursor one past the window → 10-10+1
    assert _scroll_offset(29, 0, 10, 30) == 20     # clamped to max_off (30-10)


def test_cursor_moves_up_within_window_without_clinging():
    # At the bottom (offset 20, window [20,30)), pressing k walks the cursor UP
    # inside the window — the offset must stay put, not drag down with it.
    off = 20
    for cur in (28, 27, 26, 25, 24, 23, 22, 21, 20):
        off = _scroll_offset(cur, off, 10, 30)
        assert off == 20, f"window clung at cursor {cur}: offset {off}"
    # only once the cursor reaches the window top does the view scroll up
    assert _scroll_offset(19, off, 10, 30) == 19


def test_clamps_to_bounds():
    assert _scroll_offset(0, 5, 10, 30) == 0       # never below 0
    assert _scroll_offset(100, 0, 10, 30) == 20    # never past max_off
    assert _scroll_offset(2, 0, 10, 3) == 0        # fewer entries than the window
