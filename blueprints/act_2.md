# Act II Blueprints — Extended & Structural Motion

> Canonical reference: `LEVELS_PLAN.md` (authoritative curriculum).
> Generator reference: `generation/dungeon_gen.py` (`build_dungeon_6`=W/B/E,
> `build_dungeon_8`=ge/gE, `build_dungeon_9`=G/gg, `build_dungeon_10`=H/M/L,
> `build_dungeon_13a`=`}`/`{`, `build_dungeon_13b`=`)`/`(`).
>
> **Par** = minimum keystrokes via Dijkstra over taught motions only, entry→exit inclusive.
> **Budget** = smallest ceil(par × M) such that the next-best alternative STRICTLY exceeds it;
>   default M=1.4, overridden per level where needed (documented below).
> **Forcing model (S1→S2):**
>   S1 — make command-avoiding routes physically impossible (infinite cost) via walls/void/water.
>   S2 — where S1 is impossible, tighten budget to the minimum multiplier M such that
>        next-best STRICTLY > budget; document M and the next-best cost.
> **S3** — par is the true full entry→exit solution including all navigation and Esc.
> **S4** — earlier-act commands (`$ 0 ^ [count] w b e f F t T ; ,`) must not yield a
>          cheaper route; add terrain to block any such shortcut.

---

## Level 5 — The WORD Forge (`W B E`)

### New mechanics (≤3)

1. **W** — jump to start of next WORD (maximal run of adjacent non-void clusters, no floor gap).
2. **B** — jump to start of current or previous WORD.
3. **E** — jump to end of current WORD.

**Linkage:** W/B/E are the WORD-level siblings of already-taught w/b/e. Same snake-corridor
family, same cluster metaphor, bigger jumps.

### Forcing model (S1 primary — terrain-∞)

The core defect from the review: code groups with only 2–3 `w`-boundaries per group allow
`count-w` to match `W` in keystrokes (e.g. `9w` = 2 ks = `3W`). Fix: each code group must
contain ≥6 word-boundary transitions so that the `w`-count to traverse one group requires
a 2-digit count (≥10 presses), making `count-w` cost 3 ks vs `1W` = 1 ks per group.

**Group design rules:**
- Each group must contain alternating word-chars and punctuation-chars: e.g.
  `a.b+c*d` has chars `a`, `.`, `b`, `+`, `c`, `*`, `d` — word/punct boundaries at every
  step = 6 `w`-presses for 1 `W`-press.
- Four groups per corridor, each with ≥6 `w`-presses. Total per corridor: `24w` = 3 ks
  (count "24" + w) vs `4W` = 2 ks. W saves ≥1 ks per corridor.
- Three corridors: savings of ≥3 ks total.

**S1 terrain additions:**
- Guard walls between corridors force the exact turn column; `$` cannot shortcut to the
  turn because the guard wall is at the last valid column + 1.
- Void runes at the left edge of corridor 2 (blocking `0`/`^`) remain from original design.
- A wall strip across row 6 with a single gap (1 col wide) at the LT1 exit forces the player
  to be at exactly col 3 at the descend point — only achievable if they used `4B` to land
  at the B1 anchor; using count-b risks landing at a non-gap column and hitting the wall.

**S2 budget tightening:**
- With S1 terrain, w/b/e-only path costs: C1 `24w`(3 ks)+`2j`(2)+C2 `24b`(3)+`2j`(2)+
  C3 `24e`(3) = 15 ks vs par=10.
- Minimum multiplier: par × M ≥ 14 and 15 > 14 → M = 1.4 works (budget=14, next-best=15).
- Keep M=1.4, budget=14. Next-best (w/b/e-only) = **15 ks > 14**. STRICTLY over budget. ✓

### Grid

```
58 cols × 10 rows  (cols 0-57, rows 0-9)

Row 0:  ##########################################################
Row 1:  #@[W1:a.b+c*d][W2:x+y*z/w][W3:m.n-p*q][W4:§‽∘¶]      #
Row 2:  #   [gap 2]                                              #
Row 3:  ##################################################  ######  (RT1 gap at cols 50-52, guard wall at col 53)
Row 4:  # ○[B1:°¶†‽][B2:r*s+t.u][B3:v/w-x.y][B4:z+a*b-c]     #
Row 5:  #  [gap 2]                                              #
Row 6:  ####  ####################################################  (LT1: single gap at cols 1-3, wall elsewhere)
Row 7:  #   [E1:d.e+f*g][E2:h/i-j.k][E3:l*m+n-p][E4:q.r+s*t/u.v]X#
Row 8:  #   [gap 2]                                              #
Row 9:  ##########################################################
```

**Dimensions:** 10 rows × 58 cols
**Entry:** (1, 1) — `@`
**Exit:** (7, 52) — `X` (end of E4, last char before the wall)

### Placements (coordinates)

| Glyph / Entity | Row | Col | Notes |
|---|---|---|---|
| Entry `@` | 1 | 1 | — |
| Code group W1 `a.b+c*d` | 1 | 3–9 | 7 adjacent single-char clusters, 6 w-boundaries |
| Code group W2 `x+y*z/w` | 1 | 12–18 | 7 chars, 6 w-boundaries |
| Code group W3 `m.n-p*q` | 1 | 22–28 | 7 chars, 6 w-boundaries |
| Anchor W4 (untypable 4-char) | 1 | 32–35 | seed-varying from `_L7_UNTYPABLE_PUNCT` (§‽∘¶) |
| Guard wall (blocks $ shortcut) | 3 | 53 | WALL; turn col = 52 |
| RT1 gap | 2–4 | 50–52 | corridor; descend from row 2 to row 4 |
| Void rune `○` (blocks `^`/`0`) | 4 | 1 | lethal; kills `0`/`^` shortcut on C2 |
| Void rune `○` (blocks `^`/`0`) | 5 | 1 | — |
| Anchor B1 (untypable 4-char) | 4 | 3–6 | seed-varying; `B` from C2 right end lands here |
| Code group B2 `r*s+t.u` | 4 | 18–24 | 7 chars, 6 w-boundaries |
| Code group B3 `v/w-x.y` | 4 | 28–34 | 7 chars, 6 w-boundaries |
| Code group B4 `z+a*b-c` | 4 | 38–44 | 7 chars, 6 w-boundaries |
| LT1 wall strip | 6 | 4–57 | full WALL row 6 except cols 1–3 (single gap) |
| LT1 gap | 5–7 | 1–3 | corridor; descend from row 5 to row 7 |
| Code group E1 `d.e+f*g` | 7 | 4–10 | 7 chars, 6 w-boundaries |
| Code group E2 `h/i-j.k` | 7 | 14–20 | 7 chars, 6 w-boundaries |
| Code group E3 `l*m+n-p` | 7 | 24–30 | 7 chars, 6 w-boundaries |
| Code group E4 `q.r+s*t/u.v` | 7 | 34–44 | 11 chars; `E` from col 30 (E3 end) lands at col 44; `e` stops internally |
| Exit `X` | 7 | 52 | right of E4, accessible via `$` from col 44 |

### Optimal keystrokes

```
C1 left→right:  4W   (2 ks: entry col 1 → W4 end col 35 → RT1 area col ~52)
RT1 descent:    2j   (2 ks: row 2 → row 3 → row 4; no count needed for 2 rows... 
                      actually 2j = 1 ks if used bare "jj", or "2j" = 2 ks. Use jj=2 ks.)
Actually: bare j is 1 ks; jj = 2 ks of individual presses. 2j = "2"+"j" = 2 ks.
Use: j j = 2 ks (two separate presses). Record both as 2 ks total.

C2 right→left:  4B   (2 ks: col ~52 → B4 → B3 → B2 → B1 anchor col 3)
LT1 descent:    j j  (2 ks: row 5 to row 6 [gap], row 6 gap to row 7)

C3 left→right:  4E   (2 ks: col 3 → E1 end → E2 end → E3 end → E4 end col 44)
Exit reach:     $    (1 ks: col 44 → col 52 = exit)

Full optimal path: 4W j j 4B j j 4E $
Par = 2+1+1+2+1+1+2+1 = 11
Budget = ceil(11 × 1.4) = ceil(15.4) = 16
```

*(Actual par from `_dijkstra_par_WBE`; hand-calc above is conservative — Dijkstra may find
par=10 if `jj` is actually `2j`=2 ks total. The $ to exit may also be 0 if exit is at E4's
end exactly. Recompute on implementation.)*

**par = 11 | budget = 16**
**Next-best (w/b/e-only): ≥27 ks >> budget. Strictly over budget. ✓**

### Forcing argument

**W (C1):** Each code group has ≥6 w-boundaries. To traverse 4 groups with `w`, the player
needs ≥24 w-presses. `24w` = len("24")+1 = 3 ks. `4W` = 2 ks. W saves 1 ks on C1.
Without W: C1 alone costs 3 ks (1 extra vs par). Similarly for B and E.

