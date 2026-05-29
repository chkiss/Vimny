"""Tests for Block K — resolve_text_object: word, brackets (nesting), quotes,
angle, paragraph, and sentence objects over the 2D grid. Tags (it/at) deferred."""
import pytest
from engine.world import Room, RoomType, CellType, CharRun
from engine.player import Player
from engine.text_object import resolve_text_object, TextObjectType

ROWS, COLS = 7, 28


def _room():
    room = Room(room_type=RoomType.ENTRY, rows=ROWS, cols=COLS)
    room.cells = [
        [CellType.FLOOR if (0 < r < ROWS - 1 and 0 < c < COLS - 1) else CellType.WALL
         for c in range(COLS)]
        for r in range(ROWS)
    ]
    room.spawn_pos = (1, 1)
    room.rebuild_indexes()
    return room


def _p(row, col):
    return Player(row=row, col=col)


def _span(t):
    return (t.start_row, t.start_col, t.end_row, t.end_col)


def _chars(room, row, start, syms, kind='ancient'):
    """Place each char of `syms` as its own column starting at `start`."""
    for i, ch in enumerate(syms):
        room.add_char_run(CharRun(row, start + i, (ch,), kind))


# ── word ──────────────────────────────────────────────────────────────────────

class TestWord:
    def _r(self):
        room = _room()
        room.add_char_run(CharRun(3, 2, ('a', 'b', 'c'), 'ancient'))   # cols 2-4
        room.add_char_run(CharRun(3, 7, ('d', 'e', 'f'), 'ancient'))   # cols 7-9
        return room

    def test_iw_from_mid_word(self):
        t = resolve_text_object('iw', self._r(), _p(3, 3))
        assert t.type is TextObjectType.INCLUSIVE
        assert _span(t) == (3, 2, 3, 4)

    def test_iw_position_independent(self):
        room = self._r()
        for c in (2, 3, 4):
            assert _span(resolve_text_object('iw', room, _p(3, c))) == (3, 2, 3, 4)

    def test_aw_includes_trailing_gap(self):
        t = resolve_text_object('aw', self._r(), _p(3, 2))
        assert _span(t) == (3, 2, 3, 6)        # word 2-4 + gap 5-6 (before next word)


# ── brackets (with nesting + aliases) ───────────────────────────────────────────

class TestBrackets:
    def _r(self):
        room = _room()
        for col, ch in ((2, '('), (4, 'a'), (5, 'b'), (7, ')')):
            room.add_char_run(CharRun(3, col, (ch,), 'ancient'))
        return room

    def test_i_paren_inner(self):
        t = resolve_text_object('i(', self._r(), _p(3, 4))
        assert _span(t) == (3, 3, 3, 6)        # open+1 .. close-1

    def test_a_paren_around(self):
        t = resolve_text_object('a(', self._r(), _p(3, 4))
        assert _span(t) == (3, 2, 3, 7)

    def test_i_paren_from_on_open_bracket(self):
        t = resolve_text_object('i(', self._r(), _p(3, 2))
        assert _span(t) == (3, 3, 3, 6)

    def test_nesting_innermost(self):
        room = _room()
        for col, ch in ((2, '('), (4, '('), (6, ')'), (8, ')')):
            room.add_char_run(CharRun(3, col, (ch,), 'ancient'))
        # cursor inside inner pair (col 5) → innermost
        assert _span(resolve_text_object('a(', room, _p(3, 5))) == (3, 4, 3, 6)
        # cursor between outer open and inner open (col 3) → outer pair
        assert _span(resolve_text_object('a(', room, _p(3, 3))) == (3, 2, 3, 8)

    def test_empty_pair_inner_is_none(self):
        room = _room()
        room.add_char_run(CharRun(3, 4, ('(',), 'ancient'))
        room.add_char_run(CharRun(3, 5, (')',), 'ancient'))
        assert resolve_text_object('i(', room, _p(3, 4)) is None

    def test_brace_and_bracket(self):
        room = _room()
        for col, ch in ((2, '{'), (4, 'x'), (6, '}')):
            room.add_char_run(CharRun(3, col, (ch,), 'ancient'))
        assert _span(resolve_text_object('i{', room, _p(3, 4))) == (3, 3, 3, 5)


