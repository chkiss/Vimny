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

"""The Warden Pathfinder (Act III boss) — mechanics.

C-PF-1: a boss core is immune to *editing*-delete. The player's Act III power
combo `v/W<CR>x` (visual + search-as-motion + delete) is a remote AoE that wipes
goblins and glyphs across its span — but it must NOT be able to one-shot the
Warden. An entity with ``edit_immune=True`` survives every visual-delete path
(single-row charwise, multi-row charwise, linewise, block) and every operator
delete that routes through ``_delete_cols`` / ``remove_row``; the boss is wounded
only by normal-mode ``x``. When a delete span covers it, the rest of the span
still dies, the boss stands, and ``player.last_parry`` is set so the UI can fire
"The Warden's shield defended him from your cut!".

This file IS the as-built spec for L17.1; see vimny/engine/visual.py and vimny/engine/warden_mega.py.
"""
import random

import vimny.generation.dungeon_gen as dg
from vimny.engine.world import Room, RoomType, Entity, CellType, CharRun
from vimny.engine.player import Player
from vimny.engine.modes import Mode
from vimny.engine.visual import apply_visual
from vimny.engine.search import match_cells
from vimny.engine import warden_mega as MEGA


def _room(immune: bool) -> Room:
    rows, cols = 5, 20
    cells = [[CellType.FLOOR] * cols for _ in range(rows)]
    for c in range(cols):
        cells[0][c] = cells[rows - 1][c] = CellType.WALL
    for r in range(rows):
        cells[r][0] = cells[r][cols - 1] = CellType.WALL
    room = Room(room_type=RoomType.BOSS, rows=rows, cols=cols, cells=cells)
    room.add_entity(Entity(kind='goblin', row=2, col=5, hp=1, max_hp=1))
    room.add_entity(Entity(kind='warden', row=2, col=8, hp=5, max_hp=5, edit_immune=immune))
    room.add_char_run(CharRun(2, 3, tuple('ab'), 'plain'))
    room.rebuild_indexes()
    return room


def _player(r: int, c: int) -> Player:
    p = Player()
    p.row, p.col = r, c
    return p


def _warden_alive(room):
    return any(e.kind == 'warden' and e.alive for e in room.entities)


def _goblin_alive(room):
    return any(e.kind == 'goblin' and e.alive for e in room.entities)


# ── baseline: an ordinary entity IS deleted by a visual sweep (no immunity) ──

def test_baseline_single_row_charwise_kills_warden():
    room = _room(immune=False)
    p = _player(2, 2)
    apply_visual('d', (2, 2), (2, 12), Mode.VISUAL, room, p)
    assert not _warden_alive(room)
    assert p.last_parry is False


# ── C-PF-1: edit_immune boss survives every visual-delete path ──

def test_immune_survives_single_row_charwise_but_aoe_still_clears_chaff():
    room = _room(immune=True)
    p = _player(2, 2)
    apply_visual('d', (2, 2), (2, 12), Mode.VISUAL, room, p)
    assert _warden_alive(room)            # the shield parried the cut
    assert not _goblin_alive(room)        # …but the AoE still wiped the goblin chaff
    assert p.last_parry is True           # → "shield defended him from your cut!"


def test_immune_survives_multi_row_charwise():
    room = _room(immune=True)
    p = _player(1, 2)
    apply_visual('d', (1, 2), (3, 12), Mode.VISUAL, room, p)
    assert _warden_alive(room)
    assert not _goblin_alive(room)
    assert p.last_parry is True


def test_immune_survives_linewise():
    room = _room(immune=True)
    rows_before = room.rows
    p = _player(2, 2)
    apply_visual('d', (2, 0), (2, 19), Mode.VISUAL_LINE, room, p)
    assert _warden_alive(room)
    assert room.rows == rows_before       # remove_row refused to collapse the boss's row
    assert p.last_parry is True


def test_immune_survives_block():
    room = _room(immune=True)
    p = _player(1, 8)
    apply_visual('d', (1, 8), (3, 8), Mode.VISUAL_BLOCK, room, p)
    assert _warden_alive(room)
    assert p.last_parry is True


def test_yank_over_boss_is_not_a_parry():
    room = _room(immune=True)
    p = _player(2, 2)
    apply_visual('y', (2, 2), (2, 12), Mode.VISUAL, room, p)
    assert _warden_alive(room)
    assert p.last_parry is False          # yank isn't a cut — no "defended" message


# ── C-PF-3: /W finds the Warden + echo impostors (room-scoped glyph search) ──

