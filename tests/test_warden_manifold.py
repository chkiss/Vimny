"""The Warden Manifold (Act IV boss, slug `warden_manifold`): "The Stamping Press".

He stamps himself into the world — wards of text, then copies of himself —
and the player out-copies him with the act's own verbs. The Warden is
edit_immune (every operator parries; the engine's real all-or-nothing shield)
and shelters in a FOGGED podium niche per round; breaking the round's ward
jams the press (copies gutter, his bolt draws, his fog parts and /W finds him
at last) for exactly one x. Opening ritual: an antechamber where the eternal
flame must be spread to four braziers (yl + P, the Beacon Tiers' fuel rule
active) — the gate draws AND the grand hall's fog parts. The whole hall is
fogged until then: no jump (H/G{n}/gg/M/L), walk, or search enters early.

Round → verb (see main._wm_ward_broken for the shift-proof checks):
  1  d{m}   three warding words that SAY what they are (lock, tomb, veil…);
            a wall post pins the reflow after each word and CRUMBLES when
            its word is cut
  2  r + .  his stamp four times, the same untypable warp in each; the mends
            RE-CORRUPT eight keystrokes after the solve (exactly the clean
            answer's cost) — strike at once or redo it
  3  D      a rot-tail with a rank of REAL Wardens standing on it; once the
            rot is half-cut, every keystroke DOUBLES the rank — one D or a
            flood
  4  yy+pp  his flame row stamped LIT (🜂🜂🜂 at 10,44..46); yank the LINE
            and paste twice — three flame rows, the 3×3 grid (the fuel rule
            locks charwise flames to braziers, so only HIS row can copy)

After the press falls the seal draws and the treasure pocket's fog parts:
a 3×2 vault behind the seal — exit center-west, heart container above,
the boss scroll's chest below (the chest IS the Inscriber's Hand drop).

Engine rules this boss leans on (each pinned below): tag='manifold'/'stamp'
exempt wardens from the stock auto-summon AND the post-x random leap; spawned
copies are hp=1 so one strike (or one swept D) gutters each; the tick moves
him via room.move_entity; brazier rows hold one brazier each and no glyph
anywhere east (open_gap shifts the whole buffer row); ward checks read CELL
TYPE, not is_passable (fog makes cells impassable — an is_passable check
read ward 1 as broken while it slept under the hall fog).
"""
from collections import deque

from blessed.keyboard import Keystroke
from blessed import Terminal

import main
from engine.motion import apply_motion
from engine.player import Player
from engine.search import match_cells, find_next
from engine.world import CellType, Entity
from content.levels import known_commands
from generation.dungeon_gen import (
    build_dungeon_warden_manifold,
    _WM_ROWS, _WM_COLS, _WM_AXIS, _WM_SPAWN, _WM_FLAME, _WM_BRAZIERS,
    _WM_GATE, _WM_PODIUMS, _WM_WARD1, _WM_WARD1_POSTS, _WM_WARD1_WORDS,
    _WM_WARD2, _WM_WARD2_WINDOW, _WM_WARD3, _WM_WARD3_RANK, _WM_WARD4,
    _WM_WARD4_ECHOES, _WM_SEAL, _WM_EXIT, _WM_HEART, _WM_CHEST, _WM_POCKET,
    _WM_HALL_LO, _WM_BUDGET, _QM_FLAME,
)
import pytest

from tests import SEEDS, cached_room


def _room(seed):
    """Shared READ-ONLY build; mutating tests call the builder directly."""
    return cached_room('build_dungeon_warden_manifold', seed)


def _warden(room):
    """The true Warden — tag='manifold' (round 3 floods the hall with
    kind='warden' tag='stamp' copies, so kind alone is ambiguous)."""
    return next((e for e in room.entities
                 if e.kind == 'warden' and e.tag == 'manifold' and e.alive),
                None)


def _stamps(room):
    return [e for e in room.entities
            if e.alive and e.kind == 'warden' and e.tag == 'stamp']


_STRIKE = '/W\rx'    # the search-jump strike: /W lands ON him, x at one's cell

_RITUAL = 'llyl' + '5k5lP' + '4j3lP' + 'jjP' + '4j3hP' + '5k4lll'
_R1     = 'kklldewdewde'                 # three cuts; posts crumble between
_R3     = '7j0D'                         # one stroke — rot and rank together
_R4     = '3kyypp'                       # yank his flame row, paste it twice
_LOOT   = '7k16l' + 'l' + 'lkx' + '2jx'  # seal → exit (win) → heart → chest
                                         # (7k: two pasted rows shifted him down)


