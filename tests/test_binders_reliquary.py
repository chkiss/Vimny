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

"""The Binder's Reliquary (:h — the Codex): a water-split vault crossed only
by /search; the Codex chest waits BEYOND the pass-word, and :h opens nothing
until the book is in hand."""
from collections import deque

import pytest
from blessed.keyboard import Keystroke
from blessed import Terminal

import main
from engine.world import CellType
from content.levels import LEVELS
from content.scrolls import SCROLL_CATALOG, RELIC_SCROLL_IDS
from generation.dungeon_gen import (
    build_dungeon_binders_reliquary,
    _BND_ROWS, _BND_COLS, _BND_AR, _BND_WATER_COLS, _BND_SPAWN,
    _BND_WORD_COL, _BND_CHEST, _BND_EXIT, _BND_BUDGET,
)
from tests import SEEDS, cached_room
from engine.tape import ENTER as TAPE_ENTER

ENTER = Keystroke('\r', name='KEY_ENTER')


def _room(seed=0):
    return cached_room('build_dungeon_binders_reliquary', seed)


def _K(s):
    return [Keystroke(ch) for ch in s]


def _answer_keys(room):
    # room.answer with <CR> realized as Enter, plus ONE dismiss key for the
    # Codex Key scroll screen after the chest x.
    keys = []
    for tok in room.answer.split(' '):
        if tok.endswith(TAPE_ENTER):
            keys += _K(tok[:-len(TAPE_ENTER)]) + [ENTER]
        else:
            keys += _K(tok)
        if tok == 'x':
            keys.append(Keystroke(' '))
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


# ── curriculum & catalog wiring ──────────────────────────────────────────────

def test_curriculum_entry():
    lv = next(l for l in LEVELS if l['slug'] == 'binders_reliquary')
    assert lv['display'] == '14.1'
    assert lv['type'] == 'reliquary'
    assert lv['after'] == 'seekers_labyrinth'
    assert lv['teaches'] == ['help']


def test_codex_key_is_a_named_scroll_not_a_relic():
    entry = next(s for s in SCROLL_CATALOG if s['id'] == 'readers_key')
    assert entry['title'] == 'The Codex Key'
    assert 'readers_key' not in RELIC_SCROLL_IDS


# ── dungeon structure ────────────────────────────────────────────────────────

@pytest.mark.parametrize("seed", SEEDS)
def test_layout_and_identity(seed):
    room = _room(seed)
    assert (room.rows, room.cols) == (_BND_ROWS, _BND_COLS)
    assert room.spawn_pos == _BND_SPAWN
    chest = next(e for e in room.entities if e.kind == 'chest_scroll')
    assert (chest.row, chest.col) == _BND_CHEST
    assert chest.scroll_id == 'readers_key'
    exit_ent = next(e for e in room.entities if e.kind == 'exit')
    assert (exit_ent.row, exit_ent.col) == _BND_EXIT and exit_ent.edit_immune
    assert room.par is None and room.budget == _BND_BUDGET


@pytest.mark.parametrize("seed", SEEDS)
def test_water_channel_splits_the_vault_full_height(seed):
    room = _room(seed)
    for r in range(1, room.rows - 1):
        for c in _BND_WATER_COLS:
            assert room.cells[r][c] == CellType.WATER
            assert not room.is_passable(r, c)


@pytest.mark.parametrize("seed", SEEDS)
def test_chest_and_exit_lie_beyond_the_word(seed):
    # The order of the far shore is fixed: word, THEN chest, THEN exit —
    # the Codex is looted only after the pass-word crossing.
    room = _room(seed)
    word = room._bnd_word
    assert _BND_WORD_COL > max(_BND_WATER_COLS)
    assert _BND_CHEST[1] > _BND_WORD_COL + len(word) - 1
    assert _BND_EXIT[1] > _BND_CHEST[1]


@pytest.mark.parametrize("seed", SEEDS)
def test_the_word_is_the_only_text_on_the_far_shore(seed):
    room = _room(seed)
    far = [ru for ru in room.char_runs if ru.col > max(_BND_WATER_COLS)]
    assert len(far) == 1
    ru = far[0]
    assert (ru.row, ru.col) == (_BND_AR, _BND_WORD_COL)
    assert ''.join(ru.symbols) == room._bnd_word
    # ...and no near-shore frieze glyph is alphabetic (no false search bait).
    for fr in (r for r in room.char_runs if r is not ru):
        assert not any(s.isalpha() for s in fr.symbols)


@pytest.mark.parametrize("seed", SEEDS)
def test_answer_and_colophon(seed):
    room = _room(seed)
    assert room.answer == f'/{room._bnd_word}<CR> e 2l x l'
    (title, body), = room._codex_extra
    assert title == "The Binder's Colophon"
    assert any(':h {name}' in ln for ln in body)


# ── the crossing is search-only ──────────────────────────────────────────────

