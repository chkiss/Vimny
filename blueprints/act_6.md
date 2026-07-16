# Act VI — Text Objects (Capstone) — Generator-Grade Blueprints (Revised)

> ⚠ **Pre-implementation design doc — obsolete conventions; delete-on-implement.** Uses pre-slug naming (e.g. `RuneCluster` → now `CharRun`; level numbers are now the cosmetic `display` field) — don't copy these symbols. **Delete a level's section when that level ships, and the whole file once its act is built.** See LEVELS_PLAN Part 8.

> Authority: LEVELS_PLAN.md §Act VI + §Part 3 + §Part 5; engine/text_object.py;
> engine/operator.py; generation/dungeon_gen.py.
>
> **Forcing model (S1–S5):**
> - S1: terrain-∞ first — prefer walls/void/water that make the alternative impossible.
> - S2: tighten budget — where margin-forcing is unavoidable use the minimum multiplier
>   that strictly eliminates the manual path; document the multiplier per level.
> - S3: par = true full min-keystroke entry→exit including all navigation and Esc.
>   Navigation credits `$` (1 key) and `0` (1 key) as known Act-I commands; all other
>   movement is individual keystroke-steps.  Exit navigation is ALWAYS counted.
> - S4: block earlier commands — `dw`/`d{motion}` bypasses `diw`/`daw`; design terrain
>   so each text object is strictly required (cursor position forced mid-cluster, or
>   content-size makes manual path impossible, or S1 wall forces exactly the right object).
> - S5 split: Sentence (`is as`) and Paragraph (`ip ap`) are distinct scanner families
>   and are taught in separate levels (L30 and L36).
>
> Operator keystrokes counted: `d`=1, `i`/`a`=1, object-char=1 → `diw`=3.
> `$`=1, `0`=1, each h/j/k/l-step=1.  `c`-operator escape=1 extra.
> Both the `i` and `a` variant of every text object must be independently FORCED.

---

> ✅ The Brace & Square Enclosure SHIPPED 2026-07-16 as display 34 (the actual
> build diverged from the old section: exact-text chassis, the nest chamber,
> par 45 — see `build_dungeon_brace_square_enclosure` + its tests). Sections
> below use the OLD numbering; current displays: Quote=35, Tag=36,
> Sentence=37, Paragraph=38, Grandmaster's Sanctum=38.1.

> ✅ The Quote Enclosure SHIPPED 2026-07-19 as display 35 (the actual build
> diverged from the old section: exact-text chassis, spine strikes via the
> quote objects' forward seek, the Vim-true a-quote whitespace quirk, the
> C5 first-pair trap, par 47 — see `build_dungeon_quote_enclosure` + its
> tests).

---

## Level 34 — The Tag Enclosure

**Commands introduced:** `it` `at`

**ENGINE STATUS — CHALLENGE:** `resolve_text_object` returns `None` for `'t'` (deferred in
`engine/text_object.py` line 306).  This level is designed GIVEN the prerequisite that `it`/`at`
are implemented.  A CHALLENGE is recorded for the human decision on when to implement them.

**New mechanics (≤3):**
1. Tag structure: `<tag>content</tag>` as a compound multi-glyph delimiter.
2. `it` — inner tag: content between `>` and `</tag>`.
3. `at` — around tag: content plus both tag delimiter clusters (`<tag>` and `</tag>`).

**Linkage:** Final bracket-family member; same i/a rule; new concept is multi-glyph delimiters.

**Revised design (review fixes):**
- Exit is placed at the END of the gate row (row 7), not below it, so the path is linear:
  row 2 tutorial → row 7 gate → X at (7, rightmost). No back-tracking navigation loop.
- `at` is forced by S1 wall_rune gate (same mechanism as L26/L28).
- `it` is forced by S2 (enclosures with enough goblins that `dit` beats manual).

---

### Grid  (12 rows × 48 cols)

```
################################################
#@............................................#
#.<b>ggg</b>.<em>gggg</em>..................#   row 2 — dit tutorial
#............................................#
##################################################
#............................................#
##################################################
#.<b>gggggg</b>..........................X..#   row 7 — dat gate; X at col 44
#............................................#
##################################################
#............................................#
##################################################
#............................................#
################################################
```

**Dims:** 12 rows × 48 cols.  `@`=(1,1), `X`=(7,44).

**Tag placement convention:** Tag glyphs (`<`, `b`, `>`, `<`, `/`, `b`, `>`) are individual
RuneCluster cells of kind='void' (passable) unless marked wall_rune (blocking).

---

### Row 2 — tutorial tags (dit forced by S2)

```
<b>ggg</b>    <em>gggg</em>
```

- `<b>` tag: `<` col 2, `b` col 3, `>` col 4.  Goblins at cols 5..7 (3).  `</b>`: cols 8..11.
- `<em>` tag: `<` col 13, `e` col 14, `m` col 15, `>` col 16.  Goblins at cols 17..20 (4).
  `</em>`: cols 21..25.
