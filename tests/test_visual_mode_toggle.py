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

"""Visual-mode v/V/Ctrl-v switching — and the <enter> regression.

`va<enter>` used to drop into VISUAL_BLOCK: in visual mode `a` parses to a non-motion
(enter-insert) and clears the key buffer, then <enter> arrives as a *sequence* key
with raw=''.  The old guard `raw in 'vV'` is True for '' (empty string is a substring
of everything), and `{...}[raw or '\\x16']` then defaulted to Ctrl-v → block mode.
`_visual_mode_toggle` must return None for every sequence key."""
import pytest
from vimny.engine.modes import Mode
from vimny.game import _visual_mode_toggle


def test_v_V_ctrlv_switch_to_their_modes():
    assert _visual_mode_toggle('v', 'v') == Mode.VISUAL
    assert _visual_mode_toggle('V', 'V') == Mode.VISUAL_LINE
    assert _visual_mode_toggle('', '\x16') == Mode.VISUAL_BLOCK     # Ctrl-v


@pytest.mark.parametrize('key_str', ['\r', '\n', 'KEY_ENTER', 'KEY_LEFT', 'KEY_HOME'])
def test_sequence_keys_never_toggle_a_visual_mode(key_str):
    # sequence keys reach the handler with raw='' — none may switch mode
    assert _visual_mode_toggle('', key_str) is None


@pytest.mark.parametrize('raw', ['a', 'h', 'j', 'd', 'o', 'w', '0', '$'])
def test_other_normal_keys_are_not_mode_switches(raw):
    assert _visual_mode_toggle(raw, raw) is None
