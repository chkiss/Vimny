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

"""The shared heart-run builders.

Three screens drew hearts three ways until the counts were unified; these
tests pin the STRING builders too — the plain run (width maths) and the
colored run (one reset per glyph), plus the recolour-everything path the
heart-flash uses.
"""
import pytest

from vimny.render.utils import hearts_plain, hearts_colored


@pytest.fixture(autouse=True)
def _restore_palette_state():
    """init() swaps the module-global terminal; put the real one back so no
    fake escapes leak into whichever render test runs next."""
    import vimny.render.colors as C
    saved = (C._term, C._fg_cache.copy(), C._bg_cache.copy(), C._cap_cache.copy())
    yield
    C._term, fg, bg, cap = saved
    C._fg_cache.clear(); C._fg_cache.update(fg)
    C._bg_cache.clear(); C._bg_cache.update(bg)
    C._cap_cache.clear(); C._cap_cache.update(cap)


def test_plain_run_is_exactly_the_glyphs():
    assert hearts_plain(2, 1, 3) == '♥♥♡░░░'
    assert hearts_plain(0, 0, 6) == '░░░░░░'


def test_colored_run_resets_after_every_glyph():
    import vimny.render.colors as C

    class FakeTerm:
        color_rgb = staticmethod(lambda r, g, b: f'#{r:02x}{g:02x}{b:02x}')
        on_color_rgb = staticmethod(lambda r, g, b: f'b{r}{g}{b}')
        normal = 'N'
        bright_white = 'W'
        bold = 'B'

        def __getattr__(self, name):
            return name

    C.init(FakeTerm())
    # one colour + glyph + reset per heart: a draw cut short mid-row must not
    # bleed colour into whatever is printed next
    out = hearts_colored(1, 1, 1, rst='|')
    assert out.count('|') == 3
    assert out == '#d72d2d♥|#d28719♡|#32323c░|'


def test_flash_recolours_every_heart():
    gold = 'GOLD'
    out = hearts_colored(2, 1, 0, rst='+', full_c=gold, half_c=gold,
                         empty_c=gold)
    assert out == f'{gold}♥+{gold}♥+{gold}♡+'


def test_defaults_come_from_the_palette():
    import vimny.render.colors as C

    class FakeTerm:
        color_rgb = staticmethod(lambda r, g, b: f'#{r:02x}{g:02x}{b:02x}')
        on_color_rgb = staticmethod(lambda r, g, b: f'b{r}{g}{b}')
        normal = 'N'
        bright_white = 'W'
        bold = 'B'

        def __getattr__(self, name):
            return name

    C.init(FakeTerm())
    out = hearts_colored(1, 0, 1, rst='!')
    assert '#d72d2d' in out and '#32323c' in out      # heart_full / heart_empty
