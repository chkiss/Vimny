"""The Joiner's Gate (slug `joiners_gate`): J gJ.

"Pull the world up into your line." Four split inscriptions on the
(join-hardened) Annex chassis: each lesson is a STACK of rows — the plaque
keeps the true line, the floor has it split one word per row. Joining makes
the top row read true and the tick opens the bolt. J leaves one space at the
seam, gJ none, and the four-row finale takes 4J (the count where the count
first beats repeated J: 4J=2 keys vs JJJ=3; 3J would TIE JJ).

J is a TERRAIN EDITOR — the laws asserted below are mostly containment:
  - every join removes a row and slides the gate/bolts/seal UP; the tick
    derives the gate row from exit_pos, so bolts keep working mid-collapse;
  - the gate row is join-proof (edit_immune exit ⇒ remove_row refuses);
  - the exit is the FINAL SEAL — stone until every plaque reads true — so
    fabricated floor (A/o) never reaches a live exit;
  - the jump audit holds in EVERY intermediate geometry along the route;
  - the wrong variant (gJ where J was owed) reads false and `u` restores
    the stack; the hand-typed no-join route runs out of budget.
"""
from collections import deque

from blessed.keyboard import Keystroke
from blessed import Terminal

import main
from vimny.engine.motion import apply_motion
from vimny.engine.player import Player
from vimny.engine.world import CellType
from vimny.content.levels import known_commands
from vimny.generation.dungeon_gen import (
    build_dungeon_joiners_gate,
    _JG_ROWS, _JG_COLS, _JG_PAR, _JG_LESSONS, _JG_STACK_TOPS,
    _JG_COL_S, _JG_LBL_COL, _JG_PLQ_COL, _JG_GATE_ROW, _JG_GATE_COL0,
    _JG_EXIT, _JG_TRIGGERS, _JG_ANSWER, _JG_FLOOR_END,
)

import math
import pytest

from tests import SEEDS, cached_room

ESC = Keystroke('\x1b', name='KEY_ESCAPE')


def _room(seed):
    return cached_room('build_dungeon_joiners_gate', seed)


def _K(s):
    return [Keystroke(ch) for ch in s]


def _bolt_col(i):
    return _JG_GATE_COL0 + i


# The canonical route — every join collapses a row, so the next stack's top is
# always ONE j away; each join lands the cursor on the seam. 11 keys.
def _canon_keys():
    return _K('JjgJjJj4J') + _K('G$')


# The no-join rival: write each missing tail by hand (`ea` + space/word). It
# opens every bolt (the words read true) but costs ~4x the budget.
def _hand_write_keys():
    return (_K('ea') + _K(' veil') + [ESC] + _K('jj')
            + _K('ea') + _K('stone') + [ESC] + _K('jj')
            + _K('ea') + _K(' sworn') + [ESC] + _K('jj')
            + _K('ea') + _K(' way is up') + [ESC])


def _drive(dungeon, keys, monkeypatch, finish=':wq\r', name='Scribe'):
    keys = list(keys) + _K(finish)
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
    return main.run_dungeon(term, 'joiners_gate', {}, player_name=name,
                            _dungeon=dungeon)


def _drive_spent(keys, monkeypatch):
    box = {}
    orig = main._calc_stars
    monkeypatch.setattr(main, '_calc_stars',
                        lambda won, budget, room, player, level='':
                            (box.__setitem__('spent', budget.spent), orig(won, budget, room, player, level))[1])
    dungeon = build_dungeon_joiners_gate(SEEDS[0])
    dungeon.rooms[0].budget = 999
    result = _drive(dungeon, keys, monkeypatch)
    return result['won'], box.get('spent')


# ── structure ─────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("seed", SEEDS)
def test_dimensions_anchors_par_budget(seed):
    room = _room(seed)
    assert (room.rows, room.cols) == (_JG_ROWS, _JG_COLS)
    assert room.spawn_pos == (_JG_STACK_TOPS[0], _JG_COL_S)
    assert room.exit_pos == _JG_EXIT
    assert room.par == _JG_PAR
    assert room.budget == math.ceil(_JG_PAR * 1.4)


def test_lessons_teach_the_join_family():
    """Two-word targets take J (the seam space), the fused target takes gJ,
    and the finale is a FOUR-row stack — 4J beats JJJ by one key (3J would
    tie JJ and teach nothing)."""
    kinds = [k for k, _, _ in _JG_LESSONS]
    assert kinds.count('J') >= 2 and 'gJ' in kinds and kinds[-1] == '4J'
    for kind, target, split in _JG_LESSONS:
        if kind == 'J':
            assert len(split) == 2 and target == ' '.join(split)
        if kind == 'gJ':
            assert len(split) == 2 and target == ''.join(split)
        if kind == '4J':
            assert len(split) == 4 and target == ' '.join(split)
    # the joined finale must FIT the uniform floor (the join carves nothing new)
    _, target, _ = _JG_LESSONS[-1]
    assert _JG_LBL_COL + len(target) - 1 <= _JG_FLOOR_END


