# Act II Blueprint — Adversarial Review

> Reviewer: independent adversarial pass.
> Principles: (1) Scope ≤3 new mechanics, (2) Linkage coherent, (3) Forceability — par re-derived, budget=ceil(par×1.4), taught command strictly cheapest and next-best exceeds budget; (4) Boss caps act at x.1, immune to untaught commands, one-phase-per-Act-II-motion.

---

## Level 5 — The WORD Forge (`W B E`)

### 1. SCOPE

New mechanics: W, B, E. Count = **3**. PASS.

### 2. LINKAGE

W/B/E are the WORD-level analogs of already-taught w/b/e (Act I, Level 3). The trio is the canonical "WORD motion" family; teaching all three together is standard. No cross-family contamination. **PASS.**

### 3. FORCEABILITY — Independent Par Re-Computation

**Grid:** 10 rows × 58 cols. Entry (1,1), Exit (7,51).

**Corridor structure:**
- C1 (row 1, L→R): `@` at col 1. Code groups W1 (cols 3–13), W2 (cols 16–24), W3 (cols 27–31), W4 anchor (cols 53–54). Turn at col 53, descend via RT1 gap to row 4.
- C2 (row 4, R→L): Enter at col ~53 side, traverse B4 (43–48), B3 (35–39), B2 (25–30), B1 anchor (3–4). Void runes at (4,1) and (5,1). Turn via LT1 gap to row 7.
- C3 (row 7, L→R): E1 (3–4), E2 (7–9), E3 (12–14), E4 (33–51). Exit at (7,51).

**Re-deriving par:**

*C1 with W:* `4W` = count "4" + key "W" = 2 ks, lands at col 54 (end of W4 or RT1 entrance area). Then `jj` to descend = 2 ks (no count needed for 2 rows if adjacent). Actually `2j` = 2 ks. Sub-total C1+descent: 4 ks.

*C2 with B:* From col ~53 area, `4B` = 2 ks, lands at B1 anchor col 3. Then `2j` to descend to row 7 = 2 ks. Sub-total C2+descent: 4 ks.

*C3 with E:* From col ~3 area, `4E` = 2 ks, lands at col 51 (exit). Sub-total C3: 2 ks.

**Recomputed par = 4+4+2 = 10.** Matches blueprint. **Budget = ceil(10 × 1.4) = 14.**

**Adversarial search for cheaper W-avoiding route:**

- *C1 without W:* Each code group is "adjacent single-char clusters" with type boundaries. `w` hits every alphanumeric/punctuation boundary. In `result=func` alone: `result`(word)→`=`(punct)→`func`(word) = 3 w-presses. W1+W2+W3 = at minimum 9 w-presses + gaps between groups. `12w` (count 2 ks) is generous; actual is likely `9w` = 2 ks or possibly more due to group boundaries. But even `9w` = 2 ks (same as `3W`). The critical claim is that the groups contain **more than 3 word-boundary transitions**, making `3W` unachievable without W. Let's check: `result=func` has boundaries at `=` and between `=func`. That is 2–3 `w` presses for 1 `W` jump. Three groups = 6–9 w-presses for 3 W-jumps. `9w` = 2 ks (count "9" + w). So the best w-alternative to `3W` (2 ks) is also 2 ks. The 4th group adds only `§‽` (untypable anchor, but movement still works). So `w` parity argument is WEAK for individual corridor forcing.

- *The designer's response:* The budget is tight overall. C1 alone: W-path = 2 ks; w-path ≈ `9w` = 2 ks (tie), or `12w` = 3 ks if more boundaries. The guard wall ensures the turn column is exact. The forcing is not "W is cheaper per-corridor" but rather "accumulation across three corridors + tight overall budget."

- *Adversarial check:* If C1 is `9w`=2 ks (tie), C2 is w/B comparable, C3 uses `e` — what's the total? `9w`(2)+`2j`(2)+`B-alternatives`+`2j`(2)+`e-alternatives`. B-corridor: void at (4,1) blocks `0`/`^`; `b` on adjacent clusters could be cheaper or tied. E4 is a 19-char group; from col 14, `e` stops at every internal boundary. The blueprint claims `12e` = 3 ks, but this is the count for reaching exit via `e`. Actually `12e` = 2 ks (len("12")=2, + "e"=1 = 3 ks total). So e-alternative to `4E` (2 ks) costs 3 ks. That's 1 extra ks.

- *Full w/b/e-only path:* `9w`(2)+`2j`(2)+`Nb`(2 or 3)+`2j`(2)+`12e`(3) = 11–12 ks ≤ 14 budget. **W/B/E-free path may fit budget.** This is a genuine defect.

**FORCEABILITY DEFECT:** The W and B corridors do not clearly demonstrate that w/b alternatives cost MORE than W/B. The "9w=2ks" scenario ties W. The designer relies on accumulation, but if each corridor is independently 2 ks with or without the taught command, there is no individual or joint forcing. The void rune guards on B are the strongest force (blocking `0`/`^`), but `b` with count may still be competitive.

**Verdict: FAIL — W and B are not demonstrably strictly forced; w/b with counts may match or only marginally exceed W/B cost; the budget arithmetic does not preclude a w/b/e-only path at 11–12 ks vs budget=14.**

