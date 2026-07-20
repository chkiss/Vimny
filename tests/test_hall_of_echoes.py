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

"""The Hall of Echoes (q @ ") — the macro gauntlet, v3 (2026-07-20).

Two rooms. Room 0: a poem hall — one famous 10-line rhyme (5-poem pool)
with a deadpan intruder word prepended to every line; daw at the head,
recorded once (qa), replayed down the hall. Room 1: ONE tall map of six
chambers stacked south, each replaying an earlier level's repetitive beat
WITH THAT LEVEL'S OWN LOOK (Echo Vault warped runes · Alignment masonry ·
Joiner split inscriptions · Sculpting merrily rows · Case GRANITE ·
Culling's Humpty-between-Jack lines), each on a fresh register (qb…qg).
Chambers are runs of text rows split by stone bands whose west gates grind
open as each chamber reads true; the exit under the last band needs every
chamber true. Every tape segment LEADS with its recording. Replayed keys
are budget-free; the all-manual road wins at 1★ (143 ≤ budget 220)."""
import pytest
from blessed.keyboard import Keystroke
from blessed import Terminal

import main
from engine.world import CellType
from engine import substitute as S
from generation.dungeon_gen import (
    build_dungeon_hall_of_echoes,
    _HE_COLS, _HE_TX, _HE_GATE_COL, _HE_PAR, _HE_BUDGET, _HE_POEMS,
    _HE_CHAMBERS, _HE_WARP,
)
from tests import SEEDS

ESC = Keystroke('\x1b', code=361, name='KEY_ESCAPE')


def _K(s):
    return [ESC if ch == '\x1b' else Keystroke(ch) for ch in s]


# The canonical tape (rooms 0 + 1; Esc written as \x1b). Each segment ==
# its room.answer slice with separators dropped and Esc restored; EVERY
# segment leads with its recording (qa…qg — the named-register drill).
POEM_TAPE = 'qadawjq9@aj'
MAP_TAPE = ('qbrewwq7@b02j'
            'qc>>jq3@c02j'
            'qdJjq3@d02j'
            'qeIm\x1bjq3@e02j'
            'qfg~~jq3@f02j'
            'qgddjq3@g0j')
CANON = POEM_TAPE + MAP_TAPE

# The all-manual road: every mend by hand. Wins, at 1★ (143 measured).
MANUAL = ('daw' + 'jdaw' * 9 + 'jj'
          + 're' + 'wwre' * 7 + '02j'
          + '>>' + 'j>>' * 3 + '02j'
          + 'J' + 'jJ' * 3 + '02j'
          + 'Im\x1b' + 'jIm\x1b' * 3 + '02j'
          + 'g~~' + 'jg~~' * 3 + '02j'
          + 'dd' + 'jdd' * 3 + '0j')


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
def test_two_rooms_poem_hall_and_gauntlet_map(seed):
    d = build_dungeon_hall_of_echoes(seed)
    assert len(d.rooms) == 2
    poem, gmap = d.rooms
    assert poem._he_poem in {p[0] for p in _HE_POEMS}
    for room in d.rooms:
        assert room.cols == _HE_COLS
        assert room.par == _HE_PAR and room.budget == _HE_BUDGET
    # the poem hall's south seal starts shut; only the map has the exit
    er, ec = poem.exit_pos
    assert poem.cells[er][ec] == CellType.WALL
    assert not any(e.kind == 'exit' for e in poem.entities)
    ge, gc = gmap.exit_pos
    assert gmap.cells[ge][gc] == CellType.WALL
    assert any(e.kind == 'exit' and (e.row, e.col) == (ge, gc)
               for e in gmap.entities)


def test_poem_pool_shape():
    # Every poem: 10 lines, 10 intruders, one intruder PREPENDED per line
    # (the same word-position — the first), lines within the floor width.
    assert len(_HE_POEMS) == 5
    for _name, lines, intr in _HE_POEMS:
        assert len(lines) == 10 and len(intr) == 10
        for w in intr:
            assert w.isalpha()                  # daw takes it whole
        for ln, w in zip(lines, intr):
            assert len(w) + 1 + len(ln) <= _HE_COLS - _HE_TX - 3


@pytest.mark.parametrize("seed", SEEDS)
def test_poem_hall_lays_intruder_plus_true_line_uncolored(seed):
    d = build_dungeon_hall_of_echoes(seed)
    room = d.rooms[0]
    _name, lines, intr = next(p for p in _HE_POEMS if p[0] == room._he_poem)
    for i in range(10):
        t = S.line_text(room, 1 + i)[0].strip()
        assert t == f'{intr[i]} {lines[i]}'
    # no different-colouring of the out-of-place word (playtest 2026-07-20)
    assert all(ru.kind == 'ancient' for ru in room.char_runs)


