"""Level definitions and command curriculum."""
from __future__ import annotations

LEVELS = [
    {
        'id': 0,
        'key': 'dungeon_00_the_first_cave',
        'name': 'The First Cave',
        'commands': 'h j k l',
    },
    {
        'id': 1,
        'key': 'dungeon_01_the_line_halls',
        'name': 'The Line Halls',
        'commands': '^ $ 0  :w :q :q!',
    },
    {
        'id': 2,
        'key': 'dungeon_02_the_counting_crypts',
        'name': 'The Counting Crypts',
        'commands': '[count] prefix',
    },
]


def known_commands(level_id: int) -> list:
    """All commands available at this level (cumulative)."""
    cmds = ['h', 'j', 'k', 'l']
    if level_id >= 1:
        cmds += ['^', '$', '0']
    if level_id >= 2:
        cmds += ['count', 'x']
    return cmds


def is_unlocked(level_id: int, progress: dict) -> bool:
    if level_id == 0:
        return True
    return progress.get(level_id - 1, {}).get('complete', False)
