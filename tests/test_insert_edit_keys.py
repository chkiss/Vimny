"""Blocks G + J — INSERT-mode editing keys.

Engine-level coverage for <C-w> (delete word back) and <C-u> (delete to line
start) via engine.insert, plus the clip→text flattening that backs <C-r>
register paste in main.py."""
from engine.world import Room, RoomType, CellType, CharRun
from engine.player import Player
from engine.insert import insert_delete_word_back, insert_delete_to_start
from main import _clip_to_text

ROWS, COLS = 7, 24


def _room():
    room = Room(room_type=RoomType.ENTRY, rows=ROWS, cols=COLS)
    room.cells = [
        [CellType.FLOOR if (0 < r < ROWS - 1 and 0 < c < COLS - 1) else CellType.WALL
         for c in range(COLS)]
        for r in range(ROWS)
    ]
    room.spawn_pos = (3, 1)
    room.rebuild_indexes()
    return room


def _word(room, row, col, text):
    room.add_char_run(CharRun(row, col, tuple(text), 'ancient'))
    room.rebuild_indexes()


def _row_text(room, row):
    cells = [' '] * COLS
    for ru in room.char_runs:
        if ru.row == row:
            for i, s in enumerate(ru.symbols):
                cells[ru.col + i] = s
    return ''.join(cells).strip()


# ── <C-w> delete word back ─────────────────────────────────────────────────
def test_ctrl_w_deletes_just_typed_word():
    room = _room()
    _word(room, 3, 1, 'hello')
    p = Player(row=3, col=6)                 # cursor just past 'hello'
    assert insert_delete_word_back(room, p) is True
    assert _row_text(room, 3) == ''
    assert p.col == 1

def test_ctrl_w_stops_at_previous_word():
    room = _room()
    _word(room, 3, 1, 'foo')                 # cols 1-3
    _word(room, 3, 5, 'bar')                 # cols 5-7 (a space gap at col 4)
    p = Player(row=3, col=8)                  # just past 'bar'
    insert_delete_word_back(room, p)
    assert _row_text(room, 3) == 'foo'        # only 'bar' (and the space cell) gone

def test_ctrl_w_at_line_start_noop():
    room = _room()
    p = Player(row=3, col=1)
    assert insert_delete_word_back(room, p) is False


# ── <C-u> delete to line start ─────────────────────────────────────────────
def test_ctrl_u_clears_to_start():
    room = _room()
    _word(room, 3, 1, 'abcdef')
    p = Player(row=3, col=7)
    assert insert_delete_to_start(room, p) is True
    assert _row_text(room, 3) == ''
    assert p.col == 1


# ── _clip_to_text (backs <C-r>) ────────────────────────────────────────────
def test_clip_to_text_charwise():
    clip = {'linewise': False, 'rows': [
        {'width': 3, 'char_runs': [{'dcol': 0, 'symbols': ('a', 'b', 'c'), 'kind': 'x'}]}]}
    assert _clip_to_text(clip) == 'abc'

def test_clip_to_text_with_gap():
    clip = {'linewise': False, 'rows': [
        {'width': 4, 'char_runs': [
            {'dcol': 0, 'symbols': ('a',), 'kind': 'x'},
            {'dcol': 2, 'symbols': ('b',), 'kind': 'x'}]}]}
    assert _clip_to_text(clip) == 'a b '            # gap at col 1 is a space

def test_clip_to_text_none():
    assert _clip_to_text(None) == ''
    assert _clip_to_text({'rows': []}) == ''