- `dit` from col 5 (inside `<b>`): selects cols 5..7, deletes 3 goblins.  Cost: 3 keys.
  Manual `xxx`: 3 keys (tie).  Step-in cost: player at col 2, `lll xxx` = 6 keys → `dit` wins 3.
  From col 2: `dit` = 3 (no step needed; engine scans for enclosing tag from cursor).
  From col 2: manual `lll xxx` = 6.  Saves 3 keys.
- `<em>gggg</em>` (4 goblins): `dit` = 3; manual `l xxxx` from col 13 = 5.  Saves 2 keys.
- Choke wall after `</b>` at (2,12): must clear `<b>ggg</b>` content before passing.
  `dit` clears goblins; tag glyphs are passable (void) → passage open after `dit`.

---

### Row 7 — dat gate (S1 forced)

```
<b>gggggg</b>   X (col 44)
```

- `<b>` (cols 2..4) and `</b>` (cols 8..12) are wall_rune entities.
- `dit` from col 5: clears goblins (cols 5..7) but tag wall_runes remain → blocked.
- `dat` from col 5: clears cols 2..12 including both tag wall_runes → passage opens.
- **S1 enforcement.**  X at (7,44): after `dat`, navigate `$` = 1 key.

---

### Par calculation (S3)

Optimal path:

1. Navigate @(1,1) → (2,2) [`<b>` start]: `j l` = 2 keys
2. `dit` `<b>ggg</b>`: 3 keys (from col 2; engine finds enclosing tag)
3. Navigate (2,2) → (2,13) [`<em>` start]: `11l` = 11 keys
4. `dit` `<em>gggg</em>`: 3 keys
5. Navigate (2,13) → (7,2) [gate `<b>`]: `5j 0 l` = 7 keys
   From (2,13): `5j`→(7,13); `0`→(7,1); `l`→(7,2) = 7 keys.
6. `dat` gate: 3 keys
7. Navigate (7,2) → (7,44) [X]: `$` = 1 key

**par = 2+3+11+3+7+3+1 = 30**

Manual alternative:
- `<b>ggg</b>` (3 goblins): from col 2, `lll xxx` = 6 (+3 vs `dit`=3).
- `<em>gggg</em>` (4 goblins): from col 13, `lll xxxx` = 7 (+4 vs `dit`=3).
- Gate: S1-forced (impossible without `dat`).
Manual total: 2+6+11+7+7+3+1 = 37.

**budget = ceil(30 × 1.4) = 42** — manual path (37) < 42.  S1 gate forces `dat`; `dit` forced by
how much manual exceeds par (7 key gap on just two enclosures).

Actually manual=37 < budget=42 — the ×1.4 budget allows the manual path!  The gap (37-30=7)
shows `dit` wins by 7 keys, but the budget permits up to 42.  This is fine because the player
can STILL complete within budget via manual; the game TEACHES by making `dit` clearly faster,
and `dat` is forced by S1 (not budget).

For genuine budget-forcing of `dit`, tighten: **budget = 36; multiplier ≈ ×1.2 (documented)**.
Manual (37) > budget (36) → `dit` is required on both enclosures.

**par = 30; budget = 36; multiplier = ×1.2 (documented — forces dit on both row-2 enclosures)**

**CHALLENGE (`it`/`at` engine prerequisite):** `it` and `at` return `None` in
`engine/text_object.py` (line 306).  A human developer must implement `_resolve_tag` before
this level can be built.  Implementation spec:
- Tag syntax on grid: `<X>content</X>` where X is a 1-3 char tag name; delimiters are
  multi-glyph rune clusters.
- `it` scanner: from cursor, walk left for `<` (start of open tag), right for `>` (end),
  then right past `>` for content start, right for `</` to find content end.
- `at`: same, includes the open and close tag clusters.

**Self-check (conditional on engine implementation):**
- [ ] `dit` from col 2 on `<b>ggg</b>` selects cols 5..7; tag glyphs at 2..4 and 8..11 remain.
- [ ] `dat` from col 2 on row-7 gate selects cols 2..12 (open-tag + content + close-tag);
      wall_rune entities at cols 2..4 and 8..12 are deleted → passage opens.
- [ ] X at (7,44): `$` from (7,2) after `dat` reaches the exit.
- [ ] par=30 verified (manual path from row-2 col 2 is 6 keys not 3 for 3-goblin tag).

**Primitives:** walls, floor, goblin entities, multi-glyph tag rune clusters (kind='void' for
passable; kind='wall_rune' for gate), choke corridors.

---

## Level 35 — The Sentence Enclosure

**Commands introduced:** `is` `as`

*(Split from original L30 per S5: sentence and paragraph are distinct scanner families.)*

**New mechanics (≤3):**
1. Sentence object concept: a punctuation-delimited run of runes within a row.
2. `is` — inner sentence: rune content between sentence boundaries (exclusive of period/punctuation).
3. `as` — around sentence: content plus the terminating punctuation and the following blank.

**Linkage:** `is`/`as` are the row-level analogue of `i"`/`a"` — punctuation plays the role of
delimiters.  Same i/a rule applied to a new scanner family (`_resolve_sentence`).

