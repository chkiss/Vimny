"""Assemble a dungeon from rooms joined by corridors into a single grid."""
from __future__ import annotations
import heapq, math, os, random, unicodedata
from collections import deque
from engine.world import Dungeon, Room, RoomType, CellType, RuneCluster, Entity
from engine.motion import _fog_unreachable, _cell_char
from generation.room_gen import make_room

_DIR_CHAR = {(-1, 0): 'k', (1, 0): 'j', (0, -1): 'h', (0, 1): 'l'}


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

# Level 0: Entry → Puzzle → Exit  (hjkl only)
LEVEL_0_PLAN = [
    (RoomType.ENTRY,  10, 18),
    (RoomType.PUZZLE, 10, 20),
    (RoomType.EXIT,   10, 16),
]

_RUNE_KINDS      = ['ancient', 'verdant', 'void', 'ember']
_WORD_RUNE_KINDS = ['ancient', 'verdant', 'ember']   # non-void only
_RUNE_CHAR = {
    'ancient': '∘',
    'verdant': '·',
    'void':    '○',
    'ember':   '⊙',
}

def _make_rune_syms(rng, kind: str) -> tuple:
    max_len = 2 if kind == 'void' else 7
    min_len = 1 if kind == 'verdant' else 2
    ch = _RUNE_CHAR[kind]
    return tuple(ch for _ in range(rng.randint(min_len,max_len)))

# ── Level 3 layout constants ──────────────────────────────────────────────────
_L3_CORR_TOP_ROWS = (1, 4, 7, 10, 13)  # top row of each of the 5 corridors
_L3_TOTAL_ROWS    = 16                  # rows 0-15
_L3_TOTAL_COLS    = 48                  # cols 0-47
_L3_CORR_LEFT     = 1
_L3_CORR_RIGHT    = 46

# ── Level 4 layout constants ──────────────────────────────────────────────────
_L4_CORR_TOP_ROWS = (1, 4, 7, 10, 13)
_L4_TOTAL_ROWS    = 16
_L4_TOTAL_COLS    = 72
_L4_CORR_LEFT     = 1
_L4_CORR_RIGHT    = 70

_L4_TURN_SPANS = [
    (2,  4,  69, 69),   # RT1: right side, single col, C1→C2
    (5,  7,   1,  2),   # LT1: left side,  C2→C3
    (8,  10, 69, 70),   # RT2: right side, C3→C4
    (11, 13,  1,  2),   # LT2: left side,  C4→C5
]

# Water pools per corridor: (row_tuple, col_start, col_end)
_L4_WATER_SPANS = [
    ((1, 2),            14, 37),   # C1: Zone A cols 1-13, text cols 38-69
    ((4, 5),            30, 51),   # C2: text cols 3-29, Zone B cols 52-69
    ((4, 5, 6, 7),       1,  1),   # Left-edge strip: C2-C3 via LT1 col 2 only
    ((7, 8),            18, 31),   # C3: Zone A cols 1-17, Zone B cols 32-70
    ((10, 11),          26, 51),   # C4: Zone B cols 52-70, dynamite at col 1
    ((1, 2, 3, 4, 5),   70, 70),   # Right-edge strip (narrows RT1 to col 69)
]

# Visible text strings placed as RuneCluster symbols — f/F/t/T targets
_L4_TEXT_C1  = "Most files you encounter"             # 'r' at offset 23 → col 67
_L4_TEXT_C2  = " will be scribed in letters"             # 'w' at offset 1 → col 4
_L4_TEXT_C3A = "so you can jump"                         # Zone A (cols 2-16)
_L4_TEXT_C3B = "quite easily to anything you can type"  # t! lands at col 69 before dynamite at 70

def _place_runes_in_room(composite, rng, col_offset, room_rows, room_cols,
                          total_rows, density):
    """Scatter rune clusters inside one room of the composite grid."""
    row_offset = (total_rows - room_rows) // 2
    col_end = col_offset + room_cols - 2
    for r in range(row_offset + 1, row_offset + room_rows - 1):
        c = col_offset + 2
        while c < col_end:
            if rng.random() < density:
                kind = rng.choice(_RUNE_KINDS)
                placed = False
                for _ in range(2):  # one retry for long runes at end
                    syms = _make_rune_syms(rng, kind)
                    width = len(syms)
                    if c + width <= col_end:
                        composite.runes.append(
                            RuneCluster(row=r, col=c, symbols=syms, kind=kind))
                        c += width + rng.randint(1, 3)
                        placed = True
                        break
                if placed:
                    continue
            c += 1


def _bfs_par(composite, return_path: bool = False):
    """Shortest path entry→exit treating void rune cells as impassable.
    Returns cost, or (cost, path_str) when return_path=True."""
    void_cells = {
        (ru.row, ru.col + i)
        for ru in composite.runes if ru.kind == 'void'
        for i in range(len(ru.symbols))
    }
    entry = composite.spawn_pos
    goal  = composite.exit_pos
    dist  = {entry: 0}
    prev  = {entry: None}
    q     = deque([entry])
    while q:
        r, c = q.popleft()
        if (r, c) == goal:
            if return_path:
                return dist[goal], _join_path(prev, goal, merge_single=False)
            return dist[goal]
        for dr, dc in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            nb = (r + dr, c + dc)
            if nb not in dist and composite.is_passable(*nb) and nb not in void_cells:
                dist[nb] = dist[(r, c)] + 1
                prev[nb] = ((r, c), _DIR_CHAR[(dr, dc)])
                q.append(nb)
    if return_path:
        return None, ''
    return None

