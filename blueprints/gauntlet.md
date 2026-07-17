# The Gauntlet — the everything-exam maze (display 45, slug `gauntlet`)

> ⚠ **Pre-implementation design doc — delete-on-implement.** Delete this file
> when the level ships. Scoped 2026-07-17 with the user; ONE-MAZE form and
> `Y`-not-`yy` are user directives.

Placement: `wet_ink` (44) → **The Gauntlet** (display 45, `teaches: []` — an
exam introduces nothing) → `warden_eternal` renumbered **45.1**. Display edits
+ table regen only; slugs untouched.

**Mandate (user):** a MASSIVE maze testing 2+ actions from every act,
par-forcing all of: `h j k l w b e p y Y d D C S r cit % / * # . n M ~ gU o O`
plus one of `(/)` and one of `{/}`. One continuous maze — **not** sealed
wings. `Y` replaces `yy` (user correction: `Y` is the 1-key form and `yy`
can never beat it).

---

## 1 · The one-maze laws

These are what the single-buffer form demands (vs the sealed-wings draft):

1. **Vertical reflow is buffer-global.** `o`/`O` insert rows and shift every
   row below across the WHOLE maze while the stone stays put (the GMS
   `dap`-collapse bug class). → The row-creating legs (`o`, `O`) live in the
   **bottom band**, with only sacrificial blank rows and the gate row beneath
   them, and the gate tick derives its row from `exit_pos` (rides
   `_shift_rows`) exactly like the Joiner's Gate chassis.
2. **Every buffer-wide motion spans the whole maze** (`/ * # G gg { } ( ) M H L`).
   → One global draw pool, **every seed word unique across the entire maze**
   (GMS distinct-draw loop, ~60 words); scripted fog on the search-pocket
   words audited in BOTH directions from spawn WITH wrapscan (plugh law);
   teleport-audit geometry (first-standable of every row is on the spine,
   bolts west of anything skippable) applied maze-wide.
3. **State is sequenced by the route, not by seals.** The canonical route
   orders yank-before-paste (no kill/delete between), stamp-before-dot
   (motion-only between), `/`-before-`n` (nothing resets the register
   between). A player who interleaves badly pays more keys — that is forcing
   by PAR working, not a bug. Rival audits must consider ALL reachable
   register/dot states, not just the canonical one.
4. **One FINAL SEAL** (A-carve-hardened chassis): the exit is stone until
   every door reads true AND every proof-condition holds; the seal tick is
   the union of the door ticks (exact-text, row-agnostic, two-sided,
   stateless). No per-band seals.
5. **Ticks are row-agnostic; walls never move.** A player who `dd`s or `o`s
   mid-maze garbles their own text off the stone — self-sabotage, `u`
   recovers; nothing may hard-code a row number.

## 2 · Geometry sketch

One composite room, ~**48 rows × 72 cols**. A west **spine** column (the
Annex convention) with bands opening east; every band row's first standable
cell is the spine. Top-to-bottom (row numbers indicative):

```
rows  2-13   BAND I    motion galleries      w b e M % ( ) { }   (h j k l threaded)
rows 15-23   BAND II   the search pockets    / n * #             (scripted fog)
rows 25-33   BAND III  precision doors       r ~ gU . cit
rows 35-41   BAND IV   scribe + register     d D C S y p Y
rows 43-46   BAND V    the wellsprings       o O   (+ sacrificial blanks)
row  47      GATE      bolts · FINAL SEAL · exit
```

Band V is last **by law 1**. Bands I–IV are ordered so the search pockets
sit above the precision/scribe doors: the `*`/`#` pocket words must be
unreachable by accident once the player is doing insert-mode legs (typed
door text must never collide with a pocket word — global uniqueness covers
this, but distance helps the fog audit).

## 3 · The legs

Format: **leg — forcing geometry — canonical keys — cheapest rival (cost)**.
Every rival must cost strictly more than the leg's par share (or destroy the
door). Costs use the standard model (counts = `len(str(n))+1`).

