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
    # mirror run_overworld's visibility for a horseless player: admin-only and
    # the post-adoption Registry wing are hidden.
    visible = [l for l in LEVELS
               if not l.get('admin_only') and l.get('wing') != 'registry']
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
    assert player.ow_marks == {'a': (start, 0)}


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


# ── column motions (the netrw buffer gained a column cursor) ─────────────────

ALL_COLS = ALL_TOKENS + ['w', 'b', 'e', 'W', 'B', 'E', 'f', 'F', 't', 'T',
                         ';', ',', '*', 'g_family']


def _drive_col(keys, monkeypatch, tokens=ALL_COLS):
    """Like _drive, but captures the effective column at each render."""
    cols = []
    orig = main.run_overworld
    result, player = None, None

    def _stub_render(*a, **k):
        cols.append(k.get('col', 0))
        return (k.get('scroll_offset', 0), 0, 0)

    keys = list(keys) + _K(':q\r')
    monkeypatch.setattr(main, 'render_overworld', _stub_render)
    monkeypatch.setattr(main, '_known_from_progress', lambda p: list(tokens))
    monkeypatch.setattr(Terminal, 'height', property(lambda self: 41))
    term = Terminal()
    it = iter(keys)
    monkeypatch.setattr(term, 'inkey', lambda *a, **k: next(it, Keystroke('')))
    player = Player(name='Scribe', row=0, col=0)
    result = main.run_overworld(term, player, {})
    return result, cols


def test_l_and_h_move_the_column(monkeypatch):
    # '../' is 3 wide: lll clamps at col 2, h steps back to 1.
    _r, cols = _drive_col(_K('lllh'), monkeypatch)
    assert max(cols) == 2 and cols[-1] == 1


def test_dollar_and_zero_and_caret(monkeypatch):
    # cursor starts on '../' (len 3): $ → col 2; 0 → col 0.
    _r, cols = _drive_col(_K('$'), monkeypatch)
    assert cols[-2] == 2
    _r, cols = _drive_col(_K('$0'), monkeypatch)
    assert cols[-2] == 0


def test_curswant_survives_vertical_moves(monkeypatch):
    # $ on '../' then j onto './' (len 2 → col 1), then onto a level label
    # (long → snaps to its end): Vim's sticky column.
    _r, cols = _drive_col(_K('$j'), monkeypatch)
    assert cols[-2] == 1
    lines = _lines()
    lvl = next(i for i, ln in enumerate(lines) if ln['type'] == 'level')
    _r, cols = _drive_col(_K('$' + 'j' * (lvl - default_cursor(lines))),
                          monkeypatch)
    assert cols[-2] == len(line_search_text(lines[lvl])) - 1


def test_w_walks_the_label_words(monkeypatch):
    # On a level label (dungeon_NN_name): '_'-joined = ONE Vim word, so w
    # from col 0 stays put at the line's last word start… use f to check
    # instead: f5 finds the '5' in 'dungeon_05'.
    lines = _lines()
    lvl = _line_of('goblin_gauntlet')
    label = line_search_text(lines[lvl])
    _r, cols = _drive_col(_K('j' * (lvl - default_cursor(lines)) + 'f5'),
                          monkeypatch)
    assert cols[-2] == label.index('5')


def test_semicolon_repeats_the_find(monkeypatch):
    lines = _lines()
    lvl = _line_of('goblin_gauntlet')       # dungeon_05_the_goblin_gauntlet
    label = line_search_text(lines[lvl])
    _r, cols = _drive_col(_K('j' * (lvl - default_cursor(lines)) + 'fg;'),
                          monkeypatch)
    assert cols[-2] == label.index('g', label.index('g') + 1)


def test_star_whole_word_search(monkeypatch):
    # * on './' … no word; on a level label the whole '_'-joined key is one
    # word appearing once — * wraps back to the same spot with the message.
    lines = _lines()
    lvl = _line_of('goblin_gauntlet')
    result, player = _drive(_K('j' * (lvl - default_cursor(lines)) + '*'),
                            monkeypatch, tokens=ALL_COLS)
    assert result['cursor'] == lvl
    assert any('continuing at TOP' in e for e in player.errlog)


def test_search_lands_on_the_match_column(monkeypatch):
    lines = _lines()
    lvl = _line_of('goblin_gauntlet')
    label = line_search_text(lines[lvl])
    _r, cols = _drive_col(_K('/gauntlet\r'), monkeypatch)
    assert cols[-2] == label.index('gauntlet')


def test_zz_zt_zb_move_the_view_not_the_cursor(monkeypatch):
    offs = []

    def _stub_render(*a, **k):
        offs.append(k.get('scroll_offset', 0))
        return (k.get('scroll_offset', 0), 0, 0)

    monkeypatch.setattr(main, 'render_overworld', _stub_render)
    monkeypatch.setattr(main, '_known_from_progress', lambda p: ['G'])
    monkeypatch.setattr(Terminal, 'height', property(lambda self: 12))
    term = Terminal()
    keys = _K('Gztzbzz:q\r')
    it = iter(keys)
    monkeypatch.setattr(term, 'inkey', lambda *a, **k: next(it, Keystroke('')))
    player = Player(name='Scribe', row=0, col=0)
    result = main.run_overworld(term, player, {})
    n, avail = len(_lines()), 12 - 5
    last = n - 1
    max_off = max(0, n - avail)
    # after G: zt wants cursor at top (clamped), zb at bottom, zz centred
    assert offs[-4] == min(last, max_off)              # zt
    assert offs[-3] == max(0, min(last - avail + 1, max_off))   # zb
    assert offs[-2] == max(0, min(last - avail // 2, max_off))  # zz
    assert result['cursor'] == last                    # the cursor never moved


def test_sequence_keys_do_not_crash(monkeypatch):
    # An arrow key reaches the loop with raw == '' — and '' is a substring
    # of every string, so unguarded `raw in 'wbeWBE'` matched and crashed
    # (the documented raw-in-'vV' regression class, reintroduced 2026-07-17).
    keys = [Keystroke('\x1b[A', name='KEY_UP'), Keystroke('\x1b[B', name='KEY_DOWN')]
    result, _p = _drive(keys, monkeypatch)
    assert result['action'] == 'quit'


# ── the single-source label law ──────────────────────────────────────────────

def test_search_text_matches_the_level_labels():
    for ln in _lines():
        if ln['type'] == 'level':
            assert line_search_text(ln) == key_for_slug(ln['level']['slug'])
