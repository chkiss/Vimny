# Vimny — a Vim-teaching dungeon crawler.
# Copyright (C) 2026 Chas Kissick
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.
#
# SPDX-License-Identifier: GPL-3.0-or-later

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

from vimny.generation.dungeon_gen import (
    build_dungeon_waypoint_sanctum as _build,
    _WP_PAR, _WP_ANSWER, _WP_KEYWORD, _WP_SCROLL, _WP_SPAWN,
    _WP_LOCK, _WP_EXIT, _WP_KEY, _WP_KEY_WORD_POS, _WP_DECOY_POS, _WP_CROW,
    _WP_DANGER_ROWS, _WP_WORD2, _WP_W2_POCKET1, _WP_W2_POCKET2,
    _WP_W2_DECOYS, _WP_PKT1_SPAN, _WP_PKT2_SPAN,
)
from vimny.engine.world import CellType
from vimny.engine.player import Player
from vimny.engine.motion import apply_motion, _first_non_blank_col
from vimny.engine.search import find_next
from vimny.engine.tape import ENTER as TAPE_ENTER

SEEDS = [1, 42, 999, 12345, 2 ** 20 + 7]


def _room(seed):
    return _build(seed).rooms[0]


def _positions(room, word):
    return sorted((ru.row, ru.col) for ru in room.char_runs
                  if ''.join(ru.symbols) == word)


# ── answer simulator (marks + search + chest + key + lock; vimny/game.py costs) ────
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
        elif TAPE_ENTER in tok:                                   # /pat<CR> or ?pat<CR>
            fwd = tok[0] == '/'
            pat = tok[1:-len(TAPE_ENTER)]
            last = (pat, fwd)
            dest = find_next(room, p, pat, fwd)
            assert dest is not None, f'{tok}: no match'
            p.row, p.col = dest
            spent += len(pat) + 1            # '/' charged, closing Enter free
        elif tok in ('n', 'N'):
            pat, base = last
            p.row, p.col = find_next(room, p, pat, (not base) if tok == 'N' else base)
            spent += 1
        elif tok in ('*', '#'):                                   # word under cursor
            ru = room.char_run_at(p.row, p.col)
            assert ru is not None, f'{tok}: no word under cursor'
            pat = ''.join(ru.symbols)
            fwd = tok == '*'
            last = (pat, fwd)
            dest = find_next(room, p, pat, fwd)
            assert dest is not None, f'{tok}: no match for {pat}'
            p.row, p.col = dest
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
        # The waking stone (the main-loop tick, mimicked): landing inside
        # pocket 1 lifts plugh's scripted fog.
        pf = getattr(room, '_wp_plugh_fog', set())
        if (pf and room.fog_cells & pf and p.row == _WP_W2_POCKET1[0]
                and _WP_PKT1_SPAN[0] <= p.col <= _WP_PKT1_SPAN[1]):
            room.fog_cells -= pf
    return (p.row, p.col), spent, (p.row, p.col) == _WP_EXIT, got_scroll


# ── structure (per seed) ─────────────────────────────────────────────────────
@pytest.mark.parametrize('seed', SEEDS)
def test_dimensions_and_budget(seed):
    room = _room(seed)
    assert (room.rows, room.cols) == (19, 46)
    assert room.par == _WP_PAR == 17
    assert room.budget == 24                       # ceil(17 * 1.4)


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
    # the sanctum is sealed from the danger rooms above and below: since the
    # 2026-07-18 waterworks both seals are MISTED WATER pierced only by the
    # keyless ('blue') vault doors — every cell of both rows is impassable
    # (water + fog), so no foot route crosses, and the mist blocks the
    # $ / 0 / ^ / f scans like the stone it replaced.
    for c in range(1, room.cols - 1):
        assert room.cells[3][c] == CellType.WATER
        assert (3, c) in room.fog_cells
    assert all(not room.is_passable(7, c) for c in range(room.cols))
    for c in range(1, room.cols - 1):
        if room.cells[7][c] == CellType.WATER:
            assert (7, c) in room.fog_cells
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
    """From the spawn, ?xyzzy lands on the real key word; /xyzzy hits a forward
    decoy first — so ? is the direct fetch (/ would need n-wrapping)."""
    room = _room(seed)
    p = Player(row=_WP_SPAWN[0], col=_WP_SPAWN[1])
    assert find_next(room, p, _WP_KEYWORD, False) == _WP_KEY_WORD_POS
    assert find_next(room, p, _WP_KEYWORD, True) in _WP_DECOY_POS