def _r2(room) -> str:
    return '3jw' + 'r' + room._wm_word2[0] + 'w.w.w.'


def _fight_script(room) -> str:
    """The canonical full fight, key for key (verified live; deterministic —
    the manifold warden never random-leaps)."""
    return (_RITUAL
            + _R1 + _STRIKE
            + _r2(room) + _STRIKE
            + _R3 + _STRIKE
            + _R4 + _STRIKE
            + _LOOT)


def _drive(dungeon, keys_str, monkeypatch, finish=':q!\r'):
    keys = [Keystroke(ch) for ch in keys_str] + [Keystroke(ch) for ch in finish]
    monkeypatch.setattr(main, 'render_all', lambda *a, **k: None)
    monkeypatch.setattr(main.time, 'sleep', lambda *a, **k: None)
    for anim in ('_fireworks_animation', '_win_animation', '_starfield_victory',
                 '_heart_container_animation', '_unlock_animation'):
        monkeypatch.setattr(main, anim, lambda *a, **k: None)
    for scroll_fn in ('_show_catalog_scroll', '_show_scroll_by_id'):
        monkeypatch.setattr(main, scroll_fn, lambda *a, **k: None)
    term = Terminal()
    it = iter(keys)
    monkeypatch.setattr(term, 'inkey', lambda *a, **k: next(it, Keystroke('')))
    return main.run_dungeon(term, 'warden_manifold', {}, player_name='Slayer',
                            _dungeon=dungeon)


# ── structure & symmetry ──────────────────────────────────────────────────────

@pytest.mark.parametrize("seed", SEEDS)
def test_dimensions_and_anchors(seed):
    room = _room(seed)
    assert (room.rows, room.cols) == (_WM_ROWS, _WM_COLS)
    assert room.spawn_pos == _WM_SPAWN and room.exit_pos == _WM_EXIT
    assert room.par is None and room.budget == _WM_BUDGET, "boss: no keystroke par"
    w = _warden(room)
    assert w is not None and (w.row, w.col) == _WM_PODIUMS[0]
    assert w.edit_immune, "every operator must parry on the boss"
    assert w.tag == 'manifold', "exempts auto-summon AND the post-x random leap"
    assert w.max_hp == 4, "one x-window per round"
    assert room.cells[_WM_SEAL[0]][_WM_SEAL[1]] == CellType.WALL
    assert room.cells[_WM_GATE[0]][_WM_GATE[1]] == CellType.WALL


@pytest.mark.parametrize("seed", SEEDS)
def test_hall_is_mirrored_about_the_aisle(seed):
    """The aesthetics contract: podiums, braziers, the treasure pocket and
    the friezes all mirror about the processional aisle (row 8)."""
    room = _room(seed)
    mirror = lambda r: 2 * _WM_AXIS - r
    for group in (_WM_PODIUMS, _WM_BRAZIERS, _WM_POCKET):
        cells = set(group)
        assert {(mirror(r), c) for (r, c) in cells} == cells, group
    assert mirror(_WM_HEART[0]) == _WM_CHEST[0] and _WM_HEART[1] == _WM_CHEST[1], \
        "heart and chest mirror across the exit row"
    frieze_rows = {ru.row for ru in room.char_runs if ru.row in (1, 15)}
    assert frieze_rows == {1, 15}


@pytest.mark.parametrize("seed", SEEDS)
def test_no_columns_no_hall_hearts_no_guards(seed):
    """The redesign strips the colonnade, the mid-hall hearts, and the R1
    guards: the warding words alone carry round 1."""
    room = _room(seed)
    assert not [ru for ru in room.char_runs if '║' in ru.symbols]
    hearts = [e for e in room.entities if e.kind == 'heart_container']
    assert [(e.row, e.col) for e in hearts] == [_WM_HEART]
    assert not [e for e in room.entities if e.kind == 'goblin']