---

### Grid  (16 rows × 46 cols)

```
##############################################
#@..........................................#
#..Hello world.Fear not.Run fast...........#   row 2 — sentence row A
#..........................................#
##############################################
#..........................................#
##############################################
#..Darkness reigns.No hope left.Flee now...#   row 7 — sentence row B (as gate forced)
#..........................................#
##############################################
#..........................................#
##############################################
#..Yield.or.fall.away.from.here............#   row 12 — is/as distinction (period-choke)
#..........................................#
##############################################
#..........................................#
##############################################
#..........................................#
#........................................X.#   row 15 exit
##############################################
```

**Dims:** 16 rows × 46 cols.  `@`=(1,1), `X`=(15,42).

---

### Row 2 — tutorial sentences (dis forced by S2)

```
col 2..12: "Hello world"  col 13: "."  col 14..20: "Fear not"  col 21: "."  col 22..29: "Run fast"  col 30: "."
```

- Sentence 1: cols 2..12, period at col 13.
- Sentence 2: cols 14..20, period at col 21.
- Goblins embedded: one goblin entity at col 7 (mid "Hello world"), one at col 17 (mid "Fear not").
- `dis` from col 7: selects sentence 1 content (cols 2..12), deletes including goblin at 7.  Cost: 3.
  Manual: player at col 7; `x` kills goblin (1 key), but rune cluster at 2..6 and 8..12 remain
  (non-goblin runes are not single cells; `x` only removes the goblin entity, leaving rune glyph).
  Actually in Vimny, rune clusters are multi-cell entities; `x` on col 7 removes the goblin
  embedded at col 7 but the surrounding rune text (cols 2..6, 8..12) is a backdrop.
  `dis` removes the entire sentence content (all cells cols 2..12).  3 keys.
  Manual `dis` equivalent (no text object): navigate to each cell and `x` = 11 `x` presses = 11.
  `dis` saves 8 keys → strongly forced.
- Choke wall at (2,13) (the period): blocks passage to sentence 2.
  `dis` clears cols 2..12 but period at col 13 remains → choke still present.
  `das` from col 7: selects cols 2..13 (sentence + period) → clears choke. **S1-adjacent:** the
  period IS the wall_rune; `dis` is insufficient; `das` strictly required for forward passage.
  `das` = 3 keys (same cost as `dis`).

---

### Row 7 — second sentence row (is forced, as reinforced)

```
"Darkness reigns"  "."  "No hope left"  "."  "Flee now"  "."
```

- Goblin at mid "Darkness reigns" col ~10.  Goblin at mid "No hope left" col ~25.
- `dis` from col 10: clears sentence 1 (all rune content).  3 keys vs 14 manual = 11 keys saved.
- Period at each sentence boundary: no choke this time (periods are passable).
- `dis` is sufficient; `das` is not required (optional if player wants to clear period cell too).
- This row reinforces `is` and lets the player see `as` is optional when period is not a choke.

---

### Row 12 — is/as distinction (period-choke forced, S1)

```
col 2: "Yield"  col 7: "."  col 8: "or"  col 10: "."  col 11: "fall"  ...
```

- Period at col 7 is a wall_rune entity.  Player must clear sentence 1 ("Yield", cols 2..6) AND
  the period (col 7) to pass.
- `dis` from col 4: selects cols 2..6 ("Yield" inner content). Period at col 7 remains → blocked.
- `das` from col 4: selects cols 2..7 (sentence + period). Wall_rune at col 7 deleted → passage.
- **S1 enforcement:** `das` strictly required.

---

### Par calculation (S3)

Optimal path:

1. Navigate @(1,1) → (2,7) [goblin in sentence 1]: `j 6l` = 7 keys
2. `das` sentence 1 (clears content + period choke): 3 keys
3. Navigate (2,2) → (2,17) [goblin in sentence 2, col 17]: `15l` = 15 keys
   After `das`, cursor lands at col 2; sentence 2 goblin is at col 17: `15l` = 15 keys.
   Better: after `das` from col 7, the sentence-1 text is deleted; cursor at col 2; `$` to
   col 13 (period gone, new rightmost); then walk right... This is complex; use `15l` = 15.
   Actually after deleting cols 2..13, col 14 is now at the same position; `15l` is wrong.
   Use: after `das`, cursor at col 2; goblin at original col 17 is now shifted left by 12 cols
   to col 5 (if runes shift). This depends on engine line-shift behavior.
   **Design decision: assume rune positions do NOT shift (engine deletes cells, leaves gaps as
   floor).** Goblin at col 17 stays at col 17 after deletion of cols 2..13.  So `15l` = 15 keys
   from col 2 to col 17.
4. `dis` sentence 2 (clears goblin at 17): 3 keys
5. Navigate (2,17) → (7,10) [goblin in row 7 sentence 1]: `5j 7h` = 12 keys
6. `dis` row-7 sentence 1: 3 keys
7. Navigate (7, ~col 2) → (12,4) [sentence start, row 12]: `5j 2l` = 7 keys
8. `das` row-12 sentence 1 + period: 3 keys
9. Navigate (12,2) → (15,42) [exit]: `3j $` = 4 keys

