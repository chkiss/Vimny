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

"""The Operator's Vault teaches ten operator+motion pairs. Can you JUMP them?

Each corridor is one lesson — `dw`, `db`, `de`, `dB`, `dE`, `dF?`, `dW`, `d0`,
`d$`, `dd` — and the whole level is worth nothing if a player can reach the exit
by line-jumping over the words instead of cutting through them. `G`/`{n}G`/`gg`
/`H`/`M`/`L` TELEPORT to a row's first non-blank whether or not a foot could walk
there, so this is the front that geometry alone does not defend.

THREE THINGS DEFEND IT, and this file asserts all three:

  * FOG. A fogged cell is impassable, so a jump cannot land in a corridor the
    player has not opened. This is why the fog being DERIVED matters — it is a
    consequence of the walls and the shut doors, so it holds only as long as
    EVERY SHAFT HANGS BEHIND A GATE. That is the constraint the 2026-08-02
    plan is built around, and it is not free: the level teaches `p` and not
    `P`, so a gate must always be east of the player. A forward corridor gets
    that for nothing (gate at the line end, shaft beneath it); a backward one
    cannot, so it keeps no gate at all — it drops at col 2 and its gate waits
    one row down at col 3, opened with the word the cut is still holding.
  * THE PITS. Row 4's first standable cell is the pocket at (4, 3) — so the one
    jump that does reach past corridor 1 drops the player in a hole rather than
    at the next lesson. That is what the trap column is for.
  * THE VAULT. It opens only when all ten gates stand open, and a jump speaks
    nothing — so even a landing that got through pays for nothing.

The audit is STAGED because the danger is not at the spawn — it is three
corridors in, when three gates have opened and the fog has lifted behind them.
A jump audit that only ran on the as-built room would pass while the level was
being cheesed from the middle.
"""
import re

import pytest

import generation.dungeon_gen as dg
from engine.motion import apply_motion
from engine.player import Player
from engine.world import CellType
from sharing.replay import replay_tape
from tests import SEEDS

CORR = dg._OV_CORR_ROWS

#: Every teleport a player of this level has. The Vault sits after the
#: Lineheads (`G`, `gg`) and the Screen Vault (`H`, `M`, `L`), and counts are
#: taught long before either.
_JUMPS = ([('gg', 1, False), ('G', 1, False),
           ('H', 1, False), ('M', 1, False), ('L', 1, False)]
          + [('G', n, True) for n in range(1, 36)])


#: What ends a corridor: `{n}j` down a shaft, or a jump that lands on the same
#: cell for a key less — `{n}G`, or (since the 2026-08-02 golf) a BARE `G`, which
#: the derived fog aims at the frontier for one key. See the note in
#: test_operators_vault_corridors.py — a splitter that only knew `{n}j` silently
#: merged two corridors when the tape was golfed, and every stage after them was
#: audited off by one. It happened AGAIN with bare `G`, which is why the pattern
#: now allows the count to be absent and both files assert the segment count.
_DESCENT = re.compile(r'^(\d+j|\d*G)$')


def _segments():
    """The canonical tape, split at the descent that ends each corridor. Segment
    k is the work done IN corridor k, so a prefix of k segments leaves the player
    having solved exactly k lessons. C10 ends `2j` (the ride down to the ledge)
    and carries the run out to the exit, so the tail joins it."""
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


def _landings(room, player):
    """Every row a teleport could put the player on from where they stand."""
    out = set()
    probe = Player()
    for motion, count, given in _JUMPS:
        probe.row, probe.col = player.row, player.col
        try:
            apply_motion(probe, motion, count, room, count_given=given, game_h=36)
        except Exception:                      # a motion that cannot resolve is no jump
            continue
        out.add((probe.row, probe.col))
    return out


@pytest.mark.parametrize('seed', SEEDS)
def test_no_jump_from_the_spawn_reaches_a_lesson_you_have_not_opened(seed):
    """The as-built audit: standing at the entrance, nothing carries you past
    corridor 1 except into the pit that guards it."""
    room = dg.build_dungeon_operators_vault(seed).rooms[0]
    player = Player()
    player.row, player.col = room.spawn_pos
    for (r, c) in _landings(room, player):
        assert r <= CORR[1], f'a jump reached row {r} — past corridor 1'
        if r in CORR[1:]:
            raise AssertionError(f'a jump landed IN corridor row {r}')


@pytest.mark.parametrize('seed', SEEDS)
def test_no_jump_reaches_an_unopened_lesson_AT_ANY_STAGE_of_the_route(seed):
    """THE STAGED AUDIT, which is the one that would catch a real regression.

    The danger was never the entrance — it is three corridors in, when three
    gates have opened and the fog has lifted behind them. So walk the canonical
    route corridor by corridor and check, at each stopping point, that nothing
    has landed BEHIND A SHUT GATE.

    "Behind a shut gate" rather than "in a corridor you have not opened", and
    the difference is the whole point. A jump CAN land at col 2 of the corridor
    below — that is the cell a backward corridor drops onto, in front of its
    gate, and it is fogged only until the corridor above is walked. Landing
    there early is harmless: the gate is still shut, the lesson's text is still
    dark behind it, and the player has no word to spend. What must never happen
    is arriving east of a door that has not been opened."""
    segs = _segments()
    for k in range(1, len(segs)):
        tape = ' '.join(t for s in segs[:k] for t in s)
        d = dg.build_dungeon_operators_vault(seed)
        replay_tape(d, 'operators_vault', tape)
        room = d.rooms[0]
        shut = {(e.row, e.col) for e in room.entities
                if e.kind == 'fancy_door' and e.alive}
        probe = Player()
        probe.row, probe.col = CORR[k], 2
        for (r, c) in _landings(room, probe):
            behind = [(gr, gc) for (gr, gc) in shut if gr == r and gc < c]
            assert not behind, (
                f'seed {seed}: after {k} corridor(s), a jump landed at {(r, c)} '
                f'— east of the shut gate(s) {behind}')


