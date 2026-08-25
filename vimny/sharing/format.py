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

"""The community level format: geometry, content directives, and a tape.

**A level is data, never code.** A shipped level is a Python function; a
community level must not be, because "download a level" would then mean "run a
stranger's Python" and no amount of review fixes that. The format is the
security boundary, so it is purely declarative — parsed into a `Room`, never
executed. No expressions, no callables, no import hooks. Anything an author
cannot express here is a gap in the schema to fill deliberately, never an escape
hatch. This is the one decision that cannot be revisited cheaply.

JSON rather than YAML: it is in the standard library, and the game ships with a
single runtime dependency. Nothing in the format needs YAML's expressiveness,
and YAML's implicit typing is a footgun for a file strangers author.

Fills resolve at BUILD time against the level's own seed, so the level is
byte-identical for the author who recorded the tape and every player who
replays it. A directive that resolved differently for the two would leave the
tape pointing at words that are no longer there.
"""
from __future__ import annotations

import json
import math
import random
import re
from dataclasses import dataclass, field, replace

from vimny.engine import tape as _tape
from vimny.engine.editor import (_CELL_CODE, _CODE_CELL, _UNDERWATER_CODE,
                                 _ENTITY_FIELDS)
from vimny.engine.motion import apply_stone_fog
from vimny.engine.world import (CellType, CharRun, DROPPABLE, Entity,
                          Room as LiveRoom, RoomType,
                          Seal, canonical_kind)
from vimny.generation.dungeon_gen import Dungeon
from vimny.sharing import vocab

SCHEMA = 1

#: Commands every player has, at every point in the curriculum.
ALWAYS_ON = ('u', ':w', ':q', ':q!')

MAX_ROWS, MAX_COLS = 200, 200     # _MAX_COLS in the reflow engine is 200
MAX_ROOMS       = 8            # a level is a descent, not a dungeon crawl
MAX_ENTITIES       = 400
MAX_FILLS          = 64
MAX_SEALS          = 32
MAX_SEAL_CELLS     = 64           # cells one seal may open — a door, not a demolition
MAX_SEAL_UNVEILS   = 4096        # cells one seal may reveal — a whole hall is fine
MAX_SEAL_MATCH     = 200          # a password, not a paragraph (and ≤ MAX_COLS)
MAX_VOCAB_WORDS    = 500
MAX_WORD_LEN       = 20
MAX_TAPE           = 4000

_RLE = re.compile(r'(\d*)([A-Z])')


class LevelFormatError(ValueError):
    """A level file the parser cannot make a Room out of. Always names the field."""


@dataclass
class Fill:
    """`fill this region with random words from a pool`.

    The directive the whole feature was asked for: an author says what a floor
    should be made of instead of painting every cell.
    """
    region:  tuple            # (r1, c1, r2, c2) inclusive
    pool:    str   = 'plain'
    length:  tuple = (3, 6)   # inclusive word-length range
    spacing: int   = 1        # blank cells between words
    kind:    str   = 'ancient'

    def covers(self, row: int, col: int) -> bool:
        r1, c1, r2, c2 = self.region
        return min(r1, r2) <= row <= max(r1, r2) and min(c1, c2) <= col <= max(c1, c2)


def in_fill(room, row: int, col: int):
    """The fill covering (row, col), or None. The editor's lock and the export's
    drop-list both ask this, so they can never disagree about where a fill ends."""
    for f in getattr(room, 'fills', ()):
        if f.covers(row, col):
            return f
    return None


@dataclass
class Room:
    """One room of a level: a room's worth of geometry and content.

    A level is a DESCENT, not a map — rooms are walked in order, each one's
    exit is the next one's door, and there is no going back. That is the shape
    both multi-room levels in the game already have, and it is the only shape
    worth putting in a file: a room GRAPH would need doors that name rooms, a
    way to say which door you came in by, and a spawn per door, and none of it
    buys a level anybody has wanted to write.

    ROOM, not "chamber" and not "hall". A CHAMBER is a part of one map joined
    to the rest of it by a hallway or a door — what `main._hall_of_echoes_tick`
    calls its segments, all of them inside a single grid you can walk across.
    These are not that: each one is its own grid, and they are what
    `dungeon.rooms` already holds, so "room" is the word the engine was using
    for them all along. ("Hall" is worse than either: six shipped levels are
    NAMED Halls and one of them is a slug.)

    That does mean this module has two Rooms in it. `Room` here is a room AS
    WRITTEN — geometry and content, inert. The engine's live buffer class is
    imported as `LiveRoom`, and `build` turns each of these into one of those.

    The first room is the level's own `geometry` and content keys, so the
    overwhelmingly common one-room level reads exactly as it always has. The
    rest are `then` — which is also why they are not called `rooms[1:]`: an
    author who writes `then[0]` should get the room AFTER the first, and a
    list whose zeroth entry was the second room is a trap laid on line one.
    """
    rows:      int   = 20
    cols:      int   = 80
    cells:     list  = field(default_factory=list)
    spawn:     tuple = (1, 1)
    exit:      tuple = (1, 2)
    fills:     list  = field(default_factory=list)
    seals:     list  = field(default_factory=list)
    char_runs: list  = field(default_factory=list)
    entities:  list  = field(default_factory=list)
    #: A WRAP BUFFER: one logical line that `:set wrap` folds across screen
    #: rows. `wrap` turns it on (the room must be `rows: 1`); `wrap_width` pins
    #: the fold, and 0 — the default — means REACTIVE: fold to whatever the
    #: reader's terminal is, so the same line has a different number of display
    #: rows at 80 columns than at 189. The Archivist's Library and the
    #: Wardenverse are both this; the Wardenverse is the reactive one, and its
    #: segment walls are spaced so `gj`/`gk` clear exactly one at ANY width.
    wrap:       bool  = False
    wrap_width: int   = 0
    #: VEILED plaques: wall cells whose carving is not legible yet. Declared
    #: rather than derived, because unlike fog it is not a fact about the walls
    #: — it is the level handing out its clue in instalments, and only the
    #: author knows the instalments. Listed as [row, col] pairs.
    veiled:     list  = field(default_factory=list)
    #: UNDERWATER ground off the water: permanent sunken terrain over cells
    #: that are not a river cell. The `M` cell code says water-under-haze
    #: inline; this list says the rest — [row, col] pairs, unioned with
    #: whatever the `M`s said, so an author may write it either way and a
    #: captured room writes back exactly what it carried. (Walls want
    #: `veiled`: underwater is ground you cannot stand on, veiling is a
    #: carving not legible yet.) The file key was `mist` until 2026-08-23 and
    #: is still read under that name — a format never orphans its own files.
    braziers:   list  = field(default_factory=list)
    underwater: list  = field(default_factory=list)
    #: Where this room's keys live in the FILE. Carried on it so that every
    #: message about it — parser, validator, forge — names the place the author
    #: has to go and edit, rather than a room number they never wrote down.
    where:     str   = 'geometry'

    def at(self, key: str) -> str:
        """`'entities'` → `'then[0].entities'` — where one of this room's
        other keys lives in the file."""
        return self.where[:-len('geometry')] + key


