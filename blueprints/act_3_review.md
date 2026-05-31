# Act III Blueprint — Adversarial Review

Reviewer posture: adversarial. Every claim must survive the worst seed, the worst
layout, and an independent arithmetic check.

---

## Level 10 — The Bracket Vaults

### 1. Scope

New mechanic introduced: `%` (1).
PASS — well within the ≤3 limit.

### 2. Linkage

Single idea: bracket-pair matching. No second idea smuggled in.
PASS.

### 3. Forceability

**Independent par recomputation.**

The designer's "optimal sequence" in the blueprint is:
  `3l % 6l % 6l 9l` → claimed 14 keystrokes.

Let me count this carefully:
- `3l` = 2 keystrokes (digit `3` + `l`)
- `%`  = 1
- `6l` = 2 (digit `6` + `l`)
- `%`  = 1
- `6l` = 2
- `9l` = 2 (this is supposed to cover `{` walk-through + door + exit step)

Running total: 2+1+2+1+2+2 = **10 keystrokes**, not 14.

But wait — the designer then says the separate step `l` to exit is also needed (step 6
in the narrative), and the "sequence" in step 5 says "8l = 2 keys (count prefix = 2
keystrokes)" and step 6 says "l to exit: 1 key". If all steps 1-6 are summed:

Step 1: `3l %` = 2+1 = 3
Step 2: `6l` = 2
Step 3: `%` = 1
Step 4: `6l` = 2
Step 5: `8l` = 2 (inside `{ }` passable, col 38→46 = 8 cells, but designer wrote `8l = 2 keys`)
Step 6: `l` = 1

Total: 3+2+1+2+2+1 = 11

Neither arithmetic gives 14. There is an internal inconsistency: the narrative steps sum
to ~11 and the compact sequence sums to ~10, but the par claim is 14.

**Defect:** Par is overclaimed at 14; independent count gives 10-11. Budget = ceil(14×1.4)
= 20, but correct budget = ceil(11×1.4) = ceil(15.4) = **16**. If the true par is 10-11,
a budget of 20 is generous and actually does NOT endanger the no-`%` path analysis
(walking is walled off), so the forcing argument survives the arithmetic error.

However, there is a secondary issue in the layout description itself: the "Optimal
keystrokes" section says the player starts at (6,1) and `[` is at col 4, so `3l` is
correct (cols 1→4). After `%`, player is at `]` col 15. Next `(` is at col 21, so `6l`
(cols 15→21) is correct. After `%`, player is at `)` col 32. Next `{` is at col 38, so
`6l` (cols 32→38) is correct. Then the passable interior of `{` ... `}` is cols 39-45,
the `}` is at col 46. From col 38 to col 46 = `8l` (2 keys). Door at col 47-48. Exit at
col 49. From col 46: `3l` to exit (2 keys). Grand total: 2+1+2+1+2+2+2 = **12**
(including the `3l` to reach exit from `}`).

The correct par is **~12 keystrokes**, budget = ceil(12×1.4) = ceil(16.8) = **17**.

The blueprint states budget=20. This is slightly inflated but not dangerous — the forced
path analysis (void in pairs 1 and 2, walls blocking detours) remains intact.

**Engine dependency:** `%` in `engine/motion.py` — flagged explicitly and correctly.

VERDICT: **CONDITIONAL PASS** — forceability logic is sound, but par is miscounted (12,
not 14). Budget of 20 is safe (wider margin than needed); recommend tightening to 17 to
maintain pressure. Design is sound IF `%` motion is implemented.

### 4. Boss

Not applicable at L10.
PASS.

---

## Level 15 — The Seekers' Labyrinth

### 1. Scope

New mechanics: `/pattern`, `?pattern`, `n`, `N`.

The design claims this is "2 new mechanics" (the search pair + the repeat pair). The
LEVELS_PLAN.md principle says 1-3 mechanics, and explicitly groups `/`, `?`, `n`, `N` as
one cluster in the curriculum table. The scope question raised in the brief is: is
`/ ? n N` one "search" family, or four separate mechanics at once?

Analysis: In Vim, `/` and `?` are direction variants of the same command (forward/backward
search). `n` and `N` are direction variants of "repeat search". This is exactly analogous
to `f`/`F` (one mechanic) and `;`/`,` (one mechanic repeat) — which Level 4 teaches
together as "one coherent family." The blueprint explicitly makes this parallel.

