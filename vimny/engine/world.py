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

#: Kinds an authored `Entity.drops` may name. A level file is data and stays data,
#: but `drops` is the one field that CREATES an entity at runtime, so it is the one
#: field where an allowlist earns its keep: without it a downloaded level could set
#: `drops='warden'` on a goblin and hatch a boss the validator never counted. Loot
#: only — nothing here moves, fights, or blocks a path. Lives beside the field it
#: governs so the runtime and the validator can never be reading different lists.
DROPPABLE = frozenset({'floor_key', 'chest_random', 'chest_key',
                       'heart_container', 'gold', 'dynamite'})

#: Kinds that have been RENAMED, old name → current name. A kind is written into
#: every saved layout, every published community level and every forge draft on
#: disk, so a rename is a format change: files written before it still name the
#: old kind and must keep working. Load paths run names through
#: :func:`canonical_kind`; nothing writes an old name back out, so the alias is
#: one-way and the files heal themselves on the next save.
_KIND_ALIASES = {'chest': 'chest_random'}


def canonical_kind(kind: str) -> str:
    """The current name for a possibly-renamed entity kind."""
    return _KIND_ALIASES.get(kind, kind)


#: The banner a seal shows when it grinds back, if it names no other.
SEAL_OPENED = 'The words read true — a bolt grinds back!'


@dataclass(frozen=True)
class Seal:
    """A door held shut until the buffer READS a particular way.

    Vimny grew seven of these — the Cipher Cell, the Echo Vault, the Inscription
    Halls, the two register vaults, and the two big chassis families (`_ss_doors`
    across ten levels, `_wla_doors` across seven) — and every one was a tuple of
    coordinates a builder hardcoded onto the room, driven by its own bespoke
    tick. The same rule, written seven times, expressible in a level file zero
    times. This is that rule, named once, so a builder and an author declare it
    the same way.

    The law all seven obeyed and this one keeps: a seal is **recomputed from the
    buffer every turn and never remembered**. Opening is not an event that fires;
    it is a reading that happens to be true right now. That is the whole reason
    `u` re-shuts a door instead of leaving a level permanently solved by an edit
    the player took back.

    Four axes, which between them are everything the seven were doing:

    `scope` — WHERE to read. `region` reads one rectangle of the buffer, which is
    what an author who selected a strip and typed a password means. `anyrow`
    reads every floor row and is satisfied if ANY of them answers, which is what
    the chassis levels need: charwise edits do not shift rows but `dd`, `J`, `o`
    and `p` do, and a door that named a row number would be undone by the first
    line the player removed above it.

    `mode` — HOW to compare. `exact` against the whole (stripped) text, which is
    what prices a level whose kept words must SURVIVE the strike; `contains` for
    the looser substring rule the label doors use. Two modes read no text at
    all: `braziers` opens while every brazier in its region burns, and `gone`
    names ENTITY KINDS in `match` and opens while no live entity of any named
    kind stands anywhere in the room — the legion rule.

    `match` — a tuple of targets, ALL of which must read true. One door, several
    words: a chamber holds its bolt only while every one of its sayings still
    stands somewhere on the floor.

    `requires` — indices of EARLIER seals in the same room that must also read
    true. This is the FINAL SEAL, said as data: an exit that is stone until
    every bolt before it has opened. Earlier-only, so the conjunction can never
    make a cycle and can be evaluated in one pass. A seal with an empty `match`
    and a non-empty `requires` is pure conjunction; a seal with empty `opens` is
    a pure predicate that other seals can name.

    `anchor` — where `opens` really is. `''` means the coordinates are literal.
    `'exit_row'` replaces the ROW of every opened cell with the room's live
    `exit_pos[0]`, because `J` and `dd` slide everything below a cut upwards and
    `_shift_rows` keeps `exit_pos` true: the gate rides with the exit instead of
    being left behind on the row it was built on. Columns are never shifted, so
    they stay literal.
    """
    region:   tuple = ()    # (r1, c1, r2, c2) — the cells read under scope='region'
    match:    tuple = ()    # targets, ALL of which must read true (a bare str is
                            # accepted and wrapped — one target is the common case)
    opens:    tuple = ()    # ((row, col), ...) — cells that stand FLOOR while true
    mode:     str   = 'exact'
    scope:    str   = 'region'
    requires: tuple = ()    # indices of earlier seals that must also read true
    anchor:   str   = ''    # '' | 'exit_row'
    message:  str   = ''    # the banner when it opens; '' → SEAL_OPENED
    head:     int   = -1   # anyrow only: a matched row's first glyph must sit
                           # exactly at this column (the left-align law). -1 =
                           # any margin. The Gauntlet's cit door needs its <<.
    at:       int   = -1   # anyrow only: the PIN law — the target stands with
                           # its first glyph exactly at this column, whatever
                           # sits west of it (the plumb-line family: Alignment
                           # Halls' register). -1 = unpinned.

    def __post_init__(self):
        if isinstance(self.match, str):
            # One target, spelled the short way. Normalising here rather than at
            # every reader is what lets `match='password'` and `match=('a','b')`
            # be the same kind of thing downstream.
            object.__setattr__(self, 'match',
                               (self.match,) if self.match else ())
        else:
            object.__setattr__(self, 'match', tuple(self.match))
        object.__setattr__(self, 'opens', tuple(tuple(c) for c in self.opens))
        object.__setattr__(self, 'requires', tuple(int(i) for i in self.requires))

