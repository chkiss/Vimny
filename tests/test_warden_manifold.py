"""The Warden Manifold (Act IV boss, slug `warden_manifold`): "The Stamping Press".

He stamps himself into the world — wards of text, then copies of himself —
and the player out-copies him with the act's own verbs. The Warden is
edit_immune (every operator parries; the engine's real all-or-nothing shield)
and shelters in a podium niche per round; breaking the round's ward jams the
press (echoes gutter, his bolt draws) for exactly one x. Opening ritual: an
antechamber where the eternal flame must be spread to four braziers (yl + P,
the Beacon Tiers' fuel rule active) before the ritual gate draws.

Round → verb (see main._wm_ward_broken for the shift-proof checks):
  1  d{m}   guarded ward-words, wall posts pinning the reflow per word
  2  r + .  his stamp four times, the same untypable warp in each
  3  D      a rot-tail with a rank of false Wardens standing on it
  4  yy+P   his true name (kind='flame', it burns) must appear TWICE

Engine rules this boss leans on (each pinned below): tag='manifold' exempts
him from the stock warden auto-summon AND the post-x random leap (his round
machine moves him); echoes spawn hp=1 so one strike gutters a copy through
the disguise rule; the tick moves him via room.move_entity (the entity map
must follow him or x whiffs); brazier rows hold one brazier each and no
glyph anywhere east (open_gap shifts the whole buffer row).
"""
from collections import deque

from blessed.keyboard import Keystroke
from blessed import Terminal

import main
from engine.motion import apply_motion
from engine.player import Player
from engine.world import CellType, Entity
from content.levels import known_commands
from generation.dungeon_gen import (
    build_dungeon_warden_manifold,
    _WM_ROWS, _WM_COLS, _WM_AXIS, _WM_SPAWN, _WM_FLAME, _WM_BRAZIERS,
    _WM_GATE, _WM_COLUMN_COLS, _WM_COLUMN_ROWS, _WM_PODIUMS,
    _WM_WARD1, _WM_WARD1_POSTS, _WM_WARD2, _WM_WARD3, _WM_WARD4,
    _WM_HEARTS, _WM_SEAL, _WM_EXIT, _WM_BUDGET, _QM_FLAME,
)
import pytest

from tests import SEEDS, cached_room


def _room(seed):
    """Shared READ-ONLY build; mutating tests call the builder directly."""
    return cached_room('build_dungeon_warden_manifold', seed)


def _warden(room):
    return next((e for e in room.entities if e.kind == 'warden' and e.alive), None)


def _fight_script(room) -> str:
    """The canonical full fight, key for key (verified live; deterministic —
    the manifold warden never random-leaps)."""
    letter = room._wm_word2[0]
    return (
        # ritual: lift the flame, light the brazier diamond, through the gate
        'll' + 'yl'
        + '5k' + '5l' + 'P' + '4j' + '3l' + 'P' + 'jj' + 'P' + '4j' + '3h' + 'P'
        + '5k' + '4l' + 'll'
        # R1: de × 3 (word 1 from the west; around the posts), strike 1
        + 'kk' + 'll' + 'de' + 'j' + '6l' + 'k' + 'de' + 'j' + '5l' + 'k' + 'de'
        + 'kk' + 'hh' + 'k' + 'x'
        # heart 1 via clear row 7
        + '4j' + '10l' + '3k' + 'x'
        # R2: r + dots, strike 2
        + 'jj' + 'll' + 'r' + letter + 'w.' * 3
        + '8h' + 'kk' + 'hh' + 'k' + 'x'
        # R3: D the rot and the rank, strike 3, heart 2
        + 'jjjjj' + '29h' + 'jj' + 'D' + '9l' + 'jjj' + 'x'
        + '3k' + '10l' + 'jj' + 'x'
        # R4: the name twice, the kill, the seal, out
        + 'kk' + '4l' + 'yy' + 'p' + '6l' + 'jj' + 'j' + 'x'
        + '6k' + '17l'
    )


