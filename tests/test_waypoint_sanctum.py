"""The Waypoint Sanctum (marks: m ' `; applies / ?).

A sealed, wordless sanctum in a goblin-haunted prose danger room.  Search ferries
you out for the exit key; the wordless sanctum can't be searched back to, so a
mark is the way home.  'a reaches the optional scroll room (row's first-left cell),
`a reaches the exact exit-lock approach, ? fetches the backward key past forward
decoys.  Structure fixed; only the prose decor varies by seed.
"""
import os
import pytest

from generation.dungeon_gen import (
    build_dungeon_waypoint_sanctum as _build,
    _WP_PAR, _WP_ANSWER, _WP_KEYWORD, _WP_SCROLL, _WP_SPAWN,
    _WP_LOCK, _WP_EXIT, _WP_KEY, _WP_KEY_WORD_POS, _WP_DECOY_POS,
)
from engine.world import CellType
from engine.player import Player
from engine.motion import apply_motion, _first_non_blank_col
from engine.search import find_next

SEEDS = [1, 42, 999, 12345, 2 ** 20 + 7]


def _room(seed):
    return _build(seed).rooms[0]


def _positions(room, word):
    return sorted((ru.row, ru.col) for ru in room.char_runs
                  if ''.join(ru.symbols) == word)


# ── answer simulator (marks + search + chest + key + lock; main.py costs) ────
def _simulate(answer, room):
    """Run a space-separated answer; returns (pos, spent, reached_exit, got_scroll)."""
    p = Player(row=room.spawn_pos[0], col=room.spawn_pos[1])
    marks: dict = {}
    reg_key = False
    got_scroll = False
    last = None
    spent = 0

    def _open_lock():
        room.entities = [e for e in room.entities
                         if not (e.kind == 'locked_door' and (e.row, e.col) == _WP_LOCK)]
        room.rebuild_indexes()

    for tok in answer.split():
        if tok.startswith('m') and len(tok) == 2:                 # m{a}
            marks[tok[1]] = (p.row, p.col)
            spent += 2
        elif tok.startswith("'") and len(tok) == 2:               # '{a} -> first non-blank
            mr, _ = marks[tok[1]]
            p.row, p.col = mr, _first_non_blank_col(room, mr)
            spent += 2
        elif tok.startswith('`') and len(tok) == 2:               # `{a} -> exact
            p.row, p.col = marks[tok[1]]
            spent += 2
        elif '⏎' in tok:                                          # /pat⏎ or ?pat⏎
            fwd = tok[0] == '/'
            pat = tok[1:-1]
            last = (pat, fwd)
            dest = find_next(room, p, pat, fwd)
            assert dest is not None, f'{tok}: no match'
            p.row, p.col = dest
            spent += len(pat) + 2
        elif tok in ('n', 'N'):
            pat, base = last
            p.row, p.col = find_next(room, p, pat, (not base) if tok == 'N' else base)
            spent += 1
        elif tok == 'x':
            ent = room.entity_at(p.row, p.col)
            if ent is not None and ent.kind == 'chest_scroll':
                got_scroll = True
                room.kill_entity(ent)
            elif ent is not None and ent.kind == 'floor_key':
                reg_key = True
                room.kill_entity(ent)
            spent += 1
        elif tok == 'p':
            assert reg_key and abs(p.row - _WP_LOCK[0]) + abs(p.col - _WP_LOCK[1]) == 1
            _open_lock()
            p.row, p.col = _WP_LOCK
            spent += 1
        else:                                                     # motion (maybe counted)
            i = 0
            while i < len(tok) and tok[i] in '123456789':
                i += 1
            n = int(tok[:i]) if i else 1
            apply_motion(p, tok[i:], n, room, count_given=(i > 0))
            spent += (len(tok[:i]) + 1) if i else 1
    return (p.row, p.col), spent, (p.row, p.col) == _WP_EXIT, got_scroll


# ── structure (per seed) ─────────────────────────────────────────────────────
@pytest.mark.parametrize('seed', SEEDS)
def test_dimensions_and_budget(seed):
    room = _room(seed)
    assert (room.rows, room.cols) == (15, 46)
    assert room.par == _WP_PAR == 19
    assert room.budget == 27                       # ceil(19 * 1.4)