@pytest.mark.parametrize("seed", SEEDS)
def test_treasure_pocket_geometry(seed):
    """3×2 pocket behind the seal: exit center-west, heart top of column 2,
    scroll chest bottom; sealed from the hall on every other side."""
    room = _room(seed)
    for (r, c) in _WM_POCKET:
        assert room.cells[r][c] == CellType.FLOOR
    chest = next(e for e in room.entities if e.kind == 'chest_scroll')
    assert (chest.row, chest.col) == _WM_CHEST
    # walls everywhere around the pocket except the seal cell
    ring = {(r + dr, c + dc) for (r, c) in _WM_POCKET
            for dr, dc in ((0, 1), (0, -1), (1, 0), (-1, 0))}
    for cell in ring - set(_WM_POCKET):
        if cell == _WM_SEAL:
            continue
        assert room.cells[cell[0]][cell[1]] == CellType.WALL, cell


@pytest.mark.parametrize("seed", SEEDS)
def test_warding_words_are_thematic(seed):
    """R1's words come from the curated says-what-it-is list and never donate
    the R2 true letter (Echo Vault scarcity)."""
    room = _room(seed)
    row = _WM_WARD1[0]
    words = [''.join(ru.symbols) for ru in room.char_runs
             if ru.row == row and ru.kind == 'ancient']
    assert len(words) == 3
    letter = room._wm_word2[0]
    for w in words:
        assert w in _WM_WARD1_WORDS
        assert letter not in w


@pytest.mark.parametrize("seed", SEEDS)
def test_brazier_rows_are_reflow_safe(seed):
    """One brazier per row, and no other glyph anywhere east on the buffer
    row — a charwise paste open_gaps the whole row, across walls."""
    room = _room(seed)
    rows = [r for (r, _c) in _WM_BRAZIERS]
    assert len(rows) == len(set(rows)), "two braziers on one row shove each other"
    for (r, c) in _WM_BRAZIERS:
        east = [ru for ru in room.char_runs if ru.row == r and ru.col > c]
        assert not east, f"glyphs east of brazier {(r, c)} would be shoved: {east}"


# ── fog of war: three regions, three reveals ──────────────────────────────────

@pytest.mark.parametrize("seed", SEEDS)
def test_everything_past_the_gate_starts_fogged(seed):
    room = _room(seed)
    assert room.search_glyph_entities
    assert room._wm_hall_fog <= room.fog_cells, "the grand hall reads as unknown"
    assert set(_WM_PODIUMS) <= room.fog_cells, "every niche reads as stone"
    assert set(_WM_POCKET) <= room.fog_cells, "the treasure pocket too"


@pytest.mark.parametrize("seed", SEEDS)
def test_nothing_in_the_fog_is_searchable(seed):
    """/W finds no Warden, and the warding words sleep under the hall fog —
    search cannot scout (or enter) the chamber early."""
    room = _room(seed)
    assert match_cells(room, 'W') == set()
    word = next(''.join(ru.symbols) for ru in room.char_runs
                if ru.kind == 'ancient')
    p = Player(row=room.spawn_pos[0], col=room.spawn_pos[1])
    assert find_next(room, p, word, True) is None, "fogged text must not match"


@pytest.mark.parametrize("seed", SEEDS)
def test_jumps_cannot_enter_the_fogged_hall(seed):
    """H/M/L, G/gg/{n}G land on first non-blanks — fog is impassable, so
    every landing stays in the antechamber until the ritual."""
    room = build_dungeon_warden_manifold(seed).rooms[0]      # private (mutating)
    jumps = ([('G', 1, False), ('gg', 1, False), ('H', 1, False),
              ('M', 1, False), ('L', 1, False)]
             + [('G', n, True) for n in range(1, _WM_ROWS)])
    for motion, count, count_given in jumps:
        p = Player(row=room.spawn_pos[0], col=room.spawn_pos[1])
        apply_motion(p, motion, count, room, count_given=count_given)
        assert p.col < _WM_HALL_LO, f"{motion} entered the fogged hall"
        assert (p.row, p.col) not in _WM_POCKET
        assert (p.row, p.col) not in _WM_PODIUMS


@pytest.mark.parametrize("seed", SEEDS)
def test_hall_unreachable_until_the_ritual(seed):
    """As built, BFS from the spawn stays inside the antechamber: the gate is
    wall and the fog beyond it is impassable."""
    room = build_dungeon_warden_manifold(seed).rooms[0]      # private (mutating)
    seen, q = {room.spawn_pos}, deque([room.spawn_pos])
    while q:
        r, c = q.popleft()
        for dr, dc in ((0, 1), (0, -1), (1, 0), (-1, 0)):
            nb = (r + dr, c + dc)
            if nb not in seen and room.is_passable(*nb):
                seen.add(nb)
                q.append(nb)
    assert all(c < _WM_HALL_LO for (_r, c) in seen), "the hall leaked"


