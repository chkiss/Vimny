"""Level definitions and command curriculum.

Revised curriculum per LEVELS_PLAN.md (clean renumber, S5 splits, new bosses).
Teaching levels use sequential ids 0-37 (id 11 is skipped — reserved for the
Reliquary bonus, mirroring the original convention). Bosses are `x.1`
(id = f"{N}1", e.g. boss after level 4 -> id 41, key dungeon_04.1...).

NOTE (code-sync deferred): the level IDs/keys here are intentionally ahead of
`main.py` `_build_dungeon` dispatch, the `build_dungeon_N` generators, the
`test_level_N.py` files, and `engine/command_guard` token vocabulary. See
LEVELS_PLAN.md Part 4 for the migration checklist.
"""
from __future__ import annotations

LEVELS = [
    # ── Act I — Navigation Foundations ──────────────────────────────────────
    {'id': 0,  'key': 'dungeon_00_the_first_cave',          'name': 'The First Cave',          'commands': 'h j k l  :w :q :q!'},
    {'id': 1,  'key': 'dungeon_01_the_line_halls',          'name': 'The Line Halls',          'commands': '^ $ 0', 'unlocks_after': 0},
    {'id': 11, 'key': 'dungeon_01.1_the_reliquary',         'name': 'The Reliquary',           'commands': '', 'commands_level': 1, 'unlocks_after': 1, 'type': 'reliquary'},
    {'id': 2,  'key': 'dungeon_02_the_counting_crypts',     'name': 'The Counting Crypts',     'commands': '[count]  x', 'unlocks_after': 1},
    {'id': 3,  'key': 'dungeon_03_the_rune_halls',          'name': 'The Rune Halls',          'commands': 'w b e', 'unlocks_after': 2},
    {'id': 4,  'key': 'dungeon_04_the_character_cataracts', 'name': 'The Character Cataracts', 'commands': 'f F t T  ; ,', 'unlocks_after': 3},
    {'id': 41, 'key': 'dungeon_04.1_the_wardens_keep',      'name': "The Warden's Keep",       'commands': '', 'commands_level': 4, 'unlocks_after': 4, 'type': 'boss'},

    # ── Act II — Extended & Structural Motion ───────────────────────────────
    {'id': 5,  'key': 'dungeon_05_the_word_forge',          'name': 'The WORD Forge',          'commands': 'W B E', 'unlocks_after': 41},
    {'id': 6,  'key': 'dungeon_06_the_backward_vaults',     'name': 'The Backward Vaults',     'commands': 'ge gE', 'unlocks_after': 5},
    {'id': 7,  'key': 'dungeon_07_the_file_vaults',         'name': 'The File Vaults',         'commands': 'G gg', 'unlocks_after': 6},
    {'id': 8,  'key': 'dungeon_08_the_screen_vault',        'name': 'The Screen Vault',        'commands': 'H M L', 'unlocks_after': 7},
    {'id': 9,  'key': 'dungeon_09_the_void_rift',           'name': 'The Void Rift',           'commands': '} {', 'unlocks_after': 8},
    {'id': 10, 'key': 'dungeon_10_the_sentence_corridor',   'name': 'The Sentence Corridor',   'commands': ') (', 'unlocks_after': 9},
    {'id': 101,'key': 'dungeon_10.1_the_warden_surveyor',   'name': 'The Warden Surveyor',     'commands': '', 'commands_level': 10, 'unlocks_after': 10, 'type': 'boss'},

    # ── Act III — Navigation Power Tools ────────────────────────────────────
    {'id': 12, 'key': 'dungeon_12_the_mirror_temple',       'name': 'The Mirror Temple',       'commands': '%', 'unlocks_after': 101},
    {'id': 13, 'key': 'dungeon_13_the_seekers_labyrinth',   'name': "The Seekers' Labyrinth",  'commands': '/ ? n N', 'unlocks_after': 12},
    {'id': 14, 'key': 'dungeon_14_the_waypoint_sanctum',    'name': 'The Waypoint Sanctum',    'commands': "m ' `", 'unlocks_after': 13},
    {'id': 15, 'key': 'dungeon_15_the_archivists_library',  'name': "The Archivist's Library", 'commands': ':e :set', 'unlocks_after': 14},
    {'id': 151,'key': 'dungeon_15.1_the_warden_pathfinder', 'name': 'The Warden Pathfinder',   'commands': '', 'commands_level': 15, 'unlocks_after': 15, 'type': 'boss'},

    # ── Act IV — Visual Mode & Operator Grammar ─────────────────────────────
    {'id': 16, 'key': 'dungeon_16_the_sight_sanctum',       'name': 'The Sight Sanctum',       'commands': 'v', 'unlocks_after': 151},
    {'id': 17, 'key': 'dungeon_17_the_operators_vault',     'name': "The Operator's Vault",    'commands': 'd c  (x=dl  s=cl)', 'unlocks_after': 16},
    {'id': 18, 'key': 'dungeon_18_the_whole_line_annex',    'name': 'The Whole-Line Annex',    'commands': 'dd cc  D S', 'unlocks_after': 17},
    {'id': 19, 'key': 'dungeon_19_the_quartermaster',       'name': 'The Quartermaster',       'commands': 'y yy  p P', 'unlocks_after': 18},
    {'id': 20, 'key': 'dungeon_20_the_undo_sanctum',        'name': 'The Undo Sanctum',        'commands': 'u  (Ctrl-R: scroll)', 'unlocks_after': 19},
    {'id': 21, 'key': 'dungeon_21_the_echo_vault',          'name': 'The Echo Vault',          'commands': '.', 'unlocks_after': 20},
    {'id': 211,'key': 'dungeon_21.1_the_warden_manifold',   'name': 'The Warden Manifold',     'commands': '', 'commands_level': 21, 'unlocks_after': 21, 'type': 'boss'},

    # ── Act V — Insert-Mode Construction & Editing ──────────────────────────
    {'id': 22, 'key': 'dungeon_22_the_inscription_halls',   'name': 'The Inscription Halls',   'commands': 'i a', 'unlocks_after': 211},
    {'id': 23, 'key': 'dungeon_23_the_sculpting_chambers',  'name': 'The Sculpting Chambers',  'commands': 'I A  o O', 'unlocks_after': 22},
    {'id': 24, 'key': 'dungeon_24_the_overwrite_halls',     'name': 'The Overwrite Halls',     'commands': 'r R', 'unlocks_after': 23},
    {'id': 25, 'key': 'dungeon_25_the_case_chambers',       'name': 'The Case Chambers',       'commands': '~  g~ gU gu', 'unlocks_after': 24},
    {'id': 26, 'key': 'dungeon_26_the_joiners_gate',        'name': "The Joiner's Gate",       'commands': 'J gJ', 'unlocks_after': 25},
    {'id': 27, 'key': 'dungeon_27_the_alignment_halls',     'name': 'The Alignment Halls',     'commands': '>> <<', 'unlocks_after': 26},
    {'id': 28, 'key': 'dungeon_28_the_indentation_sanctum', 'name': 'The Indentation Sanctum', 'commands': '>{m} <{m} =', 'unlocks_after': 27},
    {'id': 281,'key': 'dungeon_28.1_the_warden_scrivener',  'name': 'The Warden Scrivener',    'commands': '', 'commands_level': 28, 'unlocks_after': 28, 'type': 'boss'},

    # ── Act VI — Text Objects ───────────────────────────────────────────────
    {'id': 29, 'key': 'dungeon_29_the_word_enclosure',          'name': 'The Word Enclosure',          'commands': 'iw aw', 'unlocks_after': 281},
    {'id': 30, 'key': 'dungeon_30_the_bracket_enclosure',       'name': 'The Bracket Enclosure',       'commands': 'i( a(', 'unlocks_after': 29},
    {'id': 31, 'key': 'dungeon_31_the_brace_square_enclosure',  'name': 'The Brace & Square Enclosure','commands': 'i[ a[ i{ a{', 'unlocks_after': 30},
    {'id': 32, 'key': 'dungeon_32_the_quote_enclosure',         'name': 'The Quote Enclosure',         'commands': 'i" a" i\' a\'', 'unlocks_after': 31},
    {'id': 33, 'key': 'dungeon_33_the_tag_enclosure',           'name': 'The Tag Enclosure',           'commands': 'it at', 'unlocks_after': 32},
    {'id': 34, 'key': 'dungeon_34_the_sentence_enclosure',      'name': 'The Sentence Enclosure',      'commands': 'is as', 'unlocks_after': 33},
    {'id': 35, 'key': 'dungeon_35_the_paragraph_enclosure',     'name': 'The Paragraph Enclosure',     'commands': 'ip ap', 'unlocks_after': 34},
    {'id': 351,'key': 'dungeon_35.1_the_grandmasters_sanctum',  'name': "The Grandmaster's Sanctum",   'commands': '', 'commands_level': 35, 'unlocks_after': 35, 'type': 'boss'},

    # ── Act VII — Mastery ───────────────────────────────────────────────────
    {'id': 36, 'key': 'dungeon_36_the_spellwrights_forge', 'name': "The Spellwright's Forge", 'commands': ':s/{}/{}/', 'unlocks_after': 351},
    {'id': 37, 'key': 'dungeon_37_the_hall_of_echoes',     'name': 'The Hall of Echoes',      'commands': 'q @ "', 'unlocks_after': 36},
    {'id': 371,'key': 'dungeon_37.1_the_warden_eternal',   'name': 'The Warden Eternal',      'commands': '', 'commands_level': 37, 'unlocks_after': 37, 'type': 'boss'},

    # ── Admin ───────────────────────────────────────────────────────────────
    {'id': 99, 'key': 'dummy_dungeon', 'name': 'Dummy Dungeon', 'commands': 'd x s y p yy P', 'admin_only': True},
]


