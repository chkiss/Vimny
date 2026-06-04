"""The Editor Operator — hammers the edit-mode d/y/c operator primitives.

Personality defined in agents/bug_testers.md. Exercises engine/editor.py's range
helpers directly (no Terminal): the cut/range/clear/snapshot paths behind dw, d$,
dd, yy, cw in :edit mode, plus the merge-after-cut and undo-restore invariants.
"""
import pytest
from engine.world import Room, RoomType, CellType, CharRun, Entity
from engine.player import Player
from engine.editor import (
    _ed_cut, _ed_range_items, _ed_delete_range, _ed_clear_row, _ed_row_items,
    _ed_snapshot, _ed_restore, _merge_adjacent_char_runs,
)


def _room(rows=5, cols=30):
    room = Room(room_type=RoomType.ENTRY, rows=rows, cols=cols)
    room.cells = [[CellType.FLOOR if (0 < r < rows - 1 and 0 < c < cols - 1) else CellType.WALL
                   for c in range(cols)] for r in range(rows)]
    room.rebuild_indexes()
    return room


def _run(room, r, c, text, kind='ancient'):
    room.add_char_run(CharRun(r, c, tuple(text), kind))
    return room.char_runs[-1]


def _row_text(room, r):
    """The non-void glyphs on row r as {col: sym}."""
    out = {}
    for ru in room._char_runs_by_row.get(r, []):
        for i, s in enumerate(ru.symbols):
            out[ru.col + i] = s
    return out


# ── yank reads, delete mutates ────────────────────────────────────────────────
def test_range_items_is_read_only():
    """_ed_range_items (the yank read) must NOT mutate the room."""
    room = _room()
    _run(room, 1, 2, 'abc')
    before = _row_text(room, 1)
    items = _ed_range_items(room, 1, 2, 1, 4)
    assert _row_text(room, 1) == before          # unchanged
    assert sum(len(i['rune'].symbols) for i in items if i['type'] == 'rune') == 3


def test_row_items_is_read_only():
    room = _room()
    _run(room, 1, 2, 'ab'); _run(room, 1, 6, 'cd')
    before = _row_text(room, 1)
    _ed_row_items(room, 1)
    assert _row_text(room, 1) == before


# ── dw / d$ : range delete captures and removes ───────────────────────────────
def test_delete_range_removes_and_returns_runes():
    """dw-style: _ed_delete_range returns the captured runes AND clears them."""
    room = _room()
    _run(room, 1, 2, 'foo'); _run(room, 1, 6, 'bar')
    items = _ed_delete_range(room, 1, 2, 1, 4)        # just 'foo'
    syms = ''.join(s for i in items if i['type'] == 'rune' for s in i['rune'].symbols)
    assert syms == 'foo'
    assert _row_text(room, 1) == {6: 'b', 7: 'a', 8: 'r'}   # only 'bar' remains


def test_delete_to_end_of_row():
    """d$ from the middle deletes everything to the line end on that row."""
    room = _room(cols=20)
    for i, ch in enumerate('abcdef'):
        _run(room, 1, 3 + i, ch)                     # single-glyph runs at cols 3-8
    _ed_delete_range(room, 1, 5, 1, room.cols - 1)   # from col 5 to the wall
    assert _row_text(room, 1) == {3: 'a', 4: 'b'}    # cols 5-8 (c,d,e,f) gone


def test_delete_range_is_keyed_on_run_start_column():
    """Known granularity edge: _ed_delete_range selects runs by their START column, so a
    multi-symbol run that starts BEFORE the range yet extends into it survives intact
    (range ops are coarser than _ed_cut, which splits mid-run)."""
    room = _room()
    _run(room, 1, 3, 'abcdef')                       # one run, cols 3-8
    items = _ed_delete_range(room, 1, 5, 1, room.cols - 1)   # range starts at col 5
    assert items == []                               # run starts at 3 (< 5) → not captured
    assert _row_text(room, 1) == {3: 'a', 4: 'b', 5: 'c', 6: 'd', 7: 'e', 8: 'f'}


