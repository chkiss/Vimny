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

"""The Beacon Tiers (slug `quartermaster`): dungeon correctness tests.

Teaching goal: y (yank — copy WITHOUT cutting) and P (paste before the cursor),
with yy + paste raising whole rows. Every cold brazier shows … dying embers
(kind='pedestal', tick-managed); feed each one a flame.

Forcing: pasting is structural, and doubly so under the FUEL RULE (a deliberate
Vim exception): a charwise paste may lay a flame only onto a brazier — anywhere
else "there is no fuel to hold that flame" (free no-op). Linewise paste is
exempt (a yanked row's flames already sit in their braziers) — which is exactly
why nine flames along one row can never stand in for three tiers. P is
structural at the beacon: three ADJACENT braziers flush against the seal wall;
3P fills all three, while 3p's third flame would overrun the fuel (blocked) —
and at engine level (Vim baseline) 3p starts one cell late, leaving the
leftmost cold. The chain bolts are cumulative (bolt k needs braziers 0..k), so
cut-and-carry routes must paste the source back — copy-don't-cut made visible.

The exit sits in a one-cell POCKET behind the seal, WEST of the braziers —
unreachable by walking from any direction but through the drawn seal
(regression: a previous layout let the player walk down past the seal's east
side), and unreachable by line jumps (G/{n}G/H/M/L land on a row's first
non-blank = always a brazier's dots/flame; the exit is CARET_TRANSPARENT).

All doors run through main._quartermaster_tick — stateless and undo-safe
(the vault-tick principle), anchored on stored build coordinates (the Cipher
Cell convention; a self-inflicted dd/linewise shift desyncs until u).
"""
from collections import deque

from blessed.keyboard import Keystroke
from blessed import Terminal

import main
import engine.operator as op
from engine.motion import apply_motion
from engine.player import Player
from engine.world import CellType
from content.levels import known_commands
from generation.dungeon_gen import (
    build_dungeon_quartermaster,
    _QM_ROWS, _QM_COLS, _QM_HALL_ROW, _QM_SPAWN, _QM_SOURCE, _QM_PED1,
    _QM_BOLT_COLS, _QM_BRAZIER_ROW, _QM_BRAZIER_COLS,
    _QM_SEAL_COL, _QM_EXIT, _QM_FLAME, _QM_EMBERS, _QM_PAR,
)
import pytest

from tests import SEEDS, cached_room


def _room(seed):
    """Shared READ-ONLY build; mutating tests call the builder directly."""
    return cached_room('build_dungeon_quartermaster', seed)


def _flame_clip(width=1):
    """A charwise clip holding the flame — what yl leaves in the register.
    width > 1 emulates yw's flame-plus-trailing-blanks clip."""
    return {'linewise': False, 'rows': [{'width': width, 'char_runs': [
        {'dcol': 0, 'symbols': (_QM_FLAME,), 'kind': 'flame'}]}]}


def _glyph(room, r, c):
    ru = room.char_run_at(r, c)
    return ru.symbols[c - ru.col] if ru else None


def _light(room, r, c, count=1, before=True):
    """Paste the flame onto (r, c) the way P does (cursor on the cell)."""
    p = Player(row=r, col=c)
    op.op_paste(room, p, _flame_clip(), before=before, count=count)
    return p


def _bfs(room):
    seen, q = {room.spawn_pos}, deque([room.spawn_pos])
    while q:
        r, c = q.popleft()
        for dr, dc in ((0, 1), (0, -1), (1, 0), (-1, 0)):
            nb = (r + dr, c + dc)
            if nb not in seen and room.is_passable(*nb):
                seen.add(nb)
                q.append(nb)
    return seen


