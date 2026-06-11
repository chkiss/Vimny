# Act IV Blueprints — Visual Mode & The Operator Grammar

> ⚠ **Pre-implementation design doc — obsolete conventions; delete-on-implement.** Uses pre-slug naming (e.g. `RuneCluster` → now `CharRun`; level numbers are now the cosmetic `display` field) — don't copy these symbols. **Delete a level's section when that level ships, and the whole file once its act is built.** See LEVELS_PLAN Part 8.

> Generator-grade ASCII blueprints for levels 18–22 + boss 22.1.
> Each section is a complete spec for `build_dungeon_N()` in `generation/dungeon_gen.py`.
> Dims = (rows × cols). @ = entry, X = exit, K = keystone, D = door, g = goblin, W = warden.
> Par-solver assumptions are stated explicitly in each section.
>
> REVISION NOTES (applied after adversarial stress-test review):
> - S1 terrain-∞ forcing preferred over budget-margin forcing throughout.
> - S2 tight budget fallback: multiplier documented per level when margin-forcing is used.
> - S3 par recomputed as true full min-keystroke entry→exit including all navigation and Esc.
> - S4 earlier commands blocked via terrain or command guards where they would trivialize.
> - L19: par arithmetic corrected (2j 15l = 17, not 7; realistic par ~66); `D` taught as
>   shorthand demo since `D` and `d$` cost identically in the engine (CHALLENGE recorded).
> - L22: `dw` replaced by `de` (inclusive, chains correctly); `dd` and `d12e` bypasses
>   blocked via terrain (each goblin in single-cell alcove; door sealed by goblin death).
> - Boss Warden Manifold Phase 4: `yy`+`p` split — now Phase 4 = `yy`, Phase 5 = `p`,
>   one operator per phase; note engine CHALLENGE for `immune_to`/`phase` fields.

---

## L18 — The Operator's Vault

**Commands taught:** `d{motion}` and `c{motion}` with the full motion vocabulary.
  Sub-variants as practice (not separate lessons): `dw` `de` `db` `dt{c}` `df{c}` `d$` `d^`
  and equivalently for `c`. Aliases: `x` = `dl`, `s` = `cl` (noted in scroll/hint text).
New mechanics (count: 2):
1. The operator grammar `{operator}{motion}` is the one new idea, instantiated by two operators:
   `d` (delete) and `c` (change). Count = 2 operators, 1 grammar pattern.
2. `x` = `dl` and `s` = `cl` are retroactive aliases of the grammar, not additional mechanics.

**Linkage:** All motions are already known. The grammar `{operator}{motion}` is the single new
idea. `x` = `dl` and `s` = `cl` are retroactive aliases, not new commands.

---

### Grid

**Dims:** 16 rows × 60 cols.

Six "operator chambers" arrayed left-to-right, each 6 cols wide × 6 rows tall, at rows 2–7,
separated by 1-col WALL pillars. Each chamber has 3 rows of tightly-packed rune clusters (the
deletion targets) and one goblin at the chamber's exit row (row 9) guarding the path south.

The player must clear each goblin with the taught operator+motion for that chamber:
- Chamber 1 (cols 4–9): use `dw` to clear each rune cluster → goblin exposed → `dw` defeats it.
- Chamber 2 (cols 11–16): use `de` / `ce`.
- Chamber 3 (cols 18–23): use `db` / `cb`.
- Chamber 4 (cols 25–30): use `d$` (clears rest of row).
- Chamber 5 (cols 32–37): use `dt{c}` / `df{c}` (target char embedded in cluster).
- Chamber 6 (cols 39–44): use `d^` / `d0`.

After all goblins are defeated, the door at (8, 56) opens → exit at (15, 58).

**Grid (schematic, 16 r × 60 c):**

```
############################################################
#@                                                          #
#  [Ch1]  [Ch2]  [Ch3]  [Ch4]  [Ch5]  [Ch6]               #
#  runes  runes  runes  runes  runes  runes                 #
#  runes  runes  runes  runes  runes  runes                 #
#  runes  runes  runes  runes  runes  runes                 #
#                                                           #
#                     K                             D       #
#                                                           #
#   g      g      g      g      g      g                   #
#                                                           #
#                                                           #
#                                                           #
#                                                           #
#                                                          X#
############################################################
```

**Dims:** 16 rows × 60 cols.
- `@` at (1, 1).
- `X` at (14, 58).
- `K` (keystone) at (7, 27).
- `D` (door) at (7, 55) — opens when all 6 goblins are defeated.
- Goblins: row 9, cols 5, 12, 19, 26, 33, 40 (one per chamber).
- Rune clusters: rows 3–5, 6 per chamber. Each cluster is 2–3 symbols wide.
  Chamber 5 clusters contain a literal char target (e.g., 'z') for `dt`/`df` practice.
  Chamber 6 clusters are right-aligned (flush against the right wall of the chamber)
  so `d^` is the efficient sweep.

