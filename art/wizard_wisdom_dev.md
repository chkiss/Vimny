# Wizard Wisdom — Dev Worksheet

## Voice & Theme

The poems speak in the voice of someone who's walked these halls a hundred
times and isn't in a hurry — an old wizard who built this dungeon and still
finds it delightful. Vim commands aren't dramatic spells; they're techniques,
the way a carpenter reaches for the right tool without looking. He's earnest
about it, old-fashioned, genuinely pleased when a mechanic clicks. The dungeon
is amber-lit and warm, not threatening — lantern stone and slow breath, not
thunder and revelation. Language stays tactile: stride, step, stone, lantern.
Aphoristic — something you'd write on a notecard and pin above your desk. Each
poem should leave a mnemonic image behind, the command fused to the feeling of
using it. No grandeur. Just warm precision.

---

Each blessing slot fires after a level is completed and introduces the commands
the player will use in the very next level — the lesson arrives right before it
is needed, not far in advance. Lines must be ≤ 48 chars (the wizard's box inner
width). When a poem is finalised, update the corresponding entry in
`wizard_wisdom.txt`.

---

## How slots are numbered

`select_next_lesson_quote(completed_id)` finds the ordinal position of the
completed level in the visible LEVELS list and adds 1 → `wisdom_idx`.
A poem fires when `q['level'] == wisdom_idx` in the JSON corpus.

```
Ord  Completed level             Commands              wisdom_idx → introduces
 0   id=0   The First Cave        h j k l              → w[1]  ^ $ 0
 1   id=1   The Line Halls        ^ $ 0  :w :q :q!     → w[2]  [count]
 2   id=11  The Reliquary         hjkl ^ $ 0           → w[3]  w b e
 3   id=2   The Counting Crypts   [count] prefix       → w[4]  w b e
 4   id=3   The Rune Halls        w b e                → w[5]  f F t T
 5   id=4   The Character Cat.    f F t T              → w[6]  ; ,
 6   id=5   The Goblin Gauntlet   ; ,                  → w[7]  v
 7   id=51  The Warden's Keep     (boss)               → w[8]  v/V/Ctrl-V
 8   id=6   The Warden's Prec.    v                    → w[9]  W B E
 9   id=7   The WORD Forge        W B E                → w[10] ge gE
10   id=8   The Backward Vaults   ge gE                → w[11] G gg {n}G
11   id=9   The File Vaults       G gg                 → w[12] H M L
12   id=10  The Screen Vault      H M L                → w[13] %
13   id=12  The Bracket Vaults    %                    → w[14] } { ) (
14   id=13  The Runic Archives    } { ) (              → w[15] i a I A
15   id=14  The Inscription Halls  i a I A              → w[16] o O s S
16   id=15  The Sculpting Chambers o O s S             → w[17] (generic)
17   id=151 The Warden Unbound    (boss)               → w[18] d c
18   id=16  The Operator's Vault  d c                  → w[19] dd cc
19   id=17  The Whole-Line Annex  dd cc                → w[20] u Ctrl-R
20   id=18  The Undo Sanctum      u Ctrl-R             → w[21] (generic)
21   id=19  The Word Chiseler     dw de db ...         → w[22] (generic)
22   id=20  The Delimiter Chamber dt df dT dF          → w[23] (generic)
23   id=21  The Line-Edge Hall    d$ D d0 d^           → w[24] (generic)
24   id=22  The File Sweep        dG dgg               → w[25] y yy
25   id=23  The Yank Vault        y yy                 → w[26] p P
26   id=24  The Paste Halls       p P                  → w[27] (generic)
27   id=25  The Fine Liftmaster   yw ye y$             → w[28] (generic)
28   id=26  The Change Corridor   cw ce cb             → w[29] (generic)
29   id=27  The Delimiter Change  ct cf cT cF          → w[30] (generic)
30   id=271 The Warden Manifold   (boss)               → w[31] r R
31   id=28  The Overwrite Halls   r R                  → w[32] ~
32   id=29  The Case Chambers     ~                    → w[33] .
33   id=30  The Echo Vault        .                    → w[34] (generic)
34   id=31  The Case Operator Halls g~ gU gu           → w[35] (generic)
35   id=32  The Join Corridor     J gJ                 → w[36] (generic)
36   id=33  The Indent Halls      >> <<                → w[37] (generic)
37   id=34  The Operator Indent   >{m} <{m} =          → w[38] (generic)
38   id=341 The Warden Scrivener  (boss)               → w[39] text objects
```

---

## w[1] — after The First Cave → introduces The Line Halls (^ $ 0  :w :q)
**STATUS: ✓ KEEP**

```
 $ jumps to the distant wall—far as eye can see.
           0 returns you to the start.
            ^ hops to the first rune.
    $, 0, ^. Three steeds run swift and true.
```