# ── structure ─────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("seed", SEEDS)
def test_dimensions_and_anchors(seed):
    room = _room(seed)
    assert (room.rows, room.cols) == (_QM_ROWS, _QM_COLS)
    assert room.spawn_pos == _QM_SPAWN and room.exit_pos == _QM_EXIT
    exits = [e for e in room.entities if e.kind == 'exit']
    assert len(exits) == 1 and (exits[0].row, exits[0].col) == _QM_EXIT
    assert exits[0].edit_immune, "the beacon row must refuse dd-collapse"
    # Build state == tick steady-state: the chain holds only the source flame.
    assert room.cells[_QM_HALL_ROW][_QM_BOLT_COLS[0]] == CellType.FLOOR
    assert room.cells[_QM_HALL_ROW][_QM_BOLT_COLS[1]] == CellType.WALL
    assert room.cells[_QM_EXIT[0]][_QM_SEAL_COL] == CellType.WALL


@pytest.mark.parametrize("seed", SEEDS)
def test_initial_flames_and_embers(seed):
    """One lit brazier; every cold brazier shows … embers; nothing else."""
    room = _room(seed)
    assert _glyph(room, *_QM_SOURCE) == _QM_FLAME
    cold = [_QM_PED1] + [(_QM_BRAZIER_ROW, c) for c in _QM_BRAZIER_COLS]
    for (r, c) in cold:
        ru = room.char_run_at(r, c)
        assert ru is not None and ru.kind == 'pedestal'
        assert ru.symbols == (_QM_EMBERS,)
    flames = [ru for ru in room.char_runs if ru.kind == 'flame']
    assert len(flames) == 1, "the source is the only flame in the depot"


# ── the exit pocket: sealed against walking AND jumping ───────────────────────

@pytest.mark.parametrize("seed", SEEDS)
def test_exit_unreachable_until_the_seal_draws(seed):
    """With the doors AS BUILT the exit pocket is not reachable by walking at
    all — regression for the shipped layout where the player could descend
    past the seal's east side straight onto the exit row."""
    room = build_dungeon_quartermaster(seed).rooms[0]        # private (mutating)
    assert room.exit_pos not in _bfs(room)

    room.cells[_QM_EXIT[0]][_QM_SEAL_COL] = CellType.FLOOR   # the seal draws open
    for bc in _QM_BOLT_COLS:
        room.cells[_QM_HALL_ROW][bc] = CellType.FLOOR
    from engine.motion import auto_fog_tick
    auto_fog_tick(room, *room.spawn_pos)     # sight crosses the opened doors
    seen = _bfs(room)
    assert room.exit_pos in seen
    assert (_QM_BRAZIER_ROW, _QM_BRAZIER_COLS[0]) in seen


@pytest.mark.parametrize("seed", SEEDS)
def test_line_jumps_never_land_in_the_pocket(seed):
    """Line jumps land on a row's first non-blank — on the beacon row that is
    always a brazier's dots/flame (tick-maintained), never the pocket: the
    exit entity is CARET_TRANSPARENT and the seal wall stands between."""
    room = build_dungeon_quartermaster(seed).rooms[0]        # private (mutating)
    jumps = ([('G', 1, False), ('gg', 1, False), ('H', 1, False),
              ('M', 1, False), ('L', 1, False)]
             + [('G', n, True) for n in range(1, _QM_ROWS)])
    for motion, count, count_given in jumps:
        p = Player(row=room.spawn_pos[0], col=room.spawn_pos[1])
        apply_motion(p, motion, count, room, count_given=count_given)
        assert (p.row, p.col) != _QM_EXIT, f"{count if count_given else ''}{motion}"
        if p.row == _QM_EXIT[0]:
            assert p.col > _QM_SEAL_COL, (
                f"{count if count_given else ''}{motion} landed at/behind the seal")


# ── the fuel rule: flames lie only in braziers ────────────────────────────────

