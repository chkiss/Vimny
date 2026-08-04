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

"""The Warden Eternal (final boss): six-warden descent + the Unmasking. NOT
par-forced (par=None, win = survival). The macro-forced horde and the wizard
reveal are the culmination. Tests the tick machinery directly — the chambers
open on clearing, the reveal fires, the seal parts only when the Warden and his
whole horde are dead, and the exit stays walled/unreachable while sealed."""
from collections import deque

import pytest
from blessed import Terminal
from blessed.keyboard import Keystroke

import main
import vimny.generation.dungeon_gen as dg
from vimny.engine.world import CellType
from vimny.engine.player import Player
from tests import SEEDS


def _room(seed):
    return dg.build_dungeon_warden_eternal(seed).rooms[0]


def _bfs_reaches(room, start, goal):
    seen = {start}
    q = deque([start])
    while q:
        r, c = q.popleft()
        if (r, c) == goal:
            return True
        for dr, dc in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nr, nc = r + dr, c + dc
            if (0 <= nr < room.rows and 0 <= nc < room.cols
                    and (nr, nc) not in seen
                    and room.cells[nr][nc] != CellType.WALL):
                seen.add((nr, nc))
                q.append((nr, nc))
    return False


# ── structure ────────────────────────────────────────────────────────────────
@pytest.mark.parametrize('seed', SEEDS)
def test_structure(seed):
    r = _room(seed)
    assert (r.rows, r.cols) == (dg._WDE_ROWS, dg._WDE_COLS)
    assert r.par is None                       # NOT par-forced
    assert r.budget == dg._WDE_BUDGET
    assert len(r._wde_gates) == len(dg._WDE_CHAMBERS) == 6
    assert r.search_glyph_entities is True      # /g finds goblins, /W the Warden
    boss = [e for e in r.entities if e.tag == 'eternal_boss']
    assert len(boss) == 1 and boss[0].kind == 'warden' and boss[0].edit_immune
    # the boss and the chamber wardens are edit-immune (their shield is a
    # dynamic flash on a parried remote cut, not a static entity)
    immune_wardens = [e for e in r.entities if e.kind == 'warden' and e.edit_immune]
    assert len(immune_wardens) >= 1
    assert not any(e.kind == 'shield' for e in r.entities)   # no static shields here
    # a MOBILE swarm (macro answer) + a STATIONARY rank on the boss row (line-cut)
    swarm = [e for e in r.entities if e.tag == 'horde']
    rank  = [e for e in r.entities if e.tag == 'rank']
    assert len(swarm) >= 12
    assert len(rank) >= 8 and all(e.row == boss[0].row and e.ai == '' for e in rank)


@pytest.mark.parametrize('seed', SEEDS)
def test_no_useless_keys_or_treasure_in_the_final_map(seed):
    # The keys-open-nothing note: no locked doors, no key-bearing chests here —
    # gates open on clearing, the seal on the kill. (The one chest is the
    # epilogue scroll in the exit pocket.)
    r = _room(seed)
    assert not any(e.kind == 'locked_door' for e in r.entities)
    chests = [e for e in r.entities if e.kind in ('chest_random', 'chest_key', 'chest_scroll')]
    assert len(chests) == 1 and chests[0].scroll_id == 'wardens_rest'


@pytest.mark.parametrize('seed', SEEDS)
def test_every_chamber_starts_sealed(seed):
    r = _room(seed)
    for g in r._wde_gates:
        assert r.cells[g['band']][g['col']] == CellType.WALL


# ── the descent: a chamber opens only when its foes are cleared ───────────────
@pytest.mark.parametrize('seed', SEEDS)
def test_chamber_opens_on_clear(seed):
    r = _room(seed)
    p = Player(row=r.spawn_pos[0], col=r.spawn_pos[1])
    g = r._wde_gates[0]
    top, bot = g['rows']
    # still-alive foes: tick keeps it shut
    main._warden_eternal_tick(r, p)
    assert r.cells[g['band']][g['col']] == CellType.WALL
    # clear the chamber
    for e in r.entities:
        if e.tag == 'eternal' and top <= e.row <= bot:
            e.hp, e.alive = 0, False
    main._warden_eternal_tick(r, p)
    assert r.cells[g['band']][g['col']] == CellType.FLOOR