def _drive(dungeon, keys_str, monkeypatch, finish=':q!\r'):
    keys = [Keystroke(ch) for ch in keys_str] + [Keystroke(ch) for ch in finish]
    monkeypatch.setattr(main, 'render_all', lambda *a, **k: None)
    monkeypatch.setattr(main.time, 'sleep', lambda *a, **k: None)
    for anim in ('_fireworks_animation', '_win_animation', '_starfield_victory',
                 '_heart_container_animation', '_unlock_animation'):
        monkeypatch.setattr(main, anim, lambda *a, **k: None)
    term = Terminal()
    it = iter(keys)
    monkeypatch.setattr(term, 'inkey', lambda *a, **k: next(it, Keystroke('')))
    return main.run_dungeon(term, 'warden_manifold', {}, player_name='Slayer',
                            _dungeon=dungeon)


# ── structure & symmetry ──────────────────────────────────────────────────────

@pytest.mark.parametrize("seed", SEEDS)
def test_dimensions_and_anchors(seed):
    room = _room(seed)
    assert (room.rows, room.cols) == (_WM_ROWS, _WM_COLS)
    assert room.spawn_pos == _WM_SPAWN and room.exit_pos == _WM_EXIT
    assert room.par is None and room.budget == _WM_BUDGET, "boss: no keystroke par"
    w = _warden(room)
    assert w is not None and (w.row, w.col) == _WM_PODIUMS[0]
    assert w.edit_immune, "every operator must parry on the boss"
    assert w.tag == 'manifold', "exempts auto-summon AND the post-x random leap"
    assert w.max_hp == 4, "one x-window per round"
    assert room.cells[_WM_SEAL[0]][_WM_SEAL[1]] == CellType.WALL
    assert room.cells[_WM_GATE[0]][_WM_GATE[1]] == CellType.WALL


@pytest.mark.parametrize("seed", SEEDS)
def test_hall_is_mirrored_about_the_aisle(seed):
    """The aesthetics contract: columns, podiums, braziers, hearts and friezes
    all come in pairs mirrored about the processional aisle (row 8)."""
    room = _room(seed)
    mirror = lambda r: 2 * _WM_AXIS - r
    for group in (_WM_PODIUMS, _WM_BRAZIERS, _WM_HEARTS):
        cells = set(group)
        assert {(mirror(r), c) for (r, c) in cells} == cells, group
    for r in _WM_COLUMN_ROWS:
        assert mirror(r) in _WM_COLUMN_ROWS
        for c in _WM_COLUMN_COLS:
            assert room.cells[r][c] == CellType.WALL
            assert room.cells[mirror(r)][c] == CellType.WALL
    frieze_rows = [ru.row for ru in room.char_runs if ru.row in (1, 15)]
    assert 1 in frieze_rows and 15 in frieze_rows


@pytest.mark.parametrize("seed", SEEDS)
def test_brazier_rows_are_reflow_safe(seed):
    """One brazier per row, and the brazier rows carry NO other glyph anywhere
    east — a charwise paste open_gaps the whole BUFFER row (straight across
    the dividing wall), so any same-row glyph east of a paste would slide."""
    room = _room(seed)
    rows = [r for (r, _c) in _WM_BRAZIERS]
    assert len(rows) == len(set(rows)), "two braziers on one row shove each other"
    for (r, c) in _WM_BRAZIERS:
        east = [ru for ru in room.char_runs if ru.row == r and ru.col > c]
        assert not east, f"glyphs east of brazier {(r, c)} would be shoved: {east}"


