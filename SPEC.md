# Vimny — Complete Design Specification

## 1. Vision

Vimny is a terminal-first, dungeon crawler that teaches Vim through play. The dungeons are text buffers, the overworld is a filesystem, and every puzzle is solved by using Vim commands efficiently. Players learn real Vim grammar.

---

## 2. Design Pillars

1. **Vim fidelity above all else.** Commands behave exactly as they do in Vim. The game teaches the real tool.
2. **Efficiency is the skill.** The keystroke budget system makes Vim's core value proposition (fewer keystrokes = more power) mechanically central — not a side effect.
3. **Everything is a buffer.** Dungeons are files. The overworld is a directory. `:e`, `:w`, `:q` are real game mechanics.
4. **Learn, not suffer.** No permanent run loss. Undo returns budget. The game is a tutor, not a gauntlet.

---

## 3. Technical Architecture

### 3.1 Phase 1 (Current): Python Terminal

- **Language**: Python 3.10+
- **Rendering**: `blessed` (recommended over `curses` for richer Unicode/color support)
- **Game loop**: Event-driven, key-by-key input processing
- **No external game engine**

### 3.2 Phase 2 (Future): Web Port

- Target stack: TypeScript + xterm.js (renders same visual output in browser)
- Alternate: Rust + WebAssembly (same binary for terminal and browser)
- **Constraint for phase 1**: Keep rendering strictly separated from game logic. All game state lives in plain Python objects with zero `blessed` dependency. The renderer reads state and draws; it never mutates state. This makes rewriting the renderer for xterm.js straightforward without touching game logic.

### 3.3 Module Structure

```
Vimny/
├── main.py
├── engine/
│   ├── world.py          # World state, room management
│   ├── player.py         # Player state
│   ├── vim_parser.py     # Vim grammar: operator + count + motion
│   ├── modes.py          # Mode state machine (Normal/Insert/Visual/Command)
│   └── budget.py         # Keystroke budget tracking
├── generation/
│   ├── dungeon_gen.py    # Procedural dungeon assembly
│   ├── room_gen.py       # Individual room generation
│   ├── validator.py      # Pathfinding + budget constraint validation
│   └── seeds.py          # Seed management for replay
├── render/
│   ├── renderer.py       # Main render loop
│   ├── colors.py         # Color palette
│   ├── symbols.py        # Unicode symbol constants
│   └── overworld.py      # Netrw-style overworld renderer
├── content/
│   ├── levels.py         # Level definitions and command curricula
│   ├── enemies.py        # Enemy type definitions
│   ├── spells.py         # Insert mode spell vocabulary
│   ├── bosses.py         # Boss phase definitions
│   └── fallback_rooms/   # Hand-crafted rooms used when generation fails
└── save/
    └── save_manager.py   # Save/load, :w/:e mechanics
```

---

## 4. Visual Design

### 4.1 Style: Unicode + ANSI Color

Modern terminals support 256-color and truecolor. Use a Zelda-inspired palette with box-drawing characters, Unicode block elements, and symbolic icons. Start here; refine toward richer art in later versions.

**Structural characters**:
| Role | Character(s) | Notes |
|---|---|---|
| Solid wall | `█` (U+2588) | Impassable; fills wall cells |
| Wall shading | `▓▒░` | Decorative wall texture |
| Box borders | `┌─┐│└─┘├┤┬┴┼` | Room/corridor outlines |
| Empty floor | ` ` (space) with floor background | **Must be rendered with a distinct background color** so empty cells form a visually connected surface; never leave floor cells as raw terminal background |
| Corridor | ` ` (space) with same floor background | Treated identically to empty floor; connections between rooms are floor-colored cells that visually bridge rooms |
| Half-blocks (future) | `▀▄` | — |