**Required fix:** Make the code groups denser so that `w`-crossings per group are provably ≥4 per W-hop (e.g., groups like `a.b+c*d` have 7 w-boundaries but 1 W). Then `7w` per group × 4 groups = `28w` ≈ 3–4 ks vs `4W`=2 ks. Alternatively, tighten budget multiplier to 1.2 (budget=12) and guarantee ≥13 w-presses per corridor so even with count the w-path costs 3 ks per corridor.

---

## Level 6 — The Backward Vaults (`ge gE`)

### 1. SCOPE

New mechanics: ge, gE. Count = **2**. PASS.

### 2. LINKAGE

ge/gE are the backward-end companions of e/E, analogous to b/B (backward-start) for w/W. The pair shares the "backward end of word/WORD" semantic. Teaching them together is natural. **PASS.**

### 3. FORCEABILITY — Independent Par Re-Computation

**Grid:** 13 rows × 40 cols. Entry (1,1), Exit (12,19).

**Claimed optimal:** `4E 2j ^ 2j $ 2j ge 2j $ 2j gE j` = 2+2+1+2+1+2+1+2+1+2+1+1 = 18.

**Re-deriving par:**

The path visits 6 corridors and the exit row:
- C1 (row 1, L→R): `4E` = 2 ks → col 36 (just before guard wall at 38)
- RT1 descent: `2j` = 2 ks → row 3
- C2 (row 3, R→L): `^` = 1 ks → col 2 (first non-blank; guard wall at col 1 row 4 forces this)
- LT1 descent: `2j` = 2 ks → row 5
- C3 (row 5, decorative): `$` = 1 ks → right end
- RT2 descent: `2j` = 2 ks → row 7
- C4 ge moment: `ge` = 1 ks → col 5 (LT2 gap)
- LT2 descent: `2j` = 2 ks → row 9
- C5 (decorative): `$` = 1 ks
- RT3 descent: `2j` = 2 ks → row 11
- C6 gE: `gE` = 1 ks → col 19 (exit anchor)
- Exit: `j` = 1 ks → row 12

**Recomputed par = 2+2+1+2+1+2+1+2+1+2+1+1 = 18.** Budget = ceil(18 × 1.4) = ceil(25.2) = **26.** Matches blueprint.

**Adversarial check — ge forcing at C4:**

Player is at col 38, row 7. Must reach col 5 (LT2 gap entry). Options:
- `ge` (1 ks): backward to end of previous word = col 5. ✓
- `gE` (1 ks): backward to end of previous WORD. The anchor is 4 all-word-char; so gE also lands at col 5. Tied with ge (both are 1 ks). Blueprint acknowledges this tie explicitly.
- `33h` (3 ks): count "33" + h. col 38-33=5. Cost = len("33")+1 = 3 ks.
- `b` (1 ks): goes to **start** of the anchor cluster = col 2. Col 2 at row 8 is walled. Dead end.
- `B` (1 ks): same as b for all-word-char cluster = col 2. Also walled.

So the only valid 1-ks options are ge and gE (both reach col 5). Count-h is 3 ks. **ge and gE are jointly forced at C4 — acceptable since both are taught.**

**Adversarial check — gE forcing at C6:**

Player at col 38, row 11. Must reach col 19 (exit anchor end).
- `gE` (1 ks): backward end of previous WORD. WORD = cols 21–38 (three adjacent clusters A+S+B with no gaps). gE jumps to col 19 (end of anchor rune at cols 18–19). Cost = 1 ks.
- `ge` chain (3 ks): `ge`→30 (end of S), `ge`→28 (end of A), `ge`→19 (end of anchor) = 3 ge presses. As count: `3ge` = 3 ks (no count prefix helps: "ge" is 2 chars, so `3ge`=4 chars ≠ simpler). Actually `3ge` is len("3")+"ge" = 1+2 = 3 ks. vs gE = 2 chars = 1 ks. gE saves 2 ks. ✓
- `19h` from col 38: len("19")+1 = 3 ks. Same cost as ge-chain.
- `b` chain: anchor is 2-char (cols 18-19), then WORD cluster B, then S, then A. `b` to col 31 (B start), `b` to col 21 (A start)... doesn't land at col 19. Actually from within B (col 38), `b`→col 31 (start of B cluster), `b`→col 23 (start of S)... `b` traverses clusters. Not 1 ks to col 19.

**gE is strictly cheapest (1 ks) at C6; next-best = 3 ks.** Savings = 2 ks. Budget slack = 26-18=8 ks. But the 2-ks saving is individually meaningful.

**Budget tightness check:** Can a player bypass C6's gE using budget slack?
- Replace `gE` (1 ks) with `3ge` (3 ks): total path = 18-1+3 = 20 ks. 20 ≤ 26. **Fits budget. gE is NOT strictly forced by budget.**
- Replace `gE` with `19h` (3 ks): same result.

**FORCEABILITY DEFECT at C6:** gE is locally cheapest (1 ks vs 3 ks) but the 8-ks budget slack is wide enough to absorb the 2-ks penalty. A budget of 26 allows the player to skip gE and still complete the level.

