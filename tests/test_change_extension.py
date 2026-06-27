"""The Change Extension (display 24, slug `change_extension`): S, C.

The one-key shorthands, on the Change Annex chassis (the sixth plaque-door
hall). The player owns the `c` operator (L23); now `S` (= `cc`) and `C` (= `c$`)
each do in ONE keypress what costs two. A hall of mislabelled doors: every
door's plaque (WEST wall) shows the word it wants; the floor label to the east
shows the wrong one. Four kinds:

  S doors    — the WHOLE line is one wrong word; `S` rewrites it (cc overpays 1).
  C doors    — a correct prefix then a TWO-word wrong tail; `C` from the tail's
               start rewrites it (c$ overpays 1; `ce` stops a word short). The
               replacement is a single word, so the typed text holds no space.
  word door  — one word off inside a kept phrase; `ce` keeps the context.
  rune door  — a fused ◆ → two letters; `s` cuts it (reinforcement).

Forcing is by VOLUME (each shorthand saves exactly one key per use): the eight
shorthand doors cost +1 each on the old cc/c$ path, so the all-old route is
par + _CE_SAVING — one past the budget (margin _CE_SAVING − 1) — and is barred.
The word/rune doors cost the same on either route; they only drill WHICH tool.

Laws asserted below:
  - PLAQUE IN THE WEST WALL — uncuttable and off the floor scans (reflow is now
    segment-bounded both ways, so an east plaque would be safe too; west is the
    simplest home).
  - THE EXIT IS PLAIN FLOOR — a row of plaque-door bolts and the spine/throat
    geometry bar it; no jump reaches it until every bolt opens.
  - The C door keeps its correct PREFIX (the words are laid as separate runs so
    `w` lands on the wrong tail, not on a space glyph).
  - The canonical answer is the REAL keystroke tape (karaoke); nothing typed
    holds a space.
"""
from collections import deque

from blessed.keyboard import Keystroke
from blessed import Terminal

import main
from engine.motion import apply_motion
from engine.player import Player
from engine.world import CellType
from content.levels import known_commands
from generation.dungeon_gen import (
    build_dungeon_change_extension, _ce_pick, _ce_route, _ce_answer,
    _whole_line_dissimilar,
    _CE_ROWS, _CE_COLS, _CE_COL_S, _CE_LBL_COL, _CE_LBL_END, _CE_PLQ_COL,
    _CE_LESSON_ROWS, _CE_THROAT_ROW, _CE_GATE_ROW, _CE_GATE_COL0, _CE_EXIT,
    _CE_PAR, _CE_TRIGGERS, _CE_SAVING, _CE_N_S, _CE_N_C, _CE_KIND_ORDER,
    _CE_PREFIX, _CE_VERB, _CE_PLACEHOLDER,
)

import pytest
import random

from tests import SEEDS, cached_room

_FLOORS = (CellType.FLOOR, CellType.CORRIDOR)
ESC = Keystroke('\x1b', name='KEY_ESCAPE')


def _bolt(i):
    """The (row, col) of door i's gate bolt."""
    return (_CE_GATE_ROW, _CE_GATE_COL0 + i)


def _room(seed):
    """Shared READ-ONLY build; mutating tests call the builder directly."""
    return cached_room('build_dungeon_change_extension', seed)


def _K(s):
    return [Keystroke(ch) for ch in s]


def _change_keys(lessons):
    """The canonical S/C route (shared _ce_route): the verb keys, then the typed
    fix sealed with Esc (free)."""
    out = []
    for keys, typed in _ce_route(lessons):
        out += _K(keys)
        if typed:
            out += _K(typed) + [ESC]
    return out


def _old_keys(lessons):
    """The same route with each shorthand swapped for its two-key rival (+1 key
    each): S→cc, C→c$. The word (ce) / rune (s) doors are unchanged — they have
    no cheaper rival; they cost the same on either route."""
    out = []
    for i, L in enumerate(lessons):
        out += _K('' if i == 0 else _CE_PREFIX[L['kind']])
        if L['kind'] == 'sline':
            out += _K('cc') + _K(L['typed']) + [ESC]
        elif L['kind'] == 'ceol':
            out += _K('c$') + _K(L['typed']) + [ESC]
        elif L['kind'] == 'word':
            out += _K('ce') + _K(L['typed']) + [ESC]
        else:
            out += _K('s') + _K(L['typed']) + [ESC]
    return out + _K('G$')


