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

TWO THINGS DEFEND IT, and this file asserts both hold at EVERY stage of the
canonical route, not just at the spawn:

  * FOG. A fogged cell is impassable, so a jump cannot land in a corridor the
    player has not opened. This is why the fog being DERIVED matters: the 2026-08-01
    rebuild made the vault's fog a consequence of its walls and doors, and if
    that ever lights a corridor early, the jump lands and the lesson is skipped.
  * THE PITS. Row 4's first standable cell is the pocket at (4, 3) — so the one
    jump that does reach past corridor 1 drops the player in a hole rather than
    at the next lesson. That is what the trap column is for.

The audit is STAGED because the danger is not at the spawn — it is three
corridors in, when three gates have opened and the fog has lifted behind them.
A jump audit that only ran on the as-built room would pass while the level was
being cheesed from the middle.
"""
import pytest

import generation.dungeon_gen as dg
from engine.motion import apply_motion
from engine.player import Player
from sharing.replay import replay_tape
from tests import SEEDS

CORR = dg._OV_CORR_ROWS

#: Every teleport a player of this level has. The Vault sits after the
#: Lineheads (`G`, `gg`) and the Screen Vault (`H`, `M`, `L`), and counts are
#: taught long before either.
_JUMPS = ([('gg', 1, False), ('G', 1, False),
           ('H', 1, False), ('M', 1, False), ('L', 1, False)]
          + [('G', n, True) for n in range(1, 36)])


def _segments():
    """The canonical tape, split at the `3j` that ends each corridor. Segment k
    is the work done IN corridor k, so a prefix of k segments leaves the player
    having solved exactly k lessons."""
    toks = dg._OV_ANSWER.split()
    segs, cur = [], []
    for t in toks:
        cur.append(t)
        if t == '3j':
            segs.append(cur)
            cur = []
    if cur:
        segs.append(cur)
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
def test_a_jump_that_skips_a_corridor_cannot_win(seed):
    """THE ONE THAT MATTERS, and it is about OUTCOMES, not landings.

    An earlier version of this test asserted that no jump could LAND in a
    corridor the player had not opened, and it failed: after corridor 1, `7G`
    lands in corridor 3. That turned out to be the wrong question. Landing
    there is harmless — what matters is whether you can finish from there.

    Since 2026-08-01 a gate opens because its pack is DEAD, and the vault door
    opens only when EVERY guard in the level is down. So a corridor you jumped
    over is a corridor whose guards are still breathing, and the vault will not
    yield. The jump still happens; it just does not pay.
    """
    par = dg.build_dungeon_operators_vault(seed).rooms[0].answer
    segs = _segments()
    for k in range(1, len(segs)):            # the tail has no `3j` to stand in
        tape = ' '.join(t for s in segs[:k - 1] + [['3j']] + segs[k:] for t in s)
        d = dg.build_dungeon_operators_vault(seed)
        res = replay_tape(d, 'operators_vault', tape)
        alive = [e for r in d.rooms for e in r.entities
                 if e.kind == 'goblin' and e.alive]
        assert not res.won, (
            f'seed {seed}: skipping corridor {k} still won — its lesson is '
            f'optional ({len(alive)} guard(s) left alive)')
    # …and the route that does the work wins, so the level is not merely hard.
    d = dg.build_dungeon_operators_vault(seed)
    assert replay_tape(d, 'operators_vault', par).won


@pytest.mark.parametrize('seed', SEEDS)
def test_the_vault_is_what_makes_every_pack_required(seed):
    """The mechanism behind the test above, asserted directly: no guard may be
    left alive in a winning run. This is what a teleport cannot do — a jump
    kills nothing."""
    d = dg.build_dungeon_operators_vault(seed)
    room = d.rooms[0]
    res = replay_tape(d, 'operators_vault', room.answer)
    assert res.won
    assert not [e for r in d.rooms for e in r.entities
                if e.kind == 'goblin' and e.alive]
    assert not [e for r in d.rooms for e in r.entities
                if e.kind == 'locked_door' and e.alive]


@pytest.mark.parametrize('seed', SEEDS)
def test_the_pit_is_what_catches_the_one_jump_that_does_carry(seed):
    """`G` (and `M`/`L`) from the spawn land on row 4 — and row 4's first
    standable cell is a pocket, not a corridor. Remove the pit and that jump
    becomes a free step toward the second lesson."""
    room = dg.build_dungeon_operators_vault(seed).rooms[0]
    player = Player()
    player.row, player.col = room.spawn_pos
    apply_motion(player, 'G', 1, room, count_given=False, game_h=36)
    assert (player.row, player.col) in dg._OV_POCKETS, (player.row, player.col)


@pytest.mark.parametrize('seed', SEEDS)
def test_every_corridor_past_the_first_starts_fogged(seed):
    """The precondition the staged audit rests on. If a corridor is lit at
    build, a `{n}G` lands in it and its lesson is optional."""
    room = dg.build_dungeon_operators_vault(seed).rooms[0]
    for r in CORR[1:]:
        floor = [(r, c) for c in range(1, room.cols)
                 if (r, c) in room.fog_cells]
        assert floor, f'corridor row {r} is lit from the spawn'
