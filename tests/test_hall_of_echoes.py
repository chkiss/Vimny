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

"""The Hall of Echoes (q @ ") — the macro gauntlet, v4 (2026-07-20).

Two rooms. Room 0: a poem hall — one famous 10-line rhyme (5-poem pool)
with a deadpan intruder word prepended to every line; daw at the head,
recorded once (qa), replayed down the hall. Room 1: ONE tall map of REPLICA
chambers stacked south, each the EXACT puzzle from a source level whose own
tape repeats a 2+-char string — the Echo Vault (w w r/., qb), the Selection
Halls' panel cycle (k vbp, qc), the Refrain Vault's reprise (p 3j, qd).
Chambers are runs of text rows split by stone bands whose west gates grind
open as each chamber reads true; the exit in the last band needs every
chamber true. Replayed keys are budget-free; the all-manual road wins at
1★ (120 measured ≤ budget 160)."""
import re

import pytest
from blessed.keyboard import Keystroke
from blessed import Terminal

import main
from engine.world import CellType
from generation.dungeon_gen import (
    build_dungeon_hall_of_echoes,
    _HE_COLS, _HE_TX, _HE_GATE_COL, _HE_PAR, _HE_BUDGET, _HE_POEMS,
    _HE_WARP, _he_build_chambers,
)
from tests import SEEDS
import random

ESC = Keystroke('\x1b', code=361, name='KEY_ESCAPE')


def _K(s):
    return [ESC if ch == '\x1b' else Keystroke(ch) for ch in s]


def _tapes(seed):
    d = build_dungeon_hall_of_echoes(seed)
    return d.rooms[0].answer, d.rooms[1].answer


def _expand(tape):
    """Turn each 'qX body qN@X' macro into body*(N+1) — the no-macro road."""
    s = tape.replace(' ', '')
    out, i = '', 0
    while i < len(s):
        m = re.match(r'q([a-z])(.*?)q(\d*)@\1', s[i:])
        if m:
            body, cnt = m.group(2), m.group(3)
            out += body * (1 + (int(cnt) if cnt else 1))
            i += m.end()
        else:
            out += s[i]
            i += 1
    return out


def _drive(dungeon, keys, monkeypatch, finish=':wq\r', name='Scribe'):
    keys = list(keys) + _K(finish)
    monkeypatch.setattr(main, 'render_all', lambda *a, **k: None)
    monkeypatch.setattr(main.time, 'sleep', lambda *a, **k: None)
    for anim in ('_fireworks_animation', '_win_animation', '_starfield_victory',
                 '_heart_container_animation', '_unlock_animation',
                 '_void_fall_animation', '_drown_animation', '_sc_twinkle_animation'):
        monkeypatch.setattr(main, anim, lambda *a, **k: None)
    monkeypatch.setattr(Terminal, 'height', property(lambda self: 45))
    term = Terminal()
    it = iter(keys)
    monkeypatch.setattr(term, 'inkey', lambda *a, **k: next(it, Keystroke('')))
    return main.run_dungeon(term, 'hall_of_echoes', {}, player_name=name,
                            _dungeon=dungeon)


def _drive_spent(dungeon, keys, monkeypatch, budget=9999):
    for room in dungeon.rooms:
        room.budget = budget
    box = {}
    orig = main._calc_stars
    monkeypatch.setattr(main, '_calc_stars',
                        lambda won, budget, room, player, level='':
                            (box.__setitem__('spent', budget.spent),
                             orig(won, budget, room, player, level))[1])
    result = _drive(dungeon, keys, monkeypatch)
    return result, box.get('spent')


# ── structure ─────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("seed", SEEDS)
def test_two_rooms_poem_hall_and_gauntlet_map(seed):
    d = build_dungeon_hall_of_echoes(seed)
    assert len(d.rooms) == 2
    poem, gmap = d.rooms
    assert poem._he_poem in {p[0] for p in _HE_POEMS}
    for room in d.rooms:
        assert room.cols == _HE_COLS
        assert room.par == _HE_PAR and room.budget == _HE_BUDGET
    er, ec = poem.exit_pos
    assert poem.cells[er][ec] == CellType.WALL
    assert not any(e.kind == 'exit' for e in poem.entities)
    ge, gc = gmap.exit_pos
    assert gmap.cells[ge][gc] == CellType.WALL
    assert any(e.kind == 'exit' and (e.row, e.col) == (ge, gc)
               for e in gmap.entities)


def test_poem_pool_shape():
    assert len(_HE_POEMS) == 5
    for _name, lines, intr in _HE_POEMS:
        assert len(lines) == 10 and len(intr) == 10
        for w in intr:
            assert w.isalpha()
        for ln, w in zip(lines, intr):
            assert len(w) + 1 + len(ln) <= _HE_COLS - _HE_TX - 3