def test_fuel_rule_blocks_flames_off_brazier():
    """Charwise flame pastes land only on braziers; the rest is 'no fuel'.
    Covers the cheese battery: yw/ye-style clips on bare floor, count-pastes
    overrunning the braziers — and the legit fills stay legal."""
    room = _room(SEEDS[0])
    blocked = main._flame_paste_blocked

    hall_floor = Player(row=_QM_HALL_ROW, col=6)
    assert blocked(room, hall_floor, _flame_clip(), True, 1)
    assert blocked(room, hall_floor, _flame_clip(width=3), True, 1)   # yw clip
    on_ped1 = Player(row=_QM_PED1[0], col=_QM_PED1[1])
    assert not blocked(room, on_ped1, _flame_clip(), True, 1)         # legit P
    assert blocked(room, on_ped1, _flame_clip(), False, 1)            # p lands at 15
    b0 = Player(row=_QM_BRAZIER_ROW, col=_QM_BRAZIER_COLS[0])
    assert not blocked(room, b0, _flame_clip(), True, 3)              # 3P fills
    assert blocked(room, b0, _flame_clip(), False, 3), \
        "3p's third flame overruns the fuel — blocked outright"
    assert blocked(room, b0, _flame_clip(), True, 9)                  # nine in a row
    assert not blocked(room, b0, {'linewise': True, 'rows': [{}]}, True, 9), \
        "linewise paste is exempt — its flames are already held by braziers"
    no_flame = {'linewise': False, 'rows': [{'width': 2, 'char_runs': [
        {'dcol': 0, 'symbols': ('a', 'b'), 'kind': 'ancient'}]}]}
    assert not blocked(room, hall_floor, no_flame, True, 1), \
        "the rule governs flames only"


@pytest.mark.parametrize("keys,label", [
    ('wywllllP', 'yw then P on hall floor'),
    ('wyelllp',  'ye then p on hall floor'),
    ('^y0$P',    '^ y0 $ P — y0 is exclusive: the clip is blanks, never the flame'),
    ('wylw PG9P'.replace(' ', ''), 'nine flames in a row at the beacon'),
])
def test_cheese_battery_spreads_no_flame(keys, label, monkeypatch):
    """The known cheese attempts, key-for-key through run_dungeon:
    none of them may put a flame anywhere beyond the source/legit braziers."""
    dungeon = build_dungeon_quartermaster(SEEDS[0])
    ks = [Keystroke(ch) for ch in keys]
    ks += [Keystroke(':'), Keystroke('q'), Keystroke('!'), Keystroke('\r')]
    monkeypatch.setattr(main, 'render_all', lambda *a, **k: None)
    monkeypatch.setattr(main.time, 'sleep', lambda *a, **k: None)
    term = Terminal()
    it = iter(ks)
    monkeypatch.setattr(term, 'inkey', lambda *a, **k: next(it, Keystroke('')))
    main.run_dungeon(term, 'quartermaster', {}, player_name='Cheese',
                     _dungeon=dungeon)
    room = dungeon.rooms[0]
    legit = {_QM_SOURCE, _QM_PED1} | {(_QM_BRAZIER_ROW, c) for c in _QM_BRAZIER_COLS}
    flames = {(ru.row, ru.col) for ru in room.char_runs if _QM_FLAME in ru.symbols}
    assert flames <= legit, f"{label}: flame escaped to {sorted(flames - legit)}"


def test_engine_3p_starts_one_cell_late():
    """The Vim baseline under the game rule: at ENGINE level 3p pastes after
    the cursor, so from the first brazier the leftmost stays cold (the fuel
    rule then blocks it in normal play because the third flame overruns)."""
    r, c0 = _QM_BRAZIER_ROW, _QM_BRAZIER_COLS[0]
    assert _QM_BRAZIER_COLS == (c0, c0 + 1, c0 + 2), "braziers must be adjacent"
    room = build_dungeon_quartermaster(SEEDS[0]).rooms[0]    # private (mutating)
    room.fog_cells.clear()                   # engine baseline — not a fog test
    assert room.is_passable(r, c0) and not room.is_passable(r, c0 - 1)
    _light(room, r, c0, count=3, before=False)               # 3p
    assert _glyph(room, r, c0) != _QM_FLAME
    room = build_dungeon_quartermaster(SEEDS[0]).rooms[0]    # fresh — 3P
    room.fog_cells.clear()
    _light(room, r, c0, count=3, before=True)
    assert all(_glyph(room, r, c) == _QM_FLAME for c in _QM_BRAZIER_COLS)


