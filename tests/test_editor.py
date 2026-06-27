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

"""Tests for engine/editor.py: snapshot/restore, cut/paste, merge, range ops."""
from engine.world import Room, RoomType, CellType, Entity, CharRun
from engine.player import Player
from engine.editor import (
    _merge_adjacent_char_runs,
    _ed_cut, _ed_snapshot, _ed_restore, _ed_subst,
    _ed_paste, _ed_clear_row,
    _ed_range_items, _ed_delete_range,
    _clip_desc, _serialize_room, _deserialize_room,
)

# ── Fixtures ──────────────────────────────────────────────────────────────────

ROWS, COLS = 7, 16

def _make_room():
    room = Room(room_type=RoomType.ENTRY, rows=ROWS, cols=COLS)
    room.cells = [
        [CellType.FLOOR if (0 < r < ROWS - 1 and 0 < c < COLS - 1) else CellType.WALL
         for c in range(COLS)]
        for r in range(ROWS)
    ]
    room.spawn_pos    = (3, 1)
    room.exit_pos = (3, 13)
    room.rebuild_indexes()
    return room


def _player(row=3, col=5):
    return Player(row=row, col=col)


# ── _merge_adjacent_char_runs ─────────────────────────────────────────────────────

class TestMergeAdjacentRunes:
    def test_merges_same_kind_adjacent(self):
        room = _make_room()
        room.add_char_run(CharRun(row=3, col=2, symbols=('∘',),    kind='ancient'))
        room.add_char_run(CharRun(row=3, col=3, symbols=('∘', '∘'), kind='ancient'))
        _merge_adjacent_char_runs(room, 3)
        assert len([ru for ru in room.char_runs if ru.row == 3]) == 1
        merged = room.char_run_at(3, 2)
        assert merged is not None
        assert merged.symbols == ('∘', '∘', '∘')
        assert merged.col == 2

    def test_does_not_merge_different_kinds(self):
        room = _make_room()
        room.add_char_run(CharRun(row=3, col=2, symbols=('∘',), kind='ancient'))
        room.add_char_run(CharRun(row=3, col=3, symbols=('·',), kind='verdant'))
        _merge_adjacent_char_runs(room, 3)
        assert len([ru for ru in room.char_runs if ru.row == 3]) == 2

    def test_does_not_merge_non_adjacent(self):
        room = _make_room()
        room.add_char_run(CharRun(row=3, col=2, symbols=('∘',), kind='ancient'))
        room.add_char_run(CharRun(row=3, col=4, symbols=('∘',), kind='ancient'))
        _merge_adjacent_char_runs(room, 3)
        assert len([ru for ru in room.char_runs if ru.row == 3]) == 2

    def test_index_is_updated_after_merge(self):
        room = _make_room()
        room.add_char_run(CharRun(row=3, col=2, symbols=('∘',),    kind='ancient'))
        room.add_char_run(CharRun(row=3, col=3, symbols=('∘',), kind='ancient'))
        _merge_adjacent_char_runs(room, 3)
        merged = room.char_run_at(3, 2)
        assert room.char_run_at(3, 3) is merged

    def test_only_touches_target_row(self):
        room = _make_room()
        ru_row2 = CharRun(row=2, col=2, symbols=('·',), kind='verdant')
        room.add_char_run(ru_row2)
        room.add_char_run(CharRun(row=3, col=2, symbols=('∘',), kind='ancient'))
        room.add_char_run(CharRun(row=3, col=3, symbols=('∘',), kind='ancient'))
        _merge_adjacent_char_runs(room, 3)
        assert room.char_run_at(2, 2) is ru_row2  # row 2 untouched


# ── _ed_cut ───────────────────────────────────────────────────────────────────

