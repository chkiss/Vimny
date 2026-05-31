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

The curriculum is defined in `content/levels.py` (canonical) and mirrored in `LEVELS_PLAN.md` Part 7. "Playable" means a generator is implemented; the rest are defined but not yet built. This table is generated — run `python3 content/_gen_curriculum_table.py` after curriculum changes.

<!-- BEGIN GENERATED LEVELS TABLE -->
| # | Name | Commands | Status |
|---|---|---|---|
| 0 | The First Cave | `h j k l u :w :q :q!` | Playable |
| 1 | The Line Halls | `^ $ 0` | Playable |
| 1.1 | The Reliquary | `"` | Playable |
| 2 | The Counting Crypts | `[count] prefix` | Playable |
| 3 | The Rune Halls | `w b e` | Playable |
| 4 | The Character Cataracts | `f F t T` | Playable |
| 5 | The Goblin Gauntlet | `; , p` | Playable |
| 5.1 | The Warden's Keep | (boss) | Playable |
| 6 | The WORD Forge | `W B E` | Playable |
| 7 | The Backward Vaults | `ge gE` | Playable |
| 8 | The Lineheads | `G gg` | Playable |
| 9 | The Screen Vault | `H M L` | Playable |
| 10 | The Bracket Vaults | `%` | Playable |
| 12 | The Runic Archives | `} {` | Playable |
| 13 | The Sentence Corridor | `) (` | Playable |
| 13.1 | The Warden Surveyor | (boss) | Planned |
| 14 | The Sight Sanctum | `v` | Playable |
| 15 | The Seekers' Labyrinth | `/ ? n N` | Planned |
| 16 | The Waypoint Sanctum | `` m ' ` `` | Planned |
| 17 | The Archivist's Library | `:e :set` | Planned |
| 17.1 | The Warden Pathfinder | (boss) | Planned |
| 18 | The Operator's Vault | `d c` | Planned |
| 19 | The Whole-Line Annex | `dd cc D S` | Planned |
| 20 | The Quartermaster | `y yy P` | Planned |
| 21 | The Undo Sanctum | — | Planned |
| 22 | The Echo Vault | `.` | Planned |
| 22.1 | The Warden Manifold | (boss) | Planned |
| 23 | The Inscription Halls | `i a` | Planned |
| 24 | The Sculpting Chambers | `I A o O` | Planned |
| 25 | The Overwrite Halls | `r R` | Planned |
| 26 | The Case Chambers | `~ g~ gU gu` | Planned |
| 27 | The Joiner's Gate | `J gJ` | Planned |
| 28 | The Alignment Halls | `>> <<` | Planned |
| 29 | The Indentation Sanctum | `>{m} <{m} =` | Planned |
| 29.1 | The Warden Scrivener | (boss) | Planned |
| 30 | The Word Enclosure | `iw aw` | Planned |
| 31 | The Bracket Enclosure | `i( a(` | Planned |
| 32 | The Brace & Square Enclosure | `i[ a[ i{ a{` | Planned |
| 33 | The Quote Enclosure | `i" a" i' a'` | Planned |
| 34 | The Tag Enclosure | `it at` | Planned |
| 35 | The Sentence Enclosure | `is as` | Planned |
| 36 | The Paragraph Enclosure | `ip ap` | Planned |
| 36.1 | The Grandmaster's Sanctum | (boss) | Planned |
| 37 | The Spellwright's Forge | `:s///` | Planned |
| 38 | The Hall of Echoes | `q @ "` | Planned |
| 38.1 | The Warden Eternal | (boss) | Planned |
<!-- END GENERATED LEVELS TABLE -->

## Commands

The full command reference (also the hint-bar source) is `render/vim_commands.md`; this table mirrors it.

<details><summary>Show all commands</summary>

<!-- BEGIN GENERATED COMMANDS TABLE -->
| Command | Effect |
|---|---|
| `u` | undo |
| `:w` | write (save) |
| `:q` | quit |
| `:q!` | quit without saving |
| `h` | left |
| `j` | down |
| `k` | up |
| `l` | right |
| `0` | line start |
| `^` | first non-blank |
| `$` | end of line |
| `[N]hjkl` | count move |
| `x` | delete char |
| `w` | word start |
| `b` | word back |
| `e` | word end |
| `f{c}` | jump to char |
| `F{c}` | jump back to char |
| `t{c}` | before next char |
| `T{c}` | after prev char |
| `;` | repeat |
| `,` | reverse |
| `p` | paste |
| `W` | WORD start |
| `B` | WORD back |
| `E` | WORD end |
| `ge` | word-end back |
| `gE` | WORD-end back |
| `G` | last line |
| `gg` | first line |
| `[N]G` | go to line N |
| `H` | top of screen |
| `M` | middle of screen |
| `L` | bottom of screen |
| `%` | match bracket |
| `}` | next block |
| `{` | prev block |
| `)` | next sentence |
| `(` | prev sentence |
| `v` | visual mode |
| `/{pat}` | search |
| `n` | next match |
| `N` | prev match |
| `*` | search word |
| `m{a}` | set mark |
| `` `{a} `` | to mark |
| `'{a}` | to mark ↑ |
| `d{m}` | delete |
| `dd` | delete line |
| `c{m}` | change |
| `cc` | change line |
| `s` | substitute |
| `S` | substitute line |
| `y{m}` | yank |
| `yy` | yank line |
| `P` | paste before |
| `"{r}{op}` | named register |
| `.` | repeat change |
| `i` | insert |
| `a` | append |
| `o` | new line below |
| `O` | new line above |
| `I` | insert at start |
| `A` | append at end |
| `Esc` | exit insert |
| `r{c}` | replace char |
| `R` | replace mode |
| `~` | toggle case |
| `gU{m}` | uppercase |
| `gu{m}` | lowercase |
| `g~{m}` | toggle case |
| `J` | join lines |
| `gJ` | join, no space |
| `>{m}` | indent |
| `<{m}` | dedent |
| `iw` | inner word |
| `aw` | a word |
| `i(` | inner ( |
| `a(` | a () |
| `i[` | inner [ |
| `a[` | a [] |
| `i{` | inner { |
| `a{` | a {} |
| `i"` | inner " |
| `a"` | a "" |
| `i'` | inner ' |
| `a'` | a '' |
| `it` | inner tag |
| `at` | a tag |
| `is` | inner sentence |
| `as` | a sentence |
| `ip` | inner paragraph |
| `ap` | a paragraph |
| `q{a}` | record macro |
| `@{a}` | play macro |
| `@@` | repeat macro |
| `"{a}` | named reg |
<!-- END GENERATED COMMANDS TABLE -->

</details>

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
  dungeon_gen.py         build_dungeon_<slug> per level, Dijkstra par solvers
content/
  levels.py              Level definitions (slug identity), known_commands(slug)
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