# ── quotes ──────────────────────────────────────────────────────────────────────

class TestQuotes:
    def _r(self):
        room = _room()
        # "ab"   "cd"   → quotes at 2,5 and 8,11
        for col, ch in ((2, '"'), (3, 'a'), (4, 'b'), (5, '"'),
                        (8, '"'), (9, 'c'), (10, 'd'), (11, '"')):
            room.add_char_run(CharRun(3, col, (ch,), 'ancient'))
        return room

    def test_inner_quote(self):
        assert _span(resolve_text_object('i"', self._r(), _p(3, 3))) == (3, 3, 3, 4)

    def test_around_quote(self):
        assert _span(resolve_text_object('a"', self._r(), _p(3, 3))) == (3, 2, 3, 5)

    def test_cursor_before_selects_next_pair(self):
        # cursor at col 6 (between the two strings) → next pair (8-11)
        assert _span(resolve_text_object('i"', self._r(), _p(3, 6))) == (3, 9, 3, 10)

    def test_single_quote_object(self):
        room = _room()
        for col, ch in ((2, "'"), (3, 'x'), (4, "'")):
            room.add_char_run(CharRun(3, col, (ch,), 'ancient'))
        assert _span(resolve_text_object("i'", room, _p(3, 3))) == (3, 3, 3, 3)


# ── angle ────────────────────────────────────────────────────────────────────

def test_angle_object():
    room = _room()
    for col, ch in ((2, '<'), (3, 't'), (4, 'g'), (5, '>')):
        room.add_char_run(CharRun(3, col, (ch,), 'ancient'))
    assert _span(resolve_text_object('i<', room, _p(3, 3))) == (3, 3, 3, 4)
    assert _span(resolve_text_object('a<', room, _p(3, 3))) == (3, 2, 3, 5)


# ── paragraph (linewise) ──────────────────────────────────────────────────────

class TestParagraph:
    def _r(self):
        room = _room()
        room.add_char_run(CharRun(1, 2, ('a',), 'ancient'))
        room.add_char_run(CharRun(2, 2, ('b',), 'ancient'))
        # row 3 blank
        room.add_char_run(CharRun(4, 2, ('c',), 'ancient'))
        return room

    def test_ip_inner_block(self):
        t = resolve_text_object('ip', self._r(), _p(1, 5))
        assert t.type is TextObjectType.LINEWISE
        assert (t.start_row, t.end_row) == (1, 2)

    def test_ap_includes_trailing_blank(self):
        t = resolve_text_object('ap', self._r(), _p(1, 5))
        assert (t.start_row, t.end_row) == (1, 3)

    def test_ip_single_row_block(self):
        t = resolve_text_object('ip', self._r(), _p(4, 5))
        assert (t.start_row, t.end_row) == (4, 4)


# ── sentence ───────────────────────────────────────────────────────────────────

class TestSentence:
    def _r(self):
        room = _room()
        _chars(room, 3, 2, 'ab.')      # cols 2-4, sentence 1
        _chars(room, 3, 6, 'cd!')      # cols 6-8, sentence 2
        return room

    def test_is_inner_sentence(self):
        # cursor in sentence 1; inner trims the trailing gap
        assert _span(resolve_text_object('is', self._r(), _p(3, 3))) == (3, 2, 3, 4)

    def test_as_includes_trailing_space(self):
        assert _span(resolve_text_object('as', self._r(), _p(3, 3))) == (3, 2, 3, 5)

    def test_second_sentence(self):
        assert _span(resolve_text_object('is', self._r(), _p(3, 7))) == (3, 6, 3, 8)


# ── deferred: tags return None ─────────────────────────────────────────────────

def test_tag_object_deferred():
    room = _room()
    _chars(room, 3, 2, '<a>x</a>')
    assert resolve_text_object('it', room, _p(3, 4)) is None
