"""The WORD Forge: dungeon correctness tests."""
import math
import heapq
import pytest
from generation.dungeon_gen import build_dungeon_word_forge, _dijkstra_par_WBE, _WORD_FORGE_UNTYPABLE_PUNCT

from tests import SEEDS


@pytest.mark.parametrize("seed", SEEDS)
def test_exit_is_reachable(seed):
    d = build_dungeon_word_forge(seed)
    room = d.rooms[0]
    assert room.exit_pos is not None
    par = _dijkstra_par_WBE(room)
    assert par is not None, f"seed={seed}: exit unreachable"


@pytest.mark.parametrize("seed", SEEDS)
def test_par_matches_dijkstra(seed):
    d = build_dungeon_word_forge(seed)
    room = d.rooms[0]
    expected = _dijkstra_par_WBE(room)
    assert room.par == expected, (
        f"seed={seed}: stored par {room.par} != Dijkstra {expected}"
    )


@pytest.mark.parametrize("seed", SEEDS)
def test_budget_is_ceil_par_times_1_4(seed):
    d = build_dungeon_word_forge(seed)
    room = d.rooms[0]
    assert room.budget == math.ceil(room.par * 1.4), (
        f"seed={seed}: budget={room.budget} but ceil(par*1.4)={math.ceil(room.par*1.4)}"
    )


@pytest.mark.parametrize("seed", SEEDS)
def test_par_is_ten(seed):
    """RT1 descent walls (3,54)/(3,55) force W on C1, C2-left void guards force B,
    and game-faithful solver semantics guarantee par=10 (4W 3j 4B 3j 4E)."""
    d = build_dungeon_word_forge(seed)
    room = d.rooms[0]
    assert room.par == 10, f"seed={seed}: expected par=10, got {room.par}"


@pytest.mark.parametrize("seed", SEEDS)
def test_answer_uses_WBE(seed):
    """Optimal answer must use W, B, and E (the WORD motions taught in The WORD Forge)."""
    d = build_dungeon_word_forge(seed)
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
    d = build_dungeon_word_forge(seed)
    room = d.rooms[0]
    # Minimum count-hjkl: three horizontal segments (3 ks each) + two count-j (2 ks each) = 13
    hjkl_min = 13
    assert room.par < hjkl_min, (
        f"seed={seed}: par={room.par} should be < hjkl_min={hjkl_min}"
    )


@pytest.mark.parametrize("seed", SEEDS)
def test_entry_and_exit_not_on_void(seed):
    d = build_dungeon_word_forge(seed)
    room = d.rooms[0]
    void_cells = {
        (ru.row, ru.col + i)
        for ru in room.char_runs if ru.kind == 'void'
        for i in range(len(ru.symbols))
    }
    assert room.spawn_pos    not in void_cells, f"seed={seed}: entry is on a void cell"
    assert room.exit_pos not in void_cells, f"seed={seed}: exit is on a void cell"


@pytest.mark.parametrize("seed", SEEDS)
def test_exit_entity_at_exit_pos(seed):
    d = build_dungeon_word_forge(seed)
    room = d.rooms[0]
    exit_ents = [e for e in room.entities if e.kind == 'exit']
    assert len(exit_ents) == 1, f"seed={seed}: expected 1 exit entity, got {len(exit_ents)}"
    e = exit_ents[0]
    assert (e.row, e.col) == room.exit_pos, (
        f"seed={seed}: exit entity at ({e.row},{e.col}) != exit_pos {room.exit_pos}"
    )


def test_anchor_W_at_fixed_position():
    """W anchor is always at row=1, col=53; char drawn from _WORD_FORGE_UNTYPABLE_PUNCT."""
    d = build_dungeon_word_forge(42)
    room = d.rooms[0]
    anchor = room.char_run_at(1, 53)
    assert anchor is not None, "Expected W-anchor rune at (1, 53)"
    assert ''.join(anchor.symbols) in _WORD_FORGE_UNTYPABLE_PUNCT, (
        f"Expected untypable char at (1,53), got {''.join(anchor.symbols)!r}"
    )


def test_anchor_B_at_fixed_position():
    """B anchor is always at row=4, col=3; char drawn from _WORD_FORGE_UNTYPABLE_PUNCT."""
    d = build_dungeon_word_forge(42)
    room = d.rooms[0]
    anchor = room.char_run_at(4, 3)
    assert anchor is not None, "Expected B-anchor rune at (4, 3)"
    assert ''.join(anchor.symbols) in _WORD_FORGE_UNTYPABLE_PUNCT, (
        f"Expected untypable char at (4,3), got {''.join(anchor.symbols)!r}"
    )


@pytest.mark.parametrize("seed", SEEDS)
def test_anchors_use_distinct_chars(seed):
    """All 4 anchor chars (W4 pair + B1 pair) must be distinct across seeds."""
    d = build_dungeon_word_forge(seed)
    room = d.rooms[0]
    w4a = room.char_run_at(1, 53)
    w4b = room.char_run_at(1, 54)
    b1a = room.char_run_at(4, 3)
    b1b = room.char_run_at(4, 4)
    chars = [
        ''.join(r.symbols) for r in (w4a, w4b, b1a, b1b) if r is not None
    ]
    assert len(chars) == len(set(chars)), (
        f"seed={seed}: anchor chars not all distinct: {chars}"
    )


def test_exit_at_end_of_E4_group():
    """exit_pos must be at col 51, row 7 (end of 'output=data[n]._key')."""
    d = build_dungeon_word_forge(42)
    room = d.rooms[0]
    assert room.exit_pos == (7, 51), f"Expected exit at (7,51), got {room.exit_pos}"


@pytest.mark.parametrize("seed", SEEDS)
def test_void_guard_at_C2_left_end(seed):
    """Void runes at (4,1) and (5,1) make 0/^ on either C2 row land on void
    (death), blocking the line-start shortcut and forcing B."""
    d = build_dungeon_word_forge(seed)
    room = d.rooms[0]
    for r, c in ((4, 1), (5, 1)):
        void_rune = room.char_run_at(r, c)
        assert void_rune is not None, f"seed={seed}: no rune at ({r}, {c})"
        assert void_rune.kind == 'void', (
            f"seed={seed}: rune at ({r},{c}) is kind={void_rune.kind!r}, expected 'void'"
        )


@pytest.mark.parametrize("seed", SEEDS)
def test_descent_walls_force_W_on_C1(seed):
    """RT1 descent walls at (3,54)/(3,55) leave col 53 as the only C1→C2 turn.
    W lands at col 53 (start of the W4 WORD); E lands at col 54 (into a wall)."""
    from engine.world import CellType
    d = build_dungeon_word_forge(seed)
    room = d.rooms[0]
    assert room.cells[3][54] == CellType.WALL, f"seed={seed}: (3,54) should be wall"
    assert room.cells[3][55] == CellType.WALL, f"seed={seed}: (3,55) should be wall"
    assert room.cells[3][53] == CellType.CORRIDOR, (
        f"seed={seed}: (3,53) must stay open — it is W's descent column"
    )


@pytest.mark.parametrize("seed", SEEDS)
def test_C1_right_end_has_no_void(seed):
    """The old C1 right-end void guards are gone — the descent walls replace them."""
    d = build_dungeon_word_forge(seed)
    room = d.rooms[0]
    for r, c in ((1, 55), (2, 55)):
        ru = room.char_run_at(r, c)
        assert ru is None or ru.kind != 'void', (
            f"seed={seed}: ({r},{c}) should no longer hold a void rune, got {ru}"
        )
