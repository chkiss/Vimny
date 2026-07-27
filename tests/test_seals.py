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

"""One tick behind every content gate — `Seal` and `_seal_tick`.

Seventeen shipped levels were built on two hand-written ticks that did the same
thing at slightly different strengths (`_sight_sanctum_tick`, exact whole rows,
ten levels; `_whole_line_annex_tick`, substrings, seven). They are seals now.
These tests are over the MECHANISM rather than over any level, because the
levels' own tests already play them: what is asserted here is the law the
chassis relied on, in the smallest room that can show it.
"""
from __future__ import annotations

import pytest

import main
import sharing.format as F
from engine.player import Player
from engine.world import CellType, Seal, gate_row_seals


def _room(seals, texts=(), rows=6, cols=20):
    """A plain hall with a doorway at (4, 18), and text on the floor."""
    lvl = F.Level(name='Bolt', seed=7, rows=rows, cols=cols,
                  cells=[f'{cols}W']
                        + [f'W{cols - 2}FW'] * (rows - 2)
                        + [f'{cols}W'],
                  spawn=(1, 1), exit=(rows - 2, cols - 2),
                  char_runs=[{'row': r, 'col': 1, 'symbols': list(t),
                              'kind': 'ancient'} for r, t in texts])
    room = F.build(lvl).room
    room.seals = tuple(seals)
    for s in room.seals:                 # a seal starts SHUT, as `build` shuts its own
        for (r, c) in s.opens:
            room.cells[r][c] = CellType.WALL
    return room


def _tick(room, at=(1, 1)):
    return main._seal_tick(room, Player(row=at[0], col=at[1]))


def _write(room, r, text, col=1):
    from engine.world import CharRun
    room.char_runs = [ru for ru in room.char_runs if ru.row != r]
    if text:
        room.char_runs.append(CharRun(r, col, tuple(text), 'ancient'))
    room.rebuild_indexes()


# ── scope: anyrow ─────────────────────────────────────────────────────────────

def test_anyrow_does_not_care_which_row_the_words_are_on():
    """The whole point of the scope. Charwise edits leave rows where they were,
    but `dd`, `J`, `o` and `p` all slide them, and a door that named a row
    number would be re-barred by the first line removed above it."""
    seal = Seal(match='open', scope='anyrow', opens=((3, 10),))
    room = _room([seal], texts=[(1, 'open')])
    _tick(room)
    assert room.cells[3][10] == CellType.FLOOR
    _write(room, 1, '')
    _write(room, 2, 'open')                 # the same words, one row lower
    _tick(room)
    assert room.cells[3][10] == CellType.FLOOR


def test_exact_wants_the_whole_row_and_contains_does_not():
    """The one axis the two shipped chassis differed on. Exactness is what
    prices the Sight Sanctum family: a half-cleared row still reads false."""
    strict = _room([Seal(match='open', scope='anyrow', opens=((3, 10),))],
                   texts=[(1, 'wide open')])
    loose  = _room([Seal(match='open', scope='anyrow', mode='contains',
                         opens=((3, 10),))],
                   texts=[(1, 'wide open')])
    _tick(strict)
    _tick(loose)
    assert strict.cells[3][10] == CellType.WALL
    assert loose.cells[3][10] == CellType.FLOOR


def test_a_seal_re_bars_when_the_words_go_away():
    """STATELESS: opening is a reading that happens to be true right now, which
    is the whole reason `u` re-shuts a door instead of leaving a level
    permanently solved by an edit the player took back."""
    room = _room([Seal(match='open', scope='anyrow', opens=((3, 10),))],
                 texts=[(1, 'open')])
    _tick(room)
    assert room.cells[3][10] == CellType.FLOOR
    _write(room, 1, 'shut')
    _tick(room)
    assert room.cells[3][10] == CellType.WALL


def test_a_seal_never_shuts_under_the_player():
    """Sealing someone inside stone is not a puzzle, it is a crash."""
    room = _room([Seal(match='open', scope='anyrow', opens=((3, 10),))],
                 texts=[(1, 'open')])
    _tick(room)
    _write(room, 1, '')
    _tick(room, at=(3, 10))
    assert room.cells[3][10] == CellType.FLOOR


# ── several targets on one door ───────────────────────────────────────────────

def test_a_door_may_want_more_than_one_saying():
    """A chamber holds its bolt only while EVERY one of its words still stands
    — the Sight Sanctum family's shape, which used to need a tuple-of-tuples
    and a bespoke tick."""
    seal = Seal(match=('alpha', 'beta'), scope='anyrow', opens=((3, 10),))
    room = _room([seal], texts=[(1, 'alpha')])
    _tick(room)
    assert room.cells[3][10] == CellType.WALL, 'half the chamber is not the chamber'
    _write(room, 2, 'beta')
    _tick(room)
    assert room.cells[3][10] == CellType.FLOOR
    _write(room, 2, '')
    _tick(room)
    assert room.cells[3][10] == CellType.WALL


