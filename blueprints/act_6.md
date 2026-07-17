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

> ✅ The Tag Enclosure SHIPPED 2026-07-19 as display 36 (the actual build
> diverged from the old section: exact-text chassis, the named nest
> (dit/dat by depth), the at double-gap tear vs the a-quote single, the
> C5 aim past an empty sibling, par 48 — `_resolve_tag` had already
> shipped with the tier-1 batch; see `build_dungeon_tag_enclosure` +
> its tests).

---

> ✅ The Sentence Enclosure SHIPPED 2026-07-19 as display 37 (the actual
> build diverged from the old section: exact-text chassis, mid-sentence
> landings as the forcing terrain, the dis/das gap discrimination, the
> Vim-true as leading-whitespace fallback on the last sentence, par 45 —
> see `build_dungeon_sentence_enclosure` + its tests).

---

> ✅ The Paragraph Enclosure SHIPPED 2026-07-25 as display 38 (the actual
> build diverged from the old section: two ELEVEN-row goblin cantos so a
> counted line-cut pays its second digit where dip/dap do not; the
> Warden's Measure seal (exact final row count + no goblin standing)
> prices which blank rows survive — over-deletion (d}, dG, :g/./d)
> breaks the measure instead of being parried; the watch-gap's goblins
> stand on a textless blank row (dap-forced, :g-immune), west-walled so
> V}d can't tie par from the aisle; par 9 —
> see `build_dungeon_paragraph_enclosure` + its tests).

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
