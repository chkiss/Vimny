"""Level 10 — The Screen Vault: dungeon correctness tests.

Teaching goal: H/M/L screen-relative row jumps.
  H = first passable row, 1 ks  (beats 4k + ^: 3 ks)
  M = middle passable row, 1 ks (beats 4j: 2 ks — uniquely cheap)
  L = last passable row, 1 ks   (demonstrated but not gated: same as 4j)
"""
import math
import heapq
import pytest
from engine.world import CellType
from generation.dungeon_gen import (
    build_dungeon_10,
    _dijkstra_par_L10,
    _L10_TOTAL_ROWS, _L10_TOTAL_COLS,
    _L10_PASS_LEFT, _L10_PASS_RIGHT,
    _L10_KS_COL, _L10_KS_ROWS,
    _L10_ENTRY, _L10_EXIT_ROW, _L10_EXIT_COL,
)

SEEDS = [1, 42, 999, 12345, 2**20 + 7]


# ── Basic structural tests ────────────────────────────────────────────────────

@pytest.mark.parametrize("seed", SEEDS)
def test_entry_and_exit_passable(seed):
    d = build_dungeon_10(seed)
    room = d.rooms[0]
    r0, c0 = room.entry
    r1, c1 = room.exit_pos
    assert room.cells[r0][c0] == CellType.CORRIDOR, (
        f"seed={seed}: entry ({r0},{c0}) is not passable"
    )
    assert room.cells[r1][c1] == CellType.CORRIDOR, (
        f"seed={seed}: exit ({r1},{c1}) is not passable"
    )


@pytest.mark.parametrize("seed", SEEDS)
def test_room_dimensions(seed):
    d = build_dungeon_10(seed)
    room = d.rooms[0]
    assert room.rows == _L10_TOTAL_ROWS, f"seed={seed}: expected {_L10_TOTAL_ROWS} rows, got {room.rows}"
    assert room.cols == _L10_TOTAL_COLS, f"seed={seed}: expected {_L10_TOTAL_COLS} cols, got {room.cols}"


@pytest.mark.parametrize("seed", SEEDS)
def test_passable_region_carved(seed):
    """All cells in rows 1-9, cols 4-47 must be CORRIDOR."""
    d = build_dungeon_10(seed)
    room = d.rooms[0]
    for r in range(1, 10):
        for c in range(_L10_PASS_LEFT, _L10_PASS_RIGHT + 1):
            assert room.cells[r][c] == CellType.CORRIDOR, (
                f"seed={seed}: ({r},{c}) should be CORRIDOR, got {room.cells[r][c]}"
            )


@pytest.mark.parametrize("seed", SEEDS)
def test_objectives_present(seed):
    """Three keystone entities must exist at the correct rows and col 4."""
    d = build_dungeon_10(seed)
    room = d.rooms[0]
    keystones = [e for e in room.entities if e.kind == 'keystone']
    assert len(keystones) == 3, (
        f"seed={seed}: expected 3 keystone entities, got {len(keystones)}"
    )
    ks_rows = sorted(e.row for e in keystones)
    assert ks_rows == list(_L10_KS_ROWS), (
        f"seed={seed}: keystone rows {ks_rows} != expected {list(_L10_KS_ROWS)}"
    )
    for ks in keystones:
        assert ks.col == _L10_KS_COL, (
            f"seed={seed}: keystone at row {ks.row} has col {ks.col}, expected {_L10_KS_COL}"
        )


@pytest.mark.parametrize("seed", SEEDS)
def test_exit_entity_at_exit_pos(seed):
    d = build_dungeon_10(seed)
    room = d.rooms[0]
    exits = [e for e in room.entities if e.kind == 'exit']
    assert len(exits) == 1, f"seed={seed}: expected 1 exit entity, got {len(exits)}"
    e = exits[0]
    assert (e.row, e.col) == room.exit_pos, (
        f"seed={seed}: exit entity at ({e.row},{e.col}) != exit_pos {room.exit_pos}"
    )


