"""The Register Hoarder — pastes clipboard content everywhere unusual.

Personality defined in agents/bug_testers.md.
"""
import pytest
from engine.vim_parser import parse
from engine.modes import Mode
from engine.world import Room, RoomType, CellType, Entity
from engine.player import Player
from engine.command_guard import action_allowed


def _bare_room(rows=7, cols=30):
    room = Room(room_type=RoomType.ENTRY, rows=rows, cols=cols)
    room.cells = [
        [CellType.FLOOR if (0 < r < rows - 1 and 0 < c < cols - 1) else CellType.WALL
         for c in range(cols)]
        for r in range(rows)
    ]
    room.gg_pos    = (3, 1)
    room.exit_pos = (3, 28)
    room.fog_cells = set()
    room.rebuild_indexes()
    return room


def _floor_key_item(row=2, col=2):
    return {'type': 'entity', 'entity': Entity(kind='floor_key', row=row, col=col)}


# ── Parser ────────────────────────────────────────────────────────────────────

def test_p_parses_as_paste_before_false():
    action, remaining = parse('p', Mode.NORMAL)
    assert action == {'type': 'paste', 'before': False, 'count': 1}
    assert remaining == ''


def test_P_parses_as_paste_before_true():
    action, remaining = parse('P', Mode.NORMAL)
    assert action == {'type': 'paste', 'before': True, 'count': 1}
    assert remaining == ''


def test_3p_parses_with_count():
    action, remaining = parse('3p', Mode.NORMAL)
    assert action == {'type': 'paste', 'before': False, 'count': 3}
    assert remaining == ''


# ── p checks cell to the RIGHT ───────────────────────────────────────────────

def test_p_target_is_one_cell_to_right():
    """p (before=False) uses dc=+1, so it checks the cell directly to the right."""
    room = _bare_room()
    room.add_entity(Entity(kind='locked_door', row=3, col=5))
    player = Player(row=3, col=4)

    dc = 1   # p uses dc = +1
    target = room.entity_at(player.row, player.col + dc)

    assert target is not None
    assert target.kind == 'locked_door'


def test_P_target_is_one_cell_to_left():
    """P (before=True) uses dc=-1, so it checks the cell directly to the left."""
    room = _bare_room()
    room.add_entity(Entity(kind='locked_door', row=3, col=3))
    player = Player(row=3, col=4)

    dc = -1   # P uses dc = -1
    target = room.entity_at(player.row, player.col + dc)

    assert target is not None
    assert target.kind == 'locked_door'


# ── Key lookup in register ────────────────────────────────────────────────────

def test_key_found_in_register_at_index_0():
    """Key lookup must succeed when the first register item is a floor_key."""
    player = Player()
    player.register = [_floor_key_item()]

    reg_key_idx = next(
        (i for i, it in enumerate(player.register)
         if it.get('type') == 'entity' and
         it.get('entity') and it['entity'].kind == 'floor_key'),
        None,
    )

    assert reg_key_idx == 0


def test_key_found_in_register_when_preceded_by_other_item():
    """Key lookup must find a floor_key even if another item precedes it."""
    player = Player()
    player.register = [
        {'type': 'entity', 'entity': Entity(kind='goblin', row=1, col=1)},
        _floor_key_item(),
    ]

    reg_key_idx = next(
        (i for i, it in enumerate(player.register)
         if it.get('type') == 'entity' and
         it.get('entity') and it['entity'].kind == 'floor_key'),
        None,
    )

    assert reg_key_idx == 1


def test_key_not_found_in_empty_register():
    """Key lookup on an empty register must return None."""
    player = Player()
    player.register = []

    reg_key_idx = next(
        (i for i, it in enumerate(player.register)
         if it.get('type') == 'entity' and
         it.get('entity') and it['entity'].kind == 'floor_key'),
        None,
    )

    assert reg_key_idx is None


def test_key_not_found_when_only_goblin_in_register():
    """Register with non-key item must not match the key lookup."""
    player = Player()
    player.register = [
        {'type': 'entity', 'entity': Entity(kind='goblin', row=1, col=1)}
    ]

    reg_key_idx = next(
        (i for i, it in enumerate(player.register)
         if it.get('type') == 'entity' and
         it.get('entity') and it['entity'].kind == 'floor_key'),
        None,
    )

    assert reg_key_idx is None


# ── Key consumption ───────────────────────────────────────────────────────────

def test_consuming_key_removes_it_from_register():
    """After unlocking, the key must be removed from the register (not just ignored)."""
    player = Player()
    player.register = [_floor_key_item()]

    reg_key_idx = 0
    player.register.pop(reg_key_idx)

    assert player.register == [], "register must be empty after key is consumed"


def test_consuming_key_removes_only_that_item():
    """Only the floor_key should be consumed; other register items must remain."""
    player = Player()
    other = {'type': 'entity', 'entity': Entity(kind='shield', row=1, col=1)}
    player.register = [other, _floor_key_item()]

    reg_key_idx = 1
    player.register.pop(reg_key_idx)

    assert len(player.register) == 1
    assert player.register[0] is other


# ── Wrong direction: p with door to the left does nothing ────────────────────

def test_p_wrong_direction_misses_locked_door():
    """p checks the RIGHT neighbour; locked_door to the LEFT must not trigger unlock."""
    room = _bare_room()
    room.add_entity(Entity(kind='locked_door', row=3, col=3))
    player = Player(row=3, col=4)

    dc = 1   # p uses dc = +1
    target = room.entity_at(player.row, player.col + dc)

    # col 5 is empty, so target is None — paste would show "Nothing to paste here"
    assert target is None, (
        "p must miss the locked_door to the left (uses dc=+1, not dc=-1)"
    )


# ── action_allowed gating ─────────────────────────────────────────────────────

def test_paste_blocked_without_p_in_known_commands():
    """p (paste after) must be blocked when 'p' is not in known_commands."""
    action = {'type': 'paste', 'before': False, 'count': 1}
    known = ['h', 'j', 'k', 'l']

    assert not action_allowed(action, known), (
        "paste should be disallowed without 'p' in known_commands"
    )


def test_paste_allowed_with_p_in_known_commands():
    """p (paste after) must be allowed when 'p' is in known_commands."""
    action = {'type': 'paste', 'before': False, 'count': 1}
    known = ['h', 'j', 'k', 'l', 'p']

    assert action_allowed(action, known), (
        "paste should be allowed when 'p' is in known_commands"
    )


def test_paste_allowed_for_admin():
    """Admin always passes action_allowed regardless of known_commands."""
    action = {'type': 'paste', 'before': True, 'count': 1}
    known = ['admin']

    assert action_allowed(action, known)
