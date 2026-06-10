"""The Waypoint Sanctum (marks: m ' `; applies / ?).

A sealed, wordless sanctum corridor set HIGH in the map — a thin prose danger band
above it (holding the gold key) and a huge prose danger room filling the bottom,
both crawling with goblins, both reachable only by teleport.  Treasure teases
(chests/hearts behind keyless locks) line the bottom wall.  Search ferries you out
for the gold exit key; the wordless corridor can't be searched back to, so a mark is
the way home — and teleporting (search / mark) is the only survivable way past the
goblin horde.  'a reaches the optional scroll nook (sanctum row's first-left cell),
`a the exact spawn at the sanctum centre, ? the backward key past forward decoys.
The sanctum sits high so M never lands on the scroll.  Structure fixed; only prose
decor varies by seed.
"""
import pytest

from generation.dungeon_gen import (
    build_dungeon_waypoint_sanctum as _build,
    _WP_PAR, _WP_ANSWER, _WP_KEYWORD, _WP_SCROLL, _WP_SPAWN,
    _WP_LOCK, _WP_EXIT, _WP_KEY, _WP_KEY_WORD_POS, _WP_DECOY_POS, _WP_CROW,
    _WP_DANGER_ROWS,
)
from engine.world import CellType
from engine.player import Player
from engine.motion import apply_motion, _first_non_blank_col
from engine.search import find_next

SEEDS = [1, 42, 999, 12345, 2 ** 20 + 7]


def _room(seed):
    return _build(seed).rooms[0]


def _positions(room, word):
    return sorted((ru.row, ru.col) for ru in room.char_runs
                  if ''.join(ru.symbols) == word)


# ── answer simulator (marks + search + chest + key + lock; main.py costs) ────
def _simulate(answer, room):
    """Run a space-separated answer; returns (pos, spent, reached_exit, got_scroll)."""
    p = Player(row=room.spawn_pos[0], col=room.spawn_pos[1])
    marks: dict = {}
    reg_key = False
    got_scroll = False
    last = None
    spent = 0

    def _open_lock():
        room.entities = [e for e in room.entities
                         if not (e.kind == 'locked_door' and (e.row, e.col) == _WP_LOCK)]
        room.rebuild_indexes()

    for tok in answer.split():
        if tok.startswith('m') and len(tok) == 2:                 # m{a}
            marks[tok[1]] = (p.row, p.col)
            spent += 2
        elif tok.startswith("'") and len(tok) == 2:               # '{a} -> first non-blank
            mr, _ = marks[tok[1]]
            p.row, p.col = mr, _first_non_blank_col(room, mr)
            spent += 2
        elif tok.startswith('`') and len(tok) == 2:               # `{a} -> exact
            p.row, p.col = marks[tok[1]]
            spent += 2
        elif '⏎' in tok:                                          # /pat⏎ or ?pat⏎
            fwd = tok[0] == '/'
            pat = tok[1:-1]
            last = (pat, fwd)
            dest = find_next(room, p, pat, fwd)
            assert dest is not None, f'{tok}: no match'
            p.row, p.col = dest
            spent += len(pat) + 2
        elif tok in ('n', 'N'):
            pat, base = last
            p.row, p.col = find_next(room, p, pat, (not base) if tok == 'N' else base)
            spent += 1
        elif tok == 'x':
            ent = room.entity_at(p.row, p.col)
            if ent is not None and ent.kind == 'chest_scroll':
                got_scroll = True
                room.kill_entity(ent)
            elif ent is not None and ent.kind == 'floor_key':
                reg_key = True
                room.kill_entity(ent)
            spent += 1
        elif tok == 'p':
            assert reg_key and abs(p.row - _WP_LOCK[0]) + abs(p.col - _WP_LOCK[1]) == 1
            _open_lock()
            p.row, p.col = _WP_LOCK
            spent += 1
        else:                                                     # motion (maybe counted)
            i = 0
            while i < len(tok) and tok[i] in '123456789':
                i += 1
            n = int(tok[:i]) if i else 1
            apply_motion(p, tok[i:], n, room, count_given=(i > 0))
            spent += (len(tok[:i]) + 1) if i else 1
    return (p.row, p.col), spent, (p.row, p.col) == _WP_EXIT, got_scroll


