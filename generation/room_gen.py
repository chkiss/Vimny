"""Generate a single room with walls, floor, rune clusters, and entities."""
from __future__ import annotations
import random
from engine.world import Room, RoomType, CellType, RuneCluster, Entity

RUNE_TYPES = {
    'ancient': ('∘', '∘', '∘'),
    'verdant': ('·', '·', '·'),
    'void':    ('○', '○'),
    'ember':   ('◦', '◦', '◦', '◦'),
}

def _blank_room(rows: int, cols: int) -> list[list[CellType]]:
    cells = [[CellType.WALL] * cols for _ in range(rows)]
    for r in range(1, rows - 1):
        for c in range(1, cols - 1):
            cells[r][c] = CellType.FLOOR
    return cells

def _place_clusters(room: Room, rng: random.Random, density: float):
    interior_cols = room.cols - 2  # exclude walls
    interior_rows = room.rows - 2
    placed: list[tuple[int,int,int]] = []  # (row, col_start, width)

    for r in range(1, room.rows - 1):
        c = 2
        while c < room.cols - 3:
            if rng.random() < density:
                kind = rng.choice(list(RUNE_TYPES.keys()))
                syms = RUNE_TYPES[kind]
                width = len(syms)
                if c + width < room.cols - 1:
                    cluster = RuneCluster(row=r, col=c, symbols=syms, kind=kind)
                    room.runes.append(cluster)
                    placed.append((r, c, width))
                    c += width + rng.randint(1, 3)
                    continue
            c += 1

def make_room(room_type: RoomType, rows: int, cols: int, seed: int,
              dungeon_level: int = 0) -> Room:
    rng = random.Random(seed)
    room = Room(room_type=room_type, rows=rows, cols=cols)
    room.seed = seed
    room.cells = _blank_room(rows, cols)

    density = 0.15 + dungeon_level * 0.02

    if room_type != RoomType.ENTRY:
        _place_clusters(room, rng, density)

    # Entry point: top-left interior
    room.entry = (1, 1)

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
