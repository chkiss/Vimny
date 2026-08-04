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

"""The Word Enclosure (iw aw): proverbs by sense, the scar discrimination,
the dot gap, and the gallery's structure/karaoke discipline."""
import math

import pytest
from blessed.keyboard import Keystroke
from blessed import Terminal

import main
from vimny.engine.world import CellType
from vimny.content.levels import known_commands
from vimny.content import proverbs as pv
from vimny.generation.dungeon_gen import (
    build_dungeon_word_enclosure,
    _WE_ROWS, _WE_COLS, _WE_SPINE, _WE_SHAFT_SEPS, _WE_THROAT,
    _WE_GATE, _WE_BOLT0, _WE_EXIT, _WE_PAR, _WE_SPAWN, _WE_TEXT_MIN,
    _WE_C1_ROWS, _WE_C2_ROWS, _WE_C3_ROWS, _WE_C4_ROWS, _WE_C5_ROWS,
    _WE_C1_SLOTS, _WE_C2_SLOTS, _WE_C3_SLOTS, _WE_C4_SLOTS, _WE_C5_SLOTS,
    _WE_BAY_E,
)
from tests import SEEDS, cached_room

ESC = Keystroke('\x1b', name='KEY_ESCAPE')


def _room(seed=0):
    return cached_room('build_dungeon_word_enclosure', seed)


def _K(s):
    return [Keystroke(ch) for ch in s]


def _bolt(i):
    return (_WE_GATE, _WE_BOLT0 + i)


def _cures(room):
    return [m[2] for m in room._we_texts['misquotes']]


# The canonical tape (== room.answer with Esc placed): spawn drops onto the
# first intruder, the diw drill chains by dot, the two ciw cures mend the
# misquotes everyone knows, the daw seam with a dot reprise. Cures vary by
# seed but are all len 3 — par is column-anchored, not text-anchored.
def _canon_keys(room):
    ca, cb = _cures(room)
    return (_K('jdiwj.j.') + _K('2jciw') + _K(ca) + [ESC]
            + _K('jciw') + _K(cb) + [ESC] + _K('2jdawj.')
            + _K('2jdiWj.') + _K('l2jdaWj.') + _K('G$'))


