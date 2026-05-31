"""Level 3 — The Rune Halls: dungeon correctness tests."""
import math
import pytest
from generation.dungeon_gen import build_dungeon_rune_halls, _dijkstra_par_wbe

SEEDS = [1, 42, 999, 12345, 2**20 + 7]


@pytest.mark.parametrize("seed", SEEDS)
def test_exit_is_reachable(seed):
    d = build_dungeon_rune_halls(seed)
    room = d.room
    assert room.exit_pos is not None
    par = _dijkstra_par_wbe(room)
    assert par is not None, f"seed={seed}: exit unreachable with wbe motions"


@pytest.mark.parametrize("seed", SEEDS)
def test_par_matches_dijkstra(seed):
    d = build_dungeon_rune_halls(seed)
    room = d.room
    expected = _dijkstra_par_wbe(room)
    assert room.par == expected, (
        f"seed={seed}: stored par {room.par} != Dijkstra {expected}"
    )


@pytest.mark.parametrize("seed", SEEDS)
def test_budget_is_ceil_par_times_1_4(seed):
    d = build_dungeon_rune_halls(seed)
    room = d.room
    assert room.budget == math.ceil(room.par * 1.4), (
        f"seed={seed}: budget={room.budget} but ceil(par*1.4)={math.ceil(room.par*1.4)}"
    )


@pytest.mark.parametrize("seed", SEEDS)
def test_word_motion_is_necessary(seed):
    """hjkl-only BFS must exceed the budget — w/b/e are required to win."""
    from collections import deque
    d = build_dungeon_rune_halls(seed)
    room = d.room
    void_cells = {
        (ru.row, ru.col + i)
        for ru in room.char_runs if ru.kind == 'void'
        for i in range(len(ru.symbols))
    }
    dist = {room.spawn_pos: 0}
    q = deque([room.spawn_pos])
    while q:
        pos = q.popleft()
        r, c = pos
        for dr, dc in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            nb = (r + dr, c + dc)
            if nb not in dist and room.is_passable(*nb) and nb not in void_cells:
                dist[nb] = dist[pos] + 1
                q.append(nb)
    single_step_cost = dist.get(room.exit_pos)
    assert single_step_cost is not None, f"seed={seed}: exit unreachable with single-step BFS"
    assert single_step_cost > room.budget, (
        f"seed={seed}: hjkl-only cost {single_step_cost} fits in budget {room.budget} "
        f"— word motions are not required"
    )


@pytest.mark.parametrize("seed", SEEDS)
def test_entry_and_exit_not_on_void(seed):
    d = build_dungeon_rune_halls(seed)
    room = d.room
    void_cells = {
        (ru.row, ru.col + i)
        for ru in room.char_runs if ru.kind == 'void'
        for i in range(len(ru.symbols))
    }
    assert room.spawn_pos    not in void_cells, f"seed={seed}: entry is on a void cell"
    assert room.exit_pos not in void_cells, f"seed={seed}: exit is on a void cell"


@pytest.mark.parametrize("seed", SEEDS)
def test_exit_entity_at_exit_pos(seed):
    d = build_dungeon_rune_halls(seed)
    room = d.room
    exit_ents = [e for e in room.entities if e.kind == 'exit']
    assert len(exit_ents) == 1, f"seed={seed}: expected 1 exit entity, got {len(exit_ents)}"
    e = exit_ents[0]
    assert (e.row, e.col) == room.exit_pos, (
        f"seed={seed}: exit entity at ({e.row},{e.col}) != exit_pos {room.exit_pos}"
    )


@pytest.mark.parametrize("seed", SEEDS)
def test_void_runes_present_in_turn_rooms(seed):
    """Turn-room void guards must exist to block direct j/k shortcutting."""
    d = build_dungeon_rune_halls(seed)
    room = d.room
    void_runes = [ru for ru in room.char_runs if ru.kind == 'void']
    assert len(void_runes) >= 8, (
        f"seed={seed}: expected at least 8 void clusters (turn guards), "
        f"got {len(void_runes)}"
    )


def test_anchor_char_run_at_fixed_position():
    """The exit-anchor rune at row=13, col=42 must always be present (hard-coded)."""
    d = build_dungeon_rune_halls(42)
    room = d.room
    anchor = room.char_run_at(13, 42)
    assert anchor is not None, "Expected anchor rune at (13, 42)"
    assert anchor.kind == 'ancient'
    assert anchor.col == 42 and anchor.row == 13


def test_exit_at_last_symbol_of_anchor():
    """exit_pos must be col 44 (anchor col 42 + 2 symbols), row 13."""
    d = build_dungeon_rune_halls(42)
    room = d.room
    assert room.exit_pos == (13, 44)
