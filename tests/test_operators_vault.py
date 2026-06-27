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

"""The Operator's Vault (L18) — the first {operator}{motion} level (delete).

Ten snaked corridors, each admitting exactly one cheapest d-variant (dw, db,
de, dB, dE, dF?, dW, d0, d$, dd). Armored hp-2 guards make blade-to-blade x
bloody while a d-cut removes them outright. Gated corridors drop their colored
key when their guard group is wiped; the untagged vault key drops once every
guard is down (both stateless + undo-safe in main._operators_vault_tick).
Sloppy wide cuts shred the scroll chests; dd off the intended row collapses
the corridor into a sealed oubliette pocket (only u climbs out). Travel after
each cut rides the words left standing (w/e hops) — no big counted moves.
Structure tests + a full executed solve through the real run_dungeon loop
(answer == par, no damage) + a deep-undo regression.
"""
import math

import pytest
from blessed import Terminal
from blessed.keyboard import Keystroke

import main
import generation.dungeon_gen as dg
from engine.world import CellType, Entity
from engine.player import Player
from engine.reflow import remove_row
from engine.operator import op_delete, entity_clip, _cursor_to_line_start
from engine.text_object import compute_text_object
from engine.command_guard import action_allowed
from engine.motion import _is_word_char
from content.levels import known_commands
import render.colors as C
from tests import SEEDS


def _room(seed=7, defog=False):
    room = dg.build_dungeon_operators_vault(seed).rooms[0]
    if defog:
        room.fog_cells = set()
    return room


def _guards(room, row=None):
    return [e for e in room.entities if e.alive and e.kind == 'goblin'
            and (row is None or e.row == row)]


def _chests(room, row):
    return [e for e in room.entities
            if e.alive and e.kind == 'chest_scroll' and e.row == row]


def _cut(room, player, motion, target=None):
    action = {'type': 'operator', 'op': 'd', 'motion': motion, 'count': 1}
    if target is not None:
        action['target'] = target
    tobj = compute_text_object(player, action, room)
    if tobj is None:
        return False
    op_delete(room, player, tobj, collapse=(motion == 'line'))
    return True


def _pocket_or_wall(room, r, c):
    """A cell that confines: impassable, or another sealed oubliette pocket
    (collapses can stack two pockets into a 2-cell chimney — still sealed)."""
    return (not room.is_passable(r, c)) or room.cells[r][c] == CellType.FLOOR


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
def test_ten_corridors_with_armored_guards(seed):
    room = _room(seed)
    assert (room.rows, room.cols) == (35, 60)
    for r in dg._OV_CORR_ROWS[:-1]:                  # C1..C9 span the full width
        assert room.cells[r][2] == CellType.FLOOR and room.cells[r][57] == CellType.FLOOR
    # C10 is a dead-end overhang above the sealed ledge
    assert room.cells[30][30] == CellType.FLOOR and room.cells[30][29] == CellType.WALL
    assert room.cells[31][29] == CellType.FLOOR and room.cells[31][30] == CellType.WALL
    guards = _guards(room)
    assert len(guards) == 20
    assert all(e.hp == 2 and e.ai == 'chase' for e in guards)   # armored chasers
    per_row = {r: len(_guards(room, r)) for r in dg._OV_CORR_ROWS[:-1]}
    assert per_row == {3: 1, 6: 1, 9: 1, 12: 2, 15: 1, 18: 3, 21: 2, 24: 3, 27: 3}
    assert len(_guards(room, 31)) == 3               # the last pack, on the ledge


def test_shaft_placement_forward_at_line_end_backward_off_line_start():
    room = _room()
    for top, col in dg._OV_SHAFTS:
        assert room.cells[top][col] == CellType.FLOOR
        assert room.cells[top + 1][col] == CellType.FLOOR
    fwd = [col for top, col in dg._OV_SHAFTS if top in (4, 10, 16, 22, 28)]
    bwd = [col for top, col in dg._OV_SHAFTS if top in (7, 13, 19, 25)]
    assert all(col == 57 for col in fwd)             # forward exits: one $ away
    assert all(2 < col < 57 for col in bwd)          # backward exits: 0 overshoots