def test_chambers_wear_their_original_levels_faces():
    # Six chambers; each replay uses the ORIGINAL level's words/glyphs.
    assert len(_HE_CHAMBERS) == 6
    laids = [laid for laid, _d, _c, _t in _HE_CHAMBERS]
    assert _HE_WARP in laids[0][0]                    # Echo Vault warped runes
    assert 'she s' in laids[0][0].replace(_HE_WARP, 'e')[:6]
    assert 'lintel' in laids[1]                       # Alignment masonry
    assert 'the way' in laids[2]                      # Joiner split lines
    assert laids[3] == ('errily',) * 4                # Sculpting merrily rows
    assert laids[4] == ('GRANITE',) * 4               # Case shouting
    assert any('Humpty' in x for x in laids[5])       # Culling's squatter
    # every tape segment LEADS with its recording, registers a…g in order
    regs = [t.split(' ')[0] for _l, _d, _c, t in _HE_CHAMBERS]
    assert regs == ['qb', 'qc', 'qd', 'qe', 'qf', 'qg']
    d = build_dungeon_hall_of_echoes(0)
    assert d.rooms[0].answer.startswith('qa ')


def test_map_is_one_buffer_with_stone_bands():
    d = build_dungeon_hall_of_echoes(0)
    gmap = d.rooms[1]
    # runs of text rows split by all-wall band rows, one run per chamber
    runs, cur = [], 0
    for r in range(gmap.rows):
        has_text = bool(gmap._char_runs_by_row.get(r))
        if has_text:
            cur += 1
        elif cur:
            runs.append(cur)
            cur = 0
    assert len(runs) == len(_HE_CHAMBERS)
    assert runs == [len(laid) for laid, _d, _c, _t in _HE_CHAMBERS]


# ── the driven gauntlet ──────────────────────────────────────────────────────

@pytest.mark.parametrize("seed", SEEDS)
def test_canonical_macro_run_wins_at_par(seed, monkeypatch):
    d = build_dungeon_hall_of_echoes(seed)
    result, spent = _drive_spent(d, _K(CANON), monkeypatch)
    assert result['won'] and result['stars'] == 2
    assert spent == _HE_PAR
    assert d.current_room == 1


def test_all_manual_road_wins_one_star(monkeypatch):
    d = build_dungeon_hall_of_echoes(0)
    result, spent = _drive_spent(d, _K(MANUAL), monkeypatch)
    assert result['won'] and result['stars'] == 1
    assert _HE_PAR < spent <= _HE_BUDGET


def test_poem_hall_south_seal_advances_to_the_map(monkeypatch):
    d = build_dungeon_hall_of_echoes(0)
    poem = d.rooms[0]
    _drive(d, _K('qadawjq9@a'), monkeypatch, finish=':q!\r')
    er, ec = poem.exit_pos
    assert poem.cells[er][ec] == CellType.FLOOR       # the south seal parted
    assert d.current_room == 0                        # not stepped through yet
    d2 = build_dungeon_hall_of_echoes(0)
    _drive(d2, _K(POEM_TAPE), monkeypatch, finish=':q!\r')
    assert d2.current_room == 1                       # stepping south advances


def test_each_solved_chamber_grinds_its_band_gate(monkeypatch):
    # Solving the Echo Vault chamber alone opens the FIRST band's west gate
    # (sight floods to the next chamber); the exit stays sealed.
    d = build_dungeon_hall_of_echoes(0)
    _drive(d, _K(POEM_TAPE + 'qbrewwq7@b'), monkeypatch, finish=':q!\r')
    gmap = d.rooms[1]
    band = 1 + len(_HE_CHAMBERS[0][0])                # row under the EV run
    assert gmap.cells[band][_HE_GATE_COL] == CellType.FLOOR
    ge, gc = gmap.exit_pos
    assert gmap.cells[ge][gc] == CellType.WALL


def test_undo_rebars_a_band_gate(monkeypatch):
    d = build_dungeon_hall_of_echoes(0)
    _drive(d, _K(POEM_TAPE + 'qbrewwq7@bu'), monkeypatch, finish=':q!\r')
    gmap = d.rooms[1]
    band = 1 + len(_HE_CHAMBERS[0][0])
    assert gmap.cells[band][_HE_GATE_COL] == CellType.WALL


def test_no_jump_lands_on_the_sealed_exit(monkeypatch):
    d = build_dungeon_hall_of_echoes(0)
    seen = {}
    orig = main._calc_stars

    def spy(won, budget, room_, player, level=''):
        seen['pos'] = (player.row, player.col)
        return orig(won, budget, room_, player, level)

    monkeypatch.setattr(main, '_calc_stars', spy)
    result = _drive(d, _K(POEM_TAPE + 'G'), monkeypatch, finish=':wq\r')
    assert not result['won']
    gmap = d.rooms[1]
    assert seen['pos'] != tuple(gmap.exit_pos)


# ── curriculum ────────────────────────────────────────────────────────────────

def test_curriculum_entry():
    from content.levels import _BY_SLUG
    lv = _BY_SLUG['hall_of_echoes']
    assert lv['teaches'] == ['q', '@', 'reg_named']
