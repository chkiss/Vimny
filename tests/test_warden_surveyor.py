"""The Warden Surveyor (Act II boss) — arena structure (phase a).

These cover the static arena the two-phase warden AI will animate: the
Keep-style entry/seal/treasure frame, the poem-papered hall, the hazard
weave, and the navigability guarantees (clear aisle + clear warden row).
The warden's combat AI is tested separately once it lands.
"""
import pytest
from collections import deque

import generation.dungeon_gen as dg
from engine.world import CellType
from engine.motion import _sentence_starts, _bracket_at
from tests import SEEDS


def _room(seed):
    return dg.build_dungeon_warden_surveyor(seed).rooms[0]


def _ent(room, kind):
    return [e for e in room.entities if e.kind == kind]


def _hazards(room):
    voids = {(ru.row, ru.col) for ru in room.char_runs if ru.kind == 'void'}
    dyn   = {(e.row, e.col) for e in room.entities if e.kind == 'dynamite'}
    return voids | dyn


def _reach(room, src, dst, blocked):
    """BFS treating WALL and `blocked` cells as impassable."""
    seen, q = {src}, deque([src])
    while q:
        r, c = q.popleft()
        if (r, c) == dst:
            return True
        for dr, dc in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            nb = (r + dr, c + dc)
            if (nb not in seen and 0 <= nb[0] < room.rows and 0 <= nb[1] < room.cols
                    and room.cells[nb[0]][nb[1]] != CellType.WALL and nb not in blocked):
                seen.add(nb)
                q.append(nb)
    return False


# ── Frame (reuses the Keep's entry / seal / treasure pattern) ─────────────────

@pytest.mark.parametrize("seed", SEEDS)
def test_dimensions_and_anchors(seed):
    room = _room(seed)
    assert (room.rows, room.cols) == (dg._WS_ROWS, dg._WS_COLS)
    assert room.spawn_pos == dg._WS_SPAWN
    assert room.exit_pos == dg._WS_EXIT
    assert room.par is None and room.budget > 0


@pytest.mark.parametrize("seed", SEEDS)
def test_gating_entities_present(seed):
    room = _room(seed)
    for kind in ('seal_door', 'locked_door', 'exit', 'heart_container', 'chest_scroll'):
        assert len(_ent(room, kind)) == 1, f"missing {kind}"


@pytest.mark.parametrize("seed", SEEDS)
def test_one_warden_tagged_surveyor_with_shield(seed):
    room = _room(seed)
    wardens = _ent(room, 'warden')
    assert len(wardens) == 1
    w = wardens[0]
    assert w.tag == 'surveyor' and w.hp == 5 and w.ai == ''   # no chase, no summon
    shields = _ent(room, 'shield')
    assert len(shields) == 1 and shields[0].row == w.row      # shield on his row
    assert abs(shields[0].col - w.col) == 1


@pytest.mark.parametrize("seed", SEEDS)
def test_hall_starts_fogged(seed):
    room = _room(seed)
    # the hall sits behind the closed seal-door, so it must start hidden
    assert any((r, c) in room.fog_cells
               for r in range(dg._WS_HALL_TOP, dg._WS_HALL_BOT + 1)
               for c in (dg._WS_HALL_LEFT, 40))


# ── The verse (structural-motion targets) ─────────────────────────────────────

@pytest.mark.parametrize("seed", SEEDS)
def test_warden_row_has_bracket_pair_straddling_him(seed):
    """% (or a )/( hop) must carry the player across the warden to his far side."""
    room = _room(seed)
    w = _ent(room, 'warden')[0]
    opens  = [c for c in range(room.cols) if _bracket_at(room, w.row, c) == '(']
    closes = [c for c in range(room.cols) if _bracket_at(room, w.row, c) == ')']
    assert any(o < w.col < cl for o in opens for cl in closes), \
        "no ()-pair straddles the warden"


