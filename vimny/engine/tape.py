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

"""The answer-tape alphabet — one source of truth for the karaoke notation.

A tape (`room.answer`) is the literal keystrokes that solve a level, shown to
the admin as a karaoke sheet and matched keystroke-by-keystroke as they play.
Most keys write themselves. Four do not, because a plain space in the tape is a
*display separator* and the rest have no printable form at all:

    <Space>   a space the player actually TYPES
    <CR>      a typed Enter
    <Esc>     Esc
    <C-v>     the block-visual key

**The notation is Vim's own.** This is a Vim-teaching game, so the sheet spells
these keys the way `:help key-notation` does and the way the README's command
tables already print them. An earlier pass used single symbolic glyphs
(`␣ ⏎ ⎋`) plus an invented `^v`; that was compact but it taught the player a
private alphabet, and `⎋` (U+238B) is carried by very few monospace fonts, so
on most terminals it rendered as a tofu box.

Angle-bracket tokens are self-delimiting, which is what makes the multi-glyph
form safe: a token is matched whole by `startswith`, never character by
character, so there is no way to consume half of one.

`<Esc>` is the newest of the four, and the reason it exists is replay. Esc used
to be OMITTED entirely, on the reasoning that a player reading the sheet can
infer it: after typing text you obviously have to leave INSERT. That reads fine
on paper and cost nothing during play — but it made a tape UNREPLAYABLE. A
replayer feeding the tape back infers nothing, so the keys after an insert verb
were typed into the buffer instead of executed, and every insert/change level
had to sit out the headless audit (`python3 -m sharing audit`) and could not
have its par measured. The same gap blocked community levels: an authored route
containing `i`, `a`, `c` or `R` could not be validated at all.

Esc is free — leaving INSERT spends no budget — so writing it down does not
change any level's par by a single keystroke.

**Slot references** (`<fill0.3>`) are the fifth thing that is not a key, and the
only one that is not a keystroke at all. A tape has to contain the literal words
the player types — `cerune<Esc>` — but a `fill` directive grows different words
for every player, so a tape naming one is a tape that solves nobody's level but
its author's. A slot ref says which word instead of which letters: "whatever
grew in fill 0, slot 3". It is resolved once, at build time, against the words
that fill actually laid for THIS player, and everything downstream — the karaoke
sheet, the replayer, the cost model — sees an ordinary tape of ordinary letters.
"""
from __future__ import annotations

import re

SPACE  = '<Space>'   # a TYPED space (a plain ' ' in a tape is only a separator)
ENTER  = '<CR>'      # a typed Enter
ESC    = '<Esc>'     # Esc — free, but must be written or the tape cannot replay
CTRL_V = '<C-v>'     # the block-visual key

#: Every multi-character token, longest first so matching is unambiguous.
#: (Nothing here is a prefix of anything else, but the order is load-bearing if
#: a future token ever is — keep it sorted by length.)
TOKENS = tuple(sorted((SPACE, ENTER, ESC, CTRL_V), key=len, reverse=True))

#: The markers a reader sees but the budget never charges for.
FREE = (ESC,)

#: Back-compat alias: everything that is a written marker rather than a literal.
MARKERS = (SPACE, ENTER, ESC)

#: `<fill{n}.{k}>` — the word grown by fill n in slot k. BOTH are 0-based, to
#: match `fill[0]` in the file and in every error message the format prints; a
#: reference that counted from one while its own error message counted from zero
#: would be a trap laid for the author who is already confused.
SLOT_REF = re.compile(r'<fill(\d+)\.(\d+)>')


class UnknownSlot(LookupError):
    """A slot reference naming a fill, or a word, that the build never grew."""


def slot_refs(tape: str) -> list:
    """`[(fill, slot), …]` — every slot reference in `tape`, in order."""
    return [(int(m.group(1)), int(m.group(2))) for m in SLOT_REF.finditer(tape)]


def resolve_slots(tape: str, slots) -> str:
    """Replace every `<fill{n}.{k}>` with the word that fill grew there.

    `slots` is what the build recorded: one list of words per fill directive, in
    laying order. Raises `UnknownSlot` rather than leaving the reference in
    place — a tape that still reads `<fill0.3>` would be typed into the buffer
    letter by letter, which is a route that silently does something else.

    A fill can lay FEWER words than its region suggests (it skips stone, and it
    thins out at the right margin), so an out-of-range slot is the ordinary way
    to get this wrong and says so.
    """
    def _one(m):
        n, k = int(m.group(1)), int(m.group(2))
        if n >= len(slots):
            raise UnknownSlot(
                f'solution: {m.group(0)} names fill {n}, but this level has '
                f'{len(slots)} fill directive(s)')
        if k >= len(slots[n]):
            raise UnknownSlot(
                f'solution: {m.group(0)} names word {k} of fill {n}, which grew '
                f'only {len(slots[n])} word(s) — a fill lays no word where the '
                f'floor is stone, and stops short of the right margin')
        return slots[n][k]
    return SLOT_REF.sub(_one, tape)


