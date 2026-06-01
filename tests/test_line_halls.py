"""The Line Halls: dungeon correctness tests.

Teaching goal: $ (line end), 0 (bare line start), ^ (first non-blank char).

A fixed three-hall vertical serpentine joined by one-cell doorways at
alternating ends.  No counts exist yet, so walking costs one key per cell and
each hall forces exactly one line motion:

  Hall A (row 1) → $   spawn at the left; the only way down is at the far right
  Hall B (row 3) → 0   arrive right; the doorway down is at the bare left margin,
                       but the hall is packed with runes so ^ stops mid-hall
  Hall C (row 5) → ^   arrive left; the exit is one l right of the first carved
                       rune, behind an unmarked indent, so 0 lands short and $
                       overshoots

The structure and par (8) are seed-independent; the carved runes packing each
hall randomize per seed (kinds, lengths, positions), so the structural anchors
that drive the forcing stay fixed while the decoration varies.
"""
import math
import pytest
from engine.world import CellType
from generation.dungeon_gen import (
    build_dungeon_line_halls, _bfs_par_line,
    _LINE_HALLS_ROWS, _LINE_HALLS_COLS, _LINE_HALLS_LEFT, _LINE_HALLS_RIGHT,
    _LINE_HALLS_A_ROW, _LINE_HALLS_B_ROW, _LINE_HALLS_C_ROW,
    _LINE_HALLS_SPAWN, _LINE_HALLS_EXIT, _LINE_HALLS_DOORS,
    _LINE_HALLS_C_FIRST_RUNE,
)

from tests import SEEDS

_HALL_ROWS = (_LINE_HALLS_A_ROW, _LINE_HALLS_B_ROW, _LINE_HALLS_C_ROW)


# ── Structure ─────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("seed", SEEDS)
def test_dimensions(seed):
    room = build_dungeon_line_halls(seed).room
    assert (room.rows, room.cols) == (_LINE_HALLS_ROWS, _LINE_HALLS_COLS)


@pytest.mark.parametrize("seed", SEEDS)
def test_spawn_and_exit_passable(seed):
    room = build_dungeon_line_halls(seed).room
    assert room.spawn_pos == _LINE_HALLS_SPAWN
    assert room.exit_pos == _LINE_HALLS_EXIT
    for (r, c) in (room.spawn_pos, room.exit_pos):
        assert room.cells[r][c] in (CellType.FLOOR, CellType.CORRIDOR)


@pytest.mark.parametrize("seed", SEEDS)
def test_single_exit_at_exit_pos(seed):
    room = build_dungeon_line_halls(seed).room
    exits = [e for e in room.entities if e.kind == 'exit']
    assert len(exits) == 1
    assert (exits[0].row, exits[0].col) == _LINE_HALLS_EXIT == room.exit_pos


# ── Par / budget ────────────────────────────────────────────────────────────

@pytest.mark.parametrize("seed", SEEDS)
def test_par_matches_bfs(seed):
    room = build_dungeon_line_halls(seed).room
    assert room.par == _bfs_par_line(room)


def test_par_is_deterministic():
    """The layout is fixed, so par is 8 ($ jj 0 jj ^ l) for every seed."""
    assert {build_dungeon_line_halls(s).room.par for s in SEEDS} == {8}


@pytest.mark.parametrize("seed", SEEDS)
def test_budget_is_ceil_par_times_1_4(seed):
    room = build_dungeon_line_halls(seed).room
    assert room.budget == math.ceil(room.par * 1.4)


# ── Command necessity (drop one line motion → cheapest solve must exceed budget) ─

@pytest.mark.parametrize("seed", SEEDS)
def test_dollar_is_necessary(seed):
    """Without $, crossing Hall A means walking the whole row (no counts yet)."""
    room = build_dungeon_line_halls(seed).room
    assert _bfs_par_line(room, allow=('0', '^')) > room.budget


@pytest.mark.parametrize("seed", SEEDS)
def test_zero_is_necessary(seed):
    """Without 0, the rune-packed Hall B can only reach its left doorway by
    walking — ^ stops on the first rune, short of the margin."""
    room = build_dungeon_line_halls(seed).room
    assert _bfs_par_line(room, allow=('$', '^')) > room.budget


