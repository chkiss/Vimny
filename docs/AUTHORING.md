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

A draft opens straight into EDIT mode, where the painter's keys (`:paint` for
terrain, INSERT to write text, `:rune`, `:entity`, `d`/`y`/`p`) work as they
always have, plus the level's own properties:

| command | what it does |
|---|---|
| `:paint <kind>` | lay terrain down under the cursor, or over a `'<,'>` selection (`:paint` alone opens the palette; `:paint?` says what is there) |
| `:spawn` / `:exit` | put the spawn or the exit where you are standing |
| `:rune <kind>` | place one rune under the cursor (`:rune` alone opens the list) |
| `:fill <pool> [lo-hi] [spacing]` | fill the last VISUAL selection from a word pool (`:fill` alone opens the list; `:fill?` reads back the directive under the cursor) |
| `:fill!` | drop the fill under the cursor, keeping its words as text you own |
| `:entity [kind] [field=value …]` | place or retune the entity under the cursor (`:entity` alone opens the palette; `:entity?` reads it back; `:entity!` removes it) |
| `:seal <text>` | arm a text-match door on the last VISUAL selection |
| `:bolt` | make the cell you are standing on — or every wall cell of a `'<,'>` selection — open while that seal reads true |
| `:name` `:author` `:teaches` `:requires` `:intro` `:alternate` `:vocab` | the metadata block |
| `:meta` | what the draft currently claims |
| `:canvas <rows>x<cols>` | grow (or trim) the ground the level is drawn on (`:canvas` alone says how big it is) |
| `:play` | **playtest — walk the level as a player, recording nothing** (`:play!` for no budget) |
| `:record` | **play the level; the keys you press become the tape** |
| `:check` | run the validator and report par, budget and warnings |
| `:publish` | validate, then put it on the shelf in `~/.Vimny/levels/` |
| `:w` / `:wq` | save the draft |
| `:e` / `:e!` | re-read the draft from disk, re-rolling its fills (`:e!` to discard unsaved work) |

Every metadata command reads as well as writes, the way `:set` does: `:author
Chas` sets it, `:author?` (or a bare `:author`) asks what it is now, and
`:author!` clears it. Clearing takes the explicit `!` because a mistyped query
should not throw away the thing it was asking about.

A `V` (linewise) selection fills the **whole row**, not the columns your cursor
happened to sit between.

`:record` is the reason the forge exists. It does not record in the editor —
an editor room has passable walls, no budget and no command gating, so a route
recorded there is one no player could follow. It builds the level fresh, exactly
as a player downloads it, gates you to the level's own `requires` + `teaches`,
and drops you in to solve it. Reaching the exit ends the take; the keys become
`solution`, and the validator immediately replays it to derive par. A key the
notation cannot write (an arrow key, Backspace) ends the take rather than
producing a tape that replays as something other than what you played.

`:play` is the same walk with the recorder off. Every take that is not the
definitive one still overwrites `solution`, so rehearsing with `:record` costs
you the tape you already had — `:play` is what you reach for while the level is
still a question. It builds it fresh, gates you the same way, and writes nothing
down at the end: losing is allowed, and is usually the thing you wanted to find
out. Once the level has a tape, `:play` runs under its real budget, so *is it
doable in the budget* is a question you can ask by answering it; `:play!` drops
the budget for a roam around a half-built room. `:e` inside either one restarts it — a rehearsal
re-rolls the fills with it, so it is also how you ask what somebody else's copy
of the room looks like; a take keeps the level's own seed, because a tape holds
the letters you typed and re-rolling mid-take would write down a route through
words no copy of the level has.

### Painting terrain

`:paint <kind>` lays down one named terrain — under the cursor, or over every
cell of a `'<,'>` selection, so a river is one command:

| kind | what it is |
|---|---|
| `floor` | open ground |
| `corridor` | walkable, drawn as passage rather than room |
| `wall` | stone — blocks feet, and bounds a line for `$`, `0`, reflow and the operators |
| `wood` | destructible wall — two hits of `x` |
| `water` | unwalkable, but line motions cross it |
| `mist` | fogged water: hazy, never lit, and light will not flood past it |

`:paint` on its own opens the palette; `:paint?` says what the cursor (or the
whole selection, as a tally) is standing on. Every forge command whose argument
comes from a list the game already knows does the same when typed bare —
`:paint`, `:rune`, `:fill`, `:entity` — and each one names the line it composed
on the way out, so the list teaches its way out of being needed. (The metadata
commands are the exception: a bare `:author` *asks*, because `:field` / `:field?`
/ `:field!` is a read/write/clear split, not a missing argument.) It replaced the old `s` cycle, which
could only reach the terrains someone had remembered to thread onto the ring —
misted water was drawn by the renderer and reachable by no key at all — and which
could not answer *what else is there?*

