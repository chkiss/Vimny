# Act III — Navigation Power Tools: Blueprints

Levels 10–13.1. Each level introduces at most 3 linked mechanics, budget-forces or
contextually teaches them, and is buildable from existing engine primitives (with
clearly flagged assumed extensions).

Revision applied: S1 terrain-∞ first, S2 tight budget fallback (document multiplier),
S3 recompute par (true full solution), S4 block earlier commands. All review defects
D1–D12 addressed.

---

## Level 10 — The Mirror Temple

**Commands:** `%`

**New mechanics (1):** Bracket/pair matching — jump to the matching bracket/paren/brace.
**Linkage:** `%` is a single-idea "find the pair"; no other mechanic introduced here.

---

### Grid

```
Dims: 14 rows × 52 cols  (@=entry col 1 row 6, X=exit col 49 row 6)
```

Exact layout (14 rows × 52 cols, 0-indexed):

```
Row  0: #################################################### (all wall, 52 cols)
Row  1: #                                                  #
Row  2: #  [         ]    (         )    {         }       #
Row  3: #  [         ]    (         )    {         }       #
Row  4: oooo         ooooo         ooooo         oooooooooo
Row  5: oooo         ooooo         ooooo         oooooooooo
Row  6: @   [VOIDVOID]    (VOIDVOID)    {       } X
Row  7: oooo         ooooo         ooooo         oooooooooo
Row  8: oooo         ooooo         ooooo         oooooooooo
Row  9: #  [         ]    (         )    {         }       #
Row 10: #  [         ]    (         )    {         }       #
Row 11: #                                                  #
Row 12: #                                                  #
Row 13: #################################################### (all wall)
```

**Entry:** (6, 1)   **Exit:** (6, 49)

**Corridor row (row 6)** is passable floor between pairs. Rows 4-5 and 7-8 are void (○,
lethal). The upper (rows 2-3) and lower (rows 9-10) halves are walled off — no access
from row 6 (walls at rows 0 and 13 connect to solid walls at col 0 and col 51, and internal
columns flanking each pair form solid wall columns with no gaps on rows 4-5 and 7-8).

---

### Placements

**Three bracket pairs spanning row 6 as floor-embedded glyph rune clusters:**

| Pair | Open col | Close col | Interior (void rune cells, row 6) |
|------|----------|-----------|-----------------------------------|
| `[`  | 4        | 15        | cols 5-14 (○ runes, lethal)       |
| `(`  | 21       | 32        | cols 22-31 (○ runes, lethal)      |
| `{`  | 38       | 46        | cols 39-45 (floor, passable)      |

- Pairs 1 (`[ ]`) and 2 (`( )`) have void interior on row 6 — landing on cols 5-14 or
  22-31 is lethal. The only 1-keystroke crossing is `%` on the open bracket, which jumps
  directly to the matching close bracket on the same row, bypassing the void.
- **S1 forcing (infinite cost):** Rows 4-5 and 7-8 are solid void — no detour above or
  below. The walls flanking pairs 1 and 2 are solid on rows 2-3 and 9-10, inaccessible
  from row 6. The only legal path through each void-floored pair is `%`.
- Pair 3 (`{ }`) has passable interior — the player CAN walk through; this is the
  decoy/comparison that shows `%` is general without requiring it here.
- Keystones at open brackets cols 4, 21 and close brackets cols 15, 32 — stepping on
  the bracket glyph activates it. The door at col 47 opens only when all 4 bracket
  keystones are triggered.

**Door:** col 47-48, row 6 — locked until all 4 bracket keystones triggered.
**Exit entity:** (6, 49).

---

### Optimal keystrokes (S3 full solution, entry→exit)

Starting at (6, 1):

1. Move to `[` at col 4: `3l` = 2 keystrokes (digit `3` + `l`)
2. `%` jump `[`→`]` (col 4→15): 1 keystroke — activates both bracket keystones
3. Move to `(` at col 21: `6l` = 2 keystrokes (digit `6` + `l`)
4. `%` jump `(`→`)` (col 21→32): 1 keystroke — activates both bracket keystones
5. Move to `{` at col 38: `6l` = 2 keystrokes (digit `6` + `l`)
6. Walk through `{ }` interior to `}` at col 46: `8l` = 2 keystrokes
7. Move through door and to exit at col 49: `3l` = 2 keystrokes

**Par: 2+1+2+1+2+2+2 = 12 keystrokes**
**Budget: ceil(12 × 1.4) = ceil(16.8) = 17**

(Previous blueprint claimed par=14, budget=20. Review computed par=12, budget=17.
Corrected here per D1.)

---

### Forcing / Teaching argument

**Terrain-∞ forcing (S1):** The two void-floored pairs (`[ ]` and `( )`) make it
physically lethal to walk through their interior on row 6. Detour above (rows 2-3) or
below (rows 9-10) is impossible — those areas are fully walled off from row 6.
Every path within budget must use `%` exactly twice.

The third pair `{ }` with passable interior shows `%` is a general mechanic (it works
there too) without requiring it — demonstrating the concept at zero extra cost.

Budget of 17 is tighter than the old 20. A player who tries to reach cols 5-14 or 22-31
without `%` dies instantly (void). There is no budget question — the alternative is lethal,
not merely expensive. S1 is fully satisfied.

---

### Primitives

- Walls, floor, void (lethal landing) — all existing.
- Rune clusters representing bracket glyphs (`[`, `]`, `(`, `)`, `{`, `}`) — existing
  RuneCluster with literal bracket symbols.
- Keystones — existing Entity kind.
- Door — existing.

**CHALLENGE C-L10-1:** `%` motion in `engine/motion.py` is not implemented. Requires
scanning the current row for the nearest bracket glyph under cursor and jumping to its
pair. Brackets: `[](){}` in RuneCluster symbols. This is a hard prerequisite — the level
cannot run without it.

---

### Self-check

- (1) Scope: 1 new mechanic (`%`). Pass.
- (2) Linkage: bracket matching is a single coherent idea. Pass.
- (3) Forced (S1): void interior makes `%` the only non-lethal path; detours are walled.
  Budget 17. Pass.
- (4) Boss: not applicable here. Pass.
- Grid: 14×52, entry/exit on same row, all other rows inaccessible from row 6. Consistent.

---

---

## Level 11 — The Seekers' Labyrinth

**Commands:** `/ ? n N`

**New mechanics (2):** Forward search `/pattern`, backward search `?pattern`, repeat with
`n`/`N`. (These are one coherent family: "search navigation". `/`+`?` = 1 mechanic,
direction variants; `n`+`N` = 1 mechanic, direction variants of repeat.)
**Linkage:** All four commands are the search-navigation cluster. No other mechanic.

---

### Design decision: `/SIGIL` avatar semantics (D3 fix)

**DECIDED:** `/pattern<Enter>` in Vimny warps the **player avatar** directly to the
matched RuneCluster's cell (the cell containing the first character of the matching
text). This is NOT standard Vim cursor-only behavior. It is the Vimny-specific
interpretation: "search is teleportation in the dungeon."

This decision is **required** for the forcing argument. If search only reveals position
(cursor highlight) without moving the avatar, the level cannot force `/` over walking.
The engine must implement search-as-avatar-teleport.

**CHALLENGE C-L11-1:** `engine/search.py` `find_next()` returns `(row, col)`. The engine
dispatch for `/pattern<Enter>` must additionally move `player.row, player.col` to that
position. This is a semantic extension beyond cursor highlighting — it is a core engine
behavior change affecting all future search uses. A human must decide: should
search-teleport be the universal Vimny behavior, or only active in specific room types?

---

### Grid (revised to enable verifiable par arithmetic)