def strip_separators(tape: str) -> str:
    """The tape as matchable glyphs: plain spaces are display only."""
    return tape.replace(' ', '')


def token_at(plain: str, pos: int) -> str:
    """The tape token starting at `pos` — a `<...>` token, or one character.

    `plain` must already be separator-stripped. This is the single place that
    decides how far the playhead moves, so the live tracker, the replayer and
    the cost model can never disagree about where a token ends.
    """
    for tok in TOKENS:
        if plain.startswith(tok, pos):
            return tok
    # An UNRESOLVED slot reference is one atom too, so the forge can show and
    # measure a tape that has not been built yet without chopping one in half.
    m = SLOT_REF.match(plain, pos)
    if m:
        return m.group(0)
    return plain[pos:pos + 1]


def to_keys(tape: str, term=None, *, separators: bool = True) -> list:
    """Turn a tape into the Keystrokes the game loop reads.

    `term` supplies the KEY_ESCAPE code so the Esc keystroke is a real sequence
    key — `key.is_sequence` is what the loop tests, and a bare '\\x1b' with no
    code would be read as a printable character and typed into the buffer.

    `separators` is what makes this safe to point at two different kinds of
    string. In a TAPE a plain space is display spacing and is dropped, which is
    the whole reason a typed space has to be written `<Space>`. A hand-written
    keystroke string in a test is not a tape — `:6s/^  //<CR>` means those two
    spaces literally — so pass `separators=False` and every space is a keypress.
    """
    from blessed import Terminal
    from blessed.keyboard import Keystroke

    if term is None:
        term = Terminal(force_styling=False)
    esc_code = term.KEY_ESCAPE

    plain = strip_separators(tape) if separators else tape
    out, i = [], 0
    while i < len(plain):
        tok = token_at(plain, i)
        i += len(tok)
        if tok == ENTER:
            out.append(Keystroke('\r'))
        elif tok == SPACE:
            out.append(Keystroke(' '))
        elif tok == CTRL_V:
            out.append(Keystroke('\x16'))
        elif tok == ESC:
            out.append(Keystroke('\x1b', code=esc_code, name='KEY_ESCAPE'))
        else:
            out.append(Keystroke(tok))
    return out


def from_keystroke(key) -> str | None:
    """One pressed key → the tape notation for it, or None if it cannot be written.

    The inverse of `to_keys`, and the reason `:record` can exist: a tape typed
    by hand is a transcription the author might get wrong, while a tape captured
    from the keys that actually solved the level cannot be.

    None means REFUSE, not "skip". An arrow key, Backspace or a function key is a
    real keypress that moved the game, but the notation has no way to write it,
    so a tape containing one would replay as something other than what was
    played. Recording stops rather than hand back a tape that lies — and since
    every one of those keys has a Vim spelling (`h`/`l`, `x`), refusing also
    keeps a recorded route honest about being Vim.
    """
    if getattr(key, 'is_sequence', False):
        return ESC if getattr(key, 'name', '') == 'KEY_ESCAPE' else None
    ch = str(key)
    if ch == '\x1b':  return ESC      # Esc read as a bare byte (no code attached)
    if ch == '\r' or ch == '\n':      return ENTER
    if ch == ' ':     return SPACE
    if ch == '\x16':  return CTRL_V
    return ch if ch.isprintable() and len(ch) == 1 else None


# ── Which part of a tape is TEXT the player types, not keys they press ────────
#
# The karaoke sheet reads better when `Orow<Space>row<Space>your<Space>boat<Esc>`
# shows `O` and `<Esc>` as commands and `row row your boat` as the words they
# are. The dividing line is WORDS THE PLAYER READ OFF THE MAP — buffer text
# (`Orow…`), a search pattern (`/vault`), and a substitution's pattern and
# replacement (`:%s/moo/quack/g`) are all words from the dungeon, while the
# keys around them are Vim.
#
# Telling them apart means a real scan, because the same letters mean different
# things in different places: the `i` in `diw` is a text object, the `a` in
# `ra` is `r`'s argument, and neither opens INSERT. So the scanner consumes
# whole Vim atoms rather than characters — an operator with its text object,
# `f{char}`, `r{char}`, a mark, a register — BEFORE the verb table is
# consulted, which is what keeps those letters from being read as verbs.
#
# Tape tokens are never text: `<Space>` is a key the player presses, so it
# stays a command even in the middle of a typed phrase.

import re as _re

#: Openers that put the player in INSERT/REPLACE: everything up to the next
#: `<Esc>` is then text going into the buffer.
_INSERT_VERB = _re.compile(
    r'\d*(?:'
    r'cc|c[ia][\w(){}\[\]<>"\']|c[wWeEbB$0^%]|'   # change: cc, ciw, ca(, ce, c%
    r'gi|'                                        # gi — resume INSERT in place
    r'[IiAaOoRsSC]'                               # plain openers
    r')')

