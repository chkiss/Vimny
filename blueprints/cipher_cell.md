# The Cipher Cell — L19 blueprint (slug `cipher_cell`)

> Pre-implementation design doc — **delete when the level ships** (LEVELS_PLAN Part 8
> convention). Written in current conventions: slug identity, `CharRun` terminology,
> `display` is cosmetic. Supersedes `blueprints/act_4.md`'s "L19 — The Whole-Line
> Annex" section, whose content now describes the Change Annex (display 23.5):
> when this ships, repoint that section's header to 23.5 and delete this file.

**Curriculum entry (already in `content/levels.py`):**
`{'display': '19', 'slug': 'cipher_cell', 'name': 'The Cipher Cell', 'commands': 's  D', 'teaches': ['s', 'D']}`

**Design decisions (locked 2026-06-10):** bolts slide open directly (no key/p
plumbing on the cipher locks) · `D` forcing is SOFT (par star; `d$` fits budget) ·
fiction is pure decay (no new character) · 4 beats.

---

## Why these two commands, here

At L19 the player knows `d`/`dd`, every motion family, `/`, marks, and visual — but
**not `i`** (insert arrives at L23) and **not `r`** (L25). So:

- **`s` is the player's only way to WRITE a character**, and their first-ever entry
  into INSERT mode. Necessity is *structural* (the act_4 reviewer's "terrain-∞
  forcing"): a gate that requires producing a character cannot be passed any other
  way. `x` deletes but cannot fill the hole — that contrast IS the lesson.
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
answer can contain them. Add parser/cost tests: `D`→1, `2D`→2, explicit `d$`→2
(unchanged). Without this, `D` and `d$` cost the same and the lesson is vacuous —
the act_4 blueprint recorded exactly this CHALLENGE and punted; this level resolves
it on the side of "the budget counts physical keypresses".

## Fiction

The prison block beneath the Operator's Vault. No jailer remains; the cells have
simply decayed. Each cell bolt is warded by a cipher word etched on its lock row —
but centuries have warped single runes into unreadable symbols (`♄`, `☠`, … from the
untypable set). The TRUE word survives as a faint plaque etched in the cell (same
word, dimmer kind). Stand on the warped rune, `s`, strike the true letter, `Esc` —
the word reads true and the bolt grinds back. The corridors are furred with crumbled
rune-residue; `D` shears a whole tail of it to the wall in one stroke, and what was
lodged behind it (a rusted key, the way on) comes loose.

## Beats (4 — one concept each)

| # | Beat | Player action | Cost (budget keys) |
|---|---|---|---|
| 1 | **Cell A** (spawn) | read plaque, navigate to the warped rune, `s` + letter (+ free `Esc`) → bolt A opens | fix = 2 |
| 2 | **Corridor of residue** | cursor to the seam after the surviving word, `D` → tail gone → rusted key drops → gold gate | wipe = 1 |
| 3 | **Cell B** | TWO adjacent warped runes → `2s` + two letters (4 keys; two single `s` fixes = 6) — count synergy | fix = 4 |
| 4 | **Final tail** | one long residue tail before the exit; `D`, walk out | wipe = 1 |

The intro message carries the `Esc` half of the lesson (the player has never left
INSERT before): e.g. `The Cipher Cell — s strikes a rune and lets you write one
true; Esc seals it.`

## Topology sketch (fixed structure; vocab + residue seeded)

Dims ≈ 13×46. Bands top→bottom, lineheads-style; fog hides everything beyond each
unopened bolt (bolts block the fog flood like closed doors).

```
##############################################
# @      opal                                #  r1  Cell A: spawn (1,2); PLAQUE 'opal' (faint kind)
#        op♄l  B─────corridor───────────╖    #  r2  LOCK ROW: cipher copy + BOLT A (wall cell, tick-opened)
######################################## ####
#   rust▒▒▓░▒▒░▓▒░       K   [gold gate]     #  r4  residue tail after 'rust'; D → key drops; p the gate
#### #########################################
#  ╟ shaft down ...                          #
#        kiln           (plaque)             #  r7  Cell B: plaque
#        k♄♄n  B────────────────────╖        #  r8  LOCK ROW: two adjacent warped runes; BOLT B
######################################## ####
#   echo░▒▓▒░▓▒▒░▒▓▒▒░▒░▓▒░             X    #  r10 final tail; D; exit
##############################################
```

(Exact columns are the builder's to fix; the structural anchors — plaque row above
lock row, bolt at the lock row's east wall, tail anchored to a surviving word — are
the spec.)

## Mechanics — one new tick, everything else exists

`_cipher_cell_tick(room, player)` in main.py, wired beside `_operators_vault_tick`,
**stateless and undo-safe** on the same principle:

- `room._cc_bolts = [(row, lo, hi, target_word, (bolt_r, bolt_c)), ...]`
  Per turn read the lock row via `engine.substitute.line_text` (the canonical
  row-as-Vim-line reader); cell at the bolt = `FLOOR` iff `text[lo:hi] ==
  target_word` else `WALL`. Opening calls `_reveal_from` (fog). Undo restores
  corrupted text + player position; the tick re-walls the bolt — consistent both
  directions, no one-shot flags (the L18 lesson).
- `room._cc_tails = [(row, threshold_col, key_drop_pos), ...]`
  No glyphs at `col ≥ threshold` → `_drop_key` at the drop position (re-drops after
  undo exactly like the vault's key economy; `_key_missing` logic reused).

Corruption glyphs come from the untypable symbol set (visibly foreign; can't be
`f`-targeted — navigate by `w`/`e`/`f` on true letters). Target words come from
`vocab_plain` (MUST be typable — the player types the fix). Cell B's word needs two
adjacent letters warped (pick words where a doubled letter reads naturally, e.g.
`kiln→k♄♄n` style; the `2s` fix writes both).

## Par / answer

Hand-derived constants `_CC_PAR` / `_CC_ANSWER` (fixed structure — operators_vault /
runic_archives precedent), validated by the universal answer-cost test. New answer
notation: `s` tokens carry their typed text — `sn` = 2 keys, `2sil` = 4 keys
(`Esc` is a real keypress but unbudgeted, and `is_sequence`, so the admin karaoke
skips it). **Extend `tests/test_answer_paths._token_ks_cost`** with an `s` rule:
`^(\d*)s(.+)$` → `len(count) + 1 + len(text)`.

Rough par shape (final numbers at build time): beat fixes 2+4, wipes 1+1, plus
navigation ≈ 14–18 → par ≈ 22–26, budget = ceil(par × 1.4).

Necessity solver `_par_cipher_cell(room, no_D=False)`: small Dijkstra over
`(position, bolts_open_bitmask, tails_cleared_bitmask)` with edit actions abstracted
(fix-at-cipher = 2 keys; wipe-at-seam = 1 with `D`, 2 without). Reuses the
`_dijkstra`/`_count_moves` toolkit.

## File checklist (deltas vs the new-level skill)

- `content/levels.py` — **done** (entry exists); rerun `_gen_curriculum_table.py`
  after ship so README flips Planned→Playable.
- `main.py` — `_operator_cost` shorthand fix (prerequisite); `_cipher_cell_tick` +
  wiring in the per-turn block; `_LEVEL_INTROS['cipher_cell']`. `--level` choices:
  nothing (derived from LEVELS).
- `generation/dungeon_gen.py` — `_CC_*` constants, `build_dungeon_cipher_cell`,
  `_par_cipher_cell`, `_CC_PAR`/`_CC_ANSWER`.
- Engine — **nothing** (`s`, `D`, guard, parser, reflow-correct substitute all ship
  today; `s` deletes then `close_gap`s, typed chars `open_gap` — a mid-word fix
  reads correctly).
- `render/vim_commands.md` — a `## cipher_cell` section: the existing `s` row moves
  under it; add a `D` row (`| D | D | delete to line end |`).
- `tests/test_answer_paths.py` — the `s` token cost rule.
- `art/_gen_wizard_wisdom.py` — poem keyed `cipher_cell` (decay voice: "where the
  rune rotted, strike one true letter…"), regenerate.
- `blueprints/act_4.md` — repoint the stale "L19 — Whole-Line Annex" header to 23.5
  (Change Annex); delete this file.
- Scrolls — **nothing** (the Operator's Codex already smudge-teases `s`, gated on
  the `s` token; it clears automatically when this level is beaten).

## tests/test_cipher_cell.py

One test per property, `SEEDS`-parametrized, reading `tests.cached_room`:
structure/dimensions · plaque-and-cipher agreement (cipher = plaque word with the
warped positions swapped to untypable symbols) · exit reachability once all gates
modeled open · `par == _par_cipher_cell(room)` · answer uses `s`, `2s`, and `D` ·
**D soft-necessity**: `_par_cipher_cell(no_D=True) == par + 2` (> par, ≤ budget —
documented soft, lineheads-style) · **s structural-necessity**: curriculum guard
`'insert' not in known_commands('cipher_cell')` and `'r' not in …` (if either is
ever taught earlier, the gate stops forcing `s` and this fails loudly) ·
**tick undo-safety**: fix word → bolt floor; restore corruption (simulating undo) →
tick re-walls; re-fix → re-opens. Budget formula: covered by the universal test.
