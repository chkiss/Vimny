# Vimny — a Vim-teaching dungeon crawler.
# Copyright (C) 2026 Chas Kissick
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.
#
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations
from dataclasses import dataclass, field, replace as _dc_replace
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
    swole:        bool = False  # a goblin ~-toggled into a bigger 'G' (Easter egg)
    edit_immune:  bool = False  # True = survives editing-delete (visual/operator x/d/dd,
                            # reflow remove_row); a boss parried by its shield, chipped
                            # only by normal-mode x. See engine/visual + The Warden Pathfinder.
    shade:        int = 0   # cosmetic colour index — the impostor Wardens (goblin tag='echo')
                            # each pick a slightly different red so the player sees a myriad.


def clone_entity(e: Entity, fresh_uid: bool = False, **overrides) -> Entity:
    """Field-complete Entity copy — the ONE way to snapshot/duplicate an entity,
    so new fields can never silently drop out of a copy again. Keeps the uid
    (snapshot identity) unless ``fresh_uid`` (a paste-back is a new creature)."""
    if fresh_uid:
        overrides.setdefault('uid', next(_uid_seq))
    return _dc_replace(e, **overrides)


def strike_disguise(ent) -> bool:
    """An editing-delete (visual/operator AoE) or `x` lands on `ent`.

    A disguised impostor (goblin tag='echo', a false Warden) is REVEALED rather
    than removed: the disguise sloughs off (→ a plain 'g' that `/W` no longer
    finds) and it survives the hit. Returns True if the caller should remove the
    entity, False if it only lost its disguise and lives on. Mirrors the x-combat
    reveal in main.py so an AoE and a single x cost the same: hit to unmask, hit
    to kill."""
    if ent.kind == 'goblin' and ent.tag == 'echo':
        ent.tag = ''
        ent.hp -= 1
        if ent.hp > 0:
            return False
    return True


# ── The entity glyph layer: ONE source of truth for what an entity paints ─────
# Every targeting command (f/F/t/T, / ? * #, ^, gg/G) must agree with the glyph
# the renderer draws ON TOP of the text/terrain. Historically each consumer
# (render._ent_cell_str, motion._cell_char, search._entity_glyph, the caret
# stops) kept its OWN copy of this map, and they drifted — the recurring class of
# "the command can't see the entity sitting on text" bug. Define each fact once
# here; the consumers import these and stay in lockstep.

_ENTITY_LETTER = {'warden': 'W', 'dynamite': '!', 'archivist': 'A'}


def entity_letter(ent) -> Optional[str]:
    """The findable/searchable LETTER an entity paints — the character the renderer
    shows on top of its cell — or None for kinds drawn as decorative symbols
    (doors, keys, chests, hearts, exits, shields…) that aren't text-matchable by
    f/t and /. This is what f/F/t/T and search target, and what the renderer's
    letter-kinds draw, so changing a glyph here updates every command at once."""
    if ent.kind == 'goblin':
        if ent.tag == 'echo':
            return 'W'                             # echo goblins are the Hunt's impostor Ws
        if ent.tag == 'zombie':
            return 'Z'                             # :s/g/z/ raised the dead
        if ent.tag == 'demon':
            return '&'                             # :s/g/&/ summoned something worse
        return 'G' if ent.swole else 'g'           # ~-toggled goblins grow into a 'G'
    return _ENTITY_LETTER.get(ent.kind)


