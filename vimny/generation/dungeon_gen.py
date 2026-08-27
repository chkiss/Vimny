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

"""Assemble a dungeon from rooms joined by corridors into a single grid."""
from __future__ import annotations
import heapq, math, os, random
from collections import deque
from vimny.engine.world import (Dungeon, Room, RoomType, CellType, CharRun, Entity,
                          Seal, gate_row_seals)
from vimny.engine.tape import ESC as _TAPE_ESC
from vimny.engine.motion import (_fog_unreachable, _cell_char, _is_word_char,
                           apply_stone_fog, _FOG_BLOCK_KINDS,
                           _first_non_blank_col)
from vimny.generation.room_gen import make_room, RUNE_CHAR as _RUNE_CHAR
from vimny.content import passwords as _passwords

def _lay_dark(room, cells) -> None:
    """Hide a whole region, each cell by the right mechanism.

    A region a level wants dark is usually BOTH kinds of cell at once — the
    floor of a sealed hall and the inscriptions on its walls. Those are two
    different facts: the floor is fogged because the eye cannot reach it (the
    stone law, derived), and the wall is veiled because its carving is not
    legible yet (a puzzle, declared). Putting the walls in `fog_cells` is what
    used to make these levels exceptions to every fog rule they touched.
    """
    from vimny.engine.motion import _FOGGABLE_CELLS as _FC
    for (r, c) in cells:
        if room.cells[r][c] in _FC:
            room.fog_cells.add((r, c))
        else:
            room.veiled_cells.add((r, c))


def _doors_block_sight(room) -> None:
    """Say a level's darkness with its DOORS, not with a list of cells.

    `_fog_unreachable` floods by FEET — every closed door stops it, and "door"
    here is `_FOG_BLOCK_KINDS`: the plain and locked ones, and the seal doors and
    boss seals too — so the fog it lays is exactly "everything behind a shut
    door". That is a real rule, but
    it was written down as the resulting cells, and a level file has no way to
    say a set of cells is dark. `Entity.opaque` says the rule instead: this door
    is one the eye does not cross. The law then derives the same fog from the
    walls and the doors, which means the forge can round-trip it, a wall moved
    in the editor takes the darkness with it, and there is nothing to re-run.

    Only for levels where the two agree EXACTLY — checked cell for cell, per
    seed. A level whose fog is a lit-radius or a scripted darkness is not this
    rule and keeps its own fog list (see `tests/test_round_trip.py` KNOWN_GAPS).

    One deliberate consequence: `apply_stone_fog` marks the room `auto_fog`, so
    the pocket now lifts as sight crosses the opened door rather than waiting
    for `_reveal_from` to be called at the unlock. Same moment, fewer moving
    parts — and a closed opaque door still stops the eye from either side.
    """
    for e in room.entities:
        if e.kind in _FOG_BLOCK_KINDS:
            e.opaque = True
    room.rebuild_indexes()          # the law asks `entity_at` for opacity
    apply_stone_fog(room)


_DIR_CHAR = {(-1, 0): 'k', (1, 0): 'j', (0, -1): 'h', (0, 1): 'l'}
_DIRS = ((-1, 0), (1, 0), (0, -1), (0, 1))   # k j h l — the order every solver scans


# ── The two door chassis ──────────────────────────────────────────────────────
# Seventeen levels are built on the same gate: a row of bolts west of the exit,
# each held open while its words read true on the floor, and the exit itself
# stone until all of them do. They differ in ONE thing — whether a bolt wants
# its word to BE a whole row or merely to appear somewhere on one — so that is
# the only thing these two wrappers differ in. Both hand off to
# `world.gate_row_seals`, which is also what the level format builds; there is
# no separate tick behind either of them any more.

def _chamber_gate(doors, exit_pos):
    """Bolts that want EXACT whole rows — the Sight Sanctum family (ten levels).

    Exactness is what prices these levels: the kept words must SURVIVE the
    strike, so a linewise cut that eats one is a dead route and a half-cleared
    row still reads false. `doors` is ``((targets, col), ...)``.
    """
    return gate_row_seals(
        doors, exit_pos, mode='exact',
        bolt_message="The chamber's words read true — the bolt grinds back!",
        final_message='Every chamber reads true — the final seal parts!')


def _seal_banners(dungeon,
                  bolt="The chamber's words read true — the bolt grinds back!",
                  final='Every chamber reads true — the final seal parts!'):
    """Re-apply the gate banners to a format-built room.

    `Seal.message` is deliberately not file-format data — an author-supplied
    banner is a text channel onto another player's screen — so a room built by
    `format.build()` carries seals whose banner fell back to the generic
    SEAL_OPENED wording. The shipped chassis gates hand their banners back
    here, post-materialisation, which is the whole answer Phase 6 owes the
    open-work table on engine-only seal messages."""
    from dataclasses import replace as _dc_replace
    room = dungeon.rooms[0]
    *bolts, last = room.seals
    room.seals = (tuple(_dc_replace(s, message=bolt) for s in bolts)
                  + (_dc_replace(last, message=final),))


def _label_gate(doors, exit_pos):
    """Bolts that want a word written SOMEWHERE — the Change Annex family (seven).

    A plaque names the true label and the bolt opens once that label stands on
    the floor, wherever it stands. `doors` is the Annex's own shape,
    ``((target, (row, col)), ...)`` — the row is dropped, because the gate row
    is the exit's and is re-read every turn (`Seal.anchor`).
    """
    return gate_row_seals(
        [(target, col) for target, (_row, col) in doors], exit_pos,
        mode='contains',
        bolt_message='The label reads true — the bolt grinds back!',
        final_message='Every label reads true — the final seal parts!')


# ── Par-solver toolkit ────────────────────────────────────────────────────────
# Shared least-keystroke machinery behind the per-level `_par_<slug>` solvers.
# Each solver supplies its own `neighbors` (its bespoke move set / constraints);
# the driver, the count-move expansion, and the segment scan live here once.

def _dijkstra(start, is_goal, neighbors):
    """Generic least-keystroke search. ``neighbors(node)`` yields
    ``(next_node, label, step_cost)`` triples; ``is_goal(node)`` ends the search.
    Returns ``(cost, prev, end_node)`` — ``cost`` is None and ``end_node`` None if
    unreachable; ``prev[node] = (parent, label)`` feeds :func:`_join_path`. Nodes
    must be orderable so heap ties break exactly as the hand-written
    ``heapq.heappush((cost, node))`` loops did, preserving each solver's path."""
    dist = {start: 0}
    prev = {start: None}
    heap = [(0, start)]
    while heap:
        cost, node = heapq.heappop(heap)
        if is_goal(node):
            return cost, prev, node
        if cost > dist.get(node, math.inf):
            continue
        for nxt, label, step in neighbors(node):
            g = cost + step
            if g < dist.get(nxt, math.inf):
                dist[nxt] = g
                prev[nxt] = (node, label)
                heapq.heappush(heap, (g, nxt))
    return None, prev, None


def _bfs(start, is_goal, neighbors):
    """Generic uniform-cost (unit-step) search — the BFS analogue of :func:`_dijkstra`,
    preserving FIFO exploration order so equal-length paths match the hand-written
    deque loops. ``neighbors(node)`` yields ``(next_node, label)`` pairs. Returns
    ``(cost, prev, end_node)``."""
    dist = {start: 0}
    prev = {start: None}
    q = deque([start])
    while q:
        node = q.popleft()
        if is_goal(node):
            return dist[node], prev, node
        for nxt, label in neighbors(node):
            if nxt not in dist:
                dist[nxt] = dist[node] + 1
                prev[nxt] = (node, label)
                q.append(nxt)
    return None, prev, None


def _count_moves(passable, r, c, max_n, landable=None, dirs=_DIRS):
    """Yield ``((nr, nc), label, cost)`` for count-n h/j/k/l moves from (r, c):
    n=1 costs 1, n>1 costs ``len(str(n)) + 1``. ``passable(rr, cc)`` gates each
    cell; the first blocked cell stops that direction (and all larger counts).
    If ``landable`` is given, a cell that is passable but not landable (e.g. a void
    rune) is skipped as a target while the count motion passes THROUGH it to larger
    n — matching the engine's final-cell-only void check. ``dirs`` sets the scan
    order (a solver whose hand-written loop ordered directions differently passes
    its own order so heap tie-breaks — and thus the chosen path — stay identical)."""
    for dr, dc in dirs:
        ch = _DIR_CHAR[(dr, dc)]
        for n in range(1, max_n + 1):
            nr, nc = r + dr * n, c + dc * n
            if not passable(nr, nc):
                break
            if landable is not None and not landable(nr, nc):
                continue
            yield (nr, nc), (ch if n == 1 else f'{n}{ch}'), (1 if n == 1 else len(str(n)) + 1)


def _word_motion_chain(step_fn, key, start, max_n, landable, base=1):
    """Yield ``((nr, nc), label, cost)`` for count-N word motions (Nw/Nb/Ne, NW/NB/NE,
    Nge/NgE, …) by chaining ``step_fn`` from ``start``. A target is yielded only when
    ``landable(nr, nc)``, but the chain advances through it either way — mirroring the
    engine, where the motion always lands and a larger count steps onward even past a
    cell that isn't a legal stop. ``base`` is the n=1 keystroke cost (1 for a single
    key like w/W; 2 for a two-key prefix like ge/gE); n>1 costs ``len(str(n)) + base``."""
    pos = start
    for n in range(1, max_n):
        nxt = step_fn(*pos)
        if nxt is None:
            return
        if landable(*nxt):
            yield nxt, (key if n == 1 else f'{n}{key}'), (base if n == 1 else len(str(n)) + base)
        pos = nxt


def _row_segment(passable_left, passable_right, c, cols):
    """Inclusive (left, right) column bounds of the horizontal segment containing
    column ``c``: scan left while ``passable_left(cc)``, right while
    ``passable_right(cc)``. Powers $ / 0 / ^, which may block differently on each
    side (e.g. fog only to the right)."""
    left = c
    for nc in range(c - 1, -1, -1):
        if not passable_left(nc):
            break
        left = nc
    right = c
    for nc in range(c + 1, cols):
        if not passable_right(nc):
            break
        right = nc
    return left, right


def _join_path(prev: dict, goal, merge_single: bool = True) -> str:
    """Reconstruct path from predecessor dict and return space-joined keystrokes.

    merge_single=True: compress consecutive single hjkl labels (e.g. 'l l l' → '3l').
    merge_single=False: labels already include counts; just join them.
    """
    labels: list[str] = []
    node = goal
    while prev.get(node) is not None:
        parent, lbl = prev[node]
        labels.append(lbl)
        node = parent
    labels.reverse()
    if not merge_single:
        return ' '.join(labels)
    result: list[str] = []
    i = 0
    while i < len(labels):
        lbl = labels[i]
        if lbl in ('h', 'j', 'k', 'l'):
            j = i + 1
            while j < len(labels) and labels[j] == lbl:
                j += 1
            n = j - i
            result.append(f'{n}{lbl}' if n > 1 else lbl)
            i = j
        else:
            result.append(lbl)
            i += 1
    return ' '.join(result)

# ── Level plans ───────────────────────────────────────────────────────────────

# The First Cave: Entry → Puzzle → Exit  (hjkl only)
LEVEL_0_PLAN = [
    (RoomType.ENTRY,  10, 18),
    (RoomType.PUZZLE, 10, 20),
    (RoomType.EXIT,   10, 16),
]

_RUNE_KINDS      = ['ancient', 'verdant', 'void', 'ember']
_WORD_RUNE_KINDS = ['ancient', 'verdant', 'ember']   # non-void only
# Rune glyphs come from generation/room_gen.RUNE_CHAR (imported above) — the
# single source of truth; the kind LISTS stay here (their order seeds rng.choice).

_RUNE_MIN_LEN = 1     # normalized rune length range, identical for every kind
_RUNE_MAX_LEN = 7


def _make_rune_syms(rng, kind: str) -> tuple:
    """A rune run of a normalized random length (1.._RUNE_MAX_LEN) — the same rule
    for every kind (void included)."""
    return (_RUNE_CHAR[kind],) * rng.randint(_RUNE_MIN_LEN, _RUNE_MAX_LEN)

# ── The Rune Halls layout constants ──────────────────────────────────────────────────
_RUNE_HALLS_CORR_TOP_ROWS = (1, 4, 7, 10, 13)  # top row of each of the 5 corridors
_RUNE_HALLS_TOTAL_ROWS    = 16                  # rows 0-15
_RUNE_HALLS_TOTAL_COLS    = 48                  # cols 0-47
_RUNE_HALLS_CORR_LEFT     = 1
_RUNE_HALLS_CORR_RIGHT    = 46

# ── The Character Cataracts layout constants ──────────────────────────────────────────────────
_CHARACTER_CATARACTS_CORR_TOP_ROWS = (1, 4, 7, 10, 13)
_CHARACTER_CATARACTS_TOTAL_ROWS    = 16
_CHARACTER_CATARACTS_TOTAL_COLS    = 72
_CHARACTER_CATARACTS_CORR_LEFT     = 1
_CHARACTER_CATARACTS_CORR_RIGHT    = 70

_CHARACTER_CATARACTS_TURN_SPANS = [
    (2,  4,  69, 69),   # RT1: right side, single col, C1→C2
    (5,  7,   1,  2),   # LT1: left side,  C2→C3
    (8,  10, 69, 70),   # RT2: right side, C3→C4
    (11, 13,  1,  2),   # LT2: left side,  C4→C5
]

# Water pools per corridor: (row_tuple, col_start, col_end)
_CHARACTER_CATARACTS_WATER_SPANS = [
    ((1, 2),            14, 37),   # C1: Zone A cols 1-13, text cols 38-69
    ((4, 5),            30, 51),   # C2: text cols 3-29, Zone B cols 52-69
    ((4, 5, 6, 7),       1,  1),   # Left-edge strip: C2-C3 via LT1 col 2 only
    ((7, 8),            18, 31),   # C3: Zone A cols 1-17, Zone B cols 32-70
    ((10, 11),          26, 51),   # C4: Zone B cols 52-70, dynamite at col 1
    ((1, 2, 3, 4, 5),   70, 70),   # Right-edge strip (narrows RT1 to col 69)
]

# Visible text strings placed as CharRun symbols — f/F/t/T targets
_CHARACTER_CATARACTS_TEXT_C1  = "Most files you encounter"             # 'r' at offset 23 → col 67
_CHARACTER_CATARACTS_TEXT_C2  = " will be scribed in letters"             # 'w' at offset 1 → col 4
_CHARACTER_CATARACTS_TEXT_C3A = "so you can jump"                         # Zone A (cols 2-16)
_CHARACTER_CATARACTS_TEXT_C3B = "quite easily to anything you can type"  # t! lands at col 69 before dynamite at 70

def _scatter_row(composite, rng, row, c_start, c_end, kinds, blocked=frozenset()):
    """Greedily fill columns ``c_start..c_end`` (inclusive) on ``row`` with random
    character runs — a random kind from ``kinds`` and length 1.._RUNE_MAX_LEN, with
    exactly one blank column between consecutive runs. The single, normalized
    scatter primitive (gap = 1, inclusive right edge, no density knob).

    Edge handling:
      * A run whose natural length would overrun the right edge is clamped to fill
        the remaining space, or one cell short (leaving a trailing space).
      * Never two consecutive length-1 runs: after a length-1 run the next run is
        forced to length ≥ 2. If there isn't room for that at the right edge, we
        simply stop and leave the trailing cell empty — we never go back and
        rewrite the penultimate run.
      * ``blocked`` cells are never overlapped or touched (a placed run keeps a
        one-cell side buffer); a forced skip past a blocked cell breaks the
        length-1 chain."""
    c = c_start
    prev_len = 0
    while c <= c_end:
        avail   = c_end - c + 1
        min_len = 2 if prev_len == 1 else 1
        if avail < min_len:
            break                              # no room for an allowed run → leave trailing space
        natural = rng.randint(min_len, _RUNE_MAX_LEN)
        kind    = rng.choice(kinds)
        if natural <= avail:
            width = natural
        else:                                  # clamp: fill to the edge, or one short
            width = max(min_len, avail - rng.randint(0, 1))
        if blocked and any((row, cc) in blocked for cc in range(c - 1, c + width + 1)):
            c += 1
            prev_len = 0                       # a forced gap breaks the consecutive-run chain
            continue
        composite.char_runs.append(
            CharRun(row=row, col=c, symbols=(_RUNE_CHAR[kind],) * width, kind=kind))
        prev_len = width
        c += width + 1                         # exactly one blank column between runs


def _place_runes_in_room(composite, rng, col_offset, room_rows, room_cols, total_rows,
                         kinds=_RUNE_KINDS):
    """Greedily fill every interior row of one composite-grid room with character runs.
    ``kinds`` defaults to the full set (incl. void); pass the void-free word set for
    rooms that have no path-carving / passability retry of their own."""
    row_offset = (total_rows - room_rows) // 2
    col_end = col_offset + room_cols - 2
    for r in range(row_offset + 1, row_offset + room_rows - 1):
        _scatter_row(composite, rng, r, col_offset + 2, col_end, kinds)


def _carve_void_path(composite, protected=frozenset()):
    """Guarantee an entry→exit route through a void-packed room: BFS a floor path
    (cells are passable terrain; void is a glyph overlay, so it doesn't block the
    BFS) while routing AROUND any ``protected`` cells, then delete every void run
    lying on that route. ``protected`` void runs (e.g. hard-coded guards) are kept
    and steered around. Returns True if a route was secured."""
    entry, goal = composite.spawn_pos, composite.exit_pos
    prev = {entry: None}
    q = deque([entry])
    while q:
        cur = q.popleft()
        if cur == goal:
            break
        r, c = cur
        for dr, dc in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            nb = (r + dr, c + dc)
            if nb in prev or nb in protected:
                continue
            nr, nc = nb
            if 0 <= nr < composite.rows and 0 <= nc < composite.cols \
                    and composite.is_passable(nr, nc):
                prev[nb] = cur
                q.append(nb)
    if goal not in prev:
        return False
    route, n = set(), goal
    while n is not None:
        route.add(n)
        n = prev[n]
    composite.char_runs = [
        ru for ru in composite.char_runs
        if not (ru.kind == 'void'
                and any((ru.row, ru.col + i) in route for i in range(len(ru.symbols))))
    ]
    return True


def _bfs_par(composite, return_path: bool = False):
    """Shortest path entry→exit treating void rune cells as impassable.
    Returns cost, or (cost, path_str) when return_path=True."""
    void_cells = {
        (ru.row, ru.col + i)
        for ru in composite.char_runs if ru.kind == 'void'
        for i in range(len(ru.symbols))
    }
    entry = composite.spawn_pos
    goal  = composite.exit_pos

    def passable(r, c):
        return composite.is_passable(r, c) and (r, c) not in void_cells

    def neighbors(node):
        for (nr, nc), label, _cost in _count_moves(passable, node[0], node[1], 1):
            yield (nr, nc), label

    cost, prev, end = _bfs(entry, lambda node: node == goal, neighbors)
    if return_path:
        return (cost, _join_path(prev, end, merge_single=False)) if cost is not None else (None, '')
    return cost

# The Counting Crypts: Entry → Puzzle → Exit  ([count] prefix with hjkl + ^$0)
_COUNTING_CRYPTS_PLAN = [
    (RoomType.ENTRY,  12, 20),
    (RoomType.PUZZLE, 12, 32),
    (RoomType.EXIT,   12, 18),
]


def _dijkstra_par_count(composite, allow_counts: bool = True) -> int | None:
    """Minimum keystroke cost entry→exit using count prefix.

    Cost model: 1 for a single step; len(str(n))+1 for a count-n move.
    Void rune cells are passable (CellType.FLOOR); a count motion passes
    through them and only the final landing cell triggers damage — matching
    engine behaviour in apply_motion.  Only true walls stop the search.

    ``allow_counts=False`` caps every move at one cell, for a level whose
    command set does not include the count prefix. Without the cap the bound
    is a route that level cannot legally play, which is worse than no bound:
    it is unreachable by construction and can never be met.

    That mode also refuses to land on a void rune. The pass-through licence
    above belongs to the count motion; a single step has no cells to pass
    through, so every cell it crosses is a landing cell and costs HP. A step
    route over a rune is not a route a clean run can take, so counting it
    would put the bound back below anything playable.
    """
    entry = composite.spawn_pos
    goal  = composite.exit_pos
    max_n = max(composite.rows, composite.cols) if allow_counts else 1

    def _landable(nr, nc):                       # passable, and not a void rune
        ru = composite.char_run_at(nr, nc)
        return composite.is_passable(nr, nc) and not (ru and ru.kind == 'void')

    def neighbors(node):
        return _count_moves(composite.is_passable, node[0], node[1], max_n,
                            landable=None if allow_counts else _landable)

    cost, _prev, _end = _dijkstra(entry, lambda node: node == goal, neighbors)
    return cost


def _par_counting_crypts(composite, door_cols: list, return_path: bool = False):
    """Full state-space Dijkstra for The Counting Crypts.

    State: (row, col, closed_mask) — bit i set means door_cols[i] is still closed.
    Commands modelled: count h/j/k/l, wall/fog-bounded $ ^ 0, and x (open door).
    Fog acts as the wall: movement is blocked at fog_col = first_closed_door_col + 1.
    Doors are passable floor tiles; x is pressed while standing ON the door.
    Each x costs 1 keystroke and does not move the player.
    """
    n = len(door_cols)
    all_closed = (1 << n) - 1
    entry = composite.spawn_pos
    goal  = composite.exit_pos
    max_n = max(composite.rows, composite.cols)

    # For each door column: set of (row, col) positions where x can open it
    # (player must be standing ON the door entity).
    trigger: list = []
    for dc in door_cols:
        pos = set()
        for e in composite.entities:
            if e.kind == 'door' and e.col == dc:
                pos.add((e.row, e.col))
        trigger.append(pos)

    def get_fog_col(closed):
        for i in range(n):
            if (closed >> i) & 1:
                return door_cols[i] + 1
        return -1

    def fog_blocks_col(col, closed):
        fc = get_fog_col(closed)
        return fc >= 0 and col >= fc

    def neighbors(node):
        r, c, closed = node
        def passable(rr, cc):                       # walls + fog (fog gates the column)
            return composite.is_passable(rr, cc) and not fog_blocks_col(cc, closed)
        # count h/j/k/l — stop at wall or fog
        for (nr, nc), label, cost in _count_moves(passable, r, c, max_n):
            yield (nr, nc, closed), label, cost
        # the wall-bounded (0: walls only) / wall+fog-bounded ($ ^: fog on the right) segment
        left, right = _row_segment(
            lambda cc: composite.is_passable(r, cc),
            lambda cc: composite.is_passable(r, cc) and not fog_blocks_col(cc, closed),
            c, composite.cols)
        if right != c:                              # $ — rightward to wall/fog
            yield (r, right, closed), '$', 1
        if left != c:                               # 0 — leftward to wall
            yield (r, left, closed), '0', 1
        tgt = left                                  # ^ — leftmost char in the segment
        for nc in range(left, right + 1):
            if composite.char_run_at(r, nc):
                tgt = nc
                break
        if tgt != c:
            yield (r, tgt, closed), '^', 1
        # x — open door at current cell (player stays put)
        for i in range(n):
            if (closed >> i) & 1 and (r, c) in trigger[i]:
                yield (r, c, closed ^ (1 << i)), 'x', 1

    start = (entry[0], entry[1], all_closed)
    cost, prev, end = _dijkstra(start, lambda node: (node[0], node[1]) == goal, neighbors)
    if return_path:
        return cost, _join_path(prev, end, merge_single=False)
    return cost


def build_dungeon_first_cave(seed: int) -> Dungeon:
    from vimny.engine.editor import _CELL_CODE
    from vimny.sharing.format import Level as _Level, build as _fmt_build
    rng = random.Random(seed)
    CORRIDOR_LEN = 4

    plan = LEVEL_0_PLAN
    total_cols = sum(c for _, _, c in plan) + CORRIDOR_LEN * (len(plan) - 1)
    total_rows = max(r for _, r, _ in plan)

    # A scratch room for the placement/carving helpers to mutate; the Level is
    # projected from it once the floor settles.
    scratch = Room(room_type=RoomType.ENTRY, rows=total_rows, cols=total_cols)
    cells = [[CellType.WALL] * total_cols for _ in range(total_rows)]
    scratch.cells = cells

    col_offset = 0
    offsets = []
    for room_type, rows, cols in plan:
        offsets.append(col_offset)
        r_seed = rng.randint(0, 2**31)
        room = make_room(room_type, rows, cols, r_seed)
        # Stamp room into grid
        for r in range(rows):
            for c in range(cols):
                gr = r + (total_rows - rows) // 2
                gc = c + col_offset
                cells[gr][gc] = room.cells[r][c]
        col_offset += cols + CORRIDOR_LEN

    # Carve corridors between rooms.
    # Must include the adjacent room walls (cols_l-1 and offsets[i+1]) so the
    # corridor is contiguous with each room's interior floor.
    for i in range(len(plan) - 1):
        _, _, cols_l = plan[i]
        left_right_edge = offsets[i] + cols_l - 1   # right wall of left room
        right_left_edge = offsets[i + 1]             # left wall of right room
        mid = total_rows // 2
        for c in range(left_right_edge, right_left_edge + 1):
            cells[mid][c]     = CellType.CORRIDOR
            cells[mid - 1][c] = CellType.CORRIDOR

    # Exit: top-left interior of Room 2 (col offsets[-1]+1).
    # Player arrives at corridor rows 4-5 at the left edge of Room 2 and must
    # go UP (k) — but void guards at rows 2-3 block the straight-up path,
    # forcing a right detour then back left (h) to reach the exit.
    # This guarantees all four of h/j/k/l are required on every seed.
    exit_col_offset = offsets[-1]
    ex_c = exit_col_offset + 1   # = 47, leftmost interior col of Room 2

    # Entry: top-left interior of Room 0 → forces the player to use j (down)
    # to reach the corridor, and k (up) to reach the exit.
    # The placer reads these to keep runes off the endpoints.
    scratch.spawn_pos = (1, 2)
    scratch.exit_pos  = (1, ex_c)

    # Greedily fill all three rooms (void runes included), then guarantee a route.
    rune_rng = random.Random(rng.randint(0, 2**31))
    for i, (_, room_rows, room_cols) in enumerate(plan):
        _place_runes_in_room(scratch, rune_rng, offsets[i],
                             room_rows, room_cols, total_rows)

    # Hard-coded void guards: block (2, ex_c) and (3, ex_c) so the player cannot
    # walk straight up from the corridor to the exit.  They must go right into
    # Room 2, up to row 1, then press h to reach the exit.  Remove any random
    # character that would shadow these hard-coded voids.
    for void_row in (2, 3):
        scratch.char_runs = [
            ru for ru in scratch.char_runs
            if not (ru.row == void_row
                    and ru.col <= ex_c < ru.col + len(ru.symbols))
        ]
    scratch.char_runs.append(CharRun(row=2, col=ex_c, symbols=('○',), kind='void'))
    scratch.char_runs.append(CharRun(row=3, col=ex_c, symbols=('○',), kind='void'))

    # Never leave a void rune sitting on the entry or exit itself.
    entry_r, entry_c = (1, 2)
    exit_r,  exit_c  = (1, ex_c)
    scratch.char_runs = [
        ru for ru in scratch.char_runs
        if ru.kind != 'void' or not any(
            (ru.row == r and ru.col <= c < ru.col + len(ru.symbols))
            for r, c in ((entry_r, entry_c), (exit_r, exit_c))
        )
    ]

    # The greedy fill packs the cave with void; clear void off one floor route to
    # the exit (steered around the row-2/3 guards so the forced detour survives),
    # guaranteeing the level is solvable.
    _carve_void_path(scratch, protected={(2, ex_c), (3, ex_c)})

    level = _Level(
        name='The First Cave', seed=seed,
        rows=total_rows, cols=total_cols,
        cells=[''.join(_CELL_CODE[c] for c in row) for row in cells],
        spawn=(1, 2), exit=(1, ex_c),
        char_runs=[{'row': ru.row, 'col': ru.col,
                    'symbols': ''.join(ru.symbols), 'kind': ru.kind}
                   for ru in scratch.char_runs],
        entities=[{'kind': 'exit', 'at': [1, ex_c]}])

    dungeon = _fmt_build(level)
    room = dungeon.rooms[0]
    par, path = _bfs_par(room, return_path=True)
    if par is None:
        par, path = 100, ''

    # Budget: ceil(par × 1.4) per spec formula.
    room.par    = par
    room.budget = math.ceil(par * 1.4)
    room.answer = path
    return dungeon


# ── The Line Halls layout (teaches $ ^ 0; + always-on :w :q) ──────────────────
# A fixed vertical serpentine of three single-row halls joined by one-cell
# doorways at alternating ends.  No counts exist yet, so walking costs one key
# per cell and each hall forces one line motion: $ (Hall A, doorway far right),
# 0 (Hall B, doorway at the bare left margin past a field of runes), ^ (Hall C,
# exit one l right of the first carved rune, behind an unmarked indent).
_LINE_HALLS_ROWS  = 7      # 0 wall · 1 Hall A · 2 sep · 3 Hall B · 4 sep · 5 Hall C · 6 wall
_LINE_HALLS_COLS  = 50     # 0 wall · 1..48 halls · 49 wall
_LINE_HALLS_LEFT  = 1
_LINE_HALLS_RIGHT = 48
_LINE_HALLS_A_ROW, _LINE_HALLS_B_ROW, _LINE_HALLS_C_ROW = 1, 3, 5
_LINE_HALLS_SPAWN = (_LINE_HALLS_A_ROW, _LINE_HALLS_LEFT)            # left end of Hall A
_LINE_HALLS_DOORS = ((2, _LINE_HALLS_RIGHT), (4, _LINE_HALLS_LEFT))  # A→B right, B→C left
_LINE_HALLS_B_FIRST_RUNE_COL = 9                  # Hall B indent (cols 1..8 blank) → 0 ≠ ^
_LINE_HALLS_C_FIRST_RUNE = (_LINE_HALLS_C_ROW, 10)        # ^ lands here…
_LINE_HALLS_EXIT = (_LINE_HALLS_C_ROW, 11)                # …then one l onto the exit

def _tile_line_hall(rng, row: int, c0: int, c1: int, first_non_void: bool = True) -> list:
    """Pack runes left→right across [c0, c1] with random kinds and lengths 1.._RUNE_MAX_LEN,
    one blank column between runs — the normalized scatter rule (gap 1, clamp-to-fit,
    never two consecutive length-1 runs). The first rune placed is forced non-void:
    apply_motion ^ halts on the first char_run of ANY kind while the par solver skips
    void, so a leading void rune would desync them. Void runes therefore only sit
    mid-hall (passed over by the line jumps) or right of the exit."""
    runs, c, first, prev_len = [], c0, first_non_void, 0
    while c <= c1:
        avail   = c1 - c + 1
        min_len = 2 if prev_len == 1 else 1
        if avail < min_len:
            break
        kind = rng.choice(_WORD_RUNE_KINDS) if first else rng.choice(_RUNE_KINDS)
        first = False
        natural = rng.randint(min_len, _RUNE_MAX_LEN)
        width = natural if natural <= avail else max(min_len, avail - rng.randint(0, 1))
        runs.append(CharRun(row=row, col=c, symbols=(_RUNE_CHAR[kind],) * width, kind=kind))
        prev_len = width
        c += width + 1
    return runs


def _line_jump_moves(composite, ok, r: int, c: int):
    """The LINE JUMPS a par solver must model: `gg`, `G`, `{n}G`.

    NOT named `_par_*`: everything with that prefix in this module is ONE
    LEVEL'S solver, and anything enumerating them (a scan, a reader, the next
    person adding a level) should not have to know that one of them is a shared
    helper wearing the same prefix.

    Yields `(row, col, cost, label)` for every line the cursor can reach in one
    jump, landing where the engine lands — the row's first character, or its
    first standable cell if the row carries no text (`apply_motion`'s
    `_first_non_blank_col`). `ok(row, col)` is the CALLER's passability, so a
    solver that models a shut door keeps modelling it: a jump onto a line whose
    landing cell is behind that door is not a move.

    WHY NO `H` / `M` / `L`. Those are viewport-relative whenever the room is
    taller than the game area (Vim-faithful), so a par derived from one would be
    a par only some terminal sizes could hit — and par has to mean one number.
    `G`/`gg`/`{n}G` read the BUFFER and are the same in every window, so they are
    what a solver may safely assume. The screen jumps are covered from the other
    end, by measurement: `vimny/sharing/jumpgolf.py` replays every tape at heights 25
    through 60 and only reports a beat that holds at all of them, which is how
    The Indentation Sanctum's `M` and The Stair Rail's `H` were found. Derived
    where derivation is sound, measured where it is not.

    Line N is grid row `first_standable_row() + N - 1` (the bordering walls are
    not lines), and a count costs its digits plus the key.
    """
    base  = composite.first_standable_row()
    lines = []
    for row in range(base, composite.rows):
        col = _first_non_blank_col(composite, row)
        if col is not None and ok(row, col):
            lines.append((row, col))
    if not lines:
        return
    for i, (row, col) in enumerate(lines, start=1):
        if (row, col) == (r, c):
            continue
        n = row - base + 1                      # the LINE number, not the index
        yield row, col, len(str(n)) + 1, f'{n}G'
    # The countless forms, which are what a golfed tape actually reaches for.
    first_row, first_col = lines[0]
    if (first_row, first_col) != (r, c):
        yield first_row, first_col, 2, 'gg'
    last_row, last_col = lines[-1]
    if (last_row, last_col) != (r, c):
        yield last_row, last_col, 1, 'G'


def _bfs_par_line(composite, return_path: bool = False,
                  allow=('$', '0', '^')):
    """BFS par for The Line Halls: hjkl (each cost 1) plus the line motions in
    `allow` ($ ^ 0, each cost 1).  `allow` lets the command-necessity tests drop
    one motion and confirm the cheapest remaining solve exceeds the budget.

    $ and ^ are wall-bounded: they stop at the nearest wall in each direction,
    matching apply_motion semantics.  Targets are precomputed per (row, col).
    """
    entry = composite.spawn_pos
    goal  = composite.exit_pos

    rune_cols_by_row: dict[int, list[int]] = {}
    for ru in composite.char_runs:
        if ru.kind == 'void':
            continue
        for i in range(len(ru.symbols)):
            rune_cols_by_row.setdefault(ru.row, []).append(ru.col + i)

    def neighbors(node):
        r, c = node
        for (nr, nc), label, _cost in _count_moves(composite.is_passable, r, c, 1):
            yield (nr, nc), label                     # hjkl, each cost 1 (no counts here)
        # wall-bounded segment containing (r, c) — no fog at the Line Halls
        left, right = _row_segment(lambda cc: composite.is_passable(r, cc),
                                   lambda cc: composite.is_passable(r, cc),
                                   c, composite.cols)
        if '$' in allow and right != c:
            yield (r, right), '$'
        if '0' in allow and left != c:
            yield (r, left), '0'
        if '^' in allow:
            runes = [rc for rc in sorted(rune_cols_by_row.get(r, [])) if left <= rc <= right]
            hat = runes[0] if runes else left
            if hat != c:
                yield (r, hat), '^'

    cost, prev, end = _bfs(entry, lambda node: node == goal, neighbors)
    if return_path:
        return (cost, _join_path(prev, end, merge_single=False)) if cost is not None else (None, '')
    return cost


def build_dungeon_line_halls(seed: int) -> Dungeon:
    """The Line Halls — teaches $ ^ 0 (+ always-on :w :q).

    A fixed vertical serpentine of three single-row halls joined by one-cell
    doorways at alternating ends.  No counts exist yet, so walking costs one key
    per cell and each hall forces exactly one line motion:

      Hall A (row 1): spawn at the far left; the only way down is a doorway at
        the far RIGHT                                                   → $
      Hall B (row 3): you arrive at the right; the doorway down is at the bare
        LEFT margin, but the hall is packed with carved runes, so ^ halts on
        the first rune mid-hall — only 0 reaches the margin             → 0
      Hall C (row 5): you arrive at the left; the exit sits one cell right of
        the first carved rune (cols 1..9 are an unmarked indent), so ^ jumps to
        that rune and one l steps onto the exit                         → ^

    Seed-independent (par 8 every seed).  Void runes appear only mid-hall —
    passed over by the line jumps — or right of the exit; every cell a motion
    lands on is safe.
    """
    from vimny.engine.editor import _CELL_CODE
    from vimny.sharing.format import Level as _Level, build as _fmt_build
    ROWS, COLS = _LINE_HALLS_ROWS, _LINE_HALLS_COLS
    L, R = _LINE_HALLS_LEFT, _LINE_HALLS_RIGHT

    grid = [[CellType.WALL] * COLS for _ in range(ROWS)]
    for hall_row in (_LINE_HALLS_A_ROW, _LINE_HALLS_B_ROW, _LINE_HALLS_C_ROW):
        for c in range(L, R + 1):
            grid[hall_row][c] = CellType.FLOOR
    for (dr, dc) in _LINE_HALLS_DOORS:          # one-cell doorways through the wall rows
        grid[dr][dc] = CellType.CORRIDOR

    # ── Carved runes (random per seed, like the other levels) ───────────────────
    # The structural anchors (indents, the col-10 ^ target, the unmarked exit, the
    # blank approaches) are fixed so the forcing holds for every seed; only the
    # filler runes' kinds, lengths and gaps vary.
    rng = random.Random(seed)
    runs: list = []
    # Hall A: packed; col 1 is the spawn and cols R-1..R the doorway approach (left blank).
    runs += [{'row': ru.row, 'col': ru.col, 'symbols': ''.join(ru.symbols),
              'kind': ru.kind} for ru in _tile_line_hall(rng, _LINE_HALLS_A_ROW, L + 1, R - 2)]
    # Hall B: cols 1..8 blank, so 0 reaches the bare margin while ^ stops at col 9.
    runs += [{'row': ru.row, 'col': ru.col, 'symbols': ''.join(ru.symbols),
              'kind': ru.kind} for ru in _tile_line_hall(rng, _LINE_HALLS_B_ROW, _LINE_HALLS_B_FIRST_RUNE_COL, R - 2)]
    # Hall C: one single-cell non-void rune just left of the exit (the ^ target),
    # then a field of runes to its right so $ overshoots.  The exit cell stays unmarked.
    fr_r, fr_c = _LINE_HALLS_C_FIRST_RUNE
    fr_kind = rng.choice(_WORD_RUNE_KINDS)
    runs.append({'row': fr_r, 'col': fr_c, 'symbols': _RUNE_CHAR[fr_kind],
                 'kind': fr_kind})
    runs += [{'row': ru.row, 'col': ru.col, 'symbols': ''.join(ru.symbols),
              'kind': ru.kind} for ru in _tile_line_hall(rng, _LINE_HALLS_C_ROW, _LINE_HALLS_EXIT[1] + 2, R - 2)]

    level = _Level(
        name='The Line Halls', seed=seed,
        rows=ROWS, cols=COLS,
        cells=[''.join(_CELL_CODE[c] for c in row) for row in grid],
        spawn=_LINE_HALLS_SPAWN, exit=_LINE_HALLS_EXIT,
        char_runs=runs,
        entities=[{'kind': 'exit', 'at': [_LINE_HALLS_EXIT[0],
                                          _LINE_HALLS_EXIT[1]]}])

    dungeon = _fmt_build(level)
    room = dungeon.rooms[0]
    # Par is SOLVED, not declared: the cheapest walk the BFS proves, and the
    # tape is that walk. (build() cannot know it yet; this is the derived-par
    # path, not an author-set one.)
    par, path = _bfs_par_line(room, return_path=True)
    room.par    = par
    room.budget = math.ceil(par * 1.4)
    room.answer = path
    return dungeon


def build_dungeon_counting_crypts(seed: int) -> Dungeon:
    """The Counting Crypts — teaches [count] prefix with hjkl + ^$0.

    Layout: ENTRY(12×20) ──4── PUZZLE(12×32) ──4── EXIT(12×18)
    Total: 78 cols.  Corridors at rows 5-6.

    Puzzle room has a vertical void wall at its horizontal midpoint (col 40),
    spanning rows 2-9.  The only safe crossings are row 1 and row 10.
    Reaching either requires count vertical moves (4k/5j/etc.).
    Budget is computed with keystroke-cost Dijkstra so count is genuinely
    more efficient than single-step: 5j costs 2 keystrokes, jjjjj costs 5.
    """
    from vimny.engine.editor import _CELL_CODE
    from vimny.sharing.format import Level as _Level, build as _fmt_build
    rng = random.Random(seed)
    CORRIDOR_LEN = 4

    plan = _COUNTING_CRYPTS_PLAN
    total_cols = sum(c for _, _, c in plan) + CORRIDOR_LEN * (len(plan) - 1)
    total_rows = max(r for _, r, _ in plan)  # 12

    cells = [[CellType.WALL] * total_cols for _ in range(total_rows)]

    col_offset = 0
    offsets = []
    for room_type, rows, cols in plan:
        offsets.append(col_offset)
        r_seed = rng.randint(0, 2**31)
        room = make_room(room_type, rows, cols, r_seed)
        for r in range(rows):
            for c in range(cols):
                gr = r + (total_rows - rows) // 2
                gc = c + col_offset
                cells[gr][gc] = room.cells[r][c]
        col_offset += cols + CORRIDOR_LEN

    # Carve corridors at mid rows (5-6)
    for i in range(len(plan) - 1):
        _, _, cols_l = plan[i]
        left_right_edge = offsets[i] + cols_l - 1
        right_left_edge = offsets[i + 1]
        mid = total_rows // 2
        for c in range(left_right_edge, right_left_edge + 1):
            cells[mid][c]     = CellType.CORRIDOR
            cells[mid - 1][c] = CellType.CORRIDOR

    # Entry near top-left of Room 0 — player must navigate down+right to corridor.
    # Exit near top-left interior of Room 2 — arrives via corridor then goes up.
    # The placer reads these to keep runes off the endpoints.
    ex_c = offsets[-1] + 1   # = 61
    scratch = Room(room_type=RoomType.ENTRY, rows=total_rows, cols=total_cols)
    scratch.cells     = cells
    scratch.spawn_pos = (2, 2)
    scratch.exit_pos  = (2, ex_c)

    # Void wall in puzzle room: rows 2-(total_rows-3) at horizontal midpoint.
    # Gaps at row 1 and row (total_rows-2) are the only safe crossings.
    puzzle_mid_col = offsets[1] + plan[1][2] // 2   # = 40
    void_wall = [
        CharRun(row=row, col=puzzle_mid_col, symbols=('○',), kind='void')
        for row in range(2, total_rows - 2)          # rows 2-9
    ]

    # Decorative characters in entry and exit rooms; retry if any void blocks path.
    dungeon = None
    for _ in range(20):
        scratch.char_runs = list(void_wall)
        rune_rng = random.Random(rng.randint(0, 2**31))
        _place_runes_in_room(scratch, rune_rng, offsets[0],
                              plan[0][1], plan[0][2], total_rows, _WORD_RUNE_KINDS)
        _place_runes_in_room(scratch, rune_rng, offsets[2],
                              plan[2][1], plan[2][2], total_rows, _WORD_RUNE_KINDS)

        # Never place a void rune on the entry or exit cell itself
        entry_r, entry_c = scratch.spawn_pos
        exit_r,  exit_c  = scratch.exit_pos
        scratch.char_runs = [
            ru for ru in scratch.char_runs
            if ru.kind != 'void' or not any(
                ru.row == r and ru.col <= c < ru.col + len(ru.symbols)
                for r, c in ((entry_r, entry_c), (exit_r, exit_c))
            )
        ]

        level = _Level(
            name='The Counting Crypts', seed=seed,
            rows=total_rows, cols=total_cols,
            cells=[''.join(_CELL_CODE[c] for c in row) for row in cells],
            spawn=(2, 2), exit=(2, ex_c),
            char_runs=[{'row': ru.row, 'col': ru.col,
                        'symbols': ''.join(ru.symbols), 'kind': ru.kind}
                       for ru in scratch.char_runs],
            entities=[{'kind': 'exit', 'at': [2, ex_c]}])

        dungeon = _fmt_build(level)
        nav_par = _dijkstra_par_count(dungeon.rooms[0])
        if nav_par is not None:
            break
    else:
        nav_par = 30  # fallback; should never trigger at these densities

    # Doors at corridor-room boundaries (added before par so state-space Dijkstra
    # models them correctly: blocking, trigger positions, and x costs).
    mid = total_rows // 2
    door_cols = [
        offsets[0] + plan[0][2] - 1,   # col 19: Room 0 / corridor 1 boundary
        offsets[1] + plan[1][2] - 1,   # col 55: Room 1 / corridor 2 boundary
    ]
    room = dungeon.rooms[0]
    for dc in door_cols:
        for row in (mid - 1, mid):
            room.entities.append(Entity(kind='door', row=row, col=dc))

    # Full par: state-space Dijkstra with all Counting Crypts commands and door states.
    # Accounts for door-blocking (breaking $ into segments) and x keystrokes.
    room.rebuild_indexes()
    room.par, room.answer = _par_counting_crypts(room, door_cols, return_path=True)
    room.budget = math.ceil(room.par * 1.4)

    _doors_block_sight(room)          # the crypt is dark BEHIND ITS DOORS
    return dungeon


# ── The Rune Halls helpers ───────────────────────────────────────────────────────────

def _make_rune_corridor(composite, rng, row_top,
                        col_start=None, col_end=None,
                        blocked: frozenset = frozenset()):
    """Carve a 2-row CORRIDOR strip and greedily fill it with non-void character runs.

    Leaves a 1-cell buffer at each end so characters reach the turn-room entrance.
    blocked: set of (row, col) cells that random characters must not overlap or
    touch (1-cell side buffer enforced by the caller via the set contents).
    """
    if col_start is None:
        col_start = _RUNE_HALLS_CORR_LEFT
    if col_end is None:
        col_end = _RUNE_HALLS_CORR_RIGHT

    for c in range(col_start, col_end + 1):
        composite.cells[row_top][c]     = CellType.CORRIDOR
        composite.cells[row_top + 1][c] = CellType.CORRIDOR

    for row in (row_top, row_top + 1):
        _scatter_row(composite, rng, row, col_start + 1, col_end - 1,
                     _WORD_RUNE_KINDS, blocked=blocked)


def _dijkstra_par_wbe(composite, return_path: bool = False):
    """Minimum-keystroke Dijkstra for The Rune Halls: hjkl + w b e + count-hjkl.

    w/b/e are row-scoped and each cost 1 keystroke.  Count-n h/j/k/l cost
    len(str(n))+1, matching the existing budget model.  Void cells are never
    chosen as landing targets; count motions may pass through them
    (matching engine's final-cell-only void check).
    """
    from collections import defaultdict

    entry = composite.spawn_pos
    goal  = composite.exit_pos
    max_n = max(composite.rows, composite.cols)

    clusters_by_row: dict[int, list] = defaultdict(list)
    for ru in composite.char_runs:
        if ru.kind != 'void':
            clusters_by_row[ru.row].append(ru)
    for cls in clusters_by_row.values():
        cls.sort(key=lambda ru: ru.col)

    def _word_at(r, c):
        ru = composite.char_run_at(r, c)
        return ru if (ru and ru.kind != 'void') else None

    def _w(r, c):
        cur = _word_at(r, c)
        scan = (cur.col + len(cur.symbols)) if cur else c + 1
        for ru in clusters_by_row.get(r, []):
            if ru.col >= scan and composite.is_passable(r, ru.col):
                return (r, ru.col)
        return None

    def _b(r, c):
        cur = _word_at(r, c)
        if cur and cur.col < c:
            return (r, cur.col)
        limit = cur.col if cur else c
        for ru in reversed(clusters_by_row.get(r, [])):
            if ru.col < limit and composite.is_passable(r, ru.col):
                return (r, ru.col)
        return None

    def _e(r, c):
        cur = _word_at(r, c)
        if cur:
            end = cur.col + len(cur.symbols) - 1
            if end > c and composite.is_passable(r, end):
                return (r, end)
            scan = end + 1
        else:
            scan = c + 1
        for ru in clusters_by_row.get(r, []):
            if ru.col >= scan:
                end = ru.col + len(ru.symbols) - 1
                if composite.is_passable(r, end):
                    return (r, end)
        return None

    def landable(nr, nc):                            # a legal stop: passable, non-void
        ru = composite.char_run_at(nr, nc)
        return composite.is_passable(nr, nc) and not (ru and ru.kind == 'void')

    def neighbors(node):
        r, c = node
        # count h/j/k/l — void blocks landing but count passes through (engine behaviour)
        yield from _count_moves(composite.is_passable, r, c, max_n, landable=landable)
        # count w/b/e — chained Nw / Nb / Ne
        yield from _word_motion_chain(_w, 'w', (r, c), max_n, landable)
        yield from _word_motion_chain(_b, 'b', (r, c), max_n, landable)
        yield from _word_motion_chain(_e, 'e', (r, c), max_n, landable)

    cost, prev, end = _dijkstra(entry, lambda node: node == goal, neighbors)
    if return_path:
        return (cost, _join_path(prev, end, merge_single=False)) if cost is not None else (None, '')
    return cost


def _cataracts_place_zone(composite, rng, rows, col_start, col_end,
                          blocked=frozenset()):
    """Greedily fill character zones (each of ``rows`` between ``col_start`` and
    ``col_end``) for the Cataracts — non-void word runes (ancient/verdant/ember)."""
    for r in rows:
        _scatter_row(composite, rng, r, col_start, col_end, _WORD_RUNE_KINDS,
                     blocked=blocked)


def _dijkstra_par_ftFT(composite, return_path: bool = False):
    """Minimum-keystroke Dijkstra for The Character Cataracts: hjkl + count + w b e + f F t T.

    f/F/t/T scan includes text characters ('r','w','!') and entity chars
    ('E','?') as targets.  w/b/e stop at water (non-passable cells), matching
    apply_motion behaviour.  Scan stops at WALL/WOOD_WALL; water is transparent.
    """
    from collections import defaultdict

    ROWS, COLS = composite.rows, composite.cols

    _dynamite_cells: set = {
        (e.row, e.col) for e in composite.entities if e.kind == 'dynamite'
    }

    def _is_passable(r, c):
        if r < 0 or r >= ROWS or c < 0 or c >= COLS:
            return False
        return composite.cells[r][c] in (CellType.FLOOR, CellType.CORRIDOR)

    def _scan_stops(r, c):
        return composite.cells[r][c] in (CellType.WALL, CellType.WOOD_WALL)

    # Include text chars that appear as characters alongside entity chars.
    _SCAN_CHARS = set('!rw')
    row_chars: dict[int, list] = defaultdict(list)
    for r in range(ROWS):
        for c in range(COLS):
            if _scan_stops(r, c):
                continue
            ch = _cell_char(composite, r, c)
            if ch in _SCAN_CHARS:
                row_chars[r].append((c, ch))

    entry = composite.spawn_pos
    goal  = composite.exit_pos
    max_n = max(ROWS, COLS)

    clusters_by_row: dict[int, list] = defaultdict(list)
    for ru in composite.char_runs:
        if ru.kind != 'void':
            clusters_by_row[ru.row].append(ru)
    for cls in clusters_by_row.values():
        cls.sort(key=lambda ru: ru.col)

    def _word_at(r, c):
        ru = composite.char_run_at(r, c)
        return ru if (ru and ru.kind != 'void') else None

    def _w(r, c):
        cur  = _word_at(r, c)
        scan = (cur.col + len(cur.symbols)) if cur else c + 1
        for nc in range(scan, COLS):
            if not _is_passable(r, nc):
                return None  # water or wall stops w
            ru = composite.char_run_at(r, nc)
            if ru and ru.kind != 'void':
                return (r, ru.col) if _is_passable(r, ru.col) else None
        return None

    def _b(r, c):
        cur = _word_at(r, c)
        if cur and cur.col < c:
            return (r, cur.col) if _is_passable(r, cur.col) else None
        limit = cur.col if cur else c
        for nc in range(limit - 1, -1, -1):
            if not _is_passable(r, nc):
                return None  # water or wall stops b
            ru = composite.char_run_at(r, nc)
            if ru and ru.kind != 'void':
                return (r, ru.col) if _is_passable(r, ru.col) else None
        return None

    def _e(r, c):
        cur = _word_at(r, c)
        if cur:
            end = cur.col + len(cur.symbols) - 1
            if end > c and _is_passable(r, end):
                return (r, end)
            scan = end + 1
        else:
            scan = c + 1
        for nc in range(scan, COLS):
            if not _is_passable(r, nc):
                return None  # water or wall stops e
            ru = composite.char_run_at(r, nc)
            if ru and ru.kind != 'void':
                end = ru.col + len(ru.symbols) - 1
                return (r, end) if _is_passable(r, end) else None
        return None

    def landable(nr, nc):            # a legal stop: floor/corridor, non-void, non-dynamite
        ru = composite.char_run_at(nr, nc)
        return (_is_passable(nr, nc) and (nr, nc) not in _dynamite_cells
                and not (ru and ru.kind == 'void'))

    def neighbors(node):
        r, c = node
        # count h/j/k/l (void + dynamite block landing; count passes through)
        yield from _count_moves(_is_passable, r, c, max_n, landable=landable)
        # w / b / e (these _w/_b/_e stop at water)
        yield from _word_motion_chain(_w, 'w', (r, c), max_n, landable)
        yield from _word_motion_chain(_b, 'b', (r, c), max_n, landable)
        yield from _word_motion_chain(_e, 'e', (r, c), max_n, landable)
        # f / F / t / T — row-scoped, water-transparent, wall-stopped; each costs 2 keys
        pts      = row_chars[r]
        wall_fwd = next((nc for nc in range(c + 1, COLS) if _scan_stops(r, nc)), COLS)
        wall_bwd = next((nc for nc in range(c - 1, -1, -1) if _scan_stops(r, nc)), -1)
        for nc, ch in pts:
            if nc > c and nc < wall_fwd:
                if landable(r, nc):
                    yield (r, nc), f'f{ch}', 2
                if nc - 1 != c and landable(r, nc - 1):
                    yield (r, nc - 1), f't{ch}', 2
            elif nc < c and nc > wall_bwd:
                if landable(r, nc):
                    yield (r, nc), f'F{ch}', 2
                if nc + 1 != c and landable(r, nc + 1):
                    yield (r, nc + 1), f'T{ch}', 2

    cost, prev, end = _dijkstra(entry, lambda node: node == goal, neighbors)
    if return_path:
        return (cost, _join_path(prev, end, merge_single=False)) if cost is not None else (None, '')
    return cost


def build_dungeon_rune_halls(seed: int) -> Dungeon:
    """The Rune Halls — teaches w b e (word motions over character runs).

    Five 2-row character corridors in a snake pattern:
      C1 rows 1-2   left→right  (w efficient)
      C2 rows 4-5   right→left  (b efficient)
      C3 rows 7-8   left→right
      C4 rows 10-11 right→left
      C5 rows 13-14 left→right  (exit = last symbol of anchor character → use e)

    Turn rooms bridge adjacent corridors at alternating ends:
      RT1 rows 2-4   cols 45-46  (void at middle row 3)
      LT1 rows 5-7   cols 1-2   (void at middle row 6)
      RT2 rows 8-10  cols 45-46  (void at middle row 9)
      LT2 rows 11-13 cols 1-2   (void at middle row 12)

    Character runs fill each corridor from col 2 to col 45 (1-cell margin).
    Void clusters at each turn-room middle row block straight j/k traversal,
    forcing count-j to skip them — reinforcing the level-2 count motion.
    """
    from vimny.engine.editor import _CELL_CODE
    from vimny.sharing.format import Level as _Level, build as _fmt_build
    rng     = random.Random(seed)

    # A scratch room for the corridor carver to mutate; the Level is projected
    # from it each attempt.
    scratch = Room(room_type=RoomType.ENTRY,
                   rows=_RUNE_HALLS_TOTAL_ROWS, cols=_RUNE_HALLS_TOTAL_COLS)
    grid = [[CellType.WALL] * _RUNE_HALLS_TOTAL_COLS for _ in range(_RUNE_HALLS_TOTAL_ROWS)]
    scratch.cells = grid

    # ── Carve turn rooms ──────────────────────────────────────────────────────
    turn_spans = [
        (2,  4,  43, 44),   # RT1
        (5,  7,  1,  3),    # LT1
        (8,  10, 43, 46),   # RT2
        (11, 13, 1,  3),    # LT2
    ]
    for r0, r1, ca, cb in turn_spans:
        c0, c1 = sorted((ca, cb))  # handles ca > cb safely
        for row in range(r0, r1 + 1):
            for col in range(c0, c1 + 1):
                grid[row][col] = CellType.CORRIDOR

    # ── Hard-coded characters (deterministic; placed before random fill) ──────
    # All positions are fixed regardless of seed.  Placing them first in the
    # runes list guarantees char_run_at() returns them before any random cluster.
    _rune_halls_hardcoded = [
        # Anchor character at C5 exit — last symbol (col 44) is the exit cell
        CharRun(row=13, col=42, symbols=('∘', '∘', '∘'), kind='ancient'),
        # Ember at right end of C1 — marks the turn into RT1
        CharRun(row=1,  col=44, symbols=('⊙', '⊙', '⊙'), kind='ember'),
        # Void guards at turn-room entries/exits
        CharRun(row=1,  col=45, symbols=('○', '○'), kind='void'),
        CharRun(row=2,  col=45, symbols=('○', '○'), kind='void'),
        CharRun(row=4,  col=1,  symbols=('○', '○'), kind='void'),
        CharRun(row=5,  col=1,  symbols=('○',),     kind='void'),
        CharRun(row=7,  col=46, symbols=('○',),     kind='void'),
        CharRun(row=8,  col=45, symbols=('○', '○'), kind='void'),
        CharRun(row=10, col=1,  symbols=('○',),     kind='void'),
        CharRun(row=10, col=2,  symbols=('·','·','·','·'),     kind='verdant'),
        CharRun(row=11, col=1,  symbols=('○', '○'), kind='void'),
        CharRun(row=13, col=46, symbols=('○',),     kind='void'),
        CharRun(row=14, col=46, symbols=('○',),     kind='void'),
    ]

    # Reserved cells: Random characters must not land in or touch these cells.
    blocked: frozenset = frozenset(
        (ru.row, c)
        for ru in _rune_halls_hardcoded
        for c in range(ru.col, ru.col + len(ru.symbols))
    )

    def _project(runs) -> '_Level':
        return _Level(
            name='The Rune Halls', seed=seed,
            rows=_RUNE_HALLS_TOTAL_ROWS, cols=_RUNE_HALLS_TOTAL_COLS,
            cells=[''.join(_CELL_CODE[c] for c in row) for row in grid],
            spawn=(1, 1), exit=(13, 44),
            char_runs=[{'row': ru.row, 'col': ru.col,
                        'symbols': ''.join(ru.symbols), 'kind': ru.kind}
                       for ru in runs],
            entities=[{'kind': 'exit', 'at': [13, 44]}])

    # ── Carve and populate character corridors (up to 20 attempts for valid par) ──
    dungeon = None
    for _attempt in range(20):
        # Hard-coded runes first so char_run_at() always finds them before random ones
        scratch.char_runs = list(_rune_halls_hardcoded)
        rune_rng = random.Random(rng.randint(0, 2**31))

        for row_top in _RUNE_HALLS_CORR_TOP_ROWS:
            _make_rune_corridor(scratch, rune_rng, row_top, blocked=blocked)

        dungeon = _fmt_build(_project(scratch.char_runs))
        par, path = _dijkstra_par_wbe(dungeon.rooms[0], return_path=True)
        if par is not None:
            break
    else:
        par, path = 80, ''

    room = dungeon.rooms[0]
    room.par    = par
    room.budget = math.ceil(par * 1.4)
    room.answer = path
    return dungeon


def build_dungeon_character_cataracts(seed: int) -> Dungeon:
    """The Character Cataracts — teaches f F t T (character search over water pools).

    Five 2-row snake corridors (72 cols wide).  Each corridor has a water pool
    that blocks hjkl/w/b/e but is transparent to f/F/t/T.  Visible text
    strings on the floor tiles are the jump targets:

      C1 rows 1-2   left→right  fr  "    Most dungeons you traverse" → r at col 61
      C2 rows 4-5   right→left  Fw  " will be scribed in letters"    → w at col 4
      C3 rows 7-8   left→right  t!  "so you can jump" + "quite easily…type" + dynamite at col 70
      C4 rows 10-11 right→left  T!  dynamite at col 1 (F! would explode)
      C5 rows 13-14 left→right  w/b/e character navigation + exit
    """
    from vimny.engine.editor import _CELL_CODE
    from vimny.sharing.format import Level as _Level, build as _fmt_build
    ROWS, COLS = _CHARACTER_CATARACTS_TOTAL_ROWS, _CHARACTER_CATARACTS_TOTAL_COLS
    rng     = random.Random(seed)

    grid = [[CellType.WALL] * COLS for _ in range(ROWS)]

    # ── Carve corridors (2 rows each) ─────────────────────────────────────────
    for row_top in _CHARACTER_CATARACTS_CORR_TOP_ROWS:
        for c in range(_CHARACTER_CATARACTS_CORR_LEFT, _CHARACTER_CATARACTS_CORR_RIGHT + 1):
            grid[row_top][c]     = CellType.CORRIDOR
            grid[row_top + 1][c] = CellType.CORRIDOR

    # ── Carve turn rooms ──────────────────────────────────────────────────────
    for r0, r1, ca, cb in _CHARACTER_CATARACTS_TURN_SPANS:
        c0, c1 = min(ca, cb), max(ca, cb)
        for row in range(r0, r1 + 1):
            for col in range(c0, c1 + 1):
                grid[row][col] = CellType.CORRIDOR

    # Floor cells widening the turn-room middle rows (matches saved reference layout)
    for r, c in ((3, 67), (3, 68),           # RT1 middle
                 (6, 1),  (6, 3), (6, 4),    # LT1 middle
                 (7, 17), (8, 17),            # C3 Zone A/water boundary
                 (9, 67), (9, 68)):           # RT2 middle
        grid[r][c] = CellType.FLOOR

    # ── Water pools ───────────────────────────────────────────────────────────
    for rows, cs, ce in _CHARACTER_CATARACTS_WATER_SPANS:
        for r in rows:
            for c in range(cs, ce + 1):
                grid[r][c] = CellType.WATER

    # ── Fixed text character runs (visible f/F/t/T targets) ───────────────────
    # Text chars are individual characters; _cell_char returns each char so
    # f/F/t/T can find them.  kind='ember' gives a distinctive warm colour.
    # One row of text per corridor (the other row gets standard random characters).
    _text_runes = [
        # C1 row 1: fr jumps to 'r' at offset 23 → col 67
        CharRun(row=1, col=44, symbols=tuple(_CHARACTER_CATARACTS_TEXT_C1), kind='ember'),
        # C2 row 5: Fw jumps backward to 'w' at offset 1 → col 4
        CharRun(row=5, col=3,  symbols=tuple(_CHARACTER_CATARACTS_TEXT_C2), kind='ember'),
        # C3 row 7 Zone A: walking terrain before the water (cols 2-16)
        CharRun(row=7, col=2,  symbols=tuple(_CHARACTER_CATARACTS_TEXT_C3A), kind='ember'),
        # C3 row 7 Zone B: t! lands at col 69 (before dynamite at col 70)
        CharRun(row=7, col=33, symbols=tuple(_CHARACTER_CATARACTS_TEXT_C3B), kind='ember'),
        # C5 exit anchor: last symbol at col 65 so `e` lands on the exit
        CharRun(row=13, col=64, symbols=('⊙', '⊙'), kind='ember'),
    ]

    # ── Fixed entities ────────────────────────────────────────────────────────
    _fixed = [
        # C3: dynamite at col 70 — t! (before, col 69) is safe; f! (on) explodes
        Entity(kind='dynamite', row=7,  col=70),
        # C4: dynamite at col 1 — T! (after, col 2) is safe; F! (on) explodes
        Entity(kind='dynamite', row=10, col=1),
        Entity(kind='dynamite', row=11, col=1),
        Entity(kind='exit',  row=13, col=65),
    ]

    def _project(runs) -> '_Level':
        return _Level(
            name='The Character Cataracts', seed=seed,
            rows=ROWS, cols=COLS,
            cells=[''.join(_CELL_CODE[c] for c in row) for row in grid],
            spawn=(1, 1), exit=(13, 65),
            char_runs=[{'row': ru.row, 'col': ru.col,
                        'symbols': ''.join(ru.symbols), 'kind': ru.kind}
                       for ru in runs],
            entities=[{'kind': e.kind, 'at': [e.row, e.col]} for e in _fixed])

    # ── Blocked cells: water + text/anchor characters + fixed entities ────────
    _bl: set = {(e.row, e.col) for e in _fixed}
    for rows, cs, ce in _CHARACTER_CATARACTS_WATER_SPANS:
        for r in rows:
            for c in range(cs, ce + 1):
                _bl.add((r, c))
    for ru in _text_runes:
        for i in range(len(ru.symbols)):
            _bl.add((ru.row, ru.col + i))
    blocked = frozenset(_bl)

    # A scratch room for the zone placer to mutate.
    scratch = Room(room_type=RoomType.ENTRY, rows=ROWS, cols=COLS)
    scratch.cells = grid

    dungeon = None
    for _attempt in range(20):
        scratch.char_runs = list(_text_runes)
        rng2 = random.Random(rng.randint(0, 2**31))

        # Fill all corridor zones with standard characters
        _cataracts_place_zone(scratch, rng2, (1, 2),    2,  13, blocked=blocked)  # C1 Zone A
        _cataracts_place_zone(scratch, rng2, (1, 2),   38,  68, blocked=blocked)  # C1 Zone B
        _cataracts_place_zone(scratch, rng2, (4,),      2,  28, blocked=blocked)  # C2 row 4 Zone A
        _cataracts_place_zone(scratch, rng2, (4, 5),   52,  68, blocked=blocked)  # C2 Zone B
        _cataracts_place_zone(scratch, rng2, (8,),      2,  16, blocked=blocked)  # C3 row 8 Zone A
        _cataracts_place_zone(scratch, rng2, (8,),     32,  70, blocked=blocked)  # C3 row 8 Zone B
        _cataracts_place_zone(scratch, rng2, (10, 11),  2,  24, blocked=blocked)  # C4 Zone A
        _cataracts_place_zone(scratch, rng2, (10, 11), 52,  68, blocked=blocked)  # C4 Zone B
        # C5: dense character corridor for w/b/e practice; chest at col 20, exit anchor at col 64-65
        _cataracts_place_zone(scratch, rng2, (13, 14),  2,  63, blocked=blocked)

        dungeon = _fmt_build(_project(scratch.char_runs))
        par, path = _dijkstra_par_ftFT(dungeon.rooms[0], return_path=True)
        if par is not None:
            break
    else:
        par, path = 80, ''

    room = dungeon.rooms[0]
    room.par    = par
    room.budget = math.ceil(par * 1.4)
    room.answer = path
    return dungeon


# ── The Reliquary layout constants (the Sealed Ward) ──────────────────────────
_RELIQUARY_ROWS        = 7
_RELIQUARY_COLS        = 19
_RELIQUARY_ACTION_ROW  = 3
_RELIQUARY_WALL_COL    = 12          # full-height dividing wall; doorway at action row
_RELIQUARY_FRIEZE_ROWS = (1, 5)
_RELIQUARY_SPAWN       = (3, 1)
_RELIQUARY_CHEST       = (3, 15)
_RELIQUARY_EXIT        = (3, 16)     # immediately right of the chest
# Themed ward-words (classical Latin, V for U), right-aligned against the wall.
_RELIQUARY_SEAL_WORDS  = ('SIGILLVM', 'VINCVLVM', 'CLAVSTRA', 'ARCANVM',
                          'CVSTOS', 'SERVATA', 'SIGNVM', 'OBEX')


def _place_frieze(composite, rng, row: int, c0: int, c1: int) -> None:
    """Scatter ornamental ancient/verdant runes across [c0, c1] on `row`."""
    c = c0
    while c <= c1:
        if rng.random() < 0.55:
            kind = rng.choice(('ancient', 'verdant'))
            n    = min(rng.randint(1, 3), c1 - c + 1)
            composite.char_runs.append(
                CharRun(row=row, col=c,
                        symbols=tuple(_RUNE_CHAR[kind] for _ in range(n)), kind=kind))
            c += n + rng.randint(1, 2)
        else:
            c += rng.randint(1, 2)


def _place_frieze_sym(composite, rng, rows, c0: int, c1: int) -> None:
    """Ornamental friezes with the masons' discipline:
    ONE seeded pattern, mirrored left↔right, stamped identically on every
    row in `rows` — so the top and bottom courses match and each reads as a
    palindrome about the chamber's centre."""
    width = c1 - c0 + 1
    half  = (width + 1) // 2
    kinds: dict = {}                       # offset → rune kind (left half)
    off = 0
    while off < half:
        if rng.random() < 0.55:
            kind = rng.choice(('ancient', 'verdant'))
            n    = min(rng.randint(1, 3), half - off)
            for i in range(off, off + n):
                kinds[i] = kind
            off += n + rng.randint(1, 2)
        else:
            off += rng.randint(1, 2)
    for i, k in list(kinds.items()):       # the mirror
        kinds[width - 1 - i] = k
    for row in rows:
        c = 0
        while c < width:                   # group cells into contiguous runs
            if c in kinds:
                kind, n = kinds[c], 1
                while c + n < width and kinds.get(c + n) == kind:
                    n += 1
                composite.char_runs.append(
                    CharRun(row=row, col=c0 + c,
                            symbols=tuple(_RUNE_CHAR[kind] for _ in range(n)),
                            kind=kind))
                c += n
            else:
                c += 1


def _reliquary_answer(word: str) -> str:
    """Representative solve path (informational — reliquary has no par)."""
    seal_col = _RELIQUARY_WALL_COL - len(word)
    approach = ['l'] * (seal_col - _RELIQUARY_SPAWN[1])    # reach the leftmost glyph
    erase    = ['x'] * len(word)                           # break the seal in place
    cross    = ['l'] * (_RELIQUARY_CHEST[1] - seal_col)    # pass through to the chest
    return ' '.join(approach + erase + cross + ['x', 'l'])  # loot, then step to exit


def build_dungeon_reliquary(seed: int) -> Dungeon:
    """The Reliquary — the Sealed Ward (bonus room after The Line Halls).

    A two-chamber vault split by a full-height wall. On the approach side a
    ward-word is inscribed across the threshold; erase it glyph-by-glyph with
    x and the warded doorway opens onto the sanctum, where the relic-scroll
    (The Unnamed Register) and the exit wait — entry, seal, chest, and exit
    all on one row.

    No par challenge (par=None, reward room).  x is *forced*: the dividing
    wall blocks the sanctum until the seal CharRun on the action row is fully
    cut, which vimny/game.py's _check_seal_broken detects, opening composite.seal_door.
    """
    from vimny.engine.editor import _CELL_CODE
    from vimny.sharing.format import Level as _Level, build as _fmt_build
    rng = random.Random(seed)
    ROWS, COLS = _RELIQUARY_ROWS, _RELIQUARY_COLS
    W, ar = _RELIQUARY_WALL_COL, _RELIQUARY_ACTION_ROW

    grid = [[CellType.WALL] * COLS for _ in range(ROWS)]
    # Two floor chambers (rows 1..ROWS-2) split by the dividing wall at col W.
    for r in range(1, ROWS - 1):
        for c in range(1, W):
            grid[r][c] = CellType.FLOOR          # left approach chamber
        for c in range(W + 1, COLS - 1):
            grid[r][c] = CellType.FLOOR          # right sanctum
    # col W stays WALL top-to-bottom; the doorway at (ar, W) opens on seal-break.

    # The seal: a Latin ward-word in ember, right-aligned against the dividing
    # wall on the action row — the ONLY CharRun on that row (so its absence
    # signals a broken seal).
    word     = rng.choice(_RELIQUARY_SEAL_WORDS)
    seal_col = W - len(word)
    runs     = [{'row': ar, 'col': seal_col, 'symbols': word, 'kind': 'ember'}]
    # Ornamental friezes (randomized per seed) line both chambers — never the
    # action row, so they can't be mistaken for the seal.
    scratch = Room(room_type=RoomType.ENTRY, rows=ROWS, cols=COLS)
    scratch.cells     = grid
    scratch.char_runs = []
    _place_frieze_sym(scratch, rng, _RELIQUARY_FRIEZE_ROWS, 1, W - 1)  # approach
    for fr in _RELIQUARY_FRIEZE_ROWS:
        _place_frieze(scratch, rng, fr, W + 1, COLS - 2)     # right sanctum
    runs += [{'row': ru.row, 'col': ru.col, 'symbols': ''.join(ru.symbols),
              'kind': ru.kind} for ru in scratch.char_runs]

    level = _Level(
        name='The Reliquary', seed=seed,
        rows=ROWS, cols=COLS,
        cells=[''.join(_CELL_CODE[c] for c in row) for row in grid],
        spawn=_RELIQUARY_SPAWN, exit=_RELIQUARY_EXIT,
        char_runs=runs,
        entities=[{'kind': 'chest_scroll',
                   'at': [_RELIQUARY_CHEST[0], _RELIQUARY_CHEST[1]]},
                  {'kind': 'exit',
                   'at': [_RELIQUARY_EXIT[0], _RELIQUARY_EXIT[1]]}],
        solution=_reliquary_answer(word))

    dungeon = _fmt_build(level)
    room = dungeon.rooms[0]
    # Reward room: no par challenge — a fixed tight budget instead. The warded
    # doorway and its fog are engine mechanics, re-attached post-build.
    room.par        = None
    room.budget     = 35
    room.seal_door  = (ar, W)
    # The sanctum sleeps under fog until the seal breaks (a bare divider hides
    # nothing — the relic and exit must not be visible from spawn).
    # Standard reachability fog; _check_seal_broken lifts it with the ward.
    _fog_unreachable(room, *room.spawn_pos)
    return dungeon


# ── The Dummy Dungeon (admin sandbox) ─────────────────────────────────────────
# A showroom, not a level. Every entity kind, every glyph-CHANGING tag, every
# CellType and every rune kind gets one labelled specimen, so an admin can see
# what the game contains and practice the editor on it without hunting through
# 33 levels. Tags that only change BEHAVIOUR (the warden ranks — surveyor,
# scrivener, manifold, eternal…) are deliberately absent: they all paint the
# same 'W', so eight of them would be eight identical exhibits.
# `tests/test_dummy_dungeon.py` is the invariant — add a kind to the game, add
# a specimen here.

_DUMMY_ROWS, _DUMMY_COLS = 34, 132
_DUMMY_C0, _DUMMY_C1 = 4, 73   # the labelled-alcove span. Cols 1-3 are the SPINE:
                               # every band's label row is stone, so without a
                               # floor column running past their west end the
                               # showroom would fall into disconnected strips.
_DUMMY_DIV_W = 75    # showroom | reflow wing
_DUMMY_DIV_E = 97    # reflow wing | scratchpad
_DUMMY_YARD  = 31    # the open row both dividers open onto


def build_dungeon_dummy(seed: int) -> Dungeon:
    """Admin sandbox — a labelled showroom west, a free editing yard east.

    Layout (34 x 132; the viewport scrolls on both axes):
      Showroom    cols 1-73   — eight bands of labelled specimens off a west spine
      Divider     col 75      — open doorway at the yard row
      Reflow wing cols 76-96  — the three destructive reflow demos, quarantined
                                behind stone so a wave can't sweep an exhibit
      Divider     col 97      — locked door (an exhibit that is also the gate)
      Scratchpad  cols 98-130 — blank floor to build on, and the exit

    Bands run spec-row / label-row: friendlies 2-4/5, hostiles 7-9/10,
    loot 12/13, keys 15/16, doors 18/19, fixtures 21/22, terrain 24-26/27,
    runes 29/30. Every specimen that can move is jailed.
    """
    from vimny.engine.editor import _CELL_CODE
    from vimny.sharing.format import Level as _Level, build as _fmt_build
    ROWS, COLS = _DUMMY_ROWS, _DUMMY_COLS
    grid   = [[CellType.WALL] * COLS for _ in range(ROWS)]

    for r in range(1, ROWS - 1):                     # one open slab; the bands
        for c in range(1, COLS - 1):                 # carve their stone back in
            grid[r][c] = CellType.FLOOR
    for r in range(1, ROWS - 1):
        grid[r][_DUMMY_DIV_W] = CellType.WALL
        grid[r][_DUMMY_DIV_E] = CellType.WALL
    grid[_DUMMY_YARD][_DUMMY_DIV_W] = CellType.FLOOR
    grid[_DUMMY_YARD][_DUMMY_DIV_E] = CellType.FLOOR

    ents:   list = []
    chars:  list = []
    sealed: set  = set()
    underwater: set = set()
    spawn:  list = []

    def _band(label_row: int, items) -> None:
        """Lay one band of exhibits west to east, naming each in the stone below.

        Labels live in WALL cells on purpose: stone is uncuttable and is skipped
        by the floor text scans, so a stray `dd` in the aisle can never wipe the
        sign off an exhibit. Each item is (label, place); `place` gets the column
        it was allotted and does whatever that specimen needs.
        """
        for c in range(_DUMMY_C0, _DUMMY_C1 + 1):
            grid[label_row][c] = CellType.WALL
        c = _DUMMY_C0
        for label, place in items:
            width = max(len(label), 3) + 2
            if c + width - 1 > _DUMMY_C1:
                raise ValueError(f'dummy band {label_row} overflows its wall at {label!r}')
            place(c)
            chars.append(CharRun(row=label_row, col=c,
                                 symbols=tuple(label), kind='ancient'))
            c += width

    def _at(row: int, **kw):
        kind = kw.pop('kind')
        return lambda c: ents.append({'kind': kind, 'at': [row, c], **kw})

    def _jail(row: int, **kw):
        """A specimen cell: stone on three sides, a door on the fourth.

        EVERY specimen is jailed, friendly ones included — an un-caged ally
        beelines for the player the moment the sandbox opens, and an exhibit
        that walks away is not an exhibit.

        The door earns its place twice over. Fog here is cast by
        `apply_stone_fog`, which only STONE blocks — so the occupant is visible
        from the aisle rather than hidden in the dark. And `_steppable` refuses
        any cell that holds an entity, so the occupant can never cross its own
        door: the cage holds for exactly the reason the fog clears, with no
        engine change and no fog exemption. Delete the door and you release it.

        The stone runs above and below the DOOR as well as the cell, which is
        what makes `_is_vertical_door` draw it as the north-south door it is.
        """
        kind = kw.pop('kind')
        def place(c):
            for cc in (c, c + 1):
                grid[row - 1][cc] = CellType.WALL
                grid[row + 1][cc] = CellType.WALL
            grid[row][c - 1] = CellType.WALL
            ents.append({'kind': kind, 'at': [row, c], **kw})
            ents.append({'kind': 'door', 'at': [row, c + 1]})
        return place

    def _patch(rows: range, ct: CellType):
        def place(c):
            for r in rows:
                for cc in range(c, c + 3):
                    grid[r][cc] = ct
        return place

    def _sunken(rows: range):
        def place(c):
            for r in rows:
                for cc in range(c, c + 3):
                    grid[r][cc] = CellType.WATER
                    underwater.add((r, cc))
        return place

    def _fogbox(rows: range):
        """A sealed 3x3 pocket. Stone hides it, so it starts fogged — cut one
        wall and `auto_fog` reveals it, which is the fog law in one exhibit."""
        def place(c):
            for r in rows:
                for cc in range(c, c + 3):
                    grid[r][cc] = CellType.WALL
            grid[rows.start + 1][c + 1] = CellType.FLOOR
        return place

    def _rune(row: int, sym: str, kind: str):
        return lambda c: chars.append(CharRun(row=row, col=c,
                                              symbols=(sym,), kind=kind))

    def _gate(row: int):
        """A registered gate: banded stone (╬) some level draws back."""
        def place(c):
            grid[row][c] = CellType.WALL
            sealed.add((row, c))
        return place

    def _entry(row: int):
        def place(c):
            ents.append({'kind': 'entry_marker', 'at': [row, c]})
            spawn.append((row, c))
        return place

    # ── Friendlies — the whole `~`-toggle family sits in one eyeline, so g/G,
    # d/D and c/C read as the same joke told three times. Jailed like the rest:
    # an ally left loose runs to the player's side and the band empties itself.
    # A jail row needs a plain aisle ABOVE and BELOW its two stone rows — set a
    # jail against a label row and its aisle has no way back to the west spine.
    _band(5, [
        # A hound is a combatant like any other: it bites, and it can be bitten.
        ('dog',       _jail(3, kind='ally', hp=1, max_hp=1)),
        ('big_dog',   _jail(3, kind='ally', hp=2, max_hp=2, swole=True)),
        ('cat',       _jail(3, kind='critter')),
        ('big_cat',   _jail(3, kind='critter', swole=True)),
        ('elf',       _jail(3, kind='elf')),
        ('horse',     _jail(3, kind='horse')),
        ('archivist', _jail(3, kind='archivist', ai='')),
        ('wanderer',  _jail(3, kind='wanderer')),
    ])

    # ── Hostiles. Live `chase` AI on the goblins: they strain against the door
    # every tick and get nowhere, which is the point of the exhibit.
    _band(10, [
        ('goblin', _jail(8, kind='goblin', hp=1, max_hp=1, ai='chase', ai_speed=1)),
        ('swole',  _jail(8, kind='goblin', hp=1, max_hp=1, ai='chase', ai_speed=1,
                         swole=True)),
        ('zombie', _jail(8, kind='goblin', hp=1, max_hp=1, ai='', tag='zombie')),
        ('demon',  _jail(8, kind='goblin', hp=1, max_hp=1, ai='', tag='demon')),
        # Two echo shades, not eight: enough to show the impostors are a SPREAD
        # of reds rather than one colour. hp=2 so an unmasking strike is survived.
        ('echo',   _jail(8, kind='goblin', hp=2, max_hp=2, ai='', tag='echo', shade=0)),
        ('echo2',  _jail(8, kind='goblin', hp=2, max_hp=2, ai='', tag='echo', shade=3)),
        ('warden', _jail(8, kind='warden', hp=5, max_hp=5, ai='', summon_timer=0)),
    ])

    _band(13, [
        ('chest',     _at(12, kind='chest_random')),
        ('key_chest', _at(12, kind='chest_key')),
        ('scroll',    _at(12, kind='chest_scroll')),
        ('coin',      _at(12, kind='gold')),
        ('heart',     _at(12, kind='heart_container')),
        ('shield',    _at(12, kind='shield')),
        ('hat',       _at(12, kind='hat')),
    ])

    _band(16, [
        ('floor_key', _at(15, kind='floor_key')),
        ('gold_key',  _at(15, kind='floor_key', tag='gold')),
        ('red_key',   _at(15, kind='floor_key', tag='red')),
        ('blue_key',  _at(15, kind='floor_key', tag='blue')),
    ])

    # Loose on the floor with open sky above and below, so these draw as the
    # EAST-WEST doors they are — the jails and the wing dividers show the
    # north-south form.
    _band(19, [
        ('door',      _at(18, kind='door')),
        ('gold_lock', _at(18, kind='locked_door', tag='gold')),
        ('red_lock',  _at(18, kind='locked_door', tag='red')),
        ('blue_lock', _at(18, kind='locked_door', tag='blue')),
        ('seal_door', _at(18, kind='seal_door')),
        ('boss_seal', _at(18, kind='boss_seal')),
    ])

    _band(22, [
        ('brazier',  _at(21, kind='brazier', hp=1, max_hp=1, ai='')),
        ('pedestal', _at(21, kind='pedestal')),
        ('dynamite', _at(21, kind='dynamite')),
        ('gate',     _gate(21)),
        ('entry',    _entry(21)),
    ])

    _band(27, [
        ('floor',    lambda c: None),                       # the slab as built
        ('corridor', _patch(range(24, 27), CellType.CORRIDOR)),
        ('stone',    _patch(range(24, 27), CellType.WALL)),
        ('timber',   _patch(range(24, 27), CellType.WOOD_WALL)),
        ('water',    _patch(range(24, 27), CellType.WATER)),
        ('underwater', _sunken(range(24, 27))),
        ('fogbox',   _fogbox(range(24, 27))),
    ])

    _band(30, [
        ('ancient', _rune(29, '∘', 'ancient')),
        ('verdant', _rune(29, '·', 'verdant')),
        ('void',    _rune(29, '○', 'void')),
        ('ember',   _rune(29, '⊙', 'ember')),
    ])

    # ── Reflow wing (vimny/engine/reflow.py) — quarantined behind stone. On a ledge
    # row, editing flows and content falls against the FIXED brinks: walls and
    # void runes alike. Three demos of the one law, all destructive, which is
    # why they no longer share a room with the exhibits.
    # WATER WAVE: shove 'WAVE' into the puddle; the wave rolls right and sweeps
    # away what it reaches — the goblin drowns, the key is lost.
    grid[20][84] = CellType.WATER
    grid[20][85] = CellType.WATER
    chars.append(CharRun(row=20, col=80, symbols=tuple('WAVE'), kind='verdant'))
    ents.append({'kind': 'goblin',    'at': [20, 86], 'hp': 1, 'max_hp': 1,
                 'ai': ''})
    ents.append({'kind': 'floor_key', 'at': [20, 87]})
    # VOID MARGIN: the ○ brink sits on floor, so the cursor can step onto it and
    # FALL IN; glyphs shoved past the brink tumble into the void.
    chars.append(CharRun(row=22, col=78, symbols=tuple('GLYPHS'), kind='ancient'))
    chars.append(CharRun(row=22, col=85, symbols=('○',) * 7,     kind='void'))
    # WALL EDGE: the floor just ends at the divider. The cursor CLAMPS at the
    # last cell; glyphs tipped against the wall fall off.
    chars.append(CharRun(row=24, col=92, symbols=tuple('EDGE'), kind='ember'))
    # Wing labels, in stone — leaving cols 94-96 open so the wing stays walkable
    # from the yard doorway below.
    for c in range(76, 94):
        grid[26][c] = CellType.WALL
    chars.append(CharRun(row=26, col=76, symbols=tuple('wave'), kind='ancient'))
    chars.append(CharRun(row=26, col=82, symbols=tuple('void'), kind='ancient'))
    chars.append(CharRun(row=26, col=88, symbols=tuple('edge'), kind='ancient'))

    # ── The east divider's lock is itself the plain `locked_door` exhibit, and
    # the scratchpad beyond it is deliberately empty — nothing to disturb.
    ents.append({'kind': 'locked_door', 'at': [_DUMMY_YARD, _DUMMY_DIV_E]})
    ents.append({'kind': 'exit',        'at': [16, COLS - 3]})

    level = _Level(
        name='Dummy Dungeon', seed=seed,
        rows=ROWS, cols=COLS,
        cells=[''.join(_CELL_CODE[c] for c in row) for row in grid],
        spawn=spawn[0], exit=(16, COLS - 3),
        char_runs=[{'row': ru.row, 'col': ru.col,
                    'symbols': ''.join(ru.symbols), 'kind': ru.kind}
                   for ru in chars],
        entities=ents)

    dungeon = _fmt_build(level)
    room = dungeon.rooms[0]
    room.par            = None
    room.budget         = 99999
    room.passable_walls = False
    # Stone fog, not the derived law: a door is a grille you can see through,
    # so every jailed specimen is on display while still being caged. build()'s
    # reachability fog disagrees here by design, so it is discarded first.
    room.fog_cells = set()
    apply_stone_fog(room)
    room.sealed_cells = sealed
    room.underwater_cells   = set(underwater)       # permanent haze: reveals skip it
    room.fog_cells   |= underwater           # water is a SUBSET of fog by contract
    return dungeon


# ── The Goblin Gauntlet helpers ────────────────────────────────────────────────────────────

_GOBLIN_GAUNTLET_ROWS = 20
_GOBLIN_GAUNTLET_COLS = 58

# Snake corridor rows (single-row each)
_GOBLIN_GAUNTLET_CORR_ROWS    = [1, 3, 5, 7, 9, 11, 13, 15]
_GOBLIN_GAUNTLET_RIGHT_GOING  = {1, 5, 9, 13}   # player enters from left
_GOBLIN_GAUNTLET_LEFT_GOING   = {3, 7, 11, 15}  # player enters from right

# Right connector rows (floor at cols 55-56); left connector rows (floor at cols 2-3)
_GOBLIN_GAUNTLET_RIGHT_CONN_ROWS = [2, 6, 10, 14]
_GOBLIN_GAUNTLET_LEFT_CONN_ROWS  = [4, 8, 12, 16]
_GOBLIN_GAUNTLET_RC_COLS = (55, 56)
_GOBLIN_GAUNTLET_LC_COLS = (2, 3)


def _l5_place_near_runes(runes: list, rng, row: int,
                          col_start: int, col_end: int, n: int,
                          word_tbl: dict) -> None:
    """Scatter n decorative (non-void) character runs on the near side."""
    available = col_end - col_start + 1
    if available < 1 or n < 1:
        return
    kinds = ('ancient', 'verdant', 'ember')
    occupied: set = set()
    placed = 0
    for _ in range(n * 20):
        if placed >= n:
            break
        c = rng.randint(col_start, col_end)
        if c in occupied:
            continue
        max_len = min(7, col_end - c + 1)
        length = rng.randint(1, max_len)
        if any((c + i) in occupied for i in range(length)):
            length = 1
            if c in occupied:
                continue
        # A decorative rune carrying 'g' (the goblin glyph) would hijack the
        # fg/;/, find-scan — the cursor lands on the decoy instead of the goblin
        # and a corridor's last goblin survives. Keep all near-side decor g-free.
        choices = [w for w in (word_tbl.get(length) or word_tbl[1]) if 'g' not in w]
        if not choices:
            continue
        word = rng.choice(choices)
        kind = rng.choice(kinds)
        runes.append({'row': row, 'col': c, 'symbols': word, 'kind': kind})
        for i in range(len(word)):
            occupied.add(c + i)
        placed += 1


def _l5_goblin_positions(rng, far_start: int, far_end: int,
                          right_to_left: bool) -> list:
    """Place 2-5 goblins in [far_start, far_end] with >= 3-cell spacing."""
    space = far_end - far_start + 1
    if space < 1:
        return []
    n = min(5, max(2, space // 5))
    positions = []
    step = max(3, space // n)
    if right_to_left:
        c = far_end - rng.randint(0, max(0, step - 3))
        for _ in range(n):
            if c < far_start:
                break
            positions.append(c)
            c -= rng.randint(3, step)
    else:
        c = far_start + rng.randint(0, max(0, step - 3))
        for _ in range(n):
            if c > far_end:
                break
            positions.append(c)
            c += rng.randint(3, step)
    return positions



def _par_goblin_gauntlet(corr_data: list, gobs_17: list) -> int:
    """Analytical par for The Goblin Gauntlet.

    Optimal strategy:
    - First right-going corridor: fg (2 keys) to establish last_f.
    - Subsequent right-going corridors: ; (1 key) reuses last_f.
    - Left-going corridors: , (1 key) reverses last_f.
    - After each kill chain, $ or 0 reaches the connector in 1 key regardless
      of distance (both cross water, bounded only by walls).
    - Connector transition: j (step onto door) + x (open door, reveal fog) + j
      (enter next corridor) = 3 keys.  2j cannot cross a fogged door.
    - Row-17 entry: ; (1 key, last_f already set).  After killing all goblins,
      $ stops at col 52 (locked_door blocks _cross_water at col 53).  One p
      kills both locked_doors via BFS.  Second $ reaches col 56.  j exits.
    """
    total = 0
    first_right = True
    for c in corr_data:
        n = len(c['goblins'])
        if n == 0:
            continue
        if c['right_going']:
            entry = 2 if first_right else 1   # fg once; subsequent corridors use ;
            first_right = False
        else:
            entry = 1                          # , reverses the stored last_f
        kill   = entry + 1 + max(0, n - 1) * 2
        total += kill + 1 + 3                  # $ or 0 (1) + j x j connector (3)

    n17 = len(gobs_17)
    if n17 > 0:
        kill17 = 1 + 1 + max(0, n17 - 1) * 2 + 1   # ; x ;x… + x to pick up key
        total += kill17
    total += 4   # $ p $ j  ($ to col 52, p unlocks both doors, $ to col 56, j to exit)

    return max(total, 10)


def _answer_l5(corr_data: list, gobs_17: list) -> str:
    """Exact command sequence for the current Goblin Gauntlet layout."""
    cmds: list = []
    first_right = True
    for c in corr_data:
        n = len(c['goblins'])
        if n == 0:
            continue
        if c['right_going']:
            cmds += ['fg', 'x'] if first_right else [';', 'x']
            first_right = False
            for _ in range(n - 1):
                cmds += [';', 'x']
            cmds += ['$', 'j', 'x', 'j']
        else:
            cmds += [',', 'x']
            for _ in range(n - 1):
                cmds += [',', 'x']
            cmds += ['0', 'j', 'x', 'j']
    n17 = len(gobs_17)
    if n17 > 0:
        for _ in range(n17):
            cmds += [';', 'x']
        cmds.append('x')   # pick up key dropped by last goblin
    cmds += ['$', 'p', '$', 'j']
    return ' '.join(cmds)


def build_dungeon_goblin_gauntlet(seed: int) -> Dungeon:
    """The Goblin Gauntlet — teaches ; and , (repeat last f/t).

    Eight single-row snake corridors.  Each has a water pool (impassable to
    hjkl, transparent to f/F/t/T) with goblins on the far side.  The player
    uses fg to leap the first pool and establish last_f='g', then chains
    ;x on right-going corridors and ,x on left-going ones.
    Void runes at col 1 / col 57 punish 0 / $ overshoot.
    Rows 17-18: goblin gauntlet + door gate + exit.
    """
    _load_vocab_tables()
    _mixed = _VOCAB_MIXED_BY_LEN
    rng     = random.Random(seed)
    from vimny.engine.editor import _CELL_CODE
    from vimny.sharing.format import Level as _Level, build as _fmt_build

    cells = [[CellType.WALL] * _GOBLIN_GAUNTLET_COLS for _ in range(_GOBLIN_GAUNTLET_ROWS)]

    # Carve corridor floors (single-row each)
    for row in _GOBLIN_GAUNTLET_CORR_ROWS:
        for c in range(1, 57):
            cells[row][c] = CellType.FLOOR

    # Final section: full floor cols 1-56
    for row in (17, 18):
        for c in range(1, 57):
            cells[row][c] = CellType.FLOOR

    # Right connector passages (cols 55-56)
    for row in _GOBLIN_GAUNTLET_RIGHT_CONN_ROWS:
        for c in _GOBLIN_GAUNTLET_RC_COLS:
            cells[row][c] = CellType.FLOOR

    # Left connector passages (cols 2-3)
    for row in _GOBLIN_GAUNTLET_LEFT_CONN_ROWS:
        for c in _GOBLIN_GAUNTLET_LC_COLS:
            cells[row][c] = CellType.FLOOR

    entities: list = []                       # (no entry_marker — spawn_pos suffices)
    runes:    list = []
    corr_data      = []

    # Per-corridor randomisation
    for row in _GOBLIN_GAUNTLET_CORR_ROWS:
        right_going = row in _GOBLIN_GAUNTLET_RIGHT_GOING

        w_width = rng.randint(3, 6)
        if right_going:
            w_start = rng.randint(5, 28)
        else:
            w_start = rng.randint(20, max(20, 44 - w_width))
        w_end = w_start + w_width - 1

        for c in range(w_start, w_end + 1):
            cells[row][c] = CellType.WATER

        if right_going:
            far_start = w_end + 2
            far_end   = _GOBLIN_GAUNTLET_RC_COLS[0] - 2
            gobs = _l5_goblin_positions(rng, far_start, far_end,
                                        right_to_left=False)
        else:
            far_start = _GOBLIN_GAUNTLET_LC_COLS[1] + 2
            far_end   = w_start - 2
            gobs = _l5_goblin_positions(rng, far_start, far_end,
                                        right_to_left=True)

        for gc in gobs:
            entities.append({'kind': 'goblin', 'at': [row, gc],
                             'hp': 1, 'max_hp': 1, 'ai': 'chase', 'ai_speed': 2})

        # Decorative near-side characters (non-void)
        if right_going:
            near_s, near_e = 2, w_start - 2
        else:
            near_s, near_e = w_end + 2, 54
        _l5_place_near_runes(runes, rng, row, near_s, near_e, rng.randint(1, 3), _mixed)

        # Stone walls at corridor ends (block $ / 0 / ^ overshoot)
        if row != 1:
            cells[row][1] = CellType.WALL

        corr_data.append({
            'row':        row,
            'right_going': right_going,
            'goblins':    gobs,
        })

    # Connector doors
    for row in _GOBLIN_GAUNTLET_RIGHT_CONN_ROWS:
        for c in _GOBLIN_GAUNTLET_RC_COLS:
            entities.append({'kind': 'door', 'at': [row, c], 'opaque': True})
    for row in _GOBLIN_GAUNTLET_LEFT_CONN_ROWS:
        for c in _GOBLIN_GAUNTLET_LC_COLS:
            entities.append({'kind': 'door', 'at': [row, c], 'opaque': True})

    # Final section goblins (rows 17, no water)
    n17   = rng.randint(3, 6)
    space = 46  # cols 5-50
    gobs17: list = []
    c = 5 + rng.randint(0, 3)
    for _ in range(n17):
        if c > 50:
            break
        gobs17.append(c)
        c += space // n17 + rng.randint(-1, 2)
    for gc in gobs17:
        entities.append({'kind': 'goblin', 'at': [17, gc],
                         'hp': 1, 'max_hp': 1, 'ai': 'chase', 'ai_speed': 2})

    # Gate doors at col 53 (rows 17 and 18) + exit
    entities.append({'kind': 'locked_door', 'at': [17, 53], 'opaque': True})
    entities.append({'kind': 'locked_door', 'at': [18, 53], 'opaque': True})
    entities.append({'kind': 'exit', 'at': [18, 56]})

    par = _par_goblin_gauntlet(corr_data, gobs17)

    level = _Level(
        name='The Goblin Gauntlet', seed=seed,
        rows=_GOBLIN_GAUNTLET_ROWS, cols=_GOBLIN_GAUNTLET_COLS,
        cells=[''.join(_CELL_CODE[c] for c in row) for row in cells],
        spawn=(1, 1), exit=(18, 56),
        char_runs=runes,
        entities=entities,
        solution=_answer_l5(corr_data, gobs17))

    dungeon = _fmt_build(level, par=par)   # each cell of the gauntlet is dark
    return dungeon                          # behind its door (the opaque doors)


# ── The Warden's Keep ─────────────────────────────────────────────

_WARDENS_KEEP_ROWS = 7
_WARDENS_KEEP_COLS = 44

# Layout (7 × 44):
#   Row 0/6 : all wall
#   Row 3   : open floor 0-42  (entry 0, seal_door 16, Warden 27, locked_door 38, exit 39)
#   Rows 1,5: floor 0-15, wall 16, floor 17-37, wall 38, floor 39-42
#   Rows 2,4: stone columns (wall at even cols 0-16), open floor 17-37, wall 38, floor 39-42


def _par_wardens_keep() -> int:
    """Simulated par for The Warden's Keep.

    Optimal strategy (layout fixed; combat cost is seed-dependent):

    Phase 1 — Entry (7 keys):
      $    (1): col 0 → col 16 (seal_door; fog stops $ here).
      x    (1): open seal_door, reveals boss room.
      $    (1): col 16 → col 25 (shield at col 26 blocks $).
      k    (1): row 3 → row 2 (detour above shield).
      $    (1): col 25 → col 37 (right end of row 2).
      j    (1): row 2 → row 3.
      0    (1): col 37 → col 27 (warden; shield at col 26 stops 0).

    Phase 2 — Combat (~55 keys, seed-dependent):
      Timer wave: kill 1 pre-spawned goblin, navigate to warden.
      5 warden hits; each of the first 4 spawns 1 goblin on one side.
      After each goblin clear the warden moves one row; shield flips side.
      Shortest observed across 20 seeds: 55 keys.

    Phase 3 — Exit (1 key):
      G    (1): teleport to exit at (3,39).

    Total (best seed): 7 + 55 + 1 = 63.
    Simulated range across 20 seeds: 63–79 (mean 68).
    """
    return 63


def build_dungeon_wardens_keep(seed: int) -> Dungeon:
    ROWS, COLS = _WARDENS_KEEP_ROWS, _WARDENS_KEEP_COLS
    from vimny.engine.editor import _CELL_CODE
    from vimny.sharing.format import Level as _Level, build as _fmt_build
    cells = [[CellType.WALL] * COLS for _ in range(ROWS)]

    # Row 3: full open passage (col 43 stays wall = right border)
    for c in range(COLS - 1):
        cells[3][c] = CellType.FLOOR

    # Rows 1, 5: corridor sides + boss room + treasure room
    for row in (1, 5):
        for c in range(16):
            cells[row][c] = CellType.FLOOR
        # col 16 stays WALL (corridor/boss-room wall separator)
        for c in range(17, 38):
            cells[row][c] = CellType.FLOOR
        # col 38 stays WALL (boss-room/treasure-room wall separator)
        for c in range(39, COLS - 1):
            cells[row][c] = CellType.FLOOR

    # Rows 2, 4: stone columns at even cols 0-16, open boss room, treasure room
    for row in (2, 4):
        for c in range(COLS - 1):
            if c <= 16:
                cells[row][c] = CellType.FLOOR if c % 2 != 0 else CellType.WALL
            elif c < 38:
                cells[row][c] = CellType.FLOOR
            elif c == 38:
                cells[row][c] = CellType.WALL
            else:
                cells[row][c] = CellType.FLOOR

    level = _Level(
        name="The Warden's Keep", seed=seed,
        rows=ROWS, cols=COLS,
        cells=[''.join(_CELL_CODE[c] for c in row) for row in cells],
        spawn=(3, 0),
        exit=(3, 39),
        entities=[
            {'kind': 'seal_door', 'at': [3, 16], 'opaque': True},
            {'kind': 'shield', 'at': [3, 26]},
            {'kind': 'warden', 'at': [3, 27], 'hp': 5, 'max_hp': 5,
             'ai': '', 'summon_timer': 0},
            {'kind': 'locked_door', 'at': [3, 38], 'opaque': True},
            # opened with the key the Warden drops
            {'kind': 'exit', 'at': [3, 39]},
            {'kind': 'heart_container', 'at': [2, 41]},
            {'kind': 'chest_scroll', 'at': [4, 41]},
        ])

    dungeon = _fmt_build(level)
    room = dungeon.rooms[0]
    room.par    = None
    room.budget = math.ceil(_par_wardens_keep() * 1.4)
    return dungeon


# ── The Warden Surveyor (ACT II BOSS) ────────────────────────────────────────
# A massive, vertically-scrolling hall papered with the warden's own verse
# (English + readable Latin). Poems are laid as sentence char-runs so the act's
# structural motions stay useful: '.!?' make )/( boundaries, '()' give % its
# jumps, and spacing drives w/b/e/W/B/E/ge. Words are bounded and punctuated by
# void runes (○) and dynamite — stepping h/l through a gap can be lethal, but
# w/b/e leap word-to-word and only ever LAND on a word, so the survey motions
# are the safe way across the minefield. A clear vertical aisle (col 1) and the
# clear warden row guarantee a hazard-free route to the warden and the exit.
#
# NOTE (phase a — static arena): the two-phase visual/teleport warden AI is
# wired in vimny/game.py next. Here the warden is a plain 5-HP boss tagged 'surveyor'
# so it neither chases nor summons goblins.

_SURVEYOR_CORPUS: list[list[str]] = [
    ["I walked the world to its last wall",
     "and drove my stake where the floor gives way.",
     "All within my line is mine to keep.",
     "And you (who wandered in)? You stay."],
    ["Sight is a kind of reaching.",
     "The eye lays its level across the room,",
     "and what it touches (mark this) it can take.",
     "So watch what the warden watches!"],
    ["Do not trust the dark beyond the runes!",
     "It is not floor; it is the end of floor.",
     "One step too far surveys nothing",
     "but the long fall (and the silence after)."],
    ["Every wall I raise has a seam.",
     "Every shield (you've seen it) bares a back.",
     "Round the sentence, past the bracket -",
     "can you find the side I cannot guard?"],
    ["Count nothing twice! Move by the word,",
     "not the trembling letter. The wise foot",
     "leaps the phrase entire (the whole WORD)",
     "and lands a sentence nearer the gate."],
    ["He frames you. See the bright cells bloom -",
     "that is his gaze (deciding what to cut).",
     "One breath to leave the box. One!",
     "Step wide; he does not aim again."],
    ["Strike me, and I am elsewhere",
     "(a mark recalled, a name made place).",
     "Where will I be? Where I will.",
     "So learn to be where I am not."],
    ["The old god of edges asked no blood,",
     "only that none should move the stone.",
     "Here the stones are hungry (and patient).",
     "The line you cross will cross you back!"],
    ["To map a thing is to confess",
     "you mean to cross it. So read the room!",
     "The periods are stepping-stones;",
     "the brackets (these) swing both ways."],
    ["Lamps gutter, and the long hour turns.",
     "Still he keeps his count (and waits)."],
    ["Noli lineam transgredi meam!",
     "Quod tetigit oculus, custodis est.",
     "Ultra? Nihil."],
    ["Mensus sum noctem passibus.",
     "Oculus meus regula est (et iudex).",
     "Quod video, teneo."],
    ["Hic finis est mundi.",
     "Umbra non est solum.",
     "Cave gradum ultimum!"],
    ["Omnis murus rimam habet.",
     "Omnis clipeus tergum nudat (semper).",
     "Quaere latus quod non tegit!"],
    ["Non dormit qui portam servat.",
     "Numerat gradus tuos (omnes),",
     "patiens ut lapis."],
    ["Feri me: non ero illic!",
     "Nomen meum locus fit.",
     "Ubi ero? Ubi volam.",
     "Disce stare ubi non sum."],
    ["Etiam caelum mensus sum.",
     "Stellas numeravi mediumque iter.",
     "Quod supra est (et infra), meum est."],
]

_WS_ROWS, _WS_COLS = 30, 74
# Horizontal flow like the Warden's Keep, scaled up: a pillared entry corridor
# on the main row (you reach the seal-door with $, open it with x), a BIG hall,
# then the treasure room. The seal-door MUST sit on the player's row — only line
# motions ($/0/^) can land on a closed door; j/l cannot step onto one.
_WS_MAIN_ROW     = 14                 # entry passage / warden / exit row
_WS_ENTRY_C0, _WS_ENTRY_C1 = 1, 15    # pillared entry corridor
_WS_DIVIDE_COL   = 16                 # wall between entry and hall (seal-door gap at main row)
_WS_HALL_TOP, _WS_HALL_BOT = 1, 28    # hall incl. its water ring (perimeter)
_WS_HALL_LEFT    = 17
_WS_HALL_RIGHT   = 66
_WS_INNER_TOP, _WS_INNER_BOT = 2, 27  # dry interior (inside the moat): poem rows
_WS_INNER_RIGHT  = 65
_WS_TEXT_COL     = 18                 # poems / inscription start (interior left)
_WS_WARDEN_ROW   = 14
_WS_SEAL_DOOR    = (14, 16)
_WS_DOOR         = (14, 67)           # locked exit door (gap in the dividing wall)
_WS_EXIT         = (14, 72)
_WS_HEART        = (13, 70)
_WS_SCROLL       = (15, 70)
_WS_SPAWN        = (14, 1)
_WS_KINDS        = ('ancient', 'verdant', 'ember')
_WS_HAZARD_P     = 0.16
# The warden's inscription: '(' left of him and ')' right of him (so % hops
# across to his unshielded far side), and a '.' past him (so ) lands there too).
# No '!' — every '!' becomes a live charge, and the warden row stays clear.
_WS_WARDEN_LINE  = "He guards it (the far seam). Cross now."


def _ws_place_hazard(composite, rng, row: int, col: int) -> None:
    """Drop a dynamite charge on an empty gap cell. (Void runes were replaced by
    the room's water moat — see the ring in build_dungeon_warden_surveyor.)"""
    if col < 1 or col > composite.cols - 2:
        return
    composite.entities.append(Entity(kind='dynamite', row=row, col=col, hp=1))


def _ws_lay_line(composite, rng, row: int, col0: int, text: str, kind: str,
                 hazard_p: float, skip=()) -> None:
    """Lay one verse line as CharRuns with spaces INCLUDED, so f/t skip blanks
    and land on real punctuation (an empty floor cell reads as '.'). Runs break
    only at: every '!' (a live charge), some inter-word gaps (random
    void/dynamite), and any `skip` columns — left empty so an entity beneath
    (the warden/shield) shows through to f/F/t/T."""
    skip = set(skip)
    seg: list[str] = []
    seg_col = None

    def _flush():
        nonlocal seg, seg_col
        if seg:
            composite.char_runs.append(
                CharRun(row=row, col=seg_col, symbols=tuple(seg), kind=kind))
        seg, seg_col = [], None

    for i, ch in enumerate(text):
        col = col0 + i
        if col in skip:
            _flush()
            continue
        if ch == '!':                       # every '!' renders/behaves as dynamite
            _flush()
            composite.entities.append(Entity(kind='dynamite', row=row, col=col, hp=1))
            continue
        if ch == ' ' and hazard_p and rng.random() < hazard_p:
            _flush()
            _ws_place_hazard(composite, rng, row, col)
            continue
        if seg_col is None:
            seg_col = col
        seg.append(ch)
    _flush()
    if hazard_p and rng.random() < hazard_p:
        _ws_place_hazard(composite, rng, row, col0 + len(text))


def _ws_lay_corpus(composite, rng, row_top: int, row_bot: int, col0: int,
                   reserved: set) -> None:
    """Paper the hall with the corpus: each poem a paragraph (blank-row gap for
    }/{), kinds cycling for colour, repeating the shuffled corpus until full."""
    poems = list(_SURVEYOR_CORPUS)
    rng.shuffle(poems)
    r, pi, ki = row_top, 0, 0
    while r <= row_bot:
        if pi >= len(poems):
            rng.shuffle(poems)
            pi = 0
        poem = poems[pi]; pi += 1
        kind = _WS_KINDS[ki % len(_WS_KINDS)]; ki += 1
        for line in poem:
            while r <= row_bot and r in reserved:
                r += 1
            if r > row_bot:
                break
            _ws_lay_line(composite, rng, r, col0, line, kind, _WS_HAZARD_P)
            r += 1
        r += 1   # blank separator = a }/{ paragraph break


def regen_surveyor_hall(room, rng) -> None:
    """Re-ink the dry interior with a fresh corpus (poems + '!'-charges), wiping
    the old verse and its dynamite. Used when the Warden Surveyor enters Phase 2
    — the sentences he ate during Phase 1 regrow, reshuffled."""
    room.char_runs = [ru for ru in room.char_runs
                      if not (_WS_INNER_TOP <= ru.row <= _WS_INNER_BOT
                              and _WS_TEXT_COL <= ru.col <= _WS_INNER_RIGHT)]
    room.entities = [e for e in room.entities
                     if not (e.kind == 'dynamite'
                             and _WS_INNER_TOP <= e.row <= _WS_INNER_BOT)]
    _ws_lay_corpus(room, rng, _WS_INNER_TOP, _WS_INNER_BOT, _WS_TEXT_COL, reserved=set())
    room.rebuild_indexes()


def build_dungeon_warden_surveyor(seed: int) -> Dungeon:
    rng = random.Random(seed)
    ROWS, COLS = _WS_ROWS, _WS_COLS
    cells = [[CellType.WALL] * COLS for _ in range(ROWS)]
    MR = _WS_MAIN_ROW

    def _floor(r0, r1, c0, c1):
        for r in range(r0, r1 + 1):
            for c in range(c0, c1 + 1):
                cells[r][c] = CellType.FLOOR

    # Pillared entry corridor (reused from the Keep): a floored 5-row block,
    # passage on the main row, with stone columns (wall at even cols) carved
    # into the rows just above/below — framed by the solid floor edges so the
    # columns actually read as columns.
    _floor(MR - 2, MR + 2, _WS_ENTRY_C0, _WS_ENTRY_C1)
    for pr in (MR - 1, MR + 1):
        for c in range(_WS_ENTRY_C0, _WS_ENTRY_C1 + 1):
            if c % 2 == 0:
                cells[pr][c] = CellType.WALL
    cells[MR][_WS_DIVIDE_COL] = CellType.FLOOR         # seal-door gap (rest of col wall)

    # The big hall: floor the interior, then ring it with a WATER moat. hjkl
    # can't step onto water, so you must LEAP in (w/e/f land on a word/letter
    # beyond it); 0/$ land IN it and drown. The right edge opens a floor gate on
    # the main row so the exit stays walkable once the boss falls.
    _floor(_WS_HALL_TOP, _WS_HALL_BOT, _WS_HALL_LEFT, _WS_HALL_RIGHT)
    for c in range(_WS_HALL_LEFT, _WS_HALL_RIGHT + 1):
        cells[_WS_HALL_TOP][c] = CellType.WATER
        cells[_WS_HALL_BOT][c] = CellType.WATER
    for r in range(_WS_HALL_TOP, _WS_HALL_BOT + 1):
        cells[r][_WS_HALL_LEFT]  = CellType.WATER
        cells[r][_WS_HALL_RIGHT] = CellType.WATER
    cells[MR][_WS_HALL_RIGHT] = CellType.FLOOR         # exit gate (main row only)

    cells[MR][_WS_DOOR[1]] = CellType.FLOOR            # locked-door gap (rest of col wall)
    _floor(MR - 2, MR + 2, _WS_DOOR[1] + 1, COLS - 2)                  # treasure room

    composite = Room(room_type=RoomType.COMBAT, rows=ROWS, cols=COLS)
    composite.cells     = cells
    composite.seed      = seed
    composite.spawn_pos = _WS_SPAWN
    composite.exit_pos  = _WS_EXIT
    composite.char_runs = []
    composite.entities  = []

    # Warden embedded mid-hall on a punctuation-rich inscription so % (or a )/(
    # hop) carries the player across to his unshielded far side.
    line       = _WS_WARDEN_LINE
    lcol       = _WS_TEXT_COL + line.index('(')
    rcol       = _WS_TEXT_COL + line.index(')')
    warden_col = (lcol + rcol) // 2
    shield_col = warden_col - 1
    # leave the warden/shield cells un-lettered so f/F/t/T see 'W' beneath, not the verse
    _ws_lay_line(composite, rng, _WS_WARDEN_ROW, _WS_TEXT_COL, line, 'ember', 0.0,
                 skip=(shield_col, warden_col))

    # Paper the dry interior (skip the warden row, which must stay clear).
    _ws_lay_corpus(composite, rng, _WS_INNER_TOP, _WS_INNER_BOT,
                   _WS_TEXT_COL, reserved={_WS_WARDEN_ROW})

    composite.entities += [
        Entity(kind='seal_door',       row=_WS_SEAL_DOOR[0], col=_WS_SEAL_DOOR[1]),
        Entity(kind='shield',          row=_WS_WARDEN_ROW,   col=shield_col),
        Entity(kind='warden',          row=_WS_WARDEN_ROW,   col=warden_col,
               hp=5, max_hp=5, ai='', tag='surveyor', summon_timer=10**6),
        Entity(kind='locked_door',     row=_WS_DOOR[0], col=_WS_DOOR[1]),   # Warden's key opens it
        Entity(kind='exit',            row=_WS_EXIT[0],      col=_WS_EXIT[1]),
        Entity(kind='heart_container', row=_WS_HEART[0],     col=_WS_HEART[1]),
        Entity(kind='chest_scroll',    row=_WS_SCROLL[0],    col=_WS_SCROLL[1]),
    ]

    composite.rebuild_indexes()
    _doors_block_sight(composite)     # the keep is dark behind its seal + door

    composite.par    = None
    composite.budget = 200    # provisional; refine once the AI / par sim exists

    dungeon = Dungeon(name='The Warden Surveyor', seed=seed)
    dungeon.rooms        = [composite]
    dungeon.current_room = 0
    return dungeon


# ── The WORD Forge layout constants ──────────────────────────────────────────────────

_WORD_FORGE_TOTAL_ROWS    = 10
_WORD_FORGE_TOTAL_COLS    = 58
_WORD_FORGE_CORR_TOP_ROWS = (1, 4, 7)   # top row of each of the 3 corridors
_WORD_FORGE_CORR_LEFT     = 1
_WORD_FORGE_CORR_RIGHT    = 55

_WORD_FORGE_TURN_SPANS = [
    (2, 4, 53, 55),   # RT1: connects C1 to C2 (right side)
    (5, 7,  1,  3),   # LT1: connects C2 to C3 (left side)
]

# Untypable punctuation characters: f/F cannot target them (player can't type them).
# All have isalpha()=False so _is_word_char()=False — treated as punct by w/b/e.
# Drawn from Latin-1 Supplement, General Punctuation, Mathematical Operators, and
# Miscellaneous Technical blocks; chosen to be visually distinct from ASCII code chars.
_WORD_FORGE_UNTYPABLE_PUNCT = (
    '§',   # U+00A7  Section Sign           Latin-1 Supplement
    '‽',   # U+203D  Interrobang            General Punctuation
    '°',   # U+00B0  Degree Sign            Latin-1 Supplement
    '¶',   # U+00B6  Pilcrow Sign           Latin-1 Supplement
    '†',   # U+2020  Dagger                 General Punctuation
    '‡',   # U+2021  Double Dagger          General Punctuation
    '⁂',   # U+2042  Asterism               General Punctuation
    '≃',   # U+2243  Asymptotically Equal   Mathematical Operators
    '≈',   # U+2248  Almost Equal To        Mathematical Operators
    '∞',   # U+221E  Infinity               Mathematical Operators
    '∴',   # U+2234  Therefore              Mathematical Operators
    '⌘',   # U+2318  Place of Interest      Miscellaneous Technical
)

# (row, col_start, text, kind) — placed as adjacent single-char clusters.
# w stops at word/punct type boundaries within each group (many steps).
# W treats the whole adjacent block as one WORD (one step per group).
# Punctuation chars in code groups force 2-digit w counts (3 ks) vs 1-digit W counts (2 ks).
# Anchors (W4 at 1,53 and B1 at 4,3) are placed separately per-seed from _WORD_FORGE_UNTYPABLE_PUNCT.
_WORD_FORGE_CODE_GROUPS = [
    # C1 (rows 1-2, left→right): W teaching — `4W` from col 1 → col 53 in 2 keystrokes
    (1,  3, "result=func",         'ember'),   # W1 cols  3-13
    (1, 16, "(a,b)+val",           'ember'),   # W2 cols 16-24
    (1, 27, "x=y*2",               'ember'),   # W3 cols 27-31
    # W4 anchor at (1, 53-54): seed-varying untypable pair (see build_dungeon_word_forge)
    # C2 (rows 4-5, right→left): B teaching — `4B` from col 53 → col 3 in 2 keystrokes
    # B1 anchor at (4, 3-4): seed-varying untypable pair (see build_dungeon_word_forge)
    (4, 25, "x+=y*2",              'ember'),   # B2 cols 25-30
    (4, 35, "int[]",               'ember'),   # B3 cols 35-39
    (4, 43, "main()",              'ember'),   # B4 cols 43-48
    # C3 (rows 7-8, left→right): E teaching — `4E` from col 3 → col 51 (exit) in 2 keystrokes
    (7,  3, "if",                  'ember'),   # E1 cols  3-4
    (7,  7, "res",                 'ember'),   # E2 cols  7-9
    (7, 12, "val",                 'ember'),   # E3 cols 12-14
    (7, 33, "output=data[n]._key", 'ember'),   # E4 cols 33-51 → exit
]

def _l7_place_code_group(runes, row, col_start, text, kind='ember'):
    """Place text as adjacent single-char CharRuns (WORD group for W/B/E teaching)."""
    for i, ch in enumerate(text):
        runes.append(CharRun(row=row, col=col_start + i, symbols=(ch,), kind=kind))


def _l7_fill_row(composite, rng, row, col_start, col_end,
                 density=0.40, blocked=frozenset(), word_tbl=None):
    """Fill one corridor row with spaced non-void character runs (w ≡ W here)."""
    c = col_start
    while c <= col_end:
        if rng.random() < density:
            kind = rng.choice(_WORD_RUNE_KINDS)
            if word_tbl is not None:
                max_len = min(7, col_end - c + 1)
                length  = rng.randint(2, max(2, max_len))
                word    = rng.choice(word_tbl.get(length) or word_tbl[1])
                syms    = tuple(word)
            else:
                syms = _make_rune_syms(rng, kind)
            w = len(syms)
            if c + w - 1 <= col_end:
                if not any((row, cc) in blocked
                           for cc in range(c - 1, c + w + 1)):
                    composite.char_runs.append(
                        CharRun(row=row, col=c, symbols=syms, kind=kind))
                    c += w + rng.randint(2, 3)   # 2-3 cell gap → w ≡ W
                    continue
        c += 1


def _dijkstra_par_WBE(composite, return_path=False):
    """Minimum-keystroke Dijkstra for The WORD Forge: count hjkl + w b e + W B E.

    WORD = maximal contiguous cluster sequence (no floor gap between clusters).
    W: start of next WORD.  B: start of current (or prev) WORD.  E: end of WORD.
    """
    ROWS, COLS = composite.rows, composite.cols
    entry = composite.spawn_pos
    goal  = composite.exit_pos
    max_n = max(ROWS, COLS)

    def _rune(r, c):
        ru = composite.char_run_at(r, c)
        return ru if (ru and ru.kind != 'void') else None

    def _ok(r, c):
        if not composite.is_passable(r, c):
            return False
        ru = composite.char_run_at(r, c)
        return not (ru and ru.kind == 'void')

    # -- word/punct type helpers --
    # THE engine word-class rule (vim utf_class) — never a local copy, so the
    # solver can't drift from real play.
    _is_wc = _is_word_char

    def _char_at(r, c):
        ru = composite.char_run_at(r, c)
        if ru is None or ru.kind == 'void':
            return None
        return ru.symbols[c - ru.col]

    # -- cluster-level motions (w/b/e) — word/punct type-boundary aware --
    def _w(r, c):
        ch = _char_at(r, c)
        if ch is not None:
            t = _is_wc(ch)
            scan = c + 1
            while scan < COLS and composite.is_passable(r, scan):
                ch2 = _char_at(r, scan)
                if ch2 is None:
                    break
                if _is_wc(ch2) != t:
                    break
                scan += 1
        else:
            scan = c + 1
        for nc in range(scan, COLS):
            if not composite.is_passable(r, nc):
                return None
            if _rune(r, nc):
                return (r, nc)
        return None

    def _b(r, c):
        ch = _char_at(r, c)
        if ch is not None:
            t  = _is_wc(ch)
            rs = c
            for sc in range(c - 1, -1, -1):
                if not composite.is_passable(r, sc):
                    break
                ch2 = _char_at(r, sc)
                if ch2 is None or _is_wc(ch2) != t:
                    break
                rs = sc
            if rs < c:
                return (r, rs)
            prev = c - 1
        else:
            prev = c - 1
        while prev >= 0 and composite.is_passable(r, prev) and _char_at(r, prev) is None:
            prev -= 1
        if prev >= 0 and composite.is_passable(r, prev) and _char_at(r, prev) is not None:
            ch2 = _char_at(r, prev)
            t2  = _is_wc(ch2)
            rs2 = prev
            for sc2 in range(prev - 1, -1, -1):
                if not composite.is_passable(r, sc2):
                    break
                ch3 = _char_at(r, sc2)
                if ch3 is None or _is_wc(ch3) != t2:
                    break
                rs2 = sc2
            return (r, rs2)
        return None

    def _e(r, c):
        ch = _char_at(r, c)
        if ch is not None:
            t   = _is_wc(ch)
            pos = c + 1
            while pos < COLS and composite.is_passable(r, pos):
                ch2 = _char_at(r, pos)
                if ch2 is None or _is_wc(ch2) != t:
                    break
                pos += 1
            end = pos - 1
            if end > c:
                return (r, end)
            scan = pos
        else:
            scan = c + 1
        while scan < COLS and composite.is_passable(r, scan) and _char_at(r, scan) is None:
            scan += 1
        if scan < COLS and composite.is_passable(r, scan) and _char_at(r, scan) is not None:
            ch2  = _char_at(r, scan)
            t2   = _is_wc(ch2)
            epos = scan + 1
            while epos < COLS and composite.is_passable(r, epos):
                ch3 = _char_at(r, epos)
                if ch3 is None or _is_wc(ch3) != t2:
                    break
                epos += 1
            return (r, epos - 1)
        return None

    # -- WORD-end / WORD-start helpers --
    def _word_end(r, c):
        cur = _rune(r, c)
        if not cur:
            return None
        pos = cur.col + len(cur.symbols)
        while pos < COLS and composite.is_passable(r, pos):
            ru = _rune(r, pos)
            if ru:
                pos = ru.col + len(ru.symbols)
            else:
                break
        return pos - 1

    def _word_start(r, c):
        cur = _rune(r, c)
        if not cur:
            return None
        ws    = cur.col
        check = cur.col - 1
        while check >= 0 and composite.is_passable(r, check):
            ru = _rune(r, check)
            if ru:
                ws = ru.col
                check = ru.col - 1
            else:
                break
        return ws

    # -- WORD-level motions (W/B/E) --
    def _W(r, c):
        cur  = _rune(r, c)
        scan = (cur.col + len(cur.symbols)) if cur else c + 1
        # skip rest of current WORD (adjacent non-void clusters, no floor gap)
        while scan < COLS and composite.is_passable(r, scan):
            ru = _rune(r, scan)
            if ru:
                scan = ru.col + len(ru.symbols)
            else:
                break
        # skip whitespace (floor gaps) — W stops at walls
        while scan < COLS and composite.is_passable(r, scan) and not _rune(r, scan):
            scan += 1
        if scan < COLS and composite.is_passable(r, scan):
            ru = _rune(r, scan)
            if ru:
                return (r, ru.col)
        return None

    def _B(r, c):
        cur = _rune(r, c)
        if cur:
            ws = _word_start(r, c)
            if ws < c:
                return (r, ws)      # jump to start of current WORD
            pos = ws - 1            # already at WORD start; go to previous
        else:
            pos = c - 1
        while pos >= 0 and composite.is_passable(r, pos) and not _rune(r, pos):
            pos -= 1
        if pos >= 0 and composite.is_passable(r, pos):
            ru = _rune(r, pos)
            if ru:
                return (r, _word_start(r, pos))
        return None

    def _E(r, c):
        cur = _rune(r, c)
        if cur:
            end = _word_end(r, c)
            if end > c:
                return (r, end)
            pos = end + 1
        else:
            pos = c + 1
        while pos < COLS and composite.is_passable(r, pos) and not _rune(r, pos):
            pos += 1
        if pos < COLS and composite.is_passable(r, pos):
            ru = _rune(r, pos)
            if ru:
                return (r, _word_end(r, pos))
        return None

    def neighbors(node):
        r, c = node
        # count h/j/k/l — here a void cell BREAKS the count (via _ok), no bypass
        yield from _count_moves(_ok, r, c, max_n)
        # $ / 0 / ^ — scan by passability (void transparent), land only on _ok cells
        left, right = _row_segment(lambda cc: composite.is_passable(r, cc),
                                   lambda cc: composite.is_passable(r, cc),
                                   c, COLS)
        if right != c and _ok(r, right):
            yield (r, right), '$', 1
        if left != c and _ok(r, left):
            yield (r, left), '0', 1
        for cc in range(left, right + 1):          # ^ — first char terminates the scan
            if composite.char_run_at(r, cc):
                if _ok(r, cc):
                    yield (r, cc), '^', 1
                break
        # chain w/b/e/W/B/E
        for fn, key in ((_w, 'w'), (_b, 'b'), (_e, 'e'),
                        (_W, 'W'), (_B, 'B'), (_E, 'E')):
            yield from _word_motion_chain(fn, key, (r, c), max_n, _ok)

    cost, prev, end = _dijkstra(entry, lambda node: node == goal, neighbors)
    if return_path:
        return (cost, _join_path(prev, end, merge_single=False)) if cost is not None else (None, '')
    return cost


# ── Vocab tables (lazy-loaded from art/) ─────────────────────────────────
_VOCAB_PLAIN_BY_LEN: dict | None = None
_VOCAB_MIXED_BY_LEN: dict | None = None
_ART_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'art')


def _load_vocab_tables() -> None:
    global _VOCAB_PLAIN_BY_LEN, _VOCAB_MIXED_BY_LEN
    if _VOCAB_PLAIN_BY_LEN is not None:
        return

    def _parse(fname: str) -> dict:
        tbl: dict = {}
        with open(os.path.join(_ART_DIR, fname), encoding='utf-8') as fh:
            for raw in fh:
                word = raw.rstrip('\n').rstrip(' ')
                if not word or word.startswith('#'):
                    continue
                tbl.setdefault(len(word), []).append(word)
        return tbl

    _VOCAB_PLAIN_BY_LEN = _parse('vocab_plain.txt')
    _VOCAB_MIXED_BY_LEN = _parse('vocab_mixed.txt')


def vocab_table(pool: str) -> dict:
    """'plain' | 'mixed' → the by-length word table, loaded from art/ on first
    ask. The public door for other modules (sharing.vocab) — they must not
    reach for the private tables or drive the loader themselves."""
    _load_vocab_tables()
    return _VOCAB_PLAIN_BY_LEN if pool == 'plain' else _VOCAB_MIXED_BY_LEN


# ── The Backward Vaults layout constants ──────────────────────────────────────────────────
_BACKWARD_VAULTS_TOTAL_ROWS = 14
_BACKWARD_VAULTS_TOTAL_COLS = 40
_BACKWARD_VAULTS_CORR_ROWS  = (1, 3, 5, 7, 9, 11)   # one row per corridor
_BACKWARD_VAULTS_CORR_LEFT  = 1
_BACKWARD_VAULTS_CORR_RIGHT = 38

_BACKWARD_VAULTS_TURN_SPANS = [
    (1,  3,  36, 38),  # RT1: C1→C2, right side
    (3,  5,   1,  3),  # LT1: C2→C3, left side
    (5,  7,  36, 38),  # RT2: C3→C4, right side
    (7,  9,   5,  6),  # LT2: C4→C5, ge-critical (only cols 5-6 passable in row 8)
    (9,  11, 37, 38),  # RT3: C5→C6, right side
    (11, 12, 19, 19),  # LT3: C6→exit, gE-critical (only col 19 passable in row 12)
]


def _par_backward_vaults(composite, return_path: bool = False):
    """Minimum-keystroke Dijkstra for The Backward Vaults:
    hjkl + $ ^ 0 + w b e + W B E (count) + ge gE (count).

    State = (row, col).  Cost model follows _keystroke_cost in vimny/game.py:
      count=1 → 1 ks; count=n → len(str(n))+1 ks.
      ge/gE each add +1 base (cost 2 for n=1, len(str(n))+2 for n>1).
    W/B/E treat adjacent clusters as one WORD; for this dungeon's gap-separated
    layout W≡w, B≡b, E≡e, so par is unchanged by their inclusion.
    """
    ROWS, COLS = composite.rows, composite.cols
    entry = composite.spawn_pos
    goal  = composite.exit_pos
    max_n = max(ROWS, COLS)

    def _rune(r, c):
        ru = composite.char_run_at(r, c)
        return ru if (ru and ru.kind != 'void') else None

    def _ok(r, c):
        if not composite.is_passable(r, c):
            return False
        ru = composite.char_run_at(r, c)
        return not (ru and ru.kind == 'void')

    # THE engine word-class rule (vim utf_class) — never a local copy, so the
    # solver can't drift from real play.
    _is_wc = _is_word_char

    def _char_at(r, c):
        ru = composite.char_run_at(r, c)
        if ru is None or ru.kind == 'void':
            return None
        return ru.symbols[c - ru.col]

    # ── cluster-level motions matching vimny/engine/motion.py ──────────────────────

    def _w(r, c):
        ch = _char_at(r, c)
        if ch is not None:
            t    = _is_wc(ch)
            scan = c + 1
            while scan < COLS and composite.is_passable(r, scan):
                ch2 = _char_at(r, scan)
                if ch2 is None:
                    break
                if _is_wc(ch2) != t:
                    break
                scan += 1
        else:
            scan = c + 1
        for nc in range(scan, COLS):
            if not composite.is_passable(r, nc):
                return None
            if _rune(r, nc):
                return (r, nc)
        return None

    def _b(r, c):
        ch = _char_at(r, c)
        if ch is not None:
            t  = _is_wc(ch)
            rs = c
            for sc in range(c - 1, -1, -1):
                if not composite.is_passable(r, sc):
                    break
                ch2 = _char_at(r, sc)
                if ch2 is None or _is_wc(ch2) != t:
                    break
                rs = sc
            if rs < c:
                return (r, rs)
            prev = c - 1
        else:
            prev = c - 1
        while prev >= 0 and composite.is_passable(r, prev) and _char_at(r, prev) is None:
            prev -= 1
        if prev >= 0 and composite.is_passable(r, prev) and _char_at(r, prev) is not None:
            ch2 = _char_at(r, prev)
            t2  = _is_wc(ch2)
            rs2 = prev
            for sc2 in range(prev - 1, -1, -1):
                if not composite.is_passable(r, sc2):
                    break
                ch3 = _char_at(r, sc2)
                if ch3 is None or _is_wc(ch3) != t2:
                    break
                rs2 = sc2
            return (r, rs2)
        return None

    def _e(r, c):
        ch = _char_at(r, c)
        if ch is not None:
            t   = _is_wc(ch)
            pos = c + 1
            while pos < COLS and composite.is_passable(r, pos):
                ch2 = _char_at(r, pos)
                if ch2 is None or _is_wc(ch2) != t:
                    break
                pos += 1
            end = pos - 1
            if end > c:
                return (r, end)
            scan = pos
        else:
            scan = c + 1
        while scan < COLS and composite.is_passable(r, scan) and _char_at(r, scan) is None:
            scan += 1
        if scan < COLS and composite.is_passable(r, scan) and _char_at(r, scan) is not None:
            ch2  = _char_at(r, scan)
            t2   = _is_wc(ch2)
            epos = scan + 1
            while epos < COLS and composite.is_passable(r, epos):
                ch3 = _char_at(r, epos)
                if ch3 is None or _is_wc(ch3) != t2:
                    break
                epos += 1
            return (r, epos - 1)
        return None

    def _ge(r, c):
        """Backward to end of previous non-void cluster (matching motion.py ge)."""
        nc = c - 1
        while nc >= 0:
            if not composite.is_passable(r, nc):
                break
            ru = composite.char_run_at(r, nc)
            if ru and ru.kind != 'void':
                end_col = ru.col + len(ru.symbols) - 1
                if end_col < c:
                    return (r, end_col)
                nc = ru.col - 1  # cursor at/within this cluster: skip left of its start
                continue
            nc -= 1
        return None

    def _gE(r, c):
        """Backward to end of previous WORD (adjacent clusters, matching motion.py gE)."""
        nc = c - 1
        while nc >= 0:
            if not composite.is_passable(r, nc):
                break
            ru = composite.char_run_at(r, nc)
            if ru and ru.kind != 'void':
                end = ru.col + len(ru.symbols) - 1
                # extend right to find WORD end
                cc = end + 1
                while cc < COLS and composite.is_passable(r, cc):
                    r2 = composite.char_run_at(r, cc)
                    if r2 and r2.kind != 'void':
                        end = r2.col + len(r2.symbols) - 1
                        cc  = end + 1
                    else:
                        break
                if end < c:
                    return (r, end)
                nc = ru.col - 1  # cursor within this WORD: skip left of its start
                continue
            nc -= 1
        return None

    def _word_end_L7(r, c):
        cur = _rune(r, c)
        if not cur:
            return None
        pos = cur.col + len(cur.symbols)
        while pos < COLS and composite.is_passable(r, pos):
            ru = _rune(r, pos)
            if ru:
                pos = ru.col + len(ru.symbols)
            else:
                break
        return pos - 1

    def _word_start_L7(r, c):
        cur = _rune(r, c)
        if not cur:
            return None
        ws    = cur.col
        check = cur.col - 1
        while check >= 0 and composite.is_passable(r, check):
            ru = _rune(r, check)
            if ru:
                ws = ru.col
                check = ru.col - 1
            else:
                break
        return ws

    def _W(r, c):
        cur  = _rune(r, c)
        scan = (cur.col + len(cur.symbols)) if cur else c + 1
        while scan < COLS and composite.is_passable(r, scan):
            ru = _rune(r, scan)
            if ru:
                scan = ru.col + len(ru.symbols)
            else:
                break
        while scan < COLS and composite.is_passable(r, scan) and not _rune(r, scan):
            scan += 1
        if scan < COLS and composite.is_passable(r, scan):
            ru = _rune(r, scan)
            if ru:
                return (r, ru.col)
        return None

    def _B(r, c):
        cur = _rune(r, c)
        if cur:
            ws = _word_start_L7(r, c)
            if ws < c:
                return (r, ws)
            pos = ws - 1
        else:
            pos = c - 1
        while pos >= 0 and composite.is_passable(r, pos) and not _rune(r, pos):
            pos -= 1
        if pos >= 0 and composite.is_passable(r, pos):
            ru = _rune(r, pos)
            if ru:
                return (r, _word_start_L7(r, pos))
        return None

    def _E(r, c):
        cur = _rune(r, c)
        if cur:
            end = _word_end_L7(r, c)
            if end > c:
                return (r, end)
            pos = end + 1
        else:
            pos = c + 1
        while pos < COLS and composite.is_passable(r, pos) and not _rune(r, pos):
            pos += 1
        if pos < COLS and composite.is_passable(r, pos):
            ru = _rune(r, pos)
            if ru:
                return (r, _word_end_L7(r, pos))
        return None

    def neighbors(node):
        r, c = node
        # count j/k then h/l — this solver's scan order is j,k,l,h (kept for tie-breaks)
        yield from _count_moves(_ok, r, c, max_n, dirs=((1, 0), (-1, 0), (0, 1), (0, -1)))
        # $ / 0 / ^ — scan by passability, land only on _ok cells
        left, right = _row_segment(lambda cc: composite.is_passable(r, cc),
                                   lambda cc: composite.is_passable(r, cc),
                                   c, COLS)
        if right != c and _ok(r, right):
            yield (r, right), '$', 1
        if left != c and _ok(r, left):
            yield (r, left), '0', 1
        for cc in range(left, right + 1):          # ^ — first char terminates the scan
            if composite.char_run_at(r, cc):
                if _ok(r, cc):
                    yield (r, cc), '^', 1
                break
        # count ge/gE (backward-end, +1 base for the 'g' prefix) — BEFORE w/b/e so ge/gE
        # win tie-breaks at equal cost (the pedagogically preferred motion); ge before gE.
        for fn, key in ((_ge, 'ge'), (_gE, 'gE')):
            yield from _word_motion_chain(fn, key, (r, c), max_n, _ok, base=2)
        # count W/B/E (WORD) before w/b/e so they win equal-cost tie-breaks
        for fn, key in ((_W, 'W'), (_B, 'B'), (_E, 'E')):
            yield from _word_motion_chain(fn, key, (r, c), max_n, _ok)
        # count w/b/e
        for fn, key in ((_w, 'w'), (_b, 'b'), (_e, 'e')):
            yield from _word_motion_chain(fn, key, (r, c), max_n, _ok)

    cost, prev, end = _dijkstra(entry, lambda node: node == goal, neighbors)
    if return_path:
        return (cost, _join_path(prev, end, merge_single=False)) if cost is not None else (None, '')
    return cost


def build_dungeon_backward_vaults(seed: int) -> Dungeon:
    """ge/gE: The Backward Vaults.

    Six 1-row corridors in a snake pattern (13 rows × 40 cols).  Each corridor
    is bridged to the next by a turn room at alternating ends.  Two turns have
    narrow gaps that physically enforce the lesson:

      LT2 (rows 7-9, cols 5-6)  — ge gap
        C4 anchor: 4-character run at cols 2-5.  ge lands at end=5 (in gap);
        b   lands at start=2 (wall in row 8 — cannot descend).

      LT3 (rows 11-12, col 19) — gE gap
        C6 (row 11) cols 21-38 hold the baphomet/behemoth WORD: two adjacent
        clusters forming one WORD (col 21-28 + col 29-38, no gap between them).
        An anchor character ends at col 19; col 20 is an empty gap.
        From col 38: gE hops the whole WORD in 1 step → lands at col 19 = 2 ks.
        ge needs 2 hops (one per cluster) → 2ge = 3 ks > gE = 2 ks.
        19h = 3 ks, also slower.  gE is the strict winner.

    Guard walls at (2,38) and (4,1) narrow RT1 and LT1:
      (2,38) blocks $→col 38 descent in RT1; player uses 4e→col 36 instead.
      (4,1)  blocks 0→col 1 descent in LT1; player uses ^→col 2 instead.

    Optimal route (par computed by _par_backward_vaults):
      4E 2j ^ 2j $ 2j ge 2j $ 2j gE j
    ge is structurally forced at C4 (b lands at wall in row 8, ge costs same as gE).
    gE is structurally forced at C6 — gE j (2+1=3 ks) beats 2ge j (3+1=4 ks).
    """
    from vimny.engine.editor import _CELL_CODE
    from vimny.sharing.format import Level as _Level, build as _fmt_build
    ROWS, COLS = _BACKWARD_VAULTS_TOTAL_ROWS, _BACKWARD_VAULTS_TOTAL_COLS

    grid = [[CellType.WALL] * COLS for _ in range(ROWS)]

    # ── Carve corridors ───────────────────────────────────────────────────────
    for r in _BACKWARD_VAULTS_CORR_ROWS:
        for c in range(_BACKWARD_VAULTS_CORR_LEFT, _BACKWARD_VAULTS_CORR_RIGHT + 1):
            grid[r][c] = CellType.CORRIDOR

    # ── Carve turn spans ──────────────────────────────────────────────────────
    for r0, r1, c0, c1 in _BACKWARD_VAULTS_TURN_SPANS:
        for r in range(r0, r1 + 1):
            for c in range(c0, c1 + 1):
                grid[r][c] = CellType.CORRIDOR

    # ── Narrow-turn guard walls ────────────────────────────────────────────────
    # RT1 (rows 1-3, cols 36-38): block col 38 at row 2 so $ from C1 cannot
    # descend through the turn's far column — player must use 4e to land at
    # col 36 before descending.
    grid[2][38] = CellType.WALL
    # LT1 (rows 3-5, cols 1-3): block col 1 at row 4 so 0 from C2 cannot
    # descend at the turn's near column — player must use ^ to land at col 2.
    grid[4][1]  = CellType.WALL

    # ── Character runs (seed-varying) ──────────────────────────────────────────
    _load_vocab_tables()
    plain = _VOCAB_PLAIN_BY_LEN
    mixed = _VOCAB_MIXED_BY_LEN
    rng   = random.Random(seed)

    def _sym() -> str:
        return rng.choice(mixed.get(1, []))

    def _plain_word(n: int) -> str:
        return rng.choice(plain.get(n) or plain[3])

    def _mixed_word(n: int) -> str:
        return rng.choice(mixed.get(n) or mixed[1])

    runs: list = []

    # C1 (row 1) — e-teaching: four 3-char clusters, individual characters
    for col, kind in ((5,'ancient'), (13,'verdant'), (22,'ember'), (34,'ancient')):
        runs.append({'row': 1, 'col': col, 'symbols': _sym() + _sym() + _sym(),
                     'kind': kind})

    # C2 (row 3) — b-teaching: four 3-char clusters, individual characters
    for col, kind in ((2,'ember'), (13,'verdant'), (21,'ancient'), (29,'ember')):
        runs.append({'row': 3, 'col': col, 'symbols': _sym() + _sym() + _sym(),
                     'kind': kind})

    # C3 (row 5) — decorative plain words (cols 4-35, safe of LT1/RT2 turns)
    c3c = 4
    while c3c <= 33:
        length = rng.randint(3, min(6, 35 - c3c + 1))
        if length < 3:
            break
        runs.append({'row': 5, 'col': c3c, 'symbols': _plain_word(length),
                     'kind': rng.choice(('ancient','verdant','ember'))})
        c3c += length + rng.randint(1, 3)

    # C4 (row 7) — ge anchor: 4-char ALL-WC plain word at col 2 (end=5 lands in LT2 gap).
    # Must be all word-chars (alpha/digit/_): b from col 38 then goes to col 2 (the run
    # start), which is walled in row 8 — forcing ge/gE over b to reach the LT2 gap.
    # A mixed anchor (e.g. 'win⚑') would let b land at col 5 in 1 ks, beating gE.
    _c4_pool = [w for w in (plain.get(4) or plain[3])
                if all(c.isalpha() or c.isdigit() or c == '_' for c in w)]
    runs.append({'row': 7, 'col': 2,
                 'symbols': rng.choice(_c4_pool or ['proc']), 'kind': 'ancient'})

    # C5 (row 9) — decorative mixed words (cols 7-36, safe of LT2/RT3 turns)
    c5c = 7
    while c5c <= 34:
        length = rng.randint(3, min(6, 36 - c5c + 1))
        if length < 3:
            break
        runs.append({'row': 9, 'col': c5c, 'symbols': _mixed_word(length),
                     'kind': rng.choice(('ancient','verdant','ember'))})
        c5c += length + rng.randint(1, 3)

    # C6 (row 11) — gE lesson: one WORD hop beats counting h
    #
    # The baphomet/behemoth WORD spans cols 21-38 as three ADJACENT clusters
    # (no gaps → they form one WORD, visual: 'b4¶♯∘m3†!=b3♯3m∘†♯'):
    #   Cluster A 'b4¶♯∘m3†'  at cols 21-28  (8 chars)
    #   Cluster S '!='         at cols 29-30  (2 chars, separator)
    #   Cluster B 'b3♯3m∘†♯'  at cols 31-38  (8 chars)
    #
    # From col 38 (player entry, on cluster B):
    #   gE  = 1 WORD hop  → col 19 = 2 ks  ← optimal
    #   3ge = 3 cluster hops (S end → A end → anchor) = 4 ks
    #   19h = 3 ks
    #
    # Anchor character at cols 18-19 (ends at 19): gE landing cell.
    # Col 20 is always an empty gap between anchor and the big WORD.
    # Cols 2-16: seed-randomized mixed filler.
    _kinds3 = ('ancient', 'verdant', 'ember')
    _bb_kind = rng.choice(_kinds3)
    runs.append({'row': 11, 'col': 21, 'symbols': 'b4¶♯∘m3†',
                 'kind': _bb_kind})                                   # A: cols 21-28
    runs.append({'row': 11, 'col': 29, 'symbols': '!=',
                 'kind': _bb_kind})                                   # S: cols 29-30
    runs.append({'row': 11, 'col': 31, 'symbols': 'b3♯3m∘†♯',
                 'kind': _bb_kind})                                   # B: cols 31-38

    # Anchor: 2-char cluster ending at col 19; col 20 always empty
    runs.append({'row': 11, 'col': 18, 'symbols': _sym() + _sym(),
                 'kind': rng.choice(_kinds3)})

    # Seed-randomized mixed filler in cols 2-16
    _c6c = 2
    while _c6c <= 16:
        _flen = rng.randint(1, max(1, min(3, 17 - _c6c)))
        runs.append({'row': 11, 'col': _c6c,
                     'symbols': ''.join(_sym() for _ in range(_flen)),
                     'kind': rng.choice(_kinds3)})
        _c6c += _flen + rng.randint(1, 2)

    level = _Level(
        name='The Backward Vaults', seed=seed,
        rows=ROWS, cols=COLS,
        cells=[''.join(_CELL_CODE[c] for c in row) for row in grid],
        spawn=(1, 1), exit=(12, 19),
        char_runs=runs,
        entities=[{'kind': 'exit', 'at': [12, 19]}])

    dungeon = _fmt_build(level)
    room = dungeon.rooms[0]
    par, path = _par_backward_vaults(room, return_path=True)
    if par is None:
        par, path = 20, '4E 2j ^ 2j $ 2j ge 2j $ 2j gE j'
    room.par    = par
    room.budget = math.ceil(par * 1.4)
    room.answer = path
    return dungeon


def build_dungeon_word_forge(seed: int) -> Dungeon:
    """The WORD Forge — teaches W B E (WORD motions over code-text clusters).

    Three 2-row corridors, snake pattern (10 rows × 58 cols):
      C1 rows 1-2:  left→right   W teaching: packed adjacent code-char clusters
      C2 rows 4-5:  right→left   B teaching: packed adjacent code-char clusters
      C3 rows 7-8:  left→right   E teaching: exit at end of big packed group

    Packed code groups use single-char CharRuns placed adjacently:
      w stops at every char (many keystrokes);  W jumps the whole group (one).
    Spaced character runs in filler zones: w ≡ W (both stop cluster-by-cluster).
    Budget is computed using the W/B/E-optimal path; w/b/e-only far exceeds it.
    """
    from vimny.engine.editor import _CELL_CODE
    from vimny.sharing.format import Level as _Level, build as _fmt_build
    _load_vocab_tables()
    rng     = random.Random(seed)
    # Pick 4 distinct untypable chars: first two → W4 anchor, last two → B1 anchor.
    _four   = rng.sample(_WORD_FORGE_UNTYPABLE_PUNCT, 4)
    _anchor_W = ''.join(_four[:2])   # W4 at (1, 53-54)
    _anchor_B = ''.join(_four[2:])   # B1 at (4,  3-4)
    ROWS, COLS = _WORD_FORGE_TOTAL_ROWS, _WORD_FORGE_TOTAL_COLS

    grid = [[CellType.WALL] * COLS for _ in range(ROWS)]

    # ── Carve corridors (2 rows each) ─────────────────────────────────────────
    for row_top in _WORD_FORGE_CORR_TOP_ROWS:
        for c in range(_WORD_FORGE_CORR_LEFT, _WORD_FORGE_CORR_RIGHT + 1):
            grid[row_top][c]     = CellType.CORRIDOR
            grid[row_top + 1][c] = CellType.CORRIDOR

    # ── Carve turn rooms ─────────────────────────────────────────────────────
    for r0, r1, c0, c1 in _WORD_FORGE_TURN_SPANS:
        for row in range(r0, r1 + 1):
            for col in range(c0, c1 + 1):
                grid[row][col] = CellType.CORRIDOR

    # ── Guard walls (replace the old void guards) ─────────────────────────────
    # RT1: wall the right two descent columns so the C1→C2 turn only exists at
    # col 53 — exactly where W lands (E lands at col 54, into a wall). Forces W.
    grid[3][54] = CellType.WALL
    grid[3][55] = CellType.WALL
    # LT1: wall the col-1 descent so 0/^ to col 1 can't drop into C3; the turn
    # routes through col 3 where B lands. Forces B over 0/^.
    grid[6][1] = CellType.WALL

    # ── Hardcoded code-text clusters ──────────────────────────────────────────
    _hardcoded: list[CharRun] = []
    for row, col_start, text, kind in _WORD_FORGE_CODE_GROUPS:
        _l7_place_code_group(_hardcoded, row, col_start, text, kind)
    # Seed-varying untypable anchors (f/F cannot target these chars)
    _l7_place_code_group(_hardcoded, 1, 53, _anchor_W, 'ember')  # W4 anchor
    _l7_place_code_group(_hardcoded, 4,  3, _anchor_B, 'ember')  # B1 anchor

    # C2 left-end void guards (both rows): the first non-blank cell on each C2
    # row, so ^/0 land on them (death) while B skips back WORD-by-WORD to the
    # anchor at col 3. Forces B over the line-start shortcuts.
    _hardcoded.append(CharRun(row=4, col=1, symbols=('○',), kind='void'))
    _hardcoded.append(CharRun(row=5, col=1, symbols=('○',), kind='void'))

    def _project(runs) -> '_Level':
        return _Level(
            name='The WORD Forge', seed=seed,
            rows=ROWS, cols=COLS,
            cells=[''.join(_CELL_CODE[c] for c in row) for row in grid],
            spawn=(1, 1), exit=(7, 51),
            char_runs=[{'row': ru.row, 'col': ru.col,
                        'symbols': ''.join(ru.symbols), 'kind': ru.kind}
                       for ru in runs],
            entities=[{'kind': 'exit', 'at': [7, 51]}])

    # ── Blocked cell set (code text + exit — filler must not overlap) ──────────
    _bl: set = {(7, 51)}
    for ru in _hardcoded:
        for i in range(len(ru.symbols)):
            _bl.add((ru.row, ru.col + i))
    blocked = frozenset(_bl)

    # A scratch room for the row filler to mutate.
    scratch = Room(room_type=RoomType.ENTRY, rows=ROWS, cols=COLS)
    scratch.cells     = grid
    scratch.spawn_pos = (1, 1)
    scratch.exit_pos  = (7, 51)

    # ── Random filler character runs (secondary rows only; primary rows fixed) ──
    dungeon = None
    for _attempt in range(20):
        scratch.char_runs = list(_hardcoded)
        rng2 = random.Random(rng.randint(0, 2**31))

        _l7_fill_row(scratch, rng2, 2,  3, 52, density=0.45, blocked=blocked, word_tbl=_VOCAB_MIXED_BY_LEN)  # C1r2 baseline
        _l7_fill_row(scratch, rng2, 5,  3, 52, density=0.45, blocked=blocked, word_tbl=_VOCAB_MIXED_BY_LEN)  # C2r5 baseline
        _l7_fill_row(scratch, rng2, 8,  3, 52, density=0.45, blocked=blocked, word_tbl=_VOCAB_MIXED_BY_LEN)  # C3r8 baseline

        # Protect entry and exit from void runes
        entry_r, entry_c = scratch.spawn_pos
        exit_r,  exit_c  = scratch.exit_pos
        scratch.char_runs = [
            ru for ru in scratch.char_runs
            if ru.kind != 'void' or not any(
                ru.row == rr and ru.col <= cc < ru.col + len(ru.symbols)
                for rr, cc in ((entry_r, entry_c), (exit_r, exit_c))
            )
        ]

        dungeon = _fmt_build(_project(scratch.char_runs))
        par, path = _dijkstra_par_WBE(dungeon.rooms[0], return_path=True)
        if par is not None:
            break
    else:
        par, path = 40, ''

    room = dungeon.rooms[0]
    room.par    = par
    room.budget = math.ceil(par * 1.4)
    room.answer = path
    return dungeon


# ── The Sight Sanctum (v + operators on the selection) ─────────────────────────
# "First behold, then strike." The Act VI opener: SELECT FIRST, ACT SECOND,
# performed with the operator classes mastered across Acts IV–V. Four chambers
# on the hardened Annex chassis (west spine, exact-text doors, gate-row bolts,
# FINAL SEAL exit); each door opens while its plaque's words read true — EXACT
# whole-row text, so the kept words must SURVIVE the strike (a linewise dd/dj
# that eats a kept word is a dead route, the anti-cheese that prices the
# chambers).
#
# The honest wins of charwise v (everything else ties operator+motion by ±1):
#   • the ragged charwise MULTI-ROW span — normal mode has NO charwise
#     multi-row operator, so v{span}d / v{span}c do in ONE op what costs
#     D + ^ + dt{ch} piecewise (the Cut and Word chambers);
#   • the PER-ROW charwise ~ — the Case chamber's guard words sit exactly
#     where the linewise g~j would wrongly flip them, so only the precise
#     selection toggle reads true;
#   • the SEARCH-EXTENDED selection — /{pat} from visual is a motion that
#     grows the live selection across rows; no operator takes a search
#     (the Seal chamber: v /{x}<CR> h d beats the eye-led v 2j t{x} d by one).
#
# FORCING BY PAR (standard 1.4 budget): the leanest old route never clears
# the middle blight rows (the doors check only the target rows) — D for
# heads, ^dt{ch} for tails, i+s for the cure, count-~ for the case words —
# and WINS at 1★, one key inside the budget. Two decoy copies of each
# t-target's initial seeded in the blight price out lazy one-char searches
# in the vj-chambers (each decoy costs an n), while the Seal tail's initial
# is PRISTINE level-wide — the one named thing, so the search lesson lands.
# Blight rows that must survive in part carry their kept word at the row EDGE
# (head at line start, tail at line end) — middle rows of a charwise
# multi-row span are always consumed whole, so nothing kept may live there.
_SS_ROWS, _SS_COLS = 20, 46
_SS_SPINE  = 2                      # every row's first standable (the jump audit)
_SS_BAY_W  = 3                      # bay floor cols 3..43; east wall 44
_SS_BAY_E  = 43
_SS_TEXT_MIN = 3                    # earliest col a saying may start
_SS_BLIGHT0 = 15                    # middle/tail rows' blight starts here
_SS_SHAFT  = 19                     # the sight-line — AND the anchor: every
                                    # head ends at 18, every head-row blight
                                    # starts here; a one-cell light shaft
                                    # through each bay separator at this
                                    # column rides the plain j-hops (the
                                    # spine stays every row's first standable)
_SS_SHAFT_ROWS = (6, 10, 13)        # the bay separators it pierces
_SS_THROAT = 17                     # spine-only row joins the bays to the gate
_SS_GATE   = 18
_SS_BOLT0  = 3                      # bolts cols 3..6, one per chamber
_SS_EXIT   = (18, 7)                # the FINAL SEAL — stone until all read true
_SS_TAIL0  = 29                     # tail words sit at the row end (blight 15..28)
_SS_SPAWN  = (2, 19)                # over the first blight: j drops onto it

# SENSE, NOT DECREE (the design law): every chamber is a
# famous saying INTERRUPTED by a rot-span. The Cut/Word/Seal chambers keep
# the saying's opening words at the head row's edge and its remainder at the
# tail row's edge — the strike removes exactly the rot, and the saying
# stands complete, split across two carved lines. The Word chamber's head is
# the saying missing one final 's' (the typed cure); the Case chamber is a
# saying whose MIDDLE words are case-mangled between sound flanks. No west
# plaques: the player knows the readings by heart.
#
# The canonical tape (hand-measured, driven — the buffer mutates, so no
# Dijkstra). The chambers are ANCHOR-ALIGNED at the shaft column: the spawn
# drops onto the first blight, and every op leaves the cursor where the
# next bay's plain j-hop lands on the next anchor:
#   j       v 2j t{a} d    — Cut:   7
#   4j      v 2j t{b} c s  — Word:  9   (post-Esc cursor → the Case anchor)
#   4j      v j e ~        — Case:  6   (cursor → selection start)
#   3j      v /{x}<CR> h d    — Seal:  7   (the search Enter spends nothing)
#   G $                    — exit:  2
_SS_PAR = 31

# Case chamber pool: (west flank, flip 1, flip 2, east flank) — the middle
# two segments stand case-mangled. Flip 2 is laid at _SS_BLIGHT0 and must
# END at col 19..21 (len 6-8: the v j landing sits strictly inside it, so
# `e` stops at ITS end, west of the east flank).
# (flip 2 is exactly 6 CELLS so the rival's count-~ and its h-walk back to
# the shaft stay seed-invariant inside the standard budget)
_SS_CASE_POOL = (
    ('actions', 'speak', 'louder', 'than words'),
    ('all that', 'glitters', 'is not', 'gold'),
)
# Word chamber pool: (head missing its final s, the rest) — the typed cure
# is the single 's' that mends the saying.
_SS_WORD_POOL = (
    ('many hand', 'make light work'),
    ('no new', 'is good news'),
    ('still water', 'run deep'),
)


def _ss_answer(words: dict) -> str:
    a = words['cut'][1][0]        # the Cut tail's initial (t{a})
    b = words['word'][1][0]       # the Word tail's initial (t{b})
    x = words['seal'][1][0]       # the Seal tail's pristine initial (/{x})
    return f'j v 2j t{a} d 4j v 2j t{b} c s<Esc> 4j v j e ~ 3j v /{x}<CR> h d G $'


def _ss_splits(saying_words, head_cap=16, tail_cap=15):
    """All (head, tail) splits of a saying that fit the anchored geometry:
    head right-aligns to end at col 18, tail starts at _SS_TAIL0."""
    out = []
    for k in range(1, len(saying_words)):
        head = ' '.join(saying_words[:k])
        tail = ' '.join(saying_words[k:])
        if len(head) <= head_cap and len(tail) <= tail_cap:
            out.append((head, tail))
    return out


def _ss_draw_words(rng) -> dict:
    """Draw the chambers' sayings. The Case and Word chambers draw from
    their fixed-split pools; the Cut chamber takes any fitting split of a
    fresh saying; the Seal draws LAST, filtered so its tail's INITIAL
    appears in no other laid letter (nor the decoys nor the typed 's') —
    the pristine search anchor, /{x}<CR> has one landing."""
    from vimny.content import proverbs as _pv

    for _ in range(200):
        case = rng.choice(_SS_CASE_POOL)
        word = rng.choice(_SS_WORD_POOL)
        used_texts = {' '.join(case), f"{word[0]}s {word[1]}"}
        cut_cands = []
        for w in _pv.PLAIN:
            if any(t in ' '.join(w) or ' '.join(w) in t for t in used_texts):
                continue
            cut_cands += [(w, s) for s in _ss_splits(w)]
        if not cut_cands:
            continue
        cut_w, cut = rng.choice(cut_cands)
        a, b = cut[1][0], word[1][0]           # the t-target initials
        used = set(''.join(case) + ''.join(word) + ''.join(cut)) | {a, b, 's'}
        used.discard(' ')
        seal_cands = []
        for w in _pv.PLAIN:
            if w == cut_w or any(' '.join(w) in t or t in ' '.join(w)
                                 for t in used_texts):
                continue
            seal_cands += [s for s in _ss_splits(w)
                           if s[1][0] not in used and s[1][0] not in s[0]]
        if not seal_cands:
            continue
        seal = rng.choice(seal_cands)
        targets = [cut[0], cut[1], word[0] + 's', word[1],
                   f'{case[0]} {case[1]}', f'{case[2]} {case[3]}',
                   seal[0], seal[1]]
        if len(set(targets)) != len(targets):
            continue
        return {'cut': cut, 'word': word, 'case': case, 'seal': seal}
    raise ValueError('sight_sanctum: no pristine seal saying after 200 draws')


def _ss_chambers(words: dict):
    """The chamber table for this seed: (name, bay rows, floor runs, door
    targets). Blight is '#'; two DECOYS of each t-target's initial sit in the
    rows the t-motion never scans (t is row-local; / is buffer-wide and pays
    an n per decoy — pricing out the lazy one-char search). Kept text lives
    only at row EDGES: charwise multi-row middles are always consumed whole.
    Multi-word texts are laid one run per word by the builder."""
    b0, an, tl = _SS_BLIGHT0, _SS_SHAFT, _SS_TAIL0
    a_head, a_tail = words['cut']
    w_head, w_tail = words['word']
    g1, f1, f2, g2 = words['case']
    s_head, s_tail = words['seal']
    a, b = a_tail[0], w_tail[0]

    def head_at(text):
        return an - 1 - len(text)              # right-aligned, ends col 18

    return (
        # Cut (v 2j t{a} d): the saying's opening at the head row's edge,
        # its remainder at the tail row's end, rot between
        ('cut',  (3, 4, 5),
         ((3, head_at(a_head), a_head), (3, an, f'##{a}###{a}###'),
          (4, b0, f'#####{a}###{a}####'),
          (5, b0, '#' * 14), (5, tl, a_tail)),
         (a_head, a_tail)),
        # Word (v 2j t{b} c s): the head is the saying missing one 's' —
        # the cure is TYPED at the anchor and fuses onto the head
        # the word head ends flush at 18 (no gap): the typed 's' at the
        # anchor fuses onto it — 'still water'+'s'
        ('word', (7, 8, 9),
         ((7, head_at(w_head) + 1, w_head), (7, an, f'##{b}#####{b}#'),
          (8, b0, f'######{b}#######'),
          (9, b0, '#' * 14), (9, tl, w_tail)),
         (w_head + 's', w_tail)),
        # Case (v j e ~): the saying's middle two segments stand flipped
        # between sound flanks — the west flank before the anchor (top row
        # toggles anchor→line end), the east flank past the cursor (bottom
        # row toggles line start→cursor). The linewise g~j flips the flanks
        # too and reads false: per-row charwise ~ is forced.
        ('case', (11, 12),
         ((11, head_at(g1), g1), (11, an, f1.upper()),
          (12, b0, f2.upper()), (12, b0 + len(f2) + 1, g2)),
         (f'{g1} {f1}', f'{f2} {g2}')),
        # Seal (v /{x}<CR> h d): the tail's initial is pristine level-wide —
        # the one named thing; name what you see
        ('seal', (14, 15, 16),
         ((14, head_at(s_head), s_head), (14, an, '#' * 10),
          (15, b0, '#' * 17),
          (16, b0, '#' * 14), (16, tl, s_tail)),
         (s_head, s_tail)),
    )


def build_dungeon_sight_sanctum(seed: int) -> Dungeon:
    """The Sight Sanctum (slug `sight_sanctum`): v + d/c/~ on the selection.

    Four chambers on the hardened Annex chassis — select first, act second.
    The Cut and Word chambers force the charwise multi-row span (no normal-
    mode equivalent); the Case chamber forces the per-row charwise ~ (its
    guard words kill the linewise toggle); the Seal chamber forces the
    search-extended selection on the level's one pristine letter. Vocabulary
    is drawn per seed; slot lengths are fixed. See the section header."""
    from vimny.engine.editor import _CELL_CODE
    from vimny.sharing.format import Level as _Level, _parse_seal, build as _fmt_build
    rng = random.Random(seed)
    words = _ss_draw_words(rng)
    chambers = _ss_chambers(words)

    R, C = _SS_ROWS, _SS_COLS
    grid = [[CellType.WALL] * C for _ in range(R)]
    for r in range(2, _SS_GATE + 1):                     # the spine
        grid[r][_SS_SPINE] = CellType.FLOOR
    for _name, rows, _runs, _targets in chambers:        # the bays
        for r in rows:
            for c in range(_SS_BAY_W, _SS_BAY_E + 1):
                grid[r][c] = CellType.FLOOR
    for r in _SS_SHAFT_ROWS:                             # the light shaft —
        grid[r][_SS_SHAFT] = CellType.FLOOR             # NOT the throat row:
    # the gate row is still reachable only along the spine (teleport audit)
    # gate row: spine only — bolts and the exit STAY WALL (the FINAL SEAL);
    # the tick floors each bolt as its chamber reads true, the seal last.
    grid[_SS_SPAWN[0]][_SS_SPAWN[1]] = CellType.FLOOR   # the drop-in

    runs: list = []
    doors = []
    for i, (_name, _rows, ch_runs, targets) in enumerate(chambers):
        for rr, cc, text in ch_runs:
            # one run per word — a literal space glyph is a punctuation
            # "word" and would break w/e and the strip
            col = cc
            for part in text.split(' '):
                if part:
                    runs.append({'row': rr, 'col': col, 'symbols': part,
                                 'kind': 'ancient'})
                col += len(part) + 1
        doors.append((targets, _SS_BOLT0 + i))

    seals = []
    for i, (targets, bolt_col) in enumerate(doors):
        seals.append(_parse_seal({
            'scope': 'anyrow', 'mode': 'exact', 'anchor': 'exit_row',
            'match': [str(t) for t in targets],
            'opens': [[_SS_EXIT[0], bolt_col]],
        }, i))
    seals.append(_parse_seal({
        'anchor': 'exit_row',
        'requires': list(range(len(seals))),
        'opens': [list(_SS_EXIT)],
    }, len(seals)))

    level = _Level(
        name='The Sight Sanctum', seed=seed,
        rows=R, cols=C,
        cells=[''.join(_CELL_CODE[c] for c in row) for row in grid],
        spawn=_SS_SPAWN, exit=_SS_EXIT,
        char_runs=runs, seals=seals,
        entities=[{'kind': 'exit', 'at': [_SS_EXIT[0], _SS_EXIT[1]],
                   'edit_immune': True}],
        solution=_ss_answer(words))
    # no lintel: floating carved words over the spawn read as a locked door
    # — the credo lives in the intro hint instead

    dungeon = _fmt_build(level, par=_SS_PAR)
    _seal_banners(dungeon)
    dungeon.rooms[0]._ss_words = words
    return dungeon


# ── The Selection Halls (V <C-v>) ───────────────────────────────────────────────
# The gallery of corrupt panels: whole-row blights take V (the idiom),
# columnar seams and rectangles take <C-v> (the forcing). Six chambers on the
# exact-text chassis (spine, anchor-aligned light shaft, gate-row bolts,
# FINAL SEAL — the Sight Sanctum's proven bones):
#
#   • THE CASE TRIO (V, honestly price-forced — the g-prefix tax):
#     VU (2) beats gUU (3) on a scattered-case line that must read UPPER;
#     Vu (2) beats guu (3) on the mirror (and in visual, u LOWERCASES — it is
#     not undo, the trap-lesson); V~ (2) beats g~~ (3) on a full-flip
#     MIXED-case target (swapcased display — VU/Vu both write wrong case).
#     Linewise ops need no anchor column, so the chambers are single rows.
#   • BLOCK STRIPE (<C-v> 2j l d): three words share a 2-col blight seam at
#     the anchor column; one block delete heals all three (each row close-gaps
#     independently). Old route = 2x + dot per row, ~6 keys vs 5.
#   • BLOCK RECTANGLE (<C-v> 2j 3l ~): three PROPER NAMES (capital initial —
#     the guard the linewise Vu would destroy) with chars 2-5 wrong-cased; one
#     block toggle vs count-~ chains (~10) or per-row v-spans (dead: the top
#     row of a charwise multi-row span runs to line END and eats the tail).
#   • BLOCK INSERT (<C-v> 2j I {x} Esc — THE FINALE, new engine): three words
#     lost the SAME letter at the same column; the typed letter replays into
#     every selected row on Esc. Old route = i{x}Esc + jl. dot chain (~8 vs 5).
#
# FORCING BY PAR (standard 1.4 budget): the leanest old-only route (gUU/guu/
# g~~ + per-row dot chains) wins at 1★ a few keys inside the budget — driven.
# All six chambers anchor at the SHAFT column, so every hop is a plain {n}j
# (the nav-golf audit); the answer tape shows <C-v> as <C-v> — load-bearing,
# unlike Esc, so it must be visible (the tracker eats both chars at once).
_SH_ROWS, _SH_COLS = 32, 44   # the gallery WIDENS at the foot for the proverbs
_SH_SPINE  = 13                     # every row's first standable
_SH_BAY_W  = 14                     # bay floor cols 14..24; east wall 25
_SH_BAY_E  = 24
_SH_PLQ_COL = 2                     # full true readings, in the WEST wall band
_SH_TEXT0  = 15                     # multi-part rows start here
_SH_SHAFT  = 17                     # the anchor column + the light shaft
_SH_CASE_ROWS  = (3, 5, 7)          # VU · Vu · V~, one row each
_SH_STRIPE_ROWS = (9, 10, 11)       # block delete
_SH_RECT_ROWS   = (13, 14, 15)      # block case toggle
_SH_INS_ROWS    = (17, 18, 19)      # block insert
_SH_STAMP_ROWS  = (21, 22, 23)      # block overstrike (<C-v> r)
_SH_PANEL_ROWS  = (25, 26, 27, 28)  # the four panels (visual p, the swap)
_SH_PANEL_BAY_E = 42                # the panels' wider bay (proverbs, cols 14..42;
                                    # the trailing floor absorbs a long word's
                                    # open_gap so no swapped glyph hits the wall)
_SH_PROV_COL    = 15                # each proverb's head column
_SH_SHAFT_SEPS  = (4, 6, 8, 12, 16, 20, 24)  # separators the shaft pierces
_SH_THROAT = 29                     # spine-only (teleport audit)
_SH_GATE   = 30
_SH_BOLT0  = 14                     # bolts cols 14..21, one per chamber
_SH_EXIT   = (30, 22)               # the FINAL SEAL
_SH_PAR    = 74

# The proverb pool for the panel cycle (~20; four are drawn per seed). Each
# reads as a known saying whose STEM implies its final word, so a wrong last
# word is self-evidently wrong — no plaque needed (proverb-style, the
# sense-not-decree law). The four rows wear each other's last words rotated
# one frame down; the visual-paste swap (k$vbp) rotates them home. Kept short
# enough (≤ 22 chars) to sit in the widened foot bay; last words all distinct.
_SH_PROVERBS = (
    'no pain, no gain', 'easy come, easy go', 'live and let live',
    'haste makes waste', 'knowledge is power', 'time is money',
    'silence is golden', 'look before you leap', 'still waters run deep',
    'patience is a virtue', 'the truth will out', 'better late than never',
    'practice makes perfect', 'let sleeping dogs lie', 'beggars can\'t choose',
    'waste not, want not', 'seeing is believing', 'birds flock together',
    'slow and steady wins', 'hope springs eternal',
)


def _sh_draw_proverbs(rng):
    """Four proverbs with DISTINCT last words (so no rotation frame reads true
    by accident). Returns a list of (stem, last) — stem is everything up to
    the final space, last is the swap word."""
    for _ in range(40):
        pick = rng.sample(_SH_PROVERBS, 4)
        lasts = [p.rsplit(' ', 1)[1] for p in pick]
        if len(set(lasts)) == 4:
            return [tuple(p.rsplit(' ', 1)) for p in pick]
    raise ValueError('selection_halls: no distinct-last-word proverb draw')


def _sh_flip_mask(word: str) -> str:
    """The V~ chamber's MIXED-case target: odd indices upper — both cases
    always present (len ≥ 2), so neither VU nor Vu can write it."""
    return ''.join(ch.upper() if i % 2 else ch for i, ch in enumerate(word))


def _sh_scramble(word: str, rng, upper_target: bool) -> str:
    """A scattered-case display for a case chamber: at least one letter of
    each case, and never equal to the target (nor to the opposite sweep)."""
    for _ in range(40):
        out = ''.join(ch.upper() if rng.random() < 0.5 else ch for ch in word)
        if out != word and out != word.upper() and any(c.isupper() for c in out) \
                and any(c.islower() for c in out):
            return out
    return word[:1].upper() + word[1:] if not upper_target else word[:1] + word[1:].upper()


def _sh_draw_words(rng) -> dict:
    """Draw the gallery vocabulary (fixed slot lengths pin par and the rival
    chains): three len-6 case words; three len-5 stripe words; three len-8
    rectangle names; three len-7 insert words SHARING the letter at index 2
    (the one typed cure). All thirteen pairwise distinct."""
    _load_vocab_tables()

    def pool(length):
        return [w for w in _VOCAB_PLAIN_BY_LEN.get(length, ())
                if w.isalpha() and w == w.lower()]

    for _ in range(80):
        case3  = rng.sample(pool(6), 3)
        stripe = rng.sample(pool(5), 3)
        rect   = rng.sample(pool(8), 3)
        by_l: dict = {}
        for w in pool(7):
            by_l.setdefault(w[2], []).append(w)
        letters = [l for l, ws in by_l.items() if len(ws) >= 3]
        if not letters:
            continue
        letter = rng.choice(letters)
        ins = rng.sample(by_l[letter], 3)
        # the stamp: three len-6 words sharing the letter at index 2 — one
        # block overstrike heals all three
        by_l6: dict = {}
        for w in pool(6):
            by_l6.setdefault(w[2], []).append(w)
        letters6 = [l for l, ws in by_l6.items() if len(ws) >= 3]
        if not letters6:
            continue
        stamp_letter = rng.choice(letters6)
        stamp = rng.sample(by_l6[stamp_letter], 3)
        proverbs = _sh_draw_proverbs(rng)        # the 4-cycle panel proverbs
        picks = case3 + stripe + rect + ins + stamp
        if len(set(picks)) == len(picks):
            return {'case': case3, 'stripe': stripe, 'rect': rect,
                    'ins': ins, 'letter': letter,
                    'stamp': stamp, 'stamp_letter': stamp_letter,
                    'proverbs': proverbs}
    raise ValueError('selection_halls: no distinct draw after 80 tries')


def build_dungeon_selection_halls(seed: int) -> Dungeon:
    """The Selection Halls (slug `selection_halls`): V and <C-v>.

    Six chambers — the case trio (V's honest price win, the g-prefix tax),
    then the block stripe, rectangle, and insert (<C-v>'s ops with no
    normal-mode form at all). See the section header for the full forcing."""
    from vimny.engine.editor import _CELL_CODE
    from vimny.sharing.format import Level as _Level, _parse_seal, build as _fmt_build
    rng = random.Random(seed)
    words = _sh_draw_words(rng)
    up6, lo6, fl6 = words['case']
    letter = words['letter']

    # (bay rows, floor runs, door targets) — built per seed
    chambers = []
    t0, an = _SH_TEXT0, _SH_SHAFT
    # the case trio: word at the ANCHOR column (fnb == the shaft, so every
    # post-op cursor sits where the next {n}j hop needs it)
    chambers.append(((3,), ((3, an, _sh_scramble(up6, rng, True)),), (up6.upper(),)))
    chambers.append(((5,), ((5, an, _sh_scramble(lo6, rng, False)),), (lo6,)))
    fl_target = _sh_flip_mask(fl6)
    chambers.append(((7,), ((7, an, fl_target.swapcase()),), (fl_target,)))
    # the block stripe: 2-col '##' seam at the anchor across all three rows
    runs = []
    for r, w in zip(_SH_STRIPE_ROWS, words['stripe']):
        runs += [(r, t0, w[:2]), (r, an, '##'), (r, an + 2, w[2:])]
    chambers.append((_SH_STRIPE_ROWS, tuple(runs), tuple(words['stripe'])))
    # the block rectangle: proper names, chars 2-5 wrong-cased at cols 17-20
    runs, targets = [], []
    for r, w in zip(_SH_RECT_ROWS, words['rect']):
        name = w.capitalize()
        runs.append((r, t0, name[:2] + name[2:6].upper() + name[6:]))
        targets.append(name)
    chambers.append((_SH_RECT_ROWS, tuple(runs), tuple(targets)))
    # the block insert: every word lost its index-2 letter (the anchor col)
    runs = []
    for r, w in zip(_SH_INS_ROWS, words['ins']):
        runs.append((r, t0, w[:2] + w[3:]))
    chambers.append((_SH_INS_ROWS, tuple(runs), tuple(words['ins'])))
    # the restorer's stamp: one wrong cell ('#') at the anchor column of all
    # three rows — <C-v> 2j r{stamp_letter}
    runs = []
    for r, w in zip(_SH_STAMP_ROWS, words['stamp']):
        runs.append((r, t0, w[:2] + '#' + w[3:]))
    chambers.append((_SH_STAMP_ROWS, tuple(runs), tuple(words['stamp'])))
    # the four panels: each row is a PROVERB whose FINAL word is rotated one
    # frame down (row i wears row (i-1)'s ending), so every row reads as a
    # known saying with the wrong last word — self-evidently wrong, no plaque.
    # The visual-paste swap (…$bvep…) rotates the endings home.
    prov = words['proverbs']                             # [(stem, last), ...]
    runs, targets_p = [], []
    for i, r in enumerate(_SH_PANEL_ROWS):
        stem = prov[i][0]
        wrong = prov[(i - 1) % 4][1]                     # the previous ending
        col = _SH_PROV_COL
        for wd in f'{stem} {wrong}'.split(' '):          # one run per word
            runs.append((r, col, wd))
            col += len(wd) + 1
        targets_p.append(f'{stem} {prov[i][1]}')
    chambers.append((_SH_PANEL_ROWS, tuple(runs), tuple(targets_p)))

    R, C = _SH_ROWS, _SH_COLS
    grid = [[CellType.WALL] * C for _ in range(R)]
    for r in range(2, _SH_GATE + 1):                     # the spine
        grid[r][_SH_SPINE] = CellType.FLOOR
    for rows, _runs, _targets in chambers:               # the bays
        bay_e = _SH_PANEL_BAY_E if rows == _SH_PANEL_ROWS else _SH_BAY_E
        for r in rows:
            for c in range(_SH_BAY_W, bay_e + 1):
                grid[r][c] = CellType.FLOOR
    for r in _SH_SHAFT_SEPS:                             # the light shaft —
        grid[r][_SH_SHAFT] = CellType.FLOOR             # NOT the throat row

    runs: list = []
    doors = []
    for i, (rows, ch_runs, targets) in enumerate(chambers):
        for rr, cc, text in ch_runs:
            runs.append({'row': rr, 'col': cc, 'symbols': text,
                         'kind': 'ancient'})
        doors.append((targets, _SH_BOLT0 + i))
        if rows == _SH_PANEL_ROWS:
            continue                                     # proverb-style: no plaque
        for pr, ptext in zip(rows, targets):             # full true readings
            runs.append({'row': pr, 'col': _SH_PLQ_COL, 'symbols': ptext,
                         'kind': 'verdant'})

    seals = []
    for i, (targets, bolt_col) in enumerate(doors):
        seals.append(_parse_seal({
            'scope': 'anyrow', 'mode': 'exact', 'anchor': 'exit_row',
            'match': [str(t) for t in targets],
            'opens': [[_SH_EXIT[0], bolt_col]],
        }, i))
    seals.append(_parse_seal({
        'anchor': 'exit_row',
        'requires': list(range(len(seals))),
        'opens': [list(_SH_EXIT)],
    }, len(seals)))

    # endings are rotated one frame; the visual-paste swap (…$bvep…) rotates
    # them home for one key each, but the old-only route must RETYPE all four
    # correct endings (ce{word}) — and the longest proverb endings push that
    # route to ~115 keys. So the budget clears the worst old route (it wins,
    # at 1★) while par (74) still buys the 2nd star only with the swap (the
    # 1★ law; 1.4·par would make the old route unwinnable). <C-v> shows on the
    # tape as <C-v> (load-bearing, unlike Esc; the tracker eats both chars at once)
    sl = words['stamp_letter']
    level = _Level(
        name='The Selection Halls', seed=seed,
        rows=R, cols=C,
        cells=[''.join(_CELL_CODE[c] for c in row) for row in grid],
        spawn=(2, _SH_SPINE), exit=_SH_EXIT,
        char_runs=runs, seals=seals,
        entities=[{'kind': 'exit', 'at': [_SH_EXIT[0], _SH_EXIT[1]],
                   'edit_immune': True}],
        solution=(f'j VU 2j Vu 2j V~ 2j <C-v>2jld 4j <C-v>2j3l~ 4j '
                  f'<C-v>2jI{letter}<Esc> '
                  f'4j <C-v>2jr{sl} 4j $bvey 3j $bvep k$bvep k$bvep k$bvep G $'))

    dungeon = _fmt_build(level, par=_SH_PAR)
    _seal_banners(dungeon)
    dungeon.rooms[0]._sh_words = words
    return dungeon


# ── The Word Enclosure (iw aw) ──────────────────────────────────────────────────
# The first text objects: select by SHAPE, not by landing — and SENSE, NOT
# DECREE (the design law): every bay holds a famous
# proverb the player knows by heart. Intruder rows lay a seeded junk word
# INTO a true saying (the lesson deletes it); misquote rows swap one word
# for a wrong one (the lesson cures it). No west plaque band — the player's
# own memory of the proverb is the plaque.
#
# PAR INVARIANCE IS COLUMN-ANCHORED, NOT TEXT-ANCHORED: each slot fixes the
# corrupt word's START COLUMN and (for intruders) its length; the proverb's
# prefix right-aligns west of the slot (text0 varies per draw, and nothing
# in either tape counts words or finds letters west of the slot). The scar
# discrimination is unchanged (probe-verified): diw on the intruder leaves
# BOTH separators — `prefix  suffix`, the double-gap scar — while daw heals
# the seam: `prefix suffix`. The doors read the one-space difference.
#
#   • C1 the diw DRILL (3 rows, scar doors): junk lengths 5/4/3 at STAGGERED
#     starts 32/31/31, so the after-diw cursor always lands INSIDE the next
#     intruder — `diw j . j .` chains; `de` (rival) pays an h per stagger.
#   • C2 the ciw CURE (2 rows, misquotes, cures len 3 — different, no dot):
#     the hop lands slot+2, so `ce` pays hh; `caw` fuses and reads false.
#   • C3 the daw SEAM (2 rows, seam doors): arrival mid-intruder (hh dw = 4
#     vs daw 3); diw leaves the scar and reads false; `.` reprises.
#   • C4 the diW TOKEN · C5 the daW TOKEN (2+2 rows): the intruder is a
#     HYPHENATED junk token (`abcd-efgh` — one WORD, three w-words). The
#     CLASS lesson: diw kills a subword; the WORD family (dE/dW from the
#     token START) TIES ±1 — documented, the g~ precedent.
#
# THE DOT GAP is still the forcing story: a text object is ONE change, so
# it dot-chains down the anchor column; piecewise fixes re-position every
# row. Rivals driven WITH their own best dot usage win at 1★ (standard 1.4).
_WE_ROWS, _WE_COLS = 21, 57
_WE_SPINE  = 2                      # every row's first standable
_WE_BAY_W  = 3                      # bay floor cols 3..55; east wall 56
_WE_BAY_E  = 55
_WE_TEXT_MIN = 3                    # earliest col a proverb may start
_WE_C1_ROWS = (3, 4, 5)
_WE_C2_ROWS = (7, 8)
_WE_C3_ROWS = (10, 11)
_WE_C4_ROWS = (13, 14)              # diW — hyphenated intruders
_WE_C5_ROWS = (16, 17)              # daW
_WE_SHAFT_SEPS = ((6, 31), (9, 31), (12, 29), (15, 29))   # (row, col)
_WE_THROAT = 18
_WE_GATE   = 19
_WE_BOLT0  = 3                      # bolts cols 3..7, one per chamber
_WE_EXIT   = (19, 8)                # the FINAL SEAL
_WE_SPAWN  = (2, 32)                # over the first intruder: j drops onto it
# intruder slots: (row, junk len, start col) — the stagger keeps the chain
# landing inside the next intruder; misquote slots: (row, start col), the
# wrong word starts there (len >= 3 so the slot+2 landing stays inside).
_WE_C1_SLOTS = ((3, 5, 32), (4, 4, 31), (5, 3, 31))
_WE_C2_SLOTS = ((7, 29), (8, 29))
_WE_C3_SLOTS = ((10, 4, 29), (11, 4, 29))
_WE_C4_SLOTS = ((13, 9, 28), (14, 9, 28))
_WE_C5_SLOTS = ((16, 9, 28), (17, 9, 28))
_WE_CURE_LEN = 3
_WE_PAR = 47            # hand-tallied along the driven tape (buffer mutates)


def _we_draw_texts(rng) -> dict:
    """Draw proverbs + junk intruders for every slot.

    Geometric filters keep par seed-invariant: the corrupt word starts at
    the slot column, the prefix fits east of the spine, the tail west of
    the east wall. Proverbs pairwise distinct; junk words distinct, lower
    alpha, and absent from their own proverb."""
    from vimny.content import proverbs as _pv
    _load_vocab_tables()

    def junk_pool(length):
        return [w for w in _VOCAB_PLAIN_BY_LEN.get(length, ())
                if w.isalpha() and w == w.lower()]

    def fits_intruder(words, k, start, jlen):
        t0 = start - (_pv.prefix_len(words, k) + 1)
        last = start + jlen + 1 + len(' '.join(words[k:])) - 1
        return t0 >= _WE_TEXT_MIN and last <= _WE_BAY_E

    def fits_misquote(entry, start):
        words, idx, _cure = entry
        t0 = start - (_pv.prefix_len(words, idx) + 1)
        tail = ' '.join(words[idx + 1:])
        last = start + len(words[idx]) + (1 + len(tail) if tail else 0) - 1
        return len(words[idx]) >= 3 and t0 >= _WE_TEXT_MIN and last <= _WE_BAY_E

    intruder_slots = (_WE_C1_SLOTS + _WE_C3_SLOTS + _WE_C4_SLOTS + _WE_C5_SLOTS)
    cure_pool = _pv.misquotes_by_cure_len(_WE_CURE_LEN)
    for _ in range(200):
        sayings = rng.sample(_pv.PLAIN, len(intruder_slots))
        junks: list = []
        rows = []
        ok = True
        for (r, jlen, start), words in zip(intruder_slots, sayings):
            hyphen = jlen == 9
            if hyphen:
                a, b = rng.choice(junk_pool(4)), rng.choice(junk_pool(4))
                junk = f'{a}-{b}'
                parts = (a, b)
            else:
                junk = rng.choice(junk_pool(jlen))
                parts = (junk,)
            ks = [k for k in range(1, len(words))
                  if fits_intruder(words, k, start, jlen)]
            if not ks or any(p in words for p in parts):
                ok = False
                break
            junks += list(parts)
            rows.append((r, words, rng.choice(ks), junk, start))
        if not ok or len(set(junks)) != len(junks):
            continue
        mis = rng.sample(cure_pool, len(_WE_C2_SLOTS))
        if not all(fits_misquote(m, s) for m, (_r, s) in zip(mis, _WE_C2_SLOTS)):
            continue
        # a cure door's target is the TRUE proverb — it must not also be an
        # intruder row's saying, or mending that row opens this bolt free
        laid = {' '.join(w) for w in sayings}
        cured = {' '.join(w[:i] + (c,) + w[i + 1:]) for w, i, c in mis}
        if cured & laid:
            continue
        return {'intruders': rows, 'misquotes': mis}
    raise ValueError('word_enclosure: no fitting draw after 200 tries')


def build_dungeon_word_enclosure(seed: int) -> Dungeon:
    """The Word Enclosure (slug `word_enclosure`): iw and aw.

    Sense, not decree: every bay is a famous proverb, corrupted one word;
    the diw drill (dot-chained down the staggered intruders), the ciw cure
    (the misquote everyone can mend), and the daw seam (diw leaves the
    scar). See the section header for the forcing."""
    from vimny.content.proverbs import prefix_len, text_of
    from vimny.engine.editor import _CELL_CODE
    from vimny.sharing.format import Level as _Level, _parse_seal, build as _fmt_build
    rng = random.Random(seed)
    texts = _we_draw_texts(rng)

    R, C = _WE_ROWS, _WE_COLS
    grid = [[CellType.WALL] * C for _ in range(R)]
    for r in range(2, _WE_GATE + 1):                     # the spine
        grid[r][_WE_SPINE] = CellType.FLOOR
    all_rows = (_WE_C1_ROWS + _WE_C2_ROWS + _WE_C3_ROWS
                + _WE_C4_ROWS + _WE_C5_ROWS)
    for r in all_rows:                                   # the bays
        for c in range(_WE_BAY_W, _WE_BAY_E + 1):
            grid[r][c] = CellType.FLOOR
    for r, c in _WE_SHAFT_SEPS:                          # the light shafts —
        grid[r][c] = CellType.FLOOR                     # NOT the throat row
    grid[_WE_SPAWN[0]][_WE_SPAWN[1]] = CellType.FLOOR   # the drop-in

    runs: list = []

    def lay(r, col, words_seq):
        """One run per word, bare-floor gaps (the space-glyph law)."""
        for w in words_seq:
            runs.append({'row': r, 'col': col, 'symbols': w, 'kind': 'ancient'})
            col += len(w) + 1

    # intruder rows: prefix right-aligned west of the slot, junk AT it
    truths = {}                                          # row -> (prefix, suffix)
    for (r, words, k, junk, start) in texts['intruders']:
        t0 = start - (prefix_len(words, k) + 1)
        lay(r, t0, words[:k])
        lay(r, start, (junk,))
        lay(r, start + len(junk) + 1, words[k:])
        truths[r] = (text_of(words[:k]), text_of(words[k:]))
    # misquote rows: the wrong word sits AT the slot
    cures = {}
    for (r, start), (words, idx, cure) in zip(_WE_C2_SLOTS, texts['misquotes']):
        t0 = start - (prefix_len(words, idx) + 1)
        lay(r, t0, words[:idx])
        lay(r, start, (words[idx],))
        lay(r, start + len(words[idx]) + 1, words[idx + 1:])
        true = words[:idx] + (cure,) + words[idx + 1:]
        cures[r] = (cure, text_of(true))

    c1 = tuple(f'{truths[r][0]}  {truths[r][1]}' for r in _WE_C1_ROWS)  # scar
    c2 = tuple(cures[r][1] for r in _WE_C2_ROWS)
    c3 = tuple(f'{truths[r][0]} {truths[r][1]}' for r in _WE_C3_ROWS)   # seam
    c4 = tuple(f'{truths[r][0]}  {truths[r][1]}' for r in _WE_C4_ROWS)  # scar
    c5 = tuple(f'{truths[r][0]} {truths[r][1]}' for r in _WE_C5_ROWS)   # seam
    chambers = (c1, c2, c3, c4, c5)

    seals = []
    for i, targets in enumerate(chambers):
        seals.append(_parse_seal({
            'scope': 'anyrow', 'mode': 'exact', 'anchor': 'exit_row',
            'match': [str(t) for t in targets],
            'opens': [[_WE_EXIT[0], _WE_BOLT0 + i]],
        }, i))
    seals.append(_parse_seal({
        'anchor': 'exit_row',
        'requires': list(range(len(seals))),
        'opens': [list(_WE_EXIT)],
    }, len(seals)))

    ca, cb = (cures[r][0] for r in _WE_C2_ROWS)
    level = _Level(
        name='The Word Enclosure', seed=seed,
        rows=R, cols=C,
        cells=[''.join(_CELL_CODE[c] for c in row) for row in grid],
        spawn=_WE_SPAWN, exit=_WE_EXIT,
        char_runs=runs, seals=seals,
        entities=[{'kind': 'exit', 'at': [_WE_EXIT[0], _WE_EXIT[1]],
                   'edit_immune': True}],
        solution=(f'j diw j . j . 2j ciw {ca}<Esc> j ciw {cb}<Esc> '
                  f'2j daw j . 2j diW j . l 2j daW j . G $'))

    dungeon = _fmt_build(level, par=_WE_PAR)
    _seal_banners(dungeon)
    dungeon.rooms[0]._we_texts = texts
    return dungeon


# ── The Register I — The Unnamed Hold (the "" register) ───────────────────────
# The first bonus wing level (unlocked once the horse is adopted — the saddle
# holds the registers). It REFRESHES the unnamed register "" and teaches its
# VOLATILITY: "" is one slot, and ANY delete overwrites it. Three open bays run
# down a spine, ALL reachable from the start (no gate, no fog) so the layout
# TEMPTS the ruinous order:
#
#   spawn ─ QUARRY (row 3: the lone word "godliness") ─ DAW (row 5: "look before
#   you {junk} leap") ─ GAP (row 7: "cleanliness is next to ____") ─ exit
#
# You meet the word first, so the natural plan is yank it, walk down, and paste
# it into the gap you can already see. But the daw bay sits BETWEEN them: cut the
# intruder on the way and the delete overwrites "" with the junk, so your P lays
# the junk and the gap stays false. The lesson: a delete clobbers what you carry.
# The fix is to REORDER — yank + paste the gap FIRST, then daw; or daw first, then
# yank + paste; or simply re-yank after the clobber. Nothing is walled off, so the
# sting only ever costs a retry. The 9-letter word keeps yank + paste cheaper than
# retyping it. The exit seal wants both bays true (a seal-only tick).
_R1_ROWS, _R1_COLS = 11, 44
_R1_SPINE = 2
_R1_BAY_W, _R1_BAY_E = 3, 40
_R1_ROW_QUARRY = 3                    # the lone word — met first (tempts the yank)
_R1_ROW_DAW    = 5                    # the intruder saying — daw clobbers ""
_R1_ROW_GAP    = 7                    # the saying missing its last word (paste bay)
_R1_GATE       = 9                    # the exit/seal row
_R1_EXIT       = (9, 3)               # the FINAL SEAL, just east of the spine
_R1_SPAWN      = (2, 2)
_R1_TEXTCOL    = 3
_R1_QUARRY_WORD = 'godliness'         # yanked here, pasted into the gap (long → forces the yank)
_R1_DAW_PREFIX = ('look', 'before', 'you')
_R1_DAW_JUNK   = 'quill'
_R1_DAW_SUFFIX = ('leap',)
_R1_GAP_HEAD   = ('cleanliness', 'is', 'next', 'to')   # + the quarried 'godliness'
_R1_PAR = 16                          # the optimal driven tape below (register golf:
                                      # ye grabs " godliness" in one stroke, fo p lays
                                      # it, dw cuts the intruder). Test-pinned.
                                      # STANDARD ceil(16*1.4)=23 budget: tight on purpose —
                                      # a post-game mastery level rewards the register golf.
                                      # A verbose manual run / retype (~24) or a clobber
                                      # recovery (~32) overshoot and are barred; the register
                                      # tools are the way through, and the sting may strand
                                      # a fumbled run (recover with undo, or restart).


def build_dungeon_register_unnamed_hold(seed: int) -> Dungeon:
    """The Register I — The Unnamed Hold ("").  See the section header."""
    from vimny.content.proverbs import text_of
    from vimny.engine.editor import _CELL_CODE
    from vimny.sharing.format import Level as _Level, build as _fmt_build
    R, C = _R1_ROWS, _R1_COLS
    grid = [[CellType.WALL] * C for _ in range(R)]
    for r in range(2, _R1_GATE + 1):                     # the spine (fully open)
        grid[r][_R1_SPINE] = CellType.FLOOR
    for r in (_R1_ROW_QUARRY, _R1_ROW_DAW, _R1_ROW_GAP):  # the three bays
        for c in range(_R1_BAY_W, _R1_BAY_E + 1):
            grid[r][c] = CellType.FLOOR

    runs: list = []

    def lay(r, col, words_seq):
        for w in words_seq:
            runs.append({'row': r, 'col': col, 'symbols': w, 'kind': 'ancient'})
            col += len(w) + 1

    # Quarry — the lone word (met first).
    lay(_R1_ROW_QUARRY, _R1_TEXTCOL, (_R1_QUARRY_WORD,))
    # Daw bay — prefix, junk intruder, suffix (daw heals the seam; it clobbers "").
    lay(_R1_ROW_DAW, _R1_TEXTCOL, _R1_DAW_PREFIX)
    jcol = _R1_TEXTCOL + len(' '.join(_R1_DAW_PREFIX)) + 1
    lay(_R1_ROW_DAW, jcol, (_R1_DAW_JUNK,))
    lay(_R1_ROW_DAW, jcol + len(_R1_DAW_JUNK) + 1, _R1_DAW_SUFFIX)
    daw_target = text_of(_R1_DAW_PREFIX + _R1_DAW_SUFFIX)
    # Gap bay — head words, then a bare-floor trailing gap for the quarried word.
    col = _R1_TEXTCOL
    lay(_R1_ROW_GAP, col, _R1_GAP_HEAD)
    for w in _R1_GAP_HEAD:
        col += len(w) + 1
    gap_start = col
    gap_target = text_of(_R1_GAP_HEAD + (_R1_QUARRY_WORD,))

    level = _Level(
        name='The Unnamed Hold', seed=seed,
        rows=R, cols=C,
        cells=[''.join(_CELL_CODE[c] for c in row) for row in grid],
        spawn=_R1_SPAWN, exit=_R1_EXIT,
        char_runs=runs,
        entities=[{'kind': 'exit', 'at': [_R1_EXIT[0], _R1_EXIT[1]],
                   'edit_immune': True}],
        # The exit seal, as the format's own law: it parts while BOTH sayings
        # read true as whole rows somewhere on the floor — anyrow/exact, whose
        # multi-target match IS the conjunction. anchor='exit_row' rides the
        # row shifts.
        seals=[Seal(match=(daw_target, gap_target), scope='anyrow',
                    mode='exact', anchor='exit_row', opens=(_R1_EXIT,),
                    message='Both sayings read true — the seal parts.')],
        # The optimal tape (adversarially found): ye grabs the quarry WITH its leading
        # space in one stroke (from the spine col, e jumps to the word end), fo p lays
        # it just past "to" in the gap — all while "" is clean — THEN climb back (- k)
        # and cut the intruder with dw, and G l to the seal. Yank+paste first dodges
        # the clobber; doing it last (dw before the yank) also wins, one key dearer.
        solution='j ye 4j fo p - k fq dw G l')

    dungeon = _fmt_build(level, par=_R1_PAR)
    room = dungeon.rooms[0]
    room._r1_gap = (_R1_ROW_GAP, gap_start)              # read by the test/tape
    return dungeon


# ── The Register II — The Named Vault (the "a / "b registers) ─────────────────
# FORCED BY CAPACITY, NOT BY SURVIVAL.  INVARIANT: two sayings that share no
# word, and exactly one word wanted per bay, so no single clip is ever enough.
# That defeats both the `"_daw` route (protection, not capacity — the black
# hole spares "" and any protection tool would do) and the `J`-then-`y2e`
# route (one joined clip serving every bay, no named register needed).
#
#   spawn ─ QUARRY A (row 3: "godliness") ─ QUARRY B (row 4: "invention")
#         ─ bays rows 5..10, ALTERNATING saying A / saying B ─ seal (row 12)
#
#   an A bay reads  "cleanliness is next to dust"   → wants ... to godliness
#   a  B bay reads  "necessity is the mother of dust" → wants ... of invention
#
# Joining the quarry rows now yields a clip no bay wants, because no bay wants
# both words.  Every bay must first CUT its junk word — and that cut clobbers
# "", so a one-register route has to spend `"_` on all six bays AND walk the
# vault twice to fetch the other saying's word.  Two named registers hold both
# clips the whole way down and the vault is one pass.  ("_ is still genuinely
# useful here, which is the point: it is a reward for knowing it, not a hole.)
#
# The room is FULLY OPEN from the spawn: no gates, no fog.  The bays alternate,
# so the repeating unit is a PAIR of bays — record the pair, replay it twice.
#
# PAR IS THE MACRO ROUTE (34), not the plain named route (69) — par is the
# OPTIMUM, whatever the optimum turns out to be (docs/ARCHITECTURE.md).  Moving
# par onto the macro costs nothing here, because the macro CONTAINS the lesson:
# its recorded body pastes from both names, so it cannot be recorded without
# naming the words first.  Budget follows at the standard 1.4× (48).
_R2_ROWS, _R2_COLS = 14, 46
_R2_SPINE = 2
_R2_BAY_W, _R2_BAY_E = 3, 40
_R2_QUARRY_ROWS = (3, 4)              # one word each; no bay wants both
_R2_BAY_ROWS    = (5, 6, 7, 8, 9, 10)  # SIX bays, alternating saying A / B
_R2_GATE        = 12                  # the exit/seal row
_R2_EXIT        = (12, 3)
_R2_SPAWN       = (2, 2)
_R2_TEXTCOL     = 3
_R2_JUNK        = 'dust'              # the wrong word every bay ends on
_R2_SAYINGS     = (('cleanliness', 'is', 'next', 'to', 'godliness'),
                   ('necessity', 'is', 'the', 'mother', 'of', 'invention'))
_R2_QUARRY_WORDS = tuple(s[-1] for s in _R2_SAYINGS)
_R2_STUBS        = tuple(s[:-1] + (_R2_JUNK,) for s in _R2_SAYINGS)
_R2_PAR = 34                          # the MACRO optimal (driven); test-pinned


def _r2_saying_for(row: int) -> int:
    """Bays alternate, so the repeating unit is a PAIR."""
    return _R2_BAY_ROWS.index(row) % 2


def build_dungeon_register_named_vault(seed: int) -> Dungeon:
    """The Register II — The Named Vault ("a / "b).  See the section header."""
    from vimny.content.proverbs import text_of
    from vimny.engine.editor import _CELL_CODE
    from vimny.sharing.format import Level as _Level, build as _fmt_build
    R, C = _R2_ROWS, _R2_COLS
    grid = [[CellType.WALL] * C for _ in range(R)]
    for r in range(2, _R2_GATE + 1):                     # the spine
        grid[r][_R2_SPINE] = CellType.FLOOR
    for r in (*_R2_QUARRY_ROWS, *_R2_BAY_ROWS):          # every bay, fully open
        for c in range(_R2_BAY_W, _R2_BAY_E + 1):
            grid[r][c] = CellType.FLOOR

    runs: list = []

    def lay(r, col, words_seq):
        for w in words_seq:
            runs.append({'row': r, 'col': col, 'symbols': w, 'kind': 'ancient'})
            col += len(w) + 1

    for qrow, word in zip(_R2_QUARRY_ROWS, _R2_QUARRY_WORDS):
        lay(qrow, _R2_TEXTCOL, (word,))
    for brow in _R2_BAY_ROWS:
        lay(brow, _R2_TEXTCOL, _R2_STUBS[_r2_saying_for(brow)])

    targets = {r: text_of(_R2_SAYINGS[_r2_saying_for(r)])
               for r in _R2_BAY_ROWS}

    # PAR IS THE MACRO ROUTE, because the macro route is the optimum and par may
    # never be a lie: quarry both words, then record ONE PAIR of bays (the bays
    # alternate, so the pair is the repeating unit) starting at the earliest
    # opportunity, and `2@q` the rest.  Every bay is the same swap — `$b` onto
    # the junk word, `diw` to cut it out, `"XP` to set the right word into the
    # hole it left — so the macro body still carries the register lesson: it
    # pastes from BOTH names, and it is recorded into `q` precisely because
    # recording into `a` would destroy the word parked there.
    _bay = lambda r: '$ b diw "%sP' % 'ab'[_r2_saying_for(r)]
    # (`ye` leaves the cursor at the START of the yank, so the second quarry row
    #  needs no `w` — dropping it keeps the tape honest against the audit.)
    solution = ' '.join(['j w "aye j "bye qq',
                         'j ' + _bay(_R2_BAY_ROWS[0]),
                         'j ' + _bay(_R2_BAY_ROWS[1]),
                         'q 2@q G l'])

    level = _Level(
        name='The Named Vault', seed=seed,
        rows=R, cols=C,
        cells=[''.join(_CELL_CODE[c] for c in row) for row in grid],
        spawn=_R2_SPAWN, exit=_R2_EXIT,
        char_runs=runs,
        entities=[{'kind': 'exit', 'at': [_R2_EXIT[0], _R2_EXIT[1]],
                   'edit_immune': True}],
        # The six bays as pure predicate Seals (empty `opens` — they only
        # READ), each true while its whole row reads its saying; the exit is
        # the final seal requiring every one. The tick's conjunction, said
        # as data.
        seals=([Seal(region=(r, 0, r, C - 1), match=(targets[r],),
                     mode='exact', scope='region')
                for r in _R2_BAY_ROWS]
               + [Seal(opens=(_R2_EXIT,), anchor='exit_row',
                       requires=tuple(range(len(_R2_BAY_ROWS))),
                       message='Every saying reads true — the seal parts.')]),
        solution=solution)

    dungeon = _fmt_build(level, par=_R2_PAR)
    return dungeon


# ── The Bracket Enclosure (i( a() ────────────────────────────────────────────────
# GEM SETTINGS, BY SENSE (the design law): every bay is a
# famous proverb whose parenthesized aside has gone wrong — a junk stone set
# into the saying, or the saying's KEY word set as a gem but miscut. No west
# plaques: the player knows the true reading by heart. Par invariance is
# COLUMN-ANCHORED (the Word Enclosure law): the '(' sits at a fixed slot
# column, the proverb's prefix right-aligns west of it. Three door types,
# discriminated by what remains (probe-verified):
#   • C1 the PRIED SETTING (di(, 3 rows): `prefix (junk) suffix` →
#     `prefix () suffix` — the empty husk stays and the door reads it.
#     Junk of DIFFERENT lengths at staggered slots keeps the `di( j . j .`
#     chain landing inside the next stone; dt)/dT( pay repositioning;
#     dw/daw heal wrongly. Row 3's junk is TWO WORDS — diw kills half and
#     reads false (the object-vs-object lesson).
#   • C2 the MISCUT GEM (ci( + cure, 2 rows): the saying's famous word sits
#     bracketed but WRONG — `catches the (snake)` — and the cure is the
#     word everyone knows: → `prefix (worm) suffix`. The hop lands
#     mid-content so ct) leaves the head; ca(+cure tears and fuses.
#   • C3 the TORN FITTING (da(, 2 rows): → `prefix  suffix` — the
#     double-gap scar (a( takes no whitespace); di( leaves the husk and
#     reads false; da( honestly forced from anywhere inside.
# Walk-in chamber first (the j % entry is length-independent: % seeks the
# first '(' wherever the prefix ends); rivals driven WITH their best dot.
_BE_ROWS, _BE_COLS = 15, 58
_BE_SPINE  = 2                      # every row's first standable
_BE_BAY_W  = 3                      # bay floor cols 3..56; east wall 57
_BE_BAY_E  = 56
_BE_TEXT_MIN = 3                    # earliest col a proverb may start
_BE_C1_ROWS = (3, 4, 5)
_BE_C2_ROWS = (7, 8)
_BE_C3_ROWS = (10, 11)
_BE_SHAFT_SEPS = ((6, 30), (9, 31))  # (row, col) — the hop landing columns
_BE_THROAT = 12
_BE_GATE   = 13
_BE_BOLT0  = 3                      # bolts cols 3..5, one per chamber
_BE_EXIT   = (13, 6)                # the FINAL SEAL
# intruder slots: (row, junk len, fitting '(' col) — junk starts at '('+1;
# staggered so the di( chain and every hop land INSIDE the next stone
# (row 3's junk is 'ab cd' — 3+1+3 = 7, two words). Misquote slots:
# (row, fitting col); wrong-word len >= 3 keeps the post-cure landing in.
_BE_C1_SLOTS = ((3, 7, 30), (4, 5, 29), (5, 4, 29))
_BE_C2_SLOTS = ((7, 28), (8, 28))
_BE_C3_SLOTS = ((10, 4, 29), (11, 4, 28))
_BE_CURE_LEN = 3
_BE_PAR = 33            # hand-tallied along the driven tape (j % entry)


def _be_draw_texts(rng) -> dict:
    """Draw proverbs + junk stones for every slot (the Word Enclosure
    draw discipline: geometric fits keep par seed-invariant)."""
    from vimny.content import proverbs as _pv
    _load_vocab_tables()

    def junk_pool(length):
        return [w for w in _VOCAB_PLAIN_BY_LEN.get(length, ())
                if w.isalpha() and w == w.lower()]

    def fits_intruder(words, k, fit, jlen):
        t0 = fit - (_pv.prefix_len(words, k) + 1)
        last = fit + jlen + 3 + len(' '.join(words[k:])) - 1
        return t0 >= _BE_TEXT_MIN and last <= _BE_BAY_E

    def fits_misquote(entry, fit):
        words, idx, _cure = entry
        t0 = fit - (_pv.prefix_len(words, idx) + 1)
        tail = ' '.join(words[idx + 1:])
        last = fit + len(words[idx]) + 1 + (1 + len(tail) if tail else 0)
        return len(words[idx]) >= 3 and t0 >= _BE_TEXT_MIN and last <= _BE_BAY_E

    intruder_slots = _BE_C1_SLOTS + _BE_C3_SLOTS
    cure_pool = _pv.misquotes_by_cure_len(_BE_CURE_LEN)
    for _ in range(200):
        sayings = rng.sample(_pv.PLAIN, len(intruder_slots))
        junks: list = []
        rows = []
        ok = True
        for i, ((r, jlen, fit), words) in enumerate(zip(intruder_slots, sayings)):
            if i == 0:                                   # two words in the setting
                a, b = rng.choice(junk_pool(3)), rng.choice(junk_pool(3))
                junk, parts = f'{a} {b}', (a, b)
            else:
                junk = rng.choice(junk_pool(jlen))
                parts = (junk,)
            ks = [k for k in range(1, len(words))
                  if fits_intruder(words, k, fit, jlen)]
            if not ks or any(p in words for p in parts):
                ok = False
                break
            junks += list(parts)
            rows.append((r, words, rng.choice(ks), junk, fit))
        if not ok or len(set(junks)) != len(junks):
            continue
        mis = rng.sample(cure_pool, len(_BE_C2_SLOTS))
        if not all(fits_misquote(m, f) for m, (_r, f) in zip(mis, _BE_C2_SLOTS)):
            continue
        return {'intruders': rows, 'misquotes': mis}
    raise ValueError('bracket_enclosure: no fitting draw after 200 tries')


def build_dungeon_bracket_enclosure(seed: int) -> Dungeon:
    """The Bracket Enclosure (slug `bracket_enclosure`): i( and a(.

    Sense, not decree: proverb bays. di( pries the junk stone and keeps the
    husk, ci( recuts the miscut gem to the word everyone knows, da( tears
    the whole fitting out. See the section header for the forcing."""
    from vimny.content.proverbs import prefix_len, text_of
    from vimny.engine.editor import _CELL_CODE
    from vimny.sharing.format import Level as _Level, _parse_seal, build as _fmt_build

    rng = random.Random(seed)
    texts = _be_draw_texts(rng)

    R, C = _BE_ROWS, _BE_COLS
    grid = [[CellType.WALL] * C for _ in range(R)]
    for r in range(2, _BE_GATE + 1):                     # the spine
        grid[r][_BE_SPINE] = CellType.FLOOR
    for r in _BE_C1_ROWS + _BE_C2_ROWS + _BE_C3_ROWS:   # the bays
        for c in range(_BE_BAY_W, _BE_BAY_E + 1):
            grid[r][c] = CellType.FLOOR
    for r, c in _BE_SHAFT_SEPS:                          # the light shafts —
        grid[r][c] = CellType.FLOOR                     # NOT the throat row

    runs: list = []

    def lay(r, col, words_seq):
        for w in words_seq:
            runs.append({'row': r, 'col': col, 'symbols': w, 'kind': 'ancient'})
            col += len(w) + 1

    truths = {}                                          # row -> (prefix, suffix)
    for (r, words, k, junk, fit) in texts['intruders']:
        t0 = fit - (prefix_len(words, k) + 1)
        lay(r, t0, words[:k])
        runs.append({'row': r, 'col': fit, 'symbols': f'({junk})',
                     'kind': 'ancient'})
        lay(r, fit + len(junk) + 3, words[k:])
        truths[r] = (text_of(words[:k]), text_of(words[k:]))
    cures = {}
    for (r, fit), (words, idx, cure) in zip(_BE_C2_SLOTS, texts['misquotes']):
        t0 = fit - (prefix_len(words, idx) + 1)
        lay(r, t0, words[:idx])
        runs.append({'row': r, 'col': fit, 'symbols': f'({words[idx]})',
                     'kind': 'ancient'})
        tail = words[idx + 1:]
        if tail:
            lay(r, fit + len(words[idx]) + 3, tail)
        true = (f"{text_of(words[:idx])} ({cure})"
                + (f" {text_of(tail)}" if tail else ''))
        cures[r] = (cure, true)

    c1 = tuple(f'{truths[r][0]} () {truths[r][1]}' for r in _BE_C1_ROWS)
    c2 = tuple(cures[r][1] for r in _BE_C2_ROWS)
    c3 = tuple(f'{truths[r][0]}  {truths[r][1]}' for r in _BE_C3_ROWS)
    chambers = (c1, c2, c3)

    # The chamber gate, said in FILE vocabulary and validated like an author's:
    # three anyrow exact bolts on the gate row, then the final seal requiring
    # them all — the same shapes `gate_row_seals` builds.
    seals = []
    for i, targets in enumerate(chambers):
        seals.append(_parse_seal({
            'scope': 'anyrow', 'mode': 'exact', 'anchor': 'exit_row',
            'match': [str(t) for t in targets],
            'opens': [[_BE_EXIT[0], _BE_BOLT0 + i]],
        }, i))
    seals.append(_parse_seal({
        'anchor': 'exit_row',
        'requires': list(range(len(seals))),
        'opens': [list(_BE_EXIT)],
    }, len(seals)))

    ca, cb = (cures[r][0] for r in _BE_C2_ROWS)
    level = _Level(
        name='The Bracket Enclosure', seed=seed,
        rows=R, cols=C,
        cells=[''.join(_CELL_CODE[c] for c in row) for row in grid],
        spawn=(2, _BE_SPINE), exit=_BE_EXIT,
        char_runs=runs, seals=seals,
        entities=[{'kind': 'exit', 'at': [_BE_EXIT[0], _BE_EXIT[1]],
                   'edit_immune': True}],
        # nav golf (known shortcut): % from the spine scans to the first
        # '(' and jumps to its MATCH — j % lands ON the ')' and di( resolves
        # from the delimiter. Two keys under the w-walk, whatever the prefix.
        solution=(f'j % di( j . j . 2j ci( {ca}<Esc> j ci( {cb}<Esc> '
                  f'2j da( j . G $'))

    dungeon = _fmt_build(level, par=_BE_PAR)

    room = dungeon.rooms[0]
    _seal_banners(dungeon)
    room._be_texts = texts
    return dungeon


# ── The Brace & Square Enclosure (i[ a[ i{ a{) ──────────────────────────────
#
# Level 33 taught inside-vs-around on one delimiter family; with two more the
# lesson becomes CHOOSING the object — reading the delimiter under your hand —
# and, in the nest chamber, resolving AMBIGUITY: from one cursor position
# inside `[{jjj} bbb]`, di{ and di[ carve different spans. SENSE, NOT DECREE
# (the design law): every bay is a famous proverb wearing
# a bracketed aside gone wrong — junk stones in square or brace settings, or
# the saying's key word miscut in its fitting. No west plaques except the
# nest twins' ember/pedestal pair (which distinguish the twin DOORS, not the
# text). Par invariance is COLUMN-ANCHORED (the Word Enclosure law). Five
# chambers on the exact-text chassis (`_chamber_gate` seals):
#   C1 (rows 3-4)   di[ husk ×2, the second by dot   → 'pre [] suf'
#   C2 (rows 6-7)   ci[ cures — the miscut famous word, retyped by heart
#   C3 (rows 9-10)  di{ + dot (the family switch — a blind '.' straight off
#                   C2 replays ci[+text and finds no [ here: a costed no-op)
#   C4 (rows 12-13) THE NEST, twin mirrored rows: `pre [{jjj} bbb] suf`.
#                   Row 12's door wants only the braces emptied (di{); row
#                   13's wants the square gutted whole (di[) — same landing
#                   column, two different correct objects. Twin bolts at the
#                   CENTER pair of the gate run, ember/pedestal plaques.
#   C5 (row 15)     da{ scar                          → 'pre  suf'
#
# Forcing audit (why par 45 needs the objects):
#   • every hop lands MID-junk (never at junk start), so `{n}x` pays a
#     positioning key the object doesn't;
#   • d% kills the delimiters, so it can never match a husk target; on the
#     scar row it needs an h first (h d% = 3, a tie with da{, never a win);
#   • dT[/dt] need the junk edge, which the landings don't give;
#   • row 3's stone is two words (no single-count x chain).
_BSQ_ROWS, _BSQ_COLS = 19, 60
_BSQ_SPINE   = 2                     # every row's first standable
_BSQ_BAY_W   = 3                     # bay floor cols 3..57; east wall 58
_BSQ_BAY_E   = 57
_BSQ_TEXT_MIN = 3                    # earliest col a proverb may start
_BSQ_NEST_W   = 14                   # the nest bays start east of their tags
_BSQ_PLQ_COL  = 3                    # the twins' ember/pedestal tags, in stone
_BSQ_C1_ROWS = (3, 4)
_BSQ_C2_ROWS = (6, 7)
_BSQ_C3_ROWS = (9, 10)
_BSQ_C4_ROWS = (12, 13)
_BSQ_C5_ROWS = (15,)
_BSQ_SHAFT_SEPS = ((5, 30), (8, 31), (11, 31), (14, 29))
_BSQ_THROAT  = 16
_BSQ_GATE    = 17
_BSQ_BOLT0   = 3                     # bolts 3..8: C1 C2 C4a C4b C3 C5
_BSQ_BOLTS   = {'c1': 3, 'c2': 4, 'c4a': 5, 'c4b': 6, 'c3': 7, 'c5': 8}
_BSQ_EXIT    = (17, 9)               # the FINAL SEAL, east of every bolt
# intruder slots: (row, junk len, open col, delim) — junk starts open+1;
# row 3's junk is 'aaa bbb' (len 7, two words). Nest slots: (row, open col),
# junk len 3 + flank len 3. Misquote slots: (row, open col), cures len 3.
_BSQ_C1_SLOTS = ((3, 7, 30, '['), (4, 5, 29, '['))
_BSQ_C2_SLOTS = ((6, 28), (7, 28))
_BSQ_C3_SLOTS = ((9, 4, 29, '{'), (10, 5, 30, '{'))
_BSQ_C4_SLOTS = ((12, 28), (13, 28))
_BSQ_C5_SLOTS = ((15, 5, 28, '{'),)
_BSQ_CURE_LEN = 3
_BSQ_PAR = 45           # hand-tallied along the driven tape (j % entry)


def _bsq_draw_texts(rng) -> dict:
    """Draw proverbs + junk for every slot (the Word Enclosure draw
    discipline: geometric fits keep par seed-invariant)."""
    from vimny.content import proverbs as _pv
    _load_vocab_tables()

    def junk_pool(length):
        return [w for w in _VOCAB_PLAIN_BY_LEN.get(length, ())
                if w.isalpha() and w == w.lower()]

    def fits(words, k, open_col, fitlen):
        t0 = open_col - (_pv.prefix_len(words, k) + 1)
        last = open_col + fitlen + 1 + len(' '.join(words[k:])) - 1
        return t0 >= _BSQ_TEXT_MIN and last <= _BSQ_BAY_E

    def fits_misquote(entry, open_col):
        words, idx, _cure = entry
        t0 = open_col - (_pv.prefix_len(words, idx) + 1)
        tail = ' '.join(words[idx + 1:])
        last = open_col + len(words[idx]) + 1 + (1 + len(tail) if tail else 0)
        return (len(words[idx]) >= 3 and t0 >= _BSQ_TEXT_MIN
                and last <= _BSQ_BAY_E)

    plain_slots = _BSQ_C1_SLOTS + _BSQ_C3_SLOTS + _BSQ_C5_SLOTS
    cure_pool = _pv.misquotes_by_cure_len(_BSQ_CURE_LEN)
    n_need = len(plain_slots) + len(_BSQ_C4_SLOTS)
    for _ in range(200):
        sayings = rng.sample(_pv.PLAIN, n_need)
        junks: list = []
        rows, nests = [], []
        ok = True
        for i, ((r, jlen, oc, delim), words) in enumerate(
                zip(plain_slots, sayings[:len(plain_slots)])):
            if i == 0:                                   # two words in the setting
                a, b = rng.choice(junk_pool(3)), rng.choice(junk_pool(3))
                junk, parts = f'{a} {b}', (a, b)
            else:
                junk = rng.choice(junk_pool(jlen))
                parts = (junk,)
            ks = [k for k in range(1, len(words))
                  if fits(words, k, oc, jlen + 2)]
            if not ks or any(p in words for p in parts):
                ok = False
                break
            junks += list(parts)
            rows.append((r, words, rng.choice(ks), junk, oc, delim))
        if ok:
            for (r, oc), words in zip(_BSQ_C4_SLOTS,
                                      sayings[len(plain_slots):]):
                junk, flank = rng.choice(junk_pool(3)), rng.choice(junk_pool(3))
                # nest fitting '[{jjj} bbb]' is len 11; the nest bays start
                # at _BSQ_NEST_W (their west stone carries the twin tags)
                ks = [k for k in range(1, len(words))
                      if fits(words, k, oc, 11)
                      and oc - (_pv.prefix_len(words, k) + 1) >= _BSQ_NEST_W]
                if not ks or junk in words or flank in words or junk == flank:
                    ok = False
                    break
                junks += [junk, flank]
                nests.append((r, words, rng.choice(ks), junk, flank, oc))
        if not ok or len(set(junks)) != len(junks):
            continue
        mis = rng.sample(cure_pool, len(_BSQ_C2_SLOTS))
        if not all(fits_misquote(m, oc) for m, (_r, oc) in zip(mis, _BSQ_C2_SLOTS)):
            continue
        return {'intruders': rows, 'nests': nests, 'misquotes': mis}
    raise ValueError('brace_square_enclosure: no fitting draw after 200 tries')


def build_dungeon_brace_square_enclosure(seed: int) -> Dungeon:
    """The Brace & Square Enclosure (slug `brace_square_enclosure`):
    i[ a[ i{ a{ — choose the object; in the nest, choose the DEPTH.
    Sense, not decree: proverb bays wearing bracketed asides."""
    from vimny.content.proverbs import prefix_len, text_of
    from vimny.engine.editor import _CELL_CODE
    from vimny.sharing.format import Level as _Level, _parse_seal, build as _fmt_build
    rng = random.Random(seed)
    texts = _bsq_draw_texts(rng)

    R, C = _BSQ_ROWS, _BSQ_COLS
    grid = [[CellType.WALL] * C for _ in range(R)]
    for r in range(2, _BSQ_GATE + 1):                    # the spine
        grid[r][_BSQ_SPINE] = CellType.FLOOR
    lesson_rows = (_BSQ_C1_ROWS + _BSQ_C2_ROWS + _BSQ_C3_ROWS
                   + _BSQ_C4_ROWS + _BSQ_C5_ROWS)
    for r in lesson_rows:                                # the bays (the nest
        w = _BSQ_NEST_W if r in _BSQ_C4_ROWS else _BSQ_BAY_W   # rows keep west
        for c in range(w, _BSQ_BAY_E + 1):               # stone for their tags)
            grid[r][c] = CellType.FLOOR
    for r, c in _BSQ_SHAFT_SEPS:                         # the light shafts —
        grid[r][c] = CellType.FLOOR                     # NOT the throat row

    runs: list = []

    def lay(r, col, words_seq, colour='ancient'):
        for w in words_seq:
            runs.append({'row': r, 'col': col, 'symbols': w, 'kind': colour})
            col += len(w) + 1

    truths = {}                                          # row -> (prefix, suffix)
    for (r, words, k, junk, oc, delim) in texts['intruders']:
        close = ']' if delim == '[' else '}'
        t0 = oc - (prefix_len(words, k) + 1)
        lay(r, t0, words[:k])
        runs.append({'row': r, 'col': oc, 'symbols': f'{delim}{junk}{close}',
                     'kind': 'ancient'})
        lay(r, oc + len(junk) + 3, words[k:])
        truths[r] = (text_of(words[:k]), text_of(words[k:]))
    for (r, words, k, junk, flank, oc) in texts['nests']:
        t0 = oc - (prefix_len(words, k) + 1)
        lay(r, t0, words[:k])
        runs.append({'row': r, 'col': oc, 'symbols': f'[{{{junk}}} {flank}]',
                     'kind': 'ancient'})
        lay(r, oc + 12, words[k:])
        truths[r] = (text_of(words[:k]), text_of(words[k:]))
    cures = {}
    for (r, oc), (words, idx, cure) in zip(_BSQ_C2_SLOTS, texts['misquotes']):
        t0 = oc - (prefix_len(words, idx) + 1)
        lay(r, t0, words[:idx])
        runs.append({'row': r, 'col': oc, 'symbols': f'[{words[idx]}]',
                     'kind': 'ancient'})
        tail = words[idx + 1:]
        if tail:
            lay(r, oc + len(words[idx]) + 3, tail)
        true = (f"{text_of(words[:idx])} [{cure}]"
                + (f" {text_of(tail)}" if tail else ''))
        cures[r] = (cure, true)

    nest_flank = {r: f for r, _w, _k, _j, f, _o in texts['nests']}
    c1  = tuple(f'{truths[r][0]} [] {truths[r][1]}' for r in _BSQ_C1_ROWS)
    c2  = tuple(cures[r][1] for r in _BSQ_C2_ROWS)
    c3  = tuple(f'{truths[r][0]} {{}} {truths[r][1]}' for r in _BSQ_C3_ROWS)
    c4a = (f'{truths[12][0]} [{{}} {nest_flank[12]}] {truths[12][1]}',)
    c4b = (f'{truths[13][0]} [] {truths[13][1]}',)
    c5  = tuple(f'{truths[r][0]}  {truths[r][1]}' for r in _BSQ_C5_ROWS)
    doors = ((c1, _BSQ_BOLTS['c1']), (c2, _BSQ_BOLTS['c2']),
             (c3, _BSQ_BOLTS['c3']), (c4a, _BSQ_BOLTS['c4a']),
             (c4b, _BSQ_BOLTS['c4b']), (c5, _BSQ_BOLTS['c5']))
    # the twin tags, carved into the nest rows' west stone: ember 'braces' /
    # pedestal 'square' — they name the twin DOORS' objects (the one decree
    # the nest keeps: which depth each door judges; the sayings themselves
    # need no plaque). Glyphs in stone never join the floor text.
    lay(12, _BSQ_PLQ_COL, ('braces',), 'ember')
    lay(13, _BSQ_PLQ_COL, ('square',), 'pedestal')

    # The chamber gate in FILE vocabulary — six bolts then the final seal,
    # validated exactly as an author's file would be.
    seals = []
    for i, (targets, bolt_col) in enumerate(doors):
        seals.append(_parse_seal({
            'scope': 'anyrow', 'mode': 'exact', 'anchor': 'exit_row',
            'match': [str(t) for t in targets],
            'opens': [[_BSQ_EXIT[0], bolt_col]],
        }, i))
    seals.append(_parse_seal({
        'anchor': 'exit_row',
        'requires': list(range(len(seals))),
        'opens': [list(_BSQ_EXIT)],
    }, len(seals)))

    ca, cb = (cures[r][0] for r in _BSQ_C2_ROWS)
    level = _Level(
        name='The Brace & Square Enclosure', seed=seed,
        rows=R, cols=C,
        cells=[''.join(_CELL_CODE[c] for c in row) for row in grid],
        spawn=(2, _BSQ_SPINE), exit=_BSQ_EXIT,
        char_runs=runs, seals=seals,
        entities=[{'kind': 'exit', 'at': [_BSQ_EXIT[0], _BSQ_EXIT[1]],
                   'edit_immune': True}],
        solution=(f'j % di[ j . 2j ci[ {ca}<Esc> j ci[ {cb}<Esc> '
                  f'2j di{{ j . 2j di{{ j di[ 2j da{{ G $'))

    dungeon = _fmt_build(level, par=_BSQ_PAR)
    _seal_banners(dungeon)
    dungeon.rooms[0]._bsq_texts = texts
    return dungeon


# ── The Quote Enclosure (i" a" i' a') ───────────────────────────────────────
#
# Quotes have no matching pair — Vim pairs them by scanning the LINE — and
# that buys the level its headline lesson: the quote objects work from
# ANYWHERE WEST of the pair (the resolver seeks forward), so every strike
# here is thrown from the spine, no navigation into the setting at all.
# Five chambers on the exact-text chassis (`_chamber_gate` seals):
#   C1 (rows 3-4)   di" husk ×2, the second by dot     → 'w1 "" w2'
#   C2 (rows 6-7)   ci" cures (typed, single tokens)   → 'w1 "cure" w2'
#   C3 (rows 9-10)  di' — the quote-mark switch (a blind '.' off C2 replays
#                   ci"+text and finds no double quote here: a costed no-op)
#   C4 (rows 12-13) THE WHITESPACE QUIRK: da" / da' span the quotes PLUS the
#                   trailing space (Vim-true), so the fitting tears out to a
#                   SINGLE gap 'w1 w2' — where da( left the double-gap scar.
#   C5 (row 15)     THE SEEK'S LIMIT: 'w1 "" "jjj" w2' — the forward seek
#                   takes the FIRST pair, which is already empty (di" from
#                   the landing is a no-op), so the player must aim: one w
#                   hops the empty pair onto the second's opening mark
#                   (known golf; 2f" pays a key more).
#
# Forcing audit (why par 45 needs the objects): the objects fire from the
# spine while every old tool must first walk in (f"/w cost 1-3 keys before a
# {n}x or dt" even starts); % does not speak quotes; D/cc raze the kept
# words. C5's w l 3x route ties the object route (4 = 4) — a tie, never a
# win.
_QE_ROWS, _QE_COLS = 19, 58
_QE_SPINE   = 2                      # every row's first standable
_QE_BAY_W   = 3                      # bay floor cols 3..55; east wall 56
_QE_BAY_E   = 55
_QE_TEXT_MIN = 3                     # earliest col a proverb may start
_QE_ANCHOR  = 29                     # the opening quote's column, every row
_QE_C1_ROWS = (3, 4)
_QE_C2_ROWS = (6, 7)
_QE_C3_ROWS = (9, 10)
_QE_C4_ROWS = (12, 13)
_QE_C5_ROWS = (15,)
_QE_SHAFT_SEPS = ((5, 30), (8, 32), (11, 30), (14, 29))
_QE_THROAT  = 16
_QE_GATE    = 17
_QE_BOLTS   = {'c1': 3, 'c2': 4, 'c3': 5, 'c4': 6, 'c5': 7}
_QE_EXIT    = (17, 8)                # the FINAL SEAL, east of every bolt
# (row, junk len, quote char) for the intruder rows — the opening quote
# sits at _QE_ANCHOR on EVERY row (the proverb's prefix right-aligns west
# of it), so the chained landings stay inside or west of each next pair,
# which is all the forward seek needs. C2 rows are misquotes (the famous
# word quoted but wrong; cures len 3).
_QE_SHAPE = ((3, 3, '"'), (4, 4, '"'),
             (9, 4, "'"), (10, 3, "'"), (12, 5, '"'), (13, 4, "'"),
             (15, 3, '"'))
_QE_CURE_LEN = 3
_QE_PAR = 45            # hand-tallied along the driven tape (spine strikes)


def _qe_draw_texts(rng) -> dict:
    """Draw proverbs + quoted junk for every slot (the Word Enclosure draw
    discipline: geometric fits keep par seed-invariant)."""
    from vimny.content import proverbs as _pv
    _load_vocab_tables()

    def junk_pool(length):
        return [w for w in _VOCAB_PLAIN_BY_LEN.get(length, ())
                if w.isalpha() and w == w.lower()]

    def fits(words, k, fitlen):
        t0 = _QE_ANCHOR - (_pv.prefix_len(words, k) + 1)
        last = _QE_ANCHOR + fitlen + 1 + len(' '.join(words[k:])) - 1
        return t0 >= _QE_TEXT_MIN and last <= _QE_BAY_E

    def fits_misquote(entry):
        words, idx, _cure = entry
        t0 = _QE_ANCHOR - (_pv.prefix_len(words, idx) + 1)
        tail = ' '.join(words[idx + 1:])
        last = (_QE_ANCHOR + len(words[idx]) + 1
                + (1 + len(tail) if tail else 0))
        return (len(words[idx]) >= 2 and t0 >= _QE_TEXT_MIN
                and last <= _QE_BAY_E)

    cure_pool = _pv.misquotes_by_cure_len(_QE_CURE_LEN)
    for _ in range(200):
        sayings = rng.sample(_pv.PLAIN, len(_QE_SHAPE))
        junks: list = []
        rows = []
        ok = True
        for (r, jlen, q), words in zip(_QE_SHAPE, sayings):
            junk = rng.choice(junk_pool(jlen))
            # C5's fitting is '"" "junk"' (jlen+5); others '"junk"' (jlen+2)
            fitlen = jlen + 5 if r in _QE_C5_ROWS else jlen + 2
            ks = [k for k in range(1, len(words)) if fits(words, k, fitlen)]
            if not ks or junk in words:
                ok = False
                break
            junks.append(junk)
            rows.append((r, words, rng.choice(ks), junk, q))
        if not ok or len(set(junks)) != len(junks):
            continue
        mis = rng.sample(cure_pool, len(_QE_C2_ROWS))
        if not all(fits_misquote(m) for m in mis):
            continue
        # a C4 door's target is the PRISTINE saying — it must not also be
        # one of the other laid sayings (they never appear whole at build,
        # but a mended C4 row must not open a sibling's bolt)
        return {'intruders': rows, 'misquotes': mis}
    raise ValueError('quote_enclosure: no fitting draw after 200 tries')


def build_dungeon_quote_enclosure(seed: int) -> Dungeon:
    """The Quote Enclosure (slug `quote_enclosure`): i" a" i' a' — strike
    the quoted settings from the spine; the seek does the walking.
    Sense, not decree: proverb bays; the da" rows tear the junk out and
    the pristine saying itself is the door's reading."""
    from vimny.content.proverbs import prefix_len, text_of
    from vimny.engine.editor import _CELL_CODE
    from vimny.sharing.format import Level as _Level, _parse_seal, build as _fmt_build
    rng = random.Random(seed)
    texts = _qe_draw_texts(rng)

    R, C = _QE_ROWS, _QE_COLS
    grid = [[CellType.WALL] * C for _ in range(R)]
    for r in range(2, _QE_GATE + 1):                     # the spine
        grid[r][_QE_SPINE] = CellType.FLOOR
    lesson_rows = (_QE_C1_ROWS + _QE_C2_ROWS + _QE_C3_ROWS
                   + _QE_C4_ROWS + _QE_C5_ROWS)
    for r in lesson_rows:                                # the bays
        for c in range(_QE_BAY_W, _QE_BAY_E + 1):
            grid[r][c] = CellType.FLOOR
    for r, c in _QE_SHAFT_SEPS:                          # the light shafts —
        grid[r][c] = CellType.FLOOR                     # NOT the throat row

    runs: list = []

    def lay(r, col, words_seq):
        for w in words_seq:
            runs.append({'row': r, 'col': col, 'symbols': w, 'kind': 'ancient'})
            col += len(w) + 1

    truths = {}                                          # row -> (prefix, suffix)
    for (r, words, k, junk, q) in texts['intruders']:
        fit = (f'{q}{q} {q}{junk}{q}' if r in _QE_C5_ROWS
               else f'{q}{junk}{q}')
        t0 = _QE_ANCHOR - (prefix_len(words, k) + 1)
        lay(r, t0, words[:k])
        runs.append({'row': r, 'col': _QE_ANCHOR, 'symbols': fit,
                     'kind': 'ancient'})
        lay(r, _QE_ANCHOR + len(fit) + 1, words[k:])
        truths[r] = (text_of(words[:k]), text_of(words[k:]))
    cures = {}
    for r, (words, idx, cure) in zip(_QE_C2_ROWS, texts['misquotes']):
        t0 = _QE_ANCHOR - (prefix_len(words, idx) + 1)
        lay(r, t0, words[:idx])
        runs.append({'row': r, 'col': _QE_ANCHOR,
                     'symbols': f'"{words[idx]}"', 'kind': 'ancient'})
        tail = words[idx + 1:]
        if tail:
            lay(r, _QE_ANCHOR + len(words[idx]) + 3, tail)
        true = (f'{text_of(words[:idx])} "{cure}"'
                + (f' {text_of(tail)}' if tail else ''))
        cures[r] = (cure, true)

    c1 = tuple(f'{truths[r][0]} "" {truths[r][1]}' for r in _QE_C1_ROWS)
    c2 = tuple(cures[r][1] for r in _QE_C2_ROWS)
    c3 = tuple(f"{truths[r][0]} '' {truths[r][1]}" for r in _QE_C3_ROWS)
    c4 = tuple(f'{truths[r][0]} {truths[r][1]}' for r in _QE_C4_ROWS)
    c5 = tuple(f'{truths[r][0]} "" "" {truths[r][1]}' for r in _QE_C5_ROWS)
    doors = ((c1, _QE_BOLTS['c1']), (c2, _QE_BOLTS['c2']),
             (c3, _QE_BOLTS['c3']), (c4, _QE_BOLTS['c4']),
             (c5, _QE_BOLTS['c5']))

    seals = []
    for i, (targets, bolt_col) in enumerate(doors):
        seals.append(_parse_seal({
            'scope': 'anyrow', 'mode': 'exact', 'anchor': 'exit_row',
            'match': [str(t) for t in targets],
            'opens': [[_QE_EXIT[0], bolt_col]],
        }, i))
    seals.append(_parse_seal({
        'anchor': 'exit_row',
        'requires': list(range(len(seals))),
        'opens': [list(_QE_EXIT)],
    }, len(seals)))

    ca, cb = (cures[r][0] for r in _QE_C2_ROWS)
    level = _Level(
        name='The Quote Enclosure', seed=seed,
        rows=R, cols=C,
        cells=[''.join(_CELL_CODE[c] for c in row) for row in grid],
        spawn=(2, _QE_SPINE), exit=_QE_EXIT,
        char_runs=runs, seals=seals,
        entities=[{'kind': 'exit', 'at': [_QE_EXIT[0], _QE_EXIT[1]],
                   'edit_immune': True}],
        solution=(f'j di" j . 2j ci" {ca}<Esc> j ci" {cb}<Esc> '
                  f"2j di' j . 2j da\" j da' "
                  f'2j w di" G $'))

    dungeon = _fmt_build(level, par=_QE_PAR)
    _seal_banners(dungeon)
    dungeon.rooms[0]._qe_texts = texts
    return dungeon


# ── The Tag Enclosure (it at) ───────────────────────────────────────────────
#
# Tags are NAMED delimiters — <name>…</name>, paired by a stack, innermost
# wins — and unlike the quote objects they do NOT seek: the cursor must
# stand within the element (a blind spine strike is nothing here; the
# player pays one f> walk-in, then the dot-chains ride the aligned
# geometry). Five chambers on the exact-text chassis:
#   C1 (rows 3-4)   dit husk ×2, the second by dot   → 'w1 <n></n> w2'
#   C2 (rows 6-7)   cit cures (typed, single tokens) → 'w1 <n>cure</n> w2'
#   C3 (rows 9-10)  dat + dot — the whole element torn out. NOTE the gap:
#                   at spans the TAGS ONLY (no whitespace rule), so the
#                   tear leaves the DOUBLE gap 'w1  w2' — the da( scar,
#                   where the quote gallery's da" left the single.
#   C4 (rows 12-13) THE NEST, by NAME: <no><ni>jjj</ni></no> — from one
#                   landing column, dit empties the innermost; on the twin
#                   row dat tears the whole inner element out, leaving the
#                   outer husk '<no></no>'.
#   C5 (row 15)     THE AIM: '<na></na> <nb>jjj</nb>' — the landing sits in
#                   the FIRST element, already empty (dit no-ops); f< steps
#                   to the second element's mark, then dit.
#
# Forcing audit (why par 48 needs the objects): dit/dat resolve the whole
# element from any cell inside it, while {n}x pays its count digits plus
# the walk to the content start, d2f> pays a key over dat, and ct< pays
# the walk cit doesn't; % speaks the angle brackets but lands on single
# marks, not name-matched pairs.
_TE_ROWS, _TE_COLS = 19, 66
_TE_SPINE   = 2                      # every row's first standable
_TE_BAY_W   = 3                      # bay floor cols 3..63; east wall 64
_TE_BAY_E   = 63
_TE_TEXT_MIN = 3                     # earliest col a proverb may start
_TE_ANCHOR  = 29                     # standard rows: '<' of the element
_TE_NEST_ANCHOR = 24                 # nest/C5 rows: outer/first '<' (inner
                                     # opens at 29 = the chained landing)
_TE_C1_ROWS = (3, 4)
_TE_C2_ROWS = (6, 7)
_TE_C3_ROWS = (9, 10)
_TE_C4_ROWS = (12, 13)
_TE_C5_ROWS = (15,)
_TE_SHAFT_SEPS = ((5, 34), (8, 36), (11, 29), (14, 29))
_TE_THROAT  = 16
_TE_GATE    = 17
_TE_BOLTS   = {'c1': 3, 'c2': 4, 'c3': 5, 'c4': 6, 'c5': 7}
_TE_EXIT    = (17, 8)                # the FINAL SEAL, east of every bolt
# (row, junk len); tag names are len 3 throughout, so on standard rows the
# element content starts at col 34 — the chained landings stay inside each
# next element whatever the proverb (the Word Enclosure anchor law: the
# saying's prefix right-aligns west of the element).
_TE_SHAPE = ((3, 3), (4, 4), (9, 5), (10, 4), (12, 3), (13, 3), (15, 3))
_TE_CURE_LEN = 3
_TE_PAR = 48            # hand-tallied along the driven tape (one f> walk-in)


def _te_draw_texts(rng) -> dict:
    """Draw proverbs, junk and tag names for every slot (geometric fits
    keep par seed-invariant). Tag names are len 3, thirteen of them; junks
    distinct, foreign to their sayings."""
    from vimny.content import proverbs as _pv
    _load_vocab_tables()

    def pool(length):
        return [w for w in _VOCAB_PLAIN_BY_LEN.get(length, ())
                if w.isalpha() and w == w.lower()]

    def fits(words, k, anchor, fitlen):
        t0 = anchor - (_pv.prefix_len(words, k) + 1)
        last = anchor + fitlen + 1 + len(' '.join(words[k:])) - 1
        return t0 >= _TE_TEXT_MIN and last <= _TE_BAY_E

    def fits_misquote(entry):
        words, idx, _cure = entry
        t0 = _TE_ANCHOR - (_pv.prefix_len(words, idx) + 1)
        tail = ' '.join(words[idx + 1:])
        last = (_TE_ANCHOR + len(words[idx]) + 11
                + (1 + len(tail) if tail else 0) - 1)
        return (len(words[idx]) >= 3 and t0 >= _TE_TEXT_MIN
                and last <= _TE_BAY_E)

    n_sayings = len(_TE_SHAPE) + len(_TE_C2_ROWS)  # intruder rows only draw 7
    cure_pool = _pv.misquotes_by_cure_len(_TE_CURE_LEN)
    for _ in range(200):
        sayings = rng.sample(_pv.PLAIN, len(_TE_SHAPE))
        names = rng.sample(pool(3), 13)
        junks: list = []
        rows = []
        ni = iter(names)
        ok = True
        for (r, jlen), words in zip(_TE_SHAPE, sayings):
            junk = rng.choice(pool(jlen))
            if r in _TE_C4_ROWS:
                tag = (next(ni), next(ni))               # (outer, inner)
                anchor, fitlen = _TE_NEST_ANCHOR, 25
            elif r in _TE_C5_ROWS:
                tag = (next(ni), next(ni))               # (first, second)
                anchor, fitlen = _TE_NEST_ANCHOR, 26
            else:
                tag = (next(ni),)
                anchor, fitlen = _TE_ANCHOR, jlen + 11
            ks = [k for k in range(1, len(words))
                  if fits(words, k, anchor, fitlen)]
            if not ks or junk in words or junk in names:
                ok = False
                break
            junks.append(junk)
            rows.append((r, words, rng.choice(ks), junk, tag))
        if not ok or len(set(junks)) != len(junks):
            continue
        mis = rng.sample(cure_pool, len(_TE_C2_ROWS))
        if not all(fits_misquote(m) for m in mis):
            continue
        return {'intruders': rows, 'misquotes': mis,
                'c2_names': names[-2:]}
    raise ValueError('tag_enclosure: no fitting draw after 200 tries')


def build_dungeon_tag_enclosure(seed: int) -> Dungeon:
    """The Tag Enclosure (slug `tag_enclosure`): it at — name the element,
    and the innermost answers. Sense, not decree: proverb bays; the
    elements case junk stones or the saying's miswritten key word."""
    from vimny.content.proverbs import prefix_len, text_of
    from vimny.engine.editor import _CELL_CODE
    from vimny.sharing.format import Level as _Level, _parse_seal, build as _fmt_build
    rng = random.Random(seed)
    texts = _te_draw_texts(rng)

    R, C = _TE_ROWS, _TE_COLS
    grid = [[CellType.WALL] * C for _ in range(R)]
    for r in range(2, _TE_GATE + 1):                     # the spine
        grid[r][_TE_SPINE] = CellType.FLOOR
    lesson_rows = (_TE_C1_ROWS + _TE_C2_ROWS + _TE_C3_ROWS
                   + _TE_C4_ROWS + _TE_C5_ROWS)
    for r in lesson_rows:                                # the bays
        for c in range(_TE_BAY_W, _TE_BAY_E + 1):
            grid[r][c] = CellType.FLOOR
    for r, c in _TE_SHAFT_SEPS:                          # the light shafts —
        grid[r][c] = CellType.FLOOR                     # NOT the throat row

    runs: list = []

    def lay(r, col, words_seq):
        for w in words_seq:
            runs.append({'row': r, 'col': col, 'symbols': w, 'kind': 'ancient'})
            col += len(w) + 1

    doors_targets = {k: [] for k in ('c1', 'c2', 'c3', 'c4', 'c5')}
    for (r, words, k, junk, tag) in texts['intruders']:
        pre, suf = text_of(words[:k]), text_of(words[k:])
        if r in _TE_C4_ROWS:
            no, ni_ = tag
            fit = f'<{no}><{ni_}>{junk}</{ni_}></{no}>'
            tgt = (f'{pre} <{no}><{ni_}></{ni_}></{no}> {suf}'
                   if r == _TE_C4_ROWS[0] else f'{pre} <{no}></{no}> {suf}')
            doors_targets['c4'].append(tgt)
            anchor = _TE_NEST_ANCHOR
        elif r in _TE_C5_ROWS:
            na, nb = tag
            fit = f'<{na}></{na}> <{nb}>{junk}</{nb}>'
            doors_targets['c5'].append(
                f'{pre} <{na}></{na}> <{nb}></{nb}> {suf}')
            anchor = _TE_NEST_ANCHOR
        else:
            name, = tag
            fit = f'<{name}>{junk}</{name}>'
            anchor = _TE_ANCHOR
            if r in _TE_C1_ROWS:
                doors_targets['c1'].append(f'{pre} <{name}></{name}> {suf}')
            else:                                # C3: the double-gap tear
                doors_targets['c3'].append(f'{pre}  {suf}')
        t0 = anchor - (prefix_len(words, k) + 1)
        lay(r, t0, words[:k])
        runs.append({'row': r, 'col': anchor, 'symbols': fit,
                     'kind': 'ancient'})
        lay(r, anchor + len(fit) + 1, words[k:])
    cures = []
    for r, name, (words, idx, cure) in zip(_TE_C2_ROWS, texts['c2_names'],
                                           texts['misquotes']):
        t0 = _TE_ANCHOR - (prefix_len(words, idx) + 1)
        lay(r, t0, words[:idx])
        fit = f'<{name}>{words[idx]}</{name}>'
        runs.append({'row': r, 'col': _TE_ANCHOR, 'symbols': fit,
                     'kind': 'ancient'})
        tail = words[idx + 1:]
        if tail:
            lay(r, _TE_ANCHOR + len(fit) + 1, tail)
        doors_targets['c2'].append(
            f'{text_of(words[:idx])} <{name}>{cure}</{name}>'
            + (f' {text_of(tail)}' if tail else ''))
        cures.append(cure)
    doors = tuple((tuple(doors_targets[k]), _TE_BOLTS[k])
                  for k in ('c1', 'c2', 'c3', 'c4', 'c5'))

    seals = []
    for i, (targets, bolt_col) in enumerate(doors):
        seals.append(_parse_seal({
            'scope': 'anyrow', 'mode': 'exact', 'anchor': 'exit_row',
            'match': [str(t) for t in targets],
            'opens': [[_TE_EXIT[0], bolt_col]],
        }, i))
    seals.append(_parse_seal({
        'anchor': 'exit_row',
        'requires': list(range(len(seals))),
        'opens': [list(_TE_EXIT)],
    }, len(seals)))

    ca, cb = cures
    level = _Level(
        name='The Tag Enclosure', seed=seed,
        rows=R, cols=C,
        cells=[''.join(_CELL_CODE[c] for c in row) for row in grid],
        spawn=(2, _TE_SPINE), exit=_TE_EXIT,
        char_runs=runs, seals=seals,
        entities=[{'kind': 'exit', 'at': [_TE_EXIT[0], _TE_EXIT[1]],
                   'edit_immune': True}],
        solution=(f'j f> dit j . 2j cit {ca}<Esc> j cit {cb}<Esc> '
                  f'2j dat j . 2j dit j dat 2j f< dit G $'))

    dungeon = _fmt_build(level, par=_TE_PAR)
    _seal_banners(dungeon)
    dungeon.rooms[0]._te_texts = texts
    return dungeon


# ── The Sentence Enclosure (is as) ──────────────────────────────────────────
#
# Sentences are delimited by their own PUNCTUATION — every glyph on a row
# belongs to one — so is/as forgive position INSIDE the sentence while the
# old tools (d) d( df. d$) demand its exact edges. Every strike here lands
# MID-sentence (the chained geometry guarantees it), which is precisely
# where the objects win. Five chambers on the exact-text chassis:
#   C1 (rows 3-4)   dis the rotten middle ×2 (dot)  → 's1.  s3.' — inner
#                   trims no whitespace, so the DOUBLE gap remains
#   C2 (rows 6-7)   das the middle ×2 (dot)         → 's1. s3.' — around
#                   spans the trailing space: the SINGLE gap (the pair
#                   lesson, sentence flavour — and the doors discriminate:
#                   a d) golf produces the WRONG gap for C1)
#   C3 (rows 9-10)  cis cures (typed word + its period, single tokens)
#   C4 (row 12)     das the LAST sentence: nothing trails, so the object
#                   eats the LEADING whitespace (Vim-true, engine'd today)
#   C5 (row 14)     das + dot ACROSS sentences: raze the first two, keep
#                   the last — the dot rides the collapsing row
#
# Forcing audit (why par 45 needs the objects): every landing is
# mid-sentence, where d)/d(/d$ delete PARTIAL sentences and df. leaves the
# head; whole-sentence spans cost the old tools their positioning (F./^/hh)
# on every row; the C1-vs-C2 gap discrimination text-forces is-vs-as; '.'
# repeats are 1 key and cannot be undercut.
_SE_ROWS, _SE_COLS = 18, 69
_SE_SPINE   = 2                      # every row's first standable
_SE_BAY_W   = 3                      # bay floor cols 3..66; east wall 67
_SE_BAY_E   = 66
_SE_TEXT_MIN = 3                     # earliest col a west saying may start
_SE_TEXT0   = 24                     # C5's first junk / C3's fixed rows
_SE_C1_ROWS = (3, 4)
_SE_C2_ROWS = (6, 7)
_SE_C3_ROWS = (9, 10)
_SE_C4_ROWS = (12,)
_SE_C5_ROWS = (14,)
_SE_SHAFT_SEPS = ((5, 33), (8, 31), (11, 35), (13, 30))
_SE_THROAT  = 15
_SE_GATE    = 16
_SE_BOLTS   = {'c1': 3, 'c2': 4, 'c3': 5, 'c4': 6, 'c5': 7}
_SE_EXIT    = (16, 8)                # the FINAL SEAL, east of every bolt
_SE_SPAWN   = (2, 37)                # over C1's junk word 2: j lands MID
# SENSE, NOT DECREE: every row is famous sayings AS SENTENCES with a junk
# sentence wedged in (C1 scar / C2 seam / C4 trailing / C5 keep-last), or
# — C3, FIXED texts, seeded miswrite — the classics whose sentences the
# player completes by heart: 'veni. ????. vici.' cured with `vidi.` and
# 'live. ????. love.' cured with `laugh.` (single tokens, karaoke-safe;
# the veni-vidi-vici strand returns at the Grandmaster's exam — a
# deliberate callback). Par invariance is COLUMN-ANCHORED: each row's
# TARGET sentence starts at its slot column; the west saying right-aligns.
_SE_C1_JUNK = 33                     # 'aaa bbb.' at 33 (spawn drops on 37)
_SE_C2_JUNK = 31
_SE_C3_MID  = 30                     # the miswritten middle, len 4 + '.'
_SE_C4_JUNK = 31
_SE_C5_JUNK2 = 33                    # junkA at TEXT0, junkB at 33, saying 42
_SE_EAST    = {'c1': 42, 'c2': 40, 'c5': 42}   # east sayings' start cols
_SE_C3_FIX  = ((('veni',), 'vidi', ('vici',)),
               (('live',), 'laugh', ('love',)))
_SE_PAR = 44            # hand-tallied along the driven tape (mid landings;
                        # C5 falls to TWO DOTS riding C4's das — known golf;
                        # cures are 'vidi.' + 'laugh.')


def _se_sentence(words) -> str:
    return ' '.join(words) + '.'


def _se_draw_texts(rng) -> dict:
    """Draw the sayings + junk. West sayings right-align to their slot,
    east sayings start at fixed columns — both filtered by length so par
    stays seed-invariant. Ten distinct sayings; junk foreign to all."""
    from vimny.content import proverbs as _pv
    _load_vocab_tables()

    def pool(length):
        return [w for w in _VOCAB_PLAIN_BY_LEN.get(length, ())
                if w.isalpha() and w == w.lower()]

    # (slot key, west cap incl '.', east cap incl '.') — west spans
    # [t0, junk-2], east runs from _SE_EAST to the bay edge
    west_caps = {'c1': _SE_C1_JUNK - 2 - _SE_TEXT_MIN + 1,
                 'c2': _SE_C2_JUNK - 2 - _SE_TEXT_MIN + 1,
                 'c4': _SE_C4_JUNK - 2 - _SE_TEXT_MIN + 1}
    east_caps = {k: _SE_BAY_E - c + 1 for k, c in _SE_EAST.items()}

    sent = [_se_sentence(w) for w in _pv.PLAIN]
    for _ in range(200):
        # fill the tightest slots first, straight from length-filtered
        # candidates (a blind 10-sample starves the short-saying slots)
        east_slots = ['c1', 'c1', 'c5', 'c2', 'c2']     # caps ascending-ish
        west_slots = ['c2', 'c2', 'c4', 'c1', 'c1']
        rest = list(sent)
        picked = {}
        ok = True
        for tag, k in ([('e', k) for k in east_slots]
                       + [('w', k) for k in west_slots]):
            cap = east_caps[k] if tag == 'e' else west_caps[k]
            cands = [s for s in rest if len(s) <= cap]
            if not cands:
                ok = False
                break
            s = rng.choice(cands)
            rest.remove(s)
            picked.setdefault(tag + k, []).append(s)
        if not ok:
            continue
        east = (picked['ec1'] + picked['ec2'] + picked['ec5'])
        west = (picked['wc1'] + picked['wc2'] + picked['wc4'])
        saying_words = {w for s in east + west for w in s.rstrip('.').split(' ')}
        junk3 = [w for w in rng.sample(pool(3), 20)
                 if w not in saying_words][:14]
        mids = [w for w in rng.sample(pool(4), 8)
                if w not in saying_words][:2]
        if len(junk3) < 14 or len(mids) < 2:
            continue
        return {'east': east, 'west': west, 'junk3': junk3, 'mids': mids}
    raise ValueError('sentence_enclosure: no fitting draw after 200 tries')


def build_dungeon_sentence_enclosure(seed: int) -> Dungeon:
    """The Sentence Enclosure (slug `sentence_enclosure`): is as — the
    sentence under your hand, from anywhere inside it. Sense, not decree:
    the sentences are sayings the player knows whole."""
    from vimny.engine.editor import _CELL_CODE
    from vimny.sharing.format import Level as _Level, _parse_seal, build as _fmt_build
    rng = random.Random(seed)
    texts = _se_draw_texts(rng)
    e_c1a, e_c1b, e_c2a, e_c2b, e_c5 = texts['east']
    w_c1a, w_c1b, w_c2a, w_c2b, w_c4 = texts['west']
    j = iter(texts['junk3'])

    def jpair():
        return f'{next(j)} {next(j)}.'

    # row -> (full text, text0)
    rows, tgt = {}, {}
    for r, w_s, e_s, slot in ((3, w_c1a, e_c1a, _SE_C1_JUNK),
                              (4, w_c1b, e_c1b, _SE_C1_JUNK)):
        junk = jpair()
        rows[r] = (f'{w_s} {junk} {e_s}', slot - 1 - len(w_s))
        tgt[r] = f'{w_s}  {e_s}'                 # dis: the DOUBLE gap
    for r, w_s, e_s, slot in ((6, w_c2a, e_c2a, _SE_C2_JUNK),
                              (7, w_c2b, e_c2b, _SE_C2_JUNK)):
        junk = jpair()
        rows[r] = (f'{w_s} {junk} {e_s}', slot - 1 - len(w_s))
        tgt[r] = f'{w_s} {e_s}'                  # das: the SINGLE gap
    for r, ((s1, cure, s3), mid) in zip(_SE_C3_ROWS,
                                        zip(_SE_C3_FIX, texts['mids'])):
        rows[r] = (f'{_se_sentence(s1)} {mid}. {_se_sentence(s3)}', _SE_TEXT0)
        tgt[r] = f'{_se_sentence(s1)} {cure}. {_se_sentence(s3)}'
    rows[12] = (f'{w_c4} {jpair()}', _SE_C4_JUNK - 1 - len(w_c4))
    tgt[12] = w_c4                               # das last: the saying stands
    rows[14] = (f'{jpair()} {jpair()} {e_c5}', _SE_TEXT0)
    tgt[14] = e_c5                               # C5: only the saying stands
    doors = ((tuple(tgt[r] for r in _SE_C1_ROWS), _SE_BOLTS['c1']),
             (tuple(tgt[r] for r in _SE_C2_ROWS), _SE_BOLTS['c2']),
             (tuple(tgt[r] for r in _SE_C3_ROWS), _SE_BOLTS['c3']),
             ((tgt[_SE_C4_ROWS[0]],), _SE_BOLTS['c4']),
             ((tgt[_SE_C5_ROWS[0]],), _SE_BOLTS['c5']))

    R, C = _SE_ROWS, _SE_COLS
    grid = [[CellType.WALL] * C for _ in range(R)]
    for r in range(2, _SE_GATE + 1):                     # the spine
        grid[r][_SE_SPINE] = CellType.FLOOR
    for r in rows:                                       # the bays
        for c in range(_SE_BAY_W, _SE_BAY_E + 1):
            grid[r][c] = CellType.FLOOR
    for r, c in _SE_SHAFT_SEPS:                          # the light shafts —
        grid[r][c] = CellType.FLOOR                     # NOT the throat row
    grid[_SE_SPAWN[0]][_SE_SPAWN[1]] = CellType.FLOOR   # the drop-in

    runs: list = []
    for r, (text, t0) in rows.items():
        # Space-free runs with bare-floor gaps (the space-glyph law: a
        # literal space glyph is a punctuation 'word' and breaks w / the
        # sentence scanner) — the floor scan reconstructs the spacing.
        col = t0
        for part in text.split(' '):
            if part:
                runs.append({'row': r, 'col': col, 'symbols': part,
                             'kind': 'ancient'})
            col += len(part) + 1

    seals = []
    for i, (targets, bolt_col) in enumerate(doors):
        seals.append(_parse_seal({
            'scope': 'anyrow', 'mode': 'exact', 'anchor': 'exit_row',
            'match': [str(t) for t in targets],
            'opens': [[_SE_EXIT[0], bolt_col]],
        }, i))
    seals.append(_parse_seal({
        'anchor': 'exit_row',
        'requires': list(range(len(seals))),
        'opens': [list(_SE_EXIT)],
    }, len(seals)))

    ca, cb = (fix[1] for fix in _SE_C3_FIX)
    level = _Level(
        name='The Sentence Enclosure', seed=seed,
        rows=R, cols=C,
        cells=[''.join(_CELL_CODE[c] for c in row) for row in grid],
        spawn=_SE_SPAWN, exit=_SE_EXIT,
        char_runs=runs, seals=seals,
        entities=[{'kind': 'exit', 'at': [_SE_EXIT[0], _SE_EXIT[1]],
                   'edit_immune': True}],
        solution=(f'j dis j . 2j das j . 2j cis {ca}.<Esc> j cis {cb}.<Esc> '
                  f'2j das 2j . . G $'))

    dungeon = _fmt_build(level, par=_SE_PAR)
    _seal_banners(dungeon)
    room = dungeon.rooms[0]
    room._se_texts = texts
    room._se_rows = rows
    return dungeon


# ── The Paragraph Enclosure (ip ap) ───────────────────────────────────────────
#
# Two cantos of the goblin legion stand in ranked verse — 11 and 12 rows,
# tall enough that a counted line-cut (11dd / 14dd) pays its second digit
# where dip/dap do not, and UNEQUAL so no dot can repeat one canto's cut on
# the other. The gate keeps the WARDEN'S SIGIL: six braziers scattered on
# the three rows that must SURVIVE (the spawn row, the rest between the
# cantos, the gate row), placed so that when — and only when — exactly the
# right paragraphs fall, the survivors stack into the sigil:
#         🜂          spawn row       (c)
#        🜂 🜂         the rest        (c−1, c+1)
#       🜂 🜂 🜂        gate row        (c−2, c, c+2)
# (each flame is the Beacon Tiers' 🜂 with its flicker — established
# vocabulary only; entity-borne so its row stays BLANK)
# The seal parts when the sigil stands assembled and no goblin lives. The
# win condition is VISIBLE: a cut through the wrong row extinguishes its
# flames (remove_row kills entities), the hole in the sigil says exactly
# what went wrong, and undo relights them. No un-Vim parrying anywhere —
# 25dd/d}/dG all WORK; they just wreck the sigil:
#   • the rest below the first canto must SURVIVE — its brazier pair is
#     the visible reason; dip spares it, dap/d}/any spanning cut kills it;
#   • the spawn row must SURVIVE (its lone flame) — no counted cut may
#     start there, so the first cut is taken from INSIDE the canto;
#   • the watch-gap below the second canto AND its echo row must FALL —
#     dap's trailing block is the whole consecutive blank run (both rows);
#     V}d grabs one blank short, counted cuts pay their digits;
#   • the watch-gap's goblins stand on a TEXTLESS row, so no :g pattern
#     can ever reach them.
# Blank rows must hold NO char runs anywhere (a wall-embedded glyph would
# make the row non-blank and weld the cantos into one paragraph) — the
# braziers are ENTITIES, which leave their rows blank. The gate row's
# floor plaque is what stops dap's blank-run extension at the gate.
_PE_ROWS, _PE_COLS = 30, 32
_PE_SPAWN  = (1, 1)
_PE_P1     = (2, 12)        # first canto: 11 content rows
_PE_B1     = 13             # the warden's rest — must survive (dip, not dap)
_PE_P2     = (14, 25)       # second canto: 12 content rows (≠ P1 — no dot pair)
_PE_GUARD  = 26             # the watch-gap: goblins on a textless (blank) row
_PE_B2     = 27             # its echo — dap's trailing blank block is BOTH rows
_PE_GATE   = 28
_PE_EXIT   = (28, 27)       # the sealed exit cell itself (plain stone until open)
_PE_TEXT0  = 3
_PE_GOB_COLS   = (29, 29)   # canto sentinels: the clear column east of the
                            # longest gift line (glyph-overlay law: an entity
                            # letter must never sit on verse text)
_PE_GUARD_COLS = (8, 13, 18, 23)
_PE_SIGIL_COL  = 22         # the sigil's centre column (east, clear of the plaque)
_PE_SIGIL      = ((0, 0), (1, -1), (1, 1), (2, -2), (2, 0), (2, 2))
# Initial (row, col) of each flame: lone on the spawn row, pair on the rest,
# trio on the gate row — the sigil's shape, stretched across the hall until
# the deletions pull the three rows together.
_PE_BRAZIERS   = ((1, 22), (13, 21), (13, 23), (28, 20), (28, 22), (28, 24))
_PE_PAR    = 9              # j dip j dap $ — best old-only (j 11dd j 14dd $) pays 11


# SENSE, NOT DECREE (the design law): the cantos are the
# legion's PLUNDER-CHANT — the Twelve Days gift list (secular lines only,
# PD), canto 1 running eleven-to-partridge (11 rows), canto 2 the full
# twelve-to-partridge (12 rows). FIXED text, deliberately: no door reads it
# and nothing is typed — its job is to be a block the player recognises as
# the goblins' loot, stacked to the exact heights the counted-cut forcing
# needs; the repeated lines are authentic to the song.
_PE_GIFTS = ('twelve drummers drumming', 'eleven pipers piping',
             'ten lords a leaping', 'nine ladies dancing',
             'eight maids a milking', 'seven swans a swimming',
             'six geese a laying', 'five gold rings',
             'four calling birds', 'three french hens',
             'two turtle doves', 'a partridge in a pear tree')


def _pe_draw_words(rng) -> dict:
    """One gift line per canto row: canto 1 = eleven..partridge (11 rows),
    canto 2 = twelve..partridge (12 rows)."""
    rows = {}
    for (lo, hi), lines in ((_PE_P1, _PE_GIFTS[1:]), (_PE_P2, _PE_GIFTS)):
        for r, line in zip(range(lo, hi + 1), lines):
            rows[r] = tuple(line.split(' '))
    return rows


def build_dungeon_paragraph_enclosure(seed: int) -> Dungeon:
    """The Paragraph Enclosure (slug `paragraph_enclosure`): ip ap — the
    blank-row-bounded block under your hand, from anywhere inside it."""
    from vimny.engine.editor import _CELL_CODE
    from vimny.sharing.format import Level as _Level, build as _fmt_build
    rng = random.Random(seed)
    words = _pe_draw_words(rng)

    R, C = _PE_ROWS, _PE_COLS
    grid = [[CellType.WALL] * C for _ in range(R)]
    for r in range(1, _PE_GATE):                         # the hall: full-width
        for c in range(1, C - 2):
            grid[r][c] = CellType.FLOOR
    # The watch-gap's west end is walled: `}` from the west aisle refuses a
    # walled column (it never skips ahead), so V}d from the second canto's
    # top row cannot grab exactly canto+gap for 3 keys and tie par — the
    # visual route must first pay its way east onto the verse.
    for c in range(1, _PE_GUARD_COLS[0] - 2):
        grid[_PE_GUARD][c] = CellType.WALL
    for c in range(1, _PE_EXIT[1]):                      # gate row: aisle to the seal
        grid[_PE_GATE][c] = CellType.FLOOR
    # _PE_EXIT itself stays WALL — the seal; plain stone until the measure holds.

    runs: list = []
    for r, parts in words.items():                       # the cantos' verses
        col = _PE_TEXT0
        for w in parts:                                  # per-word runs (the
            runs.append({'row': r, 'col': col, 'symbols': w,
                         'kind': 'ancient'})
            col += len(w) + 1                            # space-glyph law)
    # The gate plaque (floor runes): names the measure, and — being char runs —
    # keeps the gate row non-blank so dap's blank-run extension stops here.
    col = _PE_TEXT0
    for part in ('sign', 'and', 'seal'):
        runs.append({'row': _PE_GATE, 'col': col, 'symbols': part,
                     'kind': 'verdant'})
        col += len(part) + 1

    entities = [{'kind': 'exit', 'at': [_PE_EXIT[0], _PE_EXIT[1]],
                 'edit_immune': True}]
    # The sigil's flames — NOT edit_immune: a cut through a flame's row
    # succeeds and extinguishes it (the hole in the sigil shows the player
    # exactly which row should have survived); undo relights it.
    for br, bc in _PE_BRAZIERS:
        entities.append({'kind': 'brazier', 'at': [br, bc], 'hp': 1, 'max_hp': 1})
    for lo, hi in (_PE_P1, _PE_P2):                      # one sentinel per verse row
        for r in range(lo, hi + 1):
            entities.append({'kind': 'goblin', 'at': [r, rng.randint(*_PE_GOB_COLS)],
                             'hp': 1, 'max_hp': 1})
    for gc in _PE_GUARD_COLS:                            # the watch-gap: no runes
        entities.append({'kind': 'goblin', 'at': [_PE_GUARD, gc],
                         'hp': 1, 'max_hp': 1})

    level = _Level(
        name='The Paragraph Enclosure', seed=seed,
        rows=R, cols=C,
        cells=[''.join(_CELL_CODE[c] for c in row) for row in grid],
        spawn=_PE_SPAWN, exit=_PE_EXIT,
        char_runs=runs, entities=entities,
        solution='j dip j dap $')

    dungeon = _fmt_build(level, par=_PE_PAR)
    dungeon.rooms[0]._pe_words = words
    return dungeon


# ── The Grandmaster's Sanctum (38.1, act boss) ────────────────────────────────
#
# Two rooms. Room 0 — the PROVING GALLERY: seven bays on the exact-text
# chassis, each a condensed reprise of its level's signature discovery, ops
# STAGGERED d/c/d/c/d/c/d so no dot rides between bays. Six text doors +
# the legion bolt (the paragraph bay's goblins must fall). The Grandmaster
# stands in the gate pocket (edit_immune — he also anchors the gate row
# against dG) and voices one line of cold appraisal per bolt; the pocket is
# stone-hidden until the seal parts (fog law), so his presence in the
# gallery is his VOICE — he is seen when the stone opens. Stepping through
# the gate swaps to room 1. Room 1 — the ARENA: the Warden's Keep pattern
# (warden hp5 → key drop → locked door → exit + chest with The Warden's
# Act). Boss conventions: par None, hand-set budget, no exit entity in the
# gallery (winning is stepping on the ARENA's exit).
#
# Bay door targets are computed FROM layout math (charwise deletes leave
# literal gaps on non-ledge rows — a diw hole is rot+2 spaces wide), so the
# plaque, the door, and the operator can never drift apart.
_GMS_ROWS0, _GMS_COLS0 = 21, 54
_GMS_SPINE   = 22
_GMS_PLQ_COL = 2                       # west-wall plaques (park-safe, uncuttable)
_GMS_TEXT0   = 24
_GMS_BAYS    = (3, 5, 7, 9, 11, 13)   # word · quote · bracket · sentence · tag · brace
_GMS_PARA    = (15, 16)               # the legion bay: a 2-row canto, goblins standing
_GMS_TAIL    = 17                      # its trailing blank …
_GMS_THROAT  = 18                      # … and the spine-only throat (also blank)
_GMS_GATE    = 19
_GMS_BOLTS   = (23, 24, 25, 26, 27, 28, 29)
_GMS_SEAL    = 30                      # stone until every proof is made
_GMS_APPRAISALS = (                    # one cold line per bolt, on the turn it opens
    "'The word, taken clean.' A bolt draws back.",
    "'You carried past the empty marks without a stroke.' A bolt draws back.",
    "'The fitting, torn whole from its setting.' A bolt draws back.",
    "'A verse cut mid-breath, and made true.' A bolt draws back.",
    "'You asked the case its name, and kept the case.' A bolt draws back.",
    "'You read the metal, not the shape.' A bolt draws back.",
    "The last goblin falls!",
)
_GMS_FINAL_LINE = ('The stone parts — and the Grandmaster regards you. '
                   '"Then come. The floor will speak for you."')
_GMS_TRANSIT = (19, 31)                # exit_pos: stepping here (or past) descends
_GMS_WATCH   = (19, 32)                # where the Grandmaster stands
_GMS_BUDGET  = 160                     # hand-set, generous (gallery + arena melee)

# ── Room 1: The Unmaking (the arena) ─────────────────────────────────────────
# The Grandmaster is the master of the written WORD — so he cannot be struck
# (edit_immune); he can only be UNWRITTEN. He is woven from six strands, each a
# different text object inscribed on a lectern. When the player closes within 2
# cells he FLEES to the nearest strand still standing; the only recourse is to
# shear a lectern with its matching object (diw · di" · di( · di{ · dit · dis),
# which costs him a strand (−1 HP) and drives him on. Six strokes and the last
# strand parts — he is unmade and the sanctum opens. (The lectern texts are
# fixed and load-bearing: each is the exact structure its object targets, and
# the shear reads the exact remnant that object leaves — a whole-line dd wipes
# the structure too and does NOT count. All six are CHARWISE inner-deletes, so
# no strand collapses a row mid-chase — the flight geometry stays put.)
_GMS_A_ROWS, _GMS_A_COLS = 15, 54
_GMS_A_SPAWN = (7, 2)
_GMS_A_BOSS  = (2, 8)                   # he opens INSIDE the first strand ('stitch'),
                                        # a valid deletion target — see _GMS_A_LECTERNS[0]
_GMS_A_SEAL_COL = 48                    # the sanctum seal wall (opens at 0 HP)
_GMS_A_EXIT  = (7, 52)
_GMS_A_HEART = (5, 51)
_GMS_A_CHEST = (9, 51)
_GMS_A_BUDGET = 300                     # boss convention: no par, very relaxed
# Each strand on its OWN row (a charwise delete pulls its row's tail left, so
# sharing a row would shift a neighbour's columns mid-fight). Fields: row,
# structure-start col, before-text, object, cursor col (where the delete is
# made), 'gone' (inner content the object removes) and 'keep' (a structure
# marker that SURVIVES the object but a whole-line dd would wipe — so only the
# inner-delete counts). They alternate left/right down the hall: a real chase.
# The six strands are FAMOUS FRAGMENTS (sense, not decree — each is a known
# phrase whose heart the player unweaves): a proverb's stitch, the cry of
# wolf, X marking the spot, the silver lining, Caesar twice over. The shear
# keys stay text-independent (f finds the DELIMITER — " ( { < — and the iw
# strand's target is the second word, as before).
_GMS_A_LECTERNS = [
    (2,  6,  'a stitch in time',         'iw', 8,  'stitch', 'time'),
    (4,  30, 'cry "wolf" again',         'i"', 35, 'wolf',   'cry'),
    (6,  8,  '(x) marks the spot',       'i(', 9,  'x',      'spot'),
    (8,  30, 'a {silver} lining',        'i{', 33, 'silver', 'lining'),
    (10, 6,  '<q>et tu</q> brute',       'it', 9,  'et tu',  'brute'),
    (12, 28, 'veni. vidi. vici.',        'is', 34, 'vidi',   'veni'),
]


def _gms_draw_words(rng) -> dict:
    """The gallery's vocabulary — all distinct so no door cross-matches."""
    _load_vocab_tables()

    def pool(length):
        return [w for w in _VOCAB_PLAIN_BY_LEN.get(length, ())
                if w.isalpha() and w == w.lower()]

    for _ in range(80):
        picks: list = []

        def draw(length):
            w = rng.choice(pool(length))
            picks.append(w)
            return w

        d = {
            'w_a': draw(3), 'w_rot': draw(4), 'w_b': draw(3),
            'q_c': draw(3), 'q_rot': draw(4), 'q_cure': draw(4),
            'k_d': draw(3), 'k_e': draw(3), 'k_rt': draw(3), 'k_g': draw(3),
            's_a': draw(3), 's_rot': draw(4), 's_cure': draw(4), 's_b': draw(3),
            't_l': draw(3), 't_name': draw(3), 't_rt': draw(3), 't_m': draw(3),
            # b_rot is len 5 so the brace pair spans the column where the
            # tag bay's dit parks the cursor (col 33) — ci{ has no forward
            # seek (Vim-faithful), so the chained landing must fall INSIDE
            # the braces, not east of them.
            'b_n': draw(3), 'b_rot': draw(5), 'b_cure': draw(3),
            'b_keep': draw(3), 'b_o': draw(3),
            'p_rows': ((draw(3), draw(4)), (draw(4), draw(3))),
        }
        flat = [w for w in picks]
        if len(set(flat)) == len(flat):
            return d
    raise ValueError('grandmasters_sanctum: no distinct draw after 80 tries')


def _gms_bay_specs(w) -> list:
    """(row_text, door_target) per bay, in bay order. Targets are computed
    from the SAME strings the rows are laid from. These bay rows are
    LEDGES: a charwise delete PULLS the tail left (close_gap), so a diw
    hole reads as the two ORIGINAL separator spaces (vs daw's one — the
    discrimination survives the pull), and da[/dit close up entirely."""
    return [
        # 1 · WORD (diw): the rot mid-row; the pull leaves the two
        # original gaps — daw eats one of them, and the door reads false.
        (f"{w['w_a']} {w['w_rot']} {w['w_b']}",
         f"{w['w_a']}  {w['w_b']}"),
        # 2 · QUOTE (ci"): an EMPTY pair first on the line — the forward
        # seek must carry past it; the cure is typed into the second pair.
        (f"\"\" {w['q_c']} \"{w['q_rot']}\"",
         f"\"\" {w['q_c']} \"{w['q_cure']}\""),
        # 3 · BRACKET (da[): the fitting torn whole from inside its
        # setting; the setting closes around the wound.
        (f"{w['k_d']} ({w['k_e']}[{w['k_rt']}]{w['k_g']})",
         f"{w['k_d']} ({w['k_e']}{w['k_g']})"),
        # 4 · SENTENCE (cis): the middle verse cut mid-breath and retyped.
        (f"{w['s_a']}. {w['s_rot']}. {w['s_b']}.",
         f"{w['s_a']}. {w['s_cure']}. {w['s_b']}."),
        # 5 · TAG (dit): empty the named case, keep the case (dat tears
        # it). The name is DRAWN per seed — the Tag Enclosure's precedent
        # (the name must derive from the tag, not be hard-coded).
        (f"{w['t_l']} <{w['t_name']}>{w['t_rt']}</{w['t_name']}> {w['t_m']}",
         f"{w['t_l']} <{w['t_name']}></{w['t_name']}> {w['t_m']}"),
        # 6 · BRACE (ci{): read the metal — the cure goes in the brace,
        # the bracketed casket beside it must stand untouched.
        (f"{w['b_n']} {{{w['b_rot']}}} [{w['b_keep']}] {w['b_o']}",
         f"{w['b_n']} {{{w['b_cure']}}} [{w['b_keep']}] {w['b_o']}"),
    ]


def build_dungeon_grandmasters_sanctum(seed: int) -> Dungeon:
    """The Grandmaster's Sanctum (slug `grandmasters_sanctum`): the act
    boss — every text object, asked properly, then the man himself."""
    from vimny.engine.editor import _CELL_CODE
    from vimny.sharing.format import Level as _Level, build as _fmt_build
    rng = random.Random(seed)
    words = _gms_draw_words(rng)
    specs = _gms_bay_specs(words)

    # ── Room 0: the proving gallery ─────────────────────────────────────────
    R, C = _GMS_ROWS0, _GMS_COLS0
    grid = [[CellType.WALL] * C for _ in range(R)]
    for r in range(1, _GMS_GATE + 1):                    # the spine
        grid[r][_GMS_SPINE] = CellType.FLOOR
    # Bays AND their separator rows are full-width floor (the ops chain
    # bay-to-bay straight down, SE's shaft trick generalised); only the
    # THROAT is spine-only, so no east column can drop past the bolts.
    for r in range(2, _GMS_THROAT):
        for c in range(_GMS_SPINE, 52):
            grid[r][c] = CellType.FLOOR
    for c in range(_GMS_SPINE, _GMS_WATCH[1] + 1):       # gate row + pocket
        grid[_GMS_GATE][c] = CellType.FLOOR
    for dc in _GMS_BOLTS:                                # the seven bolts
        grid[_GMS_GATE][dc] = CellType.WALL
    grid[_GMS_GATE][_GMS_SEAL] = CellType.WALL          # the final seal

    runs: list = []
    ent: list = []
    for bay_i, (text, target) in enumerate(specs):
        row = _GMS_BAYS[bay_i]
        col = _GMS_TEXT0                                 # the floor text
        for part in text.split(' '):
            if part:
                runs.append({'row': row, 'col': col, 'symbols': part,
                             'kind': 'ancient'})
            col += len(part) + 1
        col = _GMS_PLQ_COL                               # the west plaque = the target
        for part in target.split(' '):
            if part:
                runs.append({'row': row, 'col': col, 'symbols': part,
                             'kind': 'verdant'})
            col += len(part) + 1
    for pr_i, r in enumerate(_GMS_PARA):                 # the legion bay's canto
        a, b = words['p_rows'][pr_i]
        runs.append({'row': r, 'col': _GMS_TEXT0, 'symbols': a, 'kind': 'ancient'})
        runs.append({'row': r, 'col': _GMS_TEXT0 + len(a) + 1, 'symbols': b,
                     'kind': 'ancient'})
        for gc in (40, 46):
            ent.append({'kind': 'goblin', 'at': [r, gc],
                        'hp': 1, 'max_hp': 1, 'ai': ''})
    col = _GMS_PLQ_COL                                   # gate-row plaque: keeps the
    for part in ('the', 'last', 'gate'):                 # gate row non-blank (stops
        runs.append({'row': _GMS_GATE, 'col': col,       # dap's blank-run extension)
                     'symbols': part, 'kind': 'verdant'})
        col += len(part) + 1

    # The threshold stone: a single ◆ on the spine cell of the gate row.
    # Fixed text, load-bearing — its EXISTENCE is the mechanism: it is the
    # gate row's first non-blank, so G (and any linewise park) lands at the
    # head of the row, west of the bolts; only $ (or walking) rides the
    # opened gate east past the transit cell.
    runs.append({'row': _GMS_GATE, 'col': _GMS_SPINE, 'symbols': '◆',
                 'kind': 'ancient'})

    # The Grandmaster watches from the gate pocket. edit_immune: he anchors
    # the gate row against dG, and he is not to be killed through a wall.
    ent.append({'kind': 'warden', 'at': [_GMS_WATCH[0], _GMS_WATCH[1]],
                'hp': 5, 'max_hp': 5, 'ai': '', 'tag': 'grandmaster',
                'edit_immune': True})

    # The seven bolts + final seal, said as data. Six text bolts read their
    # bay's computed target anywhere on any row (raw strip equality — the
    # double-space hole diw leaves must NOT collapse, or daw would read true
    # too). The seventh is the legion bolt: a mode='gone' seal naming the
    # goblin kind, open only while no live goblin draws breath. All ride the
    # gate row via anchor='exit_row' so the paragraph bay's collapse cannot
    # strand them.
    seals = []
    for bay_i, (_text, target) in enumerate(specs):
        seals.append(Seal(match=(target,), scope='anyrow', mode='exact',
                          anchor='exit_row',
                          opens=((_GMS_GATE, _GMS_BOLTS[bay_i]),),
                          message=_GMS_APPRAISALS[bay_i]))
    seals.append(Seal(mode='gone', match=('goblin',), anchor='exit_row',
                      opens=((_GMS_GATE, _GMS_BOLTS[6]),),
                      message=_GMS_APPRAISALS[6]))
    seals.append(Seal(anchor='exit_row', requires=tuple(range(7)),
                      opens=((_GMS_GATE, _GMS_SEAL),),
                      message=_GMS_FINAL_LINE))

    gallery_level = _Level(
        name="The Grandmaster's Sanctum", seed=seed,
        rows=R, cols=C,
        cells=[''.join(_CELL_CODE[c] for c in row) for row in grid],
        spawn=(1, _GMS_SPINE), exit=_GMS_TRANSIT,   # NO exit entity: stepping here descends
        char_runs=runs, entities=ent, seals=seals,
        solution=("2j w w diw 2j ci\" {words['q_cure']}<Esc> 2j da[ "
                  "2j cis {words['s_cure']}.<Esc> 2j dit 2j ci{{ {words['b_cure']}<Esc> "
                  "2j dap $"))

    dungeon = _fmt_build(gallery_level)
    gallery = dungeon.rooms[0]
    # NO exit entity on the gallery: the transit cell is a stair, not a door —
    # stepping here descends. build() gives the derived marker to the last
    # room alone, but this room is built as its OWN one-room level (the two
    # are stitched below), so the strip stays honest here.
    gallery.entities = [e for e in gallery.entities if e.kind != 'exit']
    # The driven canonical (see tests): the ops chain bay to bay straight
    # down; the dap's linewise park leaves the cursor at the head of the
    # gate row, and $ rides the opened gate east past the transit cell —
    # the natural stroke from the bottom of the hall (G also works, but
    # the player is already on the last line).
    gallery.answer = (f"2j w w diw 2j ci\" {words['q_cure']}<Esc> 2j da[ "
                      f"2j cis {words['s_cure']}.<Esc> 2j dit 2j ci{{ {words['b_cure']}<Esc> "
                      f"2j dap $")
    gallery._gms_words = words
    gallery.par    = None
    gallery.budget = _GMS_BUDGET

    # ── Room 1: The Unmaking (the arena) ─────────────────────────────────────
    AR, AC = _GMS_A_ROWS, _GMS_A_COLS
    agrid = [[CellType.WALL] * AC for _ in range(AR)]
    for r in range(1, AR - 1):
        for c in range(1, _GMS_A_SEAL_COL):              # the open hall
            agrid[r][c] = CellType.FLOOR
    for r in range(1, AR - 1):                           # the sanctum pocket,
        for c in range(_GMS_A_SEAL_COL + 1, AC - 1):     # walled off by the seal
            agrid[r][c] = CellType.FLOOR
    # the seal column is WALL top to bottom (opens at 0 HP); punch the throat
    # so the pocket is a real room behind it, reachable only when he is unmade.

    aruns: list = []
    lecterns = []
    scratch = Room(room_type=RoomType.ENTRY, rows=AR, cols=AC)
    scratch.cells     = agrid
    scratch.char_runs = []
    for r, c, text, obj, cur, gone, keep in _GMS_A_LECTERNS:
        _forge_text(scratch, r, c, text, 'ember')        # ember = corrupt/bound
        # the guard cell: two east of the strand's tail, so the Grandmaster
        # recoils AWAY from the player's approach without ever sitting on the
        # text he protects (the player must reach the structure to shear it).
        lecterns.append({'row': r, 'col': c, 'obj': obj, 'cursor': (r, cur),
                         'gone': gone, 'keep': keep,
                         'guard': (r, min(_GMS_A_SEAL_COL - 1, c + len(text) + 1))})
    aruns += [{'row': ru.row, 'col': ru.col, 'symbols': ''.join(ru.symbols),
               'kind': ru.kind} for ru in scratch.char_runs]

    arena_level = _Level(
        name='The Unmaking', seed=seed,
        rows=AR, cols=AC,
        cells=[''.join(_CELL_CODE[c] for c in row) for row in agrid],
        spawn=_GMS_A_SPAWN, exit=_GMS_A_EXIT,
        char_runs=aruns,
        entities=[
            {'kind': 'warden', 'at': [_GMS_A_BOSS[0], _GMS_A_BOSS[1]],
             'hp': 6, 'max_hp': 6, 'ai': '', 'tag': 'grandmaster',
             'edit_immune': True},
            {'kind': 'exit', 'at': [_GMS_A_EXIT[0], _GMS_A_EXIT[1]]},
            {'kind': 'heart_container',
             'at': [_GMS_A_HEART[0], _GMS_A_HEART[1]]},
            {'kind': 'chest_scroll',
             'at': [_GMS_A_CHEST[0], _GMS_A_CHEST[1]]},
        ])

    arena_room = _fmt_build(arena_level).rooms[0]
    arena_room.room_type = RoomType.BOSS
    arena_room._gm_lecterns = lecterns
    arena_room._gm_seal_col = _GMS_A_SEAL_COL
    arena_room.search_glyph_entities = True   # /W finds the Grandmaster — the
                                              # Pathfinder/Manifold search parity
    arena_room.par    = None
    arena_room.budget = _GMS_A_BUDGET         # very large — the chase is unsequenced
    arena_room.answer = ''                    # no karaoke: the fight has no fixed route

    dungeon.rooms        = [gallery, arena_room]
    dungeon.current_room = 0
    return dungeon


# ── The Hall of Echoes (47: q @ " — the macro gauntlet) ──────────────────────
#
# ONE poem hall, then ONE tall gauntlet MAP of
# replica chambers stacked south (nothing wipes — the whole descent stays
# on screen, the viewport scrolls). Every chamber is the EXACT puzzle from
# its source level (same pick functions, texts, columns), and sources are
# chosen ONLY where the level's own tape repeats a 2+-char string — see
# _he_build_chambers. Chambers are runs of text rows split by stone bands;
# each band carries a west gate that grinds open when its chamber reads
# true (sight floods through — the next chamber lights as you finish the
# one above). The exit sits in the last band and needs EVERY chamber
# true. One fresh register per chamber (qa poem, then qb qc qd — the
# named-register drill). Replayed keys are budget-free (Budget.frozen);
# the all-manual road wins, at 1★ under the hand-set budget (forcing by
# PAR).
_HE_COLS  = 58
_HE_TX    = 3                          # text head col in every hall
_HE_GATE_COL = 2                       # the west gate cell in every band
_HE_PAR    = 74                        # engine-measured: the full driven tape
_HE_BUDGET = math.ceil(_HE_PAR * 1.4)  # STANDARD (par-is-the-optimum law)

# The poem pool — all PD, all 10 lines. The intruders are deadpan one-word
# asides (the Norm law: understatement over punchline), one per line, all
# prepended at word position 1 so `daw` at the head is the uniform mend.
_HE_POEMS = (
    ('solomon grundy',
     ('Solomon Grundy,', 'Born on a Monday,', 'Christened on Tuesday,',
      'Married on Wednesday,', 'Took ill on Thursday,', 'Worse on Friday,',
      'Died on Saturday,', 'Buried on Sunday.', 'This is the end',
      'Of Solomon Grundy.'),
     ('Allegedly', 'Regrettably', 'Somehow', 'Foolishly', 'Conveniently',
      'Predictably', 'Eventually', 'Reluctantly', 'Frankly', 'Anyway')),
    ('hush little baby',
     ("Hush little baby, don't say a word,",
      "Papa's gonna buy you a mockingbird.",
      "And if that mockingbird won't sing,",
      "Papa's gonna buy you a diamond ring.",
      'And if that diamond ring turns to brass,',
      "Papa's gonna buy you a looking glass.",
      'And if that looking glass gets broke,',
      "Papa's gonna buy you a billy goat.",
      "And if that billy goat won't pull,",
      "Papa's gonna buy you a cart and bull."),
     ('Please', 'Allegedly', 'Realistically', 'Reluctantly', 'Tragically',
      'Regardless', 'Eventually', 'Predictably', 'Ultimately', 'Somehow')),
    ('ding dong bell',
     ('Ding, dong, bell,', "Pussy's in the well.", 'Who put her in?',
      'Little Johnny Flynn.', 'Who pulled her out?', 'Little Tommy Stout.',
      'What a naughty boy was that,', 'To try to drown poor pussy cat,',
      'Who never did him any harm,',
      "But killed all the mice in the farmer's barn."),
     ('Suddenly', 'Apparently', 'Honestly', 'Obviously', 'Miraculously',
      'Naturally', 'Objectively', 'Sadly', 'Importantly', 'Also')),
    ('three little kittens',
     ('Three little kittens,', 'They lost their mittens,',
      'And they began to cry,', 'Oh, mother dear,', 'We sadly fear,',
      'Our mittens we have lost.', 'What! Lost your mittens,',
      'You naughty kittens!', 'Then you shall have no pie.',
      'Mee-ow, mee-ow, mee-ow.'),
     ('Statistically', 'Carelessly', 'Understandably', 'Anyway', 'Frankly',
      'Presumably', 'Wow', 'Historically', 'Legally', 'Finally')),
    ('one two buckle my shoe',
     ('One, two, buckle my shoe;', 'Three, four, knock at the door;',
      'Five, six, pick up sticks;', 'Seven, eight, lay them straight;',
      'Nine, ten, a big fat hen;', 'Eleven, twelve, dig and delve;',
      'Thirteen, fourteen, maids a-courting;',
      'Fifteen, sixteen, maids in the kitchen;',
      'Seventeen, eighteen, maids in waiting;',
      'Nineteen, twenty, my plate is empty.'),
     ('Roughly', 'Impressively', 'Gingerly', 'Meticulously', 'Somehow',
      'Tediously', 'Scandalously', 'Efficiently', 'Inexplicably',
      'Mercifully')),
)

# The gauntlet chambers: each chamber is the
# EXACT puzzle from its source level — same generators, same texts, same
# columns — chosen ONLY from levels whose own karaoke tape repeats a
# 2+-character string (the macro-worthiness criterion). Four levels qualify:
#   the Echo Vault      — 'w w .' beats down one warped corridor
#   the Selection Halls — 'k vbp' three times around the panel cycle
#   the Refrain Vault   — 'p 3j' laying the refrain under each stanza
#   the Goblin Gauntlet — '; x' felling a lair of goblins one by one (combat)
# A level does NOT qualify merely because uniform variants could be invented
# for it: the repeat must already be in its own tape. Every chamber solves on a fresh register
# (qb, qc, qd, qe after the poem hall's qa — the named-register drill).
_HE_WARP = '♄'                          # kept: relic name used by older saves/tests
_HE_GOB_C0, _HE_GOB_GAP, _HE_GOB_N = 10, 4, 6   # goblin lair: 6 foes, spaced 4


def _he_build_chambers(rng):
    """The three replica chambers, drawn with the SOURCE levels' own pick
    functions so each wears exactly its original face. Returns a list of
    (rows, done, floor_span, tape) where rows = ((col, text, kind), ...)
    per text row, done = the run's true floor texts (strip-exact), and
    tape = the chamber's answer segment (recording first wherever the
    puzzle's own shape allows)."""
    chambers = []

    # ── the Echo Vault, verbatim: the sealed plaque band + the lock row ──
    (p1, l1), (p2, l2), (w4, w3, digit) = _ev_pick_combo(rng)
    g1, g2, g3 = rng.sample(_CC_WARP_GLYPHS, 3)
    p3 = f'{w4} {digit} {w3} {digit * 3}'

    def _warp(phrase, offsets, glyph):
        out = list(phrase)
        for i in offsets:
            out[i] = glyph
        return ''.join(out)

    segs = ((_EV_SEG1_COL, p1, _warp(p1, _EV_WARPS1, g1)),
            (_EV_SEG2_COL, p2, _warp(p2, _EV_WARPS2, g2)),
            (_EV_SEG3_COL, p3, _warp(p3, (_EV_WARP3_SINGLE, *_EV_WARP3_TRIPLE), g3)))
    ev_done = ''
    for col, true, _lock in segs:
        ev_done = ev_done.ljust(col) + true
    ev_rows = (tuple((col, lock, 'ancient') for col, _t, lock in segs),)
    ev_plaques = tuple((col, true, 'verdant') for col, true, _l in segs)
    # Record the walk WITH the mend (qb w w re): each replay hops to the
    # next warp and mends it — the mend-merge law keeps the hop uniform.
    # Then the vault's own lessons close it out: ru + . and r{d} + 3.
    ev_tape = (f'qbwwr{l1}q 3@b wwr{l2} ww. wwr{digit} ww3. 0 2j')
    chambers.append({'rows': ev_rows, 'done': (ev_done.strip(),),
                     'span': (2, 56), 'plaques': ev_plaques, 'tape': ev_tape})

    # ── the Selection Halls' panel cycle, verbatim: four PROVERBS whose
    #    ENDINGS are rotated one frame down (each row reads a known saying with
    #    the wrong last word). Yank one ending, and every visual paste hands
    #    the register the next row's ending — the swap rotates them home. The
    #    reach is column-independent ($b → the last word), so the macro is
    #    k$bvep no matter how the proverbs line up. ──
    words = _sh_draw_words(rng)
    prov = words['proverbs']
    pn_rows, pn_done = [], []
    for i in range(4):
        stem = prov[i][0]
        wrong = prov[(i - 1) % 4][1]
        pn_rows.append(((4, f'{stem} {wrong}', 'ancient'),))
        pn_done.append(f'{stem} {prov[i][1]}')
    # `G` for the hop to the first panel, not `3j`: the halls below sleep under
    # stone fog and a fogged row has no standable cell, so the buffer ends where
    # the light does and `G` is one key to the frontier. Buffer-relative, unlike
    # `L` — the tape means the same thing in every window (2026-08-02).
    pn_tape = '$bvey G $bvep qck$bvepq 2@c 0 5j'
    chambers.append({'rows': tuple(pn_rows), 'done': tuple(pn_done),
                     'span': (2, 44), 'plaques': (), 'tape': pn_tape})

    # ── the Refrain Vault's reprise, verbatim: London Bridge's twelve
    #    verses with the refrain given ONCE, on the shelf above — yank it,
    #    drop three lines, lay it; the echo does the other three ──
    stanzas = tuple(t for t in _RV_TRUE if t != _RV_LADY)
    rv_rows = tuple(((2, ln, 'ancient'),) for ln in (_RV_LADY,) + stanzas)
    rv_done = (_RV_LADY,) + _RV_TRUE
    rv_tape = 'qdyy3jpq 3@d G'                    # ↓ into the goblin lair (G: see above)
    # (linewise p lands the cursor at col 0 already — no 0 needed)
    chambers.append({'rows': rv_rows, 'done': rv_done,
                     'span': (2, 55), 'plaques': (), 'tape': rv_tape})

    # ── the Goblin Gauntlet, verbatim: a row of goblins felled by ;x. `fg`
    #    sets last_f='g' and kills the first; the repeated `;x` (find the
    #    next 'g', strike) is the macro unit. A west 'lair' label (no 'g')
    #    keeps the row a recognised run once the lair is cleared. ──
    gob_cols = tuple(range(_HE_GOB_C0, _HE_GOB_C0 + _HE_GOB_N * _HE_GOB_GAP, _HE_GOB_GAP))
    #    GOLFED: record the FIND ITSELF, not the `;` that
    #    repeats it — `qg fgx q` makes the whole strike the macro unit, so the
    #    first kill is inside the recording instead of paid for separately. And
    #    `G` lands the descent on the exit band for one key where `0 j` took two.
    gob_tape = f'qe fgx q {_HE_GOB_N - 1}@e G'
    chambers.append({'rows': (((_HE_TX, 'lair', 'ancient'),),),
                     'done': ('lair',), 'span': (2, _HE_GOB_C0 + _HE_GOB_N * _HE_GOB_GAP),
                     'plaques': (), 'goblins': gob_cols, 'combat': True,
                     'tape': gob_tape})
    return chambers


def _he_poem_chamber(poem) -> dict:
    """The poem hall as the TOP run of the ONE gauntlet map: ten corrupted
    lines, each with a one-word intruder at the head (daw mends it). Recorded
    on register a, then replayed down the run; the run's south band grinds
    open onto the first replica chamber (the descent never leaves the map)."""
    _name, lines, intr = poem
    rows = tuple(((_HE_TX, f'{intr[t]} {lines[t]}', 'ancient'),) for t in range(10))
    return {'rows': rows, 'done': tuple(lines), 'span': (2, _HE_COLS - 3),
            'plaques': (), 'tape': 'qa daw j q 9@a 0 2j', 'poem': _name}


def _he_gauntlet_map(chambers, seed) -> 'Dungeon':
    """The replica chambers on ONE tall map (the viewport scrolls): runs of
    text rows split by stone bands, a west gate in each band that grinds
    open as its chamber reads true (sight floods down to the next), and the
    exit in the last band, demanding EVERY chamber true. The poem hall is the
    first run (top of the map); a chamber's plaques (the Echo Vault's true
    readings) sit wall-embedded in the stone band directly above its run."""
    from vimny.engine.editor import _CELL_CODE
    from vimny.sharing.format import Level as _Level, build as _fmt_build
    chain = tuple((ch['done'], None, ch.get('combat', False)) for ch in chambers)
    ROWS = 2 + sum(len(ch['rows']) for ch in chambers) + len(chambers)
    C = _HE_COLS
    grid = [[CellType.WALL] * C for _ in range(ROWS)]
    runs: list = []
    ents: list = []
    r = 2                                           # 0 border, 1 first band
    for ch in chambers:
        lo, hi = ch['span']
        start = r
        last_row = r
        for row in ch['rows']:
            for c in range(lo, hi + 1):
                grid[r][c] = CellType.FLOOR
            for col, text, kind in row:
                for piece_col, piece in _he_pieces(col, text):
                    runs.append({'row': r, 'col': piece_col, 'symbols': piece,
                                 'kind': kind})
            last_row = r
            r += 1
        for gc in ch.get('goblins', ()):            # the lair's stationary foes
            ents.append({'kind': 'goblin', 'at': [last_row, gc],
                         'hp': 1, 'max_hp': 1, 'ai': ''})
        # a chamber's plaques: the true readings, sealed in the stone band
        # above its run (wall cells — uncuttable, off the floor scans).
        for col, text, kind in ch.get('plaques', ()):
            for piece_col, piece in _he_pieces(col, text):
                runs.append({'row': start - 1, 'col': piece_col,
                             'symbols': piece, 'kind': kind})
        r += 1                                      # the stone band (gate shut)

    level = _Level(
        name='The Hall of Echoes', seed=seed,
        rows=ROWS, cols=C,
        cells=[''.join(_CELL_CODE[c] for c in row) for row in grid],
        spawn=(2, _HE_TX),                          # the poem run's head
        exit=(ROWS - 1, _HE_GATE_COL),              # in the last band
        char_runs=runs,
        entities=ents + [{'kind': 'exit',
                          'at': [ROWS - 1, _HE_GATE_COL], 'edit_immune': True}])

    dungeon = _fmt_build(level)
    room = dungeon.rooms[0]
    room._heg_chain = chain
    room._he_poem  = chambers[0].get('poem')        # the poem hall's rhyme name
    room.answer = ' '.join(ch['tape'] for ch in chambers)
    return dungeon


def _he_pieces(col, text):
    """Split `text` into (col, word) pieces at spaces (separate runs with
    bare gaps, the engine's word-class law)."""
    out, c = [], col
    for piece in text.split(' '):
        if piece:
            out.append((c, piece))
        c += len(piece) + 1
    return out


def build_dungeon_hall_of_echoes(seed: int) -> Dungeon:
    """The Hall of Echoes (slug `hall_of_echoes`): q @ " — record the mend
    once, and let the echo do the rest, hall after hall."""
    rng = random.Random(seed)
    poem = _HE_POEMS[rng.randrange(len(_HE_POEMS))]
    # the poem hall is the FIRST run of ONE tall map — the descent never
    # leaves it (rooms 2+ must continue the same map, not a new one)
    chambers = [_he_poem_chamber(poem)] + _he_build_chambers(rng)
    dungeon = _he_gauntlet_map(chambers, seed)
    room = dungeon.rooms[0]
    room.par    = _HE_PAR
    room.budget = math.ceil(_HE_PAR * 1.4)   # STANDARD (par-is-the-optimum law)
    return dungeon


# ── The Stair Rail (40: + - _ and NORMAL-Enter) ──────────────────────────────
#
# A VALLEY of five steps, the player spawning on the MIDDLE one. Each step
# row carries one fused word (◆word — strike the ◆, the exact-text bolt
# reads the word true) at its own column, with blank floor to its west; the
# columns ZIGZAG, so a plain j/k from one mended word lands on bare floor
# beside the next — the j/k-walker pays a trailing ^ where +/- land on the
# word in one reach. The two steps ABOVE the spawn force `-` (up to the
# first non-blank), the two BELOW force `+`; neither can be skipped, since
# every step is its own bolt. Below the valley the gate row runs WEST into
# solid stone: each mended word CARVES the next cell of a corridor through
# the stone toward the sealed exit (lone wall cells inside the valley floor
# would read as random floor when opened, not as a path being cut). With every step mended the corridor
# meets the seal, the seal parts, and the gate row's first-non-blank
# becomes the exit itself — so the final {n}+ lands straight on it; a bare
# undercroft beneath means G undershoots, and a plain {n}j lands beside
# the landing and still owes a ^.
#
# `_` cannot be UNIQUELY
# forced — `{n}_` is exactly `{n-1}+`, and `_` alone is `^` — so the tape
# takes the `+` (house style: showing `_` where `+` ties just confuses); `_`
# is taught by name in the poem/hint bar as the synonym it is. What IS
# strictly forced here is `-` (and `+`).
_SR_ROWS, _SR_COLS = 26, 54
_SR_PLQ_COL = 2
_SR_WEST    = 22                      # blank floor's west edge (so ^/-/+/_ have work)
_SR_EAST    = 46
# The valley sits LOW so every step's absolute line number is TWO digits: a
# relative {n}+ / {n}- (1-digit count) beats the absolute {nn}G that would
# otherwise tie it (both land on the first non-blank). Relative distances
# stay one digit — that gap is the whole forcing.
_SR_STEP_ROWS = (12, 14, 16, 18, 20)  # S1..S5; the player spawns on S3 (the middle)
_SR_STEP_COLS = (24, 32, 26, 34, 26)  # zigzag — vertical neighbours never align
_SR_SPAWN_IDX = 2                     # index into the two tuples above (row 16)
_SR_GATE    = 24
_SR_EXIT    = (24, 16)                # the FINAL SEAL, in the stone west of the valley
# The corridor cells between the valley's west edge and the seal, all stone
# until carved. Each step's mend floors ITS cell; the assignment follows
# the canonical mend order (S3 S2 S1 S4 S5), so the driven route carves
# east→west, one clean cut deeper per word — the grinding IS the path.
_SR_BOLT_COLS = (21, 20, 19, 18, 17)  # cols, in canonical mend order
_SR_UNDERCROFT = 25                   # bare row — G undershoots the gate to here
_SR_CHEST   = (25, 34)                # unassigned scroll chest → the relic pool
_SR_PAR     = 14                      # x 2- x H x 6+ x 2+ x 4+ ({n}_ only ever
                                      # TIES {n-1}+ — the tape takes the +)
#: The SECOND `2-` is `H`. Climbing to the topmost line of the screen is one key
#: where counting back two is two, and it held at every terminal height from 25
#: to 60 when measured — `H` is viewport-relative in a 26-row room, so that
#: measurement is what licenses it, not the reasoning (2026-08-03). Both `+` and
#: `-` are still pressed, so the rail still teaches the rail.


def _sr_draw_words(rng) -> tuple:
    """Five distinct step words (each is its own bolt's target)."""
    _load_vocab_tables()
    pool = [w for w in _VOCAB_PLAIN_BY_LEN.get(3, ())
            if w.isalpha() and w == w.lower()]
    for _ in range(80):
        words = tuple(rng.choice(pool) for _ in range(5))
        if len(set(words)) == 5:
            return words
    raise ValueError('stair_rail: no distinct draw after 80 tries')


def build_dungeon_stair_rail(seed: int) -> Dungeon:
    """The Stair Rail (slug `stair_rail`): + - _ — climb and drop, landing
    on the word, not beside it."""
    from vimny.engine.editor import _CELL_CODE
    from vimny.sharing.format import Level as _Level, _parse_seal, build as _fmt_build
    rng = random.Random(seed)
    words = _sr_draw_words(rng)

    R, C = _SR_ROWS, _SR_COLS
    grid = [[CellType.WALL] * C for _ in range(R)]
    # the whole shaft is contiguous floor (rows 2..17) so -/+ can traverse
    # the blank rows between steps; the steps' words sit on rows 2,4,6,8,10.
    for r in range(_SR_STEP_ROWS[0], _SR_UNDERCROFT + 1):
        for c in range(_SR_WEST, _SR_EAST):
            grid[r][c] = CellType.FLOOR
    # The corridor cells (_SR_BOLT_COLS) and the seal are west of the valley
    # and already stone — each mend carves its cell; the tick floors them.

    runs = []
    seals = []
    mend_order = (2, 1, 0, 3, 4)          # S3 (spawn) → S2 → S1 → S4 → S5
    for k, r in enumerate(_SR_STEP_ROWS):
        col = _SR_STEP_COLS[k]
        runs.append({'row': r, 'col': col, 'symbols': '◆' + words[k],
                     'kind': 'ember'})
        runs.append({'row': r, 'col': _SR_PLQ_COL, 'symbols': words[k],
                     'kind': 'verdant'})
        # each mended step carves its own corridor cell, east→west along
        # the canonical route (any other order carves the same passage)
        seals.append(_parse_seal({
            'scope': 'anyrow', 'mode': 'exact', 'anchor': 'exit_row',
            'match': [words[k]],
            'opens': [[_SR_EXIT[0], _SR_BOLT_COLS[mend_order.index(k)]]],
        }, k))
    seals.append(_parse_seal({
        'anchor': 'exit_row',
        'requires': list(range(len(seals))),
        'opens': [list(_SR_EXIT)],
    }, len(seals)))

    level = _Level(
        name='The Stair Rail', seed=seed,
        rows=R, cols=C,
        cells=[''.join(_CELL_CODE[c] for c in row) for row in grid],
        spawn=(_SR_STEP_ROWS[_SR_SPAWN_IDX], _SR_STEP_COLS[_SR_SPAWN_IDX]),
        exit=_SR_EXIT,
        char_runs=runs, seals=seals,
        entities=[{'kind': 'exit', 'at': [_SR_EXIT[0], _SR_EXIT[1]],
                   'edit_immune': True},
                  # chest_SCROLL, not chest_random: the reward here is a relic scroll (an
                  # unassigned scroll chest draws from the relic pool), and a random chest
                  # rolled that intent away four times in five.
                  {'kind': 'chest_scroll',
                   'at': [_SR_CHEST[0], _SR_CHEST[1]]}],
        solution='x 2- x H x 6+ x 2+ x 4+')

    dungeon = _fmt_build(level, par=_SR_PAR)   # STANDARD: the k^/j^-walk wins at 1★
    _seal_banners(dungeon)
    dungeon.rooms[0]._sr_words = words
    return dungeon


# ── The Last Reach (41: the g-family — g_ forced; g* g# gi gp gP granted) ────
#
# Three long verse rows, each running east into WATER: $ overshoots the
# text onto the flood (the $-drown trap, the Inscription Halls' law) while
# g_ lands the last GLYPH — water carries no characters, so the caret-stop
# scan sails past it. The rows are 10–12 words long, so a counted
# word-end walk pays two digits ({n}e = 3 keys) where g_ pays 2, and the
# rows are UNEQUAL so no count is reusable blind. + (taught one level
# back) chains row to row.
#
# The last GLYPH is a CORRUPTION: the tail word's final letter is wrong.
# g_ lands on it and r{letter} mends it. SENSE, NOT DECREE (no plaque):
# the three verses are FAMOUS SAYINGS, so the
# true last word — and its last letter — is known by heart; the rest of
# the saying is the (long) navigation. The door reads the true tail word
# as a substring. Corrupt spellings are fixed non-words (curz/busj/boq),
# chosen so no r-candidate but the true letter makes an English word. The
# rest of the family (g* g# gi gp gP) rides the same g_family token as
# taught conveniences — their honest par-forcing collapses to ties.
_GS_ROWS, _GS_COLS = 10, 78
_GS_SPINE  = 22
_GS_BAYS   = (2, 3, 4, 5, 6)          # adjacent — + chains them
# A FIVE-LINE poem: two SHORT sayings are inset between
# the three long ones, LEFT-ALIGNED, so the corrupt tails alternate far east
# (long, ~col 66-70) and near west (short, ~col 40-41). Every adjacent pair of
# tails is now > 20 columns apart, so a `j` then h/l walk to the next tail
# costs FAR more than g_'s two flat keys — no more `j h` cheat between stacked
# tails. The long verses stay 10+ words (the {n}e count-defense pays two digits
# there); the short verses lean on the column spread. Widths end shy of the
# flood (col 72), which still drowns any `$` overshoot.
_GS_VERSES = (
    ('an ounce of prevention is worth a pound of cure', 'curz'),   # 10w, tail @ col 70
    ('haste makes waste',                              'wastz'),   #  3w, tail @ col 40
    ('a bird in the hand is worth two in the bush',     'busj'),   # 11w, tail @ col 66
    ('knowledge is power',                             'powez'),   #  3w, tail @ col 41
    ('all work and no play makes jack a dull boy',      'boq'),    # 10w, tail @ col 65
)
_GS_NWORDS = tuple(len(v.split()) for v, _c in _GS_VERSES)
_GS_TEXT0  = 24
_GS_POOL   = (72, 73)                 # the flood: $ lands here and drowns
_GS_THROAT = 7                        # spine-only row joins the bays to the gate
_GS_GATE   = 8
# The exit and its per-verse bolts sit at the WEST end (no need for the exit
# way out east). The player mends the tails (east), then walks the
# gate row back WEST through the bolts to the seal at column 0.
_GS_BOLTS  = {2: 5, 3: 4, 4: 3, 5: 2, 6: 1}
_GS_EXIT   = (8, 0)                   # the FINAL SEAL, WEST of every bolt
_GS_PAR    = 26                       # j g_ r{f} (+ g_ r{f})×4 G 0  (measured)


def _gs_words() -> dict:
    """The three fixed sayings, split for laying: rows (word tuples), true
    tails, corrupt spellings, and the letters r must type."""
    rows = [tuple(v.split()) for v, _c in _GS_VERSES]
    tails = [r[-1] for r in rows]
    corrupts = [c for _v, c in _GS_VERSES]
    fixes = [t[-1] for t in tails]
    return {'rows': rows, 'tails': tails, 'corrupts': corrupts, 'fixes': fixes}


def build_dungeon_g_sanctum(seed: int) -> Dungeon:
    """The Last Reach (slug `g_sanctum`): the g-family — the last glyph,
    named in one reach."""
    from vimny.engine.editor import _CELL_CODE
    from vimny.sharing.format import Level as _Level, _parse_seal, build as _fmt_build
    words = _gs_words()

    R, C = _GS_ROWS, _GS_COLS
    grid = [[CellType.WALL] * C for _ in range(R)]
    for r in range(1, _GS_GATE + 1):                     # the spine
        grid[r][_GS_SPINE] = CellType.FLOOR
    for r in _GS_BAYS:                                   # the verse rows
        for c in range(_GS_SPINE, _GS_POOL[1] + 1):
            grid[r][c] = CellType.FLOOR
        for c in _GS_POOL:                               # the flood at the brink
            grid[r][c] = CellType.WATER
    # The gate row runs from the spine WEST to the seal at column 0; the bolts
    # sit between them (one per verse), and the exit (col 0) is the final seal.
    for c in range(0, _GS_SPINE + 1):
        grid[_GS_GATE][c] = CellType.FLOOR
    for dc in _GS_BOLTS.values():
        grid[_GS_GATE][dc] = CellType.WALL
    grid[_GS_EXIT[0]][_GS_EXIT[1]] = CellType.WALL      # the final seal (chassis-standard)

    runs = []
    seals = []
    for i, r in enumerate(_GS_BAYS):
        verse = words['rows'][i]
        col = _GS_TEXT0                                  # LEFT-ALIGNED (no indent)
        for k, part in enumerate(verse):
            # the last word wears its CORRUPT spelling (last letter wrong);
            # g_ lands on that letter and r{fix} mends it.
            text = words['corrupts'][i] if k == len(verse) - 1 else part
            runs.append({'row': r, 'col': col, 'symbols': text,
                         'kind': 'ancient'})
            col += len(part) + 1
        # No plaque: the saying is known by heart — the true tail (and its
        # last letter) IS the memory. Substring door on the true tail.
        seals.append(_parse_seal({
            'scope': 'anyrow', 'mode': 'contains', 'anchor': 'exit_row',
            'match': [words['tails'][i]],
            'opens': [[_GS_GATE, _GS_BOLTS[r]]],
        }, i))
    seals.append(_parse_seal({
        'anchor': 'exit_row',
        'requires': list(range(len(seals))),
        'opens': [list(_GS_EXIT)],
    }, len(seals)))

    f = words['fixes']
    level = _Level(
        name='The Last Reach', seed=seed,
        rows=R, cols=C,
        cells=[''.join(_CELL_CODE[c] for c in row) for row in grid],
        spawn=(1, _GS_SPINE), exit=_GS_EXIT,
        char_runs=runs, seals=seals,
        entities=[{'kind': 'exit', 'at': [_GS_EXIT[0], _GS_EXIT[1]],
                   'edit_immune': True}],
        # g_ reaches each tail (east), r mends; the FIRST verse is reached by j, the
        # rest by + (down to the next head). After the last mend every bolt is open,
        # so G drops to the gate row and lands on its first standable cell — the
        # seal at column 0 — winning in one key.
        solution=' '.join([f'j g_ r{f[0]}'] + [f'+ g_ r{fx}' for fx in f[1:]]) + ' G')

    dungeon = _fmt_build(level, par=_GS_PAR)   # STANDARD: the counted-e walk wins at 1★
    _seal_banners(dungeon,
                  bolt='The label reads true — the bolt grinds back!',
                  final='Every label reads true — the final seal parts!')
    dungeon.rooms[0]._gs_words = words
    return dungeon


# ── The Buried Word (42, bonus: g* and the n-chain) ──────────────────────────
#
# One standing word — the player spawns ON it (e.g. `set`) — and three
# echoes of it BURIED inside REAL longer words down the hall (`reset`,
# `onset`, `upset`). * (whole-word) finds nothing: the word never stands
# alone below the ledge. g* takes it literally and walks the chain; n
# carries on. Each real word has ONE corrupt letter — the cell just before
# the buried word — so g* still finds it; h steps onto the corruption and
# r{fix} mends it. NO PLAQUE: the draw demands that
# EXACTLY ONE letter completes the corrupt spelling into a real vocab word
# — the mend is inferable from the word itself (the game vocab is the
# dictionary; hosts stay randomized from it). The /typed-search rival
# costs a few keys more — that margin is the whole game.
# (Hosts are real words that CONTAIN the target — the true g* use case —
# never nonsense {pre}{word}{post} concatenations.)
_BW_ROWS, _BW_COLS = 8, 54
_BW_SPINE   = 22
_BW_PLQ_COL = 2
_BW_STAND   = (1, 24)                 # the standing word — spawn is ON it
_BW_BAYS    = (2, 3, 4)
_BW_TEXT0   = 24
_BW_THROAT  = 5
_BW_GATE    = 6
_BW_BOLTS   = {2: 23, 3: 24, 4: 25}
_BW_EXIT    = (6, 26)                 # the FINAL SEAL, east of every bolt
_BW_PAR     = 19                      # 2l (walk onto 'one') g* h r{f} l n ×3 G $
_BW_STANDING = 'one'                  # the word that stands alone at the mouth
# A little VERSE (single words stacked at one column would let `j r x` beat
# the hunt). The target 'one' is buried in a real word on each
# line, and the lines are STAGGERED so the buried words fall at DIFFERENT
# columns — g*/n hunts them; manual j/h nav would cost more. The reader mends
# each by the verse's sense (no plaque; the rhyme names the word).
_BW_VERSE = (   # (bay_row, col, true_line, host — the host holds the buried 'one')
    (2, _BW_TEXT0,       'alone he stood,',     'alone'),
    (3, _BW_TEXT0 + 5,   'upon his throne,',    'throne'),
    (4, _BW_TEXT0 + 10,  'as cold as stone.',   'stone'),
)


def _bw_verse_data() -> dict:
    """The fixed verse as (hosts, corrupt lines, fix chars, rows, cols). Each
    host's corrupt cell is the one just BEFORE the buried 'one', so g* still
    finds the target and h steps onto the corruption; r{fix} mends it."""
    hosts, corr_lines, fixes, rows, cols = [], [], [], [], []
    for bay, col, line, host in _BW_VERSE:
        hidx = line.index(host)
        oidx = host.index(_BW_STANDING)            # 'one' within the host
        cell = hidx + oidx - 1                      # the cell before 'one' (line coords)
        correct = line[cell]
        wrong = 'x' if correct != 'x' else 'z'
        hosts.append(host)
        corr_lines.append(line[:cell] + wrong + line[cell + 1:])
        fixes.append(correct)
        rows.append(bay)
        cols.append(col)
    return {'word': _BW_STANDING, 'hosts': hosts, 'corrupt_lines': corr_lines,
            'fixes': fixes, 'rows': rows, 'cols': cols,
            'true_lines': [l for _b, _c, l, _h in _BW_VERSE]}


def build_dungeon_buried_word(seed: int) -> Dungeon:
    """The Buried Word (slug `buried_word`, bonus): g* — the word hunted
    inside other words."""
    from vimny.engine.editor import _CELL_CODE
    from vimny.sharing.format import Level as _Level, _parse_seal, build as _fmt_build
    words = _bw_verse_data()
    w = words['word']

    R, C = _BW_ROWS, _BW_COLS
    grid = [[CellType.WALL] * C for _ in range(R)]
    for r in range(1, _BW_GATE + 1):                     # the spine
        grid[r][_BW_SPINE] = CellType.FLOOR
    for c in range(_BW_SPINE, 32):                       # the standing ledge
        grid[1][c] = CellType.FLOOR
    for r in _BW_BAYS:                                   # the echo rows
        for c in range(_BW_SPINE, 52):
            grid[r][c] = CellType.FLOOR
    for c in range(_BW_SPINE, _BW_EXIT[1]):              # gate row + bolts
        grid[_BW_GATE][c] = CellType.FLOOR
    for dc in _BW_BOLTS.values():
        grid[_BW_GATE][dc] = CellType.WALL
    # _BW_EXIT itself stays WALL — the final seal (chassis-standard).

    runs = [{'row': _BW_STAND[0], 'col': _BW_STAND[1], 'symbols': w,
             'kind': 'verdant'}]
    seals = []
    for i, r in enumerate(_BW_BAYS):
        host = words['hosts'][i]                          # the true real word
        line = words['corrupt_lines'][i]                  # verse line, host corrupt
        col  = words['cols'][i]                           # STAGGERED — not stacked
        hidx = words['true_lines'][i].index(host)         # host's char offset in the line
        # Lay the line word by word: the word covering the (corrupt) host reads
        # 'ember', the verse's other words 'ancient' — one run each, gaps between.
        off = 0
        for word in line.split(' '):
            if word:
                kind = 'ember' if off <= hidx < off + len(word) else 'ancient'
                runs.append({'row': r, 'col': col + off, 'symbols': word,
                             'kind': kind})
            off += len(word) + 1
        # No plaque: the verse's sense names the true word.
        seals.append(_parse_seal({
            'scope': 'anyrow', 'mode': 'contains', 'anchor': 'exit_row',
            'match': [host],
            'opens': [[_BW_GATE, _BW_BOLTS[r]]],
        }, i))
    seals.append(_parse_seal({
        'anchor': 'exit_row',
        'requires': list(range(len(seals))),
        'opens': [list(_BW_EXIT)],
    }, len(seals)))

    level = _Level(
        name='The Buried Word', seed=seed,
        rows=R, cols=C,
        cells=[''.join(_CELL_CODE[c] for c in row) for row in grid],
        spawn=(_BW_STAND[0], _BW_SPINE), exit=_BW_EXIT,
        char_runs=runs, seals=seals,
        entities=[{'kind': 'exit', 'at': [_BW_EXIT[0], _BW_EXIT[1]],
                   'edit_immune': True}],
        # {n}l walks east onto 'one'; then g* takes it. r mends in place (no shift),
        # so l steps back onto the word before n — else n re-finds THIS line's word
        # (one cell ahead now). g*/n do the hunting across the staggered lines.
        solution=(f'{_BW_STAND[1] - _BW_SPINE}l g* h r{words["fixes"][0]} '
                  f'l n h r{words["fixes"][1]} l n h r{words["fixes"][2]} G $'))

    dungeon = _fmt_build(level, par=_BW_PAR)
    _seal_banners(dungeon,
                  bolt='The label reads true — the bolt grinds back!',
                  final='Every label reads true — the final seal parts!')
    dungeon.rooms[0]._bw_words = words
    return dungeon


# ── The Wet Ink (44, bonus: gi) ──────────────────────────────────────────────
#
# One writing ledge and a plaque bearing only HALF the inscription. The
# second half is carved in an alcove around a bend — stone-hidden, so it
# starts fogged and must be walked to. Write the first half, go read the
# rest, and gi returns the pen to the wet ink (the exact cell INSERT was
# left at, before the Esc retreat) with insert re-entered — two keys where
# the walk back pays four. The halves are fused (no typed space — the
# karaoke law); the door reads the whole word.
_WI_ROWS, _WI_COLS = 8, 54
_WI_SPINE  = 22
_WI_PLQ_COL = 2                       # the inscription's west edge (wall plaque)
_WI_LEDGE  = 2                        # the writing row
_WI_INK0   = 24                       # where the writing begins
_WI_BRZ_ROW = 4                       # the brazier gallery, beneath the plaque
_WI_SOURCE  = (_WI_BRZ_ROW, 4)        # the one flame that never dies
_WI_BRAZIERS = ((_WI_BRZ_ROW, 8), (_WI_BRZ_ROW, 13), (_WI_BRZ_ROW, 18))
_WI_GATE   = 6
_WI_BOLT   = 23
_WI_EXIT   = (6, 24)
_WI_PAR    = 37                       # i{w1} M yl w P gi<Space>{w2} M 2w P
                                  # (was 39: the paste-tick fix opens the fuel
                                  # gate the same turn the quarter is written,
                                  # so each gi return lands on a WARM chain)
                                      # gi<Space>{w3} M 3w P gi<Space>{w4} G $ (pinned)
#: The descent was written `2+` until 2026-08-02, and `M` does it in one key.
#: The gallery is the MIDDLE of this room's five standable rows (ledge 2, spine
#: 3, gallery 4, spine 5, gate 6), so `M` lands on exactly the cell `2+` landed
#: on — the source flame — from anywhere on the ledge, every time. PAR IS THE
#: OPTIMUM: three descents at one key each instead of two is not a nicety, it is
#: the route that exists, so 42 was simply the wrong number.

# SENSE, NOT DECREE (the design law): the inscription is
# a four-word saying the player knows whole — writing the first words, they
# know what the dark plaque quarters must say before the firelight shows
# them. Both pool entries total 14 letters (words ≤ 4, the plaque pitch),
# so the typed cost — and par — is pool-invariant.
_WI_PHRASES = (
    ('live', 'and', 'let', 'live'),
    ('easy', 'come', 'easy', 'go'),
)


def _wi_draw_words(rng) -> tuple:
    """One saying per seed; the quarters are its words."""
    return _WI_PHRASES[rng.randrange(len(_WI_PHRASES))]


def build_dungeon_wet_ink(seed: int) -> Dungeon:
    """The Wet Ink (slug `wet_ink`, bonus): gi — the pen returns to where
    it left the page. One 16-glyph inscription in the ledge's west wall;
    only the first quarter shows. Beneath it, a gallery of cold braziers
    and one standing flame: carry fire (yl … p) to a brazier and its
    firelight reveals the next quarter — but a brazier only takes the
    flame once the quarter BEFORE it is written on the ledge (the fuel
    gate, _wet_ink_tick), so the scribe must leave the page and return
    to it, three times over."""
    from vimny.engine.editor import _CELL_CODE
    from vimny.sharing.format import Level as _Level, _parse_seal, build as _fmt_build
    rng = random.Random(seed)
    ws = _wi_draw_words(rng)
    full = ' '.join(ws)

    R, C = _WI_ROWS, _WI_COLS
    grid = [[CellType.WALL] * C for _ in range(R)]
    for c in range(_WI_SPINE, 47):                       # the writing ledge
        grid[_WI_LEDGE][c] = CellType.FLOOR
    for r in range(_WI_LEDGE, _WI_GATE + 1):             # the spine, down
        grid[r][_WI_SPINE] = CellType.FLOOR
    for c in range(_WI_SOURCE[1], _WI_SPINE):            # the brazier gallery
        grid[_WI_BRZ_ROW][c] = CellType.FLOOR
    for c in range(_WI_SPINE, _WI_EXIT[1]):              # gate row + the bolt
        grid[_WI_GATE][c] = CellType.FLOOR
    grid[_WI_GATE][_WI_BOLT] = CellType.WALL
    # _WI_EXIT itself stays WALL — the final seal.

    # The plaque (west wall of the ledge): the WHOLE inscription, laid at
    # build as one run per quarter (a wall-gap column between them reads
    # as the space); quarters 2-4 are fogged and revealed by firelight.
    runs = [{'row': _WI_LEDGE, 'col': _WI_PLQ_COL + 5 * k, 'symbols': w,
             'kind': 'verdant'} for k, w in enumerate(ws)]
    # The source flame, and embers on every cold brazier.
    runs.append({'row': _WI_SOURCE[0], 'col': _WI_SOURCE[1],
                 'symbols': _QM_FLAME, 'kind': 'flame'})
    for (br, bc) in _WI_BRAZIERS:
        runs.append({'row': br, 'col': bc,
                     'symbols': _QM_EMBERS, 'kind': 'pedestal'})

    seals = [_parse_seal({
        'scope': 'anyrow', 'mode': 'exact', 'anchor': 'exit_row',
        'match': [full],
        'opens': [[_WI_EXIT[0], _WI_BOLT]],
    }, 0)]
    seals.append(_parse_seal({
        'anchor': 'exit_row',
        'requires': list(range(len(seals))),
        'opens': [list(_WI_EXIT)],
    }, len(seals)))

    # THE FULL SONG, said as data: every nonempty stripped line in the
    # workroom must read the true song, in order. Blank rows are skipped;
    # pasted refrain lines are included because they ARE part of the song.
    seals.append(_parse_seal({
        'scope': 'region', 'mode': 'lines',
        'region': [4, 2, _RV_ROWS - 3, C - 4],
        'match': ['my fair lady.'] + list(_RV_TRUE),   # chasm + song = the full page
    }, len(seals)))

    # THE PROGRESSIVE FUEL GATE, said as data: quarter k written makes
    # brazier k pasteable. Each predicate carries `fuels` — one brazier cell
    # its truth permits — and the paste law unions them while true.
    for j in range(1, len(_WI_BRAZIERS) + 1):   # word 4 has no gate — it
                                                # completes the final phrase
        seals.append(_parse_seal({
            'scope': 'anyrow', 'mode': 'contains',
            'match': [' '.join(ws[:j])],
            'fuels': [list(_WI_BRAZIERS[j - 1])],
        }, len(seals)))

    # FIRELIGHT, said as data: brazier k burning lifts the veil on plaque
    # quarter k+1. The `braziers` mode reads the painted flame (glyph braziers
    # — no entities here), and `unveils` is the one-way reveal. The tick keeps
    # only the fuel gate and the embers; the reveal is a bolt now.
    for k, (br, bc) in enumerate(_WI_BRAZIERS, start=1):
        seals.append(_parse_seal({
            'mode': 'braziers',
            'region': [br, bc, br, bc],
            'unveils': [list(cell) for cell in sorted(
                (_WI_LEDGE, _WI_PLQ_COL + 5 * k - 1 + i) for i in range(5))],
        }, len(seals)))

    level = _Level(
        name='The Wet Ink', seed=seed,
        rows=R, cols=C,
        cells=[''.join(_CELL_CODE[c] for c in row) for row in grid],
        braziers=[list(c) for c in
                  ((_WI_SOURCE,) + _WI_BRAZIERS)],
        spawn=(_WI_LEDGE, _WI_INK0), exit=_WI_EXIT,
        char_runs=runs, seals=seals,
        entities=[{'kind': 'exit', 'at': [_WI_EXIT[0], _WI_EXIT[1]],
                   'edit_immune': True}],
        solution=(f'i{ws[0]}<Esc> M yl w P gi<Space>{ws[1]}<Esc> M 2w P '
                  f'gi<Space>{ws[2]}<Esc> M 3w P gi<Space>{ws[3]}<Esc> G $'))

    dungeon = _fmt_build(level, par=_WI_PAR)
    _seal_banners(dungeon)
    room = dungeon.rooms[0]
    # The three firelight bolts get their own banner (the old one-telling
    # line); they sit AFTER the final seal, which is why the generic helper's
    # *bolts/last split cannot reach them.
    from dataclasses import replace as _dc_replace
    _fire = ('The firelight spills up the stone — more of the inscription '
             'wakes.')
    room.seals = tuple(
        _dc_replace(s, message=_fire) if s.unveils else s for s in room.seals)
    room._wi_words = ws
    # The fuel gate starts source-only; _wet_ink_tick widens it as the
    # quarters are written (read by _flame_paste_blocked).
    room._qm_chain = (_WI_SOURCE,)
    room._flame_block_msg = ('The flame gutters out — only a brazier whose '
                             'quarter is written will hold it.')
    # The plaque is read in instalments: quarter k+1 (and the gap before it)
    # stays unreadable until brazier k burns. VEILED, not fogged — the text is
    # carved into WALL cells, which the fog law has nothing to say about, and
    # calling it fog cost this level an exemption from every fog audit for a
    # mechanic that was never about what the eye can reach.
    room._wi_seg_fog = tuple(
        frozenset((_WI_LEDGE, _WI_PLQ_COL + 5 * k - 1 + i) for i in range(5))
        for k in (1, 2, 3))
    room.veiled_cells = set().union(*room._wi_seg_fog)
    return dungeon


# (There is no gp level: the engine gives gp no niche. Ordinary paste
# self-chains at line end, the Beacon flame-fill is insert-plus-tumble, and
# p+l ties gp everywhere else. gp remains a granted convenience.)


# ── The Binder's Reliquary (:h — the Codex) ─────────────────────────────────
#
# A second reliquary (display 14.1, after the Seekers' Labyrinth), on the
# FIRST Reliquary's two-chamber chassis — but the divider is WATER, not
# stone. Water is transparent: the
# binder's pass-word is legible on the far shore. MIST (fog) lies on the
# channel, so every line-scoped scan stops at the bank — $ / 0 / ^ by
# _cross_water's fog check, f/F/t/T by the scan-fog law — while teleports
# (G/H/M/L/{n}G) land on the row's first standable, the NEAR shore. Search
# alone crosses: /{word}<CR> — the Labyrinth's lesson, cashed in. The bound
# Codex waits BEYOND the
# word (chest after crossing, never before), so :h cannot be opened until
# the Codex is actually in hand (the command is gated on the 'readers_key'
# grant, not just the level's 'help' token).
#
# Reward room: par None (reliquaries are unstarred), generous fixed budget.
_BND_ROWS, _BND_COLS = 7, 34
_BND_AR          = 3                  # the action row: spawn, word, chest, exit
_BND_WATER_COLS  = (12, 13)           # full-height channel; left 1..11, right 14..32
_BND_SPAWN       = (3, 1)
#: The pass-word is RIGHT-ALIGNED on its shore: it always ENDS at this column,
#: and a word of len n therefore starts at `_BND_WORD_END - n + 1`. The pool is
#: the Operator's Vault's, whose words run from 5 glyphs to 15, and the far
#: shore is sized for the longest — but the ROUTE must not change with the
#: draw, and it is the word's END the route touches (`/{word}<CR>` lands on the
#: head, `e` runs to the tail, then two steps to the lectern). Fixing the tail
#: keeps `e 2l x l` exact for every seed; fixing the head would not.
_BND_WORD_END    = 29                 # longest word (15) starts at col 15
_BND_CHEST       = (3, 31)
_BND_EXIT        = (3, 32)
_BND_FRIEZE_ROWS = (1, 5)             # LEFT chamber only — the far shore is bare
_BND_BUDGET      = 30


def _bnd_word_col(word: str) -> int:
    """First column of the right-aligned pass-word."""
    return _BND_WORD_END - len(word) + 1


def _bnd_draw_word(rng) -> str:
    """The binder's pass-word — one of the Operator's Vault's plain passwords.

    The level's fiction is a pass-word legible across the water, and a word the
    player half-recognises reads as one before anything explains it. `_OV_PLAIN`
    is the pool of single tokens with no punctuation inside them, which is what
    a `/{word}<CR>` search wants: any character motion or search takes the whole
    of it. The phrase and leet pools are the Vault's own lesson and stay there.
    """
    return rng.choice(_OV_PLAIN)


def build_dungeon_binders_reliquary(seed: int) -> Dungeon:
    """The Binder's Reliquary (slug `binders_reliquary`): the Codex (:h)."""
    from vimny.engine.editor import _CELL_CODE
    from vimny.sharing.format import Level as _Level, build as _fmt_build
    rng = random.Random(seed)
    word = _bnd_draw_word(rng)

    R, C = _BND_ROWS, _BND_COLS
    grid = [[CellType.WALL] * C for _ in range(R)]
    for r in range(1, R - 1):
        for c in range(1, C - 1):
            grid[r][c] = (CellType.WATER if c in _BND_WATER_COLS
                          else CellType.FLOOR)

    # The pass-word on the far shore — the only text across the water, so
    # the crossing search is unambiguous. Friezes stay on the near shore.
    runs = [{'row': _BND_AR, 'col': _bnd_word_col(word), 'symbols': word,
             'kind': 'ember'}]
    scratch = Room(room_type=RoomType.ENTRY, rows=R, cols=C)
    scratch.cells     = grid
    scratch.char_runs = []
    _place_frieze_sym(scratch, rng, _BND_FRIEZE_ROWS, 1, _BND_WATER_COLS[0] - 1)
    runs += [{'row': ru.row, 'col': ru.col, 'symbols': ''.join(ru.symbols),
              'kind': ru.kind} for ru in scratch.char_runs]

    level = _Level(
        name="The Binder's Reliquary", seed=seed,
        rows=R, cols=C,
        cells=[''.join(_CELL_CODE[c] for c in row) for row in grid],
        spawn=_BND_SPAWN, exit=_BND_EXIT,
        char_runs=runs,
        entities=[{'kind': 'chest_scroll',
                   'at': [_BND_CHEST[0], _BND_CHEST[1]],
                   'scroll_id': 'readers_key'},
                  {'kind': 'exit', 'at': [_BND_EXIT[0], _BND_EXIT[1]],
                   'edit_immune': True}],
        # /{word}<CR> lands on the word's first glyph; e to its end, step to the
        # lectern, loot, step out. (Enter is free; '/' + the word are charged.)
        solution=f'/{word}<CR> e 2l x l')

    dungeon = _fmt_build(level)
    room = dungeon.rooms[0]
    room._bnd_word = word

    # Mist on the water: permanent fog over the channel only. The far shore
    # stays visible and searchable; the scans stop at the bank. A designed
    # darkness, not a derived one — re-attached after the build.
    room.fog_cells  = {(r, c) for r in range(1, R - 1) for c in _BND_WATER_COLS}
    room.underwater_cells = set(room.fog_cells)         # permanent: reveals skip it

    # The Codex's own first page, bound in at the water's edge.
    room._codex_extra = ((
        "The Binder's Colophon",
        ['',
         '  Bound at the water\'s edge. Every scroll you',
         '  carry is stitched into this book; ask for any',
         '  page by name — :h {name} — and it will open.',
         ''],
    ),)

    # reward room, like the first
    room.par    = None
    room.budget = _BND_BUDGET
    return dungeon


# ── The Seekers' Labyrinth (search: / ? n N *) ──────────────────────────────────
#
# A frozen perfect maze (recursive-backtracker, 17×39).  Search ignores walls —
# it teleports the cursor to the matched text wherever it lies — so the labyrinth
# is something you *query*, not something you walk.  Walking to a key is so far
# (foot-only par ≫ budget) that the ONLY affordable route is to call out a name
# and be pulled to it.  Path-critical words are real typable vocab tokens:
#   • 'maze'  appears 3× (the player SPAWNS on the first one): * jumps to the next,
#     n walks the echoes forward, N walks them back.
#   • 'vault' sits beside the red door at the very end: /vault<CR> lands the search.
# Decor words (also vocab) flesh out the halls; none contains 'maze' or 'vault',
# so they never perturb the two taught searches.
#
# Two keys gate two colour-matched doors, and the GOLD key sits to the LEFT of the
# 3rd 'maze' — so reaching the RED key demands a backward jump:
#   • 3rd 'maze' (11,15): the GOLD key is just left of it at (11,11).
#   • 2nd 'maze' (5,1): a GOLD door (5,6) seals the RED key in a one-cell stub (5,7).
#   • the RED door (1,18) caps the exit (1,19); 'vault' (1,7) shares its corridor.
#
# Optimal route (par 18):  * n 0 x N $ p l x /vault<CR> $ p l   (/vault<CR> = len+1: '/' charged, Enter free)
#   * n    — 'maze'(1,1) → 2nd 'maze'(5,1) [a decoy] → 3rd 'maze'(11,15).
#   0 x    — 0 halts on the gold key at (11,11) (left of the maze); x cuts it.
#   N      — reverse the search: back to the 2nd 'maze'(5,1), the passed decoy.
#   $ p l  — $ halts at (5,5) before the gold door; p opens it (gold), l → red key.
#   x      — cut the red key (the register now holds red).
#   /vault<CR>— teleport to 'vault'(1,7), the exit corridor.
#   $ p l  — $ halts at (1,17) before the RED door; p opens it (red), l → exit.
_SEEKERS_MAZE = [
    "#######################################",
    "#.....#.............#.................#",
    "#####.#####.#########.###########.###.#",
    "#...#.....#...#.....#...#.#.....#.#...#",
    "#.#######.#.#.#.###.###.#.#.###.#.#.###",
    "#.......#.#.#.#...#.#.....#.#...#.#...#",
    "#.###.###.###.###.#.#.#####.#.###.###.#",
    "#.#.#...#.#...#.#.#...#.....#.#...#...#",
    "#.#.###.#.#.#.#.#.#####.#####.#.###.###",
    "#.....#.#.#.#...#...#...#.#...#.#.#...#",
    "#####.#.#.#.#######.#.###.#.###.#.###.#",
    "#.....#...#.........#.#.#...#.......#.#",
    "#.###########.#######.#.#.###.#####.#.#",
    "#.....#.....#.#.....#.#.#...#.#...#.#.#",
    "#####.#.###.###.###.#.#.###.###.#.###.#",
    "#.......#.......#.....#.........#.....#",
    "#######################################",
]
_SEEKERS_SPAWN        = (1, 1)
_SEEKERS_GOLD_KEY     = (11, 11)               # left of the 3rd 'maze' (0 halts on it)
_SEEKERS_GOLD_DOOR    = (5, 6)                 # seals the red key beside the 2nd 'maze'
_SEEKERS_RED_KEY      = (5, 7)                 # one-cell stub behind the gold door
_SEEKERS_RED_DOOR     = (1, 18)               # caps the exit
_SEEKERS_EXIT         = (1, 19)
_SEEKERS_WORD         = 'maze'                 # repeated search word (3 occurrences)
_SEEKERS_WORD_POS     = [(1, 1), (5, 1), (11, 15)]
_SEEKERS_DOORWORD     = 'vault'                # word beside the red door
_SEEKERS_DOORWORD_POS = (1, 7)
_SEEKERS_PAR          = 18
_SEEKERS_ANSWER       = '* n 0 x N $ p l x /vault<CR> $ p l'


def _seekers_runs(cells) -> list:
    """All horizontal floor runs (row, start_col, end_col) of length >= 3."""
    runs = []
    for r in range(len(cells)):
        c = 0
        row = cells[r]
        ncols = len(row)
        while c < ncols:
            if row[c] == CellType.CORRIDOR:
                s = c
                while c < ncols and row[c] == CellType.CORRIDOR:
                    c += 1
                if c - s >= 3:
                    runs.append((r, s, c - 1))
            else:
                c += 1
    return runs


def _seekers_decor_pool(rng) -> dict:
    """Length-keyed pool of typable + a few mixed vocab tokens for labyrinth
    decor — excluding any token containing the two taught search words."""
    _load_vocab_tables()
    bad = (_SEEKERS_WORD, _SEEKERS_DOORWORD)
    pool: dict = {}
    for length, words in _VOCAB_PLAIN_BY_LEN.items():
        if 3 <= length <= 8:
            keep = [w for w in words if not any(b in w for b in bad)]
            if keep:
                pool[length] = list(keep)
    # a sprinkle of mixed (glyph) tokens for atmosphere — scenery only
    for length, words in _VOCAB_MIXED_BY_LEN.items():
        if 4 <= length <= 7:
            keep = [w for w in words if not any(b in w for b in bad)]
            pool.setdefault(length, []).extend(keep[: max(1, len(keep) // 4)])
    for length in pool:
        rng.shuffle(pool[length])
    return pool


def build_dungeon_seekers_labyrinth(seed: int) -> 'Dungeon':
    """Search: The Seekers' Labyrinth. See module comment above for the design."""
    from vimny.engine.editor import _CELL_CODE
    from vimny.sharing.format import Level as _Level, build as _fmt_build
    rng = random.Random(seed)
    ROWS, COLS = len(_SEEKERS_MAZE), len(_SEEKERS_MAZE[0])
    grid = [
        [CellType.CORRIDOR if _SEEKERS_MAZE[r][c] == '.' else CellType.WALL
         for c in range(COLS)]
        for r in range(ROWS)
    ]

    # ── Reserved cells: the path-critical words + the five entities ───────────
    reserved: set = {_SEEKERS_GOLD_KEY, _SEEKERS_GOLD_DOOR, _SEEKERS_RED_KEY,
                     _SEEKERS_RED_DOOR, _SEEKERS_EXIT}
    char_runs: list = []
    for (r, c) in _SEEKERS_WORD_POS:
        char_runs.append({'row': r, 'col': c, 'symbols': _SEEKERS_WORD,
                          'kind': 'ember'})
        reserved |= {(r, c + i) for i in range(len(_SEEKERS_WORD))}
    dr, dc = _SEEKERS_DOORWORD_POS
    char_runs.append({'row': dr, 'col': dc, 'symbols': _SEEKERS_DOORWORD,
                      'kind': 'ember'})
    reserved |= {(dr, dc + i) for i in range(len(_SEEKERS_DOORWORD))}

    # ── Decor: fill the OTHER runs with vocab tokens (scenery + search fodder) ─
    pool = _seekers_decor_pool(rng)
    for (r, s, e) in _seekers_runs(grid):
        if any((r, c) in reserved for c in range(s, e + 1)):
            continue                      # leave path-word / entity runs untouched
        c = s
        while c <= e:
            remaining = e - c + 1
            lengths = [L for L in pool if L <= remaining and pool[L]]
            if not lengths:
                break
            L = rng.choice(lengths)
            word = pool[L][rng.randrange(len(pool[L]))]
            char_runs.append({'row': r, 'col': c, 'symbols': word,
                              'kind': rng.choice(('ancient', 'verdant', 'ember'))})
            c += L + 1                     # one-cell gap between words

    level = _Level(
        name="The Seekers' Labyrinth", seed=seed,
        rows=ROWS, cols=COLS,
        cells=[''.join(_CELL_CODE[c] for c in row) for row in grid],
        spawn=_SEEKERS_SPAWN, exit=_SEEKERS_EXIT,
        char_runs=char_runs,
        entities=[
            {'kind': 'floor_key',   'at': [_SEEKERS_GOLD_KEY[0],
                                           _SEEKERS_GOLD_KEY[1]],   'tag': 'gold'},
            {'kind': 'locked_door', 'at': [_SEEKERS_GOLD_DOOR[0],
                                           _SEEKERS_GOLD_DOOR[1]],  'tag': 'gold'},
            {'kind': 'floor_key',   'at': [_SEEKERS_RED_KEY[0],
                                           _SEEKERS_RED_KEY[1]],    'tag': 'red'},
            {'kind': 'locked_door', 'at': [_SEEKERS_RED_DOOR[0],
                                           _SEEKERS_RED_DOOR[1]],   'tag': 'red'},
            {'kind': 'exit',        'at': [_SEEKERS_EXIT[0],
                                           _SEEKERS_EXIT[1]]},
        ],
        solution=_SEEKERS_ANSWER)

    return _fmt_build(level, par=_SEEKERS_PAR)


# Motions available to the player on this level, for the par solver's foot phase.
# % and ( ) are bracket/sentence jumps with no targets in a bracket-free, full-stop-
# free maze (they never move), so they are omitted; ge/gE only reverse e/b within a
# run and never beat them — the set below is the player's full *useful* toolkit.
_SEEKERS_FOOT = ('h', 'j', 'k', 'l', '0', '$', '^', 'w', 'b', 'e',
                 'W', 'B', 'E', 'G', 'gg', 'H', 'M', 'L', '{', '}')
_SEEKERS_COUNTABLE = {'h', 'j', 'k', 'l', 'w', 'b', 'e', 'W', 'B', 'E', 'G', 'gg'}


def _par_seekers_labyrinth(composite, no_search: bool = False, return_path: bool = False):
    """Min-keystroke Dijkstra for The Seekers' Labyrinth (two keys, two doors).

    State = (row, col, reg, gold_open, red_open) where reg ∈ {'', 'gold', 'red'}
    is the colour of the key held in the register.  Foot moves are evaluated
    through the REAL engine (apply_motion) so maze walls and the (currently
    locked) doors behave exactly as in play — open doors are temporarily removed
    so motions cross them.  x at a key cell loads the register; p beside a door
    opens it iff the held key's colour matches.  Search is modelled as composite
    edges: '/W<CR>'/'?W<CR>' + k·n reaches the k-th match forward/backward of any word W
    (cost len(W)+1+k — '/' charged, closing Enter free); '*' + k·n does the same
    for the word under the cursor (cost 1+k).  no_search drops all search edges —
    the foot-only bound that
    proves search is required (it dwarfs the budget).
    """
    from vimny.engine.player import Player
    from vimny.engine.motion import apply_motion
    ROWS, COLS = composite.rows, composite.cols
    keys  = {e.tag: (e.row, e.col) for e in composite.entities if e.kind == 'floor_key'}
    doors = {e.tag: (e.row, e.col) for e in composite.entities if e.kind == 'locked_door'}
    EXIT  = next((e.row, e.col) for e in composite.entities if e.kind == 'exit')
    entry = composite.spawn_pos

    def _kcost(n):
        return 1 if n == 1 else len(str(n)) + 1

    _foot_cache: dict = {}

    def _foot_edges(r, c, g_open, ro_open):
        ck = (r, c, g_open, ro_open)
        if ck in _foot_cache:
            return _foot_cache[ck]
        saved = composite.entities
        open_tags = ({'gold'} if g_open else set()) | ({'red'} if ro_open else set())
        if open_tags:
            composite.entities = [e for e in saved
                                  if not (e.kind == 'locked_door' and e.tag in open_tags)]
            composite.rebuild_indexes()
        out = []
        for m in _SEEKERS_FOOT:
            maxn = max(ROWS, COLS) if m in _SEEKERS_COUNTABLE else 1
            prev = None
            for n in range(1, maxn + 1):
                p = Player(row=r, col=c)
                cg = True if m not in ('G', 'gg') else (n != 1)
                apply_motion(p, m, n, composite, count_given=cg)
                np = (p.row, p.col)
                if m in _SEEKERS_COUNTABLE and np == prev:
                    break
                prev = np
                if np != (r, c):
                    out.append((_kcost(n), np, m if n == 1 else f'{n}{m}'))
                if m not in _SEEKERS_COUNTABLE:
                    break
        if open_tags:
            composite.entities = saved
            composite.rebuild_indexes()
        _foot_cache[ck] = out
        return out

    distinct = sorted({''.join(ru.symbols) for ru in composite.char_runs})

    def _matches(pat):
        out = []
        for ru in composite.char_runs:
            i = ''.join(ru.symbols).find(pat)
            if i >= 0:
                out.append((ru.row, ru.col + i))
        return sorted(out)

    def _search_edges(r, c):
        out = []
        cur = (r, c)
        for W in distinct:
            ms = _matches(W)
            if not ms:
                continue
            fwd = [m for m in ms if m > cur] + [m for m in ms if m <= cur]   # wrap
            for k, tgt in enumerate(fwd):
                out.append((len(W) + 1 + k, tgt, f'/{W}<CR>' + 'n' * k))
            bwd = [m for m in reversed(ms) if m < cur] + [m for m in reversed(ms) if m >= cur]
            for k, tgt in enumerate(bwd):
                out.append((len(W) + 1 + k, tgt, f'?{W}<CR>' + 'n' * k))
        ru = composite.char_run_at(r, c)
        if ru is not None:
            ms = _matches(''.join(ru.symbols))
            fwd = [m for m in ms if m > cur] + [m for m in ms if m <= cur]
            for k, tgt in enumerate(fwd):
                if tgt != cur:
                    out.append((1 + k, tgt, '*' + 'n' * k))
        return out

    start = (entry[0], entry[1], '', 0, 0)
    dist = {start: 0}
    prev = {start: None}
    heap = [(0, start)]
    while heap:
        cost, st = heapq.heappop(heap)
        r, c, reg, go, ro = st
        if (r, c) == EXIT:
            if return_path:
                return cost, _join_path(prev, st, merge_single=False)
            return cost
        if cost > dist.get(st, float('inf')):
            continue

        def _try(nb, mc, lbl):
            g = cost + mc
            if g < dist.get(nb, float('inf')):
                dist[nb] = g
                prev[nb] = (st, lbl)
                heapq.heappush(heap, (g, nb))

        edges = _foot_edges(r, c, go, ro)
        if not no_search:
            edges = edges + _search_edges(r, c)
        for mc, (nr, nc), lbl in edges:
            _try((nr, nc, reg, go, ro), mc, lbl)
        # x: cut the key under the cursor into the register (overwrites)
        for tag, pos in keys.items():
            if (r, c) == pos and reg != tag:
                _try((r, c, tag, go, ro), 1, 'x')
        # p: open an adjacent door iff the held key's colour matches
        for tag, pos in doors.items():
            opened = go if tag == 'gold' else ro
            if reg == tag and not opened and abs(r - pos[0]) + abs(c - pos[1]) == 1:
                ngo, nro = (1, ro) if tag == 'gold' else (go, 1)
                _try((pos[0], pos[1], reg, ngo, nro), 1, 'p')

    return (None, '') if return_path else None


# ── The Waypoint Sanctum (marks: m ' `) ──────────────────────────────────────────
#
# A sealed, WORDLESS sanctum CORRIDOR set HIGH in the map: a thin prose danger band
# above it (holding the gold exit key) and a HUGE prose danger room filling the
# bottom two-thirds — both CRAWLING with goblins, both sealed (reachable only by a
# teleport: search / mark / line-jump).  Treasure teases (chests & hearts behind
# keyless 'blue' locks) line the bottom wall.  Search teleports you OUT to the prose
# for the gold key; the wordless corridor can't be searched back to, so a MARK is the
# way home — and a mark/search teleport is the only SURVIVABLE way past the horde.
#   • 'a (the sanctum row's first-left cell) -> the scroll nook's :set number scroll
#     (an OFF-PAR bonus: grabbing it costs +3 over par, so a collector trades the
#     second star for the relic — bonuses never sit ON the par path, else skipping
#     them would beat par).
#   • `a (exact mark) -> back to the spawn at the sanctum's centre.
#   • the exit key + its 'xyzzy' rune are sealed in a SEARCH-ONLY POCKET in the top
#     band (walls ring them) — gg/G + a count-walk can't enter, only a ?xyzzy
#     search-jump (which ignores walls) lands inside. So the search up-leg is forced
#     the same way the moats force the mark down-leg. Forward decoys (bottom room)
#     sit AFTER the spawn, so ? lands on the real rune while / hits a decoy.
#   • the sanctum sits HIGH so M (middle-of-screen) always lands DOWN in the goblin
#     room, never on the scroll nook — using M to cheat the scroll backfires lethally.
# The exit is teleport-safe (not any jump target; behind the blocking exit lock).
#
# Optimal route (par 16):
#   ma · ?xyzzy<CR> h x (key) · `a $ (home, then line-end) · p l → exit
_WP_ROWS, _WP_COLS = 19, 46
_WP_CROW   = 5                     # sanctum corridor row (mark row; wordless)
_WP_SCROLL = (5, 1)                # chest_scroll — sanctum row's first-left cell -> 'a
_WP_SCROLL_DOOR = (5, 4)           # 'blue' lock sealing the scroll nook ('a hops it)
_WP_SPAWN  = (5, 23)               # spawn + mark -> centre of the sanctum corridor
_WP_LOCK   = (5, 43)               # exit lock (gold)
_WP_EXIT   = (5, 44)
_WP_KEYWORD      = 'xyzzy'          # the magic word (Colossal Cave Adventure, 1977);
                                   # a non-word, so it can never collide with vocab
_WP_KEY_WORD_POS = (2, 30)         # the FIRST magic word — thin TOP danger band (backward)
_WP_DECOY_POS    = [(11, 12), (13, 24), (15, 34)]  # forward decoys (open danger floor)
# The SECOND magic word (Colossal Cave's other teleporter) — the # lesson:
# the ? leg lands you in the xyzzy pocket, where plugh wakes
# from a SCRIPTED fog (fogged text is unsearchable, so ?plugh from spawn
# finds nothing — the fresh-word law); its backward twin sits in a second
# sunken pocket holding the gold key, its forward decoys price out * (a
# * N N walk pays 3 where # pays 1), and the xyzzy register keeps n
# useless. Standing on plugh, # is the one-key way to the key.
_WP_WORD2        = 'plugh'
_WP_W2_POCKET1   = (2, 36)         # the waking stone, east of xyzzy in pocket 1
_WP_W2_POCKET2   = (2, 7)          # its backward twin, beside the gold key
_WP_KEY          = (2, 6)          # gold floor_key, just left of the twin
_WP_W2_DECOYS    = [(11, 30), (13, 6), (15, 16)]   # forward decoys for plugh
_WP_PKT1_SPAN    = (29, 40)        # pocket-1 interior cols (xyzzy + gap + plugh)
_WP_PKT2_SPAN    = (6, 12)         # pocket-2 interior cols (key + plugh twin)
_WP_DANGER_ROWS  = (1, 2, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17)
_WP_VAULT_COLS   = (6, 10, 14, 18, 22, 26, 30, 34, 38, 42)  # vaults lining the sanctum underside
_WP_PAR    = 17
_WP_ANSWER = "ma ?xyzzy<CR> w # h x `a $ p l"


def build_dungeon_waypoint_sanctum(seed: int) -> 'Dungeon':
    """Marks: The Waypoint Sanctum.  See the module comment above for the design.

    DESIGN NOTE — row-9 vault loot (relic scrolls + hearts): reaching it is meant
    to be an emergent Vim feat (e.g. / to a row-10 word, then G$x to carve the
    danger room open and clear the goblins), NOT a handed-out key puzzle. We
    deliberately do NOT gate it with blue keys or void-rune brinks.
    Budget does NOT meaningfully gate this: once the next level is unlocked the
    player can replay and loot one chest per visit. The heart_containers are
    safe (one-time per player via progress['collected_hearts']), but the relic
    chests respawn each visit, so replaying farms a fresh relic each run until
    the pool empties.
    REBALANCING LEVERS (only if farming proves undesirable):
    (a) persist looted vault chests per-player, mirroring the collected_hearts
    mechanism, so each chest yields at most one relic ever; and/or (b) a
    warden/summoner guarding the vault band. Both need real tuning/judgement,
    so both are deferred until there is broader play data."""
    rng = random.Random(seed)
    R, C = _WP_ROWS, _WP_COLS
    from vimny.engine.editor import _CELL_CODE
    from vimny.sharing import format as _fmt
    from vimny.sharing.format import Level as _Level, build as _fmt_build
    cells = [[CellType.WALL] * C for _ in range(R)]

    def carve(r, c):
        cells[r][c] = CellType.CORRIDOR

    # Thin TOP danger band (rows 1-2) — holds the gold key + its 'xyzzy' word.
    for r in (1, 2):
        for c in range(1, C - 1):
            carve(r, c)
    # SEARCH-ONLY POCKET: ring the gold key + its rune with walls so gg/G + a
    # count-walk (`gg j 28l`) can't reach them — only a ?xyzzy search-jump, which
    # ignores walls, lands inside. This forces the search up-leg exactly as the
    # moats (below) force the mark down-leg. The pocket spans the key cell through
    # the end of the rune; walls ceiling it (row 1) and flank it (row 2 sides).
    # (Waterworks: the pocket ring, the sanctum seals
    # and the vault boxes are MISTED WATER, not stone — everything is
    # visible, per the stone-fog law, while walking / scans stay barred:
    # water blocks feet, the water on it blocks $ / 0 / ^ / f scans, and
    # { } skip flooded rows exactly as they skipped the walls.)
    underwater: set = set()

    def moat(r, c):
        cells[r][c] = CellType.WATER
        underwater.add((r, c))

    _pkt_lo = _WP_PKT1_SPAN[0] - 1                            # left bank (col 28)
    _pkt_hi = _WP_PKT1_SPAN[1] + 1                            # right bank (col 41)
    for c in range(_pkt_lo, _pkt_hi + 1):
        moat(1, c)                                           # water over the pocket
    moat(2, _pkt_lo)                                         # left bank
    moat(2, _pkt_hi)                                         # right bank
    # Pocket 2 — the # pocket: the gold key + plugh's backward twin, ringed
    # the same way (sunken water: visible per the stone-fog law, searchable,
    # foot-proof). It sits WEST of pocket 1 so the twin is strictly behind.
    _p2_lo, _p2_hi = _WP_PKT2_SPAN[0] - 1, _WP_PKT2_SPAN[1] + 1
    for c in range(_p2_lo, _p2_hi + 1):
        moat(1, c)
    moat(2, _p2_lo)
    moat(2, _p2_hi)
    # SANCTUM (rows 4-6), sealed above by the row-3 wall and below by the row-7 wall.
    # Row 5 is the mark row: a one-cell scroll nook at col 1 behind a 'blue' lock at
    # col 2, then the wordless corridor, the gold exit lock (43) + exit (44).  Rows 4
    # & 6 are a WATER MOAT (cols 5-42, impassable) flanking the mark row: the { / }
    # paragraph jumps can't land on them and drop into the open corridor (the cheese
    # `( tc x } j $ p l` = 9). Flooded, they are skipped like the sealing walls, and
    # { / } resolve onto row 5 where _segment_left reaches the scroll nook behind the
    # blue lock, trapping the jumper. So the corridor island is reachable only by `a
    # (the exact mark): marks are genuinely forced; the legit route never leaves row 5.
    for c in range(5, 43):
        cells[4][c] = CellType.WATER          # water moat flanking the mark row
        cells[6][c] = CellType.WATER
    for c in range(1, C - 1):
        moat(3, c)                            # the sanctum's upper seal, flooded
    for c in range(1, 43):
        carve(5, c)
    carve(5, 43); carve(5, 44)           # exit-lock + exit cells
    # HUGE bottom danger room (rows 8-17).
    for r in range(8, 18):
        for c in range(1, C - 1):
            carve(r, c)
    # Treasure teases LINE the sanctum's underside: each is a 2-deep box hanging off
    # the row-7 seal — a keyless 'blue' door in the seal, a sealed shaft (row 8) and
    # the chest/heart at its foot (row 9), walled off from the danger room so only the
    # locked door (facing UP into the sanctum) ever sees it.
    entities: list = []
    vault_cells: set = set()
    first_chest = True
    for i, X in enumerate(_WP_VAULT_COLS):
        # The row-9 vaults hold hearts and relic scrolls (the random pool); only
        # the left-chamber nook holds the Numbered Ledger (see below). The FIRST
        # vault chest is pinned to The Second Stride ('redo' — <C-r>): undo is
        # always-on and refunds position + budget, so its other hand belongs to
        # the player BEFORE the editing act begins — and a scroll about a
        # waiting footprint belongs in the sanctum of marks.
        kind = 'heart_container' if i % 3 == 1 else 'chest_scroll'
        sid = 'redo' if (kind == 'chest_scroll' and first_chest) else ''
        first_chest = first_chest and kind != 'chest_scroll'
        carve(7, X)                                      # 'blue' door cell (in the seal)
        for r in (8, 9):                                 # box the shaft off the danger room
            cells[r][X - 1] = CellType.WALL              # (stone flanks; the treasure
            cells[r][X + 1] = CellType.WALL              # shows THROUGH the door — a
        cells[10][X] = CellType.WALL                     # grille, per the stone-fog law)
        entities += [{'kind': 'locked_door', 'at': [7, X], 'tag': 'blue'},
                     {'kind': kind, 'at': [9, X], 'scroll_id': sid}]
        vault_cells |= {(7, X), (8, X), (9, X)}
    for c in range(1, C - 1):
        if cells[7][c] == CellType.WALL:
            moat(7, c)                            # the lower seal, flooded too

    # Reserved cells (no prose decor / no goblins): key, both magic words +
    # their decoys, the two pocket interiors, vaults.
    reserved: set = {_WP_KEY} | vault_cells
    reserved |= {(_WP_KEY_WORD_POS[0], _WP_KEY_WORD_POS[1] + i) for i in range(len(_WP_KEYWORD))}
    for (dr, dc) in _WP_DECOY_POS:
        reserved |= {(dr, dc + i) for i in range(len(_WP_KEYWORD))}
    for (pr, pc) in (_WP_W2_POCKET1, _WP_W2_POCKET2, *_WP_W2_DECOYS):
        reserved |= {(pr, pc + i) for i in range(len(_WP_WORD2))}
    reserved |= {(2, c) for c in range(_WP_PKT1_SPAN[0], _WP_PKT1_SPAN[1] + 1)}
    reserved |= {(2, c) for c in range(_WP_PKT2_SPAN[0], _WP_PKT2_SPAN[1] + 1)}
    # Goblins crawl every danger room (deterministic stride, ~1 in 7 floor cells).
    goblins = [(r, c) for r in _WP_DANGER_ROWS for c in range(1, C - 1)
               if cells[r][c] == CellType.CORRIDOR and (r, c) not in reserved
               and (c + 2 * r) % 7 == 0]
    reserved |= set(goblins)

    # Key word (real vocab token) + forward decoys.
    char_runs = [{'row': _WP_KEY_WORD_POS[0], 'col': _WP_KEY_WORD_POS[1],
                  'symbols': _WP_KEYWORD, 'kind': 'ember'}]
    for (dr, dc) in _WP_DECOY_POS:
        char_runs.append({'row': dr, 'col': dc,
                          'symbols': _WP_KEYWORD, 'kind': 'ember'})
    for (dr, dc) in (_WP_W2_POCKET1, _WP_W2_POCKET2, *_WP_W2_DECOYS):
        char_runs.append({'row': dr, 'col': dc,
                          'symbols': _WP_WORD2, 'kind': 'ember'})
    # BOTH sanctum plughs sleep under SCRIPTED fog (the Wet Ink pattern):
    # a fogged word is unsearchable — by EVERY search uniformly, # included
    # — so ?plugh from the spawn finds nothing (with only the stone fogged,
    # a visible pocket-2 twin would be a 15-key skip straight to the key).
    # The level tick wakes the pair the moment the ?
    # leg lands in pocket 1; # then reaches the freshly-lit twin. The
    # forward DECOYS stay unfogged: they are the *-pricing, and a backward
    # search from the spawn never sees them.
    _plugh_fog = {(r, c + i)
                  for (r, c) in (_WP_W2_POCKET1, _WP_W2_POCKET2)
                  for i in range(len(_WP_WORD2))}

    # Prose fill: vocab over the danger rooms (seed-varied, never containing the
    # key word, never on a reserved cell — so the only 'cipher' matches are the
    # real one + the three decoys).
    _load_vocab_tables()
    pool: dict = {}
    for length, words in _VOCAB_PLAIN_BY_LEN.items():
        if 3 <= length <= 8:
            keep = [w for w in words if _WP_KEYWORD not in w]
            if keep:
                pool[length] = list(keep)
    for r in _WP_DANGER_ROWS:
        c = 1
        while c < C - 1:
            if (r, c) in reserved or cells[r][c] != CellType.CORRIDOR:
                c += 1
                continue
            span = 0
            while (c + span < C - 1 and cells[r][c + span] == CellType.CORRIDOR
                   and (r, c + span) not in reserved):
                span += 1
            lengths = [L for L in pool if L <= span and pool[L]]
            if lengths and span >= 3:
                L = rng.choice(lengths)
                word = pool[L][rng.randrange(len(pool[L]))]
                char_runs.append({'row': r, 'col': c, 'symbols': word,
                                  'kind': rng.choice(('ancient', 'verdant', 'ember'))})
                c += L + 1
            else:
                c += span + 1

    # BOTH sanctum plughs sleep under SCRIPTED fog (the Wet Ink pattern):
    # a fogged word is unsearchable — by EVERY search uniformly, # included
    # — so ?plugh from the spawn finds nothing (with only the stone fogged,
    # a visible pocket-2 twin would be a 15-key skip straight to the key).
    # The level tick wakes the pair the moment the ?
    # leg lands in pocket 1; # then reaches the freshly-lit twin. The
    # forward DECOYS stay unfogged: they are the *-pricing, and a backward
    # search from the spawn never sees them.
    _plugh_fog = {(r, c + i)
                  for (r, c) in (_WP_W2_POCKET1, _WP_W2_POCKET2)
                  for i in range(len(_WP_WORD2))}

    entities += [
        {'kind': 'chest_scroll', 'at': [_WP_SCROLL[0], _WP_SCROLL[1]],
         'scroll_id': 'setnum'},
        {'kind': 'locked_door',  'at': [_WP_SCROLL_DOOR[0],
                                        _WP_SCROLL_DOOR[1]], 'tag': 'blue'},
        {'kind': 'locked_door',  'at': [_WP_LOCK[0], _WP_LOCK[1]],
         'tag': 'gold'},
        {'kind': 'exit',         'at': [_WP_EXIT[0], _WP_EXIT[1]]},
        {'kind': 'floor_key',    'at': [_WP_KEY[0], _WP_KEY[1]],
         'tag': 'gold'},
    ]
    for (gr, gc) in goblins:
        entities.append({'kind': 'goblin', 'at': [gr, gc],
                         'max_hp': 1, 'ai': 'chase'})

    def encode(r):
        return ''.join(_fmt._UNDERWATER_CODE if (r, c) in underwater else _CELL_CODE[ct]
                       for c, ct in enumerate(cells[r]))

    level = _Level(
        name='The Waypoint Sanctum', seed=seed,
        rows=R, cols=C,
        cells=[encode(r) for r in range(R)],
        spawn=_WP_SPAWN, exit=_WP_EXIT,
        char_runs=char_runs,
        entities=entities,
        solution=_WP_ANSWER)

    # THE WAKING STONE, said as data: a zone seal whose region is pocket 1
    # (row 2, cols 29-40) and whose unveils are the two `plugh` words' cells.
    # While the player stands inside the pocket, the words are legible and
    # searchable; one-way, so they stay that way after they leave.
    from vimny.engine.world import Seal as _Seal
    level.seals = (*level.seals, _Seal(
        mode='zone', region=(2, _WP_PKT1_SPAN[0], 2, _WP_PKT1_SPAN[1]),
        unveils=tuple(sorted(_plugh_fog)),
        message="In the pocket's shadow, a second word wakes."))

    dungeon = _fmt_build(level, par=_WP_PAR)
    return dungeon


# ── The Bracket Vaults layout constants ─────────────────────────────────────────────────
#
# Three-corridor snake layout (9 rows × 60 cols): rows 1/3/5 are the corridors, rows 2/4
# the water gaps with a single CORRIDOR turn cell each, row 3 water except its two bracket
# cells, row 6 a water moat and row 7 a decoy goblin pit. Each corridor row has ( at col
# _BRACKET_VAULTS_BRACKET_OPEN and ) at col _BRACKET_VAULTS_BRACKET_CLOSE; WATER blocks manual
# h/l, so % is the only way across — its authentic Vim use, jumping a parenthesised run.
#
# Right turn: col _BRACKET_VAULTS_BRACKET_CLOSE, rows 1-3 (turn cell at row 2).
# Left turn:  col _BRACKET_VAULTS_BRACKET_OPEN,  rows 3-5 (turn cell at row 4).
#
# Anti-teleport: a {N}G goto-line teleport onto any snake rung must NOT shortcut the snake,
# so every snake row (2-5) has a col-1 pocket (an unmatched ) sealed by a WALL at col 2) that
# {N}G lands in instead. The exit is gated by a locked door opened with a floor_key that sits
# on the row-2 turn cell — reachable only via the snake. See _par_bracket_vaults for par.
#
_BRACKET_VAULTS_ROWS          = 9      # rows 1/3/5 = snake; 6 = water moat; 7 = decoy goblin pit
_BRACKET_VAULTS_COLS          = 60
_BRACKET_VAULTS_BRACKET_OPEN  = 4      # ( on each corridor row
_BRACKET_VAULTS_BRACKET_CLOSE = 54     # ) on rows 1 & 3; right-turn column; locked-door column
_BRACKET_VAULTS_CLOSE_R5      = 53     # ) on row 5 only (one left of CLS; exit sits at CLS)
_BRACKET_VAULTS_CORR_ROWS     = (1, 3, 5)
_BRACKET_VAULTS_MOAT_ROW      = 6      # full-water row sealing the decoy off from the snake
_BRACKET_VAULTS_DECOY_ROW     = 7      # corridor below the moat: where G/L land — a goblin trap
_BRACKET_VAULTS_DECOY_GOBLINS = (18, 33, 48)   # goblin columns on the decoy row
_BRACKET_VAULTS_ENTRY         = (1, 1)
# The exit sits behind a locked door at CLS; the floor_key that opens it is on the row-2
# right-turn cell (reachable only via the snake — a {N}G teleport lands in the col-1 pocket).
_BRACKET_VAULTS_KEY_POS       = (2, _BRACKET_VAULTS_BRACKET_CLOSE)   # (2, 54) floor_key
_BRACKET_VAULTS_DOOR_POS      = (5, _BRACKET_VAULTS_BRACKET_CLOSE)   # (5, 54) locked_door
_BRACKET_VAULTS_EXIT_POS      = (5, _BRACKET_VAULTS_BRACKET_CLOSE + 1)  # (5, 55) one past the door
_BRACKET_VAULTS_PAR           = 10      # % j x j % 2j $ p l = 1+1+1+1+1+2+1+1+1 = 10 ks
_BRACKET_VAULTS_ANSWER        = '% j x j % 2j $ p l'   # % to (1,54); j x j grabs the key &
                                                       # drops to (3,54); % 2j to (5,4); $ to
                                                       # the ) by the door; p unlocks; l → exit
# Rows 1 & 5 fill the span between ( and ) with randomly-chosen vocab words, so % jumps
# across a real (...) expression — its authentic Vim use — not empty corridor. The words
# are packed single-spaced with no gap to either bracket, so they exactly fill the span.
_BRACKET_VAULTS_WORDS_MIN     = 10      # at least this many words per parenthesised row


def _bracket_vaults_fill_words(rng, width: int, min_words: int = 10):
    """Pick random vocab words that, joined by single spaces, EXACTLY fill `width`
    columns using at least `min_words` words.

    Words come from the plain vocab table, minus any token containing a bracket
    (those would derail %). Since the vocab's shortest word is 3 chars, the packer
    only ever leaves a remainder of 0 (close) or >= 4 (room for ' ' + a 3-char word),
    never a 1-3 gap it can't fill; on the rare attempt that closes before reaching
    min_words it just retries. Deterministic for a given rng.
    """
    _load_vocab_tables()
    by_len = {n: [w for w in ws if not any(c in '()[]{}' for c in w)]
              for n, ws in _VOCAB_PLAIN_BY_LEN.items()}
    by_len = {n: ws for n, ws in by_len.items() if ws}
    lens   = sorted(by_len)
    minlen = lens[0]

    for _ in range(4000):
        words, used = [], 0
        while used < width:
            sep   = 0 if not words else 1
            avail = width - used - sep
            # Keep the remainder fillable: after this word, leave either 0 (done) or
            # enough for another ' ' + shortest word.
            cands = [L for L in lens
                     if L <= avail and (avail - L == 0 or avail - L >= minlen + 1)]
            if not cands:
                break
            # While short of the quota, prefer words that leave room to continue, and
            # bias toward shorter words so we comfortably clear min_words.
            if len(words) + 1 < min_words:
                cands = [L for L in cands if avail - L >= minlen + 1] or cands
            L = rng.choices(cands, weights=[1.0 / (x * x) for x in cands])[0]
            words.append(rng.choice(by_len[L]))
            used += sep + L
        if used == width and len(words) >= min_words:
            return words
    # Unreachable at the widths this level uses (~50 cols vs a 10-word quota); kept as a
    # guard so a narrower caller fails loudly instead of returning a short row.
    raise RuntimeError(f'could not pack {min_words}+ words into width {width}')


def _par_bracket_vaults(composite, use_percent: bool = True, return_path: bool = False):
    """Minimum-keystroke Dijkstra for The Bracket Vaults.

    The exit sits behind a locked door opened with the floor_key on the row-2 turn cell,
    so State = (row, col, has_key, door_open). Motions: h/l/j/k (count), $ 0 ^,
    % (if use_percent=True), x (grab the key on its cell), p (unlock the door one cell to
    the right, stepping onto it). A closed door blocks standing on it AND every rightward
    scan ($/^/%), exactly like the engine (a locked_door halts _cross_water).
    use_percent=False simulates the command-necessity test (% disabled → water uncrossable).
    """
    ROWS, COLS = composite.rows, composite.cols
    entry = composite.spawn_pos
    goal  = composite.exit_pos
    KEYR, KEYC   = _BRACKET_VAULTS_KEY_POS
    DOORR, DOORC = _BRACKET_VAULTS_DOOR_POS

    _PAIRS_OPEN_L11  = {'(': ')', '[': ']', '{': '}'}
    _PAIRS_CLOSE_L11 = {')': '(', ']': '[', '}': '{'}

    def _passable(r, c, do):
        if not composite.is_passable(r, c):
            return False
        if (r, c) == (DOORR, DOORC) and not do:   # locked door is a wall until opened
            return False
        return True

    def _ok(r, c, do):
        if not _passable(r, c, do):
            return False
        ru = composite.char_run_at(r, c)
        return not (ru and ru.kind == 'void')

    def _blocks_scan(r, c, do):
        return (composite.cells[r][c] in (CellType.WALL, CellType.WOOD_WALL)
                or ((r, c) == (DOORR, DOORC) and not do))

    def _bracket_here(r, c):
        ru = composite.char_run_at(r, c)
        if ru is not None:
            ch = ru.symbols[c - ru.col]
            if ch in _PAIRS_OPEN_L11 or ch in _PAIRS_CLOSE_L11:
                return ch
        return None

    def _pct(r, c, do):
        """Replicate motion.py % scan: same-row, nesting-aware, stops at walls/closed door."""
        bch   = _bracket_here(r, c)
        start = c if bch is not None else None
        # If not on a bracket, scan right for the first one (Vim behaviour).
        if start is None:
            for cc in range(c + 1, COLS):
                if _blocks_scan(r, cc, do):
                    break
                b = _bracket_here(r, cc)
                if b is not None:
                    start, bch = cc, b
                    break
        if start is None:
            return None
        forward = bch in _PAIRS_OPEN_L11
        want    = _PAIRS_OPEN_L11[bch] if forward else _PAIRS_CLOSE_L11[bch]
        scan    = range(start, COLS) if forward else range(start, -1, -1)
        depth   = 0
        for cc in scan:
            if _blocks_scan(r, cc, do):
                break
            b = _bracket_here(r, cc)
            if b == bch:
                depth += 1
            elif b == want:
                depth -= 1
                if depth == 0:
                    if _ok(r, cc, do) and cc != c:
                        return (r, cc)
                    return None
        return None

    start_state = (entry[0], entry[1], 0, 0)
    dist = {start_state: 0}
    prev = {start_state: None}
    heap = [(0, start_state)]
    max_n = max(ROWS, COLS)

    while heap:
        cost, state = heapq.heappop(heap)
        r, c, hk, do = state
        if (r, c) == goal:
            if return_path:
                return cost, _join_path(prev, state, merge_single=True)
            return cost
        if cost > dist.get(state, float('inf')):
            continue

        def _push(ns, mc=1, lbl=''):
            if ns is None:
                return
            g = cost + mc
            if g < dist.get(ns, float('inf')):
                dist[ns] = g
                prev[ns] = (state, lbl)
                heapq.heappush(heap, (g, ns))

        # x: pick up the floor key when standing on it
        if (r, c) == (KEYR, KEYC) and hk == 0:
            _push((r, c, 1, do), 1, 'x')

        # p: unlock the locked door one cell to the right (steps onto it), consuming the key
        if hk == 1 and do == 0 and (r, c + 1) == (DOORR, DOORC):
            _push((DOORR, DOORC, 0, 1), 1, 'p')

        # j/k (vertical), h/l (horizontal) — with count
        for dr, key in ((1, 'j'), (-1, 'k')):
            for n in range(1, max_n + 1):
                nr2 = r + dr * n
                if nr2 < 0 or nr2 >= ROWS or not _ok(nr2, c, do):
                    break
                mc2  = 1 if n == 1 else len(str(n)) + 1
                lbl2 = key if n == 1 else f'{n}{key}'
                _push((nr2, c, hk, do), mc2, lbl2)

        for dc, key in ((1, 'l'), (-1, 'h')):
            for n in range(1, max_n + 1):
                nc2 = c + dc * n
                if nc2 < 0 or nc2 >= COLS or not _ok(r, nc2, do):
                    break
                mc2  = 1 if n == 1 else len(str(n)) + 1
                lbl2 = key if n == 1 else f'{n}{key}'
                _push((r, nc2, hk, do), mc2, lbl2)

        # gg / G / {n}G — the line jumps. Modelled with the solver's own door
        # state, so a jump whose landing sits behind the shut door is no move.
        for jr, jc, jcost, jlbl in _line_jump_moves(
                composite, lambda rr, cc: _ok(rr, cc, do), r, c):
            _push((jr, jc, hk, do), jcost, jlbl)

        # $: rightmost passable+ok col in same row (stops at a closed door)
        best_col = None
        for cc in range(c + 1, COLS):
            if not _passable(r, cc, do):
                break
            best_col = cc
        if best_col is not None and _ok(r, best_col, do):
            _push((r, best_col, hk, do), 1, '$')

        # 0: leftmost passable+ok col in same row
        left_col = c
        for cc in range(c - 1, -1, -1):
            if not _passable(r, cc, do):
                break
            left_col = cc
        if left_col < c and _ok(r, left_col, do):
            _push((r, left_col, hk, do), 1, '0')

        # ^: first character (any kind) scanning from leftmost passable boundary.
        # Stops at the first character found (void or not); only pushes if _ok
        # (non-void).  Mirrors the game engine: void runes block ^ silently.
        lb = c
        for cc in range(c - 1, -1, -1):
            if not _passable(r, cc, do):
                break
            lb = cc
        rb = c
        for cc in range(c + 1, COLS):
            if not _passable(r, cc, do):
                break
            rb = cc
        for cc in range(lb, rb + 1):
            ru2 = composite.char_run_at(r, cc)
            if ru2:
                if _ok(r, cc, do):
                    _push((r, cc, hk, do), 1, '^')
                break  # first character (void or not) terminates search

        # %: matching bracket jump (disabled in command-necessity test)
        if use_percent:
            nb_pct = _pct(r, c, do)
            if nb_pct is not None:
                _push((nb_pct[0], nb_pct[1], hk, do), 1, '%')

    if return_path:
        return None, ''
    return None


def build_dungeon_bracket_vaults(seed: int) -> Dungeon:
    """% (The Bracket Vaults).

    Teaches `%` (bracket-matching jump) as the only way to cross a band of WATER, then
    gates the exit behind a floor_key (x to grab) and a locked door (p to unlock).
    Layout: three horizontal corridors (rows 1/3/5) in a snake pattern, with rows 2, 3
    and 4 flooded. Rows 1 & 5 fill their ( ... ) span with treasure-words so % jumps a
    real parenthesised run. Rows 2 and 4 are water except a single turn cell each; row 3
    is water except its two bracket cells. Every snake row (2-5) carries a col-1 pocket
    (unmatched ) + WALL at col 2) so a {N}G teleport is trapped there, not on the snake.

    Right turn: col 54, rows 1-3.  Left turn: col 4, rows 3-5.  Row 5's ) sits at col 53;
    the locked door is at (5,54) and the exit one cell further right at (5,55). The key is
    on the row-2 turn cell (2,54), reachable only by the snake.

    Optimal path (par=10):  % j x j % 2j $ p l
      (1,1) % → (1,54) ).  j → (2,54) key, x grabs it.  j → (3,54).  % → (3,4) (.
      2j → (5,4) (.  $ → (5,53) ) [the closed door halts $].  p unlocks the door and steps
      onto (5,54).  l → (5,55) EXIT.

    Without %: par_no_% = None (the water band is uncrossable by hand).
    Layout is deterministic; seed only colors the bracket/word characters.
    """
    from vimny.engine.editor import _CELL_CODE
    from vimny.sharing.format import Level as _Level, build as _fmt_build
    ROWS, COLS = _BRACKET_VAULTS_ROWS, _BRACKET_VAULTS_COLS

    grid = [[CellType.WALL] * COLS for _ in range(ROWS)]

    OPN = _BRACKET_VAULTS_BRACKET_OPEN   # 4
    CLS = _BRACKET_VAULTS_BRACKET_CLOSE  # 54
    EXC = _BRACKET_VAULTS_CLOSE_R5       # 53  (row-5 closing bracket col)

    # ── Carve corridors ───────────────────────────────────────────────────────
    for r in _BRACKET_VAULTS_CORR_ROWS:
        for c in range(1, COLS - 1):
            grid[r][c] = CellType.CORRIDOR

    # ── Carve turns ───────────────────────────────────────────────────────────
    # Right turn: col CLS rows 1-3 (the j-path down from C1 to C2)
    grid[2][CLS] = CellType.CORRIDOR
    # Left turn: col OPN rows 3-5 (the j-path down from C2 to C3)
    grid[4][OPN] = CellType.CORRIDOR

    # ── Water in the gap and middle rows ──────────────────────────────────────
    # Rows 2 and 4: water everywhere except the single CORRIDOR turn cells.
    # Row 3: water everywhere except the two bracket cells (OPN and CLS).
    # % scans through water (not a WALL/WOOD_WALL) to reach the matching bracket;
    # manual h/l are blocked because is_passable returns False for WATER.
    for c in range(1, COLS - 1):
        if grid[2][c] != CellType.CORRIDOR:
            grid[2][c] = CellType.WATER
        if grid[4][c] != CellType.CORRIDOR:
            grid[4][c] = CellType.WATER
        if c != OPN and c != CLS:
            grid[3][c] = CellType.WATER

    # ── Moat + decoy goblin pit (anti-teleport) ───────────────────────────────
    # The exit sits on row 5, which used to be the LAST line — so G (last line) and
    # L (bottom of screen) teleported straight to it and `% l` finished in 3, under
    # par. Add a full-water moat (row 6) and a corridor decoy (row 7) BELOW it: now
    # G/L land on row 7, sealed off from the snake by the moat, in a pit of goblins.
    # The real exit on row 5 is interior and unreachable by any teleport.
    MOAT, DECOY = _BRACKET_VAULTS_MOAT_ROW, _BRACKET_VAULTS_DECOY_ROW
    for c in range(1, COLS - 1):
        grid[MOAT][c]  = CellType.WATER
        grid[DECOY][c] = CellType.CORRIDOR

    # Anti-teleport pockets on EVERY snake row (2-5): a CORRIDOR cell at col 1 (holding an
    # unmatched ) — see below) plus a stone WALL at col 2. A {N}G goto-line teleport onto
    # any snake rung lands on that col-1 ) (the row's first-non-blank), sealed off from the
    # snake by the wall — scans ($/%/f/0/^) cross water but HALT at a wall — so it can never
    # reach the snake proper. Row 1 needs no pocket: its first-non-blank IS the snake's start
    # ( at col 4, and finishing from there already costs more than par.
    for br in (2, 3, 4, 5):
        grid[br][1] = CellType.CORRIDOR
        grid[br][2] = CellType.WALL

    # ── Place bracket CharRuns ────────────────────────────────────────────
    # Single-char CharRun at each bracket position so _bracket_at() in
    # motion.py can identify them via the character at that cell.  Row 5's ) sits
    # at EXC (one left of CLS); the exit is at CLS, so the final % lands on ) at
    # EXC and one l steps onto the exit.
    rng = random.Random(seed)
    _kinds = ('ancient', 'verdant', 'ember')

    runs: list = []
    for row in _BRACKET_VAULTS_CORR_ROWS:
        kind_open  = rng.choice(_kinds)
        kind_close = rng.choice(_kinds)
        close_col  = EXC if row == 5 else CLS
        runs.append({'row': row, 'col': OPN, 'symbols': '(', 'kind': kind_open})
        runs.append({'row': row, 'col': close_col, 'symbols': ')', 'kind': kind_close})
    # Decorative brackets on the decoy row (so it reads like the rest; they lead nowhere).
    runs.append({'row': DECOY, 'col': OPN, 'symbols': '(',
                 'kind': rng.choice(_kinds)})
    runs.append({'row': DECOY, 'col': CLS, 'symbols': ')',
                 'kind': rng.choice(_kinds)})

    # Random vocab words between the brackets on rows 1 & 5 — one CharRun per word with a
    # single-column gap between, exactly filling ( ... ) with no space against either
    # bracket. % ignores them (no brackets within) and jumps ( → ); they give the run real
    # content to span. The packer guarantees >= _WORDS_MIN words sized to the exact span.
    for wrow in (1, 5):
        close_col = EXC if wrow == 5 else CLS
        first_col = OPN + 1                         # flush against the (
        width     = close_col - first_col           # cols first_col .. close_col-1
        wc = first_col
        for w in _bracket_vaults_fill_words(rng, width, _BRACKET_VAULTS_WORDS_MIN):
            runs.append({'row': wrow, 'col': wc, 'symbols': w,
                         'kind': rng.choice(_kinds)})
            wc += len(w) + 1

    # Lone unmatched ) in each snake row's col-1 pocket (rows 2-5): it is that row's
    # first-non-blank, so a {N}G teleport lands on it. From a ) the % scan runs LEFT, hits
    # the col-0 wall and finds no match; the col-2 WALL blocks l/w/e/f/$/% rightward — so the
    # teleport is trapped in the pocket with no route to the snake or the exit.
    for br in (2, 3, 4, 5):
        runs.append({'row': br, 'col': 1, 'symbols': ')',
                     'kind': rng.choice(_kinds)})

    level = _Level(
        name='The Bracket Vaults', seed=seed,
        rows=ROWS, cols=COLS,
        cells=[''.join(_CELL_CODE[c] for c in row) for row in grid],
        spawn=_BRACKET_VAULTS_ENTRY, exit=_BRACKET_VAULTS_EXIT_POS,
        char_runs=runs,
        entities=[
            {'kind': 'exit',
             'at': [_BRACKET_VAULTS_EXIT_POS[0], _BRACKET_VAULTS_EXIT_POS[1]]},
            # Floor key on the row-2 turn cell + locked door guarding the exit: the exit can't be
            # reached by simply landing on it (a {N}G teleport is trapped in a col-1 pocket anyway),
            # and the key sits where only the snake reaches it. Pick up with x, unlock with p.
            {'kind': 'floor_key',
             'at': [_BRACKET_VAULTS_KEY_POS[0], _BRACKET_VAULTS_KEY_POS[1]]},
            {'kind': 'locked_door',
             'at': [_BRACKET_VAULTS_DOOR_POS[0], _BRACKET_VAULTS_DOOR_POS[1]]},
            # Goblins guarding the decoy pit — they punish a teleport-cheese (G/L) and can't
            # cross the moat to the snake.
            *[{'kind': 'goblin', 'at': [DECOY, gc], 'max_hp': 1, 'ai': 'chase'}
              for gc in _BRACKET_VAULTS_DECOY_GOBLINS],
        ])

    dungeon = _fmt_build(level)
    room = dungeon.rooms[0]
    par, path = _par_bracket_vaults(room, use_percent=True, return_path=True)
    if par is None:
        par, path = _BRACKET_VAULTS_PAR, _BRACKET_VAULTS_ANSWER
    room.par    = par
    room.budget = math.ceil(par * 1.4)
    room.answer = path
    return dungeon

# ── H/M/L: The Screen Vault (3 colored keys) ────────────────────────
# Viewport-filling dungeon teaching H (viewport-top), M (viewport-middle), and
# L (viewport-bottom) as distinct from G (which lands on a void row and is
# punished).
#   COLS=43, ROWS=game_h+4
#   Row 1             : wide top section (cols 1-41) — H key, 3 colored doors, exit
#   Rows 2..L_ROW     : narrow corridor (cols 1-25) — M key at M_ROW, L key at L_ROW
#   void row (L_ROW+3): G lands here (void) — punishes using G
# Three floor_keys (gold/red/blue) are randomly matched to three colored
# locked_doors per seed; par is Dijkstra-computed (_par_screen_vault).
_SCREEN_VAULT_DEFAULT_GAME_H = 33   # main._build_dungeon's default game height
_SCREEN_VAULT_COLS      = 43
_SCREEN_VAULT_H_KEY_COL = 2    # anchor col in row 1 for H (NOT col 1)
_SCREEN_VAULT_M_KEY_COL = 25   # anchor col in M_ROW; rightmost of narrow corridor
_SCREEN_VAULT_L_KEY_COL = 1    # anchor col in L_ROW; leftmost passable
_SCREEN_VAULT_DOOR_COLS = (26, 33, 39)   # locked_door cols in row 1
_SCREEN_VAULT_EXIT_COL  = 41             # exit entity col in row 1
_SCREEN_VAULT_TOP_LEFT    = (1, 1)
_SCREEN_VAULT_SPAWN     = (8, 13)
_SCREEN_VAULT_COLORS    = ('gold', 'red', 'blue')
_SCREEN_VAULT_PAR       = 17   # deterministic: 17 for every color assignment (verified in
                      # test_level_10), so it is locked rather than re-solved on
                      # every load — the par Dijkstra is expensive for this level.


def _screen_vault_key_rows(game_h: int) -> tuple:
    """Return (M_ROW, L_ROW) for a given game_h.

    H is always row 1.
    M_ROW = 1 + (game_h-1)//2  (Vim-faithful middle of passable rows 1..game_h-1).
    L_ROW = game_h - 1          (last row fully inside the viewport when vr_start=0).
    """
    m_row = 1 + (game_h - 1) // 2
    l_row = game_h - 1
    return m_row, l_row


def _par_screen_vault(composite, return_path: bool = False):
    """Minimum-keystroke Dijkstra for the Screen Vault (3 colored keys).

    State = (row, col, inv, key_alive, doors) where:
      inv      : 0=none, 1=H key held, 2=M key held, 3=L key held
      key_alive: 3-bit mask (bit0=H key on floor, bit1=M key on floor, bit2=L key)
      doors    : 3-bit mask (bit0=door0 open, bit1=door1 open, bit2=door2 open)
    Goal: position == EXIT_POS with all doors open (doors==7).

    H/M/L are modelled viewport-relative.
    """
    game_h = composite._game_h
    m_row, l_row = _screen_vault_key_rows(game_h)
    ROWS, COLS = composite.rows, composite.cols
    BASE_ROW = composite.first_standable_row()    # line N → grid row BASE_ROW + N - 1
    H_COL  = _SCREEN_VAULT_H_KEY_COL
    M_COL  = _SCREEN_VAULT_M_KEY_COL
    L_COL  = _SCREEN_VAULT_L_KEY_COL
    D_COLS = _SCREEN_VAULT_DOOR_COLS
    EX     = (_SCREEN_VAULT_TOP_LEFT[0], _SCREEN_VAULT_EXIT_COL)
    entry  = composite.spawn_pos

    door_key = composite._door_key  # door_key[d] = inv value (1/2/3) that opens door d

    _door_cells = {(1, dc): di for di, dc in enumerate(D_COLS)}
    _ok_cache: dict = {}
    def _ok(r, c, doors):
        key = (r, c, doors)
        cached = _ok_cache.get(key)
        if cached is not None:
            return cached
        if not (0 <= r < ROWS and 0 <= c < COLS):
            res = False
        elif composite.cells[r][c] not in (CellType.CORRIDOR, CellType.FLOOR):
            res = False
        else:
            di = _door_cells.get((r, c))
            res = not (di is not None and not (doors >> di & 1))
        _ok_cache[key] = res
        return res

    # _fnb_simple / _hml_targets depend only on (row, doors) with doors in 0..7,
    # so memoize them — they are hit O(rows) times per Dijkstra state otherwise.
    _fnb_cache: dict = {}
    def _fnb_simple(row, doors):
        key = (row, doors)
        if key in _fnb_cache:
            return _fnb_cache[key]
        left = None
        for col in range(COLS):
            if _ok(row, col, doors):
                if left is None:
                    left = col
                if composite.char_run_at(row, col) is not None:
                    left = col
                    break
        _fnb_cache[key] = left
        return left

    _hml_cache: dict = {}
    def _hml_targets(r, doors):
        key = (r, doors)
        if key in _hml_cache:
            return _hml_cache[key]
        vr_s = max(0, min(r - game_h // 2, ROWS - game_h))
        prows = [_r for _r in range(vr_s, min(vr_s + game_h, ROWS))
                 if _fnb_simple(_r, doors) is not None]
        res = (None, None, None) if not prows else (prows[0], prows[len(prows) // 2], prows[-1])
        _hml_cache[key] = res
        return res

    start = (composite.spawn_pos[0], composite.spawn_pos[1], 0, 0b111, 0)
    dist  = {start: 0}
    prev  = {start: None}
    heap  = [(0, start)]
    max_n = max(ROWS, COLS)

    while heap:
        cost, state = heapq.heappop(heap)
        r, c, inv, ka, doors = state

        if (r, c) == EX and doors == 0b111:
            if return_path:
                return cost, _join_path(prev, state, merge_single=False)
            return cost

        if cost > dist.get(state, float('inf')):
            continue

        def _try(nb, mc, lbl):
            g = cost + mc
            if g < dist.get(nb, float('inf')):
                dist[nb] = g
                prev[nb] = (state, lbl)
                heapq.heappush(heap, (g, nb))

        # x: collect key at current position (replaces register)
        for key_inv, key_row, key_col, key_bit in (
            (1, 1,     H_COL, 1),
            (2, m_row, M_COL, 2),
            (3, l_row, L_COL, 4),
        ):
            if (r, c) == (key_row, key_col) and (ka & key_bit):
                _try((r, c, key_inv, ka & ~key_bit, doors), 1, 'x')

        # p: unlock door to right — and step ONTO it (paste moves the cursor over)
        for di, dc in enumerate(D_COLS):
            if (r, c + 1) == (1, dc) and not (doors >> di & 1) and inv == door_key[di]:
                _try((1, dc, 0, ka, doors | (1 << di)), 1, 'p')
        # P: unlock door to left — and step onto it
        for di, dc in enumerate(D_COLS):
            if (r, c - 1) == (1, dc) and not (doors >> di & 1) and inv == door_key[di]:
                _try((1, dc, 0, ka, doors | (1 << di)), 1, 'P')

        # H, M, L (viewport-relative)
        ht, mt, lt = _hml_targets(r, doors)
        for trow, lbl in ((ht, 'H'), (mt, 'M'), (lt, 'L')):
            if trow is None:
                continue
            tc = _fnb_simple(trow, doors)
            if tc is not None and (trow, tc) != (r, c):
                _try((trow, tc, inv, ka, doors), 1, lbl)

        # gg
        er, ec = entry
        if _ok(er, ec, doors):
            _try((er, ec, inv, ka, doors), 2, 'gg')

        # G: jump to last passable row, first non-blank col
        for tr in range(ROWS - 1, -1, -1):
            fc = _fnb_simple(tr, doors)
            if fc is not None:
                if (tr, fc) != (r, c):
                    _try((tr, fc, inv, ka, doors), 1, 'G')
                break

        # nG — line n → grid row BASE_ROW + n - 1 (the border isn't a line)
        for n in range(1, ROWS + 1):
            tr2 = BASE_ROW + n - 1
            if tr2 >= ROWS:
                break
            fc2 = _fnb_simple(tr2, doors)
            if fc2 is None or (tr2, fc2) == (r, c):
                continue
            _try((tr2, fc2, inv, ka, doors), len(str(n)) + 1, f'{n}G')

        # $: last passable going right
        end_c = None
        for tc in range(c + 1, COLS):
            if not _ok(r, tc, doors):
                break
            end_c = tc
        if end_c is not None:
            _try((r, end_c, inv, ka, doors), 1, '$')

        # 0: first passable going left
        start_c = None
        for tc in range(c - 1, -1, -1):
            if not _ok(r, tc, doors):
                break
            start_c = tc
        if start_c is not None:
            _try((r, start_c, inv, ka, doors), 1, '0')

        # ^: first non-blank col
        fnb = _fnb_simple(r, doors)
        if fnb is not None and fnb != c:
            _try((r, fnb, inv, ka, doors), 1, '^')

        # hjkl and count-hjkl
        for dr, dc_dir, key in ((0, -1, 'h'), (0, 1, 'l'), (1, 0, 'j'), (-1, 0, 'k')):
            for n in range(1, max_n + 1):
                nr2 = r + dr * n
                nc2 = c + dc_dir * n
                if not _ok(nr2, nc2, doors):
                    break
                mc2  = 1 if n == 1 else len(str(n)) + 1
                lbl2 = key if n == 1 else f'{n}{key}'
                _try((nr2, nc2, inv, ka, doors), mc2, lbl2)

    if return_path:
        best_cost, best_state = float('inf'), None
        for s2, d2 in dist.items():
            if (s2[0], s2[1]) == EX and s2[4] == 0b111 and d2 < best_cost:
                best_cost, best_state = d2, s2
        if best_state:
            return best_cost, _join_path(prev, best_state, merge_single=False)
        return None, ''
    return None


def build_dungeon_screen_vault(seed: int, game_h: int = _SCREEN_VAULT_DEFAULT_GAME_H,
                     compute_answer: bool = True) -> Dungeon:
    """H M L: The Screen Vault (3 colored keys).

    Viewport-filling dungeon that teaches H (viewport-top), M (viewport-middle),
    and L (viewport-bottom) as distinct from G (room-last-row = void, punished).

    Layout: COLS=43, ROWS=game_h+4
      Row 0          : wall border
      Row 1          : wide top section (cols 1-41) — H key, 3 locked doors, exit
      Rows 2..L_ROW  : narrow corridor (cols 1-25) — M key at M_ROW, L key at L_ROW
      L_ROW+1..+2    : extra narrow corridor (below the viewport)
      L_ROW+3        : void rune row — G lands here; using G is punished
      L_ROW+4        : wall border

    Three floor_keys (gold/red/blue, randomly assigned) unlock three colored
    locked_doors in the top section.  Par is 17 for every color assignment.

    Par is locked (`_SCREEN_VAULT_PAR`) instead of re-solved on every load; the full answer
    path (admin-only) is solved lazily via ``compute_answer``.
    """
    dungeon = Dungeon(name='The Screen Vault', seed=seed)
    ROWS   = game_h + 4
    COLS   = _SCREEN_VAULT_COLS
    m_row, l_row = _screen_vault_key_rows(game_h)

    rng = random.Random(seed)

    cells = [[CellType.WALL] * COLS for _ in range(ROWS)]
    composite = Room(rows=ROWS, cols=COLS, room_type=RoomType.ENTRY)
    composite.cells = cells
    composite.seed  = seed
    composite._game_h = game_h

    # ── Carve cells ───────────────────────────────────────────────────────────
    # Row 1: wide top section (cols 1-41, all CORRIDOR)
    for c in range(1, 42):
        cells[1][c] = CellType.CORRIDOR
    # Row 2: transition — cols 1-25 open, 26-42 wall
    for c in range(1, 26):
        cells[2][c] = CellType.CORRIDOR
    # Rows 3 .. l_row+2: narrow corridor cols 1-25
    for r in range(3, l_row + 3):
        for c in range(1, 26):
            cells[r][c] = CellType.CORRIDOR
    # Void rune row: CORRIDOR cells (void runes placed as character runs below)
    void_row = l_row + 3
    for c in range(1, 26):
        cells[void_row][c] = CellType.CORRIDOR

    # ── Color assignment ──────────────────────────────────────────────────────
    colors = list(_SCREEN_VAULT_COLORS)
    key_colors  = colors[:]
    rng.shuffle(key_colors)   # key_colors[0]=H key, [1]=M key, [2]=L key
    door_colors = colors[:]
    rng.shuffle(door_colors)  # door_colors[0]=door0, [1]=door1, [2]=door2

    inv_for_color = {c: i + 1 for i, c in enumerate(key_colors)}
    composite._door_key = [inv_for_color[dc] for dc in door_colors]

    # ── Entities: keys, doors, exit ───────────────────────────────────────────
    composite.entities = [
        Entity(kind='floor_key',   row=1,     col=_SCREEN_VAULT_H_KEY_COL, tag=key_colors[0]),
        Entity(kind='floor_key',   row=m_row, col=_SCREEN_VAULT_M_KEY_COL, tag=key_colors[1]),
        Entity(kind='floor_key',   row=l_row, col=_SCREEN_VAULT_L_KEY_COL, tag=key_colors[2]),
        Entity(kind='locked_door', row=1, col=_SCREEN_VAULT_DOOR_COLS[0],  tag=door_colors[0]),
        Entity(kind='locked_door', row=1, col=_SCREEN_VAULT_DOOR_COLS[1],  tag=door_colors[1]),
        Entity(kind='locked_door', row=1, col=_SCREEN_VAULT_DOOR_COLS[2],  tag=door_colors[2]),
        Entity(kind='exit',        row=1, col=_SCREEN_VAULT_EXIT_COL),
    ]

    # ── Characters ──────────────────────────────────────────────────────────
    _load_vocab_tables()
    plain = _VOCAB_PLAIN_BY_LEN
    kinds  = ('ancient', 'verdant', 'ember')
    blocked: set = set()

    # Anchor characters at key positions (so H/M/L fnb returns the key col)
    for anchor_row, anchor_col in (
        (1,     _SCREEN_VAULT_H_KEY_COL),
        (m_row, _SCREEN_VAULT_M_KEY_COL),
        (l_row, _SCREEN_VAULT_L_KEY_COL),
    ):
        sym = rng.choice([('∘',), ('·',), ('⊙',), ('∙',)])
        composite.char_runs.append(CharRun(row=anchor_row, col=anchor_col,
                                           symbols=sym, kind=rng.choice(kinds)))
        blocked.add((anchor_row, anchor_col))

    # Row 1: vocab characters only in the left section (before the first door); the
    # door-bounded corridor (cols 27-40, up to the exit) is left clear.
    for zone_start, zone_end in ((3, 25),):
        c = zone_start
        while c <= zone_end:
            if (1, c) in blocked:
                c += 1
                continue
            max_len = min(5, zone_end - c + 1)
            if max_len < 1:
                break
            wlen = rng.randint(1, max_len)
            words = (plain or {}).get(wlen, [])
            if not words:
                c += 1
                continue
            word = rng.choice(words)
            composite.char_runs.append(CharRun(row=1, col=c,
                                               symbols=tuple(word),
                                               kind=rng.choice(kinds)))
            for i in range(len(word)):
                blocked.add((1, c + i))
            c += len(word) + rng.randint(1, 2)

    # Narrow corridor rows: vocab characters.  The M row IS filled (cols 1-24), so M
    # lands on the leftmost character and the player must then $ to reach the M key
    # at col 25 — i.e. "M $", not just "M".
    for row in range(2, l_row + 3):
        c = 1
        while c <= 25:
            if (row, c) in blocked:
                c += 1
                continue
            if row == _SCREEN_VAULT_SPAWN[0] and abs(c - _SCREEN_VAULT_SPAWN[1]) <= 1:
                c += 2
                continue
            max_len = min(4, 26 - c)
            if max_len < 1:
                break
            wlen = rng.randint(1, max_len)
            words = (plain or {}).get(wlen, [])
            if not words:
                c += 1
                continue
            word = rng.choice(words)
            if any((row, c + i) in blocked for i in range(len(word))):
                c += 1
                continue
            composite.char_runs.append(CharRun(row=row, col=c,
                                               symbols=tuple(word),
                                               kind=rng.choice(kinds)))
            for i in range(len(word)):
                blocked.add((row, c + i))
            c += len(word) + rng.randint(1, 3)

    # Void rune row: standard void runes (○) across cols 1-25 — where G lands.
    for c in range(1, 26):
        composite.char_runs.append(CharRun(row=void_row, col=c,
                                           symbols=('○',), kind='void'))

    # ── Entry / spawn / exit ──────────────────────────────────────────────────
    composite.spawn_pos = _SCREEN_VAULT_SPAWN
    composite.exit_pos  = (1, _SCREEN_VAULT_EXIT_COL)

    composite.rebuild_indexes()

    # ── Par / answer ──────────────────────────────────────────────────────────
    # Par is locked at _SCREEN_VAULT_PAR (deterministic).  The answer path is only
    # shown to admin, so solve for it only when compute_answer is set — the
    # Dijkstra is too slow to run on every load.  The solver's own cost rides
    # along as _solver_par so the par-lock test can verify without re-solving.
    composite.par    = _SCREEN_VAULT_PAR
    composite.budget = math.ceil(_SCREEN_VAULT_PAR * 1.4)
    if compute_answer:
        composite._solver_par, composite.answer = _par_screen_vault(composite, return_path=True)
    else:
        composite.answer = ''

    dungeon.rooms        = [composite]
    dungeon.current_room = 0
    return dungeon


# ── The Runic Archives layout constants ─────────────────────────────────────────────────
# Room: 22 rows × 48 cols.  Main area cols 1–42; side room row 15 cols 43–46.
#
# Blank rows (passable, no character runs): 1, 3, 5, 9, 15, 17, 19.
# Content rows (≥1 character run): 2, 4, 6, 7, 8, 10, 11, 12, 13, 14, 16, 18, 20.
#
# Key mechanic:
#   floor_key at (5,1)  — blank row above code block (rows 6–8 all non-blank).
#   locked_door at (15,43) — right-wall position at door row.
#   exit at (15,46) — inside side room.
#   void at (20,1) — prevents } from exiting safely.
#
# Navigation: rows 6-8 are all non-blank (three-row code block), so a single {
# from the spawn on blank row 9 skips them and lands at blank row 5 (key).  Key
# is 10 rows above door row 15, so count-j navigation costs 10j (3 ks) vs } }
# (2 ks) — making brace jumps strictly cheaper.
#
# Optimal path (par=7):  { x } } $ p $
#   Spawn (9,20): { → (5,1) [key; rows 6-8 non-blank, skipped].
#                 x picks up key.
#                 } → (9,1)  } → (15,1) [door row].
#                 $ → (15,42) [locked_door at 43 blocks $].
#                 p unlocks door at (15,43).  $ → (15,46) EXIT.

_RUNIC_ARCHIVES_ROWS     = 22
_RUNIC_ARCHIVES_COLS     = 48        # main 44 (cols 0–43) + side room 4 (cols 44–47)
_RUNIC_ARCHIVES_ENTRY    = (9, 20)   # spawn position
_RUNIC_ARCHIVES_EXIT     = (15, 46)  # exit entity (inside side room)
_RUNIC_ARCHIVES_KEY_POS  = (5, 1)    # floor_key entity (blank row above code block)
_RUNIC_ARCHIVES_DOOR_POS = (15, 43)  # locked_door entity
_RUNIC_ARCHIVES_VOID_POS = (20, 1)   # void rune
_RUNIC_ARCHIVES_PAR      = 7
_RUNIC_ARCHIVES_ANSWER   = '{ x } } $ p $'

# ── The Sentence Corridor constants ────────────────────────────────
# Without (/): wall gaps (cols 11-22 and 37-48) block all l/h/w paths.
#              Player trapped in S1 (cols 1-10).  Cost = infinity >> budget.

_SENTENCE_CORRIDOR_ROWS     = 5
_SENTENCE_CORRIDOR_COLS     = 73
_SENTENCE_CORRIDOR_ENTRY    = (1, 1)          # spawn: start of sentence 1
_SENTENCE_CORRIDOR_EXIT     = (1, 71)         # exit: just past the locked door
_SENTENCE_CORRIDOR_DOOR_POS = (1, 70)         # locked_door at the END of sentence 3
_SENTENCE_CORRIDOR_KEY_POS  = (3, 69)         # floor_key at the END of sentence 5
_SENTENCE_CORRIDOR_SEP_ROW  = 2              # all-wall stone row between the two sentence rows

# Five sentences (each one CharRun spanning its columns; terminator last):
#   row 1:  S1 ·gap· S2 ·gap· S3 [door][exit]
#   row 3:  S4 ·gap· S5 [key]
# S3 (3rd of row 1) and S5 (2nd of row 3) sit behind wall-gaps, so the line /
# screen jumps the player already knows (G gg {n}G H M L) reach only a row's FIRST
# sentence — ) is the sole way onto them.  { / } would otherwise cross rows and
# undercut ( as the backtrack, so a void trap line above S1 neutralises them.
_SENTENCE_CORRIDOR_SENTENCES = [
    (1, 1,  'A sentence is one stride.'),
    (1, 29, 'Where does it end?'),
    (1, 50, 'At a dot, or a bang!'),
    (3, 8,  'I cut each stone to fit.'),
    (3, 40, 'A good joint needs no mortar.'),
]


def _par_runic_archives(composite, return_path=False,
                      disable_brace=False):
    """Minimum-keystroke Dijkstra for Paragraph Jumps (The Runic Archives).

    State = (row, col, has_key, door_open) where:
      has_key:   0 = key on floor, 1 = key held
      door_open: 0 = locked_door blocking, 1 = door removed

    Available motions: hjkl, count-hjkl, 0, $, { } (unless disable_brace), x, p.
    """
    ROWS, COLS = composite.rows, composite.cols
    KR, KC = _RUNIC_ARCHIVES_KEY_POS
    DR, DC = _RUNIC_ARCHIVES_DOOR_POS
    EX     = _RUNIC_ARCHIVES_EXIT
    entry  = composite.spawn_pos
    max_n  = max(ROWS, COLS)

    def _ok(r, c, door_open):
        if not (0 <= r < ROWS and 0 <= c < COLS):
            return False
        if composite.cells[r][c] not in (CellType.CORRIDOR, CellType.FLOOR):
            return False
        if (r, c) == (DR, DC) and not door_open:
            return False
        ru = composite.char_run_at(r, c)
        return not (ru and ru.kind == 'void')

    def _row_blank(row, door_open):
        has_pass = any(_ok(row, cc, door_open) for cc in range(COLS))
        has_rune = any(composite.char_run_at(row, cc) is not None for cc in range(COLS))
        return has_pass and not has_rune

    def _leftmost_pass(row, door_open):
        for cc in range(COLS):
            if _ok(row, cc, door_open):
                return cc
        return None

    def _para_fwd(r, door_open):
        for nr in range(r + 1, ROWS):
            if _row_blank(nr, door_open):
                lp = _leftmost_pass(nr, door_open)
                if lp is not None:
                    return (nr, lp)
        prows = [rr for rr in range(ROWS) if _leftmost_pass(rr, door_open) is not None]
        if prows:
            tr, cur_lp = prows[-1], _leftmost_pass(r, door_open)
            lp = _leftmost_pass(tr, door_open)
            if lp is not None and (tr, lp) != (r, cur_lp):
                return (tr, lp)
        return None

    def _para_bwd(r, door_open):
        for nr in range(r - 1, -1, -1):
            if _row_blank(nr, door_open):
                lp = _leftmost_pass(nr, door_open)
                if lp is not None:
                    return (nr, lp)
        prows = [rr for rr in range(ROWS) if _leftmost_pass(rr, door_open) is not None]
        if prows:
            tr, cur_lp = prows[0], _leftmost_pass(r, door_open)
            lp = _leftmost_pass(tr, door_open)
            if lp is not None and (tr, lp) != (r, cur_lp):
                return (tr, lp)
        return None

    start = (entry[0], entry[1], 0, 0)
    dist  = {start: 0}
    prev  = {start: None}
    heap  = [(0, start)]

    while heap:
        cost, state = heapq.heappop(heap)
        r, c, hk, do = state

        if (r, c) == EX:
            if return_path:
                return cost, _join_path(prev, state, merge_single=False)
            return cost

        if cost > dist.get(state, float('inf')):
            continue

        def _try(nb, mc, lbl):
            g = cost + mc
            if g < dist.get(nb, float('inf')):
                dist[nb] = g
                prev[nb] = (state, lbl)
                heapq.heappush(heap, (g, nb))

        # x: pick up floor_key
        if (r, c) == (KR, KC) and hk == 0:
            _try((r, c, 1, do), 1, 'x')

        # p: use key on locked_door to the right
        if (r, c + 1) == (DR, DC) and hk == 1 and do == 0:
            _try((r, c, 0, 1), 1, 'p')

        # { } paragraph jumps
        if not disable_brace:
            fwd = _para_fwd(r, do)
            if fwd and fwd != (r, c):
                _try((fwd[0], fwd[1], hk, do), 1, '}')
            bwd = _para_bwd(r, do)
            if bwd and bwd != (r, c):
                _try((bwd[0], bwd[1], hk, do), 1, '{')

        # hjkl and count-hjkl
        for _dr, _dc, _key in ((0, -1, 'h'), (0, 1, 'l'), (1, 0, 'j'), (-1, 0, 'k')):
            for n in range(1, max_n + 1):
                nr2 = r + _dr * n
                nc2 = c + _dc * n
                if not _ok(nr2, nc2, do):
                    break
                mc2  = 1 if n == 1 else len(str(n)) + 1
                lbl2 = _key if n == 1 else f'{n}{_key}'
                _try((nr2, nc2, hk, do), mc2, lbl2)

        # gg / G / {n}G — the line jumps, under this solver's own door state
        for jr, jc, jcost, jlbl in _line_jump_moves(
                composite, lambda rr, cc: _ok(rr, cc, do), r, c):
            _try((jr, jc, hk, do), jcost, jlbl)

        # $: scan right to last passable cell
        end_c = None
        for tc in range(c + 1, COLS):
            if not _ok(r, tc, do):
                break
            end_c = tc
        if end_c is not None:
            _try((r, end_c, hk, do), 1, '$')

        # 0: scan left to first passable cell
        start_c = None
        for tc in range(c - 1, -1, -1):
            if not _ok(r, tc, do):
                break
            start_c = tc
        if start_c is not None:
            _try((r, start_c, hk, do), 1, '0')

    if return_path:
        best_cost, best_state = float('inf'), None
        for s2, d2 in dist.items():
            if (s2[0], s2[1]) == EX and d2 < best_cost:
                best_cost, best_state = d2, s2
        if best_state:
            return best_cost, _join_path(prev, best_state, merge_single=False)
        return None, ''
    return None


# ── G/gg: The Lineheads ─────────────────────────────────────────
# 16-row × 11-col vertical shaft teaching G (last line), gg (first line), and
# {n}G (nth line).
#
# Layout:
#   Row 1     : top corridor cols 1-9; start (1,1), exit (1,9);
#               locked_doors at (1,3) and (1,6) gate the corridor
#   Row 2     : cols 1-2, 4-5, 7-9 (walls at 3,6 — under the doors), so the two
#               doors are the ONLY horizontal crossings of the top
#   Rows 3-14 : a 2-wide left shaft (cols 1-2)
#   floor_keys: (4,1) and (14,2) — buried near the top and bottom of the shaft
#
# The two doors are COLORED in a fixed sequence (left=gold at (1,3), right=red at
# (1,6)); the two key COLORS are shuffled per seed, so each key opens exactly one
# door and which shaft-key matches which door varies.  Only ONE key is held at a
# time (x overwrites the register), and the left door must open before the right is
# reachable, so the solve is: fetch the gold key (wherever it landed), open the left
# door (stepping onto it), fetch the red key, open the right, reach the exit —
# riding the shaft with G (→ row 14), {n}G, and gg (→ row 1).  Par/answer are
# computed by _par_lineheads (colored key/door + line-jump model).
_LINEHEADS_ROWS   = 16
_LINEHEADS_COLS   = 11
_LINEHEADS_ENTRY  = (1, 1)             # spawn / first line
_LINEHEADS_EXIT   = (1, 9)             # exit entity == exit_pos (top-right)
_LINEHEADS_KEYS   = ((4, 1), (14, 2))  # floor_key positions
_LINEHEADS_DOORS  = ((1, 3), (1, 6))   # locked_door positions (left→right)
_LINEHEADS_COLORS = ('gold', 'red')    # fixed door sequence: door0=(1,3)=gold, door1=(1,6)=red
# Passable columns per row (every other cell is WALL):
_LINEHEADS_PASSABLE = {
    1: tuple(range(1, 10)),               # top corridor cols 1-9
    2: (1, 2, 4, 5, 7, 8, 9),             # walls at 3,6 under the doors
    **{r: (1, 2) for r in range(3, 15)},  # 2-wide left shaft, rows 3-14
}


def _par_lineheads(composite, return_path: bool = False,
                      disable_line_jumps: bool = False):
    """Minimum-keystroke Dijkstra for The Lineheads.

    Models the vertical key/door shaft with the commands a Level-8 player has:
      hjkl + count-hjkl, 0 / $ / ^ (1 ks each),
      G  (1 ks)  → last line, first-non-blank col,
      gg (2 ks)  → first line, first-non-blank col (mirror of G),
      {n}G (len(str(n))+1 ks) → line n, scanning down to a passable row, fnb col,
      x  (1 ks)  → pick up the floor_key here (overwrites the single register slot),
      p / P (1 ks) → open the locked_door to the right / left, consuming the key.
    Word/find motions are degenerate here (the room has no runes) and are omitted.

    State = (row, col, keys_mask, holding, doors_mask):
      keys_mask  — bit i set ⇒ key i still on the floor
      holding    — 1 ⇒ a key is held in the register, else 0
      doors_mask — bit i set ⇒ door i is open
    Goal: reach _LINEHEADS_EXIT (only reachable once both doors are open).
    """
    ROWS, COLS = composite.rows, composite.cols
    BASE_ROW = composite.first_standable_row()    # line N → grid row BASE_ROW + N - 1
    entry = composite.spawn_pos
    keys  = _LINEHEADS_KEYS
    doors = _LINEHEADS_DOORS
    EX    = _LINEHEADS_EXIT
    max_n = max(ROWS, COLS)
    FULL_KEYS  = (1 << len(keys)) - 1
    door_index = {d: i for i, d in enumerate(doors)}
    door_key   = composite._lgg_door_key   # door_key[di] = hold value (1/2) that opens door di

    def _ok(r, c, dm):
        if not (0 <= r < ROWS and 0 <= c < COLS):
            return False
        if composite.cells[r][c] not in (CellType.CORRIDOR, CellType.FLOOR):
            return False
        di = door_index.get((r, c))
        if di is not None and not (dm >> di & 1):
            return False          # closed locked_door blocks
        ru = composite.char_run_at(r, c)
        return not (ru and ru.kind == 'void')

    def _fnb(row, dm, km):
        """First-non-blank col — mirrors motion._first_non_blank_col + _caret_stop:
        stop on the first character OR a still-on-floor key (a notable, non-caret-
        transparent entity), else the leftmost passable col; None if the row has no
        passable cell. A key already picked up (its km bit cleared) no longer stops
        the caret — exactly as the engine deletes it from the room on `x`."""
        on_floor = {keys[i] for i in range(len(keys)) if km >> i & 1}
        left = None
        for c in range(COLS):
            if _ok(row, c, dm):
                if left is None:
                    left = c
                if composite.char_run_at(row, c) is not None or (row, c) in on_floor:
                    return c
        return left

    start = (entry[0], entry[1], FULL_KEYS, 0, 0)
    dist  = {start: 0}
    prev  = {start: None}
    heap  = [(0, start)]

    while heap:
        cost, state = heapq.heappop(heap)
        r, c, km, hold, dm = state

        if (r, c) == EX:
            if return_path:
                return cost, _join_path(prev, state, merge_single=False)
            return cost
        if cost > dist.get(state, float('inf')):
            continue

        def _try(nb, mc, lbl):
            g = cost + mc
            if g < dist.get(nb, float('inf')):
                dist[nb] = g
                prev[nb] = (state, lbl)
                heapq.heappush(heap, (g, nb))

        # x: pick up a floor_key here (sets the held key's index; overwrites)
        for ki, kp in enumerate(keys):
            if (r, c) == kp and (km >> ki & 1):
                _try((r, c, km & ~(1 << ki), ki + 1, dm), 1, 'x')

        # p / P: open an adjacent locked_door IF the held key matches its color;
        # the key is consumed and the cursor steps ONTO the door (paste moves you over)
        for di, dp in enumerate(doors):
            if (dm >> di & 1) or hold != door_key[di]:
                continue
            if (r, c + 1) == dp:
                _try((dp[0], dp[1], km, 0, dm | (1 << di)), 1, 'p')
            if (r, c - 1) == dp:
                _try((dp[0], dp[1], km, 0, dm | (1 << di)), 1, 'P')

        if not disable_line_jumps:
            # G: last line (scan up to a passable row), land on first-non-blank
            for rr in range(ROWS - 1, -1, -1):
                gc = _fnb(rr, dm, km)
                if gc is not None:
                    if (rr, gc) != (r, c):
                        _try((rr, gc, km, hold, dm), 1, 'G')
                    break

            # gg: first line (scan down to a passable row), land on first-non-blank (2 ks)
            for rr in range(ROWS):
                gc = _fnb(rr, dm, km)
                if gc is not None:
                    if (rr, gc) != (r, c):
                        _try((rr, gc, km, hold, dm), 2, 'gg')
                    break

            # {n}G: line n (1-based) → grid row BASE_ROW + n - 1 (border isn't a line),
            # scanning down to a passable row, fnb
            for n in range(1, ROWS + 1):
                rr = BASE_ROW + n - 1
                while rr < ROWS and _fnb(rr, dm, km) is None:
                    rr += 1
                if rr >= ROWS:
                    continue
                tc = _fnb(rr, dm, km)
                if (rr, tc) != (r, c):
                    _try((rr, tc, km, hold, dm), len(str(n)) + 1, f'{n}G')

        # hjkl + count-hjkl
        for dr, dc, key in ((0, -1, 'h'), (0, 1, 'l'), (1, 0, 'j'), (-1, 0, 'k')):
            for n in range(1, max_n + 1):
                nr2, nc2 = r + dr * n, c + dc * n
                if not _ok(nr2, nc2, dm):
                    break
                mc2  = 1 if n == 1 else len(str(n)) + 1
                lbl2 = key if n == 1 else f'{n}{key}'
                _try((nr2, nc2, km, hold, dm), mc2, lbl2)

        # $ / 0 / ^: horizontal jumps within the row
        end_c = None
        for tc in range(c + 1, COLS):
            if not _ok(r, tc, dm):
                break
            end_c = tc
        if end_c is not None:
            _try((r, end_c, km, hold, dm), 1, '$')
        st_c = None
        for tc in range(c - 1, -1, -1):
            if not _ok(r, tc, dm):
                break
            st_c = tc
        if st_c is not None:
            _try((r, st_c, km, hold, dm), 1, '0')
        fb = _fnb(r, dm, km)
        if fb is not None and fb != c:
            _try((r, fb, km, hold, dm), 1, '^')

    return (None, '') if return_path else None


def build_dungeon_lineheads(seed: int) -> 'Dungeon':
    """G gg {n}G: The Lineheads.

    A 16-row × 11-col vertical shaft.  The exit sits on the top row behind two locked doors; the two keys
    are buried near the top and bottom of a 2-wide left shaft, so the player
    rides G / gg / {n}G up and down to fetch a key, open its matching colored door
    (stepping onto it), and repeat.  Geometry is fixed; the two key COLORS are
    shuffled per seed (doors are a fixed gold→red sequence), so the fetch order —
    and the par — varies with the seed.  See the _LINEHEADS_* block above for geometry.

    Par/answer are computed by _par_lineheads (colored key/door + line-jump model).
    """
    from vimny.engine.editor import _CELL_CODE
    from vimny.sharing.format import Level as _Level, build as _fmt_build
    ROWS, COLS = _LINEHEADS_ROWS, _LINEHEADS_COLS

    cells = [[CellType.WALL] * COLS for _ in range(ROWS)]
    # ── Carve the fixed layout (see _LINEHEADS_PASSABLE above) ──────────────────────
    for row, passable_cols in _LINEHEADS_PASSABLE.items():
        for c in passable_cols:
            cells[row][c] = CellType.CORRIDOR

    # ── Entry / exit / keys / doors ───────────────────────────────────────────
    # Doors are a fixed color sequence (left=gold, right=red); the key colors are
    # shuffled per seed, so which shaft-key opens which door — and the order you
    # ride the shaft to fetch them — varies.
    rng = random.Random(seed)
    door_colors = list(_LINEHEADS_COLORS)                            # door0=(1,3)=gold, door1=(1,6)=red
    key_colors  = list(_LINEHEADS_COLORS); rng.shuffle(key_colors)   # key0=(4,1), key1=(14,2)
    inv_for_color = {col: ki + 1 for ki, col in enumerate(key_colors)}
    lgg_door_key = [inv_for_color[dc] for dc in door_colors]
    entities = [{'kind': 'exit',
                 'at': [_LINEHEADS_EXIT[0], _LINEHEADS_EXIT[1]]}]
    for ki, (kr, kc) in enumerate(_LINEHEADS_KEYS):
        entities.append({'kind': 'floor_key', 'at': [kr, kc], 'tag': key_colors[ki]})
    for di, (dr, dc) in enumerate(_LINEHEADS_DOORS):
        entities.append({'kind': 'locked_door', 'at': [dr, dc],
                         'tag': door_colors[di], 'opaque': True})

    level = _Level(
        name='The Lineheads', seed=seed,
        rows=ROWS, cols=COLS,
        cells=[''.join(_CELL_CODE[c] for c in row) for row in cells],
        spawn=_LINEHEADS_ENTRY, exit=_LINEHEADS_EXIT,
        char_runs=[],                       # no seed-varying runes; layout fixed
        entities=entities)

    dungeon = _fmt_build(level)
    room = dungeon.rooms[0]
    room._lgg_door_key = lgg_door_key

    # ── Compute par via Dijkstra (key/door + line-jump model) ─────────────────
    par, path = _par_lineheads(room, return_path=True)
    if par is None:                      # fixed map — should always solve
        raise RuntimeError('The Lineheads is unsolvable — check layout')
    room.par    = par
    room.budget = math.ceil(par * 1.4)
    room.answer = path
    return dungeon


def build_dungeon_runic_archives(seed: int) -> 'Dungeon':
    """Paragraph Jumps: The Runic Archives.

    Layout: 22 rows × 48 cols.
    Main area: rows 1–20, cols 1–42.  Side room: row 15, cols 43–46.

    Blank rows (no character runs): 1, 3, 5, 9, 15, 17, 19.
    Content rows (≥1 character run): 2, 4, 6, 7, 8, 10–14, 16, 18, 20.

    floor_key at (5,1) — blank row above the three-row code block (6-8).
    locked_door at (15,43) — right wall of main room at door row.
    exit at (15,46) — inside side room.

    Optimal path (par=7):  { x } } $ p $   (spawn (9,20), a blank row)
    """
    from vimny.engine.editor import _CELL_CODE
    from vimny.sharing.format import Level as _Level, build as _fmt_build
    ROWS, COLS = _RUNIC_ARCHIVES_ROWS, _RUNIC_ARCHIVES_COLS

    cells = [[CellType.WALL] * COLS for _ in range(ROWS)]
    # Main area: rows 1–20, cols 1–42
    for r in range(1, 21):
        for c in range(1, 43):
            cells[r][c] = CellType.CORRIDOR

    # Side room: row 15 cols 43–46 (door cell + interior)
    for c in range(43, 47):
        cells[15][c] = CellType.CORRIDOR

    # Character content
    _load_vocab_tables()
    plain = _VOCAB_PLAIN_BY_LEN
    rng   = random.Random(seed)
    runes: list = []

    def _fill_row(row, col_start=2, col_end=41, skip_cols=()):
        c = col_start
        first = True
        while c <= col_end:
            if c in skip_cols:
                c += 1
                continue
            if first or rng.random() < 0.40:
                kind    = rng.choice(_WORD_RUNE_KINDS)
                max_len = min(4 if first else 6, col_end - c + 1)
                length  = rng.randint(2, max(2, max_len))
                word    = rng.choice(plain.get(length) or plain[3])
                syms    = tuple(word)
                w = len(syms)
                if (c + w - 1 <= col_end
                        and not any(sk in range(c, c + w) for sk in skip_cols)):
                    runes.append({'row': row, 'col': c,
                                  'symbols': ''.join(syms), 'kind': kind})
                    c += w + rng.randint(2, 3)
                    first = False
                    continue
            c += 1

    # Para 1 (rows 2, 4); code block rows 6-8 (all non-blank forces
    # second { to skip row 7 and land at blank row 5 where key is).
    for r in (2, 4, 6, 7, 8):
        _fill_row(r)
    _fill_row(10, skip_cols=(20,))
    _fill_row(11)
    for r in (12, 13, 14):
        _fill_row(r)
    for r in (16, 18):
        _fill_row(r)

    runes.append({'row': _RUNIC_ARCHIVES_VOID_POS[0],
                  'col': _RUNIC_ARCHIVES_VOID_POS[1],
                  'symbols': '○', 'kind': 'void'})

    level = _Level(
        name='The Runic Archives', seed=seed,
        rows=ROWS, cols=COLS,
        cells=[''.join(_CELL_CODE[c] for c in row) for row in cells],
        spawn=_RUNIC_ARCHIVES_ENTRY, exit=_RUNIC_ARCHIVES_EXIT,
        char_runs=runes,
        entities=[
            {'kind': 'floor_key',   'at': [_RUNIC_ARCHIVES_KEY_POS[0],
                                           _RUNIC_ARCHIVES_KEY_POS[1]]},
            {'kind': 'locked_door', 'at': [_RUNIC_ARCHIVES_DOOR_POS[0],
                                           _RUNIC_ARCHIVES_DOOR_POS[1]]},
            {'kind': 'exit',        'at': [_RUNIC_ARCHIVES_EXIT[0],
                                           _RUNIC_ARCHIVES_EXIT[1]]},
        ])

    dungeon = _fmt_build(level)
    room = dungeon.rooms[0]
    par, path = _par_runic_archives(room, return_path=True)
    if par is None:
        par, path = _RUNIC_ARCHIVES_PAR, _RUNIC_ARCHIVES_ANSWER
    room.par    = par
    room.budget = math.ceil(par * 1.4)
    room.answer = path
    return dungeon



def _par_sentence_corridor(composite, return_path=False, no_close=False, no_open=False):
    """Minimum-keystroke Dijkstra for The Sentence Corridor — Sentence Jumps.

    State = (row, col, has_key, door_open).  Models count-hjkl, 0, $, ) and (
    (buffer-wide sentence jumps, with count), x (pick up the floor_key), and p
    (unlock the locked_door to the right, stepping onto it).  no_close / no_open
    drop ) / ( for the command-necessity checks.

    { / } are intentionally NOT modelled because the build paves a VOID TRAP LINE
    above the first sentence (row 0): `{`/`}` resolve onto it and landing on a void
    costs a heart + bounces you back, so they can never undercut ( as the backtrack
    (without it, `{` reached S3's start in one key — the cheese `4) $ x { $ p l` =
    8).  G gg {n}G H M L reach only a row's FIRST sentence, so they never beat )
    onto the key's/door's sentence either.  par is unaffected and ) stays genuinely
    required.  ( CAN be replaced by gg/{n}G + ), so it is the strongly-incentivized
    partner, not asserted as required.
    """
    from vimny.engine.motion import _sentence_starts_all
    ROWS, COLS = composite.rows, composite.cols
    DR, DC = _SENTENCE_CORRIDOR_DOOR_POS
    KR, KC = _SENTENCE_CORRIDOR_KEY_POS
    EX     = _SENTENCE_CORRIDOR_EXIT
    entry  = composite.spawn_pos
    max_n  = max(ROWS, COLS)
    starts = _sentence_starts_all(composite)

    def _ok(r, c, door_open):
        if not (0 <= r < ROWS and 0 <= c < COLS):
            return False
        if composite.cells[r][c] not in (CellType.CORRIDOR, CellType.FLOOR):
            return False
        if (r, c) == (DR, DC) and not door_open:
            return False
        ru = composite.char_run_at(r, c)
        return not (ru and ru.kind == 'void')

    start = (entry[0], entry[1], 0, 0)
    dist  = {start: 0}
    prev  = {start: None}
    heap  = [(0, start)]

    while heap:
        cost, state = heapq.heappop(heap)
        r, c, hk, do = state

        if (r, c) == EX:
            if return_path:
                return cost, _join_path(prev, state, merge_single=False)
            return cost

        if cost > dist.get(state, float('inf')):
            continue

        def _try(nb, mc, lbl):
            g = cost + mc
            if g < dist.get(nb, float('inf')):
                dist[nb] = g
                prev[nb] = (state, lbl)
                heapq.heappush(heap, (g, nb))

        # x: pick up the floor_key
        if (r, c) == (KR, KC) and hk == 0:
            _try((r, c, 1, do), 1, 'x')

        # p: unlock the locked_door to the right and step onto it (key retained)
        if (r, c + 1) == (DR, DC) and hk == 1 and do == 0:
            _try((DR, DC, hk, 1), 1, 'p')

        # ) forward / ( backward — buffer-wide sentence jumps, with count
        cur = (r, c)
        if not no_close:
            fwd = [s for s in starts if s > cur]
            for n in range(1, len(fwd) + 1):
                tr, tc = fwd[n - 1]
                mc  = 1 if n == 1 else len(str(n)) + 1
                lbl = ')' if n == 1 else f'{n})'
                _try((tr, tc, hk, do), mc, lbl)
        if not no_open:
            bwd = [s for s in starts if s < cur]
            for n in range(1, len(bwd) + 1):
                tr, tc = bwd[-n]
                mc  = 1 if n == 1 else len(str(n)) + 1
                lbl = '(' if n == 1 else f'{n}('
                _try((tr, tc, hk, do), mc, lbl)

        # hjkl and count-hjkl
        for _dr, _dc, _key in ((0, -1, 'h'), (0, 1, 'l'), (1, 0, 'j'), (-1, 0, 'k')):
            for n in range(1, max_n + 1):
                nr2 = r + _dr * n
                nc2 = c + _dc * n
                if not _ok(nr2, nc2, do):
                    break
                mc2  = 1 if n == 1 else len(str(n)) + 1
                lbl2 = _key if n == 1 else f'{n}{_key}'
                _try((nr2, nc2, hk, do), mc2, lbl2)

        # gg / G / {n}G — the line jumps, under this solver's own door state
        for jr, jc, jcost, jlbl in _line_jump_moves(
                composite, lambda rr, cc: _ok(rr, cc, do), r, c):
            _try((jr, jc, hk, do), jcost, jlbl)

        # $: scan right to the last passable cell
        end_c = None
        for tc in range(c + 1, COLS):
            if not _ok(r, tc, do):
                break
            end_c = tc
        if end_c is not None:
            _try((r, end_c, hk, do), 1, '$')

        # 0: scan left to the first passable cell
        start_c = None
        for tc in range(c - 1, -1, -1):
            if not _ok(r, tc, do):
                break
            start_c = tc
        if start_c is not None:
            _try((r, start_c, hk, do), 1, '0')

    if return_path:
        return None, ''
    return None


def build_dungeon_sentence_corridor(seed: int) -> 'Dungeon':
    """Sentence Jumps: The Sentence Corridor.

    Two sentence rows (1 and 3) split by a stone wall row (2): the only way
    between them is a sentence jump — teaching that ) ( cross lines, not just
    move within one.  Five sentences, scattered horizontally, divided by stone
    gaps:

        row 1:  A sentence is one stride. | Where does it end? | At a dot, or a bang![door][exit]
        row 3:  I cut each stone to fit. | A good joint needs no mortar.[key]

    The floor_key sits at the END of sentence 5 and the locked_door at the END of
    sentence 3.  Both host-sentences are the 2nd/3rd on their row, so the line /
    screen jumps the player already has (G gg {n}G H M L) reach only a row's FIRST
    sentence — the ONLY way onto the key's and door's sentences is ).  Reaching the
    key is mandatory, so ) is forced.  (The paragraph jumps { / } DO cross rows, so
    a void trap line above S1 stops them undercutting ( — see below.)

    ) and ( land on sentence STARTS; the key and door are at sentence ENDS, so
    the player must add $ after each jump — the core lesson of the level.

    Optimal path (par 9):  4) $ x 3( $ p l
      4) → S5 start · $ → key · x grab · 3( → S3 start · $ → door · p unlock · l exit
    (3( because ( from a sentence's END first returns to that sentence's START:
    S5end → S5start → S4start → S3start — the very nuance this level teaches.)

    ( is the shortest backtrack (3( beats gg+2)) but — like H/M/L and r/R — it
    cannot be infinitely forced (gg/{n}G + ) substitutes within budget); it is
    the strongly-incentivized partner while ) carries the mandatory lesson.
    """
    from vimny.engine.editor import _CELL_CODE
    from vimny.sharing import format as _fmt
    from vimny.sharing.format import Level as _Level, build as _fmt_build
    ROWS, COLS = _SENTENCE_CORRIDOR_ROWS, _SENTENCE_CORRIDOR_COLS

    cells = [[CellType.WALL] * COLS for _ in range(ROWS)]

    # ── Sentence rows (row 2 stays all-wall: the stone separator) ─────────────
    runes: list = []
    for (r, c, text) in _SENTENCE_CORRIDOR_SENTENCES:
        for i in range(len(text)):
            cells[r][c + i] = CellType.CORRIDOR
        runes.append({'row': r, 'col': c, 'symbols': text, 'kind': 'ember'})

    # ── Door / exit / key cells (passable floor; the door blocks via entity) ──
    dr, dc = _SENTENCE_CORRIDOR_DOOR_POS
    er, ec = _SENTENCE_CORRIDOR_EXIT
    kr, kc = _SENTENCE_CORRIDOR_KEY_POS
    cells[dr][dc] = CellType.FLOOR
    cells[er][ec] = CellType.CORRIDOR
    cells[kr][kc] = CellType.CORRIDOR

    # ── Void "trap line" above the first sentence (row 0 over S1's columns) ────
    # { / } want a blank line to land on. Without one they fell through to row 1
    # and landed at the cursor column's segment start, so `{` from the key (col 69)
    # reached S3's start in ONE key, undercutting `3(` (the cheese: `4) $ x { $ p l`
    # = 8). This strip is the topmost passable row, so `{`/`}` resolve onto it —
    # but it is paved with VOID runes: landing costs a heart and bounces you back
    # (vimny/game.py), so a cheeser reaching for `{` is punished and gains nothing,
    # leaving `(` the shortest backtrack and par at 9. The par solver and the
    # cheese audit both refuse to land on void, so par stays the true minimum.
    # Spans only S1 (a dead-end stub off the spawn) ⇒ no wall-gap bypass.
    # THREE runes suffice: every jump that resolves
    # onto this row lands on its FIRST standable cell — the strip head — so
    # a 3-rune stub traps exactly as the old full-sentence pave did.
    _s1_r, _s1_c, _s1_text = _SENTENCE_CORRIDOR_SENTENCES[0]
    for c in range(_s1_c, _s1_c + 3):
        cells[0][c] = CellType.CORRIDOR
    runes.append({'row': 0, 'col': _s1_c,
                  'symbols': _RUNE_CHAR['void'] * 3, 'kind': 'void'})

    # ── Waterworks: the inter-sentence gaps and the row-2
    # separator are MISTED WATER, not stone — every sentence is visible from
    # spawn (the stone-fog law) while the physics hold: water bars feet, and
    # the water stops $ / f at each sentence's end exactly as the stone gap
    # did (the par route's `$ → key` depends on that bound). Word motions
    # never cross water; ) ( land on sentence starts as before.
    underwater: set = set()
    for r in (1, 3):
        span = [c for c in range(COLS) if cells[r][c] != CellType.WALL]
        for c in range(min(span), max(span) + 1):
            if cells[r][c] == CellType.WALL:
                cells[r][c] = CellType.WATER
                underwater.add((r, c))
    for c in range(1, COLS - 1):
        if cells[2][c] == CellType.WALL:
            cells[2][c] = CellType.WATER
            underwater.add((2, c))

    def encode(r):
        return ''.join(_fmt._UNDERWATER_CODE if (r, c) in underwater else _CELL_CODE[ct]
                       for c, ct in enumerate(cells[r]))

    level = _Level(
        name='The Sentence Corridor', seed=seed,
        rows=ROWS, cols=COLS,
        cells=[encode(r) for r in range(ROWS)],
        spawn=_SENTENCE_CORRIDOR_ENTRY, exit=_SENTENCE_CORRIDOR_EXIT,
        char_runs=runes,
        entities=[
            {'kind': 'exit',        'at': [er, ec]},
            {'kind': 'locked_door', 'at': [dr, dc]},
            {'kind': 'floor_key',   'at': [kr, kc]},
        ])

    dungeon = _fmt_build(level)
    room = dungeon.rooms[0]
    cost, answer = _par_sentence_corridor(room, return_path=True)
    room.par    = cost
    room.budget = math.ceil(cost * 1.4)
    room.answer = answer
    return dungeon


# ── The Archivist's Library — one-line wrap_buffer + reload loop ─────────────
# Mechanically unlike any other level: the whole dungeon is ONE logical line
# (rows==1, wrap_buffer=True). ':set wrap' shelves it; ':e!' leafs through a
# seed-shuffled cadence of suit folios and decoys; ':w {suit}' files a copy;
# presenting forged folios to the Archivist is lethal. State lives on the room
# (lib_*) and is driven by the hooks in main.run_dungeon.
_LIB_SUITS      = ('hearts', 'diamonds', 'spades', 'clubs')
_LIB_SUIT_GLYPH = {'hearts': '♥', 'diamonds': '♦', 'spades': '♠', 'clubs': '♣'}
_LIB_BODY_ROWS  = 9             # text rows inside the page frame
_LIB_FALLBACK_W = 78           # build-time width; main relayouts to the real viewport


def _lib_center(s: str, w: int) -> str:
    s = s[:w]
    pad  = w - len(s)
    left = pad // 2
    return ' ' * left + s + ' ' * (pad - left)


def _lib_frame(W: int, body: list, kinds: list, border: str = 'ancient') -> list:
    """Compose a framed 'page' as rows of EXACTLY W columns (so wrapping at width W
    redraws a perfect rectangle), each tagged with its colour `kind`. Returns a list
    of (row_string, kind); the caller emits one CharRun per row so regions keep their
    own colour. The first row is the top border, so even unwrapped the player sees a
    ┌────┐ filling the view."""
    inner = max(1, W - 2)
    rows  = [('┌' + '─' * inner + '┐', border)]
    for i in range(_LIB_BODY_ROWS):
        line = body[i] if i < len(body) else ''
        k    = kinds[i] if i < len(kinds) else border
        rows.append(('│' + _lib_center(line, inner) + '│', k))
    rows.append(('└' + '─' * inner + '┘', border))
    return rows                 # each row is exactly W chars → (rows)*W total


# A library floor drawn top-down: rows of labelled book-stacks (full ▤▤, empty □□),
# reading tables, and the Archivist's desk. Stack labels are UNIQUE within a page —
# the 4 card suits, 6 chess pieces, and a RANKED pool of 89 ornaments (crosses first,
# then stars, snowflakes, florals, geometric & misc). The shelves fill the viewport
# left-to-right and the ornament pool is drawn front-to-back, so a wider window simply
# pulls in more glyphs in rank order. All glyphs are terminal width-1 (the wrapped page
# must stay a perfect rectangle).
_LIB_CHESS    = ['♚', '♛', '♜', '♝', '♞', '♟']
_LIB_FILLERS  = ['✝', '✞', '✟', '✠', '✚', '✛', '✜', '✢', '✣', '†', '‡', '☩', '☦', '☨', '✙', '⁜',
                 '✦', '✧', '✩', '✪', '✫', '✬', '✭', '✮', '✯', '✰', '★', '☆', '✱', '✲', '✴', '✵',
                 '✶', '✷', '✸', '✹', '✺', '✳',
                 '❀', '❁', '❂', '❃', '❄', '❅', '❆', '❇', '❈', '❉', '❊', '❋', '❍',
                 '✿', '❦', '❧', '⁂', '⁕', '✾', '✽', '✼', '✻', '⚘', '☘',
                 '◈', '◇', '◆', '❖', '⬡', '⬢', '⬣', '⟡', '⬠', '⬟', '⬨', '⬩',
                 '♪', '♫', '♬', '♩', '⚜', '⚝', '☼',
                 '❡', '❢', '☸', '☫', '⚹', '⚶', '⚸', '⸙']
_LIB_DESK       = '╓─╖'              # the Archivist's small desk (ember)
_LIB_TBL_SURF2  = 5                  # body index of the reading table's 2nd surface row
_LIB_BORDER     = set('┌─┐│└┘◠◡')    # box-drawing glyphs — always drawn in ancient indigo


def _lib_table_band(inner: int, rng, tables=None) -> list:
    """A centred row of two reading tables (chairs ◠/◡ along the edges). With tables=None
    the surfaces are set sparsely with a few books (≡/◫) — the library at rest. Given
    pre-generated `tables` (see _lib_folio_tables) the surfaces are PACKED instead, to
    spell a folio's answer. Returns 4 body rows."""
    n, w, gap = 2, 10, '        '
    top = '┌' + ''.join('◠' if i % 3 == 0 else '─' for i in range(w)) + '┐'
    bot = '└' + ''.join('◡' if i % 3 == 0 else '─' for i in range(w)) + '┘'

    def surfaces(content):
        if content is None:               # the library: a few books, plenty of bare space
            cells = [[' '] * w, [' '] * w]
            books = ['≡'] * rng.randint(2, 3) + ['◫'] * rng.randint(1, 2)
            spots = [(r, c) for r in range(2) for c in range(0, w, 2)]
            rng.shuffle(spots)
            for b, (r, c) in zip(books, spots):
                cells[r][c] = b
        else:
            cells = [list(content[0]), list(content[1])]
        return ['│' + ''.join(cells[0]) + '│', '│' + ''.join(cells[1]) + '│']

    surf = [surfaces(None if tables is None else tables[k]) for k in range(n)]
    join = lambda parts: (' ' * len(gap)).join(parts)
    return [join([top] * n), join([s[0] for s in surf]),
            join([s[1] for s in surf]), join([bot] * n)]


def _lib_title_row(inner: int, text: str) -> str:
    """The title, centred. (The Archivist's desk is placed separately, at _LIB_DESK_COL.)"""
    row   = [' '] * inner
    start = max(0, (inner - len(text)) // 2)
    for i, ch in enumerate(text):
        if start + i < inner:
            row[start + i] = ch
    return ''.join(row)


def _lib_table_fill(fill, suit_glyphs, nonsuit_labels, frng):
    """Choose the glyphs for a folio's tables, sampled from THIS page's shelves so the
    empties always correspond. fill is one of:
      ('suit', g)       — unmixed one suit  (the correct folio)
      ('mixsuit',)      — a jumble of suits
      ('nonsuit', True) — unmixed one non-suit label (chess piece or ornament)
      ('nonsuit', False)— a jumble of non-suit labels
    Returns (glyphs, unmixed?)."""
    if fill[0] == 'suit':
        return [fill[1]], True
    if fill[0] == 'mixsuit':
        return suit_glyphs, False
    if fill[1]:                                   # unmixed non-suit
        return [frng.choice(nonsuit_labels)], True
    return frng.sample(nonsuit_labels, min(len(nonsuit_labels), 5)), False   # mixed non-suit


def _lib_floor_spec(inner: int, rng, filled=(), fill=None, fill_rng=None,
                    title='L I B R A R Y') -> dict:
    """A library-floor page: a title, two shelf bands (the chess group and the suit
    group, packed out with UNIQUE filler labels — no duplicates), and the reading
    tables. Bookshelves render ancient indigo, tables/desk ember. Without `fill` it is
    the sparse library and the four suit stacks stand empty (□□) until `filled`. With
    a `fill` descriptor (a :e! folio) the tables are PACKED with glyphs sampled from
    this page's own shelves, and exactly those bookcases are emptied — the books the
    Archivist pulled to pack it — so the empties always correspond to the table."""
    g       = _LIB_SUIT_GLYPH
    F       = set(filled)                          # suit stacks fill ONLY as the player saves them
    pool    = list(_LIB_FILLERS)                   # ranked: pulled front-to-back as the page widens
    # Shelves per band scale to fill the viewport left-to-right, bounded by the label pool
    # so every stack stays uniquely labelled (no duplicates, no '·' fallback).
    ncells  = max(9, (inner + 2) // 4)
    ncells  = min(ncells, (len(pool) + len(_LIB_CHESS) + len(_LIB_SUITS)) // 2)
    take    = lambda: (pool.pop(0) if pool else '·')

    nonsuit = list(_LIB_CHESS)                    # every non-suit label on this page

    def make_band(center):                        # functional group centred; fillers flank both sides
        n_fill = max(0, ncells - len(center))
        left   = [take() for _ in range(n_fill // 2)]
        right  = [take() for _ in range(n_fill - n_fill // 2)]
        nonsuit.extend(left + right)              # fillers are non-suit labels
        return [(gl, True) for gl in left] + center + [(gl, True) for gl in right]

    chess_cells = make_band([(c, True) for c in _LIB_CHESS])
    suit_cells  = make_band([(g[s], s in F) for s in _LIB_SUITS])

    tables, empty = None, set()
    if fill is not None:
        glyphs, unmixed = _lib_table_fill(fill, list(g.values()), nonsuit, fill_rng or rng)
        w = 10
        tables = [[[(glyphs[0] if unmixed else (fill_rng or rng).choice(glyphs))
                    for _ in range(w)] for _ in range(2)] for _ in range(2)]
        empty  = {ch for t in tables for row in t for ch in row}

    suit_set = set(g.values())
    def render(cells):
        # Suit stacks keep their saved state; only NON-suit bookcases are emptied to
        # fill the table (suit folios show □□ simply because they aren't saved yet).
        cells = [(gl, f if gl in suit_set else (f and gl not in empty)) for gl, f in cells]
        lab   = '  '.join(f'{gl} ' for gl, _ in cells)
        shelf = '  '.join('▤▤' if f else '□□' for _, f in cells)
        return lab, shelf

    cl, cs = render(chess_cells)
    sl, ss = render(suit_cells)
    table  = _lib_table_band(inner, rng, tables)
    body   = [_lib_title_row(inner, title), cl, cs, *table, sl, ss]
    # title + shelves + frame in ancient indigo; only the reading tables glow ember.
    kinds  = ['ancient', 'ancient', 'ancient', *(['ember'] * len(table)), 'ancient', 'ancient']
    return {'kind': 'ancient', 'border': 'ancient', 'body': body, 'kinds': kinds}


def _lib_desk_col(W: int, body: list) -> int:
    """Logical column for the desk: five cells left of the 1st reading table's 2nd
    surface row. (The table content starts with the table's left │, centred by the
    frame.)"""
    drow     = _LIB_TBL_SURF2 + 1                 # +1 for the top border row
    inner    = max(1, W - 2)
    content  = body[_LIB_TBL_SURF2] if _LIB_TBL_SURF2 < len(body) else ''
    left_pad = (inner - len(content)) // 2
    return max(0, drow * W + 1 + left_pad - 5)


def _lib_place_desk(room, c0: int) -> None:
    """Set the Archivist's desk (ember) at logical column c0, splitting the run it lands
    in so it keeps its own colour."""
    if c0 + len(_LIB_DESK) > room.cols:
        return
    ru = room.char_run_at(0, c0)
    if ru is None or ru is not room.char_run_at(0, c0 + len(_LIB_DESK) - 1):
        return                                    # the desk spans a row edge — skip (rare)
    i, s, off = room.char_runs.index(ru), list(ru.symbols), c0 - ru.col
    for j, ch in enumerate(_LIB_DESK):
        s[off + j] = ch
    parts = []
    if off > 0:
        parts.append(CharRun(0, ru.col, tuple(s[:off]), ru.kind))
    parts.append(CharRun(0, c0, tuple(_LIB_DESK), 'ember'))   # the desk glows amber
    tail = s[off + len(_LIB_DESK):]
    if tail:
        parts.append(CharRun(0, c0 + len(_LIB_DESK), tuple(tail), ru.kind))
    room.char_runs[i:i + 1] = parts


def _lib_layout(room, W: int) -> None:
    """(Re)compose the current page at viewport width W as one CharRun PER display row
    (shelves indigo, tables/desk ember), resize the room, place the desk at (0,521),
    and keep the Archivist in bounds. Pages are generated from the seed (stable across
    resize). Called by the builder and by main.run_dungeon when the width changes."""
    inner  = max(8, W - 2)
    rng    = random.Random((room.seed or 0) ^ 0x5EED)
    filled = [s for s in _LIB_SUITS if s in room.lib_filed]   # suit stacks the player has saved
    if getattr(room, 'lib_done', None) == 'win':
        spec = _lib_floor_spec(inner, rng, filled=_LIB_SUITS,
                               title='L I B R A R Y   R E S T O R E D')
    elif getattr(room, 'lib_view', 'catalog') == 'catalog' or room.lib_idx < 0:
        spec = _lib_floor_spec(inner, rng, filled=filled)
    else:                                         # a :e! folio — packed tables show the answer
        frng = random.Random((room.seed or 0) ^ ((room.lib_idx + 1) * 0x9E37))
        spec = _lib_floor_spec(inner, rng, filled=filled,
                               fill=room.lib_seq[room.lib_idx]['fill'], fill_rng=frng)
    rows = _lib_frame(W, spec['body'], spec['kinds'], spec['border'])
    room.cols      = sum(len(r) for r, _ in rows)
    room.cells     = [[CellType.FLOOR] * room.cols]
    room.char_runs = []
    col = 0
    for rowstr, kind in rows:
        # Split each row so box-drawing borders stay ancient indigo while the row's
        # own content (table books, etc.) keeps its colour — e.g. blue table frames
        # around amber books.
        j, n = 0, len(rowstr)
        while j < n:
            border = rowstr[j] in _LIB_BORDER
            k = j
            while k < n and (rowstr[k] in _LIB_BORDER) == border:
                k += 1
            room.char_runs.append(CharRun(0, col + j, tuple(rowstr[j:k]),
                                          'ancient' if border else kind))
            j = k
        col += n
    room.rebuild_indexes()
    room._lib_desk_col = _lib_desk_col(W, spec['body'])
    _lib_place_desk(room, room._lib_desk_col)
    # The Archivist sits at his desk until he first paces off (_enemy_tick); after that
    # just keep him in bounds as the page re-flows.
    for e in room.entities:
        if e.kind == 'archivist':
            if not getattr(room, '_lib_arch_paced', False):
                e.col = room._lib_desk_col
            e.col = min(max(1, e.col), room.cols - 2)
    room._lib_w = W
    room.rebuild_indexes()


def build_dungeon_archivists_library(seed: int) -> Dungeon:
    rng = random.Random(seed)
    dungeon = Dungeon(name="The Archivist's Library", seed=seed)

    room = Room(room_type=RoomType.ENTRY, rows=1, cols=_LIB_FALLBACK_W)
    room.seed        = seed
    room.spawn_pos   = (0, 0)
    room.wrap_buffer = True
    # Completion-only: the lesson here (:set wrap / :e! / :w {suit}) is contextual ex-mode
    # work that spends NO keystroke budget, so a keystroke par would only meter the trailing
    # walk to the exit — meaningless.  par=0 means no 2-star is possible (_calc_stars guards
    # `par > 0`); a win is a flat 1-star that simply unlocks the next level.  The lesson stays
    # forced: ANY win mechanically requires the :e!/:w {suit} forge loop.
    room.par         = 0          # completion-only (unlock-the-next-level sandbox; no 2-star)
    room.budget      = 2000       # generous; the loop is exploratory, never budget-gated
    room.answer      = ''

    # Cadence: a one-suit folio (the only correct answer) at indices 0,3,7,10; decoys
    # elsewhere, cycling through mixed suits, unmixed non-suits and mixed non-suits.
    # Each folio carries only its FILL TYPE; the glyphs are sampled at render time from
    # the page's own shelves (so the emptied bookcases always correspond).
    suit_slots = [0, 3, 7, 10]
    suits      = list(_LIB_SUITS)
    rng.shuffle(suits)
    _decoys    = [('mixsuit',), ('nonsuit', True), ('nonsuit', False)]
    seq, decoy_n = [], 0
    for i in range(11):
        if i in suit_slots:
            S = suits[suit_slots.index(i)]
            seq.append({'suit': S, 'fill': ('suit', _LIB_SUIT_GLYPH[S])})
        else:
            seq.append({'suit': None, 'fill': _decoys[decoy_n % len(_decoys)]})
            decoy_n += 1

    room.lib_seq     = seq
    room.lib_idx     = -1         # index into the cycle of the manuscript last leafed to
    room.lib_view    = 'catalog'  # 'catalog' (the library floor) | 'leaf' (a manuscript)
    room.lib_filed   = {}         # suit-name -> the true suit of what was filed (None = decoy)
    room.lib_done    = None       # None | 'win' | 'dead'
    room.lib_dlg     = 0          # brief dialogue index (0 idle, 1-3 lines, 4 = editing)
    room.lib_dlg_col = 0          # player col when the last brief line was shown
    room.lib_hostile = False      # True once he catches the player forging — he gives chase
    room._lib_arch_flag  = False  # debounces the on-Archivist (present/panic) trigger
    room._lib_arch_paced = False  # False until the Archivist first steps off his desk

    # The Archivist paces the hall (ai='wander' → oscillates in _enemy_tick); he starts
    # off the first screen, and ':set wrap' folds the line in so the player sees him move.
    room.entities = [
        Entity(kind='archivist',    row=0, col=1, ai='wander', ai_speed=1, move_dir=1,
               hp=100, max_hp=100),   # tanky, but his 10-damage strike is what stops you
    ]
    _lib_layout(room, _LIB_FALLBACK_W)   # seats the Archivist at his desk (he paces off later)

    dungeon.rooms        = [room]
    dungeon.current_room = 0
    return dungeon


# ── The Spellwright's Forge — :s, :g, & ───────────────────────────────────────
# A warded workroom: corrupted incantations the apprentice must make TRUE before
# the sanctum door opens. Two flaws to mend with ex-commands:
#   • every line says "old" where the rite now reads "new"  →  :%s/old/new/g
#   • two cursed verses must be struck out entirely         →  :g/cursed/d
# When no line bears 'old' or 'curse', the seal at (action row, divider) dissolves
# and the player walks through to the exit. x-erasing each glyph by hand blows the
# budget — :s / :g are the efficient way (the lesson).
_FORGE_ROWS, _FORGE_COLS = 20, 58
_FORGE_DIV   = 46                       # full-height divider wall; sanctum to its right
                                        # (wide enough that the forge-song's
                                        # longest line runs 41 chars, to col 42)
_FORGE_DOOR  = 6                        # the blank corridor row: spawn, seal door, exit
# Three chambers, each forcing a different member of the :s / :g family more than once.
# Vocabulary is rigorously separated so one chamber's global rite never reaches another:
# no word outside Chamber A contains the substring 'old' (no cold/gold/holds/bond…), only
# Chamber B carries 'pale'/'pure', only Chamber C carries 'cursed'.
#
# SENSE, NOT DECREE: the
# three chambers are three rhymes everyone knows, each corrupted the way
# its rite mends. FIXED texts (their structure is the puzzle):
#   A — OLD MACDONALD'S DUCK, written with 'moo' throughout: every line
#       names the DUCK (the chorus alone reads as a
#       cow), everyone knows the duck says quack, and the moos repeat
#       WITHIN each line, so a /g-less :s leaves remnants —
#       :%s/moo/quack/g. Drills the /g flag.
#   B — HICKORY DICKORY: the famous line says the mouse ran UP the clock,
#       twice — but the MIDDLE line ('the clock struck one and the mouse
#       ran down') is rightly DOWN, so a blanket :%s/down/up/g wrecks it
#       self-evidently; :s one line, jj, & the other. Surgical :s + &.
#   C — TWINKLE TWINKLE, its two famous lines intact, with three lines of
#       OBVIOUS NONSENSE STATIC ('krzzt…') between them — nothing to fix,
#       only to strike: :g/krzzt/d sweeps the static at once. (A known
#       2-liner plus unmistakably unfixable junk reads clean; an unfamiliar
#       song with cursed-but-fixable-looking lines does not.)
_FORGE_A_WARDS   = [(2, 'the duck says moo moo here'),
                    (3, 'the duck says moo moo there'),
                    (4, 'everywhere the duck says moo moo')]
_FORGE_B_CORRUPT = [(8, 'the mouse ran down the clock'),
                    (10, 'the mouse ran down the clock again')]
_FORGE_B_KEEP    = (9, 'the clock struck one and the mouse ran down')
# (:g/…/d REMOVES rows and destroys entities on them — the sanctum's scroll
# chest must sit ABOVE every cursed row; it sits on row 10, in the sanctum
# east of the divider, so no workroom edit or cull can ever reach it.)
_FORGE_C_CURSED  = [(14, 'krzzt vrm blug krzzt'),
                    (16, 'splug krzzt gnnn'),
                    (18, 'krzzt krzzt fzzzp')]
_FORGE_C_KEEP    = [(15, 'twinkle twinkle little star'),
                    (17, 'how i wonder what you are')]
_FORGE_CHEST     = (10, _FORGE_COLS - 2)   # sanctum scroll chest (random relic —
                                           # the forge names no scroll drop)


def _forge_text(room, row, col, text, kind):
    for i, ch in enumerate(text):
        if ch != ' ':
            room.char_runs.append(CharRun(row, col + i, (ch,), kind))


# The canonical three-rite solve, as an admin karaoke tape: Enter is the glyph '<CR>' (so it
# renders on the answer sheet and the live tracker can match an Enter keypress against it),
# and spaces are visual token separators (stripped for matching, never typed).  Chamber A's
# /g mend, then 8G + surgical :s + jj + & (Chamber B, sparing the protected verse), then
# Chamber C's :g delete, then the walk out.  Tests translate <CR>→Enter and drop the spaces.
# par is this solve's measured engine cost — constant across seeds; the playthrough pins it.
_SPELLWRIGHTS_ANSWER = ':%s/moo/quack/g<CR> 8G :s/down/up/<CR> jj& :g/krzzt/d<CR> 6G$'
_SPELLWRIGHTS_PAR    = 44
# 44 = 47 keys typed MINUS the 3 command-line Enters, which execute the line
#      rather than spending budget:
#        :%s/moo/quack/g<CR> (16-1) + 8G (2) + :s/down/up/<CR> (12-1) + jj (2)
#        + & (1) + :g/krzzt/d<CR> (11-1) + 6G$ (3)
#      Chamber B's two verses straddle the protected line, so no single
#      command hits just them — the :s + & pair is the floor there; the cursor
#      never lands on the door row after a rite, so the 3-key walk out is the
#      floor too.
#      Was 45 until 2026-07-25: the old figure was hand-tallied and counted
#      neither the Enters nor their exemption, and this level is excluded
#      outright from tests/test_answer_paths.py, so nothing measured it. The
#      headless replayer (`python3 -m sharing audit`) found it on its first
#      run — which is the entire argument for §1a in docs/blueprints/level_sharing.md.


def _par_spellwrights_forge():
    return _SPELLWRIGHTS_PAR, _SPELLWRIGHTS_ANSWER


def build_dungeon_spellwrights_forge(seed: int) -> Dungeon:
    from vimny.engine.editor import _CELL_CODE
    from vimny.sharing.format import (Level as _Level, build as _fmt_build,
                                      _parse_seal)
    ROWS, COLS, W = _FORGE_ROWS, _FORGE_COLS, _FORGE_DIV

    cells = [[CellType.WALL] * COLS for _ in range(ROWS)]
    for r in range(1, ROWS - 1):
        for c in range(1, W):                      # left workroom
            cells[r][c] = CellType.FLOOR
        for c in range(W + 1, COLS - 1):           # right sanctum
            cells[r][c] = CellType.FLOOR
    # col W is wall top-to-bottom except the seal door, which opens once the rites are true.

    def forge_text(runs, row, col, text, kind):
        for i, ch in enumerate(text):
            if ch != ' ':
                runs.append({'row': row, 'col': col + i, 'symbols': ch,
                             'kind': kind})

    runs: list = []
    for r, txt in _FORGE_A_WARDS:                 # Chamber A — corrupted ember wards
        forge_text(runs, r, 2, txt, 'ember')
    for r, txt in _FORGE_B_CORRUPT:               # Chamber B — corrupt verses (mend pale→pure)
        forge_text(runs, r, 2, txt, 'ember')
    forge_text(runs, _FORGE_B_KEEP[0], 2, _FORGE_B_KEEP[1], 'verdant')   # the TRUE pale ward
    for r, txt in _FORGE_C_CURSED:                # Chamber C — cursed lines (delete)
        forge_text(runs, r, 2, txt, 'ember')
    for r, txt in _FORGE_C_KEEP:                  # the sacred lines (keep)
        forge_text(runs, r, 2, txt, 'verdant')

    forge_seals = []
    for j, phrase in enumerate(sorted(
            [t.replace('moo', 'quack') for _, t in _FORGE_A_WARDS]
          + [t.replace('down', 'up') for _, t in _FORGE_B_CORRUPT]
          + [_FORGE_B_KEEP[1]]
          + [t for _, t in _FORGE_C_KEEP],
            key=len, reverse=True)):
        forge_seals.append(_parse_seal({
            'scope': 'anyrow', 'mode': 'exact', 'match': [phrase],
        }, j))
    forge_seals.append(_parse_seal({
        'requires': list(range(len(forge_seals))),
        'opens': [[_FORGE_DOOR, W]],
    }, len(forge_seals)))

    level = _Level(
        name="The Spellwright's Forge", seed=seed,
        rows=ROWS, cols=COLS,
        cells=[''.join(_CELL_CODE[c] for c in row) for row in cells],
        seals=forge_seals,
        spawn=(_FORGE_DOOR, 1),
        exit=(_FORGE_DOOR, COLS - 2),
        char_runs=runs,
        entities=[
            {'kind': 'exit', 'at': [_FORGE_DOOR, COLS - 2]},
            # The sanctum's reward: an unassigned chest → a random relic scroll.
            # ABOVE every cursed row, so :g/krzzt/d never collapses it.
            {'kind': 'chest_scroll', 'at': [_FORGE_CHEST[0], _FORGE_CHEST[1]]},
        ])

    dungeon = _fmt_build(level)
    room = dungeon.rooms[0]

    # par is the true keystroke floor of the three rites + the walk out; measured by replay
    # across seeds (content is fixed, so par is constant).  See tests/test_spellwrights_forge.
    par, ans = _par_spellwrights_forge()
    room.par    = par
    room.budget = max(math.ceil(par * 1.4), 60)  # generous; the rites are exploratory
    room.answer = ans
    return dungeon


# ── The Refrain Vault (display 42) — repeats + remote yank: & :&& :j :y ──────
# LONDON BRIDGE IS FALLING DOWN (public domain, known to all, one search
# away for the rest). The scribe wrote the falling verses WRONG — "falling
# up" — while the build and key verses keep "up" RIGHTLY ("Build it up…",
# "Take the key and lock her up…"): a blanket :%s/up/down/g wrecks them
# self-evidently, and no contiguous range covers both falling verses while
# sparing the middle. So: one full :s/up/down/g on the double line you wake
# at, then RANGED :&& over each falling verse while the /g is fresh (a
# plain & resets the remembered flags, Vim-faithful). Above the water the
# torn final line lies sunken — "my fair" / "lady." — :1j mends it,
# :1y carries it, p lays it where the reprise goes without one (a :t of
# the chasm line arrives still sunken: text off the floor never serves).
_RV_ROWS, _RV_COLS = 18, 60
_RV_CTX  = 8                          # water course head col (the sight-line
                                      # starts here; the chasm band reaches west
                                      # past it to the song's own margin)
_RV_BAND = (2, 42)                    # sunken torn-line band, rows 1-2 — from
                                      # _RV_TX, so the torn verse left-aligns
                                      # with every carved line of the song
_RV_WTR  = 3                          # the water course (sight-line)
_RV_TX   = 2                          # song text head col (= the line start:
                                      # everything left-aligned, so a pasted
                                      # line lands flush with the verses)
_RV_SONG = (4, 15)                    # the carved song: 12 lines, NO refrains
_RV_CORRUPT = (4, 5, 6, 13, 14, 15)   # the falling verses, written "up"
_RV_SEAL_ROW  = 16                    # the blank walk below the song
_RV_SEAL_COL  = 49
_RV_CHEST_COL = 53
_RV_EXIT_COL  = 57
# The song as it SHOULD read (the seal's demand). "my fair lady." exists
# ONLY as the torn line across the water — one copy in the whole vault, so
# every refrain must be pasted from the register (yank once, lay it four
# times; a song-side copy would let :y skip the chasm entirely).
_RV_LADY = 'my fair lady.'
_RV_TRUE = (
    'London Bridge is falling down,',
    'falling down, falling down.',
    'London Bridge is falling down,',
    _RV_LADY,
    'Build it up with wood and clay,',
    'wood and clay, wood and clay.',
    'Build it up with wood and clay,',
    _RV_LADY,
    'Take the key and lock her up,',
    'lock her up, lock her up.',
    'Take the key and lock her up,',
    _RV_LADY,
    'London Bridge is falling down,',
    'falling down, falling down.',
    'London Bridge is falling down,',
    _RV_LADY,
)
_RV_PAR    = 41    # :13,15s/up/down/g(17) :4,6&&(6) :1j|1y(6 — the bar
                   # chain; :1j(3)+:1y(3) TIES in spend, but the bar is one
                   # real keystroke shorter, so the tape shows it)
                   # p(1) [3j p](3)×3 j(1) $(1)
_RV_BUDGET = 60    # generous: the double ranged-:s longhand (~52) wins 1★


def build_dungeon_refrain_vault(seed: int) -> Dungeon:
    from vimny.engine.editor import _CELL_CODE
    from vimny.sharing.format import (Level as _Level, build as _fmt_build,
                                      _parse_seal)
    R, C = _RV_ROWS, _RV_COLS

    cells = [[CellType.WALL] * C for _ in range(R)]
    underwater: set = set()
    for r in (1, 2):                               # the torn-line chasm
        for col in range(*_RV_BAND):
            cells[r][col] = CellType.FLOOR
            underwater.add((r, col))
    for col in range(*_RV_BAND):                   # the water course (sight):
        cells[_RV_WTR][col] = CellType.WATER       # exactly the chasm's span
        underwater.add((_RV_WTR, col))             # — no wider than the sheet
    for col in range(16, 35):                      # a pool in the chasm sheet,
        cells[1][col] = CellType.WATER             # on the JOIN'S SURVIVOR: the
        underwater.add((1, col))                   # :1j consumes row 2 (rows
                                                   # collapse whole), so decor
                                                   # lives where mending cannot eat it
    for r in range(_RV_SONG[0], _RV_SONG[1] + 1):
        for col in range(2, _RV_SEAL_COL):
            cells[r][col] = CellType.FLOOR         # the workroom
    for col in range(2, _RV_SEAL_COL):
        cells[_RV_SEAL_ROW][col] = CellType.FLOOR  # the seal row
    for col in range(_RV_SEAL_COL + 1, _RV_EXIT_COL + 1):
        cells[_RV_SEAL_ROW][col] = CellType.FLOOR  # the sealed exit pocket
    # (_RV_SEAL_ROW, _RV_SEAL_COL) stays WALL until _refrain_tick opens it.

    def lay(runs, r, col, text, kind):
        for wd in text.split(' '):
            runs.append({'row': r, 'col': col, 'symbols': wd, 'kind': kind})
            col += len(wd) + 1

    runs: list = []
    lay(runs, 1, _RV_TX, 'my fair', 'ancient')     # the torn refrain — the ONLY
    lay(runs, 2, _RV_TX, 'lady.', 'ancient')       # "my fair lady." anywhere,
                                                   # flush with the carved song
    carved = [t for t in _RV_TRUE if t != _RV_LADY]
    for i, true_line in enumerate(carved):         # the carved song, rows 4..15
        r = _RV_SONG[0] + i
        writ = true_line.replace('down', 'up') if r in _RV_CORRUPT else true_line
        lay(runs, r, _RV_TX, writ, 'ember' if r in _RV_CORRUPT else 'verdant')

    level = _Level(
        name='The Refrain Vault', seed=seed,
        rows=R, cols=C,
        cells=[''.join(_CELL_CODE[c] for c in row) for row in cells],
        underwater=sorted(underwater),                   # haze over floor AND water,
        spawn=(5, 2),
        exit=(_RV_SEAL_ROW, _RV_EXIT_COL),
        char_runs=runs,
        seals=(
            _parse_seal({'scope': 'region', 'mode': 'lines', 'anchor': 'exit_row',
                         'region': [0, 2, 200, C - 2],   # generous: covers post-paste layouts
                         'match': ['my fair lady.'] + list(_RV_TRUE),   # chasm + song = the full page
                         'opens': [[_RV_SEAL_ROW, _RV_SEAL_COL]],
                         'unveils': [[_RV_SEAL_ROW, c]
                                     for c in range(_RV_SEAL_COL + 1,
                                                    _RV_EXIT_COL + 1)],
                         'message': 'The song stands whole — the way opens!',
             }, 0),
        ),
        entities=[{'kind': 'exit', 'at': [_RV_SEAL_ROW, _RV_EXIT_COL]},
                  {'kind': 'chest_scroll', 'at': [_RV_SEAL_ROW, _RV_CHEST_COL]}],
        solution=(':set<Space>nu<CR> :13,15s/up/down/g<CR> :4,6&&<CR> '
                  ':1j|1y<CR> p 3j p 3j p 3j p j $'))

    dungeon = _fmt_build(level, par=_RV_PAR)
    room = dungeon.rooms[0]
    room._rv_true     = _RV_TRUE
    room._rv_seal_col = _RV_SEAL_COL
    # The water rides the file now; what stays a pin is the FOG arrangement:
    # the pocket behind the seal is hidden by position, not weather, and the
    # level wants exactly this darkness — no more, no less — than the stone
    # law would derive.
    pocket = {(_RV_SEAL_ROW, col)
              for col in range(_RV_SEAL_COL + 1, _RV_EXIT_COL + 1)}
    room.fog_cells = set(room.underwater_cells) | pocket
    return dungeon


# ── The Warden Pathfinder (Act III boss) ─────────────────────────────────────
# Two rooms: the Arena (room 0) and the Wardenverse (room 1, a single-line wrap
# buffer). Act 1 plays out in the Arena; when the Warden's shields fall he flees
# and the player follows with `:e wardenverse` (handled in vimny/game.py). See
# vimny/engine/warden_mega.py and tests/test_warden_pathfinder.py (the as-built spec).
_PF_ROWS, _PF_COLS   = 24, 78
_PF_MAIN_ROW         = 12
# A big open hall with four stone COLUMNS at the inner vertices of a 3×3 grid (just
# markers — the room stays open). The Warden's mega-attack tears bands of ROWS.
_PF_COLUMNS          = ((8, 22), (8, 44), (15, 22), (15, 44))   # column cells (impassable)
_PF_FIGHT            = (1, 22, 1, 66)       # fight area (mega tears floor only here; treasure is east)
_PF_WARDEN_START     = (12, 39)            # centre of the hall
# Impostor Wardens — goblins disguised as the Warden (tag='echo', a red 'W'). Two
# echoes flanking the center. The real Warden starts at center (12,39) but may swap
# with a random echo. After the wardenverse collapse, all echoes are revealed as
# plain goblins (hp=1, tag='') for cleanup. (row, col, shade)
_PF_ECHO_CELLS       = (
    (12, 26, 0),   # West
    (12, 52, 1),   # East
)
# Treasure room: a chamber behind a locked door on the east wall (every level has one).
# The key drops in the arena once the wardenverse has collapsed AND the last minion is dead.
_PF_TR_WALL          = 67                   # the column that seals the treasure room off
_PF_DOOR             = (12, 67)             # locked-door gap in that wall
_PF_TR_EXIT          = (12, 75)
_PF_TR_HEART         = (10, 72)
_PF_TR_SCROLL        = (14, 72)
_PF_RETURN           = (12, 60)             # where the collapse flings the player back into the arena
# The Wardenverse: ONE long logical line that wraps reactively to the terminal (like the
# Archivist's Library) — many folds at any supported width (80–189 cols); no fixed fold.
# Sparse single-cell stone walls (every ~50 cols) split the line into segments: ALL
# horizontal motion ($, w, e, f, {count}l) stops at a wall, so you can't $-skip to the
# Warden — only gj/gk (a display-row hop ≥ the min content width, ~76) clears a single
# stone, at ANY terminal width. Irregular spacing so a hop rarely lands ON a stone.
_PF_VERSE_COLS       = 720
_PF_VERSE_WALLS      = (47, 96, 152, 203, 261, 314, 368, 421, 479, 533, 588, 642)
_PF_VERSE_TEXT = ("the cut you cannot see you cannot parry   so follow the fold   "
                  "every shield bares a back   the warden runs the wrapped line   "
                  "set nowrap to still him   gj and gk to chase him down   ")


def _pf_lay_verse(room, rng) -> None:
    """Paper the single verse line with text, skipping the in-line wall cells."""
    text = (_PF_VERSE_TEXT * (room.cols // len(_PF_VERSE_TEXT) + 1))
    for c in range(1, room.cols - 1):
        if room.cells[0][c] == CellType.FLOOR:
            ch = text[c % len(text)]
            if ch != ' ':
                room.char_runs.append(CharRun(0, c, (ch,), 'ancient'))


def build_dungeon_warden_pathfinder(seed: int) -> Dungeon:
    from vimny.engine.warden_mega import init_mega
    rng = random.Random(seed)

    # ── Room 0: the Arena ───────────────────────────────────────────────────
    R, C = _PF_ROWS, _PF_COLS
    cells = [[CellType.WALL] * C for _ in range(R)]
    for r in range(1, R - 1):
        for c in range(1, C - 1):
            cells[r][c] = CellType.FLOOR
    for r in range(1, R - 1):               # seal the treasure room off (one locked-door gap)
        if r != _PF_DOOR[0]:
            cells[r][_PF_TR_WALL] = CellType.WALL
    # Four stone columns at the inner vertices of a 3×3 grid — the hall stays open.
    for (cr, cc) in _PF_COLUMNS:
        cells[cr][cc] = CellType.WALL
    arena = Room(room_type=RoomType.BOSS, rows=R, cols=C)
    arena.cells     = cells
    arena.seed      = seed
    arena.spawn_pos = (_PF_MAIN_ROW, 2)
    arena.exit_pos  = _PF_TR_EXIT           # the exit lives in the treasure room, behind the locked door
    arena.char_runs = []
    arena.entities  = []
    arena.search_glyph_entities = True      # /W finds the Warden + echoes wherever they leap

    for (cr, cc) in _PF_COLUMNS:            # the column glyph (renders over the wall cell)
        arena.char_runs.append(CharRun(cr, cc, ('▣',), 'ancient'))

    warden = Entity(kind='warden', row=_PF_WARDEN_START[0], col=_PF_WARDEN_START[1],
                    hp=3, max_hp=3, ai='', tag='pathfinder',
                    edit_immune=True, summon_timer=6)
    shield = Entity(kind='shield', row=_PF_WARDEN_START[0], col=_PF_WARDEN_START[1] - 1)
    arena.entities.append(warden)
    arena.entities.append(shield)
    echoes = []
    for (r, c, sh) in _PF_ECHO_CELLS:
        # Echoes are disguised as 'W' (tag='echo') but auto-unmask after the verse collapse.
        # Each takes only 1 hit to kill (after automatic unmasking).
        g = Entity(kind='goblin', row=r, col=c, hp=1, max_hp=1, tag='echo', shade=sh)
        echoes.append(g)
        arena.entities.append(g)

    # The real Warden isn't always the central one: half the time, swap him with a
    # random impostor so `/W` + the visual-immunity tell are the only way to find him.
    if rng.random() < 0.5:
        decoy = rng.choice(echoes)
        (warden.row, warden.col), (decoy.row, decoy.col) = \
            (decoy.row, decoy.col), (warden.row, warden.col)
        shield.row, shield.col = warden.row, warden.col - 1   # keep his shield at his flank
    arena.entities.append(Entity(kind='locked_door',     row=_PF_DOOR[0],     col=_PF_DOOR[1]))
    arena.entities.append(Entity(kind='exit',            row=_PF_TR_EXIT[0],  col=_PF_TR_EXIT[1]))
    arena.entities.append(Entity(kind='heart_container', row=_PF_TR_HEART[0], col=_PF_TR_HEART[1]))
    arena.entities.append(Entity(kind='chest_scroll',    row=_PF_TR_SCROLL[0],col=_PF_TR_SCROLL[1]))

    arena.rebuild_indexes()
    # Fog the treasure room (unreachable behind the locked door). Standard for every level —
    # and it also makes the fogged cells non-passable, so line_extent stops at the wall and a
    # `G vgg x` sweep can't reach across it into the treasure room.
    _fog_unreachable(arena, _PF_MAIN_ROW, 2)
    init_mega(arena, _PF_FIGHT)
    arena.par    = None
    arena.budget = 160                      # provisional — refine once the par sim exists

    # ── Room 1: the Wardenverse (ONE long line; wraps reactively to the terminal) ──
    VC = _PF_VERSE_COLS
    vcells = [[CellType.FLOOR] * VC]
    vcells[0][0] = vcells[0][VC - 1] = CellType.WALL
    for c in _PF_VERSE_WALLS:                 # the segment walls — $ / l / w stop here; gj/gk hop over
        vcells[0][c] = CellType.WALL
    verse = Room(room_type=RoomType.BOSS, rows=1, cols=VC)
    verse.cells       = vcells
    verse.seed        = seed
    verse.wrap_buffer = True                 # ':set wrap' soft-wraps it to the live content width
    verse.spawn_pos   = (0, 1)
    verse.char_runs   = []
    verse.entities    = []
    _pf_lay_verse(verse, rng)
    # The Warden runs the wrapped line; he's chased down (gj/gk) and stilled with :set nowrap.
    verse.entities.append(Entity(kind='warden', row=0, col=VC - 6, hp=3, max_hp=3,
                                 ai='', tag='verse', edit_immune=True))
    verse.exit_pos = None                    # no exit here — his death collapses the verse (vimny/game.py)
    verse.rebuild_indexes()
    verse.par    = None
    verse.budget = 160

    dungeon = Dungeon(name='The Warden Pathfinder', seed=seed)
    dungeon.rooms        = [arena, verse]
    dungeon.current_room = 0
    return dungeon


# ── The Operator's Vault ─────────────────────────────────────────────────────
# The first operator level: teaches the {operator}{motion} grammar via DELETE.
# Ten single-row corridors, snaked together (boustrophedon) three rows apart so
# a guard only wakes (Manhattan <= 5) once the player enters its corridor.
# Guards are ARMORED (hp 2): blade-to-blade x costs strikes and blood, but a
# d-cut removes them outright — the operator IS the weapon. Each corridor
# admits exactly one cheapest cut; everything else loses on keystrokes, landing
# position, shredded treasure, or an oubliette:
#
#   row  3  →  dw   guard in the gap after a word; the chest on the next
#                   word's 2nd char dies to any wider cut; gold gate
#   row  6  ←  db   word head one step from the shaft mouth — db's landing
#                   beats d0's line-start overshoot
#   row  9  →  de   guard riding the word's last letter; the chest in the gap
#                   after it dies to d$ (and the gate blocks w's scan, so dw
#                   can't fire)
#   row 12  ←  dB   one guard rides a mixed token's HEAD, one waits beyond: db
#                   only reaches the trailing subword — dB sweeps the WORD head
#   row 15  →  dE   guard rides a mixed token's tail: de crawls subword ends;
#                   the scroll chest past the gap punishes dW/d$
#   row 18  ←  dF?  pack of three behind a '?' bait that sits ON the shaft
#                   mouth — dF? lands you exactly there; d0 overshoots
#   row 21  →  dW   guards across a mixed token and its gap: dE stops at the
#                   token's tail; the chest on the next word punishes d$
#   row 24  ←  d0   pack of three to sweep, one at the line head so a one-cast
#                   db misses it; dd collapses the row into an oubliette
#   row 27  →  d$   pack of three ahead with no character beyond the last, so
#                   no find/word motion reaches them all
#   row 30  ←  dd   dead-end overhang: the LAST pack paces a sealed ledge one
#                   row below — dd cuts the floor line away, the ledge rises to
#                   you, and a d$ reprise sweeps it; a second dd drops you into
#                   the oubliette pocket below
#
# Gates are edit_immune locked doors (they also parry dd on their rows). Each
# gated corridor's colored key drops beside its gate when that corridor's guard
# group ('g1'/'g3'/'g7') is wiped; the untagged VAULT key drops by the vault
# door once EVERY guard is down (both wired statelessly and undo-safely in
# main._operators_vault_tick — gate tags are unique, so the tick looks doors up
# live by tag and survives undo's entity-list replacement). Oubliettes: SEALED
# 1-cell floor pockets under the corridors — dd's cursor parks on the collapsed
# row's first passable column, i.e. inside the pocket; only u climbs out. The
# first spacer under each corridor has a pocket at col 3, the second at col 1,
# so even a chained dd just falls one pocket deeper (and the }/{ own-segment
# landing rule keeps the pockets sealed against paragraph jumps). After every
# cut the player travels by whichever is cheapest — single-digit counts or the
# words left standing (no count in the answer exceeds 9); the connector shafts
# after backward corridors sit AWAY from the line start so d0 overshoots their
# mouths, while forward corridors end at $. Corridor text
# is drawn fresh from the vocabulary files every seed — positions and lengths
# are fixed (so par/answer hold for every seed), the letters never are.
# par/answer below; see tests/test_operators_vault.py for the executed solve.
_OV_ROWS, _OV_COLS = 35, 60
_OV_CORR_ROWS = (3, 6, 9, 12, 15, 18, 21, 24, 27, 30)
_OV_LCOL, _OV_RCOL = 2, 57            # corridor floor spans these columns
# two-row connector shafts below corridors 1..9: (top_row, col). Forward (→)
# corridors drop at the line end (col 57, one $ away); backward (←) ones drop
# mid-line so 0 overshoots the mouth.
#   EVERY SHAFT SITS BEHIND A GATE, which is what keeps this level dark. The
#   fog is derived, not listed (`_doors_block_sight` → `_fog_unreachable`
#   floods by FEET and stops at shut doors), so a shaft the flood can reach is a
#   corridor lit from the spawn and a `{n}G` that skips a lesson. Getting the
#   shafts behind the doors is not free, because the level teaches `p` and not
#   `P`: a gate can only be opened from the WEST, so it must always be east of
#   the player, and the way DOWN must be east of the gate.
#
#   Forward (→) corridors get that for nothing — they end at the line end, so
#   the gate goes at col 57 and the shaft directly beneath it.
#
#   Backward (←) corridors cannot: the cut carries the cursor west and there is
#   no floor west of the line head to paste from. So a backward corridor keeps
#   no gate of its own. It drops at col 2, and ITS gate stands one row down at
#   col 3 — the first thing the next corridor meets, opened with the word the
#   backward cut is still holding. The corridor below is dark until it is.
_OV_SHAFTS = tuple((r + 1, 57 if i % 2 == 0 else 2)
                   for i, r in enumerate(_OV_CORR_ROWS[:-1]))
# the oubliette pockets: (row, col) — sealed 1-cell floor cells. Col 3 on a
# first spacer row (catches a corridor dd), col 1 on the second (catches a
# chained dd from inside the first), plus the two under the vault approach.
#
# Only under the FORWARD corridors. A backward corridor's shaft comes down at
# col 2, one cell from where a pocket would sit, and a pit that touches the way
# out is not a pit — it is an alcove. Those corridors are guarded instead by
# what a `dd` puts in the register: the whole row, filler and all, which is not
# a word any gate below will hear.
_OV_POCKETS = tuple((r, 3) for r in (4, 10, 16, 22, 28)) + \
              tuple((r, 1) for r in (5, 11, 17, 23, 29)) + \
              ((32, 3), (33, 1))
#: THE SEEP — how C10's lesson is taught without being told.
#:
#: A hint used to fire on arrival at the overhang saying, in as many words, that
#: `dd` cuts the floor out from under you. This replaces it with something to
#: look at. A one-cell shelf hangs below corridor 8's gate column, and beneath
#: THAT is water, sitting in C10's own line. Both are behind the gate, so they
#: surface exactly when corridor 8's word is spoken — early enough to be
#: remembered, far enough ahead to be a question rather than an instruction.
#:
#: What the player sees is a passage stopped by one line of water. What `dd` on
#: the overhang does is take that line out, and the shelf then opens onto the
#: ledge that rose into its place. The hint is that the two are the same line.
_OV_SEEP_SHELF = (29, 3)              # the dry cell you can stand on…
_OV_SEEP_WATER = (30, 3)              # …and the line of water under it, which
                                      # is C10's floor line seen from above
_OV_SPLIT_ROW  = 30                   # C10: floor 30..57 — a dead-end overhang
_OV_LEDGE_ROW  = 31                   # the sealed ledge under it: floor 3..29
_OV_VAULT_ROW  = 33                   # antechamber + vault: floor 5..19
_OV_DOOR       = (33, 17)             # vault door (untagged); the EXIT is the prize
# answer keystrokes (operators written as separate single-key tokens: 'd w' = dw)
#: PAR IS THE OPTIMUM. The route alternates, because the corridors do:
#:
#:   FORWARD (→): cut, `$` to the gate at the line end, `p`, and the shaft is
#:     the cell you just stepped onto — `3j` and you are in the next corridor.
#:   BACKWARD (←): the cut IS the approach, `0` takes you to the drop, and you
#:     carry the word DOWN. The `p` that spends it is the first key of the next
#:     corridor, opening the gate that was holding that corridor dark.
#:
#: So a `p` at the head of a line below is not travel — it is the previous
#: lesson being paid for, one row late.
#: EVERY BACKWARD DROP IS A BARE `G`, AND THE COUNT WAS ALWAYS A MISTAKE. This
#: level's fog is DERIVED: everything past the shut gate ahead is dark, and a
#: fogged cell is not standable — so as far as any line jump can tell, the
#: BUFFER ENDS AT THE FRONTIER. `G` therefore means 'as far down as the light
#: goes', which on a backward corridor is precisely the drop `0 3j` was walking
#: to, for one key instead of three. It re-aims itself every time a gate opens,
#: which is why one key serves all four drops and no count is needed.
#:
#: This was written as `0 3j` (and one `7G`) until 2026-08-02, on the reasoning
#: that a counted jump only beats the walk when its count is a single digit —
#: true, and beside the point, because the jump never needed a count at all.
#: PAR IS THE OPTIMUM, so 62 was simply wrong; the route that exists is 55.
#: `G` over `L` deliberately: `L` is viewport-relative and would make par a
#: function of the player's terminal height, while `G` reads the buffer.
_OV_PAR = 55
_OV_ANSWER = ('dw $ p 3j '                    # C1  → dw, from the spawn, which
                                              # is the password's own head
              'db G '                         # C2  ← db, then ride down holding
                                              # the word (G = the frontier, which
                                              # IS the drop while the fog holds)
              'p de $ p 3j '                  # C3  → speak C2's word, then de
                                              # (you land on BLANK a cell short
                                              # of the password, so w has
                                              # nothing to take)
              'dB G '                         # C4  ← dB over the split token
              'p dE $ p 3j '                  # C5  → dE
              'dF? G '                        # C6  ← dF? back to the leading ?
              'p l dW $ p 3j '                # C7  → dW; the l steps onto the
                                              # password's head, which the gate
                                              # cell itself cannot hold
              'b d0 G '                       # C8  ← d0; b parks you on the far
                                              # word, so dd — which would sweep
                                              # it in — is no longer the same cut
              'p d$ $ p 3j '                  # C9  → d$
              'dd $ p G $')                   # C10 ← dd drops the floor line and
                                              # rides down; the gate is on the
                                              # ledge and the vault is below it


#: The Vault's passwords, sorted by SHAPE — which motion can take one in a
#: single cut. The words themselves live in `vimny/content/passwords.py`, because the
#: forge offers them too: a door placed by hand should be able to want the same
#: words the built levels want. Read that module's docstring before adding one;
#: the rule that every entry be a REAL password is load-bearing, not flavour.
_OV_PLAIN  = _passwords.PLAIN
_OV_SPLIT  = _passwords.SPLIT
_OV_QUERY  = _passwords.QUERY
_OV_PHRASE = _passwords.PHRASE

#: The first password is ALWAYS `password`. The level's whole model — that a
#: door can want words instead of a key — has to be legible the first time it
#: is met, and nothing says "this is a password" like the word being it. The
#: puzzle is not learning it (it is lying on the floor in front of the door);
#: the puzzle is taking it in ONE cut. Pinning corridor 1 makes the RULE free
#: so the CUT can be the lesson.
_OV_FIRST = 'password'

#: corridor -> the pool its lesson needs. Corridor 1 is pinned, so it is not
#: drawn; everything else is shuffled within its shape, which keeps the seeds
#: genuinely different without ever handing a corridor a password its own
#: motion cannot take.
_OV_SHAPES = {2: _OV_PLAIN, 3: _OV_PLAIN,
              4: _OV_SPLIT, 5: _OV_SPLIT, 7: _OV_SPLIT,
              6: _OV_QUERY,
              8: _OV_PHRASE, 9: _OV_PHRASE, 10: _OV_PHRASE}


def _ov_passwords(rng) -> dict:
    """Deal this seed's passwords: corridor number -> the words that open it.

    Shuffled WITHIN each shape and never across it. Drawing at random from one
    big pool would eventually hand corridor 8 a single token — and a single
    token is takeable by a character motion, which is exactly the cheap
    substitution the doors exist to refuse. The shape is the lesson; only the
    words rotate.

    No password is used twice in a level. Two doors wanting the same words
    would let one corridor's cut open another's gate, and a player who noticed
    would be right to walk past the lesson in between.
    """
    out, used = {1: _OV_FIRST}, {_OV_FIRST}
    for corridor in sorted(_OV_SHAPES):
        pool = [w for w in _OV_SHAPES[corridor] if w not in used]
        word = rng.choice(pool)
        used.add(word)
        out[corridor] = word
    return out


def _ov_pick(rng, table, length, used, pred=None):
    """Draw a fresh vocab token of exactly `length` from a length-keyed table
    (no repeats within the level; optional structural predicate)."""
    pool = [t for t in table.get(length, ())
            if t not in used and (pred is None or pred(t))]
    tok = rng.choice(pool)
    used.add(tok)
    return tok


def _ov_plain_ok(tok: str) -> bool:
    """A 'plain' token usable as a single word: every char a word char, so
    w/b/e treat it as ONE word. The vocab file enforces this — this stays
    as a guard so a future vocab edit
    can't silently shift the lesson landings."""
    return all(_is_word_char(c) for c in tok)


def build_dungeon_operators_vault(seed: int) -> Dungeon:
    rng = random.Random(seed)
    _load_vocab_tables()
    R, C = _OV_ROWS, _OV_COLS
    cells = [[CellType.WALL] * C for _ in range(R)]

    def floor(r, c0, c1):
        for c in range(c0, c1 + 1):
            cells[r][c] = CellType.FLOOR

    for r in _OV_CORR_ROWS[:-1]:                  # corridors 1..9: full span
        floor(r, _OV_LCOL, _OV_RCOL)
    floor(_OV_SPLIT_ROW, 30, _OV_RCOL)            # C10: a dead-end overhang…
    floor(_OV_LEDGE_ROW, 3, 29)                   # …over the sealed vault ledge.
                                                  # It reaches col 3 so that the
                                                  # cell under the seep is FLOOR:
                                                  # when `dd` takes the water's
                                                  # line out, the ledge rises
                                                  # into its place and the shelf
                                                  # at (29,3) opens onto it. The
                                                  # two halls are joined by the
                                                  # cut, which is the lesson.
    for (top, col) in _OV_SHAFTS:                 # the connector shafts
        cells[top][col] = cells[top + 1][col] = CellType.FLOOR
    for (r, c) in _OV_POCKETS:                    # the oubliette pockets
        cells[r][c] = CellType.FLOOR
    # A sunken channel runs the whole west face: cols
    # 1-2 of every spacer row are WATER under MIST, one continuous seep
    # linking the pools so the col-1 oubliettes are seen ACROSS WATER, not
    # through stone. The water matters twice: fogged water conducts no
    # reveal flood (engine law), so the channel cannot ladder this level's
    # corridor-by-corridor fog past the gates — and it bars the $ / f
    # scans as the stone did. Converted AFTER _fog_unreachable (below), so
    # the build flood sees stone here too.
    cells[_OV_SEEP_SHELF[0]][_OV_SEEP_SHELF[1]] = CellType.FLOOR   # see _OV_SEEP_*
    cells[32][10] = CellType.FLOOR                # ledge → antechamber drop
                                                  # (under C10's gate, so the
                                                  # gate opening IS the way down)
    floor(_OV_VAULT_ROW, 5, 19)                   # antechamber + vault

    from vimny.engine.editor import _CELL_CODE
    from vimny.sharing import format as _fmt
    from vimny.sharing.format import Level as _Level, build as _fmt_build
    spawn_pos = (3, _OV_LCOL)                     # the line head, on C1's own
                                                  # password: `dw` fires at once
    exit_pos  = (33, 19)
    runs:   list = []
    entities: list = []

    def word(r, c, text, kind='ember'):
        runs.append({'row': r, 'col': c, 'symbols': text, 'kind': kind})

    def phrase(r, c, text):
        # A multi-word password, laid as one run per token with a real gap
        # between them — the gaps are what stop every character motion, which
        # is the only reason the line-motion corridors can teach anything.
        for tok in text.split():
            word(r, c, tok)
            c += len(tok) + 1

    def chest(r, c):
        entities.append({'kind': 'chest_scroll', 'at': [r, c]})

    def fancy(r, c, password):
        # The corridor's gate. It opens for a register reading exactly its
        # password and for nothing else, which is what makes the corridor's own
        # motion the ONLY one that clears it: a narrower cut hands over a
        # fragment, a wider one hands over the fragment plus whatever it swept
        # up on the way. See Entity.password.
        entities.append({'kind': 'fancy_door', 'at': [r, c],
                         'password': password, 'edit_immune': True,
                         'opaque': True})

    #: this seed's passwords, corridor number -> words (see _ov_passwords)
    pw = _ov_passwords(rng)

    # The FILLER words are drawn fresh from the vocabulary each seed — only
    # their lengths are fixed, since the layout keys off those and the letters
    # never matter. The mixed-token pick that used to lay this level's lesson
    # words is gone: the words that carry a lesson are the PASSWORDS now, and
    # those are hand-written pools chosen for their shape (see _OV_SHAPES).
    used: set = set()

    def plain(n):
        return _ov_pick(rng, _VOCAB_PLAIN_BY_LEN, n, used, _ov_plain_ok)

    # ── THE CORRIDORS ────────────────────────────────────────────────────────
    # Every one is the same three pieces:
    #
    #   the PASSWORD — the words the gate wants, and the ONLY thing the cut may
    #     take. Its spelling is the lesson: a plain token reads the same under
    #     both word models, a token with punctuation inside it splits them, and
    #     a phrase is out of reach of every character motion. (See _OV_SHAPES.)
    #   the FILLER — a word placed where a cut that reaches too far will sweep
    #     it in. This is the half the old gauntlet could not build: a guard
    #     punishes a cut that takes too LITTLE, because he survives it, but
    #     every guard a `dw` kills a `d$` kills too, so nothing punished taking
    #     too much. A door that reads the register does, and refuses two words
    #     where it wanted one.
    #   the GATE — a `fancy_door`, always EAST of the player, because the level
    #     teaches `p` and not `P`. A forward corridor's gate is at its line end
    #     (col 57) with the shaft directly beneath it. A backward corridor's is
    #     one row DOWN at col 3, where the player lands after dropping at col 2,
    #     and it is opened with the word that corridor's cut is still holding.
    #     Either way the shaft is BEHIND a shut door, which is what keeps the
    #     corridor below it dark (see _OV_SHAFTS).
    #
    # WHERE THE CURSOR ARRIVES IS PART OF THE PUZZLE. `dw` and `de` cut the same
    # TEXT from the same start — they differ only by the trailing space, and the
    # gate collapses whitespace (it must, or `dd`'s column padding would never
    # match). So the two are told apart by the START CELL instead: the `de`/`dE`
    # corridors drop the player on BLANK floor a cell short of the password, and
    # from there `w`/`W` land on the password's head and cut nothing at all,
    # while `e`/`E` still reach its end. The `dw`/`dW` corridors drop the player
    # on the head, where the twin still ties — that one is irreducible, and it
    # is vim being consistent rather than the lesson leaking.
    #
    # GLUE. A short token welded to the password with a full stop, where the
    # small and big word models have to be prised apart on a password that is
    # plain: `.xyz` on the tail makes `E`/`W` overshoot, `xyz.` on the head
    # makes `B` overshoot. It reads as a rune-prefix and it is a spelling trick,
    # but it is the same spelling trick the split passwords play for free.

    _GATE = 57                                    # a forward corridor's gate
    _HEAD = _OV_LCOL                              # where `0` lands, and where a
                                                  # backward corridor drops from
    _LAND = _HEAD + 1                             # a backward corridor's gate,
                                                  # one row down, one cell east
                                                  # of where its drop lands you

    # C1 (row 3, →, arriving on the spawn at the line head): dw. THE CORRIDOR
    # THAT TEACHES THE MODEL, so its password is always the word `password` —
    # the rule has to be free the first time it is met, so that the CUT can be
    # the lesson. The spawn is the password's own head, so `dw` fires at once.
    _p = pw[1]
    word(3, _HEAD, _p + '.' + plain(3))           # tail glue: dE/dW overshoot it
    word(3, _HEAD + len(_p) + 6, plain(3))        # filler: d$ / dd sweep it in
    fancy(3, _GATE, _p)
    # C2 (row 6, ←, arriving at col 57): db. THE BACKWARD PATTERN, and it is not
    # C1 mirrored. The cut IS the approach — `db` carries the cursor from the
    # line end back to the password's head — and there is no gate on this row at
    # all: you drop at col 2 still HOLDING the word, and spend it on the door
    # waiting at the head of the corridor below.
    #
    # That door is also what keeps this corridor's own descent honest: a word
    # motion stops at a shut fancy door exactly as `$`/`0` do
    # (`_next_glyph_cell` walks `is_passable`), and the fog flood stops there
    # too, so the corridor below is dark until the word is spoken.
    _p = pw[2]
    word(6, _HEAD, plain(3))                      # filler: d0 / d^ sweep it in
    word(6, 52 - len(_p), plain(3) + '.' + _p)    # head glue: dB overshoots it
    # C3 (row 9, →, arriving at col 2, on C2's gate): de. The `p` that opens it
    # is C2's lesson being paid for a row late; it leaves the player on col 3,
    # one BLANK cell short of the password, which is what stops `w` — it lands
    # on the head and cuts nothing, while `e` still reaches the end.
    _p = pw[3]
    fancy(9, _LAND, pw[2])
    word(9, _HEAD + 3, _p + '.' + plain(3))
    word(9, _HEAD + len(_p) + 9, plain(3))
    fancy(9, _GATE, _p)
    # C4 (row 12, ←): dB. The password is split, so `db` reaches only its
    # trailing subword and hands the gate a fragment. No glue is needed here —
    # the punctuation inside the password IS the glue.
    _p = pw[4]
    word(12, _HEAD, plain(3))
    word(12, 57 - len(_p), _p)
    # C5 (row 15, →, on C4's gate): dE
    _p = pw[5]
    fancy(15, _LAND, pw[4])
    word(15, _HEAD + 3, _p)
    word(15, _HEAD + len(_p) + 5, plain(3))
    fancy(15, _GATE, _p)
    # C6 (row 18, ←): dF?. The mark LEADS the password, because `dF?` cuts from
    # the `?` up to the cursor — a trailing `?` would be found by the cut only
    # after the words it was meant to carry.
    _p = pw[6]
    word(18, _HEAD, plain(3))
    word(18, 52 - len(_p), plain(3) + '.' + _p)
    # C7 (row 21, →, on C6's gate): dW. This is the one corridor that pays a
    # step: `W` needs the cursor ON the password's head, and the head cannot be
    # the gate's own cell, so `l` walks the one square between them.
    _p = pw[7]
    fancy(21, _LAND, pw[6])
    word(21, _HEAD + 2, _p)
    word(21, _HEAD + len(_p) + 4, plain(3))
    fancy(21, _GATE, _p)
    # C8 (row 24, ←): d0. On a line whose cursor sits at its END, `dd` and `d0`
    # take the same text — so this corridor's approach is `b`, which parks the
    # player on the far word instead of past it. With a word still east of the
    # cursor, `dd` sweeps one too many and `d0` does not. `d^` stays a true
    # twin: the phrase IS the line's first non-blank, and that is `0` and `^`
    # being the same motion, not a hole in the lesson.
    _p = pw[8]
    phrase(24, _HEAD, _p)
    word(24, 52, plain(3))                        # filler: dd sweeps it in, and
                                                  # the `b` target on the way in
    # C9 (row 27, →, on C8's gate): d$. The single rune at col 2 — the cell the
    # drop lands on, WEST of the gate and so west of everything the cut can
    # reach — is what separates `d$` from `dd`. It is one glyph because one
    # glyph is all there is room for, and one is enough: `dd` takes it, `d$`
    # cannot.
    _p = pw[9]
    fancy(27, _LAND, pw[8])
    word(27, _HEAD, '#', kind='ancient')
    phrase(27, _HEAD + 3, _p)
    fancy(27, _GATE, _p)
    # C10 (row 30, ←, arriving at col 57 — on the phrase's LAST character): dd.
    # The password runs right up to the cursor so that `d0`, which stops one
    # short of it, hands the gate a phrase with its final letter missing.
    #
    # The cut drops the floor line and the player rides down onto the ledge,
    # landing Vim-true on its first non-blank. The gate is there, and the vault
    # is below it — this is the last backward corridor, and like the others it
    # carries its word one step further on before spending it.
    _p = pw[10]
    phrase(30, 58 - len(_p), _p)
    # This word sets where `dd` lands, and it is laid at the seep's own column
    # ON PURPOSE. Vim's linewise landing is the first non-blank of the line that
    # took the deleted line's place ('startofline', default on) — so the cut
    # drops the player onto exactly the cell the water was filling, directly
    # under the shelf. The line you could not cross is the line you end up
    # standing in, which is the whole lesson stated as a position rather than a
    # sentence. Anywhere else and the landing is arbitrary.
    word(_OV_LEDGE_ROW, _OV_SEEP_WATER[1], plain(3))
    fancy(31, 10, _p)
    chest(33, 7); chest(33, 12)                   # loot in the antechamber
    # the vault: the door and the way out
    entities.append({'kind': 'seal_door', 'at': [_OV_DOOR[0], _OV_DOOR[1]],
                     'edit_immune': True, 'opaque': True})
    entities.append({'kind': 'exit', 'at': [33, 19]})

    # The west-face sunken seep, laid BEFORE the fog so the law sees it as the
    # terrain it is. It runs on the CORRIDOR ROWS ONLY.
    #
    # It used to run unbroken from top to bottom, and that was the one thing in
    # this level whose fog could not be derived: water does not stop the eye
    # (feet treat it as impassable, sight does not — it is weather), so the seep
    # was a clear sightline down the west face and out along every corridor
    # behind every shut door. 569 cells had to be fogged by hand to cover it.
    # Broken into corridor-row stubs, the sightline is gone and the whole vault
    # derives from its walls and its doors. Verified: the canonical tape still
    # solves at exactly par, unharmed, on every seed — the goblins never had to
    # path around the pocket mouths after all.
    #
    # The pits are no longer lit from the spawn, and that is the honest reading:
    # you meet each pit when you reach its corridor, not from the doorway of a
    # vault you have not opened.
    underwater: set = set()
    for r in _OV_CORR_ROWS:
        for c in (1, 2):
            if cells[r][c] == CellType.WALL and (r, c) not in _OV_POCKETS:
                cells[r][c] = CellType.WATER
                underwater.add((r, c))
    # …and the seep that teaches C10 (see _OV_SEEP_*). PLAIN water, deliberately
    # NOT sunken: underwater ground is permanent haze that a reveal never clears (it is what
    # stops the west channel laddering light past the gates), so a sunken cell
    # can never be the thing a player is meant to SEE. Ordinary water conducts
    # the flood, surfaces with the shelf above it, and stops there — the ledge
    # below stays dark because row 31's floor starts east of this column.
    cells[_OV_SEEP_WATER[0]][_OV_SEEP_WATER[1]] = CellType.WATER

    def encode(r):
        return ''.join(_fmt._UNDERWATER_CODE if (r, c) in underwater else _CELL_CODE[ct]
                       for c, ct in enumerate(cells[r]))

    level = _Level(
        name="The Operator's Vault", seed=seed,
        rows=R, cols=C,
        cells=[encode(r) for r in range(R)],
        spawn=spawn_pos, exit=exit_pos,
        char_runs=runs,
        entities=entities,
        solution=_OV_ANSWER)                      # dd's Vim-true fnb landing

    dungeon = _fmt_build(level, par=_OV_PAR)
    room = dungeon.rooms[0]
    # A d-operator teaching level: bare-w navigation must stay precise (text
    # words only), so opt out of the jump-to-entity word-stop behaviour.
    room.entity_word_stops = False
    return dungeon


# ── The Cipher Cell — r + D ───────────────────────────────────────────────────
_CC_ROWS, _CC_COLS = 6, 64
_CC_ROW        = 2                     # the single gauntlet row (floor cols 1..60)
_CC_PLAQUE_ROW = 1                     # sealed plaque band: all WALL, glyphs embedded.
                                       # Visible (no fog on this level), untouchable —
                                       # and with only ONE floor row in the dungeon, no
                                       # visual selection can ever straddle it.
_CC_FLOOR_LO, _CC_FLOOR_HI = 1, 60
_CC_SPAWN  = (2, 2)
_CC_EXIT   = (2, 60)
# ONE rule opens every door: the lock row must READ AS ITS PLAQUE. The plaque
# band above shows each span's true state — a word with a blank tail — and the
# lock row decays it two ways: a warped rune where a letter belongs (mend it
# with r) and rot-text sprawling past the word (shear it with D). All four
# doors are BOLTS (wall cells managed by the tick). The two tail bolts double
# as reflow shields: close_gap's leftward pull stops at a wall, so a shear in
# one stretch can never drag the next beat's cipher across its bolt.
_CC_BOLT_A = (2, 10)                   # cell A bolt — open while cipher A reads true
_CC_BOLT_B = (2, 33)                   # jammed door — open while span 1 matches its plaque
_CC_BOLT_C = (2, 43)                   # cell B bolt — cipher B
_CC_BOLT_D = (2, 59)                   # the last jammed door — span 2
_CC_CIPHER_A_COL, _CC_CIPHER_B_COL = 4, 36
_CC_WORD1_COL,  _CC_WORD2_COL  = 13, 46
_CC_ROT1 = (18, 32)                    # rot-text spans (walkable letter soup)
_CC_ROT2 = (51, 58)
_CC_SPAN1 = (13, 32)                   # plaque-match spans: word + blank tail
_CC_SPAN2 = (46, 58)
_CC_WARP_A = 2                         # warped letter index in word A (never 0: w must
                                       # land on the word before stepping to the warp)
# Word combos: (cipher A, survivor 1, cipher B, survivor 2). Shapes are fixed so
# par is seed-invariant: A is 4 letters warped at index 2; B is 5 letters with a
# DOUBLED letter warped (both copies — the art rules' double-letter law); the
# survivors are 4 letters. Every combo satisfies TRUE-LETTER SCARCITY: each
# warped letter appears in no other displayed word, so x + p can transplant
# nothing and r is structurally the only fix (asserted at build).
_CC_COMBOS = (
    ('opal', 'rust', 'skiff', 'echo'),
    ('hymn', 'oats', 'droll', 'grub'),
    ('kiwi', 'dust', 'gamma', 'echo'),
    ('ruby', 'mint', 'fuzzy', 'acre'),
)
_CC_WARP_GLYPHS    = ('♄', '☿', '♆', '⚸')   # warped runes — untypable, punct class
_CC_PAR = 16                           # seed-invariant; tallied in the answer below


def build_dungeon_cipher_cell(seed: int) -> Dungeon:
    """The Cipher Cell: teaches r (replace one char, in place — the
    substitution-cipher tool) and D (delete to line end, ONE keypress).

    A decayed prison row, read against the plaque band sealed in the wall above
    it: ONE rule opens every door — make the lock row read as its plaque. The
    plaques show each span's true state (a word, then blank); the row beneath
    has decayed two ways: a warped rune where a letter belongs (mend it in
    place with r) and rot-text sprawling where the plaque is blank (shear it to
    the wall with D). Geometry is fixed; the seed picks the word combo, the
    warp glyph and the rot soup, so par is seed-invariant and locked at
    _CC_PAR while the answer's letters track the combo. All four doors are
    plain `Seal` gates (region/exact — stateless and undo-safe).
    """
    rng = random.Random(seed)
    word_a, word_1, word_b, word_2 = rng.choice(_CC_COMBOS)
    warp_b = next(i for i in range(len(word_b) - 1) if word_b[i] == word_b[i + 1])
    warp_glyph = rng.choice(_CC_WARP_GLYPHS)

    # True-letter scarcity — seals the x+p transplant leak (see _CC_COMBOS).
    # The rot soup is drawn from an alphabet EXCLUDING the warp letters so it
    # can't become a donor either.
    reachable_letters = set(word_1 + word_2) \
        | {ch for i, ch in enumerate(word_a) if i != _CC_WARP_A} \
        | {ch for i, ch in enumerate(word_b) if i not in (warp_b, warp_b + 1)}
    assert word_a[_CC_WARP_A] not in reachable_letters, (word_a, reachable_letters)
    assert word_b[warp_b] not in reachable_letters, (word_b, reachable_letters)
    soup_abc = [ch for ch in 'abcdefghijklmnopqrstuvwxyz'
                if ch not in (word_a[_CC_WARP_A], word_b[warp_b])]

    def rot_text(n: int) -> str:
        """`n` columns of decayed prose: letter-soup words with single gaps."""
        out: list = []
        while len(out) < n:
            if out:
                out.append(' ')
            for _ in range(min(rng.randint(2, 4), n - len(out))):
                out.append(rng.choice(soup_abc))
        return ''.join(out[:n])

    R, C = _CC_ROWS, _CC_COLS
    from vimny.engine.editor import _CELL_CODE
    from vimny.sharing.format import Level as _Level, build as _fmt_build
    cells = [[CellType.WALL] * C for _ in range(R)]
    for c in range(_CC_FLOOR_LO, _CC_FLOOR_HI + 1):
        cells[_CC_ROW][c] = CellType.CORRIDOR
    for (br, bc) in (_CC_BOLT_A, _CC_BOLT_B, _CC_BOLT_C, _CC_BOLT_D):
        cells[br][bc] = CellType.WALL              # the bolts start shut

    runs: list = []

    def lay(row, col, text, kind):
        """Place `text` at (row, col); spaces become gaps between separate runs."""
        c = col
        for piece in text.split(' '):
            if piece:
                runs.append({'row': row, 'col': c,
                             'symbols': piece, 'kind': kind})
            c += len(piece) + 1

    # Plaques: every span's TRUE state, sealed in the wall band (visible,
    # untouchable). Where a plaque is blank, the row below must be too.
    lay(_CC_PLAQUE_ROW, _CC_CIPHER_A_COL, word_a, 'verdant')
    lay(_CC_PLAQUE_ROW, _CC_WORD1_COL,   word_1, 'verdant')
    lay(_CC_PLAQUE_ROW, _CC_CIPHER_B_COL, word_b, 'verdant')
    lay(_CC_PLAQUE_ROW, _CC_WORD2_COL,   word_2, 'verdant')
    # The lock row, decayed: warped ciphers and rot-text past the plain words.
    lay(_CC_ROW, _CC_CIPHER_A_COL,
        word_a[:_CC_WARP_A] + warp_glyph + word_a[_CC_WARP_A + 1:], 'ancient')
    lay(_CC_ROW, _CC_CIPHER_B_COL,
        word_b[:warp_b] + warp_glyph * 2 + word_b[warp_b + 2:], 'ancient')
    lay(_CC_ROW, _CC_WORD1_COL, word_1, 'ancient')
    lay(_CC_ROW, _CC_WORD2_COL, word_2, 'ancient')
    for (lo, hi) in (_CC_ROT1, _CC_ROT2):
        lay(_CC_ROW, lo, rot_text(hi - lo + 1), 'ember')

    # The four bolts, as the format's own Seals — the echo-vault shape: each
    # stands open while the lock row's text over its span READS AS the plaque
    # (`scope='region', mode='exact'`; stateless, undo-safe). The blank-tailed
    # spans read identically under the region reader's whitespace collapse,
    # and this verb set (r/D) cannot put leading or double blanks in a span.
    def span_target(word, span):
        lo, hi = span
        return word + ' ' * (hi - lo + 1 - len(word))
    cc_seals = [Seal(region=(_CC_ROW, c0, _CC_ROW, c0 + len(target) - 1),
                     match=(target,), mode='exact', scope='region',
                     opens=((br, bc),))
                for c0, target, (br, bc) in (
                    (_CC_CIPHER_A_COL, word_a, _CC_BOLT_A),
                    (_CC_SPAN1[0], span_target(word_1, _CC_SPAN1), _CC_BOLT_B),
                    (_CC_CIPHER_B_COL, word_b, _CC_BOLT_C),
                    (_CC_SPAN2[0], span_target(word_2, _CC_SPAN2), _CC_BOLT_D),
                )]

    level = _Level(
        name='The Cipher Cell', seed=seed,
        rows=R, cols=C,
        cells=[''.join(_CELL_CODE[c] for c in row) for row in cells],
        spawn=_CC_SPAWN, exit=_CC_EXIT,
        char_runs=runs,
        entities=[{'kind': 'exit', 'at': [_CC_EXIT[0], _CC_EXIT[1]],
                   'edit_immune': True}],   # the final D's span sweeps its cell —
                                            # the way out must not be deletable
                                            # (nor the row dd-collapsible)
        seals=cc_seals,
        solution=(f'w w r{word_a[_CC_WARP_A]} w w D '
                  f'w w 2r{word_b[warp_b]} w w D $'))

    dungeon = _fmt_build(level, par=_CC_PAR)
    room = dungeon.rooms[0]
    # `Seal.message` is not file-format data; hand the banner back.
    from dataclasses import replace as _dc_replace
    room.seals = tuple(_dc_replace(
        s, message='The row reads as the plaque — the bolt grinds back!')
        for s in room.seals)
    return dungeon


# ── The Beacon Tiers — y / yy / P ─────────────────────────────────────────────
_QM_ROWS, _QM_COLS = 6, 48
_QM_HALL_ROW = 1                        # the supply hall (floor cols 1..45)
_QM_HALL_LO, _QM_HALL_HI = 1, 45
_QM_SPAWN  = (1, 2)
_QM_SOURCE = (1, 4)                     # the one lit brazier — the flame to spread
_QM_PED1   = (1, 14)                    # hall brazier — lit with the first paste
_QM_BOLT_COLS = (8, 18)                 # chain bolts A/B on the hall row: bolt k
                                        # stands open while flames 0..k ALL burn
_QM_SHAFT_COL = 45                      # east shaft: hall → beacon row (rows 2..3)
_QM_BRAZIER_ROW = 4                     # the beacon row (floor cols 34..45)
_QM_SHRINE_LO, _QM_SHRINE_HI = 34, 45
_QM_BRAZIER_COLS = (34, 35, 36)         # three ADJACENT cold braziers, flush against
                                        # the seal wall: standing on the first, 3P
                                        # fills all three; 3p (paste AFTER) leaves the
                                        # leftmost cold, and no cell exists to its west
_QM_SEAL_COL = 33                       # the seal: the brazier row's own west wall
_QM_EXIT = (4, 32)                      # exit POCKET behind the seal — walled on every
                                        # other side, so neither walking off the row's
                                        # east end nor any line jump can reach it
                                        # (G/{n}G/H/M/L land on a row's FIRST non-blank,
                                        # which is always a brazier's dots/flame; the
                                        # exit itself is CARET_TRANSPARENT)
_QM_FLAME  = '🜂'                        # one width-1 glyph IS the flame (untypable,
                                        # so r/insert can never forge one)
_QM_EMBERS = '…'                        # cold brazier: three dying embers, one cell
_QM_PAR = 14                            # seed-invariant; tallied in the answer below
#: The descent to the beacon row was `4G` until 2026-08-02, and `G` does it in
#: one key. The hall's lower tiers sleep under stone fog, and a fogged row has
#: no standable cell — so the BUFFER ends, as far as any line jump is concerned,
#: exactly where the light does, and `G` is 'as far down as I can see'. Unlike
#: `L` it is buffer-relative, so the tape means the same thing in every window.


def build_dungeon_quartermaster(seed: int) -> Dungeon:
    """The Beacon Tiers: teaches y (yank — copy WITHOUT cutting) and
    P (paste before the cursor); yy + paste raises whole rows.

    The depot's signal fire is down to one lit brazier; every cold brazier
    shows … dying embers — feed each one a flame. yl lifts the flame (the
    register keeps it through every paste); P lays it down — and ONLY onto
    a brazier (main._flame_paste_blocked: "there is no fuel to hold that
    flame" anywhere else; linewise paste is exempt — a yanked row's flames
    already sit in their braziers). The chain bolts are cumulative — bolt k
    stands open only while braziers 0..k ALL burn — so cutting the source
    visibly darkens the hall (copy, don't cut; u or a paste-back recovers).
    The beacon row holds three ADJACENT cold braziers flush against the
    seal wall: standing on the first, 3P fills all three in one stroke,
    while 3p (paste AFTER the cursor) leaves the leftmost cold — and no
    cell exists to its west to p from, so P is structurally the only fill.
    The finale: yy the lit beacon row and paste it twice — the beacon must
    burn in three tiers, and the whole depot must burn, to draw the seal.

    The exit sits in a one-cell POCKET behind the seal, west of the
    braziers — walled on every other side, so it cannot be walked into
    from any direction but through the drawn seal. Teleport audit
    (G/{n}G/H/M/L are long known): line jumps land on a row's first
    non-blank, which on the beacon row is always a brazier's dots/flame
    (the tick keeps one there every turn) and the exit entity itself is
    CARET_TRANSPARENT — no jump lands in the pocket. The shaft rows hold
    no glyphs, so jumps there land on the shaft itself. Geometry is fixed
    (seed-invariant); all doors run through main._quartermaster_tick —
    stateless and undo-safe.
    """
    R, C = _QM_ROWS, _QM_COLS
    from vimny.engine.editor import _CELL_CODE
    from vimny.sharing.format import (Level as _Level, build as _fmt_build,
                                      _parse_seal)
    cells = [[CellType.WALL] * C for _ in range(R)]
    for c in range(_QM_HALL_LO, _QM_HALL_HI + 1):
        cells[_QM_HALL_ROW][c] = CellType.FLOOR
    for r in (2, 3):                                     # east shaft, hall → beacon row
        cells[r][_QM_SHAFT_COL] = CellType.FLOOR
    for c in range(_QM_SHRINE_LO, _QM_SHRINE_HI + 1):
        cells[_QM_BRAZIER_ROW][c] = CellType.FLOOR
    cells[_QM_EXIT[0]][_QM_EXIT[1]] = CellType.FLOOR     # the exit pocket
    # Build state == tick steady-state: the chain holds only the source flame,
    # so bolt A stands open and bolt B (and the seal) start shut.
    cells[_QM_HALL_ROW][_QM_BOLT_COLS[1]] = CellType.WALL
    cells[_QM_EXIT[0]][_QM_SEAL_COL] = CellType.WALL

    runs: list = []
    runs.append({'row': _QM_SOURCE[0], 'col': _QM_SOURCE[1],
                 'symbols': _QM_FLAME, 'kind': 'flame'})
    for (r, c) in (_QM_PED1, *((_QM_BRAZIER_ROW, c) for c in _QM_BRAZIER_COLS)):
        runs.append({'row': r, 'col': c, 'symbols': _QM_EMBERS, 'kind': 'pedestal'})

    level = _Level(
        name='The Beacon Tiers', seed=seed,
        rows=R, cols=C,
        cells=[''.join(_CELL_CODE[c] for c in row) for row in cells],
        spawn=_QM_SPAWN,
        exit=_QM_EXIT,
        char_runs=runs,
        seals=[
            # The chain, as PER-BRAZIER predicates chained by requires: every
            # region is exactly one brazier cell, so a snuffed flame takes its
            # own predicate false the moment the run darkens — embers relayed
            # or not, no slot can fall out of consideration. Doors hang off
            # the predicates they need; the exit needs everything.
            _parse_seal({'mode': 'braziers',
                         'region': [_QM_SOURCE[0], _QM_SOURCE[1],
                                    _QM_SOURCE[0], _QM_SOURCE[1]]}, 0),
            _parse_seal({'requires': [0],
                         'opens': [[_QM_HALL_ROW, _QM_BOLT_COLS[0]]]}, 1),
            _parse_seal({'mode': 'braziers',
                         'region': [_QM_PED1[0], _QM_PED1[1],
                                    _QM_PED1[0], _QM_PED1[1]],
                         'requires': [0]}, 2),
            _parse_seal({'requires': [0, 2],
                         'opens': [[_QM_HALL_ROW, _QM_BOLT_COLS[1]]]}, 3),
        ] + [
            _parse_seal({'mode': 'braziers',
                         'region': [_QM_BRAZIER_ROW + k, c,
                                    _QM_BRAZIER_ROW + k, c],
                         'requires': [3]}, 4 + k * 3 + j)
            for k in range(3) for j, c in enumerate(_QM_BRAZIER_COLS)
        ] + [
            _parse_seal({'requires': [3] + list(range(4, 13)),
                         'opens': [[_QM_EXIT[0], _QM_SEAL_COL]]}, 13),
        ],
        braziers=sorted({_QM_SOURCE, _QM_PED1,
                         *((_QM_BRAZIER_ROW + k, c)
                           for k in range(3)
                           for c in _QM_BRAZIER_COLS)}),
        entities=[{'kind': 'exit', 'at': [_QM_EXIT[0], _QM_EXIT[1]],
                   'edit_immune': True}],   # nor its row dd-collapsible
        solution='w yl w P G 3P yy p P k 0')

    dungeon = _fmt_build(level, par=_QM_PAR)
    room = dungeon.rooms[0]
    # Hand the door banners back (Seal.message is engine-only data).
    from dataclasses import replace as _dc_replace
    _qm_banners = (
        '',                                          # the source predicate
        'The flame takes — the bolt grinds back!',   # chain bolt A
        '',                                          # hall brazier predicate
        'The flame takes — the bolt grinds back!',   # chain bolt B
    ) + ('',) * 9 + (                                # the nine tier predicates
        'The beacon burns in three tiers — the seal draws open!',  # the seal
    )
    room.seals = tuple(_dc_replace(s, message=m)
                       for s, m in zip(room.seals, _qm_banners))
    # Anchors read by main._quartermaster_tick (stored coordinates, the Cipher
    # Cell convention — a self-inflicted dd/linewise shift above them desyncs
    # the doors until u, which is the established recoverable failure mode).
    room._qm_bolt_cols = _QM_BOLT_COLS
    room._qm_seal_col  = _QM_SEAL_COL
    return dungeon


# ── The Echo Vault — . (dot-repeat) ───────────────────────────────────────────
# SENSE, NOT DECREE (the design law): the vault repeats
# what it hears — so the FIRST two spans are famous repetition itself:
#   phrase 1 = 'she sells sea shells' (every word carries exactly one 'e',
#              all four warped: mend once with r, and the echo takes three)
#   phrase 2 = 'humpty dumpty' (the 'u' pair — a fresh stroke re-primes)
# FIXED texts, deliberately (their letter-geometry IS the puzzle); the
# THIRD span stays a seeded digit beat — the count-dot lesson is numeric,
# and no song supplies a lone digit plus its tripled twin (flagged).
_EV_ROWS, _EV_COLS = 4, 62
_EV_PLAQUE_ROW = 1                     # sealed plaque band (wall row, glyphs embedded)
_EV_ROW        = 2                     # the single gauntlet row — one floor row seals
                                       # the plaques against any visual straddle (as in the Cipher Cell)
_EV_FLOOR_LO, _EV_FLOOR_HI = 1, 59
_EV_SPAWN = (2, 2)
_EV_EXIT  = (2, 59)                    # behind the final bolt; the single sealed row
                                       # means every line jump lands on the row's FIRST
                                       # non-blank (col 4) and no other row can walk in
_EV_PHRASE1, _EV_L1 = 'she sells sea shells', 'e'
_EV_PHRASE2, _EV_L2 = 'humpty dumpty', 'u'
_EV_SEG1_COL, _EV_SEG2_COL, _EV_SEG3_COL = 4, 27, 43
_EV_WARPS1 = (2, 5, 11, 16)            # every 'e' in phrase 1
_EV_WARPS2 = (1, 8)                    # every 'u' in phrase 2
_EV_WARP3_SINGLE, _EV_WARP3_TRIPLE = 5, (11, 12, 13)
_EV_BOLT_A = (2, 25)                   # opens while segment 1 reads as its plaque
_EV_BOLT_B = (2, 41)                   # … segment 2
_EV_BOLT_C = (2, 58)                   # … segment 3 — the seal before the exit
_EV_PAR = 29                           # seed-invariant; tallied in the answer below


def _ev_pick_combo(rng):
    """The two famous phrases plus the seeded digit beat. The digit words
    carry neither mend letter (scarcity: nothing reachable can donate an
    'e' or 'u', and the digit appears only warped)."""
    _load_vocab_tables()
    low = {n: [w for w in _VOCAB_PLAIN_BY_LEN.get(n, ())
               if w.isalpha() and w.islower()] for n in (3, 4)}
    f = [w for w in low[4] if _EV_L1 not in w and _EV_L2 not in w]
    g = [w for w in low[3] if _EV_L1 not in w and _EV_L2 not in w]
    return ((_EV_PHRASE1, _EV_L1), (_EV_PHRASE2, _EV_L2),
            (rng.choice(f), rng.choice(g), rng.choice('23456789')))


def build_dungeon_echo_vault(seed: int) -> Dungeon:
    """The Echo Vault: teaches . (dot — repeat the last change).

    The vault repeats what it hears: the SAME corruption has stamped itself
    down every span — the same warped rune, over and over. Mend it once with
    r; press . and the echo mends the next. ONE visible rule, the plaque
    family's third member: each span's bolt stands open while the lock row
    READS AS ITS PLAQUE — plain `Seal` gates (`scope='region'`, `mode='exact'`;
    stateless, undo-safe).

    Why . is forced: the warp glyphs are UNTYPABLE (punctuation class), so
    f/t/F/T and / can never target them; any cut (x, count-x, d{m}, D) only
    breaks the plaque match (precision rule, u recovers); and the x+P
    substitution idiom seals itself — cutting a warp overwrites the one
    unnamed register with the warp, so P pastes the rot back. r is the only
    mend, and . is its only discount (r{c}=2 keys, .=1) — the all-r route
    costs +4 over par, within budget but losing the 2-star (house style).
    A side gift of the punct class: w stops ON every warp, so the walk
    between echoes is always w/w.

    The final beat re-sizes the echo: a lone warped digit primes r{d}, and
    its tripled twin falls to 3. — the same stroke, louder. Geometry is
    fixed; the seed picks the word combo and the three warp glyphs, so par
    is locked at _EV_PAR while the answer's letters track the combo.
    """
    rng = random.Random(seed)
    (phrase1, l1), (phrase2, l2), (w4, w3, digit) = _ev_pick_combo(rng)
    g1, g2, g3 = rng.sample(_CC_WARP_GLYPHS, 3)
    phrase3 = f'{w4} {digit} {w3} {digit * 3}'

    # The shapes the par tally rests on — and TRUE mend-letter scarcity: each
    # phrase holds its letter ONLY at the warped offsets, and no mend letter
    # appears anywhere in the other segments, so nothing reachable can donate
    # it (belt and braces — the register self-seal already blocks the
    # P-then-x transplant economically).
    assert tuple(i for i, ch in enumerate(phrase1) if ch == l1) == _EV_WARPS1, phrase1
    assert tuple(i for i, ch in enumerate(phrase2) if ch == l2) == _EV_WARPS2, phrase2
    assert tuple(i for i, ch in enumerate(phrase3) if ch == digit) \
        == (_EV_WARP3_SINGLE, *_EV_WARP3_TRIPLE), phrase3
    everything = phrase1 + phrase2 + phrase3
    for cure, own in ((l1, phrase1), (l2, phrase2), (digit, phrase3)):
        assert everything.count(cure) == own.count(cure), (cure, everything)

    def warp(phrase: str, offsets, glyph: str) -> str:
        out = list(phrase)
        for i in offsets:
            out[i] = glyph
        return ''.join(out)

    R, C = _EV_ROWS, _EV_COLS
    from vimny.engine.editor import _CELL_CODE
    from vimny.sharing.format import Level as _Level, build as _fmt_build
    cells = [[CellType.WALL] * C for _ in range(R)]
    for c in range(_EV_FLOOR_LO, _EV_FLOOR_HI + 1):
        cells[_EV_ROW][c] = CellType.CORRIDOR
    for (br, bc) in (_EV_BOLT_A, _EV_BOLT_B, _EV_BOLT_C):
        cells[br][bc] = CellType.WALL              # the bolts start shut

    runs: list = []

    def lay(row, col, text, kind):
        """Place `text` at (row, col); spaces become gaps between separate runs."""
        c = col
        for piece in text.split(' '):
            if piece:
                runs.append({'row': row, 'col': c,
                             'symbols': piece, 'kind': kind})
            c += len(piece) + 1

    for col, true, lock in (
        (_EV_SEG1_COL, phrase1, warp(phrase1, _EV_WARPS1, g1)),
        (_EV_SEG2_COL, phrase2, warp(phrase2, _EV_WARPS2, g2)),
        (_EV_SEG3_COL, phrase3,
         warp(phrase3, (_EV_WARP3_SINGLE, *_EV_WARP3_TRIPLE), g3)),
    ):
        lay(_EV_PLAQUE_ROW, col, true, 'verdant')
        lay(_EV_ROW, col, lock, 'ancient')

    # The three bolts, as the format's own Seals: each stands open while the
    # lock row's text over its plaque span READS AS the plaque. The spans are
    # fixed columns on the single gauntlet row (no anchor — nothing here
    # survives a row shift anyway), and the region reader's whitespace
    # collapsing reads the one-cell gaps between a phrase's runs as the same
    # single spaces the bespoke slice used to.
    seals = [Seal(region=(_EV_ROW, c0, _EV_ROW, c0 + len(true) - 1),
                  match=(true,), mode='exact', scope='region',
                  opens=((br, bc),))
              for (c0, true), (br, bc) in zip(
                  ((_EV_SEG1_COL, phrase1), (_EV_SEG2_COL, phrase2),
                   (_EV_SEG3_COL, phrase3)),
                  (_EV_BOLT_A, _EV_BOLT_B, _EV_BOLT_C))]

    level = _Level(
        name='The Echo Vault', seed=seed,
        rows=R, cols=C,
        cells=[''.join(_CELL_CODE[c] for c in row) for row in cells],
        spawn=_EV_SPAWN, exit=_EV_EXIT,
        char_runs=runs,
        entities=[{'kind': 'exit', 'at': [_EV_EXIT[0], _EV_EXIT[1]],
                   'edit_immune': True}],   # a careless D must not delete the way
                                            # out (nor the row dd-collapsible)
        seals=seals,
        solution=(f'w w r{l1} w w . w w . w w . '
                  f'w w r{l2} w w . '
                  f'w w r{digit} w w 3. $'))

    dungeon = _fmt_build(level, par=_EV_PAR)
    room = dungeon.rooms[0]
    # `Seal.message` is not file-format data; hand the banner back.
    from dataclasses import replace as _dc_replace
    room.seals = tuple(_dc_replace(s, message='The span is mended true — the bolt grinds back!')
                       for s in room.seals)
    return dungeon


# ── The Warden Manifold (21.1, Act IV boss) — "The Stamping Press" ────────────
# Symmetric about the processional aisle (row 8): antechamber west, grand hall
# east (FOGGED until the brazier ritual draws the gate), friezes top and
# bottom, four podium niches in the quadrants. He stamps; the player
# out-copies him.
_WM_ROWS, _WM_COLS = 17, 66
_WM_AXIS = 8                            # the aisle — the hall's mirror line
# Antechamber (the opening ritual): interior rows 5..11, cols 2..12.
_WM_SPAWN    = (8, 2)
_WM_FLAME    = (8, 4)                   # the eternal flame — yl lifts it
_WM_BRAZIERS = ((3, 9), (7, 12), (9, 12), (13, 9))
                                        # a mirrored diamond. TWO reflow laws
                                        # (both found live): one brazier per
                                        # row (a later paste west of a lit
                                        # flame shoves it off its brazier),
                                        # and brazier rows must hold NO glyph
                                        # anywhere east in the BUFFER row —
                                        # open_gap shifts the whole line,
                                        # straight across the dividing wall
                                        # (rows 3/7/9/13 are glyph-free in
                                        # the hall; 5/11 carry column shafts,
                                        # 6/10 the wards)
_WM_GATE     = (8, 13)                  # ritual gate: draws when all four burn
# Grand hall: interior rows 2..14, cols 15..61.
_WM_HALL_TOP, _WM_HALL_BOT = 2, 14
_WM_HALL_LO,  _WM_HALL_HI  = 15, 61
_WM_FRIEZE_ROWS = (1, 15)               # sealed wall rows wearing his stamp-marks
# Podium niches (ward order NW → NE → SW → SE); each is a 1-cell alcove walled
# on three sides, its bolt facing the aisle. Bolts are DERIVED from the warden
# entity each tick (entities ride row shifts), never stored.
_WM_PODIUMS = ((3, 26), (3, 46), (13, 26), (13, 46))
# Ward stamps (rows mirror about the aisle; west beats then east beats):
_WM_WARD1 = (6, 18)                     # R1: d{m} — three warding words, a post per word
_WM_WARD1_POSTS = (22, 27)              # close_gap stops at walls: each word its own line
                                        # (a post CRUMBLES when its word is cut)
# The warding words SAY what they are — locks, crypts, runes, veils. Four
# letters, lowercase; the seed draws three that lack the R2 true letter
# (the Echo Vault scarcity rule survives any draw — every single letter
# leaves at least three of these standing).
_WM_WARD1_WORDS = ('lock', 'seal', 'ward', 'rune', 'bolt', 'gate', 'tomb',
                   'keep', 'bind', 'hide', 'veil', 'cage', 'cell', 'trap',
                   'hasp', 'mask')
_WM_WARD2 = (6, 38)                     # R2: r + . — his stamp, four times, one warp each
_WM_WARD2_WINDOW = 8                    # keystrokes from solve to strike before the
                                        # mends re-corrupt (the exact cost of the
                                        # clean solve: r{c} + w. + w. + w.)
_WM_WARD3 = (10, 18)                    # R3: D — rot-tail with a rank of REAL Wardens
_WM_WARD3_HI = 34
_WM_WARD3_RANK = ((10, 20), (10, 24), (10, 28), (10, 32))
_WM_WARD4 = (11, 45)                    # ward 4: yy + p p — his flame row, stamped
                                        # LIT (🜂🜂🜂). Grid (11,45..47) = the
                                        # game's ruler (10,44)..(10,46) — design
                                        # talk uses RULER coords (grid − 1 here:
                                        # display row/col = grid − first standable
                                        # row/col + 1). Two linewise pastes make
                                        # the 3×3 grid that breaks the ward.
_WM_WARD4_ECHOES = ((3, 36), (5, 24), (5, 48), (7, 36),
                    (9, 36), (11, 24), (11, 48), (13, 36))   # mirrored crowd
_WM_SEAL = (8, 62)                      # draws when the press falls silent
# Treasure pocket: rows 7..9 × cols 63..64, FOGGED until the seal draws.
# Exit center-west; column 2 holds the prizes.
_WM_EXIT  = (8, 63)
_WM_HEART = (7, 64)                     # pocket column 2, top
_WM_CHEST = (9, 64)                     # pocket column 2, bottom — a relic scroll
_WM_POCKET = tuple((r, c) for r in (7, 8, 9) for c in (63, 64))
_WM_BUDGET = 220                        # relaxed (boss convention — no par)


def build_dungeon_warden_manifold(seed: int) -> Dungeon:
    """The Warden Manifold (Act IV boss): he stamps himself into the world —
    wards of text, then copies of himself — and the player out-copies him
    with the act's own verbs. No new commands; no keystroke par.

    Opening ritual: the antechamber holds one eternal flame and four cold
    braziers (… embers). yl lifts the flame, P lays it (the Beacon Tiers'
    fuel rule is active via room._qm_chain); when all four burn, the ritual
    gate draws AND the hall's fog parts — the grand hall starts fogged
    (solid unknown from the antechamber), so no jump, walk, or search can
    enter it early.

    The fight (main._warden_manifold_tick): the Warden is edit_immune (every
    operator parries — the engine's real all-or-nothing shield) and shelters
    in a fogged podium niche behind each of his four WARDS in turn; breaking
    the ward with the act's verb jams the press — echoes gutter, his bolt
    draws, his fog parts (/W finds him at last), one x lands — and he
    re-manifests at the next podium and stamps the next ward:
      R1  d{m}   three warding words that SAY what they are (lock, tomb,
                 veil…); a wall post pins the reflow after each word and
                 CRUMBLES when its word is cut
      R2  r + .  his stamp four times, the same warp in each (the Echo
                 Vault's seals); the mends RE-CORRUPT eight keystrokes
                 after the solve — exactly the cost of the clean answer —
                 so the strike must follow at once (/W + x makes it easy)
      R3  D      a rot-tail with a rank of REAL Wardens standing on it;
                 once the rot is first cut, every keystroke DOUBLES the
                 rank while any rot remains — one D, or a flood
      R4  yy+pp  his flame row, stamped LIT (🜂🜂🜂); yank the LINE and
                 paste it twice — a 3×3 grid of flames breaks the ward
                 (charwise flames are fuel-locked to the braziers, and
                 linewise pastes stack one flame row per paste, so only
                 copying HIS row can make three flame rows)
    Then the final stagger, the killing x, the seal draws, and the treasure
    pocket's fog parts (heart + the boss scroll behind the exit).

    Ward checks are shift-proof (kind-counts on floor cells / substring
    scans across rows), bolts derive from the warden entity, and the seal
    derives from stored coords. The ward counter RIDES the undo snapshot
    (main._WM_UNDO_ATTRS — undo rewinds the fight with the world; the
    Pathfinder convention was a grind exploit here). Geometry is fixed;
    the seed picks the vocabulary.
    """
    rng = random.Random(seed)
    _load_vocab_tables()
    low4 = [w for w in _VOCAB_PLAIN_BY_LEN.get(4, ()) if w.isalpha() and w.islower()]

    # R2 first: a stampable word whose FIRST letter appears exactly once (the
    # scarce cure). Warping index 0 fixes the lock SHAPE (`⚸num ⚸num …`), so
    # the w-hop rhythm between stamps is seed-invariant — the Echo Vault's
    # fixed-offsets rule.
    word2 = letter2 = None
    for _ in range(60):
        w = rng.choice(low4)
        if w.count(w[0]) == 1:
            word2, warp_at = w, 0
            letter2 = w[0]
            break
    assert word2 is not None
    # Everything else must not donate letter2 (true scarcity, Echo Vault rule).
    words1 = rng.sample([w for w in _WM_WARD1_WORDS if letter2 not in w], 3)
    soup_abc = [ch for ch in 'abcdefghijklmnopqrstuvwxyz' if ch != letter2]
    warp_glyph = rng.choice(_CC_WARP_GLYPHS)

    def rot_text(n: int) -> str:
        out: list = []
        while len(out) < n:
            if out:
                out.append(' ')
            for _ in range(min(rng.randint(2, 4), n - len(out))):
                out.append(rng.choice(soup_abc))
        return ''.join(out[:n])

    R, C = _WM_ROWS, _WM_COLS
    cells = [[CellType.WALL] * C for _ in range(R)]
    for r in range(3, 14):                                  # antechamber
        for c in range(2, 13):
            cells[r][c] = CellType.FLOOR
    for r in range(_WM_HALL_TOP, _WM_HALL_BOT + 1):         # the grand hall
        for c in range(_WM_HALL_LO, _WM_HALL_HI + 1):
            cells[r][c] = CellType.FLOOR
    for c in _WM_WARD1_POSTS:                               # R1 reflow posts
        cells[_WM_WARD1[0]][c] = CellType.WALL
    for (pr, pc) in _WM_PODIUMS:                            # podium niches
        cells[pr][pc] = CellType.FLOOR
        side = 1 if pr < _WM_AXIS else -1                   # bolt faces the aisle
        cells[pr - side][pc] = CellType.WALL                # back wall
        cells[pr][pc - 1] = CellType.WALL
        cells[pr][pc + 1] = CellType.WALL
        cells[pr + side][pc] = CellType.WALL                # the bolt, shut
    for (r, c) in _WM_POCKET:                               # treasure pocket
        cells[r][c] = CellType.FLOOR
    cells[_WM_SEAL[0]][_WM_SEAL[1]] = CellType.WALL         # behind its seal
    cells[_WM_GATE[0]][_WM_GATE[1] + 1] = CellType.FLOOR    # threshold into the hall
    cells[_WM_GATE[0]][_WM_GATE[1]] = CellType.WALL         # ritual gate, shut

    room = Room(room_type=RoomType.ENTRY, rows=R, cols=C)
    room.cells = cells
    room.seed  = seed
    # Three fog regions, three reveals (fog is impassable, blank to render,
    # skipped by line jumps via is_passable and by search via _match_positions):
    #   hall    — everything past the gate, walls included; parts when the
    #             brazier ritual draws the gate. No H/G{n}/walk/search enters
    #             the chamber before the ritual.
    #   niches  — each podium reads as solid stone; the stagger parts the
    #             ACTIVE one (only a revealed Warden is searchable, so /W
    #             jumps the player straight onto him for the strike — x lands
    #             at one's own cell). The R2 re-corruption re-fogs him.
    #   pocket  — the treasure pocket (exit, heart, scroll chest) parts when
    #             the press falls and the seal draws.
    room.search_glyph_entities = True
    hall_fog = frozenset(
        (r, c) for r in range(1, 16) for c in range(14, 63)
        if (r, c) not in _WM_PODIUMS)
    room._wm_hall_fog   = hall_fog
    room._wm_pocket_fog = frozenset(_WM_POCKET)
    _lay_dark(room, _WM_PODIUMS)
    _lay_dark(room, hall_fog)
    _lay_dark(room, _WM_POCKET)
    # THE RITUAL GATE, said as data: four PER-BRAZIER predicates (one region
    # = one brazier cell), then a ritual seal requiring all four — it floors
    # the gate and unveils the great hall's darkness (fog and veils both).
    # The pocket reveal stays in the tick — it rides the warden's death,
    # which also gutters his copies.
    from vimny.engine.world import Seal as _Seal
    base_idx = len(room.seals)
    _preds = tuple(_Seal(
        region=(b[0], b[1], b[0], b[1]), mode='braziers', match=())
        for b in _WM_BRAZIERS)
    _ritual = _Seal(
        mode='exact', match=(), requires=tuple(range(base_idx, base_idx + 4)),
        opens=(tuple(_WM_GATE),),
        unveils=tuple(sorted(hall_fog)),
        message=('Five flames burn as one — the gate draws, and the '
                 'fog of the great hall parts!'))
    room.seals = (*room.seals, *_preds, _ritual)

    def lay(row, col, text, kind):
        c = col
        for piece in text.split(' '):
            if piece:
                room.char_runs.append(CharRun(row, c, tuple(piece), kind))
            c += len(piece) + 1

    # The eternal flame and the four cold braziers (embers tick-managed).
    room.char_runs.append(CharRun(*_WM_FLAME, (_QM_FLAME,), 'flame'))
    for (r, c) in _WM_BRAZIERS:
        room.char_runs.append(CharRun(r, c, (_QM_EMBERS,), 'pedestal'))

    # Friezes: his stamp-marks pressed into the north and south walls —
    # untypable symbols only (unsearchable, untargetable), mirrored rows,
    # centered on the hall (37 cols at 20..56; hall center = col 38).
    frieze = '♄  ▼  ☿  ▼  ♆  ▼  ⚸  ▼  ♆  ▼  ☿  ▼  ♄'
    for fr in _WM_FRIEZE_ROWS:
        lay(fr, 20, frieze, 'ember')

    # WARD 1, stamped at build (the fight opens staged): three warding
    # words, unguarded — the words themselves say "cut me". A post follows
    # each of the first two; the tick crumbles a post when its word is cut.
    c = _WM_WARD1[1]
    for w in words1:
        lay(_WM_WARD1[0], c, w, 'ancient')
        c += 5
    # Later stamps, laid by the tick on each ward transition.
    word2_lock = word2[:warp_at] + warp_glyph + word2[warp_at + 1:]
    room._wm_stamps = {
        2: (_WM_WARD2[0], _WM_WARD2[1],
            '  '.join([word2_lock] * 4), 'verdant'),
        # NOTE the rot is 'ancient', not 'ember': r-typed mends carry
        # INSERT_KIND ('ember') and the WORD-normalize repaints whole mended
        # words with it, so an ember-based rot check would false-positive on
        # the player's own R2 mends. 'ancient' is safe by TIME: ward 1's
        # words must be gone before ward 3 can exist.
        3: (_WM_WARD3[0], _WM_WARD3[1],
            rot_text(_WM_WARD3_HI - _WM_WARD3[1] + 1), 'ancient'),
        # R4: his flame row, stamped LIT. yy + p + p copies it twice — three
        # flame rows break the ward (_wm_ward_broken counts 🜂🜂🜂 rows).
        4: (_WM_WARD4[0], _WM_WARD4[1], _QM_FLAME * 3, 'flame'),
    }
    # Ward spawns: ward 3 is a rank of REAL Wardens (kind='warden', hp=1,
    # tag='stamp' — exempt from summon/leap, gutterable, NOT edit_immune so
    # one D shears rot and rank together); R4 the mirrored echo crowd.
    room._wm_spawns = {3: ('warden', 'stamp', _WM_WARD3_RANK),
                       4: ('goblin', 'echo', _WM_WARD4_ECHOES)}
    room._wm_word2, room._wm_warp = word2, warp_glyph
    room._wm_gate, room._wm_seal = _WM_GATE, _WM_SEAL
    room._wm_braziers = _WM_BRAZIERS
    # Every shut stone that is really a DOOR, registered so the renderer bands
    # it (`_seal_shown`). Without this the ritual gate and the final seal read
    # as ordinary wall — the Cipher Cell, the Echo Vault and the Shelving Room
    # all band theirs, so a player who has met those levels is entitled to
    # read plain stone as plain stone. Discovery is still gated: a band only
    # shows once some open cell beside it is un-fogged.
    room.sealed_cells = {_WM_GATE, _WM_SEAL} | {
        (pr + (1 if pr < _WM_AXIS else -1), pc) for (pr, pc) in _WM_PODIUMS}

    # The Warden: edit_immune (every operator parries), four x-windows of HP.
    # tag='manifold' exempts him from the stock warden auto-summon — pressure
    # ships QUIET here (the _wm_pressure hook decides later).
    room.entities.append(Entity(kind='warden', row=_WM_PODIUMS[0][0],
                                col=_WM_PODIUMS[0][1], hp=4, max_hp=4,
                                ai='', tag='manifold', edit_immune=True))
    room.entities.append(Entity(kind='heart_container',
                                row=_WM_HEART[0], col=_WM_HEART[1]))
    room.entities.append(Entity(kind='chest_scroll',
                                row=_WM_CHEST[0], col=_WM_CHEST[1]))
    room.entities.append(Entity(kind='exit', row=_WM_EXIT[0], col=_WM_EXIT[1],
                                edit_immune=True))
    room.spawn_pos = _WM_SPAWN
    room.exit_pos  = _WM_EXIT
    # The Beacon Tiers' fuel rule, reused: charwise flames lie only in
    # braziers — declared here, so the paste law reads them straight from
    # `room.braziers` (linewise paste is exempt; a yanked row's flames sit
    # where they sat).
    room.braziers = tuple(_WM_BRAZIERS)

    room.rebuild_indexes()
    room.par    = None                   # boss: no keystroke par (1-star win)
    room.budget = _WM_BUDGET
    room.answer = ''

    dungeon = Dungeon(name='The Warden Manifold', seed=seed)
    dungeon.rooms        = [room]
    dungeon.current_room = 0
    return dungeon


# ── The Inscription Halls (22) — the first writer ─────────────────────────────
# A wide river meanders north–south, drifting four columns west as it falls;
# lesson rows hang west of the bank like jetties. Plaque rule, fourth member
# (Cipher mended, Beacon copied, Echo repeated): here the floor text is
# INCOMPLETE — the plaque shows the whole word, the floor a fragment. Each
# word written whole grinds open ONE of five stone walls stacked before the
# exit beyond the ford (lessons in any order; ( / ) sentence-hops between
# jetties are the par route — embraced, not fought). i = the prefix lesson
# (fragment head flush against the dead-end wall: only insert-AT-cursor can
# write there); a = the suffix lesson (fragment tail on the bank, water at
# the very next cell: nowhere to stand for i — a writes past yourself, and
# INK DISPLACES THE FLOOD, each letter pushing the river back one cell,
# spilled over the east wall). The ford finale: 'river' + a + 'gate' types a
# bridge clean across — the word IS the crossing.
_IH_ROWS, _IH_COLS = 15, 52
# The river MEANDERS: 4 wide everywhere, drifting four columns west from the
# headwater to the ford (rows 1..13; index = row, [0]/[14] unused borders).
_IH_RIVER_W = 4
_IH_RIVER_LO_BY_ROW = (0, 42, 42, 41, 41, 41, 40, 40, 40, 39, 39, 39, 38, 38, 0)


def _ih_river_lo(r: int) -> int:
    return _IH_RIVER_LO_BY_ROW[r]


def _ih_bank(r: int) -> int:
    """The west bank of row r — the last standable column before the water."""
    return _ih_river_lo(r) - 1


_IH_LESSON_ROWS = (2, 5, 8, 11)         # i, a, i, a (jetties off the bank)
_IH_PLAQUE_ROWS = (1, 4, 7, 10)         # sealed band above each lesson
# Promenade connectors: (row, col) gaps through the separator/plaque rows —
# each pair shares a column passable on both neighbouring rows (the bank
# drifts, so the column steps west going downstream).
_IH_GAPS = ((3, 40), (4, 40), (6, 39), (7, 39), (9, 38), (10, 38), (12, 37))
_IH_I_HEAD = 28                         # i-rows: fragment head = the row's FIRST floor
                                        # cell (wall at 27 — nowhere to stand for `a`)
_IH_A_WEST = 29                         # a-rows: floor from here to the bank
_IH_SPLITS = (2, 1, 1, 2)               # missing-letter counts (FIXED — par invariance)
_IH_FORD_ROW = 13                       # 'river' at 33..37, tail on the bank
_IH_FORD_FRAG, _IH_FORD_WORD = 'river', 'rivergate'
# Five stone walls stacked before the exit, east of the ford: each written
# word grinds ONE open. Lesson words own the walls WEST→EAST in walking
# order — descending the jetties unbars the corridor out ahead of you; the
# bridge-word completes the road at the EASTMOST (46).
_IH_SEALS = ((13, 42), (13, 43), (13, 44), (13, 45), (13, 46))
_IH_EXIT  = (13, 47)                    # beyond all five walls
_IH_PAR   = 24                          # the ( / ) / e sentence-hop route (below);
                                        # insert costs 1 + chars (Esc spends nothing)

# Deterministic fallback if the greedy draw can't fill all four slots
# (shapes match _IH_SPLITS: head-2, tail-1, head-1, tail-2; verified against
# every scarcity rule below).
_IH_FALLBACK = (('only', 'on', 'ly'), ('wraith', 'h', 'wrait'),
                ('flame', 'f', 'lame'), ('bliss', 'ss', 'bli'))


def _ih_pick(rng):
    """Four lesson words + splits: [0]/[2] miss their HEAD (i), [1]/[3] their
    TAIL (a). Scarcity rules (the Echo Vault discipline — typing must be the
    only source of the missing letters, or x+p impersonates i/a):
      - the four missing-letter sets are pairwise disjoint;
      - no missing letter appears in ANY floor fragment, nor in 'river'
        (cuttable from the start; plaques sit in walls and cannot be cut);
      - no word is a substring of another or of 'rivergate'
        (bolt checks are whole-row substring scans on floor text).
    Greedy over a shuffled pool (a blind 4-word draw almost never satisfies
    the letter constraints; the greedy fill succeeds essentially always).
    Returns [(word, missing, fragment) × 4]."""
    _load_vocab_tables()
    pool = sorted({w for n in (4, 5, 6) for w in _VOCAB_PLAIN_BY_LEN.get(n, ())
                   if w.isalpha() and w.islower()})
    rng.shuffle(pool)
    lessons = []
    for idx in range(4):
        k = _IH_SPLITS[idx]
        for w in pool:
            if w in _IH_FORD_WORD \
                    or any(w == lw or w in lw or lw in w
                           for (lw, _m, _f) in lessons):
                continue
            if idx in (0, 2):
                missing, frag = w[:k], w[k:]
            else:
                missing, frag = w[-k:], w[:-k]
            ms = set(missing)
            frag_letters = (set(_IH_FORD_FRAG) | set(frag)
                            | {ch for (_w, _m, f) in lessons for ch in f})
            if ms & frag_letters \
                    or any(ms & set(m) for (_w, m, _f) in lessons) \
                    or any(set(m) & set(frag) for (_w, m, _f) in lessons):
                continue
            lessons.append((w, missing, frag))
            break
        else:
            return [tuple(t) for t in _IH_FALLBACK]
    return lessons


def build_dungeon_inscription_halls(seed: int) -> Dungeon:
    """The Inscription Halls (the first writer: i and a).

    Layout: the RIVER (4 wide, water — impassable, movable) meanders down
    rows 1..13, its west edge drifting 42 → 38 (four columns west; pushed
    cells spill over the east wall and are lost). i-rows dead-end west at
    col 27 with the fragment head ON col 28 — stand on the head, i writes
    under you, a physically cannot (col 27 is wall). a-rows put the fragment
    tail ON the row's bank with water at the very next cell — stand on the
    tail, a writes past you onto the flood (ink displaces it), i physically
    cannot. The ford (row 13): 'river' + a + 'gate' → 'rivergate' bridges
    the water. FIVE stone walls stack east of the ford before the exit; each
    word written whole grinds one open — plain `Seal` gates (`mode='contains'`
    over floor text, the label-gate chassis), lesson words west→east in
    walking order and the bridge-word eastmost, with the final seal holding
    the exit stone until all five read true.

    The par route hops jetties with ( / ) / e (sentence jumps, embraced —
    they only optimize travel; every word must still be written). Scarcity
    (see _ih_pick) keeps x+p from impersonating the verbs; the 'insert'
    token gates everything (curriculum: teaches ['insert'])."""
    rng = random.Random(seed)
    lessons = _ih_pick(rng)

    R, C = _IH_ROWS, _IH_COLS
    from vimny.engine.editor import _CELL_CODE
    from vimny.sharing.format import Level as _Level, build as _fmt_build
    cells = [[CellType.WALL] * C for _ in range(R)]
    for r in range(1, 14):                                   # the meandering river
        for c in range(_ih_river_lo(r), _ih_river_lo(r) + _IH_RIVER_W):
            cells[r][c] = CellType.WATER
    for i, r in enumerate(_IH_LESSON_ROWS):                  # jetty rows
        lo = _IH_I_HEAD if i in (0, 2) else _IH_A_WEST
        for c in range(lo, _ih_bank(r) + 1):
            cells[r][c] = CellType.FLOOR
    for (r, c) in _IH_GAPS:                                  # promenade connectors
        cells[r][c] = CellType.FLOOR
    for c in range(_IH_A_WEST, _ih_bank(_IH_FORD_ROW) + 1):  # the ford row
        cells[_IH_FORD_ROW][c] = CellType.FLOOR
    cells[_IH_EXIT[0]][_IH_EXIT[1]] = CellType.FLOOR         # beyond the five walls
    # the five exit walls stay WALL at build (the tick opens one per word)

    runs: list = []

    def lay(row, col, text, kind):
        runs.append({'row': row, 'col': col, 'symbols': text, 'kind': kind})

    # Plaques (the familiar sealed band, verdant in the wall) + fragments,
    # and the five exit walls: each lesson word owns its wall in walking
    # order (westmost first); the bridge-word completes the road.
    walls = list(_IH_SEALS)
    doors = []
    for i, (word, missing, frag) in enumerate(lessons):
        lrow, prow = _IH_LESSON_ROWS[i], _IH_PLAQUE_ROWS[i]
        if i in (0, 2):                                      # i: head missing
            lay(prow, _IH_I_HEAD, word, 'verdant')
            lay(lrow, _IH_I_HEAD, frag, 'ancient')
        else:                                                # a: tail missing
            span_lo = _ih_river_lo(lrow) - len(frag)
            lay(prow, span_lo, word, 'verdant')
            lay(lrow, span_lo, frag, 'ancient')
        doors.append((word, walls[i][1]))
    lay(_IH_FORD_ROW, _ih_river_lo(_IH_FORD_ROW) - len(_IH_FORD_FRAG),
        _IH_FORD_FRAG, 'ancient')                            # 'river' at 33..37
    lay(R - 1, _ih_river_lo(_IH_FORD_ROW) - len(_IH_FORD_FRAG),
        _IH_FORD_WORD, 'verdant')                            # ford plaque, south border
    doors.append((_IH_FORD_WORD, walls[4][1]))

    m = [m_ for (_w, m_, _f) in lessons]
    level = _Level(
        name='The Inscription Halls', seed=seed,
        rows=R, cols=C,
        cells=[''.join(_CELL_CODE[c] for c in row) for row in cells],
        spawn=(_IH_LESSON_ROWS[0], _ih_bank(_IH_LESSON_ROWS[0])),
        exit=_IH_EXIT,
        char_runs=runs,
        entities=[{'kind': 'exit', 'at': [_IH_EXIT[0], _IH_EXIT[1]],
                   'edit_immune': True}],
        seals=list(gate_row_seals(
            doors, _IH_EXIT, mode='contains',
            bolt_message='The word stands whole — beyond the river, a wall grinds open!',
            final_message='Every word reads true — the way out of the Halls stands open!')),
        # Canonical answer — the sentence-hop route (drives the par; insert
        # tokens 'i…'/'a…' cost 1 + len(text), Esc spends nothing; ( ) e $ cost
        # 1 each — see tests/test_answer_paths). Gate ticks fire ON the insert
        # Esc, so the seals stand open before the first NORMAL key — a single $
        # sails the whole corridor onto the exit (no second $ is needed):
        #   A: ( i{2}        = 1+3
        #   B: ) e a{1}      = 1+1+2
        #   C: ) i{1}        = 1+2
        #   D: ) e a{2}      = 1+1+3
        #   ford: ) e agate $ = 1+1+5+1   → total 24
        solution=(f'( i{m[0]}<Esc> '
                  f') e a{m[1]}<Esc> '
                  f') i{m[2]}<Esc> '
                  f') e a{m[3]}<Esc> '
                  f') e agate<Esc> $'))

    dungeon = _fmt_build(level, par=_IH_PAR)
    # `Seal.message` is not file-format data; hand the banners back.
    _seal_banners(dungeon,
                  bolt='The word stands whole — beyond the river, a wall grinds open!',
                  final='Every word reads true — the way out of the Halls stands open!')
    return dungeon


# ── The Change Annex (23) — change is delete + insert in one breath ───────────
# A hall of MISLABELLED doors. Every door's plaque (set in the wall to the WEST)
# shows the word it wants; the label on the floor to the EAST shows the wrong
# one. The plaque rule, fifth member (Cipher mended, Beacon copied, Echo
# repeated, the Halls authored) — here the annex RELABELS, and the verb is
# `change`:
#   word doors — the label is ONE word off inside a phrase that is otherwise
#                right; `ce` changes just that word. `cc` would force retyping
#                the whole kept phrase, so the motion form is forced.
#   line doors — the WHOLE line is one wrong word; `cc` rewrites it in one verb.
#                The cursor lands MID-row here (off the previous east-ending
#                edit), so cc (column-agnostic) honestly saves the `0`/`^` the
#                old `D`/`d$` rival must spend to clear from the line start
#                (its one-key rival `S` is withheld until §24).
#   rune doors — one fused rune (◆) stands for two letters; `s` cuts it and
#                spells them out, where `cw`/`r` overpay (r is one-for-one).
# Forcing is by VOLUME (the blueprint's resolved engine reality: c is
# delete-then-insert WITH reflow, identical to d-then-i, so terrain forcing is
# dead — every change merely saves ONE key over its d/x+i rival). The eight
# plaque-door bolts stand in a ROW across the gate corridor (the Inscription
# pattern), and the budget margin is pinned BELOW the door count so the all-old
# route overshoots.
#
# Three layout laws (all Vim-faithful — no state-toggled
# walls beyond the plaque-rule doors the whole family already uses):
#  - PLAQUE IN THE WEST WALL. Reflow is segment-bounded in BOTH directions: a
#    mid-row wall (or void rune) is a hard line boundary, so content on the far
#    side of a wall is never disturbed by an edit on the other side (push via
#    open_gap and pull via close_gap are symmetric — see vimny/engine/reflow.py). The
#    plaque could therefore live EAST of the label behind a bolt and stay safe;
#    it sits in the WEST wall here for the OTHER two reasons — WALL cells are
#    uncuttable (no `cc`/`D` can wipe the answer key) and excluded from the floor
#    scans that read each label. (Earlier, before the push was segment-bounded,
#    an east plaque on wall cells got erased on the first keystroke; that hazard
#    is gone, but west-wall placement remains the simplest safe home.)
#  - LINE DOORS ARE A SINGLE WORD, and `room.answer` is the real keystroke
#    string (see _wla_route / _wla_answer below). The karaoke sheet strips plain
#    spaces from room.answer as display separators, so a typed space must be
#    written `<Space>` (and a typed Enter `<CR>`). One word per door is this level's
#    choice, not a global limit — multi-word typed text is representable.
#  - THE EXIT IS PLAIN FLOOR, NOT A GATED WALL. The bolts stand in a row WEST of
#    the exit on the gate row; the spine cell west of them is the row's first
#    standable cell. So every vertical jump (G / L / {n}G / H / M) lands on the
#    reachable spine, never the isolated exit, and `$`/`0`/`|` are segment-
#    bounded (they stop at the first shut bolt — engine `_cross_water`). No jump
#    can reach the exit until the bolts honestly open. (Keeping the exit cell a
#    WALL until solved would be a non-Vim hack; the geometry does the work.)
_WLA_ROWS, _WLA_COLS = 15, 47        # widened for the saying prefixes in the west stone (≤ 25
                                     # chars — 'a stitch in time saves' is 22)
_WLA_PLQ_COL  = 1                    # (retired name) the west stone band, cols 1..25
_WLA_COL_S    = 27                   # the spine — the gate's first standable; on lesson rows it
                                     # carries the label. The west wall (cols 1..26) holds each
                                     # saying's carved PREFIX, ending two cols shy of the spine
_WLA_LBL_COL  = _WLA_COL_S           # labels start AT the spine (= where cc drops the cursor)
_WLA_LBL_END  = 45                   # label floor reaches this column (fits the longest label)
_WLA_LESSON_ROWS = tuple(range(2, 12))               # ten lesson rows, descended by j
_WLA_THROAT_ROW  = 12                                # spine-ONLY row: the block joins the gate
                                                     # only at the spine (so no east column of
                                                     # the block drops past the bolts to the exit)
_WLA_GATE_ROW    = 13                                # the gate corridor: spine · bolts · exit
_WLA_GATE_COL0   = 22                                # first bolt column (one per lesson)
_WLA_N_WORD, _WLA_N_LINE, _WLA_N_SENT = 6, 2, 2
_WLA_TRIGGERS = _WLA_N_WORD + _WLA_N_LINE + _WLA_N_SENT     # 10 doors
_WLA_EXIT = (_WLA_GATE_ROW, _WLA_GATE_COL0 + _WLA_TRIGGERS)  # plain floor, east of the bolts
_WLA_PLACEHOLDER = '◆'               # the fused rune — `s` spells it out
_WLA_PAR = 101                       # measured (drive); pinned by the playthrough test
                                     # (finale is G$ = 2 keys, not 02j$ = 4)

# SENSE, NOT DECREE (the change levels):
# every door is a saying the player knows, corrupted the way its verb mends.
# (kind, stone prefix, floor label, door target, typed) — FIXED texts, their
# letter-geometry is the puzzle:
#   word    — the saying's prefix is CARVED IN THE WEST STONE up to the spine;
#             the floor holds the wrong word + the saying's tail. `^ce` mends
#             the word and keeps the tail; the cure is known by heart. Short
#             typed cures (3/5/7) keep `{n}s` a single-digit TIE (allowed).
#   wordmix — a famous HYPHENATED expression with its pieces SCRAMBLED
#             ('round-go-merry'): instantly recognizable, retyped whole by
#             heart. `ce` stops at the hyphen (wrong); `{n}s` overpays the
#             2-digit count — only `cE` is correct AND par-optimal. And the
#             scramble is hamming-far from the cure (asserted), so no r-chain
#             undercuts the retype.
#   line    — the floor is one wrong word, the saying's carved prefix names
#             the famous last word ('time is │ water' → cc + money). The
#             wrong word is dissimilar (the cc-forcing law).
#   sent    — the saying's key word stands head-fused ('saves ◆ne'):
#             s cuts the rune and spells the two letters everyone knows.
_WLA_DOORS = (
    ('word', 'a watched', 'jug never boils', 'pot never boils', 'pot'),
    ('word', 'many hands make', 'heavy work', 'light work', 'light'),
    ('word', 'the early bird', 'grabs the worm', 'catches the worm', 'catches'),
    # the kept tail word is load-bearing: without it, ce + retype leaves the
    # target as a SUBSTRING ('well-to-do-do-well') and false-opens the bolt
    ('wordmix', '', 'to-do-well folk', 'well-to-do folk', 'well-to-do'),
    ('wordmix', '', 'ending-never road', 'never-ending road', 'never-ending'),
    ('wordmix', '', 'round-go-merry ride', 'merry-go-round ride', 'merry-go-round'),
    ('line', 'time is', 'water', 'money', 'money'),
    ('line', 'knowledge is', 'sword', 'power', 'power'),
    ('sent', 'a stitch in time saves', '◆ne', 'nine', 'ni'),
    ('sent', 'practice makes', '◆rfect', 'perfect', 'pe'),
)


def _whole_line_dissimilar(wrong: str, right: str) -> bool:
    """A change door's wrong/right words must lie far enough apart that NO cheaper
    old-tool rewrite can undercut the one-key margin that forces the taught change
    (cc/ce in the Change Annex, S in the Change Extension): they must differ in the FIRST and the LAST character
    and in at least four positions. Because both ENDS differ, the changed span
    covers the whole word — so a contiguous `{n}s` costs exactly what `cc`/`ce`
    does (and on a 2-digit-length word, one MORE), and a scatter of `r`s (Hamming
    >= 4) can't beat it either. Guards the L23 word doors AND both levels'
    whole-line doors. Without it, ~1-15% of seeds let a player clear the hall with
    count-`s`/`r` and never press the taught key (replay-confirmed; see the
    no-cheap-edit tests). Length is presumed equal (fixed-length per door)."""
    return (wrong[0] != right[0] and wrong[-1] != right[-1]
            and sum(a != b for a, b in zip(wrong, right)) >= 4)

    return wrong, right


def _wla_pick(rng):
    """The ten fixed sense-doors as lesson dicts (the rng is unused — fixed
    famous texts ARE the puzzle; kept for the builder-signature convention).
    No `typed` holds a SPACE (the karaoke law); hyphens are fine."""
    return [{'kind': kind, 'prefix': prefix, 'label': label,
             'target': target, 'typed': typed, 'len': len(typed)}
            for kind, prefix, label, target, typed in _WLA_DOORS]


# Verb keys per door kind. ce changes to the (word-class) word's end; cE through a
# punctuation mark to the WHOLE WORD's end; cc the whole line; s a single rune. Each
# is followed by typed text and an Esc (free — a sequence key the karaoke tape
# skips). `^` positions onto the label start; line doors (cc) need no column.
_WLA_VERB = {'word': 'ce', 'wordmix': 'cE', 'line': 'cc', 'sent': 's'}


def _wla_route(lessons):
    """The canonical change route as a list of (printable_keys, typed) steps,
    shared by the answer string and the playthrough test so they never drift.
    Each step's keys are pressed, then `typed` is entered in INSERT and sealed
    with Esc (callers add the Esc; it is not a printable answer key)."""
    steps = []
    for i, L in enumerate(lessons):
        prefix = '' if i == 0 else ('j' if L['kind'] == 'line' else 'j^')
        steps.append((prefix + _WLA_VERB[L['kind']], L['typed']))
    steps.append(('G$', ''))           # G to the gate row (last line), $ east to the exit
    return steps


def _wla_answer(lessons):
    """room.answer: the real keystroke tape. A step that TYPES text is sealed with
    Esc, written <Esc> (vimny/engine/tape.py): a player reading the sheet could infer it,
    but a replayer cannot — an omitted Esc makes the following keys land in the
    buffer as text. Esc spends no budget, so the tape's cost is unchanged.
    Spaces separate tokens for the karaoke display and are stripped when matched;
    no `typed` value contains a space, so the tape is unambiguous."""
    return ' '.join(keys + typed + (_TAPE_ESC if typed else '')
                    for keys, typed in _wla_route(lessons) if keys or typed)


def build_dungeon_whole_line_annex(seed: int) -> Dungeon:
    """The Change Annex (c{m}, cE, cc, s).

    An OPEN block of ten lesson rows. Each carries its WRONG label on the floor
    (east of the spine) with the RIGHT plaque set in the WEST wall (uncuttable,
    reflow-immune, excluded from the floor scans). SIX word doors come first and
    LENGTHEN by two each row (4..14): the short ones (4/6/8) are plain — `ce` and a
    `{n}s` substitute cost the same, so the novice may use either — while the long
    three (10/12/14) are MIXED (an internal punctuation mark), where `ce` stops at
    the mark and `{n}s` overpays the 2-digit count, so only `cE` is correct AND
    par-optimal. Then two line doors (`cc`) and two rune doors (`s`). Below the
    block runs the gate corridor: the spine, a ROW of ten plaque-door bolts, then
    the exit — plain floor, east of them all. Each bolt opens while its label reads
    true; until every bolt opens, walking east is barred and no jump reaches the
    exit (the spine is each row's first standable cell, `$`/`|` stop at the first
    shut bolt). Forcing is by PAR: a count-`s` solve still WINS but misses two
    stars on the 2-digit doors. See header."""
    rng = random.Random(seed)
    lessons = _wla_pick(rng)

    R, C = _WLA_ROWS, _WLA_COLS
    from vimny.engine.editor import _CELL_CODE
    from vimny.sharing.format import Level as _Level, build as _fmt_build
    cells = [[CellType.WALL] * C for _ in range(R)]
    for r in _WLA_LESSON_ROWS:                       # the open lesson block (label floor)
        for c in range(_WLA_COL_S, _WLA_LBL_END + 1):
            cells[r][c] = CellType.FLOOR
    cells[_WLA_THROAT_ROW][_WLA_COL_S] = CellType.FLOOR  # spine-only throat: block → gate
    # The spine's own gate-row cell is NOT carved: the bolt row spans it (the
    # sixth bolt stands at the spine column), so the way down onto the gate row
    # is a door like every other and opens when its label reads true. It was
    # carved FLOOR here until 2026-07-27, which the tick re-walled on the first
    # turn anyway — a one-frame lie, and one the level file could not tell.
    # the exit cell STAYS WALL — the FINAL SEAL; the tick floors it when every
    # plaque reads true (A/o can carve/fabricate floor, so geometry alone no
    # longer bars the way east of the bolts — see the `_label_gate` seals).
    # The bolt cells (the gate row, between the spine and the exit) stay WALL at
    # build; the tick opens each when its label reads true. The exit needs no
    # gating: the throat row joins the block to the gate ONLY at the spine, so no
    # east column of the block drops onto the exit; the exit is never a row's
    # first standable cell (jumps land on the spine) and `$` stops at the first
    # shut bolt (engine `_cross_water`). It opens honestly, bolt by bolt.

    runs: list = []
    doors = []
    for i, lesson in enumerate(lessons):
        lrow = _WLA_LESSON_ROWS[i]
        lesson['row'] = lrow
        # Lay the label word by word as SEPARATE runs with bare-floor gaps,
        # not one run with a space GLYPH: a space glyph reads as punctuation,
        # so `E` would run straight THROUGH it and `cE` would eat the context.
        # A real empty floor cell is whitespace, so `E` stops at the word's
        # end (the L24 C-door fix). `e` still halts at inner punctuation.
        col = _WLA_LBL_COL
        for w in lesson['label'].split(' '):
            runs.append({'row': lrow, 'col': col, 'symbols': w, 'kind': 'ancient'})
            col += len(w) + 1
        # The saying's PREFIX, carved in the west stone right-aligned to end
        # two cols shy of the spine — the sense that replaces the old decree
        # plaque (in WALL: uncuttable, off the floor scans; the wordmix
        # scrambles carry no prefix, they name themselves).
        if lesson['prefix']:
            pcol = _WLA_COL_S - 1 - len(lesson['prefix'])
            for w in lesson['prefix'].split(' '):
                runs.append({'row': lrow, 'col': pcol,
                             'symbols': w, 'kind': 'verdant'})
                pcol += len(w) + 1
        doors.append((lesson['target'], (_WLA_GATE_ROW, _WLA_GATE_COL0 + i)))

    level = _Level(
        name='The Change Annex', seed=seed,
        rows=R, cols=C,
        cells=[''.join(_CELL_CODE[c] for c in row) for row in cells],
        spawn=(_WLA_LESSON_ROWS[0], _WLA_LBL_COL),   # on lesson 1's wrong word
        exit=_WLA_EXIT,
        char_runs=runs,
        seals=list(_label_gate(doors, _WLA_EXIT)),
        entities=[{'kind': 'exit', 'at': [_WLA_EXIT[0], _WLA_EXIT[1]],
                   'edit_immune': True}],
        solution=_wla_answer(lessons))     # the real keystroke tape (karaoke)

    dungeon = _fmt_build(level, par=_WLA_PAR)
    dungeon.rooms[0]._wla_lessons = tuple(lessons)
    return dungeon


# ── The Change Extension (S, C) ───────────────────────────────────────────────
# The one-key shorthands, on the Change Annex chassis (the sixth plaque-door
# hall). The player owns the `c` operator (the Change Annex); now `S` (= `cc`, change the
# whole line) and `C` (= `c$`, change to the line's end) each do in ONE keypress
# what costs two. `S`/`C` are gated on their own tokens (engine: `S` is a
# `substitute line=True`; `C` is an operator with `shorthand='C'`), exactly the
# Operator's Vault → Cipher Cell `d$` → `D` lineage.
#
# Forcing is layered. VOLUME (S2), the Annex's model, bars the all-old route:
# each shorthand saves exactly one key per use, so the margin must sit BELOW the
# use count. The six shorthand doors (3 S + 3 C) each cost +1 on the old two-key
# path (`cc`/`c$`), so the all-old route is par + 6; a budget of par + 6 − 1 makes
# it overshoot by one while the canonical S/C route clears at par. GEOMETRY forces
# the six granular doors (one `ce` word, two `cE` WORD, two `s` rune, one `c%`
# bracket): each opens its bolt ONLY when the floor reads its exact target, and a
# wrong verb (e.g. `ce` on a `cE` door — it stops at the symbol) leaves the floor
# mislabelled and the bolt shut. They cost the same on either route; they drill
# WHICH tool, the Overwrite Halls' r-vs-R discipline. The geometry, the WEST-wall
# plaques, the spine/throat/gate, and the plain-floor exit are all the Annex's
# (see build_dungeon_whole_line_annex):
#  - The C-door's TAIL is two wrong words so `ce` (change to word end) stops one
#    word short — only `C`/`c$` rewrite the whole tail; the correct replacement is
#    a SINGLE word, so the typed text never holds a space (the karaoke rule).
#  - Reflow is segment-bounded both ways, so the plaque could sit
#    east behind a bolt; it stays in the WEST wall here only to be uncuttable and
#    off the floor scans.
_CE_ROWS, _CE_COLS = 18, 50
_CE_PLQ_COL  = 1                     # (retired name) the west stone band, cols 1..25
_CE_COL_S    = 27                    # the spine — the gate's first standable; on lesson rows it
                                     # carries the label; the west wall (cols 1..26) holds each
                                     # saying's carved PREFIX, ending two cols shy of the spine
_CE_LBL_COL  = _CE_COL_S             # labels start AT the spine (= where cc/S drops the cursor)
_CE_LBL_END  = 47                    # label floor reaches this column (fits the longest label)
_CE_LESSON_ROWS = tuple(range(2, 14))                # twelve doors, an open block (rows 2..13)
_CE_Y_ROW       = 14                                 # the Y hall: a wide floor row for the two-ending saying
_CE_Y_COL0      = 22                                 # the Y hall's floor starts west of the spine (long line)
_CE_THROAT_ROW  = 15                                 # spine-ONLY row: block → gate
_CE_GATE_ROW    = 16                                 # the gate corridor: spine · bolts · exit
_CE_GATE_COL0   = 28                                 # first bolt column (one per door)
# Door kinds in FIXED order (par invariance). The hall now DRILLS WHICH change tool
# fits, not just the shorthands: S (whole line) and C (to line end) the two new
# one-key shorthands, against the granular c-tools they DON'T replace —
#   ce      change a word, keep the trailing context;
#   cE      change a symbol-spanning WORD (`ce` stops at the symbol, only `cE` /
#           the whole-WORD motion rewrites it);
#   s       fix a single fused rune;
#   c%      change a bracketed span to its matching bracket (`ce` stops inside the
#           brackets, `cE` eats the kept suffix, S/C clobber the context).
# Three S, three C, one ce, two cE, two s, and the finale c%. EVERY C door follows
# an S door so the cursor lands EXACTLY on the wrong tail's first cell (an S word is
# 6 long; the C prefix+gap is 5, so the S word's last char sits on the tail start) —
# `jC` then rewrites the tail with no `^w` to spend. The granular doors all `j^` to
# the label start, so they nest anywhere a C does not.
_CE_KIND_ORDER = ('sline', 'ceol', 'word', 'sline', 'ceol', 'wordW',
                  'rune', 'sline', 'ceol', 'wordW', 'rune', 'bracket')
_CE_TRIGGERS = len(_CE_KIND_ORDER)                   # 12 label doors
# The Y finale (the two-ending saying) rings TWO bolts — both halves must read.
_CE_BOLTS = _CE_TRIGGERS + 2                         # 12 label bolts + the 2 Y bolts
_CE_N_S = _CE_KIND_ORDER.count('sline')              # 3
_CE_N_C = _CE_KIND_ORDER.count('ceol')               # 3
_CE_SAVING = _CE_N_S + _CE_N_C                        # 6 doors that the shorthands shorten
_CE_Y_SAVING = 8                                      # Y p + word-mends (18) vs o-retype (26)
_CE_EXIT = (_CE_GATE_ROW, _CE_GATE_COL0 + _CE_BOLTS)   # plain floor, east of the bolts
_CE_PLACEHOLDER = '◆'                # the fused rune — `s` spells it out
_CE_SYMBOL      = '★'                # the WORD-spanning symbol — `cE` crosses it, `ce` stops
# par is COMPUTED from the canonical route once below (seed-invariant — the
# texts are FIXED); pinned by tests.

# SENSE, NOT DECREE (the change levels):
# every door is a saying the player knows, corrupted the way its verb mends.
# (kind, stone prefix, floor label, door target, typed) — the ALIGNMENT LAW
# holds by construction: every S cure is EXACTLY 6 letters and every C
# door's kept floor word EXACTLY 4, so the post-S cursor (label col + 5)
# lands on the C door's wrong tail with a bare `j`.
#   sline  — the saying's carved prefix names the famous last word; the
#            floor is one dissimilar wrong word ('honesty is the best │
#            butter'). S retypes it whole.
#   ceol   — the kept floor word + a TWO-word junk tail; C rewrites the
#            tail to the famous word ('no news is │ good slop murk' → C
#            news). `ce` stops one word short.
#   word   — one word off, tail kept ('a rolling │ rock gathers no moss').
#   wordW  — the saying's key word wears a ★ scar ('ir★n is hot'): `ce`
#            stops at the symbol; only `cE` retypes the WORD by heart.
#   rune   — the key word stands head-fused ('◆ep' → de → deep).
#   bracket— a wrong bracketed head on the famous stem ('(al)gether'):
#            c% swaps exactly the bracket span for the true head.
_CE_DOORS = (
    ('sline', 'honesty is the best', 'butter', 'policy', 'policy'),
    ('ceol', 'no news is', 'good slop murk', 'good news', 'news'),
    ('word', 'a rolling', 'rock gathers no moss', 'stone gathers no moss', 'stone'),
    ('sline', 'silence is', 'sacred', 'golden', 'golden'),
    ('ceol', 'time', 'will gnaw sump', 'will tell', 'tell'),
    # The ★-scarred word is a DIFFERENT real word from the cure (an★il, not
    # ir★n): a lone `r` mends a scar but can never turn anvil into iron, so
    # only cE retypes the WORD by heart (this closes the point-change cheese).
    ('wordW', 'strike while the', f'an{_CE_SYMBOL}il is hot', 'iron is hot', 'iron'),
    ('rune', 'still waters run', f'{_CE_PLACEHOLDER}ep', 'deep', 'de'),
    ('sline', 'squeaky wheel gets the', 'polish', 'grease', 'grease'),
    ('ceol', 'actions speak louder', 'than drab fume', 'than words', 'words'),
    ('wordW', 'too many', f'cr{_CE_SYMBOL}wn spoil the broth',
     'cooks spoil the broth', 'cooks'),
    ('rune', 'mightier than the', f'{_CE_PLACEHOLDER}ord', 'sword', 'sw'),
    ('bracket', 'birds of a feather flock', '(al)gether', 'together', 'to'),
)

# The Y finale — the only famous saying whose SECOND half repeats the first's
# stump with just the last words changed: fool me once, shame on you / fool me
# twice, shame on me. The floor carries the FIRST half alone, one word wrong;
# the second half is nowhere written — the saying itself is the key. Retyping
# it letter-by-letter (o) costs 26; Y lifts the mended line whole, p lays it
# below, and two word-mends turn the echo into the answer (18). Two bolts: one
# per half.
_CE_Y_LAID = 'fool me once spite on you'
_CE_Y_T1   = 'fool me once shame on you'
_CE_Y_T2   = 'fool me twice shame on me'
_CE_Y_STEM = 'fool me twice'             # the echo plaque (the second verse's stem)


def _ce_pick(rng):
    """The twelve fixed sense-doors as lesson dicts (rng unused — fixed famous
    texts ARE the puzzle). No `typed` holds a SPACE (the karaoke law)."""
    return [{'kind': kind, 'prefix': prefix, 'label': label,
             'target': target, 'typed': typed}
            for kind, prefix, label, target, typed in _CE_DOORS]


# Verb keys per door kind. S changes the whole line; C the line's tail; ce a word;
# cE a symbol-spanning WORD; s a single fused rune; c% a bracketed span. Each is
# followed by typed text and a free Esc (a sequence key, omitted from the answer).
_CE_VERB = {'sline': 'S', 'ceol': 'C', 'word': 'ce', 'wordW': 'cE',
            'rune': 's', 'bracket': 'c%'}
# Positioning prefix per kind (i > 0). S ignores the column. A C door always
# follows an S door, so the cursor already sits on the wrong tail's first cell —
# `j` alone suffices (no `^w`). The granular doors (ce/cE/s/c%) want the label
# start (`^`). The first door is an S door, so its prefix is empty.
_CE_PREFIX = {'sline': 'j', 'ceol': 'j', 'word': 'j^', 'wordW': 'j^',
              'rune': 'j^', 'bracket': 'j^'}


def _ce_route(lessons):
    """The canonical S/C route as a list of (printable_keys, typed) steps, shared
    by the answer string and the playthrough test so they never drift. Each step's
    keys are pressed, then `typed` is entered in INSERT and sealed with Esc (the
    caller adds the Esc; it is not a printable answer key)."""
    steps = []
    for i, L in enumerate(lessons):
        prefix = '' if i == 0 else _CE_PREFIX[L['kind']]
        steps.append((prefix + _CE_VERB[L['kind']], L['typed']))
    # The Y finale: mend the first half's wrong word, lift the line, lay its
    # echo, and re-point the echo's two turning words.
    steps.append(('j^wwwce', 'shame'))     # spite → shame: the first half reads true
    steps.append(('Yp', ''))               # the line, lifted and laid again below
    steps.append(('wwce', 'twice'))        # once → twice
    steps.append(('wwwce', 'me'))          # you → me
    steps.append(('G$', ''))               # G to the gate row (last line), $ east to the exit
    return steps


def _ce_answer(lessons):
    """room.answer: the real keystroke tape. A step that TYPES text is sealed with
    Esc, written <Esc> (vimny/engine/tape.py): a player reading the sheet could infer it,
    but a replayer cannot — an omitted Esc makes the following keys land in the
    buffer as text. Esc spends no budget, so the tape's cost is unchanged.
    Spaces separate tokens for the karaoke display and are stripped when matched;
    no `typed` value contains a space, so the tape is unambiguous."""
    return ' '.join(keys + typed + (_TAPE_ESC if typed else '')
                    for keys, typed in _ce_route(lessons) if keys or typed)


def _ce_par() -> int:
    """The canonical route's keystroke count, COMPUTED from the fixed door
    table via _ce_route so it can never drift from the verb/prefix maps."""
    dummy = [{'kind': k, 'typed': t} for k, _p, _l, _t, t in _CE_DOORS]
    return sum(len(keys) + len(typed) for keys, typed in _ce_route(dummy))


_CE_PAR = _ce_par()


def build_dungeon_change_extension(seed: int) -> Dungeon:
    """The Change Extension (S, C).

    The Change Annex chassis, now with the one-key shorthands. Ten lesson rows
    (2..11) each carry a WRONG label on the floor (east of the spine) with the
    RIGHT plaque set in the WEST wall (uncuttable, off the floor scans). Four
    whole-line S doors (a single wrong word — `S` beats `cc`), four C doors (a
    correct prefix then a two-word wrong tail — `C` beats `c$`, and `ce` stops a
    word short), one `ce` word door and one `s` rune door for reinforcement.
    Below runs the gate corridor (row 12 throat → row 13 gate): the spine, a ROW
    of ten plaque-door bolts, then the exit — plain floor, east of them all. Each
    bolt opens while its label reads true; the exit is barred until every bolt
    opens, and no jump reaches it (spine = first standable, `$` stops at the first
    shut bolt). Forcing is by volume — see header."""
    rng = random.Random(seed)
    lessons = _ce_pick(rng)

    R, C = _CE_ROWS, _CE_COLS
    from vimny.engine.editor import _CELL_CODE
    from vimny.sharing.format import Level as _Level, build as _fmt_build
    cells = [[CellType.WALL] * C for _ in range(R)]
    for r in _CE_LESSON_ROWS:                        # the open lesson block (label floor)
        for c in range(_CE_COL_S, _CE_LBL_END + 1):
            cells[r][c] = CellType.FLOOR
    for c in range(_CE_Y_COL0, _CE_LBL_END + 1):     # the Y hall: wide floor for the long saying
        cells[_CE_Y_ROW][c] = CellType.FLOOR
    cells[_CE_THROAT_ROW][_CE_COL_S] = CellType.FLOOR  # spine-only throat: block → gate
    cells[_CE_GATE_ROW][_CE_COL_S] = CellType.FLOOR    # the spine reaches the gate row
    # the exit cell STAYS WALL — the FINAL SEAL; the tick floors it when every
    # plaque reads true (A/o can carve/fabricate floor, so geometry alone no
    # longer bars the way east of the bolts — see the `_label_gate` seals).
    # The bolt cells (gate row, between spine and exit) stay WALL at build; the
    # tick opens each when its label reads true. The throat joins block→gate ONLY
    # at the spine, so no east column drops onto the exit; the exit is never a
    # row's first standable cell and `$` stops at the first shut bolt.

    runs: list = []
    doors = []
    for i, lesson in enumerate(lessons):
        lrow = _CE_LESSON_ROWS[i]
        lesson['row'] = lrow
        # Lay each token as its OWN run with a bare-floor gap between them, not
        # one run with an embedded space glyph: a space glyph is a punctuation
        # 'word' (engine word-class quirk), so `w` and the `cE`/`c%` WORD scans
        # would treat a "head ctx" pair as ONE non-blank WORD and eat the
        # context. A real floor gap is genuine whitespace.
        col = _CE_LBL_COL
        for word in lesson['label'].split(' '):
            runs.append({'row': lrow, 'col': col,
                         'symbols': word, 'kind': 'ancient'})
            col += len(word) + 1
        # The saying's PREFIX, carved in the west stone (the sense that
        # replaces the decree plaque) — right-aligned, two cols shy of the
        # spine; uncuttable, off the floor scans.
        pcol = _CE_COL_S - 1 - len(lesson['prefix'])
        for word in lesson['prefix'].split(' '):
            runs.append({'row': lrow, 'col': pcol,
                         'symbols': word, 'kind': 'verdant'})
            pcol += len(word) + 1
        doors.append((lesson['target'], (_CE_GATE_ROW, _CE_GATE_COL0 + i)))
    # The Y hall: the two-ending saying's FIRST half, one word wrong, on its
    # own wide floor row. Two bolts, one per half read true.
    col = _CE_Y_COL0
    for word in _CE_Y_LAID.split(' '):
        runs.append({'row': _CE_Y_ROW, 'col': col,
                     'symbols': word, 'kind': 'ancient'})
        col += len(word) + 1
    doors.append((_CE_Y_T1, (_CE_GATE_ROW, _CE_GATE_COL0 + _CE_TRIGGERS)))
    doors.append((_CE_Y_T2, (_CE_GATE_ROW, _CE_GATE_COL0 + _CE_TRIGGERS + 1)))
    # The SECOND verse's stem plaque waits in the west wall one row BELOW the
    # first half — the echo's landing spot. Like every door here it names the
    # saying's STEM (`fool me twice`, so `once`→`twice` is the hint and the
    # rest is recalled), short enough to sit clear of the echo floor (cols
    # 1..12, floor starts at _CE_Y_COL0). When `Yp` inserts the echo row, the
    # row-shift bumps this plaque down one; the tick slides it back with the
    # restore twinkle (the Sculpting glitter, ported to the paste). Wall cells,
    # off the floor scans — it never feeds a bolt.
    pcol = 1
    for word in _CE_Y_STEM.split(' '):
        runs.append({'row': _CE_Y_ROW + 1, 'col': pcol,
                     'symbols': word, 'kind': 'verdant'})
        pcol += len(word) + 1

    level = _Level(
        name='The Change Extension', seed=seed,
        rows=R, cols=C,
        cells=[''.join(_CELL_CODE[c] for c in row) for row in cells],
        spawn=(_CE_LESSON_ROWS[0], _CE_LBL_COL),     # on door 1's wrong word
        exit=_CE_EXIT,
        char_runs=runs,
        seals=list(_label_gate(doors, _CE_EXIT)),    # the Annex chassis, as seals
        entities=[{'kind': 'exit', 'at': [_CE_EXIT[0], _CE_EXIT[1]],
                   'edit_immune': True}],
        solution=_ce_answer(lessons))      # the real keystroke tape (karaoke)

    dungeon = _fmt_build(level, par=_CE_PAR)
    room = dungeon.rooms[0]
    room._ce_y_stump  = 'fool me once'   # anchors the echo-plaque re-align (the Y row)
    room._ce_lessons  = tuple(lessons)
    return dungeon


# ── The Sculpting Chambers (I A o O) ──────────────────────────────────────────
# The topology lesson — the four insert-ENTRIES that reshape the stone, one per
# LINE of the FULL poem (the whole of ROW YOUR BOAT is the tablet; a
# skeleton-votive fragment would make no sense). The west-wall plaques
# give each line's FIRST WORD only — the player knows the song; the stone
# shows what remains of each line:
#   • O  — line 1 is MISSING and sits ABOVE the topmost given line: only `O`
#          opens a row upward. Typed whole: `row row row your boat`.
#   • I  — line 2 survives only as its TAIL (`the stream`); `I` jumps to the
#          line's first glyph and prepends `gently down ` — the given tail is
#          PUSHED east, so this line's floor runs wide (the push needs room).
#   • A  — line 3 survives only as its HEAD (`merrily merrily`); `A` appends
#          the rest — and A is the horizontal sculptor (`extend_floor`), so
#          the line carves EAST through solid stone, PAST the room's own
#          width (the buffer doubles under it): the longest line makes its
#          own space.
#   • o  — line 4 is MISSING and sits BELOW the lowest given line: only `o`
#          opens a row downward. Typed whole: `life is but a dream`.
# The vault door (a single gated cell south of line 4) opens while the whole
# poem READS TRUE, line for line. The tick (`_sculpting_chambers_tick`) is
# text- and exit_pos-relative, so it rides the row shifts o/O cause (the
# Manifold discipline); typed spaces are lawful on the tape (marked <Space>).
_SC_ROWS, _SC_COLS = 9, 40
_SC_WCOL = 13                       # the poem's lines start here — a wall GAP (cols 9-12)
                                    # breathes between the west-wall plaques and the carving floor
_SC_PLQ  = 1                        # plaque column, in the WEST wall
_SC_I_ROW = 3                       # the I line ('the stream' tail) at build
_SC_A_ROW = 4                       # the A line ('merrily merrily' head) at build
_SC_BAND = (_SC_WCOL, 45)           # scan window for each row's floor text
# The full poem, top → bottom — the votive the stone must read.
_SC_LINES = ('row row row your boat',
             'gently down the stream',
             'merrily merrily merrily merrily',
             'life is but a dream')
_SC_TARGET = tuple(ln.split()[0] for ln in _SC_LINES)   # the plaques: first words
# The plaque GIVES each line's first word — the player
# only COMPLETES the line (types everything AFTER the first word), never
# reproducing the plaque. So the FLOOR holds the completion (line minus its
# first word); the tick checks that, and the plaque supplies the head.
_SC_COMPLETIONS = tuple(ln.split(' ', 1)[1] for ln in _SC_LINES)
_SC_ANCHOR_IDX = 2                  # the plaque anchor: line 3's head is given from build
_SC_I_TYPED = 'down '               # I prepends this onto the given tail (the push)
_SC_A_TYPED = 'merrily merrily'     # A appends this onto the given head, carving east
_SC_I_GIVEN = 'the stream'          # line 2's surviving tail (completion = 'down the stream')
_SC_A_GIVEN = 'merrily'             # line 3's surviving head (completion = 'merrily'×3)
# The I line's floor must also seat the O line's completion (O opens above it and
# inherits its floor segment), so size it to the longest blank-typed completion.
_SC_I_END  = _SC_WCOL + max(len(_SC_COMPLETIONS[0]), len(_SC_COMPLETIONS[1]))
_SC_A_END  = _SC_WCOL + len(_SC_A_GIVEN)               # the A line's floor: given head + launch cell
                                    # (short — A must CARVE the rest east into the stone)
_SC_EXIT_COL = _SC_WCOL + len(_SC_COMPLETIONS[3]) - 1  # the vault door: a step SOUTH of
                                    # the LAST completion's final glyph ('dream''s m)
_SC_EXIT_ROW0 = _SC_A_ROW + 1       # at BUILD, one row below the A line; the o/O inserts
                                    # slide it down so it ends up just below line 4 (exit_pos rides)


# The route runs TOP-TO-BOTTOM, one insert-entry per line — each COMPLETING the
# line (the plaque already carries the first word):
# O 'row row your boat' · j · I 'down ' · j · A 'merrily merrily' (carves) ·
# o 'is but a dream' · j. par ENGINE-MEASURED; pinned by the driven test.
# Esc is free/omitted; spaces separate tape tokens; a TYPED space is <Space>.
_SC_PAR    = 58
_SC_ANSWER = ('Orow<Space>row<Space>your<Space>boat<Esc> j Idown<Space><Esc> j '
              'Amerrily<Space>merrily<Esc> ois<Space>but<Space>a<Space>dream<Esc> j')


def build_dungeon_sculpting_chambers(seed: int) -> Dungeon:
    """The Sculpting Chambers (slug `sculpting_chambers`): I A o O.

    The full ROW YOUR BOAT as a votive tablet, one insert-entry per line.
    Lines 2 and 3 survive in part (a tail for I, a head for A); lines 1 and
    4 are gone (O above, o below). The west plaques give each line's first
    word. When the poem reads true, line for line, the vault door (a gated
    cell south of the last line) unseals. See the section header."""
    R, C = _SC_ROWS, _SC_COLS
    from vimny.engine.editor import _CELL_CODE
    from vimny.sharing.format import Level as _Level, build as _fmt_build
    cells = [[CellType.WALL] * C for _ in range(R)]

    def floor(r, c0, c1):
        for c in range(c0, c1 + 1):
            cells[r][c] = CellType.FLOOR

    ir, ar = _SC_I_ROW, _SC_A_ROW
    floor(ir, _SC_WCOL, _SC_I_END)      # the I line: tail + room for the westward mend's push
    floor(ar, _SC_WCOL, _SC_A_END)      # the A line: head + one bare col (A's launch cell)
    # East of the A line's floor is SOLID STONE: A carves the line's second
    # half INTO it, past the room's own width (the buffer doubles under the
    # longest line). The vault door is a step SOUTH of the last line; A (an
    # east-builder) can never back-door it.

    runs: list = []
    runs.append({'row': ir, 'col': _SC_WCOL, 'symbols': _SC_I_GIVEN,
                 'kind': 'ancient'})              # line 2's surviving tail
    runs.append({'row': ar, 'col': _SC_WCOL, 'symbols': _SC_A_GIVEN,
                 'kind': 'ancient'})              # line 3's surviving head
    # The plaques, in the WEST wall: each line's FIRST WORD (confirmation,
    # not decree — the player knows the song). The tick keeps every plaque
    # ALIGNED with its line as o/O insert rows (_sculpting_chambers_tick).
    for k, word in enumerate(_SC_TARGET):
        runs.append({'row': ar + (k - _SC_ANCHOR_IDX), 'col': _SC_PLQ,
                     'symbols': word, 'kind': 'verdant'})

    exit_pos = (_SC_EXIT_ROW0, _SC_EXIT_COL)
    level = _Level(
        name='The Sculpting Chambers', seed=seed,
        rows=R, cols=C,
        cells=[''.join(_CELL_CODE[c] for c in row) for row in cells],
        spawn=(ir, _SC_WCOL),                    # on the surviving tail
        exit=exit_pos,                           # stays WALL until the poem reads true
        char_runs=runs,
        entities=[{'kind': 'exit', 'at': [exit_pos[0], exit_pos[1]],
                   'edit_immune': True}],
        solution=_SC_ANSWER)

    dungeon = _fmt_build(level, par=_SC_PAR)
    room = dungeon.rooms[0]
    room._sc_target = _SC_TARGET
    room._sc_lines  = _SC_COMPLETIONS     # the FLOOR reads the completions (plaque holds the head)
    room._sc_anchor = _SC_ANCHOR_IDX
    room._sc_band   = _SC_BAND
    return dungeon


# ── The Overwrite Halls (R) ───────────────────────────────────────────────────
# "Streams, not stitches." The player owns `r` (replace one) and `.` (repeat);
# `R` (overtype mode) earns its place where corrections run in CONSECUTIVE cells.
# Five mislabelled corridors, the Change-Annex chassis (WEST-wall plaque = the
# true word; the floor has it wrong; a bolt opens when the floor reads true):
#   • STREAM doors — a run of 3 consecutive VARIED wrong cells buried MID-word
#     (correct prefix + run + correct suffix). `R` overtypes the run in place
#     (`fx` to the run, `R` + the 3 right chars) and leaves the rest untouched.
#     Every rival overpays: `.` repeats one char so a varied run kills it (the
#     Echo Vault's lesson, inverted); the `r`-chain is `r{c}l` per cell = 3N−1;
#     `S`/`cc` (known here) clobber the correct prefix+suffix and must retype the
#     WHOLE word. FORCING by VOLUME: `R` saves _OH_SAVING keys over the cheapest
#     rival (all-`S`) across the streams, and the budget sits one below that, so
#     the fully-naive route overshoots (the Annex model).
#   • STITCH doors — a SINGLE wrong cell in an otherwise-true word: `r` fixes it
#     in two keys and `R` merely ties, so `r` stays the right tool. The lesson is
#     WHICH — stream vs stitch (the Overwrite Halls' r-vs-R discipline).
# Geometry / tick are the Annex's: spine (each row's first standable), a plaque
# in the WEST wall, a spine-only throat joining the block to the gate row, a row
# of bolts, and a plain-floor exit east of them (`_label_gate` seals; R
# overwrites IN PLACE so the floor scan is shift-free).
_OH_ROWS, _OH_COLS = 10, 39
_OH_PLQ_COL = 1                     # (retired name) the west stone band, cols 1..25
_OH_COL_S   = 27                    # the spine — the gate's first standable; the word floor
                                    # starts here, the saying's carved PREFIX fills the west wall
_OH_LBL_COL = _OH_COL_S            # the wrong word sits on the floor here
_OH_LBL_END = 36                    # word floor reaches here (fits the 9-char stream word)
_OH_LESSON_ROWS = (2, 3, 4, 5, 6)   # five corridors, descended by j
_OH_THROAT_ROW  = 7                 # spine-only row: the block joins the gate
_OH_GATE_ROW    = 8                 # the gate corridor: spine · bolts · exit
_OH_GATE_COL0   = 28                # first bolt column (one per corridor)
_OH_TRIGGERS    = len(_OH_LESSON_ROWS)
_OH_EXIT = (_OH_GATE_ROW, _OH_GATE_COL0 + _OH_TRIGGERS)   # plain floor, east of the bolts
_OH_RUN = 'xzq'                     # the 3-cell corruption every stream shares (fx finds it)

# SENSE, NOT DECREE (the change levels):
# (kind, stone prefix, target, wrong). Every corridor's floor word FINISHES a
# saying whose start is carved in the west stone — the cure is the letters
# everyone knows. STREAM: a 3-cell varied run mid-word (fx→R fixes it, S/cc/ce
# overpay). STITCH: one wrong cell (r's niche). The corrupt positions keep the
# tape's landing chain: C2's x sits west of C1's post-R cursor, C3's run west
# of C2's mend, C4's wrong cell exactly under C3's post-R cursor, C5's run
# west of C4's mend (all asserted in tests).
_OH_LESSONS = (
    ('stream', 'seeing is', 'believing', 'beli' + _OH_RUN + 'ng'),
    ('stitch', 'haste makes', 'waste', 'wastx'),
    ('stream', 'a penny saved is a penny', 'earned', 'ea' + _OH_RUN + 'd'),
    ('stitch', 'lightning never strikes', 'twice', 'twica'),
    ('stream', 'speech is', 'silver', 'si' + _OH_RUN + 'r'),
)
# par + the canonical tape, driven end-to-end (no Dijkstra — R overwrites in
# place, but the fx-R-run route is hand-measured like the Annex). The route is
# the GOLFED one — `F` (backward-find, NOT `^f`) back to each run, the C4 stitch
# taken free (the descent lands the cursor on it), and `G$` (NOT `^jj$`) to the
# door:  fx Revi · Fx re · Fx Rrne · re · Fx Rlve · G$  = 30 keys.
# Rivals measured on the SAME fixed geometry with the SAME golfed nav: all-`S`
# (retype the whole word) and the `r`-chain both overshoot; the budget bars the
# cheapest no-R route by one (par + _OH_SAVING − 1) — the Annex model.
_OH_PAR    = 30
_OH_ANSWER = 'fx Revi<Esc> j Fx re j Fx Rrne<Esc> j re j Fx Rlve<Esc> G$'
_OH_SAVING = 8


def build_dungeon_overwrite_halls(seed: int) -> Dungeon:
    """The Overwrite Halls (slug `overwrite_halls`): R.

    Five mislabelled corridors on the Change-Annex chassis. STREAM doors bury a
    run of consecutive varied wrong cells mid-word — only `R` (overtype) fixes
    them without clobbering the correct prefix/suffix; STITCH doors have one wrong
    cell where `r` still rules. See the section header for the forcing."""
    R, C = _OH_ROWS, _OH_COLS
    from vimny.engine.editor import _CELL_CODE
    from vimny.sharing.format import Level as _Level, build as _fmt_build
    cells = [[CellType.WALL] * C for _ in range(R)]
    for r in _OH_LESSON_ROWS:                        # the open corridor block
        for c in range(_OH_COL_S, _OH_LBL_END + 1):
            cells[r][c] = CellType.FLOOR
    cells[_OH_THROAT_ROW][_OH_COL_S] = CellType.FLOOR   # spine-only throat
    cells[_OH_GATE_ROW][_OH_COL_S]   = CellType.FLOOR   # the spine reaches the gate row
    # the exit cell STAYS WALL — the FINAL SEAL; the tick floors it when every
    # plaque reads true (A/o can carve/fabricate floor, so geometry alone no
    # longer bars the way east of the bolts — see the `_label_gate` seals).
    # the bolt cells (gate row, between spine and exit) stay WALL; the tick opens
    # each when its corridor reads true.

    runs: list = []
    doors = []
    lessons = []
    for i, (kind, prefix, target, wrong) in enumerate(_OH_LESSONS):
        lrow = _OH_LESSON_ROWS[i]
        runs.append({'row': lrow, 'col': _OH_LBL_COL, 'symbols': wrong,
                     'kind': 'ancient'})                     # the WRONG word, on the floor
        # the saying's carved prefix, right-aligned in the west stone (the
        # sense that replaces the decree plaque)
        pcol = _OH_COL_S - 1 - len(prefix)
        for w in prefix.split(' '):
            runs.append({'row': lrow, 'col': pcol, 'symbols': w, 'kind': 'verdant'})
            pcol += len(w) + 1
        doors.append((target, (_OH_GATE_ROW, _OH_GATE_COL0 + i)))
        lessons.append({'kind': kind, 'prefix': prefix, 'target': target,
                        'wrong': wrong, 'row': lrow})

    level = _Level(
        name='The Overwrite Halls', seed=seed,
        rows=R, cols=C,
        cells=[''.join(_CELL_CODE[c] for c in row) for row in cells],
        spawn=(_OH_LESSON_ROWS[0], _OH_COL_S),           # on corridor 1, at the spine
        exit=_OH_EXIT,
        char_runs=runs,
        seals=list(_label_gate(doors, _OH_EXIT)),
        entities=[{'kind': 'exit', 'at': [_OH_EXIT[0], _OH_EXIT[1]],
                   'edit_immune': True}],
        solution=_OH_ANSWER)

    dungeon = _fmt_build(level, par=_OH_PAR)
    dungeon.rooms[0]._oh_lessons = tuple(lessons)
    return dungeon


# ── The Case Chambers (~ gU gu g~) ────────────────────────────────────────────
# "Case is text the eye can't grep." Eight mislabelled corridors on the
# Change-Annex chassis: every floor word is letter-perfect but the CASING rotted;
# the WEST-wall plaque keeps the true form and the bolt opens when the floor
# reads true (the tick's substring check is case-sensitive already). Case ops
# edit IN PLACE — no reflow, shift-free floor scans, the Overwrite Halls model.
#
# Forcing, tool by tool (the lesson is WHICH, as in the Halls' r-vs-R):
#   • TILDE doors — ONE wrong-case cell. `~` fixes it in a single key and is
#     letter-independent; `r{c}` ties the nav but pays 2 for the fix.
#   • UPPER/LOWER doors — a word whose target is all-caps (or all-lower) with
#     the wrong cells SCATTERED (never contiguous). This kills count-~: wrong
#     means needs-a-toggle, so `{n}~` over the span toggles the CORRECT cells
#     too and the bolt stays shut; the ~-and-move chain overpays; gU/gu are
#     idempotent SETS — one sweep fixes wrong and right alike. The golfed form
#     is the doubled linewise (gUU from wherever the descent left the cursor);
#     `gue`/`gUe` tie only from column 0. One lower door is the `.` echo of the
#     previous `gue` (the Echo Vault's lesson, replayed on a new operator).
#   • The gUE door — the target spans a ★ (a WORD, not a word): `e` stops at
#     the symbol, so `gUe` mends half and the bolt stays shut; `gUE` sweeps it.
#   • The guu door — TWO words across a bare-floor gap, cursor arriving
#     mid-row (the previous tilde door's `~` advances east): `gu$` misses the
#     head, `^gu$` pays 4; `guu` takes the whole line for 3.
#   • The g~~ finale — a fully case-INVERTED two-word line with a MIXED-case
#     target: `guu`/`gUU` both write the wrong case; only the toggle mends it.
#     (`{n}~`/`g~$` from col 0 TIE at 3 keys — g~ is showcased, not priced out;
#     a toggle-operator can never out-price the toggle-key, so the door's job
#     is to make the linewise form the natural spelling.)
# FORCING BY PAR (standard 1.4 budget): the cheapest no-case-op route is the
# r-chain (2 keys per wrong cell + moves, and letter-dependent besides) or a
# retype (S/R + the whole word) — both blow past the budget long before the
# gate; the case-op route is the only par-priced one.
#
# Geometry / tick are the Annex's: per-row EXACT-FIT floors (the corridor ends
# where the word ends, so `$` lands on the last LETTER — the tilde door's nav),
# spine at the label column, a spine-only throat row, a row of eight bolts, and
# a plain-floor exit east of them (`_label_gate` seals).
_CASE_ROWS, _CASE_COLS = 13, 27
_CASE_PLQ_COL = 1                     # the true form, in the WEST wall (cols 1..11)
_CASE_COL_S   = 15                    # the spine — every row's first standable; a
                                      # 3-col wall gap (12..14) breathes between the
                                      # plaques and the floor (an ADJACENT
                                      # plaque run merges with the floor
                                      # word and painted it plaque-colored)
_CASE_LBL_COL = _CASE_COL_S            # the mis-cased word sits on the floor here
_CASE_LESSON_ROWS = (2, 3, 4, 5, 6, 7, 8, 9)   # eight corridors, descended by j
_CASE_THROAT_ROW  = 10                # spine-only row: the block joins the gate
_CASE_GATE_ROW    = 11                # the gate corridor: spine · bolts · exit
_CASE_GATE_COL0   = 16                # first bolt column (one per corridor)
_CASE_TRIGGERS    = len(_CASE_LESSON_ROWS)
_CASE_EXIT = (_CASE_GATE_ROW, _CASE_GATE_COL0 + _CASE_TRIGGERS)   # plain floor, east of the bolts

# (kind, target, wrong) — same letters, only the CASE lies. Kinds:
#   tilde  — one wrong cell (~'s niche; the first ends the word so `$` finds it,
#            the second sits mid-word and its `~` leaves the cursor EAST so the
#            next row is entered mid-line)
#   upper  — all-caps target, wrongs scattered      → gUU (count-~ dies)
#   lower  — all-lower target, wrongs scattered     → gue (from col 0)
#   echo   — same shape as lower, right after it    → `.`
#   upperW — the target spans ★, a WORD             → gUE (gUe mends half)
#   lowerL — two words across a gap, entered mid-row → guu (^gu$ pays one more)
#   invert — every letter case-flipped, MIXED target → g~~ (guu/gUU both wrong)
_CASE_LESSONS = (
    ('tilde',  'lantern',     'lanterN'),
    ('upper',  'BULWARK',     'bUlWaRk'),
    ('lower',  'wardens',     'wArDeNs'),
    ('echo',   'granite',     'gRaNiTe'),
    ('upperW', 'IRON★GATE',   'iRoN★gAtE'),
    ('tilde',  'obelisk',     'obeliSk'),
    ('lowerL', 'dim ember',   'DiM eMbEr'),
    ('invert', 'Veil Bearer', 'vEIL bEARER'),
)
# par + the canonical tape, driven end-to-end (hand-measured like the Halls —
# case ops act in place, no Dijkstra). The route is the GOLFED one: `$~` takes
# the first tilde door (exact-fit floor puts `$` on the letter), `gUU` from
# wherever `j` lands (linewise needs no `^`), `.` echoes the `gue`, `5l~` walks
# to the buried stitch and leaves the cursor east so `guu` is forced over
# `^gu$`, and `G$` rides the open bolts to the door:
#   $~ · gUU · gue · . · gUE · 5l~ · guu · g~~ · G$  (+7 j)  = 30 keys.
# Rivals on the same nav: the r-chain ≈ 70+, the S/R retype ≈ 60+ — both far
# past the STANDARD budget (ceil(par × 1.4) = 42), so no tight margin needed.
_CASE_PAR    = 30
_CASE_ANSWER = '$~ j gUU j gue j . j gUE j 5l~ j guu j g~~ G$'


def build_dungeon_case_chambers(seed: int) -> Dungeon:
    """The Case Chambers (slug `case_chambers`): ~ gU gu g~.

    Eight mislabelled corridors on the Change-Annex chassis where only the CASE
    of each floor word rotted. Tilde doors carry one wrong cell (~'s niche);
    scattered-wrong words force the idempotent gU/gu sweeps (count-~ toggles the
    correct cells too); a ★-spanning WORD forces gUE; a mid-row entry forces the
    doubled guu; the finale's fully-inverted MIXED-case line yields only to g~~.
    See the section header for the full forcing."""
    R, C = _CASE_ROWS, _CASE_COLS
    from vimny.engine.editor import _CELL_CODE
    from vimny.sharing.format import Level as _Level, build as _fmt_build
    cells = [[CellType.WALL] * C for _ in range(R)]
    for i, (kind, target, wrong) in enumerate(_CASE_LESSONS):
        r = _CASE_LESSON_ROWS[i]
        for c in range(_CASE_COL_S, _CASE_COL_S + len(wrong)):   # EXACT-FIT corridor:
            cells[r][c] = CellType.FLOOR                     # $ ends ON the word
    cells[_CASE_THROAT_ROW][_CASE_COL_S] = CellType.FLOOR   # spine-only throat
    cells[_CASE_GATE_ROW][_CASE_COL_S]   = CellType.FLOOR   # the spine reaches the gate row
    # the exit cell STAYS WALL — the FINAL SEAL; the tick floors it when every
    # plaque reads true (A/o can carve/fabricate floor, so geometry alone no
    # longer bars the way east of the bolts — see the `_label_gate` seals).
    # the bolt cells (gate row, between spine and exit) stay WALL; the tick opens
    # each when its corridor's case reads true.

    def lay(runs, r, c, text, kind):
        # split on spaces — a literal space glyph is a punctuation "word" (the
        # Change Extension gotcha); the floor scan reconstructs the gap.
        col = c
        for part in text.split(' '):
            if part:
                runs.append({'row': r, 'col': col, 'symbols': part, 'kind': kind})
            col += len(part) + 1

    runs: list = []
    doors = []
    lessons = []
    for i, (kind, target, wrong) in enumerate(_CASE_LESSONS):
        lrow = _CASE_LESSON_ROWS[i]
        lay(runs, lrow, _CASE_LBL_COL, wrong, 'ancient')       # the mis-cased word, on the floor
        lay(runs, lrow, _CASE_PLQ_COL, target, 'verdant')      # the true form, the WEST-wall plaque
        doors.append((target, (_CASE_GATE_ROW, _CASE_GATE_COL0 + i)))
        lessons.append({'kind': kind, 'target': target, 'wrong': wrong, 'row': lrow})

    level = _Level(
        name='The Case Chambers', seed=seed,
        rows=R, cols=C,
        cells=[''.join(_CELL_CODE[c] for c in row) for row in cells],
        spawn=(_CASE_LESSON_ROWS[0], _CASE_COL_S),     # on corridor 1, at the spine
        exit=_CASE_EXIT,
        char_runs=runs,
        seals=list(_label_gate(doors, _CASE_EXIT)),
        entities=[{'kind': 'exit', 'at': [_CASE_EXIT[0], _CASE_EXIT[1]],
                   'edit_immune': True}],
        solution=_CASE_ANSWER)

    dungeon = _fmt_build(level, par=_CASE_PAR)
    dungeon.rooms[0]._cc_lessons = tuple(lessons)
    return dungeon


# ── The Joiner's Gate (J gJ) ──────────────────────────────────────────────────
# "Pull the world up into your line." Four split inscriptions on the Annex
# chassis: each lesson is a STACK of rows — the plaque keeps the true line, the
# floor has it split one word per row. Joining makes the top row read true and
# the (substring) tick opens the bolt. J leaves one space at the seam; gJ none;
# {n}J joins n lines. The choice is CONTENT-forced per door: a two-word plaque
# (`bind veil`) needs the seam space → J; a fused plaque (`wardstone`) → gJ; a
# wrong variant reads false, the bolt stays shut, and `u` restores the stack.
#
# J is a TERRAIN EDITOR, so the chassis must be hardened for it:
#   • every join removes a row and slides the gate/bolts/exit UP —
#     `Seal.anchor` derives the gate row from exit_pos each tick
#     (which `_shift_rows` keeps true), so the bolts ride the collapses;
#   • the gate row itself is join-proof: `remove_row` refuses a row holding an
#     edit_immune entity, and the exit entity is edit_immune;
#   • the exit is the FINAL SEAL (stone until every plaque reads true), so the
#     floor J/A/o can fabricate never reaches a live exit.
#
# FORCING BY PAR (standard 1.4 budget): J = 1 key per door. The no-join rival
# writes the missing words by hand (`ea` + the text, ~7 keys a door, ~12 for
# the finale — A won't do: it appends past the trailing floor, stranding the
# text far east of the seam, so the row never reads true) or emulates a join
# with de + k$p (the paste lands at the floor's end, same stranding). With
# four doors the all-old route is ~4x the budget.
#
# FINALE: `4J`, not `3J` — 3J (2 keys) TIES JJ (2 keys) and teaches nothing;
# a four-row stack makes 4J (2) beat JJJ (3) by one, the count paying exactly
# at the door where it's taught (the Echo Vault's count-dot echo).
_JG_ROWS, _JG_COLS = 15, 29
_JG_PLQ_COL = 1                     # the true line, in the WEST wall (cols 1..14)
_JG_COL_S   = 15                    # the spine — every row's first standable
_JG_LBL_COL = _JG_COL_S            # the split words sit on the floor here
_JG_FLOOR_END = 27                  # uniform stack floor (holds the longest join)
_JG_STACK_TOPS = (2, 4, 6, 8)       # each stack's TOP row (the join happens here)
_JG_THROAT_ROW  = 12                # spine-only row: the block joins the gate
_JG_GATE_ROW    = 13                # the gate corridor: spine · bolts · seal
_JG_GATE_COL0   = 16                # first bolt column (one per stack)
_JG_TRIGGERS    = len(_JG_STACK_TOPS)
_JG_EXIT = (_JG_GATE_ROW, _JG_GATE_COL0 + _JG_TRIGGERS)   # the FINAL SEAL

# (kind, target, split_rows). kind: 'J' (seam space), 'gJ' (fused), '4J' (the
# count finale — three seams in one stroke).
_JG_LESSONS = (
    ('J',  'bind veil',     ('bind', 'veil')),
    ('gJ', 'wardstone',     ('ward', 'stone')),
    ('J',  'oath sworn',    ('oath', 'sworn')),
    ('4J', 'the way is up', ('the', 'way', 'is', 'up')),
)
# par + the canonical tape, driven end-to-end (hand-measured — every join
# collapses a row, so the next stack's top is always ONE j away; each join
# lands the cursor on the seam, still on the uniform floor):
#   J · j · gJ · j · J · j · 4J · G$  = 11 keys.
_JG_PAR    = 11
_JG_ANSWER = 'J j gJ j J j 4J G$'


def build_dungeon_joiners_gate(seed: int) -> Dungeon:
    """The Joiner's Gate (slug `joiners_gate`): J gJ.

    Four split inscriptions on the (join-hardened) Annex chassis. Each stack
    joins up into its plaque's line: two-word plaques take J's seam space,
    fused plaques take gJ, and the four-row finale takes 4J — the count form
    at the count where it first beats repeated J. See the section header."""
    R, C = _JG_ROWS, _JG_COLS
    from vimny.engine.editor import _CELL_CODE
    from vimny.sharing.format import Level as _Level, build as _fmt_build
    cells = [[CellType.WALL] * C for _ in range(R)]
    stack_rows = []
    for top, (kind, target, split) in zip(_JG_STACK_TOPS, _JG_LESSONS):
        stack_rows.extend(range(top, top + len(split)))
    for r in stack_rows:                                 # uniform stack floor:
        for c in range(_JG_COL_S, _JG_FLOOR_END + 1):    # wide enough to receive
            cells[r][c] = CellType.FLOOR                 # the longest joined line
    cells[_JG_THROAT_ROW][_JG_COL_S] = CellType.FLOOR    # spine-only throat
    cells[_JG_GATE_ROW][_JG_COL_S]   = CellType.FLOOR    # the spine reaches the gate
    # bolts AND the exit stay WALL — the tick opens the bolts per plaque and
    # parts the FINAL SEAL when all four read true.

    def lay(runs, r, c, text, kind):
        col = c
        for part in text.split(' '):                     # separate runs per word
            if part:
                runs.append({'row': r, 'col': col, 'symbols': part, 'kind': kind})
            col += len(part) + 1

    runs: list = []
    doors = []
    lessons = []
    for i, (top, (kind, target, split)) in enumerate(zip(_JG_STACK_TOPS, _JG_LESSONS)):
        for k, word in enumerate(split):
            lay(runs, top + k, _JG_LBL_COL, word, 'ancient')   # the split words, stacked
        lay(runs, top, _JG_PLQ_COL, target, 'verdant')         # the true line, west wall
        doors.append((target, (_JG_GATE_ROW, _JG_GATE_COL0 + i)))
        lessons.append({'kind': kind, 'target': target, 'split': split, 'top': top})

    level = _Level(
        name="The Joiner's Gate", seed=seed,
        rows=R, cols=C,
        cells=[''.join(_CELL_CODE[c] for c in row) for row in cells],
        spawn=(_JG_STACK_TOPS[0], _JG_COL_S),          # atop stack 1, at the spine
        exit=_JG_EXIT,
        char_runs=runs,
        seals=list(_label_gate(doors, _JG_EXIT)),
        entities=[{'kind': 'exit', 'at': [_JG_EXIT[0], _JG_EXIT[1]],
                   'edit_immune': True}],              # join-proof: remove_row refuses
        solution=_JG_ANSWER)

    dungeon = _fmt_build(level, par=_JG_PAR)
    dungeon.rooms[0]._jg_lessons = tuple(lessons)
    return dungeon



# ── The Alignment Halls (>> << + the case reprise) ────────────────────────────
# "Lines shove sideways — and the register line keeps both truths." Five words
# on the Annex block, each mis-SET from the shared REGISTER COLUMN (the plumb
# line, marked by │ glyphs carved in the wall bands above and below the block)
# and two of them mis-CASED as well — the Case Chambers' lesson, reprised one
# level later. The west-wall plaque keeps the true word in its TRUE CASE; a
# bolt stands open while its word reads true-cased with its first letter
# EXACTLY on the register line (exact text at the exact column, any floor row —
# `_alignment_halls_tick`, shift-/case-/o-proof, FINAL-SEAL exit).
#
# Forcing, against the REAL frontier (the old draft priced a 9-key
# delete-retype; the true rival is cheaper):
#   • a shift's rival is the INSERT-SHOVE (`i`+junk+Esc ≈ 4-5 keys vs `>>` 2)
#     — junk passes the slice check, so it's a legal, LOSING route (1 star);
#   • `<<` has no rival at all: a shifted line has no leading chars to `x`;
#   • the case reprise is forced by PAR: the no-case-op rival (`R`/`r` retype
#     after the shift) wins at ~+6 over par — inside the standard budget,
#     out of the second star (the law, working as written);
#   • `.` rides the indent: `>>` is a change, so rows 2 and 5 take their
#     shift as dot (dot's third outing — r at the Echo Vault, now `>>`/`2>>`);
#   • PARITY LAW: every offset is a multiple of INDENT_WIDTH=2 (an odd
#     offset would be unreachable by the taught command — asserted in tests);
#   • over-shift is real: one `>>` too many carries the word PAST the line
#     and the bolt re-bars (the check is two-sided); `<<` walks it back, and
#     the +2 row makes `<<` load-bearing, not remedial.
_AH_ROWS, _AH_COLS = 10, 28
_AH_PLQ_COL = 1                     # the true word, TRUE CASE, in the WEST wall
_AH_COL_S   = 10                    # the spine — every row's first standable
_AH_FLOOR_END = 25                  # the block floor; past it, shifted tails fall
_AH_REGISTER  = 16                  # the plumb line: first letters sit HERE
_AH_LESSON_ROWS = (2, 3, 4, 5, 6)   # the open block, descended by j
_AH_BAND_ROWS   = (1, 7)            # wall bands carrying the │ plumb glyphs
_AH_THROAT_ROW  = 7                 # spine-only row (shares the lower band)
_AH_GATE_ROW    = 8                 # the gate corridor: spine · bolts · seal
_AH_GATE_COL0   = 11                # first bolt column (one per lesson row)
_AH_TRIGGERS    = len(_AH_LESSON_ROWS)
_AH_EXIT = (_AH_GATE_ROW, _AH_REGISTER)   # the FINAL SEAL — on the plumb line

# (kind, target, wrong, offset): the floor shows `wrong` starting at
# REGISTER+offset. kinds: shift (case true, >> once) · upper (scattered wrong,
# gUU, count-~ dies) · tilde (ONE wrong char, ~ taken free off <<'s cursor
# snap) · pair (the COUNT lesson, Vim-true: `{n}>>` indents N ROWS, not one
# row n times — the last two rows share the −2 offset and take ONE `2>>`;
# the second of the pair is also the full case inversion, MIXED target,
# only g~~ mends it).
_AH_LESSONS = (
    ('shift',  'lintel', 'lintel', -2),
    ('upper',  'BEAM',   'bEaM',   -2),
    ('tilde',  'Sill',   'sill',   +2),
    ('pair',   'corbel', 'corbel', -2),
    ('invert', 'Panel',  'pANEL',  -2),
)
# par + the canonical tape, hand-measured and driven end-to-end. GOLFED: the
# row-3 shift is `.` (repeating >>), `<<` snaps the cursor onto the word's
# first letter so the tilde fix is one key, `2>>` seats the LAST TWO rows in
# one stroke (vs `>> j .` = 4 — the count saves one), and every indent op is
# column-agnostic so the descent needs no nav:
#   >> · .gUU · <<~ · 2>> · g~~ · G$  (+4 j)  = 21 keys.
# Rivals: the no-case-op R-retype route = 27 (wins, 1 star — the reprise is
# forced by PAR); the insert-shove ≈ 4-5 keys per shift (legal, losing).
_AH_PAR    = 21
_AH_ANSWER = '>> j .gUU j <<~ j 2>> j g~~ G$'


def build_dungeon_alignment_halls(seed: int) -> Dungeon:
    """The Alignment Halls (slug `alignment_halls`): >> << (+ the case reprise).

    Five words mis-set from the register line, two mis-cased as well: `>>`/`<<`
    seat each word's first letter exactly on the plumb column, the case verbs
    from the Chambers make it read true, and `.` rides the indent. The bolt
    check is exact-text-at-exact-column; the exit is the final seal. See the
    section header for the forcing."""
    R, C = _AH_ROWS, _AH_COLS
    from vimny.engine.editor import _CELL_CODE
    from vimny.sharing.format import Level as _Level, build as _fmt_build
    cells = [[CellType.WALL] * C for _ in range(R)]
    for r in _AH_LESSON_ROWS:                            # the open block
        for c in range(_AH_COL_S, _AH_FLOOR_END + 1):
            cells[r][c] = CellType.FLOOR
    cells[_AH_THROAT_ROW][_AH_COL_S] = CellType.FLOOR    # spine-only throat
    cells[_AH_GATE_ROW][_AH_COL_S]   = CellType.FLOOR    # the spine reaches the gate
    # bolts AND the exit stay WALL — the tick opens the bolts per seated word
    # and parts the FINAL SEAL when all five stand on the register.

    runs: list = []
    for br in _AH_BAND_ROWS:                             # the plumb line marks
        runs.append({'row': br, 'col': _AH_REGISTER, 'symbols': '│',
                     'kind': 'verdant'})

    # The five bolts + final seal ride the file as Seals — the Alignment rule
    # is the target's first glyph ON the register line, whatever sits west of
    # it: `at`, the pin law (i+junk shoving a word onto the plumb is a legal
    # route — the slice never saw west of the pin).
    lessons = []
    for i, (kind, target, wrong, offset) in enumerate(_AH_LESSONS):
        lrow = _AH_LESSON_ROWS[i]
        runs.append({'row': lrow, 'col': _AH_REGISTER + offset,
                     'symbols': wrong, 'kind': 'ancient'})   # mis-set (mis-cased) word
        runs.append({'row': lrow, 'col': _AH_PLQ_COL, 'symbols': target,
                     'kind': 'verdant'})                     # the true form, west wall
        lessons.append({'kind': kind, 'target': target, 'wrong': wrong,
                        'offset': offset, 'row': lrow})
    seals = gate_row_seals(
        [(target, _AH_GATE_COL0 + i) for i, (kind, target, wrong, offset)
         in enumerate(_AH_LESSONS)],
        _AH_EXIT, mode='exact', at=_AH_REGISTER,
        bolt_message='The word sits true on the line — the bolt grinds back!',
        final_message='Every word stands on the register — the final seal parts!')

    level = _Level(
        name='The Alignment Halls', seed=seed,
        rows=R, cols=C,
        cells=[''.join(_CELL_CODE[c] for c in row) for row in cells],
        spawn=(_AH_LESSON_ROWS[0], _AH_COL_S),               # on row one, at the spine
        exit=_AH_EXIT,
        char_runs=runs, seals=seals,
        entities=[{'kind': 'exit', 'at': [_AH_EXIT[0], _AH_EXIT[1]],
                   'edit_immune': True}],
        solution=_AH_ANSWER)

    dungeon = _fmt_build(level, par=_AH_PAR)
    room = dungeon.rooms[0]
    room._ah_register_col = _AH_REGISTER
    room._ah_lessons      = tuple(lessons)
    _seal_banners(dungeon,
                  bolt='The word sits true on the line — the bolt grinds back!',
                  final='Every word stands on the register — the final seal parts!')
    return dungeon


# ── The Indentation Sanctum (>{m} <{m} =) ─────────────────────────────────────
# "In these halls, the law of = is posted." Vim's `=` is a POLICY SOCKET
# (equalprg → indentexpr → the C fallback that mauls prose); Vimny's `=`
# applies the BLOCK LAW (engine/operator.law_column — the posted edict):
# a verse under a ':' line stands one step deeper, 'end' returns to its
# opener's station, and UNGOVERNED verse stands at the wall — which is how
# `=` wrecks plain text, kept faithfully as a playable trap.
#
# Three bays down one hall, one verb each (cannibalism solved by GEOGRAPHY):
#   • the UNGOVERNED GALLERY — plain nouns 2 west of the plumb register:
#     `>}` (2 keys) seats all three rows in one paragraph stroke. `=` here
#     RAZES the bank to the wall (visibly wrong, `u` recovers): the player
#     re-enacts the gg=G-in-markdown disaster on purpose.
#   • the OVER-SHOVED GALLERY — mirror bank past the register: `<}`.
#   • the SANCTUM'S RITE — a simple pseudocode block (fixed skeleton, ONE
#     nesting level, seeded vocab in the slots — the Operator's Vault rule)
#     whose rows are SCATTERED (+2/−2/0/+4 mixed): no uniform >{m}/<{m}
#     stroke can satisfy it and the manual per-row chain is ~18 keys; `=}`
#     (2 keys) snaps the whole rite to the law. The door check calls the
#     SAME law_column the operator uses — solver and judge can never drift.
#
# FORCING BY PAR (the budget is the standard 1.4x, per the par-is-the-optimum
# law): the manual-mason route (3>> banks, per-row >>/<</dot through the rite —
# no `=` ever) costs ~30 against par 12. `=}` really is that dominant — it seats
# a whole paragraph under the posted law for one stroke — so nothing clumsier
# than the par route fits a standard budget, and the manual road does not
# finish. That is the level being honest about how large the win is. Blank FLOOR rows separate the bays, so `}` paragraph motions
# bound each bank and j descends freely (no spine detours — the old draft's
# water terrain is dropped: floor rows are {n}G-landable and water is
# insert-bridgeable, so terrain-S1 was always a fiction).
_IS_ROWS, _IS_COLS = 21, 27
_IS_PLQ_COL = 1                     # gallery plaques (the true word), WEST wall
_IS_COL_S   = 10                    # the spine — every row's first standable
_IS_FLOOR_END = 25                  # the hall floor; past it, shoved tails fall
_IS_REGISTER  = 16                  # the galleries' plumb line (│ in the wall)
_IS_G1_ROWS = (2, 3, 4)             # ungoverned gallery: nouns at REGISTER−2
_IS_G2_ROWS = (6, 7, 8)             # over-shoved gallery: nouns at REGISTER+2
_IS_RITE_ROWS = (10, 11, 12, 13, 14, 15, 16)   # the rite block
_IS_BLANK_ROWS = (5, 9, 17)         # bare floor: paragraph boundaries for }
_IS_THROAT_ROW = 18                 # spine-only row: the hall joins the gate
_IS_GATE_ROW   = 19                 # the gate corridor: spine · bolts · seal
_IS_GATE_COL0  = 11                 # three bolts: gallery 1 · gallery 2 · rite
_IS_TRIGGERS   = 3
_IS_EXIT = (_IS_GATE_ROW, _IS_GATE_COL0 + _IS_TRIGGERS)   # the FINAL SEAL

# The rite skeleton: (template, corrupt_col). Templates hold {v}/{n} slots
# filled from the vocab per seed (structure and offsets FIXED — the answer
# tape is position-based). True columns derive from the LAW (base 10):
#   rite {n}:      10        corrupt 12  (+2)
#     {v} {n}      12        corrupt 10  (−2)
#     when {n}:    12        corrupt 14  (+2)
#       {v} {n}    14        corrupt 14  ( 0 — already true: = is idempotent)
#     end          12        corrupt 10  (−2)
#     {v} {n}      12        corrupt 16  (+4)
#   end            10        corrupt 12  (+2)
_IS_RITE = (
    ('rite {n}:', 12),
    ('{v} {n}',   10),
    ('when {n}:', 14),
    ('{v} {n}',   14),
    ('end',       10),
    ('{v} {n}',   16),
    ('end',       12),
)
_IS_NOUNS = ('oath', 'rune', 'veil', 'lamp', 'gate', 'ash',
             'fern', 'moss', 'dust', 'iron', 'bell', 'loam')
_IS_VERBS = ('bind', 'ward', 'mend', 'keep', 'cast', 'hew')
# par + the canonical tape, driven end-to-end. GOLFED: `>}`/`<}`/`=}` take
# each bay as one paragraph stroke (the blank courses bound them), the open
# floor lets `4j` hop bay to bay with no spine detours, `G$` rides the open
# bolts to the seal:  >} · 4j · <} · 4j · =} · G$  = 12 keys.
# The manual-mason rival (no `=`): 3>> banks + per-row >>/<</dot through the
# rite ≈ 30 — 2.5x par, so it does not fit the standard budget.
_IS_PAR    = 11
_IS_BUDGET = math.ceil(_IS_PAR * 1.4)   # STANDARD (par-is-the-optimum law)
#: The SECOND hop is `M`, the first stays `4j`. The sanctum is 21 rows and the
#: game area is usually smaller, so `M` is viewport-relative here — and it was
#: measured winning at the same cost at every terminal height from 25 to 60,
#: which is the only reason it is allowed to stand in a par (2026-08-03). The
#: lesson survives it: `>}`, `<}` and `=}` are all still pressed, which is the
#: rule a golfed tape has to pass before its par is lowered.
_IS_ANSWER = '>} 4j <} M =} G$'


def build_dungeon_indentation_sanctum(seed: int) -> Dungeon:
    """The Indentation Sanctum (slug `indentation_sanctum`): >{m} <{m} =.

    Two ungoverned galleries seat by paragraph shove (`>}`/`<}` — `=` there
    razes to the wall, the markdown trap); the rite, a seeded pseudocode
    block with scattered offsets, yields only to `=}` under the posted law.
    See the section header for the forcing."""
    rng = random.Random(seed)
    R, C = _IS_ROWS, _IS_COLS
    from vimny.engine.editor import _CELL_CODE
    from vimny.sharing.format import Level as _Level, build as _fmt_build
    cells = [[CellType.WALL] * C for _ in range(R)]
    hall_rows = _IS_G1_ROWS + _IS_G2_ROWS + _IS_RITE_ROWS + _IS_BLANK_ROWS
    for r in hall_rows:                                  # one open hall
        for c in range(_IS_COL_S, _IS_FLOOR_END + 1):
            cells[r][c] = CellType.FLOOR
    cells[_IS_THROAT_ROW][_IS_COL_S] = CellType.FLOOR    # spine-only throat
    cells[_IS_GATE_ROW][_IS_COL_S]   = CellType.FLOOR    # the spine reaches the gate
    # bolts AND the exit stay WALL — the tick opens them; the exit is the seal.

    def lay(runs, r, c, text, kind):
        col = c
        for part in text.split(' '):                     # separate runs per word
            if part:
                runs.append({'row': r, 'col': col, 'symbols': part, 'kind': kind})
            col += len(part) + 1

    runs: list = []
    # THE LINTEL — the law is not a passing tip but a carving that presides
    # over the whole playthrough: two lines in the top
    # wall bands, laid so the plumb │ falls exactly through the word-gap at
    # the register column ("the law is │ posted").
    lay(runs, 0, 6, 'in these halls', 'verdant')
    lay(runs, 1, 6, 'the law is posted', 'verdant')      # gap lands at col 16
    lay(runs, 1, _IS_REGISTER, '│', 'verdant')           # the plumb line, carved above
    # THE RITE'S OWN HEADING: the galleries wear their true word on the west
    # wall, but the rite block wears none, so without this nothing on screen
    # would say the block below is CODE — and `=` is the tool
    # that seats code. Carved as a TAG, `<code>`, not as prose: the galleries'
    # plaques are literal words the floor must match, so a plaque reading "the
    # code" invites the player to go and write those words. A tag reads as a
    # label ABOUT the block, which is what it is. It names no key.
    lay(runs, _IS_BLANK_ROWS[1], _IS_PLQ_COL, '<code>', 'verdant')

    nouns = rng.sample(_IS_NOUNS, 6 + sum(t.count('{n}') for t, _ in _IS_RITE))
    verbs = rng.sample(_IS_VERBS, sum(t.count('{v}') for t, _ in _IS_RITE))
    g1_words, g2_words = nouns[:3], nouns[3:6]
    slot_n, slot_v = iter(nouns[6:]), iter(verbs)

    for rows, words, off in ((_IS_G1_ROWS, g1_words, -2), (_IS_G2_ROWS, g2_words, +2)):
        for r, w in zip(rows, words):
            lay(runs, r, _IS_REGISTER + off, w, 'ancient')   # the mis-set noun
            lay(runs, r, _IS_PLQ_COL, w, 'verdant')          # its plaque, west wall

    rite_texts = []
    for (template, col), r in zip(_IS_RITE, _IS_RITE_ROWS):
        text = template
        while '{v}' in text:
            text = text.replace('{v}', next(slot_v), 1)
        while '{n}' in text:
            text = text.replace('{n}', next(slot_n), 1)
        lay(runs, r, col, text, 'ancient')
        rite_texts.append(text)

    level = _Level(
        name='The Indentation Sanctum', seed=seed,
        rows=R, cols=C,
        cells=[''.join(_CELL_CODE[c] for c in row) for row in cells],
        spawn=(_IS_G1_ROWS[0], _IS_COL_S),               # atop gallery one
        exit=_IS_EXIT,
        char_runs=runs,
        entities=[{'kind': 'exit', 'at': [_IS_EXIT[0], _IS_EXIT[1]],
                   'edit_immune': True}],
        solution=_IS_ANSWER)

    dungeon = _fmt_build(level, par=_IS_PAR)
    room = dungeon.rooms[0]
    room._is_g1_words    = tuple(g1_words)
    room._is_g2_words    = tuple(g2_words)
    room._is_rite_texts  = tuple(rite_texts)
    room._is_register    = _IS_REGISTER
    room._is_bolts       = tuple(_IS_GATE_COL0 + i for i in range(_IS_TRIGGERS))
    return dungeon


# ── The Warden Scrivener (Act V boss) — "The Unfinished Manuscript" ───────────
# He has copied these halls for an age and finished nothing. The hall IS the
# page: margin glosses carved in the north and south borders, five alcoves of
# plain stone where he shelters (no sigils — the walls
# read as walls; alcoves are found by their GEOMETRY), and passage after
# passage he refuses to finish. Every ward is stamped THE SAME DISTANCE from
# its warden's alcove — three rows out into the page, under (or over) his
# niche, the Manifold's warden-behind-his-ward silhouette — and the player
# completes each with the act's own verbs before striking in the stagger
# (main._warden_scrivener_tick; the Manifold ward machine, JOIN-HARDENED).
#
# Six beats, hp 5 (the threshold is ungated):
#   0  i        THE THRESHOLD — the antechamber lintel carries a word in
#               stone; write it anywhere on the desk and the gate draws +
#               the hall's fog parts (stateless, brazier-ritual analog).
#   1  c{m}     WARD OF THE LIE — one wrong word mid-passage; the north
#               margin gloss remembers the true line.
#   2  R        WARD OF THE ROT (TIMED) — a corrupted stream; the mends
#               re-rot _WSC_W2_WINDOW keystrokes after the solve (the
#               Manifold R2 window — the game's R-pressure debut; the
#               Overwrite Halls stayed untimed to save the timer for this).
#   3  case     WARD OF THE VOICE — a passage taken down case-INVERTED with
#               a MIXED-case target ('Veil of Iron' shape): guu/gUU write
#               the wrong voice; only the toggle reads true.
#   4  J        WARD OF THE TORN PAGE — the line's second half stranded on
#               the row below; the south gloss shows the seam's breath.
#   5  =        WARD OF THE RULE (finale) — back west under his first-facing
#               alcove: the closing passage is a rite block (the Sanctum's
#               skeleton) laid at the hall's west edge (the block law's base
#               is the line extent's start, so the rite must LIVE at the
#               margin the law measures from); `=` rules the page in one
#               stroke. The act's capstone.
#
# JOIN-HARDENING (J and = are live all fight — NEW since the Manifold):
#   • every ward check is TEXT-derived (substring / law_column scans across
#     all rows) — no stored coordinates can go stale;
#   • re-manifest positions derive from the alcoves' GEOMETRY (a niche cell
#     walled on both sides with its back to the wall, scanned down the
#     alcove's own column — columns never shift; the structure rides row
#     shifts intact), and the stamps and chorus spawns are laid RELATIVE to
#     the derived alcove row;
#   • the block law ignores wall-embedded glyphs and apply_indent never
#     moves them (the _LAW_FLOORS cell-type filters);
#   • the seal is stone until the fall (the A-carve battery holds).
_WSC_ROWS, _WSC_COLS = 23, 70
_WSC_AXIS  = 11                         # the aisle — bolts face it
_WSC_SPAWN = (13, 3)
_WSC_LINTEL = (10, 3)                   # the threshold word, carved over the desk
_WSC_GATE   = (13, 13)                  # draws when the threshold word is written
_WSC_HALL_TOP, _WSC_HALL_BOT = 2, 20
_WSC_HALL_LO,  _WSC_HALL_HI  = 15, 65
_WSC_MARGIN_ROWS = (1, 21)              # sealed border rows wearing the glosses
# The columns encasing him stand SYMMETRIC across the hall: the
# three north alcoves cut the hall in quarters (27/40/53 about center 40),
# the two south alcoves cut it in thirds (32/48). The finale alcove is the
# westmost — the rite lives at the west margin (the law's base).
# A2 takes the west third, A4 the east: both south wards share row 16, and
# J appends at the row's END OF CONTENT — the torn upper half must be the
# row's EASTMOST tenant or the pulled-up word lands after the other ward's
# mended text (found live: 'wick keeps … deadline loam').
_WSC_ALCOVES = ((3, 40), (19, 32), (3, 53), (19, 48), (3, 27))
_WSC_SIDES   = (1, -1, 1, -1, 1)        # niche opens toward the aisle
_WSC_W2_WINDOW = 8                      # keystrokes from solve to strike
_WSC_SEAL  = (13, 66)                   # draws when the Scrivener falls
_WSC_EXIT  = (13, 67)
_WSC_HEART = (12, 68)
_WSC_CHEST = (14, 68)                   # the Whole Word (text_obj, Act VI preview)
_WSC_POCKET = tuple((r, c) for r in (12, 13, 14) for c in (67, 68))
_WSC_BUDGET = 300                       # relaxed (boss convention — no par; the
                                        # budget is the ink that bounds a grind)
_WSC_NOUNS = ('oath', 'rune', 'veil', 'lamp', 'gate', 'ash', 'fern', 'moss',
              'dust', 'iron', 'bell', 'loam', 'reed', 'tarn', 'kiln', 'wick')
_WSC_VERBS = ('binds', 'wards', 'mends', 'keeps', 'casts', 'hews', 'rules',
              'seals')
# Ward-1 passage row/col, and the later stamps as (alcove_dr, col) anchors —
# every ward sits three rows out from its alcove's niche (the rite, a 4-line
# passage, RUNS rows +4..+7 below A5 and at the hall's WEST margin, cols
# offset from the law base 15: true stations 0,+2,+2,0 → laid +2,0,+4,+2).
_WSC_W1 = (6, 34)
_WSC_STAMP_ANCHORS = {
    2: ((-3, 29),),                     # A2 niche row 19 → passage row 16
    3: ((+3, 50),),                     # A3 niche row 3  → passage row 6
    4: ((-3, 45), (-2, 45)),            # A4 niche row 19 → rows 16, 17 (EAST)
    5: ((+4, 17), (+5, 15), (+6, 19), (+7, 17)),   # A5 row 3 → rows 7..10
}
# Chorus goblins (plain 'g' — copies of NOTHING; echo-tagged goblins would
# wear the Warden's own W), as (alcove_dr, col) anchors like the
# stamps, on text-free rows (a goblin standing on a passage overlays its
# letters and blinds the search). They gutter on the stagger.
_WSC_SPAWNS = {4: ((-6, 45), (-7, 58)),
               5: ((+2, 35), (+8, 33), (+8, 50), (+9, 42))}


def build_dungeon_warden_scrivener(seed: int) -> Dungeon:
    """The Warden Scrivener (Act V boss): the Unfinished Manuscript. No new
    commands; no keystroke par; hp 5, one strike per stagger. See the section
    header for the six beats and the join-hardening."""
    rng = random.Random(seed)
    _load_vocab_tables()

    # Seeded words — ALL distinct (a stray repeat could break a ward early).
    # Ward 3's capitalized nouns must not START with 'w': its mended target is
    # the only CAPITALIZED floor text in the hall, and a floor 'W' collides
    # with the Warden's letter — /W would land the strike on the word and
    # x would eat it (found live, seed 42: 'Gate of Wick' → 'Gate of ick').
    nouns = rng.sample(_WSC_NOUNS, 9)
    while nouns[3][0] == 'w' or nouns[4][0] == 'w':
        nouns = rng.sample(_WSC_NOUNS, 9)
    verbs = rng.sample(_WSC_VERBS, 5)
    threshold = nouns[0]
    true1  = f'{nouns[1]} {verbs[0]} {nouns[2]}'      # the passage as it should read
    lie1   = f'{nouns[1]} {verbs[1]} {nouns[2]}'      # his lie, mid-sentence
    long8  = [w for w in _VOCAB_PLAIN_BY_LEN.get(8, ())
              if w.isalpha() and w.islower()]
    word2  = rng.choice(long8)                        # the stream the rot eats
    mid    = (len(word2) - 3) // 2
    rot_abc = [ch for ch in 'abcdefghijklmnopqrstuvwxyz' if ch not in word2]
    rot2   = ''.join(rng.sample(rot_abc, 3))
    word2_rotted = word2[:mid] + rot2 + word2[mid + 3:]
    target3 = f'{nouns[3].capitalize()} of {nouns[4].capitalize()}'
    wrong3  = target3.swapcase()                      # the whole voice inverted
    true4   = f'{nouns[5]} {verbs[2]} {nouns[6]}'     # the torn line, made whole
    torn4a  = f'{nouns[5]} {verbs[2]}'
    torn4b  = nouns[6]
    rite_texts = (f'rite {nouns[7]}:', f'{verbs[3]} {nouns[7]}',
                  f'{verbs[4]} {nouns[8]}', 'end')

    R, C = _WSC_ROWS, _WSC_COLS
    cells = [[CellType.WALL] * C for _ in range(R)]
    for r in range(11, 16):                                 # the antechamber desk
        for c in range(2, 13):
            cells[r][c] = CellType.FLOOR
    for r in range(_WSC_HALL_TOP, _WSC_HALL_BOT + 1):       # the great page
        for c in range(_WSC_HALL_LO, _WSC_HALL_HI + 1):
            cells[r][c] = CellType.FLOOR
    for k, (pr, pc) in enumerate(_WSC_ALCOVES):             # his alcoves — plain stone
        side = _WSC_SIDES[k]
        cells[pr][pc] = CellType.FLOOR
        cells[pr - side][pc] = CellType.WALL                # back wall
        cells[pr][pc - 1] = CellType.WALL
        cells[pr][pc + 1] = CellType.WALL
        cells[pr + side][pc] = CellType.WALL                # the bolt, shut
    for (r, c) in _WSC_POCKET:                              # treasure pocket
        cells[r][c] = CellType.FLOOR
    cells[_WSC_SEAL[0]][_WSC_SEAL[1]] = CellType.WALL       # behind its seal
    cells[_WSC_GATE[0]][_WSC_GATE[1] + 1] = CellType.FLOOR  # threshold into the hall
    cells[_WSC_GATE[0]][_WSC_GATE[1]] = CellType.WALL       # the gate, shut

    room = Room(room_type=RoomType.ENTRY, rows=R, cols=C)
    room.cells = cells
    room.seed  = seed
    room.search_glyph_entities = True

    # Fog: the whole page (margins and glosses included) until the threshold
    # ritual; each alcove until its stagger; the pocket until the fall.
    # Fog runs to the FULL east wall: the pocket cells keep their own fog set
    # (excluded here so the ritual's hall reveal never unfogs them), and no
    # gloss may poke past the veil (a gloss overflowing the fog's edge shows
    # its tail at level open).
    hall_fog = frozenset(
        (r, c) for r in range(1, 22) for c in range(14, _WSC_COLS - 1)
        if (r, c) not in _WSC_ALCOVES and (r, c) not in _WSC_POCKET)
    room._wsc_hall_fog   = hall_fog
    room._wsc_pocket_fog = frozenset(_WSC_POCKET)
    _lay_dark(room, _WSC_ALCOVES)
    _lay_dark(room, hall_fog)
    _lay_dark(room, _WSC_POCKET)
    # THE THRESHOLD, said as data: while the lintel's word stands on any floor
    # row, the gate is open and the great page's carvings are legible.
    from vimny.engine.world import Seal as _Seal
    room.seals = (*room.seals, _Seal(
        scope='anyrow', mode='contains', match=(threshold,),
        opens=(tuple(_WSC_GATE),),
        unveils=tuple(sorted(hall_fog)),
        message='The threshold word stands in fresh ink — the gate draws!'))

    def lay(row, col, text, kind):
        c = col
        for piece in text.split(' '):
            if piece:
                room.char_runs.append(CharRun(row, c, tuple(piece), kind))
            c += len(piece) + 1

    lay(*_WSC_LINTEL, threshold, 'verdant')                 # the threshold lintel
    # Margin glosses — the manuscript's marginalia, carved in the border rows
    # directly over/under their passages (wall-embedded: uncuttable, off the
    # floor scans, and invisible to the block law and the indent).
    lay(1, _WSC_W1[1], true1, 'verdant')                    # north: the true line
    lay(1, 50, target3, 'verdant')                          # north: the true voice
    lay(21, 29, word2, 'verdant')                           # south: the whole stream
    lay(21, 45, true4, 'verdant')                           # south: the whole line

    # Ward 1, stamped at build (the fight opens staged): his lie on the page,
    # three rows under his first alcove.
    lay(_WSC_W1[0], _WSC_W1[1], lie1, 'ancient')

    # Later stamps, laid by the tick at each re-manifest — rows RELATIVE to
    # the freshly derived alcove niche (join-proof).
    room._wsc_stamps = {
        2: ((word2_rotted, 'ancient'),),
        3: ((wrong3, 'ancient'),),
        4: ((torn4a, 'ancient'), (torn4b, 'ancient')),
        5: tuple((t, 'ancient') for t in rite_texts),
    }
    room._wsc_targets = {1: true1, 2: word2, 3: target3, 4: true4}
    room._wsc_rite    = rite_texts
    room._wsc_word2, room._wsc_rot2, room._wsc_rotmid = word2, rot2, mid
    room._wsc_threshold = threshold
    room._wsc_gate, room._wsc_seal = _WSC_GATE, _WSC_SEAL
    # See the Manifold: every shut stone that is really a door, banded.
    room.sealed_cells = {_WSC_GATE, _WSC_SEAL} | {
        (ar + (1 if ar < _WSC_AXIS else -1), ac) for (ar, ac) in _WSC_ALCOVES}

    # The Scrivener: edit_immune (every operator parries), five x-windows.
    room.entities.append(Entity(kind='warden', row=_WSC_ALCOVES[0][0],
                                col=_WSC_ALCOVES[0][1], hp=5, max_hp=5,
                                ai='', tag='scrivener', edit_immune=True))
    room.entities.append(Entity(kind='heart_container',
                                row=_WSC_HEART[0], col=_WSC_HEART[1]))
    room.entities.append(Entity(kind='chest_scroll',
                                row=_WSC_CHEST[0], col=_WSC_CHEST[1]))
    room.entities.append(Entity(kind='exit', row=_WSC_EXIT[0], col=_WSC_EXIT[1],
                                edit_immune=True))
    room.spawn_pos = _WSC_SPAWN
    room.exit_pos  = _WSC_EXIT

    room.rebuild_indexes()
    room.par    = None                   # boss: no keystroke par (1-star win)
    room.budget = _WSC_BUDGET
    room.answer = ''

    dungeon = Dungeon(name='The Warden Scrivener', seed=seed)
    dungeon.rooms        = [room]
    dungeon.current_room = 0
    return dungeon


# ── The Gauntlet (45: the everything-exam maze) ──────────────────────────────
#
# One continuous maze — every act folded into a single buffer, sixteen doors,
# one FINAL SEAL. Nothing is new; everything is asked at once. teaches: [] —
# an exam introduces nothing. Par is HAND-TALLIED along the canonical tape and pinned by the
# driven 2★ test; every door has a per-leg rival audit in its tests.
#
# THE ONE-MAZE LAWS (why the layout is what it is):
#  • Vertical reflow is buffer-global: the row-creating legs (Y-linewise-p,
#    O, o) live in the BOTTOM band; only sacrificial blanks and the gate lie
#    beneath them, and the tick derives its gate row from exit_pos each tick
#    (rides _shift_rows — the Joiner's Gate hardening).
#  • Buffer-wide motions span the whole maze: every drawn word is globally
#    unique AND no search word (S1/T1/U1/W7) is a substring of any other
#    floor token (the distinct-draw loop enforces both).
#  • State is sequenced by the route, not by seals: /-before-n (register),
#    stamp-before-dot (gU then .), yank-AFTER-every-delete (the # trip to
#    the W7 word happens once d/D/C/S are done, so nothing clobbers it).
#
# THE POCKET ISLANDS (the search band's forcing): P1 and P2 are floor islands
# in MISTED WATER with no walking access at all — the only way in or out is
# a search jump (Vim-true: a text jump crosses any terrain). Water bars
# feet, the permanent water bars the $ / 0 / ^ / f scans, and a spine ◆ on
# each pocket row catches {n}G (fnb would otherwise be the island text).
# Everything stays VISIBLE per the stone-fog law — no fog-audit opt-out.
# The motion rival is infinite; / n * # are forced absolutely.
#
# DOOR LEDGER — 18 doors, canonical key(s) · rival that loses:
#   r1  e-door     k 3e x       spawn is the row BELOW (k opens the exam);
#                               16l x (4) / fλ;;;x (6)              [sub]
#   r2  b/w-door   j b x b x    the descent lands past BOTH intruders, so
#                               two bare b's take them back-to-front;
#                               2b x w x (+1) / F;x / fλ x           [sub]
#   r3  %-door     j % l x      11l x (4) / f;;x (5) / $ gE gE (4)  [sub]
#   r4  (-door     j ( x        the descent lands on the row's final '.';
#                               ( reaches back to the intruded sentence's
#                               start — b b x (+1) / Fλ x (+1)       [sub]
#   P1  r-door     /S1 2e rC    motions: IMPOSSIBLE (water island); s ties
#                               r — the Vim-intrinsic tie, accepted
#   P2  ~-door     n w ~~       fU ~~ (4) — w beats f by 1; R-retype (3>2)
#   P3  gU·3e ×3   * 3b gU3e    ONE operator stroke raises all three names
#                               (the count rides the motion, Vim-true);
#                               gUe w . w . (+3), count-~ per door worse
#   —   cit-door   + cit{cure} <<   + steps down from the gU gallery onto
#                               the row's fnb = the '<' (j parks on blank
#                               floor at TX where cit resolves nothing);
#                               the row stands one shift out of true and
#                               the door is COLUMN-checked — << ends it
#   —   d-door     j ^ dw       11x (3) / count-x pays the run length [row]
#   —   D-door     j w D        d$ (+1) / dw dw (+2)                  [row]
#   —   C-door     j C{cure}    c$ (+1) / D a (+1) — D parks the cursor on
#                               the first wrong word (text laid at col 23)
#   —   S-door     j S{word}    ^C (+1) / cc (+1) — park is mid-row
#   —   y-door     j b # w yiw N qb e l p q w @b   the exam's macro leg
#                  (post-reorder: q@ precedes it): recording is FREE and
#                  the replay is 2, so the taped fill (6) beats the long-
#                  hand e l p w e l p (7); the yank word lives on the
#                  SEARCH SHELF over the water band — # (off the U1
#                  anchor) or / is the only door, and the nook U1 decoy
#                  makes a wrapping * lose to # by 1; N (not n) rides
#                  home — after # the register runs backward         [sub]
#   —   Y-door     j Y p        yy p (+1); retype-with-spaces ≫      [dup]
#   —   o doors    o{w1} o{w2}  the verse lines DON'T exist — o authors
#                  them below the pasted pair (O ties o intrinsically: the
#                  same edit read from the other bank; the exam keeps o)
#   —   finale     G $ h        the ◆ east of the exit catches $; h steps
#                               back onto the frame — nothing is cheaper
_GNT_ROWS, _GNT_COLS = 27, 78
_GNT_SPINE = 24                     # the descent rail — every row's first standable
_GNT_TX    = 26                     # text column 0 for most rows
_GNT_PLQ_COL = 1                    # west-wall plaques (cols 1..22 — wide enough
                                    # for every door's FULL reading; see below)
# The SEARCH SHELF (row 1) hangs above the exam behind a full band of
# sunken water (row 2): the yank word and the # twin live there, walkable
# by nothing — a search jump is the only door (the early-stroll yank died
# with the shelf; the return N prices out every fnb-jump ferry).
_GNT_R_BLK, _GNT_R_WTR = 1, 2                     # the shelf + its water band
_GNT_R_E, _GNT_R_BW, _GNT_R_PCT, _GNT_R_SEN = 3, 4, 5, 6   # spawn is R_BW; k → R_E
_GNT_R_BLANK = 7
_GNT_R_P1, _GNT_R_P2, _GNT_R_P3 = 8, 10, 12       # 9/11 are spine-only wall rows
_GNT_R_CIT, _GNT_R_D, _GNT_R_DD = 13, 14, 15      # + steps P3 → cit (fnb = the tag)
_GNT_R_C, _GNT_R_S, _GNT_R_Y1, _GNT_R_YL = 16, 17, 18, 19
_GNT_R_NOOK = 21                                  # the decoy's SOUTHERN ISLAND —
                                                  # water rows 20/22 flank it, so
                                                  # its text heads at TX (the
                                                  # left-align law) with no walk-in
_GNT_R_GATE = 23
_GNT_P1_COLS = (26, 35)             # floor island in sunken water (search-only;
_GNT_P2_COLS = (26, 39)             # text at TX — the left-align law — with a
                                    # one-cell sunken gap east of the spine ◆)
_GNT_NOOK_COLS = (26, 28)           # decoy nook island (a search LANDING)
_GNT_BOLT0 = 27                     # 18 bolts, cols 27..44
_GNT_EXIT  = (_GNT_R_GATE, 46)      # the FINAL SEAL — stone until every proof holds
_GNT_CATCH = 47                     # ◆ east of the exit: $ lands here, h steps back
_GNT_PAR    = 94                    # the canonical tape spends EXACTLY this (probed:
                                    # par 93 drops the driven run to 1★)
_GNT_BUDGET = 140                   # hand-set generous: ~10 insert doors invite typos


def _gnt_draw_words(rng) -> dict:
    """The Gauntlet's vocabulary. Globally distinct, pairwise non-substring
    (a search word inside another token would corrupt the / n * # chains),
    with the initial-sharing groups the f/F decoys need."""
    _load_vocab_tables()

    def pool(length, initial=None):
        ws = [w for w in _VOCAB_PLAIN_BY_LEN.get(length, ())
              if w.isalpha() and w == w.lower()]
        if initial:
            ws = [w for w in ws if w[0] == initial]
        return ws

    for _ in range(200):
        picks: list = []

        def draw(length, initial=None):
            ws = [w for w in pool(length, initial) if w not in picks]
            if not ws:
                raise IndexError
            w = rng.choice(ws)
            picks.append(w)
            return w

        try:
            lam1 = rng.choice('bcdfgmprst')
            lam2 = rng.choice([c for c in 'bcdfgmprst' if c != lam1])
            lam3 = rng.choice([c for c in 'bcdfgmprst' if c not in (lam1, lam2)])
            lam4 = rng.choice([c for c in 'bcdfgmprst' if c not in (lam1, lam2, lam3)])
            d = {
                't1': draw(5, lam1), 't2': draw(5, lam1), 't3': draw(4, lam1),
                't4': draw(4), 'lam1': lam1,
                'v1': draw(4), 'v2': draw(4, lam2), 'v3': draw(4, lam2),
                'v4': draw(4), 'lam2': lam2,
                'u1': draw(4), 'u3': draw(4, lam3),
                'u4': draw(4, lam3), 'u5': draw(4), 'lam3': lam3,
                'a1': draw(4, lam4), 'a2': draw(4), 'a3': draw(4, lam4),
                'a4': draw(4), 'lam4': lam4,
                'ywd': draw(5), 's1': draw(3), 't1s': draw(3), 'u1s': draw(3),
                'rcure': draw(6), 'cw': draw(6),
                'g1': draw(5), 'g2': draw(7), 'g3': draw(4),
                'tn': draw(3), 'ti': draw(6), 'tc': draw(4),
                'dword': draw(5), 'd2': draw(4), 'd3': draw(4),
                'dhead': draw(5), 'dt1': draw(4), 'dt2': draw(4),
                'chead': draw(5), 'cw1': draw(4), 'cw2': draw(4), 'ccure': draw(4),
                'sw1': draw(4), 'sw2': draw(5), 'sword': draw(4),
                'ymid': draw(3),
                'yl1': draw(4), 'yl2': draw(4), 'yl3': draw(4),
                'ow1': draw(4), 'ow2': draw(4),
            }
        except IndexError:
            continue
        # the r-door's wrong letter: distinct from everything near its seek
        wletters = [c for c in 'kqjzxv'
                    if c not in d['s1'] + d['rcure'] and c != lam1]
        if not wletters:
            continue
        d['wl'] = rng.choice(wletters)
        # global no-substring: a search word inside any other floor token
        # (including the rot forms actually laid) breaks the / n * # chains.
        rots = [d['t3'][:4] + lam1, lam2 + d['v2'], lam2 + d['v3'],
                lam4 + d['a3'],
                d['rcure'][:5] + d['wl'],
                d['cw'][:2].upper() + d['cw'][2:]]
        tokens = [w for k, w in d.items() if k not in
                  ('lam1', 'lam2', 'lam3', 'lam4', 'wl')] + rots
        # No-substring where it GATES: the search words (chain corruption)
        # and every single-word sub-door target (a nested copy would pre-open
        # its door). Multi-word targets are context-protected by their
        # spaces; row-kind doors compare exact.
        critical = [d[k] for k in ('s1', 't1s', 'u1s', 'ywd', 'rcure', 'cw',
                                   'g1', 'g2', 'g3', 'sword', 'ow1', 'ow2')]
        ok = len(set(tokens)) == len(tokens)
        if ok:
            for a in critical:
                for b in tokens:
                    if a != b and a in b:
                        ok = False
                        break
                if not ok:
                    break
        if ok:
            return d
    raise ValueError('gauntlet: no clean draw after 200 tries')


def build_dungeon_gauntlet(seed: int) -> Dungeon:
    """The Gauntlet (slug `gauntlet`): the everything-exam. One maze, sixteen
    doors, one seal — every act's verbs asked in a single descent. See the
    section header for the door ledger and the one-maze laws."""
    rng = random.Random(seed ^ 0x6AC7)
    w = _gnt_draw_words(rng)
    R, C, SP, TX = _GNT_ROWS, _GNT_COLS, _GNT_SPINE, _GNT_TX
    cells = [[CellType.WALL] * C for _ in range(R)]

    def floor(r, c0, c1):
        for c in range(c0, c1 + 1):
            cells[r][c] = CellType.FLOOR

    # the search shelf (row 1) over its water band, the open descent
    # (galleries rows 3-6), the blank, the pocket channels, then the lower
    # band — the spine (col 24) threads rows 3..gate.
    floor(_GNT_R_BLK, TX, 62)                       # the shelf: search-only
    floor(_GNT_R_BLK, SP, SP)                       # …its ◆ threshold cell
    for r in (_GNT_R_E, _GNT_R_BW, _GNT_R_PCT, _GNT_R_SEN):
        floor(r, SP, 62)
    floor(_GNT_R_BLANK, SP, SP)                     # the spine steps through —
                                                    # the rest is moat (below):
                                                    # the islands now head at TX,
                                                    # so their CEILING must bar
                                                    # the walk-in from above
    floor(_GNT_R_P1, *_GNT_P1_COLS)                 # island 1
    floor(_GNT_R_P2, *_GNT_P2_COLS)                 # island 2
    for r in (_GNT_R_P1, _GNT_R_P2):
        cells[r][SP] = CellType.FLOOR               # the ◆ threshold cells
    # (the between-pocket rows hold NO stepping cell: a spine cell there
    # let + + hop island → island → gallery, riding each row's fnb — the
    # cheese; the courses are pure water now)
    # The lower band's floor starts at TX, not the spine: S / o / O drop
    # their typed lines at the SEGMENT START, so the segment must start
    # where the text stands — the left-align law (every playable line
    # heads at TX, mirroring the plaque column line for line).
    for r in (_GNT_R_P3, _GNT_R_CIT, _GNT_R_D, _GNT_R_DD, _GNT_R_C,
              _GNT_R_S, _GNT_R_Y1, _GNT_R_YL):
        floor(r, TX, 62)
    floor(_GNT_R_P3, SP, SP)           # the gU gallery's ◆ threshold cell:
                                       # without it, {12}G ferries straight
                                       # onto g1 and undercuts w * 3b
    # The nook: a SOUTHERN ISLAND for the U1 decoy (a search LANDING —
    # escaped the way you came in), its text at TX per the left-align
    # law. Full water rows flank it above and below, so nothing walks in
    # from the yline row or on to the gate — the gate stays reachable
    # ONLY by jump (G/L), and the finale forces G.
    floor(_GNT_R_NOOK, *_GNT_NOOK_COLS)
    floor(_GNT_R_GATE, SP, _GNT_CATCH)
    # THE WATERWORKS (stone-fog law, the waypoint pattern): the pockets and
    # the nook sit in MISTED WATER, not stone — everything stays VISIBLE
    # (the vision flood crosses water; underwater renders as haze), while the
    # islands stay search-only: water bars feet, the water on it bars the
    # $ / 0 / ^ / f scans, } { skip flooded rows, and a match starting on
    # water is no landing. Mist is permanent (underwater_cells — reveals skip it).
    underwater: set = set()

    def moat(r, c0, c1):
        for c in range(c0, c1 + 1):
            cells[r][c] = CellType.WATER
            underwater.add((r, c))

    moat(_GNT_R_WTR, SP, 62)                        # the shelf's water band
    moat(_GNT_R_BLK, SP + 1, SP + 1)                # the shelf threshold's gap
    moat(_GNT_R_P3, SP + 1, SP + 1)                 # the gallery threshold's gap
    moat(_GNT_R_BLANK, SP + 1, 62)                  # the pocket moat (ceiling)
    moat(_GNT_R_P1, SP + 1, _GNT_P1_COLS[0] - 1)    # west channel to island 1
    moat(_GNT_R_P1, _GNT_P1_COLS[1] + 1, 76)        # …and its east water
    moat(_GNT_R_P2, SP + 1, _GNT_P2_COLS[0] - 1)    # west channel to island 2
    moat(_GNT_R_P2, _GNT_P2_COLS[1] + 1, 76)        # …and its east water
    # The between-pocket courses are water too (not stone), east of the
    # spine's stepping cells — and the lower one is the SIGHT-line into
    # the lower band (its floor heads at TX with no spine entry): vision
    # floods through water, feet do not.
    moat(_GNT_R_P1 + 1, SP, 76)
    moat(_GNT_R_P2 + 1, SP, 76)
    moat(_GNT_R_NOOK - 1, SP, 62)                   # the island's north water
    moat(_GNT_R_NOOK, SP, _GNT_NOOK_COLS[0] - 1)    # …its west channel
    moat(_GNT_R_NOOK, _GNT_NOOK_COLS[1] + 1, 62)    # …its east water
    moat(_GNT_R_NOOK + 1, SP, 62)                   # …and its south water
    for i in range(18):                             # the eighteen bolts
        cells[_GNT_R_GATE][_GNT_BOLT0 + i] = CellType.WALL
    cells[_GNT_EXIT[0]][_GNT_EXIT[1]] = CellType.WALL   # the FINAL SEAL

    from vimny.engine.editor import _CELL_CODE
    from vimny.sharing import format as _fmt
    from vimny.sharing.format import Level as _Level, build as _fmt_build

    runs: list = []

    def lay(r, c, text, kind='ancient'):
        col = c
        for part in text.split(' '):
            if part:
                runs.append({'row': r, 'col': col,
                             'symbols': part, 'kind': kind})
            col += len(part) + 1

    # The sixteen-plus-two bolts ride the file as Seals — the same shapes the
    # forge arms (see _gauntlet_tick's history): sub → contains-anyrow, row →
    # exact-anyrow, dup → the SAME target twice (distinct-row law: one verse
    # is the source, not a proof), col → head=_GNT_TX (the left-align law).
    # Every bolt anchors to the exit row, so o/O/Y-p drag bolts and exit home
    # together. Messages are engine-only and re-attach post-build.
    seals = []
    _bolt_msg = 'A proof holds — a bolt grinds back!'

    def door(kind, target):
        col = _GNT_BOLT0 + len(seals)
        common = dict(scope='anyrow', anchor='exit_row',
                      opens=((_GNT_EXIT[0], col),))
        if kind == 'sub':
            seals.append(Seal(match=target, mode='contains', **common))
        elif kind == 'row':
            seals.append(Seal(match=target, mode='exact', **common))
        elif kind == 'dup':
            seals.append(Seal(match=(target, target), mode='exact', **common))
        else:                                    # 'col' — the margin IS part
            seals.append(Seal(match=target, mode='exact', head=_GNT_TX,
                              **common))

    # r1 · e-door: t3 wears an extra letter (the shared initial) at its tail.
    lay(_GNT_R_E, TX, f"{w['t1']} {w['t2']} {w['t3'][:4]}{w['lam1']} {w['t4']}")
    door('sub', f"{w['t1']} {w['t2']} {w['t3']} {w['t4']}")
    # r2 · b/w-door: two intruder initials, one behind and one ahead.
    lay(_GNT_R_BW, TX, f"{w['v1']} {w['lam2']}{w['v2']} {w['lam2']}{w['v3']} {w['v4']}")
    door('sub', f"{w['v1']} {w['v2']} {w['v3']} {w['v4']}")
    # r3 · %-door: the intruder hides fused to the closing bracket; the
    # whole corrected line fits its plaque (the wall-is-the-goal law).
    lay(_GNT_R_PCT, TX, f"{w['u1']} ({w['u3']} {w['u4']}){w['lam3']} {w['u5']}")
    door('sub', f"({w['u3']} {w['u4']}) {w['u5']}")
    # r4 · (-door: the second sentence begins with a letter that is not its
    # own. The FIRST sentence is a single word, so the intruded sentence
    # runs long and the descent lands a full word east of the intruder —
    # ( reaches its start in one stroke where b b overpays (a shorter
    # second sentence let ONE b tie the paren — the round-5 audit).
    lay(_GNT_R_SEN, TX, f"{w['a1']}. "
                        f"{w['lam4']}{w['a3']} {w['a4']} {w['a2']}.")
    # target reaches back over the first sentence's period: the intruder is
    # a PREFIX, so a shorter target would already read true around it.
    door('sub', f"{w['a1']}. {w['a3']} {w['a4']} {w['a2']}.")
    # r1 · the search shelf: U1 (the # twin) with the yank word beside it,
    # and the T1 decoy that sits BEHIND P2 so a # there lands wrong. The
    # shelf hangs over the water band — search is its only door, so the
    # yank word cannot be strolled to in advance.
    lay(_GNT_R_BLK, TX, f"{w['u1s']} {w['ywd']} {w['t1s']}")
    # P1 · r-door (sealed): the cure's last letter went wrong.
    lay(_GNT_R_P1, _GNT_P1_COLS[0], f"{w['s1']} {w['rcure'][:5]}{w['wl']}")
    door('sub', w['rcure'])
    # P2 · ~-door (sealed): the first two letters stand in the wrong case.
    lay(_GNT_R_P2, _GNT_P2_COLS[0],
        f"{w['s1']} {w['cw'][:2].upper()}{w['cw'][2:]} {w['t1s']}")
    door('sub', w['cw'])
    # P3 · the gU gallery: three lowered names of three lengths — the dot
    # amortizes gUe past count-~ only because there are THREE.
    lay(_GNT_R_P3, TX, f"{w['g1']} {w['g2']} {w['g3']} {w['t1s']}")
    for g in ('g1', 'g2', 'g3'):
        door('sub', w[g].upper())
    # r13 · cit-door: the named case holds the wrong fitting — and the row
    # stands ONE SHIFT (2 cols) out of true. + from the gU gallery lands
    # on the row's fnb = the '<' (j parks on blank floor at TX, where cit
    # resolves nothing — no forward seek, the GMS brace lesson), and the
    # door is COLUMN-checked: after cit mends the fitting, << draws the
    # line home to TX (the left-align law is diegetic here).
    lay(_GNT_R_CIT, TX + 2, f"<{w['tn']}>{w['ti']}</{w['tn']}>")
    door('col', f"<{w['tn']}>{w['tc']}</{w['tn']}>")
    # r14 · d-door (M's landing): eleven dead marks squat before the verse.
    lay(_GNT_R_D, TX, f"{'◆' * 11} {w['dword']} {w['d2']} {w['d3']}")
    door('row', f"{w['dword']} {w['d2']} {w['d3']}")
    # r15 · D-door: the head is true; everything after it is rot.
    lay(_GNT_R_DD, TX, f"{w['dhead']} {w['dt1']} {w['dt2']}")
    door('row', w['dhead'])
    # r14 · C-door: the tail is wrong from the second word on. chead is a
    # FIVE-letter word so the row heads at TX (the left-align law) while
    # the D-door's park (dhead is five too) still drops exactly onto the
    # first wrong word — C from there keeps the head and its space.
    lay(_GNT_R_C, TX, f"{w['chead']} {w['cw1']} {w['cw2']}")
    door('sub', f"{w['chead']} {w['ccure']}")
    # r17 · S-door: wrong on both sides of where the cursor arrives.
    lay(_GNT_R_S, TX, f"{w['sw1']} {w['sw2']}")
    door('sub', w['sword'])
    # r18 · y-door: two empty settings off the U1 anchor; the shelf word
    # fills both (the # trip). Each setting is a TWO-blank gap: the paste
    # shoves the tail east, turning ' <Space>' into ' word ' — so the finished
    # line reads with single spaces and IS its plaque.
    runs.append({'row': _GNT_R_Y1, 'col': TX,
                 'symbols': w['u1s'], 'kind': 'ancient'})
    runs.append({'row': _GNT_R_Y1, 'col': TX + 5,
                 'symbols': w['ymid'], 'kind': 'ancient'})
    door('sub', f"{w['u1s']} {w['ywd']} {w['ymid']} {w['ywd']}")
    # r19 · Y-door: the line must stand TWICE (Y p — the dup door).
    _yline = f"{w['yl1']} {w['yl2']} {w['yl3']}"
    lay(_GNT_R_YL, TX, _yline)
    door('dup', _yline)
    # The two verse doors: the lines DON'T EXIST until o authors them
    # below the pasted pair (there are no rune scaffold courses — o from the
    # row above always ties O from the row below, the same edit read from
    # either bank, and such courses would be the only lines the wall did not
    # show). COLUMN-checked so a verse scattered elsewhere
    # off-TX reads false.
    door('col', w['ow1'])
    door('col', w['ow2'])
    # The FINAL SEAL: the exit itself, behind every bolt (stone until the
    # whole exam reads true).
    seals.append(Seal(anchor='exit_row', opens=(_GNT_EXIT,),
                      requires=tuple(range(len(seals))),
                      message='Sixteen proofs stand together — the last seal parts!'))
    # the nook island: the U1 forward decoy (a wrapping * lands here and
    # loses to # by one). r23 · the gate: threshold ◆ (G parks west of the
    # bolts — the GMS lesson) and the catch ◆ east of the seal ($ lands
    # there; h steps back onto the frame).
    lay(_GNT_R_NOOK, _GNT_NOOK_COLS[0], w['u1s'])
    runs.append({'row': _GNT_R_GATE, 'col': SP + 1,
                 'symbols': '◆', 'kind': 'ancient'})
    runs.append({'row': _GNT_R_GATE, 'col': _GNT_CATCH,
                 'symbols': '◆', 'kind': 'ancient'})
    # Threshold ◆ on every search-band row's spine cell (the shelf, both
    # pockets, the gU gallery): {n}G / H / gg / + / - land on a row's
    # FIRST NON-BLANK, which would otherwise be the row's text — a
    # two-key ferry past the search-only law. The ◆ catches the jump on
    # a one-cell ledge with water east (w stops at the bank); search
    # remains the only useful door.
    for pr in (_GNT_R_BLK, _GNT_R_P1, _GNT_R_P2, _GNT_R_P3):
        runs.append({'row': pr, 'col': SP, 'symbols': '◆', 'kind': 'ancient'})

    # West-wall plaques: each door's FULL true reading on its own row (the
    # law — a partial cure word would make the player guess the rest).
    # Substring doors read the FLOOR only, and a match starting in stone is
    # no search landing, so the plaques can carry the whole target safely.
    # Two exceptions that cannot fit or would mislead: the y-door shows the
    # fill word TWICE (two empty settings, two copies), and the Y-door
    # shows the line that must stand twice.
    # Every plaque is its row's WHOLE finished line — navigation words
    # (s1 / t1s / u1s / the yank word) included, since they survive the
    # solve; the shelf and the nook keep their text too, so they read on
    # the wall. Only the rune courses carry no plaque.
    for pr, ptext in ((_GNT_R_BLK, f"{w['u1s']} {w['ywd']} {w['t1s']}"),
                      (_GNT_R_E, f"{w['t1']} {w['t2']} {w['t3']} {w['t4']}"),
                      (_GNT_R_BW, f"{w['v1']} {w['v2']} {w['v3']} {w['v4']}"),
                      (_GNT_R_PCT, f"{w['u1']} ({w['u3']} {w['u4']}) {w['u5']}"),
                      (_GNT_R_SEN, f"{w['a1']}. {w['a3']} {w['a4']} {w['a2']}."),
                      (_GNT_R_P1, f"{w['s1']} {w['rcure']}"),
                      (_GNT_R_P2, f"{w['s1']} {w['cw']} {w['t1s']}"),
                      (_GNT_R_P3, f"{w['g1'].upper()} {w['g2'].upper()} "
                                  f"{w['g3'].upper()} {w['t1s']}"),
                      (_GNT_R_CIT, f"<{w['tn']}>{w['tc']}</{w['tn']}>"),
                      (_GNT_R_D, f"{w['dword']} {w['d2']} {w['d3']}"),
                      (_GNT_R_DD, w['dhead']),
                      (_GNT_R_C, f"{w['chead']} {w['ccure']}"),
                      (_GNT_R_S, w['sword']),
                      (_GNT_R_Y1, f"{w['u1s']} {w['ywd']} {w['ymid']} "
                                  f"{w['ywd']}")):
        lay(pr, _GNT_PLQ_COL, ptext, 'verdant')
    # The GOAL COLUMN (the Y/o band): the west wall shows the FINISHED
    # manuscript — the yanked line TWICE (the dup door's instruction), the
    # two authored verses at the rows where they will be born, and the
    # nook's decoy word at the row where the nook will COME TO REST (the
    # inserts push its island down to anchor+5). Row inserts drag these plaques
    # out of true; _gauntlet_tick re-rights them to the yline-anchored
    # goal rows (the sculpting re-align, with its twinkle) so the wall
    # always paints the goal and the player edits until the columns agree.
    gnt_band = (_yline, w['ow1'], w['ow2'], w['u1s'])
    for pr, ptext in ((_GNT_R_YL, _yline), (_GNT_R_YL + 1, _yline),
                      (_GNT_R_YL + 2, w['ow1']), (_GNT_R_YL + 3, w['ow2']),
                      (_GNT_R_YL + 5, w['u1s'])):
        lay(pr, _GNT_PLQ_COL, ptext, 'verdant')

    def encode(r):
        return ''.join(_fmt._UNDERWATER_CODE if (r, c) in underwater else _CELL_CODE[ct]
                       for c, ct in enumerate(cells[r]))

    level = _Level(
        name='The Gauntlet', seed=seed,
        rows=R, cols=C,
        cells=[encode(r) for r in range(R)],
        spawn=(_GNT_R_BW, SP),                     # k opens the exam (row above)
        exit=_GNT_EXIT,
        char_runs=runs, seals=seals,
        entities=[{'kind': 'exit', 'at': [_GNT_EXIT[0], _GNT_EXIT[1]],
                   'edit_immune': True}],
        solution=(
            f"k 3e x j b x b x j % l x j ( x "
            f"/{w['s1']}<CR> 2e r{w['rcure'][5]} n w ~ ~ w * 3b gU3e "
            f"+ cit{w['tc']}<Esc> << j dw j w D j C{w['ccure']}<Esc> j S{w['sword']}<Esc> "
            f"j b # w yiw N qb e l p q w @b j Y p "
            f"o{w['ow1']}<Esc> o{w['ow2']}<Esc> G $ h"))

    dungeon = _fmt_build(level, par=_GNT_PAR)
    room = dungeon.rooms[0]
    room._gnt_band = gnt_band
    _seal_banners(dungeon, bolt=_bolt_msg,
                  final='Sixteen proofs stand together — the last seal parts!')
    return dungeon


# ── The Culling Ledger (display 40) — the ex-range family's first lesson ─────
# A stone ledger carved into the far face of a chasm: the player walks a
# reading gallery at the bottom and can NEVER stand on a ledger row — the
# text sits on MISTED floor (fog_cells ∩ underwater_cells: readable in full colour
# through the renderer's carved-through-water branch, but fog bars feet,
# match-landings, and cuts). Not one cell on a ledger row is passable, so
# every jump ferry ({n}G / G / H / M) simply FAILS — nothing to land on —
# and the ○ marker at each row's west lip is scenery: the chasm's warning.
# The ONLY hands long enough are the ranged ex commands: :{n}d, :{a},{b}d,
# and :{range}v//d. (Each row keeps ≥1 FLOOR cell so remove_row consents.)
# Blighted lines render EMBER, true lines VERDANT (the forge's colour law).
#
# The register lesson: the corridor holds a KEY CHEST, a
# LOCKED DOOR mid-way, and a second locked door before the exit. The key
# lives in the unnamed register (engine law), a :d clobbers it, and there
# is only one key — so every register-writing cull must go to the black
# hole (:d _, :v//d _; :g//d is Vim-faithfully register-writing too). The
# ledger starts DARK (fog without water): the UNSEEN-LINE LAW bars culling
# it blind, so the key must be fetched and door one opened FIRST, which
# parts the water (adds water to the fogged ledger — readable, still
# unwalkable). Verdant lines each carry a lit brazier at col 30; a cold
# one waits on the corridor: when the ledger reads true, the corridor
# brazier catches their fire and its light unveils the exit pocket (the
# second locked door still wants the key — mind what you cut). A key
# pasted onto the floor is swept away by the water (no stashing it past
# the culls). Blank residue rows are ignored by the check — the
# :s-blanking longhand stays a lawful 1★ route; forcing is by PAR.
_CL_ROWS, _CL_COLS = 24, 56
_CL_CATCH = 2                        # the ○ marker col on every ledger row
_CL_TX    = 5                        # carved text head col
_CL_SEP   = 20                       # misted-water course above the wall
_CL_WALL  = 21                       # stone course — solid but for the gap
_CL_GAP   = (21, 12)                 # the one gap column (east of door one)
_CL_COR   = 22                       # the corridor (player walk)
_CL_KEYCH = (_CL_COR, 4)             # the key chest
_CL_DOOR1 = (_CL_COR, 10)            # the first locked door
_CL_BRZ_COL = 30                     # braziers: lit on verdant rows, cold here
_CL_SEALDOOR = (_CL_COR, 31)         # the boss door: one cell east of the
                                     # brazier, dark until its fire answers
_CL_DOOR2 = (_CL_COR, 50)            # the last locked door, before the exit
_CL_EXIT  = (_CL_COR, 54)
_CL_CHEST = (_CL_COR, 52)
# Ledger rows (0-based; row 0 is border so GUTTER LINE N = ROW N — the ex
# address mapping follows the gutter). Stanza I 1-3 (blight 2) · gap 4 ·
# stanza II 5-10 (keep 5, blights 6-10 contiguous — the :{a},{b}d block) ·
# gap 11 · stanza III 12-19 interleaved (junk 12,14,16,17,19; sacred
# 13,15,18 — five scattered junk rows make :v//d beat five :{n}d singles
# by PAR: the best singles route, deleted bottom-up, spends 18 vs 13).
_CL_KEEP_ROWS   = (1, 3, 5)
_CL_BLIGHT_I    = 2
_CL_BLIGHT_II   = (6, 7, 8, 9, 10)
_CL_JUNK_III    = (12, 14, 16, 17, 19)
_CL_SACRED_III  = (13, 15, 18)
_CL_GAPS        = (4, 11)
_CL_PAR    = 23    # the wide cull: one :2,19v/that/d _
                   # keeps exactly the chain — engine-measured spend of the
                   # canonical tape below. The three-beat longhand
                   # (:2d :5,9d :6,13v) still wins, at 1★ (35 spent).
_CL_BUDGET = 60                      # generous: the :s-blanking longhand wins 1★
# THE HOUSE THAT JACK BUILT (public domain) — solution by sense, not decree:
# the true ledger is the cumulative chain, split at its clause seams, so its
# ORDER is known by heart; every stanza-III keep line begins with the
# chain-word "that" (the rhyme's own signature), so :v/that/d — keep what
# bears the chain, cull the rest — is READ off the page, not decreed. The
# intruders are whole OTHER nursery rhymes: one Humpty line squatting in
# stanza I, all of Little Miss Muffet as a contiguous block, and the rest
# of Humpty (plus a cheeky Jack-and-Jill) scattered through stanza III.
# None of them contains "that" — and the chain's HEAD ('This is the dog,')
# doesn't either, so the canonical wide cull ranges PAST it (:2,19v); the
# ranged :2d / :5,9d beats remain the three-beat 1★ longhand.
_CL_KEEPS = (
    'This is the dog,',                    # rows 1, 3, 5 — the chain's head
    'that worried the cat,',
    'that killed the rat,',
    'that ate the malt,',                  # rows 13, 15, 18 — every one
    'that lay in the house',               # bears the chain-word
    'that Jack built.',
)
_CL_BLIGHT_I_LINE = 'Humpty Dumpty sat on a wall,'
_CL_BLOCK = (                              # Little Miss Muffet, whole
    'Little Miss Muffet',
    'sat on a tuffet,',
    'eating her curds and whey;',
    'along came a spider,',
    'and frightened Miss Muffet away.',
)
_CL_JUNK = (                               # scattered through stanza III
    'Humpty Dumpty had a great fall.',
    "All the king's horses",
    "and all the king's men",
    "couldn't put Humpty together again.",
    'Jack and Jill went up the hill.',     # Jack, but not the chain
)


def build_dungeon_culling_ledger(seed: int) -> Dungeon:
    from vimny.engine.editor import _CELL_CODE
    from vimny.sharing.format import Level as _Level, build as _fmt_build
    R, C, TX = _CL_ROWS, _CL_COLS, _CL_TX

    cells = [[CellType.WALL] * C for _ in range(R)]
    for r in list(_CL_KEEP_ROWS) + [_CL_BLIGHT_I] + list(_CL_BLIGHT_II) \
             + list(_CL_JUNK_III) + list(_CL_SACRED_III):
        cells[r][_CL_CATCH] = CellType.FLOOR       # the ○ marker's floor cell
    # Water bands at the stanza gaps and above the stone course: they conduct
    # the vision flood between stanzas once revealed. Dark like everything
    # else until door one opens (_ledger_check runs the whole choreography —
    # reveals are event-driven, so the darkness holds on its own).
    for r in list(_CL_GAPS) + [_CL_SEP]:
        for c in range(2, 54):
            cells[r][c] = CellType.WATER
    cells[_CL_GAP[0]][_CL_GAP[1]] = CellType.FLOOR   # the one gap in the stone
    for c in range(2, 55):
        cells[_CL_COR][c] = CellType.FLOOR         # the corridor, door two's own
                                                    # cell (the ENTITY bars it —
                                                    # floor beneath, so an opened
                                                    # door is walkable)

    def carve(runs, r, text, kind):
        """Lay a ledger line: the ○ marker, then the words — floor cells that
        start DARK (the doors' opacity; _ledger_check adds the water when door
        one opens). Standable by no one either way: every jump ferry fails."""
        runs.append({'row': r, 'col': _CL_CATCH, 'symbols': '○', 'kind': 'void'})
        col = TX
        for wd in text.split(' '):
            runs.append({'row': r, 'col': col, 'symbols': wd, 'kind': kind})
            for c in range(col, col + len(wd)):
                cells[r][c] = CellType.FLOOR
            col += len(wd) + 1
        if kind == 'verdant':                      # a lit brazier keeps the line
            runs.append({'row': r, 'col': _CL_BRZ_COL, 'symbols': _QM_FLAME,
                         'kind': 'flame'})
            cells[r][_CL_BRZ_COL] = CellType.FLOOR

    runs: list = []
    for i, r in enumerate(_CL_KEEP_ROWS):          # the chain's head: dog,
        carve(runs, r, _CL_KEEPS[i], 'verdant')    # worried, killed
    carve(runs, _CL_BLIGHT_I, _CL_BLIGHT_I_LINE, 'ember')
    for i, r in enumerate(_CL_BLIGHT_II):          # all of Miss Muffet, whole
        carve(runs, r, _CL_BLOCK[i], 'ember')
    third = {r: ('verdant', _CL_KEEPS[3 + i])      # the chain's tail: every
             for i, r in enumerate(_CL_SACRED_III)}  # line bears "that"
    for i, r in enumerate(_CL_JUNK_III):
        third[r] = ('ember', _CL_JUNK[i])
    for r in sorted(third):
        kind, t = third[r]
        carve(runs, r, t, kind)

    # The cold brazier on the corridor — the finale lights it.
    runs.append({'row': _CL_COR, 'col': _CL_BRZ_COL,
                 'symbols': _QM_EMBERS, 'kind': 'pedestal'})

    level = _Level(
        name='The Culling Ledger', seed=seed,
        rows=R, cols=C,
        cells=[''.join(_CELL_CODE[c] for c in row) for row in cells],
        # The ledger starts UNDERWATER from turn one — readable but never
        # footing. No delayed veil; no darkness-adding tick.
        underwater=[(r, c) for r in range(1, _CL_SEP)
                    for c in range(1, C - 1)
                    if cells[r][c] == CellType.FLOOR],
        spawn=(_CL_COR, 2),
        exit=_CL_EXIT,
        char_runs=runs,
        entities=[
            {'kind': 'exit',         'at': [_CL_EXIT[0], _CL_EXIT[1]]},
            {'kind': 'chest_scroll', 'at': [_CL_CHEST[0], _CL_CHEST[1]]},
            {'kind': 'chest_key',    'at': [_CL_KEYCH[0], _CL_KEYCH[1]]},
            {'kind': 'locked_door',  'at': [_CL_DOOR1[0], _CL_DOOR1[1]],
             'opaque': True},
            # The boss door: one cell east of the cold brazier, dark until lit.
            {'kind': 'seal_door',    'at': [_CL_SEALDOOR[0], _CL_SEALDOOR[1]],
             'opaque': True},
            {'kind': 'locked_door',  'at': [_CL_DOOR2[0], _CL_DOOR2[1]],
             'opaque': True},
        ],
        solution=':set<Space>nu<CR> 2l x $ p :2,19v/that/d<Space>_<CR> $ p $')

    dungeon = _fmt_build(level, par=_CL_PAR)
    room = dungeon.rooms[0]
    room._ledger_keeps = _CL_KEEPS                 # the chain, in order
    room._ledger_lit = False                       # the corridor brazier, cold
    return dungeon


# ── The Shelving Room (display 41) — the movers: :m :t :> :< ─────────────────
# The Culling Ledger's chasm chassis, second lesson: the round was misfiled
# — one echo sits among the wrong pair, one sank a step too deep, and the
# last was never shelved at all. NO PLAQUE: the round
# is an echo — every voice sings twice, the echo a step deeper than its
# call — so the true shelf is known by SENSE; the shelf's own sound pairs
# show the convention. Each mended misfiling grinds back its own gallery
# bolt, IN ANY ORDER (`_SHR_BOLT_COLS`, sealed by per-line row_offset seals);
# the exit gate parts when the whole round reads true, indent included. No cell
# on a shelf row is passable (underwater floor band), so the only movers are
# the ranged ex commands: :m reorders, :t shelves the missing copy, :> :<
# set the depth. A fresh :t/:m row is born unfogged — the tick re-submerges
# ANY bare shelf floor each turn (the chasm law is stateless).
_SHR_ROWS, _SHR_COLS = 11, 72
_SHR_TX   = 30                       # shelf floor band head col
_SHR_BAND = (30, 66)                 # the sunken floor band on every shelf row
_SHR_WTR  = 8                        # the water course (sight-line + line 8's home)
_SHR_GAL  = 9                        # the reading gallery
_SHR_SEAL_COL  = 61
_SHR_CHEST_COL = 66
_SHR_EXIT_COL  = 70
# The four gallery bolts west of the seal — one per misfiling, orderless:
# voices in song order and paired · the Sonnez echo at its step · the last
# echo shelved · the last echo at its step.
_SHR_BOLT_COLS = (57, 58, 59, 60)
# FRÈRE JACQUES (traditional, public domain — the French original): an ECHO
# ROUND, so the shelf's order and duplication are known BY SENSE — every
# line is sung twice, the echo a step behind (and a step DEEP, the echo
# convention; the west-wall score confirms it for those who don't know the
# tune). The misfiling: the Dormez-vous echo shelved down among the wrong
# pair (:m), the Sonnez echo a step too deep (:<), and the last echo never
# shelved at all — :t copies the CALL, which lands flush, so the fresh echo
# needs :> at once: duplication and depth are one gesture.
_SHR_CALLS = ('Frère Jacques,', 'Dormez-vous?',
              'Sonnez les matines!', 'Ding, daing, dong.')
_SHR_INDENTS = (0, 2, 0, 2, 0, 2, 0, 2)           # call flush, echo a step deep
# Initial shelf rows 1..7: (text, indent).
_SHR_INIT = (
    ('Frère Jacques,', 0),
    ('Frère Jacques,', 2),
    ('Dormez-vous?', 0),
    ('Sonnez les matines!', 0),
    ('Sonnez les matines!', 4),                    # the echo, a step too deep
    ('Dormez-vous?', 2),                           # the stray echo (belongs at 4)
    ('Ding, daing, dong.', 0),                     # its echo never shelved
)
_SHR_PAR    = 15                     # :6m3(4) + :6<(3) + :7t7(4) + :8>(3) + $(1)
_SHR_BUDGET = 40                     # generous: the movers invite exploration


def build_dungeon_shelving_room(seed: int) -> Dungeon:
    from vimny.engine.editor import _CELL_CODE
    from vimny.sharing.format import (Level as _Level, build as _fmt_build,
                                      _parse_seal)
    R, C = _SHR_ROWS, _SHR_COLS
    targets = [(' ' * _SHR_INDENTS[i]) + _SHR_CALLS[i // 2] for i in range(8)]

    cells = [[CellType.WALL] * C for _ in range(R)]
    underwater: set = set()
    for r in range(1, 8):                          # the shelf band
        for c in range(*_SHR_BAND):
            cells[r][c] = CellType.FLOOR
            underwater.add((r, c))
    for c in range(_SHR_TX, _SHR_BAND[1] + 1):     # the water course (sight-line;
        cells[_SHR_WTR][c] = CellType.WATER        # cols west stay WALL so the
        underwater.add((_SHR_WTR, c))                    # 8th plaque line sits in stone)
    for c in range(_SHR_TX - 1, _SHR_SEAL_COL):
        cells[_SHR_GAL][c] = CellType.FLOOR        # the reading gallery (west of
    for c in range(_SHR_SEAL_COL + 1, _SHR_EXIT_COL + 1):    # the band is stone —
        cells[_SHR_GAL][c] = CellType.FLOOR        # nothing to walk there)
    for c in _SHR_BOLT_COLS:                       # the per-misfiling bolts
        cells[_SHR_GAL][c] = CellType.WALL
    # (_SHR_GAL, _SHR_SEAL_COL) stays WALL until the full-round seal opens it.

    def lay(runs, r, col, text, kind):
        for wd in text.split(' '):
            runs.append({'row': r, 'col': col, 'symbols': wd, 'kind': kind})
            col += len(wd) + 1

    runs: list = []
    for r, (text, ind) in enumerate(_SHR_INIT, start=1):   # the misfiled round
        lay(runs, r, _SHR_TX + ind, text, 'ancient')

    level = _Level(
        name='The Shelving Room', seed=seed,
        rows=R, cols=C,
        cells=[''.join(_CELL_CODE[c] for c in row) for row in cells],
        underwater=sorted(underwater | {(_SHR_GAL, c)
                            for c in range(_SHR_SEAL_COL + 1,
                                           _SHR_EXIT_COL + 1)}),
        spawn=(_SHR_GAL, _SHR_TX - 1),             # the sealed POCKET rides the
        exit=(_SHR_GAL, _SHR_EXIT_COL),            # water too: its darkness is
        char_runs=runs,                            # weather, not ignorance — one
        seals=[
            # EIGHT PER-LINE BOLTS: each pins its phrase at the exact column
            # and row relative to the first line. Read-only predicates —
            # _chasm_resubmerge maintains the gallery floor.
            # The char_run text has no leading spaces (indent is positional),
            # so per-line targets are lstrip'd.
            *[_parse_seal({'scope': 'anyrow', 'mode': 'exact',
                            'match': [targets[i].lstrip()],
                            'at': _SHR_TX + _SHR_INDENTS[i],
                            'row_offset': i},
                           i) for i in range(8)],
            # FOUR GALLERY BOLTS: each opens when its voice pair (call + echo)
            # is correctly placed.  `requires` chains to the per-line seals.
            # `anchor='exit_row'` so opens ride the live gallery row (which
            # shifts when :t inserts a buffer line).
            *[_parse_seal({'scope': 'anyrow', 'mode': 'exact', 'anchor': 'exit_row',
                            'match': [], 'opens': [[_SHR_GAL, dc]],
                            'requires': [2 * i, 2 * i + 1]},
                           8 + i)
              for i, dc in enumerate(_SHR_BOLT_COLS)],
            # THE FULL ROUND, said as data: every nonempty stripped line in
            _parse_seal({'scope': 'region', 'mode': 'lines', 'anchor': 'exit_row',
                         'region': [1, 2, 200, C - 2],
                         'match': [t.rstrip() for t in targets],
                         'opens': [[_SHR_GAL, _SHR_SEAL_COL]],
                         'unveils': [[_SHR_GAL, c] for c in
                                     range(_SHR_SEAL_COL + 1,
                                           _SHR_EXIT_COL + 1)],
                         'message': 'The round sings in order — the way opens!',
             }, 12),
        ],
        entities=[{'kind': 'exit', 'at': [_SHR_GAL, _SHR_EXIT_COL]},   # bolt
                  {'kind': 'chest_scroll', 'at': [_SHR_GAL, _SHR_CHEST_COL]}],
        solution=':set<Space>nu<CR> :6m3<CR> :6<<CR> :7t7<CR> :8><CR> $')

    dungeon = _fmt_build(level, par=_SHR_PAR)
    room = dungeon.rooms[0]
    room._shr_targets  = tuple(targets)
    # Band the shut gallery bolts + seal as stonework. Registered at build: the
    # gallery row and its bolt columns are fixed for the level's lifetime.
    # _base_sealed_cells preserves them across _seal_tick's rebuild.
    room._base_sealed_cells = {(_SHR_GAL, c)
                               for c in (*_SHR_BOLT_COLS, _SHR_SEAL_COL)}
    room.sealed_cells = set(room._base_sealed_cells)
    # The water (shelf band, water course, AND the sealed pocket) rides the
    # file; what stays a pin is the FOG arrangement: the pocket is hidden by
    # position behind a seal the scripted tick opens, and the level wants
    # exactly this darkness — no more, no less — than the stone law derives.
    pocket = {(_SHR_GAL, c) for c in range(_SHR_SEAL_COL + 1, _SHR_EXIT_COL + 1)}
    room.fog_cells = set(room.underwater_cells) | pocket
    return dungeon


# ── The Warden Eternal (FINAL BOSS) ──────────────────────────────────────────
# A vertical descent back through all six wardens the player has already
# beaten, then The Unmasking: the blessing-wizard is the Warden Eternal, the W
# glyph that was the clue all along. NOT par-forced (par=None, win = survival);
# the finale's horde is sized so a kill-macro (qa /g<CR> x q → @a) is the master's
# answer — the payoff of the Hall of Echoes.
_WDE_COLS    = 60
_WDE_SPINE   = 1                      # the descent column (open in every chamber)
_WDE_TEXT    = 4                      # west label head col
_WDE_BUDGET  = 400                    # roomy: the fight is unsequenced, unmetered

# Each chamber: (top_row, bot_row, band_row) — content rows then the stone band
# below with a passage cell at _WDE_SPINE that opens when the chamber is cleared.
_WDE_CHAMBERS = [
    (1,  3,  4),
    (5,  7,  8),
    (9,  11, 12),
    (13, 15, 16),
    (17, 19, 20),
    (21, 23, 24),
]
_WDE_FINALE_TOP = 25
_WDE_FINALE_BOT = 33
_WDE_ROWS       = 35                  # rows 0..34 (34 = bottom wall)
_WDE_SEAL_COL   = 57                  # the boss seal; the exit pocket lies east
_WDE_EXIT       = (29, 58)

# Per-chamber flavour + roster. Labels EVOKE each warden (never enumerate a
# command — the world-text law). rosters: (warden_hp or 0, goblin_count).
_WDE_CHAMBER_SPECS = [
    ("Here you first drew steel.",        0, 3),   # the Keep
    ("The eye that measured you, returns.", 3, 2), # the Surveyor
    ("The maze-maker, come round again.",  3, 3),  # the Pathfinder
    ("He who folded the halls.",           4, 3),  # the Manifold
    ("The hand that rewrote you.",         4, 4),  # the Scrivener
    ("The last teacher, unteaching.",      5, 4),  # the Grandmaster
]
# The wizard's parting verse, laid along the finale's west wall as he unmasks.
_WDE_FINALE_LABEL = "You knew my face. You never knew my name."


def build_dungeon_warden_eternal(seed: int) -> Dungeon:
    """The Warden Eternal (slug `warden_eternal`): the final boss. Six warden
    callbacks, then the Unmasking + the macro-forced horde. par=None."""
    rng = random.Random(seed ^ 0x3ADE)
    R, C = _WDE_ROWS, _WDE_COLS
    cells = [[CellType.WALL] * C for _ in range(R)]

    # Carve each chamber full-width floor; the band below stays solid WALL with
    # a single passage cell at the spine (opened by the tick when cleared).
    for (top, bot, band) in _WDE_CHAMBERS:
        for r in range(top, bot + 1):
            for c in range(1, C - 1):
                cells[r][c] = CellType.FLOOR
        # band row: solid wall (passage cell punched open later by the tick)

    # The finale hall: full-width floor, minus the sealed exit pocket east of
    # _WDE_SEAL_COL (reachable only when the Warden is unmade).
    for r in range(_WDE_FINALE_TOP, _WDE_FINALE_BOT + 1):
        for c in range(1, _WDE_SEAL_COL):
            cells[r][c] = CellType.FLOOR
    # the exit pocket (a lone standable cell behind the seal)
    cells[_WDE_EXIT[0]][_WDE_EXIT[1]] = CellType.FLOOR

    room = Room(room_type=RoomType.BOSS, rows=R, cols=C)
    room.cells     = cells
    room.seed      = seed
    room.spawn_pos = (_WDE_CHAMBERS[0][0], _WDE_SPINE)
    room.exit_pos  = _WDE_EXIT

    entities = []
    gates = []
    for i, (top, bot, band) in enumerate(_WDE_CHAMBERS):
        label, whp, gcount = _WDE_CHAMBER_SPECS[i]
        room.char_runs.append(CharRun(top, _WDE_TEXT, tuple(label), 'ancient'))
        # the returning warden (stationary, tagged so it neither chases nor
        # summons — a clean duel), then goblin minions that chase.
        mid = (top + bot) // 2
        placed = {(mid, C // 2)}
        if whp:
            entities.append(Entity(kind='warden', row=mid, col=C // 2,
                                   hp=whp, max_hp=whp, ai='', tag='eternal',
                                   edit_immune=True))
        for _ in range(gcount):
            for _try in range(30):
                gr = rng.randint(top, bot)
                gc = rng.randint(4, C - 3)
                if (gr, gc) not in placed:
                    placed.add((gr, gc))
                    entities.append(Entity(kind='goblin', row=gr, col=gc,
                                           hp=1, max_hp=1, ai='chase',
                                           ai_speed=1, tag='eternal'))
                    break
        gates.append({'band': band, 'col': _WDE_SPINE,
                      'rows': (top, bot), 'reveal': None})
    # reveal-range for each chamber below the first = its own content rows
    for i in range(1, len(gates)):
        gates[i]['reveal'] = _WDE_CHAMBERS[i]

    # ── The Unmasking: the wizard = the Warden Eternal = the W glyph ──────────
    room.char_runs.append(
        CharRun(_WDE_FINALE_TOP, _WDE_TEXT, tuple(_WDE_FINALE_LABEL), 'ancient'))
    boss = Entity(kind='warden', row=29, col=50, hp=6, max_hp=6, ai='',
                  tag='eternal_boss', edit_immune=True)
    entities.append(boss)
    # THE RANK — a wall of goblins drawn up STATIONARY on the boss's own row,
    # flanking him. They hold formation, so ONE line-cut fells them all: `0 d$`
    # (or D) shears the whole row charwise — the minions die, the shielded
    # Warden's ward turns the blade (no collapse; charwise d spares edit_immune).
    # This is the level's line-deletion lesson, distinct from the macro swarm.
    rank_cols = [c for c in range(_WDE_SEAL_COL - 14, _WDE_SEAL_COL) if c != 50]
    hplaced = {(29, 50), (29, 49)}
    for rc in rank_cols:
        entities.append(Entity(kind='goblin', row=29, col=rc, hp=1, max_hp=1,
                               ai='', tag='rank'))
        hplaced.add((29, rc))
    # the swarm — MOBILE goblins scattered across the hall (NOT the boss row),
    # sized so hand-killing is grind and a /g-x macro is the master's answer.
    for _ in range(18):
        for _try in range(60):
            gr = rng.randint(_WDE_FINALE_TOP, _WDE_FINALE_BOT)
            gc = rng.randint(3, _WDE_SEAL_COL - 2)
            if gr != 29 and (gr, gc) not in hplaced:
                hplaced.add((gr, gc))
                entities.append(Entity(kind='goblin', row=gr, col=gc, hp=1,
                                       max_hp=1, ai='chase', ai_speed=2,
                                       tag='horde'))
                break
    entities.append(Entity(kind='exit', row=_WDE_EXIT[0], col=_WDE_EXIT[1]))
    # The Warden's Rest — the epilogue scroll, waiting on the last stone before
    # the seal (looted with x on the way out, once the fight is won).
    entities.append(Entity(kind='chest_scroll', row=_WDE_EXIT[0],
                           col=_WDE_SEAL_COL - 1, scroll_id='wardens_rest'))

    room.entities = entities
    room.search_glyph_entities = True     # /g finds goblins, /W finds the Warden
    room._wde_gates   = gates
    room._wde_seal    = {'col': _WDE_SEAL_COL,
                         'rows': tuple(range(_WDE_FINALE_TOP, _WDE_FINALE_BOT + 1))}
    room._wde_boss_tag = 'eternal_boss'
    room._wde_hat_drop = (boss.row, boss.col)   # where the hat falls, on the exit path
    room._wde_revealed = False
    room.rebuild_indexes()
    apply_stone_fog(room)                 # each chamber sleeps until its gate opens
    room.par    = None                    # NOT par-forced — the victory lap
    room.budget = _WDE_BUDGET
    room.answer = ''                      # combat boss: no fixed karaoke route

    dungeon = Dungeon(name='The Warden Eternal', seed=seed)
    dungeon.rooms        = [room]
    dungeon.current_room = 0
    return dungeon