**ge at C4 is effectively forced** (along with gE jointly) because the alternatives (h-count = 3 ks) cost 2 more, and if combined with gE-skip, total excess = 4 ks. Even so, each individually skippable within slack.

**Verdict: FAIL — Budget slack of 8 ks (26-18) allows skipping both ge (saves 2 ks vs 33h) and gE (saves 2 ks vs 3ge), using 4 extra ks total, yielding path ≤ 26. The taught commands are individually cheapest but NOT budget-forced.**

**Required fix:** Reduce budget to ceil(18 × 1.2) = 22 OR add forcing terrain that makes the ge/gE-avoiding path genuinely infinite or ≥27 ks. The simplest approach: add a wall gap at C4 that makes `33h` impossible (e.g., intermediate walls blocking h-count traversal), leaving only ge/gE as finite-cost.

---

## Level 7 — The File Vaults (`G gg {n}G`)

### 1. SCOPE

New mechanics: G, gg, {n}G. Count = **3**. However, `{n}G` is a parameterization of G, not a distinct command. In Vim, `G` with a count IS `{n}G`; it's the same key. The blueprint counts it as a third mechanic. As a distinct behavioral mode (line-addressed teleport vs end-of-file), it is a meaningful teaching unit. Borderline; accept as 3. **PASS (marginal).**

### 2. LINKAGE

G/gg are file-end/file-top jumps — a canonical Vim complement pair. {n}G extends to arbitrary row addressing. All three are file-coordinate jumps. Coherent. **PASS.**

### 3. FORCEABILITY — Independent Par Re-Computation

**Grid:** 15 rows × 58 cols. Entry (0,1), Exit (0,2). KS1 at (14,55), KS2 at (4,28).

**Claimed path:** `G x 5G 27h x gg l` = 1+1+2+3+1+2+1 = 11. Budget = ceil(11 × 1.4) = ceil(15.4) = **16.**

**Re-deriving par:**

Step 1: `G` (1 ks) → (14,55). KS1.
Step 2: `x` (1 ks) → collect KS1.
Step 3: Need to reach KS2 at (4,28). From (14,55):
  - `5G` (2 ks: "5"+"G"): sets row=4, col stays 55. At row 4, col 55 is a WALL (wall row except gap cols 26-28). The engine behavior for `{n}G` with a non-passable column is critical. Blueprint says "engine clips to nearest passable" or Dijkstra handles this. IF the engine sets col=55 and col 55 is wall on row 4, the move fails. The actual engine behavior must place the player at row 4, first non-blank col of that row (col 26 or 28). Then `27h` from col 55 → col 28 makes sense only if engine keeps col=55 after `5G`.

  **Ambiguity in {n}G mechanics:** The blueprint itself shows contradictory derivations (three attempts). The final claimed path has `5G` landing at col 55 of row 4 (wall), then `27h` to col 28. This requires the engine to handle wall landing by keeping the column position as-is (a "ghost" landing), allowing horizontal navigation from col 55 even though it's a wall cell. This is non-standard and engine-implementation-dependent.

  If `5G` clips col to first non-blank (col 26), then `27h` goes left to col -1 (impossible) — `h` from col 26 goes to col 25, not toward col 28. If engine clips to rightmost passable in the gap (col 28), then `27h` makes no sense. The arithmetic is inconsistent.

  **Alternative {n}G path:** From (14,55), navigate: `10k` (3 ks) to row 4, then move left `27h` (3 ks) to col 28. Total for this segment: 6 ks vs `5G 27h` = 2+3=5 ks. `{n}G` saves only 1 ks here, and the mechanism is ill-defined.

Step 4: `x` (1 ks) → collect KS2.
Step 5: `gg` (2 ks) → (0,1).
Step 6: `l` (1 ks) → (0,2) = exit.

**Recomputed par = 1+1+5+1+2+1 = 11.** Budget = **16.** (Accepts the claimed path as correct despite the ambiguity in step 3.)

**Adversarial check — G forcing:**

From (0,1) to KS1 at (14,55):
- `G` (1 ks): 1 ks. ✓
- `13j 54l` via counts: `13j` = 3 ks, `54l` = 3 ks. Total = 6 ks. **G saves 5 ks.** ✓ Strictly forced — next-best 6 ks, budget slack = 16-11=5. But 6-ks sub-path alone eats entire slack. **G is strictly forced.** ✓

**Adversarial check — gg forcing:**

From (4,28) to entry (0,1):
- `gg` (2 ks): 2 ks. ✓
- `4k` (2 ks) to row 0, then `27h` (3 ks) to col 1: total = 5 ks. **gg saves 3 ks.** ✓
- `4k ^` (2+1=3 ks) if row 0 has non-blank at col 1: same outcome, 3 ks. gg=2 ks. Saves 1 ks. Actually `4k` = 2 ks (count "4" + "k"), `^` = 1 ks. Total = 3 ks vs gg=2 ks. gg saves 1 ks.
- Budget check: if `gg` replaced by `4k ^`: path = 1+1+5+1+3+1 = 12 ks. 12 ≤ 16. **gg NOT strictly forced by budget alone.**

**FORCEABILITY DEFECT — gg:** The `4k ^` alternative costs 3 ks vs gg=2 ks. Path without gg = 12 ks ≤ budget=16. gg is cheapest but not budget-forced.

