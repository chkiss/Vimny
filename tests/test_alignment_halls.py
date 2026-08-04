"""The Alignment Halls (slug `alignment_halls`): >> << (+ the case reprise).

"Lines shove sideways — and the register line keeps both truths." Five words
on the Annex block, each mis-SET from the shared register column (the │ plumb
glyphs in the wall bands), two mis-CASED as well — the Case Chambers' lesson
reprised one level later. The west-wall plaque keeps the true word in its
TRUE CASE; a bolt stands open while its word reads true-cased with its first
letter EXACTLY on the register line (exact text at the exact column, any
floor row). The exit is the FINAL SEAL.

Laws asserted below:
  - PARITY: every offset is a multiple of INDENT_WIDTH (an odd offset would
    be unreachable by the taught command);
  - the check is two-sided: aligning without re-casing, re-casing without
    aligning, and OVER-shifting all leave (or put) the bolt shut;
  - `apply_indent` ignores wall-embedded runs (the west-wall plaque must
    neither move nor anchor the shift — the engine fix this level forced);
  - the canonical route wins par-perfect; the no-case-op R-retype route WINS
    at 1 star (the reprise is forced by PAR, not the budget); the
    insert-shove opens a bolt (legal) but never beats par;
  - `{n}>>` is Vim-true: the count is ROWS — one 2>> seats the last pair.
"""
from collections import deque

from blessed.keyboard import Keystroke
from blessed import Terminal

import main
from vimny.engine.motion import apply_motion
from vimny.engine.operator import apply_indent, INDENT_WIDTH
from vimny.engine.player import Player
from vimny.engine.world import CellType
from vimny.content.levels import known_commands
from vimny.generation.dungeon_gen import (
    build_dungeon_alignment_halls,
    _AH_ROWS, _AH_COLS, _AH_PAR, _AH_LESSONS, _AH_LESSON_ROWS,
    _AH_COL_S, _AH_PLQ_COL, _AH_GATE_ROW, _AH_GATE_COL0, _AH_REGISTER,
    _AH_BAND_ROWS, _AH_EXIT, _AH_TRIGGERS, _AH_ANSWER,
)

import math
import pytest

from tests import SEEDS, cached_room

ESC = Keystroke('\x1b', name='KEY_ESCAPE')


def _room(seed):
    return cached_room('build_dungeon_alignment_halls', seed)


def _K(s):
    return [Keystroke(ch) for ch in s]


def _bolt(i):
    return (_AH_GATE_ROW, _AH_GATE_COL0 + i)


# The canonical route — the row-3 shift is `.` (repeating >>), `<<` snaps the
# cursor onto the mis-cased first letter so ~ is one key, and one 2>> seats
# the last TWO rows (the count is ROWS — Vim-true). 21 keys.
def _canon_keys():
    return _K('>>j.gUUj<<~j2>>jg~~') + _K('G$')


# The no-case-op rival: shift right, then RETYPE the case by hand (R/r).
# Wins — inside the standard budget — but over par: 1 star, the law working.
def _r_rival_keys():
    return (_K('>>j.') + _K('R') + _K('BEAM') + [ESC]
            + _K('j<<') + _K('rS')
            + _K('j2>>j') + _K('R') + _K('Panel') + [ESC]
            + _K('G$'))


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
    return main.run_dungeon(term, 'alignment_halls', {}, player_name=name,
                            _dungeon=dungeon)


def _drive_spent(keys, monkeypatch):
    box = {}
    orig = main._calc_stars
    monkeypatch.setattr(main, '_calc_stars',
                        lambda won, budget, room, player, level='':
                            (box.__setitem__('spent', budget.spent), orig(won, budget, room, player, level))[1])
    dungeon = build_dungeon_alignment_halls(SEEDS[0])
    dungeon.rooms[0].budget = 999
    result = _drive(dungeon, keys, monkeypatch)
    return result['won'], box.get('spent')


