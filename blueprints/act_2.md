# Act II Boss Blueprint — The Warden Surveyor (13.1)

> ⚠ **Pre-implementation design doc — obsolete conventions; delete-on-implement.** Uses pre-slug naming (e.g. `RuneCluster` → now `CharRun`; level numbers are now the cosmetic `display` field) — don't copy these symbols. **Delete a level's section when that level ships, and the whole file once its act is built.** See LEVELS_PLAN Part 8.

Act II's teaching levels (L6–L13: WORD Forge → Sentence Corridor) are **built** —
see `generation/dungeon_gen.py` (`build_dungeon_<slug>`) and the matching
`tests/test_<slug>.py`. Their blueprints were retired (delete-on-implement).
What remains here is the one **unbuilt** Act II design: the capstone boss.

Slug `warden_surveyor`, key `dungeon_13.1_the_warden_surveyor`; ships after L13
(The Sentence Corridor).

## The Warden Surveyor (ACT II BOSS — caps L6–L13)

*(The grid below still shows the original **5-phase** layout; phases 5 (`%`) and
7 (`)`/`(`) need adding — see the Phase Table, which is the authoritative 7-phase
spec.)*

### Overview

The Warden Surveyor caps the structural-motion act (L6–L13). Each of its **seven** combat phases
demands a different structural family taught in that act.

**Immunity clarification:** The Warden Surveyor's phase seals and shields CANNOT be cleared by
Act I motion-based approaches. Only Act II structural motions trigger phase transitions. `hjkl`
remain available for micro-positioning within each phase corridor — they are not disabled.
The forcing is terrain-based (S1) within each phase: the Act II motion is the only finite-cost
way to reach the phase trigger. Act I motions (hjkl, w/b/e, f/F/t/T, ; ,, ^$0, count) are
freely usable for navigation; they simply cost too much (or ∞ due to terrain) to clear phases.

### Phase Table

| Phase | Motion family | How forced (S1 terrain) | One motion per phase |
|---|---|---|---|
| 1 — WORD Approach | `W` `B` `E` | Code-WORD corridor; `w`/`b`/`e` cost ≥3× as many ks; tight phase budget → W/B/E required | ✓ |
| 2 — Backward Retreat | `ge` `gE` | Wall strip between anchor and right side (S1); h-count ∞ | ✓ |
| 3 — File Teleport | `G` `gg` | Full WALL between sections; G/gg the only cross-wall teleports | ✓ |
| 4 — Screen Thirds | `H` `M` `L` | Keystones at H/M/L rows; jointly forced (all-three-skip > phase budget) | ✓ |
| 5 — Bracket Lock *(NEW)* | `%` | Phase seal sits behind a nested bracket pair; `%` is the only finite-cost jump to its match (walls/void ∞ otherwise) | ✓ |
| 6 — Paragraph Gulf | `}` `{` | Full-width void barrier; `}`/`{` the only finite-cost cross-barrier motion | ✓ |
| 7 — Sentence Span *(NEW)* | `)` `(` | Wall-gapped multi-sentence row (per L13); `)`/`(` the only way onto the trigger sentence, then `$` to its end | ✓ |

### Grid

```
60 cols × 26 rows

Row 0:  ############################################################
Row 1:  #@[WORD clusters: a.b+c*d x+y*z/w m.n-p*q §‽∘¶]   [D1]  #  (Phase 1)
Row 2:  #  [WORD cluster filler]                                   #
Row 3:  ############################################################  (wall separator)
Row 4:  #  [ge anchor cols 2-5] ################################## #  (Phase 2; wall strip 6-57)
Row 5:  ############################################################  (wall separator)
Row 6:  #  [open corridor — G zone]                 [KS-G (6,55)] #  (Phase 3 BOTTOM)
Row 7:  #                                                          #
Row 8:  ############################################################  (FULL WALL — G/gg barrier)
Row 9:  #  [open corridor — gg zone]   @ phase3 entry (9,1)       #  (Phase 3 TOP)
Row 10: ############################################################  (wall separator)
Row 11: ####[KS-H (11,4)]...[rune clusters]...####################  (Phase 4: H row)
Row 12: ##########################################################  #
Row 13: ####[KS-M (13,4)]...[rune clusters]...####################  (Phase 4: M row)
Row 14: ##########################################################  #
Row 15: ####[KS-L (15,4)]...[rune clusters]...####################  (Phase 4: L row)
Row 16: ############################################################  (wall separator)
Row 17: # [Para 1: rune clusters rows 17-18]                      #  (Phase 6)
Row 18: # [rune clusters]                                          #
Row 19: ○○○○○○○○○○○○○○○○○○○○○○○○○○○○○○○○○○○○○○○○○○○○○○○○○○○○○○○○○  (void barrier)
Row 20: ○○○○○○○○○○○○○○○○○○○○○○○○○○○○○○○○○○○○○○○○○○○○○○○○○○○○○○○○○
Row 21: ○○○○○○○○○○○○○○○○○○○○○○○○○○○○○○○○○○○○○○○○○○○○○○○○○○○○○○○○○
Row 22:    (blank row — } target)
Row 23: # [WARDEN_SEAL] [boss_seal] [exit X at col 58]            #
Row 24: ############################################################
Row 25: ############################################################
```

