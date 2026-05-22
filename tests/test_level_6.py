"""Level 6 — The WORD Forge: dungeon correctness tests."""
import math
import heapq
import pytest
from generation.dungeon_gen import build_dungeon_6, _dijkstra_par_WBE, _L6_UNTYPABLE_PUNCT

SEEDS = [1, 42, 999, 12345, 2**20 + 7]


@pytest.mark.parametrize("seed", SEEDS)
def test_exit_is_reachable(seed):
    d = build_dungeon_6(seed)
    room = d.rooms[0]
    assert room.exit_pos is not None
    par = _dijkstra_par_WBE(room)
    assert par is not None, f"seed={seed}: exit unreachable"


@pytest.mark.parametrize("seed", SEEDS)
def test_par_matches_dijkstra(seed):
    d = build_dungeon_6(seed)
    room = d.rooms[0]
    expected = _dijkstra_par_WBE(room)
    assert room.par == expected, (
        f"seed={seed}: stored par {room.par} != Dijkstra {expected}"
    )


@pytest.mark.parametrize("seed", SEEDS)
def test_budget_is_ceil_par_times_1_4(seed):
    d = build_dungeon_6(seed)
    room = d.rooms[0]
    assert room.budget == math.ceil(room.par * 1.4), (
        f"seed={seed}: budget={room.budget} but ceil(par*1.4)={math.ceil(room.par*1.4)}"
    )


@pytest.mark.parametrize("seed", SEEDS)
def test_par_is_ten(seed):
    """Void guards on C1 rows 1-2 and C2 rows 4-5 plus game-faithful solver semantics guarantee par=10 (NW 3j NB 3j NE)."""
    d = build_dungeon_6(seed)
    room = d.rooms[0]
    assert room.par == 10, f"seed={seed}: expected par=10, got {room.par}"


@pytest.mark.parametrize("seed", SEEDS)
def test_answer_uses_WBE(seed):
    """Optimal answer must use W, B, and E (the WORD motions taught in level 6)."""
    d = build_dungeon_6(seed)
    room = d.rooms[0]
    tokens = room.answer.split()
    has_W = any(t.endswith('W') for t in tokens)
    has_B = any(t.endswith('B') for t in tokens)
    has_E = any(t.endswith('E') for t in tokens)
    assert has_W, f"seed={seed}: W not in answer {room.answer!r}"
    assert has_B, f"seed={seed}: B not in answer {room.answer!r}"
    assert has_E, f"seed={seed}: E not in answer {room.answer!r}"


@pytest.mark.parametrize("seed", SEEDS)
def test_WBE_cheaper_than_count_hjkl(seed):
    """W/B/E path (par=10) is cheaper than minimum count-hjkl path (13 keystrokes)."""
    d = build_dungeon_6(seed)
    room = d.rooms[0]
    # Minimum count-hjkl: three horizontal segments (3 ks each) + two count-j (2 ks each) = 13
    hjkl_min = 13
    assert room.par < hjkl_min, (
        f"seed={seed}: par={room.par} should be < hjkl_min={hjkl_min}"
    )


@pytest.mark.parametrize("seed", SEEDS)
def test_entry_and_exit_not_on_void(seed):
    d = build_dungeon_6(seed)
    room = d.rooms[0]
    void_cells = {
        (ru.row, ru.col + i)
        for ru in room.runes if ru.kind == 'void'
        for i in range(len(ru.symbols))
    }
    assert room.entry    not in void_cells, f"seed={seed}: entry is on a void cell"
    assert room.exit_pos not in void_cells, f"seed={seed}: exit is on a void cell"


@pytest.mark.parametrize("seed", SEEDS)
def test_exit_entity_at_exit_pos(seed):
    d = build_dungeon_6(seed)
    room = d.rooms[0]
    exit_ents = [e for e in room.entities if e.kind == 'exit']
    assert len(exit_ents) == 1, f"seed={seed}: expected 1 exit entity, got {len(exit_ents)}"
    e = exit_ents[0]
    assert (e.row, e.col) == room.exit_pos, (
        f"seed={seed}: exit entity at ({e.row},{e.col}) != exit_pos {room.exit_pos}"
    )


