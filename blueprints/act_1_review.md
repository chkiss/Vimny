# Act I Blueprint — Adversarial Review

Reviewer posture: treat every "forcing argument" as guilty until proven innocent.
All keystroke arithmetic is recomputed independently from the grid, ignoring the
blueprint's own par figures until verified.

Engine conventions assumed:
- count cost = len(str(N)) + 1
- `$`/`0`/`^` are room-scoped (stop at room wall / fog boundary)
- `f`/`F`/`t`/`T` scan through water but stop at walls
- hjkl stop at walls; void rune cells are floor but lethal to land on
- door cell blocks traversal until opened with `x`

---

## Level 0 — The First Cave

### Scope (PASS)

Claimed mechanics: 3 — `hjkl` (4-direction nav), `x` (interact/open), `:wq` (exit ritual).
The blueprint correctly counts all four directional keys as one mechanic (trivial direction
variants). `:wq` is presented as a prompted ritual, not a free-standing lesson. Count = 3.
Limit = 3. PASS.

### Linkage (PASS)

`hjkl` → `x` → `:wq` is a single coherent entry ritual: move, interact, leave.
No mixed families. PASS.

### Forceability (FAIL)

**Recomputed par (independent BFS).**

Grid: entry `@` = (1,1), exit `X` = (1, exit_col). The blueprint says exit_col is the left
interior of Room 2. Looking at the 52-col schematic, Room 2 spans roughly cols 42-50 interior,
so exit_col ≈ 42.

Canonical path the blueprint describes:
  (1,1) → down to corridor row 4 → right across corridor → up to row 1 in Room 2 → left to exit.

Let's count that precisely on the stated grid:

  Step 1 — down from row 1 to row 4: 3 presses of `j` = 3 keystrokes.
           (Row 4 is the top corridor row in the 52-col layout.)
  Step 2 — right from col 1 to the Room 2 left wall. The corridor runs cols 2-ish to col 42
           (Room 2 left boundary ≈ col 42). That is ~40 `l` presses with hjkl.
           However the blueprint's "intended optimal" uses only `l` presses — no `$` (not yet
           taught). So the "only motion available" argument is correct: at Level 0, only hjkl
           exist. The par must be computed assuming ONLY hjkl.
  Step 3 — up from row 4 to row 1: 3 presses of `k` = 3 keystrokes.
  Step 4 — navigate within Room 2 to reach exit col. If exit is at (1,42), player arrives at
           (1,42) and is done after step 3. If Room 2 interior starts at col 42, no further
           h/l needed.

Let us reconstruct from the schematic values: entry (1,1), void guards at (2, exit_col) and
(3, exit_col). The blueprint states par = 18 "representative" and notes BFS is done per seed
by `_bfs_par`.

Key question: **does the budget actually force using all four directions?**

The blueprint claims void runes at (2, exit_col) and (3, exit_col) force a `l`-then-`k`-then-`h`
detour. Examine:

Without void guards: player could go straight up from corridor entry into Room 2, needing
no `h` movement (just arrive at the column already aligned). The void guards at rows 2-3
block the straight `k k` approach from below. But the player approaches from the corridor
(rows 4-5), and Room 2 is to the right. Entry into Room 2 from the corridor places the
player somewhere in Room 2 interior (col range 42-50 interior). The exit is at (1, 42) —
leftmost interior.

So after entering Room 2 via the corridor (rows 4-5 → up into Room 2), the player would be
at (say) col 43-ish. They need to reach (1, 42). The `h` presses needed = 1. The void guards
are at col 42 rows 2 and 3, so they block direct `k` traversal up column 42. The player must
use `l` to go right of col 42, then `k` up, then `h` back left to col 42.

This does plausibly force all four directions. However:

**Adversarial test: can the player avoid `h`?**
If the player enters the corridor in row 4 at col 2, then travels right: they stop at the
Room 2 left boundary. Room 2 interior columns are 42+1 = col 43 minimum? If the door is at
col 42 and interior starts at 43, then `k k k` from (4,43) goes to (1,43). Exit is at (1,42).
Player must press `h` once. Void guards are at (2,42) and (3,42) — they block col 42 only,
not col 43. So `k k k` from (4,43) to (1,43) is clear, then `h` to (1,42). Player uses `h`.

**Adversarial test: can the player avoid `k`?**
Exit is on row 1. Player starts on row 1. If there is a direct row-1 path, player never needs
`j` or `k`. The schematic shows row 1 as: `#@.................######################X.........#`.
Between col 1 and the exit there is a wall of `#` (the Room 1 / Room 2 separator). Player
cannot traverse row 1 directly. Player must go down to corridor rows 4-5. So `j` is required.
After corridor transit, player must go back up. So `k` is required.

**Adversarial test: can the player avoid `j`?**
Player is at (1,1). To reach corridor rows 4-5, must press `j` 3 times (or `j` at all). No
other way to reach corridor. `j` is required.

**Adversarial test: can the player avoid `l`?**
Player is at (1,1). The corridor entry is to the right of them (col 2+). Without `l`, player
cannot move right. But wait — can the player go *left* of entry? `@` is at (1,1), and col 0
is a wall. There is nowhere to go left. And the exit is to the right. So `l` is required.

Conclusion: all four directions are genuinely required by the geometry. This is correct.

**Budget check:**
Stated par = 18, budget = ceil(18 × 1.4) = ceil(25.2) = 26.

The exact par is "representative; computed per-seed by `_bfs_par`." This is a serious problem.
The par is stated as approximate and seed-dependent. The blueprint offers no single authoritative
grid from which to verify par = 18 exactly. The statement "par = 18 (representative)" means the
budget (26) is also only approximate.

**Critical defect — budget not deterministically verifiable.**
For forceability, we need: stated budget = ceil(par × 1.4) AND taught command is the STRICTLY
cheapest path AND next-best exceeds budget.

At Level 0, the taught commands ARE the only commands. "Next-best alternative: random walk."
This means forceability is trivially satisfied by logic (no other commands exist), not by
arithmetic. The budget is irrelevant to forcing here — the player has no alternative commands
to skip. The budget (26) is generous by design.

However the principle states the budget must force the command. At Level 0 with a new player who
has NO commands, the budget only limits backtracking, not command choice. The blueprint
acknowledges: "Budget is generous (1.4×) to allow for exploratory mistakes."

**Is forceability satisfied?** Technically yes, because the player cannot move at all without
`hjkl`, and the geometry forces all four. The budget is a soft fail-safe, not the primary
forcing mechanism. This is a legitimate and appropriate design for a tutorial level.

**But the par = 18 claim needs scrutiny.** If the corridor is wide (columns 2-42 = 40 cells),
then the minimum path is: 3j (row 1→4) + 40l (col 2→col 42) + 3k (row 4→1) + 1h (col 43→42)
= 47 keystrokes minimum, NOT 18. That would make par = 47, budget = ceil(47 × 1.4) = 66.

The blueprint says par ≈ 17-20. This is wildly inconsistent with a 40-column corridor.
Something is wrong: either the rooms are much smaller than the 52-col grid suggests, or the
par calculation is incorrect.

Looking at the 52-col actual layout row 1:
`#@.................######################X.........#`
Counting: `#` at 0, `@` at 1, `.` at 2-18 (17 dots), `#` at 19-40 (22 wall chars),
`X` at 41, `.` at 42-50 (9 dots), `#` at 51.

So Room 1 interior: cols 2-18 (17 cells). Wall: cols 19-40. Room 2 (with X): cols 42-50.
Exit X is at col 41 (leftmost of Room 2 area).

