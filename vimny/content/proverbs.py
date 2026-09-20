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

"""The proverb pool — sense, not decree (docs/blueprints/sense_not_decree.md §2).

Puzzle texts are famous PUBLIC-DOMAIN proverbs the player knows by heart:
a level corrupts one, and the cure is the word everyone knows — the door's
"true reading" needs no plaque to decree it.

Three shapes:

- ``PLAIN``: canonical proverbs, as word tuples.  Used by INTRUDER doors —
  a seeded junk word is laid into the saying and the lesson deletes it
  (diw/daw/diW/…).  Any proverb fits any intruder slot; the builder chooses
  the insertion point so the junk word starts at the slot's fixed column
  (par invariance is column-anchored, not text-anchored).

- ``MISQUOTES``: ``(wrong_words, idx, cure)`` — the proverb as spoken with
  ONE word wrong (``wrong_words[idx]``), and the famous word that cures it.
  Used by CHANGE doors (ciw/ce/R/…).  Pool entries are grouped by cure
  length because the cure is TYPED — par counts its characters.

- ``STANZAS``: the opening lines of a nursery rhyme or verse, in their TRUE
  order, as a tuple of lines.  Used by doors that want a line ORDER rather
  than a word: the level scrambles the lines and the player, who knows the
  rhyme, knows which one belongs where — no plaque may decree it.  Three
  lines is the floor, because a level that wants "the oldest" of the cuts
  needs at least three to make old mean anything.

Builders draw per seed and filter geometrically (prefix must fit west of
the slot column, tail east of it); keep every entry universally known and
long out of copyright.
"""

PLAIN = (
    ('a', 'stitch', 'in', 'time', 'saves', 'nine'),
    ('look', 'before', 'you', 'leap'),
    ('the', 'early', 'bird', 'catches', 'the', 'worm'),
    ('a', 'watched', 'pot', 'never', 'boils'),
    ('too', 'many', 'cooks', 'spoil', 'the', 'broth'),
    ('actions', 'speak', 'louder', 'than', 'words'),
    ('better', 'late', 'than', 'never'),
    ('practice', 'makes', 'perfect'),
    ('birds', 'of', 'a', 'feather', 'flock', 'together'),
    ('a', 'rolling', 'stone', 'gathers', 'no', 'moss'),
    ('strike', 'while', 'the', 'iron', 'is', 'hot'),
    ('all', 'that', 'glitters', 'is', 'not', 'gold'),
    ('many', 'hands', 'make', 'light', 'work'),
    ('honesty', 'is', 'the', 'best', 'policy'),
    ('curiosity', 'killed', 'the', 'cat'),
    ('still', 'waters', 'run', 'deep'),
    ('no', 'news', 'is', 'good', 'news'),
    ('two', 'wrongs', 'do', 'not', 'make', 'a', 'right'),
    ('the', 'pen', 'is', 'mightier', 'than', 'the', 'sword'),
    ('time', 'is', 'money'),
    ('haste', 'makes', 'waste'),
    ('live', 'and', 'let', 'live'),
    ('no', 'pain', 'no', 'gain'),
    ('knowledge', 'is', 'power'),
)

# (wrong_words, idx, cure) — cure lengths are load-bearing (typed chars are
# priced); keyed groups below.
MISQUOTES = (
    (('curiosity', 'killed', 'the', 'dog'), 3, 'cat'),
    (('strike', 'while', 'the', 'iron', 'is', 'wet'), 5, 'hot'),
    (('a', 'watched', 'jug', 'never', 'boils'), 2, 'pot'),
    (('the', 'cat', 'is', 'out', 'of', 'the', 'jar'), 6, 'bag'),
    (('rome', 'was', 'not', 'built', 'in', 'a', 'week'), 6, 'day'),
    (('make', 'hay', 'while', 'the', 'moon', 'shines'), 4, 'sun'),
    (('look', 'before', 'you', 'jump'), 3, 'leap'),
    (('the', 'early', 'bird', 'catches', 'the', 'snake'), 5, 'worm'),
    (('a', 'rolling', 'stone', 'gathers', 'no', 'dust'), 5, 'moss'),
    (('all', 'that', 'glitters', 'is', 'not', 'tin'), 5, 'gold'),
    (('actions', 'speak', 'louder', 'than', 'deeds'), 4, 'words'),
    (('too', 'many', 'cooks', 'spoil', 'the', 'soup'), 5, 'broth'),
    (('better', 'late', 'than', 'sorry'), 3, 'never'),
    (('many', 'hands', 'make', 'short', 'work'), 3, 'light'),
    (('birds', 'of', 'a', 'feather', 'stick', 'together'), 4, 'flock'),
    (('practice', 'makes', 'flawless'), 2, 'perfect'),
    (('honesty', 'is', 'the', 'best', 'excuse'), 4, 'policy'),
)


# Verses whose LINE ORDER everyone knows — the cue a register level needs when
# the thing being retrieved is a whole line rather than a word.  Lower case and
# unpunctuated like the rest of the pool: these are carved into stone floors,
# not printed.  Every one is a nursery rhyme or a folk verse centuries out of
# copyright.
STANZAS = (
    ('twinkle twinkle little star',
     'how i wonder what you are',
     'up above the world so high'),
    ('jack and jill went up the hill',
     'to fetch a pail of water',
     'jack fell down and broke his crown'),
    ('humpty dumpty sat on a wall',
     'humpty dumpty had a great fall',
     'all the kings horses and all the kings men'),
    ('mary had a little lamb',
     'its fleece was white as snow',
     'and everywhere that mary went'),
    ('hickory dickory dock',
     'the mouse ran up the clock',
     'the clock struck one and down he run'),
    ('row row row your boat',
     'gently down the stream',
     'merrily merrily merrily merrily'),
)


def stanzas_of_width(lo, hi):
    """The stanzas whose every line is between ``lo`` and ``hi`` chars wide.

    A floor is a fixed width, so a builder picks its verse by what fits — and
    filtering by the WIDEST line keeps the draw geometric, which is what keeps
    par seed-invariant (the column-anchor law)."""
    return tuple(s for s in STANZAS
                 if all(lo <= len(line) <= hi for line in s))


def misquotes_by_cure_len(length):
    """The misquote entries whose typed cure is exactly ``length`` chars."""
    return tuple(m for m in MISQUOTES if len(m[2]) == length)


def text_of(words):
    return ' '.join(words)


def prefix_len(words, k):
    """Length of ``words[:k]`` joined — 0 when k == 0."""
    return len(' '.join(words[:k])) if k else 0