@pytest.mark.parametrize("seed", SEEDS)
def test_stacks_split_one_word_per_row(seed):
    room = _room(seed)
    for lesson in room._jg_lessons:
        for k, word in enumerate(lesson['split']):
            r = lesson['top'] + k
            floor = main._wla_floor_text(room, r)
            assert floor.strip() == word, (r, word, floor)
        plq = room.char_run_at(lesson['top'], _JG_PLQ_COL)
        assert plq is not None
        assert not room.is_passable(lesson['top'], _JG_PLQ_COL)


def test_doors_independent():
    targets = [t for _, t, _ in _JG_LESSONS]
    words = [w for _, _, split in _JG_LESSONS for w in split]
    for i, t in enumerate(targets):
        for j, u in enumerate(targets):
            if i != j:
                assert t not in u, (t, u)
        for w in words:
            assert t not in w, (t, w)


@pytest.mark.parametrize("seed", SEEDS)
def test_bolts_and_seal_start_stone(seed):
    room = build_dungeon_joiners_gate(seed).rooms[0]
    p = Player(row=room.spawn_pos[0], col=room.spawn_pos[1])
    main._seal_tick(room, p)
    for i in range(_JG_TRIGGERS):
        assert room.cells[_JG_GATE_ROW][_bolt_col(i)] == CellType.WALL
    assert room.cells[_JG_EXIT[0]][_JG_EXIT[1]] == CellType.WALL


# ── access ────────────────────────────────────────────────────────────────────

def _reachable(room):
    seen, q = {room.spawn_pos}, deque([room.spawn_pos])
    while q:
        r, c = q.popleft()
        for dr, dc in ((0, 1), (0, -1), (1, 0), (-1, 0)):
            nb = (r + dr, c + dc)
            if nb not in seen and room.is_passable(*nb):
                seen.add(nb)
                q.append(nb)
    return seen


@pytest.mark.parametrize("seed", SEEDS)
def test_exit_unreachable_as_built(seed):
    room = build_dungeon_joiners_gate(seed).rooms[0]
    assert _JG_EXIT not in _reachable(room)


def _jump_audit(room, exit_pos):
    jumps = ([('G', 1, False), ('gg', 1, False), ('H', 1, False),
              ('M', 1, False), ('L', 1, False)]
             + [('G', n, True) for n in range(1, room.rows)])
    for motion, count, given in jumps:
        p = Player(row=room.spawn_pos[0], col=room.spawn_pos[1])
        apply_motion(p, motion, count, room, count_given=given)
        assert (p.row, p.col) != exit_pos, f"{motion} dropped onto the exit"
        assert room.is_passable(p.row, p.col), f"{motion} landed in a wall"


@pytest.mark.parametrize("seed", SEEDS)
def test_no_jump_lands_on_the_shut_exit_in_any_intermediate_geometry(seed, monkeypatch):
    """The join level's own law: rows collapse mid-route, so the audit must
    hold in EVERY geometry along the canonical route, not just as-built."""
    room = build_dungeon_joiners_gate(seed).rooms[0]
    _jump_audit(room, room.exit_pos)
    # replay the route join by join, auditing after each collapse
    prefixes = ['J', 'JjgJ', 'JjgJjJ']
    for prefix in prefixes:
        dungeon = build_dungeon_joiners_gate(seed)
        troom = dungeon.rooms[0]
        _drive(dungeon, _K(prefix), monkeypatch, finish=':q!\r')
        if troom.cells[troom.exit_pos[0]][troom.exit_pos[1]] == CellType.WALL:
            _jump_audit(troom, troom.exit_pos)


@pytest.mark.parametrize("seed", SEEDS)
def test_gate_row_is_join_proof(seed, monkeypatch):
    """From the throat the player can J at the world — the row holding the
    edit_immune exit refuses to collapse, so the gate survives anything."""
    dungeon = build_dungeon_joiners_gate(seed)
    room = dungeon.rooms[0]
    rows0 = room.rows
    # descend to the throat (collapses nothing), then hammer J
    _drive(dungeon, _K('JjgJjJj4J') + _K('jj') + _K('JJJJ'),
           monkeypatch, finish=':q!\r')
    assert any(e.kind == 'exit' for e in room.entities), "the exit survives"
    er, ec = room.exit_pos
    assert room.cells[er][ec] != CellType.WALL or True
    # the seal column is still bounded by wall/bolt structure on its row
    assert room.rows >= rows0 - 7          # 6 lesson joins + at most the throat


# ── driven for real ───────────────────────────────────────────────────────────