@dataclass
class Level:
    name:        str
    author:      str  = ''
    seed:        int  = 0
    teaches:     list = field(default_factory=list)
    requires:    list = field(default_factory=list)
    no_horse:    bool = False
    alternate:   str | None = None    # a shipped slug this level offers to replace
    rows:        int  = 20
    cols:        int  = 80
    cells:       list = field(default_factory=list)   # list[str] of cell codes
    spawn:       tuple = (1, 1)
    exit:        tuple = (1, 2)
    wrap:        bool = False                         # see Room.wrap
    wrap_width:  int  = 0
    veiled:      list = field(default_factory=list)   # see Room.veiled
    underwater:  list = field(default_factory=list)   # see Room.underwater
    braziers:    list = field(default_factory=list)   # see Room.braziers
    fills:       list = field(default_factory=list)   # list[Fill]
    seals:       list = field(default_factory=list)   # list[world.Seal]
    char_runs:   list = field(default_factory=list)   # explicit text
    entities:    list = field(default_factory=list)   # list[dict]
    then:        list = field(default_factory=list)   # list[Room] — 2..n
    vocabulary:  list = field(default_factory=list)   # author's own words
    solution:    str  = ''
    intro:       str  = ''

    @property
    def rooms(self) -> list:
        """Every room, in walking order — the level's own keys, then `then`.

        A projection, not storage: the first room's fields ARE the Level's,
        so there is no second copy to keep in step and a one-room level has
        nothing extra in it. Everything downstream loops over this and stops
        caring how many rooms there are.
        """
        return [Room(rows=self.rows, cols=self.cols, cells=self.cells,
                     spawn=self.spawn, exit=self.exit,
                     wrap=self.wrap, wrap_width=self.wrap_width,
                     veiled=self.veiled, underwater=self.underwater,
                     braziers=self.braziers, fills=self.fills,
                     seals=self.seals, char_runs=self.char_runs,
                     entities=self.entities), *self.then]

    @property
    def all_fills(self) -> list:
        """Every fill in the level, in room order — which is also how a tape
        counts them: `<fill4.0>` is the level's fifth fill, wherever it stands.
        Numbering them per room would make a reference mean a different word
        depending on which one you read it in, and a tape is one string with no
        room of its own."""
        return [f for c in self.rooms for f in c.fills]

    @property
    def known(self) -> list:
        """The command set a player of this level is assumed to have.

        A community level has no curriculum position to derive one from, so it
        declares it: what it assumes (`requires`), what it introduces
        (`teaches`), and the always-on set nobody has to learn.
        """
        return list(dict.fromkeys([*self.requires, *self.teaches, *ALWAYS_ON]))


# ── Parsing ───────────────────────────────────────────────────────────────────

def parse(data: dict) -> Level:
    """Turn a decoded level file into a `Level`. Raises LevelFormatError."""
    if not isinstance(data, dict):
        raise LevelFormatError('level file must be a JSON object')
    schema = data.get('schema')
    if schema != SCHEMA:
        raise LevelFormatError(
            f'schema: expected {SCHEMA}, got {schema!r}. This level was written '
            f'for a different version of the format.')

    unknown = set(data) - {'schema', 'name', 'author', 'seed', 'teaches',
                           'requires', 'no_horse', 'alternate', 'geometry',
                           'fill', 'seals', 'char_runs', 'entities', 'veiled',
                           'braziers',
                           'underwater', 'mist',   # mist: the pre-2026-08-23 name
                           'then', 'vocabulary', 'solution', 'intro'}
    if unknown:
        # Refuse rather than ignore: a silently-dropped key is a level that
        # plays differently from the one its author tested.
        raise LevelFormatError(f'unknown top-level key(s): {sorted(unknown)}')

    geo = data.get('geometry')
    if not isinstance(geo, dict):
        raise LevelFormatError('geometry: required, and must be an object')

    lvl = Level(
        name=str(data.get('name', '')).strip(),
        author=str(data.get('author', '')).strip(),
        seed=int(data.get('seed', 0)),
        teaches=list(data.get('teaches', [])),
        requires=list(data.get('requires', [])),
        no_horse=bool(data.get('no_horse', False)),
        alternate=data.get('alternate'),
        rows=int(geo.get('rows', 0)),
        cols=int(geo.get('cols', 0)),
        cells=list(geo.get('cells', [])),
        spawn=tuple(geo.get('spawn', (1, 1))),
        exit=tuple(geo.get('exit', (1, 2))),
        wrap=bool(geo.get('wrap', False)),
        wrap_width=int(geo.get('wrap_width', 0)),
        veiled=_parse_cells_list(data.get('veiled', []), 'veiled', 'veiled'),
        braziers=_parse_cells_list(data.get('braziers', []),
                                   'braziers', 'braziers'),
        # Both names read, and union: `underwater` is canonical, `mist` is
        # what every file written before 2026-08-23 says.
        underwater=(_parse_cells_list(data.get('underwater', []),
                                      'underwater', 'underwater')
                    + _parse_cells_list(data.get('mist', []), 'mist', 'mist')),
        fills=[_parse_fill(f, i) for i, f in enumerate(data.get('fill', []))],
        seals=[_parse_seal(s, i) for i, s in enumerate(data.get('seals', []))],
        char_runs=list(data.get('char_runs', [])),
        entities=list(data.get('entities', [])),
        then=_parse_then(data.get('then', [])),
        vocabulary=list(data.get('vocabulary', [])),
        solution=str(data.get('solution', '')),
        intro=str(data.get('intro', '')),
    )
    if not lvl.name:
        raise LevelFormatError('name: required')
    return lvl


def _parse_fill(f: dict, i: int, at: str = 'fill') -> Fill:
    if not isinstance(f, dict):
        raise LevelFormatError(f'{at}[{i}]: must be an object')
    region = f.get('region')
    if not (isinstance(region, (list, tuple)) and len(region) == 4):
        raise LevelFormatError(f'{at}[{i}].region: must be [r1, c1, r2, c2]')
    length = f.get('length', [3, 6])
    if isinstance(length, int):
        length = [length, length]
    if not (isinstance(length, (list, tuple)) and len(length) == 2):
        raise LevelFormatError(f'{at}[{i}].length: must be n or [min, max]')
    return Fill(region=tuple(int(x) for x in region),
                pool=str(f.get('pool', 'plain')),
                length=(int(length[0]), int(length[1])),
                spacing=int(f.get('spacing', 1)),
                kind=str(f.get('kind', 'ancient')))


_SEAL_MODES  = ('exact', 'contains', 'braziers', 'gone')
_SEAL_SCOPES = ('region', 'anyrow')


