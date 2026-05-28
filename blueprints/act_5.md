# Act V Blueprints — Insert-Mode Construction & Editing

> Generator-grade ASCII blueprints for levels 20–24b + boss 24.1.
> Each section is a complete spec for `build_dungeon_N()` in `generation/dungeon_gen.py`.
> Dims = (rows × cols). @ = entry, X = exit, K = keystone, D = door, g = goblin, W = warden.
> Par-solver assumptions are stated explicitly in each section.
> S1: terrain-∞ forcing preferred over budget-margin forcing.
> S2: tight-budget fallback: r/R levels use ×1.2, Esc counts as 1 keystroke; document multiplier.
> S3: par = true full min-keystroke solution (entry→exit, all navigation, all Esc).
> S4: earlier-act commands blocked by terrain where needed.

---

## L20 — The Inscription Halls

**Commands taught:** `i` (insert before cursor), `a` (insert after cursor).
New mechanics (count: 2):
1. Insert mode — pressing `i` or `a` enters INSERT; printable keys write runes on passable cells; `Esc` returns to NORMAL.
2. Rune inscription — a blank corridor cell can be filled with a required glyph to satisfy a door trigger; the door unlocks when the target rune lands at exactly the trigger cell.

**Linkage:** Both `i` and `a` differ only in where they begin writing relative to the cursor: `i` writes at the cursor cell, `a` writes at cursor+1. They are the same mechanic at different offsets — the minimal coherent pair.

**Budget multiplier: ×1.4. Esc counts as 1 keystroke.**

---

### Grid

**Dims:** 12 rows × 40 cols

**Final precise grid:**

```
Row  0: ########################################
Row  1: #@......................................#
Row  2: #.##############################.......#
Row  3: #.#..............................#.....#
Row  4: #.#..............................#.....#
Row  5: #.#..............................D1....#
Row  6: #.##############################.......#
Row  7: #......................................#
Row  8: #....K2................................#
Row  9: #......................................#
Row 10: #.....................................X#
Row 11: ########################################
```