**FORCEABILITY CONCERN — {n}G mechanics ambiguity:** The blueprint shows three contradictory derivations of how `5G` interacts with a wall column. This is a blueprint defect regardless of engine behavior. The forcing argument for {n}G (saves 1 ks vs `10k`) is also within budget slack (path without {n}G = 12 ks ≤ 16).

**Verdict: FAIL — gg is cheapest but not budget-forced (path without gg = 12 ks ≤ 16); {n}G saves only 1 ks (also not budget-forced); G is strictly forced only because the alternative single-handedly exhausts the budget. The {n}G engine behavior is undefined/contradictory in the blueprint.**

**Required fix:** (a) Tighten budget to ceil(11 × 1.2) = 14 so `4k ^` (3 ks vs 2 ks) makes the gg-avoiding path = 12 > 14? No: 12 < 14 still. Need par-increasing path adjustment or budget = 12. (b) Alternatively restructure so gg return trip is longer (e.g., KS2 is farther from entry), making `gg`-alternative ≥ 5 ks to exhaust slack. (c) Resolve {n}G engine behavior definitively in the blueprint.

---

## Level 8 — The Screen Vault (`H M L`)

### 1. SCOPE

New mechanics: H, M, L. Count = **3**. PASS.

### 2. LINKAGE

H/M/L divide the screen into top/middle/bottom thirds. Canonical Vim "screen-position jump" family. No contamination. **PASS.**

### 3. FORCEABILITY — Independent Par Re-Computation (with special L analysis)

**Grid:** 11 rows × 52 cols. Passable rows 1–9 (9 rows). Entry (5,25). Exit (9,47).
KS-top (1,4), KS-mid (5,4), KS-bot (9,4).

**Claimed optimal:** `H x M x L x $` = 1+1+1+1+1+1+1 = 7. Budget = ceil(7 × 1.4) = ceil(9.8) = **10.**

**Re-deriving par:**

- H (1 ks): (5,25) → (1,4). KS-top. ✓
- x (1 ks): collect.
- M (1 ks): (1,4) → (5,4). KS-mid. ✓
- x (1 ks): collect.
- L (1 ks): (5,4) → (9,4). KS-bot. ✓
- x (1 ks): collect.
- $ (1 ks): (9,4) → (9,47) = exit. ✓

**Recomputed par = 7. Budget = 10.** Confirmed.

**H forcing:**
- H (1 ks): (5,25)→(1,4).
- Without H: `4k` (2 ks) → row 1, col stays 25; then `^` (1 ks) → col 4. Total = 3 ks. H saves 2 ks.
- Path without H: 3+1+1+1+1+1+1 = 9 ks ≤ 10. **H individually not budget-forced (9 ≤ 10).**

**M forcing:**
- M (1 ks): (1,4)→(5,4).
- Without M: `4j` (2 ks) → row 5. Col stays 4 (already at col 4 from H or ^). Total = 2 ks.
- Path without M (but using H): 1+1+2+1+1+1+1 = 8 ks ≤ 10. **M individually not budget-forced.**

**L forcing:**
- L (1 ks): (5,4)→(9,4).
- Without L: `4j` (2 ks). Path using H, M, no-L: 1+1+1+1+2+1+1 = 8 ks ≤ 10. **L individually not budget-forced.**

**Joint forcing (all three non-optimal):**
- `4k ^` (3 ks) + `4j` (2 ks) + `4j` (2 ks): extra = +2+1+1 = +4 ks. But the three x and $ are fixed. Path: 3+1+2+1+2+1+1 = **11 ks > 10**. ✓ Jointly forced.

**The designer's own analysis confirms:** any single deviation fits; only all-three-deviations blows budget. H individually skippable (9 ≤ 10). M individually skippable (8 ≤ 10). L individually skippable (8 ≤ 10). Two-of-three deviations: `3k^`+M+`4j` = 3+1+1+1+2+1+1 = 10 ≤ 10. **Even two-of-three deviations still fits budget.**

**STRICT L FORCING ANALYSIS:**

The blueprint acknowledges L is not strictly forced and analyzes fixes. Here we independently determine the minimal fix for each of H, M, L to be strictly required:

*For H to be strictly forced individually:* Need path-without-H > 10. Currently 9 ≤ 10. Need 1 more ks of penalty for the H-alternative. Options:
- Add a wall between (5,25) and col 4 of row 1 such that `^` cannot be used directly; player must take a longer horizontal path. E.g., if col 4 has a blocker requiring `0` first: `4k 0` = 3 ks. Same cost. No help.
- Increase the H alternative cost: if entry is at col 40 (instead of 25), then `4k` lands at (1,40), `^` → (1,4) still 1 ks. Same cost.
- **Real lever:** Move entry to a row other than center (e.g., row 3). Then H = (3,x)→(1,4) = still 1 ks. Without H: `2k ^` = 2+1 = 3 ks. Path = 3+1+M-cost+1+L-cost+1+1. That doesn't help H specifically.

*Minimal fix to force each of H, M, L strictly:*

The fundamental problem: with 9 passable rows and entry at row 5:
- H alternative cost: `4k` = 2 ks + `^` = 1 ks = 3 ks. H=1 ks. Δ=2.
- M alternative cost (from row 1 after H): `4j` = 2 ks. M=1 ks. Δ=1.
- L alternative cost (from row 5 after M): `4j` = 2 ks. L=1 ks. Δ=1.

