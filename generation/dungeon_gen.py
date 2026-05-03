"""Assemble a dungeon from rooms joined by corridors into a single grid."""
from __future__ import annotations
import heapq, math, random
from collections import deque
from engine.world import Dungeon, Room, RoomType, CellType, RuneCluster, Entity
from generation.room_gen import make_room

# ── Level plans ───────────────────────────────────────────────────────────────

# Level 0: Entry → Puzzle → Exit  (hjkl only)
LEVEL_0_PLAN = [
    (RoomType.ENTRY,  10, 18),
    (RoomType.PUZZLE, 10, 20),
    (RoomType.EXIT,   10, 16),
]

_RUNE_KINDS      = ['ancient', 'verdant', 'void', 'ember']
_WORD_RUNE_KINDS = ['ancient', 'verdant', 'ember']   # non-void only
_RUNE_SYMS  = {
    'ancient': ('∘', '∘', '∘'),
    'verdant': ('·', '·', '·'),
    'void':    ('○', '○'),
    'ember':   ('◦', '◦', '◦', '◦'),
}

# ── Level 3 layout constants ──────────────────────────────────────────────────
_L3_CORR_TOP_ROWS = (1, 4, 7, 10, 13)  # top row of each of the 5 corridors
_L3_TOTAL_ROWS    = 16                  # rows 0-15
_L3_TOTAL_COLS    = 48                  # cols 0-47
_L3_CORR_LEFT     = 1
_L3_CORR_RIGHT    = 46

def _place_runes_in_room(composite, rng, col_offset, room_rows, room_cols,
                          total_rows, density):
    """Scatter rune clusters inside one room of the composite grid."""
    row_offset = (total_rows - room_rows) // 2
    for r in range(row_offset + 1, row_offset + room_rows - 1):
        c = col_offset + 2
        while c < col_offset + room_cols - 2:
            if rng.random() < density:
                kind = rng.choice(_RUNE_KINDS)
                syms = _RUNE_SYMS[kind]
                width = len(syms)
                if c + width <= col_offset + room_cols - 2:
                    composite.runes.append(
                        RuneCluster(row=r, col=c, symbols=syms, kind=kind))
                    c += width + rng.randint(1, 3)
                    continue
            c += 1


def _bfs_par(composite):
    """Shortest path entry→exit treating void rune cells as impassable.
    Returns the keystroke count, or None if the exit is unreachable."""
    void_cells = {
        (ru.row, ru.col + i)
        for ru in composite.runes if ru.kind == 'void'
        for i in range(len(ru.symbols))
    }
    entry = composite.entry
    goal  = composite.exit_pos
    dist  = {entry: 0}
    q     = deque([entry])
    while q:
        r, c = q.popleft()
        if (r, c) == goal:
            return dist[goal]
        for dr, dc in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            nb = (r + dr, c + dc)
            if nb not in dist and composite.is_passable(*nb) and nb not in void_cells:
                dist[nb] = dist[(r, c)] + 1
                q.append(nb)
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


def _dijkstra_par_level2(composite, door_cols: list) -> int | None:
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
    heap  = [(0, start)]

    while heap:
        cost, (r, c, closed) = heapq.heappop(heap)
        if (r, c) == goal:
            return cost
        if cost > dist.get((r, c, closed), float('inf')):
            continue

        def push(nr, nc, nc2, mc):
            ns = (nr, nc, nc2)
            g  = cost + mc
            if g < dist.get(ns, float('inf')):
                dist[ns] = g
                heapq.heappush(heap, (g, ns))

        # count h/j/k/l — stop at wall or fog
        for dr, dc in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            for step in range(1, max_n + 1):
                nr, nc = r + dr * step, c + dc * step
                if not composite.is_passable(nr, nc) or fog_blocks_col(nc, closed):
                    break
                push(nr, nc, closed, 1 if step == 1 else len(str(step)) + 1)

        # $ — rightward to nearest wall/fog
        best = None
        for nc in range(c + 1, composite.cols):
            if not composite.is_passable(r, nc) or fog_blocks_col(nc, closed):
                break
            best = nc
        if best is not None:
            push(r, best, closed, 1)

        # 0 — leftward to nearest wall
        left = c
        for nc in range(c - 1, -1, -1):
            if not composite.is_passable(r, nc):
                break
            left = nc
        if left != c:
            push(r, left, closed, 1)

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
            push(r, tgt, closed, 1)

        # x — open door at current cell (player stays put)
        for i in range(n):
            if (closed >> i) & 1 and (r, c) in trigger[i]:
                push(r, c, closed ^ (1 << i), 1)

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

        par = _bfs_par(composite)
        if par is not None:
            break
    else:
        par = 100  # should never happen at these densities

    # Budget: ceil(par × 1.4) per spec formula.
    composite.par    = par
    composite.budget = math.ceil(par * 1.4)

    dungeon.rooms = [composite]
    dungeon.current_room = 0
    return dungeon