@pytest.mark.parametrize("seed", SEEDS)
def test_caret_is_necessary(seed):
    """Without ^, the indented Hall C exit can only be reached by walking in
    from the margin (0 lands short, $ overshoots)."""
    room = build_dungeon_line_halls(seed).room
    assert _bfs_par_line(room, allow=('$', '0')) > room.budget


# ── Rune / void-safety invariants ─────────────────────────────────────────────

@pytest.mark.parametrize("seed", SEEDS)
def test_each_hall_is_densely_runed(seed):
    """Each hall is packed with carved runes (not a bare corridor)."""
    room = build_dungeon_line_halls(seed).room
    for hr in _HALL_ROWS:
        n = sum(1 for ru in room.char_runs if ru.row == hr)
        assert n >= 4, f"row {hr} has only {n} runes"


@pytest.mark.parametrize("seed", SEEDS)
def test_rune_kinds_are_valid(seed):
    room = build_dungeon_line_halls(seed).room
    assert {ru.kind for ru in room.char_runs} <= {'ancient', 'verdant', 'void', 'ember'}


def test_runes_randomize_across_seeds():
    """The floor runes vary by seed (scattered per seed, like the other levels)."""
    def sig(s):
        room = build_dungeon_line_halls(s).room
        return tuple((ru.row, ru.col, ru.kind, len(ru.symbols))
                     for ru in sorted(room.char_runs, key=lambda r: (r.row, r.col)))
    assert len({sig(s) for s in SEEDS}) == len(SEEDS), "rune layout did not vary across seeds"


def test_all_four_rune_kinds_appear_across_seeds():
    """Across the seed set, every hall shows all four rune kinds."""
    for hr in _HALL_ROWS:
        kinds = set()
        for s in SEEDS:
            kinds |= {ru.kind for ru in build_dungeon_line_halls(s).room.char_runs
                      if ru.row == hr}
        assert kinds == {'ancient', 'verdant', 'void', 'ember'}, f"row {hr}: {kinds}"


@pytest.mark.parametrize("seed", SEEDS)
def test_leftmost_rune_each_hall_is_non_void(seed):
    """apply_motion ^ halts on the first char_run of ANY kind while the par
    solver skips void; keeping the leftmost rune non-void makes them agree (and
    makes the ^ landing survivable)."""
    room = build_dungeon_line_halls(seed).room
    for hr in _HALL_ROWS:
        row_runes = sorted((ru for ru in room.char_runs if ru.row == hr),
                           key=lambda ru: ru.col)
        assert row_runes, f"row {hr} has no runes"
        assert row_runes[0].kind != 'void', f"leftmost rune on row {hr} is void"


@pytest.mark.parametrize("seed", SEEDS)
def test_caret_target_left_of_unmarked_exit(seed):
    """^ in Hall C lands on the first rune; the exit is exactly one cell to its
    right and carries no char_run (char and exit do not obscure each other)."""
    room = build_dungeon_line_halls(seed).room
    fr_r, fr_c = _LINE_HALLS_C_FIRST_RUNE
    assert room.char_run_at(fr_r, fr_c) is not None
    assert _LINE_HALLS_EXIT == (fr_r, fr_c + 1)
    assert room.char_run_at(*_LINE_HALLS_EXIT) is None


@pytest.mark.parametrize("seed", SEEDS)
def test_no_landing_cell_is_a_void_rune(seed):
    """Void death fires only on the final landing cell, so every cell the
    optimal path lands on — both hall ends, the doorways and the ^ target —
    must not be a void rune."""
    room = build_dungeon_line_halls(seed).room
    L, R = _LINE_HALLS_LEFT, _LINE_HALLS_RIGHT
    landings = [
        _LINE_HALLS_SPAWN,
        (_LINE_HALLS_A_ROW, R), (_LINE_HALLS_B_ROW, R),       # $ lands / B entry
        (_LINE_HALLS_B_ROW, L), (_LINE_HALLS_C_ROW, L),       # 0 lands / C entry
        _LINE_HALLS_C_FIRST_RUNE, _LINE_HALLS_EXIT,           # ^ target, then exit
        *_LINE_HALLS_DOORS,
    ]
    for (r, c) in landings:
        ru = room.char_run_at(r, c)
        assert ru is None or ru.kind != 'void', f"landing ({r},{c}) is a void rune"
