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

from engine import tape as _tape
from engine.editor import _CELL_CODE, _CODE_CELL, _MIST_CODE, _ENTITY_FIELDS
from engine.motion import apply_stone_fog
from engine.world import (CellType, CharRun, DROPPABLE, Entity, Room, RoomType,
                          Seal, canonical_kind)
from generation.dungeon_gen import Dungeon
from sharing import vocab

SCHEMA = 1

#: Commands every player has, at every point in the curriculum.
ALWAYS_ON = ('u', ':w', ':q', ':q!')

MAX_ROWS, MAX_COLS = 200, 200     # _MAX_COLS in the reflow engine is 200
MAX_ENTITIES       = 400
MAX_FILLS          = 64
MAX_SEALS          = 32
MAX_SEAL_CELLS     = 64           # cells one seal may open — a door, not a demolition
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
    fills:       list = field(default_factory=list)   # list[Fill]
    seals:       list = field(default_factory=list)   # list[world.Seal]
    char_runs:   list = field(default_factory=list)   # explicit text
    entities:    list = field(default_factory=list)   # list[dict]
    vocabulary:  list = field(default_factory=list)   # author's own words
    solution:    str  = ''
    intro:       str  = ''

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
                           'fill', 'seals', 'char_runs', 'entities',
                           'vocabulary', 'solution', 'intro'}
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
        fills=[_parse_fill(f, i) for i, f in enumerate(data.get('fill', []))],
        seals=[_parse_seal(s, i) for i, s in enumerate(data.get('seals', []))],
        char_runs=list(data.get('char_runs', [])),
        entities=list(data.get('entities', [])),
        vocabulary=list(data.get('vocabulary', [])),
        solution=str(data.get('solution', '')),
        intro=str(data.get('intro', '')),
    )
    if not lvl.name:
        raise LevelFormatError('name: required')
    return lvl


def _parse_fill(f: dict, i: int) -> Fill:
    if not isinstance(f, dict):
        raise LevelFormatError(f'fill[{i}]: must be an object')
    region = f.get('region')
    if not (isinstance(region, (list, tuple)) and len(region) == 4):
        raise LevelFormatError(f'fill[{i}].region: must be [r1, c1, r2, c2]')
    length = f.get('length', [3, 6])
    if isinstance(length, int):
        length = [length, length]
    if not (isinstance(length, (list, tuple)) and len(length) == 2):
        raise LevelFormatError(f'fill[{i}].length: must be n or [min, max]')
    return Fill(region=tuple(int(x) for x in region),
                pool=str(f.get('pool', 'plain')),
                length=(int(length[0]), int(length[1])),
                spacing=int(f.get('spacing', 1)),
                kind=str(f.get('kind', 'ancient')))


_SEAL_MODES  = ('exact', 'contains')
_SEAL_SCOPES = ('region', 'anyrow')


