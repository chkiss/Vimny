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

---

## The Ex-Range mini-act — three levels BEFORE the boss (decided 2026-07-18)

Slots between the Spellwright's Forge (39) and the Stair Rail (40); displays
are cosmetic, renumber 40–45.1 and rerun `content/_gen_curriculum_table.py`.
Closes the teaching gaps for `:v` and `&`/`:&&`/`g&` (implemented since
2026-06-03, never exercised by a lesson) and gives the boss's ranged-`:s`
finale five levels of reinforcement.

**Budget/cheese fact underpinning all three:** command-line input charges
`len(cmd) + 1` (every typed char + Enter, main.py), so ex forms carry ~4+
keys of overhead and only beat normal-mode ops when ONE command treats MANY
rows. Forcing is by PAR via that multi-row win (plus terrain where the rows
are unreachable); single-row ex routes lose on cost naturally.

### Level A — SHIPPED 2026-07-18 as The Culling Ledger (display 40)
- As built: teaches `ex_range` via `:{n}d`, `:{a},{b}d`, `:{range}v//d` (the
  star turn — keep only the lines bearing the sacred word). Ledger text on
  MISTED FLOOR (fog ∩ mist: the renderer's carved-through-mist branch shows
  it in full colour; fog bars feet, search-landings, cuts); no cell on a
  ledger row is passable, so jump ferries simply fail. Par 22 (:2d +
  :5,9d + :6,13v//d + $), budget hand-set 60; :g//d, :{n}d singles, and the
  :s-blanking longhand all win at 1★. Engine laws established: ex addresses
  follow the NUMBER GUTTER (line 1 = first_standable_row, as {n}G lands);
  THE AVATAR HAS FEET — :d/:m/:t/:g//d/:s never park the player on
  unwalkable ground (a ranged edit is not a ferry); mist_cells ride row
  inserts/collapses like fog. See build_dungeon_culling_ledger +
  tests/test_culling_ledger.py (+ ex probes in test_gauntlet.py).

### Level B — SHIPPED 2026-07-18 as The Shelving Room (display 41)
- As built: the ledger's misted-chasm chassis; the true stanza carved as a
  WEST-WALL plaque column row-for-row beside the shelf. Canonical
  `:2m4 :5t7 :3< :6> $`, par 15, budget hand-set 40. :m/:t are STRUCTURAL
  ROW SURGERY (`_snapshot_rows`/`_lay_rows_below` — cells, glyphs, fog AND
  mist ride along; a reflow capture reads a fogged row as empty), :>/:< are
  glyph-wise (`_indent_rows`; wall-carved plaques never move). main's
  `_shelving_tick` re-mists any bare shelf floor (stateless chasm law) and
  re-rights the plaque column after row inserts drag it.

### Level C — SHIPPED 2026-07-18 as The Refrain Vault (display 42)
- As built: a WALKABLE scriptorium + a two-line colophon chasm. One full
  `:s/{b}/{c}/g` at the B2 spawn desk, ranged `:5&&` (the park ferries the
  scribe to the chain top — a plain `&` RESETS the remembered flags,
  Vim-faithful, so the ranged repeat must fire while /g is fresh), then
  `j& 2j& j&` down the singles; `:1,2j` mends the colophon (textual
  `_join_rows` — fog-agnostic, avatar stays put), `:1y` + `p` lay it on the
  floor. THREE protected verdant lines carrying the blight bar :% / :g / g&
  outright and their SCATTERING bars any contiguous ranged :s (best mix 39
  vs par 37). A :t/:m'd chasm slab arrives still misted — off the floor, it
  never satisfies the colophon door; only the yank serves. Par 37, budget
  hand-set 60.

**Engine work (shipped):** `run_ex_range` (strict parser) + fog-aware forms:
`_yank_rows_clip` (glyph-wise :y/:d clips), `_snapshot_rows`/`_lay_rows_below`
(:m/:t), `_indent_rows` (:>/:<), `_join_rows` (:j). `&`/`:v` needed nothing.
Deferred: `:{range}normal` (old CHALLENGE C8 territory), `:sort`.

**Gauntlet obligation:** these tokens enter the Gauntlet's `known_commands`,
so add ex-route cheese probes to `test_gauntlet.py` when they ship — `:{n}d`,
`:g//d`, `:{n}y p`, and especially `:t`/`:m` ferries of plaque-matching rows
(remote duplication is the only genuinely novel vector; assert none beats
the taped route on any door). Verdict from the 2026-07-18 audit: no current
leak — ex overhead loses on single-row beats, `:y` is linewise where the
Gauntlet forces charwise yanks, and doors are presence-matches so mass
deletion opens nothing.

**Boss tie-in:** once B ships, Phase 1/3 may add a beat that uses it (e.g.
`:m` a bridge line into place).
