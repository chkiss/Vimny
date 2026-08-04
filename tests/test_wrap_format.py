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

"""`wrap` in the level format — the Wardenverse's reactive reflow, said in a file.

The reflow itself turned out to be GENERIC, not library-specific: every consumer
keys off two plain `Room` fields and no slug appears in any of them —
`motion.enforce_fog_law` exempts a wrap buffer, `motion` gj/gk hops a display
row, `renderer` folds at `min(wrap_width or content_w, content_w)`, and
`world.normalize_row_word_kinds` leaves its colours alone. The Archivist's
Library and the Wardenverse are the same machinery; the only difference between
them is whether `wrap_width` is pinned.

What was missing was the FILE. The format had no wrap key at all, so a captured
wrap buffer came back as an ordinary room — and the round-trip probe did not
compare the flag, so it reported the loss as no loss. Both halves are fixed
here: `wrap` / `wrap_width` are geometry keys, and `_snap` compares them.
"""
import json

import pytest

import vimny.game as main
from vimny.sharing import format as F
from vimny.sharing.validate import validate

SEED = 42


def _wrap_room(**kw):
    """A minimal one-line wrap buffer."""
    return F.Level(name='Buffer', seed=1, rows=1, cols=40,
                   cells=['W38FW'],
                   spawn=(0, 1), exit=(0, 38), wrap=True, **kw)


# ── the flag survives the file ───────────────────────────────────────────────
def test_wrap_round_trips():
    lvl = F.loads(F.dumps(_wrap_room()))
    assert lvl.wrap and lvl.wrap_width == 0


def test_a_pinned_fold_width_round_trips():
    lvl = F.loads(F.dumps(_wrap_room(wrap_width=76)))
    assert lvl.wrap and lvl.wrap_width == 76


def test_an_ordinary_room_carries_no_wrap_machinery():
    """Written only when not the default, so the common level is untouched."""
    lvl = F.Level(name='Plain', rows=5, cols=20,
                  cells=['20W'] + ['W18FW'] * 3 + ['20W'],
                  spawn=(1, 1), exit=(3, 18))
    geo = json.loads(F.dumps(lvl))['geometry']
    assert 'wrap' not in geo and 'wrap_width' not in geo


def test_build_puts_the_flag_on_the_live_room():
    room = F.build(_wrap_room(wrap_width=76)).rooms[0]
    assert room.wrap_buffer is True and room.wrap_width == 76


def test_a_later_room_may_be_the_wrap_buffer():
    """Which is the shape that matters: the Wardenverse is `then[0]`, and the
    arena in front of it is an ordinary room."""
    lvl = F.Level(name='Descent', seed=1, rows=5, cols=20,
                  cells=['20W'] + ['W18FW'] * 3 + ['20W'],
                  spawn=(1, 1), exit=(3, 18),
                  then=[F.Room(rows=1, cols=40, cells=['W38FW'],
                               spawn=(0, 1), exit=(0, 38), wrap=True,
                               where='then[0].geometry')])
    rooms = F.build(F.loads(F.dumps(lvl))).rooms
    assert [r.wrap_buffer for r in rooms] == [False, True]


# ── the validator knows the shape ────────────────────────────────────────────
def test_a_wrap_buffer_is_allowed_to_be_one_row():
    """The 3-row floor exists to stop a room with no interior. A buffer has no
    interior to protect — it is one logical line."""
    rep = validate(_wrap_room())
    assert not any('rows must be 3' in e for e in rep.errors), rep.errors


def test_two_rows_of_wrap_is_refused():
    lvl = _wrap_room()
    lvl.rows = 2
    lvl.cells = ['W38FW'] * 2
    rep = validate(lvl)
    assert any('wrap needs rows 1' in e for e in rep.errors), rep.errors


def test_a_one_row_room_without_wrap_is_still_refused():
    lvl = _wrap_room()
    lvl.wrap = False
    rep = validate(lvl)
    assert any('rows must be 3' in e for e in rep.errors), rep.errors


def test_a_fold_width_without_wrap_is_refused():
    lvl = _wrap_room()
    lvl.wrap = False
    lvl.rows, lvl.cells = 5, ['40W'] + ['W38FW'] * 3 + ['40W']
    lvl.wrap_width = 76
    rep = validate(lvl)
    assert any('wrap_width means nothing' in e for e in rep.errors), rep.errors


# ── the Wardenverse itself ───────────────────────────────────────────────────
def test_the_wardenverse_survives_the_trip_as_a_reactive_buffer():
    """The check this whole thing was for: `warden_pathfinder`'s second room is
    a 720-column single line that folds to the live terminal (`wrap_width` 0),
    and it comes back out of the file the same."""
    d = main._build_dungeon('warden_pathfinder', SEED)
    verse = d.rooms[1]
    assert verse.wrap_buffer and verse.rows == 1 and verse.wrap_width == 0

    lvl = F.from_room(d.rooms[0], 'X', solution=d.rooms[0].answer or '',
                      then=[F.capture_room(r, where=f'then[{i}].geometry')
                            for i, r in enumerate(d.rooms[1:])])
    rebuilt = F.build(F.loads(F.dumps(lvl)), par=d.rooms[0].par)
    back = rebuilt.rooms[1]
    assert back.wrap_buffer and back.rows == 1 and back.wrap_width == 0
    assert back.cols == verse.cols
    # the segment walls are the puzzle — $ / w / e / {n}l all stop at them
    walls = [c for c in range(1, verse.cols - 1)
             if verse.cells[0][c].name == 'WALL']
    walls2 = [c for c in range(1, back.cols - 1)
              if back.cells[0][c].name == 'WALL']
    assert walls == walls2 and len(walls) >= 8


def test_the_probe_now_compares_the_flag():
    """It did not, which is why the loss was silent — the Wardenverse came back
    with `wrap_buffer` False and the probe called the level whole."""
    import tests.test_round_trip as RT

    class _Fake:
        rows = cols = 1
        cells = [[]]
        spawn_pos = exit_pos = (0, 0)
        char_runs = entities = ()
        mist_cells = fog_cells = seals = ()
        wrap_buffer, wrap_width = True, 0
    snap = RT._snap(_Fake())
    assert 'wrap' in snap and snap['wrap'] == (True, 0)
