# Act V Blueprint — Adversarial Review

> Reviewer role: adversarial blueprint auditor.
> Source files: `blueprints/act_5.md`, `LEVELS_PLAN.md`.
> Multiplier rule (from act_5.md header): ×1.2 for L25 (r/R); ×1.4 for all others. Esc = 1 keystroke.

---

## L23 — The Inscription Halls (`i`, `a`)

### SCOPE
Count of new mechanics:
1. Insert mode entry (pressing i/a puts player in INSERT; Esc returns to NORMAL).
2. Rune inscription trigger (blank cell filled with required glyph unlocks a door).

**Count = 2. PASS.**

### LINKAGE
`i` and `a` are both insert-mode entry points differing only in cursor offset (at vs after). They are the minimal coherent pair for Insert mode introduction. **PASS.**

### FORCEABILITY — Par recompute

Blueprint par narrative (approximate):
- K1: `34l` (encoded as "3 keys" in blueprint — DEFECT: `34l` is 3 keystrokes (`3`, `4`, `l`) but the blueprint counts it as such only by using a count prefix; this is fine).
- Actually re-examining: the blueprint writes "Navigate to K1: `34l` = 3 keys". This is correct — `34l` is a count-prefixed motion: 3 keystrokes (`3`, `4`, `l`).
- Activate K1: `x` = 1
- Navigate to trigger (5,10) from (1,35): need to go 4 rows down and 25 cols left. `4j` = 2, `25h` = 3 = 5 keys total.
- `i ∆ Esc` = 3
- Navigate to K2 (8,5) from (5,10): `3j 5h` = 4 keys.
- `x` = 1
- Navigate to (10,14) from (8,5): `2j 9l` = 4 keys.
- `a Ω Esc` = 3
- Navigate to exit (10,35) from (10,15): `20l` = 3 keys.

**Recomputed par: 3+1+5+3+4+1+4+3+3 = 27 keystrokes.**
Blueprint claims par = 30. The difference is ~3 keystrokes (blueprint includes some navigation steps the recount consolidates differently). This is within par-solver tolerance — par-solver is authoritative per the spec.

**Budget check:** Blueprint says par=30, budget=ceil(30×1.4)=42. If recomputed par=27, budget=ceil(27×1.4)=38.

**DEFECT (MINOR):** The recomputed par (27) differs from the stated par (30). The budget at 27 would be 38, not 42. The forcing argument uses the 42 budget; it must be re-verified at 38. With budget=38, wrong-command penalty of +4 (two errors) gives 31 which is still ≤38. The margin is 7 (at budget=38) — enough to absorb a different-route approach.

**Forcing argument check:**
- Without `i` at the i-trigger: player uses `aΩEsc` → rune at col 11 not col 10, door stays locked. Must reposition: `h i∆Esc` = 4 additional keys vs `i∆Esc` = 3 (extra `h` = 1 extra). Blueprint says +2 per error.
- Without `a` at the a-trigger: player uses `i∆Esc` → rune at col 14 not col 15, door stays locked. Must reposition: `l a∆Esc` = 4 keys instead of 3 = 1 extra.
- Both wrong: +2 total extra keys over par.
- But +2 over par=27 is 29, still well under budget=38. **The forcing argument FAILS if par=27.**

**DEFECT (CRITICAL):** Forcing argument is broken if recomputed par is below 30. At par=27 and budget=38, the player has 11 keys of slack. Using wrong commands (e.g., `a` instead of `i` on both triggers) costs only +2, leaving total at 29 — well under budget. The level is NOT forceable as designed.

**Fix:** The grid must add more mandatory navigation or additional trigger cells so that the wrong-command penalty pushes over budget. Alternatively, increase the number of trigger cells to 4 (two pairs), doubling the penalty to +4, which at par=27 gives 31 — still under budget=38 at ×1.4. The blueprint's own admission in the forcing section states "budget is 42, naive wrong-command total is 43" — this arithmetic only holds if par=30 and budget=42. **The par must be verified by the par-solver; the blueprint should not be approved until par-solver confirms ≥30.**

**VERDICT: CONDITIONAL FAIL** — forcing argument depends on par=30 which the recount puts in doubt.

---

## L24 — The Sculpting Chambers (`I`, `A`, `o`, `O`)

### SCOPE
Blueprint counts 3 mechanics:
1. `I`/`A` — line-edge insert entries.
2. `o`/`O` — open-line (topology change, inserts a floor row).
3. Floor extension puzzle — sealed ledge unreachable without open-line.

The "floor extension puzzle" is the dungeon primitive that FORCES `o`/`O`, not a standalone mechanic. Stripping it out:

1. `I`/`A` — line-start/end insert (command behavior).
2. `o`/`O` — open-line with topology change (command behavior + side effect).

**Count = 2 distinct command mechanics. PASS on scope.**

**However: 4 NEW COMMANDS in one level.** LEVELS_PLAN.md principle says "1–3 new mechanics." The blueprint conflates "mechanics" with "command families." `I`/`A` differ from `i`/`a` only in jump target; `o`/`O` differ from each other only in direction. The blueprint calls them 2 mechanics, 4 commands. This is permissible under the "trivial direction/flavor variants count as one" rule (LEVELS_PLAN.md §Design principles). **BORDERLINE PASS.**