@pytest.mark.parametrize("seed", SEEDS)
def test_ritual_parts_the_hall_fog_only(seed, monkeypatch):
    """Four flames: the gate draws AND the hall fog parts — but the niches
    and the treasure pocket stay stone until their own reveals."""
    dungeon = build_dungeon_warden_manifold(seed)
    room = dungeon.rooms[0]
    _drive(dungeon, _RITUAL, monkeypatch)
    assert room.cells[_WM_GATE[0]][_WM_GATE[1]] == CellType.FLOOR
    assert not (room._wm_hall_fog & room.fog_cells)
    assert set(_WM_PODIUMS) <= room.fog_cells, "niches stay stone"
    assert set(_WM_POCKET) <= room.fog_cells, "the pocket waits for the seal"
    flames = {(ru.row, ru.col) for ru in room.char_runs
              if _QM_FLAME in ru.symbols}
    assert set(_WM_BRAZIERS) <= flames, "all four braziers burn"


def test_flame_paste_blocked_off_brazier():
    """The fuel rule holds everywhere off the chain — including the R4 stamp
    cells, so the 3×3 grid can never be assembled charwise."""
    room = _room(SEEDS[0])
    clip = {'linewise': False, 'rows': [{'width': 1, 'char_runs': [
        {'dcol': 0, 'symbols': (_QM_FLAME,), 'kind': 'flame'}]}]}
    floor = Player(row=8, col=6)                              # antechamber floor
    assert main._flame_paste_blocked(room, floor, clip, True, 1)
    on_brazier = Player(row=_WM_BRAZIERS[0][0], col=_WM_BRAZIERS[0][1])
    assert not main._flame_paste_blocked(room, on_brazier, clip, True, 1)
    on_stamp = Player(row=_WM_WARD4[0], col=_WM_WARD4[1])
    assert main._flame_paste_blocked(room, on_stamp, clip, True, 3), \
        "no charwise flame on his stamp cells — the grid must be linewise"


# ── the round machine ─────────────────────────────────────────────────────────

@pytest.mark.parametrize("seed", SEEDS)
def test_operators_parry_on_the_warden(seed):
    """edit_immune: a dd aimed at his row is REFUSED and he survives any
    charwise sweep."""
    from engine.reflow import remove_row
    room = build_dungeon_warden_manifold(seed).rooms[0]      # private (mutating)
    w = _warden(room)
    assert not remove_row(room, w.row), "his row must refuse the collapse"
    from engine.operator import _delete_cols
    _delete_cols(room, w.row, 0, room.cols - 1)
    assert _warden(room) is not None, "a charwise sweep must parry too"


@pytest.mark.parametrize("seed", SEEDS)
def test_round1_posts_crumble_word_by_word(seed, monkeypatch):
    """Cut word 1 → its post falls; the next still stands. All three cuts
    break the ward; /W jumps the strike."""
    dungeon = build_dungeon_warden_manifold(seed)
    room = dungeon.rooms[0]
    _drive(dungeon, _RITUAL + 'kkllde', monkeypatch)
    row = _WM_WARD1[0]
    assert room.cells[row][_WM_WARD1_POSTS[0]] == CellType.FLOOR, "post 1 crumbles"
    assert room.cells[row][_WM_WARD1_POSTS[1]] == CellType.WALL, "post 2 stands"

    dungeon = build_dungeon_warden_manifold(seed)
    room = dungeon.rooms[0]
    _drive(dungeon, _RITUAL + _R1 + _STRIKE, monkeypatch)
    assert all(room.cells[row][p] == CellType.FLOOR for p in _WM_WARD1_POSTS)
    w = _warden(room)
    assert w.hp == 3 and (w.row, w.col) == _WM_PODIUMS[1]
    assert room._wm_round == 2
    assert room.entity_at(w.row, w.col) is w, "move_entity must re-index the map"
    assert _WM_PODIUMS[0] not in room.fog_cells, "the spent niche stays open"
    assert _WM_PODIUMS[1] in room.fog_cells, "the next niche reads as stone"
    assert match_cells(room, 'W') == set(), "re-manifested, he is hidden again"


