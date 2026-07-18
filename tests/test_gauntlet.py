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

"""The Gauntlet (45) — the everything-exam maze.

One buffer, eighteen doors, one seal. The canonical tape IS room.answer
(rebuilt into keystrokes here — the tape and the tests can never drift);
par is pinned by the driven run and by the par−1 boundary probe. Each
load-bearing forcing has a rival tape that wins at 1★ or fails its door.
"""
from collections import deque

import pytest
from blessed.keyboard import Keystroke
from blessed import Terminal

import main
from engine.world import CellType
from generation.dungeon_gen import (
    build_dungeon_gauntlet,
    _GNT_ROWS, _GNT_COLS, _GNT_SPINE, _GNT_R_E, _GNT_R_BW, _GNT_R_PCT,
    _GNT_R_BLK,
    _GNT_R_BLANK, _GNT_R_P1, _GNT_R_P2, _GNT_R_P3, _GNT_R_CIT, _GNT_R_D,
    _GNT_R_NOOK, _GNT_R_GATE, _GNT_P1_COLS, _GNT_P2_COLS, _GNT_NOOK_COLS,
    _GNT_BOLT0, _GNT_EXIT, _GNT_CATCH, _GNT_PAR, _GNT_BUDGET,
)
from tests import SEEDS, cached_room

ESC = Keystroke('\x1b', code=361, name='KEY_ESCAPE')
ENTER = Keystroke('\r', code=343, name='KEY_ENTER')


def _room(seed=0):
    return cached_room('build_dungeon_gauntlet', seed)


def _K(s):
    out = []
    for ch in s:
        out.append(ENTER if ch == '⏎' else Keystroke(ch))
    return out


# Tokens whose tail is TYPED text needing a closing Esc (insert-mode verbs).
_TYPED = ('cit', 'C', 'S', 'O', 'o')


def _tape_keys(answer):
    """room.answer → keystrokes: spaces are display separators, ⏎ is Enter,
    and every insert-verb token gets its Esc appended."""
    keys = []
    for tok in answer.split(' '):
        keys += _K(tok)
        if tok.startswith(_TYPED) and len(tok) > 1 and tok not in ('C', 'S'):
            keys.append(ESC)
    return keys


def _drive(dungeon, keys, monkeypatch, finish=':wq\r'):
    keys = list(keys) + _K(finish)
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
    return main.run_dungeon(term, 'gauntlet', {}, player_name='Scribe',
                            _dungeon=dungeon)


def _fresh(seed=0):
    return build_dungeon_gauntlet(seed)


def _swap(answer, old, new):
    """Replace one leg of the canonical tape (asserts it was present)."""
    assert f' {old} ' in f' {answer} '
    return f' {answer} '.replace(f' {old} ', f' {new} ', 1).strip()


# ── structure ─────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("seed", SEEDS)
def test_dimensions_doors_and_gate(seed):
    room = _room(seed)
    assert (room.rows, room.cols) == (_GNT_ROWS, _GNT_COLS)
    assert len(room._gnt_doors) == 18
    assert [dc for _, _, dc in room._gnt_doors] == list(range(_GNT_BOLT0,
                                                             _GNT_BOLT0 + 18))
    gr = _GNT_R_GATE
    for _, _, dc in room._gnt_doors:
        assert room.cells[gr][dc] == CellType.WALL          # bolts barred
    assert room.cells[_GNT_EXIT[0]][_GNT_EXIT[1]] == CellType.WALL   # the seal
    assert room.exit_pos == _GNT_EXIT
    assert room.spawn_pos == (_GNT_R_BW, _GNT_SPINE)


@pytest.mark.parametrize("seed", SEEDS)
def test_no_target_is_already_true(seed):
    room = _room(seed)
    floor_rows = [main._wla_floor_text(room, r) for r in range(room.rows)]
    stripped = [t.strip() for t in floor_rows]
    for kind, target, _dc in room._gnt_doors:
        if kind == 'sub':
            assert not any(target in t for t in floor_rows), target
        elif kind == 'row':
            assert target not in stripped, target
        else:
            assert sum(1 for t in stripped if t == target) < 2, target


