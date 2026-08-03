# Vimny — a Vim-teaching dungeon crawler.
# Copyright (C) 2026 Chas Kissick
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""The Inscription Halls (slug `inscription_halls`): i and a.

The first writer. A four-wide river MEANDERS down the dungeon, its west edge
drifting four columns west from headwater to ford; lesson jetties hang west
of the bank, each read against the familiar verdant plaque sealed in the
wall above it. The floor text is INCOMPLETE — the plaque shows the whole
word (plaque rule, fourth member: Cipher mended, Beacon copied, Echo
repeated, the Halls AUTHOR) — and each word written whole grinds open ONE of
five stone walls stacked east of the ford before the exit. Five in series:
nothing wins unfinished, however the player travels — the par route hops
jetties with ( / ) / e (embraced: sentence jumps only optimize travel).

Forcing (both hard, by geometry):
  i — the prefix lesson: the fragment head IS the row's first floor cell
      (wall behind it), so only insert-AT-cursor can write the prefix.
  a — the suffix lesson: the fragment tail sits ON the row's bank with water
      at the very next cell, so only insert-AFTER-cursor can write the
      suffix. INK DISPLACES THE FLOOD: each typed letter pushes that row's
      water back a cell (spilled over the east wall and lost).
The ford finale: 'river' + a + 'gate' types a bridge clean across — the word
IS the crossing. The bridge-word owns the WESTMOST exit wall, so typed water
always crushes against stone, never slides into an opened corridor.

Scarcity (the Echo Vault discipline, pinned below): the missing letters
exist nowhere cuttable, so x+p can never impersonate the verbs. Esc spends
NOTHING (engine fact); insert answer tokens ('ica', 'agate') cost 1+chars.
THE LANDING RULE (engine-wide, shipped from this level's playtests): no jump
lands where the cursor cannot stand — pinned here by the known-motion sweep.
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
    build_dungeon_inscription_halls, _ih_pick, _ih_river_lo, _ih_bank,
    _IH_ROWS, _IH_COLS, _IH_RIVER_W, _IH_LESSON_ROWS, _IH_PLAQUE_ROWS,
    _IH_GAPS, _IH_I_HEAD, _IH_A_WEST, _IH_SPLITS, _IH_FORD_ROW,
    _IH_FORD_FRAG, _IH_FORD_WORD, _IH_SEALS, _IH_EXIT, _IH_PAR,
)
import pytest
import random

from engine import tape
from tests import SEEDS, cached_room

_FLOORS = (CellType.FLOOR, CellType.CORRIDOR)
ESC = Keystroke('\x1b', name='KEY_ESCAPE')


def _room(seed):
    """Shared READ-ONLY build; mutating tests call the builder directly."""
    return cached_room('build_dungeon_inscription_halls', seed)


def _keys(answer: str, extra: str = '') -> list:
    """room.answer → real keystrokes.

    The tape writes Esc as `<Esc>` (engine/tape.py), so there is nothing to infer
    and nothing to guess at: `to_keys` is the one converter. This used to sniff
    insert tokens (`t[0] in 'ia' and t[1:].isalpha()`) and append an Esc of its
    own — which silently stopped matching once the tape carried `<Esc>` itself, and
    then fed the glyph through as printable text. The run never left INSERT, the
    trailing `:q!` was typed into the buffer, and the test hung instead of
    failing.
    """
    return tape.to_keys(answer) + [Keystroke(ch) for ch in extra]


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


# ── structure: the meandering river and the jetties ───────────────────────────

@pytest.mark.parametrize("seed", SEEDS)
def test_dimensions_anchors_and_the_river(seed):
    room = _room(seed)
    assert (room.rows, room.cols) == (_IH_ROWS, _IH_COLS)
    assert room.spawn_pos == (_IH_LESSON_ROWS[0], _ih_bank(_IH_LESSON_ROWS[0]))
    assert room.exit_pos == _IH_EXIT
    assert room.par == _IH_PAR
    for r in range(1, _IH_ROWS - 1):
        lo = _ih_river_lo(r)
        for c in range(lo, lo + _IH_RIVER_W):
            assert room.cells[r][c] == CellType.WATER, (r, c)
        assert room.cells[r][lo + _IH_RIVER_W] == CellType.WALL or \
            (r, lo + _IH_RIVER_W) in _IH_SEALS, \
            "the east wall is the brink the flood spills over"


def test_river_truly_meanders():
    """No straight vertical borders — the river drifts a
    net 4 columns west, one column at a time (contiguous, always 4 wide)."""
    los = [_ih_river_lo(r) for r in range(1, _IH_ROWS - 1)]
    assert los[0] - los[-1] == 4, "net drift of four columns west"
    assert all(0 <= a - b <= 1 for a, b in zip(los, los[1:])), \
        "the bank steps at most one column per row, always westward"