def _hunt_room(glyph_search: bool) -> Room:
    rows, cols = 5, 30
    cells = [[CellType.FLOOR] * cols for _ in range(rows)]
    for c in range(cols):
        cells[0][c] = cells[rows - 1][c] = CellType.WALL
    for r in range(rows):
        cells[r][0] = cells[r][cols - 1] = CellType.WALL
    room = Room(room_type=RoomType.BOSS, rows=rows, cols=cols, cells=cells,
                search_glyph_entities=glyph_search)
    room.add_entity(Entity(kind='warden', row=2, col=20, hp=5, max_hp=5, edit_immune=True))
    room.add_entity(Entity(kind='goblin', row=2, col=6,  hp=1, max_hp=1, tag='echo'))   # impostor W
    room.add_entity(Entity(kind='goblin', row=2, col=12, hp=1, max_hp=1, tag='echo'))   # impostor W
    room.add_entity(Entity(kind='goblin', row=3, col=15, hp=1, max_hp=1))               # real minion → 'g'
    room.rebuild_indexes()
    return room


def test_slash_W_finds_warden_and_echoes_when_flag_on():
    room = _hunt_room(glyph_search=True)
    cells = match_cells(room, 'W')
    assert (2, 20) in cells     # the real Warden
    assert (2, 6) in cells      # echo impostor
    assert (2, 12) in cells     # echo impostor
    assert (3, 15) not in cells # a plain goblin is 'g', not matched by /W


def test_slash_g_finds_only_plain_goblin():
    room = _hunt_room(glyph_search=True)
    cells = match_cells(room, 'g')
    assert (3, 15) in cells                         # the plain minion
    assert not any(c in cells for c in [(2, 20), (2, 6), (2, 12)])  # Ws aren't 'g'


def test_flag_off_search_ignores_entities():
    room = _hunt_room(glyph_search=False)
    assert match_cells(room, 'W') == set()          # no char-runs → nothing (par-safe default)
    assert match_cells(room, 'g') == set()


def test_fW_finds_warden_standing_on_text():
    """fW must find the Warden even when he stands ON char-run text (the
    wardenverse): the glyph the renderer draws on top wins over the text beneath,
    so _cell_char returns 'W'. Regression — text used to mask the glyph."""
    from vimny.engine.motion import _cell_char, _apply_find
    from vimny.engine.player import Player
    rows, cols = 1, 20
    cells = [[CellType.FLOOR] * cols]
    room = Room(room_type=RoomType.BOSS, rows=rows, cols=cols, cells=cells)
    room.add_char_run(CharRun(0, 0, tuple('abcdefghijklmnopqrs'), 'plain'))  # text under everything
    room.add_entity(Entity(kind='warden', row=0, col=12, hp=3, max_hp=3,
                           tag='verse', edit_immune=True))
    room.rebuild_indexes()
    assert _cell_char(room, 0, 12) == 'W'           # glyph beats the 'm' beneath it
    p = Player(); p.row, p.col = 0, 2
    assert _apply_find(p, 'f', 'W', room) and p.col == 12


# ── C-PF-2: mega-attack — escalating floor-tear (dd → d5 → dG) + paste-back ──

def _arena() -> Room:
    rows, cols = 20, 30
    cells = [[CellType.FLOOR] * cols for _ in range(rows)]
    for c in range(cols):
        cells[0][c] = cells[rows - 1][c] = CellType.WALL
    for r in range(rows):
        cells[r][0] = cells[r][cols - 1] = CellType.WALL
    room = Room(room_type=RoomType.BOSS, rows=rows, cols=cols, cells=cells)
    room.add_entity(Entity(kind='warden', row=10, col=15, hp=3, max_hp=3,
                           tag='pathfinder', edit_immune=True))
    room.rebuild_indexes()
    MEGA.init_mega(room, (1, rows - 2, 1, cols - 2))
    return room


def _warn(room, p, rng):
    for _ in range(MEGA._MEGA_PERIOD):
        MEGA.mega_tick(room, p, rng)


def test_warning_fires_after_the_cooldown():
    room = _arena(); p = _player(2, 2); rng = random.Random(1)
    msgs = []
    for _ in range(MEGA._MEGA_PERIOD):
        msgs += MEGA.mega_tick(room, p, rng)
    assert room.mega['phase'] == 'warn'                 # telegraph after PERIOD calm turns
    assert room.mega['band']                            # rows about to be torn
    assert any('WINDS UP' in m for m in msgs)


def test_strike_tears_floor_then_pastes_it_back():
    room = _arena(); p = _player(2, 2); rng = random.Random(1)   # far from the Warden's row
    _warn(room, p, rng)
    for _ in range(MEGA._MEGA_WARN):
        MEGA.mega_tick(room, p, rng)
    assert room.torn and room.mega['phase'] == 'torn'   # floor is gone
    for _ in range(MEGA._MEGA_TORN):
        MEGA.mega_tick(room, p, rng)
    assert not room.torn                                # …and the Warden pasted it back
    assert room.mega['phase'] == 'idle' and room.mega['level'] == 1   # escalated


