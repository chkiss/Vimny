"""Tests for engine/motion.py: apply_motion, move_player, _cell_char, _fog_unreachable, _reveal_from."""
import pytest
from engine.world import Room, RoomType, CellType, Entity, CharRun
from engine.player import Player
from engine.motion import apply_motion, move_player, _fog_unreachable, _reveal_from, _cell_char

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
    room.spawn_pos = (3, 1)
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
    room.add_char_run(CharRun(row=3, col=2,  symbols=('∘', '∘'), kind='ancient'))
    room.add_char_run(CharRun(row=3, col=6,  symbols=('·',),     kind='verdant'))
    room.add_char_run(CharRun(row=3, col=9,  symbols=('∘',),     kind='ancient'))
    room.add_char_run(CharRun(row=3, col=13, symbols=('·',),     kind='verdant'))
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

    def test_blocked_by_fog_cell(self):
        room = _bare_room()
        room.fog_cells = {(3, 10)}
        p = _player(3, 9)
        result = move_player(p, 0, 1, room)
        assert result is False
        assert p.col == 9

    def test_allows_move_to_unfogged_cell(self):
        room = _bare_room()
        room.fog_cells = {(3, 11)}   # col 10 is clear
        p = _player(3, 9)
        assert move_player(p, 0, 1, room) is True
        assert p.col == 10

    def test_vertical_movement(self):
        room = _bare_room()
        p = _player(3, 5)
        assert move_player(p, -1, 0, room) is True
        assert p.row == 2

    def test_out_of_bounds_returns_false(self):
        room = _bare_room()
        p = _player(0, 0)
        assert move_player(p, -1, 0, room) is False


# ── _fog_unreachable ──────────────────────────────────────────────────────────

def _walled_room():
    """7×24 room split into two halves by a wall at col 12 with a door at (3,12)."""
    room = _bare_room()
    for r in range(1, ROWS - 1):
        room.cells[r][12] = CellType.WALL
    # Doorway at row 3, col 12
    room.cells[3][12] = CellType.FLOOR
    door = Entity(kind='door', row=3, col=12)
    room.add_entity(door)
    return room, door


class TestFogUnreachable:
    def test_no_doors_no_fog(self):
        room = _bare_room()
        _fog_unreachable(room, 3, 1)
        assert room.fog_cells == set()

    def test_door_creates_fog_for_far_side(self):
        room, door = _walled_room()
        _fog_unreachable(room, 3, 1)
        # All cols 13-22 on floor rows should be fogged
        assert (3, 15) in room.fog_cells
        assert (3, 22) in room.fog_cells
        # Door cell itself is visible (reachable but BFS stops there)
        assert (3, 12) not in room.fog_cells
        # Left side is clear
        assert (3, 5) not in room.fog_cells

    def test_locked_door_creates_fog(self):
        room = _bare_room()
        for r in range(1, ROWS - 1):
            room.cells[r][12] = CellType.WALL
        room.cells[3][12] = CellType.FLOOR
        room.add_entity(Entity(kind='locked_door', row=3, col=12))
        _fog_unreachable(room, 3, 1)
        assert (3, 15) in room.fog_cells
        assert (3, 12) not in room.fog_cells   # locked_door cell visible