@pytest.mark.parametrize("seed", SEEDS)
def test_forcing_geometry(seed):
    """i-rows: the fragment head IS the first floor cell (wall behind);
    a-rows: the fragment tail sits ON the row's bank (water beyond)."""
    room = _room(seed)
    for i, r in enumerate(_IH_LESSON_ROWS):
        if i in (0, 2):
            assert room.cells[r][_IH_I_HEAD - 1] == CellType.WALL
            assert room.char_run_at(r, _IH_I_HEAD) is not None, \
                "the fragment head is the row's first floor cell"
        else:
            bank = _ih_bank(r)
            assert room.char_run_at(r, bank) is not None, \
                "the fragment tail sits on the bank"
            assert room.cells[r][bank + 1] == CellType.WATER
    assert room.char_run_at(_IH_FORD_ROW, _ih_bank(_IH_FORD_ROW)) is not None, \
        "'river' ends on the ford's bank"


@pytest.mark.parametrize("seed", SEEDS)
def test_plaques_sealed_in_walls(seed):
    """The familiar plaque band: plaque glyphs stand in unwalkable cells
    (uncuttable, excluded from the floor-text scans) — EXCEPT the one cell
    where each a-plaque crosses its promenade connector. Those letters are
    fragment letters (already on the floor below), so even cuttable they
    donate nothing the scarcity rule protects."""
    room = _room(seed)
    plaque_rows = set(_IH_PLAQUE_ROWS) | {_IH_ROWS - 1}
    crossings = {(r, c) for (r, c) in _IH_GAPS if r in _IH_PLAQUE_ROWS}
    lessons = _ih_pick(random.Random(seed))
    by_prow = {r: i for i, r in enumerate(_IH_PLAQUE_ROWS)}
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
                assert sym in lessons[by_prow[ru.row]][2], \
                    "the crossing letter must be a fragment letter"
    assert seen == 5, "four lesson plaques + the ford plaque in the border"


@pytest.mark.parametrize("seed", SEEDS)
def test_walls_start_shut_despite_the_plaques(seed):
    """The plaques SHOW every word from turn one — the completion scan must
    read floor text only, or every exit wall would open at entry."""
    dungeon = build_dungeon_inscription_halls(seed)
    room = dungeon.rooms[0]
    p = Player(row=room.spawn_pos[0], col=room.spawn_pos[1])
    main._inscription_halls_tick(room, p)
    for (r, c) in _IH_SEALS:
        assert room.cells[r][c] == CellType.WALL


@pytest.mark.parametrize("seed", SEEDS)
def test_five_walls_one_per_word_bridge_word_westmost(seed):
    room = _room(seed)
    assert len(room._ih_bolts) == 5
    words = [w for (w, _cell) in room._ih_bolts]
    cells = [cell for (_w, cell) in room._ih_bolts]
    assert sorted(cells) == sorted(_IH_SEALS)
    assert room._ih_bolts[0] == (_IH_FORD_WORD, _IH_SEALS[0]), \
        "the bridge-word owns the WESTMOST wall (typed water crushes on it)"
    assert len(set(words)) == 5


# ── scarcity: typing is the only source ───────────────────────────────────────

@pytest.mark.parametrize("seed", SEEDS)
def test_missing_letters_are_scarce(seed):
    """No missing letter exists anywhere cuttable (fragments + 'river'), and
    the four missing sets are pairwise disjoint — x+p can never impersonate
    i or a. Words are never substrings of each other or of the bridge-word
    (the wall checks are substring scans)."""
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


# ── access: the exit is five walls deep ───────────────────────────────────────

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
    room = build_dungeon_inscription_halls(seed).rooms[0]    # private (mutating)
    seen = _reachable(room)
    assert _IH_EXIT not in seen, "the river and the five walls hold"
    assert all(c <= _ih_bank(r) for (r, c) in seen), \
        "nothing east of the bank walks"


@pytest.mark.parametrize("seed", SEEDS)
def test_line_jumps_never_cross_the_river(seed):
    room = build_dungeon_inscription_halls(seed).rooms[0]    # private (mutating)
    jumps = ([('G', 1, False), ('gg', 1, False), ('H', 1, False),
              ('M', 1, False), ('L', 1, False)]
             + [('G', n, True) for n in range(1, _IH_ROWS)])
    for motion, count, count_given in jumps:
        p = Player(row=room.spawn_pos[0], col=room.spawn_pos[1])
        apply_motion(p, motion, count, room, count_given=count_given)
        assert p.col <= _ih_bank(p.row), f"{motion} crossed the river"
        assert (p.row, p.col) != _IH_EXIT


