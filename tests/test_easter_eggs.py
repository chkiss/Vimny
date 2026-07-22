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
    r.fog_cells = set()                    # reveal — the egg skips fogged creatures
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
    assert main._goblin_substitute('%s/q/x/', r, p, lambda m: None) is False   # no 'q' creature


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


def test_elf_becomes_a_persistent_merchant_entity():
    r, p = _room_and_master()
    main._goblin_substitute('%s/g/e/', r, p, lambda m: None)
    elves = [e for e in r.entities if e.kind == 'elf']
    assert elves and all(entity_letter(e) == 'e' and e.tag == 'elf' for e in elves)


def test_gold_becomes_a_pickup_coin():
    r, p = _room_and_master()
    main._goblin_substitute('%s/g/$/', r, p, lambda m: None)
    coins = [e for e in r.entities if e.kind == 'gold']
    assert coins and all(entity_letter(e) == '$' for e in coins)


def test_elf_trade_accepts_on_y_and_debits_gold(monkeypatch):
    from engine.world import Entity
    d = dg.build_dungeon_warden_eternal(0)
    r = d.rooms[0]
    for e in list(r.entities):                        # clear the board
        if e.kind == 'goblin':
            e.alive, e.hp = False, 0
    r.entities = [e for e in r.entities if e.kind != 'goblin']
    sr, sc = r.spawn_pos
    r.entities.append(Entity(kind='elf', tag='elf', row=sr, col=sc + 1))
    r.rebuild_indexes()
    monkeypatch.setattr(main.random, 'choice', lambda seq: seq[0])   # the 2-gold vial
    grab = {}

    def _cap(term, dungeon, player, budget, message='', *a, **k):
        grab['p'] = player

    monkeypatch.setattr(main, 'render_all', _cap)
    monkeypatch.setattr(main.time, 'sleep', lambda *a, **k: None)
    monkeypatch.setattr(main.SM, 'save_progress', lambda *a, **k: None)
    monkeypatch.setattr(Terminal, 'height', property(lambda self: 41))
    term = Terminal()
    # step onto the elf (triggers the bargain), then 'y' accepts
    it = iter([Keystroke('l'), Keystroke('y')] + [Keystroke(c) for c in ':q!\r'])
    monkeypatch.setattr(term, 'inkey', lambda *a, **k: next(it, Keystroke('')))
    main.run_dungeon(term, 'warden_eternal',
                     {'has_hat': True, 'hat_worn': True, 'gold': 5},
                     player_name='Hero', _dungeon=d)
    p = grab['p']
    assert p.gold == 3                                 # 5 - 2 (the vial's price)
    elf = next(e for e in r.entities if e.kind == 'elf')
    assert elf.tag == 'spent' and elf.ai == 'wander'   # dealt — now it wanders off


# ── the g<->G rule lives in ONE place (case_entities) for every case command ──
def test_case_ops_are_the_single_source_of_the_swelled_glyph():
    from engine.operator import case_entities
    r, p = _room_and_master()
    cells = [(e.row, e.col) for e in r.entities
             if e.kind == 'goblin' and e.tag == 'horde'][:3]
    assert case_entities(r, cells, 'gU') == 3          # uppercase → swell
    for (rr, cc) in cells:
        e = r.entity_at(rr, cc)
        assert e.swole and entity_letter(e) == 'G' and main._sight_radius(e) == 10
    assert case_entities(r, cells, 'gu') == 3           # lowercase → shrink back
    for (rr, cc) in cells:
        assert not r.entity_at(rr, cc).swole


def test_case_rule_is_uniform_across_goblin_dog_cat():
    from engine.world import Entity
    from engine.operator import case_entities
    r, _ = _room_and_master()
    dog = Entity(kind='ally', tag='dog', row=2, col=2, hp=2, max_hp=2)
    cat = Entity(kind='critter', tag='cat', row=2, col=4, hp=1, max_hp=1)
    r.entities += [dog, cat]
    r.rebuild_indexes()
    case_entities(r, [(2, 2), (2, 4)], 'gU')
    assert entity_letter(dog) == 'D' and entity_letter(cat) == 'C'


