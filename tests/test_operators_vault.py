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

"""The Operator's Vault — the first {operator}{motion} level (delete).

Ten snaked corridors, each admitting exactly one cheapest d-variant (dw, db,
de, dB, dE, dF?, dW, d0, d$, dd). Every corridor is held by a `fancy_door`: it
opens for a register whose TEXT reads its password and for nothing else, so the
cut has to land on exactly the right words — a fragment is refused and so is the
password with a filler word swept in behind it. The vault at the bottom opens
when all ten have been spoken (stateless and undo-safe, in
`main._operators_vault_tick`), which is also what stops a player simply riding
the shafts past the lessons: the shafts are open, but nothing down there is.

REDESIGNED 2026-08-02, and the reason is worth keeping. This was a combat
gauntlet — armored guards, packs holding coloured gates — and it could not be
made to teach. A guard punishes only a cut that reaches too LITTLE, because he
survives it; every guard a `dw` kills a `d$` kills too, so nothing in the level
held the ceiling, and `tests/test_operators_vault_corridors.py` found half the
corridors falling to the wrong operator for less than par. The password door is
both bounds in one entity, so the guards had no job left and were removed.

Structure tests + a full executed solve through the real run_dungeon loop
(answer == par, unharmed) + a deep-undo regression. The per-corridor forcing
audit lives in `test_operators_vault_corridors.py`; the passwords' spelling —
which is what makes the motions differ at all — lives in
`test_operators_vault_passwords.py`.
"""
import math

import pytest
from blessed import Terminal
from blessed.keyboard import Keystroke

import vimny.game as main
import vimny.generation.dungeon_gen as dg
from vimny.engine.world import CellType, Entity
from vimny.engine.player import Player
from vimny.engine.reflow import remove_row
from vimny.engine.operator import _cursor_to_line_start
from vimny.engine.command_guard import action_allowed
from vimny.content.levels import known_commands
import vimny.render.colors as C
from tests import SEEDS


def _room(seed=7, defog=False):
    room = dg.build_dungeon_operators_vault(seed).rooms[0]
    if defog:
        # Clear the revealable fog only — the west channel's MIST is
        # permanent in play (reveal floods skip it), so tests keep it too.
        room.fog_cells = set(room.underwater_cells)
    return room


def _gates(room):
    return [e for e in room.entities if e.alive and e.kind == 'fancy_door']


def _vault(room):
    return next((e for e in room.entities
                 if e.alive and e.kind == 'seal_door'), None)


def _confined(room, r, c):
    """Flood from (r, c) over passable cells; confined iff the whole reachable
    region consists of pocket columns (1 or 3) — no corridor/shaft escape."""
    seen, q = {(r, c)}, [(r, c)]
    while q:
        rr, cc = q.pop()
        for dr, dc in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nr, nc = rr + dr, cc + dc
            if (nr, nc) not in seen and room.is_passable(nr, nc):
                seen.add((nr, nc))
                q.append((nr, nc))
    return all(cc in (1, 3) for _, cc in seen)


# ── builder structure ────────────────────────────────────────────────────────
@pytest.mark.parametrize('seed', SEEDS)
def test_ten_corridors_and_no_creature_in_any_of_them(seed):
    room = _room(seed)
    assert (room.rows, room.cols) == (35, 60)
    for r in dg._OV_CORR_ROWS[:-1]:                  # C1..C9 span the full width
        assert room.cells[r][2] == CellType.FLOOR and room.cells[r][57] == CellType.FLOOR
    # C10 is a dead-end overhang above the sealed ledge
    assert room.cells[30][30] == CellType.FLOOR and room.cells[30][29] == CellType.WALL
    assert room.cells[31][29] == CellType.FLOOR and room.cells[31][30] == CellType.WALL
    # The gauntlet is gone. Not "fewer guards" — none, and no hearts to survive
    # them with: what stands between the player and the vault is ten words.
    assert not [e for e in room.entities if e.kind in ('goblin', 'warden')]
    assert not [e for e in room.entities if e.kind == 'heart_container']