def _parse_seal(s: dict, i: int, at: str = 'seals') -> Seal:
    """One `seals` entry → a `world.Seal`.

    Every failure names the field and says what was wanted, because a seal is the
    one directive whose mistake is invisible: a mistyped `opens` cell does not
    crash, it simply builds a door that never opens anywhere — and the author
    finds out at the solvability gate, several minutes later, with no clue why.
    """
    if not isinstance(s, dict):
        raise LevelFormatError(f'{at}[{i}]: must be an object')
    unknown = set(s) - {'region', 'match', 'opens', 'unveils', 'mode', 'scope',
                        'requires', 'anchor', 'head', 'at', 'message'}
    if unknown:
        raise LevelFormatError(f'{at}[{i}]: unknown key(s) {sorted(unknown)}')
    scope = str(s.get('scope', 'region'))
    if scope not in _SEAL_SCOPES:
        raise LevelFormatError(f'{at}[{i}].scope: must be one of '
                               f'{", ".join(_SEAL_SCOPES)}, got {scope!r}')
    mode = str(s.get('mode', 'exact'))
    if mode not in _SEAL_MODES:
        raise LevelFormatError(f'{at}[{i}].mode: must be one of '
                               f'{", ".join(_SEAL_MODES)}, got {mode!r}')
    # `match` may be one string or several, ALL of which must read true. A door
    # that wants a room's three sayings held at once is one seal, not three.
    match = s.get('match', [])
    if isinstance(match, str):
        match = [match] if match else []
    region = s.get('region')
    # A `braziers` seal reads no TEXT: it opens while every brazier standing in
    # its region burns. So it wants a region and refuses a `match`.
    if mode == 'braziers':
        if match:
            raise LevelFormatError(f'{at}[{i}].match: a mode="braziers" seal reads '
                                   f'braziers, not text — leave `match` empty')
        if not (isinstance(region, (list, tuple)) and len(region) == 4):
            raise LevelFormatError(f'{at}[{i}].region: a mode="braziers" seal needs '
                                   f'[r1, c1, r2, c2] naming the braziers to light')
        region = tuple(int(x) for x in region)
        match = []
    elif mode == 'gone':
        # A `gone` seal reads no TEXT either: its `match` names ENTITY KINDS,
        # and it stands open while no live entity of any named kind remains —
        # the legion rule ("no goblin draws breath"). It reads the whole room,
        # so, like braziers, it refuses the axis it does not use — here
        # `region`.
        if not match:
            raise LevelFormatError(f'{at}[{i}].match: a mode="gone" seal names '
                                   f'the entity kind(s) that must be gone, '
                                   f'e.g. "goblin"')
        if region is not None:
            raise LevelFormatError(f'{at}[{i}].region: a mode="gone" seal reads '
                                   f'the whole room — leave `region` empty')
        region = ()
    elif scope == 'region' and match:
        if not (isinstance(region, (list, tuple)) and len(region) == 4):
            raise LevelFormatError(f'{at}[{i}].region: must be [r1, c1, r2, c2]')
        region = tuple(int(x) for x in region)
    elif region:
        raise LevelFormatError(
            f'{at}[{i}].region: this seal reads no region — '
            + ('a scope="anyrow" seal reads every floor row'
               if scope == 'anyrow' else
               'a seal with no `match` reads only the seals it requires'))
    else:
        region = ()
    if not isinstance(match, (list, tuple)) or not all(
            isinstance(m, str) and m.strip() for m in match):
        raise LevelFormatError(f'{at}[{i}].match: must be the text the seal has '
                               f'to read, or a list of texts, none of them empty')
    if any(len(m) > MAX_SEAL_MATCH for m in match):
        raise LevelFormatError(f'{at}[{i}].match: at most {MAX_SEAL_MATCH} characters')
    requires = s.get('requires', [])
    if not isinstance(requires, (list, tuple)) or not all(
            isinstance(k, int) for k in requires):
        raise LevelFormatError(f'{at}[{i}].requires: must be a list of the '
                               f'indices of earlier seals')
    if any(not 0 <= k < i for k in requires):
        # Earlier-only is what makes the conjunction one pass with no cycle to
        # find. A seal that named a later one would open on a reading that had
        # not been taken yet, which is a rule nobody can debug.
        raise LevelFormatError(f'{at}[{i}].requires: must name seals BEFORE '
                               f'this one (0..{i - 1})')
    if not match and not requires and mode != 'braziers':
        raise LevelFormatError(f'{at}[{i}]: has nothing to read — give it a '
                               f'`match`, or `requires` naming earlier seals')
    anchor = str(s.get('anchor', ''))
    if anchor not in ('', 'exit_row'):
        raise LevelFormatError(f'{at}[{i}].anchor: must be "" or "exit_row", '
                               f'got {anchor!r}')
    # `head` is the left-align law made declarative: under anyrow scope, a
    # matched row's first glyph must sit exactly at this column. It names a
    # MARGIN, and only the row reader has one — the region reader strips each
    # line before comparing, so a head beside region would be a promise about
    # whitespace the format then throws away.
    head = s.get('head', -1)
    if head is None:
        head = -1
    if not isinstance(head, int) or isinstance(head, bool) or head < -1:
        raise LevelFormatError(f'{at}[{i}].head: must be a column number '
                               f'(>= 0) naming where matched rows must start')
    if head >= 0 and scope != 'anyrow':
        raise LevelFormatError(f'{at}[{i}].head: needs scope="anyrow" — a '
                               f'region seal strips its lines, so it cannot '
                               f'check a margin')
    # `at` is the PIN law: the target's first glyph stands exactly at this
    # column, whatever sits west of it. Sibling of `head`, opposite verdict on
    # the row's west end — one seal naming both would promise two margins, so
    # it is refused rather than resolved.
    pin = s.get('at', -1)
    if pin is None:
        pin = -1
    if not isinstance(pin, int) or isinstance(pin, bool) or pin < -1:
        raise LevelFormatError(f'{at}[{i}].at: must be a column number '
                               f'(>= 0) pinning where the target must stand')
    if pin >= 0 and head >= 0:
        raise LevelFormatError(f'{at}[{i}].at: a seal may name a margin '
                               f'(`head`) or a pin (`at`), not both')
    if pin >= 0 and scope != 'anyrow':
        raise LevelFormatError(f'{at}[{i}].at: needs scope="anyrow" — a region '
                               f'seal reads its rectangle as one collapsed '
                               f'page, with no columns left to pin')
    opens = s.get('opens') or []
    # A single [row, col] is allowed and is by far the common case: most doors
    # are one cell, and making an author write [[9, 40]] to say so is a papercut
    # they meet on their first seal.
    if (isinstance(opens, (list, tuple)) and len(opens) == 2
            and all(isinstance(v, int) for v in opens)):
        opens = [opens]
    if not isinstance(opens, (list, tuple)):
        raise LevelFormatError(f'{at}[{i}].opens: must be [row, col] or a list of them')
    # An EMPTY `opens` is a pure predicate — something to read, no cell to
    # stand open. Legal because the nothing-to-read guard above already ran:
    # this seal has a `match` or names earlier seals through `requires`, so it
    # is a reading other seals reach by index, not a door someone mistyped.
    if len(opens) > MAX_SEAL_CELLS:
        raise LevelFormatError(f'{at}[{i}].opens: at most {MAX_SEAL_CELLS} cells')
    cells = []
    for j, cell in enumerate(opens):
        if not (isinstance(cell, (list, tuple)) and len(cell) == 2):
            raise LevelFormatError(f'{at}[{i}].opens[{j}]: must be [row, col]')
        cells.append((int(cell[0]), int(cell[1])))
    # `unveils` — the same shape as opens, a different effect: these are
    # VEILED cells whose carving becomes legible while the seal reads true.
    # A seal may open, unveil, both, or (as a pure predicate) neither; what
    # it may never be is nothing at all — the match/requires guard above
    # already refuses a seal with no condition.
    unveils_in = s.get('unveils') or []
    if (isinstance(unveils_in, (list, tuple)) and len(unveils_in) == 2
            and all(isinstance(v, int) for v in unveils_in)):
        unveils_in = [unveils_in]
    if not isinstance(unveils_in, (list, tuple)):
        raise LevelFormatError(
            f'{at}[{i}].unveils: must be [row, col] or a list of them')
    if len(unveils_in) > MAX_SEAL_UNVEILS:
        raise LevelFormatError(
            f'{at}[{i}].unveils: at most {MAX_SEAL_UNVEILS} cells')
    unveiled = []
    for j, cell in enumerate(unveils_in):
        if not (isinstance(cell, (list, tuple)) and len(cell) == 2):
            raise LevelFormatError(f'{at}[{i}].unveils[{j}]: must be [row, col]')
        unveiled.append((int(cell[0]), int(cell[1])))
    # The banner shown when this statement transitions to true — AUTHOR DATA
    # since 2026-08-24 (it used to be engine-only). Capped and flattened: it
    # is one status line, not a letter.
    msg = ' '.join(str(s.get('message', ''))[:200].split())
    return Seal(region=region, match=tuple(match), opens=tuple(cells),
                unveils=tuple(unveiled), mode=mode, message=msg,
                scope=scope, requires=tuple(requires), anchor=anchor,
                head=head, at=pin)


def _parse_cells_list(pairs, at: str, what: str) -> list:
    """A room-level coordinate layer (`veiled`, `underwater`): a list of
    [row, col] pairs. Refused rather than coerced — a silently-dropped cell is
    a level that plays differently from the one its author tested."""
    if not isinstance(pairs, (list, tuple)):
        raise LevelFormatError(f'{at}: must be a list of [row, col] pairs')
    out = []
    for i, v in enumerate(pairs):
        if not (isinstance(v, (list, tuple)) and len(v) == 2
                and all(isinstance(x, int) and not isinstance(x, bool)
                        for x in v)):
            raise LevelFormatError(
                f'{at}[{i}]: must be a [row, col] pair of integers')
        out.append(tuple(v))
    return out