@pytest.mark.parametrize("seed", SEEDS)
def test_warden_and_exit_unreachable_as_built(seed):
    """The niche walls seal the Warden (no x-grinding a sheltered boss) and the
    gate + seal close the hall and the pocket."""
    room = build_dungeon_warden_manifold(seed).rooms[0]      # private (mutating)
    seen, q = {room.spawn_pos}, deque([room.spawn_pos])
    while q:
        r, c = q.popleft()
        for dr, dc in ((0, 1), (0, -1), (1, 0), (-1, 0)):
            nb = (r + dr, c + dc)
            if nb not in seen and room.is_passable(*nb):
                seen.add(nb)
                q.append(nb)
    w = _warden(room)
    assert (w.row, w.col) not in seen, "the round-1 niche must be sealed"
    assert room.exit_pos not in seen, "the seal hides the exit"
    assert _WM_GATE not in seen, "the ritual gate starts shut"


@pytest.mark.parametrize("seed", SEEDS)
def test_line_jumps_never_reach_the_pocket(seed):
    room = build_dungeon_warden_manifold(seed).rooms[0]      # private (mutating)
    jumps = ([('G', 1, False), ('gg', 1, False), ('H', 1, False),
              ('M', 1, False), ('L', 1, False)]
             + [('G', n, True) for n in range(1, _WM_ROWS)])
    for motion, count, count_given in jumps:
        p = Player(row=room.spawn_pos[0], col=room.spawn_pos[1])
        apply_motion(p, motion, count, room, count_given=count_given)
        assert (p.row, p.col) != _WM_EXIT, f"{motion} reached the exit pocket"
        assert (p.row, p.col) not in _WM_PODIUMS, f"{motion} reached a niche"


# ── the opening ritual ────────────────────────────────────────────────────────

@pytest.mark.parametrize("seed", SEEDS)
def test_ritual_gate_draws_when_four_flames_burn(seed, monkeypatch):
    """Light the diamond through the real loop: the gate is wall until the
    fourth flame, then draws open (and the fuel rule guards every paste)."""
    dungeon = build_dungeon_warden_manifold(seed)
    room = dungeon.rooms[0]
    assert getattr(room, '_qm_chain', None), "the fuel rule must be active"
    ritual = ('ll' + 'yl' + '5k' + '5l' + 'P' + '4j' + '3l' + 'P'
              + 'jj' + 'P' + '4j' + '3h' + 'P')
    _drive(dungeon, ritual, monkeypatch)
    assert room.cells[_WM_GATE[0]][_WM_GATE[1]] == CellType.FLOOR
    flames = {(ru.row, ru.col) for ru in room.char_runs
              if _QM_FLAME in ru.symbols}
    assert set(_WM_BRAZIERS) <= flames, "all four braziers burn"


def test_flame_paste_blocked_off_brazier():
    room = _room(SEEDS[0])
    clip = {'linewise': False, 'rows': [{'width': 1, 'char_runs': [
        {'dcol': 0, 'symbols': (_QM_FLAME,), 'kind': 'flame'}]}]}
    floor = Player(row=8, col=6)                              # antechamber floor
    assert main._flame_paste_blocked(room, floor, clip, True, 1)
    on_brazier = Player(row=_WM_BRAZIERS[0][0], col=_WM_BRAZIERS[0][1])
    assert not main._flame_paste_blocked(room, on_brazier, clip, True, 1)


# ── the round machine ─────────────────────────────────────────────────────────

@pytest.mark.parametrize("seed", SEEDS)
def test_operators_parry_on_the_warden(seed):
    """edit_immune: a dd aimed at his row is REFUSED (the row holds an anchored
    occupant) and he survives any charwise sweep."""
    from engine.reflow import remove_row
    room = build_dungeon_warden_manifold(seed).rooms[0]      # private (mutating)
    w = _warden(room)
    assert not remove_row(room, w.row), "his row must refuse the collapse"
    from engine.operator import _delete_cols
    _delete_cols(room, w.row, 0, room.cols - 1)
    assert _warden(room) is not None, "a charwise sweep must parry too"


