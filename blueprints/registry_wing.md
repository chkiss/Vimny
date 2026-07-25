# The Registry — a post-adoption bonus wing (registers)

> ⚠ **Pre-implementation design doc — delete-on-implement.** Delete a level's
> section when it ships; delete the file when the wing is built.
> Agreed 2026-07-23: a nine-level register masterclass + a boss capstone,
> unlocked once the player **adopts the horse** (`progress['horse_name']` set).
> The wing is OFF the main chain — a separate overworld section that teaches
> nothing the main game requires, so no earlier par is at risk.

## Framing

Adopting the horse opens a new stable of levels: **The Registry**. Diegetically
the horse carries your clips — his saddlebag *is* the selection register
(Level VII), which ties the wing back to the reward that unlocked it.

**Unlock gate.** `progress.get('horse_name')` is truthy (horse named/adopted).

**Overworld placement (user, 2026-07-23).** The nine levels + the boss are listed
**after The Warden Eternal** in the `world/` menu. Concretely: append their `LEVELS`
entries *after* the `warden_eternal` (display 48.1) entry — the world menu renders in
`LEVELS` order, and `dummy` is `admin_only` (filtered out for players), so appended
entries fall at the visible tail. They stay **hidden until adoption** (gate the rows
on `progress.get('horse_name')`, the way the hidden-levels wing hides its rows), so a
player who has beaten the game but not taken up the horse sees the menu end at the
Warden Eternal; adopting him reveals the Registry below it. Displays are cosmetic
(propose `R1`–`R9` + `R9.1` for the boss, or 49–57.1) — the slug is identity.

**The saddle gate (SHIPPED 2026-07-23).** The horse's saddle holds the registers,
so the register machinery only works when the horse is in the room. `command_guard.
is_saddle_register(reg)` marks the saddle registers — every register named by a
**digit or symbol** (`"0`–`"9` `"-` `"_` `"/` `":` `".` `"%` `"#` `"=` `"*` `"+`).
`action_allowed(..., horse_present=)` (wrapped in `run_dungeon._action_allowed` with
the live `_horse_here()` state) blocks them on any horse-free level — bosses, the
combat crushes, the whole pre-adoption game. **Exempt** (their own gates, no horse
needed): the **unnamed** register `""` (token `register`) and the **named / macro**
registers `"a`–`"z` / `"A`–`"Z` (token `reg_named`, the `q`/`@` machinery). This is
why the wing's puzzles are safe: the registers they teach simply don't exist off the
saddle, so no boss or main-chain par can lean on them.

**House rules (unchanged).** Every level is solved with the register it teaches.
Forcing is **by par, not budget**: an old-register route still *wins* but overpays
and drops the 2nd star. Runtime placement / gating only where it touches the
horse; builders and par solvers stay pure and seed-parametrised.

## What already exists (don't re-teach from scratch)

- `""` unnamed — introduced by the Reliquary (token `register`).
- `"a`–`"z` named — taught in the Hall of Echoes (token `reg_named`, with `q @`).

So Levels I and IV are **deepening refreshers**, not first contact; the genuinely
new teaching load is II, III, V, VI, VII, VIII, IX.

## The 10 → 9 reconciliation

Ten register families, nine titled levels: the four **read-only / environment**
registers (`":` `".` `"%` `"#`) are one family — "registers you can read but never
write" — and share **one** level (V). Plus a boss capstone (**The Registrar**).

| # | Overworld name | Register(s) | New token | Status |
|---|---|---|---|---|
| I    | The Register I — *The Unnamed Hold*    | `""`                 | reuses `register`   | refresher |
| II   | The Register II — *The Delete Ring*    | `"0`, `"1`–`"9`      | `reg_numbered`      | new · core |
| III  | The Register III — *The Small Cut*     | `"-`                 | `reg_small_delete`  | new |
| IV   | The Register IV — *The Named Vaults*   | `"a`–`"z`, `"A` append | reuses `reg_named` | deepen |
| V    | The Register V — *The Clerk's Ledger*  | `":` `".` `"%` `"#`  | `reg_readonly`      | new |
| VI   | The Register VI — *The Reckoner*       | `"=`                 | `reg_expr`          | new |
| VII  | The Register VII — *The Saddlebag*     | `"*` `"+`            | `reg_selection`     | new |
| VIII | The Register VIII — *The Black Hole*   | `"_`                 | `reg_blackhole`     | new |
| IX   | The Register IX — *The Seeker's Echo*  | `"/`                 | `reg_search`        | new |
| —    | The Registrar (boss capstone)          | multi-register       | — (`type: boss`)    | new |

