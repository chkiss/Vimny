# Bug Tester Personalities

Twelve player personalities used as agents to probe edge cases in the Vimny engine.
Each has a corresponding test file in `tests/test_bug_<name>.py`.

Invoke any of these as an agent by feeding it the personality description plus
the room/dungeon state you want probed.

These serve **two** purposes — don't stop at the first:
1. **Crash / edge-case probing** (the `test_bug_*.py` unit suites, minimal fixtures).
2. **Par integrity on the real levels** (see below) — DON'T MISS THIS.

---

## Par integrity (run the personas on the REAL generated levels)

`room.par` is meant to be the **true minimum keystrokes** to clear a level. A level's par
is set by its `_par_<slug>` Dijkstra solver for the *taught* command set, and
`tests/test_answer_paths.py` asserts the level's `answer` costs exactly that. The open
question those don't cover: **can a DIFFERENT playstyle (command set) reach the exit in
fewer keystrokes than par?** If yes, par is set too high.

That's what the personas are for here. To run the check on a level:

- Build the real dungeon: `generation.dungeon_gen.build_dungeon_<slug>(seed)`.
- Drive the persona's keys through `main.run_dungeon(..., player_name='p', _dungeon=d)`
  — use a **non-admin** player so command gating is realistic (the persona may only use
  commands learned by that level).
- Capture `budget.spent` the first frame the player stands on `room.exit_pos` (the win).
- Compare to `room.par`. **Any completion with `spent < par` means par is above the
  minimum — flag it.** (Init `render.colors`/`render.symbols` and stub the victory/scroll
  animations, or the win frame raises `color_rgb`.)

**Critical caveat — a par-probing persona must actually SOLVE the level.** Random
key-spam (what the unit fixtures use) almost never reaches an exit, so it tells you
nothing about par. To probe par, the persona must *navigate to the exit* using its
favoured commands (e.g. the Line Ender clearing a level with only `$`/`0`/`^`/`j`, the
Word Surfer with only `w`/`b`/`e`). Hand the agent the level geometry and let it plan the
route; then measure its keystrokes.

**Known-intentional sub-par cases (NOT bugs):** on search levels (`/ ? *`) par assumes
you type the full highlighted term, but a shorter unique prefix lands the cursor for
fewer keys — so an expert finishes under par by design (see README "par is not the
absolute minimum on search levels"). Anything else under par is a real par-too-high bug.

---

## The Berserker

## The Berserker
**File:** `tests/test_bug_berserker.py`

Kills everything before moving anywhere.

Uncovers: combat ordering/HP edge cases, warden spawn uid, _on_kill key drops,
enemy chase radius, shield cleanup.

---

## The Boundary Prober
**File:** `tests/test_bug_boundary_prober.py`

Moves to corners, edges, and extreme cells.

Uncovers: $-at-end, 0-at-start, w/b/e with no runes, G with None exit_pos,
fog covering entire row, and gg/G teleport behavior.

---

## The Count Maniac
**File:** `tests/test_bug_count_maniac.py`

Spams large counts everywhere.

Uncovers: count parsing edge cases (30l, 0 ambiguity), motion clamping at
room boundaries, and _keystroke_cost formula for extreme counts.

---

## The Dot Repeater
**File:** `tests/test_bug_dot_repeater.py`

Uses . (repeat last change) everywhere.

Uncovers: . before any change, count-dot count-override, last_change
copy semantics, which actions set/don't set last_change, dot gating.

---

## The Find Repeater
**File:** `tests/test_bug_find_repeater.py`

Lives on f/F/t/T and repeats with ;/,.

Uncovers: ; with no prior f, , reversal, t adjacent-char noop, F through
wall, count-f, last_f update semantics.

---

## The Line Ender
**File:** `tests/test_bug_line_ender.py`

Obsessed with $, 0, and ^. Never uses h or l if a line-end command will do.

Uncovers: fog/locked_door blocking $, water passability, count-$,
keystroke cost formula, ^ fallback to leftmost when no rune.

---

## The Pacifist
**File:** `tests/test_bug_pacifist.py`

Navigates past enemies without ever engaging them.

Uncovers: which entities block l/$ and which don't, fog blocking motion,
wall stopping f-scan, boundary passability.

---

## The Register Hoarder
**File:** `tests/test_bug_register_hoarder.py`

Pastes clipboard content everywhere unusual.

Uncovers: p vs P direction, empty register, wrong item type, key lookup order,
action_allowed gating for paste.

---

## The Undo Abuser
**File:** `tests/test_bug_undo_abuser.py`

Spams u and Ctrl-R constantly.

Uncovers: undo/redo restoring entities and fog, undoing past stack limit,
snapshot copy semantics, and redo invalidation.

---

## The Word Surfer
**File:** `tests/test_bug_word_surfer.py`

Defaults to w/b/e for all navigation — never uses h/l if a word motion reaches.

Uncovers: w/b/e through rune clusters, void rune skipping, count-word,
b-at-first-rune, w-blocked-by-wall.

---

## The Mark Setter
**File:** `tests/test_bug_mark_setter.py`

Sets marks everywhere and jumps between them.

Uncovers: `m{reg}` populating `player.marks`, `` ` `` (exact) vs `'` (first-non-blank)
jumps, unset-mark no-ops, mark jumps recording the jumplist (Ctrl-o), mark overwrite.

---

## The Editor Operator
**File:** `tests/test_bug_editor_operator.py`

Hammers the edit-mode d/y/c range primitives (engine/editor.py).

Uncovers: `_ed_range_items` read-only vs `_ed_delete_range` mutation, dw/d$ capture,
dd row-clear + exit_pos reset, the run-start-keyed range granularity (a run straddling
the range start survives), `_ed_cut` mid-run split, merge-after-cut, and
snapshot/restore (ed_undo) deep-copy.
