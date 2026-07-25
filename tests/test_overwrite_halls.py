"""The Overwrite Halls (slug `overwrite_halls`): R.

"Streams, not stitches." The player owns `r` (replace one) and `.` (repeat); `R`
(overtype mode) earns its place where corrections run in CONSECUTIVE cells. Five
mislabelled corridors on the Change-Annex chassis (WEST-wall plaque = the true
word; the floor has it wrong; a bolt opens when the floor reads true):

  STREAM doors — a run of 3 consecutive VARIED wrong cells buried MID-word. `R`
    overtypes the run in place and leaves the correct prefix/suffix untouched.
    Every rival overpays: `.` repeats one char (a varied run kills it), the
    `r`-chain is `r{c}l` per cell, `S`/`cc` (known here) clobber the correct
    prefix+suffix and retype the WHOLE word. FORCING by VOLUME: the budget bars
    the cheapest no-R route (all-`S`) by one — par + _OH_SAVING − 1.
  STITCH doors — a SINGLE wrong cell where `r` still rules (`R` merely ties).

Laws asserted below:
  - the streams carry a consecutive varied run; the stitches a single diff;
  - the canonical R route wins par-perfect, and the all-S route runs out of
    budget (R is necessary), while `.` cannot mend a varied run;
  - the exit is plain floor east of the bolts; no jump reaches it shut.
"""
from collections import deque

from blessed.keyboard import Keystroke
from blessed import Terminal

import main
from engine.motion import apply_motion
from engine.player import Player
from engine.world import CellType
from content.levels import known_commands
from generation.dungeon_gen import (
    build_dungeon_overwrite_halls,
    _OH_ROWS, _OH_COLS, _OH_PAR, _OH_SAVING, _OH_LESSONS, _OH_LESSON_ROWS,
    _OH_COL_S, _OH_LBL_COL, _OH_PLQ_COL, _OH_GATE_ROW, _OH_GATE_COL0,
    _OH_EXIT, _OH_TRIGGERS,
)

import math
import pytest

from tests import SEEDS, cached_room

ESC = Keystroke('\x1b', name='KEY_ESCAPE')


def _room(seed):
    return cached_room('build_dungeon_overwrite_halls', seed)


def _K(s):
    return [Keystroke(ch) for ch in s]


def _bolt(i):
    return (_OH_GATE_ROW, _OH_GATE_COL0 + i)


# The canonical R route (shared by the tape and the playthrough) — GOLFED: `F`
# (backward-find) back to each run, the C4 stitch taken FREE (the descent lands
# the cursor on it), and `G$` to the door. 30 keys.
def _canon_keys():
    return (_K('fx') + _K('R') + _K('evi') + [ESC] + _K('j')
            + _K('Fx') + _K('re') + _K('j')
            + _K('Fx') + _K('R') + _K('rne') + [ESC] + _K('j')
            + _K('re') + _K('j')
            + _K('Fx') + _K('R') + _K('lve') + [ESC]
            + _K('G') + _K('$'))


# The OLD hand-route shape that once mis-set par: `^f` back to each run and
# `^jj$` to the door — every one a wasteful stand-in for `F` / `G$`. It still
# wins, but spends MORE than par. Kept as a cheese regression.
def _old_nav_keys():
    return (_K('fx') + _K('R') + _K('evi') + [ESC] + _K('j')
            + _K('^') + _K('fx') + _K('re') + _K('j')
            + _K('^') + _K('fx') + _K('R') + _K('rne') + [ESC] + _K('j')
            + _K('^') + _K('fa') + _K('re') + _K('j')
            + _K('^') + _K('fx') + _K('R') + _K('lve') + [ESC]
            + _K('^') + _K('j') + _K('j') + _K('$'))