class TestRevealFrom:
    def test_reveal_opens_far_room_after_door_removed(self):
        room, door = _walled_room()
        _fog_unreachable(room, 3, 1)
        assert (3, 15) in room.fog_cells
        room.kill_entity(door)
        _reveal_from(room, 3, 1)
        assert (3, 15) not in room.fog_cells

    def test_reveal_stops_at_remaining_door(self):
        room, door = _walled_room()
        # Add a second door at col 18
        for r in range(1, ROWS - 1):
            room.cells[r][18] = CellType.WALL
        room.cells[3][18] = CellType.FLOOR
        door2 = Entity(kind='door', row=3, col=18)
        room.add_entity(door2)
        _fog_unreachable(room, 3, 1)
        room.kill_entity(door)
        _reveal_from(room, 3, 1)
        # Cols 13-17 revealed; cols 19-22 still fogged
        assert (3, 15) not in room.fog_cells
        assert (3, 20) in room.fog_cells

    def test_reveal_noop_when_no_fog(self):
        room = _bare_room()
        _reveal_from(room, 3, 1)
        assert room.fog_cells == set()


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
        room.add_char_run(CharRun(row=3, col=5, symbols=('∘', '∘'), kind='ancient'))
        assert _cell_char(room, 3, 5) == '∘'

    def test_rune_second_symbol(self):
        room = _bare_room()
        room.add_char_run(CharRun(row=3, col=5, symbols=('∘', '·'), kind='ancient'))
        assert _cell_char(room, 3, 6) == '·'

    def test_exit_entity(self):
        room = _bare_room()
        room.add_entity(Entity(kind='exit', row=3, col=10))
        assert _cell_char(room, 3, 10) == '.'

    def test_door_entity(self):
        room = _bare_room()
        room.add_entity(Entity(kind='door', row=3, col=10))
        assert _cell_char(room, 3, 10) == '.'

    def test_entry_marker_entity(self):
        room = _bare_room()
        room.add_entity(Entity(kind='entry_marker', row=3, col=1))
        assert _cell_char(room, 3, 1) == '.'

    def test_unknown_entity(self):
        room = _bare_room()
        room.add_entity(Entity(kind='wanderer', row=3, col=5))
        assert _cell_char(room, 3, 5) == '.'


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
        # Fog cells at cols 12-22 block $ from going past col 11
        room.fog_cells = {(3, c) for c in range(12, 23)}
        p = _player(3, 5)
        apply_motion(p, '$', 1, room)
        assert p.col == 11  # rightmost passable col before fog boundary

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
        room.add_char_run(CharRun(row=3, col=3, symbols=('○', '○'), kind='void'))
        room.add_char_run(CharRun(row=3, col=8, symbols=('∘',), kind='ancient'))
        p = _player(3, 1)
        apply_motion(p, 'w', 1, room)
        assert p.col == 8  # void skipped; lands on ancient

    def test_w_returns_false_when_no_next_word(self):
        room = _bare_room()
        room.add_char_run(CharRun(row=3, col=3, symbols=('∘',), kind='ancient'))
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
        room.add_char_run(CharRun(row=3, col=5, symbols=('∘',), kind='ancient'))
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
        room.add_char_run(CharRun(row=3, col=5, symbols=('∘',), kind='ancient'))
        p = _player(3, 5)  # on the only rune's end
        assert apply_motion(p, 'e', 1, room) is False


# ── apply_motion: G gg ────────────────────────────────────────────────────────

class TestApplyMotionJumps:
    def test_G_jumps_to_last_passable_row(self):
        # bare G → last passable row (row 5 in a 7-row room with wall on row 6),
        # first non-blank column (col 1, leftmost passable, no runes in bare room)
        room = _bare_room()
        p = _player(3, 1)
        apply_motion(p, 'G', 1, room, count_given=False)
        assert (p.row, p.col) == (ROWS - 2, 1)

    def test_G_exit_pos_ignored(self):
        # bare G goes to last passable row regardless of exit_pos
        room = _bare_room()
        room.exit_pos = None
        p = _player(3, 5)
        apply_motion(p, 'G', 1, room, count_given=False)
        assert (p.row, p.col) == (ROWS - 2, 1)

    def test_gg_jumps_to_first_line(self):
        # bare gg → first passable row (row 1), leftmost col (no runes); ignores spawn_pos
        room = _bare_room()
        p = _player(5, 15)
        apply_motion(p, 'gg', 1, room, count_given=False)
        assert (p.row, p.col) == (1, 1)

    def test_gg_lands_on_first_rune_of_first_line(self):
        # row 1: cols 1-3 blank, rune at col 4 → first-non-blank is the rune col
        room = _bare_room()
        room.add_char_run(CharRun(row=1, col=4, symbols=('x',), kind='ancient'))
        room.rebuild_indexes()
        p = _player(5, 10)
        apply_motion(p, 'gg', 1, room, count_given=False)
        assert (p.row, p.col) == (1, 4)

    def test_gg_ignores_spawn_pos(self):
        # gg is buffer-relative, not spawn-relative (regression guard for the bug-loop)
        room = _bare_room()
        room.spawn_pos = (5, 10)
        p = _player(4, 8)
        apply_motion(p, 'gg', 1, room, count_given=False)
        assert (p.row, p.col) == (1, 1)

    def test_ngg_jumps_to_line_n(self):
        # {n}gg → line n, first non-blank — mirrors {n}G. Line 1 is the first standable
        # row (grid row 1 here, the top border isn't a line), so line 3 = grid row 3.
        room = _bare_room()
        p = _player(5, 10)
        apply_motion(p, 'gg', 3, room, count_given=True)
        assert (p.row, p.col) == (3, 1)


