# Vimny — Level Curriculum Plan

> Canonical curriculum source: `content/levels.py` (`LEVELS` + `known_commands(slug)`).
> SPEC.md no longer holds a curriculum: its stale 20-level draft (former §9–§10) was removed
> in the 2026-05 prune, leaving SPEC.md as design vision / UI only. This document and
> `content/levels.py` are the curriculum source of truth.

This document is the living curriculum reference: the design **rubric** below, the
generated **level table** (Part 7, mirrored from `content/levels.py`), and the
**renumbering guide** (Part 8). Parts 1–6 — the original audit and clean-renumber
proposal — were retired once the curriculum shipped; the slug is the identity now,
so there is nothing left to keep re-syncing.

---

## Design principles (the rubric)

1. **Scope** — a level teaches **1–3 new mechanics**, no more. Trivial direction/flavor
   variants of one idea count as one (e.g. `f`/`F` = one "find" idea).
2. **Rational linkage** — mechanics taught together form **one coherent family**
   (`gg`+`G` ✓; `gg`+`}` ✗).
3. **Forceability** — the level can be designed so the budget puzzle **forces** the new
   command using existing game primitives, with **no/minimal new game mechanics**.
4. **Boss placement** — bosses sit at **meaningful act boundaries**, are well-spaced, and
   are numbered `x.1`.

Existing forcing primitives: walls/corridors, doors, character runs (word/WORD targets),
void runes (lethal), water, chests/keys, fog-of-war, **keystroke budget** (`par × 1.4`),
enemies (goblins chase; wardens+shields in bosses), visual mode.

---

# Part 7 — FINAL curriculum (mirrors `content/levels.py`)

Identity is the **slug** (immutable). The leftmost column is the human-facing
**display** number — cosmetic only; the historical gap (no level 11; the Runic
Archives is 12) is preserved. Bosses and the Reliquary render as `x.1`.
Curriculum order is the order of `LEVELS`. Blueprints: `blueprints/act_*.md`.

> **This table is generated** from `content/levels.py` by
> `python3 content/_gen_curriculum_table.py` — do not hand-edit between the
> markers. After renumbering (edit `display` / reorder `LEVELS`), rerun it. The
> renumbering procedure is Part 8.

