# Act VI Blueprint — Adversarial Review

> Reviewer: automated adversarial analysis.
> Source files: `/home/ch/Vimny/blueprints/act_6.md`, `/home/ch/Vimny/LEVELS_PLAN.md`,
> `/home/ch/Vimny/engine/text_object.py`.
> Date: 2026-05-27.

---

## Methodology

Four principles checked per level:

1. **SCOPE** — count genuinely NEW mechanics; ≤3 is PASS.
2. **LINKAGE** — is the set a coherent family?
3. **FORCEABILITY** — independent par recompute; verify budget=ceil(par×1.4); verify the
   cheapest path uses the text object and next-best manual path exceeds budget; verify both
   inner (i) and around (a) variants are independently forced.
4. **BOSS** — phases cover all families; `ci"` is a correctness gate not just a budget gate.

---

## Level 30 — The Word Enclosure (`iw` `aw`)

### Scope

New mechanics:
1. Text-object concept (operator argument that selects by semantic shape)
2. `iw` — inner word
3. `aw` — around word (includes trailing/leading blank)

Count: **3**. PASS.

### Linkage

`iw`/`aw` are one "word" family; `aw` is the "around" variant of `iw`. Both use the same
`_resolve_word` engine call with `around=True/False`. PASS.

### Forceability — par recompute

**Blueprint claim: par=28, budget=40.**

Blueprint optimal path:
- j (1) → diw [run] row 2 (3) → 6j (6) → diw [run] row 8 (3) → 4j+l (5) → daw hello (3) →
  5l (5) → diw/x goblin (1–3) → navigate to exit (4)

Let me recount carefully:
- Navigate @(1,1) to (2,3): `j` `2l` = 2 keys
- `diw` first [run]: 3 keys
- Navigate (2,3) to (8, whatever second [run] col is): blueprint says row 8, `6j` = 6 keys
- `diw` second [run]: 3 keys
- Navigate to (12, col 4) for `hello`: blueprint says `4j` + `l` = 5 keys — but this is from
  row 8, so `4j` reaches row 12. And already at col 3 from first run; `l` = col 4. OK, 5 keys.
- `daw` on hello: 3 keys
- Navigate from (12, 9) (after daw, end of hello+space) to (12, 14) goblin: `5l` = 5 keys
- `x` on single goblin (blueprint says acceptable as x): 1 key
- Navigate to exit at (16, 48): `4j` + large right movement ~34 = ~38 keys

**DEFECT (CRITICAL):** Navigation to exit is wildly underestimated in the blueprint. From
(12, 14) + x + at (12, 14), must reach (16, 48). That is `4j` (4) + `34l` (34) = 38 keys.
The blueprint says "Navigate to exit: 4" which is impossible for a 34-column gap.

Even assuming `$` (end-of-line) is a known command (2 keys: `$` + adjust), or some faster motion,
the exit navigation is not 4 keys. `$` would land at col 51 (or last passable col), needing one
adjust, so `4j$` = 5 keys minimum, then still not at (16, 48) exactly.

**Blueprint par=28 is WRONG by severe undercount of exit navigation.**

Realistic par recompute (generous, assuming $ reaches near exit col):
- Navigate to (2,3): 2
- diw: 3
- Navigate to (8, ~col 3): 6
- diw: 3
- Navigate to (12, 4): 5
- daw: 3
- Navigate to (12, 14): 5
- x: 1
- Navigate to (16, 48) via 4j + $: ~6 (4j + $ + h to adjust)
  
Total: 2+3+6+3+5+3+5+1+6 = **34**

Budget would be ceil(34 × 1.4) = **48**, not 40.

**Secondary defect — iw forcing:**

The blueprint says `diw` on a 3-char [run] costs 3 keys = `xxx` costs 3 keys — a tie. The
tiebreak is a void-rune hazard forcing cursor to col 3. BUT: a player could use `dw` (a
previously-known command) from col 3 instead of `diw`. The blueprint claims to teach `iw` as
a NEW concept generalising `dw`, but `dw` from col 3 would delete `run` + the trailing floor
blank (if blank follows), while `diw` deletes only the cluster. If [away] is at col 7 with a
blank at cols 6, `dw` from col 3 deletes cols 3..6 (the cluster + trailing blank) — same as
`daw`! The blueprint does NOT verify that `dw` is forcibly inferior to `diw`/`daw` here.

The adversarial manual path: `dw` (known) on [run] at col 3 → same 3 keys → no `iw`
required. The level's "iw is the cheapest" claim is falsified by the known `dw` command.