class TestEdCut:
    def test_cut_single_symbol_cluster(self):
        room = _make_room()
        ru = CharRun(row=3, col=5, symbols=('∘',), kind='ancient')
        room.add_char_run(ru)
        item = _ed_cut(room, 3, 5)
        assert item is not None
        assert item['type'] == 'rune'
        assert item['rune'].symbols == ('∘',)
        assert room.char_run_at(3, 5) is None

    def test_cut_first_symbol_of_cluster_splits(self):
        room = _make_room()
        room.add_char_run(CharRun(row=3, col=5, symbols=('∘', '∘', '∘'), kind='ancient'))
        item = _ed_cut(room, 3, 5)  # cut the leftmost ∘
        assert item['rune'].symbols == ('∘',)
        assert item['rune'].col == 5
        # Remaining: ∘∘ at col 6
        remnant = room.char_run_at(3, 6)
        assert remnant is not None
        assert remnant.symbols == ('∘', '∘')
        assert room.char_run_at(3, 5) is None

    def test_cut_middle_symbol_splits_into_two(self):
        room = _make_room()
        room.add_char_run(CharRun(row=3, col=5, symbols=('∘', '·', '∘'), kind='ancient'))
        item = _ed_cut(room, 3, 6)  # cut middle ·
        assert item['rune'].symbols == ('·',)
        left = room.char_run_at(3, 5)
        right = room.char_run_at(3, 7)
        assert left is not None and left.symbols == ('∘',)
        assert right is not None and right.symbols == ('∘',)

    def test_cut_last_symbol_leaves_prefix(self):
        room = _make_room()
        room.add_char_run(CharRun(row=3, col=5, symbols=('∘', '∘', '∘'), kind='ancient'))
        _ed_cut(room, 3, 7)  # cut rightmost
        prefix = room.char_run_at(3, 5)
        assert prefix is not None and prefix.symbols == ('∘', '∘')
        assert room.char_run_at(3, 7) is None

    def test_cut_entity(self):
        room = _make_room()
        e = Entity(kind='chest', row=3, col=5)
        room.add_entity(e)
        item = _ed_cut(room, 3, 5)
        assert item['type'] == 'entity'
        assert item['entity'] is e
        assert room.entity_at(3, 5) is None

    def test_cut_entity_exit_clears_exit_pos(self):
        room = _make_room()
        e = Entity(kind='exit', row=3, col=13)
        room.add_entity(e)
        room.exit_pos = (3, 13)
        _ed_cut(room, 3, 13)
        assert room.exit_pos is None

    def test_cut_wall_converts_to_floor(self):
        room = _make_room()
        assert room.cells[0][5] == CellType.WALL
        item = _ed_cut(room, 0, 5)
        assert item['type'] == 'cell'
        assert item['cell_type'] == CellType.WALL
        assert room.cells[0][5] == CellType.FLOOR

    def test_cut_water_returns_clip_and_leaves_floor(self):
        room = _make_room()
        room.cells[3][5] = CellType.WATER
        item = _ed_cut(room, 3, 5)
        assert item is not None
        assert item['type'] == 'cell'
        assert item['cell_type'] == CellType.WATER
        assert room.cells[3][5] == CellType.FLOOR

    def test_cut_empty_floor_returns_none(self):
        room = _make_room()
        item = _ed_cut(room, 3, 5)
        assert item is None


# ── _ed_snapshot / _ed_restore ────────────────────────────────────────────────

