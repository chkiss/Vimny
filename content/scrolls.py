# Vimny — a Vim-teaching dungeon crawler.
# Copyright (C) 2026 Chas Kissick
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Scroll content — strings and line-kind specs consumed by main.py render functions.

Line-kind tuples used in 'lines' lists:
  ('blank',)
  ('dim',    text)
  ('amber',  text)
  ('cmd',    key, desc)                              ← hi key, dim arrow, amber desc
  ('segs',   [(text, bold), …], desc)                ← key as bold/dim segments
  ('smudge', key, smudge_prefix, clear_tail, gate)  ← smudge block + dim tail
  ('smudge_seg', key_text, hide_prefix, desc)       ← key with its head smudged

Smudge clarification:
  A ('smudge', …) line stays obscured until the command(s) it previews are in
  the player's known-command set. `gate` is the command token (or tuple of
  tokens) that must all be known; once known the line renders as a clear ('cmd')
  row revealing `key` and the full description (smudge_prefix + clear_tail).
  Gate tokens match the keys produced by content.levels.known_commands(slug).
"""

# kv_rows tuples: (key, desc, gate)
#   gate is None    → always clear (key/desc shown)
#   gate is a token → smudged until that command is in the player's known set
RELIQUARY_SCROLL = {
    'title':   '◈   The Unnamed Register   ◈',
    'intro':   '  Scrawled on the scroll: a revelation.',
    'outro':   '  Your cuts are visible in the statusline.',
    'p_text':  '  holds all you delete — there must be some use...',
    'kv_rows': [
        ('x', 'deletes a character  ', None),
        ('d', 'deletes a range      ', 'd'),
        ('c', 'changes text         ', 'c'),
    ],
}

WARDEN_LEAP_SCROLL = {
    'title': "◈   The Warden's Leap   ◈",
    'lines': [
        ('dim',    'Beyond this arch, the stride grows longer.'),
        ('dim',    'Some distances ask for a different step.'),
        ('blank',),
        ('smudge', 'W/B/E', '', 'leap by space, heedless of the marks', 'W'),
        ('smudge', 'ge/gE', '', "step back to the last word's end",      'ge'),
        ('smudge', 'gg/G',  '', 'stride the full length of the hall',    'G'),
        ('smudge', 'H/M/L', '', 'anchor to what the eye can hold',       'H'),
        ('smudge', '%',     '', 'what opens has a partner that closes',  '%'),
        ('smudge', '}{',    '', 'silence between paragraphs is a door',  '{'),
        ('smudge', ')(',    '', 'walk the stops, forward or back',       '('),
        ('blank',),
        ('amber',  'Patience learns the big steps last.'),
    ],
}

WARDEN_SIGHT_SCROLL = {
    'title': "◈   The Warden's Sight   ◈",
    'lines': [
        ('dim',   "  The Warden is gone. His sight is yours."),
        ('blank',),
        ('cmd',   'v', 'enter Visual Mode'),
        ('blank',),
        ('dim',   '  In Visual Mode: Look before you leap!'),
        ('dim',   '  Use verbs and nouns just as you would'),
        ('dim',   '  in Normal Mode, and return with Esc.'),
        ('blank',),
        ('amber', '  See before you strike.'),
    ],
}

# Dropped by the Warden Surveyor — previews the SEARCH / MARK act ahead: search
# (/ ? n N *) at the Seekers' Labyrinth, revealed; marks (m ` ') at the Waypoint
# Sanctum, smudged until 'mark' is learned. Replaces the visual preview now that
# Visual Mode moved later in the curriculum (it needs operators to be forceable).
SURVEYORS_PATH_SCROLL = {
    'title': "◈   The Surveyor's Path   ◈",
    'lines': [
        ('dim',    "  The Surveyor walked, naming the land."),
        ('blank',),
        ('cmd',    '/{pat}', 'search forward for a word'),
        ('cmd',    '?{pat}', 'search backward — the mirror'),
        ('cmd',    'n     ', 'next match, same direction'),
        ('cmd',    'N     ', 'previous match, reversed'),
        ('cmd',    '*     ', 'seek the word under the cursor'),
        ('blank',),
        ('dim',    "  And for the road home, set a stone:"),
        ('smudge', 'm{a}  ', 'm', 'ark this spot, name it {a}', 'mark'),
        ('smudge', '`{a}  ', 'leap to that exact ', 'mark',      'mark'),
        ('smudge', "'{a}  ", 'leap to the ma',      "rk's line", 'mark'),
        ('blank',),
        ('amber',  '  Name a thing, and the way finds you.'),
    ],
}

WAYPOINT_SCROLL = {
    'title': "◈   The Numbered Ledger   ◈",
    'lines': [
        ('dim',   "  A surveyor's ledger, folded in the chest."),
        ('blank',),
        # full option names, with the typable abbreviation letters bold:
        ('segs',  [(':set nu', True), ('mber', False)], 'show line numbers'),
        ('segs',  [(':set nonu', True), ('mber', False)], 'hide the gutter'),
        # relativenumber: a name half-spoken — its head is smudged on the old
        # ledger, only the tail still legible (the flourish below names this).
        ('smudge_seg', ':set relativenumber', ':set relativen', 'count from the cursor'),
        ('blank',),
        ('dim',   '  A name half-spoken is a name still heard.'),
        ('blank',),
        ('amber', '  Know the line; the leap follows.'),
    ],
}

SETTERS_HAND_SCROLL = {
    'title': "◈   The Setter's Hand   ◈",
    'lines': [
        ('dim',    '  The same ledger, its margins thick with shortcuts.'),
        ('blank',),
        ('cmd',    ':set nu!',   'flip it — on if off, off if on'),
        ('cmd',    ':set invnu', 'the same flip, spelled in full'),
        ('cmd',    ':set nu&',   'restore the option to its default'),
        ('cmd',    ':set nu?',   'ask its state without changing it'),
        ('cmd',    ':set all&',  'wipe every option back to default'),
        ('blank',),
        ('amber',  '  ! flips, & forgets, ? merely asks.'),
    ],
}

# Dropped by the Warden Pathfinder — every row previews the OPERATOR act
# ahead of it (d at the Operator's Vault, r at the Cipher Cell, y at the
# Beacon Tiers, . at the Echo Vault, s/c at the Change Annex). The closing
# wisdom absorbed the retired Archivist's Method scroll, whose yank rows
# duplicated this codex.
OPERATOR_CODEX_SCROLL = {
    'title': "◈   The Operator's Codex   ◈",
    'lines': [
        ('dim',    '  In the dark, they carved the grammar of unmaking.'),
        ('blank',),
        ('cmd',    'd{m}', 'delete to motion'),
        ('cmd',    'dd  ', 'delete line'),
        ('smudge', 'r{c}', 'r',  'eplace one character',       'r'),
        ('smudge', 's   ', 's',  'ubstitute one character',    's'),
        ('smudge', 'y{m}', 'y',  'ank (copy without cutting)', 'y'),
        ('smudge', 'c{m}', 'ch', 'ange text (del + insert)',   'c'),
        ('smudge', '.   ', 'r',  'epeat the last change',      'dot'),
        ('blank',),
        ('amber',  '  d and y share one register: "'),
        ('dim',    '  Paste before deleting — or lose your copy.'),
    ],
}

# Dropped by the Warden Manifold — the boss validated the copyists' verbs
# (d, r, y, .); every row here previews the WRITERS' act ahead: i/a at the
# Inscription Halls, c at the Change Annex, o/O at the Sculpting Chambers,
# R at the Overwrite Halls. All smudged until each is learned.
INSCRIBERS_HAND_SCROLL = {
    'title': "◈   The Inscriber's Hand   ◈",
    'lines': [
        ('dim',    '  You cut, copied, repeated. Now the hand writes.'),
        ('blank',),
        ('smudge', 'i   ', 'i',  'nsert — write before the cursor',  'insert'),
        ('smudge', 'a   ', 'a',  'ppend — write after it',           'insert'),
        ('smudge', 'c{m}', 'ch', 'ange text (delete + insert)',      'c'),
        ('smudge', 'o/O ', 'o',  'pen a fresh line, below or above', 'o'),
        ('smudge', 'R   ', 'R',  'eplace mode — overtype as you go', 'R'),
        ('blank',),
        ('amber',  '  Esc seals the ink.'),
    ],
}

WHOLE_WORD_SCROLL = {
    'title': '◈   The Whole Word   ◈',
    'lines': [
        ('dim',    '  Position within the word ceased to matter.'),
        ('blank',),
        # the whole scroll is NEXT-tier (the Act VI preview): every command
        # line sleeps under the dip until its text object is learned
        ('smudge', 'iw',  'i',  'nner word  (anywhere in word)', 'iw'),
        ('smudge', 'aw',  'a',  'round word (includes space)',   'aw'),
        ('blank',),
        ('smudge', 'i(',  'i',  'nner parens', 'i('),
        ('smudge', 'i"',  'in', 'side quotes', 'i"'),
        ('blank',),
        ('amber',  '  The boundary is the rune, not where you stand.'),
    ],
}

RECALLING_HAND_SCROLL = {
    'title': '◈   The Recalling Hand   ◈',
    'lines': [
        ('dim',    '  Mid-inscription, the scribe summoned old ink.'),
        ('blank',),
        ('cmd',    '<C-r>"', 'insert the unnamed register'),
        ('cmd',    '<C-r>0', 'paste your last yank'),
        ('segs',   [('<C-r>', True), ('{reg}', False)], 'paste any named register'),
        ('cmd',    '<C-r><C-w>', 'insert the word under cursor'),
        ('blank',),
        ('amber',  '  No need to leave INSERT to recall what you kept.'),
    ],
}

QUICK_ERASE_SCROLL = {
    'title': '◈   The Quick Erase   ◈',
    'lines': [
        ('dim',    '  A slip of the chisel, mended without a pause.'),
        ('blank',),
        ('cmd',    '<C-w>', 'erase the word behind the cursor'),
        ('cmd',    '<C-u>', 'erase back to the start of the line'),
        ('cmd',    '<C-o>', 'one Normal step, then back to typing'),
        ('blank',),
        ('dim',    '  <C-o> lets you leap, then writes resume.'),
        ('blank',),
        ('amber',  '  Stay in the flow; fix without stopping.'),
    ],
}

PLUMB_LINE_SCROLL = {
    'title': '◈   The Plumb Line   ◈',
    'lines': [
        ('dim',    '  The mason dropped a weighted cord to find true.'),
        ('blank',),
        ('cmd',    '|',   'to the first column'),
        ('cmd',    '{n}|', 'to column n  (e.g. 10| → column ten)'),
        ('blank',),
        ('dim',    '  A wall or water halts the cord short.'),
        ('blank',),
        ('amber',  '  Name the column; arrive in one step.'),
    ],
}

SEARCH_CRAFT_SCROLL = {
    'title': '◈   The Lit Trail   ◈',
    'lines': [
        ('dim',    '  The tracker learned to light — and douse — the trail'),
        ('blank',),
        ('cmd',    ':set hls',  'glow every match of the search'),
        ('cmd',    ':noh',      'douse the highlights for now'),
        ('cmd',    ':set is',   'preview the match as you type'),
        ('cmd',    '<C-r><C-w>', "pull the cursor's word into /"),
        ('blank',),
        ('amber',  '  See the quarry before you give chase.'),
    ],
}

WANDERERS_THREAD_SCROLL = {
    'title': "◈   The Wanderer's Thread   ◈",
    'lines': [
        ('dim',    '  Every great leap pays out a thread behind you.'),
        ('blank',),
        ('cmd',    '<C-o>', 'thread back to where you leapt from'),
        ('cmd',    '<C-i>', 'wind it forward again'),
        ('blank',),
        ('dim',    '  Searches, G, gg, %, marks — each ties a knot.'),
        ('blank',),
        ('amber',  '  You can always find the way back.'),
    ],
}

# Grants <C-r> (redo) — u's other hand. u itself is always-on from the first
# cave; this relic completes the pair. (The Undo Sanctum level was cancelled
# 2026-06-11; the 'redo' token lives here now.)
SECOND_STRIDE_SCROLL = {
    'title': '◈   The Second Stride   ◈',
    'lines': [
        ('dim',    '  You stepped back. The footprint waited.'),
        ('blank',),
        ('cmd',    '<C-r>', 'redo what u took back'),
        ('cmd',    '[count]<C-r>', 'redo that many steps'),
        ('blank',),
        ('dim',    '  Back and forward: u and this, one rope.'),
        ('amber',  '  An undo is never a promise. Walk on.'),
    ],
}

# ── Regex-for-search scrolls (Blocks B–F) ──────────────────────────────────
# Gate token: 'regex' (granted by reading any one of these). Each teaches a
# family of search atoms; they reveal once the searcher (/) is known.

REGEX_CLASSES_SCROLL = {
    'title': '◈   The Glyph-Kinds   ◈',
    'lines': [
        ('dim',    '  A searcher learns to name what it seeks.'),
        ('blank',),
        ('cmd',    '.',  'any single character'),
        ('cmd',    '\\w', 'a word character  (\\W: not one)'),
        ('cmd',    '\\d', 'a digit          (\\D: not one)'),
        ('cmd',    '\\s', 'whitespace       (\\S: not one)'),
        ('cmd',    '\\a', 'a letter   \\l lower   \\u UPPER'),
        ('blank',),
        ('amber',  '  Seek a kind, not only a character.'),
    ],
}

REGEX_ANCHORS_SCROLL = {
    'title': '◈   The Anchors & Bounds   ◈',
    'lines': [
        ('dim',    '  Where a thing sits matters as much as what it is.'),
        ('blank',),
        ('cmd',    '^',   'the start of the line'),
        ('cmd',    '$',   'the end of the line'),
        ('cmd',    '\\<',  'the start of a word'),
        ('cmd',    '\\>',  'the end of a word'),
        ('cmd',    '\\zs', 'begin the match here (\\ze: end it here)'),
        ('blank',),
        ('amber',  '  Anchor the search; the rest drifts to it.'),
    ],
}

REGEX_QUANTIFIERS_SCROLL = {
    'title': '◈   The Many & The Maybe   ◈',
    'lines': [
        ('dim',    '  One glyph may stand for none, or for a throng.'),
        ('blank',),
        ('cmd',    '*',     'zero or more of what precedes'),
        ('cmd',    '\\+',    'one or more'),
        ('cmd',    '\\?',    'zero or one  (optional)'),
        ('cmd',    '\\{n}',  'exactly n   (\\{n,m}: n to m)'),
        ('blank',),
        ('amber',  '  Count the repetition, not the repeats.'),
    ],
}

REGEX_COLLECTIONS_SCROLL = {
    'title': '◈   The Gathered Glyphs   ◈',
    'lines': [
        ('dim',    '  Offer the searcher a choice of marks.'),
        ('blank',),
        ('cmd',    '[abc]',  'any one of a, b or c'),
        ('cmd',    '[^abc]', 'any one EXCEPT a, b or c'),
        ('cmd',    '[a-z]',  'any one in the range'),
        ('cmd',    '\\|',     'this branch OR that one'),
        ('cmd',    '\\( \\)',  'bind a group; \\. means a literal dot'),
        ('blank',),
        ('amber',  '  A set of doors, and the search picks one.'),
    ],
}

REGEX_MAGIC_SCROLL = {
    'title': '◈   The Magic Levels   ◈',
    'lines': [
        ('dim',    '  Why so many backslashes? Change the law.'),
        ('blank',),
        ('cmd',    '\\v', 'very magic — + ? ( ) | need no backslash'),
        ('cmd',    '\\V', 'very nomagic — almost all glyphs literal'),
        ('cmd',    '\\c', 'this search ignores case  (\\C: heeds it)'),
        ('blank',),
        ('dim',    '  \\v turns  \\(ab\\)\\+  into the cleaner  (ab)+'),
        ('blank',),
        ('amber',  '  Bend the grammar to fit the hand.'),
    ],
}

WARDEN_ACT_SCROLL = {
    'title': "◈   The Warden's Act   ◈",
    'lines': [
        ('dim',    '  The Sight became the Hand.'),
        ('blank',),
        ('cmd',    'v{m}d', 'select range, delete'),
        ('cmd',    'v{m}y', 'select range, yank'),
        ('cmd',    'v{m}c', 'select range, change'),
        ('smudge', 'gv',    '',  'reselect last visual span', 'visual'),
        ('blank',),
        ('amber',  '  See. Select. Strike.'),
        ('dim',    '  The eye and the hand are one.'),
    ],
}


DISPLAY_LINE_SCROLL = {
    'title': "◈   The Wrapped Line   ◈",
    'lines': [
        ('dim',   '  A long line folds to fill the page.'),
        ('dim',   '  j and k leap whole lines — here is a finer step.'),
        ('blank',),
        ('cmd',   'gj', 'down one DISPLAY line'),
        ('cmd',   'gk', 'up one DISPLAY line'),
        ('blank',),
        ('amber', '  Walk the wrap, not the line.'),
    ],
}

EDIT_BY_NAME_SCROLL = {
    'title': "◈   The Named Folio   ◈",
    'lines': [
        ('dim',   '  Every dungeon is a file; every file has a name.'),
        ('blank',),
        ('cmd',   ':e {name}', 'open a buffer by its name'),
        ('blank',),
        ('dim',   '  :e alone reloads — :e {name} opens another.'),
        ('amber', '  Call a folio by its name.'),
    ],
}


# ── Scroll catalog ────────────────────────────────────────────────────────────
# id matches the key stored in progress['extras'] when the scroll is discovered.
# dropped_by / level_slug / level_name are display metadata only.

SCROLL_CATALOG = [
    {
        'id':         'register',
        'title':      'The Unnamed Register',
        'dropped_by': 'The Reliquary',
        'level_slug': 'reliquary',
        'level_name': "The Reliquary",
        'content':    RELIQUARY_SCROLL,
    },
    {
        'id':         'leap',
        'title':      "The Warden's Leap",
        'dropped_by': "The Warden's Keep",
        'level_slug': 'wardens_keep',
        'level_name': "The Warden's Keep",
        'content':    WARDEN_LEAP_SCROLL,
    },
    {
        'id':         'search',
        'title':      "The Surveyor's Path",
        'dropped_by': 'The Warden Surveyor',
        'level_slug': 'warden_surveyor',
        'level_name': 'The Warden Surveyor',
        'content':    SURVEYORS_PATH_SCROLL,
    },
    {
        'id':         'setnum',
        'title':      'The Numbered Ledger',
        'dropped_by': 'The Waypoint Sanctum',
        'level_slug': 'waypoint_sanctum',
        'level_name': 'The Waypoint Sanctum',
        'content':    WAYPOINT_SCROLL,
    },
    {
        'id':         'display_move',
        'title':      'The Wrapped Line',
        'dropped_by': "The Archivist's Library",
        'level_slug': 'archivists_library',
        'level_name': "The Archivist's Library",
        'content':    DISPLAY_LINE_SCROLL,
    },
    {
        'id':         'edit_name',
        'title':      'The Named Folio',
        'dropped_by': "The Archivist's Library",
        'level_slug': 'archivists_library',
        'level_name': "The Archivist's Library",
        'content':    EDIT_BY_NAME_SCROLL,
    },
    {
        'id':         'd_op',
        'title':      "The Operator's Codex",
        'dropped_by': 'The Warden Pathfinder',
        'level_slug': 'warden_pathfinder',
        'level_name': 'The Warden Pathfinder',
        'content':    OPERATOR_CODEX_SCROLL,
    },
    {
        'id':         'writers',
        'title':      "The Inscriber's Hand",
        'dropped_by': 'The Warden Manifold',
        'level_slug': 'warden_manifold',
        'level_name': 'The Warden Manifold',
        'content':    INSCRIBERS_HAND_SCROLL,
    },
    {
        'id':         'text_obj',
        'title':      'The Whole Word',
        'dropped_by': 'The Warden Scrivener',
        'level_slug': 'warden_scrivener',
        'level_name': 'The Warden Scrivener',
        'content':    WHOLE_WORD_SCROLL,
    },
    {
        'id':         'visual_op',
        'title':      "The Warden's Act",
        'dropped_by': "The Grandmaster's Sanctum",
        'level_slug': 'grandmasters_sanctum',
        'level_name': "The Grandmaster's Sanctum",
        'content':    WARDEN_ACT_SCROLL,
    },

    # ── Relic scrolls — found, not act-gated. Each teaches a budget-safe
    # flourish that can't beat a level's par (see design notes). id == the
    # gating token where the scroll grants a new command.
    {
        'id':         'set_more',
        'title':      "The Setter's Hand",
        'dropped_by': 'A surveyor’s satchel',
        'level_slug': 'waypoint_sanctum',
        'level_name': 'The Waypoint Sanctum',
        'content':    SETTERS_HAND_SCROLL,
    },
    {
        'id':         'regex_classes',
        'title':      'The Glyph-Kinds',
        'dropped_by': 'A seeker’s field-notes',
        'level_slug': 'seekers_labyrinth',
        'level_name': "The Seekers' Labyrinth",
        'content':    REGEX_CLASSES_SCROLL,
    },
    {
        'id':         'regex_anchors',
        'title':      'The Anchors & Bounds',
        'dropped_by': 'A seeker’s field-notes',
        'level_slug': 'seekers_labyrinth',
        'level_name': "The Seekers' Labyrinth",
        'content':    REGEX_ANCHORS_SCROLL,
    },
    {
        'id':         'regex_quant',
        'title':      'The Many & The Maybe',
        'dropped_by': 'A seeker’s field-notes',
        'level_slug': 'seekers_labyrinth',
        'level_name': "The Seekers' Labyrinth",
        'content':    REGEX_QUANTIFIERS_SCROLL,
    },
    {
        'id':         'regex_collections',
        'title':      'The Gathered Glyphs',
        'dropped_by': 'A seeker’s field-notes',
        'level_slug': 'seekers_labyrinth',
        'level_name': "The Seekers' Labyrinth",
        'content':    REGEX_COLLECTIONS_SCROLL,
    },
    {
        'id':         'regex_magic',
        'title':      'The Magic Levels',
        'dropped_by': 'A seeker’s field-notes',
        'level_slug': 'seekers_labyrinth',
        'level_name': "The Seekers' Labyrinth",
        'content':    REGEX_MAGIC_SCROLL,
    },
    {
        'id':         'searchcraft',
        'title':      'The Lit Trail',
        'dropped_by': 'A tracker’s cache',
        'level_slug': 'seekers_labyrinth',
        'level_name': "The Seekers' Labyrinth",
        'content':    SEARCH_CRAFT_SCROLL,
    },
    {
        'id':         'jump',
        'title':      "The Wanderer's Thread",
        'dropped_by': 'A wayfarer’s pack',
        'level_slug': 'waypoint_sanctum',
        'level_name': 'The Waypoint Sanctum',
        'content':    WANDERERS_THREAD_SCROLL,
    },
    {
        # Pinned (not in the random pool): the FIRST vault chest of the
        # Waypoint Sanctum — the marks level; "the footprint waited."
        'id':         'redo',
        'title':      'The Second Stride',
        'dropped_by': 'The Waypoint Sanctum',
        'level_slug': 'waypoint_sanctum',
        'level_name': 'The Waypoint Sanctum',
        'content':    SECOND_STRIDE_SCROLL,
    },
    {
        'id':         'col_motion',
        'title':      'The Plumb Line',
        'dropped_by': 'A mason’s toolbox',
        'level_slug': 'line_halls',
        'level_name': 'The Line Halls',
        'content':    PLUMB_LINE_SCROLL,
    },
    {
        'id':         'ins_paste',
        'title':      'The Recalling Hand',
        'dropped_by': 'A scribe’s desk',
        'level_slug': 'inscription_halls',
        'level_name': 'The Inscription Halls',
        'content':    RECALLING_HAND_SCROLL,
    },
    {
        'id':         'ins_edit',
        'title':      'The Quick Erase',
        'dropped_by': 'A sculptor’s bench',
        'level_slug': 'sculpting_chambers',
        'level_name': 'The Sculpting Chambers',
        'content':    QUICK_ERASE_SCROLL,
    },
]


# ── Relic ("safe") scroll pool ──────────────────────────────────────────────
# Chests not tied to a specific level (no _SCROLL_DROPS entry) pull a random,
# not-yet-discovered scroll from this pool. Every id here is a budget-safe
# flourish that cannot beat a level's par (see the design discussion).
#
# TO ADD A NEW RELIC SCROLL:
#   1. Author its <NAME>_SCROLL content dict above.
#   2. Add a SCROLL_CATALOG entry (it lands in the library's `relics/` subtree;
#      rendering is automatic — main._show_catalog_scroll reads the catalog).
#   3. Append its id to RELIC_SCROLL_IDS below.
# The id DOUBLES AS the gating token it grants: on discovery it is written to
# progress['extras'] and injected into player.known_commands, so name it to
# match the token your command_guard / handler checks (e.g. 'jump', 'col_motion').
RELIC_SCROLL_IDS = [
    'set_more',
    'regex_classes', 'regex_anchors', 'regex_quant', 'regex_collections', 'regex_magic',
    'searchcraft', 'jump', 'col_motion', 'ins_paste', 'ins_edit',
    # 'redo' is NOT here: The Second Stride is pinned to the Waypoint
    # Sanctum's first vault chest (guaranteed — before the editing act),
    # not left to the random pool.
]


def pick_relic_scroll(discovered, rng=None):
    """Return a random relic-scroll id the player has NOT yet discovered, or
    None once they hold them all. `discovered` is any iterable of extras ids;
    `rng` is an optional random.Random for deterministic tests."""
    import random as _random
    have = set(discovered)
    pool = [sid for sid in RELIC_SCROLL_IDS if sid not in have]
    if not pool:
        return None
    return (rng or _random).choice(pool)