---

## w[2] — after The Line Halls → introduces The Counting Crypts ([count] prefix)
**STATUS: ✓ KEEP "counts" | ACTION: change "save and quit" level field 2 → 1**

### counts ✓ KEEP
```
    	  Numbers are rapid spells.
	5j glides five paces in two.
            Count once, walk once.
    Apprise, your breath steady, and leap!
```

### save and quit — ACTION PENDING: change level:2 → level:1 in wizard_wisdom.txt
The poem is correct — :w/:q IS level 1 content. Changing its level field keeps it
in the title screen pool (appears once level 1 is unlocked) and makes it a second
w[1] blessing option alongside "line motions". It just shouldn't be at w[2].

### x — keep as secondary (level:2 is fine, it's a minor unlock at that level)
```
      x clears a glyph under your lantern.
   An instant undoing, like dust brushed away.
```

---

## w[3] — after The Reliquary → introduces The Rune Halls (w b e)
**STATUS: ✓ KEEP**

```
  w skips a rune ahead, b back one, e to end.
      Ride  on words like stepping stones,
         Vim to seek the words to bend.
```

---

## w[4] — after The Counting Crypts → introduces The Rune Halls (w b e)
**STATUS: ✓ FINALIZED**

```
w steps to the next word's first stone.
b walks that same path home again.
e reaches across to the far edge—
three strides, and the river's crossed.
```

---

## w[5] — after The Rune Halls → introduces The Character Cataracts (f F t T)
**STATUS: ✓ FINALIZED**

```
fx lands square on the letter you name.
tx halts a breath before it stands.
F and T walk the same hunt backward.
Name your mark; the rest is in your hands.
```

---

## w[6] — after The Character Cataracts → introduces The Goblin Gauntlet (; ,)
**STATUS: ✓ FINALIZED**

```
Name your letter the once.
; walks that find on down the line.
, turns on its heel and comes back.
The hunt remembers; you needn't.
```

---

## w[7] — after The Goblin Gauntlet → introduces The Warden's Precision (v)
**STATUS: ✓ FINALIZED**

```
v opens the eye and it follows you.
Move, and the trail glows behind—
all it crosses, held until you act.
```

---

## w[8] — after The Warden's Keep (boss) → introduces The Warden's Precision (v)
**STATUS: ✓ FINALIZED**

```
v for a span of letters, V for lines,
Ctrl-V for a tower, column-straight.
Choose the shape that fits your work;
the verb that follows does not care.
```

---

## w[9] — after The Warden's Precision → introduces The WORD Forge (W B E)
**STATUS: ✓ FINALIZED**

```
w minds each comma, dot, and dash;
W strides past them in a single bound.
B walks it backward, E to the end—
the bolder path across the ground.
```

---

## w[10] — after The WORD Forge → introduces The Backward Vaults (ge gE)
**STATUS: ✓ FINALIZED**

```
e reaches the end of the next word.
ge looks back to where the last word ended.
Same landing, opposite direction.
gE the wide step: whitespace to whitespace.
```

---

## w[11] — after The Backward Vaults → introduces Level 9 (G gg {n}G)
**STATUS: ✓ FINALIZED**

```
gg: two soft steps to the top stone.
G: one long fall to the cellar floor.
Set a number first, and G lands there.
Top, bottom, and every rung you name.
```

---

## w[12] — after The File Vaults (id=9) → introduces The Screen Vault (H M L)
**STATUS: ✓ FINALIZED**

```
H: the high stone at the crest.
M: the middle, without counting.
L: the low stone at the base.
No rows to tally; just point and land.
```

---

## w[13] — after The Screen Vault (id=10) → introduces The Bracket Vaults (%)
**STATUS: ✓ FINALIZED**

```
% finds the bracket's other half.
Open calls to close; close to open.
Stand on either; one step to the mirror.
```

---

## w[14] — after The Bracket Vaults (id=12) → introduces The Runic Archives (} { ) ()
**STATUS: ✓ FINALIZED**

```
} leaps the blank to the next block.
{ walks it back again.
) and ( move between sentence ends.
Paragraphs and sentences, both jump.
```

---

## w[15] — after The Runic Archives (id=13) → introduces The Inscription Halls (i a I A)
**STATUS: ✓ FINALIZED**

```
i opens just before the cursor stands.
a opens just after—one step in.
I leaps to the line's first stone;
A to the last. Four doors, one room.
```

---

## w[16] — after The Inscription Halls (id=14) → introduces The Sculpting Chambers (o O s S)
**STATUS: ✓ FINALIZED**

```
o opens a new line below and listens.
O opens one just above.
s swaps what's under for what you'll write.
S clears the line—start fresh.
```

---

## w[18] — after The Warden Unbound (id=141, boss) → introduces The Operator's Vault (d c)
**STATUS: ✓ FINALIZED**