@pytest.mark.parametrize("seed", SEEDS)
def test_every_known_motion_lands_passable_and_west(seed):
    """The pressure sweep: every motion known by The Inscription Halls, applied from
    every passable west-side cell, must land somewhere the engine accounts
    for — a passable cell west of the river, or a WATER cell (the drown
    trap: the main loop damages and bounces the player, so $ on a jetty
    dunks you — punished, not a leak). Landing in a WALL or on floor east
    of the river is the `)`-cheese class: a bug. THE LANDING RULE's pin."""
    room = build_dungeon_inscription_halls(seed).rooms[0]    # private (mutating)
    spots = {(r, c) for r in range(room.rows) for c in range(room.cols)
             if room.is_passable(r, c) and c <= _ih_bank(r)}
    targets = sorted({sym for ru in room.char_runs for sym in ru.symbols})
    motions = ([(m, 1, False) for m in
                ('h', 'j', 'k', 'l', 'w', 'b', 'e', 'W', 'B', 'E', 'ge', 'gE',
                 '0', '^', '$', '(', ')', '{', '}', '%', 'G', 'gg',
                 'H', 'M', 'L')]
               + [(m, n, True) for m in ('h', 'j', 'k', 'l', 'w', 'e', 'G')
                  for n in (2, 5, 9)])

    def ok(p, what):
        on_water = room.cells[p.row][p.col] == CellType.WATER
        assert room.is_passable(p.row, p.col) or on_water, \
            f"{what} landed in a wall at {(p.row, p.col)}"
        if not on_water:                       # water landings drown + bounce
            assert p.col <= _ih_bank(p.row), \
                f"{what} crossed the river to {(p.row, p.col)}"

    for (r0, c0) in sorted(spots):
        for motion, count, count_given in motions:
            p = Player(row=r0, col=c0)
            apply_motion(p, motion, count, room, count_given=count_given)
            ok(p, f"{motion} from {(r0, c0)}")
        for tgt in targets:
            for fm in ('f', 'F', 't', 'T'):
                p = Player(row=r0, col=c0)
                apply_motion(p, fm, 1, room, target=tgt)
                ok(p, f"{fm}{tgt} from {(r0, c0)}")


@pytest.mark.parametrize("seed", SEEDS)
def test_search_skips_the_walled_plaques(seed):
    """/word, with the word standing only on the plaque (a wall band), finds
    nothing — a match you cannot stand on is not a landing. Fragments on the
    floor stay searchable."""
    from engine.search import find_next
    room = _room(seed)
    p = Player(row=room.spawn_pos[0], col=room.spawn_pos[1])
    for word, _gate in room._ih_bolts:
        if word == _IH_FORD_WORD:
            continue
        assert find_next(room, p, word, True) is None, \
            "the plaque word must not be a search landing"
    frag = ''.join(room.char_run_at(_IH_LESSON_ROWS[0], _IH_I_HEAD).symbols)
    dest = find_next(room, p, frag, True)
    assert dest is not None and room.is_passable(*dest)


@pytest.mark.parametrize("seed", SEEDS)
def test_bridging_early_cannot_win(seed, monkeypatch):
    """G + agate builds the bridge first — only the bridge-word's own wall
    opens; four lesson walls still bar the exit. Nothing wins unfinished."""
    dungeon = build_dungeon_inscription_halls(seed)
    room = dungeon.rooms[0]
    keys = ([Keystroke('G'), Keystroke('4'), Keystroke('l'), Keystroke('a')]
            + [Keystroke(ch) for ch in 'gate'] + [ESC]
            + [Keystroke(ch) for ch in 'lllllll'])
    res = _drive(dungeon, keys, monkeypatch)
    assert not res['won'], "the bridge alone must never win"
    assert room.cells[_IH_SEALS[0][0]][_IH_SEALS[0][1]] == CellType.FLOOR, \
        "the bridge-word honestly opens its OWN wall"
    for (r, c) in _IH_SEALS[1:]:
        assert room.cells[r][c] == CellType.WALL, \
            "the lesson walls hold until their words are written"


# ── the lessons, driven for real ──────────────────────────────────────────────

