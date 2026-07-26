# Writing a Vimny level

A community level is a **JSON file**, not code. Vimny reads it, builds a room
from it, and runs none of it — which is why it is safe to play a level a stranger
wrote. Drop a file in `~/.Vimny/levels/` and it turns up in the overworld under
`community/`.

```
python3 -m sharing validate mylevel.json     # check it
python3 -m sharing install  mylevel.json     # put it on your shelf
python3 -m sharing list                      # what's installed
```

## The forge — writing one without leaving the game

Everything below can be done in a text editor, and the format is documented so
that it can be. But there is a second way in: the **forge**, an admin-only bench
in the overworld under `forge/`, where a level is built by playing it.

| key | in the overworld |
|---|---|
| `%` | new draft (netrw's new-file key) — names it, and it exists on disk at once |
| `⏎` | open a draft in the editor |
| `R` / `D` | rename / delete one |

A draft opens straight into EDIT mode, where the painter's keys (`s` to cycle
wall/wood/water, INSERT to write text, `:rune`, `:entity`, `d`/`y`/`p`) work as
they always have, plus the level's own properties:

| command | what it does |
|---|---|
| `:spawn` / `:exit` | put the spawn or the exit where you are standing |
| `:fill <pool> [lo-hi] [spacing]` | fill the last VISUAL selection from a word pool |
| `:fill!` | drop the fill under the cursor, keeping its words as text you own |
| `:name` `:author` `:teaches` `:requires` `:intro` `:alternate` `:vocab` | the metadata block |
| `:meta` | what the draft currently claims |
| `:record` | **play the level; the keys you press become the tape** |
| `:check` | run the validator and report par, budget and warnings |
| `:publish` | validate, then put it on the shelf in `~/.Vimny/levels/` |
| `:w` / `:wq` | save the draft |

`:record` is the reason the forge exists. It does not record in the editor —
an editor room has passable walls, no budget and no command gating, so a route
recorded there is one no player could follow. It builds the level fresh, exactly
as a player downloads it, gates you to the level's own `requires` + `teaches`,
and drops you in to solve it. Reaching the exit ends the take; the keys become
`solution`, and the validator immediately replays it to derive par. A key the
notation cannot write (an arrow key, Backspace) ends the take rather than
producing a tape that replays as something other than what you played.

A **fill region is owned by its directive**, not by you: it regrows from the
level's seed on every build, so the editor refuses edits inside one. `:fill!`
is how you take the words for yourself.

Drafts live in `~/.Vimny/drafts/`, and a draft file *is* a level file — the same
schema, so publishing is a copy and there is no export step that can lose
anything.

## Start from a level that already works

The fastest way to see the format is to export one of the shipped levels:

```
python3 -m sharing export rune_halls mylevel.json
```

That writes a real, valid, playable level file. Change it and re-validate.

## The file

```json
{
  "schema": 1,
  "name": "The Salt Stair",
  "author": "someone",
  "seed": 1234,
  "requires": ["h", "j", "k", "l", "w", "b"],
  "teaches":  ["e"],
  "geometry": {
    "rows": 20, "cols": 80,
    "cells": ["80W", "W78FW", "..."],
    "spawn": [1, 1],
    "exit":  [18, 78]
  },
  "fill": [
    {"region": [2, 2, 16, 70], "pool": "plain", "length": [4, 6], "spacing": 1}
  ],
  "solution": "wwwdwbbP0G"
}
```

### `cells` — the map

One string per row, in run-length form: `3W60F16W` is three walls, sixty floor,
sixteen walls. Codes are `W` wall, `F` floor, `C` corridor, `A` water,
`X` wood wall (destructible). Each row must expand to exactly `cols` cells; if
it does not, the validator tells you which row and by how much.

### `fill` — "cover this floor in words"

Rather than placing every character by hand, name a region and a pool:

| pool | what it draws from |
|---|---|
| `plain` | the shipped plain-word list |
| `mixed` | the shipped list including symbol glyphs |
| `proverbs` | words from the proverb collection |
| `misquotes` | words from the misquoted-proverb collection |
| `custom` | your own `vocabulary` block |

Fills resolve from the level's `seed`, so the level is **identical** for you and
for every player. That is not tidiness — your solution tape was recorded against
one arrangement of words, and a fill that landed differently for someone else
would leave your tape pointing at text that is no longer there. A fill never
paints over stone, so carve first and fill second.

### `vocabulary` — your own words

```json
"vocabulary": ["chat", "chien", "oiseau"]
```

Inline only — a level never fetches anything. Every character must occupy one
cell: no control characters, no combining marks, and no double-width characters.
Vimny's entire model is one glyph per cell, so a wide character silently shifts
every column after it and the level you tested is not the level that renders.

### `entities`

```json
"entities": [
  {"kind": "goblin", "at": [4, 20], "hp": 2, "ai": "chase", "ai_speed": 1},
  {"kind": "locked_door", "at": [9, 40], "tag": "gold"}
]
```

