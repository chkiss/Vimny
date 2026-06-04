# Vimny — Architecture & Conventions

Vim-teaching dungeon crawler (Python/blessed). Dungeons are text buffers; every puzzle is solved with Vim commands. Curriculum: `content/levels.py` (= `LEVELS_PLAN.md` Part 7). Design vision/UI: `SPEC.md`.

Admin features: `:edit` enters editor mode on any dungeon; `:save <name>` writes layout to `~/.Vimny/layouts/<name>.json` for use as level-design reference.

## Key files
| File | Role |
|---|---|
| `main.py` | Game loop, `apply_motion`, `run_dungeon`, `run_overworld` |
| `engine/vim_parser.py` | Keystroke → action dict. `COUNTS='123456789'` |
| `engine/world.py` | `Room`, `Dungeon`, `Entity`, `CharRun`, `CellType` |
| `engine/player.py` | `Player` dataclass |
| `engine/budget.py` | `Budget` — tracks keystrokes spent vs. total |
| `engine/reflow.py` | Reflow editing primitives — `open_gap`/`close_gap`, `_insert_blank_row`, `remove_row`, `extend_floor`/`carve_floor`, `_merge_adjacent_char_runs`; `_MAX_COLS=200` |
| `engine/search.py` | `/ ? n N * #` — Vim-regex search (via `engine/vimregex.py`), matched PER LINE (`_line_string`) so a pattern spans consecutive char runs |
| `engine/substitute.py` | `:s :g :v & g&` — ex substitute & global on the same line model; `run_ex` is main.py's COMMAND-mode entry; `repeat_normal` backs `&`/`g&` |
| `generation/dungeon_gen.py` | `build_dungeon_<slug>` per level (dispatch via getattr); Dijkstra par solvers |
| `content/levels.py` | Level defs; identity = immutable `slug`, `display` = cosmetic number; `known_commands(slug)` — **canonical curriculum source** |
| `LEVELS_PLAN.md` (root) | Curriculum plan; **Part 7 table is GENERATED** from `content/levels.py` (`content/_gen_curriculum_table.py`); Part 8 = renumbering guide |
| `render/renderer.py` | Pure read-only view of state (no mutation) |
| `render/overworld.py` | netrw overworld buffer (read-only) — `build_lines`, `default_cursor`, `render_overworld` |
| `save/save_manager.py` | Player progress I/O + layout save (`~/.Vimny/layouts/`) |
| `render/vim_commands.md` | Hint-bar text source — token→(keys, desc), parsed by `render/hint_bar.py` |
| `tests/test_<slug>.py` | Per-level correctness tests (e.g. `test_counting_crypts.py`) |
| `art/vocab_plain.txt` | Vocabulary source: typable-only tokens (no internal `w` splits); use for non-word-boundary levels |
| `art/vocab_mixed.txt` | Vocabulary source: tokens with embedded Unicode punctuation; creates `w`/`b`/`e` boundaries but not `W`/`B`/`E`; use for levels teaching small-word vs WORD |
| `art/_gen_runes.py` | Generator for both vocab files — edit this, not the txt files directly |

## Mixed vocab token rules
`art/_gen_runes.py` is the source of truth. Rules for mixed tokens:
- **Decorative endpoints** (glyph appended to a complete word) are the preferred style — thematic connection beats visual match at endpoints.
- **Letter substitution** (glyph replaces a letter mid-word) requires visual or strong thematic justification. `†`=t is very lenient (cross shape). `♝`=l is acceptable (tall narrow bishop ≈ tall letter). Wide glyphs (suits, most chess pieces) mid-word without justification are banned.
- **Double-letter rule**: if substituting a letter that appears doubled (tt, ll), substitute both — e.g. `http` → `h††p`, not `ht†p`. Pure decorative endpoints are exempt.
- **Wide glyphs at endpoints** are fine; wide glyphs mid-word create poor aesthetics and need strong justification.
- Do not add tokens to the txt files directly; run `python3 art/_gen_runes.py` to regenerate.

