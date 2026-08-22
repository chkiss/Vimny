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

"""`format.paste(level, into, at)` — stamp one single-room level onto another.

Phase 5 of the port. These tests pin the contract from both sides: every
positional key moves with the offset (and nothing else does), the refusals
name their field like every other LevelFormatError, mist rides inside the
encoded cells, a composite survives dumps/loads byte-for-byte — and one
driven test composes a two-chamber macro gauntlet ENTIRELY out of pasted
fragments and wins it with q @, which is the feature's reason to exist.
"""
from dataclasses import replace

import pytest
from blessed import Terminal
from blessed.keyboard import Keystroke

import vimny.game as main
from vimny.engine.world import CellType
from vimny.generation.dungeon_gen import Dungeon
from vimny.sharing.format import (Level, LevelFormatError, Room, Fill,
                                  _parse_seal, build, dumps, loads, paste)


def _K(s):
    return [Keystroke(ch) for ch in s]


def blank(name='Blank', rows=20, cols=40, **kw):
    """A canvas of solid stone with nothing in it."""
    base = dict(name=name, rows=rows, cols=cols,
                cells=['W' * cols] * rows, spawn=(rows // 2, cols // 2),
                exit=(rows - 2, cols - 2))
    base.update(kw)
    return Level(**base)


def word_frag(name='Chamber', **kw):
    """A mendable chamber: 'coat' on a full-width floor row, a seal reading
    'cat' once the o is x'd, whose opens turn the fragment's own east doorway
    into a bolted cell until then."""
    cells = ['W' * 13,
             'WFFFFFFFFFFFW',
             'WFFFFFFFFFFFW',
             'FFFFFFFFFFFFF',          # the mend row, edges open
             'WFFFFFFFFFFFW',
             'WFFFFFFFFFFFW',
             'W' * 13]
    base = dict(
        name=name, rows=7, cols=13, cells=cells,
        spawn=(3, 1), exit=(3, 11),
        char_runs=[{'row': 3, 'col': 4, 'symbols': ['c', 'o', 'a', 't'],
                    'kind': 'ancient'}],
    )
    base.update(kw)
    lvl = Level(**base)
    # seals ride the parse path even in fixtures: Level.seals holds world.Seal
    # objects, never the file's dicts
    lvl.seals = [_parse_seal({'scope': 'region', 'match': 'cat',
                              'region': [3, 1, 3, 11], 'opens': [[3, 12]]}, 0)]
    return lvl


# ── the offset audit ─────────────────────────────────────────────────────────

def test_every_positional_key_moves_by_at():
    frag = Level(
        name='F', rows=6, cols=9,
        cells=['WWWWWWWWW',
               'WMFFFWFFW',
               'WFFFFFCAW',
               'WAFFFFFCW',
               'WFFFFFWAW',
               'WWWWWWWWW'],
        spawn=(1, 1), exit=(4, 7),
        veiled=[[1, 2]],
        fills=[Fill(region=(1, 3, 2, 5), pool='plain')],
        char_runs=[{'row': 2, 'col': 2, 'symbols': ['a', 'b'], 'kind': 'ancient'}],
        entities=[{'kind': 'goblin', 'at': [3, 3], 'hp': 1}])
    # seals go through the parse path so the fields are exactly what an
    # author's file produces
    frag.seals = [_parse_seal({'region': [1, 1, 4, 7], 'match': 'cat',
                               'opens': [[2, 2]]}, 0)]

    dr, dc = 5, 11
    host = paste(frag, blank(), (dr, dc))

    assert host.char_runs == [{'row': 2 + dr, 'col': 2 + dc,
                               'symbols': ['a', 'b'], 'kind': 'ancient'}]
    assert host.entities == [{'kind': 'goblin', 'at': [3 + dr, 3 + dc], 'hp': 1}]
    assert host.veiled == [(1 + dr, 2 + dc)]
    (f,) = host.fills
    assert f.region == (1 + dr, 3 + dc, 2 + dr, 5 + dc)
    (s,) = host.seals
    assert s.region == (1 + dr, 1 + dc, 4 + dr, 7 + dc)
    assert s.opens == ((2 + dr, 2 + dc),)
    # and the mist rode along inside the stamped rows (frag row 1 has M at col 1)
    assert 'M' in host.cells[1 + dr]


def test_host_identity_and_doors_survive_fragments_ignored():
    frag = word_frag()
    host = blank(name='Host', author='anon', seed=7, teaches=['x'],
                 solution='tape', intro='hi', vocabulary=['dwarf'],
                 spawn=(9, 20), exit=(17, 37))
    out = paste(frag, host, (2, 2))
    assert (out.name, out.author, out.seed) == ('Host', 'anon', 7)
    assert out.teaches == ['x'] and out.solution == 'tape' and out.intro == 'hi'
    assert out.spawn == (9, 20) and out.exit == (17, 37)   # the FRAGMENT's are ignored


def test_rows_outside_the_footprint_are_byte_identical():
    host = paste(word_frag(), blank(rows=20, cols=30), (3, 5))
    for r in range(20):
        if not 3 <= r < 10:
            assert host.cells[r] == 'W' * 30


def test_mist_rides_inside_footprint_and_host_mist_stands():
    frag = Level(name='M', rows=5, cols=7, cells=[
        'WWWWWWW',
        'WMAFFFW',
        'WAAAFFW',
        'WFFAMFW',
        'WWWWWWW'])
    host_cells = ['W' * 25] * 12
    host_cells[1] = 'W' + 'MA' + 'W' * 22          # host mist OUTSIDE any footprint
    host = Level(name='H', rows=12, cols=25, cells=host_cells)

    out = paste(frag, host, (5, 10))

    assert 'M' in out.cells[6] and 'M' in out.cells[8]   # fragment mist moved in
    assert out.cells[1] == host_cells[1]                  # host mist untouched


def test_composite_round_trips_byte_for_byte():
    host = paste(word_frag(), blank(name='Host'), (4, 9))
    back = loads(dumps(host))
    assert back.cells == host.cells
    assert back.char_runs == host.char_runs
    assert back.entities == host.entities
    assert [(s.region, s.match, s.opens) for s in back.seals] == \
           [(s.region, s.match, s.opens) for s in host.seals]


def test_vocabulary_merges_host_order_first():
    frag = Level(name='F', rows=5, cols=7, cells=['W' * 7] * 5,
                 fills=[Fill(region=(1, 1, 3, 5), pool='author')],
                 vocabulary=['dwarf', 'rogue'])
    out = paste(frag, blank(vocabulary=['elf']), (2, 2))
    assert out.vocabulary == ['elf', 'dwarf', 'rogue']


def test_fill_numbering_hosts_fills_come_first():
    host = blank(fills=[Fill(region=(1, 1, 2, 3), pool='plain')])
    frag = Level(name='F', rows=5, cols=7, cells=['W' * 7] * 5,
                 fills=[Fill(region=(1, 1, 2, 3), pool='plain')])
    out = paste(frag, host, (6, 6))
    assert len(out.fills) == 2
    assert out.all_fills[0].region == (1, 1, 2, 3)          # the HOST's


# ── the refusals ─────────────────────────────────────────────────────────────

def test_a_then_level_is_refused_as_a_fragment():
    frag = word_frag()
    frag.then = [Room(rows=5, cols=7)]
    with pytest.raises(LevelFormatError, match='then'):
        paste(frag, blank(), (0, 0))


@pytest.mark.parametrize('side', ['source', 'host'])
def test_wrap_buffers_are_refused_on_either_side(side):
    if side == 'source':
        with pytest.raises(LevelFormatError, match='fragment'):
            paste(word_frag(wrap=True, wrap_width=40), blank(), (0, 0))
    else:
        with pytest.raises(LevelFormatError, match='into'):
            paste(word_frag(), blank(wrap=True, wrap_width=40), (0, 0))


def test_off_canvas_is_refused_and_names_resize():
    with pytest.raises(LevelFormatError, match='resize'):
        paste(word_frag(), blank(rows=20, cols=40), (10, 30))


def test_negative_offset_is_refused():
    with pytest.raises(LevelFormatError, match='negative'):
        paste(word_frag(), blank(), (-1, 0))


def test_overlap_is_refused_and_names_the_cell():
    host_cells = ['W' * 30] * 20
    host_cells[5] = 'W' * 7 + 'FFF' + 'W' * 20      # floor where the fragment lands
    host = Level(name='H', rows=20, cols=30, cells=host_cells)
    with pytest.raises(LevelFormatError, match=r'row 5, column 7'):
        paste(word_frag(), host, (3, 5))


def test_paste_is_pure_in_the_host_it_rejects():
    host = blank()
    before = (list(host.cells), list(host.vocabulary))
    with pytest.raises(LevelFormatError):
        paste(word_frag(), host, (50, 50))           # far off canvas
    assert (host.cells, host.vocabulary) == before


# ── playability ──────────────────────────────────────────────────────────────

def test_composite_builds_shut_and_holds_its_geometry():
    host = paste(word_frag(), blank(rows=16, cols=40), (2, 2))
    d = build(host)
    room = d.rooms[0]
    assert isinstance(d, Dungeon) and room.rows == 16 and room.cols == 40
    assert room.cells[5][4] is CellType.FLOOR        # frag row 3, col 2 → (5, 4)
    # the fragment's seal came along and was built SHUT over its opens cell
    assert room.seals and room.cells[5][14] is CellType.WALL   # (3,12) → (5,14)


# ── the flagship: a gauntlet composed ONLY from pasted fragments ────────────

def _echo_gauntlet():
    """Two identical 'coat'→'cat' chambers pasted onto a bare canvas, joined
    by a corridor the HOST carves between the footprints. Mend chamber One
    with a recorded macro, replay it on chamber Two, walk out east."""
    host = blank(name='Echoes', rows=20, cols=34)
    row5 = list('W' * 34)
    for c in (14, 15, 16, 30, 31, 32):               # corridor + exit landing
        row5[c] = 'F'
    host = replace(host, cells=[''.join(row5) if r == 5 else host.cells[r]
                                for r in range(20)],
                   spawn=(5, 1), exit=(5, 31))
    host = paste(word_frag('One'), host, (2, 1))     # rows 2-8,  cols 1-13
    host = paste(word_frag('Two'), host, (2, 17))    # rows 2-8,  cols 17-29
    return build(host, par=60)


def _drive(dungeon, keys, monkeypatch):
    keys = list(keys) + _K(':wq\r')
    monkeypatch.setattr(main, 'render_all', lambda *a, **k: None)
    monkeypatch.setattr(main.time, 'sleep', lambda *a, **k: None)
    for anim in ('_fireworks_animation', '_win_animation', '_starfield_victory',
                 '_heart_container_animation', '_unlock_animation',
                 '_void_fall_animation', '_drown_animation'):
        monkeypatch.setattr(main, anim, lambda *a, **k: None)
    monkeypatch.setattr(Terminal, 'height', property(lambda self: 45))
    term = Terminal()
    it = iter(keys)
    monkeypatch.setattr(term, 'inkey', lambda *a, **k: next(it, Keystroke('')))
    return main.run_dungeon(term, 'echo_gauntlet', {}, player_name='Scribe',
                            _dungeon=dungeon)


def test_macro_recorded_once_replays_across_pasted_replicas(monkeypatch):
    d = _echo_gauntlet()
    room = d.rooms[0]
    # the spawn sits on chamber One's mend row at fragment-relative (3, 0) —
    # the SAME relative position both chambers share, which is what makes ONE
    # macro body fit either replica.
    assert tuple(room.spawn_pos) == (5, 1)

    # From rel (3,0): five l lands ON the 'o' (rel cols 1..5), x mends
    # 'coat'→'cat', the seal reads true and the east doorway unbolts. Walk
    # eleven l east through it and the corridor into chamber Two — again at
    # rel (3,0) — THEN replay the macro there, and nine more l to the exit.
    tape = ('qa' + 'lllllx' + 'q'      # record AND perform the first mend
            + 'lllllllllll'            # cross the door and corridor (cols 6→17)
            + '@a'                     # replay the macro on the pasted twin
            )
    result = _drive(d, _K(tape + 'lllllllll'), monkeypatch)   # cols 22→31, out
    assert result['action'] == 'wq'
    assert result['won'] is True