class TestEdSnapshotRestore:
    def test_snapshot_creates_independent_rune_list(self):
        room = _make_room()
        room.add_char_run(CharRun(row=3, col=5, symbols=('∘',), kind='ancient'))
        p = _player()
        snap = _ed_snapshot(room, p)
        room.char_runs.clear()
        assert len(snap['char_runs']) == 1  # snapshot unaffected

    def test_snapshot_creates_independent_entity_list(self):
        room = _make_room()
        room.add_entity(Entity(kind='chest', row=2, col=3))
        p = _player()
        snap = _ed_snapshot(room, p)
        room.entities.clear()
        assert len(snap['entities']) == 1

    def test_snapshot_creates_independent_cells(self):
        room = _make_room()
        p = _player()
        snap = _ed_snapshot(room, p)
        room.cells[3][5] = CellType.WALL
        assert snap['cells'][3][5] == CellType.FLOOR  # original was floor

    def test_snapshot_records_player_position(self):
        room = _make_room()
        p = Player(row=2, col=7)
        snap = _ed_snapshot(room, p)
        assert snap['pr'] == 2 and snap['pc'] == 7

    def test_restore_reverts_rune_changes(self):
        room = _make_room()
        ru = CharRun(row=3, col=5, symbols=('∘',), kind='ancient')
        room.add_char_run(ru)
        p = _player()
        snap = _ed_snapshot(room, p)
        room.remove_char_run(ru)
        assert room.char_run_at(3, 5) is None
        _ed_restore(room, p, snap)
        assert room.char_run_at(3, 5) is not None

    def test_restore_reverts_cell_changes(self):
        room = _make_room()
        p = _player()
        snap = _ed_snapshot(room, p)
        room.cells[3][5] = CellType.WALL
        _ed_restore(room, p, snap)
        assert room.cells[3][5] == CellType.FLOOR

    def test_restore_restores_player_position(self):
        room = _make_room()
        p = Player(row=2, col=7)
        snap = _ed_snapshot(room, p)
        p.row, p.col = 5, 1
        _ed_restore(room, p, snap)
        assert p.row == 2 and p.col == 7

    def test_restore_rebuilds_indexes(self):
        room = _make_room()
        ru = CharRun(row=3, col=5, symbols=('∘',), kind='ancient')
        room.add_char_run(ru)
        p = _player()
        snap = _ed_snapshot(room, p)
        room.char_runs.clear()
        room.rebuild_indexes()
        _ed_restore(room, p, snap)
        assert room.char_run_at(3, 5) is not None  # index rebuilt

    def test_snapshot_keeps_all_entity_fields(self):
        """An editor undo must not cripple entities: combat stats, AI, colour tag
        and edit-immunity all round-trip through snapshot/restore (clone_entity)."""
        room = _make_room()
        w = Entity(kind='warden', row=2, col=3, hp=5, max_hp=5, ai='chase',
                   ai_speed=2, tag='pathfinder', edit_immune=True, scroll_id='x')
        room.add_entity(w)
        p = _player()
        snap = _ed_snapshot(room, p)
        room.entities.clear()
        room.rebuild_indexes()
        _ed_restore(room, p, snap)
        r = room.entity_at(2, 3)
        assert (r.max_hp, r.ai, r.ai_speed, r.tag, r.edit_immune, r.scroll_id, r.uid) \
            == (5, 'chase', 2, 'pathfinder', True, 'x', w.uid)


# ── _ed_subst ─────────────────────────────────────────────────────────────────

class TestEdSubst:
    def test_floor_toggles_to_wall(self):
        room = _make_room()
        items = _ed_subst(room, 3, 5)
        assert room.cells[3][5] == CellType.WALL
        assert any(i['type'] == 'cell' and i['cell_type'] == CellType.FLOOR for i in items)

    def test_wall_subst_cycles_to_wood_wall(self):
        room = _make_room()
        items = _ed_subst(room, 0, 5)  # border cell is WALL
        assert room.cells[0][5] == CellType.WOOD_WALL
        cell_types = [i['cell_type'] for i in items if i['type'] == 'cell']
        assert CellType.WALL in cell_types

    def test_wood_wall_subst_cycles_to_water(self):
        room = _make_room()
        room.cells[3][5] = CellType.WOOD_WALL
        items = _ed_subst(room, 3, 5)
        assert room.cells[3][5] == CellType.WATER
        cell_types = [i['cell_type'] for i in items if i['type'] == 'cell']
        assert CellType.WOOD_WALL in cell_types

    def test_water_subst_cycles_to_floor(self):
        room = _make_room()
        room.cells[3][5] = CellType.WATER
        items = _ed_subst(room, 3, 5)
        assert room.cells[3][5] == CellType.FLOOR
        cell_types = [i['cell_type'] for i in items if i['type'] == 'cell']
        assert CellType.WATER in cell_types

    def test_rune_cut_included_in_items(self):
        room = _make_room()
        room.add_char_run(CharRun(row=3, col=5, symbols=('∘',), kind='ancient'))
        items = _ed_subst(room, 3, 5)
        rune_items = [i for i in items if i['type'] == 'rune']
        assert len(rune_items) == 1
        assert room.char_run_at(3, 5) is None


# ── _ed_paste ─────────────────────────────────────────────────────────────────

