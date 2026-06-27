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

"""Tests for Block L — engine/registers.py: named registers, "0 last-yank,
"_ black hole, and "A append."""
from engine.player import Player
from engine.registers import write_register, read_register, _append_clip


def _clip(*chars, kind='ancient'):
    runes = [{'dcol': i, 'symbols': (c,), 'kind': kind} for i, c in enumerate(chars)]
    return {'linewise': False, 'rows': [{'width': len(chars), 'char_runs': runes}]}


def _p():
    return Player()


class TestWriteRead:
    def test_default_yank_fills_unnamed_and_zero(self):
        p = _p()
        clip = _clip('a')
        write_register(p, '"', clip, is_delete=False)
        assert read_register(p, '"') is clip
        assert read_register(p, '0') is clip

    def test_default_delete_fills_unnamed_not_zero(self):
        p = _p()
        write_register(p, '"', _clip('x'), is_delete=True)
        assert read_register(p, '"') is not None
        assert read_register(p, '0') is None

    def test_named_register_and_unnamed_mirror(self):
        p = _p()
        clip = _clip('k')
        write_register(p, 'a', clip, is_delete=False)
        assert read_register(p, 'a') is clip
        assert read_register(p, '"') is clip
        assert read_register(p, '0') is None        # named yank does not set "0

    def test_black_hole_discards(self):
        p = _p()
        write_register(p, '"', _clip('keep'), is_delete=False)
        write_register(p, '_', _clip('gone'), is_delete=True)
        # unnamed is untouched by the black-hole write
        assert read_register(p, '"')['rows'][0]['char_runs'][0]['symbols'] == ('keep',)
        assert read_register(p, '_') is None

    def test_uppercase_reads_lowercase(self):
        p = _p()
        write_register(p, 'a', _clip('z'), is_delete=False)
        assert read_register(p, 'A') is read_register(p, 'a')

    def test_zero_register_paste_after_yank_then_delete(self):
        p = _p()
        write_register(p, '"', _clip('Y'), is_delete=False)     # yank → "0 = Y
        write_register(p, '"', _clip('D'), is_delete=True)      # delete → " = D, "0 stays Y
        assert read_register(p, '0')['rows'][0]['char_runs'][0]['symbols'] == ('Y',)
        assert read_register(p, '"')['rows'][0]['char_runs'][0]['symbols'] == ('D',)


class TestAppend:
    def test_uppercase_appends_charwise(self):
        p = _p()
        write_register(p, 'a', _clip('a', 'b'), is_delete=False)
        write_register(p, 'A', _clip('c'), is_delete=False)
        runes = read_register(p, 'a')['rows'][0]['char_runs']
        assert [(r['dcol'], r['symbols']) for r in runes] == [(0, ('a',)), (1, ('b',)), (2, ('c',))]

    def test_append_to_empty(self):
        assert _append_clip(None, _clip('x'))['rows'][0]['char_runs'][0]['symbols'] == ('x',)
