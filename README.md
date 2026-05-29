# Vimny

A terminal dungeon crawler that teaches Vim through play. The dungeons are text buffers; every puzzle is solved with Vim commands. Efficiency is the mechanic — fewer keystrokes means more power.

```
┌──────────────────────────────────────────────────────────────────────────────┐
│  ♥♥♥♥♥░░░░░  The Word Mines           -- NORMAL --   Budget: 14   Par: 10    │
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

Player progress is saved to `~/.Vimny/save.json` automatically.

## How it works

Each dungeon is a text buffer. The floor is made of **rune clusters** — groups of symbols that act as Vim words. You navigate with real Vim commands and must reach the exit within a **keystroke budget**.

| Dungeon concept | Vim concept |
|---|---|
| Floor cells | Characters |
| Rune clusters | Words |
| Empty floor between clusters | Whitespace |
| Room row | Line |
| Room wall | End of line |
| Dungeon | File |

**Keystroke budget**: Every puzzle room displays a budget. Reaching the exit within it completes the room. The par is the minimum possible keystrokes using the level's taught commands — hitting par earns a second star. `u` (undo) returns budget; you can backtrack freely.

**Void runes**: Landing on a void cell costs 1 HP. Count motions pass through void cells silently; only the final landing cell triggers damage. This mirrors Vim's motion semantics exactly.

## Levels

| # | Name | Commands | Status |
|---|---|---|---|
| 0 | The First Cave | `h j k l` · `:wq` | Playable |
| 1 | The Line Halls | `^ $ 0` · `:w :q :q!` | Playable |
| 1.1 | The Reliquary | (review) | Playable |
| 2 | The Counting Crypts | `[count]` · `x` | Playable |
| 3 | The Rune Halls | `w b e` | Playable |
| 4 | The Character Cataracts | `f F t T` | Playable |
| 5 | The Goblin Gauntlet | `; ,` | Playable |
| 5.1 | The Warden's Keep | (miniboss) | Playable |
| 6 | The Warden's Sight | `W B E` | Playable |
| 7+ | — | — | Planned |

Full curriculum (20 dungeons) in `SPEC.md`.

## Commands taught so far

| Command | Effect |
|---|---|
| `h j k l` | Move one cell in each direction |
| `0` | Jump to leftmost cell in row |
| `^` | Jump to first rune cluster in row |
| `$` | Jump to last rune cluster in row |
| `[count]motion` | Repeat any motion N times (`5l`, `3j`) |
| `x` | Open door / loot chest |
| `w` / `b` / `e` | Next word start / previous word start / word end |
| `W` / `B` / `E` | Same, but WORD (ignores gaps between adjacent clusters) |
| `f{c}` / `F{c}` | Jump to next/previous character `c` in row |
| `t{c}` / `T{c}` | Jump to before/after character `c` |
| `;` / `,` | Repeat last `f/F/t/T` forward/backward |
| `gg` / `G` | Jump to first / last line (first non-blank column) |
| `u` | Undo (returns budget) |
| `:w` `:q` `:q!` `:wq` | Save / quit / force-quit / save-and-quit |

## Project layout

```
main.py                  Game loop
engine/
  world.py               Room, Dungeon, Entity, RuneCluster, CellType
  player.py              Player dataclass
  vim_parser.py          Keystroke → action dict
  motion.py              apply_motion, move_player
  budget.py              Budget tracking
generation/
  dungeon_gen.py         build_dungeon_0…6, Dijkstra par solvers
content/
  levels.py              Level definitions, known_commands()
render/
  renderer.py            Read-only view of state (no mutation)
save/
  save_manager.py        Progress I/O, layout save
tests/                   942 tests; pytest
SPEC.md                  Full design specification
developer/               Level plan documents
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

See `SPEC.md` for the complete design document.
