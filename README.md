# Vimny

A terminal dungeon crawler that teaches Vim through play. The dungeons are text buffers; every puzzle is solved with Vim commands. Efficiency is the mechanic — fewer keystrokes means more power.

```
┌──────────────────────────────────────────────────────────────────────────────┐
│  ♥♥♥♥♥░░░░░  The WORD Forge           -- NORMAL --   Budget: 14   Par: 10    │
├──────────────────────────────────────────────────────────────────────────────┤
│     0         1         2         3         4         5                      │
│     |123456789|123456789|123456789|123456789|123456789|1                     │
│  1 ████████████████████████████████████████████████████████                  │
│  2 █  @  result=func  (a,b)+val  x=y*2               fn  ██                  │
│  3 ██████████████████████████████████████████████████████░░                  │
│  4 ██░░ go  x+=y*2  int[]  main()                        ██                  │
│  5 ██░░██████████████████████████████████████████████████░░                  │
│  6 ████████████████████████████████████████████████████████                  │
│  7 █  if  res  val           output=data[n]._key         ◉█                  │
│  8 ████████████████████████████████████████████████████████                  │
├──────────────────────────────────────────────────────────────────────────────┤
│  W:next-WORD  B:prev-WORD  E:end-WORD  w:next-word  b:prev-word  e:end-word  │
└──────────────────────────────────────────────────────────────────────────────┘
```

## Requirements

- Python 3.9+
- `blessed` library

```bash
pip install blessed
```

## Running

```bash
python main.py
```

Player progress is saved automatically to `~/.Vimny/saves/<player>.json` (one file per player).

## How it works

Each dungeon is a text buffer. The floor is made of **character runs** — groups of symbols that act as Vim words. You navigate with real Vim commands and must reach the exit within a **keystroke budget**. Editing reflows the line exactly as Vim does: insert/delete/paste shift content along the row, and anything shoved past a wall or void rune falls into the void.

| Dungeon concept | Vim concept |
|---|---|
| Floor cells | Characters |
| Character runs | Words |
| Empty floor between runs | Whitespace |
| Room row | Line |
| Room wall | End of line |
| Dungeon | File |

**Keystroke budget**: Every puzzle room displays a budget. Reaching the exit within it completes the room. The par is the minimum possible keystrokes using the level's taught commands — hitting par earns a second star. `u` (undo) returns budget; you can backtrack freely.

**Void runes**: Landing on a void cell costs 1 HP. Count motions pass through void cells silently; only the final landing cell triggers damage. This mirrors Vim's motion semantics exactly.

## Levels

| # | Name | Commands | Status |
|---|---|---|---|
| 0 | The First Cave | `h j k l` · `u` · `:w :q :q!` | Playable |
| 1 | The Line Halls | `^ $ 0` | Playable |
| 1.1 | The Reliquary | (review) | Playable |
| 2 | The Counting Crypts | `[count]` · `x` | Playable |
| 3 | The Rune Halls | `w b e` | Playable |
| 4 | The Character Cataracts | `f F t T` | Playable |
| 5 | The Goblin Gauntlet | `; , p` | Playable |
| 5.1 | The Warden's Keep | (boss) | Playable |
| 6 | The WORD Forge | `W B E` | Playable |
| 7 | The Backward Vaults | `ge gE` | Playable |
| 8 | The Lineheads | `gg G` | Playable |
| 9 | The Screen Vault | `H M L` | Playable |
| 10 | The Bracket Vaults | `%` | Playable |
| 12 | The Runic Archives | `} {` | Playable |
| 13 | The Sentence Corridor | `) (` | Playable |
| 14 | The Sight Sanctum | `v` | Playable |
| 15+ | — | — | Defined in `content/levels.py`; generators pending |

Full curriculum (all 39 levels + bosses): `content/levels.py` (canonical) and `LEVELS_PLAN.md` Part 7.

## Commands taught so far

| Command | Effect |
|---|---|
| `h j k l` | Move one cell in each direction |
| `0` / `^` / `$` | Jump to column 0 / first non-blank cell / last cell in the row |
| `[count]motion` | Repeat any motion N times (`5l`, `3j`) |
| `x` | Interact — open door / loot chest |
| `w` / `b` / `e` | Next word start / previous word start / word end |
| `W` / `B` / `E` | Same, but WORD (whitespace-delimited; punctuation does not break a WORD) |
| `ge` / `gE` | Backward to end of previous word / WORD |
| `f{c}` / `F{c}` | Jump to next/previous character `c` in the row |
| `t{c}` / `T{c}` | Jump till before/after character `c` |
| `;` / `,` | Repeat last `f F t T` forward/backward |
| `gg` / `G` | Jump to first / last line (first non-blank cell) |
| `H` / `M` / `L` | Jump to top / middle / bottom of the screen |
| `%` | Jump to the matching bracket |
| `}` / `{` | Next / previous paragraph |
| `)` / `(` | Next / previous sentence |
| `v` | Visual select |
| `p` / `P` | Paste after / before the cursor |
| `u` | Undo (returns budget) |
| `:w` `:q` `:q!` `:wq` | Save / quit / force-quit / save-and-quit |

## Project layout

```
main.py                  Game loop, run_dungeon / run_overworld, apply_motion
engine/
  world.py               Room, Dungeon, Entity, CharRun, CellType
  player.py              Player dataclass
  vim_parser.py          Keystroke → action dict
  motion.py              apply_motion, move_player
  reflow.py              Reflow editing primitives (insert/delete/join/ledge-build)
  budget.py              Budget tracking
generation/
  dungeon_gen.py         build_dungeon_0…14 (+ 51 boss), Dijkstra par solvers
content/
  levels.py              Level definitions, known_commands()
render/
  renderer.py            Read-only dungeon view (no mutation)
  overworld.py           Read-only netrw overworld buffer
  hint_bar.py            Hint-bar text (reads vim_commands.md)
  vim_commands.md        Hint-bar text source (token → keys/desc)
save/
  save_manager.py        Progress I/O, layout save
tests/                   pytest test suite
SPEC.md                  Design vision, UI spec, forward-looking notes
LEVELS_PLAN.md           Curriculum plan (Part 7 = canonical level table)
```

## Running tests

```bash
pytest
```

## Design principles

- **Vim fidelity above all else.** Commands behave exactly as they do in Vim.
- **Efficiency is the skill.** The keystroke budget makes Vim's core value proposition mechanically central.
- **Everything is a buffer.** Dungeons are files; the overworld is a directory; `:w`, `:q`, `:e` are real mechanics.
- **Renderer never mutates state.** Required for a future web port (same logic, swap renderer for xterm.js).

See `LEVELS_PLAN.md` for the curriculum and `SPEC.md` for design vision & UI.