def _parse_seal(s: dict, i: int) -> Seal:
    """One `seals` entry → a `world.Seal`.

    Every failure names the field and says what was wanted, because a seal is the
    one directive whose mistake is invisible: a mistyped `opens` cell does not
    crash, it simply builds a door that never opens anywhere — and the author
    finds out at the solvability gate, several minutes later, with no clue why.
    """
    if not isinstance(s, dict):
        raise LevelFormatError(f'seals[{i}]: must be an object')
    unknown = set(s) - {'region', 'match', 'opens', 'mode', 'scope',
                        'requires', 'anchor'}
    if unknown:
        raise LevelFormatError(f'seals[{i}]: unknown key(s) {sorted(unknown)}')
    scope = str(s.get('scope', 'region'))
    if scope not in _SEAL_SCOPES:
        raise LevelFormatError(f'seals[{i}].scope: must be one of '
                               f'{", ".join(_SEAL_SCOPES)}, got {scope!r}')
    # `match` may be one string or several, ALL of which must read true. A door
    # that wants a chamber's three sayings held at once is one seal, not three.
    match = s.get('match', [])
    if isinstance(match, str):
        match = [match] if match else []
    region = s.get('region')
    if scope == 'region' and match:
        if not (isinstance(region, (list, tuple)) and len(region) == 4):
            raise LevelFormatError(f'seals[{i}].region: must be [r1, c1, r2, c2]')
        region = tuple(int(x) for x in region)
    elif region:
        raise LevelFormatError(
            f'seals[{i}].region: this seal reads no region — '
            + ('a scope="anyrow" seal reads every floor row'
               if scope == 'anyrow' else
               'a seal with no `match` reads only the seals it requires'))
    else:
        region = ()
    if not isinstance(match, (list, tuple)) or not all(
            isinstance(m, str) and m.strip() for m in match):
        raise LevelFormatError(f'seals[{i}].match: must be the text the seal has '
                               f'to read, or a list of texts, none of them empty')
    if any(len(m) > MAX_SEAL_MATCH for m in match):
        raise LevelFormatError(f'seals[{i}].match: at most {MAX_SEAL_MATCH} characters')
    requires = s.get('requires', [])
    if not isinstance(requires, (list, tuple)) or not all(
            isinstance(k, int) for k in requires):
        raise LevelFormatError(f'seals[{i}].requires: must be a list of the '
                               f'indices of earlier seals')
    if any(not 0 <= k < i for k in requires):
        # Earlier-only is what makes the conjunction one pass with no cycle to
        # find. A seal that named a later one would open on a reading that had
        # not been taken yet, which is a rule nobody can debug.
        raise LevelFormatError(f'seals[{i}].requires: must name seals BEFORE '
                               f'this one (0..{i - 1})')
    if not match and not requires:
        raise LevelFormatError(f'seals[{i}]: has nothing to read — give it a '
                               f'`match`, or `requires` naming earlier seals')
    anchor = str(s.get('anchor', ''))
    if anchor not in ('', 'exit_row'):
        raise LevelFormatError(f'seals[{i}].anchor: must be "" or "exit_row", '
                               f'got {anchor!r}')
    opens = s.get('opens')
    # A single [row, col] is allowed and is by far the common case: most doors
    # are one cell, and making an author write [[9, 40]] to say so is a papercut
    # they meet on their first seal.
    if (isinstance(opens, (list, tuple)) and len(opens) == 2
            and all(isinstance(v, int) for v in opens)):
        opens = [opens]
    if not (isinstance(opens, (list, tuple)) and opens):
        raise LevelFormatError(f'seals[{i}].opens: must be [row, col] or a list of them')
    if len(opens) > MAX_SEAL_CELLS:
        raise LevelFormatError(f'seals[{i}].opens: at most {MAX_SEAL_CELLS} cells')
    cells = []
    for j, cell in enumerate(opens):
        if not (isinstance(cell, (list, tuple)) and len(cell) == 2):
            raise LevelFormatError(f'seals[{i}].opens[{j}]: must be [row, col]')
        cells.append((int(cell[0]), int(cell[1])))
    mode = str(s.get('mode', 'exact'))
    if mode not in _SEAL_MODES:
        raise LevelFormatError(f'seals[{i}].mode: must be one of '
                               f'{", ".join(_SEAL_MODES)}, got {mode!r}')
    return Seal(region=region, match=tuple(match), opens=tuple(cells), mode=mode,
                scope=scope, requires=tuple(requires), anchor=anchor)


def loads(text: str) -> Level:
    try:
        return parse(json.loads(text))
    except json.JSONDecodeError as exc:
        raise LevelFormatError(f'not valid JSON: {exc}') from None


# ── Cell grids ────────────────────────────────────────────────────────────────