**Entity symbols**:
| Entity | Symbol | Color |
|---|---|---|
| Player | `@` | Bright white |
| Basic enemy | `♟` | Orange |
| Guard enemy | `♜` | Red |
| Boss | `☠` | Crimson, bold |
| Heart container | `♥` | Red |
| Chest | `◈` | Gold |
| Door (locked) | `▬` | Dark grey |
| Door (open) | `░` | Light grey |
| Exit | `◉` | Bright green |

**Rune cluster symbols** (see Section 7.2):
| Cluster type | Symbols | Color |
|---|---|---|
| Ancient | `∘∘∘` | Dim blue |
| Verdant | `···` | Dim green |
| Void | `○○` | Dim purple |
| Ember | `◦◦◦◦` | Dim orange |

**Color palette** (Zelda-inspired):
| Element | Color |
|---|---|
| Wall background | Near-black |
| Floor background | Very dark grey |
| Player | Bright white |
| Enemies (normal) | Orange |
| Enemies (frozen, Visual mode) | Ice blue |
| Boss | Crimson |
| HP hearts (filled) | Red |
| HP hearts (empty) | Dark grey |
| Budget (comfortable) | Green |
| Budget (low, ≤3 remaining) | Yellow |
| Budget (critical, ≤1) | Red |
| Hint bar text | Dark grey |

### 4.2 Mode Visual Indicators

| Mode | Status label | Screen effect |
|---|---|---|
| Normal | `-- NORMAL --` green | None |
| Insert | `-- INSERT --` yellow | Warm tint on UI border |
| Visual (v) | `-- VISUAL --` magenta | Frozen enemies glow ice-blue; selected cell highlighted |
| Visual (V) | `-- VISUAL LINE --` magenta | Entire row highlighted |
| Visual (^V) | `-- VISUAL BLOCK --` magenta | Selected rectangle highlighted |
| Command | `:` white | Command line replaces hint bar |

### 4.3 Star Ratings

Each dungeon awards 1–2 stars displayed on the overworld:
- **1 star**: Reach the exit
- **2 stars**: Reach the exit at or under par

---

## 5. Game Structure

### 5.1 The Overworld: Filesystem View

The overworld renders as Vim's netrw directory browser, decorated with a game frame. The player navigates it with `hjkl` and presses `Enter` to enter a dungeon.

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

**The filesystem metaphor taught in play**: Before the player learns `:e`, they discover dungeons by walking to them in the overworld. Level 13 teaches `:e` explicitly — at which point the player realises the overworld they've been navigating *is* a filesystem.

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
| File start | Dungeon entry |
| File end | Dungeon exit |

Every Vim navigation command has a direct, literal meaning in the dungeon. 

**Room boundaries and count motions**: Each room is bounded by walls on all sides. Count motions (`5l`, `59l`, etc.) stop when they hit a wall, exactly as Vim's count-`l` stops at end-of-line. A count of 59 in a room 20 columns wide simply lands at the far wall — no overshoot. This makes room walls the correct level-design tool for forcing a specific count; void rune cells do not stop count motions (see Section 7.2). Rows are bounded by walls and fog of war (relevant to commands like ^, $, and 0)

**Fog of war**: Only applies to rooms separated by doors. A door-blocked room is hidden until its door is opened with `x`; once revealed it stays revealed. Open corridors (no door) connect rooms that are always visible. Level 0 has no doors and therefore no fog of war.

**Empty floor rendering**: Empty floor cells (the "whitespace" between rune clusters) must always be rendered with a visible background color (`very dark grey`). They must never render as raw terminal background. 

**Corridor rendering**: Corridors connecting rooms are the same floor background color as room interiors. A corridor is just more floor. 

---

## 6. Vim Mode Mechanics

### 6.1 Normal Mode (default)

The player's primary stance. Full navigation and combat available.

**Navigation commands** (unlocked per Level Curriculum in Section 9):