# Floor-like markers the cursor passes THROUGH for ^ / first-non-blank (you stand
# on them). Every OTHER live entity (a foe, key, chest, heart…) counts as content
# the caret lands on.
CARET_TRANSPARENT = frozenset({'door', 'locked_door', 'seal_door', 'exit',
                               'entry_marker', 'boss_seal'})


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
    mist_cells: set             = field(default_factory=set)  # PERMANENT scenic mist over water:
                                                              # a subset of fog_cells that reveal
                                                              # floods neither cross nor clear
                                                              # (immutable per level — no snapshot)
    passable_walls: bool        = False  # if True, walls are walkable (editor mode)
    answer: str                 = ''     # keystroke solution shown to admin
    answer_pos: int             = 0      # non-space chars of answer consumed by admin
    answer_diverged: bool       = False  # admin pressed a wrong key
    wood_damage: dict           = field(default_factory=dict)  # (r,c) -> half-steps received (1=cracked)
    wrap_buffer: bool           = False  # single-line text buffer (rows==1); ':set wrap' soft-wraps it across screen rows (The Archivist's Library)
    search_glyph_entities: bool = True   # / search overlays entity glyphs (so /W finds the Warden, /g a goblin) — ON everywhere as of 2026-07-21. Audited: no answer-tape letter collides with an entity glyph, and the only exit-adjacent entities (grandmaster W, warden_eternal + hall_of_echoes goblins) sit behind seals, so no /entity jump cheeses a par. Full suite passes forced-on.
    wrap_width:           int   = 0      # fixed ':set wrap' fold width (0 = wrap to live content width); the Wardenverse pins it so stone walls land at fold edges on any terminal.

    def __post_init__(self):
        self._entity_map:    dict = {}
        self._char_run_map:      dict = {}
        self._entity_by_kind: dict = {}   # kind -> list[Entity] (includes dead)
        self._char_run_rows:      set  = set() # rows that contain at least one rune
        self._char_runs_by_row:    dict = {}   # row -> list[CharRun]
        self._last_void_falls:     list = []   # (row,col,sym) shoved into the void by the last reflow op (engine/reflow.py)
        self._last_drowns:         list = []   # (row,col) goblins a reflow wave of water rolled over (engine/reflow.py)
        self._last_build_blocked: str | None = None   # None | 'edge' | 'void' — why A/J's last ledge-build refused

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
        for r in self._char_runs_by_row:
            normalize_row_word_kinds(self, r)

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

    def _on_entity_destroyed(self, e: Entity) -> None:
        """Clear a landmark position when its marker entity is destroyed by an
        editing op (reflow drown, x/dd cut, range delete): the exit marker frees
        exit_pos; the entry marker resets spawn_pos to the default (1, 1)."""
        if e.kind == 'exit':
            self.exit_pos = None
        elif e.kind == 'entry_marker':
            self.spawn_pos = (1, 1)

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

    def is_passable(self, r: int, c: int) -> bool:
        if r < 0 or r >= self.rows or c < 0 or c >= self.cols:
            return False
        if self.passable_walls:
            return True
        if self.cells[r][c] not in (CellType.FLOOR, CellType.CORRIDOR):
            return False
        if (r, c) in self.fog_cells:
            return False
        if (r, c) in getattr(self, 'torn', ()):    # floor torn away by the Warden (temporary)
            return False
        ent = self.entity_at(r, c)
        return ent is None or ent.kind not in ('locked_door', 'shield', 'seal_door', 'boss_seal')

    def first_standable_row(self) -> int:
        """Grid row of buffer line 1 — the first row with a FLOOR/CORRIDOR cell. The
        bordering walls aren't lines, so line N = grid row first_standable_row() + N - 1
        and `gg`/`1G` land here. Layout-based (ignores fog/doors) so numbering is stable."""
        for r in range(self.rows):
            row = self.cells[r]
            if any(row[c] in (CellType.FLOOR, CellType.CORRIDOR) for c in range(self.cols)):
                return r
        return 0

    def first_standable_col(self) -> int:
        """Grid col of buffer column 1 — the first column with a FLOOR/CORRIDOR cell
        (the left border isn't a column). Column N = first_standable_col() + N - 1."""
        for c in range(self.cols):
            if any(self.cells[r][c] in (CellType.FLOOR, CellType.CORRIDOR) for r in range(self.rows)):
                return c
        return 0

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

# Mechanic-bearing kinds: their identity drives game rules (void = lethal sink,
# flame/pedestal = the Beacon Tiers' locks), so a WORD-color normalization
# must never repaint them.
_PINNED_KINDS = ('void', 'flame', 'pedestal')


def normalize_row_word_kinds(room: Room, row: int) -> None:
    """Normalize WORD colors on one row: adjacent non-pinned clusters all take
    the leftmost cluster's kind so a WORD renders in one color. Skipped on a
    wrap_buffer room (single-line library: each region keeps its own colour).
    Called by rebuild_indexes for every row and by the row-scoped merge."""
    if getattr(room, 'wrap_buffer', False):
        return
    row_runes = sorted(room._char_runs_by_row.get(row, []), key=lambda r: r.col)
    i = 0
    while i < len(row_runes):
        ru = row_runes[i]
        if ru.kind in _PINNED_KINDS:
            i += 1
            continue
        word_kind = ru.kind
        j = i + 1
        while j < len(row_runes):
            prev, curr = row_runes[j - 1], row_runes[j]
            if prev.col + len(prev.symbols) == curr.col and curr.kind not in _PINNED_KINDS:
                curr.kind = word_kind
                j += 1
            else:
                break
        i = j


@dataclass
class Dungeon:
    name: str
    rooms: list[Room]  = field(default_factory=list)
    current_room: int  = 0
    seed: Optional[int] = None

    @property
    def room(self) -> Room:
        return self.rooms[self.current_room]