@pytest.mark.parametrize("seed", SEEDS)
def test_full_playthrough_wins_par_perfect(seed, monkeypatch):
    """The canonical sentence-hop route: ( / ) / e between jetties, i and a
    at the triggers, the typed bridge, the five open walls, the exit."""
    dungeon = build_dungeon_inscription_halls(seed)
    room = dungeon.rooms[0]
    result = _drive(dungeon, _keys(room.answer), monkeypatch, finish=':wq\r')
    assert result['won'] and result['stars'] == 2, result
    lo = _ih_river_lo(_IH_FORD_ROW)
    assert all(room.cells[_IH_FORD_ROW][c] != CellType.WATER
               for c in range(lo, lo + _IH_RIVER_W))
    assert _IH_FORD_WORD in main._ih_floor_text(room, _IH_FORD_ROW)
    for (r, c) in _IH_SEALS:
        assert room.cells[r][c] == CellType.FLOOR, "all five walls open"


@pytest.mark.parametrize("seed", SEEDS)
def test_suffix_typing_pushes_the_flood(seed, monkeypatch):
    """Lesson B: each typed letter reclaims a bank cell; the far cell spills
    over the east wall and is lost (the river narrows on that row only)."""
    dungeon = build_dungeon_inscription_halls(seed)
    room = dungeon.rooms[0]
    toks = room.answer.split()
    upto_b = ' '.join(toks[:5])                       # ( i{..} ) e a{..}
    _drive(dungeon, _keys(upto_b), monkeypatch)
    r, k = _IH_LESSON_ROWS[1], _IH_SPLITS[1]
    water = [c for c in range(room.cols) if room.cells[r][c] == CellType.WATER]
    assert len(water) == _IH_RIVER_W - k, "one water cell spilled per letter"
    assert room.cells[r][_ih_river_lo(r)] != CellType.WATER, \
        "the bank cell is reclaimed"


@pytest.mark.parametrize("seed", SEEDS)
def test_garbage_never_opens_the_walls(seed, monkeypatch):
    """Typing the wrong letters at the ford dries the row but opens nothing:
    the walls answer only to the plaques' words."""
    dungeon = build_dungeon_inscription_halls(seed)
    room = dungeon.rooms[0]
    keys = ([Keystroke('G'), Keystroke('4'), Keystroke('l'), Keystroke('a')]
            + [Keystroke(ch) for ch in 'zzzz'] + [ESC])
    _drive(dungeon, keys, monkeypatch)
    for (r, c) in _IH_SEALS:
        assert room.cells[r][c] == CellType.WALL
    assert _IH_FORD_WORD not in main._ih_floor_text(room, _IH_FORD_ROW)


@pytest.mark.parametrize("seed", SEEDS)
def test_undo_rebars_the_wall(seed, monkeypatch):
    """One insert session is one snapshot: u past the movement entry unwrites
    the word and the tick re-bars its wall."""
    dungeon = build_dungeon_inscription_halls(seed)
    room = dungeon.rooms[0]
    toks = room.answer.split()
    lesson_a = ' '.join(toks[:2])                     # '( i{..}'
    _drive(dungeon, _keys(lesson_a, extra='l'), monkeypatch)
    word, (br, bc) = room._ih_bolts[1]                # lesson A's wall
    assert room.cells[br][bc] == CellType.FLOOR, "written whole — wall open"

    dungeon = build_dungeon_inscription_halls(seed)
    room = dungeon.rooms[0]
    # u pops the 'l' movement first; the SECOND u pops the whole insert
    # session (one snapshot at entry) and unwrites the word.
    _drive(dungeon, _keys(lesson_a, extra='luul'), monkeypatch)
    word, (br, bc) = room._ih_bolts[1]
    assert room.cells[br][bc] == CellType.WALL, "undone — the wall re-bars"


def test_esc_steps_back_onto_written_ground(monkeypatch):
    """After an `a` at the bank the cursor hovers on the flood; Esc retreats
    one column (Vim-faithful) onto the just-written letter."""
    dungeon = build_dungeon_inscription_halls(SEEDS[0])
    room = dungeon.rooms[0]
    toks = room.answer.split()
    upto_b = ' '.join(toks[:5])
    _drive(dungeon, _keys(upto_b), monkeypatch)
    r, k = _IH_LESSON_ROWS[1], _IH_SPLITS[1]
    assert room.cells[r][_ih_bank(r) + k] in _FLOORS


def test_curriculum_guard():
    """The level teaches the 'insert' token; everything else the par route
    leans on is already known — including the sentence jumps."""
    known = set(known_commands('inscription_halls'))
    assert 'insert' in known
    for needed in ('count', '(', 'G', '/'):
        assert needed in known


def test_hint_bar_surfaces_append():
    # 'insert' gates both i and a (and o/O/I/A); without family expansion only i shows
    # and append is gated-in-but-invisible.
    from render.hint_bar import hint_text
    bar = hint_text(known_commands('inscription_halls'), 'inscription_halls')
    assert 'i:insert' in bar and 'a:append' in bar