def _bfs(room, start):
    seen, dq = {start}, deque([start])
    while dq:
        r, c = dq.popleft()
        for dr, dc in ((0, 1), (0, -1), (1, 0), (-1, 0)):
            n = (r + dr, c + dc)
            if (n not in seen and 0 <= n[0] < room.rows and 0 <= n[1] < room.cols
                    and room.is_passable(*n)):
                seen.add(n)
                dq.append(n)
    return seen


@pytest.mark.parametrize("seed", SEEDS)
def test_pockets_and_gate_are_walk_proof(seed):
    # P1/P2/the nook are search-only islands; the gate row lies beyond the
    # r20 wall course, so even the finale needs a jump (G) — walking never
    # reaches a bolt, the seal, or a pocket.
    room = _room(seed)
    seen = _bfs(room, room.spawn_pos)
    assert not any((_GNT_R_P1, c) in seen
                   for c in range(_GNT_P1_COLS[0], _GNT_P1_COLS[1] + 1))
    assert not any((_GNT_R_P2, c) in seen
                   for c in range(_GNT_P2_COLS[0], _GNT_P2_COLS[1] + 1))
    assert not any((_GNT_R_NOOK, c) in seen
                   for c in range(_GNT_NOOK_COLS[0], _GNT_NOOK_COLS[1] + 1))
    assert not any(r == _GNT_R_GATE for (r, c) in seen)


@pytest.mark.parametrize("seed", SEEDS)
def test_M_lands_on_the_cit_row(seed):
    # M targets the middle PASSABLE row — the ladder is built so that is the
    # cit row, and its landing column is the tag's '<' (first non-blank).
    from engine.motion import apply_motion, _first_non_blank_col
    from engine.player import Player
    room = _room(seed)
    p = Player()
    p.row, p.col = _GNT_R_P3, 68
    apply_motion(p, 'M', 1, room)
    assert p.row == _GNT_R_CIT
    assert p.col == _first_non_blank_col(room, _GNT_R_CIT) == 34


@pytest.mark.parametrize("seed", SEEDS)
def test_search_words_are_clean(seed):
    # The chain words appear EXACTLY where designed: S1 ×4 (two block
    # decoys + both pockets), T1 ×3 (block decoy, P2, P3), U1 ×3 (block,
    # y-door, nook) — and never nested inside another token.
    import re
    room = _room(seed)
    text = '\n'.join(main._wla_floor_text(room, r) for r in range(room.rows))
    blk = main._wla_floor_text(room, _GNT_R_BLK).split()
    u1, w7, s1, t1 = blk[0], blk[1], blk[2], blk[3]
    assert blk[4] == s1                                   # the second decoy
    assert len(re.findall(r'\b%s\b' % s1, text)) == 4
    assert len(re.findall(r'\b%s\b' % t1, text)) == 3
    assert len(re.findall(r'\b%s\b' % u1, text)) == 3
    assert len(re.findall(r'\b%s\b' % w7, text)) == 1
    for sw in (s1, t1, u1, w7):                           # never nested
        assert not re.search(r'\w%s|%s\w' % (sw, sw), text)


@pytest.mark.parametrize("seed", SEEDS)
def test_channels_are_misted_water(seed):
    # The waterworks: every pocket channel is WATER under permanent mist —
    # visible (the vision flood crosses water), foot-proof, scan-proof.
    # The islands themselves stay clear: visible and searchable.
    room = _room(seed)
    for r, lo in ((_GNT_R_P1, _GNT_P1_COLS[0]), (_GNT_R_P2, _GNT_P2_COLS[0]),
                  (_GNT_R_NOOK, _GNT_NOOK_COLS[0])):
        for c in range(_GNT_SPINE + 1, lo):
            assert room.cells[r][c] == CellType.WATER
            assert (r, c) in room.fog_cells and (r, c) in room.mist_cells
    for c in range(_GNT_P1_COLS[0], _GNT_P1_COLS[1] + 1):
        assert (_GNT_R_P1, c) not in room.fog_cells
    for c in range(_GNT_P2_COLS[0], _GNT_P2_COLS[1] + 1):
        assert (_GNT_R_P2, c) not in room.fog_cells


