from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum, auto
from itertools import count as _count
from typing import Optional

_uid_seq = _count(1)   # stable per-run counter; preserved through snapshots via explicit copy

class CellType(Enum):
    WALL      = auto()
    FLOOR     = auto()
    CORRIDOR  = auto()
    WATER     = auto()
    WOOD_WALL = auto()  # destructible: 2 half-steps of damage to destroy

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
    hp: int   = 1
    alive: bool = True
    max_hp:       int = 0   # 0 = non-combatant; >0 = combatant
    ai:           str = ''  # 'chase' | '' (stationary/non-combatant)
    ai_speed:     int = 1   # move every N player turns
    ai_tick:      int = 0   # counts up; entity moves when ai_tick % ai_speed == 0
    summon_timer:       int = 0   # ticks down each turn; spawns goblin when it hits 0
    goblin_free_turns:  int = 2   # turns elapsed with no live goblins (>=2 allows auto-spawn)
    # --- identity & movement state (must be copied in _snapshot) ---
    uid:          int = field(default_factory=lambda: next(_uid_seq))
    summoner_uid: int = 0   # uid of the entity that spawned this (0 = not spawned)
    origin_row:   int = -1  # starting row for bounded-oscillation entities (-1 = not set)
    move_dir:     int = 1   # oscillation direction: +1 = down (row+1), -1 = up (row-1)
    tag:          str = ''  # variant tag, e.g. 'gold' or 'red' for colored keys/doors
    scroll_id:    str = ''  # chest_scroll only: the specific scroll this chest drops
                            # ('' = pull a random relic scroll from the pool)

