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

"""A karaoke tape's spaces group ONE COMMAND to a run.

The spaces in `room.answer` are display separators — the tracker strips them,
so nothing here changes how a tape plays. What they change is whether an admin
reading along can see the command they are pressing. `dw` is one thought; `d w`
is that thought sawn in half, and it teaches the shape wrong on a screen whose
whole job is teaching the shape. Counts ride with their motion, operators with
their target, `f`/`F`/`t`/`T` with their character.

The forge's recorder already groups this way when it captures a take
(`engine.tape` lays a separator down only before the first key of a fresh
command), so a hand-authored tape that splits a verb from its object does not
merely read badly — it disagrees with the tapes the game writes itself.

This is a READING convention, so it is checked by shape rather than by parsing:
a run that CANNOT be a whole command on its own is the defect.
"""
import pytest

from vimny.content.levels import LEVELS
import main

#: Tokens that can never stand alone as a command. An operator wants a target,
#: `f`/`F`/`t`/`T`/`r` want a character, `"`/`@` want a register.
DANGLING = {'d', 'y', 'c', 'g', 'gU', 'gu', 'g~', 'z',
            '>', '<', '=', 'f', 'F', 't', 'T', 'r', '"', '@'}

#: …except after a visual selection, where the operator IS the whole command:
#: `v 2j tn d` is four commands, the last of which takes no motion because the
#: selection is its argument.
VISUAL_OPENERS = {'v', 'V', '<C-v>'}


def _dangling_runs(answer: str) -> list:
    """Every run in the tape that cannot be a command by itself."""
    bad, visual_open = [], False
    for run in answer.split():
        if run in VISUAL_OPENERS:
            visual_open = True
            continue
        if run == 'q':
            # The macro terminator — a whole command, and the only bare letter
            # in the alphabet that means "stop" rather than "operate on".
            continue
        if run.isdigit() and run != '0':
            bad.append(run)                   # a count with nothing to count
            continue
        if run in DANGLING:
            if visual_open:
                visual_open = False           # the selection was its argument
            else:
                bad.append(run)
    return bad


@pytest.mark.parametrize('slug', [lv['slug'] for lv in LEVELS])
def test_every_run_could_be_a_command_on_its_own(slug):
    """No tape splits a verb from the thing it acts on."""
    dungeon = main._build_dungeon(slug, 7, game_h=42, admin=True)
    for i, room in enumerate(dungeon.rooms):
        answer = (room.answer or '').strip()
        if not answer:
            continue
        bad = _dangling_runs(answer)
        assert not bad, (
            f'{slug} room {i}: {bad} cannot stand alone — group each with what '
            f'it acts on ("dw", not "d w").\n  {answer}')


def test_the_check_would_catch_a_split_verb():
    """A positive control: the shapes this test exists to reject."""
    assert _dangling_runs('d w $ p') == ['d']
    assert _dangling_runs('w y l w P') == ['y']
    assert _dangling_runs('d F ? G') == ['d', 'F']
    assert _dangling_runs('3 j') == ['3']


def test_the_check_allows_what_is_legitimately_bare():
    """The three shapes that LOOK dangling and are not — a visual operator,
    the macro terminator, and `0`, which is a motion and not a count."""
    assert _dangling_runs('v 2j tn d 4j') == []
    assert _dangling_runs('qa daw j q 9@a') == []
    assert _dangling_runs('x 0 j') == []
    # …and a second selection still needs its own opener
    assert _dangling_runs('v j d d') == ['d']


def test_the_operators_vault_groups_its_cuts():
    """The level the convention was found broken on, pinned by name: ten
    corridors, ten `d`-cuts, each one run."""
    room = main._build_dungeon('operators_vault', 7, game_h=42, admin=True).room
    for cut in ('dw', 'db', 'de', 'dB', 'dE', 'dF?', 'dW', 'd0', 'd$', 'dd'):
        assert f' {cut} ' in f' {room.answer} ', f'{cut} is not one run'
