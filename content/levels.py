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
        'key': 'dungeon_14_the_inscription_halls',
        'name': 'The Inscription Halls',
        'commands': 'i a I A',
        'unlocks_after': 13,
    },
    {
        'id': 15,
        'key': 'dungeon_15_the_sculpting_chambers',
        'name': 'The Sculpting Chambers',
        'commands': 'o O s S',
        'unlocks_after': 14,
    },
    {
        'id': 151,
        'key': 'dungeon_15.1_the_warden_unbound',
        'name': 'The Warden Unbound',
        'commands': '(boss)',
        'commands_level': 15,
        'unlocks_after': 15,
        'type': 'boss',
    },
    {
        'id': 16,
        'key': 'dungeon_16_the_operators_vault',
        'name': "The Operator's Vault",
        'commands': 'd c',
        'unlocks_after': 151,
    },
    {
        'id': 17,
        'key': 'dungeon_17_the_whole_line_annex',
        'name': 'The Whole-Line Annex',
        'commands': 'dd cc',
        'unlocks_after': 16,
    },
    {
        'id': 18,
        'key': 'dungeon_18_the_undo_sanctum',
        'name': 'The Undo Sanctum',
        'commands': 'u Ctrl-R',
        'unlocks_after': 17,
    },
    {
        'id': 19,
        'key': 'dungeon_19_the_word_chiseler',
        'name': 'The Word Chiseler',
        'commands': 'dw de db dW dE dB',
        'unlocks_after': 18,
    },
    {
        'id': 20,
        'key': 'dungeon_20_the_delimiter_chamber',
        'name': 'The Delimiter Chamber',
        'commands': 'dt df dT dF',
        'unlocks_after': 19,
    },
    {
        'id': 21,
        'key': 'dungeon_21_the_line_edge_hall',
        'name': 'The Line-Edge Hall',
        'commands': 'd$ D d0 d^',
        'unlocks_after': 20,
    },
    {
        'id': 22,
        'key': 'dungeon_22_the_file_sweep',
        'name': 'The File Sweep',
        'commands': 'dG dgg',
        'unlocks_after': 21,
    },
    {
        'id': 23,
        'key': 'dungeon_23_the_yank_vault',
        'name': 'The Yank Vault',
        'commands': 'y yy',
        'unlocks_after': 22,
    },
    {
        'id': 24,
        'key': 'dungeon_24_the_paste_halls',
        'name': 'The Paste Halls',
        'commands': 'p P',
        'unlocks_after': 23,
    },
    {
        'id': 25,
        'key': 'dungeon_25_the_fine_liftmaster',
        'name': 'The Fine Liftmaster',
        'commands': 'yw ye y$',
        'unlocks_after': 24,
    },
    {
        'id': 26,
        'key': 'dungeon_26_the_change_corridor',
        'name': 'The Change Corridor',
        'commands': 'cw ce cb',
        'unlocks_after': 25,
    },
    {
        'id': 27,
        'key': 'dungeon_27_the_delimiter_change',
        'name': 'The Delimiter Change',
        'commands': 'ct cf cT cF',
        'unlocks_after': 26,
    },
    {
        'id': 271,
        'key': 'dungeon_27.1_the_warden_manifold',
        'name': 'The Warden Manifold',
        'commands': '(boss)',
        'commands_level': 27,
        'unlocks_after': 27,
        'type': 'boss',
    },
    {
        'id': 28,
        'key': 'dungeon_28_the_overwrite_halls',
        'name': 'The Overwrite Halls',
        'commands': 'r R',
        'unlocks_after': 271,
    },
    {
        'id': 29,
        'key': 'dungeon_29_the_case_chambers',
        'name': 'The Case Chambers',
        'commands': '~',
        'unlocks_after': 28,
    },
    {
        'id': 30,
        'key': 'dungeon_30_the_echo_vault',
        'name': 'The Echo Vault',
        'commands': '.',
        'unlocks_after': 29,
    },
    {
        'id': 31,
        'key': 'dungeon_31_the_case_operator_halls',
        'name': 'The Case Operator Halls',
        'commands': 'g~ gU gu',
        'unlocks_after': 30,
    },
    {
        'id': 32,
        'key': 'dungeon_32_the_join_corridor',
        'name': 'The Join Corridor',
        'commands': 'J gJ',
        'unlocks_after': 31,
    },
    {
        'id': 33,
        'key': 'dungeon_33_the_indent_halls',
        'name': 'The Indent Halls',
        'commands': '>> <<',
        'unlocks_after': 32,
    },
    {
        'id': 34,
        'key': 'dungeon_34_the_operator_indent',
        'name': 'The Operator Indent',
        'commands': '>{m} <{m} =',
        'unlocks_after': 33,
    },
    {
        'id': 341,
        'key': 'dungeon_34.1_the_warden_scrivener',
        'name': 'The Warden Scrivener',
        'commands': '(boss)',
        'commands_level': 34,
        'unlocks_after': 34,
        'type': 'boss',
    },
    {
        'id': 35,
        'key': 'dungeon_35_the_word_enclosure',
        'name': 'The Word Enclosure',
        'commands': 'iw aw',
        'unlocks_after': 341,
    },
    {
        'id': 36,
        'key': 'dungeon_36_the_bracket_enclosure',
        'name': 'The Bracket Enclosure',
        'commands': 'i( a( i[ a[ i{ a{',
        'unlocks_after': 35,
    },
    {
        'id': 37,
        'key': 'dungeon_37_the_quote_enclosure',
        'name': 'The Quote Enclosure',
        'commands': 'i" a" i\' a\'',
        'unlocks_after': 36,
    },
    {
        'id': 38,
        'key': 'dungeon_38_the_tag_enclosure',
        'name': 'The Tag Enclosure',
        'commands': 'it at',
        'unlocks_after': 37,
    },
    {
        'id': 39,
        'key': 'dungeon_39_the_paragraph_enclosure',
        'name': 'The Paragraph Enclosure',
        'commands': 'is as ip ap',
        'unlocks_after': 38,
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
        cmds += ['{', '}', '(', ')']
    if effective >= 14:
        cmds += ['insert']
    if effective >= 15:
        cmds += ['s', 'S']
    if effective >= 16:
        cmds += ['d', 'c']
    if effective >= 23:
        cmds += ['y']
    if effective >= 24:
        cmds += ['register']
    if effective >= 28:
        cmds += ['r', 'R']
    if effective >= 29:
        cmds += ['~']
    if effective >= 30:
        cmds += ['dot']
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