**Optimal path:**

```
Navigate from @ (1,1) to chamber 1 (row 3, col 4): j j 3l        cost: 5
Chamber 1 (dw practice): dw dw dw [3 clusters] j [to goblin] dw  cost: ~8
Chambers 2–6: similar pattern, using de / db / d$ / dtZ / d^      cost: ~40
Navigate to exit after door opens: 5j 14l                         cost: ~7
```

**Estimated par:** ~52 keystrokes (true entry→exit including all navigation).
**Budget:** ceil(52 × 1.4) = **73 keystrokes**.

**Forcing argument (S1 terrain-∞ + S4 command blocking):**
Each chamber's goblin blocks the south corridor. Pure navigation cannot reach X.
Each chamber's rune clusters are configured so the taught `{op}{motion}` is uniquely cheapest:
- Chamber 1: `dw` (2 keys) vs `x` per-char (cluster_width keys ≈ 6). Factor ≥3.
- Chamber 4: `d$` (2 keys) vs `dw` repeated (≈10 keys). Factor ≥5.
- Chamber 5: `dtZ` (3 keys) vs hjkl-to-char (≥6 keys for distance ≥ 6). Factor ≥2.
- Without knowing any operator: goblins block south; door blocks east. No exit within budget.

Next-best cost (using only `x` for all 6 chambers): estimated ~120 keys >> budget 73.

**S4 note:** Count-motions (`d3w`) are available from L2. Chamber rune clusters are spaced so
`d3w` would overshoot and miss goblins (goblins are at exact word boundaries, not beyond).
Chamber corridor widths are set so the taught motion exactly spans the required targets.

**Primitives used:** rune clusters (word-aligned and char-targeted), goblins (guards), door
(all-goblins-defeated trigger), keystone.

**Assumptions:**
- `d{motion}` removes all rune clusters fully covered by the motion span and repositions the
  cursor (per `op_delete`). Verified in `engine/operator.py`.
- `c{motion}` does the same then enters insert mode.
- Goblins are defeated when the player executes `d{motion}` along the goblin's row with the
  goblin in the span. Engine's `_delete_cols` (via `remove_entity`) handles this.
- Par solver must model `d{motion}` as (cost of motion) + 1 key for `d`.

**Self-check:**
- ≤3 new mechanics? YES: `d`/`c` operators instantiate one grammar pattern. Count = 2 operators.
- Forced? YES: chambers block navigation; operator+motion uniquely cheapest per chamber.
- L18 self-check text previously had "count: 2" vs "grammar is the single new idea" contradiction.
  Resolved: count = 2 operators sharing 1 grammar pattern. Both are stated consistently above.

---

## L23.5 — The Change Annex (originally drafted as L19; renumbered)

> The live curriculum split this section's commands: `dd` shipped with L18
> (The Operator's Vault), `D` shipped with L19 (The Cipher Cell, built), and
> `cc`/`s`/`S`/`C` are the Change Annex at display 23.5 — this section now
> drafts THAT level. The `D`-vs-`d$` cost CHALLENGE below was resolved when
> the Cipher Cell shipped: `_operator_cost` charges shorthand `D`/`C` as ONE
> keypress.

**Commands taught:** `dd` `cc` `D` `S`.
  Idiom family: operator-doubling acts on the whole line; `D` = `d$`; `S` = `cc`.
  **`V` (linewise visual) is also introduced here** as the visual equivalent of `dd` — it is
  gated on `visual_line` token granted at this level. `Vd` = visual-line delete = same as `dd`.
New mechanics (count: 2):
1. Operator-doubling idiom: `dd` deletes the whole line; `cc` changes the whole line.
2. `D` (= `d$`) and `S` (= `cc`) as convenient single-key shorthands — taught as **idiomatic
   demos**, not budget-forced commands (see CHALLENGE below regarding `D` vs `d$` cost).

**Linkage:** Students know `d{motion}` and `c{motion}` from L18. The new idea is that doubling
the operator (`dd`, `cc`) operates on the full line — the "implicit whole-line motion." `D` and
`S` are shorthands for already-known combinations (`d$` and `cc`), taught here as the natural
same-lesson companions. `V` (linewise visual) is introduced as the bridge to what students
learned in The Sight Sanctum: "select then delete" now applies to whole lines.

**CHALLENGE — `D` vs `d$` cost equality (engine):**
In the Vimny engine, `D` is parsed as `{'type':'operator','op':'d','motion':'$'}`, costing
`_operator_cost` = 1 (for `d`) + 1 (for `$`) = 2. Explicit `d$` also costs 1 + 1 = 2.
They are identical in cost. Therefore `D` **cannot** be budget-forced over `d$`.
Design decision: `D` is taught as idiomatic shorthand (same effect, muscle-memory convenience),
not as a strictly-required command. Annex 3's layout demonstrates `D` naturally (cursor lands
at start of right-half rune line; `D` is the obvious one-key reach). No budget-forcing claim
is made for `D` vs `d$`. A human designer should decide whether to change the engine cost
model to charge `D` as 1 keystroke (single key press) vs `d$` as 2.

