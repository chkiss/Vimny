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
    entry = composite.entry
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
    entry = composite.entry
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
    entry = composite.entry
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
    composite.entry = (1, 2)

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
        entry_r, entry_c = composite.entry
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
    entry = composite.entry
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
    composite.entry = (2, 2)

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
    composite.entry = (2, 2)

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
        entry_r, entry_c = composite.entry
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

    _fog_unreachable(composite, composite.entry[0], composite.entry[1])

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

    entry = composite.entry
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

    entry = composite.entry
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

    composite.entry    = (1, 1)
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
    composite.entry    = (1, 1)
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

    composite.entry    = (1, 1)
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

    composite.entry    = (1, 1)
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
    _fog_unreachable(composite, composite.entry[0], composite.entry[1])
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
    composite.entry    = (1, 1)
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
    _fog_unreachable(composite, composite.entry[0], composite.entry[1])

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
    composite.entry    = (3, 0)
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
    entry = composite.entry
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
    entry = composite.entry
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
    """Level 8 — ge/gE: The Backward Vaults.

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

    composite.entry    = (1, 1)
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
    composite.entry    = (1, 1)
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
        entry_r, entry_c = composite.entry
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
    """Level 6 — Visual Mode (The Warden's Precision).

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
    dungeon   = Dungeon(name="The Warden's Precision", seed=seed)
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

    composite.entry  = (1, 1)
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
_L11_BRACKET_CLOSE = 54     # ) on each corridor row  (span = 50 cols)
_L11_CORR_ROWS     = (1, 3, 5)
_L11_ENTRY         = (1, 1)
_L11_EXIT_POS      = (5, _L11_BRACKET_CLOSE)
_L11_PAR           = 7       # % 2j % 2j %  = 1+2+1+2+1 = 7 ks
_L11_ANSWER        = '% 2j % 2j %'


def _dijkstra_par_L11(composite, use_percent: bool = True, return_path: bool = False):
    """Minimum-keystroke Dijkstra for Level 11 — The Bracket Vaults.

    Supported motions (all available at level 11):
      h/l/j/k (count), $ 0 ^, % (if use_percent=True).

    State = (row, col).
    use_percent=False simulates the command-necessity test (% disabled).
    """
    ROWS, COLS = composite.rows, composite.cols
    entry = composite.entry
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
    """Level 11 — % (The Bracket Vaults).

    Teaches `%` (bracket-matching jump) as the only way to cross a void-filled
    middle corridor row.  Layout: three horizontal corridors in a snake pattern.

    Rows 1 and 5 are open corridors (no voids): free navigation.
    Row 3 is void-filled except at ( col 4 and ) col 54 — the only safe
    landing cells.  Manual h/l cannot cross row 3; % jumps directly to the
    matching bracket, skipping void cells.

    Right turn: col 54, rows 1-3.  Left turn: col 4, rows 3-5.

    Optimal path (par=7):  % 2j % 2j %
      Entry (1,1): % scans right, finds ( col 4, jumps to ) col 54.
      2j → (3,54) ).  % → (3,4) (.  2j → (5,4) (.  % → (5,54) EXIT.

    Without %: par_no_% = None (row 3 void wall is uncrossable).
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

    # ── Carve corridors ───────────────────────────────────────────────────────
    for r in _L11_CORR_ROWS:
        for c in range(1, COLS - 1):
            cells[r][c] = CellType.CORRIDOR

    # ── Carve turns ───────────────────────────────────────────────────────────
    # Right turn: col CLS rows 1-3 (the j-path down from C1 to C2)
    cells[2][CLS] = CellType.CORRIDOR
    # Left turn: col OPN rows 3-5 (the j-path down from C2 to C3)
    cells[4][OPN] = CellType.CORRIDOR

    # ── Place bracket RuneClusters ────────────────────────────────────────────
    # Single-char RuneCluster at each bracket position so _bracket_at() in
    # motion.py can identify them via rune.symbols[c - rune.col].
    rng = random.Random(seed)
    _kinds = ('ancient', 'verdant', 'ember')

    runes: list[RuneCluster] = []
    for row in _L11_CORR_ROWS:
        kind_open  = rng.choice(_kinds)
        kind_close = rng.choice(_kinds)
        runes.append(RuneCluster(row=row, col=OPN, symbols=('(',), kind=kind_open))
        runes.append(RuneCluster(row=row, col=CLS, symbols=(')',), kind=kind_close))

    # ── Void field on row 3 ───────────────────────────────────────────────────
    # Every corridor cell on row 3 except OPN and CLS is filled with a void rune.
    # % scans through voids (they are CORRIDOR cells) to find the matching bracket;
    # manual h/l are blocked (_ok returns False for void cells in the BFS and the
    # game engine kills the player on landing).
    for c in range(1, COLS - 1):
        if c == OPN or c == CLS:
            continue
        runes.append(RuneCluster(row=3, col=c, symbols=('○',), kind='void'))

    composite.runes = runes

    # ── Entry and exit ────────────────────────────────────────────────────────
    composite.entry    = _L11_ENTRY
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


# ── Level 10 constants ────────────────────────────────────────────────────────

_L10_TOTAL_ROWS = 11   # rows 0-10; passable rows 1-9
_L10_TOTAL_COLS = 52   # cols 0-51; passable cols 4-47
_L10_PASS_LEFT  = 4    # first passable column
_L10_PASS_RIGHT = 47   # last passable column
_L10_KS_COL     = 4    # column of the three keystones (= first passable col)
_L10_KS_ROWS    = (1, 5, 9)   # top / middle / bottom objective rows
_L10_ENTRY      = (5, 25)     # dead centre of room
_L10_EXIT_ROW   = 9
_L10_EXIT_COL   = 47          # rightmost passable col = first-non-blank by $


def _dijkstra_par_L10(composite, return_path: bool = False):
    """Minimum-keystroke Dijkstra for Level 10 — The Screen Vault.

    State = (row, col, mask) where mask is a 3-bit bitmask of which keystones
    have been collected (bit 0 = KS-top row 1, bit 1 = KS-mid row 5,
    bit 2 = KS-bot row 9).  Win when at exit_pos with mask == 0b111.

    Available motions:
      h j k l      — single step, 1 ks each
      {n}h/j/k/l   — count step, len(str(n))+1 ks
      H            — jump to prows[0] fnb col, 1 ks
      M            — jump to prows[len//2] fnb col, 1 ks
      L            — jump to prows[-1] fnb col, 1 ks
      G            — jump to exit_pos, 1 ks
      gg           — jump to entry, 2 ks (two characters)
      $            — rightmost passable col in row, 1 ks
      0            — leftmost passable col in row, 1 ks
      ^            — first non-blank col in row, 1 ks
      x            — collect keystone at current cell (mask |= bit), 1 ks
                     (only valid if a live keystone entity is at current position)
    """
    ROWS, COLS = composite.rows, composite.cols
    entry    = composite.entry
    exit_pos = composite.exit_pos

    def _ok(r, c):
        """Cell is passable and safe to land on (not a void rune)."""
        if not composite.is_passable(r, c):
            return False
        ru = composite.rune_at(r, c)
        return not (ru and ru.kind == 'void')

    # ── Screen-relative helpers ───────────────────────────────────────────────
    # Compute first-non-blank col for all passable rows (matches motion.py).
    _fnb: dict[int, int] = {}
    for _r in range(ROWS):
        _left = None
        for _c in range(COLS):
            if composite.is_passable(_r, _c):
                if _left is None:
                    _left = _c
                if composite.rune_at(_r, _c) is not None:
                    _fnb[_r] = _c
                    break
        else:
            if _left is not None and _r not in _fnb:
                _fnb[_r] = _left

    _prows = sorted(_fnb)
    if not _prows:
        if return_path:
            return None, ''
        return None

    _h_dest  = (_prows[0],               _fnb[_prows[0]])
    _m_dest  = (_prows[len(_prows) // 2], _fnb[_prows[len(_prows) // 2]])
    _l_dest  = (_prows[-1],              _fnb[_prows[-1]])

    # ── Keystone positions → mask bits ────────────────────────────────────────
    _ks_map: dict[tuple, int] = {}   # (row, col) → bit index
    for _bit, _ent in enumerate(
        e for e in composite.entities if e.kind == 'keystone'
    ):
        _ks_map[(_ent.row, _ent.col)] = _bit

    FULL_MASK = (1 << len(_ks_map)) - 1  # all bits set = 0b111

    # ── Dijkstra ──────────────────────────────────────────────────────────────
    INF   = float('inf')
    start = (*entry, 0)          # (row, col, mask)
    dist  = {start: 0}
    prev  = {start: None}
    heap  = [(0, start)]

    while heap:
        cost, state = heapq.heappop(heap)
        r, c, mask = state
        if (r, c) == exit_pos and mask == FULL_MASK:
            if return_path:
                return cost, _join_path(prev, state, merge_single=False)
            return cost
        if cost > dist.get(state, INF):
            continue

        def _push(nb_rc, mc=1, lbl='', nb_mask=None):
            if nb_rc is None:
                return
            nr, nc = nb_rc
            if not _ok(nr, nc):
                return
            nmask = nb_mask if nb_mask is not None else mask
            nb    = (nr, nc, nmask)
            g     = cost + mc
            if g < dist.get(nb, INF):
                dist[nb] = g
                prev[nb] = (state, lbl)
                heapq.heappush(heap, (g, nb))

        max_n = max(ROWS, COLS)

        # ── hjkl (count) ──────────────────────────────────────────────────────
        for dr, dc, key in ((1,0,'j'),(-1,0,'k'),(0,1,'l'),(0,-1,'h')):
            for n in range(1, max_n + 1):
                nr2, nc2 = r + dr * n, c + dc * n
                if not _ok(nr2, nc2):
                    break
                mc2  = 1 if n == 1 else len(str(n)) + 1
                lbl2 = key if n == 1 else f'{n}{key}'
                _push((nr2, nc2), mc2, lbl2)

        # ── $ 0 ^ ─────────────────────────────────────────────────────────────
        bc = None
        for cc in range(c + 1, COLS):
            if not composite.is_passable(r, cc):
                break
            bc = cc
        if bc is not None and _ok(r, bc):
            _push((r, bc), 1, '$')

        lc = c
        for cc in range(c - 1, -1, -1):
            if not composite.is_passable(r, cc):
                break
            lc = cc
        if lc < c and _ok(r, lc):
            _push((r, lc), 1, '0')

        if _fnb.get(r) is not None and _ok(r, _fnb[r]):
            _push((r, _fnb[r]), 1, '^')

        # ── H M L ─────────────────────────────────────────────────────────────
        if _ok(*_h_dest):
            _push(_h_dest, 1, 'H')
        if _ok(*_m_dest):
            _push(_m_dest, 1, 'M')
        if _ok(*_l_dest):
            _push(_l_dest, 1, 'L')

        # ── G (exit jump) ─────────────────────────────────────────────────────
        if exit_pos and _ok(*exit_pos):
            _push(exit_pos, 1, 'G')

        # ── gg (entry jump, 2 ks) ─────────────────────────────────────────────
        if _ok(*entry):
            _push(entry, 2, 'gg')

        # ── x (collect keystone) ─────────────────────────────────────────────
        bit = _ks_map.get((r, c))
        if bit is not None and not (mask >> bit & 1):
            new_mask = mask | (1 << bit)
            nb_state = (r, c, new_mask)
            g = cost + 1
            if g < dist.get(nb_state, INF):
                dist[nb_state] = g
                prev[nb_state] = (state, 'x')
                heapq.heappush(heap, (g, nb_state))

    if return_path:
        return None, ''
    return None


def build_dungeon_10(seed: int) -> Dungeon:
    """Level 10 — H/M/L: The Screen Vault.

    A single open rectangular room (rows 1-9, cols 4-47, 11×52 total).
    Three keystones mark the top, middle, and bottom rows:

      KS-top (row 1, col 4)  — H (1 ks) lands here; 4k + ^ costs 3 ks.
      KS-mid (row 5, col 4)  — M (1 ks) is the only 1-ks row-5 jump.
      KS-bot (row 9, col 4)  — L (1 ks); also reachable by 4j (2 ks).

    Entry: (5, 25) — dead centre.
    Exit:  (9, 47) — bottom-right corner.

    All three keystones must be collected (x) before the exit unlocks.
    Decorative rune clusters fill each row between cols 6-45.

    Optimal path (par = 7 keystrokes):
      H x M x L x $
      H(1) → KS-top(1,4) → x(1) → M(1) → KS-mid(5,4) → x(1) → L(1) →
      KS-bot(9,4) → x(1) → $(1) → exit(9,47)

    H is required for par: H(1) beats 4k^(3) to reach row-1 fnb.
    M is required for par: M(1) beats 4j(2) for the row-1→row-5 jump.
    L is demonstrated but not gated: 4j (2 ks) replaces L at cost+1,
    still within budget = ceil(7 × 1.4) = 10.
    """
    dungeon   = Dungeon(name='The Screen Vault', seed=seed)
    ROWS, COLS = _L10_TOTAL_ROWS, _L10_TOTAL_COLS

    cells = [[CellType.WALL] * COLS for _ in range(ROWS)]
    composite = Room(rows=ROWS, cols=COLS, room_type=RoomType.ENTRY)
    composite.cells = cells
    composite.seed  = seed

    # ── Carve the single open room ────────────────────────────────────────────
    for r in range(1, 10):           # rows 1-9
        for c in range(_L10_PASS_LEFT, _L10_PASS_RIGHT + 1):   # cols 4-47
            cells[r][c] = CellType.CORRIDOR

    # ── Keystone entities + anchor runes ─────────────────────────────────────
    # One-char rune cluster at each keystone col so fnb(row) == _L10_KS_COL.
    # The rune symbols are thematic glyphs: ancient / verdant / ember.
    _load_vocab_tables()
    rng     = random.Random(seed)
    _kinds3 = ('ancient', 'verdant', 'ember')

    _KS_SYMBOLS = ('∘', '·', '⊙')   # one glyph per keystone row
    for idx, ks_row in enumerate(_L10_KS_ROWS):
        composite.entities.append(
            Entity(kind='keystone', row=ks_row, col=_L10_KS_COL)
        )
        # Anchor rune at the keystone cell so H/M/L land exactly here.
        composite.runes.append(
            RuneCluster(row=ks_row, col=_L10_KS_COL,
                        symbols=(_KS_SYMBOLS[idx],), kind=_kinds3[idx])
        )

    # ── Decorative rune clusters ──────────────────────────────────────────────
    # Scatter seed-varying mixed-vocab clusters on all 9 rows, cols 6-45.
    # Skip col 4 (anchor) and col 5 (gap after anchor).
    _blocked: set = set()
    for ks_row in _L10_KS_ROWS:
        _blocked.add((ks_row, _L10_KS_COL))   # anchor col

    for row in range(1, 10):
        c = _L10_PASS_LEFT + 2   # start at col 6
        while c <= 45:
            if (row, c) in _blocked:
                c += 1
                continue
            # Pick word length fitting in remaining space
            max_len = min(6, 46 - c)
            if max_len < 2:
                break
            wlen = rng.randint(2, max_len)
            words = (_VOCAB_MIXED_BY_LEN or {}).get(wlen, [])
            if not words:
                words = (_VOCAB_PLAIN_BY_LEN or {}).get(wlen, [])
            if not words:
                c += 2
                continue
            word  = rng.choice(words)
            kind  = rng.choice(_kinds3)
            composite.runes.append(
                RuneCluster(row=row, col=c, symbols=tuple(word), kind=kind)
            )
            # Mark cells occupied
            for i in range(len(word)):
                _blocked.add((row, c + i))
            c += len(word) + rng.randint(1, 3)   # gap between clusters

    # ── Entry / exit ──────────────────────────────────────────────────────────
    composite.entry    = _L10_ENTRY
    composite.exit_pos = (_L10_EXIT_ROW, _L10_EXIT_COL)
    composite.entities.append(Entity(kind='exit', row=_L10_EXIT_ROW, col=_L10_EXIT_COL))

    composite.rebuild_indexes()

    par, path = _dijkstra_par_L10(composite, return_path=True)
    if par is None:
        par, path = 7, 'H x M x L x $'
    composite.par    = par
    composite.budget = math.ceil(par * 1.4)
    composite.answer = path

    dungeon.rooms        = [composite]
    dungeon.current_room = 0
    return dungeon


# ── Level 12 layout constants ─────────────────────────────────────────────────
# Room: 22 rows × 62 cols (rows 0–21, cols 0–61).
# All interior cells (rows 0–20, cols 1–60) are CORRIDOR unless overridden.
#
# Paragraph section (rows 0–19):
#   Para 1:  rows 0–2  — seed-varying non-void rune clusters
#   Void:    rows 3–8  — full-width void rune barriers (block j/k counting)
#   Blank:   row  9    — no rune clusters at all  (paragraph divider)
#   Para 2:  rows 10–11 — seed-varying non-void rune clusters
#   Void:    rows 12–18 — full-width void rune barriers
#   Blank:   row  19   — no rune clusters at all  (paragraph divider)
#
# Sentence section (row 20):
#   S1 corridor: cols  1–10   CORRIDOR  (sentence-1 rune at cols 2–10)
#   Wall gap:    cols 11–22   WALL
#   S2 corridor: cols 23–36   CORRIDOR  (sentence-2 rune at cols 23–36)
#   Wall gap:    cols 37–48   WALL
#   S3 corridor: cols 49–60   CORRIDOR  (sentence-3 rune at cols 49–59, exit at 49)
#
# Entry: (0, 1).  Exit entity: (20, 49).
#
# Optimal route: }} j 3)   = 1+1+1+2 = 5 ks
#   }}  — paragraph jumps: row 0 → blank row 9 → blank row 19
#   j   — step down to sentence row 20
#   3)  — sentence count-jump: col 1 → S1 col 2 → S2 col 23 → S3/exit col 49
#
# Without {/}: void barriers in rows 3–8 block all j/k paths.
#              Player trapped in rows 0–2.  Cost = infinity >> budget.

_L13_ROWS        = 13
_L13_COLS        = 62
_L13_ENTRY       = (0, 1)
_L13_EXIT        = (11, 55)

_L13_PARA1_ROWS  = (0, 1, 2)
_L13_VOID_ROWS_A = tuple(range(3, 9))    # rows 3-8
_L13_BLANK_ROW_1 = 9
_L13_PARA2_ROWS  = (10, 11)


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
    """Minimum-keystroke Dijkstra for Levels 13–14 — Paragraph and Sentence Jumps.

    Available motions: count hjkl, $, 0, ^, w b e, W B E, ge gE,
                       } { (paragraph), ) ( (sentence, with count).

    disable_brace=True  excludes } and { from the search.
    disable_paren=True  excludes ) and ( from the search.
    """
    ROWS, COLS = composite.rows, composite.cols
    entry = composite.entry
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

    def _char_at(r, c):
        ru = composite.rune_at(r, c)
        if ru is None or ru.kind == 'void':
            return None
        return ru.symbols[c - ru.col]

    def _is_wc(ch):
        return (ch.isalpha() or ch.isdigit() or ch == '_'
                or unicodedata.category(ch) == 'So')

    # ── word motions ─────────────────────────────────────────────────────────

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
            prev_c = c - 1
        else:
            prev_c = c - 1
        while (prev_c >= 0 and composite.is_passable(r, prev_c)
               and _char_at(r, prev_c) is None):
            prev_c -= 1
        if (prev_c >= 0 and composite.is_passable(r, prev_c)
                and _char_at(r, prev_c) is not None):
            ch2 = _char_at(r, prev_c)
            t2  = _is_wc(ch2)
            rs2 = prev_c
            for sc2 in range(prev_c - 1, -1, -1):
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
        while (scan < COLS and composite.is_passable(r, scan)
               and _char_at(r, scan) is None):
            scan += 1
        if (scan < COLS and composite.is_passable(r, scan)
                and _char_at(r, scan) is not None):
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
        nc = c - 1
        while nc >= 0:
            if not composite.is_passable(r, nc):
                break
            ru = composite.rune_at(r, nc)
            if ru and ru.kind != 'void':
                end_col = ru.col + len(ru.symbols) - 1
                if end_col < c:
                    return (r, end_col)
                nc = ru.col - 1
                continue
            nc -= 1
        return None

    def _gE(r, c):
        nc = c - 1
        while nc >= 0:
            if not composite.is_passable(r, nc):
                break
            ru = composite.rune_at(r, nc)
            if ru and ru.kind != 'void':
                end  = ru.col + len(ru.symbols) - 1
                cc   = end + 1
                while cc < COLS and composite.is_passable(r, cc):
                    r2 = composite.rune_at(r, cc)
                    if r2 and r2.kind != 'void':
                        end = r2.col + len(r2.symbols) - 1
                        cc  = end + 1
                    else:
                        break
                if end < c:
                    return (r, end)
                nc = ru.col - 1
                continue
            nc -= 1
        return None

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
            ws = _word_start(r, c)
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

    # ── paragraph jumps ───────────────────────────────────────────────────────

    def _row_blank(row):
        has_pass = any(composite.is_passable(row, cc) for cc in range(COLS))
        has_rune = any(composite.rune_at(row, cc) is not None
                       for cc in range(COLS))
        return has_pass and not has_rune

    def _leftmost_pass(row):
        for cc in range(COLS):
            if composite.is_passable(row, cc):
                return cc
        return None

    def _para_fwd(r):
        for nr in range(r + 1, ROWS):
            if _row_blank(nr):
                lp = _leftmost_pass(nr)
                if lp is not None and _ok(nr, lp):
                    return (nr, lp)
        prows = [rr for rr in range(ROWS) if _leftmost_pass(rr) is not None]
        if prows:
            tr = prows[-1]
            lp = _leftmost_pass(tr)
            if lp is not None and _ok(tr, lp) and (tr, lp) != (r, _leftmost_pass(r)):
                return (tr, lp)
        return None

    def _para_bwd(r):
        for nr in range(r - 1, -1, -1):
            if _row_blank(nr):
                lp = _leftmost_pass(nr)
                if lp is not None and _ok(nr, lp):
                    return (nr, lp)
        prows = [rr for rr in range(ROWS) if _leftmost_pass(rr) is not None]
        if prows:
            tr = prows[0]
            lp = _leftmost_pass(tr)
            if lp is not None and _ok(tr, lp) and (tr, lp) != (r, _leftmost_pass(r)):
                return (tr, lp)
        return None

    # ── sentence starts ───────────────────────────────────────────────────────

    def _sent_starts(row):
        starts = []
        pending = True
        for cc in range(COLS):
            ru = composite.rune_at(row, cc)
            if ru is None or ru.kind == 'void':
                continue
            if pending:
                starts.append(cc)
                pending = False
            if ru.symbols[cc - ru.col] in '.!?':
                pending = True
        return starts

    # ── main search ───────────────────────────────────────────────────────────

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

        # count j/k
        for dr, key in ((1, 'j'), (-1, 'k')):
            for n in range(1, max_n + 1):
                nr2 = r + dr * n
                if nr2 < 0 or nr2 >= ROWS or not _ok(nr2, c):
                    break
                mc2  = 1 if n == 1 else len(str(n)) + 1
                lbl2 = key if n == 1 else f'{n}{key}'
                _push((nr2, c), mc2, lbl2)

        # count h/l
        for dc, key in ((1, 'l'), (-1, 'h')):
            for n in range(1, max_n + 1):
                nc2 = c + dc * n
                if nc2 < 0 or nc2 >= COLS or not _ok(r, nc2):
                    break
                mc2  = 1 if n == 1 else len(str(n)) + 1
                lbl2 = key if n == 1 else f'{n}{key}'
                _push((r, nc2), mc2, lbl2)

        # $: rightmost contiguous passable non-void col
        best_col = None
        for cc in range(c + 1, COLS):
            if not composite.is_passable(r, cc):
                break
            best_col = cc
        if best_col is not None and _ok(r, best_col):
            _push((r, best_col), 1, '$')

        # 0: leftmost contiguous passable col
        left_col = c
        for cc in range(c - 1, -1, -1):
            if not composite.is_passable(r, cc):
                break
            left_col = cc
        if left_col < c and _ok(r, left_col):
            _push((r, left_col), 1, '0')

        # ^: first rune in passability-bounded range
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
                break

        # count W/B/E
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

        # count w/b/e
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

        # count ge/gE
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

        # } / { paragraph jumps (1 ks each)
        if not disable_brace:
            nb_fwd = _para_fwd(r)
            if nb_fwd is not None and nb_fwd != (r, c):
                _push(nb_fwd, 1, '}')
            nb_bwd = _para_bwd(r)
            if nb_bwd is not None and nb_bwd != (r, c):
                _push(nb_bwd, 1, '{')

        # ) / ( sentence jumps (row-scoped, chained count)
        if not disable_paren:
            pos2 = (r, c)
            for n in range(1, max_n):
                pr, pc = pos2
                nxt_cols = [s for s in _sent_starts(pr) if s > pc]
                if not nxt_cols:
                    break
                nc2  = nxt_cols[0]
                mc2  = 1 if n == 1 else len(str(n)) + 1
                lbl2 = ')' if n == 1 else f'{n})'
                _push((pr, nc2), mc2, lbl2)
                pos2 = (pr, nc2)

            pos2 = (r, c)
            for n in range(1, max_n):
                pr, pc = pos2
                prev_cols = [s for s in _sent_starts(pr) if s < pc]
                if not prev_cols:
                    break
                nc2  = prev_cols[-1]
                mc2  = 1 if n == 1 else len(str(n)) + 1
                lbl2 = '(' if n == 1 else f'{n}('
                _push((pr, nc2), mc2, lbl2)
                pos2 = (pr, nc2)

    if return_path:
        return None, ''
    return None


# ── Level G/gg (id=85): The File Vaults ────────────────────────────────────
# 15-row × 58-col dungeon teaching G, {n}G, and gg.
#
# Layout:
#   Rows 0-3   : top section (cols 1-56), entry=(0,1)
#   Row  4     : wall except (4,26-28); (4,27) = locked_door, (4,26) and (4,28)
#                are corridor — the only crossing between top and bottom sections
#   Rows 5-14  : bottom section (cols 1-56), exit_pos=(14,55) with keystone
#
# Keystones (must all be collected before exit completes):
#   KS1 at (14, 55) — collected via G then x; {n}G unreachable without G first
#   KS2 at (4, 28)  — collected by navigating from (4,55) via 27h then x
#   Exit at (0, 2)  — step on to complete level after both keystones collected
#
# Optimal path (par = 11):
#   G(1) x(1) 5G(2) 27h(3) x(1) gg(2) l(1)
#   = 11 ks
#
# Key savings:
#   G beats 14j 54l (1 vs 6 ks)  — strictly necessary
#   5G beats 10k  (2 vs 3 ks)    — strictly cheaper from row 14
#   gg beats 4k 26h (2+1=3 vs 5 ks) — strictly cheaper to reach exit near entry
#
# All-j/k path: 14j 54l x 10k 27h x k 3k 26h = ~20 ks >> budget
#
_LGG_TOTAL_ROWS  = 15
_LGG_TOTAL_COLS  = 58
_LGG_ENTRY       = (0, 1)
_LGG_EXIT_POS    = (14, 55)   # where G teleports; has KS1
_LGG_EXIT_ENTITY = (0, 2)     # where the level completes
_LGG_KS1         = (14, 55)   # keystone 1 (same as exit_pos)
_LGG_KS2         = (4, 28)    # keystone 2 (inside wall gap, right of door)
_LGG_DOOR_COL    = 27         # locked_door entity at row 4 col 27
_LGG_WALL_ROW    = 4          # the barrier row
_LGG_GAP_COLS    = (26, 27, 28)  # corridor cells in the wall row


def _dijkstra_par_LGG(composite, return_path: bool = False):
    """Minimum-keystroke Dijkstra for Level G/gg — The File Vaults.

    State = (row, col, ks_collected) where ks_collected is a frozenset of
    collected keystone positions.  Actions:
      hjkl (1 ks), count-hjkl (len(str(n))+1 ks)
      G  (1 ks): teleport to exit_pos (_LGG_EXIT_POS)
      gg (2 ks): teleport to entry (_LGG_ENTRY)
      {n}G (len(str(n))+1 ks): teleport to row n-1 at current col; if that
           cell is in the wall row, snap to nearest passable col in the row.
      x  (1 ks): collect keystone at current cell (adds to ks_collected)
      p/P (1 ks): open locked_door to right/left; costs 1 ks if door present
    Goal: state = (_LGG_EXIT_ENTITY row/col, {KS1, KS2})
    """
    ROWS, COLS = composite.rows, composite.cols
    entry    = composite.entry
    exit_pos = composite.exit_pos
    ks1_pos  = _LGG_KS1
    ks2_pos  = _LGG_KS2
    door_pos = (_LGG_WALL_ROW, _LGG_DOOR_COL)
    goal_pos = _LGG_EXIT_ENTITY
    all_ks   = frozenset([ks1_pos, ks2_pos])

    def _ok(r, c, door_open: bool = False) -> bool:
        if r < 0 or r >= ROWS or c < 0 or c >= COLS:
            return False
        ct = composite.cells[r][c]
        if ct not in (CellType.CORRIDOR, CellType.FLOOR):
            return False
        if (r, c) == door_pos and not door_open:
            return False  # locked_door blocks
        return True

    def _snap_col(r, c, prefer_right: bool = True) -> int:
        """Find nearest passable col in row r around col c (door always open here)."""
        if _ok(r, c, door_open=True):
            return c
        # scan left and right
        for delta in range(1, COLS):
            rc = c + delta
            lc = c - delta
            if prefer_right and 0 <= rc < COLS and composite.cells[r][rc] in (CellType.CORRIDOR, CellType.FLOOR):
                return rc
            if 0 <= lc < COLS and composite.cells[r][lc] in (CellType.CORRIDOR, CellType.FLOOR):
                return lc
            if not prefer_right and 0 <= rc < COLS and composite.cells[r][rc] in (CellType.CORRIDOR, CellType.FLOOR):
                return rc
        return c

    # State = (row, col, ks_frozenset, door_open_bool)
    start = (entry[0], entry[1], frozenset(), False)
    goal_state_prefix = (goal_pos[0], goal_pos[1])

    dist = {start: 0}
    prev = {start: None}
    heap = [(0, start)]
    max_n = max(ROWS, COLS)

    while heap:
        cost, state = heapq.heappop(heap)
        r, c, ks, door_open = state

        if (r, c) == goal_state_prefix and ks == all_ks:
            if return_path:
                return cost, _join_path(prev, state, merge_single=False)
            return cost

        if cost > dist.get(state, float('inf')):
            continue

        def _push(nb_state, mc, lbl):
            nr, nc, nks, ndoor = nb_state
            if not _ok(nr, nc, ndoor):
                return
            g = cost + mc
            if g < dist.get(nb_state, float('inf')):
                dist[nb_state] = g
                prev[nb_state] = (state, lbl)
                heapq.heappush(heap, (g, nb_state))

        # x: collect keystone at current cell
        if (r, c) in (ks1_pos, ks2_pos) and (r, c) not in ks:
            new_ks = ks | frozenset([(r, c)])
            _push((r, c, new_ks, door_open), 1, 'x')

        # p: open locked_door to the right (requires floor_key = KS1 collected)
        right_cell = (r, c + 1)
        if right_cell == door_pos and not door_open and ks1_pos in ks:
            _push((r, c, ks, True), 1, 'p')

        # P: open locked_door to the left
        left_cell = (r, c - 1)
        if left_cell == door_pos and not door_open and ks1_pos in ks:
            _push((r, c, ks, True), 1, 'P')

        # G: teleport to exit_pos (1 ks)
        er, ec = exit_pos
        if _ok(er, ec, door_open):
            _push((er, ec, ks, door_open), 1, 'G')

        # gg: teleport to entry (2 ks)
        tr, tc = entry
        if _ok(tr, tc, door_open):
            _push((tr, tc, ks, door_open), 2, 'gg')

        # {n}G: teleport to row n-1 (count n ≥ 2); preserve col if passable, else snap
        for n in range(2, ROWS + 1):
            tr2 = n - 1
            if tr2 < 0 or tr2 >= ROWS:
                break
            tc2 = c
            if not _ok(tr2, tc2, door_open):
                tc2 = _snap_col(tr2, c)
            if _ok(tr2, tc2, door_open) and (tr2, tc2) != (r, c):
                mc = len(str(n)) + 1
                lbl = f'{n}G'
                g = cost + mc
                nb = (tr2, tc2, ks, door_open)
                if g < dist.get(nb, float('inf')):
                    dist[nb] = g
                    prev[nb] = (state, lbl)
                    heapq.heappush(heap, (g, nb))

        # hjkl and count-hjkl
        for dr, dc, key in ((0,-1,'h'),(0,1,'l'),(1,0,'j'),(-1,0,'k')):
            for n in range(1, max_n + 1):
                nr2 = r + dr * n
                nc2 = c + dc * n
                if nr2 < 0 or nr2 >= ROWS or nc2 < 0 or nc2 >= COLS:
                    break
                if not _ok(nr2, nc2, door_open):
                    break
                mc2  = 1 if n == 1 else len(str(n)) + 1
                lbl2 = key if n == 1 else f'{n}{key}'
                g2   = cost + mc2
                nb2  = (nr2, nc2, ks, door_open)
                if g2 < dist.get(nb2, float('inf')):
                    dist[nb2] = g2
                    prev[nb2] = (state, lbl2)
                    heapq.heappush(heap, (g2, nb2))

    if return_path:
        # Find best goal state (any ks collection)
        best = None
        for state2, d2 in dist.items():
            r2, c2, ks2, _ = state2
            if (r2, c2) == goal_state_prefix and ks2 == all_ks:
                if best is None or d2 < best[0]:
                    best = (d2, state2)
        if best:
            return best[0], _join_path(prev, best[1], merge_single=False)
        return None, ''
    return None


def build_dungeon_9(seed: int) -> 'Dungeon':
    """Level id=85 — G gg {n}G: The File Vaults.

    15-row × 58-col dungeon.  A horizontal wall at row 4 separates the top
    section (rows 0-3) from the bottom section (rows 5-14).  The only crossing
    is through the gap at cols 26-28 of row 4, which holds a locked_door entity
    at (4,27).

    Two keystones must be collected before the exit completes:
      KS1 at (14,55): collected by G then x  (G teleports to exit_pos=(14,55))
      KS2 at (4,28):  collected by navigating to the wall gap

    Optimal path (par = 11):
      G x 5G 27h x gg l
      G(1) teleports to (14,55) → x(1) collects KS1
      5G(2) teleports to (4,55)  → 27h(3) navigates to (4,28)
      x(1) collects KS2          → gg(2) teleports to (0,1)
      l(1) steps to exit at (0,2)

    Teaching checkpoints:
      G beats  14j+54l (1 vs 6 ks)     — always strictly cheaper
      5G beats 10k     (2 vs 3 ks)     — strictly cheaper from row 14
      gg beats 4k+26h  (3 vs 5 ks)     — strictly cheaper to exit near entry
    """
    dungeon  = Dungeon(name='The File Vaults', seed=seed)
    ROWS, COLS = _LGG_TOTAL_ROWS, _LGG_TOTAL_COLS

    cells = [[CellType.WALL] * COLS for _ in range(ROWS)]
    composite = Room(rows=ROWS, cols=COLS, room_type=RoomType.ENTRY)
    composite.cells = cells
    composite.seed  = seed

    # ── Carve top section (rows 0-3) ─────────────────────────────────────────
    for r in range(0, _LGG_WALL_ROW):
        for c in range(1, COLS - 1):
            cells[r][c] = CellType.CORRIDOR

    # ── Carve wall row 4 with gap ─────────────────────────────────────────────
    for c in _LGG_GAP_COLS:
        cells[_LGG_WALL_ROW][c] = CellType.CORRIDOR

    # ── Carve bottom section (rows 5-14) ─────────────────────────────────────
    for r in range(_LGG_WALL_ROW + 1, ROWS):
        for c in range(1, COLS - 1):
            cells[r][c] = CellType.CORRIDOR

    # ── Entry, exit, keystones ────────────────────────────────────────────────
    composite.entry    = _LGG_ENTRY
    composite.exit_pos = _LGG_EXIT_POS

    entities = [
        # KS1 at exit_pos (bottom right): collected via G then x
        Entity(kind='keystone',    row=_LGG_KS1[0],  col=_LGG_KS1[1]),
        # KS2 at gap right (wall row): collected by navigating to door gap
        Entity(kind='keystone',    row=_LGG_KS2[0],  col=_LGG_KS2[1]),
        # locked_door at gap centre: blocks crossing until key collected
        # (opened by p from (4,28) or P from (4,26); kills via _kill_door_group)
        Entity(kind='locked_door', row=_LGG_WALL_ROW, col=_LGG_DOOR_COL),
        # exit entity at top section
        Entity(kind='exit',        row=_LGG_EXIT_ENTITY[0], col=_LGG_EXIT_ENTITY[1]),
    ]
    composite.entities = entities

    # No seed-varying runes needed for this level
    composite.runes = []

    composite.rebuild_indexes()

    # ── Fog unreachable cells (top section initially hidden) ──────────────────
    _fog_unreachable(composite, composite.entry[0], composite.entry[1])

    # ── Compute par via Dijkstra ──────────────────────────────────────────────
    par, path = _dijkstra_par_LGG(composite, return_path=True)
    if par is None:
        par, path = 11, 'G x 5G 27h x gg l'
    composite.par    = par
    composite.budget = math.ceil(par * 1.4)
    composite.answer = path

    dungeon.rooms        = [composite]
    dungeon.current_room = 0
    return dungeon


def build_dungeon_13(seed: int) -> 'Dungeon':
    """Level 13 — Paragraph Jumps: The Void Rift.

    Semi-fixed layout: 13 rows × 62 cols.

    Para 1  rows 0–2  — seed-varying non-void rune clusters.
    Void barrier rows 3–8  — full-width void clusters block j/k counting.
    Blank row 9  — no runes; target of } jump.
    Para 2  rows 10–11 — seed-varying non-void rune clusters.
    Exit at (11, 55) — end of Para 2.

    Without {/}: void barriers trap player in rows 0–2.  Cost = infinity.
    """
    dungeon   = Dungeon(name='The Void Rift', seed=seed)
    ROWS, COLS = _L13_ROWS, _L13_COLS

    cells = [[CellType.WALL] * COLS for _ in range(ROWS)]
    composite = Room(rows=ROWS, cols=COLS, room_type=RoomType.ENTRY)
    composite.cells = cells
    composite.seed  = seed

    # ── Carve interior corridor (rows 0–11, cols 1–60) ───────────────────────
    for r in range(0, ROWS - 1):
        for c in range(1, COLS - 1):
            cells[r][c] = CellType.CORRIDOR

    # ── Void barrier rows (full-width, deterministic) ─────────────────────────
    runes: list = []
    for r in _L13_VOID_ROWS_A:
        runes.append(RuneCluster(row=r, col=1,
                                 symbols=('○',) * (COLS - 2),
                                 kind='void'))

    # ── Seed-varying decorative rune clusters (Para 1 and Para 2) ─────────────
    _load_vocab_tables()
    plain = _VOCAB_PLAIN_BY_LEN
    rng   = random.Random(seed)

    def _fill_para_row(row):
        c = 2
        while c <= 58:
            if rng.random() < 0.40:
                kind    = rng.choice(_WORD_RUNE_KINDS)
                max_len = min(6, 58 - c + 1)
                length  = rng.randint(2, max(2, max_len))
                word    = rng.choice(plain.get(length) or plain[3])
                syms    = tuple(word)
                w = len(syms)
                if c + w - 1 <= 58:
                    runes.append(RuneCluster(row=row, col=c, symbols=syms, kind=kind))
                    c += w + rng.randint(2, 3)
                    continue
            c += 1

    for r in _L13_PARA1_ROWS:
        _fill_para_row(r)
    for r in _L13_PARA2_ROWS:
        _fill_para_row(r)

    composite.runes = runes

    # ── Entry and exit ─────────────────────────────────────────────────────────
    composite.entry    = _L13_ENTRY
    composite.exit_pos = _L13_EXIT
    composite.entities = [Entity(kind='exit', row=_L13_EXIT[0], col=_L13_EXIT[1])]

    composite.rebuild_indexes()

    par, path = _dijkstra_par_L13(composite, return_path=True, disable_paren=True)
    if par is None:
        par, path = 3, '} j $'
    composite.par    = par
    composite.budget = math.ceil(par * 1.4)
    composite.answer = path

    dungeon.rooms        = [composite]
    dungeon.current_room = 0
    return dungeon


def build_dungeon_14(seed: int) -> 'Dungeon':
    """Level 14 — Sentence Jumps: The Sentence Corridor.

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
    composite.entry    = _L14_ENTRY
    composite.exit_pos = _L14_EXIT
    composite.entities = [Entity(kind='exit', row=_L14_EXIT[0], col=_L14_EXIT[1])]

    composite.rebuild_indexes()

    par, path = _dijkstra_par_L13(composite, return_path=True, disable_brace=True)
    if par is None:
        par, path = 2, '3)'
    composite.par    = par
    composite.budget = math.ceil(par * 1.4)
    composite.answer = path

    dungeon.rooms        = [composite]
    dungeon.current_room = 0
    return dungeon