**par = 7+3+15+3+12+3+7+3+4 = 57**

The large navigation numbers (step 3: 15 keys; step 5: 12 keys) are honest S3 counts.
To reduce par, compact the grid horizontally:

**Revised compact grid — 16 rows × 36 cols:**

Row 2: `..S1.S2.S3.` with S1 = 5-char sentence at col 2..6, period col 7, S2 at col 8..12,
period col 13, S3 at col 14..18, period col 19.

Goblins at col 4 (mid S1) and col 10 (mid S2).

Revised par:

1. `j 3l` → (2,4): 4 keys
2. `das` S1 (cols 2..7): 3 keys
3. Navigate (2,2) → (2,10) [goblin mid S2]: `8l` = 8 keys
4. `dis` S2: 3 keys
5. Navigate (2,8) → (7,5) [row 7 sentence 1 goblin at col 5]: `5j 3h` = 8 keys
6. `dis` row-7 S1: 3 keys
7. Navigate (7,2) → (12,4): `5j 2l` = 7 keys
8. `das` row-12 S1 + period: 3 keys
9. Navigate (12,2) → (15,32) [exit, compact grid]: `3j $` = 4 keys

**par = 4+3+8+3+8+3+7+3+4 = 43**

Manual alternative (no text objects — just `x` per goblin):
- Step 2: goblin at col 4; `x` = 1 key (removes goblin); choke at col 7 (wall_rune period) remains.
  To clear choke without `das`: impossible by `x` (period is wall_rune, not a goblin).
  **S1: `das` is the ONLY way to clear the period wall_rune.**  Manual path cannot complete level.
- Therefore forceability is S1-driven: `das` is mandatory.

For `dis` (row 2, S2): goblin-clearing only. `x` = 1 key (goblin only). `dis` = 3 keys.
Manual is cheaper for single-goblin sentences.  **Solution:** use sentences with ≥5 goblins so
`dis` (3 keys) beats `xxxxx` (5+ keys).

**Revised row-2 S2 and row-7:** pack 5 goblin entities per sentence.

Revised par (with 5-goblin sentences, goblin entities at cols 8..12 of S2, etc.):
- `dis` on 5-goblin S2 = 3 keys; `xxxxx` = 5 keys.  `dis` wins by 2.
- `das` on S1 is S1-forced regardless.

Revised par stays approximately the same; manual path is longer by 2 (using `xxxxx` instead of
`dis` for 5-goblin sentences) per such sentence.  At ×1.2 multiplier, the gap closes in.

**par = 43; budget = ceil(43 × 1.2) = 52 (documented — `dis` on 5-goblin sentences forced by
margin; `das` forced by S1 wall_rune period)**

**Self-check:**
- [ ] `_resolve_sentence` on row 2 identifies sentence boundaries at period positions.
- [ ] `dis` from col 4 on sentence 1 (cols 2..6) selects cols 2..6; period at col 7 NOT included.
- [ ] `das` from col 4 on sentence 1 selects cols 2..7 (sentence + period); wall_rune at 7 cleared.
- [ ] `dis` on 5-goblin sentence: clears 5 entities in 3 keystrokes vs 5 `x` presses.
- [ ] par=43 verified; budget=52 forces `dis` on 5-goblin sentences (manual=53 or more exceeds budget).

**Primitives:** walls, floor, rune clusters with embedded goblin entities (sentence content),
wall_rune period entities (S1 choke), corridor.

---

## Level 36 — The Paragraph Enclosure

**Commands introduced:** `ip` `ap`

*(New level, split from original L30 per S5.)*

**New mechanics (≤3):**
1. Paragraph object: a blank-row-delimited block of rows.
2. `ip` — inner paragraph: the content rows (exclusive of blank-row boundaries).
3. `ap` — around paragraph: content rows PLUS the following blank boundary row.

**Linkage:** Same i/a rule applied to the linewise/multi-row domain.  Blank rows play the role
of delimiter glyphs.  `_resolve_paragraph` uses `_row_blank` to detect boundaries — distinct
from `_resolve_sentence` (punctuation-based).

---

### Grid  (28 rows × 36 cols)

```
####################################
#@..................................#
####################################
#...................................#
#.gggggg............................#   row 4 — P1 content row 1 (6 goblins)
#.gggggg............................#   row 5 — P1 content row 2
#.gggggg............................#   row 6 — P1 content row 3
#...................................#   row 7 — blank separator (paragraph boundary)
#.gggggg............................#   row 8 — P2 content row 1
#.gggggg............................#   row 9 — P2 content row 2
#.gggggg............................#   row 10 — P2 content row 3
#...................................#   row 11 — blank separator with void-rune hazard
####################################
#...................................#
####################################
#...................................#   (corridor section)
#...................................#
####################################
#...................................#
#.gggggg............................#   row 19 — P3 content row 1 (6 goblins)
#.gggggg............................#   row 20 — P3 content row 2
#.gggggg............................#   row 21 — P3 content row 3
#...................................#   row 22 — blank separator
####################################
#...................................#
####################################
#...................................#
#.................................X.#   row 27 exit
####################################
```

