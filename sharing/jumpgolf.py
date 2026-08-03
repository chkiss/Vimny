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
  COLLAPSE    a run of adjacent TRAVEL tokens → one jump.  `0 3j` → `G`.
              The run may be as long as the tape has; see MAX_COLLAPSE. What
              it may NOT do is span an edit: `0 x 3j` is not collapsible to
              `G x`, because that does not shorten the travel — it REORDERS the
              cut relative to it, which is a different route rather than a
              cheaper spelling of this one, and whether it works depends on
              what `x` was standing on. Multi-edit routes are the beam's job
              (see `beam`/`slack`), not the collapse pass's.
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
#:
#: The first version listed only the counted walks and the jumps themselves, and
#: that was the pattern's blind spot rather than its definition: a tape travels
#: with whatever crosses rows, and eighteen shipped tapes travel with something
#: this did not recognise. A motion no candidate is ever tried against is a
#: motion no beat can be found behind (widened 2026-08-03).
#:
#:   {n}j {n}k {n}+ {n}- {n}_   the counted walks
#:   {n}G gg G H M L            the jumps themselves
#:   0 ^                        line heads — `0 3j` collapsed to `G` in the Vault
#:   {n}{ {n}} {n}( {n})        paragraph and sentence, which cross rows
#:   n N * #                    search repeats and the word hunt, which teleport
#:   /… ?…                      a search, which lands anywhere in the buffer
#:   `x 'x                      a mark jump
#:
#: NOT included: w b e W B E ge gE, and `%`. Those stay within their line in this
#: engine (`%` is row-scoped and nesting-aware), so a LINE jump cannot stand in
#: for one — and offering candidates that can only ever lose costs a full replay
#: each to prove it.
TRAVEL = re.compile(
    r'^('
    r'\d*[jk+\-]|\d+G|gg|G|H|M|L|\d*_|0|\^'          # walks, jumps, line heads
    r'|\d*[{}()]'                                     # paragraph / sentence
    r'|\d*[nN*#]'                                     # search repeats, word hunt
    r'|[/?].*'                                        # a search
    r'|[`\'].'                                        # a mark jump
    r')$')

#: Longest run of adjacent travel tokens a single jump may replace.
#:
#: `None` means "as long as this tape's longest contiguous travel run", which is
#: the only honest value: a run longer than that does not exist, so the bound
#: costs nothing and can never be the reason a beat was missed. It was 4 —
#: a magic number that happened not to bite, because the only shipped tape with
#: a longer run is The Line Halls (6), which sits before any jump is taught and
#: is therefore never golfed at all. A limit that is not currently binding is
#: still a trap: the next level with a five-token walk and a jump in its
#: curriculum would have been silently under-searched, and nothing would have
#: said so (2026-08-03).
MAX_COLLAPSE = None


def longest_travel_run(toks) -> int:
    """The longest stretch of consecutive TRAVEL tokens in a tape."""
    run = best = 0
    for t in toks:
        run = run + 1 if TRAVEL.match(t) else 0
        best = max(best, run)
    return best

#: THE ACCEPTANCE RULE: a shorter route is a par fix only if THE LEVEL STILL
#: TEACHES ITS LESSON. A route that wins by skipping the thing the level exists
#: to teach is a cheese to close, not a number to lower — and the two are easy
#: to confuse, because both look like "the tape got cheaper".
#:
#: For most levels the lesson is a keystroke, so the check is textual: every
#: key in the curriculum's `commands` string must survive in the golfed tape.
#: `spellwrights_forge` is the case that motivated it — `M` there lands
#: somewhere that makes `&` unnecessary, and the level whose whole job is
#: `:s` / `&` / `:g` would have had its par lowered to bless a route that never
#: presses `&`.
#:
#: Some lessons are STATE, not keystrokes, and no reading of the tape can see
#: them. `_VERIFY` is for those: a predicate on the finished room, checked after
#: the replay (the loop mutates the dungeon we hand it, so the room we kept a
#: reference to is the played one).
_LESSON_KEYS = {
    # slug -> the keystrokes that ARE the lesson, if `commands` needs help
    'spellwrights_forge': ('&', ':s', ':g'),
    'wet_ink':            ('gi',),
    # The Shelving Room advertises `:m :t :> :<` and writes them with ranges and
    # counts fused in — `:6m3`, `:7t7`, `:8>` — so the advertised form is not a
    # substring of its own tape and the rule had nothing to hold it to. The bare
    # ex-command letters are; a stray `m` elsewhere in a tape would weaken this,
    # which is the price of a check that reads text rather than intent.
    'shelving_room':      ('m', 't', '>', '<'),
}