# Level 1: Entry → Puzzle → Exit  (hjkl + ^ $ 0  + :w :q)
LEVEL_1_PLAN = [
    (RoomType.ENTRY,  8, 14),
    (RoomType.PUZZLE, 8, 60),
    (RoomType.EXIT,   10, 14),
]


def _bfs_par_line(composite) -> int | None:
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
    q    = deque([entry])
    while q:
        r, c = q.popleft()
        if (r, c) == goal:
            return dist[goal]
        d = dist[(r, c)]
        for dr, dc in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            nb = (r + dr, c + dc)
            if nb not in dist and composite.is_passable(*nb):
                dist[nb] = d + 1
                q.append(nb)
        for nb in (dollar_of.get((r, c)), zero_of.get((r, c)), hat_of.get((r, c))):
            if nb is not None and nb != (r, c) and nb not in dist:
                dist[nb] = d + 1
                q.append(nb)
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
        par = _bfs_par_line(composite)
        if par is not None:
            break
    else:
        par = 7

    composite.par    = par
    composite.budget = math.ceil(par * 1.4)
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
    composite.par    = _dijkstra_par_level2(composite, door_cols)
    composite.budget = math.ceil(composite.par * 1.4)

    # Fog: reveal Room 0 and the first door; hide everything beyond.
    composite.fog_col = door_cols[0] + 1   # = 20

    dungeon.rooms    = [composite]
    dungeon.current_room = 0
    return dungeon


# ── Level 3 helpers ───────────────────────────────────────────────────────────