**Dims:** 28 rows × 36 cols.  `@`=(1,1), `X`=(27,33).

---

### Paragraph P1 — dip forced (S2: 18 goblins vs 18 x-presses)

Rows 4..6, 6 goblins per row = 18 goblins total.

- `dip` from row 5 (inside P1): selects rows 4..6 linewise, deletes all 18 goblins.  Cost: 3.
- Manual `x`×18 = 18 keys.  `dip` saves 15 keys.  Overwhelmingly forced.
- Blank row 7 is the paragraph boundary (`_row_blank` returns True for row 7).

---

### Paragraph P2 — dap forced by void-rune hazard (S1 mechanism)

Rows 8..10, 6 goblins per row = 18 goblins.  Blank row 11 has void-rune hazard clusters at
cols 2..5 (lethal if stepped on).

- `dip` from row 9: selects rows 8..10, deletes goblins.  Blank row 11 survives → void-rune
  hazard at row 11 is still present; player walking down to the corridor is killed.
- `dap` from row 9: selects rows 8..11 (P2 content + blank boundary), deletes all 18 goblins
  AND row 11 (including the void-rune hazard) → safe passage to corridor.
- **S1 enforcement:** `dip` leaves lethal hazard; `dap` removes it.  `dap` strictly required
  to survive.  Cost: 3 keys (same as `dip`; safety gates the choice).

---

### Paragraph P3 — dip sufficient (teaches contrast)

Rows 19..21, 6 goblins per row.  Blank row 22 has no hazard.

- `dip` from row 20: selects rows 19..21, deletes 18 goblins.  Cost: 3.
- `dap` also works but includes blank row 22 (no hazard there).
- Player learns: `dip` is sufficient when blank row is safe; `dap` was needed for P2.

---

### Par calculation (S3)

Optimal path:

1. Navigate @(1,1) → (2,1) room entry (wall row 2): 0 — already inside room at (1,1).
   Actually grid has row 0 = wall, row 1 = `#@...#`, row 2 = wall, row 3 = blank, rows 4..6 = P1.
   Navigate (1,1) → (5, 1) [mid P1, row 5]: `j` (to row 2 wall — blocked).

**Grid redesign note:** The double-wall rows (rows 0,2 and similar) create impassable barriers.
Redesign: single-wall rows, open floor corridors:

```
Row 0: wall
Row 1: #@... (start room)
Row 2: #...  (floor — open)
Row 3: #ggg  (P1 row 1)
Row 4: #ggg  (P1 row 2)
Row 5: #ggg  (P1 row 3)
Row 6: #...  (blank boundary — paragraph separator)
Row 7: #ggg  (P2 row 1)
Row 8: #ggg  (P2 row 2)
Row 9: #ggg  (P2 row 3)
Row 10: #...+void  (blank boundary with hazard)
Row 11: wall
Row 12: #...  (corridor)
Row 13: wall
Row 14: #...  (corridor)
Row 15: wall
Row 16: #...  (corridor)
Row 17: wall
Row 18: #...  (open)
Row 19: #ggg  (P3 row 1)
Row 20: #ggg  (P3 row 2)
Row 21: #ggg  (P3 row 3)
Row 22: #...  (blank boundary — no hazard)
Row 23: wall
Row 24: #...  (corridor to exit)
Row 25: wall
Row 26: #...X (exit row)
Row 27: wall
```

Revised par:

1. Navigate (1,1) → (4,1) [P1 row 1]: `3j` = 3 keys
2. `dap` P1 (rows 3..6 including blank): 3 keys
   Wait — P1 is rows 3..5 (content); blank is row 6.  `dap` from row 4 selects rows 3..6.
   Use `dip` here if blank row 6 has no hazard.  Design: blank row 6 has no hazard → `dip` ok.
   Actually for consistent teaching: use `dip` on P1 (simple), `dap` on P2 (hazard gate), `dip` on P3.
3. `dip` P1 (rows 3..5): 3 keys.  Cursor lands at row 3.
4. Navigate (3,1) → (8,1) [P2 row 2, mid-paragraph]: `5j` = 5 keys
5. `dap` P2 + hazard blank (rows 7..10): 3 keys.  Cursor lands at row 7.
6. Navigate (7,1) → (19,1) [P3 row 1]: `12j` = 12 keys (through corridors at rows 11..18).
   This is long; compact the grid by reducing corridor rows.
   **Revised: corridor section is 2 rows (rows 11..12 = wall, 13..14 = floor corridor).**
   Actually keep corridor at ~4 rows (wall-floor-wall-floor) for visual clarity.
   Corridor rows: 11=wall, 12=floor, 13=wall, 14=floor... use just 2 corridor rooms = ~6 rows.
   Let P3 start at row 17:
7. Navigate (7,1) → (17,1) [P3 row 1]: `10j` = 10 keys
8. `dip` P3 (rows 17..19): 3 keys. Cursor at row 17.
9. Navigate (17,1) → (26,33) [exit]: `9j $` = 10 keys

**par = 3+3+5+3+10+3+10 = 37**

Manual alternative:
- P1 (18 goblins): `18x` = 18 keys vs `dip` = 3.  Gap = 15.
- P2 (18 goblins + void hazard): `18x` removes goblins, void hazard remains → death.
  `dap` is S1-forced.
- P3 (18 goblins): `18x` = 18 vs `dip` = 3.  Gap = 15.
Manual (manual P1 + S1 on P2 + manual P3): 3+18+5+3+10+18+10 = 67.

**budget = ceil(37 × 1.4) = 52** — manual path (67) >> budget (52).  The paragraph object is
overwhelmingly forced by S2 (18 goblins per paragraph); S1 forces `dap` on P2.

**par = 37; budget = 52; multiplier = ×1.4 (standard — text-object advantage is huge)**

**Self-check:**
- [ ] `_row_blank(room, 6)` returns True (floor cells, no rune entities → paragraph boundary).
- [ ] `_resolve_paragraph` from row 4: finds blank at row 6 below, blank at row 2 above;
      `ip` → rows 3..5; `ap` → rows 3..6.
- [ ] `dap` from row 8 on P2: selects rows 7..10 (content + void-hazard blank row); void-rune
      hazard at row 10 deleted → safe floor.
- [ ] `dip` from row 8 on P2: selects rows 7..9 only; void-hazard at row 10 survives → death.
- [ ] 18 goblins × 3 paragraphs = 54 goblin entities; `dip`/`dap` × 3 = 9 keystrokes total.
- [ ] Manual (54 `x` presses) = 54 >> budget=52; well-forced.

**Primitives:** walls, floor, blank rows (paragraph boundaries, passable, no rune entities),
void-rune hazard cluster (S1 forcing on blank row for P2), goblin entities in paragraph rows,
corridor between P-sections.

---

## Level 36.1 — The Grandmaster's Sanctum (FINAL BOSS)

**Commands exercised:** `diw` `daw` `di(` `da(` `da[` `da{` `di"` `da"` `da'` `dit` `dat`
`dis` `das` `dip` `dap` `ci"` — full text-object grammar.

**New mechanics (≤3):**
1. Phase barriers: wall rows that open when all entities in a phase section are cleared.
2. Defuse scrolls: read-on-step hints revealing which operator+object to use (tutorial only).
3. Warden entity (Warden kind): high-HP, stationary, guards the final crystal.

**Linkage:** Synthesises all six text-object families (word, parens, brace/square, quote, tag,
sentence, paragraph).

**Revised design (review fixes):**
- `a[` and `a{` now appear in Phase 3 (previously absent from both the level and the boss).
- Phase 4 key count corrected to 8 (was inconsistently listed as 6 in the phase table).
- Phase 4 uses a dedicated `da[` sub-puzzle AND a `da{` sub-puzzle to ensure both `a[`/`a{`
  are exercised.
- Phase 6 split into Phase 6a (`is`/`as`) and Phase 6b (`ip`/`ap`) matching the L30/L36 split.

---

### Boss Grid  (48 rows × 80 cols)

```
Phase 1 (rows 3..5):   Word — iw/aw
Phase 2 (rows 7..10):  Parens — di(/da(
Phase 3 (rows 12..17): Brace/Square — di{/da{/di[/da[ (all four required)
Phase 4 (rows 19..22): Quote — di"/da"/ci" defuse
Phase 5 (rows 24..27): Tag — dit/dat [CHALLENGE: engine prerequisite]
Phase 6a (rows 29..32): Sentence — dis/das
Phase 6b (rows 34..37): Paragraph — dip/dap
Final (rows 39..46):   All — mixed guardians + Warden
```

**Dims:** 48 rows × 80 cols.  `@`=(1,1), `X`=(47,78).

---

### Phase Table

| Phase | Rows    | Text Object(s)           | Puzzle Pattern                                                | Key Command(s)       | Keys (optimal) |
|-------|---------|--------------------------|---------------------------------------------------------------|----------------------|----------------|
| 1     |  3..5   | `iw` / `aw`              | `[run][_][away]` — `daw` clears word+blank choke; `diw` needed for second word | `daw` `diw`    | 3+3=6     |
| 2     |  7..10  | `di(` / `da(`            | `(ggg)` void delimiter + `(ggggg)` wall_rune gate             | `di(` `da(`          | 3+3=6          |
| 3a    | 12..14  | `di[` / `da[`            | `[ggg]` void + `[ggggg]` wall_rune gate                       | `di[` `da[`          | 3+3=6          |
| 3b    | 15..17  | `di{` / `da{`            | `{ggg}` void + `{ggggg}` wall_rune gate                       | `di{` `da{`          | 3+3=6          |
| 4     | 19..22  | `di"` / `da"` / `ci"`   | `"gg"` void + `"ggggg"` wall_rune gate + `"defuse"` bomb      | `di"` `da"` `ci"safe`+Esc | 3+3+8=14 |
| 5     | 24..27  | `dit` / `dat`            | `<b>ggg</b>` void + `<b>ggggg</b>` wall_rune gate            | `dit` `dat`          | 3+3=6 *CHALLENGE* |
| 6a    | 29..32  | `dis` / `das`            | 5-goblin sentences + period wall_rune choke                   | `dis` `das`          | 3+3=6          |
| 6b    | 34..37  | `dip` / `dap`            | 18-goblin paragraph + void-hazard blank row                   | `dip` `dap`          | 3+3=6          |
| Final | 39..46  | All (mixed)              | `(gg)"gg"[gg]{gg}<b>g</b>` + Warden + `da[` `da{` guardians | all + `5x`           | ~30            |

