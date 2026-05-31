"""Level 13 (id 13) — The Sentence Corridor: dungeon correctness tests.

Layout: two sentence rows (1 and 3) split by a stone wall row (2). Five
sentences, scattered horizontally and divided by wall-gaps:

    row 1:  S1 ·gap· S2 ·gap· S3 [door][exit]
    row 3:  S4 ·gap· S5 [key]

Teaches ) and ( — within a row AND across rows — plus that they land on
sentence STARTS (the key/door sit at sentence ENDS, so the player must add $).
) is hard-forced: the key is on a 2nd-of-row sentence behind a wall-gap, and the
line/screen/paragraph jumps the player already knows only reach a row's FIRST
sentence. ( is the shortest backtrack but — like H/M/L — can be substituted by
gg/{n}G + ), so it is taught/incentivized rather than infinitely forced.
"""
import math
import pytest
from engine.world import CellType
from engine.motion import _sentence_starts_all
from generation.dungeon_gen import (
    build_dungeon_13,
    _dijkstra_par_L13,
    _L13_ROWS, _L13_COLS, _L13_ENTRY, _L13_EXIT,
    _L13_DOOR_POS, _L13_KEY_POS, _L13_SEP_ROW, _L13_SENTENCES,
)

SEEDS = [1, 42, 999, 12345, 2**20 + 7]

_PAR    = 9
_ANSWER = '4) $ x 3( $ p l'


# ── structure ──────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("seed", SEEDS)
def test_dimensions(seed):
    room = build_dungeon_13(seed).rooms[0]
    assert (room.rows, room.cols) == (_L13_ROWS, _L13_COLS)


@pytest.mark.parametrize("seed", SEEDS)
def test_entry_and_exit_passable(seed):
    room = build_dungeon_13(seed).rooms[0]
    assert room.cells[_L13_ENTRY[0]][_L13_ENTRY[1]] == CellType.CORRIDOR
    assert room.cells[_L13_EXIT[0]][_L13_EXIT[1]] == CellType.CORRIDOR
    assert room.spawn_pos == _L13_ENTRY
    assert room.exit_pos == _L13_EXIT


@pytest.mark.parametrize("seed", SEEDS)
def test_separator_row_is_all_wall(seed):
    """The stone row between the two sentence rows blocks all j/k crossing,
    so the only way between rows is a sentence jump."""
    room = build_dungeon_13(seed).rooms[0]
    assert all(ct == CellType.WALL for ct in room.cells[_L13_SEP_ROW])


@pytest.mark.parametrize("seed", SEEDS)
def test_entities_present(seed):
    room = build_dungeon_13(seed).rooms[0]
    placed = {(e.kind, e.row, e.col) for e in room.entities}
    assert ('exit', *_L13_EXIT) in placed
    assert ('locked_door', *_L13_DOOR_POS) in placed
    assert ('floor_key', *_L13_KEY_POS) in placed


@pytest.mark.parametrize("seed", SEEDS)
def test_sentences_present_with_terminators(seed):
    room = build_dungeon_13(seed).rooms[0]
    for (r, c, text) in _L13_SENTENCES:
        ru = room.char_run_at(r, c)
        assert ru is not None and ru.symbols == tuple(text), (
            f"seed={seed}: sentence at ({r},{c}) is wrong"
        )
        assert ru.symbols[-1] in '.!?', (
            f"seed={seed}: sentence at ({r},{c}) has no .!? terminator"
        )


@pytest.mark.parametrize("seed", SEEDS)
def test_sentence_starts_in_reading_order(seed):
    """Five sentences, in reading order S1..S5 across the two rows."""
    room = build_dungeon_13(seed).rooms[0]
    assert _sentence_starts_all(room) == [(r, c) for (r, c, _t) in _L13_SENTENCES]


# ── the $-for-ends lesson: key / door are at sentence ENDS, not starts ────────────

@pytest.mark.parametrize("seed", SEEDS)
def test_key_and_door_are_at_sentence_ends_not_starts(seed):
    """) and ( land on sentence STARTS; the key and door sit just past the last
    char of S5 / S3, so neither is reachable by a jump alone — $ is needed."""
    room = build_dungeon_13(seed).rooms[0]
    starts = set(_sentence_starts_all(room))
    assert _L13_KEY_POS not in starts
    assert _L13_DOOR_POS not in starts
    assert _L13_KEY_POS == (3, 40 + len('A good joint needs no mortar.'))
    assert _L13_DOOR_POS == (1, 50 + len('At a dot, or a bang!'))


# ── par / budget / answer ────────────────────────────────────────────────────────

@pytest.mark.parametrize("seed", SEEDS)
def test_par_budget_answer(seed):
    room = build_dungeon_13(seed).rooms[0]
    assert room.par == _PAR
    assert room.budget == math.ceil(_PAR * 1.4)
    assert room.answer == _ANSWER


@pytest.mark.parametrize("seed", SEEDS)
def test_answer_uses_both_parens(seed):
    """The optimal path teaches BOTH ) (forward) and ( (backward)."""
    room = build_dungeon_13(seed).rooms[0]
    toks = room.answer.split()
    assert any(t.endswith(')') for t in toks), room.answer
    assert any(t.endswith('(') for t in toks), room.answer


# ── command necessity ───────────────────────────────────────────────────────────

@pytest.mark.parametrize("seed", SEEDS)
def test_close_paren_required(seed):
    """Without ), the key (a 2nd-of-row sentence behind a wall-gap) is
    unreachable, so the door can't be unlocked and the exit can't be reached.
    Line/screen jumps reach only a row's first sentence, so ) is genuinely
    required even though the solver doesn't model them."""
    room = build_dungeon_13(seed).rooms[0]
    cost = _dijkstra_par_L13(room, no_close=True)
    assert cost is None or cost > room.budget, (
        f"seed={seed}: without ), cost={cost} <= budget={room.budget}"
    )


@pytest.mark.parametrize("seed", SEEDS)
def test_open_paren_is_the_shortest_backtrack(seed):
    """The optimal solve spends ( on the backtrack from the key to the door —
    `3(` (( from S5's end returns to S5 start, then S4, then S3)."""
    room = build_dungeon_13(seed).rooms[0]
    assert _dijkstra_par_L13(room) == _PAR
    assert '3(' in room.answer.split()