# ── structure ─────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("seed", SEEDS)
def test_dimensions_anchors_par_budget(seed):
    room = _room(seed)
    assert (room.rows, room.cols) == (_AH_ROWS, _AH_COLS)
    assert room.spawn_pos == (_AH_LESSON_ROWS[0], _AH_COL_S)
    assert room.exit_pos == _AH_EXIT
    assert room.par == _AH_PAR
    assert room.budget == math.ceil(_AH_PAR * 1.4)


def test_parity_law_and_lesson_shapes():
    """Every offset is a multiple of INDENT_WIDTH (odd offsets are unreachable
    by >>/<<); the case shapes reprise the Chambers: scattered wrongs for gUU
    (count-~ dies), one wrong char for ~, a full flip with a MIXED target for
    g~~; the last two rows share one offset (the 2>> pair)."""
    for kind, target, wrong, offset in _AH_LESSONS:
        assert offset % INDENT_WIDTH == 0, "PARITY: offset unreachable by >>/<<"
        assert offset != 0, "a seated word at build = a freebie door"
        assert len(target) == len(wrong)
        assert target.lower() == wrong.lower(), "corruption is case-only"
        diffs = [i for i in range(len(target)) if target[i] != wrong[i]]
        if kind in ('shift', 'pair'):
            assert not diffs, "pure shift rows carry true case"
        if kind == 'upper':
            assert target.isupper() and len(diffs) >= 2
            assert diffs != list(range(diffs[0], diffs[-1] + 1)), "scattered"
        if kind == 'tilde':
            assert len(diffs) == 1
        if kind == 'invert':
            assert diffs == [i for i, ch in enumerate(target) if ch.isalpha()]
            assert not target.islower() and not target.isupper(), "MIXED"
    # the count pair: last two lessons, same offset, adjacent rows
    assert _AH_LESSONS[-2][3] == _AH_LESSONS[-1][3]
    assert _AH_LESSON_ROWS[-1] == _AH_LESSON_ROWS[-2] + 1


@pytest.mark.parametrize("seed", SEEDS)
def test_plaques_plumb_line_and_words(seed):
    room = _room(seed)
    for i, (kind, target, wrong, offset) in enumerate(_AH_LESSONS):
        r = _AH_LESSON_ROWS[i]
        floor = main._wla_floor_text(room, r)
        c = _AH_REGISTER + offset
        assert floor[c:c + len(wrong)] == wrong
        assert floor[_AH_REGISTER:_AH_REGISTER + len(target)] != target, "no freebie"
        plq = room.char_run_at(r, _AH_PLQ_COL)
        assert plq is not None and ''.join(plq.symbols) == target
        assert not room.is_passable(r, _AH_PLQ_COL), "plaque in the west wall"
    for br in _AH_BAND_ROWS:
        mark = room.char_run_at(br, _AH_REGISTER)
        assert mark is not None and ''.join(mark.symbols) == '│'
        assert not room.is_passable(br, _AH_REGISTER), "plumb glyphs in the wall"


def test_indent_ignores_wall_embedded_plaques():
    """The engine fix this level forced: the LINE is the passable extent, so a
    west-wall plaque on the same row neither moves nor anchors the shift."""
    room = build_dungeon_alignment_halls(SEEDS[0]).rooms[0]
    r = _AH_LESSON_ROWS[0]
    plq_before = room.char_run_at(r, _AH_PLQ_COL)
    moved = apply_indent(room, r, INDENT_WIDTH)
    assert moved == INDENT_WIDTH, "the floor word shifts"
    floor = main._wla_floor_text(room, r)
    assert floor[_AH_REGISTER:_AH_REGISTER + 6] == 'lintel', "seated by one >>"
    plq_after = room.char_run_at(r, _AH_PLQ_COL)
    assert plq_after is not None, "the plaque never moved"
    assert (plq_after.col, plq_after.symbols) == (plq_before.col, plq_before.symbols)


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
    room = build_dungeon_alignment_halls(seed).rooms[0]
    assert _AH_EXIT not in _reachable(room)


