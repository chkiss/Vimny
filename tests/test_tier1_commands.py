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

"""The 2026-07-13 engine-audit tier-1 features: Y, X, visual p/r/J, the
implicit ' mark ('' / ``), :{n} go-to-line, and the ZZ/ZQ relic.

Y and X are engine-ready but LOCKED behind their own tokens (the D/C rule) —
ungated they would golf the Beacon Tiers' (yy) and Waypoint Sanctum's (h x)
pars. Driven here as admin / via extras."""
import pytest
from blessed.keyboard import Keystroke
from blessed import Terminal

import main
from vimny.engine.vim_parser import parse
from vimny.engine.modes import Mode
from vimny.engine.command_guard import action_allowed
from vimny.engine.world import CellType
from vimny.generation.dungeon_gen import (build_dungeon_selection_halls,
                                    _SH_SPINE, _SH_CASE_ROWS, _SH_STRIPE_ROWS)

ESC = Keystroke('\x1b', name='KEY_ESCAPE')


def _K(s):
    return [Keystroke(ch) for ch in s]


def _drive(keys, monkeypatch, finish=':q!\r', name='Scribe', progress=None,
           seed=0):
    dungeon = build_dungeon_selection_halls(seed)
    room = dungeon.rooms[0]
    keys = list(keys) + (_K(finish) if finish else [])
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
    result = main.run_dungeon(term, 'selection_halls', progress or {},
                              player_name=name, _dungeon=dungeon)
    return result, room


def _row_text(room, r):
    out = ''
    for c in range(room.cols):
        if not room.is_passable(r, c):
            continue
        ru = room.char_run_at(r, c)
        out += ru.symbols[c - ru.col] if ru else ' '
    return out.strip()


# ── Y and X: engine-ready, own-token locked ──────────────────────────────────

def test_Y_parses_as_linewise_yank_with_its_own_gate():
    action, _ = parse('Y', Mode.NORMAL)
    assert action == {'type': 'operator', 'op': 'y', 'motion': 'line',
                      'count': 1, 'shorthand': 'Y'}
    assert not action_allowed(action, ['y']), "Y is its own lesson, not y's"
    assert action_allowed(action, ['y', 'Y'])


def test_X_parses_as_delete_before_with_its_own_gate():
    action, _ = parse('X', Mode.NORMAL)
    assert action['type'] == 'interact' and action.get('before')
    assert not action_allowed(action, ['x']), "X is its own lesson, not x's"
    assert action_allowed(action, ['x', 'X'])


def test_Y_yanks_the_line_and_p_duplicates_it(monkeypatch):
    dungeon_rows = build_dungeon_selection_halls(0).rooms[0].rows
    _res, room = _drive(_K('jYp'), monkeypatch, name='admin')
    assert room.rows == dungeon_rows + 1, "Y = yy: linewise clip, p opens a row"
    assert _row_text(room, _SH_CASE_ROWS[0]) == _row_text(room, _SH_CASE_ROWS[0] + 1)


def test_X_deletes_before_the_cursor(monkeypatch):
    _res, room = _drive(_K('j7lX'), monkeypatch, name='admin')
    assert len(_row_text(room, _SH_CASE_ROWS[0])) == 5, "one char gone, from the west side"


def test_X_works_for_the_scribe_once_taught(monkeypatch):
    # X joined the Cipher Cell's teaches (display 18) — known by display 31
    _res, room = _drive(_K('j7lX'), monkeypatch)
    assert len(_row_text(room, _SH_CASE_ROWS[0])) == 5


# ── visual p / r / J ─────────────────────────────────────────────────────────

def test_visual_r_overstrikes_the_selection(monkeypatch):
    _res, room = _drive(_K('j4lv2lrz'), monkeypatch)
    assert _row_text(room, _SH_CASE_ROWS[0])[:3] == 'zzz'


