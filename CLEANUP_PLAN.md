# Vimny Clean-up Plan

> ⏳ **DELETE OR UPDATE BY 2026-06-11** (7 days from 2026-06-04). This is a working
> record of a completed cleanup pass — once the branch has landed, delete it (or fold
> any still-relevant "left as-is" notes into `docs/ARCHITECTURE.md`).

Status: **EXECUTED** (2026-06-04). The review below was carried out, then the
safe/high-value items were applied. Full suite green throughout (2468 → 2460
passing; the −8 are the removed `status_color`/`_last_content_col` tests).

Legend: 🔴 inaccuracy/bug · 🟡 duplication · 🟢 streamlining · ⚪ note/question

---

## Execution log

**Applied (dead code removed):**
- `at_exit` (main.py ×3) — write-only flag.
- `status_color` (budget.py) + its 7 tests + docstring mention.
- `_last_content_col` (insert.py) + its test + the test import.
- `input_buf` (player.py) — verified unused across the tree.
- `render/symbols.py` glyphs: `WALL_SOLID`, `WALL_SHADE1/2/3`, `ENEMY_GUARD`, `BOSS`,
  `EXPLOSION`, `DOOR_OPEN`, `RUNE_ANCIENT/VERDANT/VOID/EMBER`, `BOX_BT/TT/X` (grep-confirmed no consumer).
- `room_gen.py` `interior_cols/rows`; `dungeon_gen.py` dead locals (345/377/639/669);
  `renderer.py` `room_display_rows/cols`; `parent_dir.py` `ENTRIES`; `title.py` `FRAME_W`
  + redundant lines 347-348; `vim_parser.py` dead `\x09` test.

**Applied (inaccuracy fixed):**
- `insert.py` `insert_char` docstring rewritten (overlay→reflow; `else` branch noted unreachable).

**Applied (streamlining):**
- `Room._on_entity_destroyed(ent)` (world.py) — collapses the landmark-reset rule from **6 sites** (reflow ×2, operator ×1, editor ×3).
- `render/netrw_chrome.py` — shared border / status bar / listing row / banner / bottom statusline for overworld + parent_dir + scroll_library. **Verified byte-identical** render output before/after via a fake-terminal capture diff.
- `vimregex.finditer` now delegates to `match_iter` + `eff_span`.
- `options.apply_set` now reuses `parse_modifier` for the affix grammar.
- `operator._cursor_to_line_start` + `INDENT_WIDTH` — collapses the "cursor → line start" idiom (operator ×3, visual ×1); visual's magic `2` → `INDENT_WIDTH`.
- `motion._flood_reachable` — shared door-blocked BFS behind `_fog_unreachable` + `_reveal_from`.