| Command | In-game effect |
|---|---|
| `h j k l` | Move one cell left/down/up/right |
| `0` | Jump to leftmost cell in current row |
| `^` | Jump to first rune cluster in current row |
| `$` | Jump to last rune cluster in current row |
| `w` | Jump to start of next rune cluster |
| `b` | Jump to start of previous rune cluster |
| `e` | Jump to end of current/next rune cluster |
| `gg` | Jump to dungeon entry point |
| `G` | Jump to dungeon exit |
| `{` | Jump to start of current room |
| `}` | Jump to start of next room |
| `f{c}` | Jump forward to next occurrence of character `c` in row |
| `F{c}` | Jump backward to previous occurrence of `c` in row |
| `t{c}` | Jump to cell before next `c` |
| `T{c}` | Jump to cell after previous `c` |
| `/pattern` | Search dungeon for pattern; all matches highlighted |
| `n` / `N` | Jump to next / previous search match |
| `m{a-z}` | Set named mark at current position |
| `'{a-z}` | Jump to line of named mark |
| `` `{a-z} `` | Jump to exact cell of named mark |
| `x` | Interact: open door or loot chest at cursor position |
| `u` | Undo last action; rewinds time; **returns** budget cost |
| `Ctrl-R` | Redo; re-spends budget |

**Combat commands** (real Vim grammar: `[count][operator][motion]`):

| Command | In-game effect |
|---|---|
| `d{motion}` | Attack: deal damage to enemies along the motion path |
| `dd` | Spin attack: damage all enemies in current row |
| `D` | Charge attack: damage all enemies to end of row |
| `c{motion}` | Transform: change targeted enemy into another type; briefly enters Insert mode to specify (Escape = random) |
| `cc` | Transform all enemies in current row |
| `y{motion}` | Absorb: extract item or resource from targets along motion path |
| `yy` | Absorb all items in current row |
| `p` | Deploy: place last absorbed item at cursor position |
| `.` | Repeat last combat action exactly |

**Count prefix**: Any motion or operator accepts a count. `3w` jumps 3 clusters. `d3w` attacks 3 clusters. `5j` moves down 5 rows. Counts are introduced as a standalone level (Level 2) before operators.

**Count motion fidelity**: A count motion moves step-by-step up to the requested count, stopping only at a wall (impassable cell) or the room boundary — exactly as Vim's `l`/`h`/`j`/`k` stop at end-of-line or end-of-file. Void rune cells are passable floor; a count motion passes through them silently, and only the final landing cell triggers void damage. This is intentional and Vim-faithful. If a level design needs to force a specific count (e.g. exactly `4l`), walls are the right primitive — not void runes.

### 6.2 Insert Mode

Entered via `i`, `a`, `o`, `I`, `A`, `O` — each matching real Vim entry-point semantics.

**Core mechanic**: Enemies continue moving at full speed. The player is vulnerable. Return to Normal mode with `Escape`.

**Entry points**:
| Command | Real Vim meaning | Game context |
|---|---|---|
| `i` | Insert before cursor | Cast/build at current position |
| `a` | Insert after cursor | Cast/build one step forward |
| `I` | Insert at line start | Cast/build at row's first cluster |
| `A` | Insert at line end | Cast/build at row's last cluster |
| `o` | Open new line below | Open/extend floor tile below |
| `O` | Open new line above | Open/extend floor tile above |

**Spell input**: Player types a word from the vocabulary list. Input echoes in the command area. On `Enter` or word completion: spell fires. `Escape` at any point cancels with no effect.

**Misspelled words**: No effect; costs one game tick (enemies advance one step).

**Spell vocabulary** (initial set, Level 12 unlock; expanded by finding spell scrolls in dungeons):
| Word | Effect | Position-sensitive? |
|---|---|---|
| `fire` | Word "fire" causes burn effect to nearby entities | Yes |
| `ice` | Freezes nearest enemy for 3 turns | No |
| `wall` | Places text "wall", which behaves like special wall tiles that can be traversed with word motions | Yes |
| `bridge` | Word "bridge" is walkable over water | Yes |
| `heal` | Restores 1 heart | No |
| `light` | Illuminates dark tiles in radius | No |
| `bomb` | Places explosive; detonates on player's next action | Yes |

### 6.3 Visual Mode

Entered via `v`, `V`, or `Ctrl-V`. **All enemies freeze** while Visual mode is active.

| Command | Selection | Game effect |
|---|---|---|
| `v` | Single cell | Inspect one enemy: shows HP, next move, weakness |
| `V` | Entire row | Scan row: reveals all patrol patterns |
| `Ctrl-V` | Rectangle | Area overview: enemy positions and terrain hazards in block |

**Visual mode operators** (after selection):
- `d`: Mass attack on selected enemies
- `y`: Mass absorb on selected items
- `c`: Mass transform on selected enemies

`Escape` exits Visual mode; enemies unfreeze.

### 6.4 Command Mode

Entered via `:`. Command line replaces the hint bar.

**Core commands**:
| Command | Introduced | Effect |
|---|---|---|
| `:w` | **Level 1** | Save game state to disk |
| `:q` | **Level 1** | Quit to overworld (prompts if unsaved changes) |
| `:q!` | **Level 1** | Quit without saving (teaches the `!` force modifier) |
| `:wq` | **Level 1** | Save and quit |
| `:e {name}` | Level 13 | Open named dungeon or area |
| `:e ..` | Level 13 | Navigate to parent area |
| `:set number` | Level 13 | Display HP/distance numbers above all enemies |
| `:set nonumber` | Level 13 | Remove number overlays |
| `:set relativenumber` | Scroll item (see §8.2) | Switch y-axis ruler to relative line numbers |
| `:set norelativenumber` | Scroll item (see §8.2) | Switch y-axis ruler back to absolute line numbers |

**Command mode**: Level 13 teaches the rest of Command mode beyond `:w` and `:q` (`:e`, `:set`) once the player is ready.

**Substitution spell** (unlocked at Level 18, costs Arcane Mana):
| Command | Effect | Mana cost |
|---|---|---|
| `:s/{from}/{to}/` | Transform first match in current row | 1 |
| `:s/{from}/{to}/g` | Transform all matches in current row | 3 |
| `:%s/{from}/{to}/g` | Transform all matches in current room | 5 |

Substitution applies to terrain (`wall`, `fire`, `ice`, `water`) and objects (`chest`, `door`, `lever`). Direct enemy transformation requires the `c` operator; `:s/` affects the environment only. Full scope and mana economy are TBD.

---

## 7. Core Gameplay Systems

### 7.1 Keystroke Budget System

The primary puzzle mechanic. Every puzzle room has a **keystroke budget** displayed in the status bar. Reaching the exit within budget is mandatory for puzzle completion.

**Budget types**:
- **Total budget**: `Budget: 8` — all keystrokes combined
- **Mode-split budget**: `Normal: 5 | Insert: 3` — separate pools per mode (used in later dungeons)

**Budget rules**:
- Each key press in a mode costs 1 from that mode's pool
- Entering or exiting a mode does **not** cost budget
- `u` (undo) **returns** the budget cost of the undone keystroke and rewinds all that tick's game actions
- `Ctrl-R` (redo) re-spends the returned budget
- Running out of budget does not kill the player; it signals that a more efficient command is needed (a hint appears)
- Exiting the room without meeting budget = incomplete puzzle; player may re-enter

**Par challenge** (bonus objective, optional):
- Each puzzle room has a par (minimum keystrokes for the intended solution)
- Completing at or under par earns the 2nd star
- Undo keystrokes count against par (though not against survival budget)

**Budget validation during generation** — see Section 10.

### 7.2 Rune Cluster Word System

The dungeon floor is composed of **rune clusters** — groups of Unicode symbols that form visual "words" in the text buffer. `w/b/e` navigate between them exactly as they do in a Vim buffer. This is not a metaphor.

**Cluster properties**:
- Width: 2–6 symbols
- Separated from adjacent clusters by at least 1 empty cell
- Enemies and items can sit on top of clusters (they are part of the word)
- Four visual types vary the dungeon's appearance:

| Type | Gameplay effect |
|---|---|
| Ancient, Verdant, Ember | Decorative only; no gameplay effect |
| **Void** | **Hazardous landing square**: landing on a void cell costs 1 HP. The cell is passable (CellType.FLOOR) — count motions pass through void cells and only the final landing cell triggers damage. Void runes are NOT movement blockers; use walls to stop count motions. |

**Visual feedback**:
- The cluster the player currently occupies: slightly brighter
- Next `w` target: brief highlight flash on keypress (not persistent)

### 7.3 Undo / Redo (Time Manipulation)

| Action | Effect |
|---|---|
| `u` | Rewinds player position, all enemy positions, and any actions to the state before that keystroke; returns that keystroke's budget cost |
| `Ctrl-R` | Reapplies the undone action; re-spends the budget cost |

- Undo stack: unlimited depth within a room; clears on room exit
- Undo and redo have a brief visual flash animation (reverse/forward time effect)
- Undo counts against par but not against survival budget

### 7.4 Combat

Enemies are primarily **barriers to navigation**, not the core challenge. Puzzle rooms require Vim efficiency; combat rooms require applying operators correctly.

**Enemy behavior by mode**:
| Mode | Enemy behavior |
|---|---|
| Normal | Standard patrol routes |
| Insert | Advance toward player (more aggressive) |
| Visual | Completely frozen |
| Command | Paused (player is typing) |

**Contact with enemy**: −1 heart. Player is briefly invincible for 1 second after damage (prevents chain hits).

**Initial enemy types**:
| Name | Symbol | Behavior | Defeated by |
|---|---|---|---|
| Wanderer | `♟` | Random patrol | Any `d` operator |
| Guard | `♜` | Patrols its row | `d$` or `dw` |
| Cluster | Three `◆` symbols | Groups as one word | `dw` (whole-word attack) |
| Blocker | `▬` | Static; blocks path | `dd` (row clear) |

**Enemy HP and inspection**: HP is hidden by default. `:set number` reveals it. Visual mode `v` reveals HP, next move, and weakness on a single enemy.

---

## 8. Health and Progression

### 8.1 Heart Containers

- Starting hearts: 3
- Maximum hearts: 10
- Heart containers found in chests or dropped by bosses
- Maximum 1 heart container per dungeon

### 8.2 Inventory (Roguelike Rules)

- **Persistent inventory**: items carried into a dungeon are always kept, even on death
- **Dungeon inventory**: items found inside the current dungeon are lost on death
- On dungeon completion: all dungeon items become persistent
- Item slots: 8 (expandable with bag upgrades from the Town shop)

**Item categories**:
| Category | Description |
|---|---|
| Spell scrolls | Teach a new Insert mode vocabulary word |
| Keys | Unlock locked doors in dungeons |
| Potions | One-use +1 heart restore |
| Arcane Mana crystals | Fuel for `:s/` substitution spells |
| Heart containers | Permanent +1 max HP |
| **Relative Numbers scroll** | Unlocks `:set relativenumber` / `:set norelativenumber`. Found in a chest from Level 14 onward (after `:set` is introduced in Level 13 — the player already knows the command syntax before they can use the scroll). Switches the y-axis line number ruler from absolute to relative distances — the number beside each row shows exactly how many `j`/`k` presses to reach it. |

### 8.3 Death and Respawn

- On death: respawn at dungeon entry; dungeon interior regenerates (new seed) or player may choose to replay the same seed
- No run loss; progress through dungeons is permanent
- Persistent inventory is always retained

### 8.4 Command Unlock Progression

New commands unlock at level gates: complete a dungeon, unlock the next dungeon and its command set.

On first use of a newly unlocked command, a **brief tutorial overlay** appears:
- The key(s)
- Vim description (`jump to next word`)
- Game effect (`dash to next rune cluster`)
- One in-context example

The hint bar always reflects currently known commands.

---

## 9. Level Curriculum

| # | Dungeon Name | Commands Introduced | Boss? | Notes |
|---|---|---|---|---|
| 0 | The First Cave | `h j k l` · `:wq` | No | Tutorial; introduces rooms, budget concept, rune clusters. After winning, the game prompts `:wq` to return to the overworld — the player's first encounter with command mode. |
| 1 | The Line Halls | `^ $ 0` · `:w` `:q` `:q!` | No | Long corridors; puzzles require reaching line ends efficiently. `:wq` is already known; this level formally introduces `:w` (save without quitting), `:q` (quit with prompt), and `:q!` (force-quit). The exit requires `:wq` to leave. |
| 2 | The Counting Crypts | `[count]` prefix · `x` | Minor | First level with doors. Doors seal room boundaries so `$` is room-scoped and cannot shortcut the puzzle; `x` opens them. Count motions are the only way to navigate efficiently between rooms. Fog of war applies to door-blocked rooms from this level onward. |
| 3 | The Word Mines | `w b e` | No | Rune clusters become central; word-gap puzzles |
| 4 | The Ancient Spire | `gg G` | No | Tall dungeon; top-to-bottom navigation challenges |
| 5 | The Hall of Rooms | `{ }` | No | Dungeon with many chambers; `{ }` jumps between rooms as paragraph boundaries; `hjkl` alone is too slow for inter-room puzzles |
| 6 | The Sword Temple | `d{motion}` | **MAJOR** | First operator; `dl dw d$ dd D`; combat becomes meaningful |
| 7 | The Echo Vaults | `y p` | No | Yank (absorb) and paste (deploy); duplication puzzles |
| 8 | The Transformation Shrine | `c{motion} s{motion}` | No | Change operator; enemy transformation puzzles |
| 9 | The Temple of Repetition | `.` | **MAJOR** | Repeat; combo chaining; efficiency is the entire lesson |
| 10 | The Timekeeper's Domain | `u Ctrl-R` | No | Undo/redo; temporal puzzles; budget-return mechanic taught explicitly |
| 11 | The Sight Sanctum | `v V Ctrl-V` | No | Visual mode; freeze-and-scan puzzles |
| 12 | The Builder's Forge | `i a o I A O` | **MAJOR** | Insert mode; spellcasting and building under enemy pressure |
| 13 | The Archivist's Library | `:e :set` | No | Command mode deep-dive; `:e` for dungeon travel; `:set number`; player realises the overworld they've been navigating *is* a filesystem. `:w` and `:q` are already known; this dungeon shows the full command-line vocabulary. `:set relativenumber` is a findable scroll item, not taught here |
| 14 | The Seekers' Labyrinth | `/ ? n N` | No | Search; all matches highlighted; navigation by pattern |
| 15 | The Waypoint Sanctum | `m {a-z}` `' \`` | No | Marks as fast travel waypoints |
| 16 | The Precision Corridors | `f F t T` | No | Character-find navigation; line-precise puzzles |
| 17 | The Mirror Temple | `%` | No | Bracket/pair matching; paired puzzle elements that must be activated in order |
| 18 | The Alchemist's Workshop | `:s/{}/{}/` | **MAJOR** | Substitution spells; arcane mana introduced |
| 19 | The Grandmaster's Sanctum | `q @ "` registers | **FINAL BOSS** | Macros and registers; record and replay combat sequences |

