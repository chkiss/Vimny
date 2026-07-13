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

"""The Word Enclosure (iw aw): the scar discrimination, the dot gap, and the
gallery's structure/karaoke discipline."""
import math

import pytest
from blessed.keyboard import Keystroke
from blessed import Terminal

import main
from engine.world import CellType
from content.levels import known_commands
from generation.dungeon_gen import (
    build_dungeon_word_enclosure,
    _WE_ROWS, _WE_COLS, _WE_SPINE, _WE_SHAFT_SEPS, _WE_THROAT,
    _WE_GATE, _WE_BOLT0, _WE_EXIT, _WE_PAR,
    _WE_C1_ROWS, _WE_C2_ROWS, _WE_C3_ROWS, _WE_C4_ROWS, _WE_C5_ROWS,
    _WE_C1_SHAPE, _WE_C2_SHAPE, _WE_C3_SHAPE, _WE_C4_SHAPE, _WE_C5_SHAPE,
    _WE_TEXT0,
)
from tests import SEEDS, cached_room

ESC = Keystroke('\x1b', name='KEY_ESCAPE')


def _room(seed=0):
    return cached_room('build_dungeon_word_enclosure', seed)


def _K(s):
    return [Keystroke(ch) for ch in s]


def _bolt(i):
    return (_WE_GATE, _WE_BOLT0 + i)


# The canonical tape (== room.answer with Esc placed): the diw drill chained
# by dot, the two ciw cures (different — no dot shortcut), the daw seam with
# a dot reprise. 34 keys; the cures vary by seed.
def _canon_keys(room):
    ca, cb = room._we_words['cures']
    return (_K('jwwdiwj.j.') + _K('2jciw') + _K(ca) + [ESC]
            + _K('jciw') + _K(cb) + [ESC] + _K('2jdawj.')
            + _K('2jdiWj.') + _K('l2jdaWj.') + _K('G$'))


# The leanest old-only rival (WITH its own best dot usage): de needs each
# rot's START (an h per stagger), ce/dw pay the hh walk back from the
# mid-rot landing. Wins at 1★.
def _piecewise_rival_keys(room):
    ca, cb = room._we_words['cures']
    return (_K('jwwdejh.j.') + _K('2jhhce') + _K(ca) + [ESC]
            + _K('jhhce') + _K(cb) + [ESC] + _K('2jhhdwj.')
            + _K('2jhdEj.') + _K('l2jhdWj.') + _K('G$'))


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
    return main.run_dungeon(term, 'word_enclosure', {}, player_name=name,
                            _dungeon=dungeon)


def _drive_spent(keys, monkeypatch, seed=0):
    box = {}
    orig = main._calc_stars
    monkeypatch.setattr(main, '_calc_stars',
                        lambda won, budget, room, player, level='':
                            (box.__setitem__('spent', budget.spent),
                             orig(won, budget, room, player, level))[1])
    result = _drive(build_dungeon_word_enclosure(seed), keys, monkeypatch)
    return result['won'], box.get('spent')


def _row_text(room, r):
    """The row's floor text, cell by cell (internal gaps preserved)."""
    out = ''
    for c in range(room.cols):
        if not room.is_passable(r, c):
            continue
        ru = room.char_run_at(r, c)
        out += ru.symbols[c - ru.col] if ru else ' '
    return out.strip()


# ── dungeon structure ─────────────────────────────────────────────────────────

@pytest.mark.parametrize("seed", SEEDS)
def test_layout_and_identity(seed):
    room = _room(seed)
    assert (room.rows, room.cols) == (_WE_ROWS, _WE_COLS)
    assert room.spawn_pos == (2, _WE_SPINE)
    assert room.exit_pos == _WE_EXIT
    exit_ent = next(e for e in room.entities if e.kind == 'exit')
    assert (exit_ent.row, exit_ent.col) == _WE_EXIT and exit_ent.edit_immune