def expand_row_mist(row: str, cols: int, lineno: int) -> tuple:
    """One `cells` row → (list of CellTypes, the columns that carry mist).

    Accepts both the plain form (`WFFFW`) and the run-length form (`W3F60W`),
    because a 200-column room of mostly stone is unreadable written out in full
    and unreviewable in a pull request.

    `M` is water with permanent mist over it. It expands to WATER here and the
    haze comes back as a column number, because mist is not a cell type — see
    `_MIST_CODE`.
    """
    out, mist = [], []
    pos = 0
    for m in _RLE.finditer(row):
        if m.start() != pos:
            raise LevelFormatError(
                f'geometry.cells[{lineno}]: unexpected {row[pos]!r} at column {pos}')
        pos = m.end()
        count = int(m.group(1)) if m.group(1) else 1
        code  = m.group(2)
        if code == _MIST_CODE:
            mist.extend(range(len(out), len(out) + count))
            out.extend([CellType.WATER] * count)
            continue
        if code not in _CODE_CELL:
            raise LevelFormatError(
                f'geometry.cells[{lineno}]: unknown cell code {code!r}; '
                f'known codes are {"".join(sorted(set(_CODE_CELL) | {_MIST_CODE}))}')
        out.extend([_CODE_CELL[code]] * count)
    if pos != len(row):
        raise LevelFormatError(
            f'geometry.cells[{lineno}]: unexpected {row[pos]!r} at column {pos}')
    if len(out) != cols:
        raise LevelFormatError(
            f'geometry.cells[{lineno}]: expands to {len(out)} cells, expected {cols}')
    return out, mist


def expand_row(row: str, cols: int, lineno: int) -> list:
    """One `cells` row → a list of CellTypes, mist discarded."""
    return expand_row_mist(row, cols, lineno)[0]