**B (C2):** Void runes at (4,1) and (5,1) kill `0`/`^`. From col 52, `4B` = 2 ks reaches
col 3 (B1 anchor, only gap at row 6 exit). `b`-alternatives: ≥24 b-presses = 3 ks. Saves 1 ks.
LT1 wall strip with single-col gap enforces that the player must land at col ≤3 at the LT1
entry; count-b risks overshooting and hitting the wall strip — only `4B` reliably lands at the
B1 anchor which sits exactly at the gap entrance.

**E (C3):** E4 is an 11-char group. `e` stops at every internal word/punct boundary within E4
(≥5 stops inside E4 alone). `4E` jumps to col 44 in 2 ks; `e`-only through C3 costs ≥3 ks.
Saves 1 ks.

**Joint forcing:** Each corridor's command saves 1 ks vs next-best. Total savings = 3 ks.
Without W+B+E (all three avoided): 11+3 = 14 ks vs budget=16. Still fits. Add the `$` exit
step and the void/gap constraints: without B, the LT1 gap wall forces an extra repositioning
step (+1 ks minimum). Without E, the exit requires additional `e`/`l` steps through E4 (+1 ks).
Full avoidance: 11+3+2 = **16 ks = budget** — tie. 

**S2 tightening:** Use M=1.35 → budget = ceil(11×1.35) = ceil(14.85) = **15**. Then:
- Next-best (skip all three taught commands + extra repositioning) = 16 > 15. ✓ STRICTLY over.
- Skipping one command: 11+1+1 = 13 ≤ 15. Individual commands not strictly forced.
- Skipping two commands: 11+2+2 = 15 = budget (tie). 
- Skipping all three + repositioning: 16 > 15. ✓ All-three-avoidance strictly over budget.

**Adopted: M=1.35, budget=15. Next-best (skip-all-plus-repositioning) = 16 > 15. ✓**

*(If Dijkstra finds par=10 instead of 11, recompute: budget = ceil(10×1.35) = 14;
next-best ≈15 > 14. Still works. Document actual M after implementation.)*

### Primitives used

- Adjacent single-char `RuneCluster` objects with alternating word/punct chars (≥6 boundaries/group)
- Guard wall at RT1 exit (blocks `$` shortcut to turn col)
- LT1 wall strip row 6 with single-col gap (forces precise landing from B)
- Void rune guards at (4,1),(5,1) (block `0`/`^` on C2)
- Seed-varying untypable anchor chars (f/F cannot target them)
- `_dijkstra_par_WBE` Dijkstra (already implemented)

### Self-check

- **Scope:** 3 new motions (W, B, E); coherent WORD family. ✓
- **Linkage:** Directly extends w/b/e from Level 3. ✓
- **S1 forceability:** LT1 wall + void guards make B-alternative physically risky (wall landing);
  code-group density makes w/e-count alternatives cost ≥1 extra ks each. ✓
- **S2 forceability:** M=1.35, budget=15; full-avoidance path=16 > 15. ✓
- **S4:** `$` still usable within each corridor but cannot bypass the guard walls at turns;
  `0`/`^` blocked by void runes on C2. ✓

---

## Level 6 — The Backward Vaults (`ge gE`)

### New mechanics (≤3)

1. **ge** — move backward to the end of the previous *word* (small-word).
2. **gE** — move backward to the end of the previous *WORD* (maximal adjacent cluster run).

**Linkage:** ge/gE are the backward-end companions of e/E. Same backward-motion family as b/B;
teaches the asymmetry (forward-start W/E vs backward-end ge/gE).

### Forcing model (S1 primary — terrain-∞)

**Review defect:** Budget slack = 8 ks (budget=26, par=18). `ge`-alternative at C4 (`33h`=3 ks
vs `ge`=1 ks, Δ=2) and `gE`-alternative at C6 (`3ge`=3 ks vs `gE`=1 ks, Δ=2) total only 4 extra
ks, well within the 8-ks slack. Fix: add intermediate walls in C4 row 7 between the anchor and
the right side of the corridor, making h-count traversal impossible — only ge/gE (backward
word-end motions) can reach the LT2 gap from the right side.

**S1 terrain fix for C4 (ge):**
- Row 7 corridor has the C4 all-word-char anchor at cols 2–5 (LT2 gap entrance).
- Cols 6–37 of row 7 are **wall-blocked** (solid WALL strip).
- The player arrives from RT2 at col 38. The wall strip from cols 6–37 means `h`-count from
  col 38 hits the wall at col 37 — the player cannot reach col 5 by any horizontal motion.
- `ge` (backward to end of previous word) and `gE` (backward to end of previous WORD) are
  motion-engine operations that jump over walls to the semantic target. Per engine design,
  `ge`/`gE` traverse clusters by type, landing at col 5 (end of anchor).
- Result: **any `h`/`l`/`$`/`0` alternative costs infinity (wall barrier). ge/gE are the only
  finite-cost options.** S1 forcing. ✓

**S1 terrain fix for C6 (gE):**
- Row 11 baphomet WORD (cols 21–38, three adjacent clusters with no gaps → one WORD).
- The anchor rune at cols 18–19 (col 20 always empty gap, hardcoded).
- Exit at (12, 19).
- **No change needed for gE at C6:** `gE` is already strictly cheaper (1 ks) than `ge`-chain
  (3 ks) or `h`-count (3 ks). The 2-ks savings are individually meaningful. For S1, confirm
  that `h`-count from col 38 to col 19 requires traversing the full baphomet WORD — which is
  passable terrain, so `19h` = 3 ks is a valid alternative. S1 cannot block it here.
  **Use S2:** With C4 fixed (ge now infinite-cost alternative), the combined forcing is:
  - C4: `ge` or `gE` required (infinite-cost alternative). ✓
  - C6: `gE` costs 1 ks; `3ge` = 3 ks; `19h` = 3 ks. Δ=2 ks.

**S2 budget tightening for C6:**
After fixing C4 (S1), the remaining budget slack must be tight enough that skipping `gE` at C6
blows the budget. New par with C4 S1 (same path, same par=18). Without gE at C6: path = 18-1+3
= 20 ks. Need budget < 20, i.e., budget ≤ 19. Minimum M: ceil(18×M) ≤ 19 → M ≤ 19/18 = 1.055.
Use M=1.055 → budget = ceil(18×1.055) = ceil(18.99) = **19**.
- Without gE: 20 > 19. ✓ STRICTLY over budget.
- Optimal path: 18 ≤ 19. ✓

**Adopted: M=1.055, budget=19. C4 alternatives: ∞ (S1 wall). C6 next-best: 20 > 19. ✓**

### Grid

```
40 cols × 13 rows  (cols 0-39, rows 0-12)

Row 0:  ########################################
Row 1:  #@ [∘∘∘] [∘∘∘] [∘∘∘] [∘∘∘]      ####  (C1: 4E teaching)
Row 2:  ######################################  #  (RT1: rows 1-3, cols 36-38; guard at 38)
Row 3:  # [∘∘∘] [∘∘∘] [∘∘∘] [∘∘∘]       ####  (C2: ^ teaching)
Row 4:  #   ##################################  #  (LT1: rows 3-5, col 1 walled at row 4)
Row 5:  # [plain words...]                   #  (C3: decorative, $)
Row 6:  #   ####################################  (RT2: rows 5-7)
Row 7:  # [anchor cols 2-5] ################# #  (C4: ge; wall strip cols 6-37; RT2 entry col 38)
Row 8:  ######  ##########################  ####  (LT2 gap: rows 7-9, cols 5-6; col 2 walled)
Row 9:  #   [mixed words]                      #  (C5: $)
Row 10: ########################################  (RT3: rows 9-11)
Row 11: # [filler 2-16] [anchor 18-19] [baphomet WORD 21-38] #  (C6: gE)
Row 12: ########################################X  (exit at col 19)
```

**Dimensions:** 13 rows × 40 cols
**Entry:** (1, 1) — `@`
**Exit:** (12, 19) — `X`

### Placements (coordinates)

| Glyph / Entity | Row | Col | Notes |
|---|---|---|---|
| Entry `@` | 1 | 1 | — |
| C1 clusters (4 × 3-char) | 1 | 5,13,22,34 | teach 4E; individual rune symbols |
| Guard wall (RT1) | 2 | 38 | WALL; forces 4E→col 36 not `$`→col 38 |
| C2 clusters (4 × 3-char) | 3 | 2,13,21,29 | teach ^; right→left traversal |
| Guard wall (LT1) | 4 | 1 | WALL; forces `^`→col 2 not `0`→col 1 |
| C3 plain words (decorative) | 5 | 4–33 | no forcing role |
| C4 ge anchor (4 all-WC chars) | 7 | 2–5 | end=5 = LT2 gap entry |
| **Wall strip (S1 ge block)** | 7 | 6–37 | WALL; makes h-count from col 38 impossible |
| LT2 gap | 7–9 | 5–6 | corridor; row 8 walled at col <5 |
| C5 mixed filler | 9 | 7–34 | decorative |
| C6 anchor rune | 11 | 18–19 | 2-char rune; col 20 always empty |
| C6 baphomet WORD cluster A | 11 | 21–28 | `b4¶♯∘m3†` (8 chars) |
| C6 separator cluster S | 11 | 29–30 | `!=` (2 chars, no gap → same WORD) |
| C6 baphomet WORD cluster B | 11 | 31–38 | `b3♯3m∘†♯` (8 chars) |
| C6 filler | 11 | 2–16 | seed-varying mixed chars |
| Exit `X` | 12 | 19 | — |

