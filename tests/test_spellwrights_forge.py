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

"""The Spellwright's Forge: the :s / :g rites, driven through the real
run_dungeon keystroke loop. Mend every line ('old'→'new' via :%s, strike the
'cursed' verses via :g/cursed/d); the sanctum seal dissolves and the exit opens."""
import pytest
from blessed import Terminal
from blessed.keyboard import Keystroke

import main
import generation.dungeon_gen as dg
import engine.substitute as S


def _ks(c, name=None):
    return Keystroke(c, name=name)


@pytest.fixture(autouse=True)
def _no_anim(monkeypatch):
    # The victory animations need an initialised colours module; stub them out.
    for fn in ('_win_animation', '_fireworks_animation', '_starfield_victory'):
        monkeypatch.setattr(main, fn, lambda *a, **k: None)


def _run(level, keys, *, player_name='admin', dungeon=None):
    term = Terminal(force_styling=False)
    it = iter([_ks(c) if not isinstance(c, Keystroke) else c for c in keys])
    term.inkey = lambda *a, **k: next(it, _ks(''))
    seen = []
    def cap(t, dn, pl, bg, message='', *a, **k):
        seen.append(message)
    main.render_all = cap
    res = main.run_dungeon(term, level, {}, player_name=player_name, _dungeon=dungeon)
    return res, [m for m in seen if m]


def _texts(room):
    return [S.line_text(room, r)[0] for r in range(room.rows)]


# ── structure ────────────────────────────────────────────────────────────────
def test_builder_structure():
    d = dg.build_dungeon_spellwrights_forge(1)
    r = d.room
    assert r._forge_seal == (dg._FORGE_DOOR, dg._FORGE_DIV)
    assert r.cells[dg._FORGE_DOOR][dg._FORGE_DIV] == main.CellType.WALL    # sealed shut
    kinds = {e.kind for e in r.entities}
    assert 'exit' in kinds and 'entry_marker' in kinds
    txts = _texts(r)
    assert sum('old' in t for t in txts) == 3        # three corrupted wards
    assert sum('cursed' in t for t in txts) == 2     # two cursed verses


# ── the rites open the seal, the exit completes ──────────────────────────────
def test_substitute_and_global_open_the_seal_and_win():
    d = dg.build_dungeon_spellwrights_forge(1)
    keys = (list(':%s/old/new/g') + ['\r']
            + list(':g/cursed/d') + ['\r']
            + ['k', '0'] + ['l'] * 55
            + list(':wq') + ['\r'])
    res, msgs = _run('spellwrights_forge', keys, dungeon=d)
    assert res['won'] is True
    blob = ' || '.join(msgs)
    assert '3 substitutions on 3 lines' in blob
    assert 'fewer lines' in blob
    assert d.room.cells[dg._FORGE_DOOR][dg._FORGE_DIV] == main.CellType.FLOOR   # seal dissolved
    assert not any('old' in t for t in _texts(d.room))


def test_seal_stays_shut_until_both_rites_done():
    d = dg.build_dungeon_spellwrights_forge(1)
    # Only fix the substitutions; the cursed verses remain → seal stays WALL.
    _run('spellwrights_forge', list(':%s/old/new/g') + ['\r'] + list(':q!') + ['\r'],
         dungeon=d)
    assert d.room.cells[dg._FORGE_DOOR][dg._FORGE_DIV] == main.CellType.WALL


# ── & repeats the last :s inside the level ───────────────────────────────────
def test_amp_repeats_last_substitute():
    d = dg.build_dungeon_spellwrights_forge(1)
    # Wards sit on rows 3/5/7 (1-based lines 4/6/8). Mend line 4 with :s, drop to the
    # next ward (row 5) and & to repeat it.
    keys = (list(':4s/old/new/') + ['\r']     # fix the first ward (line 4 = row 3)
            + ['j', 'j', '&']                  # → row 5, & repeats the last :s here
            + list(':q!') + ['\r'])
    _run('spellwrights_forge', keys, dungeon=d)
    txts = _texts(d.room)
    assert sum('old' in t for t in txts) == 1     # two wards mended (:s + &), one left


# ── gating: :s is refused before the Forge teaches it ────────────────────────
def test_substitute_gated_before_forge(monkeypatch):
    # On an early level a non-admin player has not learned 'subst'; :s is refused.
    from engine.world import Dungeon, Room, RoomType, CharRun, CellType
    d = Dungeon(name='t', seed=1)
    r = Room(room_type=RoomType.ENTRY, rows=1, cols=20)
    r.cells = [[CellType.FLOOR] * 20]
    r.char_runs = [CharRun(0, 1, tuple('foo'), 'ancient')]
    r.spawn_pos = (0, 0); r.budget = 99; r.par = 5; r.answer = ''
    r.rebuild_indexes(); d.rooms = [r]; d.current_room = 0
    _run('first_cave', list(':s/foo/bar/') + ['\r'] + list(':q!') + ['\r'],
         player_name='p', dungeon=d)
    assert 'bar' not in S.line_text(r, 0)[0]       # unchanged — the command was refused