def test_gates_are_edit_immune_uniquely_colored_and_no_keys_preplaced():
    room = _room()
    gates = {(e.row, e.col): e for e in room.entities if e.kind == 'locked_door'}
    assert set(gates) == {(3, 18), (9, 20), (21, 45), (33, 17)}
    assert all(e.edit_immune for e in gates.values())
    assert gates[(3, 18)].tag == 'gold'
    assert gates[(9, 20)].tag == 'blue'
    assert gates[(21, 45)].tag == 'red'
    assert gates[(33, 17)].tag == ''                 # the vault door — untagged
    # every key DROPS from a kill; none is lying around to run past
    assert not [e for e in room.entities if e.kind == 'floor_key']
    assert room._ov_groups == (('g1', 'gold'), ('g3', 'blue'), ('g7', 'red'))


def test_corridor_loot_is_scroll_chests_and_no_treasure_hoard():
    room = _room()
    assert {(e.row, e.col) for e in room.entities if e.kind == 'chest_scroll'} == \
        {(3, 14), (9, 16), (15, 20), (21, 41)}
    # no hearts anywhere, and nothing behind the vault door but the way out —
    # the lessons and the exit ARE the reward
    assert not [e for e in room.entities if e.kind == 'heart_container']
    behind = [e for e in room.entities
              if e.row == 33 and e.col > dg._OV_DOOR[1] and e.kind != 'exit']
    assert behind == []


def test_vault_is_sealed_and_fogged_until_opened():
    room = _room()
    assert room.exit_pos == (33, 19)
    assert room.exit_pos in room.fog_cells           # the way out, dark behind the door
    assert (33, 16) not in room.fog_cells            # …but the walkway shows
    assert (31, 10) not in room.fog_cells            # the sealed ledge shows too
    assert (4, 3) not in room.fog_cells              # and the oubliette pockets


@pytest.mark.parametrize('seed', SEEDS)
def test_corridor_text_is_drawn_from_the_vocab_per_seed(seed):
    """Words are sampled from the vocabulary files: positions and lengths are
    invariant (the layout and the answer key off them), the letters are not."""
    expect = {(3, 7): 3, (3, 13): 3, (6, 8): 4, (9, 12): 3, (9, 22): 3,
              (12, 8): 5, (15, 12): 6, (15, 24): 4, (18, 26): 1, (18, 46): 3,
              (21, 30): 5, (21, 40): 5, (21, 47): 3, (24, 10): 6, (27, 12): 3,
              (27, 25): 3, (31, 4): 5, (33, 7): 4, (33, 12): 4}
    room = _room(seed)
    got = {(ru.row, ru.col): ''.join(ru.symbols) for ru in room.char_runs}
    assert {pos: len(w) for pos, w in got.items()} == expect
    assert got[(18, 26)] == '?'                      # the find bait is fixed
    # plain words are single WORDS (no internal subword breaks)…
    mixed_at = {(12, 8), (15, 12), (21, 30)}
    for pos, w in got.items():
        if pos == (18, 26):
            continue
        if pos in mixed_at:                          # …mixed tokens must break
            assert _is_word_char(w[0])
            assert any(not _is_word_char(c) for c in w[1:-1])
        else:
            assert all(_is_word_char(c) for c in w)
    # and different seeds deal different words
    other = {(ru.row, ru.col): ''.join(ru.symbols)
             for ru in _room(seed + 1).char_runs}
    assert got != other


def test_oubliette_pockets_are_sealed_empty_floor():
    room = _room()
    for r, c in dg._OV_POCKETS:
        assert room.cells[r][c] == CellType.FLOOR
        assert room.entity_at(r, c) is None          # no ghouls — the seal traps
        assert not any(ru.row == r and ru.col <= c < ru.col + len(ru.symbols)
                       for ru in room.char_runs)


def test_par_and_budget():
    room = _room()
    assert room.par == 93
    assert room.budget == math.ceil(room.par * 1.4) == 131
    assert room.answer.strip()
    # travel discipline: counts stay single-digit (a human can count to 9),
    # and word motions appear only where they beat or tie the count move.
    # (a bare '0' is the line-start motion, not a count)
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


# ── precision forces (span semantics per corridor) ───────────────────────────
def test_c1_dw_is_exact_and_wider_cuts_shred_the_chest():
    room = _room(defog=True)
    p = Player(row=3, col=7)
    _cut(room, p, 'w')                               # the lesson
    assert _guards(room, 3) == [] and _chests(room, 3)
    room = _room(defog=True)
    p = Player(row=3, col=7)
    _cut(room, p, '$')                               # sloppy — chest dies
    assert not _chests(room, 3)
    gate = next(e for e in room.entities if e.kind == 'locked_door' and e.row == 3)
    assert gate.alive                                # edit_immune — cuts can't open it