def gate_row_seals(doors, exit_pos, *, mode: str = 'exact',
                   head: int = -1,
                   at: int = -1,
                   bolt_message: str = '',
                   final_message: str = '',
                   final: bool = True) -> tuple:
    """The chassis, as seals: a row of bolts, then the exit behind all of them.

    `doors` is `((targets, col), ...)` — a bolt at `col` on the gate row, held
    open while every one of `targets` reads true somewhere on the floor. The
    gate row is not passed because it is not a fact: it is `exit_pos[0]`,
    re-read each turn (`anchor='exit_row'`), so a `dd` above the gate slides the
    bolts and the exit together. `head` names the left-align margin every
    reading row must start at; `at` pins the target's first glyph to a column
    with no margin law (the plumb-line family). -1 leaves each out.

    The final seal is the exit itself, requiring every bolt — stone until the
    whole level reads true, because since `A`/`o`/`O` a player can BUILD floor
    toward an unguarded exit and geometry alone no longer contains anything.
    """
    seals = [Seal(match=targets, opens=((exit_pos[0], col),), mode=mode,
                  scope='anyrow', head=head, at=at, anchor='exit_row',
                  message=bolt_message)
             for targets, col in doors]
    if final:
        seals.append(Seal(opens=(tuple(exit_pos),), anchor='exit_row',
                          requires=tuple(range(len(seals))),
                          message=final_message))
    return tuple(seals)


