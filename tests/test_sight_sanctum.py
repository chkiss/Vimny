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

"""The Sight Sanctum (v + operators on the selection): structure, forcing law,
seal/bolt discipline, karaoke tape, and the per-token visual gate."""
import math

import pytest
from blessed.keyboard import Keystroke
from blessed import Terminal

import vimny.game as main
from vimny.engine.command_guard import action_allowed
from vimny.engine.vim_parser import parse
from vimny.engine.modes import Mode
from vimny.engine.world import CellType
from vimny.engine.search import _match_positions
from vimny.content.levels import known_commands
from vimny.generation.dungeon_gen import (
    build_dungeon_sight_sanctum,
    _SS_ROWS, _SS_COLS, _SS_SPINE, _SS_BAY_W, _SS_BAY_E, _SS_SPAWN,
    _SS_GATE, _SS_BOLT0, _SS_EXIT, _SS_PAR, _ss_answer,
)
from tests import SEEDS, cached_room, door_targets

ESC = Keystroke('\x1b', name='KEY_ESCAPE')


def _room(seed=0):
    return cached_room('build_dungeon_sight_sanctum', seed)


def _K(s):
    return [Keystroke(ch) for ch in s]


def _bolt(i):
    return (_SS_GATE, _SS_BOLT0 + i)


def _letters(room):
    """The seed's three tape letters: the two t-targets and the seal search."""
    w = room._ss_words
    return w['cut'][1][0], w['word'][1][0], w['seal'][1][0]


# The canonical tape (== room.answer with Esc placed): select first, act
# second — the spawn drops onto the first blight, anchor-aligned down the
# light shaft, so every hop is a plain {n}j. Letters drawn per seed.
def _canon_keys(room):
    a, b, x = _letters(room)
    return (_K(f'jv2jt{a}d') + _K(f'4jv2jt{b}c') + _K('s') + [ESC]
            + _K('4jvje~') + _K('3jv') + _K(f'/{x}\r') + _K('hd') + _K('G$'))


# The leanest old-only rival (cheese-audited): middle blight rows are never
# cleared — doors check only the target rows — so no dd at all: D for heads,
# ^dt{ch} for tails, i+s for the typed cure, count-~ for the flipped spans.
# Wins — inside the standard budget — but over par: 1 star.
def _piecewise_rival_keys(room):
    a, b, x = _letters(room)
    _g1, f1, f2, _g2 = room._ss_words['case']
    return (_K(f'jD2j^dt{a}') + _K('4l2jD') + _K('is') + [ESC]
            + _K(f'2j^dt{b}') + _K(f'4l2j{len(f1)}~j^{len(f2)}~')
            + _K(f'hh2jD2j^dt{x}') + _K('G$'))


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
    return main.run_dungeon(term, 'sight_sanctum', {}, player_name=name,
                            _dungeon=dungeon)


def _drive_spent(keys, monkeypatch, seed=0):
    box = {}
    orig = main._calc_stars
    monkeypatch.setattr(main, '_calc_stars',
                        lambda won, budget, room, player, level='':
                            (box.__setitem__('spent', budget.spent),
                             orig(won, budget, room, player, level))[1])
    result = _drive(build_dungeon_sight_sanctum(seed), keys, monkeypatch)
    return result['won'], box.get('spent')


def test_word_chamber_bolt_and_message_land_on_the_esc(monkeypatch):
    """Playtest 2026-07-20: the Word chamber's `v…c s` opens its bolt on the
    Esc that commits the change (Vim-true — the change lands on Esc), AND the
    'the bolt grinds back' message surfaces on THAT render (the insert-Esc path
    used to open the gate but never surface the pooled message)."""
    dungeon = build_dungeon_sight_sanctum(2)      # seed 2: word tail 'make…'
    room = dungeon.rooms[0]
    a, b, _x = _letters(room)
    toks = _K(f'jv2jt{a}d') + _K(f'4jv2jt{b}c') + _K('s') + [ESC] + _K('l')
    n_esc = len(_K(f'jv2jt{a}d') + _K(f'4jv2jt{b}c') + _K('s')) + 1   # index of the Esc
    keys = toks + _K(':wq\r')
    msgs = []
    monkeypatch.setattr(main, 'render_all',
                        lambda t, dg, pl, bg, message='', *a, **k: msgs.append(message))
    monkeypatch.setattr(main.time, 'sleep', lambda *a, **k: None)
    for anim in ('_fireworks_animation', '_win_animation', '_starfield_victory',
                 '_heart_container_animation', '_unlock_animation',
                 '_void_fall_animation', '_drown_animation'):
        monkeypatch.setattr(main, anim, lambda *a, **k: None)
    monkeypatch.setattr(Terminal, 'height', property(lambda self: 41))
    term = Terminal()
    it = iter(keys)
    esc_bolt = {}
    calls = {'n': 0}

    def _inkey(*a, **k):
        if calls['n'] == n_esc + 1:   # `l` is being fetched → the Esc fully processed
            esc_bolt['v'] = room.cells[_SS_GATE][_SS_BOLT0 + 1]
        calls['n'] += 1
        return next(it, Keystroke(''))
    monkeypatch.setattr(term, 'inkey', _inkey)
    main.run_dungeon(term, 'sight_sanctum', {}, player_name='Scribe', _dungeon=dungeon)
    assert esc_bolt.get('v') == CellType.FLOOR, "the Word bolt opens on the Esc"
    # the grind message surfaced on some render (the Esc turn), not silently
    assert any('grinds back' in m for m in msgs), \
        "the 'bolt grinds back' message must surface, not be clobbered"