class TestEdPaste:
    def test_paste_rune(self):
        room = _make_room()
        items = [{'type': 'rune',
                  'rune': CharRun(row=0, col=0, symbols=('∘', '∘'), kind='ancient')}]
        _ed_paste(room, 3, 5, items)
        ru = room.char_run_at(3, 5)
        assert ru is not None
        assert ru.symbols == ('∘', '∘')

    def test_paste_entity(self):
        room = _make_room()
        src = Entity(kind='chest', row=0, col=0)
        items = [{'type': 'entity', 'entity': src}]
        _ed_paste(room, 3, 7, items)
        e = room.entity_at(3, 7)
        assert e is not None
        assert e.kind == 'chest'

    def test_paste_entity_keeps_combat_fields_with_fresh_uid(self):
        room = _make_room()
        src = Entity(kind='goblin', row=0, col=0, hp=1, max_hp=1, ai='chase',
                     ai_speed=2, tag='echo')
        _ed_paste(room, 3, 7, [{'type': 'entity', 'entity': src}])
        e = room.entity_at(3, 7)
        assert (e.max_hp, e.ai, e.ai_speed, e.tag) == (1, 'chase', 2, 'echo')
        assert e.uid != src.uid                   # a paste is a NEW creature

    def test_paste_exit_entity_updates_exit_pos(self):
        room = _make_room()
        room.exit_pos = None
        src = Entity(kind='exit', row=0, col=0)
        items = [{'type': 'entity', 'entity': src}]
        _ed_paste(room, 3, 8, items)
        assert room.exit_pos == (3, 8)

    def test_paste_cell_type(self):
        room = _make_room()
        items = [{'type': 'cell', 'cell_type': CellType.WALL}]
        _ed_paste(room, 3, 5, items)
        assert room.cells[3][5] == CellType.WALL

    def test_paste_water_cell_type(self):
        room = _make_room()
        items = [{'type': 'cell', 'cell_type': CellType.WATER}]
        _ed_paste(room, 3, 5, items)
        assert room.cells[3][5] == CellType.WATER

    def test_paste_merges_adjacent_runes(self):
        room = _make_room()
        room.add_char_run(CharRun(row=3, col=5, symbols=('∘',), kind='ancient'))
        # Paste another ancient at col 4 — adjacent on left
        items = [{'type': 'rune',
                  'rune': CharRun(row=0, col=0, symbols=('∘',), kind='ancient')}]
        _ed_paste(room, 3, 4, items)
        merged = room.char_run_at(3, 4)
        assert merged is not None
        assert merged.symbols == ('∘', '∘')  # merged into one cluster

    def test_paste_stops_at_room_boundary(self):
        room = _make_room()
        items = [{'type': 'rune',
                  'rune': CharRun(row=0, col=0, symbols=('∘', '∘', '∘'), kind='ancient')}]
        _ed_paste(room, 3, COLS - 2, items)  # barely fits 0 symbols
        # Should not raise, even if cols is exhausted


# ── _ed_clear_row ─────────────────────────────────────────────────────────────

class TestEdClearRow:
    def test_removes_all_runes_from_row(self):
        room = _make_room()
        room.add_char_run(CharRun(row=3, col=3, symbols=('∘', '∘'), kind='ancient'))
        room.add_char_run(CharRun(row=3, col=7, symbols=('·',),      kind='verdant'))
        _ed_clear_row(room, 3)
        assert all(ru.row != 3 for ru in room.char_runs)
        assert room.char_run_at(3, 3) is None

    def test_removes_alive_entities_from_row(self):
        room = _make_room()
        room.add_entity(Entity(kind='chest', row=3, col=5))
        _ed_clear_row(room, 3)
        assert room.entity_at(3, 5) is None

    def test_does_not_touch_other_rows(self):
        room = _make_room()
        ru2 = CharRun(row=2, col=3, symbols=('∘',), kind='ancient')
        room.add_char_run(ru2)
        room.add_char_run(CharRun(row=3, col=5, symbols=('·',), kind='verdant'))
        _ed_clear_row(room, 3)
        assert room.char_run_at(2, 3) is ru2

    def test_clears_exit_pos_when_exit_entity_on_row(self):
        room = _make_room()
        room.add_entity(Entity(kind='exit', row=3, col=13))
        room.exit_pos = (3, 13)
        _ed_clear_row(room, 3)
        assert room.exit_pos is None


# ── _ed_range_items / _ed_delete_range ───────────────────────────────────────

