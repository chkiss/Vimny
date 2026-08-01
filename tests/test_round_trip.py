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

"""How much of the shipped game can the LEVEL FORMAT already say?

There are two materialisers: `main._build_dungeon`, which runs a hand-written
builder for a shipped slug, and `sharing.format.build`, which reads a level
file. The long-run intent is that there is one — a builder returns a `Level`
and the format builds it — so that the forge is complete BY CONSTRUCTION rather
than by anyone's assurance that it is.

This test is the distance to that. Every shipped level is pushed through
`from_room` → `dumps` → `loads` → `build` and compared against what went in,
cell by cell, run by run, entity by entity. Whatever differs is exactly the
part of that level the format cannot yet say, and it has to be written down
HERE, by slug, with a reason — so the gap is a number in a file that can only
go down, and never an impression anybody has.

Two directions of failure, and both are failures:

* a level loses something not on its list — the format regressed, or the
  builder started using a facility the format never had;
* a level is on the list for something it no longer loses — the exemption went
  stale, and a stale exemption is how an audit starts passing vacuously.
"""
from __future__ import annotations

import pytest

import main
import sharing.format as F
from content.levels import LEVELS

SEED = 4242
ENTRIES = {e['slug']: e for e in LEVELS}
SLUGS = list(ENTRIES)

#: slug -> (what it loses, why). Every tag here is a KNOWN hole in the format,
#: not a bug in the level. Deleting a line is the unit of progress.
KNOWN_GAPS: dict[str, tuple[tuple[str, ...], str]] = {
    # ── scripted fog ─────────────────────────────────────────────────────────
    # A level file's fog is DERIVED (the stone law: what the eye cannot reach
    # from spawn, plus the doors an author marked `opaque`). These levels fog
    # MORE than that — a lit radius, a darkness a tick re-lays — and the file
    # has no way to ask for darkness where there is neither wall nor door. Mist
    # is the one other exception it can say, and mist rides on water.
    #
    # FIVE LEFT THIS TABLE on 2026-08-01. Their fog was never a darkness at
    # all: `_fog_unreachable` floods by FEET, so what it laid was exactly
    # "everything behind a shut door" — a rule, written down as its answer, and
    # "door" there is `_FOG_BLOCK_KINDS`: plain, locked, seal doors and boss
    # seals alike. `_doors_block_sight` says the rule instead (`Entity.opaque`),
    # the law derives the same cells, and the fog came out identical on every
    # seed. Before adding a new fog exemption, check whether it is really this.
    #
    # THREE MORE LEFT on 2026-08-01, and none of them was fog either: the Wet
    # Ink, the Manifold and the Scrivener were hiding CARVED WALL CELLS, which
    # the law's universe (`_FOGGABLE_CELLS`) cannot contain by definition. That
    # is a puzzle handing out its clue in instalments, not a fact about what the
    # eye can reach, so it moved to `Room.veiled_cells` — the same
    # implementation under its own name. Their floors were derivable all along.
    'waypoint_sanctum':     (('fog',), 'unlit sanctum'),
    'operators_vault':      (('fog',), 'unlit vault'),

    # ── mist off the water ───────────────────────────────────────────────────
    # `encode_row` writes an M only where the cell is WATER, so mist in the file
    # is a property of water rather than a layer over any terrain. These two
    # haze plain floor.
    'shelving_room':        (('fog', 'mist'), 'mist over floor, not water'),
    'refrain_vault':        (('fog', 'mist'), 'mist over floor, not water'),

    # ── a room with no way out ───────────────────────────────────────────────
    # Several rooms are sayable since phase 4 (`then`), and the Sanctum's two
    # rooms survive the trip. The Wardenverse does not: it is a room with
    # `exit_pos = None`, which you leave by killing the Warden in it rather than
    # by walking anywhere, and the format cannot say "a room with no exit" —
    # every room has one, because a door is how a room ends. That is the
    # same `:e wardenverse` machinery the port already excepts.
    'warden_pathfinder':    (('fog', 'ents', 'exit'),
                             'the Wardenverse: a room with no exit, left by '
                             'an event rather than by a door'),
    'grandmasters_sanctum': (('ents',), 'room 0 has no exit entity of its own '
                             'and the format synthesises one'),

    # ── the rest ─────────────────────────────────────────────────────────────
    # `runs` HEALED 2026-07-31 when `wrap` entered the format. The rebuilt room
    # used to come back with `wrap_buffer` False, and `normalize_row_word_kinds`
    # skips a wrap buffer — so on the way back in, its regions were merged into
    # one colour and the runs no longer matched. Saying `wrap` in the file fixed
    # the colours for free.
    'archivists_library':   (('ents', 'exit'),
                             'the one agreed exception: a wrap buffer whose text '
                             'is the level and whose exit is a reading position'),
    'dummy':                (('ents',), "the horse: a session entity, dropped by "
                             '`from_room` on purpose (_TRANSIENT_KINDS)'),
}


