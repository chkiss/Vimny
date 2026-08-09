#!/usr/bin/env python3
# Vimny — a Vim-teaching dungeon crawler.
# Copyright (C) 2026 Chas Kissick
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Cut the browser build's fonts down to the characters Vimny actually draws.

The terminal build inherits whatever monospace font the player has configured,
and on a desktop that is nearly always something with box-drawing and a decent
symbol block. A browser has no such luck: the page gets the visitor's default
monospace, and Vimny's runes are drawn from the astrological, chess, card, dice
and alchemical blocks, which most of them do not cover. Those characters are not
decoration — `vimny/art/vocab_mixed.txt` is the rune vocabulary the dungeons are
built out of, so a missing glyph is a puzzle drawn with tofu in it.

So the build ships fonts, subsetted to the ~260 non-ASCII characters the package
contains. It takes three faces to cover them, in this order:

  Vimny Mono    DejaVu Sans Mono — the monospace one, and the one whose cell
                xterm.js measures. Covers all of ASCII and most of the rest.
  Vimny Runes   Symbola — public domain, and has the pentagrams, trigrams and
                alchemical symbols DejaVu has no glyph for.
  Vimny Extra   DejaVu Sans — three Canadian Syllabics that neither of the
                above carries.

Each face is subsetted to only what the face BEFORE it could not supply, so
nothing is paid for twice.

    ./web/subset_fonts.py <source-dir> <out-dir>
"""
import pathlib
import sys

from fontTools import subset
from fontTools.ttLib import TTFont

# Faces in fallback order: (css family, filename, is-the-monospace-one).
FACES = [
    ('Vimny Mono',  'DejaVuSansMono.ttf', True),
    ('Vimny Runes', 'Symbola.otf',        False),
    ('Vimny Extra', 'DejaVuSans.ttf',     False),
]

# What the page's own chrome uses, plus every printable ASCII character — the
# game is mostly ASCII and the scan below only looks for the unusual.
ALWAYS = set(range(0x20, 0x7F))

SCANNED_SUFFIXES = {'.py', '.txt', '.md', '.json'}


def wanted(package: pathlib.Path) -> set:
    """Every codepoint that appears anywhere in the installed package.

    Deliberately blunt: it counts characters in comments and docstrings too.
    Being generous costs a few hundred bytes of woff2, and the alternative —
    tracking which literals reach the screen through eleven thousand lines of
    game — is the kind of cleverness that ships a dungeon with a hole in it.
    """
    found = set(ALWAYS)
    for path in sorted(package.rglob('*')):
        if path.is_file() and path.suffix in SCANNED_SUFFIXES:
            try:
                text = path.read_text(encoding='utf-8')
            except (OSError, UnicodeDecodeError):
                continue
            found.update(ord(ch) for ch in text)
    return {cp for cp in found if cp >= 0x20 and cp != 0x7F}


def cut(src: pathlib.Path, keep: set, dest: pathlib.Path) -> set:
    """Subset `src` to `keep`, write woff2, and return what it actually had."""
    have = keep & set(TTFont(src, fontNumber=0, lazy=True).getBestCmap())
    if not have:
        return set()
    options = subset.Options()
    options.flavor = 'woff2'
    options.desubroutinize = True          # smaller for CFF outlines (Symbola)
    options.layout_features = []           # a terminal shapes nothing
    options.name_IDs = ['*']               # keep the licence strings
    options.notdef_outline = True          # a visible box beats an invisible gap
    font = subset.load_font(str(src), options)
    subsetter = subset.Subsetter(options=options)
    subsetter.populate(unicodes=have)
    subsetter.subset(font)
    subset.save_font(font, str(dest), options)
    font.close()
    return have


def main() -> int:
    if len(sys.argv) != 3:
        print(__doc__.strip().splitlines()[-1].strip(), file=sys.stderr)
        return 2
    sources = pathlib.Path(sys.argv[1])
    out     = pathlib.Path(sys.argv[2])
    out.mkdir(parents=True, exist_ok=True)

    package = pathlib.Path(__file__).resolve().parent.parent / 'vimny'
    keep    = wanted(package)

    css, remaining = [], set(keep)
    for family, filename, is_mono in FACES:
        src = sources / filename
        if not src.exists():
            print(f'   ! {filename} missing — skipping {family}', file=sys.stderr)
            continue
        # The monospace face keeps everything it can, so that xterm.js measures
        # a cell off a font that really is monospaced. The others fill gaps.
        woff2 = f'{src.stem}.woff2'
        got   = cut(src, keep if is_mono else remaining, out / woff2)
        if not got:
            print(f'   {family:12} nothing left for it — skipped')
            continue
        remaining -= got
        size = (out / woff2).stat().st_size
        print(f'   {family:12} {len(got):4} glyphs  {size / 1024:6.1f} KB')
        css.append((family, woff2))

    body = '\n'.join(
        f'@font-face {{\n'
        f'  font-family: "{family}";\n'
        f'  src: url("{fname}") format("woff2");\n'
        f'  font-display: block;\n'   # tofu for a moment is worse than nothing
        f'}}\n'
        for family, fname in css)
    (out / 'fonts.css').write_text(
        '/* Generated by web/subset_fonts.py — do not edit.\n'
        ' * DejaVu fonts: Bitstream Vera + Arev licences (permissive).\n'
        ' * Symbola by George Douros: public domain.\n'
        ' */\n' + body, encoding='utf-8')

    if remaining:
        chars = ' '.join(f'U+{cp:04X}({chr(cp)})' for cp in sorted(remaining))
        print(f'   ! {len(remaining)} characters no bundled font covers: {chars}')
    else:
        print('   every character Vimny draws has a bundled glyph')
    return 0


if __name__ == '__main__':
    sys.exit(main())
