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

"""The hidden Easter eggs: the hat-gated goblin substitutions (:s/g/X/), the
~-swell, and the ex-command winks (:help! :smile :Ni! :xyzzy)."""
from blessed.keyboard import Keystroke
from blessed import Terminal

import main
import generation.dungeon_gen as dg
from engine.player import Player
from engine.world import entity_letter


def _room_and_master():
    r = dg.build_dungeon_warden_eternal(0).rooms[0]
    p = Player(row=29, col=1)
    p.hat_worn = True
    p.known_commands = p.known_commands + ['admin']
    return r, p


def _goblins(r):
    return [e for e in r.entities if e.kind == 'goblin' and e.alive]


# ── the master's gate ─────────────────────────────────────────────────────────
def test_bareheaded_cannot_command_the_goblins():
    r = dg.build_dungeon_warden_eternal(0).rooms[0]
    p = Player(row=29, col=1)                      # no hat
    n = len(_goblins(r))
    msgs = []
    assert main._goblin_substitute('%s/g/f/', r, p, msgs.append) is True
    assert len(_goblins(r)) == n                    # nothing changed
    assert 'hat' in msgs[-1].lower()


def test_non_goblin_substitute_falls_through():
    r, p = _room_and_master()
    assert main._goblin_substitute('%s/foo/bar/', r, p, lambda m: None) is False
    assert main._goblin_substitute('%s/W/x/', r, p, lambda m: None) is False   # not 'g'


# ── remove effects ────────────────────────────────────────────────────────────
def test_friend_and_default_letter_remove_the_goblin():
    for rep in ('f', 'h', 'c', 'd', '$', '@', 'q'):
        r, p = _room_and_master()
        main._goblin_substitute('%s/g/' + rep + '/', r, p, lambda m: None)
        assert not any(e.tag not in ('zombie', 'demon') and e.kind == 'goblin'
                       and e.alive and e.tag != 'echo' for e in r.entities)


def test_headless_corpse_leaves_an_h():
    r, p = _room_and_master()
    g = next(e for e in r.entities if e.kind == 'goblin' and e.row == 29 and e.tag != 'echo')
    gr, gc = g.row, g.col
    main._goblin_substitute('s/g/h/', r, p, lambda m: None)   # current row only
    run = r.char_run_at(gr, gc)
    assert run is not None and 'h' in run.symbols


# ── transform effects (they stay, and they attack) ───────────────────────────
def test_zombie_and_demon_transform_and_stay_hostile():
    r, p = _room_and_master()
    main._goblin_substitute('%s/g/z/', r, p, lambda m: None)
    z = [e for e in r.entities if e.tag == 'zombie' and e.alive]
    assert z and all(entity_letter(e) == 'Z' and e.ai == 'chase' and e.hp == 2 for e in z)

    r, p = _room_and_master()
    main._goblin_substitute('%s/g/&/', r, p, lambda m: None)
    d = [e for e in r.entities if e.tag == 'demon' and e.alive]
    assert d and all(entity_letter(e) == '&' and e.ai == 'chase' and e.hp == 3 for e in d)


# ── flame (deferred to the caller) + elf trade (armed for y/n) ───────────────
def test_flame_marks_goblins_for_detonation():
    r, p = _room_and_master()
    main._goblin_substitute('%s/g/!/', r, p, lambda m: None)
    assert len(r._pending_boom) == len(_goblins(r))   # caller detonates these


def test_elf_arms_a_trade_prompt():
    r, p = _room_and_master()
    msgs = []
    main._goblin_substitute('%s/g/e/', r, p, msgs.append)
    assert r._elf_trade and r._elf_trade['key'] in ('hp', 'register', 'demon')
    assert 'y/n' in msgs[-1]


# ── ~ swells a goblin into a G (driven through the real loop) ─────────────────
def test_tilde_swells_a_goblin(monkeypatch):
    d = dg.build_dungeon_warden_eternal(0)
    r = d.rooms[0]
    # put a lone goblin under the spawn so the player stands on it, then ~
    g = next(e for e in r.entities if e.kind == 'goblin' and e.tag == 'horde')
    g.row, g.col = r.spawn_pos
    r.rebuild_indexes()
    monkeypatch.setattr(main, 'render_all', lambda *a, **k: None)
    monkeypatch.setattr(main.time, 'sleep', lambda *a, **k: None)
    monkeypatch.setattr(main.SM, 'save_progress', lambda *a, **k: None)
    monkeypatch.setattr(Terminal, 'height', property(lambda self: 41))
    term = Terminal()
    it = iter([Keystroke('~')] + [Keystroke(c) for c in ':q!\r'])
    monkeypatch.setattr(term, 'inkey', lambda *a, **k: next(it, Keystroke('')))
    main.run_dungeon(term, 'warden_eternal', {}, player_name='Hero', _dungeon=d)
    assert g.swole and entity_letter(g) == 'G' and g.max_hp >= 3


# ── the ex-command winks ──────────────────────────────────────────────────────
def _drive_cmd(cmd, monkeypatch):
    seen = []
    monkeypatch.setattr(main, 'render_all',
                        lambda term, dungeon, player, budget, message='', *a, **k:
                        (seen.append(message), seen.append(getattr(player, 'error', ''))))
    monkeypatch.setattr(main.time, 'sleep', lambda *a, **k: None)
    monkeypatch.setattr(main.SM, 'save_progress', lambda *a, **k: None)
    monkeypatch.setattr(Terminal, 'height', property(lambda self: 41))
    term = Terminal()
    keys = [Keystroke(':')] + [Keystroke(c) for c in cmd] + [Keystroke('\r')]
    keys += [Keystroke(c) for c in ':q!\r']
    it = iter(keys)
    monkeypatch.setattr(term, 'inkey', lambda *a, **k: next(it, Keystroke('')))
    main.run_dungeon(term, 'first_cave', {}, player_name='Hero')
    return [s for s in seen if s]


def test_ex_command_easter_eggs(monkeypatch):
    assert any("Don't panic" in s for s in _drive_cmd('help!', monkeypatch))
    assert any('Nothing happens' in s for s in _drive_cmd('xyzzy', monkeypatch))
    assert any('shrubbery' in s for s in _drive_cmd('Ni!', monkeypatch))
    assert any('wizard' in s.lower() for s in _drive_cmd('smile', monkeypatch))


def test_hat_wearer_is_greeted_in_the_first_cave(monkeypatch):
    seen = []
    monkeypatch.setattr(main, 'render_all',
                        lambda term, dungeon, player, budget, message='', *a, **k:
                        seen.append(message))
    monkeypatch.setattr(main.time, 'sleep', lambda *a, **k: None)
    monkeypatch.setattr(main.SM, 'save_progress', lambda *a, **k: None)
    monkeypatch.setattr(Terminal, 'height', property(lambda self: 41))
    term = Terminal()
    it = iter([Keystroke(c) for c in ':q!\r'])
    monkeypatch.setattr(term, 'inkey', lambda *a, **k: next(it, Keystroke('')))
    main.run_dungeon(term, 'first_cave', {'has_hat': True}, player_name='Hero')
    assert any('master' in (s or '').lower() for s in seen)