Paint touches the **cell**, not what stands on it. Writing text and then painting
`wall` over it is how you set a plaque into stone: uncuttable by `cc` or `D`, and
skipped by the floor scans that read the editable labels. `x` and `d` are for
removing things.

A **fill region is owned by its directive**, not by you: it regrows from the
level's seed on every build, so the editor refuses edits inside one. `:fill!`
is how you take the words for yourself.

Select the region and type `:` straight from VISUAL — `v`, walk the shape,
`:fill plain`. Like vim, `:` leaves visual mode, stamps the selection into the
`'<`/`'>` marks on the way out, and hands you a command line already reading
`:'<,'>`. `:fill` reads exactly those marks, so the selection has to be
*remembered*, not still open; `gv` brings it back to fill the same region twice
with different pools.

Most forge commands are addressed to a **place** (`:entity` at the cursor, `:w`
at the draft), not to a range, and typing one after that prefill is refused
rather than run — `Esc` the command line and type it plain. The marks outlive
the Esc.

A draft opens on a 20x80 room in the corner of a **100x100 canvas**. The rest is
solid stone: carve into it with `:paint floor` and the level can be as big as
the canvas. `:canvas 40x120` changes that ground — the new stone goes on at the
bottom and the right, so nothing already drawn moves and a tape recorded before
the resize still plays. It shrinks too, as far as the content: the moment a
smaller canvas would cut something it is refused rather than trimmed, because a
level quietly missing its exit is worse than one that would not resize. Nothing you did not touch ships — `:publish` trims the blank stone
margins back to one wall thick, which changes no motion and no par (stone is not
a line, and `$`/`0` stop at the walls that bound their own segment anyway).

`:teaches` and `:requires` hold a *set*, drawn from the tokens the game gates on,
so a bare `:teaches` opens that list as a multi-select — space toggles, `⏎`
accepts. `:teaches?` is still the plain question.

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
`X` wood wall (destructible), and `M` misted water — water under permanent fog,
which is a pair of facts about a cell but draws as one, so it rides the grid
rather than a second list of coordinates that could disagree with it. Each row
must expand to exactly `cols` cells; if it does not, the validator tells you
which row and by how much.

### `fill` — "cover this floor in words"

Rather than placing every character by hand, name a region and a pool:

| pool | what it draws from |
|---|---|
| `plain` | the shipped plain-word list |
| `mixed` | the shipped list including symbol glyphs |
| `proverbs` | whole proverbs, one saying at a time |
| `misquotes` | whole proverbs with one word wrong |
| `custom` | your own `vocabulary` block |

`proverbs` and `misquotes` are **line pools**: they lay a whole saying, in order,
one space between its words and two between sayings. A proverb taken apart into
a bag of words by length is not a proverb, and a misquote you cannot read is not
something a player can mend. `length` is ignored for these — a saying is as long
as it is — and the region has to be wide enough to hold the shortest one (13
columns for `proverbs`, 20 for `misquotes`), or the fill is refused rather than
growing nothing.

**Fills are re-rolled for every player**, from a fresh seed each time the level
is entered, exactly as every shipped level's words are. A fill is you saying "a
wall of words here", not "these words here"; the file's own `seed` is only what
the editor and the validator build from, so there is a fixed arrangement to
reason about. **`:e` re-rolls them** — it is your window onto somebody else's
copy, and the only place in the forge where the words move. Reopen a few times
before you publish: you are judging the region, not the draw.

What keeps that safe is a gate at publish time: your tape is replayed against
eight fresh arrangements and every one must reach the exit at the same par. A
route that depends on which words grew — hopping `w` onto an exit that happened
to sit where a word started — is refused with the seed that broke it. Move the
fill off the solution path, name the words instead of spelling them (below), or
`:fill!` it into text you own.

A fill never paints over stone, so carve first and fill second.

### `vocabulary` — your own words

```json
"vocabulary": ["chat", "chien", "oiseau"]
```

In the forge that is `:vocab chat chien oiseau`, and then `:fill custom` over a
selection. With no length range given, a custom fill uses the lengths your own
words have — so those three words are exactly what lands. Give a range
(`:fill custom 4-5`) and it narrows to the words that fit it.

A word-pool fill scatters **single words at random**; it is not a way to write a
specific sentence in a specific place. For that, type the text in INSERT mode like any
other author, or lay a fill down and `:fill!` to take its words and edit them.
Words are whitespace-separated, so a `vocabulary` entry can never contain a
space — one entry is one word standing in one run of cells.

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
`tag`, `swole`, `edit_immune`, `drops`, `group`, `opaque`. An exit entity is added at
`geometry.exit` automatically if you do not place one.

