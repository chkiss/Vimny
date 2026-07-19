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

"""The Bracket Enclosure (i( a(): proverbs by sense, the husk/gem/scar
discrimination, and the gallery's structure/karaoke discipline."""
import math

import pytest
from blessed.keyboard import Keystroke
from blessed import Terminal

import main
from engine.world import CellType
from content.levels import known_commands
from content import proverbs as pv
from generation.dungeon_gen import (
    build_dungeon_bracket_enclosure,
    _BE_ROWS, _BE_COLS, _BE_SPINE, _BE_SHAFT_SEPS, _BE_THROAT,
    _BE_GATE, _BE_BOLT0, _BE_EXIT, _BE_PAR, _BE_TEXT_MIN, _BE_BAY_E,
    _BE_C1_ROWS, _BE_C2_ROWS, _BE_C3_ROWS,
    _BE_C1_SLOTS, _BE_C2_SLOTS, _BE_C3_SLOTS,
)
from tests import SEEDS, cached_room

ESC = Keystroke('\x1b', name='KEY_ESCAPE')


def _room(seed=0):
    return cached_room('build_dungeon_bracket_enclosure', seed)


def _K(s):
    return [Keystroke(ch) for ch in s]


def _bolt(i):
    return (_BE_GATE, _BE_BOLT0 + i)


def _cures(room):
    return [m[2] for m in room._be_texts['misquotes']]


# The canonical tape (== room.answer with Esc placed): the % entry (j %
# scans to the '(' and lands on its match — user-found nav golf, and
# length-independent whatever the proverb's prefix), pry the junk stones
# (di( chained by dot), recut the miscut gems (ci( + the famous word),
# tear the fittings out (da( with a dot reprise). 33 keys.
def _canon_keys(room):
    ca, cb = _cures(room)
    return (_K('j%di(j.j.') + _K('2jci(') + _K(ca) + [ESC]
            + _K('jci(') + _K(cb) + [ESC] + _K('2jda(j.') + _K('G$'))


# The leanest old-only rival (WITH its own best dot usage), anchor-relative
# so it is seed-invariant: F( l finds each stone start from the % landing,
# dt) pries, ct) recuts (h-walks back from the mid-stone landings), F( dE
# tears fittings ('(junk)' is one WORD). Wins at 1★.
def _piecewise_rival_keys(room):
    ca, cb = _cures(room)
    return (_K('j%F(ldt)jh.j.') + _K('2jhct)') + _K(ca) + [ESC]
            + _K('jhhct)') + _K(cb) + [ESC] + _K('2jF(dEjh.') + _K('G$'))


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
    return main.run_dungeon(term, 'bracket_enclosure', {}, player_name=name,
                            _dungeon=dungeon)


def _drive_spent(keys, monkeypatch, seed=0):
    box = {}
    orig = main._calc_stars
    monkeypatch.setattr(main, '_calc_stars',
                        lambda won, budget, room, player, level='':
                            (box.__setitem__('spent', budget.spent),
                             orig(won, budget, room, player, level))[1])
    result = _drive(build_dungeon_bracket_enclosure(seed), keys, monkeypatch)
    return result['won'], box.get('spent')


def _row_text(room, r):
    out = ''
    for c in range(room.cols):
        if not room.is_passable(r, c):
            continue
        ru = room.char_run_at(r, c)
        out += ru.symbols[c - ru.col] if ru else ' '
    return out.strip()


def _truth(room, r):
    for rr, words, k, _junk, _f in room._be_texts['intruders']:
        if rr == r:
            return pv.text_of(words[:k]), pv.text_of(words[k:])
    raise KeyError(r)


# ── dungeon structure ─────────────────────────────────────────────────────────

@pytest.mark.parametrize("seed", SEEDS)
def test_layout_and_identity(seed):
    room = _room(seed)
    assert (room.rows, room.cols) == (_BE_ROWS, _BE_COLS)
    assert room.spawn_pos == (2, _BE_SPINE)
    assert room.exit_pos == _BE_EXIT
    exit_ent = next(e for e in room.entities if e.kind == 'exit')
    assert (exit_ent.row, exit_ent.col) == _BE_EXIT and exit_ent.edit_immune


@pytest.mark.parametrize("seed", SEEDS)
def test_par_answer_budget(seed):
    room = _room(seed)
    assert room.par == _BE_PAR
    assert room.budget == math.ceil(_BE_PAR * 1.4)
    ca, cb = _cures(room)
    assert room.answer == (f'j % di( j . j . 2j ci( {ca} j ci( {cb} '
                           f'2j da( j . G $')


@pytest.mark.parametrize("seed", SEEDS)
def test_exit_and_bolts_start_sealed(seed):
    room = _room(seed)
    for i in range(3):
        assert room.cells[_bolt(i)[0]][_bolt(i)[1]] == CellType.WALL
    assert room.cells[_BE_EXIT[0]][_BE_EXIT[1]] == CellType.WALL


