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

"""The entity glyph layer — one source of truth (engine.world.entity_letter).

Every targeting command (f/F/t/T, / ? * #, ^, gg/G) must agree with the glyph
the renderer draws on top of a cell. These used to be FOUR hand-kept copies of
the same entity→letter map (renderer, motion._cell_char, search._entity_glyph,
the caret stops) that drifted apart — the recurring "the command can't see the
entity sitting on text" class of bug. These tests pin all the consumers to the
single map so a future edit to one can't silently desync the others.
"""
import pytest

from engine.world import (Room, RoomType, Entity, CellType, CharRun,
                          entity_letter, CARET_TRANSPARENT)
from engine.modes import Mode
from engine.motion import _cell_char, _apply_find
from engine.player import Player
from engine.search import _line_string, match_cells
from render.renderer import _ent_cell_str
import render.colors as C


@pytest.fixture(autouse=True)
def _init_colors():
    from blessed import Terminal
    C.init(Terminal())


# every kind that paints a findable letter, with the tag it needs (if any)
LETTER_ENTITIES = [
    Entity(kind='warden',   row=0, col=5, hp=3, max_hp=3),
    Entity(kind='goblin',   row=0, col=5, hp=1, max_hp=1),                 # plain → 'g'
    Entity(kind='goblin',   row=0, col=5, hp=2, max_hp=2, tag='echo'),     # impostor → 'W'
    Entity(kind='dynamite', row=0, col=5),
    Entity(kind='archivist',row=0, col=5),
]


def _room_with(ent) -> Room:
    cells = [[CellType.FLOOR] * 12 for _ in range(3)]
    room = Room(room_type=RoomType.BOSS, rows=3, cols=12, cells=cells,
                search_glyph_entities=True)
    ent.row, ent.col = 1, 5
    room.add_entity(ent)
    room.rebuild_indexes()
    return room


@pytest.mark.parametrize("ent", LETTER_ENTITIES, ids=lambda e: f"{e.kind}-{e.tag or 'plain'}")
def test_all_consumers_agree_with_entity_letter(ent):
    letter = entity_letter(ent)
    assert letter is not None
    room = _room_with(ent)

    # 1) the renderer draws exactly that letter on the cell
    drawn = _ent_cell_str(ent, room, 1, 5, Mode.NORMAL, C.floor_bg())
    assert letter in drawn, f"renderer shows {drawn!r}, not {letter!r}"

    # 2) f/F/t/T sees it (over bare floor) …
    assert _cell_char(room, 1, 5) == letter
    # … even when the entity stands ON char-run text (the wardenverse case)
    room.add_char_run(CharRun(1, 0, tuple('abcdefghijkl'), 'plain'))
    room.rebuild_indexes()
    assert _cell_char(room, 1, 5) == letter, "glyph must beat the text beneath it"
    p = Player(); p.row, p.col = 1, 1
    assert _apply_find(p, 'f', letter, room) and p.col == 5

    # 3) search (glyph-overlay rooms) finds it at the same cell
    assert (1, 5) in match_cells(room, letter)


def test_line_string_overlays_letter_on_text():
    ent = Entity(kind='warden', row=0, col=3, hp=3, max_hp=3)
    cells = [[CellType.FLOOR] * 10]
    room = Room(room_type=RoomType.BOSS, rows=1, cols=10, cells=cells,
                search_glyph_entities=True)
    room.add_char_run(CharRun(0, 0, tuple('abcdefghij'), 'plain'))
    room.add_entity(ent)
    room.rebuild_indexes()
    text, base = _line_string(room, 0)
    assert text[ent.col - base] == 'W'          # the 'W' overlays the 'd' beneath it


def test_non_letter_entities_are_not_text_matchable():
    # doors/keys/chests/exits paint decorative symbols — entity_letter is None, so
    # f/t fall through to the char/terrain beneath (regression-guarded in test_motion).
    for kind in ('door', 'locked_door', 'exit', 'floor_key', 'chest_random', 'heart_container',
                 'seal_door', 'entry_marker', 'shield'):
        assert entity_letter(Entity(kind=kind, row=0, col=0)) is None


def test_caret_transparent_is_floorlike_only():
    # the caret passes through floor-like markers; foes/loot are content it stops on
    assert {'door', 'exit', 'seal_door'} <= CARET_TRANSPARENT
    assert not ({'warden', 'goblin', 'floor_key', 'chest_random'} & CARET_TRANSPARENT)
