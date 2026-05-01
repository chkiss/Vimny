"""Level 2 — The Counting Crypts: dungeon correctness tests."""
import heapq
import pytest
from generation.dungeon_gen import (
    build_dungeon_2, _dijkstra_par_count, _dijkstra_par_level2, LEVEL_2_PLAN,
)
from engine.world import RoomType

SEEDS = [1, 42, 999, 12345, 2**20 + 7]


def _count_optimal_reach(composite, max_count=50):
    """Dijkstra clone used for test verification (same logic as production)."""
    void_cells = {
        (ru.row, ru.col + i)
        for ru in composite.runes if ru.kind == 'void'
        for i in range(len(ru.symbols))
    }
    dist = {composite.entry: 0}
    heap = [(0, composite.entry)]
    goal = composite.exit_pos
    while heap:
        cost, (r, c) = heapq.heappop(heap)
        if (r, c) == goal:
            return cost
        if cost > dist.get((r, c), float('inf')):
            continue
        for dr, dc in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            for n in range(1, max_count + 1):
                nr, nc = r + dr * n, c + dc * n
                if not composite.is_passable(nr, nc) or (nr, nc) in void_cells:
                    break
                move_cost = 1 if n == 1 else len(str(n)) + 1
                new_cost = cost + move_cost
                if new_cost < dist.get((nr, nc), float('inf')):
                    dist[(nr, nc)] = new_cost
                    heapq.heappush(heap, (new_cost, (nr, nc)))
    return None


@pytest.mark.parametrize("seed", SEEDS)
def test_exit_is_reachable(seed):
    d = build_dungeon_2(seed)
    room = d.room
    assert room.exit_pos is not None
    par = _count_optimal_reach(room)
    assert par is not None, f"seed={seed}: exit unreachable with count motions"


@pytest.mark.parametrize("seed", SEEDS)
def test_par_matches_dijkstra(seed):
    """par equals full state-space Dijkstra: all Level 2 commands + door states."""
    d = build_dungeon_2(seed)
    room = d.room
    door_cols = sorted(set(e.col for e in room.entities if e.kind == 'door' and e.alive))
    expected = _dijkstra_par_level2(room, door_cols)
    assert room.par == expected, (
        f"seed={seed}: stored par {room.par} != full Dijkstra {expected}"
    )


@pytest.mark.parametrize("seed", SEEDS)
def test_par_includes_keystroke_for_every_action(seed):
    """par must account for all keystrokes: count motions, line motions ($), and door x.

    The simple count-Dijkstra (h/j/k/l only, ignores door blocking) produces a
    physically impossible lower bound — it walks straight through closed doors.
    The full state-space result, which models door blocking (breaking $ into
    per-segment jumps) and x keypresses, must be strictly higher and must equal
    room.par.
    """
    d = build_dungeon_2(seed)
    room = d.room
    door_cols = sorted(set(e.col for e in room.entities if e.kind == 'door' and e.alive))

    nav_only = _dijkstra_par_count(room)           # ignores doors: physically impossible
    full_par = _dijkstra_par_level2(room, door_cols)  # all commands + door state

    assert room.par == full_par, (
        f"seed={seed}: room.par={room.par} but full Dijkstra gives {full_par}"
    )
    assert full_par > nav_only, (
        f"seed={seed}: full par {full_par} should exceed nav-only {nav_only}; "
        f"door blocking and x keypresses must add cost"
    )


@pytest.mark.parametrize("seed", SEEDS)
def test_budget_is_ceil_par_times_1_4(seed):
    d = build_dungeon_2(seed)
    room = d.room
    import math
    assert room.budget == math.ceil(room.par * 1.4), \
        f"seed={seed}: budget={room.budget} but ceil(par*1.4)={math.ceil(room.par*1.4)}"


