# Sense, Not Decree — the famous-text program

> Design law (user, 2026-07-19): puzzle texts should be WELL-KNOWN,
> PUBLIC-DOMAIN verse/prose whose STRUCTURE is the solution — the player
> repairs a text they know by heart, and the plaque demotes from decree to
> confirmation. Copyrighted texts (Beatles, Wheels on the Bus, …) are
> REFUSED; religious texts avoided. Every conversion is a mini-rebuild:
> fixed (or pool-drawn) text → re-derived par → rival re-audit → karaoke.
> Delete each section when it ships.

**Shipped so far:** L40 Culling Ledger (House That Jack Built), L41 Shelving
Room (Frère Jacques, French), L42 Refrain Vault (London Bridge), 38.1
arena strands (famous fragments), and the 2026-07-19 batch (commits
0a1a364..817f027): §1 Hall of Echoes (five-song pool: Old MacDonald /
Mulberry Bush / London Bridge / Hush Little Baby / Solomon Grundy — every
entry the shape `a junk b ◆tail`, macro + par pool-invariant), §3
Sculpting Chambers (Row Your Boat's one-word-per-line skeleton — the
karaoke no-space law rules out full lines), §4 Spellwright's Forge (duck
moos :%s//g · hickory dickory's protected 'ran down' :s+& · ten green
bottles :g/falls/d), §5 Echo Vault ('she sells sea shells' + 'humpty
dumpty'; the digit beat stays mechanical — no song supplies a lone digit
plus its tripled twin), §6 Wet Ink ('live and let live' / 'easy come easy
go', both 14 typed letters → pool-invariant par), and §2 for displays
30 + 32-38 (see below).

---

## 2. The proverb family — SHIPPED 2026-07-19 for 30 + 32-38 (commits
0a1a364..fc03719): shared pool `content/proverbs.py` (PLAIN word-tuples +
MISQUOTES keyed by cure length); THE ANCHOR LAW — par invariance is
COLUMN-anchored, not text-anchored: the corrupt/intruder word starts at a
fixed slot column, the saying's prefix right-aligns west (rival tapes
rebuilt anchor-relative). West plaque bands dropped everywhere (the
player's memory is the plaque). 30 = sayings interrupted by rot-spans,
restored whole (case chamber = flipped middles; fixed 6-cell flip-2 pool
keeps the rival in the standard budget). 38 = the goblins' Twelve Days
plunder-tally (11/12 gift lines). 37's C3 = veni/vidi/vici +
live/laugh/love (fixed, cures typed by heart; the vidi strand returns at
the Grandmaster — deliberate callback).

**Change levels SHIPPED 2026-07-19 (second pass)**: 22 Change Annex (fixed
door table `_WLA_DOORS`; carved saying prefixes in the west stone replace
the decree plaques; the long cE doors are SCRAMBLED FAMOUS COMPOUNDS —
to-do-well / ending-never road / round-go-merry ride, each with a kept
tail word barring the ce+retype substring false-open; rune doors = saves
◆ne → ni, makes ◆rfect → pe; par 106→101), 23 Change Extension (`_CE_DOORS`
— the S→C alignment law holds because every S cure is exactly 6 letters:
policy/golden/grease; ceol = kept 4-letter floor word + junk tail → C
news/tell/words; ★-scars ir★n / co★ks; ◆ep→deep, ◆ord→sword; (al)gether →
c% to; par computed 86), 25 Overwrite Halls (`_OH_LESSONS` — floor
last-words rotted: believing/waste/earned/twice/silver; the corrupt
positions preserve the F-anchored landing chain, par 30 intact).

## 7. Grandmaster's Sanctum strands — SHIPPED 2026-07-19 (see header).
Explore later: gallery-bay targets (the proving gallery) joining the
proverb family; more fragment options (all's well that ends well (is),
"friends, romans" (i"), <b>the die is cast</b> (it)).

## 8. The Gauntlet (48) — THE KNOWN-TEXT EXAM (user overruled my exception)

Direction: the whole exam repairs ONE famous poem the player knows — one
line per door, each carrying a different corruption class (case, intruder
word, bracket, tag, join, duplicate line, …); "highly rewarding to do so
many edits to repair a text you know." Candidate texts (need ~16 short
lines, extremely famous, PD): **The Tyger** (Blake — 'Tyger Tyger, burning
bright' — quatrains, short lines, famous opening) · **Ozymandias**
(Shelley, 14 lines) · **Jabberwocky** (Carroll — universally known AND its
nonsense words make corruption spotting a delight; googleable) · Twinkle
Twinkle (all five stanzas, less known past stanza 1). Constraints to
re-audit: plaque column stays (the exam's format), but now reads as the
poem; every door's forcing geometry (thresholds, waterworks, left-align
law) must survive fixed text; par fully re-derived. BIG rebuild — its own
session.

## 9. Buried Word (45, g*) + Last Reach (44, g_) — TONGUE TWISTERS (user overruled)

Familiarity strengthens the */# mechanic IF the fit respects the forcing:
- **Buried Word** (g* = substring-in-word): 'How much wood would a
  woodchuck chuck…' — g* on 'chuck' finds woodCHUCK; 'She sells seashells
  by the seashore' — 'sea' buried in seashells/seashore; 'Peter Piper
  picked a peck of pickled peppers' — 'pick' inside picked/pickled. The
  corrupt-char-before-the-buried-word geometry (r-repair + n/l stepping)
  must be re-laid per twister; lines are long (good: counted-e stays
  2-digit, g_ pays 2).
- **Last Reach** (g_ vs $-drown): the same twisters as the long verse rows
  running east into water — their length is the forcing.

Suggested build order: 2 (one chassis, widest) → 1 → 5 → 6 → 4 → 3 → 9 → 8
(the exam last, biggest). Each ships with the standard re-audit
(canonical/par/rivals/karaoke/fog).
