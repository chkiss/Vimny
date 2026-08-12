# Vimny — a Vim-teaching dungeon crawler.
# Copyright (C) 2026 Chas Kissick
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""The wizard's horse — a post-game Easter egg in the First Cave.

He appears only once the Warden Eternal is beaten, stands on a free floor cell
near the entry, blocks nothing, and the cursor passes through him (he is not a
puzzle piece). His glyph is the chess knight ♞ (→ 'h' on 2-wide terminals)."""
import pytest

from vimny.generation.dungeon_gen import build_dungeon_first_cave
from vimny.engine.world import CARET_TRANSPARENT
from vimny.engine.player import Player
from vimny.game import _place_first_cave_horse, _enemy_tick, _manhattan
from tests import SEEDS


def _dist(h, player):
    return _manhattan(player.row, player.col, h.row, h.col)


def _horse(room):
    hs = [e for e in room.entities if e.kind == 'horse']
    return hs[0] if hs else None


@pytest.mark.parametrize('seed', SEEDS)
def test_horse_stands_on_a_free_floor_cell(seed):
    room = build_dungeon_first_cave(seed).room
    _place_first_cave_horse(room)
    h = _horse(room)
    assert h is not None
    # a passable floor cell, not the spawn or the exit, with room to breathe
    assert room.is_passable(h.row, h.col)
    assert (h.row, h.col) != room.spawn_pos
    assert (h.row, h.col) != room.exit_pos
    assert abs(h.row - room.spawn_pos[0]) + abs(h.col - room.spawn_pos[1]) >= 2


@pytest.mark.parametrize('seed', SEEDS)
def test_horse_blocks_nothing_and_is_caret_transparent(seed):
    room = build_dungeon_first_cave(seed).room
    _place_first_cave_horse(room)
    h = _horse(room)
    # passable (the player walks onto him) and floor-like to ^/first-non-blank
    assert room.is_passable(h.row, h.col)
    assert 'horse' in CARET_TRANSPARENT


def test_placement_is_idempotent():
    room = build_dungeon_first_cave(SEEDS[0]).room
    _place_first_cave_horse(room)
    _place_first_cave_horse(room)
    assert sum(1 for e in room.entities if e.kind == 'horse') == 1


@pytest.mark.parametrize('seed', SEEDS)
def test_horse_follows_within_the_trail_band(seed):
    # Placed far, he closes the gap over a few ticks and never treads on the
    # player nor onto another entity's cell.
    room = build_dungeon_first_cave(seed).room
    _place_first_cave_horse(room)
    h = _horse(room)
    h.tag = 'Artax'                              # named → he follows
    player = Player(row=room.spawn_pos[0], col=room.spawn_pos[1])
    for _ in range(60):
        _enemy_tick(room, player)
        assert (h.row, h.col) != (player.row, player.col)
        assert room.is_passable(h.row, h.col)
    # after settling he trails at no more than 3 cells
    assert _dist(h, player) <= 3


@pytest.mark.parametrize('seed', SEEDS)
def test_horse_holds_when_already_at_heel(seed):
    # A named horse standing next to the player (within the band) does not fidget.
    room = build_dungeon_first_cave(seed).room
    _place_first_cave_horse(room)
    h = _horse(room)
    h.tag = 'Artax'
    player = Player(row=h.row, col=h.col)
    before = (h.row, h.col)
    _enemy_tick(room, player)
    assert (h.row, h.col) == before          # co-located/adjacent → holds station


def test_unadopted_horse_wanders_like_a_cat():
    # Un-named, he ambles a cell at a time (never a Vim leap toward you) and never
    # steps onto the player.
    import random as _r
    _r.seed(0)
    room = build_dungeon_first_cave(SEEDS[0]).room
    _place_first_cave_horse(room)
    h = _horse(room)
    assert not h.tag                         # un-adopted
    player = Player(row=room.spawn_pos[0], col=room.spawn_pos[1])
    seen = set()
    for _ in range(60):
        prev = (h.row, h.col)
        _enemy_tick(room, player)
        seen.add((h.row, h.col))
        assert (h.row, h.col) != (player.row, player.col)
        assert _manhattan(prev[0], prev[1], h.row, h.col) <= 1   # single-cell ambles
        assert room.is_passable(h.row, h.col)
    assert len(seen) > 1                      # he actually wandered


def _feed(term, monkeypatch, keys):
    it = iter(keys)
    from blessed.keyboard import Keystroke
    monkeypatch.setattr(term, 'inkey', lambda *a, **k: next(it, Keystroke('')))


def test_naming_prompt_returns_typed_name(monkeypatch):
    from blessed import Terminal
    from blessed.keyboard import Keystroke
    import vimny.game as main
    term = Terminal()
    keys = [Keystroke(c) for c in 'Artax'] + [Keystroke('\r')]
    _feed(term, monkeypatch, keys)
    assert main._prompt_horse_name(term, 80, 30) == 'Artax'


def test_naming_prompt_esc_leaves_him_nameless(monkeypatch):
    from blessed import Terminal
    from blessed.keyboard import Keystroke
    import vimny.game as main
    term = Terminal()
    esc = Keystroke('\x1b', code=361, name='KEY_ESCAPE')
    _feed(term, monkeypatch, [esc])
    assert main._prompt_horse_name(term, 80, 30) == ''


def test_horse_blocked_on_bosses_and_combat():
    import vimny.game as main
    room = build_dungeon_first_cave(SEEDS[0]).room
    assert main._horse_blocked('wardens_keep', room)      # boss
    assert main._horse_blocked('goblin_gauntlet', room)   # combat crush
    assert not main._horse_blocked('rune_halls', room)    # ordinary motion level
    room.no_horse = True                                  # runtime opt-out flag
    assert main._horse_blocked('rune_halls', room)


def test_companion_glyph_rides_the_status_bar(capsys):
    from blessed import Terminal
    from vimny.engine.budget import Budget
    from vimny.render import symbols as S
    from vimny.render import colors as C
    from vimny.render.renderer import render_all
    term = Terminal()
    C.init(term); S.init(term)
    d = build_dungeon_first_cave(SEEDS[0])
    player = Player(row=d.room.spawn_pos[0], col=d.room.spawn_pos[1])
    render_all(term, d, player, Budget(20), companion='Artax')
    out = capsys.readouterr().out
    assert S.HORSE in out


def test_saddle_registers_ride_with_the_horse():
    from vimny.engine.command_guard import action_allowed, is_saddle_register
    # the saddle registers: digits + symbols; NOT "" and NOT the named/macro a-z.
    assert is_saddle_register('0') and is_saddle_register('_') and is_saddle_register('/')
    assert not is_saddle_register('"')          # unnamed — own gate
    assert not is_saddle_register('a')           # named / macro — own gate
    assert not is_saddle_register('A')           # append to a named register
    # reg_numbered is the ring's OWN lesson (The Delete Ring) and is separate from
    # the saddle gate tested here — hold it, so what this asserts is the horse.
    known = {'reg_named', 'reg_numbered', 'y', 'p', 'd'}
    numbered = {'type': 'paste', 'register': '0'}
    # horse present → allowed; horse absent → blocked (saddle stays with him)
    assert action_allowed(numbered, known, horse_present=True)
    assert not action_allowed(numbered, known, horse_present=False)
    # the unnamed and named/macro registers work with or without the horse
    for r in ('"', 'a'):
        act = {'type': 'paste', 'register': r}
        assert action_allowed(act, known, horse_present=False)


def test_horse_only_appears_post_game():
    # run_dungeon injects the horse only when warden_eternal is complete; the
    # builder itself never places one (so the fresh First Cave stays clean).
    room = build_dungeon_first_cave(SEEDS[0]).room
    assert _horse(room) is None