#: corridor row -> where the gate holding THAT corridor's password stands.
#: A forward corridor keeps its own, at its line end. A backward one cannot —
#: its cut ends at the line head with no floor west to paste from — so its gate
#: waits one row down at col 3, and is opened with the word the cut is still
#: holding when the player drops.
_GATE_OF = {3: (3, 57), 6: (9, 3), 9: (9, 57), 12: (15, 3), 15: (15, 57),
            18: (21, 3), 21: (21, 57), 24: (27, 3), 27: (27, 57), 30: (31, 10)}


@pytest.mark.parametrize('seed', SEEDS)
def test_every_corridor_has_a_gate_and_they_are_all_different(seed):
    """The paste direction fixes the geometry. This level teaches `p` and not
    `P`, so a gate is always EAST of the player — which a forward corridor gets
    for nothing and a backward corridor pays for by carrying its word one row
    further on before spending it."""
    room = _room(seed)
    gates = {(e.row, e.col): e for e in _gates(room)}
    assert set(gates) == set(_GATE_OF.values())
    assert all(e.edit_immune for e in gates.values())
    assert all(e.password for e in gates.values())
    # ten different words: one corridor's cut must never open another's gate
    assert len({e.password for e in gates.values()}) == 10


def test_every_shaft_is_behind_a_shut_gate():
    """THE REASON THE LEVEL IS DARK, and the constraint that shaped its whole
    plan. The fog here is DERIVED — `_doors_block_sight` floods by feet and
    stops at shut doors — so a shaft the flood can reach is a corridor lit from
    the spawn and a `{n}G` that skips a lesson. Every shaft therefore has to
    hang below a gate, with no other way in."""
    room = _room()
    assert dg._OV_SHAFTS == tuple((r + 1, 57 if i % 2 == 0 else 2)
                                 for i, r in enumerate(dg._OV_CORR_ROWS[:-1]))
    gate_cells = {(e.row, e.col) for e in _gates(room)}
    for top, col in dg._OV_SHAFTS:
        assert room.cells[top][col] == CellType.FLOOR, (top, col)
        assert room.cells[top + 1][col] == CellType.FLOOR
        # the only neighbour of the shaft's mouth on the corridor row above is
        # the gate itself (forward), or the gate is the first thing on the row
        # it lands on (backward)
        above, below = (top - 1, col), (top + 2, col)
        assert (above in gate_cells) or ((below[0], below[1] + 1) in gate_cells), \
            f'shaft at {(top, col)} is reachable without opening anything'


@pytest.mark.parametrize('seed', SEEDS)
def test_only_the_first_corridor_is_lit_from_the_spawn(seed):
    """What the gated shafts buy. Everything past corridor 1 sleeps dark, so a
    line jump cannot land in a lesson that has not been opened — which is the
    front geometry alone does not defend (see test_operators_vault_lessons)."""
    room = _room(seed)
    for r in dg._OV_CORR_ROWS:
        floor = [c for c in range(2, 58) if room.cells[r][c] == CellType.FLOOR]
        lit = [c for c in floor if (r, c) not in room.fog_cells]
        if r == dg._OV_CORR_ROWS[0]:
            assert lit == floor, 'corridor 1 must be visible — it is the tutorial'
        else:
            assert not lit, f'corridor row {r} is lit from the spawn'


def test_corridor_loot_is_scroll_chests_and_no_treasure_hoard():
    room = _room()
    assert {(e.row, e.col) for e in room.entities if e.kind == 'chest_scroll'} == \
        {(33, 7), (33, 12)}
    # nothing behind the vault door but the way out — the lessons and the exit
    # ARE the reward
    behind = [e for e in room.entities
              if e.row == 33 and e.col > dg._OV_DOOR[1] and e.kind != 'exit']
    assert behind == []


def test_vault_is_sealed_and_fogged_until_arrival():
    # The stone law (2026-07-19): everything below the C10 overhang sleeps
    # dark at build — the ledge, the walkway and the vault — and the tick's
    # per-key door-blocked _reveal_from lights it only when the collapse
    # drops the player in (the dd park is fog-blind for that fall). The
    # corridor pockets stay visible: they are the warning.
    room = _room()
    assert room.exit_pos == (33, 19)
    assert room.exit_pos in room.fog_cells           # the way out, dark
    assert (33, 16) in room.fog_cells                # the walkway too
    assert (31, 10) in room.fog_cells                # and the sealed ledge
    assert (4, 3) not in room.fog_cells              # but not the pockets


