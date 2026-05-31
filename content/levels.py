"""Level definitions and command curriculum.

Identity is the immutable ``slug``.  ``id`` is **transitional** — it is being
removed as part of the slug migration; new code should key off ``slug``.

Per level:
  slug      — immutable identity (used by builders, tests, saves, scrolls, poems)
  name      — display name
  teaches   — the gated command TOKENS this level introduces (drives gating)
  commands  — middle-column display string (may diverge from teaches: shows
              keystrokes not tokens, e.g. 'v' not 'visual'; descriptive forms)
  type      — 'dungeon' (default) | 'boss' | 'reliquary'
  after     — for boss/reliquary sub-levels: the slug they hang off (→ 'x.1')
  admin_only— hidden sandbox

The display number is DERIVED (see display_number): teaching levels number
sequentially is NOT assumed — we keep an explicit transitional `id` whose value
is the current shipped number, and derive 'x.1' for sub-levels.  known_commands
unions `teaches` in curriculum (list) order, so reordering LEVELS reorders the
curriculum with no per-level renumbering.

Always-on (never gated, not in `teaches`): u, :w, :q, :q!.
Not yet gated (no token): :e :set (archivist), :s/// (spellwright), = (indent).
"""
from __future__ import annotations

LEVELS = [
    {'id': 0,   'slug': 'first_cave',          'name': 'The First Cave',           'key': 'dungeon_00_the_first_cave',           'commands': 'h j k l u :w :q :q!', 'teaches': ['h', 'j', 'k', 'l']},
    {'id': 1,   'slug': 'line_halls',          'name': 'The Line Halls',           'key': 'dungeon_01_the_line_halls',           'commands': '^ $ 0',               'teaches': ['^', '$', '0']},
    {'id': 11,  'slug': 'reliquary',           'name': 'The Reliquary',            'key': 'dungeon_01.1_the_reliquary',          'commands': '"',     'type': 'reliquary', 'after': 'line_halls',         'teaches': []},
    {'id': 2,   'slug': 'counting_crypts',     'name': 'The Counting Crypts',      'key': 'dungeon_02_the_counting_crypts',      'commands': '[count] prefix',      'teaches': ['count', 'x']},
    {'id': 3,   'slug': 'rune_halls',          'name': 'The Rune Halls',           'key': 'dungeon_03_the_rune_halls',           'commands': 'w b e',               'teaches': ['w', 'b', 'e']},
    {'id': 4,   'slug': 'character_cataracts', 'name': 'The Character Cataracts',  'key': 'dungeon_04_the_character_cataracts',  'commands': 'f F t T',             'teaches': ['f', 'F', 't', 'T']},
    {'id': 5,   'slug': 'goblin_gauntlet',     'name': 'The Goblin Gauntlet',      'key': 'dungeon_05_the_goblin_gauntlet',      'commands': '; , p',               'teaches': [';', ',', 'p']},
    {'id': 51,  'slug': 'wardens_keep',        'name': "The Warden's Keep",        'key': 'dungeon_05.1_the_wardens_keep',       'type': 'boss', 'after': 'goblin_gauntlet',       'teaches': []},
    {'id': 6,   'slug': 'word_forge',          'name': 'The WORD Forge',           'key': 'dungeon_06_the_word_forge',           'commands': 'W B E',               'teaches': ['W', 'B', 'E']},
    {'id': 7,   'slug': 'backward_vaults',     'name': 'The Backward Vaults',      'key': 'dungeon_07_the_backward_vaults',      'commands': 'ge gE',               'teaches': ['ge', 'gE']},
    {'id': 8,   'slug': 'lineheads',           'name': 'The Lineheads',            'key': 'dungeon_08_the_lineheads',            'commands': 'G gg',                'teaches': ['G', 'gg']},
    {'id': 9,   'slug': 'screen_vault',        'name': 'The Screen Vault',         'key': 'dungeon_09_the_screen_vault',         'commands': 'H M L',               'teaches': ['H', 'M', 'L']},
    {'id': 10,  'slug': 'bracket_vaults',      'name': 'The Bracket Vaults',       'key': 'dungeon_10_the_bracket_vaults',       'commands': '%',                   'teaches': ['%']},
    {'id': 12,  'slug': 'runic_archives',      'name': 'The Runic Archives',       'key': 'dungeon_12_the_runic_archives',       'commands': '} {',                 'teaches': ['{', '}']},
    {'id': 13,  'slug': 'sentence_corridor',   'name': 'The Sentence Corridor',    'key': 'dungeon_13_the_sentence_corridor',    'commands': ') (',                 'teaches': ['(', ')']},
    {'id': 131, 'slug': 'warden_surveyor',     'name': 'The Warden Surveyor',      'key': 'dungeon_13.1_the_warden_surveyor',    'type': 'boss', 'after': 'sentence_corridor',     'teaches': []},
    {'id': 14,  'slug': 'sight_sanctum',       'name': 'The Sight Sanctum',        'key': 'dungeon_14_the_sight_sanctum',        'commands': 'v',                   'teaches': ['visual']},
    {'id': 15,  'slug': 'seekers_labyrinth',   'name': "The Seekers' Labyrinth",   'key': 'dungeon_15_the_seekers_labyrinth',    'commands': '/ ? n N',             'teaches': ['/', '*']},
    {'id': 16,  'slug': 'waypoint_sanctum',    'name': 'The Waypoint Sanctum',     'key': 'dungeon_16_the_waypoint_sanctum',     'commands': "m ' `",               'teaches': ['mark']},
    {'id': 17,  'slug': 'archivists_library',  'name': "The Archivist's Library",  'key': 'dungeon_17_the_archivists_library',   'commands': ':e :set',             'teaches': []},
    {'id': 171, 'slug': 'warden_pathfinder',   'name': 'The Warden Pathfinder',    'key': 'dungeon_17.1_the_warden_pathfinder',  'type': 'boss', 'after': 'archivists_library',    'teaches': []},
    {'id': 18,  'slug': 'operators_vault',     'name': "The Operator's Vault",     'key': 'dungeon_18_the_operators_vault',      'commands': 'd c',                 'teaches': ['d', 'c', 's']},
    {'id': 19,  'slug': 'whole_line_annex',    'name': 'The Whole-Line Annex',     'key': 'dungeon_19_the_whole_line_annex',     'commands': 'dd cc D S',           'teaches': ['S']},
    {'id': 20,  'slug': 'quartermaster',       'name': 'The Quartermaster',        'key': 'dungeon_20_the_quartermaster',        'commands': 'y yy P',              'teaches': ['y', 'P', 'register']},
    {'id': 21,  'slug': 'undo_sanctum',        'name': 'The Undo Sanctum',         'key': 'dungeon_21_the_undo_sanctum',         'teaches': []},
    {'id': 22,  'slug': 'echo_vault',          'name': 'The Echo Vault',           'key': 'dungeon_22_the_echo_vault',           'commands': '.',                   'teaches': ['dot']},
    {'id': 221, 'slug': 'warden_manifold',     'name': 'The Warden Manifold',      'key': 'dungeon_22.1_the_warden_manifold',    'type': 'boss', 'after': 'echo_vault',            'teaches': []},
    {'id': 23,  'slug': 'inscription_halls',   'name': 'The Inscription Halls',    'key': 'dungeon_23_the_inscription_halls',    'commands': 'i a',                 'teaches': ['insert']},
    {'id': 24,  'slug': 'sculpting_chambers',  'name': 'The Sculpting Chambers',   'key': 'dungeon_24_the_sculpting_chambers',   'commands': 'I A o O',             'teaches': []},
    {'id': 25,  'slug': 'overwrite_halls',     'name': 'The Overwrite Halls',      'key': 'dungeon_25_the_overwrite_halls',      'commands': 'r R',                 'teaches': ['r', 'R']},
    {'id': 26,  'slug': 'case_chambers',       'name': 'The Case Chambers',        'key': 'dungeon_26_the_case_chambers',        'commands': '~ g~ gU gu',          'teaches': ['~', 'gU', 'gu', 'g~']},
    {'id': 27,  'slug': 'joiners_gate',        'name': "The Joiner's Gate",        'key': 'dungeon_27_the_joiners_gate',         'commands': 'J gJ',                'teaches': ['J', 'gJ']},
    {'id': 28,  'slug': 'alignment_halls',     'name': 'The Alignment Halls',      'key': 'dungeon_28_the_alignment_halls',      'commands': '>> <<',               'teaches': ['>', '<']},
    {'id': 29,  'slug': 'indentation_sanctum', 'name': 'The Indentation Sanctum',  'key': 'dungeon_29_the_indentation_sanctum',  'commands': '>{m} <{m} =',         'teaches': []},
    {'id': 291, 'slug': 'warden_scrivener',    'name': 'The Warden Scrivener',     'key': 'dungeon_29.1_the_warden_scrivener',   'type': 'boss', 'after': 'indentation_sanctum',   'teaches': []},
    {'id': 30,  'slug': 'word_enclosure',      'name': 'The Word Enclosure',       'key': 'dungeon_30_the_word_enclosure',       'commands': 'iw aw',               'teaches': ['iw', 'aw']},
    {'id': 31,  'slug': 'bracket_enclosure',   'name': 'The Bracket Enclosure',    'key': 'dungeon_31_the_bracket_enclosure',    'commands': 'i( a(',               'teaches': ['i(', 'a(']},
    {'id': 32,  'slug': 'brace_square_enclosure', 'name': 'The Brace & Square Enclosure', 'key': 'dungeon_32_the_brace_square_enclosure', 'commands': 'i[ a[ i{ a{', 'teaches': ['i[', 'a[', 'i{', 'a{']},
    {'id': 33,  'slug': 'quote_enclosure',     'name': 'The Quote Enclosure',      'key': 'dungeon_33_the_quote_enclosure',      'commands': 'i" a" i\' a\'',       'teaches': ['i"', 'a"', "i'", "a'"]},
    {'id': 34,  'slug': 'tag_enclosure',       'name': 'The Tag Enclosure',        'key': 'dungeon_34_the_tag_enclosure',        'commands': 'it at',               'teaches': ['it', 'at']},
    {'id': 35,  'slug': 'sentence_enclosure',  'name': 'The Sentence Enclosure',   'key': 'dungeon_35_the_sentence_enclosure',   'commands': 'is as',               'teaches': ['is', 'as']},
    {'id': 36,  'slug': 'paragraph_enclosure', 'name': 'The Paragraph Enclosure',  'key': 'dungeon_36_the_paragraph_enclosure',  'commands': 'ip ap',               'teaches': ['ip', 'ap']},
    {'id': 361, 'slug': 'grandmasters_sanctum', 'name': "The Grandmaster's Sanctum", 'key': 'dungeon_36.1_the_grandmasters_sanctum', 'type': 'boss', 'after': 'paragraph_enclosure', 'teaches': []},
    {'id': 37,  'slug': 'spellwrights_forge',  'name': "The Spellwright's Forge",  'key': 'dungeon_37_the_spellwrights_forge',   'commands': ':s///',               'teaches': []},
    {'id': 38,  'slug': 'hall_of_echoes',      'name': 'The Hall of Echoes',       'key': 'dungeon_38_the_hall_of_echoes',       'commands': 'q @ "',               'teaches': ['q', '@', 'reg_named']},
    {'id': 381, 'slug': 'warden_eternal',      'name': 'The Warden Eternal',       'key': 'dungeon_38.1_the_warden_eternal',     'type': 'boss', 'after': 'hall_of_echoes',        'teaches': []},
    {'id': 99,  'slug': 'dummy',               'name': 'Dummy Dungeon',            'key': 'dummy_dungeon',                       'commands': 'd x s y p yy P', 'admin_only': True, 'teaches': []},
]

