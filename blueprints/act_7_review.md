# Act VII Blueprint — Adversarial Review

Reviewer posture: adversarial. Every forcing argument is stress-tested independently.
All arithmetic is recomputed from scratch; the blueprint's own numbers are not trusted
until verified.

---

## Level 31 — The Spellwright's Forge

### SCOPE

New mechanics introduced:

1. Arcane Mana pool (per-room integer, displayed in status bar, deducted by `:s`).
2. Fire terrain `F` (impassable) / Ice terrain `I` (passable) — a new terrain type pair
   with conversion semantics.
3. `:s/{from}/{to}/` and `:s/{from}/{to}/g` commands.
4. Wanderer enemies on fire rows (using existing enemy type, but placed on impassable
   terrain as a patrol complication).

Verdict: The blueprint claims "1 new mechanic" by bundling mana + `:s` as a single family
and treating F/I terrain as implicit. That accounting is wrong:

- Mana pool = new engine feature (SPEC §6.4 TBD).
- F/I terrain pair with conversion = new terrain mechanic (two new tile types + the rule
  that `:s` mutates terrain, not just text).
- `:s` command = new command mechanic.

That is **3 new mechanics** — which is the maximum. The blueprint's claim of "1" is
misleading but the actual count does not exceed the cap. Borderline PASS on scope, but
the claim of "1" should be corrected to "3" in the document.

**SCOPE: PASS (3 of 3 max, but mislabeled as 1 — fix the count)**

---

### LINKAGE

`:s` is command-mode (`:` already known from Level 1 `:w/:q`). The `/from/to/` substitution
syntax and the `g` flag are one cohesive idea: "replace text at current scope". Mana is the
resource gate, not a separate gameplay family. F→I terrain conversion is the puzzle
expression of `:s`.

The wanderer enemies on fire rows are a minor complication using an already-known entity
type and do not constitute a new mechanic family.

**LINKAGE: PASS**

---

### FORCEABILITY — INDEPENDENT PAR RECOMPUTATION

**Layout facts (from blueprint):**
- Entry: row 1, col 1. Exit: row 15, col 49.
- Fire rows: rows 4, 7, 10. Cols 3–48 = **46 tiles per row** (col 48 − col 3 + 1 = 46).
  The blueprint says "20 F tiles per row" in the placements table but rows 4/7/10 in the
  exact blueprint grid show `FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF` spanning
  cols 3–48 of a 52-col grid, which is 46 F characters, not 20. This is a significant
  discrepancy. The blueprint uses "20" in the forcing argument. We flag this as a defect
  and recompute using both values.

**Defect D-31-1:** The blueprint contradicts itself on fire-row width. The ASCII diagram
shows 46 F tiles; the placements table says 20. The forcing argument relies on this count
for the manual-path cost. At 46 tiles the manual cost is even higher, so the forcing
direction is correct, but the par computation uses 20, which is wrong if the map truly has
46. Fix: reconcile to one number and restate par.

**Recomputing par using the blueprint's stated layout (treating 20 tiles as intended):**

Segment-by-segment:

1. Entry (row 1, col 1) → fire row 4: `4j` = 4 keystrokes (not 2 as stated in blueprint;
   moving from row 1 to row 4 is 3 rows down = `3j` = 2 keystrokes counting the prefix
   digit + j, OR just the number 3 + j = 2 keys, but the blueprint writes `4j` for 2
   keys which is correct: `4` + `j` = 2 keystrokes).
   Wait — re-read: blueprint says `4j — move down to row 4 (2 keystrokes)`. From row 1,
   `4j` moves 4 rows to row 5, not row 4. To reach row 4 from row 1, the correct command
   is `3j` = 2 keystrokes. This is another defect.

**Defect D-31-2:** `4j` from row 1 reaches row 5, not row 4. Fire row is at row 4, so
the correct navigation is `3j` (2 keys). The blueprint writes `4j` everywhere for
fire-row navigation which is off by one. This makes the route description internally
inconsistent (player lands on row 5, not the fire row, then must navigate back). Fix:
change `4j` to `3j` for the first fire corridor.

Let me recompute par from scratch with correct geometry:

- Entry: row 1, col 1.
- Fire row 1 at row 4 → from row 1: `3j` = 2 keys to reach row 4.
- `:s/F/I/g<CR>` = `:` `s` `/` `F` `/` `I` `/` `g` `<CR>` = 9 keystrokes. Correct.
- `j` = step into cleared row 4 (now passable): 1 key. But wait — player is already ON
  row 4 when they issue `:s`. The `:s` command in Vim operates on the current line. So
  after `3j`, player is at row 4. `:s/F/I/g` clears row 4. Then `j` moves to row 5
  (open floor). That is correct.

- From row 5 → fire row 7: `2j` = 2 keys. Correct.
- `:s/F/I/g<CR>` = 9 keys.
- `j` to row 8 = 1 key.
- From row 8 → fire row 10: `2j` = 2 keys.
- `:s/F/I/g<CR>` = 9 keys.
- `j` to row 11 = 1 key.
- Row 11 → keystone at row 13, col 1: `2j` = 2 keys (plus already at col 1, so no
  horizontal move needed). Blueprint says `3j`. From row 11 to row 13 = 2 rows, so `2j`
  not `3j`. Another off-by-one.