@pytest.mark.parametrize("seed", SEEDS)
def test_paragraph_breaks_exist(seed):
    """Blank rows between poems give }/{ somewhere to land."""
    room = _room(seed)
    rows_with_text = {ru.row for ru in room.char_runs if ru.kind != 'void'}
    blanks = [r for r in range(dg._WS_HALL_TOP, dg._WS_HALL_BOT + 1)
              if r not in rows_with_text]
    assert len(blanks) >= 3


@pytest.mark.parametrize("seed", SEEDS)
def test_multiple_sentences_somewhere(seed):
    """At least one row carries >1 sentence (so )/( has an intra-row target)."""
    room = _room(seed)
    assert any(len(_sentence_starts(room, r)) >= 2 for r in range(room.rows))


# ── The hazard weave ──────────────────────────────────────────────────────────

@pytest.mark.parametrize("seed", SEEDS)
def test_water_moat_and_dynamite_no_void(seed):
    room = _room(seed)
    assert any(room.cells[r][c] == CellType.WATER
               for r in range(room.rows) for c in range(room.cols)), 'expected a water moat'
    assert not any(ru.kind == 'void' for ru in room.char_runs), 'void runes replaced by water'
    assert _ent(room, 'dynamite')


@pytest.mark.parametrize("seed", SEEDS)
def test_moat_rings_the_hall_with_entry_and_exit_gates(seed):
    room = _room(seed)
    L, R = dg._WS_HALL_LEFT, dg._WS_HALL_RIGHT
    T, B = dg._WS_HALL_TOP, dg._WS_HALL_BOT
    # perimeter is water...
    assert room.cells[8][L] == CellType.WATER and room.cells[8][R] == CellType.WATER
    assert room.cells[T][40] == CellType.WATER and room.cells[B][40] == CellType.WATER
    # ...entry is leap-gated (water at the left edge, dry floor just beyond)...
    assert room.cells[dg._WS_WARDEN_ROW][L] == CellType.WATER
    assert room.cells[dg._WS_WARDEN_ROW][dg._WS_TEXT_COL] == CellType.FLOOR
    # ...and the right edge opens a dry exit gate on the main row only.
    assert room.cells[dg._WS_WARDEN_ROW][R] == CellType.FLOOR


@pytest.mark.parametrize("seed", SEEDS)
def test_warden_row_interior_is_clear(seed):
    """The warden's row interior is dry and dynamite-free, so the combat /
    approach lane stays navigable."""
    room = _room(seed)
    wr = dg._WS_WARDEN_ROW
    for c in range(dg._WS_TEXT_COL, dg._WS_INNER_RIGHT + 1):
        assert room.cells[wr][c] == CellType.FLOOR
        e = room.entity_at(wr, c)
        assert e is None or e.kind != 'dynamite'


@pytest.mark.parametrize("seed", SEEDS)
def test_interior_route_to_warden_and_exit(seed):
    """From just inside the moat (where ^/f land), a step-path avoiding water and
    dynamite reaches a cell beside the warden and on through the exit gate."""
    room = _room(seed)
    blocked = _hazards(room) | {(r, c) for r in range(room.rows) for c in range(room.cols)
                                if room.cells[r][c] == CellType.WATER}
    w = _ent(room, 'warden')[0]
    start = (dg._WS_WARDEN_ROW, dg._WS_TEXT_COL)
    beside = {(w.row, w.col - 1), (w.row, w.col + 1)}
    assert any(_reach(room, start, b, blocked) for b in beside)
    assert _reach(room, start, room.exit_pos, blocked)


@pytest.mark.parametrize("seed", SEEDS)
def test_leap_in_drown_out(seed):
    """^ from the opened seal-door leaps the moat onto the first char; 0/$ on a
    combat row land in the water (drown)."""
    from engine.player import Player
    from engine.motion import apply_motion
    room = _room(seed)
    room.fog_cells.clear()                       # as if the seal-door were opened
    p = Player(); p.row, p.col = dg._WS_SEAL_DOOR
    apply_motion(p, '^', 1, room, game_h=22)
    assert (p.row, p.col) == (dg._WS_WARDEN_ROW, dg._WS_TEXT_COL)
    assert room.cells[p.row][p.col] == CellType.FLOOR
    for m in ('0', '$'):
        q = Player(); q.row, q.col = 8, 40
        apply_motion(q, m, 1, room, game_h=22)
        assert room.cells[q.row][q.col] == CellType.WATER, f'{m} should drown'


