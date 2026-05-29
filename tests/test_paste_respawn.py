"""Paste from the unnamed register: cut letters lay back down, and cut creatures
respawn live and hostile — all through one Vim register (player.registers['"']).

The cut/paste wiring lives in run_dungeon's keystroke loop, so these tests target
the engine-reachable contract it leans on: entity_clip + op_paste (the creature
round-trip) and _clip_from_cut_runes (the letter round-trip)."""
import pytest
from engine.world import Room, RoomType, CellType, Entity, RuneCluster
from engine.player import Player
from engine.operator import entity_clip, op_paste
from main import _clip_from_cut_runes, _enemy_tick, _PASTE_SPAWN_MSG

ROWS, COLS = 7, 30


def _bare_room():
    room = Room(room_type=RoomType.COMBAT, rows=ROWS, cols=COLS)
    room.cells = [
        [CellType.FLOOR if (0 < r < ROWS - 1 and 0 < c < COLS - 1) else CellType.WALL
         for c in range(COLS)]
        for r in range(ROWS)
    ]
    room.spawn_pos = (3, 1)
    room.exit_pos  = (3, COLS - 2)
    room.rebuild_indexes()
    return room


def _slain(kind, **kw):
    """A creature as it is when killed (what the combat handler clips)."""
    e = Entity(kind=kind, row=3, col=5, **kw)
    e.alive = False
    e.hp    = 0
    return e


def _rune_item(sym, col, kind='ancient'):
    """A cut letter as `x` produces it (single-symbol rune at a column)."""
    return {'type': 'rune', 'rune': RuneCluster(3, col, (sym,), kind)}


# ── cut creature → clip → paste respawns it live & hostile ──────────────────────

def test_paste_revives_cut_goblin_live_and_hostile():
    room   = _bare_room()
    player = Player(row=3, col=5)
    assert op_paste(room, player, entity_clip(_slain('goblin', max_hp=1, ai='chase', ai_speed=1)),
                    before=False)                          # p → col 6
    g = room.entity_at(3, 6)
    assert g and g.kind == 'goblin' and g.alive and g.hp == g.max_hp == 1 and g.ai == 'chase'
    assert player.col == 5, 'cursor must never land the player on the pasted creature'


def test_clip_is_reusable_and_spawns_are_independent():
    """The register isn't consumed by paste (vim-faithful), and each paste is a
    fresh creature — so you can loose several goblins from one kill."""
    room   = _bare_room()
    player = Player(row=3, col=5)
    clip   = entity_clip(_slain('goblin', max_hp=1, ai='chase'))
    op_paste(room, player, clip, before=False)             # col 6
    player.col = 10
    op_paste(room, player, clip, before=False)             # col 11
    a, b = room.entity_at(3, 6), room.entity_at(3, 11)
    assert a and b and a.uid != b.uid and a.alive and b.alive


def test_pasted_goblin_chases_player():
    room   = _bare_room()
    player = Player(row=3, col=1)
    op_paste(room, player, entity_clip(_slain('goblin', max_hp=1, ai='chase', ai_speed=1)),
             before=False)                                 # pasted at col 2
    g = room.entity_at(3, 2)
    assert g is not None and g.alive
    player.col = 6                                         # player walks off; goblin gives chase
    _enemy_tick(room, player)
    assert g.col > 2, 'the respawned goblin must step toward the player'


def test_pasted_goblin_is_killable_again():
    room   = _bare_room()
    player = Player(row=3, col=5)
    op_paste(room, player, entity_clip(_slain('goblin', max_hp=1, ai='chase')), before=False)
    g = room.entity_at(3, 6)
    g.hp -= 1
    assert g.hp <= 0


# ── cut letter → clip → paste lays it back ───────────────────────────────────────

def test_paste_cut_letter_after_cursor():
    room   = _bare_room()
    player = Player(row=3, col=5)
    clip   = _clip_from_cut_runes([_rune_item('z', 5)], base_col=5)
    assert op_paste(room, player, clip, before=False)      # p → col 6
    ru = room.rune_at(3, 6)
    assert ru is not None and ru.symbols == ('z',)


def test_cut_letter_clip_preserves_column_gaps():
    # 'a' at col 5 and 'b' at col 7 (gap at 6) → dcol 0 and 2
    clip   = _clip_from_cut_runes([_rune_item('a', 5), _rune_item('b', 7)], base_col=5)
    dcols  = sorted(rd['dcol'] for rd in clip['rows'][0]['runes'])
    assert dcols == [0, 2]


def test_runes_only_clip_pastes_without_entities_key():
    """Regression: a clip with no 'entities' key (the d/dw path) must paste cleanly."""
    room   = _bare_room()
    player = Player(row=3, col=5)
    clip   = {'linewise': False,
              'rows': [{'width': 1, 'runes': [{'dcol': 0, 'symbols': ('q',), 'kind': 'ancient'}]}]}
    assert op_paste(room, player, clip, before=False)
    assert room.rune_at(3, 6) is not None


def test_creature_spawn_messages_cover_the_combat_kinds():
    assert set(_PASTE_SPAWN_MSG) == {'goblin', 'warden', 'shield'}