def test_c3_de_is_exact_dw_cannot_even_fire():
    room = _room(defog=True)
    p = Player(row=9, col=7)
    _cut(room, p, 'e')                               # e from the gap → imp's tail
    assert _guards(room, 9) == [] and _chests(room, 9)
    room = _room(defog=True)
    p = Player(row=9, col=12)
    assert _cut(room, p, 'w') is False               # gate blocks the w-scan
    room = _room(defog=True)
    p = Player(row=9, col=7)
    _cut(room, p, '$')
    assert not _chests(room, 9)                      # sloppy — chest dies


def test_c4_db_misses_the_head_guard_dB_sweeps_both():
    room = _room(defog=True)
    p = Player(row=12, col=57)
    _cut(room, p, 'b')                               # only reaches the 'ps' subword
    assert [(e.row, e.col) for e in _guards(room, 12)] == [(12, 8)]
    room = _room(defog=True)
    p = Player(row=12, col=57)
    _cut(room, p, 'B')                               # from the WORD head
    assert _guards(room, 12) == []
    assert (p.row, p.col) == (12, 8)                 # lands a step from the shaft


def test_c5_dE_is_exact_dW_shreds_the_chest():
    room = _room(defog=True)
    p = Player(row=15, col=7)
    _cut(room, p, 'E')                               # E from the gap → token tail
    assert _guards(room, 15) == [] and _chests(room, 15)
    room = _room(defog=True)
    p = Player(row=15, col=12)
    _cut(room, p, 'W')                               # crosses the gap → eats the chest
    assert not _chests(room, 15)


def test_c6_dF_lands_on_the_shaft_mouth():
    room = _room(defog=True)
    p = Player(row=18, col=57)
    _cut(room, p, 'F', target='?')
    assert _guards(room, 18) == []
    assert (p.row, p.col) == (18, 26)                # exactly the way down
    room = _room(defog=True)
    p = Player(row=18, col=57)
    _cut(room, p, '0')                               # the sweep works but…
    assert _guards(room, 18) == []
    assert p.col == 2                                # …overshoots the mouth at 26


def test_c7_dE_misses_the_gap_guard_dW_is_exact_d_dollar_shreds():
    room = _room(defog=True)
    p = Player(row=21, col=30)
    _cut(room, p, 'E')
    assert [(e.row, e.col) for e in _guards(room, 21)] == [(21, 37)]
    room = _room(defog=True)
    p = Player(row=21, col=30)
    _cut(room, p, 'W')
    assert _guards(room, 21) == [] and _chests(room, 21)
    room = _room(defog=True)
    p = Player(row=21, col=30)
    _cut(room, p, '$')                               # $ stops at the gate, eats chest
    assert not _chests(room, 21)


def test_c8_db_misses_the_line_head_guard():
    room = _room(defog=True)
    p = Player(row=24, col=57)
    _cut(room, p, 'b')                               # b stops at 'censer'
    assert (24, 3) in [(e.row, e.col) for e in _guards(room, 24)]
    room = _room(defog=True)
    p = Player(row=24, col=57)
    _cut(room, p, '0')
    assert _guards(room, 24) == [] and p.col == 2


def test_c9_no_find_reaches_the_whole_pack():
    room = _room(defog=True)
    deep = room.char_run_at(27, 27)                  # the row's deepest character
    target = deep.symbols[27 - deep.col]
    p = Player(row=27, col=7)
    _cut(room, p, 'f', target=target)
    assert {(e.row, e.col) for e in _guards(room, 27)} >= {(27, 30), (27, 40)}