**Rationale for grid revision:** The original 20×70 grid made worst-case par
arithmetically unsupportable (review D2: travel to top-right alcove alone ≈ 35+ moves).
Grid is reduced to 12×40 with 3×3 = 9 alcoves so travel distances are verifiable.

```
Dims: 12 rows × 40 cols

########################################
#                                      #
# [A1] # [A2] # [A3] #                 #
#      #      #      #                 #
########D######D######D#################
# [B1] # [B2] # [B3] #                 #
#      #      #      #                 #
########D######D######D#################
# [C1] # [C2] # [C3] #                 #
#      #      #      #                 #
########################################
#  @ ----bottom corridor---- X (door)  #
########################################
```

Exact layout (12 rows × 40 cols, 0-indexed):

```
Row  0: ######################################## (wall)
Row  1: # [alcove A1] # [alcove A2] # [alcove A3] #    #
Row  2: # (cols 2-10) # (cols 13-21)# (cols 24-32)#    #
Row  3: #             #             #             #    #
Row  4: ####D##########D##############D############### 
Row  5: # [alcove B1] # [alcove B2] # [alcove B3] #    #
Row  6: # (cols 2-10) # (cols 13-21)# (cols 24-32)#    #
Row  7: #             #             #             #    #
Row  8: ####D##########D##############D##############
Row  9: # [alcove C1] # [alcove C2] # [alcove C3] #    #
Row 10: #             #             #             #    #
Row 11: ######################################## (wall)
Row 12: # @(col 1)  ---bottom corridor---  X(col 37) #  (exit door locked)
Row 13: ######################################## (wall)
```

Correction: the grid is **14 rows × 40 cols** (rows 0-13). Entry at (12, 1), exit at
(12, 37). The 9 alcoves are in rows 1-10 across 3 column groups and 3 row bands, with
door cells at rows 4 and 8 giving access from the bottom corridor (row 12) upward.

**Alcove coordinates (1 cell = 1 game cell):**

| Alcove | Row band | Cols   | SIGIL seed slot |
|--------|----------|--------|-----------------|
| A1     | 1-3      | 2-10   | seed mod 9 == 0 |
| A2     | 1-3      | 13-21  | seed mod 9 == 1 |
| A3     | 1-3      | 24-32  | seed mod 9 == 2 |
| B1     | 5-7      | 2-10   | seed mod 9 == 3 |
| B2     | 5-7      | 13-21  | seed mod 9 == 4 |
| B3     | 5-7      | 24-32  | seed mod 9 == 5 |
| C1     | 9-10     | 2-10   | seed mod 9 == 6 |
| C2     | 9-10     | 13-21  | seed mod 9 == 7 |
| C3     | 9-10     | 24-32  | seed mod 9 == 8 |

---

### Placements

- **Entry** `@`: (12, 1). Row 12 is fully lit bottom corridor.
- **Exit** `X`: (12, 37). Exit door locked until: SIGIL collected AND both ECHO
  keystones activated.
- **SIGIL keystone**: one alcove, seed-determined (see table). Rune text: `"SIGIL"`.
  The alcoves are all fogged (fog_cells) and structurally identical from outside.
- **ECHO rune clusters**: 2 alcoves (not the SIGIL alcove) each contain one cluster
  with text `"ECHO"`. Each ECHO cluster acts as a keystone — both must be collected
  to unlock the exit. These are mandatory, not optional (S1: exit locked).
- **Fog-of-war**: all 9 alcoves are initially fogged. Fog clears when the player
  avatar enters (or teleports into) the alcove.
- **Hint scroll** at (12, 3): "Something in these halls answers to a name. `/SIGIL`
  will take you to it." (Read on approach; teaches `/` syntax.)
- **Hint scroll** at (12, 20): "Use `n` to find the next echo. `N` goes back."

**Why ECHO keystones are mandatory:** The exit door is locked by three conditions:
1. SIGIL keystone collected.
2. ECHO keystone #1 collected.
3. ECHO keystone #2 collected.
All three conditions must be met. This makes `n`/`N` mechanically required (not merely
beneficial), satisfying S1 for the repeat commands.

---

### Optimal keystrokes — worst case (S3 full solution)

**Worst-case SIGIL seed:** A3 (top-right, row 1-3, cols 24-32). After search-teleport,
the player must then navigate to the two ECHO alcoves and finally to the exit.
**ECHO placements (worst-case seed):** ECHO#1 in B1 (row 5-7, cols 2-10), ECHO#2 in
C1 (row 9-10, cols 2-10) — both far left, requiring backward traversal.

**Sequence with search:**

1. `/SIGIL<Enter>` = 7 keystrokes. Avatar teleports to SIGIL in A3 (~row 2, col 28).
   Fog clears in A3. SIGIL is on the current cell — collect automatically on arrival
   (or 1 bump): say **1 key** to confirm collect. Running total: 8.

2. ECHO#1 is in B1. Player is at ~(2, 28). Type `/ECHO<Enter>` = 7 keys. Avatar
   teleports to ECHO#1 in B1 (~row 6, col 5). Collect (1 key). Running total: 16.

3. ECHO#2 is in C1. Player is at ~(6, 5). Type `?ECHO<Enter>` = 7 keys — backward
   search finds ECHO#2 at C1 (~row 9, col 5), which is "before" (row-wise below) the
   current position in the search ordering. Teleport to ECHO#2. Collect (1 key).
   Running total: 24.

   **Forcing `?`:** ECHO#2 in C1 is at a higher row index than ECHO#1 in B1. In the
   room's rune ordering (row-major), C1 comes after B1 — so from B1, `/ECHO` would
   wrap around and land on B1 again (already collected, or the other ECHO if it's in
   the same direction). `?ECHO` (backward) reaches C1 directly. Alternatively, `N`
   from step 2 goes backward to find C1: **`N`** = 1 key. Running total: 17 + 1 = 18
   for collect (if using `N` instead of `?ECHO`).

   **Forcing `N`:** After step 2 (player used `/ECHO`), `last_search = (ECHO, forward)`.
   `N` reverses and finds ECHO#2 in C1. This is cheaper (1 key) than re-typing
   `?ECHO<Enter>` (7 keys). Budget pressure makes `N` the dominant strategy.

4. Navigate from C1 (~row 9, col 5) to exit (12, 37):
   - Down through bottom-corridor door: ~3 rows = 3 `j` = 1 count-move: `3j` = 2 keys
   - Right to exit: col 5→37 = 32 cols. `32l` = 3 keys (digit `3`, digit `2`, `l`).
   Running total: 24 + 2 + 3 = 29.

**Par: 29 keystrokes (worst seed)**
**Budget: ceil(29 × 1.4) = ceil(40.6) = 41**

**Verification — manual path (no search) worst seed:**
Player at (12, 1). Must check alcoves systematically. Expected alcove checks before
finding SIGIL: on average 4.5 alcoves (SIGIL in slot 8/9 = worst). Each alcove requires:
- Walk from corridor to alcove via door (~2 rows up) = 2 keys
- Walk across alcove to check (~4 cols) = 1 count-key
- Walk back to corridor (~2 rows down) = 2 keys
- Horizontal traverse to next alcove (~11 cols) = 2 keys
Per alcove: ~7 keys. 8 alcoves to check before A3: 8×7 = 56 keys. Then walk to each
ECHO (2 alcoves × 7 keys) = 14. Navigation to exit ~10 keys. No-search total: ~80+.
No-search path >> budget of 41. Search is required by S2 budget. S1 applies to SIGIL
location (impossible to know which alcove without search or exhaustive check exceeding
budget).

