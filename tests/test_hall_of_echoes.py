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

"""The Hall of Echoes (q @ ") — the macro gauntlet, v2 (2026-07-20).

Seven rooms chained by south seals: two poem halls (a famous 10-line rhyme
with one deadpan intruder word prepended to every line — daw at the head,
recorded once, replayed down the hall; the recording PERSISTS into hall
two), then five replay chambers reprising earlier levels' repetitive beats
with macros (Echo Vault r-hops, Alignment >>, Joiner J, Sculpting I, Case
g~~), each on a fresh register. Replayed keys are budget-free; the
all-manual road wins at 1★ under the hand-set budget."""
import pytest
from blessed.keyboard import Keystroke
from blessed import Terminal

import main
from engine.world import CellType
from engine import substitute as S
from generation.dungeon_gen import (
    build_dungeon_hall_of_echoes,
    _HE_COLS, _HE_TX, _HE_PAR, _HE_BUDGET, _HE_POEMS, _HE_CHAMBERS,
)
from tests import SEEDS

ESC = Keystroke('\x1b', code=361, name='KEY_ESCAPE')


def _K(s):
    return [ESC if ch == '\x1b' else Keystroke(ch) for ch in s]


# The canonical tape across all seven rooms (Esc written as \x1b; each
# room's slice == its room.answer with separators dropped and Esc added).
CANON = ('daw' 'qa' 'jdaw' 'q' '8@a' '2j'          # poem hall A
         'daw' '9@a' '2j'                          # poem hall B: @a persists
         'lre' 'qb' 'wlre' 'q' '6@b' '^2j'         # Echo Vault beat
         '>>' 'qc' 'j>>' 'q' '6@c' '2j'            # Alignment beat
         'J' 'qd' 'jJ' 'q' '4@d' '2j'              # Joiner beat
         'Ie\x1b' 'qe' 'jIe\x1b' 'q' '4@e' '2j'    # Sculpting beat
         'g~~' 'qf' 'jg~~' 'q' '4@f' '2j')         # Case beat → exit

# The all-manual road: every mend by hand. Wins, at 1★ (198 ≤ budget 220).
MANUAL = ('daw' + 'jdaw' * 9 + '2j'
          + 'daw' + 'jdaw' * 9 + '2j'
          + 'lre' + 'wlre' * 7 + '^2j'
          + '>>' + 'j>>' * 7 + '2j'
          + 'J' + 'jJ' * 5 + '2j'
          + 'Ie\x1b' + 'jIe\x1b' * 5 + '2j'
          + 'g~~' + 'jg~~' * 5 + '2j')


def _drive(dungeon, keys, monkeypatch, finish=':wq\r', name='Scribe'):
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
    return main.run_dungeon(term, 'hall_of_echoes', {}, player_name=name,
                            _dungeon=dungeon)


def _drive_spent(dungeon, keys, monkeypatch):
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
def test_seven_rooms_and_two_distinct_poems(seed):
    d = build_dungeon_hall_of_echoes(seed)
    assert len(d.rooms) == 7
    assert d.rooms[0]._he_poem != d.rooms[1]._he_poem
    for room in d.rooms:
        assert room.cols == _HE_COLS
        assert room.par == _HE_PAR and room.budget == _HE_BUDGET
        er, ec = room.exit_pos
        assert room.cells[er][ec] == CellType.WALL     # every seal starts shut
    # only the LAST room carries the real exit entity
    for k, room in enumerate(d.rooms):
        has_exit = any(e.kind == 'exit' for e in room.entities)
        assert has_exit == (k == len(d.rooms) - 1)


def test_poem_pool_shape():
    # Every poem: 10 lines, 10 intruders, one intruder PREPENDED per line
    # (the same word-position — the first), lines ≤ the room's floor width.
    assert len(_HE_POEMS) == 5
    for _name, lines, intr in _HE_POEMS:
        assert len(lines) == 10 and len(intr) == 10
        for w in intr:
            assert w.isalpha()                  # daw takes it whole
        for ln, w in zip(lines, intr):
            assert len(w) + 1 + len(ln) <= _HE_COLS - _HE_TX - 3


