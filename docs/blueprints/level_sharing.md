# Community levels — authoring, validation, sharing

Status: **built** (2026-07-25), except alternates (§6). The design below stands as
written; what shipped is noted per section and summarised in §7. Author-facing
documentation is `docs/AUTHORING.md`; the code is the `vimny/sharing/` package.

This is the plan for letting players write dungeons and pass them to each other.
It is a system feature, not a level.

Two end goals, from the original ask:

- **(a) Alternates** — a community level stands in for one of the shipped levels.
- **(b) A bonus wing** — downloadable levels played as extra content.

(b) is achievable on the design below. (a) is achievable but carries a curriculum
risk covered at the end, and should stay opt-in.

---

## 0. The constraint that decides everything: a level is data, never code

A shipped level is a Python function (`build_dungeon_<slug>`). A community level
**must not be**. The moment "download a level" means "run a stranger's Python,"
Vimny becomes a malware vector, and no amount of review fixes that — the format
is the security boundary.

So the format is **purely declarative**: geometry, content directives, entity
attributes, and a solution tape. It is parsed into a `Room`, never executed. No
expressions, no lambdas, no `eval`, no import hooks. Anything an author cannot
express declaratively is a gap in the schema to be filled deliberately — never an
escape hatch.

This is the one decision that cannot be revisited cheaply later, so it comes first.

---

## 1. Par — the hard problem, and the author-tape answer

Vimny's spine is **PAR IS THE OPTIMUM**: par is the cheapest route that exists.
Shipped levels get it from a hand-written Dijkstra solver per level, over that
level's exact command set. A community author cannot write one, and a *general*
solver over the full command set (operators, registers, substitute, text objects,
macros) is not a feature — it is a research project.

**The answer: the author supplies the karaoke tape, and the engine replays it.**

The machinery already exists. `room.answer` is a literal keystroke string, already
matched keystroke-by-keystroke during play, and `budget.spend()` already prices
every key. Replaying a tape headlessly therefore yields a keystroke count, and
that count is the level's par. Better still, **the replay is also the solvability
proof** — a level whose tape does not reach the exit is rejected before it ships.
One artifact does both jobs.

### The honest caveat

A replayed tape gives the cost of **the author's route**. That is an upper bound,
not an optimum. A community par can therefore be *loose* in a way no shipped par
is, and calling both "par" would quietly weaken the game's central promise.

Three ways to handle it, in order of preference:

1. **Label it.** Community levels score against **author's par**, named as such in
   the UI. Stars still work; the player knows the bar was set by a person rather
   than proved by a solver. Honest, cheap, and no engineering risk.
2. **Lower-bound check.** Run the existing motion-only Dijkstra as a validator: if
   a pure-motion route is *cheaper* than the tape, the tape is definitely not
   optimal, and the author is told so at submission time. This cannot prove
   optimality (it ignores operators and registers) but it catches the common
   beginner error — an author who never learned the shortcut their own level
   should be teaching.
3. **Community golf** — see §1a. This is the real answer, and it applies to the
   shipped curriculum too.

Recommendation: ship **1 + 2**, and build §1a alongside them.

---

## 1a. Community golf, applied to the shipped levels

A submitted tape is **self-verifying**: replay it headlessly, and either it reaches
the exit for fewer keystrokes than the recorded par or it does not. No trust, no
reviewer judgement, no reputation system — the claim carries its own proof.

That property is worth far more on the **shipped** curriculum than on community
levels. Every shipped par is a claim that a hand-written Dijkstra solver found the
cheapest route over that level's command set, and the standing law is that par *is*
the optimum. Every such claim is falsifiable by exactly one artifact: a shorter
tape. So players submitting improved solutions are not a leaderboard feature — they
are a **distributed audit of the game's central invariant**, and one that scales
past what any solver review can cover. The cheese audit found par drift by hand on
a handful of levels; this finds it everywhere, continuously, for free.

Mechanically it is the same replayer as §1, pointed at a different target:

- Submission is a slug plus a tape.
- CI replays it against that level's deterministic build.
- If it completes under par, the finding is **confirmed automatically** — it is a
  bug in that level's solver, filed with a reproduction attached.
- Fixing it means correcting `_par_<slug>` and re-deriving
  `budget = ceil(par * 1.4)`, exactly as a hand-found cheese fix does today.

The one thing to get right is that a confirmed beat is a **solver bug report, not a
score**. Par is a property of the level; it changes because the old value was
wrong, not because someone played well. Presenting it as a leaderboard would invite
the opposite reading and, worse, create an incentive to sit on findings.

---

## 2. The format

One file per level, declarative, versioned. Sketch — field names to be settled at
implementation, structure is the point:

```
schema:        1
name:          "The Salt Stair"
author:        "someone"
seed:          1234                 # fills are deterministic from this
teaches:       ["W", "B", "E"]      # tokens this level introduces
requires:      ["w", "b", "0", "$"] # tokens assumed already known; the replay may
                                    # use nothing outside requires + teaches + always-on
no_horse:      false                # bar the companion (room.no_horse / _horse_blocked)
alternate:     null                 # or a shipped slug — see §6

geometry:
  rows: 20
  cols: 80
  cells: [ ... ]                    # run-length encoded rows of cell codes
  spawn: [r, c]
  exit:  [r, c]

fill:                               # declarative content — see §3
  - region:    [r1, c1, r2, c2]
    generator: vocab_mixed
    length:    [4, 6]
    spacing:   1

entities:
  - kind: goblin
    at:   [r, c]
    ai:   chase
    speed: 1
    hp:   2

vocabulary:                         # optional author-supplied pools — see §4
  words:    [...]
  proverbs: [...]

solution: "wwwdwbbP0G"              # the karaoke tape; par is derived from it
```

Everything the current editor drops on the floor has to be in here. Today
`_serialize_room` (`vimny/engine/editor.py:273`) captures cells, char_runs, entity
kind/row/col, spawn and exit — and nothing else. It loses `par`, `budget`,
`answer`, `teaches`, seed, fog, mist, and **every entity attribute**, so a saved
goblin returns stationary at hp=1 with no AI. Fixing that serialization is
prerequisite work for all of this.

---

## 3. Fill directives — "fill this floor with words"

The original question was how an author says *"this floor should be filled with
random glyphs from some vocabulary list"* rather than painting every cell. That is
what `fill` is for: a region plus a generator, resolved at **load time** against
the level's `seed`, so the result is deterministic — the same level renders
identically for every player, which the solution tape requires.

The sources already exist and are clean; they are simply trapped inside builders:

| Generator | Backing source |
|---|---|
| `vocab_plain`, `vocab_mixed` | `_load_vocab_tables()` (`vimny/generation/dungeon_gen.py:2502`) — dicts keyed by word length |
| `proverbs` | `vimny/content/proverbs.py` — `PLAIN` |
| `misquotes` | `vimny/content/proverbs.py` — `MISQUOTES`, `misquotes_by_cure_len()` |
| `custom` | the author's own `vocabulary` block (§4) |

The work is to lift these behind a small stable API — `words(kind, length, rng)` —
that both shipped builders and the loader call. Shipped levels should migrate onto
it too, so the authoring path is the same one the game itself uses rather than a
second-class imitation. A directive that resolves differently for author and
player is a broken level, so the loader must be the single implementation.

---

## 4. Author-supplied vocabulary

Authors need their own word lists — a level about French verbs cannot be built
from the shipped pool. Constraints:

- **Inline in the level file.** No external fetches, ever; a level that phones
  home is a tracking beacon.
- **Validated on load**: printable, no control characters, no combining marks, and
  width-1 per character. Vimny's whole model is one glyph per cell, so a CJK or
  emoji word silently corrupts every column position downstream.
- **Bounded**: a cap on list length and word length, so a level file cannot be a
  denial-of-service payload.
- Author words are **content, not code** — they render, and nothing else.

Anything shown on screen from an untrusted file is a moderation surface. Worth
saying plainly in whatever channel distributes these: a level file can contain
arbitrary text, and the game does not review it.

---

## 5. Validation — what a level must pass to be playable

The validator is the whole product. It runs on load, not just on submission, so a
hand-edited file cannot bypass it.

1. **Schema** — known version, all required fields, no unknown keys.
2. **Bounds** — rows/cols within limits; every coordinate in range; spawn and exit
   standable; entity count capped.
3. **Determinism** — building twice from the seed yields identical rooms.
4. **Solvability** — the tape replays headlessly and reaches the exit. Hard gate.
5. **Par** — derived from the replay; `budget == ceil(par * 1.4)`, computed, never
   author-set. Authors do not get to pick the budget.
6. **Command scope** — the replay uses no token outside `requires` + `teaches` +
   the always-on set (`u`, `:w`, `:q`, `:q!`). A level cannot secretly demand a
   command it neither taught nor declared. This is the same `action_allowed`
   gate the curriculum already runs on, pointed at an authored token set instead
   of `known_commands(slug)` — the replayer must enforce it, or an author can
   ship a level that is unsolvable for the player it targets.
   `no_horse` is declarative and needs no validation beyond being a boolean.
7. **Golf warning** — the motion-only Dijkstra lower bound (§1.2); a warning to the
   author, not a rejection.
8. **Content** — vocabulary passes §4.

Rejections must name the failing rule. An authoring tool whose error is "invalid
level" trains people to give up.

---

## 6. Alternates — a level offered in place of a shipped one (goal *a*)

If you'd like to propose alternate or improved layouts for levels, submit a level
labeled `alternate: <slug>`, and ensure the level teaches **exactly** that slug's
`teaches` set — no more and no less (the level must have no dependencies _not_
already taught in the curriculum as well). The validator enforces that
mechanically; see also "Think you can do a shipped level better?".