def test_flame_and_embers_are_untypable():
    """r{char} types keyboard characters: neither the flame nor the embers can
    ever be forged — pasting the register is structurally the only writer."""
    assert not _QM_FLAME.isascii() and not _QM_EMBERS.isascii()


# ── par / answer ──────────────────────────────────────────────────────────────

@pytest.mark.parametrize("seed", SEEDS)
def test_par_is_locked_and_answer_uses_the_lesson(seed):
    """par is seed-invariant (fixed geometry); the par path yanks the flame
    (y l), pastes before twice (the hall brazier + the count-paste 3P), and
    raises the beacon with y y + p P (below then above — the P leaves the
    cursor one row under the seal row, saving the second k of the old p p
    route; player-found golf 2026-07-18). (Answer cost == par and the
    budget formula: covered by the universal tests.)"""
    room = _room(seed)
    assert room.par == _QM_PAR
    toks = room.answer.split()
    assert '3P' in toks, "the beacon fill is ONE count-paste"
    assert toks.count('P') == 2 and toks.count('p') == 1
    assert toks.count('y') == 3, "one yl + one yy on the par path"


def test_walking_route_fits_the_budget():
    """The par path rides G to the beacon row; the mortal walking route
    ($ down the shaft, B to the braziers) costs par+2 and must still fit."""
    room = _room(SEEDS[0])
    assert room.par + 2 <= room.budget


def test_curriculum_guard():
    """Forcing assumptions: paste is the only flame-writer at L20 (no insert,
    no substitutes), and named registers stay deferred to The Hall of Echoes —
    if 'register'/'reg_named' ever lands at or before here, re-audit the level."""
    known = set(known_commands('quartermaster'))
    for needed in ('y', 'P', 'p', 'd', 'D', 'r', 'count', '$', 'G'):
        assert needed in known
    for absent in ('insert', 's', 'c', 'R', 'register', 'reg_named'):
        assert absent not in known, f"{absent!r} learned at or before the Beacon Tiers"


# ── the tick: stateless, undo-safe ────────────────────────────────────────────

@pytest.mark.parametrize("seed", SEEDS)
def test_tick_chain_bolts_follow_the_flames_both_ways(seed):
    room = build_dungeon_quartermaster(seed).rooms[0]        # private (mutating)
    p = Player(row=_QM_HALL_ROW, col=2)
    A, B = _QM_BOLT_COLS

    main._quartermaster_tick(room, p)
    assert room.cells[_QM_HALL_ROW][B] == CellType.WALL      # hall brazier still cold

    _light(room, *_QM_PED1)                                  # the P at the hall brazier
    msgs = main._quartermaster_tick(room, p)
    assert room.cells[_QM_HALL_ROW][B] == CellType.FLOOR
    assert any('bolt' in m for m in msgs)

    src = room.char_run_at(*_QM_SOURCE)                      # cut the source —
    room.remove_char_run(src)                                # the chain darkens
    msgs = main._quartermaster_tick(room, p)
    for bc in (A, B):
        assert room.cells[_QM_HALL_ROW][bc] == CellType.WALL
    assert any('chain' in m for m in msgs)
    laid = room.char_run_at(*_QM_SOURCE)                     # …and embers appear
    assert laid is not None and laid.kind == 'pedestal'

    room.remove_char_run(laid)                               # undo restores the flame
    room.add_char_run(src)                                   # (snapshot replaces the row)
    main._quartermaster_tick(room, p)
    for bc in (A, B):
        assert room.cells[_QM_HALL_ROW][bc] == CellType.FLOOR