def encode_row(cells: list, mist_cols=()) -> str:
    """The inverse of expand_row_mist, run-length encoded."""
    out, run, prev = [], 0, None
    mist_cols = set(mist_cols)
    for i, ct in enumerate(cells):
        code = _MIST_CODE if i in mist_cols and ct == CellType.WATER else _CELL_CODE[ct]
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
    grid = [expand_row(row, lvl.cols, i) for i, row in enumerate(lvl.cells)]
    keep = set()
    for r, row in enumerate(grid):
        for c, ct in enumerate(row):
            if ct != CellType.WALL:
                keep.add((r, c))
    for ru in lvl.char_runs:
        for i in range(len(ru['symbols'])):
            keep.add((int(ru['row']), int(ru['col']) + i))
    for e in lvl.entities:
        keep.add((int(e['at'][0]), int(e['at'][1])))
    for f in lvl.fills:
        keep.add((f.region[0], f.region[1]))
        keep.add((f.region[2], f.region[3]))
    for s in lvl.seals:
        keep.add((s.region[0], s.region[1]))
        keep.add((s.region[2], s.region[3]))
        keep.update(tuple(c) for c in s.opens)
    keep.add(tuple(lvl.spawn))
    keep.add(tuple(lvl.exit))
    if not keep:
        return lvl
    r1 = max(0, min(r for r, _ in keep) - 1)
    r2 = min(lvl.rows - 1, max(r for r, _ in keep) + 1)
    c1 = max(0, min(c for _, c in keep) - 1)
    c2 = min(lvl.cols - 1, max(c for _, c in keep) + 1)
    if (r1, c1, r2, c2) == (0, 0, lvl.rows - 1, lvl.cols - 1):
        return lvl                                   # already tight

    def _mv(pos):
        return (int(pos[0]) - r1, int(pos[1]) - c1)

    mist = {(r, c) for r, row in enumerate(lvl.cells)
            for c in expand_row_mist(row, lvl.cols, r)[1]}
    out = replace(
        lvl,
        rows=r2 - r1 + 1, cols=c2 - c1 + 1,
        cells=[encode_row(grid[r][c1:c2 + 1],
                          [c - c1 for (mr, c) in mist if mr == r])
               for r in range(r1, r2 + 1)],
        spawn=_mv(lvl.spawn), exit=_mv(lvl.exit),
        char_runs=[{**ru, 'row': int(ru['row']) - r1, 'col': int(ru['col']) - c1}
                   for ru in lvl.char_runs],
        entities=[{**e, 'at': list(_mv(e['at']))} for e in lvl.entities],
        fills=[replace(f, region=(f.region[0] - r1, f.region[1] - c1,
                                  f.region[2] - r1, f.region[3] - c1))
               for f in lvl.fills],
        seals=[replace(s, opens=tuple(_mv(c) for c in s.opens),
                       region=((s.region[0] - r1, s.region[1] - c1,
                                s.region[2] - r1, s.region[3] - c1)
                               if s.region else ()))
               for s in lvl.seals],
    )
    return out


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
    if len(lvl.cells) != lvl.rows:
        raise LevelFormatError(
            f'geometry.cells: {len(lvl.cells)} rows, geometry.rows says {lvl.rows}')
    grid = [expand_row_mist(row, lvl.cols, i) for i, row in enumerate(lvl.cells)]
    cells = [g[0] for g in grid]
    mist  = {(r, c) for r, (_, cols) in enumerate(grid) for c in cols}

    room = Room(room_type=RoomType.ENTRY, rows=lvl.rows, cols=lvl.cols)
    room.cells     = cells
    room.mist_cells = set(mist)
    room.fog_cells  = set(mist)      # mist is always a subset of the fog
    room.seed      = lvl.seed
    room.spawn_pos = tuple(lvl.spawn)
    room.exit_pos  = tuple(lvl.exit)
    room.no_horse  = lvl.no_horse

    # Seals are built SHUT, whatever the grid says, and before anything else reads
    # the grid. A `cells` grid is written by `from_room` while the level was being
    # played, so a door that happened to be open at save time would otherwise be
    # encoded as floor and ship unsealed — the puzzle solved before the player
    # arrives. Shutting them here rather than after the fills also keeps a fill
    # from growing a word onto a door cell. The tick opens the door on turn one if
    # the text really does read true, so nothing legitimate is lost.
    room.seals = tuple(lvl.seals)
    for _s in lvl.seals:
        for _r, _c in _s.opens:
            if 0 <= _r < room.rows and 0 <= _c < room.cols:
                room.cells[_r][_c] = CellType.WALL

    custom = vocab.by_length([w for w in lvl.vocabulary]) if lvl.vocabulary else None
    rng    = random.Random(lvl.seed if seed is None else seed)

    runs = [CharRun(row=int(r['row']), col=int(r['col']),
                    symbols=tuple(r['symbols']) if not isinstance(r['symbols'], str)
                            else tuple(r['symbols']),
                    kind=str(r.get('kind', 'ancient')))
            for r in lvl.char_runs]
    grown, slots = [], []
    for f in lvl.fills:
        laid = _resolve_fill(f, room, rng, custom)
        slots.append([''.join(ru.symbols) for ru in laid])
        grown.extend(laid)
    room.char_runs = runs + grown

    # What each fill grew, in laying order — the SLOTS a tape may point at. This
    # is a record of one build and nothing reads it afterwards, which is why it
    # can exist alongside the note below: it is never asked what a cell holds
    # NOW, only what the words were at the moment the room was made.
    room.fill_slots = slots
    try:
        room.answer = _tape.resolve_slots(lvl.solution, slots)
    except _tape.UnknownSlot as exc:
        raise LevelFormatError(str(exc)) from None
    # The tape AS WRITTEN, kept so that saving the room back out writes the
    # references the author wrote rather than the one roll they happened to get.
    room.answer_source = lvl.solution

    # The fill regions travel with the room so the editor can draw them, refuse
    # edits inside them, and write them back out as directives. Which text a
    # fill GREW is deliberately not recorded per-run: a row edit re-merges its
    # runs into fresh objects, so any ownership pinned to an object identity
    # would evaporate on the first keystroke. `in_fill` asks the regions
    # instead, and a region is stable no matter how often the row is rebuilt.
    room.fills = list(lvl.fills)

    room.entities = [_make_entity(e, i) for i, e in enumerate(lvl.entities)]
    if not any(e.kind == 'exit' for e in room.entities):
        room.entities.append(Entity(kind='exit', row=room.exit_pos[0],
                                    col=room.exit_pos[1]))

    # The fog law, after the seals are shut and not before: a shut seal is a
    # wall, and the pocket behind it is exactly what the eye cannot reach. Fog
    # is DERIVED here rather than stored in the file, so it can never disagree
    # with the walls an author painted — move a wall in the forge and the fog
    # moves with it, with nothing to remember and nothing to re-run.
    # A level file has no scripts, so the only fog it can carry is MIST — which
    # is permanent by being mist, not by holding the reveal back. So a built
    # level always re-reveals: walk in, and the pocket lights as sight crosses
    # the opened seal, while the mist stays hazy for ever.
    apply_stone_fog(room)

    room.rebuild_indexes()
    finalize_par(room, par)

    dungeon = Dungeon(name=lvl.name, seed=lvl.seed)
    dungeon.rooms        = [room]
    dungeon.current_room = 0
    return dungeon


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