Counting as 2 mechanics (search-invoke + search-repeat) is defensible and matches the
curriculum rubric. Under the strictest reading (`/` ≠ `?` ≠ `n` ≠ `N` = 4 distinct
keystrokes), scope would be 4 and FAIL. But `/ ? n N` is a tighter family than
`f F t T ; ,` (6 keystrokes, taught together in L4 as one scope unit).

JUDGMENT: **BORDERLINE PASS** — the family argument holds by analogy to L4's precedent,
but the designer should explicitly state that `/`+`?` = 1 mechanic and `n`+`N` = 1
mechanic (the blueprint does state this in the self-check). However, the rubric says
"≤3 new mechanics" so even if all four are counted separately, 4 > 3 = FAIL under strict
reading. Recommend the designer defend counting `/`+`?` as 1 unit (they do) and
`n`+`N` as 1 unit (they do).

Decision: PASS under the design's stated grouping (2 mechanics), with the caveat that an
independent reviewer using "each keystroke = 1 mechanic" would call FAIL.

### 2. Linkage

`/`, `?`, `n`, `N` are Vim's search-navigation cluster. Coherent family.
PASS.

### 3. Forceability

**Independent par recomputation.**

Designer's claim: par = 33, budget = ceil(33×1.4) = 47, then relaxed to 50.

**Problem 1 — Seed variance and worst-case par.**

The designer gives a best-case analysis: SIGIL in worst-case alcove = top-right (Row1,
Col-D). Let me check the search cost for this case:
- `/SIGIL<Enter>` = 7 keystrokes (/, S, I, G, I, L, Enter)
- Travel from row 18 (bottom corridor) to top-right alcove: must traverse 3 wall rows
  with doors. Roughly row 18 → door at row 15 (3 steps up) → door at row 10 (5 steps up)
  → door at row 5 (5 steps up) → alcove interior (~3 steps) = ~16+ moves, plus horizontal
  travel to Col-D (~15 steps right). The designer estimates "~10" for this travel.
  16+15 = ~31 moves just to reach the SIGIL, before collecting it.

This is a **critical error**: the designer's "~10 moves to SIGIL" appears to be a severe
underestimate for worst-case (top-right alcove, 20×70 grid). Even a generous estimate:
from (18,2) to top-right alcove interior could be row 18→15→10→5→4 and col 2→65 =
~13 rows + ~63 cols = ~76 moves minimum in Manhattan distance, but the grid has walls and
doors forcing a constrained path. A realistic estimate for a 20-row, 70-col labyrinth
with 3 intermediate wall rows is 30-50 moves to reach the SIGIL in the worst alcove.

Then navigate from SIGIL to exit (18, 67): another 20-40 moves depending on alcove.

Realistic worst-case par WITH search: 7 (search) + 35 (to SIGIL) + 1 (collect) + 30
(to exit) ≈ **73 keystrokes**.

Budget at 1.4x = ceil(73×1.4) = ceil(102.2) = **103** — not 47.

**The ±5 range claim never appears in the blueprint.** The designer simply says "par ~33"
for "SIGIL in worst-case alcove" without showing the arithmetic. This par of 33 is
implausible for a 20×70 maze. Even if `/SIGIL` teleports the cursor (rather than making
the player *walk* to it), and the player still needs to physically navigate the player
character:
- The search command jumps the *cursor* to the SIGIL, but the *player entity* must still
  physically walk there. The blueprint conflates cursor-jump with player-movement.

**Defect — Critical:** The blueprint appears to confuse editor-cursor movement (where
`/SIGIL` warps the cursor instantly) with player-avatar movement in the dungeon (where the
player still has to physically navigate to the SIGIL location to pick it up). If search
only jumps the cursor (as in text Vim), the player must still walk — and the par/forcing
argument collapses entirely because the "cheap path" is just knowing where the SIGIL is
(cursor highlight) + walking, which is not dramatically cheaper than systematic search if
the labyrinth is large.

**Two possible design intents — and both have problems:**

**Interpretation A:** `/SIGIL` warps the *player avatar* to the SIGIL location (like a
teleport). Then:
- This requires a custom "search = teleport" engine behavior that is NOT standard Vim `/`.
- The blueprint does NOT flag this as an engine extension. It lists `find_next` returning
  `(row, col)` and storing in `player.last_search`, but it does NOT say the player entity
  physically teleports to that position.
- If this is the intent, it must be flagged as a major engine extension (not listed).

**Interpretation B:** `/SIGIL` only highlights/reveals the SIGIL's position (standard Vim
behavior — cursor jumps in the text buffer, but there is no "cursor" concept separate from
the player in this dungeon game). The player still walks there.
- Then the advantage of search is only informational (knowing the target position) vs.
  manual exploration. A smart player could still find the SIGIL by checking 1-2 alcoves
  (statistically 1/(12) to 6/12 chance in first 1-6 checks = expected ~5 manual checks).