The bonus wing (goal *b*) does not have this requirement and submissions are
welcome for fun, playable levels that sit outside of the curriculum.

---

## 6a. Distribution — GitHub as the hub

GitHub is a good fit, for one reason above all the others: **CI can run the
validator.** Every submitted level is a pull request; a GitHub Actions workflow
runs §5 headlessly — schema, determinism, tape replay, par derivation, budget,
token scope, content limits — and the PR cannot merge until it passes. Nobody ever
has to trust a submission or playtest it to find out it is broken. The same
workflow serves §1a: a par-improvement submission is a tape, CI replays it, and a
confirmed beat opens a solver bug automatically.

The rest of what is needed comes free: accounts and identity, moderation and
blocking, review threads, revision history, and a takedown path for content the
project will not host.

**Voting** is the weakest part. The honest options are 👍 reactions on the PR or a
Discussions thread — crude, gameable, and no worse than what a hand-rolled system
would be at this scale. That is enough to sort a bonus wing by popularity, and it
is *not* enough to gate an alternate swap, which stays on the playtest label
(§6). Vote-gating it would make the curriculum a popularity contest.

**Two things GitHub should not be asked to do:**

- **Networking from inside the game.** v1 should ship with *no* network code: the
  player downloads a level file and drops it in `~/.Vimny/levels/`, and the game
  reads a directory. An in-game fetcher adds a privacy surface, an outage
  dependency, and a second trust boundary, to save one manual step. Combined with
  §0 — no code, no network — the security story stays short enough to state in
  the README.
- **Being the barrier to entry.** Requiring a GitHub account to *share* a level is
  reasonable; requiring one to *play* a shared level is not. Keep the played
  artifact a plain file that can travel by any means.

A separate `vimny-levels` repo, not the game repo: different review bar, different
moderation load, and it keeps the game's history clean.

---

## 7. Prerequisites, in order — and what shipped

**Built:** 2, 3, 4, 5, 6 and the tooling for 7. `vimny/sharing/replay.py` (the tape
replayer), `vimny/sharing/format.py` (the declarative format), `vimny/sharing/vocab.py`
(the shared `words()` API), `vimny/sharing/validate.py` (the eight rules),
`vimny/sharing/library.py` (`~/.Vimny/levels/`, no network code) and
`vimny/sharing/cli.py` (`python3 -m vimny.sharing {validate,golf,audit,export,list,install}`),
plus the `community/` wing in the overworld and
`.github/workflows/validate-levels.yml`.

**§1a paid for itself immediately.** The audit's first run found The
Spellwright's Forge claiming par 45 for a route its own canonical tape wins in
44 — reproducible on every seed. The old figure was hand-tallied and counted
neither the three command-line Enters nor their exemption from the budget, and
the level is excluded outright from `tests/test_answer_paths.py`, so nothing had
ever measured it. Exactly the argument this section makes: the claim was
falsifiable by one artifact, and no community was needed to falsify it.

**Not built:** step 8, alternates. The format and validator support it
(`alternate: <slug>`, enforced to teach exactly the target's lesson), but
nothing consumes it yet — by design, per §6. The `vimny-levels` repository does
not exist; its CI workflow does.

**One limit worth recording:** a tape containing an insert or change verb cannot
be replayed from the tape alone, because the notation omits `<Esc>` (a sequence
key the live tracker skips) and the following keys would be typed into the
buffer. Twenty-one shipped levels are in that position and are par-pinned by
their own driven tests; `sharing audit` PRINTS each one as skipped rather than
dropping it, so a level can never pass the audit invisibly. A community level
whose route needs an insert verb cannot currently be validated — the fix is a
tape notation for Esc, and it is the next thing to build here.

### The original order



1. Make custom layouts **playable at all**. Today the launcher hardcodes slug
   `first_cave`, forces edit mode on entry, and falls back to `Budget(20)` because
   there is no par (`main.py:8590-8598`). Nothing else can be tested until a
   layout can be played as itself.
2. Extend serialization to capture entity attributes, fog/mist, seed, teaches, and
   the tape (`vimny/engine/editor.py:273`).
3. Lift the word sources behind the shared `words()` API (§3) and migrate shipped
   builders onto it.
4. Build the headless tape replayer — the piece that yields par and solvability.
   **Highest-value single item.** It unlocks community par (§1), the validator
   (§5), and the shipped-curriculum audit (§1a) — and §1a is worth building
   against the existing levels *before* any sharing exists, since it can start
   finding real par bugs on day one with no community at all.
5. Write the validator (§5).
6. Import/export, the `~/.Vimny/levels/` directory, and the bonus-wing listing in
   netrw. No network code (§6a).
7. The `vimny-levels` repo and its CI workflow (§6a).
8. Only then: alternate swaps (§6), gated on the playtest label.

Steps 1–2 are also plain quality-of-life wins for the admin editor, so they pay
for themselves even if the sharing pipeline stalls.
