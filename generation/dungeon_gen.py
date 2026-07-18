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
from engine.world import Dungeon, Room, RoomType, CellType, CharRun, Entity
from engine.motion import (_fog_unreachable, _cell_char, _is_word_char,
                           apply_stone_fog)
from generation.room_gen import make_room, RUNE_CHAR as _RUNE_CHAR

_DIR_CHAR = {(-1, 0): 'k', (1, 0): 'j', (0, -1): 'h', (0, 1): 'l'}
_DIRS = ((-1, 0), (1, 0), (0, -1), (0, 1))   # k j h l — the order every solver scans


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


def _dijkstra_par_count(composite) -> int | None:
    """Minimum keystroke cost entry→exit using count prefix.

    Cost model: 1 for a single step; len(str(n))+1 for a count-n move.
    Void rune cells are passable (CellType.FLOOR); a count motion passes
    through them and only the final landing cell triggers damage — matching
    engine behaviour in apply_motion.  Only true walls stop the search.
    """
    entry = composite.spawn_pos
    goal  = composite.exit_pos
    max_n = max(composite.rows, composite.cols)

    def neighbors(node):
        return _count_moves(composite.is_passable, node[0], node[1], max_n)

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
    rng = random.Random(seed)
    dungeon = Dungeon(name='The First Cave', seed=seed)
    CORRIDOR_LEN = 4

    plan = LEVEL_0_PLAN
    total_cols = sum(c for _, _, c in plan) + CORRIDOR_LEN * (len(plan) - 1)
    total_rows = max(r for _, r, _ in plan)

    # Build unified cell grid
    cells = [[CellType.WALL] * total_cols for _ in range(total_rows)]

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

    # Build a single composite room representing the dungeon floor
    composite = Room(room_type=RoomType.ENTRY, rows=total_rows, cols=total_cols)
    composite.cells = cells
    composite.seed  = seed

    # Entry: top-left interior of Room 0 → forces the player to use j (down)
    # to reach the corridor, and k (up) to reach the exit.
    composite.spawn_pos = (1, 2)

    # Exit: top-left interior of Room 2 (col offsets[-1]+1).
    # Player arrives at corridor rows 4-5 at the left edge of Room 2 and must
    # go UP (k) — but void guards at rows 2-3 block the straight-up path,
    # forcing a right detour then back left (h) to reach the exit.
    # This guarantees all four of h/j/k/l are required on every seed.
    exit_col_offset = offsets[-1]
    ex_c = exit_col_offset + 1   # = 47, leftmost interior col of Room 2
    composite.exit_pos = (1, ex_c)
    composite.entities.append(Entity(kind='exit', row=1, col=ex_c))

    # Greedily fill all three rooms (void runes included), then guarantee a route.
    composite.char_runs.clear()
    rune_rng = random.Random(rng.randint(0, 2**31))
    for i, (_, room_rows, room_cols) in enumerate(plan):
        _place_runes_in_room(composite, rune_rng, offsets[i],
                             room_rows, room_cols, total_rows)

    # Hard-coded void guards: block (2, ex_c) and (3, ex_c) so the player cannot
    # walk straight up from the corridor to the exit.  They must go right into
    # Room 2, up to row 1, then press h to reach the exit.  Remove any random
    # character that would shadow these hard-coded voids.
    for void_row in (2, 3):
        composite.char_runs = [
            ru for ru in composite.char_runs
            if not (ru.row == void_row
                    and ru.col <= ex_c < ru.col + len(ru.symbols))
        ]
    composite.char_runs.append(CharRun(row=2, col=ex_c, symbols=('○',), kind='void'))
    composite.char_runs.append(CharRun(row=3, col=ex_c, symbols=('○',), kind='void'))

    # Never leave a void rune sitting on the entry or exit itself.
    entry_r, entry_c = composite.spawn_pos
    exit_r,  exit_c  = composite.exit_pos
    composite.char_runs = [
        ru for ru in composite.char_runs
        if ru.kind != 'void' or not any(
            (ru.row == r and ru.col <= c < ru.col + len(ru.symbols))
            for r, c in ((entry_r, entry_c), (exit_r, exit_c))
        )
    ]

    # The greedy fill packs the cave with void; clear void off one floor route to
    # the exit (steered around the row-2/3 guards so the forced detour survives),
    # guaranteeing the level is solvable.
    _carve_void_path(composite, protected={(2, ex_c), (3, ex_c)})

    par, path = _bfs_par(composite, return_path=True)
    if par is None:
        par, path = 100, ''

    # Budget: ceil(par × 1.4) per spec formula.
    composite.par    = par
    composite.budget = math.ceil(par * 1.4)
    composite.answer = path

    composite.rebuild_indexes()
    dungeon.rooms = [composite]
    dungeon.current_room = 0
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
    dungeon = Dungeon(name='The Line Halls', seed=seed)
    ROWS, COLS = _LINE_HALLS_ROWS, _LINE_HALLS_COLS
    L, R = _LINE_HALLS_LEFT, _LINE_HALLS_RIGHT

    cells = [[CellType.WALL] * COLS for _ in range(ROWS)]
    for hall_row in (_LINE_HALLS_A_ROW, _LINE_HALLS_B_ROW, _LINE_HALLS_C_ROW):
        for c in range(L, R + 1):
            cells[hall_row][c] = CellType.FLOOR
    for (dr, dc) in _LINE_HALLS_DOORS:          # one-cell doorways through the wall rows
        cells[dr][dc] = CellType.CORRIDOR

    composite = Room(room_type=RoomType.ENTRY, rows=ROWS, cols=COLS)
    composite.cells     = cells
    composite.seed      = seed
    composite.spawn_pos = _LINE_HALLS_SPAWN
    composite.exit_pos  = _LINE_HALLS_EXIT
    composite.entities.append(
        Entity(kind='exit', row=_LINE_HALLS_EXIT[0], col=_LINE_HALLS_EXIT[1]))

    # ── Carved runes (random per seed, like the other levels) ───────────────────
    # The structural anchors (indents, the col-10 ^ target, the unmarked exit, the
    # blank approaches) are fixed so the forcing holds for every seed; only the
    # filler runes' kinds, lengths and gaps vary.
    rng = random.Random(seed)
    runs: list = []
    # Hall A: packed; col 1 is the spawn and cols R-1..R the doorway approach (left blank).
    runs += _tile_line_hall(rng, _LINE_HALLS_A_ROW, L + 1, R - 2)
    # Hall B: cols 1..8 blank, so 0 reaches the bare margin while ^ stops at col 9.
    runs += _tile_line_hall(rng, _LINE_HALLS_B_ROW, _LINE_HALLS_B_FIRST_RUNE_COL, R - 2)
    # Hall C: one single-cell non-void rune just left of the exit (the ^ target),
    # then a field of runes to its right so $ overshoots.  The exit cell stays unmarked.
    fr_r, fr_c = _LINE_HALLS_C_FIRST_RUNE
    fr_kind = rng.choice(_WORD_RUNE_KINDS)
    runs.append(CharRun(row=fr_r, col=fr_c, symbols=(_RUNE_CHAR[fr_kind],), kind=fr_kind))
    runs += _tile_line_hall(rng, _LINE_HALLS_C_ROW, _LINE_HALLS_EXIT[1] + 2, R - 2)
    composite.char_runs = runs

    composite.rebuild_indexes()
    par, path = _bfs_par_line(composite, return_path=True)
    composite.par    = par
    composite.budget = math.ceil(par * 1.4)
    composite.answer = path
    dungeon.rooms        = [composite]
    dungeon.current_room = 0
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
    rng = random.Random(seed)
    dungeon = Dungeon(name='The Counting Crypts', seed=seed)
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

    composite = Room(room_type=RoomType.ENTRY, rows=total_rows, cols=total_cols)
    composite.cells = cells
    composite.seed  = seed

    # Entry near top-left of Room 0 — player must navigate down+right to corridor
    composite.spawn_pos = (2, 2)

    # Exit near top-left interior of Room 2 — arrives via corridor then goes up
    ex_c = offsets[-1] + 1   # = 61
    ex_r = 2
    composite.exit_pos = (ex_r, ex_c)
    composite.entities.append(Entity(kind='exit', row=ex_r, col=ex_c))

    # Void wall in puzzle room: rows 2-(total_rows-3) at horizontal midpoint.
    # Gaps at row 1 and row (total_rows-2) are the only safe crossings.
    puzzle_mid_col = offsets[1] + plan[1][2] // 2   # = 40
    void_wall = [
        CharRun(row=row, col=puzzle_mid_col, symbols=('○',), kind='void')
        for row in range(2, total_rows - 2)          # rows 2-9
    ]

    # Decorative characters in entry and exit rooms; retry if any void blocks path.
    for _ in range(20):
        composite.char_runs = list(void_wall)
        rune_rng = random.Random(rng.randint(0, 2**31))
        _place_runes_in_room(composite, rune_rng, offsets[0],
                              plan[0][1], plan[0][2], total_rows, _WORD_RUNE_KINDS)
        _place_runes_in_room(composite, rune_rng, offsets[2],
                              plan[2][1], plan[2][2], total_rows, _WORD_RUNE_KINDS)

        # Never place a void rune on the entry or exit cell itself
        entry_r, entry_c = composite.spawn_pos
        exit_r,  exit_c  = composite.exit_pos
        composite.char_runs = [
            ru for ru in composite.char_runs
            if ru.kind != 'void' or not any(
                ru.row == r and ru.col <= c < ru.col + len(ru.symbols)
                for r, c in ((entry_r, entry_c), (exit_r, exit_c))
            )
        ]

        nav_par = _dijkstra_par_count(composite)
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
    for dc in door_cols:
        for row in (mid - 1, mid):
            composite.entities.append(Entity(kind='door', row=row, col=dc))

    # Full par: state-space Dijkstra with all Counting Crypts commands and door states.
    # Accounts for door-blocking (breaking $ into segments) and x keystrokes.
    composite.rebuild_indexes()
    composite.par, composite.answer = _par_counting_crypts(composite, door_cols, return_path=True)
    composite.budget = math.ceil(composite.par * 1.4)

    _fog_unreachable(composite, composite.spawn_pos[0], composite.spawn_pos[1])

    dungeon.rooms    = [composite]
    dungeon.current_room = 0
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
    rng     = random.Random(seed)
    dungeon = Dungeon(name='The Rune Halls', seed=seed)

    cells = [[CellType.WALL] * _RUNE_HALLS_TOTAL_COLS for _ in range(_RUNE_HALLS_TOTAL_ROWS)]

    composite = Room(room_type=RoomType.ENTRY,
                     rows=_RUNE_HALLS_TOTAL_ROWS, cols=_RUNE_HALLS_TOTAL_COLS)
    composite.cells = cells
    composite.seed  = seed

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
                cells[row][col] = CellType.CORRIDOR

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

    composite.spawn_pos    = (1, 1)
    composite.exit_pos = (13, 44)
    composite.entities = [Entity(kind='exit', row=13, col=44)]

    # ── Carve and populate character corridors (up to 20 attempts for valid par) ──
    for _attempt in range(20):
        # Hard-coded runes first so char_run_at() always finds them before random ones
        composite.char_runs = list(_rune_halls_hardcoded)
        rune_rng = random.Random(rng.randint(0, 2**31))

        for row_top in _RUNE_HALLS_CORR_TOP_ROWS:
            _make_rune_corridor(composite, rune_rng, row_top, blocked=blocked)

        composite.rebuild_indexes()
        par, path = _dijkstra_par_wbe(composite, return_path=True)
        if par is not None:
            break
    else:
        par, path = 80, ''

    composite.par    = par
    composite.budget = math.ceil(par * 1.4)
    composite.answer = path

    dungeon.rooms        = [composite]
    dungeon.current_room = 0
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
    ROWS, COLS = _CHARACTER_CATARACTS_TOTAL_ROWS, _CHARACTER_CATARACTS_TOTAL_COLS
    rng     = random.Random(seed)
    dungeon = Dungeon(name='The Character Cataracts', seed=seed)

    cells = [[CellType.WALL] * COLS for _ in range(ROWS)]
    composite = Room(room_type=RoomType.ENTRY, rows=ROWS, cols=COLS)
    composite.cells = cells
    composite.seed  = seed

    # ── Carve corridors (2 rows each) ─────────────────────────────────────────
    for row_top in _CHARACTER_CATARACTS_CORR_TOP_ROWS:
        for c in range(_CHARACTER_CATARACTS_CORR_LEFT, _CHARACTER_CATARACTS_CORR_RIGHT + 1):
            cells[row_top][c]     = CellType.CORRIDOR
            cells[row_top + 1][c] = CellType.CORRIDOR

    # ── Carve turn rooms ──────────────────────────────────────────────────────
    for r0, r1, ca, cb in _CHARACTER_CATARACTS_TURN_SPANS:
        c0, c1 = min(ca, cb), max(ca, cb)
        for row in range(r0, r1 + 1):
            for col in range(c0, c1 + 1):
                cells[row][col] = CellType.CORRIDOR

    # Floor cells widening the turn-room middle rows (matches saved reference layout)
    for r, c in ((3, 67), (3, 68),           # RT1 middle
                 (6, 1),  (6, 3), (6, 4),    # LT1 middle
                 (7, 17), (8, 17),            # C3 Zone A/water boundary
                 (9, 67), (9, 68)):           # RT2 middle
        cells[r][c] = CellType.FLOOR

    # ── Water pools ───────────────────────────────────────────────────────────
    for rows, cs, ce in _CHARACTER_CATARACTS_WATER_SPANS:
        for r in rows:
            for c in range(cs, ce + 1):
                cells[r][c] = CellType.WATER

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
    composite.entities = list(_fixed)
    composite.spawn_pos    = (1, 1)
    composite.exit_pos = (13, 65)

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

    for _attempt in range(20):
        composite.char_runs = list(_text_runes)
        rng2 = random.Random(rng.randint(0, 2**31))

        # Fill all corridor zones with standard characters
        _cataracts_place_zone(composite, rng2, (1, 2),    2,  13, blocked=blocked)  # C1 Zone A
        _cataracts_place_zone(composite, rng2, (1, 2),   38,  68, blocked=blocked)  # C1 Zone B
        _cataracts_place_zone(composite, rng2, (4,),      2,  28, blocked=blocked)  # C2 row 4 Zone A
        _cataracts_place_zone(composite, rng2, (4, 5),   52,  68, blocked=blocked)  # C2 Zone B
        _cataracts_place_zone(composite, rng2, (8,),      2,  16, blocked=blocked)  # C3 row 8 Zone A
        _cataracts_place_zone(composite, rng2, (8,),     32,  70, blocked=blocked)  # C3 row 8 Zone B
        _cataracts_place_zone(composite, rng2, (10, 11),  2,  24, blocked=blocked)  # C4 Zone A
        _cataracts_place_zone(composite, rng2, (10, 11), 52,  68, blocked=blocked)  # C4 Zone B
        # C5: dense character corridor for w/b/e practice; chest at col 20, exit anchor at col 64-65
        _cataracts_place_zone(composite, rng2, (13, 14),  2,  63, blocked=blocked)

        composite.rebuild_indexes()
        par, path = _dijkstra_par_ftFT(composite, return_path=True)
        if par is not None:
            break
    else:
        par, path = 80, ''

    composite.par    = par
    composite.budget = math.ceil(par * 1.4)
    composite.answer = path

    dungeon.rooms        = [composite]
    dungeon.current_room = 0
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
    """Ornamental friezes with the masons' discipline (playtest 2026-07-17):
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
    cut, which main.py's _check_seal_broken detects, opening composite.seal_door.
    """
    rng = random.Random(seed)
    dungeon = Dungeon(name='The Reliquary', seed=seed)
    ROWS, COLS = _RELIQUARY_ROWS, _RELIQUARY_COLS
    W, ar = _RELIQUARY_WALL_COL, _RELIQUARY_ACTION_ROW

    cells = [[CellType.WALL] * COLS for _ in range(ROWS)]
    # Two floor chambers (rows 1..ROWS-2) split by the dividing wall at col W.
    for r in range(1, ROWS - 1):
        for c in range(1, W):
            cells[r][c] = CellType.FLOOR          # left approach chamber
        for c in range(W + 1, COLS - 1):
            cells[r][c] = CellType.FLOOR          # right sanctum
    # col W stays WALL top-to-bottom; the doorway at (ar, W) opens on seal-break.

    composite = Room(room_type=RoomType.ENTRY, rows=ROWS, cols=COLS)
    composite.cells     = cells
    composite.seed      = seed
    composite.spawn_pos = _RELIQUARY_SPAWN
    composite.exit_pos  = _RELIQUARY_EXIT
    composite.seal_door = (ar, W)                 # opened by _check_seal_broken

    composite.entities = [
        Entity(kind='chest_scroll', row=_RELIQUARY_CHEST[0], col=_RELIQUARY_CHEST[1]),
        Entity(kind='exit',         row=_RELIQUARY_EXIT[0],  col=_RELIQUARY_EXIT[1]),
    ]

    # The seal: a Latin ward-word in ember, right-aligned against the dividing
    # wall on the action row — the ONLY CharRun on that row (so its absence
    # signals a broken seal).
    word     = rng.choice(_RELIQUARY_SEAL_WORDS)
    seal_col = W - len(word)
    composite.char_runs = [
        CharRun(row=ar, col=seal_col, symbols=tuple(word), kind='ember'),
    ]
    # Ornamental friezes (randomized per seed) line both chambers — never the
    # action row, so they can't be mistaken for the seal.
    _place_frieze_sym(composite, rng, _RELIQUARY_FRIEZE_ROWS, 1, W - 1)  # approach
    for fr in _RELIQUARY_FRIEZE_ROWS:
        _place_frieze(composite, rng, fr, W + 1, COLS - 2)     # right sanctum

    composite.par    = None
    composite.budget = 35
    composite.answer = _reliquary_answer(word)

    # The sanctum sleeps under fog until the seal breaks (playtest 2026-07-17:
    # the divider hid nothing — the relic and exit were visible from spawn).
    # Standard reachability fog; _check_seal_broken lifts it with the ward.
    _fog_unreachable(composite, *composite.spawn_pos)

    composite.rebuild_indexes()
    dungeon.rooms        = [composite]
    dungeon.current_room = 0
    return dungeon


def build_dungeon_dummy(seed: int) -> Dungeon:
    """Admin editing sandbox — all editable element types, plus two fog-walled rooms.

    Layout (rows 1-18):
      Main room   cols 1-41  — open area with all entity/cell/character types
      Wall divider col 42    — doorway at rows 9-10 (regular door)
      Room A      cols 43-57 — water pool; accessed by opening the door
      Wall divider col 58    — doorway at rows 9-10 (locked door)
      Room B      cols 59-78 — contains the exit; accessed with a key
    """
    ROWS, COLS = 20, 80
    dungeon = Dungeon(name='Dummy Dungeon', seed=seed)
    cells   = [[CellType.WALL] * COLS for _ in range(ROWS)]

    # Main room floor
    for r in range(1, ROWS - 1):
        for c in range(1, 42):
            cells[r][c] = CellType.FLOOR

    # Room A floor
    for r in range(1, ROWS - 1):
        for c in range(43, 58):
            cells[r][c] = CellType.FLOOR

    # Room B floor
    for r in range(1, ROWS - 1):
        for c in range(59, COLS - 1):
            cells[r][c] = CellType.FLOOR

    # Doorways carved into the dividing walls
    cells[9][42]  = CellType.FLOOR   # regular door opening (top)
    cells[10][42] = CellType.FLOOR   # regular door opening (bottom)
    cells[9][58]  = CellType.FLOOR   # locked door opening (top)
    cells[10][58] = CellType.FLOOR   # locked door opening (bottom)

    # Wood wall block in main room: rows 4-12 cols 7-21; row 8 is shorter
    for r in range(4, 13):
        end_c = 14 if r == 8 else 22
        for c in range(7, end_c):
            cells[r][c] = CellType.WOOD_WALL

    # Demo corridor strip in main room
    for c in range(25, 36):
        cells[9][c] = CellType.CORRIDOR

    # Reflow water demo (row 13, clear of the wood-wall block): a 2-cell puddle
    cells[13][9]  = CellType.WATER
    cells[13][10] = CellType.WATER

    # Water pool in Room A
    for r in range(11, 17):
        for c in range(44, 57):
            cells[r][c] = CellType.WATER

    composite = Room(room_type=RoomType.ENTRY, rows=ROWS, cols=COLS)
    composite.cells = cells
    composite.seed  = seed

    composite.spawn_pos    = (1, 1)
    composite.exit_pos = (9, 70)

    composite.entities = [
        Entity(kind='entry_marker', row=1,  col=1),
        Entity(kind='dynamite',     row=8,  col=14),
        Entity(kind='wanderer',     row=3,  col=35),
        # Chests in main room
        Entity(kind='chest',        row=3,  col=25),
        Entity(kind='chest_key',    row=4,  col=25),
        Entity(kind='chest_scroll', row=5,  col=25),
        # Combat entities
        Entity(kind='warden', row=4,  col=50, hp=5, max_hp=5, ai='',      summon_timer=0),
        Entity(kind='goblin', row=17, col=3,  hp=1, max_hp=1, ai='chase', ai_speed=1),
        Entity(kind='goblin',    row=13, col=11, hp=1, max_hp=1, ai=''),  # reflow water-wave: drowns
        Entity(kind='floor_key', row=13, col=12),                        # reflow water-wave: swept away (lost)
        # Room-divider door (fog boundary — opens into Room A)
        Entity(kind='door',         row=9,  col=42),
        Entity(kind='door',         row=10, col=42),
        # Room-divider locked door (fog boundary — opens into Room B)
        Entity(kind='locked_door',  row=9,  col=58),
        Entity(kind='locked_door',  row=10, col=58),
        # Exit at the far end of Room B
        Entity(kind='exit',         row=9,  col=70),
    ]

    composite.char_runs = [
        CharRun(row=2, col=3,  symbols=('∘',), kind='ancient'),
        CharRun(row=2, col=8,  symbols=('·',), kind='verdant'),
        CharRun(row=2, col=13, symbols=('○',), kind='void'),
        CharRun(row=2, col=17, symbols=('⊙',), kind='ember'),
        # ── Reflow pilot (engine/reflow.py): on a ledge row, editing flows and
        # content falls against the FIXED brinks — walls and void runes alike.
        # Three demos of the one law:
        # Row 13 — WATER WAVE: shove the 'WAVE' glyphs into the puddle (cols 9-10);
        # the wave rolls right and SWEEPS AWAY whatever it reaches — the goblin
        # (col 11) drowns, the key (col 12) is lost.
        CharRun(row=13, col=5,  symbols=tuple('WAVE'),   kind='verdant'),
        # Row 14 — VOID MARGIN: the ○○○ brink (col 35) sits on floor, so the cursor
        # can step onto it and FALL IN; glyphs past the brink tumble into the void.
        CharRun(row=14, col=29, symbols=tuple('GLYPHS'), kind='ancient'),
        CharRun(row=14, col=35, symbols=('○',) * 7,      kind='void'),
        # Row 16 — WALL EDGE: the corridor just ends at the stone wall (col 42). The
        # cursor CLAMPS at the last floor cell; glyphs tipped against the wall fall off.
        CharRun(row=16, col=38, symbols=tuple('EDGE'),   kind='ember'),
    ]

    composite.par            = None
    composite.budget         = 99999
    composite.passable_walls = False
    composite.rebuild_indexes()
    _fog_unreachable(composite, composite.spawn_pos[0], composite.spawn_pos[1])
    dungeon.rooms        = [composite]
    dungeon.current_room = 0
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
        runes.append(CharRun(row=row, col=c,
                                 symbols=tuple(word), kind=kind))
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
    dungeon = Dungeon(name='The Goblin Gauntlet', seed=seed)

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

    composite = Room(room_type=RoomType.ENTRY, rows=_GOBLIN_GAUNTLET_ROWS, cols=_GOBLIN_GAUNTLET_COLS)
    composite.cells    = cells
    composite.seed     = seed
    composite.spawn_pos    = (1, 1)
    composite.exit_pos = (18, 56)

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
            entities.append(Entity(kind='goblin', row=row, col=gc,
                                   hp=1, max_hp=1, ai='chase', ai_speed=2))

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
            entities.append(Entity(kind='door', row=row, col=c))
    for row in _GOBLIN_GAUNTLET_LEFT_CONN_ROWS:
        for c in _GOBLIN_GAUNTLET_LC_COLS:
            entities.append(Entity(kind='door', row=row, col=c))

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
        entities.append(Entity(kind='goblin', row=17, col=gc,
                               hp=1, max_hp=1, ai='chase', ai_speed=2))

    # Gate doors at col 53 (rows 17 and 18) + exit
    entities.append(Entity(kind='locked_door', row=17, col=53))
    entities.append(Entity(kind='locked_door', row=18, col=53))
    entities.append(Entity(kind='exit', row=18, col=56))

    composite.entities = entities
    composite.char_runs    = runes

    par = _par_goblin_gauntlet(corr_data, gobs17)
    composite.par    = par
    composite.budget = math.ceil(par * 1.4)
    composite.answer = _answer_l5(corr_data, gobs17)

    composite.rebuild_indexes()
    _fog_unreachable(composite, composite.spawn_pos[0], composite.spawn_pos[1])

    dungeon.rooms        = [composite]
    dungeon.current_room = 0
    return dungeon


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

    composite = Room(room_type=RoomType.COMBAT, rows=ROWS, cols=COLS)
    composite.cells    = cells
    composite.seed     = seed
    composite.spawn_pos    = (3, 0)
    composite.exit_pos = (3, 39)
    composite.entities = [
        Entity(kind='seal_door',       row=3, col=16),
        Entity(kind='shield',          row=3, col=26),
        Entity(kind='warden',          row=3, col=27, hp=5, max_hp=5, ai='',
               summon_timer=0),
        Entity(kind='locked_door',     row=3, col=38),   # opened with the key the Warden drops
        Entity(kind='exit',            row=3, col=39),
        Entity(kind='heart_container', row=2, col=41),
        Entity(kind='chest_scroll',    row=4, col=41),
    ]
    composite.rebuild_indexes()
    _fog_unreachable(composite, 3, 0)

    composite.par    = None
    composite.budget = math.ceil(_par_wardens_keep() * 1.4)

    dungeon = Dungeon(name="The Warden's Keep", seed=seed)
    dungeon.rooms        = [composite]
    dungeon.current_room = 0
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
# wired in main.py next. Here the warden is a plain 5-HP boss tagged 'surveyor'
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
    _fog_unreachable(composite, _WS_SPAWN[0], _WS_SPAWN[1])

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

    State = (row, col).  Cost model follows _keystroke_cost in main.py:
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

    # ── cluster-level motions matching engine/motion.py ──────────────────────

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
    dungeon   = Dungeon(name='The Backward Vaults', seed=seed)
    ROWS, COLS = _BACKWARD_VAULTS_TOTAL_ROWS, _BACKWARD_VAULTS_TOTAL_COLS

    cells = [[CellType.WALL] * COLS for _ in range(ROWS)]
    composite = Room(rows=ROWS, cols=COLS, room_type=RoomType.ENTRY)
    composite.cells = cells
    composite.seed  = seed

    # ── Carve corridors ───────────────────────────────────────────────────────
    for r in _BACKWARD_VAULTS_CORR_ROWS:
        for c in range(_BACKWARD_VAULTS_CORR_LEFT, _BACKWARD_VAULTS_CORR_RIGHT + 1):
            cells[r][c] = CellType.CORRIDOR

    # ── Carve turn spans ──────────────────────────────────────────────────────
    for r0, r1, c0, c1 in _BACKWARD_VAULTS_TURN_SPANS:
        for r in range(r0, r1 + 1):
            for c in range(c0, c1 + 1):
                cells[r][c] = CellType.CORRIDOR

    # ── Narrow-turn guard walls ────────────────────────────────────────────────
    # RT1 (rows 1-3, cols 36-38): block col 38 at row 2 so $ from C1 cannot
    # descend through the turn's far column — player must use 4e to land at
    # col 36 before descending.
    cells[2][38] = CellType.WALL
    # LT1 (rows 3-5, cols 1-3): block col 1 at row 4 so 0 from C2 cannot
    # descend at the turn's near column — player must use ^ to land at col 2.
    cells[4][1]  = CellType.WALL

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

    runes: list = []

    # C1 (row 1) — e-teaching: four 3-char clusters, individual characters
    for col, kind in ((5,'ancient'), (13,'verdant'), (22,'ember'), (34,'ancient')):
        runes.append(CharRun(row=1, col=col,
                                  symbols=(_sym(), _sym(), _sym()), kind=kind))

    # C2 (row 3) — b-teaching: four 3-char clusters, individual characters
    for col, kind in ((2,'ember'), (13,'verdant'), (21,'ancient'), (29,'ember')):
        runes.append(CharRun(row=3, col=col,
                                  symbols=(_sym(), _sym(), _sym()), kind=kind))

    # C3 (row 5) — decorative plain words (cols 4-35, safe of LT1/RT2 turns)
    c3c = 4
    while c3c <= 33:
        length = rng.randint(3, min(6, 35 - c3c + 1))
        if length < 3:
            break
        runes.append(CharRun(row=5, col=c3c,
                                  symbols=tuple(_plain_word(length)),
                                  kind=rng.choice(('ancient','verdant','ember'))))
        c3c += length + rng.randint(1, 3)

    # C4 (row 7) — ge anchor: 4-char ALL-WC plain word at col 2 (end=5 lands in LT2 gap).
    # Must be all word-chars (alpha/digit/_): b from col 38 then goes to col 2 (the run
    # start), which is walled in row 8 — forcing ge/gE over b to reach the LT2 gap.
    # A mixed anchor (e.g. 'win⚑') would let b land at col 5 in 1 ks, beating gE.
    _c4_pool = [w for w in (plain.get(4) or plain[3])
                if all(c.isalpha() or c.isdigit() or c == '_' for c in w)]
    runes.append(CharRun(row=7, col=2,
                              symbols=tuple(rng.choice(_c4_pool or ['proc'])),
                              kind='ancient'))

    # C5 (row 9) — decorative mixed words (cols 7-36, safe of LT2/RT3 turns)
    c5c = 7
    while c5c <= 34:
        length = rng.randint(3, min(6, 36 - c5c + 1))
        if length < 3:
            break
        runes.append(CharRun(row=9, col=c5c,
                                  symbols=tuple(_mixed_word(length)),
                                  kind=rng.choice(('ancient','verdant','ember'))))
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
    runes.append(CharRun(row=11, col=21,
                             symbols=tuple('b4¶♯∘m3†'), kind=_bb_kind))  # A: cols 21-28
    runes.append(CharRun(row=11, col=29,
                             symbols=('!', '='), kind=_bb_kind))          # S: cols 29-30
    runes.append(CharRun(row=11, col=31,
                             symbols=tuple('b3♯3m∘†♯'), kind=_bb_kind))  # B: cols 31-38

    # Anchor: 2-char cluster ending at col 19; col 20 always empty
    runes.append(CharRun(row=11, col=18,
                             symbols=(_sym(), _sym()), kind=rng.choice(_kinds3)))

    # Seed-randomized mixed filler in cols 2-16
    _c6c = 2
    while _c6c <= 16:
        _flen = rng.randint(1, max(1, min(3, 17 - _c6c)))
        runes.append(CharRun(row=11, col=_c6c,
                                 symbols=tuple(_sym() for _ in range(_flen)),
                                 kind=rng.choice(_kinds3)))
        _c6c += _flen + rng.randint(1, 2)

    composite.char_runs = runes

    composite.spawn_pos    = (1, 1)
    composite.exit_pos = (12, 19)
    composite.entities = [Entity(kind='exit', row=12, col=19)]

    composite.rebuild_indexes()
    par, path = _par_backward_vaults(composite, return_path=True)
    if par is None:
        par, path = 20, '4E 2j ^ 2j $ 2j ge 2j $ 2j gE j'
    composite.par    = par
    composite.budget = math.ceil(par * 1.4)
    composite.answer = path
    dungeon.rooms        = [composite]
    dungeon.current_room = 0
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
    _load_vocab_tables()
    rng     = random.Random(seed)
    # Pick 4 distinct untypable chars: first two → W4 anchor, last two → B1 anchor.
    _four   = rng.sample(_WORD_FORGE_UNTYPABLE_PUNCT, 4)
    _anchor_W = ''.join(_four[:2])   # W4 at (1, 53-54)
    _anchor_B = ''.join(_four[2:])   # B1 at (4,  3-4)
    dungeon = Dungeon(name='The WORD Forge', seed=seed)
    ROWS, COLS = _WORD_FORGE_TOTAL_ROWS, _WORD_FORGE_TOTAL_COLS

    cells = [[CellType.WALL] * COLS for _ in range(ROWS)]
    composite = Room(room_type=RoomType.ENTRY, rows=ROWS, cols=COLS)
    composite.cells = cells
    composite.seed  = seed

    # ── Carve corridors (2 rows each) ─────────────────────────────────────────
    for row_top in _WORD_FORGE_CORR_TOP_ROWS:
        for c in range(_WORD_FORGE_CORR_LEFT, _WORD_FORGE_CORR_RIGHT + 1):
            cells[row_top][c]     = CellType.CORRIDOR
            cells[row_top + 1][c] = CellType.CORRIDOR

    # ── Carve turn rooms ─────────────────────────────────────────────────────
    for r0, r1, c0, c1 in _WORD_FORGE_TURN_SPANS:
        for row in range(r0, r1 + 1):
            for col in range(c0, c1 + 1):
                cells[row][col] = CellType.CORRIDOR

    # ── Guard walls (replace the old void guards) ─────────────────────────────
    # RT1: wall the right two descent columns so the C1→C2 turn only exists at
    # col 53 — exactly where W lands (E lands at col 54, into a wall). Forces W.
    cells[3][54] = CellType.WALL
    cells[3][55] = CellType.WALL
    # LT1: wall the col-1 descent so 0/^ to col 1 can't drop into C3; the turn
    # routes through col 3 where B lands. Forces B over 0/^.
    cells[6][1] = CellType.WALL

    # ── Entry and exit ────────────────────────────────────────────────────────
    composite.spawn_pos    = (1, 1)
    composite.exit_pos = (7, 51)   # last char of C3 code group "output=data[n]._key"
    composite.entities = [Entity(kind='exit', row=7, col=51)]

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

    # ── Blocked cell set (code text + exit — filler must not overlap) ──────────
    _bl: set = {(7, 51)}
    for ru in _hardcoded:
        for i in range(len(ru.symbols)):
            _bl.add((ru.row, ru.col + i))
    blocked = frozenset(_bl)

    # ── Random filler character runs (secondary rows only; primary rows fixed) ──
    for _attempt in range(20):
        composite.char_runs = list(_hardcoded)
        rng2 = random.Random(rng.randint(0, 2**31))

        _l7_fill_row(composite, rng2, 2,  3, 52, density=0.45, blocked=blocked, word_tbl=_VOCAB_MIXED_BY_LEN)  # C1r2 baseline
        _l7_fill_row(composite, rng2, 5,  3, 52, density=0.45, blocked=blocked, word_tbl=_VOCAB_MIXED_BY_LEN)  # C2r5 baseline
        _l7_fill_row(composite, rng2, 8,  3, 52, density=0.45, blocked=blocked, word_tbl=_VOCAB_MIXED_BY_LEN)  # C3r8 baseline

        # Protect entry and exit from void runes
        entry_r, entry_c = composite.spawn_pos
        exit_r,  exit_c  = composite.exit_pos
        composite.char_runs = [
            ru for ru in composite.char_runs
            if ru.kind != 'void' or not any(
                ru.row == rr and ru.col <= cc < ru.col + len(ru.symbols)
                for rr, cc in ((entry_r, entry_c), (exit_r, exit_c))
            )
        ]

        composite.rebuild_indexes()
        par, path = _dijkstra_par_WBE(composite, return_path=True)
        if par is not None:
            break
    else:
        par, path = 40, ''

    composite.par    = par
    composite.budget = math.ceil(par * 1.4)
    composite.answer = path

    dungeon.rooms        = [composite]
    dungeon.current_room = 0
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
#     (the Seal chamber: v /{x}⏎ h d beats the eye-led v 2j t{x} d by one).
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
_SS_ROWS, _SS_COLS = 20, 30
_SS_SPINE  = 13                     # every row's first standable (the jump audit)
_SS_BAY_W  = 14                     # bay floor cols 14..28; east wall 29
_SS_BAY_E  = 28
_SS_PLQ_COL = 2                     # the full true readings, in the WEST wall
                                    # band (cols 2..11 — wide enough for the
                                    # Case chamber's two-word rows)