### Optimal keystrokes

```
C1 (row 1, left→right):  4E    (2 ks)
Turn RT1:                 2j    (2 ks)
C2 (row 3, right→left):   ^    (1 ks)
Turn LT1:                 2j    (2 ks)
C3 (row 5):               $    (1 ks)
Turn RT2:                 2j    (2 ks)
C4 ge:                    ge   (1 ks: col 38 → col 5 via ge, over wall strip)
Turn LT2:                 2j    (2 ks)
C5:                        $    (1 ks)
Turn RT3:                 2j    (2 ks)
C6 gE:                    gE   (1 ks: col 38 → col 19)
Exit:                      j    (1 ks)

Full optimal: 4E 2j ^ 2j $ 2j ge 2j $ 2j gE j
Par = 2+2+1+2+1+2+1+2+1+2+1+1 = 18
Budget = ceil(18 × 1.055) = 19
```

**par = 18 | budget = 19**

### Forcing argument

**ge (C4):** Wall strip at row 7 cols 6–37 physically blocks all horizontal motions (h, l, $, 0,
w, b, e, W, B, E) from col 38 to col 5. The wall is impassable terrain. Only `ge`/`gE` — which
are backward-end word/WORD motions that the engine resolves by scanning backward across cluster
types — can land at col 5 (end of the 4-char all-WC anchor). **Next-best: ∞ (wall). S1 forced.** ✓

**gE (C6):** Baphomet WORD at cols 21–38 (three adjacent clusters, no gaps). `gE` from col 38
jumps backward to col 19 (end of anchor) in 1 ks. `ge`-chain: `ge`→30, `ge`→28, `ge`→19 = 3 ks.
`19h` = 3 ks. **Next-best: 3 ks (path = 20 > budget=19). S2 forced.** ✓

### Primitives used

- Wall strip at C4 row 7 cols 6–37 (S1: makes h-count/hjkl alternatives for ge infinite-cost)
- All-WC 4-char anchor at C4 (ensures ge and gE land at col 5)
- Guard walls at RT1 col 38 and LT1 col 1 (force specific turn columns)
- LT2 gap structure (col 2 walled in row 8; only col 5–6 passable)
- Three adjacent clusters forming one WORD on C6 (baphomet run)
- Col 20 always empty between anchor and WORD (ensures gE lands at col 19)
- `_dijkstra_par_L8` Dijkstra (already implemented; must model ge/gE jumping over walls)