def _drive(dungeon, keys, monkeypatch, finish=':wq\r', name='Scribe'):
    keys = list(keys) + _K(finish)
    monkeypatch.setattr(main, 'render_all', lambda *a, **k: None)
    monkeypatch.setattr(main.time, 'sleep', lambda *a, **k: None)
    for anim in ('_fireworks_animation', '_win_animation', '_starfield_victory',
                 '_heart_container_animation', '_unlock_animation',
                 '_void_fall_animation', '_drown_animation'):
        monkeypatch.setattr(main, anim, lambda *a, **k: None)
    term = Terminal()
    it = iter(keys)
    monkeypatch.setattr(term, 'inkey', lambda *a, **k: next(it, Keystroke('')))
    return main.run_dungeon(term, 'change_extension', {}, player_name=name,
                            _dungeon=dungeon)


# ── structure ─────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("seed", SEEDS)
def test_dimensions_anchors_par_budget(seed):
    room = _room(seed)
    assert (room.rows, room.cols) == (_CE_ROWS, _CE_COLS)
    assert room.spawn_pos == (_CE_LESSON_ROWS[0], _CE_LBL_COL)
    assert room.exit_pos == _CE_EXIT
    assert room.par == _CE_PAR
    # tight margin (S2 by volume): below the shorthand-door count, so all-old overshoots
    assert room.budget == _CE_PAR + _CE_SAVING - 1
    assert room.budget - room.par < _CE_SAVING


@pytest.mark.parametrize("seed", SEEDS)
def test_lesson_block_is_open_floor(seed):
    room = _room(seed)
    for r in _CE_LESSON_ROWS:
        for c in range(_CE_COL_S, _CE_LBL_END + 1):
            assert room.cells[r][c] == CellType.FLOOR, (r, c)


@pytest.mark.parametrize("seed", SEEDS)
def test_plaque_is_in_the_west_wall(seed):
    """The plaque sits WEST of the spine, in WALL cells (uncuttable, off the
    floor scans)."""
    room = _room(seed)
    for r in _CE_LESSON_ROWS:
        plq = room.char_run_at(r, _CE_PLQ_COL)
        assert plq is not None and plq.kind == 'verdant'
        assert _CE_PLQ_COL < _CE_COL_S, "plaque is west of the spine"
        for k in range(len(plq.symbols)):
            assert room.cells[r][_CE_PLQ_COL + k] == CellType.WALL


@pytest.mark.parametrize("seed", SEEDS)
def test_bolts_start_walled_exit_is_plain_floor(seed):
    """Every gate bolt is WALL at build (the tick opens them per label). The
    exit is PLAIN FLOOR — never a gated wall — and stays floor through a tick."""
    dungeon = build_dungeon_change_extension(seed)
    room = dungeon.rooms[0]
    p = Player(row=room.spawn_pos[0], col=room.spawn_pos[1])
    main._whole_line_annex_tick(room, p)
    for i in range(_CE_TRIGGERS):
        assert room.cells[_bolt(i)[0]][_bolt(i)[1]] == CellType.WALL
    assert room.cells[_CE_EXIT[0]][_CE_EXIT[1]] == CellType.FLOOR


@pytest.mark.parametrize("seed", SEEDS)
def test_lesson_mix(seed):
    """Four S, four C, one word, one rune — the fixed order (par invariance);
    door 0 is an S door so its route prefix is empty (S ignores the column)."""
    room = _room(seed)
    kinds = tuple(L['kind'] for L in room._ce_lessons)
    assert kinds == _CE_KIND_ORDER
    assert kinds[0] == 'sline'
    assert kinds.count('sline') == _CE_N_S == 4
    assert kinds.count('ceol') == _CE_N_C == 4
    # every C door follows an S door, so the cursor lands on the wrong tail and
    # `jC` rewrites it with no `^w` to spend (uniform nav, honest par)
    for i, k in enumerate(kinds):
        if k == 'ceol':
            assert i > 0 and kinds[i - 1] == 'sline', f"C door {i} must follow an S door"