def _all_S_keys():
    """The cheapest no-R route: change the whole word on each stream (S), r the
    stitches. Costs par + _OH_SAVING, one past the budget."""
    return (_K('S') + _K('believing') + [ESC] + _K('j')
            + _K('Fx') + _K('re') + _K('j')
            + _K('S') + _K('earned') + [ESC] + _K('j')
            + _K('Fa') + _K('re') + _K('j')
            + _K('S') + _K('silver') + [ESC]
            + _K('G') + _K('$'))


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
    return main.run_dungeon(term, 'overwrite_halls', {}, player_name=name,
                            _dungeon=dungeon)


def _drive_spent(keys, monkeypatch):
    """Drive a route with an UNCAPPED budget and return (won, spent) — used to
    audit whether any route beats par (a mis-set par = a cheese)."""
    box = {}
    orig = main._calc_stars
    monkeypatch.setattr(main, '_calc_stars',
                        lambda won, budget, room, player, level='':
                            (box.__setitem__('spent', budget.spent), orig(won, budget, room, player, level))[1])
    dungeon = build_dungeon_overwrite_halls(SEEDS[0])
    dungeon.rooms[0].budget = 999          # uncap: measure the true keystroke cost
    result = _drive(dungeon, keys, monkeypatch)
    return result['won'], box.get('spent')


# ── structure ─────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("seed", SEEDS)
def test_dimensions_anchors_par_budget(seed):
    room = _room(seed)
    assert (room.rows, room.cols) == (_OH_ROWS, _OH_COLS)
    assert room.spawn_pos == (_OH_LESSON_ROWS[0], _OH_COL_S)
    assert room.exit_pos == _OH_EXIT
    assert room.par == _OH_PAR
    # TIGHT (Annex model): budget one below the all-S route, so it overshoots
    assert room.budget == math.ceil(_OH_PAR * 1.4)   # STANDARD


def test_streams_carry_a_consecutive_varied_run_stitches_a_single_diff():
    """Each STREAM word differs from its plaque in a CONTIGUOUS run of >= 2 cells
    whose target chars are varied (no two adjacent equal → `.` dies); each STITCH
    differs in exactly ONE cell (r's niche)."""
    for kind, _prefix, target, wrong in _OH_LESSONS:
        assert len(target) == len(wrong)
        diffs = [i for i in range(len(target)) if target[i] != wrong[i]]
        if kind == 'stream':
            assert len(diffs) >= 2
            assert diffs == list(range(diffs[0], diffs[-1] + 1)), "the run is contiguous"
            run = target[diffs[0]:diffs[-1] + 1]
            assert all(run[i] != run[i + 1] for i in range(len(run) - 1)), \
                "varied run — no two adjacent equal, so `.` cannot repeat it"
        else:
            assert len(diffs) == 1, "a stitch is a single wrong cell"


@pytest.mark.parametrize("seed", SEEDS)
def test_stone_prefix_true_saying_floor_wrong_word(seed):
    """Sense, not decree: the saying's start is carved in the west stone
    (WALL cells, off the floor scans), right-aligned two cols shy of the
    spine; the floor holds only the wrong finishing word."""
    room = _room(seed)
    for i, (kind, prefix, target, wrong) in enumerate(_OH_LESSONS):
        r = _OH_LESSON_ROWS[i]
        stones = [ru for ru in room.char_runs
                  if ru.row == r and ru.kind == 'verdant']
        assert stones, r
        for ru in stones:
            for k in range(len(ru.symbols)):
                assert room.cells[r][ru.col + k] == CellType.WALL
        assert max(ru.col + len(ru.symbols) - 1 for ru in stones) == _OH_COL_S - 2
        text = ' '.join(''.join(ru.symbols)
                        for ru in sorted(stones, key=lambda u: u.col))
        assert text == prefix
        floor = main._wla_floor_text(room, r)
        assert wrong in floor and target not in floor, (target, wrong)


