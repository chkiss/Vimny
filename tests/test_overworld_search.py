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

"""The overworld as a real netrw buffer: / ? n N search over the visible
labels, :{n}, buffer-local marks + '', and the Ctrl-o/Ctrl-i jump list —
token-gated, then Vim-identical (line-granular cursor, a documented
deviation)."""
import pytest
from blessed.keyboard import Keystroke
from blessed import Terminal

import main
from engine.player import Player
from render.overworld import build_lines, default_cursor, line_search_text
from content.levels import LEVELS, key_for_slug

ALL_TOKENS = ['/', 'mark', 'jump', 'line_addr', 'count', 'G', '{', '}']


def _K(s):
    return [Keystroke(ch) for ch in s]


def _drive(keys, monkeypatch, tokens=ALL_TOKENS):
    keys = list(keys) + _K(':q\r')
    errlog = []
    player = Player(name='Scribe', row=0, col=0)

    def _stub_render(*a, **k):
        if player.error:                      # errors are cleared on the next
            errlog.append(player.error)       # keypress — capture at render time
        return (k.get('scroll_offset', 0), 0, 0)

    monkeypatch.setattr(main, 'render_overworld', _stub_render)
    monkeypatch.setattr(main, '_known_from_progress', lambda p: list(tokens))
    monkeypatch.setattr(Terminal, 'height', property(lambda self: 41))
    term = Terminal()
    it = iter(keys)
    monkeypatch.setattr(term, 'inkey', lambda *a, **k: next(it, Keystroke('')))
    result = main.run_overworld(term, player, {})
    player.errlog = errlog
    return result, player


def _lines():
    visible = [l for l in LEVELS if not l.get('admin_only')]
    return build_lines(visible, [])


def _line_of(slug):
    for i, ln in enumerate(_lines()):
        if ln['type'] == 'level' and ln['level']['slug'] == slug:
            return i
    raise AssertionError(slug)


# ── search ────────────────────────────────────────────────────────────────────

def test_slash_search_jumps_to_the_label(monkeypatch):
    result, player = _drive(_K('/goblin_gauntlet\r'), monkeypatch)
    assert result['cursor'] == _line_of('goblin_gauntlet')
    assert player.last_search == ('goblin_gauntlet', True)


def test_n_and_N_walk_the_matches(monkeypatch):
    # 'enclosure' matches many level labels — n walks forward, N back.
    matches = [i for i, ln in enumerate(_lines())
               if 'enclosure' in line_search_text(ln)]
    result, _p = _drive(_K('/enclosure\rn'), monkeypatch)
    assert result['cursor'] == matches[1]
    result, _p = _drive(_K('/enclosure\rnN'), monkeypatch)
    assert result['cursor'] == matches[0]


def test_question_searches_backward_with_wrap(monkeypatch):
    # From the top, ? wraps to the LAST match and says so.
    matches = [i for i, ln in enumerate(_lines())
               if 'enclosure' in line_search_text(ln)]
    result, player = _drive(_K('?enclosure\r'), monkeypatch)
    assert result['cursor'] == matches[-1]
    assert any('continuing at BOTTOM' in e for e in player.errlog)


def test_not_found_reports_E486(monkeypatch):
    start = default_cursor(_lines())
    result, player = _drive(_K('/zzqqxx\r'), monkeypatch)
    assert result['cursor'] == start
    assert any(e.startswith('E486') for e in player.errlog)


def test_empty_pattern_repeats_the_last_search(monkeypatch):
    result, _p = _drive(_K('/enclosure\rgg/\r'), monkeypatch)
    matches = [i for i, ln in enumerate(_lines())
               if 'enclosure' in line_search_text(ln)]
    assert result['cursor'] == matches[0]


def test_search_is_token_gated(monkeypatch):
    start = default_cursor(_lines())
    result, player = _drive(_K('/goblin\r'), monkeypatch, tokens=[])
    assert result['cursor'] == start
    assert any("haven't learned" in e for e in player.errlog)


# ── :{n} ─────────────────────────────────────────────────────────────────────

def test_colon_line_number_jumps(monkeypatch):
    result, _p = _drive(_K(':9\r'), monkeypatch)
    assert result['cursor'] == 8


def test_colon_line_number_gated(monkeypatch):
    start = default_cursor(_lines())
    result, player = _drive(_K(':9\r'), monkeypatch, tokens=['/'])
    assert result['cursor'] == start
    assert any("haven't learned" in e for e in player.errlog)


# ── marks + '' ───────────────────────────────────────────────────────────────

def test_mark_set_and_jump_back(monkeypatch):
    start = default_cursor(_lines())
    result, player = _drive(_K("maG'a"), monkeypatch)
    assert result['cursor'] == start
    assert player.ow_marks == {'a': start}


def test_quote_quote_returns_to_jump_origin(monkeypatch):
    start = default_cursor(_lines())
    result, _p = _drive(_K("G''"), monkeypatch)
    assert result['cursor'] == start


def test_unset_mark_reports_E20(monkeypatch):
    _r, player = _drive(_K("'z"), monkeypatch)
    assert any(e.startswith('E20') for e in player.errlog)


# ── the jump list ────────────────────────────────────────────────────────────

def test_ctrl_o_and_tab_walk_the_jump_list(monkeypatch):
    start = default_cursor(_lines())
    last = len(_lines()) - 1
    result, _p = _drive(_K('G') + [Keystroke('\x0f')], monkeypatch)
    assert result['cursor'] == start                  # Ctrl-o: back before G
    result, _p = _drive(_K('G') + [Keystroke('\x0f'), Keystroke('\t')],
                        monkeypatch)
    assert result['cursor'] == last                   # Ctrl-i: forward again


def test_search_feeds_the_jump_list(monkeypatch):
    start = default_cursor(_lines())
    result, _p = _drive(_K('/goblin_gauntlet\r') + [Keystroke('\x0f')],
                        monkeypatch)
    assert result['cursor'] == start


# ── the single-source label law ──────────────────────────────────────────────

def test_search_text_matches_the_level_labels():
    for ln in _lines():
        if ln['type'] == 'level':
            assert line_search_text(ln) == key_for_slug(ln['level']['slug'])
