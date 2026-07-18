# Act VII — Mastery Blueprints

> **Pre-implementation design doc — delete-on-implement.** Delete a level's
> section when that level ships, and the whole file once its act is built.
> Only the final boss remains unbuilt.

> ✅ The Spellwright's Forge SHIPPED as display 39 (section removed).
> ✅ The Hall of Echoes SHIPPED as display 40 → now 44 (the actual build
> diverged from the old blueprint: five ECHO ROWS on the exact-text chassis,
> each needing a two-part mend — daw the junk + x the fused ◆ — so `.` can
> never carry a whole row; canonical `j qa ^ w daw w x j q 4@a G $` par 14;
> budget GENEROUS hand-set 45 — forcing by PAR, not the old tight-budget
> scheme; see `build_dungeon_hall_of_echoes` + tests).
> ✅ The Gauntlet SHIPPED as display 45 (par 94, all-commands exam;
> plaque doors, goal column, karaoke macro, misted-water forcing).

---

## Level 45.1 — The Warden Eternal (FINAL BOSS) — v2 plan, 2026-07-18

> Supersedes the v1 three-phase design in full. v1 relied on three things that
> are now dead or contrary to project law: (a) the **mana pool** (retired
> 2026-06-15 — substitution shipped token-gated at the Spellwright's Forge);
> (b) **tight-budget forcing** (the S2 1.24×/1.30× multipliers — we now force
> by PAR: sub-optimal routes WIN at 1★, budgets stay generous); (c) the **wave
> timer** (CHALLENGE C6 — cut entirely; a respawn tick is a new engine system
> whose only job is punishing slow play, i.e. budget-thinking; static fire per
> phase does the forcing).

**Role in the curriculum.** The player arrives having passed the Gauntlet —
pure editing mastery is already examined. The boss is therefore the thing the
Gauntlet deliberately wasn't: **combat woven into editing** — the payoff of
every warden fight in the game. No new commands (`teaches: []`); the demanded
mastery is ranged `:s//g` (L39), macros (L44), and timed combat.

**Shape.** ONE composite arena (~24×60), three vertical phase zones separated
by plaque doors (Gauntlet `'sub'`/`'row'` door kinds), scripted by a plain
`_warden_eternal_tick` in main.py — no new boss-state architecture (old
CHALLENGE C7 resolved by precedent: every scripted level works this way).

### Phase 1 — The Ashen Tide (`:{range}s/F/·/g` forced by terrain-infinity)

- Rows 2–4 are full-width **fire**: lethal-landing CharRuns (void semantics —
  no motion may LAND there; line jumps pass over, Vim-faithful) with a misted
  water margin on the west so the player can never stand adjacent — `x`/`dd`/
  visual can never reach the fire. The only tool that acts on rows you are not
  standing on is **ranged substitute**: `:2,4s/F/·/g` clears all three rows in
  one command — the capstone of the Spellwright lessons.
- Forcing is by PAR: per-row `:s//g` with `+` stepping still solves (wins 1★);
  the bare-`:s` (no `g`) route clears one glyph per call and can never reach
  par. Terrain-infinity only bars the NON-`:s` routes (walk/cut = impossible).
- Phase door D1: `'sub'` plaque door — the cleared rows must read as the west
  plaque says (the `·` replacement text is part of the riddle).

### Phase 2 — The Echo Storm (macros forced by PAR)

- Five **echo-wardens** (Pathfinder trick: `goblin tag='echo'`, rendered
  `boss_echo_fg` 'W'), one per corridor row, each guarding an identical
  corrupted verse needing a multi-key mend + strike — Hall-of-Echoes law: a
  TWO-part mend (e.g. `daw` + `x` a fused glyph) so `.` can never carry it.
- Canonical: record on the first echo (`qa … q`, recording FREE per
  `Budget.frozen`), then `4@a`. Manual ×5 and five single `@a`s both WIN at
  1★ — no tight budget.
- Phase door D2: all five verses mended (`'row'`/`'dup'` doors) — the kills
  alone don't open it; the text must be right.

### Phase 3 — The Eternal Surge + the Warden Eternal

- Fire returns over the approach rows (ranged `:s` again, now typed while
  echoes patrol below), then the boss himself: `edit_immune`, 5 HP, and the
  Pathfinder's **mega-attack** (`engine/warden_mega.py`: idle→warn→strike
  telegraph, rotating safe pillars) so the kill is timed `x` strikes from
  marked pillars — marks/jumplist under pressure — not a stationary bag.
- `boss_seal` on the exit until `_check_boss_cleared`; exit sits EAST of a
  bolt row per the teleport-audit geometry (no `{n}G`/`G`/`L` skip — assert
  in tests that no jump lands on the exit while sealed and BFS can't reach it).

### Par / budget / answer

- **Par: hand-tallied along the driven canonical route** (mutating buffer +
  combat ⇒ no Dijkstra), pinned by the playthrough test at 2★. Rival tapes
  (manual echoes, per-row `:s`, no-`g`) asserted to win at 1★. Budget
  generous: `ceil(par*1.4)` or hand-set roomy.
- **Cheese-probe parametrized test from day one** (Gauntlet pattern):
  `{n}G`/`gg`/`H` ferries, early yanks, spine walks — each must fail or
  overspend.
- **Answer stays admin-karaoke-playable**: `:2,4s/F/·/g` contains no spaces,
  so the tape tokenises; verify with the admin-driven sync test (Gauntlet
  precedent — driven tests must run as `admin` to exercise the tracker).
- **Scroll drop: none of the smudge kind** (no next tier to tease). Either a
  pure-epilogue scroll ("The Warden's Rest", zero smudges) or no drop — the
  existing `warden_eternal` poem in `art/_gen_wizard_wisdom.py` carries the
  ending.

### Files

`_WE_*` constants + `build_dungeon_warden_eternal` (+ hand-tallied par) in
`generation/dungeon_gen.py`; `_warden_eternal_tick` in `main.py`;
`tests/test_warden_eternal.py` on the `test_gauntlet.py` template (driven
`_drive` harness, cheese probes, rivals, admin karaoke sync). Delete this
file when the boss ships.

### Open question (pre-implementation)

Whether to teach further `:{range}` ex commands (`:d`, `:m`, `:t`, `:y`,
`:>`, `:j`) in a new level BEFORE the boss — under assessment; if such a
level ships, Phase 1/3 may add a beat that uses it (e.g. `:m` a bridge line
into place).
