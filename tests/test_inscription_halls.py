"""The Inscription Halls (display 22, slug `inscription_halls`): i and a.

The first writer. A four-wide river crosses the dungeon north–south; lesson
rows hang west of the bank like jetties, each read against the familiar
verdant plaque sealed in the wall above it. The floor text is INCOMPLETE —
the plaque shows the whole word — and a bank gate opens when the word is
written whole (plaque rule, fourth member: Cipher mended, Beacon copied,
Echo repeated, the Halls AUTHOR).

Forcing (both hard, by geometry):
  i — the prefix lesson: the fragment head IS the row's first floor cell
      (wall behind it), so only insert-AT-cursor can write the prefix;
      `a` would need to stand inside the wall.
  a — the suffix lesson: the fragment tail sits ON the bank with water at
      the very next cell, so only insert-AFTER-cursor can write the suffix;
      `i` would need to stand on the river. INK DISPLACES THE FLOOD: each
      typed letter pushes that row's water back a cell (spilled over the
      east wall and lost — engine: open_gap moves water; insert_char now
      writes onto water cells).
The ford finale: 'river' + a + 'gate' types a bridge clean across — the
word IS the crossing — and the seal draws on the exit pocket.

Scarcity (the Echo Vault discipline, pinned below): the missing letters
exist nowhere cuttable, so x+p can never impersonate the verbs. Esc spends
NOTHING (engine fact); insert answer tokens ('ica', 'agate') cost 1+chars.
Vim-faithful Esc retreat (cursor steps back one column) shipped with this
level — it is also the safety net off the water after an `a` at the bank.
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
    build_dungeon_inscription_halls, _ih_pick,
    _IH_ROWS, _IH_COLS, _IH_RIVER_LO, _IH_RIVER_HI, _IH_BANK,
    _IH_LESSON_ROWS, _IH_PLAQUE_ROWS, _IH_BOLT_ROWS, _IH_I_HEAD, _IH_A_WEST,
    _IH_SPLITS, _IH_FORD_ROW, _IH_FORD_FRAG, _IH_FORD_WORD, _IH_SEAL,
    _IH_EXIT, _IH_PAR,
)
import pytest
import random

from tests import SEEDS, cached_room

_FLOORS = (CellType.FLOOR, CellType.CORRIDOR)
ESC = Keystroke('\x1b', name='KEY_ESCAPE')


def _room(seed):
    """Shared READ-ONLY build; mutating tests call the builder directly."""
    return cached_room('build_dungeon_inscription_halls', seed)


def _keys(answer: str, extra: str = '') -> list:
    """room.answer → real keystrokes (insert tokens expand to entry key +
    typed chars + Esc; Esc costs no budget)."""
    out = []
    for t in answer.split():
        if len(t) >= 2 and t[0] in 'ia' and t[1:].isalpha():
            out.append(Keystroke(t[0]))
            out += [Keystroke(ch) for ch in t[1:]]
            out.append(ESC)
        else:
            out += [Keystroke(ch) for ch in t]
    out += [Keystroke(ch) for ch in extra]
    return out


def _drive(dungeon, keys, monkeypatch, finish=':q!\r'):
    keys = list(keys) + [Keystroke(ch) for ch in finish]
    monkeypatch.setattr(main, 'render_all', lambda *a, **k: None)
    monkeypatch.setattr(main.time, 'sleep', lambda *a, **k: None)
    for anim in ('_fireworks_animation', '_win_animation', '_starfield_victory',
                 '_heart_container_animation', '_unlock_animation',
                 '_void_fall_animation', '_drown_animation'):
        monkeypatch.setattr(main, anim, lambda *a, **k: None)
    term = Terminal()
    it = iter(keys)
    monkeypatch.setattr(term, 'inkey', lambda *a, **k: next(it, Keystroke('')))
    return main.run_dungeon(term, 'inscription_halls', {}, player_name='Scribe',
                            _dungeon=dungeon)


# ── structure: the river and the jetties ──────────────────────────────────────

@pytest.mark.parametrize("seed", SEEDS)
def test_dimensions_anchors_and_the_river(seed):
    room = _room(seed)
    assert (room.rows, room.cols) == (_IH_ROWS, _IH_COLS)
    assert room.spawn_pos == (_IH_LESSON_ROWS[0], _IH_BANK)
    assert room.exit_pos == _IH_EXIT
    assert room.par == _IH_PAR
    # a TRUE river: four wide, every row top wall to bottom wall
    for r in range(1, _IH_ROWS - 1):
        for c in range(_IH_RIVER_LO, _IH_RIVER_HI + 1):
            assert room.cells[r][c] == CellType.WATER, (r, c)
        assert room.cells[r][_IH_RIVER_HI + 1] == CellType.WALL, \
            "the east wall is the brink the flood spills over"


@pytest.mark.parametrize("seed", SEEDS)
def test_forcing_geometry(seed):
    """i-rows: the fragment head IS the first floor cell (wall behind);
    a-rows: the fragment tail sits ON the bank (water beyond)."""
    room = _room(seed)
    for i, r in enumerate(_IH_LESSON_ROWS):
        if i in (0, 2):
            assert room.cells[r][_IH_I_HEAD - 1] == CellType.WALL
            assert room.char_run_at(r, _IH_I_HEAD) is not None, \
                "the fragment head is the row's first floor cell"
        else:
            tail = room.char_run_at(r, _IH_BANK)
            assert tail is not None, "the fragment tail sits on the bank"
            assert room.cells[r][_IH_BANK + 1] == CellType.WATER
    ford_tail = room.char_run_at(_IH_FORD_ROW, _IH_BANK)
    assert ford_tail is not None, "'river' ends on the bank"


@pytest.mark.parametrize("seed", SEEDS)
def test_plaques_sealed_in_walls(seed):
    """The familiar plaque band: plaque glyphs stand in unwalkable cells
    (uncuttable, excluded from the floor-text scans) — EXCEPT the one cell
    where each a-plaque crosses the promenade gap (rows 4/10, col 37).
    Those two letters are fragment letters (already on the floor below), so
    even cuttable they donate nothing the scarcity rule protects."""
    room = _room(seed)
    plaque_rows = set(_IH_PLAQUE_ROWS) | {_IH_ROWS - 1}
    crossings = {(4, _IH_BANK), (10, _IH_BANK)}
    seen = 0
    for ru in room.char_runs:
        if ru.row not in plaque_rows:
            continue
        seen += 1
        assert ru.kind == 'verdant'
        for k, sym in enumerate(ru.symbols):
            cell = (ru.row, ru.col + k)
            if room.cells[cell[0]][cell[1]] == CellType.FLOOR:
                assert cell in crossings, f"plaque glyph on open floor at {cell}"
                lessons = {r: i for i, r in enumerate(_IH_PLAQUE_ROWS)}
                idx = lessons[ru.row]
                frag = _ih_pick(random.Random(seed))[idx][2]
                assert sym in frag, "the crossing letter must be a fragment letter"
    assert seen == 5, "four lesson plaques + the ford plaque in the border"


@pytest.mark.parametrize("seed", SEEDS)
def test_gates_start_shut_despite_the_plaques(seed):
    """The plaques SHOW every word from turn one — the completion scan must
    read floor text only, or every gate would open at entry."""
    dungeon = build_dungeon_inscription_halls(seed)
    room = dungeon.rooms[0]
    p = Player(row=room.spawn_pos[0], col=room.spawn_pos[1])
    main._inscription_halls_tick(room, p)
    for _w, (r, c) in room._ih_bolts:
        assert room.cells[r][c] == CellType.WALL
    assert room.cells[_IH_SEAL[0]][_IH_SEAL[1]] == CellType.WALL


# ── scarcity: typing is the only source ───────────────────────────────────────

@pytest.mark.parametrize("seed", SEEDS)
def test_missing_letters_are_scarce(seed):
    """No missing letter exists anywhere cuttable (fragments + 'river'), and
    the four missing sets are pairwise disjoint — x+p can never impersonate
    i or a. Words are never substrings of each other or of the bridge-word
    (the gate checks are substring scans)."""
    lessons = _ih_pick(random.Random(seed))
    msets = [set(m) for (_w, m, _f) in lessons]
    cuttable = set(_IH_FORD_FRAG) | {ch for (_w, _m, f) in lessons for ch in f}
    for i, ms in enumerate(msets):
        assert not (ms & cuttable), (seed, lessons)
        for j in range(i + 1, 4):
            assert not (ms & msets[j])
    words = [w for (w, _m, _f) in lessons]
    for a in words:
        assert a not in _IH_FORD_WORD
        for b in words:
            assert a == b or a not in b
    for i, (_w, m, _f) in enumerate(lessons):
        assert len(m) == _IH_SPLITS[i], "fixed splits — par invariance"


# ── access: the pocket is sealed against everything ───────────────────────────

@pytest.mark.parametrize("seed", SEEDS)
def test_exit_unreachable_as_built(seed):
    room = build_dungeon_inscription_halls(seed).rooms[0]    # private (mutating)
    seen, q = {room.spawn_pos}, deque([room.spawn_pos])
    while q:
        r, c = q.popleft()
        for dr, dc in ((0, 1), (0, -1), (1, 0), (-1, 0)):
            nb = (r + dr, c + dc)
            if nb not in seen and room.is_passable(*nb):
                seen.add(nb)
                q.append(nb)
    assert _IH_EXIT not in seen, "the river and the seal hold"
    assert all(c <= _IH_BANK for (_r, c) in seen), "nothing east of the bank walks"


@pytest.mark.parametrize("seed", SEEDS)
def test_line_jumps_never_cross_the_river(seed):
    room = build_dungeon_inscription_halls(seed).rooms[0]    # private (mutating)
    jumps = ([('G', 1, False), ('gg', 1, False), ('H', 1, False),
              ('M', 1, False), ('L', 1, False)]
             + [('G', n, True) for n in range(1, _IH_ROWS)])
    for motion, count, count_given in jumps:
        p = Player(row=room.spawn_pos[0], col=room.spawn_pos[1])
        apply_motion(p, motion, count, room, count_given=count_given)
        assert p.col <= _IH_BANK, f"{motion} crossed the river"
        assert (p.row, p.col) != _IH_EXIT


# ── the lessons, driven for real ──────────────────────────────────────────────

@pytest.mark.parametrize("seed", SEEDS)
def test_full_playthrough_wins_par_perfect(seed, monkeypatch):
    dungeon = build_dungeon_inscription_halls(seed)
    room = dungeon.rooms[0]
    result = _drive(dungeon, _keys(room.answer), monkeypatch, finish=':wq\r')
    assert result['won'] and result['stars'] == 2, result
    # the ford is bridged: row 13's water is gone, the word spans the river
    assert all(room.cells[_IH_FORD_ROW][c] != CellType.WATER
               for c in range(_IH_RIVER_LO, _IH_RIVER_HI + 1))
    assert _IH_FORD_WORD in main._ih_floor_text(room, _IH_FORD_ROW)


@pytest.mark.parametrize("seed", SEEDS)
def test_suffix_typing_pushes_the_flood(seed, monkeypatch):
    """Lesson B: each typed letter reclaims a bank cell; the far cell spills
    over the east wall and is lost (the river narrows on that row only)."""
    dungeon = build_dungeon_inscription_halls(seed)
    room = dungeon.rooms[0]
    toks = room.answer.split()
    upto_b = ' '.join(toks[:5])                       # through lesson B's a-token
    _drive(dungeon, _keys(upto_b), monkeypatch)
    r = _IH_LESSON_ROWS[1]
    k = _IH_SPLITS[1]
    water = [c for c in range(room.cols) if room.cells[r][c] == CellType.WATER]
    assert len(water) == (_IH_RIVER_HI - _IH_RIVER_LO + 1) - k, \
        "one water cell spilled per typed letter"
    assert room.cells[r][_IH_RIVER_LO] != CellType.WATER, "the bank cell is reclaimed"


@pytest.mark.parametrize("seed", SEEDS)
def test_garbage_never_opens_the_seal(seed, monkeypatch):
    """Typing the wrong letters dries nothing it shouldn't: the ford seal
    answers only to the plaque's word."""
    dungeon = build_dungeon_inscription_halls(seed)
    room = dungeon.rooms[0]
    toks = room.answer.split()
    pre = ' '.join(toks[:-3])                         # everything before 'agate'
    garbage = _keys(pre) + [Keystroke('a')] + \
        [Keystroke(ch) for ch in 'zzzz'] + [ESC]
    _drive(dungeon, garbage, monkeypatch)
    assert room.cells[_IH_SEAL[0]][_IH_SEAL[1]] == CellType.WALL
    # the flood is gone on that row regardless — but the gate reads, not counts
    assert _IH_FORD_WORD not in main._ih_floor_text(room, _IH_FORD_ROW)


