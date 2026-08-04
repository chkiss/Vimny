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

"""The Undo Abuser — spams u and Ctrl-R constantly.

Personality defined in agents/bug_testers.md.
"""
from vimny.engine.world import Room, RoomType, CellType, Entity
from vimny.engine.player import Player
from vimny.engine.budget import Budget
from main import _pop_history_step, _snapshot


def _bare_room(rows=7, cols=30):
    room = Room(room_type=RoomType.ENTRY, rows=rows, cols=cols)
    room.cells = [
        [CellType.FLOOR if (0 < r < rows - 1 and 0 < c < cols - 1) else CellType.WALL
         for c in range(cols)]
        for r in range(rows)
    ]
    room.spawn_pos    = (3, 1)
    room.exit_pos = (3, 28)
    room.fog_cells = set()
    room.rebuild_indexes()
    return room


def _budget(total=50, spent=0):
    b = Budget(total)
    b.spent = spent
    return b


# ── 1. Undo simple movement restores position ─────────────────────────────────

def test_undo_movement_restores_position():
    room = _bare_room()
    player = Player(row=3, col=5)
    budget = _budget(spent=1)
    undo_stack = [(3, 1, 0)]
    redo_stack = []

    result = _pop_history_step(undo_stack, redo_stack, room, player, budget)

    assert result is True
    assert player.row == 3
    assert player.col == 1
    assert budget.spent == 0


# ── 2. Undo on empty stack returns False ──────────────────────────────────────

def test_undo_empty_stack_returns_false():
    room = _bare_room()
    player = Player(row=3, col=5)
    budget = _budget(spent=2)

    result = _pop_history_step([], [], room, player, budget)

    assert result is False
    assert player.col == 5
    assert budget.spent == 2


# ── 3. Undo dict snapshot restores entities ──────────────────────────────────

def test_undo_dict_snapshot_restores_entities():
    room = _bare_room()
    goblin = Entity(kind='goblin', row=3, col=10, hp=1, max_hp=1, ai='chase')
    room.add_entity(goblin)

    player = Player(row=3, col=5)
    budget = _budget(spent=0)
    snap = _snapshot(room, player, budget)

    room.kill_entity(goblin)
    budget.spent = 1
    assert room.entity_at(3, 10) is None

    undo_stack = [snap]
    redo_stack = []
    result = _pop_history_step(undo_stack, redo_stack, room, player, budget)

    assert result is True
    restored = room.entity_at(3, 10)
    assert restored is not None, "goblin must be alive again after undo"
    assert restored.alive
    assert restored.kind == 'goblin'


# ── 4. Undo dict snapshot restores fog_cells ─────────────────────────────────

def test_undo_dict_snapshot_restores_fog_cells():
    room = _bare_room()
    room.fog_cells = {(3, 10), (3, 11)}

    player = Player(row=3, col=5)
    budget = _budget(spent=0)
    snap = _snapshot(room, player, budget)

    room.fog_cells = set()
    player.col = 10
    budget.spent = 1

    undo_stack = [snap]
    redo_stack = []
    _pop_history_step(undo_stack, redo_stack, room, player, budget)

    assert room.fog_cells == {(3, 10), (3, 11)}, (
        "fog_cells must be restored to the snapshot value after undo"
    )


# ── 5. Undo pushes inverse onto redo_stack (tuple) ───────────────────────────

def test_undo_tuple_pushes_to_redo_stack():
    """The pre-undo position must be pushed as a tuple onto redo_stack."""
    room = _bare_room()
    player = Player(row=3, col=8)
    budget = _budget(spent=3)
    undo_stack = [(3, 1, 0)]
    redo_stack = []

    _pop_history_step(undo_stack, redo_stack, room, player, budget)

    assert len(redo_stack) == 1
    item = redo_stack[0]
    assert isinstance(item, tuple)
    assert item[:3] == (3, 8, 3) and len(item) == 5


# ── 6. Undo pushes inverse onto redo_stack (dict) ────────────────────────────

def test_undo_dict_pushes_dict_to_redo_stack():
    room = _bare_room()
    goblin = Entity(kind='goblin', row=3, col=10, hp=1, max_hp=1, ai='chase')
    room.add_entity(goblin)

    player = Player(row=3, col=5)
    budget = _budget(spent=0)
    snap = _snapshot(room, player, budget)

    room.kill_entity(goblin)
    player.col = 10
    budget.spent = 1

    undo_stack = [snap]
    redo_stack = []
    _pop_history_step(undo_stack, redo_stack, room, player, budget)

    assert len(redo_stack) == 1
    item = redo_stack[0]
    assert isinstance(item, dict), "undo of a dict entry must push a dict onto redo_stack"
    assert {'row', 'col', 'spent', 'entities', 'fog_cells'} <= item.keys()