@pytest.mark.parametrize("seed", SEEDS)
def test_poem_rooms_lay_intruder_plus_true_line(seed):
    d = build_dungeon_hall_of_echoes(seed)
    for room in d.rooms[:2]:
        _name, lines, intr = next(p for p in _HE_POEMS if p[0] == room._he_poem)
        for i in range(10):
            t = S.line_text(room, 1 + i)[0].strip()
            assert t == f'{intr[i]} {lines[i]}'
            assert t != lines[i]


def test_chamber_specs_match_their_beats():
    # 5 replay chambers; each demands the exact true rows; the alignment
    # chamber alone demands a head column.
    assert len(_HE_CHAMBERS) == 5
    cols = [hc for _l, _t, _sc, hc, _a in _HE_CHAMBERS]
    assert sum(1 for c in cols if c is not None) == 1


# ── the driven gauntlet ──────────────────────────────────────────────────────

@pytest.mark.parametrize("seed", SEEDS)
def test_canonical_macro_run_wins_at_par(seed, monkeypatch):
    d = build_dungeon_hall_of_echoes(seed)
    result, spent = _drive_spent(d, _K(CANON), monkeypatch)
    assert result['won'] and result['stars'] == 2
    assert spent == _HE_PAR
    assert d.current_room == len(d.rooms) - 1


def test_all_manual_road_wins_one_star(monkeypatch):
    d = build_dungeon_hall_of_echoes(0)
    result, spent = _drive_spent(d, _K(MANUAL), monkeypatch)
    assert result['won'] and result['stars'] == 1
    assert _HE_PAR < spent <= _HE_BUDGET


def test_first_hall_macro_clears_the_second_hall(monkeypatch):
    # The recording persists across the seal: in hall two, daw + 9@a alone
    # mends the whole poem (no re-recording).
    d = build_dungeon_hall_of_echoes(0)
    tape = 'daw' 'qa' 'jdaw' 'q' '8@a' '2j' 'daw' '9@a'
    _drive(d, _K(tape), monkeypatch, finish=':q!\r')
    assert d.current_room == 1
    room = d.rooms[1]
    _name, lines, _intr = next(p for p in _HE_POEMS if p[0] == room._he_poem)
    for i in range(10):
        assert S.line_text(room, 1 + i)[0].strip() == lines[i]


def test_solved_hall_opens_south_and_advances(monkeypatch):
    d = build_dungeon_hall_of_echoes(0)
    room0 = d.rooms[0]
    tape = 'daw' 'qa' 'jdaw' 'q' '8@a'
    _drive(d, _K(tape), monkeypatch, finish=':q!\r')
    er, ec = room0.exit_pos
    assert room0.cells[er][ec] == CellType.FLOOR      # the south seal parted
    assert d.current_room == 0                        # not stepped through yet
    d2 = build_dungeon_hall_of_echoes(0)
    _drive(d2, _K(tape + '2j'), monkeypatch, finish=':q!\r')
    assert d2.current_room == 1                       # stepping south advances


def test_undo_rebars_the_south_seal(monkeypatch):
    d = build_dungeon_hall_of_echoes(0)
    room0 = d.rooms[0]
    tape = 'daw' 'qa' 'jdaw' 'q' '8@a' 'u'
    _drive(d, _K(tape), monkeypatch, finish=':q!\r')
    er, ec = room0.exit_pos
    assert room0.cells[er][ec] == CellType.WALL


def test_no_jump_lands_on_a_sealed_south_door(monkeypatch):
    # G from spawn lands the corridor row (last standable), never the seal.
    d = build_dungeon_hall_of_echoes(0)
    room0 = d.rooms[0]
    seen = {}
    orig = main._calc_stars

    def spy(won, budget, room_, player, level=''):
        seen['pos'] = (player.row, player.col)
        return orig(won, budget, room_, player, level)

    monkeypatch.setattr(main, '_calc_stars', spy)
    result = _drive(d, _K('G'), monkeypatch, finish=':wq\r')
    assert not result['won']
    assert seen['pos'][0] == room0.exit_pos[0] - 1    # the corridor, not the seal
    assert d.current_room == 0


# ── curriculum ────────────────────────────────────────────────────────────────

def test_curriculum_entry():
    from content.levels import _BY_SLUG
    lv = _BY_SLUG['hall_of_echoes']
    assert lv['teaches'] == ['q', '@', 'reg_named']