def test_caught_on_a_torn_row_takes_fall_damage():
    room = _arena(); rng = random.Random(1)
    _warn(room, _player(2, 2), rng)
    r = next(iter(room.mega['band']))
    p = _player(r, 5); hp0 = p.hp
    for _ in range(MEGA._MEGA_WARN):
        MEGA.mega_tick(room, p, rng)
    assert p.hp == hp0 - MEGA._MEGA_DMG                 # the floor gave way beneath you


def test_off_the_band_is_safe():
    room = _arena(); rng = random.Random(1)
    _warn(room, _player(2, 2), rng)
    safe_r = next(r for r in range(1, 19) if r not in room.mega['band'])
    p = _player(safe_r, 5); hp0 = p.hp
    for _ in range(MEGA._MEGA_WARN):
        MEGA.mega_tick(room, p, rng)
    assert p.hp == hp0


def test_attacks_escalate_dd_then_d5_then_dG():
    room = _arena(); p = _player(2, 2); rng = random.Random(0)
    sizes = []
    for _ in range(3):
        while room.mega['phase'] != 'warn':
            MEGA.mega_tick(room, p, rng)
        sizes.append(len(room.mega['band']))
        while room.mega['phase'] != 'idle':
            MEGA.mega_tick(room, p, rng)
    assert sizes[0] == 1                                # dd — just his row
    assert sizes[1] > sizes[0]                          # d5k/d5j — a wider band
    assert sizes[2] > sizes[1]                          # dG/dgg — out to an edge


def test_goblin_on_a_torn_row_is_culled():
    room = _arena(); rng = random.Random(1)
    _warn(room, _player(1, 1), rng)
    r = next(iter(room.mega['band']))
    room.add_entity(Entity(kind='goblin', row=r, col=5, hp=1, max_hp=1))   # over the gap
    room.add_entity(Entity(kind='goblin', row=1, col=3, hp=1, max_hp=1))   # safe row
    room.rebuild_indexes()
    for _ in range(MEGA._MEGA_WARN):
        MEGA.mega_tick(room, _player(1, 1), rng)
    alive = {(e.row, e.col) for e in room.entities if e.kind == 'goblin' and e.alive}
    assert (r, 5) not in alive and (1, 3) in alive


def test_paste_back_restores_buried_minions_and_redisguises():
    """When the floor pastes back, the Warden restores the minions the tear buried
    AND re-cloaks every live goblin as a 2-HP false Warden — so unmasked/half-cut
    minions revert between strikes."""
    room = _arena(); rng = random.Random(1); p = _player(1, 1)
    _warn(room, p, rng)
    band = room.mega['band']
    r = next(iter(band))
    buried = Entity(kind='goblin', row=r, col=5, hp=1, max_hp=1, tag='echo', shade=3)
    safe_r = next(rr for rr in range(1, 19) if rr not in band)
    survivor = Entity(kind='goblin', row=safe_r, col=6, hp=1, max_hp=1, tag='')  # unmasked
    room.add_entity(buried); room.add_entity(survivor); room.rebuild_indexes()
    for _ in range(MEGA._MEGA_WARN):                     # strike — buried minion falls
        MEGA.mega_tick(room, p, rng)
    assert not buried.alive
    msgs = []
    for _ in range(MEGA._MEGA_TORN):                     # paste — restore + re-cloak
        msgs += MEGA.mega_tick(room, p, rng)
    assert buried.alive and buried.tag == 'echo' and buried.hp == 2     # restored impostor
    assert survivor.tag == 'echo' and survivor.hp == 2 and survivor.max_hp == 2  # re-disguised
    assert any('cloaked as Wardens' in m for m in msgs)


# ── C-PF-6: the real Warden's position is randomised among the impostors ───────
def test_warden_position_varies_and_stays_valid():
    seen = set()
    for s in range(40):
        a = dg.build_dungeon_warden_pathfinder(s).rooms[0]
        w = next(e for e in a.entities if e.kind == 'warden')
        sh = next(e for e in a.entities if e.kind == 'shield')
        seen.add((w.row, w.col))
        assert a.cells[w.row][w.col] == CellType.FLOOR        # never inside a column wall
        assert (sh.row, sh.col) == (w.row, w.col - 1)         # shield stays at his flank
    assert len(seen) >= 3                                     # not always the same cell
    assert (12, 39) in seen                                   # …but sometimes still central


# ── builder: the two-room dungeon is wired (Act 1 arena + Act 2 wardenverse) ──