@pytest.mark.parametrize("seed", SEEDS)
def test_poem_hall_lays_intruder_plus_true_line_uncolored(seed):
    from engine import substitute as S
    d = build_dungeon_hall_of_echoes(seed)
    room = d.rooms[0]
    _name, lines, intr = next(p for p in _HE_POEMS if p[0] == room._he_poem)
    for i in range(10):
        t = S.line_text(room, 1 + i)[0].strip()
        assert t == f'{intr[i]} {lines[i]}'
    assert all(ru.kind == 'ancient' for ru in room.char_runs)


def test_chambers_are_exact_source_replicas():
    """The three replica chambers are drawn from the SOURCE levels' own pick
    functions, so they wear the original faces exactly: the Echo Vault's
    warped runes, the Selection Halls' 4-word panel cycle, the Refrain
    Vault's London Bridge reprise. Every tape segment records on a fresh
    register (qb, qc, qd — the named-register drill)."""
    chambers = _he_build_chambers(random.Random(0))
    assert len(chambers) == 3
    # Echo Vault: the lock row carries warped runes; a plaque band above
    ev = chambers[0]
    lock = ''.join(''.join(sym for _c, sym in
                           [(col + k, s) for col, text, _kind in ev['rows'][0]
                            for k, s in enumerate(text)]))
    assert any(g in lock for g in ('♄', '☿', '♆', '⚸'))
    assert ev['plaques'], "the Echo Vault keeps its sealed plaque band"
    # Selection Halls: four panel rows, a 4-cycle (each row wears another's word)
    pn = chambers[1]
    assert len(pn['done']) == 4
    words = [d.split()[1] for d in pn['done']]
    assert len(set(words)) == 4
    # Refrain Vault: the reprise — 'my fair lady.' given once, laid four times
    rv = chambers[2]
    # the reprise appears 4 times in the true song, plus the given shelf copy
    assert rv['done'].count('my fair lady.') == 5
    # but it is LAID only once (the shelf) — the other four are pasted
    assert sum(1 for row in rv['rows']
               for _c, t, _k in row if t == 'my fair lady.') == 1
    # Each chamber records on a fresh register in order — b, c, d. (The Echo
    # Vault and Refrain segments lead with their recording; the Selection
    # panel swap needs a one-time `ye` yank before its repeatable k-vbp unit,
    # so its qc sits just after the setup — the exact puzzle is preserved
    # over a cosmetic leading-q.)
    regs = [re.search(r'q([a-z])', ch['tape']).group(1) for ch in chambers]
    assert regs == ['b', 'c', 'd']


def test_map_is_one_buffer_with_stone_bands():
    d = build_dungeon_hall_of_echoes(0)
    gmap = d.rooms[1]
    chambers = _he_build_chambers(random.Random(0))
    runs, cur = [], 0
    for r in range(2, gmap.rows):          # row 1 is the sealed plaque band
        has_text = any(main._wla_floor_text(gmap, r).strip()
                       for _ in [0]) and bool(
                       [ru for ru in gmap._char_runs_by_row.get(r, [])
                        if gmap.cells[r][ru.col] != CellType.WALL])
        if has_text:
            cur += 1
        elif cur:
            runs.append(cur)
            cur = 0
    if cur:
        runs.append(cur)
    assert len(runs) == len(chambers)
    assert runs == [len(ch['rows']) for ch in chambers]


# ── the driven gauntlet ──────────────────────────────────────────────────────

@pytest.mark.parametrize("seed", SEEDS)
def test_canonical_macro_run_wins_at_par(seed, monkeypatch):
    d = build_dungeon_hall_of_echoes(seed)
    poem_tape, map_tape = d.rooms[0].answer, d.rooms[1].answer
    keys = _K((poem_tape + ' ' + map_tape).replace(' ', ''))
    result, spent = _drive_spent(d, keys, monkeypatch)
    assert result['won'] and result['stars'] == 2, (result, spent)
    assert spent == _HE_PAR
    assert d.current_room == 1


def test_all_manual_road_wins_one_star(monkeypatch):
    d = build_dungeon_hall_of_echoes(0)
    poem_tape, map_tape = d.rooms[0].answer, d.rooms[1].answer
    keys = _K(_expand(poem_tape) + _expand(map_tape))
    result, spent = _drive_spent(d, keys, monkeypatch, budget=_HE_BUDGET)
    assert result['won'] and result['stars'] == 1
    assert _HE_PAR < spent <= _HE_BUDGET