@pytest.mark.parametrize("seed", SEEDS)
def test_islands_are_search_only(seed):
    # Water bars feet (the BFS test), the mist bars the line scans, and the
    # spine ◆ catches every fnb jump ({n}G / + / -) — only a search lands
    # on an island; the search itself remains a lawful landing.
    from engine.motion import apply_motion, _first_non_blank_col
    from engine.player import Player
    from engine.search import find_next
    room = _room(seed)
    isl1 = set(range(_GNT_P1_COLS[0], _GNT_P1_COLS[1] + 1))
    for motion in ('$', 'w', 'e', 'W', 'E'):
        p = Player()
        p.row, p.col = _GNT_R_P1, _GNT_SPINE
        apply_motion(p, motion, 1, room)
        assert not (p.row == _GNT_R_P1 and p.col in isl1), motion
    # the fnb of both pocket rows is the spine ◆, not the island text
    for r in (_GNT_R_P1, _GNT_R_P2):
        assert _first_non_blank_col(room, r) == _GNT_SPINE
    # …while the search still crosses the water onto the island
    s1 = main._wla_floor_text(room, _GNT_R_BLK).split()[2]
    p = Player()
    p.row, p.col = room.spawn_pos
    hit = find_next(room, p, s1, True)
    assert hit is not None and hit[0] in (_GNT_R_BLK, _GNT_R_P1, _GNT_R_P2)


@pytest.mark.parametrize("seed", SEEDS)
def test_plaques_read_the_full_targets(seed):
    # The playtest law: every door row's west-wall plaque carries the door's
    # FULL true reading (the y/Y doors show their fill word twice / the
    # doubled line). Wall runs never join the floor scans or a search.
    room = _room(seed)

    def plaque(r):
        return ' '.join(''.join(ru.symbols) for ru in room.char_runs
                        if ru.row == r and ru.kind == 'verdant'
                        and ru.col < _GNT_SPINE)

    targets = [t for _k, t, _dc in room._gnt_doors]
    # doors 0-3 (galleries), 4-5 (pocket cures), 9 (cit), 10-11 (row doors),
    # 12 (C), 13 (S) read VERBATIM on their rows; P3 reads its three raised
    # names as one plaque; the O/o doors (16-17) read their created lines.
    for r, t in ((_GNT_R_E, targets[0]), (_GNT_R_BW, targets[1]),
                 (_GNT_R_PCT, targets[2]), (_GNT_R_P1, targets[4]),
                 (_GNT_R_P2, targets[5]), (_GNT_R_CIT, targets[9]),
                 (_GNT_R_D, targets[10]),
                 (_GNT_R_P3, ' '.join(targets[6:9]))):
        assert plaque(r) == t, (r, t)


# ── the driven canonical ──────────────────────────────────────────────────────

@pytest.mark.parametrize("seed", SEEDS)
def test_canonical_run_wins_at_par(seed, monkeypatch):
    d = _fresh(seed)
    result = _drive(d, _tape_keys(d.rooms[0].answer), monkeypatch)
    assert result['won'] and result['stars'] == 2
    room = d.rooms[0]
    gr = room.exit_pos[0]
    assert all(room.cells[gr][dc] != CellType.WALL
               for _, _, dc in room._gnt_doors)


def test_par_boundary_is_exact(monkeypatch):
    # The canonical spends EXACTLY par: par−1 drops the same tape to 1★.
    d = _fresh(0)
    d.rooms[0].par = _GNT_PAR - 1
    result = _drive(d, _tape_keys(d.rooms[0].answer), monkeypatch)
    assert result['won'] and result['stars'] == 1


def test_budget_is_hand_set(monkeypatch):
    assert _room(0).budget == _GNT_BUDGET


# ── rival tapes: each loses a star or fails its door ──────────────────────────

def test_skipping_M_costs_a_star(monkeypatch):
    # j lands ~34 cols east of the tag; ^ recovers to the '<' — one key more.
    d = _fresh(0)
    a = _swap(d.rooms[0].answer, 'M', 'j ^')
    result = _drive(d, _tape_keys(a), monkeypatch)
    assert result['won'] and result['stars'] == 1