# ── structure (per seed) ─────────────────────────────────────────────────────
@pytest.mark.parametrize('seed', SEEDS)
def test_dimensions_and_budget(seed):
    room = _room(seed)
    assert (room.rows, room.cols) == (19, 46)
    assert room.par == _WP_PAR == 20
    assert room.budget == 28                       # ceil(20 * 1.4)


@pytest.mark.parametrize('seed', SEEDS)
def test_corridor_is_wordless_and_walled_off(seed):
    room = _room(seed)
    # the mark row (5) carries no characters and rows 4 & 6 are a WATER moat
    # (impassable) -> the sanctum still can't be searched home, and the { / }
    # paragraph jumps that used to land on the wordless rows 4/6 now skip them like
    # walls and resolve to the sealed nook, so marks stay the only way in.
    assert not any(ru.row == 5 for ru in room.char_runs)
    assert all(room.cells[4][c] == CellType.WATER for c in range(5, 43))
    assert all(room.cells[6][c] == CellType.WATER for c in range(5, 43))
    # the sanctum is sealed from the danger rooms above and below: the top seal is a
    # solid wall, the bottom seal a wall pierced only by keyless ('blue') vault doors
    # — every cell of both rows is impassable, so no foot route crosses.
    assert all(room.cells[3][c] == CellType.WALL for c in range(room.cols))
    assert all(not room.is_passable(7, c) for c in range(room.cols))
    # the prose danger rooms DO carry text (search fodder + the key word)
    assert any(ru.row in (1, 2) for ru in room.char_runs)
    assert any(8 <= ru.row <= 17 for ru in room.char_runs)


@pytest.mark.parametrize('seed', SEEDS)
def test_danger_room_crawls_with_goblins(seed):
    room = _room(seed)
    goblins = [e for e in room.entities if e.kind == 'goblin']
    assert len(goblins) >= 40                       # crawling
    assert all(g.row in _WP_DANGER_ROWS for g in goblins)   # all in the danger rooms


@pytest.mark.parametrize('seed', SEEDS)
def test_entities_and_search_words(seed):
    room = _room(seed)
    ent = {}
    for e in room.entities:
        ent.setdefault(e.kind, []).append((e.row, e.col, e.tag))
    assert (_WP_SCROLL[0], _WP_SCROLL[1], '') in ent['chest_scroll']
    assert (_WP_EXIT[0], _WP_EXIT[1], '') in ent['exit']
    assert (_WP_LOCK[0], _WP_LOCK[1], 'gold') in ent['locked_door']     # gold exit lock
    assert (_WP_KEY[0], _WP_KEY[1], 'gold') in ent['floor_key']         # gold key
    # treasure teases: relic-scroll chests + hearts behind 'blue' locks (no blue key)
    assert len(ent.get('chest_scroll', [])) + len(ent.get('heart_container', [])) >= 8
    assert any(tag == 'blue' for (_, _, tag) in ent['locked_door'])
    # one real key word (backward) + the forward decoys; nothing else matches
    assert _positions(room, _WP_KEYWORD) == sorted([_WP_KEY_WORD_POS] + _WP_DECOY_POS)
    for ru in room.char_runs:
        w = ''.join(ru.symbols)
        if w != _WP_KEYWORD:
            assert _WP_KEYWORD not in w


@pytest.mark.parametrize('seed', SEEDS)
def test_apostrophe_reaches_scroll_backtick_reaches_lock(seed):
    """'a → the scroll room (corridor's first-left cell); `a → the exit-lock approach."""
    room = _room(seed)
    assert _first_non_blank_col(room, _WP_CROW) == _WP_SCROLL[1]          # 'a target
    assert _WP_SPAWN != _WP_SCROLL and _WP_SPAWN[1] > _WP_SCROLL[1]       # `a target distinct, deeper


@pytest.mark.parametrize('seed', SEEDS)
def test_backward_search_is_the_direct_key_fetch(seed):
    """From the scroll cell, ?cipher lands on the real key; /cipher hits a forward
    decoy first — so ? is the direct fetch (/ would need n-wrapping)."""
    room = _room(seed)
    p = Player(row=_WP_SCROLL[0], col=_WP_SCROLL[1])
    assert find_next(room, p, _WP_KEYWORD, False) == _WP_KEY_WORD_POS
    assert find_next(room, p, _WP_KEYWORD, True) in _WP_DECOY_POS