### Band I — motion (Acts I–II)

- **w×2, e** — a word-run corridor: the landing is a `◆` fused to the END of
  the 3rd word (x it off — the Stair Rail lesson), words share first letters
  (kills `f`), 2-digit `l`-counts pay 3. `w w e x` vs `f◆x` (blocked by an
  earlier decoy `◆`... no: `f` to a unique glyph ties) → **the ◆ is NOT
  unique on the row** — a decoy ◆ mid-word-1 makes `f◆` need `;` (3 keys).
- **b** — after the x, the bolt-word to verify is BEHIND the cursor
  mid-row: `b` (1) vs `F`+char (2) vs `0w` (2).
- **M** — the corridor descends; the next gallery's entry row is the middle
  screen row, ≥10 rows from the park (`{n}j` = 3, `{n}G` = 3, `gg`/`G`/`H`/`L`
  land wrong). `M` = 1. M's landing cell is DESIGNED: first standable of
  that row = the spine, west of everything.
- **%** — a long bracket lintel `(…………)` spanning the gallery: cursor parks
  ON the `(` (previous leg ends there), mate is 20+ cols east past a decoy
  `)` (so `f)` = 2 + `;` = 3). `%` = 1. The `%`-landing starts the next leg.
- **( or )** — a 3-sentence verse row: the target word heads sentence 3;
  `) )` (2) vs `w`×6 (6) vs `/word` (len+2 ≥ 5). `}` overshoots (no blank row
  before the paragraph block below). AUDIT: wall-carved glyphs seed sentence
  starts (motion.py law) — this band's wall plaques must sit on rows with no
  sentence-object interplay, or be punctuation-free.
- **{ or }** — a packed 11-row paragraph block (blank-bounded; PE blank-row
  laws: char runs anywhere unblank, entities don't). `}` (1) crosses it;
  `{n}j` needs a 2-digit count (3). The block's rows are decor text (drawn,
  never door-read — but see law 2: all words still globally unique).

### Band II — search (Act III), the fog choreography

State ledger: the register is EMPTY entering this band (no prior search on
the canonical route).

