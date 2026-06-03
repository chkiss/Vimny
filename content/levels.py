"""Level definitions and command curriculum.

Identity is the immutable ``slug`` — used by builders, tests, saves, scrolls,
and wizard poems. There is no integer id: the human-facing number lives in the
explicit ``display`` field (cosmetic), and curriculum order is the order of this
list.

Per level:
  slug      — immutable identity
  display   — human-facing level number (e.g. '5', '5.1'); cosmetic only
  name      — display name
  teaches   — the gated command TOKENS this level introduces (drives gating)
  commands  — middle-column display string (may diverge from teaches: shows
              keystrokes not tokens, e.g. 'v' not 'visual'; descriptive forms)
  type      — 'dungeon' (default) | 'boss' | 'reliquary'
  after     — for boss/reliquary sub-levels: the slug they hang off (→ 'x.1')
  admin_only— hidden sandbox

known_commands unions `teaches` in curriculum (list) order, so reordering LEVELS
reorders the curriculum with no per-level renumbering. Renumbering is just
editing `display` strings — identity (slug) never moves; the overworld
'filename' label is derived from display + slug by key_for_slug, never stored.

Always-on (never gated, not in `teaches`): u, :w, :q, :q!.
Not yet gated (no token): :e :set (archivist), :s/// (spellwright), = (indent).
"""
from __future__ import annotations

