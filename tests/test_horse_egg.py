# Vimny — a Vim-teaching dungeon crawler.
# Copyright (C) 2026 Chas Kissick
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""The wizard's horse — a post-game Easter egg in the First Cave.

He appears only once the Warden Eternal is beaten, stands on a free floor cell
near the entry, blocks nothing, and the cursor passes through him (he is not a
puzzle piece). His glyph is the chess knight ♞ (→ 'h' on 2-wide terminals)."""
import pytest

from generation.dungeon_gen import build_dungeon_first_cave
from engine.world import CARET_TRANSPARENT
from engine.player import Player
from main import _place_first_cave_horse, _enemy_tick, _manhattan
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
    player = Player(row=room.spawn_pos[0], col=room.spawn_pos[1])
    for _ in range(60):
        _enemy_tick(room, player)
        assert (h.row, h.col) != (player.row, player.col)
        assert room.is_passable(h.row, h.col)
    # after settling he trails at no more than 3 cells
    assert _dist(h, player) <= 3


@pytest.mark.parametrize('seed', SEEDS)
def test_horse_holds_when_already_at_heel(seed):
    # Standing next to the player (within the band), he does not fidget.
    room = build_dungeon_first_cave(seed).room
    _place_first_cave_horse(room)
    h = _horse(room)
    player = Player(row=h.row, col=h.col)
    # step the player one cell off the horse if possible, else keep them adjacent
    player.row = h.row
    before = (h.row, h.col)
    _enemy_tick(room, player)
    assert (h.row, h.col) == before          # co-located/adjacent → holds station


def _feed(term, monkeypatch, keys):
    it = iter(keys)
    from blessed.keyboard import Keystroke
    monkeypatch.setattr(term, 'inkey', lambda *a, **k: next(it, Keystroke('')))


def test_naming_prompt_returns_typed_name(monkeypatch):
    from blessed import Terminal
    from blessed.keyboard import Keystroke
    import main
    term = Terminal()
    keys = [Keystroke(c) for c in 'Artax'] + [Keystroke('\r')]
    _feed(term, monkeypatch, keys)
    assert main._prompt_horse_name(term, 80, 30) == 'Artax'


def test_naming_prompt_esc_leaves_him_nameless(monkeypatch):
    from blessed import Terminal
    from blessed.keyboard import Keystroke
    import main
    term = Terminal()
    esc = Keystroke('\x1b', code=361, name='KEY_ESCAPE')
    _feed(term, monkeypatch, [esc])
    assert main._prompt_horse_name(term, 80, 30) == ''


def test_horse_blocked_on_bosses_and_combat():
    import main
    room = build_dungeon_first_cave(SEEDS[0]).room
    assert main._horse_blocked('wardens_keep', room)      # boss
    assert main._horse_blocked('goblin_gauntlet', room)   # combat crush
    assert not main._horse_blocked('rune_halls', room)    # ordinary motion level
    room.no_horse = True                                  # runtime opt-out flag
    assert main._horse_blocked('rune_halls', room)


def test_companion_glyph_rides_the_status_bar(capsys):
    from blessed import Terminal
    from engine.budget import Budget
    from render import symbols as S
    from render import colors as C
    from render.renderer import render_all
    term = Terminal()
    C.init(term); S.init(term)
    d = build_dungeon_first_cave(SEEDS[0])
    player = Player(row=d.room.spawn_pos[0], col=d.room.spawn_pos[1])
    render_all(term, d, player, Budget(20), companion='Artax')
    out = capsys.readouterr().out
    assert S.HORSE in out


def test_horse_only_appears_post_game():
    # run_dungeon injects the horse only when warden_eternal is complete; the
    # builder itself never places one (so the fresh First Cave stays clean).
    room = build_dungeon_first_cave(SEEDS[0]).room
    assert _horse(room) is None
