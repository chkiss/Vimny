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

## Level 17 — The Archivist's Library  (REDESIGN 2026-06-02)

> Supersedes the prior INDEX/passphrase design (which re-taught `:set number` —
> now owned by L16 Waypoint Sanctum — and required a nested-room subsystem that
> collides with `:q`=exit-to-overworld). New design below, decided with the user.

**Commands taught:** `:set wrap` · `:e` / `:e!` (reload) · `:w {name}` (save-as)
**Rewards (scrolls, from finale chests):** `gj` / `gk` · `:e {name}`

**Teaching mode: CONTEXTUAL — ×2.0 budget.**
Theme: the command-line `:` family AS file operations. The whole level is a single
buffer you read with `wrap`, reload with `:e!`, and snapshot with `:w {name}`.

---

### The buffer model — ONE logical line (drives everything)

The entire level is a **1-row × ~1000-col room with no walls.** Consequences:

- **`nowrap` is free.** The renderer already centres a horizontal viewport on the
  player (`render/renderer.py` `vc_start`), so the opening "ribbon" needs no new
  rendering — `l`/`w`/`$`/`fA` scroll the Archivist into view.
- **`j`/`k` are honest no-ops** — moving *by line* on a one-line buffer goes nowhere,
  exactly as real Vim behaves. No special-casing; a one-time hint on first press:
  *"This library is one long line — j/k move between lines, and there's only one."*