**Defect D-31-3:** Navigation from row 11 to row 13 (keystone) is `2j` (2 keys), not
`3j` as stated in the blueprint. The blueprint's own route says `3j — move to row 13
(2 keystrokes)` — the keystroke count of 2 is correct for `3j` but the count of rows
(3 vs 2) is wrong; both cannot be right.

Let me recount with corrected geometry:

| Step | Command | Keys |
|------|---------|------|
| Row 1 → row 4 (fire row 1) | `3j` | 2 |
| Clear fire row 4 | `:s/F/I/g<CR>` | 9 |
| Step into row 4 → row 5 | `j` | 1 |
| Row 5 → row 7 (fire row 2) | `2j` | 2 |
| Clear fire row 7 | `:s/F/I/g<CR>` | 9 |
| Step to row 8 | `j` | 1 |
| Row 8 → row 10 (fire row 3) | `2j` | 2 |
| Clear fire row 10 | `:s/F/I/g<CR>` | 9 |
| Step to row 11 | `j` | 1 |
| Row 11 → row 13 (keystone) | `2j` | 2 |
| Collect keystone | `x` | 1 |
| Row 13 → row 15 (exit row) | `2j` | 2 |
| Col 1 → col 49 (exit) | `48l` | 3 |

**Independent par = 2+9+1+2+9+1+2+9+1+2+1+2+3 = 44 keystrokes**

Blueprint claims par = 47. The difference is 3 keys due to the `4j`→`3j` correction for
fire row 1 and the `3j`→`2j` correction for keystone navigation. The actual corrected par
is **44**.

**Budget recomputed:** ceil(44 × 1.4) = ceil(61.6) = **62 keystrokes** (blueprint says 66).

**Forcing argument — manual path:**

The blueprint argues: "without `:s/g`, manual clearing of 20 tiles × 2 keys = 40 per
row, 120 total". At the corrected tile count of 46, manual cost rises to 92 per row ×
3 = 276 keystrokes. Even at 20 tiles it's 120, far exceeding budget of 62. **Forcing
holds at either tile count.**

**Mana dual gate — `:s` without `g`:**
Each room has mana = 8. Without `g`, each `:s/F/I/` costs 1 mana but only clears one F
tile. To clear 20 tiles: 20 mana needed. Pool = 8. Fails after 8 invocations. At 46
tiles: 46 mana needed vs. 8 pool. Gate holds. However: the blueprint says "mana=8,
budget=14" for puzzle rooms, but the main par table says budget = 62 for the full level.
The per-room budget of 14 is unexplained and inconsistent with the level-wide budget of
62. Are rooms independently budgeted? If so, the per-room budget of 14 should be
explained and enforced separately. This is ambiguous.

**Defect D-31-4:** Per-room budget of 14 appears only in the mana allocation table and is
never reconciled with the level-wide budget of 62. If rooms have independent budgets, the
level-wide par/budget computation is irrelevant. If not, the per-room budget numbers are
noise. Fix: decide whether budget is per-room or level-wide and document consistently.

**Keystroke counting: does `:` count as 1 key?**
The blueprint states: "`:` enters command mode, each subsequent character costs 1."
This is the correct model. `:s/F/I/g<CR>` = 9 keystrokes. Verified.

**Command-avoiding routes:**
- Can the player use `r` (replace single char) to change F→I one at a time? Each `r I`
  = 2 keystrokes per tile. 20 tiles = 40 keys per row, 120 total → over budget. Blocked.
- Can the player skip fire rows entirely by going around? The grid has `##` walls on all
  four sides with fire rows spanning cols 3–48 of a 52-col grid; wall cols 0–2 and 49–51
  are `#`. There is no navigable path around the fire rows.
- Can the player use `dd` to delete a fire row and walk through? The blueprint does not
  specify whether `dd` affects terrain. If `dd` deletes the current line including fire
  tiles, this is a massive escape hatch. The blueprint should explicitly state that `dd`
  on a fire row does NOT clear it for movement (or if it does, cost it and verify budget).

**Defect D-31-5:** The blueprint does not address `dd`, `dw`, or other deletion operators
applied to fire terrain tiles. If deletion operators treat fire tiles as rune-like objects
and remove them, the player can use `3dd` (3 keys) to clear an entire fire row, which is
cheaper than `:s/F/I/g` (9 keys) and would bypass the teaching objective entirely. Fix:
explicitly specify that fire terrain is NOT affected by `d`/`c` operators (terrain is
not a rune).

**FORCEABILITY: CONDITIONAL PASS** — forcing holds if D-31-1 through D-31-5 are resolved.
Par should be corrected to **44**, budget to **62**. The dual gate (budget + mana) is
sound in principle but the arithmetic errors undermine confidence.

---

