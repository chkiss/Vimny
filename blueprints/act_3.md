# Act III — Navigation Power Tools: Blueprints

> ⚠ **Pre-implementation design doc — obsolete conventions; delete-on-implement.** Uses pre-slug naming (e.g. `RuneCluster` → now `CharRun`; level numbers are now the cosmetic `display` field) — don't copy these symbols. **Delete a level's section when that level ships, and the whole file once its act is built.** See LEVELS_PLAN Part 8.

Level 17.1. Each level introduces at most 3 linked mechanics, budget-forces or
contextually teaches them, and is buildable from existing engine primitives (with
clearly flagged assumed extensions).

> **Shipped — sections removed (delete-on-implement):** L10 The Bracket Vaults,
> L15 The Seekers' Labyrinth, L16 The Waypoint Sanctum, L17 The Archivist's Library.
> Remaining below: L17.1.

---

## Level 17.1 — The Warden Pathfinder (ACT III BOSS)

> **AS BUILT (2026-06-07) — this supersedes the pillar/positional details below, which
> are kept for design history.** The code + `tests/test_warden_pathfinder.py` are the
> source of truth. Net of the playtest iterations:
> - **Arena = a big OPEN hall** with four stone columns at the 3×3 inner vertices
>   (`_PF_COLUMNS`) — the old "pillar grid" / "nine equal blocks" maze is gone.
> - **Impostors = a CROWD of false Wardens.** The hall opens to ~17 goblins all disguised
>   as the Warden (`tag='echo'`, a red `W` in a *spread of shades* centred on the boss's
>   own red; each carries a `shade` index). The entry banner reads **"You see a myriad of
>   Wardens!"** (the goblin count is suppressed). Each impostor has **2 HP**: the first
>   `x` **strips the disguise** ("the disguise sloughs away: just a goblin!") — it becomes
>   a plain `g` that `/W` no longer finds — and the second `x` kills it. An **AoE** (visual
>   delete) **unmasks** the impostors it covers the same way (live `g`, 1 HP) rather than
>   deleting them outright; a second sweep finishes them. The real Warden (visual-immune)
>   hides among them, and his **start cell is randomised** (~50%: swapped with a random
>   impostor) so he isn't always the central `W` — only `/W` + the visual-immunity tell find him.
> - **Mega-attack = an escalating floor-TEAR** (`engine/warden_mega.py`): `dd` → `d5k/d5j`
>   → `dG/dgg`, torn cells (`room.torn`) rendered as void and impassable, anyone caught
>   falls. After a few turns the Warden **pastes the floor back** — and on the paste he
>   **restores the minions the tear buried** AND **re-cloaks every live goblin as a 2-HP
>   false Warden** (`_paste_back`), so unmasked/half-cut minions revert between strikes.
>   (Not the old positional "safe-pillar" model.)
> - **Wardenverse = one long REACTIVELY-wrapping line** (no fixed fold; works 80–189 cols)
>   with sparse stone walls so `$`/`l` stop and `gj`/`gk` is the way across. The Warden
>   **walks/approaches** and **hits & is hit regardless of `:set wrap`** (wrap only matters
>   for *reaching* him). His death **collapses the verse** → back to the arena → clear the
>   minions → a **key** drops → opens the **treasure room** (heart + scroll + exit).