# ── the Unmasking ─────────────────────────────────────────────────────────────
@pytest.mark.parametrize('seed', SEEDS)
def test_reveal_fires_in_the_finale(seed):
    r = _room(seed)
    p = Player(row=r.spawn_pos[0], col=r.spawn_pos[1])
    main._warden_eternal_tick(r, p)
    assert r._wde_revealed is False
    p.row = dg._WDE_FINALE_TOP
    msgs = main._warden_eternal_tick(r, p)
    assert r._wde_revealed is True
    assert any('Warden' in m for m in msgs)


# ── the seal parts only when the Warden AND the horde are dead ────────────────
@pytest.mark.parametrize('seed', SEEDS)
def test_seal_needs_boss_and_whole_horde(seed):
    r = _room(seed)
    p = Player(row=dg._WDE_FINALE_TOP, col=1)
    seal = r._wde_seal
    # kill the boss but leave the horde: seal stays shut
    for e in r.entities:
        if e.tag == 'eternal_boss':
            e.hp, e.alive = 0, False
    main._warden_eternal_tick(r, p)
    assert r.cells[seal['rows'][0]][seal['col']] == CellType.WALL
    assert p.has_hat is False
    # clear every goblin too: the seal parts and the Warden LEAVES HIS HAT
    for e in r.entities:
        if e.kind == 'goblin':
            e.hp, e.alive = 0, False
    main._warden_eternal_tick(r, p)
    assert all(r.cells[row][seal['col']] == CellType.FLOOR for row in seal['rows'])
    hat = [e for e in r.entities if e.kind == 'hat']
    assert len(hat) == 1                       # dropped, not yet worn
    assert p.has_hat is False


@pytest.mark.parametrize('seed', SEEDS)
def test_hat_drops_and_is_not_auto_collected(seed):
    # The Warden leaves his hat where he falls; it must be LOOTED with x (or dl),
    # never picked up by merely walking onto it.
    r = _room(seed)
    p = Player(row=dg._WDE_FINALE_TOP, col=1)
    for e in r.entities:                       # win the fight
        if e.kind in ('warden', 'goblin'):
            e.hp, e.alive = 0, False
    main._warden_eternal_tick(r, p)            # seal parts, hat drops
    hat = next(e for e in r.entities if e.kind == 'hat')
    p.row, p.col = hat.row, hat.col            # stand on it
    main._warden_eternal_tick(r, p)
    assert p.has_hat is False                  # walking does NOT collect it
    assert hat.alive                           # still there, awaiting x


def test_line_cut_shears_the_rank_and_flashes_the_ward(monkeypatch):
    """Drive it: with the swarm/chambers pre-cleared, walk to the boss row and
    d$ — the stationary rank dies in one charwise cut, the edit-immune Warden
    survives, and his shield flashes on his cell that frame."""
    d = dg.build_dungeon_warden_eternal(0)
    r = d.rooms[0]
    boss = next(e for e in r.entities if e.tag == 'eternal_boss')
    for e in r.entities:                       # leave only the rank + the boss
        if e.tag in ('eternal', 'horde'):
            e.hp, e.alive = 0, False
    flashes = []

    def _cap(term, dungeon, player, budget, message='', *a, **k):
        if getattr(r, '_ward_flash', None):
            flashes.append(set(r._ward_flash))

    monkeypatch.setattr(main, 'render_all', _cap)
    monkeypatch.setattr(main.time, 'sleep', lambda *a, **k: None)
    monkeypatch.setattr(main.SM, 'save_progress', lambda *a, **k: None)
    monkeypatch.setattr(Terminal, 'height', property(lambda self: 41))
    script = [Keystroke('j')] * (boss.row - r.spawn_pos[0])   # down to the boss row
    script += [Keystroke('0'), Keystroke('d'), Keystroke('$')]
    script += [Keystroke(c) for c in ':q!\r']
    term = Terminal()
    it = iter(script)
    monkeypatch.setattr(term, 'inkey', lambda *a, **k: next(it, Keystroke('')))
    main.run_dungeon(term, 'warden_eternal', {}, player_name='Hero', _dungeon=d)
    assert not any(e.alive for e in r.entities if e.tag == 'rank')   # rank sheared
    assert boss.alive                                               # ward held
    assert any((boss.row, boss.col) in f for f in flashes)          # shield flashed


