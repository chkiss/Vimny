"""Tests for engine/motion.py: apply_motion, move_player, _cell_char, _update_fog."""
import pytest
from engine.world import Room, RoomType, CellType, Entity, RuneCluster
from engine.player import Player
from engine.motion import apply_motion, move_player, _update_fog, _cell_char

# ── Shared room fixtures ──────────────────────────────────────────────────────

ROWS, COLS = 7, 24

def _bare_room():
    """7×24 room, walls on border, open floor inside. No runes or entities."""
    room = Room(room_type=RoomType.ENTRY, rows=ROWS, cols=COLS)
    room.cells = [
        [CellType.FLOOR if (0 < r < ROWS - 1 and 0 < c < COLS - 1) else CellType.WALL
         for c in range(COLS)]
        for r in range(ROWS)
    ]
    room.entry    = (3, 1)
    room.exit_pos = (3, 20)
    room.rebuild_indexes()
    return room


def _rune_room():
    """_bare_room plus a standard layout of rune clusters and an exit entity on row 3.

    Row 3 layout (passable cols 1-22):
      col 2-3: ancient ∘∘
      col 6:   verdant ·
      col 9:   ancient ∘
      col 13:  verdant ·
      col 20:  exit entity (char 'E')
    """
    room = _bare_room()
    room.add_rune(RuneCluster(row=3, col=2,  symbols=('∘', '∘'), kind='ancient'))
    room.add_rune(RuneCluster(row=3, col=6,  symbols=('·',),     kind='verdant'))
    room.add_rune(RuneCluster(row=3, col=9,  symbols=('∘',),     kind='ancient'))
    room.add_rune(RuneCluster(row=3, col=13, symbols=('·',),     kind='verdant'))
    room.add_entity(Entity(kind='exit', row=3, col=20))
    room.exit_pos = (3, 20)
    return room


def _player(row=3, col=1):
    return Player(row=row, col=col)


# ── move_player ───────────────────────────────────────────────────────────────

class TestMovePlayer:
    def test_moves_into_open_floor(self):
        room = _bare_room()
        p = _player(3, 5)
        assert move_player(p, 0, 1, room) is True
        assert p.col == 6

    def test_blocked_by_wall(self):
        room = _bare_room()
        p = _player(3, 1)
        result = move_player(p, 0, -1, room)  # col 0 is wall
        assert result is False
        assert p.col == 1

    def test_blocked_by_fog(self):
        room = _bare_room()
        room.fog_col = 10
        p = _player(3, 9)
        result = move_player(p, 0, 1, room)  # col 10 >= fog_col
        assert result is False
        assert p.col == 9

    def test_allows_move_up_to_fog_boundary(self):
        room = _bare_room()
        room.fog_col = 10
        p = _player(3, 8)
        assert move_player(p, 0, 1, room) is True  # col 9 < fog_col
        assert p.col == 9

    def test_vertical_movement(self):
        room = _bare_room()
        p = _player(3, 5)
        assert move_player(p, -1, 0, room) is True
        assert p.row == 2

    def test_out_of_bounds_returns_false(self):
        room = _bare_room()
        p = _player(0, 0)
        assert move_player(p, -1, 0, room) is False


# ── _update_fog ───────────────────────────────────────────────────────────────

class TestUpdateFog:
    def test_sets_fog_to_first_door_col_plus_one(self):
        room = _bare_room()
        room.add_entity(Entity(kind='door', row=3, col=10))
        _update_fog(room)
        assert room.fog_col == 11

    def test_multiple_doors_uses_leftmost(self):
        room = _bare_room()
        room.add_entity(Entity(kind='door', row=3, col=10))
        room.add_entity(Entity(kind='door', row=3, col=15))
        _update_fog(room)
        assert room.fog_col == 11

    def test_dead_door_ignored(self):
        room = _bare_room()
        e = Entity(kind='door', row=3, col=10)
        room.add_entity(e)
        room.kill_entity(e)
        _update_fog(room)
        assert room.fog_col == -1

    def test_no_doors_clears_fog(self):
        room = _bare_room()
        room.fog_col = 10
        _update_fog(room)
        assert room.fog_col == -1