Everything that makes a creature what it is travels with it — `hp`, `ai`,
`tag`, `swole`, `edit_immune`. An exit entity is added at `geometry.exit`
automatically if you do not place one.

### `requires` and `teaches`

`requires` is what you assume the player already knows; `teaches` is what your
level introduces. Together they are the *only* commands your level may use — a
key outside them is refused by the same gate the curriculum uses, so a tape that
reaches for one will fail validation rather than surprise a player who cannot
press it. Never list a token in both.

### `solution` — the tape, and where par comes from

The literal keystrokes that solve your level, in order. It does two jobs:

1. it **proves the level is solvable** — a tape that does not reach the exit is
   rejected; and
2. it **sets par** — Vimny replays it and counts what the engine charges.

**You don't set par, and you don't set the budget** — there is nowhere in the
file to put them. Par is whatever your tape actually costs when Vimny plays it
back, and the budget follows as `ceil(par × 1.4)`. That way the numbers always
describe the level as it really is.

Notation: a plain space in the tape is just spacing for readability, so write a
space you actually type as `<Space>`, a typed Enter as `<CR>`, and Esc as `<Esc>`. Esc costs
nothing, but write it down anyway — without it the replay keeps typing your next
keys into the buffer.

> **Author's par, honestly.** Replaying your tape measures **your route**. It is
> an upper bound, not a proof of the optimum — which is why community levels
> score against *author's par*, named as such. If plain movement alone beats
> your tape, the validator warns you: that usually means the level does not
> actually force the lesson it is teaching.

### `no_horse`

`true` bars the companion, and with it the saddle registers.

## What the validator checks

| rule | what it means |
|---|---|
| `schema` | a version this game understands, and no unknown keys |
| `bounds` | sizes and coordinates in range; spawn on floor |
| `content` | vocabulary is printable, single-width, and bounded |
| `scope` | `requires` and `teaches` do not overlap |
| `alternate` | if you named a level to stand in for, you fit its curriculum slot |
| `geometry` | the room actually builds |
| `determinism` | two builds of your file are identical |
| `solvable` | the tape replays and reaches the exit — **hard gate** |
| `par` | derived from the replay; budget is `ceil(par × 1.4)` |
| `golf` | *warning*: plain movement beats your tape |

Every rejection tells you which rule it broke and where. The same checks run
whenever a level is loaded, not just when it is submitted, so a level that plays
on your machine plays the same way on someone else's.

## Beating a shipped level's par

Every shipped par claims a solver found the cheapest route. If you find a
shorter one, that claim is wrong, and your tape is the proof:

```
python3 -m sharing golf spellwrights_forge --tape ':%s/moo/quack/g<CR> 8G ...'
```

A confirmed beat is a **bug report against that level's solver**, not a high
score — par is a property of the level and changes because the old value was
wrong, not because you played well. This is how the pipeline's first run found
The Spellwright's Forge claiming par 45 for a route that costs 44.

## Think you can do a shipped level better?

Send it. If you have written a level you think teaches its lesson better than the
one currently in the game, say which one it stands in for:

```json
"alternate": "rune_halls",
"teaches": ["w", "b", "e"]
```

The one hard rule is that **it has to sit in the same place in the curriculum**.
Vimny teaches commands in order, and every level after yours assumes the player
arrived knowing everything taught so far — no more, no less. So your level has to
teach the *same commands* as the one it replaces:

- The Rune Halls teaches `w`, `b`, `e`. A replacement teaches exactly `w`, `b`,
  `e`. ✅
- Yours also throws in `f{char}` because it made a nicer puzzle. ❌ — the player
  now arrives at The Finding Hall already knowing its lesson, and that level has
  nothing left to teach them.
- Yours drops `e` because your layout did not need it. ❌ — three levels later
  something asks for `e` and the player has never seen it.

The same goes for your `requires`: your level may lean on anything taught *before*
the one it stands in for, and nothing that comes after. A replacement for The Rune
Halls cannot need `f{char}` — the player has not met it yet.

What you *may* change freely: the layout, the words, the fiction, the intro, the
route, the difficulty. Those are the things worth improving.

Validation checks the fit for you and names the commands you are over or under
by. Whether your level is *better* is the part no tool can settle, so expect to be
asked for playtesters before anything gets swapped.

## Levels that are just fun

None of the above applies if you are not trying to replace anything. Leave
`alternate` out and your level lives in the bonus wing, where it can teach
whatever it likes, in any order, to a player who already knows what they know.
Those submissions are welcome too — they just have to be playable.

## What Vimny will not do

- **No code.** A level is data. Nothing in the file is ever executed.
- **No network.** The game reads `~/.Vimny/levels/`. It does not fetch, phone
  home, or check for updates. You bring files by whatever means you like.
- **No review.** A level file can contain any text its author put there, and the
  game does not moderate it.