# ── Determinism / variation ───────────────────────────────────────────────────

def test_seed_determinism():
    a = dg.build_dungeon_warden_surveyor(7).rooms[0]
    b = dg.build_dungeon_warden_surveyor(7).rooms[0]
    sig = lambda rm: sorted((ru.row, ru.col, ru.symbols, ru.kind) for ru in rm.char_runs)
    assert sig(a) == sig(b)


def test_hazards_vary_across_seeds():
    sigs = {tuple(sorted(_hazards(dg.build_dungeon_warden_surveyor(s).rooms[0])))
            for s in range(30)}
    assert len(sigs) > 1


# ── Phase-1 attack helpers (the warden's v-sweep) ─────────────────────────────

import main
from engine.player import Player


@pytest.mark.parametrize("seed", SEEDS)
def test_threat_span_follows_the_player(seed):
    """v$ (warden→right edge) when the player is on his right; v0 otherwise."""
    room = _room(seed)
    w = _ent(room, 'warden')[0]
    _, _, l, r = main._ws_bounds()
    assert main._ws_threat_span(w.col, w.col + 5) == (w.col, r)   # player right → v$
    assert main._ws_threat_span(w.col, w.col - 5) == (l, w.col)   # player left  → v0


@pytest.mark.parametrize("seed", SEEDS)
def test_paren_cells_are_inside_brackets(seed):
    room = _room(seed)
    cells = main._ws_paren_cells(room)
    assert cells, 'expected cells inside () pairs'
    # every reported cell lies strictly between an open and close paren on its row
    for (r, c) in cells:
        row_txt = {cc: (room.char_run_at(r, cc).symbols[cc - room.char_run_at(r, cc).col]
                        if room.char_run_at(r, cc) else ' ') for cc in range(room.cols)}
        opens  = [cc for cc, ch in row_txt.items() if ch == '(' and cc < c]
        closes = [cc for cc, ch in row_txt.items() if ch == ')' and cc > c]
        assert opens and closes


@pytest.mark.parametrize("seed", SEEDS)
def test_landable_rejects_water_occupied_and_adjacent(seed):
    room = _room(seed)
    w = _ent(room, 'warden')[0]
    p = Player(); p.row, p.col = w.row, w.col
    assert not main._ws_landable(room, p, w.row, w.col)            # occupied (warden)
    assert not main._ws_landable(room, p, 8, dg._WS_HALL_LEFT)     # water moat
    assert not main._ws_landable(room, p, p.row, p.col + 1)        # too close to player


@pytest.mark.parametrize("seed", SEEDS)
def test_teleport_pool_has_landable_parentheticals(seed):
    """The 60%-weighted parenthetical pool is actually populated."""
    room = _room(seed)
    p = Player(); p.row, p.col = dg._WS_SPAWN
    paren_landable = [c for c in main._ws_paren_cells(room) if main._ws_landable(room, p, *c)]
    assert paren_landable


@pytest.mark.parametrize("seed", SEEDS)
def test_erase_row_clears_only_the_span(seed):
    room = _room(seed)
    w = _ent(room, 'warden')[0]
    _, _, l, r = main._ws_bounds()
    # chars left of the span on the warden row survive; chars in the span vanish
    def chars_in(c0, c1):
        return sum(1 for ru in room.char_runs if ru.row == w.row
                   for i in range(len(ru.symbols)) if c0 <= ru.col + i <= c1)
    left_before = chars_in(l, w.col - 1)
    main._ws_erase_row(room, w.row, w.col, r)               # erase the v$ span
    assert chars_in(w.col, r) == 0
    assert chars_in(l, w.col - 1) == left_before


# ── Hint bar / command gating on a boss level ─────────────────────────────────