@pytest.mark.parametrize('seed', SEEDS)
def test_each_corridor_carries_its_own_password_and_a_filler(seed):
    """The two pieces the forcing rests on, per corridor: the password the gate
    wants, laid on the floor to be cut, and at least one OTHER word for a cut
    that over-reaches to sweep in. A corridor that lost its filler would take
    the password just as happily from a `d$`."""
    room = _room(seed)
    by_cell = {(e.row, e.col): e for e in _gates(room)}
    for corridor, gate_cell in _GATE_OF.items():
        password = by_cell[gate_cell].password
        if corridor == 30:
            # C10 is the exception, and has to be: its lesson IS "take the whole
            # line", so a filler word would make the correct cut wrong. What
            # holds its ceiling instead is where the phrase ENDS — flush against
            # the cursor, so `d0` (which stops one short) hands the gate the
            # phrase with its final letter missing.
            end = max(ru.col + len(ru.symbols) - 1
                      for ru in room.char_runs if ru.row == 30)
            assert end == 57, 'C10 phrase no longer reaches the arrival column'
            continue
        # lay the row out by COLUMN, which is the only reading that can tell a
        # filler from the glue welded onto the password: both are extra text,
        # but only one of them is somewhere a cut can stop short of.
        cells = {}
        for ru in room.char_runs:
            if ru.row == corridor:
                for i, sym in enumerate(ru.symbols):
                    cells[ru.col + i] = sym
        line = ''.join(cells.get(c, ' ') for c in range(room.cols))
        at = line.find(password)
        assert at >= 0, (corridor, password, line.strip())
        # something stands OUTSIDE the password's own columns, for a cut that
        # over-reaches to sweep in
        span = range(at, at + len(password))
        assert any(c not in span for c in cells), \
            f'corridor at row {corridor} has no filler word'


def test_the_seep_shows_c10s_lesson_instead_of_saying_it():
    """C10 used to be taught by a banner: "…This floor is one rotten line: dd
    cuts it out from under you." That is the answer read aloud, at the one
    corridor whose lesson is hardest to see coming.

    The geometry says it instead. A shelf hangs below corridor 8's gate column
    with WATER under it, and that water lies in C10's own floor line. Four
    things have to hold for it to teach anything, and each is a separate way to
    break it:"""
    room = _room()
    shelf, seep = dg._OV_SEEP_SHELF, dg._OV_SEEP_WATER

    # 1. you can stand on the shelf, and the water stops you going further
    assert room.cells[shelf[0]][shelf[1]] == CellType.FLOOR
    assert room.cells[seep[0]][seep[1]] == CellType.WATER
    assert not room.is_passable(*seep)

    # 2. the water is NOT misted. Mist is permanent haze that a reveal never
    #    clears — it is what stops the west channel laddering light past the
    #    gates — so a misted cell can never be the thing a player is meant to
    #    see. This one has to surface.
    assert seep not in room.underwater_cells

    # 3. it is in C10's line, which is what makes `dd` the answer rather than a
    #    guess: the row the water sits in is the row the cut takes out
    assert seep[0] == dg._OV_SPLIT_ROW

    # 4. and the cell beneath it is the ledge, so when that line goes the shelf
    #    opens onto what rose into its place
    assert room.cells[dg._OV_LEDGE_ROW][seep[1]] == CellType.FLOOR


def test_the_seep_stays_dark_until_the_gate_above_it_opens():
    """It must not be visible from the spawn (that is a spoiler two acts early)
    and it must not light the vault when it does surface (that is the prize).
    What it shows is hall and a door — somewhere to get to, and no way yet."""
    room = _room()
    assert dg._OV_SEEP_SHELF in room.fog_cells
    assert dg._OV_SEEP_WATER in room.fog_cells

    # the flood as it stands the moment corridor 8's gate opens. It has to be
    # measured with the gate DEAD and from the cell the player is standing on:
    # _flood_reachable stops at a live door without expanding through it, so
    # flooding from the gate's own cell reaches exactly that cell and would
    # report the seep hidden no matter what the geometry did.
    from vimny.engine.motion import _flood_reachable
    gate = next(e for e in _gates(room) if (e.row, e.col) == (27, 3))
    room.kill_entity(gate)
    room.rebuild_indexes()
    lit = _flood_reachable(room, 27, 2)
    assert dg._OV_SEEP_SHELF in lit and dg._OV_SEEP_WATER in lit
    assert (33, 16) not in lit, 'the seep lights the vault walkway'
    assert room.exit_pos not in lit, 'the seep lights the way out'