# ── 7. Redo after undo returns to post-action state ──────────────────────────

def test_redo_after_undo_restores_post_action_state():
    room = _bare_room()
    player = Player(row=3, col=5)
    budget = _budget(spent=2)
    undo_stack = [(3, 1, 0)]
    redo_stack = []

    _pop_history_step(undo_stack, redo_stack, room, player, budget)
    assert player.col == 1

    _pop_history_step(redo_stack, undo_stack, room, player, budget)

    assert player.row == 3
    assert player.col == 5
    assert budget.spent == 2


# ── 8. count=3 undo pops three entries ───────────────────────────────────────

def test_undo_count_3_pops_three_entries():
    room = _bare_room()
    player = Player(row=3, col=4)
    budget = _budget(spent=3)
    undo_stack = [(3, 1, 0), (3, 2, 1), (3, 3, 2)]
    redo_stack = []

    results = [
        _pop_history_step(undo_stack, redo_stack, room, player, budget)
        for _ in range(3)
    ]

    assert all(results), "all three undo steps should succeed"
    assert undo_stack == []
    assert len(redo_stack) == 3


# ── 9. count > stack length stops at empty ───────────────────────────────────

def test_undo_count_exceeds_stack_stops_at_empty():
    room = _bare_room()
    player = Player(row=3, col=3)
    budget = _budget(spent=2)
    undo_stack = [(3, 1, 0), (3, 2, 1)]
    redo_stack = []

    results = [
        _pop_history_step(undo_stack, redo_stack, room, player, budget)
        for _ in range(5)
    ]

    assert results[0] is True
    assert results[1] is True
    assert results[2] is False
    assert results[3] is False
    assert results[4] is False
    assert undo_stack == []


# ── 10. _snapshot copies entity state (no shared reference) ──────────────────

def test_snapshot_copies_entity_state():
    room = _bare_room()
    goblin = Entity(kind='goblin', row=3, col=5, hp=1, max_hp=1, ai='chase')
    room.add_entity(goblin)

    player = Player(row=3, col=1)
    budget = _budget(spent=0)
    snap = _snapshot(room, player, budget)

    goblin.alive = False
    goblin.hp = 0
    room.kill_entity(goblin)

    snap_goblin = next((e for e in snap['entities'] if e.kind == 'goblin'), None)
    assert snap_goblin is not None
    assert snap_goblin.alive is True, (
        "_snapshot must copy entity objects, not keep live references"
    )
    assert snap_goblin.hp == 1


# ── 11. _snapshot copies fog_cells ───────────────────────────────────────────

def test_snapshot_copies_fog_cells():
    room = _bare_room()
    room.fog_cells = {(3, 10)}

    player = Player(row=3, col=5)
    budget = _budget(spent=0)
    snap = _snapshot(room, player, budget)

    room.fog_cells.clear()
    room.fog_cells.add((3, 20))

    assert (3, 10) in snap['fog_cells'], "_snapshot must store a copy of fog_cells"
    assert (3, 20) not in snap['fog_cells'], "post-snapshot changes must not leak in"


# ── 12. Full round-trip: kill → undo → goblin alive ──────────────────────────

def test_undo_restores_killed_entity():
    room = _bare_room()
    goblin = Entity(kind='goblin', row=3, col=15, hp=2, max_hp=2, ai='chase')
    room.add_entity(goblin)

    player = Player(row=3, col=14)
    budget = _budget(spent=0)
    snap = _snapshot(room, player, budget)

    room.kill_entity(goblin)
    player.col = 15
    budget.spent = 1

    assert goblin.alive is False

    undo_stack = [snap]
    redo_stack = []
    _pop_history_step(undo_stack, redo_stack, room, player, budget)

    found = room.entity_at(3, 15)
    assert found is not None, "goblin must reappear after undo"
    assert found.alive is True
    assert found.kind == 'goblin'


# ── 13. rebuild_indexes called after dict undo ───────────────────────────────

def test_rebuild_indexes_called_after_dict_undo():
    """entity_at must locate a restored entity — confirms rebuild_indexes() was called."""
    room = _bare_room()
    goblin = Entity(kind='goblin', row=3, col=12, hp=1, max_hp=1, ai='chase')
    room.add_entity(goblin)

    player = Player(row=3, col=11)
    budget = _budget(spent=0)
    snap = _snapshot(room, player, budget)

    room.kill_entity(goblin)
    assert room.entity_at(3, 12) is None

    undo_stack = [snap]
    redo_stack = []
    _pop_history_step(undo_stack, redo_stack, room, player, budget)

    found = room.entity_at(3, 12)
    assert found is not None, (
        "entity_at must return goblin after dict undo — rebuild_indexes() must be called"
    )
    assert found.kind == 'goblin'
    assert found.alive is True
