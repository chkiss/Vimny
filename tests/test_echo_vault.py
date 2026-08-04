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

"""The Echo Vault: dungeon correctness tests.

Teaching goal: . (dot — repeat the last change), echoed off r. ONE visible
rule, the plaque family's third member: each span's bolt stands open while
the lock row READS AS ITS PLAQUE (main._echo_vault_tick, stateless/undo-safe).

Why . is forced: the warp glyphs are UNTYPABLE (punctuation class) so
f/t/F/T and / can never target them; any cut only breaks the plaque match
(precision rule, u recovers); the x+P substitution idiom seals itself
(cutting a warp overwrites the one register with the warp — P pastes the
rot back); and nothing else writes at this level (no insert/c/s/R). r is the
only mend; . is its only discount — the all-r route costs par+4, within
budget but losing the 2-star (house soft-forcing posture).

The final beat re-sizes the echo: a lone warped digit primes r{d}, and its
tripled twin falls to 3. — count-dot, Vim-faithfully overriding the count.
"""
from collections import deque

from blessed.keyboard import Keystroke
from blessed import Terminal

import vimny.game as main
from vimny.engine.motion import apply_motion, _is_word_char
from vimny.engine.player import Player
from vimny.engine.world import CellType
from vimny.content.levels import known_commands
from vimny.generation.dungeon_gen import (
    build_dungeon_echo_vault,
    _EV_ROWS, _EV_COLS, _EV_ROW, _EV_PLAQUE_ROW, _EV_SPAWN, _EV_EXIT,
    _EV_SEG1_COL, _EV_SEG2_COL, _EV_SEG3_COL,
    _EV_WARPS1, _EV_WARPS2, _EV_WARP3_SINGLE, _EV_WARP3_TRIPLE,
    _EV_BOLT_A, _EV_BOLT_B, _EV_BOLT_C, _EV_PAR,
)
import pytest

from tests import SEEDS, cached_room


def _room(seed):
    """Shared READ-ONLY build; mutating tests call the builder directly."""
    return cached_room('build_dungeon_echo_vault', seed)


def _cell(room, r, c):
    ru = room.char_run_at(r, c)
    return ru.symbols[c - ru.col] if ru else None


def _span_text(room, row, c0, n):
    return ''.join(_cell(room, row, c0 + k) or ' ' for k in range(n))


def _plaques(room):
    """(phrase1, phrase2, phrase3) read off the sealed plaque band (the combo
    shapes are fixed: 13, 10 and 14 columns)."""
    return (_span_text(room, _EV_PLAQUE_ROW, _EV_SEG1_COL, 13),
            _span_text(room, _EV_PLAQUE_ROW, _EV_SEG2_COL, 10),
            _span_text(room, _EV_PLAQUE_ROW, _EV_SEG3_COL, 14))


def _drive(dungeon, keys_str, monkeypatch, finish=':q!\r'):
    keys = [Keystroke(ch) for ch in keys_str] + [Keystroke(ch) for ch in finish]
    monkeypatch.setattr(main, 'render_all', lambda *a, **k: None)
    monkeypatch.setattr(main.time, 'sleep', lambda *a, **k: None)
    monkeypatch.setattr(main, '_fireworks_animation', lambda *a, **k: None)
    monkeypatch.setattr(main, '_win_animation', lambda *a, **k: None)
    term = Terminal()
    it = iter(keys)
    monkeypatch.setattr(term, 'inkey', lambda *a, **k: next(it, Keystroke('')))
    return main.run_dungeon(term, 'echo_vault', {}, player_name='Echo',
                            _dungeon=dungeon)


# ── structure ─────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("seed", SEEDS)
def test_dimensions_and_anchors(seed):
    room = _room(seed)
    assert (room.rows, room.cols) == (_EV_ROWS, _EV_COLS)
    assert room.spawn_pos == _EV_SPAWN and room.exit_pos == _EV_EXIT
    exits = [e for e in room.entities if e.kind == 'exit']
    assert len(exits) == 1 and (exits[0].row, exits[0].col) == _EV_EXIT
    assert exits[0].edit_immune, "a careless D sweeps the exit cell — immune"
    for pos in (_EV_BOLT_A, _EV_BOLT_B, _EV_BOLT_C):
        assert room.cells[pos[0]][pos[1]] == CellType.WALL, f"bolt {pos} starts shut"


@pytest.mark.parametrize("seed", SEEDS)
def test_single_floor_row_seals_the_plaques(seed):
    """One passable row: no visual selection can straddle the plaque band, no
    other row can walk toward the exit, and every line jump (G/{n}G/H/M/L)
    lands on THIS row's first non-blank — far west of the final bolt."""
    room = _room(seed)
    rows = {r for r in range(room.rows) for c in range(room.cols)
            if room.cells[r][c] in (CellType.FLOOR, CellType.CORRIDOR)}
    assert rows == {_EV_ROW}