@pytest.mark.parametrize("seed", SEEDS)
def test_doors_independent(seed):
    """No target reads inside another target or any wrong word, so each bolt
    answers only to its own corridor."""
    targets = [t for _, _, t, _ in _OH_LESSONS]
    wrongs = [w for _, _, _, w in _OH_LESSONS]
    for i, t in enumerate(targets):
        for j, u in enumerate(targets):
            if i != j:
                assert t not in u, (t, u)
        for w in wrongs:
            assert t not in w, (t, w)


# ── access: exit unreachable until the halls read true ────────────────────────

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
    room = build_dungeon_overwrite_halls(seed).rooms[0]
    assert _OH_EXIT not in _reachable(room)


@pytest.mark.parametrize("seed", SEEDS)
def test_no_jump_lands_on_the_shut_exit(seed):
    room = build_dungeon_overwrite_halls(seed).rooms[0]
    jumps = ([('G', 1, False), ('gg', 1, False), ('H', 1, False),
              ('M', 1, False), ('L', 1, False)]
             + [('G', n, True) for n in range(1, _OH_ROWS)])
    for motion, count, given in jumps:
        p = Player(row=room.spawn_pos[0], col=room.spawn_pos[1])
        apply_motion(p, motion, count, room, count_given=given)
        assert (p.row, p.col) != _OH_EXIT, f"{motion} dropped onto the exit"
        assert room.is_passable(p.row, p.col), f"{motion} landed in a wall"


# ── driven for real ───────────────────────────────────────────────────────────

@pytest.mark.parametrize("seed", SEEDS)
def test_full_R_route_wins_par_perfect(seed, monkeypatch):
    dungeon = build_dungeon_overwrite_halls(seed)
    room = dungeon.rooms[0]
    result = _drive(dungeon, _canon_keys(), monkeypatch)
    assert result['won'] and result['stars'] == 2, result
    for i in range(_OH_TRIGGERS):
        assert room.cells[_bolt(i)[0]][_bolt(i)[1]] == CellType.FLOOR, "every bolt open"


def test_no_cheaper_nav_beats_par(monkeypatch):
    """Anti-cheese: par must be the MINIMUM keystroke cost, so NO winning route may
    spend less than par. test_answer_paths only checks the canonical answer WINS —
    it never checks par is minimal, which is how the first hand-route (`^f`, `^jj$`)
    inflated par to 38 and slipped through. Here the golfed route is par, and the
    wasteful old-nav route wins but spends strictly MORE (never less)."""
    won_g, spent_g = _drive_spent(_canon_keys(), monkeypatch)
    assert won_g and spent_g == _OH_PAR, (won_g, spent_g)
    won_o, spent_o = _drive_spent(_old_nav_keys(), monkeypatch)
    assert won_o and spent_o > _OH_PAR, "the ^f/^jj$ nav must cost MORE than par, not define it"
    # the general invariant: neither driven route wins for less than par
    for won, spent in ((won_g, spent_g), (won_o, spent_o)):
        assert not (won and spent < _OH_PAR), "a winning route cheaper than par = a mis-set par"


@pytest.mark.parametrize("seed", SEEDS)
def test_all_S_route_is_barred(seed, monkeypatch):
    """Necessity by PAR, not by budget (par-is-the-optimum law, 2026-07-25).
    Mending every stream with `S` (never `R`) costs par + _OH_SAVING. It used to
    be BARRED by a hand-tightened budget; the budget is now the standard 1.4x,
    so it WINS — and loses the second star."""
    dungeon = build_dungeon_overwrite_halls(seed)
    result = _drive(dungeon, _all_S_keys(), monkeypatch)
    assert result['won'] and result['stars'] == 1, result


