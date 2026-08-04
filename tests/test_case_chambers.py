"""The Case Chambers (slug `case_chambers`): ~ gU gu g~.

"Case is text the eye can't grep." Eight mislabelled corridors on the
Change-Annex chassis where every floor word is letter-perfect but the CASE
rotted; the WEST-wall plaque keeps the true form and the (case-sensitive) tick
opens each bolt when the floor reads true. Case ops edit in place — no reflow.

  TILDE doors — one wrong cell; `~` (1 key) beats `r{c}` (2) and is
    letter-independent.
  UPPER/LOWER doors — scattered wrong cells, all-caps / all-lower target:
    count-~ toggles the CORRECT cells too (wrong text, bolt shut); the
    idempotent gU/gu sweeps fix everything at once. One door is the `.` echo
    of the previous `gue`.
  The gUE door — the target spans ★: `gUe` stops at the symbol and mends half.
  The guu door — two words across a gap, entered mid-row: `gu$` misses the
    head, `^gu$` pays one more; `guu` takes the line.
  The g~~ finale — a fully-inverted MIXED-case line: guu/gUU both write the
    wrong case; only the toggle mends it.

Laws asserted below:
  - every corruption is case-only (same letters, same length);
  - scattered doors are truly scattered (count-~ must die), tilde doors carry
    exactly one wrong cell, the finale is a full inversion of a mixed target;
  - the canonical case-op route wins par-perfect; the wrong-tool routes leave
    their bolts shut; the no-case-op r-chain runs out of budget;
  - no cheaper nav beats par (the anti-cheese audit);
  - the exit is plain floor east of the bolts; no jump reaches it shut.
"""
from collections import deque

from blessed.keyboard import Keystroke
from blessed import Terminal

import vimny.game as main
from vimny.engine.motion import apply_motion
from vimny.engine.player import Player
from vimny.engine.world import CellType
from vimny.content.levels import known_commands
from vimny.generation.dungeon_gen import (
    build_dungeon_case_chambers,
    _CASE_ROWS, _CASE_COLS, _CASE_PAR, _CASE_LESSONS, _CASE_LESSON_ROWS,
    _CASE_COL_S, _CASE_LBL_COL, _CASE_PLQ_COL, _CASE_GATE_ROW, _CASE_GATE_COL0,
    _CASE_EXIT, _CASE_TRIGGERS, _CASE_ANSWER,
)

import math
import pytest

from tests import SEEDS, cached_room

ESC = Keystroke('\x1b', name='KEY_ESCAPE')


def _room(seed):
    return cached_room('build_dungeon_case_chambers', seed)


def _K(s):
    return [Keystroke(ch) for ch in s]


def _bolt(i):
    return (_CASE_GATE_ROW, _CASE_GATE_COL0 + i)


# The canonical case-op route (shared by the tape and the playthrough) — GOLFED:
# `$~` takes the end-of-word tilde (exact-fit floor), `gUU` linewise from
# wherever `j` lands, `.` echoes the `gue`, `5l~` leaves the cursor east so the
# next row is entered mid-line (guu's forcing), `G$` to the door. 30 keys.
def _canon_keys():
    return _K('$~jgUUjguej.jgUEj5l~jguujg~~G$')


# A wasteful-but-winning variant: `^`-prefix the operators and take the door by
# `jj$`. It wins, but spends strictly MORE than par — the nav-cheese regression
# (the Overwrite Halls' `^f`/`^jj$` lesson).
def _wasteful_keys():
    return _K('$~j^gUUj^guej^.j^gUEj^5l~j^guujg~~^jj$')


# The cheapest NO-case-op route: r each wrong cell (letter-dependent, 2 keys a
# cell, plus the walking). It blows the standard budget long before the gate.
def _all_r_keys():
    return (_K('$rn') + _K('j')                        # lanterN
            + _K('rK2hrA2hrL2hrB') + _K('j')           # bUlWaRk (from col 18)
            + _K('lra2lrd2lrn') + _K('j')              # wArDeNs (from col 12)
            + _K('$rehhrihhrahhrg') + _K('j')          # gRaNiTe
            + _K('^rI2lrO3lrG2lrT') + _K('j')          # iRoN★gAtE
            + _K('^5lrs') + _K('j')                    # obeliSk
            + _K('^rd2lrm3lrm2lre') + _K('j')          # DiM eMbEr
            + _K('^rV3lhre...'))                       # never reached: budget dead


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
    return main.run_dungeon(term, 'case_chambers', {}, player_name=name,
                            _dungeon=dungeon)


