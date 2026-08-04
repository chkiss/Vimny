"""The Sculpting Chambers (slug `sculpting_chambers`): I A o O.

The topology lesson, on the FULL poem (playtest 2026-07-20: the one-word
skeleton votive made no sense). The tablet is the whole of ROW YOUR BOAT;
the west-wall plaques give each line's FIRST WORD only, and the stone shows
what remains of each line — the verb is implied by the wound:

  O  — line 1 is MISSING, above the topmost given line: only O opens upward.
  I  — line 2 survives as its TAIL (`the stream`); I prepends `gently down `
       and the tail is PUSHED east (the line's floor runs wide for the push).
  A  — line 3 survives as its HEAD (`merrily merrily`); A appends the rest,
       carving EAST through solid stone PAST the room's own width (the buffer
       doubles under the longest line — A makes its own space).
  o  — line 4 is MISSING, below the lowest given line: only o opens downward.

The vault door (one gated cell south of the last line) unseals while the poem
reads true line for line; the tick is text- and exit_pos-relative (rides the
o/O row shifts), stateless, undo-safe. Typed spaces are lawful on the tape,
marked <Space>.
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
    build_dungeon_sculpting_chambers,
    _SC_ROWS, _SC_COLS, _SC_PAR, _SC_TARGET, _SC_BAND, _SC_LINES, _SC_COMPLETIONS,
    _SC_I_ROW, _SC_A_ROW, _SC_WCOL, _SC_PLQ, _SC_EXIT_COL, _SC_EXIT_ROW0,
    _SC_I_GIVEN, _SC_A_GIVEN, _SC_I_TYPED, _SC_A_TYPED, _SC_ANSWER, _SC_A_END,
)

import math
import pytest

from tests import SEEDS, cached_room

ESC = Keystroke('\x1b', name='KEY_ESCAPE')
_FLOORS = (CellType.FLOOR, CellType.CORRIDOR)


def _room(seed):
    return cached_room('build_dungeon_sculpting_chambers', seed)


def _K(s):
    return [Keystroke(ch) for ch in s]


# The canonical route runs TOP-TO-BOTTOM, one insert-entry per line, each
# COMPLETING the line (the plaque already holds the first word):
# O comp0 · j · I 'down ' · j · A comp2's rest · o comp3 · j onto the door.
def _canon_keys():
    return (_K('O') + _K(_SC_COMPLETIONS[0]) + [ESC] + _K('j')
            + _K('I') + _K(_SC_I_TYPED) + [ESC] + _K('j')
            + _K('A') + _K(_SC_A_TYPED) + [ESC]
            + _K('o') + _K(_SC_COMPLETIONS[3]) + [ESC]
            + _K('j'))


def _drive(dungeon, keys, monkeypatch, finish=':wq\r', name='Scribe'):
    keys = list(keys) + _K(finish)
    monkeypatch.setattr(main, 'render_all', lambda *a, **k: None)
    monkeypatch.setattr(main.time, 'sleep', lambda *a, **k: None)
    for anim in ('_fireworks_animation', '_win_animation', '_starfield_victory',
                 '_heart_container_animation', '_unlock_animation',
                 '_void_fall_animation', '_drown_animation', '_sc_twinkle_animation'):
        monkeypatch.setattr(main, anim, lambda *a, **k: None)
    monkeypatch.setattr(Terminal, 'height', property(lambda self: 41))
    term = Terminal()
    it = iter(keys)
    monkeypatch.setattr(term, 'inkey', lambda *a, **k: next(it, Keystroke('')))
    return main.run_dungeon(term, 'sculpting_chambers', {}, player_name=name,
                            _dungeon=dungeon)


def _poem_rows(room):
    """The nonempty floor-band texts (the COMPLETIONS), top to bottom,
    space-normalised."""
    c0, c1 = _SC_BAND
    seq = [' '.join(main._wla_floor_text(room, r)[c0:c1 + 1].split())
           for r in range(room.rows)]
    return [t for t in seq if t]


# ── structure ─────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("seed", SEEDS)
def test_dimensions_anchors_par_budget(seed):
    room = _room(seed)
    assert (room.rows, room.cols) == (_SC_ROWS, _SC_COLS)
    assert room.spawn_pos == (_SC_I_ROW, _SC_WCOL)
    assert room.exit_pos == (_SC_EXIT_ROW0, _SC_EXIT_COL)
    assert room.par == _SC_PAR
    assert room.budget == math.ceil(_SC_PAR * 1.4)


@pytest.mark.parametrize("seed", SEEDS)
def test_only_the_tail_and_the_head_are_given(seed):
    """The tablet starts with just two wounded lines: line 2's tail and line
    3's head. Lines 1 and 4 have no row yet — the player must OPEN them."""
    room = _room(seed)
    assert _poem_rows(room) == [_SC_I_GIVEN, _SC_A_GIVEN]


