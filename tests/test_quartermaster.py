"""The Quartermaster (L20): dungeon correctness tests.

Teaching goal: y (yank — copy WITHOUT cutting) and P (paste before the cursor),
with yy + paste raising whole rows. ONE rule, inherited from the Cipher Cell:
a lock cell BURNS while it matches the flame plaque sealed in the wall above
it; unlit locks show … embers (kind='pedestal', tick-managed).

Forcing: pasting is structural (nothing else can put a flame on a pedestal —
the glyph is untypable, so r/insert can never forge one). P specifically is
structural at the stub pedestal: it sits on the LEFTMOST floor cell of its
row, so no cell ever exists to its left to p from. The chain bolts are
cumulative (bolt k needs flames 0..k), so cut-and-carry routes must paste the
source back — copy-don't-cut made visible. yy for the tier seal is SOFT
(dd + 3 pastes costs par+1, within budget but losing the 2-star).

All doors run through main._quartermaster_tick — stateless and undo-safe
(the vault-tick principle), every anchor re-derived from the plaque glyphs
each turn so linewise pastes can't desync the locks.
"""
from collections import deque

from blessed.keyboard import Keystroke
from blessed import Terminal

import main
import engine.operator as op
from engine.player import Player
from engine.world import CellType, CharRun
from content.levels import known_commands
from generation.dungeon_gen import (
    build_dungeon_quartermaster,
    _QM_ROWS, _QM_COLS, _QM_PLAQUE_ROW, _QM_HALL_ROW, _QM_SPAWN,
    _QM_SOURCE, _QM_PED1, _QM_PED2, _QM_BOLT_COLS,
    _QM_MURAL_ROWS, _QM_BRAZIER_ROW, _QM_TIER_COLS, _QM_SLOT_COL,
    _QM_SEAL, _QM_EXIT, _QM_FLAME, _QM_EMBERS, _QM_PAR,
)
import pytest

from tests import SEEDS, cached_room


def _room(seed):
    """Shared READ-ONLY build; mutating tests call the builder directly."""
    return cached_room('build_dungeon_quartermaster', seed)


def _flame_clip():
    """A charwise clip holding the flame — what yl leaves in the register."""
    return {'linewise': False, 'rows': [{'width': 1, 'char_runs': [
        {'dcol': 0, 'symbols': (_QM_FLAME,), 'kind': 'flame'}]}]}


def _glyph(room, r, c):
    ru = room.char_run_at(r, c)
    return ru.symbols[c - ru.col] if ru else None


def _light(room, r, c):
    """Paste the flame onto (r, c) the way P does (cursor on the cell)."""
    p = Player(row=r, col=c)
    op.op_paste(room, p, _flame_clip(), before=True)
    return p


# ── structure ─────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("seed", SEEDS)
def test_dimensions_and_anchors(seed):
    room = _room(seed)
    assert (room.rows, room.cols) == (_QM_ROWS, _QM_COLS)
    assert room.spawn_pos == _QM_SPAWN and room.exit_pos == _QM_EXIT
    exits = [e for e in room.entities if e.kind == 'exit']
    assert len(exits) == 1 and (exits[0].row, exits[0].col) == _QM_EXIT
    assert exits[0].edit_immune, "the exit row must refuse dd-collapse"
    # Build state == tick steady-state: the chain holds only the source flame.
    assert room.cells[_QM_HALL_ROW][_QM_BOLT_COLS[0]] == CellType.FLOOR
    for bc in _QM_BOLT_COLS[1:]:
        assert room.cells[_QM_HALL_ROW][bc] == CellType.WALL
    assert room.cells[_QM_SEAL[0]][_QM_SEAL[1]] == CellType.WALL


@pytest.mark.parametrize("seed", SEEDS)
def test_plaques_are_sealed_in_wall(seed):
    """Every plaque flame sits embedded in a WALL cell (cursor can never reach
    it, so no yank can harvest a plaque), and each has its lock cell — passable
    floor — directly beneath, except the upper mural rows (pure mural)."""
    room = _room(seed)
    plaques = [(ru.row, ru.col) for ru in room.char_runs
               if ru.kind == 'flame' and not room.is_passable(ru.row, ru.col)]
    assert (_QM_PLAQUE_ROW, _QM_SOURCE[1]) in plaques
    assert (_QM_PLAQUE_ROW, _QM_PED1[1]) in plaques
    assert (_QM_PED2[0] - 1, _QM_PED2[1]) in plaques
    for r in _QM_MURAL_ROWS:
        for c in _QM_TIER_COLS:
            assert (r, c) in plaques
    locks = [(r + 1, c) for r, c in plaques if room.is_passable(r + 1, c)]
    assert sorted(locks) == sorted(
        [_QM_SOURCE, _QM_PED1, _QM_PED2]
        + [(_QM_BRAZIER_ROW, c) for c in _QM_TIER_COLS])


