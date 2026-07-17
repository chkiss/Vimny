# Act VI — Text Objects (Capstone) — Generator-Grade Blueprints (Revised)

> ⚠ **Pre-implementation design doc — obsolete conventions; delete-on-implement.** Uses pre-slug naming (e.g. `RuneCluster` → now `CharRun`; level numbers are now the cosmetic `display` field) — don't copy these symbols. **Delete a level's section when that level ships, and the whole file once its act is built.** See LEVELS_PLAN Part 8.

> Authority: LEVELS_PLAN.md §Act VI + §Part 3 + §Part 5; engine/text_object.py;
> engine/operator.py; generation/dungeon_gen.py.
>
> **Forcing model (S1–S5):**
> - S1: terrain-∞ first — prefer walls/void/water that make the alternative impossible.
> - S2: tighten budget — where margin-forcing is unavoidable use the minimum multiplier
>   that strictly eliminates the manual path; document the multiplier per level.
> - S3: par = true full min-keystroke entry→exit including all navigation and Esc.
>   Navigation credits `$` (1 key) and `0` (1 key) as known Act-I commands; all other
>   movement is individual keystroke-steps.  Exit navigation is ALWAYS counted.
> - S4: block earlier commands — `dw`/`d{motion}` bypasses `diw`/`daw`; design terrain
>   so each text object is strictly required (cursor position forced mid-cluster, or
>   content-size makes manual path impossible, or S1 wall forces exactly the right object).
> - S5 split: Sentence (`is as`) and Paragraph (`ip ap`) are distinct scanner families
>   and are taught in separate levels (L30 and L36).
>
> Operator keystrokes counted: `d`=1, `i`/`a`=1, object-char=1 → `diw`=3.
> `$`=1, `0`=1, each h/j/k/l-step=1.  `c`-operator escape=1 extra.
> Both the `i` and `a` variant of every text object must be independently FORCED.

---

> ✅ The Brace & Square Enclosure SHIPPED 2026-07-16 as display 34 (the actual
> build diverged from the old section: exact-text chassis, the nest chamber,
> par 45 — see `build_dungeon_brace_square_enclosure` + its tests). Sections
> below use the OLD numbering; current displays: Quote=35, Tag=36,
> Sentence=37, Paragraph=38, Grandmaster's Sanctum=38.1.

> ✅ The Quote Enclosure SHIPPED 2026-07-19 as display 35 (the actual build
> diverged from the old section: exact-text chassis, spine strikes via the
> quote objects' forward seek, the Vim-true a-quote whitespace quirk, the
> C5 first-pair trap, par 47 — see `build_dungeon_quote_enclosure` + its
> tests).

---

> ✅ The Tag Enclosure SHIPPED 2026-07-19 as display 36 (the actual build
> diverged from the old section: exact-text chassis, the named nest
> (dit/dat by depth), the at double-gap tear vs the a-quote single, the
> C5 aim past an empty sibling, par 48 — `_resolve_tag` had already
> shipped with the tier-1 batch; see `build_dungeon_tag_enclosure` +
> its tests).

---

> ✅ The Sentence Enclosure SHIPPED 2026-07-19 as display 37 (the actual
> build diverged from the old section: exact-text chassis, mid-sentence
> landings as the forcing terrain, the dis/das gap discrimination, the
> Vim-true as leading-whitespace fallback on the last sentence, par 45 —
> see `build_dungeon_sentence_enclosure` + its tests).

---

> ✅ The Paragraph Enclosure SHIPPED as display 38, then REDESIGNED after
> playtest (the Warden's SIGIL replaced the row-count measure): two tall
> UNEQUAL goblin cantos (11 vs 12 rows — counted cuts pay a second digit,
> no dot pair spans both), and six brazier flames (▲ entities — rows stay
> blank) on the three must-survive rows, which stack into ▲/▲▲/▲▲▲ when
> exactly the right paragraphs fall. The seal opens on the assembled
> sigil + no goblin standing; wrong cuts SUCCEED and visibly extinguish
> flames (undo relights). The watch-gap's goblins stand on a textless
> blank row (dap-forced, :g-immune), west-walled so V}d can't tie par;
> par 9 — see `build_dungeon_paragraph_enclosure` + its tests.