@dataclass
class CharRun:
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
    char_runs: list[CharRun]    = field(default_factory=list)
    entities: list[Entity]      = field(default_factory=list)
    spawn_pos: tuple[int,int]    = (0, 0)   # player spawn + par-solver/fog start (NOT a gg target — gg/G are buffer-relative)
    exit_pos: Optional[tuple[int,int]] = None
    budget: Optional[int]       = None
    par: Optional[int]          = None
    seed: Optional[int]         = None
    fog_cells: set              = field(default_factory=set)  # (r,c) pairs not yet visible
    passable_walls: bool        = False  # if True, walls are walkable (editor mode)
    answer: str                 = ''     # keystroke solution shown to admin
    answer_pos: int             = 0      # non-space chars of answer consumed by admin
    answer_diverged: bool       = False  # admin pressed a wrong key
    wood_damage: dict           = field(default_factory=dict)  # (r,c) -> half-steps received (1=cracked)
    ledge_rows: set             = field(default_factory=set)   # rows that REFLOW (open to the void); empty = overlay (see engine/reflow.py)
    wrap_buffer: bool           = False  # single-line text buffer (rows==1); ':set wrap' soft-wraps it across screen rows (The Archivist's Library)

    def __post_init__(self):
        self._entity_map:    dict = {}
        self._char_run_map:      dict = {}
        self._entity_by_kind: dict = {}   # kind -> list[Entity] (includes dead)
        self._char_run_rows:      set  = set() # rows that contain at least one rune
        self._char_runs_by_row:    dict = {}   # row -> list[CharRun]
        self._last_void_falls:     list = []   # (row,col,sym) shoved into the void by the last reflow op (engine/reflow.py)
        self._last_drowns:         list = []   # (row,col) goblins a reflow wave of water rolled over (engine/reflow.py)
        self._last_build_blocked = None        # None | 'edge' | 'void' — why A/J's last ledge-build refused

    # ── Spatial index ──────────────────────────────────────────────────────────

    def rebuild_indexes(self) -> None:
        """Rebuild O(1) lookup dicts from the current character and entity lists.

        Call after any wholesale assignment to room.char_runs or room.entities,
        and after _ed_restore.  Individual add/remove helpers keep the indexes
        in sync incrementally and do not require a full rebuild.
        """
        self._entity_map = {(e.row, e.col): e for e in self.entities if e.alive}
        self._entity_by_kind = {}
        for e in self.entities:
            self._entity_by_kind.setdefault(e.kind, []).append(e)
        self._char_run_map   = {}
        self._char_runs_by_row = {}
        for ru in self.char_runs:
            for i in range(len(ru.symbols)):
                self._char_run_map[(ru.row, ru.col + i)] = ru
            self._char_runs_by_row.setdefault(ru.row, []).append(ru)
        self._char_run_rows = {ru.row for ru in self.char_runs}
        # Normalize WORD colors: adjacent non-void clusters on the same row all
        # take the leftmost cluster's kind so a WORD renders in one color.
        by_row: dict = {}
        for ru in self.char_runs:
            by_row.setdefault(ru.row, []).append(ru)
        for row_runes in by_row.values():
            row_runes.sort(key=lambda r: r.col)
            i = 0
            while i < len(row_runes):
                ru = row_runes[i]
                if ru.kind == 'void':
                    i += 1
                    continue
                word_kind = ru.kind
                j = i + 1
                while j < len(row_runes):
                    prev, curr = row_runes[j - 1], row_runes[j]
                    if prev.col + len(prev.symbols) == curr.col and curr.kind != 'void':
                        curr.kind = word_kind
                        j += 1
                    else:
                        break
                i = j

    def add_entity(self, e: Entity) -> None:
        self.entities.append(e)
        if e.alive:
            self._entity_map[(e.row, e.col)] = e
        self._entity_by_kind.setdefault(e.kind, []).append(e)

    def remove_entity(self, e: Entity) -> None:
        self.entities.remove(e)
        self._entity_map.pop((e.row, e.col), None)
        _kl = self._entity_by_kind.get(e.kind)
        if _kl:
            try:
                _kl.remove(e)
            except ValueError:
                pass

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

    def add_char_run(self, ru: CharRun) -> None:
        self.char_runs.append(ru)
        for i in range(len(ru.symbols)):
            self._char_run_map[(ru.row, ru.col + i)] = ru
        self._char_runs_by_row.setdefault(ru.row, []).append(ru)
        self._char_run_rows.add(ru.row)

    def remove_char_run(self, ru: CharRun) -> None:
        self.char_runs.remove(ru)
        for i in range(len(ru.symbols)):
            self._char_run_map.pop((ru.row, ru.col + i), None)
        _rl = self._char_runs_by_row.get(ru.row)
        if _rl:
            try:
                _rl.remove(ru)
            except ValueError:
                pass
            if not _rl:
                del self._char_runs_by_row[ru.row]
                self._char_run_rows.discard(ru.row)

    # ── Lookup methods (O(1) with indexes built) ───────────────────────────────

    def cell(self, r: int, c: int) -> CellType:
        return self.cells[r][c]

    def is_passable(self, r: int, c: int) -> bool:
        if r < 0 or r >= self.rows or c < 0 or c >= self.cols:
            return False
        if self.passable_walls:
            return True
        if self.cells[r][c] not in (CellType.FLOOR, CellType.CORRIDOR):
            return False
        if (r, c) in self.fog_cells:
            return False
        ent = self.entity_at(r, c)
        return ent is None or ent.kind not in ('locked_door', 'shield', 'seal_door', 'boss_seal')

    def damage_wood_wall(self, r: int, c: int, half_steps: int = 1) -> bool:
        """Deal half_steps of damage to wood wall at (r, c).

        Returns True if destroyed (cell becomes FLOOR); False if still standing.
        """
        current = self.wood_damage.get((r, c), 0)
        total   = current + half_steps
        if total >= 2:
            self.cells[r][c] = CellType.FLOOR
            self.wood_damage.pop((r, c), None)
            return True
        self.wood_damage[(r, c)] = total
        return False

    def entity_at(self, r: int, c: int) -> Optional[Entity]:
        return self._entity_map.get((r, c))

    def char_run_at(self, r: int, c: int) -> Optional[CharRun]:
        return self._char_run_map.get((r, c))

@dataclass
class Dungeon:
    name: str
    rooms: list[Room]  = field(default_factory=list)
    current_room: int  = 0
    seed: Optional[int] = None

    @property
    def room(self) -> Room:
        return self.rooms[self.current_room]
