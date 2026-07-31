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

#: A new draft's room — a CANVAS, not a level. You cannot select a region larger
#: than the room you are standing in, so a 20x80 draft quietly capped how big
#: anything an author built could be, and there was no way to grow one. The
#: canvas is big and what ships is trimmed to fit: `format.crop` takes the blank
#: stone back off at publish time, so the generous size costs the reader nothing.
NEW_ROWS, NEW_COLS = 100, 100


@dataclass
class Draft:
    """One level under construction, plus where it lives on disk."""
    path:  Path
    level: F.Level
    error: str = ''                       # set when the file would not parse
    #: WHICH ROOM THE AUTHOR IS STANDING IN. A level is a descent of up to
    #: `format.MAX_ROOMS` rooms, and the forge shows exactly one of them at a
    #: time — there is one cursor and one screen. This is the index into
    #: `level.rooms`, so 0 is the level's own geometry and n is `then[n-1]`.
    #: It is deliberately NOT saved to the file: which room an author last had
    #: open is a fact about the editing session, not about the level, and a
    #: draft that reopened into room 4 because that is where its author left
    #: off would be a file that renders differently for the next reader.
    room_index: int = 0

    @property
    def name(self) -> str:
        return self.level.name if self.level else self.path.stem

    @property
    def ok(self) -> bool:
        return self.level is not None and not self.error

    def report(self) -> Report:
        """What the validator makes of it right now — the same check CI runs."""
        return validate(self.level)

    def build(self, par: int | None = None, seed: int | None = None):
        """Render the draft to a playable Dungeon.

        `par=None` while authoring, which leaves the budget generous: an author
        walking their own half-built level must not be cut off mid-thought by a
        budget derived from a tape that does not exist yet.

        `seed=None` grows the fills from the level's own seed, which is what an
        author wants for every incidental rebuild — the room should not rearrange
        itself because they painted a wall. A caller that passes a seed is asking
        the deliberate question a player's copy answers: what do the fills look
        like for somebody else? Only `:e` does that.
        """
        return F.build(self.level, par=par, seed=seed)


# ── The blank page ────────────────────────────────────────────────────────────

#: The floor a new draft opens ON. The rest of the canvas is solid stone the
#: author carves into with `:paint floor` — which is why the canvas can be huge
#: without every new level being huge: stone nobody touched is trimmed at publish.
OPEN_ROWS, OPEN_COLS = 20, 80


def blank_cells(rows: int = NEW_ROWS, cols: int = NEW_COLS) -> list:
    """A walled room in the corner of a stone canvas — run-length encoded.

    The room is the familiar 20x80 so a draft still opens on somewhere to stand,
    and it sits at the top-left so the author's first screen is that room rather
    than a field of rock. Everything beyond it is stone waiting to be carved.
    """
    open_r = min(OPEN_ROWS, rows)
    open_c = min(OPEN_COLS, cols)
    wall   = F.encode_row([CellType.WALL] * cols)
    inner  = F.encode_row([CellType.WALL] + [CellType.FLOOR] * (open_c - 2)
                          + [CellType.WALL] * (cols - open_c + 1))
    return [wall] + [inner] * (open_r - 2) + [wall] * (rows - open_r + 1)


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
                  spawn=(1, 1),
                  # …in the room the draft opens on, not the far corner of the
                  # canvas, which is solid rock.
                  exit=(min(OPEN_ROWS, rows) - 2, min(OPEN_COLS, cols) - 2))
    return Draft(path=_path(lvl.name), level=lvl)


# ── Room → Level ──────────────────────────────────────────────────────────────

