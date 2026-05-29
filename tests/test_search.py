"""Tests for Block F search — engine/search.py: substring matching over clusters,
forward/backward with wraparound, match-column landing, word-under-cursor."""
import pytest
from engine.world import Room, RoomType, CellType, CharRun
from engine.player import Player
from engine.search import find_next, word_under_cursor, _match_positions

ROWS, COLS = 7, 24


def _room():
    room = Room(room_type=RoomType.ENTRY, rows=ROWS, cols=COLS)
    room.cells = [
        [CellType.FLOOR if (0 < r < ROWS - 1 and 0 < c < COLS - 1) else CellType.WALL
         for c in range(COLS)]
        for r in range(ROWS)
    ]
    room.rebuild_indexes()
    return room


def _p(row, col):
    return Player(row=row, col=col)


def _abab():
    """'ab'@(3,2), 'cd'@(3,8), 'ab'@(5,4)."""
    room = _room()
    room.add_char_run(CharRun(3, 2, ('a', 'b'), 'ancient'))
    room.add_char_run(CharRun(3, 8, ('c', 'd'), 'ancient'))
    room.add_char_run(CharRun(5, 4, ('a', 'b'), 'ancient'))
    return room


class TestFindNext:
    def test_forward_finds_next_in_reading_order(self):
        assert find_next(_abab(), _p(3, 2), 'ab', True) == (5, 4)

    def test_forward_wraps_to_first(self):
        assert find_next(_abab(), _p(5, 4), 'ab', True) == (3, 2)

    def test_backward(self):
        assert find_next(_abab(), _p(5, 4), 'ab', False) == (3, 2)

    def test_backward_wraps_to_last(self):
        assert find_next(_abab(), _p(3, 2), 'ab', False) == (5, 4)

    def test_substring_matches_within_cluster(self):
        room = _room()
        room.add_char_run(CharRun(3, 5, ('x', 'a', 'b'), 'ancient'))    # 'xab'
        # match column is the first matched char: 5 + 'xab'.find('ab') == 6
        assert find_next(room, _p(3, 0), 'ab', True) == (3, 6)

    def test_distinct_pattern(self):
        assert find_next(_abab(), _p(3, 0), 'cd', True) == (3, 8)

    def test_no_match_returns_none(self):
        assert find_next(_abab(), _p(3, 0), 'zz', True) is None

    def test_empty_pattern_returns_none(self):
        assert find_next(_abab(), _p(3, 0), '', True) is None

    def test_match_positions_sorted_reading_order(self):
        assert _match_positions(_abab(), 'ab') == [(3, 2), (5, 4)]


class TestWordUnderCursor:
    def test_word_from_cluster(self):
        room = _abab()
        assert word_under_cursor(room, _p(3, 2)) == 'ab'
        assert word_under_cursor(room, _p(3, 3)) == 'ab'    # mid-cluster

    def test_none_on_blank(self):
        assert word_under_cursor(_abab(), _p(3, 0)) is None