@pytest.mark.parametrize("seed", SEEDS)
def test_par_answer_budget(seed):
    room = _room(seed)
    assert room.par == _WE_PAR
    assert room.budget == math.ceil(_WE_PAR * 1.4)
    ca, cb = room._we_words['cures']
    assert room.answer == (f'j w w diw j . j . 2j ciw {ca} j ciw {cb} '
                           f'2j daw j . 2j diW j . l 2j daW j . G $')


@pytest.mark.parametrize("seed", SEEDS)
def test_exit_and_bolts_start_sealed(seed):
    room = _room(seed)
    for i in range(5):
        assert room.cells[_bolt(i)[0]][_bolt(i)[1]] == CellType.WALL
    assert room.cells[_WE_EXIT[0]][_WE_EXIT[1]] == CellType.WALL


@pytest.mark.parametrize("seed", SEEDS)
def test_spine_is_every_rows_first_standable(seed):
    room = _room(seed)
    for r in range(room.rows):
        cols = [c for c in range(room.cols) if room.is_passable(r, c)]
        if cols:
            assert cols[0] == _WE_SPINE, f"row {r} first standable {cols[0]}"


@pytest.mark.parametrize("seed", SEEDS)
def test_light_shaft_pierces_separators_but_not_the_throat(seed):
    room = _room(seed)
    for r, c in _WE_SHAFT_SEPS:
        assert room.cells[r][c] == CellType.FLOOR
        assert room.cells[_WE_THROAT][c] == CellType.WALL


@pytest.mark.parametrize("seed", SEEDS)
def test_word_draw_shapes_and_landings(seed):
    """Fixed slot lengths; the rot stagger keeps every dot-chain landing
    INSIDE the next rot, and the shaft column inside every hopped-to rot."""
    room = _room(seed)
    words = room._we_words
    shapes = _WE_C1_SHAPE + _WE_C2_SHAPE + _WE_C3_SHAPE
    for (r, w1l, rotl, rot_s), (w1, rot, w2) in zip(shapes, words['rows']):
        assert (len(w1), len(rot), len(w2)) == (w1l, rotl, 5)
        assert rot_s == _WE_TEXT0 + w1l + 1
    # C1 chain: each after-diw cursor (rot start) is inside the NEXT rot
    for (ra, _l1, _rl, sa), (rb, _l2, rlb, sb) in zip(_WE_C1_SHAPE, _WE_C1_SHAPE[1:]):
        assert sb <= sa < sb + rlb, "the stagger keeps the dot chain alive"
    # the shafts land inside the C2/C3 rots (ce/dw pay the h's back)
    shaft = dict(_WE_SHAFT_SEPS)
    for r, _w1l, rotl, rot_s in (_WE_C2_SHAPE + _WE_C3_SHAPE[:1]):
        assert rot_s < shaft[6] < rot_s + rotl
    # the mixed tokens: two len-4 words hyphenated (one WORD, three w-words)
    for (_r, _w1l, tokl, _ts), (w1, tok, w2) in zip(
            _WE_C4_SHAPE + _WE_C5_SHAPE, words['mixed']):
        assert len(tok) == tokl == 9 and tok[4] == '-'
        assert (len(w1), len(w2)) == (3, 5)
    picks = ([w for triple in words['rows'] for w in triple]
             + [w for triple in words['mixed'] for w in triple]
             + words['cures'])
    assert len(set(picks)) == len(picks)


def test_curriculum_and_gating():
    known = known_commands('word_enclosure')
    assert all(t in known for t in ('iw', 'aw', 'iW', 'aW'))
    prev = known_commands('selection_halls')
    assert all(t not in prev for t in ('iw', 'aw', 'iW', 'aW'))


# ── the forcing law, driven ──────────────────────────────────────────────────

