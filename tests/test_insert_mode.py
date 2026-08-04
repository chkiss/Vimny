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

"""Tests for mode entry/exit key handling.

Covers: i/a/o/I/A/O → INSERT, v → VISUAL, V → VISUAL LINE,
        ESC exits any non-NORMAL mode back to NORMAL,
        and that the parser ignores keypresses in INSERT mode.
"""
import pytest
from vimny.engine.vim_parser import parse
from vimny.engine.modes import Mode
from vimny.engine.player import Player


# ── Parser: mode-entry keys in NORMAL mode ───────────────────────────────────

@pytest.mark.parametrize("key,variant", [
    ('i', 'i'), ('a', 'a'), ('o', 'o'),
    ('I', 'I'), ('A', 'A'), ('O', 'O'),
])
def test_insert_mode_entry_keys(key, variant):
    action, remaining = parse(key, Mode.NORMAL)
    assert action is not None
    assert action['type'] == 'enter_mode'
    assert action['mode'] == 'insert'
    assert action.get('variant') == variant
    assert remaining == ''


def test_s_parses_substitute_char():
    action, remaining = parse('s', Mode.NORMAL)
    assert action == {'type': 'substitute', 'count': 1}
    assert remaining == ''


def test_S_parses_substitute_line():
    action, remaining = parse('S', Mode.NORMAL)
    assert action == {'type': 'substitute', 'line': True, 'count': 1}
    assert remaining == ''


def test_v_enters_visual():
    action, remaining = parse('v', Mode.NORMAL)
    assert action == {'type': 'enter_mode', 'mode': 'visual'}
    assert remaining == ''


def test_capital_V_enters_visual_line():
    action, remaining = parse('V', Mode.NORMAL)
    assert action == {'type': 'enter_mode', 'mode': 'visual_line'}
    assert remaining == ''


def test_gv_reselects_visual():
    action, remaining = parse('gv', Mode.NORMAL)
    assert action == {'type': 'enter_mode', 'mode': 'visual', 'reselect': True}
    assert remaining == ''


# ── Parser: ignores input in non-NORMAL modes ─────────────────────────────────

@pytest.mark.parametrize("mode", [Mode.INSERT, Mode.VISUAL, Mode.VISUAL_LINE, Mode.VISUAL_BLOCK])
def test_parser_returns_none_in_non_normal_modes(mode):
    action, buf = parse('h', mode)
    assert action is None
    assert buf == 'h'  # buffer unchanged — caller must handle it


# ── ESC mode exit via _apply_esc helper ──────────────────────────────────────

from vimny.engine.motion import _apply_esc  # noqa: E402  (import after engine imports)


@pytest.mark.parametrize("start_mode", [
    Mode.INSERT,
    Mode.VISUAL,
    Mode.VISUAL_LINE,
    Mode.VISUAL_BLOCK,
])
def test_esc_returns_any_mode_to_normal(start_mode):
    player = Player()
    player.mode = start_mode
    _apply_esc(player)
    assert player.mode == Mode.NORMAL


def test_esc_in_normal_mode_is_harmless():
    player = Player()
    player.mode = Mode.NORMAL
    _apply_esc(player)
    assert player.mode == Mode.NORMAL


# ── End-to-end key sequence: i then ESC ──────────────────────────────────────

def test_insert_then_esc_round_trip():
    """Simulate game-loop handling: 'i' → INSERT, ESC → NORMAL."""
    player = Player()
    assert player.mode == Mode.NORMAL

    # 'i' in NORMAL → action says enter_insert
    action, _ = parse('i', Mode.NORMAL)
    assert action['type'] == 'enter_mode'
    player.mode = Mode.INSERT  # game loop applies this

    assert player.mode == Mode.INSERT

    # ESC → NORMAL (game loop calls _apply_esc)
    _apply_esc(player)
    assert player.mode == Mode.NORMAL
