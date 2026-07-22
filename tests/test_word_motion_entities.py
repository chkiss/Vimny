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

"""Option A: navigation word motions (w/b/e/ge) may land on a content entity
(a key, a goblin) sitting on bare floor — so `w` replaces `2l` to reach a key.
Operators (dw/de/cw) stay entity-blind (pure text words), and an entity standing
ON text stays part of that word, never its own stop."""
from engine.world import Room, RoomType, CellType, CharRun, Entity
from engine.player import Player
from engine.motion import apply_motion


def _room():
    #  col: 1 2      6        (a key on bare floor at col 6)
    #       a b      🗝
    r = Room(room_type=RoomType.ENTRY, rows=1, cols=12)
    r.cells = [[CellType.FLOOR] * 12]
    r.char_runs = [CharRun(0, 1, ('a', 'b'), 'ancient')]
    r.entities = [Entity(kind='floor_key', row=0, col=6)]
    r.rebuild_indexes()
    return r


def test_w_jumps_to_a_key_on_floor():
    r = _room()
    p = Player(row=0, col=1)
    apply_motion(p, 'w', 1, r)
    assert p.col == 6                              # w reached the key (was 2l)


def test_ge_lands_on_the_key():
    r = _room()
    p = Player(row=0, col=8)
    apply_motion(p, 'ge', 1, r)
    assert p.col == 6


def test_operator_motions_stay_text_only():
    r = _room()
    p = Player(row=0, col=1)
    apply_motion(p, 'w', 1, r, entity_stops=False)   # operator span computation
    assert p.col != 6                              # the key is invisible to dw/cw


def test_entity_on_text_is_part_of_that_word():
    # a goblin standing ON the 'b' of "ab" does not split the word — w from the
    # word start still crosses the whole "ab", it is not a new stop.
    r = Room(room_type=RoomType.ENTRY, rows=1, cols=12)
    r.cells = [[CellType.FLOOR] * 12]
    r.char_runs = [CharRun(0, 1, ('a', 'b'), 'ancient'),
                   CharRun(0, 6, ('c', 'd'), 'ancient')]
    r.entities = [Entity(kind='goblin', row=0, col=2)]   # on the 'b'
    r.rebuild_indexes()
    p = Player(row=0, col=1)
    apply_motion(p, 'w', 1, r)
    assert p.col == 6                              # skipped past ab (goblin ⊂ ab), to cd


def test_a_room_may_opt_out(monkeypatch):
    r = _room()
    r.entity_word_stops = False                   # the Operator's Vault does this
    p = Player(row=0, col=1)
    apply_motion(p, 'w', 1, r)
    assert p.col != 6                              # key not a stop when opted out
