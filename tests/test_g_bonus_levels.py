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

"""The g-family bonus levels (43–45): The Buried Word (g*/n), The Wet Ink
(gi), The Stamp Run (gp). Bonus framing: par ties with old-tool routes are
accepted by design — the lesson is the idiom."""
import math

import pytest
from blessed.keyboard import Keystroke
from blessed import Terminal

import vimny.game as main
from vimny.engine.world import CellType
from vimny.generation.dungeon_gen import (
    build_dungeon_buried_word, _BW_BAYS, _BW_GATE, _BW_BOLTS, _BW_EXIT,
    _BW_PAR, _BW_STAND, _BW_SPINE,
    build_dungeon_wet_ink, _WI_LEDGE, _WI_PLQ_COL, _WI_SOURCE, _WI_BRAZIERS,
    _WI_GATE, _WI_BOLT, _WI_EXIT, _WI_PAR, _QM_FLAME, _QM_EMBERS,
)
from tests import SEEDS, cached_room, door_targets

ESC = Keystroke('\x1b', name='KEY_ESCAPE')


def _K(s):
    return [Keystroke(ch) for ch in s]


def _drive(dungeon, slug, keys, monkeypatch, finish=':wq\r'):
    keys = list(keys) + _K(finish)
    monkeypatch.setattr(main, 'render_all', lambda *a, **k: None)
    monkeypatch.setattr(main.time, 'sleep', lambda *a, **k: None)
    for anim in ('_fireworks_animation', '_win_animation', '_starfield_victory',
                 '_heart_container_animation', '_unlock_animation',
                 '_void_fall_animation', '_drown_animation'):
        monkeypatch.setattr(main, anim, lambda *a, **k: None)
    monkeypatch.setattr(Terminal, 'height', property(lambda self: 41))
    term = Terminal()
    it = iter(keys)
    monkeypatch.setattr(term, 'inkey', lambda *a, **k: next(it, Keystroke('')))
    return main.run_dungeon(term, slug, {}, player_name='Scribe',
                            _dungeon=dungeon)


def _spent(dungeon, slug, keys, monkeypatch):
    box = {}
    orig = main._calc_stars
    monkeypatch.setattr(main, '_calc_stars',
                        lambda won, budget, room, player, level='':
                            (box.__setitem__('spent', budget.spent),
                             orig(won, budget, room, player, level))[1])
    result = _drive(dungeon, slug, keys, monkeypatch)
    return result['won'], box.get('spent')


# ── The Buried Word (g* / n) ─────────────────────────────────────────────────

@pytest.mark.parametrize("seed", SEEDS)
def test_bw_structure(seed):
    """The verse (playtest 2026-07-20): the target 'one' stands alone at the
    mouth, then is BURIED in a real word on each STAGGERED line — the buried
    words fall at DIFFERENT columns, so g*/n hunts them (no more single words
    stacked at one column that `j r x` would sweep)."""
    room = cached_room('build_dungeon_buried_word', seed)
    # spawn WEST of 'one' (playtest 2026-07-20): the player walks onto it so
    # the word reads clear at the mouth instead of hiding under the cursor
    assert room.spawn_pos == (_BW_STAND[0], _BW_SPINE)
    assert room.spawn_pos != _BW_STAND
    w = room._bw_words['word']                       # 'one'
    stand = next(ru for ru in room.char_runs if ru.row == _BW_STAND[0]
                 and ru.col == _BW_STAND[1])
    assert ''.join(stand.symbols) == w
    host_cols = []
    for i, r in enumerate(_BW_BAYS):
        host = room._bw_words['hosts'][i]            # e.g. 'alone'
        run = next(ru for ru in room.char_runs
                   if ru.row == r and ru.kind == 'ember')
        text = ''.join(run.symbols)                  # the corrupt host, e.g. 'thxone,'
        core = text.rstrip('.,;:')                   # drop trailing verse punctuation
        assert w in core and core.count(w) == 1      # g* finds the buried word once
        assert len(core) == len(host)                # one substituted cell
        assert sum(a != b for a, b in zip(core, host)) == 1
        idx = host.index(w)
        assert core[idx:] == host[idx:] and core[idx - 1] != host[idx - 1]  # before it
        host_cols.append(run.col + idx)              # the buried word's column
    # the STAGGER: no two buried words share a column (else j/manual nav cheats)
    assert len(set(host_cols)) == len(host_cols)
    # the buried word never stands alone below the ledge (whole-word * finds none)
    for r in _BW_BAYS:
        for ru in room.char_runs:
            if ru.row == r:
                assert ''.join(ru.symbols).rstrip('.,;:') != w