# ── _cell_char ────────────────────────────────────────────────────────────────

class TestCellChar:
    def test_floor_cell(self):
        room = _bare_room()
        assert _cell_char(room, 3, 5) == '.'

    def test_wall_cell(self):
        room = _bare_room()
        assert _cell_char(room, 0, 0) == '#'

    def test_rune_first_symbol(self):
        room = _bare_room()
        room.add_rune(RuneCluster(row=3, col=5, symbols=('∘', '∘'), kind='ancient'))
        assert _cell_char(room, 3, 5) == '∘'

    def test_rune_second_symbol(self):
        room = _bare_room()
        room.add_rune(RuneCluster(row=3, col=5, symbols=('∘', '·'), kind='ancient'))
        assert _cell_char(room, 3, 6) == '·'

    def test_exit_entity(self):
        room = _bare_room()
        room.add_entity(Entity(kind='exit', row=3, col=10))
        assert _cell_char(room, 3, 10) == 'E'

    def test_door_entity(self):
        room = _bare_room()
        room.add_entity(Entity(kind='door', row=3, col=10))
        assert _cell_char(room, 3, 10) == '+'

    def test_entry_marker_entity(self):
        room = _bare_room()
        room.add_entity(Entity(kind='entry_marker', row=3, col=1))
        assert _cell_char(room, 3, 1) == '@'

    def test_unknown_entity(self):
        room = _bare_room()
        room.add_entity(Entity(kind='wanderer', row=3, col=5))
        assert _cell_char(room, 3, 5) == '?'


# ── apply_motion: basic hjkl ─────────────────────────────────────────────────

class TestApplyMotionHJKL:
    def test_l_moves_right(self):
        room = _bare_room()
        p = _player(3, 5)
        assert apply_motion(p, 'l', 1, room) is True
        assert p.col == 6

    def test_h_moves_left(self):
        room = _bare_room()
        p = _player(3, 5)
        assert apply_motion(p, 'h', 1, room) is True
        assert p.col == 4

    def test_j_moves_down(self):
        room = _bare_room()
        p = _player(3, 5)
        assert apply_motion(p, 'j', 1, room) is True
        assert p.row == 4

    def test_k_moves_up(self):
        room = _bare_room()
        p = _player(3, 5)
        assert apply_motion(p, 'k', 1, room) is True
        assert p.row == 2

    def test_l_blocked_by_wall_returns_false(self):
        room = _bare_room()
        p = _player(3, 22)  # col 23 is wall
        assert apply_motion(p, 'l', 1, room) is False
        assert p.col == 22

    def test_count_l_moves_n_steps(self):
        room = _bare_room()
        p = _player(3, 1)
        apply_motion(p, 'l', 5, room)
        assert p.col == 6

    def test_count_l_stops_at_wall(self):
        room = _bare_room()
        p = _player(3, 20)
        apply_motion(p, 'l', 10, room)  # only 2 cols of floor left
        assert p.col == 22


# ── apply_motion: line motions 0 $ ^ ─────────────────────────────────────────

class TestApplyMotionLineBoundary:
    def test_zero_goes_to_leftmost_passable(self):
        room = _bare_room()
        p = _player(3, 15)
        apply_motion(p, '0', 1, room)
        assert p.col == 1

    def test_zero_from_leftmost_no_move(self):
        room = _bare_room()
        p = _player(3, 1)
        assert apply_motion(p, '0', 1, room) is False
        assert p.col == 1

    def test_dollar_goes_to_rightmost_passable(self):
        room = _bare_room()
        p = _player(3, 5)
        apply_motion(p, '$', 1, room)
        assert p.col == 22

    def test_dollar_respects_fog(self):
        room = _bare_room()
        room.fog_col = 12
        p = _player(3, 5)
        apply_motion(p, '$', 1, room)
        assert p.col == 11  # rightmost col < fog_col

    def test_caret_jumps_to_first_rune_start(self):
        room = _rune_room()
        p = _player(3, 15)
        apply_motion(p, '^', 1, room)
        assert p.col == 2  # first rune (∘∘) starts at col 2

    def test_caret_from_floor_left_of_rune(self):
        room = _rune_room()
        p = _player(3, 1)
        apply_motion(p, '^', 1, room)
        assert p.col == 2

    def test_caret_no_rune_on_row_stays_put(self):
        room = _bare_room()
        p = _player(3, 10)
        result = apply_motion(p, '^', 1, room)
        # no rune → target = left = 1, which differs from current 10
        assert p.col == 1