**Placements:**
- `@` entry: (1, 1).
- `X` exit: (10, 38).
- Inner room: rows 2–6, cols 1–32 (walls at boundary; floor cells rows 3–4, cols 2–31).
- `K1` keystone: (1, 38) — activates D1 condition check. Reached via outer corridor (rows 1, 7–10).
- `D1` door: (5, 32) — opens when K1 active AND rune cluster at row 3, cols 10–12 equals `∆∆∆` (triple glyph, so misplaced runes can't accidentally satisfy it) AND rune `Ω` at trigger cell (4, 20).
- `i`-trigger: (4, 10) — player must position cursor at (4, 10) and type `i ∆ ∆ ∆ Esc`. Runes land at cols 10, 11, 12. Three-glyph target so `a` from (4,10) would land runes at 11,12,13 — all three off.
- `a`-trigger: (4, 19) — player must position cursor at (4, 19) and type `a Ω Esc`. Rune `Ω` lands at col 20. Using `i` from col 19 places rune at col 19, not 20 — door stays locked.
- Rune decoration row 3, cols 5–8: `"i→"` (ancient, read-only, not a trigger).
- Rune decoration row 3, cols 15–18: `"a→"` (ancient, read-only).
- `K2` keystone: (8, 5) — activates D2.
- `D2` door: (10, 35) — opens when K2 active. Simple key-activated door; no rune trigger (keeps budget from bloating further).

**NOTE — why three-glyph `i`-trigger:** a single glyph `∆` using `a` from position 10 lands one cell off; a player could simply try `a`, see failure, then reposition and try `i` — but with only a 1-glyph target this costs 1 extra key only. A 3-glyph burst (via `i ∆∆∆ Esc` vs `a ∆∆∆ Esc`) shifts the entire cluster by 1 col. With a 3-glyph target the wrong command misses every cell of the cluster, and repositioning + retrying costs +3 keys (move + correct command + Esc). This firms the forcing.

**Wrong-command analysis (S2 forcing):**
- Wrong command on `i`-trigger: cursor at (4,10), uses `a ∆∆∆ Esc` → runes at cols 11,12,13; trigger needs 10,11,12. Must reposition: `h i ∆∆∆ Esc` → +1 extra key = total +1 per trigger. With two triggers: +2.
- Wrong command on `a`-trigger: cursor at (4,19), uses `i Ω Esc` → rune at col 19; needs col 20. Must reposition: `l a Ω Esc` → +1 extra key.
- Both wrong: par + 2. Budget must be par+1 to force. **Budget = par + 1 → set par first.**

**Optimal keystrokes (S3 full recount):**
1. Navigate to K1 (1,38): from (1,1), `37l` = 3 keys (`3`,`7`,`l`). `x` = 1.
2. Navigate to inner room `i`-trigger (4,10): `3j 28h` = `3j`=2, `28h`=3 = 5 keys.
3. `i ∆ ∆ ∆ Esc` = 6 keys (`i`, `∆`, `∆`, `∆`, `Esc`). (Three glyphs to make the trigger robust.)
4. Navigate to `a`-trigger (4,19): `9l` = 2 keys.
5. `a Ω Esc` = 3 keys.
6. Exit inner room, navigate to K2 (8,5): `4j 14h` = `4j`=2, `14h`=3 = 5 keys. `x` = 1.
7. Navigate to exit (10,38): `2j 33l` = `2j`=2, `33l`=3 = 5 keys.

**Par: 3+1+5+6+2+3+5+1+5 = 31 keystrokes.**
**Budget: ceil(31 × 1.4) = ceil(43.4) = 44 keystrokes.**

**Forcing verification (S2):**
- Wrong on `i`-trigger: +1 key. Wrong on `a`-trigger: +1 key. Both wrong: par+2 = 33 ≤ 44. **NOT forced by budget alone.**
- Add a second pair of triggers (rows 3 inner, same approach): four triggers total. Both `i`-triggers at cols 10 and a second location; both `a`-triggers at two locations. Wrong on all four: +4 keys → par+4 = 35 ≤ 44. Still not forced at ×1.4.
- **S1 terrain fix (adopted):** The inner room has void runes at cols 9 and 11 flanking the `i`-trigger cell col 10, and void runes at cols 20 and 22 flanking the `a`-trigger cell col 20 (but col 19 the cursor position is safe). The void placement means: if `a` is used from col 10, the rune lands at col 11 which is a void — player takes void damage = level fails immediately. If `i` is used from col 19, rune lands at col 19 ≠ trigger col 20, and player cannot step to col 20 through the void at col 20... Actually: simpler approach: wall cells at col 9 and col 13 force the cursor to stand exactly at col 10 for the first trigger (walls left and right bound the 3-cell slot); wall cells at col 18 and col 22 bound the second trigger slot forcing cursor at col 19.
- **Terrain-forced rule for `i`:** The `i`-trigger slot cols 10–12 is preceded by a wall at col 9 (forcing entry from left only, cursor arrives at col 10 from the wall gap), and followed by a wall at col 13. Player enters the slot at col 10. `i` writes at col 10 — correct. `a` writes at col 11 — off by one, trigger fails, rune at wrong cell, door locked. No repositioning possible without backing out through the wall gap (costly). This is terrain-guided; undo is available but costs +2 (undo + redo correctly), which is within ×1.4. **So terrain doesn't give infinite forcing for `i`/`a` — the commands differ by only 1 cell.**
- **Final approach:** Use the ×1.4 budget with par=31, budget=44, and TWO triggers with a total wrong-command penalty of +2 (not enough alone), PLUS add 2 more `i`/`a` trigger pairs (total 4 triggers) making wrong-command total penalty +4 → par+4=35 ≤ 44. This still doesn't force. **Switch to: 8 triggers (4 `i`, 4 `a`) in a longer inner corridor, wrong penalty = +8 → par_extended+8 must exceed budget.** Revised par with 8 triggers: navigation grows, par≈42, budget=ceil(42×1.4)=59. Wrong-all: 42+8=50 ≤ 59. Still not enough.
- **Root issue:** At ×1.4 the wrong-by-1 penalty per trigger is too small. **Decision: tighten multiplier to ×1.15 for L20.** Par=31, budget=ceil(31×1.15)=ceil(35.65)=36. Wrong on both triggers: 31+2=33 ≤ 36. Still not enough. Wrong on four triggers: 31+4=35 ≤ 36. Still not. Five triggers: 31+5=36 = budget. Need 6 triggers: 31+6=37 > 36. **Six triggers (3 `i`, 3 `a`) with ×1.15 budget forces.** But ×1.15 requires documentation and is non-standard.
- **Cleaner design (adopted):** Use the 3-glyph `i`-trigger (costs 5 keys total: `i ∆∆∆ Esc`) and 1-glyph `a`-trigger (costs 3 keys: `a Ω Esc`). Wrong on `i`-trigger (use `a ∆∆∆ Esc` at cursor col 10): runes land at 11,12,13; correct need 10,11,12. Player must undo, move left 1, redo: `u h i ∆∆∆ Esc` = 5+3=8 keys vs 5 correct = +3 per trigger. Two `i`-triggers: +6. One `a`-trigger with +1 penalty. Three total triggers: wrong-all penalty = +7. Par with 3 triggers ≈ 31+5+3=39 (extra trigger traversal). Budget=ceil(39×1.4)=55. Wrong-all: 39+7=46 ≤ 55. **×1.4 still too loose.**
- **Final decision (adopted):** Budget multiplier ×1.2 for L20 (same as L22, justified by the "wrong-by-1" penalty being inherently small for `i`/`a`). Par=31, budget=ceil(31×1.2)=38. Two triggers (+2 wrong penalty): 31+2=33 ≤ 38. Still not forced at 2 triggers. Four triggers (+4): 35 ≤ 38. Five triggers (+5): 36 ≤ 38. Six triggers (+6): 37 ≤ 38. Seven triggers (+7): 38 = budget, not >. Eight triggers (+8): 39 > 38. **Eight triggers (4 `i`, 4 `a`) at ×1.2 forces.**
- **Par with 8 triggers:** 4 `i`-triggers × 5 keys + 4 `a`-triggers × 3 keys + navigation between all = 20+12+nav. Navigation (traversing trigger cells in order along a corridor): roughly 8 × 2 nav keys (move between triggers) = 16. Plus K1, K2, exit nav: ~15. Total par ≈ 20+12+16+15 = 63. Budget = ceil(63×1.2) = 76. Wrong-all (8 triggers): 63+8=71 ≤ 76. Still not forced!
- **Root problem identified:** The per-trigger wrong-command penalty for `i`/`a` is inherently +1 key (reposition 1 cell). No budget multiplier makes 8×1=8 keys exceed a budget that has all of par's navigation baked in. The only solution is terrain-forcing (S1) or a rethink.

**S1 Terrain-forcing adopted for L20 (final):**

The inner room is a narrow 1-wide corridor with walls on both sides. Trigger cells are at the far ends of single-cell dead-ends. For the `i`-trigger:
- A dead-end alcove at (3, 10): wall at (3,9) and (3,11) and (2,10) so cursor arrives from (3,10) via the only gap (from left). Player is at col 10; the only passable cells are col 10 (current) and the way back.
- Rune trigger: blank cell at (3,10). Target rune: `∆` must be at (3,10). `i ∆ Esc` writes at col 10 (cursor cell) → correct. `a ∆ Esc` writes at col 11 → but col 11 is a wall. **The game engine cannot write into a wall cell.** So `a` from col 10 with a wall at col 11 fails — `a` places the cursor at col 11 (after cursor) but col 11 is a wall, so the rune write is rejected (or the char lands in the wall = invalid placement). The door stays locked. No repositioning possible — col 11 is a wall permanently. **`a` is topologically impossible at this trigger. `i` is the only working command. Terrain-forced with ∞ cost for the wrong command. PASS (S1).**

Similarly for the `a`-trigger:
- Dead-end alcove at (4, 20): wall at (4,21). Player stands at col 19 (the only cell they can reach from the left). `a ∆ Esc` writes at col 20 (after cursor = col 19+1 = 20) → correct. `i ∆ Esc` writes at col 19 (cursor cell) → wrong cell, trigger not satisfied. Player must undo and retry with `a`, adding `u a ∆ Esc` = +2 keys (undo + redo-correctly). But `u` is already taught by L18, so undo+retry is available. +2 ≤ budget margin.
- **To close the undo hole:** Place void rune at (4,19) after the inscription is written, OR: make the `a`-trigger require the rune at col 20 AND simultaneously require col 19 to be blank (the `i`-command fills col 19 and locks the door by contaminating cell 19). A contaminated cell 19 means the player must `x` to clear it first (+1 key) and then retry `a`. Budget margin tightened to ≤1 key.
- Actually: the door trigger for `a` checks that col 19 is blank AND col 20 has `∆`. `i ∆ Esc` fills col 19 (wrong) → col 19 is no longer blank → door condition fails. Player must `x` to clear col 19 (+1 key), then `a ∆ Esc` (+3 keys). Wrong command costs +1 key. With budget margin small this is enough.
- **Par (revised, S3 full recount, 2 terrain-forced triggers, ×1.4 budget):**
  1. Navigate from (1,1) to K1 (1,38): `37l` = 3 keys. `x` = 1.
  2. Navigate to `i`-trigger approach (3,9): `2j 29h` = `2j`=2, `29h`=3 = 5 keys.
  3. `l` to enter alcove (3,10) = 1 key.
  4. `i ∆ Esc` = 3 keys.
  5. Navigate to `a`-trigger approach (4,18): `j 8h` = `j`=1, `8h`=2 = 3 keys.
  6. `l` to (4,19) = 1 key.
  7. `a ∆ Esc` = 3 keys.
  8. Exit inner room, navigate to K2 (8,5): `4j ... 14h` ≈ `4j`=2, `14h`=3 = 5 keys. `x`=1.
  9. Navigate to X (10,38): `2j 33l` = `2j`=2, `33l`=3 = 5 keys.

**Par: 3+1+5+1+3+3+1+3+5+1+5 = 31 keystrokes.**
**Budget: ceil(31 × 1.4) = 44 keystrokes.**

**Forcing (final):**
- `i`-trigger: terrain-forced (wall at cursor+1 blocks `a`). ∞ cost to violate. S1. **PASS.**
- `a`-trigger: `i` at col 19 contaminates col 19, door condition requires col 19 blank. Wrong-command cost: +1 (clear + retry). Budget margin = 44−31 = 13. +1 ≤ 13, so not forced by budget. **Residual: `a`-trigger has terrain guidance but budget doesn't close the 1-key hole.** CHALLENGE filed below.
- **Decision adopted:** The `i`-trigger is S1 terrain-forced (hard). The `a`-trigger is S1-guided (contamination mechanic) but only +1 penalty — the player is guided to `a` because the wrong command produces a visible failure state and they correct it within budget. The level teaches `a` as a concept; the hard forcing is on `i`. Accepted as "functionally forceable by context + 1 soft budget nudge."

**Primitives used:** walls forming dead-end alcoves, blank trigger cells, rune-inscription door triggers (cell must equal glyph AND neighboring cell condition), keystones.
**Engine ops:** `begin_insert` (`i`/`a` variants), `insert_char`, `replace_chars` not used.

**Self-check:**
- [x] ≤3 new mechanics (2: INSERT mode entry, rune-inscription trigger).
- [x] Coherent family: `i` and `a` are the same mode, minimal offset difference.
- [x] `i` terrain-forced (S1): wall at cursor+1 makes `a` physically impossible at that trigger.
- [x] `a` guided by contamination: wrong command (i) makes trigger cell dirty, requires correction.
- [x] Grid navigable: entry → K1 → `i`-trigger alcove → `a`-trigger alcove → K2 → exit.
- [x] Budget multiplier ×1.4; Esc counted.

---

## L21 — The Sculpting Chambers

**Commands taught:** `I` (insert at first non-blank of line), `A` (insert after last rune on line), `o` (open line below), `O` (open line above).
New mechanics (count: 2):
1. `I` / `A` — line-edge insert entries (jump to line start or end, then INSERT). S1-forced by dead-end corridor architecture.
2. `o` / `O` — open-line: inserts a blank floor row below/above the cursor row, shifting content, then enters INSERT on the new row. This is a real topology change.

**Linkage:** All four commands are insert-mode entry points. `I`/`A` are the line-scope versions of `i`/`a`. `o`/`O` are the "add a row" versions — same mode, new dimension.

**Budget multiplier: ×1.4. Esc counts as 1 keystroke.**

---

### Design philosophy (S1 adopted for all four commands)

**`I` terrain-forcing:** A trigger cell is at the leftmost non-blank column of its row. To reach it, the player must type `I` (which jumps to first non-blank), then inscribe the glyph. Walking there manually would cost ≥5 extra keystrokes (long corridor, walls block shortcut). `I` is cheaper by ≥5 keys; budget margin is set so ≤4 extra keys fit.

**`A` terrain-forcing:** A trigger cell is at the rightmost passable column of a long row (col 38 of a 40-wide map). Walking there manually: `38l` = 3 keys, then `i glyph Esc` = 3 keys = 6 keys. `A glyph Esc` from anywhere on that row = 3 keys. Budget ensures the 3-key savings × 2 `A`-triggers exceed margin.

**`o` topology-forcing (S1):** A sealed room has no floor connection. `o` from the row above inserts a connecting floor row. Without `o`, the room is physically inaccessible. ∞ cost. S1. PASS.

**`O` topology-forcing (S1):** Inside the sealed room (entered via `o`) there is a raised ledge sub-room (rows sealed above the player's new floor row). `O` from inside the ledge's floor row inserts a connecting row above, making the ledge accessible. Without `O`, the ledge (which holds the exit X) is physically inaccessible from inside. ∞ cost. S1. PASS.

---

### Grid (BEFORE topology changes)

**Dims:** 16 rows × 44 cols

```
Row  0: ############################################
Row  1: #@..........................................#
Row  2: #............................................#  ← outer corridor
Row  3: #..K1........................................#
Row  4: #............................................#
Row  5: ############################################  ← sealed-room outer top wall (full row of #)
Row  6: ###[SEALED OUTER ROOM: rows 5–11, cols 0–43]#  ← enter via o on row 4
Row  7: #..#................................#.......#
Row  8: #..#................................#.......#  ← I-trigger at (8, 3) leftmost non-blank
Row  9: ####[LEDGE sub-room: rows 9–11, cols 28–43]#  ← sealed sub-room; enter via O on row 9
Row 10: #..#............................####.......#
Row 11: #..#............................#X.#.......#  ← exit X inside ledge
Row 12: ############################################  ← sealed-room bottom wall
Row 13: #............................................#
Row 14: #..K2........................................#
Row 15: ############################################
```

**Precise final grid (16 r × 44 c, BEFORE o/O):**

```
Row  0: ############################################
Row  1: #@..........................................#
Row  2: #...........INSCRIBE_A→.(A-trigger row).....#
Row  3: #...K1......................................#
Row  4: #...........INSCRIBE_B→..(A-trigger row 2)..#
Row  5: ############################################  ← outer sealed wall (solid, full-width)
Row  6: ############################################  ← inner room top wall (o inserts row between 4 and 5)
Row  7: #..#.................I_trigger..........#...#  ← (7,3) leftmost non-blank, 3=first passable
Row  8: #..#............................................#
Row  9: ############################################  ← ledge wall (O inserts row between 8 and 9)
Row 10: ############################################  ← ledge inner top
Row 11: #..#............................#X.#........#
Row 12: ############################################  ← inner room bottom wall
Row 13: #..........................................#
Row 14: #...K2.....................................#
Row 15: ############################################
```

**Simplified annotated grid (working spec, 16 r × 44 c):**

```
Row  0: ############################################
Row  1: #@..........................................#
Row  2: #...........................................#
Row  3: #...K1......................................#
Row  4: #....AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA#  ← A-trigger row: rune must land at col 42
Row  5: ############################################  ← sealed outer top; o on row 4 inserts row 5
Row  6: ############################################  ← sealed outer top (post-o this becomes row 7)
Row  7: #..I_trig....................................#  ← I-trigger at col 3 (first non-blank)
Row  8: #...........................................#
Row  9: ############################################  ← ledge wall; O on row 8 inserts row 9 (sub-room)
Row 10: #....................................##X##.#  ← ledge floor with exit (only reachable via O)
Row 11: ############################################  ← ledge bottom wall
Row 12: ############################################  ← outer sealed bottom
Row 13: #...........................................#
Row 14: #...K2.....................................#
Row 15: ############################################
```

**AFTER `o` on row 4 (player at row 4, `o` inserts blank floor at row 5):**

```
Row  4: #....AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA#
Row  5: #..[NEW FLOOR — cursor here, INSERT active]#  ← outer sealed room now connected
Row  6: ############################################  (was row 5's sealed wall, shifted to row 6)
Row  7: #..I_trig....................................#  (was row 6, shifted to row 7... wait)
```

*Engine note: `o` inserts a new passable row immediately below the cursor row; all rows below shift down by 1. The sealed outer room (previously rows 5–12) shifts to rows 6–13. The new row 5 provides floor continuity from the outer corridor into the sealed outer room.*

**AFTER `O` on row 8 (player inside sealed outer room at row 8, `O` inserts blank floor at row 8):**
- `O` inserts a new passable row above cursor row 8 → new row 8 (player on it), old row 8 shifts to row 9. The ledge sub-room (previously rows 9–11 post-o-shift) becomes connected to the outer sealed room's floor via new row 8. Player can walk from new row 8 into the ledge room and reach X.

**Placements:**
- `@` entry: (1, 1).
- `X` exit: (10, 38) — inside the ledge sub-room. Only reachable after both `o` and `O`.
- `K1` keystone: (3, 4) — activates D1.
- `D1` door: gate between outer corridor and the `A`-trigger row. Opens when K1 active AND rune `Φ` is at (4, 42) (the `A`-trigger: player types `A Φ Esc` on row 4, which appends after the last rune → col 42).
- `A`-trigger: row 4. Row 4 is the longest row, cols 1–42 all passable. `A` from anywhere on row 4 jumps to last rune col + 1 and writes. `A Φ Esc` = 3 keys. Walking manually to col 42 and typing `i Φ Esc`: cost = `41l` (3 keys) + 3 keys = 6 keys. `A` saves 3 keys per trigger. Two `A`-triggers (rows 4 and 2): saves 6 keys total vs manual walk. Budget margin ≤5 → `A` forced.
- Second `A`-trigger: row 2, rune `Ψ` must land at (2, 42). Same structure.
- `I`-trigger: row 7 of the sealed outer room. `I` jumps to col 3 (first non-blank of the row, the leftmost floor cell inside the sealed room past the inner wall). Rune `Σ` must land at (7, 3). Walking to col 3 from where player enters (col ~2 or 10+): manual walk = `2l` or similar (short). Actually the inner room layout: sealed room's inner-left wall is at col 2, floor starts col 3. Player enters via new row 5 (after o) at some col near 3. So walking to col 3 is trivial. `I` vs walking is not a big savings here.
- **`I` terrain fix:** The `I`-trigger's row 7 has a wall at col 2 (inner-left sealed-room wall) and rune clusters filling cols 4–40 (non-blank). The FIRST non-blank col is col 3. The trigger cell for `I` is (7, 3). BUT: cols 6–38 have decorative rune clusters (non-blank). If player is at col 25 (middle of the row), walking to col 3 manually = `22h` = 3 keys (count-prefixed). `I` from col 25 = 1 key (jumps directly to col 3). Player still needs to type glyph + Esc: `I Σ Esc` = 3 keys vs `22h i Σ Esc` = 6 keys. Savings = 3 keys. Player enters from the new floor row (row 5) at col ~20 (midpoint). `I` saves ≥3 keys. Budget margin set ≤2. **`I` forced by budget.**
- `K2` keystone: (14, 4) — activates D2 (the final exit door from the outer lower corridor).
- `D2` door: (15, 35) on the outer corridor (post-exit from sealed rooms). Opens when K2 active.
- Outer corridor A-trigger rows (2, 4): on the path the player walks before encountering the sealed rooms.

**Optimal keystrokes (S3 full recount):**
1. K1 (3,4): from (1,1), `2j 3l x` = `2j`=2, `3l`=2, `x`=1 = 5 keys.
2. Row 2 `A`-trigger: `j` = 1. `A Ψ Esc` = 3 keys. D_A gate condition met.
3. Row 4 `A`-trigger: `2j` = 2. `A Φ Esc` = 3 keys. D1 condition met.
4. `o` = 1. New row 5 inserted; cursor at row 5, INSERT active. `Esc` = 1. Outer sealed room accessible.
5. Navigate into sealed room, reach row 7 col ~20 (via new row 5, then j j): `2j` = 2 (rows 5→6→7, but row 6 is the old sealed wall now shifted — check: after o, new row 5 is floor; row 6 is the old sealed-room inner top wall, still a wall. Hmm — player on new floor row 5 walks along it but cannot step onto row 6 wall. Need row 6 to have a gap. **Design fix: the sealed outer room's inner top wall (originally row 5) has a 1-cell gap at col 10. After o inserts new floor row, the gap at (6,10) allows j to reach row 7.** So: `l ... j` = reach col 10 then step down through gap: ~5 keys total navigation from row 5.
6. `I Σ Esc` = 3 keys. D_I condition met.
7. Navigate to row 8 (the row above the ledge): `j` = 1. (Row 8 is floor of outer sealed room, below I-trigger row 7.)
8. `O` = 1. New row 8 inserted above player; cursor on new row 8, INSERT active. `Esc` = 1. Ledge sub-room now accessible.
9. Walk into ledge sub-room and to X: navigation from new row 8 into ledge ~6 keys.
10. ... (K2 is reached only on a second path if X is the immediate exit; or K2 is before the sealed rooms.)

**Revised layout (K2 placed BEFORE sealed rooms):**
- K2 at (3, 38): player activates it on the way past row 3 (rightward navigation). `K2 x` = adds 2 keys to step 1 path.
- D2 is the exit door at X (not needed separately — X is unlocked when K2 active AND all rune conditions met).
- Simplification: X exit at (ledge row, col 38) opens when K2 active AND rune `Σ` at I-trigger. No D2 door needed separately.

**Par (revised, K2 on the outer path before sealed rooms):**
1. K1 (3,4): `2j 3l x` = 5 keys.
2. K2 (3,38): `34l x` = `34l`=3, `x`=1 = 4 keys.
3. Row 2 `A`-trigger: `j 40h` = `j`=1, `40h`=3 = 4 keys; wait, K2 at (3,38), row 2 A-trigger means going back up: `k` = 1. `A Ψ Esc` = 3 keys.
4. Row 4 `A`-trigger: `2j` = 2. `A Φ Esc` = 3 keys.
5. `o Esc` = 2 keys.
6. Navigate to I-trigger (new row 7, col ~3 to 20): `2j l*5` ≈ `2j`=2, `10l`=3 = 5 keys (reaching col 10 gap, stepping down to row 7).
7. `I Σ Esc` = 3 keys.
8. Navigate to `O`-trigger position (row below I-trigger, above ledge wall): `j` = 1.
9. `O Esc` = 2 keys.
10. Navigate into ledge and reach X (10,38): `j 35l` ≈ `j`=1, `35l`=3 = 4 keys.

**Par: 5+4+1+3+2+3+2+5+3+1+2+1+3 = ~35 keystrokes.**
*Par-solver authoritative; approximate here.*
**Budget: ceil(35 × 1.4) = 49 keystrokes.**

**Forcing verification (S1 + S2):**
- `o`: sealed outer room has no other connection. ∞ cost without `o`. S1. PASS.
- `O`: ledge sub-room has no connection except via `O` from inside the outer sealed room. ∞ cost without `O`. S1. PASS.
- `A`: saves 3 keys per trigger vs manual walk; 2 triggers = 6 keys savings; budget margin = 49−35 = 14. Without `A`: 35+6=41 ≤ 49. NOT forced by budget alone with 2 triggers.
- **`A` additional forcing:** Make the `A`-trigger rows 60-col wide (extend map to 60 cols). Manual walk to col 58: `57l` = 3 keys + `i glyph Esc` = 6 vs `A glyph Esc` = 3. Savings = 3 per trigger. Four `A`-trigger rows → saves 12. Budget 49, par grows by ~6 (extra nav in wider map) = 41. Without `A`: 41+12=53 > 49. **FORCED.** Adopt 4 `A`-triggers in a 60-col map.
- `I`: saves 3+ keys vs manual walk (from mid-row). Budget margin after A-forcing = 49-(41)=8. Without `I`: +3 → 41+3=44 ≤ 49. With ≥3 `I`-triggers and savings of 3 each: +9 → 50 > 49. **Adopt 3 `I`-trigger cells in the sealed room.**

**Map revision (60-col, 4 A-triggers, 3 I-triggers):**
- Dims: 16 rows × 60 cols.
- Four `A`-trigger rows (rows 1, 2, 3, 4 outer corridor). Each row 58 cols wide of passable floor.
- Three `I`-trigger cells inside sealed outer room (rows 7, 8, 9 sealed-room floor, each at leftmost passable col 3).
- Par grows but `A`/`I` forcing is confirmed. Par-solver authoritative.

**Primitives used:** sealed rooms (solid walls), 1-cell gap in sealed wall (allows entry after `o`), rune clusters filling row (forcing `I` from mid-row to save walk), long-row design (forcing `A` over manual walk), doors, keystones.
**Engine ops:** `begin_insert` (I/A/o/O variants), `_insert_blank_row`, `insert_char`.

**Self-check:**
- [x] ≤3 new mechanics (2: I/A line-edge insert, o/O open-line topology change).
- [x] Coherent family: all four are insert-mode entry points.
- [x] `o` S1-forced: sealed outer room inaccessible otherwise.
- [x] `O` S1-forced: ledge sub-room inside sealed room inaccessible otherwise.
- [x] `A` budget-forced: 4 triggers × 3-key savings each = 12 keys exceeds budget margin after longer corridor.
- [x] `I` budget-forced: 3 triggers × 3-key savings each = 9 keys > budget margin.
- [x] BEFORE/AFTER described for both `o` and `O`.
- [x] No new engine primitives.

---

## L22 — The Overwrite Halls

**Commands taught:** `r{ch}` (replace char without entering INSERT), `R` (Replace mode: overwrite-and-advance stream, Esc to exit).
New mechanics (count: 2):
1. `r{ch}` — single overwrite, 2 keystrokes total (`r` + char), cursor stays.
2. `R` — Replace mode: each keystroke overwrites and advances; `Esc` exits.

**Budget multiplier: ×1.15** (tighter than ×1.2 to force each command individually over
substitution alternatives). **Esc counts as 1 keystroke.**

**Linkage:** Both commands overwrite existing runes without entering INSERT flow. `r` is single-
shot (cheaper per char for 1-cell fixes); `R` is a stream (cheaper per char for N≥3 consecutive
cells). Contrast with `i`/`a` which write on empty/after cells.

---

### Forcing derivation (S2 tight-budget — REDESIGNED for individual strict forcing)

**Previous design (combined-only forcing):** With ×1.2 and par≈63, margin=13 absorbed r-savings
(9) and R-savings (11) individually; only avoiding BOTH exceeded budget. Root cause: the long
r-corridor (34 ks) inflated par so that margin > savings-per-command.

**Fix:** Use a compact single-row layout so par is minimal and margin = ceil(par×0.15) < 9.
This makes r-savings (9 ks) and R-savings (11 ks) each individually exceed margin.

**Target par = 39 ks** (proven below). Budget (×1.15) = ceil(39×1.15) = ceil(44.85) = **45**.
Margin = 45−39 = **6**. Since 9 > 6 and 11 > 6, BOTH commands are individually forced. ✓

**Navigation insight:** The r-cells are separated by void runes. Between adjacent r-cells, the
player can use `w` (jump-motion, 1 ks) to skip the intervening void, since `w` is a buffer-
position jump that does not land on intermediate void cells. This replaces `2l` (2 ks) with `w`
(1 ks) for inter-cell navigation, reducing corridor par by 8 ks vs the previous design.

**r-savings derivation (9 corrections, w-hops):**
- Optimal: `r α w r β w ... r ι` = 9×2(r-pairs) + 8×1(w-hops) = 26 ks for the r-section.
- Without `r` (use `s α Esc w`): 9×3(s-pairs) + 8×1(w-hops) = 35 ks for r-section. +9 ks. ✓
- `R` cannot cross voids (void cells are lethal; R-mode would kill on void entry). `r` is the
  only viable single-cell command. Void isolation is the S1 guard against using R on r-cells.

**R-savings derivation (7 consecutive cells):**
- Optimal: `R P Q R S T U V Esc` = 7+2 = 9 ks.
- Without `R` (use `r l` per cell): 7×2+6×1 = 20 ks. +11 ks. ✓
- `r` on the R-cells: player could use `r P l r Q l...r V` = 20 ks vs R=9 ks. R is cheaper. ✓

---

### Grid — REDESIGNED compact single-row layout

**Dims:** 4 rows × 30 cols

**Annotated grid:**

```
Row  0: ##############################
Row  1: #@A.B.C.D.E.F.G.H.I.DPQRSTUVX#
Row  2: ##############################
Row  3: ##############################
```

**Legend (row 1):**
```
col  1: @ (entry)
col  2: A (r-cell 1: wrong glyph, target α)
col  3: ○ (void rune — lethal, isolates r-cell 1)
col  4: B (r-cell 2: wrong glyph, target β)
col  5: ○ (void)
col  6: C (r-cell 3: target γ)
col  7: ○ (void)
col  8: D (r-cell 4: target δ)
col  9: ○ (void)
col 10: E (r-cell 5: target ε)
col 11: ○ (void)
col 12: F (r-cell 6: target ζ)
col 13: ○ (void)
col 14: G (r-cell 7: target η)
col 15: ○ (void)
col 16: H (r-cell 8: target θ)
col 17: ○ (void)
col 18: I (r-cell 9: target ι)
col 19: D (door — auto-opens when all 9 r-cells corrected; passable when open)
col 20: P (R-cell 1: wrong glyph, target P)
col 21: Q (R-cell 2: target Q)
col 22: R (R-cell 3: target R)
col 23: S (R-cell 4: target S)
col 24: T (R-cell 5: target T)
col 25: U (R-cell 6: target U)
col 26: V (R-cell 7: target V)
col 27: X (exit — auto-opens when R-corridor corrected; locked until both corridors done)
col 28: # (wall)
```

**Dims:** 4 rows × 30 cols (rows 0–3, cols 0–29; passable content cols 1–27 on row 1).
**Entry:** (1, 1). **Exit:** (1, 27).

**Void isolation (S1 for r):** Void runes at odd cols 3,5,7,9,11,13,15,17 between each r-cell pair.
A player attempting `R` from col 2 would overwrite col 2 then advance to col 3 = void (lethal).
Only `r` (cursor stays after each write) can be used on the r-corridor. ✓

**R-corridor bounds (S1 for r-vs-R):** Col 19 is a door (wall-like when locked). Col 28 is wall.
No void between R-cells cols 20–26 — R can advance freely through them. Void at col 27 = exit,
not a void rune but a door trigger. Player enters R-corridor at col 20, completes 7 overwrites
(cols 20–26), then Esc, then `l` to exit at col 27.

**S4 block:** Rows 0, 2, 3 are full walls. Player cannot use `j`/`k` to bypass the single-row
corridor. `$` from col 1 → col 26 (last non-void passable cell before exit); but corrections
are still required (door at col 19 locked, exit at col 27 locked until corrections done). `$`
saves 0 ks on corrections — player must still do all corrections in order. ✓

**`w`/`W` navigation between r-cells:** `w` from col 2 (r-cell 1, word-char) → col 4 (r-cell 2,
skipping void at col 3). Jump-motion; does NOT land on col 3. `w` from col 4 → col 6. Etc.
8 `w` presses total for 8 hops between the 9 r-cells. This is the optimal navigation. ✓

---

### Placements (coordinates)

| Glyph / Entity | Row | Col | Notes |
|---|---|---|---|
| Entry `@` | 1 | 1 | — |
| r-cells (9 wrong glyphs) | 1 | 2,4,6,8,10,12,14,16,18 | targets: α,β,γ,δ,ε,ζ,η,θ,ι |
| Void runes `○` (8 isolators) | 1 | 3,5,7,9,11,13,15,17 | lethal; block R-mode crossing |
| Door D (auto-trigger) | 1 | 19 | opens when all 9 r-cells match targets |
| R-cells (7 consecutive) | 1 | 20–26 | targets: P,Q,R,S,T,U,V (distinct glyphs) |
| Exit `X` | 1 | 27 | opens when R-corridor corrected AND door passed |
| Full wall rows | 0,2,3 | 0–29 | S4: no j/k bypass possible |
| Wall cols | 1 | 0,28,29 | left/right bounds |

---

### Optimal keystrokes (S3 full recount)

```
l  (1 ks): (1,1) → (1,2)  first r-cell
r α (2 ks): correct r-cell 1 at col 2
w  (1 ks): (1,2) → (1,4)  skip void, land on r-cell 2
r β (2 ks): correct r-cell 2
w  (1 ks): → (1,6)
r γ (2 ks): correct r-cell 3
w  (1 ks): → (1,8)
r δ (2 ks): correct r-cell 4
w  (1 ks): → (1,10)
r ε (2 ks): correct r-cell 5
w  (1 ks): → (1,12)
r ζ (2 ks): correct r-cell 6
w  (1 ks): → (1,14)
r η (2 ks): correct r-cell 7
w  (1 ks): → (1,16)
r θ (2 ks): correct r-cell 8
w  (1 ks): → (1,18)
r ι (2 ks): correct r-cell 9. Door D opens. At col 18.
l  (1 ks): (1,18) → (1,19)  door col (open)
l  (1 ks): (1,19) → (1,20)  R-corridor start
R P Q R S T U V Esc (9 ks): overwrite cols 20–26. Cursor at col 26.
l  (1 ks): (1,26) → (1,27)  exit X

Full optimal: l [r α w]×8 r ι l l R…Esc l
Par = 1 + 9×2 + 8×1 + 1 + 1 + 9 + 1
    = 1 + 18 + 8 + 1 + 1 + 9 + 1
    = 39 keystrokes
Budget = ceil(39 × 1.15) = ceil(44.85) = 45
```

**par = 39 | budget = 45 | M = 1.15**

---

### Forcing argument (individual strict forcing)

**`r` individually forced:**
- Without `r`, use `s α Esc w` per r-cell: 9×3(s-pairs) + 8×1(w-hops) = 27+8 = 35 ks for r-section.
- r-section with r: 9×2+8×1 = 26 ks. Without-r penalty: +9 ks.
- Without-r total: 39+9 = 48 > budget=45. **STRICTLY over. ✓**

*(Conservative assumption: `s α` at a void-adjacent cell is possible with +1 ks Esc overhead. If
void adjacency makes `s` lethal, the penalty is ∞ and forcing is S1. Either way, r is forced.)*

**`R` individually forced:**
- Without `R`, use `r P l r Q l r R l r S l r T l r U l r V`: 7×2+6×1 = 20 ks for R-section.
- R-section with R: 9 ks. Without-R penalty: +11 ks.
- Without-R total: 39+11 = 50 > budget=45. **STRICTLY over. ✓**

**Both avoided:**
- Without r AND R: 39+9+11 = 59 > 45. ✓

**Arithmetic summary:**
```
par = 39
budget = ceil(39 × 1.15) = 45
margin = 45 − 39 = 6

r-savings  = 9  > 6 = margin → r individually forced: 39+9=48 > 45. ✓
R-savings  = 11 > 6 = margin → R individually forced: 39+11=50 > 45. ✓
```

**Void isolation (S1 for R-on-r-corridor):** Void runes between r-cells kill any R-mode run that
tries to cross them. `R` on the r-corridor = death after first overwrite. R is impossible there.
Combined with budget forcing: `r` is both S1-guarded and budget-forced. ✓

**Rune clusters (decorative):**
- A read-only ancient inscription along the top of row 1 (before the r-corridor) is optional;
  in the compact single-row layout there is no space for decorative rows. The mechanics are
  taught by the corrective puzzle structure itself.

---

### Self-check

- [x] ≤3 new mechanics (2: r single-overwrite, R stream-overwrite).
- [x] Coherent family: both overwrite in-place; `r` is 1-cell, `R` is N-cell stream.
- [x] r-corridor: 9 cells, void-isolated → blocks R-mode crossing (S1 void guard).
- [x] R-corridor: 7 consecutive cells → R saves 11 ks over repeated r.
- [x] r individually forced: 39+9=48 > budget=45. STRICTLY over. ✓
- [x] R individually forced: 39+11=50 > budget=45. STRICTLY over. ✓
- [x] Budget multiplier ×1.15 documented; Esc counted; margin=6.
- [x] S4: full-wall rows 0,2,3 block j/k bypass; `$` cannot skip correction triggers.
- [x] `w`-hop navigation between r-cells is the optimal inter-cell move (1 ks vs `2l`=2 ks);
      without-r path also uses `w`-hops, so savings = 9 ks (not affected by hop optimality).
- [x] CHALLENGE RESOLVED: individual strict forcing achieved via compact layout + ×1.15 budget.

---

## L23 — The Case Chambers

**Commands taught:** `~` (toggle case of char at cursor, advance), `g~{motion}` (toggle case over motion), `gU{motion}` (uppercase over motion), `gu{motion}` (lowercase over motion).
New mechanics (count: 2):
1. `~` — single-char case toggle with cursor advance.
2. Case operators `g~` / `gU` / `gu` — apply case transform over a text-object/motion span.

**Linkage:** All four are case transformations. `~` is the single-cell version; `g~`/`gU`/`gu` are operator-scope versions (same grammar as `d`/`y`/`c` but for case). They form the complete case-editing family.

**Budget multiplier: ×1.4. Esc not needed (case commands are Normal-mode).**

**Case-sensitive trigger mechanic:** Doors open only when the rune cluster at a trigger cell matches the required case pattern exactly.

---

### Par arithmetic correction (S3)

The review found `gU6l` = **4 keystrokes** (`g`, `U`, `6`, `l`), not 3. All case operators with a count-motion take 4 keystrokes: operator-char (`g`) + command-char (`U`/`u`/`~`) + count digit + motion key. Without count: `gUw` = 3 keystrokes (g, U, w). Design uses `gUW` (uppercase to WORD end) = 3 keystrokes where possible, or `g~6l` etc. where count is needed (4 keystrokes).

**Adopted convention:** Use WORD motions (`gUW`, `guW`, `g~W`) = 3 keystrokes each where the cluster is one WORD. This avoids count-digit overhead. Each 6-char cluster is one WORD (no internal spaces). `gUW` = 3 keys, `guW` = 3 keys, `g~W` = 3 keys.

---

### Grid

**Dims:** 16 rows × 48 cols

**Final precise grid (16 r × 48 c):**

```
Row  0: ################################################
Row  1: #@..............................................#
Row  2: #...K...........................................#
Row  3: #...............................................#
Row  4: #...abCDeF (zone 1: need ALL UPPER → D1).....#
Row  5: #...'x' (~ single-char trigger)..............#
Row  6: #.......................................D1.....#
Row  7: #...............................................#
Row  8: #...ABCDEF (zone 2: need ALL LOWER → D2).....#
Row  9: #...'Y' (~ single-char trigger)..............#
Row 10: #.......................................D2.....#
Row 11: #...............................................#
Row 12: #...AaBbCc (zone 3: need SWAPPED → D3)......#
Row 13: #...'z' (~ single-char trigger)..............#
Row 14: #.......................................D3.....#
Row 15: ################################################
```

*(Exit X is at (14,46), reached through D3.)*

**Placements:**
- `@` entry: (1, 1).
- `X` exit: (14, 46) — past D3.
- `K` keystone: (2, 4) — activates all door condition checks.
- `D1` door: (6, 40) — opens when rune cluster row 4 cols 3–8 = `ABCDEF`.
- `D2` door: (10, 40) — opens when rune cluster row 8 cols 3–8 = `abcdef`.
- `D3` door: (14, 40) — opens when rune cluster row 12 cols 3–8 = `aAbBcC` (case-swapped from `AaBbCc`).

**Rune clusters:**
- Row 4, cols 3–8: `abCDeF` (6-char WORD, ancient). Trigger: all uppercase = `ABCDEF`. Cheapest: `gUW` = 3 keys (positions cursor at col 3, `gUW` uppercases to WORD-end). Vs `~` × 4 wrong-case chars (a,b,e,f need toggling; C,D already upper): 4 `~` presses + navigation through already-correct chars. Navigation: from col 3, first char `a` (toggle), `l` to b (toggle), `l` to C (skip), `l` to D (skip), `l` to e (toggle), `l` to f (toggle) = 4 toggles + 5 moves = 9 keys. `gUW` saves 6 keys per zone.
- Row 4, col 12: `'x'` (single char, ancient). Trigger: must be `'X'`. Cheapest: `~` = 1 key (toggle + advance). Vs `rX` = 2 keys. `~` saves 1 key. Budget must be tight enough that this 1-key savings matters.
- Row 8, cols 3–8: `ABCDEF` (6-char WORD, verdant). Trigger: all lowercase = `abcdef`. Cheapest: `guW` = 3 keys. Vs `~` × 6 = 6 keys + 5 moves = 11 keys. `guW` saves 8 keys.
- Row 8, col 12: `'Y'` (single char, verdant). Trigger: must be `'y'`. Cheapest: `~` = 1 key. Vs `ry` = 2 keys. Saves 1 key.
- Row 12, cols 3–8: `AaBbCc` (6-char WORD, ember). Trigger: `aAbBcC` (every char case-flipped). Cheapest: `g~W` = 3 keys. Vs `~` × 6 = 6 + 5 moves = 11 keys. `g~W` saves 8 keys.
- Row 12, col 12: `'z'` (single char, ember). Trigger: must be `'Z'`. Cheapest: `~` = 1 key. Saves 1.
- **Three additional 6-char zones (rows 5–6 area):** To ensure `~`-only path exceeds budget, add 3 more mixed-case 6-char zones each requiring operator approach. Total operator zones: 6 (three 6-char clusters + three more in bonus corridor). See below.

**S2 budget forcing derivation (corrected par):**

Operator path (3 zones, 3 single-chars):
1. K (2,4): `j 3l x` = `j`=1, `3l`=2, `x`=1 = 4 keys.
2. Row 4 col 3: `2j h` = `2j`=2, `h`=1 = 3 keys.
3. `gUW` = 3 keys.
4. Col 12 (`~`-trigger): `8l ~` = `8l`=2, `~`=1 = 3 keys.
5. Navigate to D1 (6,40): `2j 28l` = `2j`=2, `28l`=3 = 5 keys.
6. Row 8 col 3: `2j 37h` = `2j`=2, `37h`=3 = 5 keys.
7. `guW` = 3 keys.
8. Col 12 (`~`-trigger): `8l ~` = 3 keys.
9. D2 (10,40): `2j 28l` = 5 keys.
10. Row 12 col 3: `2j 37h` = 5 keys.
11. `g~W` = 3 keys.
12. Col 12 (`~`-trigger): `8l ~` = 3 keys.
13. D3 (14,40): `2j 28l` = 5 keys.
14. X (14,46): `6l` = 2 keys.

**Par: 4+3+3+3+5+5+3+3+5+5+3+3+5+2 = 52 keystrokes.**
**Budget: ceil(52 × 1.4) = ceil(72.8) = 73 keystrokes.**
**Margin: 73−52 = 21 keys.**

**`~`-only path cost analysis:**
- Zone 1 (row 4, `abCDeF`→`ABCDEF`): `~` 4 wrong chars + navigate through 2 correct = 4+5 = 9 vs `gUW`=3; extra = +6.
- Zone 2 (row 8, `ABCDEF`→`abcdef`): `~` all 6 + navigate = 6+5=11 vs `guW`=3; extra = +8.
- Zone 3 (row 12, `AaBbCc`→`aAbBcC`): `~` all 6 + navigate = 6+5=11 vs `g~W`=3; extra = +8.
- Three `~`-trigger single chars: `rX`, `ry`, `rZ` = 2 keys each vs `~` = 1 key each; `~` is CHEAPER here by 1 each — the `~`-only player would use `~` for single chars anyway. So no penalty for `~`-only player on single-char triggers; they save 0 there.
- Total extra for `~`-only on 3 zones: +6+8+8 = +22.
- `~`-only total: 52+22 = 74 > 73. **FORCED! PASS.**

*(Wait: zone 1 extra is +6, zones 2 and 3 extra are +8 each. Sum = +22. 52+22=74 > 73. By 1 key — tight but valid.)*

**Adding 3 more zones raises the margin:** With 6 operator zones total (3 additional 6-char clusters on rows 5, 9, 13), total extra for `~`-only = 22 × 2 = 44 (approximate, if symmetric). Par grows by ~15 (extra traversal). Budget = ceil(67×1.4)=94. `~`-only: 67+44=111 > 94. Massive margin for forcing — but this is over-engineering. **The 3-zone design (par=52, budget=73) is sufficient: `~`-only path = 74 > 73 by 1 key.**

**`~` single-char forcing:**
- `~` saves 1 key vs `rX` per single-char trigger.
- 3 single-char triggers: saves 3 keys total.
- Without `~` (use `r` for all single chars): par+3 = 55. Budget=73. 55 ≤ 73. NOT forced individually.
- BUT: `~` is also the only sensible command for a single case-toggle. `rX` would set the char to uppercase `X` always, even if it's already `X` — and `rX` for a toggle doesn't make semantic sense. More importantly, `~` is designed to toggle, so `rX` could be used instead. The forcing is soft: `~` is the conceptually correct command and is taught explicitly; budget doesn't strictly force it over `r`.
- **S1 alternative for `~`:** The single-char triggers are chars that can be either upper or lower depending on context (randomly determined per run). If the target toggle state is determined at runtime, the player cannot pre-type `rX` because they don't know whether the target is `X` or `x`. Only `~` (toggle) works regardless. **This makes `~` functionally required: `r` requires knowing the target case; `~` works blindly.** This is S1 logical-forcing rather than budget-forcing. **Adopted.**

**Forcing summary (final):**
- `gUW`/`guW`/`g~W`: budget-forced; `~`-only path exceeds budget by 1 key (74 > 73). PASS.
- `~` single-char: S1-forced by randomized target case (can't pre-compute `r{ch}`). PASS.

**Primitives used:** case-sensitive rune triggers (door opens on exact case pattern), rune clusters (mixed case, one WORD), single-char triggers (random case), doors, keystone.
**Engine ops:** `case_char` (`~`), `op_case` (`g~`/`gU`/`gu`), `_case_transform`.

**Self-check:**
- [x] ≤3 new mechanics (2: ~ single-char, case operators).
- [x] Coherent family: all are case transforms.
- [x] Par arithmetic corrected: `gUW` = 3 keys (WORD motion, no count digit), not 4.
- [x] Par = 52, budget = 73.
- [x] `~`-only path: 74 > 73 by 1 key. Budget-forced. PASS.
- [x] `~` single-char: S1-forced by runtime-random target (cannot pre-compute `r{ch}`). PASS.
- [x] No new engine primitives.

---

## L24 — The Joiner's Gate

**Commands taught:** `J` (join: append next row onto current, adding a space), `gJ` (join without space).
New mechanics (count: 1 — the row-join/carve mechanic is one idea, two variants):
1. `J` / `gJ` — appends the floor content of the row below onto the end of the current row, carving a corridor into a previously sealed room. `J` inserts a separating space at the join point; `gJ` does not. The distinction matters when a trigger requires the joined rune cluster to start at a precise column.

**Linkage:** J and gJ are a minimal pair (same mechanic, one-space difference). They belong together; teaching one without the other leaves the space/no-space distinction unresolved.

**Budget multiplier: ×1.4. Esc counts as 1 keystroke.**

---

### Undo-hole fix (S2 budget tighten + rune-content distinction)

The review found that with undo available (taught at L18), a player can try `J`, observe failure, undo, try `gJ` — costing only +2 keys per wrong attempt. With budget margin of 14 (budget=47, par=33), two undo-retries cost +4, still within margin.

**Fix adopted:** The `J`/`gJ` distinction is enforced by **rune content**, not just column position. The door trigger checks the *content* of the joined rune cluster (including the space or lack thereof):
- `gJ` joins `αβγ` + `δεζ` → `αβγδεζ` (no space). The trigger for D_inner requires the sequence `αβγδεζ` (6 chars, no space). If `J` is used: `αβγ δεζ` (7 chars, with space in position 4) — the sequence is different, the door condition checks for exact content match, and fails. Undo and retry with `gJ` costs +2 keys = par+2. Budget tightened so margin < 2.
- **Budget tightened:** par=33, budget=ceil(33×1.05)=35. Margin=2. Undo-retry penalty=+2 → 35=35, not > 35. Still at boundary.
- Tighter: par=33, multiplier so budget=34. ceil(33×1.03)=34. Margin=1. Undo-retry: 35>34. FORCED.
- But a multiplier of ×1.03 is extreme and non-standard. **Better:** Add more mandatory navigation to raise par to 40, then budget=ceil(40×1.4)=56. Undo-retry penalty = +2 per wrong door. With 2 doors: +4 if both wrong. Without any of this — but par is higher.

**Alternative fix (adopted):** Make the join result **irreversible by design**: once `J` is executed, the joined row cannot be un-joined by undo (the `u` command is marked as non-applicable to row-join operations). This is a game-mechanic decision — the engine can mark J/gJ as non-undoable. If undo is blocked for J/gJ, the player must choose correctly the first time. Wrong choice = must restart the level.

This is the **CHALLENGE for the engine** (see challenges section). In the blueprint, we document it and design ASSUMING this engine behavior (one-shot join, no undo).

**With irreversible J/gJ:**
- D_inner trigger: `gJ` produces content `αβγδεζ`; `J` produces `αβγ δεζ`. Wrong choice locks D_inner permanently (level fails, must restart). **S1 forcing: the wrong command produces an unrecoverable state. ∞ effective cost. PASS.**
- D2 trigger: `J` produces `αβγ δεζ` (space between); the trigger requires the space (password = two-word rune). `gJ` produces `αβγδεζ` (one word), wrong content. **S1 forcing: wrong command = unrecoverable. PASS.**

---

### Grids (BEFORE and AFTER J)

**BEFORE (14 r × 46 c):**

```
Row  0: ##############################################
Row  1: #@............................................#
Row  2: #.............................................#
Row  3: #...K1........................................#
Row  4: #.............................................#
Row  5: #...αβγ.....[JOIN POINT below → inner room]..#
Row  6: ##########################.....................#  ← sealed inner room left wall (rows 6–10)
Row  7: #...#..........................#...............#
Row  8: #...#...D_inner................#...............#
Row  9: #...#...X_inner................#...............#
Row 10: #...#.........................#................#
Row 11: ##########################.....................#  ← inner room bottom wall
Row 12: #...K2........................................#
Row 13: #.......................................D2...X#
##############################################
```

**Sealed inner room: rows 6–11, cols 3–27.** All four walls solid `#`. No entry except via gJ on row 5.

Row 5 contains rune cluster `αβγ` (3 glyphs) at cols 3–5. Row 6 contains `δεζ` as floor content (the inner room top-wall row's content cells when merged). After `gJ` on row 5: row 6's floor content is appended to row 5 without space → row 5 becomes `αβγδεζ` at cols 3–8; the sealed inner room's floor (rows 7–10) becomes accessible via row 5's extended extent. The join point opens a lateral passage at col 6 of row 5 (where the inner room top-wall cells meet).

**AFTER `gJ` on row 5:**
- Row 5 now includes columns 3–8 passable (αβγδεζ). Player can walk right along row 5 past col 5 into the inner room area (row 5 extends through where row 6's top wall was). The inner room's top wall row (row 6) is absorbed into row 5's extent, and inner room floor rows 7–10 are now accessible downward from row 5's extended extent.
- D_inner trigger: rune cluster at cols 3–8 of row 5 = `αβγδεζ` (no space) → D_inner opens. If `J` had been used: cluster = `αβγ δεζ` (space at col 6) → D_inner stays locked (irreversibly wrong if no undo).

**D2 on primary path (row 12→13):**
- Row 12 contains rune `αβγ` at cols 3–5; row 13 (below, where K2 is) has floor content `δεζ` at cols 3–5. Player types `J` on row 12: joins row 13 content with space → row 12 = `αβγ δεζ` at cols 3–9 (space at col 6). D2 trigger requires `αβγ δεζ` (two-word rune, space required). **`J` forced for D2.** `gJ` would produce `αβγδεζ` (one-word, no space) → D2 stays locked.

**Placements:**
- `@` entry: (1, 1).
- `X` primary exit: (13, 43).
- `X_inner` (bonus/alternate, inside sealed room): (9, 6).
- `K1` keystone: (3, 4) — activates D_inner condition.
- `K2` keystone: (12, 4) — activates D2 condition.
- `D_inner` door: (8, 4) — inside sealed room; opens when rune at row 5 cols 3–8 = `αβγδεζ` (gJ-content).
- `D2` door: (13, 39) — opens when rune at row 12 cols 3–9 = `αβγ δεζ` (J-content, with space).
- Join point 1: row 5 (player here, `gJ` merges row 6's content without space → accesses sealed inner room).
- Join point 2: row 12 (player here, `J` merges row 13's content with space → satisfies D2 trigger).

**Optimal keystrokes (S3 full recount):**
1. K1 (3,4): `2j 3l x` = `2j`=2, `3l`=2, `x`=1 = 5 keys.
2. Navigate to row 5 (join point 1): `2j` = 2 keys.
3. `gJ` = 2 keys. Inner room accessible.
4. Walk into inner room to X_inner/D_inner area: `r 5j` ≈ navigate through new passage ~6 keys.
5. K2 (12,4): navigate out of inner room, reach row 12: ~7 keys. `x` = 1.
6. Row 12 (join point 2): player already at row 12 col 4. `J` = 1 key.
7. Navigate to D2 (13,39) and X (13,43): `j 39l` = `j`=1, `39l`=3 = 4 keys.

**Par: 5+2+2+6+7+1+1+4 = 28 keystrokes.**
*Par-solver authoritative.*
**Budget: ceil(28 × 1.4) = ceil(39.2) = 40 keystrokes.**
**Margin: 12 keys.**

**Forcing (with irreversible J/gJ):**
- `gJ` for D_inner: wrong command (`J`) produces wrong content → D_inner locked forever. Irreversible. S1. PASS.
- `J` for D2: wrong command (`gJ`) produces wrong content → D2 locked forever. Irreversible. S1. PASS.
- Topology (sealed inner room): only accessible via J/gJ on row 5. ∞ cost otherwise. S1. PASS.

**Primitives used:** sealed room (four solid walls), rune clusters (content-sensitive join trigger), doors, keystones.
**Engine ops:** `J`/`gJ` (new op — row-carve/join; non-undoable per design); engine implementation per LEVELS_PLAN.md D3.

**Self-check:**
- [x] ≤3 new mechanics (1 mechanic family: join/carve, two variants J/gJ).
- [x] Coherent family: J and gJ differ only in the space separator.
- [x] J/gJ topology-forced (sealed inner room inaccessible otherwise). S1.
- [x] J vs gJ distinction content-forced (rune content check, not column-only). S1.
- [x] Undo-hole closed: J/gJ marked non-undoable in engine. CHALLENGE filed.
- [x] BEFORE/AFTER grids shown.
- [x] J/gJ is a new engine op per LEVELS_PLAN.md D3.

---

## L24a — The Alignment Halls

**Commands taught:** `>>` (indent line right by shiftwidth), `<<` (indent line left by shiftwidth).
New mechanics (count: 1):
1. `>>` / `<<` — shift all runes on the current line right/left by INDENT_WIDTH (2 cols) within the row's passable extent (`apply_indent`). This moves *runes*, not floor topology.

**Rune-alignment trigger mechanic:** A gate opens only when a target rune cluster sits at exactly column N. `>>` is cheaper than delete-and-retype for nudging a cluster into position.

**Linkage:** `>>` and `<<` are one mechanic — horizontal rune shift, bidirectional. They belong together as the "indent/unindent" pair.

**Budget multiplier: ×1.4. Esc not needed.**

---

### Forcing derivation (S2)

**`>>` forced over delete+retype:**
- Cluster of 4 glyphs at col C, target col C+2 (1 shiftwidth): `>>` = 2 keys. Delete+retype: `d4l` = 3 keys + `i ∘∘∘∘ Esc` = 6 keys = 9 keys. Savings = 7 keys per zone. With 4 `>>`-zones: saves 28 keys. Budget margin must be < 28.
- Par (4 zones + 4 `<<`-zones + navigation): estimated 40. Budget = ceil(40×1.4)=56. Margin=16. Without `>>` on 4 zones: +28 → 68 > 56. PASS.

**`<<` forced over delete+retype:**
- Same logic, 4 `<<`-zones. Savings = 28 keys (symmetric with `>>`). Already included above.

**`>>` / `<<` keystroke count correction:**
- `>>` = 2 keystrokes (`>`, `>`). `<<` = 2 keystrokes.
- `2>>` = 3 keystrokes (`2`, `>`, `>`). `3>>` = 3 keystrokes (`3`, `>`, `>`). (Review confirmed: 3 keys, not 4.)
- INDENT_WIDTH = 2. To shift by 4 cols (2 shiftwidths): `2>>` = 3 keys. To shift by 6 cols: `3>>` = 3 keys.

---

### Grid

**Dims:** 14 rows × 52 cols

**Final precise grid (14 r × 52 c):**

```
Row  0: ####################################################
Row  1: #@..................................................#
Row  2: #...K_A.............................................#
Row  3: #...∘∘∘∘ (col 5, target col 9)....D_A..............#  ← >> zone 1
Row  4: #...⊕⊕⊕⊕ (col 5, target col 9)....D_B..............#  ← >> zone 2
Row  5: #...∆∆∆∆ (col 5, target col 9)....D_C..............#  ← >> zone 3
Row  6: #...Ωβγδ (col 5, target col 9)....D_D..............#  ← >> zone 4
Row  7: #..K_B..............................................#
Row  8: #...⊙⊙⊙⊙ (col 13, target col 9)...D_E.............#  ← << zone 1
Row  9: #...·∘·∘ (col 13, target col 9)...D_F.............#  ← << zone 2
Row 10: #...ΦΨΩα (col 13, target col 9)...D_G.............#  ← << zone 3
Row 11: #...∇∈∉∊ (col 13, target col 9)...D_H.............#  ← << zone 4
Row 12: #...............................................X...#
Row 13: ####################################################
```

**Placements:**
- `@` entry: (1, 1).
- `X` exit: (12, 47).
- `K_A` keystone: (2, 4) — activates `>>` zone triggers (D_A through D_D).
- `K_B` keystone: (7, 4) — activates `<<` zone triggers (D_E through D_H).
- `D_A`–`D_D` doors: (3,30),(4,30),(5,30),(6,30) — each opens when the corresponding rune cluster on its row sits at col 9 (target). All four must be satisfied to pass through to the `<<` section.
- `>>` zones (rows 3–6): each row has a 4-glyph rune cluster at col 5. Target: col 9 (delta = +4 = 2 shiftwidths). `2>>` = 3 keys. vs delete+retype: 9 keys. Savings = 6 keys per zone.
- `D_E`–`D_H` doors: (8,30),(9,30),(10,30),(11,30) — each opens when corresponding rune cluster sits at col 9. All four must be satisfied.
- `<<` zones (rows 8–11): each row has a 4-glyph rune cluster at col 13. Target: col 9 (delta = -4 = 2 shiftwidths left). `2<<` = 3 keys. vs delete+retype: 9 keys. Savings = 6 keys per zone.

**Optimal keystrokes (S3 full recount):**
1. K_A (2,4): `j 3l x` = `j`=1, `3l`=2, `x`=1 = 4 keys.
2. Row 3, `2>>`: `j 2>>` = `j`=1, `2>>`=3 = 4 keys. D_A met.
3. Row 4, `2>>`: `j 2>>` = 4 keys. D_B met.
4. Row 5, `2>>`: `j 2>>` = 4 keys. D_C met.
5. Row 6, `2>>`: `j 2>>` = 4 keys. D_D met.
6. K_B (7,4): `j 26h x` = `j`=1, `26h`=3, `x`=1 = 5 keys.
7. Row 8, `2<<`: `j 8l 2<<` = `j`=1, `8l`=2, `2<<`=3 = 6 keys. D_E met.
8. Row 9, `2<<`: `j 2<<` = `j`=1, `2<<`=3 = 4 keys. D_F met.
9. Row 10, `2<<`: `j 2<<` = 4 keys. D_G met.
10. Row 11, `2<<`: `j 2<<` = 4 keys. D_H met.
11. Navigate to X (12,47): `j 34l` = `j`=1, `34l`=3 = 4 keys.

**Par: 4+4+4+4+4+5+6+4+4+4+4 = 47 keystrokes.**
**Budget: ceil(47 × 1.4) = ceil(65.8) = 66 keystrokes.**
**Margin: 19 keys.**

**Forcing verification:**
- `>>` zones: 4 zones × 6-key savings = 24 keys. Without `>>`: par+24 = 71 > 66. PASS.
- `<<` zones: 4 zones × 6-key savings = 24 keys. Without `<<`: par+24 = 71 > 66. PASS.
- Each direction individually forced. PASS.
- `>>` keystroke count: `2>>` = 3 keys (2, >, >) confirmed.
- `3>>` = 3 keys (3, >, >) — corrected from blueprint's "4 keys" error.

**S4 block:** Long-row `$` jumps and `0` jumps could move the cursor to col 0 or end-of-row before doing a manual delete+retype. The `>>` command shifts the rune cluster in-place without moving the cursor far — `>>` is strictly cheaper than any other approach because no `d`/`i` is needed.

**Primitives used:** rune-column triggers (gate at exact col), doors (8 doors, 4 per direction), keystones, rune clusters at off-target positions.
**Engine ops:** `apply_indent` (`>>`, `<<`).

**Self-check:**
- [x] ≤3 new mechanics (1: >> / << horizontal rune shift, bidirectional).
- [x] Coherent family: >> and << are the same shift mechanic in two directions.
- [x] `>>` individually forced: 4 zones × 6-key savings = 24 > margin 19. PASS.
- [x] `<<` individually forced: same analysis. PASS.
- [x] `>>` and `3>>` keystroke count corrected (2 and 3, not 4).
- [x] Rune-column trigger is the natural dungeon primitive for alignment.
- [x] No topology changes; purely rune-position manipulation.

---

## L24b — The Indentation Sanctum

**Commands taught:** `>{motion}` / `<{motion}` (indent over motion span), `=` (auto-indent / re-align).
New mechanics (count: 2):
1. `>{motion}` / `<{motion}` — indent/unindent operator applied over a motion span (multiple rows shifted in one command).
2. `=` — auto-indent: aligns rune cluster to the "standard" column for its row context (computed per row, not a fixed delta).

**Linkage:** `>{m}` and `<{m}` extend `>>` / `<<` to multi-row scope — same shift mechanic, operator form. `=` is the "smart shift" variant that computes the target column automatically. All three are horizontal rune alignment commands.

**Budget multiplier: ×1.4. Esc not needed.**

**`>{motion}` keystroke count:** `>2j` = 3 keystrokes (`>`, `2`, `j`). `<2j` = 3 keystrokes. `=2j` = 3 keystrokes.

---

### Forcing derivation

**`>{m}` forced over per-row `>>`:**
- 4-row alignment zone: each row needs 1 shiftwidth right. `>3j` = 3 keys (shifts rows current→current+3 = 4 rows, 1 shiftwidth each). vs `>>` × 4 rows + 3 `j` navigations: `>>j>>j>>j>>` = 4×2 + 3×1 = 11 keys. Savings = 8 keys per 4-row zone. With 2 such zones: saves 16 keys. Budget margin must be < 16.

**`<{m}` forced over per-row `<<`:**
- 4-row unindent zone: same analysis. `<3j` = 3 keys vs `<<j<<j<<j<<` = 11 keys. Savings = 8 per zone.

**`=` forced over manual `>>`/`<<`:**
- Variable-delta zone: 3 rows with different target offsets (row A needs +2, row B needs +6, row C needs +4). `=2j` = 3 keys (auto-aligns all 3 to their computed targets). Manual: `>>` (A, delta=2=1×INDENT_WIDTH) = 2 keys, `j 3>>` (B, delta=6=3×INDENT_WIDTH) = 4 keys, `j 2>>` (C, delta=4=2×INDENT_WIDTH) = `j`=1+`2>>`=3=4 keys. Total manual = 2+4+4+2nav = 12 keys. `=` saves 9 keys. With 2 `=`-zones: saves 18 keys.
- Budget margin: with `>{m}` zone savings (16) and `=` zone savings (18): combined without all = +34. Par ≈ 36. Budget = ceil(36×1.4)=51. Without both: 36+34=70 >> 51. Each individually: +16 > margin? Margin = 51-36 = 15. Without `>{m}` only: +16 > 15. PASS. Without `=` only: +18 > 15. PASS. Both individually forced.

---

### Grid

**Dims:** 16 rows × 48 cols

**Final precise grid (16 r × 48 c):**

```
Row  0: ################################################
Row  1: #@..............................................#
Row  2: #...K_A.........................................#
Row  3: #...∘∘ (col 5, target col 7)....................#  ← >{m} zone 1 row A
Row  4: #...∘∘ (col 5, target col 7)....................#  ← >{m} zone 1 row B
Row  5: #...∘∘ (col 5, target col 7)....................#  ← >{m} zone 1 row C
Row  6: #...∘∘ (col 5, target col 7)....D_A............#  ← >{m} zone 1 row D (gate condition: all 4 at col 7)
Row  7: #..K_B..........................................#
Row  8: #...⊙⊙ (col 9, target col 7)....................#  ← <{m} zone row A
Row  9: #...⊙⊙ (col 9, target col 7)....................#  ← <{m} zone row B
Row 10: #...⊙⊙ (col 9, target col 7)....................#  ← <{m} zone row C
Row 11: #...⊙⊙ (col 9, target col 7)...D_B.............#  ← <{m} zone row D
Row 12: #...K_C.........................................#
Row 13: #...∆∆ (col 3, target col 5)....................#  ← = zone row A (needs +2)
Row 14: #...∆∆ (col 3, target col 9)....................#  ← = zone row B (needs +6)
Row 15: #...∆∆ (col 3, target col 7)...D_C.....X.......#  ← = zone row C (needs +4)
################################################
```

**Placements:**
- `@` entry: (1, 1).
- `X` exit: (15, 42).
- `K_A` keystone: (2, 4) — activates D_A.
- `D_A` door: (6, 34) — opens when all 4 rune clusters on rows 3–6 sit at col 7.
- `>{m}` zone: rows 3–6, each has cluster `∘∘` at col 5. Target: col 7 (delta = +2 = 1 shiftwidth). `>3j` from row 3 = 3 keys (shifts rows 3,4,5,6 by 1 shiftwidth). All 4 rows satisfied. vs per-row `>>`: `>>j>>j>>j>>` = 11 keys. Savings = 8 keys.
- `K_B` keystone: (7, 4) — activates D_B.
- `D_B` door: (11, 34) — opens when all 4 rune clusters on rows 8–11 sit at col 7.
- `<{m}` zone: rows 8–11, each has cluster `⊙⊙` at col 9. Target: col 7 (delta = -2 = 1 shiftwidth left). `<3j` from row 8 = 3 keys. Savings = 8 keys.
- `K_C` keystone: (12, 4) — activates D_C.
- `D_C` door: (15, 34) — opens when all 3 rune clusters on rows 13–15 sit at their respective target columns.
- `=` zone: row 13 cluster `∆∆` at col 3, target col 5 (+2); row 14 cluster at col 3, target col 9 (+6); row 15 cluster at col 3, target col 7 (+4). `=2j` from row 13 = 3 keys (auto-aligns rows 13,14,15 to their computed targets). vs manual: 12 keys. Savings = 9 keys.
- Second `>` zone (rows 3–6) is the only `>{m}` zone; a second `<{m}` scenario (rows 8–11) is the `<{m}` zone. Two directions covered.

**Optimal keystrokes (S3 full recount):**
1. K_A (2,4): `j 3l x` = 4 keys.
2. Row 3: `j` = 1. `>3j` = 3 keys. D_A all-four satisfied.
3. D_A (6,34): walk through: `3j 27l` = `3j`=2, `27l`=3 = 5 keys.
4. K_B (7,4): `j 30h x` = `j`=1, `30h`=3, `x`=1 = 5 keys.
5. Row 8: `j 8l` = `j`=1, `8l`=2 = 3 keys. `<3j` = 3 keys.
6. D_B (11,34): `3j 25l` = `3j`=2, `25l`=3 = 5 keys.
7. K_C (12,4): `j 30h x` = 5 keys.
8. Row 13: `j` = 1. `=2j` = 3 keys.
9. D_C (15,34): `2j 31l` = `2j`=2, `31l`=3 = 5 keys.
10. X (15,42): `8l` = 2 keys.

**Par: 4+1+3+5+5+3+3+5+5+1+3+5+2 = 45 keystrokes.**
**Budget: ceil(45 × 1.4) = ceil(63) = 63 keystrokes.**
**Margin: 18 keys.**

**Forcing verification:**
- `>{m}` (1 zone, saves 8): without `>{m}`: par+8 = 53 ≤ 63. NOT individually forced with 1 zone!
- **Add second `>{m}` zone** (rows 3–6 become two such zones, doubling the grid): 2 zones × 8 keys = 16 savings. Par grows by ~10 (extra traversal) = 55. Budget = ceil(55×1.4) = 77. Without `>{m}`: 55+16=71 ≤ 77. Still not forced!
- **Root issue same as before:** More zones → larger par → larger budget. Savings don't outpace margin growth.
- **Fix:** Use 4-row zones with 2 shiftwidths required (delta = +4 = 2 shiftwidths). `>{m}` applied twice: `>3j >3j` = 6 keys. vs per-row `>>` twice each: `2>>j2>>j2>>j2>>` (each row needs `2>>` = 3 keys) = 3×4+3nav = 15 keys. Savings = 9 per zone. Same problem.
- **Alternative fix (S1 adopted):** The `>{m}` zone rooms are physically arranged so that the player MUST shift multiple rows from a SINGLE position. Specifically: the player is in a pit (a 1-cell-wide corridor running vertically, enclosed by walls on both sides) with no ability to move left/right to access individual rows. From the pit, `>>` only affects the current row. To shift all 4 rows, the player must use `>3j` (which operates on 4 rows at once from the current cursor position). Attempting to use `>>` per row requires leaving the pit (impossible — walls on all sides of the pit corridor) or repositioning. The pit structure makes per-row `>>` impossible — the player cannot access each row individually because the wall constraints of the pit prevent left/right movement. **∞ cost for per-row approach. S1. PASS.**

**S1 pit design for `>{m}`:**
- `>{m}` zone is a vertical 1-cell corridor (pit), cols 4–4 only (1-col wide), rows 3–6. Player is at (3,4). `>3j` shifts all 4 rows (3,4,5,6) by 1 shiftwidth simultaneously. `>>` shifts only the current row; player cannot `j` to next row and `>>` because they'd need to also be at col 4 of the next row — but they are! Actually in a 1-cell-wide pit, `j` is available (player can move up/down). Per-row `>>` is possible: `>>j>>j>>j>>` from col 4 = 11 keys. `>3j` = 3 keys. Budget savings = 8. Need savings > margin.
- **Revised: the pit design forces `>{m}` if moving `j` between rows is blocked.** Make the pit have water at rows 4 and 5 (impassable except via `>{m}`'s row-skip). `>3j` shifts rows 3–6 from row 3 without requiring the player to step on rows 4/5. But `>>j>>j>>j>>` requires stepping on rows 4 and 5 (water = death). **Water forcing: the player cannot `j` through water to reach rows 4,5 for individual `>>`; only `>3j` (applied from row 3) reaches all rows without cursor movement. S1 forcing with water.**

**S1 water design for `>{m}` (adopted):**
- Rows 4 and 5 of the `>{m}` zone have water tiles (lethal to step on). The rune clusters on rows 4 and 5 are above water (they exist as rune cells but their floor tile is water).
- `>3j` from row 3: applies indent to rows 3,4,5,6 without moving the cursor to those rows. The operator acts on the CELLS, not the cursor path. Engine `apply_indent` iterates over rows in the motion span regardless of cursor position. Result: all 4 clusters shifted. **S1 PASS: player cannot `j` into water rows to do per-row `>>`.**
- `<3j` zone: same design, rows 9 and 10 have water. `<3j` from row 8 shifts all four `<` rows.
- `=` zone: rows 14 and 15... player needs to step on row 15 to reach X. Use a different structure: `=2j` from row 13 aligns rows 13,14,15. Rows 14 is water, so player cannot `>>` it manually. S1.

**Revised par (with water-blocked zones, mostly same):**

*Par unchanged since water-tile rows don't affect the cursor path (player stays at row 3, 8, 13 respectively to issue the operator commands). Navigation adjusts slightly:*

**Par: 4+1+3+5+5+3+3+5+5+1+3+5+2 = 45 keystrokes (same).**
**Budget: 63. Margin: 18.**

**Forcing (S1 water):**
- `>{m}`: per-row `>>` requires stepping onto water rows (lethal). `>3j` from dry row works. ∞ cost for per-row approach. S1. PASS.
- `<{m}`: same. S1. PASS.
- `=`: per-row `>>` requires stepping onto water row 14 (lethal). `=2j` from row 13 works. S1. PASS.

**Primitives used:** water tiles (lethal), rune-column triggers, doors, keystones, rune clusters at off-target positions.
**Engine ops:** `apply_indent` (`>{m}`, `<{m}`); `apply_autoindent` (`=`).

**Self-check:**
- [x] ≤3 new mechanics (2: >{m}/<{m} operator-scope indent, = auto-indent).
- [x] Coherent family: all are horizontal rune shift commands, multi-row scope.
- [x] `>{m}` S1-forced: water tiles on intermediate rows block per-row `>>`. PASS.
- [x] `<{m}` S1-forced: same. PASS.
- [x] `=` S1-forced: water tile on row 14 blocks manual `>>` for that row. PASS.
- [x] `>{motion}` keystroke count: `>3j` = 3 keys (>, 3, j). `<3j` = 3 keys. `=2j` = 3 keys.
- [x] No topology changes; purely rune-position manipulation.
- [x] CHALLENGE: engine must support `apply_indent` / `apply_autoindent` on rows the cursor does not occupy (operator acts on motion range, not cursor path).

---

## L24.1 — The Warden Scrivener (ACT V BOSS)

**Commands:** All Act V commands (i a I A o O r R ~ g~ gU gu J gJ >> << >{m} <{m} =).
**Phases:** 5 phases (one command per phase). Each phase: Warden is immune to all Act V commands except one; the correct command dissolves the rune shield; then `x` deals damage.

**Boss mechanic:** The Warden Scrivener is a multi-phase combat entity surrounded by a rune field. Each phase:
1. The Warden projects a **rune shield** that must be transformed using the phase command.
2. Wrong command attempts waste keystrokes (budget drain). Warden chases (speed varies).
3. A **scroll** (in chest at entry) reveals the phase commands.

**Phase table:**

| Phase | HP | Warden action | Required command | Rune condition | Immune to |
|-------|-----|---------------|-----------------|----------------|-----------|
| 1 | 3 | Stationary | `r{ch}` | Replace 3 wrong-glyph shield cells with correct glyphs; then `x` | All except `r` |
| 2 | 3 | Slow chase (speed 4) | `gU{motion}` | Uppercase the rune cluster on Warden's row; then `x` | All except `gU` |
| 3 | 3 | Medium chase (speed 3) | `J` | Join-carve the sealed wall below Warden's row to expose weak point; then `x` | All except `J` |
| 4 | 3 | Fast chase (speed 2) | `gJ` | Join-carve the second sealed row (no space, exact-col weak point); then `x` | All except `gJ` |
| 5 | 4 | Fast + 2 goblins | `>>` | Shift alignment-lock rune to col 14 (Warden's weak-point column); then `x` | All except `>>` |

---

### Boss grid (18 r × 52 c)

```
Row  0: ####################################################
Row  1: #[chest]...........................................#
Row  2: #...K..............................................#
Row  3: #@.................................................#
Row  4: #...................................................#
Row  5: ############################################.......#  ← phase gate (opens after phase 1)
Row  6: #....W_P1...........................................#  ← phase 1 Warden (stationary)
Row  7: #....X.X.X. (shield: 3 wrong-glyph cells)..........#  ← wrong glyphs at cols 5,7,9
Row  8: ############################################.......#  ← phase gate 2
Row  9: #....W_P2...........................................#  ← phase 2 Warden (slow chase)
Row 10: #....abcdef (all-lower cluster, needs gU)...........#
Row 11: ############################################.......#  ← phase gate 3
Row 12: #....W_P3...........................................#  ← phase 3 Warden (medium chase)
Row 13: ##########(sealed wall — J target)..................#  ← J joins row 12+13; weak point exposed
Row 14: ############################################.......#  ← phase gate 4
Row 15: #....W_P4...........................................#  ← phase 4 Warden (fast chase)
Row 16: ##########(sealed wall — gJ target).................#  ← gJ joins row 15+16; exact-col weak point
Row 17: ############################################.......#  ← phase gate 5
Row 18: #....W_P5....g.....g...............................#  ← phase 5 Warden (fast + 2 goblins)
Row 19: #....⊕ (lock rune at col 8, target col 14)..........#
####################################################
```

*(Grid is 20 rows × 52 cols for the boss encounter.)*

---

### Phase details (corrected pars)

**Phase 1 — `r{ch}` (replace, stationary):**
- Warden at (6, 4). Shield: 3 wrong-glyph cells at row 7, cols 5, 7, 9 (`X₁ X₂ X₃`).
- Correct glyphs: `∘ · ⊙`. Player must `r∘` at col 5, `2l r·` at col 7, `2l r⊙` at col 9.
- Shield dissolves → Warden vulnerable → player moves to (6,4), `x`.
- **Phase 1 par recount (S3):**
  - Entry at (3,1). Navigate to K (2,4): `j 3l x` = 4 keys.
  - Navigate to row 7 col 5: `4j 4l` = `4j`=2, `4l`=2 = 4 keys.
  - `r∘ 2l r· 2l r⊙` = 2+2+2+2+2 = 10 keys.
  - Navigate to Warden (6,4) to `x`: `k h` = 2 keys. `x` = 1.
  - Phase 1 subtotal: 4+4+10+2+1 = **21 keys**.
  - Blueprint had 12 — corrected.

**Phase 2 — `gU{motion}` (uppercase, slow chase speed 4):**
- Warden at (9,4). Rune cluster `abcdef` at row 10, cols 4–9 (one WORD).
- `gUW` = 3 keys → `ABCDEF`. Warden vulnerable → `x`.
- **Phase 2 par recount:**
  - Navigate from phase-1 exit area to phase-2 area, past phase gate 2: ~4 keys.
  - Position at row 10 col 4: `j` = 1.
  - `gUW` = 3 keys.
  - Navigate to Warden (9,4) `x`: `k x` = 2 keys.
  - Phase 2 subtotal: 4+1+3+2 = **10 keys**.

**Phase 3 — `J` (join, medium chase speed 3):**
- Warden at (12,4). Row 13 is a sealed wall row directly below (cols 0–9 are `#`, rest passable).
- `J` on row 12: joins row 13's floor content onto row 12 with a space. The join exposes the Warden's weak point at col 9 (the content of row 13 at col 9 is a `★` weak-point marker; after J, `★` is now on row 12 at col 9+1=10 with the space offset — wrong col! Use `gJ` to get exact col... wait, but Phase 3 forces `J` and Phase 4 forces `gJ`).
- **Phase 3 revised:** Row 13 contains `★` at col 8. After `J` (with space): `★` lands at col 13+1=... Let's say row 12 currently has content up to col 8 (Warden and shield at cols 4–8). `J` appends row 13's content at col 9 (one space after last char at col 8). Row 13 has `★` at col 0 (its leftmost). After join: col 9 = space, col 10 = `★`. Weak point now at col 10 of row 12. Warden moves to col 10. Player `x` at col 10.
- Alternatively: **Phase 3 simply uses `J` to carve open the wall row below to expose a passage**. The weak-point rune is irrelevant to column; the join action itself opens a sealed corridor exposing the Warden's back. `J` required. Wrong command: `gJ` produces different content (different col offset for weak-point detection by the engine). The phase-3 trigger checks for J-style join (space present in joined content).
- **Phase 3 par:**
  - Navigate past gate 3 to phase-3 arena: ~4 keys.
  - `J` = 1 key. Warden exposed.
  - Navigate to Warden `x`: ~3 keys.
  - Phase 3 subtotal: 4+1+3 = **8 keys**.

**Phase 4 — `gJ` (join without space, fast chase speed 2):**
- Warden at (15,4). Row 16 is sealed below. `gJ` joins without space; weak-point rune from row 16 lands at exact col (col 5 = last char of row 15 + 0 space). Phase-4 trigger requires no-space join (content check). `J` would push weak-point rune 1 col right, trigger fails.
- **Phase 4 par:**
  - Navigate past gate 4: ~3 keys.
  - `gJ` = 2 keys. Warden exposed.
  - Navigate to Warden `x`: ~3 keys.
  - Phase 4 subtotal: 3+2+3 = **8 keys**.

**Phase 5 — `>>` (indent, fast chase + 2 goblins):**
- Warden at (18,4). Lock rune `⊕` at row 19, col 8. Target col 14 (delta = +6 = 3 shiftwidths). `3>>` = 3 keys (`3`,`>`,`>`) — not 4 (corrected from original blueprint error).
- Lock rune shifts → col 14 = Warden's weak-point column → Warden vulnerable → `x`.
- 2 goblins also chase (spawn at (18,20) and (18,35) post-phase-4).
- **Phase 5 par:**
  - Navigate past gate 5 while avoiding goblins: ~5 keys.
  - Position at row 19: `j` = 1.
  - `3>>` = 3 keys.
  - Navigate to Warden (18,4) `x` while goblins approach: ~4 keys.
  - Phase 5 subtotal: 5+1+3+4 = **13 keys**.

**Phase immunity clarifications (corrected):**
- Phase 2: immune to all except `gU`. (Immunity description tightened — only `gU` works, not `gu`/`g~`; the rune requires uppercasing specifically.)
- Phase 3: immune to all except `J`.
- Phase 4: immune to all except `gJ`.
- Each phase: exactly ONE correct command. One-command-per-phase rule satisfied.

**Par (total boss encounter):** 21+10+8+8+13 = **60 keystrokes**.
**Budget:** ceil(60 × 1.4) = ceil(84) = **84 keystrokes**.

*(Note: original blueprint had par=59 from undercounted phase 1. Corrected to 60.)*

**Self-check:**
- [x] 5 phases, each demands exactly one Act V command.
- [x] Boss numbered 24.1 (x.1 convention).
- [x] Phases escalate: stationary → slow chase → medium chase → fast chase → fast+goblins.
- [x] Each phase has a clear rune condition before `x` damage (immune mechanic).
- [x] Phase commands span the act: r (overwrite), gU (case), J (join), gJ (join-no-space), >> (indent).
- [x] Phase 3 and Phase 4 are split (J and gJ each have their own phase). One command per phase. PASS.
- [x] Phase 1 par corrected to 21 (from 12). Total par corrected to 60 (from 59).
- [x] `3>>` = 3 keystrokes (3, >, >) confirmed and corrected.
- [x] Scroll chest in pre-boss area reveals phase commands.
- [x] CHALLENGE: Phase 3/4 J/gJ boss phases depend on J/gJ being non-undoable and distinguishable by rune-content output. Engine must mark J/gJ as phase triggers based on content type.

---

## Summary

| Level | Commands | Par | Budget | Forceable? | Key risks |
|-------|----------|-----|--------|------------|-----------|
| L20 — Inscription Halls | `i a` | 31 | 44 (×1.4) | Yes — `i` S1-terrain-forced (wall blocks `a`); `a` S1-guided (contamination) | `a`-trigger: +1 undo penalty only; soft forcing. CHALLENGE filed. |
| L21 — Sculpting Chambers | `I A o O` | ~35 | 49 (×1.4) | Yes — `o`/`O` S1-topology; `A`/`I` budget-forced (4A-triggers saves 12 > margin; 3I-triggers saves 9 > margin) | Par-solver must confirm with wider 60-col map and 4 A-triggers + 3 I-triggers |
| L22 — Overwrite Halls | `r R` | 39 | 45 (×1.15) | Yes — `r` individually forced (39+9=48>45); `R` individually forced (39+11=50>45); STRICT ✓ | w-hop navigation between r-cells; void isolation blocks R on r-corridor |
| L23 — Case Chambers | `~ g~ gU gu` | 52 | 73 (×1.4) | Yes — `gUW`/`guW`/`g~W` budget-forced (~-only path=74>73); `~` S1-forced by runtime-random case | Par corrected (52, not 28); `gUW` = 3 keys (WORD motion, no count digit) |
| L24 — Joiner's Gate | `J gJ` | 28 | 40 (×1.4) | Yes — S1 topology + S1 rune-content; both J and gJ forced | CHALLENGE: J/gJ must be non-undoable in engine |
| L24a — Alignment Halls | `>> <<` | 47 | 66 (×1.4) | Yes — 4 zones each direction; savings (24) > margin (19) | `3>>` = 3 keystrokes corrected |
| L24b — Indentation Sanctum | `>{m} <{m} =` | 45 | 63 (×1.4) | Yes — S1 water tiles block per-row approach; operator forced | CHALLENGE: engine must apply indent to rows cursor does not occupy |
| L24.1 — Warden Scrivener | All Act V | 60 | 84 (×1.4) | Yes — per-phase immunity + 5 distinct phases | Phase 1 par corrected (21, not 12); Phase 3/4 J/gJ split into separate phases |

---

## CHALLENGES (requiring human/engine decision)

1. **`a`-trigger in L20 (soft forcing):** The `a`-trigger uses a contamination mechanic (+1 key penalty for wrong command). This does not exceed the ×1.4 budget margin. The level teaches `a` but does not hard-force it. Options: (a) accept soft forcing as sufficient for the first Insert-mode level; (b) redesign with a column-placement puzzle where the `a`-trigger cell is at the rightmost wall of a sealed slot (so `a` must write AT the rightmost passable cell — `i` would write one cell left, leaving the trigger unsatisfied AND the player cannot reposition because the slot's right wall blocks further movement). Decision needed.

2. **L22 individual r and R — RESOLVED:** Compact single-row layout (par=39, ×1.15, budget=45, margin=6) makes r (savings=9>6) and R (savings=11>6) individually forced. Challenge closed.

3. **J/gJ non-undoable (engine decision):** Levels L24 and L24.1 (phases 3/4) require `J`/`gJ` to be non-undoable or to produce visibly different/irreversible world states that make undo+retry unhelpful. The engine must either: (a) mark J/gJ as non-undoable ops; (b) have the join produce a locked rune state that undo would not restore correctly (content-sensitive undo). Decision needed from engine maintainer.

4. **`>{m}` operator on non-cursor rows (engine prerequisite):** L24b requires `apply_indent` (and `apply_autoindent` for `=`) to act on all rows in the motion span without requiring the cursor to visit each row. This must be verified as an engine capability. If `>{m}` currently only applies indent to the cursor's row (ignoring the motion), L24b's forcing model breaks. Decision: verify or implement multi-row indent operator in engine before finalizing L24b design.

5. **J/gJ op implementation (engine prerequisite):** `J`/`gJ` are listed in LEVELS_PLAN.md as unimplemented. The boss phases 3 and 4 depend on J/gJ producing distinguishable content outputs (with/without space) that the trigger system can check. The engine must implement J/gJ as specified in LEVELS_PLAN.md D3 before these levels can be generated and tested.

6. **L21 map size and par-solver:** L21 adopts a 60-col map with 4 `A`-triggers and 3 `I`-triggers. The par-solver must confirm that: (a) the optimal path uses `A` for all `A`-triggers (not manual walk); (b) the optimal path uses `I` for all `I`-triggers; (c) the resulting par and budget satisfy the forcing inequalities stated in the blueprint. Par-solver run required before finalizing L21's generator code.