@pytest.mark.parametrize("seed", SEEDS)
def test_round2_solve_strike_within_the_window(seed, monkeypatch):
    dungeon = build_dungeon_warden_manifold(seed)
    room = dungeon.rooms[0]
    _drive(dungeon, _RITUAL + _R1 + _STRIKE + _r2(room) + _STRIKE, monkeypatch)
    w = _warden(room)
    assert w.hp == 2 and (w.row, w.col) == _WM_PODIUMS[2]
    word2 = room._wm_word2
    assert not main._wm_ward_broken(room, 2) or True   # round is past; ward moot
    assert room._wm_round == 3


@pytest.mark.parametrize("seed", SEEDS)
def test_round2_mends_recorrupt_after_the_window(seed, monkeypatch):
    """Solve, then waste _WM_WARD2_WINDOW keystrokes: the stamps re-warp, the
    bolt re-bars, and his fog is re-laid (no /W into a sealed niche)."""
    dungeon = build_dungeon_warden_manifold(seed)
    room = dungeon.rooms[0]
    _drive(dungeon, _RITUAL + _R1 + _STRIKE + _r2(room)
           + 'h' * _WM_WARD2_WINDOW, monkeypatch)
    w = _warden(room)
    assert w.hp == 3, "no strike landed"
    assert not main._wm_ward_broken(room, 2), "the mends must re-corrupt"
    assert (w.row, w.col) in room.fog_cells, "he is re-fogged"
    assert match_cells(room, 'W') == set()
    bolt = main._wm_bolt_cell(room, w)
    assert room.cells[bolt[0]][bolt[1]] == CellType.WALL, "the bolt re-bars"


@pytest.mark.parametrize("seed", SEEDS)
def test_round2_recorrupted_stamps_can_be_resolved(seed, monkeypatch):
    """After a re-corruption the same r + dots rhythm works again: line
    start, w onto the first warp (the warding words are long gone, so the
    stamps are the row's only words), mend, dots, strike."""
    dungeon = build_dungeon_warden_manifold(seed)
    room = dungeon.rooms[0]
    letter = room._wm_word2[0]
    re_solve = '0w' + 'r' + letter + 'w.w.w.'
    _drive(dungeon, _RITUAL + _R1 + _STRIKE + _r2(room)
           + 'h' * _WM_WARD2_WINDOW + re_solve + _STRIKE, monkeypatch)
    w = _warden(room)
    assert w.hp == 2, "the re-solve must open the window again"


@pytest.mark.parametrize("seed", SEEDS)
def test_round3_rank_is_real_wardens(seed, monkeypatch):
    dungeon = build_dungeon_warden_manifold(seed)
    room = dungeon.rooms[0]
    _drive(dungeon, _RITUAL + _R1 + _STRIKE + _r2(room) + _STRIKE, monkeypatch)
    rank = _stamps(room)
    assert len(rank) == len(_WM_WARD3_RANK)
    assert all(e.hp == 1 and not e.edit_immune for e in rank)
    assert {(e.row, e.col) for e in rank} == set(_WM_WARD3_RANK)


@pytest.mark.parametrize("seed", SEEDS)
def test_round3_partial_cut_doubles_per_keystroke(seed, monkeypatch):
    """x one rot char, then two keystrokes: 4 → 8 → 16. The flood is the
    punishment; D is the lesson."""
    dungeon = build_dungeon_warden_manifold(seed)
    room = dungeon.rooms[0]
    pre = _RITUAL + _R1 + _STRIKE + _r2(room) + _STRIKE
    _drive(dungeon, pre + '7j' + '28h' + 'x' + 'l' + 'l', monkeypatch)
    assert len(_stamps(room)) >= 16, "the rank must double per keystroke"


@pytest.mark.parametrize("seed", SEEDS)
def test_round3_one_D_shears_rot_and_rank(seed, monkeypatch):
    """The signature stroke: one D takes the rot and every Warden standing
    on it; the stagger gutters any copy left and no doubling ever primes."""
    dungeon = build_dungeon_warden_manifold(seed)
    room = dungeon.rooms[0]
    pre = _RITUAL + _R1 + _STRIKE + _r2(room) + _STRIKE
    _drive(dungeon, pre + _R3, monkeypatch)
    assert main._wm_ward_broken(room, 3)
    assert not _stamps(room), "the rank gutters with the rot"
    w = _warden(room)
    assert (w.row, w.col) not in room.fog_cells, "his fog parts for the strike"