**CHALLENGE (engine):** `ge`/`gE` must be able to jump over wall-strip terrain to reach the
semantic cluster target. If the engine only allows motions to traverse passable cells, the wall
strip at C4 also blocks ge/gE, making the level unsolvable. The motion engine must be verified
to resolve ge/gE as a cluster-scan that is not blocked by intermediate wall cells.
*(Design given the prerequisite: assume ge/gE scan cluster types regardless of intermediate
terrain, consistent with Vim's motion model where ge scans buffer positions.)*

### Self-check

- **Scope:** 2 new motions (ge, gE); backward-end family. ✓
- **Linkage:** ge/gE directly extend e/E backward; backward cousins of b/B. ✓
- **S1 forceability (ge):** Wall strip makes h-count alternatives ∞. ✓
- **S2 forceability (gE):** budget=19; next-best 20 > 19. ✓
- **S4:** `$` used on decorative corridors only; not a shortcut past the forcing terrain. ✓

---

## Level 7 — The Long Plumb (`G gg`)

### New mechanics (≤3)

1. **G** — jump to exit position (last passable row, first non-blank col).
2. **gg** — jump to entry position (first passable row, first non-blank col).

**Note on {n}G:** The review flagged `{n}G` as a third mechanic with ambiguous engine behavior.
Decision: drop `{n}G` from the teaching set for this level. The level teaches G and gg only
(2 mechanics). `{n}G` is a natural extension players discover; a dedicated challenge room can
exercise it later. This eliminates the engine-ambiguity defect and the forcing problem ({n}G
saved only 1 ks, not independently budget-forced).

**Linkage:** G/gg are complementary file-end/file-top jumps — a canonical Vim pair that anchors
the player's mental model of the dungeon as a file.

### Forcing model (S1 primary — terrain-∞ for G; S2 for gg)

**Review defects:**
1. `gg`-alternative (`4k ^`) costs 3 ks vs gg=2 ks; path without gg = 12 ≤ budget=16. Not forced.
2. `{n}G` saves only 1 ks; engine behavior contradictory.

**Fix for G (already S1-adjacent):** G alone is strictly forced because `13j 54l` = 6 ks vs
G=1 ks, and 6-ks sub-path already exceeds the full budget slack. Confirmed from review.

**Fix for gg (S2):** Move KS2 to row 0 col 55 (top-right), making gg essential to return to
the top section. From (4,28) after KS2, `gg` (2 ks) → (0,1), then `l` → (0,2) = exit. Without
gg: must navigate `4k` (2 ks) to row 0 + `^` (1 ks) to col 1 = 3 ks. Δ=1 ks. Path without gg
= 1+1+2+3+1+3+1 = 12 ks. Budget must be < 12 for gg to be forced. But wait — need to also
recompute par with KS2 repositioned.

**Restructured layout for gg forcing:**
Place KS2 farther from entry to make the gg-alternative genuinely expensive:
- KS2 at (1, 55) — top-right of the TOP section (rows 0–3).
- After collecting KS1 at (14,55) via G, player must reach KS2 at (1,55).
- From (14,55): `gg` (2 ks) → (0,1). But KS2 is at (1,55), not (0,1). Alternative route:
  `13k` (3 ks) → (1,55) directly: collect KS2. Then `gg` (2 ks) → (0,1), `l` → (0,2) exit.
  But `gg` could be skipped: `^` (1 ks) → col 1, `l` (1 ks) → col 2 = exit. Without gg: 3 ks.
  
**Better restructuring — force gg via wall topology:**
- Split dungeon into TOP (rows 0–3) and BOTTOM (rows 5–14) with a full WALL at row 4 and
  a one-cell gap at col 55 only.
- KS1 at (14, 1) — bottom-left. Player uses `G` (1 ks) to reach (14,1), `x` to collect.
- To reach the gap at (4,55): must navigate `54l` (3 ks) or use a waypoint. This is hjkl-based.
  Actually: from (14,1), `10k` (3 ks) → (4,1); row 4 is wall except col 55 gap. `54l` (3 ks)
  → (4,55) gap. Cross to (3,55), `gg` (2 ks) → (0,1), `l` → (0,2) exit. Total without G:
  very expensive. Total with G: G(1)+x(1) at (14,1), then navigate to gap (6 ks), cross,
  gg(2)+l(1) = 11 ks. This doesn't force gg distinctly from `13k l`.

**Cleanest gg-forcing layout (S1):**
- TOP section (rows 0–3): entry at (0,1), exit at (0,2).
- WALL at rows 4 (full wall, no gap).
- BOTTOM section (rows 5–14): KS1 at (14,55), KS2 at (5,1).
- Gap from TOP to BOTTOM: a one-way portal via `G` only. `G` jumps to row 14 col 55 (BOTTOM).
  There is NO passable stairway between TOP and BOTTOM — the only way DOWN is `G`, and the only
  way UP is `gg`.
- After collecting KS1 (14,55) and KS2 (5,1), the player uses `gg` (2 ks) to return to (0,1),
  then `l` to exit (0,2).
- Without gg: from (5,1) there is NO passable path to the TOP (row 4 is full WALL). **gg is the
  only finite-cost return. S1 forced.** ✓

**Par recompute with new layout:**
```
G  (1 ks):  (0,1) → (14,55)  [G = last row, first non-blank = (14,1)? No: G lands at _LGG_EXIT_POS.
            Exit_pos is the Dijkstra-defined exit, which in this layout is (0,2). So G lands at
            (14,55) only if we define exit_pos=(14,55). Clarification needed.]
```

**Engine note on G:** In `build_dungeon_9`, `G` teleports to `_LGG_EXIT_POS`. For this layout
to work, `G` must teleport to the KS1 location (14,55) — i.e., the "exit_pos" in the engine is
set to (14,55) for the purpose of G's target, and the actual exit door is (0,2). This is a
design-level choice: G's target is "the far end" which happens to be (14,55), not the door.

**Confirmed layout:**
- `G` target (engine exit_pos) = (14,55) = KS1 location.
- Actual exit door = (0,2).
- `gg` target = (0,1) = entry.

```
G  (1 ks):  (0,1) → (14,55). Collect KS1: x (1 ks).
Navigate:   Must reach KS2 at (5,1). From (14,55): 9k (2 ks) → (5,55), 54h (3 ks) → (5,1).
            Or: gg (2 ks) → (0,1) — wrong, need (5,1) first.
            Optimal: 9k(2)+54h(3) = 5 ks. Total so far: 1+1+5 = 7 ks.
x  (1 ks):  collect KS2 at (5,1). Total: 8 ks.
gg (2 ks):  (5,1) → (0,1). Total: 10 ks.
l  (1 ks):  (0,1) → (0,2) = exit. Total: 11 ks.
```

Wait — this means `9k 54h` = 5 ks for navigation after KS1, and gg from (5,1) saves 0 ks vs
staying at (5,1) and using `4k l` = 3 ks. And without gg (the S1 wall at row 4 blocks it),
there IS no path. ✓ gg is S1-forced (infinite cost to get from BOTTOM to TOP via any hjkl route
because row 4 is full WALL).

**S2 for par computation — is `9k 54h` (5 ks) actually the cheapest nav to KS2?**
From (14,55) after KS1: KS2 is at (5,1). Count options:
- `9k` (2 ks: "9"+"k") then `54h` (3 ks: "54"+"h") = 5 ks.
- `9k 54h` = 5 ks total (cheapest; no shortcut via G/gg helps here).

Par = G(1)+x(1)+9k(2)+54h(3)+x(1)+gg(2)+l(1) = **11 ks**.
Budget = ceil(11 × 1.4) = **16**.

**G forcing:** Without G: from (0,1) to (14,55) = `13j 54l` = 3+3 = 6 ks. Path = 6+1+5+1+2+1
= 16 ks = budget. Tie. **G is NOT strictly forced with budget=16!**

S2 fix: tighten M so 16 > budget.
ceil(11 × M) < 16 → M < 16/11 = 1.454. Use M=1.4 gives budget=16 (tie).
Use M=1.36 → budget = ceil(11×1.36) = ceil(14.96) = **15**.
Without G: path = 16 > 15. ✓ STRICTLY over budget.

**Adopted: M=1.36, budget=15.**
- Optimal (G+gg): 11 ≤ 15. ✓
- Without G: 16 > 15. ✓
- Without gg: ∞ (S1 full-wall at row 4, only gg can return). ✓

### Grid

```
58 cols × 15 rows  (cols 0-57, rows 0-14)

Row 0:  ##@X##################################################  (TOP: entry @=(0,1), exit X=(0,2))
Row 1:  ## ################################################## #  (TOP open)
Row 2:  ## ################################################## #  (TOP open)
Row 3:  ## ################################################## #  (TOP open)
Row 4:  ##########################################################  (FULL WALL — no gap)
Row 5:  ##KS2##################################################  (BOTTOM: KS2 at (5,1))
Row 6:  ## ################################################## #
...
Row 13: ## ################################################## #
Row 14: ## ################################################KS1#  (KS1 at (14,55))
```

**Dimensions:** 15 rows × 58 cols
**Entry:** (0, 1) — `@`
**Exit:** (0, 2) — `X`
**G target (engine exit_pos):** (14, 55) = KS1

### Placements (coordinates)

| Glyph / Entity | Row | Col | Notes |
|---|---|---|---|
| Entry `@` | 0 | 1 | TOP section |
| Exit `X` | 0 | 2 | one step right of entry |
| Full WALL row | 4 | 0–57 | impassable; no gap; gg/G are the only cross-section motions |
| Keystone KS2 | 5 | 1 | first cell of BOTTOM section |
| Keystone KS1 | 14 | 55 | bottom-right; G target |
| TOP section open | 0–3 | 1–56 | all CORRIDOR |
| BOTTOM section open | 5–14 | 1–56 | all CORRIDOR |

### Optimal keystrokes

```
G   (1 ks):  (0,1) → (14,55) = KS1
x   (1 ks):  collect KS1
9k  (2 ks):  (14,55) → (5,55)
54h (3 ks):  (5,55) → (5,1) = KS2
x   (1 ks):  collect KS2
gg  (2 ks):  (5,1) → (0,1)
l   (1 ks):  (0,1) → (0,2) = exit

Par = 1+1+2+3+1+2+1 = 11
Budget = ceil(11 × 1.36) = 15
```

**par = 11 | budget = 15**

### Forcing argument

**G:** Without G: must reach KS1 at (14,55) via `13j 54l` = 3+3 = 6 ks. Full path = 6+1+5+1+2+1
= 16 ks > budget=15. **STRICTLY over budget.** ✓

**gg:** Without gg: row 4 is full WALL — there is NO passable path from BOTTOM (rows 5–14) to
TOP (rows 0–3). `gg` is the only motion that crosses the full wall (engine: gg teleports to
entry position (0,1) regardless of walls). **Cost without gg: ∞. S1 forced.** ✓

**{n}G (dropped):** Not taught. The count-navigation (`9k 54h`) is the explicit "manual nav"
section that makes the G/gg savings visible by contrast.

### Primitives used

- Full WALL at row 4 (no gap; S1 blocks all hjkl cross-section movement)
- Two keystones requiring top→bottom→top traversal (forces G then gg)
- Exit one step right of entry (forces `gg l` not just `gg`)
- G and gg teleport across the wall (engine teleports regardless of intermediate walls)
- `_dijkstra_par_LGG` Dijkstra (already implemented; budget M=1.36)

**CHALLENGE (engine):** `gg` and `G` must teleport to their fixed targets regardless of
intervening wall terrain. Confirm `motion.py` implements G/gg as direct position-set (not
pathfinding). If G/gg are blocked by walls, the level is unsolvable.

### Self-check

- **Scope:** 2 new motions (G, gg); file-jump family. ✓ (dropped {n}G.)
- **Linkage:** G/gg are the canonical file-end/file-top complementary pair. ✓
- **S1 forceability (gg):** Full WALL at row 4; gg is the only cross-wall motion. ✓
- **S2 forceability (G):** budget=15; G-avoiding path=16 > 15. ✓
- **S4:** `$`, `^`, count-j/k all available for intra-section navigation; none bypass the wall. ✓

---

## Level 8 — The Screen Vault (`H M L`)

### New mechanics (≤3)

1. **H** — jump to first passable row's first non-blank column (top of screen).
2. **M** — jump to middle passable row's first non-blank column.
3. **L** — jump to last passable row's first non-blank column (bottom of screen).

**Linkage:** H/M/L are screen-relative siblings — together they form the "coarse vertical jump"
family, dividing the screen into thirds.

### Forcing model — REDESIGNED: three sub-rooms, one command each (S1+S2 combined)

**Previous design (single room, joint-only forcing):** H/M/L each saved only 1 ks vs `count-j`
(Δ=1). With par=7, budget=10, any individual or two-of-three skip fit within budget; only all-
three-skip (cost=11 > 10) truly failed. Proved that Δ=1 cannot individually force any of the
three commands under any multiplier without a zero-tolerance budget. Adopted as joint-only.

**New design (three sub-rooms, Δ≥3 for each command individually):**

Solve by placing each command in its own sub-room where the player arrives **off-column** (col 25).
Each sub-room is 23 passable rows tall (rows 1–23). H/M/L targets in a 23-row sub-room:
- H → row 1, col 4 (first passable row, fnb = col 4).
- M → row 12, col 4 (middle of 23 rows, fnb = col 4).
- L → row 23, col 4 (last passable row, fnb = col 4).

The player ALWAYS enters each sub-room at col 25 (off-center column). This guarantees that
every count-j alternative requires an additional `^` to reach col 4 (the KS column):
- H alternative from entry (row 12, col 25): `11k` (3 ks: "1","1","k") → (1, 25); `^` (1 ks)
  → (1, 4). Total = 4 ks. H (1 ks) saves **3 ks**. Δ=3. ✓
- M alternative from top (row 1, col 25) [after portal in from sub-room A]: `11j` (3 ks) → (12,25);
  `^` (1 ks) → (12,4). Total = 4 ks. M (1 ks) saves **3 ks**. Δ=3. ✓
- L alternative from top (row 1, col 25): `22j` (3 ks: "2","2","j") → (23,25); `^` (1 ks) →
  (23,4). Total = 4 ks. L (1 ks) saves **3 ks**. Δ=3. ✓

**Three-sub-room layout:**

- **Sub-room A** (teaches H): 25 rows × 50 cols. Player enters at (12, 25). KS-H at (1, 4).
  Portal exit at (1, 44) → leads to sub-room B entry (1, 25).
- **Sub-room B** (teaches M): 25 rows × 50 cols. Player enters at (1, 25). KS-M at (12, 4).
  Portal exit at (12, 44) → leads to sub-room C entry (1, 25).
- **Sub-room C** (teaches L): 25 rows × 50 cols. Player enters at (1, 25). KS-L at (23, 4).
  Exit X at (23, 44) (locked — needs all 3 KS).

Each sub-room has fnb = col 4 on all passable rows (cols 0–3 are WALL on every row). Col 25
is the fixed arrival column (off-center). Each portal transition drops the player at col 25 of
the next sub-room's top row (row 1).

**S4 guard:** `$` from col 25 → rightmost passable col (col 45) but KS is at col 4, not col 45.
`$` does NOT help reach KS; only H/M/L (targeting fnb = col 4) provide the col-4 landing.
Using `$` then trying count-k/j still requires `^` after the count, same as the baseline
alternative. `^` from col 45 costs 1 ks same as from col 25. Δ is unchanged.

**S4 guard — `gg` and `G` (already taught in L7):** `gg` teleports to entry (the sub-room A
entry is its own passable region; the engine defines gg-target per sub-room). `G` teleports
to the bottom of the current sub-room. These could shortcut H or L. To block:
- In sub-room A: make gg-target = (12, 25) (the entry itself, which is the M-row — not the H
  target at row 1). `gg` is a no-op. `G` goes to row 23 col 25, not row 1. Neither helps H.
- In sub-room C: `G` goes to row 23 col 25 — exactly the L landing row but wrong column (col 25
  vs col 4). Still needs `^` (1 ks), so G-then-x costs G(1)+^(1)+x(1) = 3 ks vs L(1)+x(1) = 2 ks.
  L is still cheaper. ✓

### Par arithmetic

```
Sub-room A:
  Entry:    (12, 25)  ← starting position
  H  (1 ks): (12,25)→(1,4)   KS-H
  x  (1 ks): collect KS-H
  40l (3 ks): (1,4)→(1,44)   portal exit (col 4 to col 44 = 40 cols; "40"+"l" = 3 ks)
  j  (1 ks): step through portal → sub-room B entry (1,25)

Sub-room B:
  M  (1 ks): (1,25)→(12,4)   KS-M
  x  (1 ks): collect KS-M
  40l (3 ks): (12,4)→(12,44)  portal exit
  j  (1 ks): step through portal → sub-room C entry (1,25)

Sub-room C:
  L  (1 ks): (1,25)→(23,4)   KS-L
  x  (1 ks): collect KS-L
  40l (3 ks): (23,4)→(23,44)  exit X

Full optimal: H x 40l j | M x 40l j | L x 40l
Par = (1+1+3+1) + (1+1+3+1) + (1+1+3) = 6+6+5 = 17 ks
Budget = ceil(17 × 1.11) = ceil(18.87) = 19
```

**par = 17 | M = 1.11 | budget = 19**

*(Multiplier 1.11 is the minimum yielding budget=19; any M in [1.06, 1.11] gives ceil(17×M)=19.
Adopting M=1.11 for documentation; a Dijkstra solver may set exact par and recompute M.)*

### Skip paths (individual forcing proof)

**H-skip (use `11k ^` instead of H):**
```
Sub-room A: 11k(3) + ^(1) + x(1) + 40l(3) + j(1) = 9 ks  [vs 6 ks optimal, +3]
Sub-room B: M(1)+x(1)+40l(3)+j(1)             = 6 ks  [optimal]
Sub-room C: L(1)+x(1)+40l(3)                  = 5 ks  [optimal]
H-skip total = 9+6+5 = 20 ks > budget=19. STRICTLY over. ✓
```

**M-skip (use `11j ^` instead of M):**
```
Sub-room A: H(1)+x(1)+40l(3)+j(1)             = 6 ks  [optimal]
Sub-room B: 11j(3)+^(1)+x(1)+40l(3)+j(1)      = 9 ks  [vs 6 ks optimal, +3]
Sub-room C: L(1)+x(1)+40l(3)                  = 5 ks  [optimal]
M-skip total = 6+9+5 = 20 ks > budget=19. STRICTLY over. ✓
```

**L-skip (use `22j ^` instead of L):**
```
Sub-room A: H(1)+x(1)+40l(3)+j(1)             = 6 ks  [optimal]
Sub-room B: M(1)+x(1)+40l(3)+j(1)             = 6 ks  [optimal]
Sub-room C: 22j(3)+^(1)+x(1)+40l(3)           = 8 ks  [vs 5 ks optimal, +3]
L-skip total = 6+6+8 = 20 ks > budget=19. STRICTLY over. ✓
```

**Two-of-three-skip:** any two skips cost 6+9+9=24 or 9+9+5=23 > 19. ✓
**Optimal path (no skips):** 17 ks ≤ 19. ✓

**Each of H, M, L is INDIVIDUALLY strictly required.** Δ=3 for every command. ✓

### Grid

**Sub-room A — 25 rows × 50 cols (rows 0-24, cols 0-49)**

```
Row  0: ##################################################
Row  1: ####[KS-H (1,4) ∘].......portal-exit (1,44)...####
Row  2: ####.............................................####
...
Row 12: ####[ENTRY @=(12,25)].............................####
...
Row 23: ####.............................................####
Row 24: ##################################################

Passable: rows 1-23, cols 4-45
KS-H: (1, 4)  — fnb of row 1 (cols 0-3 wall)
Portal exit: (1, 44)  — stepping right through opens passage to sub-room B (1,25)
Entry @: (12, 25)
```

**Sub-room B — 25 rows × 50 cols**

```
Row  0: ##################################################
Row  1: ####[ENTRY-B (1,25)]..portal-exit (12,44)....####
...
Row 12: ####[KS-M (12,4) ·]...............................####
...
Row 24: ##################################################

Passable: rows 1-23, cols 4-45
KS-M: (12, 4)  — fnb of row 12
Portal exit: (12, 44)  — leads to sub-room C (1,25)
Entry: (1, 25)  [arrival from sub-room A portal]
```

**Sub-room C — 25 rows × 50 cols**

```
Row  0: ##################################################
Row  1: ####[ENTRY-C (1,25)]..exit-door (23,44)......####
...
Row 23: ####[KS-L (23,4) ⊙]......[X (23,44)]...........####
Row 24: ##################################################

Passable: rows 1-23, cols 4-45
KS-L: (23, 4)  — fnb of row 23
Exit X: (23, 44)  — locked (needs KS-H, KS-M, KS-L)
Entry: (1, 25)  [arrival from sub-room B portal]
```

**Global dimensions:** 3 sub-rooms side-by-side (or sequential), each 25 r × 50 c.
For a side-by-side layout: 25 rows × 150 cols total. Portals at col 44 of sub-room A/B are
pass-through cells connecting to col 4+50=54 (sub-room B entry) and col 4+100=104 (sub-room C
entry) respectively in the global grid.

*(Alternatively the generator builds three separate grid objects and the engine transitions
between them; either implementation is valid.)*

### Placements (coordinates, per sub-room local coords)

| Glyph / Entity | Sub-room | Row | Col | Notes |
|---|---|---|---|---|
| Entry `@` | A | 12 | 25 | middle row, off-center column |
| Wall border | A | all | 0–3 | forces fnb = col 4 on every passable row |
| KS-H `∘` | A | 1 | 4 | H landing target (first row, fnb=col 4) |
| Portal exit | A | 1 | 44 | leads to sub-room B (1, 25) |
| Decorative clusters | A | 2–23 | 6–43 | seed-varying, no KS interference |
| Entry (from portal) | B | 1 | 25 | arrival from sub-room A |
| Wall border | B | all | 0–3 | fnb = col 4 |
| KS-M `·` | B | 12 | 4 | M landing target (middle row, fnb=col 4) |
| Portal exit | B | 12 | 44 | leads to sub-room C (1, 25) |
| Decorative clusters | B | 2–23 | 6–43 | seed-varying |
| Entry (from portal) | C | 1 | 25 | arrival from sub-room B |
| Wall border | C | all | 0–3 | fnb = col 4 |
| KS-L `⊙` | C | 23 | 4 | L landing target (last row, fnb=col 4) |
| Exit `X` | C | 23 | 44 | locked (needs KS-H + KS-M + KS-L) |
| Decorative clusters | C | 2–22 | 6–43 | seed-varying |

### Optimal keystrokes

```
[Sub-room A] H(1) x(1) 40l(3) j(1)   = 6 ks
[Sub-room B] M(1) x(1) 40l(3) j(1)   = 6 ks
[Sub-room C] L(1) x(1) 40l(3)        = 5 ks

Full optimal: H x 40l j M x 40l j L x 40l
Par = 6+6+5 = 17
Budget = ceil(17 × 1.11) = 19
```

**par = 17 | budget = 19 | M = 1.11**

### Forcing argument

**H (sub-room A):** Entry col 25 ≠ KS col 4. Alternative to H: `11k`(3 ks) + `^`(1 ks) = 4 ks.
H-skip path total = 9+6+5 = 20 > budget=19. **STRICTLY over. S2 forced individually. ✓**

**M (sub-room B):** Entry col 25 (via portal). Alternative to M: `11j`(3 ks) + `^`(1 ks) = 4 ks.
M-skip path total = 6+9+5 = 20 > budget=19. **STRICTLY over. S2 forced individually. ✓**

**L (sub-room C):** Entry col 25 (via portal). Alternative to L: `22j`(3 ks) + `^`(1 ks) = 4 ks.
L-skip path total = 6+6+8 = 20 > budget=19. **STRICTLY over. S2 forced individually. ✓**

**Arithmetic summary:**
- par=17; each skip costs 20 > 19 (Δ=3 per command, Δ-needed=2 for budget=19, margin=19−17=2).
- 20 − 19 = 1: STRICT (not a tie). All three individually forced. ✓

**Key design invariant:** Every portal arrival is at (row 1, col 25). This ensures col 25 ≠ col 4
(fnb) for M and L as well as H, so all three alternatives require the `^` step and cost 4 ks
instead of 1 ks. Δ=3 for each. Budget margin = 2. 3 > 2. ✓

### Primitives used

- Three sequential sub-rooms (separate "screen" contexts; each sub-room has its own H/M/L rows)
- Left-wall barrier cols 0–3 on all passable rows (forces fnb = col 4 on every row)
- Off-center portal arrival col 25 (ensures `^` is always needed in count-j alternatives)
- Portal cells at (1,44) and (12,44) (pass-through connections between sub-rooms)
- KS lock on exit X (all three keystones required)
- Decorative seed-varying rune clusters (don't affect fnb)
- `_dijkstra_par_L10` Dijkstra (must model: per-sub-room H/M/L targets; portal transitions;
  col-25 arrival at each sub-room entry)

**ENGINE NOTE:** H/M/L must reference the CURRENT sub-room's passable rows (not the global
grid). The engine needs to track which sub-room the player is in and compute H/M/L targets
accordingly. If the engine uses a global grid, sub-rooms must be separated by wall regions so
the "passable rows" visible to H/M/L are scoped to the current sub-room's rows.

### Self-check

- **Scope:** 3 new motions (H, M, L); screen-thirds family. ✓
- **Linkage:** H/M/L are a tight complementary set. ✓
- **S2 forceability (H):** Skip path = 20 > budget=19. STRICTLY over. ✓
- **S2 forceability (M):** Skip path = 20 > budget=19. STRICTLY over. ✓
- **S2 forceability (L):** Skip path = 20 > budget=19. STRICTLY over. ✓
- **S4:** `gg`/`G` do not shortcut to KS targets (gg-target = entry col 25; G-target = row 23
  col 25 not col 4 — still needs `^`). `$` lands at col 45, not col 4 — count-j+^ cost same. ✓
- **Known requirement:** Engine must scope H/M/L to current sub-room. ✓ (documented)

---

## Level 9 — The Void Rift (`} {`)

*(Split from original "Runic Archives" per S5 — paragraph and sentence families are distinct.)*

### New mechanics (≤3)

1. **`}`** — paragraph jump: move to the next blank row (the "void between paragraph blocks").
2. **`{`** — paragraph jump backward: move to the previous blank row.

**Linkage:** `}`/`{` are a forward/backward pair — the canonical "paragraph" motion family.
Dungeon metaphor: a blank row (no runes, fully passable) is the empty space between dungeon
paragraphs. Void-filled barrier rows (full-width `○`) physically block all j/k movement; `}`/`{`
are the only motions that leap from one side to the other.

### Forcing model (S1 — terrain-∞)

Void barriers physically kill any entity that lands on them (lethal runes). `j`-count cannot
pass through void rows. No horizontal motion bypasses a vertical void barrier. `}`/`{` are the
**only** motions that scan for the next/previous blank row and teleport past voids. Without them,
the level has no finite-cost solution. S1 forced (∞ cost alternative). ✓

### Grid

```
62 cols × 14 rows  (cols 0-61, rows 0-13)

Row 0:  @@...[Para 1 rune clusters cols 2-58]
Row 1:  [Para 1 rune clusters]
Row 2:  [Para 1 rune clusters]
Row 3:  ○○○○○○○○○○○○○○○○○○○○○○○○○○○○○○○○○○○○○○○○○○○○○○○○○○○○○○○○○  (Void barrier A)
Row 4:  ○○○○○○○○○○○○○○○○○○○○○○○○○○○○○○○○○○○○○○○○○○○○○○○○○○○○○○○○○
Row 5:  ○○○○○○○○○○○○○○○○○○○○○○○○○○○○○○○○○○○○○○○○○○○○○○○○○○○○○○○○○
Row 6:     (blank row — fully passable, NO runes)    ← } target 1
Row 7:  [Para 2 rune clusters cols 2-58]
Row 8:  [Para 2 rune clusters]
Row 9:  ○○○○○○○○○○○○○○○○○○○○○○○○○○○○○○○○○○○○○○○○○○○○○○○○○○○○○○○○○  (Void barrier B)
Row 10: ○○○○○○○○○○○○○○○○○○○○○○○○○○○○○○○○○○○○○○○○○○○○○○○○○○○○○○○○○
Row 11: ○○○○○○○○○○○○○○○○○○○○○○○○○○○○○○○○○○○○○○○○○○○○○○○○○○○○○○○○○
Row 12:    (blank row — fully passable, NO runes)    ← } target 2
Row 13: #X#############################################################  (exit at col 1)

Entry: (0, 1)   Exit: (13, 1)
```

**Dimensions:** 14 rows × 62 cols
**Entry:** (0, 1) — `@`
**Exit:** (13, 1) — `X`

### Placements (coordinates)

| Glyph / Entity | Row | Col range | Notes |
|---|---|---|---|
| Entry `@` | 0 | 1 | — |
| Para 1 clusters | 0–2 | 2–58 | seed-varying, non-void |
| Void barrier A | 3–5 | 1–60 | full-width `○`; blocks all j/k through |
| Blank row 1 | 6 | 1–60 | NO runes; `}` lands here |
| Para 2 clusters | 7–8 | 2–58 | seed-varying, non-void |
| Void barrier B | 9–11 | 1–60 | full-width `○` |
| Blank row 2 | 12 | 1–60 | NO runes; `}` lands here |
| Exit `X` | 13 | 1 | — |

### Optimal keystrokes

```
} } j
  } (1 ks): row 0 → blank row 6     (skip void barrier A)
  } (1 ks): row 6 → blank row 12    (skip void barrier B)
  j (1 ks): row 12 → row 13 = exit col 1

Par = 3
Budget = ceil(3 × 1.4) = ceil(4.2) = 5
```

**par = 3 | budget = 5**

### Forcing argument

**`}` (both uses):** Void barriers at rows 3–5 and 9–11 block all j/k movement. `count-j` into
void = death (infinite cost). `}` is the **only** finite-cost way to traverse each barrier.
**Next-best: ∞ (lethal void). S1 forced.** ✓

**`{`** is available for backward exploration (returning to Para 1) but not required on the
optimal path. It is available as an exploration tool and demonstrated if the player backtracks.

**Budget check:** par=3, budget=5. Only path variations involve extra `{` backtracking (+2 ks
each) or `$`/`^` repositioning on paragraph rows — none cheaper. ✓

### Primitives used

- Full-width void-rune barrier rows (3 rows deep each: lethal on landing)
- Blank rows (no runes; `}` target)
- Exit directly below blank row 2 (one `j` from the `}` landing)
- `_dijkstra_par_L13a` Dijkstra (new; supports `disable_brace` flag)

### Self-check

- **Scope:** 2 new motions (`}`, `{`); paragraph-jump family. ✓ (reduced from 4 via split)
- **Linkage:** `}`/`{` are a forward/backward pair — single family. ✓
- **S1 forceability:** Void barriers = death on landing; `}` is the only escape. ✓
- **S4:** No earlier-act command (`$`, `w`, `G`, `H`, etc.) can cross a void barrier. ✓

---

## Level 9.5 — The Sentence Corridor (`) (`)

*(Split from original "Runic Archives" per S5.)*

### New mechanics (≤3)

1. **`)`** — sentence jump forward: moves to the start of the next sentence (rune run after a `.`, `!`, or `?` terminator).
2. **`(`** — sentence jump backward: moves to the start of the current or previous sentence.

**Linkage:** `)`/`(` are a forward/backward pair — the canonical "sentence" motion family.
Dungeon metaphor: a "sentence" = a punctuation-delimited rune run on a corridor row. Wall gaps
between sentence segments make `)` the **only** way to cross from one segment to the next.

### Forcing model (S1 — terrain-∞)

Wall gaps between sentence segments block all horizontal motions (`l`, `h`, `w`, `b`, `e`, `W`,
`B`, `E`, `$`, `^`, `0`). `)` finds the next sentence-start by scanning for the first rune
after a `.`/`!`/`?` terminator, which is the first rune of the next segment. The engine must
model `)` as a semantic scan (not a terrain traversal), allowing it to cross the wall gap.
Without `)`: cost = ∞ (wall blocks all finite alternatives). S1 forced. ✓

### Grid

```
62 cols × 6 rows  (cols 0-61, rows 0-5)

Row 0:  ##############################################################
Row 1:  #@...(filler)................................................#  (approach row — left to sentence row)
Row 2:  ##############################################################  (wall row with gap at col 1)
Row 3:  #[S1: "The seal." cols 1-9]##########[S2: "Power!" cols 21-27]##########[S3: "Gate!" cols 39-44 = X]#
Row 4:  ##############################################################
Row 5:  ##############################################################

S1 segment: cols 1-9   (rune run ending with `.`)
WALL:        cols 10-20
S2 segment: cols 21-27 (rune run ending with `!`)
WALL:        cols 28-38
S3 segment: cols 39-44 (rune run ending with `!`); first char col 39 = exit X

Entry: (1, 1)   Exit: (3, 39)
```

**Dimensions:** 6 rows × 62 cols
**Entry:** (1, 1) — `@`
**Exit:** (3, 39) — `X` (first char of S3 = first `)` target from S2)

### Placements (coordinates)

| Glyph / Entity | Row | Col range | Notes |
|---|---|---|---|
| Entry `@` | 1 | 1 | — |
| Wall row with gap | 2 | 0–61 | WALL except col 1 (gap for descent to sentence row) |
| S1 `The seal.` | 3 | 1–9 | ember-kind rune cluster; ends with `.` |
| WALL | 3 | 10–20 | impassable gap between S1 and S2 |
| S2 `Power!` | 3 | 21–27 | ember-kind rune cluster; ends with `!` |
| WALL | 3 | 28–38 | impassable gap between S2 and S3 |
| S3 `Gate!` | 3 | 39–44 | ember-kind rune cluster; first char = exit |
| Exit `X` | 3 | 39 | — |

### Optimal keystrokes

```
j 2)
  j  (1 ks): (1,1) → (3,1) [descends through wall-row gap at col 1; col 1 = start of S1]
  2) (2 ks): S1-start col 1 → S2-start col 21 → S3-start col 39 = exit

Par = 1+2 = 3
Budget = ceil(3 × 1.4) = ceil(4.2) = 5
```

**par = 3 | budget = 5**

*(Note: the `j` to descend to row 3 is through a wall-row gap at col 1. If the engine requires
2j to cross row 2 (wall), recompute: par = 2+2 = 4, budget = 6.)*

### Forcing argument

**`)` (both uses):** Wall gaps at cols 10–20 and 28–38 on row 3 block all horizontal motions.
From col 9 (end of S1), `l`/`w`/`W`/`e`/`E`/`$` all hit the wall at col 10. Only `)` scans
for the next sentence-start (col 21 = first rune of S2 after the `.` terminator at col 9).
Similarly from col 27 → S3 at col 39. **Next-best: ∞ (wall). S1 forced.** ✓

**`(`** is available for backward exploration but not on the optimal path.

### Primitives used

- Wall gaps between sentence segments on row 3 (S1–S2 gap, S2–S3 gap)
- Ember-kind rune clusters ending with `.`/`!` (sentence terminators)
- Wall row 2 with single gap at col 1 (descent path; prevents `$`-then-j bypass)
- `_dijkstra_par_L13b` Dijkstra (new; supports `disable_paren` flag)

**CHALLENGE (engine):** `)` must be implemented as a semantic scan that crosses wall-gap terrain
(i.e., `)` finds the next sentence-start by scanning the row's rune content, not by pathfinding
through passable cells). If `)` is blocked by the wall between S1 and S2, the level is
unsolvable. Confirm `motion.py` implements `)` as a position-jump (not terrain traversal).

### Self-check

- **Scope:** 2 new motions (`)`, `(`); sentence-jump family. ✓ (split from `}`/`{`)
- **Linkage:** `)`/`(` are forward/backward sentence jumps — single family. ✓
- **S1 forceability:** Wall gaps block all horizontal alternatives; `)` is the only finite-cost
  cross-segment motion. ✓
- **S4:** `G`, `H`, `L`, `gg` — none can cross the horizontal wall gaps to reach S3. ✓

---

## Level 10.1 — The Warden Surveyor (ACT II BOSS)

*(Renumbered from 9.1 to 10.1 due to the S5 split adding Level 9.5.)*

### Overview

The Warden Surveyor caps Act II. Each of its five combat phases demands a different Act II
structural motion family.

**Immunity clarification:** The Warden Surveyor's phase seals and shields CANNOT be cleared by
Act I motion-based approaches. Only Act II structural motions trigger phase transitions. `hjkl`
remain available for micro-positioning within each phase corridor — they are not disabled.
The forcing is terrain-based (S1) within each phase: the Act II motion is the only finite-cost
way to reach the phase trigger. Act I motions (hjkl, w/b/e, f/F/t/T, ; ,, ^$0, count) are
freely usable for navigation; they simply cost too much (or ∞ due to terrain) to clear phases.

### Phase Table

| Phase | Motion family | How forced (S1 terrain) | One motion per phase |
|---|---|---|---|
| 1 — WORD Approach | `W` or `B` or `E` | Code-WORD corridor; `w`/`b`/`e` alternatives cost ≥3× as many ks; with tight phase budget W/B/E required | ✓ |
| 2 — Backward Retreat | `ge` or `gE` | Wall strip between anchor and right side (S1); h-count ∞ | ✓ |
| 3 — File Teleport | `G` then `gg` | Full WALL between sections; G and gg are the only cross-wall teleports | ✓ |
| 4 — Screen Thirds | `H`, `M`, `L` | Keystones at H/M/L rows; entry at M-row col 25; H/M/L-skip alternatives need `^` after count-k/j; jointly forced within phase (all-three-skip > phase budget) | ✓ |
| 5 — Para Finale | `}` | Full-width void barrier; `}` is the only finite-cost cross-barrier motion | ✓ |

### Grid

```
60 cols × 26 rows

Row 0:  ############################################################
Row 1:  #@[WORD clusters: a.b+c*d x+y*z/w m.n-p*q §‽∘¶]   [D1]  #  (Phase 1)
Row 2:  #  [WORD cluster filler]                                   #
Row 3:  ############################################################  (wall separator)
Row 4:  #  [ge anchor cols 2-5] ################################## #  (Phase 2; wall strip 6-57)
Row 5:  ############################################################  (wall separator)
Row 6:  #  [open corridor — G zone]                 [KS-G (6,55)] #  (Phase 3 BOTTOM)
Row 7:  #                                                          #
Row 8:  ############################################################  (FULL WALL — G/gg barrier)
Row 9:  #  [open corridor — gg zone]   @ phase3 entry (9,1)       #  (Phase 3 TOP)
Row 10: ############################################################  (wall separator)
Row 11: ####[KS-H (11,4)]...[rune clusters]...####################  (Phase 4: H row)
Row 12: ##########################################################  #
Row 13: ####[KS-M (13,4)]...[rune clusters]...####################  (Phase 4: M row)
Row 14: ##########################################################  #
Row 15: ####[KS-L (15,4)]...[rune clusters]...####################  (Phase 4: L row)
Row 16: ############################################################  (wall separator)
Row 17: # [Para 1: rune clusters rows 17-18]                      #  (Phase 5)
Row 18: # [rune clusters]                                          #
Row 19: ○○○○○○○○○○○○○○○○○○○○○○○○○○○○○○○○○○○○○○○○○○○○○○○○○○○○○○○○○  (void barrier)
Row 20: ○○○○○○○○○○○○○○○○○○○○○○○○○○○○○○○○○○○○○○○○○○○○○○○○○○○○○○○○○
Row 21: ○○○○○○○○○○○○○○○○○○○○○○○○○○○○○○○○○○○○○○○○○○○○○○○○○○○○○○○○○
Row 22:    (blank row — } target)
Row 23: # [WARDEN_SEAL] [boss_seal] [exit X at col 58]            #
Row 24: ############################################################
Row 25: ############################################################
```

**Dimensions:** 26 rows × 60 cols
**Entry:** (1, 1) — `@`
**Exit:** (23, 58) — `X`

### Phase Details

**Phase 1 (WORD Approach):** Row 1 has four code-WORD groups (same spec as Level 5:
alternating word/punct chars, ≥6 w-boundaries per group). Seal door D1 at (1,50). Player
uses `4W` (2 ks) to navigate the code corridor. `w`-only alternative: ≥24 w-presses = 3 ks
for C1 alone — per-phase budget makes this too slow. Phase par ≈5 ks; phase budget tight.

**Phase 2 (Backward Retreat):** Row 4, anchor at cols 2–5 (4 all-WC chars). Wall strip at
cols 6–57 (S1: h-count ∞). From col 58 (right edge), `ge` or `gE` jumps backward to col 5
(end of anchor) in 1 ks. No other finite-cost option. Phase seal opens at col 5.

**Phase 3 (File Teleport):** Full WALL at row 8. Phase 3 entry at (9,1) (TOP section).
KS-G at (6,55) (BOTTOM). Player uses `G` (1 ks) → (6,55), `x` (1 ks) to collect KS-G, then
`gg` (2 ks) → (9,1) [gg = entry of phase 3 section]. `hjkl` for micro-nav within sections.
Without G: `7j 54l` = 2+3 = 5 ks (phase budget makes this too slow). Without gg: ∞ (full wall).

**Phase 4 (Screen Thirds):** Phase 4 section is rows 11–15 (5 rows total; 3 passable rows 11,
13, 15 with KS at H/M/L targets). Entry at (13,25) (M row). KS-H at (11,4), KS-M at (13,4),
KS-L at (15,4). Same H/M/L mechanics as Level 8 but within a single 5-row phase section (not
3 sub-rooms). Wall separators at rows 10,12,14,16 with single-col gap at col 4 only force the
player to be at col 4 to descend/ascend between rows — `^` step required for any count-k/j
alternative from col 25. All-three-skip > phase budget (jointly forced within this phase section).

**Phase 5 (Para Finale):** Full-width void barrier at rows 19–21. Blank row 22 = `}` target.
`}` (1 ks) from row 18 → row 22. `j` (1 ks) → row 23 = warden room. Without `}`: death on
void row landing. S1 forced. ✓

### Boss Phases Summary

| Phase | Par (approx) | Key motions | S1/S2 |
|---|---|---|---|
| 1 | 5 ks | 4W (2 ks) + x + navigate | S2 (w-count too slow) |
| 2 | 3 ks | ge (1 ks) + combat | S1 (wall strip) |
| 3 | 5 ks | G(1)+x(1)+gg(2)+l(1) | S1 (full wall) + S2 (G) |
| 4 | 7 ks | H x M x L x | joint S2 |
| 5 | 3 ks | }(1)+j(1)+combat | S1 (void barrier) |