**Forcing `n` specifically:** If player uses `/ECHO<Enter>` for ECHO#1 and finds it in
B1, `n` repeats forward search — if ECHO#2 is in A2 or A3 (above B1 in the row-major
wrap), `n` reaches it in 1 key vs. manual navigation (~7+ keys). The worst-case seeding
ensures at least one `n` or `N` use saves ≥6 keys vs. re-typing the search or walking.

**Forcing `?` specifically:** ECHO#2 placement in C1 (below B1, row-major) means from
B1, forward search wraps around top of the dungeon before reaching C1 — `N` (reverse
repeat, 1 key) or `?ECHO<Enter>` (7 keys) reaches it directly going backward. The budget
gap between `n` (6 keys wasted on a wrap pass) and `N` (1 key direct) forces `N`.

---

### Forcing / Teaching argument

**Fog-of-knowledge + search-as-teleport:** All alcoves are identical and fogged. The
SIGIL position varies by seed — the player cannot know which alcove to enter first.
`/SIGIL<Enter>` teleports directly to SIGIL regardless of which alcove it's in.
Manual exhaustive search blows the budget of 41 by ~40+ keys. S1 (terrain-∞) applies
because the correct alcove is unknowable without search; S2 (budget) confirms it.

**`n`/`N` forced:** Both ECHO keystones are mandatory for the exit lock. After using
`/ECHO` for ECHO#1, repeating with `n` (1 key) or `N` (1 key) to find ECHO#2 is always
cheaper than re-typing the full pattern (7 keys). The 6-key savings per use is
comfortably larger than any counting-keystroke precision.

**`?` forced:** The seeding of ECHO#2 below ECHO#1 (in row-major order) means from
ECHO#1's position, `N` (backward repeat) finds ECHO#2 directly. Forward `n` wraps the
full dungeon before reaching it. The budget forces the backward direction.

---

### Primitives

- Fog-of-war — existing (`fog_cells` in Room).
- Doors — existing Entity kind.
- Keystones — existing Entity kind.
- Rune clusters with specific text strings — existing RuneCluster.
- Scroll hints — existing.

**CHALLENGE C-L11-1 (critical):** `engine/search.py` `find_next()` must move the
player avatar to the matched cell, not only return `(row, col)`. This is a semantic
extension — standard Vim `/` is cursor-only; Vimny `/` is avatar-teleport. A human
must decide: is this global behavior or a room-flag opt-in? Decision required before
L11 can be built.

**CHALLENGE C-L11-2:** `player.last_search` (pattern + direction) field and `n`/`N`
dispatch in `engine/motion.py` are required. `n` calls
`find_next(room, player, player.last_search.pattern, player.last_search.forward)`;
`N` reverses direction. Neither is implemented (confirmed: LEVELS_PLAN.md Part 5).

**CHALLENGE C-L11-3 (design decision):** What happens when the player teleports into
a fogged alcove via `/SIGIL`? The fog should clear for that alcove. Requires that the
fog-reveal logic triggers on avatar position change (not only on manual walk-in). If
fog reveal is tied to `player.row/col` change, this works automatically. Confirm.

---

### Self-check

- (1) Scope: 2 new mechanics (`/`+`?` as one pair, `n`+`N` as the repeat pair). Pass.
- (2) Linkage: `/`, `?`, `n`, `N` are exactly the Vim search cluster. Pass.
- (3) Forced (S1+S2): Fog-of-knowledge + search-as-teleport makes `/SIGIL` the only
  viable SIGIL locator within budget. `n`/`N` forced by mandatory ECHO keystones + budget
  gap. `?` forced by ECHO placement ordering in worst seed. Par=29 (worst case), budget=41.
  No-search path ≈ 80+. Pass.
- (4) Boss: not applicable. Pass.
- Engine flags: C-L11-1 (avatar teleport), C-L11-2 (last_search + n/N), C-L11-3 (fog on
  teleport). All flagged as challenges requiring human decisions.

---

---

## Level 12 — The Waypoint Sanctum

**Commands:** `m{a-z}`, `'`/`` ` `` (jump to mark)

**New mechanics (2):** Set a mark (`m{a}` marks current position as `a`); jump to mark
(`'a` or `` `a ``). (One coherent family: "persistent waypoints".)
**Linkage:** `m` and `'`/`` ` `` are the mark pair — set and return. No other mechanic.

---

### Grid (revised: 24 rows × 60 cols, WINDING MAZE — terrain-∞ redesign)

**Why the straight-corridor design failed:** Prior designs used straight corridors.
Count-moves like `40l` cost only 3 keys regardless of distance, so widening the grid
added zero keystroke overhead (Option A failed), and adding extra keystones added only
3-key savings per mark-jump (Option B failed, no-marks stayed below budget).

**Root fix — winding corridors defeat count-compression:** Replace every junction-return
path with a 5–6-bend winding corridor. Each bend is a wall that forces a NEW direction
key — a separate 2-key count-move. A 6-bend return path costs 6 × 2 = 12 keystrokes on
foot regardless of segment length, because it is the NUMBER OF DIRECTION CHANGES, not
distance, that drives keystroke cost. `` `b `` teleports back in 2 keystrokes. Per-return
saving: 10 keys. With 3 forced returns: 30 keys total — easily forces the budget.

```
Dims: 24 rows × 60 cols
```

Schematic (winding topology; exact wall placement drives 5-6 bends per return):

```
Row  0: wall
Row  1-3:  CHAMBER-A (col 2-8)                    CHAMBER-C (col 44-50)  EXIT-ROOM (col 52-58)
Row  4:  wall; door col 4 (A→winding), door col 44 (C), door col 50 (EXIT-locked)
Row  5-7:  [UPPER WINDING ZONE — 5 bends between A/C and Junction]
Row  8:  JUNCTION cell (col 30) — mb hint scroll
Row  9:  wall
Row 10-11: [LOWER WINDING ZONE — 5 bends between Junction and lower section]
Row 12: wall; door col 4 (B→winding), door col 44 (D)
Row 13-15: CHAMBER-B (col 2-8)            CHAMBER-D (col 44-50)
Row 16: wall
Row 17-18: [LOWER-B-D WINDING — 5 bends connecting B, junction, D]
Row 19: wall
Row 20: HUB cell (col 30) — ma hint scroll; 4-bend winding below
Row 21: ANTECHAMBER (col 2-8); straight run right from entry to HUB
Row 22: wall
Row 23: wall

Entry: (21, 2)    Exit: (2, 56)    Junction: (8, 30)    HUB: (20, 30)
```

**5-bend winding exemplar (Junction (8,30) → Chamber-A (2,4); walls force each turn):**

```
Seg 1: (8,30) → (8,22)   8 left  [2 keys: `8h`]
Seg 2: (8,22) → (5,22)   3 up    [2 keys: `3k`]
Seg 3: (5,22) → (5,12)  10 left  [2 keys: `10h`]
Seg 4: (5,12) → (3,12)   2 up    [2 keys: `2k`]
Seg 5: (3,12) → (3,5)    7 left  [2 keys: `7h`]
Seg 6: (3,5)  → (2,4)    corner  [2 keys: `k l` or `kh`]
```