---

> ✅ The Grandmaster's Sanctum SHIPPED as display 38.1 (built to the
> prepped section below: two rooms — the proving gallery's seven
> staggered-op bays on the exact-text chassis with computed pulled-gap
> targets + the legion bolt, the Grandmaster's appraisal per bolt, G's
> first-non-blank parking the player through the opened gate; then the
> arena duel — leap-exempt 'grandmaster' warden, stand-and-trade, key →
> locked door → exit + The Warden's Act chest. par None, budget 160.
> DEVIATION from the pinned decision, for morning review: the gate
> pocket is stone-hidden, so the Grandmaster is HEARD during the bays
> and SEEN when the seal parts — bolts are stone, and stone blocks
> sight (the fog law); a from-the-start sightline would have needed a
> bolt-bypassing corridor. See `build_dungeon_grandmasters_sanctum` +
> tests/test_grandmasters_sanctum.py. THIS FILE'S ACT IS COMPLETE —
> delete the file once reviewed.)

## Level 38.1 — The Grandmaster's Sanctum (act boss) — PREPPED 2026-07-25

**Slug** `grandmasters_sanctum` · display **38.1** · `type: 'boss'`,
`after: 'paragraph_enclosure'`, `teaches: []` — the `content/levels.py` entry
already exists. **Drop already wired**: `_SCROLL_DROPS['grandmasters_sanctum']`
→ The Warden's Act (`extras id 'visual_op'`, `WARDEN_ACT_SCROLL` in main.py) —
visual OPERATORS (v/V/<C-v> + d/c/y/case/J/p) unlock only from this chest.

### Engine reality check (supersedes everything in the old section)

- `_resolve_tag` SHIPPED — the old P0 blocker (Phase 5) is gone.
- There is **no `wall_rune` entity kind, no bomb timer, no pressure plate** —
  those primitives were never built and are NOT the plan. Use the shipped
  primitives instead:
  - **Exact-text doors** — `room._ss_doors` + `_sight_sanctum_tick` (add the
    slug to the dispatch tuple in main.py). Stateless, two-sided, row-agnostic
    stripped-text matching, FINAL SEAL exit. This is the act's whole chassis.
  - **The Warden's Measure** — `_paragraph_enclosure_tick` pattern: seal on
    (all goblins dead AND `room.rows ==` blessed count). Prices d}/dG/V}d
    over-deletion with zero un-Vim parrying.
  - **Warden combat** — `Entity(kind='warden', hp=5, max_hp=5, ai='')`, goblin
    summons within `_ALERT_RADIUS`, `edit_immune` parries line cuts (and stops
    `dG` collapses at his row), 1-`x` stagger windows (Manifold/Scrivener).
  - **Marker glyphs in wall cells** ride `_shift_rows` (Scrivener) — anchors
    survive row collapses.

### Player kit at entry (known_commands through `ip`/`ap`)

Everything through the enclosure act: counts, word/find/search/line/paragraph
motions, marks, `x r R s S C D J gJ`, case family, `>> << =`, insert family,
`d y c p P` + doubles, `.`, undo/redo, **visual SELECTIONS** (v/V/<C-v> — but
NOT visual operators: `visual_op` is this boss's own drop, so no bay may
require v+op), and ALL text objects (`iw aw i( a( i[ a[ i{ a{ i" a" i' a'
it at is as ip ap`). **NOT yet**: `:s`/`:g` (39), macros/named registers (40).
Cheese-audit every bay against this full kit — especially `d{n}j` ties,
`d}`/`d{` two-key linewise kills, dot-carry, and `{n}x` digit pricing.

### Design direction — a gauntlet of reprises

