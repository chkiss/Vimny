"""Level 12 (id=12) — The Runic Archives: dungeon correctness tests.

Layout: 22 rows × 48 cols.
Main area cols 1–42; side room row 15 cols 43–46.

Blank rows (passable, no rune clusters): 1, 3, 5, 9, 15, 17, 19.
Content rows (≥1 rune cluster): 2, 4, 6, 7, 8, 10, 11, 12, 13, 14, 16, 18, 20.

floor_key at (5,1) — blank row above code block (rows 6-8 all non-blank).
locked_door at (15,43) — right-wall position at door row.
exit at (15,46) — inside side room.

Optimal path (par=7):  { x } } $ p $
  Spawn (9,20): { → (5,1) [key].  x picks up key.
                } → (9,1)  } → (15,1).  $ → (15,42).  p unlocks door.  $ → exit.
"""
import math
import pytest
from engine.world import CellType
from generation.dungeon_gen import (
    build_dungeon_runic_archives,
    _par_runic_archives,
    _RUNIC_ARCHIVES_ROWS, _RUNIC_ARCHIVES_COLS,
    _RUNIC_ARCHIVES_ENTRY, _RUNIC_ARCHIVES_EXIT,
    _RUNIC_ARCHIVES_KEY_POS, _RUNIC_ARCHIVES_DOOR_POS, _RUNIC_ARCHIVES_VOID_POS,
    _RUNIC_ARCHIVES_PAR, _RUNIC_ARCHIVES_ANSWER,
)

SEEDS = [1, 42, 999, 12345, 2**20 + 7]

_BLANK_ROWS   = (1, 3, 5, 9, 15, 17, 19)
_CONTENT_ROWS = (2, 4, 6, 7, 8, 10, 11, 12, 13, 14, 16, 18, 20)


# ── structural tests ──────────────────────────────────────────────────────────

@pytest.mark.parametrize("seed", SEEDS)
def test_dimensions(seed):
    room = build_dungeon_runic_archives(seed).rooms[0]
    assert room.rows == _RUNIC_ARCHIVES_ROWS
    assert room.cols == _RUNIC_ARCHIVES_COLS


@pytest.mark.parametrize("seed", SEEDS)
def test_entry_and_exit_passable(seed):
    room = build_dungeon_runic_archives(seed).rooms[0]
    r0, c0 = room.spawn_pos
    r1, c1 = room.exit_pos
    assert room.cells[r0][c0] == CellType.CORRIDOR, f"entry not CORRIDOR"
    assert room.cells[r1][c1] == CellType.CORRIDOR, f"exit not CORRIDOR"


@pytest.mark.parametrize("seed", SEEDS)
def test_exit_entity_at_exit_pos(seed):
    room = build_dungeon_runic_archives(seed).rooms[0]
    exits = [e for e in room.entities if e.kind == 'exit']
    assert len(exits) == 1
    assert (exits[0].row, exits[0].col) == _RUNIC_ARCHIVES_EXIT
    assert room.exit_pos == _RUNIC_ARCHIVES_EXIT


@pytest.mark.parametrize("seed", SEEDS)
def test_key_entity_at_key_pos(seed):
    room = build_dungeon_runic_archives(seed).rooms[0]
    keys = [e for e in room.entities if e.kind == 'floor_key']
    assert len(keys) == 1, f"seed={seed}: expected 1 floor_key, got {len(keys)}"
    assert (keys[0].row, keys[0].col) == _RUNIC_ARCHIVES_KEY_POS


@pytest.mark.parametrize("seed", SEEDS)
def test_door_entity_at_door_pos(seed):
    room = build_dungeon_runic_archives(seed).rooms[0]
    doors = [e for e in room.entities if e.kind == 'locked_door']
    assert len(doors) == 1, f"seed={seed}: expected 1 locked_door, got {len(doors)}"
    assert (doors[0].row, doors[0].col) == _RUNIC_ARCHIVES_DOOR_POS