def _parse_then(rooms) -> list:
    """The `then` list → rooms 2..n. Every message names `then[i].{key}`."""
    if not isinstance(rooms, (list, tuple)):
        raise LevelFormatError('then: must be a list of rooms, each with its '
                               'own `geometry`')
    if len(rooms) > MAX_ROOMS - 1:
        raise LevelFormatError(f'then: a level may have at most {MAX_ROOMS} '
                               f'rooms, got {len(rooms) + 1}')
    out = []
    for i, h in enumerate(rooms):
        at = f'then[{i}]'
        if not isinstance(h, dict):
            raise LevelFormatError(f'{at}: must be an object')
        unknown = set(h) - {'geometry', 'fill', 'seals', 'char_runs',
                            'entities', 'veiled', 'underwater', 'mist'}
        if unknown:
            # Deliberately narrower than the top level: a room is geometry
            # and content, and everything else — the tape, the seed, what the
            # level teaches — belongs to the LEVEL. A `solution` inside a
            # room would read as a second tape and there is only ever one.
            raise LevelFormatError(f'{at}: unknown key(s) {sorted(unknown)}; a '
                                   f'room carries geometry and content only')
        geo = h.get('geometry')
        if not isinstance(geo, dict):
            raise LevelFormatError(f'{at}.geometry: required, and must be an object')
        out.append(Room(
            rows=int(geo.get('rows', 0)),
            cols=int(geo.get('cols', 0)),
            cells=list(geo.get('cells', [])),
            spawn=tuple(geo.get('spawn', (1, 1))),
            exit=tuple(geo.get('exit', (1, 2))),
            wrap=bool(geo.get('wrap', False)),
            wrap_width=int(geo.get('wrap_width', 0)),
            veiled=_parse_cells_list(h.get('veiled', []), f'{at}.veiled', 'veiled'),
            braziers=_parse_cells_list(h.get('braziers', []),
                                   f'{at}.braziers', 'braziers'),
            underwater=(_parse_cells_list(h.get('underwater', []),
                                          f'{at}.underwater', 'underwater')
                        + _parse_cells_list(h.get('mist', []), f'{at}.mist', 'mist')),
            fills=[_parse_fill(f, j, f'{at}.fill')
                   for j, f in enumerate(h.get('fill', []))],
            seals=[_parse_seal(s, j, f'{at}.seals')
                   for j, s in enumerate(h.get('seals', []))],
            char_runs=list(h.get('char_runs', [])),
            entities=list(h.get('entities', [])),
            where=f'{at}.geometry'))
    return out


def loads(text: str) -> Level:
    try:
        return parse(json.loads(text))
    except json.JSONDecodeError as exc:
        raise LevelFormatError(f'not valid JSON: {exc}') from None
    except (TypeError, ValueError, KeyError, AttributeError) as exc:
        # Valid JSON, wrong shape (a string where a list belongs, a float seed,
        # `spawn` with two entries…) must reach every caller as the named error
        # — one malformed file may never take down a whole shelf listing.
        raise LevelFormatError(f'malformed level file: {exc}') from None


# ── Cell grids ────────────────────────────────────────────────────────────────

def expand_row_underwater(row: str, cols: int, lineno: int,
                          where: str = 'geometry') -> tuple:
    """One `cells` row → (list of CellTypes, the columns that carry water).

    Accepts both the plain form (`WFFFW`) and the run-length form (`W3F60W`),
    because a 200-column room of mostly stone is unreadable written out in full
    and unreviewable in a pull request.

    `M` is ground with permanent haze over it. It expands to WATER here and
    the haze comes back as a column number, because being underwater is not a
    cell type — see `_UNDERWATER_CODE`. (The code was named `_MIST_CODE`; the
    glyph is 'M' for history.)
    """
    out, underwater = [], []
    pos = 0
    for m in _RLE.finditer(row):
        if m.start() != pos:
            raise LevelFormatError(
                f'{where}.cells[{lineno}]: unexpected {row[pos]!r} at column {pos}')
        pos = m.end()
        count = int(m.group(1)) if m.group(1) else 1
        code  = m.group(2)
        if len(out) + count > cols:
            # Bail BEFORE expanding: an unbounded count (`W999999999F`) would
            # allocate first and only then fail the length check below.
            raise LevelFormatError(
                f'{where}.cells[{lineno}]: run of {count} {code!r} runs past {cols} columns')
        if code == _UNDERWATER_CODE:
            underwater.extend(range(len(out), len(out) + count))
            out.extend([CellType.WATER] * count)
            continue
        if code not in _CODE_CELL:
            raise LevelFormatError(
                f'{where}.cells[{lineno}]: unknown cell code {code!r}; '
                f'known codes are {"".join(sorted(set(_CODE_CELL) | {_UNDERWATER_CODE}))}')
        out.extend([_CODE_CELL[code]] * count)
    if pos != len(row):
        raise LevelFormatError(
            f'{where}.cells[{lineno}]: unexpected {row[pos]!r} at column {pos}')
    if len(out) != cols:
        raise LevelFormatError(
            f'{where}.cells[{lineno}]: expands to {len(out)} cells, expected {cols}')
    return out, underwater


def expand_row(row: str, cols: int, lineno: int,
               where: str = 'geometry') -> list:
    """One `cells` row → a list of CellTypes, the water discarded."""
    return expand_row_underwater(row, cols, lineno, where)[0]


def encode_row(cells: list, underwater_cols=()) -> str:
    """The inverse of expand_row_underwater, run-length encoded."""
    out, run, prev = [], 0, None
    underwater_cols = set(underwater_cols)
    for i, ct in enumerate(cells):
        code = _UNDERWATER_CODE if i in underwater_cols and ct == CellType.WATER else _CELL_CODE[ct]
        if code == prev:
            run += 1
        else:
            if prev is not None:
                out.append(f'{run if run > 1 else ""}{prev}')
            prev, run = code, 1
    if prev is not None:
        out.append(f'{run if run > 1 else ""}{prev}')
    return ''.join(out)


def crop(lvl: Level) -> Level:
    """The same level with its blank stone margins trimmed to one wall thick.

    The forge hands an author a big canvas — you cannot select a region larger
    than the room you are standing in, so the room has to be bigger than
    anything anyone might want to draw. What ships should be the level, not the
    canvas: a 100x100 file that is 94 rows of untouched stone is a level nobody
    can read the diff of, and a viewport that starts by scrolling through
    nothing.

    Cropping is gameplay-neutral, which is why it can be done silently. Solid
    stone is not a LINE — `gg`, `G` and the line numbers count from the first
    standable row — and `$`/`0` stop at the walls that bound their own segment,
    so removing whole rows and columns that contain nothing but wall changes no
    motion, no distance and no par. One wall row and column are kept on every
    side, because a room needs a border and content flush against the edge of
    the grid is content with nothing to stop a motion.
    """
    # `lvl.rooms` is a fresh projection every time it is asked for, so it is
    # asked for ONCE: the identity `_crop_room` returns to say "nothing to
    # take off" is only meaningful against the very objects it was handed.
    before   = lvl.rooms
    rooms = [_crop_room(c) for c in before]
    if all(a is b for a, b in zip(rooms, before)):
        return lvl                               # every room already tight
    first = rooms[0]
    return replace(
        lvl,
        rows=first.rows, cols=first.cols, cells=first.cells,
        spawn=first.spawn, exit=first.exit,
        wrap=first.wrap, wrap_width=first.wrap_width, veiled=first.veiled,
        underwater=first.underwater,
        fills=first.fills,
        seals=first.seals, char_runs=first.char_runs, entities=first.entities,
        then=rooms[1:],
    )