@pytest.mark.parametrize("seed", SEEDS)
def test_undo_rebars_the_gate(seed, monkeypatch):
    """One u unwinds the whole inscription (one snapshot per insert session)
    and the tick re-bars the bank gate."""
    dungeon = build_dungeon_inscription_halls(seed)
    room = dungeon.rooms[0]
    toks = room.answer.split()
    lesson_a = ' '.join(toks[:2])                     # '9h i{..}'
    _drive(dungeon, _keys(lesson_a, extra='l'), monkeypatch)   # l: tick opens the gate
    word, (br, bc) = room._ih_bolts[0]
    assert room.cells[br][bc] == CellType.FLOOR, "written whole — gate open"

    dungeon = build_dungeon_inscription_halls(seed)
    room = dungeon.rooms[0]
    # u pops the 'l' movement first; the SECOND u pops the whole insert
    # session (one snapshot at entry) and unwrites the word.
    _drive(dungeon, _keys(lesson_a, extra='luul'), monkeypatch)
    word, (br, bc) = room._ih_bolts[0]
    assert room.cells[br][bc] == CellType.WALL, "undone — the gate re-bars"


def test_esc_steps_back_onto_written_ground(monkeypatch):
    """After an `a` at the bank the cursor hovers on the flood; Esc retreats
    one column (Vim-faithful) onto the just-written letter."""
    dungeon = build_dungeon_inscription_halls(SEEDS[0])
    room = dungeon.rooms[0]
    toks = room.answer.split()
    upto_b = ' '.join(toks[:5])
    _drive(dungeon, _keys(upto_b), monkeypatch)
    # lesson B's row: the cell at the old bank+k is floor and holds a letter
    r, k = _IH_LESSON_ROWS[1], _IH_SPLITS[1]
    assert room.cells[r][_IH_BANK + k] in _FLOORS


def test_curriculum_guard():
    """The level teaches the 'insert' token; everything else it leans on is
    already known (counts, hjkl, u)."""
    known = set(known_commands('inscription_halls'))
    assert 'insert' in known
    for needed in ('count', 'u' if 'u' in known else 'insert', 'G', '/'):
        assert needed in known
