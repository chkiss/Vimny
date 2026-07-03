"""The Sculpting Chambers (slug `sculpting_chambers`): I A o O.

The topology lesson — the four insert-ENTRIES, split by axis so each does one
thing (see the o/O engine change: o/O open a Vim BLANK line, segment-width,
never bridging a wall column — that axis is A's):

  O / o  — the VERTICAL sculptors: open a blank line ABOVE / BELOW to carve a
           missing verse of the vault's votive.  The dedication must read, line
           upon line, `keep · seal · sesame · amen`; only `seal` and the `same`
           stub are given.  `keep` must sit ABOVE the topmost given line (only
           `O` reaches above) and `amen` BELOW the lowest (only `o` reaches
           below), so the two are forced apart by DIRECTION.
  A       — the HORIZONTAL sculptor: `extend_floor` carves floor east THROUGH
           the solid stone plugging the one route to the door.  ∞ (nothing else
           turns wall into floor).
  I       — the keystone: the `sesame` line is given only its tail (`same`);
           after the A-work the cursor sits far east, so `I` jumps to the line
           start to prepend `se` → `sesame`.  Soft-forced (saves the ^i / 0i
           walk); the finale.

The vault door (one gated cell at room.exit_pos) unseals the instant the votive
reads true.  A cannot cheat it: the door is a step SOUTH of A's landing (A builds
east, never INTO it) and a void rune caps the password row's east edge (the only
other floor whose east end lines up with the door column).
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
    build_dungeon_sculpting_chambers,
    _SC_ROWS, _SC_COLS, _SC_PAR, _SC_TARGET, _SC_BAND,
    _SC_SEAL_ROW, _SC_PASS_ROW, _SC_WCOL, _SC_EXIT_COL,
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


# The canonical votive route (shared by the tape and the playthrough): carve the
# verses top-down (O keep · I se · o amen), climb to the seal line, breach the
# stone (A), drop south onto the door. Esc seals each insert (free, omitted from
# the answer tape).
def _canon_keys():
    return (_K('O') + _K('keep') + [ESC]
            + _K('jj') + _K('I') + _K('se') + [ESC]
            + _K('o') + _K('amen') + [ESC]
            + _K('kk') + _K('A') + _K('wxyz') + [ESC]
            + _K('j'))


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
    return main.run_dungeon(term, 'sculpting_chambers', {}, player_name=name,
                            _dungeon=dungeon)


# ── structure ─────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("seed", SEEDS)
def test_dimensions_anchors_par_budget(seed):
    room = _room(seed)
    assert (room.rows, room.cols) == (_SC_ROWS, _SC_COLS)
    assert room.spawn_pos == (_SC_SEAL_ROW, _SC_WCOL)
    assert room.exit_pos == (_SC_PASS_ROW, _SC_EXIT_COL)
    assert room.par == _SC_PAR
    assert room.budget == math.ceil(_SC_PAR * 1.4)


@pytest.mark.parametrize("seed", SEEDS)
def test_only_seal_and_the_stub_are_given(seed):
    """The tablet starts with just two verses on the floor: the `seal` anchor and
    the password's `same` tail. `keep` and `amen` have no line yet — the player
    must OPEN them."""
    room = _room(seed)
    c0, c1 = _SC_BAND
    verses = [main._sc_leading_verse(room, r, c0, c1) for r in range(room.rows)]
    verses = [v for v in verses if v]
    assert verses == ['seal', 'same']


@pytest.mark.parametrize("seed", SEEDS)
def test_door_is_sealed_and_east_of_the_seal_line_is_stone(seed):
    """The exit cell is WALL at build (the votive unseals it), and the stone east
    of the `seal` segment is solid — A's only launch is the segment's east edge,
    not a stray corridor."""
    room = build_dungeon_sculpting_chambers(seed).rooms[0]
    er, ec = room.exit_pos
    assert room.cells[er][ec] == CellType.WALL
    # east of the seal segment (its bare launch cell) is wall, all the way to the
    # exit column — nothing pre-floored for A to jump past.
    for c in range(_SC_WCOL + 5, _SC_EXIT_COL + 1):
        assert room.cells[_SC_SEAL_ROW][c] == CellType.WALL, c


# ── the door is unreachable until the votive reads true (teleport audit) ───────

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
    """With the door sealed, no line jump may land on it (it is WALL, and never a
    row's first standable cell)."""
    room = build_dungeon_sculpting_chambers(seed).rooms[0]
    jumps = ([('G', 1, False), ('gg', 1, False), ('H', 1, False),
              ('M', 1, False), ('L', 1, False)]
             + [('G', n, True) for n in range(1, _SC_ROWS)])
    for motion, count, given in jumps:
        p = Player(row=room.spawn_pos[0], col=room.spawn_pos[1])
        apply_motion(p, motion, count, room, count_given=given)
        assert (p.row, p.col) != room.exit_pos, f"{motion} dropped onto the door"
        assert room.is_passable(p.row, p.col), f"{motion} landed in a wall"


# ── the votive, driven for real ───────────────────────────────────────────────

@pytest.mark.parametrize("seed", SEEDS)
def test_full_votive_route_wins_par_perfect(seed, monkeypatch):
    dungeon = build_dungeon_sculpting_chambers(seed)
    result = _drive(dungeon, _canon_keys(), monkeypatch)
    assert result['won'] and result['stars'] == 2, result


@pytest.mark.parametrize("seed", SEEDS)
def test_the_door_opens_only_when_the_whole_votive_reads(seed, monkeypatch):
    """Drive the votive, then read the tablet: the four verses stand in order and
    the door is FLOOR."""
    dungeon = build_dungeon_sculpting_chambers(seed)
    room = dungeon.rooms[0]
    _drive(dungeon, _canon_keys(), monkeypatch, finish=':q!\r')
    c0, c1 = _SC_BAND
    verses = [v for v in (main._sc_leading_verse(room, r, c0, c1)
                          for r in range(room.rows)) if v]
    assert verses == list(_SC_TARGET)
    er, ec = room.exit_pos
    assert room.cells[er][ec] == CellType.FLOOR


# ── each of I A o O is necessary (drop one → no win) ───────────────────────────

_DROP = {
    'O':  _K('jj') + _K('I') + _K('se') + [ESC] + _K('o') + _K('amen') + [ESC]
          + _K('kk') + _K('A') + _K('wxyz') + [ESC] + _K('j'),
    'o':  _K('O') + _K('keep') + [ESC] + _K('jj') + _K('I') + _K('se') + [ESC]
          + _K('kk') + _K('A') + _K('wxyz') + [ESC] + _K('j'),
    'I':  _K('O') + _K('keep') + [ESC] + _K('o') + _K('amen') + [ESC]
          + _K('kk') + _K('A') + _K('wxyz') + [ESC] + _K('j'),
    'A':  _K('O') + _K('keep') + [ESC] + _K('jj') + _K('I') + _K('se') + [ESC]
          + _K('o') + _K('amen') + [ESC] + _K('kk') + _K('j'),
}


@pytest.mark.parametrize("cmd", sorted(_DROP))
def test_each_insert_entry_is_necessary(cmd, monkeypatch):
    """Remove any one of I/A/o/O from the route and the vault never opens: O/o
    carve the verses the votive needs, I finishes the password, A breaches the
    stone to the door."""
    dungeon = build_dungeon_sculpting_chambers(SEEDS[0])
    result = _drive(dungeon, _DROP[cmd], monkeypatch)
    assert not result['won'], f"dropping {cmd} still won"


def test_A_alone_cannot_backdoor_the_sealed_door(monkeypatch):
    """A breaches the stone, but with the votive UNwritten the door stays sealed —
    A (an east-builder) can never carve into a cell that is a step SOUTH, and the
    password row's east edge is void-capped. Breach + walk wins nothing."""
    dungeon = build_dungeon_sculpting_chambers(SEEDS[0])
    room = dungeon.rooms[0]
    # climb nowhere; just breach east off the seal line and try to reach the door
    keys = _K('A') + _K('wxyzab') + [ESC] + _K('j') + _K('jjjj')
    result = _drive(dungeon, keys, monkeypatch, finish=':q!\r')
    assert not result['won']
    er, ec = room.exit_pos
    assert room.cells[er][ec] == CellType.WALL, "the door never unsealed"


# ── o / O are forced APART by direction ───────────────────────────────────────

def test_keep_is_above_and_amen_is_below_the_given_lines(monkeypatch):
    """The votive order forces the two open-line commands apart: `keep` is the
    TOPMOST verse (only O opens a line above the top given line) and `amen` is the
    BOTTOMMOST (only o opens below the lowest). After the route, the rows confirm
    it."""
    dungeon = build_dungeon_sculpting_chambers(SEEDS[0])
    room = dungeon.rooms[0]
    _drive(dungeon, _canon_keys(), monkeypatch, finish=':q!\r')
    c0, c1 = _SC_BAND
    rows = {main._sc_leading_verse(room, r, c0, c1): r
            for r in range(room.rows)
            if main._sc_leading_verse(room, r, c0, c1)}
    assert rows['keep'] < rows['seal'] < rows['sesame'] < rows['amen']


# ── undo re-seals the door (stateless tick) ───────────────────────────────────

def test_undo_reseals_the_door(monkeypatch):
    """The tick is stateless: unwriting a verse (u) drops the votive below true
    and the door re-seals."""
    dungeon = build_dungeon_sculpting_chambers(SEEDS[0])
    room = dungeon.rooms[0]
    # write the whole votive, breach, then undo the last verse-write (amen)
    keys = (_K('O') + _K('keep') + [ESC] + _K('jj') + _K('I') + _K('se') + [ESC]
            + _K('o') + _K('amen') + [ESC] + _K('u'))
    _drive(dungeon, keys, monkeypatch, finish=':q!\r')
    c0, c1 = _SC_BAND
    verses = [v for v in (main._sc_leading_verse(room, r, c0, c1)
                          for r in range(room.rows)) if v]
    assert 'amen' not in verses, "the amen verse was undone"
    er, ec = room.exit_pos
    assert room.cells[er][ec] == CellType.WALL, "door re-sealed"


# ── curriculum + karaoke ──────────────────────────────────────────────────────

def test_curriculum_teaches_the_four_insert_entries():
    known = set(known_commands('sculpting_chambers'))
    assert {'I', 'A', 'o', 'O'} <= known
    prior = set(known_commands('change_extension'))   # the level before
    assert not ({'I', 'A', 'o', 'O'} & prior), "the four are new here"


@pytest.mark.parametrize("seed", SEEDS)
def test_answer_is_the_real_keystroke_tape(seed, monkeypatch):
    """room.answer is the printable keystrokes of the canonical route (Esc
    omitted, spaces separators). Driven as admin it advances answer_pos to the
    end without diverging."""
    room = _room(seed)
    assert room.answer == 'Okeep jj Ise oamen kk Awxyz j'
    dungeon = build_dungeon_sculpting_chambers(seed)
    troom = dungeon.rooms[0]
    _drive(dungeon, _canon_keys(), monkeypatch, finish=':q!\r', name='admin')
    assert not troom.answer_diverged
    assert troom.answer_pos == len(troom.answer.replace(' ', ''))