**Total**: 20 dungeons, 4 major milestone bosses, 1 final boss.

---

## 10. Boss Fights

Bosses appear at major milestones (Levels 6, 9, 12, 18, 19). Each boss:
- Is **immune** to commands not yet introduced in the preceding dungeon group
- Has **multiple phases**, each requiring a different variant of the new command
- Drops a **heart container** and a unique cosmetic reward

**Example: The Sword Demon (Level 6 boss)**:

| Phase | Immunity | Required command |
|---|---|---|
| 1 | All | `dl` (basic left strike) |
| 2 | Splits into three word-clusters | `dw` (word attack hits all) |
| 3 | Retreats to row ends | `d$` (charge to end) |
| 4 | Fills entire row | `dd` (spin attack) |

**Boss room**: No keystroke budget. Boss fights are timed encounters, not efficiency puzzles. The budget system resumes in post-boss chest room.

---

## 11. Procedural Generation

### 11.1 Dungeon Structure

- **Rooms per dungeon**: 3–7 (scales with level)
- **Room size**: 8×6 to 20×14 cells
- **Connections**: 1–3 cell wide corridors or direct doors
- **Room roles assigned before generation**: entry, puzzle (1–2), combat (1–2), chest, safe room, [boss if milestone], exit

### 11.2 Generation Algorithm