Sequencing *is* the difficulty curve: I (refresher) → II (the ring, the conceptual
linchpin) → III/IV (isolation & multiplexing) → V (read-only strings) → VI (compute)
→ VII (persistence) → VIII (the void trick) → IX (search callback) → boss.

---

## Proverbs over plaques — sense, not decree (user, 2026-07-23)

Extend the famous-text program (`blueprints/sense_not_decree.md`, pool
`content/proverbs.py`) into this wing: wherever a level would otherwise carve a
**plaque that decrees the answer**, use a WELL-KNOWN PUBLIC-DOMAIN proverb or verse
whose *structure* is the solution — the player repairs / completes / retrieves a text
they know by heart, and any plaque demotes to confirmation. Registers are an
unusually good fit: their whole point is *which stored fragment do I bring back*, and
a remembered saying tells you which fragment without a sign spelling it out.

**Where it lands (per level):**

| # | Register | Proverb/poem opportunity (replaces the plaque) |
|---|---|---|
| I    | `""`         | Complete a proverb missing one word: yank the stray word, `p` it into the gap. The saying (not a plaque) says which word belongs; the clobber-twist strands it, and the saying's shape shows what's still missing. |
| II   | `"0`/`"1`–`9`| **Poem-as-ring.** Delete three lines of a known stanza in sequence; the gate wants the *oldest* — the player knows the poem's line order, so the numbered ring is retrieval, not guesswork. Yank-chamber: complete a proverb whose key word you `"0p` back after `dd`s clobber `""`. |
| III  | `"-`         | A single wrong word in a MISQUOTE (`content/proverbs.py`): the small charwise cut that fixes it survives in `"-` past an unrelated linewise `dd`. The famous line is the cue. |
| IV   | `"a`–`"z`, `"A` | Three cure-words from three proverbs → `"a`/`"b`/`"c`. Append chamber: gather the scattered fragments of ONE famous couplet, in order, into `"A`; the assembled line is verse the player knows. |
| V    | `":` `".` `"%` `"#` | **The plaque-honest exception** — a *records office* where dry labels are diegetically right (file names, last command). Minimal proverb use; `".` can re-stamp a short famous phrase you inscribe once. Keep the clerical texture; don't force verse here. |
| VI   | `"=`         | A **counting rhyme** supplies the numbers to compute: "One for sorrow, two for joy…" (magpies) or "Thirty days hath September…". The rhyme is the riddle; `"=` does the sum. |
| VII  | `"*`/`"+`    | **Couplet across the boundary.** Carry the first half of a famous couplet in `"*`; the exit chamber's door wants the whole. Its shape means you know what the saddlebag holds. |
| VIII | `"_`         | A proverb interrupted by junk words (INTRUDER shape): `"_dd` the junk into the void so the key word you carry in `""` survives. The saying flags which words are intruders. |
| IX   | `"/`         | A **buried/repeated word** in a tongue-twister or proverb (the Buried-Word chassis): `/` the word you know from the saying, then `"/p` inscribes the pattern. |

**Anchor law still applies** (`sense_not_decree.md` §2): par invariance is
**column-anchored**, not text-anchored — pool-drawn sayings must have their fixed slot
column fall where the register op lands, with the prefix right-aligned west. Every
conversion is a mini-rebuild: text → re-derived par → rival re-audit → karaoke. Keep
texts universally known and long out of copyright; refuse copyrighted lyrics.

---

## Per-level design