# ── Lookup maps ────────────────────────────────────────────────────────────────
_BY_ID   = {l['id']: l for l in LEVELS}
_BY_SLUG = {l['slug']: l for l in LEVELS}

# Frozen historical id→slug map: migrates legacy int-keyed save files to slug
# keys. Derived now while `id` exists; becomes a literal dict once `id` is dropped.
LEGACY_ID_SLUG = {l['id']: l['slug'] for l in LEVELS}


def slug_for_id(level_id: int) -> str | None:
    lv = _BY_ID.get(level_id)
    return lv['slug'] if lv else None


def id_for_slug(slug: str) -> int | None:
    lv = _BY_SLUG.get(slug)
    return lv['id'] if lv else None


def display_number(slug: str) -> str:
    """Human-facing level number. Boss/reliquary sub-levels render as
    '{parent}.1'; teaching levels render their own number. (Transitional:
    derived from the current `id`; becomes order-derived once `id` is dropped.)"""
    lv = _BY_SLUG.get(slug)
    if not lv:
        return '?'
    if lv.get('type') in ('boss', 'reliquary'):
        return f'{lv["id"] // 10}.1'
    return str(lv['id'])


# ── Curriculum command set (slug, order-based) ──────────────────────────────────

def known_commands_for_slug(slug: str) -> list:
    """All gated command tokens available at `slug`: the cumulative union of
    every level's `teaches` up to and including this one, in LEVELS order.
    Reordering LEVELS reorders the curriculum — no thresholds to maintain."""
    cmds: list = []
    for lv in LEVELS:
        for tok in lv.get('teaches', ()):
            if tok not in cmds:
                cmds.append(tok)
        if lv['slug'] == slug:
            break
    return cmds


