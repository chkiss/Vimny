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

"""Engine tests for :s / :g / :v and the & repeats (vimny/engine/substitute.py), driven
directly on hand-built rooms (no full game loop). The line model: a row's text is
its non-void glyphs with gaps as spaces, wall-bounded."""
from vimny.engine.world import Room, RoomType, CharRun, CellType
from vimny.engine.player import Player
import vimny.engine.substitute as S


def _room(lines, cols=None):
    """Build a room from text lines; each non-space char becomes an 'ancient' glyph.
    No border walls (lo=0, hi=cols) so the whole row is the line."""
    rows = len(lines)
    cols = cols or (max(len(ln) for ln in lines) + 4)
    r = Room(room_type=RoomType.ENTRY, rows=rows, cols=cols)
    r.cells = [[CellType.FLOOR] * cols for _ in range(rows)]
    runs = []
    for ri, ln in enumerate(lines):
        for ci, ch in enumerate(ln):
            if ch != ' ':
                runs.append(CharRun(ri, ci, (ch,), 'ancient'))
    r.char_runs = runs
    r.rebuild_indexes()
    return r


def _player(row=0, col=0):
    p = Player(name='t')
    p.row, p.col = row, col
    return p


def _text(room, row):
    return S.line_text(room, row)[0]


def _all(room):
    return [_text(room, r) for r in range(room.rows)]


# ── basic substitute ─────────────────────────────────────────────────────────
def test_first_only_by_default():
    r = _room(['foo foo foo'])
    handled, msg, ns, nl = S.run_ex('s/foo/bar/', r, _player())
    assert handled and (ns, nl) == (1, 1)
    assert _text(r, 0) == 'bar foo foo'


def test_global_flag_all_on_line():
    r = _room(['foo foo foo'])
    S.run_ex('s/foo/bar/g', r, _player())
    assert _text(r, 0) == 'bar bar bar'


def test_percent_range_all_lines():
    r = _room(['foo', 'foo', 'bar'])
    _h, msg, ns, nl = S.run_ex('%s/foo/X/g', r, _player())
    assert (ns, nl) == (2, 2)
    assert _all(r) == ['X', 'X', 'bar']


def test_line_number_range():
    r = _room(['aa', 'aa', 'aa', 'aa'])
    S.run_ex('2,3s/aa/Z/', r, _player(row=0))
    assert _all(r) == ['aa', 'Z', 'Z', 'aa']


def test_dot_dollar_range():
    r = _room(['a', 'a', 'a', 'a'])
    S.run_ex('.,$s/a/b/', r, _player(row=1))
    assert _all(r) == ['a', 'b', 'b', 'b']


def test_count_acts_on_following_lines():
    r = _room(['x', 'x', 'x', 'x'])
    # :s/x/y/ 2 from line 2 → lines 2 and 3
    S.run_ex('2s/x/y/ 2', r, _player())
    assert _all(r) == ['x', 'y', 'y', 'x']


# ── flags ────────────────────────────────────────────────────────────────────
def test_ignorecase_flag():
    r = _room(['Foo foo FOO'])
    S.run_ex('s/foo/x/gi', r, _player())
    assert _text(r, 0) == 'x x x'


def test_force_case_sensitive_flag():
    r = _room(['Foo foo'])
    S.run_ex('s/foo/x/gI', r, _player())
    assert _text(r, 0) == 'Foo x'


def test_n_flag_counts_without_changing():
    r = _room(['aa aa aa'])
    _h, msg, ns, nl = S.run_ex('s/aa/bb/gn', r, _player())
    assert _text(r, 0) == 'aa aa aa'        # unchanged
    assert ns == 3 and 'matches' in msg


def test_pattern_not_found_message():
    r = _room(['abc'])
    _h, msg, ns, nl = S.run_ex('s/zzz/x/', r, _player())
    assert ns == 0 and 'Pattern not found' in msg


# ── separators & replacement semantics ───────────────────────────────────────
def test_alternate_separator():
    r = _room(['/usr/bin'])
    S.run_ex('s#/#:#g', r, _player())
    assert _text(r, 0) == ':usr:bin'


def test_ampersand_is_whole_match():
    r = _room(['cat'])
    S.run_ex('s/cat/[&]/', r, _player())
    assert _text(r, 0) == '[cat]'


def test_backrefs_and_groups():
    r = _room(['ab'])
    S.run_ex(r's/\(a\)\(b\)/\2\1/', r, _player())
    assert _text(r, 0) == 'ba'


def test_case_modifiers():
    r = _room(['hello world'])
    S.run_ex(r's/\w\+/\u&/g', r, _player())     # capitalise each word
    assert _text(r, 0) == 'Hello World'


def test_upper_run_to_E():
    r = _room(['abcdef'])
    S.run_ex(r's/\(abc\)\(def\)/\U\1\E\2/', r, _player())
    assert _text(r, 0) == 'ABCdef'