@pytest.mark.parametrize('seed', SEEDS)
def test_a_jump_that_skips_a_corridor_cannot_win(seed):
    """THE ONE THAT MATTERS, and it is about OUTCOMES, not landings.

    An earlier version of this test asserted that no jump could LAND in a
    corridor the player had not opened, and it failed: after corridor 1, `7G`
    lands in corridor 3. That turned out to be the wrong question. Landing
    there is harmless — what matters is whether you can finish from there.

    Since 2026-08-02 every corridor is held by a gate that opens only for a
    register reading its password, and the vault opens only when all ten stand
    open. So a corridor you jumped over is a corridor whose word has not been
    spoken, and the vault will not yield. The jump still happens; it just does
    not pay — which is now the level's ONLY defence, the fog having gone with
    the geometry (see this module's docstring).
    """
    par = dg.build_dungeon_operators_vault(seed).rooms[0].answer
    segs = _segments()
    for k in range(1, len(segs) + 1):
        # replace corridor k's work with its bare descent — the player rides
        # past the lesson instead of doing it
        drop = [segs[k - 1][-1]] if segs[k - 1][-1] in ('3j', '2j') else ['3j']
        tape = ' '.join(t for s in segs[:k - 1] + [drop] + segs[k:] for t in s)
        d = dg.build_dungeon_operators_vault(seed)
        res = replay_tape(d, 'operators_vault', tape)
        shut = [e for r in d.rooms for e in r.entities
                if e.kind == 'fancy_door' and e.alive]
        assert not res.won, (
            f'seed {seed}: skipping corridor {k} still won — its lesson is '
            f'optional ({len(shut)} gate(s) left shut)')
    # …and the route that does the work wins, so the level is not merely hard.
    d = dg.build_dungeon_operators_vault(seed)
    assert replay_tape(d, 'operators_vault', par).won


@pytest.mark.parametrize('seed', SEEDS)
def test_the_vault_is_what_makes_every_gate_required(seed):
    """The mechanism behind the test above, asserted directly: no gate may be
    left shut in a winning run. This is what a teleport cannot do — a jump
    speaks nothing.

    It used to assert that no GUARD was left alive, and after the guards were
    removed it went on passing while asserting nothing at all. A vacuous audit
    is worse than a missing one, because the suite still reads as covered."""
    d = dg.build_dungeon_operators_vault(seed)
    room = d.rooms[0]
    gates = [e for e in room.entities if e.kind == 'fancy_door']
    assert len(gates) == 10, 'nothing to leave shut — this audit would be empty'
    res = replay_tape(d, 'operators_vault', room.answer)
    assert res.won
    assert not [e for r in d.rooms for e in r.entities
                if e.kind == 'fancy_door' and e.alive]
    assert not [e for r in d.rooms for e in r.entities
                if e.kind == 'seal_door' and e.alive]


@pytest.mark.parametrize('seed', SEEDS)
def test_the_pit_is_what_catches_the_one_jump_that_does_carry(seed):
    """`G` from the spawn lands on row 4 — and row 4's first standable cell is
    the pocket at (4, 3), not a corridor. Remove the pit and that jump becomes a
    free step toward the second lesson."""
    room = dg.build_dungeon_operators_vault(seed).rooms[0]
    player = Player()
    player.row, player.col = room.spawn_pos
    apply_motion(player, 'G', 1, room, count_given=False, game_h=36)
    assert (player.row, player.col) in dg._OV_POCKETS, (player.row, player.col)


@pytest.mark.parametrize('seed', SEEDS)
def test_every_corridor_past_the_first_starts_fully_fogged(seed):
    """The precondition the staged audit rests on. If a corridor is lit at
    build, a `{n}G` lands in it and its lesson is optional.

    It asks whether EVERY FLOOR CELL is dark, and both halves of that matter.
    The version before 2026-08-02 asked whether ANY cell in `range(1, cols)`
    was fogged — and col 1 of every corridor row is the misted seep, which is
    fog by contract, so the test could not fail. It went on passing through a
    redesign that lit the entire level. A precondition that cannot fail is not
    a precondition."""
    room = dg.build_dungeon_operators_vault(seed).rooms[0]
    for r in CORR[1:]:
        lit = [(r, c) for c in range(2, 58)
               if room.cells[r][c] == CellType.FLOOR and (r, c) not in room.fog_cells]
        assert not lit, f'corridor row {r} is lit from the spawn: {lit[:5]}'
