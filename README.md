# Vimny

A TUI dungeon crawler that teaches Vim through play. The dungeons are text buffers and every puzzle is solved with Vim commands. Hitting the "par" means you fully learned the lesson.

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
- A terminal **at least 80 columns** wide (the supported minimum). The playfield
  grows with the window up to **189 columns** (the overworld and The Archivist's
  Library use the extra width); beyond that it stops widening.

```bash
pip install blessed
```

## Running

```bash
python main.py
```

Player progress is saved automatically to `~/.Vimny/saves/<player>.json` (one file per player).

## How it works

Each dungeon is a text buffer. The floor is made of **characters, words, and spaces** — you navigate with real Vim commands and must reach the exit within a **keystroke budget**. Editing reflows the line exactly as Vim does: insert/delete/paste shift content along the row, and anything shoved past a wall or void rune falls into the void.

| Dungeon concept          | Vim concept |
|--------------------------|-------------|
| Floor cells              | Characters  |
| Character runs           | Words       |
| Empty floor between runs | Whitespace  |
| Room row                 | Line        |
| Room wall                | End of line |
| Dungeon                  | File        |

**Keystroke budget**: Every puzzle room displays a budget. Reaching the exit within it completes the room. The par is the minimum possible keystrokes using the level's taught commands — hitting par earns a second star. `u` (undo) returns budget; you can backtrack freely.

> **Note — par is not the absolute minimum on search levels.** On levels that use search (`/`, `?`), par is computed assuming you type the **full search term** the level highlights (e.g. `/cipher⏎`). Because a search pattern only needs enough characters to land uniquely on the target, an expert can type a shorter prefix (e.g. `/cip⏎`) and finish *under* par. This is intentional and consistent across all search levels: par rewards "type the word you see," and the budget leaves headroom for prefix-search optimization.

**Void runes**: Landing on a void cell costs 1 HP. Count motions pass through void cells silently; only the final landing cell triggers damage. This mirrors Vim's motion semantics exactly.

## Levels

The curriculum is defined in `content/levels.py` (canonical) and mirrored in `LEVELS_PLAN.md` Part 7. "Playable" means a generator is implemented; the rest are defined but not yet built. This table is generated — run `python3 content/_gen_curriculum_table.py` after curriculum changes.

<!-- BEGIN GENERATED LEVELS TABLE -->
| # | Name | Commands | Status |
|---|---|---|---|
| 0 | The First Cave | `h j k l u :w :q :q!` | Playable |
| 1 | The Line Halls | `^ $ 0` | Playable |
| 1.1 | The Reliquary | `x` | Playable |
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
| 13.1 | The Warden Surveyor | (boss) | Playable |
| 14 | The Seekers' Labyrinth | `/ ? n N *` | Playable |
| 15 | The Waypoint Sanctum | `` m ' ` `` | Playable |
| 16 | The Archivist's Library | `:set wrap  :e!  :w {file}` | Playable |
| 16.1 | The Warden Pathfinder | (boss) | Playable |
| 17 | The Operator's Vault | `d{m}  dd` | Playable |
| 18 | The Cipher Cell | `r  D` | Playable |
| 19 | The Beacon Tiers | `y yy P` | Playable |
| 20 | The Echo Vault | `.` | Playable |
| 20.1 | The Warden Manifold | (boss) | Playable |
| 21 | The Inscription Halls | `i a` | Playable |
| 22 | The Change Annex | `c{m}  cE  cc  s` | Playable |
| 23 | The Change Extension | `S  C` | Playable |
| 24 | The Sculpting Chambers | `I A o O` | Playable |
| 25 | The Overwrite Halls | `R` | Playable |
| 26 | The Case Chambers | `~ g~ gU gu` | Playable |
| 27 | The Joiner's Gate | `J gJ` | Playable |
| 28 | The Alignment Halls | `>> <<` | Playable |
| 29 | The Indentation Sanctum | `>{m} <{m} =` | Playable |
| 29.1 | The Warden Scrivener | (boss) | Playable |
| 30 | The Sight Sanctum | `v {m} d/c/~` | Playable |
| 31 | The Selection Halls | `V  <C-v>` | Playable |
| 32 | The Word Enclosure | `iw aw iW aW` | Playable |
| 33 | The Bracket Enclosure | `i( a(` | Planned |
| 34 | The Brace & Square Enclosure | `i[ a[ i{ a{` | Planned |
| 35 | The Quote Enclosure | `i" a" i' a'` | Planned |
| 36 | The Tag Enclosure | `it at` | Planned |
| 37 | The Sentence Enclosure | `is as` | Planned |
| 38 | The Paragraph Enclosure | `ip ap` | Planned |
| 38.1 | The Grandmaster's Sanctum | (boss) | Planned |
| 39 | The Spellwright's Forge | `:s///  :g  &` | Playable |
| 40 | The Hall of Echoes | `q @ "` | Planned |
| 40.1 | The Warden Eternal | (boss) | Planned |
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
| `x` | delete char |
| `[N]hjkl` | count move |
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
| `v{m}d/c/~` | act on the selection |
| `V` | select whole lines |
| `<C-v>` | select a block |
| `/{pat}` | search |
| `?{pat}` | search back |
| `n` | next match |
| `N` | prev match |
| `*` | search word |
| `m{a}` | set mark |
| `` `{a} `` | to mark |
| `'{a}` | to mark ↑ |
| `:set wrap` | wrap lines |
| `:e!` | reload file |
| `:w {file}` | save as |
| `d{m}  dd` | delete |
| `c{m}` | change |
| `cc` | change line |
| `r{c}` | replace char |
| `D` | delete to line end |
| `c{m}  cc` | change |
| `s` | substitute |
| `S` | substitute line |
| `C` | change to end |
| `y{m}  yy` | yank |
| `P` | paste before |
| `.` | repeat change |
| `i` | insert |
| `a` | append |
| `Esc` | exit insert |
| `I` | insert at start |
| `A` | append at end |
| `o` | new line below |
| `O` | new line above |
| `R` | replace mode |
| `~` | toggle case |
| `gU{m}` | uppercase |
| `gu{m}` | lowercase |
| `g~{m}` | toggle case |
| `J` | join lines |
| `gJ` | join, no space |
| `>{m}` | indent |
| `<{m}` | dedent |
| `={m}` | apply the law |
| `V` | visual line |
| `<C-v>` | visual block |
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
| `:s/old/new/` | substitute |
| `:%s//g` | substitute all |
| `:g/pat/d` | global delete |
| `&` | repeat last :s |
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
  search.py              / ? n N * # — Vim-regex search, matched per line
  substitute.py          :s :g :v & — ex substitute & global
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
- **Efficiency is enforced by par and budget.** The keystroke budget makes Vim's core value proposition central, and the par encourages the player to strive for perfect execution efficiency.
- **Everything is a buffer.** Dungeons are files; the overworld is a directory; `:w`, `:q`, `:e` are real mechanics.

See `LEVELS_PLAN.md` for the curriculum and `SPEC.md` for design vision & UI.

## License

Vimny is free software, licensed under the **GNU General Public License v3.0** —
see [`LICENSE`](LICENSE) for the full text. The only runtime dependency,
[`blessed`](https://pypi.org/project/blessed/), is MIT-licensed and so
GPL-compatible.