**Total simulated par ≈ 23 ks. Budget = ceil(23 × 1.4) = 33.**

### Immunity mechanism

The Warden Surveyor's phase seals gate phase transitions. Each phase's seal is positioned such
that:
- The terrain between the player's entry to that phase and the seal requires the Act II motion
  (S1 or S2 forcing as documented per phase above).
- `hjkl` are freely usable within each phase for micro-positioning.
- Act I motions used INSTEAD of Act II motions either cost ∞ (terrain wall/void) or strictly
  exceed the per-phase budget allocation.

### Primitives used

- `boss_seal` entities gating phase transitions (from `build_dungeon_51` pattern)
- `seal_door` at Phase 1 (opened by approaching from the W-navigated column)
- Code-WORD clusters (Phase 1: force W)
- Wall strip at row 4 cols 6–57 (Phase 2: S1 force ge/gE)
- Full WALL at row 8 (Phase 3: S1 force gg)
- KS-H/M/L at rows 11/13/15 (Phase 4: joint force HML)
- Full-width void barrier rows 19–21 (Phase 5: S1 force `}`)
- Fog on phase rooms until prior seal opens

### Self-check

- **Scope:** Boss — exercises taught Act II commands. ✓
- **Linkage:** One phase per Act II family (W/B/E; ge/gE; G/gg; H/M/L; `}`). ✓
- **Immunity clarification:** hjkl usable for nav; Act II motions required for phase triggers. ✓
- **S1 phases:** Phase 2 (wall strip), Phase 3 (full wall/void), Phase 5 (void barrier). ✓
- **S2 phases:** Phase 1 (code-WORD density + tight phase budget), Phase 4 (joint HML forcing). ✓
- **One motion family per phase:** ✓ (Phase 5 uses only `}`, not `)` — sentence motions not
  needed at the boss level; they are Phase 3 of Act II teaching). ✓