@pytest.mark.parametrize("seed", SEEDS)
def test_label_target_shapes(seed):
    """sline: a single 6-letter word (no space). ceol: prefix kept, a two-word
    wrong tail collapses to ONE right word. word: one word off, context kept.
    rune: a fused ◆ → two letters. No typed value holds a space."""
    for L in _ce_pick(random.Random(seed)):
        assert ' ' not in L['typed'], "no typed value may contain a space"
        if L['kind'] == 'sline':
            assert ' ' not in L['label'] and ' ' not in L['target']
            assert L['typed'] == L['target'] and L['label'] != L['target']
            assert len(L['typed']) == 6
        elif L['kind'] == 'ceol':
            lw, tw = L['label'].split(), L['target'].split()
            assert len(lw) == 3 and len(tw) == 2          # 'pre badA badB' → 'pre right'
            assert lw[0] == tw[0], "prefix kept"
            assert L['typed'] == tw[1] and len(L['typed']) == 4
            assert tw[1] not in (lw[1], lw[2]), "the tail is genuinely wrong"
        elif L['kind'] == 'word':
            lw, tw = L['label'].split(), L['target'].split()
            assert lw[1] == tw[1] and lw[0] != tw[0]      # context kept
            assert L['typed'] == tw[0] and len(L['typed']) == 4
        else:
            assert L['label'].startswith(_CE_PLACEHOLDER)
            tw = L['target'].split()
            assert L['typed'] == tw[0][:2] and len(L['typed']) == 2
            assert L['label'].split()[1] == tw[1]         # context kept


@pytest.mark.parametrize("seed", SEEDS)
def test_doors_independent(seed):
    """Distinct words guarantee it: no target is a substring of another target
    or of any label, so each change opens exactly its own bolt."""
    lessons = _ce_pick(random.Random(seed))
    targets = [L['target'] for L in lessons]
    labels = [L['label'] for L in lessons]
    for i, t in enumerate(targets):
        for j, u in enumerate(targets):
            if i != j:
                assert t not in u, (t, u)
        for lb in labels:
            assert t not in lb, (t, lb)


def test_s_doors_resist_cheap_old_tool_edits():
    """The S/C-forcing margin is a single key (budget = par + SAVING - 1), so an
    S door whose wrong/right words are SIMILAR could be rewritten more cheaply
    than `cc`/`S` with an already-known tool (a `r`, a count-`s`, or a shared
    prefix/suffix change). That alone clears the door for under a key and—since
    the margin is exactly one—lets a player beat the hall WITHOUT ever pressing S
    or C (replay-confirmed on the old generator, e.g. seed 1349's `strobe`→`strong`
    via `4l2sng`). `_draw_whole_line_pair` forbids it: each S-door pair differs in
    the first AND last char and in >= 4 positions, so the cheapest old-tool rewrite
    is `{6}s` = `cc`'s cost, never less. Scanned WIDE (not just the 5 SEEDS)."""
    for seed in range(1000):
        for L in _ce_pick(random.Random(seed)):
            if L['kind'] == 'sline':
                assert _whole_line_dissimilar(L['label'], L['target']), \
                    (seed, L['label'], L['target'])


@pytest.mark.parametrize("seed", SEEDS)
def test_c_door_label_words_are_separate_runs(seed):
    """A C door's words are laid as separate runs with bare-floor gaps (not one
    run with a space glyph), so `w` skips the gap and lands on the wrong tail —
    NOT on the space (which the word-class scan reads as a punctuation 'word')."""
    room = build_dungeon_change_extension(seed).rooms[0]
    for L in room._ce_lessons:
        if L['kind'] != 'ceol':
            continue
        words = L['label'].split()
        col = _CE_LBL_COL
        for w in words:
            ru = room.char_run_at(L['row'], col)
            assert ru is not None and ''.join(ru.symbols) == w, (L['row'], col, w)
            gap = col + len(w)
            assert room.char_run_at(L['row'], gap) is None, "a bare-floor gap, not a space glyph"
            col = gap + 1


# ── access: the exit is ten changes deep, and no jump cheats it ───────────────

def _reachable(room):
    seen, q = {room.spawn_pos}, deque([room.spawn_pos])
    while q:
        r, c = q.popleft()
        for dr, dc in ((0, 1), (0, -1), (1, 0), (-1, 0)):
            nb = (r + dr, c + dc)
            if nb not in seen and room.is_passable(*nb):
                seen.add(nb)
                q.append(nb)
    return seen