# ── paragraph motions cannot vault into the pockets or the vault ─────────────
def test_paragraph_jumps_respect_the_walls():
    """}/{ land only in a segment holding the player's own column (engine
    rule) — so they can't teleport sideways into the sealed pockets, ladder
    down the spacer rows, or reach the vault walkway from above."""
    from engine.motion import apply_motion

    room = _room()                                   # fog intact = real play
    def jump(start, motion):
        p = Player(row=start[0], col=start[1])
        moved = apply_motion(p, motion, 1, room, game_h=30)
        return (p.row, p.col), moved

    assert jump((3, 2), '}') == ((3, 2), False)      # spawn: wall below
    assert jump((3, 5), '}') == ((3, 5), False)      # no vault to (32,5)/walkway
    assert jump((3, 57), '}') == ((3, 57), False)    # shaft fogged pre-gate
    # standing directly above the visible pit IS a way in… and u the way out
    assert jump((3, 3), '}') == ((4, 3), True)
    assert jump((4, 3), '}') == ((4, 3), False)      # sealed below
    assert jump((4, 3), '{') == ((4, 3), False)      # sealed above


# ── dd: parried on gate rows, oubliette everywhere else, REQUIRED at C10 ────
def test_dd_is_parried_on_gate_rows():
    room = _room(defog=True)
    for r in (3, 9, 21):
        assert remove_row(room, r, Player(row=r, col=30)) is False
    assert room.rows == 35


def test_dd_elsewhere_collapses_into_a_sealed_oubliette():
    room = _room(defog=True)
    p = Player(row=6, col=30)
    assert remove_row(room, 6, p)
    _cursor_to_line_start(room, p, 6)
    assert (p.row, p.col) == (6, 3)                  # the first-spacer pocket
    assert _confined(room, p.row, p.col)
    # a chained dd just falls one pocket deeper — still no way out but u
    assert remove_row(room, p.row, p)
    _cursor_to_line_start(room, p, p.row)
    assert (p.row, p.col) == (6, 1)                  # the second-spacer pocket
    assert _confined(room, p.row, p.col)


def test_c10_dd_raises_the_ledge_and_a_second_dd_is_the_oubliette():
    room = _room(defog=True)
    p = Player(row=30, col=57)
    assert remove_row(room, 30, p)
    _cursor_to_line_start(room, p, 30)
    assert (p.row, p.col) == (30, 2)                 # riding the risen ledge
    assert {(e.row, e.col) for e in _guards(room, 30)} == \
        {(30, 10), (30, 16), (30, 22)}               # the last pack, now on your line
    assert room.exit_pos == (32, 19)                 # the vault slid up with the cut
    assert remove_row(room, 30, p)                   # greed: cut the ledge too…
    _cursor_to_line_start(room, p, 30)
    assert (p.row, p.col) == (30, 3)                 # …and drop into the pocket
    assert _confined(room, p.row, p.col)


# ── key drops: stateless, group-scoped, undo-safe ────────────────────────────
def _keys(room):
    return [(e.row, e.col, e.tag) for e in room.entities
            if e.alive and e.kind == 'floor_key']


def test_gate_key_drops_when_its_group_falls_and_redrops_after_undo():
    room = _room()
    player = Player(row=3, col=7)
    g1 = next(e for e in room.entities if e.tag == 'g1')
    room.kill_entity(g1)
    assert main._operators_vault_tick(room, player)
    assert _keys(room) == [(3, 15, 'gold')]
    assert main._operators_vault_tick(room, player) == []     # no duplicate
    # undo restores the guard and removes the key → quiet again
    key = next(e for e in room.entities if e.kind == 'floor_key')
    room.kill_entity(key)
    g1.alive = True
    room.rebuild_indexes()
    assert main._operators_vault_tick(room, player) == []
    room.kill_entity(g1)                                       # re-kill → re-drop
    assert main._operators_vault_tick(room, player)
    assert _keys(room) == [(3, 15, 'gold')]


def test_key_drop_survives_undo_replacing_the_entity_list():
    """Undo replaces room.entities with snapshot COPIES; the tick must resolve
    gates live (by tag), never through stale references."""
    room = _room()
    player = Player(row=3, col=7)
    # simulate undo: replace every entity object with a same-state copy
    room.entities = [Entity(kind=e.kind, row=e.row, col=e.col, hp=e.hp,
                            alive=e.alive, max_hp=e.max_hp, ai=e.ai, tag=e.tag,
                            edit_immune=e.edit_immune) for e in room.entities]
    room.rebuild_indexes()
    g1 = next(e for e in room.entities if e.tag == 'g1')
    room.kill_entity(g1)
    assert main._operators_vault_tick(room, player)
    assert _keys(room) == [(3, 15, 'gold')]


