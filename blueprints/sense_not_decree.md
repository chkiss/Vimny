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
arena strands (famous fragments — stitch in time, cry "wolf", (x) marks the
spot, {silver} lining, <q>et tu</q>, veni. vidi. vici.).

---

## 1. Hall of Echoes (47, macros) — SEED-RANDOMIZED SONG POOL

Five near-identical rows, DISTINCT last word each, one macro mended down
the hall. Draw one song per seed from a pool of FIVE template-verse sets
(pool entries must share: 5 rows, same blight positions, same mend
keystrokes, so par is pool-invariant — pad/choose variants accordingly):
1. **Old MacDonald** — 'And on that farm he had a {cow|pig|duck|horse|sheep}, E-I-E-I-O.'
2. **Twelve Days gift list** — 'five gold rings' / 'four calling birds' /
   'three French hens' / 'two turtle doves' / 'and a partridge…' (secular
   list lines only).
3. **This Old Man** — 'He played knick-knack on my {thumb|shoe|knee|door|hive}.'
4. **One, Two, Buckle My Shoe** — 'one, two, buckle my shoe' / 'three,
   four, knock at the door' / 'five, six, pick up sticks' / 'seven, eight,
   lay them straight' / 'nine, ten, a big fat hen'.
5. **Solomon Grundy** — 'born on a Monday' / 'christened on Tuesday' /
   'married on Wednesday' / 'took ill on Thursday' / 'buried on Sunday'.
Blight: identical junk+◆ stamped into each row (the existing two-part-mend
law). Constraint: the macro body must be position-independent across all
five sets (leading ^, daw+x as today).

## 2. The proverb family (23-25 change levels + 30 sight + 32-38 enclosures) — ALL

One shared pattern: each door = a famous proverb misquoted by ONE word;
the cure is the word everyone knows. Seed-randomized from a proverb pool
FILTERED BY CURE LENGTH (pars must stay seed-invariant: pool entries keyed
by (cure_len, object_type)). Starter pool: a stitch in time saves nine ·
look before you leap · the early bird catches the worm · a watched pot
never boils · too many cooks spoil the broth · actions speak louder than
words · better late than never · practice makes perfect · birds of a
feather flock together · a rolling stone gathers no moss · strike while
the iron is hot · all that glitters is not gold · many hands make light
work · honesty is the best policy · curiosity killed the cat. Per level:
- 23-25 (ce/cc/S/C/R): whole-word/line miswrites of proverbs.
- 30 (visual): the corrupt span inside a proverb.
- 32 iw/aw: the wrong word; 33-34 brackets/braces: '(the worm)' style
  asides; 35 quotes: the misquote INSIDE quotation marks (the natural
  home); 36 it: '<title>look before you leap</title>'; 37 is: two-sentence
  proverbs ('Look before you leap. …'); 38 ip: a whole proverb stanza.

## 3. Sculpting Chambers (24, o/O/A/I) — ROW YOUR BOAT

The half-cut votive becomes 'Row, row, row your boat, / gently down the
stream, / merrily, merrily, merrily, merrily, / life is but a dream.'
Typed inserts complete a verse the player knows; 'merrily ×4' is the A/
append beat. Fixed text → hand-tallied par (typed lengths change: full
re-derivation + rival audit).

## 4. Spellwright's Forge (39, :s) — OPTIONS (user: London Bridge materials alone is weak)

Pick per-chamber from:
a. **Old MacDonald wrong-sound** (strongest): a duck verse written with
   'moo' throughout → `:s/moo/quack/g` — everyone knows the fix; the /g
   flag is five moos on one line. A protected cow verse KEEPS its moos
   (the :%s trap, by sense).
b. **For Want of a Nail** (proverb-famous chain): nail→shoe→horse→rider→
   message→battle→kingdom; a verse written with the WRONG want mended by
   :s; the chain orders the replacements.
c. London Bridge material verses (wood and clay → bricks and mortar →
   iron and steel → silver and gold) — one of many, ties to L42.
d. **Hickory Dickory Dock** — 'the mouse ran UP the clock' / 'ran down':
   small, single-word, good for the & repeat chamber.

## 5. Echo Vault (the `.` level) — OPTIONS

One blight stamped down the hall; the dot repeats one mend. Candidates
(exact repeated line = the dot's natural text):
a. **Hot cross buns** — 'Hot cross buns!' ×2 + 'one a penny, two a penny'.
b. **Rain, rain, go away** — 'rain, rain, go away, / come again another
   day' (repeat the couplet down the hall).
c. **Ten green bottles** — each verse repeats its bottle line twice.
d. London Bridge 'falling down, falling down' rows.

## 6. Wet Ink (46, gi) — OPTIONS

The four ledge words become a FOUR-WORD PD proverb typed with i/gi:
a. 'better late than never'  b. 'easy come, easy go'
c. 'no pain, no gain'        d. 'first come, first served'
e. 'live and let live'
Note: typed length sets par — either pin ONE phrase (fixed par) or draw
from the pool and compute par per phrase at build (room.par is per-room;
tests adapt). Brazier word-prefix fuel-gate keys on the words — verify
prefix-uniqueness per phrase.

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
