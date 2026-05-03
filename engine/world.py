from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Optional

class CellType(Enum):
    WALL     = auto()
    FLOOR    = auto()
    CORRIDOR = auto()

class RoomType(Enum):
    ENTRY   = auto()
    PUZZLE  = auto()
    COMBAT  = auto()
    CHEST   = auto()
    SAFE    = auto()
    BOSS    = auto()
    EXIT    = auto()

@dataclass
class Entity:
    kind: str           # 'wanderer', 'guard', 'chest', 'exit', etc.
    row: int
    col: int
    hp: int = 1
    alive: bool = True

@dataclass
class RuneCluster:
    row: int
    col: int
    symbols: tuple      # e.g. ('∘','∘','∘')
    kind: str           # 'ancient','verdant','void','ember'

@dataclass
class Room:
    room_type: RoomType
    rows: int
    cols: int
    cells: list[list[CellType]] = field(default_factory=list)
    runes: list[RuneCluster]    = field(default_factory=list)
    entities: list[Entity]      = field(default_factory=list)
    entry: tuple[int,int]       = (0, 0)
    exit_pos: Optional[tuple[int,int]] = None
    budget: Optional[int]       = None
    par: Optional[int]          = None
    seed: Optional[int]         = None
    fog_col: int                = -1   # columns >= fog_col are hidden; -1 = no fog
    passable_walls: bool        = False  # if True, walls are walkable (editor mode)

    def cell(self, r: int, c: int) -> CellType:
        return self.cells[r][c]

    def is_passable(self, r: int, c: int) -> bool:
        if r < 0 or r >= self.rows or c < 0 or c >= self.cols:
            return False
        if self.passable_walls:
            return True
        return self.cells[r][c] in (CellType.FLOOR, CellType.CORRIDOR)

    def entity_at(self, r: int, c: int) -> Optional[Entity]:
        for e in self.entities:
            if e.alive and e.row == r and e.col == c:
                return e
        return None

    def rune_at(self, r: int, c: int) -> Optional[RuneCluster]:
        for ru in self.runes:
            if ru.row == r and ru.col <= c < ru.col + len(ru.symbols):
                return ru
        return None

@dataclass
class Dungeon:
    name: str
    rooms: list[Room]  = field(default_factory=list)
    current_room: int  = 0
    seed: Optional[int] = None

    @property
    def room(self) -> Room:
        return self.rooms[self.current_room]