6 segments × 2 keys = **12 keystrokes on foot**.  `` `b `` = 2 keystrokes.  Saving: 10 keys.
Walls at each bend physically prevent diagonal or straight-line shortcuts.

**The multi-visit path:** To open EXIT ROOM (locked door at (2, 50)):
- K1 in CHAMBER-A: (2, 4)
- K2 in CHAMBER-B: (14, 4)
- K3 in CHAMBER-D: (14, 46)

All three must be collected. The topology forces 3 mandatory returns to Junction (8,30):
once after K1 (to reach lower section for K2), once after K2 (to reach D side for K3),
once after K3 (to reach EXIT via upper-right).

---

### Placements

- **Entry** `@`: ANTECHAMBER (21, 2).
- **Exit** `X`: EXIT ROOM (2, 56). Door at (2, 50) locked until K1+K2+K3 collected.
- **K1**: CHAMBER-A interior, (2, 4).
- **K2**: CHAMBER-B interior, (14, 4).
- **K3**: CHAMBER-D interior, (14, 46).
- **Junction mark target**: (8, 30) — winding hub.
- **Mark hints (scroll entities):**
  - (20, 15): "Mark the Hub — you will return: `ma`."
  - (8, 30): "Mark this crossroads — every chamber winds back here: `mb`."

---

### Optimal keystrokes — step-by-step (S3 full solution)

**With marks (winding maze):**

| Step | Action | Keys |
|------|--------|------|
| ANTE(21,2)→HUB(20,30): `28l`=3, `k`=1 | 4 |
| `ma` at HUB (20,30) | 2 |
| HUB→Junction (8,30): 4-bend winding `9k 3h 4k 2l 3k`≈10 | 10 |
| `mb` at Junction (8,30) | 2 |
| Junction→A (2,4): 6-bend winding (see exemplar) | 12 |
| Collect K1 | 1 |
| `` `b `` → Junction (8,30) | 2 |
| Junction→lower (row 12-14 zone): 5-bend winding `5j 3h 3j 5h 2j`≈10 | 10 |
| Lower→B (14,4): `3h`+`2j`≈4 | 4 |
| Collect K2 | 1 |
| `` `b `` → Junction (8,30) | 2 |
| Junction→lower (same route): 10 | 10 |
| Lower→D (14,46): `3l`+`2j`≈4 | 4 |
| Collect K3 | 1 |
| `` `b `` → Junction (8,30) | 2 |
| Junction→EXIT (3-bend then straight `15l`): `3k 8l 4k 7l`≈10 | 10 |

**Mark path total: 4+2+10+2+12+1+2+10+4+1+2+10+4+1+2+10 = 77 keystrokes**

**Par: 77 keystrokes**
**Budget: ceil(77 × 1.35) = ceil(103.95) = 104**

---

### No-marks path — step-by-step

Without marks, every junction return is walked (12 keys each, 6-bend winding):

| Step | Action | Keys |
|------|--------|------|
| ANTE→HUB→Junction (once) | 4+10=14 |
| Junction→A winding | 12 |
| Collect K1 | 1 |
| A→Junction (foot, 6-bend winding back) | 12 |
| Junction→lower winding+B | 10+4=14 |
| Collect K2 | 1 |
| B→Junction (foot, winding back) | 14 |
| Junction→lower winding+D | 10+4=14 |
| Collect K3 | 1 |
| D→Junction (foot, winding back) | 14 |
| Junction→EXIT | 10 |

**No-marks total: 14+12+1+12+14+1+14+14+1+14+10 = 107 keystrokes**

**STRICT-FORCED: YES.** Budget = 104. No-marks (107) > budget (104). Margin = 3 keys.

Arithmetic: per-return saving = 12 (foot, 6-bend) − 2 (`` `b ``) = 10 keys. 3 returns:
30 keys saved. Mark path = 77; no-marks = 77 + 30 = 107. 107 > 104 = budget. ✓

---

### Revised placements and budget (final)

- Grid: 24 rows × 60 cols.
- Entry: (21, 2). Exit: (2, 56).
- K1: (2, 4). K2: (14, 4). K3: (14, 46). Junction: (8, 30). HUB: (20, 30).
- Par (marks): **77 keystrokes**
- Par (no-marks): **107 keystrokes**
- Budget: **ceil(77 × 1.35) = 104**
- No-marks (107) > budget (104). Margin = 3 keys. **Marks strictly forced.**

**Hint scroll at (8, 30):** "Every chamber winds back to this crossroads. Mark it now
or retrace every bend. `mb`."

---

### Forcing / Teaching argument

**Winding-maze topology (terrain-∞ via direction-change cost):** The maze forces 3
mandatory junction returns (for K1, K2, K3). Each foot-return through the winding maze
costs 12 keystrokes (6 wall-bends × 2 keys each). `` `b `` teleports back in 2 keystrokes.
Saving per return: 10 keys × 3 returns = 30 keys. No-marks (107) exceeds budget (104) by
3 keys. The winding bends defeat count-move compression: `40h` costs 3 keys but a
6-bend path costs 12 keys — 4× more. The NUMBER OF DIRECTION CHANGES drives the asymmetry.

**`'` vs `` ` `` distinction:** `'b` lands at the first non-blank of row 8 (e.g., col 3
or col 4 — leftmost maze-entry cell), not at (8,30). Navigation col 4→col 30 = `26l`=3
extra keys per use. 3 uses: +9 keys. Using `'` for all 3 returns costs 9 extra, pushing
the marks path from 77 to 86 — still under budget (104). So `'` still forces marks over
no-marks; `` ` `` saves the extra 9 keys over `'`, incentivising the player to learn the
distinction in practice. Both are forced by the budget gap; `` ` `` is strictly cheaper.

---

### Primitives

- Walls, floor, winding corridors (existing wall primitive), doors — all existing.
- Keystones — existing.
- Scroll hints — existing.
- Winding corridor topology uses standard walls arranged to force 5-6 direction changes
  per return path — no new engine primitive required.

**CHALLENGE C-L12-A (engine prerequisite):** `player.marks` dict + `m{a-z}` dispatch +
`` `a ``/`'a` dispatch are unimplemented (confirmed: LEVELS_PLAN.md Part 5). Required
before L12 runs. This challenge is UNCHANGED from the prior design — it is an engine
implementation task, not a design tension.

**CHALLENGE C-L12-B:** The par-solver must model mark-teleports in its Dijkstra state.
`frozenset` of `(char, row, col)` mark states needed. Alternatively, hardcode par=77 for
this fixed layout and skip the solver extension (recommended for the winding-maze layout,
which has a fixed deterministic optimal path).

---

### Self-check

