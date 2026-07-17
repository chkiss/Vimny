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

import main
from engine.world import CellType
from generation.dungeon_gen import (
    build_dungeon_buried_word, _BW_BAYS, _BW_GATE, _BW_BOLTS, _BW_EXIT,
    _BW_PAR, _BW_STAND,
    build_dungeon_wet_ink, _WI_LEDGE, _WI_ALCOVE, _WI_BEND, _WI_GATE,
    _WI_BOLT, _WI_EXIT, _WI_PAR,
)
from tests import SEEDS, cached_room

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
    room = cached_room('build_dungeon_buried_word', seed)
    assert room.spawn_pos == _BW_STAND
    w = room._bw_words['word']
    stand = next(ru for ru in room.char_runs if ru.row == _BW_STAND[0]
                 and ru.col == _BW_STAND[1])
    assert ''.join(stand.symbols) == w
    for i, r in enumerate(_BW_BAYS):
        # a REAL word buries the target; ONE letter (the cell before it) is
        # corrupt, but the target itself is intact so g* finds it.
        run = next(ru for ru in room.char_runs
                   if ru.row == r and ru.kind == 'ember')
        text = ''.join(run.symbols)
        host = room._bw_words['hosts'][i]
        corr = room._bw_words['corrupts'][i]
        assert text == corr and corr != host        # the corrupt spelling laid
        assert len(corr) == len(host)               # one substituted letter
        assert sum(a != b for a, b in zip(corr, host)) == 1
        assert text.count(w) == 1 and w in text     # g* will find it (once)
        idx = host.index(w)
        assert corr[idx:] == host[idx:] and corr[idx - 1] != host[idx - 1]  # before it
    # the buried word never stands alone below the ledge (whole-word *
    # would find nothing)
    for r in _BW_BAYS:
        for ru in room.char_runs:
            if ru.row == r:
                assert ''.join(ru.symbols) != w


@pytest.mark.parametrize("seed", SEEDS)
def test_bw_hosts_are_real_words(seed):
    import generation.dungeon_gen as dg
    dg._load_vocab_tables()
    real = set(x for L in range(4, 8)
               for x in dg._VOCAB_PLAIN_BY_LEN.get(L, ()))
    room = cached_room('build_dungeon_buried_word', seed)
    for host in room._bw_words['hosts']:
        assert host in real                          # actual words, not nonsense


@pytest.mark.parametrize("seed", SEEDS)
def test_bw_plaque_shows_the_true_host(seed):
    room = cached_room('build_dungeon_buried_word', seed)
    for i, r in enumerate(_BW_BAYS):
        host = room._bw_words['hosts'][i]
        plq = next(ru for ru in room.char_runs
                   if ru.row == r and ru.col == 2)     # _BW_PLQ_COL
        assert ''.join(plq.symbols) == host           # matches the door target
        target, _ = room._wla_doors[i]
        assert target == host


def _bw_canon(room):
    f = room._bw_words['fixes']
    return f'g*hr{f[0]}lnhr{f[1]}lnhr{f[2]}G$'


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
    # /word finds the same buried copies (literal), but the typed search
    # costs word-length+1 up front where g* is two flat — the same r mends.
    keys = _K(f'/{w}\rhr{f[0]}lnhr{f[1]}lnhr{f[2]}G$')
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

@pytest.mark.parametrize("seed", SEEDS)
def test_wi_structure(seed):
    room = cached_room('build_dungeon_wet_ink', seed)
    w1, w2 = room._wi_words
    assert room._ss_doors[0][0] == (w1 + w2,)
    # plaque 2 is stone-hidden until the bend is walked (the fog law)
    p2 = next(ru for ru in room.char_runs
              if ru.row == _WI_ALCOVE + 1)
    assert ''.join(p2.symbols) == w2
    assert any((r, c) in room.fog_cells
               for r in (_WI_ALCOVE,) for c in range(_WI_BEND, _WI_BEND + 6))


@pytest.mark.parametrize("seed", SEEDS)
def test_wi_canonical_wins_at_par(seed, monkeypatch):
    d = build_dungeon_wet_ink(seed)
    w1, w2 = d.rooms[0]._wi_words
    keys = (_K('i') + _K(w1) + [ESC] + _K('$2j')
            + _K('gi') + _K(w2) + [ESC] + _K('G$'))
    won, spent = _spent(d, 'wet_ink', keys, monkeypatch)
    assert won and spent == _WI_PAR


@pytest.mark.parametrize("seed", SEEDS)
def test_wi_walk_back_rival_wins(seed, monkeypatch):
    # No gi: climb back and append at the seam — a and the walk cost more.
    d = build_dungeon_wet_ink(seed)
    w1, w2 = d.rooms[0]._wi_words
    keys = (_K('i') + _K(w1) + [ESC] + _K('$2j')
            + _K('2kg_a') + _K(w2) + [ESC] + _K('G$'))
    won, spent = _spent(d, 'wet_ink', keys, monkeypatch)
    assert won and spent > _WI_PAR


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
