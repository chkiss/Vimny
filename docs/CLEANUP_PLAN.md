# Vimny — Clean-up Plan

**Execution status (2026-06-03):** A.1, B, C, D.1, **D.2**, E, F.1 — **done & committed**
(full suite green, 2432). F.2 — **already satisfied**: every `blueprints/act_*.md` already
carries a prominent "⚠ Pre-implementation design doc — obsolete conventions;
delete-on-implement" banner, so the finding was moot (corrected below). D.2 was done as a
pure prefix-drop closure `_render(msg='', **kw)` (forwards every other arg unchanged), so all
65 `run_dungeon` call sites convert behaviour-identically; the 3 `render_all` calls in
`_heart_container_animation` (outside `run_dungeon`, no closure in scope) stay direct.
G is follow-on work, not cleanup, so left out.

A codebase audit for bugs, edge cases, bloat, cruft, duplication, and doc accuracy.
Findings are ordered by category; each has a concrete location and a recommended action.
Nothing here is urgent — the codebase is healthy (2440 tests green, no TODO/FIXME, no
debug prints, no unused imports, no mutable-default-arg bugs, clean exception handling).

**Method.** Foundational engine files read in full (`world`, `player`, `budget`, `modes`,
`options`, `registers`, `jumplist`, `macro`, `vim_parser`, `search`, `substitute`, `reflow`
top). Large/editing files (`main.py` 4.6k, `dungeon_gen.py` 5.6k, `motion`, `operator`,
`editor`, `insert`, `text_object`, `renderer`) audited structurally + with an AST/grep static
pass and via their extensive test coverage (`test_motion` 770, `test_operator` 741, etc.).
Static checks: AST unused-import scan (clean), unreferenced-function scan, risk-pattern grep.

---

## A. Bugs / correctness & edge cases
No live bugs found (the recent anti-exploit and cut-undo fixes are in and tested). One
latent robustness gap:

1. **`engine/motion.py:64-67` `_reveal_from`** indexes `room.cells[nr][nc]` for each BFS
   neighbour with **no bounds check**, while its sibling `_fog_unreachable` (line 44) guards
   via `nb in foggable` (bounds-safe). Today every room has in-bounds WALL borders so the BFS
   never steps off-grid — but if any level ever places floor on row 0 / col 0 / the last
   row/col, this silently negative-index-wraparounds (`cells[-1]`) or `IndexError`s. Add the
   same `0 <= nr < room.rows and 0 <= nc < room.cols` guard for parity and safety. Low
   severity, but it's a real inconsistency between two functions that should match.

## B. Dead code (remove)
1. **`engine/player.py:48` `Player.move()`** — zero callers (all movement goes through
   `apply_motion`). Remove.
2. **`engine/search.py:16` `_first_offset()`** — orphaned by the per-line search rewrite
   (`_match_positions` now uses `_spans`). Zero references. Remove.
3. **`render/renderer.py:130` `_pad()`** — zero references. Remove.
4. **`content/levels.py` `display_number()` (83), `is_reliquary()` (147), `is_visible()` (151)**
   — zero references. Remove (confirm none are reached via getattr/string first — grep says no).
5. **`engine/world.py:73` `Room.ledge_rows`** + **`generation/dungeon_gen.py:1529`
   `composite.ledge_rows = {13, 14, 16}`** — dead no-op: `reflow.is_ledge()` is hardcoded
   `True` (overlay model retired), so `ledge_rows` membership is never read by the engine.
   Remove the field and the assignment; see also C.2 for the stale comment.

## C. Cruft / vestigial machinery
1. **`engine/budget.py` — `undo()`, `redo()`, `_history`** are vestigial. The game restores
   `budget.spent` directly from snapshots (`main._pop_history_step`) and never calls
   `budget.undo()/redo()`; `spend()` still appends to `_history`, which therefore grows
   unbounded for the session and is never read. Runtime only uses `spend`, `frozen`,
   `remaining`, `is_over`, `status_color`. **Action:** remove `undo`/`redo`/`_history` (and the
   `test_budget.py` cases that cover them) OR, if kept for a future direct-budget-undo path,
   add a comment saying so and stop appending to `_history`. Verify before deleting.