def test_dd_on_the_overhang_joins_the_shelf_to_the_ledge():
    """The payoff, driven: the cut that removes the water's line is the cut that
    connects the two halls."""
    room = _room(defog=True)
    shelf, seep = dg._OV_SEEP_SHELF, dg._OV_SEEP_WATER
    assert room.cells[seep[0]][seep[1]] == CellType.WATER      # blocked before
    player = Player(row=dg._OV_SPLIT_ROW, col=57)
    assert remove_row(room, dg._OV_SPLIT_ROW, player)
    # the ledge has risen into the water's row, directly under the shelf
    assert room.cells[shelf[0] + 1][shelf[1]] == CellType.FLOOR
    assert room.is_passable(shelf[0] + 1, shelf[1])


def test_oubliette_pockets_are_sealed_empty_floor():
    room = _room()
    for r, c in dg._OV_POCKETS:
        assert room.cells[r][c] == CellType.FLOOR
        assert room.entity_at(r, c) is None          # no ghouls — the seal traps
        assert not any(ru.row == r and ru.col <= c < ru.col + len(ru.symbols)
                       for ru in room.char_runs)


def test_the_pockets_sit_only_under_the_forward_corridors():
    """A backward corridor drops at col 2, one cell from where a pocket would
    sit, and a pit that touches the way out is an alcove rather than a trap. So
    the pits hang under the forward corridors only — and those rows carry a
    gate, which parries `dd` outright, making the pit the answer to a `}` off
    the wrong column rather than to a linewise cut."""
    room = _room()
    shaft_cols = {col for _, col in dg._OV_SHAFTS}
    for r, c in dg._OV_POCKETS:
        assert all(abs(c - sc) > 1 or room.cells[r][sc] != CellType.FLOOR
                   for sc in shaft_cols), f'pocket {(r, c)} touches a shaft'


def test_par_and_budget():
    room = _room()
    # 69 → 63 with the 2026-08-02 redesign, then 62, then 55 the same day when
    # the travel was golfed properly. The combat came out (no guard to strike,
    # no key to fetch, no pack to finish) and the corridors alternate: a forward
    # one pays `$ p 3j` into the gate at its line end, a backward one hands its
    # word to the door waiting a row below, where the `p` that opens it doubles
    # as the first key of the next lesson.
    #
    # EVERY backward drop is a bare `G`. The fog here is derived, so a fogged
    # cell is not standable and the buffer ends at the frontier — `G` means 'as
    # far down as the light goes', which IS the drop, and it re-aims itself each
    # time a gate opens. 62 came from checking one drop and reasoning about the
    # rest; par is the optimum, so the number that matters is the one a replay
    # measures.
    assert room.par == 55
    assert room.budget == math.ceil(room.par * 1.4) == 77
    assert room.answer.strip()
    # travel discipline: counts stay single-digit (a human can count to 9)
    for tok in room.answer.split():
        if tok[0].isdigit() and len(tok) > 1:
            assert len(tok) == 2, f'multi-digit count in answer: {tok}'


# ── the D shorthand is its own later lesson ─────────────────────────────────
def test_D_shorthand_locked_until_the_cipher_cell():
    d_short = {'type': 'operator', 'op': 'd', 'motion': '$', 'count': 1,
               'shorthand': 'D'}
    assert not action_allowed(d_short, known_commands('operators_vault'))
    assert action_allowed(d_short, known_commands('cipher_cell'))
    # the two-key grammar itself is fully open at the Vault
    for m in ('w', 'b', 'e', 'W', 'B', 'E', '0', '$', 'line'):
        assert action_allowed({'type': 'operator', 'op': 'd', 'motion': m,
                               'count': 1}, known_commands('operators_vault'))


