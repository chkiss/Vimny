"""Prove every hjkl direction is required to complete Level 0."""
from collections import deque
import pytest
from generation.dungeon_gen import build_dungeon_0

SEEDS = [1, 42, 999, 12345, 2**20 + 7]
DELTA = {'h': (0, -1), 'j': (1, 0), 'k': (-1, 0), 'l': (0, 1)}
LEVEL_0_COMMANDS = set('hjkl')


def can_reach(room, entry, goal, allowed_keys):
    moves = [DELTA[k] for k in allowed_keys]
    void = {
        (ru.row, ru.col + i)
        for ru in room.runes if ru.kind == 'void'
        for i in range(len(ru.symbols))
    }
    seen = {entry}
    q = deque([entry])
    while q:
        pos = q.popleft()
        if pos == goal:
            return True
        r, c = pos
        for dr, dc in moves:
            nb = (r + dr, c + dc)
            if nb not in seen and room.is_passable(*nb) and nb not in void:
                seen.add(nb)
                q.append(nb)
    return False


@pytest.mark.parametrize("seed", SEEDS)
def test_exit_is_reachable(seed):
    d = build_dungeon_0(seed)
    room = d.room
    assert can_reach(room, room.entry, room.exit_pos, LEVEL_0_COMMANDS), \
        f"seed={seed}: exit unreachable with full hjkl"


@pytest.mark.parametrize("seed,omit", [(s, c) for s in SEEDS for c in sorted(LEVEL_0_COMMANDS)])
def test_each_command_is_necessary(seed, omit):
    d = build_dungeon_0(seed)
    room = d.room
    restricted = LEVEL_0_COMMANDS - {omit}
    assert not can_reach(room, room.entry, room.exit_pos, restricted), \
        f"seed={seed}: exit reachable without '{omit}' — command is not required"