For strict individual forcing, we need each Δ > budget slack. Budget slack = 10-7=3. Each Δ must be > 3, i.e., ≥4. Currently max Δ=2 (for H). None are ≥4.

To make M individually forced: need `4j`-equivalent to cost ≥5 ks. If KS-mid is at row 9 from KS-top at row 1: `8j` = 2 ks still. Count doesn't help. The only way to increase M alternative cost is to make the physical distance so large that `count-j` exceeds budget. With 9 passable rows, `8j` = 2 ks. Even 99 passable rows, `98j` = 3 ks. For M-alternative to cost 4+ ks, need `count-j` = 4 ks, which requires the count to be 3+ digits, i.e., ≥100j apart. Impractical for a dungeon room.

**Conclusion:** With the current budget formula (×1.4) and HML each costing 1 ks, no room height makes H, M, L each individually budget-forced. The `count-j` for any row difference ≤99 costs at most 3 ks (2-digit count + j). Since par=7 and budget=10 allows 3 ks of slack, and the most expensive HML alternative (H) costs 3 ks (+2 penalty), the best achievable is:

**Minimal fix for joint strict forcing:** Require 4 keystone visits such that budget tightens. Add a 4th keystone requiring `gg`-return after L, making par=9, budget=ceil(9×1.4)=13. Path without any one H/M/L adds 1–2 ks per skip × 4 forced uses. Still insufficient individually.

**True minimal fix:** Reduce budget multiplier to 1.14 for this level only, giving budget=ceil(7×1.14)=8. Then:
- Without any single H/M/L: path ≥ 8 ks = budget, meaning path = 9 > 8 fails. But wait: using H and M and `4j` instead of L: 1+1+1+1+2+1+1=8. 8 ≤ 8 ties. Still not strictly failed.
- Budget=7 (multiplier=1.0): only the par path works. But budget < par+1 is too tight (no error tolerance).

**The designer's self-admission stands: L cannot be strictly individually forced with standard budget formula. The blueprint documents this as a known weakness.** The only practical fix is a second L-gated door (as suggested in the blueprint) that doubles the L-usage, making skipping L cost 2×1=2 extra ks, and the total H+M+2L path has par=9, budget=13, two-L-skip path = 9+2=11 ≤ 13 (still fits). Three-skip path = 9+2+2+2=15 > 13. Joint forcing with 3 skips.

**Verdict: FAIL — L (and M, H individually) are not strictly budget-forced. The best achievable is joint forcing (all-three-skip exceeds budget by 1 ks). The blueprint acknowledges this defect. No simple room-height fix resolves it with standard ×1.4 budget formula.**

**Minimal concrete fix:** Use a two-pass design with a second descent. After collecting all 3 KS, the exit is above KS-top. Player must use `H` again to return (making H appear twice in the optimal path). Par = `H x M x L x H $` = 8. Budget = ceil(8×1.4) = 12. Without first H: `4k^`=3 extra. Without L: `4j`=1 extra. Without return-H: `8j^`=3 extra. Skipping return-H + L: 3+1=4 extra → path=12 = budget (tie still). Add wall between KS-bot and exit top area to require M on return: H x M x L x M H $ → par=9, budget=13. Still "jointly forced 3-skip" but individual forcing still elusive. Accept two-pass H-return fix as best achievable; document L as "demonstrated, jointly forced."

---

## Level 9 — The Runic Archives (`} { ) (`)

### 1. SCOPE

New mechanics: `}` and `{` (paragraph family), `)` and `(` (sentence family). Count = **4 commands, 2 families.** The blueprint argues 2 families = 2 mechanics ≤ 3. This is a charitable reading: by the spec, mechanics are counted by family/concept. **BORDERLINE PASS** — 2 families fits ≤3. However, the LEVELS_PLAN.md explicitly flags this as a linkage concern: "split off `) (`." The reviewer notes this is a genuine scope/linkage stress.

### 2. LINKAGE

`}` and `{` are vertical paragraph jumps. `)` and `(` are horizontal sentence jumps. The dungeon metaphor treats them as "structural jumps over content chunks" — different axes, different semantics. The LEVELS_PLAN.md explicitly flags: "define sentence metaphor or split off `) (`." The blueprint defines the sentence metaphor (D5 resolution) but the two families remain different in kind:
- Paragraph = vertical jump (row-axis), skipping void barriers
- Sentence = horizontal jump (col-axis), skipping wall-blocked segments

These are NOT the same family. In Vim, paragraph and sentence motions are related as "text-block navigation," but in-dungeon they map to completely different terrain types. **The linkage is mixed: vertical structural jump vs horizontal structural jump with different terrain primitives.**

LEVELS_PLAN.md: "10/13 Runic Archives `} { ) (` `) (` has **no defined dungeon metaphor**; two families — Linkage — Med." This audit flag is not resolved by the blueprint's D5 definition; D5 only defines the sentence metaphor, not the cross-family linkage.

