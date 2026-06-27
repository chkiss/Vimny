"""The Change Annex (display 23, slug `whole_line_annex`): c{m}, cc, s.

Change is delete + insert in one breath. A hall of mislabelled doors: every
door's plaque (set in the WEST wall) shows the word it wants; the label on the
floor to the east shows the wrong one (the plaque rule, fifth member — Cipher
mended, Beacon copied, Echo repeated, the Halls authored, the Annex RELABELS).
Three door kinds, three verbs:

  word doors — the label is ONE word off inside a kept phrase; `ce` changes
               just that word (cc would force retyping the whole phrase).
  line doors — the WHOLE line is one wrong word; `cc` rewrites it. The cursor
               lands MID-row here (off the previous east-ending edit), so cc
               (column-agnostic) honestly saves the `0`/`^` the old `D`/`d$`
               rival must spend to clear from the line start.
  rune doors — one fused rune (◆) stands for two letters; `s` cuts it and
               spells them out (cw/r overpay — r is one-for-one).

Forcing is by VOLUME (c is delete-then-insert with reflow, identical to
d-then-i, so terrain forcing is dead — every change saves exactly ONE key over
its d/x + i rival). The eight bolts gate an exit-stack; the budget margin
(TRIGGERS − 1) sits below the door count, so the all-old route overshoots and
is barred.

Two layout laws (from the first playtest, asserted below):
  - PLAQUE IN THE WEST WALL: in WALL cells it is uncuttable and out of the floor
    scans. (Reflow is now segment-bounded both ways — 2026-06-26 — so an east
    plaque behind a wall would be safe too; west is just the simplest home.)
  - the canonical answer is the REAL keystroke tape (karaoke); nothing typed
    contains a space (line doors are a single word), so it is unambiguous.
  - TELEPORT AUDIT: the exit stays WALL until every label reads true, so no
    jump (G / L / {n}G lands on the first STANDABLE cell, reachable or not)
    can drop onto the isolated exit.
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
    build_dungeon_whole_line_annex, _wla_pick, _wla_route, _wla_answer,
    _WLA_ROWS, _WLA_COLS, _WLA_COL_S, _WLA_LBL_COL, _WLA_LBL_END, _WLA_PLQ_COL,
    _WLA_LESSON_ROWS, _WLA_GATE_ROW, _WLA_GATE_COL0, _WLA_EXIT, _WLA_PAR,
    _WLA_TRIGGERS, _WLA_N_WORD, _WLA_N_LINE, _WLA_N_SENT, _WLA_PLACEHOLDER,
)


def _bolt(i):
    """The (row, col) of lesson i's gate bolt."""
    return (_WLA_GATE_ROW, _WLA_GATE_COL0 + i)
import pytest
import random

from tests import SEEDS, cached_room

_FLOORS = (CellType.FLOOR, CellType.CORRIDOR)
ESC = Keystroke('\x1b', name='KEY_ESCAPE')


def _room(seed):
    """Shared READ-ONLY build; mutating tests call the builder directly."""
    return cached_room('build_dungeon_whole_line_annex', seed)


def _K(s):
    return [Keystroke(ch) for ch in s]


def _change_keys(lessons):
    """The canonical change route (shared _wla_route): the verb keys, then the
    typed fix sealed with Esc (free)."""
    out = []
    for keys, typed in _wla_route(lessons):
        out += _K(keys)
        if typed:
            out += _K(typed) + [ESC]
    return out


def _old_keys(lessons):
    """The same route with every change swapped for its old d/x + i rival
    (+1 key each): ce→de i, cc→0 D i (clear from the line start), s→x i."""
    out = []
    for i, L in enumerate(lessons):
        out += _K('' if i == 0 else ('j' if L['kind'] == 'line' else 'j^'))
        if L['kind'] == 'word':
            out += _K('de') + _K('i') + _K(L['typed']) + [ESC]
        elif L['kind'] == 'line':
            out += _K('0') + _K('D') + _K('i') + _K(L['typed']) + [ESC]
        else:
            out += _K('x') + _K('i') + _K(L['typed']) + [ESC]
    return out + _K('G$')


