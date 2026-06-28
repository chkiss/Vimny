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

"""The admin karaoke answer-sheet tracker (main.run_dungeon + render.renderer).

As an admin types the canonical solve, the answer tape's playhead (room.answer_pos)
advances key-for-key.  The NORMAL/VISUAL and INSERT trackers were always there; this
suite guards the two modes that were added later and had silently never worked:

  * COMMAND mode  — `:s` / `:g` ex-commands (the Spellwright's Forge)
  * SEARCH  mode  — `/pat` and `?pat` (Seekers' Labyrinth, the Waypoint Sanctum)

The tape marks Enter with the glyph '⏎' and separates tokens with spaces (stripped for
matching); _replay translates that to the raw keystrokes an admin would press.
"""
import pytest
from blessed import Terminal
from blessed.keyboard import Keystroke

import main
import generation.dungeon_gen as dg


@pytest.fixture(autouse=True)
def _no_anim(monkeypatch):
    for fn in ('_win_animation', '_fireworks_animation', '_starfield_victory'):
        monkeypatch.setattr(main, fn, lambda *a, **k: None)
    # Mid-dungeon scrolls read their dismiss key via a direct term.inkey() that bypasses
    # the karaoke tracker; stub them so an automated replay doesn't consume a tape key.
    for fn in ('_show_scroll_by_id', '_render_standard_scroll',
               '_show_reliquary_scroll', '_show_catalog_scroll'):
        if hasattr(main, fn):
            monkeypatch.setattr(main, fn, lambda *a, **k: None)


def _replay(tape):
    """Karaoke tape → raw keystrokes: ⏎ → Enter, drop the visual space separators."""
    return [Keystroke('\r' if c == '⏎' else c) for c in tape if c != ' ']


def _drive_admin(slug, dungeon):
    term = Terminal(force_styling=False)
    import render.colors as _colors
    _colors.init(term)                       # key/chest colour paths touch color_rgb()
    keys = _replay(dungeon.room.answer) + [Keystroke(c) for c in ':q!\r']
    it = iter(keys)
    term.inkey = lambda *a, **k: next(it, Keystroke(''))
    main.render_all = lambda *a, **k: None
    main.run_dungeon(term, slug, {}, player_name='admin', _dungeon=dungeon)


@pytest.mark.parametrize("slug", [
    'spellwrights_forge',   # COMMAND mode — :%s/.../g, :s/.../, :g/cursed/d
    'seekers_labyrinth',    # SEARCH forward — /vault⏎
    'waypoint_sanctum',     # SEARCH backward — ?xyzzy⏎
    'operators_vault',      # NORMAL operators + relic-chest scrolls (stubbed above)
    'cipher_cell',          # NORMAL r / D — a plain control
])
def test_karaoke_tape_advances_to_the_end(slug):
    d = dg.build_dungeon_spellwrights_forge(1) if slug == 'spellwrights_forge' \
        else getattr(dg, f'build_dungeon_{slug}')(1)
    room = d.room
    plain = room.answer.replace(' ', '')
    assert plain, f"{slug} has no answer tape"
    _drive_admin(slug, d)
    assert not room.answer_diverged, f"{slug}: tape diverged at {room.answer_pos}/{len(plain)}"
    assert room.answer_pos == len(plain), f"{slug}: stuck at {room.answer_pos}/{len(plain)}"


def test_non_admin_player_never_tracks_or_sees_the_tape():
    # The answer sheet is admin-only: room.answer is cleared on entry for real players.
    d = dg.build_dungeon_spellwrights_forge(1)
    term = Terminal(force_styling=False)
    keys = _replay(d.room.answer) + [Keystroke(c) for c in ':q!\r']
    it = iter(keys)
    term.inkey = lambda *a, **k: next(it, Keystroke(''))
    main.render_all = lambda *a, **k: None
    main.run_dungeon(term, 'spellwrights_forge', {}, player_name='Normand', _dungeon=d)
    assert d.room.answer == '' and d.room.answer_pos == 0
