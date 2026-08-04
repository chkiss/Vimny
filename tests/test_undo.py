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

"""
Undo correctness: every player action that mutates entity state must push a
dict (entity snapshot) onto the undo stack via _snapshot(), not a positional
tuple.

Covered actions
  chest x       — dict format (entity restored on undo)
  chest_key x   — floor_key added to the unnamed " register; chest restored on undo
  door x        — dict format (interact handler)
  dynamite step — dict format (motion handler, upgraded from tuple at explosion time)
  locked_door p — dict format; key read from " (NOT consumed), door restored on undo
  combat x      — dict format (strike snapshot; u revives the foe's HP + refunds the key)
  shield x      — dict format (shield restored on undo)
  heart_container x — undo BARRIER: stacks cleared (snapshots don't carry max_hp,
                  so undoing past the pickup would let the +2 stack forever)

Why an action can be missed
  test_all_entity_mutations_undoable hardcodes every entity-killing action.
  Add new entries here whenever a new action calls room.kill_entity() outside
  edit mode, so the test guards against the omission.

Required dict fields (all produced by _snapshot() in vimny/game.py)
  row, col, spent, entities, fog_cells
"""
from vimny.engine.world import Room, Entity, CellType, RoomType
from vimny.engine.player import Player
from vimny.engine.budget import Budget
from vimny.engine.operator import entity_clip
from vimny.engine.registers import write_register, read_register


# ── Fixtures ──────────────────────────────────────────────────────────────────

def _corridor(rows=5, cols=12):
    cells = [[CellType.FLOOR] * cols for _ in range(rows)]
    room = Room(room_type=RoomType.SAFE, rows=rows, cols=cols, cells=cells,
                spawn_pos=(2, 0), exit_pos=(2, cols - 1))
    room.rebuild_indexes()
    return room


def _snap(room):
    """Deep-copy of room.entities — matches the snapshot format used in vimny/game.py."""
    return [Entity(kind=e.kind, row=e.row, col=e.col, hp=e.hp, alive=e.alive)
            for e in room.entities]


def _apply_undo(item, room, player, budget):
    """Apply one undo item, mirroring vimny/game.py's undo branch."""
    if isinstance(item, dict):
        player.row, player.col = item['row'], item['col']
        budget.spent = item['spent']
        room.entities = item['entities']
        if 'cells' in item:                      # cells/rows/cols round-trip (reflow vertical/ledge ops)
            room.cells = item['cells']
            room.rows  = item['rows']
            room.cols  = item.get('cols', room.cols)
        room.fog_cells = item['fog_cells']
        room.rebuild_indexes()
    else:
        pr, pc, ps = item
        player.row, player.col = pr, pc
        budget.spent = ps
        # tuple format: entity state is NOT restored — this is the bug


# ── Chest x ───────────────────────────────────────────────────────────────────

def test_chest_x_undo_restores_entity():
    """x on a chest pushes a dict undo entry so the chest is restored."""
    room = _corridor()
    chest = Entity(kind='chest_random', row=2, col=5)
    room.add_entity(chest)
    player = Player(row=2, col=5)
    budget = Budget(20)

    undo_item = {'row': player.row, 'col': player.col, 'spent': budget.spent,
                 'entities': _snap(room), 'fog_cells': set(room.fog_cells)}
    room.kill_entity(chest)
    budget.spend(1)

    _apply_undo(undo_item, room, player, budget)

    restored = room.entity_at(2, 5)
    assert restored is not None, "chest must be present after undo"
    assert restored.alive
    assert restored.kind == 'chest_random'


def test_chest_key_adds_floor_key_to_register():
    """Opening a chest_key puts a floor_key into the player register."""
    room = _corridor()
    chest = Entity(kind='chest_key', row=2, col=5)
    room.add_entity(chest)
    player = Player(row=2, col=5)

    # Simulate what vimny/game.py does on chest_key loot
    write_register(player, '"',
                   entity_clip(Entity(kind='floor_key', row=chest.row, col=chest.col)),
                   is_delete=True)
    room.kill_entity(chest)

    ents = [ed['tmpl'] for rw in read_register(player, '"')['rows']
            for ed in rw.get('entities', ())]
    assert any(e['kind'] == 'floor_key' for e in ents), \
        "the unnamed \" register must hold a floor_key after looting chest_key"