### I — The Unnamed Hold (`""`) — SHIPPED 2026-07-23
`build_dungeon_register_unnamed_hold` + `tests/test_register_unnamed_hold.py`.
Vertical spine, three OPEN bays top→bottom (no gate, no fog — all reachable so the
layout can tempt): QUARRY (the lone word "godliness", met first), DAW ("look before
you {junk} leap"), GAP ("cleanliness is next to ____"). You meet the word first, so
the natural plan is yank → walk down → paste — but the DAW sits between, and cutting
it en route overwrites `""` with the junk, so `p` lays the junk and the gap stays
false. The lesson: a delete clobbers what you carry. Fix by ORDER (yank+paste the
gap first, then daw) or re-yank; nothing is walled off so the sting costs only a
retry. **Par 16** = the adversarially-golfed optimum (`j ye 4j fo p - k fq dw G l`:
`ye` grabs " godliness" with its leading space in one stroke, `fo p` lays it, `dw`
cuts the intruder). **Budget is STANDARD** `ceil(16*1.4)=23` — tight on purpose (a
post-game mastery level): a looser register order (~17) still wins at 1★, but a
verbose retype (~24) or a clobber-then-re-yank recovery (~32) OVERSHOOT and are
barred, so the register tools are the way through and a fumbled run can strand
(user call — recover with undo, or restart). The tempting yank→daw→paste fails
outright. Seal-only tick `_register_unnamed_hold_tick`. Sense, not decree: both bays
are famous sayings.

**Cost-model fix (bonus of this level):** `_token_ks_cost` in
`tests/test_answer_paths.py` under-charged a 2-char operator+motion (`ye`/`dw`/`d$`/
`dd`) as 1 key when the engine charges 2. No shipped answer used such a token before
this level, so the bug was latent; patched to return 2, letting this answer stay
tokeniser-validated (no `_ANSWER_NOT_TOKENISED` / `_NONSTANDARD_BUDGET` exemption).

### II — The Named Vault (`"a`/`"b`) — SHIPPED 2026-07-25 (rebuilt TWICE same day)
`build_dungeon_register_named_vault` + `tests/test_register_named_vault.py`.
**Two sayings, alternating.** Quarry rows 3–4 hold `godliness` and `invention`;
six bays (rows 5–10) alternate `cleanliness is next to dust` / `necessity is the
mother of dust`. Every bay is the same **exchange**: `$b diw "XP` — cut the junk
word out, set the right word into the hole it left. par **69** (named, driven,
seed-invariant), standard `ceil(69*1.4)=96` budget. The best one-register route
(`"_diw` so the cut never eats its word, then batch one saying and walk back for
the other) costs **74** → 1★. Fully open: no gates, no fog, and because the bays
alternate the repeating unit is a **pair** — record it at the first bay and
`2@q` the rest: **37**. The reward, not the requirement.

#### FORCE BY CAPACITY, NOT BY SURVIVAL (rebuild #1)
The first cut forced `"a` by **threat**: a `daw` clobbered `""`, so you had to
hide the word somewhere safe. That is not forcing — it is a *protection* puzzle,
and **any protection tool solves a protection puzzle**. `"_daw` sends the cut to
the black hole, leaves `""` untouched, and came in at **55 against par 59** — it
BEAT par. Worse, the player who found it had learned something true about Vim and
was being punished for it. Pricing `"_` higher would have been a thumb on the
scale hiding a design error.

#### NEVER LET ONE CLIP HOLD BOTH WORDS (rebuild #2 — playtest, user 2026-07-25)
Cut #2 forced by capacity, but put the two quarry words on adjacent rows and made
every bay want **both**. The playtester ran `j J 0 y2e qa 2j fe p 0 4@a`: `J`
joined the quarry rows, one `y2e` took both words as a single clip, and a macro
did the vault **with no named register at all**. Separate *rows* is not a
guard — `J`, `dd`, `:m`, and visual-block all reshape rows.

The only durable guard is that **no single clip is ever wanted anywhere**: two
sayings that share no word, one word per bay. Then a combined clip is garbage in
every bay by construction, and it does not matter how the player rearranges the
quarry. Alternation also kills `.` — the last change flips register every bay.

**Deletions are what put `""` under fire.** Each bay must `diw` its junk word
before it can paste, so the one-register rival needs `"_` on all six bays. Per
bay that ties par exactly (`"_diw`+`P` = `diw`+`"aP` = 8); the entire margin is
the **second walk of the vault** to fetch the other saying's word. Thin (5 keys)
but real, and it is the honest gap — `"_` is a *reward* for knowing it here, not
a hole.

**Make the quarry words LONG.** `$b cw<word>` retypes a bay for `4+len(word)`
against the register route's flat 8, so a short word makes the keyboard beat the
vault outright. Nine letters each ⇒ 13 vs 8. `test_typing_the_word_costs_more_
than_pasting_it` pins this.

**The deeper limit (read before the next named-register level).** With the prefix
charged, a named register costs +2 per paste while a one-register rival pays only
extra *travel* — and travel is cheap because counts are cheap (`8k` = 2 keys). So
for **additive** puzzles named registers barely win. The shape that wins is
**exchange**, which is what this level finally became: the paste lands in a hole
the delete just made, so the two operations are welded together and the rival
cannot decouple them.

### THE REGISTER-PREFIX CHARGE (engine law, user 2026-07-24)
`"{reg}` is two real keypresses, so `main._register_prefix_cost(action)` adds 2 to
every operator (`_operator_cost`) and every paste charge. A named register buys
**persistence, not free typing**. The audit's `_token_ks_cost` matches (`"aye` = 4,
`"ap` = 3). Before this, prefixes were charged 0 — which would have made named
registers a pure golf win and broken the wing's whole difficulty curve.