@pytest.mark.parametrize("seed", SEEDS)
def test_spine_is_every_rows_first_standable(seed):
    room = _room(seed)
    for r in range(room.rows):
        cols = [c for c in range(room.cols) if room.is_passable(r, c)]
        if cols:
            assert cols[0] == _BE_SPINE, f"row {r} first standable {cols[0]}"


@pytest.mark.parametrize("seed", SEEDS)
def test_light_shaft_pierces_separators_but_not_the_throat(seed):
    room = _room(seed)
    for r, c in _BE_SHAFT_SEPS:
        assert room.cells[r][c] == CellType.FLOOR
        assert room.cells[_BE_THROAT][c] == CellType.WALL


@pytest.mark.parametrize("seed", SEEDS)
def test_proverb_draw_anchors_and_landings(seed):
    """The '(' sits at its slot exactly; junk lengths fixed; the stagger
    keeps the di( chain and every hop inside the next stone; the laid text
    is the saying with its aside; sayings distinct, junk foreign."""
    room = _room(seed)
    texts = room._be_texts
    slot_by_row = {r: (jl, f) for r, jl, f in (_BE_C1_SLOTS + _BE_C3_SLOTS)}
    laid = {}
    for i, (r, words, k, junk, fit) in enumerate(texts['intruders']):
        jl, f = slot_by_row[r]
        assert fit == f and len(junk) == jl
        if r == _BE_C1_ROWS[0]:
            assert ' ' in junk, "row 3's stone is TWO WORDS (diw kills half)"
        t0 = fit - (pv.prefix_len(words, k) + 1)
        assert t0 >= _BE_TEXT_MIN
        assert fit + jl + 2 + len(' '.join(words[k:])) <= _BE_BAY_E
        assert _row_text(room, r) == \
            f"{pv.text_of(words[:k])} ({junk}) {pv.text_of(words[k:])}"
        laid[r] = (fit + 1, jl)                      # stone start, len
    for (r, f), (words, idx, cure) in zip(_BE_C2_SLOTS, texts['misquotes']):
        assert len(cure) == 3 and len(words[idx]) >= 3
        expect = (f"{pv.text_of(words[:idx])} ({words[idx]})"
                  + (f" {pv.text_of(words[idx + 1:])}" if words[idx + 1:] else ''))
        assert _row_text(room, r) == expect
        laid[r] = (f + 1, len(words[idx]))
    # C1 chain: each after-di( cursor (stone start) is inside the NEXT stone
    for ra, rb in zip(_BE_C1_ROWS, _BE_C1_ROWS[1:]):
        (sa, _la), (sb, lb) = laid[ra], laid[rb]
        assert sb <= sa < sb + lb, "the stagger keeps the dot chain alive"
    # every hopped-to stone contains its shaft landing column
    shaft = dict(_BE_SHAFT_SEPS)
    for r, land in ((_BE_C2_ROWS[0], shaft[6]), (_BE_C3_ROWS[0], shaft[9])):
        s, ln = laid[r]
        assert s <= land < s + ln, f"row {r}: landing {land} outside {s}+{ln}"
    sayings = [words for _r, words, _k, _j, _f in texts['intruders']]
    assert len({' '.join(w) for w in sayings}) == len(sayings)
    for _r, words, _k, junk, _f in texts['intruders']:
        assert all(p not in words for p in junk.split(' '))


def test_curriculum_and_gating():
    known = known_commands('bracket_enclosure')
    assert 'i(' in known and 'a(' in known
    prev = known_commands('word_enclosure')
    assert 'i(' not in prev and 'a(' not in prev


# ── the forcing law, driven ──────────────────────────────────────────────────

@pytest.mark.parametrize("seed", SEEDS)
def test_full_setting_route_wins_par_perfect(seed, monkeypatch):
    dungeon = build_dungeon_bracket_enclosure(seed)
    room = dungeon.rooms[0]
    result = _drive(dungeon, _canon_keys(room), monkeypatch)
    assert result['won'] and result['stars'] == 2, result
    for i in range(3):
        assert room.cells[_bolt(i)[0]][_bolt(i)[1]] == CellType.FLOOR


def test_canonical_route_costs_exactly_par(monkeypatch):
    room = _room(0)
    won, spent = _drive_spent(_canon_keys(room), monkeypatch)
    assert won and spent == _BE_PAR, (won, spent)


@pytest.mark.parametrize("seed", SEEDS)
def test_piecewise_route_wins_at_one_star(seed, monkeypatch):
    """THE LAW, driven: the no-bracket-object route (dt)/ct)/F(dE with its
    own best dot usage) WINS — inside the standard budget — but over par."""
    dungeon = build_dungeon_bracket_enclosure(seed)
    result = _drive(dungeon, _piecewise_rival_keys(dungeon.rooms[0]), monkeypatch)
    assert result['won'] and result['stars'] == 1, result


