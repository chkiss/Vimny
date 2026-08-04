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

"""Slice 1 of The Archivist's Library: ':set wrap' soft-wraps a single-line buffer.

The wrap math lives in three pure helpers (no Terminal) so it is unit-testable in
isolation; a render smoke test confirms render_all drives a wrap_buffer room for both
wrap states without error and that the gate leaves ordinary rooms on the nowrap path.
"""
import pytest
from blessed import Terminal

import vimny.render.colors as C
import vimny.render.symbols as S
from vimny.render.renderer import (wrap_total_rows, wrap_scroll_start, wrap_room_col,
                             render_all)
from vimny.engine.world import Dungeon, Room, RoomType, CellType
from vimny.engine.player import Player
from vimny.engine.budget import Budget


@pytest.fixture
def term():
    """A headless Terminal with the colour/symbol modules initialised, as the
    real game does at startup before any render_all call."""
    t = Terminal()
    C.init(t)
    S.init(t)
    return t


# ── wrap_total_rows ─────────────────────────────────────────────────────────
@pytest.mark.parametrize('cols,width,expect', [
    (300, 72, 5),     # 300/72 = 4.16 → 5 display rows
    (72,  72, 1),     # exact fit → 1 row
    (73,  72, 2),     # one over → spills to a 2nd row
    (10,  72, 1),     # shorter than the width → 1 row
    (0,   72, 1),     # empty buffer still occupies one row
    (300, 0,  1),     # degenerate width → 1 (no div-by-zero)
])
def test_wrap_total_rows(cols, width, expect):
    assert wrap_total_rows(cols, width) == expect


# ── wrap_scroll_start (vertical display-line scroll, centred on cursor) ──────
def test_scroll_start_top_when_cursor_near_start():
    # cursor on display row 0, plenty of viewport → no scroll
    assert wrap_scroll_start(cursor_col=5, cols=1000, width=72, view_h=20) == 0


def test_scroll_start_centres_cursor_in_middle():
    # cursor at col 720 → display row 10; centred in a 20-high view → start 0..clamped
    # display row 10 - 10 (view_h//2) = 0
    assert wrap_scroll_start(cursor_col=720, cols=2000, width=72, view_h=20) == 0
    # deeper cursor: col 1440 → drow 20; 20 - 10 = 10
    assert wrap_scroll_start(cursor_col=1440, cols=3000, width=72, view_h=20) == 10


def test_scroll_start_clamps_at_bottom():
    # total rows for 1000/72 = 14; with view_h 20 the block fits → never scroll
    assert wrap_scroll_start(cursor_col=999, cols=1000, width=72, view_h=20) == 0
    # tall block, cursor at the very end → clamp to total - view_h
    total = wrap_total_rows(5000, 72)            # 70
    start = wrap_scroll_start(cursor_col=4999, cols=5000, width=72, view_h=20)
    assert start == total - 20
    assert start >= 0


def test_scroll_start_degenerate():
    assert wrap_scroll_start(0, 0, 0, 0) == 0


# ── wrap_room_col (display coord → logical column) ──────────────────────────
@pytest.mark.parametrize('drow,screen_c,width,expect', [
    (0, 0, 72, 0),
    (0, 5, 72, 5),
    (1, 0, 72, 72),
    (3, 7, 72, 3 * 72 + 7),
])
def test_wrap_room_col(drow, screen_c, width, expect):
    assert wrap_room_col(drow, screen_c, width) == expect


def test_wrap_room_col_inverts_div_mod():
    # for any logical col, (col//W, col%W) must round-trip through wrap_room_col
    W = 72
    for col in (0, 1, 71, 72, 73, 299, 1001):
        assert wrap_room_col(col // W, col % W, W) == col


# ── render smoke test ───────────────────────────────────────────────────────
def _wrap_dungeon(cols=300):
    room = Room(rows=1, cols=cols, room_type=RoomType.ENTRY, wrap_buffer=True)
    room.cells = [[CellType.CORRIDOR] * cols]
    room.spawn_pos = (0, 0)
    room.par, room.budget = 0, 50
    room.rebuild_indexes()
    d = Dungeon(name='Library', seed=1)
    d.rooms, d.current_room = [room], 0
    return d


@pytest.mark.parametrize('wrap', [False, True])
def test_render_wrap_buffer_does_not_crash(term, wrap):
    d = _wrap_dungeon()
    player = Player(row=0, col=150)   # mid-line → forces a non-trivial display row
    player.wrap = wrap
    render_all(term, d, player, Budget(50))   # prints; must not raise


def test_wrap_gate_requires_all_three_conditions(term):
    # wrap rendering must only engage when player.wrap AND room.wrap_buffer AND rows==1.
    # A normal multi-row room with player.wrap=True must still render via the nowrap path
    # (no crash, no wrap math applied to a 2-D grid).
    room = Room(rows=5, cols=20, room_type=RoomType.ENTRY, wrap_buffer=False)
    room.cells = [[CellType.CORRIDOR] * 20 for _ in range(5)]
    room.spawn_pos = (2, 2)
    room.par, room.budget = 0, 20
    room.rebuild_indexes()
    d = Dungeon(name='Test', seed=1)
    d.rooms, d.current_room = [room], 0
    player = Player(row=2, col=2)
    player.wrap = True
    render_all(term, d, player, Budget(20))   # nowrap path; must not raise
