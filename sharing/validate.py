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

"""The validator — the whole product.

It runs **on load**, not only on submission, so a hand-edited file cannot walk
past it. A level that fails is not playable.

Every rejection names the rule it broke. An authoring tool whose only error is
"invalid level" teaches people to give up, and the author is the person best
placed to fix the problem if they are told what it is.
"""
from __future__ import annotations

import math
import unicodedata
from dataclasses import dataclass, field

from content.levels import LEVELS, known_commands
from engine.world import CellType
from sharing import format as F
from sharing.replay import replay_tape


@dataclass
class Report:
    errors:   list = field(default_factory=list)   # fatal — the level cannot ship
    warnings: list = field(default_factory=list)   # advisory — the author should know
    par:      int | None = None
    budget:   int | None = None

    @property
    def ok(self) -> bool:
        return not self.errors

    def fail(self, rule: str, msg: str) -> None:
        self.errors.append(f'[{rule}] {msg}')

    def warn(self, rule: str, msg: str) -> None:
        self.warnings.append(f'[{rule}] {msg}')


_SHIPPED_SLUGS = {lv['slug'] for lv in LEVELS}
_STANDABLE     = (CellType.FLOOR, CellType.CORRIDOR)


def validate(lvl: F.Level) -> Report:
    """Run every rule. Returns a Report; never raises for a bad level."""
    rep = Report()

    _check_bounds(lvl, rep)
    _check_vocabulary(lvl, rep)
    _check_declarations(lvl, rep)
    if not rep.ok:
        return rep                    # geometry is broken; building would only
                                      # produce a second, more confusing error

    dungeon = _try_build(lvl, rep)
    if dungeon is None:
        return rep

    _check_determinism(lvl, dungeon, rep)
    _check_standable(lvl, dungeon, rep)
    if not rep.ok:
        return rep

    _check_solvable_and_par(lvl, rep)
    if rep.ok:
        _check_golf(lvl, rep)
    return rep


# ── 2. Bounds ─────────────────────────────────────────────────────────────────

def _check_bounds(lvl: F.Level, rep: Report) -> None:
    if not 3 <= lvl.rows <= F.MAX_ROWS:
        rep.fail('bounds', f'geometry.rows must be 3..{F.MAX_ROWS}, got {lvl.rows}')
    if not 3 <= lvl.cols <= F.MAX_COLS:
        rep.fail('bounds', f'geometry.cols must be 3..{F.MAX_COLS}, got {lvl.cols}')
    if len(lvl.entities) > F.MAX_ENTITIES:
        rep.fail('bounds', f'at most {F.MAX_ENTITIES} entities, got {len(lvl.entities)}')
    if len(lvl.fills) > F.MAX_FILLS:
        rep.fail('bounds', f'at most {F.MAX_FILLS} fill directives, got {len(lvl.fills)}')
    if len(lvl.seals) > F.MAX_SEALS:
        rep.fail('bounds', f'at most {F.MAX_SEALS} seals, got {len(lvl.seals)}')
    if len(lvl.solution) > F.MAX_TAPE:
        rep.fail('bounds', f'solution tape longer than {F.MAX_TAPE} keystrokes')
    if not lvl.solution.strip():
        rep.fail('bounds', 'solution: required — it is what proves the level '
                           'is solvable and what sets its par')

    def _in_range(what, pos):
        r, c = pos
        if not (0 <= r < lvl.rows and 0 <= c < lvl.cols):
            rep.fail('bounds', f'{what} {list(pos)} is outside the {lvl.rows}x{lvl.cols} room')

    _in_range('geometry.spawn', lvl.spawn)
    _in_range('geometry.exit', lvl.exit)
    for i, e in enumerate(lvl.entities):
        at = e.get('at')
        if isinstance(at, (list, tuple)) and len(at) == 2:
            _in_range(f'entities[{i}].at', at)
        # `drops` is the only field in the format that CREATES an entity at
        # runtime — everything else describes something the file already listed
        # and the checks above already counted. So it is the only field where a
        # downloaded level could otherwise conjure something nobody validated:
        # `drops: warden` on a goblin hatches a boss out of thin air. Loot only.
        # Through `canonical_kind` first, so a renamed loot kind is not read as
        # a kind nobody has ever heard of — the parser accepts the old name and
        # the validator has to agree with it or the file is refused for a rename
        # its author never made.
        drop = str(e.get('drops', '') or '')
        if drop and F.canonical_kind(drop.partition(':')[0]) not in F.DROPPABLE:
            rep.fail('bounds', f'entities[{i}].drops: {drop!r} is not something a '
                               f'creature may leave behind; allowed kinds are '
                               f'{", ".join(sorted(F.DROPPABLE))}')
    for i, f in enumerate(lvl.fills):
        r1, c1, r2, c2 = f.region
        if r1 > r2 or c1 > c2:
            rep.fail('bounds', f'fill[{i}].region is inside out: {list(f.region)}')
        if f.pool not in F.vocab.POOLS:
            rep.fail('bounds', f'fill[{i}].pool: unknown pool {f.pool!r}')
        if f.pool == 'custom' and not lvl.vocabulary:
            rep.fail('bounds', f"fill[{i}] uses the 'custom' pool but the level "
                               f'declares no vocabulary')
        if f.length[0] < 1 or f.length[1] < f.length[0]:
            rep.fail('bounds', f'fill[{i}].length: {list(f.length)} is not a valid range')
    for i, s in enumerate(lvl.seals):
        r1, c1, r2, c2 = s.region
        if r1 > r2 or c1 > c2:
            rep.fail('bounds', f'seals[{i}].region is inside out: {list(s.region)}')
        _in_range(f'seals[{i}].region start', (r1, c1))
        _in_range(f'seals[{i}].region end', (r2, c2))
        for j, cell in enumerate(s.opens):
            _in_range(f'seals[{i}].opens[{j}]', cell)
            if min(r1, r2) <= cell[0] <= max(r1, r2) and \
               min(c1, c2) <= cell[1] <= max(c1, c2):
                # A door inside its own condition is a door that opens, becomes
                # walkable, gets written on, and re-shuts on whatever the player
                # wrote — a loop with no honest reading. Refuse it while the
                # author can still see which seal they meant.
                rep.fail('bounds', f'seals[{i}].opens[{j}] {list(cell)} lies inside '
                                   f"the seal's own region — a door cannot be part "
                                   f'of the text that opens it')


