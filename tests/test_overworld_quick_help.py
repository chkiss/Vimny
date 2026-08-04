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

"""The overworld's Quick Help row.

`%` is netrw's "new file" and here it forges a new level. It is the ONLY way to
start one, and it was advertised nowhere — so the one thing an author most needs
to know was the one thing the screen did not say.

It is admin-only, so it is shown to the admin and to nobody else: a key everyone
can see but only one player may press is worse than one that is simply not
advertised.

The row also has to FIT. `_row` pads with `max(0, cw - vis)` and does nothing
when a row is too long, so an over-wide help line does not clip — it pushes the
right border out. That was already happening at 80 columns before `%` was added.
"""
import re

import pytest
from blessed import Terminal

from vimny.engine.player import Player
from vimny.render.overworld import render_overworld
from vimny.render.utils import inner_w

_GUTTER = 4          # render.overworld's GW when line numbers are on


def _draw(term, name, **kw):
    import vimny.render.colors as C
    C.init(term)                       # the palette reads the live terminal
    player = Player()
    player.name = name
    lines = [{'type': 'comment', 'tag': t}
             for t in ('div', 'title', 'path', 'sort', 'help', 'div')]
    import io
    import contextlib
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        render_overworld(term, player, {}, 0, lines, **kw)
    return re.sub(r'\x1b\[[0-9;?]*[a-zA-Z]', '', buf.getvalue())


def _help_row(raw):
    for line in raw.split('\n'):
        if 'Quick Help' in line:
            return line
    return ''


class _FixedSize(Terminal):
    """A terminal of a known size.

    Subclassed rather than monkeypatched: `type(t).width = ...` sets the
    property on the Terminal CLASS, which every other test in the suite shares —
    doing that here took 458 of them down with it.
    """

    def __init__(self, width):
        super().__init__(force_styling=None)
        self._fixed_w = width

    @property
    def width(self):
        return self._fixed_w

    @property
    def height(self):
        return 41


def _term(width):
    return _FixedSize(width)


def test_admin_is_told_how_to_forge_a_new_level():
    raw = _draw(_term(120), 'admin')
    assert '%:new' in _help_row(raw)


def test_an_ordinary_player_is_not():
    """They cannot press it — `run_overworld` refuses with 'Only the admin can
    forge new levels.' Advertising a key that answers back with a refusal is
    worse than not advertising it."""
    raw = _draw(_term(120), 'Scribe')
    assert '%' not in _help_row(raw)


@pytest.mark.parametrize('width', [80, 100, 120, 189, 250])
@pytest.mark.parametrize('name', ['admin', 'Scribe'])
def test_the_help_row_never_pushes_the_border_out(width, name):
    """The invariant is that it is the SAME WIDTH as every other row. A row that
    overflows takes the right border with it, so comparing against the divider
    catches it where a length bound alone might not."""
    raw = _draw(_term(width), name)
    rows = [l for l in raw.split('\n') if l.strip()]
    ruler = next(l for l in rows if '====' in l)
    row = _help_row(raw)
    assert row, 'no help row drawn'
    assert len(row) == len(ruler), (width, name, len(row), len(ruler))


def test_the_help_row_would_overflow_unfitted():
    """Not hypothetical: the full hint list is wider than an 80-column box, so
    the trim is doing real work rather than passing vacuously."""
    cw = inner_w(_term(80)) - _GUTTER
    full = ('"   Quick Help: j/k:move  gg/G:top/bot  Enter:open  %:new  '
            'D:del  R:rename  -:up  :q:quit')
    assert len(full) > cw


def test_the_narrowest_terminal_keeps_the_new_level_hint():
    """The row is trimmed from the END when it will not fit, which is why `%`
    sits near the front: the hint that exists to be DISCOVERED must not be the
    first casualty of a small window."""
    assert '%:new' in _help_row(_draw(_term(80), 'admin'))