@pytest.mark.parametrize("seed", SEEDS)
def test_full_enclosure_route_wins_par_perfect(seed, monkeypatch):
    dungeon = build_dungeon_word_enclosure(seed)
    room = dungeon.rooms[0]
    result = _drive(dungeon, _canon_keys(room), monkeypatch)
    assert result['won'] and result['stars'] == 2, result
    for i in range(5):
        assert room.cells[_bolt(i)[0]][_bolt(i)[1]] == CellType.FLOOR


def test_canonical_route_costs_exactly_par(monkeypatch):
    room = _room(0)
    won, spent = _drive_spent(_canon_keys(room), monkeypatch)
    assert won and spent == _WE_PAR, (won, spent)


@pytest.mark.parametrize("seed", SEEDS)
def test_piecewise_route_wins_at_one_star(seed, monkeypatch):
    """THE LAW, driven: the no-text-object route (de/ce/dw with its own best
    dot usage) WINS — inside the standard budget — but over par: 1 star."""
    dungeon = build_dungeon_word_enclosure(seed)
    result = _drive(dungeon, _piecewise_rival_keys(dungeon.rooms[0]), monkeypatch)
    assert result['won'] and result['stars'] == 1, result


def test_admin_karaoke_tape_tracks_to_the_end(monkeypatch):
    dungeon = build_dungeon_word_enclosure(0)
    room = dungeon.rooms[0]
    _drive(dungeon, _canon_keys(room), monkeypatch, name='admin')
    assert not room.answer_diverged
    assert room.answer_pos == len(room.answer.replace(' ', ''))


# ── the chambers' laws ───────────────────────────────────────────────────────

def test_diw_leaves_the_scar_and_daw_heals_the_seam(monkeypatch):
    """The discrimination, driven: diw on a C1 row leaves the double gap;
    daw there would heal the seam and the door must stay barred."""
    dungeon = build_dungeon_word_enclosure(0)
    room = dungeon.rooms[0]
    (w1, _rot, w2) = room._we_words['rows'][0]
    _drive(dungeon, _K('jwwdiw'), monkeypatch, finish=':q!\r')
    assert _row_text(room, _WE_C1_ROWS[0]) == f'{w1}  {w2}'

    dungeon = build_dungeon_word_enclosure(0)
    room = dungeon.rooms[0]
    _drive(dungeon, _K('jwwdaw'), monkeypatch, finish=':q!\r')
    assert _row_text(room, _WE_C1_ROWS[0]) == f'{w1} {w2}', "seam healed"
    assert room.cells[_bolt(0)[0]][_bolt(0)[1]] == CellType.WALL, \
        "the scar door does not accept the healed seam"


def test_dw_heals_the_seam_and_is_dead_for_the_drill(monkeypatch):
    """dw from the rot's start eats the trailing gap — single gap, scar door
    stays shut (the reason the piecewise rival must use de)."""
    dungeon = build_dungeon_word_enclosure(0)
    room = dungeon.rooms[0]
    _drive(dungeon, _K('jwwdw'), monkeypatch, finish=':q!\r')
    assert room.cells[_bolt(0)[0]][_bolt(0)[1]] == CellType.WALL


def test_caw_fuses_the_cure_and_reads_false(monkeypatch):
    """caw on a cure row eats the separator — the typed cure fuses into w2
    and the exact-text door stays barred (u recovers)."""
    dungeon = build_dungeon_word_enclosure(0)
    room = dungeon.rooms[0]
    ca, _cb = room._we_words['cures']
    _drive(dungeon, _K('jwwdiwj.j.2jcaw') + _K(ca) + [ESC],
           monkeypatch, finish=':q!\r')
    w1, _rot, w2 = room._we_words['rows'][3]
    assert _row_text(room, _WE_C2_ROWS[0]) == f'{w1} {ca}{w2}', "fused"
    assert room.cells[_bolt(1)[0]][_bolt(1)[1]] == CellType.WALL


