"""The Warden Pathfinder (L17.1, Act III boss) — mechanics.

C-PF-1: a boss core is immune to *editing*-delete. The player's Act III power
combo `v/W⏎x` (visual + search-as-motion + delete) is a remote AoE that wipes
goblins and glyphs across its span — but it must NOT be able to one-shot the
Warden. An entity with ``edit_immune=True`` survives every visual-delete path
(single-row charwise, multi-row charwise, linewise, block) and every operator
delete that routes through ``_delete_cols`` / ``remove_row``; the boss is wounded
only by normal-mode ``x``. When a delete span covers it, the rest of the span
still dies, the boss stands, and ``player.last_parry`` is set so the UI can fire
"The Warden's shield defended him from your cut!".

See blueprints/act_3.md (L17.1) and engine/visual.py.
"""
from engine.world import Room, RoomType, Entity, CellType, CharRun
from engine.player import Player
from engine.modes import Mode
from engine.visual import apply_visual
from engine.search import match_cells


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
