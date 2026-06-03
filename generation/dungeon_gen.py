"""Assemble a dungeon from rooms joined by corridors into a single grid."""
from __future__ import annotations
import heapq, math, os, random, unicodedata
from collections import deque
from engine.world import Dungeon, Room, RoomType, CellType, CharRun, Entity
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

# The First Cave: Entry → Puzzle → Exit  (hjkl only)
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

def _place_runes_in_room(composite, rng, col_offset, room_rows, room_cols,
                          total_rows, density):
    """Scatter character runs inside one room of the composite grid."""
    row_offset = (total_rows - room_rows) // 2
    col_end = col_offset + room_cols - 2
    for r in range(row_offset + 1, row_offset + room_rows - 1):
        c = col_offset + 2
        while c < col_end:
            if rng.random() < density:
                kind = rng.choice(_RUNE_KINDS)
                placed = False
                for _ in range(2):  # one retry for long characters at end
                    syms = _make_rune_syms(rng, kind)
                    width = len(syms)
                    if c + width <= col_end:
                        composite.char_runs.append(
                            CharRun(row=r, col=c, symbols=syms, kind=kind))
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
        for ru in composite.char_runs if ru.kind == 'void'
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

        # ^ — leftmost character in wall/fog-bounded segment
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
            if composite.char_run_at(r, nc):
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

    # Place character runs in all three rooms — no safe rows, characters can appear
    # anywhere including rows 4-5 (the corridor band).  Par is computed by BFS
    # after placement.  If the characters block every path, retry with a new sub-seed
    # (up to 20 attempts).
    densities = {0: 0.20, 1: 0.28, 2: 0.20}
    for attempt in range(20):
        composite.char_runs.clear()
        rune_rng = random.Random(rng.randint(0, 2**31))
        for i, (_, room_rows, room_cols) in enumerate(plan):
            _place_runes_in_room(composite, rune_rng, offsets[i],
                                 room_rows, room_cols, total_rows, densities[i])

        # Hard-coded void guards: block (2, ex_c) and (3, ex_c) so the player
        # cannot walk straight up from the corridor to the exit.  They must go
        # right into Room 2, up to row 1, then press h to reach the exit.
        # Remove any random character that would shadow these hard-coded voids.
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
    """Pack runes left→right across [c0, c1] with random kinds, lengths and 1–3
    cell gaps (seeded by the dungeon seed, the way the other levels scatter
    theirs).  The first rune placed is forced non-void: apply_motion ^ halts on
    the first char_run of ANY kind while the par solver skips void, so a leading
    void rune would desync them — and the ^ landing must be survivable.  Void
    runes therefore only sit mid-hall (passed over by the line jumps) or right of
    the exit, never on a cell a motion lands on."""
    runs, c, first = [], c0, first_non_void
    while c <= c1:
        kind = rng.choice(_WORD_RUNE_KINDS) if first else rng.choice(_RUNE_KINDS)
        first = False
        syms = list(_make_rune_syms(rng, kind))[:c1 - c + 1]   # trim a long rune to fit
        runs.append(CharRun(row=row, col=c, symbols=tuple(syms), kind=kind))
        c += len(syms) + rng.randint(1, 3)
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
            if lbl in allow and nb is not None and nb != (r, c) and nb not in dist:
                dist[nb] = d + 1
                prev[nb] = ((r, c), lbl)
                q.append(nb)
    if return_path:
        return None, ''
    return None


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
        CharRun(row=row, col=puzzle_mid_col, symbols=('○',), kind='void')
        for row in range(2, total_rows - 2)          # rows 2-9
    ]

    # Decorative characters in entry and exit rooms; retry if any void blocks path.
    for attempt in range(20):
        composite.char_runs = list(void_wall)
        rune_rng = random.Random(rng.randint(0, 2**31))
        _place_runes_in_room(composite, rune_rng, offsets[0],
                              plan[0][1], plan[0][2], total_rows, 0.18)
        _place_runes_in_room(composite, rune_rng, offsets[2],
                              plan[2][1], plan[2][2], total_rows, 0.18)

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
                        col_start=None, col_end=None, density=0.65,
                        blocked: frozenset = frozenset()):
    """Carve a 2-row CORRIDOR strip and fill it densely with non-void character runs.

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
        c = col_start + 1
        while c <= col_end - 1:
            if rng.random() < density:
                kind  = rng.choice(_WORD_RUNE_KINDS)
                placed = False
                for _ in range(2):  # one retry for long characters at end
                    syms  = _make_rune_syms(rng, kind)
                    width = len(syms)
                    if c + width - 1 <= col_end:
                        if not any((row, cc) in blocked
                                   for cc in range(c - 1, c + width + 1)):
                            composite.char_runs.append(
                                CharRun(row=row, col=c, symbols=syms, kind=kind))
                            c += width + rng.randint(1, 2)
                            placed = True
                            break
                if placed:
                    continue
            c += 1


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
            ru = composite.char_run_at(nr, nc)
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
                ru = composite.char_run_at(nr, nc)
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


def _cataracts_place_zone(composite, rng, rows, col_start, col_end,
                   density=0.55, blocked=frozenset()):
    """Fill a character zone across the given rows between col_start and col_end."""
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
                        composite.char_runs.append(
                            CharRun(row=r, col=c, symbols=syms, kind=kind))
                        c += w + rng.randint(1, 2)
                        continue
            c += 1


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
            ru = composite.char_run_at(nr, nc)
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
                ru = composite.char_run_at(nr, nc)
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
        CharRun(row=1,  col=44, symbols=('◦', '◦', '◦'), kind='ember'),
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
        CharRun(row=13, col=64, symbols=('◦', '◦'), kind='ember'),
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
        _cataracts_place_zone(composite, rng2, (13, 14),  2,  63,
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
    for fr in _RELIQUARY_FRIEZE_ROWS:
        _place_frieze(composite, rng, fr, 1, W - 1)            # left chamber
        _place_frieze(composite, rng, fr, W + 1, COLS - 2)     # right sanctum

    composite.par    = None
    composite.budget = 35
    composite.answer = _reliquary_answer(word)

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
        CharRun(row=2, col=17, symbols=('◦',), kind='ember'),
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
    composite.ledge_rows = {13, 14, 16}

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
        word = rng.choice(word_tbl.get(length) or word_tbl[1])
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

    entities: list = [Entity(kind='entry_marker', row=1, col=1)]
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


# ── The Warden Surveyor (ACT II BOSS, caps L6-L13) ────────────────────────────
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
    # Matches engine/_is_word_char: alpha/digit/_ plus Unicode So (Symbol,Other).
    def _is_wc(ch):
        return ch.isalpha() or ch.isdigit() or ch == '_' or unicodedata.category(ch) == 'So'

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

        # ^: leftmost character in passability-bounded range; void as first character = lethal, don't push
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
            ru2 = composite.char_run_at(r, cc)
            if ru2:
                if _ok(r, cc):
                    _push((r, cc), 1, '^')
                break  # first character (void or not) terminates search

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

    # Matches engine/_is_word_char: alpha/digit/_ plus Unicode So (Symbol,Other).
    def _is_wc(ch):
        return ch.isalpha() or ch.isdigit() or ch == '_' or unicodedata.category(ch) == 'So'

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

        # ^: first character in passability-bounded range (any direction from current col)
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
            ru2 = composite.char_run_at(r, cc)
            if ru2:
                if _ok(r, cc):
                    _push((r, cc), 1, '^')
                break  # first character (void or not) terminates search

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


def build_dungeon_sight_sanctum(seed: int) -> Dungeon:
    """Visual Mode: The Sight Sanctum.

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
            composite.char_runs.append(CharRun(row=1, col=c, symbols=('○',), kind='void'))
    for c in range(3, 19):                   # row 3: cols 3-18 (col 19 always clear)
        if rng.random() < 0.6:
            composite.char_runs.append(CharRun(row=3, col=c, symbols=('○',), kind='void'))

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
# Optimal route (par 19):  * n 0 x N $ p l x /vault⏎ $ p l
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
_SEEKERS_PAR          = 19
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
    (cost len(W)+2+k); '*' + k·n does the same for the word under the cursor
    (cost 1+k).  no_search drops all search edges — the foot-only bound that
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
                out.append((len(W) + 2 + k, tgt, f'/{W}⏎' + 'n' * k))
            bwd = [m for m in reversed(ms) if m < cur] + [m for m in reversed(ms) if m >= cur]
            for k, tgt in enumerate(bwd):
                out.append((len(W) + 2 + k, tgt, f'?{W}⏎' + 'n' * k))
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
#     (optional — par includes the detour; skippers beat par).
#   • `a (exact mark) -> back to the spawn at the sanctum's centre.
#   • the exit key sits BACKWARD (thin top band) with forward decoys (bottom room),
#     so ? lands on it directly while / hits a decoy.
#   • the sanctum sits HIGH so M (middle-of-screen) always lands DOWN in the goblin
#     room, never on the scroll nook — using M to cheat the scroll backfires lethally.
# The exit is teleport-safe (not any jump target; behind the blocking exit lock).
#
# Optimal route (par 20, taking the scroll):
#   ma · 'a x (scroll) · ?cipher⏎ h x (key) · `a $ (home, then line-end) · p l → exit
# A skipper drops 'a x and finishes in 17 — under par.
_WP_ROWS, _WP_COLS = 19, 46
_WP_CROW   = 5                     # sanctum corridor row (mark row; wordless)
_WP_SCROLL = (5, 1)                # chest_scroll — sanctum row's first-left cell -> 'a
_WP_SCROLL_DOOR = (5, 4)           # 'blue' lock sealing the scroll nook ('a hops it)
_WP_SPAWN  = (5, 23)               # spawn + mark -> centre of the sanctum corridor
_WP_LOCK   = (5, 43)               # exit lock (gold)
_WP_EXIT   = (5, 44)
_WP_KEYWORD      = 'cipher'
_WP_KEY_WORD_POS = (2, 30)         # exit key's word — thin TOP danger band (backward)
_WP_KEY          = (2, 29)         # gold floor_key, just left of the word
_WP_DECOY_POS    = [(11, 12), (13, 24), (15, 34)]  # forward decoys (open danger floor)
_WP_DANGER_ROWS  = (1, 2, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17)
_WP_VAULT_COLS   = (6, 10, 14, 18, 22, 26, 30, 34, 38, 42)  # vaults lining the sanctum underside
_WP_PAR    = 20
_WP_ANSWER = "ma 'a x ?cipher⏎ h x `a $ p l"


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

    # Thin TOP danger band (rows 1-2) — holds the gold key + its 'cipher' word.
    for r in (1, 2):
        for c in range(1, C - 1):
            carve(r, c)
    # SANCTUM (rows 4-6), sealed above by the row-3 wall and below by the row-7 wall.
    # Row 5 is the mark row: a one-cell scroll nook at col 1 behind a 'blue' lock at
    # col 2, then the wordless corridor, the gold exit lock (43) + exit (44).  Rows 4
    # & 6 are corridor only from col 5 — so their first-non-blank is the corridor,
    # never the nook (this keeps M off the scroll; see the module comment).
    for c in range(5, 43):
        carve(4, c); carve(6, c)
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
    for i, X in enumerate(_WP_VAULT_COLS):
        # The row-9 vaults hold hearts and relic scrolls (the random pool); only
        # the left-chamber nook holds the Numbered Ledger (see below).
        kind = 'heart_container' if i % 3 == 1 else 'chest_scroll'
        carve(7, X)                                      # 'blue' door cell (in the seal)
        for r in (8, 9):                                 # box the shaft off the danger room
            cells[r][X - 1] = CellType.WALL
            cells[r][X + 1] = CellType.WALL
        cells[10][X] = CellType.WALL
        entities += [Entity(kind='locked_door', row=7, col=X, tag='blue'),
                     Entity(kind=kind, row=9, col=X)]
        vault_cells |= {(7, X), (8, X), (9, X)}
    composite.cells = cells
    composite.seed = seed

    # Reserved cells (no prose decor / no goblins): key, key word, decoys, vaults.
    reserved: set = {_WP_KEY} | vault_cells
    reserved |= {(_WP_KEY_WORD_POS[0], _WP_KEY_WORD_POS[1] + i) for i in range(len(_WP_KEYWORD))}
    for (dr, dc) in _WP_DECOY_POS:
        reserved |= {(dr, dc + i) for i in range(len(_WP_KEYWORD))}
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
# Three-corridor snake layout (7 rows × 60 cols).
# Each corridor row has ( at col _BRACKET_VAULTS_BRACKET_OPEN and ) at col _BRACKET_VAULTS_BRACKET_CLOSE.
# Row 3 (middle) is filled with void runes everywhere EXCEPT the two bracket cells,
# forcing the player to use % to cross it rather than manual h/l navigation.
#
# Right turn: col _BRACKET_VAULTS_BRACKET_CLOSE, rows 1-3 (single-column gap cell at row 2).
# Left turn:  col _BRACKET_VAULTS_BRACKET_OPEN,  rows 3-5 (single-column gap cell at row 4).
#
# Optimal path (par=7):  % 2j % 2j %
#   Entry (1,1): % scans right, finds ( at col 4, jumps to ) at col 54.
#   2j → (3,54) ).  % → (3,4) (.  2j → (5,4) (.  % → (5,54) EXIT.
#   % at (1,1) is not on a bracket but Vim-style % scans right for the first
#   bracket on the row — finds ( col 4 and jumps to its match ) col 54.
#
_BRACKET_VAULTS_ROWS          = 7
_BRACKET_VAULTS_COLS          = 60
_BRACKET_VAULTS_BRACKET_OPEN  = 4      # ( on each corridor row
_BRACKET_VAULTS_BRACKET_CLOSE = 54     # ) on rows 1 & 3; right-turn column; exit column
_BRACKET_VAULTS_CLOSE_R5      = 53     # ) on row 5 only (one left of CLS; exit sits at CLS)
_BRACKET_VAULTS_CORR_ROWS     = (1, 3, 5)
_BRACKET_VAULTS_ENTRY         = (1, 1)
_BRACKET_VAULTS_EXIT_POS      = (5, _BRACKET_VAULTS_BRACKET_CLOSE)
_BRACKET_VAULTS_PAR           = 8       # % 2j % 2j % l  = 1+2+1+2+1+1 = 8 ks
_BRACKET_VAULTS_ANSWER        = '% 2j % 2j % l'