The three chests are `chest_key` (a key), `chest_scroll` (a scroll) and
`chest_random` (50% key, 30% scroll, 20% heart). A level that wants a specific
reward should name it — `chest_random` is a gamble, and its odds are rolled at
the moment of looting, so it is not something a solution tape can rely on.
`chest_random` was called `chest` before; files that still say so keep working.

**A door is a thing standing on a cell, not a kind of ground** — `:entity door`,
never `:paint door`. And what blocks *feet* and what blocks the *eye* are two
separate facts:

| | blocks the way | hides what is beyond |
|---|---|---|
| `door` | no — you walk onto it and `x` opens it | only with `opaque` |
| `locked_door` | yes | only with `opaque` |
| `:paint wood` | yes — two hits of `x` break it | no (stone is opaque anyway) |

Fog is derived from the stone, and an ordinary door is a grille you can see
through: that is what makes a caged specimen an exhibit rather than a rumour.
Set **`"opaque": true`** on a door and the eye stops there instead — everything
behind it starts fogged, and opening the door is what lifts it. Nothing is
scripted and nothing is stored; move the door and the darkness moves with it. A
closed door is closed from either side: if you stand ON an opaque plain door the
far side stays dark, and only stepping PAST it opens the pocket beyond. For a
door that both bars your feet and hides what is behind it, use an opaque
`locked_door` — an opaque plain door fogs, but a player still walks onto it.

**Colours pair on `tag`.** A `floor_key` tagged `gold` opens a `locked_door`
tagged `gold` and nothing else; an untagged door takes any key. Pick up a key
with `x` — it goes into the unnamed register — and open the door by pasting it
there: **`p` if the door is east of you, `P` if it is west**. Which means a
level with a locked door has to DECLARE `p` (or `P`) in `requires` or `teaches`,
or nobody can open it — `x` is always allowed, but pasting is a lesson like any
other. `:check` and `:play` both warn when a level places a lock its own command
set cannot work; you will not notice it in the forge, where nothing is gated, so
the warning greets you the moment you rehearse. A `chest_key` carries its tag onto the key it gives up, so
`{"kind": "chest_key", "tag": "gold"}` is a chest holding a gold key.

Only **`gold`, `red` and `blue`** are painted as colours. Pairing is plain
string equality, so `tag=vault_b` pairs a key to a door perfectly well — it
just draws in the default brass. Use a colour when the colour is the clue.

**`:entity` takes the `'<,'>` range**, and then it addresses every standable
cell of the selection instead of the one under the cursor — a rank of goblins,
a row of chests, a wall of coins, in one command. `v`, walk the shape, then
`:entity goblin tag=echo`. Wall, wood and water cells inside the region are
skipped rather than refused: the region was drawn around what you could see,
and a creature sealed in the stonework can never be reached or fought.

`:'<,'>entity!` sweeps the selection clear again (`gv` first, to get the region
back), and `:'<,'>entity?` answers with a tally rather than one cell. The whole
ranged placement is one `u`.

**`:entity` with no argument opens the palette**, and the palette can set the
same fields the command can: pick a kind with `j`/`k` and Enter, then walk that
kind's notable fields, Enter to choose a value, and Enter on the last row to
place it. Fields with a known set of values (`tag`, `ai`, `drops`, `scroll_id`)
offer that set, with a last row for typing anything else.
It reports the command it just ran (`Placed by  :entity floor_key tag=red`)
— the menu answers "what can I place?", the command is still the mechanism.

**To place the same thing again, `@:`** — and `@@` for each one after that.
`.` will not do it: `.` repeats the last *change*, and an Ex command is not one,
in Vimny exactly as in Vim. `@:` re-runs the last `:` command wherever the
cursor now is, so a row of identical goblins is `:entity goblin tag=echo`
once, then `l@:l@@l@@`.

**`edit_immune` makes an entity survive editing.** It is a field on the entity
(`warden` and `locked_door` offer it), and it does two things: a `d` that would
sweep the entity's cell passes over it (`engine/operator.py`), and a `dd`/`J`
that would collapse its whole row refuses to (`engine/reflow.py`). It is the
"boss parries the blade" ward: a Warden so marked twists out of a visual cut
("only a precise `x` can land on him"), which is what stops a boss fight from
being won with `dG`. It is also how a level anchors a row it cannot afford to
lose — nearly every shipped exit entity is `edit_immune`, and that is what
stops a final `D` or `dG` from deleting the way out from under the player.

