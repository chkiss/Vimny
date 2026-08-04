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

"""The Selection Halls (V <C-v>): the case-trio forcing (the g-prefix tax),
the block ops' price gaps, block-insert propagation, and the gallery's
structure/karaoke discipline."""
import math

import pytest
from blessed.keyboard import Keystroke
from blessed import Terminal

import vimny.game as main
from vimny.engine.world import CellType
from vimny.content.levels import known_commands
from vimny.generation.dungeon_gen import (
    build_dungeon_selection_halls,
    _SH_ROWS, _SH_COLS, _SH_SPINE, _SH_SHAFT, _SH_SHAFT_SEPS, _SH_THROAT,
    _SH_GATE, _SH_BOLT0, _SH_EXIT, _SH_PAR,
    _SH_CASE_ROWS, _SH_STRIPE_ROWS, _SH_RECT_ROWS, _SH_INS_ROWS,
)
from tests import SEEDS, cached_room

ESC = Keystroke('\x1b', name='KEY_ESCAPE')
CV  = Keystroke('\x16')


def _room(seed=0):
    return cached_room('build_dungeon_selection_halls', seed)


def _K(s):
    return [Keystroke(ch) for ch in s]


def _bolt(i):
    return (_SH_GATE, _SH_BOLT0 + i)


# The canonical tape (== room.answer with <C-v>/Esc placed; <C-v> on the tape
# is the <C-v> keystroke). 64 keys; the typed letters vary by seed.
def _canon_keys(room):
    w = room._sh_words
    return (_K('jVU2jVu2jV~2j') + [CV] + _K('2jld') + _K('4j') + [CV]
            + _K('2j3l~') + _K('4j') + [CV] + _K('2jI') + _K(w['letter']) + [ESC]
            + _K('4j') + [CV] + _K('2jr') + _K(w['stamp_letter'])
            + _K('4j$bvey3j$bvepk$bvepk$bvepk$bvep') + _K('G$'))


# The leanest old-only rival: gUU/guu/g~~ for the trio, 2x + dot down the
# stripe, count-~ chains over the rectangle, hand inserts (dot after an
# insert only RE-ENTERS insert), r + dot for the stamp — and for the four
# panels, cut-then-paste ONCE (the bay wall eats the pushed word — the
# void-push) then RETYPE the rest: visual p is terrain-forced. Wins at 1★
# only because the budget is hand-set generous (110 = old min 109 + 1; the
# route pays two count-x digit charges under the 2026-07-19 {n}x law).
def _rival_keys(room):
    w = room._sh_words
    keys = (_K('jgUU2jguu2jg~~2j') + _K('2xj.j.') + _K('2j')
            + _K('4~j4h.j4h.') + _K('4h2j'))
    for i in range(3):
        keys += _K('i') + _K(w['letter']) + [ESC]
        if i < 2:
            keys += _K('j')
    keys += _K('2j^2lr') + _K(w['stamp_letter']) + _K('j^2l.j^2l.')
    # the four panels, old-only: retype each wrong ending in place with ce
    # (no visual swap) — correct but keystroke-heavier than the …$bvep… cycle
    prov = w['proverbs']
    keys += _K('2j')                                # row 23 → panel r0 (row 25)
    for i in range(4):
        keys += _K('$bce') + _K(prov[i][1]) + [ESC]
        if i < 3:
            keys += _K('j')
    return keys + _K('G$')


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
    return main.run_dungeon(term, 'selection_halls', {}, player_name=name,
                            _dungeon=dungeon)


def _spend_uncapped(dungeon, keys, monkeypatch, _drive_fn):
    """Drive a route with the budget UNCAPPED and return (won, spent).

    PAR-IS-THE-OPTIMUM (docs/ARCHITECTURE.md): the budget follows par at 1.4x and
    is never widened to keep a sub-optimal route alive, so a rival's claim to
    test is that it costs MORE THAN PAR — not that it squeaks inside a hand-set
    budget. Whether it also falls outside the standard budget is a consequence of
    how much worse it is, not a design knob."""
    box = {}
    orig = main._calc_stars
    monkeypatch.setattr(main, '_calc_stars',
                        lambda won, budget, room, player, level='':
                            (box.__setitem__('spent', budget.spent),
                             orig(won, budget, room, player, level))[1])
    for r in dungeon.rooms:
        r.budget = 99999
    result = _drive_fn(dungeon, keys, monkeypatch)
    return result['won'], box.get('spent')



