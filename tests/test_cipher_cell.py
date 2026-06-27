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

"""The Cipher Cell (L19): dungeon correctness tests.

Teaching goal: r (replace one char in place — the substitution-cipher tool) and
D (delete to line end, ONE keypress), under ONE visible rule: make the lock row
READ AS ITS PLAQUE. The plaque band shows each span's true state (a word, then
blank); the lock row decays it with a warped rune (mend with r) and rot-text
sprawling where the plaque is blank (shear with D).

r is structurally forced: at the Cipher Cell the player has no other way to
produce a character (i: the Inscription Halls; s/c: the Change Annex; R: the
Overwrite Halls — all later) and the warped letters appear
nowhere reachable, so x+p can transplant nothing. D is SOFT-forced (lineheads
precedent): par assumes D; the d$ route costs par+2 and still fits the ×1.4
budget but loses the 2-star.

All four doors run through main._cipher_cell_tick — stateless and undo-safe
(the vault-tick principle): every bolt is recomputed from the text each turn.
"""
from collections import deque

from blessed.keyboard import Keystroke
from blessed import Terminal

import main
from engine.insert import replace_chars
from engine.motion import _is_word_char
from engine.player import Player
from engine.world import CellType
from content.levels import known_commands
from generation.dungeon_gen import (
    build_dungeon_cipher_cell,
    _CC_ROWS, _CC_COLS, _CC_ROW, _CC_PLAQUE_ROW,
    _CC_SPAWN, _CC_EXIT, _CC_BOLT_A, _CC_BOLT_B, _CC_BOLT_C, _CC_BOLT_D,
    _CC_CIPHER_A_COL, _CC_CIPHER_B_COL, _CC_WORD1_COL, _CC_ROT1, _CC_ROT2,
    _CC_SPAN1, _CC_SPAN2, _CC_WARP_A, _CC_PAR,
)
import pytest

from tests import SEEDS, cached_room


def _room(seed):
    """Shared READ-ONLY build; mutating tests call the builder directly."""
    return cached_room('build_dungeon_cipher_cell', seed)


def _run_text(room, row, c0, n):
    out = []
    for c in range(c0, c0 + n):
        ru = room.char_run_at(row, c)
        out.append(ru.symbols[c - ru.col] if ru else ' ')
    return ''.join(out)


def _plaques(room):
    """(word_a, word_1, word_b, word_2) read off the sealed plaque band."""
    runs = sorted((ru for ru in room.char_runs if ru.row == _CC_PLAQUE_ROW),
                  key=lambda ru: ru.col)
    return [''.join(ru.symbols) for ru in runs]


# ── structure ─────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("seed", SEEDS)
def test_dimensions_and_anchors(seed):
    room = _room(seed)
    assert (room.rows, room.cols) == (_CC_ROWS, _CC_COLS)
    assert room.spawn_pos == _CC_SPAWN and room.exit_pos == _CC_EXIT
    exits = [e for e in room.entities if e.kind == 'exit']
    assert len(exits) == 1 and (exits[0].row, exits[0].col) == _CC_EXIT
    assert exits[0].edit_immune, "the final D sweeps the exit cell — it must be immune"
    for pos in (_CC_BOLT_A, _CC_BOLT_B, _CC_BOLT_C, _CC_BOLT_D):
        assert room.cells[pos[0]][pos[1]] == CellType.WALL, f"bolt {pos} must start shut"


@pytest.mark.parametrize("seed", SEEDS)
def test_single_floor_row_seals_the_plaques(seed):
    """Exactly one passable row exists, so no visual selection (charwise, line,
    or block) can ever straddle the plaque band — the x+p harvest stays sealed."""
    room = _room(seed)
    rows = {r for r in range(room.rows) for c in range(room.cols)
            if room.cells[r][c] in (CellType.FLOOR, CellType.CORRIDOR)}
    assert rows == {_CC_ROW}


@pytest.mark.parametrize("seed", SEEDS)
def test_plaques_match_ciphers(seed):
    """Each cipher is its plaque word with the warped position(s) swapped to an
    untypable (non-word-class) glyph; the rest of the letters agree."""
    room = _room(seed)
    word_a, _w1, word_b, _w2 = _plaques(room)
    warp_b = next(i for i in range(len(word_b) - 1) if word_b[i] == word_b[i + 1])
    ca = _run_text(room, _CC_ROW, _CC_CIPHER_A_COL, len(word_a))
    cb = _run_text(room, _CC_ROW, _CC_CIPHER_B_COL, len(word_b))
    for i, (true_ch, cur_ch) in enumerate(zip(word_a, ca)):
        if i == _CC_WARP_A:
            assert cur_ch != true_ch and not _is_word_char(cur_ch)
        else:
            assert cur_ch == true_ch
    for i, (true_ch, cur_ch) in enumerate(zip(word_b, cb)):
        if i in (warp_b, warp_b + 1):
            assert cur_ch != true_ch and not _is_word_char(cur_ch)
        else:
            assert cur_ch == true_ch