It guards the **editing verbs only**. `x` combat damage still lands, by design:
`edit_immune` says "this is a creature, not text", not "this is invincible".

**`drops` is what a creature leaves behind when it dies**, written `kind` or
`kind:tag`. It is a field on the creature, not a rule about goblins, so a
zombie, a wanderer or a Warden all drop the same way. Only loot may be
dropped — `floor_key`, `chest_random`, `chest_key`, `heart_container`, `gold`,
`dynamite` — because `drops` is the one field in the format that creates
something at runtime, and a level should not be able to hatch a boss the
validator never counted.

**`group` makes the drop wait for the whole group.** Give several creatures the
same `group` and the drop lands only when the last of them falls, in the
lowest-numbered member's cell:

```json
{"kind": "goblin", "at": [4, 20], "hp": 2, "ai": "chase",
 "group": "patrol", "drops": "floor_key:gold"}
```

In the forge that is `:entity goblin group=patrol drops=floor_key:gold`. The
drop is recomputed every turn from who is alive right now, never remembered —
so `u` revives the patrol and takes the key back, and it does not matter whether
you killed them with `x` or cut them down with `dw`.

### `seals` — a door held shut until the text reads right

```json
"seals": [
  {"region": [2, 2, 2, 14], "match": "this password", "opens": [9, 40]}
]
```

The cells in `opens` stand as floor exactly while the buffer inside `region`
reads `match`, and turn back to stone the moment it does not. `opens` takes a
single `[row, col]` or a list of them, so a three-cell gate is one seal.

`mode` is `"exact"` by default: the region reads that text and nothing else.
`"contains"` opts into the looser rule, where the text merely has to appear
somewhere inside the region.

**`match` may be a list**, and then every one of them has to read true at once —
a chamber that holds its bolt only while all three of its sayings still stand is
one seal, not three.

#### Reading the whole floor instead of a rectangle

```json
{"scope": "anyrow", "match": "a watched pot never boils", "opens": [13, 22]}
```

`"scope": "anyrow"` drops the region and reads **every floor row**: the seal is
true if any row answers. Reach for it the moment your level has a verb that
moves lines around — `dd`, `J`, `o`, `p` all slide rows, and a seal that named a
rectangle would be undone by the first line the player removed above it. With
`mode: "exact"` the row must read *exactly* that text (which is what makes a
half-cleared row read false); with `"contains"` the words merely have to appear
on some row. An `anyrow` seal takes no `region`.

#### A seal that waits for other seals

```json
{"requires": [0, 1, 2], "opens": [13, 32], "anchor": "exit_row"}
```

`requires` names **earlier** seals by index, all of which must read true. A seal
with `requires` and no `match` reads no text of its own — it is pure conjunction,
and that is how you write a **final seal**: a row of bolts, then an exit that is
stone until every one of them has opened. Do that whenever your level teaches
`A`, `o` or `O`, because a player who can build floor can walk around any gate
that is only geometry. (Indices must point backwards, so the conjunction can
never chase its own tail.)

`"anchor": "exit_row"` puts the door on whatever row the exit is on *right now*
rather than the row you wrote down. The column is still yours. Levels where rows
can be cut or joined need it, or the gate is left behind on the row it was built
on while the exit slides away.

Seventeen shipped levels are built out of exactly these four pieces — see
`world.gate_row_seals`, which is the whole chassis in nine lines.

Two things a seal deliberately will not do. It **only reads walkable stone** —
text written in wall cells never counts, which is what lets you set the password
on a plaque beside the door without the door opening itself. And a cell in
`opens` may not lie inside its own `region`: a door that is part of the text
that opens it becomes walkable, gets written on, and re-shuts on whatever was
written. The validator refuses that one by name.

Because it is a reading and not an event, **undo re-seals**. There is no state
to get out of step, and a seal cell is always written to the file as stone
however it happened to be standing when you saved.

In the forge: select the strip in VISUAL and `:seal this password` — typing `:`
straight from the selection is the point, the region is what the seal reads.
Then go to the door and `:bolt`.

**`:bolt` takes the `'<,'>` range**, which is how a whole wall is wired to one
trigger rather than bolted a cell at a time: select the wall, `:bolt`, and every
masonry cell in the selection becomes the same door. Floor inside the selection
is left alone — a seal writes its `opens` cells out as *stone*, so bolting floor
would wall off squares the author was standing on. (Where `:entity` takes the
standable half of a selection, `:bolt` takes the masonry: each command takes the
half it can mean anything about.) A second `:bolt` widens the same seal rather
than making a second one, and cells that lie inside the seal's own region are
**refused** rather than quietly dropped — silently meaning fewer cells is how a
wall ends up with a hole in it nobody put there.