# ── requires: the final seal ──────────────────────────────────────────────────

def test_the_final_seal_waits_for_every_bolt():
    seals = gate_row_seals(((('alpha',), 8), (('beta',), 9)), (4, 18),
                           mode='exact')
    room = _room(seals, texts=[(1, 'alpha')])
    _tick(room)
    assert (room.cells[4][8], room.cells[4][9], room.cells[4][18]) == (
        CellType.FLOOR, CellType.WALL, CellType.WALL)
    _write(room, 2, 'beta')
    _tick(room)
    assert room.cells[4][18] == CellType.FLOOR, 'every bolt open — the exit parts'
    _write(room, 1, '')
    _tick(room)
    assert room.cells[4][18] == CellType.WALL, 'and it returns when one is undone'


def test_a_requirement_may_only_look_backwards():
    """Earlier-only is what makes the conjunction one pass with no cycle to
    find. A seal naming a later one would open on a reading not yet taken."""
    with pytest.raises(F.LevelFormatError, match='BEFORE'):
        F._parse_seal({'requires': [1], 'opens': [4, 18]}, 0)


def test_a_seal_must_have_something_to_read():
    with pytest.raises(F.LevelFormatError, match='nothing to read'):
        F._parse_seal({'opens': [4, 18]}, 0)


def test_an_anyrow_seal_has_no_region():
    with pytest.raises(F.LevelFormatError, match='reads no region'):
        F._parse_seal({'scope': 'anyrow', 'match': 'open',
                       'region': [1, 1, 1, 4], 'opens': [4, 18]}, 0)


# ── anchor: the gate rides the exit ───────────────────────────────────────────

def test_the_gate_row_follows_the_exit_when_rows_shift():
    """`J` and `dd` slide everything below a cut upwards and `_shift_rows` keeps
    `exit_pos` true, so the bolts have to ride with it rather than stay on the
    row they were built on. This is what the hand-written ticks meant by
    re-deriving `gr = room.exit_pos[0]` every turn."""
    seals = gate_row_seals(((('alpha',), 8),), (4, 18), mode='exact')
    room = _room(seals, texts=[(1, 'alpha')])
    room.exit_pos = (3, 18)                      # a row above the gate was cut
    _tick(room)
    assert room.cells[3][8] == CellType.FLOOR, 'the bolt moved up with the exit'
    assert room.cells[3][18] == CellType.FLOOR
    assert room.cells[4][8] == CellType.WALL, 'and nothing opened where it was'


def test_the_banding_follows_the_gate_too():
    """`sealed_cells` is what draws a shut bolt as stonework rather than blank
    wall, so it has to be derived from the same live coordinates."""
    seals = gate_row_seals(((('alpha',), 8),), (4, 18), mode='exact')
    room = _room(seals)
    _tick(room)
    assert room.sealed_cells == {(4, 8), (4, 18)}
    room.exit_pos = (3, 18)
    _tick(room)
    assert room.sealed_cells == {(3, 8), (3, 18)}


# ── the shipped chassis, said as data ─────────────────────────────────────────

@pytest.mark.parametrize('slug', [
    'sight_sanctum', 'selection_halls', 'word_enclosure', 'bracket_enclosure',
    'brace_square_enclosure', 'quote_enclosure', 'tag_enclosure',
    'sentence_enclosure', 'stair_rail', 'wet_ink',
    'whole_line_annex', 'change_extension', 'overwrite_halls', 'case_chambers',
    'joiners_gate', 'g_sanctum', 'buried_word'])
def test_every_chassis_level_is_bolts_then_a_final_seal(slug):
    """Seventeen levels, one shape: doors that read text, then an exit that
    reads the doors. No level keeps a private tick any more."""
    room = main._build_dungeon(slug, 4242).rooms[0]
    *bolts, final = room.seals
    assert bolts, f'{slug} has no doors'
    assert all(s.match and s.scope == 'anyrow' and not s.requires for s in bolts)
    assert not final.match, 'the final seal reads no text of its own'
    assert final.requires == tuple(range(len(bolts))), 'it reads every bolt'
    assert final.opens == (tuple(room.exit_pos),)
    assert all(s.anchor == 'exit_row' for s in room.seals)
    # and every one of them starts shut, so nothing is walkable on turn zero
    assert all(room.cells[r][c] == CellType.WALL
               for s in room.seals for (r, c) in s.opens)