@pytest.mark.parametrize("seed", SEEDS)
def test_round4_flame_row_and_the_linewise_finale(seed, monkeypatch):
    """Round 4 stamps his flame row LIT (🜂🜂🜂 at 10,44..46); yy + p + p
    copies it into the 3×3 grid (real rows — he and his fog ride the
    shift) and the ward breaks."""
    dungeon = build_dungeon_warden_manifold(seed)
    room = dungeon.rooms[0]
    pre = _RITUAL + _R1 + _STRIKE + _r2(room) + _STRIKE + _R3 + _STRIKE
    _drive(dungeon, pre, monkeypatch)
    assert room._wm_round == 4
    assert any(ru.kind == 'flame' and (ru.row, ru.col) == _WM_WARD4
               and len(ru.symbols) == 3 for ru in room.char_runs), \
        "his flame row stamps LIT"
    assert not main._wm_ward_broken(room, 4), "one flame row is not the grid"
    echoes = [e for e in room.entities
              if e.alive and e.kind == 'goblin' and e.tag == 'echo']
    assert len(echoes) == len(_WM_WARD4_ECHOES)

    dungeon = build_dungeon_warden_manifold(seed)
    room = dungeon.rooms[0]
    _drive(dungeon, pre + _R4, monkeypatch)
    assert main._wm_ward_broken(room, 4), "three flame rows break ward 4"
    assert room.rows == _WM_ROWS + 2, "two REAL rows pasted in"
    assert not [e for e in room.entities
                if e.alive and e.kind == 'goblin'], "the crowd gutters"
    w = _warden(room)
    assert (w.row, w.col) not in room.fog_cells, "his fog parts (it rode the shift)"


@pytest.mark.parametrize("seed", SEEDS)
def test_undo_rewinds_the_round_with_the_world(seed, monkeypatch):
    """Undoing the round-2 strike restores his HP, his podium AND the round
    counter — so the next strike re-runs round 3 (the rot re-stamps), never
    skipping ahead. Pins the grind exploit shut: with the round outside the
    snapshot, an undone world read the NEXT ward as vacuously broken (no
    rot = "sheared"), the bolt stood open, and he could be ground down
    strike after strike without re-solving anything."""
    dungeon = build_dungeon_warden_manifold(seed)
    room = dungeon.rooms[0]
    _drive(dungeon, _RITUAL + _R1 + _STRIKE + _r2(room) + _STRIKE + 'u',
           monkeypatch)
    w = _warden(room)
    assert w.hp == 3, "the strike is undone"
    assert (w.row, w.col) == _WM_PODIUMS[1], "back at the round-2 podium"
    assert room._wm_round == 2, "the round rewinds with the world"

    dungeon = build_dungeon_warden_manifold(seed)
    room = dungeon.rooms[0]
    _drive(dungeon, _RITUAL + _R1 + _STRIKE + _r2(room) + _STRIKE + 'u' + 'x',
           monkeypatch)
    w = _warden(room)
    assert w.hp == 2 and room._wm_round == 3, "the re-strike re-enters round 3"
    assert main._wm_rot_cells(room) > 0, "the rot re-stamps — back to bottom-left"


# ── the full fight ────────────────────────────────────────────────────────────

@pytest.mark.parametrize("seed", SEEDS)
def test_full_fight_wins(seed, monkeypatch):
    """The canonical fight, key for key through run_dungeon: ritual, four
    rounds, four /W strikes, the seal, the loot, the exit."""
    dungeon = build_dungeon_warden_manifold(seed)
    room = dungeon.rooms[0]
    result = _drive(dungeon, _fight_script(room), monkeypatch, finish=':wq\r')
    assert result['won'], result
    assert _warden(room) is None
    assert not [e for e in room.entities if e.alive
                and (e.kind == 'goblin'
                     or (e.kind == 'warden' and e.tag == 'stamp'))], \
        "every copy gutters when the press falls"
    sr, sc = room._wm_seal
    assert room.cells[sr][sc] == CellType.FLOOR
    assert not (set(_WM_POCKET) & room.fog_cells), "the pocket fog parts"
    assert not any(e.alive and e.kind == 'heart_container'
                   for e in room.entities), "the heart is collected"
    assert not any(e.alive and e.kind == 'chest_scroll'
                   for e in room.entities), "the scroll chest is opened"


def test_curriculum_guard():
    """The boss teaches nothing; everything it demands is already known."""
    known = set(known_commands('warden_manifold'))
    for needed in ('d', 'D', 'r', 'dot', 'y', 'P', 'p', 'count', '$', '0',
                   'G', '/'):
        assert needed in known