@dataclass
class Entity:
    kind: str           # 'wanderer', 'guard', 'chest_random', 'exit', etc.
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
    opaque:       bool = False  # a door the eye does NOT cross. The fog law is
                            # STONE-bounded on purpose — an ordinary door is a
                            # grille you see through, which is how a caged
                            # specimen is an exhibit rather than a rumour. But a
                            # door meant to hide what is behind it until it opens
                            # could not be said at all before this: fog is derived
                            # from geometry, and there is no geometry for "dark in
                            # here". Set it and `_vision_flood` stops at the door,
                            # so everything beyond starts fogged and is revealed
                            # by opening it — no scripted fog, nothing stored.
    shade:        int = 0   # cosmetic colour index — the impostor Wardens (goblin tag='echo')
                            # each pick a slightly different red so the player sees a myriad.
    drops:        str = ''  # what this leaves behind when it dies: a kind, optionally
                            # 'kind:tag' ('floor_key:gold'). A FIELD, not a rule about
                            # goblins — a zombie, a wanderer or a warden drops the same
                            # way, because the drop belongs to the creature an author
                            # placed and not to the level it was placed in.
    group:        str = ''  # drop-group id. With it set, the drop is left only when the
                            # LAST live member of the group dies — "kill the whole patrol
                            # and the key falls". Empty = each creature drops for itself.
    lit:          bool = True  # a brazier's flame. True → the 🜂 flame; False → cold
                            # embers (…) that a pasted fire lights. Default True so an
                            # author placing a brazier gets a lit one and every existing
                            # brazier entity stays lit. Meaningful only for kind='brazier';
                            # inert on anything else.
    password:     str = ''  # kind='fancy_door' only: the words that open it. The door
                            # is shut until you PASTE a register whose text reads
                            # exactly this (see engine.registers.clip_to_text), so the
                            # key to a fancy door is something you cut out of the floor
                            # rather than something you find lying on it.
                            #
                            # It is the mirror of a guard, and the level design turns on
                            # that. A guard punishes a cut that takes too LITTLE — it
                            # survives, and it is still standing when you reach the exit.
                            # Nothing punished a cut that took too MUCH, because every
                            # creature a `dw` kills a `d$` kills too, which is how a
                            # vault full of hand-placed guards still let `d$` clear six
                            # of its ten lessons for less than par. A door that reads
                            # what you are holding is the missing half: overshoot and
                            # the register carries extra words, and extra words are not
                            # the password. Between the two, exactly one motion fits.
                            #
                            # WHY THE REGISTER AND NOT THE FLOOR. The check is on the
                            # clip, never on the cells in front of the door — so no
                            # amount of inserting or deleting whitespace can shove the
                            # right word into the doorway and call it opened. That is
                            # the same rule a locked door already keeps (a key lying
                            # NEXT to one has never opened it), which is what lets this
                            # be taught as the familiar key-and-`p` model with a word
                            # for a key, rather than as a new mechanism.
    dropped:      bool = False  # runtime only: this carrier has already left its drop.
                            # The drop tick recomputes from the roster each turn, which
                            # respawned a key the moment it left the world — picked up
                            # AND spent (pasted onto a lock) it was neither lying about
                            # nor held, so it looked never-dropped and fell again. This
                            # marks the deed done. Undo-safe: it rides the entity through
                            # `clone_entity` snapshots, so reviving the carrier clears it
                            # and re-killing drops afresh. Never serialised — always False
                            # on a fresh build.


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
    reveal in vimny/game.py so an AoE and a single x cost the same: hit to unmask, hit
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
    if ent.kind == 'ally':                         # :s/g/d/ — a hound on your side
        return 'D' if ent.swole else 'd'
    if ent.kind == 'critter':                      # :s/g/c/ — a harmless cat
        return 'C' if ent.swole else 'c'
    if ent.kind == 'gold':                         # :s/g/$/ — a coin to pick up
        return '$'
    if ent.kind == 'elf':                          # :s/g/e/ — a merchant of bad bargains
        return 'e'
    return _ENTITY_LETTER.get(ent.kind)


# Floor-like markers the cursor passes THROUGH for ^ / first-non-blank (you stand
# on them). Every OTHER live entity (a foe, key, chest, heart…) counts as content
# the caret lands on.
CARET_TRANSPARENT = frozenset({'door', 'locked_door', 'seal_door', 'exit',
                               'entry_marker', 'boss_seal', 'horse', 'fancy_door'})

#: Entities the cursor may not occupy. A shut door is a wall that can be opened,
#: and everything that reads the map has to agree on that: feet (`is_passable`),
#: the line scans (`_cross_water`, `_SCAN_BLOCK`), and — since 2026-08-02 — the
#: cursor advance of every verb that WRITES a cell and steps to the next one
#: (`i`/`a`/`A`/`r`/`R`). Those verbs used to check the CELL alone, and a door
#: sits on ordinary floor, so typing at the cell before one walked the cursor
#: straight through it while `l` refused. Named once here because a blocker that
#: only some of the readers know about is a hole in every wall it stands in.
BLOCKING_KINDS = ('locked_door', 'shield', 'seal_door', 'boss_seal', 'fancy_door')