**VERDICT: FAIL (forceability — par wrong, known `dw` bypasses iw teaching)**

---

## Level 31 — The Bracket Enclosure (`i(` `a(`)

### Scope

New mechanics:
1. Bracket scanning (left scan for `(`, right for `)`)
2. `i(` — inner parens
3. `a(` — around parens (includes delimiters)

Count: **3**. PASS.

### Linkage

`i(`/`a(` are one pair-delimiter family, direct extension of L25's i/a rule. PASS.

### Forceability — par recompute

**Blueprint claim: par=25, budget=35.**

Blueprint optimal path:
- Navigate (1,1)→(2,2): `j l` = 2
- `di(` enclosure A (clears goblins at 3,4): 3
- Move right past choke: `2l` or `w` = 2 — but after `di(`, goblins at 3,4 gone; player is at
  (2,2); choke wall at (2,6) blocks; to pass, must move to col 6+; `2l` from col 2 → col 4,
  but choke is at col 6 — need `4l` or more. Blueprint says "2" which seems wrong.
- `di(` enclosure B (goblins 8,9,10): 3
- `di(` enclosure C (goblin 14): 3
- Navigate to row 7: `5j` = 5
- `da(` gate: 3
- Navigate to X: 4

Recount with choke navigation correction:
- (1,1)→(2,2): 2
- `di(` A: 3
- Navigate col 2 past choke at col 6 to col 7 (the `(` of B): `5l` = 5 (not 2)
- `di(` B: 3
- Navigate col 7 to col 13 (the `(` of C): `6l` = 6 (not stated)
- `di(` C: 3
- Navigate row 2 → row 7: `5j` = 5
- `da(` gate: 3
- Navigate to X at (7,57): from (7,7) → `50l` ≈ 50 keys, or blueprint ignores that X is at col 57.

**DEFECT (CRITICAL):** Navigation to X is massively underestimated ("4"). X is at (7,57) and
after clearing the gate enclosure (cols 2..7), player is at ~(7,7). That is at least `50l` or
`$` (1 key if $ is known). Even optimistically `$j` or similar, the exit navigation is not 4.

Furthermore, the inter-enclosure navigation on row 2 (from col 2 to col 7 to col 13) is not
counted in the blueprint's "2" and omitted steps. The blueprint counts 2+3+2+3+3+5+3+4 = 25,
but the actual navigation between enclosures A→B→C alone is at least 5+6 = 11 extra keys.

