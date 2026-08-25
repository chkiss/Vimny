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

"""The player's shelf of community levels: `~/.Vimny/levels/`.

**There is no network code here, and there must never be.** This module reads a
directory and nothing else: a player drops a level file in, and the game finds
it. Nothing is fetched at startup, in the background, or on a timer.

The network lives one module away and only ever at the player's word.
`vimny/sharing/remote.py` fetches the community shelf when they ask for it (`:e
remote`), and `vimny/sharing/submit.py` builds a link for their browser to open —
neither one runs unbidden, and both hand what they get back to the same
`validate()` a hand-dropped file goes through. Keeping them separate is what
keeps the security story short enough to state in the README: together with "a
level is data, never code" (`vimny/sharing/format.py`), Vimny reads files you put
there or asked for, and runs none of them.

Every level is validated on LOAD, not merely when it was submitted, so a
hand-edited file gets the same scrutiny as a reviewed one.
"""
from __future__ import annotations

import random
from dataclasses import dataclass
from pathlib import Path

from vimny.save import save_manager as _sm
from vimny.sharing import format as F
from vimny.sharing.validate import Report, validate

def levels_dir():
    """The shelf directory, resolved late so VIMNY_HOME (test isolation)
    redirects it along with every other path."""
    return _sm.SAVE_DIR / 'levels'


LEVELS_DIR = levels_dir()   # historical constant; prefer levels_dir()

_MAX_BYTES = 512 * 1024   # same cap sharing.remote applies to downloads — a level file is never larger


@dataclass
class Shelved:
    """One file on the shelf, whether or not it turned out to be playable."""
    path:   Path
    level:  F.Level | None = None
    report: Report | None = None
    error:  str = ''

    @property
    def ok(self) -> bool:
        return self.level is not None and self.report is not None and self.report.ok

    @property
    def name(self) -> str:
        return self.level.name if self.level else self.path.stem

    @property
    def slug(self) -> str:
        """Community slugs are namespaced so one can never collide with a
        shipped slug — save keys, scroll drops and progress all key by slug."""
        return f'community/{self.path.stem}'


def list_levels() -> list[Shelved]:
    """Every `*.json` on the shelf, validated, sorted by name.

    Broken files are RETURNED rather than skipped, carrying their error. A file
    that silently vanishes from the list is a player wondering why the level
    they downloaded is not there; one listed with "why" attached is a player who
    can fix it or tell the author.
    """
    if not LEVELS_DIR.exists():
        return []
    out = [load_level(p) for p in sorted(LEVELS_DIR.glob('*.json'))]
    out.sort(key=lambda s: s.name.lower())
    return out


def load_level(path: Path) -> Shelved:
    try:
        raw = path.read_bytes()
    except OSError as exc:
        return Shelved(path=path, error=f'could not read the file: {exc}')
    if len(raw) > _MAX_BYTES:
        return Shelved(path=path,
                       error='that file is suspiciously large — refusing to load it')
    try:
        text = raw.decode('utf-8')
    except UnicodeDecodeError:
        return Shelved(path=path, error='that file is not UTF-8 text')
    return _from_text(path, text)


def _from_text(path: Path, text: str) -> Shelved:
    """Parse + validate text already in hand. `loads` funnels every
    type-confusion to LevelFormatError; this catch is the belt to that brace,
    so one broken shelf file can never take down the whole listing."""
    try:
        lvl = F.loads(text)
    except F.LevelFormatError as exc:
        return Shelved(path=path, error=str(exc))
    rep = validate(lvl)
    return Shelved(path=path, level=lvl, report=rep,
                   error='' if rep.ok else rep.errors[0])


def build_shelved(shelf: Shelved):
    """Build a validated shelf entry into a playable Dungeon, par already pinned.

    Par comes from the validator's replay of the author's own tape — never from
    the file. Refuses an entry that did not validate, because the load-time
    check is the only thing standing between a player and a level that cannot be
    finished.
    """
    if not shelf.ok:
        raise ValueError(f'{shelf.path.name}: {shelf.error}')
    # A FRESH seed every time it is played, exactly as a shipped level gets one.
    # Par came from the tape and is pinned; validation proved the tape holds
    # whatever the fills grow, so the words are free to be different.
    return F.build(shelf.level, par=shelf.report.par,
                   seed=random.randint(0, 2 ** 31 - 1))


def install(path: Path) -> Shelved:
    """Copy a level file onto the shelf, validating before it lands there."""
    try:
        raw = path.read_bytes()
    except OSError as exc:
        return Shelved(path=path, error=f'could not read the file: {exc}')
    if len(raw) > _MAX_BYTES:
        return Shelved(path=path,
                       error='that file is suspiciously large — not installing')
    try:
        text = raw.decode('utf-8')
    except UnicodeDecodeError:
        return Shelved(path=path, error='that file is not UTF-8 text')
    shelf = _from_text(path, text)
    if not shelf.ok:
        return shelf
    LEVELS_DIR.mkdir(parents=True, exist_ok=True)
    dest = LEVELS_DIR / path.name
    # Write the SAME bytes that were validated — re-reading the source could
    # pick up a change between the two reads.
    dest.write_text(text, encoding='utf-8')
    return load_level(dest)


def export(lvl: F.Level, path: Path) -> Path:
    path.write_text(F.dumps(lvl), encoding='utf-8')
    return path
