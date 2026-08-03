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

"""Does a LINE JUMP beat the travel a level's own tape is written with?

PAR IS THE OPTIMUM — the cheapest route that exists — so a one-key jump that
reaches where a two-key walk was going is not a nicety, it is a recorded par
that is simply wrong. This module is how that question gets asked by
MEASUREMENT rather than by reasoning, which is the only way it has ever been
answered correctly: `operators_vault` shipped 62 because someone checked one
drop and reasoned about the other three, and the route that exists was 55.

Three passes, applied to a level's own tape until nothing more improves:

  SUBSTITUTE  one token → one jump.  `4G` → `G`.
  COLLAPSE    a run of 2..4 adjacent tokens → one jump.  `0 3j` → `G`.
              This pass is why the module exists. A substitute-only sweep
              found the `operators_vault` drops by accident — swapping the
              `0` left the `3j` dead, and the deletion pass swept it up — and
              a collapse that does not decompose that way is invisible to it.
              A tool whose blind spots are shaped like the bug it is looking
              for gives clean bills of health it has not earned.
  DELETE      drop a DEAD TRAVEL token.  A saving LARGER than the keystroke
              difference means the substitution did not shorten the route, it
              turned a following motion into a blocked no-op — free, and doing
              nothing. A tape carrying dead keys is not an answer: the karaoke
              would teach a player to press a key that does not matter.

The deletion pass is restricted to TRAVEL tokens on purpose, and the restriction
is the difference between two questions that look alike and are not:

  "does a jump beat this walk?"        → a par bug. Fix the number.
  "is this level's own work optional?" → a design question. Fix the level, or
                                         decide the level is fine as it is.

Unrestricted, the pass answers the second while claiming to answer the first:
it golfed `wet_ink` from 39 to 26 by deleting the entire fire ritual, which is
a true statement about that level and nothing whatever to do with `M` vs `2+`.
`--strip` asks the second question deliberately; the default does not.

Two rules the passes are held to:

  TOKEN GATING IS ABSOLUTE. A candidate the level has not taught is not a
  route — it is a key the game refuses. Candidates are filtered against
  `known_commands(slug)` with no exceptions, and `replay_tape` is handed the
  same set, so the gate is enforced twice: once when proposing and once when
  playing.

  A BEAT MUST HOLD AT EVERY HEIGHT. `H`/`M`/`L` are viewport-relative whenever
  the room is taller than the game area (Vim-faithful), so a saving found at
  one window size may not exist at another. An improvement is accepted only if
  it wins AND spends less at every height tested — which is what keeps par from
  becoming a function of the player's terminal. (`G`/`gg` read the buffer and
  are stable by construction; they are usually the better answer for that
  reason alone.)
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from unittest import mock

import blessed

from sharing.replay import replay_tape

#: The jumps worth trying. `G`/`gg` first: buffer-relative, so a tape written
#: with one means the same thing in every window.
JUMPS = ('G', 'gg', 'H', 'M', 'L')

#: Terminal heights a real player might have. The game area is `height - 8`,
#: and H/M/L go viewport-relative once the room is taller than that, so the
#: spread has to straddle the rooms (8..36 rows) rather than sample one end.
HEIGHTS = (25, 30, 41, 50, 60)

#: Tokens that MOVE THE CURSOR TO ANOTHER ROW — the only ones a line jump
#: rivals. Everything else in a tape is an edit, and a jump cannot stand in for
#: an edit.
TRAVEL = re.compile(r'^(\d*[jk+\-]|\d+G|gg|G|H|M|L|\d+_|0|\^)$')

#: Longest run of adjacent tokens a single jump may replace.
MAX_COLLAPSE = 4


@dataclass
class Step:
    """One accepted improvement, for the report."""
    kind: str                      # 'sub' | 'collapse' | 'delete'
    at: int
    was: str
    now: str
    spent: int


@dataclass
class Result:
    slug: str
    par: int | None
    canonical: int | None          # what the shipped tape actually spends
    best: int | None
    tape: str = ''
    steps: list = field(default_factory=list)
    #: Jumps this level has TAUGHT. Empty is the ordinary state of the first ten
    #: levels, not a failure — and it must not be reported as one. The curriculum
    #: introduces G/gg at position 10 and H/M/L at 11, so eight shipped levels
    #: have no jump to golf with and are silently, correctly, unimprovable.
    taught: tuple = ()

    @property
    def beats_par(self) -> bool:
        return (self.par is not None and self.best is not None
                and self.best < self.par)


def _spend_at(slug, builder, toks, known, height):
    """Replay at ONE terminal height. None if the tape does not win."""
    with mock.patch.object(blessed.Terminal, 'height',
                           property(lambda self, _h=height: _h)):
        res = replay_tape(builder(0), slug, ' '.join(toks), known=known)
    return res.spent if res.won else None


def _spend_everywhere(slug, builder, toks, known, heights):
    """The cost of a tape, but only if it wins at EVERY height and costs the
    same at each. A route whose price depends on the window is not a route this
    tool will recommend: par has to mean one number.

    The cheap height is tried first as a filter — most candidates die there,
    and each replay is a full run of the game loop.
    """
    first = _spend_at(slug, builder, toks, known, heights[0])
    if first is None:
        return None
    for h in heights[1:]:
        if _spend_at(slug, builder, toks, known, h) != first:
            return None
    return first


def golf(slug: str, *, heights=HEIGHTS, jumps=JUMPS, max_collapse=MAX_COLLAPSE,
         strip=False, log=None) -> Result:
    """Golf one shipped level's tape down to a fixed point.

    `strip=True` lets the deletion pass drop ANY token, not just dead travel —
    which stops asking "does a jump beat this walk?" and starts asking "is this
    level's own work optional?". Useful, and a different question; see above.
    """
    import generation.dungeon_gen as dg
    from content.levels import known_commands

    builder = getattr(dg, f'build_dungeon_{slug}', None)
    if builder is None:
        raise ValueError(f'no such level: {slug}')
    room  = builder(0).room
    known = known_commands(slug)
    # TOKEN GATING, at the point of proposal. The level has to have taught it.
    cands = tuple(j for j in jumps if j in known)
    out   = Result(slug=slug, par=room.par, canonical=None, best=None,
                   taught=cands)
    if not room.answer:
        return out

    toks = room.answer.split(' ')
    best = _spend_everywhere(slug, builder, toks, known, heights)
    out.canonical = out.best = best
    if best is None:                       # the shipped tape is height-sensitive
        return out                         # or does not win — not this tool's job
    out.tape = ' '.join(toks)
    if not cands:
        return out                 # nothing taught to golf WITH — see Result.taught

    def _try(trial, kind, at, was, now):
        nonlocal toks, best
        got = _spend_everywhere(slug, builder, trial, known, heights)
        # `<=` for deletions: a token whose removal costs nothing was doing
        # nothing, and dropping it is an improvement even at equal price.
        better = got is not None and (got < best or (kind == 'delete' and got <= best))
        if not better:
            return False
        step = Step(kind=kind, at=at, was=was, now=now, spent=got)
        out.steps.append(step)
        if log:
            log(step)
        toks, best = trial, got
        return True

    changed = True
    while changed:
        changed = False
        # ── 1. substitute: one travel token → one jump ──────────────────────
        for i, tok in enumerate(toks):
            if not TRAVEL.match(tok):
                continue
            for c in cands:
                if c == tok:
                    continue
                if _try(toks[:i] + [c] + toks[i + 1:], 'sub', i, tok, c):
                    changed = True
                    break
            if changed:
                break
        if changed:
            continue
        # ── 2. collapse: a RUN of travel tokens → one jump ──────────────────
        for n in range(2, max_collapse + 1):
            for i in range(len(toks) - n + 1):
                run = toks[i:i + n]
                if not all(TRAVEL.match(t) for t in run):
                    continue
                for c in cands:
                    if _try(toks[:i] + [c] + toks[i + n:], 'collapse', i,
                            ' '.join(run), c):
                        changed = True
                        break
                if changed:
                    break
            if changed:
                break
        if changed:
            continue
        # ── 3. delete: was that key doing anything at all? ──────────────────
        for i, tok in enumerate(toks):
            if not strip and not TRAVEL.match(tok):
                continue        # an EDIT being droppable is a different question
            if _try(toks[:i] + toks[i + 1:], 'delete', i, tok, ''):
                changed = True
                break

    out.best = best
    out.tape = ' '.join(toks)
    return out


def golfable_levels() -> list:
    """Every shipped level this tool can ask the question of."""
    import generation.dungeon_gen as dg
    from content.levels import LEVELS
    from sharing.cli import _NO_SINGLE_TAPE

    out = []
    for lv in LEVELS:
        slug = lv['slug']
        if slug in _NO_SINGLE_TAPE:
            continue
        builder = getattr(dg, f'build_dungeon_{slug}', None)
        if builder is None:
            continue
        room = builder(0).room
        if room.answer and room.par is not None:
            out.append(slug)
    return out