def _par_bracket_vaults(composite, use_percent: bool = True, return_path: bool = False):
    """Minimum-keystroke Dijkstra for The Bracket Vaults.

    Supported motions (all available at The Bracket Vaults):
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
        ru = composite.char_run_at(r, c)
        return not (ru and ru.kind == 'void')

    def _bracket_here(r, c):
        ru = composite.char_run_at(r, c)
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

        # ^: first character (any kind) scanning from leftmost passable boundary.
        # Stops at the first character found (void or not); only pushes if _ok
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
            ru2 = composite.char_run_at(r, cc)
            if ru2:
                if _ok(r, cc):
                    _push((r, cc), 1, '^')
                break  # first character (void or not) terminates search

        # %: matching bracket jump (disabled in command-necessity test)
        if use_percent:
            nb_pct = _pct(r, c)
            if nb_pct is not None:
                _push(nb_pct, 1, '%')

    if return_path:
        return None, ''
    return None


def build_dungeon_bracket_vaults(seed: int) -> Dungeon:
    """% (The Bracket Vaults).

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
    Layout is deterministic; seed only colors bracket characters.
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

    composite.char_runs = runes

    # ── Entry and exit ────────────────────────────────────────────────────────
    composite.spawn_pos    = _BRACKET_VAULTS_ENTRY
    composite.exit_pos = _BRACKET_VAULTS_EXIT_POS
    composite.entities = [Entity(kind='exit',
                                 row=_BRACKET_VAULTS_EXIT_POS[0], col=_BRACKET_VAULTS_EXIT_POS[1])]

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
    # Par is locked at _SCREEN_VAULT_PAR (deterministic; test_level_10 runs the solver to
    # verify).  The answer path is only shown to admin, so solve for it only when
    # compute_answer is set — the Dijkstra is too slow to run on every load.
    composite.par    = _SCREEN_VAULT_PAR
    composite.budget = math.ceil(_SCREEN_VAULT_PAR * 1.4)
    composite.answer = _par_screen_vault(composite, return_path=True)[1] if compute_answer else ''

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
# screen / paragraph jumps the player already knows (G gg {n}G H M L { }) reach
# only a row's FIRST sentence — ) is the sole way onto them.
_SENTENCE_CORRIDOR_SENTENCES = [
    (1, 1,  'A sentence is one stride.'),
    (1, 29, 'Where does it end?'),
    (1, 50, 'At a dot, or a bang!'),
    (3, 8,  'I cut each stone to fit.'),
    (3, 40, 'A good joint needs no mortar.'),
]