# Level 2: Entry → Puzzle → Exit  ([count] prefix with hjkl + ^$0)
LEVEL_2_PLAN = [
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

    dist = {entry: 0}
    heap = [(0, entry)]

    while heap:
        cost, (r, c) = heapq.heappop(heap)
        if (r, c) == goal:
            return cost
        if cost > dist.get((r, c), float('inf')):
            continue
        for dr, dc in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            for n in range(1, max_n + 1):
                nr, nc = r + dr * n, c + dc * n
                if not composite.is_passable(nr, nc):
                    break  # wall stops this and all larger counts
                move_cost = 1 if n == 1 else len(str(n)) + 1
                new_cost  = cost + move_cost
                if new_cost < dist.get((nr, nc), float('inf')):
                    dist[(nr, nc)] = new_cost
                    heapq.heappush(heap, (new_cost, (nr, nc)))
    return None


def _dijkstra_par_level2(composite, door_cols: list, return_path: bool = False):
    """Full state-space Dijkstra for Level 2.

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

    start = (entry[0], entry[1], all_closed)
    dist  = {start: 0}
    prev  = {start: None}
    heap  = [(0, start)]

    while heap:
        cost, (r, c, closed) = heapq.heappop(heap)
        if (r, c) == goal:
            if return_path:
                return cost, _join_path(prev, (r, c, closed), merge_single=False)
            return cost
        if cost > dist.get((r, c, closed), float('inf')):
            continue

        def push(nr, nc, nc2, mc, lbl=''):
            ns = (nr, nc, nc2)
            g  = cost + mc
            if g < dist.get(ns, float('inf')):
                dist[ns] = g
                prev[ns] = ((r, c, closed), lbl)
                heapq.heappush(heap, (g, ns))

        # count h/j/k/l — stop at wall or fog
        for dr, dc in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            ch = _DIR_CHAR[(dr, dc)]
            for step in range(1, max_n + 1):
                nr, nc = r + dr * step, c + dc * step
                if not composite.is_passable(nr, nc) or fog_blocks_col(nc, closed):
                    break
                mc  = 1 if step == 1 else len(str(step)) + 1
                lbl = ch if step == 1 else f'{step}{ch}'
                push(nr, nc, closed, mc, lbl)

        # $ — rightward to nearest wall/fog
        best = None
        for nc in range(c + 1, composite.cols):
            if not composite.is_passable(r, nc) or fog_blocks_col(nc, closed):
                break
            best = nc
        if best is not None:
            push(r, best, closed, 1, '$')

        # 0 — leftward to nearest wall
        left = c
        for nc in range(c - 1, -1, -1):
            if not composite.is_passable(r, nc):
                break
            left = nc
        if left != c:
            push(r, left, closed, 1, '0')

        # ^ — leftmost rune in wall/fog-bounded segment
        lb = c
        for nc in range(c - 1, -1, -1):
            if not composite.is_passable(r, nc):
                break
            lb = nc
        rb = c
        for nc in range(c + 1, composite.cols):
            if not composite.is_passable(r, nc) or fog_blocks_col(nc, closed):
                break
            rb = nc
        tgt = lb
        for nc in range(lb, rb + 1):
            if composite.rune_at(r, nc):
                tgt = nc
                break
        if tgt != c:
            push(r, tgt, closed, 1, '^')

        # x — open door at current cell (player stays put)
        for i in range(n):
            if (closed >> i) & 1 and (r, c) in trigger[i]:
                push(r, c, closed ^ (1 << i), 1, 'x')

    if return_path:
        return None, ''
    return None


def build_dungeon_0(seed: int) -> Dungeon:
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
        _, rows_l, cols_l = plan[i]
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

    # Place rune clusters in all three rooms — no safe rows, runes can appear
    # anywhere including rows 4-5 (the corridor band).  Par is computed by BFS
    # after placement.  If the runes block every path, retry with a new sub-seed
    # (up to 20 attempts).
    densities = {0: 0.20, 1: 0.28, 2: 0.20}
    for attempt in range(20):
        composite.runes.clear()
        rune_rng = random.Random(rng.randint(0, 2**31))
        for i, (_, room_rows, room_cols) in enumerate(plan):
            _place_runes_in_room(composite, rune_rng, offsets[i],
                                 room_rows, room_cols, total_rows, densities[i])

        # Hard-coded void guards: block (2, ex_c) and (3, ex_c) so the player
        # cannot walk straight up from the corridor to the exit.  They must go
        # right into Room 2, up to row 1, then press h to reach the exit.
        # Remove any random rune that would shadow these hard-coded voids.
        for void_row in (2, 3):
            composite.runes = [
                ru for ru in composite.runes
                if not (ru.row == void_row
                        and ru.col <= ex_c < ru.col + len(ru.symbols))
            ]
        composite.runes.append(RuneCluster(row=2, col=ex_c, symbols=('○',), kind='void'))
        composite.runes.append(RuneCluster(row=3, col=ex_c, symbols=('○',), kind='void'))

        # Never leave a void rune sitting on the entry or exit itself.
        entry_r, entry_c = composite.spawn_pos
        exit_r,  exit_c  = composite.exit_pos
        composite.runes = [
            ru for ru in composite.runes
            if ru.kind != 'void' or not any(
                (ru.row == r and ru.col <= c < ru.col + len(ru.symbols))
                for r, c in ((entry_r, entry_c), (exit_r, exit_c))
            )
        ]

        par, path = _bfs_par(composite, return_path=True)
        if par is not None:
            break
    else:
        par, path = 100, ''

    # Budget: ceil(par × 1.4) per spec formula.
    composite.par    = par
    composite.budget = math.ceil(par * 1.4)
    composite.answer = path

    composite.rebuild_indexes()
    dungeon.rooms = [composite]
    dungeon.current_room = 0
    return dungeon


# Level 1: Entry → Puzzle → Exit  (hjkl + ^ $ 0  + :w :q)
LEVEL_1_PLAN = [
    (RoomType.ENTRY,  8, 14),
    (RoomType.PUZZLE, 8, 60),
    (RoomType.EXIT,   10, 14),
]


def _bfs_par_line(composite, return_path: bool = False):
    """BFS par for Level 1: hjkl + $ ^ 0 line-end motions (each costs 1).

    $ and ^ are wall-bounded: they stop at the nearest wall in each direction,
    matching apply_motion semantics.  Targets are precomputed per (row, col).
    """
    entry = composite.spawn_pos
    goal  = composite.exit_pos

    rune_cols_by_row: dict[int, list[int]] = {}
    for ru in composite.runes:
        if ru.kind == 'void':
            continue
        for i in range(len(ru.symbols)):
            rune_cols_by_row.setdefault(ru.row, []).append(ru.col + i)

    # Per-cell targets: split each row into contiguous passable segments at walls.
    dollar_of: dict[tuple, tuple] = {}
    zero_of:   dict[tuple, tuple] = {}
    hat_of:    dict[tuple, tuple] = {}

    for r in range(composite.rows):
        segments: list[tuple[int, int]] = []
        seg_start = None
        for c in range(composite.cols):
            if composite.is_passable(r, c):
                if seg_start is None:
                    seg_start = c
            else:
                if seg_start is not None:
                    segments.append((seg_start, c - 1))
                    seg_start = None
        if seg_start is not None:
            segments.append((seg_start, composite.cols - 1))

        rcols = sorted(rune_cols_by_row.get(r, []))
        for seg_l, seg_r in segments:
            runes = [rc for rc in rcols if seg_l <= rc <= seg_r]
            hat_dest = (r, runes[0]) if runes else (r, seg_l)
            for c in range(seg_l, seg_r + 1):
                dollar_of[(r, c)] = (r, seg_r)
                zero_of[(r, c)]   = (r, seg_l)
                hat_of[(r, c)]    = hat_dest

    dist = {entry: 0}
    prev = {entry: None}
    q    = deque([entry])
    while q:
        r, c = q.popleft()
        if (r, c) == goal:
            if return_path:
                return dist[goal], _join_path(prev, goal, merge_single=False)
            return dist[goal]
        d = dist[(r, c)]
        for dr, dc in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            nb = (r + dr, c + dc)
            if nb not in dist and composite.is_passable(*nb):
                dist[nb] = d + 1
                prev[nb] = ((r, c), _DIR_CHAR[(dr, dc)])
                q.append(nb)
        for nb, lbl in ((dollar_of.get((r, c)), '$'),
                        (zero_of.get((r, c)),   '0'),
                        (hat_of.get((r, c)),    '^')):
            if nb is not None and nb != (r, c) and nb not in dist:
                dist[nb] = d + 1
                prev[nb] = ((r, c), lbl)
                q.append(nb)
    if return_path:
        return None, ''
    return None


def build_dungeon_1(seed: int) -> Dungeon:
    """The Line Halls — teaches ^ $ 0 + :w :q.

    ENTRY(8×14) ─4─ PUZZLE(8×60) ─4─ EXIT(10×14)  →  96 × 10 composite.

    EXIT is full-height (10 rows); ENTRY/PUZZLE are 8 rows centred at rows 1-8.
    Global rows 0 and 9 exist only inside EXIT, so `^` on row 1 finds the exit
    at (1, 83) with no competing runes from other rooms.

    Optimal path (≈7 keys): jj → $ → kkk → ^ .  hjkl-only cost ≫ budget.
    """
    rng = random.Random(seed)
    dungeon = Dungeon(name='The Line Halls', seed=seed)
    CORRIDOR_LEN = 4

    plan      = LEVEL_1_PLAN
    total_cols = sum(c for _, _, c in plan) + CORRIDOR_LEN * (len(plan) - 1)
    total_rows = max(r for _, r, _ in plan)  # 10

    cells = [[CellType.WALL] * total_cols for _ in range(total_rows)]

    col_offset = 0
    offsets    = []
    for room_type, rows, cols in plan:
        offsets.append(col_offset)
        r_seed = rng.randint(0, 2**31)
        room   = make_room(room_type, rows, cols, r_seed)
        for r in range(rows):
            for c in range(cols):
                gr = r + (total_rows - rows) // 2
                gc = c + col_offset
                cells[gr][gc] = room.cells[r][c]
        col_offset += cols + CORRIDOR_LEN

    # Carve corridors at rows 4-5 (mid = total_rows // 2 = 5)
    for i in range(len(plan) - 1):
        _, rows_l, cols_l = plan[i]
        left_right_edge  = offsets[i] + cols_l - 1
        right_left_edge  = offsets[i + 1]
        mid = total_rows // 2
        for c in range(left_right_edge, right_left_edge + 1):
            cells[mid][c]     = CellType.CORRIDOR
            cells[mid - 1][c] = CellType.CORRIDOR

    composite = Room(room_type=RoomType.ENTRY, rows=total_rows, cols=total_cols)
    composite.cells = cells
    composite.seed  = seed

    # Entry above corridor rows — player must use j to reach the corridor.
    composite.spawn_pos = (2, 2)

    # Exit at leftmost interior cell of EXIT room on row 1 (EXIT-only row).
    # offsets[-1]=82; interior starts at col 83.  Row 1 is above corridor
    # rows 4-5, so on row 1 only EXIT interior (cols 83-94) is passable.
    # ^ on row 1 therefore lands at col 83 (first passable = first rune).
    ex_c = offsets[-1] + 1   # 83
    ex_r = 1
    composite.exit_pos = (ex_r, ex_c)
    composite.entities.append(Entity(kind='exit', row=ex_r, col=ex_c))

    # Scatter decorative runes; strip void runes and row-1 runes so the only
    # rune on the exit row is the hardcoded anchor that ^ will land on.
    for _attempt in range(20):
        composite.runes.clear()
        rune_rng = random.Random(rng.randint(0, 2**31))
        for i, (_, room_rows, room_cols) in enumerate(plan):
            _place_runes_in_room(composite, rune_rng, offsets[i],
                                 room_rows, room_cols, total_rows, 0.15)
        composite.runes = [
            ru for ru in composite.runes
            if ru.kind != 'void' and ru.row != ex_r
        ]
        # Anchor rune at exit position so ^ on row 1 lands exactly on the exit.
        composite.runes.append(
            RuneCluster(row=ex_r, col=ex_c, symbols=('∘',), kind='ancient'))
        par, path = _bfs_par_line(composite, return_path=True)
        if par is not None:
            break
    else:
        par, path = 7, ''

    composite.par    = par
    composite.budget = math.ceil(par * 1.4)
    composite.answer = path
    composite.rebuild_indexes()
    dungeon.rooms    = [composite]
    dungeon.current_room = 0
    return dungeon


def build_dungeon_2(seed: int) -> Dungeon:
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

    plan = LEVEL_2_PLAN
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
        _, rows_l, cols_l = plan[i]
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
        RuneCluster(row=row, col=puzzle_mid_col, symbols=('○',), kind='void')
        for row in range(2, total_rows - 2)          # rows 2-9
    ]

    # Decorative runes in entry and exit rooms; retry if any void blocks path.
    for attempt in range(20):
        composite.runes = list(void_wall)
        rune_rng = random.Random(rng.randint(0, 2**31))
        _place_runes_in_room(composite, rune_rng, offsets[0],
                              plan[0][1], plan[0][2], total_rows, 0.18)
        _place_runes_in_room(composite, rune_rng, offsets[2],
                              plan[2][1], plan[2][2], total_rows, 0.18)

        # Never place a void rune on the entry or exit cell itself
        entry_r, entry_c = composite.spawn_pos
        exit_r,  exit_c  = composite.exit_pos
        composite.runes = [
            ru for ru in composite.runes
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

    # Full par: state-space Dijkstra with all Level 2 commands and door states.
    # Accounts for door-blocking (breaking $ into segments) and x keystrokes.
    composite.rebuild_indexes()
    composite.par, composite.answer = _dijkstra_par_level2(composite, door_cols, return_path=True)
    composite.budget = math.ceil(composite.par * 1.4)

    _fog_unreachable(composite, composite.spawn_pos[0], composite.spawn_pos[1])

    dungeon.rooms    = [composite]
    dungeon.current_room = 0
    return dungeon


# ── Level 3 helpers ───────────────────────────────────────────────────────────

def _make_rune_corridor(composite, rng, row_top,
                        col_start=None, col_end=None, density=0.65,
                        blocked: frozenset = frozenset()):
    """Carve a 2-row CORRIDOR strip and fill it densely with non-void rune clusters.

    Leaves a 1-cell buffer at each end so runes reach the turn-room entrance.
    blocked: set of (row, col) cells that random runes must not overlap or
    touch (1-cell side buffer enforced by the caller via the set contents).
    """
    if col_start is None:
        col_start = _L3_CORR_LEFT
    if col_end is None:
        col_end = _L3_CORR_RIGHT

    for c in range(col_start, col_end + 1):
        composite.cells[row_top][c]     = CellType.CORRIDOR
        composite.cells[row_top + 1][c] = CellType.CORRIDOR

    for row in (row_top, row_top + 1):
        c = col_start + 1
        while c <= col_end - 1:
            if rng.random() < density:
                kind  = rng.choice(_WORD_RUNE_KINDS)
                placed = False
                for _ in range(2):  # one retry for long runes at end
                    syms  = _make_rune_syms(rng, kind)
                    width = len(syms)
                    if c + width - 1 <= col_end:
                        if not any((row, cc) in blocked
                                   for cc in range(c - 1, c + width + 1)):
                            composite.runes.append(
                                RuneCluster(row=row, col=c, symbols=syms, kind=kind))
                            c += width + rng.randint(1, 2)
                            placed = True
                            break
                if placed:
                    continue
            c += 1


def _dijkstra_par_wbe(composite, return_path: bool = False):
    """Minimum-keystroke Dijkstra for Level 3: hjkl + w b e + count-hjkl.

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
    for ru in composite.runes:
        if ru.kind != 'void':
            clusters_by_row[ru.row].append(ru)
    for cls in clusters_by_row.values():
        cls.sort(key=lambda ru: ru.col)

    def _word_at(r, c):
        ru = composite.rune_at(r, c)
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

    dist = {entry: 0}
    prev = {entry: None}
    heap = [(0, entry)]

    while heap:
        cost, (r, c) = heapq.heappop(heap)
        if (r, c) == goal:
            if return_path:
                return cost, _join_path(prev, (r, c), merge_single=False)
            return cost
        if cost > dist.get((r, c), float('inf')):
            continue

        def _push(nb, mc=1, lbl=''):
            if nb is None:
                return
            nr, nc = nb
            if not composite.is_passable(nr, nc):
                return
            ru = composite.rune_at(nr, nc)
            if ru and ru.kind == 'void':
                return
            g = cost + mc
            if g < dist.get((nr, nc), float('inf')):
                dist[(nr, nc)] = g
                prev[(nr, nc)] = ((r, c), lbl)
                heapq.heappush(heap, (g, (nr, nc)))

        # count h/j/k/l — void blocks landing but count can bypass (engine behaviour)
        for dr, dc in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            ch = _DIR_CHAR[(dr, dc)]
            for n in range(1, max_n + 1):
                nr, nc = r + dr * n, c + dc * n
                if not composite.is_passable(nr, nc):
                    break
                ru = composite.rune_at(nr, nc)
                if ru and ru.kind == 'void':
                    continue  # can't land here; larger n can bypass
                mc  = 1 if n == 1 else len(str(n)) + 1
                lbl = ch if n == 1 else f'{n}{ch}'
                _push((nr, nc), mc, lbl)

        # count-w/b/e: chain calls to model Nw, Nb, Ne
        pos = (r, c)
        for n in range(1, max_n):
            nxt = _w(*pos)
            if nxt is None:
                break
            mc  = 1 if n == 1 else len(str(n)) + 1
            _push(nxt, mc, 'w' if n == 1 else f'{n}w')
            pos = nxt

        pos = (r, c)
        for n in range(1, max_n):
            nxt = _b(*pos)
            if nxt is None:
                break
            mc  = 1 if n == 1 else len(str(n)) + 1
            _push(nxt, mc, 'b' if n == 1 else f'{n}b')
            pos = nxt

        pos = (r, c)
        for n in range(1, max_n):
            nxt = _e(*pos)
            if nxt is None:
                break
            mc  = 1 if n == 1 else len(str(n)) + 1
            _push(nxt, mc, 'e' if n == 1 else f'{n}e')
            pos = nxt

    if return_path:
        return None, ''
    return None


def _l4_place_zone(composite, rng, rows, col_start, col_end,
                   density=0.55, blocked=frozenset()):
    """Fill a rune zone across the given rows between col_start and col_end."""
    for r in rows:
        c = col_start
        while c <= col_end:
            if rng.random() < density:
                kind = rng.choice(('ancient', 'verdant'))
                syms = _make_rune_syms(rng, kind)
                w    = len(syms)
                if c + w - 1 <= col_end:
                    if not any((r, cc) in blocked
                               for cc in range(c - 1, c + w + 1)):
                        composite.runes.append(
                            RuneCluster(row=r, col=c, symbols=syms, kind=kind))
                        c += w + rng.randint(1, 2)
                        continue
            c += 1


def _dijkstra_par_ftFT(composite, return_path: bool = False):
    """Minimum-keystroke Dijkstra for Level 4: hjkl + count + w b e + f F t T.

    f/F/t/T scan includes text-rune chars ('r','w','!') and entity chars
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

    # Include text chars that appear as rune symbols alongside entity chars.
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
    for ru in composite.runes:
        if ru.kind != 'void':
            clusters_by_row[ru.row].append(ru)
    for cls in clusters_by_row.values():
        cls.sort(key=lambda ru: ru.col)

    def _word_at(r, c):
        ru = composite.rune_at(r, c)
        return ru if (ru and ru.kind != 'void') else None

    def _w(r, c):
        cur  = _word_at(r, c)
        scan = (cur.col + len(cur.symbols)) if cur else c + 1
        for nc in range(scan, COLS):
            if not _is_passable(r, nc):
                return None  # water or wall stops w
            ru = composite.rune_at(r, nc)
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
            ru = composite.rune_at(r, nc)
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
            ru = composite.rune_at(r, nc)
            if ru and ru.kind != 'void':
                end = ru.col + len(ru.symbols) - 1
                return (r, end) if _is_passable(r, end) else None
        return None

    dist = {entry: 0}
    prev = {entry: None}
    heap = [(0, entry)]

    while heap:
        cost, (r, c) = heapq.heappop(heap)
        if (r, c) == goal:
            if return_path:
                return cost, _join_path(prev, (r, c), merge_single=False)
            return cost
        if cost > dist.get((r, c), float('inf')):
            continue

        def _push(nb, mc=1, lbl=''):
            if nb is None:
                return
            nr, nc = nb
            if not _is_passable(nr, nc):
                return
            if (nr, nc) in _dynamite_cells:
                return
            ru = composite.rune_at(nr, nc)
            if ru and ru.kind == 'void':
                return
            g = cost + mc
            if g < dist.get((nr, nc), float('inf')):
                dist[(nr, nc)] = g
                prev[(nr, nc)] = ((r, c), lbl)
                heapq.heappush(heap, (g, (nr, nc)))

        # count h/j/k/l
        for dr, dc in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            ch = _DIR_CHAR[(dr, dc)]
            for n in range(1, max_n + 1):
                nr, nc = r + dr * n, c + dc * n
                if not _is_passable(nr, nc):
                    break
                ru = composite.rune_at(nr, nc)
                if ru and ru.kind == 'void':
                    continue
                if (nr, nc) in _dynamite_cells:
                    continue
                mc  = 1 if n == 1 else len(str(n)) + 1
                lbl = ch if n == 1 else f'{n}{ch}'
                _push((nr, nc), mc, lbl)

        # w / b / e (stop at water)
        pos = (r, c)
        for n in range(1, max_n):
            nxt = _w(*pos)
            if nxt is None:
                break
            mc = 1 if n == 1 else len(str(n)) + 1
            _push(nxt, mc, 'w' if n == 1 else f'{n}w')
            pos = nxt

        pos = (r, c)
        for n in range(1, max_n):
            nxt = _b(*pos)
            if nxt is None:
                break
            mc = 1 if n == 1 else len(str(n)) + 1
            _push(nxt, mc, 'b' if n == 1 else f'{n}b')
            pos = nxt

        pos = (r, c)
        for n in range(1, max_n):
            nxt = _e(*pos)
            if nxt is None:
                break
            mc = 1 if n == 1 else len(str(n)) + 1
            _push(nxt, mc, 'e' if n == 1 else f'{n}e')
            pos = nxt

        # f / F / t / T — row-scoped, water-transparent, wall-stopped
        pts      = row_chars[r]
        wall_fwd = next((nc for nc in range(c + 1, COLS) if _scan_stops(r, nc)), COLS)
        wall_bwd = next((nc for nc in range(c - 1, -1, -1) if _scan_stops(r, nc)), -1)

        for nc, ch in pts:
            if nc > c and nc < wall_fwd:
                if _is_passable(r, nc):
                    _push((r, nc), 2, f'f{ch}')   # f + target char = 2 keys
                if nc - 1 != c and _is_passable(r, nc - 1):
                    _push((r, nc - 1), 2, f't{ch}')
            elif nc < c and nc > wall_bwd:
                if _is_passable(r, nc):
                    _push((r, nc), 2, f'F{ch}')
                if nc + 1 != c and _is_passable(r, nc + 1):
                    _push((r, nc + 1), 2, f'T{ch}')

    if return_path:
        return None, ''
    return None


def build_dungeon_3(seed: int) -> Dungeon:
    """The Rune Halls — teaches w b e (word motions over rune clusters).

    Five 2-row rune corridors in a snake pattern:
      C1 rows 1-2   left→right  (w efficient)
      C2 rows 4-5   right→left  (b efficient)
      C3 rows 7-8   left→right
      C4 rows 10-11 right→left
      C5 rows 13-14 left→right  (exit = last symbol of anchor rune → use e)

    Turn rooms bridge adjacent corridors at alternating ends:
      RT1 rows 2-4   cols 45-46  (void at middle row 3)
      LT1 rows 5-7   cols 1-2   (void at middle row 6)
      RT2 rows 8-10  cols 45-46  (void at middle row 9)
      LT2 rows 11-13 cols 1-2   (void at middle row 12)

    Rune clusters fill each corridor from col 2 to col 45 (1-cell margin).
    Void clusters at each turn-room middle row block straight j/k traversal,
    forcing count-j to skip them — reinforcing the level-2 count motion.
    """
    rng     = random.Random(seed)
    dungeon = Dungeon(name='The Rune Halls', seed=seed)

    cells = [[CellType.WALL] * _L3_TOTAL_COLS for _ in range(_L3_TOTAL_ROWS)]

    composite = Room(room_type=RoomType.ENTRY,
                     rows=_L3_TOTAL_ROWS, cols=_L3_TOTAL_COLS)
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

    # ── Hard-coded runes (deterministic; placed before random fill) ───────────
    # All positions are fixed regardless of seed.  Placing them first in the
    # runes list guarantees rune_at() returns them before any random cluster.
    _l3_hardcoded = [
        # Anchor rune at C5 exit — last symbol (col 44) is the exit cell
        RuneCluster(row=13, col=42, symbols=('∘', '∘', '∘'), kind='ancient'),
        # Ember at right end of C1 — marks the turn into RT1
        RuneCluster(row=1,  col=44, symbols=('◦', '◦', '◦'), kind='ember'),
        # Void guards at turn-room entries/exits
        RuneCluster(row=1,  col=45, symbols=('○', '○'), kind='void'),
        RuneCluster(row=2,  col=45, symbols=('○', '○'), kind='void'),
        RuneCluster(row=4,  col=1,  symbols=('○', '○'), kind='void'),
        RuneCluster(row=5,  col=1,  symbols=('○',),     kind='void'),
        RuneCluster(row=7,  col=46, symbols=('○',),     kind='void'),
        RuneCluster(row=8,  col=45, symbols=('○', '○'), kind='void'),
        RuneCluster(row=10, col=1,  symbols=('○',),     kind='void'),
        RuneCluster(row=10, col=2,  symbols=('·','·','·','·'),     kind='verdant'),
        RuneCluster(row=11, col=1,  symbols=('○', '○'), kind='void'),
        RuneCluster(row=13, col=46, symbols=('○',),     kind='void'),
        RuneCluster(row=14, col=46, symbols=('○',),     kind='void'),
    ]

    # Reserved cells: Random runes must not land in or touch these cells.
    blocked: frozenset = frozenset(
        (ru.row, c)
        for ru in _l3_hardcoded
        for c in range(ru.col, ru.col + len(ru.symbols))
    )

    composite.spawn_pos    = (1, 1)
    composite.exit_pos = (13, 44)
    composite.entities = [Entity(kind='exit', row=13, col=44)]

    # ── Carve and populate rune corridors (up to 20 attempts for valid par) ──
    for _attempt in range(20):
        # Hard-coded runes first so rune_at() always finds them before random ones
        composite.runes = list(_l3_hardcoded)
        rune_rng = random.Random(rng.randint(0, 2**31))

        for row_top in _L3_CORR_TOP_ROWS:
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


def build_dungeon_4(seed: int) -> Dungeon:
    """The Character Cataracts — teaches f F t T (character search over water pools).

    Five 2-row snake corridors (72 cols wide).  Each corridor has a water pool
    that blocks hjkl/w/b/e but is transparent to f/F/t/T.  Visible text
    strings on the floor tiles are the jump targets:

      C1 rows 1-2   left→right  fr  "    Most dungeons you traverse" → r at col 61
      C2 rows 4-5   right→left  Fw  " will be scribed in letters"    → w at col 4
      C3 rows 7-8   left→right  t!  "so you can jump" + "quite easily…type" + dynamite at col 70
      C4 rows 10-11 right→left  T!  dynamite at col 1 (F! would explode)
      C5 rows 13-14 left→right  w/b/e rune navigation + exit
    """
    ROWS, COLS = _L4_TOTAL_ROWS, _L4_TOTAL_COLS
    rng     = random.Random(seed)
    dungeon = Dungeon(name='The Character Cataracts', seed=seed)

    cells = [[CellType.WALL] * COLS for _ in range(ROWS)]
    composite = Room(room_type=RoomType.ENTRY, rows=ROWS, cols=COLS)
    composite.cells = cells
    composite.seed  = seed

    # ── Carve corridors (2 rows each) ─────────────────────────────────────────
    for row_top in _L4_CORR_TOP_ROWS:
        for c in range(_L4_CORR_LEFT, _L4_CORR_RIGHT + 1):
            cells[row_top][c]     = CellType.CORRIDOR
            cells[row_top + 1][c] = CellType.CORRIDOR

    # ── Carve turn rooms ──────────────────────────────────────────────────────
    for r0, r1, ca, cb in _L4_TURN_SPANS:
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
    for rows, cs, ce in _L4_WATER_SPANS:
        for r in rows:
            for c in range(cs, ce + 1):
                cells[r][c] = CellType.WATER

    # ── Fixed text rune clusters (visible f/F/t/T targets) ───────────────────
    # Text chars are individual rune symbols; _cell_char returns each char so
    # f/F/t/T can find them.  kind='ember' gives a distinctive warm colour.
    # One row of text per corridor (the other row gets standard random runes).
    _text_runes = [
        # C1 row 1: fr jumps to 'r' at offset 23 → col 67
        RuneCluster(row=1, col=44, symbols=tuple(_L4_TEXT_C1), kind='ember'),
        # C2 row 5: Fw jumps backward to 'w' at offset 1 → col 4
        RuneCluster(row=5, col=3,  symbols=tuple(_L4_TEXT_C2), kind='ember'),
        # C3 row 7 Zone A: walking terrain before the water (cols 2-16)
        RuneCluster(row=7, col=2,  symbols=tuple(_L4_TEXT_C3A), kind='ember'),
        # C3 row 7 Zone B: t! lands at col 69 (before dynamite at col 70)
        RuneCluster(row=7, col=33, symbols=tuple(_L4_TEXT_C3B), kind='ember'),
        # C5 exit anchor: last symbol at col 65 so `e` lands on the exit
        RuneCluster(row=13, col=64, symbols=('◦', '◦'), kind='ember'),
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

    # ── Blocked cells: water + text/anchor runes + fixed entities ─────────────
    _bl: set = {(e.row, e.col) for e in _fixed}
    for rows, cs, ce in _L4_WATER_SPANS:
        for r in rows:
            for c in range(cs, ce + 1):
                _bl.add((r, c))
    for ru in _text_runes:
        for i in range(len(ru.symbols)):
            _bl.add((ru.row, ru.col + i))
    blocked = frozenset(_bl)

    for _attempt in range(20):
        composite.runes = list(_text_runes)
        rng2 = random.Random(rng.randint(0, 2**31))

        # Fill all corridor zones with standard runes
        _l4_place_zone(composite, rng2, (1, 2),    2,  13, blocked=blocked)  # C1 Zone A
        _l4_place_zone(composite, rng2, (1, 2),   38,  68, blocked=blocked)  # C1 Zone B
        _l4_place_zone(composite, rng2, (4,),      2,  28, blocked=blocked)  # C2 row 4 Zone A
        _l4_place_zone(composite, rng2, (4, 5),   52,  68, blocked=blocked)  # C2 Zone B
        _l4_place_zone(composite, rng2, (8,),      2,  16, blocked=blocked)  # C3 row 8 Zone A
        _l4_place_zone(composite, rng2, (8,),     32,  70, blocked=blocked)  # C3 row 8 Zone B
        _l4_place_zone(composite, rng2, (10, 11),  2,  24, blocked=blocked)  # C4 Zone A
        _l4_place_zone(composite, rng2, (10, 11), 52,  68, blocked=blocked)  # C4 Zone B
        # C5: dense rune corridor for w/b/e practice; chest at col 20, exit anchor at col 64-65
        _l4_place_zone(composite, rng2, (13, 14),  2,  63,
                        density=0.60, blocked=blocked)

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


def build_dungeon_1_1(seed: int) -> Dungeon:
    """The Reliquary — bonus chest room unlocked alongside level 2.

    Layout (5 rows × 17 cols):
      Entry room (interior 3r × 2c): rows 0-4, cols 0-3;  floor at rows 1-3, cols 1-2.
      Corridor   (1r × 8c):          row 2,   cols 3-12   (carves through both room walls).
      Dest room  (interior 3r × 3c): rows 0-4, cols 12-16; floor at rows 1-3, cols 13-15.

    Chest (scroll) at center of destination interior: (2, 14).
    Exit at top-right interior corner: (1, 15).
    Entry at top-left of entry interior: (1, 1).

    No par challenge (par=None).  Budget = 15.
    Intended path: j  $  h  x  k  l  (6 keystrokes).
    """
    dungeon = Dungeon(name='The Reliquary', seed=seed)
    ROWS, COLS = 5, 17

    cells = [[CellType.WALL] * COLS for _ in range(ROWS)]

    # Entry room interior: rows 1-3, cols 1-2
    for r in range(1, 4):
        for c in range(1, 3):
            cells[r][c] = CellType.FLOOR

    # Single-row corridor: row 2, cols 3-12 (carves entry right wall and dest left wall)
    for c in range(3, 13):
        cells[2][c] = CellType.CORRIDOR

    # Destination room interior: rows 1-3, cols 13-15
    for r in range(1, 4):
        for c in range(13, 16):
            cells[r][c] = CellType.FLOOR

    composite = Room(room_type=RoomType.ENTRY, rows=ROWS, cols=COLS)
    composite.cells = cells
    composite.seed  = seed

    composite.spawn_pos    = (1, 1)
    composite.exit_pos = (1, 15)

    composite.entities = [
        Entity(kind='chest_scroll', row=2, col=14),
        Entity(kind='exit',         row=1, col=15),
    ]

    composite.par    = None
    composite.budget = 15
    composite.answer = 'j $ h x k l'

    composite.rebuild_indexes()
    dungeon.rooms        = [composite]
    dungeon.current_room = 0
    return dungeon


def build_dungeon_dummy(seed: int) -> Dungeon:
    """Admin editing sandbox — all editable element types, plus two fog-walled rooms.

    Layout (rows 1-18):
      Main room   cols 1-41  — open area with all entity/cell/rune types
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
        # Room-divider door (fog boundary — opens into Room A)
        Entity(kind='door',         row=9,  col=42),
        Entity(kind='door',         row=10, col=42),
        # Room-divider locked door (fog boundary — opens into Room B)
        Entity(kind='locked_door',  row=9,  col=58),
        Entity(kind='locked_door',  row=10, col=58),
        # Exit at the far end of Room B
        Entity(kind='exit',         row=9,  col=70),
    ]

    composite.runes = [
        RuneCluster(row=2, col=3,  symbols=('∘',), kind='ancient'),
        RuneCluster(row=2, col=8,  symbols=('·',), kind='verdant'),
        RuneCluster(row=2, col=13, symbols=('○',), kind='void'),
        RuneCluster(row=2, col=17, symbols=('◦',), kind='ember'),
    ]

    composite.par            = None
    composite.budget         = 99999
    composite.passable_walls = False
    composite.rebuild_indexes()
    _fog_unreachable(composite, composite.spawn_pos[0], composite.spawn_pos[1])
    dungeon.rooms        = [composite]
    dungeon.current_room = 0
    return dungeon