---

### Grid

**Dims:** 18 rows × 52 cols.

Three annex chambers stacked vertically, each containing a full row of rune clusters.
Each annex has a void strip that makes navigating around the rune line physically impossible
(S1 terrain-∞ forcing for `dd` and `cc`).

**Precise layout (18 r × 52 c):**

```
##################################################
#@...........K...................................#
##################################################
#...[ANNEX 1: dd chamber]........................#
#...oooooooooooooooooooooooooooooooooooooooooooo#  <- void strip (impassable, full row)
#...rrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrr#  <- rune line (full row, must dd to clear)
#...D............................................#
##################################################
#...[ANNEX 2: cc chamber]........................#
#...oooooooooooooooooooooooooooooooooooooooooooo#  <- void strip
#...rrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrr#  <- rune line
#...D............................................#
##################################################
#...[ANNEX 3: D/d$ chamber — right-half rune]...#
#...         ooooooooooooooooooooooooooooooooooo#  <- void strip, right half only
#...         rrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrr#  <- right-half rune line
#...D.............................................X#
##################################################
```

- `@` at (1, 1).
- `X` at (16, 50).
- `K` (keystone) at (1, 13).
- Three annex chambers stacked vertically:
  - Annex 1 (rows 3–6): full-row rune line at row 5, cols 3–50. Door at (6, 3).
  - Annex 2 (rows 8–11): full-row rune line at row 10, cols 3–50. Door at (11, 3).
  - Annex 3 (rows 13–16): right-half rune line at row 15, cols 17–50. Door at (16, 3) → exit.
- Void strips on the row above each rune line: make it impossible to walk past the rune line
  without clearing it (S1 terrain-∞ forcing).
- `S` (= `cc`) is taught via a scroll in the annex 2 chest (same operation as `cc`, different key).

**Rune placement:**
- Annex 1 and 2: full passable extent (cols 3–50) packed with alternating ancient/verdant clusters.
  Total width forces `dd` to be cheapest: clearing via `dw dw dw...` ≈ 24 keys >> `dd` = 2.
- Annex 3: rune line starts at col 17 (cursor lands here after entering the annex). `D` = `d$`
  costs 2 keys. `dw dw ...` ≈ 18 keys. `D` demonstrated as idiomatic shorthand (no strict forcing
  over `d$` — see CHALLENGE).

**Optimal path (true full entry→exit):**

```
@ (1,1) → keystone (1,13):                    12l              cost: 12
[optional; skip if not required]
@ (1,1) → annex 1 rune at (5,3):              4j 2l            cost:  6
dd — clears full rune line, opens door:        dd               cost:  2
Through door to annex 2 rune (10,3):           4j               cost:  4
cc — clears full rune line (enters insert):    cc               cost:  2
Esc (exit insert mode):                        Esc              cost:  1
Through door to annex 3 (15,17):               4j 14l           cost: 18
D — clears right-half rune line, opens door:   D                cost:  2
Navigate to exit (16,50) from (15,17):         j 33l            cost: 34
                                                           ──────────
Total (skipping optional keystone):                             69
```

**Par:** ~69 keystrokes (true entry→exit, all navigation included).
**Budget:** ceil(69 × 1.4) = **97 keystrokes**.

**Forcing argument:**
- Annex 1 (dd, S1 terrain-∞): The void strip above the rune line makes walking past impossible.
  The rune line is 48 cols wide; `dd` (2 keys) clears it; `dw dw...` ≈ 24 keys. Terrain forces
  ANY clearing; `dd` is then cheapest clearer. Factor 12× vs `dw` repeated.
- Annex 2 (cc, S1 terrain-∞): Same pattern. `cc` + Esc = 3 keys; `cw cw...` + Esc × N ≈ 26 keys.
- Annex 3 (D/d$): Void strip forces clearing; `D` (= `d$`, cost 2) demonstrated as idiomatic.
  No strict budget-forcing claim between `D` and `d$` (see CHALLENGE).

**Primitives used:** full-row rune lines, void strips (bypass prevention per S1), doors
(per-annex rune-cleared trigger), keystone, chest (S scroll reward in annex 2).