- The par savings would be small and the budget gap between "search" and "manual
  exploration" would be narrow — possibly not enough to force search.

**Conclusion:** The forceability argument for `/SIGIL` fundamentally depends on an
unspecified engine behavior. The claimed par of 33 is arithmetically unsupportable for a
20×70 grid regardless of interpretation.

**Problem 2 — `n`/`N` forcing argument is circular.**

The blueprint says: "The budget is tight enough that `n`/`N` to step between ECHO clusters
costs fewer keys than counting-hjkl between them — forcing at least one `n` use for the
bonus keystone that opens a shortcut gate on the bottom corridor."

But:
- The shortcut gate is opened by a bonus keystone (optional content).
- If the shortcut gate is optional, `n`/`N` is not forced — it's only incentivized.
- The blueprint then says "The shortcut gate saves 6 keys on the exit run, so using `n`
  is cheaper." But 6 keys saved vs. 2 ECHO keystones requiring `n n` (and an initial `?`
  or `/ECHO` search command = ~7 keystrokes) means the net saving is tiny and depends
  on the shortcut gate distance being exactly 6 cells — which is unverified.

**Problem 3 — `?` backward search forcing argument.**

"After collecting SIGIL (which may be in a top alcove), the player is positioned above the
exit. The last ECHO keystone is in a bottom-left alcove. `?ECHO<Enter>` (backward search)
+ `n` reaches it more cheaply than navigating row-by-row back down."

But: if the player just needs to go DOWN (toward exit at row 18), navigating down with `j`
or count-`j` is straightforward. The claim that `?ECHO` is cheaper than `[count]j` in a
20-row grid is not demonstrated with arithmetic.

**Budget inconsistency:** Designer computes budget=47, then says "relaxed slightly to 50."
But no par-recomputation justifies 50 — it's just "variance." The correct approach is to
compute worst-case par and set budget = ceil(worst_par × 1.4).

VERDICT: **FAIL** — Par claim (33) is arithmetically unsupportable for a 20×70 grid.
The forcing argument depends on an unspecified engine behavior (does `/SIGIL` teleport the
player avatar?). The `?` and `n`/`N` forcing arguments are not demonstrated with
arithmetic for the worst seed. This level needs a redesign or a much smaller grid where
the par arithmetic is verifiable.

### 4. Boss

Not applicable at L15.

---

## Level 16 — The Waypoint Sanctum

### 1. Scope

New mechanics: `m{a-z}` (set mark), `'a`/`` `a `` (jump to mark). Count = 2.
PASS.

### 2. Linkage

`m` + `'`/`` ` `` = set-waypoint + jump-to-waypoint. One coherent family.
PASS.

### 3. Forceability

**Independent par recomputation.**

Designer claims: par-with-marks ≈ 42, par-without-marks ≈ 65, budget = ceil(42×1.4) = 59.
At budget 59, the no-mark path (65) exceeds budget.

Let me verify the layout and path independently.

Grid: 18 rows × 60 cols. Key positions from the blueprint:
- Entry: (16, 2) — ANTECHAMBER
- K1: CHAMBER-A, (3, 5)
- K2: CHAMBER-B, (9, 5)
- K3: CHAMBER-D, (9, 43)
- Exit: (3, 57) — EXIT ROOM

**Path without marks (Manhattan lower bound ignoring walls):**
ANTE(16,2) → HUB → UpperCorr → A(3,5): row diff = 13, col diff = 3 → ~16+ moves
A(3,5) → B(9,5): but the blueprint says the route goes back down through corridor.
  From A upper-left, must go: (3,5)→UpperCorr → LowerCorr → B(9,5): rows ~10, cols ~0 = ~10 moves
B(9,5) → D(9,43): col diff = 38 = ~38 moves (same row but must traverse through doors)
D(9,43) → UpperCorr → C → EXIT(3,57): row diff = 6, col diff = 14 = ~20 moves

Rough no-marks total: 16 + 10 + 38 + 20 = ~84 moves (just navigation, no mark overhead).
But this includes walls and doors adding detours. The designer says ~65 without marks.