Realistic par (generous):
- (1,1)→(2,2): 2
- di( A: 3
- Navigate col 2 → col 7 (skip choke): 5
- di( B: 3
- Navigate col 7 → col 13: 6
- di( C: 3
- Navigate (2,13) → (7,2): `5j` + left nav ≈ `5j 11h` = 16
- da( gate: 3
- Navigate (7,7) → (7,57): `50l` = 50 (or `$` = 1 if known)

Total even with $ known: 2+3+5+3+6+3+16+3+1 = **42**
Budget: ceil(42 × 1.4) = **59**, not 35.

**Secondary defect — i( vs a( distinction:**

The blueprint forces `di(` on row 2 (non-blocking delimiters) and `da(` on row 7 (wall_rune
delimiter). This is a valid distinction. HOWEVER: the blueprint states in the forcing argument
that "Row 2, enclosure B (3 goblins): di( = 3 keys; manual xxx = 3 keys — tie" then says the
tiebreak is that the player arrives at the `(` glyph (col 7), not col 8, so `di(` works
without stepping inside while `xxx` requires `l xxx` = 4.

BUT: the player knows `x` kills an entity in one keystroke. From col 7, `l x l x l x` = 6,
not `l xxx` = 4. The blueprint confuses "three x presses" with "step + three x presses". The
actual cost is `l` (step in) + `xxx` = 4. So the tiebreak logic as stated is correct — but
this is a margin of only 1 key per enclosure, NOT enforced by budget. With par undercounted,
the budget slack is actually much larger, and the manual path does NOT reliably exceed budget.

**VERDICT: FAIL (forceability — par severely undercounted; navigation between enclosures and
to exit omitted; budget 35 is approximately 59 in reality, which would still force text objects,
but the stated arithmetic is wrong)**

---

## Level 32 — The Brace & Square Enclosure (`i[` `a[` `i{` `a{`)

### Scope

New mechanics:
1. `i[`/`a[` — square-bracket pair (same algorithm as `i(`/`a(`, new char)
2. `i{`/`a{` — curly-brace pair (same algorithm, new char)
3. Nested pairs: `_resolve_pair` depth counter; cursor inside inner brace targets only inner

Count: **3**. PASS — if `i[/a[` and `i{/a{` count as one mechanic ("bracket family extension")
each, or as two separate (3 total with nesting). The blueprint explicitly lists them as 3
mechanics. PASS.

**But scope is borderline.** The LEVELS_PLAN.md description for L27 is "rest of brackets
(Decision: split of old L36)". The old L36 combined `i( a( i[ a[ i{ a{` into one level.
Splitting to L26 (parens) + L27 (square/brace) puts 4 commands in L27. Each `i[`/`a[` pair
and `i{`/`a{` pair are genuinely distinct from L26 only by delimiter char. The blueprint
counts them as 2 mechanics (same algorithm, new chars). Acceptable per the `i[/a[` = one
"bracket family extension" interpretation. **PASS** (barely; adversarial reading would FAIL
for 4 new commands in `i[ a[ i{ a{`).

### Linkage

`i[` `a[` `i{` `a{` are a direct extension of L26's bracket-pair concept. Nesting is the
genuinely new sub-concept. All in one "pair-delimiter" family. PASS.

### Forceability — par recompute

**Blueprint claim: par=35, budget=49.**

Blueprint optimal path:
- Navigate to (2,2): `j l` = 2
- `di[` on `[gg]`: 3
- Navigate to `{ggg}` at col 7: `3l` = 3 — wait, player is at (2,2) after di[ (cursor stays at
  deletion point). After deleting cols 3,4, cursor is at col 2. The `{` at col 7 is 5 columns
  away: `5l` = 5, not 3.
- `di{` on `{ggg}`: 3
- Navigate to row 7: `5j` = 5
- `di[` from col 5 in nested: 3
- Navigate to row 11: `4j` = 4
- Navigate to col 4 (`3l`): 3
- `di{` outer brace: 3
- Navigate to exit at (13,36): from (11,4) → `2j 32l` = 34 keys

Blueprint says "Navigate to exit: 6" which, from (11, ~col 9 after di{), to (13,36) would be
at least `2j` + `27l` = 29 keys. Not 6.

**DEFECT (CRITICAL):** Exit navigation wildly underestimated again. After clearing row 11,
player is around (11, 9); exit is at (13, 36). Minimum: `2j` + `27l` = 29 keys.

Realistic par:
- (1,1)→(2,2): 2
- di[: 3
- navigate to col 7 (5l): 5
- di{: 3
- navigate (2,7) to (7,5): 5j + back few cols = 5+2 = 7
- di[: 3
- navigate (7,9) to (11,4): 4j + left 5 = 4+5 = 9
- di{: 3
- navigate (11,9) to (13,36): 2j + 27l = 29

Total: 2+3+5+3+7+3+9+3+29 = **64**
Budget: ceil(64 × 1.4) = **90**, not 49.

**Secondary defect — `a[` and `a{` are NEVER forced:**

The blueprint ends with a NOTE: "`da{` vs `di{` does NOT have a mechanical difference here —
the act's `a{` distinction is instead demonstrated in the boss." This means `a[` is NEVER
forced in L27 either — the blueprint only forces `di[` and `di{`. The "around" variants of
BOTH square brackets and curly braces go unforced at the level where they are introduced.

LEVELS_PLAN principle: a level must force BOTH the inner and around variant, or split them.
`a[` and `a{` appear in the level's command list but are never made cheapest over `i[`/`i{`.

**VERDICT: FAIL (forceability — par wrong; `a[` and `a{` are introduced but never forced in
L27; deferred to boss is insufficient)**

---

## Level 33 — The Quote Enclosure (`i"` `a"` `i'` `a'`)

### Scope

New mechanics:
1. Quote scanning by parity (left-to-right, paired by index, not depth)
2. `i"`/`i'` — content between matching quote glyphs
3. `a"`/`a'` — content plus both quote-glyph delimiters

Count: **3**. PASS.

### Linkage

`i"`/`a"` and `i'`/`a'` share the identical parity-scan algorithm. Same family. PASS.

### Forceability — par recompute

**Blueprint claim: par=27, budget=38.**

Blueprint optimal path:
- Navigate (1,1)→(2,2): 2
- `di"` "gg": 3
- Navigate past choke to col 7: 2 — from (2,2) after deletion, col 2; choke wall at (2,6);
  need to reach col 7. `5l` = 5, not 2.
- `di'` 'ggg': 3
- Navigate to col 13: `6l` = 6, not 2.
- `di"` "g": 3
- Navigate row 2 → row 7: `5j` = 5
- `da"` gate: 3
- Navigate to exit (7,53): from (7,7) → `46l` = 46 keys, or `$` if known.

Blueprint says inter-enclosure navigations are 2+2=4 keys and exit is 4 keys. These are
dramatically wrong by the same systematic undercount seen in L25/L26.

Realistic par:
- (1,1)→(2,2): 2
- di": 3
- navigate col 2→col 7: 5
- di': 3
- navigate col 7→col 13: 6
- di": 3
- navigate (2,13)→(7,2): 5j + 11h = 16
- da": 3
- navigate (7,7)→(7,53): $=1 if known, else 46l

Total with $: 2+3+5+3+6+3+16+3+1 = **42**
Budget: ceil(42 × 1.4) = **59**, not 38.

**Secondary defect — `i'` vs `a'` distinction not forced:**

The blueprint forces `da"` on row 7 (wall_rune quotes) and uses `di"` on row 2. `i'` appears
only on row 2 enclosure B ('ggg'). `a'` is NEVER forced — there is no row that requires `da'`
(all single-quote delimiters are void-rune, not wall_rune). The `a'` variant is introduced but
not independently forced.

**Secondary defect — `di"` on single-goblin enclosure "g" (row 2 col 13..15):**

Blueprint claims `di"` from col 13 (`"`) costs 3 keys while `x` = 1 key. It says "player is
ON the `"` glyph; `di"` selects inner col 14." But `x` on the `"` glyph would delete the
delimiter, not the goblin — and `x` on the goblin at col 14 costs `l x` = 2 keys from col 13.
`di"` = 3 keys vs `l x` = 2 keys → manual is CHEAPER for enclosure C. The blueprint uses
enclosure C to "teach the idiom" despite it not being cheaper — this is fine for pedagogy but
not a forced use.

**VERDICT: FAIL (forceability — par wrong; `a'` never forced; `di"` on single-goblin
enclosure is not cheaper than manual)**

---

## Level 34 — The Tag Enclosure (`it` `at`)

### Scope

New mechanics:
1. Tag structure: `<tag>content</tag>` as compound multi-glyph delimiter
2. `it` — inner tag: content between `>` and `</`
3. `at` — around tag: content plus both tag delimiter clusters

Count: **3**. PASS.

### Linkage

`it`/`at` are a single "tag" family; same i/a rule; genuinely new concept (multi-glyph
delimiters). PASS.

### Forceability — par recompute

**Blueprint claim: par=45, budget=63.**

Blueprint optimal path:
- (1,1)→(2,2): 2
- `dit` on `<b>gg</b>` row 2: 3
- Navigate to `<em>` at col 12: `7l` = 7 — from (2,2) after clearing cols 5,6 (content);
  cursor stays at (2,2); `<em>` starts at col 12. `10l` = 10, not 7. The blueprint says 7l
  to reach col 12 from col 2; that reaches col 9, not 12.
- `dit` on `<em>ggg</em>`: 3
- Navigate to row 7: `5j` = 5
- `dat` gate: 3
- Navigate to row 12: `5j` = 5
- Position at col 8: `7l` = 7 — from (7, ~col 16 after dat), must go to (12,8). Needs `5j`
  (already counted) + repositioning. Blueprint counts 7l from starting position but player is
  not at col 1 at that point.
- `dit` from div: 3
- Navigate to exit (7,65): from (12, ~col 25) → the exit is at (7, 65) which is ABOVE row 12.
  Blueprint's optimal path went row 2 → row 7 → row 12 → exit, but exit is at (7,65). Player
  would need to go back UP. Blueprint says "navigate to exit: 7" — going from row 12 back to
  row 7 then right is at least `5k` + `40l` = 45 keys.

**DEFECT (CRITICAL):** The exit at (7,65) is placed ABOVE row 12 in the grid. The optimal
path should have cleared row 7 (dat gate) and then navigated RIGHT to X on row 7 before
descending to row 12. Or the exit is wrongly placed relative to the path. Either way, the
blueprint's path goes past X without collecting it, then tries to navigate back up — par is
wildly wrong.

**DEFECT (CRITICAL — UNIMPLEMENTED ENGINE OPERATION):**

`it` and `at` are explicitly flagged in the engine: `engine/text_object.py` line 306:
```python
return None   # 't' (tag) deferred
```
`resolve_text_object` returns `None` for any tag text object. The level CANNOT be played
until this is implemented. The blueprint acknowledges this but lists par/budget as if the
level is functional.

**VERDICT: FAIL (scope PASS; forceability FAIL — par wrong; `it`/`at` UNIMPLEMENTED in
engine; exit placement inconsistency)**

---

## Levels 35 & 36 — The Sentence Enclosure (`is` `as`) + The Paragraph Enclosure (`ip` `ap`)

### Scope

New mechanics:
1. `is`/`as` — sentence object (punctuation-delimited row runs; `as` includes trailing blank up to next sentence)
2. `ip`/`ap` — paragraph object (blank-row-delimited; linewise)
3. Blank row as paragraph separator (must be created explicitly; passable, no runes)

Count: **3**. PASS by the blueprint's counting.

**But this is adversarially BORDERLINE.** LEVELS_PLAN.md's audit table (row 39) explicitly
flags `is as ip ap` as "Sentence + paragraph = two families" and marks it as a **Linkage**
defect with severity Low. The plan's proposed curriculum lists L35 as "The Sentence &
Paragraph Enclosure (is as ip ap) (or split into two)." Introducing both sentence objects AND
paragraph objects in one level is introducing two distinct scanner algorithms: `_resolve_sentence`
(punctuation-based) and `_resolve_paragraph` (blank-row-based). These are genuinely different
families — sentences are charwise/row-level, paragraphs are linewise/multi-row.

**VERDICT on scope:** By strict counting this is 3 mechanics. But by family-linkage criterion
it is TWO families forced together. Adversarially: FAIL (linkage) by LEVELS_PLAN's own audit
which already flagged this.

### Linkage — FAIL

Sentence and paragraph are NOT one coherent family in the engine. `_resolve_sentence` is
charwise; `_resolve_paragraph` is linewise. They use entirely different algorithms and
different delimiter types (punctuation vs blank rows). This is the same split that
LEVELS_PLAN §1.1 identified and recommended fixing ("or split into two"). **FAIL.**

### Forceability — par recompute

**Blueprint claim: par=29, budget=41.**

Blueprint optimal path:
- Navigate to row 2 sentence 1: `j l` = 2
- `das` sentence 1: 3
- Navigate to sentence 2: "1 (already at 17 after das)" — questionable; `das` from col 1
  selects cols 2..17 (inclusive), cursor lands at col 2 after deletion. Sentence 2 start is
  now at col 2 (after sentence 1 was deleted). Actually if sentence 1 (cols 2..17) is deleted,
  "Fear not" would now start at col 2. `das` leaves cursor at start of deletion = col 2. The
  next sentence IS at col 2. Navigate: 0 keys. This part could be 0, not 1. Acceptable.
- `dis` sentence 2: 3
- Navigate down to paragraph section: "6j to row 9 entry" = 6 — from row 2 + 6 = row 8, but
  blueprint says "row 9 entry." From row 2, `6j` reaches row 8, not row 9. Off by 1.
- Navigate into P1 (row 12): `3j` = 3 — from row 9: row 9+3 = row 12. If starting from row 8
  after 6j from row 2, then `4j` to row 12.
- `dap` P1 + blank boundary: 3
- Navigate to P2 (row 16): `2j` = 2 — from row 12, `dap` selects rows 11..14 linewise; cursor
  lands at row 11 (start of selection). P2 is at rows 15..17. From row 11: `4j` = 4, not 2.
- `dip` P2: 3
- Navigate to exit (20,57): from row 17 + ~col 2 → `3j` + `55l` = 58 keys. Blueprint says 3.

**DEFECT (CRITICAL):** Navigation from P2 to exit at (20,57) is severely underestimated ("3").
From row 17, col ~2, the exit is at row 20, col 57: `3j 55l` = 58 keys minimum.

**DEFECT (MODERATE):** After `dap` on P1 (linewise deletion of rows 11..14), cursor lands at
row 11 in Vim convention (linewise deletes leave cursor at start). P2 is at rows 15..17. That
is `4j`, not `2j`.

Realistic par:
- j l: 2
- das: 3
- dis sentence 2 (0 nav): 3
- 7j to enter paragraph section (row 9): 7
- 3j to row 12: 3
- dap: 3
- 4j to P2 row 16: 4
- dip: 3
- 3j + 55l to exit: 58

Total: 2+3+3+7+3+3+4+3+58 = **86**
Budget: ceil(86 × 1.4) = **121**, not 41.

With $ known for the final navigation: 2+3+3+7+3+3+4+3+(3j + $) = 2+3+3+7+3+3+4+3+4 = **31**
Budget: ceil(31 × 1.4) = **44**

This is closer to the claimed 41 ONLY if `$` is counted as valid and movement is counted as 1
per cardinal step. But `55l` = 55 individual keystrokes; `$` = 1. The blueprint should specify
whether `$` is in scope for Act VI. Given `$` is taught in Act I (L1), it is a known command.
With `$` the exit navigation is reasonable. But then par=31 ≠ 29 (still off by 2).

**VERDICT: FAIL (linkage — two families; forceability — par off; paragraph cursor-after-dap
position error; P2 navigation undercount)**

---

## Level 36.1 — The Grandmaster's Sanctum (FINAL BOSS)

### Scope

New mechanics:
1. Phase barriers (wall rows that drop on trigger)
2. Defuse scrolls (optional — tutorial hints)
3. Warden entity (high-HP)

Count: **3**. PASS.

### Linkage

Boss synthesises all six families from the act. Phase barriers are a known boss mechanic
(used in earlier bosses per LEVELS_PLAN). Warden entity is a known primitive. PASS.

### Boss-specific verification: `ci"` as correctness gate

The blueprint correctly states: "`di"` does not defuse the bomb (mechanical requirement);
`ci"` is the only command that both clears and replaces. Not a budget question — a correctness
gate." This matches the principle that `ci"` must be a **correctness gate**, not just the
cheapest path. PASS.

Phase 4 detail check:
- Bomb timer activates on stepping on pressure plate.
- `di"` clears content but leaves empty quotes; replacement rune absent → bomb not defused.
- `ci"` + typing `safe` + Esc places a 'safe' kind rune inside the quotes → deactivates timer.
- This is mechanically correct IF the engine implements this bomb-timer + rune-kind check.
  The bomb-timer entity is listed as a new primitive in the boss's primitive list — it is NOT
  a previously existing primitive. This means the boss introduces a genuinely new game mechanic
  (bomb timer + pressure plate + defuse check) which is not in any prior level. This is
  legitimate for a final boss but should be flagged.

### Par recompute

**Blueprint claim: par=105, budget=147.**

The boss par calculation sums:
- Phase 1: 6
- Phase 2: 7
- Phase 3: 7
- Phase 4: 12
- Phase 5: 7
- Phase 6: 10
- Final chamber: 26
- Between-phase navigation: 30

Total: 6+7+7+12+7+10+26+30 = **105**. Arithmetic checks out internally.

**DEFECT (MODERATE) — Phase 4 keystroke count:**

Blueprint Phase 4 table row says "`ci"` + rune + `Esc` = 6 keys" but the Phase 4 detail
section says "ci" (3) + `safe` (4) + `Esc` (1) = 8 keys." The table and detail section
disagree. The detail section is more specific; 8 keys is correct for `ci"safe<Esc>`. The
table's "6" is wrong.

Corrected Phase 4 boss par: 12 (navigate 4 + ci"safe+Esc 8) — matches detail section.
But table shows Phase 4 as "6 keys (optimal)" which is inconsistent.

**DEFECT (MODERATE) — Final chamber `5x` count:**

Blueprint says "5x" to defeat Warden with max_hp=5. This assumes each `x` deals 1 HP and
the Warden has exactly 5 HP. That is consistent with the stated `max_hp=5`. But the player
must REACH col 40 first (after `di[`). The blueprint counts `5x` = 5 keys in the final
26-key tally. Also `das` on "Yield or fall." — that sentence includes a period and space;
`das` = 3 keys. The tally adds up: navigate 6 + da( 3 + di" 3 + di[ 3 + dat 3 + das 3 + 5x 5 = 26.
This checks out.

**DEFECT (MODERATE) — `a[` and `a{` are never exercised in the boss:**

Phase 3 uses `di[` (inner). The boss phase table shows `di[` as the Phase 3 command. Neither
`a[` nor `a{` appears in any phase or the final chamber. Since `a[`/`a{` are never forced in
L27 (noted above) AND not forced in the boss, these two commands are taught in L27 but never
actually required to be used throughout the entire act. This is a design gap.

**DEFECT (MINOR) — `is` appears in final chamber but not in the phase table:**

The Phase Table omits Phase for `is`/`as` — Phase 6 covers `dap`/`dip` but `is`/`as` only
appears in the final chamber (`das` on "Yield or fall."). This is acceptable — the final
chamber can require any act command. But `is` (inner sentence) is never required in the boss
phases or final chamber; only `as` (das) is used.

**VERDICT on `ci"` correctness gate: PASS**
**VERDICT on boss overall: PASS (with noted inconsistencies)**

---

## Systematic Defect: Navigation Undercount Across All Levels

All levels (25, 26, 27, 28, 29, 30) share the same systematic error: the blueprint's "Navigate
to exit: N" is almost always a 1-digit placeholder that does not account for the actual column
distance to the exit marker X. In every level the exit is placed near the right side of a wide
grid (52–72 cols), and the final navigation step is listed as 3–7 keys when the actual minimum
is 20–50 keystrokes (or 1–4 if `$` and `e` and other known motions are used).

The recomputed par values depend critically on whether `$` (end of line) is credited as a
single navigation key. If yes, the par values are closer to the blueprint's claims. If not,
they are off by 20–50x. The blueprint does not resolve this ambiguity.

**Recommendation:** State explicitly whether `$` is a valid navigation shortcut in Act VI par
calculations, and recompute all par values consistently.

---

## Unimplemented Engine Operations

| Command | Engine Status |
|---------|--------------|
| `it` (inner tag) | Returns `None` — explicitly deferred in `text_object.py` line 306 |
| `at` (around tag) | Returns `None` — same line, same branch |

No other text objects used in Act VI are unimplemented. `iw`, `aw`, `i(`, `a(`, `i[`, `a[`,
`i{`, `a{`, `i"`, `a"`, `i'`, `a'`, `ip`, `ap`, `is`, `as` are all implemented in
`resolve_text_object`.

---

## Level-by-Level Verdict Summary

### L25 — The Word Enclosure
- **SCOPE:** PASS (3 mechanics)
- **LINKAGE:** PASS (iw/aw one family)
- **FORCEABILITY:** FAIL
  - Known `dw` command bypasses `diw` forcing (same cost, already known to player).
  - `daw` semantics overlap with `dw` from the start of a word — no verification that `dw`
    is more expensive.
  - Par=28 is undercounted; exit navigation "4 keys" from col 14 to (16,48) requires ~38 keys
    unless `$` is used.
  - **Fix:** Add a word that is NOT at the start of a rune (cursor mid-cluster) so `dw` from
    that position eats only from cursor forward, not the whole cluster, making `diw` (whole
    cluster) strictly cheaper. Or add a "cursor trap" that places player in the middle of [run]
    so `dw` only deletes partial cluster and fails to open the choke. Clarify `$` usage.

### L26 — The Bracket Enclosure
- **SCOPE:** PASS (3 mechanics)
- **LINKAGE:** PASS (i(/a( one family)
- **FORCEABILITY:** FAIL
  - Par=25 is severely undercounted; inter-enclosure navigation (~11 keys) and exit navigation
    (~46 keys without $) omitted.
  - Wall_rune delimiter forcing of `da(` is valid in principle.
  - **Fix:** Recompute par with all navigation steps. Place X at the end of the gate row (row 7,
    col ~8) so exit navigation is minimal. Reduce inter-enclosure gaps.

### L27 — The Brace & Square Enclosure
- **SCOPE:** PASS (borderline — 4 commands, 3 mechanics)
- **LINKAGE:** PASS (all bracket-pair family)
- **FORCEABILITY:** FAIL
  - Par=35 undercounted; exit navigation to (13,36) from (11,9) is ~29 keys not 6.
  - `a[` and `a{` are NEVER forced (blueprint explicitly defers them to boss where they also
    don't appear).
  - **Fix:** Add a `da[` puzzle (outer `[` is a wall_rune blocking passage). Add a `da{` puzzle.
    Recompute par.

### L28 — The Quote Enclosure
- **SCOPE:** PASS (3 mechanics)
- **LINKAGE:** PASS (i"/a" and i'/a' same parity-scan family)
- **FORCEABILITY:** FAIL
  - Par=27 undercounted; inter-enclosure and exit navigation omitted.
  - `a'` is never forced (only `a"` gate is forced).
  - `di"` on single-goblin enclosure C is NOT cheaper than `lx` (manual wins by 1 key).
  - **Fix:** Add a wall_rune single-quote gate to force `da'`. Remove or relabel enclosure C
    as optional/pedagogical. Recompute par.

### L29 — The Tag Enclosure
- **SCOPE:** PASS (3 mechanics)
- **LINKAGE:** PASS (it/at one tag family)
- **FORCEABILITY:** FAIL
  - `it`/`at` are UNIMPLEMENTED in the engine (returns None).
  - Par=45 undercounted (7l to reach col 12 from col 2 is wrong; exit navigation wrong).
  - Exit at (7,65) is above the nested-tag puzzle at row 12; optimal path must revisit row 7,
    creating a navigation loop not counted in par.
  - **Fix:** Implement `it`/`at` in engine before generating this level. Move X to end of row 7
    or restructure grid so path is linear. Recompute par.

### L35 & L36 — The Sentence + Paragraph Enclosure
- **SCOPE:** PASS (3 mechanics by count) / FAIL (2 families by linkage)
- **LINKAGE:** FAIL (sentence = charwise punctuation-scanner; paragraph = linewise blank-scanner;
  two distinct families flagged by LEVELS_PLAN §1.1 audit)
- **FORCEABILITY:** FAIL
  - Par=29 is wrong; exit navigation to (20,57) is ~58 keys (or 4 with $).
  - After `dap` on P1 (linewise), cursor at row 11, not row 14; `2j` to P2 should be `4j`.
  - `as` (around sentence) forcing is valid (period is wall_rune choke).
  - `ap` (around paragraph) forcing via void-hazard on blank row is valid in principle.
  - **Fix:** Split into two levels: L35 = sentence only (`is as`), L36 = paragraph only
    (`ip ap`). Recompute par for each. Fix cursor-after-linewise-delete position in par calc.

### Boss 36.1 — The Grandmaster's Sanctum
- **SCOPE:** PASS (3 new boss mechanics)
- **LINKAGE:** PASS (synthesises all act families)
- **FORCEABILITY:** PASS (overall; each phase requires the specific family's command)
- **BOSS:** PASS (`ci"` is explicitly a correctness gate, not budget-dependent)
- **Noted issues:**
  - Phase 4 table says "6 keys" but detail says "8 keys" — inconsistency.
  - `a[` and `a{` are NEVER forced anywhere in Act VI (L27 or boss).
  - `is` (inner sentence) is never required; only `as` appears.
  - Bomb timer is a new primitive not introduced in any prior level — boss introduces it cold.

---

## Overall Verdict

**4 of 6 levels FAIL forceability. 1 level FAILS linkage. 1 level has an unimplemented engine dependency (L29).**

The act is structurally sound in intent but has two pervasive problems:
1. **Systematic par undercount** across all levels (navigation to exit dramatically understated).
2. **`around` variants under-forced**: `a[`, `a{`, and `a'` are introduced but never independently required.

---

## Prioritized Fix List

| Priority | Level | Defect | Fix |
|----------|-------|--------|-----|
| P0 | L29 | `it`/`at` unimplemented in engine | Implement `_resolve_tag` in `engine/text_object.py` before generating L29 |
| P1 | ALL | Navigation-to-exit severely undercounted in par | Clarify `$` credit policy; recompute all par values with consistent navigation model |
| P2 | L27 | `a[` and `a{` never forced anywhere in the act | Add wall_rune `[` gate (forces `da[`) and wall_rune `{` gate (forces `da{`) in L27 |
| P2 | L28 | `a'` never forced | Add wall_rune single-quote gate on row 7 or a new row |
| P3 | L25 | Known `dw` bypasses `iw` teaching | Place cursor mid-cluster so `dw` only deletes part; or verify `dw` is excluded from known commands at L25 |
| P3 | L35 | Sentence + paragraph = two families (LEVELS_PLAN flagged) | Split L35 into L35 (`is as`) and L36 (`ip ap`) |
| P4 | L25 | Par=28 undercounted | Recompute with correct exit navigation |
| P4 | L26 | Par=25 undercounted | Recompute; consider placing X on row 7 (gate row) to minimize exit nav |
| P4 | L27 | Par=35 undercounted; exit at (13,36) too far | Recompute; move X to right-end of row 7 or 11 |
| P4 | L28 | Par=27 undercounted; di" on single-goblin enclosure not forced | Recompute; relabel enclosure C as pedagogical, not forced |
| P4 | L29 | Par=45 undercounted; exit placement creates navigation loop | Restructure grid; X on row 7 (gate row) after the gate |
| P4 | L35 | Par=29 undercounted; cursor-after-dap position error | Fix `dap` cursor landing point in par calc; recompute |
| P5 | Boss | Phase 4 table says 6 keys, detail says 8 | Correct table to 8 keys; update boss par to 107 |
| P5 | Boss | `a[` and `a{` absent from all phases and final chamber | Add one `da[` or `da{` encounter in final chamber |

---

## Unimplemented Engine Operations (full list)

| Operation | File | Line | Status |
|-----------|------|------|--------|
| `it` (inner tag) | `engine/text_object.py` | 306 | Returns `None` — explicitly deferred |
| `at` (around tag) | `engine/text_object.py` | 306 | Returns `None` — same branch |