@pytest.mark.parametrize('seed', SEEDS)
def test_sanctum_is_sealed_and_wordless(seed):
    room = _room(seed)
    # the sanctum row carries no characters, so it can't be searched back to
    assert not any(ru.row == 7 for ru in room.char_runs)
    # the sanctum is walled off top and bottom (rows 6 and 8 all wall)
    assert all(room.cells[6][c] == CellType.WALL for c in range(room.cols))
    assert all(room.cells[8][c] == CellType.WALL for c in range(room.cols))


@pytest.mark.parametrize('seed', SEEDS)
def test_entities_and_search_words(seed):
    room = _room(seed)
    ent = {(e.kind): [] for e in room.entities}
    for e in room.entities:
        ent[e.kind].append((e.row, e.col))
    assert _WP_SCROLL in ent['chest_scroll']
    assert _WP_EXIT in ent['exit']
    assert _WP_LOCK in ent['locked_door']
    assert _WP_KEY in ent['floor_key']
    assert len(ent['goblin']) == 4
    # one real key word (backward) + three forward decoys; nothing else matches
    assert _positions(room, _WP_KEYWORD) == sorted([_WP_KEY_WORD_POS] + _WP_DECOY_POS)
    for ru in room.char_runs:
        w = ''.join(ru.symbols)
        if w != _WP_KEYWORD:
            assert _WP_KEYWORD not in w


@pytest.mark.parametrize('seed', SEEDS)
def test_apostrophe_reaches_scroll_backtick_reaches_lock(seed):
    """'a → the scroll room (row's first-left cell); `a → the exit-lock approach."""
    room = _room(seed)
    assert _first_non_blank_col(room, 7) == _WP_SCROLL[1]      # 'a target = scroll cell
    assert _WP_SPAWN != _WP_SCROLL and _WP_SPAWN[1] > _WP_SCROLL[1]  # `a target is distinct, deeper


@pytest.mark.parametrize('seed', SEEDS)
def test_backward_search_is_the_cheapest_key_fetch(seed):
    """From the scroll cell, ?cipher lands on the real key; /cipher hits a forward
    decoy first — so ? is the direct fetch (/ would need n-wrapping)."""
    room = _room(seed)
    p = Player(row=_WP_SCROLL[0], col=_WP_SCROLL[1])
    assert find_next(room, p, _WP_KEYWORD, False) == _WP_KEY_WORD_POS
    assert find_next(room, p, _WP_KEYWORD, True) in _WP_DECOY_POS


@pytest.mark.parametrize('seed', SEEDS)
def test_exit_is_teleport_safe(seed):
    """No mark-jump / line-jump target is the exit: it's not the sanctum row's
    first-non-blank, and it's reachable only through the (blocking) exit lock."""
    room = _room(seed)
    assert _first_non_blank_col(room, 7) != _WP_EXIT[1]
    assert not room.is_passable(*_WP_LOCK)            # lock blocks
    assert room.is_passable(*_WP_EXIT)
    # exit's only orthogonal floor neighbour is the lock cell
    er, ec = _WP_EXIT
    nbrs = [(er + dr, ec + dc) for dr, dc in ((1, 0), (-1, 0), (0, 1), (0, -1))
            if 0 <= er + dr < room.rows and 0 <= ec + dc < room.cols
            and room.cells[er + dr][ec + dc] == CellType.CORRIDOR]
    assert nbrs == [_WP_LOCK]


# ── par path (structure is seed-independent: run once) ───────────────────────
def test_answer_solves_within_budget_and_takes_the_scroll():
    room = _room(42)
    pos, spent, reached, got_scroll = _simulate(_WP_ANSWER, room)
    assert reached, f'answer ended at {pos}, not the exit {_WP_EXIT}'
    assert got_scroll, 'the par route loots the :set number scroll via \'a'
    assert spent == _WP_PAR == 19
    assert spent <= room.budget


def test_skipping_the_scroll_beats_par():
    """Dropping the 'a x detour finishes under par — the scroll is optional."""
    room = _room(42)
    skip = _WP_ANSWER.replace("'a x ", "")            # drop the scroll detour
    pos, spent, reached, got_scroll = _simulate(skip, room)
    assert reached and not got_scroll
    assert spent == _WP_PAR - 3 == 16                 # 'a(2) + x(1) saved
    assert spent < _WP_PAR
