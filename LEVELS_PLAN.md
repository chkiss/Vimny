# Vimny — Level Curriculum Plan

> Canonical curriculum source: `content/levels.py` (`LEVELS` + `known_commands()`).
> SPEC.md no longer holds a curriculum: its stale 20-level draft (former §9–§10) was removed
> in the 2026-05 prune, leaving SPEC.md as design vision / UI only. This document and
> `content/levels.py` are the curriculum source of truth.

This plan was produced in two phases:
1. **Audit** — the current curriculum stress-tested against four design principles.
2. **Revision** — a clean-renumbered curriculum that fixes the audit findings, fills
   missing Vim mechanics, and re-anchors bosses at act boundaries.

---

## Design principles (the rubric)

1. **Scope** — a level teaches **1–3 new mechanics**, no more. Trivial direction/flavor
   variants of one idea count as one (e.g. `f`/`F` = one "find" idea).
2. **Rational linkage** — mechanics taught together form **one coherent family**
   (`gg`+`G` ✓; `gg`+`}` ✗).
3. **Forceability** — the level can be designed so the budget puzzle **forces** the new
   command using existing game primitives, with **no/minimal new game mechanics**.
4. **Boss placement** — bosses sit at **meaningful act boundaries**, are well-spaced, and
   are numbered `x.1`.

Existing forcing primitives: walls/corridors, doors, character runs (word/WORD targets),
void runes (lethal), water, chests/keys, fog-of-war, **keystroke budget** (`par × 1.4`),
enemies (goblins chase; wardens+shields in bosses), visual mode.

---

# Part 1 — Audit of the current curriculum

## 1.1 Master issue table

| # | Current level | Commands | Issue | Principle | Severity |
|---|---|---|---|---|---|
| 14 | Inscription Halls | `i a I A` | Introduces Insert **mode** + 4 entry points at once | Scope | High |
| 15 | Sculpting Chambers | `o O s S` | `o/O` (insert-entry) bundled with unrelated `s/S` (substitute) | Linkage/Scope | High |
| 36 | Bracket Enclosure | `i( a( i[ a[ i{ a{` | 6 variants in one level | Scope | High |
| 5 | Goblin Gauntlet | `; ,` | Orphaned from their parent `f F t T` (L4) | Linkage | High |
| 2 | Counting Crypts | `[count]` + `x` | `x` unrelated to count prefix | Linkage | Med-High |
| 1 | Line Halls | `^ $ 0` + `:w :q :q!` | Two families (motions + command-mode) | Linkage/Scope | Med |
| 10/13 | Runic Archives | `} { ) (` | `) (` has **no defined dungeon metaphor**; two families | Linkage | Med |
| 39 | Paragraph Enclosure | `is as ip ap` | Sentence + paragraph = two families | Linkage | Low |
| 29 | Case Chambers | `~` | Single trivial command — under-scoped | Scope | Med |
| 30 | Echo Vault | `.` | Single command, isolated from what it repeats | Scope/Linkage | Med |
| 19–27 | (operator block) | `dw…`, `yw…`, `cw…` | Over-leveled combinatorics: op + already-known motion | Scope | Med |
| 18 | Undo Sanctum | `u Ctrl-R` | **Cannot be budget-forced** (corrects mistakes, never the cheap path) | Forceability | High |
| 30 | Echo Vault | `.` | Map forceable, but validator must model "last change" | Forceability | High |
| 32 | Join Corridor | `J gJ` | No dungeon analogue without dynamic row-merge mechanic | Forceability | High |
| 33/34 | Indent | `>> <<`, `>{m}…` | No analogue without "shiftable cluster/bridge" mechanic | Forceability | High |
| 15 | Sculpting | `o O` | Indistinguishable from `i/a` by budget without "expandable floor" | Forceability | High |
| 28 | Overwrite | `r R` | Budget margin vs `s`/`x+i` erased by the 1.4× buffer | Forceability | Med |
| 10 | Screen Vault | `L` | Demonstrated but not strictly forced (fix: room height) | Forceability | Low |
| — | bosses 6–13 | — | **No boss across 8 levels** of extended motion | Boss placement | High |
| — | end of curriculum | — | **No finale boss** after the text-object capstone | Boss placement | High |
| 151 | Warden Unbound | — | Caps a heterogeneous 10-level act (6–15) — too broad | Boss placement | Med |

