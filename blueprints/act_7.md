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

## Level 48.1 — The Warden Eternal (FINAL BOSS) — v3 plan, 2026-07-21

> **v3 supersedes the v2 three-phase / par-forced design** (kept below as
> historical detail). Two user decisions (2026-07-21) reshaped it:
> (1) **NO par-forcing** — this is the victory lap, not a teaching gate;
> `par = None`, budget hand-set generous, WIN = survival (Pathfinder /
> Grandmaster precedent). Every chamber is a *showcase*, not a star-gate.
> (2) **Six-warden callback + the reveal**: the wizard who blessed the player
> before every level **was the Warden the whole time** — the whole curriculum
> was his trial by fire. The boss is the mentor dropping his disguise; the
> reward is his **hat**. Renumbered 45.1 → **48.1** (ex-range + g-levels
> shifted the chain).

**Role in the curriculum.** The Gauntlet already examined pure editing. The
Eternal is the emotional capstone: a descent back through **all six wardens**
the player has already beaten (Keep · Surveyor · Pathfinder · Manifold ·
Scrivener · Grandmaster), each antechamber reprising that warden's signature
mechanic as a victory-lap trial, ending in **The Unmasking** — the wizard
steps from the dark and is the Warden Eternal. No new commands (`teaches: []`).

### Structure — six antechambers + the Unmasking

One composite arena, a vertical descent, scripted by a plain
`_warden_eternal_tick` in `main.py` (grandmasters/gauntlet tick precedent — no
new boss-state architecture). Each chamber is gated by a plaque/seal door and
reprises exactly one prior warden's scroll-skill (`_SCROLL_DROPS` ids in
parens). None is par-forced — the door opens when the trial is *met*, generous
budget throughout:

1. **The Keep's Gate** (`wardens_keep` → combat/`x`) — a short goblin-pack
   duel; where the whole journey's fighting began. Seal opens on last kill.
2. **The Surveyor's Span** (`warden_surveyor` → `visual`) — a visual-mode
   select-and-strike beat (`v{motion}` then operate); his gift was The
   Warden's Sight.
3. **The Pathfinder's Verse** (`warden_pathfinder` → `d_op`, the mega-attack,
   `/W`, the wardenverse) — the telegraphed `warden_mega.py` attack on rotating
   safe pillars + a `/W` "find the true warden among echoes" beat.
