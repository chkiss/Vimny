"""The Warden Scrivener (Act V boss, slug `warden_scrivener`): the Unfinished
Manuscript. He has copied these halls for an age and finished nothing; the
player completes his manuscript with the act's own verbs — the scrivener's
crafts — and strikes him in the stagger after each ward breaks.

Six beats, hp 5: the THRESHOLD (i — the lintel's word parts the fog), the
LIE (c), the ROT (R, TIMED — the mends re-rot _WSC_W2_WINDOW keystrokes after
the solve), the VOICE (case — mixed target, only the toggle reads true), the
TORN PAGE (J), and the RULE (= — the act's capstone).

The chassis is the Manifold press, JOIN-HARDENED — J and = are live all
fight, so the laws asserted below are mostly about that:
  - every ward check is text-derived; the bolt derives from the warden
    entity; the re-manifest alcove derives from its wall MARKER; the stamps
    and echo spawns are laid RELATIVE to the derived alcove row;
  - THE PIN: an adversarial mid-fight J (collapsing a clean aisle row before
    ward 2) leaves the whole remaining fight completable, key for key;
  - the wrong verb leaves a ward standing; the rot timer punishes a slow
    strike; undo rewinds the fight with the world;
  - boss conventions: par=None, relaxed budget, 1-star win, sealed pocket.
"""
from blessed.keyboard import Keystroke
from blessed import Terminal

import main
from engine.world import CellType
from content.levels import known_commands
from generation.dungeon_gen import (
    build_dungeon_warden_scrivener,
    _WSC_ROWS, _WSC_COLS, _WSC_BUDGET, _WSC_ALCOVES, _WSC_SIDES,
    _WSC_SEAL, _WSC_EXIT, _WSC_POCKET, _WSC_GATE, _WSC_W1, _WSC_W2_WINDOW,
)

import pytest

from tests import SEEDS, cached_room

ESC = Keystroke('\x1b', name='KEY_ESCAPE')


def _K(s):
    return [Keystroke(ch) for ch in s]


def _room(seed):
    return cached_room('build_dungeon_warden_scrivener', seed)


def _warden(room):
    return next((e for e in room.entities
                 if e.kind == 'warden' and e.tag == 'scrivener' and e.alive),
                None)


_STRIKE = '/W\rx'    # the search-jump strike: /W lands ON him, x at one's cell


def _lie_verb(room):
    return main._wla_floor_text(room, _WSC_W1[0]).strip().split()[1]


def _fight_keys(room, upto=99):
    """The canonical fight, key for key — every navigation is a SEARCH, so the
    script is position-independent (the arena may collapse under J)."""
    thr    = room._wsc_threshold
    true_v = room._wsc_targets[1].split()[1]
    word2, rot2, mid = room._wsc_word2, room._wsc_rot2, room._wsc_rotmid
    wrong3_head = room._wsc_targets[3].split()[0].swapcase()
    strike = _K(_STRIKE)
    keys = []
    keys += _K('i') + _K(thr) + [ESC]                              # 0 threshold
    if upto < 1:
        return keys
    keys += _K('/' + _lie_verb(room) + '\r') + _K('cw') + _K(true_v) + [ESC]
    if upto < 1.5:
        return keys
    keys += strike                                                 # 1 the Lie
    if upto < 2:
        return keys
    keys += _K('/' + rot2 + '\r') + _K('R') + _K(word2[mid:mid + 3]) + [ESC]
    if upto < 2.5:
        return keys
    keys += strike                                                 # 2 the Rot
    if upto < 3:
        return keys
    keys += _K('/' + wrong3_head + '\r') + _K('g~$') + strike      # 3 the Voice
    if upto < 4:
        return keys
    keys += _K('/' + room._wsc_targets[4].split()[0] + '\r') + _K('J') + strike
    if upto < 5:
        return keys
    keys += _K('/rite\r') + _K('=3j') + strike                     # 5 the Rule
    # loot: down the west margin, $ across the open seal into the pocket,
    # heart, chest, then a step back west onto the exit
    keys += _K('10j') + _K('$') + _K('kx') + _K('2jx') + _K('kh')
    return keys


