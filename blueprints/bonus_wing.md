# The Bonus Wing — before the final boss

> ⚠ **Pre-implementation design doc — delete-on-implement.** Delete a level's
> section when it ships; delete the file when the wing is built.
> Agreed 2026-07-16: the wing sits ON the main chain BEFORE the Warden
> Eternal — after The Hall of Echoes (display 40), pushing the final boss
> out (displays are cosmetic; slugs are the identity, so renumbering is a
> `display` edit + table regen only).

Placement: `hall_of_echoes` → **Stair Rail** → **G-Sanctum** →
**Cartographer's Table** → `warden_eternal`.

All three teach budget-safe conveniences late enough that no earlier par can
be touched (every gate token unlocks after the last golf-sensitive level;
the tight-budget Overwrite Halls stretch is long past).

---

> ✅ The Stair Rail SHIPPED as display 41 (built to the sketch: five
> east-drifting steps of fused ◆words on the exact-text chassis, each +
> landing what j strands beside; the 8_ counted drop to a gate that G
> undershoots into a chest-bearing undercroft; par 13, STANDARD ×1.4
> budget, the j^-walk (17) wins 1★; warden_eternal renumbered 41.1
> hanging off stair_rail — see `build_dungeon_stair_rail` + its tests).

## The G-Sanctum (`g_sanctum`) — the g-family

- `g_` (last non-blank), `gp`/`gP` (paste, cursor AFTER the pasted text —
  the repeated-paste idiom), `g*`/`g#` (word-under-cursor search without
  word boundaries), `gi` (INSERT at the last insert spot). Recap plaques:
  `ge`/`gE`/`gv`/`gj`/`gk`.
- **Engine: NOT built** — g_, gp/gP, g*/g#, gi all need motion/paste/search
  work. One gate token `g_family`.
- Forcing sketches: a `g*` gallery where the target word is a SUBSTRING of
  its echoes (`*` finds nothing — whole-word — while `g*` walks the chain);
  a `gp` stamp-run (paste-advance-paste beats `p l l …`); `gi` returning to
  an interrupted inscription after a forced detour.

## The Cartographer's Table (`cartographers_table`) — `zf` folds

- The Codex (14.1, SHIPPED 2026-07-16) already teaches za/zR/zM on the
  reader pane, so this level's scope shrank to CREATING folds: `zf{motion}`,
  `zo`/`zc`, and folds over a dungeon buffer (the surveyor's map diegesis —
  fold the finished wings; doors read the visible state of the table).
- **Engine: partially built** — the fold model exists in `engine/codex.py`
  (visible-rows view, closed-fold-is-one-line motion) but only for the
  read-only pane; a dungeon-buffer fold layer + a fold-state door species
  are new. Decide scope before building; the user has folds "under
  consideration", not committed.

---

## Post-wing roadmap (not this file's scope)

- Windows / tabs / buffer management — post-game (README roadmap). Includes
  `<C-w>w` pane switching (decided 2026-07-16): until that act, the Codex
  pane is deliberately MODAL — focus stays in the book until :q.
- The Surveyor's Census relic (`<C-g>` introspection family) ships as a
  scroll + zero-budget handlers, independent of the wing (see scroll drafts
  approved 2026-07-16: The Craftsman's "Census Stone").