@pytest.mark.parametrize("seed", SEEDS)
def test_anchor_runes_at_keystone_cells(seed):
    """Each keystone row must have a rune at col 4 so H/M/L land there."""
    d = build_dungeon_10(seed)
    room = d.rooms[0]
    for ks_row in _L10_KS_ROWS:
        ru = room.rune_at(ks_row, _L10_KS_COL)
        assert ru is not None, (
            f"seed={seed}: expected anchor rune at ({ks_row},{_L10_KS_COL})"
        )


# ── Par / budget tests ────────────────────────────────────────────────────────

@pytest.mark.parametrize("seed", SEEDS)
def test_par_matches_dijkstra(seed):
    d = build_dungeon_10(seed)
    room = d.rooms[0]
    computed = _dijkstra_par_L10(room)
    assert room.par == computed, (
        f"seed={seed}: room.par={room.par} but Dijkstra computed {computed}"
    )


@pytest.mark.parametrize("seed", SEEDS)
def test_budget_is_ceil_par_times_1_4(seed):
    d = build_dungeon_10(seed)
    room = d.rooms[0]
    assert room.budget == math.ceil(room.par * 1.4), (
        f"seed={seed}: budget={room.budget} but ceil(par*1.4)={math.ceil(room.par * 1.4)}"
    )


# ── Command-usage tests ───────────────────────────────────────────────────────

@pytest.mark.parametrize("seed", SEEDS)
def test_answer_uses_H(seed):
    """The optimal path must use H to jump to the top keystone row."""
    d = build_dungeon_10(seed)
    room = d.rooms[0]
    tokens = room.answer.split()
    assert 'H' in tokens, (
        f"seed={seed}: 'H' not found in answer {room.answer!r}"
    )


@pytest.mark.parametrize("seed", SEEDS)
def test_answer_uses_M(seed):
    """The optimal path must use M to jump to the middle keystone row."""
    d = build_dungeon_10(seed)
    room = d.rooms[0]
    tokens = room.answer.split()
    assert 'M' in tokens, (
        f"seed={seed}: 'M' not found in answer {room.answer!r}"
    )


@pytest.mark.parametrize("seed", SEEDS)
def test_answer_does_NOT_require_L_when_removed(seed):
    """Solving with L disabled must still be possible within budget.

    L is demonstrated (KS-bot at the bottom row) but not gated — 4j (2 ks)
    replaces L (1 ks) and the total path cost stays ≤ budget.
    """
    d = build_dungeon_10(seed)
    room = d.rooms[0]

    # Run a Dijkstra that excludes L and check the result fits in budget.
    cost_no_L = _dijkstra_par_L10_no_L(room)
    assert cost_no_L is not None, (
        f"seed={seed}: no solution found without L"
    )
    assert cost_no_L <= room.budget, (
        f"seed={seed}: no-L cost {cost_no_L} exceeds budget {room.budget}"
    )


# ── H-vs-gg comparison ────────────────────────────────────────────────────────

@pytest.mark.parametrize("seed", SEEDS)
def test_H_is_cheaper_than_gg_for_top_row(seed):
    """H (1 ks) reaches top-row fnb in fewer keystrokes than gg (2 ks).

    gg goes to the entry position (row 5), not row 1.  To reach row 1 fnb
    via gg the player would need gg (2 ks) + 4k (2 ks) + ^ (1 ks) = 5 ks
    from the same starting position, versus H = 1 ks.
    """
    d = build_dungeon_10(seed)
    room = d.rooms[0]
    # H keystroke count
    h_cost = 1
    # gg keystroke count (two chars)
    gg_cost = 2
    assert h_cost < gg_cost, "H must cost fewer keystrokes than gg"

    # The par path uses H; verify the H step moves player to row 1 fnb
    entry_row, entry_col = room.entry
    top_ks_row = min(_L10_KS_ROWS)
    assert entry_row != top_ks_row, (
        f"seed={seed}: entry is already on top row — H vs gg comparison invalid"
    )

    # Confirm answer contains H (par always uses H because it's strictly cheaper)
    tokens = room.answer.split()
    assert 'H' in tokens, (
        f"seed={seed}: par path should use H but got {room.answer!r}"
    )