def test_the_westward_paste_is_not_taught_here():
    """The constraint the whole layout is built around, asserted so that nobody
    "fixes" a corridor by reaching for `P`: it is not in this level's hand."""
    known = known_commands('operators_vault')
    assert action_allowed({'type': 'paste', 'before': False, 'count': 1}, known)
    assert not action_allowed({'type': 'paste', 'before': True, 'count': 1}, known)


# ── paragraph motions cannot vault into the pockets or the vault ─────────────
def test_paragraph_jumps_respect_the_walls():
    """}/{ land only in a segment holding the player's own column (engine
    rule) — so they can't teleport sideways into the sealed pockets, ladder
    down the spacer rows, or reach the vault walkway from above."""
    from vimny.engine.motion import apply_motion

    room = _room()                                   # fog intact = real play
    def jump(start, motion):
        p = Player(row=start[0], col=start[1])
        moved = apply_motion(p, motion, 1, room, game_h=30)
        return (p.row, p.col), moved

    assert jump((3, 2), '}') == ((3, 2), False)      # spawn: wall below
    assert jump((3, 5), '}') == ((3, 5), False)      # no vault to (32,10)/walkway
    # standing directly above the visible pit IS a way in… and u the way out
    assert jump((3, 3), '}') == ((4, 3), True)
    assert jump((4, 3), '}') == ((4, 3), False)      # sealed below
    assert jump((4, 3), '{') == ((4, 3), False)      # sealed above


# ── dd: parried wherever a gate stands, and REQUIRED at C10 ─────────────────
def test_dd_is_parried_on_the_forward_corridors_and_free_on_the_backward_ones():
    """A gate is edit_immune, so it parries the linewise cut — which means the
    forward corridors (gate at their own line end) refuse `dd` outright, and the
    backward ones (whose gate waits a row below) do not.

    That asymmetry is not a hole. What a `dd` on a backward corridor puts in the
    register is the WHOLE row — the filler, the glue and the password together —
    and no gate below will hear that. The cut is allowed; it just spends the
    word the corridor was carrying."""
    room = _room(defog=True)
    for r in (3, 9, 15, 21, 27):
        assert remove_row(room, r, Player(row=r, col=30)) is False, r
    assert room.rows == 35
    for r in (6, 12, 18, 24):
        fresh = _room(defog=True)
        assert remove_row(fresh, r, Player(row=r, col=30)) is True, r


def test_c10_dd_raises_the_ledge_and_a_second_dd_is_parried():
    room = _room(defog=True)
    p = Player(row=30, col=57)
    assert remove_row(room, 30, p)
    _cursor_to_line_start(room, p, 30)
    # VIM-TRUE, and aimed. `'startofline'` is on by default, so a linewise `d`
    # lands on the first non-blank of the line that took the deleted one's
    # place — never the column you cut from. You arrive at col 57 and leave from
    # col 3, and that is Vim rather than a convenience.
    #
    # Which non-blank it is, is the level's choice, and the ledge's word is laid
    # in the seep's own column so the answer is "the cell the water was filling".
    # The line you could not cross is the line you now stand in.
    assert (p.row, p.col) == (30, dg._OV_SEEP_WATER[1])
    assert room.is_passable(*dg._OV_SEEP_SHELF), 'the shelf above is now open'
    assert room.rows == 34
    assert room.exit_pos == (32, 19)                 # the vault slid up with the cut
    # the ledge carries C10's own gate, so greed is refused rather than fatal
    assert remove_row(room, 30, p) is False


# ── the vault: it opens when every password has been spoken ─────────────────
def test_the_vault_opens_only_when_every_gate_is_open():
    room = _room()
    player = Player(row=33, col=15)
    gates = _gates(room)
    for g in gates[:-1]:
        room.kill_entity(g)
    main._operators_vault_tick(room, player)
    assert _vault(room) is not None                  # the vault still stands
    room.kill_entity(gates[-1])                      # the last word is spoken
    msgs = main._operators_vault_tick(room, player)
    assert any('vault door' in m for m in msgs)
    assert _vault(room) is None