## 1.2 Missing standard Vim mechanics (absent from `levels.py`)

| Mechanic | Forceability | Notes |
|---|---|---|
| Search `/ ? n N` | Hard → achievable | Needs a "hidden exit / fog-of-knowledge" target so search is the cheap locator |
| Marks `m ' \`` | Needs new mechanic | Requires a multi-visit ("revisit point A") layout to beat absolute jumps |
| Substitute `:s///` | Achievable | Use the planned mana economy; `:s/x/y/g` beats N manual changes |
| Macros + registers `q @ "` | Needs validator work | Map design is easy; Dijkstra must model recorded-macro state |
| Command-mode `:e :set` | Contextual | Taught by the overworld-is-a-filesystem reveal, not a budget puzzle |

## 1.3 Systemic findings

- **Operator+motion combinatorics are over-leveled.** The grammar "any operator ∘ any
  motion" should be taught **once**, then *practiced within* levels — not given a fresh
  dungeon per (operator, motion) pair (L19/20/22/25/26/27).
- **Mode introductions are mis-sized.** Insert mode (the game's core build/spell mode) is
  crammed into one 4-command level; visual mode gets a clean single-command level. Flip the
  emphasis: thin command set, rich context, for mode intros.
- **`known_commands()` is partially blind.** `J gJ`, `>> <<`, `g~ gU gu`, `r R`, and **all
  text objects** are never registered, so the gate/validation system can't see them.
- **Bosses cluster late.** Acts I and IV are well-capped; the long motion act (6–13) and the
  entire back half (text objects) have no milestone.

---

# Part 2 — Proposed revised curriculum (clean renumber)

Acts are coherent skill phases; each ends with an `x.1` Warden boss immune to commands not
yet taught, with phases that each demand a different command from the act.

> **Numbering note (read before trusting the ids below).** Act I–II match the shipped
> curriculum. **Act III onward keeps this proposal's tentative numbering and act-grouping**
> (it lists the nav power-tools as Act III and puts visual mode in Act IV). The **authoritative
> ids, keys, and grouping live in Part 7 + `content/levels.py`** — where the standalone Goblin
> Gauntlet ships as **L5** and visual mode (`v`) ships as **L14**, leading the nav act. Do not
> read the Act III–VII ids below as final.

### Act I — Navigation Foundations
| # | Name | Teaches | Notes / changes |
|---|---|---|---|
| 0 | The First Cave | `h j k l` (+ `x` interact, `:wq` exit) | `x` moves here as the basic interact key |
| 1 | The Line Halls | `^ $ 0` | command-mode `:w :q :q!` introduced via the exit ritual, not as "motions" |
| 2 | The Counting Crypts | `[count]` | `x` removed (now L0) |
| 3 | The Rune Halls | `w b e` | — |
| 4 | The Character Cataracts | `f F t T` | — |
| 5 | The Goblin Gauntlet | `; , p` | — |
| **5.1** | **The Warden's Keep** (BOSS) | caps Act I | phases: hjkl → count → wbe → fFtT → ;,p |

### Act II — Extended & Structural Motion
| # | Name | Teaches | Notes / changes |
|---|---|---|---|
| 6 | The WORD Forge | `W B E` | — |
| 7 | The Backward Vaults | `ge gE` | — |
| 8 | The Lineheads | `G gg` | — |
| 9 | The Screen Vault | `H M L` | fix `L` forcing via room height |
| 10 | The Bracket Vaults | `%` | bracket/pair matching |
| 12 | The Runic Archives | `} {` | paragraph jumps; void barriers force `}` |
| 13 | The Sentence Corridor | `) (` | **define sentence metaphor** (corridor segments); split from Runic Archives |
| **13.1** | **The Warden Surveyor** (BOSS) | caps Act II | one phase per structural family — all 7: W/B/E, ge/gE, G/gg, H/M/L, %, }/{, )/( |

### Act III — Navigation Power Tools  *(mostly NEW mechanics)*
| # | Name | Teaches | Notes |
|---|---|---|---|
| 10 | The Mirror Temple | `%` | bracket/pair matching |
| 11 | The Seekers' Labyrinth | `/ ? n N` *(NEW)* | hidden-target search; needs "fog-of-knowledge" exit |
| 12 | The Waypoint Sanctum | `m ' \`` *(NEW)* | marks; needs multi-visit ("return to A") layout |
| 13 | The Archivist's Library | `:e :set` *(NEW)* | command-mode + the overworld-is-a-filesystem reveal |
| **13.1** | **The Warden Pathfinder** (BOSS) *(NEW)* | caps navigation mastery | — |

### Act IV — Visual Mode & The Operator Grammar
| # | Name | Teaches | Notes / changes |
|---|---|---|---|
| 14 | The Sight Sanctum | `v` (+ `V`?) | visual select; bridges into operators |
| 15 | The Operator's Vault | `d c` (+ `x`=`dl`, `s`=`cl`) | teach `d`/`c` **with motions immediately**; absorbs old `cw/ce/cb`, `ct/cf…`, `dt/df…` as practice |
| 16 | The Whole-Line Annex | `dd cc` `D` `S` | operator-doubling idiom + `D`(=`d$`), `S`(=`cc`); **`s S` move here** from old L15 |
| 17 | The Quartermaster | `y yy` `p P` | yank+paste together (merge old L23+L24), with `yw ye y$` as practice |
| 18 | The Undo Sanctum | `u Ctrl-R` | **demonstration level** (budget relaxed) — see Decision D1 |
| 19 | The Echo Vault | `.` (+ revisit `r R`) | dot-repeat taught on a repeatable change; needs validator "last-change" — Decision D2 |
| **19.1** | **The Warden Manifold** (BOSS) | caps operator grammar | phase per operator∘motion |

### Act V — Insert-Mode Construction
| # | Name | Teaches | Notes / changes |
|---|---|---|---|
| 20 | The Inscription Halls | `i a` | **Insert mode introduced alone**, simplest entries |
| 21 | The Sculpting Chambers | `I A` `o O` | line-edge + open-line entries; **`o O` rejoin the insert family** (needs "expandable floor" — Decision D3) |
| 22 | The Overwrite Halls | `r R` | replace char + Replace mode (Decision D4 on budget margin) |
| 23 | The Case Chambers | `~` `g~ gU gu` | **merge** old L29 `~` with case operators |
| 24 | The Stonemason's Hall | `J gJ` `>> <<` `>{m} <{m} =` | join + indent; needs "seam"/"shiftable bridge" mechanics (Decision D3) |
| **24.1** | **The Warden Scrivener** (BOSS) | caps construction/editing | — |

### Act VI — Text Objects (capstone)
| # | Name | Teaches | Notes / changes |
|---|---|---|---|
| 25 | The Word Enclosure | `iw aw` | text-object concept |
| 26 | The Bracket Enclosure | `i( a(` | **split**: parens only |
| 27 | The Brace & Square Enclosure | `i[ a[ i{ a{` | rest of brackets (Decision: split of old L36) |
| 28 | The Quote Enclosure | `i" a" i' a'` | — |
| 29 | The Tag Enclosure | `it at` | — |
| 30 | The Sentence & Paragraph Enclosure | `is as ip ap` | (or split into two) |
| **30.1** | **The Grandmaster's Sanctum** (FINAL BOSS) *(NEW)* | full grammar finale | `ci"` defuse, `da(` clear, `dip` sweep, etc. |

### Act VII — Mastery *(optional, NEW)*
| # | Name | Teaches | Notes |
|---|---|---|---|
| 31 | The Spellwright's Forge | `:s/{}/{}/` *(NEW)* | substitution spells via mana |
| 32 | The Hall of Echoes | `q @ "` registers/macros *(NEW)* | record/replay; needs macro-aware validator |
| **32.1** | **The Warden Eternal** (FINAL BOSS) *(NEW)* | true finale | record a macro to survive multi-phase combat |

> Bonus rooms: **The Reliquary** (review) and per-act scroll vaults remain, slotted as `x.x`
> side rooms; they don't gate progression.

**Result:** ~33 teaching levels + 7 bosses across 6–7 acts, every level ≤3 linked mechanics,
every act boss-capped, all standard Vim mechanics covered.

---

# Part 3 — Resolved design decisions

Engine reality check (from reading `engine/insert.py`, `operator.py`): `o/O` already insert a
real FLOOR row; `>>/<<` already shift runes horizontally; `s/S`, `r/R`, `d c y p`, case ops
all mutate runes. **`J/gJ` is unimplemented; marks have no engine support; search & macros
have partial engine primitives.** So most "needs a new mechanic" worries dissolve.

- **D1 — `u` / `Ctrl-R`.** ✅ **`Ctrl-R` (redo) becomes a discoverable scroll reward**, not a
  lesson level. **`u` (undo)** stays a light "budget-return" utility taught in a relaxed-budget
  demo moment — not a forced puzzle.
- **D2 — Dot `.`.** ✅ Force on the map (N identical changes); **extend the par-solver to model
  "last change."** No new game primitive.
- **D3 — Back-half primitives.** ✅ `o/O` forced via the existing floor-row insert
  ("extend the floor to reach the exit"). `>>/<<` forced via a **rune-alignment trigger**
  (gate opens when a rune reaches column X; `>>` is the cheap aligner) — no new floor
  primitive. **`J/gJ` IS implemented as a new engine op**: `J` appends the floor of the row
  below onto the end of the current row, carving a corridor into a previously-sealed room;
  forced via a "join to open the passage" puzzle.
- **D4 — `r R`.** ✅ Force by **tightening this level's budget multiplier and counting `Esc`**
  as a keystroke.
- **D5 — `) (` sentence metaphor.** Proposal: a "sentence" = a punctuation-delimited run
  within a corridor; `)` / `(` jump between such runs. (Confirm during blueprinting.)
- **D6 — Act VII (`:s`, macros).** ✅ **Included.** `:s` via the mana economy; macros need a
  **macro-aware par-solver**. Curriculum runs through the macro finale.

**Per-command forcing plan: APPROVED.**

---

# Part 4 — Code-sync checklist (consequence of clean renumber)

Renumbering `content/levels.py` IDs/keys desyncs the rest of the codebase. This phase
updates `levels.py` (+ `known_commands()`); the following must follow on a branch before the
game runs correctly again:

- [ ] `main.py` `_build_dungeon()` dispatch — remap `level == N → build_dungeon_N`.
- [ ] Rename `build_dungeon_N` generators in `generation/dungeon_gen.py` to new IDs.
- [ ] Rename `tests/test_level_N.py` + update their imports/IDs.
- [ ] `test_par_all_levels.py` level→builder mapping.
- [ ] `unlocks_after` chains and any `commands_level` overrides.
- [ ] Boss `x.1` keys/ids for the **new** bosses (9.1, 13.1, 30.1, 32.1).
- [ ] Save/progress migration (old saves reference old IDs) — add a remap or reset note.
- [x] Rewrite or delete SPEC.md §9–§10. *(Done 2026-05: SPEC pruned to vision/UI; curriculum/command/boss sections removed.)*
- [ ] Register the new commands in `known_commands()` (`J gJ`, `>> <<`, `g~ gU gu`, `r R`,
      text objects, search, marks, `:s`, macros).

> Done on a branch so `main` stays runnable; `main.py` dispatch + generators are explicitly
> deferred per the agreed scope ("doc + update `levels.py`; generators later").

---

# Part 5 — Stress-test findings (systemic) + engine prerequisites

The blueprint stress-test (per-act review files: `blueprints/act_N_review.md`) found pervasive
forceability defects. Root causes are systemic:

- **S1 — Prefer infinite-cost forcing over budget-margin forcing.** Most fails were
  "command-avoiding route fits within the ×1.4 budget." Where possible make the alternative
  *impossible* (walls/void/water = infinite cost), not merely more expensive.
- **S2 — Tighten budgets per level.** Where margin-forcing is unavoidable, set the multiplier so
  the next-best route STRICTLY exceeds budget. Don't default to ×1.4; use the minimum needed and
  document it.
- **S3 — Par must be the TRUE full min-keystroke solution** entry→exit, including all navigation
  and Esc. Designers undercounted (omitted exit nav); every par needs recompute.
- **S4 — Block earlier-act commands.** Ensure prior commands (`$ 0` count etc.) can't trivialize
  a later level; add terrain so the newly-taught command is still required.
- **S5 — Required splits:** Stonemason (`>> <<` | `>{m} <{m} =`), Runic Archives (`} {` | `) (`),
  Sentence & Paragraph (`is as` | `ip ap`).

## Engine prerequisites surfaced (for the later code phase)
- `D` and `d$` have identical cost → can't budget-force `D` (needs cost model or design change).
- `@a` is 2 keystrokes, not 3 → recheck all `N@a` macro forcing.
- dot-repeat does NOT chain with `dw` (cursor resets to start); use inclusive `de` for chains.
- Unimplemented: `it`/`at` (text_object.py returns None), `%`, marks (`m '` backtick), search
  state (`last_search`, `n`/`N`/`?`), mana economy (`:s`), wave-timer, macro-aware par-solver,
  boss per-phase immunity fields on `Entity`, and the new `J`/`gJ` row-carve op.
- Bosses that violated one-command-per-phase (Manifold `yy`+`p`; Scrivener `J`+`gJ`) → split phases.

> Iteration: each act was returned to its design agent with its review + rules S1–S5 for a
> consolidated revision pass, then re-verified.

---

# Part 6 — Post-revision: open challenges for decision

After the revision round (terrain-∞ forcing), `blueprints/act_*.md` are sound at the blueprint
layer for nearly all levels. Remaining items: (6.1) design tensions needing a call, (6.2) one
cross-cutting model decision, (6.3) an engine backlog for the code phase (no decision now),
(6.4) renumbering impact.

## 6.1 Design tensions (need a decision)
- **T1 — Razor-thin budgets (×1.03–×1.10):** `;,` (Act I find), marks (Act III), `di(` (Act VI
  brackets), `di"` (Act VI quotes). In each, the *companion* command (`f`, mark-set, `a(`, `a"`)
  is terrain-∞ forced; only the inner/repeat partner leans on a 1-keystroke margin. Options:
  (a) accept thin margins (needs an exact, deterministic per-seed par solver; one stray key
  fails the player); (b) inflate content to widen the gap (risks non-convergence + bloat);
  (c) accept the partner as "taught alongside, strongly incentivized," with the S1 companion
  carrying the mandatory lesson. *Recommend (c).*
- **T2 — Joint-only forcing:** `H M L` (Act II) and `r R` (Act V) can't force each member
  individually under any fixed multiplier — only avoiding the whole family blows budget.
  Options: accept family-level forcing, or add per-room "screen contexts" (new primitive).
  *Recommend accept family-level.*
- **T3 — `D` vs `d$`:** identical engine cost, so `D` is unforceable. *Recommend* fixing the
  cost model (`D` = 1 physical key, Vim-faithful) in the code phase; teach `D` as a shorthand
  demo until then.
- **T4 — `0` at L1:** introduced at L1, first *forced* at L2 (the void-wall bypass).
  *Recommend accept* the introduce-then-force pattern.

## 6.2 Cross-cutting model decision
- **M1 — Jump-motion semantics (load-bearing).** Forcing for `ge/gE`, `G/gg`, `%`, `) (`,
  search and marks depends on these being **buffer-position jumps that move the player avatar
  and may cross wall/void terrain** (NOT terrain pathfinding). Consistent with "the cursor is
  the avatar." Many Act II/III levels collapse without this. *Assumed YES unless you object.*
- **M2 — Par-solver scope.** Correct budgets need the solver to model `$ 0` + count, `de`-chain
  for dot, mark-jumps, search-teleport, and macro record/replay. The macro-aware solver is a
  real build. *Recommend:* extend the Dijkstra solver for motions/operators; **hand-author and
  lock par** for the marks/macro/boss levels.

## 6.3 Engine backlog (code phase — no decision needed now)
Motions as buffer jumps: `%`, search (`/ ? n N`, `last_search`), marks (`m '` backtick),
`ge/gE`+`G/gg` wall-crossing. New ops: `J/gJ` row-carve; mana economy + `:s`; `:e`/`:set` +
room-stack `:q`-return; `it/at` (`text_object.py` returns None). Cost/model fixes: `D`=1 key;
`@a`=2 keys (re-derive `N@a`); dot chains via `de`. Boss infra: `Entity.immune_to`/`phase`;
visual-source tagging; yank/paste-as-damage; wave-timer (normal-mode-tick); multi-phase state
machine. Hazards/markers: poison-rune or `blocked_commands`; `wall_rune` delimiter kind;
bomb-timer; `x`-on-dead-entity reflector. Par-solver: model `$ 0` count + the above.

## 6.4 Renumbering impact
The three S5 splits add **3 teaching levels** (Runic Archives→`}{` + `)(`; Stonemason→indent +
indent-motion; Sentence&Paragraph→sentence + paragraph). Bosses shift. Apply the Part 4
clean-renumber cascade when updating `content/levels.py`.

## 6.5 Resolutions (decided)
- **M1 — DECIDED: jump-motions move the player avatar across terrain** (buffer-position jumps).
- **M2 — par-solver: extend the Dijkstra solver** to model `$ 0`+count and `de`-chaining; for
  levels it can't model (marks, macros, bosses) hand-author & lock par, and **surface any
  per-level solver gap as a code comment on that level flagged for the user**.
- **T1/T2 — RESOLVED via a max-effort strict-forcing round** (no placeholders needed):
  `; ,` repeated-void targets (only `;` advances); marks 6-bend maze; `di( / di"` keystone-on-
  delimiter (terrain-∞); `H M L` three sub-room screens (strict ×1.11 — **needs engine support:
  `H/M/L` must reference the current sub-room's passable row range**); `r R` void-isolated runs
  (strict ×1.15). `T3` (`D`=`d$` cost) and `T4` (`0` introduced@1, forced@2) accepted per recs.

---

# Part 7 — FINAL curriculum (mirrors `content/levels.py`)

Identity is the **slug** (immutable). The leftmost column is the human-facing
**display** number — cosmetic only; the historical gap (no level 11; the Runic
Archives is 12) is preserved. Bosses and the Reliquary render as `x.1`.
Curriculum order is the order of `LEVELS`. Blueprints: `blueprints/act_*.md`.

> **This table is generated** from `content/levels.py` by
> `python3 content/_gen_curriculum_table.py` — do not hand-edit between the
> markers. After renumbering (edit `display` / reorder `LEVELS`), rerun it. The
> renumbering procedure is Part 8.

<!-- BEGIN GENERATED CURRICULUM TABLE -->
| # | slug | Name | commands | type |
|---|------|------|----------|------|
| 0 | `first_cave` | The First Cave | `h j k l u :w :q :q!` |  |
| 1 | `line_halls` | The Line Halls | `^ $ 0` |  |
| 1.1 | `reliquary` | The Reliquary | `"` | reliquary |
| 2 | `counting_crypts` | The Counting Crypts | `[count] prefix` |  |
| 3 | `rune_halls` | The Rune Halls | `w b e` |  |
| 4 | `character_cataracts` | The Character Cataracts | `f F t T` |  |
| 5 | `goblin_gauntlet` | The Goblin Gauntlet | `; , p` |  |
| 5.1 | `wardens_keep` | The Warden's Keep | — | boss |
| 6 | `word_forge` | The WORD Forge | `W B E` |  |
| 7 | `backward_vaults` | The Backward Vaults | `ge gE` |  |
| 8 | `lineheads` | The Lineheads | `G gg` |  |
| 9 | `screen_vault` | The Screen Vault | `H M L` |  |
| 10 | `bracket_vaults` | The Bracket Vaults | `%` |  |
| 12 | `runic_archives` | The Runic Archives | `} {` |  |
| 13 | `sentence_corridor` | The Sentence Corridor | `) (` |  |
| 13.1 | `warden_surveyor` | The Warden Surveyor | — | boss |
| 14 | `sight_sanctum` | The Sight Sanctum | `v` |  |
| 15 | `seekers_labyrinth` | The Seekers' Labyrinth | `/ ? n N` |  |
| 16 | `waypoint_sanctum` | The Waypoint Sanctum | `m ' `` |  |
| 17 | `archivists_library` | The Archivist's Library | `:e :set` |  |
| 17.1 | `warden_pathfinder` | The Warden Pathfinder | — | boss |
| 18 | `operators_vault` | The Operator's Vault | `d c` |  |
| 19 | `whole_line_annex` | The Whole-Line Annex | `dd cc D S` |  |
| 20 | `quartermaster` | The Quartermaster | `y yy P` |  |
| 21 | `undo_sanctum` | The Undo Sanctum | — |  |
| 22 | `echo_vault` | The Echo Vault | `.` |  |
| 22.1 | `warden_manifold` | The Warden Manifold | — | boss |
| 23 | `inscription_halls` | The Inscription Halls | `i a` |  |
| 24 | `sculpting_chambers` | The Sculpting Chambers | `I A o O` |  |
| 25 | `overwrite_halls` | The Overwrite Halls | `r R` |  |
| 26 | `case_chambers` | The Case Chambers | `~ g~ gU gu` |  |
| 27 | `joiners_gate` | The Joiner's Gate | `J gJ` |  |
| 28 | `alignment_halls` | The Alignment Halls | `>> <<` |  |
| 29 | `indentation_sanctum` | The Indentation Sanctum | `>{m} <{m} =` |  |
| 29.1 | `warden_scrivener` | The Warden Scrivener | — | boss |
| 30 | `word_enclosure` | The Word Enclosure | `iw aw` |  |
| 31 | `bracket_enclosure` | The Bracket Enclosure | `i( a(` |  |
| 32 | `brace_square_enclosure` | The Brace & Square Enclosure | `i[ a[ i{ a{` |  |
| 33 | `quote_enclosure` | The Quote Enclosure | `i" a" i' a'` |  |
| 34 | `tag_enclosure` | The Tag Enclosure | `it at` |  |
| 35 | `sentence_enclosure` | The Sentence Enclosure | `is as` |  |
| 36 | `paragraph_enclosure` | The Paragraph Enclosure | `ip ap` |  |
| 36.1 | `grandmasters_sanctum` | The Grandmaster's Sanctum | — | boss |
| 37 | `spellwrights_forge` | The Spellwright's Forge | `:s///` |  |
| 38 | `hall_of_echoes` | The Hall of Echoes | `q @ "` |  |
| 38.1 | `warden_eternal` | The Warden Eternal | — | boss |
| 99 | `dummy` | Dummy Dungeon | `d x s y p yy P` |  |
<!-- END GENERATED CURRICULUM TABLE -->

---

# Part 8 — Renumbering & the slug model (for future edits)

`content/levels.py` is the single source of truth. Every builder, test, par
solver, save record, scroll, and wizard poem is keyed by the immutable **slug**
— never by a level number. Renumbering is therefore cheap and safe.

## To renumber or reorder the curriculum
1. Edit `LEVELS` in `content/levels.py`: reorder entries and/or change `display`
   strings. **Never change a `slug`** — that is the identity.
2. `known_commands`, unlock gating (`unlocks_after_slug`), and the hint-bar tiers
   all derive from `LEVELS` order automatically — nothing else to touch.
3. Run `python3 content/_gen_curriculum_table.py` to refresh the Part 7 table.
4. `python3 -m pytest -q` — green confirms the curriculum is consistent.

## Keyed by slug (renumber-immune)
- Builders: `build_dungeon_<slug>` (`generation/dungeon_gen.py`).
- Tests: `tests/test_<slug>.py`; par solvers `_par_<slug>`; constants `_<SLUG>_*`.
- Saves: `progress` is keyed by slug (`save/save_manager.py`).
- Scrolls: `_SCROLL_DROPS` (main.py) + `SCROLL_CATALOG.level_slug` (content/scrolls.py).
- Wizard poems: `introduces_slug` (`art/_gen_wizard_wisdom.py`).
- Per-level special-casing in main.py compares `level == '<slug>'`.

## The only places numbers still live
- `display` (one cosmetic string per level) — the single thing a renumber edits.
- `LEGACY_ID_SLUG` (`content/levels.py`) — a **frozen** historical id→slug map,
  used solely to migrate pre-refactor int-keyed save files. Never edit it: it is
  a permanent record of the numbering in use when those saves were written.

## Adding a new level
Add a `LEVELS` entry (unique slug, `display`, `name`, `key`, `teaches`); write
`build_dungeon_<slug>` + `tests/test_<slug>.py`; if it precedes a lesson, add a
slug-keyed poem in `art/_gen_wizard_wisdom.py` and regenerate. A brand-new slug
needs **no** `LEGACY_ID_SLUG` entry (only levels that ever shipped with an int id
appear there).