@pytest.mark.parametrize("seed", SEEDS)
def test_far_shore_unreachable_by_walking(seed):
    room = _room(seed)
    seen, dq = {room.spawn_pos}, deque([room.spawn_pos])
    while dq:
        r, c = dq.popleft()
        for dr, dc in ((0, 1), (0, -1), (1, 0), (-1, 0)):
            nr, nc = r + dr, c + dc
            if (nr, nc) not in seen and 0 <= nr < room.rows and 0 <= nc < room.cols \
                    and room.is_passable(nr, nc):
                seen.add((nr, nc))
                dq.append((nr, nc))
    assert _BND_EXIT not in seen and _BND_CHEST not in seen
    assert all(c <= max(_BND_WATER_COLS) for _r, c in seen)


@pytest.mark.parametrize("seed", SEEDS)
def test_near_shore_friezes_are_symmetric(seed):
    room = _room(seed)
    c0, c1 = 1, min(_BND_WATER_COLS) - 1
    width = c1 - c0 + 1
    rows = {}
    for fr in (1, 5):
        cells = {}
        for ru in room.char_runs:
            if ru.row == fr and ru.col <= c1:
                for i, _s in enumerate(ru.symbols):
                    cells[ru.col + i] = ru.kind
        rows[fr] = cells
    a, b = rows[1], rows[5]
    assert a == b, "top and bottom courses must match"
    assert a, "expected near-shore friezes"
    mirrored = {c0 + (width - 1 - (c - c0)): k for c, k in a.items()}
    assert a == mirrored, "each course must be a palindrome"


@pytest.mark.parametrize("seed", SEEDS)
def test_mist_lies_on_the_water(seed):
    room = _room(seed)
    for r in range(1, room.rows - 1):
        for c in _BND_WATER_COLS:
            assert (r, c) in room.fog_cells
    # ...and ONLY on the water — the far shore stays visible/searchable.
    assert all(c in _BND_WATER_COLS for _r, c in room.fog_cells)


def test_only_search_crosses_the_mist(monkeypatch):
    # The cheese audit: $ and f{ch} are scans (the mist stops them at the
    # bank); G/gg land on the row's first standable (the near shore). Every
    # one of them, driven, leaves the player west of the water.
    dungeon = build_dungeon_binders_reliquary(0)
    word = dungeon.rooms[0]._bnd_word
    seen = {}
    orig = main._calc_stars
    def spy(won, budget, room_, player, level=''):
        seen['pos'] = (player.row, player.col)
        return orig(won, budget, room_, player, level)
    monkeypatch.setattr(main, '_calc_stars', spy)
    keys = _K('$Ggg$') + _K('f' + word[0]) + _K('t' + word[0])
    result = _drive(dungeon, keys, monkeypatch, finish=':wq\r')
    assert not result['won']
    assert seen['pos'][1] < min(_BND_WATER_COLS), seen


# ── playthroughs ─────────────────────────────────────────────────────────────

@pytest.mark.parametrize("seed", SEEDS)
def test_answer_tape_wins_at_par(seed, monkeypatch):
    dungeon = build_dungeon_binders_reliquary(seed)
    result = _drive(dungeon, _answer_keys(dungeon.rooms[0]), monkeypatch)
    assert result['won']
    assert result['stars'] == 0                    # reliquaries are unstarred


def test_h_refuses_until_the_codex_is_in_hand(monkeypatch):
    # Before the chest: 'help' is taught by the level, but there is no book —
    # :h must refuse. After looting, it opens (and reading stays free).
    dungeon = build_dungeon_binders_reliquary(0)
    room = dungeon.rooms[0]
    tape = _answer_keys(room)                      # capture BEFORE driving —
    seen = {}                                      # a run clears room.answer
    orig = main._calc_stars                        # for non-admin players
    def spy(won, budget, room_, player, level=''):
        seen['pane'] = getattr(player, 'codex_pane', None)
        seen['spent'] = budget.spent
        return orig(won, budget, room_, player, level)
    monkeypatch.setattr(main, '_calc_stars', spy)

    early = _K(':h') + [ENTER]
    result = _drive(dungeon, early, monkeypatch, finish=':wq\r')
    assert seen['pane'] is None and not result['won']

    keys = tape[:-1]                               # cross + loot, hold at chest
    keys += _K(':h binder') + [ENTER] + _K('jj') + _K(':q') + [ENTER]
    keys += _K('l')                                # step onto the exit
    result = _drive(dungeon, keys, monkeypatch)
    assert result['won'] and seen['pane'] is None


def test_reading_the_codex_is_free(monkeypatch):
    # Same run with and without the read — identical spend.
    spends = []
    orig = main._calc_stars
    for read in (False, True):
        dungeon = build_dungeon_binders_reliquary(0)
        room = dungeon.rooms[0]
        box = {}
        def spy(won, budget, room_, player, level='', _box=box):
            _box['spent'] = budget.spent
            return orig(won, budget, room_, player, level)
        monkeypatch.setattr(main, '_calc_stars', spy)
        keys = _answer_keys(room)[:-1]
        if read:
            keys += (_K(':h') + [ENTER] + _K('zRjjzM') + _K('/binder') + [ENTER]
                     + _K(':q') + [ENTER])
        keys += _K('l')
        result = _drive(dungeon, keys, monkeypatch)
        assert result['won']
        spends.append(box['spent'])
    assert spends[0] == spends[1]