**Verdict: FAIL — Mixed linkage. `}` / `{` (paragraph, vertical, void-barrier) and `)` / `(` (sentence, horizontal, wall-segment) are two distinct families in both Vim semantics and dungeon metaphor. Teaching them in one level violates the linkage principle.**

**Required fix:** Split into two levels:
- Level 9a: `} {` (paragraph jumps; void barriers)
- Level 9b: `) (` (sentence jumps; wall-segmented corridors)
This also reduces scope per level to 2 mechanics each.

### 3. FORCEABILITY — Independent Par Re-Computation

**Grid:** 22 rows × 62 cols. Entry (0,1). Exit (20,49).

**Claimed path:** `} } j 3)` = 1+1+1+2 = 5. Budget = ceil(5 × 1.4) = ceil(7) = **7.**

**Re-deriving par:**

- `}` (1 ks): row 0 → row 9 (blank row after void barrier A rows 3–8). ✓
- `}` (1 ks): row 9 → row 19 (blank row after void barrier B rows 12–18). ✓
- `j` (1 ks): row 19 → row 20. Col stays at 1. ✓
- `3)` (2 ks): col 1 → S1-start col 2 → S2-start col 23 → S3-start col 49 = exit. ✓

Wait: `3)` from col 1. First `)` lands at the start of the first sentence in S1 (col 2, since S1 begins at col 2 and row 19 blank-row descent puts player at col 1). Second `)` lands at S2-start col 23 (after `.` in S1). Third `)` lands at S3-start col 49 (after `!` in S2) = exit. Cost = "3" + ")" = 2 ks. ✓

**Recomputed par = 5. Budget = 7.** Confirmed.

**} forcing:**
- `}` is forced by void barriers (rows 3–8): any `j`-based movement into void = death. Infinite cost without `}`. ✓ **Strictly forced.**

**) forcing:**
- `)` is forced by wall gaps at cols 11–22 and 37–48: no horizontal motion can cross these. `l`, `w`, `W`, `e`, `E`, `$` all blocked. `)` finds next sentence start. ✓ **Strictly forced.**

**Adversarial search for cheaper path:**
- Row 19 is narrowed (cols 11-60 walled). After descending to row 20, player is at col 1 (leftmost passable). `$` on row 20 would go to col 60 (rightmost passable after S3), passing the exit. But `$` still can't cross the wall gaps — `$` on row 20 would go only to col 10 (end of S1, since cols 11-22 are walled). So `$` reaches col 10, not col 49. Cannot bypass walls with `$`.
- `G` or `gg`: not taught yet in Act II's own internal ordering... but taught in Level 7. Could `G` skip to the exit? `G` jumps to last passable row's first non-blank. Last passable row is row 20; first non-blank = col 1 (the entry of row 20). That's S1, not the exit. Not useful.
- Any taught motion short of `)` cannot cross the wall gaps on row 20. **Strictly forced.** ✓

**Forceability verdict: PASS** (despite linkage failure).

---

## Level 9.1 — The Warden Surveyor (Boss)

### 1. SCOPE

Boss — scope principle applies differently: the boss exercises previously taught commands, not new ones. **N/A.**

### 2. BOSS PLACEMENT

- Numbered 9.1: caps Act II. ✓
- Positioned after Level 9 (the last Act II teaching level). ✓
- New boss (the Warden Surveyor) — not recycling a prior boss. ✓

### 3. IMMUNITY TO UNTAUGHT COMMANDS

Blueprint states: "immune to Act I motions (`h j k l` `w b e` `f F t T` `; ,` `^ $ 0` `[count]`)." Act II motions required per phase. **PASS — immune mechanism documented.** ✓

However: Acts I commands are h/j/k/l, ^/$/ 0, count, w/b/e, f/F/t/T and ;/,. The immunity list covers all of these. ✓

But: Phase 3 (File Teleport) says "G/gg" is forced, yet G/gg require basic navigation `h/j/k/l` to reach the warden after teleporting. The blueprint says Act I motions are immune but the player still needs hjkl for micro-navigation. **This is a contradiction: if hjkl are immune (unusable), the player cannot navigate at all within each phase.** The immunity must mean "immune to hjkl used as ATTACK actions," not that hjkl are completely disabled. Clarification needed.

### 4. ONE PHASE PER ACT II MOTION

| Phase | Motion | Status |
|---|---|---|
| 1 | W/B/E | Act II Level 5 family ✓ |
| 2 | ge/gE | Act II Level 6 family ✓ |
| 3 | G/gg | Act II Level 7 family ✓ |
| 4 | H/M/L | Act II Level 8 family ✓ |
| 5 | `}` / `{` / `)` / `(` | Act II Level 9 family ✓ |

5 phases, 5 Act II families. ✓

**Phase count:** 5 phases for 5 Act II levels. Spec says "one phase per Act II motion." The spec is interpreted as "one phase per Act II family." ✓

### 5. BOSS FORCEABILITY

Each phase claims Act I-only paths cost infinity. Spot-check:
- Phase 1: Code-WORD corridor forces W/B/E; `hjkl` would require crossing code-text boundaries — but `h/j/k/l` can navigate any CORRIDOR regardless of rune content. The forcing argument "only W/B/E reach the phase trigger" requires that the phase trigger (seal_door D1) is accessible only via W/B/E navigational mechanics, not just movement. **If the trigger is a door at col 50 and the player can `49l` to reach it, hjkl-only navigation works.** The forcing must come from budget (49l = 3 ks vs 4W = 2 ks), not physical impossibility.