### (later) The Delete Ring (`"0`, `"1`–`"9`) — richest level in the wing
Two chambers.
- **Yank survives delete:** yank the key word, then clear three obstacle-words with
  `dd` (each overwrites `""`). The door needs the key word — only `"0p` (the yank
  register, untouched by deletes) still holds it. Old route: re-yank after the
  deletes → detour → over par.
- **The ring (poem-as-ring):** three lines of a stanza the player knows are deleted
  in sequence; the gate wants the **oldest**. Because it's a remembered poem, its
  line order is known — `"1p`/`"2p`/`"3p` walk the delete ring (or `"1p` then `.` to
  rotate) to *retrieve* it, no plaque decreeing which line was first. Forcing: no
  non-numbered register reaches a superseded delete.

### III — The Small Cut (`"-`)
Charwise deletes < one line land in `"-` (and `""`); a **linewise** delete pushes the
numbered ring and evicts `""`. Puzzle: make a small charwise cut (`x`/`dw`), then a
linewise `dd` elsewhere; the door wants that first small cut back — `""` is gone (the
`dd` took it) but `"-p` still has it. Forcing: only `"-` isolates the small delete.

### IV — The Named Vaults (`"a`–`"z`, `"A` append)
Deepens the Hall of Echoes. Three doors need three *different* words; `""` can't hold
three. Stash each in `"a`/`"b`/`"c` (`"ayw`), unlock with `"ap`/`"bp`/`"cp`. Second
chamber teaches **append**: gather scattered fragments of one phrase, in order, into
`"A` (uppercase = append), paste the assembled whole. Forcing: three simultaneous
clips are impossible without named registers.

### V — The Clerk's Ledger (`":` `".` `"%` `"#`) — read-only family
A "records office"; these registers are *read* (pasted) but never written by you.
- `".` last inserted text — type a word in one alcove; a later door wants it again →
  `".p` re-stamps without retyping.
- `":` last Ex command — a lock wants the command you just ran, spelled out.
- `"%` current file name — the level's own name is one door's passphrase.
- `"#` alternate file — via the existing `:e {file}` multi-buffer system (Archivist's
  Library chassis): after `:e` to a second buffer and back, `"#` names the one you
  left; a door wants that name.
Forcing: these strings live *only* in the read-only registers; retyping is possible
but the level/file names are long enough that `"%p`/`"#p` win on keys.

### VI — The Reckoner (`"=`)
The expression register. A gate poses an arithmetic riddle (rune counts, star
totals). `"=` opens an expression prompt; type the sum, `<CR>p` pastes the computed
number into the lock. Ties to the game's count system. Forcing: the answer exists as
*no* text anywhere to yank — it must be computed.
**Scope note:** needs a small, **sandboxed integer-expression evaluator** (arithmetic
only — no arbitrary `eval`).

### VII — The Saddlebag (`"*` `"+`) — thematic keystone
Vim's `"*`/`"+` are the OS selection/clipboard: content that outlives the buffer.
No OS clipboard in-game, so map them to a **cross-level clip carried by the horse**,
persisted in `progress` (the saddlebag). Puzzle spans an entrance and exit chamber
separated by a "leave and return" (a `:e` / level boundary): `""` is wiped by the
trip, but `"*` survives because the horse carried it. Forcing: only the selection
register persists across the boundary — and it *only exists because you adopted the
horse*, closing the loop.
**Faithfulness note:** the one family with no literal in-game Vim analogue; this is a
faithful-in-spirit mapping (user-approved 2026-07-23).

### VIII — The Black Hole (`"_`)
You carry a key word in `""`. Decoy words block the path and must be deleted — but a
normal `dd`/`x` would overwrite the key. `"_dd` deletes into the void, leaving `""`
intact; then `p` the key at the door. Forcing: every non-black-hole delete clobbers
the carried clip; only `"_` removes without side effects. Clean, elegant "aha."

