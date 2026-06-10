# The Cipher Cell — L19 blueprint (slug `cipher_cell`)

> Pre-implementation design doc — **delete when the level ships** (LEVELS_PLAN Part 8
> convention). Written in current conventions: slug identity, `CharRun` terminology,
> `display` is cosmetic. Supersedes `blueprints/act_4.md`'s "L19 — The Whole-Line
> Annex" section, whose content now describes the Change Annex (display 23.5):
> when this ships, repoint that section's header to 23.5 and delete this file.

**Curriculum entry (`content/levels.py`, updated 2026-06-10):**
`{'display': '19', 'slug': 'cipher_cell', 'name': 'The Cipher Cell', 'commands': 'r  D', 'teaches': ['r', 'D']}`

**Design decisions (locked 2026-06-10):** the level teaches **`r`**, not `s` — a
substitution cipher is one-for-one overwrite, which is exactly `r` (in-place, no
reflow shift; vimtutor itself teaches `r` before the change family). `s` ≡ `cl`
moved to its true family at the Change Annex (23.5, with `S` ≡ `cc` and `C` ≡ `c$`);
the Overwrite Halls (25) keep `R` alone. Other locks: bolts slide open directly ·
`D` forcing is SOFT (par star; `d$` fits budget) · fiction is pure decay · 4 beats.

---

## Why these two commands, here

At L19 the player knows `d`/`dd` and every motion family — but **no writing tool**:
`i` arrives at L23, `s`/`c` at 23.5, `R` at 25. So:

- **`r` is the player's only way to produce a character.** `x` deletes a warped
  rune but leaves a hole nothing can fill — that contrast IS the lesson. The one
  leak to seal by design: `x` + `p` could transplant a true letter from elsewhere,
  so (a) plaques sit in **wall-sealed niches** (visible — this level does not call
  `_fog_unreachable` — but unreachable), and (b) the lock words' true letters
  appear **nowhere reachable** (a vocab-selection constraint at build time;
  corridor residue is untypable symbols anyway). With both, `r`-necessity is
  structural (the act_4 reviewer's "terrain-∞ forcing"), not budget arithmetic.
- **`D` ≡ `d$`** semantically, so its forcing is soft by design (precedent:
  lineheads' `G` vs count-`j`): par assumes `D`; a `d$`-only run still fits the
  ×1.4 budget but loses the 2-star.

## Engine prerequisite — charge `D` as ONE keystroke

`_operator_cost` (main.py) currently prices the action dict (`op:'d'` + `motion:'$'`
= 2) even when the player pressed a single `D`. The parser already tags
`action['shorthand'] = 'D'/'C'`. Fix, before the builder lands:

```python
    if 'shorthand' in action:          # D / C — one physical keypress
        return (len(str(count)) if count > 1 else 0) + 1
```

Safe: `D`/`C` are guard-gated until their lessons, so no existing level's par or
answer can contain them. Add cost tests: `D`→1, `2D`→2, explicit `d$`→2 (unchanged).
Without this, `D` and `d$` cost the same and the lesson is vacuous — the act_4
blueprint recorded exactly this CHALLENGE and punted; this resolves it on the side
of "the budget counts physical keypresses".

## Fiction

The prison block beneath the Operator's Vault. No jailer remains; the cells have
simply decayed. Each cell bolt is warded by a cipher word etched on its lock row —
but centuries have warped single runes into unreadable symbols (`♄`, `☠`, … from the
untypable set). The TRUE word survives on a plaque sealed behind niche glass in each
cell (readable, untouchable). Stand on the warped rune, strike the true letter over
it — `r` + letter, the stone overwritten in place — and the word reads true; the
bolt grinds back. The corridors are furred with crumbled rune-residue; `D` shears a
whole tail of it to the wall in one stroke, and what was lodged behind it (a rusted
key, the way on) comes loose.

## Beats (4 — one concept each)

| # | Beat | Player action | Cost (budget keys) |
|---|---|---|---|
| 1 | **Cell A** (spawn) | read the niche plaque, navigate to the warped rune, `r` + letter → bolt A opens | fix = 2 |
| 2 | **Corridor of residue** | cursor to the seam after the surviving word, `D` → tail gone → rusted key drops → gold gate | wipe = 1 |
| 3 | **Cell B** | a DOUBLED letter warped twice-adjacent (`mo♄♄` for `moss`) → `2rs` fixes both in 3 keys (two single `r`s = 5: `rs l rs`) — count synergy, and it rhymes with the art rules' "substitute both of a doubled pair" | fix = 3 |
| 4 | **Final tail** | one long residue tail before the exit; `D`, walk out | wipe = 1 |

No mode is ever entered — `r` stays in NORMAL (its defining property vs the change
family; the status line never flickers). Intro message carries the grammar:
`The Cipher Cell — r strikes one true rune over the false; D shears the rot to the wall.`

## Topology sketch (fixed structure; vocab + residue seeded)

Dims ≈ 13×46. Bands top→bottom, lineheads-style. No `_fog_unreachable` (the sealed
plaque niches must be visible); bolts are wall cells, so the way on is simply shut
until the word reads true.

```
##############################################
# @     ▐opal▌                               #  r1  Cell A: spawn (1,2); PLAQUE in sealed niche
#        op♄l  B─────corridor───────────╖    #  r2  LOCK ROW: cipher copy + BOLT A (wall cell, tick-opened)
######################################## ####
#   rust▒▒▓░▒▒░▓▒░       K   [gold gate]     #  r4  residue tail after 'rust'; D → key drops; p the gate
#### #########################################
#  ╟ shaft down ...                          #
#       ▐moss▌                               #  r7  Cell B: plaque (doubled-letter word)
#        mo♄♄  B────────────────────╖        #  r8  LOCK ROW: two adjacent warped runes; BOLT B
######################################## ####
#   echo░▒▓▒░▓▒▒░▒▓▒▒░▒░▓▒░             X    #  r10 final tail; D; exit
##############################################
```

(Exact columns are the builder's to fix; the structural anchors — sealed plaque
above its lock row, bolt at the lock row's east wall, tail anchored to a surviving
word, true letters absent from all reachable text — are the spec.)

## Mechanics — one new tick, everything else exists

`_cipher_cell_tick(room, player)` in main.py, wired beside `_operators_vault_tick`,
**stateless and undo-safe** on the same principle:

- `room._cc_bolts = [(row, lo, hi, target_word, (bolt_r, bolt_c)), ...]`
  Per turn read the lock row via `engine.substitute.line_text` (the canonical
  row-as-Vim-line reader); cell at the bolt = `FLOOR` iff `text[lo:hi] ==
  target_word` else `WALL`. Undo restores corrupted text + player position; the
  tick re-walls the bolt — consistent both directions, no one-shot flags (the L18
  lesson).
- `room._cc_tails = [(row, threshold_col, key_drop_pos), ...]`
  No glyphs at `col ≥ threshold` → `_drop_key` at the drop position (re-drops after
  undo exactly like the vault's key economy; `_key_missing` logic reused).

Corruption glyphs come from the untypable symbol set (visibly foreign; can't be
`f`-targeted — navigate by `w`/`e`/`f` on true letters). Target words come from
`vocab_plain` (typable — the player types the replacement letters). `r` overwrites
in place (no reflow — correct Vim), so the word never shifts while being fixed.

## Par / answer

Hand-derived constants `_CC_PAR` / `_CC_ANSWER` (fixed structure — operators_vault /
runic_archives precedent), validated by the universal answer-cost test. Answer
notation: `r` tokens carry their letter — `rn` = 2 keys, `2rs` = 3 keys. **Extend
`tests/test_answer_paths._token_ks_cost`** by adding `r` to the find-family regex
(`_FT_RE`: `[fFtT]` → `[fFtTr]` — identical cost shape). No INSERT, no `Esc`, no
karaoke complications.

Rough par shape (final numbers at build time): fixes 2+3, wipes 1+1, plus
navigation ≈ 14–18 → par ≈ 21–25, budget = ceil(par × 1.4).

Necessity solver `_par_cipher_cell(room, no_D=False)`: small Dijkstra over
`(position, bolts_open_bitmask, tails_cleared_bitmask)` with edit actions abstracted
(fix-at-cipher = 2 keys, double-fix = 3; wipe-at-seam = 1 with `D`, 2 without).
Reuses the `_dijkstra`/`_count_moves` toolkit.

## File checklist (deltas vs the new-level skill)

- `content/levels.py` — **done** (L19 `r D`; `s` → Change Annex; Overwrite Halls →
  `R` alone; tables regenerated). Rerun `_gen_curriculum_table.py` after ship so
  README flips Planned→Playable.
- `render/vim_commands.md` — **done** (`## cipher_cell` section with `r{c}`/`D`;
  `s` row under the annex; overwrite section is `R`-only).
- `main.py` — `_operator_cost` shorthand fix (prerequisite); `_cipher_cell_tick` +
  wiring in the per-turn block; `_LEVEL_INTROS['cipher_cell']`. `--level` choices:
  nothing (derived from LEVELS).
- `generation/dungeon_gen.py` — `_CC_*` constants, `build_dungeon_cipher_cell`,
  `_par_cipher_cell`, `_CC_PAR`/`_CC_ANSWER`.
- Engine — **nothing** (`r` via `replace_chars`, `D` via the shorthand tag, guard
  and parser all ship today; `r` on count `2r{c}` writes the char twice — exactly
  the Cell B fix).
- `tests/test_answer_paths.py` — add `r` to `_FT_RE`.
- `art/_gen_wizard_wisdom.py` — poem keyed `cipher_cell` (decay voice; the line
  "r swaps one letter and stays put" retired from the Overwrite Halls poem is the
  seed), regenerate.
- `blueprints/act_4.md` — repoint the stale "L19 — Whole-Line Annex" header to 23.5
  (Change Annex — which now also teaches `s`); delete this file.
- Scrolls — **nothing required** (the Operator's Codex smudge-teases `s`, which now
  clears at the annex — still truthful. Optional: a future `r` tease line gated on
  the `r` token).

## tests/test_cipher_cell.py

One test per property, `SEEDS`-parametrized, reading `tests.cached_room`:
structure/dimensions · plaque-and-cipher agreement (cipher = plaque word with the
warped positions swapped to untypable symbols) · **true-letter scarcity** (each
lock word's true letters appear on no reachable cell — the x/p leak stays sealed) ·
plaque niches unreachable (BFS) · exit reachability with all gates modeled open ·
`par == _par_cipher_cell(room)` · answer uses `r`, `2r`, and `D` ·
**D soft-necessity**: `_par_cipher_cell(no_D=True) == par + 2` (> par, ≤ budget —
documented soft, lineheads-style) · **r structural-necessity**: curriculum guard
(`'insert'`, `'s'`, `'c'`, `'R'` all NOT in `known_commands('cipher_cell')` — if any
is ever taught earlier, the gate stops forcing `r` and this fails loudly) ·
**tick undo-safety**: fix word → bolt floor; restore corruption (simulating undo) →
tick re-walls; re-fix → re-opens. Budget formula: covered by the universal test.