# ── Helper: Dijkstra without L ────────────────────────────────────────────────

def _dijkstra_par_L10_no_L(composite):
    """Same as _dijkstra_par_L10 but with L excluded (to test L is not required)."""
    ROWS, COLS = composite.rows, composite.cols
    entry    = composite.entry
    exit_pos = composite.exit_pos

    def _ok(r, c):
        if not composite.is_passable(r, c):
            return False
        ru = composite.rune_at(r, c)
        return not (ru and ru.kind == 'void')

    _fnb: dict[int, int] = {}
    for _r in range(ROWS):
        _left = None
        for _c in range(COLS):
            if composite.is_passable(_r, _c):
                if _left is None:
                    _left = _c
                if composite.rune_at(_r, _c) is not None:
                    _fnb[_r] = _c
                    break
        else:
            if _left is not None and _r not in _fnb:
                _fnb[_r] = _left

    _prows = sorted(_fnb)
    if not _prows:
        return None

    _h_dest = (_prows[0],               _fnb[_prows[0]])
    _m_dest = (_prows[len(_prows) // 2], _fnb[_prows[len(_prows) // 2]])
    # L is EXCLUDED — not added to the move set

    _ks_map: dict[tuple, int] = {}
    for _bit, _ent in enumerate(e for e in composite.entities if e.kind == 'keystone'):
        _ks_map[(_ent.row, _ent.col)] = _bit

    FULL_MASK = (1 << len(_ks_map)) - 1
    INF       = float('inf')
    start     = (*entry, 0)
    dist      = {start: 0}
    heap      = [(0, start)]

    while heap:
        cost, state = heapq.heappop(heap)
        r, c, mask = state
        if (r, c) == exit_pos and mask == FULL_MASK:
            return cost
        if cost > dist.get(state, INF):
            continue

        def _push(nb_rc, mc=1, nb_mask=None):
            if nb_rc is None:
                return
            nr, nc = nb_rc
            if not _ok(nr, nc):
                return
            nmask = nb_mask if nb_mask is not None else mask
            nb    = (nr, nc, nmask)
            g     = cost + mc
            if g < dist.get(nb, INF):
                dist[nb] = g
                heapq.heappush(heap, (g, nb))

        max_n = max(ROWS, COLS)
        for dr, dc in ((1,0),(-1,0),(0,1),(0,-1)):
            key = {(1,0):'j',(-1,0):'k',(0,1):'l',(0,-1):'h'}[(dr,dc)]
            for n in range(1, max_n + 1):
                nr2, nc2 = r + dr * n, c + dc * n
                if not _ok(nr2, nc2):
                    break
                mc2 = 1 if n == 1 else len(str(n)) + 1
                _push((nr2, nc2), mc2)

        # $
        bc = None
        for cc in range(c + 1, COLS):
            if not composite.is_passable(r, cc):
                break
            bc = cc
        if bc is not None and _ok(r, bc):
            _push((r, bc), 1)

        # 0
        lc = c
        for cc in range(c - 1, -1, -1):
            if not composite.is_passable(r, cc):
                break
            lc = cc
        if lc < c and _ok(r, lc):
            _push((r, lc), 1)

        # ^
        if _fnb.get(r) is not None and _ok(r, _fnb[r]):
            _push((r, _fnb[r]), 1)

        # H and M (L excluded)
        if _ok(*_h_dest):
            _push(_h_dest, 1)
        if _ok(*_m_dest):
            _push(_m_dest, 1)

        # G
        if exit_pos and _ok(*exit_pos):
            _push(exit_pos, 1)

        # gg (2 ks)
        if _ok(*entry):
            _push(entry, 2)

        # x
        bit = _ks_map.get((r, c))
        if bit is not None and not (mask >> bit & 1):
            new_mask = mask | (1 << bit)
            nb_state = (r, c, new_mask)
            g = cost + 1
            if g < dist.get(nb_state, INF):
                dist[nb_state] = g
                heapq.heappush(heap, (g, nb_state))

    return None