# ── Level 5 helpers ────────────────────────────────────────────────────────────

_L5_ROWS = 20
_L5_COLS = 58

# Snake corridor rows (single-row each)
_L5_CORR_ROWS    = [1, 3, 5, 7, 9, 11, 13, 15]
_L5_RIGHT_GOING  = {1, 5, 9, 13}   # player enters from left
_L5_LEFT_GOING   = {3, 7, 11, 15}  # player enters from right

# Right connector rows (floor at cols 55-56); left connector rows (floor at cols 2-3)
_L5_RIGHT_CONN_ROWS = [2, 6, 10, 14]
_L5_LEFT_CONN_ROWS  = [4, 8, 12, 16]
_L5_RC_COLS = (55, 56)
_L5_LC_COLS = (2, 3)


def _l5_place_near_runes(runes: list, rng, row: int,
                          col_start: int, col_end: int, n: int,
                          word_tbl: dict) -> None:
    """Scatter n decorative (non-void) rune clusters on the near side."""
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
        word = rng.choice(word_tbl.get(length) or word_tbl[1])
        kind = rng.choice(kinds)
        runes.append(RuneCluster(row=row, col=c,
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



def _par_l5(corr_data: list, gobs_17: list) -> int:
    """Analytical par for Level 5.

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
    """Exact command sequence for the current Level 5 layout."""
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


def build_dungeon_5(seed: int) -> Dungeon:
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

    cells = [[CellType.WALL] * _L5_COLS for _ in range(_L5_ROWS)]

    # Carve corridor floors (single-row each)
    for row in _L5_CORR_ROWS:
        for c in range(1, 57):
            cells[row][c] = CellType.FLOOR

    # Final section: full floor cols 1-56
    for row in (17, 18):
        for c in range(1, 57):
            cells[row][c] = CellType.FLOOR

    # Right connector passages (cols 55-56)
    for row in _L5_RIGHT_CONN_ROWS:
        for c in _L5_RC_COLS:
            cells[row][c] = CellType.FLOOR

    # Left connector passages (cols 2-3)
    for row in _L5_LEFT_CONN_ROWS:
        for c in _L5_LC_COLS:
            cells[row][c] = CellType.FLOOR

    composite = Room(room_type=RoomType.ENTRY, rows=_L5_ROWS, cols=_L5_COLS)
    composite.cells    = cells
    composite.seed     = seed
    composite.spawn_pos    = (1, 1)
    composite.exit_pos = (18, 56)

    entities: list = [Entity(kind='entry_marker', row=1, col=1)]
    runes:    list = []
    corr_data      = []

    # Per-corridor randomisation
    for row in _L5_CORR_ROWS:
        right_going = row in _L5_RIGHT_GOING

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
            far_end   = _L5_RC_COLS[0] - 2
            gobs = _l5_goblin_positions(rng, far_start, far_end,
                                        right_to_left=False)
        else:
            far_start = _L5_LC_COLS[1] + 2
            far_end   = w_start - 2
            gobs = _l5_goblin_positions(rng, far_start, far_end,
                                        right_to_left=True)

        for gc in gobs:
            entities.append(Entity(kind='goblin', row=row, col=gc,
                                   hp=1, max_hp=1, ai='chase', ai_speed=2))

        # Decorative near-side runes (non-void)
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
    for row in _L5_RIGHT_CONN_ROWS:
        for c in _L5_RC_COLS:
            entities.append(Entity(kind='door', row=row, col=c))
    for row in _L5_LEFT_CONN_ROWS:
        for c in _L5_LC_COLS:
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
    composite.runes    = runes

    par = _par_l5(corr_data, gobs17)
    composite.par    = par
    composite.budget = math.ceil(par * 1.4)
    composite.answer = _answer_l5(corr_data, gobs17)

    composite.rebuild_indexes()
    _fog_unreachable(composite, composite.spawn_pos[0], composite.spawn_pos[1])

    dungeon.rooms        = [composite]
    dungeon.current_room = 0
    return dungeon


# ── Level 5.1 — The Warden's Keep ─────────────────────────────────────────────

_L51_ROWS = 7
_L51_COLS = 44

# Layout (7 × 44):
#   Row 0/6 : all wall
#   Row 3   : open floor 0-42  (entry 0, seal_door 16, Warden 27, boss_seal 38, exit 39)
#   Rows 1,5: floor 0-15, wall 16, floor 17-37, wall 38, floor 39-42
#   Rows 2,4: stone columns (wall at even cols 0-16), open floor 17-37, wall 38, floor 39-42


def _par_l51() -> int:
    """Simulated par for Level 5.1 (The Warden's Keep).

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


def build_dungeon_51(seed: int) -> Dungeon:
    ROWS, COLS = _L51_ROWS, _L51_COLS
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
        Entity(kind='boss_seal',       row=3, col=38),
        Entity(kind='exit',            row=3, col=39),
        Entity(kind='heart_container', row=2, col=41),
        Entity(kind='chest_scroll',    row=4, col=41),
    ]
    composite.rebuild_indexes()
    _fog_unreachable(composite, 3, 0)

    composite.par    = None
    composite.budget = math.ceil(_par_l51() * 1.4)

    dungeon = Dungeon(name="The Warden's Keep", seed=seed)
    dungeon.rooms        = [composite]
    dungeon.current_room = 0
    return dungeon


# ── Level 8 layout constants ──────────────────────────────────────────────────

_L7_TOTAL_ROWS    = 10
_L7_TOTAL_COLS    = 58
_L7_CORR_TOP_ROWS = (1, 4, 7)   # top row of each of the 3 corridors
_L7_CORR_LEFT     = 1
_L7_CORR_RIGHT    = 55

_L7_TURN_SPANS = [
    (2, 4, 53, 55),   # RT1: connects C1 to C2 (right side)
    (5, 7,  1,  3),   # LT1: connects C2 to C3 (left side)
]

# Untypable punctuation characters: f/F cannot target them (player can't type them).
# All have isalpha()=False so _is_word_char()=False — treated as punct by w/b/e.
# Drawn from Latin-1 Supplement, General Punctuation, Mathematical Operators, and
# Miscellaneous Technical blocks; chosen to be visually distinct from ASCII code chars.
_L7_UNTYPABLE_PUNCT = (
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
# Anchors (W4 at 1,53 and B1 at 4,3) are placed separately per-seed from _L7_UNTYPABLE_PUNCT.
_L7_CODE_GROUPS = [
    # C1 (rows 1-2, left→right): W teaching — `4W` from col 1 → col 53 in 2 keystrokes
    (1,  3, "result=func",         'ember'),   # W1 cols  3-13
    (1, 16, "(a,b)+val",           'ember'),   # W2 cols 16-24
    (1, 27, "x=y*2",               'ember'),   # W3 cols 27-31
    # W4 anchor at (1, 53-54): seed-varying untypable pair (see build_dungeon_7)
    # C2 (rows 4-5, right→left): B teaching — `4B` from col 53 → col 3 in 2 keystrokes
    # B1 anchor at (4, 3-4): seed-varying untypable pair (see build_dungeon_7)
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
    """Place text as adjacent single-char RuneClusters (WORD group for W/B/E teaching)."""
    for i, ch in enumerate(text):
        runes.append(RuneCluster(row=row, col=col_start + i, symbols=(ch,), kind=kind))


def _l7_fill_row(composite, rng, row, col_start, col_end,
                 density=0.40, blocked=frozenset(), word_tbl=None):
    """Fill one corridor row with spaced non-void rune clusters (w ≡ W here)."""
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
                    composite.runes.append(
                        RuneCluster(row=row, col=c, symbols=syms, kind=kind))
                    c += w + rng.randint(2, 3)   # 2-3 cell gap → w ≡ W
                    continue
        c += 1


def _dijkstra_par_WBE(composite, return_path=False):
    """Minimum-keystroke Dijkstra for Level 8: count hjkl + w b e + W B E.

    WORD = maximal contiguous cluster sequence (no floor gap between clusters).
    W: start of next WORD.  B: start of current (or prev) WORD.  E: end of WORD.
    """
    ROWS, COLS = composite.rows, composite.cols
    entry = composite.spawn_pos
    goal  = composite.exit_pos
    max_n = max(ROWS, COLS)

    def _rune(r, c):
        ru = composite.rune_at(r, c)
        return ru if (ru and ru.kind != 'void') else None

    def _ok(r, c):
        if not composite.is_passable(r, c):
            return False
        ru = composite.rune_at(r, c)
        return not (ru and ru.kind == 'void')

    # -- word/punct type helpers --
    # Matches engine/_is_word_char: alpha/digit/_ plus Unicode So (Symbol,Other).
    def _is_wc(ch):
        return ch.isalpha() or ch.isdigit() or ch == '_' or unicodedata.category(ch) == 'So'

    def _char_at(r, c):
        ru = composite.rune_at(r, c)
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

    dist = {entry: 0}
    prev = {entry: None}
    heap = [(0, entry)]

    while heap:
        cost, (r, c) = heapq.heappop(heap)
        if (r, c) == goal:
            if return_path:
                return cost, _join_path(prev, (r, c), merge_single=False)
            return cost
        if cost > dist.get((r, c), float('inf')):
            continue

        def _push(nb, mc=1, lbl=''):
            if nb is None:
                return
            nr, nc = nb
            if not _ok(nr, nc):
                return
            g = cost + mc
            if g < dist.get((nr, nc), float('inf')):
                dist[(nr, nc)] = g
                prev[(nr, nc)] = ((r, c), lbl)
                heapq.heappush(heap, (g, (nr, nc)))

        # count h/j/k/l
        for dr, dc in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            ch_d = _DIR_CHAR[(dr, dc)]
            for n in range(1, max_n + 1):
                nr2, nc2 = r + dr * n, c + dc * n
                if not _ok(nr2, nc2):
                    break
                mc2  = 1 if n == 1 else len(str(n)) + 1
                lbl2 = ch_d if n == 1 else f'{n}{ch_d}'
                _push((nr2, nc2), mc2, lbl2)

        # $: scan right via passability (void runes don't stop scan); skip if landing is void
        best = None
        for cc in range(c + 1, COLS):
            if not composite.is_passable(r, cc):
                break
            best = cc
        if best is not None and _ok(r, best):
            _push((r, best), 1, '$')

        # 0: scan left via passability; skip if landing is void
        leftmost = c
        for cc in range(c - 1, -1, -1):
            if not composite.is_passable(r, cc):
                break
            leftmost = cc
        if leftmost < c and _ok(r, leftmost):
            _push((r, leftmost), 1, '0')

        # ^: leftmost rune in passability-bounded range; void as first rune = lethal, don't push
        left_b = c
        for cc in range(c - 1, -1, -1):
            if not composite.is_passable(r, cc):
                break
            left_b = cc
        right_b = c
        for cc in range(c + 1, COLS):
            if not composite.is_passable(r, cc):
                break
            right_b = cc
        for cc in range(left_b, right_b + 1):
            ru2 = composite.rune_at(r, cc)
            if ru2:
                if _ok(r, cc):
                    _push((r, cc), 1, '^')
                break  # first rune (void or not) terminates search

        # chain w/b/e/W/B/E
        for fn, key in ((_w, 'w'), (_b, 'b'), (_e, 'e'),
                        (_W, 'W'), (_B, 'B'), (_E, 'E')):
            pos2 = (r, c)
            for n in range(1, max_n):
                nxt = fn(*pos2)
                if nxt is None:
                    break
                mc2  = 1 if n == 1 else len(str(n)) + 1
                lbl2 = key if n == 1 else f'{n}{key}'
                _push(nxt, mc2, lbl2)
                pos2 = nxt

    if return_path:
        return None, ''
    return None


# ── Rune-word tables (lazy-loaded from art/) ─────────────────────────────────
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


# ── Level 7 layout constants ──────────────────────────────────────────────────
_L8_TOTAL_ROWS = 14
_L8_TOTAL_COLS = 40
_L8_CORR_ROWS  = (1, 3, 5, 7, 9, 11)   # one row per corridor
_L8_CORR_LEFT  = 1
_L8_CORR_RIGHT = 38

_L8_TURN_SPANS = [
    (1,  3,  36, 38),  # RT1: C1→C2, right side
    (3,  5,   1,  3),  # LT1: C2→C3, left side
    (5,  7,  36, 38),  # RT2: C3→C4, right side
    (7,  9,   5,  6),  # LT2: C4→C5, ge-critical (only cols 5-6 passable in row 8)
    (9,  11, 37, 38),  # RT3: C5→C6, right side
    (11, 12, 19, 19),  # LT3: C6→exit, gE-critical (only col 19 passable in row 12)
]


def _dijkstra_par_L8(composite, return_path: bool = False):
    """Minimum-keystroke Dijkstra for Level 8 — The Backward Vaults:
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
        ru = composite.rune_at(r, c)
        return ru if (ru and ru.kind != 'void') else None

    def _ok(r, c):
        if not composite.is_passable(r, c):
            return False
        ru = composite.rune_at(r, c)
        return not (ru and ru.kind == 'void')

    # Matches engine/_is_word_char: alpha/digit/_ plus Unicode So (Symbol,Other).
    def _is_wc(ch):
        return ch.isalpha() or ch.isdigit() or ch == '_' or unicodedata.category(ch) == 'So'

    def _char_at(r, c):
        ru = composite.rune_at(r, c)
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
            ru = composite.rune_at(r, nc)
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
            ru = composite.rune_at(r, nc)
            if ru and ru.kind != 'void':
                end = ru.col + len(ru.symbols) - 1
                # extend right to find WORD end
                cc = end + 1
                while cc < COLS and composite.is_passable(r, cc):
                    r2 = composite.rune_at(r, cc)
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

    dist = {entry: 0}
    prev = {entry: None}
    heap = [(0, entry)]

    while heap:
        cost, (r, c) = heapq.heappop(heap)
        if (r, c) == goal:
            if return_path:
                return cost, _join_path(prev, (r, c), merge_single=False)
            return cost
        if cost > dist.get((r, c), float('inf')):
            continue

        def _push(nb, mc=1, lbl=''):
            if nb is None:
                return
            nr, nc = nb
            if not _ok(nr, nc):
                return
            g = cost + mc
            if g < dist.get((nr, nc), float('inf')):
                dist[(nr, nc)] = g
                prev[(nr, nc)] = ((r, c), lbl)
                heapq.heappush(heap, (g, (nr, nc)))

        # count j/k (vertical, step-by-step)
        for dr, key in ((1, 'j'), (-1, 'k')):
            for n in range(1, max_n + 1):
                nr2 = r + dr * n
                if nr2 < 0 or nr2 >= ROWS or not _ok(nr2, c):
                    break
                mc2  = 1 if n == 1 else len(str(n)) + 1
                lbl2 = key if n == 1 else f'{n}{key}'
                _push((nr2, c), mc2, lbl2)

        # count h/l (horizontal, step-by-step)
        for dc, key in ((1, 'l'), (-1, 'h')):
            for n in range(1, max_n + 1):
                nc2 = c + dc * n
                if nc2 < 0 or nc2 >= COLS or not _ok(r, nc2):
                    break
                mc2  = 1 if n == 1 else len(str(n)) + 1
                lbl2 = key if n == 1 else f'{n}{key}'
                _push((r, nc2), mc2, lbl2)

        # $: rightmost passable col in same row (skip void landing)
        best_col = None
        for cc in range(c + 1, COLS):
            if not composite.is_passable(r, cc):
                break
            best_col = cc
        if best_col is not None and _ok(r, best_col):
            _push((r, best_col), 1, '$')

        # 0: leftmost passable col
        left_col = c
        for cc in range(c - 1, -1, -1):
            if not composite.is_passable(r, cc):
                break
            left_col = cc
        if left_col < c and _ok(r, left_col):
            _push((r, left_col), 1, '0')

        # ^: first rune in passability-bounded range (any direction from current col)
        lb = c
        for cc in range(c - 1, -1, -1):
            if not composite.is_passable(r, cc):
                break
            lb = cc
        rb = c
        for cc in range(c + 1, COLS):
            if not composite.is_passable(r, cc):
                break
            rb = cc
        for cc in range(lb, rb + 1):
            ru2 = composite.rune_at(r, cc)
            if ru2:
                if _ok(r, cc):
                    _push((r, cc), 1, '^')
                break  # first rune (void or not) terminates search

        # count ge/gE (backward-end motions, chained); base cost +1 for the 'g' prefix.
        # Pushed BEFORE w/b/e so that gE wins tiebreaks when 9b and gE reach the same
        # cell at equal cost (2 ks each); gE is the pedagogically preferred motion.
        # ge before gE: on the LT2 gap, ge and gE both cost 2 ks but ge is the simpler
        # command taught first, so ge wins that tiebreak.
        for fn, key in ((_ge, 'ge'), (_gE, 'gE')):
            pos2 = (r, c)
            for n in range(1, max_n):
                nxt = fn(*pos2)
                if nxt is None:
                    break
                mc2  = 2 if n == 1 else len(str(n)) + 2
                lbl2 = key if n == 1 else f'{n}{key}'
                _push(nxt, mc2, lbl2)
                pos2 = nxt

        # count W/B/E (WORD motions, chained) — before w/b/e so W/B/E win tiebreaks
        # when both reach the same cell at equal cost (isolated uniform-type clusters).
        for fn, key in ((_W, 'W'), (_B, 'B'), (_E, 'E')):
            pos2 = (r, c)
            for n in range(1, max_n):
                nxt = fn(*pos2)
                if nxt is None:
                    break
                mc2  = 1 if n == 1 else len(str(n)) + 1
                lbl2 = key if n == 1 else f'{n}{key}'
                _push(nxt, mc2, lbl2)
                pos2 = nxt

        # count w/b/e (word motions, chained)
        for fn, key in ((_w, 'w'), (_b, 'b'), (_e, 'e')):
            pos2 = (r, c)
            for n in range(1, max_n):
                nxt = fn(*pos2)
                if nxt is None:
                    break
                mc2  = 1 if n == 1 else len(str(n)) + 1
                lbl2 = key if n == 1 else f'{n}{key}'
                _push(nxt, mc2, lbl2)
                pos2 = nxt

    if return_path:
        return None, ''
    return None


def build_dungeon_8(seed: int) -> Dungeon:
    """Level 7 — ge/gE: The Backward Vaults.

    Six 1-row corridors in a snake pattern (13 rows × 40 cols).  Each corridor
    is bridged to the next by a turn room at alternating ends.  Two turns have
    narrow gaps that physically enforce the lesson:

      LT2 (rows 7-9, cols 5-6)  — ge gap
        C4 anchor: 4-char rune at cols 2-5.  ge lands at end=5 (in gap);
        b   lands at start=2 (wall in row 8 — cannot descend).

      LT3 (rows 11-12, col 19) — gE gap
        C6 (row 11) cols 21-38 hold the baphomet/behemoth WORD: two adjacent
        clusters forming one WORD (col 21-28 + col 29-38, no gap between them).
        An anchor rune ends at col 19; col 20 is an empty gap.
        From col 38: gE hops the whole WORD in 1 step → lands at col 19 = 2 ks.
        ge needs 2 hops (one per cluster) → 2ge = 3 ks > gE = 2 ks.
        19h = 3 ks, also slower.  gE is the strict winner.

    Guard walls at (2,38) and (4,1) narrow RT1 and LT1:
      (2,38) blocks $→col 38 descent in RT1; player uses 4e→col 36 instead.
      (4,1)  blocks 0→col 1 descent in LT1; player uses ^→col 2 instead.

    Optimal route (par computed by _dijkstra_par_L8):
      4E 2j ^ 2j $ 2j ge 2j $ 2j gE j
    ge is structurally forced at C4 (b lands at wall in row 8, ge costs same as gE).
    gE is structurally forced at C6 — gE j (2+1=3 ks) beats 2ge j (3+1=4 ks).
    """
    dungeon   = Dungeon(name='The Backward Vaults', seed=seed)
    ROWS, COLS = _L8_TOTAL_ROWS, _L8_TOTAL_COLS

    cells = [[CellType.WALL] * COLS for _ in range(ROWS)]
    composite = Room(rows=ROWS, cols=COLS, room_type=RoomType.ENTRY)
    composite.cells = cells
    composite.seed  = seed

    # ── Carve corridors ───────────────────────────────────────────────────────
    for r in _L8_CORR_ROWS:
        for c in range(_L8_CORR_LEFT, _L8_CORR_RIGHT + 1):
            cells[r][c] = CellType.CORRIDOR

    # ── Carve turn spans ──────────────────────────────────────────────────────
    for r0, r1, c0, c1 in _L8_TURN_SPANS:
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

    # ── Rune clusters (seed-varying) ──────────────────────────────────────────
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

    # C1 (row 1) — e-teaching: four 3-char clusters, individual rune symbols
    for col, kind in ((5,'ancient'), (13,'verdant'), (22,'ember'), (34,'ancient')):
        runes.append(RuneCluster(row=1, col=col,
                                  symbols=(_sym(), _sym(), _sym()), kind=kind))

    # C2 (row 3) — b-teaching: four 3-char clusters, individual rune symbols
    for col, kind in ((2,'ember'), (13,'verdant'), (21,'ancient'), (29,'ember')):
        runes.append(RuneCluster(row=3, col=col,
                                  symbols=(_sym(), _sym(), _sym()), kind=kind))

    # C3 (row 5) — decorative plain words (cols 4-35, safe of LT1/RT2 turns)
    c3c = 4
    while c3c <= 33:
        length = rng.randint(3, min(6, 35 - c3c + 1))
        if length < 3:
            break
        runes.append(RuneCluster(row=5, col=c3c,
                                  symbols=tuple(_plain_word(length)),
                                  kind=rng.choice(('ancient','verdant','ember'))))
        c3c += length + rng.randint(1, 3)

    # C4 (row 7) — ge anchor: 4-char ALL-WC plain word at col 2 (end=5 lands in LT2 gap).
    # Must be all word-chars (alpha/digit/_): b from col 38 then goes to col 2 (the run
    # start), which is walled in row 8 — forcing ge/gE over b to reach the LT2 gap.
    # A mixed anchor (e.g. 'win⚑') would let b land at col 5 in 1 ks, beating gE.
    _c4_pool = [w for w in (plain.get(4) or plain[3])
                if all(c.isalpha() or c.isdigit() or c == '_' for c in w)]
    runes.append(RuneCluster(row=7, col=2,
                              symbols=tuple(rng.choice(_c4_pool or ['proc'])),
                              kind='ancient'))

    # C5 (row 9) — decorative mixed words (cols 7-36, safe of LT2/RT3 turns)
    c5c = 7
    while c5c <= 34:
        length = rng.randint(3, min(6, 36 - c5c + 1))
        if length < 3:
            break
        runes.append(RuneCluster(row=9, col=c5c,
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
    # Anchor rune at cols 18-19 (ends at 19): gE landing cell.
    # Col 20 is always an empty gap between anchor and the big WORD.
    # Cols 2-16: seed-randomized mixed filler.
    _kinds3 = ('ancient', 'verdant', 'ember')
    _bb_kind = rng.choice(_kinds3)
    runes.append(RuneCluster(row=11, col=21,
                             symbols=tuple('b4¶♯∘m3†'), kind=_bb_kind))  # A: cols 21-28
    runes.append(RuneCluster(row=11, col=29,
                             symbols=('!', '='), kind=_bb_kind))          # S: cols 29-30
    runes.append(RuneCluster(row=11, col=31,
                             symbols=tuple('b3♯3m∘†♯'), kind=_bb_kind))  # B: cols 31-38

    # Anchor: 2-char cluster ending at col 19; col 20 always empty
    runes.append(RuneCluster(row=11, col=18,
                             symbols=(_sym(), _sym()), kind=rng.choice(_kinds3)))

    # Seed-randomized mixed filler in cols 2-16
    _c6c = 2
    while _c6c <= 16:
        _flen = rng.randint(1, max(1, min(3, 17 - _c6c)))
        runes.append(RuneCluster(row=11, col=_c6c,
                                 symbols=tuple(_sym() for _ in range(_flen)),
                                 kind=rng.choice(_kinds3)))
        _c6c += _flen + rng.randint(1, 2)

    composite.runes = runes

    composite.spawn_pos    = (1, 1)
    composite.exit_pos = (12, 19)
    composite.entities = [Entity(kind='exit', row=12, col=19)]

    composite.rebuild_indexes()
    par, path = _dijkstra_par_L8(composite, return_path=True)
    if par is None:
        par, path = 20, '4E 2j ^ 2j $ 2j ge 2j $ 2j gE j'
    composite.par    = par
    composite.budget = math.ceil(par * 1.4)
    composite.answer = path
    dungeon.rooms        = [composite]
    dungeon.current_room = 0
    return dungeon


def build_dungeon_7(seed: int) -> Dungeon:
    """The WORD Forge — teaches W B E (WORD motions over code-text clusters).

    Three 2-row corridors, snake pattern (10 rows × 58 cols):
      C1 rows 1-2:  left→right   W teaching: packed adjacent code-char clusters
      C2 rows 4-5:  right→left   B teaching: packed adjacent code-char clusters
      C3 rows 7-8:  left→right   E teaching: exit at end of big packed group

    Packed code groups use single-char RuneClusters placed adjacently:
      w stops at every char (many keystrokes);  W jumps the whole group (one).
    Spaced rune clusters in filler zones: w ≡ W (both stop cluster-by-cluster).
    Budget is computed using the W/B/E-optimal path; w/b/e-only far exceeds it.
    """
    _load_vocab_tables()
    rng     = random.Random(seed)
    # Pick 4 distinct untypable chars: first two → W4 anchor, last two → B1 anchor.
    _four   = rng.sample(_L7_UNTYPABLE_PUNCT, 4)
    _anchor_W = ''.join(_four[:2])   # W4 at (1, 53-54)
    _anchor_B = ''.join(_four[2:])   # B1 at (4,  3-4)
    dungeon = Dungeon(name='The WORD Forge', seed=seed)
    ROWS, COLS = _L7_TOTAL_ROWS, _L7_TOTAL_COLS

    cells = [[CellType.WALL] * COLS for _ in range(ROWS)]
    composite = Room(room_type=RoomType.ENTRY, rows=ROWS, cols=COLS)
    composite.cells = cells
    composite.seed  = seed

    # ── Carve corridors (2 rows each) ─────────────────────────────────────────
    for row_top in _L7_CORR_TOP_ROWS:
        for c in range(_L7_CORR_LEFT, _L7_CORR_RIGHT + 1):
            cells[row_top][c]     = CellType.CORRIDOR
            cells[row_top + 1][c] = CellType.CORRIDOR

    # ── Carve turn rooms ─────────────────────────────────────────────────────
    for r0, r1, c0, c1 in _L7_TURN_SPANS:
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
    _hardcoded: list[RuneCluster] = []
    for row, col_start, text, kind in _L7_CODE_GROUPS:
        _l7_place_code_group(_hardcoded, row, col_start, text, kind)
    # Seed-varying untypable anchors (f/F cannot target these chars)
    _l7_place_code_group(_hardcoded, 1, 53, _anchor_W, 'ember')  # W4 anchor
    _l7_place_code_group(_hardcoded, 4,  3, _anchor_B, 'ember')  # B1 anchor

    # C2 left-end void guards (both rows): the first non-blank cell on each C2
    # row, so ^/0 land on them (death) while B skips back WORD-by-WORD to the
    # anchor at col 3. Forces B over the line-start shortcuts.
    _hardcoded.append(RuneCluster(row=4, col=1, symbols=('○',), kind='void'))
    _hardcoded.append(RuneCluster(row=5, col=1, symbols=('○',), kind='void'))

    # ── Blocked cell set (code text + exit — filler must not overlap) ──────────
    _bl: set = {(7, 51)}
    for ru in _hardcoded:
        for i in range(len(ru.symbols)):
            _bl.add((ru.row, ru.col + i))
    blocked = frozenset(_bl)

    # ── Random filler rune clusters (secondary rows only; primary rows fixed) ──
    for _attempt in range(20):
        composite.runes = list(_hardcoded)
        rng2 = random.Random(rng.randint(0, 2**31))

        _l7_fill_row(composite, rng2, 2,  3, 52, density=0.45, blocked=blocked, word_tbl=_VOCAB_MIXED_BY_LEN)  # C1r2 baseline
        _l7_fill_row(composite, rng2, 5,  3, 52, density=0.45, blocked=blocked, word_tbl=_VOCAB_MIXED_BY_LEN)  # C2r5 baseline
        _l7_fill_row(composite, rng2, 8,  3, 52, density=0.45, blocked=blocked, word_tbl=_VOCAB_MIXED_BY_LEN)  # C3r8 baseline

        # Protect entry and exit from void runes
        entry_r, entry_c = composite.spawn_pos
        exit_r,  exit_c  = composite.exit_pos
        composite.runes = [
            ru for ru in composite.runes
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


def build_dungeon_6(seed: int) -> Dungeon:
    """Level 14 — Visual Mode: The Sight Sanctum.

    Fixed U-shaped layout:
        #####################
        #@~~~~~~~~~~~~~~~~~~#
        ##################  #
        #E!~~~~~~~~~~~~~~~~~#
        #####################

    Top corridor (row 1): void runes at cols 2-19 (60% random per cell).
    Bottom corridor (row 3): exit at col 1, dynamite at col 2, void runes at
    cols 3-18 (60% random per cell).
    Gap connecting rows 1–3 at cols 18-19 of row 2.

    Optimal route (par=11):  v $ x $ j j v F ! x h
      v$x  — select all of row 1; x clears its voids; player back at (1,1).
      $jj  — navigate right-end → gap → (3,19).
      vF!x — select from (3,19) back to dynamite at (3,2); x deletes cols 2-19
             (exit at col 1 is outside the selection); player lands at col 2.
      h    — step left onto exit at (3,1).
    """
    ROWS, COLS = 5, 21
    dungeon   = Dungeon(name='The Sight Sanctum', seed=seed)
    composite = Room(rows=ROWS, cols=COLS, room_type=RoomType.ENTRY)

    cells = [[CellType.WALL] * COLS for _ in range(ROWS)]
    for c in range(1, 20):
        cells[1][c] = CellType.CORRIDOR
    cells[2][18] = CellType.CORRIDOR
    cells[2][19] = CellType.CORRIDOR
    for c in range(1, 20):
        cells[3][c] = CellType.CORRIDOR
    composite.cells = cells

    rng = random.Random(seed)
    for c in range(2, 20):                   # row 1: cols 2-19
        if rng.random() < 0.6:
            composite.runes.append(RuneCluster(row=1, col=c, symbols=('○',), kind='void'))
    for c in range(3, 19):                   # row 3: cols 3-18 (col 19 always clear)
        if rng.random() < 0.6:
            composite.runes.append(RuneCluster(row=3, col=c, symbols=('○',), kind='void'))

    composite.entities.append(Entity(kind='exit',     row=3, col=1))
    composite.entities.append(Entity(kind='dynamite', row=3, col=2))

    composite.spawn_pos  = (1, 1)
    composite.par    = 11
    composite.budget = math.ceil(11 * 1.4)
    composite.answer = 'v $ x $ j j v F ! x h'

    composite.rebuild_indexes()
    dungeon.rooms        = [composite]
    dungeon.current_room = 0
    return dungeon


# ── Level 11 layout constants ─────────────────────────────────────────────────
#
# Three-corridor snake layout (7 rows × 60 cols).
# Each corridor row has ( at col _L11_BRACKET_OPEN and ) at col _L11_BRACKET_CLOSE.
# Row 3 (middle) is filled with void runes everywhere EXCEPT the two bracket cells,
# forcing the player to use % to cross it rather than manual h/l navigation.
#
# Right turn: col _L11_BRACKET_CLOSE, rows 1-3 (single-column gap cell at row 2).
# Left turn:  col _L11_BRACKET_OPEN,  rows 3-5 (single-column gap cell at row 4).
#
# Optimal path (par=7):  % 2j % 2j %
#   Entry (1,1): % scans right, finds ( at col 4, jumps to ) at col 54.
#   2j → (3,54) ).  % → (3,4) (.  2j → (5,4) (.  % → (5,54) EXIT.
#   % at (1,1) is not on a bracket but Vim-style % scans right for the first
#   bracket on the row — finds ( col 4 and jumps to its match ) col 54.
#
_L11_ROWS          = 7
_L11_COLS          = 60
_L11_BRACKET_OPEN  = 4      # ( on each corridor row
_L11_BRACKET_CLOSE = 54     # ) on rows 1 & 3; right-turn column; exit column
_L11_CLOSE_R5      = 53     # ) on row 5 only (one left of CLS; exit sits at CLS)
_L11_CORR_ROWS     = (1, 3, 5)
_L11_ENTRY         = (1, 1)
_L11_EXIT_POS      = (5, _L11_BRACKET_CLOSE)
_L11_PAR           = 8       # % 2j % 2j % l  = 1+2+1+2+1+1 = 8 ks
_L11_ANSWER        = '% 2j % 2j % l'


def _dijkstra_par_L11(composite, use_percent: bool = True, return_path: bool = False):
    """Minimum-keystroke Dijkstra for Level 11 — The Bracket Vaults.

    Supported motions (all available at level 11):
      h/l/j/k (count), $ 0 ^, % (if use_percent=True).

    State = (row, col).
    use_percent=False simulates the command-necessity test (% disabled).
    """
    ROWS, COLS = composite.rows, composite.cols
    entry = composite.spawn_pos
    goal  = composite.exit_pos

    _PAIRS_OPEN_L11  = {'(': ')', '[': ']', '{': '}'}
    _PAIRS_CLOSE_L11 = {')': '(', ']': '[', '}': '{'}

    def _ok(r, c):
        if not composite.is_passable(r, c):
            return False
        ru = composite.rune_at(r, c)
        return not (ru and ru.kind == 'void')

    def _bracket_here(r, c):
        ru = composite.rune_at(r, c)
        if ru is not None:
            ch = ru.symbols[c - ru.col]
            if ch in _PAIRS_OPEN_L11 or ch in _PAIRS_CLOSE_L11:
                return ch
        return None

    def _pct(r, c):
        """Replicate motion.py % scan: same-row, nesting-aware, stops at walls."""
        bch   = _bracket_here(r, c)
        start = c if bch is not None else None
        # If not on a bracket, scan right for the first one (Vim behaviour).
        if start is None:
            for cc in range(c + 1, COLS):
                if composite.cells[r][cc] in (CellType.WALL, CellType.WOOD_WALL):
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
            if composite.cells[r][cc] in (CellType.WALL, CellType.WOOD_WALL):
                break
            b = _bracket_here(r, cc)
            if b == bch:
                depth += 1
            elif b == want:
                depth -= 1
                if depth == 0:
                    if _ok(r, cc) and cc != c:
                        return (r, cc)
                    return None
        return None

    dist = {entry: 0}
    prev = {entry: None}
    heap = [(0, entry)]
    max_n = max(ROWS, COLS)

    while heap:
        cost, (r, c) = heapq.heappop(heap)
        if (r, c) == goal:
            if return_path:
                return cost, _join_path(prev, (r, c), merge_single=True)
            return cost
        if cost > dist.get((r, c), float('inf')):
            continue

        def _push(nb, mc=1, lbl=''):
            if nb is None:
                return
            nr, nc = nb
            if not _ok(nr, nc):
                return
            g = cost + mc
            if g < dist.get((nr, nc), float('inf')):
                dist[(nr, nc)] = g
                prev[(nr, nc)] = ((r, c), lbl)
                heapq.heappush(heap, (g, (nr, nc)))

        # j/k (vertical), h/l (horizontal) — with count
        for dr, key in ((1, 'j'), (-1, 'k')):
            for n in range(1, max_n + 1):
                nr2 = r + dr * n
                if nr2 < 0 or nr2 >= ROWS or not _ok(nr2, c):
                    break
                mc2  = 1 if n == 1 else len(str(n)) + 1
                lbl2 = key if n == 1 else f'{n}{key}'
                _push((nr2, c), mc2, lbl2)

        for dc, key in ((1, 'l'), (-1, 'h')):
            for n in range(1, max_n + 1):
                nc2 = c + dc * n
                if nc2 < 0 or nc2 >= COLS or not _ok(r, nc2):
                    break
                mc2  = 1 if n == 1 else len(str(n)) + 1
                lbl2 = key if n == 1 else f'{n}{key}'
                _push((r, nc2), mc2, lbl2)

        # $: rightmost passable+ok col in same row
        best_col = None
        for cc in range(c + 1, COLS):
            if not composite.is_passable(r, cc):
                break
            best_col = cc
        if best_col is not None and _ok(r, best_col):
            _push((r, best_col), 1, '$')

        # 0: leftmost passable+ok col in same row
        left_col = c
        for cc in range(c - 1, -1, -1):
            if not composite.is_passable(r, cc):
                break
            left_col = cc
        if left_col < c and _ok(r, left_col):
            _push((r, left_col), 1, '0')

        # ^: first rune (any kind) scanning from leftmost passable boundary.
        # Stops at the first rune found (void or not); only pushes if _ok
        # (non-void).  Mirrors the game engine: void runes block ^ silently.
        lb = c
        for cc in range(c - 1, -1, -1):
            if not composite.is_passable(r, cc):
                break
            lb = cc
        rb = c
        for cc in range(c + 1, COLS):
            if not composite.is_passable(r, cc):
                break
            rb = cc
        for cc in range(lb, rb + 1):
            ru2 = composite.rune_at(r, cc)
            if ru2:
                if _ok(r, cc):
                    _push((r, cc), 1, '^')
                break  # first rune (void or not) terminates search

        # %: matching bracket jump (disabled in command-necessity test)
        if use_percent:
            nb_pct = _pct(r, c)
            if nb_pct is not None:
                _push(nb_pct, 1, '%')

    if return_path:
        return None, ''
    return None


def build_dungeon_12(seed: int) -> Dungeon:
    """Level 10 — % (The Bracket Vaults).

    Teaches `%` (bracket-matching jump) as the only way to cross a band of WATER.
    Layout: three horizontal corridors (rows 1/3/5) in a snake pattern, with rows
    2, 3 and 4 flooded.

    Rows 1 and 5 are open corridors.  Rows 2 and 4 are water except the single
    turn cell on each.  Row 3 is water except at ( col 4 and ) col 54 — the only
    landing cells.  WATER blocks manual h/l (is_passable is False); % scans across
    the water to the matching bracket.

    Right turn: col 54, rows 1-3.  Left turn: col 4, rows 3-5.  Row 5's ) sits at
    col 53 with the exit one cell right at (5,54).

    Optimal path (par=8):  % 2j % 2j % l
      Entry (1,1): % → ) col 54.  2j → (3,54).  % → (3,4) (.  2j → (5,4) (.
      % → (5,53) ).  l → (5,54) EXIT.

    Without %: par_no_% = None (the water band is uncrossable by hand).
    Layout is deterministic; seed only colors bracket runes.
    """
    dungeon   = Dungeon(name='The Bracket Vaults', seed=seed)
    ROWS, COLS = _L11_ROWS, _L11_COLS

    cells = [[CellType.WALL] * COLS for _ in range(ROWS)]
    composite = Room(rows=ROWS, cols=COLS, room_type=RoomType.ENTRY)
    composite.cells = cells
    composite.seed  = seed

    OPN = _L11_BRACKET_OPEN   # 4
    CLS = _L11_BRACKET_CLOSE  # 54
    EXC = _L11_CLOSE_R5       # 53  (row-5 closing bracket col)

    # ── Carve corridors ───────────────────────────────────────────────────────
    for r in _L11_CORR_ROWS:
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

    # ── Place bracket RuneClusters ────────────────────────────────────────────
    # Single-char RuneCluster at each bracket position so _bracket_at() in
    # motion.py can identify them via rune.symbols[c - rune.col].  Row 5's ) sits
    # at EXC (one left of CLS); the exit is at CLS, so the final % lands on ) at
    # EXC and one l steps onto the exit.
    rng = random.Random(seed)
    _kinds = ('ancient', 'verdant', 'ember')

    runes: list[RuneCluster] = []
    for row in _L11_CORR_ROWS:
        kind_open  = rng.choice(_kinds)
        kind_close = rng.choice(_kinds)
        close_col  = EXC if row == 5 else CLS
        runes.append(RuneCluster(row=row, col=OPN, symbols=('(',), kind=kind_open))
        runes.append(RuneCluster(row=row, col=close_col, symbols=(')',), kind=kind_close))

    composite.runes = runes

    # ── Entry and exit ────────────────────────────────────────────────────────
    composite.spawn_pos    = _L11_ENTRY
    composite.exit_pos = _L11_EXIT_POS
    composite.entities = [Entity(kind='exit',
                                 row=_L11_EXIT_POS[0], col=_L11_EXIT_POS[1])]

    composite.rebuild_indexes()

    par, path = _dijkstra_par_L11(composite, use_percent=True, return_path=True)
    if par is None:
        par, path = _L11_PAR, _L11_ANSWER
    composite.par    = par
    composite.budget = math.ceil(par * 1.4)
    composite.answer = path

    dungeon.rooms        = [composite]
    dungeon.current_room = 0
    return dungeon


# ── Level 9 — H/M/L: The Screen Vault (3 colored keys) ────────────────────────
# Viewport-filling dungeon teaching H (viewport-top), M (viewport-middle), and
# L (viewport-bottom) as distinct from G (which lands on a void row and is
# punished).  Restored from the recovered "screen_vault_3keys" design.
#   COLS=43, ROWS=game_h+4
#   Row 1             : wide top section (cols 1-41) — H key, 3 colored doors, exit
#   Rows 2..L_ROW     : narrow corridor (cols 1-25) — M key at M_ROW, L key at L_ROW
#   void row (L_ROW+3): G lands here (void) — punishes using G
# Three floor_keys (gold/red/blue) are randomly matched to three colored
# locked_doors per seed; par is Dijkstra-computed (_dijkstra_par_L10).
_L10_DEFAULT_GAME_H = 33   # main._build_dungeon's default game height
_L10_COLS      = 43
_L10_H_KEY_COL = 2    # anchor col in row 1 for H (NOT col 1)
_L10_M_KEY_COL = 25   # anchor col in M_ROW; rightmost of narrow corridor
_L10_L_KEY_COL = 1    # anchor col in L_ROW; leftmost passable
_L10_DOOR_COLS = (26, 33, 39)   # locked_door cols in row 1
_L10_EXIT_COL  = 41             # exit entity col in row 1
_L10_TOP_LEFT    = (1, 1)
_L10_SPAWN     = (8, 13)
_L10_COLORS    = ('gold', 'red', 'blue')
_L10_PAR       = 17   # deterministic: 17 for every color assignment (verified in
                      # test_level_10), so it is locked rather than re-solved on
                      # every load — the par Dijkstra is expensive for this level.


def _l10_key_rows(game_h: int) -> tuple:
    """Return (M_ROW, L_ROW) for a given game_h.

    H is always row 1.
    M_ROW = 1 + (game_h-1)//2  (Vim-faithful middle of passable rows 1..game_h-1).
    L_ROW = game_h - 1          (last row fully inside the viewport when vr_start=0).
    """
    m_row = 1 + (game_h - 1) // 2
    l_row = game_h - 1
    return m_row, l_row


def _dijkstra_par_L10(composite, return_path: bool = False):
    """Minimum-keystroke Dijkstra for the Screen Vault (3 colored keys).

    State = (row, col, inv, key_alive, doors) where:
      inv      : 0=none, 1=H key held, 2=M key held, 3=L key held
      key_alive: 3-bit mask (bit0=H key on floor, bit1=M key on floor, bit2=L key)
      doors    : 3-bit mask (bit0=door0 open, bit1=door1 open, bit2=door2 open)
    Goal: position == EXIT_POS with all doors open (doors==7).

    H/M/L are modelled viewport-relative.
    """
    game_h = composite._game_h
    m_row, l_row = _l10_key_rows(game_h)
    ROWS, COLS = composite.rows, composite.cols
    H_COL  = _L10_H_KEY_COL
    M_COL  = _L10_M_KEY_COL
    L_COL  = _L10_L_KEY_COL
    D_COLS = _L10_DOOR_COLS
    EX     = (_L10_TOP_LEFT[0], _L10_EXIT_COL)
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
                if composite.rune_at(row, col) is not None:
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

        # p: unlock door to right
        for di, dc in enumerate(D_COLS):
            if (r, c + 1) == (1, dc) and not (doors >> di & 1) and inv == door_key[di]:
                _try((r, c, 0, ka, doors | (1 << di)), 1, 'p')
        # P: unlock door to left
        for di, dc in enumerate(D_COLS):
            if (r, c - 1) == (1, dc) and not (doors >> di & 1) and inv == door_key[di]:
                _try((r, c, 0, ka, doors | (1 << di)), 1, 'P')

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

        # nG
        for n in range(1, ROWS + 1):
            tr2 = n - 1
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


def build_dungeon_10(seed: int, game_h: int = _L10_DEFAULT_GAME_H,
                     compute_answer: bool = True) -> Dungeon:
    """Level 9 — H M L: The Screen Vault (3 colored keys).

    Viewport-filling dungeon that teaches H (viewport-top), M (viewport-middle),
    and L (viewport-bottom) as distinct from G (room-last-row = void, punished).
    Restored from the recovered "screen_vault_3keys" design.

    Layout: COLS=43, ROWS=game_h+4
      Row 0          : wall border
      Row 1          : wide top section (cols 1-41) — H key, 3 locked doors, exit
      Rows 2..L_ROW  : narrow corridor (cols 1-25) — M key at M_ROW, L key at L_ROW
      L_ROW+1..+2    : extra narrow corridor (below the viewport)
      L_ROW+3        : void rune row — G lands here; using G is punished
      L_ROW+4        : wall border

    Three floor_keys (gold/red/blue, randomly assigned) unlock three colored
    locked_doors in the top section.  Par is 17 for every color assignment.

    Par is locked (`_L10_PAR`) instead of re-solved on every load; the full answer
    path (admin-only) is solved lazily via ``compute_answer``.
    """
    dungeon = Dungeon(name='The Screen Vault', seed=seed)
    ROWS   = game_h + 4
    COLS   = _L10_COLS
    m_row, l_row = _l10_key_rows(game_h)

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
    # Void rune row: CORRIDOR cells (void runes placed as rune clusters below)
    void_row = l_row + 3
    for c in range(1, 26):
        cells[void_row][c] = CellType.CORRIDOR

    # ── Color assignment ──────────────────────────────────────────────────────
    colors = list(_L10_COLORS)
    key_colors  = colors[:]
    rng.shuffle(key_colors)   # key_colors[0]=H key, [1]=M key, [2]=L key
    door_colors = colors[:]
    rng.shuffle(door_colors)  # door_colors[0]=door0, [1]=door1, [2]=door2

    inv_for_color = {c: i + 1 for i, c in enumerate(key_colors)}
    composite._door_key = [inv_for_color[dc] for dc in door_colors]

    # ── Entities: keys, doors, exit ───────────────────────────────────────────
    composite.entities = [
        Entity(kind='floor_key',   row=1,     col=_L10_H_KEY_COL, tag=key_colors[0]),
        Entity(kind='floor_key',   row=m_row, col=_L10_M_KEY_COL, tag=key_colors[1]),
        Entity(kind='floor_key',   row=l_row, col=_L10_L_KEY_COL, tag=key_colors[2]),
        Entity(kind='locked_door', row=1, col=_L10_DOOR_COLS[0],  tag=door_colors[0]),
        Entity(kind='locked_door', row=1, col=_L10_DOOR_COLS[1],  tag=door_colors[1]),
        Entity(kind='locked_door', row=1, col=_L10_DOOR_COLS[2],  tag=door_colors[2]),
        Entity(kind='exit',        row=1, col=_L10_EXIT_COL),
    ]

    # ── Runes ─────────────────────────────────────────────────────────────────
    _load_vocab_tables()
    plain = _VOCAB_PLAIN_BY_LEN
    kinds  = ('ancient', 'verdant', 'ember')
    blocked: set = set()

    # Anchor runes at key positions (so H/M/L fnb returns the key col)
    for anchor_row, anchor_col in (
        (1,     _L10_H_KEY_COL),
        (m_row, _L10_M_KEY_COL),
        (l_row, _L10_L_KEY_COL),
    ):
        sym = rng.choice([('∘',), ('·',), ('⊙',), ('∙',)])
        composite.runes.append(RuneCluster(row=anchor_row, col=anchor_col,
                                           symbols=sym, kind=rng.choice(kinds)))
        blocked.add((anchor_row, anchor_col))

    # Row 1: vocab runes only in the left section (before the first door); the
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
            composite.runes.append(RuneCluster(row=1, col=c,
                                               symbols=tuple(word),
                                               kind=rng.choice(kinds)))
            for i in range(len(word)):
                blocked.add((1, c + i))
            c += len(word) + rng.randint(1, 2)

    # Narrow corridor rows: vocab runes.  The M row IS filled (cols 1-24), so M
    # lands on the leftmost rune and the player must then $ to reach the M key
    # at col 25 — i.e. "M $", not just "M".
    for row in range(2, l_row + 3):
        c = 1
        while c <= 25:
            if (row, c) in blocked:
                c += 1
                continue
            if row == _L10_SPAWN[0] and abs(c - _L10_SPAWN[1]) <= 1:
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
            composite.runes.append(RuneCluster(row=row, col=c,
                                               symbols=tuple(word),
                                               kind=rng.choice(kinds)))
            for i in range(len(word)):
                blocked.add((row, c + i))
            c += len(word) + rng.randint(1, 3)

    # Void rune row: standard void runes (○) across cols 1-25 — where G lands.
    for c in range(1, 26):
        composite.runes.append(RuneCluster(row=void_row, col=c,
                                           symbols=('○',), kind='void'))

    # ── Entry / spawn / exit ──────────────────────────────────────────────────
    composite.spawn_pos = _L10_SPAWN
    composite.exit_pos  = (1, _L10_EXIT_COL)

    composite.rebuild_indexes()

    # ── Par / answer ──────────────────────────────────────────────────────────
    # Par is locked at _L10_PAR (deterministic; test_level_10 runs the solver to
    # verify).  The answer path is only shown to admin, so solve for it only when
    # compute_answer is set — the Dijkstra is too slow to run on every load.
    composite.par    = _L10_PAR
    composite.budget = math.ceil(_L10_PAR * 1.4)
    composite.answer = _dijkstra_par_L10(composite, return_path=True)[1] if compute_answer else ''

    dungeon.rooms        = [composite]
    dungeon.current_room = 0
    return dungeon


# ── Level 12 layout constants ─────────────────────────────────────────────────
# Room: 22 rows × 48 cols.  Main area cols 1–42; side room row 15 cols 43–46.
#
# Blank rows (passable, no rune clusters): 1, 3, 5, 9, 15, 17, 19.
# Content rows (≥1 rune cluster): 2, 4, 6, 7, 8, 10, 11, 12, 13, 14, 16, 18, 20.
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

_L13_ROWS     = 22
_L13_COLS     = 48        # main 44 (cols 0–43) + side room 4 (cols 44–47)
_L13_ENTRY    = (9, 20)   # spawn position
_L13_EXIT     = (15, 46)  # exit entity (inside side room)
_L13_KEY_POS  = (5, 1)    # floor_key entity (blank row above code block)
_L13_DOOR_POS = (15, 43)  # locked_door entity
_L13_VOID_POS = (20, 1)   # void rune
_L13_PAR      = 7
_L13_ANSWER   = '{ x } } $ p $'

# ── Level 14 (Sentence Corridor) constants ────────────────────────────────
# Without (/): wall gaps (cols 11-22 and 37-48) block all l/h/w paths.
#              Player trapped in S1 (cols 1-10).  Cost = infinity >> budget.

_L14_ROWS     = 3
_L14_COLS     = 62
_L14_ENTRY    = (1, 1)
_L14_EXIT     = (1, 49)

_L14_SENT_ROW = 1
_L14_S1_COLS  = (1, 10)
_L14_S2_COLS  = (23, 36)
_L14_S3_COLS  = (49, 60)

_L14_SENT_CLUSTERS = [
    (1, 2,  ('T','h','e',' ','s','e','a','l','.')),
    (1, 23, ('A','n','c','i','e','n','t',' ','p','o','w','e','r','!')),
    (1, 49, ('T','h','e',' ','g','a','t','e',' ','o','!')),
]


def _dijkstra_par_L13(composite, return_path=False,
                      disable_brace=False, disable_paren=False):
    """Minimum-keystroke Dijkstra for Level 12 — Paragraph Jumps (The Runic Archives).

    State = (row, col, has_key, door_open) where:
      has_key:   0 = key on floor, 1 = key held
      door_open: 0 = locked_door blocking, 1 = door removed

    Available motions: hjkl, count-hjkl, 0, $, { } (unless disable_brace), x, p.
    disable_paren accepted but ignored (no sentence jumps in this level).
    """
    ROWS, COLS = composite.rows, composite.cols
    KR, KC = _L13_KEY_POS
    DR, DC = _L13_DOOR_POS
    EX     = _L13_EXIT
    entry  = composite.spawn_pos
    max_n  = max(ROWS, COLS)

    def _ok(r, c, door_open):
        if not (0 <= r < ROWS and 0 <= c < COLS):
            return False
        if composite.cells[r][c] not in (CellType.CORRIDOR, CellType.FLOOR):
            return False
        if (r, c) == (DR, DC) and not door_open:
            return False
        ru = composite.rune_at(r, c)
        return not (ru and ru.kind == 'void')

    def _row_blank(row, door_open):
        has_pass = any(_ok(row, cc, door_open) for cc in range(COLS))
        has_rune = any(composite.rune_at(row, cc) is not None for cc in range(COLS))
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


# ── Level 8 — G/gg: The Long Plumb ─────────────────────────────────────────
# 16-row × 11-col vertical shaft teaching G (last line), gg (first line), and
# {n}G (nth line).  Restored from the admin design layout saved as
# "dungeon_09_the_screen_vault_pre-reversion" (a mislabel — it is the Long Plumb).
#
# Layout:
#   Row 1     : top corridor cols 1-9; start (1,1), exit (1,9);
#               locked_doors at (1,3) and (1,6) gate the corridor
#   Row 2     : cols 1-2, 4-5, 7-9 (walls at 3,6 — under the doors), so the two
#               doors are the ONLY horizontal crossings of the top
#   Rows 3-14 : a 2-wide left shaft (cols 1-2)
#   floor_keys: (4,1) and (14,2) — buried near the top and bottom of the shaft
#
# Both doors are untagged (either key opens either door), but only ONE key can be
# held at a time (x overwrites the register), so the solve is: fetch a key, open a
# door, fetch the other, open the other, reach the exit — riding the shaft with
# G (→ row 14), {n}G, and gg (→ row 1).  Par/answer are computed by
# _dijkstra_par_LGG (key/door + line-jump model).
_LGG_ROWS  = 16
_LGG_COLS  = 11
_LGG_ENTRY = (1, 1)             # spawn / first line
_LGG_EXIT  = (1, 9)             # exit entity == exit_pos (top-right)
_LGG_KEYS  = ((4, 1), (14, 2))  # floor_key positions
_LGG_DOORS = ((1, 3), (1, 6))   # locked_door positions
# Passable columns per row (every other cell is WALL):
_LGG_PASSABLE = {
    1: tuple(range(1, 10)),               # top corridor cols 1-9
    2: (1, 2, 4, 5, 7, 8, 9),             # walls at 3,6 under the doors
    **{r: (1, 2) for r in range(3, 15)},  # 2-wide left shaft, rows 3-14
}


def _dijkstra_par_LGG(composite, return_path: bool = False,
                      disable_line_jumps: bool = False):
    """Minimum-keystroke Dijkstra for Level 8 — The Long Plumb.

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
    Goal: reach _LGG_EXIT (only reachable once both doors are open).
    """
    ROWS, COLS = composite.rows, composite.cols
    entry = composite.spawn_pos
    keys  = _LGG_KEYS
    doors = _LGG_DOORS
    EX    = _LGG_EXIT
    max_n = max(ROWS, COLS)
    FULL_KEYS  = (1 << len(keys)) - 1
    door_index = {d: i for i, d in enumerate(doors)}

    def _ok(r, c, dm):
        if not (0 <= r < ROWS and 0 <= c < COLS):
            return False
        if composite.cells[r][c] not in (CellType.CORRIDOR, CellType.FLOOR):
            return False
        di = door_index.get((r, c))
        if di is not None and not (dm >> di & 1):
            return False          # closed locked_door blocks
        ru = composite.rune_at(r, c)
        return not (ru and ru.kind == 'void')

    def _fnb(row, dm):
        """First-non-blank col (matches motion._first_non_blank_col): first rune
        start, else leftmost passable; None if the row has no passable cell."""
        left = None
        for c in range(COLS):
            if _ok(row, c, dm):
                if left is None:
                    left = c
                if composite.rune_at(row, c) is not None:
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

        # x: pick up a floor_key here (overwrites the single register slot)
        for ki, kp in enumerate(keys):
            if (r, c) == kp and (km >> ki & 1):
                _try((r, c, km & ~(1 << ki), 1, dm), 1, 'x')

        # p / P: open an adjacent locked_door, consuming the held key
        if hold:
            for di, dp in enumerate(doors):
                if dm >> di & 1:
                    continue
                if (r, c + 1) == dp:
                    _try((r, c, km, 0, dm | (1 << di)), 1, 'p')
                if (r, c - 1) == dp:
                    _try((r, c, km, 0, dm | (1 << di)), 1, 'P')

        if not disable_line_jumps:
            # G: last line (scan up to a passable row), land on first-non-blank
            for rr in range(ROWS - 1, -1, -1):
                gc = _fnb(rr, dm)
                if gc is not None:
                    if (rr, gc) != (r, c):
                        _try((rr, gc, km, hold, dm), 1, 'G')
                    break

            # gg: first line (scan down to a passable row), land on first-non-blank (2 ks)
            for rr in range(ROWS):
                gc = _fnb(rr, dm)
                if gc is not None:
                    if (rr, gc) != (r, c):
                        _try((rr, gc, km, hold, dm), 2, 'gg')
                    break

            # {n}G: line n (1-based); scan down from row n-1 to a passable row, fnb
            for n in range(1, ROWS + 1):
                rr = n - 1
                while rr < ROWS and _fnb(rr, dm) is None:
                    rr += 1
                if rr >= ROWS:
                    continue
                tc = _fnb(rr, dm)
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
        fb = _fnb(r, dm)
        if fb is not None and fb != c:
            _try((r, fb, km, hold, dm), 1, '^')

    return (None, '') if return_path else None


def build_dungeon_9(seed: int) -> 'Dungeon':
    """Level 8 — G gg {n}G: The Long Plumb.

    A 16-row × 11-col vertical shaft (restored from the admin design layout
    "dungeon_09_the_screen_vault_pre-reversion" — a mislabel; it is the Long
    Plumb).  The exit sits on the top row behind two locked doors; the two keys
    are buried near the top and bottom of a 2-wide left shaft, so the player
    rides G / gg / {n}G up and down to fetch a key, open a door, and repeat.
    Fixed layout (no seed variation); see the _LGG_* block above for geometry.

    Par/answer are computed by _dijkstra_par_LGG (key/door + line-jump model);
    e.g. par 15 = G l x 13k p 5G x gg $ p $.
    """
    dungeon = Dungeon(name='The Long Plumb', seed=seed)
    ROWS, COLS = _LGG_ROWS, _LGG_COLS

    cells = [[CellType.WALL] * COLS for _ in range(ROWS)]
    composite = Room(rows=ROWS, cols=COLS, room_type=RoomType.ENTRY)
    composite.cells = cells
    composite.seed  = seed

    # ── Carve the fixed layout (see _LGG_PASSABLE above) ──────────────────────
    for row, passable_cols in _LGG_PASSABLE.items():
        for c in passable_cols:
            cells[row][c] = CellType.CORRIDOR

    # ── Entry / exit / keys / doors ───────────────────────────────────────────
    composite.spawn_pos   = _LGG_ENTRY
    composite.exit_pos = _LGG_EXIT
    entities = [Entity(kind='exit', row=_LGG_EXIT[0], col=_LGG_EXIT[1])]
    for kr, kc in _LGG_KEYS:
        entities.append(Entity(kind='floor_key', row=kr, col=kc))
    for dr, dc in _LGG_DOORS:
        entities.append(Entity(kind='locked_door', row=dr, col=dc))
    composite.entities = entities
    composite.runes = []   # no seed-varying runes; the layout is fixed

    composite.rebuild_indexes()
    _fog_unreachable(composite, composite.spawn_pos[0], composite.spawn_pos[1])

    # ── Compute par via Dijkstra (key/door + line-jump model) ─────────────────
    par, path = _dijkstra_par_LGG(composite, return_path=True)
    if par is None:                      # fixed map — should always solve
        raise RuntimeError('Level 8 (The Long Plumb) is unsolvable — check layout')
    composite.par    = par
    composite.budget = math.ceil(par * 1.4)
    composite.answer = path

    dungeon.rooms        = [composite]
    dungeon.current_room = 0
    return dungeon


def build_dungeon_13(seed: int) -> 'Dungeon':
    """Level 12 (id=12) — Paragraph Jumps: The Runic Archives.

    Layout: 22 rows × 48 cols.
    Main area: rows 1–20, cols 1–42.  Side room: row 15, cols 43–46.

    Blank rows (no rune clusters): 1, 3, 5, 9, 15, 17, 19.
    Content rows (≥1 rune cluster): 2, 4, 6, 7, 8, 10–14, 16, 18, 20.

    floor_key at (5,1) — blank row above the three-row code block (6-8).
    locked_door at (15,43) — right wall of main room at door row.
    exit at (15,46) — inside side room.

    Optimal path (par=7):  { x } } $ p $   (spawn (9,20), a blank row)
    """
    dungeon   = Dungeon(name='The Runic Archives', seed=seed)
    ROWS, COLS = _L13_ROWS, _L13_COLS

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

    # Rune content
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
                    runes.append(RuneCluster(row=row, col=c, symbols=syms, kind=kind))
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

    runes.append(RuneCluster(row=_L13_VOID_POS[0], col=_L13_VOID_POS[1],
                             symbols=('○',), kind='void'))
    composite.runes = runes

    composite.spawn_pos   = _L13_ENTRY
    composite.exit_pos = _L13_EXIT
    composite.entities = [
        Entity(kind='floor_key',   row=_L13_KEY_POS[0],  col=_L13_KEY_POS[1]),
        Entity(kind='locked_door', row=_L13_DOOR_POS[0], col=_L13_DOOR_POS[1]),
        Entity(kind='exit',        row=_L13_EXIT[0],     col=_L13_EXIT[1]),
    ]

    composite.rebuild_indexes()

    par, path = _dijkstra_par_L13(composite, return_path=True)
    if par is None:
        par, path = _L13_PAR, _L13_ANSWER
    composite.par    = par
    composite.budget = math.ceil(par * 1.4)
    composite.answer = path

    dungeon.rooms        = [composite]
    dungeon.current_room = 0
    return dungeon



def build_dungeon_14(seed: int) -> 'Dungeon':
    """Level 13 — Sentence Jumps: The Sentence Corridor.

    Fixed layout: 3 rows × 62 cols.  Only row 1 is passable.

    S1 (cols 1–10)  — 'The seal.'      ends with '.'
    Wall gap (cols 11–22)
    S2 (cols 23–36) — 'Ancient power!' ends with '!'
    Wall gap (cols 37–48)
    S3 (cols 49–59) — 'The gate o!'    ends with '!'
    Exit entity at (1, 49) = sentence-3 start.

    Optimal path (par = 2):  3)
      3) — entry col 1 → S1 col 2 → S2 col 23 → S3/exit col 49  (2 ks)

    Without (/): wall gaps trap player in S1 (cols 1–10).  Cost = infinity.
    """
    dungeon   = Dungeon(name='The Sentence Corridor', seed=seed)
    ROWS, COLS = _L14_ROWS, _L14_COLS

    cells = [[CellType.WALL] * COLS for _ in range(ROWS)]
    composite = Room(rows=ROWS, cols=COLS, room_type=RoomType.ENTRY)
    composite.cells = cells
    composite.seed  = seed

    # ── Carve sentence row (row 1, cols 1–60) ────────────────────────────────
    for c in range(1, COLS - 1):
        cells[_L14_SENT_ROW][c] = CellType.CORRIDOR

    # ── Re-wall gaps between sentence segments ────────────────────────────────
    s1_end = _L14_S1_COLS[1]   # col 10
    s2_beg = _L14_S2_COLS[0]   # col 23
    s2_end = _L14_S2_COLS[1]   # col 36
    s3_beg = _L14_S3_COLS[0]   # col 49

    for c in range(s1_end + 1, s2_beg):   # cols 11-22
        cells[_L14_SENT_ROW][c] = CellType.WALL
    for c in range(s2_end + 1, s3_beg):   # cols 37-48
        cells[_L14_SENT_ROW][c] = CellType.WALL

    # ── Fixed sentence rune clusters ──────────────────────────────────────────
    runes: list = []
    for row, col, syms in _L14_SENT_CLUSTERS:
        runes.append(RuneCluster(row=row, col=col, symbols=syms, kind='ember'))
    composite.runes = runes

    # ── Entry and exit ─────────────────────────────────────────────────────────
    composite.spawn_pos    = _L14_ENTRY
    composite.exit_pos = _L14_EXIT
    composite.entities = [Entity(kind='exit', row=_L14_EXIT[0], col=_L14_EXIT[1])]

    composite.rebuild_indexes()

    # Fixed layout with fixed optimal path (par always 2).
    composite.par    = 2
    composite.budget = math.ceil(2 * 1.4)
    composite.answer = '3)'

    dungeon.rooms        = [composite]
    dungeon.current_room = 0
    return dungeon