def _drive(dungeon, keys, monkeypatch, finish=':wq\r'):
    keys = list(keys) + _K(finish)
    monkeypatch.setattr(main, 'render_all', lambda *a, **k: None)
    monkeypatch.setattr(main.time, 'sleep', lambda *a, **k: None)
    for anim in ('_fireworks_animation', '_win_animation', '_starfield_victory',
                 '_heart_container_animation', '_unlock_animation',
                 '_void_fall_animation', '_drown_animation'):
        monkeypatch.setattr(main, anim, lambda *a, **k: None)
    for fn in ('_show_catalog_scroll', '_show_scroll_by_id'):
        if hasattr(main, fn):
            monkeypatch.setattr(main, fn, lambda *a, **k: None)
    monkeypatch.setattr(Terminal, 'height', property(lambda self: 41))
    term = Terminal()
    it = iter(keys)
    monkeypatch.setattr(term, 'inkey', lambda *a, **k: next(it, Keystroke('')))
    return main.run_dungeon(term, 'warden_scrivener', {}, player_name='Slayer',
                            _dungeon=dungeon)


# ── structure + conventions ───────────────────────────────────────────────────

@pytest.mark.parametrize("seed", SEEDS)
def test_boss_conventions(seed):
    room = _room(seed)
    assert (room.rows, room.cols) == (_WSC_ROWS, _WSC_COLS)
    assert room.par is None and room.budget == _WSC_BUDGET
    w = _warden(room)
    assert w is not None and w.hp == w.max_hp == 5 and w.edit_immune
    assert (w.row, w.col) == _WSC_ALCOVES[0]
    ex = next(e for e in room.entities if e.kind == 'exit')
    assert ex.edit_immune, "the gate row is join-proof"
    assert room.cells[_WSC_SEAL[0]][_WSC_SEAL[1]] == CellType.WALL
    assert room.cells[_WSC_GATE[0]][_WSC_GATE[1]] == CellType.WALL


@pytest.mark.parametrize("seed", SEEDS)
def test_plain_stone_alcoves_and_the_colon_lint(seed):
    room = _room(seed)
    # alcoves are PLAIN STONE (playtest: no sigils) and found by GEOMETRY —
    # the derivation must agree with the build coords on the fresh room
    for k, (pr, pc) in enumerate(_WSC_ALCOVES):
        br = pr - _WSC_SIDES[k]
        assert room.char_run_at(br, pc) is None, "no sigil in the back wall"
        assert not room.is_passable(br, pc)
        assert main._wsc_alcove_pos(room, k) == (pr, pc)
    # COLON LINT: no non-finale passage may end ':' or lead 'end' — the block
    # law reads any text, and a stray colon turns = into a ward-scrambler
    texts = [room._wsc_targets[k] for k in (1, 2, 3, 4)]
    texts += [t for ward, stamps in room._wsc_stamps.items() if ward != 5
              for t, _kind in stamps]
    texts.append(main._wla_floor_text(room, _WSC_W1[0]).strip())
    for t in texts:
        assert not t.rstrip().endswith(':'), t
        assert t.split()[0] != 'end', t
    # ward 3 is the only CAPITALIZED floor text and must carry no 'W' — a
    # floor 'W' collides with the Warden's letter and /W eats the word
    assert 'W' not in room._wsc_targets[3]


@pytest.mark.parametrize("seed", SEEDS)
def test_words_distinct(seed):
    room = _room(seed)
    words = [room._wsc_threshold]
    for k in (1, 2, 3, 4):
        words += room._wsc_targets[k].lower().split()
    assert len(set(words)) == len(words), "seeded words never collide"
    # the rite may echo its own noun line to line, but never a ward's word
    rite_words = {w for t in room._wsc_rite
                  for w in t.rstrip(':').split() if w not in ('rite', 'end')}
    assert not (rite_words & set(words)), "the rite borrows no ward's word"


@pytest.mark.parametrize("seed", SEEDS)
def test_the_page_sleeps_under_fog(seed):
    """Before the threshold, the hall (glosses included) is fogged: /W finds
    nothing, no jump enters, the lie is unsearchable."""
    room = build_dungeon_warden_scrivener(seed).rooms[0]
    from engine.search import _match_positions
    assert _match_positions(room, 'W') == []
    assert _match_positions(room, _lie_verb(room)) == []
    assert (_WSC_ALCOVES[0]) in room.fog_cells
    assert set(_WSC_POCKET) <= room.fog_cells


def test_threshold_parts_the_fog(monkeypatch):
    dungeon = build_dungeon_warden_scrivener(SEEDS[0])
    room = dungeon.rooms[0]
    _drive(dungeon, _fight_keys(room, upto=0), monkeypatch, finish=':q!\r')
    gr, gc = _WSC_GATE
    assert room.cells[gr][gc] == CellType.FLOOR, "the gate draws"
    assert not (room._wsc_hall_fog & room.fog_cells), "the page's fog parts"
    assert set(_WSC_POCKET) <= room.fog_cells, "the pocket keeps its fog"