#: Levels with NO keystroke lesson, named so the absence is a decision.
#: A level that reaches the acceptance rule with an empty key set accepts any
#: cheaper route at all — which is fine when there is genuinely nothing to keep,
#: and silent rot when there is. Being on this list is the difference.
NO_LESSON_KEYS = {
    'gauntlet': 'the closing gauntlet teaches nothing new — it is a revision of '
                'everything, so no one key is the lesson to keep',
}

#: slug -> what must be TRUE of the finished room, beyond the tape's text.
#:
#: `wet_ink`: par must assume a player who does NOT already recognise the
#: saying. The plaque's second, third and fourth quarters are veiled until the
#: brazier beneath each one burns, so a route that never carries fire is a
#: route only someone who knew the words could walk. The fire being SKIPPABLE
#: is fine — that is the level rewarding recognition — but it cannot be what
#: par is measured against, or par would be the cost of already knowing.
_VERIFY = {
    'wet_ink': lambda room: not room.veiled_cells,
}


def lesson_keys(slug: str) -> tuple:
    """The keystrokes that must survive in a golfed tape for it to count."""
    from content.levels import LEVELS
    if slug in _LESSON_KEYS:
        return _LESSON_KEYS[slug]
    entry = next((l for l in LEVELS if l['slug'] == slug), {})
    # `commands` is the overworld's keystroke string — '>{m} <{m} =' — so the
    # placeholders come out and what is left is what the player actually types.
    raw = entry.get('commands', '')
    for junk in ('{m}', '{n}', '{char}', '///'):
        raw = raw.replace(junk, ' ')
    return tuple(k for k in raw.split() if k)


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
    #: Which build this was golfed against — a level whose layout varies by seed
    #: has a different route per seed, so a result without one is ambiguous.
    seed: int = 0
    tape: str = ''
    steps: list = field(default_factory=list)
    #: Jumps this level has TAUGHT. Empty is the ordinary state of the first ten
    #: levels, not a failure — and it must not be reported as one. The curriculum
    #: introduces G/gg at position 10 and H/M/L at 11, so eight shipped levels
    #: have no jump to golf with and are silently, correctly, unimprovable.
    taught: tuple = ()
    #: The keystrokes this level exists to teach — see _LESSON_KEYS.
    lesson: tuple = ()
    #: How many MEASURED, genuinely cheaper winning routes were refused for
    #: dropping one of them. A nonzero count is not noise: a shorter way exists
    #: that skips the lesson, i.e. a cheese to close even though par is right.
    skipped_lesson: int = 0
    #: Those routes, as (tape, spend) — a refusal is only actionable if you can
    #: see the route it refers to.
    refused: list = field(default_factory=list)
    #: How many distinct tapes were measured, and whether the search stopped
    #: because it ran out of tapes or ran out of budget. An exhausted search is
    #: a "no beat found" that has NOT looked everywhere, and saying so is the
    #: difference between a result and a reassurance.
    evaluated: int = 0
    exhausted: bool = False

    @property
    def beats_par(self) -> bool:
        return (self.par is not None and self.best is not None
                and self.best < self.par)


def _spend_at(slug, builder, toks, known, height, verify=None, seed=0):
    """Replay at ONE terminal height. None if the tape does not win, or wins
    without leaving the room in the state the lesson requires."""
    dungeon = builder(seed)
    with mock.patch.object(blessed.Terminal, 'height',
                           property(lambda self, _h=height: _h)):
        res = replay_tape(dungeon, slug, ' '.join(toks), known=known)
    if not res.won:
        return None
    # The loop MUTATES the dungeon it is handed, so this is the played room.
    if verify is not None and not verify(dungeon.rooms[0]):
        return None
    return res.spent