**Applied later (supervised, generation — accepts par changes, full suite re-validated):**
- 🟢 **rune-glyph unification** (#4) — `room_gen.RUNE_CHAR` is now the single source (ember unified to `⊙`); `dungeon_gen` and `main.py`'s `:rune` import it. Four duplicate glyph maps + 3 hand-placed `◦` embers collapsed to one.
- 🟢 substitute `_sub_line`↔`_sub_line_confirm` core-share (`_sub_line_core` + 9 new confirm-flow tests), `run_global`↔`_split_sep` (`_scan_field`), `_first_nonblank_col`→`_first_glyph_col` rename, reflow `_shift_rows`, editor `_split_run_at` — all done.
- 🟢🟢 **rune-scatter normalization** — one greedy `_scatter_row` (gap 1, length 1–7 all kinds, clamp-to-fit, no consecutive length-1, no density knob) behind `_place_runes_in_room`/`_make_rune_corridor`/`_cataracts_place_zone`/`_tile_line_hall`; cataracts gained ember; first cave keeps void + `_carve_void_path` guarantees solvability. WORD Forge's 2–3 gap kept (w≡W pedagogy). first_cave par rose (sparse → dense field) — flagged.

**Also applied:**
- `room_gen._place_clusters` (+ `RUNE_TYPES`, the `density`/`dungeon_level` plumbing, and the now-unused `CharRun` import) **deleted** — dead output (callers only used `make_room`'s `.cells`; zero observable change, suite green).
- `scrolls.py` docstring: stale `('v_sight',)` line-kind removed (unused anywhere).
- Orphaned-builder check ran: **no orphan `build_dungeon_*`** (the 25 LEVELS-without-builder are future/unimplemented curriculum entries, not dead code).

**Applied later still (par-solver toolkit + cheese audit):**
- 🟢🟢 **dungeon_gen par-solver toolkit** (#3) — DONE. Extracted `_dijkstra`/`_bfs`/`_count_moves`/`_row_segment`/`_word_motion_chain` and rewired **8 solvers** (`_bfs_par`, `_bfs_par_line`, `_dijkstra_par_count`, `_par_counting_crypts`, `_dijkstra_par_wbe`, `_dijkstra_par_ftFT`, `_dijkstra_par_WBE`, `_par_backward_vaults`); each verified par+answer **byte-identical** across all levels × 5 seeds + `par_audit` clean. Net −260 lines. The analytic (`goblin_gauntlet`, `wardens_keep`) and bespoke-motion (`%`, `H/M/L`, `/search`, sentence) solvers are intentionally NOT on the toolkit.
- `tools/cheese_audit.py` (new) — key/door-aware "is par the true minimum over the full learned motion set?" audit; found + fixed cheeses in `sentence_corridor` (void trap line) and `waypoint_sanctum` (water moat). All key/door levels now clean.

**Also applied (cleanup tail):**
- ⚪/🔴 **motion scan-blocker `seal_door` inconsistency** — FIXED. `_cross_water` ($/0/^) now blocks `seal_door` like `f/F/t/T` and fog; behaviour-preserving (current levels already fog the seal column), suite green.
- 🟢 editor `_serialize_room`/`_deserialize_room` cell codec — collapsed to one `_CELL_CODE` (+ derived `_CODE_CELL`).

**Left as-is (diminishing returns):**
- 🟢 motion word-motions (w/b/e/W/B/E) internal repetition — delicate, Vim-faithful, correct as-is; dedup risks edge-case regressions tests may miss. Poor risk/reward.
- 🟢 tests/ fixture duplication (`_room`/`_bare_room`/… across 10-15 files) → a conftest — real but test-only and high-churn (fixtures differ subtly per file). Low value.

---

## Deletion recommendations — VERDICTS

The four you asked me to mull, after the full read-through:

1. **`at_exit` (main.py 1492 / 2156 / 2830)** — ✅ **DELETE (valid).** Assigned three times, read zero times — a write-only flag superseded by `won`. (main.py is outside this review's edit scope, but the verdict holds; removal is 3 lines.)
2. **`status_color` (engine/budget.py:24)** — ✅ **DELETE (valid), with its test.** No production caller. It colors by *remaining* (≤1 crit / ≤3 low), but the renderer already colors the budget by *spent-vs-par* inline (renderer.py 252-260) — a different model. `status_color` is the orphaned/superseded one. (Alternative: wire it into the renderer and drop the inline logic — but that changes the on-screen coloring model, so deletion is the conservative call.) Test: test_budget.py 87-117.
3. **`_last_content_col` (engine/insert.py:19)** — ✅ **DELETE (valid), with its test.** Not imported by main.py, unused elsewhere in insert.py, referenced only by test_insert.py. `begin_insert`'s `A` uses `_rightmost_passable` instead. Test: test_insert.py `test_last_content_col` + the import on line 8.
4. **`render/symbols.py` dead glyphs** — ✅ **DELETE (valid).** Confirmed against renderer.py: walls render as a colored space, runes from `ru.symbols`, warden as `'W'`, open doors as floor. No consumer for: `WALL_SOLID`, `WALL_SHADE1/2/3`, `ENEMY_GUARD`, `BOSS`, `EXPLOSION`, `DOOR_OPEN`, `RUNE_ANCIENT/VERDANT/VOID/EMBER`, `BOX_BT/TT/X`. (Keep `FLOOR`/`CORRIDOR` — not vulture-flagged; verify before touching.)

### New deletion candidates found this pass
- ✅ `room_gen.py` `interior_cols`/`interior_rows` (21-22) — unused locals.
- ✅ `dungeon_gen.py` dead locals — 345 `rows_l`, 377 `attempt`, 639 `rows_l`, 669 `attempt`.
- ✅ `render/renderer.py` `room_display_rows`/`room_display_cols` (288-289) — unused locals.
- ✅ `render/parent_dir.py` `ENTRIES` (10) — dead module alias.
- ✅ `render/title.py` `FRAME_W` (12) — dead constant; lines 347-348 redundant (overwritten by 349-350).
- ⚪ `engine/player.py` `input_buf` (42) — vulture-flagged; VERIFY against main.py before deleting (vim_parser takes the buffer as an arg; this field may be vestigial — not yet confirmed).

## Top streamlining priorities (highest payoff first)
1. 🟡🟡 **`Room._on_entity_destroyed(ent)`** — collapses the "reset exit_pos/spawn_pos on destroy" rule duplicated **6×** (reflow ×2, operator ×1, editor ×3). Smallest change, broadest reach, low risk.
2. 🟡🟡 **`render/netrw_chrome.py`** — extract the status bar + `border_h`/`_row`/`_hdr`/`_div` + header block shared (often verbatim) by parent_dir.py, scroll_library.py, overworld.py.
3. 🟢🟢 **dungeon_gen.py par-solver toolkit** — shared motion-expansion primitives (count-`hjkl`, `$`/`0`/`^` segment scan, `_w`/`_b`/`_e`, `_push` relaxation) + generic state-space Dijkstra to deduplicate the many `_par_<slug>`/`_bfs_par_*`/`_dijkstra_par_*`. Biggest LOC win but par-integrity-critical — gate behind the per-level tests + par_audit.
4. 🟢 unify the rune-glyph source (room_gen.RUNE_TYPES / dungeon_gen._RUNE_CHAR / symbols.RUNE_* — three copies, inconsistent ember glyph).
5. 🟢 smaller dedups: `options.apply_set`↔`parse_modifier`; vimregex `finditer`↔`match_iter`↔`eff_span`; `substitute._sub_line`↔`_sub_line_confirm`; the "cursor → line start" idiom (operator/visual); the rune-scatter placers (dungeon_gen/room_gen).

## Inaccuracies (docs/comments that mislead)
- 🔴 `insert.py` `insert_char` docstring (104-107): "Overlay rows (the default everywhere) overwrite the cell in place" — backwards; overlay was retired, reflow is universal (`is_ledge` always True). The `else` overwrite branch (117-118) is currently unreachable.
- ⚪ `scrolls.py` docstring lists a `('v_sight',)` line-kind no scroll uses.

## Coverage of this review
Read line-by-line: all of engine/, content/, render/, save/, tools/, generation/room_gen.py, and dungeon_gen.py lines 1-1170 + tail. dungeon_gen.py middle (~1170-5680) surveyed structurally (it is N repetitions of the same builder+solver shape; findings apply file-wide). main.py excluded per the goal. tests/ swept where tied to flagged code (see note). No edits were made — this is a plan only.

---

## Findings by file

### engine/ (foundational)
- `modes.py` — clean.
- `player.py` — ⚪ `input_buf` (line 42) vulture-flagged; verify it's read/written (candidate if not).
- `budget.py` — ⚪ `status_color` (24) deletion candidate; confirmed no production caller (tests only).
- `registers.py` — clean.
- `jumplist.py` — clean (`_CAP+1` in jump_back is intentional: stashes current pos).
- `macro.py` — clean.
- `options.py` — 🟡 `apply_set` (80-91) re-implements the `?!&`/`inv`/`no` suffix/prefix parsing that `parse_modifier` (32-48) already encodes. Consolidate to one parser.
- `command_guard.py` — clean (action_allowed/guard_message token overlap is inherent).
- `vim_parser.py` — 🟢 trivial: line 215 `ch == '\t' or ch == '\x09'` — `\t` *is* `\x09`; second test is dead.
- `text_object.py` — clean. ⚪ `iW`/`aW` unhandled (line 297 only `'w'`); likely intentional scope.
- `motion.py`:
  - 🟡 `_fog_unreachable` (22-48) and `_reveal_from` (51-73) are near-duplicate door-blocked BFS floods over FLOOR/CORRIDOR/WATER. Factor a shared `_flood_reachable(room, start, blocked_kinds)`.
  - ⚪/🔴 **Inconsistent scan-blocker sets** across motions — verify intended:
    - fog/reveal block: `door, locked_door, seal_door, boss_seal`
    - `_cross_water` (used by `$`/`0`/`^`) blocks: `locked_door, shield, boss_seal` (NOT `door`, NOT `seal_door`)
    - `_apply_find` `_SCAN_BLOCK` (f/F/t/T) blocks: `shield, locked_door, seal_door, boss_seal` (NOT `door`)
    Should `$`/`0`/`^` stop at a `seal_door`? The omission looks accidental.
  - 🟢 word motions (w/b/e/W/B/E, lines 309-548) are long and internally repetitive (cluster-scan logic restated); the left-scan in `0` (255-258) and `^` (275-278) is identical. Factoring possible but delicate (Vim-faithful) — low priority / handle with care.
- `search.py` — clean.
- `vimregex.py` — 🟢 `VimPattern.finditer` (52-62), `match_iter` (69-78), `eff_span` (80-84) repeat the advance rule + span computation; `finditer` could delegate: `for m in self.match_iter(s): yield self.eff_span(m)`.
- `reflow.py` — 🟢 `_insert_blank_row`/`remove_row` are mirror inverses sharing row-shift boilerplate (modest dedupe via a `_shift_rows` helper). 🟡 "entity destroyed → reset exit/spawn" rule duplicated (see operator.py).
- `operator.py`:
  - 🟡🟡 **"entity destroyed → reset exit_pos/spawn_pos"** — see editor.py; now **6 occurrences** total. TOP dedup target.
  - 🟡 "cursor → line start" idiom (`player.row=min(...); ext=line_extent; player.col=ext[0]...`) repeats in op_delete (161-163, 179-182) and op_case (274-277). Extract `_cursor_to_line_start`.
- `visual.py` — clean. 🟢 `>`/`<` (139-140) repeats the cursor→line-start idiom; `amount = 2` (135) is a magic number — use `operator.INDENT_WIDTH`.
- `insert.py`:
  - ✅ **`_last_content_col` (19-22) is dead** — not imported by main.py, unused in-file, only test_insert.py. DELETE (with its test).
  - 🔴 `insert_char` docstring (104-107) is INACCURATE: claims "Overlay rows (the default everywhere) overwrite the cell in place." Overlay was retired (2026-05-30); `is_ledge` is hardcoded True so reflow is universal. The `else` overwrite branch (117-118) is currently unreachable (kept only via the `reflow.is_ledge` future-hook). Fix the docstring; decide whether to keep the dead else-branch.
  - 🟢 every `is_ledge(...)` call site (here line 111, operator op_delete 176) is a guard that's always True — vestigial, but `reflow.is_ledge` docstring says it's an intentional future hook (task #15). Leave, but note.
- `editor.py`:
  - 🟡🟡 the entity-destroy/reset rule is here 3× (`_ed_cut` 60-63, `_ed_clear_row` 153-157, `_ed_delete_range` 184-188) — total **6 across the codebase** (also reflow ×2, operator ×1). Consolidate into one `Room` method; biggest single dedup win.
  - 🟢 `_ed_cut`'s char-run splitting (44-56) duplicates `insert._delete_at` (25-35) logic (split a run around one cell); could share a `_split_run_at` helper.
  - ⚪ `_serialize_room`/`_deserialize_room` cell_map is defined twice (inverse dicts, 210-211 & 232-233) — fine, but could derive one from the other.
- `substitute.py`:
  - 🟢 `_sub_line` (167-195) and `_sub_line_confirm` (438-467) duplicate most of the match-iterate / tp-kp build / tail logic — share a core (the confirm q/a/l flow is the only real delta).
  - 🟢 `run_global` inline pattern split (514-521) re-implements `_split_sep`'s backslash-aware separator scan.
  - 🟡 naming collision/confusion: `motion._first_non_blank_col` vs `substitute._first_nonblank_col` (and text_object uses its own). Different semantics, near-identical names. Consolidate or rename clearly.

### engine/ deletion-candidate verdicts (from this pass)
- `_last_content_col` (insert.py) — **DELETE** (orphan, tests-only).
- `status_color` (budget.py) — still tests-only; verdict deferred to final section.
- `input_buf` (player.py) — needs main.py usage check (excluded from review); flagged.

### generation/
- `room_gen.py`:
  - ✅ `interior_cols`/`interior_rows` (lines 21-22) — unused locals, DELETE. Module is live (`make_room` called by `build_dungeon_first_cave`).
  - 🟡 rune-glyph tables duplicated & inconsistent: `room_gen.RUNE_TYPES` has `ember='◦'`; `dungeon_gen._RUNE_CHAR` has `ember='⊙'`. Both live → first cave uses a different ember glyph than other levels. Unify the glyph source.
- `dungeon_gen.py` (huge — surveyed in chunks):
  - 🟢🟢 **Systemic duplication: per-level par solvers.** `_bfs_par`, `_dijkstra_par_count`, `_par_counting_crypts`, `_bfs_par_line`, and the many `_par_<slug>` each re-implement the same machinery: spawn/exit endpoints, BFS/Dijkstra relaxation, count-`hjkl` expansion, `$`/`0`/`^` wall-bounded segment scan, `_join_path` reconstruction. The `$`/`^`/`0` segment logic alone is copy-pasted across `_par_counting_crypts` (268-303), `_bfs_par_line` (479-505), and others. A shared motion-expansion toolkit + generic state-space Dijkstra would cut this dramatically. CAVEAT: par-integrity-critical; refactor only under the per-level tests + tools/par_audit.py.
  - ✅ dead locals (vulture): 345 `rows_l` (only `cols_l` used → `_, _, cols_l`), 377 `attempt` (→ `for _ in`), and 639/669 (same pattern in another builder). DELETE.
  - 🟢 `_w`/`_b`/`_e` word-motion solvers + count-chaining are duplicated between `_dijkstra_par_wbe` (760-891) and `_dijkstra_par_ftFT` (914-1098) (latter only adds water-stops). Fold into one parametrized helper.
  - 🟡 multiple near-identical "scatter runes with density + long-rune retry + 1–3 gap" placers: `_place_runes_in_room` (104), `_make_rune_corridor` (720), `_cataracts_place_zone` (894), room_gen `_place_clusters`. One shared scatter primitive.
  - ⚪ COVERAGE NOTE: dungeon_gen.py (~5700 lines) was surveyed structurally (lines 1–1170 read in full; remainder sampled). It is N repetitions of {layout constants + builder + bespoke par-solver + scatter helper}; the systemic findings above apply file-wide. A dedicated par-solver-consolidation pass is the high-value follow-up. Recommend a focused re-read of any builder before editing it.
  - 🔎 RECOMMENDED CHECK (needs `dir()`/search, not done here): orphaned builders = `_gen_curriculum_table._built_slugs() - {l['slug'] for l in LEVELS}`. Any built slug not in LEVELS is a dead `build_dungeon_*`.

### render/
- `utils.py` — clean.
- `colors.py` — clean. `expl_near/mid/far` (30-32) are LIVE via `color_palette` `getattr` discovery (vulture flag = false positive). Do NOT delete.
- `symbols.py` — ✅ **dead-glyph candidate CONFIRMED.** renderer.py renders walls as `wall_bg + ' '`, runes from `ru.symbols`, warden as `'W'`, open doors as floor — so these have no consumer (vulture-confirmed across all importers): `WALL_SOLID`, `WALL_SHADE1/2/3`, `ENEMY_GUARD`, `BOSS`, `EXPLOSION`, `DOOR_OPEN`, `RUNE_ANCIENT/VERDANT/VOID/EMBER`, `BOX_BT/TT/X`. DELETE these (vestigial pre-color-rendering glyphs; `RUNE_*` are a 3rd copy of the rune tuples). Keep `FLOOR`/`CORRIDOR` (not vulture-flagged; verify). 🟡 the `RUNE_*` deletion also removes one of the three duplicate rune-glyph tables.
- `renderer.py` — ✅ `room_display_rows`/`room_display_cols` (288-289) dead locals → DELETE. Otherwise clean, well-factored (`_cell` shared by wrap/nowrap). The line/col anchoring (base_row/first_standable_*) matches this session's numbering fix.
- `parent_dir.py` — ✅ `ENTRIES` (line 10) dead module alias → DELETE (comment says "prefer entries_for()").
- `hint_bar.py` — clean.
- `color_palette.py` — clean; confirms `expl_*`/`rune_*` color fns are live via getattr discovery.
- `title.py` — ✅ `FRAME_W` (12) dead constant → DELETE. ✅ 🟢 lines 347-348 are redundant (immediately overwritten by 349-350 unconditionally) → DELETE.
- `overworld.py` — clean. 🟡 status-bar block (74-91) ≈ duplicate of parent_dir.py (38-55). ⚪ `badge_col` names two different things (width @113 vs color in `_content`).
- `wizard_blessing.py` — clean. 🟡 eye-blink constants/logic + `_AMBER_CHARS` duplicated with title.py — share via one module.
- `scroll_library.py` — clean, but 🟡🟡 **netrw chrome heavily duplicated**: `_row`/`_hdr`/`_div` (85-103) are verbatim copies of parent_dir.py's (66-84); the status bar (54-72) + header rows (96-123) repeat parent_dir's. The "Vimny / name / hearts / -- LABEL --" status bar is identical in 3 files (parent_dir, overworld, scroll_library). **Extract `render/netrw_chrome.py`** (status bar + border_h + _row/_hdr/_div + header block) — the largest render-layer dedup.

### save/
- `save_manager.py` — clean. `_SPECIAL_KEYS` is the single source of truth; save/load round-trip is explicit (minor 🟢 repetition, acceptable).

### tools/
- `par_audit.py` — clean, well-documented. Generic replay-validated nav audit; complementary to (not redundant with) the build-time `_par_<slug>` solvers. No issues.

### tests/ — COVERAGE NOTE
Tests were NOT individually read line-by-line (dozens of files; lower value/line and context-bounded). Reviewed where tied to flagged code (test_motion, test_insert, test_budget, test_combat, test_bug_berserker). Known test-side actions: deleting `status_color`/`_last_content_col` requires removing their tests (test_budget.py 87-117 asserts, test_insert.py `test_last_content_col` + import). Per-level `test_<slug>.py` follow the `SEEDS` parametrization convention (ARCHITECTURE) — likely consistent. RECOMMEND a separate lighter test pass focused on: (a) stale tests referencing removed symbols, (b) duplicated fixtures that could move to a conftest.

### content/
- `levels.py` — clean. ⚪ `display` skips '11' (cosmetic).
- `_gen_curriculum_table.py` — clean; `_built_slugs()` (37-39) is the basis for the orphaned-builder check above.
- `scrolls.py` — clean data; every `*_SCROLL` is referenced in `SCROLL_CATALOG`; no orphan scrolls. ⚪ docstring lists a `('v_sight',)` line-kind no scroll dict uses (verify the main.py renderer still needs it, else drop from doc).