```python
def generate_room(room_type, dungeon_level, known_commands, target_commands):
    for attempt in range(MAX_ATTEMPTS):  # MAX_ATTEMPTS = 100
        seed = random_seed()
        room = place_walls_and_floor(seed, room_type)
        room = place_rune_clusters(room, density=cluster_density(dungeon_level))
        room = place_enemies(room, dungeon_level, room_type)
        room = place_items(room, room_type)
        room = place_entry_and_exit(room)

        if validate_room(room, known_commands, target_commands):
            room.seed = seed
            return room

    # Generation failed: use a hand-crafted fallback
    return load_fallback_room(room_type, dungeon_level)
```

Each level maintains at least **3 hand-crafted fallback rooms** per room type in `content/fallback_rooms/`.

### 11.3 Validation Algorithm

```python
def validate_room(room, known_commands, target_commands):
    all_commands = known_commands + target_commands

    # 1. Basic connectivity: can player reach exit at all?
    if not path_exists(room.entry, room.exit, all_commands):
        return False

    # 2. Budget constraints (puzzle rooms only)
    if room.type == PUZZLE:
        min_with_target    = min_keystrokes(room, all_commands)
        min_without_target = min_keystrokes(room, known_commands)

        if min_with_target is None:
            return False  # Unsolvable even with target commands

        budget = math.ceil(min_with_target * 1.4)  # 40 % buffer; see §11.4
        room.par    = min_with_target
        room.budget = budget

        # Room must NOT be solvable within budget using only old commands
        if min_without_target is not None and min_without_target <= budget:
            return False

    # 3. Softlock check: no game state reachable from which exit becomes impossible
    if leads_to_softlock(room, all_commands):
        return False

    return True
```

