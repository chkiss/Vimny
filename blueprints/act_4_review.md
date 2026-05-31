# Act IV Blueprint Review — Adversarial Analysis

> Reviewer: automated adversarial pass.
> Sources: `blueprints/act_4.md`, `LEVELS_PLAN.md`, `engine/operator.py`, `engine/visual.py`,
> `engine/text_object.py`, `engine/motion.py`, `engine/world.py`, `main.py`.
> All arithmetic recomputed independently.

---

## L14 — The Sight Sanctum (`v`)

### SCOPE — PASS
Count: 2 mechanics. (1) visual-mode entry `v`; (2) `v{motion}d` select-then-operate.
Both are one conceptual family. `y`/`c` variants on visual selections are practice, not
new mechanics. Count is correctly 2.

### LINKAGE — PASS
`v` bridges into operator grammar (L18). Prior motion vocabulary is unchanged.
Coherent family: select → delete/yank/change.

### FORCEABILITY — FAIL

**V-shortcut bypass (critical).**
`V` (linewise visual, `Mode.VISUAL_LINE`) becomes available at the same time as `v`:
`main.py` gates ALL visual modes on `'visual' in player.known_commands`. There is no
separate gate for `V`. Within the inner room, `V d` selects the full passable row extent
(`line_extent()` via `op_delete`'s linewise path) and clears it. Cost: **2 keys per row**
versus the blueprint's `v $d` = **3 keys per row**.

Recomputed optimal with `V`:
```
nav to void field:    2j 2l      = 4
V d   (row 3):        V d        = 2
j V d (row 4):        j V d      = 3
j V d (row 5):        j V d      = 3
j V d (row 6):        j V d      = 3
exit inner room + X:             ≈ 10
                                 ─────
True par with V:                   25
Budget (V path): ceil(25 × 1.4) = 35
```

Blueprint states par = 29, budget = 41. With `V`, par = 25. The budget-25 path fits within
budget-41, so the blueprint's budget does not prevent `V`. More importantly: `V d` is
cheaper than `v $d` per row, so the par-solver would prefer `V` unless `V` is explicitly
gated. The taught command `v` is **not strictly cheapest**.

**Concrete fix:** Add a `V` gate separate from `v` in `known_commands`. Teach only `v`
in L14; teach `V` in a later level (e.g., L19 as part of the whole-line family). Alternatively,
document that L14's budget is computed with V available and par = 25, budget = 35, and
restate the solution sequence to use `v $d` only because the void field is not full-row-wide
(so `V d` would clear walls too — but `V` with `op_delete` uses `line_extent()` which
is bounded by the inner walls, so `V d` is safe and clears only the void). Gate `V` separately.

**Par recomputed:** 25 (with V). Blueprint stated 29.
**Budget recomputed:** ceil(25 × 1.4) = **35**. Blueprint stated 41.

---

## L18 — The Operator's Vault (`d c`)

### SCOPE — BORDERLINE PASS (1 finding)

Blueprint claims count = 2: (1) `d` operator, (2) `c` operator. The self-check entry also
says "grammar `{op}{motion}` is the single new idea." These are contradictory.

**Scrutiny of grammar-as-one-mechanic:** Calling `d` and `c` two mechanics and the grammar
a third would give count = 3. Calling the grammar the mechanic and `d`/`c` instances gives
count = 1. The blueprint chooses count = 2 by listing both operators as mechanics but not
counting the grammar separately. This is defensible if `d` and `c` are genuinely new (they
are — they had no operator-grammar form before this level). The sub-variants (`dw`, `de`,
`db`, `dt`, `df`, `d$`, `d^`, and `c`-equivalents) are **not** new mechanics — they are
instances of the grammar. Count = 2 is marginally acceptable but the blueprint should
acknowledge the grammar is a third concept bundled implicitly.

**Verdict:** PASS (scope = 2, all within one family), but the inconsistency between
"count: 2" and "grammar is the single new idea" should be resolved in the text.

### LINKAGE — PASS
All motions are pre-known. `d`/`c` apply the grammar. `x = dl`, `s = cl` are retroactive
aliases. Coherent family.

### FORCEABILITY — PASS (with one engine caveat)

Chamber-per-motion design correctly makes taught motion cheapest within each chamber:
`dw` ≪ repeated `x` (per-char), `d$` ≪ repeated `dw`, etc. Navigation-blocking goblins
close the non-operator bypass. Budget (73) is sufficiently tight.

**Engine caveat:** `op_delete` (the normal operator path) calls `_delete_cols`, which uses
`room.remove_entity()` — full erasure. `_kill_entities_in_span` (in `visual.py`) is called
only from `apply_visual()`, not from the normal `op_delete` path. However, `_delete_cols`
does remove entities in the span (including goblins), so goblin-killing via `dw` does work
mechanically. The difference: `kill_entity` sets `alive=False` (tracked in `_entity_by_kind`)
while `remove_entity` fully erases from the list. Door-open triggers that use
`_entity_by_kind.get('goblin', [])` must handle both removal modes. Flag for implementers.

**Par:** 52 (stated). Independent estimate: ~50–55. Accepted.
**Budget:** ceil(52 × 1.4) = **73**. Confirmed.

---

## L19 — The Whole-Line Annex (`dd cc D S`)

### SCOPE — PASS
Count: 2. (1) Operator-doubling idiom (`dd`/`cc`); (2) Shorthands `D`/`S`.
All four are the whole-line/end-of-line family. `S = cc` is a shorthand of the idiom,
not a third mechanic.

### LINKAGE — PASS
Students know `d{motion}`, `c{motion}` (L18). Doubling = implicit whole-line. `D = d$` is a
known combination in shorthand form. Coherent family.

### FORCEABILITY — FAIL (two defects)

**Defect 1: Arithmetic errors in stated optimal path.**

Blueprint states: "Through door into annex 3: `2j 15l` cost: 7." But 2 + 15 = 17, not 7.
Similarly "Navigate to exit: ll… X cost ~5" is implausible from (16, 17) to (16, 50): 33l = 33.

Recomputed par (18 r × 52 c layout):
```
@(1,1) → annex1 rune at (5,2):    4j l         =  5
dd (clears row, opens door):       dd           =  2
→ annex2 rune:                     2j           =  2
cc (clears, enters insert):        cc           =  2
Esc (exit insert mode):            Esc          =  1
→ annex3 rune at (13,17):          2j 15l       = 17
D (clears right-half rune line):   D            =  1
→ exit at (16,50) from (13,17):    3j 33l       = 36
                                                ─────
Recomputed par:                                   66
Budget: ceil(66 × 1.4) =                          93
```

Stated par = 28, stated budget = 40. The stated values are roughly a 2× underestimate.
The budget must be recomputed from a correctly traced path; otherwise the par-solver will
not correctly determine whether alternatives exceed budget.

**Defect 2: `D` vs `d$` not strictly forced.**

Blueprint claims: "Budget is set so `D` (1 key) must be used to stay under budget across
the whole dungeon — total savings from `D` vs `d$` contribute to meeting budget."

In annex 3, `D` costs 1 key and `d$` costs 2 keys (both `_operator_cost` = `len('D')+1`...
actually `D` is parsed as `{'type':'operator', 'op':'d', 'motion':'$'}` from vim_parser line 137,
cost = 1 (len 'd') + 1 (motion '$' = 1 key) = 2. Wait: `D` is 1 keystroke, but its action is
`op='d', motion='$'`. `_operator_cost` for motion='$': `c = 1` ('d'), `_keystroke_cost(1, '$') = 1`.
Total = 2. And explicit `d$` = 'd' then '$' = also 2. So `D` and `d$` have the **same cost in
Vimny** (both = 2 operator-cost units). There is no forcing argument between them — they are
equivalent. The blueprint incorrectly states `D` costs 1 key; it costs 2 (one for `D` being
a 1-char sequence that expands to `d$`, but the engine charges `_operator_cost` = 2).

Even if `D` and `d$` were 1 vs 2 keys: budget slack = par × 0.4 >> 1 key for any realistic
par, so `d$` also fits within budget. `D` cannot be forced via budget alone.

**What IS forced:** `dd` and `cc` are correctly forced (full-row rune lines make per-cluster
deletion far too expensive). The forcing for `D`/`S` specifically is not sound.

**Concrete fix:**
1. Retrace the optimal path carefully; compute correct par (approximately 66 in the current
   layout, or redesign the layout to shorten it).
2. Either accept that `D` is taught as the natural shorthand for `d$` without a strict budget
   forcing (idiomatic practice, not forced), or redesign annex 3 so `D` and `d$` differ in
   keystroke count in the Vimny engine.

---

## L20 — The Quartermaster (`y yy p P`)

### SCOPE — PASS
Count: 2. (1) `y`/`yy` yank operator; (2) `p`/`P` paste. One family: copy-paste.
"Linewise vs charwise clip distinction" is an implementation detail, not a third mechanic.

### LINKAGE — PASS
`y{motion}` mirrors `d{motion}` grammar (L18). `yy` mirrors `dd` idiom (L19). `p`/`P`
complete the triad. Coherent family.

### FORCEABILITY — PASS (structurally)

The door trigger (pedestal fill) requires runes placed in the pedestal zone. No other
command duplicates rune content; the player cannot reach X without triggering the door.
Forceability is structural (layout-enforced), not budget-enforced. This is acceptable and
stronger than budget-only forcing.

**Arithmetic defect in stated path (non-blocking):**
Blueprint states "Navigate to pedestal row 8 (3,3)→(8,32): `5j 29l` (or `jj 15l`) cost: 7."
5j + 29l = 34 keys, jj + 15l = 17 keys — neither equals 7. The "cost: 7" appears to be
a copy-paste error from elsewhere. The stated total par = 31 may therefore be understated,
but this does not break forceability since forcing is structural.

Also: "Navigate to door (14,46)→exit (19,54): `4j 14l 5j 8l` cost: ~13." That sequence is
4+14+5+8 = 31 keys, not 13.

**Concrete fix:** Retrace and re-sum the optimal path to get a correct par. With the void
strip forcing a detour, realistic par is approximately 55–65 keystrokes. Recompute budget.

---

## L21 — The Undo Sanctum (`u`)

### SCOPE — PASS
Count: 1 (`u`). `Ctrl-R` is a scroll reward, not a lesson. Intentionally minimal.

### LINKAGE — PASS
`u` logically follows operator grammar (corrects mistakes from L18–L20). Coherent.

### FORCEABILITY — PASS (correctly NOT forced)

Blueprint correctly marks this as "DEMO LEVEL — NOT BUDGET-FORCED" per Decision D1 from
`LEVELS_PLAN.md`. Budget is relaxed (999 / uncapped). The level does not claim forceability.
No door, no forced clearing. This is the correct handling.

**Verified:** The claim that `u` "is never the cheapest path to the exit" is correct —
the player can walk from `@` to `X` in ~8 keys without using `u`.

---

## L22 — The Echo Vault (`.`)

### SCOPE — PASS
Count: 1 (`.` dot-repeat). The simplest scope of the act.

### LINKAGE — PASS
`.` requires a repeatable last change. Design builds on L18's `dw` grammar. Coherent.

### FORCEABILITY — FAIL (three independent defects)

**Defect 1 (critical): `dw` dot-repeat does NOT chain through column-separated targets.**

This is a fundamental engine/design mismatch. After `dw` at cursor col 3 (cluster at cols
3–4, gap at 5, next cluster at col 6):

- `compute_text_object` runs `apply_motion('w')` from col 3 → col 6, then restores cursor.
- TextObject: (row1, 3, row1, 6, EXCLUSIVE). `_clip` → hi = 5. Span [3,5].
- `op_delete` deletes [3,5] (cluster + gap), goblin at col 3 removed. Cursor → `start_col` = **3**.
- `.` = repeat last_change (`op='d', motion='w'`) from col 3 (now empty floor):
  `apply_motion('w')` from col 3 (no rune) → scans forward → col 6 (next cluster).
  TextObject (row1, 3, row1, 6, EXCLUSIVE). Span [3,5]. **All floor. No-op.**
- Every subsequent `.` produces the same empty [3,5] span. **Goblin at col 6 is never reached.**

The blueprint states: "`.` (repeat `dw`) advances to unit N+1's rune and defeats goblin N+1."
This is incorrect. Cursor always stays at col 3 (`op_delete` sets `player.col = text_obj.start_col`).

**Verified arithmetic (as requested):**
- `dw × 12` = 24 keys + navigation 6 = **30 keys**. Budget = 27. **30 > 27. FORCED** ✓
- `dw . × 11` = 2 + 11 = 13 keys + navigation 6 = **19 keys ≤ 27** ✓
- **But the `.` chain doesn't work at all**, so the par/budget calculation is moot.

The "last change must not reset on hjkl" assumption is correctly stated. That is not the
issue. The issue is that even without any hjkl between goblins (same-row layout), the
dot-repeat cursor doesn't advance.

**Potential fix using `de` instead of `dw`:**
`e` is an INCLUSIVE motion. `de` from col 3 on cluster 3–4: TextObject (row1, 3, row1, 4, INCLUSIVE),
span [3,4]. Cluster deleted, goblin at col 3 killed. Cursor → col 3.
`.` = repeat `de` from col 3 (empty): `apply_motion('e')` scans forward → next rune at col 6,
end of cluster 6–7 = col 7. TextObject (row1, 3, row1, 7, INCLUSIVE), span [3,7].
Goblin at col 6 **is in [3,7]** → killed. This chains correctly.
Each successive `.` expands the span from col 3 to the end of the next surviving cluster.
**`de . . . . . . . . . . .` (12 clusters) works.** Budget arithmetic is unchanged (19 ≤ 27).

**Defect 2: `dd` trivially bypasses the forced path.**

Blueprint acknowledges the `dd` problem and goes through several "fixes," all abandoned.
The final design (single-row, 12 clusters, 12 goblins on row 1) leaves `dd` as a valid solution:
`dd` (2 keys) + navigation `ll` (2 keys) + exit `4l` (4 keys) = **8 keystrokes ≪ budget 27**.
This is not fixed. The blueprint's "ACCEPT THE SIMPLEST WORKING DESIGN" paragraph explicitly
acknowledges budget-only forcing works for `dw×12` vs `dw.×11`, then ignores `dd`.

**Defect 3: Count-motion bypass.**

`d12w` or `12dw` (Vimny parser supports `motion_count`):
`_operator_cost`: op='d' (1) + `_keystroke_cost(12, 'w')` = `len('12')+1` = 3. Total = 4 keys.
Plus navigation 6 = **10 keystrokes ≪ budget 27**. Not addressed in the blueprint.

**Concrete fixes:**
1. Replace `dw` with `de` as the teaching command. Budget arithmetic is identical (19/27).
   Verify that `de . . . . . . . . . . .` chains correctly as shown above.
2. Prevent `dd` bypass: place goblins on a separate row from the rune clusters, with the
   trigger requiring goblins to be killed by an operator that covers their specific column
   (not `dd`). Alternatively, enclose each goblin in a single-cell corridor so `dd` kills
   the player (dd includes an exit-entity cell → `_delete_cols` removes exit → level unwinnable).
   Cleaner: use a rune-barrier-door (each goblin guards a door, doors require individual clearing).
3. Prevent count-motion bypass: either disallow count with operators at this level via a
   command guard, or verify that `d12e` doesn't chain (it would delete from cursor to end of
   the 12th word from cursor — with 12 clusters at the expected spacing this needs verification).

---

## 22.1 — The Warden Manifold (Boss)

### SCOPE — N/A (no new mechanics; capstone)

### LINKAGE — PASS
All five phases use Act IV commands: `dw`, `d$`/`D`, `dd`, `yy`+`p`, `v{motion}d`.
Full Act IV vocabulary exercised. Coherent capstone.

### BOSS — PARTIAL FAIL (two defects)

**Defect 1: Phase 4 breaks the single-operator-per-phase principle.**

Phases 1–3 and 5 each require exactly one operator∘motion: `dw`, `d$`, `dd`, `v{m}d`.
Phase 4 requires **two** separate commands: `yy` (yank) then `p` (paste). This is a
compound two-step sequence, not a single operator∘motion pair. The phase table header says
"Required Operator∘Motion" but lists "yy p" — these are two distinct operator invocations.

The immunity model cannot enforce "the player must use yy then p in sequence" using the
existing `immune_to: set[str]` field concept, since each command is a separate event. A phase
based on a two-step sequence requires a state machine (phase 4 sub-state: "has yanked the
capture row?" then "did they paste onto the pedestal?") — this is substantially more complex
to implement than the other phases' single-command checks.

Additionally, Phase 4's "capture rune" → "paste onto pedestal → damage" is a **new engine
trigger** not present in `operator.py` or `visual.py`. The existing `op_paste` does not deal
damage; it just places rune clips. Implementing this requires a new post-paste check.

**Concrete fix:** Redesign Phase 4 to use a single operator∘motion. Options:
- `yy` alone: Warden is immune to everything except `yy`; yanking the Warden's row into the
  register "captures" it (yank is the attack, not paste). But `op_yank` does not mutate —
  using it as damage requires a new trigger on yank-of-warden-row.
- Replace Phase 4 with a `cc` or `s`-based phase (already introduced in L19), keeping the
  five-phase structure but using a simpler forcing mechanic.
- Or: Collapse to four phases and remove Phase 4 entirely.

**Defect 2: `immune_to` field absent from `Entity` dataclass.**

`engine/world.py` `Entity` has no `immune_to` field. The Warden's per-phase immunity
system (the core boss mechanic) requires engine extension. This is noted in the blueprint
("The Warden entity needs a new `immune_to: set[str]` field") but is labeled as an assumption,
not a risk. It is a concrete implementation dependency that must be resolved before the boss
is buildable. Similarly, `phase: int` is not on `Entity`.

Also: `apply_visual()` calls `_kill_entities_in_span` which respects `_PROTECTED_KINDS`
(`{'exit', 'door', 'boss_seal'}`). Warden entity (`kind='warden'`) is not in `_PROTECTED_KINDS`,
so a visual-delete spanning the Warden WOULD kill it via `_kill_entities_in_span` — but only
in visual mode. Normal `op_delete` via `_delete_cols` would also `remove_entity` the Warden.
The immunity model must intercept both paths.

**Phase immunity per-phase verification:**
- Phase 1 (`dw`): plausible if immunity blocks all other ops. ✓
- Phase 2 (`d$`/`D`): plausible (end-of-line operator). ✓
- Phase 3 (`dd`): plausible (linewise operator). ✓
- Phase 4 (`yy p`): **FAIL** — compound sequence, not a single op∘motion. ✗
- Phase 5 (`v{m}d`): plausible if engine tags "delete source = visual". ✓

---

## Summary Table

| Level | Scope | Linkage | Forceability | Boss | Overall |
|-------|-------|---------|--------------|------|---------|
| L14 Sight Sanctum | PASS | PASS | **FAIL** (V beats v; same gate, cheaper) | N/A | **FAIL** |
| L18 Operator's Vault | PASS\* | PASS | PASS | N/A | PASS |
| L19 Whole-Line Annex | PASS | PASS | **FAIL** (par arithmetic wrong; D≡d$ cost) | N/A | **FAIL** |
| L20 Quartermaster | PASS | PASS | PASS | N/A | PASS |
| L21 Undo Sanctum | PASS | PASS | PASS (correctly demo) | N/A | PASS |
| L22 Echo Vault | PASS | PASS | **FAIL** (dw chain broken; dd+count bypass) | N/A | **FAIL** |
| 22.1 Warden Manifold | N/A | PASS | N/A | **PARTIAL FAIL** (Phase 4) | **FAIL** |

\* L18 scope: "count: 2" and "grammar is the single new idea" are contradictory. Accepted as 2
(both operators are new), but the text should be made consistent.

**FAIL count: 4** (L14 forceability, L19 forceability, L22 forceability, 22.1 boss Phase 4).

---

## Overall Verdict

**FAIL.** Act IV has 4 distinct failures, two of which are critical (L22 dot-repeat chain is
fundamentally broken; L14 V-shortcut bypass undermines the teaching).

---

## Prioritized Fix List

### P0 — Blocking (level is unworkable as designed)

1. **L22: Replace `dw` with `de` as the teaching command.**
   `dw` dot-repeat does not chain through column-separated targets; the cursor stays at the
   deleted-cluster's start_col and each `.` re-spans the same empty cells. `de` (INCLUSIVE)
   chains correctly because the end-of-word col is included, spanning to each successive
   cluster. Restate all blueprint text referencing `dw` in L22 as `de`.
   Confirm: `de .×11` = 13 + nav 6 = 19 ≤ budget 27. `de×12` = each call hits one new cluster
   but also re-sweeps earlier floor; verify par-solver models this correctly.

2. **L22: Fix the `dd` bypass.**
   With 12 goblins on row 1, `dd` (2 keys) + nav (6 keys) = 8 ≪ budget 27.
   Fix option A: enclose each goblin in a 1-cell corridor so that `dd` on the goblin's row
   also deletes the exit entity on that row (per `_delete_cols` entity removal), making the
   level unwinnable. Place the exit on the same row but outside the corridor.
   Fix option B: use rune-barrier-doors (each goblin hides behind a sealed door; door requires
   `de` to clear the rune lock). `dd` would clear rune locks but also remove the doors (making
   them permanently open — actually this helps the player, not hurts). Better: use a per-goblin
   HP bar that requires exactly 1 `de` hit (not `dd`).
   Fix option C: place goblins on individual narrow corridors (separate rows), where the
   between-goblin movement is a `w` (not `j`) — so last_change is not reset. This requires
   a non-linear layout.

3. **L22: Fix the count-motion bypass.**
   `d12e` or `12de` = 4 keys + nav = 10 ≪ budget 27. Options: (a) apply a command guard that
   disallows count > 1 with operators in L22 (teaching count is L2's job, not L22's); (b) design
   the level so the targets require individual targeting that count-motions cannot batch
   (e.g., goblins in cells where the count-motion span would include a protected entity that
   blocks the span).

### P1 — Significant (forceability compromised)

4. **L14: Gate `V` separately from `v`.**
   `V` becomes available as soon as `'visual' in player.known_commands`. Since `V d` costs
   2 keys per row vs `v $d` = 3 keys per row, the taught command is not strictly optimal.
   Add `'visual_line'` as a separate known_commands token, gate `V` on it, and defer `V`
   to a later level (e.g., the whole-line family in L19 where `V` is naturally equivalent to `dd`
   for a row). Recompute par and budget for L14 with `V` unavailable (par = 29, budget = 41
   as stated).

5. **L19: Retrace optimal path; correct par and budget.**
   The stated optimal path has a known error: `2j 15l` stated as cost 7 (actual: 17).
   Retrace the full path for the stated 18 r × 52 c layout. Estimated correct par ≈ 60–70.
   Budget = ceil(par × 1.4). All subsequent self-checks and the summary table must use the
   corrected values.

6. **L19: Acknowledge that `D` and `d$` have identical cost in Vimny.**
   `_operator_cost` for `D` = `{'type':'operator','op':'d','motion':'$'}` = 1 + 1 = 2.
   For explicit `d$` = 1 + 1 = 2. Same cost. The blueprint's claim "D (1 key) must be used"
   is wrong in the Vimny engine. Either (a) accept that annex 3 teaches `D` as idiomatic
   practice (same cost as `d$`, just a shorthand) without budget-forcing, or (b) change the
   engine to count `D` as a 1-keystroke action (single key that issues `d$`) — which would
   require parser changes.

### P2 — Architectural (boss design)

7. **22.1 Phase 4: Replace `yy p` compound with a single-op phase.**
   Phase 4 breaks the per-phase "exactly one operator∘motion" invariant and requires new
   engine mechanics (paste-as-damage). Simplest replacement: make Phase 4 a `cc` phase
   (the Warden is immune to all but a change-operator on its row). `cc` is taught in L19 and
   not yet used in the boss. Alternatively, use a `yy`-only phase (yanking the Warden's row
   captures it into the register — implement as: if `op_yank` is called on a row containing
   a Warden entity, deal 1 phase damage). This is simpler than paste-as-damage.

8. **22.1: Add `immune_to` and `phase` fields to `Entity` dataclass.**
   Both fields are required by the boss design and are absent from `engine/world.py`.
   `immune_to: frozenset = field(default_factory=frozenset)` and `phase: int = 0`.
   The `_check_boss_cleared` and warden-damage logic in `main.py` must consult `immune_to`
   before applying damage. The visual-mode vs normal-mode distinction for Phase 5 immunity
   requires tagging the delete path — suggest a `source: str = ''` parameter threaded through
   `op_delete` / `apply_visual`.

### P3 — Documentation / consistency

9. **L18: Resolve the "count: 2 vs grammar is the single new idea" contradiction.**
   Pick one framing and state it consistently. Recommended: "The operator grammar `{op}{motion}`
   is the one new idea, instantiated by two operators: `d` (delete) and `c` (change). Count = 2
   operators, 1 grammar pattern."

10. **L20: Retrace optimal path; correct arithmetic.**
    `5j 29l cost: 7` and `4j 14l 5j 8l cost: ~13` are both wrong (actual: 34 and 31 respectively).
    Retrace with the void-strip detour modelled. Estimated correct par ≈ 55–65. The structural
    forceability is unaffected, but the stated par/budget values will change the summary table.
