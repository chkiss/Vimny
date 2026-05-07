from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Optional

class CellType(Enum):
    WALL     = auto()
    FLOOR    = auto()
    CORRIDOR = auto()
    WATER    = auto()

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
    answer: str                 = ''     # keystroke solution shown to admin

    def __post_init__(self):
        self._entity_map: dict = {}
        self._rune_map:   dict = {}

    # ── Spatial index ──────────────────────────────────────────────────────────

    def rebuild_indexes(self) -> None:
        """Rebuild O(1) lookup dicts from the current runes/entities lists.

        Call after any wholesale assignment to room.runes or room.entities,
        and after _ed_restore.  Individual add/remove helpers keep the indexes
        in sync incrementally and do not require a full rebuild.
        """
        self._entity_map = {(e.row, e.col): e for e in self.entities if e.alive}
        self._rune_map   = {}
        for ru in self.runes:
            for i in range(len(ru.symbols)):
                self._rune_map[(ru.row, ru.col + i)] = ru

    def add_entity(self, e: Entity) -> None:
        self.entities.append(e)
        if e.alive:
            self._entity_map[(e.row, e.col)] = e

    def remove_entity(self, e: Entity) -> None:
        self.entities.remove(e)
        self._entity_map.pop((e.row, e.col), None)

    def kill_entity(self, e: Entity) -> None:
        """Set alive=False and remove from the spatial index."""
        self._entity_map.pop((e.row, e.col), None)
        e.alive = False

    def move_entity(self, e: Entity, new_r: int, new_c: int) -> None:
        """Relocate an entity and keep the spatial index consistent."""
        self._entity_map.pop((e.row, e.col), None)
        e.row, e.col = new_r, new_c
        if e.alive:
            self._entity_map[(e.row, e.col)] = e

    def add_rune(self, ru: RuneCluster) -> None:
        self.runes.append(ru)
        for i in range(len(ru.symbols)):
            self._rune_map[(ru.row, ru.col + i)] = ru

    def remove_rune(self, ru: RuneCluster) -> None:
        self.runes.remove(ru)
        for i in range(len(ru.symbols)):
            self._rune_map.pop((ru.row, ru.col + i), None)

    # ── Lookup methods (O(1) with indexes built) ───────────────────────────────

    def cell(self, r: int, c: int) -> CellType:
        return self.cells[r][c]

    def is_passable(self, r: int, c: int) -> bool:
        if r < 0 or r >= self.rows or c < 0 or c >= self.cols:
            return False
        if self.passable_walls:
            return True
        return self.cells[r][c] in (CellType.FLOOR, CellType.CORRIDOR)

    def entity_at(self, r: int, c: int) -> Optional[Entity]:
        return self._entity_map.get((r, c))

    def rune_at(self, r: int, c: int) -> Optional[RuneCluster]:
        return self._rune_map.get((r, c))

@dataclass
class Dungeon:
    name: str
    rooms: list[Room]  = field(default_factory=list)
    current_room: int  = 0
    seed: Optional[int] = None

    @property
    def room(self) -> Room:
        return self.rooms[self.current_room]