**Pathfinding**: BFS treating each known command as a movement primitive. The command set defines the movement graph — `w` is an edge that crosses cluster gaps; `hjkl` is not.

### 11.4 Budget Formula

For all puzzle rooms (current and future), the budget is computed from par:

```
budget = ceil(par × 1.4)
```

The 40 % buffer gives a beginner room to explore and backtrack without the puzzle feeling punishing. Par itself is the BFS-minimum keystroke count using only the commands available at that level.

### 11.5 Level 0 Dungeon Layout (The First Cave)

Fixed topology — rune cluster decoration varies by seed, but room positions, corridor geometry, entry/exit, and void guards do not.

```
 col:   0        17 18   21 22       41 42   45 46     61
        ┌Room 0──┐  corridor  ┌Room 1──────┐  corridor  ┌Room 2──┐
 row 0: ████████████████████████████████████████████████████████████
 row 1: █  @     █  ░░░░░░░░  █            █  ░░░░░░░░  ◉ ○(void) █
 row 2: █        █  ░░░░░░░░  █            █  ░░░░░░░░  ○(void)   █
 row 3: █        █  ░░░░░░░░  █            █  ░░░░░░░░  █          █
 row 4: █        ░░░░░░░░░░░░░░░            ░░░░░░░░░░░░░░░          █
 row 5: █        ░░░░░░░░░░░░░░░            ░░░░░░░░░░░░░░░          █
  ...   █        █  ░░░░░░░░  █            █  ░░░░░░░░  █          █
 row 9: ████████████████████████████████████████████████████████████
```

