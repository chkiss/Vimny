# Vimny — a Vim-teaching dungeon crawler.
# Copyright (C) 2026 Chas Kissick
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""The Sentence Corridor: dungeon correctness tests.

Layout: two sentence rows (1 and 3) split by a stone wall row (2). Five
sentences, scattered horizontally and divided by wall-gaps:

    row 1:  S1 ·gap· S2 ·gap· S3 [door][exit]
    row 3:  S4 ·gap· S5 [key]

Teaches ) and ( — within a row AND across rows — plus that they land on
sentence STARTS (the key/door sit at sentence ENDS, so the player must add $).
) is hard-forced: the key is on a 2nd-of-row sentence behind a wall-gap, and the
line/screen jumps the player already knows only reach a row's FIRST sentence.
( is the shortest backtrack; the paragraph jumps { / } would otherwise undercut
it (cheaper cross-row jump), so a void trap line above S1 makes them land on a
void (a heart + bounce-back). ( can still be substituted by gg/{n}G + ), so it is
taught/incentivized rather than infinitely forced.
"""
import math
import pytest
from engine.world import CellType
from engine.motion import _sentence_starts_all
from generation.dungeon_gen import (
    build_dungeon_sentence_corridor,
    _par_sentence_corridor,
    _SENTENCE_CORRIDOR_ROWS, _SENTENCE_CORRIDOR_COLS, _SENTENCE_CORRIDOR_ENTRY, _SENTENCE_CORRIDOR_EXIT,
    _SENTENCE_CORRIDOR_DOOR_POS, _SENTENCE_CORRIDOR_KEY_POS, _SENTENCE_CORRIDOR_SEP_ROW, _SENTENCE_CORRIDOR_SENTENCES,
)

from tests import SEEDS

_PAR    = 9
_ANSWER = '4) $ x 3( $ p l'


# ── structure ──────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("seed", SEEDS)
def test_dimensions(seed):
    room = build_dungeon_sentence_corridor(seed).rooms[0]
    assert (room.rows, room.cols) == (_SENTENCE_CORRIDOR_ROWS, _SENTENCE_CORRIDOR_COLS)


@pytest.mark.parametrize("seed", SEEDS)
def test_entry_and_exit_passable(seed):
    room = build_dungeon_sentence_corridor(seed).rooms[0]
    assert room.cells[_SENTENCE_CORRIDOR_ENTRY[0]][_SENTENCE_CORRIDOR_ENTRY[1]] == CellType.CORRIDOR
    assert room.cells[_SENTENCE_CORRIDOR_EXIT[0]][_SENTENCE_CORRIDOR_EXIT[1]] == CellType.CORRIDOR
    assert room.spawn_pos == _SENTENCE_CORRIDOR_ENTRY
    assert room.exit_pos == _SENTENCE_CORRIDOR_EXIT


@pytest.mark.parametrize("seed", SEEDS)
def test_separator_row_is_all_impassable(seed):
    """The separator between the two sentence rows blocks all j/k crossing,
    so the only way between rows is a sentence jump. Since the 2026-07-18
    waterworks it is MISTED WATER (visible, scan-blocking) framed by the
    border walls — every cell impassable either way."""
    room = build_dungeon_sentence_corridor(seed).rooms[0]
    sep = _SENTENCE_CORRIDOR_SEP_ROW
    for c, ct in enumerate(room.cells[sep]):
        assert not room.is_passable(sep, c)
        if ct == CellType.WATER:
            assert (sep, c) in room.fog_cells    # the mist bars the scans


@pytest.mark.parametrize("seed", SEEDS)
def test_entities_present(seed):
    room = build_dungeon_sentence_corridor(seed).rooms[0]
    placed = {(e.kind, e.row, e.col) for e in room.entities}
    assert ('exit', *_SENTENCE_CORRIDOR_EXIT) in placed
    assert ('locked_door', *_SENTENCE_CORRIDOR_DOOR_POS) in placed
    assert ('floor_key', *_SENTENCE_CORRIDOR_KEY_POS) in placed


@pytest.mark.parametrize("seed", SEEDS)
def test_sentences_present_with_terminators(seed):
    room = build_dungeon_sentence_corridor(seed).rooms[0]
    for (r, c, text) in _SENTENCE_CORRIDOR_SENTENCES:
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
    room = build_dungeon_sentence_corridor(seed).rooms[0]
    assert _sentence_starts_all(room) == [(r, c) for (r, c, _t) in _SENTENCE_CORRIDOR_SENTENCES]


# ── the $-for-ends lesson: key / door are at sentence ENDS, not starts ────────────

@pytest.mark.parametrize("seed", SEEDS)
def test_key_and_door_are_at_sentence_ends_not_starts(seed):
    """) and ( land on sentence STARTS; the key and door sit just past the last
    char of S5 / S3, so neither is reachable by a jump alone — $ is needed."""
    room = build_dungeon_sentence_corridor(seed).rooms[0]
    starts = set(_sentence_starts_all(room))
    assert _SENTENCE_CORRIDOR_KEY_POS not in starts
    assert _SENTENCE_CORRIDOR_DOOR_POS not in starts
    assert _SENTENCE_CORRIDOR_KEY_POS == (3, 40 + len('A good joint needs no mortar.'))
    assert _SENTENCE_CORRIDOR_DOOR_POS == (1, 50 + len('At a dot, or a bang!'))


# ── par / budget / answer ────────────────────────────────────────────────────────

@pytest.mark.parametrize("seed", SEEDS)
def test_par_budget_answer(seed):
    room = build_dungeon_sentence_corridor(seed).rooms[0]
    assert room.par == _PAR
    assert room.budget == math.ceil(_PAR * 1.4)
    assert room.answer == _ANSWER


@pytest.mark.parametrize("seed", SEEDS)
def test_answer_uses_both_parens(seed):
    """The optimal path teaches BOTH ) (forward) and ( (backward)."""
    room = build_dungeon_sentence_corridor(seed).rooms[0]
    toks = room.answer.split()
    assert any(t.endswith(')') for t in toks), room.answer
    assert any(t.endswith('(') for t in toks), room.answer


# ── command necessity ───────────────────────────────────────────────────────────

@pytest.mark.parametrize("seed", SEEDS)
def test_close_paren_required(seed):
    """Without ), the key (a 2nd-of-row sentence behind a wall-gap) is
    unreachable, so the door can't be unlocked and the exit can't be reached.
    Line/screen jumps reach only a row's first sentence, and the cross-row { / }
    paragraph jumps land on the row-0 void trap, so ) is genuinely required even
    though the solver doesn't model those motions."""
    room = build_dungeon_sentence_corridor(seed).rooms[0]
    cost = _par_sentence_corridor(room, no_close=True)
    assert cost is None or cost > room.budget, (
        f"seed={seed}: without ), cost={cost} <= budget={room.budget}"
    )


@pytest.mark.parametrize("seed", SEEDS)
def test_open_paren_is_the_shortest_backtrack(seed):
    """The optimal solve spends ( on the backtrack from the key to the door —
    `3(` (( from S5's end returns to S5 start, then S4, then S3)."""
    room = build_dungeon_sentence_corridor(seed).rooms[0]
    assert _par_sentence_corridor(room) == _PAR
    assert '3(' in room.answer.split()