`:seal *word` arms the looser `contains` reading — the glob sense of `*` — and
`:seal!` removes the seal bolting the cell you are on.

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

#### Naming a word the fill grew

A route that **types** a word off the floor cannot spell it out — the word is a
different one for every player. Point at it instead:

```json
"solution": "wwce<fill0.4><Esc>"
```

`<fill0.4>` is *the word `fill[0]` grew in slot 4*. Both numbers count from
zero, like `fill[0]` does everywhere else: fills in the order you wrote them,
words in the order they were laid — left to right, then down. Vimny substitutes
the real word when it builds the room, so what the player is scored against is
ordinary letters, and what your file says is what you meant.

**Don't count the words — stand on one and ask.** In the forge, `:fill?` over a
word tells you the reference for it:

```
'addr' is <fill0.7> — write that in the solution and every player types their own.
```

That is also where you find out you cannot: over a fill that rolls its lengths,
`:fill?` says so, and names the cure — `:fill length=4` retunes the fill under
the cursor in place, keeping its region *and its position in the list*, which
is what any `<fill0.…>` you have already written is pointing at. (Re-selecting
the region and `:fill`ing it again would **add** a second directive on top of
the first.) A bare `:fill` asks for the length as its second step, so you meet
the choice while you are making the wall rather than at `:check`.

Two rules come with it, and both are about par being **one number**:

* the fill you read from must grow words of a **single length**
  (`"length": 4`, not `[3, 6]`) — `ce` plus a word costs as many keys as the
  word is long, so a fill that rolls its lengths is a level with a different
  par for every player; and
* you cannot read a word out of a **saying pool**, where which proverb turned up
  decides the length too.

A fill lays no word on stone and stops short of the right margin, so it can grow
fewer words than its region looks like it holds. A slot that was never laid is
refused by name rather than left in the tape.

**What about `3e` versus `4e`?** A counted motion depends on where the words
are, not on what they say — and a single-length fill lays them in exactly the
same places for every player. Word length is what decides where the next word
starts, so fixing the length fixes every position, and the number of words too;
all that is re-rolled is the letters. Look at your own build, count once, and
write `3e`: it is right for everybody. That is the same law doing both jobs,
and it is why counts need no notation of their own.

The flip side is a real limit worth knowing. If you *want* the roll to change
the route — "count the words yourself, however many there are today" — Vimny
cannot score that level. Par is one number, and a route that is four keys for
one player and five for the next does not have one.

### `then` — a level of more than one chamber

Most levels are one room. A level that is a **descent** — a gallery, then the
arena you are chased into — writes the chambers after the first in `then`:

```json
  "geometry": { "rows": 12, "cols": 60, "cells": ["..."],
                "spawn": [1, 1], "exit": [10, 58] },
  "seals": [ {"region": [2, 2, 2, 40], "match": "the gate stands open",
              "opens": [10, 58]} ],
  "then": [
    { "geometry": { "rows": 20, "cols": 80, "cells": ["..."],
                    "spawn": [1, 1], "exit": [18, 78] },
      "entities": [ {"at": [9, 40], "kind": "warden"} ] }
  ]
```

Chambers are walked **in order, one way**. Stand on a chamber's exit and the
next one begins where its own `spawn` says; only the LAST chamber's exit wins
the level. To make a door conditional, put a seal on the exit cell — you cannot
stand on stone, so nothing else is needed.

("Chamber" and not "room": a `room` is the engine's single grid of cells, and
the levels called *Halls* are levels. A chamber is one segment of a descent.)

Each chamber carries its own `geometry`, `fill`, `seals`, `char_runs` and
`entities`, and nothing else: the seed, the tape, what the level teaches and
your `vocabulary` belong to the LEVEL. `then[0]` is the chamber after the
first, not the first.

Three things follow from there being one level and several chambers:

* **One tape.** `solution` is the whole descent, in order, with no notation for
  passing a door — walking onto the exit is what does it. Par is the whole
  route.
* **Fills are numbered across the level.** `<fill0.3>` is the level's first
  fill wherever it stands; if the first chamber has two fills, the first fill
  in `then[0]` is `<fill2.…>`. `:fill?` counts the same way, so standing on a
  word always gives you a reference you can paste into the tape.
* **The undo stack does not follow you.** Each chamber keeps its own past; the
  chamber behind you is past mending.

The forge cannot yet build a second chamber — it edits the one you are standing
in, which is always the first, and passes the rest through untouched. A level
with `then` is written by hand for now, and `:check` judges it in full.

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