@pytest.mark.parametrize("seed", SEEDS)
def test_true_letter_scarcity(seed):
    """The warped letters appear NOWHERE reachable (the whole gauntlet row, rot
    soup included), so x+p can transplant nothing and r is the only fix."""
    room = _room(seed)
    word_a, _w1, word_b, _w2 = _plaques(room)
    warp_b = next(i for i in range(len(word_b) - 1) if word_b[i] == word_b[i + 1])
    reachable = {s for ru in room.char_runs if ru.row == _CC_ROW for s in ru.symbols}
    assert word_a[_CC_WARP_A] not in reachable
    assert word_b[warp_b] not in reachable


@pytest.mark.parametrize("seed", SEEDS)
def test_rot_is_legible_text_and_no_void(seed):
    """The rot must read as TEXT — typable word-class letters, so 'D deletes
    text' matches what the player sees (not wall-coloured cells) — sprawling
    exactly where the plaque above is blank. No void runes anywhere."""
    room = _room(seed)
    assert all(ru.kind != 'void' for ru in room.char_runs)
    for (lo, hi) in (_CC_ROT1, _CC_ROT2):
        glyphs = [ru.symbols[c - ru.col]
                  for c in range(lo, hi + 1)
                  for ru in [room.char_run_at(_CC_ROW, c)] if ru is not None]
        assert glyphs, "the rot span must hold text"
        assert all(_is_word_char(g) for g in glyphs), glyphs
        for c in range(lo, hi + 1):                   # plaque blank above the rot
            assert room.char_run_at(_CC_PLAQUE_ROW, c) is None


# ── par / answer ──────────────────────────────────────────────────────────────

@pytest.mark.parametrize("seed", SEEDS)
def test_par_is_locked_and_answer_tracks_the_combo(seed):
    """par is seed-invariant (combo shapes are identical); the answer's r-token
    letters are exactly the plaque letters under the warped positions. (Answer
    cost == par and the budget formula: covered by the universal tests.)"""
    room = _room(seed)
    word_a, _w1, word_b, _w2 = _plaques(room)
    warp_b = next(i for i in range(len(word_b) - 1) if word_b[i] == word_b[i + 1])
    assert room.par == _CC_PAR
    toks = room.answer.split()
    assert toks.count('D') == 2, "both rot spans are sheared with D on the par path"
    assert f'r{word_a[_CC_WARP_A]}' in toks
    assert f'2r{word_b[warp_b]}' in toks, "the doubled warp is fixed with ONE count-r"


def test_soft_D_forcing_margin():
    """The d$ fallback (par+2: two shears at 2 keys instead of 1) still fits the
    budget — D's forcing is deliberately SOFT, costing the par star only
    (lineheads precedent for shorthand lessons)."""
    room = _room(SEEDS[0])
    assert room.par + 2 <= room.budget


def test_D_shorthand_costs_one_keypress():
    """The engine prerequisite: D is one physical key. d$ stays 2."""
    D  = {'type': 'operator', 'op': 'd', 'motion': '$', 'count': 1,
          'motion_count': 1, 'shorthand': 'D'}
    assert main._operator_cost(D) == 1
    assert main._operator_cost({**D, 'count': 2}) == 2                   # 2D
    d_dollar = {'type': 'operator', 'op': 'd', 'motion': '$', 'count': 1,
                'motion_count': 1, 'motion_count_given': False}
    assert main._operator_cost(d_dollar) == 2


def test_r_structural_necessity_curriculum_guard():
    """r is forced because NOTHING else at L19 writes a character. If any of
    these is ever taught at or before the Cipher Cell, the gate stops forcing
    r and this level needs a redesign — fail loudly."""
    known = set(known_commands('cipher_cell'))
    for writer in ('insert', 's', 'c', 'R'):
        assert writer not in known, f"{writer!r} learned before the Cipher Cell"
    for needed in ('r', 'D', 'd', '$', 'count'):
        assert needed in known


# ── reachability (with the gates modeled open) ────────────────────────────────