def _drive_spent(keys, monkeypatch):
    """Drive a route with an UNCAPPED budget and return (won, spent) — the
    par-minimality audit."""
    box = {}
    orig = main._calc_stars
    monkeypatch.setattr(main, '_calc_stars',
                        lambda won, budget, room, player, level='':
                            (box.__setitem__('spent', budget.spent), orig(won, budget, room, player, level))[1])
    dungeon = build_dungeon_case_chambers(SEEDS[0])
    dungeon.rooms[0].budget = 999          # uncap: measure the true keystroke cost
    result = _drive(dungeon, keys, monkeypatch)
    return result['won'], box.get('spent')


# ── structure ─────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("seed", SEEDS)
def test_dimensions_anchors_par_budget(seed):
    room = _room(seed)
    assert (room.rows, room.cols) == (_CASE_ROWS, _CASE_COLS)
    assert room.spawn_pos == (_CASE_LESSON_ROWS[0], _CASE_COL_S)
    assert room.exit_pos == _CASE_EXIT
    assert room.par == _CASE_PAR
    assert room.budget == math.ceil(_CASE_PAR * 1.4)   # STANDARD: volume alone bars the rivals


def test_every_corruption_is_case_only():
    """Same letters, same length — only the case lies (the level's premise)."""
    for kind, target, wrong in _CASE_LESSONS:
        assert len(target) == len(wrong)
        assert target != wrong
        assert target.lower() == wrong.lower(), (target, wrong)


def test_door_shapes_force_their_tools():
    """The shape of each corruption is the forcing:
    tilde = exactly ONE wrong cell; upper/lower/echo = >= 3 wrong cells NOT all
    contiguous (count-~ toggles the correct cells too); upperW spans a non-alpha
    WORD glyph; lowerL and invert carry a space (linewise doors); invert flips
    EVERY letter and its target is mixed-case (guu/gUU both fail)."""
    for kind, target, wrong in _CASE_LESSONS:
        diffs = [i for i in range(len(target)) if target[i] != wrong[i]]
        if kind == 'tilde':
            assert len(diffs) == 1
        if kind in ('upper', 'lower', 'echo', 'upperW'):
            assert len(diffs) >= 3
            assert diffs != list(range(diffs[0], diffs[-1] + 1)), \
                "scattered — a contiguous run would fall to count-~"
        if kind == 'upper':
            assert target.isupper()
        if kind in ('lower', 'echo'):
            assert target.islower()
        if kind == 'upperW':
            assert any(not ch.isalpha() and ch != ' ' for ch in target), \
                "the WORD glyph — e stops there, E does not"
        if kind in ('lowerL', 'invert'):
            assert ' ' in target, "a two-word line — the linewise door"
        if kind == 'invert':
            letters = [i for i, ch in enumerate(target) if ch.isalpha()]
            assert diffs == letters, "every letter flipped"
            assert not target.islower() and not target.isupper(), \
                "MIXED target — gUU/guu both write the wrong case"
    # the echo door immediately follows the lower door it repeats
    kinds = [k for k, _, _ in _CASE_LESSONS]
    assert kinds[kinds.index('echo') - 1] == 'lower'


@pytest.mark.parametrize("seed", SEEDS)
def test_plaque_true_form_floor_wrong_case(seed):
    room = _room(seed)
    for i, (kind, target, wrong) in enumerate(_CASE_LESSONS):
        r = _CASE_LESSON_ROWS[i]
        floor = main._wla_floor_text(room, r)
        assert wrong in floor and target not in floor, (target, wrong)
        # the plaque lives in the WEST wall, off the floor scans
        plq = room.char_run_at(r, _CASE_PLQ_COL)
        assert plq is not None
        assert not room.is_passable(r, _CASE_PLQ_COL)


@pytest.mark.parametrize("seed", SEEDS)
def test_exact_fit_corridors(seed):
    """Each corridor's floor ends where its word ends — `$` lands on the last
    LETTER (the tilde door's nav), never on bare floor east of it."""
    room = _room(seed)
    for i, (kind, target, wrong) in enumerate(_CASE_LESSONS):
        r = _CASE_LESSON_ROWS[i]
        last = _CASE_LBL_COL + len(wrong) - 1
        assert room.is_passable(r, last)
        assert not room.is_passable(r, last + 1)