@pytest.mark.parametrize("seed", SEEDS)
def test_void_at_correct_position(seed):
    room = build_dungeon_runic_archives(seed).rooms[0]
    ru = room.char_run_at(_RUNIC_ARCHIVES_VOID_POS[0], _RUNIC_ARCHIVES_VOID_POS[1])
    assert ru is not None and ru.kind == 'void', f"seed={seed}: no void at {_RUNIC_ARCHIVES_VOID_POS}"


# ── blank and content rows ────────────────────────────────────────────────────

@pytest.mark.parametrize("seed", SEEDS)
def test_blank_rows_have_no_runes(seed):
    """All blank rows must have zero rune clusters."""
    room = build_dungeon_runic_archives(seed).rooms[0]
    for row in _BLANK_ROWS:
        for c in range(_RUNIC_ARCHIVES_COLS):
            assert room.char_run_at(row, c) is None, (
                f"seed={seed}: unexpected rune at ({row},{c})"
            )


@pytest.mark.parametrize("seed", SEEDS)
def test_blank_rows_are_passable(seed):
    room = build_dungeon_runic_archives(seed).rooms[0]
    for row in _BLANK_ROWS:
        assert any(room.is_passable(row, c) for c in range(_RUNIC_ARCHIVES_COLS)), (
            f"seed={seed}: blank row {row} has no passable cells"
        )


@pytest.mark.parametrize("seed", SEEDS)
def test_content_rows_have_runes(seed):
    """Every content row must have at least one rune cluster (non-blank)."""
    room = build_dungeon_runic_archives(seed).rooms[0]
    for row in _CONTENT_ROWS:
        has_rune = any(room.char_run_at(row, c) is not None for c in range(_RUNIC_ARCHIVES_COLS))
        assert has_rune, f"seed={seed}: content row {row} has no rune clusters"


# ── par and budget ────────────────────────────────────────────────────────────

@pytest.mark.parametrize("seed", SEEDS)
def test_par_matches_dijkstra(seed):
    room = build_dungeon_runic_archives(seed).rooms[0]
    computed = _par_runic_archives(room)
    assert room.par == computed, f"seed={seed}: room.par={room.par} Dijkstra={computed}"


@pytest.mark.parametrize("seed", SEEDS)
def test_budget_is_ceil_par_times_1_4(seed):
    room = build_dungeon_runic_archives(seed).rooms[0]
    assert room.budget == math.ceil(room.par * 1.4)


def test_par_is_correct():
    """Par must equal _RUNIC_ARCHIVES_PAR=7 for all seeds; answer must match _RUNIC_ARCHIVES_ANSWER."""
    for seed in SEEDS:
        room = build_dungeon_runic_archives(seed).rooms[0]
        assert room.par == _RUNIC_ARCHIVES_PAR, f"seed={seed}: par={room.par} != {_RUNIC_ARCHIVES_PAR}"
        assert room.answer == _RUNIC_ARCHIVES_ANSWER, f"seed={seed}: answer={room.answer!r}"


# ── answer uses brace motions ─────────────────────────────────────────────────

@pytest.mark.parametrize("seed", SEEDS)
def test_answer_uses_both_brace_directions(seed):
    """`{` and `}` must both appear in room.answer."""
    room = build_dungeon_runic_archives(seed).rooms[0]
    tokens = room.answer.split()
    assert '{' in tokens, f"seed={seed}: '{{' missing from {room.answer!r}"
    assert '}' in tokens, f"seed={seed}: '}}' missing from {room.answer!r}"


# ── brace necessity ───────────────────────────────────────────────────────────

@pytest.mark.parametrize("seed", SEEDS)
def test_brace_required(seed):
    """Without {{ and }}, the cost exceeds par.

    The optimal brace path (7 ks) beats the best hjkl/$-only path (10 ks):
    10j from key row 5 to door row 15 costs 3 ks; } } costs only 2 ks.
    """
    room = build_dungeon_runic_archives(seed).rooms[0]
    cost_no_brace = _par_runic_archives(room, disable_brace=True)
    assert cost_no_brace is None or cost_no_brace > room.par, (
        f"seed={seed}: without {{/}}, cost={cost_no_brace} <= par={room.par}"
    )
