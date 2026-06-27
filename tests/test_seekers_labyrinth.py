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

"""The Seekers' Labyrinth (search: / ? n N *).

A frozen perfect maze where search teleports across walls — the only affordable
way to either key (foot-only par ≫ budget).  The player spawns on the first of
three 'maze' words; * / n reach the third, beside the GOLD key.  Grabbing it and
jumping BACK with N (to the 2nd 'maze', a passed decoy) reaches the GOLD door,
which seals the RED key; the RED key opens the RED door at the very end, beside
'vault'.  Structure is fixed; only decor words vary by seed.
"""
import os
import pytest

from generation.dungeon_gen import (
    build_dungeon_seekers_labyrinth as _build,
    _par_seekers_labyrinth as _par,
    _SEEKERS_PAR, _SEEKERS_ANSWER, _SEEKERS_WORD, _SEEKERS_DOORWORD,
    _SEEKERS_SPAWN, _SEEKERS_GOLD_KEY, _SEEKERS_GOLD_DOOR,
    _SEEKERS_RED_KEY, _SEEKERS_RED_DOOR, _SEEKERS_EXIT,
)
from engine.world import CellType
from engine.player import Player
from engine.motion import apply_motion
from engine.search import find_next, word_under_cursor, match_cells

SEEDS = [1, 42, 999, 12345, 2 ** 20 + 7]


def _room(seed):
    return _build(seed).rooms[0]


def _word_at(room, r, c):
    ru = room.char_run_at(r, c)
    return ''.join(ru.symbols) if ru is not None else None


def _positions(room, word):
    return sorted((ru.row, ru.col) for ru in room.char_runs
                  if ''.join(ru.symbols) == word)


def _only_passable_neighbour(room, r, c):
    nbrs = [(r + dr, c + dc) for dr, dc in ((1, 0), (-1, 0), (0, 1), (0, -1))
            if 0 <= r + dr < room.rows and 0 <= c + dc < room.cols
            and room.cells[r + dr][c + dc] == CellType.CORRIDOR]
    return nbrs


# ── vocab sourcing ──────────────────────────────────────────────────────────
def _load_vocab(fname):
    path = os.path.join(os.path.dirname(__file__), '..', 'art', fname)
    out = set()
    with open(path, encoding='utf-8') as fh:
        for raw in fh:
            w = raw.rstrip('\n').rstrip(' ')
            if w and not w.startswith('#'):
                out.add(w)
    return out


_VOCAB = _load_vocab('vocab_plain.txt') | _load_vocab('vocab_mixed.txt')


# ── answer simulator (mirrors main.py keystroke costs + key/door mechanics) ──
def _simulate(answer, room):
    """Run a space-separated answer through the real engine.  Tracks the unnamed
    register's key colour and the two coloured doors.  Returns
    (final_pos, keystrokes_spent, reached_exit)."""
    keys  = {e.tag: (e.row, e.col) for e in room.entities if e.kind == 'floor_key'}
    doors = {e.tag: (e.row, e.col) for e in room.entities if e.kind == 'locked_door'}
    EXIT  = _SEEKERS_EXIT
    p = Player(row=room.spawn_pos[0], col=room.spawn_pos[1])
    reg = ''
    last = None
    spent = 0

    def _open(tag):
        room.entities = [e for e in room.entities
                         if not (e.kind == 'locked_door' and e.tag == tag)]
        room.rebuild_indexes()

    for tok in answer.split():
        if '⏎' in tok:                                  # /pat⏎ or ?pat⏎
            fwd = tok[0] == '/'
            pat = tok[1:-1]
            last = (pat, fwd)
            dest = find_next(room, p, pat, fwd)
            assert dest is not None, f'{tok}: no match'
            p.row, p.col = dest
            spent += len(pat) + 2
        elif tok in ('*', '#'):
            w = word_under_cursor(room, p)
            assert w is not None, f'* with no word under cursor at {(p.row, p.col)}'
            fwd = tok == '*'
            last = (w, fwd)
            p.row, p.col = find_next(room, p, w, fwd)
            spent += 1
        elif tok in ('n', 'N'):
            pat, base = last
            fwd = (not base) if tok == 'N' else base
            p.row, p.col = find_next(room, p, pat, fwd)
            spent += 1
        elif tok == 'x':
            for tag, pos in keys.items():
                if (p.row, p.col) == pos:
                    reg = tag                            # cut key into the register
            spent += 1
        elif tok == 'p':
            for tag, pos in doors.items():
                if reg == tag and abs(p.row - pos[0]) + abs(p.col - pos[1]) == 1:
                    _open(tag)
                    p.row, p.col = pos                   # paste steps onto the door
            spent += 1
        else:                                            # motion (maybe counted)
            i = 0
            while i < len(tok) and tok[i] in '123456789':   # count starts 1-9
                i += 1
            n = int(tok[:i]) if i else 1
            apply_motion(p, tok[i:], n, room, count_given=(i > 0))
            spent += (len(tok[:i]) + 1) if i else 1
    return (p.row, p.col), spent, (p.row, p.col) == EXIT