Now the corridor path: player goes from (1,1) down to corridor rows. The corridor appears to
be a gap in the wall between row 1-3 and row 7-9 (the wall is at rows 0 and 9 only; rows 4-5
are corridor rows based on schematic). Looking at the 52-col layout:

Row 4: `#..................##########################.......#`
Row 5: `##..........................................########`

Row 4 has `#` at 0, `.` at 1-18, `#` at 19-40, `.` at 41-48, `#` at 49. Wait, that shows Room
2 area is accessible via row 4 right side. But there's a wall block cols 19-40 on row 4.

Row 5: `##..........................................########`
Row 5: wall at 0-1, floor at 2-41, wall at 42-49. This is the through-corridor row!

So the corridor path:
1. `jjjj` (4 keys): row 1 → row 5 (4 steps down through Room 1 interior rows 1-4)
   Wait, row 4 has `.` at col 1-18 (still in Room 1). Row 5 is the corridor.
   From (1,1) to (5,1) = 4j.
2. But there's a door! The blueprint says "The `x` key is demoed on the door at the corridor
   entry." Where is the door? The blueprint says `x` opens the first door blocking the exit
   corridor. On row 5, if there's a door at col 19 (Room 1 right boundary), then the player
   needs to reach col 19 row 5 and press `x`.

Path from (1,1):
- `jjjj` (4): → (5,1)
- `llllllllllllllllll` (18): → (5,18) — right edge of Room 1 on row 5
  OR: is there a door that creates a boundary? The corridor row appears to be at row 5 spanning
  cols 2-41 based on `##..........................................########`
  (# at 0,1; . at 2-41; # at 42-49). Room 1's right wall appears at col 18 in room rows but
  on corridor row 5 there may be no wall (open corridor). So `l` presses could go straight to
  Room 2.

If the corridor row 5 is open from col 2 to col 41, and exit is at (1,41):
- `jjjj` (4): row 1 → row 5
- `llllllllllllllllllll` (40 presses from col 1 to col 41): too many
  OR with door at col 18/19 on corridor: `lllllllll` (17) + `x` (1) = 18 to reach corridor
  entrance at col 18, then many more `l` presses.

Actually row 5 from the schematic: `##..........................................########`
Col 0-1 = `##`, col 2 = `.` to col 41 = `.`, col 42-49 = `########`. The corridor on row 5
spans cols 2-41 (40 cells). On row 6 similarly.

If entry is at (1,1) and exit is at (1,41):
Path: `jjjj` (4) + `llll...l` (40, col 1 → 41) + `kkkk` (4) = 48 keystrokes.
But void guards at rows 2 and 3 of exit col (col 41) force the player to approach from col 42
or higher and then use `h`. So: `jjjj`(4) + 41`l` presses (col1→42) + `kkkk`(4) + `h`(1)
= 50 keystrokes.

Or the player can go via row 6 (also corridor): same distance.

**This puts par at roughly 48-50, not 18.** The budget = ceil(48 × 1.4) = 68, not 26.

This is a significant arithmetic defect. The blueprint's par = 18 is only possible if Room 1
is extremely narrow (maybe only 3-4 cols wide) and the corridor to Room 2 is very short.
However the stated "10 rows × 52 cols" and the ASCII art do not support par = 18.

ALTERNATIVELY: the blueprint's "Simplified schematic (32-col version)" may represent the ACTUAL
layout and the "52-col" version is a documentation error. On the 32-col version:
Row 1: `#@..........................####` — col 0=#, col 1=@, cols 2-27=., cols 28-31=#...
Exit appears to be in a smaller Room 2. If Room 2 starts at col 28 and is ~4 cols wide with
exit at col 29:
- `jjjj`(4) + `llll...` (27 from col 1 to col 28) + `kkkk`(4) = 35 keystrokes still >> 18.

Par = 18 is not achievable on a corridor that requires 27+ horizontal moves.

**VERDICT: The par = 18 claim is inconsistent with the grid dimensions. This is an arithmetic
FAIL unless the grid is much smaller than described.**

Defect: Par is stated as 18 but the minimum BFS on the described 52-col grid yields ~48-50.
The budget of 26 would be BELOW par on the actual grid — the player cannot finish within
budget at all, making the level broken rather than merely unforcing.

FORCEABILITY: **FAIL** — par arithmetic does not reconcile with the stated grid dimensions.
The "18" figure appears to be a placeholder / estimate that was never verified against the
actual grid.

### Boss (N/A for Level 0)

---

## Level 1 — The Line Halls

### Scope (FAIL)

Claimed mechanics: the blueprint says 3 — `$`, `0`, `^` as one family, plus `:w/:q/:q!`.
But per LEVELS_PLAN.md §1.1, the audit itself flagged "Two families (motions + command-mode)"
for Level 1 as a Med linkage/scope issue. `:w/:q/:q!` are a distinct command-mode family
from the line-edge motions.

Count of NEW mechanic families: 2 — line-edge motions (`^$0`) and command-mode exits
(`:w :q :q!`). However, LEVELS_PLAN.md also says "command-mode `:w :q :q!` introduced via
the exit ritual, not as 'motions'." If they are not taught as puzzle mechanics but only as an
exit ritual prompt, they may not count as "new mechanics" in the scope sense.

Charitable reading: `:w/:q/:q!` are prompted by the UI at the exit tile and require no
player discovery — they count as 1 "exit ritual extension" mechanic, not 3 separate mechanics.
Total = 2 mechanics (line-edge family + exit ritual extension). Limit = 3. PASS under
charitable reading.

However the blueprint itself lists `:w/:q/:q!` as mechanic #4 ("Not puzzle-gated; explained
by lore scroll"). If it is explained by a lore scroll and not puzzle-gated, it arguably does
not count toward scope. Scope = 1 mechanic family (`^$0`) plus a contextual ritual. PASS.

**Scope: PASS** (with caveat that `:w/:q/:q!` are tutorial-only, not puzzle-gated).

### Linkage (FAIL)

`^`, `$`, `0` are the line-edge family. `:w`, `:q`, `:q!` are the command-mode file-operation
family. These are NOT one coherent family. The LEVELS_PLAN.md audit explicitly called this out
as a "Linkage/Scope: Med" issue.

The blueprint tries to save this by framing `:w/:q/:q!` as extending the Level 0 `:wq` ritual.
But `:wq` in Level 0 is also flagged: it's in the same linkage problem position. `:wq`, `:w`,
`:q`, `:q!` are all command-mode operations and arguably a separate family from motion keys.

The LEVELS_PLAN.md resolved plan (Part 2) still includes both in Level 1: "command-mode
`:w :q :q!` introduced via the exit ritual." If this means they are NOT taught as learnable
commands but merely prompted at the exit UI, it is defensible. But the blueprint explicitly
counts them as "new mechanics" — making it a linkage FAIL.

**Linkage: FAIL** — line-edge motions (`^$0`) and command-mode operations (`:w :q :q!`) are
distinct families bundled in one level. Fix: demote `:w/:q/:q!` to pure UI prompts not listed
as new mechanics, or split them to a separate level.

### Forceability (FAIL)

**Recomputed par independently.**

Grid stated: ENTRY(8r×14c) — corridor(4c wide) — PUZZLE(8r×60c) — corridor(4c wide) — EXIT(10r×14c).
Total: 10 rows × 96 cols.
Entry `@` = (2, 1). Exit `X` = (1, 83).

Intended solution: `jj` + `$` + `kkk` + `^` = 7 keystrokes.

Verify step by step:
- `jj` (2): (2,1) → (4,1). Row 4 is top corridor row (ENTRY rows 1-8, corridor rows 4-5).
  Actually: ENTRY is "8r tall, centered rows 1-8." Corridor is at rows 4-5. From (2,1), `jj`
  → (4,1). Is (4,1) in the corridor? If ENTRY interior is rows 1-8 and corridor is rows 4-5,
  then (4,1) is still in ENTRY interior. The corridor path runs across, not just down. Hmm.
  
  Let me re-read: "Exit `X` = (1, 83)" — row 1. ENTRY bottom corridor row = row 4.
  From entry (2,1), press `jj` → (4,1). Now `$` on row 4: "ENTRY right boundary" = col 13
  (ENTRY is 14 cols wide, interior cols 1-13). But fog extends only to the edge of ENTRY;
  the corridor entrance may be at col 14-17 (4-col wide corridor). Actually `$` is room-scoped
  and stops at the room's right wall. In ENTRY's row 4, `$` → col 13.

Wait, the blueprint says:
  "`$` (1 key): slide rightward to col 81 (right edge of PUZZLE/corridor row 4-5 segment)."

This means from (2,1), after `jj` to (4,1), a single `$` slides all the way to col 81 — the
right edge of PUZZLE including the corridor. That would require `$` to be cross-room-scoped,
not room-scoped. But the engine convention states "`$`/`0`/`^` are room-scoped (stop at room
wall)."