**Assumptions:**
- `dd` deletes the full line extent and is modelled as 2 keys. Cursor lands at first passable cell.
- `D` in the engine is `d$` — deletes from cursor to end of passable extent.
- `cc` deletes the line and enters insert mode (2 keys); `Esc` exits (1 key). Par includes Esc.
- Par solver models `dd` (cost 2), `D` (cost 2 = same as `d$`), `cc` (cost 2) + Esc (cost 1).
- Door trigger: rune count on annex target row drops to zero.
- `V` (`visual_line`) token granted at this level; `Vd` on a rune row is equivalent to `dd`.
  Budget covers `Vd` (cost 2 per row) as an acceptable alternative to `dd`.

**Self-check:**
- ≤3 new mechanics? YES: (1) `dd`/`cc` operator-doubling, (2) `D`/`S` shorthand, (3) `V` linewise.
  All four are one idiom family: whole-line or end-of-line operations.
- Forced? YES: terrain-∞ via void strips for `dd` and `cc`. `D`/`S` taught as demo.
- Par correctly computed? YES: 69 (corrected from prior erroneous ~28; `2j 15l` = 17, not 7).
- CHALLENGE recorded? YES — `D` vs `d$` cost equality.

---

## L20 — The Beacon Tiers (BUILT — section deleted on implement)

Built 2026-06-11 as **The Beacon Tiers** (slug `quartermaster`); this draft's
pedestal-fill design was superseded during implementation (the engine's linewise
paste inserts REAL rows — it cannot fill existing ones). See
`generation/dungeon_gen.py::build_dungeon_quartermaster` and
`tests/test_quartermaster.py` for the level as shipped.

---

## L21 — The Undo Sanctum (CANCELLED 2026-06-11)

The level was cut from the curriculum: `u` has been always-on since the first
cave (a full snapshot rewind that even refunds budget), so a sandbox taught
nothing new, and `<C-r>` is now granted by the **'redo' relic scroll**
(`content/scrolls.py`, gated in `engine/command_guard.py`). The `redo` token
may return to the curriculum later if a level earns it.

---

## L22 — The Echo Vault

**Commands taught:** `.` (dot-repeat — repeat the last change).
New mechanics (count: 1, the minimum):
1. `.` repeats the last change (the exact operator+motion from the previous mutating keystroke).

**Teaching command: `de` (not `dw`).**
The engine's dot-repeat with `dw` does NOT chain through column-separated targets: after `dw`
deletes a cluster, the cursor stays at `start_col` (now empty floor), and each subsequent `.`
re-spans the same empty cells with a no-op `w` motion. `de` (INCLUSIVE motion) chains correctly:
after `de` at col C deletes a cluster ending at col D, each `.` re-runs `de` from col C on
empty floor — `e` scans forward to the end of the NEXT surviving cluster, so the span grows to
cover that cluster and the goblin on it. This is verified from the engine motion model.
Budget arithmetic is identical whether `dw` or `de` is the teaching command.

**Linkage:** `.` is only useful when there is a repeatable last change. This level immediately
follows L18 (operator grammar). Students have `de`, `dd`, `ce`, etc. as known changes. The
level is designed around 12 identical targets, each exactly 1 `e`-motion apart, so the optimal
sequence is `de . . . . . . . . . . .` (1 + 11 dots) vs `de de de ...` (2 × 12 = 24 keys).

---

### Grid

**Dims:** 12 rows × 62 cols.

The Echo Vault is a single long corridor with 12 identical rune sentinels (goblins). Each
goblin occupies a 1-cell alcove on the north wall of the corridor, separated from the main
corridor by a 1-cell gap. The player clears the first with `de`, then chains `.` × 11.

**S1 Terrain-∞ bypass blocking:**

Each goblin's alcove is a 1-cell side niche (1 col wide × 1 row deep, north of row 1). The
corridor is the main passable row. The goblins are reachable only from the corridor via `de`
on the rune cluster at the alcove mouth. This layout has two bypass-blocking properties:

1. **`dd` bypass blocked:** `dd` on the corridor row (row 1) deletes rune clusters on row 1
   but does NOT reach the goblin entities in the 1-cell alcoves on row 0 (the alcove cells
   are in a separate row). The door trigger requires all 12 goblins dead; `dd` on row 1
   leaves all goblins alive in their alcoves. `dd` does not solve the level.

2. **`d12e` count bypass blocked (S4):** Count-motions are available from L2. A command guard
   at L22 disallows `count > 1` with the `e` motion (or with any operator-motion combination),
   or equivalently the engine's operator guard for this level strips the count prefix. This
   means `d12e` is not accepted; the player must use `.` to chain. Document this guard in
   `content/levels.py` as a `blocked_commands` entry for L22.