Not a dix/dax drill sheet. Seven bays, each distilling its level's SIGNATURE
DISCOVERY, on the exact-text chassis (gate row of bolts west of the FINAL
SEAL, spine as every row's first standable, spine-only throat):

1. **Word** — mid-cluster landing; the diw double-gap vs daw single-gap read.
2. **Bracket** — a cure at depth in a nest; the innermost-pair rule.
3. **Brace & Square** — mixed metals, casket-within-fitting; read before cutting.
4. **Quote** — strike from the rail; an EMPTY pair sits first on the line.
5. **Tag** — named cases; the innermost answers; an empty sibling decoy.
6. **Sentence** — dis/das gap discrimination; lay adjacent same-op targets so
   the par route rides the dot (the act's crowning golf), or stagger ops if
   the dot-carry makes the bay trivial — probe empirically before pinning.
7. **Paragraph** — one tall canto of goblins under the Warden's Measure; this
   bay's condition folds into the FINAL SEAL (goblins dead + measure held +
   every door true).

**Finale** — the Grandmaster: warden hp5, `edit_immune`, stationed past the
gate; summons goblins; 5 strikes through stagger windows; his fall opens the
chest (`chest_scroll` → the wired drop) and the way out.

### Constraints & conventions (learned this act — do not relearn)

- **Sizing**: the old 48×80 grid is rejected — PE's 29 rows is near the
  comfortable ceiling (test terminals are 41 high). Budget ~26–30 rows;
  if seven bays + arena don't fit one hall, use two rooms (Pathfinder
  precedent) — bays hall, then arena.
- **Pricing**: boss convention — `par None`, generous HAND-SET budget, add to
  `_SKIP_LEVELS` in tests/test_answer_paths.py. Forcing inside each bay is by
  exact-text (the wrong tool leaves the door shut), never by budget.
- Blank rows must be totally runeless (wall-embedded glyphs weld paragraphs);
  the gate row needs runes to stop `ap`'s blank-run extension.
- Space-free runs; plaques end west of the spine; no typed SPACE in the
  answer tape; `Esc` omitted from the tape; share one route generator between
  answer and test.
- Teleport audit by geometry (bolts west of the seal, spine-only throat);
  `}`'s landing refuses a walled column — usable as a gate, never a wormhole.
- apply_stone_fog for anything the stone hides from spawn (the universal fog
  audit auto-discovers the builder).
- Intro: atmospheric, names the situation only — never the per-bay
  distinction or the trap (the 2026-07-12 / 2026-07-25 spoiler law).
- Scroll smudging: The Warden's Act reveals the just-validated text-object
  tier and smudges the visual-op lines until learned (`_smudge_gate_met` —
  already authored; verify against the final known-set only).

### Decisions (RESOLVED with user 2026-07-25)

1. **Two rooms** — room 1 = the proving gallery (antechamber + seven bays +
   gate + final seal), room 2 = the arena (Grandmaster, chest, exit).
   Pathfinder precedent; keeps each room under the ~30-row ceiling.
2. **Stagger operators** — no dot-carry shortcuts; every bay is typed in
   full. "This is the final drill." Adjacent bays must not share an op
   (probe the dot empirically anyway before pinning any tape).
3. **Finale-only combat, presence throughout** — the Grandmaster acts only
   in the arena (keeps the gallery deterministic; Scrivener already owns
   during-puzzle pressure). In the gallery he stands visible beyond the
   final seal from the start and speaks one line of cold appraisal per
   bolt that opens — flavor, no mechanics.

---

## Summary Table

| Level | Name                      | Commands         | par  | budget   | Notes                                             |
|-------|---------------------------|------------------|------|----------|---------------------------------------------------|
| 38.1  | The Grandmaster's Sanctum | all text objects | None | hand-set | boss; drop wired (The Warden's Act / `visual_op`) |

(Rows for displays 30–38 removed — all shipped; see the ✅ notes above and
each level's builder + tests.)

## Old open challenges — all resolved

1. `it`/`at` engine prereq — **shipped** (`_resolve_tag`, Tag Enclosure 36).
2. & 3. ×1.03 budget tightness — **obsolete**; the act shipped on forcing-by-PAR
   with standard ×1.4 budgets (old routes win at 1★).
4. `wall_rune` delimiter kind — **never built**; exact-text doors carry the
   `a`-variant forcing instead.
5. Bomb-timer `ci"` defuse — **rejected**; the shipped `ci"`+cure exact-text
   door (Quote Enclosure) is the pattern.
6. `$`/`0` in par counts — **obsolete**; enclosure pars are hand-tallied along
   the driven tape and pinned by each level's playthrough test.