**Dimensions:** 26 rows × 60 cols
**Entry:** (1, 1) — `@`
**Exit:** (23, 58) — `X`

### Phase Details

**Phase 1 (WORD Approach):** Row 1 has four code-WORD groups (same spec as Level 6:
alternating word/punct chars, ≥6 w-boundaries per group). Seal door D1 at (1,50). Player
uses `4W` (2 ks) to navigate the code corridor. `w`-only alternative: ≥24 w-presses = 3 ks
for C1 alone — per-phase budget makes this too slow. Phase par ≈5 ks; phase budget tight.

**Phase 2 (Backward Retreat):** Row 4, anchor at cols 2–5 (4 all-WC chars). Wall strip at
cols 6–57 (S1: h-count ∞). From col 58 (right edge), `ge` or `gE` jumps backward to col 5
(end of anchor) in 1 ks. No other finite-cost option. Phase seal opens at col 5.

**Phase 3 (File Teleport):** Full WALL at row 8. Phase 3 entry at (9,1) (TOP section).
KS-G at (6,55) (BOTTOM). Player uses `G` (1 ks) → (6,55), `x` (1 ks) to collect KS-G, then
`gg` (2 ks) → (9,1) [gg = entry of phase 3 section]. `hjkl` for micro-nav within sections.
Without G: `7j 54l` = 2+3 = 5 ks (phase budget makes this too slow). Without gg: ∞ (full wall).

**Phase 4 (Screen Thirds):** Phase 4 section is rows 11–15 (5 rows total; 3 passable rows 11,
13, 15 with KS at H/M/L targets). Entry at (13,25) (M row). KS-H at (11,4), KS-M at (13,4),
KS-L at (15,4). Same H/M/L mechanics as Level 9 but within a single 5-row phase section (not
3 sub-rooms). Wall separators at rows 10,12,14,16 with single-col gap at col 4 only force the
player to be at col 4 to descend/ascend between rows — `^` step required for any count-k/j
alternative from col 25. All-three-skip > phase budget (jointly forced within this phase section).

**Phase 6 (Para Finale):** Full-width void barrier at rows 19–21. Blank row 22 = `}` target.
`}` (1 ks) from row 18 → row 22. `j` (1 ks) → row 23 = warden room. Without `}`: death on
void row landing. S1 forced. ✓

*(Phases 5 (`%` bracket lock) and 7 (`)`/`(` sentence span) are specified in the Phase Table
but not yet drawn into the grid above — add them when building.)*

### Boss Phases Summary

| Phase | Par (approx) | Key motions | S1/S2 |
|---|---|---|---|
| 1 WORD | 5 ks | 4W (2 ks) + x + navigate | S2 (w-count too slow) |
| 2 ge/gE | 3 ks | ge (1 ks) + combat | S1 (wall strip) |
| 3 G/gg | 5 ks | G(1)+x(1)+gg(2)+l(1) | S1 (full wall) + S2 (G) |
| 4 H/M/L | 7 ks | H x M x L x | joint S2 |
| 5 % | 3 ks | %(1) to the match + x + combat | S1 (bracket lock) |
| 6 }/{ | 3 ks | }(1)+j(1)+combat | S1 (void barrier) |
| 7 )/( | 4 ks | )/( to trigger sentence + $ + combat | S1 (wall-gap row) |

**Total simulated par ≈ 30 ks (recompute at build). Budget = ceil(30 × 1.4) = 42.**

### Immunity mechanism

The Warden Surveyor's phase seals gate phase transitions. Each phase's seal is positioned such
that:
- The terrain between the player's entry to that phase and the seal requires the Act II motion
  (S1 or S2 forcing as documented per phase above).
- `hjkl` are freely usable within each phase for micro-positioning.
- Act I motions used INSTEAD of Act II motions either cost ∞ (terrain wall/void) or strictly
  exceed the per-phase budget allocation.

### Primitives used

- `boss_seal` entities gating phase transitions (from the Warden's Keep boss pattern, `build_dungeon_wardens_keep`)
- `seal_door` at Phase 1 (opened by approaching from the W-navigated column)
- Code-WORD clusters (Phase 1: force W)
- Wall strip at row 4 cols 6–57 (Phase 2: S1 force ge/gE)
- Full WALL at row 8 (Phase 3: S1 force gg)
- KS-H/M/L at rows 11/13/15 (Phase 4: joint force HML)
- Full-width void barrier rows 19–21 (Phase 6: S1 force `}`)
- Fog on phase rooms until prior seal opens

### Self-check

- **Scope:** Boss — exercises every structural family taught in the act it caps (L6–L13). ✓
- **Linkage:** One phase per family — all seven: W/B/E; ge/gE; G/gg; H/M/L; `%`; `}`/`{`; `)`/`(`. ✓
- **Immunity clarification:** hjkl usable for nav; the act's structural motions required for phase triggers. ✓
- **S1 phases:** 2 (wall strip), 3 (full wall), 5 (bracket lock), 6 (void barrier), 7 (wall-gap row). ✓
- **S2 phases:** 1 (code-WORD density + tight phase budget), 4 (joint HML forcing). ✓
- **One motion family per phase:** ✓ — and `)`/`(` now have their own phase (7), matching the L13 lesson. ✓
