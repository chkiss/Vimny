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

"""The render palette's session caches.

Blessed resolves every capability call through terminfo, and the renderer asks
for the same handful of colors ~2,000 times per frame. `colors.py` resolves
each distinct color once per Terminal and hands back the same STRING (identity,
not just equality). These tests pin that contract — including the part a cache
gets wrong when nobody looks: init() with a DIFFERENT terminal must not serve
the old terminal's escape strings.
"""
from blessed import Terminal

import pytest

from vimny.render import colors
from vimny.render import utils  # noqa: F401  (imports the palette modules)


@pytest.fixture(autouse=True)
def _restore_palette_state():
    """init() swaps the module-global terminal; put back whatever the rest of
    the suite expects so no stale escape strings leak across test files."""
    saved = (colors._term, colors._fg_cache.copy(),
             colors._bg_cache.copy(), colors._cap_cache.copy())
    yield
    colors._term, fg, bg, cap = saved
    colors._fg_cache.clear(); colors._fg_cache.update(fg)
    colors._bg_cache.clear(); colors._bg_cache.update(bg)
    colors._cap_cache.clear(); colors._cap_cache.update(cap)


def test_colors_are_cached_by_identity():
    t = Terminal(force_styling=True)
    colors.init(t)
    assert colors.boss_fg() is colors.boss_fg()
    assert colors.floor_bg() is colors.floor_bg()
    assert colors.normal_fg() is colors.normal_fg()
    # …and each string is what the terminal itself would say
    assert colors.boss_fg() == t.color_rgb(210, 35, 45)


def test_reinit_serves_the_new_terminal_not_the_old_cache():
    styled = Terminal(force_styling=True)
    plain = Terminal(force_styling=False)
    colors.init(styled)
    warm = colors.boss_fg()                 # populate the cache
    assert warm != ''
    colors.init(plain)
    assert colors.boss_fg() != warm         # the old strings must be gone
    assert colors.boss_fg() == plain.color_rgb(210, 35, 45)


def test_unstyled_terminal_caches_empty_strings():
    colors.init(Terminal(force_styling=False))
    assert colors.player_fg() == ''
    assert colors.expl_near() == ''
