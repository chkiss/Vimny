"""The Indentation Sanctum (slug `indentation_sanctum`): >{m} <{m} =.

"In these halls, the law of = is posted." `=` is Vim's policy socket; Vimny's
`=` applies the BLOCK LAW (engine/operator.law_column): a verse under a ':'
line stands one step deeper, 'end' returns to its opener's station, and
UNGOVERNED verse stands at the wall — the gg=G-in-markdown disaster, kept
faithfully as a playable trap. Three bays, one verb each:

  the UNGOVERNED GALLERY  — plain nouns 2 west of the plumb line: `>}`;
                            `=` here RAZES the bank to the wall (u recovers);
  the OVER-SHOVED GALLERY — the mirror: `<}`;
  the SANCTUM'S RITE      — seeded pseudocode with SCATTERED offsets: no
                            uniform shift can satisfy it; `=}` snaps it true.

Laws asserted below:
  - the law function is what the door check calls (solver == judge);
  - `=` mis-razes ungoverned verse and the bolt stays shut;
  - the canonical `>} 4j <} M =} G$` wins par-perfect (11);
  - the manual-mason route (no `=`) WINS at 1 star under the hand-set
    budget — forcing by PAR, not an unwinnable wall;
  - uniform `>{m}`/`<{m}` strokes cannot satisfy the scattered rite;
  - rite offsets are heterogeneous, even (parity), and include one
    already-true row (idempotence);
  - the hardened-chassis battery: sealed exit, A-carve regression, jump
    audit, stateless undo re-barring.
"""
from collections import deque

from blessed.keyboard import Keystroke
from blessed import Terminal

import vimny.game as main
from vimny.engine.motion import apply_motion
from vimny.engine.operator import law_column, INDENT_WIDTH
from vimny.engine.player import Player
from vimny.engine.world import CellType
from vimny.content.levels import known_commands
from vimny.generation.dungeon_gen import (
    build_dungeon_indentation_sanctum,
    _IS_ROWS, _IS_COLS, _IS_PAR, _IS_BUDGET, _IS_ANSWER, _IS_RITE,
    _IS_COL_S, _IS_PLQ_COL, _IS_REGISTER, _IS_G1_ROWS, _IS_G2_ROWS,
    _IS_RITE_ROWS, _IS_BLANK_ROWS, _IS_GATE_ROW, _IS_GATE_COL0,
    _IS_EXIT, _IS_TRIGGERS,
)

import math
import pytest

from tests import SEEDS, cached_room

ESC = Keystroke('\x1b', name='KEY_ESCAPE')


def _room(seed):
    return cached_room('build_dungeon_indentation_sanctum', seed)


def _K(s):
    return [Keystroke(ch) for ch in s]


def _bolt(i):
    return (_IS_GATE_ROW, _IS_GATE_COL0 + i)


# The canonical route: each bay is one paragraph stroke (the blank courses
# bound them); the open floor lets 4j hop bay to bay; M takes the second hop. 11 keys.
def _canon_keys():
    return _K('>}4j<}M=}') + _K('G$')


# The manual-mason rival: no `=` anywhere — count-linewise banks, then the
# rite row by row (>>/<</dot). Wins at 1 star under the hand-set budget.
def _manual_keys():
    return _K('3>>4j3<<4j') + _K('<<j>>j<<jj>>j<<.j.') + _K('G$')


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
    return main.run_dungeon(term, 'indentation_sanctum', {}, player_name=name,
                            _dungeon=dungeon)


def _spend_uncapped(dungeon, keys, monkeypatch, _drive_fn):
    """Drive a route with the budget UNCAPPED and return (won, spent).

    PAR-IS-THE-OPTIMUM (docs/ARCHITECTURE.md): the budget follows par at 1.4x and
    is never widened to keep a sub-optimal route alive, so a rival's claim to
    test is that it costs MORE THAN PAR — not that it squeaks inside a hand-set
    budget. Whether it also falls outside the standard budget is a consequence of
    how much worse it is, not a design knob."""
    box = {}
    orig = main._calc_stars
    monkeypatch.setattr(main, '_calc_stars',
                        lambda won, budget, room, player, level='':
                            (box.__setitem__('spent', budget.spent),
                             orig(won, budget, room, player, level))[1])
    for r in dungeon.rooms:
        r.budget = 99999
    result = _drive_fn(dungeon, keys, monkeypatch)
    return result['won'], box.get('spent')



