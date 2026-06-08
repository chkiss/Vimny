"""The Operator's Vault (L18) — the first {operator}{motion} level (delete).

Six snaked single-row corridors, each cleared by one d-variant against a chasing
goblin; the sixth kill opens the vault. Structure + a full executed solve through
the real run_dungeon loop (answer == par, no damage, all goblins down).
"""
import pytest
from blessed import Terminal
from blessed.keyboard import Keystroke

import main
import generation.dungeon_gen as dg
from engine.world import CellType
import render.colors as C


def _room(seed=7):
    return dg.build_dungeon_operators_vault(seed).rooms[0]


# ── builder structure ────────────────────────────────────────────────────────
def test_six_corridors_each_with_a_chasing_goblin():
    room = _room()
    assert (room.rows, room.cols) == (24, 60)
    for r in dg._OV_CORR_ROWS:                       # each corridor is open floor 2..57
        assert room.cells[r][2] == CellType.FLOOR and room.cells[r][57] == CellType.FLOOR
    gobs = [e for e in room.entities if e.kind == 'goblin']
    assert len(gobs) == 6
    assert all(e.ai == 'chase' for e in gobs)        # normal (chasing) behaviour
    assert {e.row for e in gobs} == set(dg._OV_CORR_ROWS)   # one per corridor


def test_connectors_snake_and_do_not_form_a_bypass_shaft():
    room = _room()
    # the rows BETWEEN corridors are wall except at the single alternating connector
    assert room.cells[4][57] == CellType.FLOOR and room.cells[4][2] == CellType.WALL   # C1→C2 right
    assert room.cells[7][2] == CellType.FLOOR and room.cells[7][57] == CellType.WALL   # C2→C3 left
    assert room.cells[16][57] == CellType.FLOOR and room.cells[16][2] == CellType.WALL # C5→C6 right


def test_vault_is_sealed_and_fogged_until_opened():
    room = _room()
    assert any(e.kind == 'locked_door' for e in room.entities)
    assert any(e.kind == 'heart_container' for e in room.entities)
    assert any(e.kind == 'chest_scroll' for e in room.entities)
    assert room.exit_pos == (20, 13)
    assert room.exit_pos in room.fog_cells           # treasure hidden behind the sealed door


def test_par_and_budget():
    room = _room()
    assert room.par == 35 and room.budget == 49 and room.answer.strip()


# ── executed solve ───────────────────────────────────────────────────────────
def test_answer_solves_the_vault(monkeypatch):
    """Driving the answer through the real loop reaches the exit at exactly par,
    unharmed, with every goblin cut down and the vault door opened."""
    C.init(Terminal())
    d = dg.build_dungeon_operators_vault(7)
    room = d.rooms[0]

    state = {}

    class _Win(Exception):
        pass

    def _winsig(term, iw, dungeon, player):
        state['pos'] = (player.row, player.col)
        state['hp'] = player.hp
        raise _Win()

    monkeypatch.setattr(main, '_fireworks_animation', _winsig)
    cap = {}
    monkeypatch.setattr(main, 'render_all',
                        lambda term, dn, pl, bg, message='', *a, **k: cap.update(budget=bg))

    keys = [ch for tok in room.answer.split() for ch in tok]
    it = iter(keys + [''] * 6)
    term = Terminal()
    monkeypatch.setattr(term, 'inkey', lambda *a, **k: Keystroke(next(it, '')))

    with pytest.raises(_Win):
        main.run_dungeon(term, 'operators_vault', {}, player_name='admin', _dungeon=d)

    assert state['pos'] == room.exit_pos             # reached the exit
    assert state['hp'] == 6                           # unharmed — goblins cut down at range
    assert cap['budget'].spent == room.par            # solved in exactly par keystrokes
    assert not any(e.alive for e in room.entities if e.kind == 'goblin')
    assert getattr(room, 'vault_open', False)