# ── apply_motion: ge gE backward word-end (Block E) ──────────────────────────

class TestApplyMotionBackwardWordEnd:
    # _rune_room row 3 ends: ∘∘@2-3→3, ·@6→6, ∘@9→9, ·@13→13 (all gap-separated)

    def test_ge_from_floor_lands_on_prev_word_end(self):
        room = _rune_room()
        p = _player(3, 15)
        apply_motion(p, 'ge', 1, room)
        assert p.col == 13  # end of · at col 13

    def test_ge_from_word_end_skips_to_previous(self):
        room = _rune_room()
        p = _player(3, 13)  # on ·@13 (its own end)
        apply_motion(p, 'ge', 1, room)
        assert p.col == 9   # end of ∘@9

    def test_ge_from_inside_skips_own_word(self):
        room = _rune_room()
        p = _player(3, 9)   # on ∘@9
        apply_motion(p, 'ge', 1, room)
        assert p.col == 6   # end of ·@6

    def test_ge_multi_symbol_word_end(self):
        room = _rune_room()
        p = _player(3, 6)   # on ·@6
        apply_motion(p, 'ge', 1, room)
        assert p.col == 3   # end of ∘∘ (spans 2-3)

    def test_ge_no_previous_word_no_move(self):
        room = _rune_room()
        p = _player(3, 3)   # end of the first word
        assert apply_motion(p, 'ge', 1, room) is False
        assert p.col == 3

    def test_count_ge_chains(self):
        room = _rune_room()
        p = _player(3, 15)
        apply_motion(p, 'ge', 2, room)
        assert p.col == 9   # 15→13→9

    def test_ge_does_not_land_on_void(self):
        room = _bare_room()
        room.add_char_run(CharRun(row=3, col=5, symbols=('○', '○'), kind='void'))
        p = _player(3, 9)
        assert apply_motion(p, 'ge', 1, room) is False  # void is not a word
        assert p.col == 9

    def test_gE_coalesces_adjacent_clusters(self):
        # WORD1 = ∘∘@2-3 + ·@4 (adjacent, end 4); gap; WORD2 = ∘@7 (end 7)
        room = _bare_room()
        room.add_char_run(CharRun(row=3, col=2, symbols=('∘', '∘'), kind='ancient'))
        room.add_char_run(CharRun(row=3, col=4, symbols=('·',),     kind='verdant'))
        room.add_char_run(CharRun(row=3, col=7, symbols=('∘',),     kind='ancient'))
        p = _player(3, 10)
        apply_motion(p, 'gE', 1, room)
        assert p.col == 7   # end of WORD2
        apply_motion(p, 'gE', 1, room)
        assert p.col == 4   # coalesced end of WORD1 (∘∘ + ·)


# ── apply_motion: H M L screen-relative rows (Batch 1) ───────────────────────