def _drive_spent(keys, monkeypatch, seed=0):
    box = {}
    orig = main._calc_stars
    monkeypatch.setattr(main, '_calc_stars',
                        lambda won, budget, room, player, level='':
                            (box.__setitem__('spent', budget.spent),
                             orig(won, budget, room, player, level))[1])
    result = _drive(build_dungeon_selection_halls(seed), keys, monkeypatch)
    return result['won'], box.get('spent')


def _row_text(room, r):
    """The row's floor text, cell by cell (runs may be stored unmerged)."""
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
    assert (room.rows, room.cols) == (_SH_ROWS, _SH_COLS)
    assert room.spawn_pos == (2, _SH_SPINE)
    assert room.exit_pos == _SH_EXIT
    exit_ent = next(e for e in room.entities if e.kind == 'exit')
    assert (exit_ent.row, exit_ent.col) == _SH_EXIT and exit_ent.edit_immune


@pytest.mark.parametrize("seed", SEEDS)
def test_par_answer_budget(seed):
    room = _room(seed)
    assert room.par == _SH_PAR
    assert room.budget == math.ceil(_SH_PAR * 1.4)   # STANDARD
    L, sl = room._sh_words['letter'], room._sh_words['stamp_letter']
    # <C-v> shows as <C-v> — LOAD-BEARING on the tape (playtest: omitting it
    # made the tape unplayable; a d2j swallowed a stripe row)
    assert room.answer == (f'j VU 2j Vu 2j V~ 2j <C-v>2jld 4j <C-v>2j3l~ 4j <C-v>2jI{L}<Esc> '
                           f'4j <C-v>2jr{sl} 4j $bvey 3j $bvep k$bvep k$bvep k$bvep G $')


@pytest.mark.parametrize("seed", SEEDS)
def test_exit_and_bolts_start_sealed(seed):
    room = _room(seed)
    for i in range(8):
        assert room.cells[_bolt(i)[0]][_bolt(i)[1]] == CellType.WALL
    assert room.cells[_SH_EXIT[0]][_SH_EXIT[1]] == CellType.WALL


@pytest.mark.parametrize("seed", SEEDS)
def test_spine_is_every_rows_first_standable(seed):
    room = _room(seed)
    for r in range(room.rows):
        cols = [c for c in range(room.cols) if room.is_passable(r, c)]
        if cols:
            assert cols[0] == _SH_SPINE, f"row {r} first standable {cols[0]}"


@pytest.mark.parametrize("seed", SEEDS)
def test_light_shaft_pierces_separators_but_not_the_throat(seed):
    room = _room(seed)
    for r in _SH_SHAFT_SEPS:
        assert room.cells[r][_SH_SHAFT] == CellType.FLOOR
    assert room.cells[_SH_THROAT][_SH_SHAFT] == CellType.WALL


@pytest.mark.parametrize("seed", SEEDS)
def test_word_draw_slot_shapes(seed):
    """Fixed slot lengths pin par and the rival chains; the insert words
    share the letter at index 2 (the one typed cure); all distinct."""
    w = _room(seed)._sh_words
    assert [len(x) for x in w['case']] == [6, 6, 6]
    assert [len(x) for x in w['stripe']] == [5, 5, 5]
    assert [len(x) for x in w['rect']] == [8, 8, 8]
    assert [len(x) for x in w['ins']] == [7, 7, 7]
    assert all(x[2] == w['letter'] for x in w['ins'])
    assert [len(x) for x in w['stamp']] == [6, 6, 6]
    assert all(x[2] == w['stamp_letter'] for x in w['stamp'])
    # the four panels are proverbs (stem, last) with DISTINCT last words
    prov = w['proverbs']
    assert len(prov) == 4
    assert len({last for _stem, last in prov}) == 4
    picks = w['case'] + w['stripe'] + w['rect'] + w['ins'] + w['stamp']
    assert len(set(picks)) == len(picks)


def test_curriculum_and_gating():
    known = known_commands('selection_halls')
    assert 'visual_line' in known and 'visual_block' in known
    assert 'visual_op' in known, "arrives already-known from the Sight Sanctum"


# ── the forcing law, driven ──────────────────────────────────────────────────

