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

"""The Binder's Reliquary (:h — the Codex): one forced round-trip through
the book, and reading is free."""
import math

import pytest
from blessed.keyboard import Keystroke
from blessed import Terminal

import main
from engine.world import CellType
from content.levels import LEVELS
from content.scrolls import SCROLL_CATALOG, RELIC_SCROLL_IDS
from generation.dungeon_gen import (
    build_dungeon_binders_reliquary,
    _BND_ROWS, _BND_COLS, _BND_LECTERN, _BND_KEY_ROWS, _BND_TEXT0,
    _BND_GATE, _BND_BOLT, _BND_EXIT, _BND_PAR,
)
from tests import SEEDS, cached_room

ENTER = Keystroke('\r', name='KEY_ENTER')


def _room(seed=0):
    return cached_room('build_dungeon_binders_reliquary', seed)


def _K(s):
    return [Keystroke(ch) for ch in s]


def _answer_keys(room):
    # The tape plus ONE dismiss key for the lectern scroll screen after x.
    keys = _K('x') + [Keystroke(' ')]
    for tok in room.answer.split(' ')[1:]:
        keys += _K(tok)
    return keys


def _drive(dungeon, keys, monkeypatch, finish=':wq\r', name='Scribe'):
    keys = list(keys) + _K(finish[:-1]) + [ENTER]
    monkeypatch.setattr(main, 'render_all', lambda *a, **k: None)
    monkeypatch.setattr(main.time, 'sleep', lambda *a, **k: None)
    for anim in ('_fireworks_animation', '_win_animation', '_starfield_victory',
                 '_heart_container_animation', '_unlock_animation',
                 '_void_fall_animation', '_drown_animation'):
        monkeypatch.setattr(main, anim, lambda *a, **k: None)
    monkeypatch.setattr(Terminal, 'height', property(lambda self: 41))
    term = Terminal()
    it = iter(keys)
    monkeypatch.setattr(term, 'inkey', lambda *a, **k: next(it, Keystroke('')))
    return main.run_dungeon(term, 'binders_reliquary', {}, player_name=name,
                            _dungeon=dungeon)


def _drive_spent(dungeon, keys, monkeypatch):
    box = {}
    orig = main._calc_stars
    monkeypatch.setattr(main, '_calc_stars',
                        lambda won, budget, room, player, level='':
                            (box.__setitem__('spent', budget.spent),
                             orig(won, budget, room, player, level))[1])
    result = _drive(dungeon, keys, monkeypatch)
    return result, box.get('spent')


# ── curriculum & catalog wiring ──────────────────────────────────────────────

def test_curriculum_entry():
    lv = next(l for l in LEVELS if l['slug'] == 'binders_reliquary')
    assert lv['display'] == '14.1'
    assert lv['type'] == 'reliquary'
    assert lv['after'] == 'seekers_labyrinth'
    assert lv['teaches'] == ['help']


def test_readers_key_is_a_named_scroll_not_a_relic():
    assert any(s['id'] == 'readers_key' for s in SCROLL_CATALOG)
    assert 'readers_key' not in RELIC_SCROLL_IDS


# ── dungeon structure ────────────────────────────────────────────────────────

@pytest.mark.parametrize("seed", SEEDS)
def test_layout_and_identity(seed):
    room = _room(seed)
    assert (room.rows, room.cols) == (_BND_ROWS, _BND_COLS)
    assert room.spawn_pos == _BND_LECTERN
    lectern = next(e for e in room.entities if e.kind == 'chest_scroll')
    assert (lectern.row, lectern.col) == _BND_LECTERN
    assert lectern.scroll_id == 'readers_key'
    exit_ent = next(e for e in room.entities if e.kind == 'exit')
    assert (exit_ent.row, exit_ent.col) == _BND_EXIT and exit_ent.edit_immune


@pytest.mark.parametrize("seed", SEEDS)
def test_door_starts_sealed_and_not_already_true(seed):
    room = _room(seed)
    assert room.cells[_BND_GATE][_BND_BOLT] == CellType.WALL
    assert room.cells[_BND_EXIT[0]][_BND_EXIT[1]] == CellType.WALL
    (targets, _dc), = room._ss_doors
    texts = {main._wla_floor_text(room, r).strip() for r in range(room.rows)}
    assert targets[0] not in texts


@pytest.mark.parametrize("seed", SEEDS)
def test_colophon_names_the_true_key(seed):
    room = _room(seed)
    true_word = room._bnd_words['keys'][room._bnd_words['true']]
    (title, body), = room._codex_extra
    assert title == "The Binder's Colophon"
    page_tokens = {t.strip('.,;') for ln in body for t in ln.split()}
    assert true_word in page_tokens
    # ...and no counterfeit key appears on the page.
    for i, w in enumerate(room._bnd_words['keys']):
        if i != room._bnd_words['true']:
            assert w not in page_tokens


