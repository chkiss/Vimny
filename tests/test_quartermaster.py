"""The Quartermaster (L20): dungeon correctness tests.

Teaching goal: y (yank — copy WITHOUT cutting) and P (paste before the cursor),
with yy + paste raising whole rows. Every cold brazier shows … dying embers
(kind='pedestal', tick-managed); feed each one a flame.

Forcing: pasting is structural (nothing else can put a flame on a brazier —
the glyph is untypable, so r/insert can never forge one). P specifically is
structural at the beacon: three ADJACENT braziers flush against the west wall,
so standing on the first, 3P fills all three while 3p (paste AFTER) leaves the
leftmost cold — and no cell exists to its west to p from. The chain bolts are
cumulative (bolt k needs braziers 0..k), so cut-and-carry routes must paste
the source back — copy-don't-cut made visible. yy for the tiers ties with
dd + 3P in cost (both Vim-real); the answer teaches yy.

Teleport audit: G/{n}G/H/M/L (long known) land on a row's FIRST non-blank, so
the seal and the exit share the LAST row with the exit at its far END — every
jump lands west of the seal and queues at the door (this replaced a shipped
layout where bare G landed beside the exit).

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
    _QM_BOLT_COLS, _QM_BRAZIER_ROW, _QM_BRAZIER_COLS, _QM_EXIT_ROW,
    _QM_SEAL_COL, _QM_EXIT, _QM_FLAME, _QM_EMBERS, _QM_PAR,
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


def _light(room, r, c, count=1, before=True):
    """Paste the flame onto (r, c) the way P does (cursor on the cell)."""
    p = Player(row=r, col=c)
    op.op_paste(room, p, _flame_clip(), before=before, count=count)
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
    assert room.cells[_QM_HALL_ROW][_QM_BOLT_COLS[1]] == CellType.WALL
    assert room.cells[_QM_EXIT_ROW][_QM_SEAL_COL] == CellType.WALL


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


@pytest.mark.parametrize("seed", SEEDS)
def test_3P_fills_the_beacon_and_3p_leaves_the_left_cold(seed):
    """The forced-P design, pinned through the real paste op: the braziers are
    ADJACENT and flush against the west wall. Standing on the first, 3P fills
    all three; 3p (paste AFTER the cursor) misses the leftmost — and no cell
    exists to its west to p from."""
    r, c0 = _QM_BRAZIER_ROW, _QM_BRAZIER_COLS[0]
    assert _QM_BRAZIER_COLS == (c0, c0 + 1, c0 + 2), "braziers must be adjacent"

    room = build_dungeon_quartermaster(SEEDS[0]).rooms[0]    # private (mutating)
    assert room.is_passable(r, c0) and not room.is_passable(r, c0 - 1)
    _light(room, r, c0, count=3, before=True)                # 3P
    assert all(_glyph(room, r, c) == _QM_FLAME for c in _QM_BRAZIER_COLS)

    room = build_dungeon_quartermaster(SEEDS[0]).rooms[0]    # fresh — now 3p
    _light(room, r, c0, count=3, before=False)
    assert _glyph(room, r, c0) != _QM_FLAME, "3p must leave the leftmost cold"
    assert all(_glyph(room, r, c) == _QM_FLAME for c in (c0 + 1, c0 + 2))


def test_flame_and_embers_are_untypable():
    """r{char} types keyboard characters: neither the flame nor the embers can
    ever be forged — pasting the register is structurally the only writer."""
    assert not _QM_FLAME.isascii() and not _QM_EMBERS.isascii()


# ── teleport audit (G / {n}G / H / M / L / gg) ────────────────────────────────

@pytest.mark.parametrize("seed", SEEDS)
def test_line_jumps_never_land_past_the_seal(seed):
    """Line jumps land on a row's first non-blank — by design always WEST of
    the seal, never on the exit. Regression: a previous layout put the exit in
    a row-below alcove and bare G landed beside it."""
    room = build_dungeon_quartermaster(seed).rooms[0]        # private (mutating)
    jumps = ([('G', 1, False), ('gg', 1, False), ('H', 1, False),
              ('M', 1, False), ('L', 1, False)]
             + [('G', n, True) for n in range(1, _QM_ROWS)])
    for motion, count, count_given in jumps:
        p = Player(row=room.spawn_pos[0], col=room.spawn_pos[1])
        apply_motion(p, motion, count, room, count_given=count_given)
        assert (p.row, p.col) != _QM_EXIT, f"{count if count_given else ''}{motion}"
        if p.row == _QM_EXIT_ROW:
            assert p.col < _QM_SEAL_COL, (
                f"{count if count_given else ''}{motion} landed east of the seal")


# ── par / answer ──────────────────────────────────────────────────────────────

@pytest.mark.parametrize("seed", SEEDS)
def test_par_is_locked_and_answer_uses_the_lesson(seed):
    """par is seed-invariant (fixed geometry); the par path yanks the flame
    (y l), pastes before twice (the hall brazier + the count-paste 3P), and
    raises the beacon with y y + two pastes. (Answer cost == par and the
    budget formula: covered by the universal tests.)"""
    room = _room(seed)
    assert room.par == _QM_PAR
    toks = room.answer.split()
    assert '3P' in toks, "the beacon fill is ONE count-paste"
    assert toks.count('P') == 1 and toks.count('p') == 2
    assert toks.count('y') == 3, "one yl + one yy on the par path"


def test_walking_route_fits_the_budget():
    """The par path rides 4G to the beacon row; the mortal walking route
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
        assert absent not in known, f"{absent!r} learned at or before the Quartermaster"