LEVELS = [
    {'display': '0',    'slug': 'first_cave',            'name': 'The First Cave',             'commands': 'h j k l u :w :q :q!', 'teaches': ['h', 'j', 'k', 'l']},
    {'display': '1',    'slug': 'line_halls',            'name': 'The Line Halls',             'commands': '^ $ 0', 'teaches': ['^', '$', '0']},
    {'display': '1.1',  'slug': 'reliquary',             'name': 'The Reliquary',              'commands': 'x', 'type': 'reliquary', 'after': 'line_halls', 'teaches': ['x']},
    {'display': '2',    'slug': 'counting_crypts',       'name': 'The Counting Crypts',        'commands': '[count] prefix', 'teaches': ['count']},
    {'display': '3',    'slug': 'rune_halls',            'name': 'The Rune Halls',             'commands': 'w b e', 'teaches': ['w', 'b', 'e']},
    {'display': '4',    'slug': 'character_cataracts',   'name': 'The Character Cataracts',    'commands': 'f F t T', 'teaches': ['f', 'F', 't', 'T']},
    {'display': '5',    'slug': 'goblin_gauntlet',       'name': 'The Goblin Gauntlet',        'commands': '; , p', 'teaches': [';', ',', 'p']},
    {'display': '5.1',  'slug': 'wardens_keep',          'name': "The Warden's Keep",          'type': 'boss', 'after': 'goblin_gauntlet', 'teaches': []},
    {'display': '6',    'slug': 'word_forge',            'name': 'The WORD Forge',             'commands': 'W B E', 'teaches': ['W', 'B', 'E']},
    {'display': '7',    'slug': 'backward_vaults',       'name': 'The Backward Vaults',        'commands': 'ge gE', 'teaches': ['ge', 'gE']},
    {'display': '8',    'slug': 'lineheads',             'name': 'The Lineheads',              'commands': 'G gg', 'teaches': ['G', 'gg']},
    {'display': '9',    'slug': 'screen_vault',          'name': 'The Screen Vault',           'commands': 'H M L', 'teaches': ['H', 'M', 'L']},
    {'display': '10',   'slug': 'bracket_vaults',        'name': 'The Bracket Vaults',         'commands': '%', 'teaches': ['%']},
    {'display': '12',   'slug': 'runic_archives',        'name': 'The Runic Archives',         'commands': '} {', 'teaches': ['{', '}']},
    {'display': '13',   'slug': 'sentence_corridor',     'name': 'The Sentence Corridor',      'commands': ') (', 'teaches': ['(', ')']},
    {'display': '13.1', 'slug': 'warden_surveyor',       'name': 'The Warden Surveyor',        'type': 'boss', 'after': 'sentence_corridor', 'teaches': []},
    {'display': '14',   'slug': 'sight_sanctum',         'name': 'The Sight Sanctum',          'commands': 'v', 'teaches': ['visual']},
    {'display': '15',   'slug': 'seekers_labyrinth',     'name': "The Seekers' Labyrinth",     'commands': '/ ? n N *', 'teaches': ['/', '*']},
    {'display': '16',   'slug': 'waypoint_sanctum',      'name': 'The Waypoint Sanctum',       'commands': "m ' `", 'teaches': ['mark']},
    {'display': '17',   'slug': 'archivists_library',    'name': "The Archivist's Library",    'commands': ':set wrap  :e!  :w {suit}', 'teaches': []},
    {'display': '17.1', 'slug': 'warden_pathfinder',     'name': 'The Warden Pathfinder',      'type': 'boss', 'after': 'archivists_library', 'teaches': []},
    {'display': '18',   'slug': 'operators_vault',       'name': "The Operator's Vault",       'commands': 'd c', 'teaches': ['d', 'c', 's']},
    {'display': '19',   'slug': 'whole_line_annex',      'name': 'The Whole-Line Annex',       'commands': 'dd cc D S', 'teaches': ['S']},
    {'display': '20',   'slug': 'quartermaster',         'name': 'The Quartermaster',          'commands': 'y yy P', 'teaches': ['y', 'P', 'register']},
    {'display': '21',   'slug': 'undo_sanctum',          'name': 'The Undo Sanctum',           'teaches': []},
    {'display': '22',   'slug': 'echo_vault',            'name': 'The Echo Vault',             'commands': '.', 'teaches': ['dot']},
    {'display': '22.1', 'slug': 'warden_manifold',       'name': 'The Warden Manifold',        'type': 'boss', 'after': 'echo_vault', 'teaches': []},
    {'display': '23',   'slug': 'inscription_halls',     'name': 'The Inscription Halls',      'commands': 'i a', 'teaches': ['insert']},
    {'display': '24',   'slug': 'sculpting_chambers',    'name': 'The Sculpting Chambers',     'commands': 'I A o O', 'teaches': []},
    {'display': '25',   'slug': 'overwrite_halls',       'name': 'The Overwrite Halls',        'commands': 'r R', 'teaches': ['r', 'R']},
    {'display': '26',   'slug': 'case_chambers',         'name': 'The Case Chambers',          'commands': '~ g~ gU gu', 'teaches': ['~', 'gU', 'gu', 'g~']},
    {'display': '27',   'slug': 'joiners_gate',          'name': "The Joiner's Gate",          'commands': 'J gJ', 'teaches': ['J', 'gJ']},
    {'display': '28',   'slug': 'alignment_halls',       'name': 'The Alignment Halls',        'commands': '>> <<', 'teaches': ['>', '<']},
    {'display': '29',   'slug': 'indentation_sanctum',   'name': 'The Indentation Sanctum',    'commands': '>{m} <{m} =', 'teaches': []},
    {'display': '29.1', 'slug': 'warden_scrivener',      'name': 'The Warden Scrivener',       'type': 'boss', 'after': 'indentation_sanctum', 'teaches': []},
    {'display': '30',   'slug': 'word_enclosure',        'name': 'The Word Enclosure',         'commands': 'iw aw', 'teaches': ['iw', 'aw']},
    {'display': '31',   'slug': 'bracket_enclosure',     'name': 'The Bracket Enclosure',      'commands': 'i( a(', 'teaches': ['i(', 'a(']},
    {'display': '32',   'slug': 'brace_square_enclosure', 'name': 'The Brace & Square Enclosure', 'commands': 'i[ a[ i{ a{', 'teaches': ['i[', 'a[', 'i{', 'a{']},
    {'display': '33',   'slug': 'quote_enclosure',       'name': 'The Quote Enclosure',        'commands': 'i" a" i\' a\'', 'teaches': ['i"', 'a"', "i'", "a'"]},
    {'display': '34',   'slug': 'tag_enclosure',         'name': 'The Tag Enclosure',          'commands': 'it at', 'teaches': ['it', 'at']},
    {'display': '35',   'slug': 'sentence_enclosure',    'name': 'The Sentence Enclosure',     'commands': 'is as', 'teaches': ['is', 'as']},
    {'display': '36',   'slug': 'paragraph_enclosure',   'name': 'The Paragraph Enclosure',    'commands': 'ip ap', 'teaches': ['ip', 'ap']},
    {'display': '36.1', 'slug': 'grandmasters_sanctum',  'name': "The Grandmaster's Sanctum",  'type': 'boss', 'after': 'paragraph_enclosure', 'teaches': []},
    {'display': '37',   'slug': 'spellwrights_forge',    'name': "The Spellwright's Forge",    'commands': ':s///', 'teaches': []},
    {'display': '38',   'slug': 'hall_of_echoes',        'name': 'The Hall of Echoes',         'commands': 'q @ "', 'teaches': ['q', '@', 'reg_named']},
    {'display': '38.1', 'slug': 'warden_eternal',        'name': 'The Warden Eternal',         'type': 'boss', 'after': 'hall_of_echoes', 'teaches': []},
    {'display': '99',   'slug': 'dummy',                 'name': 'Dummy Dungeon',              'commands': 'd x s y p yy P', 'admin_only': True, 'teaches': []},
]