@pytest.mark.parametrize("seed", SEEDS)
def test_round1_break_staggers_and_strike_advances(seed, monkeypatch):
    """Break ward 1 through the real loop: the bolt draws (stagger), the x
    lands, and the press re-manifests him at podium 2 with ward 2 stamped."""
    dungeon = build_dungeon_warden_manifold(seed)
    room = dungeon.rooms[0]
    ritual = ('llyl' + '5k5lP' + '4j3lP' + 'jjP' + '4j3hP' + '5k4lll')
    r1 = 'kk' + 'll' + 'de' + 'j6lk' + 'de' + 'j5lk' + 'de'
    _drive(dungeon, ritual + r1, monkeypatch)
    pr, pc = _WM_PODIUMS[0]
    side = 1 if pr < _WM_AXIS else -1
    assert room.cells[pr + side][pc] == CellType.FLOOR, "the bolt draws on the break"
    assert main._wm_ward_broken(room, 1)

    dungeon = build_dungeon_warden_manifold(seed)
    room = dungeon.rooms[0]
    _drive(dungeon, ritual + r1 + 'kkhhkx', monkeypatch)
    w = _warden(room)
    assert w.hp == 3 and (w.row, w.col) == _WM_PODIUMS[1]
    assert room._wm_round == 2
    assert room.entity_at(w.row, w.col) is w, "move_entity must re-index the map"
    word2 = room._wm_word2
    assert not main._wm_ward_broken(room, 2), "ward 2 stamps warped"
    assert word2 not in main._wm_row_text(room, _WM_WARD2[0])


@pytest.mark.parametrize("seed", SEEDS)
def test_round3_one_D_erases_the_rank(seed, monkeypatch):
    """The signature image: a rank of false Wardens standing on the rot — ONE
    D shears text and copies together (hp=1 echoes die through the disguise)."""
    dungeon = build_dungeon_warden_manifold(seed)
    room = dungeon.rooms[0]
    letter = room._wm_word2[0]
    upto_r3 = (('llyl' + '5k5lP' + '4j3lP' + 'jjP' + '4j3hP' + '5k4lll')
               + 'kklldej6lkdej5lkde' + 'kkhhkx'
               + '4j10l3kx'
               + 'jjll' + 'r' + letter + 'w.w.w.' + '8hkkhhkx'
               + 'jjjjj29hjj')
    _drive(dungeon, upto_r3, monkeypatch)
    echoes = [e for e in room.entities if e.kind == 'goblin' and e.alive]
    assert len(echoes) == 4 and all(e.tag == 'echo' and e.hp == 1 for e in echoes)

    dungeon = build_dungeon_warden_manifold(seed)
    room = dungeon.rooms[0]
    _drive(dungeon, upto_r3 + 'D', monkeypatch)
    assert not [e for e in room.entities if e.kind == 'goblin' and e.alive], \
        "one D erases the whole rank like text"
    assert main._wm_ward_broken(room, 3)


# ── the full fight ────────────────────────────────────────────────────────────

@pytest.mark.parametrize("seed", SEEDS)
def test_full_fight_wins(seed, monkeypatch):
    """The canonical fight, key for key through run_dungeon: ritual, four
    rounds, four strikes, the seal, the exit. Deterministic by design."""
    dungeon = build_dungeon_warden_manifold(seed)
    room = dungeon.rooms[0]
    result = _drive(dungeon, _fight_script(room), monkeypatch, finish=':wq\r')
    assert result['won'], result
    assert _warden(room) is None
    assert not [e for e in room.entities if e.kind == 'goblin' and e.alive], \
        "every echo gutters when the press falls"
    sr, sc = room._wm_seal
    assert room.cells[sr][sc] == CellType.FLOOR


def test_curriculum_guard():
    """The boss teaches nothing; everything it demands is already known."""
    known = set(known_commands('warden_manifold'))
    for needed in ('d', 'D', 'r', 'dot', 'y', 'P', 'p', 'count', '$', 'G'):
        assert needed in known
    for absent in ('insert', 'c', 's', 'R', 'subst'):
        assert absent not in known
