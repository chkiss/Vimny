# Writing a Vimny level

A community level is a **JSON file**, not code. Vimny parses it into a room and
runs none of it — that is the security boundary, and it is why you can play a
level a stranger wrote. Drop a file in `~/.Vimny/levels/` and it appears in the
overworld under `community/`.

```
python3 -m sharing validate mylevel.json     # check it
python3 -m sharing install  mylevel.json     # put it on your shelf
python3 -m sharing list                      # what's installed
```

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

**You do not set par, and you do not set the budget.** Par is the replayed cost
of your tape, and the budget is always `ceil(par × 1.4)`. Being able to declare
either would let a level be tuned to hide a sloppy route.

Notation: a plain space is a *display separator* and is stripped, so write a
space you actually type as `␣` and a typed Enter as `⏎`. `<Esc>` is omitted.

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
| `geometry` | the room actually builds |
| `determinism` | two builds of your file are identical |
| `solvable` | the tape replays and reaches the exit — **hard gate** |
| `par` | derived from the replay; budget is `ceil(par × 1.4)` |
| `golf` | *warning*: plain movement beats your tape |

Every rejection names its rule. Validation runs on **load**, not only on
submission, so hand-editing a file does not get you past it.

## Beating a shipped level's par

Every shipped par claims a solver found the cheapest route. If you find a
shorter one, that claim is wrong, and your tape is the proof:

```
python3 -m sharing golf spellwrights_forge --tape ':%s/moo/quack/g⏎ 8G ...'
```

A confirmed beat is a **bug report against that level's solver**, not a high
score — par is a property of the level and changes because the old value was
wrong, not because you played well. This is how the pipeline's first run found
The Spellwright's Forge claiming par 45 for a route that costs 44.

## Substitution — standing in for a shipped level

`"substitutes": "rune_halls"` makes a level a candidate stand-in. It must teach
*exactly* that level's lesson: teach more and the player runs ahead of the
curriculum, teach less and a later level depends on a command they never met.

Substitution is **off by default** and stays that way. A level can be perfectly
valid and still be a bad *teacher*, and a new player who hits one has no way to
know the curriculum was swapped — they will conclude Vimny is bad, not that the
level is. The bonus wing carries none of that risk.

## What Vimny will not do

- **No code.** A level is data. Nothing in the file is ever executed.
- **No network.** The game reads `~/.Vimny/levels/`. It does not fetch, phone
  home, or check for updates. You bring files by whatever means you like.
- **No review.** A level file can contain any text its author put there, and the
  game does not moderate it.
