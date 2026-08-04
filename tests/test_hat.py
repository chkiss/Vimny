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

"""The Warden Eternal's hat: `:set hat` grants admin-like all-command access in
ANY level once looted, shimmers the cursor, and persists via progress. Driven
through the real run_dungeon keystroke loop on an EARLY level (first_cave) to
prove the master may cast any spell anywhere."""
from blessed.keyboard import Keystroke
from blessed import Terminal

import vimny.game as main


def _ks(ch):
    return Keystroke(ch)


def _cmd(s):
    return [_ks(':')] + [_ks(c) for c in s] + [_ks('\r')]


def _drive(script, progress):
    """Run first_cave with `script` keystrokes; return (last_player, messages)."""
    grab = {}
    msgs = []

    def _cap(term, dungeon, player, budget, message='', *a, **k):
        grab['player'] = player
        if message:
            msgs.append(message)

    term = Terminal()
    it = iter(script + _cmd('q!'))
    _orig_render = main.render_all
    _orig_inkey = term.inkey
    _orig_save = main.SM.save_progress
    main.render_all = _cap
    main.SM.save_progress = lambda *a, **k: None   # never touch the real save dir
    term.inkey = lambda *a, **k: next(it, _ks(''))
    try:
        main.run_dungeon(term, 'first_cave', progress, player_name='Normand')
    finally:
        main.render_all = _orig_render
        main.SM.save_progress = _orig_save
        term.inkey = _orig_inkey
    return grab.get('player'), msgs


def test_hat_grants_all_commands_in_an_early_level():
    p, msgs = _drive(_cmd('set hat'), {'has_hat': True})
    assert p.hat_worn is True
    assert 'admin' in p.known_commands          # every gate short-circuits
    assert any('brow' in m for m in msgs)


def test_nohat_returns_normal_gating():
    p, _ = _drive(_cmd('set hat') + _cmd('set nohat'), {'has_hat': True})
    assert p.hat_worn is False
    assert 'admin' not in p.known_commands


def test_hat_toggle_is_gated_behind_actually_holding_it():
    p, msgs = _drive(_cmd('set hat'), {})     # never looted
    assert p.hat_worn is False
    assert 'admin' not in p.known_commands
    assert any('no hat' in m.lower() for m in msgs)


def test_worn_state_persists_into_a_fresh_level_entry():
    # has_hat + hat_worn saved in progress → re-entering re-dons the aura.
    p, _ = _drive([], {'has_hat': True, 'hat_worn': True})
    assert p.hat_worn is True
    assert 'admin' in p.known_commands


def test_bang_and_query_forms():
    p, msgs = _drive(_cmd('set hat!') + _cmd('set hat?'), {'has_hat': True})
    assert p.hat_worn is True
    assert 'hat' in msgs           # the query echoes the state
