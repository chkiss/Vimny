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
    {
        'id': 3,
        'key': 'dungeon_03_the_rune_halls',
        'name': 'The Rune Halls',
        'commands': 'w b e',
    },
    {
        'id': 99,
        'key': 'dummy_dungeon',
        'name': 'Dummy Dungeon',
        'commands': 'd x s y p yy P',
        'admin_only': True,
    },
]


def known_commands(level_id: int) -> list:
    """All commands available at this level (cumulative)."""
    cmds = ['h', 'j', 'k', 'l']
    if level_id >= 1:
        cmds += ['^', '$', '0']
    if level_id >= 2:
        cmds += ['count', 'x']
    if level_id >= 3:
        cmds += ['w', 'b', 'e']
    return cmds


def is_unlocked(level_id: int, progress: dict, player_name: str = '') -> bool:
    if player_name == 'admin':
        return True
    level = next((l for l in LEVELS if l['id'] == level_id), None)
    if level and level.get('admin_only', False):
        return True
    if level_id == 0:
        return True
    return progress.get(level_id - 1, {}).get('complete', False)


def is_visible(level: dict, player_name: str) -> bool:
    return not level.get('admin_only', False) or player_name == 'admin'
