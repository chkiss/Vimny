# Act VII — Mastery Blueprints

> ⚠ **Pre-implementation design doc — obsolete conventions; delete-on-implement.** Uses pre-slug naming (e.g. `RuneCluster` → now `CharRun`; level numbers are now the cosmetic `display` field) — don't copy these symbols. **Delete a level's section when that level ships, and the whole file once its act is built.** See LEVELS_PLAN Part 8.

> Levels 37, 38, and 38.1. Commands: `:s/{}/{}/[g]`, `q @ "`. Capstone act.
> All three share one coherent family: **power automation** — transform many
> targets with a single compound command, then industrialise repetition.

**Design principles applied (Part 5 S1–S4):**
- S1 — terrain-infinity first: where possible make the alternative path *impossible*
  (impassable terrain = infinite cost), not merely more expensive.
- S2 — tight budget fallback: where margin-forcing is unavoidable, set the multiplier
  so the next-best route STRICTLY exceeds budget; document the multiplier explicitly.
- S3 — par is the TRUE full min-keystroke solution, entry→exit, all navigation included.
- S4 — earlier commands blocked so newly-taught command remains required.

---

## Level 37 — The Spellwright's Forge

**Commands taught:** `:s/{from}/{to}/` and `:s/{from}/{to}/g`

### New mechanics (3 of ≤3 allowed)

1. **Arcane Mana pool** — displayed in the status bar. Current mana is consumed by
   `:s` commands. Mana does not recharge mid-room; it is reset at room entry.
   - `:s/{}/{}/` — costs 1 mana, transforms first match on current row.
   - `:s/{}/{}/g` — costs 3 mana, transforms ALL matches on current row.
2. **Fire terrain `F`** — impassable (player is blocked, cannot step onto an `F` tile).
   This is S1 terrain-infinity: crossing a fire row without clearing it is *impossible*,
   not merely expensive.
3. **Ice terrain `I`** — produced by `:s/F/I/g`; passable floor. `:s` is the only engine
   action that converts terrain glyphs; `d`, `c`, `r` and other operators do NOT affect
   terrain tiles (terrain is not a rune-entity).

*(Scope note: blueprint v1 claimed "1 new mechanic". Corrected count is 3: mana pool,
F terrain, `:s` command. This is the legal maximum; count is accurate.)*

**Linkage:** `:s` is command-mode (`:` already known from Level 1 `:w/:q`).
The `/from/to/g` syntax and mana gate are the only new ideas. Substitution applies
to terrain glyphs (`F`=fire, `I`=ice) — not enemies (SPEC §6.4).

**`dd` / `dw` hatch explicitly closed:** Deletion operators (`dd`, `dw`, `d$`, `D`)
do not affect terrain tiles. Fire tiles are terrain, not rune-entities. A `dd` on a
fire row deletes any rune-entities on that row but leaves the fire terrain intact and
the row still impassable. This must be enforced in `engine/operator.py`'s terrain
dispatch.

---

### Grid

```
Dimensions: 16 rows × 52 cols  (@=entry, X=exit, F=fire impassable, I=ice passable, K=keystone)

Row  0: ####################################################
Row  1: #@..................................................#   <- entry row 1, col 1
Row  2: #...................................................#
Row  3: ####################################################
Row  4: #...FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF...#   <- fire corridor 1 (46 F tiles)
Row  5: #...................................................#
Row  6: ####################################################
Row  7: #...FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF...#   <- fire corridor 2 (46 F tiles)
Row  8: #...................................................#
Row  9: ####################################################
Row 10: #...FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF...#   <- fire corridor 3 (46 F tiles)
Row 11: #...................................................#
Row 12: ####################################################
Row 13: #K..................................................#   <- keystone row 13, col 1
Row 14: #...................................................#
Row 15: #.................................................X.#   <- exit row 15, col 49
Row 16: ####################################################
```

**Exact blueprint (17 rows × 52 cols):**

```
####################################################
#@..................................................#
#...................................................#
####################################################
#...FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF...#
#...................................................#
####################################################
#...FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF...#
#...................................................#
####################################################
#...FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF...#
#...................................................#
####################################################
#K..................................................#
#...................................................#
#.................................................X.#
####################################################
```

- **@** entry: row 1, col 1
- **X** exit: row 15, col 49
- **K** keystone (unlocks exit door): row 13, col 1
- **F** fire tiles: rows 4, 7, 10 cols 3–48 = **46 F tiles per row** (col 48 − col 3 + 1 = 46)
- Three fire rows span full corridor width; walls at cols 0–2 and 49–51 are `#`. No
  navigable path exists around the fire rows — S1 terrain-infinity in full effect.
- Each fire row is converted to **I** (ice, passable) by `:s/F/I/g`.
- The keystone at row 13 is collected with `x`; it opens the exit door at row 15.

**Mana allocation:**
- Each fire-row crossing room: mana = 8 at entry (enough for exactly one `:s/F/I/g` per
  room, with 5 mana remaining — mana reset per room, cross-room stockpiling impossible).