@pytest.mark.parametrize("seed", SEEDS)
def test_exit_unreachable_as_built(seed):
    room = build_dungeon_change_extension(seed).rooms[0]
    assert _CE_EXIT not in _reachable(room), "the bolts and the geometry hold"


@pytest.mark.parametrize("seed", SEEDS)
def test_no_jump_lands_on_the_shut_exit(seed):
    """The teleport audit: with the bolts shut, NO line jump may land on the
    plain-floor exit (it is never a row's first standable cell, and the throat
    joins the block to the gate only at the spine)."""
    room = build_dungeon_change_extension(seed).rooms[0]
    jumps = ([('G', 1, False), ('gg', 1, False), ('H', 1, False),
              ('M', 1, False), ('L', 1, False)]
             + [('G', n, True) for n in range(1, _CE_ROWS)])
    for motion, count, given in jumps:
        p = Player(row=room.spawn_pos[0], col=room.spawn_pos[1])
        apply_motion(p, motion, count, room, count_given=given)
        assert (p.row, p.col) != _CE_EXIT, f"{motion} dropped onto the shut exit"
        assert room.is_passable(p.row, p.col), f"{motion} landed in a wall"


# ── the doors, driven for real ────────────────────────────────────────────────

@pytest.mark.parametrize("seed", SEEDS)
def test_full_change_route_wins_par_perfect(seed, monkeypatch):
    dungeon = build_dungeon_change_extension(seed)
    room = dungeon.rooms[0]
    result = _drive(dungeon, _change_keys(room._ce_lessons), monkeypatch)
    assert result['won'] and result['stars'] == 2, result
    for i in range(_CE_TRIGGERS):
        assert room.cells[_bolt(i)[0]][_bolt(i)[1]] == CellType.FLOOR, "every bolt open"


@pytest.mark.parametrize("seed", SEEDS)
def test_c_door_keeps_the_prefix(seed, monkeypatch):
    """After the full route, every C-door row reads 'prefix right' — the correct
    prefix and the space survive (C rewrote only the tail; `w` did not eat the
    gap). This pins the separate-runs fix."""
    dungeon = build_dungeon_change_extension(seed)
    room = dungeon.rooms[0]
    _drive(dungeon, _change_keys(room._ce_lessons), monkeypatch)
    for L in room._ce_lessons:
        if L['kind'] == 'ceol':
            assert L['target'] in main._wla_floor_text(room, L['row']), \
                f"C door row {L['row']} should read {L['target']!r}"


@pytest.mark.parametrize("seed", SEEDS)
def test_plaques_survive_every_change(seed, monkeypatch):
    """The west-wall plaque is untouched by the floor edits: after the whole
    route (every kind of edit) each plaque still reads its original target."""
    dungeon = build_dungeon_change_extension(seed)
    room = dungeon.rooms[0]
    want = {r: room.char_run_at(r, _CE_PLQ_COL).symbols for r in _CE_LESSON_ROWS}
    _drive(dungeon, _change_keys(room._ce_lessons), monkeypatch)
    for r in _CE_LESSON_ROWS:
        plq = room.char_run_at(r, _CE_PLQ_COL)
        assert plq is not None and plq.symbols == want[r], \
            f"plaque on row {r} was disturbed by an edit"


@pytest.mark.parametrize("seed", SEEDS)
def test_all_old_route_is_barred(seed, monkeypatch):
    """Necessity, by volume: the route that spends cc/c$ on EVERY shorthand
    door (never S, never C) costs par + _CE_SAVING — one past the budget — so
    the path runs out and the exit is never reached."""
    dungeon = build_dungeon_change_extension(seed)
    result = _drive(dungeon, _old_keys(dungeon.rooms[0]._ce_lessons), monkeypatch)
    assert not result['won'], "the all-old route must run out of budget"


@pytest.mark.parametrize("seed", SEEDS)
def test_garbage_never_opens_a_bolt(seed, monkeypatch):
    """Typing the wrong letters over door 1 (an S door) changes the floor but
    matches no plaque — the bolt answers only to its target."""
    dungeon = build_dungeon_change_extension(seed)
    room = dungeon.rooms[0]
    keys = _K('S') + _K('zzzzzz') + [ESC]             # mangle door 1's whole line
    _drive(dungeon, keys, monkeypatch, finish=':q!\r')
    assert room.cells[_bolt(0)[0]][_bolt(0)[1]] == CellType.WALL