### LINKAGE
`I`, `A`, `o`, `O` are all insert-mode entry points. `I`/`A` are line-scope `i`/`a`; `o`/`O` are "open a new row." The linkage is: all enter INSERT mode, they differ in *where* the new content goes. **PASS.**

### FORCEABILITY — Par recompute

Blueprint optimal path:
1. K1 at (1,37): `36l` = 3 keys, `x` = 1. Total: 4.
2. Row 10: `9j` = 2 keys, `I Σ Esc` = 3. Total: 5.
3. Row 5 (inner wall top): `5k 2l` = 4 keys.
4. `o` = 1, `Esc` = 1. Total: 2.
5. Walk into sealed room via new row to some rune/exit: ~5 keys.
6. K2 (shifted to row 11 post-`o`): ~3 keys, `x` = 1. Total: 4.
7. Row 12 end: `j A Φ Esc` = 4 keys.
8. Exit (X at (12,39)): `5l` = 2.

Recomputed: 4+5+4+2+5+4+4+2 = **30 keystrokes** (estimate).
Blueprint claims par=32. Plausible; par-solver authoritative.

**Budget check:** par=32, budget=ceil(32×1.4)=45. **PASS on arithmetic.**

**Forcing argument — o/O:**
- Topology forcing (sealed room unreachable without `o`/`O`): **STRONG**. The sealed inner room (rows 4–8, cols 2–38) has no corridor connection to the main hall. `o` is the only way to insert a connecting floor row. This is binary: the puzzle is physically impossible without `o`/`O`.
- **DEFECT:** The blueprint does not specify whether `o` and `O` are BOTH required, or just one. `O` used from inside the sealed room would require being already inside — impossible. So only `o` (from row 5, opening a row below) is usable. `O` is topologically forced only if the player can be inside the room and needs to open a row above — which requires a second puzzle within the sealed room. **The blueprint only forces `o`, not `O`.** `O` appears as a decoration/teaching element, not a forced command.
- **Fix:** Add a second puzzle inside the sealed room that requires `O` (open row above): e.g., the X_alt ledge is above a sealed sub-room accessible only via `O` on the row below the ledge.

**Forcing argument — I/A:**
- The blueprint states the margin is "intentionally wide" (13 keys) and I/A forcing is loose. The wrong-command penalty for I at the wrong trigger is "off-by-many: +2 repositioning keys each." With budget margin of 13, two errors cost +4 — well under. **I/A are NOT forceable in this level.** The blueprint admits this explicitly.

**DEFECT (CRITICAL):** `I` and `A` are not forceable. The budget margin of 13 absorbs both errors. The self-check box "[x] o/O forced by topology; I/A by col trigger" is false for I/A.

**VERDICT: FAIL** — `I` and `A` are not budget-forced; `O` is not topology-forced.

---

## L25 — The Overwrite Halls (`r`, `R`)

### SCOPE
New mechanics:
1. `r{ch}` — single-char overwrite, 2 keystrokes, cursor stays.
2. `R` — Replace mode stream (overwrite-and-advance, Esc exits).

**Count = 2. PASS.**

### LINKAGE
Both overwrite existing runes in-place (vs insert which adds on empty/new cells). Minimal coherent pair. **PASS.**

### FORCEABILITY — Par recompute

Blueprint path:
1. K1 at (1,49): `48l x` = ... `48l` is 3 keystrokes (`4`,`8`,`l`), `x`=1 = 4 keys.
2. Navigate to row 4 col 4 from (1,49): `3j 45h` = `3j`=2, `45h`=3 = 5 keys.
3. r-CORRIDOR: `r α 2l r β 2l r γ 2l r δ` = `r`+`α` + `2l` + `r`+`β` + `2l` + `r`+`γ` + `2l` + `r`+`δ` = 2+2+2+2+2+2+2 = 14 keys. But wait: `2l` is 2 keystrokes (`2`,`l`), not 3. So: 4×2 (four `r{ch}`) + 3×2 (three `2l` moves) = 8+6 = 14. **CONFIRMED.**
4. Navigate to row 6 col 4 from row 4 col 10: `2j 6h` = `2j`=2, `6h`=2 = 4 keys.
5. R-CORRIDOR: `R P Q R S T Esc` = 7 keys (`R` + 5 chars + `Esc`).
6. K2 at (8,4): from (6,4): `2j`=2, `x`=1 = 3 keys.
7. Exit at (8,49): `45l`=3 keys.

**Recomputed par: 4+5+14+4+7+3+3 = 40 keystrokes.**
Blueprint claims par=39. Close; within 1 key. The rounding depends on exact navigation.

**Budget check (×1.2):** par=39, budget=ceil(39×1.2)=ceil(46.8)=47. Recomputed at par=40: budget=ceil(40×1.2)=48. Blueprint says 47. **PASS on arithmetic** (within par-solver tolerance).

**Esc counting:** `R P Q R S T Esc` — Esc is counted as 1 keystroke per the multiplier rule. The blueprint explicitly notes this. **PASS.**