def test_boss_hint_shows_the_act_not_the_next_command():
    from content.levels import act_commands
    from render.hint_bar import hint_text, _format
    acts = act_commands('warden_surveyor')
    # the whole of act 2, in curriculum order; none of act 1's basics
    assert acts == ['W', 'B', 'E', 'ge', 'gE', 'G', 'gg', 'H', 'M', 'L', '%', '{', '}', '(', ')']
    assert not ({'h', 'j', 'k', 'l', 'x', 'count', 'f'} & set(acts))
    # the next-act command the scroll gates is NOT part of the act
    gated = main._SCROLL_DROPS['warden_surveyor'][0]        # 'visual'
    assert gated not in acts
    # the boss hint lists the act even if that command has leaked into `known`
    assert hint_text([gated], slug='warden_surveyor') == _format(acts)


@pytest.mark.parametrize("seed", SEEDS)
def test_phase2_regen_restores_eaten_verse(seed):
    """At Phase 2 onset the sweep-eaten verse regrows (reshuffled)."""
    import random
    room = _room(seed)

    def verse_chars():
        return sum(len(ru.symbols) for ru in room.char_runs
                   if dg._WS_INNER_TOP <= ru.row <= dg._WS_INNER_BOT)

    before = verse_chars()
    for r in range(dg._WS_INNER_TOP, dg._WS_INNER_TOP + 6):       # the warden ate some rows
        main._ws_erase_row(room, r, dg._WS_TEXT_COL, dg._WS_INNER_RIGHT)
    eaten = verse_chars()
    dg.regen_surveyor_hall(room, random.Random(seed + 1))
    assert eaten < before
    assert verse_chars() > eaten                                 # regrew


@pytest.mark.parametrize("seed", SEEDS)
def test_paragraph_jumps_cannot_escape_the_hall(seed):
    """}/{ must stay within the moat-bounded hall, not vault into the entry/treasure."""
    from engine.player import Player
    from engine.motion import apply_motion
    room = _room(seed)
    room.fog_cells.clear()
    lo_r, hi_r = dg._WS_INNER_TOP, dg._WS_INNER_BOT
    lo_c, hi_c = dg._WS_TEXT_COL, dg._WS_INNER_RIGHT
    for motion in ('}', '{'):
        p = Player(); p.row, p.col = dg._WS_WARDEN_ROW, 30
        for _ in range(15):
            apply_motion(p, motion, 1, room, game_h=22)
            assert lo_r <= p.row <= hi_r and lo_c <= p.col <= hi_c, \
                f'{motion} escaped to {(p.row, p.col)}'


def test_shield_does_not_block_paragraph_jump_to_leftmost():
    """A shield blocks stepping, not a } jump: } reaches the leftmost blank,
    crossing the shield, but the moat still bounds the segment."""
    from engine.world import Entity
    from engine.motion import _segment_left
    room = _room(42)
    room.fog_cells.clear()
    blank = next(r for r in range(dg._WS_INNER_TOP, dg._WS_INNER_BOT + 1)
                 if not any(ru.row == r for ru in room.char_runs))
    room.entities.append(Entity(kind='shield', row=blank, col=40))
    room.rebuild_indexes()
    assert _segment_left(room, blank, 55) == dg._WS_TEXT_COL    # crosses the shield to col 18
    assert room.cells[blank][dg._WS_TEXT_COL - 1] == CellType.WATER   # ...bounded by the moat


def test_phase2_block_threat_is_the_ctrlv_rectangle():
    """Phase 2 frames the Ctrl-v rectangle between warden and player."""
    from engine.visual import block_bounds
    assert block_bounds((10, 30), (14, 40)) == (10, 14, 30, 40)
    assert block_bounds((14, 40), (10, 30)) == (10, 14, 30, 40)   # order-independent


def test_gated_command_is_taught_by_the_next_level():
    """The id the boss locks until its scroll is read is what the following
    teaching level introduces."""
    from content.levels import LEVELS
    gated = main._SCROLL_DROPS['warden_surveyor'][0]
    idx = next(i for i, lv in enumerate(LEVELS) if lv['slug'] == 'warden_surveyor')
    nxt = next(lv for lv in LEVELS[idx + 1:] if lv.get('teaches'))
    assert gated in nxt['teaches']
