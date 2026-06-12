# Act V Blueprints — The Writers (displays 22 → 28.1)

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
  audit walking from adjacent rows); reflow laws (open_gap shifts the whole
  buffer row across walls; brinks eat shoved content).
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
insert mode first (22), then change-as-one-verb (22.5), then text entry from
line edges and whole new rows (23), overwriting (24), case (25), joining
rows (26), and shoving lines sideways (27–28). The Scrivener (28.1) stamps it
all shut. The act's repeated image: **the dungeon is unfinished — the player
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

## 22.5 — The Change Annex (`whole_line_annex`) — `c{m} cc s S C`

(Absorbs the old act_4.md §L23.5 — that section is deleted; `dd` shipped at
the Operator's Vault, `D` at the Cipher Cell.)

**Change is delete + insert in one breath.** Plaque rule again: spans hold
the WRONG word; the door wants the right one. `c{m}` clears the span and
drops into insert atomically.

Forcing model:
- `c{m}` vs `d{m}` + `i`: saves exactly 1 key per change. Force by volume —
  N change-triggers with margin < N — or by terrain: a `d` cut reflows the
  row (close_gap pulls the tail left past the cut) BEFORE the insert, so a
  d-then-i rewrite lands the new word against SHIFTED neighbors and breaks
  an adjacent plaque; `c` holds the gap open until Esc. **Verify which model
  the engine implements for `c` (gap-hold vs delete-then-insert) — if `c`
  reflows identically, use volume-forcing only.**
- `s` (= `x` + `i`, 1 key cheaper per single-char fix), `S` (= `cc`), `C`
  (= `c$`): shorthands charged as ONE key (engine precedent: `_operator_cost`
  charges `D` as one keypress; `C`/`S` gated on this level's tokens).
  Teach as idioms; force `s` and `C` by volume where natural, accept `S` as
  a demonstrated companion.
- Old draft floated introducing `V` (visual-line) here with a `visual_line`
  token — **still optional**; decide at build (Open Decision #2).

Design device: a hall of mislabeled doors — every label is one word off
("lock" where the door wants "veil"); the annex re-labels them.

---

## 23 — The Sculpting Chambers (`sculpting_chambers`) — `I A o O`

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
- `I`: first-non-blank insert — a plaque word must gain a prefix at the
  line's start while the cursor is far right after the `A` work; `I` jumps +
  inserts in one key. Budget-forced (savings per use > margin); the only
  soft-forced command of the four — acceptable in this company.

Risks: row inserts shift everything below (constants go stale — derive all
checks from text/entities, the Manifold discipline); the par solver from the
old draft is void — hand-tally par along the canonical answer (Operator's
Vault precedent: no Dijkstra once the buffer mutates).

---

## 24 — The Overwrite Halls (`overwrite_halls`) — `R`

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

## 25 — The Case Chambers (`case_chambers`) — `~ g~ gU gu`

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

## 26 — The Joiner's Gate (`joiners_gate`) — `J gJ`

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

## 27 — The Alignment Halls (`alignment_halls`) — `>> <<`

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

## 28 — The Indentation Sanctum (`indentation_sanctum`) — `>{m} <{m} =`

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

## 28.1 — The Warden Scrivener (`warden_scrivener`) — boss

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
2. **Introduce `V` (visual-line) at the Change Annex?** Old draft said yes
   (token `visual_line`); curriculum currently doesn't list it. Decide when
   the annex is designed.
3. **`>{m}` span-indent + `=` semantics** (engine task + design definition —
   see §28). The only engine work in the act.
4. ~~Insert-cost model confirmation~~ — RESOLVED at the Inscription Halls
   build: each typed char spends 1, **Esc spends nothing** (main's INSERT
   loop charges only `insert_char`). Pars use 1 + chars per insert.
