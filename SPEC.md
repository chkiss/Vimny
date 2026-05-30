# Vimny — Design Notes (Vision, UI & Forward-Looking Mechanics)

> **Scope.** This document holds design *vision*, the *UI layout* spec, and *not-yet-built*
> mechanics. It is **not** the source of truth for the curriculum or command behavior — those
> drifted here once and caused real bugs. Canonical sources:
> - **Curriculum** (levels, command-unlock order): `content/levels.py` — mirrored in `LEVELS_PLAN.md` **Part 7**.
> - **Command semantics**: the engine (`engine/`) + tests; quick reference in `README.md`.
> - **Architecture, key files, conventions, budget formula**: `CLAUDE.md`.
>
> Section numbers below are intentionally non-contiguous. The stale or duplicated sections
> (former §3 architecture, §4 visual tables, §6.1–6.3 command tables, §7–§11 systems/procgen,
> §13 save, and the build checklist) were removed in the 2026-05 prune. Retained sections keep
> their **original numbers** so outside references (e.g. blueprints citing "SPEC §6.4") still resolve.

---

## 1. Vision

Vimny is a terminal-first, dungeon crawler that teaches Vim through play. The dungeons are text buffers, the overworld is a filesystem, and every puzzle is solved by using Vim commands efficiently. Players learn real Vim grammar.

---

## 2. Design Pillars

1. **Vim fidelity above all else.** Commands behave exactly as they do in Vim. The game teaches the real tool. Editing reflows like a real Vim line — insert/delete/paste shift content; the one bounded twist is that a dungeon row is wall-bounded, so content shoved past a wall or void rune falls into the void (water is movable and drowns whatever a wave reaches). See `engine/reflow.py`.
2. **Efficiency is the skill.** The keystroke budget system makes Vim's core value proposition (fewer keystrokes = more power) mechanically central — not a side effect.
3. **Everything is a buffer.** Dungeons are files. The overworld is a directory. `:e`, `:w`, `:q` are real game mechanics.
4. **Learn, not suffer.** No permanent run loss. Undo returns budget. The game is a tutor, not a gauntlet.

---

## 5. Game Structure

### 5.1 The Overworld: Filesystem View

The overworld renders as Vim's netrw directory browser, decorated with a game frame. The player navigates it with `hjkl` and presses `Enter` to enter a dungeon.

*(Illustrative mockup — dungeon names/levels here are not the canonical curriculum; see `content/levels.py`.)*

```
┌──────────────────────────────────────────────────────────────────────────────┐
│  Vimny              ♥♥♥♥♥  Gold: 142  Keys: 3                                │
│  Normand the Cursor    LVL 5   Known: hjkl ^$0 w b e gg G { }                │
├──────────────────────────────────────────────────────────────────────────────┤
│ ============================================================================ │
│ The Known World                                   [Vimny v0.1]               │
│   /world/                                                                    │
│   Sorted by: discovery order                                                 │
│   Enter:open  ?:examine  I:inventory  Q:quit                                 │
│ ============================================================================ │
│ ../                                                                          │
│ ./                                                                           │
│ town_of_normalmode/              [TOWN]                                      │
│ dungeon_00_the_first_cave        [★★★ COMPLETE]                              │
│ dungeon_01_the_line_halls        [★★☆ COMPLETE]                              │
│ dungeon_02_the_counting_crypts   [★★☆ COMPLETE]                              │
│ dungeon_03_the_word_mines        [► CURRENT]                                 │
│ dungeon_04_the_ancient_spire     [LOCKED]                                    │
│ dungeon_05_the_hall_of_rooms     [LOCKED]                                    │
└──────────────────────────────────────────────────────────────────────────────┘
```

**Frame** (top rows): Player name, HP hearts, gold, key count, known command list, level.

**netrw header**: Title, path, quick help showing game-specific commands (not Vim commands).

**Listing**: Dungeon "files" with star ratings and status. Areas (town, forest) are "directories."

**Navigation**: `hjkl` to move cursor, `Enter` to open, `?` to examine, `I` for inventory. `:e dungeon_name` to jump directly. `:e ..` goes to parent area.

**The filesystem metaphor taught in play**: Before the player learns `:e`, they discover dungeons by walking to them in the overworld. A later command-mode dungeon teaches `:e` explicitly — at which point the player realises the overworld they've been navigating *is* a filesystem.

### 5.2 Dungeons (Files)

Each dungeon is:
- A series of **rooms** connected by corridors and doors
- **Procedurally generated** each run (or replayed with the same seed by player choice)
- A **text buffer** — the floor is made of rune clusters the player navigates with Vim
- Introduced by a **dungeon title card** styled as a Vim file header, showing dungeon name, command focus, and par scores