class TestApplyMotionScreenRows:
    # _bare_room: passable rows 1-5; M = middle = row 3.
    def test_H_goes_to_top_passable_row(self):
        room = _bare_room()
        p = _player(5, 10)
        apply_motion(p, 'H', 1, room)
        assert (p.row, p.col) == (1, 1)

    def test_L_goes_to_bottom_passable_row(self):
        room = _bare_room()
        p = _player(2, 10)
        apply_motion(p, 'L', 1, room)
        assert (p.row, p.col) == (5, 1)

    def test_M_goes_to_middle_row(self):
        room = _bare_room()
        p = _player(1, 5)
        apply_motion(p, 'M', 1, room)
        assert p.row == 3

    def test_M_lands_on_first_nonblank_rune_col(self):
        room = _rune_room()   # runes on row 3 start at col 2
        p = _player(1, 5)
        apply_motion(p, 'M', 1, room)
        assert (p.row, p.col) == (3, 2)

    def test_H_no_move_when_already_there(self):
        room = _bare_room()
        p = _player(1, 1)
        assert apply_motion(p, 'H', 1, room) is False


# ── apply_motion: % bracket match (Batch 1) ──────────────────────────────────

def _bracket_room():
    """row 3: ( @2  [ @4  ] @6  ) @8  — nested ( [ ] )."""
    room = _bare_room()
    for col, sym in ((2, '('), (4, '['), (6, ']'), (8, ')')):
        room.add_char_run(CharRun(row=3, col=col, symbols=(sym,), kind='ancient'))
    return room


class TestApplyMotionBracketMatch:
    def test_open_paren_to_close(self):
        room = _bracket_room()
        p = _player(3, 2)
        apply_motion(p, '%', 1, room)
        assert p.col == 8

    def test_close_paren_to_open(self):
        room = _bracket_room()
        p = _player(3, 8)
        apply_motion(p, '%', 1, room)
        assert p.col == 2

    def test_inner_bracket_pair(self):
        room = _bracket_room()
        p = _player(3, 4)   # '['
        apply_motion(p, '%', 1, room)
        assert p.col == 6   # ']'

    def test_from_floor_scans_right_to_first_bracket(self):
        room = _bracket_room()
        p = _player(3, 1)
        apply_motion(p, '%', 1, room)
        assert p.col == 8   # finds '(' @2, matches ')' @8

    def test_unmatched_no_move(self):
        room = _bare_room()
        room.add_char_run(CharRun(row=3, col=5, symbols=('(',), kind='ancient'))
        p = _player(3, 5)
        assert apply_motion(p, '%', 1, room) is False
        assert p.col == 5


# ── apply_motion: { } paragraph (Batch 1) ────────────────────────────────────

def _para_room():
    """Content on rows 1,2,4; blank passable rows 3 and 5."""
    room = _bare_room()
    for r in (1, 2, 4):
        room.add_char_run(CharRun(row=r, col=2, symbols=('∘',), kind='ancient'))
    return room


class TestApplyMotionParagraph:
    def test_next_paragraph_to_blank_row(self):
        room = _para_room()
        p = _player(1, 2)
        apply_motion(p, '}', 1, room)
        assert (p.row, p.col) == (3, 1)

    def test_next_paragraph_chains(self):
        room = _para_room()
        p = _player(1, 2)
        apply_motion(p, '}', 2, room)
        assert (p.row, p.col) == (5, 1)

    def test_prev_paragraph(self):
        room = _para_room()
        p = _player(4, 2)
        apply_motion(p, '{', 1, room)
        assert (p.row, p.col) == (3, 1)

    def test_brace_no_blank_below_no_move(self):
        room = _para_room()
        p = _player(5, 1)
        assert apply_motion(p, '}', 1, room) is False


# ── apply_motion: ( ) sentence (Batch 1) ─────────────────────────────────────

def _sentence_room():
    """row 3: 'ab.' @2-4, 'cd!' @6-8, 'ef' @10-11 → sentence starts 2, 6, 10."""
    room = _bare_room()
    room.add_char_run(CharRun(row=3, col=2,  symbols=('a', 'b', '.'), kind='ancient'))
    room.add_char_run(CharRun(row=3, col=6,  symbols=('c', 'd', '!'), kind='ancient'))
    room.add_char_run(CharRun(row=3, col=10, symbols=('e', 'f'),      kind='ancient'))
    return room