- With Act I-motion immunity meaning "attacks don't work" (not movement disabled), the budget-forcing argument applies: hjkl-only path costs more than Act II-motion path, exceeding per-phase budget. The overall budget of 41 ks would be exceeded by hjkl-only traversal. Plausible but requires the per-phase Dijkstra to confirm.

**BOSS VERDICT: CONDITIONAL PASS.** The immunity mechanism ambiguity (hjkl-disabled vs hjkl-non-attacking) is a defect. The phase structure is correct (one per Act II family). Flagged for implementation clarification.

**Required clarification:** Define "immune to Act I motions" as: the warden's shield/seal cannot be opened by Act I-motion-based approaches; Act II motions are required to clear each phase, regardless of hjkl availability for micro-navigation.

---

## Per-Level Summary

### Level 5 — The WORD Forge

**Recomputed par = 10. Budget = 14.**

| Principle | Verdict | Finding |
|---|---|---|
| Scope | PASS | 3 mechanics (W, B, E) |
| Linkage | PASS | WORD-motion family |
| Forceability | FAIL | w/b with count-prefixes may tie W/B at 2 ks per corridor; w/b/e-only path ≈11–12 ks ≤ budget 14 |
| — | — | — |

**Defect:** Code-group density insufficient to guarantee `w`-boundary-count > 3 per W-hop, allowing count-w to match W in keystroke cost.

**Concrete fix:** Guarantee ≥5 word-boundary transitions per code group (e.g., `a.b+c*d` = 6 w-presses per 1 W-press). With 4 groups, `w`-only path ≥ `20w` = 3 ks vs `4W` = 2 ks per corridor. Ensure all three corridors have this property. Then w-only path = 3+2+3+2+3 = 13 ks ≤ 14 (still fits!). Budget must be tightened to ceil(10 × 1.2) = 12 to force the issue. OR add a 5th group per corridor so `25w` = 3 ks difference accumulates: total w-only = 3+2+3+2+3 = 13 > 12.

---

### Level 6 — The Backward Vaults

**Recomputed par = 18. Budget = 26.**

| Principle | Verdict | Finding |
|---|---|---|
| Scope | PASS | 2 mechanics (ge, gE) |
| Linkage | PASS | Backward-end word/WORD family |
| Forceability | FAIL | Budget slack = 8 ks; ge/gE-avoiding path (using 33h and 3ge) costs only 4 extra ks ≤ slack |
| — | — | — |

**Defect:** The 8-ks budget slack (budget=26 vs par=18) allows skipping ge at C4 (+2 ks via 33h) and gE at C6 (+2 ks via 3ge/19h), yielding total path ≤ 22 ks ≤ 26.

**Concrete fix:** Tighten budget to ceil(18 × 1.2) = 22. Then ge-skip path = 18-1+3 = 20 ≤ 22 (still fits). The only effective fix is to make ge/gE-alternatives physically impossible (wall the h-count route at C4, force only ge/gE to reach the gap) or restructure so the alternative costs ≥9 ks more per use. At C4: if there is no open horizontal corridor from col 38 to col 5 except via backward-word-end motion (i.e., intervening walls block h-count but not ge/gE), then ge/gE are strictly forced by terrain. Implement intermediate walls in C4 row 7 between cols 6–37, leaving only the word-cluster path traversable by ge/gE.

---

### Level 7 — The File Vaults

**Recomputed par = 11. Budget = 16.**

| Principle | Verdict | Finding |
|---|---|---|
| Scope | PASS | 3 mechanics (G, gg, {n}G) — marginal |
| Linkage | PASS | File-coordinate jump family |
| Forceability | FAIL | gg-avoiding path = 12 ks ≤ 16; {n}G saves only 1 ks (path without = 12 ks ≤ 16); {n}G mechanics ambiguous/contradictory in blueprint |
| — | — | — |

**Defect:** Three contradictory derivations of `5G` behavior in the blueprint. gg individually skippable (12 ks ≤ 16). {n}G individually skippable (12 ks ≤ 16). Only G is strictly forced (G-avoiding path ≥17 ks > 16).

**Concrete fix (gg):** Move KS2 to row 13 (near bottom), requiring gg to cover ~13 rows. Then gg-alternative = `13k` = 3 ks, `l` to exit = path = 1+1+5+1+3+1 = 12 ≤ 16. Still insufficient. Real fix: add a second keystone requiring gg at the top, making par=13, budget=19, gg-alternative = 3+3=6 extra ks → path without gg = 19 > 19? No: 13+6=19 = budget (tie). Use budget multiplier 1.3: budget=17. Path without gg = 19 > 17. gg forced.

**Concrete fix ({n}G):** Resolve engine behavior in blueprint and in `motion.py`: `{n}G` sets `row = n-1` and clamps `col` to first-non-blank of that row (standard Vim behavior). This gives a concrete and unambiguous mechanic. Recompute par accordingly.

---

### Level 8 — The Screen Vault

**Recomputed par = 7. Budget = 10.**