@pytest.mark.parametrize("seed", SEEDS)
def test_plaques_give_only_the_first_words(seed):
    """Each west-wall plaque is exactly its line's first word, carved in WALL
    cells (uncuttable, off the floor scans)."""
    room = _room(seed)
    plaques = sorted((ru.row, ''.join(ru.symbols)) for ru in room.char_runs
                     if ru.kind == 'verdant')
    assert [w for _r, w in plaques] == list(_SC_TARGET)
    assert _SC_TARGET == tuple(ln.split()[0] for ln in _SC_LINES)
    for r, w in plaques:
        for k in range(len(w)):
            assert room.cells[r][_SC_PLQ + k] == CellType.WALL


@pytest.mark.parametrize("seed", SEEDS)
def test_door_sealed_and_east_of_the_A_line_is_stone(seed):
    """The exit cell is WALL at build, and east of the A line's launch cell is
    solid stone — the second half of the longest line must be CARVED."""
    room = build_dungeon_sculpting_chambers(seed).rooms[0]
    er, ec = room.exit_pos
    assert room.cells[er][ec] == CellType.WALL
    a_end = _SC_WCOL + len(_SC_A_GIVEN)
    for c in range(a_end + 1, _SC_COLS - 1):
        assert room.cells[_SC_A_ROW][c] == CellType.WALL, c


# ── the door is unreachable until the poem reads true (teleport audit) ─────────

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
    room = build_dungeon_sculpting_chambers(seed).rooms[0]
    assert room.exit_pos not in _reachable(room)


@pytest.mark.parametrize("seed", SEEDS)
def test_no_jump_lands_on_the_sealed_door(seed):
    room = build_dungeon_sculpting_chambers(seed).rooms[0]
    jumps = ([('G', 1, False), ('gg', 1, False), ('H', 1, False),
              ('M', 1, False), ('L', 1, False)]
             + [('G', n, True) for n in range(1, _SC_ROWS)])
    for motion, count, given in jumps:
        p = Player(row=room.spawn_pos[0], col=room.spawn_pos[1])
        apply_motion(p, motion, count, room, count_given=given)
        assert (p.row, p.col) != room.exit_pos, f"{motion} dropped onto the door"
        assert room.is_passable(p.row, p.col), f"{motion} landed in a wall"


# ── the poem, driven for real ─────────────────────────────────────────────────

@pytest.mark.parametrize("seed", SEEDS)
def test_full_poem_route_wins_par_perfect(seed, monkeypatch):
    dungeon = build_dungeon_sculpting_chambers(seed)
    result = _drive(dungeon, _canon_keys(), monkeypatch)
    assert result['won'] and result['stars'] == 2, result


def _drive_spent(keys, monkeypatch):
    box = {}
    orig = main._calc_stars
    monkeypatch.setattr(main, '_calc_stars',
                        lambda won, budget, room, player, level='':
                            (box.__setitem__('spent', budget.spent),
                             orig(won, budget, room, player, level))[1])
    dungeon = build_dungeon_sculpting_chambers(SEEDS[0])
    dungeon.rooms[0].budget = 999          # uncap: measure the true keystroke cost
    result = _drive(dungeon, keys, monkeypatch)
    return result['won'], box.get('spent')