@pytest.mark.parametrize("seed", SEEDS)
def test_words_distinct_and_rows_shaped(seed):
    room = _room(seed)
    words = room._bnd_words
    assert len(set(words['keys']) | set(words['junk'])) == 8
    for i, r in enumerate(_BND_KEY_ROWS):
        text = main._wla_floor_text(room, r).strip()
        assert text == f'{words["junk"][i]} {words["keys"][i]}'
        assert len(text) == 9


@pytest.mark.parametrize("seed", SEEDS)
def test_par_answer_budget(seed):
    room = _room(seed)
    assert room.par == _BND_PAR
    assert room.budget == math.ceil(_BND_PAR * 1.4)
    ops = ['4x' if i == room._bnd_words['true'] else '9x' for i in range(4)]
    assert room.answer == f'x 2j {ops[0]} j {ops[1]} j {ops[2]} j {ops[3]} G l'


# ── playthroughs ─────────────────────────────────────────────────────────────

@pytest.mark.parametrize("seed", SEEDS)
def test_answer_tape_wins_at_par(seed, monkeypatch):
    dungeon = build_dungeon_binders_reliquary(seed)
    result, spent = _drive_spent(dungeon, _answer_keys(dungeon.rooms[0]),
                                 monkeypatch)
    assert result['won'] and spent == _BND_PAR
    assert result['stars'] == 0                     # reliquaries are unstarred


def test_reading_the_codex_is_free(monkeypatch):
    # The full intended run — open the book, land on the colophon, read,
    # close — spends exactly the same as the never-reads tape.
    dungeon = build_dungeon_binders_reliquary(0)
    room = dungeon.rooms[0]
    keys = (_K('x') + [Keystroke(' ')]
            + _K(':h binder') + [ENTER]             # focus moves into the pane
            + _K('jjgg') + _K('/turns') + [ENTER]   # browse + search, all free
            + _K(':q') + [ENTER])                   # close the WINDOW, not the game
    for tok in room.answer.split(' ')[1:]:
        keys += _K(tok)
    result, spent = _drive_spent(dungeon, keys, monkeypatch)
    assert result['won'] and spent == _BND_PAR


def test_q_closes_the_window_before_it_quits_the_game(monkeypatch):
    # Vim-true: with the pane open, :q! closes the WINDOW; the game only
    # ends on the second :q! — so the pane must swallow exactly one.
    dungeon = build_dungeon_binders_reliquary(0)
    keys = (_K('x') + [Keystroke(' ')] + _K(':h binder') + [ENTER]
            + _K(':q!') + [ENTER])                  # captured by the pane
    result = _drive(dungeon, keys, monkeypatch, finish=':q!\r')
    assert not result['won']


def test_h_is_gated_until_taught(monkeypatch):
    # Drive a level BEFORE 14.1 (the labyrinth's known set): :h must refuse.
    from generation.dungeon_gen import build_dungeon_first_cave
    dungeon = build_dungeon_first_cave(0)
    seen = {}
    orig = main._calc_stars
    def spy(won, budget, room_, player, level=''):
        seen['pane'] = getattr(player, 'codex_pane', None)
        return orig(won, budget, room_, player, level)
    monkeypatch.setattr(main, '_calc_stars', spy)
    monkeypatch.setattr(main, 'render_all', lambda *a, **k: None)
    monkeypatch.setattr(main.time, 'sleep', lambda *a, **k: None)
    monkeypatch.setattr(Terminal, 'height', property(lambda self: 41))
    term = Terminal()
    keys = _K(':h') + [ENTER] + _K(':q!') + [ENTER]
    it = iter(keys)
    monkeypatch.setattr(term, 'inkey', lambda *a, **k: next(it, Keystroke('')))
    main.run_dungeon(term, 'first_cave', {}, player_name='Scribe',
                     _dungeon=dungeon)
    assert seen.get('pane') is None


def test_wrong_guess_is_recoverable_within_budget(monkeypatch):
    # Raze the true row by mistake, undo, then run the honest tape.
    dungeon = build_dungeon_binders_reliquary(0)
    room = dungeon.rooms[0]
    t = room._bnd_words['true']
    keys = _K('x') + [Keystroke(' ')] + _K('2j')
    keys += _K(f'{t}j' if t else '')                # descend to the true row
    keys += _K('9xu')                               # the mis-strike, undone
    keys += _K(f'{t}k' if t else '')                # climb back
    for tok in room.answer.split(' ')[2:]:
        keys += _K(tok)
    result, spent = _drive_spent(dungeon, keys, monkeypatch)
    assert result['won'] and spent <= room.budget


def test_no_jump_lands_on_the_sealed_exit(monkeypatch):
    dungeon = build_dungeon_binders_reliquary(0)
    seen = {}
    orig = main._calc_stars
    def spy(won, budget, room_, player, level=''):
        seen['pos'] = (player.row, player.col)
        return orig(won, budget, room_, player, level)
    monkeypatch.setattr(main, '_calc_stars', spy)
    result = _drive(dungeon, _K('G$'), monkeypatch, finish=':wq\r')
    assert not result['won']
    assert seen['pos'][0] != _BND_GATE, seen
