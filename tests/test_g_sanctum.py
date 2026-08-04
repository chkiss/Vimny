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

"""The G-Sanctum (the g-family): three verses running east into water —
$ overshoots onto the flood and drowns; g_ lands the last glyph (water
carries no characters); counted e-walks pay two digits."""
import math

import pytest
from blessed.keyboard import Keystroke
from blessed import Terminal

import main
from vimny.engine.world import CellType
from vimny.generation.dungeon_gen import (
    build_dungeon_g_sanctum,
    _GS_ROWS, _GS_COLS, _GS_SPINE, _GS_BAYS, _GS_NWORDS, _GS_POOL,
    _GS_GATE, _GS_BOLTS, _GS_EXIT, _GS_PAR, _GS_VERSES,
)
from tests import SEEDS, cached_room


def _room(seed=0):
    return cached_room('build_dungeon_g_sanctum', seed)


def _K(s):
    return [Keystroke(ch) for ch in s]


# The canonical tape (== room.answer): g_ from the spine lands the last
# glyph — the tail word's CORRUPT final letter — and r{fix} mends it;
# + chains the bays. (Per seed: the fix letters are the true spellings.)
def _canon(room):
    f = room._gs_words['fixes']
    steps = f'jg_r{f[0]}' + ''.join(f'+g_r{fx}' for fx in f[1:])
    return steps + 'G'                                   # G lands on the open west seal


# The counted-e rival: the LONG verses are 10+ words, so {n}e pays two count
# digits where g_ pays two flat (par+1 per long row); the short verses only
# tie. Same r{fix} mend. Wins, but over par (1★).
def _rival(room):
    f = room._gs_words['fixes']
    n = _GS_NWORDS
    steps = f'j{n[0]}er{f[0]}' + ''.join(f'+{n[i]}er{f[i]}' for i in range(1, len(f)))
    return steps + 'G0'


def _drive(dungeon, keys, monkeypatch, finish=':wq\r', name='Scribe'):
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
    return main.run_dungeon(term, 'g_sanctum', {}, player_name=name,
                            _dungeon=dungeon)


def _drive_spent(keys, monkeypatch, seed=0):
    box = {}
    orig = main._calc_stars
    monkeypatch.setattr(main, '_calc_stars',
                        lambda won, budget, room, player, level='':
                            (box.__setitem__('spent', budget.spent),
                             orig(won, budget, room, player, level))[1])
    result = _drive(build_dungeon_g_sanctum(seed), keys, monkeypatch)
    return result['won'], box.get('spent')


# ── structure ─────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("seed", SEEDS)
def test_layout_and_identity(seed):
    room = _room(seed)
    assert (room.rows, room.cols) == (_GS_ROWS, _GS_COLS)
    assert room.spawn_pos == (1, _GS_SPINE)
    assert room.exit_pos == _GS_EXIT
    exit_ent = next(e for e in room.entities if e.kind == 'exit')
    assert (exit_ent.row, exit_ent.col) == _GS_EXIT and exit_ent.edit_immune


@pytest.mark.parametrize("seed", SEEDS)
def test_par_answer_budget(seed):
    room = _room(seed)
    assert room.par == _GS_PAR
    assert room.budget == math.ceil(_GS_PAR * 1.4)
    f = room._gs_words['fixes']
    steps = [f'j g_ r{f[0]}'] + [f'+ g_ r{fx}' for fx in f[1:]]
    assert room.answer == ' '.join(steps) + ' G'


@pytest.mark.parametrize("seed", SEEDS)
def test_verses_end_in_a_corrupt_tail_before_the_flood(seed):
    room = _room(seed)
    w = room._gs_words
    for i, r in enumerate(_GS_BAYS):
        runs = sorted((ru for ru in room.char_runs
                       if ru.row == r and _GS_SPINE < ru.col < _GS_POOL[0]),
                      key=lambda ru: ru.col)
        assert len(runs) == _GS_NWORDS[i]
        tail = ''.join(runs[-1].symbols)
        assert tail == w['corrupts'][i]                 # the corrupt spelling laid
        assert tail != w['tails'][i]                    # ≠ the true word (plaque)
        assert tail[:-1] == w['tails'][i][:-1]          # only the last letter is wrong
        for c in _GS_POOL:                    # the drowning pool past the verse
            assert room.cells[r][c] == CellType.WATER