def test_delete_range_does_not_touch_other_rows():
    room = _room()
    _run(room, 1, 2, 'aa'); _run(room, 2, 2, 'bb')
    _ed_delete_range(room, 1, 0, 1, 10)
    assert _row_text(room, 1) == {}
    assert _row_text(room, 2) == {2: 'b', 3: 'b'}


# ── dd : clear the whole row ──────────────────────────────────────────────────
def test_clear_row_removes_runes_and_entities():
    room = _room()
    _run(room, 1, 2, 'word')
    room.add_entity(Entity(kind='goblin', row=1, col=8, max_hp=1))
    _ed_clear_row(room, 1)
    assert _row_text(room, 1) == {}
    assert not any(e.row == 1 and e.alive for e in room.entities)


def test_clear_row_resets_exit_when_it_was_on_the_row():
    room = _room()
    room.add_entity(Entity(kind='exit', row=1, col=5))
    room.exit_pos = (1, 5)
    _ed_clear_row(room, 1)
    assert room.exit_pos is None


def test_delete_range_resets_exit_in_range():
    room = _room()
    room.add_entity(Entity(kind='exit', row=1, col=5))
    room.exit_pos = (1, 5)
    _ed_delete_range(room, 1, 0, 1, 10)
    assert room.exit_pos is None


# ── _ed_cut: single-symbol extraction splits a run ────────────────────────────
def test_cut_extracts_one_symbol_and_splits_the_run():
    """x-style cut takes ONLY the symbol under the cursor, leaving split remnants."""
    room = _room()
    _run(room, 1, 4, 'abcd')
    item = _ed_cut(room, 1, 5)                        # the 'b' (col 5)
    assert item['type'] == 'rune' and item['rune'].symbols == ('b',)
    assert _row_text(room, 1) == {4: 'a', 6: 'c', 7: 'd'}   # b gone, a | cd split


def test_cut_on_empty_floor_returns_none():
    room = _room()
    assert _ed_cut(room, 1, 5) is None


# ── merge after cuts ──────────────────────────────────────────────────────────
def test_merge_joins_adjacent_runs_but_not_across_a_gap():
    room = _room()
    room.add_char_run(CharRun(1, 2, ('a',), 'ancient'))
    room.add_char_run(CharRun(1, 3, ('b',), 'ancient'))    # adjacent → merges with 'a'
    room.add_char_run(CharRun(1, 6, ('x',), 'ancient'))    # gap at 4-5 → stays separate
    _merge_adjacent_char_runs(room, 1)
    runs = sorted(room._char_runs_by_row.get(1, []), key=lambda r: r.col)
    assert [(''.join(r.symbols), r.col) for r in runs] == [('ab', 2), ('x', 6)]


# ── undo via snapshot/restore (the ed_undo stack) ─────────────────────────────
def test_snapshot_restore_brings_back_a_deleted_range():
    room = _room()
    player = Player(row=1, col=2)
    _run(room, 1, 2, 'restore-me')
    snap = _ed_snapshot(room, player)                # the ed_undo entry
    _ed_delete_range(room, 1, 0, 1, 20)
    assert _row_text(room, 1) == {}
    _ed_restore(room, player, snap)                  # u
    assert ''.join(_row_text(room, 1)[c] for c in sorted(_row_text(room, 1))) == 'restore-me'


def test_snapshot_is_a_deep_copy_not_a_view():
    """Mutating the room after a snapshot must not corrupt the snapshot."""
    room = _room()
    player = Player(row=1, col=2)
    _run(room, 1, 2, 'xy')
    snap = _ed_snapshot(room, player)
    _ed_clear_row(room, 1)
    _run(room, 1, 2, 'ZZZZ')                          # further edits
    _ed_restore(room, player, snap)
    assert _row_text(room, 1) == {2: 'x', 3: 'y'}     # the original, intact