> **REVISED 2026-06-05.** Re-based on the current curriculum (previous boss is
> `warden_surveyor` 13.1, so **Act III = L14–L17**), structured as **two acts**, around
> vim *composition* and the real Warden AI. Directives:
> 1. **Force every Act III command** — visual `v`, search `/ * n N`, marks `m ' \``,
>    `:e`/`:e!`, `:set wrap`/`nowrap`, `gj`/`gk`, `:w`.
> 2. **Commands compose; let the player feel powerful.** `v/W⏎x` is ONE command
>    (visual + search-as-motion + delete) — a remote AoE that erases the whole span. The
>    level embraces this, never special-cases an op, and adds no magic-word gates.
> 3. **Bosses are immune to visual-delete** — the rule that keeps the AoE from
>    trivializing the fight; the core is *chipped*, not one-shot.
> 4. **Match the real Warden AI** — Wardens leap (`_do_warden_move`, 2–6 rows, shield
>    flips to the player's side) and sweep (`_ws_erase_row`). Combat previews Act IV by
>    escalating the sweep into a telegraphed `dd`/`p` cut-and-rebuild.

**Act III commands this boss caps:**

| Level | Command | Forced in |
|-------|---------|-----------|
| L14 Sight Sanctum | visual `v` (composed: `v/W⏎x`) | Act 1 — AoE + the Hunt |
| L15 Seekers' Labyrinth | `/` `*` `n` `N` | Act 1 — the Hunt + relocating the leaping Warden |
| L16 Waypoint Sanctum | marks `m ' \`` (2–4) | Act 1 — pillar-refuge vs. the mega-attack |
| L17 Archivist's Library | `:e`, `:set wrap`/`nowrap`, `gj`/`gk`, `:e!`, `:w` | Act 2 — the Verse finale |

**Structure (revised 2026-06-05):** Act 1 is the arena — strip the Warden's shields
(visual + the Hunt) while surviving his leap/swarm-summons/mega-attacks with pillar-marks.
Shields down → he flees into the **wardenverse**. Act 2 — `:e wardenverse` into ONE long
line that **wraps reactively to the terminal** (like the Library; no fixed fold, works
80–189 cols): he *runs the wrapped line*, chased with `gj`/`gk` while `:set wrap` is on and
**stilled by `:set nowrap`** (focus-break); `x` him down. His death **collapses the verse**
and flings you back to the arena. Act 3 — mop up the leftover minions; when the verse has
collapsed AND the last goblin is dead, the **key clatters to the floor** → opens the
**locked treasure room** (loot + the exit). The verse has no exit of its own.

---

### The one rule that makes it work: bosses are immune to visual-delete

`v/W⏎x` composes (`main.py:2325` — a search from visual mode extends the selection) and
deletes the whole span. But `_kill_entities_in_span` (`engine/visual.py:59`) currently
kills *every* entity in a visual span except `{exit, door, boss_seal}` — so today a single
`v$x` would **one-shot the Warden**. Fix: **a boss core is visual-delete-immune** (add
`warden`/a boss flag to the protected kinds). Then:

- **`v/W⏎x` is the player's power tool** — a remote AoE that wipes summoned goblins, erases
  floor glyphs, and shaves a lane across the whole selected span. The player is *meant* to
  enjoy deleting huge chunks of the room.
- **The boss core survives any visual sweep** and is wounded only by **normal-mode `x`**
  (the established combat) from its open flank. When a `v`-delete span *contains* the
  Warden, everything else in the span dies, the Warden stands, and a message fires:
  **"The Warden's shield defended him from your cut!"** — the immunity reads as a parry.

> **CHALLENGE C-PF-1 — DONE (2026-06-05).** Implemented as a per-entity
> `Entity.edit_immune` flag (opt-in; zero risk to shipped bosses). Guarded at every
> editing-delete chokepoint — `_delete_cols` (charwise/block), `remove_row` (linewise/dd),
> and `_kill_entities_in_span` (visual). `apply_visual` sets `player.last_parry` when a
> delete span covers an immune boss; `main.py` then emits **"The Warden's shield defended
> him from your cut!"** Note: the *existing* `_PROTECTED_KINDS` check was already dead on
> the delete path (`_delete_cols` removed entities first) — this is the real fix. Tests:
> `tests/test_warden_pathfinder.py` (all 4 visual paths + AoE-still-clears-chaff + yank).

---

### The Warden — movement & combat (inherit the real AI; preview Act IV)

- **Leap (`_do_warden_move`):** bounds to a random open row 2–6 away; `_reposition_warden_shield`
  **flips its shield to the side facing the player.** Often lands off-screen → `/W` to
  relocate it (search teleport).
- **Summon:** 2 chasing goblins every ~6 turns within radius 5 — the chaff your `v/W⏎x`
  AoE is for.
- **Sweep (`_ws_erase_row` / `_ws_threat_span`):** a `v$`/`v0` sweep from itself to the
  player-side edge, erasing that row's glyphs/floor.
- **Mega-attack (new, telegraphed; Act IV preview; ACT 1 ONLY):** idle (8t) → warn (3t,
  banner *"THE WARDEN INHALES THE FLOOR — only the lit stones will hold!"*) → strike. The
  strike "tears the floor away and slams it back" — flavor of `dd` then `p`/`P`. Mechanically
  it is **positional** (no terrain mutation — there is no VOID cell type, and this keeps
  marks/the grid stable): anyone NOT on a **safe pillar** takes fall damage and goblins off
  the stones are culled. Only a **rotating subset** of pillars is safe each cycle — the
  telegraph lights them green — so one refuge is never enough. (Stops once he flees to the
  verse — there he is vulnerable, not rampaging.)

> **CHALLENGE C-PF-2:** Mega-attack timer (flash → `remove_row` → `p`/`P`) layered on the
> existing leap + sweep; never delete a shield, the verse door, or the exit; pillars carry
> an immune flag. Tuning: cadence (8/3 a guess), swath size.

---

### Room layout (top-down)

**Arena — normal multi-line grid, 24 rows × 78 cols (≈23 real linebreaks).** The Warden
leaps around behind its flipping shield; the floor carries a **symmetric grid of pillars
`▣`** (refuge stones, out of `x` range of the Warden). West door = entrance; east door =
the Warden's escape into the verse. Pillars are laid out on a regular lattice (e.g. every
6th column × every 4th row), NOT scattered:

```
 #########################################################################
 #     ▣      ▣      ▣      ▣      ▣      ▣      ▣      ▣      ▣      ▣     #
 #  W(imp)        W(imp)         [ W ] shield→▒        W(imp)             #
[W]ENTER ▣      ▣      ▣      ▣      ▣      ▣      ▣      ▣      ▣  [VERSE]E
 #                W(imp)                       W(imp)                     #
 #     ▣      ▣      ▣      ▣      ▣      ▣      ▣      ▣      ▣      ▣     #
 #########################################################################
```
(each cycle the telegraph lights one row/handful of these stones green — jump to a lit one)

**Verse file — a SEPARATE buffer reached by `:e warden.verse`: one logical line, ~300
cols, NO linebreaks, with stone-wall glyphs embedded along it.** Every on-screen row is a
soft-`wrap` display row, not a real line (`wrap_buffer=True`, `rows==1`; opens `nowrap`).
The only place `:set wrap`/`gj`/`gk` do anything. `:e` is forward progress, not a side-trip.

So: **arena = real linebreaks; verse = pure wrap, a different file.**

---

### Act 1 — The Arena: visual + search + marks (strip the shields, survive)

The Warden leaps, flips its shield to your side, summons goblins, sweeps rows, and — from
the first chip — launches telegraphed **mega-attacks**. So marks are live immediately.

- **The AoE (visual):** `v/W⏎x` (or `v$x`, `v0x`) wipes summoned goblins and shaves glyphs
  across the span — crowd control and clearing a lane to the Warden's open flank.
- **The Hunt (search):** the Warden hides among impostors. **All of them — impostors and
  the real Warden — are uppercase `W`**, so `/W` matches *every* one (faithful; there is NO
  lowercase-`w`-renders-as-`W` cheat). Impostors are simply a **different color** — a
  cosmetic tell, never a search difference. `v/W⏎x` across the cluster deletes the colored
  impostors; **the one `W` left standing is the real Warden** (visual-immune, with the
  "shield defended him from your cut!" message). `/W` + `n`/`N` also cycles matches; when he
  leaps off-screen, `/W` snaps you to him.