@pytest.mark.parametrize("seed", SEEDS)
def test_no_plaque_and_sayings_known_by_heart(seed):
    # SENSE, NOT DECREE: the verses are famous sayings — no plaque west of
    # the spine; the true tail is not yet true on the floor.
    room = _room(seed)
    w = room._gs_words
    assert not any(ru.col < _GS_SPINE for ru in room.char_runs)
    for i, r in enumerate(_GS_BAYS):
        assert w['tails'][i] not in ''.join(main._wla_floor_text(room, r))
        # the laid verse is the saying with only the tail's last letter wrong
        floor = ' '.join(''.join(ru.symbols)
                         for ru in sorted((ru for ru in room.char_runs
                                           if ru.row == r), key=lambda ru: ru.col))
        want = _GS_VERSES[i][0].rsplit(' ', 1)[0] + ' ' + _GS_VERSES[i][1]
        assert floor == want


def test_word_counts_and_adjacency():
    # The LONG verses are 10+ words (so {n}e pays two count digits where g_ is
    # two flat); adjacent bays always differ in count (long/short alternation),
    # so no count transfers blind to the next verse.
    assert max(_GS_NWORDS) >= 10 and _GS_NWORDS.count(10) + _GS_NWORDS.count(11) >= 3
    assert all(a != b for a, b in zip(_GS_NWORDS, _GS_NWORDS[1:]))


def test_corruptions_are_visible_nonwords():
    # The corrupt spelling differs from the true tail in ONLY the last
    # letter and is itself no word — the wrongness is visible; the SAYING
    # (not a dictionary) names the mend.
    for verse, corr in _GS_VERSES:
        tail = verse.rsplit(' ', 1)[1]
        assert corr[:-1] == tail[:-1] and corr[-1] != tail[-1]
        assert not corr.isalpha() or corr != tail        # a visibly-wrong spelling


@pytest.mark.parametrize("seed", SEEDS)
def test_exit_and_bolts_start_sealed(seed):
    room = _room(seed)
    for dc in _GS_BOLTS.values():
        assert room.cells[_GS_GATE][dc] == CellType.WALL
    assert room.cells[_GS_EXIT[0]][_GS_EXIT[1]] == CellType.WALL


# ── playthroughs ─────────────────────────────────────────────────────────────

@pytest.mark.parametrize("seed", SEEDS)
def test_canonical_g_run_wins_at_par(seed, monkeypatch):
    won, spent = _drive_spent(_K(_canon(_room(seed))), monkeypatch, seed)
    assert won and spent == _GS_PAR


@pytest.mark.parametrize("seed", SEEDS)
def test_counted_e_rival_wins_at_one_star(seed, monkeypatch):
    room = _room(seed)
    won, spent = _drive_spent(_K(_rival(room)), monkeypatch, seed)
    assert won and _GS_PAR < spent <= room.budget


def _tail_cols(room):
    cols = []
    for r in _GS_BAYS:
        run = max((ru for ru in room.char_runs if ru.row == r and ru.kind == 'ancient'),
                  key=lambda ru: ru.col)
        cols.append(run.col + len(run.symbols) - 1)      # the corrupt last glyph
    return cols


@pytest.mark.parametrize("seed", SEEDS)
def test_adjacent_tails_separated_so_no_jh_cheat(seed):
    """Playtest 2026-07-20: adjacent verse tails must sit >= 3 columns apart,
    so `j` then an h/l walk to the next tail costs more than g_ (2 keys). When
    two tails were one column apart (…bush@66 / …boy@65), `j h` cheated g_."""
    cols = _tail_cols(_room(seed))
    for a, b in zip(cols, cols[1:]):
        assert abs(a - b) >= 3, (cols, "adjacent tails too close — j h would cheat g_")


def test_j_walk_rival_cannot_even_finish(monkeypatch):
    """The cheat the playtest found: reach each next tail by `j` (down, same
    column) then an h/l walk, never g_. With the tails now alternating far
    east / near west, the walk between them is ~100 keystrokes — it blows the
    budget entirely and never reaches the exit (g_ is the only affordable
    reach). ADVERSARIAL: the fix, driven."""
    room = _room(0)
    f = room._gs_words['fixes']
    cols = _tail_cols(room)
    keys = f'jg_r{f[0]}'                                  # mend verse 1 (g_ used once to start)
    cur = cols[0]
    walk = 0
    for i in range(1, len(f)):
        dc = cols[i] - cur                               # j lands at `cur`; walk to tail i
        keys += 'j' + ('l' if dc > 0 else 'h') * abs(dc) + 'r' + f[i]
        walk += abs(dc)
        cur = cols[i]
    keys += 'G0'
    assert walk > 80, walk                               # the manual walk is enormous
    won, _spent = _drive_spent(_K(keys), monkeypatch, 0)
    assert not won                                       # can't afford the j-walk at all