2. **`engine/world.py:73`** comment "rows that REFLOW … empty = overlay (see engine/reflow.py)"
   contradicts the retired-overlay model. Fix when removing `ledge_rows` (B.5).

## D. Duplication / bloat
1. **`main.py` guard boilerplate (×15).** The block
   `if not _action_allowed(action, player.known_commands): _push(_guard_message(...));
   message = _pool_msg(); msg_ttl = _MSG_ROTATE_TTL; render_all(...); continue`
   repeats 15 times verbatim. Extract a closure `_blocked(action) -> bool` that does the
   push+render and returns True, so call sites read `if _blocked(action): continue`.
   ~45 lines removed, one source of truth for the gate message.
2. **`main.py` `render_all(term, dungeon, player, budget, …)` (×68).** DONE. Added a
   `_render(msg='', **kw)` closure that drops the four-arg prefix and forwards everything
   else unchanged; all 65 `run_dungeon` calls now read `_render(...)`. The 3 calls inside
   `_heart_container_animation` (a module-level helper, outside the closure's scope) stay as
   direct `render_all`.
3. **`engine/substitute.py` `gg` closure (lines 168 & 450).** The capture-group getter is
   defined verbatim in `_sub_line` and `_sub_line_confirm`. Hoist to a module-level
   `_grouper(m, s, e, text)` factory.

## E. Minor / style
1. **`engine/substitute.py:173`** `except (IndexError, Exception)` is redundant — `Exception`
   subsumes `IndexError`. Narrow to `except (re.error, IndexError)` (and the sibling
   `except Exception` in `_sub_line_confirm`).
2. **`render/title.py:46`** broad `except Exception` on optional-wisdom-file load — narrow to
   `(OSError, ValueError, KeyError)`.
3. **`engine/world.py:84`** `_last_build_blocked` is set in `__post_init__` without a type
   annotation while its siblings have `: list`/`: set`. Cosmetic.

## F. Accuracy / documentation drift
1. **`engine/modes.py:11-12`** — `Mode.SEARCH` / `Mode.MACRO_RECORD` comments say
   "(Block F — … not yet wired)". Both are fully wired. Update the comments.
2. **`blueprints/act_*.md`.** DONE — followed the banner's own "delete-on-implement" rule
   for the levels that have since shipped: deleted `act_2.md` (Warden Surveyor 13.1) and
   `act_3.md` (whole file; its last remaining level, the Warden Pathfinder 17.1, shipped —
   the as-built spec now lives in `tests/test_warden_pathfinder.py` + the engine), and
   excised the §L17 (Archivist's Library) / §L37 (Spellwright's Forge) sections from the
   other acts. Every remaining blueprint section (act_4–7) is an UNBUILT level
   (L18–L36.x bosses, L38/L38.1), so they stay.
3. **Curriculum status (not a bug).** 22 of 47 levels have generators; L37 The Spellwright's
   Forge is built but its prerequisites L18–L36 (`operators_vault`, `echo_vault`, … 25 levels)
   are not, so L37 isn't reachable by normal progression yet. Track as content status, not code.

## G. Follow-on opportunities (not cleanup, noted while reading)
1. **Deferred bug-testers now buildable.** `agents/bug_testers.md` deferred `mark_setter` and
   `editor_operator` pending marks/operator coverage — both now exist (marks: Waypoint Sanctum;
   d/c/y: `engine/operator.py` + `test_operator.py`). They could be written.

---

### Suggested order (low-risk → higher-touch)
1. B (dead code) + E (style) + F.1 (stale comments) — pure deletions/edits, no behaviour change.
2. C.2 + D.3 + E.1 — small dedupe/clarity.
3. D.1 + D.2 — the `main.py` guard/render helpers (biggest readability win; touch many sites,
   so do under green tests with care).
4. C.1 (Budget vestigial machinery) — verify-then-remove; touches `test_budget.py`.
5. F.2 (blueprint banners) + G — docs/content, do whenever.

Run the full suite after each group; all changes above should be behaviour-preserving except
the explicit removals, which are dead paths.