@pytest.mark.parametrize("seed", SEEDS)
def test_initial_flames_and_embers(seed):
    """One lit hall brazier; cold pedestals show … embers; the shrine row is
    one flame short of its mural."""
    room = _room(seed)
    assert _glyph(room, *_QM_SOURCE) == _QM_FLAME
    for (r, c) in (_QM_PED1, _QM_PED2, (_QM_BRAZIER_ROW, _QM_SLOT_COL)):
        ru = room.char_run_at(r, c)
        assert ru is not None and ru.kind == 'pedestal'
        assert ru.symbols == (_QM_EMBERS,)
    for c in _QM_TIER_COLS:
        if c != _QM_SLOT_COL:
            assert _glyph(room, _QM_BRAZIER_ROW, c) == _QM_FLAME


@pytest.mark.parametrize("seed", SEEDS)
def test_P_is_structurally_forced_at_the_stub(seed):
    """The stub pedestal is the LEFTMOST floor cell of its row: the cell to its
    left is wall forever, so p (paste after) can never reach it — only P."""
    room = _room(seed)
    r, c = _QM_PED2
    assert room.is_passable(r, c)
    assert not room.is_passable(r, c - 1)
    assert all(not room.is_passable(r, cc) for cc in range(0, c))


def test_flame_and_embers_are_untypable():
    """r{char} types keyboard characters: neither the flame nor the embers can
    ever be forged — pasting the register is structurally the only writer."""
    assert not _QM_FLAME.isascii() and not _QM_EMBERS.isascii()


# ── par / answer ──────────────────────────────────────────────────────────────

@pytest.mark.parametrize("seed", SEEDS)
def test_par_is_locked_and_answer_uses_the_lesson(seed):
    """par is seed-invariant (fixed geometry); the par path yanks once (y l),
    pastes before three times (the two structural P cells + the hall pedestal),
    and raises the beacon with y y + two pastes. (Answer cost == par and the
    budget formula: covered by the universal tests.)"""
    room = _room(seed)
    assert room.par == _QM_PAR
    toks = room.answer.split()
    assert toks.count('P') == 3
    assert toks.count('p') == 2
    assert toks.count('y') == 3, "one yl + one yy on the par path"
    assert 'l' in toks


def test_soft_yy_forcing_margin():
    """The dd + 3-paste tier route (cut the brazier row, paste it back thrice)
    costs par+1 — within budget, losing the 2-star only. yy's forcing is
    deliberately SOFT (lineheads precedent for whole-line lessons)."""
    room = _room(SEEDS[0])
    assert room.par + 1 <= room.budget


def test_curriculum_guard():
    """Forcing assumptions: paste is the only flame-writer at L20 (no insert,
    no substitutes), and named registers stay deferred to The Hall of Echoes —
    if 'register'/'reg_named' ever lands at or before here, re-audit the level."""
    known = set(known_commands('quartermaster'))
    for needed in ('y', 'P', 'p', 'd', 'D', 'r', 'count', '$'):
        assert needed in known
    for absent in ('insert', 's', 'c', 'R', 'register', 'reg_named'):
        assert absent not in known, f"{absent!r} learned at or before the Quartermaster"


# ── reachability (with the gates modeled open) ────────────────────────────────

@pytest.mark.parametrize("seed", SEEDS)
def test_exit_reachable_once_gates_open(seed):
    room = build_dungeon_quartermaster(seed).rooms[0]        # private (mutating)
    for bc in _QM_BOLT_COLS:
        room.cells[_QM_HALL_ROW][bc] = CellType.FLOOR
    room.cells[_QM_SEAL[0]][_QM_SEAL[1]] = CellType.FLOOR
    seen, q = {room.spawn_pos}, deque([room.spawn_pos])
    while q:
        r, c = q.popleft()
        for dr, dc in ((0, 1), (0, -1), (1, 0), (-1, 0)):
            nb = (r + dr, c + dc)
            if nb not in seen and room.is_passable(*nb):
                seen.add(nb)
                q.append(nb)
    assert room.exit_pos in seen
    assert _QM_PED2 in seen, "the stub pedestal must be walkable"


# ── the tick: stateless, undo-safe ────────────────────────────────────────────