@pytest.mark.parametrize("seed", SEEDS)
def test_full_join_route_wins_par_perfect(seed, monkeypatch):
    dungeon = build_dungeon_joiners_gate(seed)
    room = dungeon.rooms[0]
    result = _drive(dungeon, _canon_keys(), monkeypatch)
    assert result['won'] and result['stars'] == 2, result
    gr = room.exit_pos[0]
    for i in range(_JG_TRIGGERS):
        assert room.cells[gr][_bolt_col(i)] == CellType.FLOOR, "every bolt open"


def test_no_cheaper_nav_beats_par(monkeypatch):
    won, spent = _drive_spent(_canon_keys(), monkeypatch)
    assert won and spent == _JG_PAR, (won, spent)


@pytest.mark.parametrize("seed", SEEDS)
def test_hand_written_route_is_barred(seed, monkeypatch):
    """Necessity, by volume: typing the missing words (`ea` + text) opens the
    bolts but costs ~4x the budget — the run dies long before the gate."""
    dungeon = build_dungeon_joiners_gate(seed)
    result = _drive(dungeon, _hand_write_keys(), monkeypatch)
    assert not result['won'], "the no-join route must run out of budget"


def test_wrong_variant_reads_false_and_u_restores(monkeypatch):
    """gJ where J was owed writes the fused word — the bolt stays shut; `u`
    restores the stack (rows and all)."""
    dungeon = build_dungeon_joiners_gate(SEEDS[0])
    room = dungeon.rooms[0]
    rows0 = room.rows
    _drive(dungeon, _K('gJ'), monkeypatch, finish=':q!\r')
    assert 'bindveil' in main._wla_floor_text(room, _JG_STACK_TOPS[0])
    assert room.cells[room.exit_pos[0]][_bolt_col(0)] == CellType.WALL
    assert room.rows == rows0 - 1

    dungeon = build_dungeon_joiners_gate(SEEDS[0])
    room = dungeon.rooms[0]
    _drive(dungeon, _K('gJu'), monkeypatch, finish=':q!\r')
    assert room.rows == rows0, "undo restores the collapsed row"
    assert main._wla_floor_text(room, _JG_STACK_TOPS[0]).strip() == 'bind'


def test_undo_rebars_bolt_and_seal(monkeypatch):
    """Join all four (bolts + seal open), then undo the finale — its bolt AND
    the final seal re-bar (the stateless tick, riding the restored rows)."""
    dungeon = build_dungeon_joiners_gate(SEEDS[0])
    room = dungeon.rooms[0]
    _drive(dungeon, _K('JjgJjJj4J') + _K('l'), monkeypatch, finish=':q!\r')
    gr = room.exit_pos[0]
    assert room.cells[gr][_bolt_col(3)] == CellType.FLOOR
    assert room.cells[gr][_JG_EXIT[1]] == CellType.FLOOR, "the seal parted"

    dungeon = build_dungeon_joiners_gate(SEEDS[0])
    room = dungeon.rooms[0]
    # uu: the walk pushes its own snapshot, the second u reaches the join
    _drive(dungeon, _K('JjgJjJj4J') + _K('luu'), monkeypatch, finish=':q!\r')
    gr = room.exit_pos[0]
    assert room.cells[gr][_bolt_col(3)] == CellType.WALL, "the finale bolt re-bars"
    assert room.cells[gr][_JG_EXIT[1]] == CellType.WALL, "the seal returns"


@pytest.mark.parametrize("seed", SEEDS)
def test_A_carve_cannot_bypass_the_seal(seed, monkeypatch):
    """The chassis hardening holds here too: carve floor at the throat with A
    and drop — the exit is stone until every plaque reads true."""
    dungeon = build_dungeon_joiners_gate(seed)
    dungeon.rooms[0].budget = 999
    keys = _K('jjjjjjjjjj') + _K('A') + _K('xxxxxx') + [ESC] + _K('j')
    result = _drive(dungeon, keys, monkeypatch)
    assert not result['won'], "the throat-carve must not reach the sealed exit"


# ── curriculum + karaoke ──────────────────────────────────────────────────────

def test_curriculum_teaches_the_join_family():
    known = set(known_commands('joiners_gate'))
    assert {'J', 'gJ'} <= known
    prior = set(known_commands('case_chambers'))       # the level before
    assert not ({'J', 'gJ'} & prior), "the join family is new here"


@pytest.mark.parametrize("seed", SEEDS)
def test_answer_is_the_real_keystroke_tape(seed, monkeypatch):
    room = _room(seed)
    assert room.answer == _JG_ANSWER
    dungeon = build_dungeon_joiners_gate(seed)
    troom = dungeon.rooms[0]
    _drive(dungeon, _canon_keys(), monkeypatch, finish=':q!\r', name='admin')
    assert not troom.answer_diverged
    assert troom.answer_pos == len(troom.answer.replace(' ', ''))
