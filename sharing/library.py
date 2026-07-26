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

**There is no network code here, and there must never be.** A player downloads
a level file by whatever means they like and drops it in the directory; the game
reads a directory and nothing else. An in-game fetcher would buy one saved
manual step at the price of a privacy surface, an outage dependency, and a
second trust boundary. Together with "a level is data, never code"
(`sharing/format.py`), that keeps the whole security story short enough to state
in the README: Vimny reads files you put there, and runs none of them.

Every level is validated on LOAD, not merely when it was submitted, so a
hand-edited file gets the same scrutiny as a reviewed one.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from save.save_manager import SAVE_DIR
from sharing import format as F
from sharing.validate import Report, validate

LEVELS_DIR = SAVE_DIR / 'levels'


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


def levels_dir() -> Path:
    return LEVELS_DIR


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
        text = path.read_text(encoding='utf-8')
    except OSError as exc:
        return Shelved(path=path, error=f'could not read the file: {exc}')
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
    return F.build(shelf.level, par=shelf.report.par)


def install(path: Path) -> Shelved:
    """Copy a level file onto the shelf, validating before it lands there."""
    shelf = load_level(path)
    if not shelf.ok:
        return shelf
    LEVELS_DIR.mkdir(parents=True, exist_ok=True)
    dest = LEVELS_DIR / path.name
    dest.write_text(path.read_text(encoding='utf-8'), encoding='utf-8')
    return load_level(dest)


def export(lvl: F.Level, path: Path) -> Path:
    path.write_text(F.dumps(lvl), encoding='utf-8')
    return path