def test_par_is_the_measured_route_cost(monkeypatch):
    """Hand-par level: the canonical route spends EXACTLY par (engine-measured,
    so par can never drift above the driven route)."""
    won, spent = _drive_spent(_canon_keys(), monkeypatch)
    assert won and spent == _SC_PAR, (won, spent)


@pytest.mark.parametrize("seed", SEEDS)
def test_the_door_opens_when_the_whole_poem_reads(seed, monkeypatch):
    """Drive the route, then read the tablet: the four COMPLETIONS stand in
    order (the plaque holds each head) and the door is FLOOR. The A line's
    completion has been CARVED east into the stone that was solid at build."""
    dungeon = build_dungeon_sculpting_chambers(seed)
    room = dungeon.rooms[0]
    _drive(dungeon, _canon_keys(), monkeypatch, finish=':q!\r')
    assert _poem_rows(room) == list(_SC_COMPLETIONS)
    er, ec = room.exit_pos
    assert room.cells[er][ec] == CellType.FLOOR
    # A carved a corridor: cells east of the given head that were WALL at build
    # are now FLOOR bearing the completion's tail.
    a_row = next(r for r in range(room.rows)
                 if main._wla_floor_text(room, r).split()[:1] == ['merrily'])
    assert _SC_WCOL + len(_SC_COMPLETIONS[2]) - 1 > _SC_A_END, \
        "the A completion must run east past the build floor (into stone)"
    assert room.cells[a_row][_SC_A_END + 3] == CellType.FLOOR, \
        "the stone east of the launch cell was carved to floor"


# ── each of I A o O is necessary (drop one → no win) ───────────────────────────

_DROP = {
    'O':  _K('j')
          + _K('I') + _K(_SC_I_TYPED) + [ESC] + _K('j')
          + _K('A') + _K(_SC_A_TYPED) + [ESC]
          + _K('o') + _K(_SC_COMPLETIONS[3]) + [ESC] + _K('j'),
    'I':  _K('O') + _K(_SC_COMPLETIONS[0]) + [ESC] + _K('jj')
          + _K('A') + _K(_SC_A_TYPED) + [ESC]
          + _K('o') + _K(_SC_COMPLETIONS[3]) + [ESC] + _K('j'),
    'A':  _K('O') + _K(_SC_COMPLETIONS[0]) + [ESC] + _K('j')
          + _K('I') + _K(_SC_I_TYPED) + [ESC] + _K('j')
          + _K('o') + _K(_SC_COMPLETIONS[3]) + [ESC] + _K('j'),
    'o':  _K('O') + _K(_SC_COMPLETIONS[0]) + [ESC] + _K('j')
          + _K('I') + _K(_SC_I_TYPED) + [ESC] + _K('j')
          + _K('A') + _K(_SC_A_TYPED) + [ESC] + _K('jj'),
}


@pytest.mark.parametrize("cmd", sorted(_DROP))
def test_each_insert_entry_is_necessary(cmd, monkeypatch):
    """Remove any one of I/A/o/O from the route and the vault never opens: a
    line of the poem is missing or wounded."""
    dungeon = build_dungeon_sculpting_chambers(SEEDS[0])
    result = _drive(dungeon, _DROP[cmd], monkeypatch)
    assert not result['won'], f"dropping {cmd} still won"


def test_A_alone_cannot_backdoor_the_sealed_door(monkeypatch):
    """Carving the A line with the rest of the poem unwritten never wins: the
    door is a step SOUTH of the last line, gated on the whole poem, and A (an
    east-builder) can never carve into a cell due south."""
    dungeon = build_dungeon_sculpting_chambers(SEEDS[0])
    room = dungeon.rooms[0]
    keys = _K('j') + _K('A') + _K(_SC_A_TYPED) + [ESC] + _K('jjjj')
    result = _drive(dungeon, keys, monkeypatch, finish=':q!\r')
    assert not result['won']
    er, ec = room.exit_pos
    assert room.cells[er][ec] == CellType.WALL, "the door never unsealed"