def _spend_everywhere(slug, builder, toks, known, heights, verify=None, seed=0):
    """The cost of a tape, but only if it wins at EVERY height and costs the
    same at each. A route whose price depends on the window is not a route this
    tool will recommend: par has to mean one number.

    The cheap height is tried first as a filter — most candidates die there,
    and each replay is a full run of the game loop.
    """
    first = _spend_at(slug, builder, toks, known, heights[0], verify, seed)
    if first is None:
        return None
    for h in heights[1:]:
        if _spend_at(slug, builder, toks, known, h, verify, seed) != first:
            return None
    return first


#: Search shape. beam=1 / slack=0 is greedy hill-climbing — fast, and blind to
#: any win that needs two edits neither of which pays alone.
BEAM, SLACK, MAX_EVALS = 1, 0, 4000
#: What `--deep` uses. Four tapes alive, detours of up to one key admitted.
DEEP_BEAM, DEEP_SLACK = 4, 1


def layout_fingerprint(slug: str, seed: int) -> tuple:
    """What a golf result actually depends on: the tape, the grid, and the text.

    Most levels are seed-INVARIANT — the seed picks vocabulary at most, and many
    do not consult it at all — so golfing all five of the repo's seeds would
    replay the same search five times over. This is what lets the sweep cover
    every distinct layout instead of every seed, which is the same coverage for
    a fraction of the cost.

    Note that a level whose seed only swaps WORDS still fingerprints as
    different, because the tape carries those words: `/vault<CR>` is not
    `/cellar<CR>`, and a route's cost can turn on a word's length.
    """
    import generation.dungeon_gen as dg
    room = getattr(dg, f'build_dungeon_{slug}')(seed).room
    grid = tuple(tuple(c.value if hasattr(c, 'value') else c for c in row)
                 for row in room.cells)
    runs = tuple(sorted((ru.row, ru.col, ''.join(ru.symbols))
                        for ru in room.char_runs))
    return (room.answer, room.par, grid, runs)


def distinct_seeds(slug: str, seeds) -> list:
    """The subset of `seeds` that give this level genuinely different layouts."""
    out, seen = [], set()
    for s in seeds:
        fp = layout_fingerprint(slug, s)
        if fp not in seen:
            seen.add(fp)
            out.append(s)
    return out


