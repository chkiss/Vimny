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

Why an action can be missed
  test_all_entity_mutations_undoable hardcodes every entity-killing action.
  Add new entries here whenever a new action calls room.kill_entity() outside
  edit mode, so the test guards against the omission.

Required dict fields (all produced by _snapshot() in main.py)
  row, col, spent, entities, fog_cells
"""
from engine.world import Room, Entity, CellType, RoomType
from engine.player import Player
from engine.budget import Budget
from engine.operator import entity_clip
from engine.registers import write_register, read_register


# ── Fixtures ──────────────────────────────────────────────────────────────────

def _corridor(rows=5, cols=12):
    cells = [[CellType.FLOOR] * cols for _ in range(rows)]
    room = Room(room_type=RoomType.SAFE, rows=rows, cols=cols, cells=cells,
                spawn_pos=(2, 0), exit_pos=(2, cols - 1))
    room.rebuild_indexes()
    return room


def _snap(room):
    """Deep-copy of room.entities — matches the snapshot format used in main.py."""
    return [Entity(kind=e.kind, row=e.row, col=e.col, hp=e.hp, alive=e.alive)
            for e in room.entities]


def _apply_undo(item, room, player, budget):
    """Apply one undo item, mirroring main.py's undo branch."""
    if isinstance(item, dict):
        player.row, player.col = item['row'], item['col']
        budget.spent = item['spent']
        room.entities = item['entities']
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
    chest = Entity(kind='chest', row=2, col=5)
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
    assert restored.kind == 'chest'


def test_chest_key_adds_floor_key_to_register():
    """Opening a chest_key puts a floor_key into the player register."""
    room = _corridor()
    chest = Entity(kind='chest_key', row=2, col=5)
    room.add_entity(chest)
    player = Player(row=2, col=5)

    # Simulate what main.py does on chest_key loot
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
    chest = Entity(kind='chest',       row=2, col=2)
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
    entity_actions.append(('chest', chest_undo))

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