@pytest.mark.parametrize("seed", SEEDS)
def test_no_jump_lands_on_the_shut_exit(seed):
    room = build_dungeon_alignment_halls(seed).rooms[0]
    jumps = ([('G', 1, False), ('gg', 1, False), ('H', 1, False),
              ('M', 1, False), ('L', 1, False)]
             + [('G', n, True) for n in range(1, _AH_ROWS)])
    for motion, count, given in jumps:
        p = Player(row=room.spawn_pos[0], col=room.spawn_pos[1])
        apply_motion(p, motion, count, room, count_given=given)
        assert (p.row, p.col) != _AH_EXIT, f"{motion} dropped onto the exit"
        assert room.is_passable(p.row, p.col), f"{motion} landed in a wall"


# ── the two-sided check, driven ───────────────────────────────────────────────

def test_bolt_opens_on_seat_rebars_on_overshift(monkeypatch):
    """>> seats row one (bolt opens); a second >> carries it PAST the line
    (bolt re-bars); << walks it back (bolt reopens)."""
    dungeon = build_dungeon_alignment_halls(SEEDS[0])
    room = dungeon.rooms[0]
    _drive(dungeon, _K('>>l'), monkeypatch, finish=':q!\r')
    assert room.cells[_bolt(0)[0]][_bolt(0)[1]] == CellType.FLOOR, "seated → open"

    dungeon = build_dungeon_alignment_halls(SEEDS[0])
    room = dungeon.rooms[0]
    _drive(dungeon, _K('>>>>l'), monkeypatch, finish=':q!\r')
    assert room.cells[_bolt(0)[0]][_bolt(0)[1]] == CellType.WALL, "over-shifted → re-bars"

    dungeon = build_dungeon_alignment_halls(SEEDS[0])
    room = dungeon.rooms[0]
    _drive(dungeon, _K('>>>><<l'), monkeypatch, finish=':q!\r')
    assert room.cells[_bolt(0)[0]][_bolt(0)[1]] == CellType.FLOOR, "<< walks it back"


def test_alignment_without_case_and_case_without_alignment_stay_shut(monkeypatch):
    """Row two needs BOTH truths: shifted but mis-cased (j>>) stays shut;
    cased but mis-set (jgUU) stays shut; both together open."""
    dungeon = build_dungeon_alignment_halls(SEEDS[0])
    room = dungeon.rooms[0]
    _drive(dungeon, _K('j>>l'), monkeypatch, finish=':q!\r')
    assert room.cells[_bolt(1)[0]][_bolt(1)[1]] == CellType.WALL, "aligned, still rotten"

    dungeon = build_dungeon_alignment_halls(SEEDS[0])
    room = dungeon.rooms[0]
    _drive(dungeon, _K('jgUUl'), monkeypatch, finish=':q!\r')
    assert room.cells[_bolt(1)[0]][_bolt(1)[1]] == CellType.WALL, "true-cased, off the line"

    dungeon = build_dungeon_alignment_halls(SEEDS[0])
    room = dungeon.rooms[0]
    _drive(dungeon, _K('jgUU>>l'), monkeypatch, finish=':q!\r')
    assert room.cells[_bolt(1)[0]][_bolt(1)[1]] == CellType.FLOOR, "both truths → open"


def test_insert_shove_is_legal_but_never_beats_par(monkeypatch):
    """The frontier rival: i+junk shoves the word onto the line — the slice
    check tolerates junk west of it, so the bolt OPENS (a legal route). It
    costs 5 keys where >> costs 2, so it can never undercut par."""
    dungeon = build_dungeon_alignment_halls(SEEDS[0])
    room = dungeon.rooms[0]
    _drive(dungeon, _K('4li') + _K('xx') + [ESC], monkeypatch, finish=':q!\r')
    assert room.cells[_bolt(0)[0]][_bolt(0)[1]] == CellType.FLOOR, "shove opens the bolt"


# ── driven for real ───────────────────────────────────────────────────────────