**Forcing argument — r over s+i+Esc:**
- `s α Esc` = 3 keys vs `r α` = 2 keys. Savings per correction = 1 key.
- 4 corrections: total savings = 4 keys.
- Budget at ×1.2: par=39, budget=47. Without `r`, using `s` for all 4 corrections: +4 keys → total = 43, still ≤47. **r is NOT forced by budget alone.**

**DEFECT (CRITICAL):** With ×1.2 budget and 4 corrections, the `s`-approach total (43) is still under budget (47). The 8-key margin absorbs the 4-key penalty. The blueprint self-check marks "[x] r forced by budget (saves 1 key/correction × 4 = 4 keys; margin = 8 at ×1.2)" — **the self-check incorrectly passes this.** Margin=8 > penalty=4, so r is NOT forced.

**Fix:** Add 5 more single-cell corrections (total 9 corrections). `r`-approach: 9×2=18 keys. `s`-approach: 9×3=18... no. Actually with 9 corrections: `r` saves 9 keys total. Budget=47, par≈39+5nav=44. `s`-approach: 44+9=53 > 47. **9 corrections forces `r`.** The layout must have 9 void-gap separated wrong-glyph cells.

**Forcing argument — R over repeated r:**
- Mixed-glyph run of 5 cells: `R P Q R S T Esc` = 7 keys. Repeated `r` + moves: `r P l r Q l r R l r S l r T` = 5×2 + 4×1 = 14 keys. Savings = 7 keys.
- With current budget (47) and par (39), the R-savings of 7 keys: without `R`, using repeated `r`: par → 39+7=46 ≤ 47. **R is NOT forced; 46 < 47.**

**DEFECT (CRITICAL):** The R-CORRIDOR saving of 7 keys (46 total) is exactly 1 below budget (47). This barely fails to force `R` — a player using repeated `r` could still complete in 46 keystrokes, which is ≤47 and passes. **R is not forced.** The margin is 0 if r-savings are also applied to the r-corridor (which they might not be if the r-forcing also fails). This requires combined analysis:

If `s` is used for r-corridor (4 corrections, +4 keys) AND repeated `r` is used for R-corridor (+7 keys): total = 39+4+7=50 > 47. So the COMBINED worst case (avoiding both `r` and `R`) is forced. But the player can dodge only `R` (use `r` everywhere): 39+7=46 ≤ 47. R is still not individually forced.

**Fix:** Extend the R-corridor to 7 cells, making `R` savings = 14-7+2nav = larger. At 7 consecutive mixed-glyph cells: `R` = 1+7+1=9 keys. Repeated `r` + 6 moves = 7×2+6=20 keys. Savings = 11. Par grows by ~2 nav = ~41. Budget = ceil(41×1.2)=50. Without `R`: 41+11=52 > 50. **R is forced with 7-cell corridor.**

**VERDICT: FAIL** — `r` is not individually forced (4-cell r-corridor, 8-key margin). `R` is not individually forced (5-cell corridor, saves 7 but budget margin is 8).

---

## L26 — The Case Chambers (`~`, `g~`, `gU`, `gu`)

### SCOPE
New mechanics:
1. `~` — single-char case toggle with cursor advance.
2. Case operators `g~`/`gU`/`gu` — apply case transform over motion span.

**Count = 2. PASS.**

### LINKAGE
All four are case transformations. `~` is single-cell; `g~`/`gU`/`gu` are operator-scope. Same family. **PASS.**

### FORCEABILITY — Par recompute

Blueprint optimal path:
1. K at (2,4): `j 3l x` = 3 keys. Hmm: `j`=1, `3l`=2, `x`=1 = 4 keys.
2. Row 4 col 3: `2j 2h`... from (2,4): `2j`=2 (to row 4), cursor at col 4, shift to col 3: `h`=1 = 3 keys.
3. `gU6l` = 3 keys (g, U, 6, l — wait: `gU6l` is 4 keystrokes: `g`, `U`, `6`, `l`). **DEFECT in arithmetic.**
   - `gU6l` = keys: `g` + `U` + `6` + `l` = **4 keystrokes**, not 3.
   - Similarly `gu6l` = 4 keystrokes, `g~6l` = 4 keystrokes.
4. Single-char trigger (row 4, col 12): navigate `9l`=2, `~`=1 = 3 keys.
5. Navigate to D1 (row 6, col 39): `2j 27l` = `2j`=2, `27l`=3 = 5 keys.
6. Row 8, col 3: `2j 36h` = `2j`=2, `36h`=3 = 5 keys.
7. `gu6l` = 4 keys.
8. Row 10 D2: `2j 36l` = `2j`=2, `36l`=3 = 5 keys.
9. Row 12, col 3: `2j 36h` = 5 keys.
10. `g~6l` = 4 keys.
11. Exit (13,42): `j 36l` = `j`=1, `36l`=3 = 4 keys.

**Recomputed par: 4+3+4+3+5+5+4+5+5+4+4 = 46 keystrokes.**
Blueprint claims par=28. **This is a massive discrepancy — 28 vs 46.**

**DEFECT (CRITICAL — ARITHMETIC):** The blueprint systematically undercounts case operator keystrokes. `gU6l` is 4 keystrokes (`g`, `U`, `6`, `l`), not 3 as implied. Navigation also appears under-counted. The stated par of 28 is unrealistically low.