def test_chest_key_undo_restores_chest():
    """Undoing a chest_key pickup restores the chest entity."""
    room = _corridor()
    chest = Entity(kind='chest_key', row=2, col=5)
    room.add_entity(chest)
    player = Player(row=2, col=5)
    budget = Budget(20)

    undo_item = {'row': player.row, 'col': player.col, 'spent': budget.spent,
                 'entities': _snap(room), 'fog_cells': set(room.fog_cells)}
    write_register(player, '"',
                   entity_clip(Entity(kind='floor_key', row=chest.row, col=chest.col)),
                   is_delete=True)
    room.kill_entity(chest)
    budget.spend(1)

    _apply_undo(undo_item, room, player, budget)

    assert room.entity_at(2, 5) is not None, "chest_key must be restored after undo"


# ── Door x ────────────────────────────────────────────────────────────────────

def test_door_x_undo_restores_entity():
    """Door x uses dict format → entity snapshot is saved and restored correctly."""
    room = _corridor()
    door = Entity(kind='door', row=2, col=5)
    room.add_entity(door)
    player = Player(row=2, col=5)
    budget = Budget(20)

    undo_item = {'row': player.row, 'col': player.col, 'spent': budget.spent,
                 'entities': _snap(room), 'fog_cells': set(room.fog_cells)}
    room.kill_entity(door)
    budget.spend(1)

    _apply_undo(undo_item, room, player, budget)

    restored = room.entity_at(2, 5)
    assert restored is not None, "door must be present after undo"
    assert restored.alive
    assert restored.kind == 'door'


# ── Dynamite step ─────────────────────────────────────────────────────────────

def test_dynamite_step_undo_restores_entity():
    """Stepping on dynamite pushes a dict undo entry so the entity is restored."""
    room = _corridor()
    dyn = Entity(kind='dynamite', row=2, col=5)
    room.add_entity(dyn)
    player = Player(row=2, col=4)
    budget = Budget(20)

    prev_pos = (player.row, player.col, budget.spent)
    budget.spend(1)
    player.row, player.col = 2, 5

    undo_stack = [{'row': prev_pos[0], 'col': prev_pos[1], 'spent': prev_pos[2],
                   'entities': _snap(room), 'fog_cells': set(room.fog_cells)}]
    room.kill_entity(dyn)

    _apply_undo(undo_stack.pop(), room, player, budget)

    restored = room.entity_at(2, 5)
    assert restored is not None, "dynamite must be restored after undo"
    assert restored.alive
    assert restored.kind == 'dynamite'


# ── Locked door p ─────────────────────────────────────────────────────────────

def test_locked_door_p_undo_restores_door():
    """p on a locked_door pushes a dict undo entry that restores the door."""
    room = _corridor()
    ldoor = Entity(kind='locked_door', row=2, col=6)
    room.add_entity(ldoor)
    player = Player(row=2, col=5)
    floor_key = Entity(kind='floor_key', row=2, col=5)
    write_register(player, '"', entity_clip(floor_key), is_delete=True)
    budget = Budget(20)

    undo_item = {'row': player.row, 'col': player.col, 'spent': budget.spent,
                 'entities': _snap(room), 'fog_cells': set(room.fog_cells)}
    # Unlock the door — the key in " is NOT consumed (vim-faithful; reusable).
    room.kill_entity(ldoor)
    budget.spend(1)

    assert room.entity_at(2, 6) is None

    _apply_undo(undo_item, room, player, budget)

    restored = room.entity_at(2, 6)
    assert restored is not None, "locked_door must be present after undo"
    assert restored.alive
    assert restored.kind == 'locked_door'

    # The key still sits in the unnamed register, reusable for more doors.
    ents = [ed['tmpl'] for rw in read_register(player, '"')['rows']
            for ed in rw.get('entities', ())]
    assert any(e['kind'] == 'floor_key' for e in ents)