def test_doors_independent():
    """No target reads inside another target or any wrong word (case-sensitive),
    so each bolt answers only to its own corridor."""
    targets = [t for _, t, _ in _CASE_LESSONS]
    wrongs = [w for _, _, w in _CASE_LESSONS]
    for i, t in enumerate(targets):
        for j, u in enumerate(targets):
            if i != j:
                assert t not in u, (t, u)
        for w in wrongs:
            assert t not in w, (t, w)


# ── access: exit unreachable until the chambers read true ─────────────────────

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
    room = build_dungeon_case_chambers(seed).rooms[0]
    assert _CASE_EXIT not in _reachable(room)


@pytest.mark.parametrize("seed", SEEDS)
def test_no_jump_lands_on_the_shut_exit(seed):
    room = build_dungeon_case_chambers(seed).rooms[0]
    jumps = ([('G', 1, False), ('gg', 1, False), ('H', 1, False),
              ('M', 1, False), ('L', 1, False)]
             + [('G', n, True) for n in range(1, _CASE_ROWS)])
    for motion, count, given in jumps:
        p = Player(row=room.spawn_pos[0], col=room.spawn_pos[1])
        apply_motion(p, motion, count, room, count_given=given)
        assert (p.row, p.col) != _CASE_EXIT, f"{motion} dropped onto the exit"
        assert room.is_passable(p.row, p.col), f"{motion} landed in a wall"


# ── driven for real ───────────────────────────────────────────────────────────

@pytest.mark.parametrize("seed", SEEDS)
def test_full_case_route_wins_par_perfect(seed, monkeypatch):
    dungeon = build_dungeon_case_chambers(seed)
    room = dungeon.rooms[0]
    result = _drive(dungeon, _canon_keys(), monkeypatch)
    assert result['won'] and result['stars'] == 2, result
    for i in range(_CASE_TRIGGERS):
        assert room.cells[_bolt(i)[0]][_bolt(i)[1]] == CellType.FLOOR, "every bolt open"


def test_no_cheaper_nav_beats_par(monkeypatch):
    """Anti-cheese: the golfed route spends exactly par; the ^-heavy variant
    wins but spends strictly more; nothing winning spends less."""
    won_g, spent_g = _drive_spent(_canon_keys(), monkeypatch)
    assert won_g and spent_g == _CASE_PAR, (won_g, spent_g)
    won_w, spent_w = _drive_spent(_wasteful_keys(), monkeypatch)
    assert won_w and spent_w > _CASE_PAR, (won_w, spent_w)
    for won, spent in ((won_g, spent_g), (won_w, spent_w)):
        assert not (won and spent < _CASE_PAR), "a winning route cheaper than par = a mis-set par"


@pytest.mark.parametrize("seed", SEEDS)
def test_all_r_route_is_barred(seed, monkeypatch):
    """Necessity, by volume: r-ing every wrong cell (never a case op) costs 2
    keys a cell plus the walking — it runs out of the standard budget."""
    dungeon = build_dungeon_case_chambers(seed)
    result = _drive(dungeon, _all_r_keys(), monkeypatch)
    assert not result['won'], "the all-r route must run out of budget"


def test_count_tilde_dies_on_a_scattered_door(monkeypatch):
    """`7~` over a scattered-wrong word toggles the CORRECT cells too — the
    bolt stays shut. Wrong means needs-a-toggle only cell by cell; the sweep
    must be the idempotent gU."""
    dungeon = build_dungeon_case_chambers(SEEDS[0])
    room = dungeon.rooms[0]
    _drive(dungeon, _K('$~j^7~'), monkeypatch, finish=':q!\r')
    assert 'BULWARK' not in main._wla_floor_text(room, _CASE_LESSON_ROWS[1])
    assert room.cells[_bolt(1)[0]][_bolt(1)[1]] == CellType.WALL, "bolt still shut"


def test_gUe_mends_only_half_the_word_door(monkeypatch):
    """On the ★-spanning WORD, `e` stops at the symbol: gUe raises the head and
    leaves the tail rotten — gUE's forcing."""
    dungeon = build_dungeon_case_chambers(SEEDS[0])
    room = dungeon.rooms[0]
    _drive(dungeon, _K('$~jgUUjguej.jgUe'), monkeypatch, finish=':q!\r')
    floor = main._wla_floor_text(room, _CASE_LESSON_ROWS[4])
    assert 'IRON★GATE' not in floor
    assert 'IRON★' in floor, "the head was raised — e stopped at the symbol"
    assert room.cells[_bolt(4)[0]][_bolt(4)[1]] == CellType.WALL, "bolt still shut"


