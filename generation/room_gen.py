"""Generate a single room with walls, floor, character runs, and entities."""
from __future__ import annotations
import random
from engine.world import Room, RoomType, CellType, Entity

# Canonical rune glyph per kind — the single source of truth, shared with
# generation/dungeon_gen.py (imported there as `_RUNE_CHAR`). Change a glyph here
# and it changes everywhere a rune of that kind is drawn.
RUNE_CHAR = {
    'ancient': '∘',
    'verdant': '·',
    'void':    '○',
    'ember':   '⊙',
}

def _blank_room(rows: int, cols: int) -> list[list[CellType]]:
    cells = [[CellType.WALL] * cols for _ in range(rows)]
    for r in range(1, rows - 1):
        for c in range(1, cols - 1):
            cells[r][c] = CellType.FLOOR
    return cells

def make_room(room_type: RoomType, rows: int, cols: int, seed: int) -> Room:
    rng = random.Random(seed)
    room = Room(room_type=room_type, rows=rows, cols=cols)
    room.seed = seed
    room.cells = _blank_room(rows, cols)

    # Entry point: top-left interior
    room.spawn_pos = (1, 1)

    # Exit: depends on room type
    if room_type == RoomType.EXIT:
        room.exit_pos = (rows - 2, cols - 2)
        room.entities.append(Entity(kind='exit', row=rows - 2, col=cols - 2))
    elif room_type == RoomType.CHEST:
        room.entities.append(Entity(kind='chest', row=rows // 2, col=cols - 3))
    elif room_type in (RoomType.COMBAT,):
        # Place a couple of wanderers
        for _ in range(rng.randint(1, 2)):
            er = rng.randint(1, rows - 2)
            ec = rng.randint(1, cols - 2)
            room.entities.append(Entity(kind='wanderer', row=er, col=ec, hp=2))

    return room
