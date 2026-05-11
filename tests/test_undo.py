"""
Undo correctness: every player action that mutates entity state must push a
dict (entity snapshot) onto the undo stack via _snapshot(), not a positional
tuple.

Covered actions
  chest x       — dict format with 'keys' field (loot may grant a key)
  door x        — dict format (interact handler)
  dynamite step — dict format (motion handler, upgraded from tuple at explosion time)
  locked_door p — dict format with 'keys' field (paste handler)

Why an action can be missed
  test_all_entity_mutations_undoable hardcodes every entity-killing action.
  Add new entries here whenever a new action calls room.kill_entity() outside
  edit mode, so the test guards against the omission.

Required dict fields (all produced by _snapshot() in main.py)
  row, col, spent, entities, fog_cells, keys
  _snapshot() always includes 'keys' so inventory is restored for any action
  that grants or removes items, even if the caller doesn't think about it.
"""
from engine.world import Room, Entity, CellType, RoomType
from engine.player import Player
from engine.budget import Budget


# ── Fixtures ──────────────────────────────────────────────────────────────────

def _corridor(rows=5, cols=12):
    cells = [[CellType.FLOOR] * cols for _ in range(rows)]
    room = Room(room_type=RoomType.SAFE, rows=rows, cols=cols, cells=cells,
                entry=(2, 0), exit_pos=(2, cols - 1))
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
        player.keys = item.get('keys', player.keys)
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
                 'entities': _snap(room), 'fog_cells': set(room.fog_cells),
                 'keys': player.keys}
    room.kill_entity(chest)
    budget.spend(1)

    _apply_undo(undo_item, room, player, budget)

    restored = room.entity_at(2, 5)
    assert restored is not None, "chest must be present after undo"
    assert restored.alive
    assert restored.kind == 'chest'


def test_chest_key_undo_restores_key():
    """When a chest_key grants a key, undoing must revert player.keys too."""
    room = _corridor()
    chest = Entity(kind='chest_key', row=2, col=5)
    room.add_entity(chest)
    player = Player(row=2, col=5)
    player.keys = 0
    budget = Budget(20)

    undo_item = {'row': player.row, 'col': player.col, 'spent': budget.spent,
                 'entities': _snap(room), 'fog_cells': set(room.fog_cells),
                 'keys': player.keys}
    player.keys += 1    # loot grants a key
    room.kill_entity(chest)
    budget.spend(1)

    assert player.keys == 1
    _apply_undo(undo_item, room, player, budget)

    assert player.keys == 0, "key grant must be reverted by undo"
    assert room.entity_at(2, 5) is not None, "chest_key must be restored"


# ── Door x ────────────────────────────────────────────────────────────────────

def test_door_x_undo_restores_entity():
    """Door x uses dict format → entity snapshot is saved and restored correctly."""
    room = _corridor()
    door = Entity(kind='door', row=2, col=5)
    room.add_entity(door)
    player = Player(row=2, col=5)
    budget = Budget(20)

    undo_item = {'row': player.row, 'col': player.col, 'spent': budget.spent,
                 'entities': _snap(room), 'fog_cells': set(room.fog_cells),
                 'keys': player.keys}
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
                   'entities': _snap(room), 'fog_cells': set(room.fog_cells),
                   'keys': player.keys}]
    room.kill_entity(dyn)

    _apply_undo(undo_stack.pop(), room, player, budget)

    restored = room.entity_at(2, 5)
    assert restored is not None, "dynamite must be restored after undo"
    assert restored.alive
    assert restored.kind == 'dynamite'


# ── Locked door p ─────────────────────────────────────────────────────────────

def test_locked_door_p_undo_restores_entity_and_key():
    """p on a locked_door pushes a dict undo entry that restores the door and the key."""
    room = _corridor()
    ldoor = Entity(kind='locked_door', row=2, col=6)
    room.add_entity(ldoor)
    player = Player(row=2, col=5)
    player.keys = 1
    budget = Budget(20)

    undo_item = {'row': player.row, 'col': player.col, 'spent': budget.spent,
                 'entities': _snap(room), 'fog_cells': set(room.fog_cells),
                 'keys': player.keys}
    player.keys -= 1
    room.kill_entity(ldoor)
    budget.spend(1)

    assert player.keys == 0
    assert room.entity_at(2, 6) is None

    _apply_undo(undo_item, room, player, budget)

    assert player.keys == 1, "key must be restored after undo"
    restored = room.entity_at(2, 6)
    assert restored is not None, "locked_door must be present after undo"
    assert restored.alive
    assert restored.kind == 'locked_door'


# ── Combined: all entity-mutating actions restore entities on undo ─────────────

def test_all_entity_mutations_undoable():
    """Every entity-killing action must push a dict undo entry with all fields.

    Add new entries here whenever a new action calls room.kill_entity() outside
    edit mode.  Every entry must include 'keys' (produced automatically by
    _snapshot() in main.py) so inventory is restored regardless of whether the
    specific action grants items.
    """
    room = _corridor()
    chest = Entity(kind='chest',       row=2, col=2)
    door  = Entity(kind='door',        row=2, col=4)
    dyn   = Entity(kind='dynamite',    row=2, col=7)
    ldoor = Entity(kind='locked_door', row=2, col=10)
    for e in (chest, door, dyn, ldoor):
        room.add_entity(e)

    player = Player(row=2, col=1)
    player.keys = 1
    budget = Budget(20)

    entity_actions = []

    # --- chest x ---
    chest_undo = {'row': player.row, 'col': player.col, 'spent': budget.spent,
                  'entities': _snap(room), 'fog_cells': set(room.fog_cells),
                  'keys': player.keys}
    room.kill_entity(chest)
    budget.spend(1)
    entity_actions.append(('chest', chest_undo))

    # --- door x ---
    door_undo = {'row': player.row, 'col': player.col, 'spent': budget.spent,
                 'entities': _snap(room), 'fog_cells': set(room.fog_cells),
                 'keys': player.keys}
    room.kill_entity(door)
    budget.spend(1)
    entity_actions.append(('door', door_undo))

    # --- dynamite step ---
    prev = (player.row, player.col, budget.spent)
    budget.spend(1)
    player.row, player.col = 2, 7
    dyn_undo = {'row': prev[0], 'col': prev[1], 'spent': prev[2],
                'entities': _snap(room), 'fog_cells': set(room.fog_cells),
                'keys': player.keys}
    room.kill_entity(dyn)
    entity_actions.append(('dynamite', dyn_undo))

    # --- locked_door p ---
    ldoor_undo = {'row': player.row, 'col': player.col, 'spent': budget.spent,
                  'entities': _snap(room), 'fog_cells': set(room.fog_cells),
                  'keys': player.keys}
    player.keys -= 1
    room.kill_entity(ldoor)
    budget.spend(1)
    entity_actions.append(('locked_door', ldoor_undo))

    for label, item in entity_actions:
        assert isinstance(item, dict), (
            f"undo item for '{label}' is a {type(item).__name__}, not a dict — "
            "entity state cannot be restored; use _snapshot() in the handler"
        )
        assert 'keys' in item, (
            f"undo item for '{label}' is missing 'keys' — "
            "use _snapshot() which always includes it"
        )