def test_the_vault_rule_is_stateless_so_undo_re_bars_it():
    """The tick re-derives the vault from the gates every turn rather than
    remembering, which is what makes it undo-safe: reviving a gate must shut the
    vault again, and re-opening it must re-open the vault."""
    room = _room()
    player = Player(row=3, col=7)                    # away from the vault, so the
                                                     # approach nudge stays quiet
    gates = _gates(room)
    for g in gates:
        room.kill_entity(g)
    assert main._operators_vault_tick(room, player)
    assert _vault(room) is None
    # undo: the gate and the vault come back as snapshot copies
    for e in room.entities:
        if e.kind in ('fancy_door', 'seal_door'):
            e.alive = True
    room.rebuild_indexes()
    assert main._operators_vault_tick(room, player) == []
    assert _vault(room) is not None
    for g in _gates(room):
        room.kill_entity(g)
    assert main._operators_vault_tick(room, player)
    assert _vault(room) is None


def test_the_vault_rule_survives_undo_replacing_the_entity_list():
    """Undo replaces room.entities with snapshot COPIES; the tick must resolve
    the doors live, never through references held across a turn."""
    room = _room()
    player = Player(row=33, col=15)
    room.entities = [Entity(kind=e.kind, row=e.row, col=e.col, hp=e.hp,
                            alive=e.alive, max_hp=e.max_hp, ai=e.ai, tag=e.tag,
                            password=e.password, edit_immune=e.edit_immune)
                     for e in room.entities]
    room.rebuild_indexes()
    for g in _gates(room):
        room.kill_entity(g)
    assert main._operators_vault_tick(room, player)
    assert _vault(room) is None


def test_vault_door_nudges_while_a_gate_stands():
    room = _room()
    player = Player(row=33, col=15)                  # at the door, too early
    msgs = main._operators_vault_tick(room, player)
    assert any('gate above' in m for m in msgs)
    assert _vault(room) is not None                  # and it is still shut


# ── executed solve ───────────────────────────────────────────────────────────
def _drive(monkeypatch, d, keys):
    """Run keys through the real loop; returns (state, budget) where state has
    the win position/hp if the exit was reached. Stops (without failing) when
    the keys run out — the win-celebration screens consume a few trailing
    blanks, hence the padding."""
    C.init(Terminal())
    state = {}

    class _Win(Exception):
        pass

    class _OutOfKeys(Exception):
        pass

    def _winsig(term, iw, dungeon, player):
        state['pos'] = (player.row, player.col)
        state['hp'] = player.hp
        raise _Win()

    monkeypatch.setattr(main, '_fireworks_animation', _winsig)
    monkeypatch.setattr(main, '_unlock_animation', lambda *a, **k: None)
    monkeypatch.setattr(main, '_show_catalog_scroll', lambda *a, **k: None)
    cap = {'msgs': []}

    def _render_stub(term, dn, pl, bg, message='', *a, **k):
        cap.update(budget=bg, player=pl)
        if message:
            cap['msgs'].append(message)

    monkeypatch.setattr(main, 'render_all', _render_stub)

    it = iter(keys + [''] * 2000)

    def _ink(*a, **k):
        try:
            return Keystroke(next(it))
        except StopIteration:
            raise _OutOfKeys()

    term = Terminal()
    monkeypatch.setattr(term, 'inkey', _ink)

    try:
        main.run_dungeon(term, 'operators_vault', {}, player_name='admin', _dungeon=d)
    except (_Win, _OutOfKeys):
        pass
    return state, cap


@pytest.mark.parametrize('seed', SEEDS)
def test_answer_solves_the_vault(monkeypatch, seed):
    """Driving the answer through the real loop reaches the exit at exactly par,
    unharmed, with every gate spoken open — for EVERY seed, since the lessons
    and the travel key off word positions and lengths, never the letters the
    seed happened to deal."""
    d = dg.build_dungeon_operators_vault(seed)
    room = d.rooms[0]
    keys = [ch for tok in room.answer.split() for ch in tok]
    state, cap = _drive(monkeypatch, d, keys)

    assert state['pos'] == room.exit_pos == (32, 19)  # the vault, one collapse later
    assert state['hp'] == 6                           # nothing in here can hurt you
    assert cap['budget'].spent == room.par            # solved in exactly par
    assert room.rows == 34                            # exactly one line was cut away
    assert _gates(room) == []
    assert _vault(room) is None