@pytest.mark.parametrize('seed', SEEDS)
def test_exit_is_teleport_safe(seed):
    room = _room(seed)
    assert _first_non_blank_col(room, _WP_CROW) != _WP_EXIT[1]
    assert not room.is_passable(*_WP_LOCK)            # exit lock blocks
    assert room.is_passable(*_WP_EXIT)
    er, ec = _WP_EXIT
    nbrs = [(er + dr, ec + dc) for dr, dc in ((1, 0), (-1, 0), (0, 1), (0, -1))
            if 0 <= er + dr < room.rows and 0 <= ec + dc < room.cols
            and room.cells[er + dr][ec + dc] == CellType.CORRIDOR]
    assert nbrs == [_WP_LOCK]                          # only way to the exit is the lock


def test_M_never_lands_on_the_scroll():
    """The sanctum sits HIGH, so M (jump to the middle visible row's first cell) is
    pulled DOWN into the goblin room — never onto the scroll nook — at every realistic
    terminal height.  Using M to cheat the scroll backfires instead of rewarding."""
    room = _room(42)
    for game_h in [0] + list(range(11, 51)):           # 0 = whole-room view; 11+ = playable
        p = Player(row=_WP_SPAWN[0], col=_WP_SPAWN[1])
        apply_motion(p, 'M', 1, room, game_h=game_h)
        assert (p.row, p.col) != _WP_SCROLL, f'M freebies the scroll at game_h={game_h}'
    # at a near-full-room view M drops you INTO the danger room below the sanctum
    p = Player(row=_WP_SPAWN[0], col=_WP_SPAWN[1])
    apply_motion(p, 'M', 1, room, game_h=room.rows - 1)
    assert p.row in _WP_DANGER_ROWS and p.row > _WP_CROW


# ── par path (structure is seed-independent: run once) ───────────────────────
def test_answer_solves_within_budget_and_takes_the_scroll():
    room = _room(42)
    pos, spent, reached, got_scroll = _simulate(_WP_ANSWER, room)
    assert reached, f'answer ended at {pos}, not the exit {_WP_EXIT}'
    assert got_scroll, 'the par route loots the :set number scroll via \'a'
    assert spent == _WP_PAR == 20
    assert spent <= room.budget


def test_skipping_the_scroll_beats_par():
    room = _room(42)
    skip = _WP_ANSWER.replace("'a x ", "")            # drop the scroll detour
    pos, spent, reached, got_scroll = _simulate(skip, room)
    assert reached and not got_scroll
    assert spent == _WP_PAR - 3 == 17
    assert spent < _WP_PAR


# ── :set number gutter (the scroll's payoff) + scroll-drop wiring ────────────
def test_only_the_left_nook_holds_the_numbered_ledger():
    """The left-chamber nook chest carries scroll_id 'setnum' (the Numbered
    Ledger); the row-9 vault chests carry no scroll_id, so they drop random
    relic scrolls.  The level is no longer a per-level forced 'setnum' drop."""
    import main
    room = _room(42)
    nook = next(e for e in room.entities
                if e.kind == 'chest_scroll' and (e.row, e.col) == _WP_SCROLL)
    assert nook.scroll_id == 'setnum'
    row9 = [e for e in room.entities if e.kind == 'chest_scroll' and e.row == 9]
    assert row9 and all(e.scroll_id == '' for e in row9)
    assert 'waypoint_sanctum' not in main._SCROLL_DROPS


def test_set_number_renders_a_line_gutter(capsys):
    """player.number_mode toggles a dungeon line-number gutter; default 'none'
    leaves the frame ungutted.  In relativenumber the cursor's own line reads 0."""
    from blessed import Terminal
    import render.colors as C
    import render.symbols as S
    from render.renderer import render_all
    from engine.budget import Budget
    t = Terminal(); C.init(t); S.init(t)
    d = _build(42)
    p = Player(row=_WP_CROW, col=_WP_SPAWN[1])

    p.number_mode = 'none'
    render_all(t, d, p, Budget(total=27), '')
    plain = capsys.readouterr().out

    p.number_mode = 'number'
    render_all(t, d, p, Budget(total=27), '')
    numbered = capsys.readouterr().out

    p.number_mode = 'relativenumber'
    render_all(t, d, p, Budget(total=27), '')
    relative = capsys.readouterr().out

    assert numbered != plain                           # the gutter changes the frame
    assert relative != plain
    assert '  0 ' in relative                          # cursor line = 0 (relativenumber)
    assert '  0 ' not in plain                         # default: no gutter
    assert '  0 ' not in numbered                      # absolute mode never shows 0