# ── dungeon structure ─────────────────────────────────────────────────────────

@pytest.mark.parametrize("seed", SEEDS)
def test_layout_and_identity(seed):
    room = _room(seed)
    assert (room.rows, room.cols) == (_SS_ROWS, _SS_COLS)
    assert room.spawn_pos == _SS_SPAWN
    assert room.exit_pos == _SS_EXIT
    exit_ent = next(e for e in room.entities if e.kind == 'exit')
    assert (exit_ent.row, exit_ent.col) == _SS_EXIT and exit_ent.edit_immune


@pytest.mark.parametrize("seed", SEEDS)
def test_par_answer_budget(seed):
    room = _room(seed)
    assert room.par == _SS_PAR
    assert room.budget == math.ceil(_SS_PAR * 1.4)
    assert room.answer == _ss_answer(room._ss_words)


@pytest.mark.parametrize("seed", SEEDS)
def test_exit_and_bolts_start_sealed(seed):
    """The FINAL SEAL law: bolts and exit are STONE until their text holds."""
    room = _room(seed)
    for i in range(4):
        assert room.cells[_bolt(i)[0]][_bolt(i)[1]] == CellType.WALL
    assert room.cells[_SS_EXIT[0]][_SS_EXIT[1]] == CellType.WALL


@pytest.mark.parametrize("seed", SEEDS)
def test_spine_is_every_rows_first_standable(seed):
    """The teleport audit: no jump may land east of the spine — every floor
    row's westmost passable cell is the spine (except the chest nook row)."""
    room = _room(seed)
    for r in range(room.rows):
        cols = [c for c in range(room.cols) if room.is_passable(r, c)]
        if cols:
            assert cols[0] == _SS_SPINE, f"row {r} first standable {cols[0]}"


@pytest.mark.parametrize("seed", SEEDS)
def test_light_shaft_pierces_separators_but_not_the_throat(seed):
    """The sight-line: one floor cell at the anchor column through each bay
    separator (the {n}j hops ride it) — but the throat row stays spine-only,
    so the gate row is reachable only along the spine (teleport audit)."""
    from vimny.generation.dungeon_gen import _SS_SHAFT, _SS_THROAT
    room = _room(seed)
    for r in (6, 10, 13):
        assert room.cells[r][_SS_SHAFT] == CellType.FLOOR
    assert room.cells[_SS_THROAT][_SS_SHAFT] == CellType.WALL


def test_bolt_opens_the_instant_the_strike_lands(monkeypatch):
    """The insert-Esc rule for visual ops: the Cut chamber's d opens its bolt
    THIS turn — no one-key lag before the banner/bolt."""
    dungeon = build_dungeon_sight_sanctum(0)
    room = dungeon.rooms[0]
    a, _b, _x = _letters(room)
    _drive(dungeon, _K(f'jv2jt{a}d'), monkeypatch, finish=':q!\r')
    assert room.cells[_bolt(0)[0]][_bolt(0)[1]] == CellType.FLOOR


@pytest.mark.parametrize("seed", SEEDS)
def test_seal_initial_is_pristine_level_wide(seed):
    """The Seal's search anchor: the tail's initial occurs in exactly one
    FLOOR position (its own) — the plaque copy is sealed in the wall, which
    search skips — so /{x}<CR> has one landing."""
    room = _room(seed)
    _a, _b, x = _letters(room)
    positions = _match_positions(room, x)
    from vimny.generation.dungeon_gen import _SS_TAIL0
    # every floor match lives inside the tail itself (the initial may recur
    # within its own text — /{x}<CR> still lands on the head), none elsewhere
    assert positions and positions[0] == (16, _SS_TAIL0), (x, positions)
    assert all(r == 16 and c >= _SS_TAIL0 for r, c in positions), (x, positions)


