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

"""Tests for Block F macros — vimny/engine/macro.py: key normalisation for recording
and synthetic-key reconstruction for playback."""
from vimny.engine.macro import synth_key, record_char, SynthKey, ESC, ENTER, BACKSPACE


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
        from vimny.engine.player import Player
        return Player()

    def test_player_has_no_separate_macro_store(self):
        assert not hasattr(self._player(), 'macros')

    def test_recording_lands_in_the_text_register(self):
        from vimny.engine.registers import record_register, read_register, clip_to_keys
        p = self._player()
        record_register(p, 'a', 'ddp')
        assert clip_to_keys(read_register(p, 'a')) == 'ddp'
        assert 'a' in p.registers

    def test_recording_clobbers_text_that_was_in_that_register(self):
        from vimny.engine.registers import (write_register, record_register,
                                      read_register, clip_to_keys, keys_to_clip)
        p = self._player()
        write_register(p, 'a', keys_to_clip('hello'))
        record_register(p, 'a', 'xp')
        assert clip_to_keys(read_register(p, 'a')) == 'xp'

    def test_yanked_text_can_be_replayed_as_keys(self):
        # The payoff of unification: @ runs a register's contents whatever put
        # them there, so a word you yanked off the floor is executable.
        from vimny.engine.registers import (write_register, read_register,
                                      clip_to_keys, keys_to_clip)
        p = self._player()
        write_register(p, 'a', keys_to_clip('jjp'))       # as if yanked
        assert clip_to_keys(read_register(p, 'a')) == 'jjp'

    def test_uppercase_register_appends_the_recording(self):
        from vimny.engine.registers import record_register, read_register, clip_to_keys
        p = self._player()
        record_register(p, 'a', 'dd')
        record_register(p, 'A', 'p')
        assert clip_to_keys(read_register(p, 'a')) == 'ddp'

    def test_recording_leaves_the_unnamed_register_and_zero_alone(self):
        # vim does not disturb "" or "0 while recording — only an explicit
        # yank/delete does.
        from vimny.engine.registers import record_register
        p = self._player()
        record_register(p, 'a', 'dd')
        assert '"' not in p.registers and '0' not in p.registers

    def test_black_hole_records_nothing(self):
        from vimny.engine.registers import record_register
        p = self._player()
        record_register(p, '_', 'dd')
        assert '_' not in p.registers

    def test_control_chars_ride_in_caret_notation(self):
        # Stored as vim DISPLAYS them (^[), so a macro register can be pasted
        # into a buffer and read on screen — no raw escape byte ever reaches
        # the terminal — and it still round-trips back to real keys for @.
        from vimny.engine.registers import keys_to_clip, clip_to_keys
        from vimny.engine.macro import ESC
        clip = keys_to_clip('ce' + ESC)
        assert clip_to_keys(clip) == 'ce' + ESC
        syms = clip['rows'][0]['char_runs'][0]['symbols']
        assert '\x1b' not in syms and ''.join(syms) == 'ce^['


# ── @ runs EVERY line of a register, not just the first ──────────────────────
class TestMultiLineReplay:
    """`clip_to_keys` read `rows[0]` and dropped the rest, so a multi-line
    register HALF-RAN: the first line executed and the rest vanished with no
    error. Latent until the stores were unified — now a register can hold `yy`
    of a row of keystrokes, or a `qA` append across lines."""

    def _rows(self, *lines):
        from vimny.engine.registers import keys_to_clip
        rows = []
        for l in lines:
            rows.extend(keys_to_clip(l)['rows'])
        return rows

    def test_one_charwise_row_is_unchanged(self):
        """The common case — every recording is one line — must not move."""
        from vimny.engine.registers import keys_to_clip, clip_to_keys
        assert clip_to_keys(keys_to_clip('ddp')) == 'ddp'

    def test_every_row_replays_joined_by_enter(self):
        from vimny.engine.registers import clip_to_keys
        from vimny.engine.macro import ENTER
        clip = {'linewise': False, 'rows': self._rows('ddp', 'xp')}
        assert clip_to_keys(clip) == 'ddp' + ENTER + 'xp'

    def test_a_linewise_clip_ends_with_one_too(self):
        """A linewise register ends with a newline in vim, so `yy@\"` on a line
        holding an ex command runs it AND submits it — which is the whole point
        of being able to execute text you yanked off the floor."""
        from vimny.engine.registers import clip_to_keys
        from vimny.engine.macro import ENTER
        clip = {'linewise': True, 'rows': self._rows(':s/old/new/')}
        assert clip_to_keys(clip) == ':s/old/new/' + ENTER

    def test_a_charwise_clip_does_not(self):
        from vimny.engine.registers import keys_to_clip, clip_to_keys
        from vimny.engine.macro import ENTER
        assert not clip_to_keys(keys_to_clip('dw')).endswith(ENTER)

    def test_an_empty_register_still_replays_as_nothing(self):
        from vimny.engine.registers import clip_to_keys
        assert clip_to_keys({'linewise': True, 'rows': []}) == ''
        assert clip_to_keys(None) == ''

    def test_the_join_survives_caret_notation(self):
        """The rows are stored with control chars as ^[ / ^M, and the ENTER put
        BETWEEN them is a real one — the un-caret pass must not confuse them."""
        from vimny.engine.registers import clip_to_keys
        from vimny.engine.macro import ENTER, ESC
        clip = {'linewise': False, 'rows': self._rows('ce' + ESC, 'j')}
        assert clip_to_keys(clip) == 'ce' + ESC + ENTER + 'j'

    def test_an_appended_recording_spanning_rows_replays_whole(self):
        from vimny.engine.player import Player
        from vimny.engine.registers import (record_register, read_register,
                                      clip_to_keys, write_register)
        from vimny.engine.macro import ENTER
        p = Player()
        # a linewise yank into "a, then qA appends a recording after it
        write_register(p, 'a', {'linewise': True, 'rows': self._rows('jdd')})
        record_register(p, 'A', 'xp')
        played = clip_to_keys(read_register(p, 'a'))
        assert 'jdd' in played and 'xp' in played and ENTER in played
