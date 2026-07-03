# Act V Blueprints — The Writers (displays 22 → 30.1)

> ⚠ **Pre-implementation design doc — delete-on-implement.** Delete a level's
> section when it ships; delete the file when the act is built.
> Rewritten 2026-06-12 to current conventions (the original draft predated the
> slug refactor, universal reflow, and the Manifold-era boss patterns).

## Conventions (current — do not copy the old draft's)

- Identity is the **slug**; the number is the cosmetic `display`. Builders
  `build_dungeon_<slug>`, constants `_<SLUG>_*`, tests `tests/test_<slug>.py`.
- On-screen text = **CharRun** ("rune" is theme only). Budget = `ceil(par × 1.4)`
  unless a section justifies a tighter multiplier (S2). `Esc` costs 1 keystroke;
  **verify the per-typed-char insert cost empirically before fixing any par**.
- **Coordinates in design talk are the game's RULER** (status line: display =
  grid − first standable row/col + 1). Grids in this doc are sketches, not specs.
- Modern level pattern (Operator's Vault → Manifold lineage): stateless
  undo-safe `main._<slug>_tick`; vocab-driven text per seed with fixed
  lengths/positions (par seed-invariant); hand-tallied par + `room.answer` in
  separate operator/motion tokens; a real-keystroke `run_dungeon` playthrough
  test; **teleport + walking audit** (G/{n}G/gg/H/M/L land on first non-blanks;
  audit walking from adjacent rows); reflow laws (BOTH open_gap PUSH and close_gap
  PULL are segment-bounded — a mid-row wall/void rune is a hard line boundary; the
  glyph against the wall falls INTO it, content on the far side is safe; so a clue
  behind a wall survives an edit on either side).
- Toolkit now available to every level: **fog regions** (impassable, blank,
  unsearchable, jump-proof — three-reveal pattern shipped in the Manifold),
  the **plaque-rule family** (span must read as its plaque: Cipher → Beacon →
  Echo), the **fuel rule** (room-attr-scoped paste exception), **wards** (boss
  terminology — never "rounds"), boss state riding the undo snapshot.
- **u and `<C-r>` are both assumed held** throughout this act: redo (The
  Second Stride) is pinned to the Waypoint Sanctum's first vault chest
  (display 16). No design may rely on "undo-retry is unaffordable" — wrong-
  guess retries cost ~2 keys; force with terrain (∞) or content, or accept
  and budget for soft forcing explicitly.

## The act's arc

The player has walked (Acts I–III) and cut/copied (Act IV). Act V writes:
insert mode first (22), then change-as-one-verb (23) and its one-key
shorthands (24), then text entry from line edges and whole new rows (25),
overwriting (26), case (27), joining rows (28), and shoving lines sideways
(29–30). The Scrivener (30.1) stamps it all shut. The act's repeated image: **the dungeon is unfinished — the player
authors the missing stone.**

Engine status: the whole act is already mechanically supported (insert mode +
`'insert'` token gate, `o`/`O` real-row inserts, `A` floor-building +
buffer-doubling, `r`/`R` overwrite-in-place, `J`/`gJ` joins, `>>`/`<<`
reflow indents, `c`/`s`/`S`/`C` parse + gates). One engine task remains —
see Open Decisions #3 (`>{m}` over motion spans).

---

## 22 — The Inscription Halls (`inscription_halls`) — `i a`

**BUILT 2026-06-12** (reworked twice after playtests) — see
`generation/dungeon_gen.py::build_dungeon_inscription_halls` and
`tests/test_inscription_halls.py`. As shipped: a MEANDERING river (drifts
4 cols west, headwater to ford; water writable — ink displaces the flood;
engine changes: `insert_char` water-write + Vim-faithful Esc retreat),
prefix/suffix hard-forcing by wall/water geometry, fragment scarcity via
greedy vocab draw, FIVE exit walls (one per word, bridge-word westmost),
the `rivergate` ford finale, par 26 via the ( / ) / e sentence-hop route
(embraced after a playtest beat the walking par). Two lasting laws came
out of its playtests: Esc spends NOTHING (insert tokens cost 1 + chars —
Open Decision #4 RESOLVED) and THE LANDING RULE (engine-wide: no jump
lands where the cursor cannot stand; pressure-sweep test = the template).

---

## 23 — The Change Annex (`whole_line_annex`) — `c{m} cc s`

**BUILT 2026-06-26** (reworked twice after playtests) — see
`generation/dungeon_gen.py::build_dungeon_whole_line_annex`,
`main._whole_line_annex_tick`, and `tests/test_whole_line_annex.py`. As shipped:
a hall of MISLABELLED doors (plaque rule, 5th member — the annex RELABELS). An
OPEN block of eight lesson rows; each carries its wrong label on the floor EAST
of the spine with the right plaque set in the WEST wall. Below, a spine-only
THROAT row drops to the GATE corridor: the spine, a ROW of eight plaque-door
bolts, then the exit (plain floor, east of them). Three door kinds, three verbs,
word-first:
- **word doors** (×4) — the label is one word off inside a kept phrase; `ce`
  changes just that word (`cc` would force retyping the whole phrase).
- **line doors** (×2) — the WHOLE line is one wrong word; `cc` rewrites it. The
  cursor lands MID-row here (off the previous east-ending edit), so `cc`
  (column-agnostic) saves the `0`/`^` the old `D`/`d$` rival needs to clear from
  the line start. **Key learning: at column 0 the `D` shorthand TIES `cc`, so
  the forcing only holds with the cursor away from the start — which the
  consecutive-row block + east-ending edits provide for free.**
- **rune doors** (×2) — one fused rune (◆) stands for two letters; `s` cuts it
  and spells them out (`r` is one-for-one, `cw` overpays).

Finale is `G$` (2 keys: G to the gate row, $ east). Labels start AT the spine
column (no blank margin), so a `cc` word lands naturally aligned with every other
label — there is no optional alignment space.

**REDESIGNED 2026-06-27 — par-forcing + the `cE` length progression** (room now
15×41, ten lesson rows, par 106, budget = par + TRIGGERS − 1 = 115). Two reasons
drove it: (a) a pressure test found the old hall was clearable with NO new command
(a similar word door could be fixed by a plain `r`; ~15% of seeds — closed by the
dissimilarity gate), and worse, `c` was never actually FORCED — count-`s` ties
`ce`/`cc` for free. (b) The fix is the user's forcing philosophy: **force by PAR,
not budget.** The SIX word doors now LENGTHEN by two each row (4·6·8·10·12·14):
- 4/6/8 plain — `ce` and `{n}s` cost the same, so count-`s` is *allowed*, not a cheat.
- 10/12/14 MIXED — an internal punctuation mark (`fire-blade`). `ce` (word-class)
  stops at the mark and leaves the bolt shut; only `cE` (WORD-class) spans the whole
  token. And `{n}s` overpays the 2-digit count, so `cE` is the unique correct AND
  par-optimal tool. A count-`s` solve still WINS — it just lands over par (1★ not 2★).
- 2 line (`cc`) + 2 rune (`s`) doors round it out.
Mixed words are laid as SEPARATE runs + a bare-floor gap (a space GLYPH reads as
punctuation, so `E` would run through it — the L24 C-door fix). The compound words
embed common words, so distinctness no longer guarantees independence: `_wla_pick`
redraws against `_wla_independent`. Plaques live in a widened west wall (spine at
col 21) to hold the ~19-char targets. ENGINE FIX: a `{n}s` substitute now charges
its count digits (`budget.spend(_keystroke_cost(count))`, main.py) — it was a flat
1, which made count-`s` *cheaper* than `cE` and inverted the whole forcing.

**Four playtest laws baked in:**
1. **PLAQUE IN THE WEST WALL.** Reflow is segment-bounded in BOTH directions —
   a mid-row wall (or void rune) is a hard line boundary, so content on the far
   side of a wall is never disturbed by an edit on the other side (`open_gap`
   push and `close_gap` pull are symmetric since 2026-06-26). The plaque could
   sit east behind a bolt and stay safe; it lives in the WEST wall here for the
   OTHER two reasons — WALL cells are uncuttable (no `cc`/`D` wipes the answer
   key) and excluded from the floor scans that read each label.
2. **Nothing typed may contain a SPACE** — the admin karaoke answer matches
   keystrokes with spaces stripped as separators, so a typed space is
   unrepresentable. Hence line doors are a SINGLE word, and `room.answer` is the
   real keystroke tape (`_wla_route`/`_wla_answer`). ENGINE FIX: insert-mode typed
   chars now advance `answer_pos` too (every insert level's karaoke was silently
   desyncing once it left NORMAL mode).
3. **THE EXIT IS PLAIN FLOOR — NO GATED WALL.** (The first cut kept the exit WALL
   until solved; rejected as non-Vim. The #1 principle is Vim-faithfulness.) The
   barrier is GEOMETRY + the plaque-door bolts: the bolts stand in a row WEST of
   the exit, the spine is each row's first standable cell, the throat row joins
   the block to the gate ONLY at the spine — so every vertical jump (`G`/`L`/
   `{n}G`/`H`/`M`) lands on the reachable spine, and `$`/`0`/`|` are segment-
   bounded (they stop at the first shut bolt — `_cross_water`). No jump reaches
   the exit until the bolts honestly open. The Inscription pattern (its exit sits
   behind the river + walls for the same reason).
4. **Intro hint stays atmospheric** — names the premise, never the keystrokes.

`V`/`S`/`C` stayed out (Open Decision #2; the shorthands are §24). Two opt-outs in
`test_answer_paths.py`: `_NONSTANDARD_BUDGET` (tight) and `_ANSWER_NOT_TOKENISED`
(the `ce`/`cc`/`s` keystroke tape isn't a parseable token string). The new-level
skill (`.claude/commands/new-level.md`) gained the karaoke + hint + reflow + audit
guidance.

---

## 24 — The Change Extension (`change_extension`) — `S C`  ✅ BUILT 2026-06-26

**BUILT** on the Annex chassis (`build_dungeon_change_extension`, par 70, budget
77; finale `G$` not `02j$`; labels start AT the spine column so `S`/`C` words land
naturally aligned, no blank margin; every C door FOLLOWS an S door so the cursor
lands on the wrong tail and the route is `jC`, not `j^wC` — par dropped 78→70).
Ten plaque-door rows: 4 S doors (a single 6-letter wrong word — `S` beats
`cc` by one key), 4 C doors (a correct 4-letter prefix then a TWO-word wrong tail
→ `C` from the tail beats `c$` by one, and `ce` stops a word short; the correct
replacement is ONE word so the typed text holds no space), 1 `ce` word door and
1 `s` rune door for reinforcement. Forcing by volume: the all-old cc/c$ route is
par + 8, one past the budget (margin 7). The tick is the Annex's generic
plaque-door scan (the room sets `_wla_doors`). Intro stays atmospheric. Pinned by
`tests/test_change_extension.py` (97 tests). Two **engine fixes** shipped with it:
- **`S` is now segment-bounded like `cc`** — `engine/insert._clear_row` cleared the
  WHOLE buffer row (wiping the west-wall plaque); it now clears only the passable
  `line_extent`, so `S` == `cc` exactly (a wall-embedded plaque survives both).
- **C-door labels are laid as SEPARATE runs** with bare-floor gaps, not one run
  with a space glyph: a space glyph is read as a punctuation 'word' that `w` stops
  ON, so `j^w` would land on the space; separate runs let `w` skip the gap to the
  wrong tail. The floor scan reconstructs the space, so the target reads the same.

**The one-key shorthands.** The player owns the `c` operator (§23). `S` and
`C` are the to-the-whole-line and to-end-of-line idioms — each does in ONE
keypress what the player currently spends two on. They are gated on their own
shorthand tokens (engine precedent: `_operator_cost` charges `D`/`C`/`S` as a
single keypress via the `shorthand` tag; `command_guard` requires the token
on top of the `c` operator).

The split's whole point: `S` **is** `cc` and `C` **is** `c$`, one key cheaper
each — so a single tight-par puzzle can never force `cc` AND `S` at once (`S`
strictly dominates). Staging them as the *upgrade* lets each be forced
honestly, mirroring the Operator's Vault → Cipher Cell `d$` → `D` lineage.

Forcing model (S2 by volume — the savings are exactly 1 key/use, so margin
must be < the use count):
- `S` vs the `cc` learned last level: whole-line relabels return in greater
  number, par tuned so the `cc` path (2 keys/line) blows the budget and only
  `S` (1 key/line) clears it.
- `C` vs `c$`: a bank of doors whose labels are correct up to some column and
  wrong to the line's end — `C` from that column rewrites the tail in one key
  where `c$` overpays by one per door.
- Keep a few `c{m}`/`s` triggers scattered in so the level reinforces WHICH
  tool, not just the two new ones (the Overwrite Halls' `r`-vs-`R` discipline).
- WHOLE-LINE PAIRS MUST BE DISSIMILAR (`_draw_whole_line_pair`/`_whole_line_dissimilar`):
  a single-key volume margin is fragile — if a whole-line door's wrong/right words
  are similar (shared prefix/suffix, or Hamming < 4) a player can rewrite it with
  `r`/count-`s` for less than `cc`/`S` and bypass the lesson entirely. Pressure-test
  (2026-06-27) replay-confirmed a no-S/C win on ~0.2-1.6% of seeds (e.g. seed 1349
  `strobe`→`strong` via `4l2sng`). Fix: every whole-line pair (L23 `line`, L24
  `sline`) now differs in the FIRST and LAST char and in ≥4 positions, so the
  cheapest old-tool rewrite ties `cc`. Pinned by `test_*_resist_cheap_old_tool_edits`
  over 1000 seeds (the 5 SEEDS the rest of the suite uses all happened to be safe).

Design device: re-enter the mislabeled-door hall, now with longer labels and
whole-line corruptions — the annex taught the verb, the extension teaches the
one-key reflexes. Hand-tally par along the canonical `S`/`C` answer.

---

## 25 — The Sculpting Chambers (`sculpting_chambers`) — `I A o O`

**The topology level — the act's spectacle.** All four are insert ENTRIES:
`I`/`A` at line edges, `o`/`O` opening whole new rows.

Forcing (all four S1 / terrain-∞ where possible):
- `o`: a sealed room with NO floor connection — `o` from the row above
  inserts the connecting row. ∞ without it. (Engine: `_insert_blank_row`,
  real rows, map shifts down, fog and entities ride.)
- `O`: inside that room, a ledge sealed from below holds the exit approach —
  `O` opens the row above from within. ∞.
- `A`: **embrace A-the-builder** (the old draft predates it): `A` is the
  game's only floor-CREATING command — it positions past the line's end and
  each typed char builds floor INTO the wall (`extend_floor`), stopping at a
  void rune, doubling the buffer at the edge. Design: a key/lever pocket
  sealed in solid stone east of a corridor's end — the player must BUILD the
  corridor to it, glyph by glyph. ∞ without `A`. (Mind `_MAX_COLS`=200 and
  the edge-of-the-world message; keep the build short.)
- `I`: first-non-blank insert — the level's FINALE and the exit gate itself.
  One row is a PASSWORD: its floor shows only the TAIL of a phrase, the head
  sheared off at the west (the plaque covers the WHOLE line, not a lone word).
  After the last `A`-build the cursor sits at the far east; the player drops
  onto the password row — a DIFFERENT line, so the far-east column carries over
  — and `I` jumps to the line's start to type the missing head in one key. The
  completed line reads true and drops the exit key: the final door opens.
  NO NEW MECHANIC — this is the whole-line plaque-match (the Change Annex's
  `_wla` floor-text tick) turned into a full-line password. Budget-forced (`I`
  saves the westward walk over `^i`/`0i`); still the only soft-forced command of
  the four, but now the capstone that unifies the act rather than a side plaque.

Risks: row inserts shift everything below (constants go stale — derive all
checks from text/entities, the Manifold discipline); the par solver from the
old draft is void — hand-tally par along the canonical answer (Operator's
Vault precedent: no Dijkstra once the buffer mutates).

---

## 26 — The Overwrite Halls (`overwrite_halls`) — `R`

(Old draft taught `r`+`R`; `r` shipped at the Cipher Cell — this is now an
`R`-only lesson, and the old compact-corridor design is void.)

**Streams, not stitches.** The player owns `r` (singles) and `.` (repeat);
`R` must win where corrections run in CONSECUTIVE cells.

Forcing arithmetic (S2 — tighter multiplier, document it):
- N consecutive wrong cells: `R` + N chars + `Esc` = N+2 keys.
- Best `r`-chain: `r{c}` (2) + `l` (1) per cell − 1 = 3N−1 keys; `.` repeats
  the SAME char only, so design the runs with VARIED target chars and dot
  dies (the Echo Vault taught dot off identical fixes — this level teaches
  its limit).
- Savings 2N−3 per run; with runs of 5–7 and margin tuned (×1.2–×1.3), `R`
  is forced per-run. Singles stay scattered between runs so `r` remains the
  right tool there — the lesson is WHICH.
- Optional pressure (reuse, don't rebuild): the Manifold's ward-2
  re-corruption timer — a half-corrected stream re-rots if the player dawdles
  mid-run. Decide at build whether the first R level wants timers at all.

---

## 27 — The Case Chambers (`case_chambers`) — `~ g~ gU gu`

**Case is text the eye can't grep.** Plaques demand exact case patterns
(`VeiL` vs `veil`); doors check the span case-sensitively (they already do —
matches are exact).

Forcing (the old draft's math survives; keep):
- Clusters are single WORDs → `gUW`/`guW`/`g~W` = 3 keys each (count-free).
- All-`~` alternative on a 6-char cluster = 6 keys + cursor advances; with
  enough clusters the `~`-only path exceeds budget (old draft: par 52,
  budget 73, ~-only 74 — re-tally at build).
- `~` itself keeps single-char triggers (mixed-case sentinels) so it's used,
  not just out-priced.
- Seed variance: case patterns randomized per seed; answers must reference
  positions, not letters (the Operator's Vault rule: no letter-dependent
  keystrokes in `room.answer` except fixed bait).

---

## 28 — The Joiner's Gate (`joiners_gate`) — `J gJ`

**Pull the world up into your line.** `J` appends the row below onto the
current row with one space at the seam; `gJ` with none. (Engine: `op_join` =
`remove_row` + extend — shipped, undoable, snapshot-safe.)

**The old draft's "make J/gJ non-undoable" is REJECTED** — it contradicts
the game's undo philosophy (u is the always-on rope) and the engine.
Forcing instead:
- The JOIN itself is S1: the bridge content (a floor word the player must
  stand on / a key glyph) lives on the row BELOW a chasm row; no motion
  brings it up; only a join does. ∞ without J/gJ.
- The J-vs-gJ CHOICE is content-forced per trigger: one door's plaque is two
  words (`bind veil` — needs the seam space → `J`), another's is one fused
  word (`bindveil` → `gJ`). A wrong variant + `u` + retry costs 2–3 keys —
  budget for exactly one such retry (margin ≥ 3, < 6) and accept it: the
  PLAQUE telegraphs the answer, so the retry is the player not reading, not
  the design leaking.
- `{n}J` joins n lines — a finale beat can ask for one 3-row join (3J),
  echoing the count-dot finale of the Echo Vault.

---

## 29 — The Alignment Halls (`alignment_halls`) — `>> <<`

**Lines shove sideways.** `>>`/`<<` shift the row's text by INDENT_WIDTH=2
within the wall-bounded row (`apply_indent`; right shifts can shove tails off
brinks — that's a trap, not a bug: greedy `>>` near a void loses the plaque).

Forcing: column-alignment plaques (a lock glyph must SIT at ruler column N —
the Cipher Cell check at exact columns). Per zone, `>>` (2 keys) vs
delete-and-retype (~9 keys): savings ≈ 7/zone, 4+ zones, margin < savings.
`{n}>>` = 3 keys for n shifts — teach it on a 2-shift zone. `<<` mirrors
(over-shifted rows must come back; left dedent clamps at the wall, nothing
falls — asymmetry worth one explicit beat).

---

## 30 — The Indentation Sanctum (`indentation_sanctum`) — `>{m} <{m} =`

**The operator form — act on rows you never visit.** A bank of rows must
align; the rows between/around are WATER or void-ruled (unwalkable), so
per-row `>>` visits are impossible or unaffordable: `>{m}` (e.g. `>}` /
`>3j`) indents the whole span from one standpoint. S1 via terrain.

- **Engine prerequisite (the act's one real engine task):** verify/implement
  `>{motion}` applying `apply_indent` to every row in the motion span without
  cursor visits, plus the parser forms `>j`/`>}`/`3>>`. (`>>`/`<<` shipped at
  the single-row level on 2026-05-30.)
- `=` semantics must be DEFINED for Vimny (no filetype indent exists):
  proposal — `={m}` aligns each row in the span to the row's plaque column
  (the level's posted target), i.e. "make it read right" as one stroke; the
  finale beat. Decide at build (Open Decision #3).

---

## 30.1 — The Warden Scrivener (`warden_scrivener`) — boss

**Rebuilt on the Manifold chassis** (the old five-phase immunity table is
void): ward machine, fogged podium niches, `/W` strikes (`search_glyph_
entities` + fog discipline), `edit_immune` parry, ward counter riding the
undo snapshot, boss conventions (par=None, relaxed budget, `_SKIP_LEVELS`,
deterministic scripted fight, 1-star win).

Sketch — **"The Unfinished Manuscript"**: the hall is a half-written page;
each ward is a passage he refuses to finish, completed with one act-V verb:
  1. `i`/`a` — a plaque sentence missing its opening word (write it in).
  2. `c{m}` — his lie mid-sentence (change it true).
  3. `R` — a corrupted stream overwritten in place (re-corruption timer,
     ward-2 style, tuned).
  4. `J` — the sentence's second half stranded on the row below (join it).
  5. `>>` — the closing line out of its margin (align it; the seal column).
Five wards → hp 5; the opening ritual in the antechamber should WRITE rather
than paste (e.g. inscribe the word the lintel shows — an `i` warm-up).
Pressure: decide after the framework plays (the `_wm_pressure` lesson).
Treasure pocket behind the seal: heart + the **Whole Word** chest (the
`text_obj` drop is already wired in `_SCROLL_DROPS` and previews Act VI —
audit-correct).

---

## Open decisions (the live ones — everything else from the old draft is
resolved or rejected above)

1. **Inscription Halls trigger mechanisms vs reflow** — the i/a hard-forcing
   variants must be verified against open_gap/brink behavior live before par
   is fixed (build-time verification, designer sign-off on the variant).
2. ~~Introduce `V` (visual-line) at the Change Annex?~~ — RESOLVED 2026-06-17
   toward **no**: the Change Annex (§23) stays about the change verbs, not a
   new mode. `V`/`visual_line` remains unlisted in the curriculum.
3. **`>{m}` span-indent + `=` semantics** (engine task + design definition —
   see §30). The only engine work in the act.
4. ~~Insert-cost model confirmation~~ — RESOLVED at the Inscription Halls
   build: each typed char spends 1, **Esc spends nothing** (main's INSERT
   loop charges only `insert_char`). Pars use 1 + chars per insert.
