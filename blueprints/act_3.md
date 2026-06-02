# Act III — Navigation Power Tools: Blueprints

> ⚠ **Pre-implementation design doc — obsolete conventions; delete-on-implement.** Uses pre-slug naming (e.g. `RuneCluster` → now `CharRun`; level numbers are now the cosmetic `display` field) — don't copy these symbols. **Delete a level's section when that level ships, and the whole file once its act is built.** See LEVELS_PLAN Part 8.

Levels 17, 17.1. Each level introduces at most 3 linked mechanics, budget-forces or
contextually teaches them, and is buildable from existing engine primitives (with
clearly flagged assumed extensions).

> **Shipped — sections removed (delete-on-implement):** L10 The Bracket Vaults,
> L15 The Seekers' Labyrinth, L16 The Waypoint Sanctum. Remaining below: L17, L17.1.

Revision applied: S1 terrain-∞ first, S2 tight budget fallback (document multiplier),
S3 recompute par (true full solution), S4 block earlier commands. All review defects
D1–D12 addressed.

---

## Level 17 — The Archivist's Library

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

**`:e` scope guard (D8 fix):** `:e <name>` within L17 is restricted to the names
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

**CHALLENGE C-L17-1:** `:e {name}<Enter>` dispatch in command mode — maps name to
`build_dungeon_N()` or stub room builder. The engine has `:wq` / `:q` dispatch
(`engine/modes.py` or `main.py`); `:e` must be added. Requires a dungeon-name registry.

**CHALLENGE C-L17-2:** `:set number<Enter>` — toggles `player.options['number']`; renderer
checks this flag to show HP. `player.options` dict + `:set` parser needed. Neither exists.

**CHALLENGE C-L17-3:** Return-to-library mechanic — `:q` in a nested room (INDEX or stub)
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

## Level 17.1 — The Warden Pathfinder (ACT III BOSS)

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

**CHALLENGE C-L17-1-Boss (critical, same root cause as C-L16-1):** Count-move compression
eliminates the mark-forcing advantage in Phase 3. The arena detour (15 cells) costs `15l`
= 3 keys. The mark-jump costs 2+1 = 3 keys. Essentially the same cost.

**Resolution: forbid count-prefix in the NE Chamber during Phase 3** (extend C-L16-2 to
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

**CHALLENGE C-L17-2-Boss:** The mirror-trap reflected damage requires that `x` on a
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

**CHALLENGE C-L17-1-Boss:** Count-move compression threatens mark-forcing in Phase 3.
Resolved by 30-cell winding corridor (terrain forcing). No engine change required for
THIS fix, but the winding corridor must be physically laid out in the room builder.

**CHALLENGE C-L17-2-Boss:** Mirror trap (`x` on HP=0 entity → player -1 HP). Requires
new engine behavior: `x` dispatch checks if target entity HP ≤ 0; if so, applies damage
to player and activates REFLECTOR effect. Must be implemented before Phase 4 runs.

**CHALLENGE C-L17-3-Boss (existing):** Warden immunity flag `warden_phase_immune: set[str]`
on Entity — motion dispatch checks before applying Act II motions. Already flagged in
original blueprint; unchanged.

**CHALLENGE C-L17-4-Boss:** All engine extensions from L10-L17 (`%`, last_search, n/N,
marks, `:e`, `:set`) must be implemented before this boss level runs. The boss depends on
all of them.

---

### Self-check

- (1) Scope: Boss uses all Act III mechanics. Acceptable for a boss level. Pass.
- (2) Linkage: Each phase maps 1:1 to an Act III teaching level. Pass.
- (3) Forced:
  - Phase 1: void-gap forcing. Pass.
  - Phase 2: decoy-fog forcing. Pass (D11 clarified — `:set` not needed in P2).
  - Phase 3: winding detour + mark-jump (D9 redesign). Pass pending C-L17-1-Boss
    (winding corridor must be built).
  - Phase 4: mirror-trap forcing (D10 redesign). Pass pending C-L17-2-Boss.
- (4) Boss: caps Act III at 17.1. Well-spaced after 13.1. Pass.

---

---

## Engine Extensions Summary (Act III) — Revised

All extensions below must be implemented before Act III runs, ordered by dependency:

| Extension | Required by | Status | Notes |
|-----------|------------|--------|-------|
| `%` motion in `engine/motion.py` | L10, Boss P1, Boss Final | CHALLENGE C-L10-1 | Scan row for bracket glyph under cursor; jump to pair. Brackets: `[](){}` in RuneCluster. |
| `player.last_search` (pattern + direction) | L15, Boss P2 | CHALLENGE C-L15-2 | Store after `/` or `?`. Used by `n`/`N`. |
| `n`/`N` dispatch | L15, Boss P2 | CHALLENGE C-L15-2 | `find_next()` with stored pattern/direction. |
| `/pattern` avatar teleport | L15, Boss P2 | CHALLENGE C-L15-1 | Critical: player avatar moves to match cell, not just cursor. Human decision required. |
| Fog reveal on teleport | L15 | CHALLENGE C-L15-3 | Fog clears when avatar position changes. Likely free if fog tied to `player.row/col`. |
| `player.marks` dict | L16, Boss P3 | CHALLENGE C-L16-2 | `{char: (row,col)}`. `m{a-z}` sets; `` `{a} `` and `'{a}` jump. |
| `` `a ``/`'a` dispatch | L16, Boss P3 | CHALLENGE C-L16-2 | `` `a `` → exact (row,col); `'a` → first non-blank of marked row. |
| Budget multiplier ×1.03 for L16 | L16 | CHALLENGE C-L16-3 | Near-zero slack; human must accept or redesign topology. |
| Count-prefix forcing gap | L16 | CHALLENGE C-L16-1 | Count-move compression collapses mark budget advantage. Human decision required. |
| `:e {name}` command dispatch | L17, Boss P4 | CHALLENGE C-L17-1 | Name→builder registry. Add to command-mode parser. |
| `:set {option}` command | L17, Boss P4 | CHALLENGE C-L17-2 | `player.options` dict + renderer HP branch. |
| Room-stack / return-to-library | L17 | CHALLENGE C-L17-3 | `:q` in nested room restores prior room state + sets flags. |
| Mirror trap (x on dead entity → player damage) | Boss P4 | CHALLENGE C-L17-2-Boss | New engine behavior on `x` dispatch. |
| Winding corridor (30-cell) in NE Chamber | Boss P3 | CHALLENGE C-L17-1-Boss | Must be laid out in room builder; no engine change, just map design. |
| Warden immunity flag | Boss | CHALLENGE C-L17-3-Boss | `warden_phase_immune: set[str]` on Entity; checked in motion dispatch. |
| Mark-aware par solver (or hardcoded par) | L16 | CHALLENGE C-L16-3 | Dijkstra state includes frozenset of mark positions, or hardcode par=49. |