def _par_runic_archives(composite, return_path=False,
                      disable_brace=False, disable_paren=False):
    """Minimum-keystroke Dijkstra for Paragraph Jumps (The Runic Archives).

    State = (row, col, has_key, door_open) where:
      has_key:   0 = key on floor, 1 = key held
      door_open: 0 = locked_door blocking, 1 = door removed

    Available motions: hjkl, count-hjkl, 0, $, { } (unless disable_brace), x, p.
    disable_paren accepted but ignored (no sentence jumps in this level).
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

    def _fnb(row, dm):
        """First-non-blank col (matches motion._first_non_blank_col): first character
        start, else leftmost passable; None if the row has no passable cell."""
        left = None
        for c in range(COLS):
            if _ok(row, c, dm):
                if left is None:
                    left = c
                if composite.char_run_at(row, c) is not None:
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

    Line/screen jumps (G gg {n}G H M L { }) are intentionally NOT modelled: they
    only reach the FIRST sentence of a row, so they never beat ) onto the key's or
    door's sentence (both sit behind wall-gaps) — par is unaffected and ) stays
    genuinely required.  ( CAN be replaced by gg/{n}G + ), so it is the
    strongly-incentivized partner, not asserted as required.
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
    screen / paragraph jumps the player already has (G gg {n}G H M L { }) reach
    only a row's FIRST sentence — the ONLY way onto the key's and door's
    sentences is ).  Reaching the key is mandatory, so ) is forced.

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


# ── The Archivist's Library (L17) — one-line wrap_buffer + reload loop ───────
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


def _lib_frame(W: int, body: list) -> str:
    """Compose a framed 'page' as ONE wrap line: rows of EXACTLY W columns, so that
    wrapping at the viewport width W redraws a perfect rectangle. The first W chars
    are the top border, so even unwrapped the player sees ┌────┐ filling the view."""
    inner = max(1, W - 2)
    rows  = ['┌' + '─' * inner + '┐']
    for i in range(_LIB_BODY_ROWS):
        rows.append('│' + _lib_center(body[i] if i < len(body) else '', inner) + '│')
    rows.append('└' + '─' * inner + '┘')
    return ''.join(rows)        # each row is exactly W chars → (rows)*W total


# A library floor drawn top-down: rows of book-stacks (each labelled), reading
# tables with chairs. Full stacks are ▐█▌; the four SUIT stacks stand empty (▐ ▌)
# until their folios are refiled.
_LIB_GAP    = '   '
_LIB_TABLES = 'o▭▭▭o      o▭▭▭o      o▭▭▭o'


def _lib_band(labels: list, fill: list) -> tuple:
    """One shelf-band: a label row (a glyph centred over each stack) and a stack row."""
    lab   = _LIB_GAP.join(f' {g} ' for g in labels)
    shelf = _LIB_GAP.join('▐█▌' if f else '▐ ▌' for f in fill)
    return lab, shelf


def _lib_catalog_spec() -> dict:
    g = _LIB_SUIT_GLYPH
    l1, s1 = _lib_band(['▦', '▦', g['hearts'], '▦', g['diamonds'], '▦'],
                       [1, 1, 0, 1, 0, 1])
    l2, s2 = _lib_band(['▦', g['spades'], '▦', '▦', g['clubs'], '▦'],
                       [1, 0, 1, 1, 0, 1])
    body = ['L I B R A R Y', '', l1, s1, s1, _LIB_TABLES, l2, s2, s2]
    return {'suit': None, 'kind': 'ancient', 'body': body}


def _lib_suit_spec(suit: str) -> dict:
    g    = _LIB_SUIT_GLYPH[suit]
    row  = ' '.join([g] * 7)
    full = '▐' + '█' * 15 + '▌'
    mid  = '▐█' + _lib_center(' '.join([g] * 3), 13) + '█▌'
    body = ['  '.join(suit.upper()), '', row, full, mid, full, row, '', '']
    return {'suit': suit, 'kind': 'ember', 'body': body}


def _lib_decoy_spec(n: int) -> dict:
    full = '▐' + '░▒▓' * 5 + '▌'
    mid  = '▐░' + _lib_center('~ ~ ~ ~', 13) + '▒▌'
    body = ['R U I N E D   L E A F', '',
            '░ ▒ ▓ ░ ▒ ▓ ░', full, mid, full, '▓ ░ ▒ ▓ ░ ▒ ▓', '', '']
    return {'suit': None, 'kind': 'verdant', 'body': body}


def _lib_finale_spec() -> dict:
    g = _LIB_SUIT_GLYPH
    l1, s1 = _lib_band([g['hearts'], '▦', g['diamonds'], '▦', g['spades'], g['clubs']],
                       [1, 1, 1, 1, 1, 1])
    body = ['L I B R A R Y   R E S T O R E D', '', l1, s1, s1, _LIB_TABLES, s1, s1, '']
    return {'suit': None, 'kind': 'ember', 'body': body}


def _lib_layout(room, W: int) -> None:
    """(Re)compose the current page at viewport width W: rebuild the one-line buffer,
    resize the room, and rest the Archivist at the bottom-right corner so $ presents.
    Called by the builder and by main.run_dungeon whenever the width changes."""
    if getattr(room, 'lib_done', None) == 'win' and getattr(room, 'lib_finale', None):
        spec = room.lib_finale
    elif room.lib_idx < 0:
        spec = room.lib_catalog
    else:
        spec = room.lib_seq[room.lib_idx]
    line = _lib_frame(W, spec['body'])
    room.cols      = len(line)
    room.cells     = [[CellType.FLOOR] * room.cols]
    room.char_runs = [CharRun(0, 0, tuple(line), spec['kind'])]
    for e in room.entities:
        if e.kind == 'archivist':
            e.col = room.cols - 1          # bottom-right corner → reachable with $
    room._lib_w = W
    room.rebuild_indexes()


def build_dungeon_archivists_library(seed: int) -> Dungeon:
    rng = random.Random(seed)
    dungeon = Dungeon(name="The Archivist's Library", seed=seed)

    room = Room(room_type=RoomType.ENTRY, rows=1, cols=_LIB_FALLBACK_W)
    room.seed        = seed
    room.spawn_pos   = (0, 0)
    room.wrap_buffer = True
    room.par         = 0          # contextual level — no par-forcing
    room.budget      = 2000       # generous; the loop is exploratory, never budget-gated
    room.answer      = ''

    # Cadence: suit at indices 0,3,7,10 of an 11-long cycle; decoys elsewhere; loops.
    suit_slots = [0, 3, 7, 10]
    suits      = list(_LIB_SUITS)
    rng.shuffle(suits)
    seq, decoy_n = [], 0
    for i in range(11):
        if i in suit_slots:
            seq.append(_lib_suit_spec(suits[suit_slots.index(i)]))
        else:
            decoy_n += 1
            seq.append(_lib_decoy_spec(decoy_n))

    room.lib_seq     = seq
    room.lib_catalog = _lib_catalog_spec()
    room.lib_finale  = _lib_finale_spec()
    room.lib_idx     = -1         # -1 = the catalogue/index is showing
    room.lib_filed   = {}         # suit-name -> the true suit of what was filed (None = decoy)
    room.lib_done    = None       # None | 'win' | 'dead'
    room.lib_briefed = False      # has the player seen the post-wrap brief?
    room._lib_arch_flag = False   # debounces the on-Archivist trigger

    # The Archivist starts off the first screen (resting at the far corner); ':set wrap'
    # folds the line into the viewport and brings him into view.
    room.entities = [
        Entity(kind='entry_marker', row=0, col=0),
        Entity(kind='archivist',    row=0, col=1),
    ]
    _lib_layout(room, _LIB_FALLBACK_W)

    dungeon.rooms        = [room]
    dungeon.current_room = 0
    return dungeon