def test_anchor_W_at_fixed_position():
    """W anchor is always at row=1, col=53; char drawn from _L6_UNTYPABLE_PUNCT."""
    d = build_dungeon_6(42)
    room = d.rooms[0]
    anchor = room.rune_at(1, 53)
    assert anchor is not None, "Expected W-anchor rune at (1, 53)"
    assert ''.join(anchor.symbols) in _L6_UNTYPABLE_PUNCT, (
        f"Expected untypable char at (1,53), got {''.join(anchor.symbols)!r}"
    )


def test_anchor_B_at_fixed_position():
    """B anchor is always at row=4, col=3; char drawn from _L6_UNTYPABLE_PUNCT."""
    d = build_dungeon_6(42)
    room = d.rooms[0]
    anchor = room.rune_at(4, 3)
    assert anchor is not None, "Expected B-anchor rune at (4, 3)"
    assert ''.join(anchor.symbols) in _L6_UNTYPABLE_PUNCT, (
        f"Expected untypable char at (4,3), got {''.join(anchor.symbols)!r}"
    )


@pytest.mark.parametrize("seed", SEEDS)
def test_anchors_use_distinct_chars(seed):
    """All 4 anchor chars (W4 pair + B1 pair) must be distinct across seeds."""
    d = build_dungeon_6(seed)
    room = d.rooms[0]
    w4a = room.rune_at(1, 53)
    w4b = room.rune_at(1, 54)
    b1a = room.rune_at(4, 3)
    b1b = room.rune_at(4, 4)
    chars = [
        ''.join(r.symbols) for r in (w4a, w4b, b1a, b1b) if r is not None
    ]
    assert len(chars) == len(set(chars)), (
        f"seed={seed}: anchor chars not all distinct: {chars}"
    )


def test_exit_at_end_of_E4_group():
    """exit_pos must be at col 51, row 7 (end of 'output=data[n]._key')."""
    d = build_dungeon_6(42)
    room = d.rooms[0]
    assert room.exit_pos == (7, 51), f"Expected exit at (7,51), got {room.exit_pos}"


@pytest.mark.parametrize("seed", SEEDS)
def test_void_guard_at_C2_left_end(seed):
    """Void rune at (4, 1) makes 0/^ on C2 land on void (death), blocking the shortcut."""
    d = build_dungeon_6(seed)
    room = d.rooms[0]
    void_rune = room.rune_at(4, 1)
    assert void_rune is not None, f"seed={seed}: no rune at (4, 1)"
    assert void_rune.kind == 'void', (
        f"seed={seed}: rune at (4,1) is kind={void_rune.kind!r}, expected 'void'"
    )


@pytest.mark.parametrize("seed", SEEDS)
def test_void_guard_at_C1_right_end(seed):
    """Void rune at (1, 55) blocks $ shortcut on C1 top row."""
    d = build_dungeon_6(seed)
    room = d.rooms[0]
    void_rune = room.rune_at(1, 55)
    assert void_rune is not None, f"seed={seed}: no rune at (1, 55)"
    assert void_rune.kind == 'void', (
        f"seed={seed}: rune at (1,55) is kind={void_rune.kind!r}, expected 'void'"
    )


def test_dollar_on_C1_reaches_void():
    """$ from C1 entry (1,1) reaches the void guard at col 55 (rightmost passable cell)."""
    from engine.motion import _cross_water
    d = build_dungeon_6(42)
    room = d.rooms[0]
    best = None
    for c in range(2, room.cols):
        if not _cross_water(room, 1, c):
            break
        best = c
    assert best == 55, f"$ from col 1 reaches col {best}, expected 55 (void at rightmost)"
    void_rune = room.rune_at(1, best)
    assert void_rune is not None and void_rune.kind == 'void', (
        f"col {best} should be void guard, got {void_rune}"
    )