def test_dot_cannot_mend_a_varied_run(monkeypatch):
    """`.` repeats ONE char, so on a varied run it lays the wrong letters and the
    bolt stays shut — the Echo Vault's dot lesson, inverted."""
    dungeon = build_dungeon_overwrite_halls(SEEDS[0])
    room = dungeon.rooms[0]
    # r the first run cell, then dot along it (repeats that one char)
    keys = _K('fx') + _K('re') + _K('l') + _K('.') + _K('l') + _K('.')
    _drive(dungeon, keys, monkeypatch, finish=':q!\r')
    assert 'believing' not in main._wla_floor_text(room, _OH_LESSON_ROWS[0])
    assert room.cells[_bolt(0)[0]][_bolt(0)[1]] == CellType.WALL, "bolt still shut"


def test_A_carve_cannot_bypass_the_seal(monkeypatch):
    """Anti-cheese (found 2026-07-12): `A` is known here and builds floor east,
    so a player could carve along the throat row and drop past the bolts — and
    row-global `A` used to vault the shut bolts outright. The exit is now the
    FINAL SEAL (stone until every plaque reads true) and `A` is segment-bounded,
    so neither carve route wins."""
    # carve the throat row east, then j down toward the exit
    dungeon = build_dungeon_overwrite_halls(SEEDS[0])
    dungeon.rooms[0].budget = 999
    keys = _K('jjjjj') + _K('A') + _K('xxxxxx') + [ESC] + _K('j')
    result = _drive(dungeon, keys, monkeypatch)
    assert not result['won'], "the throat-carve must not reach the sealed exit"
    # A on the gate row itself must stop at the cursor's segment (the spine)
    dungeon = build_dungeon_overwrite_halls(SEEDS[0])
    dungeon.rooms[0].budget = 999
    room = dungeon.rooms[0]
    keys = _K('jjjjjj') + _K('A') + [ESC] + _K('h')
    result = _drive(dungeon, keys, monkeypatch)
    assert not result['won'], "segment-bounded A must not vault the shut bolts"


@pytest.mark.parametrize("seed", SEEDS)
def test_undo_rebars_a_bolt(seed, monkeypatch):
    """One overtype run is one snapshot: `R`-ing a stream opens its bolt; `u`
    unwrites it and the tick re-bars (stateless, undo-safe)."""
    dungeon = build_dungeon_overwrite_halls(seed)
    room = dungeon.rooms[0]
    _drive(dungeon, _K('fx') + _K('R') + _K('evi') + [ESC] + _K('l'),
           monkeypatch, finish=':q!\r')
    assert room.cells[_bolt(0)[0]][_bolt(0)[1]] == CellType.FLOOR, "opened"

    dungeon = build_dungeon_overwrite_halls(seed)
    room = dungeon.rooms[0]
    _drive(dungeon, _K('fx') + _K('R') + _K('evi') + [ESC] + _K('l') + _K('uu'),
           monkeypatch, finish=':q!\r')
    assert room.cells[_bolt(0)[0]][_bolt(0)[1]] == CellType.WALL, "re-barred"


# ── curriculum + karaoke ──────────────────────────────────────────────────────

def test_curriculum_teaches_R_and_keeps_r():
    known = set(known_commands('overwrite_halls'))
    assert {'R', 'r', 'dot'} <= known
    prior = set(known_commands('sculpting_chambers'))     # the level before
    assert 'R' not in prior, "R is new here"


@pytest.mark.parametrize("seed", SEEDS)
def test_answer_is_the_real_keystroke_tape(seed, monkeypatch):
    """room.answer is the printable keystrokes of the canonical route (Esc
    omitted, spaces separators). Driven as admin it advances answer_pos to the
    end without diverging — R-mode chars advance the tape too."""
    room = _room(seed)
    assert room.answer == 'fx Revi j Fx re j Fx Rrne j re j Fx Rlve G$'
    dungeon = build_dungeon_overwrite_halls(seed)
    troom = dungeon.rooms[0]
    _drive(dungeon, _canon_keys(), monkeypatch, finish=':q!\r', name='admin')
    assert not troom.answer_diverged
    assert troom.answer_pos == len(troom.answer.replace(' ', ''))