@pytest.mark.parametrize("seed", SEEDS)
def test_full_alignment_route_wins_par_perfect(seed, monkeypatch):
    dungeon = build_dungeon_alignment_halls(seed)
    room = dungeon.rooms[0]
    result = _drive(dungeon, _canon_keys(), monkeypatch)
    assert result['won'] and result['stars'] == 2, result
    for i in range(_AH_TRIGGERS):
        assert room.cells[_bolt(i)[0]][_bolt(i)[1]] == CellType.FLOOR, "every bolt open"


def test_no_cheaper_nav_beats_par(monkeypatch):
    won, spent = _drive_spent(_canon_keys(), monkeypatch)
    assert won and spent == _AH_PAR, (won, spent)
    won_r, spent_r = _drive_spent(_r_rival_keys(), monkeypatch)
    assert won_r and spent_r > _AH_PAR, "the R-retype must cost more than par"


@pytest.mark.parametrize("seed", SEEDS)
def test_no_case_op_route_wins_at_one_star(seed, monkeypatch):
    """THE LAW, driven: the no-case-op R/r-retype route WINS — inside the
    standard budget — but over par: 1 star. The case reprise is forced by
    PAR, not by an unwinnable budget."""
    dungeon = build_dungeon_alignment_halls(seed)
    result = _drive(dungeon, _r_rival_keys(), monkeypatch)
    assert result['won'] and result['stars'] == 1, result


def test_undo_rebars_bolt_and_seal(monkeypatch):
    dungeon = build_dungeon_alignment_halls(SEEDS[0])
    room = dungeon.rooms[0]
    _drive(dungeon, _K('>>j.gUUj<<~j2>>jg~~') + _K('l'), monkeypatch, finish=':q!\r')
    assert room.cells[_bolt(4)[0]][_bolt(4)[1]] == CellType.FLOOR
    assert room.cells[_AH_EXIT[0]][_AH_EXIT[1]] == CellType.FLOOR, "the seal parted"

    dungeon = build_dungeon_alignment_halls(SEEDS[0])
    room = dungeon.rooms[0]
    # uu: the walk pushes its own snapshot, the second u reaches the g~~
    _drive(dungeon, _K('>>j.gUUj<<~j2>>jg~~') + _K('luu'), monkeypatch, finish=':q!\r')
    assert room.cells[_bolt(4)[0]][_bolt(4)[1]] == CellType.WALL, "re-bars"
    assert room.cells[_AH_EXIT[0]][_AH_EXIT[1]] == CellType.WALL, "the seal returns"


@pytest.mark.parametrize("seed", SEEDS)
def test_A_carve_cannot_bypass_the_seal(seed, monkeypatch):
    dungeon = build_dungeon_alignment_halls(seed)
    dungeon.rooms[0].budget = 999
    keys = _K('jjjjjj') + _K('A') + _K('xxxxxx') + [ESC] + _K('j')
    result = _drive(dungeon, keys, monkeypatch)
    assert not result['won'], "the throat-carve must not reach the sealed exit"


# ── curriculum + karaoke ──────────────────────────────────────────────────────

def test_curriculum_teaches_indent_keeps_case_and_dot():
    known = set(known_commands('alignment_halls'))
    assert {'>', '<'} <= known
    assert {'~', 'gU', 'g~', 'dot'} <= known, "the reprise rides known verbs"
    prior = set(known_commands('joiners_gate'))        # the level before
    assert not ({'>', '<'} & prior), "the indent family is new here"


@pytest.mark.parametrize("seed", SEEDS)
def test_answer_is_the_real_keystroke_tape(seed, monkeypatch):
    room = _room(seed)
    assert room.answer == _AH_ANSWER
    dungeon = build_dungeon_alignment_halls(seed)
    troom = dungeon.rooms[0]
    _drive(dungeon, _canon_keys(), monkeypatch, finish=':q!\r', name='admin')
    assert not troom.answer_diverged
    assert troom.answer_pos == len(troom.answer.replace(' ', ''))
