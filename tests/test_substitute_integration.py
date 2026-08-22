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

"""End-to-end :s / :g / & through the real run_dungeon loop: undo, the c (confirm)
flag, :v / :g! inversion, and budget. Driven on plain custom rooms (admin player)."""
from blessed import Terminal
from blessed.keyboard import Keystroke

import vimny.game as main
import vimny.engine.substitute as S
from vimny.engine.world import Dungeon, Entity, Room, RoomType, CharRun, CellType


def _ks(c, name=None):
    return Keystroke(c, name=name)


def _dungeon(lines, cols=None):
    rows = len(lines)
    cols = cols or max(len(l) for l in lines) + 6
    d = Dungeon(name='t', seed=1)
    r = Room(room_type=RoomType.ENTRY, rows=rows, cols=cols)
    r.cells = [[CellType.FLOOR] * cols for _ in range(rows)]
    runs = []
    for ri, ln in enumerate(lines):
        for ci, ch in enumerate(ln):
            if ch != ' ':
                runs.append(CharRun(ri, ci, (ch,), 'ancient'))
    r.char_runs = runs
    r.spawn_pos = (0, 0); r.budget = 999; r.par = 5; r.answer = ''
    r.rebuild_indexes(); d.rooms = [r]; d.current_room = 0
    return d


def _run(d, keys):
    term = Terminal(force_styling=False)
    it = iter([_ks(c) for c in keys])
    term.inkey = lambda *a, **k: next(it, _ks(''))
    spent = {}
    main.render_all = lambda t, dn, pl, bg, message='', *a, **k: spent.update(v=bg.spent)
    main.run_dungeon(term, 'spellwrights_forge', {}, player_name='admin', _dungeon=d)
    return [S.line_text(d.room, r)[0] for r in range(d.room.rows)], spent.get('v')


def test_substitute_is_undoable():
    d = _dungeon(['foo foo'])
    lines, _ = _run(d, list(':s/foo/X/g') + ['\r'] + ['u'] + list(':q!') + ['\r'])
    assert lines == ['foo foo']                     # u restored the line


def test_substitute_charges_budget():
    d = _dungeon(['foo'])
    _lines, spent = _run(d, list(':s/foo/bar/') + ['\r'] + list(':q!') + ['\r'])
    assert spent == len(':s/foo/bar/')              # len(cmd)+1 (the ':' counts)


def test_confirm_flag_picks_matches():
    d = _dungeon(['old old old'])
    # :s/old/new/gc → confirm y, n, y  →  new old new
    keys = list(':s/old/new/gc') + ['\r'] + ['y', 'n', 'y'] + list(':q!') + ['\r']
    lines, _ = _run(d, keys)
    assert lines == ['new old new']


def test_confirm_quit_stops():
    d = _dungeon(['old old old'])
    keys = list(':s/old/new/gc') + ['\r'] + ['y', 'q'] + list(':q!') + ['\r']
    lines, _ = _run(d, keys)
    assert lines == ['new old old']                 # first replaced, then q halts


def test_v_inverts_global():
    d = _dungeon(['keep me', 'drop', 'keep me', 'drop'])
    lines, _ = _run(d, list(':v/keep/d') + ['\r'] + list(':q!') + ['\r'])
    assert lines == ['keep me', 'keep me']


def test_g_bang_inverts_global():
    d = _dungeon(['hit', 'miss', 'hit'])
    lines, _ = _run(d, list(':g!/hit/d') + ['\r'] + list(':q!') + ['\r'])
    assert lines == ['hit', 'hit']


def test_global_substitute_end_to_end():
    d = _dungeon(['a x', 'b y', 'a z'])
    lines, _ = _run(d, list(':g/a/s/ /-/') + ['\r'] + list(':q!') + ['\r'])
    assert lines == ['a-x', 'b y', 'a-z']


# ── :m / :t carry their creatures ─────────────────────────────────────────────

def _with_gold_on_row0(d, col=1):
    g = Entity(kind='gold', row=0, col=col)
    d.room.entities.append(g)
    d.room.rebuild_indexes()
    return g


def test_moved_line_takes_its_creature_along():
    # the coin is part of the line: row surgery moves it with its text
    d = _dungeon(['aaaa', 'bbbb'])
    _with_gold_on_row0(d)
    # :1m2 — move line 1 below line 2 (dest inside the range would be E134)
    lines, _ = _run(d, list(':1m2') + ['\r'] + list(':q!') + ['\r'])
    assert lines == ['bbbb', 'aaaa']
    golds = [e for e in d.room.entities if e.kind == 'gold' and e.alive]
    assert len(golds) == 1
    assert (golds[0].row, golds[0].col) == (1, 1)


def test_copied_line_mints_a_fresh_creature_not_the_same_one():
    # :t duplicates: both rows hold a live coin, distinct objects
    d = _dungeon(['aaaa'])
    _with_gold_on_row0(d)
    lines, _ = _run(d, list(':t0') + ['\r'] + list(':q!') + ['\r'])
    assert lines == ['aaaa', 'aaaa']
    golds = [e for e in d.room.entities if e.kind == 'gold' and e.alive]
    assert len(golds) == 2
    assert {(g.row, g.col) for g in golds} == {(0, 1), (1, 1)}
    assert golds[0] is not golds[1]


def test_snapshot_excludes_landmarks_and_edit_immune_occupants():
    # exits never fire twice; an edit_immune occupant must not be minted
    # into a copy (:t must not clone the boss)
    from vimny.engine.substitute import _snapshot_rows
    d = _dungeon(['xxxx'])
    r = d.room
    r.entities.append(Entity(kind='gold', row=0, col=0))
    r.entities.append(Entity(kind='warden', row=0, col=2, edit_immune=True))
    r.entities.append(Entity(kind='exit', row=0, col=3))
    r.rebuild_indexes()
    snap = _snapshot_rows(r, 0, 0)
    riders = snap[0][4]
    assert [e.kind for e in riders] == ['gold']