#: Atoms eaten whole so the letters inside them are never read as verbs.
_NOT_A_VERB = (
    _re.compile(r'[/?:][^ ]*?' + _re.escape(ENTER)),  # /pat<CR>, :%s/a/b/g<CR>
    _re.compile(r'\d*[dy](?:[ia][\w(){}\[\]<>"\']|[dy]|[\w$0^%(){}\[\]<>"\'])'),
    _re.compile(r'\d*[fFtT].'),                       # f{char} and friends
    _re.compile(r'r.'),                               # r{char} — replace one
    _re.compile(r'["mq@\'`]\w'),                      # "a  ma  qa  @a  'a  `a
    # gU, gu, g~, gg, gj … but NOT `gi`, which resumes INSERT and belongs to
    # the verb table. This list is consulted first, so a `g[a-zA-Z]` catch-all
    # would eat `gi` before the opener was ever considered.
    _re.compile(r'\d*g[a-hj-zA-Z~]'),
)


#: A search or ex line, eaten whole — its own words are picked out separately.
_CMDLINE = _re.compile(r'[/?:][^ ]*?' + _re.escape(ENTER))


def _cmdline_word_indices(line: str, base: int) -> set:
    """Indices of the WORDS inside one `/…<CR>` or `:…<CR>`, offset by `base`.

    `/vault<CR>` → `vault`. `:%s/moo/quack/g<CR>` → `moo` and `quack`. The
    surrounding `:%s/`, `/g` and `<CR>` are Vim and stay commands.

    Fields are taken positionally from the `/`-delimited body, which is what
    Vim itself does: a substitute carries pattern AND replacement, a `:g`/`:v`
    carries only a pattern (what follows it is a command, not a word).
    """
    body = line[1:-len(ENTER)]                 # drop the introducer and the <CR>
    off  = base + 1
    if line[0] in '/?':                        # a bare search: all of it is the pattern
        return set(range(off, off + len(body)))

    parts, want = body.split('/'), ()
    if len(parts) > 1:
        head = parts[0].rstrip('!')            # ':%s' / ':2,19v' / ':g'
        if head.endswith('s'):
            want = (1, 2)                      # pattern and replacement
        elif head.endswith(('g', 'v')):
            want = (1,)                        # pattern only
    out, pos = set(), off
    for idx, part in enumerate(parts):
        if idx in want:
            out |= set(range(pos, pos + len(part)))
        pos += len(part) + 1                   # +1 for the '/' delimiter
    return out


def literal_spans(tape: str) -> list:
    """`[(start, end), …]` over `tape` — the stretches that are WORDS, not keys.

    Indices are into the tape as written, spaces and all, so a renderer can
    colour it directly. Three things count as words, because all three are text
    the player read off the map: buffer text between an insert opener and its
    `<Esc>`, a search pattern, and a substitution's pattern and replacement.

    Tape tokens never count. `<Space>` is a key the player presses, so it stays
    a command even mid-phrase, and a run is split around it. Plain separator
    spaces are excluded too — they are display, not keystrokes.
    """
    n = len(tape)
    lit = set()
    i, in_insert = 0, False

    while i < n:
        if tape[i] == ' ':
            i += 1
            continue
        tok = token_at(tape, i)
        if in_insert:
            if tok == ESC:
                in_insert = False
            elif tok not in TOKENS:            # a token is a key, never a word
                lit |= set(range(i, i + len(tok)))   # a slot ref is a word, whole
            i += len(tok)
            continue
        m = _CMDLINE.match(tape, i)
        if m:
            lit |= _cmdline_word_indices(m.group(0), i)
            i = m.end()
            continue
        for pat in _NOT_A_VERB:                # eat whole atoms before reading verbs
            m = pat.match(tape, i)
            if m:
                i = m.end()
                break
        else:
            m = _INSERT_VERB.match(tape, i)
            if m:
                in_insert = True
                i = m.end()
                continue
            i += len(tok)

    lit -= {i for i, ch in enumerate(tape) if ch == ' '}
    spans, run = [], None
    for i in range(n + 1):
        if i in lit:
            run = i if run is None else run
        elif run is not None:
            spans.append((run, i))
            run = None
    return spans


def keystroke_cost(tape: str) -> int:
    """How many BUDGET-SPENDING keys a tape holds.

    One token is one keystroke however many glyphs it is written with — which
    is the whole reason `token_at` is shared. Esc is a mode key and spends
    nothing, so it does not count; that is exactly why writing it down was safe
    to add to tapes that were already par-pinned.
    """
    plain = strip_separators(tape)
    n, i = 0, 0
    while i < len(plain):
        tok = token_at(plain, i)
        i += len(tok)
        if tok not in FREE:
            n += 1
    return n

