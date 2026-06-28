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

"""The Goblin Gauntlet (slug `goblin_gauntlet`): ; , p.

A combat gauntlet: cross each corridor's water by lining up the goblins with
fg, then ; / , to repeat the find down the row, x to kill, p to drop the banked
key at the col-53 gate.  The canonical answer rides fg/;/, across the goblins —
so NO decorative rune on the floor may carry the goblin glyph 'g', or the
find-scan lands on the decoy instead of a goblin and a corridor's last goblin
survives (the gate never opens).  Regression for the g-rune interception bug:
the cost-vs-par test (test_answer_paths) could not catch it because the tape's
cost was correct; only an end-to-end replay reveals the lost win.
"""
import pytest
from generation.dungeon_gen import build_dungeon_goblin_gauntlet as _build
from tests import SEEDS

# the goblin glyph (engine.world entity_letter / render._REG_ENTITY): fg targets it
_GOBLIN_GLYPH = 'g'


@pytest.mark.parametrize("seed", SEEDS)
def test_no_decor_rune_carries_the_goblin_glyph(seed):
    """Every decorative floor rune is g-free, so fg/;/, only ever land on a real
    goblin — never a same-letter decoy that would strand a corridor's last foe."""
    room = _build(seed).rooms[0]
    offenders = [(ru.row, ru.col, ''.join(ru.symbols)) for ru in room.char_runs
                 if _GOBLIN_GLYPH in ru.symbols]
    assert not offenders, f"decor runes carrying '{_GOBLIN_GLYPH}': {offenders}"


# The canonical fg/;/, + p playthrough (the end-to-end win that the g-rune bug
# broke) is replayed for every seed by the universal
# test_answer_paths.py::test_answer_path_actually_wins.  The decor-glyph invariant
# above is the structural guard that keeps that win reachable.