def _drive_spent(keys, monkeypatch):
    box = {}
    orig = main._calc_stars
    monkeypatch.setattr(main, '_calc_stars',
                        lambda won, budget, room, player, level='':
                            (box.__setitem__('spent', budget.spent), orig(won, budget, room, player, level))[1])
    dungeon = build_dungeon_indentation_sanctum(SEEDS[0])
    dungeon.rooms[0].budget = 999
    result = _drive(dungeon, keys, monkeypatch)
    return result['won'], box.get('spent')


def _start_col(room, r):
    line = main._wla_floor_text(room, r)
    return len(line) - len(line.lstrip()) if line.strip() else None


# ── structure + the law ───────────────────────────────────────────────────────

@pytest.mark.parametrize("seed", SEEDS)
def test_dimensions_anchors_par_budget(seed):
    room = _room(seed)
    assert (room.rows, room.cols) == (_IS_ROWS, _IS_COLS)
    assert room.spawn_pos == (_IS_G1_ROWS[0], _IS_COL_S)
    assert room.exit_pos == _IS_EXIT
    assert room.par == _IS_PAR
    assert room.budget == math.ceil(_IS_PAR * 1.4)   # STANDARD


def test_rite_shape_parity_and_scatter():
    """Rite offsets are EVEN (parity law), HETEROGENEOUS (no uniform shift can
    satisfy them — the =-forcing), and include one already-true row (=
    idempotence). The skeleton carries the ':'/'end' structure the law reads."""
    true_cols, depth = [], 0
    base = _IS_COL_S
    for template, corrupt in _IS_RITE:
        if template.split()[0] == 'end':
            depth = max(depth - 1, 0)
        true_cols.append(base + INDENT_WIDTH * depth)
        if template.endswith(':'):
            depth += 1
    offsets = [c - t for (_, c), t in zip(_IS_RITE, true_cols)]
    assert all(o % INDENT_WIDTH == 0 for o in offsets), "PARITY"
    assert len(set(offsets)) >= 3, "heterogeneous — no uniform stroke fixes it"
    assert 0 in offsets, "one row already true: = is idempotent there"
    assert any(o > 0 for o in offsets) and any(o < 0 for o in offsets)
    assert depth == 0, "the rite closes every block it opens"


@pytest.mark.parametrize("seed", SEEDS)
def test_law_column_is_the_door_judge(seed):
    """The SAME law_column the = operator applies is what the rite bolt
    demands: as built, at least one rite row disagrees with the law; after
    =, every row agrees."""
    room = build_dungeon_indentation_sanctum(seed).rooms[0]
    disagree = [r for r in _IS_RITE_ROWS if _start_col(room, r) != law_column(room, r)]
    assert disagree, "the rite is mis-set as built"
    # gallery rows are UNGOVERNED: the law says the wall (the segment start)
    for r in _IS_G1_ROWS + _IS_G2_ROWS:
        assert law_column(room, r) == _IS_COL_S, "ungoverned verse → the wall"


@pytest.mark.parametrize("seed", SEEDS)
def test_words_distinct_and_plaques_in_the_wall(seed):
    room = _room(seed)
    words = list(room._is_g1_words) + list(room._is_g2_words)
    rite_words = [w for t in room._is_rite_texts for w in t.rstrip(':').split()
                  if w not in ('rite', 'when', 'end')]
    all_words = words + rite_words
    assert len(set(all_words)) == len(all_words), "seeded words never collide"
    for rows, off, ws in ((_IS_G1_ROWS, -2, room._is_g1_words),
                          (_IS_G2_ROWS, +2, room._is_g2_words)):
        for r, w in zip(rows, ws):
            floor = main._wla_floor_text(room, r)
            c = _IS_REGISTER + off
            assert floor[c:c + len(w)] == w
            plq = room.char_run_at(r, _IS_PLQ_COL)
            assert plq is not None and not room.is_passable(r, _IS_PLQ_COL)
    mark = room.char_run_at(1, _IS_REGISTER)
    assert mark is not None and ''.join(mark.symbols) == '│'


@pytest.mark.parametrize("seed", SEEDS)
def test_blank_courses_bound_the_bays(seed):
    """The bays are separated by bare FLOOR rows — paragraph boundaries, so
    `>}`/`<}`/`=}` each take exactly one bay."""
    room = _room(seed)
    for r in _IS_BLANK_ROWS:
        assert main._wla_floor_text(room, r).strip() == ''
        assert room.is_passable(r, _IS_COL_S)


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
    room = build_dungeon_indentation_sanctum(seed).rooms[0]
    assert _IS_EXIT not in _reachable(room)