@pytest.mark.parametrize('seed', SEEDS)
def test_both_pockets_are_search_only(seed):
    """Both magic-word pockets: interiors stay corridor (search jumps land),
    ringed by misted water (no foot path in, no $ / f scan across, contents
    VISIBLE per the stone-fog law). Pocket 1 holds xyzzy + the waking plugh;
    pocket 2 (strictly WEST — behind, for #) holds plugh's twin + the key."""
    room = _room(seed)
    for span in (_WP_PKT1_SPAN, _WP_PKT2_SPAN):
        lo, hi = span
        for c in range(lo, hi + 1):
            assert room.cells[2][c] == CellType.CORRIDOR, (2, c)
        for rc in ([(2, lo - 1), (2, hi + 1)]
                   + [(1, c) for c in range(lo - 1, hi + 2)]):
            assert room.cells[rc[0]][rc[1]] == CellType.WATER, rc
            assert rc in room.fog_cells, rc
    assert room.cells[_WP_KEY[0]][_WP_KEY[1]] == CellType.CORRIDOR
    assert _WP_PKT2_SPAN[1] < _WP_PKT1_SPAN[0]     # pocket 2 is BEHIND


@pytest.mark.parametrize('seed', SEEDS)
def test_plugh_sleeps_until_the_pocket_is_entered(seed):
    """BOTH sanctum plughs start under scripted fog — fog blocks EVERY
    search uniformly (# included), so ?plugh from the spawn finds nothing
    at all: the fogged pair is skipped, and the unfogged decoys all lie
    FORWARD, out of a backward search's reach. (With only the stone
    fogged, the visible twin was a 15-key skip straight to the key.)"""
    room = _room(seed)
    fogged = {(r, c + i) for (r, c) in (_WP_W2_POCKET1, _WP_W2_POCKET2)
              for i in range(len(_WP_WORD2))}
    assert fogged <= room.fog_cells
    assert fogged == room._wp_plugh_fog
    assert not (fogged & room.mist_cells)          # liftable — NOT mist
    # every plugh stands where designed, nowhere else
    assert _positions(room, _WP_WORD2) == sorted(
        [_WP_W2_POCKET1, _WP_W2_POCKET2] + _WP_W2_DECOYS)
    # the spawn cheese, pinned dead: a backward plugh search skips the
    # fogged pair and WRAPS (Vim-true) onto a forward decoy in the goblin
    # room — never a pocket. Decoy-hopping can't reach the pair either.
    p = Player(row=_WP_SPAWN[0], col=_WP_SPAWN[1])
    hit = find_next(room, p, _WP_WORD2, False)
    assert hit in _WP_W2_DECOYS
    for _ in range(6):                             # walk the whole visible chain
        p.row, p.col = hit
        hit = find_next(room, p, _WP_WORD2, False)
        assert hit in _WP_W2_DECOYS                # the pockets never surface


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
def test_answer_solves_at_par_via_the_forced_search():
    room = _room(42)
    pos, spent, reached, got_scroll = _simulate(_WP_ANSWER, room)
    assert reached, f'answer ended at {pos}, not the exit {_WP_EXIT}'
    assert not got_scroll, 'the par route is the lean forced-search line, no scroll detour'
    assert spent == _WP_PAR == 17
    assert spent <= room.budget


def test_hash_is_forced_by_par():
    """The #-less rival from the plugh stone: * hits a forward decoy and
    N N walks back through the stone to the twin — 3 keys where # pays 1.
    It wins, at 1★ (par+2)."""
    room = _room(42)
    rival = _WP_ANSWER.replace(' # ', ' * N N ', 1)
    pos, spent, reached, _s = _simulate(rival, room)
    assert reached
    assert spent == _WP_PAR + 2
    assert spent <= room.budget                    # wins — but one star