# ── apply_motion: w b e word motions ─────────────────────────────────────────

class TestApplyMotionWordMotions:
    def test_w_from_floor_jumps_to_first_rune(self):
        room = _rune_room()
        p = _player(3, 1)
        apply_motion(p, 'w', 1, room)
        assert p.col == 2  # first rune start (∘∘ at col 2)

    def test_w_from_inside_cluster_jumps_past_it(self):
        room = _rune_room()
        p = _player(3, 2)  # on ∘∘ cluster start
        apply_motion(p, 'w', 1, room)
        assert p.col == 6  # next rune: verdant · at col 6

    def test_w_skips_void_rune(self):
        room = _bare_room()
        room.add_rune(RuneCluster(row=3, col=3, symbols=('○', '○'), kind='void'))
        room.add_rune(RuneCluster(row=3, col=8, symbols=('∘',), kind='ancient'))
        p = _player(3, 1)
        apply_motion(p, 'w', 1, room)
        assert p.col == 8  # void skipped; lands on ancient

    def test_w_returns_false_when_no_next_word(self):
        room = _bare_room()
        room.add_rune(RuneCluster(row=3, col=3, symbols=('∘',), kind='ancient'))
        p = _player(3, 3)  # on the only rune; no next word
        assert apply_motion(p, 'w', 1, room) is False

    def test_count_w_chains(self):
        room = _rune_room()
        p = _player(3, 1)
        apply_motion(p, 'w', 3, room)
        assert p.col == 9  # 1→2→6→9

    def test_b_from_middle_of_cluster_goes_to_start(self):
        room = _rune_room()
        p = _player(3, 3)  # inside ∘∘ at col 2-3
        apply_motion(p, 'b', 1, room)
        assert p.col == 2

    def test_b_from_start_of_cluster_goes_to_prev(self):
        room = _rune_room()
        p = _player(3, 6)  # on · at col 6
        apply_motion(p, 'b', 1, room)
        assert p.col == 2  # ∘∘ cluster at col 2

    def test_b_returns_false_when_no_prev_word(self):
        room = _bare_room()
        room.add_rune(RuneCluster(row=3, col=5, symbols=('∘',), kind='ancient'))
        p = _player(3, 5)  # on the only rune
        assert apply_motion(p, 'b', 1, room) is False

    def test_e_from_floor_jumps_to_end_of_first_rune(self):
        room = _rune_room()
        p = _player(3, 1)
        apply_motion(p, 'e', 1, room)
        assert p.col == 3  # end of ∘∘ (spans 2-3)

    def test_e_from_start_of_cluster_jumps_to_its_end(self):
        room = _rune_room()
        p = _player(3, 2)  # start of ∘∘ at col 2-3
        apply_motion(p, 'e', 1, room)
        assert p.col == 3

    def test_e_from_end_of_cluster_jumps_to_next_end(self):
        room = _rune_room()
        p = _player(3, 3)  # end of ∘∘
        apply_motion(p, 'e', 1, room)
        assert p.col == 6  # end of · at col 6 (single symbol)

    def test_e_returns_false_when_no_next_word(self):
        room = _bare_room()
        room.add_rune(RuneCluster(row=3, col=5, symbols=('∘',), kind='ancient'))
        p = _player(3, 5)  # on the only rune's end
        assert apply_motion(p, 'e', 1, room) is False


