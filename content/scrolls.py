"""Scroll content — strings and line-kind specs consumed by main.py render functions.

Line-kind tuples used in 'lines' lists:
  ('blank',)
  ('dim',    text)
  ('amber',  text)
  ('cmd',    key, desc)                              ← hi key, dim arrow, amber desc
  ('segs',   [(text, bold), …], desc)                ← key as bold/dim segments
  ('smudge', key, smudge_prefix, clear_tail, gate)  ← smudge block + dim tail
  ('smudge_seg', key_text, hide_prefix, desc)       ← key with its head smudged
  ('v_sight',)                                       ← warden-sight special v row

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

OPERATOR_CODEX_SCROLL = {
    'title': "◈   The Operator's Codex   ◈",
    'lines': [
        ('dim',    '  In the Loom, they carved the grammar of unmaking.'),
        ('blank',),
        ('cmd',    'd{m}', 'delete to motion'),
        ('cmd',    'dd  ', 'delete line'),
        ('smudge', 'y{m}', 'y',  'ank (copy without cutting)', 'y'),
        ('smudge', 'c{m}', 'ch', 'ange text (del + insert)',   'c'),
        ('blank',),
        ('amber',  '  "  holds what you cut.  Something awaits.'),
    ],
}

ARCHIVISTS_METHOD_SCROLL = {
    'title': "◈   The Archivist's Method   ◈",
    'lines': [
        ('dim',    '  The Archivist copied before erasing. Wise.'),
        ('blank',),
        ('cmd',    'y{m}', 'yank (copy without cutting)'),
        ('cmd',    'yy  ', 'yank line'),
        ('cmd',    'p   ', 'put after cursor'),
        ('smudge', 'c{m}', 'ch', 'ange text (del + insert)', 'c'),
        ('blank',),
        ('amber',  '  d and y share the same register.'),
        ('dim',    '  Paste before deleting — or lose your copy.'),
    ],
}

WHOLE_WORD_SCROLL = {
    'title': '◈   The Whole Word   ◈',
    'lines': [
        ('dim',    '  Position within the word ceased to matter.'),
        ('blank',),
        ('cmd',    'iw', 'inner word  (anywhere in word)'),
        ('cmd',    'aw', 'around word (includes space)'),
        ('blank',),
        ('smudge', 'i(',  'i',  'nner parens', 'i('),
        ('smudge', 'i"',  'in', 'side quotes', 'i"'),
        ('blank',),
        ('amber',  '  The boundary is the rune, not where you stand.'),
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
        'id':         'visual',
        'title':      "The Warden's Sight",
        'dropped_by': 'The Warden Surveyor',
        'level_slug': 'warden_surveyor',
        'level_name': 'The Warden Surveyor',
        'content':    WARDEN_SIGHT_SCROLL,
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
        'id':         'd_op',
        'title':      "The Operator's Codex",
        'dropped_by': 'The Warden Pathfinder',
        'level_slug': 'warden_pathfinder',
        'level_name': 'The Warden Pathfinder',
        'content':    OPERATOR_CODEX_SCROLL,
    },
    {
        'id':         'y_op',
        'title':      "The Archivist's Method",
        'dropped_by': 'The Warden Manifold',
        'level_slug': 'warden_manifold',
        'level_name': 'The Warden Manifold',
        'content':    ARCHIVISTS_METHOD_SCROLL,
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
]