class TestEdRangeOps:
    def test_range_items_single_row(self):
        room = _make_room()
        room.add_char_run(CharRun(row=3, col=4, symbols=('∘',), kind='ancient'))
        room.add_char_run(CharRun(row=3, col=8, symbols=('·',), kind='verdant'))
        items = _ed_range_items(room, 3, 3, 3, 10)
        rune_cols = {i['rune'].col for i in items if i['type'] == 'rune'}
        assert 4 in rune_cols and 8 in rune_cols

    def test_range_items_excludes_outside_range(self):
        room = _make_room()
        room.add_char_run(CharRun(row=3, col=2,  symbols=('∘',), kind='ancient'))
        room.add_char_run(CharRun(row=3, col=12, symbols=('·',), kind='verdant'))
        items = _ed_range_items(room, 3, 4, 3, 10)
        assert all(i['rune'].col not in (2, 12) for i in items if i['type'] == 'rune')

    def test_delete_range_removes_runes_and_returns_them(self):
        room = _make_room()
        room.add_char_run(CharRun(row=3, col=5, symbols=('∘',), kind='ancient'))
        items = _ed_delete_range(room, 3, 4, 3, 7)
        assert any(i['type'] == 'rune' for i in items)
        assert room.char_run_at(3, 5) is None

    def test_delete_range_multi_row(self):
        room = _make_room()
        room.add_char_run(CharRun(row=2, col=5, symbols=('∘',), kind='ancient'))
        room.add_char_run(CharRun(row=4, col=5, symbols=('·',), kind='verdant'))
        items = _ed_delete_range(room, 2, 1, 4, 10)
        rune_rows = {i['rune'].row for i in items if i['type'] == 'rune'}
        assert 2 in rune_rows and 4 in rune_rows
        assert room.char_run_at(2, 5) is None
        assert room.char_run_at(4, 5) is None


# ── _clip_desc ────────────────────────────────────────────────────────────────

class TestClipDesc:
    def test_rune_item(self):
        item = {'type': 'rune', 'rune': CharRun(row=0, col=0, symbols=('∘',), kind='ancient')}
        assert _clip_desc(item) == 'ancient rune'

    def test_entity_item(self):
        item = {'type': 'entity', 'entity': Entity(kind='chest', row=0, col=0)}
        assert _clip_desc(item) == 'chest'

    def test_wall_cell_item(self):
        item = {'type': 'cell', 'cell_type': CellType.WALL}
        assert _clip_desc(item) == 'wall'

    def test_floor_cell_item(self):
        item = {'type': 'cell', 'cell_type': CellType.FLOOR}
        assert _clip_desc(item) == 'floor'

    def test_water_cell_item(self):
        item = {'type': 'cell', 'cell_type': CellType.WATER}
        assert _clip_desc(item) == 'water'


# ── _serialize_room ───────────────────────────────────────────────────────────

class TestSerializeRoom:
    def test_basic_structure(self):
        room = _make_room()
        d = _serialize_room(room)
        assert d['rows'] == ROWS
        assert d['cols'] == COLS
        assert len(d['cells']) == ROWS
        assert len(d['cells'][0]) == COLS

    def test_wall_serialized_as_W(self):
        room = _make_room()
        d = _serialize_room(room)
        assert d['cells'][0][0] == 'W'

    def test_floor_serialized_as_F(self):
        room = _make_room()
        d = _serialize_room(room)
        assert d['cells'][3][5] == 'F'

    def test_water_serialized_as_A(self):
        room = _make_room()
        room.cells[3][5] = CellType.WATER
        d = _serialize_room(room)
        assert d['cells'][3][5] == 'A'

    def test_runes_included(self):
        room = _make_room()
        room.add_char_run(CharRun(row=3, col=5, symbols=('∘', '∘'), kind='ancient'))
        d = _serialize_room(room)
        assert len(d['char_runs']) == 1
        assert d['char_runs'][0] == {'row': 3, 'col': 5, 'symbols': ['∘', '∘'], 'kind': 'ancient'}

    def test_char_runs_round_trip_through_deserialize(self):
        room = _make_room()
        room.add_char_run(CharRun(row=3, col=5, symbols=('∘', '∘'), kind='ancient'))
        back = _deserialize_room(_serialize_room(room))
        ru = back.char_run_at(3, 5)
        assert ru is not None and ru.symbols == ('∘', '∘') and ru.kind == 'ancient'

    def test_dead_entities_excluded(self):
        room = _make_room()
        alive = Entity(kind='chest', row=2, col=3)
        dead  = Entity(kind='door',  row=4, col=7, alive=False)
        room.add_entity(alive)
        room.entities.append(dead)
        d = _serialize_room(room)
        assert len(d['entities']) == 1
        assert d['entities'][0]['kind'] == 'chest'

    def test_entry_and_exit_pos(self):
        room = _make_room()
        d = _serialize_room(room)
        assert d['spawn_pos']    == [3, 1]
        assert d['exit_pos'] == [3, 13]

    def test_no_exit_pos_is_none(self):
        room = _make_room()
        room.exit_pos = None
        d = _serialize_room(room)
        assert d['exit_pos'] is None