class TestApplyMotionSentence:
    def test_next_sentence(self):
        room = _sentence_room()
        p = _player(3, 2)
        apply_motion(p, ')', 1, room)
        assert p.col == 6

    def test_next_sentence_from_floor(self):
        room = _sentence_room()
        p = _player(3, 1)
        apply_motion(p, ')', 1, room)
        assert p.col == 2

    def test_prev_sentence_mid_sentence(self):
        room = _sentence_room()
        p = _player(3, 7)
        apply_motion(p, '(', 1, room)
        assert p.col == 6

    def test_prev_sentence_at_start_goes_previous(self):
        room = _sentence_room()
        p = _player(3, 6)
        apply_motion(p, '(', 1, room)
        assert p.col == 2

    def test_next_sentence_count(self):
        room = _sentence_room()
        p = _player(3, 1)
        apply_motion(p, ')', 2, room)
        assert p.col == 6

    def test_no_next_sentence_no_move(self):
        room = _sentence_room()
        p = _player(3, 10)
        assert apply_motion(p, ')', 1, room) is False


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

    def test_f_cannot_target_exit_entity(self):
        room = _rune_room()
        p = _player(3, 1)
        apply_motion(p, 'f', 1, room, target='E')
        assert p.col == 1  # exit no longer returns 'E' from _cell_char; no jump

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
        room.add_char_run(CharRun(row=4, col=5, symbols=('∘',), kind='ancient'))
        p = _player(3, 1)
        result = apply_motion(p, 'f', 1, room, target='∘')
        assert result is False  # rune is on a different row


# ── apply_motion: door entity not targetable by f+ ───────────────────────────

class TestApplyMotionColumnBar:
    """| — go to column n (1-indexed); bare | → column 1."""

    def test_bar_count_goes_to_column(self):
        # column 1 is the first standable col (grid col 1 here), so 10| → grid col 10
        room = _bare_room()
        p = _player(3, 1)
        apply_motion(p, '|', 10, room)          # 10| → col 10
        assert p.col == 10

    def test_bare_bar_goes_to_first_column(self):
        room = _bare_room()
        p = _player(3, 15)
        apply_motion(p, '|', 1, room)           # | → column 1 = col 0… but col 0 is wall
        assert p.col == 1                        # stops at first passable cell

    def test_bar_moves_left(self):
        room = _bare_room()
        p = _player(3, 18)
        apply_motion(p, '|', 6, room)           # 6| → col 6, moving left
        assert p.col == 6

    def test_bar_clamps_to_room_width(self):
        room = _bare_room()
        p = _player(3, 1)
        apply_motion(p, '|', 999, room)         # far past the right wall
        assert p.col == COLS - 2                 # last passable column

    def test_bar_stops_at_wall(self):
        room = _bare_room()
        # wall the interior at col 8: | past it cannot cross
        room.cells[3][8] = CellType.WALL
        room.rebuild_indexes()
        p = _player(3, 1)
        apply_motion(p, '|', 15, room)
        assert p.col == 7                        # stops one before the wall


class TestApplyMotionDoor:
    def test_f_plus_cannot_target_door(self):
        room = _bare_room()
        room.add_entity(Entity(kind='door', row=3, col=10))
        p = _player(3, 1)
        apply_motion(p, 'f', 1, room, target='+')
        assert p.col == 1  # door no longer returns '+' from _cell_char; no jump


# ── Word classes: pinned to REAL Vim (the north star) ────────────────────────
# Reference behavior captured from `vim -u NONE` (v8.2) probes, 2026-06-09:
#   a♠b cd   → w stops at charcols 2, 3, 5   (♠ is PUNCTUATION, its own word)
#   war☠den  → splits war|☠|den
#   a♠♥♦b    → the symbol run is ONE punctuation word
# Vim's utf_class marks the whole U+20A0–U+27FF block ("all kinds of symbols")
# as punctuation. A previous engine revision treated So-category symbols as
# word chars — this class exists so that can never silently regress.

