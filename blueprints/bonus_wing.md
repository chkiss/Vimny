# The Cartographer's Table (`cartographers_table`) — `zf` folds

> Pre-implementation design doc — delete this file when the level ships.

The rest of this wing (The Stair Rail, The Last Reach, The Buried Word, The Wet
Ink) has shipped; only the fold level is left, and it is not committed — folds
are under consideration, not agreed.

- The Binder's Reliquary already teaches `za`/`zR`/`zM` on the reader pane, so
  this level's scope is **creating** folds: `zf{motion}`, `zo`/`zc`, and folds
  over a dungeon buffer. Diegesis: a surveyor's table where you fold away the
  wings you have finished, and doors read the visible state of the table.
- **Engine: partially built.** The fold model exists in `engine/codex.py`
  (visible-rows view; a closed fold is one line to motions) but only for the
  read-only pane. A dungeon-buffer fold layer and a fold-state door species are
  both new. Decide scope before building.
- Placement: late enough that no earlier par is at risk — every gate token in
  this wing unlocks after the last golf-sensitive level.