@pytest.mark.parametrize('seed', SEEDS)
def test_rank_is_line_cuttable_while_the_shielded_boss_is_not(seed):
    # The line-deletion invariant: the stationary rank on the boss row is NOT
    # edit-immune (a charwise d$/D kills it), while the boss on that same row IS
    # edit-immune (his shield turns the blade) — so one line-cut shears the
    # minions and leaves the Warden for the blade. No collapse: charwise, not dd.
    r = _room(seed)
    boss = next(e for e in r.entities if e.tag == 'eternal_boss')
    rank = [e for e in r.entities if e.tag == 'rank']
    assert rank and all(e.row == boss.row and not e.edit_immune for e in rank)
    assert boss.edit_immune                      # the shield survives the sweep


# ── teleport / walking audit: the exit is unreachable while sealed ────────────
@pytest.mark.parametrize('seed', SEEDS)
def test_exit_unreachable_while_sealed(seed):
    r = _room(seed)
    assert not _bfs_reaches(r, r.spawn_pos, r.exit_pos)
    # no row's first non-blank standable column is the exit column — so no
    # G/gg/H/M/L teleport lands on the exit while the seal is shut.
    exit_c = r.exit_pos[1]
    for row in range(r.rows):
        first = next((c for c in range(r.cols)
                      if r.cells[row][c] != CellType.WALL), None)
        assert first != exit_c    # every jump lands west of the sealed pocket


# ── end-to-end: the whole descent through the real run_dungeon loop ───────────
def test_full_descent_wins_and_grants_the_hat(monkeypatch):
    """Drive the FULL loop with every foe pre-cleared, so the live tick chain
    (gates open → the Unmasking → the seal parts → win) runs end-to-end and the
    hat is granted and persisted. Combat itself is shipped machinery, exercised
    elsewhere; this pins the boss's own state machine through run_dungeon."""
    d = dg.build_dungeon_warden_eternal(0)
    r = d.rooms[0]
    for e in r.entities:                       # the victory lap, foes already down
        if e.kind in ('warden', 'goblin'):
            e.hp, e.alive = 0, False
    for anim in ('_fireworks_animation', '_win_animation', '_starfield_victory',
                 '_heart_container_animation', '_unlock_animation'):
        monkeypatch.setattr(main, anim, lambda *a, **k: None)
    monkeypatch.setattr(main, 'render_all', lambda *a, **k: None)
    monkeypatch.setattr(main.time, 'sleep', lambda *a, **k: None)
    monkeypatch.setattr(Terminal, 'height', property(lambda self: 41))
    # walk down the spine, east to the dropped hat, x it, then on to the exit
    hat_row, hat_col = r._wde_hat_drop
    script  = [Keystroke('j')] * (hat_row - r.spawn_pos[0])
    script += [Keystroke('l')] * (hat_col - r.spawn_pos[1])
    script += [Keystroke('x')]                                    # loot the hat
    script += [Keystroke('l')] * (dg._WDE_EXIT[1] - hat_col)
    script += [Keystroke(c) for c in ':wq\r']
    term = Terminal()
    it = iter(script)
    monkeypatch.setattr(term, 'inkey', lambda *a, **k: next(it, Keystroke('')))
    progress = {}
    res = main.run_dungeon(term, 'warden_eternal', progress, player_name='Hero',
                           _dungeon=d)
    assert res['won'] is True
    assert progress.get('has_hat') is True     # the hat, persisted on the win-save
    assert r._wde_revealed is True             # the Unmasking fired