def test_tilde_reuses_last_replacement():
    r = _room(['a a', 'b b'])
    p = _player()
    S.run_ex('s/a/XY/g', r, p)
    p.row = 1
    S.run_ex('s/b/~/g', r, p)                    # ~ → 'XY'
    assert _all(r) == ['XY XY', 'XY XY']


def test_empty_pattern_reuses_last_search():
    r = _room(['cat cat'])
    p = _player()
    p.last_search = ('cat', True)
    S.run_ex('s//dog/g', r, p)
    assert _text(r, 0) == 'dog dog'


# ── repeats: :s, &, :&&, g& ──────────────────────────────────────────────────
def test_bare_s_repeats_without_flags():
    r = _room(['aa aa', 'aa aa'])
    p = _player()
    S.run_ex('s/aa/b/g', r, p)                   # line 0 all
    p.row = 1
    S.run_ex('s', r, p)                          # repeat, NO g → first only
    assert _all(r) == ['b b', 'b aa']


def test_double_amp_repeats_with_flags():
    r = _room(['aa aa', 'aa aa'])
    p = _player()
    S.run_ex('s/aa/b/g', r, p)
    p.row = 1
    S.run_ex('&&', r, p)                         # repeat WITH g
    assert _all(r) == ['b b', 'b b']


def test_g_amp_repeats_over_whole_file_with_flags():
    r = _room(['aa', 'aa', 'aa'])
    p = _player()
    S.run_ex('s/aa/b/g', r, p)
    S.repeat_normal(r, p, whole_file=True, keep_flags=True)
    assert _all(r) == ['b', 'b', 'b']


def test_normal_amp_current_line_no_flags():
    r = _room(['aa aa', 'aa aa'])
    p = _player()
    S.run_ex('s/aa/b/g', r, p)
    p.row = 1
    S.repeat_normal(r, p, whole_file=False, keep_flags=False)
    assert _all(r) == ['b b', 'b aa']


# ── :g / :v ──────────────────────────────────────────────────────────────────
def test_global_delete():
    r = _room(['keep', 'drop me', 'keep', 'drop me'])
    S.run_ex('g/drop/d', r, _player())
    assert _all(r) == ['keep', 'keep']


def test_global_substitute():
    r = _room(['ax', 'by', 'ax', 'cz'])
    S.run_ex('g/a/s/x/X/', r, _player())
    assert _all(r) == ['aX', 'by', 'aX', 'cz']


def test_invert_global_v():
    r = _room(['hit', 'miss', 'hit', 'miss'])
    S.run_ex('v/hit/d', r, _player())
    assert _all(r) == ['hit', 'hit']


def test_global_bang_is_invert():
    r = _room(['hit', 'miss'])
    S.run_ex('g!/hit/d', r, _player())
    assert _all(r) == ['hit']


# ── line split via \r ─────────────────────────────────────────────────────────
def test_replacement_newline_splits_line():
    r = _room(['a-b-c'], cols=12)
    inserted = []

    def insert_row(at):
        from vimny.engine.reflow import _insert_blank_row
        _insert_blank_row(r, at + 1, at)
        inserted.append(at)

    S.run_ex(r's/-/\r/g', r, _player(), insert_row=insert_row)
    assert _all(r)[:3] == ['a', 'b', 'c']


# ── void runes are text (consistent with / and x) ────────────────────────────
def _kinds(room, row=0):
    return [(ru.col, ''.join(ru.symbols), ru.kind)
            for ru in sorted(room.char_runs, key=lambda x: x.col) if ru.row == row]


def test_void_rune_is_substitutable():
    # A void rune ('○') is text: substituting it away fills the hole with ordinary
    # runes (no longer the deadly 'void' kind).
    r = Room(room_type=RoomType.ENTRY, rows=1, cols=20)
    r.cells = [[CellType.FLOOR] * 20]
    for c, sym, k in [(1, 'a', 'ancient'), (2, '○', 'void'), (3, 'b', 'ancient')]:
        r.add_char_run(CharRun(0, c, (sym,), k))
    r.rebuild_indexes()
    S.run_ex('s/○/X/', r, _player())
    assert _kinds(r) == [(1, 'aXb', 'ancient')]          # filled, all ordinary text


def test_void_rune_untouched_keeps_its_kind():
    # A substitution elsewhere on the line leaves an unchanged void rune void (deadly).
    r = Room(room_type=RoomType.ENTRY, rows=1, cols=20)
    r.cells = [[CellType.FLOOR] * 20]
    for c, sym, k in [(1, 'f', 'ancient'), (2, 'o', 'ancient'), (3, 'o', 'ancient'),
                      (4, '○', 'void'), (5, 'z', 'ancient')]:
        r.add_char_run(CharRun(0, c, (sym,), k))
    r.rebuild_indexes()
    S.run_ex('s/foo/HI/', r, _player())
    assert ('○', 'void') in [(s, k) for _c, s, k in _kinds(r)]


# ── not-a-substitute passes through ──────────────────────────────────────────
def test_unrelated_command_not_handled():
    r = _room(['abc'])
    handled, *_ = S.run_ex('wq', r, _player())
    assert handled is False