**This is the core contradiction.** If `$` is room-scoped, it stops at col 13 (ENTRY right
wall), not col 81. The player would need to: use `$` in ENTRY → col 13, open the corridor
(no door here?), enter corridor, use `$` again in corridor → col 17ish, enter PUZZLE, use `$`
again → col 80, then enter EXIT room.

That would make the solution NOT `jj $ kkk ^` = 7 keys, but rather much longer.

**ALTERNATIVELY:** the engine convention "`$` stops at room wall" may mean it stops at the
fog boundary of the current room, and corridors are part of one "room-scoped segment" that
spans ENTRY + corridor + PUZZLE because there are no doors here. If there are no doors,
the fog-of-war is already cleared (or auto-cleared on corridor entry), and `$` scans the full
visible row segment.

But even if `$` on row 4 from col 1 reaches col 81, the player still needs to traverse
the 60-col PUZZLE room. After `$` → (4,81), `kkk` → (1,81). Then `^` on row 1: the blueprint
says the anchor rune `∘` at (1,83) is the only rune on row 1 in EXIT. `^` finds the first
rune → (1,83) = exit.

From (4,81) to (1,83): 3 `k` presses (rows 4→3→2→1) = 3. But wait: EXIT room starts at
col 85 (EXIT is "14c wide, starting at col 85"). If (4,81) is still in PUZZLE and EXIT
interior starts at col 85, then `k k k` from (4,81) doesn't take the player into EXIT row 1
unless EXIT room spans row 1 with no wall there at col 81. The EXIT room is described as
"10r tall" (rows 0-9) while other rooms are 8r tall (rows 1-8). The EXIT room extending to
row 0 and row 9 means row 1 is accessible from the EXIT room interior.

The blueprint says: "Row 1 has no other passable cells to the left of col 83 (only EXIT
interior cols 83–94)." And "Anchor rune at (1,83) so that `^` on row 1 lands exactly on the
exit." But if the player is at (4, 81) — in PUZZLE — and presses `kk k`, they go to (1,81).
Row 1 at col 81 is still in PUZZLE (PUZZLE spans cols 21-80 interior based on the schematic).
From (1,81), `^` on row 1 finds the first rune. If row 1 of PUZZLE has random rune clusters,
`^` would land on the leftmost rune there, NOT at (1,83).

