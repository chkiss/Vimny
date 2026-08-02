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

"""The Operator's Vault teaches ten operator+motion pairs — is each one FORCED?

`tests/test_operators_vault_lessons.py` asks whether a corridor can be SKIPPED
(by a teleport). This file asks the sharper question: standing in the corridor
and doing the work, can you do it with the WRONG OPERATOR and still pay par?

That is the failure this level kept shipping. `d$` cleared corridor 1 for 68 in
a 69-par level; `d^` cleared corridors 2, 4 and 6. Every one of those was found
by hand, one at a time, after the level had been declared clean — because the
level's own tests only ever drove the canonical tape and the tape, naturally,
passed. A cheese that costs LESS than par is not a rough edge; it means the
lesson's command is not the cheapest route, which is the only definition of
"forced" this project uses.

So: substitute, drive, and compare. For each corridor, every other d-motion the
player holds is spliced into the canonical route in place of the real cut, and
the WHOLE tape is replayed. A substitution that wins for <= par is a lesson
that isn't taught.

WHY IT CANNOT BE A STATIC CHECK. Whether `dE` over-reaches depends on where the
gate stands, what the seed drew for the corridor's password, where the cursor
arrived, and what the reflow did to the row after the cut. None of that is
legible from the layout constants. Only driving it settles it.

THE FORCING DEVICE. One entity does the whole job now: a `fancy_door` opens for
a register whose TEXT reads its password and for nothing else, so a cut that
reaches too little hands it a fragment and a cut that reaches too far hands it
the password plus whatever it swept up. Both are refused. The level used to try
this with goblins, and goblins can only ever hold the LOWER bound — a guard
punishes a cut that under-reaches because he survives it, but every guard a `dw`
kills a `d$` kills too, so nothing held the ceiling and half the corridors fell
to the wrong operator. The redesign (2026-08-02) took the guards out entirely.

WHAT SURVIVES, AND WHY IT IS NOT A DEBT. Three corridors are still tied by one
other motion each, and all three ties are vim being consistent rather than the
lesson leaking:

  * C1 `dw` / `de` — these cut the same TEXT from the same cell. They differ
    only by the trailing space, and the gate collapses whitespace (it has to,
    or `dd`'s column padding would never match anything). Where the lesson is
    `e`, the corridor breaks the tie by dropping the player on BLANK floor a
    cell short of the password, so `w` lands on its head and cuts nothing —
    but a `w` corridor has no matching trick, because `e` reaches exactly as
    far as `w` does.
  * C7 `dW` / `dE` — the same tie, one word model up.
  * C8 `d0` / `d^` — the phrase IS the line's first non-blank, so on that row
    the two motions are the same motion.

`_UNFORCED` is the live register of these. It is not an allowance: the test
fails BOTH ways, so a corridor that turns out to be forced after all must be
taken out of the list, and the list cannot rot into a lie.
"""
import re

import pytest

import generation.dungeon_gen as dg
from sharing.replay import replay_tape
from tests import SEEDS

#: Every operator+motion pair the player holds by this level. `d^` is in here
#: because leaving it out is exactly how three of these corridors shipped
#: broken — an audit is only as good as its worst-remembered motion.
_ALTS = ('d w', 'd W', 'd e', 'd E', 'd b', 'd B',
         'd 0', 'd ^', 'd $', 'd d', 'd F ?', 'd f ?')

#: corridor number -> the motions that tie its lesson at par. Every entry here
#: is one of the three irreducible ties described above; there is no entry that
#: a better layout could remove, and anything NEW appearing here is a bug in the
#: level, not a line to add.
_UNFORCED = {
    1: {'d e'},          # e reaches exactly as far as w, from the word's head
    7: {'d E'},          # the same tie, one word model up
    8: {'d ^'},          # the phrase is the line's first non-blank
}