def _crop_room(h: Room) -> Room:
    """One room, trimmed. Returns `h` itself when there is nothing to take
    off — which is how `crop` tells a level that needs no cropping from one that
    does, and why a level whose every room is already tight is returned
    unchanged rather than rebuilt into an equal copy.

    Each room is trimmed on its OWN margins: they are separate grids that
    only ever share a level, and one cropped to the width of its neighbour would
    be padded with stone for no reason but tidiness.
    """
    grid = [expand_row(row, h.cols, i, h.where) for i, row in enumerate(h.cells)]
    keep = set()
    for r, row in enumerate(grid):
        for c, ct in enumerate(row):
            if ct != CellType.WALL:
                keep.add((r, c))
    for ru in h.char_runs:
        for i in range(len(ru['symbols'])):
            keep.add((int(ru['row']), int(ru['col']) + i))
    for e in h.entities:
        keep.add((int(e['at'][0]), int(e['at'][1])))
    for f in h.fills:
        keep.add((f.region[0], f.region[1]))
        keep.add((f.region[2], f.region[3]))
    for s in h.seals:
        keep.add((s.region[0], s.region[1]))
        keep.add((s.region[2], s.region[3]))
        keep.update(tuple(c) for c in s.opens)
    keep.add(tuple(h.spawn))
    keep.add(tuple(h.exit))
    if not keep:
        return h
    r1 = max(0, min(r for r, _ in keep) - 1)
    r2 = min(h.rows - 1, max(r for r, _ in keep) + 1)
    c1 = max(0, min(c for _, c in keep) - 1)
    c2 = min(h.cols - 1, max(c for _, c in keep) + 1)
    if (r1, c1, r2, c2) == (0, 0, h.rows - 1, h.cols - 1):
        return h                                     # already tight

    def _mv(pos):
        return (int(pos[0]) - r1, int(pos[1]) - c1)

    sunken = {(r, c) for r, row in enumerate(h.cells)
              for c in expand_row_underwater(row, h.cols, r, h.where)[1]}
    return replace(
        h,
        rows=r2 - r1 + 1, cols=c2 - c1 + 1,
        cells=[encode_row(grid[r][c1:c2 + 1],
                          [c - c1 for (mr, c) in sunken if mr == r])
               for r in range(r1, r2 + 1)],
        spawn=_mv(h.spawn), exit=_mv(h.exit),
        char_runs=[{**ru, 'row': int(ru['row']) - r1, 'col': int(ru['col']) - c1}
                   for ru in h.char_runs],
        entities=[{**e, 'at': list(_mv(e['at']))} for e in h.entities],
        fills=[replace(f, region=(f.region[0] - r1, f.region[1] - c1,
                                  f.region[2] - r1, f.region[3] - c1))
               for f in h.fills],
        seals=[replace(s, opens=tuple(_mv(c) for c in s.opens),
                       region=((s.region[0] - r1, s.region[1] - c1,
                                s.region[2] - r1, s.region[3] - c1)
                               if s.region else ()))
               for s in h.seals],
    )


def resize(lvl: Level, rows: int, cols: int) -> Level:
    """The same level on a bigger (or smaller) canvas. `crop`'s deliberate half.

    Crop is automatic and silent because it only ever takes off stone nobody
    touched. Growing cannot be automatic — nothing in a level says how much room
    its author still wants — so it is a command, and this is what it does.

    Everything is anchored at the TOP-LEFT, which is what makes it safe: the new
    stone goes on at the bottom and the right, so not one existing cell, entity,
    fill region or mark changes its coordinates, and a tape recorded before the
    resize still plays. (Anchoring in the middle would move every row and column
    and silently invalidate every one of them.)

    Shrinking is allowed as far as the content: it is refused the moment it
    would cut something, rather than dropping it, because a level quietly
    missing the exit is worse than a level that would not resize.
    """
    if not 3 <= rows <= MAX_ROWS or not 3 <= cols <= MAX_COLS:
        raise LevelFormatError(f'a canvas is 3..{MAX_ROWS} by 3..{MAX_COLS}')
    h = lvl.rooms[0]
    if (rows, cols) == (h.rows, h.cols):
        return lvl
    if rows < h.rows or cols < h.cols:
        used = _content_extent(h)
        # `rows - 2`, not `rows - 1`: the last row and column are the border, and
        # content flush against the edge of the grid is content with nothing to
        # stop a motion. Crop keeps that wall too.
        if used and (used[0] > rows - 2 or used[1] > cols - 2):
            raise LevelFormatError(
                f'the level reaches row {used[0]}, column {used[1]} — '
                f'a smaller canvas would cut it')
    grid = [expand_row(row, h.cols, i, h.where) for i, row in enumerate(h.cells)]
    sunken = {(r, c) for r, row in enumerate(h.cells)
              for c in expand_row_underwater(row, h.cols, r, h.where)[1]}
    stone = [CellType.WALL] * cols
    out   = []
    for r in range(rows):
        row = (grid[r][:cols] + stone[h.cols:cols]) if r < h.rows else stone
        out.append(encode_row(row, [c for (mr, c) in sunken if mr == r and c < cols]))
    return replace(lvl, rows=rows, cols=cols, cells=out)


def paste(level: Level, into: Level, at: tuple) -> Level:
    """Stamp a single-room level onto another level's canvas.

    The fragment's top-left cell lands on `at = (row, col)`. Everything
    positional moves with it — the cells (and the water encoded inside them),
    fills, seals, char runs, entities and veiled plaques — and the host keeps
    its own name, spawn, exit, seed and curriculum identity. A fragment is
    geometry and content, no doors: its `spawn`/`exit` are ignored, because
    where you come in and where you leave are decisions about the WHOLE map,
    which is exactly what hall-of-echoes-style composition wants. The host's
    fills are numbered before the fragment's (`all_fills` order), so tape
    references to the HOST's fills keep meaning what they meant; references to
    the fragment's own fills would move anyway — a paste rewrites coordinates,
    and a solution recorded against the fragment's canvas stops playing at the
    offset. The host level writes its own tape.

    Refusals, all naming their field:
      * a fragment with `then` rooms — stacking descents is not an operation;
      * either side a wrap buffer — one folded logical line does not compose
        onto a grid, and a reactive fold's geometry is reader-dependent;
      * the footprint off the canvas — resize the host first, explicitly;
      * any destination cell that is not untouched stone — paste stamps stone
        onto stone only, so an import can never silently overwrite somebody's
        floor (the rule resize set: refuse rather than drop).

    The fragment's border ring is walls like any room's, so a legal paste
    welds it seamlessly into the surrounding bands.
    """
    src = level.rooms[0]
    dst = into.rooms[0]
    if level.then:
        raise LevelFormatError(
            f'paste: a fragment must be one room — this level carries '
            f'{len(level.then)} `then` room(s), and stacking descents is '
            f'not an operation')
    if src.wrap or src.wrap_width:
        raise LevelFormatError(
            'paste: the fragment is a wrap buffer — one folded logical line '
            'does not compose onto a grid')
    if dst.wrap or dst.wrap_width:
        raise LevelFormatError(
            'into: the host is a wrap buffer — paste composes plain grids only')

    dr, dc = int(at[0]), int(at[1])
    if dr < 0 or dc < 0:
        raise LevelFormatError(
            f'at: ({dr}, {dc}) — negative offsets have no meaning for a '
            f'top-left landing point')
    if dr + src.rows > dst.rows or dc + src.cols > dst.cols:
        raise LevelFormatError(
            f'at: a {src.rows}x{src.cols} fragment at ({dr}, {dc}) reaches '
            f'row {dr + src.rows - 1}, column {dc + src.cols - 1}, past the '
            f'host canvas of {dst.rows}x{dst.cols} — resize(into, …) first')

    grid = [expand_row_underwater(row, dst.cols, i, dst.where)
            for i, row in enumerate(dst.cells)]
    frag = [expand_row_underwater(row, src.cols, i, src.where)
            for i, row in enumerate(src.cells)]
    for r in range(dr, dr + src.rows):
        dcells = grid[r][0]
        for c in range(dc, dc + src.cols):
            if dcells[c] is not CellType.WALL:
                raise LevelFormatError(
                    f'at: ({dr}, {dc}) would land on floor already at row '
                    f'{r}, column {c} — paste stamps stone onto stone only')

    out = []
    for r, (dcells, dsunken) in enumerate(grid):
        if dr <= r < dr + src.rows:
            row = list(dcells)
            fr, fsunken = frag[r - dr]
            row[dc:dc + src.cols] = fr
            # Host water outside the footprint keeps its column; the
            # footprint's comes from the fragment, offset in.
            sunken = {c for c in dsunken if not (dc <= c < dc + src.cols)}
            sunken |= {c + dc for c in fsunken}
            out.append(encode_row(row, sunken))
        else:
            out.append(dst.cells[r])

    def _mv(pos):
        return (int(pos[0]) + dr, int(pos[1]) + dc)

    fills = list(dst.fills) + [
        replace(f, region=(f.region[0] + dr, f.region[1] + dc,
                           f.region[2] + dr, f.region[3] + dc))
        for f in src.fills]
    seals = list(dst.seals) + [
        replace(s,
                opens=tuple(_mv(c) for c in s.opens),
                region=((s.region[0] + dr, s.region[1] + dc,
                         s.region[2] + dr, s.region[3] + dc)
                        if s.region else ()))
        for s in src.seals]
    char_runs = list(dst.char_runs) + [
        {**ru, 'row': int(ru['row']) + dr, 'col': int(ru['col']) + dc}
        for ru in src.char_runs]
    entities = list(dst.entities) + [
        {**e, 'at': list(_mv(e['at']))} for e in src.entities]
    veiled = ([tuple(v) for v in into.veiled] +
              [(int(v[0]) + dr, int(v[1]) + dc) for v in src.veiled])
    underwater = ([tuple(v) for v in into.underwater] +
            [(int(v[0]) + dr, int(v[1]) + dc) for v in src.underwater])
    # A fragment whose fills draw on its OWN vocabulary brings those words:
    # without the union its fills resolve against a pool that does not exist.
    vocabulary = list(into.vocabulary)
    seen = set(vocabulary)
    for w in level.vocabulary:
        if w not in seen:
            seen.add(w)
            vocabulary.append(w)

    return replace(into, cells=out, fills=fills, seals=seals,
                   char_runs=char_runs, entities=entities, veiled=veiled,
                   underwater=underwater, vocabulary=vocabulary)


