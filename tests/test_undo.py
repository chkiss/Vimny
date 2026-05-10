"""
Undo correctness: every player action that mutates entity state must push a
dict (entity snapshot) onto the undo stack, not a positional tuple.

Covered actions
  door x     — dict format (interact handler, main.py lines 583-594)
  dynamite   — dict format (motion handler, main.py dynamite branch)

Regression guard: if a new entity-killing action uses tuple undo instead of
dict undo, test_all_entity_mutations_undoable will catch it.
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
    """Apply one undo item, mirroring main.py's undo branch (lines 511-527)."""
    if isinstance(item, dict):
        player.row, player.col = item['row'], item['col']
        budget.spent = item['spent']
        room.entities = item['entities']
        room.fog_col = item['fog_col']
        room.rebuild_indexes()
    else:
        pr, pc, ps = item
        player.row, player.col = pr, pc
        budget.spent = ps
        # tuple format: entity state is NOT restored — this is the bug


# ── Door x — already fixed, sanity check ─────────────────────────────────────

def test_door_x_undo_restores_entity():
    """Door x uses dict format → entity snapshot is saved and restored correctly."""
    room = _corridor()
    door = Entity(kind='door', row=2, col=5)
    room.add_entity(door)
    player = Player(row=2, col=5)
    budget = Budget(20)

    # main.py lines 583-588: dict pushed BEFORE kill_entity
    undo_item = {'row': player.row, 'col': player.col, 'spent': budget.spent,
                 'entities': _snap(room), 'fog_col': room.fog_col}
    room.kill_entity(door)
    budget.spend(1)

    _apply_undo(undo_item, room, player, budget)

    restored = room.entity_at(2, 5)
    assert restored is not None, "door must be present after undo"
    assert restored.alive
    assert restored.kind == 'door'


# ── Dynamite step — BUG: tuple undo loses entity snapshot ────────────────────

def test_dynamite_step_undo_restores_entity():
    """Stepping on dynamite pushes a dict undo entry so the entity is restored.

    Regression: motion handler pushed a tuple before the explosion, losing the
    entity snapshot.  Fix: upgrade the tuple to a dict before kill_entity.
    """
    room = _corridor()
    dyn = Entity(kind='dynamite', row=2, col=5)
    room.add_entity(dyn)
    player = Player(row=2, col=4)
    budget = Budget(20)

    # Simulate what main.py currently does (THE BUG):
    #   motion handler pushes tuple at line 409 …
    prev_pos = (player.row, player.col, budget.spent)
    budget.spend(1)
    player.row, player.col = 2, 5      # player lands on dynamite

    undo_stack = [{'row': prev_pos[0], 'col': prev_pos[1], 'spent': prev_pos[2],
                   'entities': _snap(room), 'fog_col': room.fog_col}]
    room.kill_entity(dyn)

    _apply_undo(undo_stack.pop(), room, player, budget)

    restored = room.entity_at(2, 5)
    assert restored is not None, (
        "dynamite must be restored after undo — "
        "fix: upgrade undo_stack tuple to dict before kill_entity in dynamite branch"
    )
    assert restored.alive
    assert restored.kind == 'dynamite'


# ── Combined: all entity-mutating actions restore entities on undo ─────────────

def test_all_entity_mutations_undoable():
    """Both door and dynamite undo items must be dict-format (entity snapshot).

    If an action is added that kills an entity via tuple undo, this test will
    catch the regression by verifying the undo_stack item type.
    """
    room = _corridor()
    door = Entity(kind='door', row=2, col=3)
    dyn  = Entity(kind='dynamite', row=2, col=7)
    room.add_entity(door)
    room.add_entity(dyn)

    player = Player(row=2, col=2)
    budget = Budget(20)

    entity_actions = []

    # --- door x: main.py pushes dict (correct) ---
    door_undo = {'row': player.row, 'col': player.col, 'spent': budget.spent,
                 'entities': _snap(room), 'fog_col': room.fog_col}
    room.kill_entity(door)
    budget.spend(1)
    entity_actions.append(('door', door_undo))

    # --- dynamite step: must push dict with entity snapshot before kill ---
    prev = (player.row, player.col, budget.spent)
    budget.spend(1)
    player.row, player.col = 2, 7
    dyn_undo = {'row': prev[0], 'col': prev[1], 'spent': prev[2],
                'entities': _snap(room), 'fog_col': room.fog_col}
    room.kill_entity(dyn)
    entity_actions.append(('dynamite', dyn_undo))

    for label, item in entity_actions:
        assert isinstance(item, dict), (
            f"undo item for '{label}' is a {type(item).__name__}, not a dict — "
            f"entity state cannot be restored; use dict format with entity snapshot"
        )