def golf(slug: str, *, seed: int = 0, heights=HEIGHTS, jumps=JUMPS,
         max_collapse=MAX_COLLAPSE, strip=False, beam=BEAM, slack=SLACK,
         max_evals=MAX_EVALS, log=None) -> Result:
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
    room  = builder(seed).room
    known = known_commands(slug)
    # TOKEN GATING, at the point of proposal. The level has to have taught it.
    cands = tuple(j for j in jumps if j in known)
    out   = Result(slug=slug, par=room.par, canonical=None, best=None,
                   taught=cands, seed=seed)
    if not room.answer:
        return out

    verify = _VERIFY.get(slug)
    # Only the lesson keys THE SHIPPED TAPE ACTUALLY PRESSES. A level's
    # `commands` string is what the overworld advertises, and it can be wider
    # than its own answer: The Stair Rail advertises `+ - _` and its tape uses
    # only `+` and `-`, so demanding `_` would reject every route for dropping a
    # key the level never demonstrates. The rule is "still teaches its lesson",
    # and the canonical tape is the definition of what it teaches.
    keys = tuple(k for k in lesson_keys(slug) if k in room.answer)
    out.lesson = keys

    def _teaches_still(trial):
        """Does this tape still press the keys the level exists to teach?"""
        flat = ' '.join(trial)
        return all(k in flat for k in keys)

    toks = room.answer.split(' ')
    best = _spend_everywhere(slug, builder, toks, known, heights, verify, seed)
    out.canonical = out.best = best
    if best is None:                       # the shipped tape is height-sensitive
        return out                         # or does not win — not this tool's job
    out.tape = ' '.join(toks)
    if not cands:
        return out                 # nothing taught to golf WITH — see Result.taught

    memo = {' '.join(toks): best}

    def _measure(trial):
        """Cost of a candidate tape, cached. The cache is what makes a beam
        affordable: different search paths reach the same tape constantly, and
        each measurement is a full replay at every height."""
        key = ' '.join(trial)
        if key not in memo:
            memo[key] = _spend_everywhere(slug, builder, trial, known,
                                          heights, verify, seed)
        return memo[key]

    def _successors(state):
        """Every one-edit neighbour of a tape: substitute, collapse, delete."""
        for i, tok in enumerate(state):
            if not TRAVEL.match(tok):
                continue
            for c in cands:
                if c != tok:
                    yield state[:i] + [c] + state[i + 1:], 'sub', i, tok, c
        # Bound by the tape, not by a constant: runs longer than this state's
        # longest travel stretch do not exist, so raising the ceiling to it adds
        # only REAL candidates and never a wasted replay.
        limit = max_collapse if max_collapse is not None else longest_travel_run(state)
        for n in range(2, limit + 1):
            for i in range(len(state) - n + 1):
                run = state[i:i + n]
                if not all(TRAVEL.match(t) for t in run):
                    continue
                for c in cands:
                    yield (state[:i] + [c] + state[i + n:], 'collapse', i,
                           ' '.join(run), c)
        for i, tok in enumerate(state):
            if strip or TRAVEL.match(tok):
                # an EDIT being droppable is a different question — see --strip
                yield state[:i] + state[i + 1:], 'delete', i, tok, ''

    # ── the search ──────────────────────────────────────────────────────────
    #
    # Greedy hill-climbing (beam=1, slack=0) is the default and reproduces what
    # this tool has always done. It has one blind spot, and it is not a small
    # one: it takes the FIRST improvement it finds and never looks at a tape
    # that is not immediately cheaper, so a win that needs two edits — where
    # neither edit pays on its own — is invisible to it. `0 3j` -> `G` was only
    # ever caught because the first edit happened to leave the second key dead.
    #
    # `beam` keeps the K cheapest tapes alive instead of one; `slack` admits
    # tapes up to K keys DEARER than the best so far, which is what lets a
    # two-edit win be assembled through a step that pays nothing. slack=0 still
    # admits ties, i.e. plateau moves, which is the cheap half of the same idea.
    # `max_evals` bounds the whole thing: this is a search over tapes, and the
    # measurement is a full replay, so it needs a ceiling rather than a promise.
    best_toks = list(toks)
    frontier  = [(best, list(toks))]
    seen      = {' '.join(toks)}
    parent    = {}                       # tape -> (parent tape, Step)

    while frontier and len(memo) < max_evals:
        nxt = []
        for _cost, state in frontier:
            for trial, kind, at, was, now in _successors(state):
                if len(memo) >= max_evals:
                    break
                key = ' '.join(trial)
                if key in seen:
                    continue
                seen.add(key)
                got = _measure(trial)
                if got is None:
                    continue             # does not win, or is height-sensitive
                if not _teaches_still(trial):
                    if got < best:
                        # A REAL cheaper route that skips the lesson: a cheese
                        # to close, not a par to lower. Counted, never walked.
                        out.skipped_lesson += 1
                        out.refused.append((key, got))
                    continue
                parent[key] = (' '.join(state),
                               Step(kind=kind, at=at, was=was, now=now, spent=got))
                if got < best:
                    best, best_toks = got, list(trial)
                    if log:
                        log(parent[key][1])
                # Admit ties and, with slack, small detours — that is the whole
                # point of not being greedy.
                if got <= best + slack:
                    nxt.append((got, list(trial)))
        nxt.sort(key=lambda p: p[0])
        frontier = nxt[:beam]

    out.evaluated = len(memo)
    out.exhausted = len(memo) >= max_evals
    toks = best_toks
    # Walk the parent chain back so `steps` describes how the winner was built,
    # not the order the search happened to visit things in.
    chain, cur = [], ' '.join(best_toks)
    while cur in parent:
        prev, step = parent[cur]
        chain.append(step)
        cur = prev
    out.steps = list(reversed(chain))

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