@pytest.mark.parametrize("seed", SEEDS)
def test_tick_manages_the_ember_markers(seed):
    """Embers are fixtures: deleted dots are relaid; dots shoved aside by a
    paste's open_gap are swept the same turn (and the pasted flame must NOT
    repaint them — the pinned-kind rule in normalize_row_word_kinds)."""
    room = build_dungeon_quartermaster(seed).rooms[0]        # private (mutating)
    p = Player(row=_QM_HALL_ROW, col=2)

    room.remove_char_run(room.char_run_at(*_QM_PED1))        # a careless D
    main._quartermaster_tick(room, p)
    ru = room.char_run_at(*_QM_PED1)
    assert ru is not None and ru.kind == 'pedestal'          # relaid

    _light(room, *_QM_PED1)                                  # open_gap shoves the dots
    r, c = _QM_PED1
    shoved = room.char_run_at(r, c + 1)
    assert shoved is not None and shoved.kind == 'pedestal'  # kind survived the merge
    main._quartermaster_tick(room, p)
    assert _glyph(room, r, c) == _QM_FLAME                   # lit
    assert room.char_run_at(r, c + 1) is None                # stray swept


@pytest.mark.parametrize("seed", SEEDS)
def test_seal_needs_three_tiers_and_the_whole_chain(seed):
    """The seal draws open only while the beacon burns in three tiers AND the
    depot chain burns — checked through REAL row inserts. A jump into the
    beacon row that skipped the hall brazier leaves the seal shut."""
    from engine.reflow import _insert_blank_row
    from engine.world import CharRun
    room = build_dungeon_quartermaster(seed).rooms[0]        # private (mutating)
    p = Player(row=_QM_BRAZIER_ROW, col=_QM_BRAZIER_COLS[0])

    _light(room, _QM_BRAZIER_ROW, _QM_BRAZIER_COLS[0], count=3)   # 3P
    msgs = main._quartermaster_tick(room, p)
    assert any('no more braziers' in m for m in msgs), \
        "the one-shot too-cold nudge fires when one tier stands alone (no command named)"
    assert not any('yy' in m for m in msgs), "the nudge must not name the command"
    for k in (1, 2):                                         # the two linewise pastes
        _insert_blank_row(room, _QM_BRAZIER_ROW + k, _QM_BRAZIER_ROW, p)
        for c in _QM_BRAZIER_COLS:
            room.add_char_run(CharRun(_QM_BRAZIER_ROW + k, c, (_QM_FLAME,), 'flame'))
    main._quartermaster_tick(room, p)
    exit_e = next(e for e in room.entities if e.kind == 'exit')
    assert exit_e.row == _QM_EXIT[0], "p-pastes insert BELOW — the exit holds its row"
    seal = (exit_e.row, _QM_SEAL_COL)
    assert room.cells[seal[0]][seal[1]] == CellType.WALL, (
        "three tiers alone must NOT draw the seal — the hall brazier is cold")

    _light(room, *_QM_PED1)                                  # complete the chain
    msgs = main._quartermaster_tick(room, p)
    assert room.cells[seal[0]][seal[1]] == CellType.FLOOR
    assert any('three tiers' in m for m in msgs)

    snuffed = room.char_run_at(_QM_BRAZIER_ROW + 2, _QM_BRAZIER_COLS[0])
    room.remove_char_run(snuffed)                            # undo snuffs a tier
    main._quartermaster_tick(room, p)
    assert room.cells[seal[0]][seal[1]] == CellType.WALL     # the seal re-bars


# Full answer playthrough (canonical tape → run_dungeon → 2-star win) is covered
# for every seed by the universal test_answer_paths.py::test_answer_path_actually_wins.
# (test_cheese_battery_spreads_no_flame above still drives run_dungeon for the
# known cheese routes — that negative forcing is NOT covered universally.)


def test_hint_bar_surfaces_the_linewise_yy():
    # Learning 'y' unlocks the linewise yy as well as y{m}; the bar bundles yy into the
    # y keys cell (like c{m}  cc) so yank-line is never gated-in-but-invisible.
    from render.hint_bar import hint_text
    bar = hint_text(known_commands('quartermaster'), 'quartermaster')
    assert 'y{m}' in bar and 'yy' in bar
    assert 'P' in bar
