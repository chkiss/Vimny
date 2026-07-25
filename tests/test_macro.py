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


# ── macros ARE registers (unified 2026-07-25) ────────────────────────────────
class TestMacrosAreRegisters:
    """There is no separate macro store: `qa` records INTO register a, `@a`
    replays whatever register a holds. That is how vim works, and it is why
    q/@ are spelled with register names at all."""

    def _player(self):
        from engine.player import Player
        return Player()

    def test_player_has_no_separate_macro_store(self):
        assert not hasattr(self._player(), 'macros')

    def test_recording_lands_in_the_text_register(self):
        from engine.registers import record_register, read_register, clip_to_keys
        p = self._player()
        record_register(p, 'a', 'ddp')
        assert clip_to_keys(read_register(p, 'a')) == 'ddp'
        assert 'a' in p.registers

    def test_recording_clobbers_text_that_was_in_that_register(self):
        from engine.registers import (write_register, record_register,
                                      read_register, clip_to_keys, keys_to_clip)
        p = self._player()
        write_register(p, 'a', keys_to_clip('hello'))
        record_register(p, 'a', 'xp')
        assert clip_to_keys(read_register(p, 'a')) == 'xp'

    def test_yanked_text_can_be_replayed_as_keys(self):
        # The payoff of unification: @ runs a register's contents whatever put
        # them there, so a word you yanked off the floor is executable.
        from engine.registers import (write_register, read_register,
                                      clip_to_keys, keys_to_clip)
        p = self._player()
        write_register(p, 'a', keys_to_clip('jjp'))       # as if yanked
        assert clip_to_keys(read_register(p, 'a')) == 'jjp'

    def test_uppercase_register_appends_the_recording(self):
        from engine.registers import record_register, read_register, clip_to_keys
        p = self._player()
        record_register(p, 'a', 'dd')
        record_register(p, 'A', 'p')
        assert clip_to_keys(read_register(p, 'a')) == 'ddp'

    def test_recording_leaves_the_unnamed_register_and_zero_alone(self):
        # vim does not disturb "" or "0 while recording — only an explicit
        # yank/delete does.
        from engine.registers import record_register
        p = self._player()
        record_register(p, 'a', 'dd')
        assert '"' not in p.registers and '0' not in p.registers

    def test_black_hole_records_nothing(self):
        from engine.registers import record_register
        p = self._player()
        record_register(p, '_', 'dd')
        assert '_' not in p.registers

    def test_control_chars_ride_in_caret_notation(self):
        # Stored as vim DISPLAYS them (^[), so a macro register can be pasted
        # into a buffer and read on screen — no raw escape byte ever reaches
        # the terminal — and it still round-trips back to real keys for @.
        from engine.registers import keys_to_clip, clip_to_keys
        from engine.macro import ESC
        clip = keys_to_clip('ce' + ESC)
        assert clip_to_keys(clip) == 'ce' + ESC
        syms = clip['rows'][0]['char_runs'][0]['symbols']
        assert '\x1b' not in syms and ''.join(syms) == 'ce^['