**Budget recompute:** ceil(46×1.4) = ceil(64.4) = **65 keystrokes** (vs blueprint's 40).

**Forcing argument — operators vs ~ only:**
- Using `~` for 6 cells on row 4: cursor must toggle case of 4 wrong-case cells. The cluster `abCDeF` needs 4 toggles (`a→A`, `b→B`, `e→E`... depends on which are wrong). If 4 cells need toggling: 4×1=4 `~` presses + 5 moves between them (staying on already-correct cells) = ~9 keys. vs `gU6l`=4 keys. Saves 5.
- With recomputed par (46) and budget (65): `~`-only approach on 3 zones ≈ 46+(9-4)+(6+6-4)+(similar)= 46+5+8+5 = 64 ≤ 65. **Still barely under budget — operators not definitively forced.**
- The blueprint's own note says "Tighten: add one more 6-cell mixed zone." This is necessary. **The level as designed does not force the operators with high confidence.**

**VERDICT: FAIL** — par arithmetic is incorrect (28 vs ~46); budget of 40 is wrong (should be ~65); forcing argument for case operators is loose and depends on exact cell counts not pinned in the blueprint.

---

## L27 — The Joiner's Gate (`J`, `gJ`)

### SCOPE
New mechanics:
1. `J`/`gJ` — row-join / lateral corridor carving (one mechanic, two variants).

**Count = 1. PASS.**

### LINKAGE
`J` and `gJ` differ only in space insertion. Minimal pair. **PASS.**

### FORCEABILITY — Par recompute

Blueprint optimal path:
1. K1 at (3,4): `j 3l x` = `j`=1, `3l`=2, `x`=1 = 4 keys.
2. Navigate to row 5 (from row 3): `2j`=2 = 2 keys. (But blueprint says `j`=1. From (3,4) to row 5: 2 rows down = `2j`=2 keys.)
3. `gJ` = 2 keys.
4. Walk into inner room to D_inner and X_inner: ~8 keys (blueprint's estimate).
5. K2 at (12,4): ~5 keys, `x`=1 = 6 keys.
6. Row 12 for J: `j`=1, `J`=1 = 2 keys.
7. Navigate to D2 and X (13,43): ~8 keys.

**Recomputed par: 4+2+2+8+6+2+8 = 32 keystrokes** (vs blueprint's 33). Close enough.

**Budget check:** ceil(32×1.4)=ceil(44.8)=45 (vs blueprint's 47 at par=33). **Arithmetic: ceil(33×1.4)=ceil(46.2)=47. CONFIRMED.**

**Topology forcing — J/gJ:**
- Sealed room (rows 6–10, cols 3–28): four solid walls, no entry. `J` is the only way in. **STRONGLY FORCED by topology. PASS.**

**J vs gJ distinction:**
- D_inner trigger: rune at col 4. `gJ` (no space) places joined content at col immediately adjacent; `J` (with space) shifts content to col 5. Wrong command: door stays locked.
- Repositioning cost: player must use the correct command. No repositioning is possible after the fact — the row has already been joined. **Player would need to undo and redo.** But `u` (undo) is available from L18.
- **DEFECT:** If `u` is taught by L27, the player can undo a wrong `J`/`gJ` and retry. Cost of undo: `u J/gJ` = 2 extra keystrokes per wrong attempt. With budget=47 and par=33, margin=14 — the player could attempt both wrong and right for D_inner: `gJ u J` = 4 keys instead of 2. But this only adds 2 extra keys, well within budget. **The J vs gJ distinction is NOT forced by budget.**

**DEFECT (SIGNIFICANT):** The J/gJ distinction relies on column-exact trigger, but undo allows a player to try `J` first, observe door stays locked, undo, try `gJ`. Cost: +2 keys per door. With 2 doors (D_inner and D2), maximum undo-retry cost: +4 keys. Par=33+4=37 ≤ budget=47. **Not forceable with undo available.**

**Fix (two options):**
1. Make the join irreversible in the engine (one-shot operation, no undo). This is a game-mechanic decision with broad implications.
2. Remove the J vs gJ distinction puzzle — use only one command (e.g., always `gJ`) for both doors, forcing it via topology only. The second door on the primary path uses `J` for a *different* topology puzzle (a different sealed room), where the *space* inserted by `J` is required to form a two-word rune trigger (with a literal space between words). This is a content distinction, not a column-counting one, and cannot be fixed by undoing.

**VERDICT: CONDITIONAL PASS (topology forcing is strong; J/gJ distinction forcing is weak if undo is available).**

---

## L28/L29 — The Alignment Halls + Indentation Sanctum (`>>`, `<<`, `>{m}`, `<{m}`, `=`)

### SCOPE — CRITICAL ANALYSIS

The blueprint claims 3 new mechanics:
1. `>>` / `<<` — shift runes on current line right/left (one shiftwidth).
2. `>{m}` / `<{m}` — same shift over multiple rows (motion-scope).
3. `=` — auto-indent (aligns to computed target column).

**But the actual command list is 5 commands: `>>`, `<<`, `>{m}`, `<{m}`, `=`.**

Grouping analysis:
- `>>` and `<<` = one mechanic (indent/unindent a single line, bidirectional — same as `h`/`l` being one directional mechanic).
- `>{m}` and `<{m}` = one mechanic (indent/unindent over a motion — the operator form).
- `=` = a third mechanic (auto-indent to computed target).

**Count = 3. SCOPE PASS by the blueprint's grouping.**

**However:** Is `>>`/`<<` genuinely the same mechanic as `>{m}`/`<{m}`? In Vim, `>>` is syntactic sugar for `>_` (indent current line). `>{motion}` is the general operator form. They are the same underlying mechanic at different scopes — analogous to `dd` vs `d{motion}`. By the LEVELS_PLAN.md rule ("trivial direction/flavor variants of one idea count as one"), grouping `>>`/`<<`/`>{m}`/`<{m}` as one family is defensible.

**However: 5 commands is a lot even if grouped as 3 mechanics.** The blueprint itself flags "5 commands in one level; ensure coherent family framing." LEVELS_PLAN.md groups J/gJ AND `>>`/`<<`/`>{m}`/`<{m}`/`=` together in L27 (the original plan before the blueprint split them into L27 and L28/L29). **The LEVELS_PLAN.md table shows L27 as "The Alignment Halls + Indentation Sanctum" teaching `J gJ >> << >{m} <{m} =` — that is 7 commands.** The blueprint split J/gJ into the separate L27, so L28/L29 has 5. This is better, but still at the edge.

**SPLIT RECOMMENDATION — see Findings section below.**

### LINKAGE
`>>`, `<<`, `>{m}`, `<{m}`, `=` are all horizontal rune-shift commands. They operate on rune positions within fixed floor cells (no topology change). They form the "horizontal alignment" family. **PASS.**

### FORCEABILITY — Par recompute

Blueprint par narrative for `>>` zone:
- `2>>` = 3 keys (`2`, `>`, `>`). Shifts col 5 → col 9 in two shiftwidths. CONFIRMED.

**For `>>` zone (DEFECT):** Blueprint says "two `>>` presses = 4 keys. Alt: `2>>` = 3 keys." Correct. But then says "Even cheaper: `>>`×2 = 4 keys or `2>>` = 3." This is circular. `2>>` is the cheapest single-line indent. The budget must be computed with the cheapest approach.

**For `<<` zone:** Similarly `2<<` = 3 keys. But the blueprint also suggests `<<`×2 = 4. The cheapest approach uses `2<<`=3.

**For multi-row zone (`>{m}`):**
- 3 rows, each needs 3 shiftwidths. 
- `>{motion}` applies ONE shiftwidth over the motion span.
- To shift 3 rows × 3 shiftwidths: need 3 × `>2j` = 3 × 3 keys = 9 keys + navigation.
- vs `3>>` per row: row 11: `3>>`=4 keys. `j`=1. `3>>`=4. `j`=1. `3>>`=4 = 14 keys total.
- `>2j` × 3 wins: 9 keys.
- **But `3>2j`** — is this valid? The blueprint explores this. In Vim, `3>2j` means "indent 3 times over the next 2 lines" = shifts 3 shiftwidths over rows 11–13 in 4 keystrokes (`3`,`>`,`2`,`j`). **If the engine supports count-prefixed `>{motion}`, then `3>2j` = 4 keys, which beats `>2j` × 3 = 9 keys.**

**DEFECT (FORCEABILITY — multi-row zone):** If `3>2j` is 4 keystrokes, the optimal path is 4 keys for the 3-row zone. The blueprint does not settle whether this syntax is supported. If it is, par drops significantly and the per-row `>>` vs `>{motion}` distinction collapses (because `3>2j` is both a count and a motion-operator).

**Budget recompute:**
Recomputing the full level:
1. K_A `x`: navigate + x ≈ `j 3l x` = 4 keys.
2. Row 4, `2>>` = 3 keys.
3. Navigate to D_A (5,32): `j 23l` = `j`=1, `23l`=3 = 4 keys. Pass through.
4. K_B `x` (7,4): `2j 28h x` = `2j`=2, `28h`=3, `x`=1 = 6 keys.
5. Row 8, `2<<` = 3 keys.
6. Navigate to D_B (9,32): `j 24l` = `j`=1, `24l`=3 = 4 keys. Pass through.
7. K_C `x` (14,4): navigate ≈ 5+1=6 keys.
8. Navigate to row 11, col 5: `3j` = 2 keys.
9. Multi-row zone: `>2j >2j >2j` = 9 keys (or `3>2j`=4 if supported).
10. `=` zone: `=2j` = 3 keys.
11. Navigate to exit (15,44): ~5 keys.

**Recomputed par (using `>2j`×3): 4+3+4+6+3+4+6+2+9+3+5 = 49 keystrokes** (vs blueprint's 52). Close.
**Recomputed par (using `3>2j`): 4+3+4+6+3+4+6+2+4+3+5 = 44 keystrokes.**

**Budget (at par=52):** ceil(52×1.4)=ceil(72.8)=73. Blueprint says 73. **CONFIRMED.**
**Budget (at par=44):** ceil(44×1.4)=62. If `3>2j` is optimal, the budget is 62 and the margin is 18.

**`>>` forcing over delete+retype:**
- Shifting rune cluster (4 glyphs) from col 5 to col 9: `2>>` = 3 keys vs delete+retype: `d4l i∘∘∘∘ Esc` = 3+1+4+1=9... no, `d4l` = 3 keys, `i` = 1, 4 chars = 4, `Esc` = 1 = 9 keys. Savings from `>>` = 6 keys per zone. With 2 alignment zones: saves 12 keys.
- Budget=73, par=52. Without `>>`: 52+12=64 ≤ 73. **`>>` is NOT forced by budget alone with this large margin.**

**DEFECT (CRITICAL):** The budget margin of 21 (73-52) is far too large to force `>>` over delete+retype (saves 6 keys/zone, 2 zones = 12 keys savings required, but margin is 21). The forcing argument "multi-zone aggregate +8 exceed the margin" is incorrect — +8 < 21.

**`=` forcing:**
- Blueprint: two clusters at different offsets; `=2j` = 3 keys vs manual `>>` per row requiring different counts. 
- `=2j` = 4 keystrokes (`=`,`2`,`j`... wait: `=` operator + `2j` motion = `=`+`2`+`j` = 3 keystrokes).
- Manual `>>` per row: row A needs 1 shiftwidth (`>>`=2 keys), row B needs 3 shiftwidths (`3>>`=4 keys) + `j` navigation = 2+1+4=7 keys.
- Savings: 7-3=4 keys. Budget margin is 21. **`=` is not forced.**

**VERDICT: FAIL** — `>>` and `=` are not budget-forced given the 21-key budget margin. The level requires significant tightening.

### SCOPE — SPLIT RECOMMENDATION

The 5-command level (technically 3 mechanics) is at the boundary. Given the forceability failures, a split is recommended:

**Proposed Split:**
- **L28/L29 — The Alignment Halls:** `>>`, `<<` only. New mechanic: horizontal rune shifting (single-line). Rune-alignment trigger (gate opens when rune at column X). Par ≈ 25, budget ≈ 35 (×1.4). Tighter margin forces `>>` over delete+retype (need ≥4 alignment zones with 4-key savings each = 16 keys penalty for no-`>>` → 41 > 35). FORCEABLE.
- **L27b — The Indentation Sanctum:** `>{m}`, `<{m}`, `=`. New mechanic: multi-row indent operator, auto-indent. 3-row zone forces `>{m}` over per-row `>>`; variable-delta zone forces `=`. Par ≈ 30, budget ≈ 42. FORCEABLE if budget is tighter.

This split reduces each level to 2 commands and 1–2 mechanics each, and makes forceability achievable.

---

## L29.1 — The Warden Scrivener (Boss)

### SCOPE
Boss level — all Act V commands. Not subject to the ≤3 mechanic limit; instead evaluated on per-phase immunity and one-command-per-phase structure. **N/A for scope.**

### BOSS STRUCTURE

**Per-phase immunity:** Blueprint specifies:
- Phase 1: immune to all except `r`.
- Phase 2: immune to all except `gU/gu/g~` (the blueprint says "all except gU/gu/g~" — THREE commands, not one).
- Phase 3: immune to all except `J/gJ` (TWO commands).
- Phase 4: immune to all except `>>` (one command).

**DEFECT (Phase 2 — one command per phase violated):** Phase 2 allows `gU`, `gu`, AND `g~` — three different commands. The boss principle requires "one command per phase." The rune condition is "uppercase the rune cluster" which specifically requires `gU`. `gu` would lowercase it (wrong direction) and `g~` would toggle (wrong transform). These wrong commands waste keystrokes but the phase still only has ONE correct answer (`gU`). **This is functionally one command per phase (only `gU` works), but the immunity description is imprecise.** Fix: state "Immune to all except `gU`."

**DEFECT (Phase 3 — one command per phase):** Phase 3 requires both `J` and `gJ` sequentially ("Player must `J` on row 12... then `gJ` on the combined row"). This is TWO commands in one phase. The boss principle says one command per phase. **FAIL — Phase 3 violates the one-command-per-phase rule.**

**Fix (Phase 3):** Use only `gJ` (or only `J`) for the join. Add the second join variant as its own phase (Phase 3b) or eliminate it.

### FORCEABILITY — Boss Par recompute

Phase budgets stated:
- Phase 1: 12 keys. Phase 2: 15 keys. Phase 3: 14 keys. Phase 4: 18 keys. Total par=59.

**Phase 1 recompute:**
- Navigate to phase 1 arena from entry: ~5 keys.
- Navigate to shield runes (row 7, cols 4,6,8): from Warden at (6,4), stand at col 4 row 7: `j`=1.
- `r∘` = 2, `2l`=2, `r·` = 2, `2l`=2, `r⊙`=2 = 10 keys for corrections.
- `x` Warden: navigate from (7,8) to (6,4): `k 4h`=3, `x`=1 = 4 keys.
- Total phase 1: 5+1+10+4 = 20 keys. Blueprint says 12. **Discrepancy of 8 keys — blueprint severely under-counts phase 1 navigation.**

**Phase 4 recompute:**
- Lock rune at col 10, shift to col 16: delta=6, shiftwidth=2, so 3 shiftwidths needed.
- `3>>` = 4 keys. Then navigate to Warden for `x`: distance unclear. Budget says 18 keys.
- `3>>` (`3`,`>`,`>`)=3 keystrokes, not 4. **`>>` is 2 keystrokes, `3>>` is `3`+`>`+`>`=3 keystrokes.** Blueprint claims "3>>` = 4 keys" — this is incorrect. **`3>>` = 3 keystrokes.**

**DEFECT (ARITHMETIC):** `3>>` is 3 keystrokes (count=`3`, operator=`>`, second `>`), not 4. This error appears in both L28/L29 and the boss.

**Budget check:** par=59, budget=ceil(59×1.4)=ceil(82.6)=83. Blueprint says 83. **Correct.**

**Phase immunities coverage:**
- Phase 1: `r` (overwrite family, from L25).
- Phase 2: `gU` (case operator, from L26).
- Phase 3: `J`/`gJ` (join, from L27). — Two commands used, violation.
- Phase 4: `>>` (indent, from L28/L29).

Commands NOT covered in boss phases: `i`, `a`, `I`, `A`, `o`, `O`, `R`, `~`, `g~`, `gu`, `<<`, `>{m}`, `<{m}`, `=`. The boss only tests 4 of the act's ~19 commands. This is a design choice (not every command needs a boss phase), but noteworthy.

**VERDICT: FAIL** — Phase 3 requires two commands (`J` then `gJ`) in one phase; `3>>` keystroke count is wrong in Phase 4; phase 1 par is severely under-counted.

---

## Alignment/Indentation Split Proposal (Detailed)

The LEVELS_PLAN.md groups J/gJ with `>>`/`<<`/`>{m}`/`<{m}`/`=` in one level. The blueprint already separated J/gJ into L27. The remaining 5 commands in L28/L29 should be split further:

### Proposed L28/L29 — The Alignment Chambers (`>>`, `<<`)

**Commands:** `>>` (indent right), `<<` (indent left).
**Mechanic count:** 1 — horizontal rune shift, bidirectional.
**Forcing:** Use 6 single-line alignment zones (3 for `>>`, 3 for `<<`). Each zone: rune offset by 2 cols (1 shiftwidth). `>>` or `<<` = 2 keys. Delete+retype = 7+ keys. Savings per zone = 5+ keys. 6 zones × 5 = 30 keys savings. Par ≈ 35, budget = ceil(35×1.4)=49. Without `>>`: 35+30=65 >> 49. FORCED.
**Linkage:** `>>` and `<<` are one mechanic (indent/unindent), directional variants.

### Proposed L27b — The Indentation Sanctum (`>{m}`, `<{m}`, `=`)

**Commands:** `>{motion}` (multi-line indent), `<{motion}` (multi-line unindent), `=` (auto-indent).
**Mechanic count:** 2 — operator-scope indent, auto-indent.
**Forcing:**
- `>{m}`: 4-row zone, each needs 1 shiftwidth. `>3j`=3 keys vs `>>` × 4 + 3 nav = 11 keys. Saves 8. Budget must be tight enough.
- `=`: 3-row zone with variable per-row deltas (row A needs 1 shift, row B needs 3 shifts). `=2j`=3 keys vs manual: `>>` on A (2) + `j` (1) + `3>>` on B (4) + `j` (1) + `2>>` on C (3) = 11 keys. Saves 8.
- Combined savings: 16 keys. Par ≈ 32. Budget=ceil(32×1.4)=45. Without operators: 32+16=48 > 45. **FORCED.**
**Linkage:** Both `>{m}` and `=` extend the indent mechanic to multi-row scope; `=` uses computed targets.

---

## Summary: Defects by Level

### L23 — The Inscription Halls
| Category | Finding |
|---|---|
| SCOPE | PASS (2 mechanics) |
| LINKAGE | PASS |
| FORCEABILITY | CONDITIONAL FAIL — par likely ~27 not 30; forcing argument relies on par=30 being confirmed by par-solver; at par=27 budget=38 and wrong-command penalty (+2) does not exceed budget |
| Concrete fix | Par-solver must confirm par≥30. If par<30, add 2 more trigger cells (one `i`-trigger, one `a`-trigger) to raise wrong-command penalty to +4 and ensure budget is exceeded without the correct commands. |

### L24 — The Sculpting Chambers
| Category | Finding |
|---|---|
| SCOPE | PASS (2 mechanics by family rule, 4 commands) |
| LINKAGE | PASS |
| FORCEABILITY | FAIL — `I` and `A` not budget-forced (13-key margin, 4-key penalty); `O` not topology-forced (only `o` from outside is usable) |
| Concrete fix | (1) Reduce budget by tightening par (add mandatory long-distance navigation). (2) Add a second sealed sub-room inside the main sealed room, accessible only via `O` (open row above) from inside — requires first entering via `o`. (3) Add `I` and `A` triggers with tighter column constraints so wrong-command penalty exceeds 2 keys. |

### L25 — The Overwrite Halls
| Category | Finding |
|---|---|
| SCOPE | PASS (2 mechanics) |
| LINKAGE | PASS |
| FORCEABILITY | FAIL — `r` not individually forced (4 corrections, 4-key savings, 8-key budget margin); `R` not individually forced (5-cell corridor saves 7 keys, within budget margin) |
| Concrete fix | (1) Increase r-corridor to 9 corrections: `r`-savings = 9 keys > 8-key margin. (2) Increase R-corridor to 7 consecutive cells: `R`-savings = 11 keys > 8-key margin. Adjust grid dimensions accordingly. |

### L26 — The Case Chambers
| Category | Finding |
|---|---|
| SCOPE | PASS (2 mechanics) |
| LINKAGE | PASS |
| FORCEABILITY | FAIL — par stated as 28 is arithmetically wrong (~46 is more accurate, since `gU6l` = 4 keystrokes not 3); budget of 40 is wrong (should be ~65); case operator forcing must be re-derived with correct par |
| Concrete fix | (1) Recount all keystrokes: `g~`/`gU`/`gu` + motion = 4 keystrokes, not 3. (2) Restate par and budget. (3) Verify that `~`-only approach exceeds the corrected budget; add more zones if needed. |

### L27 — The Joiner's Gate
| Category | Finding |
|---|---|
| SCOPE | PASS (1 mechanic) |
| LINKAGE | PASS |
| FORCEABILITY | CONDITIONAL PASS — topology forcing is strong; J vs gJ distinction is undermined by undo availability |
| Concrete fix | Make the J/gJ distinction rely on rune *content* (e.g., joined rune forms a different word with/without space) rather than column position, so undo+retry is not sufficient — the player must choose correctly on the first attempt because both J and gJ each produce a different irreversible world state. Alternatively: lock the rune type so that after a wrong join, the resulting rune cluster is a different (non-trigger) sequence, and the only way to progress is the correct command from the start. |

### L28/L29 — The Alignment Halls + Indentation Sanctum
| Category | Finding |
|---|---|
| SCOPE | BORDERLINE (5 commands, 3 mechanics — should be SPLIT) |
| LINKAGE | PASS |
| FORCEABILITY | FAIL — `>>` not forced (21-key budget margin absorbs 12-key penalty); `=` not forced; `3>>` keystroke count wrong (3 not 4) |
| Concrete fix | SPLIT into L28/L29 (>>/<< only) and L27b (>{m}/<{m}/=). In L28/L29: use 6 tight alignment zones, par≈35, budget≈49; without `>>`: 65>49. In L27b: use 4-row + variable-delta zones; combined savings 16 keys, par≈32, budget≈45; without operators: 48>45. |

### L29.1 — The Warden Scrivener (Boss)
| Category | Finding |
|---|---|
| SCOPE | N/A |
| LINKAGE | N/A |
| FORCEABILITY | FAIL — Phase 1 par severely under-counted (~20 keys not 12); `3>>` counted as 4 keystrokes when it is 3 |
| BOSS | FAIL — Phase 2 immunity description imprecise (3 allowed commands, only 1 correct); Phase 3 uses two commands (J then gJ) in one phase, violating one-command-per-phase rule |
| Concrete fix | (1) Fix Phase 2 immunity: "immune to all except `gU`." (2) Split Phase 3 into two phases: Phase 3 = `J` only (opens sealed row, reveals weak point), Phase 4 = `gJ` (merges fragment at exact column), Phase 5 = `>>` (align lock rune). This makes the boss 5 phases total. (3) Recount all phase pars with correct keystroke arithmetic. (4) Fix `3>>` = 3 keystrokes throughout. |

---

## Overall Verdict

**5 out of 6 levels (+ boss) have at least one FAIL.** Only L27 (Joiner's Gate) passes all criteria conditionally.

### Prioritized Fix List

1. **[CRITICAL] L28/L29 — SPLIT into L28/L29 (>>/<<) and L27b (>{m}/<{m}/=).** The 5-command scope and forceability failures together require this. The split also resolves the budget margin problem by tightening each sub-level's par.

2. **[CRITICAL] L25 — Increase r-corridor to 9 cells and R-corridor to 7 cells.** The current corridor sizes fail to force the commands within the ×1.2 budget margin.

3. **[CRITICAL] L26 — Recount par with correct keystroke arithmetic (`gU6l`=4, not 3).** Restate par (~46), budget (~65), and re-derive the forcing argument for case operators. Add more zones until `~`-only path exceeds budget.

4. **[CRITICAL] L29.1 (Boss) — Fix Phase 3 to use only one command.** Either `J` or `gJ` per phase, not both. Add a 5th phase for the second join command. Fix all keystroke arithmetic (`3>>`=3 keys).

5. **[SIGNIFICANT] L24 — Add topology forcing for `O` and budget forcing for `I`/`A`.** Add a sub-sealed-room inside the main sealed room requiring `O` from within. Tighten I/A trigger geometry so wrong-command penalty ≥ budget margin / 2.

6. **[SIGNIFICANT] L23 — Verify par≥30 with par-solver.** If par<30, add trigger cells to raise wrong-command penalty. The forcing argument is only sound if par=30 and budget=42 are confirmed.

7. **[MINOR] L27 — Harden J vs gJ distinction against undo+retry.** Change the trigger from column-exact to content-dependent so undo-and-retry does not allow brute-forcing the correct command.

8. **[MINOR] L28/L29 — Fix `3>>` = 3 keystrokes (not 4) throughout the blueprint and boss section.**