@pytest.mark.parametrize("seed", SEEDS)
def test_undo_rebars_the_bolt(seed, monkeypatch):
    """One change is one snapshot: making it opens the bolt; u unwrites the
    word and the tick re-bars it (stateless, undo-safe)."""
    dungeon = build_dungeon_change_extension(seed)
    room = dungeon.rooms[0]
    L0 = room._ce_lessons[0]                            # an S door
    _drive(dungeon, _K('S') + _K(L0['typed']) + [ESC] + _K('l'),
           monkeypatch, finish=':q!\r')
    assert room.cells[_bolt(0)[0]][_bolt(0)[1]] == CellType.FLOOR, "opened"

    dungeon = build_dungeon_change_extension(seed)
    room = dungeon.rooms[0]
    # l (a move), then u u: first u pops the move, the second the whole change.
    _drive(dungeon, _K('S') + _K(L0['typed']) + [ESC] + _K('luul'),
           monkeypatch, finish=':q!\r')
    assert room.cells[_bolt(0)[0]][_bolt(0)[1]] == CellType.WALL, "re-barred"


@pytest.mark.parametrize("seed", SEEDS)
def test_one_shut_bolt_bars_the_exit(seed, monkeypatch):
    """Nine labels true leaves the tenth bolt shut, so the exit (plain floor,
    east of the bolts) stays UNREACHABLE — the row of bolts is a series gate."""
    dungeon = build_dungeon_change_extension(seed)
    room = dungeon.rooms[0]
    lessons = room._ce_lessons
    keys = []
    for i, L in enumerate(lessons[:-1]):               # drive only the first nine
        keys += _K('' if i == 0 else _CE_PREFIX[L['kind']])
        keys += _K(_CE_VERB[L['kind']])
        keys += _K(L['typed']) + [ESC]
    keys += _K('j')                                    # toward the gate, no change
    _drive(dungeon, keys, monkeypatch, finish=':q!\r')
    assert room.cells[_bolt(9)[0]][_bolt(9)[1]] == CellType.WALL, "10th bolt shut"
    assert _CE_EXIT not in _reachable(room), "one shut bolt still bars the exit"


# ── the shorthands really are the lesson ──────────────────────────────────────

def test_curriculum_teaches_S_and_C():
    """The level introduces exactly the two shorthands, on top of the inherited
    `c` operator and `s`."""
    known = set(known_commands('change_extension'))
    assert {'S', 'C', 'c', 's'} <= known
    # and they were NOT already known the level before (whole_line_annex)
    prior = set(known_commands('whole_line_annex'))
    assert 'S' not in prior and 'C' not in prior


@pytest.mark.parametrize("seed", SEEDS)
def test_route_uses_the_shorthands(seed):
    """The canonical answer really presses S and C (not cc/c$)."""
    room = _room(seed)
    answer = room.answer
    assert 'S' in answer and 'C' in answer
    assert 'cc' not in answer and 'c$' not in answer


# ── the admin karaoke answer ──────────────────────────────────────────────────

@pytest.mark.parametrize("seed", SEEDS)
def test_answer_is_the_real_keystroke_tape(seed):
    """room.answer is the printable keystrokes of the canonical route (Esc
    omitted, spaces only as separators), so the admin answer-sheet tracks it
    keystroke for keystroke. No typed value contains a space."""
    room = _room(seed)
    expected = ''.join(keys + typed for keys, typed in _ce_route(room._ce_lessons))
    assert room.answer.replace(' ', '') == expected
    assert room.answer == _ce_answer(room._ce_lessons)


def test_admin_answer_tracking_follows_the_route(monkeypatch):
    """Driven as `admin`, the canonical keystrokes advance answer_pos without
    diverging (every non-space answer char is matched in order)."""
    dungeon = build_dungeon_change_extension(SEEDS[0])
    room = dungeon.rooms[0]
    _drive(dungeon, _change_keys(room._ce_lessons), monkeypatch,
           finish=':q!\r', name='admin')
    assert not room.answer_diverged, "the canonical route must not diverge"
    assert room.answer_pos == len(room.answer.replace(' ', ''))