The blueprint says "no row-1 runes" in ENTRY + PUZZLE (see rune placement table: "density
0.15; no void; no row-1 runes"). This means row 1 of PUZZLE is entirely blank floor. Then
`^` from (1,81) finds... no rune in PUZZLE row 1, and `^` is room-scoped so it stays within
PUZZLE. Does it do nothing? Or does it fail? "First rune" with no rune is undefined behavior
— likely no movement.

So from (1,81) the player needs to move right into EXIT room (row 1, col 83). That requires
`ll` (2 presses) + `^` or just `^` if EXIT room row 1 is now in scope. If the player is at
(1,81) and presses `l l` to (1,83), they've used 9 keystrokes total (jj + $ + kkk + ll = 9)
vs stated par = 7.

**The intended solution's arithmetic requires `$` to span from ENTRY through the corridor into
PUZZLE in a single keystroke AND `kkk` to work across the PUZZLE/EXIT room boundary. Both of
these hinge on the definition of "room scope" for these commands.**

If the level is designed so that ENTRY, corridor, and PUZZLE are treated as ONE room (no
dividing walls, just open floor), then `$` and `^` are scoped to this combined region.
But that breaks the "room-scoped" engine convention.

**Arithmetic verdict:**

The blueprint's claimed par = 7 requires:
1. `$` to span across ENTRY+corridor+PUZZLE in one keypress (cross-room `$`)
2. `kkk` to land in EXIT room row 1 at a column still within PUZZLE
3. `^` to find the rune in EXIT room from a position in PUZZLE

None of these is consistent with "room-scoped `$`/`^`" as stated in engine conventions.
The par = 7 is UNVERIFIABLE and likely wrong. The actual par under room-scoped rules is
substantially higher.

Even granting the most charitable interpretation (no walls between rooms = one big room),
let's reverify:
- `jj` from (2,1) → (4,1): 2 keys. ✓
- `$` from (4,1) → (4, 81): 1 key. ✓ (if one big room)
- `kkk` from (4,81) → (1,81): 3 keys. ✓
- `^` from (1,81) → (1,83): 1 key. ✓ (if no other runes on row 1 to the left of 83)

Total = 7. **Under the one-big-room interpretation, par = 7 is correct.**

But does row 1 at col 81 have clear floor with no runes? Blueprint says "no row-1 runes" in
ENTRY + PUZZLE. So yes, row 1 is clear up to EXIT room interior (col 83). `^` at (1,81)
would find the first rune on row 1 in the current scope — and if that scope includes EXIT
(one big room), the first rune is at (1,83). This works.

**Budget check:** ceil(7 × 1.4) = ceil(9.8) = 10. ✓

**Can hjkl-only beat the budget of 10?**
Without `$`: player needs to go right across PUZZLE + corridor. PUZZLE is 60 cols wide
(cols 21-80). From (4,1) to (4,81) = 80 `l` presses. Then `kkk` (3) + `ll` to exit (2) = 85.
Total ≈ 87 >> 10. ✓

**Is `0` forced?** The blueprint claims "`0` is forced by a mandatory U-turn in seed-varying
puzzle layouts." This is the weakest link. "`0` snaps back to the left-side cluster start
after using `$` on the right side." But the intended optimal solution `jj $ kkk ^` does NOT
use `0` at all. The blueprint says `0` forcing is "seed-dependent." 

**This is a FORCEABILITY FAIL for `0`.** The optimal solution uses only `j`, `$`, `k`, `^`.
`0` is taught but not required by the optimal path. The "U-turn sub-puzzle" is described
vaguely and admitted to be "seed-dependent." If `0` is not required to complete the level
within budget in any seed, it is not forced.

Additionally, the stated next-best alternative (hjkl-only ≈ 22 keys >> budget 10) uses the
example path "reach (1, 83) from (4, 81) requires kkkl…l = 3 + 12 = 15 extra keys." 
But 15 extra keys on top of `jj $(1)` = jj + 80l + kkk + ll = 87 keys total, not 22.
The 22-key figure seems to assume `$` is already used for the corridor crossing and only the
EXIT approach uses hjkl. This underestimates the hjkl cost: if `$` is used but `^` is
replaced by `ll` (2 keys), hjkl-only = 2+1+3+12 = 18 keys > 10. ✓ (budget still exceeded)

But `^` is what forces the player right — they could do `jj $ kkk ll` = 8 keys (still > 10?
No, 8 < 10). Wait: `jj`(2) + `$`(1) + `kkk`(3) + `ll`(2) = 8 keystrokes. Budget is 10.
**8 < 10. The player can reach the exit WITHOUT `^` and stay within budget!**

`^` is supposedly required because "without `^`, the player needs `lllllll...` (12 more `l`)
after entering EXIT room row 1 = 4+12 = 16 keys >> 10." But I just showed: `jj $  kkk ll` =
8 keys reaches (1,83) without `^`. The `ll` after `kkk` costs only 2 extra keys (not 12),
because the player arrives at (1,81) after `kkk` from (4,81), and (1,83) is only 2 columns away.

**`^` IS NOT FORCED. The player can bypass it with 2 `l` presses and still be at 8 keys < budget 10.**

This is a critical forceability failure: `^` is skippable. The blueprint's "next-best
alternative" cost of 16 is wrong (the real cost is 8, below budget).

**FORCEABILITY: FAIL** — `^` can be bypassed (8 keys < budget 10). `0` forcing is
seed-dependent with no deterministic guarantee. The stated next-best cost of 16 is incorrect.

### Boss (N/A for Level 1)

---

## Level 2 — The Counting Crypts

### Scope (PASS)

One new mechanic: `[count]motion`. Limit = 3. PASS.

### Linkage (PASS)

Count prefix applies to `hjkl` (L0) and `^$0` (L1) — extensions of already-known commands.
One conceptual layer. PASS.

Note: LEVELS_PLAN.md flagged the OLDER Level 2 for "`[count]` + `x`" linkage issue, but the
revised blueprint has `x` at Level 0. The reviewed blueprint has count-only. PASS.

### Forceability (FAIL)

**Recomputed par independently.**

Grid: 12 rows × 78 cols. Entry (2,2), Exit (2,61). Void wall at col 40 rows 2-9. Doors at
rows 5-6 at cols 19 and 55.

Intended solution (blueprint's corrected version):
`4j`(2) + `x`(1) + `$`(1) + `5k`(2) + `$`(1) + `5j`(2) + `x`(1) + `$`(1) + `4k`(2) + `$`(1) = 14 keys.

Let me verify each step:

From (2,2):
1. `4j` (2 keys): (2,2) → (6,2). Row 6 = corridor row (corridor is rows 5-6; row 5 is top
   corridor, row 6 is bottom). From row 2, 4j → row 6. ✓
2. `x` (1): open door at col 19, rows 5-6. But player is at (6,2), not at the door (6,19).
   The `x` opens the door at the door cell. Player must BE at the door cell to press `x`.
   So player must first move to (6,19). That requires `l` × 17 presses from col 2 to col 19.
   OR can `x` be used from a distance? Engine convention says "doors sealed at room fog
   boundary — `x` opens from the door cell." **Player must be at (6,19) to open the door.**

   So between step 1 and step 2, the player needs 17 `l` presses (or use `$` to reach col 18,
   which is ENTRY right edge, then `l` to col 19 for door). Actually `$` on row 6 within ENTRY
   (cols 1-18 interior) would go to col 18. Then `l` to col 19.

   Blueprint's sequence `4j x $` would require `x` at (6,2) to somehow open a door at (6,19).
   This only works if `x` has an interaction radius, but the engine says "from the door cell."

   **Major defect:** the intended solution omits the navigation steps WITHIN ENTRY to reach
   the door. The sequence as written (`4j x $`) is incorrect — the player must also traverse
   across ENTRY (17+ columns) to reach the door before pressing `x`.

Let me recompute par accounting for this:

Path: (2,2) → need to reach door at (5 or 6, 19) → cross corridor to PUZZLE → go up to row 1
(via row 1 bypass over void wall) → cross PUZZLE → reach door at (5 or 6, 55) → cross to
EXIT → go up to (2,61).

Optimal with count + `$`:

a. `4j` (2): (2,2) → (6,2)
b. `$` (1): (6,2) → (6,18) [ENTRY right interior edge on corridor row, fog stops at col 18
   if door at col 19 is closed and blocks fog] OR does `$` reach col 19 (the door)?
   The blueprint says "`$`/`0`/`^` are room-scoped (stop at room wall)." If the door at col 19
   is a room-wall-equivalent, `$` stops at col 18.
c. `l` (1): → (6,19) [door cell]
d. `x` (1): open door. Fog now reveals corridor col 19-22 and PUZZLE.
e. `$` (1): (6,19) → (6,54) [corridor + PUZZLE right interior, blocked by second door at col 55]
f. `5k` (2): (6,54) → (1,54) [row 6 to row 1; 5 steps]
g. `$` (1): (1,54) → (1,54) → col 55-ish? PUZZLE right wall on row 1 (no door here, row 1
   is above the doors at rows 5-6). Actually PUZZLE interior on row 1 spans cols 23-54 (the
   PUZZLE room is 32 cols wide at cols 23-54). `$` from (1,54) stays at col 54 (already at edge).
   Hmm, or does `$` go further right through the corridor? On row 1, there may be no wall
   between PUZZLE and EXIT room (the wall is only at rows 5-6 for the doors). This is unclear.
   
h. Assume player must navigate to door at col 55 (rows 5-6). Must go back down:
   `5j` (2): (1,54) → (6,54)
i. `l` (1): → (6,55) [second door cell]
j. `x` (1): open second door.
k. `$` (1): (6,55) → (6,60) [EXIT interior right edge? Or (6,77)?]
   If `$` goes to (6,77) (far right of EXIT), that's too far — exit is at (2,61).
l. `4k` (2): (6,77) → (2,77). Then need to go left to (2,61).
   `$` on row 2 in EXIT would go to (2,77). Need to use `0` or `^` or multiple `h`.
   From (2,77) to (2,61) = 16 `h` presses. This doesn't work.

The whole sequence is fundamentally broken because the blueprint's claimed par-14 solution
omits the intra-ENTRY navigation to the door and gives incorrect column positions.

**Re-estimate actual par with correct accounting:**

Truly optimal path with count + `$`:
- (2,2) → (6,2): `4j` = 2
- (6,2) → (6,18): `$` = 1 [stops at ENTRY interior right edge]
- (6,18) → (6,19): `l` = 1 [move to door]
- open door: `x` = 1
- (6,19) → (6,54): `$` = 1 [corridor+PUZZLE, stops at door at col 55]
- (6,54) → (6,55): `l` = 1 [move to second door]  — wait, or does fog block col 55 until
  the second door opens? If the door itself is at col 55, and doors block traversal, `l`
  from col 54 would hit the door. Player needs to open it.
- Wait: can the player be AT the door to open it? `x` opens from the door cell. So `l` moves
  player to door cell (6,55) (doors don't stop movement to the door cell, only THROUGH it).
- `x` = 1 [open second door]
- (6,55) → corridor to EXIT:
  Void wall is at col 40 rows 2-9. We haven't crossed it yet. We went from ENTRY (cols 1-18)
  through corridor (cols 19-22) into PUZZLE (cols 23-54). The void wall at col 40 blocks
  rows 2-9 within PUZZLE. We've been on row 6 (within rows 2-9), so we cannot cross col 40
  directly.
  
  **We must use row 1 (above void range) to cross the void wall.** This means:
  - From (6,54), go UP to row 1: `5k` (2): → (1,54)
  - But we already passed the void wall going right from col 19 to col 54. How? If the
    void wall at col 40 rows 2-9 blocks ALL movement in col 40, then `$` from (6,19) would
    stop at (6,39)! Not reach (6,54).

  **AH — this is the critical error.** The void wall at col 40, rows 2-9 blocks corridor
  traversal. On row 6 (which is in rows 2-9), `$` from col 19 hits the void wall at col 40
  and stops at col 39 (or col 40 is lethal so `$` stops just before it at col 39).

  So the player CANNOT use `$` to cross the void wall at row 6. They MUST go to row 1 or
  row 10 (outside the void range rows 2-9) to cross.

Revised optimal path:
- (2,2) → (6,2): `4j`=2
- (6,2) → (6,18): `$`=1 [ENTRY right edge]
- (6,18) → (6,19): `l`=1 [door]
- `x`=1 [open door]
- (6,19) → (6,39): `$`=1 [stops before void wall at col 40]
- (6,39) → (1,39): `5k`=2 [go up to row 1, above void range]
- (1,39) → (1,54): `$`=1 [PUZZLE right end on row 1 — assuming no wall there]
  Actually on row 1, the void wall doesn't exist (void is rows 2-9). So `$` goes right
  freely to PUZZLE right wall at col 54 on row 1.
- (1,54) → (1,54): no door on row 1 at col 55? Doors are at rows 5-6 only. So on row 1,
  there's no door blocking. Does `$` on row 1 go straight to EXIT? If there's no wall on
  row 1 between PUZZLE and EXIT, `$` could go to col 77 (EXIT far right).
  If EXIT room starts at col 59: `$` from (1,54) → (1,58) [PUZZLE right wall, EXIT starts at 59]
  OR if row 1 is open through: `$` → (1,77).
  
  Assuming row 1 is the bypass route (walls only at rows 5-6 for the doors), `$` on row 1
  goes to col 77. Then player needs to go to exit at (2,61):
- (1,77) → (2,77): `j`=1
- (2,77) → (2,61): `0`=1 [if exit is leftmost rune] or multiple `h` presses.
  `0` would go to col 59 (EXIT left interior edge). Exit is at (2,61) — 2 cols from left.
  `0` then `ll` = 3 keys. Or `16h` = 16 keys.

Actual optimal (rough lower bound):
4j(2) + $(1) + l(1) + x(1) + $(1) + 5k(2) + $(1) + j(1) + [go to exit position]...

This is getting complex. The point is: **par ≠ 14 keys.** The correct par on this grid is
substantially higher because:
1. The intra-ENTRY navigation to the door is omitted (adds 1-2 keys minimum)
2. The void wall forces a row-1 bypass that the blueprint's 14-key sequence ignores

**A realistic minimum is around 18-22 keys**, not 14.

The stated hjkl-only estimate of 26 keys may be close to the count-optimal par, meaning
the budget margin is dangerously thin or inverted.

**FORCEABILITY: FAIL** — par = 14 is incorrect (the stated optimal sequence is malformed
and skips steps needed to operate `x` from the door cell and to bypass the void wall).
The actual par is higher, and the hjkl-only "next-best" of 26 may not exceed the corrected
count budget.

---

## Level 3 — The Rune Halls

### Scope (PASS)

Three mechanics: `w` (next cluster start), `b` (prev cluster start), `e` (cluster end).
These are the word-motion triad — one family. Count = 1 family = 1-3 mechanics. PASS.

### Linkage (PASS)

`w`/`b`/`e` are the complete word-motion family. All operate on rune clusters as "words."
No unrelated commands mixed in. PASS.

### Forceability (PASS with reservation)

**Recomputed par independently.**

Grid: 16 rows × 48 cols. Five 2-row snake corridors. Dense rune clusters (density 0.65).
Entry (1,1). Exit (13,44).

**w/b/e vs. hjkl:**
One 46-col corridor with density 0.65 ≈ 30 rune cells out of 46 = ~10 clusters (if average
cluster width is 3). With `w`: 10 keystrokes. With `l`: 46 keystrokes. Ratio: 4.6×.
Over 5 corridors: w/b ≈ 50 keys vs l ≈ 230 keys. Turns via `2j` = 2 keys (count from L2).

Blueprint's par = 30 seems reasonable for 5 corridors × ~6 keys each.

**Adversarial test — can `$`/`0` replace `w`/`b`?**
The blueprint argues `$`/`0` are insufficient because:
1. Turn rooms have void runes at entry cols, so `$` would stop at the void boundary.
2. Alternate corridors go right-to-left, requiring `b`.
3. Exit is at (13,44) — NOT the row end (void at col 46).

Checking claim 3: exit is at (13,44), void is at (13,46). `$` on row 13 would stop at col 45
(before void at col 46). Exit is at (13,44), 1 cell left of `$`'s landing. So `$` + `h` = 2
keys, while `e` = 1 key. Alternatively, `e` from the anchor rune start at (13,42) lands on
(13,44) = exit. `$` lands at (13,45) = 1 off. So: `$`(1) + `h`(1) = 2 vs `e`(1). `e` saves 1.

**Is `e` strictly forced?** If using `$` + `h` costs 2 and using `e` costs 1, the difference
is 1 key. Budget = 42. If the rest of the level uses `w`/`b` (say 29 keys), then:
- With `e`: total = 30 keys < 42 ✓
- Without `e`, using `$`+`h`: total = 31 keys < 42 ✓

**`e` is NOT strictly forced** — the player can use `$` + `h` and still be within budget (31 < 42).

**Is `b` strictly forced?**
C2 and C4 go right-to-left. `b` traverses right-to-left cluster-by-cluster. Alternative:
use `h` (slow) or `0` (jumps to left edge in 1 key). If the player uses `0` instead of `b`
on C2, they jump from right end to left end in 1 key. Then they only need to descend via
`2j`. This would make C2 cost: `0`(1) + `2j`(2) = 3 keys, vs `b`×10 + `2j`(2) = 12 keys.

**Wait — `0` is much cheaper than `b` for right-to-left corridors!** The blueprint claims
`$`/`0` don't work because "The snake pattern means alternate corridors go right-to-left
(needing `b` to traverse backward over runes)." But `0` in 1 key beats `b`×10 overwhelmingly!

Why would a player use `b` instead of `0` on a right-to-left corridor? They wouldn't, unless
the design forces them to stop at intermediate runes (e.g., to pick up collectibles or
activate runes to open a door). The blueprint does not mention such intermediate stops as
required. The snake layout alone does NOT force `b` over `0`.

**`b` is NOT forced.** On right-to-left corridors, `0` is cheaper (1 key vs 10 keys).
The player can traverse C2 and C4 with `0` (jump left) + turn, saving ~9 keys per corridor.

This also breaks the par calculation. Let's recompute:
- C1 (left→right, ~10 clusters): `w`×10 = 10 keys. But can `$` do it? `$` = 1 key → lands
  at right end (col 46 is void, so `$` → col 45). Need to turn down into RT1. This is faster!
  Use `$`(1) + `2j`(2) = 3 keys for C1 instead of 10 `w` presses.
  
- C2 (right→left, 10 clusters): `0`(1) + `2j`(2) = 3 keys for C2.

- C3, C4: same, 3 keys each.

- C5 (left→right): `$`(1) + `h`(1) = 2 keys (or `e` = 1 key for last position, but `$` to 45
  then `h` to 44 works).

Using `$`/`0` for corridor traversal: (3+3+3+3+2) = 14 keys total.
Using `w`/`b`/`e`: ~30 keys total.

**`$`/`0` are dramatically cheaper than `w`/`b`/`e`** (14 vs 30 keys) AND are within budget 42!

**The level catastrophically fails forceability.** The player can use `$`/`0` (already taught
in L1) to traverse every corridor in 1 key per corridor end, reaching the exit in ~14 keys,
well within budget 42. There is NO need to use `w`/`b`/`e` at all.

The blueprint claims: "`$`/`0` only move to row-ends, not from cluster to cluster in the
required direction. `$` would stop short (blocked by fog at the void boundary) or land you at
the turn-room entrance, not traversing toward exit."

This claim is partially wrong:
- For C1 (left→right): `$` from left end of C1 → col 45 (just before void at 46). Then the
  player needs to enter the turn room. The turn room entry is at col 43-44 (RT1 = rows 2-4,
  cols 43-44). From (1,45), `j` → (2,45). But void at (1,45-46) and (2,45-46). Wait — void
  at cols 45-46 for RT1 blocks (1,45) and (2,45-46). So `$` from (1, col 1) would stop at
  col 44 (void at 45 blocks), not col 45. Then `jj` or `2j` → turn room. Actually:
  "void at (1, 45-46): Block overshoot past RT1 corridor" — so `$` on row 1 stops at col 44.
  From (1,44), `2j` → (3,44) (RT1 spans rows 2-4, cols 43-44). ✓

  But the turn room exit goes into C2 at row 4-5. Does the player now need to traverse C2?
  From (3,44) or (4,44), they want to go left across C2 to reach LT1. `0` from (4,44) → (4,1)
  in 1 key! Then `2j` → (6,1) (LT1). Continue similarly.

  **The `$`/`0` path works perfectly through the snake corridors** — using `$` to jump right
  and `0` to jump left, bypassing the need for `w`/`b`/`e`.

The blueprint's claim that void guards prevent `$`/`0` is incorrect — void guards only prevent
landing ON the void, but `$`/`0` stop BEFORE void cells.

**FORCEABILITY: FAIL** — `$`/`0` from Level 1 provide a drastically cheaper path (~14 keys)
well within budget 42, making `w`/`b`/`e` entirely optional. The key invariant is violated:
the taught command is NOT the cheapest path.

---

## Level 4 — The Character Cataracts

### Scope (PASS with marginal flag)

Six items listed: `f`, `F`, `t`, `T` (find-family = one mechanic family), `;`, `,`
(repeat = one mechanic family). The blueprint counts these as 3 mechanics (f/F/t/T as 1,
`;` as 1, `,` as 1) but groups them into "two related sub-families of one character-find idea."

Per LEVELS_PLAN.md principle 1: "Trivial direction/flavor variants of one idea count as one."
`f` and `F` are direction variants of find (forward/backward). `t` and `T` are direction
variants of till. So: find-variants = 1 mechanic, till-variants = 1 mechanic (arguably
distinct from find by the "stop before" semantics), `;`/`,` = 1 mechanic (repeat). Total = 3.
Limit = 3. PASS.

### Linkage (PASS)

`f`/`F`/`t`/`T`/`;`/`,` are the complete find+repeat family. LEVELS_PLAN.md confirmed this
as a fix (merging `;`,`,` up from the old L5). One coherent family. PASS.

### Forceability (FAIL — as flagged by the designer)

The blueprint itself admits: "`;`/`,` are not strictly forced by the basic budget but are
strongly incentivized." This is a self-declared FAIL for the forceability of `;`/`,`.

**Independent verification of `;`/`,` forcing:**

From the blueprint's arithmetic:
- C4 with fresh `T!` costs 2 keys; with `,` costs 1 key. Difference = 1 key.
- Budget margin: 38 - 27 = 11 keys of slack.

If both `;` and `,` each save 1 key, total savings = 2 keys. 27 + 2 = 29 < 38 (within budget
without using `;`/`,`). So the player can solve the level WITHOUT `;`/`,` and stay at 29 keys
< budget 38. `;`/`,` are firmly NOT forced.

The blueprint acknowledges this and proposes a workaround: "in C5 (the exit corridor), the `e`
anchor is accessible only after using `;` to find the `◦` target char within the rune field."
But earlier C5 is described as a "w/b/e rune field" traversed by `w`×N + `e`. This proposal
contradicts the level design described in the grid section.

**`f`/`F`/`t`/`T` forcing (main family):**
Water pools physically block hjkl/w/b/e. Without find commands, the level is unsolvable.
**This is correct and genuine — water makes f/F/t/T strictly required.**

But note: the `$`/`0` forceability problem from Level 3 resurfaces. Can `$` scan through water?
The blueprint says "`$` stops at room wall" and water is floor-level. `$` does NOT scan through
water — it stops at the water's edge (water cells are blocking for hjkl and `$`). So `$`
cannot cross the water pools. `f`/`F`/`t`/`T` CAN scan through water. This is the genuine
distinction. ✓

**`t` vs `f` forcing:**
Dynamite at (7,70): `f!` lands on dynamite = death; `t!` stops at col 69 = safe. This
genuinely forces knowing the difference. ✓ Dynamite at (10-11,1): `F!` lands on dynamite;
`T!` stops at col 2. ✓

**Is the `t` vs `f` distinction sufficient or is death by dynamite too punishing?**
Gameplay concern (not a principle violation per se): if the player doesn't know `t` vs `f`,
they die to dynamite. This is a strong forcing mechanic — perhaps too abrupt for a teaching
level. But the principle only requires forceability, not gentleness. PASS on this point.

**Claimed par = 27, budget = 38.**

Recompute per-corridor minimum (charitable interpretation where `;`/`,` are used):
- C1: `fr`(2) + turn: `jj`(2) + descent: `2j`(2) = ... wait.

The blueprint says turns use `jj 2j`. But why `jj` AND `2j`? Looking at turn rooms: RT1 spans
rows 2-4, so from C1 (row 2) into RT1 and down to C2 (row 4) = `jj` (2 rows). But blueprint
shows connectors as (3) keys. Let me recount: from C1 row 1 → RT1 (2,3) → C2 row 4 = `jjj`
(3 steps) = 3 keys. So connector = 3. ✓

Per-corridor:
- C1: `fr`(2) + `jjj`(3) = 5
- C2: `Fw`(2) + `jjj`(3) = 5  
- C3: `t!`(2) + `jjj`(3) = 5
- C4: `,`(1) + `jjj`(3) = 4  [reuses C3's `!` find via `,` = `T!`]
- C5: w-traverse + `e`. Blueprint says ≈8. Accept as 8.

Total = 5+5+5+4+8 = 27. ✓

**Without `;`/`,`:**
- C4: `T!`(2) + `jjj`(3) = 5 instead of 4.
- Total = 5+5+5+5+8 = 28 < 38. WITHIN BUDGET.

**`;`/`,` are not forced.** Confirmed FAIL.

**Could the budget be tightened to force them?**
If budget = ceil(27 × 1.4) = 38, and the non-`;`,`-path costs 29, we need budget < 29 to
force them. That means par must be reduced so that ceil(par × 1.4) < 29, i.e. par < 20.7.
But par = 27 with `;`/`,`. So the budget structure doesn't work — par WITH `;`/`,` (27) is
too close to cost WITHOUT them (29) relative to the 1.4× multiplier.

To force `;`/`,`, the designer needs either:
(a) More `;`/`,` opportunities that save enough keys cumulatively, OR
(b) A mandatory `;`-chain mechanic (e.g., a locked door that only opens after 3 consecutive
    `;` presses activating rune triggers).

**FORCEABILITY: FAIL** — `;`/`,` can be bypassed (28 keys < budget 38). The main
`f`/`F`/`t`/`T` family IS genuinely forced by water impassability.

### Boss (N/A for Level 4)

---

## Level 4.1 — The Warden's Keep (ACT I BOSS)

### Scope (PASS)

No new mechanics taught. Boss caps Act I commands. PASS.

### Linkage (PASS)

Each phase exercises one Act I command family. Families are internally coherent. PASS.

### Forceability (PARTIAL FAIL)

**Phase-by-phase analysis:**

**Phase 0 (x):** `x` opens seal_door. Without `x`, door stays closed, player cannot reach
boss. Trivially forced. PASS.

**Phase 1 (hjkl):** Stone column maze in entry corridor. Player must navigate around columns.
No shortcut without basic movement. PASS.

**Phase 2 ($0):** Shield swaps sides after each warden hit. `$` in 1 key vs up to 25 `h`/`l`.
Without `$`/`0`: 4 repositionings × ~12 keys each = 48 extra >> budget. PASS.

**Phase 3 ([count]):** Goblins spawn 4-9 cells away. `5j`(2) vs `jjjjj`(5). With 4 goblins:
count saves 4×3=12 keys minimum. Without count: 4×9=36 keys vs 4×2=8 keys = 28 extra. PASS.

**Phase 4 (w/e):** Boss room fills with rune clusters. `w`×n faster than `l`×n.
**But wait — this faces the same problem as Level 3.** Can the player use `$` to reach the
warden in 1 key instead of multiple `w` presses?

In Phase 4, the warden retreats to the far end (col ~37 of a 44-col room). Player is at
col ~16. `$` from player → col 37 (right end, before boss_seal) = 1 key.
`w`×n across rune field = multiple keys.

**`$` is strictly cheaper than `w` here.** The same bug as Level 3: `$` makes `w` optional.

If the blueprint expects `w` to close distance in Phase 4, but `$` (taught in L1) does it
in 1 key, Phase 4 does not force `w`. This is a forceability FAIL for Phase 4.

**Phase 5 (fg;):** `fg` finds goblin at 'g' character. `;x` chains kills. Without `;`:
`fg x` per goblin (3 keys) vs `fg` + `;x`×(n-1) (2+2n-2 = 2n keys for n goblins).
For 3 goblins: without `;` = 9, with `;` = 6. Difference = 3.

But the budget question: does using `fg x` (without `;`) blow the budget?
Budget = ceil(63 × 1.4) = 89. If the 3-goblin chain costs 9 vs 6, total = 63+3 = 66 < 89.
Still within budget. **`;` is not forced by budget in Phase 5.**

However, if the summon chain is longer (e.g., 5 goblins): without `;` = 15 keys extra, with
`;` = 10 keys extra. Difference = 5. Still within the generous 26-key budget slack.

**FORCEABILITY: FAIL** — Phase 4 (`w`/`e`) is bypassed by `$` (taught in L1); Phase 5 (`;`)
is not budget-forced given the 26-key slack. Phase 0-3 are legitimately forced.

### Boss Placement (PASS)

Level 4.1: `x.1` numbering ✓. Caps Act I ✓. One boss for the act ✓. Each phase maps to one
command family ✓. PASS.

---

## Summary of Findings

### Fails by Level

| Level | Principle | Finding |
|---|---|---|
| 0 | Forceability | Par = 18 inconsistent with grid dimensions (corridor ≈40 cols → par ≈47-50) |
| 1 | Linkage | `^$0` + `:w/:q/:q!` are distinct families |
| 1 | Forceability | `^` bypassed by `ll` (8 keys < budget 10); `0` not deterministically forced |
| 2 | Forceability | Par = 14 incorrect (sequence omits door-approach steps and void-wall bypass) |
| 3 | Forceability | `$`/`0` (taught L1) give ~14 key solution << budget 42; `w`/`b`/`e` not forced |
| 4 | Forceability | `;`/`,` not forced (bypass costs 28 < budget 38); confirmed by designer |
| 4.1 | Forceability | Phase 4: `$` (L1) beats `w`; Phase 5: `;` not budget-forced |

---

## Per-Level Verdicts

### Level 0

**SCOPE: PASS** — 3 mechanics (hjkl, x, :wq). Directions count as one.
**LINKAGE: PASS** — move/interact/exit is one entry-ritual family.
**FORCEABILITY: FAIL**
- Recomputed par: corridor ≈ 40+ cols → BFS min ≈ 47-50 steps, NOT 18.
- Budget of 26 would be BELOW par on the described 52-col grid.
- If par ≈ 48, budget should be ceil(48 × 1.4) = 68, not 26.
- Fix required: EITHER (a) shrink the grid so the corridor is ~10 cells wide (achieves par
  ≈18) OR (b) recompute par on the actual generated grid and update budget = ceil(par × 1.4).
  The grid description and par must be consistent.

**BOSS: N/A**

### Level 1

**SCOPE: PASS** — `^$0` family + exit ritual (UI-prompted, not puzzle-gated = 0 extra scope).
**LINKAGE: FAIL**
- `^$0` are positional motion keys; `:w/:q/:q!` are command-mode file operations.
- These are distinct families even if framed as "extending the Level 0 exit ritual."
- Fix: Demote `:w/:q/:q!` to pure UI prompts not described as "new mechanics," OR give them
  a separate level. LEVELS_PLAN.md §2 already endorses this split.

**FORCEABILITY: FAIL**
- `^` is bypassable: `jj $ kkk ll` = 8 keys < budget 10 reaches exit without `^`.
- Stated next-best cost of 16 is wrong; true cost without `^` is 8.
- `0` is not deterministically forced (seed-dependent U-turn sub-puzzle).
- Fix: Move exit to (1, exit_col+N) where N is large enough that `kkk` leaves the player
  far enough that `ll`...`l` > budget. Specifically: the player after `jj $ kkk` must be at
  a column such that hjkl-only to exit costs > (budget − 6). With budget 10 and 6 keys used,
  remaining = 4. Place exit so hjkl approach requires ≥5 keys without `^`. Alternatively,
  tighten budget to 8 (so `jj $ kkk ll` = 8 is exactly at budget, and any error fails).
  Better fix: require `0` by placing a mandatory rune collection on the PUZZLE's left side
  that the player must visit before proceeding to EXIT.

**BOSS: N/A**

### Level 2

**SCOPE: PASS** — 1 mechanic (count prefix).
**LINKAGE: PASS** — count applies to known motions.
**FORCEABILITY: FAIL**
- Claimed par = 14 keys. The sequence as written is malformed: `4j x $` requires the player
  to already be at the door to press `x`, but the door is 17 cols away from the starting column.
- Void wall at col 40 (rows 2-9) means `$` on corridor row 6 stops at col 39, not col 54.
  Player must use row-1 bypass, adding steps the blueprint ignores.
- Revised realistic par: ~20-24 keys.
- Fix: Recompute par by running the actual Dijkstra solver on the grid. Update the blueprint's
  step-by-step sequence to account for (a) intra-room navigation to door cells and (b) the
  void wall bypass via row 1. The budget should be ceil(actual_par × 1.4).

**BOSS: N/A**

### Level 3

**SCOPE: PASS** — 3 mechanics (w, b, e) as one word-motion family.
**LINKAGE: PASS** — w/b/e are the complete word-motion triad.
**FORCEABILITY: FAIL — CRITICAL**
- `$`/`0` (taught Level 1) yield a ~14-key solution by jumping to corridor ends, well within
  budget 42.
- `$` stops before void guards but still reaches the turn-room entry column.
- `0` on right-to-left corridors (C2, C4) is dramatically cheaper than `b` (1 key vs 10 keys).
- This makes `w`/`b`/`e` strictly unnecessary.
- Fix: The fix must make `$`/`0` unable to traverse the snake corridors. Options:
  (a) Place void runes at BOTH ends of each corridor row (not just the overshoot end), so
      `$` stops in the middle of the corridor rather than at the far end. The player must
      then use `w` to hop over individual runes to reach the turn-room entrance.
  (b) Make the corridor ends sealed (no direct jump to far end) by placing a wall/door at
      the turn-room threshold, requiring the player to be at a specific rune cell to open it.
  (c) Require intermediate rune collection: each corridor has N mandatory activation runes
      that must be visited (stepped on); `w`/`b` is the only way to visit them all within
      budget since `$`/`0` skip them.

**BOSS: N/A**

### Level 4

**SCOPE: PASS** — f/F/t/T (find family) + ;/, (repeat family) = 2-3 mechanics, one combined family.
**LINKAGE: PASS** — all six are the find+repeat family.
**FORCEABILITY: FAIL (partial)**
- f/F/t/T: GENUINELY FORCED by water impassability. ✓
- t vs f distinction: GENUINELY FORCED by dynamite. ✓
- `;`/`,`: NOT FORCED. Skipping them costs 28 keys < budget 38. Designer-acknowledged.
- Fix for `;`/`,`: Add a mandatory `;`-chain sub-puzzle. Proposed: in C5, the exit anchor
  is locked behind a keystone that requires the player to find the same character THREE times
  consecutively using `;` (the keystone only activates on the 3rd consecutive same-char find).
  This makes `;` required by logic, not just budget. OR: extend the water pools so that
  the player must make 4+ finds of the same character in sequence — then `;` saves enough
  keys (4+ keys vs 4×2 = 8 keys) to push the no-`;` cost above budget.

**BOSS: N/A**

### Level 4.1 — The Warden's Keep

**SCOPE: PASS** — no new mechanics.
**LINKAGE: PASS** — each phase maps to one Act I family.
**FORCEABILITY: FAIL (partial)**
- Phases 0-3: PASS (genuinely forced).
- Phase 4 (`w`/`e`): FAIL — `$` from L1 jumps to the warden's side in 1 key, bypassing
  the need for `w`×n cluster-hopping. Fix: place void runes at the boss-room far end so that
  `$` stops before the warden's position, requiring the player to land exactly on the warden's
  cell using `e` (which lands on a cluster's last cell = warden position) or `w` (hops past
  the penultimate cluster into warden's cluster). Alternatively, make the warden immune to
  damage unless the player arrived via a rune cluster (flavor: "warden shielded except from
  rune energy footstep").
- Phase 5 (`;`): FAIL — `;` saves 3 keys on a 3-goblin chain; 26-key budget slack absorbs
  this. Fix: increase goblin chain to 6-8 goblins so that `;` saves 10+ keys, making non-`;`
  path exceed budget.

**BOSS PLACEMENT: PASS** — 4.1 numbering, caps Act I, correct structure.

---

## Overall Act Verdict

**ACT I: FAIL**

Total FAIL count across principles:
- Level 0: 1 FAIL (Forceability)
- Level 1: 2 FAILs (Linkage, Forceability)
- Level 2: 1 FAIL (Forceability)
- Level 3: 1 FAIL (Forceability — CRITICAL)
- Level 4: 1 FAIL (Forceability — partial, for `;`/`,`)
- Level 4.1: 1 FAIL (Forceability — partial, Phases 4 and 5)

**Total: 7 principle FAILs across 6 levels/boss.**

The most severe systemic issue is that `$`/`0` (taught in Level 1) are never blocked from
providing optimal or near-optimal paths in Levels 3 and 4.1's Phase 4. Once a powerful
navigation shortcut is taught, all subsequent levels must actively prevent it from being the
cheapest solution to their new mechanic.

---

## Prioritized Fix List

### Priority 1 — CRITICAL (level is broken / new mechanic not required)

1. **Level 3 — `$`/`0` bypass.** `w`/`b`/`e` not forced. Fix: void runes at BOTH ends of
   each corridor row (not just the overshoot end) so `$`/`0` stop mid-corridor, forcing the
   player to use `w`/`b` to cross cluster-by-cluster. Specifically: place void at col 2
   (left end of C1, C3, C5) and col 45 (right end) so `$` from col 3 stops at col 44, `0`
   from col 44 stops at col 3. The player must use `w`/`b` to traverse the 40 cells between
   void guards. This also eliminates the `0`-as-free-right-to-left shortcut.

2. **Level 1 — `^` bypass.** `jj $ kkk ll` = 8 keys < budget 10 skips `^`. Fix: Move the
   exit 3+ additional columns right of where `kkk` lands the player, so that hjkl-only
   approach after `$`+`kkk` costs ≥5 keys, pushing total to ≥11 > budget 10. Specifically:
   place exit at (1, 86) (not col 83), ensure no runes on row 1 left of col 86, and place
   anchor rune `∘` at (1,86). Then `jj $ kkk ^` = 7 keys; `jj $ kkk llll` = 10 keys = budget
   (ties, doesn't fail); `jj $ kkk lllll` = 11 > 10. Budget must be 9 to force `^` strictly.
   Alternative: tighten budget to ceil(7 × 1.25) = 9, so `jj $ kkk ll` = 8 < 9 barely makes
   it, BUT any additional key (error or extra move) fails. Better: tighten budget to 8 and
   require `^` to reach (1,86) so `jj $ kkk ^` = 7 < 8 ✓ but `jj $ kkk ll` = 8 = budget (tie).
   Truly force: budget = 7 (exact par), no slack. Risky for L1 pedagogically. 
   BETTER FIX: keep budget 10, but add a 5-column blank gap between `kkk` landing and exit,
   so hjkl approach = 5 keys → total 11 > budget. Force `^` to bridge this gap in 1 key.

3. **Level 0 — Par inconsistency.** Grid says 52 cols with a 40-col corridor; par says 18.
   Impossible. Fix: Run `_bfs_par` on the actual generated grid (not the schematic) for a
   set of seeds and use the median as stated par. Update budget = ceil(par × 1.4). OR shrink
   the Level 0 grid to ~20 cols wide (3-col room + 2-col corridor + 3-col room) so par is
   genuinely ≈18.

### Priority 2 — HIGH (teaching intent undermined)

4. **Level 2 — Par sequence malformed.** The optimal-solution steps are wrong (don't account
   for navigating to door cell, and ignore void-wall bypass requirements). Fix: Rewrite the
   step-by-step sequence correctly and re-run Dijkstra. Update par and budget.

5. **Level 4 — `;`/`,` not forced.** Fix: Add a keystone sub-puzzle in C5 that requires 3+
   consecutive `;` activations (each `;` lights a rune; all 3 must be lit to open the exit
   door). Alternatively, double the number of corridors (add C6 and C7) using only `!`
   targets so that `,` and `;` are each used 3+ times, accumulating a 6-key saving that
   pushes no-repeat-cost above budget.

6. **Level 4.1 Phase 4 — `$` bypasses `w`.** Fix: Void rune at boss room far end (col 35)
   so `$` stops before warden at col 36; warden is at col 37 on a rune cluster so `e` or `w`
   is required to land precisely. Set the warden at the last cell of a rune cluster — then
   `w` to cluster start + `e` to cluster end = warden cell; `$` lands at void boundary (col 36).

### Priority 3 — MEDIUM (principle violation, pedagogically fixable)

7. **Level 1 — Linkage (`:w/:q/:q!`).** Fix: Remove them from the "new mechanics" list and
   demote to pure UI prompt text in the exit-tile overlay, not a learnable command. They
   appear naturally and are self-explanatory; they don't need to count as a mechanic family.

8. **Level 4.1 Phase 5 — `;` not budget-forced.** Fix: Increase goblin summon chain to 6
   goblins. Without `;`: 6 × `fg x`(3) = 18 keys; with `;`: `fg x` + 5×`;x`(2) = 13 keys.
   Savings = 5 keys. If combat base cost rises proportionally, the budget slack tightens to
   where `;` becomes required. OR: reduce Phase 5 budget component, e.g., impose a separate
   phase time-limit (goblins expire after N turns, forcing speed).