def test_admin_karaoke_tape_tracks_to_the_end(monkeypatch):
    dungeon = build_dungeon_bracket_enclosure(0)
    room = dungeon.rooms[0]
    _drive(dungeon, _canon_keys(room), monkeypatch, name='admin')
    assert not room.answer_diverged
    assert room.answer_pos == len(room.answer.replace(' ', ''))


# ── the chambers' laws ───────────────────────────────────────────────────────

def test_di_paren_keeps_the_husk_and_da_paren_leaves_the_scar(monkeypatch):
    """The discrimination, driven both ways on row 3."""
    dungeon = build_dungeon_bracket_enclosure(0)
    room = dungeon.rooms[0]
    pre, suf = _truth(room, _BE_C1_ROWS[0])
    _drive(dungeon, _K('j%di('), monkeypatch, finish=':q!\r')
    assert _row_text(room, _BE_C1_ROWS[0]) == f'{pre} () {suf}', "the husk stays"

    dungeon = build_dungeon_bracket_enclosure(0)
    room = dungeon.rooms[0]
    _drive(dungeon, _K('j%da('), monkeypatch, finish=':q!\r')
    assert _row_text(room, _BE_C1_ROWS[0]) == f'{pre}  {suf}', "the scar"
    assert room.cells[_bolt(0)[0]][_bolt(0)[1]] == CellType.WALL, \
        "the husk door does not accept the scar"


def test_diw_kills_half_the_two_word_stone(monkeypatch):
    """The object-vs-object lesson: row 3's stone is two words — diw takes
    one and the husk door stays barred; only di( takes the delimited span."""
    dungeon = build_dungeon_bracket_enclosure(0)
    room = dungeon.rooms[0]
    _drive(dungeon, _K('j%bdiw'), monkeypatch, finish=':q!\r')
    assert '(' in _row_text(room, _BE_C1_ROWS[0])
    assert room.cells[_bolt(0)[0]][_bolt(0)[1]] == CellType.WALL


def test_ca_paren_tears_the_setting_and_reads_false(monkeypatch):
    """ca( + cure on a C2 row loses the setting — the door wants the cure IN
    parens (u recovers)."""
    dungeon = build_dungeon_bracket_enclosure(0)
    room = dungeon.rooms[0]
    ca, _cb = _cures(room)
    _drive(dungeon, _K('j%di(j.j.2jca(') + _K(ca) + [ESC],
           monkeypatch, finish=':q!\r')
    assert '(' not in _row_text(room, _BE_C2_ROWS[0])
    assert room.cells[_bolt(1)[0]][_bolt(1)[1]] == CellType.WALL


def test_di_paren_on_the_fitting_rows_reads_false(monkeypatch):
    """di( where da( is needed leaves the husk — the scar door stays shut."""
    dungeon = build_dungeon_bracket_enclosure(0)
    room = dungeon.rooms[0]
    ca, cb = _cures(room)
    bad = (_K('j%di(j.j.') + _K('2jci(') + _K(ca) + [ESC]
           + _K('jci(') + _K(cb) + [ESC] + _K('2jdi(j.'))
    _drive(dungeon, bad, monkeypatch, finish=':q!\r')
    assert room.cells[_bolt(2)[0]][_bolt(2)[1]] == CellType.WALL


def test_undo_rebars_bolt_and_seal(monkeypatch):
    dungeon = build_dungeon_bracket_enclosure(0)
    room = dungeon.rooms[0]
    _drive(dungeon, _canon_keys(room)[:-2] + _K('l'), monkeypatch, finish=':q!\r')
    assert room.cells[_BE_EXIT[0]][_BE_EXIT[1]] == CellType.FLOOR, "the seal parted"

    dungeon = build_dungeon_bracket_enclosure(0)
    room = dungeon.rooms[0]
    _drive(dungeon, _canon_keys(room)[:-2] + _K('luu'), monkeypatch, finish=':q!\r')
    assert room.cells[_bolt(2)[0]][_bolt(2)[1]] == CellType.WALL, "re-bars"
    assert room.cells[_BE_EXIT[0]][_BE_EXIT[1]] == CellType.WALL, "re-seals"


def test_no_jump_lands_on_the_sealed_exit(monkeypatch):
    dungeon = build_dungeon_bracket_enclosure(0)
    seen = {}
    orig = main._calc_stars
    def spy(won, budget, room_, player, level=''):
        seen['pos'] = (player.row, player.col)
        return orig(won, budget, room_, player, level)
    monkeypatch.setattr(main, '_calc_stars', spy)
    result = _drive(dungeon, _K('G$'), monkeypatch, finish=':wq\r')
    assert not result['won']
    assert seen['pos'] == (_BE_GATE, _BE_SPINE), seen