**Layout:**

```
##############################################################
#nnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnn...........#  <- row 0: goblin alcoves
#@.∘∘.∘∘.∘∘.∘∘.∘∘.∘∘.∘∘.∘∘.∘∘.∘∘.∘∘.∘∘..............D..X..#  <- row 1: main corridor
##############################################################
(rows 2–11: open floor, unreachable during the puzzle — walls at rows 2 and 11 encl. corridor)
```

Where `n` = 1-cell alcove containing a goblin (accessible only from row 1 via `de` or similar).
The corridor is a 1-row channel (row 1 only), bounded by walls above (row 0 walls except alcoves)
and below (row 2 wall).

**Precise entity/rune placement (row 1, cols):**

- Rune clusters (∘∘, width 2): cols 3–4, 6–7, 9–10, 12–13, 15–16, 18–19,
  21–22, 24–25, 27–28, 30–31, 33–34, 36–37. (12 clusters, 2 wide, 1-col gap.)
- Goblin alcoves (row 0, 1-cell niche): cols 3, 6, 9, 12, 15, 18, 21, 24, 27, 30, 33, 36.
  Each goblin is in row 0, same col as the start of its cluster on row 1.
  The alcove mouth on row 1 is the cluster start col. `de` on the cluster covers the goblin
  because `_kill_entities_in_span` checks both row 0 (alcove) and row 1 (cluster) cells for
  entities within the inclusive span. (Implementation note: the span for `de` at (1, C) is
  inclusive of (1, C) to (1, D), where D = end of cluster. The goblin at (0, C) is one cell
  north — the engine must check adjacent alcove cells for goblin entities killed by `de`.)
  Alternatively (simpler): place goblins ON row 1 at the cluster start col. `de` kills them
  since they are within the inclusive span. `dd` on row 1 deletes rune clusters and goblins,
  BUT: the door trigger is "all goblins killed by a targeted single-cluster operator" tracked
  via a per-goblin kill-source flag... this is complex. Use the SIMPLER approach:
  
**REVISED SIMPLEST LAYOUT (goblins on row 1, `dd` blocked by exit placement):**
- Goblins and rune clusters on row 1.
- Exit entity `X` is on row 1 at col 58, inside the `dd` span.
- `dd` on row 1 deletes ALL entities in row 1 including the `X` exit entity via `_delete_cols`.
  With `X` deleted, the door trigger cannot resolve (exit entity removed → level unwinnable).
  The builder must ensure `X` is in a protected position OR flag `X` as `_PROTECTED_KINDS`.
  **Actually:** `X` is already in `_PROTECTED_KINDS` = `{'exit', 'door', 'boss_seal'}` per
  `visual.py`. So `_delete_cols` (non-visual path) will NOT remove `X`. `dd` still kills
  all goblins. This approach does NOT block `dd`.

**DEFINITIVE LAYOUT — use terrain to block `dd`:**
Place the corridor so `dd` on the goblin+rune row also encompasses a WALL cell or a
"poison rune" (kind='poison') that kills the player when deleted. This makes `dd` self-defeating.

Specifically: immediately after the last cluster (col 38), place a poison rune at col 39.
`dd` on row 1 would delete from col 1 to col 60 (full row), including col 39 (poison rune).
Deleting a poison rune triggers "player takes damage = game over" (or level restart).
The player learns not to use `dd` here by experiencing the consequence.

This is a new primitive (poison rune). If unimplemented, fall back to:
**S4 command guard:** Block `dd` explicitly via `blocked_commands` at L22. Document this guard.

```
##############################################################
#@.∘∘.∘∘.∘∘.∘∘.∘∘.∘∘.∘∘.∘∘.∘∘.∘∘.∘∘.∘∘.!.............D..X#
#  g  g  g  g  g  g  g  g  g  g  g  g  ^                   #
##############################################################
  [! = poison rune; ^ = note position]
```

Where goblins are at the same cols as cluster starts (row 1). `!` = poison rune at col 39.
`dd` = game over (hits poison). `de . × 11` avoids col 39 (only spans within cluster fields).

**Command guards for L22 (S4):**
- `dd` blocked via terrain (poison rune) OR explicit `blocked_commands` entry.
- `d12e` (count > 1) blocked via `blocked_commands = ['count_operator']` at L22.

**Optimal path:**

