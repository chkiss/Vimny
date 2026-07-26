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
`<C-w>`, `<C-u>`, `<C-o>`, `<C-r>{reg}` — the keys that make insert mode more
than typing. **All four are already implemented** (`main.py`, `engine/insert.py`)
and reachable as the `ins_edit` / `ins_paste` relic scrolls. What is missing is a
level, and the obstacle is the cost model, not the geometry:

- `<C-w>`, `<C-u>` and Backspace all spend **nothing**. A route that fixes a
  mistyped word with `<C-w>` and one that backspaces it letter by letter cost the
  same, so no par gap exists and no level can force the lesson.
- `<C-r>{reg}` spends **1 per pasted character** — identical to typing the text.
  It can tie a typed route, never beat it.

Repricing them by keystroke (Backspace and `<C-w>` at 1, `<C-r>{reg}` flat) would
make all of this forceable, and was **considered and rejected**: a flat-cost
register paste is cheaper than typing for any word of three characters or more,
which hands every text-entry level in the game a shortcut. The cheese surface is
worse than the missing lesson. These keys stay free flourishes.

Anyone revisiting this needs a *new* forcing mechanism, not a new price — some
way for the world, not the budget, to reward the correcting keys.

### Community levels (a system feature, not a level) — BUILT 2026-07-25
Blueprint: `blueprints/level_sharing.md`; author guide: `docs/AUTHORING.md`;
code: the `sharing/` package. The load-bearing decisions held: a level is
**declarative data, never code**; par comes from replaying an author-supplied
karaoke tape, which doubles as the solvability proof; the budget is computed,
never author-set. Levels live in `~/.Vimny/levels/` and appear in the overworld
under `community/`. There is no network code in the game and there must not be.

The same replayer audits the shipped curriculum (`python3 -m sharing audit`) and
found a real par bug on its first run — The Spellwright's Forge, par 45 for a
44-keystroke route. Still open: alternate swaps (§6, deliberately unbuilt), and a
tape notation for `<Esc>` so insert/change routes can be validated at all.

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