### BOSS: N/A (Level 31 has no boss)

---

### VERDICT: CONDITIONAL PASS

| Principle | Result | Notes |
|-----------|--------|-------|
| Scope | PASS | 3 mechanics (mislabeled as 1) |
| Linkage | PASS | `:s` + mana + F/I terrain are one family |
| Forceability | CONDITIONAL PASS | 5 defects; par wrong by 3 keys; `dd` escape hatch unaddressed |
| Boss | N/A | — |

**Required fixes:** D-31-1 (tile count), D-31-2 (navigation off-by-one), D-31-3
(keystone nav off-by-one), D-31-4 (per-room vs. level budget), D-31-5 (`dd` escape hatch).

---

---

## Level 32 — The Hall of Echoes

### SCOPE

New mechanics introduced:

1. Macro recording — `q{a-z}…q`.
2. Macro replay — `@{reg}` and `N@{reg}`.

Named registers `"a`–`"z` are cited as "partially implemented" and "introduced
conceptually in yank/paste levels." If they are genuinely prior knowledge, they are not
new here. The blueprint correctly counts 2 new mechanics.

**SCOPE: PASS (2 of 3 max)**

---

### LINKAGE

`q`/`@` use the named-register namespace (`"a`–`"z`) which was established in the yank/paste
act. Recording into a register and replaying from it is one coherent family. `N@{reg}` is
the count-form of `@{reg}`, same family. `@@` (last macro) is not mentioned in the
blueprint's forced-command set; no issue.

**LINKAGE: PASS**

---

### FORCEABILITY — INDEPENDENT PAR RECOMPUTATION

**Layout analysis:**

From the precise chamber layout table:

- Player starts at col 1.
- Chamber 1: goblin at col 4, ember rune at col 7, door at col 8.
- Chamber 2: goblin at col 9, ember at col 12, door at col 13.
- Chamber 3: goblin at col 14, ember at col 17, door at col 18.
- Chamber 4: goblin at col 19, ember at col 22, door at col 23.
- Chamber 5: goblin at col 24, ember at col 27.
- Exit at col 77.

**Does `w` land on the goblin?**
`w` in Vim jumps to the start of the next word. In a dungeon engine that treats each tile
as a character, the "words" depend on tile classification. The blueprint warns: "Spacing is
schematic; actual col positions should be tuned during generation to guarantee `w` lands on
goblin and ember positions." This is a critical caveat — if `w` does not reliably land on
the goblin position, the macro body `w dw w x` is wrong and the whole forcing argument
collapses.