def test_taking_the_scroll_is_an_off_par_bonus():
    """The scroll nook is a reward, not on the par path: detouring for it via 'a x
    costs +3 over par, trading the second star for the relic.  (If it sat ON par,
    skipping it would beat par — the old cheese this redesign removed.)"""
    room = _room(42)
    take = _WP_ANSWER.replace("ma ", "ma 'a x ", 1)   # insert the scroll detour
    pos, spent, reached, got_scroll = _simulate(take, room)
    assert reached and got_scroll
    assert spent == _WP_PAR + 3 == 20
    assert spent > _WP_PAR


def test_driven_canonical_wins_at_par(monkeypatch):
    """The REAL main loop end to end: the ? leg, the tick's plugh reveal,
    the # fetch, the mark home. (The simulator mimics the tick; this one
    proves it.)"""
    import vimny.game as main
    from blessed import Terminal
    from blessed.keyboard import Keystroke
    import vimny.render.colors as C
    import vimny.render.symbols as S
    C.init(Terminal())
    S.init(Terminal())
    d = _build(42)
    keys = [Keystroke(ch) for ch in 'ma?xyzzy\rw#hx`a$pl:wq\r']
    monkeypatch.setattr(main, 'render_all', lambda *a, **k: None)
    monkeypatch.setattr(main.time, 'sleep', lambda *a, **k: None)
    for anim in ('_fireworks_animation', '_win_animation', '_starfield_victory',
                 '_heart_container_animation', '_unlock_animation',
                 '_void_fall_animation', '_drown_animation'):
        monkeypatch.setattr(main, anim, lambda *a, **k: None)
    monkeypatch.setattr(Terminal, 'height', property(lambda self: 41))
    box = {}
    orig = main._calc_stars
    monkeypatch.setattr(main, '_calc_stars',
                        lambda won, budget, room, player, level='':
                            (box.__setitem__('spent', budget.spent),
                             orig(won, budget, room, player, level))[1])
    term = Terminal()
    it = iter(keys)
    monkeypatch.setattr(term, 'inkey', lambda *a, **k: next(it, Keystroke('')))
    result = main.run_dungeon(term, 'waypoint_sanctum', {}, player_name='Scribe',
                              _dungeon=d)
    assert result['won'] and box['spent'] == _WP_PAR


# ── :set number gutter (the scroll's payoff) + scroll-drop wiring ────────────
def test_nook_ledger_and_the_pinned_second_stride():
    """The left-chamber nook chest carries 'setnum' (the Numbered Ledger).
    Among the row-9 vault chests, exactly ONE is pinned to 'redo' (The
    Second Stride — guaranteed here, BEFORE the editing act, instead of
    floating in the random relic pool); the rest pull random relics."""
    import vimny.game as main
    from vimny.content.scrolls import RELIC_SCROLL_IDS
    room = _room(42)
    nook = next(e for e in room.entities
                if e.kind == 'chest_scroll' and (e.row, e.col) == _WP_SCROLL)
    assert nook.scroll_id == 'setnum'
    row9 = [e for e in room.entities if e.kind == 'chest_scroll' and e.row == 9]
    assert sorted(e.scroll_id for e in row9) == [''] * (len(row9) - 1) + ['redo']
    assert 'redo' not in RELIC_SCROLL_IDS, "pinned chests leave the pool"
    assert 'waypoint_sanctum' not in main._SCROLL_DROPS


def test_set_number_renders_a_line_gutter(capsys):
    """player.number_mode toggles a dungeon line-number gutter; default 'none'
    leaves the frame ungutted.  In relativenumber the cursor's own line reads 0."""
    from blessed import Terminal
    import vimny.render.colors as C
    import vimny.render.symbols as S
    from vimny.render.renderer import render_all
    from vimny.engine.budget import Budget
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


def test_hint_bar_surfaces_the_whole_mark_family():
    # The one 'mark' gate unlocks set (m{a}) AND both jumps (`{a} '{a}) — but only the
    # m{a} row carries the token, so the bar must expand the family (like / → ? n N) or
    # the player can set a mark yet never see how to jump back to it.
    from vimny.render.hint_bar import hint_text
    from vimny.content.levels import known_commands
    bar = hint_text(known_commands('waypoint_sanctum'), 'waypoint_sanctum')
    assert 'm{a}' in bar
    assert '`{a}' in bar and "'{a}" in bar             # both jump-to-mark keys shown
