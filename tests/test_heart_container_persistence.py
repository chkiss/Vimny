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

"""A heart container only PERSISTS when the player writes (:w / :wq).

Picking one up grants +2 max HP for the current run, but the upgrade (max_hp + the
collected-hearts record) is staged and committed only on a write — quitting with :q!
discards it, and a plain :q is blocked (E37) while the pickup is unsaved.  Regression:
pickup used to mutate `progress` immediately, so a heart survived an unsaved exit.

Driven through the real run_dungeon loop on a tiny hand-built dungeon."""
from blessed.keyboard import Keystroke
from blessed import Terminal

import vimny.game as main
from vimny.engine.world import Dungeon, Room, RoomType, CellType, Entity


def _ks(ch, name=None):
    return Keystroke(ch, name=name)


def _heart_dungeon():
    room = Room(rows=5, cols=20, room_type=RoomType.ENTRY)
    room.cells = [[CellType.WALL] * 20 for _ in range(5)]
    for c in range(1, 19):
        room.cells[2][c] = CellType.CORRIDOR
    room.spawn_pos = (2, 2)
    room.exit_pos  = (2, 18)
    room.entities  = [Entity(kind='heart_container', row=2, col=3)]
    room.par, room.budget, room.answer = 10, 40, ''
    room.rebuild_indexes()
    d = Dungeon(name='Test', seed=1)
    d.rooms, d.current_room = [room], 0
    return d


def _drive(monkeypatch, keys, progress):
    """Run the loop with scripted keys as a normal (non-admin) player; admin would
    bypass the :q write-guard.  Returns (result, error_frames)."""
    frames = []
    monkeypatch.setattr(main, 'render_all',
                        lambda term, d, p, b, *a, **k: frames.append(p.error))
    monkeypatch.setattr(main.time, 'sleep', lambda *a, **k: None)
    term = Terminal()
    it = iter(keys)
    monkeypatch.setattr(term, 'inkey', lambda *a, **k: next(it, _ks('')))
    result = main.run_dungeon(term, 'dummy', progress, player_name='Normand',
                              _dungeon=_heart_dungeon())
    return result, frames


# l x  → pick the heart up (move onto it, then x)
_PICKUP = [_ks('l'), _ks('x')]


def test_quit_bang_discards_the_heart(monkeypatch):
    progress = {}
    result, _ = _drive(monkeypatch, _PICKUP + [_ks(':'), _ks('q'), _ks('!'), _ks('\r')], progress)
    assert result['action'] == 'quit'
    assert progress.get('collected_hearts', []) == []      # nothing persisted
    assert progress.get('max_hp', 6) == 6                  # upgrade discarded


def test_wq_persists_the_heart(monkeypatch):
    progress = {}
    result, _ = _drive(monkeypatch, _PICKUP + [_ks(':'), _ks('w'), _ks('q'), _ks('\r')], progress)
    assert result['action'] == 'wq'
    assert progress['collected_hearts'] == [['dummy', 2, 3]]
    assert progress['max_hp'] == 8                          # +2 committed


def test_plain_q_is_blocked_while_the_heart_is_unsaved(monkeypatch):
    progress = {}
    # :q first (should be refused with E37), then :q! to actually leave
    keys = _PICKUP + [_ks(':'), _ks('q'), _ks('\r'),
                      _ks(':'), _ks('q'), _ks('!'), _ks('\r')]
    result, errors = _drive(monkeypatch, keys, progress)
    assert any('E37' in (e or '') for e in errors)         # :q was refused
    assert result['action'] == 'quit'                      # :q! got out
    assert progress.get('max_hp', 6) == 6                  # still discarded