def test_diw_on_the_seam_rows_reads_false(monkeypatch):
    """The two-sided law from the other direction: diw where daw is needed
    leaves the scar and the seam door must not open."""
    dungeon = build_dungeon_word_enclosure(0)
    room = dungeon.rooms[0]
    keys = _canon_keys(room)
    # swap the first daw for diw: ...2j diw j . — the drill op on seam rows
    ca, cb = room._we_words['cures']
    bad = (_K('jwwdiwj.j.') + _K('2jciw') + _K(ca) + [ESC]
           + _K('jciw') + _K(cb) + [ESC] + _K('2jdiwj.'))
    _drive(dungeon, bad, monkeypatch, finish=':q!\r')
    assert room.cells[_bolt(2)[0]][_bolt(2)[1]] == CellType.WALL


def test_diw_on_a_mixed_token_kills_a_subword_and_reads_false(monkeypatch):
    """The CLASS lesson: iw stops at the hyphen — half the token remains and
    the scar door stays barred; only iW takes the whole WORD."""
    dungeon = build_dungeon_word_enclosure(0)
    room = dungeon.rooms[0]
    ca, cb = room._we_words['cures']
    upto_c4 = (_K('jwwdiwj.j.') + _K('2jciw') + _K(ca) + [ESC]
               + _K('jciw') + _K(cb) + [ESC] + _K('2jdawj.') + _K('2j'))
    _drive(dungeon, upto_c4 + _K('diw'), monkeypatch, finish=':q!\r')
    w1, tok, w2 = room._we_words['mixed'][0]
    assert '-' in _row_text(room, _WE_C4_ROWS[0]), "the hyphen half remains"
    assert room.cells[_bolt(3)[0]][_bolt(3)[1]] == CellType.WALL


def test_dW_heals_the_seam_and_is_dead_for_the_token_scar(monkeypatch):
    """dW eats the trailing gap — single gap where the C4 door wants the
    double-gap scar (the reason the WORD-family rival must use dE)."""
    dungeon = build_dungeon_word_enclosure(0)
    room = dungeon.rooms[0]
    ca, cb = room._we_words['cures']
    upto_c4 = (_K('jwwdiwj.j.') + _K('2jciw') + _K(ca) + [ESC]
               + _K('jciw') + _K(cb) + [ESC] + _K('2jdawj.') + _K('2j'))
    _drive(dungeon, upto_c4 + _K('hdW'), monkeypatch, finish=':q!\r')
    assert room.cells[_bolt(3)[0]][_bolt(3)[1]] == CellType.WALL


def test_undo_rebars_bolt_and_seal(monkeypatch):
    dungeon = build_dungeon_word_enclosure(0)
    room = dungeon.rooms[0]
    _drive(dungeon, _canon_keys(room)[:-2] + _K('l'), monkeypatch, finish=':q!\r')
    assert room.cells[_WE_EXIT[0]][_WE_EXIT[1]] == CellType.FLOOR, "the seal parted"

    dungeon = build_dungeon_word_enclosure(0)
    room = dungeon.rooms[0]
    # uu: the walk pushes a snapshot; the second u reaches the dotted daw
    _drive(dungeon, _canon_keys(room)[:-2] + _K('luu'), monkeypatch, finish=':q!\r')
    assert room.cells[_bolt(4)[0]][_bolt(4)[1]] == CellType.WALL, "re-bars"
    assert room.cells[_WE_EXIT[0]][_WE_EXIT[1]] == CellType.WALL, "re-seals"


def test_no_jump_lands_on_the_sealed_exit(monkeypatch):
    dungeon = build_dungeon_word_enclosure(0)
    seen = {}
    orig = main._calc_stars
    def spy(won, budget, room_, player, level=''):
        seen['pos'] = (player.row, player.col)
        return orig(won, budget, room_, player, level)
    monkeypatch.setattr(main, '_calc_stars', spy)
    result = _drive(dungeon, _K('G$'), monkeypatch, finish=':wq\r')
    assert not result['won']
    assert seen['pos'] == (_WE_GATE, _WE_SPINE), seen