def test_a_gate_refuses_the_wrong_words(monkeypatch):
    """The half the guards could never hold: a cut that reaches TOO FAR opens
    nothing. `d$` on corridor 1 takes the password and the filler behind it, and
    the gate — which reads the register, not the floor — says so and stays shut."""
    d = dg.build_dungeon_operators_vault(7)
    room = d.rooms[0]
    state, cap = _drive(monkeypatch, d, list('d$$p'))

    assert state == {}
    assert [e for e in _gates(room) if e.row == 3]     # still standing
    # the refusal quotes the REGISTER back — that is what teaches that the door
    # weighs the whole cut rather than looking for its word somewhere inside it
    # — and never quotes the password, which would be handing over the answer
    err = cap['player'].error or ''
    assert 'It hears' in err and 'does not budge' in err
    assert 'wants' not in err


def test_blocked_dd_is_parried_loudly_and_costs_nothing(monkeypatch):
    """Regression: dd on a gated row used to spend budget, clobber the register,
    leave a no-op undo entry, and lie with 'Deleted.'. A parried cut must be
    free, side-effect free, and SAY it was parried."""
    d = dg.build_dungeon_operators_vault(7)
    room = d.rooms[0]
    state, cap = _drive(monkeypatch, d, list('ddu'))

    assert state == {}
    assert room.rows == 35                           # nothing collapsed
    assert cap['budget'].spent == 0                  # nothing paid
    player = cap['player']
    assert main._held_key(player) is None            # register untouched
    assert player.registers.get('"') is None
    joined = ' '.join(cap['msgs'])
    assert 'parried' in joined
    assert 'Deleted.' not in joined                  # no false report
    assert 'Nothing to undo' in joined               # and no phantom undo entry
    assert player.last_change is None                # '.' has nothing to repeat


def test_blocked_dd_on_a_one_line_buffer(monkeypatch):
    """The structural twin: a single-row buffer (the wardenverse shape) refuses
    dd — the dungeon can't go to zero lines — with its own message."""
    from vimny.engine.world import Room, RoomType, CellType, Dungeon

    room = Room(room_type=RoomType.ENTRY, rows=1, cols=8)
    room.cells = [[CellType.WALL] + [CellType.FLOOR] * 6 + [CellType.WALL]]
    room.spawn_pos, room.exit_pos = (0, 1), (0, 6)
    room.char_runs, room.entities = [], []
    room.rebuild_indexes()
    room.par, room.budget, room.answer = 5, 10, ''
    d = Dungeon(name='dd-last-line', seed=0)
    d.rooms, d.current_room = [room], 0

    state, cap = _drive(monkeypatch, d, list('dd'))
    assert state == {}
    assert room.rows == 1 and cap['budget'].spent == 0
    assert any('last line resists' in m for m in cap['msgs'])
    assert not any('Deleted.' in m for m in cap['msgs'])


def test_deep_undo_unwinds_the_whole_solve(monkeypatch):
    """Regression for the undo report: unwinding the entire solve with u must
    walk back step by step to the pristine 35-row dungeon — every gate shut
    again, chests restored, budget refunded — never jumping rows or leaving the
    player walled in."""
    d = dg.build_dungeon_operators_vault(7)
    room = d.rooms[0]
    keys = [ch for tok in room.answer.split() for ch in tok]
    keys = keys[:-2]                                 # stop one step short of the exit
    keys += list('u' * 200)
    state, cap = _drive(monkeypatch, d, keys)

    assert state == {}                               # never won, never crashed
    player = cap['player']
    assert room.rows == 35                           # the cut line is back
    assert len(_gates(room)) == 10                   # every gate shut again
    assert _vault(room) is not None
    assert len([e for e in room.entities
                if e.alive and e.kind == 'chest_scroll']) == 2
    assert cap['budget'].spent == 0                  # fully refunded
    assert (player.row, player.col) == room.spawn_pos
    assert room.is_passable(player.row, player.col)  # never parked inside a wall


def test_hint_bar_surfaces_the_linewise_dd():
    # Learning 'd' unlocks the linewise dd as well as d{m}; the bar bundles dd into the
    # d keys cell (like c{m}  cc) so delete-line is never gated-in-but-invisible.
    from vimny.render.hint_bar import hint_text
    bar = hint_text(known_commands('operators_vault'), 'operators_vault')
    assert 'd{m}' in bar and 'dd' in bar
