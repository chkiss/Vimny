"""Phase 2: spatial index correctness — entity_at / rune_at and all mutation helpers."""
import pytest
from engine.world import Room, RoomType, CellType, Entity, RuneCluster


def _make_room(rows=7, cols=16):
    room = Room(room_type=RoomType.ENTRY, rows=rows, cols=cols)
    room.cells = [
        [CellType.FLOOR if (0 < r < rows - 1 and 0 < c < cols - 1) else CellType.WALL
         for c in range(cols)]
        for r in range(rows)
    ]
    room.gg_pos    = (3, 1)
    room.exit_pos = (3, 13)
    room.rebuild_indexes()
    return room


# ── entity_at ────────────────────────────────────────────────────────────────

class TestEntityAt:
    def test_hit(self):
        room = _make_room()
        e = Entity(kind='chest', row=2, col=5)
        room.add_entity(e)
        assert room.entity_at(2, 5) is e

    def test_miss_empty_cell(self):
        room = _make_room()
        assert room.entity_at(2, 5) is None

    def test_dead_entity_excluded_by_rebuild(self):
        room = _make_room()
        e = Entity(kind='chest', row=2, col=5, alive=False)
        room.entities.append(e)
        room.rebuild_indexes()
        assert room.entity_at(2, 5) is None

    def test_dead_entity_not_added_by_add_entity(self):
        room = _make_room()
        e = Entity(kind='chest', row=2, col=5, alive=False)
        room.add_entity(e)
        assert room.entity_at(2, 5) is None

    def test_two_entities_different_cells(self):
        room = _make_room()
        e1 = Entity(kind='chest', row=2, col=3)
        e2 = Entity(kind='exit',  row=3, col=9)
        room.add_entity(e1)
        room.add_entity(e2)
        assert room.entity_at(2, 3) is e1
        assert room.entity_at(3, 9) is e2


# ── entity mutation helpers ───────────────────────────────────────────────────

class TestEntityMutationHelpers:
    def test_add_entity_indexes_immediately(self):
        room = _make_room()
        e = Entity(kind='door', row=1, col=7)
        room.add_entity(e)
        assert room.entity_at(1, 7) is e
        assert e in room.entities

    def test_remove_entity_clears_index(self):
        room = _make_room()
        e = Entity(kind='chest', row=2, col=5)
        room.add_entity(e)
        room.remove_entity(e)
        assert room.entity_at(2, 5) is None
        assert e not in room.entities

    def test_kill_entity_clears_index_and_sets_alive_false(self):
        room = _make_room()
        e = Entity(kind='chest', row=2, col=5)
        room.add_entity(e)
        room.kill_entity(e)
        assert room.entity_at(2, 5) is None
        assert e.alive is False
        assert e in room.entities  # stays in list, just dead

    def test_move_entity_updates_both_keys(self):
        room = _make_room()
        e = Entity(kind='wanderer', row=2, col=2)
        room.add_entity(e)
        room.move_entity(e, 4, 8)
        assert room.entity_at(2, 2) is None
        assert room.entity_at(4, 8) is e
        assert e.row == 4 and e.col == 8

    def test_rebuild_indexes_picks_up_direct_list_mutation(self):
        room = _make_room()
        e = Entity(kind='exit', row=3, col=13)
        room.entities.append(e)          # bypass add_entity
        assert room.entity_at(3, 13) is None  # not in index yet
        room.rebuild_indexes()
        assert room.entity_at(3, 13) is e


# ── rune_at ───────────────────────────────────────────────────────────────────

class TestRuneAt:
    def test_hit_first_column(self):
        room = _make_room()
        ru = RuneCluster(row=3, col=4, symbols=('∘', '∘', '∘'), kind='ancient')
        room.add_rune(ru)
        assert room.rune_at(3, 4) is ru

    def test_hit_middle_column(self):
        room = _make_room()
        ru = RuneCluster(row=3, col=4, symbols=('∘', '∘', '∘'), kind='ancient')
        room.add_rune(ru)
        assert room.rune_at(3, 5) is ru

    def test_hit_last_column(self):
        room = _make_room()
        ru = RuneCluster(row=3, col=4, symbols=('∘', '∘', '∘'), kind='ancient')
        room.add_rune(ru)
        assert room.rune_at(3, 6) is ru

    def test_miss_before_cluster(self):
        room = _make_room()
        ru = RuneCluster(row=3, col=4, symbols=('∘', '∘'), kind='ancient')
        room.add_rune(ru)
        assert room.rune_at(3, 3) is None

    def test_miss_after_cluster(self):
        room = _make_room()
        ru = RuneCluster(row=3, col=4, symbols=('∘', '∘'), kind='ancient')
        room.add_rune(ru)
        assert room.rune_at(3, 6) is None

    def test_miss_different_row(self):
        room = _make_room()
        ru = RuneCluster(row=3, col=4, symbols=('∘',), kind='ancient')
        room.add_rune(ru)
        assert room.rune_at(2, 4) is None

    def test_single_symbol_cluster(self):
        room = _make_room()
        ru = RuneCluster(row=2, col=7, symbols=('·',), kind='verdant')
        room.add_rune(ru)
        assert room.rune_at(2, 7) is ru
        assert room.rune_at(2, 8) is None


# ── rune mutation helpers ─────────────────────────────────────────────────────

class TestRuneMutationHelpers:
    def test_add_rune_indexes_all_columns(self):
        room = _make_room()
        ru = RuneCluster(row=2, col=3, symbols=('·', '·', '·', '·'), kind='verdant')
        room.add_rune(ru)
        for c in range(3, 7):
            assert room.rune_at(2, c) is ru

    def test_remove_rune_clears_all_columns(self):
        room = _make_room()
        ru = RuneCluster(row=2, col=3, symbols=('∘', '∘'), kind='ancient')
        room.add_rune(ru)
        room.remove_rune(ru)
        assert room.rune_at(2, 3) is None
        assert room.rune_at(2, 4) is None
        assert ru not in room.runes

    def test_rebuild_reindexes_multi_symbol(self):
        room = _make_room()
        ru = RuneCluster(row=1, col=2, symbols=('∘', '∘', '∘'), kind='ancient')
        room.runes.append(ru)            # bypass add_rune
        assert room.rune_at(1, 3) is None  # not in index
        room.rebuild_indexes()
        assert room.rune_at(1, 3) is ru

    def test_two_runes_adjacent_different_rows(self):
        room = _make_room()
        ru1 = RuneCluster(row=2, col=5, symbols=('·',), kind='verdant')
        ru2 = RuneCluster(row=3, col=5, symbols=('∘',), kind='ancient')
        room.add_rune(ru1)
        room.add_rune(ru2)
        assert room.rune_at(2, 5) is ru1
        assert room.rune_at(3, 5) is ru2