@pytest.mark.parametrize("seed", SEEDS)
def test_full_selection_route_wins_par_perfect(seed, monkeypatch):
    dungeon = build_dungeon_selection_halls(seed)
    room = dungeon.rooms[0]
    result = _drive(dungeon, _canon_keys(room), monkeypatch)
    assert result['won'] and result['stars'] == 2, result
    for i in range(8):
        assert room.cells[_bolt(i)[0]][_bolt(i)[1]] == CellType.FLOOR


def test_canonical_route_costs_exactly_par(monkeypatch):
    room = _room(0)
    won, spent = _drive_spent(_canon_keys(room), monkeypatch)
    assert won and spent == _SH_PAR, (won, spent)


@pytest.mark.parametrize("seed", SEEDS)
def test_piecewise_route_wins_at_one_star(seed, monkeypatch):
    """THE LAW, driven: the no-V/<C-v> route (gUU/guu/g~~ + per-row chains)
    WINS — inside the standard budget — but over par: 1 star."""
    dungeon = build_dungeon_selection_halls(seed)
    won, spent = _spend_uncapped(dungeon, _rival_keys(dungeon.rooms[0]),
                                 monkeypatch, _drive)
    assert won and spent > dungeon.rooms[0].par, (won, spent)


def test_admin_karaoke_tape_tracks_to_the_end(monkeypatch):
    """<C-v> is omitted from the tape like Esc; everything else tracks."""
    dungeon = build_dungeon_selection_halls(0)
    room = dungeon.rooms[0]
    _drive(dungeon, _canon_keys(room), monkeypatch, name='admin')
    assert not room.answer_diverged
    assert room.answer_pos == len(room.answer.replace(' ', ''))


# ── the chambers' laws ───────────────────────────────────────────────────────

def test_block_delete_closes_each_rows_gap(monkeypatch):
    """Vim-true block delete: every row's tail pulls left independently —
    the stripe rows read whole after one <C-v> d."""
    dungeon = build_dungeon_selection_halls(0)
    room = dungeon.rooms[0]
    _drive(dungeon, _K('jVU2jVu2jV~2j') + [CV] + _K('2jld'),
           monkeypatch, finish=':q!\r')
    for r, w in zip(_SH_STRIPE_ROWS, room._sh_words['stripe']):
        assert _row_text(room, r) == w
    assert room.cells[_bolt(3)[0]][_bolt(3)[1]] == CellType.FLOOR


def test_block_insert_propagates_to_every_row(monkeypatch):
    """The new engine: <C-v> {n}j I {x} Esc replays the typed run into every
    selected row at the anchor column."""
    dungeon = build_dungeon_selection_halls(0)
    room = dungeon.rooms[0]
    _drive(dungeon, _canon_keys(room)[:-2], monkeypatch, finish=':q!\r')
    for r, w in zip(_SH_INS_ROWS, room._sh_words['ins']):
        assert _row_text(room, r) == w
    assert room.cells[_bolt(5)[0]][_bolt(5)[1]] == CellType.FLOOR


def test_visual_u_lowercases_it_is_not_undo(monkeypatch):
    """The trap-lesson: with a live selection, u is the lowercase SET —
    driving V u on the Vu chamber opens its bolt (nothing was undone)."""
    dungeon = build_dungeon_selection_halls(0)
    room = dungeon.rooms[0]
    _drive(dungeon, _K('3jVu'), monkeypatch, finish=':q!\r')
    assert room.cells[_bolt(1)[0]][_bolt(1)[1]] == CellType.FLOOR
    assert _row_text(room, _SH_CASE_ROWS[1]) == room._sh_words['case'][1]


def test_wrong_case_sweep_is_a_dead_route(monkeypatch):
    """VU on the full-flip chamber writes wrong case — the mixed target needs
    the toggle, not a sweep; the bolt stays barred (u recovers)."""
    dungeon = build_dungeon_selection_halls(0)
    room = dungeon.rooms[0]
    _drive(dungeon, _K('5jVU'), monkeypatch, finish=':q!\r')
    assert room.cells[_bolt(2)[0]][_bolt(2)[1]] == CellType.WALL


def test_linewise_case_on_rect_names_is_dead(monkeypatch):
    """The rectangle's capital initials are the guards: Vu across the three
    names lowercases the initials too — the doors must stay barred."""
    dungeon = build_dungeon_selection_halls(0)
    room = dungeon.rooms[0]
    _drive(dungeon, _K('11jV2ju'), monkeypatch, finish=':q!\r')
    assert room.cells[_bolt(4)[0]][_bolt(4)[1]] == CellType.WALL