# ── Lookup map ──────────────────────────────────────────────────────────────
_BY_SLUG = {l['slug']: l for l in LEVELS}


def display_number(slug: str) -> str:
    """Human-facing level number (e.g. '5', '5.1'). Cosmetic only."""
    lv = _BY_SLUG.get(slug)
    return lv['display'] if lv else '?'


def key_for_slug(slug: str) -> str:
    """The overworld row label (netrw 'filename'), derived from display + slug —
    e.g. 'dungeon_05_the_goblin_gauntlet'. The integer part of display is
    zero-padded to two digits; the dummy sandbox is the one special case."""
    lv = _BY_SLUG.get(slug)
    if not lv:
        return slug
    if slug == 'dummy':
        return 'dummy_dungeon'
    intpart, _, frac = lv['display'].partition('.')
    num = intpart.zfill(2) + (f'.{frac}' if frac else '')
    return f'dungeon_{num}_the_{slug}'


# ── Curriculum command set (slug, order-based) ──────────────────────────────────

def known_commands(slug: str) -> list:
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


def act_commands(slug: str) -> list:
    """The commands taught in the act `slug` belongs to: every `teaches` from the
    previous boss (exclusive) up to — but NOT including — `slug`, in curriculum
    order. Used for a boss's hint bar: the player can drill every command of the
    act it caps, but not the next act's command (which the boss only previews).
    A reliquary is not an act boundary, so its commands are included."""
    lv = _BY_SLUG.get(slug)
    if lv is None:
        return []
    idx = LEVELS.index(lv)
    start = 0                                # first level of this act
    for i in range(idx - 1, -1, -1):
        if LEVELS[i].get('type') == 'boss':  # the previous boss caps the prior act
            start = i + 1
            break
    cmds: list = []
    for prev in LEVELS[start:idx]:           # curriculum order, up to (not incl.) slug
        for tok in prev.get('teaches', ()):
            if tok not in cmds:
                cmds.append(tok)
    return cmds


def level_type(slug: str) -> str:
    """Returns 'dungeon' (default), 'boss', or 'reliquary'."""
    return (_BY_SLUG.get(slug) or {}).get('type', 'dungeon')


def is_reliquary(slug: str) -> bool:
    return level_type(slug) == 'reliquary'


def is_visible(level: dict, player_name: str) -> bool:
    return not level.get('admin_only', False) or player_name == 'admin'


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