# ── 8. Content ────────────────────────────────────────────────────────────────

def _check_vocabulary(lvl: F.Level, rep: Report) -> None:
    """Author words are CONTENT, not code — they render and nothing else.

    Width is the load-bearing check. Vimny's whole model is one glyph per cell,
    so a CJK or emoji character silently corrupts every column position
    downstream of it: the level the author tested is not the level that renders.
    """
    if len(lvl.vocabulary) > F.MAX_VOCAB_WORDS:
        rep.fail('content', f'vocabulary: at most {F.MAX_VOCAB_WORDS} words, '
                            f'got {len(lvl.vocabulary)}')
    for w in lvl.vocabulary[:F.MAX_VOCAB_WORDS]:
        if not isinstance(w, str) or not w:
            rep.fail('content', f'vocabulary: {w!r} is not a non-empty string')
            continue
        if len(w) > F.MAX_WORD_LEN:
            rep.fail('content', f'vocabulary: {w!r} is longer than {F.MAX_WORD_LEN}')
        for ch in w:
            if unicodedata.category(ch) in ('Cc', 'Cf', 'Cs', 'Co', 'Cn'):
                rep.fail('content', f'vocabulary: {w!r} contains a control or '
                                    f'unassigned character')
                break
            if unicodedata.combining(ch):
                rep.fail('content', f'vocabulary: {w!r} contains a combining mark, '
                                    f'which does not occupy a cell of its own')
                break
            if unicodedata.east_asian_width(ch) in ('W', 'F'):
                rep.fail('content', f'vocabulary: {w!r} contains the double-width '
                                    f'character {ch!r}; Vimny is one glyph per cell')
                break


# ── 6. Command scope, and: does an alternate fit where it says it does? ───────

def _check_declarations(lvl: F.Level, rep: Report) -> None:
    if lvl.alternate is not None:
        if lvl.alternate not in _SHIPPED_SLUGS:
            rep.fail('alternate', f'{lvl.alternate!r} is not a shipped level slug')
        else:
            target = next(lv for lv in LEVELS if lv['slug'] == lvl.alternate)
            want   = set(target.get('teaches', []))
            got    = set(lvl.teaches)
            if want != got:
                # Exactly, in both directions. Teaching MORE leaves the player
                # ahead of the curriculum; teaching LESS leaves a later level
                # depending on a command they never met.
                rep.fail('alternate',
                         f'a level offered in place of {lvl.alternate!r} has to '
                         f'teach exactly {sorted(want)}, but this one teaches '
                         f'{sorted(got)}')
            # The other half of "same place in the curriculum": what the level
            # ASSUMES has to have been taught by the time a player gets here.
            # `known_commands` is cumulative and INCLUDES the target, so the set
            # a player actually arrives with is that minus the target's own
            # lesson.
            arrives_with = set(known_commands(lvl.alternate)) - want
            # A token in both requires and teaches is reported once, by the
            # `scope` rule below, with a clearer message than this one.
            missing = (set(lvl.requires) - arrives_with
                       - set(F.ALWAYS_ON) - set(lvl.teaches))
            if missing:
                rep.fail('alternate',
                         f'this level needs {sorted(missing)}, which a player '
                         f'reaching {lvl.alternate!r} has not been taught yet')
    overlap = set(lvl.requires) & set(lvl.teaches)
    if overlap:
        rep.fail('scope', f'token(s) {sorted(overlap)} are in both requires and '
                          f'teaches — a level cannot introduce what it assumes')