def sync(draft: Draft, room) -> None:
    """Fold the edited Room back into the draft's Level, in place.

    Fills, vocabulary and the metadata block survive because they are read off
    the Level and handed straight back — a Room has nowhere to keep them, so
    anything not carried across here would be silently lost on the first save.

    The forge edits ONE room at a time — `draft.room_index`, the one the author
    is standing in. The others are not on screen and nothing here has touched
    them, so they ride through untouched; dropping them would be an edit to a
    room the author never opened.
    """
    lvl = draft.level
    fills = list(getattr(room, 'fills', lvl.fills))
    seals = list(getattr(room, 'seals', lvl.seals))
    if draft.room_index:
        # A later room: only that entry of `then` changes. Everything
        # level-wide — the name, the tape, the vocabulary, room 0 — belongs
        # to the level and is none of this room's business.
        i = draft.room_index - 1
        then = list(lvl.then)
        then[i] = F.capture_room(room, fills=fills, seals=seals,
                                      where=f'then[{i}].geometry')
        lvl.then = then
        return
    draft.level = F.from_room(
        room, lvl.name, author=lvl.author, solution=lvl.solution,
        teaches=lvl.teaches, requires=lvl.requires,
        fills=fills, seals=seals,
        vocabulary=lvl.vocabulary, intro=lvl.intro, alternate=lvl.alternate,
        seed=lvl.seed, then=lvl.then)


# ── Rooms ─────────────────────────────────────────────────────────────────────
# A level is a DESCENT: room 1, then room 2, and the exit of each is the door
# into the next. The forge builds them one at a time because there is one cursor
# and one screen; `:room` is how an author moves between them.

def add_room(draft: Draft) -> int:
    """Append a blank room and return its index (its `level.rooms` slot).

    Blank means the same canvas `new()` opens on, so a second room starts
    exactly as welcoming as the first — an author who has to carve a room out of
    solid rock before they can put anything in it would reasonably conclude the
    feature was not finished.
    """
    if len(draft.level.rooms) >= F.MAX_ROOMS:
        raise ValueError(f'a level may have at most {F.MAX_ROOMS} rooms — '
                         'a descent, not a dungeon crawl')
    i = len(draft.level.then)
    draft.level.then.append(F.Room(
        rows=NEW_ROWS, cols=NEW_COLS, cells=blank_cells(NEW_ROWS, NEW_COLS),
        spawn=(1, 1),
        exit=(min(OPEN_ROWS, NEW_ROWS) - 2, min(OPEN_COLS, NEW_COLS) - 2),
        where=f'then[{i}].geometry'))
    return len(draft.level.rooms) - 1


def delete_room(draft: Draft, index: int) -> None:
    """Remove one room. Room 1 cannot go: it is the level's own geometry,
    it is where the player spawns, and a level with no first room is not a level
    with one fewer room — it is nothing."""
    if index <= 0:
        raise ValueError('the first room is the level itself — it cannot be '
                         'removed, only edited')
    if index > len(draft.level.then):
        raise ValueError(f'there is no room {index + 1}')
    draft.level.then.pop(index - 1)
    # `where` names a room's place in the FILE, and every entry after the
    # hole just moved. Left stale, the next parse error would send its author to
    # a key that is no longer the one they are looking at.
    for i, h in enumerate(draft.level.then):
        h.where = f'then[{i}].geometry'
    draft.room_index = min(draft.room_index, len(draft.level.rooms) - 1)


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
    # The canvas is not the level: trim the untouched stone margins to one wall
    # thick. `crop` is gameplay-neutral (see its docstring), and this re-runs the
    # validator on the cropped file rather than trusting that — if par came out
    # different, something in the claim is wrong and the author must hear it
    # instead of shipping a level whose budget no longer matches its route.
    shipped = F.crop(draft.level)
    if shipped is not draft.level:
        crop_rep = validate(shipped)
        if not crop_rep.ok or crop_rep.par != rep.par:
            return None, crop_rep if not crop_rep.ok else rep
        rep = crop_rep
    LEVELS_DIR.mkdir(parents=True, exist_ok=True)
    dest = LEVELS_DIR / f'{_slug(draft.level.name)}.json'
    dest.write_text(F.dumps(shipped), encoding='utf-8')
    return dest, rep