# ── reachability (with the gates modeled open) ────────────────────────────────

@pytest.mark.parametrize("seed", SEEDS)
def test_exit_reachable_once_gates_open(seed):
    room = build_dungeon_quartermaster(seed).rooms[0]        # private (mutating)
    for bc in _QM_BOLT_COLS:
        room.cells[_QM_HALL_ROW][bc] = CellType.FLOOR
    room.cells[_QM_EXIT_ROW][_QM_SEAL_COL] = CellType.FLOOR
    seen, q = {room.spawn_pos}, deque([room.spawn_pos])
    while q:
        r, c = q.popleft()
        for dr, dc in ((0, 1), (0, -1), (1, 0), (-1, 0)):
            nb = (r + dr, c + dc)
            if nb not in seen and room.is_passable(*nb):
                seen.add(nb)
                q.append(nb)
    assert room.exit_pos in seen
    assert (_QM_BRAZIER_ROW, _QM_BRAZIER_COLS[0]) in seen


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
    depot chain burns — checked through REAL row inserts, so the seal (same
    row as the exit) must ride the shift. A teleport into the shrine that
    skipped the hall brazier leaves the seal shut."""
    from engine.reflow import _insert_blank_row
    from engine.world import CharRun
    room = build_dungeon_quartermaster(seed).rooms[0]        # private (mutating)
    p = Player(row=_QM_BRAZIER_ROW, col=_QM_BRAZIER_COLS[0])

    _light(room, _QM_BRAZIER_ROW, _QM_BRAZIER_COLS[0], count=3)   # 3P
    msgs = main._quartermaster_tick(room, p)
    assert any('one tier alone' in m for m in msgs), "the one-shot yy nudge"
    for k in (1, 2):                                         # the two linewise pastes
        _insert_blank_row(room, _QM_BRAZIER_ROW + k, _QM_BRAZIER_ROW, p)
        for c in _QM_BRAZIER_COLS:
            room.add_char_run(CharRun(_QM_BRAZIER_ROW + k, c, (_QM_FLAME,), 'flame'))
    main._quartermaster_tick(room, p)
    exit_e = next(e for e in room.entities if e.kind == 'exit')
    assert exit_e.row == _QM_EXIT[0] + 2, "the exit rides the inserted rows"
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


# ── full answer playthrough through the real keystroke loop ───────────────────

@pytest.mark.parametrize("seed", SEEDS)
def test_answer_playthrough_wins_at_par(seed, monkeypatch):
    """Type the answer key-for-key through run_dungeon as a normal player:
    yank, paste, 4G, the count-paste 3P, the beacon raise — and the run ends
    par-perfect (2 stars)."""
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
