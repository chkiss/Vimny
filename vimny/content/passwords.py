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

"""The words a `fancy_door` opens for, sorted by the only thing that matters —
their SHAPE under vim's two word models.

A fancy door opens for a register whose text reads its password and for nothing
else, so the password's SPELLING is the forcing device: which motion takes it in
one cut is decided by where the punctuation and the spaces fall. That is what
the four pools are. They are not flavour lists; picking the wrong pool for a
door is picking the wrong lesson for it.

  PLAIN   one token, no punctuation. `w`/`e`/`b` and `W`/`E`/`B` agree on it,
          so it serves the SMALL-word lessons — the big-word twin is no cheaper
          and no dearer, and the surrounding geometry decides the rest.
  SPLIT   one token with punctuation INSIDE it. This is where the two models
          part company: `w` stops at the punctuation and takes a fragment, `W`
          runs to the whitespace and takes the whole. A door wanting the whole
          thing therefore cannot be opened by the small-word motion at all.
          These are the leet spellings, and the leet is not decoration — the
          `.` and `-` are the entire mechanism.
  QUERY   begins with `?`, for `dF?`. `dF?` cuts from the `?` up to the cursor,
          so the mark has to LEAD the password, which is why these read as
          challenges: the door is asking. (These are the one pool NOT drawn
          from real passwords — they are real sentry challenges, leetified to
          carry the leading mark.)
  PHRASE  more than one word. No character motion takes a space, so only a LINE
          motion (`0`, `$`, `dd`) can hand one of these over whole.

DIRECTION DOES NOT SORT THEM. A westward `db` cuts the same token an eastward
`dw` does; what the direction decides is where the word is laid relative to the
door and whether the player opens it with `p` or `P`. So a password may serve
either facing, and a level is free to shuffle within a pool.

They are real passwords from other people's dungeons — Durin's door, the Fat
Lady, Dumbledore's office, Colossal Cave, NetHack, Ali Baba, DOOM, Falken's
backdoor into the WOPR, and one IRC channel (`hunter2`, which is a joke ABOUT a
password and is here because everyone recognises it) — because a password the
player half-recognises is one they read as a password before anything explains
it.

EVERY ENTRY MUST BE A REAL ONE, and the rule is load-bearing rather than
decorative. `abstinence and toffee` sat here until 2026-08-02 and was not from
anywhere: it welded the Fat Lady's `Abstinence` onto Dumbledore's `Toffee
Eclairs` and read, convincingly, like something half-remembered. That is the
failure mode — an invented password is indistinguishable from a real one to
whoever adds the next, so the pool drifts into pastiche and the recognition the
whole idea rests on quietly stops being real. (`justice for all` went at the
same time; it is a Metallica record, not a door.)

A password also appears in ONE pool only. The leet spellings and the phrases
were separately dealt `open sesame` / `0pen-sesame`, `fortuna major` /
`f0rtuna-maj0r`, `pig snout` / `p1g.sn0ut` — the same door twice in one run,
which reads as the level repeating itself rather than as two shapes.

The forge reads these too (`:entity fancy_door password=…` offers them), so an
author placing a door by hand picks from the same words the built levels use —
and the free-text row is still there, because a level with its own fiction
should be able to write its own words.
"""

PLAIN = ('mellon', 'xyzzy', 'plugh', 'dissendium', 'wattlebird',
         'balderdash', 'swordfish', 'iddqd', 'idkfa', 'elbereth',
         'shibboleth', 'joshua', 'plover', 'flibbertigibbet', 'hunter2')

SPLIT = ('c4put.dr4c0nis', 'f0rtuna-maj0r', 'p1g.sn0ut', 'sherbet-lem0n',
         't0ffee.eclairs', 'scurvy-cur', 'lem0n.dr0p')

QUERY = ('?wh0g0esthere', '?speakfr1end', '?fr1end0rfoe', '?whatw0rd')

#: Durin's door; Ali Baba; the hymn NetHack engraves; Colossal Cave's giant
#: room; and the Fat Lady and Dumbledore's office, which supply most of the
#: real multi-word ones.
PHRASE = ('speak friend and enter', 'open sesame', 'elbereth gilthoniel',
          'mimbulus mimbletonia', 'banana fritters', 'cockroach cluster',
          'fizzing whizbee', 'acid pops', 'fee fie foe foo')

#: `(name, words, what the shape MEANS for the cut)` — in the order an author
#: meets the lessons, so the forge's list reads as a curriculum rather than as
#: an alphabet. The note is the one thing a level designer has to know before
#: choosing: a door is a lesson about a motion, and the pool IS the motion.
POOLS = (
    ('plain',  PLAIN,  'one token, no punctuation — w/e/b and W/E/B agree'),
    ('split',  SPLIT,  'punctuation INSIDE — only the BIG-word motions take it whole'),
    ('query',  QUERY,  'leading ? — the mark dF? searches back to'),
    ('phrase', PHRASE, 'more than one word — only a LINE motion (0, $, dd) takes it'),
)

#: word → the pool it came from, for anything that wants to say what shape a
#: password is without re-deriving it from the spelling.
POOL_OF = {w: name for name, words, _note in POOLS for w in words}

ALL = tuple(w for _name, words, _note in POOLS for w in words)