class TestVimWordClasses:
    def test_game_symbols_are_punctuation_like_in_vim(self):
        from engine.motion import _is_word_char
        for sym in '♠☠†°§·⌘∞♯⚙⛧☘‽¶⁂≈♂⚀♝':
            assert not _is_word_char(sym), f'{sym!r} must be punctuation (vim utf_class)'
        for wc in 'a9_éÿ×':
            assert _is_word_char(wc), f'{wc!r} must be a word char (vim iskeyword)'

    def test_w_stops_on_a_symbol_between_letters(self):
        # vim: 'a♠b cd' → w lands on ♠, then b, then cd
        room = _bare_room()
        room.add_char_run(CharRun(row=3, col=2, symbols=('a', '♠', 'b'), kind='ember'))
        room.add_char_run(CharRun(row=3, col=6, symbols=('c', 'd'), kind='ember'))
        p = _player(3, 2)
        apply_motion(p, 'w', 1, room)
        assert p.col == 3                        # the ♠ — its own punctuation word
        apply_motion(p, 'w', 1, room)
        assert p.col == 4                        # then b
        apply_motion(p, 'w', 1, room)
        assert p.col == 6                        # then cd

    def test_e_takes_a_symbol_run_as_one_word(self):
        # vim: 'a♠♥♦b' → from a, w lands on ♠ and e runs to ♦ (one punct word)
        room = _bare_room()
        room.add_char_run(CharRun(row=3, col=2,
                                  symbols=('a', '♠', '♥', '♦', 'b'), kind='ember'))
        p = _player(3, 2)
        apply_motion(p, 'w', 1, room)
        assert p.col == 3
        apply_motion(p, 'e', 1, room)
        assert p.col == 5                        # end of the ♠♥♦ run

    def test_b_lands_on_trailing_subword_of_split_token(self):
        # vim: 'war☠den' splits — b from beyond lands on 'den', not 'war'
        room = _bare_room()
        room.add_char_run(CharRun(row=3, col=2,
                                  symbols=tuple('war☠den'), kind='ember'))
        p = _player(3, 12)
        apply_motion(p, 'b', 1, room)
        assert p.col == 6                        # 'den' — the trailing subword


class TestWordMotionVoidStarts:
    """Starting ON a void rune: a cluster TOUCHING the void is the same WORD
    (void runes are text, so there is no gap), so W skips past it to the NEXT
    word — while w lands on it (the small-word scans treat void as whitespace).
    Pinned by the word-motion refactor's differential fuzz."""

    def _void_room(self):
        room = _bare_room()
        room.add_char_run(CharRun(row=3, col=2,  symbols=('○', '○'), kind='void'))
        room.add_char_run(CharRun(row=3, col=4,  symbols=('a', 'b'), kind='ancient'))
        room.add_char_run(CharRun(row=3, col=9,  symbols=('z',),     kind='ember'))
        return room

    def test_W_from_void_skips_the_touching_word(self):
        room = self._void_room()
        p = _player(3, 3)                        # on the void; 'ab' touches at col 4
        apply_motion(p, 'W', 1, room)
        assert p.col == 9                        # 'ab' is the same WORD — skip to 'z'

    def test_w_from_void_lands_on_the_touching_word(self):
        room = self._void_room()
        p = _player(3, 3)
        apply_motion(p, 'w', 1, room)
        assert p.col == 4                        # w treats the void as whitespace

    def test_W_gap_void_blocks_the_leap_but_w_clears_it(self):
        room = _bare_room()
        room.add_char_run(CharRun(row=3, col=2, symbols=('a',), kind='ancient'))
        room.add_char_run(CharRun(row=3, col=5, symbols=('○',), kind='void'))
        room.add_char_run(CharRun(row=3, col=8, symbols=('z',), kind='ember'))
        p = _player(3, 2)
        assert apply_motion(p, 'W', 1, room) is False    # ○ in the gap stops W
        p2 = _player(3, 2)
        apply_motion(p2, 'w', 1, room)
        assert p2.col == 8                               # ...but w leaps over it
