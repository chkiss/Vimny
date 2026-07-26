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

"""A level being written: the forge's half of the sharing pipeline.

**A draft file IS a level file.** Not a private editor format that is converted
on the way out — the same JSON, in the same schema, in its own directory. That
is the point: publishing is a copy, so there is no export step that can lose
something, and a half-finished draft is diagnosed by the very validator that
will judge the finished one. A draft simply fails `solvable` until it has a
tape, which is a true statement about it rather than a special case.

The other decision worth naming is that a draft is a **`Level`**, and the Room
is what the Level renders to. The obvious alternative — hold the Room and
serialise it on save, the way `~/.Vimny/layouts/` does — cannot express a fill:
a fill is a directive that grows words at build time, and once you have thrown
it away and kept the words, a region an author asked to be "sixty cells of
proverbs" is sixty cells of frozen text that the next edit cannot regrow. So the
Level is authoritative for everything declarative (fills, vocabulary, metadata),
the Room is authoritative for everything the author physically painted (cells,
hand-placed text, entities), and `sync` moves the second into the first.
"""
from __future__ import annotations

import json
import random
from dataclasses import dataclass, field
from pathlib import Path

from engine.editor import _CELL_CODE
from engine.world import CellType
from save.save_manager import DRAFTS_DIR, _slug
from sharing import format as F
from sharing.library import LEVELS_DIR
from sharing.validate import Report, validate

#: A new draft's room. Fits the stock terminal without scrolling, and is the
#: same shape as most shipped levels.
NEW_ROWS, NEW_COLS = 20, 80


@dataclass
class Draft:
    """One level under construction, plus where it lives on disk."""
    path:  Path
    level: F.Level
    error: str = ''                       # set when the file would not parse

    @property
    def name(self) -> str:
        return self.level.name if self.level else self.path.stem

    @property
    def ok(self) -> bool:
        return self.level is not None and not self.error

    def report(self) -> Report:
        """What the validator makes of it right now — the same check CI runs."""
        return validate(self.level)

    def build(self, par: int | None = None):
        """Render the draft to a playable Dungeon.

        `par=None` while authoring, which leaves the budget generous: an author
        walking their own half-built level must not be cut off mid-thought by a
        budget derived from a tape that does not exist yet.
        """
        return F.build(self.level, par=par)


# ── The blank page ────────────────────────────────────────────────────────────

def blank_cells(rows: int = NEW_ROWS, cols: int = NEW_COLS) -> list:
    """A walled room with a floor in it — run-length encoded, like the format."""
    wall  = F.encode_row([CellType.WALL] * cols)
    inner = F.encode_row([CellType.WALL] + [CellType.FLOOR] * (cols - 2)
                         + [CellType.WALL])
    return [wall] + [inner] * (rows - 2) + [wall]


def new(name: str, author: str = '', rows: int = NEW_ROWS,
        cols: int = NEW_COLS) -> Draft:
    """A fresh draft: an empty room, a seed, and nothing else claimed.

    The seed is minted once, here, and then never changes on its own. Every
    fill in the level resolves from it, so a seed that drifted would rearrange
    the words under a tape that was recorded against the old arrangement.
    """
    lvl = F.Level(name=name.strip(), author=author.strip(),
                  seed=random.randint(0, 2 ** 31 - 1),
                  rows=rows, cols=cols, cells=blank_cells(rows, cols),
                  spawn=(1, 1), exit=(rows - 2, cols - 2))
    return Draft(path=_path(lvl.name), level=lvl)


# ── Room → Level ──────────────────────────────────────────────────────────────

def sync(draft: Draft, room) -> None:
    """Fold the edited Room back into the draft's Level, in place.

    Fills, vocabulary and the metadata block survive because they are read off
    the Level and handed straight back — a Room has nowhere to keep them, so
    anything not carried across here would be silently lost on the first save.
    """
    lvl = draft.level
    draft.level = F.from_room(
        room, lvl.name, author=lvl.author, solution=lvl.solution,
        teaches=lvl.teaches, requires=lvl.requires,
        fills=list(getattr(room, 'fills', lvl.fills)),
        vocabulary=lvl.vocabulary, intro=lvl.intro, alternate=lvl.alternate,
        seed=lvl.seed)


# ── Disk ──────────────────────────────────────────────────────────────────────

def _path(name: str) -> Path:
    return DRAFTS_DIR / f'{_slug(name)}.json'


def save(draft: Draft) -> Path:
    """Write the draft out. Renaming a level renames its file with it."""
    DRAFTS_DIR.mkdir(parents=True, exist_ok=True)
    dest = _path(draft.level.name)
    dest.write_text(F.dumps(draft.level), encoding='utf-8')
    if draft.path != dest and draft.path.exists():
        draft.path.unlink()
    draft.path = dest
    return dest


def load(path: Path) -> Draft:
    """Read one draft. A file that will not parse comes back carrying its
    error rather than vanishing — a draft you cannot see is one you cannot
    fix."""
    try:
        return Draft(path=path, level=F.loads(path.read_text(encoding='utf-8')))
    except (OSError, json.JSONDecodeError, F.LevelFormatError) as exc:
        return Draft(path=path, level=None, error=str(exc))


def list_drafts() -> list:
    if not DRAFTS_DIR.exists():
        return []
    return sorted((load(p) for p in DRAFTS_DIR.glob('*.json')),
                  key=lambda d: d.name.lower())


def delete(draft: Draft) -> bool:
    if draft.path.exists():
        draft.path.unlink()
        return True
    return False


def publish(draft: Draft) -> tuple:
    """Validate, then put the draft on the shelf. Returns `(path|None, report)`.

    A draft is only ever published through the validator, and the file that
    lands is the draft's own bytes — so the level that ships is exactly the one
    the author was playing, not a re-rendering of it that might differ.
    """
    rep = draft.report()
    if not rep.ok:
        return None, rep
    LEVELS_DIR.mkdir(parents=True, exist_ok=True)
    dest = LEVELS_DIR / f'{_slug(draft.level.name)}.json'
    dest.write_text(F.dumps(draft.level), encoding='utf-8')
    return dest, rep