@pytest.mark.parametrize("seed", SEEDS)
def test_exit_reachable_once_gates_open(seed):
    room = build_dungeon_cipher_cell(seed).rooms[0]          # private (mutating)
    for pos in (_CC_BOLT_A, _CC_BOLT_B, _CC_BOLT_C, _CC_BOLT_D):
        room.cells[pos[0]][pos[1]] = CellType.FLOOR
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
def test_tick_bolt_follows_the_cipher_both_ways(seed):
    room = build_dungeon_cipher_cell(seed).rooms[0]          # private (mutating)
    word_a = _plaques(room)[0]
    warp_col = _CC_CIPHER_A_COL + _CC_WARP_A
    glyph = room.char_run_at(_CC_ROW, warp_col).symbols[0]   # the warped rune
    p = Player(row=_CC_ROW, col=warp_col)

    main._cipher_cell_tick(room, p)
    assert room.cells[_CC_BOLT_A[0]][_CC_BOLT_A[1]] == CellType.WALL   # still corrupt

    replace_chars(room, p, word_a[_CC_WARP_A])               # the r fix
    msgs = main._cipher_cell_tick(room, p)
    assert room.cells[_CC_BOLT_A[0]][_CC_BOLT_A[1]] == CellType.FLOOR
    assert any('bolt' in m for m in msgs)

    p.col = warp_col
    replace_chars(room, p, glyph)                            # undo restored the rot
    main._cipher_cell_tick(room, p)
    assert room.cells[_CC_BOLT_A[0]][_CC_BOLT_A[1]] == CellType.WALL   # re-barred

    replace_chars(room, p, word_a[_CC_WARP_A])               # re-fix re-opens
    main._cipher_cell_tick(room, p)
    assert room.cells[_CC_BOLT_A[0]][_CC_BOLT_A[1]] == CellType.FLOOR


def _shear(room, row, lo, hi):
    for ru in [ru for ru in room.char_runs
               if ru.row == row and not (ru.col + len(ru.symbols) - 1 < lo or ru.col > hi)]:
        room.remove_char_run(ru)


@pytest.mark.parametrize("seed", SEEDS)
def test_tick_jammed_doors_track_their_rot(seed):
    room = build_dungeon_cipher_cell(seed).rooms[0]          # private (mutating)
    p = Player(row=_CC_ROW, col=2)
    main._cipher_cell_tick(room, p)
    assert room.cells[_CC_BOLT_B[0]][_CC_BOLT_B[1]] == CellType.WALL
    assert room.cells[_CC_BOLT_D[0]][_CC_BOLT_D[1]] == CellType.WALL
    _shear(room, _CC_ROW, *_CC_ROT1)                         # the D shear (word kept)
    msgs = main._cipher_cell_tick(room, p)
    assert room.cells[_CC_BOLT_B[0]][_CC_BOLT_B[1]] == CellType.FLOOR
    assert any('plaque' in m for m in msgs)
    assert room.cells[_CC_BOLT_D[0]][_CC_BOLT_D[1]] == CellType.WALL   # rot 2 untouched
    _shear(room, _CC_ROW, *_CC_ROT2)
    main._cipher_cell_tick(room, p)
    assert room.cells[_CC_BOLT_D[0]][_CC_BOLT_D[1]] == CellType.FLOOR


@pytest.mark.parametrize("seed", SEEDS)
def test_shearing_the_word_itself_keeps_the_bolt_shut(seed):
    """The plaque says the word must REMAIN: a careless D from the word's start
    (wiping word and rot alike) leaves the span mismatched and the bolt shut —
    the precision rule, recoverable with u."""
    room = build_dungeon_cipher_cell(seed).rooms[0]          # private (mutating)
    p = Player(row=_CC_ROW, col=2)
    _shear(room, _CC_ROW, _CC_WORD1_COL, _CC_SPAN1[1])       # word_1 + rot, all gone
    main._cipher_cell_tick(room, p)
    assert room.cells[_CC_BOLT_B[0]][_CC_BOLT_B[1]] == CellType.WALL


# ── full answer playthrough through the real keystroke loop ───────────────────

@pytest.mark.parametrize("seed", SEEDS)
def test_answer_playthrough_wins_at_par(seed, monkeypatch):
    """Type the answer key-for-key through run_dungeon as a normal player:
    every gate opens in sequence and the run ends par-perfect (2 stars)."""
    dungeon = build_dungeon_cipher_cell(seed)
    keys = [Keystroke(ch) for ch in dungeon.rooms[0].answer.replace(' ', '')]
    keys += [Keystroke(':'), Keystroke('w'), Keystroke('q'), Keystroke('\r')]

    monkeypatch.setattr(main, 'render_all', lambda *a, **k: None)
    monkeypatch.setattr(main.time, 'sleep', lambda *a, **k: None)
    monkeypatch.setattr(main, '_fireworks_animation', lambda *a, **k: None)
    monkeypatch.setattr(main, '_win_animation', lambda *a, **k: None)
    term = Terminal()
    it = iter(keys)
    monkeypatch.setattr(term, 'inkey', lambda *a, **k: next(it, Keystroke('')))
    result = main.run_dungeon(term, 'cipher_cell', {}, player_name='Normand',
                              _dungeon=dungeon)
    assert result['won'] and result['stars'] == 2, result