---

### Phase 3 detail — `da[` and `da{` forced (new in this revision)

**Phase 3a (rows 12..14):**

```
Row 13: ..[ggg]...   (void [ delimiters; di[ only needed)
         ..[ggggg].  (wall_rune [ delimiters; da[ required)
```

- Sub-puzzle A: `[ggg]` with void delimiters — `di[` clears goblins (3 keys).
- Sub-puzzle B: `[ggggg]` with wall_rune `[` and `]` — `da[` required (3 keys, S1-forced).
- Phase barrier at row 14 drops when both sub-puzzles cleared.

**Phase 3b (rows 15..17):**

```
Row 16: ..{ggg}...   (void { delimiters)
         ..{ggggg}.  (wall_rune { delimiters; da{ required)
```

- Same structure; forces `di{` then `da{`.

This ensures all four of `i[` `a[` `i{` `a{` are exercised in the boss, not just `i[` and `i{`.

---

### Phase 4 detail — `ci"` defuse (correctness gate)

- `"gg"` enclosure (void delimiters): `di"` clears 2 goblins. 3 keys.
- `"ggggg"` enclosure (wall_rune `"`): `da"` clears goblins + delimiters. 3 keys.
- Bomb puzzle: void-rune cluster labeled `"defuse"` on a pressure plate at (21, 10..17).
  Stepping on plate activates bomb timer (3 turns).
- `ci"` from col 10: enters change mode inside `"` pair, selects `defuse` (cols 11..16),
  deletes it, puts player in insert mode.  Player types `safe` (4 keys) + `Esc` (1 key).
  Total: `ci"` (3) + `safe` (4) + `Esc` (1) = **8 keys**.
- `di"` kills content but does not place a replacement rune → bomb not defused.  Only `ci"` +
  replacement text deactivates the timer.  **Correctness gate (not budget-gated).**

**Phase 4 key count: 3 + 3 + 8 = 14 keys optimal.**

---

### Phase 5 detail — CHALLENGE

Phase 5 (`dit`/`dat`) requires the `_resolve_tag` engine implementation.
**CHALLENGE:** Until `it`/`at` are implemented, Phase 5 cannot be tested or generated.
Design GIVEN the prerequisite; record as a blocking CHALLENGE.

If `it`/`at` remain unimplemented when the boss is built, Phase 5 can be temporarily replaced
with a repeat of Phase 3b (`da{`) or a `da'` (single-quote) gate as a placeholder.

---

### Boss par calculation (S3)

| Phase | Navigate | Commands | Total |
|-------|----------|----------|-------|
| 1     | 3        | 6        | 9     |
| 2     | 4        | 6        | 10    |
| 3a    | 4        | 6        | 10    |
| 3b    | 4        | 6        | 10    |
| 4     | 4        | 14       | 18    |
| 5     | 4        | 6        | 10    |
| 6a    | 4        | 6        | 10    |
| 6b    | 4        | 6        | 10    |
| Final | 6        | 30       | 36    |
| Between-phase nav (barrier rows × 8 phases × ~4j) | 32 | — | 32 |

**par = 9+10+10+10+18+10+10+10+36+32 = 145**

Wait — the between-phase navigation of 32 keys is already partially included in each phase's
"navigate" row.  Separate the inter-phase corridor navigation (moving from the end of one phase
to the start of the next, ~4 rows each, 8 transitions = 32 steps) from the intra-phase navigation
(moving to the puzzle positions within a phase).

**par = (9+10+10+10+18+10+10+10+36) + 32 = 113 + 32 = 145**

**budget = ceil(145 × 1.4) = 203**

The large par reflects the genuine complexity of 8 phases + final chamber. The ×1.4 budget
gives 58 slack keys — enough for player disorientation but not systematic avoidance.

---