# The leanest old-only rival (WITH its own best dot usage): de needs each
# intruder's START (an h per stagger), ce/dw pay the hh walk back from the
# mid-word landing. Wins at 1★.
def _piecewise_rival_keys(room):
    ca, cb = _cures(room)
    return (_K('jdejh.j.') + _K('2jhhce') + _K(ca) + [ESC]
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
    assert room.spawn_pos == _WE_SPAWN
    assert room.exit_pos == _WE_EXIT
    exit_ent = next(e for e in room.entities if e.kind == 'exit')
    assert (exit_ent.row, exit_ent.col) == _WE_EXIT and exit_ent.edit_immune


@pytest.mark.parametrize("seed", SEEDS)
def test_par_answer_budget(seed):
    room = _room(seed)
    assert room.par == _WE_PAR
    assert room.budget == math.ceil(_WE_PAR * 1.4)
    ca, cb = _cures(room)
    assert room.answer == (f'j diw j . j . 2j ciw {ca}<Esc> j ciw {cb}<Esc> '
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
def test_proverb_draw_anchors_and_landings(seed):
    """The corrupt word occupies its slot exactly (start col + length); the
    stagger keeps every dot-chain landing INSIDE the next corrupt word; the
    laid text is the saying itself, fitting the bay."""
    room = _room(seed)
    texts = room._we_texts
    slot_by_row = {r: (jl, s) for r, jl, s in
                   (_WE_C1_SLOTS + _WE_C3_SLOTS + _WE_C4_SLOTS + _WE_C5_SLOTS)}
    laid = {}
    for r, words, k, junk, start in texts['intruders']:
        jl, s = slot_by_row[r]
        assert start == s and len(junk) == jl
        assert 1 <= k <= len(words) - 1, "a word stands each side of the junk"
        t0 = start - (pv.prefix_len(words, k) + 1)
        assert t0 >= _WE_TEXT_MIN
        assert start + jl + len(' '.join(words[k:])) <= _WE_BAY_E
        assert _row_text(room, r) == \
            f"{pv.text_of(words[:k])} {junk} {pv.text_of(words[k:])}"
        laid[r] = (start, jl)
    for (r, s), (words, idx, cure) in zip(_WE_C2_SLOTS, texts['misquotes']):
        assert len(cure) == 3 and len(words[idx]) >= 3
        assert _row_text(room, r) == pv.text_of(words)
        laid[r] = (s, len(words[idx]))
    # C1 chain: each after-diw cursor (slot start) is inside the NEXT slot
    for ra, rb in zip(_WE_C1_ROWS, _WE_C1_ROWS[1:]):
        (sa, _la), (sb, lb) = laid[ra], laid[rb]
        assert sb <= sa < sb + lb, "the stagger keeps the dot chain alive"
    # every hopped-to corrupt word contains its shaft landing column
    shaft = dict(_WE_SHAFT_SEPS)
    for r, land in ((7, shaft[6]), (10, shaft[9]), (13, shaft[12]),
                    (16, shaft[15])):
        s, ln = laid[r]
        assert s <= land < s + ln, f"row {r}: landing {land} outside {s}+{ln}"
    # the hyphenated tokens are one WORD, three w-words
    for r, words, k, junk, start in texts['intruders']:
        if r in _WE_C4_ROWS + _WE_C5_ROWS:
            assert len(junk) == 9 and junk[4] == '-'
    # famous texts pairwise distinct; junk foreign to its own saying
    sayings = [words for _r, words, _k, _j, _s in texts['intruders']]
    assert len({' '.join(w) for w in sayings}) == len(sayings)
    for _r, words, _k, junk, _s in texts['intruders']:
        assert all(p not in words for p in junk.split('-'))
    # a cure door's target must not equal any laid saying (cross-open guard)
    cured = {' '.join(w[:i] + (c,) + w[i + 1:])
             for w, i, c in texts['misquotes']}
    assert not (cured & {' '.join(w) for w in sayings})


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

def _truth(room, r):
    """(prefix, suffix) of the intruder row's true saying."""
    for rr, words, k, _junk, _s in room._we_texts['intruders']:
        if rr == r:
            return pv.text_of(words[:k]), pv.text_of(words[k:])
    raise KeyError(r)


def test_diw_leaves_the_scar_and_daw_heals_the_seam(monkeypatch):
    """The discrimination, driven: diw on a C1 row leaves the double gap;
    daw there would heal the seam and the door must stay barred."""
    dungeon = build_dungeon_word_enclosure(0)
    room = dungeon.rooms[0]
    pre, suf = _truth(room, _WE_C1_ROWS[0])
    _drive(dungeon, _K('jdiw'), monkeypatch, finish=':q!\r')
    assert _row_text(room, _WE_C1_ROWS[0]) == f'{pre}  {suf}'

    dungeon = build_dungeon_word_enclosure(0)
    room = dungeon.rooms[0]
    _drive(dungeon, _K('jdaw'), monkeypatch, finish=':q!\r')
    assert _row_text(room, _WE_C1_ROWS[0]) == f'{pre} {suf}', "seam healed"
    assert room.cells[_bolt(0)[0]][_bolt(0)[1]] == CellType.WALL, \
        "the scar door does not accept the healed seam"


def test_dw_heals_the_seam_and_is_dead_for_the_drill(monkeypatch):
    """dw from the intruder's start eats the trailing gap — single gap, scar
    door stays shut (the reason the piecewise rival must use de)."""
    dungeon = build_dungeon_word_enclosure(0)
    room = dungeon.rooms[0]
    _drive(dungeon, _K('jdw'), monkeypatch, finish=':q!\r')
    assert room.cells[_bolt(0)[0]][_bolt(0)[1]] == CellType.WALL


def test_caw_fuses_the_cure_and_reads_false(monkeypatch):
    """caw on a misquote row eats a separator — the typed cure fuses into a
    neighbour and the exact-text door stays barred (u recovers)."""
    dungeon = build_dungeon_word_enclosure(0)
    room = dungeon.rooms[0]
    ca, _cb = _cures(room)
    _drive(dungeon, _K('jdiwj.j.2jcaw') + _K(ca) + [ESC],
           monkeypatch, finish=':q!\r')
    words, idx, _cure = room._we_texts['misquotes'][0]
    true = pv.text_of(words[:idx] + (ca,) + words[idx + 1:])
    assert _row_text(room, _WE_C2_ROWS[0]) != true, "fused — reads false"
    assert room.cells[_bolt(1)[0]][_bolt(1)[1]] == CellType.WALL


def test_diw_on_the_seam_rows_reads_false(monkeypatch):
    """The two-sided law from the other direction: diw where daw is needed
    leaves the scar and the seam door must not open."""
    dungeon = build_dungeon_word_enclosure(0)
    room = dungeon.rooms[0]
    ca, cb = _cures(room)
    bad = (_K('jdiwj.j.') + _K('2jciw') + _K(ca) + [ESC]
           + _K('jciw') + _K(cb) + [ESC] + _K('2jdiwj.'))
    _drive(dungeon, bad, monkeypatch, finish=':q!\r')
    assert room.cells[_bolt(2)[0]][_bolt(2)[1]] == CellType.WALL


def test_diw_on_a_mixed_token_kills_a_subword_and_reads_false(monkeypatch):
    """The CLASS lesson: iw stops at the hyphen — half the token remains and
    the scar door stays barred; only iW takes the whole WORD."""
    dungeon = build_dungeon_word_enclosure(0)
    room = dungeon.rooms[0]
    ca, cb = _cures(room)
    upto_c4 = (_K('jdiwj.j.') + _K('2jciw') + _K(ca) + [ESC]
               + _K('jciw') + _K(cb) + [ESC] + _K('2jdawj.') + _K('2j'))
    _drive(dungeon, upto_c4 + _K('diw'), monkeypatch, finish=':q!\r')
    assert '-' in _row_text(room, _WE_C4_ROWS[0]), "the hyphen half remains"
    assert room.cells[_bolt(3)[0]][_bolt(3)[1]] == CellType.WALL


def test_dW_heals_the_seam_and_is_dead_for_the_token_scar(monkeypatch):
    """dW eats the trailing gap — single gap where the C4 door wants the
    double-gap scar (the reason the WORD-family rival must use dE)."""
    dungeon = build_dungeon_word_enclosure(0)
    room = dungeon.rooms[0]
    ca, cb = _cures(room)
    upto_c4 = (_K('jdiwj.j.') + _K('2jciw') + _K(ca) + [ESC]
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
    # uu: the walk pushes a snapshot; the second u reaches the dotted daW
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