def test_held_key_suppresses_the_drop_and_a_clobbered_register_redrops():
    room = _room()
    player = Player(row=3, col=7)
    g1 = next(e for e in room.entities if e.tag == 'g1')
    room.kill_entity(g1)
    # the player holds the gold key in the unnamed register → nothing to drop
    main._reg_write(player, '"',
                    entity_clip(Entity(kind='floor_key', row=3, col=15, tag='gold')),
                    is_delete=True)
    assert main._operators_vault_tick(room, player) == []
    # …until a later cut clobbers the register — then the vault is forgiving
    main._reg_write(player, '"',
                    {'linewise': False,
                     'rows': [{'width': 1, 'char_runs': [
                         {'dcol': 0, 'symbols': ('x',), 'kind': 'ember'}]}]},
                    is_delete=True)
    assert main._operators_vault_tick(room, player)
    assert _keys(room) == [(3, 15, 'gold')]


def test_vault_key_drops_only_when_every_guard_is_down():
    room = _room()
    player = Player(row=30, col=2)
    guards = _guards(room)
    for g in guards[:-1]:
        room.kill_entity(g)
    main._operators_vault_tick(room, player)
    assert all(t for _, _, t in _keys(room))         # gate keys maybe — no vault key
    room.kill_entity(guards[-1])                     # the last guard falls
    msgs = main._operators_vault_tick(room, player)
    assert any('vault key' in m for m in msgs)
    door = dg._OV_DOOR
    assert (door[0], door[1] - 3, '') in _keys(room)


def test_vault_door_nudges_while_guards_remain():
    room = _room()
    player = Player(row=33, col=15)                  # at the door, too early
    msgs = main._operators_vault_tick(room, player)
    assert any('draws breath' in m for m in msgs)
    assert _keys(room) == []


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
    unharmed, with every guard cut down, every door opened, and every scroll
    chest collected along the way — for EVERY seed, since the lessons and the
    travel key off word positions/lengths, never the sampled letters."""
    d = dg.build_dungeon_operators_vault(seed)
    room = d.rooms[0]
    keys = [ch for tok in room.answer.split() for ch in tok]
    state, cap = _drive(monkeypatch, d, keys)

    assert state['pos'] == room.exit_pos == (32, 19)  # the vault, one collapse later
    assert state['hp'] == 6                           # unharmed — guards cut at range
    assert cap['budget'].spent == room.par            # solved in exactly par keystrokes
    assert room.rows == 34                            # exactly one line was cut away
    assert _guards(room) == []
    assert not any(e.alive and e.kind == 'locked_door' for e in room.entities)
    assert not any(e.alive and e.kind == 'floor_key' for e in room.entities)
    # par includes collecting every scroll chest — none is left behind
    assert not [e for e in room.entities if e.alive and e.kind == 'chest_scroll']


def test_blocked_dd_is_parried_loudly_and_costs_nothing(monkeypatch):
    """Regression: dd on a gate row (display line 1 — the gold gate parries the
    collapse) used to spend budget, clobber the register, leave a no-op undo
    entry, and lie with 'Deleted.'. A parried cut must be free, side-effect
    free, and SAY it was parried."""
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
    from engine.world import Room, RoomType, CellType, Dungeon

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
    walk back step by step to the pristine 35-row dungeon — guards alive, gates
    re-locked, chests restored, budget refunded — never jumping rows or leaving
    the player walled in."""
    d = dg.build_dungeon_operators_vault(7)
    room = d.rooms[0]
    keys = [ch for tok in room.answer.split() for ch in tok]
    keys = keys[:-2]                                 # stop one step short of the exit
    keys += list('u' * 160)
    state, cap = _drive(monkeypatch, d, keys)

    assert state == {}                               # never won, never crashed
    player = cap['player']
    assert room.rows == 35                           # the cut line is back
    assert len(_guards(room)) == 20                  # every guard restored
    assert sorted(e.tag for e in room.entities
                  if e.alive and e.kind == 'locked_door') == ['', 'blue', 'gold', 'red']
    assert len([e for e in room.entities
                if e.alive and e.kind == 'chest_scroll']) == 4
    assert not [e for e in room.entities if e.alive and e.kind == 'floor_key']
    assert cap['budget'].spent == 0                  # fully refunded
    assert (player.row, player.col) == room.spawn_pos
    assert room.is_passable(player.row, player.col)  # never parked inside a wall