@pytest.mark.parametrize("seed", SEEDS)
def test_tick_chain_bolts_follow_the_flames_both_ways(seed):
    room = build_dungeon_quartermaster(seed).rooms[0]        # private (mutating)
    p = Player(row=_QM_HALL_ROW, col=2)
    A, B, C = _QM_BOLT_COLS

    main._quartermaster_tick(room, p)
    assert room.cells[_QM_HALL_ROW][B] == CellType.WALL      # ped1 still cold

    _light(room, *_QM_PED1)                                  # the P at the hall pedestal
    msgs = main._quartermaster_tick(room, p)
    assert room.cells[_QM_HALL_ROW][B] == CellType.FLOOR
    assert any('bolt' in m for m in msgs)
    assert room.cells[_QM_HALL_ROW][C] == CellType.WALL      # stub still cold

    _light(room, *_QM_PED2)
    main._quartermaster_tick(room, p)
    assert room.cells[_QM_HALL_ROW][C] == CellType.FLOOR     # chain complete

    src = room.char_run_at(*_QM_SOURCE)                      # cut the source —
    room.remove_char_run(src)                                # the chain darkens
    msgs = main._quartermaster_tick(room, p)
    for bc in _QM_BOLT_COLS:
        assert room.cells[_QM_HALL_ROW][bc] == CellType.WALL
    assert any('chain' in m for m in msgs)
    laid = room.char_run_at(*_QM_SOURCE)                     # …and embers appear
    assert laid is not None and laid.kind == 'pedestal'

    room.remove_char_run(laid)                               # undo restores the flame
    room.add_char_run(src)                                   # (snapshot replaces the row)
    main._quartermaster_tick(room, p)
    for bc in _QM_BOLT_COLS:
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
def test_tier_seal_tracks_three_tiers_and_rides_row_shifts(seed):
    """The seal draws open while the three rows below the mural all burn at
    every mural column — checked through REAL row inserts, so the anchor
    (the cell above the exit entity) must ride the shift."""
    from engine.reflow import _insert_blank_row
    room = build_dungeon_quartermaster(seed).rooms[0]        # private (mutating)
    p = Player(row=_QM_BRAZIER_ROW, col=_QM_SLOT_COL)

    _light(room, _QM_BRAZIER_ROW, _QM_SLOT_COL)              # complete the brazier row
    main._quartermaster_tick(room, p)
    assert room.cells[_QM_SEAL[0]][_QM_SEAL[1]] == CellType.WALL   # one tier ≠ three

    for k in (1, 2):                                         # the two linewise pastes
        _insert_blank_row(room, _QM_BRAZIER_ROW + k, _QM_BRAZIER_ROW, p)
        for c in _QM_TIER_COLS:
            room.add_char_run(CharRun(_QM_BRAZIER_ROW + k, c, (_QM_FLAME,), 'flame'))
    msgs = main._quartermaster_tick(room, p)
    exit_e = next(e for e in room.entities if e.kind == 'exit')
    assert exit_e.row == _QM_EXIT[0] + 2, "the exit rides the inserted rows"
    seal = (exit_e.row - 1, exit_e.col)
    assert room.cells[seal[0]][seal[1]] == CellType.FLOOR
    assert any('three tiers' in m for m in msgs)

    snuffed = room.char_run_at(_QM_BRAZIER_ROW + 2, _QM_TIER_COLS[0])
    room.remove_char_run(snuffed)                            # undo snuffs a tier
    main._quartermaster_tick(room, p)
    assert room.cells[seal[0]][seal[1]] == CellType.WALL     # the seal re-bars


# ── full answer playthrough through the real keystroke loop ───────────────────

@pytest.mark.parametrize("seed", SEEDS)
def test_answer_playthrough_wins_at_par(seed, monkeypatch):
    """Type the answer key-for-key through run_dungeon as a normal player:
    yank, three P's, the beacon raise — and the run ends par-perfect (2 stars)."""
    dungeon = build_dungeon_quartermaster(seed)
    keys = [Keystroke(ch) for ch in dungeon.rooms[0].answer.replace(' ', '')]
    keys += [Keystroke(':'), Keystroke('w'), Keystroke('q'), Keystroke('\r')]

    monkeypatch.setattr(main, 'render_all', lambda *a, **k: None)
    monkeypatch.setattr(main.time, 'sleep', lambda *a, **k: None)
    monkeypatch.setattr(main, '_fireworks_animation', lambda *a, **k: None)
    monkeypatch.setattr(main, '_win_animation', lambda *a, **k: None)
    term = Terminal()
    it = iter(keys)
    monkeypatch.setattr(term, 'inkey', lambda *a, **k: next(it, Keystroke('')))
    result = main.run_dungeon(term, 'quartermaster', {}, player_name='Normand',
                              _dungeon=dungeon)
    assert result['won'] and result['stars'] == 2, result