# ── 3. Determinism ────────────────────────────────────────────────────────────

def _try_build(lvl: F.Level, rep: Report):
    try:
        return F.build(lvl)
    except F.LevelFormatError as exc:
        rep.fail('geometry', str(exc))
    except Exception as exc:                       # noqa: BLE001 — author input
        rep.fail('geometry', f'could not build the room: {exc}')
    return None


def _check_determinism(lvl: F.Level, first, rep: Report) -> None:
    """Two builds of one file must be identical.

    The tape was recorded against one arrangement of words. If a fill resolved
    differently for the next player, their level is not the level the tape
    solves — so this is a correctness rule, not tidiness.
    """
    try:
        second = F.build(lvl)
    except Exception as exc:                       # noqa: BLE001
        rep.fail('determinism', f'the second build failed where the first did not: {exc}')
        return
    a, b = first.room, second.room
    if a.cells != b.cells:
        rep.fail('determinism', 'two builds produced different cell grids')
    if _runs_key(a) != _runs_key(b):
        rep.fail('determinism', 'two builds produced different text — a fill '
                                'directive is not seeded deterministically')
    if _ents_key(a) != _ents_key(b):
        rep.fail('determinism', 'two builds produced different entities')


def _runs_key(room):
    return sorted((ru.row, ru.col, ''.join(ru.symbols), ru.kind)
                  for ru in room.char_runs)


def _ents_key(room):
    return sorted((e.kind, e.row, e.col, e.tag, e.hp) for e in room.entities)


def _check_standable(lvl: F.Level, dungeon, rep: Report) -> None:
    room = dungeon.room
    sr, sc = room.spawn_pos
    if room.cells[sr][sc] not in _STANDABLE:
        rep.fail('bounds', f'geometry.spawn {list(room.spawn_pos)} is not a '
                           f'floor cell — the player would start inside stone')
    er, ec = room.exit_pos
    if room.cells[er][ec] not in _STANDABLE:
        # A SEALED exit is legitimate (a gate opened by solving the level), so
        # this is advice rather than a rejection — solvability is the real test.
        rep.warn('bounds', f'geometry.exit {list(room.exit_pos)} is not floor. '
                           f'That is fine for a sealed exit that a tick opens, '
                           f'but nothing else will reach it.')


# ── 4 + 5. Solvability and par ────────────────────────────────────────────────

def _check_solvable_and_par(lvl: F.Level, rep: Report) -> None:
    """Replay the tape. This is the hard gate, and it sets par.

    Par is DERIVED here and never read from the file, so an author cannot hand
    themselves a loose budget. `known` is the level's own declared command set,
    which is also what enforces rule 6: a tape reaching for a command the level
    neither requires nor teaches is refused by the same `action_allowed` gate
    the curriculum runs on, and the replay fails.
    """
    dungeon = F.build(lvl)                          # fresh: the loop mutates it
    result  = replay_tape(dungeon, 'community', lvl.solution, known=lvl.known)

    if result.error:
        rep.fail('solvable', result.error)
        return
    if not result.won:
        rep.fail('solvable',
                 'the solution tape replays without reaching the exit. Either the '
                 'route is wrong, or it uses a command this level neither lists in '
                 '`requires` nor `teaches` — a gated key is silently refused, and '
                 'everything after it lands on the wrong cell.')
        return

    rep.par    = result.spent
    rep.budget = math.ceil(result.spent * 1.4)
    if result.spent <= 0:
        rep.fail('par', 'the tape cost nothing — par must be at least 1')


# ── 7. Golf warning (advisory) ────────────────────────────────────────────────

def _check_golf(lvl: F.Level, rep: Report) -> None:
    """Motion-only lower bound: if plain movement beats the tape, the tape is
    definitely not optimal.

    This cannot prove optimality — it models no operator, register or text
    object — but it catches the common beginner error: an author who never
    learned the shortcut their own level is supposed to be teaching. A warning,
    never a rejection, because a deliberately scenic route is the author's call.
    """
    from generation.dungeon_gen import _dijkstra_par_count
    try:
        lower = _dijkstra_par_count(F.build(lvl).room)
    except Exception:                              # noqa: BLE001 — advisory only
        return
    if lower is not None and rep.par is not None and lower < rep.par:
        rep.warn('golf',
                 f'plain movement alone reaches the exit in {lower} keystrokes, '
                 f"but your tape spends {rep.par}. Par is the CHEAPEST route that "
                 f'exists, so this level would ship with a loose par — and a '
                 f'player who finds the shorter route gets two stars for ignoring '
                 f'the lesson. Consider tightening the route or the geometry.')