#: A token that ends a corridor by leaving it: `3j` down a shaft, `2j` off the
#: ledge, or a `{n}G` that lands on the same cell for a key less. MATCHING ONLY
#: `{n}j` is how this file quietly broke once — the tape golfed C2's descent to
#: `7G`, the splitter did not recognise it, C2 and C3 merged into one segment,
#: and every corridor after them was audited under the wrong number (the run
#: reported "corridor 6 teaches dW", which is corridor 7's lesson).
_DESCENT = re.compile(r'^\d+[jG]$')


def _segments():
    """The canonical tape split at the descent that ends each corridor, so
    segment k is exactly the work done IN corridor k. C10 ends `2j` (the ride
    down to the ledge) and carries the run out to the exit, so the tail joins
    it rather than becoming a phantom eleventh corridor."""
    segs, cur = [], []
    for t in dg._OV_ANSWER.split():
        cur.append(t)
        if _DESCENT.match(t):
            segs.append(cur)
            cur = []
    if cur:
        segs[-1].extend(cur)
    assert len(segs) == 10, f'the tape no longer reads as ten corridors: {segs}'
    return segs


def _cut_span(seg):
    """Locate the `d {motion}` inside a segment as (index, token count).
    `dF?`/`df?` are three tokens; everything else is two."""
    for i, t in enumerate(seg):
        if t == 'd':
            wide = i + 1 < len(seg) and seg[i + 1] in ('F', 'f', 'T', 't')
            return i, (3 if wide else 2)
    raise AssertionError(f'no cut in segment {seg!r} — the tape changed shape')


@pytest.mark.parametrize('seed', SEEDS)
def test_every_corridor_is_beaten_only_by_its_own_operator(seed):
    """The audit. For each corridor, splice in every other d-motion and drive
    the whole route; nothing may win for par or less except the real lesson."""
    segs = _segments()
    par = dg.build_dungeon_operators_vault(seed).rooms[0].par

    for k, seg in enumerate(segs, 1):
        i, n = _cut_span(seg)
        canonical = ' '.join(seg[i:i + n])
        allowed = _UNFORCED.get(k, set())
        cheap = set()

        for alt in _ALTS:
            if alt == canonical:
                continue
            spliced = seg[:i] + alt.split() + seg[i + n:]
            tape = ' '.join(tok for s in segs[:k - 1] + [spliced] + segs[k:]
                            for tok in s)
            dungeon = dg.build_dungeon_operators_vault(seed)
            try:
                res = replay_tape(dungeon, 'operators_vault', tape)
            except Exception:
                continue                     # a route that cannot even be driven
            if res.won and res.spent <= par:
                cheap.add(alt)

        assert not (cheap - allowed), (
            f'seed {seed}: corridor {k} teaches {canonical!r} but '
            f'{sorted(cheap - allowed)} also wins for <= par ({par}) — the '
            f'lesson is not forced')
        assert not (allowed - cheap), (
            f'seed {seed}: corridor {k} lists {sorted(allowed - cheap)} as an '
            f'unforced substitution, but it no longer wins cheaply. Take it '
            f'out of _UNFORCED — a stale debt register hides the next one.')


@pytest.mark.parametrize('seed', SEEDS)
def test_every_corridor_is_held_by_a_door_that_reads_the_register(seed):
    """The claim this level's design rests on, asserted rather than believed:
    there are ten corridors and ten gates, each wanting a different word. If a
    gate ever goes missing its corridor has no ceiling at all, and the audit
    above would go quiet about it — a corridor with nothing to open is not a
    corridor the substitutions can fail in."""
    room = dg.build_dungeon_operators_vault(seed).rooms[0]
    gates = [e for e in room.entities if e.kind == 'fancy_door']
    assert len(gates) == 10
    assert all(e.password for e in gates)
    assert len({e.password for e in gates}) == 10, (
        'two gates want the same word — one corridor\'s cut opens another\'s')
    assert not any(e.kind == 'goblin' for e in room.entities), (
        'a guard is back in the vault; guards can only hold the lower bound, '
        'which is the failure this level was redesigned out of')