**Path with marks:**
The designer claims marks save ~24 steps from corridor re-walks. Let me check:
- Without marks, from A(3,5) you must walk back to upper corridor, then DOWN to lower
  corridor, then to B. The upper→lower corridor traversal = ~14 rows = ~14 steps each way.
  With mark `mb` at upper corridor (say row 6, col 30): `` `b `` (2 keys) jumps directly
  to corridor junction vs. walking 10-14 steps. Savings per jump = ~10-12 steps.
- 3 mark-jumps used (designer says 2-3): 3×10 = 30 steps saved.
- Mark setting overhead: 2 marks × 2 keystrokes = 4 extra keystrokes.
- Net saving: 30 - 4 = 26 keystrokes. Consistent with the "~24 step" claim.

If no-marks path ≈ 65 and marks save ~26, marks path ≈ 39. Designer says 42 (a bit higher
due to door interactions). Plausible.

**Budget arithmetic:**
- Designer: budget = ceil(42 × 1.4) = ceil(58.8) = 59. ✓ (arithmetic is correct)
- Forcing: no-marks (65) > budget (59) → marks are required. ✓

**Critical adversarial check: is the no-marks lower bound of 65 actually achievable by a
clever player?**

From the layout, the corridor traversal is the key cost driver. Let me estimate more
carefully:

ANTE(16,2) → UpperCorr via HUB: HUB at rows 15-17, UpperCorr at rows 6-7.
  From (16,2) to upper corridor (row 6): ~10 rows up + navigating HUB doors = ~15 moves.
  Then left to A at col 5: already at col 2, so ~3 moves.
A(3,5) → collect K1 → return to UpperCorr: ~3 down to row 6 = 3 moves.
UpperCorr (6, 5) → LowerCorr (13, something): must go back through HUB or via corridor
  junction. The layout shows the corridors are at rows 6-7 and 13-14. To go from upper to
  lower, the player must traverse ~7 rows through the room structure.
  LowerCorr (13, col) → B(9,5): up ~4 rows + at col 5 already = ~4 moves.
B → collect K2 → D(9,43): traverse the lower corridor ~38 cols = ~38 moves (including
  navigating through any intermediate doors).
D → collect K3 → EXIT(3,57): up ~6 rows + right ~14 cols = ~20 moves.

This gives: 15 + 3 + 3 + 7 + 4 + 1 + 38 + 1 + 20 = ~92 moves. This is significantly
higher than the designer's 65, suggesting the layout is more forgiving than I'm computing,
or the grid is not as I'm reconstructing it.

The designer does not show step-by-step path arithmetic for the no-marks path. Without
this, the "65 > budget 59" forcing claim cannot be fully verified independently.

**Seed variance:** K positions are fixed in the blueprint (K1=(3,5), K2=(9,5), K3=(9,43))
— not seed-variable. Good. The layout is deterministic. Par is not seed-dependent.

**Mark-jump engine assumption:**
The designer notes the par-solver extension ("Dijkstra state must include
`frozen_marks: frozenset[str, row, col]`") is flagged as required. This is honest and
specific.

**`'` vs `` ` `` distinction:** The blueprint claims the exit door's column placement
makes `` `b `` (exact column) 1 step cheaper than `'b` (first non-blank of row). This is
a very small distinction — a 1-keystroke difference is within noise. It is not a strong
forcing argument for teaching `` ` `` specifically; it's more of a demonstration.

**Defect (minor):** The no-marks par of 65 is asserted but not computed step-by-step.
The forcing claim (65 > 59) is plausible from the layout topology but unverified. The
grid layout description is inconsistent: Row 18 is listed in the layout table but the
grid dims say "18 rows × 60 cols" (rows 0-17), yet rows up to Row 18 are shown.
This is a grid dimension error (should be 19 rows × 60 cols, or the row 18 is row
index 18 in 0-indexed 19-row grid). The entry is listed as (16, 2) in a supposed
"18 row" grid — which places it 2 rows from the bottom, plausible.

VERDICT: **CONDITIONAL PASS** — Forceability logic is topologically sound and the budget
arithmetic (59) is correctly computed from the claimed par (42). The no-marks path cost
(65) is asserted but not verified with step-by-step arithmetic; the margin of 6 keystrokes
(65-59) is tight and could flip if the no-marks path is actually 60-62. Grid has a
dimension inconsistency (18 vs 19 rows). Engine flags are specific and honest.
Design is sound IF mark commands are implemented.

### 4. Boss

Not applicable at L16.

---

## Level 17 — The Archivist's Library

### 1. Scope

New mechanics: `:e {filename}`, `:set {option}`. Count = 2.
PASS.

### 2. Linkage

Both are Vim command-mode meta-commands. `:e` navigates the filesystem; `:set` configures
the environment. The blueprint frames them as "control plane of your editor" — a coherent
framing. The family is slightly weaker than ideal (`:e` is navigation; `:set` is
configuration — different functions) but both live in `:` command mode and are taught
together in standard Vim tutorials. Analogous to how `wq` and `q!` are taught together.

PASS (weak, but acceptable).

### 3. Forceability (Contextual — relaxed budget ×2.0)

**Blueprint claims this level uses CONTEXTUAL teaching, not budget-forcing.**
The rules state: for `:e/:set` (contextual, relaxed budget), verify that:
(a) `:e` is genuinely REQUIRED to progress (not just flavor).
(b) `:set` does not need to be required, but the relaxed budget is justified.
(c) The relaxed budget (×2.0) is justified.

**(a) Is `:e index` genuinely required?**

The blueprint says: "The exit portal is locked until the player uses `:e index`. There is
no other way to obtain the passphrase that unlocks the Archivist's exit-door."

This is a hard lock — the player *cannot* progress without `:e index`. ✓

However, there is a logical gap: the "passphrase" mechanic requires:
1. Player uses `:e index` (visits the INDEX room).
2. Player reads passphrase "OPEN".
3. Player returns (`:q` or `:e archivist_library`).
4. Player speaks to Archivist NPC, who checks `player.flags['index_read']`.
5. Exit unlocks.

Step 4 is "speaking with the passphrase" — but the blueprint doesn't specify how the
player communicates the passphrase to the Archivist. If it's just bumping the NPC after
the flag is set (no additional input needed), then the "passphrase" is a flavor device
and the actual requirement is just `:e index` + return. This is fine mechanically but
the passphrase narrative is cosmetic.

**(b) Is `:set number` genuinely required?**

"The bonus keystone (not required for exit, but gives a scroll reward) requires knowing
an enemy's exact HP, which is hidden until `:set number` is active."

`:set number` is **NOT required for progression**. It unlocks only an optional bonus.
This satisfies the contextual teaching model (experiential, not forced).

**(c) Is the relaxed budget (×2.0 = budget 80 vs par 40) justified?**

The designer explicitly states this is a "guided contextual teaching moment, not a
par-pressure puzzle." The precedent from LEVELS_PLAN.md Decision D1 (undo as relaxed demo)
confirms this pattern is acceptable. The ×2.0 multiplier is stated explicitly.

PASS — but with a flag: the `:e {dungeon-name}` mechanic (visiting real dungeon names
from shelves) could create scope for the player to softlock by `:e`-ing into a prior
dungeon and not returning. The blueprint mentions `:q` or `:e archivist_library` to
return, but if the mini-room for e.g. `cave_01` doesn't have a clear return path, this
is a usability/design gap.

**Engine flags for `:e` and `:set`:** Both flagged explicitly and correctly. The INDEX
mini-room and `player.flags['index_read']` are specified.

VERDICT: **PASS** — `:e` is genuinely required for progression (hard lock). `:set` is
contextual (bonus only). Relaxed budget (×2.0) is justified per established curriculum
precedent. Engine flags are honest and specific.

### 4. Boss

Not applicable at L17.

---

## Level 17.1 — The Warden Pathfinder (Boss)

### 1. Boss placement and structure

- Caps Act III (levels 10-13). ✓
- Numbered 17.1. ✓
- Has 4 phases + 1 final, each mapping 1:1 to an Act III teaching level. ✓

PASS.

### 2. Scope

Boss uses all Act III mechanics. The LEVELS_PLAN rubric explicitly allows boss levels to
use all act mechanics ("Scope: Boss uses all Act III mechanics — acceptable for a boss").
This is confirmed by the LEVELS_PLAN.md Acts I and II boss precedents.

PASS.

### 3. Linkage

Each phase is a self-contained application of one Act III mechanic. Phases are ordered
by Act III level order (10→11→12→13). Coherent.

PASS.

### 4. Forceability (Boss)

**Phase 1 — `%` (NW Chamber):**
Three `[ ]` pairs with void interior. Identical to L10's mechanism. `%` is the only
non-lethal gap-crosser. The third `]` lands on K (shield-1 keystone). ✓

Estimated keystrokes (Phase 1): 3× (`moves to open bracket` + `%`) + navigate to K.
Rough: (3 moves + 1) × 3 = 12 + setup = ~12-14 keys. Designer says ~8. The discrepancy
is because the designer may assume the brackets are directly adjacent. With 3 pairs
on a chamber row (cols 3-24 = 21 cols), each pair's open bracket is reachable with ~2-3
moves each. ~8 may be accurate if the chamber is compact.

**Phase 2 — `/n` (SW Chamber):**
Four entities named "WARDEN" (3 decoys + 1 real). `/WARDEN<Enter>` = 7 keys. Then `n n`
to skip decoys (2 keys). `x x x` to test decoys (3 keys, assuming 1-damage kill per
decoy). Then `x` on real Warden.

But: the blueprint says "real Warden has HP=5 (visible with `:set number`)". If HP is not
visible (`:set number` not yet used), the player doesn't know when they've found the real
one vs. a decoy that just happened to survive one hit. This creates a mechanic dependency:
Phase 2 implicitly requires `:set number` (from Phase 4's mechanic) to be used early to
identify the real Warden. This is a **phase-ordering defect**: Phase 4's mechanic is
leaked into Phase 2.

**Fix:** Either (a) make decoys die in 1 hit regardless (so the player discovers the real
one by exclusion without needing HP visibility), or (b) make the real Warden visually
distinct (e.g. different character) in Phase 2. Option (a) is simpler.

Designer says "decoy goblins die instantly with 1 damage; the real Warden has HP=5
(visible with `:set number`)." If decoys die in 1 hit, the player can identify the real
Warden by exclusion — they `x` each found entity and the one that doesn't die is real.
This works WITHOUT `:set number`. So the mechanic ordering is actually fine — the
HP-visibility is a nice-to-have, not required for Phase 2 identification. **Self-correcting
defect — no fix needed.** However, the blueprint text is misleading in Phase 2's
description by mentioning HP=5 visibility, suggesting `:set number` is useful there.

Phase 2 cost: 7 + 2 + 4 (x-ing 3 decoys + 1 real) + navigation = ~15 keys. Designer
says ~12. Plausible if the chamber is small.

**Phase 3 — Marks (NE Chamber):**
"Warden speed = 1, same as player; no room to get past without marks."

This is the most problematic phase. The forcing argument hinges on the Warden chasing
at the same speed as the player, making it impossible to manually outmaneuver. This
requires precise spatial layout verification.

Chamber: cols 52-73 = 21 cols wide. K-red at col 54, K-blue at col 60, K-green at col 68.
Warden respawns at col 60 (on K-blue).

Path without marks: Player enters from left (col 52), moves right to K-red (col 54, 2
moves), collects. Then moves right to K-blue (col 60, 6 moves). Warden is at col 60
blocking K-blue? Or does Warden spawn after some trigger?

"Player sets ma at col 54 (K-red), collects K-red, mb at col 60 (K-blue), collects K-blue,
then Warden blocks the path back to green."

Wait — the player collects K-blue before Warden appears to block? Then how does Warden
block access to K-green (col 68) if the player just collected K-blue at col 60 and K-green
is at col 68 (8 cols further right)?

The layout is: K-red(54) ... K-blue(60) ... K-green(68). The player should be able to
walk right through all three in order: 54→60→68 = 16 moves from chamber entry, collecting
all keystones without needing marks at all, if Warden doesn't spawn until *after* K-blue.

**Defect:** The mark-forcing argument for Phase 3 is logically inconsistent. If the player
can collect K-red, K-blue in sequence (left to right), then K-green is also reachable by
continuing right — Warden spawning at col 60 (already passed) would be behind the player,
not blocking K-green. The designer says Warden "blocks the path back to green" but the
player doesn't need to go BACK — they can go FORWARD to green.

The only scenario where marks are needed is if the player must visit the keystones in
a non-linear order, or if the Warden spawns AHEAD of K-green. The blueprint doesn't
establish this non-linearity convincingly.

**Alternative forcing scenario:** If K-green requires stepping on K-red→K-blue→K-green
in order, AND the Warden blocks the corridor between K-blue and K-green (spawning at col
64, between 60 and 68), then the player needs to use mark-jump to "blink past" the Warden.
But this is not what the blueprint describes — it says Warden spawns at col 60 (= K-blue
position).

VERDICT FOR PHASE 3: The mark-forcing argument is **broken**. The spatial layout does not
support the claim that marks are required.

**Phase 4 — `:set number` (SE Chamber):**
"`:set number` reveals HP=3. Player uses `x` three times."

Without `:set number`, can the player just spam `x` until the Warden dies? If HP is
hidden, the player doesn't know when to stop. But the exit door opens "when Warden HP=0",
so the player can just `x` repeatedly until the door opens — no need to know HP=3
specifically. The `:set number` only saves the player from over-pressing `x` (which has
no downside if `x` on a dead entity is a no-op).

**Defect:** `:set number` is not genuinely required in Phase 4 for progression — the player
can blindly `x` until the door opens. The budget claim depends on whether extra `x`
presses cost keystroke budget. If `x` on dead entity = 0 cost, the player has no incentive
to use `:set number` in Phase 4.

**Budget for the boss:**

Designer: par = 60, budget = ceil(60×1.4) = 84.

Phase costs breakdown:
- Phase 1: ~12 (my estimate) vs designer's ~8
- Phase 2: ~15 vs designer's ~12
- Phase 3: uncertain (mark-forcing is broken, so par is undefined if marks aren't needed)
- Phase 4: ~5-8 (`:set number<Enter>` = 2+1+6+1=10 keys, then 3×`x` = 3 keys, navigate
  to exit = ~5 keys: total ~18 keys vs designer's ~8)
- Transitions: ~14 (as stated)

My estimate: 12 + 15 + ? + 18 + 14 = ~60+ (excluding Phase 3). With Phase 3 ~10 (if
marks not needed): ~72 total. Designer's 60 seems optimistic.

**Immunity flag:**
"Boss is immune to `G gg H M L } {` (Act II motions)." This is the correct
mechanism. The flag is specified as `warden_phase_immune: set[str]`. This is a new
engine requirement — flagged honestly.

VERDICT (Boss overall): **FAIL** — Phase 3 mark-forcing logic is broken (player can walk
linearly left-to-right without marks). Phase 4 `:set number` is not genuinely required
(player can spam `x`). Par arithmetic (60) is likely underestimated. Two of the four
phases have forcing defects.

---

## Engine Extensions — Completeness Check

All extensions from the blueprint table:

| Extension | Flagged? | Correct? |
|-----------|----------|----------|
| `%` motion in `engine/motion.py` | ✓ | ✓ |
| `player.last_search` (pattern + direction) | ✓ | ✓ |
| `n`/`N` dispatch | ✓ | ✓ |
| `player.marks` dict | ✓ | ✓ |
| `'a` / `` `a `` dispatch | ✓ | ✓ |
| Mark-aware par solver | ✓ | ✓ (or hardcode) |
| `:e {name}` command dispatch | ✓ | ✓ |
| `:set {option}` command | ✓ | ✓ |
| Warden immunity flag | ✓ | ✓ |

**Missing flag:** For L15, the blueprint does NOT clarify whether `/SIGIL` warps the
player *avatar* (teleport) or just highlights the position (cursor-only). This is a
critical missing engine specification that must be added.

**Missing flag:** For Boss Phase 3, the Warden's exact spawn trigger and spawn location
relative to the keystones must be specified precisely enough to verify the forcing
argument.

---

## Summary of Defects

### L10 — Bracket Vaults
- **D1 (Minor):** Par is miscounted. Blueprint claims 14; independent computation gives 12.
  Budget should be 17, not 20. Forceability is unaffected (walls block alternatives).
- **Fix:** Recount par step-by-step; tighten budget to ceil(12×1.4)=17. No redesign needed.

### L15 — Seekers' Labyrinth
- **D2 (Critical):** Par claim (33) is arithmetically impossible for a 20×70 grid. Even
  with optimal search, travel to SIGIL in worst-case alcove exceeds 33 total keystrokes.
- **D3 (Critical):** Engine behavior of `/SIGIL` is unspecified: does it teleport the
  player avatar, or only reveal position? Forcing argument depends entirely on this.
- **D4 (Moderate):** `?` and `n`/`N` forcing is not demonstrated with arithmetic for any
  specific seed configuration.
- **D5 (Minor):** Budget is informally "relaxed to 50" without recomputing par first.
- **Fix Options:**
  - Option A: Shrink grid to ~10×30, recompute par with step-by-step arithmetic, verify
    worst-case budget forces search.
  - Option B: Specify that `/SIGIL` teleports the player avatar (flag as engine extension),
    then recompute par correctly based on teleport-then-walk-to-exit cost.
  - Option C: Split level — L15 teaches only `/` (forward search with fog-of-knowledge);
    a small follow-up level teaches `n`/`N`.

### L16 — Waypoint Sanctum
- **D6 (Minor):** No-marks par (65) is asserted without step-by-step arithmetic.
  The forcing margin (65-59=6) is too tight to trust without verification.
- **D7 (Minor):** Grid dimension inconsistency: "18 rows" but rows 0-18 are listed (19 rows).
- **Fix:** Provide explicit step-by-step path cost for the no-marks path. Correct grid
  dimensions. If no-marks path is actually closer to 62, increase the layout to widen
  the margin or adjust par downward.

### L17 — Archivist's Library
- **D8 (Minor):** `:e`-ing into a prior dungeon name (e.g., `cave_01` from the shelf)
  could leave the player stranded if those rooms don't have a return mechanism.
- **Fix:** Either (a) restrict `:e` to only "index" in this level's context, or (b) ensure
  all named rooms have `:q` / `:e archivist_library` as a return path.

### L17.1 — Boss
- **D9 (Critical):** Phase 3 mark-forcing is broken. K-red→K-blue→K-green are left-to-right;
  a player can collect all three in linear order without marks. The Warden spawning at
  K-blue (col 60, already passed) does not block K-green (col 68, to the right).
  Fix: Redesign Phase 3 so keystones are in non-linear positions (e.g., two are behind
  the player after Warden spawns, forcing mark-jump to retrieve them without re-running
  past the Warden), OR have the Warden spawn ahead (between K-blue and K-green).
- **D10 (Moderate):** Phase 4 `:set number` is not required — player can spam `x` until
  the exit opens without knowing HP.
  Fix: Add a consequence to over-pressing `x` (e.g., each `x` after HP=0 has a cost, or
  use a timed mechanic), OR require the player to type exactly HP `x` presses (verified
  by a puzzle lock), OR make `:set number` reveal a code the player must enter.
- **D11 (Minor):** Phase 2 description says HP=5 is "visible with `:set number`" — implying
  `:set` is useful in Phase 2 — but this is not required for identification (decoys die
  in 1 hit). The text is misleading; clarify.
- **D12 (Minor):** Par (60) likely underestimates Phase 4 cost (`:set number<Enter>` = 10
  keys alone). Recompute.

---

## Overall Verdict

| Level | Scope | Linkage | Forceability | Boss | Overall |
|-------|-------|---------|-------------|------|---------|
| L10   | PASS  | PASS    | COND. PASS  | N/A  | COND. PASS |
| L15   | BORDERLINE | PASS | FAIL | N/A | FAIL |
| L16   | PASS  | PASS    | COND. PASS  | N/A  | COND. PASS |
| L17   | PASS  | PASS    | PASS (contextual) | N/A | PASS |
| 17.1  | PASS  | PASS    | FAIL        | FAIL (2 phase defects) | FAIL |

**Total FAILs: 2 levels** (L15, L17.1) **+ 2 CONDITIONAL PASSes** (L10, L16).

---

## Prioritized Fix List

**P0 — Must fix before level runs:**

1. **(L15) Specify `/ search` engine behavior** — teleport avatar or cursor-only? Add to
   engine extensions table. Without this, the entire L15 forcing argument is undefined.

2. **(L15) Recompute par with correct arithmetic** — the 33-keystroke claim is wrong for a
   20×70 grid. Either shrink the grid or recompute from first principles. Show worst-case
   seed arithmetic explicitly.

3. **(L17.1 Phase 3) Redesign mark-forcing** — K-red/K-blue/K-green are co-linear (left to
   right); player can reach all three without marks. Non-linear layout required (e.g., K-red
   at far left, K-green at far right, Warden spawning in the middle after K-blue is
   collected, forcing mark-jump back to one side).

4. **(L17.1 Phase 4) Make `:set number` genuinely required** — add a mechanic that makes
   blind `x`-spamming fail (e.g., a counter puzzle, or a "wrong hit" penalty that is only
   avoidable by knowing exact HP via `:set number`).

**P1 — Fix before release:**

5. **(L10) Correct par to 12, tighten budget to 17** — minor but cleanest to fix now.

6. **(L16) Provide step-by-step no-marks path arithmetic** — the 6-keystroke margin (65-59)
   must be verified; if the true no-marks cost is <60, the level needs a layout adjustment
   to widen the gap.

7. **(L16) Fix grid dimension: "18 rows" should be 19 rows** (rows 0-18, 0-indexed).

**P2 — Cleanup:**

8. **(L15) Provide explicit `n`/`N` and `?` forcing arithmetic** for a specific seed layout,
   not just narrative hand-waving.

9. **(L17) Clarify `:e` scope** — restrict or handle all shelf dungeon names to prevent
   softlock when player `:e`s into a named room without a return path.

10. **(L17.1) Clarify Phase 2 description** — remove the implication that `:set number` is
    useful in Phase 2 for decoy identification (it is not required; decoys die in 1 hit).

11. **(L17.1) Recompute boss par** — Phase 4 alone costs ~18 keys (`:set number<Enter>` +
    `x x x` + exit navigation); total par is likely 70+, not 60. Recompute and adjust
    budget accordingly.
