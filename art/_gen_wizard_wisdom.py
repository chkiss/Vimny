#!/usr/bin/env python3
# Vimny — a Vim-teaching dungeon crawler.
# Copyright (C) 2026 Chas Kissick
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Source of truth for the Wizard Wisdom corpus — generates art/wizard_wisdom.txt.

Edit the POEMS list here, then run `python3 art/_gen_wizard_wisdom.py`.
Do not hand-edit wizard_wisdom.txt; it is a generated artifact (cf. _gen_runes.py).

─── Voice & Theme ──────────────────────────────────────────────────────────
The poems speak in the voice of someone who's walked these halls a hundred
times and isn't in a hurry — an old wizard who built this dungeon and still
finds it delightful. Vim commands aren't dramatic spells; they're techniques,
the way a carpenter reaches for the right tool without looking. He's earnest,
old-fashioned, genuinely pleased when a mechanic clicks. The dungeon is
amber-lit and warm, not threatening — lantern stone and slow breath, not
thunder and revelation. Language stays tactile: stride, step, stone, lantern.
Aphoristic — something you'd pin above your desk. Each poem leaves a mnemonic
image behind, the command fused to the feeling of using it. No grandeur. Just
warm precision.

─── How a poem is chosen (the key scheme) ──────────────────────────────────
Each blessing fires after a level is COMPLETED and introduces the commands of
the very next level — the lesson arrives right before it is needed.

A poem is keyed by `introduces_slug`: the LEVELS slug of the level it precedes.
`select_next_lesson_quote(completed_slug)` (render/title.py) finds the next
visible level after the completed one and fires the poem whose introduces_slug
matches. Keying by slug is robust to curriculum reordering AND renumbering —
the slug never changes, so a poem always precedes the same level.

Poems with introduces_slug=None are the GENERIC pool: title-screen flavour and
the fallback when a level has no dedicated poem (e.g. after the final boss).
`select_quote_by_name` looks poems up by `name` ('home row', 'save and quit').