## Architecture rules
- **Level identity is the immutable `slug`** (no integer id). `display` is a cosmetic number. `build_dungeon_<slug>`, `tests/test_<slug>.py`, `_par_<slug>`, `_<SLUG>_*` constants, save-progress keys, scroll `level_slug`, and wizard `introduces_slug` all key by slug. **Renumber** = edit `display` / reorder `LEVELS` (never touch a slug) + rerun `content/_gen_curriculum_table.py`. See LEVELS_PLAN Part 8.
- Renderer never mutates state (required for future web port).
- `Budget.spend(cost)` where `cost = 1` (single step) or `len(str(n))+1` (count-n move).
- `apply_motion` loops step-by-step; void rune check fires only on final cell (intentional — Vim-faithful).
- Undo stack entries are either `(row, col, spent)` tuples (movement) or dicts with `entities`/`fog_col` keys (door-open).
- **Terminology — "character"/"CharRun", not "rune".** On-screen characters are `CharRun` objects (`room.char_runs`); in code, comments, and docstrings call them **characters** / **character runs**. Clips key the list under `'char_runs'`; the merge helper is `_merge_adjacent_char_runs`. "rune" is reserved for the THEME only: level names (The Rune Halls, The Runic Archives), the vocab pipeline (`art/_gen_runes.py`, `vocab_*.txt`), wizard poems, and `<kind> rune` type phrases (e.g. "void rune"). Do not use "rune" to mean a generic character or "rune cluster" to mean a word.
- **Reflow grid (Vim line model), NOT an overlay grid:** editing flows like a real Vim line — insert/`x`/`d`/`s`/paste SHIFT content within the wall-bounded row (blanks are spaces, so a word past a gap is still pushed). Content shoved past a FIXED brink (any wall or void rune) is lost over the brink; water is movable and a wave sweeps any entity it reaches into the void (drown). `r`/`R` overwrite in place (correct Vim) and do not reflow. Charwise paste: `p` inserts after the cursor, `P` before; the cursor lands on the last pasted cell (including a creature — the `x`-attack position). Pasting a key onto a locked door unlocks it and steps the player onto the door (consistent with paste). Reflow is universal — `is_ledge` always True. Hold any new editing command to this model. See `engine/reflow.py`.
- **Void runes are TEXT, not just terrain:** a `○` is a `CharRun` (kind=`void`) — `/`/`*` search it, `x` deletes it, and `:s` substitutes it. Substituting a void away fills the hole as ordinary text (replacement chars take the line's first non-void kind); an untouched void keeps kind=`void`. The reflow FIXED-brink rule (content shoved into a void falls off) governs only the push/pull editing ops (`i`/`x`/`d`/`p`), NOT the whole-line rewrite of `:s`. Anything drawn with a glyph (words, void runes) is text to `/`/`x`/`:s`; cell-terrain with no glyph (walls, water) is invisible to all three. See `engine/substitute.py` / `engine/search.py`.
- **Ex substitute & global (`engine/substitute.py`):** `:s`/`:g`/`:v`/`&`/`g&`, taught at The Spellwright's Forge (L37, token `subst`). A "line" is a row's wall-bounded glyphs with gaps as spaces (`_read_line` → text + per-char kinds); `set_line_text` re-lays the row (content past the right wall falls off). Ranges (`%` `N` `.` `$` `'a` `'<'>` `±N` `a,b`/`a;b`; `:g` defaults to whole file), `:s` flags `g c i I n e &` + count, full Vim replacement (`& \0-\9 ~ \u\U\l\L\E \r \t`), and the repeats all there. `&`/`g&` parse to a `sub_repeat` action.
- **Vertical / ledge reflow (BUILT, `engine/reflow.py`):** three primitives, all there. `_insert_blank_row` = vertical add (`o`/`O`, and linewise `p`/`P` which now insert REAL rows and shift the map down). `remove_row` = vertical collapse (`dd` and visual-line `d`, the exact inverse of `o`; `cc`/`S`/`D`/`C` still clear in place). `extend_floor`/`carve_floor` = horizontal ledge-build (`A` jumps to the line END — just past the rightmost passable cell, skipping trailing floor as Vim skips trailing spaces, NOT just past the last character — then lays new floor into the void one plank per keystroke, DOUBLING `room.cols` at the right border up to `_MAX_COLS`=200 — the **edge of the world**, past which `A`/`J` refuse and show `_EDGE_OF_WORLD_MSG`; a `○` void rune also stops it, via `room._last_build_blocked`). `A` is the ONLY floor-creating command — interior insert AND `>>` shove the tail off the right brink (`>>` reflows via `open_gap`; it does NOT clamp at the wall). `J`/`gJ` (join, L27) = `remove_row(row+1)` + `extend_floor`-append onto this line (`J` one space at the seam + cursor there, `gJ` none; `nJ` joins n lines; preserves the joined line's internal spacing). Undo snapshots `rows`+`cols`+`cells`; pass `player` to `remove_row`/`_insert_blank_row` so marks/jumplist shift with the rows.
- **Overworld = a netrw buffer (`render/overworld.py` + `run_overworld` in `main.py`):** a flat list of selectable lines — the `"` comment header (lines 1–6, numbered), `../`/`./`, the level entries, then a `custom/` section of saved layouts. The cursor is an index into that list, defaulting to `../` (`default_cursor`); `_scroll_offset` is a stateful Vim-like viewport (no cling). Motions are gated by `_known_from_progress(progress)` (admin bypasses): `j`/`k` always; counts, `gg`/`G`, `{n}G` (line-based, 1-indexed over the buffer), `H`/`M`/`L`, `{`/`}`, and `Ctrl-d`/`u`/`f`/`b` once learned. `:set number`/`relativenumber`/`nonumber` (+ `nu`/`rnu`/`nonu`/`nornu`) toggle the gutter. `R` renames a custom layout (`save_manager.rename_layout`), `D` deletes one (y-confirm); built-ins refuse `D`/`R`, and the buffer is read-only (`d`/`dd` refuse). Live blinking cursor via `term.cvvis`; `_done` restores `term.civis` on exit.

## Test conventions
- Dungeon tests: parametrize over `SEEDS = [1, 42, 999, 12345, 2**20 + 7]`; one test per property (reachability, par match, budget formula, command necessity, void safety).
- Command necessity: BFS with restricted command set; assert `cost > room.budget`.
- File I/O tests: `monkeypatch.setattr('save.save_manager.SAVES_DIR', tmp_path)` to avoid touching `~/.Vimny`.
- Motion/editor tests: build a minimal `Room` fixture with `rebuild_indexes()` rather than using a full dungeon.
- Key files: `tests/test_counting_crypts.py` (template for level tests), `engine/motion.py` and `engine/editor.py` (source for motion/editor tests).

## Known bugs
None currently. Previously known bugs (now fixed):
- `30l` trailing-zero split: fixed in `vim_parser.py` via `(count and buf[i] == '0')` guard.
- `3j 59l 3k` void bypass: fixed — fog wall at door column blocks count motions past it.
- `x` then `u` left the character deleted (a free delete): fixed — the cut snapshot is taken BEFORE `_ed_cut` mutates the row, so undo restores the cut character.
- undo-refund cheat (`fx`·`u`·`;` / `/pat`·`u`·`n` / change·`u`·`.` reached the target for 1 key): fixed — undoing a find/search/change arms a re-cost (`player.pending_recost_f/s/c`) so the next `;`/`n`/`.` re-pays the full original cost.