def test_adversarial_no_reach_beats_par(monkeypatch):
    """ADVERSARIAL (playtest 2026-07-21): no clever reach — word motions (ge),
    counted walks ({n}h/{n}l), or word-end counts ({n}e) — costs LESS than the
    g_ par. The tightest word-motion route (ge on the short verses, g_ on the
    long) TIES at par; every other alternative overshoots."""
    room = _room(0)
    f = room._gs_words['fixes']
    cols = _tail_cols(room)
    nwords = _GS_NWORDS

    # 1) ge on the short (east-tail) verses, g_ on the long — the tightest rival
    ge = (f'jg_r{f[0]}' + f'jger{f[1]}' + f'+g_r{f[2]}'
          + f'jger{f[3]}' + f'+g_r{f[4]}' + 'G')
    won, spent = _drive_spent(_K(ge), monkeypatch, 0)
    assert won and spent >= _GS_PAR and spent <= room.budget      # ties, never beats

    # 2) counted h/l walk between the alternating tails — overshoots
    walk = f'jg_r{f[0]}'
    cur = cols[0]
    for i in range(1, len(f)):
        dc = cols[i] - cur
        walk += 'j' + f'{abs(dc)}' + ('l' if dc > 0 else 'h') + f'r{f[i]}'
        cur = cols[i]
    walk += 'G'
    won, spent = _drive_spent(_K(walk), monkeypatch, 0)
    assert won and spent > _GS_PAR                                # dearer than g_

    # 3) word-end {n}e count on every verse — overshoots (long verses pay 2 digits)
    we = f'j{nwords[0]}er{f[0]}' + ''.join(f'+{nwords[i]}er{f[i]}'
                                           for i in range(1, len(f))) + 'G'
    won, spent = _drive_spent(_K(we), monkeypatch, 0)
    assert won and spent > _GS_PAR


def test_dollar_drowns_in_the_flood(monkeypatch):
    # The forcing terrain: $ overshoots the text onto the water.
    dungeon = build_dungeon_g_sanctum(0)
    result = _drive(dungeon, _K('j$'), monkeypatch, finish=':q!\r')
    assert not result['won']


def test_g_underscore_lands_the_last_glyph(monkeypatch):
    dungeon = build_dungeon_g_sanctum(0)
    room = dungeon.rooms[0]
    seen = {}
    orig = main._enemy_tick

    def spy(room_, player):
        seen['pos'] = (player.row, player.col)
        return orig(room_, player)

    monkeypatch.setattr(main, '_enemy_tick', spy)
    _drive(dungeon, _K('jg_'), monkeypatch, finish=':q!\r')
    r, c = seen['pos']
    assert r == _GS_BAYS[0]
    run = max((ru for ru in room.char_runs
               if ru.row == r and ru.kind == 'ancient'), key=lambda ru: ru.col)
    assert c == run.col + len(run.symbols) - 1      # the corrupt letter, not the brink


def test_undo_rebars_an_open_bolt(monkeypatch):
    dungeon = build_dungeon_g_sanctum(0)
    room = dungeon.rooms[0]
    _drive(dungeon, _K('jg_xu'), monkeypatch, finish=':q!\r')
    assert room.cells[_GS_GATE][_GS_BOLTS[2]] == CellType.WALL


# ── teleport audit ───────────────────────────────────────────────────────────

def test_no_jump_lands_on_the_sealed_exit(monkeypatch):
    # The exit is the WEST seal at column 0; with the verses unmended it is
    # WALL, and the bolts west of the spine bar the way, so `G 0` (the winning
    # ending) cannot reach it — it clamps east of the shut bolts.
    dungeon = build_dungeon_g_sanctum(0)
    seen = {}
    orig = main._calc_stars

    def spy(won, budget, room_, player, level=''):
        seen['pos'] = (player.row, player.col)
        return orig(won, budget, room_, player, level)

    monkeypatch.setattr(main, '_calc_stars', spy)
    result = _drive(dungeon, _K('G0'), monkeypatch, finish=':wq\r')
    assert not result['won']
    assert seen['pos'] != _GS_EXIT and seen['pos'][1] > _GS_EXIT[1], seen


@pytest.mark.parametrize("seed", SEEDS)
def test_exit_unreachable_until_all_true(seed):
    from collections import deque
    room = _room(seed)
    seen, dq = {room.spawn_pos}, deque([room.spawn_pos])
    while dq:
        r, c = dq.popleft()
        for dr, dc in ((0, 1), (0, -1), (1, 0), (-1, 0)):
            nr, nc = r + dr, c + dc
            if (nr, nc) not in seen and 0 <= nr < room.rows and 0 <= nc < room.cols \
                    and room.is_passable(nr, nc):
                seen.add((nr, nc))
                dq.append((nr, nc))
    assert _GS_EXIT not in seen