### IX — The Seeker's Echo (`"/`)
The last-search-pattern register. A hidden word is found only by `/pattern` (search
chops from Seekers' Labyrinth). A door then wants that exact pattern *as text*:
`"/p` pastes what you last searched for (`<C-r>/` in insert is the equivalent).
Forcing: the pattern lives only in `"/`; retyping risks a mismatch and the paste is
fewer keys. Callback to the search wing.

### Boss — The Registrar (`type: boss`, `after: <IX slug>`)
A mastery gauntlet: one multi-lock vault that forces juggling several registers at
once — e.g. a `"*` saddlebag clip brought in, a `"_dd` to clear a decoy without
losing it, a `"0p` yank that survived intervening deletes, and a `"/p` search paste
to finish. No new token (bosses teach nothing). Its `chest_scroll` previews… nothing
further (end of the wing) — instead drop a lore scroll: *The Complete Registry*, the
one-page table of all ten register families, as the wing's trophy.

---

## Proposed slugs (immutable once created)

`register_unnamed_hold`, `register_delete_ring`, `register_small_cut`,
`register_named_vaults`, `register_clerks_ledger`, `register_reckoner`,
`register_saddlebag`, `register_black_hole`, `register_seekers_echo`,
`the_registrar` (boss).

## Engine work this implies

Extend the existing `player.registers` model + `"`-prefix parsing (named registers
already work — generalise the prefix to every register name and gate each token):

- **`"0` + `"1`–`"9`** — numbered ring: `"0` = last yank; linewise delete/change
  shifts `"1`→`"2`→…; `.` after `"1p` rotates. (`reg_numbered`)
- **`"-`** — small-delete slot for charwise (< one line) deletes. (`reg_small_delete`)
- **`"_`** — black-hole sink: writes discarded, `""` untouched. (`reg_blackhole`)
- **`"/`** — populated by the last search; readable/pasteable. (`reg_search`)
- **`":` `".` `"%` `"#`** — read-only population from last-Ex / last-insert /
  current-file / alternate-file; paste-only. (`reg_readonly`) `"#` leans on the
  `:e`/netrw multi-buffer system.
- **`"=`** — expression prompt + **sandboxed integer eval** → paste result. (`reg_expr`)
- **`"*` `"+`** — persisted to `progress` (saddlebag), survives level transitions.
  (`reg_selection`)

Parser/guard: generalise `"{reg}` prefix parsing; add each token to `action_allowed`
+ `guard_message`; add `render/vim_commands.md` rows (hint tiers auto-derive).
Mechanics genuinely new: **VI** (expression prompt) and **VII** (cross-level clip).
Everything else reuses the yank/delete/paste + door-riddle chassis already in the
Quartermaster / Hall of Echoes / mislabelled-doors levels.

## Overworld / gating checklist (when building)

- Add the nine + boss `LEVELS` entries as a separate bonus section (not on the main
  chain); regen the curriculum table (`content/_gen_curriculum_table.py`).
- Gate visibility/unlock on `progress.get('horse_name')`; wire the reveal the way the
  hidden-levels wing does.
- Per-level `build_dungeon_<slug>` + `_par_<slug>` + `tests/test_<slug>.py`
  (dimensions, reachability, par == solver, budget, **command necessity by par**,
  void safety) — full new-level checklist.
- Wizard-wisdom POEM per level (`art/_gen_wizard_wisdom.py`, `introduces_slug`).

## Open items to confirm before building

1. **Level II ordering of the two chambers** — yank-survives-delete first (motivates
   `"0`) then the ring, as written. ✔ assumed.
2. **`"=` eval sandbox** — integer arithmetic on rune/star counts only; confirm the
   allowed grammar (`+ - * /`, parens?) before implementing VI.
3. **Saddlebag persistence key** — store the `"*` clip in `progress['saddlebag']`;
   confirm it should also survive save/quit (proposed: yes — it's the horse's).
4. **Text picks** — choose the specific proverbs/verse per level from the
   `content/proverbs.py` pool (extend it as needed): the II stanza (line order must
   be famous), the IV couplet to fragment-and-append, the VI counting rhyme, the VII
   couplet to split across the boundary. Each pick then drives a re-derived par +
   rival re-audit (anchor law). V stays deliberately plaque/records-clerical.