def _drive(dungeon, keys, monkeypatch, finish=':wq\r', name='Scribe'):
    keys = list(keys) + _K(finish)
    monkeypatch.setattr(main, 'render_all', lambda *a, **k: None)
    monkeypatch.setattr(main.time, 'sleep', lambda *a, **k: None)
    for anim in ('_fireworks_animation', '_win_animation', '_starfield_victory',
                 '_heart_container_animation', '_unlock_animation',
                 '_void_fall_animation', '_drown_animation'):
        monkeypatch.setattr(main, anim, lambda *a, **k: None)
    term = Terminal()
    it = iter(keys)
    monkeypatch.setattr(term, 'inkey', lambda *a, **k: next(it, Keystroke('')))
    return main.run_dungeon(term, 'whole_line_annex', {}, player_name=name,
                            _dungeon=dungeon)


# ── structure ─────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("seed", SEEDS)
def test_dimensions_anchors_par_budget(seed):
    room = _room(seed)
    assert (room.rows, room.cols) == (_WLA_ROWS, _WLA_COLS)
    assert room.spawn_pos == (_WLA_LESSON_ROWS[0], _WLA_LBL_COL)
    assert room.exit_pos == _WLA_EXIT
    assert room.par == _WLA_PAR
    # tight margin (S2 by volume): below the door count, so all-old overshoots
    assert room.budget == _WLA_PAR + _WLA_TRIGGERS - 1
    assert room.budget - room.par < _WLA_TRIGGERS


@pytest.mark.parametrize("seed", SEEDS)
def test_lesson_block_is_open_floor(seed):
    room = _room(seed)
    for r in _WLA_LESSON_ROWS:
        for c in range(_WLA_COL_S, _WLA_LBL_END + 1):
            assert room.cells[r][c] == CellType.FLOOR, (r, c)


@pytest.mark.parametrize("seed", SEEDS)
def test_plaque_is_in_the_west_wall(seed):
    """The plaque sits WEST of the spine, in WALL cells (uncuttable, reflow-
    immune, and excluded from the floor scans)."""
    room = _room(seed)
    for r in _WLA_LESSON_ROWS:
        plq = room.char_run_at(r, _WLA_PLQ_COL)
        assert plq is not None and plq.kind == 'verdant'
        assert _WLA_PLQ_COL < _WLA_COL_S, "plaque is west of the spine"
        for k in range(len(plq.symbols)):
            assert room.cells[r][_WLA_PLQ_COL + k] == CellType.WALL


@pytest.mark.parametrize("seed", SEEDS)
def test_bolts_start_walled_exit_is_plain_floor(seed):
    """Every gate bolt is WALL at build (the tick opens them per label). The
    exit is PLAIN FLOOR — never a gated wall — and stays floor through a tick."""
    dungeon = build_dungeon_whole_line_annex(seed)
    room = dungeon.rooms[0]
    p = Player(row=room.spawn_pos[0], col=room.spawn_pos[1])
    main._whole_line_annex_tick(room, p)
    for i in range(_WLA_TRIGGERS):
        assert room.cells[_bolt(i)[0]][_bolt(i)[1]] == CellType.WALL
    assert room.cells[_WLA_EXIT[0]][_WLA_EXIT[1]] == CellType.FLOOR


@pytest.mark.parametrize("seed", SEEDS)
def test_lesson_mix(seed):
    """Four word, two line, two rune doors, word doors first (so the line-door
    cursor lands mid-row off the previous east-ending edit)."""
    room = _room(seed)
    kinds = [L['kind'] for L in room._wla_lessons]
    assert kinds == (['word'] * _WLA_N_WORD + ['line'] * _WLA_N_LINE
                     + ['sent'] * _WLA_N_SENT)


@pytest.mark.parametrize("seed", SEEDS)
def test_label_target_shapes(seed):
    """word: one word off (context kept). line: a single wrong word (no space —
    the karaoke answer can't type one). sent: a fused ◆ → two letters."""
    for L in _wla_pick(random.Random(seed)):
        assert ' ' not in L['typed'], "no typed value may contain a space"
        if L['kind'] == 'word':
            lw, tw = L['label'].split(), L['target'].split()
            assert lw[1] == tw[1] and lw[0] != tw[0]           # context kept
            assert L['typed'] == tw[0] and len(L['typed']) == 4
        elif L['kind'] == 'line':
            assert ' ' not in L['label'] and ' ' not in L['target']
            assert L['typed'] == L['target'] and L['label'] != L['target']
            assert len(L['typed']) == 6
        else:
            assert L['label'].startswith(_WLA_PLACEHOLDER)
            tw = L['target'].split()
            assert L['typed'] == tw[0][:2] and len(L['typed']) == 2
            assert L['label'].split()[1] == tw[1]              # context kept