def test_dot_replays_a_full_insert(monkeypatch):
    """Vim-true '.': after i…Esc, dot replays the TYPED TEXT and the implicit
    Esc — it does not park the player in INSERT (the 2026-07-12 gap)."""
    dungeon = build_dungeon_selection_halls(0)
    room = dungeon.rooms[0]
    # stripe bay, blank floor at col 14: type on row 9, dot on row 10
    _drive(dungeon, _K('7j') + _K('i') + _K('zz') + [ESC] + _K('j.') + _K('l'),
           monkeypatch, finish=':q!\r')
    assert _row_text(room, 9).startswith('zz')
    assert _row_text(room, 10).startswith('zz'), "dot replayed text + Esc"


def test_dot_replays_ciw_with_its_cure(monkeypatch):
    """'.' after c{obj}+text repeats the whole change — the enclosure-era
    drill. ciw on the VU word, dot on the Vu word two rows down."""
    dungeon = build_dungeon_selection_halls(0)
    room = dungeon.rooms[0]
    # iw unlocks at the Word Enclosure (32) — drive as admin for the engine law
    _drive(dungeon, _K('jllll') + _K('ciw') + _K('x') + [ESC] + _K('2j.'),
           monkeypatch, finish=':q!\r', name='admin')
    assert _row_text(room, 3) == 'x'
    assert _row_text(room, 5) == 'x', "dot re-cut the word and retyped the cure"


def test_gU_takes_a_text_object(monkeypatch):
    """gUiw — the case operators accept text objects; sweeping the scrambled
    word to UPPER opens the first chamber (the 4-key rival to VU)."""
    dungeon = build_dungeon_selection_halls(0)
    room = dungeon.rooms[0]
    # iw unlocks at the Word Enclosure (32) — drive as admin for the engine law
    _drive(dungeon, _K('jllll') + _K('gUiw'), monkeypatch, finish=':q!\r',
           name='admin')
    assert room.cells[_bolt(0)[0]][_bolt(0)[1]] == CellType.FLOOR


def test_block_append_writes_past_the_right_edge(monkeypatch):
    """<C-v> A — block append: the typed run lands one past the block's right
    edge on EVERY selected row."""
    dungeon = build_dungeon_selection_halls(0)
    room = dungeon.rooms[0]
    # block over cols 15-16 ('sh'/'cl'/'re'), A appends at col 17
    _drive(dungeon, _K('7jll') + [CV] + _K('2jl') + _K('A') + _K('q') + [ESC],
           monkeypatch, finish=':q!\r')
    for r, w in zip(_SH_STRIPE_ROWS, room._sh_words['stripe']):
        assert _row_text(room, r).startswith(w[:2] + 'q'), _row_text(room, r)


def test_undo_rebars_bolt_and_seal(monkeypatch):
    dungeon = build_dungeon_selection_halls(0)
    room = dungeon.rooms[0]
    _drive(dungeon, _canon_keys(room)[:-2] + _K('l'), monkeypatch, finish=':q!\r')
    assert room.cells[_SH_EXIT[0]][_SH_EXIT[1]] == CellType.FLOOR, "the seal parted"

    dungeon = build_dungeon_selection_halls(0)
    room = dungeon.rooms[0]
    # uu: the walk pushes a snapshot; the second u reaches the final vbp —
    # ONE u refunds the whole visual paste-over
    _drive(dungeon, _canon_keys(room)[:-2] + _K('luu'), monkeypatch, finish=':q!\r')
    assert room.cells[_bolt(7)[0]][_bolt(7)[1]] == CellType.WALL, "re-bars"
    assert room.cells[_SH_EXIT[0]][_SH_EXIT[1]] == CellType.WALL, "re-seals"


def test_no_jump_lands_on_the_sealed_exit(monkeypatch):
    dungeon = build_dungeon_selection_halls(0)

    seen = {}
    orig = main._calc_stars
    def spy(won, budget, room_, player, level=''):
        seen['pos'] = (player.row, player.col)
        return orig(won, budget, room_, player, level)
    monkeypatch.setattr(main, '_calc_stars', spy)
    result = _drive(dungeon, _K('G$'), monkeypatch, finish=':wq\r')
    assert not result['won']
    assert seen['pos'] == (_SH_GATE, _SH_SPINE), seen