@pytest.mark.parametrize("seed", SEEDS)
def test_case_rows_read_flanks_sound_and_middles_flipped(seed):
    """The saying's middle segments stand UPPER between lowercase flanks —
    and the whole reading is the saying, split across the two rows."""
    room = _room(seed)
    g1, f1, f2, g2 = room._ss_words['case']
    assert main._wla_floor_text(room, 11).strip() == f'{g1} {f1.upper()}'
    assert main._wla_floor_text(room, 12).strip() == f'{f2.upper()} {g2}'


def test_no_chest_in_the_sanctum():
    # playtest 2026-07-16: the spawn-nook chest read as clutter — removed
    room = _room(0)
    assert not any(e.kind == 'chest_scroll' for e in room.entities)


def test_curriculum_teaches_visual_and_visual_op():
    known = known_commands('sight_sanctum')
    assert 'visual' in known and 'visual_op' in known
    # and neither sibling mode leaks in early (the per-token gate)
    assert 'visual_line' not in known and 'visual_block' not in known


def test_word_draw_constraints_hold_across_many_seeds():
    """The vocabulary lint, 300 seeds: every draw builds; the seal initial is
    floor-unique (one /{x} landing); every door target is distinct."""
    from vimny.generation.dungeon_gen import _SS_TAIL0
    for seed in range(300):
        room = build_dungeon_sight_sanctum(seed).rooms[0]
        _a, _b, x = _letters(room)
        positions = _match_positions(room, x)
        assert positions[0] == (16, _SS_TAIL0), (seed, x, positions)
        assert all(r == 16 and c >= _SS_TAIL0 for r, c in positions), (seed, x)
        targets = [t for ts in door_targets(room) for t in ts]
        assert len(set(targets)) == len(targets) == 8, (seed, targets)


# ── the per-token visual gate ─────────────────────────────────────────────────

def test_v_gates_but_V_and_block_stay_locked():
    known = known_commands('sight_sanctum')
    v_action, _ = parse('v', Mode.NORMAL)
    V_action, _ = parse('V', Mode.NORMAL)
    b_action, _ = parse('\x16', Mode.NORMAL)
    assert action_allowed(v_action, known)
    assert not action_allowed(V_action, known), "V is the Selection Halls' own"
    assert not action_allowed(b_action, known), "<C-v> is the Selection Halls' own"
    prev = known_commands('warden_scrivener')
    assert not action_allowed(v_action, prev), "v unlearned before the Sanctum"


# ── the forcing law, driven ──────────────────────────────────────────────────

@pytest.mark.parametrize("seed", SEEDS)
def test_full_sight_route_wins_par_perfect(seed, monkeypatch):
    dungeon = build_dungeon_sight_sanctum(seed)
    room = dungeon.rooms[0]
    result = _drive(dungeon, _canon_keys(room), monkeypatch)
    assert result['won'] and result['stars'] == 2, result
    for i in range(4):
        assert room.cells[_bolt(i)[0]][_bolt(i)[1]] == CellType.FLOOR


def test_canonical_route_costs_exactly_par(monkeypatch):
    room = _room(0)
    won, spent = _drive_spent(_canon_keys(room), monkeypatch)
    assert won and spent == _SS_PAR, (won, spent)


@pytest.mark.parametrize("seed", SEEDS)
def test_piecewise_route_wins_at_one_star(seed, monkeypatch):
    """THE LAW, driven: the no-visual D/dd/^dt/cc route WINS — inside the
    standard budget — but over par: 1 star. The sight is forced by PAR."""
    dungeon = build_dungeon_sight_sanctum(seed)
    result = _drive(dungeon, _piecewise_rival_keys(dungeon.rooms[0]), monkeypatch)
    assert result['won'] and result['stars'] == 1, result


def test_admin_karaoke_tape_tracks_to_the_end(monkeypatch):
    """The answer is the literal tape: driving it as admin never diverges and
    consumes every char (<CR> marks the search Enter; Esc is skipped)."""
    dungeon = build_dungeon_sight_sanctum(0)
    room = dungeon.rooms[0]
    _drive(dungeon, _canon_keys(room), monkeypatch, name='admin')
    assert not room.answer_diverged
    assert room.answer_pos == len(room.answer.replace(' ', ''))


# ── seal / bolt discipline ───────────────────────────────────────────────────