def test_skipping_hash_with_star_costs_a_star(monkeypatch):
    # A wrapping * lands on the nook decoy; n (still forward) wraps on to
    # the block twin — the same place # reaches, one key later. The return
    # flips with the direction: the canonical N becomes n.
    d = _fresh(0)
    a = _swap(d.rooms[0].answer, '#', '* n')
    a = _swap(a, 'N', 'n')
    result = _drive(d, _tape_keys(a), monkeypatch)
    assert result['won'] and result['stars'] == 1


def test_skipping_brace_costs_a_star(monkeypatch):
    # Searching from the sentence row eats both block decoys (n n) — the }
    # that skips past them is exactly one key cheaper.
    d = _fresh(0)
    room = d.rooms[0]
    s1 = main._wla_floor_text(room, _GNT_R_BLK).split()[2]
    a = _swap(room.answer, f'}} /{s1}⏎', f'/{s1}⏎ n n')
    result = _drive(d, _tape_keys(a), monkeypatch)
    assert result['won'] and result['stars'] == 1


def test_s_ties_r_documented(monkeypatch):
    # The Vim-intrinsic tie: s{c}Esc costs what r{c} costs. The exam accepts
    # either — the tape stays canonical with r, and this pin documents why.
    d = _fresh(0)
    room = d.rooms[0]
    rtok = next(t for t in room.answer.split(' ')
                if len(t) == 2 and t[0] == 'r')
    a = _swap(room.answer, rtok, 's' + rtok[1])
    keys = []
    for tok in a.split(' '):
        keys += _K(tok)
        if tok.startswith(_TYPED) and len(tok) > 1 and tok not in ('C', 'S'):
            keys.append(ESC)
        if tok == 's' + rtok[1]:
            keys.append(ESC)                        # s enters insert; Esc is free
    result = _drive(d, keys, monkeypatch)
    assert result['won'] and result['stars'] == 2


def test_longhand_fill_costs_a_star(monkeypatch):
    # The q@ re-audit (macros now precede the exam): the y-door fill is the
    # exam's macro leg — recording is free and @b replays for 2, so the
    # untaped longhand (w e l p ×2 = 8 vs 6) loses exactly the star.
    d = _fresh(0)
    a = _swap(d.rooms[0].answer, 'qb w e l p q @b', 'w e l p w e l p')
    result = _drive(d, _tape_keys(a), monkeypatch)
    assert result['won'] and result['stars'] == 1


def test_jump_cannot_pass_the_sealed_gate(monkeypatch):
    # G lands the threshold ◆; $ stops at the first barred bolt; the seal
    # never opens for position alone.
    d = _fresh(0)
    result = _drive(d, _K('G$'), monkeypatch, finish=':wq\r')
    assert not result['won']
    assert d.current_room == 0


def test_first_door_opens_and_undo_rebars(monkeypatch):
    d = _fresh(0)
    room = d.rooms[0]
    _drive(d, _K('k3ex'), monkeypatch, finish=':q!\r')
    assert room.cells[_GNT_R_GATE][_GNT_BOLT0] != CellType.WALL
    d2 = _fresh(0)
    room2 = d2.rooms[0]
    _drive(d2, _K('k3exu'), monkeypatch, finish=':q!\r')
    assert room2.cells[_GNT_R_GATE][_GNT_BOLT0] == CellType.WALL


# ── curriculum ────────────────────────────────────────────────────────────────

def test_curriculum_entry():
    from content.levels import _BY_SLUG, known_commands
    lv = _BY_SLUG['gauntlet']
    assert lv['display'] == '45'
    assert lv['teaches'] == []                     # an exam introduces nothing
    # everything the exam asks is already taught by this point
    known = set(known_commands('gauntlet'))
    for tok in ('w', 'b', 'e', 'p', 'y', 'Y', 'd', 'D', 'C', 'S', 'r',
                'it', '%', '/', '*', 'dot', '~', 'gU', 'insert', '{', '}',
                '(', ')', 'q'):
        assert tok in known, tok
