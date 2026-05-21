"""Dummy dungeon completeness and admin editability.

Invariant: every CellType, entity kind, and rune kind used in the game must be
present in the dummy dungeon so the admin can see and practice with each one.
Every cell type must also be placeable via paste; obstacle types (WALL, WATER)
must additionally survive a cut-then-paste round-trip.

When you add a new CellType, entity kind, or rune kind:
  1. Add it to the relevant constant below.
  2. Place at least one instance of it in build_dungeon_dummy().
  3. If it is an obstacle type (impassable, admin-removable), add it to CUTTABLE_TYPES.
"""
import pytest
from engine.world import CellType
from engine.editor import _ed_cut, _ed_subst, _ed_paste
from generation.dungeon_gen import build_dungeon_dummy

SEED = 42

# ── Source-of-truth sets — update these when new kinds are introduced ─────────

EXPECTED_ENTITY_KINDS = {
    'entry_marker', 'exit', 'door', 'dynamite',
    'wanderer',
    'chest', 'chest_key', 'chest_scroll',
    'locked_door',
    'goblin', 'warden',
}
EXPECTED_RUNE_KINDS   = {'ancient', 'verdant', 'void', 'ember'}

# Cell types where _ed_cut should return a clip and leave FLOOR behind.
# Structural floor types (FLOOR, CORRIDOR) are pasteable but not cuttable.
CUTTABLE_TYPES = {CellType.WALL, CellType.WATER, CellType.WOOD_WALL}


# ── Presence ──────────────────────────────────────────────────────────────────

def test_all_cell_types_present():
    """Every CellType member must appear at least once in the dummy room's cell grid."""
    room = build_dungeon_dummy(SEED).room
    present = {ct for row in room.cells for ct in row}
    missing = [ct.name for ct in CellType if ct not in present]
    assert not missing, (
        f"CellType(s) {missing} absent from dummy dungeon — "
        "add at least one cell of each type so the admin can see and practice with it"
    )


def test_all_entity_kinds_present():
    room = build_dungeon_dummy(SEED).room
    present = {e.kind for e in room.entities if e.alive}
    missing = sorted(EXPECTED_ENTITY_KINDS - present)
    assert not missing, (
        f"Entity kind(s) {missing} absent from dummy dungeon — "
        "add an instance to build_dungeon_dummy() and to EXPECTED_ENTITY_KINDS above"
    )


def test_all_rune_kinds_present():
    room = build_dungeon_dummy(SEED).room
    present = {ru.kind for ru in room.runes}
    missing = sorted(EXPECTED_RUNE_KINDS - present)
    assert not missing, (
        f"Rune kind(s) {missing} absent from dummy dungeon — "
        "add an instance to build_dungeon_dummy() and to EXPECTED_RUNE_KINDS above"
    )


def test_no_unexpected_entity_kinds():
    """Guard the other direction: new entity kinds are noticed and added to the set."""
    room = build_dungeon_dummy(SEED).room
    present = {e.kind for e in room.entities if e.alive}
    unexpected = sorted(present - EXPECTED_ENTITY_KINDS)
    assert not unexpected, (
        f"Entity kind(s) {unexpected} found in dummy dungeon but not in "
        "EXPECTED_ENTITY_KINDS — add them to the constant in this test file"
    )


def test_no_unexpected_rune_kinds():
    room = build_dungeon_dummy(SEED).room
    present = {ru.kind for ru in room.runes}
    unexpected = sorted(present - EXPECTED_RUNE_KINDS)
    assert not unexpected, (
        f"Rune kind(s) {unexpected} found in dummy dungeon but not in "
        "EXPECTED_RUNE_KINDS — add them to the constant in this test file"
    )


# ── Editability: paste (all cell types) ──────────────────────────────────────

@pytest.mark.parametrize("ct", list(CellType), ids=lambda ct: ct.name)
def test_all_cell_types_are_pasteable(ct):
    """Every CellType must be placeable via _ed_paste (used by admin 'p' command)."""
    room = build_dungeon_dummy(SEED).room
    r, c = 3, 3  # interior floor cell
    item = {'type': 'cell', 'cell_type': ct}
    _ed_paste(room, r, c, [item])
    assert room.cells[r][c] == ct, f"CellType.{ct.name} not correctly set by _ed_paste"


# ── Editability: cut → paste round-trip (obstacle types only) ─────────────────

@pytest.mark.parametrize("ct", sorted(CUTTABLE_TYPES, key=lambda x: x.name))
def test_cuttable_types_survive_round_trip(ct):
    """x cuts the cell to FLOOR and returns a clip; p restores it."""
    room = build_dungeon_dummy(SEED).room
    r, c = 3, 3
    room.cells[r][c] = ct

    clip = _ed_cut(room, r, c)
    assert clip is not None,                   f"{ct.name}: _ed_cut returned None"
    assert clip['type'] == 'cell'
    assert clip['cell_type'] == ct,            f"{ct.name}: clip carries wrong cell_type"
    assert room.cells[r][c] == CellType.FLOOR, f"{ct.name}: cell should be FLOOR after cut"

    _ed_paste(room, r, c, [clip])
    assert room.cells[r][c] == ct,             f"{ct.name}: cell not restored after paste"


def test_floor_cut_returns_none():
    """FLOOR is not an obstacle; _ed_cut on an empty floor cell returns None."""
    room = build_dungeon_dummy(SEED).room
    assert _ed_cut(room, 3, 3) is None


def test_corridor_cut_returns_none():
    """CORRIDOR is structural floor; _ed_cut returns None (use paste to place it)."""
    room = build_dungeon_dummy(SEED).room
    r, c = 3, 3
    room.cells[r][c] = CellType.CORRIDOR
    assert _ed_cut(room, r, c) is None


# ── Editability: _ed_subst cycle covers all cuttable types ───────────────────

def test_subst_cycle_visits_all_cuttable_types():
    """Pressing s repeatedly from FLOOR must visit every type in CUTTABLE_TYPES."""
    room = build_dungeon_dummy(SEED).room
    r, c = 3, 3
    room.cells[r][c] = CellType.FLOOR

    seen = set()
    for _ in range(len(CellType) * 2):
        _ed_subst(room, r, c)
        seen.add(room.cells[r][c])
        if room.cells[r][c] == CellType.FLOOR:
            break

    missing = sorted(CUTTABLE_TYPES - seen, key=lambda x: x.name)
    assert not missing, (
        f"_ed_subst cycle never visited {[ct.name for ct in missing]} — "
        "add them to _SUBST_CYCLE in engine/editor.py"
    )


def test_subst_cycle_returns_to_floor():
    """The s cycle must be closed — repeated presses return to FLOOR."""
    room = build_dungeon_dummy(SEED).room
    r, c = 3, 3
    room.cells[r][c] = CellType.FLOOR

    for _ in range(len(CellType) * 2):
        _ed_subst(room, r, c)
        if room.cells[r][c] == CellType.FLOOR:
            return  # cycle closed

    pytest.fail("_ed_subst cycle never returned to FLOOR")
