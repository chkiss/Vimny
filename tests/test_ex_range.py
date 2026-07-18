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

"""Engine tests for the ex-range family — :[range]d y m t > < j
(engine/substitute.py run_ex_range), driven directly on hand-built rooms.
Same harness as test_substitute.py: no border walls, every non-space char an
'ancient' glyph, a row's text is its glyphs with gaps as spaces."""
from engine.world import Room, RoomType, CharRun, CellType, Entity
from engine.player import Player
from engine.operator import INDENT_WIDTH
import engine.substitute as S


def _room(lines, cols=None):
    rows = len(lines)
    cols = cols or (max(len(ln) for ln in lines) + 6)
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
    return [_text(room, r).rstrip() for r in range(room.rows)]


# ── parsing / claiming ───────────────────────────────────────────────────────
def test_looks_like_claims_only_full_parses():
    r = _room(['aa', 'bb', 'cc'])
    p = _player()
    for cmd in ('d', '2d', '1,2d', 'dx', 'y', 'y a', 'm0', '2m$', 't.', 'co3',
                'move+1', 'copy0', '>', '>>', '2,3<', 'j', 'j!', '1,3join'):
        assert S.looks_like_ex_range(cmd, r, p), cmd
    for cmd in ('delmarks', 'marks', 'mo', 't', 'w', 'e cave', 'set wrap',
                'd12', 'j odd', 's/a/b/', 'g/a/d'):
        assert not S.looks_like_ex_range(cmd, r, p), cmd


def test_sg_family_not_claimed_and_vice_versa():
    r = _room(['aa'])
    p = _player()
    assert S.looks_like_sg('s/a/b/', r, p) and not S.looks_like_ex_range('s/a/b/', r, p)
    assert S.looks_like_ex_range('2d', r, p) and not S.looks_like_sg('2d', r, p)


# ── :[range]d ────────────────────────────────────────────────────────────────
def test_delete_current_line_by_default():
    r = _room(['aa', 'bb', 'cc'])
    p = _player(row=1)
    handled, _msg, _ns, nl = S.run_ex('d', r, p)
    assert handled and nl == 1
    assert _all(r) == ['aa', 'cc'] and r.rows == 2


def test_delete_range_reports_fewer_lines():
    r = _room(['aa', 'bb', 'cc', 'dd'])
    handled, msg, _ns, nl = S.run_ex('2,3d', r, _player())
    assert handled and nl == 2 and msg == '2 fewer lines'
    assert _all(r) == ['aa', 'dd']


def test_delete_fills_unnamed_register_linewise():
    r = _room(['aa', 'bb'])
    p = _player(row=1)
    S.run_ex('d', r, p)
    clip = p.registers['"']
    assert clip['linewise'] and len(clip['rows']) == 1
    assert p.registers.get('0') is None            # a delete never fills "0


def test_delete_into_named_register():
    r = _room(['aa', 'bb'])
    p = _player()
    S.run_ex('d z', r, p)
    assert p.registers['z']['linewise']
    assert p.registers['"'] is p.registers['z']


# ── :[range]y ────────────────────────────────────────────────────────────────
def test_yank_leaves_buffer_untouched_and_fills_registers():
    r = _room(['aa', 'bb', 'cc'])
    p = _player()
    handled, msg, _ns, nl = S.run_ex('1,2y', r, p)
    assert handled and nl == 2 and msg == '2 lines yanked'
    assert _all(r) == ['aa', 'bb', 'cc']
    assert p.registers['"']['linewise'] and len(p.registers['"']['rows']) == 2
    assert p.registers['0'] is p.registers['"']    # a yank fills "0


def test_yank_named_register():
    r = _room(['aa', 'bb'])
    p = _player()
    S.run_ex('2y a', r, p)
    assert len(p.registers['a']['rows']) == 1


# ── :[range]m ────────────────────────────────────────────────────────────────
def test_move_to_top_with_addr_zero():
    r = _room(['aa', 'bb', 'cc'])
    p = _player()
    handled, _msg, _ns, nl = S.run_ex('3m0', r, p)
    assert handled and nl == 1
    assert _all(r) == ['cc', 'aa', 'bb']
    assert p.row == 0                              # cursor on the last moved line


def test_move_to_bottom_adjusts_for_removed_rows():
    r = _room(['aa', 'bb', 'cc', 'dd'])
    p = _player()
    S.run_ex('1m$', r, p)
    assert _all(r) == ['bb', 'cc', 'dd', 'aa']
    assert p.row == 3


def test_move_range_down_and_cursor_lands_last():
    r = _room(['aa', 'bb', 'cc', 'dd'])
    p = _player()
    handled, msg, _ns, _nl = S.run_ex('1,2m$', r, p)
    assert handled and msg == '2 lines moved'
    assert _all(r) == ['cc', 'dd', 'aa', 'bb']
    assert p.row == 3