def test_gu_dollar_misses_the_head_of_the_line_door(monkeypatch):
    """Entering the two-word line mid-row (the tilde door leaves the cursor
    east), `gu$` lowers only the tail — the head stays rotten. guu's forcing."""
    dungeon = build_dungeon_case_chambers(SEEDS[0])
    room = dungeon.rooms[0]
    _drive(dungeon, _K('$~jgUUjguej.jgUEj5l~jgu$'), monkeypatch, finish=':q!\r')
    floor = main._wla_floor_text(room, _CASE_LESSON_ROWS[6])
    assert 'dim ember' not in floor
    assert room.cells[_bolt(6)[0]][_bolt(6)[1]] == CellType.WALL, "bolt still shut"


def test_guu_and_gUU_both_fail_the_inverted_finale(monkeypatch):
    """The finale's target is MIXED case: forcing to one case writes the wrong
    text either way; only the toggle (g~~) mends it."""
    for wrong_tool in ('guu', 'gUU'):
        dungeon = build_dungeon_case_chambers(SEEDS[0])
        room = dungeon.rooms[0]
        _drive(dungeon, _K('$~jgUUjguej.jgUEj5l~jguuj' + wrong_tool),
               monkeypatch, finish=':q!\r')
        floor = main._wla_floor_text(room, _CASE_LESSON_ROWS[7])
        assert 'Veil Bearer' not in floor, wrong_tool
        assert room.cells[_bolt(7)[0]][_bolt(7)[1]] == CellType.WALL, "bolt still shut"


def test_A_carve_cannot_bypass_the_seal(monkeypatch):
    """Anti-cheese: `A` is known here and builds floor east.
    The exit is the FINAL SEAL (stone until every plaque reads true) and `A` is
    segment-bounded, so neither the throat-carve nor the gate-row A wins."""
    dungeon = build_dungeon_case_chambers(SEEDS[0])
    dungeon.rooms[0].budget = 999
    keys = _K('jjjjjjjj') + _K('A') + _K('xxxxxxxxx') + [ESC] + _K('j')
    result = _drive(dungeon, keys, monkeypatch)
    assert not result['won'], "the throat-carve must not reach the sealed exit"
    dungeon = build_dungeon_case_chambers(SEEDS[0])
    dungeon.rooms[0].budget = 999
    keys = _K('jjjjjjjjj') + _K('A') + [ESC] + _K('h')
    result = _drive(dungeon, keys, monkeypatch)
    assert not result['won'], "segment-bounded A must not vault the shut bolts"


@pytest.mark.parametrize("seed", SEEDS)
def test_undo_rebars_a_bolt(seed, monkeypatch):
    """A case sweep is one snapshot: gUU opens its bolt; `u` unwrites it and the
    stateless tick re-bars."""
    dungeon = build_dungeon_case_chambers(seed)
    room = dungeon.rooms[0]
    _drive(dungeon, _K('$~jgUUl'), monkeypatch, finish=':q!\r')
    assert room.cells[_bolt(1)[0]][_bolt(1)[1]] == CellType.FLOOR, "opened"

    dungeon = build_dungeon_case_chambers(seed)
    room = dungeon.rooms[0]
    _drive(dungeon, _K('$~jgUUluu'), monkeypatch, finish=':q!\r')
    assert room.cells[_bolt(1)[0]][_bolt(1)[1]] == CellType.WALL, "re-barred"


# ── curriculum + karaoke ──────────────────────────────────────────────────────

def test_curriculum_teaches_the_case_family():
    known = set(known_commands('case_chambers'))
    assert {'~', 'gU', 'gu', 'g~', 'r', 'R', 'dot'} <= known
    prior = set(known_commands('overwrite_halls'))     # the level before
    assert not ({'~', 'gU', 'gu', 'g~'} & prior), "the case family is new here"


@pytest.mark.parametrize("seed", SEEDS)
def test_answer_is_the_real_keystroke_tape(seed, monkeypatch):
    """room.answer is the printable keystrokes of the canonical route (spaces
    separators). Driven as admin it advances answer_pos to the end without
    diverging."""
    room = _room(seed)
    assert room.answer == _CASE_ANSWER
    dungeon = build_dungeon_case_chambers(seed)
    troom = dungeon.rooms[0]
    _drive(dungeon, _canon_keys(), monkeypatch, finish=':q!\r', name='admin')
    assert not troom.answer_diverged
    assert troom.answer_pos == len(troom.answer.replace(' ', ''))