def _content_extent(h: Room) -> tuple[int, int] | None:
    """The furthest row and column of the room anything at all occupies —
    floor, text, an entity, a fill, a seal, the spawn or the exit."""
    grid = [expand_row(row, h.cols, i, h.where) for i, row in enumerate(h.cells)]
    keep = {(r, c) for r, row in enumerate(grid)
            for c, ct in enumerate(row) if ct != CellType.WALL}
    for ru in h.char_runs:
        keep.add((int(ru['row']), int(ru['col']) + len(ru['symbols']) - 1))
    for e in h.entities:
        keep.add((int(e['at'][0]), int(e['at'][1])))
    for f in h.fills:
        keep.add((f.region[2], f.region[3]))
    for s in h.seals:
        if s.region:
            keep.add((s.region[2], s.region[3]))
        keep.update(tuple(c) for c in s.opens)
    keep.add(tuple(h.spawn))
    keep.add(tuple(h.exit))
    if not keep:
        return None
    return max(r for r, _ in keep), max(c for _, c in keep)


# ── Building ──────────────────────────────────────────────────────────────────

def build(lvl: Level, par: int | None = None, seed: int | None = None) -> Dungeon:
    """Turn a parsed Level into a playable Dungeon.

    `par` is passed in rather than declared, because par is DERIVED from
    replaying the author's tape and never author-set — otherwise an author could
    hand themselves a budget. Until it is known the room carries a generous one
    so the tape can be replayed at all; `finalize_par` then pins both.

    `seed` is what the FILLS grow from, and the play path passes a fresh one
    every run — the same way a shipped level is built from a new random seed
    each time it is entered. A fill is the author saying "a wall of words here",
    not "these words here", and a wall that came out identical for every player
    forever was a hard-coded block of text wearing a directive's clothes.
    Omitted, it falls back to the file's own seed, which is what validation and
    the editor want: a fixed arrangement to reason about. What keeps this honest
    is `_check_fill_stability` — the tape must solve the level, at the same par,
    whichever words grew.
    """
    custom = vocab.by_length([w for w in lvl.vocabulary]) if lvl.vocabulary else None
    # ONE rng for the whole level, drawn on room by room in walking order.
    # Two rooms seeded alike would grow the same wall of words twice, and the
    # second would read as a copy of the first rather than another room in the
    # same dungeon.
    rng = random.Random(lvl.seed if seed is None else seed)

    rooms, slots = [], []
    for spec in lvl.rooms:
        room = _build_room(spec, lvl, rng, custom)
        # The level-wide index of this room's first fill, so `slot_at` can
        # name a word as the tape does no matter which room it stands in.
        room.fill_index0 = len(slots)
        slots.extend(room.fill_slots)
        finalize_par(room, par)
        rooms.append(room)
    # The exit MARKER is the last room's alone: earlier rooms are doors, and a
    # door is a POSITION (standing on exit_pos advances), not an entity. A
    # synthesised marker on a transit room drew the win-portal over the stair,
    # and could be cut away by a text op to free exit_pos out from under the
    # door. A room whose file names its own exit entity keeps it — explicit
    # beats derived — and the last room is given one when it has none.
    if rooms:
        last = rooms[-1]
        if not any(e.kind == 'exit' for e in last.entities):
            last.entities.append(Entity(kind='exit', row=last.exit_pos[0],
                                        col=last.exit_pos[1]))
            last.rebuild_indexes()      # the room indexed its entities already

    # The tape belongs to the LEVEL, not a room: one route walks all of them,
    # and the karaoke position travels with the player through the doors.
    try:
        rooms[0].answer = _tape.resolve_slots(lvl.solution, slots)
    except _tape.UnknownSlot as exc:
        raise LevelFormatError(str(exc)) from None
    # The tape AS WRITTEN, kept so that saving the room back out writes the
    # references the author wrote rather than the one roll they happened to get.
    rooms[0].answer_source = lvl.solution
    # Every room but the last is a door: stand on its exit and the next one
    # begins. Declared on the room rather than asked of the level, because the
    # game loop holds a room and has no way back to the file it came from.
    for room in rooms[:-1]:
        room.advance_on_exit = True

    dungeon = Dungeon(name=lvl.name, seed=lvl.seed)
    dungeon.rooms        = rooms
    dungeon.current_room = 0
    # What this level TEACHES, for the hint bar. A community level has no
    # curriculum position, so the bar cannot look its lesson up by slug — the
    # declaration in the file is the only answer there is.
    dungeon.level_teaches = list(lvl.teaches)
    return dungeon


