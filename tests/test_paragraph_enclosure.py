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

"""The Paragraph Enclosure (ip ap): tall unequal cantos so counted line-cuts
pay their digits, and the Warden's Sigil — six brazier flames on the three
rows that must survive, stacking into ▲ / ▲ ▲ / ▲ ▲ ▲ when exactly the right
paragraphs fall. The win condition is visible: wrong cuts extinguish flames."""
import math

import pytest
from blessed.keyboard import Keystroke
from blessed import Terminal

import main
from engine.world import CellType
from engine.text_object import resolve_text_object
from generation.dungeon_gen import (
    build_dungeon_paragraph_enclosure,
    _PE_ROWS, _PE_COLS, _PE_SPAWN, _PE_P1, _PE_B1, _PE_P2, _PE_GUARD,
    _PE_B2, _PE_GATE, _PE_EXIT, _PE_PAR, _PE_SIGIL, _PE_BRAZIERS,
)
from tests import SEEDS, cached_room


def _room(seed=0):
    return cached_room('build_dungeon_paragraph_enclosure', seed)


def _K(s):
    return [Keystroke(ch) for ch in s]


def _flames(room):
    return [(e.row, e.col) for e in room.entities
            if e.kind == 'brazier' and e.alive]


def _sigil_stands(room):
    fl = _flames(room)
    if len(fl) != 6:
        return False
    r0, c0 = min(fl)
    return set(fl) == {(r0 + dr, c0 + dc) for dr, dc in _PE_SIGIL}


# The canonical tape (== room.answer): dip spares the rest below the first
# canto (its flame pair survives); dap takes the second canto WITH its whole
# trailing blank block (the watch-gap and its echo), pulling the gate row's
# flame trio up under the pair — the sigil stands.
CANON = 'jdipjdap$'

# The leanest old-only rival: two counted line-cuts around the flames. No
# cut may start on the SPAWN row (its lone flame is the sigil's crown), so
# the rival enters the canto first: 11dd takes exactly the first canto,
# 14dd from the second canto's top row takes canto + watch-gap + echo (dd is
# row-based, so the gap's walled west end doesn't stop it the way it stops
# a d{n}j motion). The cantos are UNEQUAL (11 vs 12 rows), so no dot can
# repeat the first cut on the second. Wins, at 1★ (11 > par 9).
RIVAL = 'j11ddj14dd$'


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
    return main.run_dungeon(term, 'paragraph_enclosure', {}, player_name=name,
                            _dungeon=dungeon)


def _drive_spent(keys, monkeypatch, seed=0):
    box = {}
    orig = main._calc_stars
    monkeypatch.setattr(main, '_calc_stars',
                        lambda won, budget, room, player, level='':
                            (box.__setitem__('spent', budget.spent),
                             orig(won, budget, room, player, level))[1])
    result = _drive(build_dungeon_paragraph_enclosure(seed), keys, monkeypatch)
    return result['won'], box.get('spent')


# ── dungeon structure ─────────────────────────────────────────────────────────

@pytest.mark.parametrize("seed", SEEDS)
def test_layout_and_identity(seed):
    room = _room(seed)
    assert (room.rows, room.cols) == (_PE_ROWS, _PE_COLS)
    assert room.spawn_pos == _PE_SPAWN
    assert room.exit_pos == _PE_EXIT
    exit_ent = next(e for e in room.entities if e.kind == 'exit')
    assert (exit_ent.row, exit_ent.col) == _PE_EXIT and exit_ent.edit_immune


@pytest.mark.parametrize("seed", SEEDS)
def test_par_answer_budget(seed):
    room = _room(seed)
    assert room.par == _PE_PAR
    assert room.budget == math.ceil(_PE_PAR * 1.4)
    assert room.answer == 'j dip j dap $'


@pytest.mark.parametrize("seed", SEEDS)
def test_exit_starts_sealed(seed):
    room = _room(seed)
    assert room.cells[_PE_EXIT[0]][_PE_EXIT[1]] == CellType.WALL