@pytest.mark.parametrize("seed", SEEDS)
def test_line_jumps_land_far_from_the_exit(seed):
    room = build_dungeon_echo_vault(seed).rooms[0]           # private (mutating)
    jumps = ([('G', 1, False), ('gg', 1, False), ('H', 1, False),
              ('M', 1, False), ('L', 1, False)]
             + [('G', n, True) for n in range(1, _EV_ROWS)])
    for motion, count, count_given in jumps:
        p = Player(row=room.spawn_pos[0], col=room.spawn_pos[1])
        apply_motion(p, motion, count, room, count_given=count_given)
        assert (p.row, p.col) != _EV_EXIT
        assert p.col < _EV_BOLT_A[1], f"{motion} landed past the first bolt"


@pytest.mark.parametrize("seed", SEEDS)
def test_warps_are_untypable_and_match_their_plaques(seed):
    """Every warped position holds an untypable punctuation glyph (f/t// can
    never target it; r can never be replaced by typing it); every unwarped
    position agrees with the plaque; the three segments use distinct glyphs."""
    room = _room(seed)
    p1, p2, p3 = _plaques(room)
    glyphs = set()
    for (col, true, offsets) in (
        (_EV_SEG1_COL, p1, _EV_WARPS1),
        (_EV_SEG2_COL, p2, _EV_WARPS2),
        (_EV_SEG3_COL, p3, (_EV_WARP3_SINGLE, *_EV_WARP3_TRIPLE)),
    ):
        for i, true_ch in enumerate(true):
            cur = _cell(room, _EV_ROW, col + i) or ' '
            if i in offsets:
                assert cur != true_ch and not _is_word_char(cur) \
                    and not cur.isascii(), (col, i, cur)
                glyphs.add(cur)
            else:
                assert cur == true_ch, (col, i, cur, true_ch)
    assert len(glyphs) == 3, "each segment wears its own warp glyph"


@pytest.mark.parametrize("seed", SEEDS)
def test_mend_letter_scarcity(seed):
    """Each phrase carries its mend letter ONLY at the warped offsets — all
    copies get warped, so the cure exists nowhere reachable (belt and braces:
    the register self-seal already blocks transplants)."""
    room = _room(seed)
    p1, p2, p3 = _plaques(room)
    l1, l2 = p1[_EV_WARPS1[0]], p2[_EV_WARPS2[0]]
    digit = p3[_EV_WARP3_SINGLE]
    reachable = {s for ru in room.char_runs if ru.row == _EV_ROW for s in ru.symbols}
    assert l1 not in reachable and l2 not in reachable and digit not in reachable


# ── par / answer ──────────────────────────────────────────────────────────────

@pytest.mark.parametrize("seed", SEEDS)
def test_par_is_locked_and_answer_tracks_the_combo(seed):
    """par is seed-invariant (combo shapes identical); the answer mends with
    ONE r per letter and echoes the rest — including the count-dot finale."""
    room = _room(seed)
    p1, p2, p3 = _plaques(room)
    assert room.par == _EV_PAR
    toks = room.answer.split()
    assert toks.count('.') == 4, "four plain echoes on the par path"
    assert '3.' in toks, "the triple falls to ONE count-dot"
    assert f'r{p1[_EV_WARPS1[0]]}' in toks
    assert f'r{p2[_EV_WARPS2[0]]}' in toks
    assert f'r{p3[_EV_WARP3_SINGLE]}' in toks
    assert toks.count('r' + p3[_EV_WARP3_SINGLE]) == 1, \
        "the triple is never mended with r directly"


def test_all_r_route_is_star_soft():
    """Mending every warp with r instead of . costs par+5 (the 4 plain dots
    +1 each; 3r{d} over 3. +1) — within the ×1.4 budget, losing the star."""
    room = _room(SEEDS[0])
    assert room.par + 5 <= room.budget


def test_curriculum_guard():
    """Forcing assumptions: nothing else writes at the Echo Vault (no insert,
    no substitutes, no R, no :s) and the prerequisite tools are known."""
    known = set(known_commands('echo_vault'))
    for needed in ('dot', 'r', 'd', 'D', 'y', 'P', 'p', 'count', '$', 'G'):
        assert needed in known
    for absent in ('insert', 's', 'c', 'R', 'subst', 'register', 'reg_named'):
        assert absent not in known, f"{absent!r} learned at or before the Echo Vault"


# ── reachability ──────────────────────────────────────────────────────────────