| Property | Value | Derivation |
|---|---|---|
| Room 0 (ENTRY) | 10 rows × 18 cols | composite cols 0–17 |
| Room 1 (PUZZLE) | 10 rows × 20 cols | composite cols 22–41 |
| Room 2 (EXIT) | 10 rows × 16 cols | composite cols 46–61 |
| Corridor length | 4 cells (+ 1 wall each side = 6 carved) | cols 17–22 and 41–46 |
| Corridor rows | 4 and 5 (2-cell wide, centred) | mid = total_rows // 2 = 5 |
| Entry position | row 1, col 2 | top-left interior of Room 0 |
| Exit position | row 1, col 47 | top-left interior of Room 2 |
| Void guards | rows 2–3, col 47 | block straight-up path; force right detour then `h` |
| **Par** | **BFS-computed per seed** | avoids void cells; typically ~50–60 keystrokes |
| **Budget** | **⌈par × 1.4⌉** | — |

**Layout rationale**: Entry at row 1 forces `j` to reach the corridors (rows 4–5); exit at row 1 of Room 2 forces `k` to climb back up; void guards at rows 2–3, col 47 block the straight vertical ascent and require the player to step right then press `h` back to the exit. This guarantees all four of `h/j/k/l` are necessary on every seed.

**Corridor connectivity rule**: when carving a corridor between two rooms, the carving range must include the right wall of the left room and the left wall of the right room, not just the gap cells between them. Carving only the gap leaves two wall cells that block movement.

