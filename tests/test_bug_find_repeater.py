"""The Find Repeater — lives on f/F/t/T and repeats with ;/,.

Personality defined in agents/bug_testers.md.
"""
from engine.world import Room, RoomType, CellType, Entity, CharRun
from engine.player import Player
from engine.motion import apply_motion


def _bare_room(rows=7, cols=40):
    room = Room(room_type=RoomType.ENTRY, rows=rows, cols=cols)
    room.cells = [
        [CellType.FLOOR if (0 < r < rows - 1 and 0 < c < cols - 1) else CellType.WALL
         for c in range(cols)]
        for r in range(rows)
    ]
    room.spawn_pos    = (3, 1)
    room.exit_pos = (3, 38)
    room.fog_cells = set()
    room.rebuild_indexes()
    return room


def _goblin_at(room, col, row=3):
    g = Entity(kind='goblin', row=row, col=col, max_hp=1, ai='chase')
    room.add_entity(g)
    return g


def _char_run_at(room, col, symbol='∘', row=3):
    ru = CharRun(row=row, col=col, symbols=(symbol,), kind='ancient')
    room.char_runs.append(ru)
    room.rebuild_indexes()
    return ru


# ── ; and , with no prior f ───────────────────────────────────────────────────

def test_semicolon_with_no_last_f_does_nothing():
    """; with player.last_f == None must not move the player."""
    room = _bare_room()
    player = Player(row=3, col=5)
    assert player.last_f is None

    moved = apply_motion(player, ';', 1, room)

    assert not moved, "; must return False when last_f is None"
    assert player.col == 5


def test_comma_with_no_last_f_does_nothing():
    """, with player.last_f == None must not move the player."""
    room = _bare_room()
    player = Player(row=3, col=5)

    moved = apply_motion(player, ',', 1, room)

    assert not moved, ", must return False when last_f is None"
    assert player.col == 5


# ── f finds target and sets last_f ───────────────────────────────────────────

def test_f_finds_goblin_character():
    """f{g} must jump to the first goblin in the row."""
    room = _bare_room()
    _goblin_at(room, col=10)
    player = Player(row=3, col=1)

    moved = apply_motion(player, 'f', 1, room, target='g')

    assert moved
    assert player.col == 10


def test_f_sets_last_f():
    """Successful f must update player.last_f = (motion, target)."""
    room = _bare_room()
    _goblin_at(room, col=10)
    player = Player(row=3, col=1)

    apply_motion(player, 'f', 1, room, target='g')

    assert player.last_f == ('f', 'g'), f"expected last_f=('f','g'), got {player.last_f}"


# ── ; repeats forward find ────────────────────────────────────────────────────

def test_semicolon_repeats_f_find():
    """; after f{g} must find the next goblin in the same direction."""
    room = _bare_room()
    _goblin_at(room, col=10)
    _goblin_at(room, col=20)
    player = Player(row=3, col=1)

    apply_motion(player, 'f', 1, room, target='g')
    assert player.col == 10

    moved = apply_motion(player, ';', 1, room)

    assert moved
    assert player.col == 20, f"; should advance to col 20, got {player.col}"


# ── , reverses find ───────────────────────────────────────────────────────────

def test_comma_reverses_to_F():
    """, after f{g} must reverse using F{g} (backward scan)."""
    room = _bare_room()
    _goblin_at(room, col=5)
    _goblin_at(room, col=10)
    _goblin_at(room, col=20)
    player = Player(row=3, col=1)

    apply_motion(player, 'f', 1, room, target='g')   # → col 5
    apply_motion(player, ';', 1, room)                # → col 10

    moved = apply_motion(player, ',', 1, room)

    assert moved
    assert player.col == 5, f", should go back to col 5, got {player.col}"


# ── t: just-before target ─────────────────────────────────────────────────────

def test_t_lands_one_before_target():
    """t{∘} must land at target_col - 1, not on the rune itself."""
    room = _bare_room()
    _char_run_at(room, col=10, symbol='∘')
    player = Player(row=3, col=1)

    moved = apply_motion(player, 't', 1, room, target='∘')

    assert moved
    assert player.col == 9, f"t should land at col 9 (one before 10), got {player.col}"


def test_T_lands_one_after_target():
    """T{∘} (backward) must land at target_col + 1."""
    room = _bare_room()
    _char_run_at(room, col=5, symbol='∘')
    player = Player(row=3, col=15)

    moved = apply_motion(player, 'T', 1, room, target='∘')

    assert moved
    assert player.col == 6, f"T should land at col 6 (one after 5), got {player.col}"


def test_t_adjacent_target_does_not_move():
    """t{∘} where target is at player.col+1 would put dest at player.col — must not move."""
    room = _bare_room()
    _char_run_at(room, col=2, symbol='∘')
    player = Player(row=3, col=1)

    # t wants dest = 2 - 1 = 1 = player.col → no move
    moved = apply_motion(player, 't', 1, room, target='∘')

    assert not moved, "t should not move when target is directly adjacent"
    assert player.col == 1


# ── f scan stops at wall ──────────────────────────────────────────────────────

def test_f_scan_stops_at_wall():
    """f must not jump past a wall cell."""
    room = _bare_room()
    room.cells[3][15] = CellType.WALL
    _goblin_at(room, col=20)
    player = Player(row=3, col=1)

    moved = apply_motion(player, 'f', 1, room, target='g')

    assert not moved, "f must not find goblin beyond a wall"
    assert player.col == 1


def test_F_scan_stops_at_wall_going_backward():
    """F must not jump past a wall cell when scanning backward."""
    room = _bare_room()
    room.cells[3][10] = CellType.WALL
    _goblin_at(room, col=5)
    player = Player(row=3, col=20)

    moved = apply_motion(player, 'F', 1, room, target='g')

    assert not moved, "F must not find goblin beyond a wall (scanning backward)"
    assert player.col == 20


# ── F backward find ───────────────────────────────────────────────────────────

def test_F_backward_find_works():
    """F{g} must jump backward to the nearest goblin."""
    room = _bare_room()
    _goblin_at(room, col=5)
    player = Player(row=3, col=15)

    moved = apply_motion(player, 'F', 1, room, target='g')

    assert moved
    assert player.col == 5


# ── count-f ───────────────────────────────────────────────────────────────────

def test_count_2_f_finds_second_occurrence():
    """2f{g} with two goblins must land on the second one."""
    room = _bare_room()
    _goblin_at(room, col=5)
    _goblin_at(room, col=10)
    player = Player(row=3, col=1)

    moved = apply_motion(player, 'f', 2, room, target='g')

    assert moved
    assert player.col == 10, f"2f should land at col 10, got {player.col}"


# ── ; does NOT update last_f ──────────────────────────────────────────────────

def test_semicolon_does_not_update_last_f():
    """; must not overwrite player.last_f, so subsequent , still reverses correctly."""
    room = _bare_room()
    _goblin_at(room, col=5)
    _goblin_at(room, col=10)
    _goblin_at(room, col=20)
    player = Player(row=3, col=1)

    apply_motion(player, 'f', 1, room, target='g')   # → col 5; last_f = ('f','g')
    apply_motion(player, ';', 1, room)                # → col 10; last_f must stay ('f','g')

    assert player.last_f == ('f', 'g'), (
        f"; must not update last_f, expected ('f','g'), got {player.last_f}"
    )

    # Verify , can still reverse back to col 5
    moved = apply_motion(player, ',', 1, room)
    assert moved
    assert player.col == 5