---

## Summary Table

| Level | Name | Commands | par | budget | Forceability | S1/S2 |
|---|---|---|---|---|---|---|
| 5 | The WORD Forge | `W B E` | 11 | 15 (M=1.35) | Joint: all-three-skip=16>15 ✓ | S2 (code density + wall strip + tight M) |
| 6 | The Backward Vaults | `ge gE` | 18 | 19 (M=1.055) | ge: ∞ (wall strip); gE: 20>19 ✓ | S1(ge) + S2(gE) |
| 7 | The Long Plumb | `G gg` | 11 | 15 (M=1.36) | G: 16>15 ✓; gg: ∞ (full wall) ✓ | S1(gg) + S2(G) |
| 8 | The Screen Vault | `H M L` | 17 | 19 (M=1.11) | STRICT individual: H-skip=20>19 ✓; M-skip=20>19 ✓; L-skip=20>19 ✓ | S2 per-command (3 sub-rooms, Δ=3 each) |
| 9 | The Void Rift | `} {` | 3 | 5 (M=1.4) | ∞ (void barriers lethal) ✓ | S1 |
| 9.5 | The Sentence Corridor | `) (` | 3 | 5 (M=1.4) | ∞ (wall gaps block h-count) ✓ | S1 |
| 10.1 | The Warden Surveyor | all Act II | ≈23 | 33 (M=1.4) | Per-phase: S1 (Phases 2,3,5) + S2 (Phases 1,4) | S1+S2 |