# ── the full fight ────────────────────────────────────────────────────────────

def _assert_fallen(room):
    assert _warden(room) is None
    assert not [e for e in room.entities if e.alive
                and e.kind == 'goblin' and e.tag == 'chorus'], "the chorus gutters"
    sr, sc = room._wsc_seal
    assert room.cells[sr][sc] == CellType.FLOOR, "the seal draws"
    assert not (set(_WSC_POCKET) & room.fog_cells), "the pocket fog parts"
    assert not any(e.alive and e.kind == 'heart_container' for e in room.entities)
    assert not any(e.alive and e.kind == 'chest_scroll' for e in room.entities)


@pytest.mark.parametrize("seed", SEEDS)
def test_full_fight_wins(seed, monkeypatch):
    """The canonical fight, key for key through run_dungeon: threshold, five
    wards, five /W strikes, the seal, the loot, the exit."""
    dungeon = build_dungeon_warden_scrivener(seed)
    room = dungeon.rooms[0]
    result = _drive(dungeon, _fight_keys(room), monkeypatch)
    assert result['won'], result
    _assert_fallen(room)


@pytest.mark.parametrize("seed", SEEDS)
def test_adversarial_join_cannot_break_the_press(seed, monkeypatch):
    """THE JOIN-HARDENING PIN: collapse a clean aisle row with J right after
    the first strike — every later beat (derived alcoves, relative stamps and
    spawns, text-derived checks, the = law) still tracks, and the same
    position-independent script finishes the fight."""
    dungeon = build_dungeon_warden_scrivener(seed)
    room = dungeon.rooms[0]
    base = _fight_keys(room)
    cut = len(_fight_keys(room, upto=1.5))       # right after strike 1
    # collapse row 16 — W2/W4's FUTURE stamp region (south of the pocket, so
    # the plain-walking loot tail stays honest; every ward mechanism south of
    # the cut must re-derive)
    keys = base[:cut] + _K('12jJ') + base[cut:]
    rows0 = room.rows
    result = _drive(dungeon, keys, monkeypatch)
    assert result['won'], result
    assert room.rows < rows0, "the adversarial J really collapsed a row"
    _assert_fallen(room)


def test_wrong_voice_leaves_the_ward_standing(monkeypatch):
    """gUU on the Voice writes the wrong case (the target is MIXED): the ward
    stands, the alcove stays sealed."""
    dungeon = build_dungeon_warden_scrivener(SEEDS[0])
    room = dungeon.rooms[0]
    keys = _fight_keys(room, upto=2.5)
    wrong3_head = room._wsc_targets[3].split()[0].swapcase()
    keys = keys + _K('/' + wrong3_head + '\r') + _K('gUU')
    _drive(dungeon, keys, monkeypatch, finish=':q!\r')
    assert not main._wsc_ward_broken(room, 3)
    w = _warden(room)
    assert w is not None and w.hp == 3, "no stagger, no strike"


def test_rot_timer_recorrupts_on_a_slow_strike(monkeypatch):
    """Solve the Rot, then dawdle past the window — the mends re-rot and the
    ward stands again (the Manifold R2 punishment, inherited)."""
    dungeon = build_dungeon_warden_scrivener(SEEDS[0])
    room = dungeon.rooms[0]
    keys = _fight_keys(room, upto=2) + _K('hl' * _WSC_W2_WINDOW)
    _drive(dungeon, keys, monkeypatch, finish=':q!\r')
    assert not main._wsc_ward_broken(room, 2), "the rot crawled back"


def test_undo_rewinds_the_fight(monkeypatch):
    """Break the Lie, then u — the lie is restored and the ward stands (the
    counter rides the snapshot; the Manifold convention)."""
    dungeon = build_dungeon_warden_scrivener(SEEDS[0])
    room = dungeon.rooms[0]
    keys = _fight_keys(room, upto=1) + _K('u')
    _drive(dungeon, keys, monkeypatch, finish=':q!\r')
    assert not main._wsc_ward_broken(room, 1), "the lie stands again"


# ── curriculum + the drop ─────────────────────────────────────────────────────

def test_curriculum_guard():
    """The boss teaches nothing; every verb it demands is already known."""
    known = set(known_commands('warden_scrivener'))
    for needed in ('insert', 'c', 'R', 'g~', 'gU', 'J', '=', '/', 'count'):
        assert needed in known, needed


def test_scroll_drop_wired():
    """The Whole Word (text_obj, the Act VI preview) drops here."""
    entry = main._SCROLL_DROPS.get('warden_scrivener')
    assert entry is not None and entry[0] == 'text_obj'