- The mana gate enforces `g` flag: without `g`, each `:s/F/I/` clears only 1 of 46 F
  tiles per invocation (1 mana each). Clearing all 46 tiles without `g` requires 46 mana
  per row; pool = 8. Hard fail after 8 invocations. This is a hard block (run out of mana
  before row is passable), not a budget penalty.

*(Budget is a single level-wide counter; there is no separate per-room budget. The
per-room budget figure in the v1 blueprint was noise and is removed.)*

---

### Placements

| Thing | Location | Notes |
|---|---|---|
| Entry `@` | row 1, col 1 | — |
| Fire row 1 | row 4, cols 3–48 | 46 F tiles; impassable terrain |
| Fire row 2 | row 7, cols 3–48 | 46 F tiles; impassable terrain |
| Fire row 3 | row 10, cols 3–48 | 46 F tiles; impassable terrain |
| Keystone K | row 13, col 1 | `x` to collect; opens exit door |
| Exit `X` | row 15, col 49 | K-gated |
| Wanderer enemy | row 4, col 25 | patrols row 4 (existing entity type) |
| Wanderer enemy | row 7, col 25 | patrols row 7 |
| Wanderer enemy | row 10, col 25 | patrols row 10 |
| Mana orb (chest) | row 1, col 40 | +3 mana bonus (hints the system) |
| Scroll: `:s` | room entry | "`:s/F/I/g` turns the whole row to ice." |

---

### Intended optimal solution

**Navigation geometry (corrected from v1):**

| Step | From → To | Command | Keys | Running total |
|---|---|---|---|---|
| 1 | row 1 → row 4 (fire row 1) | `3j` | 2 | 2 |
| 2 | Clear row 4 | `:s/F/I/g<CR>` | 9 | 11 |
| 3 | Step through row 4 → row 5 | `j` | 1 | 12 |
| 4 | row 5 → row 7 (fire row 2) | `2j` | 2 | 14 |
| 5 | Clear row 7 | `:s/F/I/g<CR>` | 9 | 23 |
| 6 | Step through row 7 → row 8 | `j` | 1 | 24 |
| 7 | row 8 → row 10 (fire row 3) | `2j` | 2 | 26 |
| 8 | Clear row 10 | `:s/F/I/g<CR>` | 9 | 35 |
| 9 | Step through row 10 → row 11 | `j` | 1 | 36 |
| 10 | row 11 → row 13 (keystone) | `2j` | 2 | 38 |
| 11 | Collect keystone | `x` | 1 | 39 |
| 12 | row 13 → row 15 (exit row) | `2j` | 2 | 41 |
| 13 | col 1 → col 49 (exit) | `48l` | 3 | 44 |

**Full keystroke string (canonical):** `3j :s/F/I/g<CR> j 2j :s/F/I/g<CR> j 2j :s/F/I/g<CR> j 2j x 2j 48l`

*(v1 used `4j` for the first fire row, which moves from row 1 to row 5, bypassing row 4.
Corrected to `3j`. v1 also used `3j` for keystone nav from row 11, which reaches row 14.
Corrected to `2j`. Both were off-by-one.)*

---

### Par + Budget