<!-- BEGIN GENERATED CURRICULUM TABLE -->
| # | slug | Name | commands | type |
|---|------|------|----------|------|
| 0 | `first_cave` | The First Cave | `h j k l u :w :q :q!` |  |
| 1 | `line_halls` | The Line Halls | `^ $ 0` |  |
| 1.1 | `reliquary` | The Reliquary | `x` | reliquary |
| 2 | `counting_crypts` | The Counting Crypts | `[count] prefix` |  |
| 3 | `rune_halls` | The Rune Halls | `w b e` |  |
| 4 | `character_cataracts` | The Character Cataracts | `f F t T` |  |
| 5 | `goblin_gauntlet` | The Goblin Gauntlet | `; , p` |  |
| 5.1 | `wardens_keep` | The Warden's Keep | — | boss |
| 6 | `word_forge` | The WORD Forge | `W B E` |  |
| 7 | `backward_vaults` | The Backward Vaults | `ge gE` |  |
| 8 | `lineheads` | The Lineheads | `G gg` |  |
| 9 | `screen_vault` | The Screen Vault | `H M L` |  |
| 10 | `bracket_vaults` | The Bracket Vaults | `%` |  |
| 12 | `runic_archives` | The Runic Archives | `} {` |  |
| 13 | `sentence_corridor` | The Sentence Corridor | `) (` |  |
| 13.1 | `warden_surveyor` | The Warden Surveyor | — | boss |
| 14 | `seekers_labyrinth` | The Seekers' Labyrinth | `/ ? n N * #` |  |
| 14.1 | `binders_reliquary` | The Binder's Reliquary | `:h za :q` | reliquary |
| 15 | `waypoint_sanctum` | The Waypoint Sanctum | `` m ' ` `` |  |
| 16 | `archivists_library` | The Archivist's Library | `:set wrap  :e!  :w {file}` |  |
| 16.1 | `warden_pathfinder` | The Warden Pathfinder | — | boss |
| 17 | `operators_vault` | The Operator's Vault | `d{m}  dd` |  |
| 18 | `cipher_cell` | The Cipher Cell | `r  D  X` |  |
| 19 | `quartermaster` | The Beacon Tiers | `y yy P` |  |
| 20 | `echo_vault` | The Echo Vault | `.` |  |
| 20.1 | `warden_manifold` | The Warden Manifold | — | boss |
| 21 | `inscription_halls` | The Inscription Halls | `i a` |  |
| 22 | `whole_line_annex` | The Change Annex | `c{m}  cE  cc  s` |  |
| 23 | `change_extension` | The Change Extension | `S  C  Y` |  |
| 24 | `sculpting_chambers` | The Sculpting Chambers | `I A o O` |  |
| 25 | `overwrite_halls` | The Overwrite Halls | `R` |  |
| 26 | `case_chambers` | The Case Chambers | `~ g~ gU gu` |  |
| 27 | `joiners_gate` | The Joiner's Gate | `J gJ` |  |
| 28 | `alignment_halls` | The Alignment Halls | `>> <<` |  |
| 29 | `indentation_sanctum` | The Indentation Sanctum | `>{m} <{m} =` |  |
| 29.1 | `warden_scrivener` | The Warden Scrivener | — | boss |
| 30 | `sight_sanctum` | The Sight Sanctum | `v {m} d/c/~` |  |
| 31 | `selection_halls` | The Selection Halls | `V  <C-v>` |  |
| 32 | `word_enclosure` | The Word Enclosure | `iw aw iW aW` |  |
| 33 | `bracket_enclosure` | The Bracket Enclosure | `i( a(` |  |
| 34 | `brace_square_enclosure` | The Brace & Square Enclosure | `i[ a[ i{ a{` |  |
| 35 | `quote_enclosure` | The Quote Enclosure | `i" a" i' a'` |  |
| 36 | `tag_enclosure` | The Tag Enclosure | `it at` |  |
| 37 | `sentence_enclosure` | The Sentence Enclosure | `is as` |  |
| 38 | `paragraph_enclosure` | The Paragraph Enclosure | `ip ap` |  |
| 38.1 | `grandmasters_sanctum` | The Grandmaster's Sanctum | — | boss |
| 39 | `spellwrights_forge` | The Spellwright's Forge | `:s///  :g  &` |  |
| 40 | `culling_ledger` | The Culling Ledger | `:d :a,bd :v//d` |  |
| 41 | `stair_rail` | The Stair Rail | `+ - _` |  |
| 42 | `g_sanctum` | The Last Reach | `g_ g* gi gp` |  |
| 43 | `buried_word` | The Buried Word | `g* n` |  |
| 44 | `wet_ink` | The Wet Ink | `gi` |  |
| 45 | `hall_of_echoes` | The Hall of Echoes | `q @ "` |  |
| 46 | `gauntlet` | The Gauntlet | — |  |
| 46.1 | `warden_eternal` | The Warden Eternal | — | boss |
| 99 | `dummy` | Dummy Dungeon | `d x s y p yy P` |  |
<!-- END GENERATED CURRICULUM TABLE -->

---

# Part 8 — Renumbering & the slug model (for future edits)

`content/levels.py` is the single source of truth. Every builder, test, par
solver, save record, scroll, and wizard poem is keyed by the immutable **slug**
— never by a level number. Renumbering is therefore cheap and safe.

## To renumber or reorder the curriculum
1. Edit `LEVELS` in `content/levels.py`: reorder entries and/or change `display`
   strings. **Never change a `slug`** — that is the identity.
2. `known_commands`, unlock gating (`unlocks_after_slug`), and the hint-bar tiers
   all derive from `LEVELS` order automatically — nothing else to touch.
3. Run `python3 content/_gen_curriculum_table.py` to refresh the Part 7 table.
4. `python3 -m pytest -q` — green confirms the curriculum is consistent.

## Keyed by slug (renumber-immune)
- Builders: `build_dungeon_<slug>` (`generation/dungeon_gen.py`).
- Tests: `tests/test_<slug>.py`; par solvers `_par_<slug>`; constants `_<SLUG>_*`.
- Saves: `progress` is keyed by slug (`save/save_manager.py`).
- Scrolls: `_SCROLL_DROPS` (main.py) + `SCROLL_CATALOG.level_slug` (content/scrolls.py).
- Wizard poems: `introduces_slug` (`art/_gen_wizard_wisdom.py`).
- Per-level special-casing in main.py compares `level == '<slug>'`.

## The only place numbers still live
- `display` (one cosmetic string per level) — the single thing a renumber edits.

Saves are keyed by slug. The pre-refactor int-keyed save files were migrated to
slug keys once (a throwaway script, with a backup); the historical id→slug map
was then deleted, so there is **no** legacy numbering anywhere in the runtime.

## Adding a new level
Add a `LEVELS` entry (unique slug, `display`, `name`, `key`, `teaches`); write
`build_dungeon_<slug>` + `tests/test_<slug>.py`; if it precedes a lesson, add a
slug-keyed poem in `art/_gen_wizard_wisdom.py` and regenerate.