@pytest.mark.parametrize("seed", SEEDS)
def test_blank_rows_are_truly_blank(seed):
    # A single stray char run (even one embedded in a wall) on a boundary row
    # would weld the two cantos into ONE paragraph. The sigil's flames are
    # ENTITIES precisely so their rows stay blank.
    room = _room(seed)
    text_rows = {ru.row for ru in room.char_runs}
    for r in (_PE_SPAWN[0], _PE_B1, _PE_GUARD, _PE_B2):
        assert r not in text_rows, f"row {r} must stay blank"
    for lo, hi in (_PE_P1, _PE_P2):
        for r in range(lo, hi + 1):
            assert r in text_rows, f"canto row {r} must carry a verse"
    assert _PE_GATE in text_rows          # the plaque stops dap's blank run


@pytest.mark.parametrize("seed", SEEDS)
def test_the_sigil_flames_ride_the_surviving_rows(seed):
    room = _room(seed)
    assert sorted(_flames(room)) == sorted(_PE_BRAZIERS)
    rows = {r for r, _ in _PE_BRAZIERS}
    assert rows == {_PE_SPAWN[0], _PE_B1, _PE_GATE}
    for e in room.entities:
        if e.kind == 'brazier':
            assert not e.edit_immune      # a wrong cut SUCCEEDS and snuffs it
    assert not _sigil_stands(room)        # scattered at first — rows apart


@pytest.mark.parametrize("seed", SEEDS)
def test_sentinel_ranks(seed):
    room = _room(seed)
    gobs = [e for e in room.entities if e.kind == 'goblin']
    assert all(not g.ai for g in gobs)                    # a standing legion
    by_row = {}
    for g in gobs:
        by_row.setdefault(g.row, []).append(g)
    for lo, hi in (_PE_P1, _PE_P2):
        for r in range(lo, hi + 1):
            assert r in by_row
    assert len(by_row.get(_PE_GUARD, [])) == 4            # the watch-gap
    # The west aisle stays out of attack radius (the canonical route is safe).
    assert all(g.col >= 3 for g in gobs)


@pytest.mark.parametrize("seed", SEEDS)
def test_paragraph_objects_resolve_to_the_cantos(seed):
    room = _room(seed)

    class P:
        pass

    p = P()
    p.row, p.col = _PE_P1[0] + 5, 1                       # mid first canto
    t = resolve_text_object('ip', room, p)
    assert (t.start_row, t.end_row) == _PE_P1
    p.row = _PE_P2[0] + 3                                 # mid second canto
    t = resolve_text_object('ap', room, p)
    assert (t.start_row, t.end_row) == (_PE_P2[0], _PE_B2)  # both trailing blanks


# ── playthroughs ─────────────────────────────────────────────────────────────

@pytest.mark.parametrize("seed", SEEDS)
def test_canonical_run_wins_at_par_and_raises_the_sigil(seed, monkeypatch):
    dungeon = build_dungeon_paragraph_enclosure(seed)
    box = {}
    orig = main._calc_stars
    monkeypatch.setattr(main, '_calc_stars',
                        lambda won, budget, room, player, level='':
                            (box.__setitem__('spent', budget.spent),
                             orig(won, budget, room, player, level))[1])
    result = _drive(dungeon, _K(CANON), monkeypatch)
    assert result['won'] and box['spent'] == _PE_PAR
    assert _sigil_stands(dungeon.rooms[0])


@pytest.mark.parametrize("seed", SEEDS)
def test_counted_cut_rival_wins_at_one_star(seed, monkeypatch):
    room = _room(seed)
    won, spent = _drive_spent(_K(RIVAL), monkeypatch, seed)
    assert won and _PE_PAR < spent <= room.budget


def test_one_cut_through_both_cantos_snuffs_the_pair(monkeypatch):
    # The 25dd question (playtest 2026-07-17): a single counted cut spanning
    # canto–rest–canto fells every goblin — and visibly extinguishes the
    # rest's flame pair, so the sigil (and the seal) can never stand.
    dungeon = build_dungeon_paragraph_enclosure(0)
    result = _drive(dungeon, _K('j25dd$'), monkeypatch)
    assert not result['won']
    room = dungeon.rooms[0]
    assert not any(e.alive for e in room.entities if e.kind == 'goblin')
    assert len(_flames(room)) == 4                        # the pair is dark
    assert not _sigil_stands(room)


