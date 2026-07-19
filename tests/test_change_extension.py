"""The Change Extension (slug `change_extension`): S, C.

The one-key shorthands, on the Change Annex chassis (the sixth plaque-door
hall). The player owns the `c` operator (the Change Annex); now `S` (= `cc`) and `C` (= `c$`)
each do in ONE keypress what costs two. A hall of mislabelled doors: every
door's plaque (WEST wall) shows the word it wants; the floor label to the east
shows the wrong one. Six kinds drill the distinct change verbs:

  S doors     — the WHOLE line is one wrong word; `S` rewrites it (cc overpays 1).
  C doors     — a correct prefix then a TWO-word wrong tail; `C` from the tail's
                start rewrites it (c$ overpays 1; `ce` stops a word short). The
                replacement is a single word, so the typed text holds no space.
  word door   — one word off inside a kept phrase; `ce` keeps the context.
  wordW door  — a ★-spanning WORD; `cE` crosses the symbol, `ce` stops at it
                (changes only the head → wrong text → the bolt stays shut).
  rune door   — a fused ◆ → two letters; `s` cuts it (reinforcement).
  bracket door— a (bracketed) head on a kept stem; `c%` changes the bracket span
                inclusively, keeping the stem (cE/s/C clobber the wrong extent).

Forcing is layered. VOLUME bars the all-old route: each shorthand saves exactly
one key, so the six shorthand doors (3·S + 3·C) cost +1 each on the old cc/c$
path — the all-old route is par + _CE_SAVING, one past the budget (margin
_CE_SAVING − 1). GEOMETRY forces the granular doors: ce/cE/s/c% each produce the
target only with the right verb, so a wrong verb leaves the floor mislabelled
and the bolt shut (replay-confirmed: `ce` on a wordW door, `cE`/`s`/`C` on the
bracket door).

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
    _CE_PREFIX, _CE_VERB, _CE_PLACEHOLDER, _CE_SYMBOL,
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
    each): S→cc, C→c$. The granular doors (ce/cE/s/c%) are unchanged — they have
    no cheaper rival; they cost the same on either route."""
    out = []
    for i, L in enumerate(lessons):
        out += _K('' if i == 0 else _CE_PREFIX[L['kind']])
        if L['kind'] == 'sline':
            out += _K('cc') + _K(L['typed']) + [ESC]
        elif L['kind'] == 'ceol':
            out += _K('c$') + _K(L['typed']) + [ESC]
        else:
            out += _K(_CE_VERB[L['kind']]) + _K(L['typed']) + [ESC]
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
def test_saying_prefixes_are_carved_in_the_west_stone(seed):
    """Sense, not decree: every door's saying prefix is carved in WALL cells
    (uncuttable, off the floor scans), right-aligned to end two cols shy of
    the spine — the saying reads straight across the stone into the floor."""
    room = _room(seed)
    for L in room._ce_lessons:
        r = L['row']
        stones = [ru for ru in room.char_runs
                  if ru.row == r and ru.kind == 'verdant']
        assert stones, r
        for ru in stones:
            for k in range(len(ru.symbols)):
                assert room.cells[r][ru.col + k] == CellType.WALL
        east = max(ru.col + len(ru.symbols) - 1 for ru in stones)
        assert east == _CE_COL_S - 2
        text = ' '.join(''.join(ru.symbols)
                        for ru in sorted(stones, key=lambda u: u.col))
        assert text == L['prefix']


@pytest.mark.parametrize("seed", SEEDS)
def test_bolts_start_walled_exit_is_the_final_seal(seed):
    """Every gate bolt is WALL at build (the tick opens them per label). The
    exit is the FINAL SEAL — stone until every plaque reads true, and it stays
    stone through a tick (A can carve floor east of the bolts since the
    Sculpting Chambers, so the seal, not the geometry, holds the way)."""
    dungeon = build_dungeon_change_extension(seed)
    room = dungeon.rooms[0]
    p = Player(row=room.spawn_pos[0], col=room.spawn_pos[1])
    main._whole_line_annex_tick(room, p)
    for i in range(_CE_TRIGGERS):
        assert room.cells[_bolt(i)[0]][_bolt(i)[1]] == CellType.WALL
    assert room.cells[_CE_EXIT[0]][_CE_EXIT[1]] == CellType.WALL


@pytest.mark.parametrize("seed", SEEDS)
def test_lesson_mix(seed):
    """Three S, three C, one word, two wordW, two rune, one bracket — the fixed
    order (par invariance); door 0 is an S door so its route prefix is empty (S
    ignores the column)."""
    room = _room(seed)
    kinds = tuple(L['kind'] for L in room._ce_lessons)
    assert kinds == _CE_KIND_ORDER
    assert kinds[0] == 'sline'
    assert kinds.count('sline') == _CE_N_S == 3
    assert kinds.count('ceol') == _CE_N_C == 3
    assert kinds.count('wordW') == 2 and kinds.count('rune') == 2
    assert kinds.count('word') == 1 and kinds.count('bracket') == 1
    # every C door follows an S door, so the cursor lands on the wrong tail and
    # `jC` rewrites it with no `^w` to spend (uniform nav, honest par)
    for i, k in enumerate(kinds):
        if k == 'ceol':
            assert i > 0 and kinds[i - 1] == 'sline', f"C door {i} must follow an S door"