@pytest.mark.parametrize("seed", SEEDS)
def test_bw_hosts_are_real_words(seed):
    # The verse's hosts are real English words that bury the target (hand-
    # picked for the rhyme, so not gated on the game's vocab table).
    room = cached_room('build_dungeon_buried_word', seed)
    w = room._bw_words['word']
    for host in room._bw_words['hosts']:
        assert host.isalpha() and len(host) >= 4
        assert w in host and host != w and host.index(w) >= 1


@pytest.mark.parametrize("seed", SEEDS)
def test_bw_no_plaque_and_door_reads_the_true_word(seed):
    # NO plaque: the mend is named by the VERSE's sense (the rhyme), and the
    # door demands the exact true host — a wrong-but-real word won't open it.
    room = cached_room('build_dungeon_buried_word', seed)
    assert not any(ru.col < _BW_STAND[1] and ru.row in _BW_BAYS
                   for ru in room.char_runs)
    for i, _r in enumerate(_BW_BAYS):
        host = room._bw_words['hosts'][i]
        target, = door_targets(room)[i]
        assert target == host


def _bw_canon(room):
    f = room._bw_words['fixes']
    walk = _BW_STAND[1] - _BW_SPINE                  # {n}l onto 'one' from spawn
    return f'{walk}lg*hr{f[0]}lnhr{f[1]}lnhr{f[2]}G$'


@pytest.mark.parametrize("seed", SEEDS)
def test_bw_canonical_wins_at_par(seed, monkeypatch):
    d = build_dungeon_buried_word(seed)
    won, spent = _spent(d, 'buried_word', _K(_bw_canon(d.rooms[0])), monkeypatch)
    assert won and spent == _BW_PAR


@pytest.mark.parametrize("seed", SEEDS)
def test_bw_typed_search_rival_wins_at_one_star(seed, monkeypatch):
    d = build_dungeon_buried_word(seed)
    f = d.rooms[0]._bw_words['fixes']
    w = d.rooms[0]._bw_words['word']
    walk = _BW_STAND[1] - _BW_SPINE
    # walk onto 'one' (same as the g* route), then /word finds the same buried
    # copies — but the typed search costs word-length+1 where g* is two flat.
    keys = _K(f'{walk}l/{w}\rhr{f[0]}lnhr{f[1]}lnhr{f[2]}G$')
    won, spent = _spent(d, 'buried_word', keys, monkeypatch)
    assert won and _BW_PAR < spent <= d.rooms[0].budget


def test_bw_star_finds_nothing(monkeypatch):
    # * is whole-word since the g-family shipped: no echo stands alone,
    # so * leaves the cursor on the standing word.
    d = build_dungeon_buried_word(0)
    seen = {}
    orig = main._enemy_tick

    def spy(room_, player):
        seen['pos'] = (player.row, player.col)
        return orig(room_, player)

    monkeypatch.setattr(main, '_enemy_tick', spy)
    _drive(d, 'buried_word', _K('*'), monkeypatch, finish=':q!\r')
    assert seen['pos'][0] == _BW_STAND[0]     # never left the ledge row


# ── The Wet Ink (gi) ─────────────────────────────────────────────────────────

def _wi_canon_keys(ws):
    """The canonical tape: write a quarter, carry fire (w hops the ember
    words, P lights in place), gi back — ×3. Typed spaces join the quarters
    (the tape marks them <Space>). The descent is `M`, not `2+`: the gallery is
    the middle of this room's five standable rows, so one key lands where two
    did."""
    return (_K('i') + _K(ws[0]) + [ESC] + _K('MylwP')
            + _K('gi ') + _K(ws[1]) + [ESC] + _K('M2wP')
            + _K('gi ') + _K(ws[2]) + [ESC] + _K('M3wP')
            + _K('gi ') + _K(ws[3]) + [ESC] + _K('G$'))


@pytest.mark.parametrize("seed", SEEDS)
def test_wi_structure(seed):
    room = cached_room('build_dungeon_wet_ink', seed)
    ws = room._wi_words
    full = ' '.join(ws)
    from vimny.generation.dungeon_gen import _WI_PHRASES
    assert ws in _WI_PHRASES and len(ws) == 4
    assert sum(len(w) for w in ws) == 14, "pool-invariant typed cost"
    assert door_targets(room)[0] == (full,)
    # the whole inscription is laid at build, in the west WALL, one run
    # per quarter with a gap column for the space
    for k, w in enumerate(ws):
        plq = next(ru for ru in room.char_runs
                   if ru.row == _WI_LEDGE and ru.col == _WI_PLQ_COL + 5 * k)
        assert ''.join(plq.symbols) == w
    # quarter 1 legible, quarters 2-4 VEILED (the firelight law). Veiled and not
    # fogged: this is carved into WALL, and fog is about cells you could stand
    # in — see `Room.veiled_cells`.
    for i in range(4):
        assert (_WI_LEDGE, _WI_PLQ_COL + i) not in room.veiled_cells
    for k in (1, 2, 3):
        for i in range(4):
            assert (_WI_LEDGE, _WI_PLQ_COL + 5 * k + i) in room.veiled_cells
    # one standing flame, embers on every cold brazier
    src = room.char_run_at(*_WI_SOURCE)
    assert src is not None and src.symbols == (_QM_FLAME,)
    for rc in _WI_BRAZIERS:
        ru = room.char_run_at(*rc)
        assert ru is not None and ru.symbols == (_QM_EMBERS,)
    # the fuel gate starts source-only
    assert room._qm_chain == (_WI_SOURCE,)