- **/** — the band entry names a ward-word on its plaque; the word stands
  ≥12 rows / several bends away with motions costing >len+2. Word len 3 →
  `/abc⏎` = 5. Nothing between ties (fog on the pocket copies, below).
- **n** — a second copy further along the pocket chain; `n` (1) vs retyping
  (5). NOTHING between the `/` leg and the `n` leg resets the register.
- **`*`** — the `n`-landing parks the cursor ON a fresh word (the twin word
  is fused beside the landing — Buried Word pattern); its twin stands AHEAD
  with a BACKWARD decoy (so a wrapping `#` ties wrong). `*` = 1 vs `/word`
  = len+2 vs `nN`-games (register holds the / word, not this one — N finds
  the wrong thing).
- **#** — the `*`-landing parks on a second fresh word; its twin is BEHIND,
  with a FORWARD decoy (wrapping `*` lands wrong) — the Waypoint #-law
  verbatim. `#` = 1 vs `*NN` = 3 vs `?word` = len+2.
- **FOG:** every pocket word's OTHER copies sleep under scripted fog until
  the band-entry tick wakes them (fog EVERY occurrence either cheese
  direction could substitute; audit `?word`-from-spawn wraps; pin the cheese
  tapes). Fogged cells are impassable — the reveal tick must fire before the
  player's path crosses them (search landings call `_content_ticks` same
  turn — already engine law).

### Band III — precision (Acts IV–V)

Exact-text doors on the `_wla_doors` chassis (west-wall plaques hold
targets), all opening bolts in the row-47 gate.

- **r** — one wrong char in a door word whose row is PACKED flush to the
  east wall: `s`/insert open a gap and the reflow push shoves the tail
  glyph into the wall (void-fall — door text destroyed). `r{c}` (2) ties
  `s{c}` (2) on cost but `s` DESTROYS; `r` is the only non-destructive fix.
  Test: the `s` tape leaves the door unopenable (until `u`).
- **~** — two consecutive wrong-CASE chars: `~~` (2) vs `r{c}r{c}` (4) vs
  `gUl gUl`-ish (no — `gUe` would fix a whole-word case but these two chars
  sit mid-word in an otherwise-correct word, so any sweep overshoots:
  idempotence doesn't help when the REST of the word is correctly lower).
  Use a MIXED-target word (Case Chambers `g~~` law) so sweeps fail.
- **gU + .** — two doors, whole-lowercase words of DIFFERENT lengths (4 and
  6): door 1 `gUe` (3), door 2 `.` (1) = 4 total. Rivals: `veU veU` = 6
  (and if visual-dot repeats region-size, the length mismatch garbles door
  2 — verify engine; either way it loses); `~`×4 + `~`×6 = 10; `gUe gUe`
  = 6. Motion-only between stamp and dot (the connecting corridor is part
  of the leg).
- **cit** — a `<name>word</name>` door, drawn tag name (GMS law), cursor
  parking west of the tag: `cit` + typed cure vs `f>l ce` + cure (+2) vs
  `ci<` (wrong object — changes the tag name, door shut). Cure is a single
  drawn token (karaoke law).

### Band IV — scribe + register (Acts IV, VI)

- **d** — a ≥3-char junk run fused before a door word: `dw` (2) vs `xxx`
  (3). (Charwise — NO dd anywhere on the canonical route; law 1.)
- **D** — multi-word junk from mid-row to the east wall: `D` (1) vs `d$`
  (2) vs `dw dw` (4).
- **C** — a wrong two-word tail: `C` + one drawn word (1+len) vs `c$`
  (2+len) vs `D a` (2+len). The C door FOLLOWS a door that parks the
  cursor mid-row (Change Extension chaining law).
- **S** — wrong text on BOTH sides of the arriving column (C leaves the
  head): `S`+word (1+len) vs `0C`/`^C` (2+len) vs `cc` (2+len). Single
  drawn word (space law).
- **y + p** — a door needs a drawn 7-char word that exists ONCE, two rows
  above the door slot: `yiw` (3) + move + `p` (1) vs typing it (i+7+Esc ≈
  8). No delete/kill between yank and paste on the route (state law 3).
- **Y + p** — a LINE door: a whole drawn 3-word line (≥14 chars incl the
  two floor gaps — laid as separate CharRuns, floor scan reconstructs the
  spaces) duplicated onto the blank slot below it: `Y` (1) + `j` + `p` (1)
  vs retyping (unpayable; also spaces can't be typed in karaoke — the
  RIVAL types it but the canonical never does; rival cost ≈ 17). `yy` ties
  +1 — allowed, loses a key, still opens the door (Y-preference is priced,
  not gated). Linewise `p` here is a REAL row insertion → this door is the
  southernmost text in Band IV and the pasted row lands on a sacrificial
  blank (law 1 applies to `p`-linewise too!).
  **⚠ open design item:** verify linewise-p row insertion under the gate
  tick — same `_shift_rows` ride as Joiner's; if it destabilizes, flip
  this door to charwise `y$`+`p` and give `Y` a different lesson slot.

### Band V — the wellsprings (Act V)

- **o** — a gate-verse must exist on a line that DOESN'T exist: the band's
  packed 2-row stanza has no blank below (walls tight); `o` opens the line
  (Sculpting blank=True, segment-scoped floor) and types the drawn word.
  Not merely cheaper — the only way to create the line. Rows below: only
  sacrificial blanks + gate row (law 1).
- **O** — same, ABOVE the stanza's first row (a sealed lintel line). `O` +
  drawn word; `ko`-style alternatives cost +1 and land the wrong side of a
  wall course.
- **h j k l** — threaded everywhere; the designed single-step: the o/O
  stanza approach ends one cell east of the verse column (`h` optimal), and
  the final walk onto the exit is `l` (GMS arena pattern). `j`/`k` are the
  band connectors all route long.

### The gate

Row 47: bolts (one per door, ~14), the FINAL SEAL east of all bolts, exit
entity east of the seal, ◆ threshold stone at the spine head (G parks west
— the GMS lesson), spine-only throat row above (teleport audit).

## 4 · Canonical route & state ledger

One tape, top to bottom: Band I motions → Band II searches → III → IV → V →
`$` through the gate. Register states along it:

| leg | search reg | unnamed reg | last change |
|---|---|---|---|
| I motions | empty | empty | — |
| II / n * # | /word → *word → #word | empty | — |
| III r ~ gU . cit | #word (unused) | r/~ debris — OK, y comes later | gU stamp → . |
| IV d D C S | #word | d/D/C/S clips — then **yank AFTER all deletes** | S |
| IV y p Y p | #word | y-word → pasted → Y-line → pasted | p |
| V o O | #word | Y-line (unused) | O-insert |

The y/Y legs are the LAST edits before Band V precisely so no delete
clobbers them (user: "change the sequence of keys" — this is that).

## 5 · Numbers

- Par: hand-tallied along the tape, ~**85–95** keys (≈24 forced commands +
  typed door text + connectors). Pinned by the driven 2★ test, NOT a solver
  (`_SKIP_LEVELS` / own driven test — GMS pattern; `C.init`/`S.init` in
  driven tests).
- Budget: hand-set generous (~par+35; `_NONSTANDARD_BUDGET`) — ~10 insert
  doors invite typos; forcing is by PAR (every leg's rival test), never by
  budget.
- Answer: one karaoke tape from a `_gauntlet_route(words)` helper shared
  with the driven test; all typed text single drawn tokens; `Esc` omitted;
  `_ANSWER_NOT_TOKENISED` + `_REPLAY_OWN_TEST` opt-ins.

## 6 · Test plan (≈100 tests)

1. Structure/geometry per seed; global word uniqueness; BFS spawn→gate.
2. Driven canonical wins at 2★ (par); per-leg rival tapes: each wins at 1★
   or leaves its door shut (the `r`-vs-`s` destruction case; `ce`-vs-`cE`
   class replays).
3. Cheese pins: `?`-from-spawn wraps for both pocket words; `*`/`#`
   cross-pocket substitution; `G`/`gg`/`M`/`{n}G` land-audit on every row
   (no jump reaches east of a shut bolt/seal); dap/dd-collapse + jump does
   not cross the seal (position+seal-cell transition law — N/A here, same
   room, but the seal cell itself is the win gate).
4. Fog: pocket copies unsearchable + impassable pre-reveal; reveal tick
   fires on the entry row; search landing ticks same-turn.
5. Reflow: o/O legs shift only sacrificial rows (assert every door text
   still reads true after the canonical o/O/p-linewise legs); the r-door
   `s`-tape void-falls the tail.
6. Sequence-key guards (`raw and raw in …`) on any new key handling.

## 7 · Fiction (intro stays atmospheric — never names keys)

"The Gauntlet: every hall you have walked, folded into one. The wardens
built it as their proving ground; the stone remembers every lesson and asks
them all at once. Nothing here is new. Everything here is final." Wizard
poem may name commands plainly (poem law); the intro may not.

## 8 · Open items for user review

- The `Y`-linewise-`p` door's row insertion (§Band IV ⚠) — fallback drafted.
- `(`-vs-`)` and `{`-vs-`}`: canonical uses `)` and `}` (forward reads
  naturally on a descending maze); the mirrors are allowed, priced equal.
- Combat: NONE in this level (protects the register legs; `x` is not on the
  mandate list — the ◆-x in Band I is an edit on text, not combat).
- Display renumber: warden_eternal 44.1 → 45.1 at ship time.