def test_undo_rebars_bolt_and_seal(monkeypatch):
    dungeon = build_dungeon_sight_sanctum(0)
    room = dungeon.rooms[0]
    _drive(dungeon, _canon_keys(room)[:-2] + _K('l'), monkeypatch, finish=':q!\r')
    assert room.cells[_bolt(3)[0]][_bolt(3)[1]] == CellType.FLOOR
    assert room.cells[_SS_EXIT[0]][_SS_EXIT[1]] == CellType.FLOOR, "the seal parted"

    dungeon = build_dungeon_sight_sanctum(0)
    room = dungeon.rooms[0]
    # uu: the walk pushes its own snapshot; the second u reaches the Seal's d —
    # one u refunds the WHOLE selection (anchor + spent ride the snapshot)
    _drive(dungeon, _canon_keys(room)[:-2] + _K('luu'), monkeypatch, finish=':q!\r')
    assert room.cells[_bolt(3)[0]][_bolt(3)[1]] == CellType.WALL, "re-bars"
    assert room.cells[_SS_EXIT[0]][_SS_EXIT[1]] == CellType.WALL, "re-seals"


def test_linewise_cut_that_eats_a_kept_word_is_a_dead_route(monkeypatch):
    """The anti-cheese: dj on the Cut chamber's head row eats 'veil' — the
    exact-text door must NOT open however much blight also died."""
    dungeon = build_dungeon_sight_sanctum(0)
    room = dungeon.rooms[0]
    _drive(dungeon, _K('jdj'), monkeypatch, finish=':q!\r')
    gr = room.exit_pos[0]           # dj collapsed rows — the gate rode the shift
    assert room.cells[gr][_SS_BOLT0] == CellType.WALL
    assert room.cells[gr][room.exit_pos[1]] == CellType.WALL


def test_half_cleared_chamber_stays_shut(monkeypatch):
    """Exact-row matching: clearing only the head row ('veil' true, 'sill'
    still buried) leaves the bolt barred."""
    dungeon = build_dungeon_sight_sanctum(0)
    room = dungeon.rooms[0]
    _drive(dungeon, _K('jD'), monkeypatch, finish=':q!\r')
    assert room.cells[_bolt(0)[0]][_bolt(0)[1]] == CellType.WALL


def test_linewise_case_toggle_is_a_dead_route(monkeypatch):
    """The Case chamber's flanks: g~j flips the sound flanking words too, so
    the whole-lines toggle reads false — per-row charwise v~ is the cure."""
    dungeon = build_dungeon_sight_sanctum(0)
    room = dungeon.rooms[0]
    _drive(dungeon, _K('9jg~j'), monkeypatch, finish=':q!\r')
    assert room.cells[_bolt(2)[0]][_bolt(2)[1]] == CellType.WALL


def test_visual_case_toggle_spares_the_guard_words(monkeypatch):
    """Vim-true multi-row charwise ~: only the selected span flips — 'dim'
    (west of the anchor, top row) and 'ash' (east of the cursor, bottom row)
    keep their case, and the bolt opens."""
    dungeon = build_dungeon_sight_sanctum(0)
    room = dungeon.rooms[0]
    a, b, _x = _letters(room)
    _drive(dungeon, _K(f'jv2jt{a}d') + _K(f'4jv2jt{b}c') + _K('s') + [ESC]
           + _K('4jvje~'), monkeypatch, finish=':q!\r')
    assert room.cells[_bolt(2)[0]][_bolt(2)[1]] == CellType.FLOOR


def test_spine_detour_nav_costs_more_than_par(monkeypatch):
    """The nav-golf audit: routing bay-to-bay via the spine (0 + {n}j + e l)
    instead of the light shaft loses to the tape — par IS the cheapest nav."""
    room = _room(0)
    a, b, x = _letters(room)
    spine_variant = (_K(f'jv2jt{a}d') + _K(f'4jv2jt{b}c') + _K('s')
                     + [ESC] + _K('04j17l') + _K('vje~') + _K('3jv')
                     + _K(f'/{x}\r') + _K('hd') + _K('G$'))
    won, spent = _drive_spent(spine_variant, monkeypatch)
    assert won and spent > _SS_PAR, (won, spent)


def test_no_jump_lands_on_the_sealed_exit(monkeypatch):
    """G / $ discipline while the seal holds: G lands the gate row ON the
    spine, and $ stops at the first shut bolt."""
    dungeon = build_dungeon_sight_sanctum(0)
    room = dungeon.rooms[0]

    seen = {}
    orig = main._calc_stars
    def spy(won, budget, room_, player, level=''):
        seen['pos'] = (player.row, player.col)
        return orig(won, budget, room_, player, level)
    monkeypatch.setattr(main, '_calc_stars', spy)
    result = _drive(dungeon, _K('G$'), monkeypatch, finish=':wq\r')
    assert not result['won']
    assert seen['pos'] == (_SS_GATE, _SS_SPINE), seen
