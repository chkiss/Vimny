"""Scroll content — strings and line-kind specs consumed by main.py render functions.

Line-kind tuples used in 'lines' lists:
  ('blank',)
  ('dim',    text)
  ('amber',  text)
  ('cmd',    key, desc)                        ← hi key, dim arrow, amber desc
  ('smudge', key, smudge_prefix, clear_tail)   ← smudge block + dim tail
  ('v_sight',)                                 ← warden-sight special v row
"""

RELIQUARY_SCROLL = {
    'title':   '◈   The Unnamed Register   ◈',
    'intro':   '  Scrawled on the scroll: a revelation.',
    'outro':   '  Your cuts are visible in the statusline.',
    'p_text':  '  holds all you delete — there must be some use...',
    'kv_rows': [
        ('clear',   'x', 'deletes a character  '),
        ('smudged', '▒', '▒',   'eletes a range'),
        ('smudged', '▒', '▒▒▒', 'nges text'),
    ],
}

REGISTER_TUTORIAL_SCROLL = {
    'title':   '◈   The Unnamed Register   ◈',
    'intro':   '  Scrawled on the scroll: a revelation.',
    'outro':   '  Your cuts are visible in the statusline.',
    'p_text':  '  holds all you delete — there must be some use...',
    'kv_rows': [
        ('clear', 'x', 'deletes a character  '),
        ('clear', 'd', 'deletes a range      '),
        ('clear', 'c', 'changes text         '),
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

OPERATOR_CODEX_SCROLL = {
    'title': "◈   The Operator's Codex   ◈",
    'lines': [
        ('dim',    '  In the Loom, they carved the grammar of unmaking.'),
        ('blank',),
        ('cmd',    'd{m}', 'delete to motion'),
        ('cmd',    'dd  ', 'delete line'),
        ('smudge', 'y{m}', 'y',  'ank (copy without cutting)'),
        ('smudge', 'c{m}', 'ch', 'ange text (del + insert)'),
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
        ('smudge', 'c{m}', 'ch', 'ange text (del + insert)'),
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
        ('smudge', 'i(',  'i',  'nner parens'),
        ('smudge', 'i"',  'in', 'side quotes'),
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
        ('smudge', 'gv',    '',  'reselect last visual span'),
        ('blank',),
        ('amber',  '  See. Select. Strike.'),
        ('dim',    '  The eye and the hand are one.'),
    ],
}


# ── Scroll catalog ────────────────────────────────────────────────────────────
# id matches the key stored in progress['extras'] when the scroll is discovered.
# dropped_by / level_id / level_name are display metadata only.

SCROLL_CATALOG = [
    {
        'id':         'register',
        'title':      'The Unnamed Register',
        'dropped_by': 'The Reliquary',
        'level_id':   11,
        'level_name': "The Reliquary",
        'content':    REGISTER_TUTORIAL_SCROLL,
    },
    {
        'id':         'visual',
        'title':      "The Warden's Sight",
        'dropped_by': "The Warden's Keep",
        'level_id':   51,
        'level_name': "The Warden's Keep",
        'content':    WARDEN_SIGHT_SCROLL,
    },
    {
        'id':         'd_op',
        'title':      "The Operator's Codex",
        'dropped_by': 'The Warden Unbound',
        'level_id':   141,
        'level_name': 'The Warden Unbound',
        'content':    OPERATOR_CODEX_SCROLL,
    },
    {
        'id':         'y_op',
        'title':      "The Archivist's Method",
        'dropped_by': 'The Warden Manifold',
        'level_id':   251,
        'level_name': 'The Warden Manifold',
        'content':    ARCHIVISTS_METHOD_SCROLL,
    },
    {
        'id':         'text_obj',
        'title':      'The Whole Word',
        'dropped_by': 'The Warden Scrivener',
        'level_id':   321,
        'level_name': 'The Warden Scrivener',
        'content':    WHOLE_WORD_SCROLL,
    },
    {
        'id':         'visual_op',
        'title':      "The Warden's Act",
        'dropped_by': 'The Warden Scrivener',
        'level_id':   321,
        'level_name': 'The Warden Scrivener',
        'content':    WARDEN_ACT_SCROLL,
    },
]