def test_move_into_itself_is_an_error():
    r = _room(['aa', 'bb', 'cc'])
    handled, msg, _ns, nl = S.run_ex('1,2m1', r, _player())
    assert handled and nl == 0 and msg.startswith('E134')
    assert _all(r) == ['aa', 'bb', 'cc']


def test_move_leaves_registers_alone():
    r = _room(['aa', 'bb'])
    p = _player()
    p.registers['"'] = {'linewise': False, 'rows': [{'width': 1, 'char_runs': []}]}
    before = p.registers['"']
    S.run_ex('2m0', r, p)
    assert p.registers['"'] is before


# ── :[range]t ────────────────────────────────────────────────────────────────
def test_copy_duplicates_without_removing():
    r = _room(['aa', 'bb'])
    p = _player()
    handled, _msg, _ns, nl = S.run_ex('1t$', r, p)
    assert handled and nl == 1
    assert _all(r) == ['aa', 'bb', 'aa'] and r.rows == 3


def test_copy_to_top_and_registers_alone():
    r = _room(['aa', 'bb'])
    p = _player(row=1)
    S.run_ex('t0', r, p)                           # default range = current line
    assert _all(r) == ['bb', 'aa', 'bb']
    assert p.registers.get('"') is None


def test_co_alias():
    r = _room(['aa', 'bb'])
    S.run_ex('1co1', r, _player())
    assert _all(r) == ['aa', 'aa', 'bb']


# ── :[range]> / :[range]< ────────────────────────────────────────────────────
def test_indent_range_shifts_by_indent_width():
    r = _room(['aa', 'bb', 'cc'])
    handled, msg, _ns, nl = S.run_ex('1,2>', r, _player())
    assert handled and nl == 2 and msg == '2 lines >ed 1 time'
    assert _text(r, 0)[:INDENT_WIDTH] == ' ' * INDENT_WIDTH
    assert _text(r, 0).strip() == 'aa' and _text(r, 2).strip() == 'cc'
    assert _text(r, 2)[0] == 'c'                   # row 3 untouched


def test_double_indent_and_dedent_round_trip():
    r = _room(['aa'])
    S.run_ex('>>', r, _player())
    assert _text(r, 0).index('a') == 2 * INDENT_WIDTH
    S.run_ex('<', r, _player())
    assert _text(r, 0).index('a') == INDENT_WIDTH
    S.run_ex('<<', r, _player())                   # clamped at the wall
    assert _text(r, 0).index('a') == 0


def test_dedent_at_wall_is_a_noop():
    r = _room(['aa'])
    handled, _msg, _ns, nl = S.run_ex('<', r, _player())
    assert handled and nl == 0


# ── :[range]j ────────────────────────────────────────────────────────────────
def test_bare_join_joins_with_next_line():
    r = _room(['aa', 'bb', 'cc'])
    p = _player()
    handled, _msg, _ns, nl = S.run_ex('j', r, p)
    assert handled and nl == 1
    assert _all(r) == ['aa bb', 'cc'] and r.rows == 2


def test_range_join_collapses_whole_range():
    r = _room(['aa', 'bb', 'cc', 'dd'])
    handled, _msg, _ns, nl = S.run_ex('1,3j', r, _player())
    assert handled and nl == 2
    assert _all(r) == ['aa bb cc', 'dd']


def test_join_bang_leaves_no_seam_space():
    r = _room(['aa', 'bb'])
    S.run_ex('j!', r, _player())
    assert _all(r) == ['aabb']


# ── boss safety: edit-immune rows parry structural removal ───────────────────
def _with_warden(r, row):
    w = Entity(kind='warden', row=row, col=1, max_hp=5)
    w.edit_immune = True
    r.add_entity(w)
    return r


def test_delete_parried_by_edit_immune_row():
    r = _with_warden(_room(['aa', 'bb', 'cc']), 1)
    handled, msg, _ns, nl = S.run_ex('%d', r, _player())
    assert handled and nl == 0 and 'shield' in msg
    assert r.rows == 3


def test_move_parried_by_edit_immune_row():
    r = _with_warden(_room(['aa', 'bb', 'cc']), 0)
    handled, msg, _ns, nl = S.run_ex('1m$', r, _player())
    assert handled and nl == 0 and 'shield' in msg
    assert _all(r) == ['aa', 'bb', 'cc']


def test_copy_of_immune_row_is_allowed():
    r = _with_warden(_room(['aa', 'bb']), 0)
    handled, _msg, _ns, nl = S.run_ex('1t$', r, _player())
    assert handled and nl == 1                     # :t doesn't cut — no parry
    assert _all(r) == ['aa', 'bb', 'aa']