- **Marks (survival):** pillars `▣` sit in a **symmetric grid** across the arena; only a
  rotating subset is safe each cycle (lit green by the telegraph). The 3-turn warning is too
  short to *walk* to the safe one, so you **bank `ma`/`mb`/… on the grid's pillars early**
  and `` ` ``-jump to whichever is lit (the safe set rotates → one mark isn't enough).
  Between cycles, reposition to the Warden's **unguarded side** (shield flipped away) and
  `x` to chip a shield/HP.
- **Shields down → he flees.** Once stripped of protection, the Warden bolts through the
  **east door into his verse**, vulnerable. Act 1 ends.

### Act 2 — The Verse file (the chase-corner KILL): `:e`, `:set wrap`/`nowrap`, `gj`/`gk`, `:e!`, `:w`

The player **`:e warden.verse`** to follow into the one-line wrap buffer (opens `nowrap`;
the Warden is off down the line, walled off). The verse line has **stone-wall glyphs
embedded along it** — the crux of the toggle:

- **`:set wrap` + `gj`/`gk` (ATTACK):** wrap folds the line into display rows; `j`/`k` are
  inert (one logical line), and **`gj`/`gk` move you vertically across display rows, routing
  *around* the in-line stone walls** — the only way to close on the Warden. Shields down, so
  `x` on him now lands. (The single spot in the game where `gj`/`gk` is unavoidable —
  cements the motion earned at the end of L17.)
- **Without wrap:** horizontal motions (`F`/`f`/`/`/`l`) toward him **stop dead at the stone
  walls** — you cannot reach him in `nowrap`.
- **`:set nowrap` (DEFEND):** collapsing the verse **breaks the Warden's focus → he cannot
  attack.** The fight is a toggle: `nowrap` to survive his telegraphed sweep, `wrap` to
  resume the `gj`/`gk` approach and `x` him.
- **`:e!` (reset):** a mistaken edit while dodging corrupts the verse; `:e!` reloads clean.
- **`:w` (the kill):** corner him at the line-end, land the finishing `x`, and `:w` seals
  the file — the Warden falls and the level is won. He is vulnerable and you are on the
  chase; there is no further phase.

---

### Par and budget (estimate — confirm with solver)

| Act | Par | Notes |
|-----|-----|-------|
| 1 arena | ~52 | `v/W⏎x` sweeps + Hunt, bank `ma`–`md`, survive ~2–3 mega-cycles, chip shields |
| 2 verse | ~35 | `:e` + wrap/`gj`/`gk` chase + `nowrap` dodges + `x` + `:w` |
| transitions | ~10 | door traversals |

**Par ≈ 97 → Budget ceil(97 × 1.4) = 136.** (Estimate; mark/visual-aware solver or a
hardcoded par must confirm.)

---

### Forcing / Teaching argument

- **Visual + search (composed):** goblin chaff + the colored-impostor cluster reward
  `v/W⏎x`; boss visual-immunity makes "the survivor is real" the natural Hunt; a leaping,
  off-screen Warden makes `/W` the cheap relocator.
- **Marks:** pillars are the only mega-attack-safe cells, scattered, 3-turn warning too
  short to walk between → pre-set marks + `` ` ``-jumps, rotating safe set forcing **2–4**.
- **`:e` + wrap + `gj`/`gk` + nowrap:** the Warden flees to a *different file* → `:e`; one
  logical line walled along its length → `j`/`k` inert and horizontal motions blocked, so
  `gj`/`gk` are the only approach; his sweep is lethal → `:set nowrap` breaks his focus.
- **Act IV preview:** the mega-attack cuts (`dd`) and pastes (`p`/`P`) the arena.

---

### Primitives & challenges

Act III primitives are **shipped** (visual L14; `/ * n N`+teleport L15; marks L16;
`:e`/`:e!`/`:set wrap`/`nowrap`/`gj`/`gk`/`:w` L17; Warden leap + `v`-sweep). The boss adds:

| Item | Where | Status | Notes |
|------|-------|--------|-------|
| Boss immune to visual-delete + parry message | all | **C-PF-1** | Keeps `v/W⏎x` from one-shotting the boss; core chipped by `x`. |
| Mega-attack + pillar refuges | Act 1 | **C-PF-2/4 — DONE (2026-06-05)** | `engine/warden_mega.py`: idle(8t)→warn(3t)→strike cadence; strike damages anyone off a **safe pillar** (`take_damage 4`) and culls goblins; positional (no terrain mutation — there is no VOID cell type, and it keeps marks/grid stable). Only a rotating subset of pillars is **safe** each cycle (telegraph lights them green, `C.mega_safe_bg`) → forces 2–4 marks. Wired in `_enemy_tick`; tests in `test_warden_pathfinder.py`. **Pillar PLACEMENT (builder) must be a symmetric grid, not scatter.** |
| Impostor `W`s by color (not by glyph) | Act 1 | **C-PF-3 — DONE (2026-06-05; crowd+reveal 2026-06-07)** | Impostor = `goblin` `tag='echo'`, **2 HP**, rendered `boss_echo_fg(shade)` `W` in a *spread of shades* (`_ECHO_SHADES`) centred on the boss red; `Entity.shade` picks the variant. ~17 of them → entry banner **"You see a myriad of Wardens!"** (goblin count suppressed). First `x` strips the disguise (`tag→''`, becomes a plain `g`); second `x` kills. Room flag `search_glyph_entities` overlays glyphs so `/W` finds the Warden + still-disguised echoes wherever they leap (default off → par identical). Real one is visual-immune. Tests **C-PF-3/4** in `test_warden_pathfinder.py`. |
| Pillar (`▣`) glyphs placed in a **symmetric grid** | Act 1 | folded into C-PF-2/4 / builder | `▣` char-runs at the grid cells + the same coords in `room.pillars`; geometry keeps the Warden out of `x`-range. Grid/symmetric, NOT random scatter. |
| `:e wardenverse` chase into a 2nd `wrap_buffer` room; in-line walls; `nowrap` focus-break | Act 2 | **C-PF-5 — DONE (2026-06-05)** | Verse is a 2nd `Room` (`Dungeon.rooms[1]`); `:e wardenverse` switches `current_room` once `room.warden_fled`. In-line `WALL` cells block `h`/`l`/`F`/`/` (gj/gk route around); the verse Warden (`tag='verse'`, `edit_immune`) attacks only while `player.wrap`. Flee hook + message in the `x`-combat. **Provisional: par/budget, verse wall spacing, and combat balance need playtesting.** |
| Builder `build_dungeon_warden_pathfinder` (two rooms, grid pillars) | both | **DONE (2026-06-05)** | `generation/dungeon_gen.py` (`_PF_*` constants). 24×78 arena + 1×120 verse. Structural test in `test_warden_pathfinder.py`. par=None/budget provisional. |
| `warden_phase_immune` on Entity | all | prior draft | Blocks Act II long-range motions in tight spots. |

---

### Self-check

- (1) Scope: all four Act III commands + Act IV cut/paste preview, in two acts. Pass.
- (2) Linkage: visual→L14, search→L15, marks→L16, `:e`/wrap/`gj`/`gk`→L17. Pass.
- (3) Faithfulness: `v` and `/` compose freely, never special-cased; impostors differ by
  color not glyph; only rule is boss visual-immunity; no magic-word gates. Pass.
- (4) Real AI: Warden leaps + flips shield + sweeps (inherited), not stationary. Pass.
- (5) Marks live from the start; verse is the forward chase-finale (no return); `:set
  nowrap` & `gj`/`gk` each unavoidable. Pass.
- (6) Boss caps Act III at 17.1, well-spaced after 13.1. Pass — pending C-PF-1..5.

---