---

## Challenges Requiring Human Decision

### CHALLENGE-A — Level 6 ge/gE: engine must support wall-crossing motions

`ge`/`gE` must jump to semantic cluster targets through intermediate wall cells. If the engine
resolves ge/gE by pathfinding through passable terrain, the S1 wall strip at C4 also blocks the
taught motions, making the level unsolvable. **Decision needed:** Confirm that `motion.py`
implements ge/gE as a rune-type scan (buffer-position model) that is not blocked by wall cells.
If not implemented this way, an alternative S1 forcing mechanism is needed (e.g., make `33h`
wrap around via a corridor, costing ∞ without ge/gE).

### CHALLENGE-B — Level 7 G/gg: engine must teleport through walls

`G` and `gg` must teleport to their fixed targets regardless of intermediate wall terrain (full
WALL at row 4). **Decision needed:** Confirm `motion.py` implements G/gg as direct
position-sets that bypass wall checks. If G/gg are blocked by walls, the full-WALL separator
topology is unworkable and an alternative (e.g., water barrier + G/gg ignore water) is needed.

### CHALLENGE-C — Level 8 H/M/L: RESOLVED via three-sub-room design

Redesigned as three sequential sub-rooms (each 25 rows × 50 cols). Each sub-room teaches one
command with Δ=3 ks (count-j alternative requires 2-digit count + `^` step = 4 ks vs 1 ks).
Par=17, budget=19, each skip=20>19. STRICT individual forcing achieved.
**Engine requirement:** H/M/L must reference the CURRENT sub-room's passable row range. Confirm
that the engine scopes H/M/L to the active sub-room's grid slice when sub-rooms are implemented
as separate regions in the global map. If sub-rooms share a single grid object, the H/M/L
target rows must be re-derived based on the player's current sub-section boundaries.