def test_a_cut_from_the_spawn_row_snuffs_the_crown(monkeypatch):
    # 12dd from the spawn row would tie the rival by letting the spawn row
    # substitute for the rest — the crown flame on the spawn row forbids it.
    dungeon = build_dungeon_paragraph_enclosure(0)
    result = _drive(dungeon, _K('12ddj14ddj$'), monkeypatch)
    assert not result['won']
    assert len(_flames(dungeon.rooms[0])) == 5            # the crown is dark


def test_no_dot_pair_spans_both_cantos(monkeypatch):
    # 11dd then `.` (the equal-size dot cheese): the cantos are 11 vs 12
    # rows, so the repeated cut falls one row short of the watch-gap.
    dungeon = build_dungeon_paragraph_enclosure(0)
    result = _drive(dungeon, _K('j11ddj.jjj$'), monkeypatch)
    assert not result['won']
    assert any(e.alive for e in dungeon.rooms[0].entities if e.kind == 'goblin')


def test_overeating_the_rest_breaks_the_sigil(monkeypatch):
    # d} from the first canto eats the rest along with the canto — its
    # flame pair dies with the row, and the seal never parts, even with the
    # second canto swept correctly.
    dungeon = build_dungeon_paragraph_enclosure(0)
    result = _drive(dungeon, _K('jd}jdap$'), monkeypatch)
    assert not result['won']
    room = dungeon.rooms[0]
    er, ec = room.exit_pos
    assert room.cells[er][ec] == CellType.WALL
    assert len(_flames(room)) == 4


def test_dip_on_the_second_canto_leaves_the_watch(monkeypatch):
    # dip spares the watch-gap: its goblins stand, so the seal stays shut.
    dungeon = build_dungeon_paragraph_enclosure(0)
    result = _drive(dungeon, _K('jdipjdip$'), monkeypatch)
    assert not result['won']
    room = dungeon.rooms[0]
    assert any(e.alive for e in room.entities if e.kind == 'goblin')


def test_dG_over_deletion_is_not_a_route(monkeypatch):
    # dG from inside the first canto rips everything down to the anchored
    # gate row: goblins all die, but the flames die with their rows.
    dungeon = build_dungeon_paragraph_enclosure(0)
    result = _drive(dungeon, _K('jdG$'), monkeypatch)
    assert not result['won']


def test_undo_relights_the_flames_and_reseals(monkeypatch):
    dungeon = build_dungeon_paragraph_enclosure(0)
    room = dungeon.rooms[0]
    _drive(dungeon, _K('jdipjd}u'), monkeypatch, finish=':q!\r')
    # d} ate the second canto plus the watch-gap AND beyond; undo rebuilt it
    assert len(_flames(room)) == 6
    er, ec = room.exit_pos
    assert room.cells[er][ec] == CellType.WALL
    assert any(e.alive for e in room.entities if e.kind == 'goblin')


def test_goblins_fall_with_their_rows(monkeypatch):
    dungeon = build_dungeon_paragraph_enclosure(0)
    room = dungeon.rooms[0]
    p1_gobs = sum(1 for e in room.entities if e.kind == 'goblin'
                  and _PE_P1[0] <= e.row <= _PE_P1[1])
    n0 = sum(1 for e in room.entities if e.kind == 'goblin' and e.alive)
    _drive(dungeon, _K('jdip'), monkeypatch, finish=':q!\r')
    n1 = sum(1 for e in room.entities if e.kind == 'goblin' and e.alive)
    assert n0 - n1 == p1_gobs                 # exactly the first canto fell
    assert room.rows == _PE_ROWS - (_PE_P1[1] - _PE_P1[0] + 1)


# ── teleport audit ───────────────────────────────────────────────────────────

def test_no_jump_lands_on_the_sealed_exit(monkeypatch):
    dungeon = build_dungeon_paragraph_enclosure(0)
    seen = {}
    orig = main._calc_stars

    def spy(won, budget, room_, player, level=''):
        seen['pos'] = (player.row, player.col)
        return orig(won, budget, room_, player, level)

    monkeypatch.setattr(main, '_calc_stars', spy)
    result = _drive(dungeon, _K('G$'), monkeypatch, finish=':wq\r')
    assert not result['won']
    assert seen['pos'][1] < _PE_EXIT[1], seen             # $ stopped at the seal


@pytest.mark.parametrize("seed", SEEDS)
def test_exit_unreachable_until_the_sigil(seed):
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
    assert _PE_EXIT not in seen