| Principle | Verdict | Finding |
|---|---|---|
| Scope | PASS | 3 mechanics (H, M, L) |
| Linkage | PASS | Screen-thirds family |
| Forceability | FAIL | H, M, L each individually skippable (single-skip path ≤ 9 ks ≤ 10); two-of-three skips = 10 ks = budget (tie); only all-three-skip (11 ks > 10) truly fails |
| — | — | — |

**Defect:** L (and H, M) not individually or pairwise budget-forced. Only jointly forced when all three alternatives are chosen simultaneously. Single-skip path fits budget.

**Concrete fix (minimal):** Two-pass layout. After collecting KS-bot (row 9) via L, the exit is at row 1 (top), requiring H again. Path = `H x M x L x H $` = 8 ks. Budget = ceil(8×1.4) = 12. L-skip: `4j` instead of L = 8-1+2 = 9 ≤ 12. Still not forced. **Better:** 3-pass with locked door at each KS requiring sequence H→M→L→H→M→L (par=13, budget=19). Two L-skips: +2 ks. Still ≤19. **True fix:** Accept joint forcing as the design intent (documented) and add a note that this level "demonstrates" rather than "strictly forces" each command individually. No room-height fix works with ×1.4 budget — formally proven above.

---

### Level 9 — The Runic Archives

**Recomputed par = 5. Budget = 7.**

| Principle | Verdict | Finding |
|---|---|---|
| Scope | BORDERLINE PASS | 4 commands in 2 families; treated as 2 mechanics |
| Linkage | FAIL | `} {` (vertical paragraph, void-barrier) and `) (` (horizontal sentence, wall-segment) are different families with different dungeon primitives |
| Forceability | PASS | `}` forced by void barriers (infinite cost otherwise); `)` forced by wall gaps (infinite cost otherwise) |
| — | — | — |

**Defect:** Mixed linkage — paragraph and sentence jumps use different terrain types and different axes. LEVELS_PLAN.md explicitly flags this as a medium-severity issue.

**Concrete fix:** Split into two levels:
- Level 9: `} {` — "The Void Rift" — paragraph jumps, void barriers, vertical axis.
- Level 9.5 (or renumber): `) (` — "The Sentence Corridor" — sentence jumps, wall-segmented rows, horizontal axis.
Both levels individually have 2 mechanics, coherent families, and terrain-forced commands.

---

### Level 9.1 — The Warden Surveyor (Boss)

**Par ≈ 29. Budget = 41.**

| Principle | Verdict | Finding |
|---|---|---|
| Scope (boss) | PASS | N/A — exercises taught commands |
| Boss placement | PASS | x.1 numbering, caps Act II |
| Immunity | CONDITIONAL PASS | Immunity mechanism ambiguous: "Act I motions immune" contradicts hjkl being needed for micro-navigation |
| One phase per motion | PASS | 5 phases, 5 Act II families (W/B/E, ge/gE, G/gg, H/M/L, `}{)(`) |
| — | — | — |

**Defect:** The immunity claim "immune to Act I motions (`h j k l`...)" is contradicted by the need for hjkl micro-navigation within each phase. If hjkl are truly disabled, the player cannot navigate within phases. If hjkl are allowed for movement but not for "attacks/phase triggers," this must be stated explicitly.

**Concrete fix:** Restate immunity as: "The Warden Surveyor's phase seals and shields cannot be cleared by Act I motion-based attacks. Only Act II structural motions can trigger phase transitions. `hjkl` remain available for micro-positioning within each phase corridor."

---

## Overall Verdict

**Total FAIL count: 5** (Level 5 Forceability, Level 6 Forceability, Level 7 Forceability, Level 8 Forceability, Level 9 Linkage). Boss is CONDITIONAL PASS.

### Prioritized Fix List

1. **(CRITICAL) Level 9 — Split `} {` and `) (` into two levels.** Linkage failure is a structural blueprint defect that affects act numbering and boss design. Splitting requires renumbering 9.1 to 10.1 (or inserting 9.5).

2. **(HIGH) Level 6 — Add intermediate walls in C4 row 7 to make ge/gE-alternatives physically impossible.** Budget slack alone does not force the commanded motions. Terrain-based forcing is the correct mechanism.

3. **(HIGH) Level 5 — Guarantee ≥5 word-boundary transitions per code group** (redesign groups like `a.b+c*d`) AND tighten budget to ceil(10 × 1.2) = 12 to ensure w-only paths exceed budget.

4. **(HIGH) Level 7 — Resolve {n}G engine behavior definitively** (standard Vim: set row, clamp col to first-non-blank). Restructure layout so gg-alternative ≥5 ks (move KS2 location or add a return-trip requirement).

5. **(MEDIUM) Level 8 — Accept joint-only forcing as documented; add explicit "demonstrated but not individually forced" label in blueprint.** If strict individual forcing is desired, implement two-pass layout with H required on return trip, and document that this is the best achievable under ×1.4 budget formula.

6. **(LOW) Level 9.1 — Clarify immunity mechanism** in blueprint text: specify that hjkl remain functional for micro-navigation; only phase triggers require Act II motions.

---

*Reviewed against:*
- `/home/ch/Vimny/blueprints/act_2.md`
- `/home/ch/Vimny/LEVELS_PLAN.md`
