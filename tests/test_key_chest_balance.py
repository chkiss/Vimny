"""Verify key/lock balance and pre-assignment for all playable levels.

Rules enforced here:
  1. chest_key count == locked_door count  (every lock has exactly one key)
  2. No plain 'chest' entities             (loot must be pre-assigned at generation)

The dummy dungeon is an admin sandbox and is intentionally excluded.
"""
import pytest
from generation.dungeon_gen import (
    build_dungeon_0, build_dungeon_1, build_dungeon_2,
    build_dungeon_3, build_dungeon_4,
)

SEEDS = [1, 42, 999, 12345, 2**20 + 7]

_BUILDERS = {
    0: build_dungeon_0,
    1: build_dungeon_1,
    2: build_dungeon_2,
    3: build_dungeon_3,
    4: build_dungeon_4,
}


def _room(level, seed):
    return _BUILDERS[level](seed).rooms[0]


@pytest.mark.parametrize('seed', SEEDS)
@pytest.mark.parametrize('level', sorted(_BUILDERS))
def test_chest_keys_match_locked_doors(level, seed):
    room    = _room(level, seed)
    n_keys  = sum(1 for e in room.entities if e.kind == 'chest_key'   and e.alive)
    n_locks = sum(1 for e in room.entities if e.kind == 'locked_door' and e.alive)
    assert n_keys == n_locks, (
        f'level {level} seed {seed}: {n_keys} chest_key(s) vs {n_locks} locked_door(s)'
    )


@pytest.mark.parametrize('seed', SEEDS)
@pytest.mark.parametrize('level', sorted(_BUILDERS))
def test_no_untyped_chests(level, seed):
    room    = _room(level, seed)
    unnamed = [e for e in room.entities if e.kind == 'chest' and e.alive]
    assert not unnamed, (
        f'level {level} seed {seed}: {len(unnamed)} untyped chest(s) — '
        'use chest_key or chest_scroll instead'
    )