**Defect D-32-1:** The macro body `w dw w x` assumes `w` always lands exactly on the
goblin, then exactly on the ember rune. This is only true if the word-boundary detection
places each goblin and each rune at a word start. The inter-chamber spacing (cols differ
by 5 between each chamber's goblin) must be verified against the engine's `w` motion
implementation to confirm identical step sizes across all 5 chambers. The blueprint
acknowledges this only as a "tuning note" — it should be a hard verified prerequisite.
Fix: specify the exact word-boundary rules the engine uses (e.g., does `g` glyph
constitute a one-character word? does `.` floor tile count as whitespace separator?) and
verify the layout satisfies them.

**Does `dw` kill the goblin?**
The blueprint asks "does `dw` kill an enemy on the landing cell of `w`?" and does not
answer it. `dw` in Vim deletes from cursor to start of next word. If the engine treats
goblin death as "delete the entity at the motion range's endpoint", and the cursor is
already on the goblin (because `w` landed there), then `dw` would delete from the
goblin's position to the start of the next word (the ember), potentially consuming both
targets. Alternatively, if the cursor is one step before the goblin (adjacent floor),
`dw` would delete from cursor through the goblin to the next word boundary, which could
kill the goblin.

The exact semantics depend on whether the player cursor is ON the goblin after `w` or
ADJACENT to it. These are different combat outcomes and the blueprint leaves this
unspecified.

**Defect D-32-2:** The `dw` kill mechanic is semantically ambiguous. The blueprint asks
the question but does not answer it. A macro that silently fails to kill the goblin (e.g.,
because `dw` deletes tiles rather than attacking enemies) would soft-lock the level. Fix:
specify and verify in `engine/operator.py` that `dw` with cursor on an enemy entity
attacks that enemy and removes it from the level.

**Independent par recomputation:**

Macro approach:

- `qa` = 2 keys (open recording into register `a`)
- Macro body for chamber 1 (executed live): `w dw w x` = 1+2+1+1 = 5 keys
- `q` = 1 key (close recording)
- Recording overhead total = 2 + 5 + 1 = 8 keys. Matches blueprint.
- First replay batch: `4@a` = 1+1+1 = 3 keys (digit `4`, `@`, `a`). Matches blueprint.
- Navigate to exit: player is at col 27 after chamber 5, exit at col 77.
  Distance = 77 − 27 = 50 columns. `50l` = 3 keys (digit `5`, `0`, `l`).
  Blueprint says `49l` which is 3 keys (`4`, `9`, `l`).
  Let me recheck: after collecting ember rune at col 27 and opening final door (no
  door after chamber 5), player is at col 27. Exit at col 77. 77 − 27 = 50 steps.
  So `50l` is correct, not `49l`.

**Defect D-32-3:** Navigation to exit is `50l` (3 keys: `5`, `0`, `l`) not `49l` (3
keys). The keystroke count is the same (3 keys) so par is unaffected, but the command is
wrong. Fix: change `49l` to `50l`.

**Independent par:**

| Step | Command | Keys |
|------|---------|------|
| Record macro (chamber 1 live) | `qa w dw w x q` | 8 |
| Replay × 4 | `4@a` | 3 |
| Navigate to exit | `50l` | 3 |
| **Total** | | **14** |

Blueprint par = 14. **Confirmed.** Budget = ceil(14 × 1.4) = ceil(19.6) = **20**.
Blueprint says 20. Confirmed.

**Next-best path (manual, no macro):**

Manual per chamber: `w dw w x` = 5 keys × 5 chambers = 25 keys.
Navigate to exit: 3 keys.
Total = 28 keys. Budget = 20. 28 > 20. **Manual fails. Forcing holds.**

**Single-replay fallback: `@a @a @a @a` (no count form):**

Recording: 8 keys.
Replay chamber 2: `@a` = 2 keys.
Replay chamber 3: `@a` = 2 keys.
Replay chamber 4: `@a` = 2 keys.
Replay chamber 5: `@a` = 2 keys.
= 8 + 4×2 = 16 keys.
Navigate: 3 keys.
Total = 19 keys. Budget = 20. **19 ≤ 20. The single-replay fallback PASSES the budget.**

The blueprint claims this path costs 20 exactly ("scrapes under"). Let me verify:
Blueprint says `qa w dw w x q @a @a @a @a` = 8 + 4×3 = 8 + 12 = 20. But `@a` = 2
keystrokes (`@` + `a`), not 3. Blueprint counts `@a` as 3 keystrokes, which would
mean it's counting the whitespace separator. If the budget engine counts whitespace in
command strings, this changes everything. If not, 4×`@a` = 4×2 = 8 keys, total = 16 + 3
(exit) = 19 keys — well under budget.

**Defect D-32-4 (CRITICAL):** The blueprint counts `@a` as 3 keystrokes in the fallback
analysis. `@` and `a` are 2 keystrokes. If `@a` = 2 keys, the single-replay fallback
costs 8 + 8 + 3 = 19 < 20. The budget does NOT force `N@a` over individual `@a` repeats
— the player can use four separate `@a` calls and still finish under budget. The `N@a`
form is not strictly forced. This breaks the "COUNT form `N@a` is forced over single `@a`
repeats" requirement.

Fix options:
A. Reduce budget by 1: budget = 19 → single-replay costs 19 = budget (ties, not fails).
   But ties typically pass (≤ budget). Still not forced.
B. Add one more chamber (N=6): manual = 6×5+3 = 33 > 20. Macro: 8+3+3 = 14 ≤ 20. Single
   replay: 8+5×2+3 = 21 > 20. Forces `N@a`. But N=6 means `5@a` in the count form.
C. Increase manual cost per chamber so budget tightens. Add an intermediate step.
D. Accept that the level teaches `N@a` conceptually via the tutorial scroll but does not
   strictly force it over individual replays. Document this honestly.

Option B (6 chambers) is the cleanest fix if strict forcing of `N@a` is required.

**FORCEABILITY: FAIL** — the count form `N@a` is not strictly forced over individual `@a`
repeats due to an arithmetic error in the blueprint. Manual approach is correctly excluded,
but the sub-goal of forcing `N@a` specifically is not achieved.

---

### BOSS: N/A (Level 32 has no boss)

---

### VERDICT: FAIL

| Principle | Result | Notes |
|-----------|--------|-------|
| Scope | PASS | 2 mechanics |
| Linkage | PASS | q/@ are one family |
| Forceability | FAIL | `N@a` not forced over `@a×N`; `dw` semantics unverified; `w` positioning unverified |
| Boss | N/A | — |

**Required fixes:** D-32-1 (`w` word-boundary verification), D-32-2 (`dw` kill semantics),
D-32-3 (`49l`→`50l`), D-32-4 (CRITICAL: `@a` = 2 keys, not 3 — add chamber 6 to force
`N@a`).

---

---

## Level 32.1 — The Warden Eternal (FINAL BOSS)

### SCOPE

No new mechanics introduced. The boss reuses `:s/F/I/g` (Level 31) and `q/@ "` (Level
32). The wave-timer mechanic (fire respawn every N keystrokes), the multi-phase boss state
machine, and the mana refill orbs are engine features, not new commands taught to the
player. Scope is satisfied.

**SCOPE: PASS (0 new commands, reuse only)**

---

### LINKAGE

All three phases demand Act VII mechanics. Phase 1 → `:s`. Phase 2 → macros. Phase 3 →
both. Coherent.

**LINKAGE: PASS**

---

### FORCEABILITY — PHASE BY PHASE

#### Phase 1 — The Ashen Tide

**Blueprint claims:**
- 3 fire rows, 20 F tiles each.
- Wave timer: "every 6 keystrokes" fire respawns.
- Mana pool: 12 at phase entry; `:s/F/I/g` costs 3.
- Par: 34 keystrokes. Budget: 48.
- Next-best: manual F-clear = 120 keystrokes.

**Independent par recomputation:**

Optimal sequence as described:

| Step | Command | Keys |
|------|---------|------|
| Clear fire row 2 | `:s/F/I/g<CR>` | 9 |
| Step into row 2 | `j` | 1 |
| Clear fire row 3 | `:s/F/I/g<CR>` | 9 |
| Step to row 3 | `j` | 1 |
| Clear fire row 4 | `:s/F/I/g<CR>` | 9 |
| Step to row 4 | `j` | 1 |
| Strike Warden at row 5 | `dw` | 2 |
| Advance to door row 6 | `j` | 1 |
| Open phase door | `x` | 1 |
| **Total** | | **34** |

Blueprint par = 34. **Confirmed.** Budget = ceil(34 × 1.4) = ceil(47.6) = **48**. Confirmed.

**Wave timer issue:**
The player takes 34 keystrokes to complete phase 1. The wave timer fires every 6 keystrokes,
so fire would respawn at keys 6, 12, 18, 24, 30. That's 5 respawns during the optimal
run. But the optimal sequence clears each row immediately before stepping into it:
- Keys 1–9: `:s/F/I/g<CR>` clears row 2. (Timer fires at key 6 during this — fire spawns
  DURING command entry.)
- Keys 10: `j`. Player enters row 2.

If the wave timer fires at key 6 (mid-command-entry for `:s`), it would respawn fire on
rows already being cleared or rows not yet reached. This creates ambiguity: does the wave
timer fire during command-mode input? If yes, the player may be caught mid-command with
fire respawning under them. The blueprint does not address whether the wave timer is
suspended during command-mode entry (i.e., does `:s…<CR>` consume 9 timer ticks or just
1?).

**Defect D-B-1 (CRITICAL):** The wave timer granularity (every 6 keystrokes) conflicts
with the 9-keystroke cost of `:s/F/I/g<CR>`. If the timer fires every 6 player keystrokes
including those typed in command mode, fire respawns mid-`:s` command entry (at key 6
of the 9-key sequence). This either: (a) interrupts command-mode; (b) respawns fire
behind the player's already-cleared rows; or (c) is undefined behavior. The forcing
argument assumes the player can clear all 3 rows before any respawn, which requires the
timer to NOT fire during command-mode input, or the wave timer window to be large enough
(≥ 34 keys for the entire optimal run). But at 6-key intervals, this is contradicted.
Fix: either (i) make the wave timer ≥ 40 keystrokes (enough for a full optimal run), or
(ii) specify that command-mode keystrokes do not advance the wave timer, and document this
in the engine.

**Manual cost verification:**
Manual F-clear via `x` per tile: 20 tiles per row × (move + interact) = 20×2 = 40 keys per
row × 3 rows = 120. Plus navigation and Warden strike: ~10 more. Total ≈ 130 >> 48.
Forcing holds IF the wave timer is resolved.

**Mana verification:**
12 mana at entry. 3 `:s/F/I/g` calls × 3 mana = 9 mana used. 3 mana remaining. This
works. The mana constraint does not constrain phase 1 (player has enough for 4 calls).
The mana gate in phase 1 is loose — it doesn't force anything extra. The budget gate alone
does the work.

#### Phase 2 — The Echo Storm

**Blueprint claims:**
- 4 warden copies. Compound move per copy: `w dw j` = 4 keys (blueprint says 4, but `w`+`d`+`w`+`j` = 4 keys — wait, blueprint writes the body as `w dw j` which is `w`, `d`, `w`, `j` = 4 keystrokes).
- Macro: `qa w dw j q` = overhead 6 keys; body = `w dw j` = 4 keys (recorded).
  Wait: `q` `a` = 2 keys to start; body `w` `d` `w` `j` = 4 keys (executed live on copy 1);
  `q` = 1 key to stop. Total recording = 7 keys, not 6.
- Replay: `3@a` = 3 keys for copies 2, 3, 4.
- Navigation to door: `3j x` = 4 keys.
- Par: 7 + 3 + 4 = **14**, but blueprint says 6 + 3 + 4 = **13**.

**Defect D-B-2:** The recording overhead is miscounted. `qa` = 2 keys, body = `w dw j` =
4 keys (executed live), closing `q` = 1 key. Total = 7 keys, not 6. Blueprint says 6
overhead. Actual phase 2 par = 7 + 3 + 4 = **14**, not 13.

Budget recomputed: ceil(14 × 1.4) = ceil(19.6) = **20** (same as blueprint's 19 due to
the discrepancy — blueprint says budget = 19, which would be ceil(13 × 1.4) = ceil(18.2)
= 19). With corrected par of 14, budget = 20.

**Next-best (manual × 4 copies):**
4 copies × `w dw j` = 4 × 4 = 16 keys + nav 4 = **20 keys**. Budget corrected to 20.
20 ≤ 20 (manual equals budget, does not exceed it). **Manual does NOT fail the budget
— it ties.**

**Defect D-B-3 (CRITICAL):** With corrected par (14) and corrected budget (20), the
manual approach costs 20 keys — exactly equal to the budget. A tie typically passes
(≤ budget). Therefore the manual approach is NOT excluded, and the macro is not forced.

Blueprint claims "manual = 20 > 19" to make it fail by one. But:
1. If recording overhead = 7 (not 6), par = 14 and budget = 20.
2. Manual = 20 ≤ 20. Not forced.

Alternatively, if we keep the blueprint's par = 13 (accepting 6-key overhead):
Budget = 19. Manual = 20 > 19. Forced. But the 6-key overhead is wrong (it's 7).

This is a critical arithmetic error that makes phase 2 forcing fail under independent
verification. Fix: either (a) accept 7-key overhead, set par = 14, budget = 20, and add
one more chamber copy (5 copies instead of 4) so manual = 5×4+4 = 24 > 20; or (b)
redefine the macro body to be 3 keys instead of 4 (e.g., drop the `j` sidestep) and
recompute.

**Single-replay fallback (`@a` × 3):**
With 7-key overhead: 7 + 3×2 + 4 = 7 + 6 + 4 = 17 < 20. The count form `3@a` (3 keys)
vs. three `@a` (6 keys) saves 3 keys. With budget = 20, both forms pass. `N@a` is again
not forced over individual replays.

**Defect D-B-4:** In phase 2 (same issue as D-32-4 for level 32): `@a` = 2 keystrokes,
not 3. Three separate `@a` calls = 6 keys; `3@a` = 3 keys. Under the corrected budget of
20, `3@a` (total 14) and `@a @a @a` (total 17) both fit. Only if budget is tightened
(e.g., by adding copies) does `N@a` become strictly necessary.

#### Phase 3 — The Eternal Surge

**Blueprint claims:**
- 2 fire rows (not 3 as in phase 1) + 3 warden copies.
- Par ≈ 35 (explicitly marked approximate). Budget ≈ 49.
- The macro body includes a `:s` call: `qa w dw j :s/F/I/g<CR> q`.
- Body = `w dw j :s/F/I/g<CR>` = 1+2+1+9 = 13 keys. Overhead = `qa` + `q` = 3 keys.
  Total recording = 3 + 13 = 16 keys (blueprint says "overhead 6; body = 15 keys").

Let me re-read: Blueprint writes "overhead 6; body = `w dw j :s/F/I/g<CR>` = 15 keys".

`w` = 1, `d` = 1, `w` = 1, `j` = 1, `:` = 1, `s` = 1, `/` = 1, `F` = 1, `/` = 1,
`I` = 1, `/` = 1, `g` = 1, `<CR>` = 1 → body = 13 keys, not 15. Blueprint says 15.

**Defect D-B-5:** Phase 3 macro body `w dw j :s/F/I/g<CR>` = 13 keystrokes, not 15 as
stated. The blueprint also says "overhead 6" but `qa` + `q` = 3 keys. If we count the
first-copy execution (live, inside the recording) as part of the overhead: `qa` (2) +
body-live-first-copy (13) + `q` (1) = 16 total for the recording block. Blueprint says
"overhead 6; body 15" which doesn't add up by any counting method.

**Independent phase 3 par recomputation:**

Step 1: Clear 2 fire rows (rows 13–14 from arena diagram):
- Player enters phase 3 zone at row 13. Fire rows 13 and 14.
- `:s/F/I/g<CR>` × 2 = 18 keys.
- `j` to step through = 1 key per row = 2 keys.
- Subtotal: 20 keys.

Step 2: Record macro for warden copies (first copy live in recording):
- `qa` = 2 keys.
- `w dw j :s/F/I/g<CR>` = 13 keys (live execution on copy 1).
- `q` = 1 key.
- Subtotal: 16 keys.

Step 3: Replay for 2 remaining copies: `2@a` = 3 keys.

Step 4: Strike Warden Eternal (`5j dw` or `G dw`):
- `5j` = 2 keys (nav), `dw` = 2 keys = 4 keys total.

Step 5: Navigate to exit (`x` + nav):
- `x` = 1 key, `49l` or similar ≈ 3 keys = 4 keys.

**Independent phase 3 par = 20 + 16 + 3 + 4 + 4 = 47 keystrokes.**
Budget = ceil(47 × 1.4) = ceil(65.8) = **66 keystrokes.**

Blueprint says par ≈ 35, budget ≈ 49. Our independent computation yields 47/66 — a
massive discrepancy. The blueprint's 35-key par appears to have dramatically undercounted
the recording cost (16 keys for the macro recording block alone, plus 20 for initial fire
clears).

**Defect D-B-6 (CRITICAL):** Phase 3 par is dramatically undercounted. Blueprint claims
≈35; independent calculation yields ≈47. Budget should be ≈66, not 49. The "approximate"
caveat is insufficient — a 34% undercount invalidates the forcing argument which depends
on the exact budget value. Fix: recompute phase 3 par carefully with exact arena geometry
and correct keystroke counts.

**Is the combined approach forced in phase 3?**

Blueprint claims "`:s` only (no macro): ≈55 > 49" and "macro only (no `:s`): hard blocked
by fire".

With corrected budget of 66:
- `:s` only approach: 2 fire clears (18 keys) + 3 manual warden strikes (3 × `w dw j` =
  12 keys) + nav = 18 + 12 + 4 + 4 = 38 keys < 66. **`:s`-only fits the corrected budget.**
- This means the combined-approach forcing argument collapses entirely under the corrected
  numbers.

**Defect D-B-7 (CRITICAL):** With the corrected budget of 66, the `:s`-only approach
(clear fire with `:s`, manually handle all 3 warden copies) costs ≈38 keys, which is well
under budget. Phase 3 does NOT force the macro technique — `:s` alone suffices. The
blueprint's forcing argument relies on the incorrect budget of 49. Fix: either (a) add
more warden copies to phase 3 to make the manual-with-`:s` approach exceed 66 keys, or
(b) use a tighter budget multiplier, or (c) redesign phase 3 geometry.

**``:s` inside a macro body — engine feasibility:**
The blueprint asserts that `engine/macro.py`'s `record_char` captures `:`, `/`, printable
chars, and `<CR>`, and that command-mode dispatch replays correctly when driven by `synth_key`
objects. This is a complex engine requirement. If command-mode replay via `synth_key` is not
implemented, the entire phase 3 puzzle is impossible. The blueprint flags this as an
assumption but does not provide evidence it works.

**Defect D-B-8:** `:s` inside a macro body requires the engine's replay mechanism to
correctly dispatch command-mode sequences. This is a significant engine prerequisite that
should be tested independently before the level is built. Flag as a hard prerequisite.

**Phase 3 — `N@a` forcing:**
Even with the correct par, if `:s`-only suffices (as shown above), adding `N@a` is
optional, not forced. To force both:
- Increase warden copy count to 6+ (enough that manual per-copy is infeasible).
- OR increase fire row count to 4+ (so `:s` calls consume enough keys that manual Wardens
  push total over budget).
The current design with 3 copies and 2 fire rows does not create a hard forcing of both
techniques simultaneously.

**Total boss par/budget summary (corrected):**

| Phase | Blueprint Par | Corrected Par | Blueprint Budget | Corrected Budget |
|-------|-------------|---------------|-----------------|------------------|
| Phase 1 | 34 | 34 | 48 | 48 |
| Phase 2 | 13 | 14 | 19 | 20 |
| Phase 3 | ~35 | ~47 | ~49 | ~66 |
| Total | 82 | ~95 | 116 | ~134 |

---

### BOSS: FAIL

| Phase | Technique Forced? | Notes |
|-------|------------------|-------|
| Phase 1 (`:s/F/I/g`) | CONDITIONAL | Wave timer fires mid-command (D-B-1) |
| Phase 2 (macro) | FAIL | Overhead miscounted; manual ties budget; `N@a` not forced (D-B-2, D-B-3, D-B-4) |
| Phase 3 (combined) | FAIL | Par dramatically undercounted; `:s`-only fits corrected budget (D-B-5, D-B-6, D-B-7) |

The core finale concept (multi-phase combat requiring both techniques) is sound, but the
arithmetic does not support the design as written. All three forcing arguments require
correction.

---

### VERDICT: FAIL

| Principle | Result | Notes |
|-----------|--------|-------|
| Scope | PASS | No new mechanics |
| Linkage | PASS | All phases in Act VII family |
| Forceability | FAIL | Phase 2 manual ties budget; phase 3 combined not forced; wave timer undefined |
| Boss | FAIL | Phase 2 and 3 forcing arguments collapse under independent arithmetic |

---

---

## Engine Prerequisites (Required Before Build)

The following are engine features that do not yet exist and must be built before Act VII
can be correctly implemented or validated:

| # | Feature | Required by | Status per blueprint |
|---|---------|------------|---------------------|
| E1 | Arcane Mana pool (per-room integer, deducted by `:s`, displayed in status bar) | L31, L32.1 | TBD (SPEC §6.4) |
| E2 | Fire terrain `F` (impassable) / Ice terrain `I` (passable, produced by `:s`) | L31, L32.1 | New terrain types |
| E3 | `:s/{}/{}/` and `:s/{}/{}/g` command dispatch — terrain-aware substitution | L31, L32.1 | New command |
| E4 | Macro recording (`q{a-z}`) and replay (`@{reg}`, `N@{reg}`) | L32, L32.1 | Partially in `engine/macro.py` |
| E5 | Macro-aware par solver (extended Dijkstra modeling macro recording state) | L32, L32.1 | Significant validator extension |
| E6 | Wave timer mechanic (fire respawn every N player keystrokes) | L32.1 Phase 1 | New engine tick hook |
| E7 | Multi-phase boss state machine (phase door triggers, HP tracking) | L32.1 | New `content/bosses.py` feature |
| E8 | `:s` replay inside macro body via `synth_key` in command-mode dispatch | L32.1 Phase 3 | Confirm before build |
| E9 | `dw` kills enemy on landing cell (verify semantic) | L32, L32.1 | Needs verification in `engine/operator.py` |
| E10 | Word-boundary `w` reliably lands on entity positions (verify for given layout) | L32, L32.1 | Layout-dependent; must verify |

---

## Overall Verdict

**FAIL.** The act blueprint has a sound high-level concept — dual-technique Act VII
capstone — but contains multiple critical arithmetic errors in the forceability arguments
that cause the mandatory commands to not be strictly forced under independent verification.

Specific failures:
- Level 31: Par overcounted by 3 keys (navigation off-by-ones); tile count contradicted
  (20 vs. 46); `dd`-on-fire-terrain escape hatch unaddressed.
- Level 32: `N@a` count form not forced because `@a` = 2 keys not 3 (four separate
  `@a` calls fit under budget). `dw` kill semantics unverified.
- Boss Phase 2: Recording overhead off by 1 key (6→7); manual approach ties budget at
  corrected numbers; macro not strictly forced.
- Boss Phase 3: Par undercounted by ~12 keys (35→47); under corrected budget the
  `:s`-only approach fits, meaning Phase 3 does NOT force the combined use of both
  techniques — the central design goal of the finale boss is unachieved.

---

## Prioritized Fix List

1. **[CRITICAL] Fix `@a` key count** (D-32-4, D-B-4): `@a` = 2 keystrokes, not 3.
   Consequences: Level 32 and Boss Phase 2 do not force `N@a` over individual `@a`
   repeats. Fix: add chamber 6 to Level 32 (making manual cost 33 > 20) and add a warden
   copy to Boss Phase 2 to maintain forcing.

2. **[CRITICAL] Recompute Boss Phase 3 par** (D-B-6, D-B-7): Correct par is ~47, not
   ~35. Under correct budget (~66), `:s`-only approach (≈38 keys) fits without macros.
   Phase 3 does not force the combined technique. Redesign with more warden copies or
   additional fire rows so that `:s`-only exceeds budget 66.

3. **[CRITICAL] Resolve wave timer vs. command-mode keystrokes** (D-B-1): Specify
   whether timer ticks during command-mode input. If it does, a 6-keystroke timer fires
   mid-`:s` command. Either make the timer fire only on normal-mode keystrokes, or extend
   the wave window to ≥ 40 keystrokes.

4. **[HIGH] Fix Level 31 navigation off-by-ones** (D-31-2, D-31-3): `4j` → `3j` for
   first fire row; `3j` → `2j` for keystone navigation. Corrected par = 44, budget = 62.

5. **[HIGH] Reconcile L31 fire tile count** (D-31-1): ASCII grid shows 46 F tiles;
   placements say 20. Choose one and update the forcing argument accordingly.

6. **[HIGH] Fix Boss Phase 2 recording overhead** (D-B-2, D-B-3): Overhead = 7 keys
   (not 6). Corrected par = 14, budget = 20. Manual approach now ties (20 = 20) — not
   excluded. Add one copy (5 total) to restore forcing: manual = 5×4+4 = 24 > 20.

7. **[HIGH] Address `dd` escape hatch on fire terrain** (D-31-5): Explicitly specify
   that `d`/`c` operators do not affect terrain tiles. Document in level and engine spec.

8. **[HIGH] Fix Level 31 scope claim** (D-31 scope): Blueprint claims 1 new mechanic;
   correct count is 3 (mana, F/I terrain conversion, `:s` command). Update documentation.

9. **[MEDIUM] Verify `dw` kill semantics** (D-32-2): Confirm in `engine/operator.py`
   that `dw` with cursor on an enemy kills that enemy. Document the verified behavior in
   the blueprint.

10. **[MEDIUM] Verify `w` word-boundary positioning** (D-32-1): Confirm that with the
    exact layout specified, `w` consistently lands on goblin positions across all chambers.
    Lock in the exact column positions (not schematic).

11. **[MEDIUM] Fix Boss Phase 3 macro body keystroke count** (D-B-5): Body = 13 keys,
    not 15. Overhead = 7 keys (not 6). Restate phase 3 par and budget after correcting
    all sub-counts.

12. **[MEDIUM] Reconcile per-room vs. level-wide budget** in Level 31 (D-31-4): The
    mana allocation table cites per-room budget=14 which contradicts the level-wide
    budget=62. Clarify which enforcement model is used.

13. **[LOW] Fix L32 navigation command** (D-32-3): `49l` → `50l` (player at col 27,
    exit at col 77 = 50 steps). Keystroke count is unaffected (both = 3 keys) but
    command is wrong.
