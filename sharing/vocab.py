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

"""The word sources, behind one stable API.

An author writing "fill this floor with words" needs the same pools the shipped
builders draw from. Today those pools are reachable only from inside
`generation/dungeon_gen.py`. This module is the shared front door.

The rule that matters: **the loader must be the single implementation.** A fill
directive that resolves one way for the author and another for the player is a
broken level — the solution tape was recorded against words that are no longer
there. So both paths call `words()`, and both pass the level's own seeded RNG.

Author-supplied pools (`custom`) come from the level file itself and are
validated before they get here; see `sharing/validate.py`.
"""
from __future__ import annotations

import random

from content import proverbs

#: Pools an author may name in a `fill` directive.
POOLS = ('plain', 'mixed', 'proverbs', 'misquotes', 'custom')


def words(pool: str, length: int, rng: random.Random,
          custom: dict | None = None) -> str:
    """One word of exactly `length` characters from `pool`.

    Falls back to the 1-character table when a pool has nothing at that length,
    which is what the shipped builders already do — a fill directive should
    thin out rather than crash on an unlucky length.
    """
    table = word_table(pool, custom)
    choices = table.get(length) or table.get(1)
    if not choices:
        raise ValueError(f'vocabulary pool {pool!r} is empty')
    return rng.choice(choices)


def word_table(pool: str, custom: dict | None = None) -> dict:
    """The whole pool as {length: [word, ...]}. Cached for the shipped pools."""
    if pool == 'custom':
        if not custom:
            raise ValueError("fill named the 'custom' pool but the level "
                             "declares no `vocabulary` block")
        return custom
    if pool not in POOLS:
        raise ValueError(f'unknown vocabulary pool {pool!r}; '
                         f'known pools are {", ".join(POOLS)}')
    return _shipped_table(pool)


def by_length(word_list) -> dict:
    """Group an arbitrary word list into the {length: [...]} shape a pool uses.

    This is the shape an author's `vocabulary` block is turned into, and the one
    `word_table` returns, so a custom pool is indistinguishable from a shipped
    one at the point of use.
    """
    table: dict = {}
    for w in word_list:
        table.setdefault(len(w), []).append(w)
    return table


_CACHE: dict = {}


def _shipped_table(pool: str) -> dict:
    if pool in _CACHE:
        return _CACHE[pool]
    if pool in ('plain', 'mixed'):
        # The vocab files are the builders' own source; import lazily so this
        # module does not drag the whole generation package into a validator.
        from generation import dungeon_gen as dg
        dg._load_vocab_tables()
        table = dg._VOCAB_PLAIN_BY_LEN if pool == 'plain' else dg._VOCAB_MIXED_BY_LEN
    elif pool == 'proverbs':
        table = by_length([w for saying in proverbs.PLAIN for w in saying])
    else:                                   # misquotes — the wrong words only
        table = by_length([w for wrong, _idx, _cure in proverbs.MISQUOTES
                           for w in wrong])
    _CACHE[pool] = table
    return table


def proverb(rng: random.Random) -> tuple:
    """A whole saying, as a tuple of words — for a `proverb_line` fill."""
    return rng.choice(proverbs.PLAIN)


def misquote(rng: random.Random) -> tuple:
    """A (wrong_words, index, cure) triple — a saying with one word wrong."""
    return rng.choice(proverbs.MISQUOTES)