def level_type(level_id: int) -> str:
    """Returns 'dungeon', 'reliquary', or 'boss'. Defaults to 'dungeon'."""
    level = next((l for l in LEVELS if l['id'] == level_id), None)
    return (level or {}).get('type', 'dungeon')


def is_reliquary(level_id: int) -> bool:
    return level_type(level_id) == 'reliquary'


def known_commands(level_id: int) -> list:
    """All commands available at this level (cumulative).

    Gate thresholds are the new teaching-level ids (id 11 = Reliquary is skipped).
    Token vocabulary for the NEW families (search/mark/cmdmode/join/indent/
    textobj/substitute/macro) must be wired into engine/command_guard during the
    code-sync phase — see LEVELS_PLAN.md Part 4.
    """
    level = next((l for l in LEVELS if l['id'] == level_id), None)
    effective = level.get('commands_level', level_id) if level else level_id
    cmds = ['h', 'j', 'k', 'l']
    if effective >= 1:  cmds += ['^', '$', '0']
    if effective >= 2:  cmds += ['count', 'x']
    if effective >= 3:  cmds += ['w', 'b', 'e']
    if effective >= 4:  cmds += ['f', 'F', 't', 'T', ';', ',']
    if effective >= 5:  cmds += ['W', 'B', 'E']
    if effective >= 6:  cmds += ['ge', 'gE']
    if effective >= 7:  cmds += ['G', 'gg']
    if effective >= 8:  cmds += ['H', 'M', 'L']
    if effective >= 9:  cmds += ['{', '}']
    if effective >= 10: cmds += ['(', ')']
    if effective >= 12: cmds += ['%']
    if effective >= 13: cmds += ['search']            # / ? n N
    if effective >= 14: cmds += ['mark']              # m ' `
    if effective >= 15: cmds += ['cmdmode']           # :e :set
    if effective >= 16: cmds += ['visual']            # v
    if effective >= 17: cmds += ['d', 'c', 's']       # operators (x=dl from L2; s=cl)
    if effective >= 18: cmds += ['D', 'S']            # dd/cc (via d/c) + D/S shorthands
    if effective >= 19: cmds += ['y', 'p', 'P']       # yank + paste
    if effective >= 20: cmds += ['u']                 # undo (redo = scroll reward)
    if effective >= 21: cmds += ['dot']               # .
    if effective >= 22: cmds += ['insert']            # i a
    if effective >= 23: cmds += ['open']              # I A o O
    if effective >= 24: cmds += ['r', 'R']            # replace
    if effective >= 25: cmds += ['~', 'case']         # ~ + g~ gU gu
    if effective >= 26: cmds += ['join']              # J gJ
    if effective >= 27: cmds += ['indent']            # >> <<
    if effective >= 28: cmds += ['indent_motion']     # >{m} <{m} =
    if effective >= 29: cmds += ['textobj']           # iw aw
    if effective >= 30: cmds += ['to_paren']          # i( a(
    if effective >= 31: cmds += ['to_bracket']        # i[ a[ i{ a{
    if effective >= 32: cmds += ['to_quote']          # i" a" i' a'
    if effective >= 33: cmds += ['to_tag']            # it at
    if effective >= 34: cmds += ['to_sentence']       # is as
    if effective >= 35: cmds += ['to_paragraph']      # ip ap
    if effective >= 36: cmds += ['substitute']        # :s
    if effective >= 37: cmds += ['macro', 'register'] # q @ "
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
