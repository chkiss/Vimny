"""Normal-mode x cuts TEXT only — the count-x cheese regression.

The catch-all cut loop once routed through the admin editor's _ed_cut, so a
count-x in normal play carved WALLS into floor, deleted locked doors, and
free-killed creatures at range — bypassing keys, combat, and geometry on every
level. x now cuts char runs only; creatures die by the combat branch (which
covers 'wanderer' too) and dynamite by its dedicated scan.

Driven through the real run_dungeon keystroke loop on tiny hand-built rooms."""
from blessed.keyboard import Keystroke
from blessed import Terminal

import main
from engine.world import Dungeon, Room, RoomType, CellType, CharRun, Entity


def _ks(ch, name=None):
    return Keystroke(ch, name=name)


def _dungeon(neighbor=None, runs=()):
    room = Room(rows=5, cols=20, room_type=RoomType.ENTRY)
    room.cells = [[CellType.WALL] * 20 for _ in range(5)]
    for c in range(1, 19):
        room.cells[2][c] = CellType.CORRIDOR
    room.spawn_pos = (2, 2)
    room.exit_pos  = (2, 18)
    room.entities  = [Entity(kind='exit', row=2, col=18)]
    if neighbor == 'wall':
        room.cells[2][3] = CellType.WALL
    elif neighbor is not None:
        kw = dict(hp=1, max_hp=1, ai='chase') if neighbor in ('goblin', 'wanderer') else {}
        room.entities.append(Entity(kind=neighbor, row=2, col=3, **kw))
    for ru in runs:
        room.char_runs.append(ru)
    room.par, room.budget, room.answer = 10, 60, ''
    room.rebuild_indexes()
    d = Dungeon(name='Probe', seed=1)
    d.rooms, d.current_room = [room], 0
    return d


def _drive(monkeypatch, dungeon, keys):
    monkeypatch.setattr(main, 'render_all', lambda *a, **k: None)
    monkeypatch.setattr(main.time, 'sleep', lambda *a, **k: None)
    term = Terminal()
    it = iter(list(keys) + [_ks(':'), _ks('q'), _ks('!'), _ks('\r')])
    monkeypatch.setattr(term, 'inkey', lambda *a, **k: next(it, _ks('')))
    main.run_dungeon(term, 'dummy', {}, player_name='Normand', _dungeon=dungeon)
    return dungeon.rooms[0]


def test_count_x_does_not_carve_walls(monkeypatch):
    d = _dungeon('wall')
    room = _drive(monkeypatch, d, [_ks('2'), _ks('x')])
    assert room.cells[2][3] == CellType.WALL


def test_count_x_does_not_delete_a_locked_door(monkeypatch):
    d = _dungeon('locked_door')
    room = _drive(monkeypatch, d, [_ks('2'), _ks('x')])
    assert any(e.alive and e.kind == 'locked_door' for e in room.entities)


def test_count_x_does_not_kill_a_creature_at_range(monkeypatch):
    d = _dungeon('goblin')
    room = _drive(monkeypatch, d, [_ks('2'), _ks('x')])
    assert any(e.alive and e.kind == 'goblin' for e in room.entities)


def test_x_on_own_cell_still_strikes_a_wanderer(monkeypatch):
    """Creatures die by COMBAT: step onto the wanderer and x — the combat branch
    (which now covers 'wanderer') lands the hit."""
    d = _dungeon('wanderer')
    room = _drive(monkeypatch, d, [_ks('l'), _ks('x')])
    assert not any(e.alive and e.kind == 'wanderer' for e in room.entities)


def test_count_x_still_cuts_characters_at_range(monkeypatch):
    """3x cuts three TEXT cells rightward (Vim's x), reflow pulling the tail."""
    d = _dungeon(runs=[CharRun(2, 2, ('a', 'b', 'c', 'd'), 'ancient')])
    room = _drive(monkeypatch, d, [_ks('3'), _ks('x')])
    ru = room.char_run_at(2, 2)
    assert ru is not None and ''.join(ru.symbols) == 'd'    # abc cut, d pulled to col 2