Every line must be <= LINE_W (48) chars; the generator centres each line and
asserts the width. Keep introduces_slug in sync with content/levels.py.
"""
from __future__ import annotations
import json
from pathlib import Path

LINE_W   = 48   # wizard's box inner width (must match _BOX_INNER_W in title.py)
OUT_PATH = Path(__file__).parent / 'wizard_wisdom.txt'

# (introduces_slug, name, [raw lines])  — raw lines are centred by the generator.
# introduces_slug None  → generic pool / by-name lookup.
POEMS: list[tuple[str | None, str, list[str]]] = [
    # ── Generic pool (title screen + fallback + by-name) ─────────────────────
    (None, 'home row', [
        'h left, l right, j down, k up—',
        'a road built one step at a time.',
        'The arrow keys lie far from the hearth;',
        'keep your hands warm.',
    ]),
    (None, 'save and quit', [
        ': opens the spellbook beneath the glass.',
        ':w saves your tale in parchment permanence.',
        ':q winds the scroll, :wq keeps it safe.',
        ':q! lights it aflame—no record remains.',
    ]),
    (None, 'rhythm', [
        'Budget is breath. Par is pulse.',
        'Let the keystrokes flicker, not be rushed.',
    ]),
    (None, 'philosophy', [
        'Vim is a posture, not a tool.',
        'The hands stay; the mind roams the map.',
        'To forget and to recall are both roads.',
        'Clarity is warmth in the fingers.',
    ]),
    (None, 'encouragement', [
        'Every mage began with hjkl.',
        "You're not slow—you're tuning the signal.",
        'The buffer awaits in warm, soft light.',
    ]),
    (None, 'closing', [
        'Avaunt, traveler! Keep your glow steady.',
        'The world is text. You are the light.',
        'Lost? Esc. Return to stillness.',
        'Rest at home row.',
    ]),

    # ── Lesson poems, keyed by the slug they introduce ───────────────────────
    ('line_halls', 'line motions', [           # The Line Halls — ^ $ 0
        '0 to the bare left margin,',
        '^ to the first letter that speaks,',
        "$ to the line's far wall.",
        'Far-left, first word, far-right.',
    ]),
    ('reliquary', 'delete char', [             # The Reliquary — x (delete char); register " foreshadowed
        'x. No aim, no stride—just the mark',
        'beneath you, struck from the row.',
        'The unnamed register " keeps it.',
        'Nothing wanders far in here.',
    ]),
    ('counting_crypts', 'counts', [            # The Counting Crypts — [count]
        'Once I tapped j eleven times to fall.',
        'Now I say the number, then step.',
        '11j: eleven floors in a single breath.',
    ]),
    ('rune_halls', 'w b e', [                  # The Rune Halls — w b e
        "w steps to the next word's first stone.",
        'b walks that same path home again.',
        'e reaches across to the far edge—',
        "three strides, and the river's crossed.",
    ]),
    ('character_cataracts', 'f F t T', [       # The Character Cataracts — f F t T
        'fx lands square on the letter you name.',
        'tx halts a breath before it stands.',
        'F and T walk the same hunt backward.',
        'Name your mark; the rest is in your hands.',
    ]),
    ('goblin_gauntlet', '; ,', [               # The Goblin Gauntlet — ; , p
        'Name your letter the once.',
        '; walks that find on down the line.',
        ', turns on its heel and comes back.',
        "The hunt remembers; you needn't.",
    ]),
    ('wardens_keep', 'warden keep', [          # The Warden's Keep (boss)
        'A Warden waits beyond this door.',
        'Bring no new trick—only what you know.',
        'Steady hands have crossed worse halls.',
        'Breathe, and let the keystrokes fall.',
    ]),
    ('word_forge', 'W B E', [                  # The WORD Forge — W B E
        'w minds each comma, dot, and dash;',
        'W strides past them in a single bound.',
        'B walks it backward, E to the end—',
        'the bolder path across the ground.',
    ]),
    ('backward_vaults', 'ge gE', [             # The Backward Vaults — ge gE
        "e walks forward to a word's far edge.",
        'ge turns and finds the edge behind.',
        'The g says: the same reach, the other way.',
        'gE the wide one—whitespace to whitespace.',
    ]),
    ('lineheads', 'G gg', [                     # The Lineheads — G gg
        'gg: two soft steps to the top stone.',
        'G: one long fall to the cellar floor.',
        'Set a number first, and G lands there.',
        'Top, bottom, and every rung you name.',
    ]),
    ('screen_vault', 'H M L', [                # The Screen Vault — H M L
        'H, the high stone where the screen begins.',
        'M, the middle, never counted.',
        'L, the low stone where it ends.',
        'Your eye already knows the row.',
    ]),
    ('bracket_vaults', '%', [                  # The Bracket Vaults — %
        '( and ) are two ends of one arc.',
        '% steps from either to its partner.',
        'Stand on the open, land on the close—',
        'one hop, and the pair is closed.',
    ]),
    ('runic_archives', '} {', [                # The Runic Archives — } {
        '} leaps the blank to the next block.',
        '{ walks it back again.',
        'Paragraphs are doors of empty space.',
        'Step through; the silence carries you.',
    ]),
    ('sentence_corridor', ') (', [             # The Sentence Corridor — ) (
        'A full stop is a stone in the brook.',
        ') hops to the next, ( to the last.',
        'Sentence by sentence you cross dry.',
        'Each ending holds your foot.',
    ]),
    ('warden_surveyor', 'warden sight', [      # The Warden Surveyor (boss)
        "The Warden's eye opens ahead.",
        'He sees the whole hall before he moves.',
        'No new key—only your gathered craft.',
        'Look first; then make your stride.',
    ]),
    ('sight_sanctum', 'v', [                    # The Sight Sanctum — v
        'v opens the eye and it follows you.',
        'Move, and the trail glows behind—',
        'all it crosses, held until you act.',
    ]),
    ('seekers_labyrinth', '/ ? n N *', [       # The Seekers' Labyrinth — / ? n N *
        '/ casts a name down the hall ahead;',
        '? sends the same call back. n, N follow.',
        '* takes the word beneath your feet',
        'and hunts its echo through the stone.',
    ]),
    ('waypoint_sanctum', "m ' `", [            # The Waypoint Sanctum — m ' `
        'ma sets a stone you can name.',
        '`a returns to it, exact.',
        "'a drops you at that line's first rune.",
        'Mark the spot; wander; come straight back.',
    ]),
    ('archivists_library', ':e :set', [        # The Archivist's Library — :e :set
        ":e opens another chamber's scroll.",
        ':set number lights each line with a count.',
        'Many rooms, one steady lantern—',
        'step between them without losing your place.',
    ]),
    ('warden_pathfinder', 'warden pathfinder', [   # The Warden Pathfinder (boss)
        "The Pathfinder maps every hall you've walked.",
        'He asks no new trick, only your route.',
        'Find the seam; mark the turn; move clean.',
        'The way out is the way you came to know.',
    ]),
    ('operators_vault', 'd c', [               # The Operator's Vault — d c
        'd takes whatever the motion crosses.',
        'c takes it too, then opens to write.',
        'The verb decides; the motion measures.',
        'dw, c$ — say both, and it is done.',
    ]),
    ('cipher_cell', 'r D', [                   # The Cipher Cell — r D
        'r swaps one letter and stays put—',
        'strike the true rune over the false.',
        'D shears the rot from cursor to wall.',
        'Read what the cell forgot; write it back.',
    ]),
    ('whole_line_annex', 'c cc s', [           # The Change Annex — c cc s
        'd cuts the word, then drops the pen.',
        'c takes the word and hands you the pen.',
        'cc rewrites the line; s, a single rune.',
        'change cuts and writes in one breath.',
    ]),
    ('change_extension', 'S C', [              # The Change Extension — S C
        'cc you know—two strokes to mend a line.',
        'S does the same and asks for only one.',
        'c$ recut the tail; C is its single key.',
        'The practised hand spends less, says more.',
    ]),
    ('quartermaster', 'y yy P', [              # The Beacon Tiers — y yy P
        'y lifts the letters; nothing is cut.',
        'yy takes the whole line in one reach.',
        "What's lifted waits in the register—",
        'P lays it back, just before the cursor.',
    ]),
    # The Undo Sanctum was cancelled (u is always-on; <C-r> arrives by relic
    # scroll) — its poem lives on in the generic pool as 'undo and redo'.
    (None, 'undo and redo', [
        'u steps the last change back.',
        '<C-r> steps it forward again.',
        'Not retreat—the rope that lets you climb.',
        'Try the bold move; you can return.',
    ]),
    ('echo_vault', '.', [                       # The Echo Vault — .
        '. is memory; it forgets nothing.',
        'Whatever you changed last—it holds the shape.',
        'Move to the next place and press once.',
        'The same hand falls again.',
    ]),
    ('warden_manifold', 'warden manifold', [   # The Warden Manifold (boss)
        'The Manifold wears a hundred faces.',
        'Each is a task you have already learned.',
        'No new key waits past this gate—',
        'only the patience to repeat yourself well.',
    ]),
    ('inscription_halls', 'i a', [             # The Inscription Halls — i a
        'i opens just before the cursor stands.',
        'a opens just after—one step in.',
        'Two doors into the same quiet room.',
        'Esc closes them when the word is set.',
    ]),
    ('sculpting_chambers', 'I A o O', [        # The Sculpting Chambers — I A o O
        "I leaps to the line's first stone to write;",
        "A to the last—the line's far end.",
        'o opens a fresh line below; O above.',
        'Four ways in, each to its own edge.',
    ]),
    ('overwrite_halls', 'R', [                 # The Overwrite Halls — R
        'r struck one stone; R does not stop.',
        'It walks the wall, overwriting as it goes.',
        'A whole run of flaws under one steady hand—',
        'Esc, and the new line stands.',
    ]),
    ('case_chambers', '~ g~ gU gu', [          # The Case Chambers — ~ g~ gU gu
        '~ turns the lamp on the letter below:',
        'small to tall, tall to small, one step.',
        'gU raises a span; gu lowers it; g~ flips.',
        'Case bends; the cursor walks on.',
    ]),
    ('joiners_gate', 'J gJ', [                  # The Joiner's Gate — J gJ
        'J pulls the next line up to this one,',
        'setting a single space at the seam.',
        'gJ joins them with no space at all.',
        'Two rows become one clean stride.',
    ]),
    ('alignment_halls', '>> <<', [             # The Alignment Halls — >> <<
        '>> pushes the line one step right.',
        '<< pulls it back toward the margin.',
        'Indent is breath given to structure.',
        'Nudge the row until it sits true.',
    ]),
    ('indentation_sanctum', '>{m} <{m} =', [   # The Indentation Sanctum — >{m} <{m} =
        '> and < take a motion, like any verb:',
        '>} shifts a paragraph in one reach.',
        '= lets the buffer set its own depth.',
        'Name the span; the indent follows.',
    ]),
    ('warden_scrivener', 'warden scrivener', [     # The Warden Scrivener (boss)
        'The Scrivener has copied every hall.',
        'He tests the editing hand, not new keys.',
        'Cut clean, write true, fix what slips.',
        'A steady scribe needs no fresh spell.',
    ]),
    ('word_enclosure', 'iw aw', [              # The Word Enclosure — iw aw
        'Stand anywhere inside a word—',
        'ciw still changes the whole of it.',
        'iw takes the word; aw takes its space too.',
        'Name the shape; the rest is done.',
    ]),
    ('bracket_enclosure', 'i( a(', [           # The Bracket Enclosure — i( a(
        'Deep inside the parens, ci( clears them.',
        "i( holds what's within; a( takes the walls.",
        'No need to find the edges yourself—',
        'name the pair, and Vim spans it.',
    ]),
    ('brace_square_enclosure', 'i[ a[ i{ a{', [    # The Brace & Square Enclosure
        'Square or brace, the rule holds:',
        'i[ within, a[ with the brackets.',
        'i{ the body, a{ the braces too.',
        'Every pair answers to inside and around.',
    ]),
    ('quote_enclosure', 'i" a" i\' a\'', [          # The Quote Enclosure
        'ci" clears what the quotes contain.',
        'i" the words; a" the marks as well.',
        '\' or ", the same hand works both.',
        'Stand between; name in or around.',
    ]),
    ('tag_enclosure', 'it at', [               # The Tag Enclosure — it at
        'it holds what a tag pair wraps.',
        'at takes the tags themselves as well.',
        'cit rewrites the content clean,',
        'the angle-marks left standing.',
    ]),
    ('sentence_enclosure', 'is as', [          # The Sentence Enclosure — is as
        'is grasps the sentence you stand within.',
        'as gathers its trailing space too.',
        'No hunting for the stops—',
        'name the sentence, and it is yours.',
    ]),
    ('paragraph_enclosure', 'ip ap', [         # The Paragraph Enclosure — ip ap
        'ip takes the block you stand inside.',
        'ap gathers the blank line after, too.',
        'A whole paragraph in one named reach.',
        'The largest stone, lifted clean.',
    ]),
    ('grandmasters_sanctum', 'grandmaster', [      # The Grandmaster's Sanctum (boss)
        'The Grandmaster keeps the deepest hall.',
        'Every text object, every verb, in turn.',
        "Bring the whole of what you've learned—",
        'name the shape, and let it answer.',
    ]),
    ('spellwrights_forge', ':s///', [          # The Spellwright's Forge — :s///
        ':s shifts one shape on a line.',
        ':%s reshapes the whole world at once.',
        ':g/pat/d strikes every line bearing the curse.',
        'Name what is, then what shall be.',
    ]),
    ('hall_of_echoes', 'q @ "', [              # The Hall of Echoes — q @ "
        'qa captures your rhythm; q stills it.',
        '@a plays it back like a looped tape.',
        '"ay fills a jar; "ap pours it out.',
        'One motion, stored to echo down the halls.',
    ]),
    ('warden_eternal', 'warden eternal', [     # The Warden Eternal (final boss)
        'The last Warden is every Warden.',
        'No key remains for me to give—',
        'the buffer is yours now, end to end.',
        'Go gently, traveler. The light holds.',
    ]),
]


def _centre(line: str) -> str:
    """Centre a raw line within LINE_W; assert it fits."""
    assert len(line) <= LINE_W, f'line exceeds {LINE_W} chars ({len(line)}): {line!r}'
    pad = LINE_W - len(line)
    left = pad // 2
    return ' ' * left + line + ' ' * (pad - left)


def build() -> dict:
    levels = []
    for introduces_slug, name, lines in POEMS:
        levels.append({
            'introduces_slug': introduces_slug,
            'name': name,
            'line_count': len(lines),
            'quote': [_centre(l) for l in lines],
        })
    return {'levels': levels}


def main() -> None:
    data = build()
    header = (
        '# Vimny — Wizard Wisdom Corpus\n'
        '# GENERATED by art/_gen_wizard_wisdom.py — do not edit by hand.\n'
        '#\n'
        '# Each poem is tagged with introduces_slug: the LEVELS slug of the level\n'
        '# it precedes. The blessing fires that poem when the player completes the\n'
        '# level just before it. introduces_slug=null poems are the generic pool\n'
        '# (title-screen flavour + fallback). See the generator for voice notes.\n'
    )
    body = json.dumps(data, indent=2, ensure_ascii=False)
    OUT_PATH.write_text(header + body + '\n')
    print(f'Wrote {len(data["levels"])} poems to {OUT_PATH}')


if __name__ == '__main__':
    main()