**Room types**:
| Type | Description |
|---|---|
| Entry room | Starting room; no enemies |
| Puzzle room | Has a keystroke budget constraint; mandatory use of target commands |
| Combat room | Enemy patrols; player must defeat or route around them |
| Chest room | Reward room; no enemies |
| Safe room | Checkpoint; auto-triggers `:w` on entry |
| Boss room | Milestone combat encounter |
| Exit room | Contains the dungeon exit (`◉`) |

### 5.3 The Dungeon as Text Buffer

The dungeon floor is a navigable text buffer:

| Vim concept | Dungeon equivalent |
|---|---|
| Characters | Individual floor cells |
| Words | Rune clusters (groups of Unicode symbols) |
| Whitespace | Empty floor cells between clusters — **traversable floor, not void** |
| Lines | Rows of the dungeon |
| End of line | Room wall — `$`, `l`, and count-`l` stop here |
| Paragraphs | Rooms |
| Newline / line boundary | Door — separates rooms; opened with `x` before the next room is accessible |
| First line (`gg`) | Top row of the dungeon buffer — `gg` lands on its first non-blank cell |
| Last line (`G`) | Bottom row of the dungeon buffer — `G` lands on its first non-blank cell |

Every Vim navigation command has a direct, literal meaning in the dungeon. (Note: `gg`/`G` are **buffer-relative** — first/last line — *not* the player spawn or the exit; conflating them is what an earlier draft got wrong.)

**Room boundaries and count motions**: Each room is bounded by walls on all sides. Count motions (`5l`, `59l`, etc.) stop when they hit a wall, exactly as Vim's count-`l` stops at end-of-line. A count of 59 in a room 20 columns wide simply lands at the far wall — no overshoot. This makes room walls the correct level-design tool for forcing a specific count; void rune cells do **not** stop count motions (a void rune is passable floor that costs 1 HP only on the final landing cell). Rows are bounded by walls and fog of war (relevant to commands like `^`, `$`, and `0`).

**Fog of war**: Only applies to rooms separated by doors. A door-blocked room is hidden until its door is opened with `x`; once revealed it stays revealed. Open corridors (no door) connect rooms that are always visible. Level 0 has no doors and therefore no fog of war.

**Empty floor rendering**: Empty floor cells (the "whitespace" between rune clusters) must always be rendered with a visible background color (`very dark grey`). They must never render as raw terminal background.

**Corridor rendering**: Corridors connecting rooms are the same floor background color as room interiors. A corridor is just more floor.

---

## 6. Vim Mode Mechanics

Normal / Insert / Visual mode command **semantics** are canonical in the engine (`engine/`) +
tests and summarized in `README.md`; the per-level unlock order is in `content/levels.py`
(= `LEVELS_PLAN.md` Part 7). Basic Command mode (`:w` `:q` `:q!` `:wq` `:e` `:set number`) is
covered by the save system and the curriculum. The one piece retained here is the **not-yet-built**
substitution mechanic, which blueprints reference as "SPEC §6.4".

### 6.4 Substitution & Arcane Mana (forward-looking / TBD)

**Substitution spell** (a later mastery-tier unlock; costs Arcane Mana):
| Command | Effect | Mana cost |
|---|---|---|
| `:s/{from}/{to}/` | Transform first match in current row | 1 |
| `:s/{from}/{to}/g` | Transform all matches in current row | 3 |
| `:%s/{from}/{to}/g` | Transform all matches in current room | 5 |

Substitution applies to terrain (`wall`, `fire`, `ice`, `water`) and objects (`chest`, `door`, `lever`). Direct enemy transformation requires the `c` operator; `:s/` affects the environment only. Full scope and mana economy are TBD.

---

## 12. UI Layout

### 12.0 UI Dimensions

Every game view — dungeon, overworld, transition screens — uses the same outer frame dimensions. This is the answer to "should there be consistency?": yes, both horizontally and vertically, so the frame never jumps when switching views.

**Horizontal**:

| Quantity | Value |
|---|---|
| Frame outer width | **80 columns** |
| Frame inner width | 78 columns (80 − 2 border `│` characters) |
| Maximum adaptive width | 120 columns on wider terminals |

The frame fills terminal width between 80 and 120 columns. Every content line pads with trailing spaces to the full inner width — this is what keeps the right `│` border column-aligned even when content is short. Lines that do not fill to the inner width produce a ragged right border.

**Vertical**:

| Quantity | Value |
|---|---|
| Chrome rows (fixed) | **6 rows**: top border `┌─┐` (1) + status bar (1) + top `├─┤` separator (1) + bottom `├─┤` separator (1) + hint/footer bar (1) + bottom border `└─┘` (1) |
| Game area rows | Terminal height − 6 |
| Minimum game area | 18 rows (24-row terminal − 6 chrome) |
| Recommended game area | 24+ rows (30-row terminal − 6 chrome) |