- **Horizontal motions carry you down the page.** Past a wrap column, `l` lands on the
  next *display* row (it's one continuous line). The player traverses the wrapped
  manuscript with `l`/`w`/`$`/`f`/marks/search — the hard way — until the finale hands
  over `gj`/`gk`.
- **Motion/collision engine is untouched** — it stays a wide 1×N room; only the *view*
  wraps.

---

### `:set wrap` — the centrepiece

`:set wrap<CR>` flips render mode: the long line flows into a viewport-width block, the
`├ └ │ ─` tree snaps into aligned columns, and the **Archivist (`A`)** appears on
screen. `:set nowrap` reverts to the ribbon.

- **Parsing** is nearly free — `engine/options.py` already has `parse_modifier` for
  boolean options (handles `wrap`/`nowrap`/`invwrap`/`wrap?`). Add a `Player.wrap`
  field; this level sets it `False` at entry (the only level that opens `nowrap`).
- **Rendering** is the real work: lay row 0's columns across screen rows of width `W`;
  map cursor at logical col *c* → display `(c // W, c % W)`; same for the Archivist.
  When the block is taller than the viewport, **scroll vertically BY DISPLAY LINE,
  centred on the cursor** (standard Vim wrap behaviour).
- *Detail:* with `:set number` on, Vim numbers only the first display row of a wrapped
  line and blanks the continuations — mirror that. (Number stays off here.)

---

### The reload loop — `:e` → `E37` → `:e!`, and `:w {suit}`

The Archivist edits the buffer **live, in front of the player**, so the buffer is
*perpetually modified*. The loop:

1. The file keeps changing under the player → **`W11: Warning: File "library" has
   changed since editing started`** flickers in the status bar (the nudge to reload).
2. Player reaches for **`:e`** → blocked: **`E37: No write since last change (add ! to
   override)`** — *already emitted by this codebase* (`main.py:1767`). The teaching beat.
3. **`:e!`** force-reloads to the **next manuscript** in the sequence; echoes the read
   message `"library" 1L, 412B`.
4. Player **reads which suit** the current manuscript is (drenched in that suit's glyph,
   named in the wrapped tree) and files a *named copy*: **`:w hearts`** /
   `:w diamonds` / `:w spades` / `:w clubs`. Echo `"hearts" [New] 1L, 412B written`.
   **No correctness check** — `:w {name}` writes whatever is in the buffer, exactly as
   real Vim does. The reckoning is deferred to assembly.
5. `:w {name}` does **not** clear the modified flag (it's a copy), so plain `:e` still
   hits E37 → the player keeps using `:e!` to advance.

---

### The sequence (deterministic cadence, seed-shuffled suits)

`:e!` walks a fixed-length **cycle** with cadence `suit, non, non, suit, non, non,
non, suit, …` that **loops**, so a missed suit comes back around (forgiving on
navigation). The four suits are assigned to the suit-slots in **seed-randomised order**;
the *positions* of suit vs. decoy are fixed. Decoys = corrupted noise pages or **`~`
empty-buffer pages** (Vim's own end-of-file glyph). On the post-death fresh `:e`
restart the seed reshuffles, so the order can't be memorised — you must read.

---

### The reckoning — forge a folio, the Archivist kills you

There is **no save-time feedback** (faithful: `:w hearts` confirms the *write*, never
the *content*). The four-quadrant library is assembled from **whatever you actually
saved** under each name:

- Correct → that suit's clean folio fills its quadrant.
- Wrong (misnamed, or a decoy/`~` filed under a suit) → the bogus characters sit
  visibly in that quadrant. You *see* your forgery assembled.

**Commit point:** filing is free (re-`:w hearts` overwrites; last write wins). Assembly
triggers only when the player **presents the set to the Archivist** (bump him) after all
four suit-files exist — the deliberate moment of truth, so a careful player can
self-correct before committing.

**Verdict:**
- **Any forgery → the Archivist turns hostile** — *"So YOU'RE the pest who's been
  mangling my folios!"* — and lands a **lethal hit** (`take_damage` ≥ `player.max_hp`,
  guaranteed kill even with heart-container upgrades). This routes straight into the
  **existing** death convention: `** GAME OVER ** Type :e to re-load the dungeon.`
  (`main.py:1733`) → `:e` rebuilds the level **fresh with a new seed** (`main.py:1833`).
  **Full restart, no redo.** No new combat system: it's a scripted lethal `take_damage`
  at the assembly bump, not a ranged-projectile mechanic.
- **Clean assembly (all four correct) → the combined library reveal** + two
  `chest_scroll` entities.

---

### Finale — combined library + two reward chests

The buffer transforms into a serene wrapped four-quadrant library (`♥ ♦` / `♠ ♣`):

- **Chest 1 → `gj` / `gk`** — display-line motion. On this 1-row buffer, `gj` = `col +
  W`, `gk` = `col − W` (clamped). Thematic payoff: having tamed the wrapped library,
  you learn to *walk its display lines*.
- **Chest 2 → `:e {name}`** — open a buffer *by name* (the escalation from the bare `:e`
  you used all level; unlocks the token for future use).

`:wq` completes the level. Rewards are scroll tokens (like `setnum`), granted only after
a clean assembly — so the combat verdict gates them.

---

### Par / budget

This is a **command-loop level, not a path level** — the standard Dijkstra `_par_<slug>`
solver does not apply. Par is bespoke: `:set wrap` (1) + `:e!` × (cycle steps to surface
all 4 suits, ~7–10) + `:w {suit}` × 4 + the present-to-Archivist bump + minimal reading
navigation. Rough par ≈ 90–120 keystrokes; **budget = ceil(par × 2.0)**. The test
asserts the loop is *completable* within budget and that all four `:w`s are *necessary*
(can't assemble cleanly without them) — not a path cost.

---

### Engine change-list (system PR — slice riskiest-first)

**CHALLENGE C-L17-1 — `:set wrap` rendering (the risk; prove it alone first):**
`Player.wrap` field; `apply_set` adds `wrap`/`nowrap`/`invwrap`; renderer wraps a 1-row
room across screen rows + vertical display-line scroll + cursor/entity coord mapping.

**CHALLENGE C-L17-2 — reload loop:** per-level sequence + cadence + seed-shuffle +
pointer + filed-suit set; `:e`→E37 (reuse existing message), `:e!`→advance+reload+read
message, W11 nudge; `:w {name}` save-as (pure buffer→file write, no validation).

**CHALLENGE C-L17-3 — Archivist NPC:** new `npc` entity kind (non-combat) with a
dialogue state machine (pre-wrap panic → post-wrap quest brief → live tidying animation
on each `:e!` → assembly verdict) and a **hostile state** that fires the scripted lethal
hit on a forged commit. Tidying animation rides the existing real-time tick; functionally
stubbable as an instant swap for MVP.

**CHALLENGE C-L17-4 — finale + rewards:** combined-library layout assembled *from the
saved files*; two `chest_scroll`s; reward scrolls in `content/scrolls.py` granting
`gj`/`gk` + `:e {name}` tokens; `gj`/`gk` motion impl (col ± W).

**Bookkeeping:** `content/levels.py` L17 `commands`/`teaches`; `content/scrolls.py`
(two reward scrolls); `render/vim_commands.md` (hint tokens); regen
`content/_gen_curriculum_table.py`; new `tests/test_archivists_library.py`.

---

### Faithfulness self-check

| Element | Real Vim | ✓ |
|---|---|---|
| ribbon → block on `:set wrap` | `nowrap`/`wrap` | ✓ |
| `j`/`k` go nowhere | line-motion on a 1-line buffer | ✓ |
| `gj`/`gk` move by display row | exactly their purpose | ✓ |
| `:e` blocked → `:e!` | `E37`, force-reload | ✓ (msg already in code) |
| "edited under you" nudge | `W11` | ✓ |
| `:w hearts` files a copy, no validation, stays modified | `:w {file}` save-as | ✓ |
| reload echo `"library" 1L, NNNB` | read message | ✓ |

---

### Deferred / minor

- **Terminal resize mid-level** re-wraps cosmetically (tree alignment assumes entry-time
  width) — acceptable; punt.
- Exact decoy glyphs and folio text — author during build.
- Optional faithful micro-beat: `:w` onto an existing name → `E13: File exists (add ! to
  override)` teaching `:w!` — probably too fiddly; skip unless wanted.
- Chest-open uses the existing `chest_scroll` flow.

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
| `:set wrap` rendering (1-row buffer wrapped across screen rows + vertical display-line scroll) | L17 | CHALLENGE C-L17-1 | The risk — prove alone first. `Player.wrap` + `apply_set` wrap option (parsing free via `engine/options.py`); motion engine untouched (stays 1×N), view-only wrap. |
| Reload loop: `:e`→E37, `:e!`→advance+reload, `:w {name}` save-as | L17 | CHALLENGE C-L17-2 | Per-level seed-shuffled suit sequence + filed-suit set; E37 message already in code; `:w {name}` = pure buffer→file write, no validation. |
| Archivist `npc` entity + hostile state + scripted lethal hit | L17 | CHALLENGE C-L17-3 | New non-combat `npc` kind; dialogue state machine; forged-commit fires `take_damage ≥ max_hp` → reuses existing GAME OVER → `:e` fresh-restart convention (no new combat system). |
| `gj`/`gk` (col ± W) + `:e {name}` reward tokens | L17 | CHALLENGE C-L17-4 | Granted by finale `chest_scroll`s after a clean assembly. |
| `:set number` HP reveal | Boss P4 | (covered by L16) | Boss P4 reuses `:set number` (now shipped at L16 Waypoint Sanctum) to reveal the Warden's hidden HP — NOT an L17 dependency anymore. |
| Mirror trap (x on dead entity → player damage) | Boss P4 | CHALLENGE C-L17-2-Boss | New engine behavior on `x` dispatch. |
| Winding corridor (30-cell) in NE Chamber | Boss P3 | CHALLENGE C-L17-1-Boss | Must be laid out in room builder; no engine change, just map design. |
| Warden immunity flag | Boss | CHALLENGE C-L17-3-Boss | `warden_phase_immune: set[str]` on Entity; checked in motion dispatch. |
| Mark-aware par solver (or hardcoded par) | L16 | CHALLENGE C-L16-3 | Dijkstra state includes frozenset of mark positions, or hardcode par=49. |