def test_visual_J_joins_the_selected_lines(monkeypatch):
    rows0 = build_dungeon_selection_halls(0).rooms[0].rows
    w = build_dungeon_selection_halls(0).rooms[0]._sh_words['stripe']
    _res, room = _drive(_K('7jVjJ'), monkeypatch)
    assert room.rows == rows0 - 1
    assert _row_text(room, _SH_STRIPE_ROWS[0]) == \
        f'{w[0][:2]}##{w[0][2:]} {w[1][:2]}##{w[1][2:]}', "J's seam space"


def test_visual_p_pastes_over_the_selection(monkeypatch):
    # yank 3 chars of the first case word, then paste them over the second's
    _res, room = _drive(_K('j4lv2ly') + _K('2jv2lp'), monkeypatch)
    r1 = _row_text(room, _SH_CASE_ROWS[0])
    r2 = _row_text(room, _SH_CASE_ROWS[1])
    assert r2[:3] == r1[:3], "the yanked span landed over the selection"
    assert len(r2) == 6, "same length: 3 cut, 3 pasted"


def test_visual_p_swaps_registers_vim_true(monkeypatch):
    """After vp the unnamed register holds what the selection WAS (the cut),
    so a second vp pastes the displaced text — the classic swap."""
    _res, room = _drive(_K('j4lv2ly') + _K('2jv2lp') + _K('2jv2lp'),
                        monkeypatch)
    r2 = _row_text(room, _SH_CASE_ROWS[1])
    r3 = _row_text(room, _SH_CASE_ROWS[2])
    assert r3[:3] != r2[:3], "the second vp pasted the FIRST vp's cut"


# ── '' — the implicit jump-back mark ─────────────────────────────────────────

def test_quote_quote_jumps_back_and_toggles(monkeypatch):
    seen = {}
    orig = main._calc_stars
    def spy(won, budget, room_, player, level=''):
        seen['pos'] = (player.row, player.col)
        return orig(won, budget, room_, player, level)
    monkeypatch.setattr(main, '_calc_stars', spy)
    _res, room = _drive(_K('G') + _K("''"), monkeypatch, finish=':wq\r')
    assert seen['pos'] == (2, _SH_SPINE), "back to where the G jumped from"


# ── :{n} — go to line ────────────────────────────────────────────────────────

def test_colon_number_goes_to_the_line(monkeypatch):
    seen = {}
    orig = main._calc_stars
    def spy(won, budget, room_, player, level=''):
        seen['pos'] = (player.row, player.col)
        return orig(won, budget, room_, player, level)
    monkeypatch.setattr(main, '_calc_stars', spy)
    _res, room = _drive(_K(':4\r'), monkeypatch, finish=':wq\r')
    # same landing semantics as {n}G — a real row, on its first non-blank
    assert seen['pos'][0] in range(2, room.rows), seen
    r, c = seen['pos']
    assert room.is_passable(r, c)


# ── ZZ / ZQ — the Sealed Departure relic ─────────────────────────────────────

def test_ZZ_is_locked_without_the_relic(monkeypatch):
    res, _room = _drive(_K('ZQ') + _K('jj'), monkeypatch, finish=':q!\r')
    assert res.get('won') is not True     # ZQ ignored; the :q! quit ends it


def test_ZQ_quits_with_the_relic(monkeypatch):
    res, _room = _drive(_K('ZQ'), monkeypatch, finish='',
                        progress={'extras': ['ZZ']})
    assert not res.get('won')


def test_ZZ_wins_like_wq_with_the_relic(monkeypatch):
    from tests.test_selection_halls import _canon_keys
    room0 = build_dungeon_selection_halls(0).rooms[0]
    keys = _canon_keys(room0)             # ends on the exit
    res, _room = _drive(keys + _K('ZZ'), monkeypatch, finish='',
                        progress={'extras': ['ZZ']})
    assert res.get('won') and res.get('stars') == 2, res


def test_sealed_departure_is_in_the_relic_pool():
    from vimny.content.scrolls import RELIC_SCROLL_IDS, SCROLL_CATALOG
    assert 'ZZ' in RELIC_SCROLL_IDS
    entry = next(s for s in SCROLL_CATALOG if s['id'] == 'ZZ')
    assert entry['title'] == 'The Sealed Departure'