| | |
|---|---|
| **Par** | **44 keystrokes** (corrected from v1's 47) |
| **Budget** | ceil(44 × 1.4) = **62 keystrokes** (multiplier 1.4 is sufficient; S1 terrain-infinity does the primary forcing) |
| **Mana per fire row** | 8 at room entry; `:s/F/I/g` costs 3 |

---

### Forcing argument (dual gate)

**Gate 1 — S1 terrain-infinity (primary):**
Fire rows are impassable. There is no navigable route from entry to exit that avoids all
three fire rows (walls seal both sides of every corridor; confirmed by layout). A player
who does not clear the fire rows cannot advance. The cost of "not using `:s`" is infinite,
not merely high. This is the strongest possible forcing primitive.

**Gate 2 — Mana eliminates bare `:s/F/I/` (no `g` flag):**
Each room's mana pool is 8. Clearing 46 F tiles without the `g` flag requires 46
invocations of `:s/F/I/` (1 mana each = 46 mana per row). Pool exhausts after 8
invocations; remaining 38 tiles stay as impassable `F`. The row is still blocked.
This mana gate is a hard block (not a budget penalty), eliminating the bare-`:s` path.

**Gate 3 — Budget eliminates `r I` per-tile replace (edge case):**
Even if a player attempted `r I` (2 keystrokes per tile, no mana cost), clearing 46
tiles per row = 92 keystrokes per row × 3 rows = 276 keystrokes. 276 >> budget 62.
Blocked. (Note: `r` mutates rune-entities, not terrain — so `r I` on a fire tile is
a no-op per the terrain rule above. Belt-and-suspenders: budget also blocks it.)

**Only `:s/F/I/g` (3 mana, 9 keystrokes) passes all three gates.**

---

### Primitives used

- Walls, fire terrain `F` (impassable), ice terrain `I` (passable via `:s`), door/keystone.
- Mana pool mechanic (new; 1 of 3).
- Count motions `Nj`, `Nl`, `x`, command-mode entry `:`.

### Flagged assumptions

- **CHALLENGE C1 — Mana economy** (SPEC §6.4 TBD): Blueprint assumes mana is implemented
  as a per-room integer pool displayed in the status bar; `:s` deducts from it and fails
  with "No mana" if exhausted. Engine implementation required before this level is playable.
- **CHALLENGE C2 — Terrain immutability under `d`/`c`/`r`**: Engine must distinguish
  terrain tiles from rune-entities in `engine/operator.py`. Deletion operators must skip
  terrain. Needs explicit dispatch check.
- **Par solver**: `:s/F/I/g` is modelled as a 9-keystroke action converting a fire row to
  passable; BFS routes through after conversion. No macro state needed for L37.

### Self-check

- [x] Mechanics ≤ 3: 3 new (mana pool, F terrain, `:s` command). At the cap; correct.
- [x] Coherent family: `:s` + mana + F/I terrain are one substitution-magic family.
- [x] S1 terrain-infinity: fire rows are impassable, not merely expensive to cross.
- [x] Mana gate (Gate 2) eliminates bare `:s/F/I/` path with hard block, not budget.
- [x] Par corrected to 44 (v1 had 47 due to two off-by-one navigation errors).
- [x] Budget = 62; next-best without `:s/g` is infinite (terrain block) or budget-fatal.
- [x] Fire tile count reconciled: 46 per row (col 3–48 inclusive). v1 said "20"; corrected.
- [x] `dd` hatch explicitly closed; documented in engine requirement.

---

---

## Level 38 — The Hall of Echoes

**Commands taught:** `q{reg}…q` (record macro), `@{reg}` (replay macro),
`N@{reg}` (replay N times), `"{reg}` (named register select)

### New mechanics (2 of ≤3 allowed)

1. **Macro recording** — `q{a-z}` begins recording; `q` ends recording. The
   macro body is stored in register `{a-z}`.
2. **Macro replay** — `@{reg}` replays the recorded sequence once; `N@{reg}`
   replays it N times.

**Keystroke fact (critical):** `@a` = **2 keystrokes** (`@` + `a`). `N@a` =
`len(str(N)) + 2` keystrokes. The v1 blueprint counted `@a` as 3, which is wrong;
every forcing argument has been rederived with the correct count.

**Linkage:** `q`/`@` use the named-register namespace (`"a`–`"z`) established in the
yank/paste act. One coherent family: named registers + record/replay.

---

### Grid

```
Dimensions: 14 rows × 80 cols. Effectively a single navigable row (row 1).
5 identical combat chambers, each with 1 goblin and 1 ember rune, separated by doors.
```

**Chamber structure (row 1):**

Each chamber follows the pattern: `[floor][goblin][floor][ember rune][door]`.
The goblin blocks the path to the rune; the rune must be collected to open the door.

**Exact column layout (row 1):**

| Col | Content |
|---|---|
| 1 | `@` entry |
| 2–3 | floor |
| 4 | goblin `g` (chamber 1) |
| 5–6 | floor |
| 7 | ember rune `E` (chamber 1) |
| 8 | door `D` |
| 9 | goblin `g` (chamber 2) |
| 10–11 | floor |
| 12 | ember rune `E` |
| 13 | door `D` |
| 14 | goblin `g` (chamber 3) |
| 15–16 | floor |
| 17 | ember rune `E` |
| 18 | door `D` |
| 19 | goblin `g` (chamber 4) |
| 20–21 | floor |
| 22 | ember rune `E` |
| 23 | door `D` |
| 24 | goblin `g` (chamber 5) |
| 25–26 | floor |
| 27 | ember rune `E` |
| 28–76 | open floor (reward corridor) |
| 77 | `X` exit |

**S1 terrain-infinity for the sequence:** The door after each chamber only opens
when the ember rune is collected. The goblin physically occupies the cell between
the player and the rune, and must be killed before the rune can be reached. This
makes "skip the goblin" impossible (the cell is occupied) — the per-chamber sequence
(`advance → kill → advance → collect`) is terrain-forced, not budget-forced.

**`w` motion guarantee:** The chamber spacing (goblin at col 4, rune at col 7;
next goblin at col 9; etc.) is designed so that `w` — jumping to the next
non-floor entity — lands exactly on the goblin, then exactly on the rune.
This requires the engine's `w` motion to classify goblins and ember runes as
"word boundaries" (non-floor tile types). This is a **hard prerequisite** (see
CHALLENGE C3). The column positions above are the locked layout; the "schematic,
tune later" caveat in v1 is withdrawn. These exact positions must be used.

**`dw` semantics:** `dw` from a position adjacent to the goblin (cursor on the
floor cell immediately preceding the goblin) attacks through the motion range and
kills the goblin. However, if `w` lands the cursor ON the goblin's cell, then `dw`
from that position deletes forward, potentially consuming the goblin and the next
word boundary. To avoid ambiguity: the macro body uses `w` to move TO the goblin's
cell, then `dw` which deletes the goblin (the entity at the current cell is the
target of the operator) and leaves the cursor at the next word boundary (the rune).
This semantics must be verified in `engine/operator.py` — see CHALLENGE C4.

**Named register requirement:** A scroll at entry instructs the player to record
into register `a` (`qa`). The level validator checks that register `"a` contains
a non-empty macro before the first door crossing.

---

### Intended optimal solution

**Step 1 — Record the macro (chamber 1 executed live, 8 keystrokes total):**
```
qa      (start recording into register a: 2 keys)
w       (jump to goblin at col 4: 1 key)
dw      (kill goblin: 2 keys)
w       (advance to ember rune at col 7: 1 key)
x       (collect rune, door opens: 1 key)
q       (stop recording: 1 key)
```
Recording block = `q` `a` `w` `d` `w` `w` `x` `q` = **8 keystrokes**.
Macro body stored in `"a` = `w dw w x` = 5 keystrokes.
After this block, player is at col 7 (rune collected), door at col 8 is open.

**Step 2 — Replay for chambers 2–5 (4 remaining):**
```
4@a     (replay 4 times: '4' '@' 'a' = 3 keystrokes)
```
After replay, player is at col 27 (rune 5 collected), all 4 doors open.

**Step 3 — Navigate to exit:**
```
50l     (col 27 → col 77: '5' '0' 'l' = 3 keystrokes)
```
*(v1 said `49l`; corrected: 77 − 27 = 50 steps.)*

**Full keystroke string (canonical):** `qa w dw w x q 4@a 50l`

---

### Par + Budget

| | |
|---|---|
| **Par** | **14 keystrokes** |
| **Budget** | ceil(14 × 1.28) = **18 keystrokes** (multiplier 1.28; tighter than default 1.4 — see S2) |

**Why 1.28x (not 1.4x):**
With `@a` = 2 keystrokes (not 3), the single-replay fallback `@a @a @a @a` (no count
form) costs 8 (record) + 4×2 (replays) + 3 (exit) = **19 keystrokes**. At the default
1.4× budget of 20, that path would pass (19 ≤ 20), meaning `N@a` is not strictly forced
over individual `@a` calls. Setting budget = 18 (multiplier 1.28, ceil(14×1.28)=18)
makes single-replay cost 19 > 18 — strictly excluded. The S2 multiplier and its
rationale must be documented in the level metadata.

---

### Forcing argument

**Gate 1 — S1 terrain-infinity forces the macro sequence per chamber:**
Each goblin occupies the only path to its rune; each door requires the rune. The
per-chamber sequence (kill goblin, collect rune) is physically impossible to skip.
This forces the *content* of the macro body without relying on budget math.

**Gate 2 — Budget (18) excludes manual repetition:**
Manual approach (5 chambers, no macro): 5 × 5 keystrokes + 3 (exit) = 28.
28 > 18 (budget). Cannot complete without a macro.

**Gate 3 — Budget (18) excludes `@a` repeated individually (no count form):**
Single-replay: 8 (record+ch1) + 4×2 (four `@a`) + 3 (exit) = 19.
19 > 18 (budget). Cannot complete with individual `@a` repeats.

**Count-form `4@a` passes:** 8 (record+ch1) + 3 (`4@a`) + 3 (exit) = 14 ≤ 18.

**All three gates together:** terrain forces the sequence; budget excludes manual
repetition; tight budget additionally excludes the non-count replay form. Only
`qa [body] q` + `4@a` (par = 14) fits within budget 18.

---

### Primitives used

- Goblin wanderers (existing), ember rune clusters (existing), doors (existing).
- Named registers `"a`–`"z` (partially in `engine/registers.py`).
- `q`/`@` macro recording/replay (partially in `engine/macro.py`).

### Flagged assumptions

- **CHALLENGE C3 — `w` word-boundary on entities:** `w` must land exactly on goblin
  and rune positions for the macro body to work. Requires engine's `w` motion to treat
  goblin/rune tile types as word-start boundaries. The exact column layout above is
  locked (not schematic). Must be verified against `engine/motion.py` before build.
- **CHALLENGE C4 — `dw` kill semantics:** `dw` with cursor on an enemy entity must
  attack and kill that enemy, leaving the cursor at the next word boundary. Ambiguity:
  does `dw` delete from cursor through next word (potentially consuming two entities),
  or attack exactly the entity at cursor? Must be verified in `engine/operator.py` and
  documented as a canonical rule.
- **CHALLENGE C5 — Macro-aware par solver:** Standard Dijkstra cannot model macro
  state. Extended solver needs state = `(col, door_mask, register_a_contents)`. On
  `qa`, enter recording mode; moves append to register rather than advancing state;
  `q` closes recording; `@a` applies the stored sequence as a batch. Significant
  validator extension.

### Self-check

- [x] Mechanics ≤ 3: 2 new (record + replay; same family).
- [x] `@a` = 2 keystrokes (not 3) — all arithmetic rederived with correct count.
- [x] S1 terrain-infinity: goblin blocks path; door locks rune; sequence is physically forced.
- [x] S2 tight budget: multiplier 1.28 (budget=18) excludes both manual (28) and
  single-replay (19). Multiplier documented and justified.
- [x] `w` positioning locked to exact columns; no longer schematic.
- [x] `dw` semantics flagged as CHALLENGE C4 with resolution path.
- [x] Exit navigation corrected: `50l` (not `49l`).
- [x] CHALLENGE C5 (macro-aware par solver) flagged.

---

---

## Level 38.1 — The Warden Eternal (FINAL BOSS)

**Commands demanded:** `:s/{}/{}/g` (from L37), `q @ "` (from L38), plus all
prior mastery commands. This is the capstone encounter.

**Boss concept:** The Warden Eternal occupies a three-phase arena. Each phase
presents a different hazard pattern neutralised only by a specific Act VII mechanic.
Phase 1 requires `:s/F/I/g`. Phase 2 requires `N@a`. Phase 3 requires both — fire
rows make `:s` mandatory (terrain-infinity), and 9 warden copies make `N@a` mandatory
(tight budget). The combined requirement is achieved by layering both hazards, not by
embedding `:s` inside a macro body (which would require CHALLENGE C8 to be resolved
first).

---

### Phases table

| Phase | Name | Hazard | Required mechanic | Primary forcing |
|---|---|---|---|---|
| 1 | The Ashen Tide | 3 rows of fire (F) spawn per wave | `:s/F/I/g` | S1 terrain-infinity: fire rows impassable |
| 2 | The Echo Storm | 5 warden copies patrol identical corridors | `qa [body] q` + `4@a` | S1 sequence-force via doors; S2 budget=17 excludes single-replay |
| 3 | The Eternal Surge | 3 fire rows + 9 warden copies simultaneously | `:s/F/I/g` + `qa [body] q` + `8@a` | S1 terrain-infinity (fire) + S2 budget=62 (warden count) |

---

### Grid (multi-phase; same 20×60 arena, different overlays)

```
############################################################
#@..........................................................#   row 1  (entry)
#...........................................................#   rows 2-4 (phase 1 fire zone)
#...........................................................#
#...........................................................#
#...........................................................#
######################################D#####################   row 6  (phase door 1)
#...........................................................#   rows 7-11 (phase 2 warden zone)
#...........................................................#
#...........................................................#
#...........................................................#
#...........................................................#
######################################D#####################   row 12 (phase door 2)
#...........................................................#   rows 13-17 (phase 3 combined zone)
#...........................................................#
#...........................................................#
#...........................................................#
#...........................................................#
#...........W.......................................W.......#   row 18 (Warden Eternal)
#.................................................X.........#   row 19 (exit)
############################################################
```

- **@** entry: row 1, col 1
- **X** exit: row 19, col 49
- Phase door D1 (row 6, col 38) opens when Phase 1 condition is met.
- Phase door D2 (row 12, col 38) opens when Phase 2 condition is met.
- **W** Warden Eternal: row 18, two anchor positions (high-HP boss, 5 HP).
- Fire rows spawn in their respective zones as overlays (not part of base map).
- Warden copies spawn in their zone as overlays on phase entry.

---

### Phase 1 — The Ashen Tide (`:s/F/I/g`)

**Overlay:** On entering Phase 1, fire spawns across rows 2, 3, 4 (full-width F tiles,
impassable). The wave timer is defined in § Wave Timer Semantics below.

**Mana pool:** 12 at phase entry (resets each wave; enough for 4 × `:s/F/I/g` calls).

**S1 terrain-infinity:** Fire rows are impassable. The player cannot reach phase door D1
without clearing all three fire rows. `:s/F/I/g` is strictly required.

**Optimal sequence:**

| Step | Command | Keys | Cumulative |
|---|---|---|---|
| Clear fire row 2 (player is on row 1) | `:s/F/I/g<CR>` | 9 | 9 |
| Step into cleared row 2 | `j` | 1 | 10 |
| Clear fire row 3 | `:s/F/I/g<CR>` | 9 | 19 |
| Step to row 3 | `j` | 1 | 20 |
| Clear fire row 4 | `:s/F/I/g<CR>` | 9 | 29 |
| Step to row 4 | `j` | 1 | 30 |
| Strike Warden (row 5) | `dw` | 2 | 32 |
| Advance to door (row 6) | `j` | 1 | 33 |
| Open phase door | `x` | 1 | 34 |

**Phase 1 par:** 34 keystrokes.
**Phase 1 budget:** ceil(34 × 1.4) = **48 keystrokes** (1.4× sufficient; terrain-infinity
does the primary forcing).

Next-best without `:s`: fire rows are physically impassable. Cost = infinite.
`:s`-only (no `g` flag): 46 tiles × 1 mana each, pool = 12. Exhausts after 12 tiles.
Row 2 is still 34 tiles away from cleared. Hard block. `g` flag is mandatory.

**Mana note:** 3 × `:s/F/I/g` = 9 mana used. 3 mana remaining. Mana is not the
binding constraint in Phase 1 — terrain-infinity is. Mana pool serves as a
signal to the player that `:s` costs a resource and `g` is the efficient form.

---

### Phase 2 — The Echo Storm (`q @ "`)

**Overlay:** 5 identical Warden copies spawn at rows 7–11, one per row. Each copy
patrols its row. The compound move per copy:
- `w` — advance to warden copy
- `dw` — strike and kill the copy
- `j` — sidestep down to next row (avoid counter-attack, advance toward door)

Macro body: `w dw j` = 1+2+1 = **4 keystrokes**.
Recording block (first copy executed live): `qa` (2) + body (4 live) + `q` (1) = **7 keystrokes**.
Replay for 4 remaining copies: `4@a` = `4`+`@`+`a` = **3 keystrokes** (`@a` = 2 ks, not 3).
Navigation to door + open: `3j` (2) + `x` (1) = **3 keystrokes**.

**Phase 2 par:** 7 + 3 + 3 = **13 keystrokes**.
**Phase 2 budget:** ceil(13 × 1.30) = **17 keystrokes** (S2 multiplier; see below).

**Forcing argument:**

| Approach | Cost | vs budget 17 |
|---|---|---|
| Manual (5 copies × 4 ks + nav 3) | 23 | > 17 — EXCLUDED |
| Single-replay (4 × `@a` separately: 7+4×2+3) | 19 | > 17 — EXCLUDED |
| Count-form `4@a` (7+3+3) | 13 | ≤ 17 — PASSES |

**Why 1.30× (not 1.4×):** `@a` = 2 keystrokes. At 1.4× budget = ceil(13×1.4) = 19,
single-replay costs 19 = budget (ties, passes). S2 tighter multiplier 1.30 gives
budget=17, strictly excluding single-replay (19 > 17). Multiplier documented here.

S1 terrain-sequence via doors also forces the per-copy action sequence (must kill copy
to advance to the next row and ultimately reach door D2).

---

### Phase 3 — The Eternal Surge (combined mastery)

**Overlay:** Fire rows spawn across rows 13, 14, 15 (impassable). 9 Warden copies
spawn in a grid beyond the fire rows (rows 13–17, spread across the zone). The
Warden Eternal waits at row 18.

**Two-hazard design rationale (why NOT `:s` inside macro body):**
Embedding `:s/F/I/g<CR>` inside the macro body creates a complex engine dependency
(CHALLENGE C8: command-mode replay via `synth_key` inside macro). Instead, Phase 3
is designed so the player clears fire first (terrain-infinity forces `:s`), then
records and replays a macro for the warden copies (tight budget forces `N@a`).
Both techniques are strictly required without the `:s`-in-macro complexity.

**Optimal sequence:**

| Step | Command | Keys | Cumulative |
|---|---|---|---|
| Player enters phase 3 zone at row 12 (door just opened) | — | — | — |
| Clear fire row 13 (player on row 12, `:s` operates on current row after `j`) | `j` + `:s/F/I/g<CR>` | 1+9 | 10 |
| Step through row 13 | `j` | 1 | 11 |
| Clear fire row 14 | `:s/F/I/g<CR>` | 9 | 20 |
| Step through row 14 | `j` | 1 | 21 |
| Clear fire row 15 | `:s/F/I/g<CR>` | 9 | 30 |
| Step to row 15 | `j` | 1 | 31 |
| Navigate to warden copy 1 (row 16, already adjacent after fire clear) | — (already in position) | — | 31 |
| Record macro: `qa` | `qa` | 2 | 33 |
| Body (live on copy 1): `w dw j` | `w dw j` | 4 | 37 |
| Close recording: `q` | `q` | 1 | 38 |
| Replay for 8 remaining copies: `8@a` | `8@a` | 3 | 41 |
| Strike Warden Eternal at row 18: `4j dw` | `4j` + `dw` | 2+2 | 45 |
| Collect exit key + reach X: `x` + `48l` | `x` + `48l` | 1+3 | 49 |
| Advance to exit row 19 | `j` | 1 | 50 |

*(Row navigation is approximate; exact geometry depends on warden copy placement
in the 13–17 zone. The par of 50 is the target; exact tuning during generation
may shift it by ±2. Budget at 1.24× is set to 62 = ceil(50×1.24), giving enough
room for minor geometry variation.)*

**Phase 3 par:** **50 keystrokes** (corrected from v1's ~35, which undercounted by ~15).
**Phase 3 budget:** ceil(50 × 1.24) = **62 keystrokes** (S2 multiplier; see below).

**Forcing argument:**

| Approach | Cost | vs budget 62 |
|---|---|---|
| Macro-only (no `:s`): fire rows impassable | INFINITE | — hard block |
| `:s`-only (manual all 9 wardens): 30+2+9×4+4+4 | 76 | > 62 — EXCLUDED |
| Single-replay (8 × `@a` sep): 30+2+7+8×2+4+4 | 63 | > 62 — EXCLUDED |
| Combined `:s` + count-form `8@a`: 50 | 50 | ≤ 62 — PASSES |

**Why 1.24× (not 1.4×):** At 1.4×, budget = ceil(50×1.4) = 70. Single-replay
costs 63 ≤ 70 (passes; `N@a` not forced). S2 tighter multiplier 1.24 gives
budget = 62, strictly excluding single-replay (63 > 62). Multiplier documented.

---

### Wave Timer Semantics (Phase 1 and Phase 3)

**Definition:** The wave timer advances by 1 tick on each **normal-mode keystroke**
(motion keys, operator keys, `x`, `dw`, etc.). Keystrokes typed inside command-mode
(after `:` until `<CR>`) do NOT advance the wave timer. The full `:s/F/I/g<CR>`
sequence counts as **0 timer ticks** while being typed; the timer advances by 1 tick
when the command is confirmed with `<CR>` (i.e., command-mode entry counts as 1
normal-mode event on completion).

**Rationale:** If each character inside `:s/F/I/g<CR>` advanced the timer (9 ticks
for 9 keystrokes), a 6-keystroke wave period would fire mid-command, creating
undefined behavior (fire respawning while the player is typing the command that
clears it). Treating command-mode as atomic (1 timer tick on `<CR>`) eliminates this
ambiguity. This is a **hard engine requirement** — see CHALLENGE C6.

**Phase 1 timer calibration:**
Optimal Phase 1 normal-mode keystrokes: `j, j, j, d, w, j, x` = 7 ticks
(`:s/F/I/g<CR>` × 3 = 3 ticks; total = 7+3 = 10 ticks). Set wave period = 12
ticks to ensure no respawn during the optimal 10-tick run. A suboptimal player
(taking ≥12 normal-mode actions) will face a wave respawn, increasing difficulty.

**Phase 3 timer calibration:** Similar analysis; wave period = 15 ticks.

---

### Full boss par + budget summary

| Phase | Par | Budget | Multiplier | Primary forcing |
|---|---|---|---|---|
| Phase 1 — Ashen Tide | 34 | 48 | 1.40 | S1 terrain-infinity (fire impassable) |
| Phase 2 — Echo Storm | 13 | 17 | 1.30 | S1 sequence + S2 tight budget excludes single-replay |
| Phase 3 — Eternal Surge | 50 | 62 | 1.24 | S1 fire-infinity + S2 excludes `:s`-only and single-replay |
| **Boss total** | **97** | **127** | — | All Act VII techniques required |

*(v1 total was 82/116. Corrected to 97/127 due to: Phase 2 overhead +1 (7 not 6);
Phase 3 par +15 (50 not 35) from correct counting of all steps.)*

---

### Placements (full arena)

| Thing | Location | Notes |
|---|---|---|
| Entry `@` | row 1, col 1 | — |
| Phase door 1 | row 6, col 38 | Opens when all P1 fire cleared + Warden struck |
| Phase door 2 | row 12, col 38 | Opens when all 5 P2 copies killed |
| Fire rows (P1) | rows 2, 3, 4 (full width) | Wave-spawned; impassable terrain |
| Warden copies × 5 | rows 7–11, col ~30 | Phase 2; each patrols its row |
| Fire rows (P3) | rows 13, 14, 15 (full width) | Phase 3 overlay; impassable |
| Warden copies × 9 | rows 13–17, spread | Phase 3; pattern TBD at generation |
| Warden Eternal | row 18, col 30 | High HP (5); boss entity |
| Exit `X` | row 19, col 49 | Unlocked after Warden Eternal struck |
| Mana refill orb | row 6, col 1 | Restores 12 mana on entry to Phase 2 zone |
| Mana refill orb | row 12, col 1 | Restores 12 mana on entry to Phase 3 zone |
| Hint scroll | row 1, col 10 | "Record your spells. Replay your will." |

---

### Flagged assumptions / CHALLENGES

- **CHALLENGE C6 — Wave timer semantics (engine):** Timer must be implemented
  as a normal-mode-keystroke counter, not a raw keystroke counter. Command-mode
  input (after `:`) must not advance the timer until `<CR>` confirmation. Requires
  a per-room tick hook in the game loop and a mode-aware counter. New engine feature.
- **CHALLENGE C7 — Multi-phase boss state machine:** Phase door triggers (open on
  condition), HP tracking across `dw` strikes, and overlay spawning per phase require
  a boss state machine in `content/bosses.py` or a general `on_condition` system in
  `engine/world.py`. New engine feature.
- **CHALLENGE C8 — `:s` inside macro body (deferred):** Phase 3 is redesigned to
  NOT require `:s` inside a macro body, avoiding this challenge. If a future level
  requires it, `engine/macro.py`'s `record_char` must capture `:`, `/`, printable
  chars, and `<CR>`, and command-mode dispatch must replay correctly via `synth_key`.
  Flag as a deferred hard prerequisite.
- **CHALLENGE C9 — Macro-aware par solver (boss):** Phase 3 par computation requires
  the solver to model the macro recording + replay sequence without `:s` inside it
  (simpler than C8 requires, but still needs the recording-state extension from C5).

### Self-check

- [x] ≤ 3 new mechanics: `:s` (L37), macros (L38); boss reuses both. No new mechanic.
- [x] Coherent family: all phases demand Act VII power-automation techniques.
- [x] Phase 1: S1 terrain-infinity forces `:s/F/I/g`. Mana blocks bare `:s/F/I/`.
- [x] Phase 2: S1 sequence-force + S2 budget=17 (1.30×) forces `N@a` over single `@a`.
- [x] Phase 3: S1 forces `:s` (fire impassable); S2 budget=62 (1.24×) forces `N@a`.
  Combined par=50 ≤ 62; `:s`-only=76 > 62; single-replay=63 > 62.
- [x] Phase 3 does NOT embed `:s` inside macro body — avoids C8.
- [x] Wave timer semantics defined: fires on normal-mode ks only; command-mode = 0 ticks.
- [x] Boss par corrected: 97 (was 82). Budget corrected: 127 (was 116).
- [x] Phase 2 overhead corrected: 7 keys (was 6). Phase 2 par = 13 (was 13 coincidentally,
  but budget corrected from 19 to 17).
- [x] Phase 3 par corrected: 50 (was ~35 — dramatically undercounted in v1).
- [x] All CHALLENGES (C1–C9) listed with resolution paths.

---

---

## Appendix — Summary Table

| Level | Commands | Par | Budget | Multiplier | Forceable? | Key Risks / Challenges |
|---|---|---|---|---|---|---|
| 37 — Spellwright's Forge | `:s/F/I/` `:s/F/I/g` | 44 | 62 | 1.40 | Yes — S1 terrain-infinity (impassable fire) + mana hard-block on bare `:s` | C1 mana economy (SPEC §6.4 TBD); C2 terrain immutability under `d`/`c`/`r` |
| 38 — Hall of Echoes | `qa…q` `@a` `N@a` | 14 | 18 | 1.28 | Yes — S1 goblin/door sequence + S2 tight budget excludes both manual and single-replay | C3 `w` word-boundary verification (layout locked); C4 `dw` kill semantics; C5 macro-aware par solver |
| 38.1 P1 — Ashen Tide | `:s/F/I/g` | 34 | 48 | 1.40 | Yes — S1 terrain-infinity (fire impassable) | C6 wave timer (normal-mode only); C7 multi-phase state machine |
| 38.1 P2 — Echo Storm | `qa…q` `N@a` | 13 | 17 | 1.30 | Yes — S1 sequence + S2 excludes single-replay | C6 wave timer; C7 state machine |
| 38.1 P3 — Eternal Surge | `:s/F/I/g` + `qa…q` + `N@a` | 50 | 62 | 1.24 | Yes — S1 fire-infinity forces `:s`; S2 excludes `:s`-only and single-replay | C8 deferred (`:s` in macro not used); C9 macro-aware solver for boss |
| **Boss total** | All Act VII | **97** | **127** | — | Yes | All challenges above |

---

## CHALLENGES requiring human decision

See dedicated section at end of document for full list. Summary:

| ID | Challenge | Affects | Decision needed |
|---|---|---|---|
| C1 | Mana economy (SPEC §6.4) — per-room pool, deduction, display | L37, L38.1 | Engine implementation spec |
| C2 | Terrain immutability under `d`/`c`/`r` operators | L37, L38.1 | `engine/operator.py` dispatch rule |
| C3 | `w` word-boundary on goblin/rune tile types | L38, L38.1 | `engine/motion.py` tile classification |
| C4 | `dw` semantics: attack entity at cursor vs. delete through range | L38, L38.1 | `engine/operator.py` combat rule |
| C5 | Macro-aware par solver (recording-state extended Dijkstra) | L38, L38.1 | Validator architecture decision |
| C6 | Wave timer: normal-mode-only ticks; command-mode = 0 ticks during entry | L38.1 | Engine tick hook design |
| C7 | Multi-phase boss state machine (phase doors, HP tracking, overlays) | L38.1 | `content/bosses.py` architecture |
| C8 | `:s` inside macro body via `synth_key` (deferred; not used in current design) | Deferred | Defer until needed |
| C9 | Macro-aware par solver for boss Phase 3 (extension of C5) | L38.1 | Covered by C5 decision |
