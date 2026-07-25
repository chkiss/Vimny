# Vimny — Level Plan (what is not yet built)

The shipped curriculum lives in `content/levels.py` (canonical) and is listed in
the README. **This document is forward-looking only**: it holds the design rubric
every new level must satisfy, and the levels still to be built. When a level
ships, its entry here is deleted — notes worth keeping move into the level's
builder in `generation/dungeon_gen.py`, next to the code they explain.

---

## Design principles (the rubric)

1. **Scope** — a level teaches **1–3 new mechanics**, no more. Trivial
   direction/flavour variants of one idea count as one (e.g. `f`/`F` = one
   "find" idea).
2. **Rational linkage** — mechanics taught together form **one coherent family**
   (`gg`+`G` ✓; `gg`+`}` ✗).
3. **Forceability** — the level can be built so the puzzle **forces** the new
   command out of existing primitives, with no (or minimal) new game mechanics.
4. **Par is the optimum** — par is the cheapest route that *exists*, whatever it
   turns out to be, and the budget is always `ceil(par * 1.4)`. The lesson is
   forced by par, never by a tight budget. (Law: `docs/ARCHITECTURE.md`.)
5. **Boss placement** — bosses sit at **meaningful act boundaries**, are
   well-spaced, and are numbered `x.1`.

Forcing primitives available: walls and corridors, doors, character runs
(word/WORD targets), void runes, water and fogged water, chests and keys,
fog-of-war, the keystroke budget, enemies (goblins chase; wardens summon), and
visual mode.

---

## To build

### The Registry — the bonus register wing
Blueprint: `blueprints/registry_wing.md`. Two of its levels have shipped (The
Register I, The Register II); the rest are designed and unbuilt:

| Level | Teaches |
|---|---|
| The Delete Ring | `"0`, `"1`–`"9` |
| The Small Cut | `"-` |
| The Named Vaults | `"a`–`"z`, `"A` append |
| The Clerk's Ledger | `":` `".` `"%` `"#` (read-only) |
| The Reckoner | `"=` |
| The Saddlebag | `"*` `"+` |
| The Black Hole | `"_` |
| The Seeker's Echo | `"/` |
| The Registrar (boss) | — |

### Folds
Blueprint: `blueprints/bonus_wing.md` — The Cartographer's Table, `zf`.
`za` already exists (the Binder's Reliquary); the fold *creation* level does not.

### Insert-mode editing
`<C-w>`, `<C-u>`, `<C-r>{reg}` — the keys that make insert mode more than
typing. No blueprint yet; the hard part is forcing them, since a puzzle can
rarely tell how a word got deleted.

### Windows, tabs and buffers
Vimny is one buffer per dungeon today. Multi-buffer play needs engine work
before it can be a level, and is the largest open item.

---

## Reordering the curriculum

Identity is the immutable **slug**; the leftmost number in the README is the
cosmetic `display` field. To renumber, edit `display` / reorder `LEVELS` in
`content/levels.py` — never touch a slug — then rerun
`python3 content/_gen_curriculum_table.py` and the test suite. See
`docs/ARCHITECTURE.md` for what else keys by slug.