def test_a_wrong_line_keeps_the_door_shut(monkeypatch):
    """The tablet is exact: a wrong word in any line leaves the door sealed."""
    keys = (_K('O') + _K('row row row your goat') + [ESC] + _K('j')
            + _K('I') + _K(_SC_I_TYPED) + [ESC] + _K('j')
            + _K('A') + _K(_SC_A_TYPED) + [ESC]
            + _K('o') + _K(_SC_COMPLETIONS[3]) + [ESC] + _K('j'))
    dungeon = build_dungeon_sculpting_chambers(SEEDS[0])
    assert not _drive(dungeon, keys, monkeypatch)['won']


# ── o / O are forced APART by direction ───────────────────────────────────────

def test_line1_is_above_and_line4_is_below_the_given_lines(monkeypatch):
    dungeon = build_dungeon_sculpting_chambers(SEEDS[0])
    room = dungeon.rooms[0]
    _drive(dungeon, _canon_keys(), monkeypatch, finish=':q!\r')
    assert _poem_rows(room) == list(_SC_COMPLETIONS)   # top-to-bottom order holds


# ── undo re-seals the door (stateless tick) ───────────────────────────────────

def test_undo_reseals_the_door(monkeypatch):
    dungeon = build_dungeon_sculpting_chambers(SEEDS[0])
    room = dungeon.rooms[0]
    keys = _canon_keys()[:-1] + _K('u')          # undo the last line-write
    _drive(dungeon, keys, monkeypatch, finish=':q!\r')
    assert _poem_rows(room) != list(_SC_COMPLETIONS)
    er, ec = room.exit_pos
    assert room.cells[er][ec] == CellType.WALL, "door re-sealed"


# ── plaques follow their lines as o/O insert rows ─────────────────────────────

def test_plaques_realign_with_their_lines_after_inserts(monkeypatch):
    """o/O row-inserts drift the plaques; the tick re-lays each onto its
    line's slot (relative to the merrily anchor). After the full route the
    plaques stand IN ORDER, one per completion row, directly west — the
    plaque supplies each line's head and the floor its completion."""
    dungeon = build_dungeon_sculpting_chambers(SEEDS[0])
    room = dungeon.rooms[0]
    _drive(dungeon, _canon_keys(), monkeypatch, finish=':q!\r')
    c0, c1 = _SC_BAND
    completion_rows = [r for r in range(room.rows)
                       if main._wla_floor_text(room, r)[c0:c1 + 1].split()]
    plaques = sorted((ru.row, ''.join(ru.symbols)) for ru in room.char_runs
                     if ru.kind == 'verdant')
    # the four plaques sit on the four completion rows, in top-to-bottom order,
    # each naming its line's first word
    assert [row for row, _w in plaques] == completion_rows
    assert [w for _row, w in plaques] == list(_SC_TARGET)
    for ru in room.char_runs:
        if ru.kind == 'verdant':
            assert ru.col == _SC_PLQ
    # and each plaque's head + its floor completion reconstitutes the full line
    for (row, head), full in zip(plaques, _SC_LINES):
        floor = ' '.join(main._wla_floor_text(room, row)[c0:c1 + 1].split())
        assert f'{head} {floor}' == full


# ── curriculum + karaoke ──────────────────────────────────────────────────────

def test_curriculum_teaches_the_four_insert_entries():
    known = set(known_commands('sculpting_chambers'))
    assert {'I', 'A', 'o', 'O'} <= known
    prior = set(known_commands('change_extension'))   # the level before
    assert not ({'I', 'A', 'o', 'O'} & prior), "the four are new here"


@pytest.mark.parametrize("seed", SEEDS)
def test_answer_is_the_real_keystroke_tape(seed, monkeypatch):
    """room.answer is the printable keystrokes of the canonical route (Esc
    omitted, spaces separators, TYPED spaces marked <Space>). Driven as admin it
    advances answer_pos to the end without diverging."""
    room = _room(seed)
    assert room.answer == _SC_ANSWER
    assert ' '.join(_SC_ANSWER.split()) == _SC_ANSWER   # separators are single
    dungeon = build_dungeon_sculpting_chambers(seed)
    troom = dungeon.rooms[0]
    _drive(dungeon, _canon_keys(), monkeypatch, finish=':q!\r', name='admin')
    assert not troom.answer_diverged
    assert troom.answer_pos == len(troom.answer.replace(' ', ''))