def _make_rune_corridor(composite, rng, row_top,
                        col_start=None, col_end=None, density=0.65):
    """Carve a 2-row CORRIDOR strip and fill it densely with non-void rune clusters.

    Leaves a 1-cell buffer at each end so runes reach the turn-room entrance.
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
                syms  = _RUNE_SYMS[kind]
                width = len(syms)
                if c + width - 1 <= col_end:
                    composite.runes.append(
                        RuneCluster(row=row, col=c, symbols=syms, kind=kind))
                    c += width + rng.randint(1, 2)
                    continue
            c += 1


def _dijkstra_par_wbe(composite) -> int | None:
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
    heap = [(0, entry)]

    while heap:
        cost, (r, c) = heapq.heappop(heap)
        if (r, c) == goal:
            return cost
        if cost > dist.get((r, c), float('inf')):
            continue

        def _push(nb, mc=1):
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
                heapq.heappush(heap, (g, (nr, nc)))

        # count h/j/k/l — void blocks landing but count can bypass (engine behaviour)
        for dr, dc in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            for n in range(1, max_n + 1):
                nr, nc = r + dr * n, c + dc * n
                if not composite.is_passable(nr, nc):
                    break
                ru = composite.rune_at(nr, nc)
                if ru and ru.kind == 'void':
                    continue  # can't land here; larger n can bypass
                mc = 1 if n == 1 else len(str(n)) + 1
                _push((nr, nc), mc)

        # w, b, e (cost 1 each)
        _push(_w(r, c))
        _push(_b(r, c))
        _push(_e(r, c))

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
        (2,  4,  45, 46),   # RT1
        (5,  7,  1,  2),    # LT1
        (8,  10, 45, 46),   # RT2
        (11, 13, 1,  2),    # LT2
    ]
    for r0, r1, ca, cb in turn_spans:
        for row in range(r0, r1 + 1):
            cells[row][ca] = CellType.CORRIDOR
            cells[row][cb] = CellType.CORRIDOR

    # ── Carve and populate rune corridors (up to 20 attempts for valid par) ──
    for _attempt in range(20):
        composite.runes.clear()
        rune_rng = random.Random(rng.randint(0, 2**31))

        for row_top in _L3_CORR_TOP_ROWS:
            _make_rune_corridor(composite, rune_rng, row_top)

        # C5 exit area: clear auto-placed runes from cols 40-46, then anchor a
        # fixed 3-symbol cluster whose last cell is the exit position.
        composite.runes = [
            ru for ru in composite.runes
            if not (ru.row in (13, 14) and ru.col >= 40)
        ]
        composite.runes.append(
            RuneCluster(row=13, col=42, symbols=('∘', '∘', '∘'), kind='ancient'))

        composite.entry    = (1, 1)
        composite.exit_pos = (13, 44)    # last symbol of anchor rune
        composite.entities = [Entity(kind='exit', row=13, col=44)]

        # Voids for turns and far end of exit
        for mid_row, col in ((1,45),(2,45),(4,1),(5,1),(7,45),(8,45),(10,1),(11,1)):
            composite.runes.append(
                RuneCluster(row=mid_row, col=col, symbols=('○', '○'), kind='void'))
        for mid_row, col in ((13,46),(14,46)):
            composite.runes.append(
                RuneCluster(row=mid_row, col=col, symbols=('○'), kind='void'))

        par = _dijkstra_par_wbe(composite)
        if par is not None:
            break
    else:
        par = 80

    composite.par    = par
    composite.budget = math.ceil(par * 1.4)

    dungeon.rooms        = [composite]
    dungeon.current_room = 0
    return dungeon


def build_dungeon_dummy(seed: int) -> Dungeon:
    """Admin editing sandbox — open room containing all editable element types."""
    ROWS, COLS = 20, 62
    dungeon = Dungeon(name='Dummy Dungeon', seed=seed)
    cells   = [[CellType.WALL] * COLS for _ in range(ROWS)]

    for r in range(1, ROWS - 1):
        for c in range(1, COLS - 1):
            cells[r][c] = CellType.FLOOR

    # Demo wall strips so the admin can practice cutting/pasting walls
    for c in range(8, 22):
        cells[5][c] = CellType.WALL
    for r in range(9, 16):
        cells[r][38] = CellType.WALL

    composite = Room(room_type=RoomType.ENTRY, rows=ROWS, cols=COLS)
    composite.cells = cells
    composite.seed  = seed

    composite.entry    = (1, 1)
    composite.exit_pos = (ROWS - 2, COLS - 2)

    composite.entities = [
        Entity(kind='entry_marker', row=1,        col=1),
        Entity(kind='exit',         row=ROWS - 2, col=COLS - 2),
        Entity(kind='door',         row=6,        col=30),
        Entity(kind='door',         row=7,        col=30),
    ]

    composite.runes = [
        RuneCluster(row=2,  col=3,  symbols=('∘', '∘', '∘'),      kind='ancient'),
        RuneCluster(row=2,  col=8,  symbols=('·', '·', '·'),       kind='verdant'),
        RuneCluster(row=2,  col=13, symbols=('○', '○'),            kind='void'),
        RuneCluster(row=2,  col=17, symbols=('◦', '◦', '◦', '◦'), kind='ember'),
        RuneCluster(row=8,  col=5,  symbols=('∘', '∘'),            kind='ancient'),
        RuneCluster(row=8,  col=10, symbols=('·', '·'),            kind='verdant'),
        RuneCluster(row=12, col=15, symbols=('◦', '◦', '◦'),       kind='ember'),
        RuneCluster(row=15, col=45, symbols=('∘', '∘', '∘'),       kind='ancient'),
    ]

    composite.par            = None
    composite.budget         = 99999
    composite.passable_walls = True
    dungeon.rooms            = [composite]
    dungeon.current_room = 0
    return dungeon
