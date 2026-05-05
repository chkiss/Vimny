"""Answer-path correctness: each token must be an atomic keystroke for the level."""
import re
import pytest
from generation.dungeon_gen import build_dungeon_0, build_dungeon_1

SEEDS = [0, 1, 42, 999, 2**20 + 7]

_COUNT_RE = re.compile(r'^\d+[hjkl]$')   # e.g. '44l', '3j', '2h'


def _answer_keystroke_cost(answer: str, has_count: bool) -> int:
    """Count keystrokes in an answer path under the given command model."""
    total = 0
    for token in answer.split():
        if has_count and _COUNT_RE.match(token):
            # count-N + motion key = len(digits) + 1
            total += len(token) - 1 + 1   # = len(token)
        else:
            total += 1
    return total


class TestLevel0AnswerPath:
    """Level 0 has only h/j/k/l.  Answer must not use count notation."""

    def test_no_count_notation(self):
        for seed in SEEDS:
            room = build_dungeon_0(seed).room
            for token in room.answer.split():
                assert not _COUNT_RE.match(token), (
                    f"seed={seed}: count notation '{token}' in level-0 answer "
                    f"(player hasn't learned count motions)"
                )

    def test_token_count_equals_par(self):
        for seed in SEEDS:
            room = build_dungeon_0(seed).room
            tokens = room.answer.split()
            assert len(tokens) == room.par, (
                f"seed={seed}: answer has {len(tokens)} tokens but par={room.par}"
            )


class TestLevel1AnswerPath:
    """Level 1 has h/j/k/l + ^$0.  Answer must not use count notation."""

    def test_no_count_notation(self):
        for seed in SEEDS:
            room = build_dungeon_1(seed).room
            for token in room.answer.split():
                assert not _COUNT_RE.match(token), (
                    f"seed={seed}: count notation '{token}' in level-1 answer"
                )

    def test_token_count_equals_par(self):
        for seed in SEEDS:
            room = build_dungeon_1(seed).room
            tokens = room.answer.split()
            assert len(tokens) == room.par, (
                f"seed={seed}: answer has {len(tokens)} tokens but par={room.par}"
            )
