"""Tests for the overworld viewport scroll (render.overworld._scroll_offset).

The cling bug: the old formula recomputed the offset from the cursor every frame,
pinning the cursor to the bottom edge once scrolled. The fix keeps a stateful
offset and scrolls only when the cursor leaves the window.
"""
from render.overworld import _scroll_offset


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