_SS_TEXT0  = 15                     # floor words start two east of the spine
_SS_SHAFT  = 19                     # the sight-line: a one-cell light shaft
                                    # through each bay separator at the anchor
                                    # column, so the plain j-hop (4j/3j) rides
                                    # straight from strike to next anchor (the
                                    # spine stays every row's first standable)
_SS_SHAFT_ROWS = (6, 10, 13)        # the bay separators it pierces
_SS_THROAT = 17                     # spine-only row joins the bays to the gate
_SS_GATE   = 18
_SS_BOLT0  = 14                     # bolts cols 14..17, one per chamber
_SS_EXIT   = (18, 18)               # the FINAL SEAL — stone until all read true
_SS_TAIL0  = 24                     # tail words sit at the row end, after 9 blight

# The canonical tape (hand-measured, driven — the buffer mutates, so no
# Dijkstra). The chambers are ANCHOR-ALIGNED at the shaft column: heads are
# exactly 4 letters, so `e l` lands the anchor and every op leaves the cursor
# where the next bay's plain j-hop lands on the next anchor — no {n}G / } /
# H-M-L golf can undercut the tape (the nav-golf audit, driven):
#   j e l   v 2j t{a} d    — Cut:   9   (cursor → the anchor)
#   4j      v 2j t{b} c s  — Word:  9   (post-Esc cursor → the anchor)
#   4j      v j e ~        — Case:  6   (cursor → selection start)
#   3j      v /{x}⏎ h d    — Seal:  7
#   G $                    — exit:  2
_SS_PAR = 33


def _ss_answer(words: dict) -> str:
    a = words['cut'][1][0]        # the Cut tail's initial (t{a})
    b = words['word'][1][0]       # the Word tail's initial (t{b})
    x = words['seal'][1][0]       # the Seal tail's pristine initial (/{x})
    return f'j e l v 2j t{a} d 4j v 2j t{b} c s 4j v j e ~ 3j v /{x}⏎ h d G $'


def _ss_draw_words(rng) -> dict:
    """Draw the chamber vocabulary. Slot LENGTHS are fixed (they pin par and
    the rival's count-~ costs); the words vary per seed. Constraints:
      • all words pairwise distinct, and the Word chamber's cure (stem+'s')
        distinct from everything;
      • the Seal tail's INITIAL appears in no other drawn word (nor in the
        typed 's') — the pristine search anchor, /{x}⏎ has one landing."""
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

        a_head, a_tail = draw(4), draw(4)     # Cut: head / tail
        stem,  b_tail  = draw(4), draw(4)     # Word: stem (+'s') / tail
        gw, w1 = draw(3), draw(5)             # Case: west guard · flipped word
        w2, ge = draw(6), draw(3)             # Case: flipped word · east guard
        s_head = draw(4)                      # Seal: head
        if len(set(picks + [stem + 's'])) != len(picks) + 1:
            continue                          # a collision — redraw everything
        used = set(''.join(picks)) | {'s'}
        cands = [w for w in pool(4) + pool(5)
                 if w[0] not in used and w not in picks]
        if not cands:
            continue
        s_tail = rng.choice(cands)            # Seal: the pristine-initial tail
        return {'cut': (a_head, a_tail), 'word': (stem, b_tail),
                'case': (gw, w1, w2, ge), 'seal': (s_head, s_tail)}
    raise ValueError('sight_sanctum: no pristine seal word after 80 draws')


