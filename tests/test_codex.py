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

"""The Codex pane (engine/codex.py): folds, motion over visible rows,
search that opens the containing fold, and the :h landing."""
from blessed.keyboard import Keystroke

import main
from engine.codex import CodexPane, scroll_sections
from content.scrolls import SCROLL_CATALOG


def _pane():
    return CodexPane([
        ('The First Page',  ['alpha one', 'alpha two']),
        ('The Second Page', ['beta one', 'beta two', 'beta three']),
        ('The Third Page',  ['gamma one']),
    ])


# ── folds ─────────────────────────────────────────────────────────────────────

def test_opens_fully_folded_as_a_table_of_contents():
    p = _pane()
    assert p.visible_lines() == [0, 3, 7]           # the three headers only


def test_za_toggles_the_section_under_the_cursor():
    p = _pane()
    p.toggle_fold()
    assert p.visible_lines() == [0, 1, 2, 3, 7]
    p.toggle_fold()
    assert p.visible_lines() == [0, 3, 7]


def test_zR_and_zM():
    p = _pane()
    p.open_all()
    assert p.visible_lines() == list(range(9))
    p.cursor = 5                                    # inside section 2
    p.close_all()
    assert p.visible_lines() == [0, 3, 7]
    assert p.cursor == 3                            # snapped to its header


# ── motion: a closed fold is ONE line (Vim-true) ─────────────────────────────

def test_j_steps_over_a_closed_fold_as_one_line():
    p = _pane()
    p.move(1)
    assert p.cursor == 3
    p.move(1)
    assert p.cursor == 7
    p.move(1)                                       # clamped at bottom
    assert p.cursor == 7
    p.move(-2)
    assert p.cursor == 0


def test_gg_and_G():
    p = _pane()
    p.to_bottom()
    assert p.cursor == 7
    p.to_top()
    assert p.cursor == 0


# ── search ────────────────────────────────────────────────────────────────────

def test_search_lands_and_opens_the_containing_fold():
    p = _pane()
    assert p.search('beta two')
    assert p.cursor == 5
    assert 5 in p.visible_lines()                   # fold opened


def test_n_wraps_and_N_reverses():
    p = _pane()
    p.open_all()
    assert p.search('one')
    first = p.cursor
    assert p.search('')                             # n
    assert p.cursor != first
    p.search('')
    p.search('')                                    # wraps around
    assert p.cursor == first
    assert p.search('', backward=True)              # N
    assert p.cursor != first


def test_failed_search_moves_nothing():
    p = _pane()
    assert not p.search('xyzzy')
    assert p.cursor == 0


# ── :h landing ────────────────────────────────────────────────────────────────

def test_jump_to_matches_a_title_substring_and_unfolds():
    p = _pane()
    assert p.jump_to('second')
    assert p.cursor == 3
    assert 4 in p.visible_lines()


def test_jump_to_unknown_name_fails():
    p = _pane()
    assert not p.jump_to('grimoire')


# ── rendering ────────────────────────────────────────────────────────────────

def test_render_rows_marks_ridges_and_follows_the_cursor():
    p = _pane()
    rows = p.render_rows(3, 60)
    assert len(rows) == 3
    assert all(is_ridge for _t, _c, is_ridge in rows)
    assert rows[0][1]                               # cursor on the first ridge
    assert '(2 lines)' in rows[0][0]
    p.open_all()
    p.to_bottom()
    rows = p.render_rows(3, 60)
    assert rows[-1][1]                              # scrolled to keep cursor


# ── the standing matter ──────────────────────────────────────────────────────

def test_every_catalog_scroll_binds_into_the_codex():
    # Regression: the Unnamed Register uses the kv shape, not tagged lines —
    # a full-catalog player must still open the book (KeyError 2026-07-16).
    all_ids = [s['id'] for s in SCROLL_CATALOG]
    secs = scroll_sections(SCROLL_CATALOG, all_ids)
    assert len(secs) == len(SCROLL_CATALOG)
    reg_body = dict((t, b) for t, b in secs)['The Unnamed Register']
    assert any(x.strip().startswith('x') for x in reg_body)
    # Every bound line must be plain text — rich (text, hl) segments (the
    # Numbered Ledger, the Recalling Hand) flatten (zR crash, 2026-07-16)...
    for title, body in secs:
        for ln in body:
            assert isinstance(ln, str), (title, ln)
    # ...and the whole open book must render.
    pane = CodexPane(secs)
    pane.open_all()
    pane.to_bottom()
    for text, _cur, _ridge in pane.render_rows(30, 56):
        assert isinstance(text, str)


def test_scroll_sections_only_binds_discovered_scrolls():
    assert scroll_sections(SCROLL_CATALOG, []) == []
    secs = scroll_sections(SCROLL_CATALOG, ['readers_key'])
    assert len(secs) == 1 and secs[0][0] == 'The Codex Key'
    assert any(':h {name}' in ln for ln in secs[0][1])


# ── the pane feed (main._codex_feed) ─────────────────────────────────────────

class _FakePlayer:
    pass


def _feed(player, s):
    for ch in s:
        if ch == '\r':
            main._codex_feed(player, Keystroke('\r', name='KEY_ENTER'))
        else:
            main._codex_feed(player, Keystroke(ch))


def test_feed_folds_counts_and_q_closes_the_window():
    player = _FakePlayer()
    player.codex_pane = _pane()
    _feed(player, 'za')                             # unfold section 1
    assert player.codex_pane.visible_lines() == [0, 1, 2, 3, 7]
    _feed(player, '2j')                             # count motion
    assert player.codex_pane.cursor == 2
    _feed(player, 'G')
    assert player.codex_pane.cursor == 7
    _feed(player, 'gg')
    assert player.codex_pane.cursor == 0
    _feed(player, ':q\r')                           # closes the WINDOW only
    assert player.codex_pane is None


def test_feed_search_input_flow():
    player = _FakePlayer()
    player.codex_pane = _pane()
    _feed(player, '/gamma\r')
    assert player.codex_pane.cursor == 8
    _feed(player, ':wq\r')
    assert player.codex_pane is None