# ── structure (per seed) ─────────────────────────────────────────────────────
@pytest.mark.parametrize('seed', SEEDS)
def test_dimensions_and_budget(seed):
    room = _room(seed)
    assert (room.rows, room.cols) == (17, 39)
    assert room.par == _SEEKERS_PAR == 19
    assert room.budget == 27                      # ceil(19 * 1.4)


@pytest.mark.parametrize('seed', SEEDS)
def test_spawn_sits_on_the_search_word(seed):
    room = _room(seed)
    assert room.spawn_pos == _SEEKERS_SPAWN
    assert _word_at(room, *_SEEKERS_SPAWN) == _SEEKERS_WORD   # '*' is the opener


@pytest.mark.parametrize('seed', SEEDS)
def test_search_words_have_the_right_counts(seed):
    room = _room(seed)
    assert _positions(room, _SEEKERS_WORD) == [(1, 1), (5, 1), (11, 15)]   # 3 echoes
    assert _positions(room, _SEEKERS_DOORWORD) == [(1, 7)]                 # 1 door word
    for ru in room.char_runs:                       # decor never collides with either
        w = ''.join(ru.symbols)
        if w in (_SEEKERS_WORD, _SEEKERS_DOORWORD):
            continue
        assert _SEEKERS_WORD not in w and _SEEKERS_DOORWORD not in w


@pytest.mark.parametrize('seed', SEEDS)
def test_two_coloured_keys_and_doors(seed):
    room = _room(seed)
    ent = {(e.kind, e.tag): (e.row, e.col) for e in room.entities}
    assert ent[('floor_key', 'gold')]   == _SEEKERS_GOLD_KEY  == (11, 11)
    assert ent[('locked_door', 'gold')] == _SEEKERS_GOLD_DOOR == (5, 6)
    assert ent[('floor_key', 'red')]    == _SEEKERS_RED_KEY   == (5, 7)
    assert ent[('locked_door', 'red')]  == _SEEKERS_RED_DOOR  == (1, 18)
    assert ent[('exit', '')]            == _SEEKERS_EXIT      == (1, 19)


@pytest.mark.parametrize('seed', SEEDS)
def test_gold_key_is_left_of_the_third_maze(seed):
    """0 from the 3rd 'maze' must halt on the gold key (so the cursor stays left
    of the maze and N then jumps back to the 2nd 'maze')."""
    room = _room(seed)
    assert _SEEKERS_GOLD_KEY[0] == 11 and _SEEKERS_GOLD_KEY[1] < 15
    p = Player(row=11, col=15)                      # on the 3rd 'maze'
    apply_motion(p, '0', 1, room)
    assert (p.row, p.col) == _SEEKERS_GOLD_KEY


@pytest.mark.parametrize('seed', SEEDS)
def test_red_key_is_sealed_by_the_gold_door(seed):
    room = _room(seed)
    assert _only_passable_neighbour(room, *_SEEKERS_RED_KEY) == [_SEEKERS_GOLD_DOOR]


@pytest.mark.parametrize('seed', SEEDS)
def test_exit_is_gated_by_the_red_door(seed):
    room = _room(seed)
    assert _only_passable_neighbour(room, *_SEEKERS_EXIT) == [_SEEKERS_RED_DOOR]


@pytest.mark.parametrize('seed', SEEDS)
def test_every_word_is_sourced_from_vocab(seed):
    room = _room(seed)
    for ru in room.char_runs:
        assert ''.join(ru.symbols) in _VOCAB


# ── solver / forcing (structure is seed-independent: run once) ───────────────
def test_answer_solves_within_budget():
    room = _room(42)
    pos, spent, reached = _simulate(_SEEKERS_ANSWER, room)
    assert reached, f'answer ended at {pos}, not the exit {_SEEKERS_EXIT}'
    assert spent == _SEEKERS_PAR == 19
    assert spent <= room.budget


def test_answer_backtracks_with_N():
    """The canonical route returns to the passed decoy with N (the cheapest
    backward jump) — the command this level exists to teach."""
    assert 'N' in _SEEKERS_ANSWER.split()


def test_search_makes_it_feasible():
    """With search, a full solution exists within budget (the Dijkstra's model
    can't use the 1-key N, so it lands a hair above the hand par, still ≤ budget)."""
    room = _room(42)
    assert _par(room) <= room.budget


def test_search_is_required():
    """Without search, the best foot route costs far more than the budget — so
    search is genuinely the only affordable way through the labyrinth."""
    room = _room(42)
    foot_only = _par(room, no_search=True)
    assert foot_only > room.budget
    assert foot_only >= 2 * room.budget          # by a wide margin (≈176 vs 27)


@pytest.mark.parametrize('seed', SEEDS)
def test_hlsearch_cells_cover_every_maze_echo(seed):
    """match_cells (the hlsearch source) lights up all three 'maze' words."""
    room = _room(seed)
    cells = match_cells(room, _SEEKERS_WORD)
    for (r, c) in _positions(room, _SEEKERS_WORD):
        assert all((r, c + i) in cells for i in range(len(_SEEKERS_WORD)))