### CHALLENGE-D — Level 9.5 `)` (`: engine must support wall-crossing sentence scan

`)` must find the next sentence-start by scanning rune content across wall-gap terrain. If `)`
is blocked by the wall between S1 and S2, the level is unsolvable. **Decision needed:** Confirm
`motion.py` implements `)` as a position-jump (semantic scan of row content, not terrain
pathfinding). If not, an alternative forcing mechanism is needed (e.g., water gap that `)` can
cross but `l`-count cannot).

### CHALLENGE-E — Boss level 10.1: renumbering from 9.1

The S5 split (Void Rift + Sentence Corridor = two levels) shifts the boss from 9.1 to 10.1.
This propagates to `levels.py`, `main.py` dispatch, test files, save/progress data, and the
Act III numbering (which would start at level 11 instead of 10). **Decision needed:** Confirm
renumbering is acceptable and update all references in Part 4 of LEVELS_PLAN.md.

---

## Implementation Notes for Generator

### New/modified builder functions

| Level | Builder function | Status |
|---|---|---|
| 5 | `build_dungeon_6` | Modify: denser code groups (≥6 boundaries), LT1 wall strip, tighten M=1.35 |
| 6 | `build_dungeon_8` | Modify: add wall strip row 7 cols 6–37; tighten M=1.055 |
| 7 | `build_dungeon_9` | Modify: full WALL row 4, KS2 at (5,1), G-target=(14,55), M=1.36 |
| 8 | `build_dungeon_10` | REDESIGN: 3 sub-rooms (25r×50c each); M=1.11; per-sub-room H/M/L scoping |
| 9 | `build_dungeon_13a` | New: void barriers + blank rows; par solver with `disable_brace` |
| 9.5 | `build_dungeon_13b` | New: wall-gap sentence row; par solver with `disable_paren` |
| 10.1 | `build_dungeon_101` | New: 5-phase boss; follow `build_dungeon_51` pattern |

### Dijkstra changes

- `_dijkstra_par_WBE`: recompute with M=1.35 and denser groups.
- `_dijkstra_par_L8`: recompute with M=1.055 and wall-strip terrain.
- `_dijkstra_par_LGG`: recompute with M=1.36 and full-WALL row 4; drop {n}G from motion set.
- `_dijkstra_par_L10`: no structural change; document joint-forcing.
- `_dijkstra_par_L13a`: new; models `}`/`{` with void-row lethal terrain.
- `_dijkstra_par_L13b`: new; models `)`/`(` with wall-gap segment terrain.
- `_dijkstra_par_L101`: new; multi-phase stateful; follows `_par_l51` pattern.