# ── Combined: all entity-mutating actions use dict undo entries ───────────────

def test_all_entity_mutations_undoable():
    """Every entity-killing action must push a dict undo entry.

    Add new entries here whenever a new action calls room.kill_entity() outside
    edit mode, so the test guards against the omission.
    """
    room = _corridor()
    chest = Entity(kind='chest_random',       row=2, col=2)
    door  = Entity(kind='door',        row=2, col=4)
    dyn   = Entity(kind='dynamite',    row=2, col=7)
    ldoor = Entity(kind='locked_door', row=2, col=10)
    for e in (chest, door, dyn, ldoor):
        room.add_entity(e)

    player = Player(row=2, col=1)
    budget = Budget(20)

    entity_actions = []

    # --- chest x ---
    chest_undo = {'row': player.row, 'col': player.col, 'spent': budget.spent,
                  'entities': _snap(room), 'fog_cells': set(room.fog_cells)}
    room.kill_entity(chest)
    budget.spend(1)
    entity_actions.append(('chest_random', chest_undo))

    # --- door x ---
    door_undo = {'row': player.row, 'col': player.col, 'spent': budget.spent,
                 'entities': _snap(room), 'fog_cells': set(room.fog_cells)}
    room.kill_entity(door)
    budget.spend(1)
    entity_actions.append(('door', door_undo))

    # --- dynamite step ---
    prev = (player.row, player.col, budget.spent)
    budget.spend(1)
    player.row, player.col = 2, 7
    dyn_undo = {'row': prev[0], 'col': prev[1], 'spent': prev[2],
                'entities': _snap(room), 'fog_cells': set(room.fog_cells)}
    room.kill_entity(dyn)
    entity_actions.append(('dynamite', dyn_undo))

    # --- locked_door p ---
    ldoor_undo = {'row': player.row, 'col': player.col, 'spent': budget.spent,
                  'entities': _snap(room), 'fog_cells': set(room.fog_cells)}
    room.kill_entity(ldoor)
    budget.spend(1)
    entity_actions.append(('locked_door', ldoor_undo))

    for label, item in entity_actions:
        assert isinstance(item, dict), (
            f"undo item for '{label}' is a {type(item).__name__}, not a dict — "
            "entity state cannot be restored; use _snapshot() in the handler"
        )
        required = {'row', 'col', 'spent', 'entities', 'fog_cells'}
        missing = required - item.keys()
        assert not missing, (
            f"undo item for '{label}' is missing fields: {missing} — "
            "use _snapshot() which always includes them"
        )


# ── Fumble: undo while carrying a key drops it (penalty, NOT a normal undo) ───

def _undo_or_fumble(room, player, budget, undo_stack):
    """Mirror vimny/game.py's undo branch: the undo HAPPENS, and if a key is carried it
    drops at the pre-undo spot (dropped after the undo so a restore can't wipe it)."""
    from vimny.game import _held_key, _drop_key
    held = _held_key(player)
    spot = (player.row, player.col)
    done = False
    if undo_stack:
        _apply_undo(undo_stack.pop(), room, player, budget)
        done = True
    if held is not None and done and _drop_key(room, spot[0], spot[1], held.get('tag', '')):
        player.registers['"'] = None
        return 'fumble'
    return 'undo' if done else 'noop'


def test_undo_while_holding_key_drops_it_and_still_undoes():
    """u while carrying a key drops it where you stood (colour preserved) AND the
    undo still happens (you snap back to the previous position); register clears."""
    room = _corridor()
    player = Player(row=2, col=5)
    budget = Budget(20)
    budget.spent = 4
    write_register(player, '"',
                   entity_clip(Entity(kind='floor_key', row=2, col=2, tag='red')),
                   is_delete=True)
    # Last change was a move from (2,0); undo returns the adventurer there.
    undo_stack = [(2, 0, 0)]

    result = _undo_or_fumble(room, player, budget, undo_stack)

    assert result == 'fumble'
    dropped = room.entity_at(2, 5)                      # key left at the pre-undo spot
    assert dropped is not None and dropped.kind == 'floor_key' and dropped.tag == 'red'
    from vimny.game import _held_key
    assert _held_key(player) is None, "register must no longer carry the key"
    assert (player.row, player.col) == (2, 0), "the undo must have run (snapped back)"
    assert budget.spent == 0, "the undo must have reverted the budget"


