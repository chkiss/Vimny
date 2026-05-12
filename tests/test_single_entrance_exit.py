"""All levels must have exactly one entrance and one exit entity."""
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


@pytest.mark.parametrize("level", sorted(_BUILDERS))
@pytest.mark.parametrize("seed", SEEDS)
def test_exactly_one_exit_entity(level, seed):
    room = _BUILDERS[level](seed).room
    exits = [e for e in room.entities if e.kind == 'exit']
    assert len(exits) == 1, (
        f"level={level} seed={seed}: expected 1 exit entity, got {len(exits)} "
        f"at {[(e.row, e.col) for e in exits]}"
    )


@pytest.mark.parametrize("level", sorted(_BUILDERS))
@pytest.mark.parametrize("seed", SEEDS)
def test_exit_entity_matches_exit_pos(level, seed):
    room = _BUILDERS[level](seed).room
    exits = [e for e in room.entities if e.kind == 'exit']
    assert len(exits) >= 1, f"level={level} seed={seed}: no exit entity"
    assert (exits[0].row, exits[0].col) == room.exit_pos, (
        f"level={level} seed={seed}: exit entity at ({exits[0].row},{exits[0].col}) "
        f"!= exit_pos {room.exit_pos}"
    )


@pytest.mark.parametrize("level", sorted(_BUILDERS))
@pytest.mark.parametrize("seed", SEEDS)
def test_entry_is_passable(level, seed):
    room = _BUILDERS[level](seed).room
    r, c = room.entry
    assert room.is_passable(r, c), (
        f"level={level} seed={seed}: entry {room.entry} is not passable"
    )