### 11.7 Seed System

- Each dungeon run is assigned a seed at generation time; stored in save file
- On dungeon completion screen: seed is displayed (`Seed: 7a3f91`)
- Player chooses **New run** (fresh seed) or **Replay** (same seed)
- `:e dungeon_name seed=7a3f91` in Command mode opens a specific seed directly

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

If the player has found the **Relative Numbers scroll** (§8.2) and toggled `:set relativenumber`, the ruler switches to relative distances — every row shows how many `j`/`k` presses it is from the cursor, and the cursor row shows its absolute number. Toggling is persistent across sessions (saved with the player's settings).

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

## 13. Save System

**Save location**: `~/.Vimny/save.json`

**What is saved**: dungeon seed, room state, player position, HP, persistent inventory, known commands, star ratings, hard mode flag.

**Auto-save triggers**: safe room entry, dungeon completion, `:w` command.

**`:w`**: Saves from anywhere — dungeon or overworld. Teaches the habit.

**`:q`**: If unsaved: prompts `Save before quitting? :w / :q! / cancel`. `:q!` force-quits without saving — teaches the `!` modifier.

---

## 14. Open Questions / TBD

| Topic | Status | Notes |
|---|---|---|
| `:s/` mana economy | TBD | Drop rates, max stock, regeneration |
| `c` operator Insert timeout | TBD | How long before transformation randomises |
| Full spell vocabulary | TBD | Expand beyond initial 7 words |
| Town of Normalmode | TBD | NPC dialogue, shop inventory, side quests |
| Named registers (`"a`–`"z`) | TBD | Whether registers have distinct game-mechanic meaning |

---

## Checklist

- Title screen - Done
- Dungeon level floors, corridors and doors - Done
- Level 0 - Done
- Level 1 - Done
- Level 2 - Done
- Level 3
- Level 4
- Level 5
- Level 6
- Level 7
- Level 8
- Level 9
- Level 10
- Level 11
- Level 12
- Level 13
- Level 14
- Level 15
- Level 16
- Level 17
- Level 18
- Level 19
- Level 20
- Music
- Combat
- Enemy 1
- Boss dungeon
- Boss 1
- Chests