def test_poem_hall_south_seal_advances_to_the_map(monkeypatch):
    d = build_dungeon_hall_of_echoes(0)
    poem = d.rooms[0]
    _drive(d, _K('qadawjq9@a'), monkeypatch, finish=':q!\r')
    er, ec = poem.exit_pos
    assert poem.cells[er][ec] == CellType.FLOOR
    assert d.current_room == 0
    d2 = build_dungeon_hall_of_echoes(0)
    _drive(d2, _K('qadawjq9@aj'), monkeypatch, finish=':q!\r')
    assert d2.current_room == 1


def test_first_chamber_grinds_its_band_gate(monkeypatch):
    """Solving the Echo Vault chamber alone opens the FIRST band's west gate
    (sight floods to the next chamber); the exit stays sealed."""
    d = build_dungeon_hall_of_echoes(0)
    poem_tape, map_tape = d.rooms[0].answer, d.rooms[1].answer
    ev_seg = map_tape.split('0 5j')[0]            # up to the end of the EV chamber
    keys = _K((poem_tape + 'j' + ev_seg).replace(' ', ''))
    _drive_spent(d, keys, monkeypatch)
    gmap = d.rooms[1]
    chambers = _he_build_chambers(random.Random(0))
    band = 2 + len(chambers[0]['rows'])           # row under the EV run
    assert gmap.cells[band][_HE_GATE_COL] == CellType.FLOOR
    ge, gc = gmap.exit_pos
    assert gmap.cells[ge][gc] == CellType.WALL


def test_no_jump_lands_on_the_sealed_exit(monkeypatch):
    d = build_dungeon_hall_of_echoes(0)
    seen = {}
    orig = main._calc_stars

    def spy(won, budget, room_, player, level=''):
        seen['pos'] = (player.row, player.col)
        return orig(won, budget, room_, player, level)

    monkeypatch.setattr(main, '_calc_stars', spy)
    result = _drive(d, _K('qadawjq9@ajG'), monkeypatch, finish=':wq\r')
    assert not result['won']
    gmap = d.rooms[1]
    assert seen['pos'] != tuple(gmap.exit_pos)


# ── the Vim showmode indicator ────────────────────────────────────────────────

def test_recording_indicator_shows_and_clears(monkeypatch):
    """While a macro records, the statusline appends Vim's `recording @a`
    showmode indicator; it clears the moment the stop-q lands."""
    import contextlib, io
    import render.colors as Cx
    import render.symbols as Sx
    from render.renderer import render_all as _render_all   # the real one (main's may be stubbed)
    from engine.budget import Budget
    from engine.player import Player
    term = Terminal()
    monkeypatch.setattr(Terminal, 'height', property(lambda self: 30))
    Cx.init(term)
    Sx.init(term)
    d = build_dungeon_hall_of_echoes(0)
    pl = Player(row=1, col=3)
    pl.known_commands = set()

    def _out(**kw):
        f = io.StringIO()
        with contextlib.redirect_stdout(f):
            _render_all(term, d, pl, Budget(total=100), '', **kw)
        return f.getvalue()

    assert 'recording @a' in _out(recording='a')
    assert 'recording @' not in _out(recording='')


def test_recording_flows_to_render_while_recording(monkeypatch):
    """Driven: after `qb` the render receives recording='b'; after the stop-q
    it receives ''."""
    seen = []
    real = main.render_all
    monkeypatch.setattr(main, 'render_all',
                        lambda *a, **k: seen.append(k.get('recording')))
    monkeypatch.setattr(main.time, 'sleep', lambda *a, **k: None)
    for anim in ('_fireworks_animation', '_win_animation', '_starfield_victory',
                 '_heart_container_animation', '_unlock_animation',
                 '_void_fall_animation', '_drown_animation', '_sc_twinkle_animation'):
        monkeypatch.setattr(main, anim, lambda *a, **k: None)
    monkeypatch.setattr(Terminal, 'height', property(lambda self: 45))
    d = build_dungeon_hall_of_echoes(0)
    term = Terminal()
    # qb  (start), l (a recorded move), q (stop)
    keys = _K('qblq') + _K(':q!\r')
    it = iter(keys)
    monkeypatch.setattr(term, 'inkey', lambda *a, **k: next(it, Keystroke('')))
    main.run_dungeon(term, 'hall_of_echoes', {}, player_name='Scribe', _dungeon=d)
    assert 'b' in seen, "the indicator was live while recording"
    assert seen[-1] in ('', None), "the indicator cleared after stop-q"


# ── curriculum ────────────────────────────────────────────────────────────────

def test_curriculum_entry():
    from content.levels import _BY_SLUG
    lv = _BY_SLUG['hall_of_echoes']
    assert lv['teaches'] == ['q', '@', 'reg_named']