4. **The Manifold's Echo** (`warden_manifold` → `y_op`, `.`) — a yank/paste +
   dot-repeat chamber (five echo-wardens, Hall-of-Echoes two-part mend so `.`
   can't carry a whole row; macro-friendly but not forced).
5. **The Scrivener's Leaves** (`warden_scrivener` → `text_obj`) — text-object
   mends (`ciw` / `ci"` / `dit`) on corrupted verses.
6. **The Grandmaster's Seal** (`grandmasters_sanctum` → `visual_op`) — the
   staggered ranged-operator gallery reprise; the last door before the throne.

**The Unmasking (finale) — macros are the intended best line.** Beyond the
sixth seal the wizard is waiting — the same figure who recited every blessing
poem. On approach he drops the robe: he is the **Warden Eternal**
(`edit_immune`, ~6 HP, the mega-attack). He does not fight alone: he summons
**hordes of goblins** — ranks large enough that hand-killing one-by-one is
grinding, deliberate tedium. The MASTER'S answer is to **record a kill-macro
and replay it**: e.g. `qa /g⏎ x q` (search to the next goblin glyph, strike,
stop) then `@a` / `20@a` mows the whole horde regardless of layout — search
finds each goblin wherever it stands, so ONE macro scales to any wave. This is
the payoff of the Hall of Echoes: the final fight is won not by faster
fingers but by **writing a program**. Design for **multiple new macros**
(user directive): distinct enemy glyphs / registers reward a small kit —
`@a` for the goblin rank (`/g x`), `@b` for a second pattern (a different
glyph or a move-then-strike), and macros that CALL macros (record `@a` inside a
bigger sweep). Between waves the boss's mega-attack forces marked-pillar
dodging, so the loop is *record → replay to clear the horde → dodge → strike
the boss*. NOT par-forced: hand-killing still wins eventually; the horde is
merely SIZED so the macro is the obvious mastery, never a star-gate.
On his defeat he leaves behind **the wizard's hat** (a lootable Entity) and
**The Warden's Rest** epilogue scroll (zero smudges). `boss_seal` on the exit
until `_check_boss_cleared`; exit east of a bolt row per the teleport audit
(assert no jump reaches it while sealed, BFS can't either).

**Macro-horde engine checks (flag at build):** (a) goblin glyphs must be
`/`-searchable — reuse the Pathfinder `search_glyph_entities` overlay so `/g`
lands the cursor ON a goblin cell; (b) `x` must kill the entity the search
landed on (x-attacks the entity on the player's own cell — verify a
search-landing counts as "on"); (c) macro replay over an emptying board must
degrade gracefully (a `@a` whose `/g` finds nothing should no-op, not error —
`_MACRO_MAX` recursion cap + failed-search abort already exist); (d) summoning
is stateless/undo-safe like the Operator's Vault key-drop tick (resolve counts
live each tick; never hold entity refs across undo). All are small extensions
of shipped systems, not new architecture.

**Reward / ending.** Hat pickup + The Warden's Rest scroll + the existing
`warden_eternal` wizard-wisdom poem as the send-off (its last line is already
"Go gently, traveler."). The hat is the tangible "you are the master now"
token; the reveal recontextualises every poem the player has read.
`_SCROLL_DROPS['warden_eternal']` = a NON-smudge epilogue scroll (no next tier
to tease) via `_render_standard_scroll`.

**Par / budget / tests.** `par = None`, budget hand-set generous; add to
`_SKIP_LEVELS` in `test_answer_paths.py` (combat boss, no keystroke par) and
flag that exemption to the user. Tests on the `test_grandmasters_sanctum` /
`test_warden_pathfinder` template: per-chamber structure + seal-open
conditions, mega-attack safe-pillar survivability, the Unmasking transition,
exit teleport-audit (no jump/BFS reaches sealed exit), hat + scroll drop. NO
cheese-probe par battery (nothing to par-force). Answer tape optional (skip).

**Reveal plumbing — RESOLVED 2026-07-21 (user):**

1. **Wizard = Warden = the `W` glyph** — it has been the clue all along (every
   warden renders `W`). No new glyph. On the Unmasking, color the boss `W` with
   a **calm shimmering "breathing" effect** cycling violet / periwinkle / white
   / blue (a slow phase over ticks, like the mega telegraph but serene) — "the
   Wizard/Warden in all his majesty". New palette entry `warden_eternal_fg` +
   a per-tick phase index the renderer reads.

2. **The wizard's hat is WEARABLE and vim-faithful via `:set`.** Picking it up
   grants the item; the player then chooses to don/doff it with **`:set hat`** /
   **`:set nohat`** — reusing the game's established `:set` idiom (`:set wrap`,
   `:set nu`). Wearing it makes `known_commands` return the FULL command set
   (admin-like) **in every level, including early ones** — the master may use
   any spell anywhere. It is a PERMANENT post-game unlock (saved to progress
   once looted; the toggle state also persists). **Cursor tell (vim-faithful):**
   Vim signals mode by cursor shape/color (`guicursor`); here, wearing the hat
   renders the player cursor with the same violet→blue **shimmer** as the
   unmasked Warden — you literally carry his aura. `:set nohat` returns the
   normal cursor and normal per-level gating. Implementation: `player.has_hat`
   (looted) + `player.hat_worn` (toggle); `command_guard.action_allowed`
   short-circuits to allow-all when `hat_worn`; the cursor renderer picks the
   shimmer palette when `hat_worn`; `:set hat`/`nohat` parsed alongside the
   existing set-options. Gate the toggle behind `has_hat` (no early cheat).

3. **`/g` + `x` verified as the macro-kill primitive** (build-time check #3
   confirmed proceed): reuse `search_glyph_entities` so `/g` lands on a goblin;
   `x` kills the entity on the landed cell; empty-board `@a` no-ops via the
   existing failed-search abort.

---

### v2 (SUPERSEDED — par-forced three-phase, kept for reference) — 2026-07-18

> The three-phase ranged-`:s` / macros / timed-combat design below is
> superseded by v3's six-warden callback. Its *mechanics* (fire rows via
> ranged `:s`, echo-warden two-part mend, mega-attack finale) are still the
> best raw material for chambers 3–6 — mine them, but they are showcases now,
> not par-gates.

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

### Level C — SHIPPED 2026-07-18, REBUILT 2026-07-19 as London Bridge (display 42)
- v2 (user-directed: v1's vocab words were arbitrary): the vault sings
  LONDON BRIDGE IS FALLING DOWN (public domain, fixed text — par constant
  by construction). The falling verses are carved "falling UP"; the build
  and key verses keep "up" RIGHTLY, so `:%s/up/down/g` wrecks them
  self-evidently and no contiguous range spans both falling verses while
  sparing the middle. Canonical `:s/up/down/g` on the double line (spawn),
  ranged `:16,18&&` + `:4,6&&` while /g is fresh (a plain & resets the
  remembered flags), then `:1j` (bare join — user catch, 2 keys under
  :1,2j) + `:1y` + `p` lays the torn "my fair lady." where the reprise
  goes without one. A :t'd chasm slab arrives still misted — off the
  floor, it never completes the song. Par 38, budget hand-set 60.

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