@pytest.mark.parametrize("seed", SEEDS)
def test_exit_reachable_once_bolts_open(seed):
    room = build_dungeon_echo_vault(seed).rooms[0]           # private (mutating)
    assert_unreached = room.exit_pos
    seen, q = {room.spawn_pos}, deque([room.spawn_pos])
    while q:
        r, c = q.popleft()
        for dr, dc in ((0, 1), (0, -1), (1, 0), (-1, 0)):
            nb = (r + dr, c + dc)
            if nb not in seen and room.is_passable(*nb):
                seen.add(nb)
                q.append(nb)
    assert assert_unreached not in seen, "the exit is sealed as built"
    for pos in (_EV_BOLT_A, _EV_BOLT_B, _EV_BOLT_C):
        room.cells[pos[0]][pos[1]] = CellType.FLOOR
    from vimny.engine.motion import auto_fog_tick
    auto_fog_tick(room, *room.spawn_pos)     # sight crosses the opened bolts
    seen, q = {room.spawn_pos}, deque([room.spawn_pos])
    while q:
        r, c = q.popleft()
        for dr, dc in ((0, 1), (0, -1), (1, 0), (-1, 0)):
            nb = (r + dr, c + dc)
            if nb not in seen and room.is_passable(*nb):
                seen.add(nb)
                q.append(nb)
    assert room.exit_pos in seen


# ── the tick: stateless, undo-safe ────────────────────────────────────────────

@pytest.mark.parametrize("seed", SEEDS)
def test_tick_bolt_follows_the_mend_both_ways(seed):
    from vimny.engine.insert import replace_chars
    room = build_dungeon_echo_vault(seed).rooms[0]           # private (mutating)
    p1, _p2, _p3 = _plaques(room)
    l1 = p1[_EV_WARPS1[0]]
    warp_cols = [_EV_SEG1_COL + i for i in _EV_WARPS1]
    glyph = _cell(room, _EV_ROW, warp_cols[0])
    p = Player(row=_EV_ROW, col=warp_cols[0])

    main._echo_vault_tick(room, p)
    assert room.cells[_EV_BOLT_A[0]][_EV_BOLT_A[1]] == CellType.WALL

    for c in warp_cols:                                      # mend all three
        p.col = c
        replace_chars(room, p, l1)
    msgs = main._echo_vault_tick(room, p)
    assert room.cells[_EV_BOLT_A[0]][_EV_BOLT_A[1]] == CellType.FLOOR
    assert any('bolt' in m for m in msgs)

    p.col = warp_cols[1]
    replace_chars(room, p, glyph)                            # undo restored a warp
    main._echo_vault_tick(room, p)
    assert room.cells[_EV_BOLT_A[0]][_EV_BOLT_A[1]] == CellType.WALL   # re-barred


# ── the forcing seals, through the real keystroke loop ────────────────────────

@pytest.mark.parametrize("seed", SEEDS)
def test_yank_does_not_disarm_the_echo(seed, monkeypatch):
    """Vim: yank is not a change. After priming the echo with r, a stray yl
    must not clobber last_change — the next . still mends the next warp.
    (Regression for the engine fix this level motivated.)"""
    dungeon = build_dungeon_echo_vault(seed)
    room = dungeon.rooms[0]
    p1 = _plaques(room)[0]
    l1 = p1[_EV_WARPS1[0]]
    _drive(dungeon, f'wwr{l1}ylww.', monkeypatch)
    assert _cell(room, _EV_ROW, _EV_SEG1_COL + _EV_WARPS1[1]) == l1, \
        "the echo survived the yank"


@pytest.mark.parametrize("seed", SEEDS)
def test_register_self_seal_blocks_the_transplant(seed, monkeypatch):
    """Cutting a warp overwrites the unnamed register with the warp itself —
    the cure can't ride the same register as the disease."""
    dungeon = build_dungeon_echo_vault(seed)
    glyph = _cell(dungeon.rooms[0], _EV_ROW, _EV_SEG1_COL + _EV_WARPS1[0])
    room = dungeon.rooms[0]
    _drive(dungeon, 'wwxP', monkeypatch)                     # x the warp, paste back
    assert _cell(room, _EV_ROW, _EV_SEG1_COL + _EV_WARPS1[0]) == glyph, \
        "P pasted the rot back — the register self-seal held"


@pytest.mark.parametrize("seed", SEEDS)
def test_careless_D_keeps_the_bolt_shut(seed, monkeypatch):
    """The precision rule: D from a warp shears the keepers too — the span no
    longer reads as its plaque and the bolt stays shut (u recovers)."""
    dungeon = build_dungeon_echo_vault(seed)
    room = dungeon.rooms[0]
    _drive(dungeon, 'wwD', monkeypatch)
    assert room.cells[_EV_BOLT_A[0]][_EV_BOLT_A[1]] == CellType.WALL


# Full answer playthrough (canonical tape → run_dungeon → 2-star win) is covered
# for every seed by the universal test_answer_paths.py::test_answer_path_actually_wins.