def _ss_chambers(words: dict):
    """The chamber table for this seed: (name, bay rows, floor runs, door
    targets). Blight is '#'; two DECOYS of each t-target's initial sit in the
    rows the t-motion never scans (t is row-local; / is buffer-wide and pays
    an n per decoy — pricing out the lazy one-char search). Kept words live
    only at row EDGES: charwise multi-row middles are always consumed whole."""
    t0, an, tl = _SS_TEXT0, _SS_SHAFT, _SS_TAIL0
    a_head, a_tail = words['cut']
    stem,  b_tail  = words['word']
    gw, w1, w2, ge = words['case']
    s_head, s_tail = words['seal']
    a, b = a_tail[0], b_tail[0]
    return (
        # Cut (v 2j t{a} d): head at row start, tail at row end, full middle
        ('cut',  (3, 4, 5),
         ((3, t0, a_head), (3, an, f'##{a}###{a}###'),
          (4, t0, f'#####{a}###{a}####'),
          (5, t0, '#' * 9), (5, tl, a_tail)),
         (a_head, a_tail)),
        # Word (v 2j t{b} c s): kept head stem, the cure is TYPED — stem+'s'.
        # The 4-letter head puts the anchor ON the shaft column, and the
        # post-Esc cursor lands on the Case anchor
        ('word', (7, 8, 9),
         ((7, t0, stem), (7, an, f'##{b}#####{b}#'),
          (8, t0, f'######{b}#######'),
          (9, t0, '#' * 9), (9, tl, b_tail)),
         (stem + 's', b_tail)),
        # Case (v j e ~): two flipped words with GUARD words outside the
        # span — the west guard before the anchor (top row toggles
        # anchor→line end), the east guard past the cursor (bottom row
        # toggles line start→cursor). The linewise g~j flips the guards too
        # and reads false: per-row charwise ~ is forced.
        ('case', (11, 12),
         ((11, t0, gw), (11, an, w1.upper()),
          (12, t0, w2.upper()), (12, t0 + 7, ge)),
         (f'{gw} {w1}', f'{w2} {ge}')),
        # Seal (v /{x}⏎ h d): the tail's initial is pristine level-wide —
        # the one named thing; name what you see
        ('seal', (14, 15, 16),
         ((14, t0, s_head), (14, an, '#' * 10),
          (15, t0, '#' * 14),
          (16, t0, '#' * 9), (16, tl, s_tail)),
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
    rng = random.Random(seed)
    words = _ss_draw_words(rng)
    chambers = _ss_chambers(words)

    R, C = _SS_ROWS, _SS_COLS
    cells = [[CellType.WALL] * C for _ in range(R)]
    for r in range(2, _SS_GATE + 1):                     # the spine
        cells[r][_SS_SPINE] = CellType.FLOOR
    for _name, rows, _runs, _targets in chambers:        # the bays
        for r in rows:
            for c in range(_SS_BAY_W, _SS_BAY_E + 1):
                cells[r][c] = CellType.FLOOR
    for r in _SS_SHAFT_ROWS:                             # the light shaft —
        cells[r][_SS_SHAFT] = CellType.FLOOR             # NOT the throat row:
    # the gate row is still reachable only along the spine (teleport audit)
    # gate row: spine only — bolts and the exit STAY WALL (the FINAL SEAL);
    # the tick floors each bolt as its chamber reads true, the seal last.

    room = Room(room_type=RoomType.ENTRY, rows=R, cols=C)
    room.cells = cells
    room.seed  = seed

    doors = []
    for i, (_name, _rows, runs, targets) in enumerate(chambers):
        for rr, cc, text in runs:
            room.char_runs.append(CharRun(rr, cc, tuple(text), 'ancient'))
        doors.append((targets, _SS_BOLT0 + i))
        # the plaque carries the row's FULL true reading (multi-word rows
        # split into one run per word — a literal space glyph is a
        # punctuation "word" and would render a floor-looking gap)
        plaque_rows = (_rows[0], _rows[-1])
        for pr, ptext in zip(plaque_rows, targets):
            col = _SS_PLQ_COL
            for part in ptext.split(' '):
                room.char_runs.append(CharRun(pr, col, tuple(part), 'verdant'))
                col += len(part) + 1
    room._ss_doors = tuple(doors)
    room._ss_words = words
    # no lintel: floating carved words over the spawn read as a locked door
    # (playtest 2026-07-12) — the credo lives in the intro hint instead

    room.entities.append(Entity(kind='exit', row=_SS_EXIT[0], col=_SS_EXIT[1],
                                edit_immune=True))
    room.spawn_pos = (2, _SS_SPINE)
    room.exit_pos  = _SS_EXIT

    room.rebuild_indexes()
    room.par    = _SS_PAR
    room.budget = math.ceil(_SS_PAR * 1.4)   # STANDARD: the piecewise route wins at 1★
    room.answer = _ss_answer(words)

    dungeon = Dungeon(name='The Sight Sanctum', seed=seed)
    dungeon.rooms        = [room]
    dungeon.current_room = 0
    return dungeon


# ── The Selection Halls (V <C-v>) ───────────────────────────────────────────────
# The gallery of corrupt panels: whole-row blights take V (the idiom),
# columnar seams and rectangles take <C-v> (the forcing). Six chambers on the
# exact-text chassis (spine, anchor-aligned light shaft, gate-row bolts,
# FINAL SEAL — the Sight Sanctum's proven bones):
#
#   • THE CASE TRIO (V, honestly price-forced — the g-prefix tax; user-found):
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
# (the nav-golf audit); the answer tape shows <C-v> as ^v — load-bearing,
# unlike Esc, so it must be visible (the tracker eats both chars at once).
_SH_ROWS, _SH_COLS = 32, 26
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
_SH_PANEL_FLK   = 15                # panel flank word (len 3) at cols 15..17
_SH_PANEL_W0    = 19                # panel word (len 6) at cols 19..24
_SH_SHAFT_SEPS  = (4, 6, 8, 12, 16, 20, 24)  # separators the shaft pierces
_SH_THROAT = 29                     # spine-only (teleport audit)
_SH_GATE   = 30
_SH_BOLT0  = 14                     # bolts cols 14..21, one per chamber
_SH_EXIT   = (30, 22)               # the FINAL SEAL
_SH_PAR    = 64


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
        panels = rng.sample(pool(6), 4)          # the 4-cycle panel words
        flanks = rng.sample(pool(3), 4)
        picks = case3 + stripe + rect + ins + stamp + panels + flanks
        if len(set(picks)) == len(picks):
            return {'case': case3, 'stripe': stripe, 'rect': rect,
                    'ins': ins, 'letter': letter,
                    'stamp': stamp, 'stamp_letter': stamp_letter,
                    'panels': panels, 'flanks': flanks}
    raise ValueError('selection_halls: no distinct draw after 80 tries')


def build_dungeon_selection_halls(seed: int) -> Dungeon:
    """The Selection Halls (slug `selection_halls`): V and <C-v>.

    Six chambers — the case trio (V's honest price win, the g-prefix tax),
    then the block stripe, rectangle, and insert (<C-v>'s ops with no
    normal-mode form at all). See the section header for the full forcing."""
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
    # the four panels: each row holds the PREVIOUS row's true word (a 4-cycle
    # rotated one frame down); flanks make every row's reading distinct
    runs, targets_p = [], []
    for i, r in enumerate(_SH_PANEL_ROWS):
        wrong = words['panels'][(i - 1) % 4]     # row i wears panel i-1
        runs += [(r, _SH_PANEL_FLK, words['flanks'][i]),
                 (r, _SH_PANEL_W0, wrong)]
        targets_p.append(f"{words['flanks'][i]} {words['panels'][i]}")
    chambers.append((_SH_PANEL_ROWS, tuple(runs), tuple(targets_p)))

    R, C = _SH_ROWS, _SH_COLS
    cells = [[CellType.WALL] * C for _ in range(R)]
    for r in range(2, _SH_GATE + 1):                     # the spine
        cells[r][_SH_SPINE] = CellType.FLOOR
    for rows, _runs, _targets in chambers:               # the bays
        for r in rows:
            for c in range(_SH_BAY_W, _SH_BAY_E + 1):
                cells[r][c] = CellType.FLOOR
    for r in _SH_SHAFT_SEPS:                             # the light shaft —
        cells[r][_SH_SHAFT] = CellType.FLOOR             # NOT the throat row

    room = Room(room_type=RoomType.ENTRY, rows=R, cols=C)
    room.cells = cells
    room.seed  = seed

    doors = []
    for i, (rows, runs, targets) in enumerate(chambers):
        for rr, cc, text in runs:
            room.char_runs.append(CharRun(rr, cc, tuple(text), 'ancient'))
        doors.append((targets, _SH_BOLT0 + i))
        for pr, ptext in zip(rows, targets):             # full true readings
            room.char_runs.append(CharRun(pr, _SH_PLQ_COL, tuple(ptext), 'verdant'))
    room._ss_doors = tuple(doors)                        # the shared exact-text tick
    room._sh_words = words

    room.entities.append(Entity(kind='exit', row=_SH_EXIT[0], col=_SH_EXIT[1],
                                edit_immune=True))
    room.spawn_pos = (2, _SH_SPINE)
    room.exit_pos  = _SH_EXIT

    room.rebuild_indexes()
    room.par    = _SH_PAR
    room.budget = 110   # GENEROUS hand-set (old-route min 109 + 1; the route
    # pays two count-x digit charges since the 2026-07-19 {n}x law): the four
    # panels' bay wall EATS the old P-then-delete juggle's displaced word
    # (the void-push), so the honest old route must RETYPE two panels and
    # rebuild a third — visual p is terrain-forced, and 1.4·par (90) would
    # make the old route unwinnable (the 1★ law). Indentation precedent.
    # <C-v> shows on the tape as ^v (load-bearing, unlike Esc — a player
    # following the tape must see it; the tracker eats both chars at once)
    sl = words['stamp_letter']
    room.answer = (f'j VU 2j Vu 2j V~ 2j ^v2jld 4j ^v2j3l~ 4j ^v2jI{letter} '
                   f'4j ^v2jr{sl} 4j w ye 3j vep k vbp k vbp k vbp G $')

    dungeon = Dungeon(name='The Selection Halls', seed=seed)
    dungeon.rooms        = [room]
    dungeon.current_room = 0
    return dungeon


# ── The Word Enclosure (iw aw) ──────────────────────────────────────────────────
# The first text objects: select by SHAPE, not by landing. Three chambers on
# the exact-text chassis, discriminated by THE SCAR (probe-verified): deleting
# a middle word from `w1 rot w2` with diw leaves BOTH separators — `w1  w2`,
# the double-gap scar — while daw takes the trailing one too: `w1 w2`, the
# seam healed. The doors read the one-space difference directly.
#
#   • C1 the diw DRILL (3 rows, doors = double-gap targets): rot words of
#     DIFFERENT lengths at STAGGERED starts, so the after-diw cursor (the
#     deletion start) always lands INSIDE the next row's rot — `diw j . j .`
#     chains at 1 key/row. The piecewise rival (`de` needs the word START
#     each row) pays an h per stagger; dw/daw heal the seam and read false.
#   • C2 the ciw CURE (2 rows, different cures — no dot shortcut): the hop
#     lands two INSIDE the rot (the previous Esc parks the cursor exactly on
#     the next anchor), so `ce` pays hh first; `caw` fuses the typed cure
#     into w2 and reads false; count-s is position-relative.
#   • C3 the daw SEAM (2 rows, doors = single-gap): `dw` from the start
#     would tie daw, so the arrival is mid-rot again (hh dw = 4 vs daw 3);
#     diw leaves the scar and reads false; `.` repeats the daw on row two.
#   • C4 the diW TOKEN (2 rows) · C5 the daW TOKEN (2 rows): MIXED stones
#     (`rotA-rotB` — one WORD, three w-words). The CLASS lesson: diw/dw/de
#     kill a subword and read false; the honest rival is the WORD family
#     (dE/dW from the token START), which TIES ±1 — documented, the g~
#     precedent. Scar doors for diW, seam doors for daW.
#
# THE DOT GAP (first level priced after the dot-insert replay, 2026-07-13):
# a text object is ONE change, so it dot-chains down a column; the piecewise
# fixes need re-positioning every row that dot can't provide. Rivals are
# driven WITH their own best dot usage and win at 1★ inside the standard 1.4
# budget. Vocabulary is drawn per seed with FIXED slot lengths.
_WE_ROWS, _WE_COLS = 21, 40
_WE_SPINE  = 17                     # every row's first standable
_WE_BAY_W  = 18                     # bay floor cols 18..38; east wall 39
_WE_BAY_E  = 38
_WE_PLQ_COL = 2                     # full true readings (≤14 chars, cols 2..15)
_WE_TEXT0  = 19                     # w1 starts here on every row
_WE_SHAFT  = 26                     # the landing column: inside every rot it hops to
_WE_C1_ROWS = (3, 4, 5)
_WE_C2_ROWS = (7, 8)
_WE_C3_ROWS = (10, 11)
_WE_C4_ROWS = (13, 14)              # diW — mixed tokens
_WE_C5_ROWS = (16, 17)              # daW
_WE_SHAFT_SEPS = ((6, 26), (9, 26), (12, 24), (15, 24))   # (row, col)
_WE_THROAT = 18
_WE_GATE   = 19
_WE_BOLT0  = 18                     # bolts cols 18..22, one per chamber
_WE_EXIT   = (19, 23)               # the FINAL SEAL
# (row, w1 len, rot len, rot start): rot start = TEXT0 + w1len + 1; staggered
# so the diw chain lands inside the next rot, and the C2/C3 hop from the
# shaft column arrives at rot start + 2 (ce/dw must pay the h's back).
_WE_C1_SHAPE = ((3, 7, 5, 27), (4, 6, 4, 26), (5, 6, 3, 26))
_WE_C2_SHAPE = ((7, 4, 4, 24), (8, 4, 4, 24))
_WE_C3_SHAPE = ((10, 4, 4, 24), (11, 4, 4, 24))
# mixed-token chambers: (row, w1 len, token len, token start) — the token is
# rotA-rotB (two len-4 words hyphenated: ONE WORD, three w-words)
_WE_C4_SHAPE = ((13, 3, 9, 23), (14, 3, 9, 23))
_WE_C5_SHAPE = ((16, 3, 9, 23), (17, 3, 9, 23))
_WE_PAR = 49            # hand-tallied along the driven tape (buffer mutates)


def _we_draw_words(rng) -> dict:
    """Draw the enclosure vocabulary (fixed slot lengths pin par and the
    rival chains). Seven (w1, rot, w2) triples + two typed cures (len 3),
    all pairwise distinct."""
    _load_vocab_tables()

    def pool(length):
        return [w for w in _VOCAB_PLAIN_BY_LEN.get(length, ())
                if w.isalpha() and w == w.lower()]

    shapes = _WE_C1_SHAPE + _WE_C2_SHAPE + _WE_C3_SHAPE
    for _ in range(80):
        picks: list = []

        def draw(length):
            w = rng.choice(pool(length))
            picks.append(w)
            return w

        rows = [(draw(w1l), draw(rotl), draw(5)) for _r, w1l, rotl, _rs in shapes]
        # mixed tokens for C4/C5: rotA-rotB (token len 9 = 4+1+4)
        mixed = [(draw(w1l), f'{draw(4)}-{draw(4)}', draw(5))
                 for _r, w1l, _tl, _ts in (_WE_C4_SHAPE + _WE_C5_SHAPE)]
        cures = [draw(3), draw(3)]
        if len(set(picks)) == len(picks):
            return {'rows': rows, 'mixed': mixed, 'cures': cures}
    raise ValueError('word_enclosure: no distinct draw after 80 tries')


def build_dungeon_word_enclosure(seed: int) -> Dungeon:
    """The Word Enclosure (slug `word_enclosure`): iw and aw.

    Select by shape, not by landing: the diw drill (dot-chained down the
    staggered rots), the ciw cure (caw fuses and reads false), and the daw
    seam (diw leaves the scar). See the section header for the forcing."""
    rng = random.Random(seed)
    words = _we_draw_words(rng)
    shapes = _WE_C1_SHAPE + _WE_C2_SHAPE + _WE_C3_SHAPE

    # per-row runs + each chamber's door targets
    runs, targets = [], {}
    for (r, w1l, rotl, rot_s), (w1, rot, w2) in zip(shapes, words['rows']):
        w2_s = rot_s + rotl + 1
        runs += [(r, _WE_TEXT0, w1), (r, rot_s, rot), (r, w2_s, w2)]
        targets[r] = (w1, w2)
    for (r, _w1l, tokl, tok_s), (w1, tok, w2) in zip(
            _WE_C4_SHAPE + _WE_C5_SHAPE, words['mixed']):
        runs += [(r, _WE_TEXT0, w1), (r, tok_s, tok), (r, tok_s + tokl + 1, w2)]
        targets[r] = (w1, w2)
    c1 = tuple(f'{targets[r][0]}  {targets[r][1]}' for r in _WE_C1_ROWS)  # the scar
    c2 = tuple(f'{targets[r][0]} {c} {targets[r][1]}'
               for r, c in zip(_WE_C2_ROWS, words['cures']))
    c3 = tuple(f'{targets[r][0]} {targets[r][1]}' for r in _WE_C3_ROWS)  # the seam
    c4 = tuple(f'{targets[r][0]}  {targets[r][1]}' for r in _WE_C4_ROWS)  # scar
    c5 = tuple(f'{targets[r][0]} {targets[r][1]}' for r in _WE_C5_ROWS)   # seam
    chambers = ((_WE_C1_ROWS, c1), (_WE_C2_ROWS, c2), (_WE_C3_ROWS, c3),
                (_WE_C4_ROWS, c4), (_WE_C5_ROWS, c5))

    R, C = _WE_ROWS, _WE_COLS
    cells = [[CellType.WALL] * C for _ in range(R)]
    for r in range(2, _WE_GATE + 1):                     # the spine
        cells[r][_WE_SPINE] = CellType.FLOOR
    for rows, _t in chambers:                            # the bays
        for r in rows:
            for c in range(_WE_BAY_W, _WE_BAY_E + 1):
                cells[r][c] = CellType.FLOOR
    for r, c in _WE_SHAFT_SEPS:                          # the light shafts —
        cells[r][c] = CellType.FLOOR                     # NOT the throat row

    room = Room(room_type=RoomType.ENTRY, rows=R, cols=C)
    room.cells = cells
    room.seed  = seed

    doors = []
    for i, (rows, tgt) in enumerate(chambers):
        doors.append((tgt, _WE_BOLT0 + i))
        for pr, ptext in zip(rows, tgt):                 # full true readings
            col = _WE_PLQ_COL
            for part in ptext.split(' '):
                if part:
                    room.char_runs.append(CharRun(pr, col, tuple(part), 'verdant'))
                col += len(part) + 1
    for rr, cc, text in runs:
        room.char_runs.append(CharRun(rr, cc, tuple(text), 'ancient'))
    room._ss_doors = tuple(doors)                        # the shared exact-text tick
    room._we_words = words

    room.entities.append(Entity(kind='exit', row=_WE_EXIT[0], col=_WE_EXIT[1],
                                edit_immune=True))
    room.spawn_pos = (2, _WE_SPINE)
    room.exit_pos  = _WE_EXIT

    room.rebuild_indexes()
    room.par    = _WE_PAR
    room.budget = math.ceil(_WE_PAR * 1.4)   # STANDARD: the piecewise route wins at 1★
    ca, cb = words['cures']
    room.answer = (f'j w w diw j . j . 2j ciw {ca} j ciw {cb} '
                   f'2j daw j . 2j diW j . l 2j daW j . G $')

    dungeon = Dungeon(name='The Word Enclosure', seed=seed)
    dungeon.rooms        = [room]
    dungeon.current_room = 0
    return dungeon


# ── The Bracket Enclosure (i( a() ────────────────────────────────────────────────
# GEM SETTINGS: the parens are settings, the content is the stone. Three
# door types on the exact-text chassis, discriminated by what remains
# (probe-verified):
#   • C1 the PRIED SETTING (di(, 3 rows): `w1 (rot) w2` → `w1 () w2` — the
#     empty husk stays and the door reads it. Stones of DIFFERENT lengths at
#     staggered positions keep the `di( j . j .` chain landing inside the
#     next stone (a replayed {n}x eats the wrong span — dead); dt)/dT( pay
#     repositioning; dw/daw heal wrongly. Row 3's stone is TWO WORDS —
#     diw kills half and reads false (the object-vs-object lesson).
#   • C2 the NEW STONE (ci( + cure, 2 rows, different cures): → `w1 (cure)
#     w2`; the hop lands mid-content so ct) leaves the head (wrong text);
#     ca(+cure tears the setting out and fuses — reads false.
#   • C3 the TORN FITTING (da(, 2 rows): → `w1  w2` — the double-gap scar
#     (a( takes no whitespace); di( leaves the husk and reads false. da( is
#     honestly forced from anywhere inside (F( df) = 5 vs 3); `(stone)` is
#     ONE WORD, so dE-from-the-( ties only after an F(/h back.
# Walk-in chamber first, arrival-forced chambers on hops (the chamber-order
# law); rivals driven WITH their own best dot usage.
_BE_ROWS, _BE_COLS = 15, 41
_BE_SPINE  = 17                     # every row's first standable
_BE_BAY_W  = 18                     # bay floor cols 18..39; east wall 40
_BE_BAY_E  = 39
_BE_PLQ_COL = 2                     # full true readings (≤14 chars)
_BE_TEXT0  = 19                     # w1 starts here on every row
_BE_C1_ROWS = (3, 4, 5)
_BE_C2_ROWS = (7, 8)
_BE_C3_ROWS = (10, 11)
_BE_SHAFT_SEPS = ((6, 25), (9, 26))  # (row, col) — the hop landing columns
_BE_THROAT = 12
_BE_GATE   = 13
_BE_BOLT0  = 18                     # bolts cols 18..20, one per chamber
_BE_EXIT   = (13, 21)               # the FINAL SEAL
# (row, w1 len, stone len, fitting '(' col): stone start = fitting + 1 =
# TEXT0 + w1len + 2; staggered so the di( chain and every hop land INSIDE
# the next stone (row 3's stone is 'ab cd' — 3+1+3 = 7, two words).
_BE_C1_SHAPE = ((3, 5, 7, 25), (4, 4, 5, 24), (5, 4, 4, 24))
_BE_C2_SHAPE = ((7, 3, 4, 23), (8, 3, 4, 23))
_BE_C3_SHAPE = ((10, 4, 4, 24), (11, 3, 4, 23))
_BE_PAR = 33            # hand-tallied along the driven tape (j % entry)


def _be_draw_words(rng) -> dict:
    """Draw the enclosure vocabulary (fixed slot lengths pin par and the
    rival chains). Row 3's stone is two len-3 words; two typed cures (len 3);
    all pairwise distinct."""
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

        rows = []
        for i, (_r, w1l, stl, _fs) in enumerate(_BE_C1_SHAPE + _BE_C2_SHAPE
                                                + _BE_C3_SHAPE):
            stone = f'{draw(3)} {draw(3)}' if i == 0 else draw(stl)
            rows.append((draw(w1l), stone, draw(5)))
        cures = [draw(3), draw(3)]
        if len(set(picks)) == len(picks):
            return {'rows': rows, 'cures': cures}
    raise ValueError('bracket_enclosure: no distinct draw after 80 tries')


def build_dungeon_bracket_enclosure(seed: int) -> Dungeon:
    """The Bracket Enclosure (slug `bracket_enclosure`): i( and a(.

    Gem settings: di( pries the stone and keeps the husk, ci( sets a new
    stone, da( tears the whole fitting out and leaves the scar. See the
    section header for the forcing."""
    rng = random.Random(seed)
    words = _be_draw_words(rng)
    shapes = _BE_C1_SHAPE + _BE_C2_SHAPE + _BE_C3_SHAPE

    runs, targets = [], {}
    for (r, w1l, stl, f_s), (w1, stone, w2) in zip(shapes, words['rows']):
        w2_s = f_s + stl + 3                          # past '(stone) '
        runs += [(r, _BE_TEXT0, w1), (r, f_s, f'({stone})'), (r, w2_s, w2)]
        targets[r] = (w1, w2)
    c1 = tuple(f'{targets[r][0]} () {targets[r][1]}' for r in _BE_C1_ROWS)
    c2 = tuple(f'{targets[r][0]} ({c}) {targets[r][1]}'
               for r, c in zip(_BE_C2_ROWS, words['cures']))
    c3 = tuple(f'{targets[r][0]}  {targets[r][1]}' for r in _BE_C3_ROWS)
    chambers = ((_BE_C1_ROWS, c1), (_BE_C2_ROWS, c2), (_BE_C3_ROWS, c3))

    R, C = _BE_ROWS, _BE_COLS
    cells = [[CellType.WALL] * C for _ in range(R)]
    for r in range(2, _BE_GATE + 1):                     # the spine
        cells[r][_BE_SPINE] = CellType.FLOOR
    for rows, _t in chambers:                            # the bays
        for r in rows:
            for c in range(_BE_BAY_W, _BE_BAY_E + 1):
                cells[r][c] = CellType.FLOOR
    for r, c in _BE_SHAFT_SEPS:                          # the light shafts —
        cells[r][c] = CellType.FLOOR                     # NOT the throat row

    room = Room(room_type=RoomType.ENTRY, rows=R, cols=C)
    room.cells = cells
    room.seed  = seed

    doors = []
    for i, (rows, tgt) in enumerate(chambers):
        doors.append((tgt, _BE_BOLT0 + i))
        for pr, ptext in zip(rows, tgt):                 # full true readings
            col = _BE_PLQ_COL
            for part in ptext.split(' '):
                if part:
                    room.char_runs.append(CharRun(pr, col, tuple(part), 'verdant'))
                col += len(part) + 1
    for rr, cc, text in runs:
        room.char_runs.append(CharRun(rr, cc, tuple(text), 'ancient'))
    room._ss_doors = tuple(doors)                        # the shared exact-text tick
    room._be_words = words

    room.entities.append(Entity(kind='exit', row=_BE_EXIT[0], col=_BE_EXIT[1],
                                edit_immune=True))
    room.spawn_pos = (2, _BE_SPINE)
    room.exit_pos  = _BE_EXIT

    room.rebuild_indexes()
    room.par    = _BE_PAR
    room.budget = math.ceil(_BE_PAR * 1.4)   # STANDARD: the piecewise route wins at 1★
    ca, cb = words['cures']
    # nav golf (user-found in playtest): % from the spine scans to the first
    # '(' and jumps to its MATCH — j % lands ON the ')' and di( resolves
    # from the delimiter. Two keys under the w-walk.
    room.answer = (f'j % di( j . j . 2j ci( {ca} j ci( {cb} '
                   f'2j da( j . G $')

    dungeon = Dungeon(name='The Bracket Enclosure', seed=seed)
    dungeon.rooms        = [room]
    dungeon.current_room = 0
    return dungeon


# ── The Brace & Square Enclosure (i[ a[ i{ a{) ──────────────────────────────
#
# Level 33 taught inside-vs-around on one delimiter family; with two more the
# lesson becomes CHOOSING the object — reading the delimiter under your hand —
# and, in the nest chamber, resolving AMBIGUITY: from one cursor position
# inside `[{junk} flank]`, di{ and di[ carve different spans. Five chambers on
# the exact-text chassis (_sight_sanctum_tick):
#   C1 (rows 3-4)   di[ husk ×2, the second by dot   → 'w1 [] w2'
#   C2 (rows 6-7)   ci[ cures (typed, single tokens) → 'w1 [cure] w2'
#   C3 (rows 9-10)  di{ + dot (the family switch — a blind '.' straight off
#                   C2 replays ci[+text and finds no [ here: a costed no-op)
#   C4 (rows 12-13) THE NEST, twin mirrored rows: `w1 [{jjj} bbb] w2`.
#                   Row 12's door wants only the braces emptied (di{); row
#                   13's wants the square gutted whole (di[) — same landing
#                   column, two different correct objects. Twin bolts sit at
#                   the CENTER of the gate run (cols 25-26), plaques ember /
#                   pedestal so the pair reads as a matched set.
#   C5 (row 15)     da{ scar                          → 'w1  w2'
#
# Forcing audit (why par 45 needs the objects):
#   • every hop lands MID-junk (never at junk start), so `{n}x` pays a
#     positioning key the object doesn't;
#   • d% kills the delimiters, so it can never match a husk target; on the
#     scar row it needs an h first (h d% = 3, a tie with da{, never a win);
#   • dT[/dt] need the junk edge, which the landings don't give;
#   • row 3's stone is two words (no single-count x chain).
_BSQ_ROWS, _BSQ_COLS = 19, 48
_BSQ_SPINE   = 22                    # every row's first standable
_BSQ_BAY_W   = 23                    # bay floor cols 23..45; east wall 46
_BSQ_BAY_E   = 45
_BSQ_PLQ_COL = 2                     # full true readings (≤19 chars)
_BSQ_TEXT0   = 24                    # w1 starts here on every row
_BSQ_C1_ROWS = (3, 4)
_BSQ_C2_ROWS = (6, 7)
_BSQ_C3_ROWS = (9, 10)
_BSQ_C4_ROWS = (12, 13)
_BSQ_C5_ROWS = (15,)
_BSQ_SHAFT_SEPS = ((5, 30), (8, 31), (11, 31), (14, 29))
_BSQ_THROAT  = 16
_BSQ_GATE    = 17
_BSQ_BOLT0   = 23                    # bolts 23..28: C1 C2 C4a C4b C3 C5
_BSQ_BOLTS   = {'c1': 23, 'c2': 24, 'c4a': 25, 'c4b': 26, 'c3': 27, 'c5': 28}
_BSQ_EXIT    = (17, 29)              # the FINAL SEAL, east of every bolt
# (row, w1 len, junk/stone len, delimiter open col = TEXT0 + w1len + 1)
_BSQ_C1_SHAPE = ((3, 5, 7, 30), (4, 4, 5, 29))       # row 3 stone = 'aaa bbb'
_BSQ_C2_SHAPE = ((6, 3, 4, 28), (7, 3, 4, 28))
_BSQ_C3_SHAPE = ((9, 4, 4, 29), (10, 5, 5, 30))
_BSQ_C4_SHAPE = ((12, 3, 3, 28), (13, 3, 3, 28))     # mirrored twins
_BSQ_C5_SHAPE = ((15, 3, 5, 28),)
_BSQ_PAR = 45           # hand-tallied along the driven tape (j % entry)


def _bsq_draw_words(rng) -> dict:
    """Draw the enclosure vocabulary (fixed slot lengths pin par and the
    rival chains). Row 3's stone is two len-3 words; C4's twins carry a len-3
    junk and a len-3 flank each; two typed cures (len 3); all distinct."""
    _load_vocab_tables()

    def pool(length):
        return [w for w in _VOCAB_PLAIN_BY_LEN.get(length, ())
                if w.isalpha() and w == w.lower()]

    shapes = (_BSQ_C1_SHAPE + _BSQ_C2_SHAPE + _BSQ_C3_SHAPE
              + _BSQ_C4_SHAPE + _BSQ_C5_SHAPE)
    for _ in range(80):
        picks: list = []

        def draw(length):
            w = rng.choice(pool(length))
            picks.append(w)
            return w

        rows, flanks = [], {}
        for i, (r, w1l, stl, _fs) in enumerate(shapes):
            stone = f'{draw(3)} {draw(3)}' if i == 0 else draw(stl)
            rows.append((draw(w1l), stone, draw(5)))
            if r in _BSQ_C4_ROWS:
                flanks[r] = draw(3)
        cures = [draw(3), draw(3)]
        if len(set(picks)) == len(picks):
            return {'rows': rows, 'cures': cures, 'flanks': flanks}
    raise ValueError('brace_square_enclosure: no distinct draw after 80 tries')


def build_dungeon_brace_square_enclosure(seed: int) -> Dungeon:
    """The Brace & Square Enclosure (slug `brace_square_enclosure`):
    i[ a[ i{ a{ — choose the object; in the nest, choose the DEPTH."""
    rng = random.Random(seed)
    words = _bsq_draw_words(rng)
    shapes = (_BSQ_C1_SHAPE + _BSQ_C2_SHAPE + _BSQ_C3_SHAPE
              + _BSQ_C4_SHAPE + _BSQ_C5_SHAPE)

    runs, targets = [], {}
    for (r, w1l, stl, f_s), (w1, stone, w2) in zip(shapes, words['rows']):
        if r in _BSQ_C4_ROWS:                          # `w1 [{jjj} bbb] w2`
            fit = f'[{{{stone}}} {words["flanks"][r]}]'
        elif r in _BSQ_C1_ROWS + _BSQ_C2_ROWS:         # `w1 [stone] w2`
            fit = f'[{stone}]'
        else:                                          # `w1 {stone} w2`
            fit = f'{{{stone}}}'
        w2_s = f_s + len(fit) + 1
        runs += [(r, _BSQ_TEXT0, w1), (r, f_s, fit), (r, w2_s, w2)]
        targets[r] = (w1, w2)
    ca, cb = words['cures']
    c1  = tuple(f'{targets[r][0]} [] {targets[r][1]}' for r in _BSQ_C1_ROWS)
    c2  = tuple(f'{targets[r][0]} [{c}] {targets[r][1]}'
                for r, c in zip(_BSQ_C2_ROWS, words['cures']))
    c3  = tuple(f'{targets[r][0]} {{}} {targets[r][1]}' for r in _BSQ_C3_ROWS)
    c4a = (f'{targets[12][0]} [{{}} {words["flanks"][12]}] {targets[12][1]}',)
    c4b = (f'{targets[13][0]} [] {targets[13][1]}',)
    c5  = tuple(f'{targets[r][0]}  {targets[r][1]}' for r in _BSQ_C5_ROWS)
    doors = ((c1, _BSQ_BOLTS['c1']), (c2, _BSQ_BOLTS['c2']),
             (c3, _BSQ_BOLTS['c3']), (c4a, _BSQ_BOLTS['c4a']),
             (c4b, _BSQ_BOLTS['c4b']), (c5, _BSQ_BOLTS['c5']))
    plaques = {**{r: (t, 'verdant') for r, t in zip(_BSQ_C1_ROWS, c1)},
               **{r: (t, 'verdant') for r, t in zip(_BSQ_C2_ROWS, c2)},
               **{r: (t, 'verdant') for r, t in zip(_BSQ_C3_ROWS, c3)},
               12: (c4a[0], 'ember'), 13: (c4b[0], 'pedestal'),
               15: (c5[0], 'verdant')}

    R, C = _BSQ_ROWS, _BSQ_COLS
    cells = [[CellType.WALL] * C for _ in range(R)]
    for r in range(2, _BSQ_GATE + 1):                    # the spine
        cells[r][_BSQ_SPINE] = CellType.FLOOR
    for r, _w1l, _stl, _fs in shapes:                    # the bays
        for c in range(_BSQ_BAY_W, _BSQ_BAY_E + 1):
            cells[r][c] = CellType.FLOOR
    for r, c in _BSQ_SHAFT_SEPS:                         # the light shafts —
        cells[r][c] = CellType.FLOOR                     # NOT the throat row

    room = Room(room_type=RoomType.ENTRY, rows=R, cols=C)
    room.cells = cells
    room.seed  = seed

    for pr, (ptext, colour) in plaques.items():          # full true readings
        col = _BSQ_PLQ_COL
        for part in ptext.split(' '):
            if part:
                room.char_runs.append(CharRun(pr, col, tuple(part), colour))
            col += len(part) + 1
    for rr, cc, text in runs:
        room.char_runs.append(CharRun(rr, cc, tuple(text), 'ancient'))
    room._ss_doors = doors                               # the shared exact-text tick
    room._bsq_words = words

    room.entities.append(Entity(kind='exit', row=_BSQ_EXIT[0], col=_BSQ_EXIT[1],
                                edit_immune=True))
    room.spawn_pos = (2, _BSQ_SPINE)
    room.exit_pos  = _BSQ_EXIT

    room.rebuild_indexes()
    room.par    = _BSQ_PAR
    room.budget = math.ceil(_BSQ_PAR * 1.4)  # STANDARD: the piecewise route wins at 1★
    room.answer = (f'j % di[ j . 2j ci[ {ca} j ci[ {cb} '
                   f'2j di{{ j . 2j di{{ j di[ 2j da{{ G $')

    dungeon = Dungeon(name='The Brace & Square Enclosure', seed=seed)
    dungeon.rooms        = [room]
    dungeon.current_room = 0
    return dungeon


# ── The Quote Enclosure (i" a" i' a') ───────────────────────────────────────
#
# Quotes have no matching pair — Vim pairs them by scanning the LINE — and
# that buys the level its headline lesson: the quote objects work from
# ANYWHERE WEST of the pair (the resolver seeks forward), so every strike
# here is thrown from the spine, no navigation into the setting at all.
# Five chambers on the exact-text chassis (_sight_sanctum_tick):
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
#                   (player-found golf 2026-07-20; 2f" pays a key more).
#
# Forcing audit (why par 45 needs the objects): the objects fire from the
# spine while every old tool must first walk in (f"/w cost 1-3 keys before a
# {n}x or dt" even starts); % does not speak quotes; D/cc raze the kept
# words. C5's w l 3x route ties the object route (4 = 4) — a tie, never a
# win.
_QE_ROWS, _QE_COLS = 19, 44
_QE_SPINE   = 20                     # every row's first standable
_QE_BAY_W   = 21                     # bay floor cols 21..42; east wall 43
_QE_BAY_E   = 42
_QE_PLQ_COL = 2                      # full true readings (≤17 chars)
_QE_TEXT0   = 22                     # w1 starts here on every row (len 4)
_QE_C1_ROWS = (3, 4)
_QE_C2_ROWS = (6, 7)
_QE_C3_ROWS = (9, 10)
_QE_C4_ROWS = (12, 13)
_QE_C5_ROWS = (15,)
_QE_SHAFT_SEPS = ((5, 28), (8, 30), (11, 28), (14, 27))
_QE_THROAT  = 16
_QE_GATE    = 17
_QE_BOLTS   = {'c1': 21, 'c2': 22, 'c3': 23, 'c4': 24, 'c5': 25}
_QE_EXIT    = (17, 26)               # the FINAL SEAL, east of every bolt
# (row, junk len, quote char); w1 is len 4 on every row so the opening
# quote sits at col 27 throughout — the chained landings stay inside or
# west of each next pair, which is all the forward seek needs.
_QE_SHAPE = ((3, 3, '"'), (4, 4, '"'), (6, 5, '"'), (7, 4, '"'),
             (9, 4, "'"), (10, 3, "'"), (12, 5, '"'), (13, 4, "'"),
             (15, 3, '"'))
_QE_PAR = 45            # hand-tallied along the driven tape (spine strikes)


def _qe_draw_words(rng) -> dict:
    """Draw the enclosure vocabulary (fixed slot lengths pin par and the
    rival chains): nine w1 (len 4), nine junks (per-shape lens), nine w2
    (len 5), two typed cures (len 3); all pairwise distinct."""
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

        rows = [(draw(4), draw(jl), draw(5)) for (_r, jl, _q) in _QE_SHAPE]
        cures = [draw(3), draw(3)]
        if len(set(picks)) == len(picks):
            return {'rows': rows, 'cures': cures}
    raise ValueError('quote_enclosure: no distinct draw after 80 tries')


def build_dungeon_quote_enclosure(seed: int) -> Dungeon:
    """The Quote Enclosure (slug `quote_enclosure`): i" a" i' a' — strike
    the quoted settings from the spine; the seek does the walking."""
    rng = random.Random(seed)
    words = _qe_draw_words(rng)

    runs, targets = [], {}
    for (r, jl, q), (w1, junk, w2) in zip(_QE_SHAPE, words['rows']):
        if r in _QE_C5_ROWS:                       # 'w1 "" "jjj" w2'
            fit = f'{q}{q} {q}{junk}{q}'
        else:                                      # 'w1 "junk" w2'
            fit = f'{q}{junk}{q}'
        w2_s = _QE_TEXT0 + 5 + len(fit) + 1
        runs += [(r, _QE_TEXT0, w1), (r, _QE_TEXT0 + 5, fit), (r, w2_s, w2)]
        targets[r] = (w1, w2, q)
    ca, cb = words['cures']
    c1 = tuple(f'{targets[r][0]} "" {targets[r][1]}' for r in _QE_C1_ROWS)
    c2 = tuple(f'{targets[r][0]} "{c}" {targets[r][1]}'
               for r, c in zip(_QE_C2_ROWS, words['cures']))
    c3 = tuple(f"{targets[r][0]} '' {targets[r][1]}" for r in _QE_C3_ROWS)
    c4 = tuple(f'{targets[r][0]} {targets[r][1]}' for r in _QE_C4_ROWS)
    c5 = (f'{targets[15][0]} "" "" {targets[15][1]}',)
    doors = ((c1, _QE_BOLTS['c1']), (c2, _QE_BOLTS['c2']),
             (c3, _QE_BOLTS['c3']), (c4, _QE_BOLTS['c4']),
             (c5, _QE_BOLTS['c5']))

    R, C = _QE_ROWS, _QE_COLS
    cells = [[CellType.WALL] * C for _ in range(R)]
    for r in range(2, _QE_GATE + 1):                     # the spine
        cells[r][_QE_SPINE] = CellType.FLOOR
    for r, _jl, _q in _QE_SHAPE:                         # the bays
        for c in range(_QE_BAY_W, _QE_BAY_E + 1):
            cells[r][c] = CellType.FLOOR
    for r, c in _QE_SHAFT_SEPS:                          # the light shafts —
        cells[r][c] = CellType.FLOOR                     # NOT the throat row

    room = Room(room_type=RoomType.ENTRY, rows=R, cols=C)
    room.cells = cells
    room.seed  = seed

    # Full true readings, carved row-aligned into the west wall.
    plaque_rows = (_QE_C1_ROWS + _QE_C2_ROWS + _QE_C3_ROWS
                   + _QE_C4_ROWS + _QE_C5_ROWS)
    plaque_texts = list(c1) + list(c2) + list(c3) + list(c4) + list(c5)
    for pr, ptext in zip(plaque_rows, plaque_texts):
        col = _QE_PLQ_COL
        for part in ptext.split(' '):
            if part:
                room.char_runs.append(CharRun(pr, col, tuple(part), 'verdant'))
            col += len(part) + 1
    for rr, cc, text in runs:
        room.char_runs.append(CharRun(rr, cc, tuple(text), 'ancient'))
    room._ss_doors = doors                               # the shared exact-text tick
    room._qe_words = words

    room.entities.append(Entity(kind='exit', row=_QE_EXIT[0], col=_QE_EXIT[1],
                                edit_immune=True))
    room.spawn_pos = (2, _QE_SPINE)
    room.exit_pos  = _QE_EXIT

    room.rebuild_indexes()
    room.par    = _QE_PAR
    room.budget = math.ceil(_QE_PAR * 1.4)  # STANDARD: the walk-in route wins at 1★
    room.answer = (f'j di" j . 2j ci" {ca} j ci" {cb} '
                   f"2j di' j . 2j da\" j da' "
                   f'2j w di" G $')

    dungeon = Dungeon(name='The Quote Enclosure', seed=seed)
    dungeon.rooms        = [room]
    dungeon.current_room = 0
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
_TE_ROWS, _TE_COLS = 19, 60
_TE_SPINE   = 28                     # every row's first standable
_TE_BAY_W   = 29                     # bay floor cols 29..57; east wall 58
_TE_BAY_E   = 57
_TE_PLQ_COL = 2                      # full true readings (≤25 chars, < spine)
_TE_TEXT0   = 30                     # w1 starts here (len 4); element at 35
_TE_C1_ROWS = (3, 4)
_TE_C2_ROWS = (6, 7)
_TE_C3_ROWS = (9, 10)
_TE_C4_ROWS = (12, 13)               # nest rows carry NO w1/w2 (plaque width)
_TE_C5_ROWS = (15,)
_TE_SHAFT_SEPS = ((5, 40), (8, 42), (11, 35), (14, 35))
_TE_THROAT  = 16
_TE_GATE    = 17
_TE_BOLTS   = {'c1': 29, 'c2': 30, 'c3': 31, 'c4': 32, 'c5': 33}
_TE_EXIT    = (17, 34)               # the FINAL SEAL, east of every bolt
# (row, junk len); tag names are len 3 throughout, so on standard rows the
# open tag sits at col 35 and the content at col 40 — the chained landings
# stay inside each next element.
_TE_SHAPE = ((3, 3), (4, 4), (6, 3), (7, 4), (9, 5), (10, 4),
             (12, 3), (13, 3), (15, 3))
_TE_PAR = 48            # hand-tallied along the driven tape (one f> walk-in)


def _te_draw_words(rng) -> dict:
    """Draw the enclosure vocabulary: seven w1/w2 pairs (standard rows),
    nine junks, THIRTEEN len-3 tag names (nest rows and C5 carry two each),
    two typed cures; all pairwise distinct."""
    _load_vocab_tables()

    def pool(length):
        return [w for w in _VOCAB_PLAIN_BY_LEN.get(length, ())
                if w.isalpha() and w == w.lower()]

    std_rows = [r for r, _jl in _TE_SHAPE
                if r not in _TE_C4_ROWS + _TE_C5_ROWS]
    for _ in range(80):
        picks: list = []

        def draw(length):
            w = rng.choice(pool(length))
            picks.append(w)
            return w

        rows = {}
        for r, jl in _TE_SHAPE:
            if r in _TE_C4_ROWS:                 # (outer, inner, junk)
                rows[r] = (draw(3), draw(3), draw(jl))
            elif r in _TE_C5_ROWS:               # (first, second, junk)
                rows[r] = (draw(3), draw(3), draw(jl))
            else:                                # (w1, name, junk, w2)
                rows[r] = (draw(4), draw(3), draw(jl), draw(5))
        cures = [draw(3), draw(3)]
        if len(set(picks)) == len(picks):
            return {'rows': rows, 'cures': cures, 'std_rows': std_rows}
    raise ValueError('tag_enclosure: no distinct draw after 80 tries')


def build_dungeon_tag_enclosure(seed: int) -> Dungeon:
    """The Tag Enclosure (slug `tag_enclosure`): it at — name the element,
    and the innermost answers."""
    rng = random.Random(seed)
    words = _te_draw_words(rng)

    runs = []
    plaques = []                                          # (row, target text)
    doors_targets = {k: [] for k in ('c1', 'c2', 'c3', 'c4', 'c5')}
    ca, cb = words['cures']
    for r, _jl in _TE_SHAPE:
        w = words['rows'][r]
        if r in _TE_C4_ROWS:
            no, ni, junk = w
            text = f'<{no}><{ni}>{junk}</{ni}></{no}>'
            runs.append((r, _TE_TEXT0, text))
            tgt = (f'<{no}><{ni}></{ni}></{no}>' if r == _TE_C4_ROWS[0]
                   else f'<{no}></{no}>')
            doors_targets['c4'].append(tgt)
            plaques.append((r, tgt))
        elif r in _TE_C5_ROWS:
            na, nb, junk = w
            text = f'<{na}></{na}> <{nb}>{junk}</{nb}>'
            runs.append((r, _TE_TEXT0, text))
            tgt = f'<{na}></{na}> <{nb}></{nb}>'
            doors_targets['c5'].append(tgt)
            plaques.append((r, tgt))
        else:
            w1, name, junk, w2 = w
            fit = f'<{name}>{junk}</{name}>'
            runs += [(r, _TE_TEXT0, w1), (r, _TE_TEXT0 + 5, fit),
                     (r, _TE_TEXT0 + 5 + len(fit) + 1, w2)]
            if r in _TE_C1_ROWS:
                tgt = f'{w1} <{name}></{name}> {w2}'
                doors_targets['c1'].append(tgt)
            elif r in _TE_C2_ROWS:
                cure = ca if r == _TE_C2_ROWS[0] else cb
                tgt = f'{w1} <{name}>{cure}</{name}> {w2}'
                doors_targets['c2'].append(tgt)
            else:                                # C3: the double-gap tear
                tgt = f'{w1}  {w2}'
                doors_targets['c3'].append(tgt)
            plaques.append((r, tgt))
    doors = tuple((tuple(doors_targets[k]), _TE_BOLTS[k])
                  for k in ('c1', 'c2', 'c3', 'c4', 'c5'))

    R, C = _TE_ROWS, _TE_COLS
    cells = [[CellType.WALL] * C for _ in range(R)]
    for r in range(2, _TE_GATE + 1):                     # the spine
        cells[r][_TE_SPINE] = CellType.FLOOR
    for r, _jl in _TE_SHAPE:                             # the bays
        for c in range(_TE_BAY_W, _TE_BAY_E + 1):
            cells[r][c] = CellType.FLOOR
    for r, c in _TE_SHAFT_SEPS:                          # the light shafts —
        cells[r][c] = CellType.FLOOR                     # NOT the throat row

    room = Room(room_type=RoomType.ENTRY, rows=R, cols=C)
    room.cells = cells
    room.seed  = seed

    for pr, ptext in plaques:                            # full true readings
        col = _TE_PLQ_COL
        for part in ptext.split(' '):
            if part:
                room.char_runs.append(CharRun(pr, col, tuple(part), 'verdant'))
            col += len(part) + 1
    for rr, cc, text in runs:
        room.char_runs.append(CharRun(rr, cc, tuple(text), 'ancient'))
    room._ss_doors = doors                               # the shared exact-text tick
    room._te_words = words

    room.entities.append(Entity(kind='exit', row=_TE_EXIT[0], col=_TE_EXIT[1],
                                edit_immune=True))
    room.spawn_pos = (2, _TE_SPINE)
    room.exit_pos  = _TE_EXIT

    room.rebuild_indexes()
    room.par    = _TE_PAR
    room.budget = math.ceil(_TE_PAR * 1.4)  # STANDARD: the walk-in route wins at 1★
    room.answer = (f'j f> dit j . 2j cit {ca} j cit {cb} '
                   f'2j dat j . 2j dit j dat 2j f< dit G $')

    dungeon = Dungeon(name='The Tag Enclosure', seed=seed)
    dungeon.rooms        = [room]
    dungeon.current_room = 0
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
_SE_ROWS, _SE_COLS = 18, 54
_SE_SPINE   = 22                     # every row's first standable
_SE_BAY_W   = 23                     # bay floor cols 23..51; east wall 52
_SE_BAY_E   = 51
_SE_PLQ_COL = 2                      # full true readings (≤19 chars)
_SE_TEXT0   = 24
_SE_C1_ROWS = (3, 4)
_SE_C2_ROWS = (6, 7)
_SE_C3_ROWS = (9, 10)
_SE_C4_ROWS = (12,)
_SE_C5_ROWS = (14,)
_SE_SHAFT_SEPS = ((5, 33), (8, 31), (11, 33), (13, 29))
_SE_THROAT  = 15
_SE_GATE    = 16
_SE_BOLTS   = {'c1': 23, 'c2': 24, 'c3': 25, 'c4': 26, 'c5': 27}
_SE_EXIT    = (16, 28)               # the FINAL SEAL, east of every bolt
_SE_PAR = 43            # hand-tallied along the driven tape (mid landings;
                        # C5 falls to TWO DOTS riding C4's das — player-found
                        # golf 2026-07-20: re-striking das there paid 2 over)


def _se_draw_words(rng) -> dict:
    """Draw the enclosure vocabulary. Per-chamber row SHAPES stagger the
    first sentence's length so the chained landing column always falls
    MID-target-sentence: C1/C5 rows open with a two-word sentence, C2 with
    a lone len-5 word, C3/C4 with a lone len-4 word. Cures len 3."""
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

        rows = {}
        for r in _SE_C1_ROWS + _SE_C5_ROWS:      # 3× two len-3 words
            rows[r] = ([draw(3), draw(3)], [draw(3), draw(3)],
                       [draw(3), draw(3)])
        for r in _SE_C2_ROWS:                    # len-5 lone + 2× pairs
            rows[r] = ([draw(5)], [draw(3), draw(3)], [draw(3), draw(3)])
        for r in _SE_C3_ROWS:                    # len-4 lone + 2× pairs
            rows[r] = ([draw(4)], [draw(3), draw(3)], [draw(3), draw(3)])
        for r in _SE_C4_ROWS:                    # len-4 lone + one pair
            rows[r] = ([draw(4)], [draw(3), draw(3)])
        cures = [draw(3), draw(3)]
        if len(set(picks)) == len(picks):
            return {'rows': rows, 'cures': cures}
    raise ValueError('sentence_enclosure: no distinct draw after 80 tries')


def _se_sentence(words) -> str:
    return ' '.join(words) + '.'


def build_dungeon_sentence_enclosure(seed: int) -> Dungeon:
    """The Sentence Enclosure (slug `sentence_enclosure`): is as — the
    sentence under your hand, from anywhere inside it."""
    rng = random.Random(seed)
    words = _se_draw_words(rng)
    ca, cb = words['cures']

    runs, plaques = [], []
    tgt = {}
    for r, sents in words['rows'].items():
        text = ' '.join(_se_sentence(s) for s in sents)
        # Space-free runs with bare-floor gaps (the space-glyph law: a
        # literal space glyph is a punctuation 'word' and breaks w / the
        # sentence scanner) — the floor scan reconstructs the spacing.
        col = _SE_TEXT0
        for part in text.split(' '):
            if part:
                runs.append((r, col, part))
            col += len(part) + 1
        s_texts = [_se_sentence(s) for s in sents]
        if r in _SE_C1_ROWS:                     # dis middle: DOUBLE gap
            tgt[r] = f'{s_texts[0]}  {s_texts[2]}'
        elif r in _SE_C2_ROWS:                   # das middle: SINGLE gap
            tgt[r] = f'{s_texts[0]} {s_texts[2]}'
        elif r in _SE_C3_ROWS:                   # cis middle: the cure
            cure = ca if r == _SE_C3_ROWS[0] else cb
            tgt[r] = f'{s_texts[0]} {cure}. {s_texts[2]}'
        elif r in _SE_C4_ROWS:                   # das last: only s1 stands
            tgt[r] = s_texts[0]
        else:                                    # C5: only the LAST stands
            tgt[r] = s_texts[2]
        plaques.append((r, tgt[r]))
    doors = ((tuple(tgt[r] for r in _SE_C1_ROWS), _SE_BOLTS['c1']),
             (tuple(tgt[r] for r in _SE_C2_ROWS), _SE_BOLTS['c2']),
             (tuple(tgt[r] for r in _SE_C3_ROWS), _SE_BOLTS['c3']),
             ((tgt[_SE_C4_ROWS[0]],), _SE_BOLTS['c4']),
             ((tgt[_SE_C5_ROWS[0]],), _SE_BOLTS['c5']))

    R, C = _SE_ROWS, _SE_COLS
    cells = [[CellType.WALL] * C for _ in range(R)]
    for r in range(2, _SE_GATE + 1):                     # the spine
        cells[r][_SE_SPINE] = CellType.FLOOR
    for r in words['rows']:                              # the bays
        for c in range(_SE_BAY_W, _SE_BAY_E + 1):
            cells[r][c] = CellType.FLOOR
    for r, c in _SE_SHAFT_SEPS:                          # the light shafts —
        cells[r][c] = CellType.FLOOR                     # NOT the throat row

    room = Room(room_type=RoomType.ENTRY, rows=R, cols=C)
    room.cells = cells
    room.seed  = seed

    for pr, ptext in plaques:                            # full true readings
        col = _SE_PLQ_COL
        for part in ptext.split(' '):
            if part:
                room.char_runs.append(CharRun(pr, col, tuple(part), 'verdant'))
            col += len(part) + 1
    for rr, cc, text in runs:
        room.char_runs.append(CharRun(rr, cc, tuple(text), 'ancient'))
    room._ss_doors = doors                               # the shared exact-text tick
    room._se_words = words

    room.entities.append(Entity(kind='exit', row=_SE_EXIT[0], col=_SE_EXIT[1],
                                edit_immune=True))
    room.spawn_pos = (2, _SE_SPINE)
    room.exit_pos  = _SE_EXIT

    room.rebuild_indexes()
    room.par    = _SE_PAR
    room.budget = math.ceil(_SE_PAR * 1.4)  # STANDARD: the edge-hunting route wins at 1★
    room.answer = (f'j 5w dis j . 2j das j . 2j cis {ca}. j cis {cb}. '
                   f'2j das 2j . . G $')

    dungeon = Dungeon(name='The Sentence Enclosure', seed=seed)
    dungeon.rooms        = [room]
    dungeon.current_room = 0
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
_PE_ROWS, _PE_COLS = 30, 30
_PE_SPAWN  = (1, 1)
_PE_P1     = (2, 12)        # first canto: 11 content rows
_PE_B1     = 13             # the warden's rest — must survive (dip, not dap)
_PE_P2     = (14, 25)       # second canto: 12 content rows (≠ P1 — no dot pair)
_PE_GUARD  = 26             # the watch-gap: goblins on a textless (blank) row
_PE_B2     = 27             # its echo — dap's trailing blank block is BOTH rows
_PE_GATE   = 28
_PE_EXIT   = (28, 27)       # the sealed exit cell itself (plain stone until open)
_PE_TEXT0  = 3
_PE_GOB_COLS   = (17, 27)   # canto sentinels stand east, clear of the west aisle
_PE_GUARD_COLS = (8, 13, 18, 23)
_PE_SIGIL_COL  = 22         # the sigil's centre column (east, clear of the plaque)
_PE_SIGIL      = ((0, 0), (1, -1), (1, 1), (2, -2), (2, 0), (2, 2))
# Initial (row, col) of each flame: lone on the spawn row, pair on the rest,
# trio on the gate row — the sigil's shape, stretched across the hall until
# the deletions pull the three rows together.
_PE_BRAZIERS   = ((1, 22), (13, 21), (13, 23), (28, 20), (28, 22), (28, 24))
_PE_PAR    = 9              # j dip j dap $ — best old-only (j 11dd j 14dd $) pays 11


def _pe_draw_words(rng) -> dict:
    """Two short vocab words per canto row (the legion's verses)."""
    _load_vocab_tables()

    def pool(length):
        return [w for w in _VOCAB_PLAIN_BY_LEN.get(length, ())
                if w.isalpha() and w == w.lower()]

    rows = {}
    for lo, hi in (_PE_P1, _PE_P2):
        for r in range(lo, hi + 1):
            rows[r] = (rng.choice(pool(rng.choice((3, 4, 5)))),
                       rng.choice(pool(rng.choice((3, 4, 5)))))
    return rows


def build_dungeon_paragraph_enclosure(seed: int) -> Dungeon:
    """The Paragraph Enclosure (slug `paragraph_enclosure`): ip ap — the
    blank-row-bounded block under your hand, from anywhere inside it."""
    rng = random.Random(seed)
    words = _pe_draw_words(rng)

    R, C = _PE_ROWS, _PE_COLS
    cells = [[CellType.WALL] * C for _ in range(R)]
    for r in range(1, _PE_GATE):                         # the hall: full-width
        for c in range(1, C - 2):
            cells[r][c] = CellType.FLOOR
    # The watch-gap's west end is walled: `}` from the west aisle refuses a
    # walled column (it never skips ahead), so V}d from the second canto's
    # top row cannot grab exactly canto+gap for 3 keys and tie par — the
    # visual route must first pay its way east onto the verse.
    for c in range(1, _PE_GUARD_COLS[0] - 2):
        cells[_PE_GUARD][c] = CellType.WALL
    for c in range(1, _PE_EXIT[1]):                      # gate row: aisle to the seal
        cells[_PE_GATE][c] = CellType.FLOOR
    # _PE_EXIT itself stays WALL — the seal; plain stone until the measure holds.

    room = Room(room_type=RoomType.ENTRY, rows=R, cols=C)
    room.cells = cells
    room.seed  = seed

    for r, (a, b) in words.items():                      # the cantos' verses
        room.char_runs.append(CharRun(r, _PE_TEXT0, tuple(a), 'ancient'))
        room.char_runs.append(CharRun(r, _PE_TEXT0 + len(a) + 1, tuple(b), 'ancient'))
    # The gate plaque (floor runes): names the measure, and — being char runs —
    # keeps the gate row non-blank so dap's blank-run extension stops here.
    col = _PE_TEXT0
    for part in ('sign', 'and', 'seal'):
        room.char_runs.append(CharRun(_PE_GATE, col, tuple(part), 'verdant'))
        col += len(part) + 1
    room._pe_words = words

    room.entities.append(Entity(kind='exit', row=_PE_EXIT[0], col=_PE_EXIT[1],
                                edit_immune=True))
    # The sigil's flames — NOT edit_immune: a cut through a flame's row
    # succeeds and extinguishes it (the hole in the sigil shows the player
    # exactly which row should have survived); undo relights it.
    for br, bc in _PE_BRAZIERS:
        room.entities.append(Entity(kind='brazier', row=br, col=bc,
                                    hp=1, max_hp=1, ai=''))
    for lo, hi in (_PE_P1, _PE_P2):                      # one sentinel per verse row
        for r in range(lo, hi + 1):
            room.entities.append(Entity(kind='goblin', row=r,
                                        col=rng.randint(*_PE_GOB_COLS),
                                        hp=1, max_hp=1, ai=''))
    for gc in _PE_GUARD_COLS:                            # the watch-gap: no runes
        room.entities.append(Entity(kind='goblin', row=_PE_GUARD, col=gc,
                                    hp=1, max_hp=1, ai=''))

    room.spawn_pos = _PE_SPAWN
    room.exit_pos  = _PE_EXIT

    room.rebuild_indexes()
    apply_stone_fog(room)                 # the sealed exit pocket sleeps under fog
    room.par    = _PE_PAR
    room.budget = math.ceil(_PE_PAR * 1.4)  # STANDARD: the counted-cut route wins at 1★
    room.answer = 'j dip j dap $'

    dungeon = Dungeon(name='The Paragraph Enclosure', seed=seed)
    dungeon.rooms        = [room]
    dungeon.current_room = 0
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
_GMS_A_BOSS  = (2, 11)                  # he opens INSIDE the first strand ('oath'),
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
_GMS_A_LECTERNS = [
    (2,  6,  'bind oath free',           'iw', 11, 'oath', 'bind'),
    (4,  30, 'cry "vow" now',            'i"', 35, 'vow',  'cry'),
    (6,  8,  'hold (bond) tight',        'i(', 14, 'bond', 'hold'),
    (8,  32, 'keep {ward} shut',         'i{', 38, 'ward', 'keep'),
    (10, 6,  '<rite>mark</rite> gone',   'it', 12, 'mark', 'rite'),
    (12, 28, 'one. cut this. two.',      'is', 33, 'cut',  'one'),
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
        # (a fixed <b> was a hard-coding regression, caught 2026-07-17).
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
    rng = random.Random(seed)
    words = _gms_draw_words(rng)
    specs = _gms_bay_specs(words)

    # ── Room 0: the proving gallery ─────────────────────────────────────────
    R, C = _GMS_ROWS0, _GMS_COLS0
    cells = [[CellType.WALL] * C for _ in range(R)]
    for r in range(1, _GMS_GATE + 1):                    # the spine
        cells[r][_GMS_SPINE] = CellType.FLOOR
    # Bays AND their separator rows are full-width floor (the ops chain
    # bay-to-bay straight down, SE's shaft trick generalised); only the
    # THROAT is spine-only, so no east column can drop past the bolts.
    for r in range(2, _GMS_THROAT):
        for c in range(_GMS_SPINE, 52):
            cells[r][c] = CellType.FLOOR
    for c in range(_GMS_SPINE, _GMS_WATCH[1] + 1):       # gate row + pocket
        cells[_GMS_GATE][c] = CellType.FLOOR
    for dc in _GMS_BOLTS:                                # the seven bolts
        cells[_GMS_GATE][dc] = CellType.WALL
    cells[_GMS_GATE][_GMS_SEAL] = CellType.WALL          # the final seal

    gallery = Room(room_type=RoomType.ENTRY, rows=R, cols=C)
    gallery.cells = cells
    gallery.seed  = seed

    doors = []
    for bay_i, (text, target) in enumerate(specs):
        row = _GMS_BAYS[bay_i]
        col = _GMS_TEXT0                                 # the floor text
        for part in text.split(' '):
            if part:
                gallery.char_runs.append(CharRun(row, col, tuple(part), 'ancient'))
            col += len(part) + 1
        col = _GMS_PLQ_COL                               # the west plaque = the target
        for part in target.split(' '):
            if part:
                gallery.char_runs.append(CharRun(row, col, tuple(part), 'verdant'))
            col += len(part) + 1
        doors.append((target, _GMS_BOLTS[bay_i]))
    doors.append((None, _GMS_BOLTS[6]))                  # the legion bolt (goblins)
    gallery._gms_doors = tuple(doors)

    for pr_i, r in enumerate(_GMS_PARA):                 # the legion bay's canto
        a, b = words['p_rows'][pr_i]
        gallery.char_runs.append(CharRun(r, _GMS_TEXT0, tuple(a), 'ancient'))
        gallery.char_runs.append(CharRun(r, _GMS_TEXT0 + len(a) + 1, tuple(b), 'ancient'))
        for gc in (40, 46):
            gallery.entities.append(Entity(kind='goblin', row=r, col=gc,
                                           hp=1, max_hp=1, ai=''))
    col = _GMS_PLQ_COL                                   # gate-row plaque: keeps the
    for part in ('the', 'last', 'gate'):                 # gate row non-blank (stops
        gallery.char_runs.append(                        # dap's blank-run extension)
            CharRun(_GMS_GATE, col, tuple(part), 'verdant'))
        col += len(part) + 1

    # The threshold stone: a single ◆ on the spine cell of the gate row.
    # Fixed text, load-bearing — its EXISTENCE is the mechanism: it is the
    # gate row's first non-blank, so G (and any linewise park) lands at the
    # head of the row, west of the bolts; only $ (or walking) rides the
    # opened gate east past the transit cell.
    gallery.char_runs.append(CharRun(_GMS_GATE, _GMS_SPINE, ('◆',), 'ancient'))

    # The Grandmaster watches from the gate pocket. edit_immune: he anchors
    # the gate row against dG, and he is not to be killed through a wall.
    gallery.entities.append(Entity(kind='warden', row=_GMS_WATCH[0],
                                   col=_GMS_WATCH[1], hp=5, max_hp=5,
                                   ai='', tag='grandmaster', edit_immune=True))

    gallery.spawn_pos = (1, _GMS_SPINE)
    gallery.exit_pos  = _GMS_TRANSIT          # NO exit entity: stepping here descends
    gallery._gms_words = words
    gallery.rebuild_indexes()
    apply_stone_fog(gallery)
    gallery.par    = None
    gallery.budget = _GMS_BUDGET
    gallery.answer = ''                        # set below once words are drawn

    # ── Room 1: The Unmaking (the arena) ─────────────────────────────────────
    AR, AC = _GMS_A_ROWS, _GMS_A_COLS
    acells = [[CellType.WALL] * AC for _ in range(AR)]
    for r in range(1, AR - 1):
        for c in range(1, _GMS_A_SEAL_COL):              # the open hall
            acells[r][c] = CellType.FLOOR
    for r in range(1, AR - 1):                           # the sanctum pocket,
        for c in range(_GMS_A_SEAL_COL + 1, AC - 1):     # walled off by the seal
            acells[r][c] = CellType.FLOOR
    # the seal column is WALL top to bottom (opens at 0 HP); punch the throat
    # so the pocket is a real room behind it, reachable only when he is unmade.

    arena = Room(room_type=RoomType.BOSS, rows=AR, cols=AC)
    arena.cells     = acells
    arena.seed      = seed
    arena.spawn_pos = _GMS_A_SPAWN
    arena.exit_pos  = _GMS_A_EXIT

    lecterns = []
    for r, c, text, obj, cur, gone, keep in _GMS_A_LECTERNS:
        _forge_text(arena, r, c, text, 'ember')          # ember = corrupt/bound
        # the guard cell: two east of the strand's tail, so the Grandmaster
        # recoils AWAY from the player's approach without ever sitting on the
        # text he protects (the player must reach the structure to shear it).
        lecterns.append({'row': r, 'col': c, 'obj': obj, 'cursor': (r, cur),
                         'gone': gone, 'keep': keep,
                         'guard': (r, min(_GMS_A_SEAL_COL - 1, c + len(text) + 1))})
    arena._gm_lecterns = lecterns
    arena._gm_seal_col = _GMS_A_SEAL_COL
    arena._gm_last_shear = 0

    arena.entities  = [
        Entity(kind='warden', row=_GMS_A_BOSS[0], col=_GMS_A_BOSS[1],
               hp=6, max_hp=6, ai='', tag='grandmaster', edit_immune=True),
        Entity(kind='exit', row=_GMS_A_EXIT[0], col=_GMS_A_EXIT[1]),
        Entity(kind='heart_container', row=_GMS_A_HEART[0], col=_GMS_A_HEART[1]),
        Entity(kind='chest_scroll', row=_GMS_A_CHEST[0], col=_GMS_A_CHEST[1]),
    ]
    arena.search_glyph_entities = True   # /W finds the Grandmaster — the
    arena.rebuild_indexes()              # Pathfinder/Manifold search parity
    arena.par    = None
    arena.budget = _GMS_A_BUDGET         # very large — the chase is unsequenced
    arena.answer = ''                     # no karaoke: the fight has no fixed route

    # The driven canonical (see tests): the ops chain bay to bay straight
    # down; the dap's linewise park leaves the cursor at the head of the
    # gate row, and $ rides the opened gate east past the transit cell —
    # the natural stroke from the bottom of the hall (G also works, but
    # the player is already on the last line).
    gallery.answer = (f"2j w w diw 2j ci\" {words['q_cure']} 2j da[ "
                      f"2j cis {words['s_cure']}. 2j dit 2j ci{{ {words['b_cure']} "
                      f"2j dap $")
    # The arena (The Unmaking) has NO karaoke — shear the six strands in any
    # order; the Grandmaster starts inside one and slips to another whenever
    # you close on him. The seal opens when the last strand parts.

    dungeon = Dungeon(name="The Grandmaster's Sanctum", seed=seed)
    dungeon.rooms        = [gallery, arena]
    dungeon.current_room = 0
    return dungeon


# ── The Hall of Echoes (40: q @ " — macros + named registers) ────────────────
#
# Five ECHO ROWS — the same blighted verse copied down the hall, each row
# needing the SAME two-part mend (daw the junk word, x the fused ◆ off the
# last word) but bearing a DISTINCT last word, so each of the five
# exact-text bolts answers only its own row (identical targets would let
# one mended row open every bolt — the row-agnostic matching law). Two
# different edits per row means the dot can only carry HALF the work; the
# macro carries all of it: record the first mend (qa ^ w daw w x j q),
# then 4@a replays it down the hall. Replayed keys are budget-free
# (Budget.frozen — the engine's macro pricing), so par is the RECORDING
# plus three keys of replay. The dot-assisted manual mend wins at 1★
# under the hand-set budget; the :s routes (subst is already taught at
# 39) cannot name the untypable ◆ except by char-class and land ~31 —
# also 1★. The ^ at the macro's head is what makes it position-
# independent (j exits each row mid-text; ^ renormalises).
_HE_ROWS, _HE_COLS = 10, 54
_HE_SPINE  = 22
_HE_PLQ_COL = 2
_HE_TEXT0  = 24
_HE_ECHOES = (2, 3, 4, 5, 6)          # the five copies of the verse
_HE_THROAT = 7
_HE_GATE   = 8
_HE_BOLTS  = {2: 23, 3: 24, 4: 25, 5: 26, 6: 27}
_HE_EXIT   = (8, 28)                  # the FINAL SEAL, east of every bolt
_HE_PAR    = 13                       # qa j ^ w daw w x q 4@a G $ — the j RIDES
                                      # INSIDE the macro (record the row-advance,
                                      # not a separate leading j; playtest 2026-07-17)
_HE_BUDGET = 45                       # GENEROUS hand-set: the straight manual
                                      # mend (43 — the dot can't ride at all,
                                      # x is always the LAST change) wins 1★


def _he_draw_words(rng) -> dict:
    """One verse, five tails: a + junk + b shared, c1..c5 distinct."""
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

        d = {'a': draw(3), 'junk': draw(4), 'b': draw(3),
             'tails': tuple(draw(3) for _ in range(5))}
        if len(set(picks)) == len(picks):
            return d
    raise ValueError('hall_of_echoes: no distinct draw after 80 tries')


def build_dungeon_hall_of_echoes(seed: int) -> Dungeon:
    """The Hall of Echoes (slug `hall_of_echoes`): q @ " — record the mend
    once, and let the echo do the rest."""
    rng = random.Random(seed)
    words = _he_draw_words(rng)

    R, C = _HE_ROWS, _HE_COLS
    cells = [[CellType.WALL] * C for _ in range(R)]
    for r in range(1, _HE_GATE + 1):                     # the spine
        cells[r][_HE_SPINE] = CellType.FLOOR
    for r in _HE_ECHOES:                                 # the echo rows
        for c in range(_HE_SPINE, 52):
            cells[r][c] = CellType.FLOOR
    for dc in _HE_BOLTS.values():                        # gate row + bolts
        cells[_HE_GATE][dc] = CellType.WALL
    for c in range(_HE_SPINE, _HE_EXIT[1]):
        if c not in _HE_BOLTS.values():
            cells[_HE_GATE][c] = CellType.FLOOR
    # _HE_EXIT itself stays WALL — the final seal (chassis-standard).

    room = Room(room_type=RoomType.ENTRY, rows=R, cols=C)
    room.cells = cells
    room.seed  = seed

    doors = []
    for i, r in enumerate(_HE_ECHOES):
        tail = words['tails'][i]
        # The verse: `aaa jjjj bbb ◆tail` — daw pulls the junk out whole,
        # x strikes the fused glyph, and the row reads `aaa bbb tail`.
        col = _HE_TEXT0
        for part, kind in ((words['a'], 'ancient'), (words['junk'], 'ancient'),
                           (words['b'], 'ancient'), ('◆' + tail, 'ember')):
            room.char_runs.append(CharRun(r, col, tuple(part), kind))
            col += len(part) + 1
        target = f"{words['a']} {words['b']} {tail}"
        col = _HE_PLQ_COL                                # west plaque = the target
        for part in target.split(' '):
            room.char_runs.append(CharRun(r, col, tuple(part), 'verdant'))
            col += len(part) + 1
        doors.append(((target,), _HE_BOLTS[r]))
    room._ss_doors = tuple(doors)                        # the shared exact-text tick
    room._he_words = words

    room.entities.append(Entity(kind='exit', row=_HE_EXIT[0], col=_HE_EXIT[1],
                                edit_immune=True))
    room.spawn_pos = (1, _HE_SPINE)
    room.exit_pos  = _HE_EXIT

    room.rebuild_indexes()
    apply_stone_fog(room)
    room.par    = _HE_PAR
    room.budget = _HE_BUDGET
    room.answer = 'qa j ^ w daw w x q 4@a G $'

    dungeon = Dungeon(name='The Hall of Echoes', seed=seed)
    dungeon.rooms        = [room]
    dungeon.current_room = 0
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
# every step is its own bolt. Below the valley a shaft drops to the gate,
# whose EXIT sits at the gate row's own first-non-blank with a bare
# undercroft beneath it (G undershoots), so the descent is {n}_ landing
# straight onto the seal — a plain {n}j lands beside it and still owes a ^.
#
# Redesigned 2026-07-17: the old level was a pure descent — `-` went unused
# and the final `8_` tied a plain `7j` (a trailing `$` made the landing
# column moot). NOTE: `_` cannot be UNIQUELY forced — `{n}_` is exactly
# `{n-1}+`, and `_` alone is `^` — so the drop's `{n}_` merely TIES `{n-1}+`
# while beating `j`/`G`; the level teaches `_` as a first-class descent, not
# as the sole key. What IS strictly forced here is `-` (and `+`).
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
_SR_EXIT    = (24, _SR_WEST)          # the FINAL SEAL, AT the gate row's first-non-blank
_SR_BOLT_COLS = (24, 25, 26, 27, 28)  # per-word bolts, east of the exit
_SR_UNDERCROFT = 25                   # bare row — G undershoots the gate to here
_SR_CHEST   = (25, 34)                # unassigned → the relic scroll pool
_SR_PAR     = 15                      # x 2- x 2- x 6+ x 2+ x 5_


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
    rng = random.Random(seed)
    words = _sr_draw_words(rng)

    R, C = _SR_ROWS, _SR_COLS
    cells = [[CellType.WALL] * C for _ in range(R)]
    # the whole shaft is contiguous floor (rows 2..17) so -/+ can traverse
    # the blank rows between steps; the steps' words sit on rows 2,4,6,8,10.
    for r in range(_SR_STEP_ROWS[0], _SR_UNDERCROFT + 1):
        for c in range(_SR_WEST, _SR_EAST):
            cells[r][c] = CellType.FLOOR
    for dc in _SR_BOLT_COLS:                               # the per-word bolts
        cells[_SR_GATE][dc] = CellType.WALL
    cells[_SR_EXIT[0]][_SR_EXIT[1]] = CellType.WALL        # the FINAL SEAL (the fnb)

    room = Room(room_type=RoomType.ENTRY, rows=R, cols=C)
    room.cells = cells
    room.seed  = seed

    doors = []
    for k, r in enumerate(_SR_STEP_ROWS):
        col = _SR_STEP_COLS[k]
        room.char_runs.append(CharRun(r, col, tuple('◆' + words[k]), 'ember'))
        room.char_runs.append(CharRun(r, _SR_PLQ_COL, tuple(words[k]), 'verdant'))
        doors.append(((words[k],), _SR_BOLT_COLS[k]))
    room._ss_doors = tuple(doors)                        # the shared exact-text tick
    room._sr_words = words

    room.entities.append(Entity(kind='exit', row=_SR_EXIT[0], col=_SR_EXIT[1],
                                edit_immune=True))
    room.entities.append(Entity(kind='chest', row=_SR_CHEST[0], col=_SR_CHEST[1]))
    room.spawn_pos = (_SR_STEP_ROWS[_SR_SPAWN_IDX], _SR_STEP_COLS[_SR_SPAWN_IDX])
    room.exit_pos  = _SR_EXIT

    room.rebuild_indexes()
    apply_stone_fog(room)
    room.par    = _SR_PAR
    room.budget = math.ceil(_SR_PAR * 1.4)  # STANDARD: the k^/j^-walk wins at 1★
    room.answer = 'x 2- x 2- x 6+ x 2+ x 5_'

    dungeon = Dungeon(name='The Stair Rail', seed=seed)
    dungeon.rooms        = [room]
    dungeon.current_room = 0
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
# g_ lands on it and r{letter} mends it — the west plaque shows the tail's
# TRUE spelling (a single short word, so the plaque genuinely matches the
# one word you repair; the rest of the verse is navigation filler). The
# door reads that tail word as a substring, so the plaque and the goal are
# the same thing. (Redesigned 2026-07-17 from the old whole-verse exact
# door, whose one-word plaque could never match the long line.) The rest
# of the family (g* g# gi gp gP) rides the same g_family token as taught
# conveniences — their honest par-forcing collapses to ties (see the log).
_GS_ROWS, _GS_COLS = 8, 78
_GS_SPINE  = 22
_GS_PLQ_COL = 2
_GS_BAYS   = (2, 3, 4)                # adjacent — + chains them
_GS_NWORDS = (10, 12, 11)             # unequal, all two-digit e-counts
_GS_TEXT0  = 24
_GS_POOL   = (72, 73)                 # the flood: $ lands here and drowns
_GS_THROAT = 5
_GS_GATE   = 6
_GS_BOLTS  = {2: 68, 3: 69, 4: 70}
_GS_EXIT   = (6, 71)                  # the FINAL SEAL, east of every bolt
_GS_PAR    = 17                       # j g_ r{f} + g_ r{f} + g_ r{f} G $


def _gs_draw_words(rng) -> dict:
    """Three verses of len-3 words. Each TAIL word's last letter is corrupted
    to a wrong letter (g_ lands there, r{fix} mends it); the true tails are
    globally unique so the door's substring read is unambiguous."""
    _load_vocab_tables()
    pool = [w for w in _VOCAB_PLAIN_BY_LEN.get(3, ())
            if w.isalpha() and w == w.lower()]
    poolset = set(pool)
    alph = 'abcdefghijklmnopqrstuvwxyz'
    for _ in range(200):
        rows = [tuple(rng.choice(pool) for _ in range(n)) for n in _GS_NWORDS]
        tails = [r[-1] for r in rows]
        allwords = [w for r in rows for w in r]
        if len(set(tails)) != 3:
            continue
        if any(allwords.count(t) != 1 for t in tails):        # tails unique in the buffer
            continue
        corrupts, fixes, ok = [], [], True
        for t in tails:
            wrong = rng.choice([c for c in alph if c != t[-1]])
            corr = t[:-1] + wrong
            if corr in poolset or corr in allwords:           # corruption ≠ any real word
                ok = False
                break
            corrupts.append(corr)
            fixes.append(t[-1])                                # the letter r must type
        if ok:
            return {'rows': rows, 'tails': tails, 'corrupts': corrupts, 'fixes': fixes}
    raise ValueError('g_sanctum: no clean draw after 200 tries')


def build_dungeon_g_sanctum(seed: int) -> Dungeon:
    """The Last Reach (slug `g_sanctum`): the g-family — the last glyph,
    named in one reach."""
    rng = random.Random(seed)
    words = _gs_draw_words(rng)

    R, C = _GS_ROWS, _GS_COLS
    cells = [[CellType.WALL] * C for _ in range(R)]
    for r in range(1, _GS_GATE + 1):                     # the spine
        cells[r][_GS_SPINE] = CellType.FLOOR
    for r in _GS_BAYS:                                   # the verse rows
        for c in range(_GS_SPINE, _GS_POOL[1] + 1):
            cells[r][c] = CellType.FLOOR
        for c in _GS_POOL:                               # the flood at the brink
            cells[r][c] = CellType.WATER
    for c in range(_GS_SPINE, _GS_EXIT[1]):              # gate row + bolts
        cells[_GS_GATE][c] = CellType.FLOOR
    for dc in _GS_BOLTS.values():
        cells[_GS_GATE][dc] = CellType.WALL
    # _GS_EXIT itself stays WALL — the final seal (chassis-standard).

    room = Room(room_type=RoomType.ENTRY, rows=R, cols=C)
    room.cells = cells
    room.seed  = seed

    doors = []
    for i, r in enumerate(_GS_BAYS):
        verse = words['rows'][i]
        col = _GS_TEXT0
        for k, part in enumerate(verse):
            # the last word wears its CORRUPT spelling (last letter wrong);
            # g_ lands on that letter and r{fix} mends it.
            text = words['corrupts'][i] if k == len(verse) - 1 else part
            room.char_runs.append(CharRun(r, col, tuple(text), 'ancient'))
            col += len(part) + 1
        # West plaque: the tail word's TRUE spelling — a single short word
        # that genuinely matches the one word you repair.
        room.char_runs.append(CharRun(r, _GS_PLQ_COL, tuple(words['tails'][i]),
                                      'verdant'))
        # substring door: opens when the true tail reads on the floor.
        doors.append((words['tails'][i], (_GS_GATE, _GS_BOLTS[r])))
    room._wla_doors = tuple(doors)                       # the substring tick
    room._gs_words = words

    room.entities.append(Entity(kind='exit', row=_GS_EXIT[0], col=_GS_EXIT[1],
                                edit_immune=True))
    room.spawn_pos = (1, _GS_SPINE)
    room.exit_pos  = _GS_EXIT

    room.rebuild_indexes()
    apply_stone_fog(room)
    room.par    = _GS_PAR
    room.budget = math.ceil(_GS_PAR * 1.4)  # STANDARD: the counted-e walk wins at 1★
    f = words['fixes']
    room.answer = f'j g_ r{f[0]} + g_ r{f[1]} + g_ r{f[2]} G $'

    dungeon = Dungeon(name='The Last Reach', seed=seed)
    dungeon.rooms        = [room]
    dungeon.current_room = 0
    return dungeon


# ── The Buried Word (42, bonus: g* and the n-chain) ──────────────────────────
#
# One standing word — the player spawns ON it (e.g. `set`) — and three
# echoes of it BURIED inside REAL longer words down the hall (`reset`,
# `onset`, `upset`). * (whole-word) finds nothing: the word never stands
# alone below the ledge. g* takes it literally and walks the chain; n
# carries on. Each real word has ONE corrupt letter — the cell just before
# the buried word — so g* still finds it; h steps onto the corruption and
# r{fix} mends it. The west plaque shows the word's TRUE spelling (which the
# substring door reads, so the plaque and the goal are the same). The
# /typed-search rival costs a few keys more — that margin is the whole game.
# (Redesigned 2026-07-17: real words that CONTAIN the target — the true g*
# use case — in place of the old nonsense {pre}{word}{post} concatenations.)
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
_BW_PAR     = 17                      # g* h r{f} l n h r{f} l n h r{f} G $


def _bw_draw_words(rng) -> dict:
    """A short target word (len 3) and three REAL longer words that contain
    it (buried, with a non-empty prefix). Each host word gets ONE corrupt
    letter — the cell just before the buried word — so g* still finds the
    target; h steps onto the corruption, r{fix} mends it."""
    _load_vocab_tables()

    def pool(length):
        return [w for w in _VOCAB_PLAIN_BY_LEN.get(length, ())
                if w.isalpha() and w == w.lower()]

    allwords = set(w for L in range(4, 8) for w in pool(L))
    hosts_by_len = [w for L in range(4, 8) for w in pool(L)]
    targets = [w for w in pool(3)]
    alph = 'abcdefghijklmnopqrstuvwxyz'
    for _ in range(400):
        t = rng.choice(targets)
        # real words that BURY the target once, past position 0 (a prefix to corrupt)
        hosts = [w for w in hosts_by_len
                 if w != t and w.count(t) == 1 and w.index(t) >= 1]
        if len(hosts) < 3:
            continue
        picks = rng.sample(hosts, 3)
        corrupts, fixes, ok = [], [], True
        for word in picks:
            idx = word.index(t)                        # corrupt the cell before it
            correct = word[idx - 1]
            wrong = rng.choice([c for c in alph if c != correct])
            corr = word[:idx - 1] + wrong + word[idx:]
            if corr in allwords or corr.count(t) != 1:
                ok = False                             # corruption ≠ real word;
                break                                  # target still buried once
            corrupts.append(corr)
            fixes.append(correct)
        if ok:
            return {'word': t, 'hosts': picks, 'corrupts': corrupts, 'fixes': fixes}
    raise ValueError('buried_word: no clean draw after 400 tries')


def build_dungeon_buried_word(seed: int) -> Dungeon:
    """The Buried Word (slug `buried_word`, bonus): g* — the word hunted
    inside other words."""
    rng = random.Random(seed)
    words = _bw_draw_words(rng)
    w = words['word']

    R, C = _BW_ROWS, _BW_COLS
    cells = [[CellType.WALL] * C for _ in range(R)]
    for r in range(1, _BW_GATE + 1):                     # the spine
        cells[r][_BW_SPINE] = CellType.FLOOR
    for c in range(_BW_SPINE, 32):                       # the standing ledge
        cells[1][c] = CellType.FLOOR
    for r in _BW_BAYS:                                   # the echo rows
        for c in range(_BW_SPINE, 52):
            cells[r][c] = CellType.FLOOR
    for c in range(_BW_SPINE, _BW_EXIT[1]):              # gate row + bolts
        cells[_BW_GATE][c] = CellType.FLOOR
    for dc in _BW_BOLTS.values():
        cells[_BW_GATE][dc] = CellType.WALL
    # _BW_EXIT itself stays WALL — the final seal (chassis-standard).

    room = Room(room_type=RoomType.ENTRY, rows=R, cols=C)
    room.cells = cells
    room.seed  = seed

    room.char_runs.append(CharRun(*_BW_STAND, tuple(w), 'verdant'))
    doors = []
    for i, r in enumerate(_BW_BAYS):
        host = words['hosts'][i]                         # the true real word
        corr = words['corrupts'][i]                      # …with one wrong letter
        room.char_runs.append(CharRun(r, _BW_TEXT0, tuple(corr), 'ember'))
        # west plaque: the host word's TRUE spelling — what the door reads.
        room.char_runs.append(CharRun(r, _BW_PLQ_COL, tuple(host), 'verdant'))
        doors.append((host, (_BW_GATE, _BW_BOLTS[r])))
    room._wla_doors = tuple(doors)                       # the substring tick
    room._bw_words = words

    room.entities.append(Entity(kind='exit', row=_BW_EXIT[0], col=_BW_EXIT[1],
                                edit_immune=True))
    room.spawn_pos = _BW_STAND
    room.exit_pos  = _BW_EXIT

    room.rebuild_indexes()
    apply_stone_fog(room)
    room.par    = _BW_PAR
    room.budget = math.ceil(_BW_PAR * 1.4)
    # r mends in place (no shift), so l steps back onto the word before n —
    # else n re-finds THIS row's word (which now sits one cell ahead of the
    # cursor). The old ◆-x route shifted the word onto the cursor for free.
    f = words['fixes']
    room.answer = f'g* h r{f[0]} l n h r{f[1]} l n h r{f[2]} G $'

    dungeon = Dungeon(name='The Buried Word', seed=seed)
    dungeon.rooms        = [room]
    dungeon.current_room = 0
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
_WI_PAR    = 44                       # i{w1} 2+ yl w P gi␣{w2} 2+ 2w P
                                      # gi␣{w3} 2+ 3w P gi␣{w4} G $ (pinned)


def _wi_draw_words(rng) -> tuple:
    """The four quarters of the inscription (len 4 each, all distinct)."""
    _load_vocab_tables()
    pool = [w for w in _VOCAB_PLAIN_BY_LEN.get(4, ())
            if w.isalpha() and w == w.lower()]
    for _ in range(80):
        ws = tuple(rng.choice(pool) for _ in range(4))
        if len(set(ws)) == 4:
            return ws
    raise ValueError('wet_ink: no distinct draw after 80 tries')


def build_dungeon_wet_ink(seed: int) -> Dungeon:
    """The Wet Ink (slug `wet_ink`, bonus): gi — the pen returns to where
    it left the page. One 16-glyph inscription in the ledge's west wall;
    only the first quarter shows. Beneath it, a gallery of cold braziers
    and one standing flame: carry fire (yl … p) to a brazier and its
    firelight reveals the next quarter — but a brazier only takes the
    flame once the quarter BEFORE it is written on the ledge (the fuel
    gate, _wet_ink_tick), so the scribe must leave the page and return
    to it, three times over."""
    rng = random.Random(seed)
    ws = _wi_draw_words(rng)
    full = ' '.join(ws)

    R, C = _WI_ROWS, _WI_COLS
    cells = [[CellType.WALL] * C for _ in range(R)]
    for c in range(_WI_SPINE, 47):                       # the writing ledge
        cells[_WI_LEDGE][c] = CellType.FLOOR
    for r in range(_WI_LEDGE, _WI_GATE + 1):             # the spine, down
        cells[r][_WI_SPINE] = CellType.FLOOR
    for c in range(_WI_SOURCE[1], _WI_SPINE):            # the brazier gallery
        cells[_WI_BRZ_ROW][c] = CellType.FLOOR
    for c in range(_WI_SPINE, _WI_EXIT[1]):              # gate row + the bolt
        cells[_WI_GATE][c] = CellType.FLOOR
    cells[_WI_GATE][_WI_BOLT] = CellType.WALL
    # _WI_EXIT itself stays WALL — the final seal.

    room = Room(room_type=RoomType.ENTRY, rows=R, cols=C)
    room.cells = cells
    room.seed  = seed

    # The plaque (west wall of the ledge): the WHOLE inscription, laid at
    # build as one run per quarter (a wall-gap column between them reads
    # as the space); quarters 2-4 are fogged and revealed by firelight.
    for k, w in enumerate(ws):
        room.char_runs.append(CharRun(_WI_LEDGE, _WI_PLQ_COL + 5 * k,
                                      tuple(w), 'verdant'))
    # The source flame, and embers on every cold brazier.
    room.char_runs.append(CharRun(*_WI_SOURCE, (_QM_FLAME,), 'flame'))
    for (br, bc) in _WI_BRAZIERS:
        room.char_runs.append(CharRun(br, bc, (_QM_EMBERS,), 'pedestal'))
    room._ss_doors = (((full,), _WI_BOLT),)              # the full inscription
    room._wi_words = ws
    # The fuel gate starts source-only; _wet_ink_tick widens it as the
    # quarters are written (read by _flame_paste_blocked).
    room._qm_chain = (_WI_SOURCE,)
    room._flame_block_msg = ('The flame gutters out — only a brazier whose '
                             'quarter is written will hold it.')

    room.entities.append(Entity(kind='exit', row=_WI_EXIT[0], col=_WI_EXIT[1],
                                edit_immune=True))
    room.spawn_pos = (_WI_LEDGE, _WI_INK0)
    room.exit_pos  = _WI_EXIT

    room.rebuild_indexes()
    # SCRIPTED fog on the plaque's WALL cells (the fog-audit only polices
    # stone-hidden FLOOR): quarter k+1 (and the gap before it) is dark
    # until brazier k burns.
    room._wi_seg_fog = tuple(
        frozenset((_WI_LEDGE, _WI_PLQ_COL + 5 * k - 1 + i) for i in range(5))
        for k in (1, 2, 3))
    room.fog_cells = set().union(*room._wi_seg_fog)
    room.par    = _WI_PAR
    room.budget = math.ceil(_WI_PAR * 1.4)
    room.answer = (f'i{ws[0]} 2+ yl w P gi␣{ws[1]} 2+ 2w P '
                   f'gi␣{ws[2]} 2+ 3w P gi␣{ws[3]} G $')

    dungeon = Dungeon(name='The Wet Ink', seed=seed)
    dungeon.rooms        = [room]
    dungeon.current_room = 0
    return dungeon


# (The Stamp Run — a gp level — was designed and CUT 2026-07-17: the
# engine gives gp no niche. Ordinary paste self-chains at line end, the
# Beacon flame-fill is insert-plus-tumble, and p+l ties gp everywhere
# else. Recorded in the build log; gp remains a granted convenience.)


# ── The Binder's Reliquary (:h — the Codex) ─────────────────────────────────
#
# A second reliquary (display 14.1, after the Seekers' Labyrinth), on the
# FIRST Reliquary's two-chamber chassis — but the divider is WATER, not
# stone (redesigned 2026-07-17 after playtest). Water is transparent: the
# binder's pass-word is legible on the far shore. MIST (fog) lies on the
# channel, so every line-scoped scan stops at the bank — $ / 0 / ^ by
# _cross_water's fog check, f/F/t/T by the scan-fog law — while teleports
# (G/H/M/L/{n}G) land on the row's first standable, the NEAR shore. Search
# alone crosses: /{word}⏎ — the Labyrinth's lesson, cashed in. The bound
# Codex waits BEYOND the
# word (chest after crossing, never before), so :h cannot be opened until
# the Codex is actually in hand (the command is gated on the 'readers_key'
# grant, not just the level's 'help' token).
#
# Reward room: par None (reliquaries are unstarred), generous fixed budget.
_BND_ROWS, _BND_COLS = 7, 24
_BND_AR          = 3                  # the action row: spawn, word, chest, exit
_BND_WATER_COLS  = (12, 13)           # full-height channel; left 1..11, right 14..22
_BND_SPAWN       = (3, 1)
_BND_WORD_COL    = 15                 # pass-word cols 15..19 (len 5)
_BND_CHEST       = (3, 21)
_BND_EXIT        = (3, 22)
_BND_FRIEZE_ROWS = (1, 5)             # LEFT chamber only — the far shore is bare
_BND_BUDGET      = 30


def _bnd_draw_word(rng) -> str:
    """The binder's pass-word: one len-5 vocab word."""
    _load_vocab_tables()
    pool = [w for w in _VOCAB_PLAIN_BY_LEN.get(5, ())
            if w.isalpha() and w == w.lower()]
    return rng.choice(pool)


def build_dungeon_binders_reliquary(seed: int) -> Dungeon:
    """The Binder's Reliquary (slug `binders_reliquary`): the Codex (:h)."""
    rng = random.Random(seed)
    word = _bnd_draw_word(rng)

    R, C = _BND_ROWS, _BND_COLS
    cells = [[CellType.WALL] * C for _ in range(R)]
    for r in range(1, R - 1):
        for c in range(1, C - 1):
            cells[r][c] = (CellType.WATER if c in _BND_WATER_COLS
                           else CellType.FLOOR)

    room = Room(room_type=RoomType.ENTRY, rows=R, cols=C)
    room.cells = cells
    room.seed  = seed

    # The pass-word on the far shore — the only text across the water, so
    # the crossing search is unambiguous. Friezes stay on the near shore.
    room.char_runs.append(CharRun(_BND_AR, _BND_WORD_COL, tuple(word), 'ember'))
    _place_frieze_sym(room, rng, _BND_FRIEZE_ROWS, 1, _BND_WATER_COLS[0] - 1)
    room._bnd_word = word

    # Mist on the water: permanent fog over the channel only. The far shore
    # stays visible and searchable; the scans stop at the bank.
    room.fog_cells  = {(r, c) for r in range(1, R - 1) for c in _BND_WATER_COLS}
    room.mist_cells = set(room.fog_cells)         # permanent: reveals skip it

    # The Codex's own first page, bound in at the water's edge.
    room._codex_extra = ((
        "The Binder's Colophon",
        ['',
         '  Bound at the water\'s edge. Every scroll you',
         '  carry is stitched into this book; ask for any',
         '  page by name — :h {name} — and it will open.',
         ''],
    ),)

    room.entities = [
        Entity(kind='chest_scroll', row=_BND_CHEST[0], col=_BND_CHEST[1],
               scroll_id='readers_key'),
        Entity(kind='exit', row=_BND_EXIT[0], col=_BND_EXIT[1],
               edit_immune=True),
    ]
    room.spawn_pos = _BND_SPAWN
    room.exit_pos  = _BND_EXIT

    room.rebuild_indexes()
    room.par    = None                            # reward room, like the first
    room.budget = _BND_BUDGET
    # /{word}⏎ lands on the word's first glyph; e to its end, step to the
    # lectern, loot, step out. (Enter is free; '/' + the word are charged.)
    room.answer = f'/{word}⏎ e 2l x l'

    dungeon = Dungeon(name="The Binder's Reliquary", seed=seed)
    dungeon.rooms        = [room]
    dungeon.current_room = 0
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
#   • 'vault' sits beside the red door at the very end: /vault⏎ lands the search.
# Decor words (also vocab) flesh out the halls; none contains 'maze' or 'vault',
# so they never perturb the two taught searches.
#
# Two keys gate two colour-matched doors, and the GOLD key sits to the LEFT of the
# 3rd 'maze' — so reaching the RED key demands a backward jump:
#   • 3rd 'maze' (11,15): the GOLD key is just left of it at (11,11).
#   • 2nd 'maze' (5,1): a GOLD door (5,6) seals the RED key in a one-cell stub (5,7).
#   • the RED door (1,18) caps the exit (1,19); 'vault' (1,7) shares its corridor.
#
# Optimal route (par 18):  * n 0 x N $ p l x /vault⏎ $ p l   (/vault⏎ = len+1: '/' charged, Enter free)
#   * n    — 'maze'(1,1) → 2nd 'maze'(5,1) [a decoy] → 3rd 'maze'(11,15).
#   0 x    — 0 halts on the gold key at (11,11) (left of the maze); x cuts it.
#   N      — reverse the search: back to the 2nd 'maze'(5,1), the passed decoy.
#   $ p l  — $ halts at (5,5) before the gold door; p opens it (gold), l → red key.
#   x      — cut the red key (the register now holds red).
#   /vault⏎— teleport to 'vault'(1,7), the exit corridor.
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
_SEEKERS_ANSWER       = '* n 0 x N $ p l x /vault⏎ $ p l'


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
    rng = random.Random(seed)
    ROWS, COLS = len(_SEEKERS_MAZE), len(_SEEKERS_MAZE[0])
    dungeon   = Dungeon(name="The Seekers' Labyrinth", seed=seed)
    composite = Room(rows=ROWS, cols=COLS, room_type=RoomType.ENTRY)
    composite.cells = [
        [CellType.CORRIDOR if _SEEKERS_MAZE[r][c] == '.' else CellType.WALL
         for c in range(COLS)]
        for r in range(ROWS)
    ]
    composite.seed = seed

    # ── Reserved cells: the path-critical words + the five entities ───────────
    reserved: set = {_SEEKERS_GOLD_KEY, _SEEKERS_GOLD_DOOR, _SEEKERS_RED_KEY,
                     _SEEKERS_RED_DOOR, _SEEKERS_EXIT}
    char_runs: list = []
    for (r, c) in _SEEKERS_WORD_POS:
        char_runs.append(CharRun(row=r, col=c, symbols=tuple(_SEEKERS_WORD), kind='ember'))
        reserved |= {(r, c + i) for i in range(len(_SEEKERS_WORD))}
    dr, dc = _SEEKERS_DOORWORD_POS
    char_runs.append(CharRun(row=dr, col=dc, symbols=tuple(_SEEKERS_DOORWORD), kind='ember'))
    reserved |= {(dr, dc + i) for i in range(len(_SEEKERS_DOORWORD))}

    # ── Decor: fill the OTHER runs with vocab tokens (scenery + search fodder) ─
    pool = _seekers_decor_pool(rng)
    for (r, s, e) in _seekers_runs(composite.cells):
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
            char_runs.append(CharRun(row=r, col=c, symbols=tuple(word),
                                     kind=rng.choice(('ancient', 'verdant', 'ember'))))
            c += L + 1                     # one-cell gap between words

    composite.char_runs = char_runs
    composite.spawn_pos = _SEEKERS_SPAWN
    composite.exit_pos  = _SEEKERS_EXIT
    composite.entities  = [
        Entity(kind='floor_key',   row=_SEEKERS_GOLD_KEY[0],  col=_SEEKERS_GOLD_KEY[1],  tag='gold'),
        Entity(kind='locked_door', row=_SEEKERS_GOLD_DOOR[0], col=_SEEKERS_GOLD_DOOR[1], tag='gold'),
        Entity(kind='floor_key',   row=_SEEKERS_RED_KEY[0],   col=_SEEKERS_RED_KEY[1],   tag='red'),
        Entity(kind='locked_door', row=_SEEKERS_RED_DOOR[0],  col=_SEEKERS_RED_DOOR[1],  tag='red'),
        Entity(kind='exit',        row=_SEEKERS_EXIT[0],      col=_SEEKERS_EXIT[1]),
    ]
    composite.par    = _SEEKERS_PAR
    composite.budget = math.ceil(_SEEKERS_PAR * 1.4)
    composite.answer = _SEEKERS_ANSWER

    composite.rebuild_indexes()
    dungeon.rooms        = [composite]
    dungeon.current_room = 0
    return dungeon


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
    edges: '/W⏎'/'?W⏎' + k·n reaches the k-th match forward/backward of any word W
    (cost len(W)+1+k — '/' charged, closing Enter free); '*' + k·n does the same
    for the word under the cursor (cost 1+k).  no_search drops all search edges —
    the foot-only bound that
    proves search is required (it dwarfs the budget).
    """
    from engine.player import Player
    from engine.motion import apply_motion
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
                out.append((len(W) + 1 + k, tgt, f'/{W}⏎' + 'n' * k))
            bwd = [m for m in reversed(ms) if m < cur] + [m for m in reversed(ms) if m >= cur]
            for k, tgt in enumerate(bwd):
                out.append((len(W) + 1 + k, tgt, f'?{W}⏎' + 'n' * k))
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
#   ma · ?xyzzy⏎ h x (key) · `a $ (home, then line-end) · p l → exit
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
# The SECOND magic word (Colossal Cave's other teleporter) — the # lesson
# (2026-07-17): the ? leg lands you in the xyzzy pocket, where plugh wakes
# from a SCRIPTED fog (fogged text is unsearchable, so ?plugh from spawn
# finds nothing — the fresh-word law); its backward twin sits in a second
# misted pocket holding the gold key, its forward decoys price out * (a
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
_WP_ANSWER = "ma ?xyzzy⏎ w # h x `a $ p l"


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
    REBALANCING LEVERS, post-playtesting (only if farming proves undesirable):
    (a) persist looted vault chests per-player, mirroring the collected_hearts
    mechanism, so each chest yields at most one relic ever; and/or (b) a
    warden/summoner guarding the vault band. Both need real tuning/judgement, so
    deferred until there are more players than Joseph testing."""
    rng = random.Random(seed)
    R, C = _WP_ROWS, _WP_COLS
    dungeon = Dungeon(name='The Waypoint Sanctum', seed=seed)
    composite = Room(rows=R, cols=C, room_type=RoomType.ENTRY)
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
    # (Waterworks conversion 2026-07-18: the pocket ring, the sanctum seals
    # and the vault boxes are MISTED WATER, not stone — everything is
    # visible, per the stone-fog law, while walking / scans stay barred:
    # water blocks feet, the mist on it blocks $ / 0 / ^ / f scans, and
    # { } skip flooded rows exactly as they skipped the walls.)
    mist: set = set()

    def moat(r, c):
        cells[r][c] = CellType.WATER
        mist.add((r, c))

    _pkt_lo = _WP_PKT1_SPAN[0] - 1                            # left bank (col 28)
    _pkt_hi = _WP_PKT1_SPAN[1] + 1                            # right bank (col 41)
    for c in range(_pkt_lo, _pkt_hi + 1):
        moat(1, c)                                           # water over the pocket
    moat(2, _pkt_lo)                                         # left bank
    moat(2, _pkt_hi)                                         # right bank
    # Pocket 2 — the # pocket: the gold key + plugh's backward twin, ringed
    # the same way (misted water: visible per the stone-fog law, searchable,
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
        entities += [Entity(kind='locked_door', row=7, col=X, tag='blue'),
                     Entity(kind=kind, row=9, col=X, scroll_id=sid)]
        vault_cells |= {(7, X), (8, X), (9, X)}
    for c in range(1, C - 1):
        if cells[7][c] == CellType.WALL:
            moat(7, c)                            # the lower seal, flooded too
    composite.cells = cells
    composite.seed = seed
    composite.fog_cells  = set(mist)              # mist on every converted pool
    composite.mist_cells = set(mist)              # …permanent: reveals skip it
    # (the plugh fog is added below, once the runs exist — NOT mist: the
    # tick lifts it, and mist_cells would make the reveal skip it)

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
    char_runs = [CharRun(row=_WP_KEY_WORD_POS[0], col=_WP_KEY_WORD_POS[1],
                         symbols=tuple(_WP_KEYWORD), kind='ember')]
    for (dr, dc) in _WP_DECOY_POS:
        char_runs.append(CharRun(row=dr, col=dc, symbols=tuple(_WP_KEYWORD), kind='ember'))
    for (dr, dc) in (_WP_W2_POCKET1, _WP_W2_POCKET2, *_WP_W2_DECOYS):
        char_runs.append(CharRun(row=dr, col=dc, symbols=tuple(_WP_WORD2), kind='ember'))
    # BOTH sanctum plughs sleep under SCRIPTED fog (the Wet Ink pattern):
    # a fogged word is unsearchable — by EVERY search uniformly, # included
    # — so ?plugh from the spawn finds nothing (with only the stone fogged,
    # the visible pocket-2 twin was a 15-key skip straight to the key —
    # caught 2026-07-17). The level tick wakes the pair the moment the ?
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
                char_runs.append(CharRun(row=r, col=c, symbols=tuple(word),
                                         kind=rng.choice(('ancient', 'verdant', 'ember'))))
                c += L + 1
            else:
                c += span + 1

    composite.char_runs = char_runs
    composite.fog_cells |= _plugh_fog
    composite._wp_plugh_fog = _plugh_fog
    composite.spawn_pos = _WP_SPAWN
    composite.exit_pos  = _WP_EXIT
    entities += [
        Entity(kind='chest_scroll', row=_WP_SCROLL[0],      col=_WP_SCROLL[1], scroll_id='setnum'),
        Entity(kind='locked_door',  row=_WP_SCROLL_DOOR[0], col=_WP_SCROLL_DOOR[1], tag='blue'),
        Entity(kind='locked_door',  row=_WP_LOCK[0],        col=_WP_LOCK[1],        tag='gold'),
        Entity(kind='exit',         row=_WP_EXIT[0],        col=_WP_EXIT[1]),
        Entity(kind='floor_key',    row=_WP_KEY[0],         col=_WP_KEY[1],         tag='gold'),
    ]
    for (gr, gc) in goblins:
        entities.append(Entity(kind='goblin', row=gr, col=gc, max_hp=1, ai='chase'))
    composite.entities = entities
    composite.par    = _WP_PAR
    composite.budget = math.ceil(_WP_PAR * 1.4)
    composite.answer = _WP_ANSWER

    composite.rebuild_indexes()
    dungeon.rooms        = [composite]
    dungeon.current_room = 0
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
    # Extremely unlikely fallback: shortest words padded — caller widths make this dead code.
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
    dungeon   = Dungeon(name='The Bracket Vaults', seed=seed)
    ROWS, COLS = _BRACKET_VAULTS_ROWS, _BRACKET_VAULTS_COLS

    cells = [[CellType.WALL] * COLS for _ in range(ROWS)]
    composite = Room(rows=ROWS, cols=COLS, room_type=RoomType.ENTRY)
    composite.cells = cells
    composite.seed  = seed

    OPN = _BRACKET_VAULTS_BRACKET_OPEN   # 4
    CLS = _BRACKET_VAULTS_BRACKET_CLOSE  # 54
    EXC = _BRACKET_VAULTS_CLOSE_R5       # 53  (row-5 closing bracket col)

    # ── Carve corridors ───────────────────────────────────────────────────────
    for r in _BRACKET_VAULTS_CORR_ROWS:
        for c in range(1, COLS - 1):
            cells[r][c] = CellType.CORRIDOR

    # ── Carve turns ───────────────────────────────────────────────────────────
    # Right turn: col CLS rows 1-3 (the j-path down from C1 to C2)
    cells[2][CLS] = CellType.CORRIDOR
    # Left turn: col OPN rows 3-5 (the j-path down from C2 to C3)
    cells[4][OPN] = CellType.CORRIDOR

    # ── Water in the gap and middle rows ──────────────────────────────────────
    # Rows 2 and 4: water everywhere except the single CORRIDOR turn cells.
    # Row 3: water everywhere except the two bracket cells (OPN and CLS).
    # % scans through water (not a WALL/WOOD_WALL) to reach the matching bracket;
    # manual h/l are blocked because is_passable returns False for WATER.
    for c in range(1, COLS - 1):
        if cells[2][c] != CellType.CORRIDOR:
            cells[2][c] = CellType.WATER
        if cells[4][c] != CellType.CORRIDOR:
            cells[4][c] = CellType.WATER
        if c != OPN and c != CLS:
            cells[3][c] = CellType.WATER

    # ── Moat + decoy goblin pit (anti-teleport) ───────────────────────────────
    # The exit sits on row 5, which used to be the LAST line — so G (last line) and
    # L (bottom of screen) teleported straight to it and `% l` finished in 3, under
    # par. Add a full-water moat (row 6) and a corridor decoy (row 7) BELOW it: now
    # G/L land on row 7, sealed off from the snake by the moat, in a pit of goblins.
    # The real exit on row 5 is interior and unreachable by any teleport.
    MOAT, DECOY = _BRACKET_VAULTS_MOAT_ROW, _BRACKET_VAULTS_DECOY_ROW
    for c in range(1, COLS - 1):
        cells[MOAT][c]  = CellType.WATER
        cells[DECOY][c] = CellType.CORRIDOR

    # Anti-teleport pockets on EVERY snake row (2-5): a CORRIDOR cell at col 1 (holding an
    # unmatched ) — see below) plus a stone WALL at col 2. A {N}G goto-line teleport onto
    # any snake rung lands on that col-1 ) (the row's first-non-blank), sealed off from the
    # snake by the wall — scans ($/%/f/0/^) cross water but HALT at a wall — so it can never
    # reach the snake proper. Row 1 needs no pocket: its first-non-blank IS the snake's start
    # ( at col 4, and finishing from there already costs more than par.
    for br in (2, 3, 4, 5):
        cells[br][1] = CellType.CORRIDOR
        cells[br][2] = CellType.WALL

    # ── Place bracket CharRuns ────────────────────────────────────────────
    # Single-char CharRun at each bracket position so _bracket_at() in
    # motion.py can identify them via the character at that cell.  Row 5's ) sits
    # at EXC (one left of CLS); the exit is at CLS, so the final % lands on ) at
    # EXC and one l steps onto the exit.
    rng = random.Random(seed)
    _kinds = ('ancient', 'verdant', 'ember')

    runes: list[CharRun] = []
    for row in _BRACKET_VAULTS_CORR_ROWS:
        kind_open  = rng.choice(_kinds)
        kind_close = rng.choice(_kinds)
        close_col  = EXC if row == 5 else CLS
        runes.append(CharRun(row=row, col=OPN, symbols=('(',), kind=kind_open))
        runes.append(CharRun(row=row, col=close_col, symbols=(')',), kind=kind_close))
    # Decorative brackets on the decoy row (so it reads like the rest; they lead nowhere).
    runes.append(CharRun(row=DECOY, col=OPN, symbols=('(',), kind=rng.choice(_kinds)))
    runes.append(CharRun(row=DECOY, col=CLS, symbols=(')',), kind=rng.choice(_kinds)))

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
            runes.append(CharRun(row=wrow, col=wc, symbols=tuple(w), kind=rng.choice(_kinds)))
            wc += len(w) + 1

    # Lone unmatched ) in each snake row's col-1 pocket (rows 2-5): it is that row's
    # first-non-blank, so a {N}G teleport lands on it. From a ) the % scan runs LEFT, hits
    # the col-0 wall and finds no match; the col-2 WALL blocks l/w/e/f/$/% rightward — so the
    # teleport is trapped in the pocket with no route to the snake or the exit.
    for br in (2, 3, 4, 5):
        runes.append(CharRun(row=br, col=1, symbols=(')',), kind=rng.choice(_kinds)))

    composite.char_runs = runes

    # ── Entry and exit ────────────────────────────────────────────────────────
    composite.spawn_pos    = _BRACKET_VAULTS_ENTRY
    composite.exit_pos = _BRACKET_VAULTS_EXIT_POS
    composite.entities = [Entity(kind='exit',
                                 row=_BRACKET_VAULTS_EXIT_POS[0], col=_BRACKET_VAULTS_EXIT_POS[1])]
    # Floor key on the row-2 turn cell + locked door guarding the exit: the exit can't be
    # reached by simply landing on it (a {N}G teleport is trapped in a col-1 pocket anyway),
    # and the key sits where only the snake reaches it. Pick up with x, unlock with p.
    composite.entities.append(Entity(kind='floor_key',
                                     row=_BRACKET_VAULTS_KEY_POS[0], col=_BRACKET_VAULTS_KEY_POS[1]))
    composite.entities.append(Entity(kind='locked_door',
                                     row=_BRACKET_VAULTS_DOOR_POS[0], col=_BRACKET_VAULTS_DOOR_POS[1]))
    # Goblins guarding the decoy pit — they punish a teleport-cheese (G/L) and can't
    # cross the moat to the snake.
    for gc in _BRACKET_VAULTS_DECOY_GOBLINS:
        composite.entities.append(Entity(kind='goblin', row=DECOY, col=gc, max_hp=1, ai='chase'))

    composite.rebuild_indexes()

    par, path = _par_bracket_vaults(composite, use_percent=True, return_path=True)
    if par is None:
        par, path = _BRACKET_VAULTS_PAR, _BRACKET_VAULTS_ANSWER
    composite.par    = par
    composite.budget = math.ceil(par * 1.4)
    composite.answer = path

    dungeon.rooms        = [composite]
    dungeon.current_room = 0
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
    dungeon = Dungeon(name='The Lineheads', seed=seed)
    ROWS, COLS = _LINEHEADS_ROWS, _LINEHEADS_COLS

    cells = [[CellType.WALL] * COLS for _ in range(ROWS)]
    composite = Room(rows=ROWS, cols=COLS, room_type=RoomType.ENTRY)
    composite.cells = cells
    composite.seed  = seed

    # ── Carve the fixed layout (see _LINEHEADS_PASSABLE above) ──────────────────────
    for row, passable_cols in _LINEHEADS_PASSABLE.items():
        for c in passable_cols:
            cells[row][c] = CellType.CORRIDOR

    # ── Entry / exit / keys / doors ───────────────────────────────────────────
    # Doors are a fixed color sequence (left=gold, right=red); the key colors are
    # shuffled per seed, so which shaft-key opens which door — and the order you
    # ride the shaft to fetch them — varies.
    composite.spawn_pos   = _LINEHEADS_ENTRY
    composite.exit_pos = _LINEHEADS_EXIT
    rng = random.Random(seed)
    door_colors = list(_LINEHEADS_COLORS)                            # door0=(1,3)=gold, door1=(1,6)=red
    key_colors  = list(_LINEHEADS_COLORS); rng.shuffle(key_colors)   # key0=(4,1), key1=(14,2)
    inv_for_color = {col: ki + 1 for ki, col in enumerate(key_colors)}
    composite._lgg_door_key = [inv_for_color[dc] for dc in door_colors]
    entities = [Entity(kind='exit', row=_LINEHEADS_EXIT[0], col=_LINEHEADS_EXIT[1])]
    for ki, (kr, kc) in enumerate(_LINEHEADS_KEYS):
        entities.append(Entity(kind='floor_key', row=kr, col=kc, tag=key_colors[ki]))
    for di, (dr, dc) in enumerate(_LINEHEADS_DOORS):
        entities.append(Entity(kind='locked_door', row=dr, col=dc, tag=door_colors[di]))
    composite.entities = entities
    composite.char_runs = []   # no seed-varying runes; the layout is fixed

    composite.rebuild_indexes()
    _fog_unreachable(composite, composite.spawn_pos[0], composite.spawn_pos[1])

    # ── Compute par via Dijkstra (key/door + line-jump model) ─────────────────
    par, path = _par_lineheads(composite, return_path=True)
    if par is None:                      # fixed map — should always solve
        raise RuntimeError('The Lineheads is unsolvable — check layout')
    composite.par    = par
    composite.budget = math.ceil(par * 1.4)
    composite.answer = path

    dungeon.rooms        = [composite]
    dungeon.current_room = 0
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
    dungeon   = Dungeon(name='The Runic Archives', seed=seed)
    ROWS, COLS = _RUNIC_ARCHIVES_ROWS, _RUNIC_ARCHIVES_COLS

    cells = [[CellType.WALL] * COLS for _ in range(ROWS)]
    composite = Room(rows=ROWS, cols=COLS, room_type=RoomType.ENTRY)
    composite.cells = cells
    composite.seed  = seed

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
                    runes.append(CharRun(row=row, col=c, symbols=syms, kind=kind))
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

    runes.append(CharRun(row=_RUNIC_ARCHIVES_VOID_POS[0], col=_RUNIC_ARCHIVES_VOID_POS[1],
                             symbols=('○',), kind='void'))
    composite.char_runs = runes

    composite.spawn_pos   = _RUNIC_ARCHIVES_ENTRY
    composite.exit_pos = _RUNIC_ARCHIVES_EXIT
    composite.entities = [
        Entity(kind='floor_key',   row=_RUNIC_ARCHIVES_KEY_POS[0],  col=_RUNIC_ARCHIVES_KEY_POS[1]),
        Entity(kind='locked_door', row=_RUNIC_ARCHIVES_DOOR_POS[0], col=_RUNIC_ARCHIVES_DOOR_POS[1]),
        Entity(kind='exit',        row=_RUNIC_ARCHIVES_EXIT[0],     col=_RUNIC_ARCHIVES_EXIT[1]),
    ]

    composite.rebuild_indexes()

    par, path = _par_runic_archives(composite, return_path=True)
    if par is None:
        par, path = _RUNIC_ARCHIVES_PAR, _RUNIC_ARCHIVES_ANSWER
    composite.par    = par
    composite.budget = math.ceil(par * 1.4)
    composite.answer = path

    dungeon.rooms        = [composite]
    dungeon.current_room = 0
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
    from engine.motion import _sentence_starts_all
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
    dungeon = Dungeon(name='The Sentence Corridor', seed=seed)
    ROWS, COLS = _SENTENCE_CORRIDOR_ROWS, _SENTENCE_CORRIDOR_COLS

    cells = [[CellType.WALL] * COLS for _ in range(ROWS)]
    composite = Room(rows=ROWS, cols=COLS, room_type=RoomType.ENTRY)
    composite.cells = cells
    composite.seed  = seed

    # ── Sentence rows (row 2 stays all-wall: the stone separator) ─────────────
    runes: list = []
    for (r, c, text) in _SENTENCE_CORRIDOR_SENTENCES:
        for i in range(len(text)):
            cells[r][c + i] = CellType.CORRIDOR
        runes.append(CharRun(row=r, col=c, symbols=tuple(text), kind='ember'))
    composite.char_runs = runes

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
    # (main.py), so a cheeser reaching for `{` is punished and gains nothing,
    # leaving `(` the shortest backtrack and par at 9. The par solver and the
    # cheese audit both refuse to land on void, so par stays the true minimum.
    # Spans only S1 (a dead-end stub off the spawn) ⇒ no wall-gap bypass.
    # Shaved to THREE runes (playtest 2026-07-19): every jump that resolves
    # onto this row lands on its FIRST standable cell — the strip head — so
    # a 3-rune stub traps exactly as the old full-sentence pave did.
    _s1_r, _s1_c, _s1_text = _SENTENCE_CORRIDOR_SENTENCES[0]
    for c in range(_s1_c, _s1_c + 3):
        cells[0][c] = CellType.CORRIDOR
    runes.append(CharRun(row=0, col=_s1_c,
                         symbols=tuple(_RUNE_CHAR['void'] * 3), kind='void'))

    # ── Waterworks (2026-07-18): the inter-sentence gaps and the row-2
    # separator are MISTED WATER, not stone — every sentence is visible from
    # spawn (the stone-fog law) while the physics hold: water bars feet, and
    # the mist stops $ / f at each sentence's end exactly as the stone gap
    # did (the par route's `$ → key` depends on that bound). Word motions
    # never cross water; ) ( land on sentence starts as before.
    mist: set = set()
    for r in (1, 3):
        span = [c for c in range(COLS) if cells[r][c] != CellType.WALL]
        for c in range(min(span), max(span) + 1):
            if cells[r][c] == CellType.WALL:
                cells[r][c] = CellType.WATER
                mist.add((r, c))
    for c in range(1, COLS - 1):
        if cells[2][c] == CellType.WALL:
            cells[2][c] = CellType.WATER
            mist.add((2, c))
    composite.fog_cells  = set(mist)
    composite.mist_cells = set(mist)              # permanent: reveals skip it

    composite.spawn_pos = _SENTENCE_CORRIDOR_ENTRY
    composite.exit_pos  = _SENTENCE_CORRIDOR_EXIT
    composite.entities = [
        Entity(kind='exit',        row=er, col=ec),
        Entity(kind='locked_door', row=dr, col=dc),
        Entity(kind='floor_key',   row=kr, col=kc),
    ]
    composite.rebuild_indexes()

    cost, answer = _par_sentence_corridor(composite, return_path=True)
    composite.par    = cost
    composite.budget = math.ceil(cost * 1.4)
    composite.answer = answer

    dungeon.rooms        = [composite]
    dungeon.current_room = 0
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
                                        # (widened 2026-07-17: the forge-song's
                                        # longest line runs 41 chars, to col 42)
_FORGE_DOOR  = 6                        # the blank corridor row: spawn, seal door, exit
# Three chambers, each forcing a different member of the :s / :g family more than once.
# Vocabulary is rigorously separated so one chamber's global rite never reaches another:
# no word outside Chamber A contains the substring 'old' (no cold/gold/holds/bond…), only
# Chamber B carries 'pale'/'pure', only Chamber C carries 'cursed'.
#
# The floor incantations were rewritten 2026-07-17 (writing-agent pass, user
# pick "the forge-song"): the SURVIVING lines — the three A wards mended to
# 'new', the two B verses mended to 'pure', B's kept 'pale' line, and C's two
# sacred keepers — read TOP TO BOTTOM as one coherent poem (a smith waking the
# forge and blessing the blade). The corruptions still self-label: a forge
# RENEWS (iron, sparks, songs) so 'old' reads wrong; a heart and one's work
# plainly want 'pure' while the moon is rightly pale; the 'cursed' lines are
# struck while the 'sacred' ones are kept. Line lengths reach 41 (Chamber A),
# which is why _FORGE_DIV was widened to 46.
#
# THE FINAL POEM (post-edit), in buffer order:
#   new iron, new fire, i wake the forge        (A1)
#   new sparks for the new blade i shape         (A2)
#   new songs rise where the new hammer falls    (A3)
#   shaped by a heart that beats pure            (B1)
#   under a pale and patient moon                (B2, kept)
#   my work lies pure beneath its light          (B3)
#   sacred embers guard the coal                 (C2, kept)
#   this blade is sacred, keep it well           (C4, kept)
#
# Chamber A — Ember Wards (rows 2-4): 'old' repeats WITHIN each line, so :s/old/new/
# alone leaves remnants — only :%s/old/new/g mends a whole ward.  Drills the /g flag.
_FORGE_A_WARDS   = [(2, 'old iron, old fire, i wake the forge'),
                    (3, 'old sparks for the old blade i shape'),
                    (4, 'old songs rise where the old hammer falls')]
# Chamber B — Selfsame Verses (rows 8-10): 'pale'→'pure', but the MIDDLE line's 'pale'
# is TRUE (verdant) and must remain.  A whole-buffer :%s/pale/pure/g wrecks it; the two
# corrupt (ember) lines straddle the protected one so no single range covers just them —
# :s one, jj past the true line, & the other.  Drills surgical :s + the & repeat.
_FORGE_B_CORRUPT = [(8, 'shaped by a heart that beats pale'),
                    (10, 'my work lies pale beneath its light')]
_FORGE_B_KEEP    = (9, 'under a pale and patient moon')
# Chamber C — Cursed Litany (rows 14-18): :g/cursed/d sweeps every cursed (ember) line at
# once; the sacred (verdant) lines between them must remain (so a blanket delete fails).
# Drills :g/pat/d and its selective, all-at-once global reach.
# (Rows start at 14, NOT 13: :g/…/d REMOVES rows and destroys entities on them,
# and the sanctum's scroll chest sits on row 13 — the litany begins below it.)
_FORGE_C_CURSED  = [(14, 'cursed sparks die in the ash'),
                    (16, 'no cursed thing survives this heat'),
                    (18, 'cursed iron cracks and is thrown out')]
_FORGE_C_KEEP    = [(15, 'sacred embers guard the coal'),
                    (17, 'this blade is sacred, keep it well')]
_FORGE_CHEST     = (13, _FORGE_COLS - 2)   # sanctum scroll chest (random relic —
                                           # the forge names no scroll drop)


def _forge_text(room, row, col, text, kind):
    for i, ch in enumerate(text):
        if ch != ' ':
            room.char_runs.append(CharRun(row, col + i, (ch,), kind))


# The canonical three-rite solve, as an admin karaoke tape: Enter is the glyph '⏎' (so it
# renders on the answer sheet and the live tracker can match an Enter keypress against it),
# and spaces are visual token separators (stripped for matching, never typed).  Chamber A's
# /g mend, then 8G + surgical :s + jj + & (Chamber B, sparing the protected verse), then
# Chamber C's :g delete, then the walk out.  Tests translate ⏎→Enter and drop the spaces.
# par is this solve's measured engine cost — constant across seeds; the playthrough pins it.
_SPELLWRIGHTS_ANSWER = ':%s/old/new/g⏎ 8G :s/pale/pure/⏎ jj& :g/cursed/d⏎ 6G$'
_SPELLWRIGHTS_PAR    = 45
# 45 = :%s/old/new/g (13) + 8G (2) + :s/pale/pure/ (13) + jj (2) + & (1) + :g/cursed/d (11)
#      + 6G$ (3).  Chamber B's two verses straddle the protected line, so no single command
#      hits just them — the :s + & pair is the floor there; the cursor never lands on the
#      door row after a rite, so the 3-key walk out is the floor too.


def _par_spellwrights_forge():
    return _SPELLWRIGHTS_PAR, _SPELLWRIGHTS_ANSWER


def build_dungeon_spellwrights_forge(seed: int) -> Dungeon:
    dungeon = Dungeon(name="The Spellwright's Forge", seed=seed)
    ROWS, COLS, W = _FORGE_ROWS, _FORGE_COLS, _FORGE_DIV

    cells = [[CellType.WALL] * COLS for _ in range(ROWS)]
    for r in range(1, ROWS - 1):
        for c in range(1, W):                      # left workroom
            cells[r][c] = CellType.FLOOR
        for c in range(W + 1, COLS - 1):           # right sanctum
            cells[r][c] = CellType.FLOOR
    # col W is wall top-to-bottom except the seal door, which opens once the rites are true.

    room = Room(room_type=RoomType.ENTRY, rows=ROWS, cols=COLS)
    room.cells     = cells
    room.seed      = seed
    room.spawn_pos = (_FORGE_DOOR, 1)
    room.exit_pos  = (_FORGE_DOOR, COLS - 2)
    room.char_runs = []
    for r, txt in _FORGE_A_WARDS:                 # Chamber A — corrupted ember wards
        _forge_text(room, r, 2, txt, 'ember')
    for r, txt in _FORGE_B_CORRUPT:               # Chamber B — corrupt verses (mend pale→pure)
        _forge_text(room, r, 2, txt, 'ember')
    _forge_text(room, _FORGE_B_KEEP[0], 2, _FORGE_B_KEEP[1], 'verdant')   # the TRUE pale ward
    for r, txt in _FORGE_C_CURSED:                # Chamber C — cursed lines (delete)
        _forge_text(room, r, 2, txt, 'ember')
    for r, txt in _FORGE_C_KEEP:                  # the sacred lines (keep)
        _forge_text(room, r, 2, txt, 'verdant')

    room.entities = [
        Entity(kind='exit',         row=_FORGE_DOOR, col=COLS - 2),
        # The sanctum's reward: an unassigned chest → a random relic scroll.
        # Row 13 — ABOVE every cursed row, so :g/cursed/d never collapses it.
        Entity(kind='chest_scroll', row=_FORGE_CHEST[0], col=_FORGE_CHEST[1]),
    ]
    # The seal: the divider cell on the corridor row.  main._forge_check opens it once the
    # incantations RING TRUE — every line that should REMAIN must read its exact text
    # (Chamber A mended old→new with /g, Chamber B's two verses mended pale→pure, B's TRUE
    # pale line untouched, Chamber C's sacred lines intact) AND no 'cursed' line survives.
    # Demanding the exact text (not the mere absence of 'old'/'cursed') forbids the snip
    # mangle (`:%s/l//g` etc.) that once satisfied a bare substring check for pennies.
    room._forge_seal = (_FORGE_DOOR, W)
    # Every phrase that must be present when the rite is true (mended or deliberately kept):
    room._forge_mended = (
        [t.replace('old', 'new')   for _r, t in _FORGE_A_WARDS]    # A: /g-mended wards
        + [t.replace('pale', 'pure') for _r, t in _FORGE_B_CORRUPT]  # B: surgically mended
        + [_FORGE_B_KEEP[1]]                                         # B: the protected true line
        + [t for _r, t in _FORGE_C_KEEP]                            # C: the sacred keep lines
    )

    # par is the true keystroke floor of the three rites + the walk out; measured by replay
    # across seeds (content is fixed, so par is constant).  See tests/test_spellwrights_forge.
    par, ans = _par_spellwrights_forge()
    room.par    = par
    room.budget = max(math.ceil(par * 1.4), 60)  # generous; the rites are exploratory
    room.answer = ans

    room.rebuild_indexes()
    apply_stone_fog(room)                 # sealed pockets sleep under fog
    dungeon.rooms        = [room]
    dungeon.current_room = 0
    return dungeon


# ── The Refrain Vault (display 42) — repeats + remote yank: & :&& :j :y ──────
# A walkable scriptorium under a small chasm. Rows of verses carry one blight
# word; the first mend is spoken in full (:s/{b}/{c}/g on the triple-blighted
# desk you wake at), then & repeats it line by line and :&& (flags kept)
# clears the second triple. THREE protected verdant lines carrying the SAME
# blight word stand scattered BETWEEN the blighted rows: :%s / g& / :g//s all
# mend them too (door fails), and no contiguous :{a},{b}s can cover every
# blight while missing every protected line — the repeat family wins by PAR.
# Above the water course, the vault's colophon lies broken across two misted
# chasm lines: :1,2j mends it, :1y carries it, p lays it in the hall (a
# :t/:m ferry of the chasm line arrives still misted — impassable stone that
# can never satisfy the door's on-the-floor demand; only the yank serves).
_RV_ROWS, _RV_COLS = 14, 60
_RV_CTX  = 8                          # chasm band head col
_RV_BAND = (8, 41)                    # misted colophon band, rows 1-2
_RV_WTR  = 3                          # the water course (sight-line)
_RV_TX   = 4                          # workroom text head col
_RV_WORK = (4, 12)                    # walkable verse rows
_RV_PROTECTED = (4, 7, 10)            # verdant, blight word KEPT
_RV_MULTI     = (5, 11)               # triple-blight rows (B1 = spawn, B2)
_RV_SINGLE    = (6, 8, 9)             # one blight each — the & chain
_RV_FILLER    = 12                    # a clean closing verse (the seal row)
_RV_SEAL_COL  = 49
_RV_CHEST_COL = 53
_RV_EXIT_COL  = 57
# A plain & resets the remembered flags (Vim-faithful), so the OTHER triple
# is mended by RANGED :5&& while the /g is still fresh — before the & chain.
# The spawn desk is B2 (row 11): the :5&& park carries the scribe to the top
# of the chain, and the singles fall to plain & on the way back down.
_RV_PAR    = 37    # :s/{b}/{c}/g(14) :5&&(4) j&(2) 2j&(3) j&(2)
                   # :1,2j(5) :1y(3) p(1) 3j(2) $(1)
_RV_BUDGET = 60                       # generous: the longhand roads win 1★


def _rv_draw_words(rng):
    """(b, c, pool): blight, cure, and 23 fillers free of both as substrings."""
    _load_vocab_tables()
    p4 = _VOCAB_PLAIN_BY_LEN[4]
    for _ in range(200):
        b, c = rng.sample(p4, 2)
        pool = [w for w in p4 + _VOCAB_PLAIN_BY_LEN[5]
                if b not in w and c not in w and w not in (b, c)]
        if len(pool) >= 24:                    # 5 colophon + 6 + 4 + 6 + 3 filler
            return b, c, rng.sample(pool, 24)
    raise RuntimeError('refrain vault: vocab too thin')


def build_dungeon_refrain_vault(seed: int) -> Dungeon:
    dungeon = Dungeon(name='The Refrain Vault', seed=seed)
    rng = random.Random(seed ^ 0x8EF8)
    b, c, pool = _rv_draw_words(rng)
    R, C = _RV_ROWS, _RV_COLS

    cells = [[CellType.WALL] * C for _ in range(R)]
    mist: set = set()
    for r in (1, 2):                               # the colophon chasm
        for col in range(*_RV_BAND):
            cells[r][col] = CellType.FLOOR
            mist.add((r, col))
    for col in range(_RV_CTX, C - 3):              # the water course (sight)
        cells[_RV_WTR][col] = CellType.WATER
        mist.add((_RV_WTR, col))
    for r in range(*_RV_WORK):
        for col in range(2, _RV_SEAL_COL):
            cells[r][col] = CellType.FLOOR         # the workroom
    for col in range(2, _RV_SEAL_COL):
        cells[_RV_FILLER][col] = CellType.FLOOR    # the seal row
    for col in range(_RV_SEAL_COL + 1, _RV_EXIT_COL + 1):
        cells[_RV_FILLER][col] = CellType.FLOOR    # the sealed exit pocket
    # (_RV_FILLER, _RV_SEAL_COL) stays WALL until _refrain_tick opens it.

    room = Room(room_type=RoomType.ENTRY, rows=R, cols=C)
    room.cells     = cells
    room.seed      = seed
    room.spawn_pos = (_RV_MULTI[1], 2)             # the B2 desk (row 11)
    room.exit_pos  = (_RV_FILLER, _RV_EXIT_COL)
    room.char_runs = []

    def lay(r, col, text, kind):
        for wd in text.split(' '):
            room.char_runs.append(CharRun(r, col, tuple(wd), kind))
            col += len(wd) + 1

    take = iter(pool)
    half1 = f'{next(take)} {next(take)} {next(take)}'
    half2 = f'{next(take)} {next(take)}'
    lay(1, _RV_CTX, half1, 'ancient')
    lay(2, _RV_CTX, half2, 'ancient')
    colophon = f'{half1} {half2}'

    protected, mended = [], []
    for r in _RV_PROTECTED:
        t = f'{next(take)} {b} {next(take)}'
        protected.append(t); lay(r, _RV_TX, t, 'verdant')
    for r in _RV_MULTI:
        w1, w2 = next(take), next(take)
        lay(r, _RV_TX, f'{b} {w1} {b} {w2} {b}', 'ember')
        mended.append(f'{c} {w1} {c} {w2} {c}')
    for r in _RV_SINGLE:
        w1, w2 = next(take), next(take)
        lay(r, _RV_TX, f'{w1} {b} {w2}', 'ember')
        mended.append(f'{w1} {c} {w2}')
    lay(_RV_FILLER, _RV_TX, f'{next(take)} {next(take)} {next(take)}', 'ancient')

    room.entities = [
        Entity(kind='exit',         row=_RV_FILLER, col=_RV_EXIT_COL),
        Entity(kind='chest_scroll', row=_RV_FILLER, col=_RV_CHEST_COL),
    ]
    room._rv_blight    = b
    room._rv_protected = tuple(protected)
    room._rv_mended    = tuple(mended)
    room._rv_colophon  = colophon
    room._rv_seal_col  = _RV_SEAL_COL

    room.par    = _RV_PAR
    room.budget = _RV_BUDGET
    room.answer = (f':set␣nu⏎ :s/{b}/{c}/g⏎ :5&&⏎ j & 2j & j & '
                   f':1,2j⏎ :1y⏎ p 3j $')

    room.rebuild_indexes()
    pocket = {(_RV_FILLER, col)
              for col in range(_RV_SEAL_COL + 1, _RV_EXIT_COL + 1)}
    room.fog_cells  = set(mist) | pocket
    room.mist_cells = set(mist)
    dungeon.rooms        = [room]
    dungeon.current_room = 0
    return dungeon


# ── The Warden Pathfinder (Act III boss) ─────────────────────────────────────
# Two rooms: the Arena (room 0) and the Wardenverse (room 1, a single-line wrap
# buffer). Act 1 plays out in the Arena; when the Warden's shields fall he flees
# and the player follows with `:e wardenverse` (handled in main.py). See
# engine/warden_mega.py and tests/test_warden_pathfinder.py (the as-built spec).
_PF_ROWS, _PF_COLS   = 24, 78
_PF_MAIN_ROW         = 12
# A big open hall with four stone COLUMNS at the inner vertices of a 3×3 grid (just
# markers — the room stays open). The Warden's mega-attack tears bands of ROWS.
_PF_COLUMNS          = ((8, 22), (8, 44), (15, 22), (15, 44))   # column cells (impassable)
_PF_FIGHT            = (1, 22, 1, 66)       # fight area (mega tears floor only here; treasure is east)
_PF_WARDEN_START     = (12, 39)            # centre of the hall
# Impostor Wardens — goblins disguised as the Warden (tag='echo', a red 'W'), spread
# across the hall so the player enters to "a myriad of Wardens".  Each carries a shade
# index (a slightly different red); the real Warden hides among them at (12,39).
# (row, col, shade)
_PF_ECHO_CELLS       = (
    ( 4, 26, 1), ( 4, 34, 4), ( 4, 44, 2), ( 4, 52, 6),
    ( 8, 30, 3), ( 8, 50, 5), ( 8, 58, 0),
    (12, 28, 2), (12, 50, 7), (12, 58, 1),
    (16, 30, 6), (16, 50, 3), (16, 58, 4),
    (20, 26, 0), (20, 34, 5), (20, 44, 7), (20, 52, 2),
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
    from engine.warden_mega import init_mega
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
        # hp=2: the first x strikes off the Warden-disguise (→ plain goblin), the second kills.
        g = Entity(kind='goblin', row=r, col=c, hp=2, max_hp=2, tag='echo', shade=sh)
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
    verse.exit_pos = None                    # no exit here — his death collapses the verse (main.py)
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
_OV_SHAFTS = ((4, 57), (7, 7), (10, 57), (13, 7), (16, 57),
              (19, 26), (22, 57), (25, 7), (28, 57))
# the oubliette pockets: (row, col) — sealed 1-cell floor cells. Col 3 on every
# first spacer row (catches a corridor dd), col 1 on every second spacer row
# (catches a chained dd from inside the first pocket), plus the two under the
# vault approach.
_OV_POCKETS = tuple((r, 3) for r in (4, 7, 10, 13, 16, 19, 22, 25, 28)) + \
              tuple((r, 1) for r in (5, 8, 11, 14, 17, 20, 23, 26, 29)) + \
              ((32, 3), (33, 1))
_OV_SPLIT_ROW  = 30                   # C10: floor 30..57 — a dead-end overhang
_OV_LEDGE_ROW  = 31                   # the sealed ledge under it: floor 2..29
_OV_VAULT_ROW  = 33                   # antechamber + vault: floor 5..19
_OV_DOOR       = (33, 17)             # vault door (untagged); the EXIT is the prize
_OV_KEY_DCOL   = 3                    # keys drop 3 cells before their door
# answer keystrokes (operators written as separate single-key tokens: 'd w' = dw)
_OV_ANSWER = ('w d w 7l x l x 2l p $ 3j '     # C1  → dw; chest + gold key + gate
              'd b h 3j '                     # C2  ← db lands by the shaft mouth
              'd e w e x l x 2l p $ 3j '      # C3  → de; chest + blue key + gate
              'd B h 3j '                     # C4  ← dB from the WORD head
              'd E e 4l x $ 3j '              # C5  → dE; e rides the reflowed word
              'd F ? 3j '                     # C6  ← dF? lands on the shaft mouth
              'w d W e 7l x l x 2l p $ 3j '   # C7  → dW; chest + red key + gate
              'd 0 5l 3j '                    # C8  ← d0 sweep (dd = oubliette)
              'd $ $ 3j '                     # C9  → d$ sweep
              'd d d $ l 2j 9l x 2l p 2l')    # C10 ← dd, ride down, d$, vault
                                              # (dd lands Vim-true on the risen
                                              # ledge's FIRST NON-BLANK, col 4
                                              # — one l to the vault approach)


def _ov_pick(rng, table, length, used, pred=None):
    """Draw a fresh vocab token of exactly `length` from a length-keyed table
    (no repeats within the level; optional structural predicate)."""
    pool = [t for t in table.get(length, ())
            if t not in used and (pred is None or pred(t))]
    tok = rng.choice(pool)
    used.add(tok)
    return tok


def _ov_mixed_ok(tok: str) -> bool:
    """A mixed token usable as an operator-lesson WORD: it must START on a word
    character (B/W land on the token head) and break into subwords somewhere
    inside (an internal non-word char), so the small-word motions w/b/e crawl
    while W/B/E take the whole token."""
    return _is_word_char(tok[0]) and any(not _is_word_char(c) for c in tok[1:-1])


def _ov_plain_ok(tok: str) -> bool:
    """A 'plain' token usable as a single word: every char a word char, so
    w/b/e treat it as ONE word. The vocab file enforces this since the
    2026-06-09 reclassification — kept as a guard so a future vocab edit
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
    floor(_OV_LEDGE_ROW, _OV_LCOL, 29)            # …over the sealed vault ledge
    for (top, col) in _OV_SHAFTS:                 # the connector shafts
        cells[top][col] = cells[top + 1][col] = CellType.FLOOR
    for (r, c) in _OV_POCKETS:                    # the oubliette pockets
        cells[r][c] = CellType.FLOOR
    # A misted channel runs the whole west face (playtest 2026-07-19): cols
    # 1-2 of every spacer row are WATER under MIST, one continuous seep
    # linking the pools so the col-1 oubliettes are seen ACROSS WATER, not
    # through stone. The mist matters twice: fogged water conducts no
    # reveal flood (engine law), so the channel cannot ladder this level's
    # corridor-by-corridor fog past the gates — and it bars the $ / f
    # scans as the stone did. Converted AFTER _fog_unreachable (below), so
    # the build flood sees stone here too.
    cells[32][5] = CellType.FLOOR                 # ledge → antechamber drop
    floor(_OV_VAULT_ROW, 5, 19)                   # antechamber + vault

    room = Room(room_type=RoomType.COMBAT, rows=R, cols=C)
    room.cells     = cells
    room.seed      = seed
    room.spawn_pos = (3, _OV_LCOL)
    room.exit_pos  = (33, 19)
    room.char_runs = []
    room.entities  = []

    def word(r, c, text, kind='ember'):
        room.char_runs.append(CharRun(row=r, col=c, symbols=tuple(text), kind=kind))

    def goblin(r, c, tag=''):
        room.entities.append(Entity(kind='goblin', row=r, col=c, hp=2, max_hp=2,
                                    ai='chase', ai_speed=1, tag=tag))

    def gate(r, c, color):
        room.entities.append(Entity(kind='locked_door', row=r, col=c, tag=color,
                                    edit_immune=True))

    def chest(r, c):
        room.entities.append(Entity(kind='chest_scroll', row=r, col=c))

    # All corridor text is drawn fresh from the vocabulary files each seed —
    # only the LENGTHS are fixed (the whole layout keys off them), never the
    # letters. Mixed tokens additionally need the lesson structure
    # (_ov_mixed_ok: word-char head + an internal subword break).
    used: set = set()

    def plain(n):
        return _ov_pick(rng, _VOCAB_PLAIN_BY_LEN, n, used, _ov_plain_ok)

    def mixed(n):
        return _ov_pick(rng, _VOCAB_MIXED_BY_LEN, n, used, _ov_mixed_ok)

    # C1 (row 3, →): dw — guard in the gap; the chest riding the next word's
    # 2nd char dies to any wider cut, and the gold gate parries dd.
    word(3, 7, plain(3)); goblin(3, 11, tag='g1'); word(3, 13, plain(3))
    chest(3, 14)
    gate(3, 18, 'gold')                           # key drops at 15 when g1 falls
    # C2 (row 6, ←): db — the word head is one step from the shaft mouth at
    # col 7; d0 also kills the guard but lands at col 2, one key worse.
    word(6, 8, plain(4)); goblin(6, 14)
    # C3 (row 9, →): de — guard riding the word's last letter; the chest in the
    # gap dies to d$, and dw cannot even fire (the gate blocks the w-scan, so w
    # has no target). The filler word beyond the gate reflows in after the cut
    # and becomes the w/e path to the loot.
    word(9, 12, plain(3)); goblin(9, 14, tag='g3')
    chest(9, 16)
    gate(9, 20, 'blue')                           # key drops at 17 when g3 falls
    word(9, 22, plain(3))
    # C4 (row 12, ←): dB — one guard rides the token HEAD, one waits beyond:
    # db only reaches the trailing subword and misses the head guard.
    word(12, 8, mixed(5)); goblin(12, 8); goblin(12, 15)
    # C5 (row 15, →): dE — guard rides the token's tail (de crawls subword
    # ends); the scroll chest in the gap punishes dW/d$; the far word reflows
    # in as the path.
    word(15, 12, mixed(6)); goblin(15, 17)
    chest(15, 20)
    word(15, 24, plain(4))
    # C6 (row 18, ←): dF? — the '?' bait sits ON the shaft mouth (col 26): the
    # cut sweeps the pack AND lands you on the way down. The decoy word blocks
    # a one-cast db (b stops there first).
    word(18, 26, '?', kind='ancient')
    goblin(18, 30); goblin(18, 36); goblin(18, 42)
    word(18, 46, plain(3))
    # C7 (row 21, →): dW — dE stops at the token's tail and misses the gap
    # guard; the chest riding the next word dies to d$ ($ stops at the gate);
    # the word beyond the gate reflows in as the w/e path to the loot.
    word(21, 30, mixed(5)); goblin(21, 34, tag='g7'); goblin(21, 37, tag='g7')
    word(21, 40, plain(5))
    chest(21, 41)
    gate(21, 45, 'red')                           # key drops at 42 when g7 falls
    word(21, 47, plain(3))
    # C8 (row 24, ←): d0 — sweep the pack; the guard AT the line head makes a
    # one-cast db miss; dd collapses the row into the oubliette below.
    goblin(24, 3); word(24, 10, plain(6)); goblin(24, 20); goblin(24, 29)
    # C9 (row 27, →): d$ — no character beyond the last guard, so no find or
    # word motion reaches all three.
    word(27, 12, plain(3)); goblin(27, 20); word(27, 25, plain(3))
    goblin(27, 30); goblin(27, 40)
    # C10 (row 30, ←) + the ledge: the LAST pack paces the sealed ledge below
    # the overhang; dd drops the floor line, d$ sweeps the risen pack. The
    # antechamber words are the w-path to the dropped vault key.
    word(31, 4, plain(5)); goblin(31, 10); goblin(31, 16); goblin(31, 22)
    word(33, 7, plain(4)); word(33, 12, plain(4))
    # the vault: the door and the way out — the level's chests came earlier
    room.entities.append(Entity(kind='locked_door', row=_OV_DOOR[0], col=_OV_DOOR[1],
                                edit_immune=True))
    room.entities.append(Entity(kind='exit', row=33, col=19))
    # guard-group tag → gate color-tag (tags are unique; the key-drop tick in
    # main.py resolves the LIVE door by tag, so undo replacing room.entities
    # can never leave it holding a stale reference)
    room._ov_groups = (('g1', 'gold'), ('g3', 'blue'), ('g7', 'red'))

    room.rebuild_indexes()
    _fog_unreachable(room, room.spawn_pos[0], room.spawn_pos[1])
    # (2026-07-19) Only the CORRIDOR pockets are subtracted: they are the
    # visible pits (the warning), they're audit-clean — sight passes the
    # gate grilles — and fogging them phase-shifts the goblin AI against
    # the canonical tape (fog is impassable; a pocket mouth is a move
    # option). The ledge, the antechamber, its two pockets and the vault
    # sleep dark until the C10 collapse drops the player in — the tick's
    # per-key door-blocked _reveal_from lights them from where they land
    # (the dd park is fog-blind for exactly this fall).
    room.fog_cells -= {p for p in _OV_POCKETS if p[0] <= 29}
    # The west-face misted channel (see the note above): laid after the fog
    # flood so the build flood saw stone, permanently misted thereafter.
    # Every WALL cell in the strip converts — including the corridor rows'
    # own col-1 stubs (playtest 2026-07-19: they read as interruptions), so
    # the seep runs unbroken top to bottom. On a corridor row only col 1 is
    # stone (col 2 is its floor), and the mist keeps 0 / ^ landing at col 2.
    for r in range(_OV_CORR_ROWS[0], _OV_SPLIT_ROW):
        for c in (1, 2):
            if room.cells[r][c] == CellType.WALL:
                room.cells[r][c] = CellType.WATER
                room.fog_cells.add((r, c))
                room.mist_cells.add((r, c))
    room.par    = 92                              # dd's Vim-true fnb landing
    room.answer = _OV_ANSWER                      # (2026-07-12) saved a key
    room.budget = math.ceil(92 * 1.4)

    dungeon = Dungeon(name="The Operator's Vault", seed=seed)
    dungeon.rooms        = [room]
    dungeon.current_room = 0
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
    _CC_PAR while the answer's letters track the combo. All four doors run
    through main._cipher_cell_tick — stateless and undo-safe.
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
    cells = [[CellType.WALL] * C for _ in range(R)]
    for c in range(_CC_FLOOR_LO, _CC_FLOOR_HI + 1):
        cells[_CC_ROW][c] = CellType.CORRIDOR
    for (br, bc) in (_CC_BOLT_A, _CC_BOLT_B, _CC_BOLT_C, _CC_BOLT_D):
        cells[br][bc] = CellType.WALL              # the bolts start shut

    room = Room(room_type=RoomType.ENTRY, rows=R, cols=C)
    room.cells = cells
    room.seed  = seed

    def lay(row, col, text, kind):
        """Place `text` at (row, col); spaces become gaps between separate runs."""
        c = col
        for piece in text.split(' '):
            if piece:
                room.char_runs.append(CharRun(row, c, tuple(piece), kind))
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

    # The exit is edit-immune: the final D's span sweeps over its cell, and the
    # way out must not be deletable (nor the row dd-collapsible — immunity
    # parries that too, per the L18 refused-collapse rule).
    room.entities.append(Entity(kind='exit', row=_CC_EXIT[0], col=_CC_EXIT[1],
                                edit_immune=True))
    room.spawn_pos = _CC_SPAWN
    room.exit_pos  = _CC_EXIT

    # Bolt specs read by main._cipher_cell_tick (stateless, undo-safe): each is
    # (row, c0, target, bolt_pos) — the bolt stands open while the lock row's
    # text over [c0, c0+len(target)) READS AS the target, i.e. as the plaque
    # (the word, then blank where the plaque is blank).
    def span_target(word, span):
        lo, hi = span
        return word + ' ' * (hi - lo + 1 - len(word))
    room._cc_bolts = [
        (_CC_ROW, _CC_CIPHER_A_COL, word_a, _CC_BOLT_A),
        (_CC_ROW, _CC_SPAN1[0], span_target(word_1, _CC_SPAN1), _CC_BOLT_B),
        (_CC_ROW, _CC_CIPHER_B_COL, word_b, _CC_BOLT_C),
        (_CC_ROW, _CC_SPAN2[0], span_target(word_2, _CC_SPAN2), _CC_BOLT_D),
    ]

    room.rebuild_indexes()
    # Par tally (combo shapes identical, so this holds for every seed):
    #   w w r?   (4)  → mend cipher A, bolt A grinds back
    #   w w D    (3)  → to the rot past the plain word; shear it; bolt B opens
    #   w w 2r?  (5)  → double-mend cipher B, bolt C opens
    #   w w D    (3)  → shear rot 2; bolt D opens
    #   $        (1)  → walk out
    room.par    = _CC_PAR
    room.budget = math.ceil(_CC_PAR * 1.4)
    room.answer = (f'w w r{word_a[_CC_WARP_A]} w w D '
                   f'w w 2r{word_b[warp_b]} w w D $')

    apply_stone_fog(room)                 # sealed pockets sleep under fog
    dungeon = Dungeon(name='The Cipher Cell', seed=seed)
    dungeon.rooms        = [room]
    dungeon.current_room = 0
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
_QM_PAR = 15                            # seed-invariant; tallied in the answer below


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

    room = Room(room_type=RoomType.ENTRY, rows=R, cols=C)
    room.cells = cells
    room.seed  = seed

    room.char_runs.append(CharRun(*_QM_SOURCE, (_QM_FLAME,), 'flame'))
    for (r, c) in (_QM_PED1, *((_QM_BRAZIER_ROW, c) for c in _QM_BRAZIER_COLS)):
        room.char_runs.append(CharRun(r, c, (_QM_EMBERS,), 'pedestal'))

    # The exit must not be deletable from under the level (nor its row
    # dd-collapsible — immunity parries that, per the L18 refused-collapse rule).
    room.entities.append(Entity(kind='exit', row=_QM_EXIT[0], col=_QM_EXIT[1],
                                edit_immune=True))
    room.spawn_pos = _QM_SPAWN
    room.exit_pos  = _QM_EXIT
    # Anchors read by main._quartermaster_tick (stored coordinates, the Cipher
    # Cell convention — a self-inflicted dd/linewise shift above them desyncs
    # the doors until u, which is the established recoverable failure mode).
    room._qm_chain     = (_QM_SOURCE, _QM_PED1)
    room._qm_bolt_cols = _QM_BOLT_COLS
    room._qm_braziers  = tuple((_QM_BRAZIER_ROW, c) for c in _QM_BRAZIER_COLS)
    room._qm_seal_col  = _QM_SEAL_COL

    room.rebuild_indexes()
    # Par tally (fixed geometry, so this holds for every seed):
    #   w y l       (3)  → step to the flame; lift it (nothing is cut)
    #   w P         (2)  → hall brazier: paste lights it; bolt B grinds back
    #   4G          (2)  → line 4: land on the first cold beacon brazier
    #   3P          (2)  → one count-paste fills all three (3p leaves the left cold)
    #   y y p P     (4)  → yank the beacon row; one tier below, one ABOVE the
    #                      copy — three tiers burn at rows 4/5/6 and the P
    #                      leaves the cursor ONE row under the seal row (the
    #                      exit row never shifts: p's insert is below it, P's
    #                      is below it too). Player-found golf (2026-07-18);
    #                      the old p p route paid an extra k to climb back.
    #   k 0         (2)  → up to the seal row; 0 walks west onto the exit
    room.par    = _QM_PAR
    room.budget = math.ceil(_QM_PAR * 1.4)
    room.answer = 'w y l w P 4G 3P y y p P k 0'

    apply_stone_fog(room)                 # the exit pocket sleeps under fog

    dungeon = Dungeon(name='The Beacon Tiers', seed=seed)
    dungeon.rooms        = [room]
    dungeon.current_room = 0
    return dungeon


# ── The Echo Vault — . (dot-repeat) ───────────────────────────────────────────
_EV_ROWS, _EV_COLS = 4, 52
_EV_PLAQUE_ROW = 1                     # sealed plaque band (wall row, glyphs embedded)
_EV_ROW        = 2                     # the single gauntlet row — one floor row seals
                                       # the plaques against any visual straddle (as in the Cipher Cell)
_EV_FLOOR_LO, _EV_FLOOR_HI = 1, 49
_EV_SPAWN = (2, 2)
_EV_EXIT  = (2, 49)                    # behind the final bolt; the single sealed row
                                       # means every line jump lands on the row's FIRST
                                       # non-blank (col 4) and no other row can walk in
# Segment columns. Shapes are FIXED across combos so par is seed-invariant:
# phrase 1 = 4+3+4 letters, its letter warped at string offsets (1, 7, 10);
# phrase 2 = 5+4 letters, warped at (3, 6); phrase 3 = word4 ⟨digit⟩ word3
# ⟨digit×3⟩, digits warped at (5, 11, 12, 13) — the lone digit primes r, the
# triple is the count-dot beat (3.).
_EV_SEG1_COL, _EV_SEG2_COL, _EV_SEG3_COL = 4, 20, 33
_EV_WARPS1 = (1, 7, 10)
_EV_WARPS2 = (3, 6)
_EV_WARP3_SINGLE, _EV_WARP3_TRIPLE = 5, (11, 12, 13)
_EV_BOLT_A = (2, 18)                   # opens while segment 1 reads as its plaque
_EV_BOLT_B = (2, 31)                   # … segment 2
_EV_BOLT_C = (2, 48)                   # … segment 3 — the seal before the exit
# Combos: (phrase1, letter1), (phrase2, letter2), (word4, word3, digit).
# Each phrase carries its letter EXACTLY at the warp offsets, and no mend
# letter (or the digit) appears ANYWHERE else in the vault (asserted at
# build): every copy gets warped, so the cure exists nowhere reachable —
# true scarcity, on top of the register self-seal. Combos are normally
# ASSEMBLED from the vocab corpus per seed (_ev_pick_combo — the shapes stay
# fixed, so par holds); this static table is the deterministic fallback for
# a corpus that can't satisfy a draw.
_EV_COMBOS = (
    (('mend the seal', 'e'), ('guard rust', 'r'), ('lock', 'map', '7')),
    (('mist ski mild', 'i'), ('burnt numb', 'n'), ('gate', 'map', '3')),
    (('bold who boat', 'o'), ('crust salt', 's'), ('dial', 'rim', '5')),
    (('mast sea malt', 'a'), ('burnt numb', 'n'), ('rope', 'dim', '9')),
)
_EV_PAR = 25                           # seed-invariant; tallied in the answer below


def _ev_pick_combo(rng):
    """Assemble a seed-random Echo Vault combo from the vocab corpus.

    The SHAPES are fixed (they are what keeps par seed-invariant): phrase 1 =
    4+3+4 letters with the mend letter exactly once per word at indices
    1/2/1; phrase 2 = 5+4 with its letter at 3/0; phrase 3 = a free 4- and
    3-letter word plus a digit. Cross-segment scarcity is enforced in the
    pools (each mend letter appears nowhere in the other segments), so the
    builder's asserts hold for every draw. Deterministic per seed; falls
    back to the static _EV_COMBOS table if the corpus can't satisfy."""
    _load_vocab_tables()
    low = {n: [w for w in _VOCAB_PLAIN_BY_LEN.get(n, ())
               if w.isalpha() and w.islower()] for n in (3, 4, 5)}
    for _ in range(40):
        l1, l2 = rng.sample('abcdefghijklmnopqrstuvwxyz', 2)
        a = [w for w in low[4] if w[1] == l1 and w.count(l1) == 1 and l2 not in w]
        b = [w for w in low[3] if w[2] == l1 and w.count(l1) == 1 and l2 not in w]
        d = [w for w in low[5] if w[3] == l2 and w.count(l2) == 1 and l1 not in w]
        e = [w for w in low[4] if w[0] == l2 and w.count(l2) == 1 and l1 not in w]
        f = [w for w in low[4] if l1 not in w and l2 not in w]
        g = [w for w in low[3] if l1 not in w and l2 not in w]
        if len(a) < 2 or not (b and d and e and f and g):
            continue
        w1, w3 = rng.sample(a, 2)
        return ((f'{w1} {rng.choice(b)} {w3}', l1),
                (f'{rng.choice(d)} {rng.choice(e)}', l2),
                (rng.choice(f), rng.choice(g), rng.choice('23456789')))
    return rng.choice(_EV_COMBOS)


def build_dungeon_echo_vault(seed: int) -> Dungeon:
    """The Echo Vault: teaches . (dot — repeat the last change).

    The vault repeats what it hears: the SAME corruption has stamped itself
    down every span — the same warped rune, over and over. Mend it once with
    r; press . and the echo mends the next. ONE visible rule, the plaque
    family's third member: each span's bolt stands open while the lock row
    READS AS ITS PLAQUE (main._echo_vault_tick — stateless, undo-safe).

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
    cells = [[CellType.WALL] * C for _ in range(R)]
    for c in range(_EV_FLOOR_LO, _EV_FLOOR_HI + 1):
        cells[_EV_ROW][c] = CellType.CORRIDOR
    for (br, bc) in (_EV_BOLT_A, _EV_BOLT_B, _EV_BOLT_C):
        cells[br][bc] = CellType.WALL              # the bolts start shut

    room = Room(room_type=RoomType.ENTRY, rows=R, cols=C)
    room.cells = cells
    room.seed  = seed

    def lay(row, col, text, kind):
        """Place `text` at (row, col); spaces become gaps between separate runs."""
        c = col
        for piece in text.split(' '):
            if piece:
                room.char_runs.append(CharRun(row, c, tuple(piece), kind))
            c += len(piece) + 1

    for col, true, lock in (
        (_EV_SEG1_COL, phrase1, warp(phrase1, _EV_WARPS1, g1)),
        (_EV_SEG2_COL, phrase2, warp(phrase2, _EV_WARPS2, g2)),
        (_EV_SEG3_COL, phrase3,
         warp(phrase3, (_EV_WARP3_SINGLE, *_EV_WARP3_TRIPLE), g3)),
    ):
        lay(_EV_PLAQUE_ROW, col, true, 'verdant')
        lay(_EV_ROW, col, lock, 'ancient')

    # The exit is edit-immune: a careless D sweeps toward its cell, and the
    # way out must not be deletable (nor the row dd-collapsible).
    room.entities.append(Entity(kind='exit', row=_EV_EXIT[0], col=_EV_EXIT[1],
                                edit_immune=True))
    room.spawn_pos = _EV_SPAWN
    room.exit_pos  = _EV_EXIT

    # Bolt specs read by main._echo_vault_tick (stateless, undo-safe): each is
    # (row, c0, target, bolt_pos) — the bolt stands open while the lock row's
    # text over [c0, c0+len(target)) READS AS the plaque.
    room._ev_bolts = [
        (_EV_ROW, _EV_SEG1_COL, phrase1, _EV_BOLT_A),
        (_EV_ROW, _EV_SEG2_COL, phrase2, _EV_BOLT_B),
        (_EV_ROW, _EV_SEG3_COL, phrase3, _EV_BOLT_C),
    ]

    room.rebuild_indexes()
    # Par tally (combo shapes identical, so this holds for every seed):
    #   w w r⟨l1⟩  w w .  w w .   (10) → mend once; the echo takes the other two
    #   w w r⟨l2⟩  w .            (6)  → a new stroke re-primes the echo
    #   w w r⟨d⟩   w w 3.         (8)  → the lone digit primes; 3. mends the triple
    #   $                         (1)  → walk out through the drawn seal
    room.par    = _EV_PAR
    room.budget = math.ceil(_EV_PAR * 1.4)
    room.answer = (f'w w r{l1} w w . w w . '
                   f'w w r{l2} w . '
                   f'w w r{digit} w w 3. $')

    apply_stone_fog(room)                 # sealed pockets sleep under fog
    dungeon = Dungeon(name='The Echo Vault', seed=seed)
    dungeon.rooms        = [room]
    dungeon.current_room = 0
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
    room.fog_cells.update(_WM_PODIUMS)
    room.fog_cells.update(hall_fog)
    room.fog_cells.update(_WM_POCKET)

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
    # braziers — so the R4 grid can only be built by copying his flame ROW
    # (linewise paste is exempt; a yanked row's flames sit where they sat).
    room._qm_chain = (_WM_FLAME, *_WM_BRAZIERS)

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
# word grinds ONE open. The bridge-word owns the WESTMOST (42) — typed water
# is always crushed against stone, never slid into an opened corridor.
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
    word written whole grinds one open (main._inscription_halls_tick) — the
    bridge-word owns the westmost, so typed water always crushes against
    stone. The ford plaque is carved in the south border.

    The par route hops jetties with ( / ) / e (sentence jumps, embraced —
    they only optimize travel; every word must still be written). Scarcity
    (see _ih_pick) keeps x+p from impersonating the verbs; the 'insert'
    token gates everything (curriculum: teaches ['insert'])."""
    rng = random.Random(seed)
    lessons = _ih_pick(rng)

    R, C = _IH_ROWS, _IH_COLS
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

    room = Room(room_type=RoomType.ENTRY, rows=R, cols=C)
    room.cells = cells
    room.seed  = seed

    def lay(row, col, text, kind):
        room.char_runs.append(CharRun(row, col, tuple(text), kind))

    # Plaques (the familiar sealed band, verdant in the wall) + fragments,
    # and the five exit walls: the bridge-word takes the westmost seal; the
    # lesson words take the rest in order.
    walls = list(_IH_SEALS)
    bolts = [(_IH_FORD_WORD, walls[0])]
    for i, (word, missing, frag) in enumerate(lessons):
        lrow, prow = _IH_LESSON_ROWS[i], _IH_PLAQUE_ROWS[i]
        if i in (0, 2):                                      # i: head missing
            lay(prow, _IH_I_HEAD, word, 'verdant')
            lay(lrow, _IH_I_HEAD, frag, 'ancient')
        else:                                                # a: tail missing
            span_lo = _ih_river_lo(lrow) - len(frag)
            lay(prow, span_lo, word, 'verdant')
            lay(lrow, span_lo, frag, 'ancient')
        bolts.append((word, walls[i + 1]))
    lay(_IH_FORD_ROW, _ih_river_lo(_IH_FORD_ROW) - len(_IH_FORD_FRAG),
        _IH_FORD_FRAG, 'ancient')                            # 'river' at 33..37
    lay(R - 1, _ih_river_lo(_IH_FORD_ROW) - len(_IH_FORD_FRAG),
        _IH_FORD_WORD, 'verdant')                            # ford plaque, south border

    room._ih_bolts = tuple(bolts)

    room.entities.append(Entity(kind='exit', row=_IH_EXIT[0], col=_IH_EXIT[1],
                                edit_immune=True))
    room.spawn_pos = (_IH_LESSON_ROWS[0], _ih_bank(_IH_LESSON_ROWS[0]))
    room.exit_pos  = _IH_EXIT

    room.rebuild_indexes()
    room.par    = _IH_PAR
    room.budget = math.ceil(_IH_PAR * 1.4)
    # Canonical answer — the sentence-hop route (drives the par; insert
    # tokens 'i…'/'a…' cost 1 + len(text), Esc spends nothing; ( ) e $ cost
    # 1 each — see tests/test_answer_paths). Since the 2026-07-10 engine fix
    # gate ticks fire ON the insert Esc, so the seals stand open before the
    # first NORMAL key — a single $ sails the whole corridor onto the exit
    # (the old tape's second $ was the pre-fix tick lag; playtest 2026-07-18):
    #   A: ( i{2}        = 1+3
    #   B: ) e a{1}      = 1+1+2
    #   C: ) i{1}        = 1+2
    #   D: ) e a{2}      = 1+1+3
    #   ford: ) e agate $ = 1+1+5+1   → total 24
    m = [m_ for (_w, m_, _f) in lessons]
    room.answer = (f'( i{m[0]} '
                   f') e a{m[1]} '
                   f') i{m[2]} '
                   f') e a{m[3]} '
                   f') e agate $')

    apply_stone_fog(room)                 # sealed pockets sleep under fog
    dungeon = Dungeon(name='The Inscription Halls', seed=seed)
    dungeon.rooms        = [room]
    dungeon.current_room = 0
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
# Three layout laws from the first playtest (all Vim-faithful — no state-toggled
# walls beyond the plaque-rule doors the whole family already uses):
#  - PLAQUE IN THE WEST WALL. Reflow is segment-bounded in BOTH directions: a
#    mid-row wall (or void rune) is a hard line boundary, so content on the far
#    side of a wall is never disturbed by an edit on the other side (push via
#    open_gap and pull via close_gap are symmetric — see engine/reflow.py). The
#    plaque could therefore live EAST of the label behind a bolt and stay safe;
#    it sits in the WEST wall here for the OTHER two reasons — WALL cells are
#    uncuttable (no `cc`/`D` can wipe the answer key) and excluded from the floor
#    scans that read each label. (Earlier, before the push was segment-bounded,
#    an east plaque on wall cells got erased on the first keystroke; that hazard
#    is gone, but west-wall placement remains the simplest safe home.)
#  - NOTHING THE PLAYER TYPES MAY CONTAIN A SPACE. The admin "karaoke" answer
#    sheet matches keystrokes against room.answer with spaces stripped as
#    separators, so a typed space is unrepresentable. Hence line doors are a
#    SINGLE wrong word (not a phrase), and `room.answer` is the real keystroke
#    string (see _wla_route / _wla_answer below).
#  - THE EXIT IS PLAIN FLOOR, NOT A GATED WALL. The bolts stand in a row WEST of
#    the exit on the gate row; the spine cell west of them is the row's first
#    standable cell. So every vertical jump (G / L / {n}G / H / M) lands on the
#    reachable spine, never the isolated exit, and `$`/`0`/`|` are segment-
#    bounded (they stop at the first shut bolt — engine `_cross_water`). No jump
#    can reach the exit until the bolts honestly open. (The first cut kept the
#    exit cell WALL until solved — a non-Vim hack, now retired for geometry.)
_WLA_ROWS, _WLA_COLS = 15, 41        # widened/heightened for the 14-char word doors (and the
                                     # WEST-wall plaque must hold the longest target, ~19 chars)
_WLA_PLQ_COL  = 1                    # plaques sit in the WEST wall (reflow-immune), cols 1..19
_WLA_COL_S    = 21                   # the spine — the gate's first standable; on lesson rows it
                                     # carries the label. Pushed east so the west wall (cols 1..20)
                                     # holds a 14-char-word + ctx plaque without spilling onto floor
_WLA_LBL_COL  = _WLA_COL_S           # labels start AT the spine (= where cc drops the cursor)
_WLA_LBL_END  = 39                   # label floor reaches this column (fits a 14-char word + ctx)
_WLA_LESSON_ROWS = tuple(range(2, 12))               # ten lesson rows, descended by j
_WLA_THROAT_ROW  = 12                                # spine-ONLY row: the block joins the gate
                                                     # only at the spine (so no east column of
                                                     # the block drops past the bolts to the exit)
_WLA_GATE_ROW    = 13                                # the gate corridor: spine · bolts · exit
_WLA_GATE_COL0   = 22                                # first bolt column (one per lesson)
_WLA_N_WORD, _WLA_N_LINE, _WLA_N_SENT = 6, 2, 2
_WLA_TRIGGERS = _WLA_N_WORD + _WLA_N_LINE + _WLA_N_SENT     # 10 doors
_WLA_WORD_LENS = (4, 6, 8, 10, 12, 14)               # word doors lengthen by 2 each row
_WLA_MIX_MIN   = 10                  # words THIS long (2-digit) are MIXED (punctuated) and force
                                     # `cE`: `ce` stops at the punctuation, count-`s` overpays the
                                     # 2-digit count — so only `cE` is both correct AND par-optimal
_WLA_EXIT = (_WLA_GATE_ROW, _WLA_GATE_COL0 + _WLA_TRIGGERS)  # plain floor, east of the bolts
_WLA_PLACEHOLDER = '◆'               # the fused rune — `s` spells it out
_WLA_PAR = 106                       # measured (drive); pinned by the playthrough test
                                     # (finale is G$ = 2 keys, not 02j$ = 4)
# Distinct words at FIXED lengths (par invariance needs fixed lengths, never
# fixed letters): 4-letter for word/rune doors, 6-letter for the whole-line
# doors — the deterministic fallback when the vocab draw comes up short.
_WLA_FALLBACK_4 = (
    'lock', 'veil', 'gate', 'bind', 'rune', 'dust', 'iron', 'moss',
    'fern', 'silt', 'oath', 'wisp', 'mire', 'peat', 'gild', 'hush',
)
# A whole-line fallback pool with pairwise-distinct FIRST and LAST letters, so any
# draw order yields a dissimilar (cc-forcing) pair. (Unreachable with the real
# vocab — the 6-letter pool is hundreds deep — but kept honest.)
_WLA_FALLBACK_6 = ('cipher', 'shadow', 'velvet', 'frozen',
                   'marble', 'liquid', 'quartz', 'bishop')
_WLA_FALLBACK_8 = ('absolute', 'crescent', 'darkened', 'flagrant',
                   'gauntlet', 'helmeted', 'ironclad', 'keystone')

# MIXED word pools — 2-digit-length tokens carrying an internal punctuation mark.
# `ce` (word-class) stops at the punctuation, so it changes only the first run and
# the bolt stays shut; only `cE` (WORD-class) spans the whole token. And because
# the length is 2 digits, a `{n}s` substitute spends one key more than `cE`. So on
# these doors `cE` alone is BOTH correct and par-optimal — the lesson. (The vocab
# tables hold no word this long, mixed or otherwise, so these are the only source.)
_WLA_WORDS_10 = (
    'fire-blade', 'moon-cloak', 'soul-flame', 'rune-stone', 'bone-shard',
    'dawn-light', 'void-touch', 'iron-grasp', 'gold-crown', 'frost-bite',
    'blood-oath', 'storm-call', 'night-fall', 'ghost-fire', 'witch-hour',
    'raven-wing',
)
_WLA_WORDS_12 = (
    'shadow-blade', 'winter-storm', 'spirit-bound', 'dragon-blood',
    'silver-crown', 'golden-chain', 'frozen-heart', 'molten-stone',
    'hollow-crown', 'sacred-flame', 'broken-blade', 'cursed-bones',
    'wicked-charm', 'raven-flight',
)
_WLA_WORDS_14 = (
    'phantom-shield', 'crimson-shroud', 'thunder-strike', 'ancient-mantle',
    'scarlet-shield', 'twisted-shadow', 'blasted-hollow', 'cracked-mirror',
    'obsidian-blade', 'spectral-flame', 'withered-crown', 'serpent-shield',
)
_WLA_MIXED_POOLS = {10: _WLA_WORDS_10, 12: _WLA_WORDS_12, 14: _WLA_WORDS_14}


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


def _draw_whole_line_pair(stream):
    """(wrong, right) drawn from the DISTINCT word stream, redrawing `right` until
    the pair is `_whole_line_dissimilar`. Falls back to the last candidate if the
    stream runs dry (only the tiny hardcoded pool — never hit by the real vocab),
    so generation always terminates."""
    wrong = next(stream)
    right = next(stream)
    while not _whole_line_dissimilar(wrong, right):
        try:
            right = next(stream)
        except StopIteration:
            break
    return wrong, right


def _wla_independent(lessons) -> bool:
    """No target reads inside another target, or inside any label — so each change
    opens exactly its own bolt. Distinct words alone USED to guarantee this, but the
    MIXED compound words embed common short words ('dragon-blood' carries 'dragon'),
    so a plain line/word/sent target can now collide with one. This is the gate that
    `_wla_pick` redraws against."""
    targets = [L['target'] for L in lessons]
    labels  = [L['label'] for L in lessons]
    for i, t in enumerate(targets):
        if any(j != i and t in u for j, u in enumerate(targets)):
            return False
        if any(t in lb for lb in labels):
            return False
    return True


def _wla_pick(rng):
    """`_wla_pick_once`, redrawn until the doors are independent (a mixed compound
    word can embed a shorter target — see `_wla_independent`). The deep pools make a
    collision rare, so this almost always returns on the first draw; the cap is a
    safety net."""
    lessons = _wla_pick_once(rng)
    for _ in range(60):
        if _wla_independent(lessons):
            break
        lessons = _wla_pick_once(rng)
    return lessons


def _wla_pick_once(rng):
    """Ten lessons at FIXED word lengths (so par is seed-invariant) — a relabelling
    each. Returns lesson dicts:
      word    — short, plain. {'label':'wrong ctx','target':'right ctx','typed':'right'}
                Lengths 4/6/8: `ce` and a `{n}s` substitute COST THE SAME, so the
                novice may use either — count-`s` is allowed, not a cheat.
      wordmix — long (10/12/14), MIXED (an internal punctuation mark). Same shape,
                but `ce` stops at the punctuation (wrong) and `{n}s` overpays the
                2-digit count, so only `cE` is correct AND par-optimal. THE LESSON.
      line    — {'label':'wrongw','target':'rightw','typed':'rightw'}  (whole line, cc)
      sent    — {'label':'◆st ctx','target':'fist ctx','typed':'fi'}   (a fused ◆, s)
    No `typed` holds a SPACE (the karaoke answer can't represent one); an internal
    hyphen is fine. All words are DISTINCT — door independence (no target is a
    substring of another label/target). The word doors lengthen by 2 each row."""
    _load_vocab_tables()
    def _plain(n, fallback):
        p = sorted({w for w in _VOCAB_PLAIN_BY_LEN.get(n, ())
                    if w.isalpha() and w.islower()})
        rng.shuffle(p)
        return iter(p if len(p) >= 8 else list(fallback))
    def _mixed(n):
        p = list(_WLA_MIXED_POOLS[n]); rng.shuffle(p); return iter(p)
    plain = {4: _plain(4, _WLA_FALLBACK_4), 6: _plain(6, _WLA_FALLBACK_6),
             8: _plain(8, _WLA_FALLBACK_8)}
    mixed = {n: _mixed(n) for n in _WLA_MIXED_POOLS}
    w4 = plain[4]                                       # ctx + sent share the 4-letter stream
    lessons = []
    for n in _WLA_WORD_LENS:
        src = plain[n] if n < _WLA_MIX_MIN else mixed[n]
        wrong, right = _draw_whole_line_pair(src)       # dissimilar — the diff spans the whole
        ctx = next(w4)                                  # word (no cheaper r/count-s rewrite)
        lessons.append({'kind': 'word' if n < _WLA_MIX_MIN else 'wordmix', 'len': n,
                        'label': f'{wrong} {ctx}', 'target': f'{right} {ctx}', 'typed': right})
    for _ in range(_WLA_N_LINE):
        wrong, right = _draw_whole_line_pair(plain[6])  # dissimilar — forces cc, no r/count-s cheese
        lessons.append({'kind': 'line', 'label': wrong,
                        'target': right, 'typed': right})
    for _ in range(_WLA_N_SENT):
        wanted, ctx = next(w4), next(w4)
        lessons.append({'kind': 'sent',
                        'label': f'{_WLA_PLACEHOLDER}{wanted[2:]} {ctx}',
                        'target': f'{wanted} {ctx}', 'typed': wanted[:2]})
    return lessons


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
    """room.answer: the real keystroke tape (printable keys only — Esc omitted).
    Spaces separate tokens for the karaoke display and are stripped when matched;
    no `typed` value contains a space, so the tape is unambiguous."""
    return ' '.join(keys + typed for keys, typed in _wla_route(lessons) if keys or typed)


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
    cells = [[CellType.WALL] * C for _ in range(R)]
    for r in _WLA_LESSON_ROWS:                       # the open lesson block (label floor)
        for c in range(_WLA_COL_S, _WLA_LBL_END + 1):
            cells[r][c] = CellType.FLOOR
    cells[_WLA_THROAT_ROW][_WLA_COL_S] = CellType.FLOOR  # spine-only throat: block → gate
    cells[_WLA_GATE_ROW][_WLA_COL_S] = CellType.FLOOR    # the spine reaches the gate row
    # the exit cell STAYS WALL — the FINAL SEAL; the tick floors it when every
    # plaque reads true (A/o can carve/fabricate floor, so geometry alone no
    # longer bars the way east of the bolts — see _whole_line_annex_tick).
    # The bolt cells (the gate row, between the spine and the exit) stay WALL at
    # build; the tick opens each when its label reads true. The exit needs no
    # gating: the throat row joins the block to the gate ONLY at the spine, so no
    # east column of the block drops onto the exit; the exit is never a row's
    # first standable cell (jumps land on the spine) and `$` stops at the first
    # shut bolt (engine `_cross_water`). It opens honestly, bolt by bolt.

    room = Room(room_type=RoomType.ENTRY, rows=R, cols=C)
    room.cells = cells
    room.seed  = seed

    def lay(row, col, text, kind):
        room.char_runs.append(CharRun(row, col, tuple(text), kind))

    doors = []
    for i, lesson in enumerate(lessons):
        lrow = _WLA_LESSON_ROWS[i]
        lesson['row'] = lrow
        if lesson['kind'] in ('word', 'wordmix'):
            # Lay the word and its context as SEPARATE runs with a bare-floor gap,
            # not one run with a space GLYPH: a space glyph reads as punctuation, so
            # `E` would run straight THROUGH it and `cE` would eat the context. A
            # real empty floor cell is whitespace, so `E` stops at the word's end
            # (the L24 C-door fix). `e` still halts at the inner punctuation.
            col = _WLA_LBL_COL
            for w in lesson['label'].split(' '):
                lay(lrow, col, w, 'ancient')
                col += len(w) + 1
        else:
            lay(lrow, _WLA_LBL_COL, lesson['label'], 'ancient')    # wrong label, on the floor
        lay(lrow, _WLA_PLQ_COL, lesson['target'], 'verdant')       # the plaque, in the WEST wall
        doors.append((lesson['target'], (_WLA_GATE_ROW, _WLA_GATE_COL0 + i)))
    room._wla_doors   = tuple(doors)
    room._wla_lessons = tuple(lessons)

    room.entities.append(Entity(kind='exit', row=_WLA_EXIT[0], col=_WLA_EXIT[1],
                                edit_immune=True))
    room.spawn_pos = (_WLA_LESSON_ROWS[0], _WLA_LBL_COL)       # on lesson 1's wrong word
    room.exit_pos  = _WLA_EXIT

    room.rebuild_indexes()
    room.par    = _WLA_PAR
    # The lesson is forced by PAR, not by the budget (a sub-optimal solve still
    # WINS, it just misses two stars): `cE` is the only tool that is both correct
    # (on a mixed door `ce` stops at the punctuation) AND par-optimal (`{n}s`
    # overpays the 2-digit count), so an all-`s` solve lands one key over par per
    # 2-digit door. The budget stays generous (par + TRIGGERS − 1) — enough to bar
    # only the truly-old d/x + i route (par + TRIGGERS). See the playthrough tests.
    room.budget = _WLA_PAR + _WLA_TRIGGERS - 1
    room.answer = _wla_answer(lessons)     # the real keystroke tape (karaoke)

    dungeon = Dungeon(name='The Change Annex', seed=seed)
    dungeon.rooms        = [room]
    dungeon.current_room = 0
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
#  - Reflow is now segment-bounded both ways (2026-06-26), so the plaque could sit
#    east behind a bolt; it stays in the WEST wall here only to be uncuttable and
#    off the floor scans.
_CE_ROWS, _CE_COLS = 17, 29
_CE_PLQ_COL  = 1                     # plaques in the WEST wall (uncuttable, off the scans)
_CE_COL_S    = 11                    # the spine — the gate's first standable; on lesson rows it
                                     # carries the label (no blank margin, so the word a cc/S
                                     # lands at the spine reads aligned with every other label)
_CE_LBL_COL  = _CE_COL_S             # labels start AT the spine (= where cc/S drops the cursor)
_CE_LBL_END  = 27                    # label floor reaches this column (fits the longest C label)
_CE_LESSON_ROWS = tuple(range(2, 14))                # twelve doors, an open block (rows 2..13)
_CE_THROAT_ROW  = 14                                 # spine-ONLY row: block → gate
_CE_GATE_ROW    = 15                                 # the gate corridor: spine · bolts · exit
_CE_GATE_COL0   = 12                                 # first bolt column (one per door)
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
_CE_TRIGGERS = len(_CE_KIND_ORDER)                   # 12 doors
_CE_N_S = _CE_KIND_ORDER.count('sline')              # 3
_CE_N_C = _CE_KIND_ORDER.count('ceol')               # 3
_CE_SAVING = _CE_N_S + _CE_N_C                        # 6 doors that the shorthands shorten
_CE_EXIT = (_CE_GATE_ROW, _CE_GATE_COL0 + _CE_TRIGGERS)   # plain floor, east of the bolts
_CE_PLACEHOLDER = '◆'                # the fused rune — `s` spells it out
_CE_SYMBOL      = '★'                # the WORD-spanning symbol — `cE` crosses it, `ce` stops
# par is COMPUTED from the canonical route once below (seed-invariant — every door's
# keystrokes and typed text are fixed length); pinned by tests.

# Distinct words at FIXED lengths (par invariance needs fixed lengths): 6-letter
# for the whole-line S doors (two per door — wrong label + right target), 4-letter
# for the C tails / word / rune doors. Deterministic fallbacks when the vocab draw
# is short. Eight 6-letter, twenty-one 4-letter are needed.
# Pairwise-distinct first AND last letters (dissimilar in any draw order) — see
# _WLA_FALLBACK_6. Eight 6-letter words are needed (four S doors, a pair each).
_CE_FALLBACK_6 = ('cipher', 'shadow', 'velvet', 'frozen',
                  'marble', 'liquid', 'quartz', 'bishop')
_CE_FALLBACK_4 = (
    'lock', 'veil', 'gate', 'bind', 'rune', 'dust', 'iron', 'moss',
    'fern', 'silt', 'oath', 'wisp', 'mire', 'peat', 'gild', 'hush',
    'kiln', 'tarn', 'wyrm', 'sear', 'lode', 'glen', 'rime', 'spar',
    'cove', 'dune', 'fang', 'helm', 'jade', 'reef', 'thaw', 'yarn',
)


def _ce_pick(rng):
    """Twelve lessons, each a (label → target) relabelling at FIXED word lengths
    so par is seed-invariant. Returns lesson dicts:
      sline  — {'label': 'wrongw', 'target': 'rightw', 'typed': 'rightw'}   (one 6-letter word)
      ceol   — {'label': 'pre bad rot', 'target': 'pre fix', 'typed': 'fix'} (prefix kept, 2-word tail → 1)
      word   — {'label': 'wrong ctx', 'target': 'right ctx', 'typed': 'right'}
      wordW  — {'label': 'fr★ee ctx', 'target': 'step ctx', 'typed': 'step'}  (cE crosses ★, ce stops)
      rune   — {'label': '◆st ctx',   'target': 'fist ctx',  'typed': 'fi'}
      bracket— {'label': '(co)il ctx', 'target': 'buil ctx', 'typed': 'bu'}   (c% swaps the bracket span)
    All words are drawn DISTINCT across the level, which alone guarantees door
    independence (no target is a substring of another label/target): every
    space-bearing target needs a unique two-word sequence, and the only space-free
    target — the 6-letter S word — cannot sit inside a 4-letter word. No `typed`
    value contains a SPACE (the C tail collapses to a single word), so the karaoke
    answer tape is unambiguous."""
    _load_vocab_tables()
    def _pool(n, need, fallback):
        p = sorted({w for w in _VOCAB_PLAIN_BY_LEN.get(n, ())
                    if w.isalpha() and w.islower()})
        rng.shuffle(p)
        return iter(p if len(p) >= need else list(fallback))
    # 4-letter draws: C pre/badA/badB/right; word wrong/right/ctx; each cE
    # src/right/ctx; each rune wanted/ctx; bracket src/typed-src/ctx.
    need4 = (_CE_KIND_ORDER.count('ceol') * 4 + _CE_KIND_ORDER.count('word') * 3
             + _CE_KIND_ORDER.count('wordW') * 3 + _CE_KIND_ORDER.count('rune') * 2
             + _CE_KIND_ORDER.count('bracket') * 3)
    need6 = _CE_N_S * 2                    # S: wrong label + right target
    w6 = _pool(6, need6, _CE_FALLBACK_6)
    w4 = _pool(4, need4, _CE_FALLBACK_4)
    lessons = []
    for kind in _CE_KIND_ORDER:
        if kind == 'sline':
            wrong, right = _draw_whole_line_pair(w6)   # dissimilar — forces S, no r/count-s cheese
            lessons.append({'kind': 'sline', 'label': wrong,
                            'target': right, 'typed': right})
        elif kind == 'ceol':
            pre, badA, badB, right = next(w4), next(w4), next(w4), next(w4)
            lessons.append({'kind': 'ceol', 'label': f'{pre} {badA} {badB}',
                            'target': f'{pre} {right}', 'typed': right})
        elif kind == 'word':
            wrong, right, ctx = next(w4), next(w4), next(w4)
            lessons.append({'kind': 'word', 'label': f'{wrong} {ctx}',
                            'target': f'{right} {ctx}', 'typed': right})
        elif kind == 'wordW':
            # A symbol-spanning WORD: `ce` stops at the symbol (changes only the
            # head), `cE` rewrites the whole WORD. Context word kept.
            src, right, ctx = next(w4), next(w4), next(w4)
            word_w = f'{src[:2]}{_CE_SYMBOL}{src[2:]}'     # e.g. 'mo★ss'
            lessons.append({'kind': 'wordW', 'label': f'{word_w} {ctx}',
                            'target': f'{right} {ctx}', 'typed': right})
        elif kind == 'bracket':
            # A bracketed head on a kept stem: `c%` changes '(' to its match ')'
            # (just the bracketed bit), keeping the stem. `ce` stops inside, `cE`
            # eats the stem, S/C clobber the context.
            src, tsrc, ctx = next(w4), next(w4), next(w4)
            junk, stem, fix = src[:2], src[2:], tsrc[:2]    # '(ju)st' -> 'fixst'
            lessons.append({'kind': 'bracket',
                            'label': f'({junk}){stem} {ctx}',
                            'target': f'{fix}{stem} {ctx}', 'typed': fix})
        else:                              # rune
            wanted, ctx = next(w4), next(w4)
            lessons.append({'kind': 'rune',
                            'label': f'{_CE_PLACEHOLDER}{wanted[2:]} {ctx}',
                            'target': f'{wanted} {ctx}', 'typed': wanted[:2]})
    return lessons


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
    steps.append(('G$', ''))               # G to the gate row (last line), $ east to the exit
    return steps


def _ce_answer(lessons):
    """room.answer: the real keystroke tape (printable keys only — Esc omitted).
    Spaces separate tokens for the karaoke display and are stripped when matched;
    no `typed` value contains a space, so the tape is unambiguous."""
    return ' '.join(keys + typed for keys, typed in _ce_route(lessons) if keys or typed)


# Fixed typed length per door kind (par invariance): the whole-line S word is 6,
# the C tail / word / cE replacement 4, the rune / bracket head 2.
_CE_TYPED_LEN = {'sline': 6, 'ceol': 4, 'word': 4, 'wordW': 4, 'rune': 2, 'bracket': 2}


def _ce_par() -> int:
    """The canonical route's keystroke count, COMPUTED from _ce_route so it can
    never drift from the verb/prefix maps. Seed-invariant — every door's keys and
    typed text are fixed length — so a dummy lessons list with the right typed
    lengths gives the exact par (no vocab draw needed)."""
    dummy = [{'kind': k, 'typed': 'x' * _CE_TYPED_LEN[k]} for k in _CE_KIND_ORDER]
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
    cells = [[CellType.WALL] * C for _ in range(R)]
    for r in _CE_LESSON_ROWS:                        # the open lesson block (label floor)
        for c in range(_CE_COL_S, _CE_LBL_END + 1):
            cells[r][c] = CellType.FLOOR
    cells[_CE_THROAT_ROW][_CE_COL_S] = CellType.FLOOR  # spine-only throat: block → gate
    cells[_CE_GATE_ROW][_CE_COL_S] = CellType.FLOOR    # the spine reaches the gate row
    # the exit cell STAYS WALL — the FINAL SEAL; the tick floors it when every
    # plaque reads true (A/o can carve/fabricate floor, so geometry alone no
    # longer bars the way east of the bolts — see _whole_line_annex_tick).
    # The bolt cells (gate row, between spine and exit) stay WALL at build; the
    # tick opens each when its label reads true. The throat joins block→gate ONLY
    # at the spine, so no east column drops onto the exit; the exit is never a
    # row's first standable cell and `$` stops at the first shut bolt.

    room = Room(room_type=RoomType.ENTRY, rows=R, cols=C)
    room.cells = cells
    room.seed  = seed

    def lay(row, col, text, kind):
        room.char_runs.append(CharRun(row, col, tuple(text), kind))

    doors = []
    for i, lesson in enumerate(lessons):
        lrow = _CE_LESSON_ROWS[i]
        lesson['row'] = lrow
        if lesson['kind'] in ('ceol', 'wordW', 'bracket'):
            # Lay each token as its OWN run with a bare-floor gap between them, not
            # one run with an embedded space glyph: a space glyph is a punctuation
            # 'word' (engine word-class quirk), so `w` and the `cE`/`c%` WORD scans
            # would treat the whole "head ctx" as ONE non-blank WORD and eat the
            # context. A real floor gap is genuine whitespace, so `cE` stops at the
            # head's end and the C route's `w` lands on the wrong tail. The floor
            # scan reconstructs the space from the empty cell, so the target reads
            # identically. (Word/rune doors never scan across the space — `ce`/`s`
            # stop at the first letter-word end — so they keep the single-run shape.)
            col = _CE_LBL_COL
            for word in lesson['label'].split(' '):
                lay(lrow, col, word, 'ancient')
                col += len(word) + 1
        else:
            lay(lrow, _CE_LBL_COL, lesson['label'], 'ancient')  # wrong label, on the floor
        lay(lrow, _CE_PLQ_COL, lesson['target'], 'verdant')    # the plaque, in the WEST wall
        doors.append((lesson['target'], (_CE_GATE_ROW, _CE_GATE_COL0 + i)))
    # The tick is the Annex's generic plaque-door scan, keyed on `room._wla_doors`.
    room._wla_doors   = tuple(doors)
    room._ce_lessons  = tuple(lessons)

    room.entities.append(Entity(kind='exit', row=_CE_EXIT[0], col=_CE_EXIT[1],
                                edit_immune=True))
    room.spawn_pos = (_CE_LESSON_ROWS[0], _CE_LBL_COL)         # on door 1's wrong word
    room.exit_pos  = _CE_EXIT

    room.rebuild_indexes()
    room.par    = _CE_PAR
    # TIGHT margin (S2 by volume): the all-old route swaps S→cc and C→c$ (+1 key
    # each over the shorthand), so it costs par + _CE_SAVING; a margin of
    # _CE_SAVING − 1 makes that route overshoot by one while the S/C route clears
    # at par. Pinned by tests/test_change_extension.py.
    room.budget = _CE_PAR + _CE_SAVING - 1
    room.answer = _ce_answer(lessons)      # the real keystroke tape (karaoke)

    dungeon = Dungeon(name='The Change Extension', seed=seed)
    dungeon.rooms        = [room]
    dungeon.current_room = 0
    return dungeon


# ── The Sculpting Chambers (I A o O) ──────────────────────────────────────────
# The topology lesson — the four insert-ENTRIES that reshape the stone, split by
# axis so each does ONE thing (see the o/O engine change: o/O open a Vim BLANK
# line, segment-width, never bridging a wall column — that axis is A's):
#   • A  — the HORIZONTAL sculptor: `extend_floor` carves floor east THROUGH a
#          wall column (the game's only wall→floor build). The vault's outer
#          stone plugs the one corridor to the door; only A breaches it. ∞.
#   • o/O — the VERTICAL sculptors: open a blank line below / above to carve a new
#          verse of the vault's votive. The dedication must READ, line upon line,
#          keep · seal · sesame · amen; only `seal` and the `same`-stub are given,
#          so the player must OPEN the lines the other verses live on. `keep` sits
#          ABOVE the topmost given line (only `O` reaches above) and `amen` BELOW
#          the lowest (only `o` reaches below) — the two are forced apart by
#          direction. ∞ (i/a cannot add a row).
#   • I  — the votive's keystone: the `sesame` line is given only its tail
#          (`same`); after the A-work the cursor sits far EAST, so `I` (first-non-
#          blank insert, one key) jumps to the line start to prepend `se` →
#          `sesame`. Soft-forced (`I` saves the ^i / 0i walk); the finale.
# The vault door (a single gated cell) opens the instant the votive reads true —
# the password drops the key. The tick (`_sculpting_chambers_tick`) is text- and
# exit_pos-relative, so it is immune to the row shifts o/O/I cause (the Manifold
# discipline). A cannot cheat the door: the door is a VERTICAL step off the
# corridor's end (A builds east, never into it) and void runes cap every floor
# edge A could otherwise build from toward it.
_SC_ROWS, _SC_COLS = 9, 28
_SC_WCOL = 13                       # the votive's verses start here — a 4-cell wall GAP (cols 9-12)
                                    # breathes between the west-wall plaques and the carving floor
_SC_PLQ  = 1                        # plaque column, in the WEST wall
_SC_SEAL_ROW = 4                    # the given anchor line ('seal') at build
_SC_PASS_ROW = 5                    # the given password line (tail 'same') just below it
_SC_BAND = (_SC_WCOL, _SC_WCOL + 12)   # scan window for each row's leading verse
_SC_TARGET = ('keep', 'seal', 'sesame', 'amen')   # the votive, read top → bottom
_SC_CARVE  = 'hew'                  # the word A must CARVE into the seal line's stone (its plaque names it)
_SC_SEAL_END = 17                   # the 'seal' segment's east edge — A's launch cell (bare gap)
_SC_PLUG   = (18, 20)               # the solid stone east of 'seal' where A cuts _SC_CARVE
_SC_EXIT_COL = 16                   # the vault door: a step SOUTH of the LAST verse (amen's end col)
_SC_EXIT_ROW0 = _SC_PASS_ROW + 1    # at BUILD, one row below the password line; the o/O inserts
                                    # slide it down so it ends up just below `amen` (exit_pos rides them)


# The route runs TOP-TO-BOTTOM, one act per line (the natural reading order):
# O keep(5) · j(1) · A hew(4) · ^(1) · j(1) · I se(3) · o amen(5) · j(1) = 21.
# The carve is line 2's act, done IN PLACE (not saved for last); `^` returns from
# the cut to the spine to keep descending. The door sits below the LAST verse
# (amen), so completing the votive drops you onto it — and the carve's / amen's
# Esc fires the gate tick (main._content_ticks), so a single `j` steps through.
# Esc is free/omitted; spaces separate tokens. The A-carve is the SPECIFIC word
# `hew` (not filler) — named on the seal plaque (`seal hew`).
_SC_PAR    = 21
_SC_ANSWER = 'Okeep j Ahew ^ j Ise oamen j'


def build_dungeon_sculpting_chambers(seed: int) -> Dungeon:
    """The Sculpting Chambers (slug `sculpting_chambers`): I A o O.

    A votive tablet the player carves open. `seal` and the `same`-stub are given;
    O opens `keep` above, o opens `amen` below, I prepends `se` → `sesame`. When
    the four verses read in order the vault door (a gated cell south of an
    isolated corridor) unseals — but the corridor is walled off by a stone plug
    that only A can breach. See the section header for the axis split."""
    R, C = _SC_ROWS, _SC_COLS
    cells = [[CellType.WALL] * C for _ in range(R)]

    def floor(r, c0, c1):
        for c in range(c0, c1 + 1):
            cells[r][c] = CellType.FLOOR

    sr, pr = _SC_SEAL_ROW, _SC_PASS_ROW
    floor(sr, _SC_WCOL, _SC_SEAL_END)             # 'seal' segment (+ a bare col: A's launch cell)
    floor(pr, _SC_WCOL, _SC_WCOL + 5)              # the password line (fits 'sesame' + the `se` push)
    # East of the 'seal' segment is SOLID STONE (sr, 14..). A cuts `hew` INTO it —
    # a content inscription (only A writes into wall), NOT a path; the seal line's
    # 2nd token must read `hew`. The vault door is elsewhere: a step SOUTH of the
    # LAST verse (amen), which lands one row below the given password line —
    # `_SC_EXIT_ROW0`. So the votive is carved top-to-bottom and the door drops you
    # out at the bottom; A (an east-builder) can never back-door a door due south.

    room = Room(room_type=RoomType.ENTRY, rows=R, cols=C)
    room.cells = cells
    room.seed  = seed

    def lay(r, c, text, kind):
        room.char_runs.append(CharRun(r, c, tuple(text), kind))

    lay(sr, _SC_WCOL, 'seal', 'ancient')          # the given anchor verse
    lay(pr, _SC_WCOL, 'same', 'ancient')          # the password's given tail
    # The votive reference, in the WEST wall (verdant plaques). The seal plaque
    # ALSO carries the carve word `hew` (`seal hew`), so the A-cut is a named
    # sequence, not arbitrary filler. The tick keeps every plaque ALIGNED with its
    # verse as o/O insert rows (see _sculpting_chambers_tick).
    _plaque_text = {'seal': f'seal {_SC_CARVE}'}
    for k, word in enumerate(_SC_TARGET):
        lay(sr - 1 + k, _SC_PLQ, _plaque_text.get(word, word), 'verdant')

    room._sc_target = _SC_TARGET
    room._sc_carve  = _SC_CARVE
    room._sc_band   = _SC_BAND

    # The door: a step SOUTH of the last verse (amen), one row below the given
    # password line. It stays WALL until the votive + carve read true.
    exit_pos = (_SC_EXIT_ROW0, _SC_EXIT_COL)
    room.entities.append(Entity(kind='exit', row=exit_pos[0], col=exit_pos[1], edit_immune=True))
    room.spawn_pos = (sr, _SC_WCOL)               # on the 'seal' verse
    room.exit_pos  = exit_pos

    room.rebuild_indexes()
    room.par    = _SC_PAR
    room.budget = math.ceil(_SC_PAR * 1.4)
    room.answer = _SC_ANSWER

    dungeon = Dungeon(name='The Sculpting Chambers', seed=seed)
    dungeon.rooms        = [room]
    dungeon.current_room = 0
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
# of bolts, and a plain-floor exit east of them (`_whole_line_annex_tick`, keyed
# on room._wla_doors; R overwrites IN PLACE so the floor scan is shift-free).
_OH_ROWS, _OH_COLS = 10, 24
_OH_PLQ_COL = 1                     # the true word, in the WEST wall (cols 1..8)
_OH_COL_S   = 10                    # the spine — the gate's first standable; the word floor start
_OH_LBL_COL = _OH_COL_S            # the wrong word sits on the floor here
_OH_LBL_END = 18                    # word floor reaches here (fits the 8-char stream words)
_OH_LESSON_ROWS = (2, 3, 4, 5, 6)   # five corridors, descended by j
_OH_THROAT_ROW  = 7                 # spine-only row: the block joins the gate
_OH_GATE_ROW    = 8                 # the gate corridor: spine · bolts · exit
_OH_GATE_COL0   = 11                # first bolt column (one per corridor)
_OH_TRIGGERS    = len(_OH_LESSON_ROWS)
_OH_EXIT = (_OH_GATE_ROW, _OH_GATE_COL0 + _OH_TRIGGERS)   # plain floor, east of the bolts
_OH_RUN = 'xzq'                     # the 3-cell corruption every stream shares (fx finds it)

# (kind, target, wrong). STREAM: a 3-cell varied run mid-word (fx→R fixes it,
# S/cc/ce overpay). STITCH: one wrong cell (r's niche). Order interleaves them.
_OH_LESSONS = (
    ('stream', 'guardian', 'guar' + _OH_RUN + 'n'),   # guar·[dia→xzq]·n
    ('stitch', 'sentry',   'sentxy'),                  # sent·[r→x]·y
    ('stream', 'rampart',  'ra' + _OH_RUN + 'rt'),     # ra·[mpa→xzq]·rt
    ('stitch', 'portal',   'portil'),                  # port·[a→i]·l
    ('stream', 'bastion',  'ba' + _OH_RUN + 'on'),     # ba·[sti→xzq]·on
)
# par + the canonical tape, driven end-to-end (no Dijkstra — R overwrites in
# place, but the fx-R-run route is hand-measured like the Annex). The route is
# the GOLFED one — `F` (backward-find, NOT `^f`) back to each run, the C4 stitch
# taken free (the descent lands the cursor on it), and `G$` (NOT `^jj$`) to the
# door:  fx Rdia · Fx rr · Fx Rmpa · ra · Fx Rsti · G$  = 30 keys.
# Rivals measured on the SAME seed-invariant geometry with the SAME golfed nav:
# all-`S` (retype the whole word) = 39, all-`r`-chain = 42. The budget bars the
# cheapest no-R route (all-S) by one: par + _OH_SAVING(9) − 1 = 38 < 39.
# (An earlier hand-route used `^f`/`^jj$` and mis-set par to 38 — a nav cheese;
# see tests/test_overwrite_halls.py::test_no_cheaper_nav_beats_par.)
_OH_PAR    = 30
_OH_ANSWER = 'fx Rdia j Fx rr j Fx Rmpa j ra j Fx Rsti G$'
_OH_SAVING = 9


def build_dungeon_overwrite_halls(seed: int) -> Dungeon:
    """The Overwrite Halls (slug `overwrite_halls`): R.

    Five mislabelled corridors on the Change-Annex chassis. STREAM doors bury a
    run of consecutive varied wrong cells mid-word — only `R` (overtype) fixes
    them without clobbering the correct prefix/suffix; STITCH doors have one wrong
    cell where `r` still rules. See the section header for the forcing."""
    R, C = _OH_ROWS, _OH_COLS
    cells = [[CellType.WALL] * C for _ in range(R)]
    for r in _OH_LESSON_ROWS:                        # the open corridor block
        for c in range(_OH_COL_S, _OH_LBL_END + 1):
            cells[r][c] = CellType.FLOOR
    cells[_OH_THROAT_ROW][_OH_COL_S] = CellType.FLOOR   # spine-only throat
    cells[_OH_GATE_ROW][_OH_COL_S]   = CellType.FLOOR   # the spine reaches the gate row
    # the exit cell STAYS WALL — the FINAL SEAL; the tick floors it when every
    # plaque reads true (A/o can carve/fabricate floor, so geometry alone no
    # longer bars the way east of the bolts — see _whole_line_annex_tick).
    # the bolt cells (gate row, between spine and exit) stay WALL; the tick opens
    # each when its corridor reads true.

    room = Room(room_type=RoomType.ENTRY, rows=R, cols=C)
    room.cells = cells
    room.seed  = seed

    def lay(r, c, text, kind):
        room.char_runs.append(CharRun(r, c, tuple(text), kind))

    doors = []
    lessons = []
    for i, (kind, target, wrong) in enumerate(_OH_LESSONS):
        lrow = _OH_LESSON_ROWS[i]
        lay(lrow, _OH_LBL_COL, wrong, 'ancient')             # the WRONG word, on the floor
        lay(lrow, _OH_PLQ_COL, target, 'verdant')            # the true word, the WEST-wall plaque
        doors.append((target, (_OH_GATE_ROW, _OH_GATE_COL0 + i)))
        lessons.append({'kind': kind, 'target': target, 'wrong': wrong, 'row': lrow})
    room._wla_doors    = tuple(doors)                        # reuse the Annex tick
    room._oh_lessons   = tuple(lessons)

    room.entities.append(Entity(kind='exit', row=_OH_EXIT[0], col=_OH_EXIT[1],
                                edit_immune=True))
    room.spawn_pos = (_OH_LESSON_ROWS[0], _OH_COL_S)         # on corridor 1, at the spine
    room.exit_pos  = _OH_EXIT

    room.rebuild_indexes()
    room.par    = _OH_PAR
    room.budget = _OH_PAR + _OH_SAVING - 1       # TIGHT (Annex model): all-S overshoots by one
    room.answer = _OH_ANSWER

    dungeon = Dungeon(name='The Overwrite Halls', seed=seed)
    dungeon.rooms        = [room]
    dungeon.current_room = 0
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
# a plain-floor exit east of them (`_whole_line_annex_tick` on room._wla_doors).
_CASE_ROWS, _CASE_COLS = 13, 27
_CASE_PLQ_COL = 1                     # the true form, in the WEST wall (cols 1..11)
_CASE_COL_S   = 15                    # the spine — every row's first standable; a
                                      # 3-col wall gap (12..14) breathes between the
                                      # plaques and the floor (playtest 2026-07-12:
                                      # an ADJACENT plaque run merged with the floor
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
    cells = [[CellType.WALL] * C for _ in range(R)]
    for i, (kind, target, wrong) in enumerate(_CASE_LESSONS):
        r = _CASE_LESSON_ROWS[i]
        for c in range(_CASE_COL_S, _CASE_COL_S + len(wrong)):   # EXACT-FIT corridor:
            cells[r][c] = CellType.FLOOR                     # $ ends ON the word
    cells[_CASE_THROAT_ROW][_CASE_COL_S] = CellType.FLOOR   # spine-only throat
    cells[_CASE_GATE_ROW][_CASE_COL_S]   = CellType.FLOOR   # the spine reaches the gate row
    # the exit cell STAYS WALL — the FINAL SEAL; the tick floors it when every
    # plaque reads true (A/o can carve/fabricate floor, so geometry alone no
    # longer bars the way east of the bolts — see _whole_line_annex_tick).
    # the bolt cells (gate row, between spine and exit) stay WALL; the tick opens
    # each when its corridor's case reads true.

    room = Room(room_type=RoomType.ENTRY, rows=R, cols=C)
    room.cells = cells
    room.seed  = seed

    def lay(r, c, text, kind):
        # split on spaces — a literal space glyph is a punctuation "word" (the
        # Change Extension gotcha); the floor scan reconstructs the gap.
        col = c
        for part in text.split(' '):
            if part:
                room.char_runs.append(CharRun(r, col, tuple(part), kind))
            col += len(part) + 1

    doors = []
    lessons = []
    for i, (kind, target, wrong) in enumerate(_CASE_LESSONS):
        lrow = _CASE_LESSON_ROWS[i]
        lay(lrow, _CASE_LBL_COL, wrong, 'ancient')             # the mis-cased word, on the floor
        lay(lrow, _CASE_PLQ_COL, target, 'verdant')            # the true form, the WEST-wall plaque
        doors.append((target, (_CASE_GATE_ROW, _CASE_GATE_COL0 + i)))
        lessons.append({'kind': kind, 'target': target, 'wrong': wrong, 'row': lrow})
    room._wla_doors  = tuple(doors)                          # reuse the Annex tick
    room._cc_lessons = tuple(lessons)

    room.entities.append(Entity(kind='exit', row=_CASE_EXIT[0], col=_CASE_EXIT[1],
                                edit_immune=True))
    room.spawn_pos = (_CASE_LESSON_ROWS[0], _CASE_COL_S)         # on corridor 1, at the spine
    room.exit_pos  = _CASE_EXIT

    room.rebuild_indexes()
    room.par    = _CASE_PAR
    room.budget = math.ceil(_CASE_PAR * 1.4)       # STANDARD: volume alone bars the r-chain/retype
    room.answer = _CASE_ANSWER

    dungeon = Dungeon(name='The Case Chambers', seed=seed)
    dungeon.rooms        = [room]
    dungeon.current_room = 0
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
# J is a TERRAIN EDITOR, so the chassis had to be hardened first (2026-07-12):
#   • every join removes a row and slides the gate/bolts/exit UP —
#     `_whole_line_annex_tick` derives the gate row from exit_pos each tick
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

    room = Room(room_type=RoomType.ENTRY, rows=R, cols=C)
    room.cells = cells
    room.seed  = seed

    def lay(r, c, text, kind):
        col = c
        for part in text.split(' '):                     # separate CharRuns per word
            if part:
                room.char_runs.append(CharRun(r, col, tuple(part), kind))
            col += len(part) + 1

    doors = []
    lessons = []
    for i, (top, (kind, target, split)) in enumerate(zip(_JG_STACK_TOPS, _JG_LESSONS)):
        for k, word in enumerate(split):
            lay(top + k, _JG_LBL_COL, word, 'ancient')   # the split words, stacked
        lay(top, _JG_PLQ_COL, target, 'verdant')         # the true line, west-wall plaque
        doors.append((target, (_JG_GATE_ROW, _JG_GATE_COL0 + i)))
        lessons.append({'kind': kind, 'target': target, 'split': split, 'top': top})
    room._wla_doors  = tuple(doors)                      # the (hardened) Annex tick
    room._jg_lessons = tuple(lessons)

    room.entities.append(Entity(kind='exit', row=_JG_EXIT[0], col=_JG_EXIT[1],
                                edit_immune=True))       # join-proof: remove_row refuses
    room.spawn_pos = (_JG_STACK_TOPS[0], _JG_COL_S)      # atop stack 1, at the spine
    room.exit_pos  = _JG_EXIT

    room.rebuild_indexes()
    room.par    = _JG_PAR
    room.budget = math.ceil(_JG_PAR * 1.4)       # STANDARD: the hand-written rival is ~4x
    room.answer = _JG_ANSWER

    dungeon = Dungeon(name="The Joiner's Gate", seed=seed)
    dungeon.rooms        = [room]
    dungeon.current_room = 0
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
    cells = [[CellType.WALL] * C for _ in range(R)]
    for r in _AH_LESSON_ROWS:                            # the open block
        for c in range(_AH_COL_S, _AH_FLOOR_END + 1):
            cells[r][c] = CellType.FLOOR
    cells[_AH_THROAT_ROW][_AH_COL_S] = CellType.FLOOR    # spine-only throat
    cells[_AH_GATE_ROW][_AH_COL_S]   = CellType.FLOOR    # the spine reaches the gate
    # bolts AND the exit stay WALL — the tick opens the bolts per seated word
    # and parts the FINAL SEAL when all five stand on the register.

    room = Room(room_type=RoomType.ENTRY, rows=R, cols=C)
    room.cells = cells
    room.seed  = seed

    def lay(r, c, text, kind):
        room.char_runs.append(CharRun(r, c, tuple(text), kind))

    for br in _AH_BAND_ROWS:                             # the plumb line marks
        lay(br, _AH_REGISTER, '│', 'verdant')

    doors = []
    lessons = []
    for i, (kind, target, wrong, offset) in enumerate(_AH_LESSONS):
        lrow = _AH_LESSON_ROWS[i]
        lay(lrow, _AH_REGISTER + offset, wrong, 'ancient')   # mis-set (mis-cased) word
        lay(lrow, _AH_PLQ_COL, target, 'verdant')            # the true form, west wall
        doors.append((target, _AH_GATE_COL0 + i))
        lessons.append({'kind': kind, 'target': target, 'wrong': wrong,
                        'offset': offset, 'row': lrow})
    room._ah_doors        = tuple(doors)
    room._ah_register_col = _AH_REGISTER
    room._ah_lessons      = tuple(lessons)

    room.entities.append(Entity(kind='exit', row=_AH_EXIT[0], col=_AH_EXIT[1],
                                edit_immune=True))
    room.spawn_pos = (_AH_LESSON_ROWS[0], _AH_COL_S)     # on row one, at the spine
    room.exit_pos  = _AH_EXIT

    room.rebuild_indexes()
    room.par    = _AH_PAR
    room.budget = math.ceil(_AH_PAR * 1.4)   # STANDARD: R-retype wins at 1 star inside it
    room.answer = _AH_ANSWER

    dungeon = Dungeon(name='The Alignment Halls', seed=seed)
    dungeon.rooms        = [room]
    dungeon.current_room = 0
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
# FORCING BY PAR with a HAND-SET GENEROUS budget (non-1.4): the manual-mason
# route (3>> banks, per-row >>/<</dot through the rite — no `=` ever) WINS at
# 1 star (~30 keys, driven in tests); the budget bars only routes clumsier
# than that. Blank FLOOR rows separate the bays, so `}` paragraph motions
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
# rite ≈ 30 — it WINS at 1 star under the hand-set budget below.
_IS_PAR    = 12
_IS_BUDGET = 31          # HAND-SET (non-1.4): manual-mason route (30) wins 1★
_IS_ANSWER = '>} 4j <} 4j =} G$'


def build_dungeon_indentation_sanctum(seed: int) -> Dungeon:
    """The Indentation Sanctum (slug `indentation_sanctum`): >{m} <{m} =.

    Two ungoverned galleries seat by paragraph shove (`>}`/`<}` — `=` there
    razes to the wall, the markdown trap); the rite, a seeded pseudocode
    block with scattered offsets, yields only to `=}` under the posted law.
    See the section header for the forcing."""
    rng = random.Random(seed)
    R, C = _IS_ROWS, _IS_COLS
    cells = [[CellType.WALL] * C for _ in range(R)]
    hall_rows = _IS_G1_ROWS + _IS_G2_ROWS + _IS_RITE_ROWS + _IS_BLANK_ROWS
    for r in hall_rows:                                  # one open hall
        for c in range(_IS_COL_S, _IS_FLOOR_END + 1):
            cells[r][c] = CellType.FLOOR
    cells[_IS_THROAT_ROW][_IS_COL_S] = CellType.FLOOR    # spine-only throat
    cells[_IS_GATE_ROW][_IS_COL_S]   = CellType.FLOOR    # the spine reaches the gate
    # bolts AND the exit stay WALL — the tick opens them; the exit is the seal.

    room = Room(room_type=RoomType.ENTRY, rows=R, cols=C)
    room.cells = cells
    room.seed  = seed

    def lay(r, c, text, kind):
        col = c
        for part in text.split(' '):                     # separate CharRuns per word
            if part:
                room.char_runs.append(CharRun(r, col, tuple(part), kind))
            col += len(part) + 1

    # THE LINTEL — the law is not a passing tip but a carving that presides
    # over the whole playthrough (playtest 2026-07-12): two lines in the top
    # wall bands, laid so the plumb │ falls exactly through the word-gap at
    # the register column ("the law is │ posted").
    lay(0, 6, 'in these halls', 'verdant')
    lay(1, 6, 'the law is posted', 'verdant')            # gap lands at col 16
    lay(1, _IS_REGISTER, '│', 'verdant')                 # the plumb line, carved above

    nouns = rng.sample(_IS_NOUNS, 6 + sum(t.count('{n}') for t, _ in _IS_RITE))
    verbs = rng.sample(_IS_VERBS, sum(t.count('{v}') for t, _ in _IS_RITE))
    g1_words, g2_words = nouns[:3], nouns[3:6]
    slot_n, slot_v = iter(nouns[6:]), iter(verbs)

    for rows, words, off in ((_IS_G1_ROWS, g1_words, -2), (_IS_G2_ROWS, g2_words, +2)):
        for r, w in zip(rows, words):
            lay(r, _IS_REGISTER + off, w, 'ancient')     # the mis-set noun
            lay(r, _IS_PLQ_COL, w, 'verdant')            # its plaque, west wall

    rite_texts = []
    for (template, col), r in zip(_IS_RITE, _IS_RITE_ROWS):
        text = template
        while '{v}' in text:
            text = text.replace('{v}', next(slot_v), 1)
        while '{n}' in text:
            text = text.replace('{n}', next(slot_n), 1)
        lay(r, col, text, 'ancient')
        rite_texts.append(text)

    room._is_g1_words    = tuple(g1_words)
    room._is_g2_words    = tuple(g2_words)
    room._is_rite_texts  = tuple(rite_texts)
    room._is_register    = _IS_REGISTER
    room._is_bolts       = tuple(_IS_GATE_COL0 + i for i in range(_IS_TRIGGERS))

    room.entities.append(Entity(kind='exit', row=_IS_EXIT[0], col=_IS_EXIT[1],
                                edit_immune=True))
    room.spawn_pos = (_IS_G1_ROWS[0], _IS_COL_S)         # atop gallery one
    room.exit_pos  = _IS_EXIT

    room.rebuild_indexes()
    room.par    = _IS_PAR
    room.budget = _IS_BUDGET
    room.answer = _IS_ANSWER

    dungeon = Dungeon(name='The Indentation Sanctum', seed=seed)
    dungeon.rooms        = [room]
    dungeon.current_room = 0
    return dungeon


# ── The Warden Scrivener (Act V boss) — "The Unfinished Manuscript" ───────────
# He has copied these halls for an age and finished nothing. The hall IS the
# page: margin glosses carved in the north and south borders, five alcoves of
# plain stone where he shelters (playtest 2026-07-12: no sigils — the walls
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
# The columns encasing him stand SYMMETRIC across the hall (playtest): the
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
# Chorus goblins (plain 'g' — copies of NOTHING; playtest: echo-tagged
# goblins wore the Warden's own W), as (alcove_dr, col) anchors like the
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
    # gloss may poke past the veil (playtest: a south gloss once overflowed
    # the fog's edge and its tail showed at level open).
    hall_fog = frozenset(
        (r, c) for r in range(1, 22) for c in range(14, _WSC_COLS - 1)
        if (r, c) not in _WSC_ALCOVES and (r, c) not in _WSC_POCKET)
    room._wsc_hall_fog   = hall_fog
    room._wsc_pocket_fog = frozenset(_WSC_POCKET)
    room.fog_cells.update(_WSC_ALCOVES)
    room.fog_cells.update(hall_fog)
    room.fog_cells.update(_WSC_POCKET)

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
# an exam introduces nothing. Full design: blueprints/gauntlet.md (delete on
# review). Par is HAND-TALLIED along the canonical tape and pinned by the
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
# feet, the permanent mist bars the $ / 0 / ^ / f scans, and a spine ◆ on
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
# misted water (row 2): the yank word and the # twin live there, walkable
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
_GNT_P1_COLS = (26, 35)             # floor island in misted water (search-only;
_GNT_P2_COLS = (26, 39)             # text at TX — the left-align law — with a
                                    # one-cell misted gap east of the spine ◆)
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
    # user-found cheese; the courses are pure water now)
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
    # (the vision flood crosses water; mist renders as haze), while the
    # islands stay search-only: water bars feet, the mist on it bars the
    # $ / 0 / ^ / f scans, } { skip flooded rows, and a match starting on
    # water is no landing. Mist is permanent (mist_cells — reveals skip it).
    mist: set = set()

    def moat(r, c0, c1):
        for c in range(c0, c1 + 1):
            cells[r][c] = CellType.WATER
            mist.add((r, c))

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

    room = Room(room_type=RoomType.ENTRY, rows=R, cols=C)
    room.cells = cells
    room.seed  = seed

    def lay(r, c, text, kind='ancient'):
        col = c
        for part in text.split(' '):
            if part:
                room.char_runs.append(CharRun(r, col, tuple(part), kind))
            col += len(part) + 1

    doors = []                     # (kind, target, bolt_col) — see _gauntlet_tick

    def door(kind, target):
        doors.append((kind, target, _GNT_BOLT0 + len(doors)))

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
    # shoves the tail east, turning ' ␣' into ' word ' — so the finished
    # line reads with single spaces and IS its plaque.
    room.char_runs.append(CharRun(_GNT_R_Y1, TX, tuple(w['u1s']), 'ancient'))
    room.char_runs.append(CharRun(_GNT_R_Y1, TX + 5, tuple(w['ymid']),
                                  'ancient'))
    door('sub', f"{w['u1s']} {w['ywd']} {w['ymid']} {w['ywd']}")
    # r19 · Y-door: the line must stand TWICE (Y p — the dup door).
    _yline = f"{w['yl1']} {w['yl2']} {w['yl3']}"
    lay(_GNT_R_YL, TX, _yline)
    door('dup', _yline)
    # The two verse doors: the lines DON'T EXIST until o authors them
    # below the pasted pair (the rune scaffold courses were cut 2026-07-18
    # — o from the row above always tied O from the row below, the same
    # edit read from either bank, and the courses were the only lines the
    # wall did not show). COLUMN-checked so a verse scattered elsewhere
    # off-TX reads false.
    door('col', w['ow1'])
    door('col', w['ow2'])
    # the nook island: the U1 forward decoy (a wrapping * lands here and
    # loses to # by one). r23 · the gate: threshold ◆ (G parks west of the
    # bolts — the GMS lesson) and the catch ◆ east of the seal ($ lands
    # there; h steps back onto the frame).
    lay(_GNT_R_NOOK, _GNT_NOOK_COLS[0], w['u1s'])
    room.char_runs.append(CharRun(_GNT_R_GATE, SP + 1, ('◆',), 'ancient'))
    room.char_runs.append(CharRun(_GNT_R_GATE, _GNT_CATCH, ('◆',), 'ancient'))
    # Threshold ◆ on every search-band row's spine cell (the shelf, both
    # pockets, the gU gallery): {n}G / H / gg / + / - land on a row's
    # FIRST NON-BLANK, which would otherwise be the row's text — a
    # two-key ferry past the search-only law. The ◆ catches the jump on
    # a one-cell ledge with water east (w stops at the bank); search
    # remains the only useful door.
    for pr in (_GNT_R_BLK, _GNT_R_P1, _GNT_R_P2, _GNT_R_P3):
        room.char_runs.append(CharRun(pr, SP, ('◆',), 'ancient'))

    # West-wall plaques: each door's FULL true reading on its own row (the
    # playtest law — a partial cure word made the player guess the rest).
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
    room._gnt_band = (_yline, w['ow1'], w['ow2'], w['u1s'])
    for pr, ptext in ((_GNT_R_YL, _yline), (_GNT_R_YL + 1, _yline),
                      (_GNT_R_YL + 2, w['ow1']), (_GNT_R_YL + 3, w['ow2']),
                      (_GNT_R_YL + 5, w['u1s'])):
        lay(pr, _GNT_PLQ_COL, ptext, 'verdant')

    room._gnt_doors = tuple(doors)
    room.entities.append(Entity(kind='exit', row=_GNT_EXIT[0], col=_GNT_EXIT[1],
                                edit_immune=True))
    room.spawn_pos = (_GNT_R_BW, SP)               # k opens the exam (row above)
    room.exit_pos  = _GNT_EXIT

    room.rebuild_indexes()
    room.fog_cells  = set(mist)                    # mist on every channel…
    room.mist_cells = set(mist)                    # …permanent: reveals skip it
    room.par    = _GNT_PAR
    room.budget = _GNT_BUDGET
    # The canonical tape (karaoke): every typed token is a single drawn word.
    room.answer = (
        f"k 3e x j b x b x j % l x j ( x "
        f"/{w['s1']}⏎ 2e r{w['rcure'][5]} n w ~ ~ w * 3b gU3e "
        f"+ cit{w['tc']} << j dw j w D j C{w['ccure']} j S{w['sword']} "
        f"j b # w yiw N qb e l p q w @b j Y p "
        f"o{w['ow1']} o{w['ow2']} G $ h")

    dungeon = Dungeon(name='The Gauntlet', seed=seed)
    dungeon.rooms        = [room]
    dungeon.current_room = 0
    return dungeon


# ── The Culling Ledger (display 40) — the ex-range family's first lesson ─────
# A stone ledger carved into the far face of a chasm: the player walks a
# reading gallery at the bottom and can NEVER stand on a ledger row — the
# text sits on MISTED floor (fog_cells ∩ mist_cells: readable in full colour
# through the renderer's carved-through-mist branch, but fog bars feet,
# match-landings, and cuts). Not one cell on a ledger row is passable, so
# every jump ferry ({n}G / G / H / M) simply FAILS — nothing to land on —
# and the ○ marker at each row's west lip is scenery: the chasm's warning.
# The ONLY hands long enough are the ranged ex commands: :{n}d, :{a},{b}d,
# and :{range}v//d. (Each row keeps ≥1 FLOOR cell so remove_row consents.)
# Blighted lines render EMBER, true lines VERDANT (the forge's colour law).
#
# v3 (2026-07-19, the register lesson): the corridor holds a KEY CHEST, a
# LOCKED DOOR mid-way, and a second locked door before the exit. The key
# lives in the unnamed register (engine law), a :d clobbers it, and there
# is only one key — so every register-writing cull must go to the black
# hole (:d _, :v//d _; :g//d is Vim-faithfully register-writing too). The
# ledger starts DARK (fog without mist): the UNSEEN-LINE LAW bars culling
# it blind, so the key must be fetched and door one opened FIRST, which
# parts the mist (adds mist to the fogged ledger — readable, still
# unwalkable). Verdant lines each carry a lit brazier at col 30; a cold
# one waits on the corridor: when the ledger reads true, the corridor
# brazier catches their fire and its light unveils the exit pocket (the
# second locked door still wants the key — mind what you cut). A key
# pasted onto the floor is swept away by the mist (no stashing it past
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
_CL_PAR    = 36    # 2l(2) x(1) $(1) p(1)  :2d␣_(5) :5,9d␣_(7)
                   # :6,13v/{s4}/d␣_(15)  $(1) p(1) 4l(2)
_CL_BUDGET = 60                      # generous: the :s-blanking longhand wins 1★


def _cl_draw_words(rng):
    """(s4, b5, pool): the sacred word (len 4), the blight word (len 5), and a
    pool of distinct filler words containing neither as a substring."""
    _load_vocab_tables()
    p4, p5 = _VOCAB_PLAIN_BY_LEN[4], _VOCAB_PLAIN_BY_LEN[5]
    for _ in range(200):
        s4, b5 = rng.choice(p4), rng.choice(p5)
        pool = [w for w in p4 + p5
                if s4 not in w and b5 not in w and w not in (s4, b5)]
        if len(pool) >= 43:                    # 9 keep + 3 + 10 blight + 6 + 15
            return s4, b5, rng.sample(pool, 43)
    raise RuntimeError('culling ledger: vocab too thin')


def build_dungeon_culling_ledger(seed: int) -> Dungeon:
    dungeon = Dungeon(name='The Culling Ledger', seed=seed)
    rng = random.Random(seed ^ 0x2C11)
    s4, b5, pool = _cl_draw_words(rng)
    R, C, TX = _CL_ROWS, _CL_COLS, _CL_TX

    cells = [[CellType.WALL] * C for _ in range(R)]
    mist: set = set()                              # visible-through-haze from turn 0
    fog:  set = set()                              # DARK until door one opens
    for r in list(_CL_KEEP_ROWS) + [_CL_BLIGHT_I] + list(_CL_BLIGHT_II) \
             + list(_CL_JUNK_III) + list(_CL_SACRED_III):
        cells[r][_CL_CATCH] = CellType.FLOOR       # the ○ marker's floor cell
    # Misted-water bands at the stanza gaps and above the stone course: they
    # conduct the vision flood between stanzas AND stop the natural walk-
    # reveal (light halts at mist), so the dark ledger cannot leak open.
    for r in list(_CL_GAPS) + [_CL_SEP]:
        for c in range(2, 54):
            cells[r][c] = CellType.WATER
            mist.add((r, c))
    cells[_CL_GAP[0]][_CL_GAP[1]] = CellType.FLOOR   # the one gap in the stone
    for c in range(2, 50):
        cells[_CL_COR][c] = CellType.FLOOR         # the corridor
    for c in range(51, 55):
        cells[_CL_COR][c] = CellType.FLOOR         # the dark exit pocket

    room = Room(room_type=RoomType.ENTRY, rows=R, cols=C)
    room.cells     = cells
    room.seed      = seed
    room.spawn_pos = (_CL_COR, 2)
    room.exit_pos  = _CL_EXIT
    room.char_runs = []

    def carve(r, text, kind):
        """Lay a ledger line: the ○ marker, then the words — floor cells that
        start DARK (fog only; _ledger_check adds the mist when door one
        opens). Standable by no one either way: every jump ferry fails."""
        room.char_runs.append(CharRun(r, _CL_CATCH, ('○',), 'void'))
        fog.add((r, _CL_CATCH))
        col = TX
        for wd in text.split(' '):
            room.char_runs.append(CharRun(r, col, tuple(wd), kind))
            for c in range(col, col + len(wd)):
                cells[r][c] = CellType.FLOOR
                fog.add((r, c))
            col += len(wd) + 1
        if kind == 'verdant':                      # a lit brazier keeps the line
            room.char_runs.append(CharRun(r, _CL_BRZ_COL, (_QM_FLAME,), 'flame'))
            cells[r][_CL_BRZ_COL] = CellType.FLOOR
            fog.add((r, _CL_BRZ_COL))

    take = iter(pool)
    keeps = []
    for r in _CL_KEEP_ROWS:                        # stanza I/II true lines
        t = f'{next(take)} {next(take)} {next(take)}'
        keeps.append(t); carve(r, t, 'verdant')
    carve(_CL_BLIGHT_I, f'{next(take)} {next(take)} {next(take)}', 'ember')
    for i, r in enumerate(_CL_BLIGHT_II):          # the contiguous blight block
        w1, w2 = next(take), next(take)
        t = (f'{b5} {w1} {w2}', f'{w1} {b5} {w2}', f'{w1} {w2} {b5}')[i % 3]
        carve(r, t, 'ember')
    third = {}
    for r in _CL_SACRED_III:                       # sacred lines lead with s4
        t = f'{s4} {next(take)} {next(take)}'
        third[r] = ('verdant', t)
    for r in _CL_JUNK_III:
        third[r] = ('ember', f'{next(take)} {next(take)} {next(take)}')
    for r in sorted(third):                        # carve in row order…
        kind, t = third[r]
        carve(r, t, kind)
        if kind == 'verdant':
            keeps.append(t)                        # …so keeps stays ledger-ordered

    # The cold brazier on the corridor — the finale lights it.
    room.char_runs.append(CharRun(_CL_COR, _CL_BRZ_COL, (_QM_EMBERS,), 'pedestal'))

    room.entities = [
        Entity(kind='exit',        row=_CL_EXIT[0],  col=_CL_EXIT[1]),
        Entity(kind='chest_scroll', row=_CL_CHEST[0], col=_CL_CHEST[1]),
        Entity(kind='chest_key',   row=_CL_KEYCH[0], col=_CL_KEYCH[1]),
        Entity(kind='locked_door', row=_CL_DOOR1[0], col=_CL_DOOR1[1]),
        Entity(kind='locked_door', row=_CL_DOOR2[0], col=_CL_DOOR2[1]),
    ]
    room._ledger_keeps = tuple(keeps)              # the true lines, in order
    room._ledger_blight = b5
    room._ledger_lit = False                       # the corridor brazier, cold

    room.par    = _CL_PAR
    room.budget = _CL_BUDGET
    room.answer = (f':set␣nu⏎ 2l x $ p :2d␣_⏎ :5,9d␣_⏎ '
                   f':6,13v/{s4}/d␣_⏎ $ p 4l')

    room.rebuild_indexes()
    pocket = {(_CL_COR, c) for c in range(51, 55)}  # the dark exit pocket
    room.fog_cells  = fog | set(mist) | pocket      # fog bars feet + landings…
    room.mist_cells = set(mist)                     # …only the water shows, hazy
    dungeon.rooms        = [room]
    dungeon.current_room = 0
    return dungeon


# ── The Shelving Room (display 41) — the movers: :m :t :> :< ─────────────────
# The Culling Ledger's chasm chassis, second lesson: verses were shelved
# BLIND across the gap — one out of order, the closing refrain never shelved
# at all, two landed at the wrong depth. The true stanza is carved in the
# WEST WALL (a plaque column, row for row beside the shelf); the seal opens
# when the shelf reads the plaque exactly, indent included. No cell on a
# shelf row is passable (misted floor band), so the only movers are the
# ranged ex commands: :m reorders, :t shelves the missing copy, :> :< set
# the depth. A fresh :t/:m row is born unfogged — main's _shelving_tick
# re-mists ANY bare shelf floor each turn (the chasm law is stateless) and
# re-rights the plaque column after row inserts drag it.
_SHR_ROWS, _SHR_COLS = 11, 72
_SHR_PLQ  = 3                        # plaque head col (wall glyphs, + indent)
_SHR_TX   = 30                       # shelf floor band head col
_SHR_BAND = (30, 66)                 # the misted floor band on every shelf row
_SHR_WTR  = 8                        # the water course (sight-line + line 8's home)
_SHR_GAL  = 9                        # the reading gallery
_SHR_SEAL_COL  = 61
_SHR_CHEST_COL = 66
_SHR_EXIT_COL  = 70
# Target stanza: 8 lines, refrain (line 5's text) closing at line 8.
_SHR_INDENTS = (0, 2, 2, 0, 0, 2, 2, 0)
# Initial shelf rows 1..7: (target_index, indent) — T4 shelved second, T3 a
# step too deep, T6 flush that should stand deep, the refrain copy missing.
_SHR_INIT = ((0, 0), (3, 0), (1, 2), (2, 4), (4, 0), (5, 0), (6, 2))
_SHR_PAR    = 15                     # :2m4(4) + :5t7(4) + :3<(3) + :6>(3) + $(1)
_SHR_BUDGET = 40                     # generous: the movers invite exploration


def _shr_draw_words(rng):
    _load_vocab_tables()
    _CL_ = _VOCAB_PLAIN_BY_LEN
    pool = rng.sample(_CL_[4] + _CL_[5], 21)
    return [' '.join(pool[i * 3:i * 3 + 3]) for i in range(7)]


def build_dungeon_shelving_room(seed: int) -> Dungeon:
    dungeon = Dungeon(name='The Shelving Room', seed=seed)
    rng = random.Random(seed ^ 0x54E1)
    lines = _shr_draw_words(rng)                   # T1..T7; refrain = T5
    R, C = _SHR_ROWS, _SHR_COLS
    targets = [(' ' * _SHR_INDENTS[i]) + lines[i if i < 7 else 4]
               for i in range(8)]

    cells = [[CellType.WALL] * C for _ in range(R)]
    mist: set = set()
    for r in range(1, 8):                          # the shelf band
        for c in range(*_SHR_BAND):
            cells[r][c] = CellType.FLOOR
            mist.add((r, c))
    for c in range(_SHR_TX, _SHR_BAND[1] + 1):     # the water course (sight-line;
        cells[_SHR_WTR][c] = CellType.WATER        # cols west stay WALL so the
        mist.add((_SHR_WTR, c))                    # 8th plaque line sits in stone)
    for c in range(_SHR_TX - 1, _SHR_SEAL_COL):
        cells[_SHR_GAL][c] = CellType.FLOOR        # the reading gallery (west of
    for c in range(_SHR_SEAL_COL + 1, _SHR_EXIT_COL + 1):    # the band is stone —
        cells[_SHR_GAL][c] = CellType.FLOOR        # nothing to walk there)
    # (_SHR_GAL, _SHR_SEAL_COL) stays WALL until _shelving_tick opens it.

    room = Room(room_type=RoomType.ENTRY, rows=R, cols=C)
    room.cells     = cells
    room.seed      = seed
    room.spawn_pos = (_SHR_GAL, _SHR_TX - 1)       # under the shelf's west edge
    room.exit_pos  = (_SHR_GAL, _SHR_EXIT_COL)
    room.char_runs = []

    def lay(r, col, text, kind):
        for wd in text.split(' '):
            room.char_runs.append(CharRun(r, col, tuple(wd), kind))
            col += len(wd) + 1

    for i, t in enumerate(targets):                # the plaque column (rows 1..8)
        lay(i + 1, _SHR_PLQ + _SHR_INDENTS[i], t.strip(), 'verdant')
    for r, (ti, ind) in enumerate(_SHR_INIT, start=1):   # the misshelved stanza
        lay(r, _SHR_TX + ind, lines[ti], 'ancient')

    room.entities = [
        Entity(kind='exit',         row=_SHR_GAL, col=_SHR_EXIT_COL),
        Entity(kind='chest_scroll', row=_SHR_GAL, col=_SHR_CHEST_COL),
    ]
    room._shr_targets = tuple(targets)
    room._shr_plaque  = tuple((_SHR_INDENTS[i], targets[i].strip())
                              for i in range(8))
    room._shr_seal_col = _SHR_SEAL_COL

    room.par    = _SHR_PAR
    room.budget = _SHR_BUDGET
    room.answer = ':set␣nu⏎ :2m4⏎ :5t7⏎ :3<⏎ :6>⏎ $'

    room.rebuild_indexes()
    pocket = {(_SHR_GAL, c) for c in range(_SHR_SEAL_COL + 1, _SHR_EXIT_COL + 1)}
    room.fog_cells  = set(mist) | pocket
    room.mist_cells = set(mist)
    dungeon.rooms        = [room]
    dungeon.current_room = 0
    return dungeon