def level_type_for_slug(slug: str) -> str:
    return (_BY_SLUG.get(slug) or {}).get('type', 'dungeon')


def is_reliquary_for_slug(slug: str) -> bool:
    return level_type_for_slug(slug) == 'reliquary'


def is_visible(level: dict, player_name: str) -> bool:
    return not level.get('admin_only', False) or player_name == 'admin'


# ── Legacy id-keyed API (transitional — callers migrate to slug, then remove) ───

def level_type(level_id: int) -> str:
    """Returns 'dungeon', 'reliquary', or 'boss'. Defaults to 'dungeon'."""
    return (_BY_ID.get(level_id) or {}).get('type', 'dungeon')


def is_reliquary(level_id: int) -> bool:
    return level_type(level_id) == 'reliquary'


def known_commands(level_id: int) -> list:
    """All commands available at this level (cumulative). Transitional id-keyed
    wrapper over the slug/order-based known_commands_for_slug()."""
    slug = slug_for_id(level_id)
    if slug is not None:
        return known_commands_for_slug(slug)
    # Unknown id (e.g. ad-hoc sandbox level): fall back to the full command set.
    return known_commands_for_slug(LEVELS[-1]['slug'])


def unlocks_after_slug(slug: str) -> str | None:
    """The level whose completion unlocks `slug`, derived from curriculum order:
    the previous non-reliquary level (bosses ARE on the main chain). The
    reliquary hangs off its `after` parent and is itself off the main chain."""
    lv = _BY_SLUG.get(slug)
    if not lv or lv['slug'] == 'first_cave':
        return None
    if lv.get('type') == 'reliquary':
        return lv.get('after')
    idx = LEVELS.index(lv)
    for prev in reversed(LEVELS[:idx]):
        if prev.get('type') != 'reliquary' and not prev.get('admin_only'):
            return prev['slug']
    return None


def is_unlocked(slug: str, progress: dict, player_name: str = '') -> bool:
    """True if `slug` is playable: admin sees all; admin-only sandboxes are
    always open; every other level unlocks when its unlocks_after_slug prereq is
    complete. `progress` is keyed by slug."""
    if player_name == 'admin':
        return True
    level = _BY_SLUG.get(slug)
    if level is None:
        return False
    if level.get('admin_only', False):
        return True
    target = unlocks_after_slug(slug)
    if target is None:                       # first_cave / no prerequisite
        return True
    return progress.get(target, {}).get('complete', False)