```
Navigate from @ (1,1) to first rune (1,3):   l l              cost: 2
de [defeat goblin 1 — inclusive e motion]:    de               cost: 2
. [repeat de, defeat goblin 2]:               .                cost: 1
. [goblin 3]:                                 .                cost: 1
. [goblin 4]:                                 .                cost: 1
. [goblin 5]:                                 .                cost: 1
. [goblin 6]:                                 .                cost: 1
. [goblin 7]:                                 .                cost: 1
. [goblin 8]:                                 .                cost: 1
. [goblin 9]:                                 .                cost: 1
. [goblin 10]:                                .                cost: 1
. [goblin 11]:                                .                cost: 1
. [goblin 12]:                                .                cost: 1
Navigate to X (1,58) after door opens:        20l              cost: 3
                                                         ─────────────
Total:                                                         17
```

**Par:** 17 keystrokes (true entry→exit).
**Budget:** ceil(17 × 1.4) = **24 keystrokes**.

**Revised forcing (S2 tight budget):**
- `de × 12` = 24 keys + navigation 5 = **29 keystrokes > budget 24**. Fails.
- `de . × 11` = 2 + 11 = 13 keys + navigation (ll + 20l = 5) = **17 ≤ budget 24**. Passes.
- **Forced.** (Multiplier used: ×1.4, standard. Documents: 29 > 24.)
- `dd` blocked by terrain (poison rune at col 39) OR `blocked_commands`.
- `d12e` blocked by `blocked_commands` (count > 1 with operators at L22).

**Primitives used:** rune clusters (12 identical, perfectly spaced), goblins (one per cluster),
door (all-goblins-defeated trigger), poison rune (or command guard) blocking `dd` bypass,
command guard blocking count-operator bypass.

**Assumptions (CRITICAL — Dot Last-Change Model):**
- The engine models "last change" as the exact operator+motion pair: `de`.
- `de` from col C on a cluster (cols C to D, inclusive): cursor → col C (start). Last change = `de`.
- `.` re-executes `de` from col C (now empty floor): `e` scans forward to end of next surviving
  cluster (col D'), spanning [C, D']. Goblin at the new cluster's start col is within [C, D'] and
  is killed. This chains through all 12 goblins without any `j` or navigation.
- Navigation keystrokes (`l`, `l` at start; `20l` at end) do NOT reset last change, since they
  are non-mutating. Only mutating operations set the last change register.
- `blocked_commands` at L22: `['dd', 'count_operator']` (or equivalent guard names as implemented
  in `main.py` / `content/levels.py`).

**Self-check:**
- ≤3 new mechanics? YES: exactly 1 (`.` dot-repeat).
- Forced? YES: `de × 12` = 29 > budget 24; `de .×11` = 17 ≤ 24. Tight by design.
- `dw` replaced by `de`? YES: chaining verified via inclusive-motion engine model.
- `dd` bypass blocked? YES: terrain (poison rune) or command guard.
- Count bypass blocked? YES: `blocked_commands` for count > 1 with operators.

---

## 22.1 — The Warden Manifold (Act IV Boss)

**Commands taught:** None new. Caps Act IV — all operator+motion grammar.
Format: Multi-phase boss where each phase of the Warden is immune to all operators EXCEPT
one specific operator∘motion pair. The player must recognize which pair is required per phase.

**Phase 4 redesign:** The original Phase 4 (`yy + p`, two commands) violated the one-operator-
per-phase invariant. It is now split into **two separate phases** — Phase 4 = `yy` (yank,
captures the Warden), Phase 5 = `p` (paste, places the captured Warden into the trap). The
boss is now 6 phases (previously 5). This preserves the yank+paste teaching from L20 while
respecting the single-operator-per-phase principle.

**CHALLENGE — `immune_to` / `phase` fields (engine):**
`engine/world.py` `Entity` dataclass has no `immune_to` field and no `phase` field.
The per-phase immunity system (the core boss mechanic) requires engine extension:
- `immune_to: frozenset = field(default_factory=frozenset)` — operators that deal 0 damage.
- `phase: int = 0` — current phase (1–6).
Both fields are absent from the current codebase. This is a concrete implementation dependency
that must be resolved before the boss is buildable. A human designer must approve the Entity
schema change. Until then, Phase immunity is an unimplemented CHALLENGE.

Additionally: Phase 6 (visual-mode delete) requires tagging "was this delete initiated from
visual mode?" The engine's `apply_visual()` path vs non-visual `op_delete` path must expose
a `source: str` parameter. This is also unimplemented.

---

### Overview

The Warden Manifold is a 6-phase boss fight. Each phase, the Warden's "shield" (displayed as
a glyph around it) indicates the only operator∘motion that can damage it. Other operators
bounce off (0 damage). Between phases, the Warden may summon minions (goblins) that the player
must clear to expose the Warden again.

The boss room is a single large arena (20 r × 60 c) with the Warden `W` at center, keystone `K`
at a safe side alcove, and the exit `X` sealed until all 6 phases are complete.