@pytest.mark.parametrize("seed", SEEDS)
def test_doors_independent(seed):
    """Distinct words guarantee it: no target is a substring of another target
    or of any label, so each change opens exactly its own bolt."""
    lessons = _wla_pick(random.Random(seed))
    targets = [L['target'] for L in lessons]
    labels = [L['label'] for L in lessons]
    for i, t in enumerate(targets):
        for j, u in enumerate(targets):
            if i != j:
                assert t not in u, (t, u)
        for lb in labels:
            assert t not in lb, (t, lb)


# ── access: the exit is eight changes deep, and no jump cheats it ─────────────

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
    room = build_dungeon_whole_line_annex(seed).rooms[0]
    assert _WLA_EXIT not in _reachable(room), "the stack and the seal hold"


@pytest.mark.parametrize("seed", SEEDS)
def test_no_jump_lands_on_the_shut_exit(seed):
    """The teleport audit: with the doors shut, NO line jump may land on the
    isolated exit (it is WALL until every label reads true)."""
    room = build_dungeon_whole_line_annex(seed).rooms[0]
    jumps = ([('G', 1, False), ('gg', 1, False), ('H', 1, False),
              ('M', 1, False), ('L', 1, False)]
             + [('G', n, True) for n in range(1, _WLA_ROWS)])
    for motion, count, given in jumps:
        p = Player(row=room.spawn_pos[0], col=room.spawn_pos[1])
        apply_motion(p, motion, count, room, count_given=given)
        assert (p.row, p.col) != _WLA_EXIT, f"{motion} dropped onto the shut exit"
        assert room.is_passable(p.row, p.col), f"{motion} landed in a wall"


# ── the doors, driven for real ────────────────────────────────────────────────

@pytest.mark.parametrize("seed", SEEDS)
def test_full_change_route_wins_par_perfect(seed, monkeypatch):
    dungeon = build_dungeon_whole_line_annex(seed)
    room = dungeon.rooms[0]
    result = _drive(dungeon, _change_keys(room._wla_lessons), monkeypatch)
    assert result['won'] and result['stars'] == 2, result
    for i in range(_WLA_TRIGGERS):
        assert room.cells[_bolt(i)[0]][_bolt(i)[1]] == CellType.FLOOR, "every bolt open"


@pytest.mark.parametrize("seed", SEEDS)
def test_plaques_survive_every_change(seed, monkeypatch):
    """The west-wall plaque is reflow-immune: after the whole route (every kind
    of edit) each plaque still reads its original target."""
    dungeon = build_dungeon_whole_line_annex(seed)
    room = dungeon.rooms[0]
    want = {r: room.char_run_at(r, _WLA_PLQ_COL).symbols for r in _WLA_LESSON_ROWS}
    _drive(dungeon, _change_keys(room._wla_lessons), monkeypatch)
    for r in _WLA_LESSON_ROWS:
        plq = room.char_run_at(r, _WLA_PLQ_COL)
        assert plq is not None and plq.symbols == want[r], \
            f"plaque on row {r} was disturbed by an edit"


@pytest.mark.parametrize("seed", SEEDS)
def test_all_old_route_is_barred(seed, monkeypatch):
    """Necessity, by volume: the route that spends d/x + i on EVERY change
    (never c, never s) costs par + TRIGGERS — one past the budget — so the
    path runs out and the exit is never reached."""
    dungeon = build_dungeon_whole_line_annex(seed)
    result = _drive(dungeon, _old_keys(dungeon.rooms[0]._wla_lessons), monkeypatch)
    assert not result['won'], "the all-old route must run out of budget"


