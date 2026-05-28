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
        'commands': '(boss)',
        'commands_level': 5,
        'unlocks_after': 5,
        'type': 'boss',
    },
    {
        'id': 6,
        'key': 'dungeon_06_the_wardens_precision',
        'name': "The Warden's Precision",
        'commands': 'v',
        'unlocks_after': 51,
    },
    {
        'id': 7,
        'key': 'dungeon_07_the_word_forge',
        'name': 'The WORD Forge',
        'commands': 'W B E',
        'unlocks_after': 6,
    },
    {
        'id': 8,
        'key': 'dungeon_08_the_backward_vaults',
        'name': 'The Backward Vaults',
        'commands': 'ge gE',
        'unlocks_after': 7,
    },
    {
        'id': 9,
        'key': 'dungeon_09_the_file_vaults',
        'name': 'The File Vaults',
        'commands': 'G gg',
        'unlocks_after': 8,
    },
    {
        'id': 10,
        'key': 'dungeon_10_the_screen_vault',
        'name': 'The Screen Vault',
        'commands': 'H M L',
        'unlocks_after': 9,
    },
    {
        'id': 12,
        'key': 'dungeon_12_the_bracket_vaults',
        'name': 'The Bracket Vaults',
        'commands': '%',
        'unlocks_after': 10,
    },
    {
        'id': 13,
        'key': 'dungeon_13_the_runic_archives',
        'name': 'The Runic Archives',
        'commands': '} { ) (',
        'unlocks_after': 12,
    },
    {
        'id': 14,
        'key': 'dungeon_14_the_sentence_corridor',
        'name': 'The Sentence Corridor',
        'commands': ') (',
    },
    {
        'id': 141,
        'key': 'dungeon_14.1_the_warden_surveyor',
        'name': 'The Warden Surveyor',
        'commands': '(boss)',
        'commands_level': 14,
        'unlocks_after': 14,
        'type': 'boss',
    },
    {
        'id': 15,
        'key': 'dungeon_15_the_seekers_labyrinth',
        'name': "The Seekers' Labyrinth",
        'commands': '/ ? n N',
        'unlocks_after': 141,
    },
    {
        'id': 16,
        'key': 'dungeon_16_the_waypoint_sanctum',
        'name': 'The Waypoint Sanctum',
        'commands': "m ' `",
    },
    {
        'id': 17,
        'key': 'dungeon_17_the_archivists_library',
        'name': "The Archivist's Library",
        'commands': ':e :set',
    },
    {
        'id': 171,
        'key': 'dungeon_17.1_the_warden_pathfinder',
        'name': 'The Warden Pathfinder',
        'commands': '(boss)',
        'commands_level': 17,
        'unlocks_after': 17,
        'type': 'boss',
    },
    {
        'id': 18,
        'key': 'dungeon_18_the_operators_vault',
        'name': "The Operator's Vault",
        'commands': 'd c',
        'unlocks_after': 171,
    },
    {
        'id': 19,
        'key': 'dungeon_19_the_whole_line_annex',
        'name': 'The Whole-Line Annex',
        'commands': 'dd cc D S',
    },
    {
        'id': 20,
        'key': 'dungeon_20_the_quartermaster',
        'name': 'The Quartermaster',
        'commands': 'y yy p P',
    },
    {
        'id': 21,
        'key': 'dungeon_21_the_undo_sanctum',
        'name': 'The Undo Sanctum',
        'commands': 'u',
    },
    {
        'id': 22,
        'key': 'dungeon_22_the_echo_vault',
        'name': 'The Echo Vault',
        'commands': '.',
    },
    {
        'id': 221,
        'key': 'dungeon_22.1_the_warden_manifold',
        'name': 'The Warden Manifold',
        'commands': '(boss)',
        'commands_level': 22,
        'unlocks_after': 22,
        'type': 'boss',
    },
    {
        'id': 23,
        'key': 'dungeon_23_the_inscription_halls',
        'name': 'The Inscription Halls',
        'commands': 'i a',
        'unlocks_after': 221,
    },
    {
        'id': 24,
        'key': 'dungeon_24_the_sculpting_chambers',
        'name': 'The Sculpting Chambers',
        'commands': 'I A o O',
    },
    {
        'id': 25,
        'key': 'dungeon_25_the_overwrite_halls',
        'name': 'The Overwrite Halls',
        'commands': 'r R',
    },
    {
        'id': 26,
        'key': 'dungeon_26_the_case_chambers',
        'name': 'The Case Chambers',
        'commands': '~ g~ gU gu',
    },
    {
        'id': 27,
        'key': 'dungeon_27_the_joiners_gate',
        'name': "The Joiner's Gate",
        'commands': 'J gJ',
    },
    {
        'id': 28,
        'key': 'dungeon_28_the_alignment_halls',
        'name': 'The Alignment Halls',
        'commands': '>> <<',
    },
    {
        'id': 29,
        'key': 'dungeon_29_the_indentation_sanctum',
        'name': 'The Indentation Sanctum',
        'commands': '>{m} <{m} =',
    },
    {
        'id': 291,
        'key': 'dungeon_29.1_the_warden_scrivener',
        'name': 'The Warden Scrivener',
        'commands': '(boss)',
        'commands_level': 29,
        'unlocks_after': 29,
        'type': 'boss',
    },
    {
        'id': 30,
        'key': 'dungeon_30_the_word_enclosure',
        'name': 'The Word Enclosure',
        'commands': 'iw aw',
        'unlocks_after': 291,
    },
    {
        'id': 31,
        'key': 'dungeon_31_the_bracket_enclosure',
        'name': 'The Bracket Enclosure',
        'commands': 'i( a(',
    },
    {
        'id': 32,
        'key': 'dungeon_32_the_brace_square_enclosure',
        'name': 'The Brace & Square Enclosure',
        'commands': 'i[ a[ i{ a{',
    },
    {
        'id': 33,
        'key': 'dungeon_33_the_quote_enclosure',
        'name': 'The Quote Enclosure',
        'commands': 'i" a" i\' a\'',
    },
    {
        'id': 34,
        'key': 'dungeon_34_the_tag_enclosure',
        'name': 'The Tag Enclosure',
        'commands': 'it at',
    },
    {
        'id': 35,
        'key': 'dungeon_35_the_sentence_enclosure',
        'name': 'The Sentence Enclosure',
        'commands': 'is as',
    },
    {
        'id': 36,
        'key': 'dungeon_36_the_paragraph_enclosure',
        'name': 'The Paragraph Enclosure',
        'commands': 'ip ap',
    },
    {
        'id': 361,
        'key': 'dungeon_36.1_the_grandmasters_sanctum',
        'name': "The Grandmaster's Sanctum",
        'commands': '(boss)',
        'commands_level': 36,
        'unlocks_after': 36,
        'type': 'boss',
    },
    {
        'id': 37,
        'key': 'dungeon_37_the_spellwrights_forge',
        'name': "The Spellwright's Forge",
        'commands': ':s///',
        'unlocks_after': 361,
    },
    {
        'id': 38,
        'key': 'dungeon_38_the_hall_of_echoes',
        'name': 'The Hall of Echoes',
        'commands': 'q @ "',
    },
    {
        'id': 381,
        'key': 'dungeon_38.1_the_warden_eternal',
        'name': 'The Warden Eternal',
        'commands': '(boss)',
        'commands_level': 38,
        'unlocks_after': 38,
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
    """Returns 'dungeon', 'reliquary', or 'boss'. Defaults to 'dungeon'."""
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
        cmds += ['visual']
    if effective >= 7:
        cmds += ['W', 'B', 'E']
    if effective >= 8:
        cmds += ['ge', 'gE']
    if effective >= 9:
        cmds += ['G', 'gg']
    if effective >= 10:
        cmds += ['H', 'M', 'L']
    if effective >= 12:
        cmds += ['%']
    if effective >= 13:
        cmds += ['{', '}']
    if effective >= 14:
        cmds += ['(', ')']
    if effective >= 15:
        cmds += ['/', '*']
    if effective >= 16:
        cmds += ['mark']
    if effective >= 18:
        cmds += ['d', 'c', 's']
    if effective >= 19:
        cmds += ['S']
    if effective >= 20:
        cmds += ['y', 'register']
    if effective >= 22:
        cmds += ['dot']
    if effective >= 23:
        cmds += ['insert']
    if effective >= 25:
        cmds += ['r', 'R']
    if effective >= 26:
        cmds += ['~', 'gU', 'gu', 'g~']
    if effective >= 28:
        cmds += ['>', '<']
    if effective >= 30:
        cmds += ['iw', 'aw']
    if effective >= 31:
        cmds += ['i(', 'a(']
    if effective >= 32:
        cmds += ['i[', 'a[', 'i{', 'a{']
    if effective >= 33:
        cmds += ['i"', 'a"', "i'", "a'"]
    if effective >= 34:
        cmds += ['it', 'at']
    if effective >= 35:
        cmds += ['is', 'as']
    if effective >= 36:
        cmds += ['ip', 'ap']
    if effective >= 38:
        cmds += ['q', '@', 'reg_named']
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
