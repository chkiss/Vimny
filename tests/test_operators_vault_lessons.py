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
from tests import SEEDS
from tests.test_operators_vault import _drive

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


@pytest.mark.xfail(strict=True, reason=(
    'KNOWN CHEESE, found 2026-08-01 and PRE-EXISTING (not from the fog rebuild '
    '— measured against the old geometry, which leaked one MORE jump). After '
    "corridor 1, `7G` lands in corridor 3 and corridor 2's `db` lesson is never "
    'taught; `4G` lands at corridor 2 col 8, which is west of the shaft mouth '
    '`db` exists to reach, for one key less. The per-key `_reveal_from` in the '
    'tick lights the corridor AHEAD of the one the player walked into, and a '
    'lit corridor is a legal landing. Un-xfail when the level defends it.'))
@pytest.mark.parametrize('seed', SEEDS)
def test_no_jump_at_any_stage_skips_the_next_lesson(monkeypatch, seed):
    """THE STAGED AUDIT — the one that matters, because the danger is not at the
    spawn. It is two corridors in, when a gate has opened and the reveal has run.

    After solving k corridors the tape leaves the player in corridor k+1, so
    corridors 1..k+1 are legitimately reachable. A jump that lands in corridor
    k+2 or beyond has skipped a lesson outright.
    """
    segs = _segments()
    for k in range(1, len(segs)):
        d = dg.build_dungeon_operators_vault(seed)
        prefix = [ch for seg in segs[:k] for tok in seg for ch in tok]
        _state, cap = _drive(monkeypatch, d, prefix)
        room, player = d.rooms[0], cap['player']
        allowed = k + 1                      # the corridor they now stand in
        for (r, c) in _landings(room, player):
            if r not in CORR:
                continue                     # a pit or a dead row is no shortcut
            reached = CORR.index(r) + 1
            assert reached <= allowed, (
                f'seed {seed}: after {k} corridor(s), a jump from '
                f'{(player.row, player.col)} landed in corridor {reached} '
                f'at {(r, c)} — lesson {allowed + 1} was never taught')


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