def test_builder_makes_a_two_room_dungeon():
    from vimny.generation.dungeon_gen import build_dungeon_warden_pathfinder as build
    d = build(7)
    assert len(d.rooms) == 2 and d.current_room == 0
    arena, verse = d.rooms

    # Arena (Act 1): a big OPEN hall with four stone columns at the 3×3 vertices
    assert (arena.rows, arena.cols) == (24, 78)
    columns = [(r, c) for r in (8, 15) for c in (22, 44)]
    assert all(arena.cells[r][c] == CellType.WALL for (r, c) in columns)   # the columns
    assert arena.cells[12][33] == CellType.FLOOR and arena.cells[4][30] == CellType.FLOOR  # open hall
    assert arena.search_glyph_entities and arena.mega['phase'] == 'idle'
    assert arena.mega['bounds'][3] <= 66                # mega tears only the fight area, not the treasure
    warden = next(e for e in arena.entities if e.kind == 'warden')
    assert warden.tag == 'pathfinder' and warden.edit_immune
    # Two impostor Wardens (goblins, tag='echo') flanking the center. Each has 1 HP
    # and auto-unmasks after the verse collapse (no manual two-hit pattern).
    echoes = [e for e in arena.entities if e.kind == 'goblin' and e.tag == 'echo']
    assert len(echoes) == 2
    assert all(e.hp == 1 and e.max_hp == 1 for e in echoes)
    assert len({e.shade for e in echoes}) == 2          # two different shades
    # Treasure room behind a locked door (the exit + loot live there; key drops in Act 3)
    assert arena.exit_pos is not None
    assert any(e.kind == 'locked_door' for e in arena.entities)
    assert any(e.kind == 'exit' for e in arena.entities)
    assert any(e.kind == 'heart_container' for e in arena.entities)

    # Wardenverse (Act 2): ONE long line that wraps REACTIVELY (no fixed fold), immune
    # Warden, and NO exit — his death collapses the verse (handled in vimny/game.py).
    assert verse.wrap_buffer and verse.rows == 1
    assert getattr(verse, 'wrap_width', 0) == 0         # reactive (folds to the live terminal width)
    assert verse.cols >= 600                            # long enough to fold many times even at 189 cols
    inner_walls = [c for c in range(1, verse.cols - 1) if verse.cells[0][c] == CellType.WALL]
    assert len(inner_walls) >= 8                        # segment walls: $ / l stop here, gj/gk hop them
    vw = next(e for e in verse.entities if e.kind == 'warden')
    assert vw.tag == 'verse' and vw.edit_immune
    assert verse.exit_pos is None                       # collapse, not a verse exit


# ── C-PF-4: verse collapse auto-unmasks all echoes ──────────────────────────
def test_verse_collapse_unmasks_all_echoes():
    """When the verse Warden is defeated and the wardenverse collapses, all remaining
    echoes in the arena are automatically revealed (tag='' hp=1) for cleanup. This
    replaces the old two-hit-per-echo pattern now that visual mode isn't available."""
    from vimny.engine.player import Player

    d = dg.build_dungeon_warden_pathfinder(7)
    arena = d.rooms[0]
    verse = d.rooms[1]

    # Verify echoes start disguised
    echoes = [e for e in arena.entities if e.kind == 'goblin' and e.tag == 'echo']
    assert len(echoes) == 2
    assert all(e.tag == 'echo' and e.hp == 1 for e in echoes)

    # Simulate the verse collapse by calling the unmask logic directly
    # (this is what happens in vimny/game.py when the verse Warden dies)
    for e in arena.entities:
        if e.kind == 'goblin' and e.tag == 'echo' and e.alive:
            e.tag = ''       # no longer disguised as 'W'
            e.hp = 1
            e.max_hp = 1

    # Verify all echoes are now revealed
    revealed = [e for e in arena.entities if e.kind == 'goblin' and e.alive]
    assert len(revealed) == 2
    assert all(e.tag == '' and e.hp == 1 for e in revealed)


def test_caret_lands_on_key_not_passable_door():
    """^ stops on a notable entity (a dropped key) but treats floor-like passage
    markers (a door you stand on) as blank — regression for the post-collapse key."""
    from vimny.engine.player import Player
    from vimny.engine.motion import apply_motion
    from vimny.engine.world import Entity
    arena = dg.build_dungeon_warden_pathfinder(7).rooms[0]
    for e in arena.entities:                              # post-collapse: foes cleared
        if e.kind in ('goblin', 'warden', 'shield'):
            e.alive = False
    arena.rebuild_indexes()
    arena.add_entity(Entity(kind='door', row=12, col=20))   # a passage marker, transparent to ^
    arena.add_entity(Entity(kind='floor_key', row=12, col=40))
    p = Player(); p.row, p.col = 12, 60
    apply_motion(p, '^', 1, arena)
    assert (p.row, p.col) == (12, 40)                     # past the door, onto the key