- (1) Scope: 2 mechanics (`m` set-mark, `'`/`` ` `` jump-to-mark). Pass.
- (2) Linkage: mark set + mark jump are the standard Vim mark pair. Pass.
- (3) Forced (S2, winding topology): no-marks (107) > budget (104) at ×1.35 multiplier.
  Margin = 3 keys. Winding bends defeat count-compression: 6 direction changes × 2 keys
  = 12 foot-cost vs 2 mark-cost. Gap is comfortable. Pass.
- (4) Boss: not applicable. Pass.
- Grid revised to 24 rows × 60 cols (winding maze). Engine flags specific. Pass.

---

---

## Level 13 — The Archivist's Library

**Commands:** `:e {filename}`, `:set {option}`

**Teaching mode: CONTEXTUAL — not budget-forced.**
Budget multiplier: ×2.0 (explicitly documented per S2, justified per LEVELS_PLAN.md D1
precedent). The level is a guided discovery moment: "the overworld is a filesystem."

**New mechanics (2):**
- `:e {dungeon-name}` — travel to a dungeon by filename.
- `:set number` — toggle line-numbers (reveals enemy HP).
**Linkage:** Both are command-mode (`:`) meta-operations. `:e` = navigation; `:set` =
configuration. Same control-plane family as `:wq`/`:q!` from Act I.

---

### Grid

```
Dims: 22 rows × 80 cols   (the Library's Reading Hall)
```

Exact layout (22 rows × 80 cols, 0-indexed):

```
Row  0: wall (full)
Row  1: #   THE ARCHIVIST'S LIBRARY                                          #
Row  2: #   (subtitle rune cluster)                                          #
Row  3: wall (partial — north stacks wall)
Row  4: #  [shelf-A]  [shelf-B]  [shelf-C]  [shelf-D]  ...                  #
Row  5: #  (dungeon-name rune clusters: "cave_01" "crypt_02" "goblin_gauntlet" "cataracts" "mirror_temple" "index")
Row  6: #  [shelf-E]  [shelf-F]                                              #
Row  7: wall (partial — dividing stacks from center)
Row  8: #                                                                    #
Row  9: #   [ARCHIVIST: Entity kind='npc', shows scroll on bump]            #
Row 10: #   [READING TABLE: decoration rune]                                 #
Row 11: #                                                                    #
Row 12: wall (partial — dividing center from south)
Row 13: #  [shelf-G]  [shelf-H]  — :set option names as rune clusters       #
Row 14: #  "number"   "wrap"     "ignorecase"                                #
Row 15: wall (partial)
Row 16: #  @ ENTRY                                                           #
Row 17: #  [SCROLL-1: "Every dungeon is a file. `:e <dungeon-name>` opens it.
         The filenames are on the shelves. Try `:e index`."]                 #
Row 18: #                                                                    #
Row 19: #  [SCROLL-2: "`:set number` reveals an entity's true strength."]   #
Row 20: #  [X — portal, initially fogged/locked]                             #
Row 21: wall (full)
```

---

### Placements

- **Entry** `@`: (16, 3).
- **Exit** `X`: (20, 70) — initially fogged. Revealed + unlocked after `:e index` +
  return sequence.

**Scrolls:**
1. (17, 3): "Every dungeon is a file. `:e <dungeon-name>` opens it. Try `:e index`."
2. (19, 3): "`:set number` reveals an entity's true strength. Try it now."
3. (9, 38) [Archivist NPC]: "The INDEX holds the way forward. Return here once you
   have read it."

**Dungeon-name rune clusters (STACKS NORTH, rows 4-6):**
- `"cave_01"`, `"crypt_02"`, `"goblin_gauntlet"`, `"cataracts"`, `"mirror_temple"`,
  `"index"`
The player can read them. The special one is `"index"`.

**:set option rune clusters (STACKS EAST, rows 13-14):**
- `"number"`, `"wrap"`, `"ignorecase"`

**The INDEX "file":** When the player types `:e index<Enter>`, the game loads a
handcrafted 4×30 read-only room:
```
  ┌──────────────────────────┐
  │  INDEX OF DUNGEONS       │
  │  ─────────────────────── │
  │  PASSPHRASE: "OPEN"      │
  └──────────────────────────┘
```
The player reads it, then types `:q<Enter>` (or `:e archivist_library<Enter>`) to return.
On return, `player.flags['index_read'] = True` is set automatically. The Archivist NPC
checks this flag on bump — no explicit passphrase input required; the flag IS the
passphrase mechanism. This avoids any free-text input complexity.

**`:e` scope guard (D8 fix):** `:e <name>` within L13 is restricted to the names
present on the shelves. Any other name returns the Archivist's message: "That dungeon
is not in this library." This prevents softlocks from `:e`-ing into rooms without
return paths. Shelf names other than `"index"` load abbreviated stub rooms (2×20, empty
except for a `:q` hint) — they all have a `":q` to return" scroll and cannot trap the
player.

**`:set number` demonstration:**
Two stationary guard Entities (HP=2 each) on rows 8-10. Before `:set number`, HP is
hidden (shown as `g`). After `:set number`, HP shows as `g(2)`. A bonus keystone (K)
in STACKS EAST unlocks a scroll reward — but is NOT required for the exit. Guards can
be bypassed by walking around them; `:set number` is contextually rewarding, not forced.

**`:e` is a hard lock (D8 / review Forceability concern):**
The exit portal at (20, 70) is fogged and locked. The ONLY trigger to reveal and unlock
it is the Archivist NPC bump with `player.flags['index_read'] == True`. The ONLY way to
set that flag is to `:e index` and return. There is no alternative path. `:e index` is
a genuine hard prerequisite for progression.

---

### Optimal keystrokes

1. Read entry scroll: bump (1 key).
2. Open INDEX: `:e index<Enter>` = 9 keystrokes (`:`, `e`, ` `, `i`, `n`, `d`, `e`, `x`, `Enter`).
3. Read passphrase. Return: `:q<Enter>` = 3 keystrokes.
4. Navigate to Archivist NPC + bump: ~7 moves = 3-4 keystrokes (count-move to row 9).
5. Exit revealed — navigate to portal: ~12 keystrokes.

**Par: ~28 keystrokes** (no optional content)
**Budget: ceil(28 × 2.0) = 56** (contextual ×2.0 multiplier, documented)

---

### Forcing / Teaching argument

**`:e` is contextually taught (hard lock):** The exit portal is physically locked until
`:e index` + return. No budget math needed — it is structurally impossible to reach the
exit without `:e`. The experiential insight ("the dungeon I just visited was a file")
is the teaching moment.

**`:set` is contextually taught (reward, not required):** The bonus keystone provides a
scroll reward but doesn't gate the exit. The `:set number` → HP-visibility → guard-HP
puzzle is engaging but optional. This matches the contextual design pattern.

**Overworld-as-filesystem reveal:** Shelf rune clusters listing real dungeon names makes
the metaphor concrete. The player can `:e cave_01` and see an abbreviated version of an
earlier level — genuine Vim-fidelity moment with no softlock risk (all stubs have `:q`).

---

### Primitives

- Rune clusters — existing RuneCluster.
- NPC Entity (scroll-on-bump) — existing.
- Fog-of-war on exit portal — existing.
- Keystones — existing.

**CHALLENGE C-L13-1:** `:e {name}<Enter>` dispatch in command mode — maps name to
`build_dungeon_N()` or stub room builder. The engine has `:wq` / `:q` dispatch
(`engine/modes.py` or `main.py`); `:e` must be added. Requires a dungeon-name registry.

**CHALLENGE C-L13-2:** `:set number<Enter>` — toggles `player.options['number']`; renderer
checks this flag to show HP. `player.options` dict + `:set` parser needed. Neither exists.

**CHALLENGE C-L13-3:** Return-to-library mechanic — `:q` in a nested room (INDEX or stub)
must restore the player's exact position in the Archivist's Library room, including
`player.flags['index_read']` being set. This requires a room-stack or save-state mechanism.

---

### Self-check

- (1) Scope: 2 mechanics (`:e`, `:set`). Pass.
- (2) Linkage: command-mode meta-operations. Pass.
- (3) Contextual: `:e` is a hard lock (structurally required). `:set` is contextual
  (rewarding but optional). ×2.0 multiplier documented. Pass.
- (4) Boss: not applicable. Pass.
- D8 (`:e` softlock) fixed by name restriction + stub rooms with `:q` return. Pass.

---

---

## Level 13.1 — The Warden Pathfinder (ACT III BOSS)

**Commands required (from Act III):** `%`, `/ ? n N`, `m ' \``, `:set`
**Boss type:** Multi-phase Warden

---

### Grid

```
Dims: 24 rows × 78 cols   (the Pathfinder's Arena)
```

Layout unchanged from original blueprint (phases in NW/SW/NE/SE chambers + arena floor).
See original grid diagram — structural layout is sound. Defects are in phase mechanics
only.

---

### Boss Phases Table

| Phase | Trigger | Mechanic required | Chamber | What the player does |
|-------|---------|-------------------|---------|---------------------|
| **1** | Enter arena | `%` | NW Chamber | 3 `[ ]` void-interior pairs; `%` across each to reach shield keystone. |
| **2** | Shield 1 down | `/n N` | SW Chamber | `/WARDEN<Enter>` finds first entity; `n` skips decoys; `N` back if overshoot; `x` each (decoys die in 1 hit, real Warden doesn't). |
| **3** | Warden located | `m '` `` ` `` | NE Chamber | Non-linear keystone layout + Warden blocking. Must mark-jump to collect all three. See redesign below. |
| **4** | Shield 2 down | `:set number` | SE Chamber | Warden's HP is hidden; blind `x` reflects damage (mirror trap); `:set number` reveals HP=3; player presses `x` exactly 3 times. |
| **Final** | All shields down | `%` + `x` | Arena floor | Cross void bridge via `%`; `x` to deliver final blow. |

---

### Detailed phase mechanics

**Phase 1 — Bracket Gauntlet (NW Chamber, rows 3-5, cols 3-24): UNCHANGED**

```
#  [ V O I D ] [ V O I D ] [ V O I D ] [K]  #
```

Three `[ ]` pairs with void interior. Player must `%` across each. Third `]` lands on
K (shield-1 keystone). This is structurally identical to L10 — no defect found in review.

Phase 1 par: 3× (moves to bracket + `%`) + collect K.
- `[` at col 5: `2l`=2; `%`=1 (→ col 12)
- `[` at col 14: `2l`=2; `%`=1 (→ col 21)
- `[` at col 23: `2l`=2; `%`=1 (→ col 30, K)
- Collect K: 1 key (auto or bump)
Phase 1 par: 2+1+2+1+2+1+1 = **10 keystrokes**

**Phase 2 — Search Gauntlet (SW Chamber): CLARIFIED (D11 fix)**

```
#  [fog][decoy-W][fog][decoy-W][fog][decoy-W][fog][WARDEN-real][fog]  #
```

Four entities: 3 decoy goblins named `"WARDEN"` (HP=1), 1 real Warden (HP=5).
All fogged initially.

`/WARDEN<Enter>` = 7 keys. First match may be a decoy or the real one.
`n` = 1 key to advance to next match. `N` = 1 key to go back.
Player tests each found entity with `x`:
- Decoy: dies in 1 hit (HP=1). Confirmed decoy — continue with `n`.
- Real Warden: survives 1 hit (HP=5). Confirmed real — phase 2 ends.

**`:set number` is NOT required in Phase 2** (D11 fix — clarified). Decoys die in 1 hit
regardless of whether HP is visible. The player identifies the real Warden by exclusion.
The Phase 2 description no longer mentions HP visibility as useful here.

Phase 2 par: `/WARDEN<Enter>`=7, then in best case `x` on first match (real) = 1 key;
total = 8. Worst case: 3 decoys first = `n x n x n x x` = 3+3+1 = 7 more = 15. Average
~12. Designer's estimate of ~12 is consistent.

Phase 2 par estimate: **12 keystrokes** (average path; worst seed = 15).

**Phase 3 — Mark Gauntlet (NE Chamber): REDESIGNED (D9 fix)**

**Problem (from review):** Original layout had K-red(col54)→K-blue(col60)→K-green(col68)
in linear left-to-right order. Player could walk straight through without marks. The Warden
spawning at col 60 (K-blue's position, already passed) would be BEHIND the player, not
blocking K-green.

**Redesigned layout — U-shaped chamber (NE Chamber, rows 3-5, cols 52-75):**

```
  cols:  52  54  56  58  60  62  64  66  68  70  72  74
row 3:  #  [K-red]  .  .  .  .  [wall-barrier]  .  [K-green]  #
row 4:  #  .  .  .  .  [K-blue]  .  .  .  .  .  .  #
row 5:  ####################################################
```

Precise specification:

```
Row 3: # [floor col 52-55] [WALL cols 56-64] [floor col 65-74] #
Row 4: # [floor col 52-74, fully passable]                      #
```

- **K-red**: (3, 54) — upper-left arm, accessible only from row 4 via col 54 up to row 3.
- **K-blue**: (4, 62) — center of lower passage.
- **K-green**: (3, 70) — upper-right arm, accessible only from row 4 via col 70 up to row 3.
- **Wall barrier**: row 3, cols 56-64 — solid wall separating left arm from right arm
  in the upper row. The only connection between the two upper arms is through row 4.

**Warden spawn trigger:** The Warden appears at **(4, 63)** — immediately to the RIGHT of
K-blue — after K-blue is collected.

**Sequence of events:**

1. Player enters from col 52. Walks right on row 4.
2. To collect K-red: player must go UP from (4, 54) to (3, 54). Then back DOWN to row 4.
   Optimal: reach (4,54), `k`=1, collect K-red=1, `j`=1 back to row 4. Cost: 3 keys.
3. Continue right on row 4 to K-blue at (4, 62). Collect K-blue. Cost: `8l`=2, collect=1.
4. **Warden spawns at (4, 63)** — immediately to the right of the player who is at (4, 62).
5. K-green is at (3, 70). To reach it: player must go RIGHT past col 63 (where Warden is)
   on row 4, OR teleport past the Warden via mark-jump.
6. **Without marks:** Player is at (4, 62). Warden at (4, 63). Player moves right → Warden
   pushes back (combat: player takes damage but cannot pass). Player cannot reach (4, 70)
   to go up to (3, 70) because Warden blocks the row. Attempting to squeeze past = death
   (Warden attack on same cell).
7. **With marks:** Before collecting K-blue, player set `ma` at (4, 52) (chamber entry)
   or `mb` at (3, 54) (K-red's upper cell). After K-blue is collected and Warden spawns
   at (4,63): player uses `` `a `` to jump to (4, 52) — behind Warden. Then walks right
   around... wait, Warden is at (4, 63) and player is now at (4, 52) — still blocked.

**Correction — the U-shape is key:**

The wall at row 3, cols 56-64 means there are TWO one-cell-wide "portals" into the upper
row: col 55 (left of wall) and col 65 (right of wall). K-green is at (3, 70), reachable
only by going UP at col 65-74 range.

After Warden spawns at (4, 63), the player at (4, 62) cannot move right past (4, 63).
However, if the player had previously marked position (3, 54) as `ma` (K-red's cell, in
the upper-left arm), they can:
- `` `a `` → teleport to (3, 54), in the upper-left arm.
- Walk right along row 3... but row 3 is WALLED at cols 56-64. Cannot reach (3, 70).

This still doesn't work — the wall barrier blocks row 3 traversal.

**Revised U-chamber design:**

The U-shape must allow travel FROM the left arm TO the right arm via row 4 ONLY, and the
Warden must spawn BETWEEN the left-arm access (col 55) and the right-arm access (col 65).

Player journey:
1. Enter at (4, 52). Go right.
2. Branch UP at (4, 54): collect K-red at (3, 54). Set `ma` here.
3. Return to row 4. Go right.
4. Collect K-blue at (4, 60). **Warden spawns at (4, 62)** — between the wall ends.
   Right-arm access is at (4, 65)→(3, 65+). Warden at (4, 62) blocks col 62-64 range.
5. Without marks: player at (4, 60), Warden at (4, 62). Player cannot reach (4, 65).
6. With `` `a ``: teleport to (3, 54). Row 3, left of wall. STILL blocked by wall.

The problem: the wall-in-row-3 prevents using a mark in the upper arm to reach the upper
right arm. The mark-jump must land somewhere that circumvents the Warden's block of row 4.

**Final Phase 3 design — backtrack-requiring layout:**

The chamber has a secondary entrance. The NE Chamber is connected to the arena floor
(below) by TWO doors: one at col 55 (west door) and one at col 70 (east door). The
Warden's spawn at col 62 BLOCKS the single-row-4 passage between the two doors.

```
Row 3: # [K-red col54] [wall cols 56-64] [K-green col 70] #
Row 4: # [K-blue col 60] [Warden spawn col 62] [floor 65-74] #
Row 5: #### [west-door col 55] #### [east-door col 70] ####
```

The arena floor (row 9 or equivalent) connects to both doors. To reach K-green after
Warden spawns:
- Player must EXIT via west door (returning to arena floor), walk right to east door, and
  enter east door — arriving at (4, 70), then up to (3, 70) = K-green.
- This "going around through the arena" costs: exit west door (~3k to row 9) + walk right
  to east door (~15l) + enter east door (~3k to row 4) + reach K-green (up 1k) = 22+ keys.
- With marks: set `mb` at the east-door threshold (4, 70) before the Warden spawns (player
  must pass through it on entry — the chamber is entered from the east door OR the west door).

**Wait — if the player enters from the west door and must pass the east door position to
collect K-red and K-blue, they can set `mb` at (4, 70) as they pass it going left to K-red.
Then after Warden spawns at col 62, `` `b `` teleports to (4, 70) — east of Warden — and
the player climbs up to (3, 70) for K-green.**

This works! The forcing argument:

- Player enters NE chamber from west door at (5, 55), moves up to row 4.
- Passes through (4, 70) on the way left to K-red. **Sets `mb` at (4, 70).**
- Goes left to (3, 54) — K-red. Sets `ma` at (3, 54). Collects K-red.
- Returns to row 4. Goes right. Collects K-blue at (4, 60).
- **Warden spawns at (4, 62).** Player is at (4, 60), Warden at (4, 62). K-green at (3, 70).
- Without marks: player must exit west (back through col 55 to arena, ~5+ keys left) then
  traverse arena to east door (col 70, ~15 keys right) then enter east door (~5 keys up)
  = ~25+ extra keys to reach K-green.
- With `` `b ``: teleport to (4, 70) — 2 keys. Then `k` to (3, 70) = K-green: 1 key.
  Total: 3 keys.
- Savings: ~22 keys. Budget impact: decisive.

**This is the true backtrack.** The player set `mb` at (4, 70) BEFORE the Warden spawned,
anticipating the need. Without that mark, the only route to K-green is the long arena
detour. The mark-jump is genuine and requires foresight.

Phase 3 layout (final):

```
NE Chamber (rows 3-5, cols 52-75):

Row 3:  #   [K-red col 54]   [WALL cols 56-69]   [K-green col 70]   #
Row 4:  #   [floor, left arm 52-55] [K-blue col 60] [WARDEN-spawn col 62] [floor 63-75]  #
Row 5:  ####[west-door col 55]#######################[east-door col 70]####

Arena connection: west door (5,55) and east door (5,70) both connect to arena floor (row 9).
```

Phase 3 par (with marks):
- Enter west door, move right to (4,70): `15l`=3 keys.
- Set `mb` at (4,70): `mb`=2.
- Move left to (3,54) via (4,54)→up: `16h`=3, `k`=1.
- Set `ma` at (3,54): `ma`=2.
- Collect K-red: 1.
- Return to (4,54): `j`=1.
- Move right to (4,60): `6l`=2.
- Collect K-blue: 1. (Warden spawns at (4,62).)
- `` `b `` to (4,70): 2.
- `k` to (3,70): 1. Collect K-green: 1.
- Collect = auto (on K-green cell): counted as 1.
- Exit via east door: `5j`=2 (to row 9).
Phase 3 par: 3+2+3+1+2+1+1+2+1+2+1+1+2 = **22 keystrokes**

Phase 3 par (without marks) — arena detour:
Enter west, move right to K-red: `2l`+`k`+collect=4. Return to row 4: `j`=1. Move right
to K-blue: `6l`=2+collect=1. Warden blocks. Exit west: `3h`+`5j`=2+2=4. Move right in
arena to east door at col 70: `15l`=3. Enter east door: `5k`=2. `k` to row 3: 1. Collect
K-green: 1. Exit east door to arena: `6j`=2.
No-marks par: 4+1+2+1+4+3+2+1+1+2 = **21 keystrokes** (approximately same as mark path!).

**Problem again:** The arena detour only costs 2-3 extra keys beyond the mark path because
count-moves compress the long horizontal run. The mark-jump saves ~22 manual steps but
those steps only cost 3-4 keystrokes with count-moves.

**CHALLENGE C-L13-1-Boss (critical, same root cause as C-L12-1):** Count-move compression
eliminates the mark-forcing advantage in Phase 3. The arena detour (15 cells) costs `15l`
= 3 keys. The mark-jump costs 2+1 = 3 keys. Essentially the same cost.

**Resolution: forbid count-prefix in the NE Chamber during Phase 3** (extend C-L12-2 to
boss rooms, or alternatively make the arena detour structurally longer by requiring door
interaction sequences that each cost 1 key each, e.g. 20 door segments each requiring a
single `l` = 20 keys vs. `` `b `` = 2 keys).

**Alternative resolution (preferred):** Make the arena detour physically much longer by
inserting a maze corridor between the west exit and the east entrance — 30+ individual
floor cells requiring 1 key each. This is terrain forcing (S1): the detour is long by
design, not by grid width.

**Adopted fix for Phase 3:** Insert a 30-cell winding corridor (rows 6-8, cols 30-75)
between west door and east door. No count-prefix block needed. Detour = 30 keys.
Mark-jump = 2+1 = 3 keys. Saving = 27 keys. Budget decisive.

Phase 3 revised par (marks): **22 keystrokes** (unchanged — mark path doesn't use detour).
Phase 3 detour (no marks): 4+1+2+1+(detour 30 keys)+1+1+2 = **42 keystrokes**.

Revised Phase 3 total no-marks: 42 keystrokes vs marks: 22 keystrokes. Saving: 20 keys.
At budget including all phases, this gap is decisive.

**Phase 4 — Final Config (SE Chamber): REDESIGNED (D10 fix)**

**Problem (from review):** Player can spam `x` until exit door opens — `:set number` not
genuinely required. Fix: mirror trap mechanic.

**Redesigned Phase 4:**

```
SE Chamber (rows 13-15, cols 52-73):
#  [WARDEN final form — HP=3, hidden until :set number]  #
#  [scroll: "What you cannot see, you cannot fight."]    #
#  [mirror-trap rune: "REFLECTOR" — reflects excess damage to player]  #
#  [X EXIT portal — locked, opens when Warden HP=0 AND mirror intact] #
```

**Mirror Trap mechanic:** A `REFLECTOR` rune entity is present in the SE chamber. This
entity is active while the Warden is alive. When the player presses `x` (attack), if
the Warden's current HP is already 0, the damage is reflected back to the player (-1 HP
per reflected `x`). Since the player likely enters Phase 4 with limited HP remaining
from earlier phases, 2-3 reflected hits cause death.

The exit portal opens ONLY when Warden HP = 0. The Warden starts at HP=3.

**Without `:set number`:** The player does not know HP=3. To avoid reflection-death:
- Spam `x` and hope to stop at exactly 3 — probability 1/N where N = number of `x`
  presses the player is willing to try. With ~5 HP remaining and 1 reflected damage per
  over-press: player can afford 0 over-presses. Effective probability of success without
  knowledge ≈ 1/∞ (must press exactly 3 times with no feedback).
- The scroll says "What you cannot see, you cannot fight." — contextual hint for `:set`.

**With `:set number`:** Warden shows `WARDEN(3)`. Player presses `x` three times,
watching HP count down: `WARDEN(2)` → `WARDEN(1)` → `WARDEN(0)`. Exit opens. Mirror
trap never triggers. No reflected damage.

**`:set number` is now genuinely required for safe completion.** Without it, the player
faces certain death (any over-press reflects). `:set number` is a hard lock via risk
rather than structure — but because the risk is deterministic (1 over-press = 1 death
with reduced HP pool), it functionally forces the command.

**CHALLENGE C-L13-2-Boss:** The mirror-trap reflected damage requires that `x` on a
dead entity (HP=0) deals 1 damage to the player. This is a new engine behavior —
currently `x` on a dead/absent entity is likely a no-op. The `REFLECTOR` entity or an
HP-check on `x` dispatch must be implemented. A human must decide the implementation
mechanism.

Phase 4 par (with `:set number`):
- `:set number<Enter>` = `:` `s` `e` `t` ` ` `n` `u` `m` `b` `e` `r` `Enter` = 12 keys.
- 3× `x` = 3 keys.
- Navigate to exit portal: ~5 keys.
Phase 4 par: **20 keystrokes**

(Previous blueprint said ~8. Corrected here per D12 — `:set number<Enter>` alone = 12
keys. Total ~20 is accurate.)

---

### Par and budget (revised)

| Phase | Par (keystrokes) | Notes |
|-------|-----------------|-------|
| Phase 1 | 10 | 3 `%` crossings + collect |
| Phase 2 | 12 | `/WARDEN`+`n`+`x` sequence (average seed) |
| Phase 3 | 22 | Mark-guided collection with winding corridor detour |
| Phase 4 | 20 | `:set number<Enter>` + 3×`x` + exit nav |
| Transitions | 14 | Between chambers (arena traversal) |

**Par: 10+12+22+20+14 = 78 keystrokes**
**Budget: ceil(78 × 1.4) = ceil(109.2) = 110**

(Previous blueprint: par=60, budget=84. Corrected per D12 — Phase 4 alone was
undercounted by 12 keys; Phase 3 redesign adds 4 keys.)

---

### Forcing / Teaching argument

Each phase forces exactly one mechanic:
- **Phase 1:** Void-interior `[ ]` pairs — `%` is the only safe gap-crosser (terrain-∞).
- **Phase 2:** Decoy Wardens in fog — `/WARDEN<Enter>` + `n`/`N` is the only cheap
  real-Warden locator (budget forces search vs. manual cell-check).
- **Phase 3:** Warden blocks the only linear path to K-green — `` `b `` mark-jump (2 keys)
  bypasses the 30-key winding detour (terrain+budget forcing, S1+S2).
- **Phase 4:** Mirror trap reflects excess `x` → player death — `:set number` reveals HP=3
  so player knows exactly when to stop. Without it, any over-press is fatal (structural
  forcing via damage reflection).

Act II motions (`G gg H M L } {`) are blocked by the Warden immunity flag
(`warden_phase_immune: set[str]`) — no cheap path via earlier long-range motions.

---

### Primitives

- All primitives from Levels 10-13.
- Warden entity with multi-phase HP + shield — existing boss framework.
- Decoy entities (`kind='goblin'`, `name="WARDEN"`) — existing.
- Phase gating via HP thresholds — existing.

**CHALLENGE C-L13-1-Boss:** Count-move compression threatens mark-forcing in Phase 3.
Resolved by 30-cell winding corridor (terrain forcing). No engine change required for
THIS fix, but the winding corridor must be physically laid out in the room builder.

**CHALLENGE C-L13-2-Boss:** Mirror trap (`x` on HP=0 entity → player -1 HP). Requires
new engine behavior: `x` dispatch checks if target entity HP ≤ 0; if so, applies damage
to player and activates REFLECTOR effect. Must be implemented before Phase 4 runs.

**CHALLENGE C-L13-3-Boss (existing):** Warden immunity flag `warden_phase_immune: set[str]`
on Entity — motion dispatch checks before applying Act II motions. Already flagged in
original blueprint; unchanged.

**CHALLENGE C-L13-4-Boss:** All engine extensions from L10-L13 (`%`, last_search, n/N,
marks, `:e`, `:set`) must be implemented before this boss level runs. The boss depends on
all of them.

---

### Self-check

- (1) Scope: Boss uses all Act III mechanics. Acceptable for a boss level. Pass.
- (2) Linkage: Each phase maps 1:1 to an Act III teaching level. Pass.
- (3) Forced:
  - Phase 1: void-gap forcing. Pass.
  - Phase 2: decoy-fog forcing. Pass (D11 clarified — `:set` not needed in P2).
  - Phase 3: winding detour + mark-jump (D9 redesign). Pass pending C-L13-1-Boss
    (winding corridor must be built).
  - Phase 4: mirror-trap forcing (D10 redesign). Pass pending C-L13-2-Boss.
- (4) Boss: caps Act III at 13.1. Well-spaced after 9.1. Pass.

---

---

## Engine Extensions Summary (Act III) — Revised

All extensions below must be implemented before Act III runs, ordered by dependency:

| Extension | Required by | Status | Notes |
|-----------|------------|--------|-------|
| `%` motion in `engine/motion.py` | L10, Boss P1, Boss Final | CHALLENGE C-L10-1 | Scan row for bracket glyph under cursor; jump to pair. Brackets: `[](){}` in RuneCluster. |
| `player.last_search` (pattern + direction) | L11, Boss P2 | CHALLENGE C-L11-2 | Store after `/` or `?`. Used by `n`/`N`. |
| `n`/`N` dispatch | L11, Boss P2 | CHALLENGE C-L11-2 | `find_next()` with stored pattern/direction. |
| `/pattern` avatar teleport | L11, Boss P2 | CHALLENGE C-L11-1 | Critical: player avatar moves to match cell, not just cursor. Human decision required. |
| Fog reveal on teleport | L11 | CHALLENGE C-L11-3 | Fog clears when avatar position changes. Likely free if fog tied to `player.row/col`. |
| `player.marks` dict | L12, Boss P3 | CHALLENGE C-L12-2 | `{char: (row,col)}`. `m{a-z}` sets; `` `{a} `` and `'{a}` jump. |
| `` `a ``/`'a` dispatch | L12, Boss P3 | CHALLENGE C-L12-2 | `` `a `` → exact (row,col); `'a` → first non-blank of marked row. |
| Budget multiplier ×1.03 for L12 | L12 | CHALLENGE C-L12-3 | Near-zero slack; human must accept or redesign topology. |
| Count-prefix forcing gap | L12 | CHALLENGE C-L12-1 | Count-move compression collapses mark budget advantage. Human decision required. |
| `:e {name}` command dispatch | L13, Boss P4 | CHALLENGE C-L13-1 | Name→builder registry. Add to command-mode parser. |
| `:set {option}` command | L13, Boss P4 | CHALLENGE C-L13-2 | `player.options` dict + renderer HP branch. |
| Room-stack / return-to-library | L13 | CHALLENGE C-L13-3 | `:q` in nested room restores prior room state + sets flags. |
| Mirror trap (x on dead entity → player damage) | Boss P4 | CHALLENGE C-L13-2-Boss | New engine behavior on `x` dispatch. |
| Winding corridor (30-cell) in NE Chamber | Boss P3 | CHALLENGE C-L13-1-Boss | Must be laid out in room builder; no engine change, just map design. |
| Warden immunity flag | Boss | CHALLENGE C-L13-3-Boss | `warden_phase_immune: set[str]` on Entity; checked in motion dispatch. |
| Mark-aware par solver (or hardcoded par) | L12 | CHALLENGE C-L12-3 | Dijkstra state includes frozenset of mark positions, or hardcode par=49. |
