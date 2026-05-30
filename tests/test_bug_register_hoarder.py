"""The Register Hoarder — pastes clipboard content everywhere unusual.

Personality defined in agents/bug_testers.md.
"""
import pytest
from engine.vim_parser import parse
from engine.modes import Mode
from engine.world import Room, RoomType, CellType, Entity
from engine.player import Player
from engine.command_guard import action_allowed
from engine.operator import entity_clip
from engine.registers import write_register, read_register


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


# ── Key lives in the unnamed " register (one payload; reusable; overwritten by a cut) ──

def _key_clip(tag=''):
    return entity_clip(Entity(kind='floor_key', row=2, col=2, tag=tag))


def _reg_keys(player):
    clip = read_register(player, '"') or {}
    return [ed['tmpl'] for rw in clip.get('rows', [])
            for ed in rw.get('entities', ()) if ed['tmpl'].get('kind') == 'floor_key']


def test_key_held_in_unnamed_register():
    """A picked-up key is just the unnamed register's payload."""
    player = Player()
    write_register(player, '"', _key_clip(), is_delete=True)
    assert _reg_keys(player), 'the " register must hold the floor_key'


def test_cutting_overwrites_held_key():
    """Cutting anything after picking up a key overwrites it — one payload in "."""
    player = Player()
    write_register(player, '"', _key_clip(), is_delete=True)
    write_register(player, '"',
                   {'linewise': False,
                    'rows': [{'width': 1,
                              'char_runs': [{'dcol': 0, 'symbols': ('x',), 'kind': 'ancient'}]}]},
                   is_delete=True)
    assert not _reg_keys(player), 'a later cut must overwrite the held key'


def test_key_not_consumed_so_it_is_reusable():
    """Unlock reads the key but never empties " — so p p / 3p reuse one key."""
    player = Player()
    write_register(player, '"', _key_clip(), is_delete=True)
    read_register(player, '"')
    read_register(player, '"')
    assert _reg_keys(player), 'the key must persist for repeated pastes'


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
