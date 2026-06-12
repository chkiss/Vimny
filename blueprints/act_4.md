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

## L22 — The Echo Vault (BUILT — section deleted on implement)

Built 2026-06-11 as display 21 (slug `echo_vault`). This draft's `de`-chain
design was superseded: in the current curriculum `D`, `df{c}`/`dt{c}` partial
sweeps and count-`x` all out-price a deletion chain, so the shipped level
echoes **`r`** instead (untypable warp glyphs; plaque-family rule; `3.`
count-dot finale). See `generation/dungeon_gen.py::build_dungeon_echo_vault`
and `tests/test_echo_vault.py`.

---

## 22.1 — The Warden Manifold (BUILT — section deleted on implement)

Built 2026-06-12 as display 21.1, "The Stamping Press". This draft's
selective-immunity design (`immune_to`/`phase` Entity fields, visual-source
tagging) was never built: the shipped boss uses the engine's real
all-or-nothing `edit_immune` parry plus STRUCTURAL rounds — he stamps wards
of text and copies of himself, each round keyed to one Act-IV verb
(d{m} → r+. → D → yy+P), with an antechamber brazier ritual (yl + P, the
fuel rule) gating entry, a mirrored hall (friezes, colonnade, four podium
niches), and a pressure hook deliberately left quiet. See
`generation/dungeon_gen.py::build_dungeon_warden_manifold`,
`main._warden_manifold_tick` and `tests/test_warden_manifold.py`.

---

## Summary Table

| Level | Name | Commands | Par | Budget | Forcing | Key Risks / Challenges |
|-------|------|----------|-----|--------|---------|----------------------|
| 18 | The Operator's Vault | `d{motion}` `c{motion}` | ~52 | 73 | S1 terrain-∞ (goblins block) + budget per chamber | Per-chamber alignment must be hand-tuned; count-motions handled by chamber geometry |
| 19 | The Whole-Line Annex | `dd` `cc` `D` `S` | 69 | 97 | S1 terrain-∞ (void strips block bypass) | CHALLENGE: `D` ≡ `d$` cost (2=2); `D` taught as demo not forced. Par corrected from ~28 to 69. |
| 20 | The Beacon Tiers (BUILT) | `y yy P` | 17 | 24 | Structural (fuel rule: flames paste only onto braziers) + 3P count-paste | Shipped 2026-06-11; see code/tests. |
| 21 | (CANCELLED) The Undo Sanctum | — | — | — | u always-on; `<C-r>` via the 'redo' relic scroll | Cut 2026-06-11; token may return later. |
| 22 | The Echo Vault (BUILT, display 21) | `.` echoed off `r` | 25 | 35 | Untypable warps (f/t// can't target); cuts break the plaque; register self-seal | Shipped 2026-06-11; see code/tests. |
| 22.1 | The Warden Manifold (BUILT, display 21.1) | ALL Act IV (`d{m} r+. D yy+P`, x windows) | — | 220 (relaxed) | Structural rounds + edit_immune parry (no immunity engine) | Shipped 2026-06-12; see code/tests. |