def _make_entity(spec: dict, i: int) -> Entity:
    if not isinstance(spec, dict):
        raise LevelFormatError(f'entities[{i}]: must be an object')
    at = spec.get('at')
    if not (isinstance(at, (list, tuple)) and len(at) == 2):
        raise LevelFormatError(f'entities[{i}].at: must be [row, col]')
    kw = {k: v for k, v in spec.items() if k in _ENTITY_FIELDS}
    kw.pop('row', None)
    kw.pop('col', None)
    if 'kind' not in kw:
        raise LevelFormatError(f'entities[{i}].kind: required')
    # A published level is written once and read forever. When a kind is
    # renamed, every file already in the wild still names the old one, and the
    # only acceptable answer is to keep reading it.
    kw['kind'] = canonical_kind(str(kw['kind']))
    if kw.get('drops'):
        _k, _sep, _tag = str(kw['drops']).partition(':')
        kw['drops'] = canonical_kind(_k) + _sep + _tag
    unknown = set(spec) - set(_ENTITY_FIELDS) - {'at'}
    if unknown:
        raise LevelFormatError(f'entities[{i}]: unknown field(s) {sorted(unknown)}')
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
                     'spawn': list(lvl.spawn), 'exit': list(lvl.exit)},
        'solution': lvl.solution,
    }
    if lvl.alternate:
        data['alternate'] = lvl.alternate
    if lvl.intro:
        data['intro'] = lvl.intro
    if lvl.fills:
        data['fill'] = [{'region': list(f.region), 'pool': f.pool,
                         'length': list(f.length), 'spacing': f.spacing,
                         'kind': f.kind} for f in lvl.fills]
    if lvl.seals:
        # Every optional axis is written only when it is not the default, so a
        # plain region-and-password seal still reads as the four short lines it
        # always was and an author is never shown machinery they did not ask for.
        out = []
        for s in lvl.seals:
            d = {'opens': [list(c) for c in s.opens], 'mode': s.mode}
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
            out.append(d)
        data['seals'] = out
    if lvl.char_runs:
        data['char_runs'] = lvl.char_runs
    if lvl.entities:
        data['entities'] = lvl.entities
    if lvl.vocabulary:
        data['vocabulary'] = lvl.vocabulary
    return json.dumps(data, indent=2, ensure_ascii=False) + '\n'


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
              seed: int | None = None) -> Level:
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
    because a Room has nowhere to remember it.
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
    _mist_by_row = {}
    for r, c in getattr(room, 'mist_cells', ()):
        _mist_by_row.setdefault(r, set()).add(c)
    for s in seals:
        for r, c in s.opens:
            if 0 <= r < room.rows and 0 <= c < room.cols:
                grid[r][c] = CellType.WALL
    return Level(
        name=name, author=author,
        seed=room.seed or 0 if seed is None else seed,
        teaches=list(teaches), requires=list(requires),
        no_horse=bool(getattr(room, 'no_horse', False)),
        alternate=alternate, intro=intro,
        rows=room.rows, cols=room.cols,
        cells=[encode_row(row, _mist_by_row.get(r, ()))
               for r, row in enumerate(grid)],
        spawn=tuple(room.spawn_pos), exit=tuple(room.exit_pos or (1, 1)),
        fills=list(fills), seals=list(seals),
        char_runs=[{'row': ru.row, 'col': ru.col,
                    'symbols': list(ru.symbols), 'kind': ru.kind}
                   for ru in room.char_runs if not _grown(fills, ru)],
        entities=[dict({'at': [e.row, e.col]},
                       **{f: getattr(e, f) for f in _ENTITY_FIELDS
                          if f not in ('row', 'col')})
                  for e in room.entities
                  if e.alive and e.kind not in _TRANSIENT_KINDS],
        vocabulary=list(vocabulary),
        # The tape as WRITTEN wins over the tape as resolved: a level whose
        # route says "the word in fill 0, slot 3" must be written back out
        # saying that, not naming the one word this build happened to roll.
        solution=solution or getattr(room, 'answer_source', '') or room.answer,
    )