def _build_room(spec: Room, lvl: Level, rng: random.Random,
                   custom) -> LiveRoom:
    """One room of a level, as written, → one live Room. Everything level-wide
    is passed in."""
    if len(spec.cells) != spec.rows:
        raise LevelFormatError(
            f'{spec.where}.cells: {len(spec.cells)} rows, {spec.where}.rows says '
            f'{spec.rows}')
    grid = [expand_row_underwater(row, spec.cols, i, spec.where)
            for i, row in enumerate(spec.cells)]
    cells = [g[0] for g in grid]
    underwater  = {(r, c) for r, (_, cols) in enumerate(grid) for c in cols}
    # Ground said as a coordinate list unions with whatever the `M` codes
    # said: inline M is water shorthand, the list is every other terrain.
    # Both are the author's water; neither overrides the other.
    underwater |= {(int(a), int(b)) for a, b in getattr(spec, 'underwater', ())}

    room = LiveRoom(room_type=RoomType.ENTRY, rows=spec.rows, cols=spec.cols)
    room.cells     = cells
    room.underwater_cells = set(underwater)
    room.braziers = tuple(tuple(int(x) for x in cell)
                          for cell in getattr(spec, 'braziers', ()))
    room.fog_cells  = set(underwater)  # water is always a subset of the fog
    room.seed      = lvl.seed
    room.spawn_pos = tuple(spec.spawn)
    room.exit_pos  = tuple(spec.exit)
    room.no_horse  = lvl.no_horse
    room.wrap_buffer = bool(spec.wrap)
    room.wrap_width  = int(spec.wrap_width)
    room.veiled_cells = {(int(a), int(b)) for a, b in spec.veiled}

    # Seals are built SHUT, whatever the grid says, and before anything else reads
    # the grid. A `cells` grid is written by `from_room` while the level was being
    # played, so a door that happened to be open at save time would otherwise be
    # encoded as floor and ship unsealed — the puzzle solved before the player
    # arrives. Shutting them here rather than after the fills also keeps a fill
    # from growing a word onto a door cell. The tick opens the door on turn one if
    # the text really does read true, so nothing legitimate is lost.
    room.seals = tuple(spec.seals)
    # A seal's UNVEIL cells are not doors — they are veiled carvings, already
    # stone (or whatever the author kept), and the tick lifts their veil; they
    # must not be walled here, or the reveal would re-hide behind new rock.
    from vimny.engine.motion import _FOGGABLE_CELLS as _FC
    for _s in spec.seals:
        for (r, c) in _s.unveils:
            if not (0 <= r < room.rows and 0 <= c < room.cols):
                continue
            # An unveil cell's DARKNESS is seeded by terrain: stone keeps a
            # veil (the carving is not legible yet), open ground keeps fog.
            if room.cells[r][c] in (CellType.WALL, CellType.WOOD_WALL):
                room.veiled_cells.add((r, c))
            elif room.cells[r][c] in _FC:
                room.fog_cells.add((r, c))
    for _s in spec.seals:
        for _r, _c in _s.opens:
            if 0 <= _r < room.rows and 0 <= _c < room.cols:
                room.cells[_r][_c] = CellType.WALL

    runs = [CharRun(row=int(r['row']), col=int(r['col']),
                    symbols=tuple(r['symbols']) if not isinstance(r['symbols'], str)
                            else tuple(r['symbols']),
                    kind=str(r.get('kind', 'ancient')))
            for r in spec.char_runs]
    grown, slots = [], []
    for f in spec.fills:
        laid = _resolve_fill(f, room, rng, custom)
        slots.append([''.join(ru.symbols) for ru in laid])
        grown.extend(laid)
    room.char_runs = runs + grown

    # What each fill grew, in laying order — the SLOTS a tape may point at. This
    # is a record of one build and nothing reads it afterwards, which is why it
    # can exist alongside the note below: it is never asked what a cell holds
    # NOW, only what the words were at the moment the room was made.
    room.fill_slots = slots

    # The fill regions travel with the room so the editor can draw them, refuse
    # edits inside them, and write them back out as directives. Which text a
    # fill GREW is deliberately not recorded per-run: a row edit re-merges its
    # runs into fresh objects, so any ownership pinned to an object identity
    # would evaporate on the first keystroke. `in_fill` asks the regions
    # instead, and a region is stable no matter how often the row is rebuilt.
    room.fills = list(spec.fills)

    room.entities = [_make_entity(e, i, spec.at('entities'))
                     for i, e in enumerate(spec.entities)]
    # The derived exit marker is NOT added here — see build(), which gives it
    # to the last room alone once every room exists. A transit room's stair is
    # bare: no portal drawn, nothing for a cut to destroy.

    # The fog law, after the seals are shut and not before: a shut seal is a
    # wall, and the pocket behind it is exactly what the eye cannot reach. Fog
    # is DERIVED here rather than stored in the file, so it can never disagree
    # with the walls an author painted — move a wall in the forge and the fog
    # moves with it, with nothing to remember and nothing to re-run.
    # A level file has no scripts, so the only fog it can carry is the
    # UNDERWATER kind — permanent by being drowned ground, not by holding the
    # reveal back. So a built level always re-reveals: walk in, and the pocket
    # lights as sight crosses the opened seal, while sunken cells stay hazy.
    # …and the indexes BEFORE the law, not after: an `opaque` door is a thing
    # standing on a cell, so the law has to be able to ask what is standing
    # there. Indexed after, `entity_at` answered None and a door an author
    # declared opaque fogged nothing.
    room.rebuild_indexes()
    apply_stone_fog(room)
    return room


def finalize_par(room, par: int | None) -> None:
    """Pin par and derive the budget from it — `ceil(par * 1.4)`, no exceptions.

    Authors do not get to pick a budget. Par is the cheapest route the tape
    proves exists, and the budget is a fixed function of it; letting either be
    declared would let a level be tuned to hide a sloppy route.
    """
    if par is None:
        room.par    = None
        room.budget = 99999        # replay-only: the tape has not been costed yet
    else:
        room.par    = par
        room.budget = math.ceil(par * 1.4)


def _make_entity(spec: dict, i: int, where: str = 'entities') -> Entity:
    if not isinstance(spec, dict):
        raise LevelFormatError(f'{where}[{i}]: must be an object')
    at = spec.get('at')
    if not (isinstance(at, (list, tuple)) and len(at) == 2):
        raise LevelFormatError(f'{where}[{i}].at: must be [row, col]')
    kw = {k: v for k, v in spec.items() if k in _ENTITY_FIELDS}
    kw.pop('row', None)
    kw.pop('col', None)
    if 'kind' not in kw:
        raise LevelFormatError(f'{where}[{i}].kind: required')
    # A published level is written once and read forever. When a kind is
    # renamed, every file already in the wild still names the old one, and the
    # only acceptable answer is to keep reading it.
    kw['kind'] = canonical_kind(str(kw['kind']))
    if kw.get('drops'):
        _k, _sep, _tag = str(kw['drops']).partition(':')
        kw['drops'] = canonical_kind(_k) + _sep + _tag
    unknown = set(spec) - set(_ENTITY_FIELDS) - {'at'}
    if unknown:
        raise LevelFormatError(f'{where}[{i}]: unknown field(s) {sorted(unknown)}')
    return Entity(row=int(at[0]), col=int(at[1]), **kw)


def _resolve_fill(f: Fill, room, rng: random.Random, custom) -> list:
    """Lay words across a region, left to right, row by row."""
    if f.pool in vocab.LINE_POOLS:
        return _resolve_fill_lines(f, room, rng)
    r1, c1, r2, c2 = f.region
    lo, hi = f.length
    out = []
    for r in range(max(0, r1), min(room.rows, r2 + 1)):
        c = max(0, c1)
        limit = min(room.cols - 1, c2)
        while c <= limit:
            length = rng.randint(lo, hi)
            if c + length - 1 > limit:
                break
            # Only lay a word where the whole run stands on floor; a fill must
            # not paint text into stone the author carved on purpose.
            if all(room.cells[r][c + i] in (CellType.FLOOR, CellType.CORRIDOR)
                   for i in range(length)):
                word = vocab.words(f.pool, length, rng, custom)
                out.append(CharRun(row=r, col=c, symbols=tuple(word), kind=f.kind))
                c += length + f.spacing
            else:
                c += 1
    return out


def _resolve_fill_lines(f: Fill, room, rng: random.Random) -> list:
    """Lay WHOLE sayings across a region, one after another, row by row.

    Each word is still its own CharRun — `w` and `e` must step word by word, as
    they do over any other text — but the words of one saying are laid in order,
    one space apart, so the row reads as the sentence it is. `length` is ignored
    here: a saying is as long as it is, and the region's WIDTH is what decides
    whether it fits. Only sayings that fit the space left on the row are
    candidates, so a fill thins out at the right margin rather than laying half
    a proverb.
    """
    r1, c1, r2, c2 = f.region
    pool = vocab.sayings(f.pool)
    out  = []
    for r in range(max(0, r1), min(room.rows, r2 + 1)):
        c     = max(0, c1)
        limit = min(room.cols - 1, c2)
        while c <= limit:
            fits = [s for s in pool if c + vocab.saying_width(s) - 1 <= limit]
            if not fits:
                break
            saying = rng.choice(fits)
            width  = vocab.saying_width(saying)
            if all(room.cells[r][c + i] in (CellType.FLOOR, CellType.CORRIDOR)
                   for i in range(width)):
                _c = c
                for word in saying:
                    out.append(CharRun(row=r, col=_c, symbols=tuple(word),
                                       kind=f.kind))
                    _c += len(word) + 1
                # At least TWO blanks between sayings: one space is the gap
                # INSIDE a saying, so a single space between them runs two
                # proverbs together into one unreadable line.
                c += width + max(2, f.spacing)
            else:
                c += 1
    return out


# ── Writing ───────────────────────────────────────────────────────────────────

def dumps(lvl: Level) -> str:
    """Serialise a Level back to file text (stable key order, diffable)."""
    data = {
        'schema':   SCHEMA,
        'name':     lvl.name,
        'author':   lvl.author,
        'seed':     lvl.seed,
        'teaches':  lvl.teaches,
        'requires': lvl.requires,
        'no_horse': lvl.no_horse,
        'geometry': {'rows': lvl.rows, 'cols': lvl.cols, 'cells': lvl.cells,
                     'spawn': list(lvl.spawn), 'exit': list(lvl.exit),
                     **_dump_wrap(lvl.rooms[0])},
        'solution': lvl.solution,
    }
    if lvl.alternate:
        data['alternate'] = lvl.alternate
    if lvl.intro:
        data['intro'] = lvl.intro
    data.update(_dump_content(lvl.rooms[0]))
    if lvl.then:
        data['then'] = [{'geometry': {'rows': h.rows, 'cols': h.cols,
                                      'cells': h.cells,
                                      'spawn': list(h.spawn),
                                      'exit': list(h.exit),
                                      **_dump_wrap(h)},
                         **_dump_content(h)} for h in lvl.then]
    if lvl.vocabulary:
        data['vocabulary'] = lvl.vocabulary
    return json.dumps(data, indent=2, ensure_ascii=False) + '\n'