---

### Grid

```
############################################################
#..........................................................#
#..........................................................#
#...K.......................................................#
#..........................................................#
#..........................................................#
#.......................[ARENA CENTER]......................#
#..........................................................W#  <- Warden spawns center-right
#..........................................................#
#..........................................................#
#..........................................................#
#..........................................................#
#..........................................................#
#..........................................................#
#..........................................................#
#..........................................................#
#..........................................................#
#..........................................................#
#..........................................................#
#..........X.............................................  #
############################################################
```

**Dims:** 20 rows × 60 cols.
- `@` at (1, 1).
- `W` (Warden) spawns at (9, 50) for phase 1. Repositions per phase.
- `K` (keystone) at (3, 3).
- `X` (exit) at (19, 11) — sealed behind a boss_seal door until phase 6 complete.
- Arena: open floor, rows 1–18, cols 1–58. No interior walls.

---

### Phase Table

| Phase | Warden Position | Required Operator∘Motion | Shield Glyph | Minions | Notes |
|-------|----------------|--------------------------|--------------|---------|-------|
| 1 | (9, 50) | `dw` | `∘W∘` | None | Warden surrounded by word-rune clusters; only `dw` penetrates |
| 2 | (5, 30) | `d$` / `D` | `W→` | 3 goblins | Clear goblins first; then `D` or `d$` on Warden's row |
| 3 | (14, 20) | `dd` | `══W` | None | Full-line delete targets Warden's entire row |
| 4 | (9, 40) | `yy` | `⇅W` | 2 goblins | Yank the Warden's row; the yank "captures" it (damage trigger on yank-of-warden-row) |
| 5 | (16, 35) | `p` | `W⇓` | None | Paste the captured row onto the pedestal; Warden "released" takes damage |
| 6 | (9, 30) | `v {motion} d` | `[W]` | 4 goblins | Visual-select the Warden's cluster span, then delete |

**Phase 4 detail (`yy`):** The Warden is immune to everything except `yy` in this phase.
`op_yank` on the Warden's row (which contains a "capture rune" cluster adjacent to the Warden)
triggers "phase 4 hit" — the yank captures the Warden into the register. Damage = 1. This
requires a post-yank check: if the yanked row contains a Warden entity, deal phase damage.
This is simpler than the old "paste-as-damage" mechanic.

**Phase 5 detail (`p`):** Immediately after Phase 4, the register contains the captured row
(with the Warden's capture rune). A "pedestal" zone is revealed at row 16, cols 20–40. The
player must navigate to row 15 (one above the pedestal) and press `p` — paste places the
capture rune onto the pedestal, dealing the final Phase 5 damage. Warden transitions to Phase 6.
This is a new trigger type: post-paste check for capture-rune on pedestal zone.

**Note:** Phases 4 and 5 together replace the original single Phase 4 (`yy p`). The invariant
"one operator per phase" is now satisfied. Each phase has a single required command.

---

### Phase Mechanics Detail

**Phase 1 (`dw`):**
- Warden surrounded by 4 rune clusters (N/S/E/W). Each cluster kind='ancient' (∘∘∘).
- `dw` from a position where `w` lands on the Warden's col deals 1 damage.
- Other operators deal 0 damage (immunity — CHALLENGE: requires `immune_to` on Entity).
- Warden has 3 HP for phase 1. After 3 `dw` hits → phase 2.
- Warden AI: slowly drifts toward player (ai='chase', ai_speed=3).

**Phase 2 (`D` / `d$`):**
- Warden moves to (5, 30). Three goblins at (9, 20), (9, 30), (9, 40).
- Only end-of-line operator (`D` or `d$`) deals damage. Player must be on Warden's row,
  cursor to Warden's left.
- Warden has 2 HP. Goblins have 1 HP (killable with `dw` or `x`).
- After goblins cleared and 2 `D` hits → phase 3.

**Phase 3 (`dd`):**
- Warden moves to (14, 20). Warden's row surrounded by walls above/below (rows 13, 15).
  Only `dd` on row 14 hits.
- Warden has 2 HP. After 2 `dd` hits → phase 4.
- Between hits, Warden drifts along row 14 (oscillates cols 10–50).

**Phase 4 (`yy`):**
- Warden at (9, 40). Two goblins at (5, 20), (5, 40).
- Warden's row (row 9) has a "capture rune" cluster adjacent to the Warden entity.
- `yy` (yank row 9) triggers phase 4 hit if yanked row contains Warden entity → 1 damage.
- Warden has 1 HP. After 1 `yy` hit → phase 5.
- Goblins must be cleared first (they block the clear sightline to row 9).

**Phase 5 (`p`):**
- Warden at (16, 35). Register holds the captured row from Phase 4.
- A pedestal platform (target zone) revealed at row 16, cols 20–40.
- Player navigates to row 15, presses `p` — paste places capture rune on pedestal → 1 damage.
- Warden has 1 HP. After 1 `p` hit → phase 6.

**Phase 6 (`v {motion} d`):**
- Warden at (9, 30). Four goblins at (6, 10), (6, 30), (13, 10), (13, 30).
- Warden surrounded by a 3×3 rune cluster grid. Player must `v`, extend selection to include
  the Warden entity's col, then `d` — visual-select-delete hits the Warden.
- Warden has 3 HP. After 3 visual-delete hits → boss defeated.
- Warden AI: random walk (ai='wander', speed 2).
- On defeat: boss_seal door at (19, 10) opens → exit at (19, 11) accessible.

---

### Par / Budget

The boss fight does not use a strict par/budget — it is a combat encounter. Each phase has
a "par hit sequence":

| Phase | Optimal Hit Sequence | Keys (per hit × HP) |
|-------|---------------------|---------------------|
| 1 | `navigate + dw` × 3 | ~6 + 3×(nav+2) ≈ 18 |
| 2 | `3×(dw goblin) + 2×(navigate to row 5 + D)` | ~24 |
| 3 | `navigate to row 14 + dd` × 2 | ~10 |
| 4 | `2×(dw goblin) + navigate + yy` | ~12 |
| 5 | `navigate to row 15 + p` | ~8 |
| 6 | `4×(dw goblin) + 3×(navigate + v span d)` | ~30 |
| Total | — | ~102 |

**Boss budget (relaxed):** 160 keystrokes (~1.57× par). The boss is a capstone challenge.

**Forcing argument (per phase):**
Each phase's immunity forces the player to use that phase's operator. The Warden's HP does not
decrease from any other attack. Implementation requires `immune_to` / `phase` on Entity
(see CHALLENGE).

**Assumptions:**
- CHALLENGE: `Entity` dataclass needs `immune_to: frozenset` and `phase: int` fields.
- CHALLENGE: Phase 5's visual-delete immunity requires tagging delete source (`source='visual'`
  parameter through `apply_visual()` → `op_delete`).