@pytest.mark.parametrize("seed", SEEDS)
def test_count_is_necessary(seed):
    """Single-step BFS should need MORE keystrokes than the budget allows."""
    from collections import deque
    d = build_dungeon_2(seed)
    room = d.room
    void_cells = {
        (ru.row, ru.col + i)
        for ru in room.runes if ru.kind == 'void'
        for i in range(len(ru.symbols))
    }
    # BFS counting one keystroke per single-step move
    dist = {room.entry: 0}
    q = deque([room.entry])
    while q:
        pos = q.popleft()
        r, c = pos
        for dr, dc in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            nb = (r + dr, c + dc)
            if nb not in dist and room.is_passable(*nb) and nb not in void_cells:
                dist[nb] = dist[pos] + 1
                q.append(nb)
    single_step_cost = dist.get(room.exit_pos)
    assert single_step_cost is not None, f"seed={seed}: exit unreachable single-step"
    assert single_step_cost > room.budget, (
        f"seed={seed}: single-step cost {single_step_cost} fits in budget {room.budget} "
        f"— count is not required"
    )


@pytest.mark.parametrize("seed", SEEDS)
def test_void_wall_exists_in_puzzle_room(seed):
    """Void wall at the puzzle room's horizontal midpoint must be present."""
    d = build_dungeon_2(seed)
    room = d.room
    # offsets[1] = 20 + 4 = 24, plan[1][2]//2 = 16 → mid_col = 40
    puzzle_offset = LEVEL_2_PLAN[0][2] + 4   # 24
    puzzle_mid_col = puzzle_offset + LEVEL_2_PLAN[1][2] // 2  # 40
    void_at_mid = [ru for ru in room.runes
                   if ru.kind == 'void' and ru.col == puzzle_mid_col]
    assert len(void_at_mid) >= 4, \
        f"seed={seed}: expected void wall at col {puzzle_mid_col}, found {len(void_at_mid)} runes"


@pytest.mark.parametrize("seed", SEEDS)
def test_entry_and_exit_not_on_void(seed):
    d = build_dungeon_2(seed)
    room = d.room
    void_cells = {
        (ru.row, ru.col + i)
        for ru in room.runes if ru.kind == 'void'
        for i in range(len(ru.symbols))
    }
    assert room.entry    not in void_cells, f"seed={seed}: entry is on a void cell"
    assert room.exit_pos not in void_cells, f"seed={seed}: exit is on a void cell"


# ── Known failing tests (bugs to be fixed) ───────────────────────────────────

def test_3j_59l_3k_does_not_beat_par():
    """Fog wall blocks the count-motion shortcut to the exit.

    Without fog, '3j 59l 3k' from entry (2,2) would reach exit_pos directly
    by passing through the void wall, coming in far under par.  The fog wall
    at col 20 stops 59l at col 19 (the door), so the player cannot reach the
    exit via this sequence.
    """
    from main import apply_motion
    from engine.player import Player

    d = build_dungeon_2(1)
    room = d.room

    player = Player(row=room.entry[0], col=room.entry[1])

    for motion, count in [('j', 3), ('l', 59), ('k', 3)]:
        apply_motion(player, motion, count, room)

    assert (player.row, player.col) != room.exit_pos, (
        f"3j 59l 3k unexpectedly reached exit {room.exit_pos}; "
        f"door at col 19 should have blocked this shortcut"
    )


def test_count_with_trailing_zero_not_split_at_zero():
    """Bug: '30l' is misparsed as motion='0' (go-to-line-start) with count=3.

    COUNTS = set('123456789') excludes '0', so the parser treats the '0' in
    '30' as the beginning-of-line motion rather than the second digit of the
    count.  In real Vim, '0' is only a motion when it appears as the *first*
    character of a command; after one or more non-zero digits it is always part
    of the count.

    Fix: allow '0' inside the count-accumulation loop when count is non-empty.
    """
    from engine.vim_parser import parse
    from engine.modes import Mode

    action, remaining = parse('30l', Mode.NORMAL)
    # FAILS: parser returns {'type': 'motion', 'motion': '0', 'count': 3}
    assert action == {'type': 'motion', 'motion': 'l', 'count': 30}, (
        f"'30l' parsed as {action!r}; expected count=30 motion='l'"
    )
    assert remaining == '', f"unexpected remaining buffer after '30l': {remaining!r}"