def _dump_wrap(h: Room) -> dict:
    """The wrap keys, written only when they are not the default — so the
    overwhelmingly common ordinary room carries no wrap machinery at all."""
    out = {}
    if h.wrap:
        out['wrap'] = True
    if h.wrap_width:
        out['wrap_width'] = h.wrap_width
    return out


def _dump_content(h: Room) -> dict:
    """One room's content keys, empty ones left out. Shared by the level's
    own block and every entry in `then`, so a room reads the same wherever
    it is."""
    data = {}
    if h.veiled:
        data['veiled'] = [list(v) for v in h.veiled]
    if h.underwater:
        data['underwater'] = [list(v) for v in h.underwater]
    if getattr(h, 'braziers', None):
        data['braziers'] = [list(v) for v in h.braziers]
    if h.fills:
        data['fill'] = [{'region': list(f.region), 'pool': f.pool,
                         'length': list(f.length), 'spacing': f.spacing,
                         'kind': f.kind} for f in h.fills]
    if h.seals:
        # Every optional axis is written only when it is not the default, so a
        # plain region-and-password seal still reads as the four short lines it
        # always was and an author is never shown machinery they did not ask for.
        out = []
        for s in h.seals:
            d = {'opens': [list(c) for c in s.opens], 'mode': s.mode}
            if getattr(s, 'message', ''):
                d['message'] = s.message
            if s.unveils:
                d['unveils'] = [list(c) for c in s.unveils]
            if s.region:
                d['region'] = list(s.region)
            if s.match:
                d['match'] = s.match[0] if len(s.match) == 1 else list(s.match)
            if s.scope != 'region':
                d['scope'] = s.scope
            if s.requires:
                d['requires'] = list(s.requires)
            if s.anchor:
                d['anchor'] = s.anchor
            if s.head >= 0:
                d['head'] = s.head
            if s.at >= 0:
                d['at'] = s.at
            out.append(d)
        data['seals'] = out
    if h.char_runs:
        data['char_runs'] = h.char_runs
    if h.entities:
        data['entities'] = h.entities
    return data


def _grown(fills, ru) -> bool:
    """True if a fill region covers this run's first cell — i.e. a directive grew
    it and it must not also be written out by hand."""
    return any(f.covers(ru.row, ru.col) for f in fills)


#: Entity kinds that belong to the SESSION, not to the level. The wizard's horse
#: is placed into whatever room the player walks into, so an author who has beaten
#: the game finds him standing in their draft — and `from_room` would happily write
#: him into the file. That is not a cosmetic wart: a shipped horse re-triggers the
#: first-meeting naming prompt for anyone who has not met him, and that prompt eats
#: the keys after it, which is exactly how a recorded tape loses its trailing `:wq`
#: and a level that plays perfectly reports itself unsolvable.
_TRANSIENT_KINDS = frozenset({'horse'})


def from_room(room, name: str, author: str = '', solution: str = '',
              teaches=(), requires=(), *, fills=None, seals=None, vocabulary=(),
              intro: str = '', alternate: str | None = None,
              seed: int | None = None, then=()) -> Level:
    """Capture a live Room as an authored Level — the editor's export path.

    Hand-placed text is written out explicitly; text a FILL grew is not. A fill
    is a directive that re-resolves from the seed at build time, so writing its
    words out as well would ship the level with both, and the second build would
    lay the words on top of themselves. Anything standing inside a fill region
    is therefore dropped here and left to the directive — which is what makes an
    authored level round-trip through the editor unchanged.

    Session entities (`_TRANSIENT_KINDS`) are dropped for the same reason: they
    were never authored, they were walked in. Seal doors are re-shut for the
    third form of it: their open state is a reading of the buffer, not a fact
    about the room.

    Everything not derivable from the grid — the fills themselves, the author's
    vocabulary, the intro, the slug it stands in for — has to be passed in,
    because a Room has nowhere to remember it. `then` is the sharpest case: this
    captures ONE room, and a level's later rooms are rooms nobody is standing
    in. They ride through untouched, and a caller that forgets to pass them
    saves a two-room level as a one-room one.
    """
    h = capture_room(room, fills=fills, seals=seals)
    return Level(
        name=name, author=author,
        seed=room.seed or 0 if seed is None else seed,
        teaches=list(teaches), requires=list(requires),
        no_horse=bool(getattr(room, 'no_horse', False)),
        alternate=alternate, intro=intro,
        rows=h.rows, cols=h.cols, cells=h.cells,
        spawn=h.spawn, exit=h.exit,
        wrap=h.wrap, wrap_width=h.wrap_width, veiled=h.veiled,
        underwater=h.underwater, braziers=h.braziers,
        fills=h.fills, seals=h.seals,
        char_runs=h.char_runs, entities=h.entities,
        then=list(then),
        vocabulary=list(vocabulary),
        # The tape as WRITTEN wins over the tape as resolved: a level whose
        # route says "the word in fill 0, slot 3" must be written back out
        # saying that, not naming the one word this build happened to roll.
        solution=solution or getattr(room, 'answer_source', '') or room.answer,
    )


def capture_room(room, *, fills=None, seals=None,
                 where: str = 'geometry') -> Room:
    """Capture one LIVE room as one room AS WRITTEN — the half of `from_room`
    that is about a room rather than a level.

    Split out because a level of several rooms is captured a room at a time:
    `from_room` makes the first room and the level around it, and every room
    after it comes through here into `then`.
    """
    if fills is None:
        fills = list(getattr(room, 'fills', []))
    if seals is None:
        seals = list(getattr(room, 'seals', ()))
    # Write the seal cells out as STONE, whatever they are standing as right now.
    # A seal cell is not terrain the author painted — it is a door the tick opens
    # and shuts as the text changes, and the author is quite likely looking at it
    # open, because that is how they just tested it. Encoding what is on screen
    # would ship a level whose door starts open and whose puzzle is already
    # solved. `build` shuts them again on load too; both ends hold the same line
    # so neither depends on the other having done it.
    grid = [list(row) for row in room.cells]
    _sunken_by_row = {}
    for r, c in getattr(room, 'underwater_cells', ()):
        if room.cells[r][c] != CellType.WATER:      # water rides the M code
            _sunken_by_row.setdefault('list', []).append((r, c))
        else:
            _sunken_by_row.setdefault(r, set()).add(c)
    for s in seals:
        for r, c in s.opens:
            if 0 <= r < room.rows and 0 <= c < room.cols:
                grid[r][c] = CellType.WALL
    return Room(
        rows=room.rows, cols=room.cols,
        cells=[encode_row(row, _sunken_by_row.get(r, ()))
               for r, row in enumerate(grid)],
        spawn=tuple(room.spawn_pos), exit=tuple(room.exit_pos or (1, 1)),
        wrap=bool(getattr(room, 'wrap_buffer', False)),
        wrap_width=int(getattr(room, 'wrap_width', 0) or 0),
        veiled=sorted(getattr(room, 'veiled_cells', ()) or ()),
        braziers=sorted(getattr(room, 'braziers', ()) or ()),
        underwater=sorted(_sunken_by_row.get('list', ())),
        fills=list(fills), seals=list(seals),
        char_runs=[{'row': ru.row, 'col': ru.col,
                    'symbols': list(ru.symbols), 'kind': ru.kind}
                   for ru in room.char_runs if not _grown(fills, ru)],
        entities=[dict({'at': [e.row, e.col]},
                       **{f: getattr(e, f) for f in _ENTITY_FIELDS
                          if f not in ('row', 'col')})
                  for e in room.entities
                  if e.alive and e.kind not in _TRANSIENT_KINDS],
        where=where)