def test_label_target_shapes():
    """sline: one dissimilar wrong word, cure EXACTLY 6 letters (the S→C
    alignment law). ceol: kept 4-letter floor word + a two-word junk tail
    collapsing to the famous word. word: one word off, tail kept. wordW: a
    ★-scarred famous word, context kept. rune: a fused ◆ head → two letters.
    bracket: a wrong (bracketed) head on the famous stem. No typed value
    holds a space (fixed texts — checked once)."""
    for L in _ce_pick(random.Random(0)):
        assert ' ' not in L['typed'], "no typed value may contain a space"
        if L['kind'] == 'sline':
            assert ' ' not in L['label'] and ' ' not in L['target']
            assert L['typed'] == L['target'] and L['label'] != L['target']
            assert len(L['typed']) == 6, "the alignment law: S cures are 6"
        elif L['kind'] == 'ceol':
            lw, tw = L['label'].split(), L['target'].split()
            assert len(lw) == 3 and len(tw) == 2          # 'pre badA badB' → 'pre right'
            assert lw[0] == tw[0] and len(lw[0]) == 4, \
                "prefix kept, 4 letters (the alignment law)"
            assert L['typed'] == tw[1]
            assert tw[1] not in (lw[1], lw[2]), "the tail is genuinely wrong"
        elif L['kind'] == 'word':
            lw, tw = L['label'].split(), L['target'].split()
            assert lw[1:] == tw[1:] and lw[0] != tw[0]    # tail kept
            assert L['typed'] == tw[0]
        elif L['kind'] == 'wordW':
            lw, tw = L['label'].split(), L['target'].split()
            assert _CE_SYMBOL in lw[0], "the head WORD spans the ★ (ce stops; cE crosses)"
            assert lw[1:] == tw[1:], "context kept"
            assert L['typed'] == tw[0]
            assert _CE_SYMBOL not in tw[0], "the target head is plain"
        elif L['kind'] == 'bracket':
            lw = L['label'].split()
            assert lw[0].startswith('(') and ')' in lw[0], "a bracketed head"
            stem = lw[0].split(')', 1)[1]                  # '(al)gether' → 'gether'
            assert L['target'] == L['typed'] + stem, "c% swaps only the bracket span"
            assert len(L['typed']) == 2
        else:
            assert L['label'].startswith(_CE_PLACEHOLDER)
            assert L['typed'] == L['target'][:2] and len(L['typed']) == 2
            assert L['target'][2:] == L['label'][1:], "the fused head hides 2 letters"


def test_doors_independent():
    """No target is a substring of another target or of any label, so each
    change opens exactly its own bolt (fixed texts — checked once)."""
    lessons = _ce_pick(random.Random(0))
    targets = [L['target'] for L in lessons]
    labels = [L['label'] for L in lessons]
    for i, t in enumerate(targets):
        for j, u in enumerate(targets):
            if i != j:
                assert t not in u, (t, u)
        for lb in labels:
            assert t not in lb, (t, lb)


def test_s_doors_resist_cheap_old_tool_edits():
    """The S/C-forcing margin is a single key (budget = par + SAVING − 1), so
    an S door whose wrong/right words were SIMILAR could fall to r/count-s for
    under the shorthand. The fixed pairs differ in the first AND last char and
    in >= 4 positions, so the cheapest old-tool rewrite is `{6}s` = `cc`'s
    cost, never less."""
    for L in _ce_pick(random.Random(0)):
        if L['kind'] == 'sline':
            assert _whole_line_dissimilar(L['label'], L['target']), \
                (L['label'], L['target'])


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
def test_stone_prefixes_survive_every_change(seed, monkeypatch):
    """The carved saying prefixes are untouched by the floor edits: after the
    whole route (every kind of edit) each still reads across the stone."""
    dungeon = build_dungeon_change_extension(seed)
    room = dungeon.rooms[0]
    def stones():
        return sorted((ru.row, ru.col, ru.symbols)
                      for ru in room.char_runs if ru.kind == 'verdant')
    want = stones()
    _drive(dungeon, _change_keys(room._ce_lessons), monkeypatch)
    assert stones() == want, "a carved prefix was disturbed by an edit"


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
    """All labels but the last true leaves the final bolt shut, so the exit
    (plain floor, east of the bolts) stays UNREACHABLE — the bolts are a series
    gate."""
    dungeon = build_dungeon_change_extension(seed)
    room = dungeon.rooms[0]
    lessons = room._ce_lessons
    keys = []
    for i, L in enumerate(lessons[:-1]):               # drive all but the last door
        keys += _K('' if i == 0 else _CE_PREFIX[L['kind']])
        keys += _K(_CE_VERB[L['kind']])
        keys += _K(L['typed']) + [ESC]
    keys += _K('j')                                    # toward the gate, no change
    _drive(dungeon, keys, monkeypatch, finish=':q!\r')
    last = _CE_TRIGGERS - 1
    assert room.cells[_bolt(last)[0]][_bolt(last)[1]] == CellType.WALL, "final bolt shut"
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