@pytest.mark.parametrize("seed", SEEDS)
def test_no_jump_lands_on_the_shut_exit(seed):
    room = build_dungeon_indentation_sanctum(seed).rooms[0]
    jumps = ([('G', 1, False), ('gg', 1, False), ('H', 1, False),
              ('M', 1, False), ('L', 1, False)]
             + [('G', n, True) for n in range(1, _IS_ROWS)])
    for motion, count, given in jumps:
        p = Player(row=room.spawn_pos[0], col=room.spawn_pos[1])
        apply_motion(p, motion, count, room, count_given=given)
        assert (p.row, p.col) != _IS_EXIT, f"{motion} dropped onto the exit"
        assert room.is_passable(p.row, p.col), f"{motion} landed in a wall"


# ── the trap and the forcing, driven ──────────────────────────────────────────

def test_equals_razes_the_ungoverned_gallery(monkeypatch):
    """The markdown trap, playable: `=}` on the plain-verse gallery applies
    the law to text the law does not govern — every noun razed to the wall,
    the bolt shut; `u` recovers."""
    dungeon = build_dungeon_indentation_sanctum(SEEDS[0])
    room = dungeon.rooms[0]
    _drive(dungeon, _K('=}l'), monkeypatch, finish=':q!\r')
    for r in _IS_G1_ROWS:
        assert _start_col(room, r) == _IS_COL_S, "razed to the wall"
    assert room.cells[_bolt(0)[0]][_bolt(0)[1]] == CellType.WALL, "bolt shut"

    dungeon = build_dungeon_indentation_sanctum(SEEDS[0])
    room = dungeon.rooms[0]
    # uu: the walk pushes its own snapshot, the second u reaches the =
    _drive(dungeon, _K('=}luu'), monkeypatch, finish=':q!\r')
    for r, w in zip(_IS_G1_ROWS, room._is_g1_words):
        assert _start_col(room, r) == _IS_REGISTER - 2, "u restores the bank"


def test_uniform_strokes_cannot_satisfy_the_rite(monkeypatch):
    """>{m}/<{m} shift every row the SAME way; the rite's offsets are mixed,
    so any single uniform stroke leaves the bolt shut."""
    for stroke in ('>}', '<}'):
        dungeon = build_dungeon_indentation_sanctum(SEEDS[0])
        room = dungeon.rooms[0]
        _drive(dungeon, _K('>}4j<}M') + _K(stroke) + _K('l'),
               monkeypatch, finish=':q!\r')
        assert room.cells[_bolt(2)[0]][_bolt(2)[1]] == CellType.WALL, stroke


@pytest.mark.parametrize("seed", SEEDS)
def test_full_law_route_wins_par_perfect(seed, monkeypatch):
    dungeon = build_dungeon_indentation_sanctum(seed)
    room = dungeon.rooms[0]
    result = _drive(dungeon, _canon_keys(), monkeypatch)
    assert result['won'] and result['stars'] == 2, result
    for i in range(_IS_TRIGGERS):
        assert room.cells[_bolt(i)[0]][_bolt(i)[1]] == CellType.FLOOR
    # the rite stands as the law reads — judged by the operator's own function
    for r in _IS_RITE_ROWS:
        assert _start_col(room, r) == law_column(room, r)


def test_no_cheaper_nav_beats_par(monkeypatch):
    won, spent = _drive_spent(_canon_keys(), monkeypatch)
    assert won and spent == _IS_PAR, (won, spent)
    won_m, spent_m = _drive_spent(_manual_keys(), monkeypatch)
    assert won_m and spent_m > _IS_PAR, "the manual route must cost more than par"


@pytest.mark.parametrize("seed", SEEDS)
def test_manual_mason_route_wins_at_one_star(seed, monkeypatch):
    """THE LAW, driven: the no-= route (count-linewise banks + per-row
    >>/<</dot through the rite) WINS under the hand-set budget, at 1 star —
    forcing by PAR, not an unwinnable wall."""
    dungeon = build_dungeon_indentation_sanctum(seed)
    won, spent = _spend_uncapped(dungeon, _manual_keys(), monkeypatch, _drive)
    assert won and spent > dungeon.rooms[0].par, (won, spent)