```
d cuts the letters the motion would cross.
c cuts, then opens for what you'll write.
Two operators; one grammar.
Motion names the range—the verb does the rest.
```

---

## w[19] — after The Operator's Vault (id=15) → introduces The Whole-Line Annex (dd cc)
**STATUS: ✓ FINALIZED**

```
Double the letter: the whole line answers.
dd clears the row; cc clears and waits.
One stroke for the span you stand on.
The motion already knew which row.
```

---

## w[20] — after The Whole-Line Annex (id=155) → introduces The Undo Sanctum (u Ctrl-R)
**STATUS: ✓ FINALIZED**

```
u walks the last change back.
Ctrl-R brings it forward again.
Not defeat—the tool that lets you try.
Take the bold step; undo it if you must.
```

---

## w[25] — after The File Sweep (id=20) → introduces The Yank Vault (y yy)
**STATUS: ✓ FINALIZED**

```
y lifts the letters the motion would cross.
Nothing is cut; the stone stays in place.
yy takes the whole line in one reach.
What's lifted lives in the register.
```

---

## w[26] — after The Yank Vault (id=21) → introduces The Paste Halls (p P)
**STATUS: ✓ FINALIZED**

```
p sets the lifted weight just past the cursor.
P lays it one step before.
What y gathered, p places.
Move first; then press once.
```

---

## w[31] — after The Warden Manifold (id=251, boss) → introduces The Overwrite Halls (r R)
**STATUS: ✓ FINALIZED**

```
r names the replacement; the cursor stays.
R walks the line and overwrites as it goes.
One letter wrong, or a whole run:
pick the shape that fits.
```

---

## w[32] — after The Overwrite Halls (id=26) → introduces The Case Chambers (~)
**STATUS: ✓ FINALIZED**

```
~ turns the lamp on the letter below:
small to tall, tall to small, one step.
Count it — 3~ flips three in one reach.
Case bends; the cursor walks on.
```

---

## w[33] — after The Case Chambers (id=27) → introduces The Echo Vault (.)
**STATUS: ✓ FINALIZED**

```
. is memory; it forgets nothing.
Whatever you changed last—it holds the shape.
Move to the next place and press once.
The same hand falls again.
```

---

## w[39] — after The Warden Scrivener (id=321, boss) → introduces text objects (iw aw i( ...)
**STATUS: ✓ FINALIZED**

```
Stand anywhere inside a word—
ciw still changes the whole thing.
i for the flesh, a for the skin.
Name the shape; the rest is done.
```

---

## Summary of changes to wizard_wisdom.txt

| Slot | Action | Status |
|------|--------|--------|
| w[2] "save and quit" | level field: 2 → 1 | ✓ finalized |
| w[4] "gg / G"        | REPLACE with w b e poem | ✓ finalized |
| w[5] "paragraphs"    | REPLACE with f F t T poem | ✓ finalized |
| w[6] "delete"        | REPLACE with ; , poem | ✓ finalized |
| w[7] "echoes"        | REPLACE with v poem | ✓ finalized |
| w[8] "transformation"| REPLACE with v/V/Ctrl-V poem | ✓ finalized |
| w[9] "dot"           | REPLACE with W B E poem | ✓ finalized |
| w[10] "undo"         | REPLACE with ge gE poem | ✓ finalized |
| w[11] "visual"       | REPLACE with G gg {n}G poem | ✓ finalized |
| w[12] old d y c      | REPLACE with H M L poem | ✓ finalized |
| w[13] old y p P yy   | REPLACE with % poem | ✓ finalized |
| w[14] old r R ~ .    | REPLACE with } { ) ( poem | ✓ finalized |
| w[15] text objects   | level field: 15 → 39 | ✓ finalized |
| old level=16 "%"     | level field: 16 → 0 (generic pool) | ✓ finalized |
| old level=17 "substitute" | level field: 17 → 0 | ✓ finalized |
| old level=18 "macros"| level field: 18 → 0 | ✓ finalized |
| old level=19 "files" | level field: 19 → 0 | ✓ finalized |
| w[15] new i a I A    | ADD at level=15 | ✓ finalized |
| w[16] new o O s S    | ADD at level=16 | ✓ finalized |
| w[18] new d c        | ADD at level=18 | ✓ finalized |
| w[19] new dd cc      | ADD at level=19 | ✓ finalized |
| w[20] new u Ctrl-R   | ADD at level=20 | ✓ finalized |
| w[25] new y yy       | ADD at level=25 | ✓ finalized |
| w[26] new p P        | ADD at level=26 | ✓ finalized |
| w[31] new r R        | ADD at level=31 | ✓ finalized |
| w[32] new ~          | ADD at level=32 | ✓ finalized |
| w[33] new .          | ADD at level=33 | ✓ finalized |