# ── sight: demons are relentless, G-goblins see twice as far ─────────────────
def test_demon_sees_everywhere_and_swole_sees_double():
    r, p = _room_and_master()
    main._goblin_substitute('%s/g/&/', r, p, lambda m: None)
    dem = next(e for e in r.entities if e.tag == 'demon')
    assert main._sight_radius(dem) > 1000            # relentless, unlimited range

    r, p = _room_and_master()
    main._goblin_substitute('%s/g/G/', r, p, lambda m: None)
    big = next(e for e in r.entities if e.swole and e.kind == 'goblin')
    assert main._sight_radius(big) == main._ALERT_RADIUS * 2   # doubled sight
    assert entity_letter(big) == 'G'


# ── the dog fights on your side ───────────────────────────────────────────────
def test_dog_is_an_ally_that_mauls_the_nearest_foe():
    from engine.world import Entity
    r, p = _room_and_master()
    for e in list(r.entities):                       # clear the board of goblins
        if e.kind == 'goblin':
            e.alive, e.hp = False, 0
    r.entities = [e for e in r.entities if e.kind != 'goblin']
    dog = Entity(kind='ally', tag='dog', row=10, col=10, hp=2, max_hp=2,
                 ai='hunt', ai_speed=1)
    foe = Entity(kind='goblin', tag='horde', row=10, col=11, hp=1, max_hp=1,
                 ai='chase', ai_speed=1)
    r.entities += [dog, foe]
    r.rebuild_indexes()
    main._enemy_tick(r, p)
    assert not foe.alive                             # the hound felled it


def test_cat_persists_as_a_harmless_critter():
    r, p = _room_and_master()
    main._goblin_substitute('%s/g/c/', r, p, lambda m: None)
    cats = [e for e in r.entities if e.kind == 'critter']
    assert cats and all(entity_letter(c) == 'c' and c.ai == 'wander' for c in cats)


def test_uppercase_creature_letters_make_the_swelled_form():
    # D = a big hound, C = a big cat — the uppercase form is the swelled one,
    # just like G is a swelled goblin.
    r, p = _room_and_master()
    main._goblin_substitute('%s/g/D/', r, p, lambda m: None)
    dogs = [e for e in r.entities if e.kind == 'ally']
    assert dogs and all(e.swole and entity_letter(e) == 'D' for e in dogs)

    r, p = _room_and_master()
    main._goblin_substitute('%s/g/C/', r, p, lambda m: None)
    cats = [e for e in r.entities if e.kind == 'critter']
    assert cats and all(e.swole and entity_letter(e) == 'C' for e in cats)


def test_swelling_an_ally_keeps_it_yours():
    from engine.world import Entity
    d = dg.build_dungeon_warden_eternal(0)
    r = d.rooms[0]
    dog = Entity(kind='ally', tag='dog', row=r.spawn_pos[0], col=r.spawn_pos[1],
                 hp=2, max_hp=2, ai='hunt', ai_speed=1)
    r.entities.append(dog)
    r.rebuild_indexes()
    import main as _m
    from blessed import Terminal
    _m_render = _m.render_all
    Terminal.height = property(lambda self: 41)
    term = Terminal()
    it = iter([Keystroke('~')] + [Keystroke(c) for c in ':q!\r'])
    _m.render_all = lambda *a, **k: None
    _m.time.sleep = lambda *a, **k: None
    _m.SM.save_progress = lambda *a, **k: None
    term.inkey = lambda *a, **k: next(it, Keystroke(''))
    _m.run_dungeon(term, 'warden_eternal', {}, player_name='Hero', _dungeon=d)
    _m.render_all = _m_render
    assert dog.swole and entity_letter(dog) == 'D' and dog.kind == 'ally'


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
