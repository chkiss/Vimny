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

"""Tests for Block F macros — engine/macro.py: key normalisation for recording
and synthetic-key reconstruction for playback."""
from engine.macro import synth_key, record_char, SynthKey, ESC, ENTER, BACKSPACE


class TestSynthKey:
    def test_printable(self):
        k = synth_key('a')
        assert str(k) == 'a' and k.name == '' and k.is_sequence is False

    def test_escape(self):
        assert synth_key(ESC).name == 'KEY_ESCAPE'

    def test_enter(self):
        assert synth_key(ENTER).name == 'KEY_ENTER'

    def test_backspace(self):
        assert synth_key(BACKSPACE).name == 'KEY_BACKSPACE'


class TestRecordChar:
    def test_printable_key(self):
        assert record_char(SynthKey('x')) == 'x'

    def test_escape_key(self):
        assert record_char(SynthKey('\x1b', name='KEY_ESCAPE')) == ESC

    def test_enter_key(self):
        assert record_char(SynthKey('\r', name='KEY_ENTER')) == ENTER

    def test_backspace_key(self):
        assert record_char(SynthKey('\x7f', name='KEY_BACKSPACE')) == BACKSPACE

    def test_sequence_skipped(self):
        assert record_char(SynthKey('\x1b[A', is_sequence=True)) is None


def test_record_then_synth_roundtrip_preserves_specials():
    for ch in ('a', 'Ω', ESC, ENTER, BACKSPACE):
        rec = record_char(synth_key(ch))
        assert rec == ch
        assert synth_key(rec).name == synth_key(ch).name