- Phase 4 yank-as-damage: post-yank check in dungeon tick — if `op_yank` row contains Warden
  entity, deal phase damage. New trigger type; implement as post-action check.
- Phase 5 paste-as-damage: post-paste check — if pasted row's capture rune overlaps pedestal
  zone, deal phase damage. New trigger type.
- `Ctrl-R` scroll (from L21) may be found in a chest in the boss room's safe alcove.

**Self-check:**
- Boss caps Act IV? YES — all Act IV commands used across 6 phases.
- Each phase: single operator∘motion? YES (Phase 4 = `yy`, Phase 5 = `p`, split correctly).
- One-operator-per-phase invariant? YES — Phase 4/5 split resolves the original compound defect.
- CHALLENGES recorded? YES: `immune_to`/`phase` on Entity; visual-source tagging.

---

## Summary Table

| Level | Name | Commands | Par | Budget | Forcing | Key Risks / Challenges |
|-------|------|----------|-----|--------|---------|----------------------|
| 18 | The Operator's Vault | `d{motion}` `c{motion}` | ~52 | 73 | S1 terrain-∞ (goblins block) + budget per chamber | Per-chamber alignment must be hand-tuned; count-motions handled by chamber geometry |
| 19 | The Whole-Line Annex | `dd` `cc` `D` `S` | 69 | 97 | S1 terrain-∞ (void strips block bypass) | CHALLENGE: `D` ≡ `d$` cost (2=2); `D` taught as demo not forced. Par corrected from ~28 to 69. |
| 20 | The Beacon Tiers (BUILT) | `y yy P` | 17 | 24 | Structural (fuel rule: flames paste only onto braziers) + 3P count-paste | Shipped 2026-06-11; see code/tests. |
| 21 | (CANCELLED) The Undo Sanctum | — | — | — | u always-on; `<C-r>` via the 'redo' relic scroll | Cut 2026-06-11; token may return later. |
| 22 | The Echo Vault | `.` (dot-repeat via `de`) | 17 | 24 | S2 tight budget (`de×12`=29>24) + S1/S4 bypass blocking | `de` not `dw` (chains correctly); `dd` blocked by terrain/guard; count blocked by guard. |
| 22.1 | The Warden Manifold | ALL Act IV (`dw d$ dd yy p v..d`) | ~102 | 160 (relaxed) | Per-phase immunity | CHALLENGE: `immune_to`/`phase` fields on Entity; visual-source tagging; Phase 4/5 split (yy then p). |