**Self-check:**
- [ ] Phase 3a: `da[` required to clear wall_rune `[` gate; `di[` leaves wall_rune → blocked.
- [ ] Phase 3b: `da{` required to clear wall_rune `{` gate; `di{` leaves wall_rune → blocked.
- [ ] Phase 4 `ci"`: 3+4+1 = 8 keys in phase table (corrected from previous 6).
- [ ] Phase 5: marked CHALLENGE (engine `it`/`at` prerequisite).
- [ ] Final chamber includes at least one encounter requiring `da[` and one requiring `da{`
      (to ensure these commands appear if Phase 3 is the only other place they're exercised).
- [ ] par=145 verified by summing table rows; budget=203.

**Primitives:** walls, floor, phase-barrier walls (drop on trigger), Warden entity
(max_hp=5, ai='stationary'), goblin entities, void-rune delimiter glyphs (passable), wall_rune
delimiter entities (S1 gates in each phase), bomb timer entity (Phase 4), pressure plate,
defuse-check (rune kind ≠ 'void' after ci"), defuse scroll hints.

---

## Summary Table

| Level | Name                          | Commands              | par | budget | Multiplier | Both i AND a forced? | Residual Challenge                              |
|-------|-------------------------------|-----------------------|-----|--------|------------|----------------------|-------------------------------------------------|
| 30    | The Word Enclosure            | `iw` `aw`             |  30 |     41 | ×1.35      | Yes (S1 void+S1 wall-blank) | None — S1 terrain fully forces both      |
| 31    | The Bracket Enclosure         | `i(` `a(`             |  33 |     34 | ×1.03      | Yes (S1 gate + S2 enclosures) | CHALLENGE: budget ×1.03 is very tight; designer may add a 4th enclosure |
| 32    | The Brace & Square Enclosure  | `i[` `a[` `i{` `a{`  |  35 |     49 | ×1.4       | Yes (S1 gates for all four) | None — S1 gates force all four variants   |
| 33    | The Quote Enclosure           | `i"` `a"` `i'` `a'`  |  36 |     37 | ×1.03      | Yes (S1 gates for " and ') | CHALLENGE: budget ×1.03 very tight; designer may add enclosures |
| 34    | The Tag Enclosure             | `it` `at`             |  30 |     36 | ×1.2       | Yes (S1 gate for at; S2 for it) | CHALLENGE (blocking): `it`/`at` unimplemented in engine |
| 35    | The Sentence Enclosure        | `is` `as`             |  43 |     52 | ×1.2       | Yes (S1 period wall_rune; S2 5-goblin sentences) | None — S1 fully forces `as`; S2 forces `is` |
| 36  | The Paragraph Enclosure       | `ip` `ap`             |  37 |     52 | ×1.4       | Yes (S1 void-hazard blank; S2 18-goblin paras) | None — S1+S2 fully force both             |
| 36.1  | The Grandmaster's Sanctum     | all text objects      | 145 |    203 | ×1.4       | Yes (all phases) | CHALLENGE: Phase 5 blocked by `it`/`at` engine prereq |

---

## Challenges Requiring Human Decision

1. **`it`/`at` engine implementation (P0 — blocking):** `resolve_text_object` returns `None`
   for `'t'` (tag objects) in `engine/text_object.py` line 306. Levels 29 and Boss Phase 5
   cannot be generated or tested until a developer implements `_resolve_tag`. Decision needed:
   which sprint implements this? Is a placeholder phase acceptable for the boss?

2. **L26 budget tightness (×1.03):** The `di(` vs `lxxx` margin is 1 key per enclosure.
   Three enclosures give a 3-key gap (manual=35, budget=34). At ×1.03 a single accidental
   keystroke causes failure. Decision: (a) accept ×1.03 with the three-enclosure layout,
   (b) add a 4th enclosure (widens gap to 4 keys, budget ≤ 37 at ×1.03 still forces it), or
   (c) accept ×1.4 and treat `di(` on row-2 enclosures as pedagogical (not budget-forced)
   while relying on S1 gate (`da(`) for the mandatory command.

3. **L28 budget tightness (×1.03):** Same issue as L26 — `di"` / `di'` vs step-in-manual is
   a 1-key gap per enclosure. Decision: (a) accept ×1.03, (b) add more enclosures per row to
   widen gap, or (c) accept ×1.4 with S1 gates carrying the `da"`/`da'` forcing.

4. **L26/L28 wall_rune delimiter entity implementation:** The forcing mechanism for `da(`,
   `da"`, `da'` requires that `(` / `"` / `'` glyphs can be marked as `kind='wall_rune'`
   (blocking), distinct from `kind='void'` (passable). Confirm this entity-kind distinction
   exists in the engine before generating these levels.

5. **Boss Phase 4 bomb-timer mechanic:** The `ci"` defuse puzzle requires a bomb timer entity
   (pressure plate → countdown → explosion) and a defuse-check (rune placed by `ci"` must be
   `kind ≠ 'void'`). This is a new game primitive not yet confirmed in the engine. Decision:
   implement bomb-timer entity, or replace Phase 4 with a simpler `ci"` puzzle (e.g., a
   locked door that opens only when the inner content of a quote enclosure is changed to a
   specific rune).

6. **`$` as navigation shortcut in par counts:** All par calculations credit `$` (go to end of
   line) as 1 keystroke (known Act-I command). If the engine's Dijkstra solver does NOT model
   `$`, the actual par values may differ from generator output. Decision: ensure the par solver
   includes `$` and `0` as navigation options, or recompute all exit-navigation steps without `$`.
