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

Linux and macOS are the supported platforms. Windows is untested — the game no
longer *refuses* to start there, but `blessed`'s Windows support is partial and
the terminal handling has not been verified.

## Running

From a checkout:

```bash
pip install blessed
python main.py
```

Or install it:

```bash
pip install .
vimny
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

> **Note — par is not the absolute minimum on search levels.** On levels that use search (`/`, `?`), par is computed assuming you type the **full search term** the level highlights (e.g. `/cipher<CR>`). Because a search pattern only needs enough characters to land uniquely on the target, an expert can type a shorter prefix (e.g. `/cip<CR>`) and finish *under* par. This is intentional and consistent across all search levels: par rewards "type the word you see," and the budget leaves headroom for prefix-search optimization.

**Terrain**: Levels use terrain to make a particular Vim command the *only* good answer, rather than merely the intended one.

- **Void runes** — holes in the floor. Landing on one costs 1 HP, but count motions pass *through* them silently: only the final landing cell bites. So a void rune bars stepping, never jumping.
- **Water** — impassable on foot; you have to jump over it.
- **Fogged water** — impassable on foot *and* opaque, so a blind jump like `$` won't clear it. You have to aim at a character you can see.

## Levels

The main game sequence is complete — every level below is playable.

<!-- BEGIN GENERATED LEVELS TABLE -->
| # | Name | Commands |
|---|---|---|
| 0 | The First Cave | `h j k l u :w :q :q!` |
| 1 | The Line Halls | `^ $ 0` |
| 1.1 | The Reliquary | `x` |
| 2 | The Counting Crypts | `[count] prefix` |
| 3 | The Rune Halls | `w b e` |
| 4 | The Character Cataracts | `f F t T` |
| 5 | The Goblin Gauntlet | `; , p` |
| 5.1 | The Warden's Keep | (boss) |
| 6 | The WORD Forge | `W B E` |
| 7 | The Backward Vaults | `ge gE` |
| 8 | The Lineheads | `G gg` |
| 9 | The Screen Vault | `H M L` |
| 10 | The Bracket Vaults | `%` |
| 12 | The Runic Archives | `} {` |
| 13 | The Sentence Corridor | `) (` |
| 13.1 | The Warden Surveyor | (boss) |
| 14 | The Seekers' Labyrinth | `/ ? n N * #` |
| 14.1 | The Binder's Reliquary | `:h za :q` |
| 15 | The Waypoint Sanctum | `` m ' ` `` |
| 16 | The Archivist's Library | `:set wrap  :e!  :w {file}` |
| 16.1 | The Warden Pathfinder | (boss) |
| 17 | The Operator's Vault | `d{m}  dd` |
| 18 | The Cipher Cell | `r  D  X` |
| 19 | The Beacon Tiers | `y yy P` |
| 20 | The Echo Vault | `.` |
| 20.1 | The Warden Manifold | (boss) |
| 21 | The Inscription Halls | `i a` |
| 22 | The Change Annex | `c{m}  cE  cc  s` |
| 23 | The Change Extension | `S  C  Y` |
| 24 | The Sculpting Chambers | `I A o O` |
| 25 | The Overwrite Halls | `R` |
| 26 | The Case Chambers | `~ g~ gU gu` |
| 27 | The Joiner's Gate | `J gJ` |
| 28 | The Alignment Halls | `>> <<` |
| 29 | The Indentation Sanctum | `>{m} <{m} =` |
| 29.1 | The Warden Scrivener | (boss) |
| 30 | The Sight Sanctum | `v {m} d/c/~` |
| 31 | The Selection Halls | `V  <C-v>` |
| 32 | The Word Enclosure | `iw aw iW aW` |
| 33 | The Bracket Enclosure | `i( a(` |
| 34 | The Brace & Square Enclosure | `i[ a[ i{ a{` |
| 35 | The Quote Enclosure | `i" a" i' a'` |
| 36 | The Tag Enclosure | `it at` |
| 37 | The Sentence Enclosure | `is as` |
| 38 | The Paragraph Enclosure | `ip ap` |
| 38.1 | The Grandmaster's Sanctum | (boss) |
| 39 | The Spellwright's Forge | `:s///  :g  &` |
| 40 | The Culling Ledger | `:d _ :a,bd :v//d` |
| 41 | The Shelving Room | `:m :t :> :<` |
| 42 | The Refrain Vault | `& :&& :j :y` |
| 43 | The Stair Rail | `+ - _` |
| 44 | The Last Reach | `g_ g* gi gp` |
| 45 | The Buried Word | `g* n` |
| 46 | The Wet Ink | `gi` |
| 47 | The Hall of Echoes | `q @ "` |
| 48 | The Gauntlet | — |
| 48.1 | The Warden Eternal | (boss) |
| R1 | The Unnamed Hold | `""  y  p` |
| R2 | The Named Vault | `"ay  "by  "aP  "bP` |
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
| `v{m} d/c/~/p/r/J` | act on the selection |
| `V` | select whole lines |
| `<C-v>` | select a block |
| `:h {name}` | open the Codex to a page |
| `za` | unfold / fold a section |
| `:q` | close the book |
| `/{pat}` | search |
| `?{pat}` | search back |
| `n` | next match |
| `N` | prev match |
| `*` | search word |
| `#` | search word back |
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
| `X` | delete before cursor |
| `c{m}  cc` | change |
| `s` | substitute |
| `S` | substitute line |
| `C` | change to end |
| `Y` | yank line |
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
| `iw` | inner word |
| `aw` | a word |
| `iW` | inner WORD |
| `aW` | a WORD |
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
| `:{n}d` | delete line n |
| `:{a},{b}d` | delete range |
| `:{r}v//d` | keep matching |
| `:d _` | cut, keep reg |
| `q{a}` | record macro |
| `@{a}` | play macro |
| `@@` | repeat macro |
| `"{a}` | named reg |
| `+` | down, first word |
| `{n}_` | to line n below |
| `g_` | last non-blank |
| `g*` | search substring |
| `g#` | substring back |
| `gi` | resume inserting |
| `gp` | paste, cursor after |
<!-- END GENERATED COMMANDS TABLE -->

</details>

### What Vim commands does Vimny not teach?

Vimny aims for Vim-faithfulness in everything it *does* implement, but some
commands are deliberately out of scope:

- **Scrolling & viewport** — `zz` `zt` `zb` `<C-d>` `<C-u>` `<C-f>` `<C-b>`
  `<C-e>` `<C-y>`: dungeons fit the screen; there is no viewport-scroll
  model (`H`/`M`/`L` are the only screen-relative commands).
- **`U` (vi's line-undo)** — `u` and the redo scroll (`<C-r>`) cover the
  undo story; a third undo channel would complicate it for a key modern Vim
  users rarely reach for.
- **Window/tab/buffer management** — Vimny is a single buffer by design;
  each dungeon *is* the file. On the roadmap, not in the curriculum.
- **Insert-mode editing keys** — `<C-w>`, `<C-u>`, `<C-o>`, `<C-r>{reg}` are
  implemented and can be found as scrolls, but no level *teaches* them. They
  are priced to be free (`<C-w>` and `<C-u>` cost nothing; `<C-r>` charges per
  pasted character, exactly what typing the text would cost), so no puzzle can
  force them at par — which is what a Vimny level does. Pricing them by
  keystroke instead would make a register paste cheaper than typing and hand
  every text-entry level a shortcut, so they stay free flourishes rather than
  curriculum. See Upcoming features.
- **Completion, plugins, ex-mode scripting** — out of scope.
- **NORMAL-mode `Enter`** — a duplicate of `+`, which the Stair Rail
  already teaches.

## Project layout

```
main.py                  Game loop, run_dungeon / run_overworld, the forge
engine/
  world.py               Room, Dungeon, Entity, CharRun, CellType, Seal
  player.py              Player dataclass
  vim_parser.py          Keystroke → action dict
  command_guard.py       action_allowed — what the curriculum has taught yet
  motion.py              apply_motion, move_player, the fog laws
  operator.py            d y c p and friends — operator + text object
  text_object.py         iw aw i( a" ip … — the spans an operator acts on
  insert.py              i a I A o O s S, INSERT-mode editing
  reflow.py              Reflow editing primitives (insert/delete/join/ledge-build)
  visual.py              v V <C-v> — the selections
  search.py              / ? n N * # — Vim-regex search, matched per line
  substitute.py          :s :g :v & — ex substitute & global
  registers.py           named/unnamed registers, clip ↔ text
  macro.py               q @ — record and replay
  jumplist.py            <C-o> <C-i> — where you have been
  tape.py                The keystroke-tape notation (<Space> <CR> <Esc> <C-v>)
  budget.py              Budget tracking
generation/
  dungeon_gen.py         build_dungeon_<slug> per level, par solvers
content/
  levels.py              Level definitions (slug identity), known_commands(slug)
  scrolls.py             Scroll text + the scroll catalogue
  passwords.py           The password pools a fancy_door opens for
render/
  renderer.py            Read-only dungeon view (no mutation)
  overworld.py           Read-only netrw overworld buffer
  title.py               Title screen and name prompt
  scroll_library.py      The scrolls you have collected
  remote_shelf.py        Browse the remote level shelf
  symbols.py             Every glyph the game draws, with width fallbacks
  hint_bar.py            Hint-bar text (reads vim_commands.md)
  vim_commands.md        Hint-bar text source (token → keys/desc)
sharing/                 Levels as DATA — the authoring/sharing pipeline
  format.py              The level file format: parse, build, export
  validate.py            Every rule a level file must satisfy
  draft.py               The forge's in-progress level
  replay.py              Replay a keystroke tape through the real game loop
  jumpgolf.py            Does a line jump beat a tape's travel? (par audit)
  remote.py              The one place Vimny makes a network request
  cli.py                 python3 -m sharing — validate / audit / export / …
save/
  save_manager.py        Progress I/O, layout save
tests/                   pytest test suite
docs/ARCHITECTURE.md     The canonical reference: architecture, laws, conventions
docs/AUTHORING.md        Writing a level, in the forge or in an editor
SPEC.md                  Design vision, UI spec, forward-looking notes
LEVELS_PLAN.md           Design rubric + the levels not yet built
```

## Writing your own levels

There are two ways in, and they produce the same thing — a level is a plain JSON
file either way.

**In the game — the forge.** An authoring bench in the overworld under `forge/`,
where a level is built by playing it: paint the room, place the text and the
doors, then `:record` walks your own solution and captures it as the level's
answer. The par comes from replaying that recording, so a level cannot ship
claiming a route nobody has walked. The forge is **admin-only** — sign in with
the player name `admin` to reach it. Be warned that the same name also unlocks
every level and shows you each puzzle's solution as you play, so use a separate
save for authoring rather than the one you are playing on.

**In a text editor.** The format is documented, so you never have to use the
forge:

```
python3 -m sharing export rune_halls mylevel.json   # start from a working level
python3 -m sharing validate mylevel.json            # check it
python3 -m sharing install  mylevel.json            # put it on your shelf
```

Either way, drop the file in `~/.Vimny/levels/` and it shows up in the overworld
under `community/`.

**The shelf.** Community levels live at
**[github.com/chkiss/vimny-levels](https://github.com/chkiss/vimny-levels)** —
type `:e remote` in the overworld to browse what's there and install any of them
without leaving the game. To add yours, open a pull request against that repo
with your level file; it is checked by the same validator you can run yourself
(`python3 -m sharing validate mylevel.json`), so if it passes locally it will
pass there.

Two things worth knowing before you install a level someone else wrote:

- **A level is data, never code.** Vimny reads the file and builds a room from
  it. Nothing in it is ever executed — that is what makes it safe to play,
  rather than anyone having vetted it.
- **Vimny goes online only when you ask it to, in one place.** Nothing is
  fetched at startup, in the background, or on a timer: there is no phone-home,
  no telemetry, and no update check. The single exception is the **remote
  shelf** — type `:e remote` in the overworld and Vimny fetches a public index
  of community levels over HTTPS so you can browse and install them. Nothing
  else in the game makes a network request, and a level you already have on
  your shelf never triggers one. Vimny does not moderate what a level file says.

A community level's par comes from replaying the author's own solution, so it is
labelled *author's par* — the cost of a route that definitely works, not a
promise that no shorter one exists. Nobody gets to type in their own par or
budget.

Full guide: [docs/AUTHORING.md](docs/AUTHORING.md).

## Upcoming features

- **The Registry** — a bonus wing on the register family: the delete ring (`"0`, `"1`–`"9`), the small-delete register (`"-`), the read-only registers (`":` `".` `"%` `"#`), the expression register (`"=`), the system clipboard (`"*` `"+`), the black hole (`"_`), the search register (`"/`), and a boss to close it out. The first two levels are in.
- **Folds** — `zf` / `za` and a level built around them.
- **Insert-mode editing** — `<C-w>`, `<C-u>` and friends: the keys that make insert mode more than typing.
- **Windows, tabs and buffers** — Vimny is one buffer per dungeon today; multi-buffer play is on the roadmap.

## Design principles

- **Vim fidelity above all else.** Commands behave exactly as they do in Vim.
- **Efficiency is enforced by par and budget.** The keystroke budget makes Vim's core value proposition central, and the par encourages the player to strive for perfect execution efficiency.
- **Everything is a buffer.** Dungeons are files; the overworld is a directory; `:w`, `:q`, `:e` are real mechanics.

See [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) if you want to work on the
engine — it is the canonical reference for the architecture, the laws the levels
are held to, and the conventions. `LEVELS_PLAN.md` is what's planned next, and
`SPEC.md` the design vision & UI.

## License

Vimny is free software, licensed under the **GNU General Public License v3.0** —
see [`LICENSE`](LICENSE) for the full text.