@pytest.mark.parametrize("seed", SEEDS)
def test_garbage_never_opens_a_bolt(seed, monkeypatch):
    """Typing the wrong letters over a label changes the floor but matches no
    plaque — the bolt answers only to its target."""
    dungeon = build_dungeon_whole_line_annex(seed)
    room = dungeon.rooms[0]
    keys = _K('ce') + _K('zzzz') + [ESC]              # mangle lesson 1's first word
    _drive(dungeon, keys, monkeypatch, finish=':q!\r')
    assert room.cells[_bolt(0)[0]][_bolt(0)[1]] == CellType.WALL


@pytest.mark.parametrize("seed", SEEDS)
def test_undo_rebars_the_bolt(seed, monkeypatch):
    """One change is one snapshot: making it opens the bolt; u unwrites the
    word and the tick re-bars it (stateless, undo-safe)."""
    dungeon = build_dungeon_whole_line_annex(seed)
    room = dungeon.rooms[0]
    L0 = room._wla_lessons[0]
    _drive(dungeon, _K('ce') + _K(L0['typed']) + [ESC] + _K('l'),
           monkeypatch, finish=':q!\r')
    assert room.cells[_bolt(0)[0]][_bolt(0)[1]] == CellType.FLOOR, "opened"

    dungeon = build_dungeon_whole_line_annex(seed)
    room = dungeon.rooms[0]
    # l (a move), then u u: first u pops the move, the second the whole change.
    _drive(dungeon, _K('ce') + _K(L0['typed']) + [ESC] + _K('luul'),
           monkeypatch, finish=':q!\r')
    assert room.cells[_bolt(0)[0]][_bolt(0)[1]] == CellType.WALL, "re-barred"


@pytest.mark.parametrize("seed", SEEDS)
def test_one_shut_bolt_bars_the_exit(seed, monkeypatch):
    """Seven labels true leaves the eighth bolt shut, so the exit (plain floor,
    east of the bolts) stays UNREACHABLE — the row of bolts is a series gate."""
    dungeon = build_dungeon_whole_line_annex(seed)
    room = dungeon.rooms[0]
    lessons = room._wla_lessons
    keys = []
    for i, L in enumerate(lessons[:-1]):             # drive only the first seven
        keys += _K('' if i == 0 else ('j' if L['kind'] == 'line' else 'j^'))
        keys += _K({'word': 'ce', 'line': 'cc', 'sent': 's'}[L['kind']])
        keys += _K(L['typed']) + [ESC]
    keys += _K('j')                                  # onto the gate row, no change
    _drive(dungeon, keys, monkeypatch, finish=':q!\r')
    assert room.cells[_bolt(7)[0]][_bolt(7)[1]] == CellType.WALL, "8th bolt shut"
    assert _WLA_EXIT not in _reachable(room), "one shut bolt still bars the exit"


# ── the admin karaoke answer ──────────────────────────────────────────────────

@pytest.mark.parametrize("seed", SEEDS)
def test_answer_is_the_real_keystroke_tape(seed):
    """room.answer is the printable keystrokes of the canonical route (Esc
    omitted, spaces only as separators), so the admin answer-sheet tracks it
    keystroke for keystroke. No typed value contains a space."""
    room = _room(seed)
    expected = ''.join(keys + typed for keys, typed in _wla_route(room._wla_lessons))
    assert room.answer.replace(' ', '') == expected
    assert room.answer == _wla_answer(room._wla_lessons)


def test_admin_answer_tracking_follows_the_route(monkeypatch):
    """Driven as `admin`, the canonical keystrokes advance answer_pos without
    diverging (every non-space answer char is matched in order)."""
    dungeon = build_dungeon_whole_line_annex(SEEDS[0])
    room = dungeon.rooms[0]
    _drive(dungeon, _change_keys(room._wla_lessons), monkeypatch,
           finish=':q!\r', name='admin')
    assert not room.answer_diverged, "the canonical route must not diverge"
    assert room.answer_pos == len(room.answer.replace(' ', ''))


# ── curriculum ────────────────────────────────────────────────────────────────

def test_curriculum_guard():
    known = set(known_commands('whole_line_annex'))
    assert {'c', 's'} <= known                      # the verbs this level grants
    for needed in ('d', 'D', 'x', 'insert', 'G', '^', 'count'):
        assert needed in known, needed             # the route's prior tools