The 6-row chrome layout is identical in both the dungeon view and the overworld, so row 0 is always the top border, row 1 the status/header bar, and the last row the bottom border. Switching views does not shift the player's eye anchor.

### 12.1 Main Dungeon View

```
┌──────────────────────────────────────────────────────────────────────────────┐
│  ♥♥♥♥♥░░░░░  The Word Mines           -- NORMAL --   Budget: 8   Par: 6      │
├──────────────────────────────────────────────────────────────────────────────┤
│     0         1         2         3         4         5                      │
│     |123456789|123456789|123456789|123456789|123456789|1                     │
│  1 ████████████████████████████████████████████████████                      │
│  2 █  ∘∘∘  ···   ○○  @  ◦◦◦◦   ♟    ···  ○            █                      │
│  3 █                                                  █                      │
│  4 █  ∘∘  ◈    ···   ♟    ○○○   ···                   ░░                     │
│  5 █                            ♜                     ░░                     │
│  6 █  ◦◦◦◦   ∘∘∘    ○○    ···       ◉                 █                      │
│  7 ████████████████████████████████████████████████████                      │
│                                                                              │
├──────────────────────────────────────────────────────────────────────────────┤
│  h/j/k/l:move  w:next-word  b:prev-word  e:end-word  ^:row-start  $:end      │
└──────────────────────────────────────────────────────────────────────────────┘
```

The `░░` gap in the right wall is a corridor opening — two floor-background cells where the `█` wall is absent, connecting this room to the next. There are no labels inside the map area; corridors are purely structural gaps.

**Empty floor rendering**: Every cell inside the room boundary that does not contain a rune cluster, enemy, or item must be rendered as a space character with the floor background color applied (`very dark grey`). Never leave floor cells as raw terminal background. Without the fill, the room interior looks like floating symbol islands separated by void — the renderer must apply the background to every floor cell on every draw call.

**Corridor rendering**: Corridor cells share the same floor background as room interiors. A corridor is a contiguous strip of floor-background cells through a gap in the wall. Because both sides of the gap (room interior and corridor) carry the same background color, the connection is visually seamless. Any corridor that looks detached or dashed is a rendering bug: some floor cells are not receiving the background fill.

**Row 1 — Status bar**: HP hearts (filled `♥` / empty `░`), dungeon name, mode indicator, budget remaining, par target.

**Rows 2–N — Game area**: Dungeon view. Scrolls if dungeon is larger than the viewport.

**Last row — Hint bar**: Known commands with brief labels. In Command mode, this row becomes the command line (`:` prompt). Hidden in hard mode.

### 12.2 Navigation Rulers

Both axes display position rulers to help players estimate count motions.

**X-axis ruler** (column ruler, above the game grid):

Two rows, one character per column:

```
  |123456789|123456789|123456789|123456789|123456789|123456789|123456789|12345
  0         1         2         3         4         5         6         7
```

- Top row: unit digits (1–9) with `|` at every decade boundary (cols 0, 10, 20, …)
- Bottom row: tens digit at each decade boundary, blank elsewhere
- Together they let the player read any column position unambiguously at a glance

**Y-axis ruler** (line numbers, left of the game grid):

Default: absolute line numbers, exactly as Vim's `:set number`. The leftmost passable row of the dungeon is row 1.

If the player has found the **Relative Numbers scroll** (a findable inventory item) and toggled `:set relativenumber`, the ruler switches to relative distances — every row shows how many `j`/`k` presses it is from the cursor, and the cursor row shows its absolute number. Toggling is persistent across sessions (saved with the player's settings).

### 12.3 Terminal Size Requirements

- Minimum: 80 columns × 24 rows
- Recommended: 100×30+
- Game detects terminal size at launch and on resize; adjusts viewport
- Below minimum: warning shown, game pauses

### 12.4 Hard Mode

- Hint bar hidden (replaced by blank row or mode label only)
- Budget buffer reduced to +0 (exact minimum required)
- Enemy speed: 1.25×
- Toggle: main menu or `:set hardmode` / `:set nohardmode` in-game
- Persists in save file

---

## 14. Open Questions / TBD

| Topic | Status | Notes |
|---|---|---|
| `:s/` mana economy | TBD | Drop rates, max stock, regeneration |
| `c` operator Insert timeout | TBD | How long before transformation randomises |
| Full spell vocabulary | TBD | Expand beyond initial 7 words |
| Town of Normalmode | TBD | NPC dialogue, shop inventory, side quests |
| Named registers (`"a`–`"z`) | TBD | Whether registers have distinct game-mechanic meaning |
