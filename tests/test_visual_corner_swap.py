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

"""`o` and `O` — moving the cursor to the other end of a visual selection.

`O` shipped in 8d62d60 with no test at all, which is how it came to be listed
as unbuilt for a month. The important property is the LAST test here: neither
key can change which cells are selected, only which end the cursor holds. That
is what lets the verb be handed to a player without re-auditing the par of
every level that owns a visual mode — a claim worth a test rather than a
comment.
"""
import pytest
from vimny.engine.modes import Mode
from vimny.engine.visual import swap_ends, in_selection

MODES = [Mode.VISUAL, Mode.VISUAL_LINE, Mode.VISUAL_BLOCK]

ANCHOR, CURSOR = (2, 3), (5, 9)


@pytest.mark.parametrize('vmode', MODES)
def test_o_trades_the_two_ends(vmode):
    assert swap_ends(ANCHOR, CURSOR, vmode) == (CURSOR, ANCHOR)


def test_O_in_block_mode_swaps_only_the_columns():
    # The cursor keeps its own row and crosses to the far side of the
    # rectangle; the anchor keeps its row and takes the column the cursor left.
    anchor, cursor = swap_ends(ANCHOR, CURSOR, Mode.VISUAL_BLOCK, corner=True)
    assert cursor == (5, 3), 'the cursor should stay on row 5'
    assert anchor == (2, 9), 'the anchor should stay on row 2'


@pytest.mark.parametrize('vmode', [Mode.VISUAL, Mode.VISUAL_LINE])
def test_O_outside_block_mode_is_just_o(vmode):
    """Vim-true: only a rectangle has corners to cross to."""
    assert swap_ends(ANCHOR, CURSOR, vmode, corner=True) == \
           swap_ends(ANCHOR, CURSOR, vmode)


@pytest.mark.parametrize('vmode', MODES)
@pytest.mark.parametrize('corner', [False, True])
def test_pressing_it_twice_returns_to_where_you_started(vmode, corner):
    once  = swap_ends(ANCHOR, CURSOR, vmode, corner=corner)
    twice = swap_ends(*once, vmode, corner=corner)
    assert twice == (ANCHOR, CURSOR)


@pytest.mark.parametrize('vmode', MODES)
@pytest.mark.parametrize('corner', [False, True])
def test_the_selection_itself_never_moves(vmode, corner):
    """The no-cheese property, and the reason this verb costs no par audit.

    Every operator reads the span through block_bounds/visual_span, which take
    min and max of the two ends — so rearranging the same two corners cannot
    change one cell of what d/y/c would touch.
    """
    before = {(r, c) for r in range(8) for c in range(12)
              if in_selection(ANCHOR, CURSOR, vmode, r, c)}
    anchor, cursor = swap_ends(ANCHOR, CURSOR, vmode, corner=corner)
    after = {(r, c) for r in range(8) for c in range(12)
             if in_selection(anchor, cursor, vmode, r, c)}
    assert before == after
    assert before, 'the fixture selects nothing — the test would pass vacuously'