def _snap(room) -> dict:
    """Everything about a room a player could tell apart."""
    return {
        'cells': [[c.name for c in row] for row in room.cells],
        'spawn': tuple(room.spawn_pos or ()),
        'exit':  tuple(room.exit_pos or ()),
        'runs':  sorted((r.row, r.col, ''.join(r.symbols), r.kind)
                        for r in room.char_runs),
        'ents':  sorted((e.kind, e.row, e.col) for e in room.entities),
        'mist':  sorted(room.mist_cells or ()),
        'fog':   sorted(room.fog_cells or ()),
        'seals': len(room.seals or ()),
        # A WRAP BUFFER is a room you read rather than walk, and whether it
        # wraps changes every motion in it — so it is something a player can
        # tell apart, and the probe was blind to it until 2026-07-31. The
        # Wardenverse came through this trip with `wrap_buffer` silently False,
        # reported whole, and nothing failed. Compared here, that is a gap the
        # table has to name or the format has to close.
        'wrap':  (bool(getattr(room, 'wrap_buffer', False)),
                  int(getattr(room, 'wrap_width', 0) or 0)),
        # VEILED plaques. Compared from the day the field existed: moving the
        # wall-cell darkness out of `fog_cells` fixed three exemptions, and it
        # would have been a cheat to fix them by putting the thing somewhere
        # the probe was not looking.
        'veiled': sorted(getattr(room, 'veiled_cells', ()) or ()),
    }


def _lost(slug) -> tuple[str, ...]:
    """What a shipped level cannot say about itself in the level format."""
    entry = ENTRIES[slug]
    dungeon = main._build_dungeon(slug, SEED)
    src = dungeon.rooms[0]
    # Every room, not just the one the player starts in: a level of several
    # rooms is captured a room at a time, the first as the level's own
    # geometry and the rest as `then`. A probe that read room 0 alone would
    # report a two-room level as whole while leaving half of it behind.
    lvl = F.from_room(src, entry['name'], solution=src.answer or '',
                      teaches=entry.get('teaches', ()),
                      then=[F.capture_room(r, where=f'then[{i}].geometry')
                            for i, r in enumerate(dungeon.rooms[1:])])
    rebuilt = F.build(F.loads(F.dumps(lvl)), par=src.par)
    lost = set()
    if len(rebuilt.rooms) != len(dungeon.rooms):
        lost.add('rooms')
    for old, new in zip(dungeon.rooms, rebuilt.rooms):
        a, b = _snap(old), _snap(new)
        lost.update(k for k in a if a[k] != b[k])
    return tuple(sorted(lost))


@pytest.mark.parametrize('slug', SLUGS)
def test_a_level_loses_only_what_is_written_down(slug):
    lost = _lost(slug)
    allowed = set(KNOWN_GAPS.get(slug, ((), ''))[0])
    surprise = sorted(set(lost) - allowed)
    assert not surprise, (
        f'{slug} no longer round-trips through the level format: {surprise}. '
        'Either the format regressed, or this builder started using something '
        'the format cannot say — in which case add it to KNOWN_GAPS with a '
        'reason, and say so out loud.')


@pytest.mark.parametrize('slug', sorted(KNOWN_GAPS))
def test_no_exemption_is_stale(slug):
    """An exemption that no longer applies is an audit passing vacuously."""
    lost = set(_lost(slug))
    listed = set(KNOWN_GAPS[slug][0])
    healed = sorted(listed - lost)
    assert not healed, (
        f'{slug} now round-trips {healed} — delete it from KNOWN_GAPS '
        '(and take the win).')


def test_the_gap_is_a_number_that_only_goes_down():
    """The headline. 43 of 60 shipped levels already survive the trip whole.

    If this fails downward, something regressed. If it fails upward, a phase of
    the port landed — raise the floor in the same commit so it cannot slide
    back.
    """
    lossless = [s for s in SLUGS if s not in KNOWN_GAPS]
    assert len(lossless) >= 43, (
        f'only {len(lossless)}/{len(SLUGS)} levels round-trip losslessly')