@pytest.mark.parametrize("seed", SEEDS)
def test_wi_canonical_wins_at_par(seed, monkeypatch):
    d = build_dungeon_wet_ink(seed)
    keys = _wi_canon_keys(d.rooms[0]._wi_words)
    won, spent = _spent(d, 'wet_ink', keys, monkeypatch)
    assert won and spent == _WI_PAR


@pytest.mark.parametrize("seed", SEEDS)
def test_wi_walk_back_rival_wins(seed, monkeypatch):
    # No gi: climb back (2-) and append at the seam (g_a) — costs more per rep.
    d = build_dungeon_wet_ink(seed)
    ws = d.rooms[0]._wi_words
    # The rival gets M for the descent too — a rival golfed worse than the
    # canonical route proves nothing about gi.
    keys = (_K('i') + _K(ws[0]) + [ESC] + _K('MylwP')
            + _K('2-g_a ') + _K(ws[1]) + [ESC] + _K('M2wP')
            + _K('2-g_a ') + _K(ws[2]) + [ESC] + _K('M3wP')
            + _K('2-g_a ') + _K(ws[3]) + [ESC] + _K('G$'))
    won, spent = _spent(d, 'wet_ink', keys, monkeypatch)
    assert won and _WI_PAR < spent <= d.rooms[0].budget


@pytest.mark.parametrize("seed", SEEDS)
def test_wi_cold_brazier_refuses_ahead_of_the_ink(seed, monkeypatch):
    # Light brazier 2 before quarter 2 is written: the paste is a free
    # no-op — the brazier stays embers and quarter 3 stays dark.
    d = build_dungeon_wet_ink(seed)
    ws = d.rooms[0]._wi_words
    keys = _K('i') + _K(ws[0]) + [ESC] + _K('2+yl2wP')
    _drive(d, 'wet_ink', keys, monkeypatch, finish=':q!\r')
    room = d.rooms[0]
    b2 = room.char_run_at(*_WI_BRAZIERS[1])
    assert b2 is not None and b2.symbols == (_QM_EMBERS,)
    # VEILED, not fogged: the plaque is carved into WALL, which the fog law has
    # nothing to say about — see `Room.veiled_cells`.
    assert room._wi_seg_fog[1] <= room.veiled_cells


@pytest.mark.parametrize("seed", SEEDS)
def test_wi_firelight_reveals_one_quarter(seed, monkeypatch):
    # Light brazier 1 legitimately: quarter 2 wakes, quarters 3-4 stay dark.
    d = build_dungeon_wet_ink(seed)
    ws = d.rooms[0]._wi_words
    keys = _K('i') + _K(ws[0]) + [ESC] + _K('2+ylwP')
    _drive(d, 'wet_ink', keys, monkeypatch, finish=':q!\r')
    room = d.rooms[0]
    b1 = room.char_run_at(*_WI_BRAZIERS[0])
    assert b1 is not None and b1.symbols == (_QM_FLAME,)
    assert not (room._wi_seg_fog[0] & room.veiled_cells)
    assert room._wi_seg_fog[1] <= room.veiled_cells
    assert room._wi_seg_fog[2] <= room.veiled_cells
    assert not room.fog_cells, 'the ledge is lit; nothing here is FOG'


# ── shared audits ────────────────────────────────────────────────────────────

@pytest.mark.parametrize("builder,gate,exit_pos", [
    ('build_dungeon_buried_word', _BW_GATE, _BW_EXIT),
    ('build_dungeon_wet_ink', _WI_GATE, _WI_EXIT),
])
def test_exits_start_sealed_and_unreachable(builder, gate, exit_pos):
    from collections import deque
    room = cached_room(builder, 0)
    assert room.cells[exit_pos[0]][exit_pos[1]] == CellType.WALL
    seen, dq = {room.spawn_pos}, deque([room.spawn_pos])
    while dq:
        r, c = dq.popleft()
        for dr, dc in ((0, 1), (0, -1), (1, 0), (-1, 0)):
            nr, nc = r + dr, c + dc
            if (nr, nc) not in seen and 0 <= nr < room.rows and 0 <= nc < room.cols \
                    and room.is_passable(nr, nc):
                seen.add((nr, nc))
                dq.append((nr, nc))
    assert exit_pos not in seen