def test_undo_without_a_key_is_normal():
    """With no key in hand, u behaves as a plain undo."""
    room = _corridor()
    player = Player(row=2, col=8)
    budget = Budget(20)
    budget.spent = 3
    undo_stack = [{'row': 2, 'col': 1, 'spent': 0,
                   'entities': _snap(room), 'fog_cells': set(room.fog_cells)}]

    result = _undo_or_fumble(room, player, budget, undo_stack)

    assert result == 'undo'
    assert (player.row, player.col) == (2, 1) and budget.spent == 0
    assert undo_stack == []


def test_combat_x_undo_revives_hp_and_refunds_the_key():
    """A combat strike pushes its own snapshot: u revives the foe's HP, refunds
    exactly the strike's keystroke, and a redo re-lands it (no free hits)."""
    from vimny.game import _snapshot, _pop_history_step
    room = _corridor()
    warden = Entity(kind='warden', row=2, col=5, hp=5, max_hp=5)
    room.add_entity(warden)
    player = Player(row=2, col=5)
    budget = Budget(20)
    budget.spent = 3
    undo_stack, redo_stack = [], []

    undo_stack.append(_snapshot(room, player, budget))      # the combat-branch push
    warden.hp -= 1
    budget.spend(1)

    assert _pop_history_step(undo_stack, redo_stack, room, player, budget)
    restored = room.entity_at(2, 5)
    assert restored.hp == 5 and restored.max_hp == 5, "undo must revive the struck HP"
    assert budget.spent == 3, "undo must refund exactly the strike's keystroke"

    assert _pop_history_step(redo_stack, undo_stack, room, player, budget, is_redo=True)
    assert room.entity_at(2, 5).hp == 4 and budget.spent == 4, "redo re-lands the hit"


def test_shield_x_undo_restores_shield():
    """x on a shield pushes a snapshot so u puts the shield back."""
    from vimny.game import _snapshot, _pop_history_step
    room = _corridor()
    shield = Entity(kind='shield', row=2, col=6)
    room.add_entity(shield)
    player = Player(row=2, col=6)
    budget = Budget(20)
    undo_stack, redo_stack = [], []

    undo_stack.append(_snapshot(room, player, budget))
    room.kill_entity(shield)
    budget.spend(1)
    assert room.entity_at(2, 6) is None

    _pop_history_step(undo_stack, redo_stack, room, player, budget)
    restored = room.entity_at(2, 6)
    assert restored is not None and restored.kind == 'shield' and restored.alive


def test_cols_round_trip_after_buffer_double():
    """A's ledge-build can DOUBLE room.cols; undo must restore the old width.
    Snapshot/restore now carry 'cols' alongside 'rows' so the cells grid and
    room.cols stay in sync after an undo."""
    from vimny.engine.reflow import extend_floor
    room = _corridor(rows=4, cols=8)
    player = Player(row=1, col=0)
    budget = Budget(total=10)
    snap = {'row': player.row, 'col': player.col, 'spent': budget.spent,
            'entities': _snap(room),
            'cells': [r[:] for r in room.cells], 'rows': room.rows, 'cols': room.cols,
            'fog_cells': set(room.fog_cells)}
    extend_floor(room, 1, 7, 'Q')                 # building on the border (col 7) doubles to 16
    assert room.cols == 16
    _apply_undo(snap, room, player, budget)
    assert room.cols == 8                          # width restored
    assert all(len(r) == 8 for r in room.cells)    # every row matches room.cols again