# ── apply_motion: G gg ────────────────────────────────────────────────────────

class TestApplyMotionJumps:
    def test_G_jumps_to_exit_pos(self):
        room = _bare_room()
        p = _player(3, 1)
        apply_motion(p, 'G', 1, room)
        assert (p.row, p.col) == room.exit_pos

    def test_G_no_exit_does_nothing(self):
        room = _bare_room()
        room.exit_pos = None
        p = _player(3, 5)
        apply_motion(p, 'G', 1, room)
        assert (p.row, p.col) == (3, 5)

    def test_gg_jumps_to_entry(self):
        room = _bare_room()
        p = _player(5, 15)
        apply_motion(p, 'gg', 1, room)
        assert (p.row, p.col) == room.entry


# ── apply_motion: f F t T find-char motions ──────────────────────────────────

class TestApplyMotionFindChar:
    def test_f_finds_first_occurrence_forward(self):
        room = _rune_room()
        p = _player(3, 1)
        apply_motion(p, 'f', 1, room, target='∘')
        assert p.col == 2

    def test_f_finds_second_occurrence_from_inside_cluster(self):
        room = _rune_room()
        p = _player(3, 4)  # past ∘∘, scanning forward finds ∘ at col 9
        apply_motion(p, 'f', 1, room, target='∘')
        assert p.col == 9

    def test_f_targets_exit_entity_char(self):
        room = _rune_room()
        p = _player(3, 1)
        apply_motion(p, 'f', 1, room, target='E')
        assert p.col == 20

    def test_f_no_target_found_no_move(self):
        room = _bare_room()
        p = _player(3, 5)
        result = apply_motion(p, 'f', 1, room, target='∘')
        assert result is False
        assert p.col == 5

    def test_f_target_none_no_move(self):
        room = _rune_room()
        p = _player(3, 1)
        result = apply_motion(p, 'f', 1, room, target=None)
        assert result is False

    def test_F_finds_first_occurrence_backward(self):
        room = _rune_room()
        p = _player(3, 15)
        apply_motion(p, 'F', 1, room, target='∘')
        assert p.col == 9  # rightmost ∘ before col 15

    def test_F_backward_from_col_5(self):
        room = _rune_room()
        p = _player(3, 5)
        apply_motion(p, 'F', 1, room, target='∘')
        assert p.col == 3  # ∘∘ cluster: col 3 is the second ∘ (still < 5)

    def test_t_stops_one_before_target(self):
        room = _rune_room()
        p = _player(3, 4)  # scanning forward from col 4, finds ∘ at col 9
        apply_motion(p, 't', 1, room, target='∘')
        assert p.col == 8  # one before col 9

    def test_T_stops_one_after_target(self):
        room = _rune_room()
        p = _player(3, 15)  # scanning backward, finds ∘ at col 9
        apply_motion(p, 'T', 1, room, target='∘')
        assert p.col == 10  # one after col 9

    def test_count_f_hops_multiple_occurrences(self):
        room = _rune_room()
        p = _player(3, 1)
        apply_motion(p, 'f', 2, room, target='∘')
        # First f∘ → col 2; second f∘ → col 3 (still inside ∘∘ cluster)
        assert p.col == 3

    def test_f_stops_at_wall(self):
        room = _bare_room()
        # put a rune on row 4, player on row 3 — f only scans current row
        room.add_rune(RuneCluster(row=4, col=5, symbols=('∘',), kind='ancient'))
        p = _player(3, 1)
        result = apply_motion(p, 'f', 1, room, target='∘')
        assert result is False  # rune is on a different row


# ── apply_motion: door entity for f+ ─────────────────────────────────────────

class TestApplyMotionDoor:
    def test_f_plus_finds_door(self):
        room = _bare_room()
        room.add_entity(Entity(kind='door', row=3, col=10))
        p = _player(3, 1)
        apply_motion(p, 'f', 1, room, target='+')
        assert p.col == 10
