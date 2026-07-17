# Act VII — Mastery Blueprints

> Display renumbering 2026-07-16: "Level 38" below = current display **40**
> (`hall_of_echoes`), "38.1" = **40.1** (`warden_eternal`). The BONUS WING
> (blueprints/bonus_wing.md) slots between them on the main chain, pushing
> the final boss's display out when it ships.

> ⚠ **Pre-implementation design doc — obsolete conventions; delete-on-implement.** Uses pre-slug naming (e.g. `RuneCluster` → now `CharRun`; level numbers are now the cosmetic `display` field) — don't copy these symbols. **Delete a level's section when that level ships, and the whole file once its act is built.** See LEVELS_PLAN Part 8.

> Levels 38 and 38.1 (L37 The Spellwright's Forge has shipped — section removed).
> Commands: `q @ "`. Capstone act. The family is **power automation** — transform
> many targets with a single compound command, then industrialise repetition.

> ⚠ **STALE: "Arcane Mana" is retired (2026-06-15).** The Warden Eternal (38.1)
> design below gates `:s/` behind a mana pool and cites "SPEC §6.4" — both gone.
> Substitution shipped at The Spellwright's Forge token-gated (no mana), so this
> boss needs a NEW forcing mechanism for `:s` (terrain-infinity or a token/relic
> gate) before it can be built. Treat every "mana" reference here as a dead
> placeholder, not live spec.

**Design principles applied (Part 5 S1–S4):**
- S1 — terrain-infinity first: where possible make the alternative path *impossible*
  (impassable terrain = infinite cost), not merely more expensive.
- S2 — tight budget fallback: where margin-forcing is unavoidable, set the multiplier
  so the next-best route STRICTLY exceeds budget; document the multiplier explicitly.
- S3 — par is the TRUE full min-keystroke solution, entry→exit, all navigation included.
- S4 — earlier commands blocked so newly-taught command remains required.

---

> ✅ The Hall of Echoes SHIPPED as display 40 (the actual build diverged
> from the old section: the goblin-corridor design assumed w-lands-on-
> entities semantics the engine never had — instead five ECHO ROWS on
> the exact-text chassis, one blighted verse copied five times with a
> DISTINCT last word per row (identical targets would let one mended row
> open every bolt), each needing a TWO-part mend (daw the junk + x the
> fused ◆) so the dot can never carry the whole row; macro engine was
> already fully built (engine/macro.py, Budget.frozen replay pricing);
> canonical `j qa ^ w daw w x j q 4@a G $` par 14 — the ^ makes the
> macro position-independent; budget GENEROUS hand-set 45 (straight
> manual = 43 wins 1★; forcing by PAR, not the old tight-18 scheme);
> the :s routes (subst is taught at 39) cannot name the untypable ◆ and
> land ~31, also 1★ — see `build_dungeon_hall_of_echoes` + its tests).

---

## Level 38.1 — The Warden Eternal (FINAL BOSS)

**Commands demanded:** `:s/{}/{}/g` (from L37), `q @ "` (from L38), plus all
prior mastery commands. This is the capstone encounter.

**Boss concept:** The Warden Eternal occupies a three-phase arena. Each phase
presents a different hazard pattern neutralised only by a specific Act VII mechanic.
Phase 1 requires `:s/F/I/g`. Phase 2 requires `N@a`. Phase 3 requires both — fire
rows make `:s` mandatory (terrain-infinity), and 9 warden copies make `N@a` mandatory
(tight budget). The combined requirement is achieved by layering both hazards, not by
embedding `:s` inside a macro body (which would require CHALLENGE C8 to be resolved
first).

---

### Phases table

| Phase | Name | Hazard | Required mechanic | Primary forcing |
|---|---|---|---|---|
| 1 | The Ashen Tide | 3 rows of fire (F) spawn per wave | `:s/F/I/g` | S1 terrain-infinity: fire rows impassable |
| 2 | The Echo Storm | 5 warden copies patrol identical corridors | `qa [body] q` + `4@a` | S1 sequence-force via doors; S2 budget=17 excludes single-replay |
| 3 | The Eternal Surge | 3 fire rows + 9 warden copies simultaneously | `:s/F/I/g` + `qa [body] q` + `8@a` | S1 terrain-infinity (fire) + S2 budget=62 (warden count) |

---

### Grid (multi-phase; same 20×60 arena, different overlays)

```
############################################################
#@..........................................................#   row 1  (entry)
#...........................................................#   rows 2-4 (phase 1 fire zone)
#...........................................................#
#...........................................................#
#...........................................................#
######################################D#####################   row 6  (phase door 1)
#...........................................................#   rows 7-11 (phase 2 warden zone)
#...........................................................#
#...........................................................#
#...........................................................#
#...........................................................#
######################################D#####################   row 12 (phase door 2)
#...........................................................#   rows 13-17 (phase 3 combined zone)
#...........................................................#
#...........................................................#
#...........................................................#
#...........................................................#
#...........W.......................................W.......#   row 18 (Warden Eternal)
#.................................................X.........#   row 19 (exit)
############################################################
```

- **@** entry: row 1, col 1
- **X** exit: row 19, col 49
- Phase door D1 (row 6, col 38) opens when Phase 1 condition is met.
- Phase door D2 (row 12, col 38) opens when Phase 2 condition is met.
- **W** Warden Eternal: row 18, two anchor positions (high-HP boss, 5 HP).
- Fire rows spawn in their respective zones as overlays (not part of base map).
- Warden copies spawn in their zone as overlays on phase entry.

---

### Phase 1 — The Ashen Tide (`:s/F/I/g`)

**Overlay:** On entering Phase 1, fire spawns across rows 2, 3, 4 (full-width F tiles,
impassable). The wave timer is defined in § Wave Timer Semantics below.

**Mana pool:** 12 at phase entry (resets each wave; enough for 4 × `:s/F/I/g` calls).

**S1 terrain-infinity:** Fire rows are impassable. The player cannot reach phase door D1
without clearing all three fire rows. `:s/F/I/g` is strictly required.

**Optimal sequence:**

| Step | Command | Keys | Cumulative |
|---|---|---|---|
| Clear fire row 2 (player is on row 1) | `:s/F/I/g<CR>` | 9 | 9 |
| Step into cleared row 2 | `j` | 1 | 10 |
| Clear fire row 3 | `:s/F/I/g<CR>` | 9 | 19 |
| Step to row 3 | `j` | 1 | 20 |
| Clear fire row 4 | `:s/F/I/g<CR>` | 9 | 29 |
| Step to row 4 | `j` | 1 | 30 |
| Strike Warden (row 5) | `dw` | 2 | 32 |
| Advance to door (row 6) | `j` | 1 | 33 |
| Open phase door | `x` | 1 | 34 |

**Phase 1 par:** 34 keystrokes.
**Phase 1 budget:** ceil(34 × 1.4) = **48 keystrokes** (1.4× sufficient; terrain-infinity
does the primary forcing).

Next-best without `:s`: fire rows are physically impassable. Cost = infinite.
`:s`-only (no `g` flag): 46 tiles × 1 mana each, pool = 12. Exhausts after 12 tiles.
Row 2 is still 34 tiles away from cleared. Hard block. `g` flag is mandatory.

**Mana note:** 3 × `:s/F/I/g` = 9 mana used. 3 mana remaining. Mana is not the
binding constraint in Phase 1 — terrain-infinity is. Mana pool serves as a
signal to the player that `:s` costs a resource and `g` is the efficient form.

---

### Phase 2 — The Echo Storm (`q @ "`)

**Overlay:** 5 identical Warden copies spawn at rows 7–11, one per row. Each copy
patrols its row. The compound move per copy:
- `w` — advance to warden copy
- `dw` — strike and kill the copy
- `j` — sidestep down to next row (avoid counter-attack, advance toward door)

Macro body: `w dw j` = 1+2+1 = **4 keystrokes**.
Recording block (first copy executed live): `qa` (2) + body (4 live) + `q` (1) = **7 keystrokes**.
Replay for 4 remaining copies: `4@a` = `4`+`@`+`a` = **3 keystrokes** (`@a` = 2 ks, not 3).
Navigation to door + open: `3j` (2) + `x` (1) = **3 keystrokes**.

**Phase 2 par:** 7 + 3 + 3 = **13 keystrokes**.
**Phase 2 budget:** ceil(13 × 1.30) = **17 keystrokes** (S2 multiplier; see below).

**Forcing argument:**

| Approach | Cost | vs budget 17 |
|---|---|---|
| Manual (5 copies × 4 ks + nav 3) | 23 | > 17 — EXCLUDED |
| Single-replay (4 × `@a` separately: 7+4×2+3) | 19 | > 17 — EXCLUDED |
| Count-form `4@a` (7+3+3) | 13 | ≤ 17 — PASSES |

**Why 1.30× (not 1.4×):** `@a` = 2 keystrokes. At 1.4× budget = ceil(13×1.4) = 19,
single-replay costs 19 = budget (ties, passes). S2 tighter multiplier 1.30 gives
budget=17, strictly excluding single-replay (19 > 17). Multiplier documented here.

S1 terrain-sequence via doors also forces the per-copy action sequence (must kill copy
to advance to the next row and ultimately reach door D2).

---

### Phase 3 — The Eternal Surge (combined mastery)

**Overlay:** Fire rows spawn across rows 13, 14, 15 (impassable). 9 Warden copies
spawn in a grid beyond the fire rows (rows 13–17, spread across the zone). The
Warden Eternal waits at row 18.

**Two-hazard design rationale (why NOT `:s` inside macro body):**
Embedding `:s/F/I/g<CR>` inside the macro body creates a complex engine dependency
(CHALLENGE C8: command-mode replay via `synth_key` inside macro). Instead, Phase 3
is designed so the player clears fire first (terrain-infinity forces `:s`), then
records and replays a macro for the warden copies (tight budget forces `N@a`).
Both techniques are strictly required without the `:s`-in-macro complexity.

**Optimal sequence:**

| Step | Command | Keys | Cumulative |
|---|---|---|---|
| Player enters phase 3 zone at row 12 (door just opened) | — | — | — |
| Clear fire row 13 (player on row 12, `:s` operates on current row after `j`) | `j` + `:s/F/I/g<CR>` | 1+9 | 10 |
| Step through row 13 | `j` | 1 | 11 |
| Clear fire row 14 | `:s/F/I/g<CR>` | 9 | 20 |
| Step through row 14 | `j` | 1 | 21 |
| Clear fire row 15 | `:s/F/I/g<CR>` | 9 | 30 |
| Step to row 15 | `j` | 1 | 31 |
| Navigate to warden copy 1 (row 16, already adjacent after fire clear) | — (already in position) | — | 31 |
| Record macro: `qa` | `qa` | 2 | 33 |
| Body (live on copy 1): `w dw j` | `w dw j` | 4 | 37 |
| Close recording: `q` | `q` | 1 | 38 |
| Replay for 8 remaining copies: `8@a` | `8@a` | 3 | 41 |
| Strike Warden Eternal at row 18: `4j dw` | `4j` + `dw` | 2+2 | 45 |
| Collect exit key + reach X: `x` + `48l` | `x` + `48l` | 1+3 | 49 |
| Advance to exit row 19 | `j` | 1 | 50 |

*(Row navigation is approximate; exact geometry depends on warden copy placement
in the 13–17 zone. The par of 50 is the target; exact tuning during generation
may shift it by ±2. Budget at 1.24× is set to 62 = ceil(50×1.24), giving enough
room for minor geometry variation.)*

**Phase 3 par:** **50 keystrokes** (corrected from v1's ~35, which undercounted by ~15).
**Phase 3 budget:** ceil(50 × 1.24) = **62 keystrokes** (S2 multiplier; see below).

**Forcing argument:**

| Approach | Cost | vs budget 62 |
|---|---|---|
| Macro-only (no `:s`): fire rows impassable | INFINITE | — hard block |
| `:s`-only (manual all 9 wardens): 30+2+9×4+4+4 | 76 | > 62 — EXCLUDED |
| Single-replay (8 × `@a` sep): 30+2+7+8×2+4+4 | 63 | > 62 — EXCLUDED |
| Combined `:s` + count-form `8@a`: 50 | 50 | ≤ 62 — PASSES |

**Why 1.24× (not 1.4×):** At 1.4×, budget = ceil(50×1.4) = 70. Single-replay
costs 63 ≤ 70 (passes; `N@a` not forced). S2 tighter multiplier 1.24 gives
budget = 62, strictly excluding single-replay (63 > 62). Multiplier documented.

---

### Wave Timer Semantics (Phase 1 and Phase 3)

**Definition:** The wave timer advances by 1 tick on each **normal-mode keystroke**
(motion keys, operator keys, `x`, `dw`, etc.). Keystrokes typed inside command-mode
(after `:` until `<CR>`) do NOT advance the wave timer. The full `:s/F/I/g<CR>`
sequence counts as **0 timer ticks** while being typed; the timer advances by 1 tick
when the command is confirmed with `<CR>` (i.e., command-mode entry counts as 1
normal-mode event on completion).

**Rationale:** If each character inside `:s/F/I/g<CR>` advanced the timer (9 ticks
for 9 keystrokes), a 6-keystroke wave period would fire mid-command, creating
undefined behavior (fire respawning while the player is typing the command that
clears it). Treating command-mode as atomic (1 timer tick on `<CR>`) eliminates this
ambiguity. This is a **hard engine requirement** — see CHALLENGE C6.

**Phase 1 timer calibration:**
Optimal Phase 1 normal-mode keystrokes: `j, j, j, d, w, j, x` = 7 ticks
(`:s/F/I/g<CR>` × 3 = 3 ticks; total = 7+3 = 10 ticks). Set wave period = 12
ticks to ensure no respawn during the optimal 10-tick run. A suboptimal player
(taking ≥12 normal-mode actions) will face a wave respawn, increasing difficulty.

**Phase 3 timer calibration:** Similar analysis; wave period = 15 ticks.

---

### Full boss par + budget summary

| Phase | Par | Budget | Multiplier | Primary forcing |
|---|---|---|---|---|
| Phase 1 — Ashen Tide | 34 | 48 | 1.40 | S1 terrain-infinity (fire impassable) |
| Phase 2 — Echo Storm | 13 | 17 | 1.30 | S1 sequence + S2 tight budget excludes single-replay |
| Phase 3 — Eternal Surge | 50 | 62 | 1.24 | S1 fire-infinity + S2 excludes `:s`-only and single-replay |
| **Boss total** | **97** | **127** | — | All Act VII techniques required |

*(v1 total was 82/116. Corrected to 97/127 due to: Phase 2 overhead +1 (7 not 6);
Phase 3 par +15 (50 not 35) from correct counting of all steps.)*

---

### Placements (full arena)

| Thing | Location | Notes |
|---|---|---|
| Entry `@` | row 1, col 1 | — |
| Phase door 1 | row 6, col 38 | Opens when all P1 fire cleared + Warden struck |
| Phase door 2 | row 12, col 38 | Opens when all 5 P2 copies killed |
| Fire rows (P1) | rows 2, 3, 4 (full width) | Wave-spawned; impassable terrain |
| Warden copies × 5 | rows 7–11, col ~30 | Phase 2; each patrols its row |
| Fire rows (P3) | rows 13, 14, 15 (full width) | Phase 3 overlay; impassable |
| Warden copies × 9 | rows 13–17, spread | Phase 3; pattern TBD at generation |
| Warden Eternal | row 18, col 30 | High HP (5); boss entity |
| Exit `X` | row 19, col 49 | Unlocked after Warden Eternal struck |
| Mana refill orb | row 6, col 1 | Restores 12 mana on entry to Phase 2 zone |
| Mana refill orb | row 12, col 1 | Restores 12 mana on entry to Phase 3 zone |
| Hint scroll | row 1, col 10 | "Record your spells. Replay your will." |

---

### Flagged assumptions / CHALLENGES

- **CHALLENGE C6 — Wave timer semantics (engine):** Timer must be implemented
  as a normal-mode-keystroke counter, not a raw keystroke counter. Command-mode
  input (after `:`) must not advance the timer until `<CR>` confirmation. Requires
  a per-room tick hook in the game loop and a mode-aware counter. New engine feature.
- **CHALLENGE C7 — Multi-phase boss state machine:** Phase door triggers (open on
  condition), HP tracking across `dw` strikes, and overlay spawning per phase require
  a boss state machine in `content/bosses.py` or a general `on_condition` system in
  `engine/world.py`. New engine feature.
- **CHALLENGE C8 — `:s` inside macro body (deferred):** Phase 3 is redesigned to
  NOT require `:s` inside a macro body, avoiding this challenge. If a future level
  requires it, `engine/macro.py`'s `record_char` must capture `:`, `/`, printable
  chars, and `<CR>`, and command-mode dispatch must replay correctly via `synth_key`.
  Flag as a deferred hard prerequisite.
- **CHALLENGE C9 — Macro-aware par solver (boss):** Phase 3 par computation requires
  the solver to model the macro recording + replay sequence without `:s` inside it
  (simpler than C8 requires, but still needs the recording-state extension from C5).

### Self-check

- [x] ≤ 3 new mechanics: `:s` (L37), macros (L38); boss reuses both. No new mechanic.
- [x] Coherent family: all phases demand Act VII power-automation techniques.
- [x] Phase 1: S1 terrain-infinity forces `:s/F/I/g`. Mana blocks bare `:s/F/I/`.
- [x] Phase 2: S1 sequence-force + S2 budget=17 (1.30×) forces `N@a` over single `@a`.
- [x] Phase 3: S1 forces `:s` (fire impassable); S2 budget=62 (1.24×) forces `N@a`.
  Combined par=50 ≤ 62; `:s`-only=76 > 62; single-replay=63 > 62.
- [x] Phase 3 does NOT embed `:s` inside macro body — avoids C8.
- [x] Wave timer semantics defined: fires on normal-mode ks only; command-mode = 0 ticks.
- [x] Boss par corrected: 97 (was 82). Budget corrected: 127 (was 116).
- [x] Phase 2 overhead corrected: 7 keys (was 6). Phase 2 par = 13 (was 13 coincidentally,
  but budget corrected from 19 to 17).
- [x] Phase 3 par corrected: 50 (was ~35 — dramatically undercounted in v1).
- [x] All CHALLENGES (C1–C9) listed with resolution paths.

---

---

## Appendix — Summary Table

| Level | Commands | Par | Budget | Multiplier | Forceable? | Key Risks / Challenges |
|---|---|---|---|---|---|---|
| 37 — Spellwright's Forge | `:s/F/I/` `:s/F/I/g` | 44 | 62 | 1.40 | Yes — S1 terrain-infinity (impassable fire) + mana hard-block on bare `:s` | C1 mana economy (SPEC §6.4 TBD); C2 terrain immutability under `d`/`c`/`r` |
| 38 — Hall of Echoes | `qa…q` `@a` `N@a` | 14 | 18 | 1.28 | Yes — S1 goblin/door sequence + S2 tight budget excludes both manual and single-replay | C3 `w` word-boundary verification (layout locked); C4 `dw` kill semantics; C5 macro-aware par solver |
| 38.1 P1 — Ashen Tide | `:s/F/I/g` | 34 | 48 | 1.40 | Yes — S1 terrain-infinity (fire impassable) | C6 wave timer (normal-mode only); C7 multi-phase state machine |
| 38.1 P2 — Echo Storm | `qa…q` `N@a` | 13 | 17 | 1.30 | Yes — S1 sequence + S2 excludes single-replay | C6 wave timer; C7 state machine |
| 38.1 P3 — Eternal Surge | `:s/F/I/g` + `qa…q` + `N@a` | 50 | 62 | 1.24 | Yes — S1 fire-infinity forces `:s`; S2 excludes `:s`-only and single-replay | C8 deferred (`:s` in macro not used); C9 macro-aware solver for boss |
| **Boss total** | All Act VII | **97** | **127** | — | Yes | All challenges above |

---

## CHALLENGES requiring human decision

See dedicated section at end of document for full list. Summary:

| ID | Challenge | Affects | Decision needed |
|---|---|---|---|
| C1 | Mana economy (SPEC §6.4) — per-room pool, deduction, display | L37, L38.1 | Engine implementation spec |
| C2 | Terrain immutability under `d`/`c`/`r` operators | L37, L38.1 | `engine/operator.py` dispatch rule |
| C3 | `w` word-boundary on goblin/rune tile types | L38, L38.1 | `engine/motion.py` tile classification |
| C4 | `dw` semantics: attack entity at cursor vs. delete through range | L38, L38.1 | `engine/operator.py` combat rule |
| C5 | Macro-aware par solver (recording-state extended Dijkstra) | L38, L38.1 | Validator architecture decision |
| C6 | Wave timer: normal-mode-only ticks; command-mode = 0 ticks during entry | L38.1 | Engine tick hook design |
| C7 | Multi-phase boss state machine (phase doors, HP tracking, overlays) | L38.1 | `content/bosses.py` architecture |
| C8 | `:s` inside macro body via `synth_key` (deferred; not used in current design) | Deferred | Defer until needed |
| C9 | Macro-aware par solver for boss Phase 3 (extension of C5) | L38.1 | Covered by C5 decision |