def blocked_by_entity(room, r: int, c: int) -> bool:
    """Is (r, c) held by a live blocking entity?"""
    ent = room.entity_at(r, c)
    return ent is not None and ent.kind in BLOCKING_KINDS


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
    #: VEILED PLAQUES — wall cells whose carved text is not readable yet.
    #:
    #: Deliberately NOT fog. Fog is the stone law: a physical fact about what
    #: the eye can reach, derived from the walls, and its universe is the cells
    #: you could stand in (`_FOGGABLE_CELLS`). A plaque hidden until the
    #: firelight reaches it is not physics at all — it is a puzzle handing out
    #: its clue in instalments, and it lives on WALL cells, which the law can
    #: never speak about.
    #:
    #: Three levels used to say it by putting wall cells into `fog_cells`, and
    #: every one of them then had to be excused from the fog audits and from the
    #: round-trip probe — an exception per level for a mechanic they shared.
    #: This is the same implementation (the renderer draws a veiled cell as bare
    #: stone) under its own name, so neither rule has to make room for the
    #: other. Reveal by discarding from this set, exactly as fog is lifted.
    veiled_cells: set           = field(default_factory=set)
    mist_cells: set             = field(default_factory=set)  # PERMANENT scenic mist over water:
                                                              # a subset of fog_cells that reveal
                                                              # floods neither cross nor clear
                                                              # (immutable per level — no snapshot)
    seals: tuple                = ()     # Seal objects — declarative text-match doors.
                                         # Empty for every shipped level today; the
                                         # five hardcoded families keep their own ticks
                                         # until they are worth porting. Driven by
                                         # `_seal_tick`, which no-ops on an empty tuple,
                                         # so carrying it costs nothing.
    passable_walls: bool        = False  # if True, walls are walkable (editor mode)
    answer: str                 = ''     # keystroke solution shown to admin
    answer_pos: int             = 0      # non-space chars of answer consumed by admin
    answer_diverged: bool       = False  # admin pressed a wrong key
    wood_damage: dict           = field(default_factory=dict)  # (r,c) -> half-steps received (1=cracked)
    sealed_cells: set           = field(default_factory=set)   # (r,c) of every GATE cell: a wall some
                                                               # level opens (and may re-shut).
                                                               # DERIVED, never authoritative. The
                                                               # renderer bands a cell only while it is
                                                               # STILL WALL, so opening and re-sealing
                                                               # need no bookkeeping — the cell flip
                                                               # shows both. Written by whichever code
                                                               # knows the live coordinates: at build
                                                               # time for fixed gates, but rewritten each
                                                               # tick where the row can move (the annex
                                                               # chassis derives its gate row from
                                                               # exit_pos, since J slides rows up). Never
                                                               # snapshot it: it is recomputed, not state.
    wrap_buffer: bool           = False  # single-line text buffer (rows==1); ':set wrap' soft-wraps it across screen rows (The Archivist's Library)
    # `/` search overlays entity glyphs (so /W finds the Warden, /g a goblin).
    # ON everywhere. Safe because no answer-tape letter collides with an entity
    # glyph, and the only exit-adjacent entities (grandmaster W, warden_eternal
    # + hall_of_echoes goblins) sit behind seals — so no /entity jump cheeses a par.
    search_glyph_entities: bool = True
    wrap_width:           int   = 0      # fixed ':set wrap' fold width (0 = wrap to live content width); the Wardenverse pins it so stone walls land at fold edges on any terminal.

    def __post_init__(self):
        self._entity_map:    dict = {}
        self._char_run_map:      dict = {}
        self._entity_by_kind: dict = {}   # kind -> list[Entity] (includes dead)
        self._char_run_rows:      set  = set() # rows that contain at least one rune
        self._char_runs_by_row:    dict = {}   # row -> list[CharRun]
        self._last_void_falls:     list = []   # (row,col,sym) shoved into the void by the last reflow op (vimny/engine/reflow.py)
        self._last_drowns:         list = []   # (row,col) goblins a reflow wave of water rolled over (vimny/engine/reflow.py)
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
        # Only clear the index slot if THIS entity owns it: two live entities
        # can share a cell (paste-backs spawn onto occupied cells), and the
        # slot belongs to whichever add_entity saw last — popping unconditionally
        # would orphan the survivor from every entity_at() reader.
        if self._entity_map.get((e.row, e.col)) is e:
            self._entity_map.pop((e.row, e.col), None)
        _kl = self._entity_by_kind.get(e.kind)
        if _kl:
            try:
                _kl.remove(e)
            except ValueError:
                pass

    def kill_entity(self, e: Entity) -> None:
        """Set alive=False and remove from the spatial index."""
        if self._entity_map.get((e.row, e.col)) is e:   # see remove_entity — stacked entities share a slot
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
        return ent is None or ent.kind not in BLOCKING_KINDS

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
