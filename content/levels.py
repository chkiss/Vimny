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
        'id': 11,
        'key': 'dungeon_01.1_the_reliquary',
        'name': 'The Reliquary',
        'commands': 'hjkl ^ $ 0',
        'commands_level': 1,
        'unlocks_after': 1,
        'type': 'reliquary',
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
        'id': 4,
        'key': 'dungeon_04_the_character_cataracts',
        'name': 'The Character Cataracts',
        'commands': 'f F t T',
    },
    {
        'id': 5,
        'key': 'dungeon_05_the_goblin_gauntlet',
        'name': 'The Goblin Gauntlet',
        'commands': '; ,',
    },
    {
        'id': 51,
        'key': 'dungeon_05.1_the_wardens_keep',
        'name': "The Warden's Keep",
        'commands': '(miniboss)',
        'commands_level': 5,
        'unlocks_after': 5,
        'type': 'boss',
    },
    {
        'id': 6,
        'key': 'dungeon_06_the_word_forge',
        'name': 'The WORD Forge',
        'commands': 'W B E',
        'unlocks_after': 51,
    },
    {
        'id': 121,
        'key': 'dungeon_12.1_the_scrivenors_loom',
        'name': "The Scrivener's Loom",
        'commands': '(miniboss)',
        'commands_level': 12,
        'unlocks_after': 12,
        'type': 'boss',
    },
    {
        'id': 171,
        'key': 'dungeon_17.1_the_erasure_engine',
        'name': 'The Erasure Engine',
        'commands': '(miniboss)',
        'commands_level': 17,
        'unlocks_after': 17,
        'type': 'boss',
    },
    {
        'id': 231,
        'key': 'dungeon_23.1_the_palimpsests_chamber',
        'name': "The Palimpsest's Chamber",
        'commands': '(miniboss)',
        'commands_level': 23,
        'unlocks_after': 23,
        'type': 'boss',
    },
    {
        'id': 331,
        'key': 'dungeon_33.1_the_symmetrals_sanctum',
        'name': "The Symmetral's Sanctum",
        'commands': '(miniboss)',
        'commands_level': 33,
        'unlocks_after': 33,
        'type': 'boss',
    },
    {
        'id': 99,
        'key': 'dummy_dungeon',
        'name': 'Dummy Dungeon',
        'commands': 'd x s y p yy P',
        'admin_only': True,
    },
]


def level_type(level_id: int) -> str:
    """Returns 'dungeon' or 'reliquary'. Defaults to 'dungeon' if not specified."""
    level = next((l for l in LEVELS if l['id'] == level_id), None)
    return (level or {}).get('type', 'dungeon')


def is_reliquary(level_id: int) -> bool:
    return level_type(level_id) == 'reliquary'


def known_commands(level_id: int) -> list:
    """All commands available at this level (cumulative)."""
    level = next((l for l in LEVELS if l['id'] == level_id), None)
    effective = level.get('commands_level', level_id) if level else level_id
    cmds = ['h', 'j', 'k', 'l']
    if effective >= 1:
        cmds += ['^', '$', '0']
    if effective >= 2:
        cmds += ['count', 'x']
    if effective >= 3:
        cmds += ['w', 'b', 'e']
    if effective >= 4:
        cmds += ['f', 'F', 't', 'T']
    if effective >= 5:
        cmds += [';', ',']
    if effective >= 6:
        cmds += ['W', 'B', 'E']
    return cmds


def is_unlocked(level_id: int, progress: dict, player_name: str = '') -> bool:
    if player_name == 'admin':
        return True
    level = next((l for l in LEVELS if l['id'] == level_id), None)
    if level and level.get('admin_only', False):
        return True
    if level_id == 0:
        return True
    unlock_after = level.get('unlocks_after', level_id - 1) if level else level_id - 1
    return progress.get(unlock_after, {}).get('complete', False)


def is_visible(level: dict, player_name: str) -> bool:
    return not level.get('admin_only', False) or player_name == 'admin'