def test_undo_rebars_bolt_and_seal(monkeypatch):
    dungeon = build_dungeon_indentation_sanctum(SEEDS[0])
    room = dungeon.rooms[0]
    _drive(dungeon, _K('>}4j<}M=}') + _K('l'), monkeypatch, finish=':q!\r')
    assert room.cells[_bolt(2)[0]][_bolt(2)[1]] == CellType.FLOOR
    assert room.cells[_IS_EXIT[0]][_IS_EXIT[1]] == CellType.FLOOR, "the seal parted"

    dungeon = build_dungeon_indentation_sanctum(SEEDS[0])
    room = dungeon.rooms[0]
    _drive(dungeon, _K('>}4j<}M=}') + _K('luu'), monkeypatch, finish=':q!\r')
    assert room.cells[_bolt(2)[0]][_bolt(2)[1]] == CellType.WALL, "re-bars"
    assert room.cells[_IS_EXIT[0]][_IS_EXIT[1]] == CellType.WALL, "the seal returns"


@pytest.mark.parametrize("seed", SEEDS)
def test_A_carve_cannot_bypass_the_seal(seed, monkeypatch):
    dungeon = build_dungeon_indentation_sanctum(seed)
    dungeon.rooms[0].budget = 999
    keys = (_K('16j') + _K('A') + _K('xxxx') + [ESC] + _K('j'))
    result = _drive(dungeon, keys, monkeypatch)
    assert not result['won'], "the throat-carve must not reach the sealed exit"


# ── curriculum + karaoke ──────────────────────────────────────────────────────

def test_curriculum_teaches_equals_keeps_indent_and_paragraphs():
    known = set(known_commands('indentation_sanctum'))
    assert '=' in known
    assert {'>', '<', '}'} <= known, "the operators and the paragraph motion"
    prior = set(known_commands('alignment_halls'))     # the level before
    assert '=' not in prior, "= is new here"


def test_equals_is_gated_before_this_level(monkeypatch):
    """A player without the '=' token cannot equalize (the ungated-= trap the
    curriculum audit caught: teaches was [] and would have shipped it free)."""
    from vimny.engine.command_guard import action_allowed
    action = {'type': 'operator', 'op': '=', 'motion': 'line', 'count': 1}
    assert not action_allowed(action, known_commands('alignment_halls'))
    assert action_allowed(action, known_commands('indentation_sanctum'))


@pytest.mark.parametrize("seed", SEEDS)
def test_answer_is_the_real_keystroke_tape(seed, monkeypatch):
    room = _room(seed)
    assert room.answer == _IS_ANSWER
    dungeon = build_dungeon_indentation_sanctum(seed)
    troom = dungeon.rooms[0]
    _drive(dungeon, _canon_keys(), monkeypatch, finish=':q!\r', name='admin')
    assert not troom.answer_diverged
    assert troom.answer_pos == len(troom.answer.replace(' ', ''))


def test_the_rite_wears_a_heading_that_says_it_is_code(monkeypatch):
    """Playtest (user, 2026-07-25): the galleries wear their true word on the
    west wall, but the rite block wore nothing — nothing on screen said the
    block below was CODE, which is what `=` seats. The heading is carved in the
    WALL band that divides the last gallery from the rite: uncuttable, off the
    floor scans, and it names no key.

    It is a TAG, not prose. Every other plaque in this level is a literal word
    the floor must be made to match, so a heading reading "the code" would read
    as one more of those — go and write those words. `<code>` reads as a label
    ABOUT the block below it."""
    room = build_dungeon_indentation_sanctum(0).rooms[0]
    heading = [ru for ru in room.char_runs
               if ru.row == _IS_BLANK_ROWS[1] and ru.col < _IS_COL_S]
    assert heading, "the rite needs a heading"
    text = ' '.join(''.join(ru.symbols) for ru in sorted(heading, key=lambda u: u.col))
    assert text == '<code>', text
    assert text.startswith('<') and text.endswith('>'), \
        "a TAG, so it never reads as a word the floor must be made to match"
    for ru in heading:                       # in the WALL: uncuttable, unscanned
        for k in range(len(ru.symbols)):
            assert room.cells[ru.row][ru.col + k] == CellType.WALL
    # and it must not disturb the rite check — that reads FLOOR text only
    assert 'code' not in main._wla_floor_text(room, _IS_BLANK_ROWS[1])
