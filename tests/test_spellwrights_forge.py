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

"""The Spellwright's Forge: three chambers, each forcing a different member of the
:s / :g family, driven through the real run_dungeon keystroke loop — and each a
rhyme everyone knows (sense, not decree):

  A — the DUCK'S MOOS   : 'moo' repeats within each line → :%s/moo/quack/g (/g).
  B — HICKORY DICKORY   : the mouse ran DOWN where the famous line runs UP, but
                          the middle line's 'ran down' is TRUE → surgical :s + &
                          (a whole-buffer :%s would wreck the protected line).
  C — TWINKLE TWINKLE   : its two famous lines amid three lines of nonsense
                          static — nothing to fix, only strike → :g/krzzt/d.

The sanctum seal dissolves only when every line that must remain reads its exact
text and no line of static survives."""
import pytest
from blessed import Terminal
from blessed.keyboard import Keystroke

import vimny.game as main
import vimny.generation.dungeon_gen as dg
import vimny.engine.substitute as S
from vimny.engine.tape import to_keys


def _ks(c, name=None):
    return Keystroke(c, name=name)


@pytest.fixture(autouse=True)
def _no_anim(monkeypatch):
    # The victory animations need an initialised colours module; stub them out.
    for fn in ('_win_animation', '_fireworks_animation', '_starfield_victory'):
        monkeypatch.setattr(main, fn, lambda *a, **k: None)


def _run(level, keys, *, player_name='admin', dungeon=None):
    term = Terminal(force_styling=False)
    it = iter([_ks(c) if not isinstance(c, Keystroke) else c for c in keys])
    term.inkey = lambda *a, **k: next(it, _ks(''))
    seen = []
    def cap(t, dn, pl, bg, message='', *a, **k):
        seen.append(message)
    main.render_all = cap
    # Pin the screen height: the route uses `M`, whose landing row depends on
    # the terminal's size. A real shell and an xdist worker disagree — and a
    # half-mended route must not accidentally complete just because the test
    # ran beside a taller terminal.
    saved_h = Terminal.height
    Terminal.height = property(lambda self: 45)
    try:
        res = main.run_dungeon(term, level, {}, player_name=player_name,
                               _dungeon=dungeon)
    finally:
        Terminal.height = saved_h
    return res, [m for m in seen if m]


def _texts(room):
    return [S.line_text(room, r)[0] for r in range(room.rows)]


def _seal_open(room):
    return room.cells[dg._FORGE_DOOR][dg._FORGE_DIV] == main.CellType.FLOOR


def _replay(tape):
    """Translate a karaoke answer tape to raw keystrokes: <CR> → Enter, drop the visual
    space separators (no solve here ever types a literal space)."""
    return to_keys(tape)


# ── structure ────────────────────────────────────────────────────────────────
def test_builder_structure():
    d = dg.build_dungeon_spellwrights_forge(1)
    r = d.room
    assert (r.rows, r.cols) == (dg._FORGE_ROWS, dg._FORGE_COLS)
    # The gate is DATA now: the final seal opens the forge door cell.
    door_seal = [s for s in r.seals if s.opens]
    assert len(door_seal) == 1
    assert tuple(door_seal[0].opens[0]) == (dg._FORGE_DOOR, dg._FORGE_DIV)
    assert not _seal_open(r)                          # sealed shut at the start
    kinds = {e.kind for e in r.entities}
    assert 'exit' in kinds
    assert 'entry_marker' not in kinds                # cut 2026-07-17 (the flash)
    txts = _texts(r)
    # Chamber A — three moo lines, each repeating the rot WITHIN the line (forces /g).
    assert sum('moo' in t for t in txts) == 3
    assert all(t.count('moo') >= 2 for t in txts if 'moo' in t)
    # Chamber B — two corrupt 'down' verses + one TRUE down line between them.
    assert sum('down' in t for t in txts) == 3
    # Chamber C — three lines of static + the famous 2-liner between them.
    assert sum('krzzt' in t for t in txts) == 3
    assert any('twinkle' in t for t in txts) and any('wonder' in t for t in txts)


def test_vocabulary_is_chamber_separated():
    # Each chamber's global rite must never reach another's lines: 'moo' lives ONLY in
    # Chamber A (mouse ≠ moo), 'down'/'up' only in B, 'krzzt' only in C.  This is
    # what lets :%s/moo/quack/g be surgical and the rites independent.
    r = dg.build_dungeon_spellwrights_forge(1).room
    A_rows = {rr for rr, _ in dg._FORGE_A_WARDS}
    B_rows = {rr for rr, _ in dg._FORGE_B_CORRUPT} | {dg._FORGE_B_KEEP[0]}
    C_rows = {rr for rr, _ in dg._FORGE_C_CURSED}
    for row, t in enumerate(_texts(r)):
        if 'moo' in t:                     assert row in A_rows, (row, t)
        if 'down' in t or 'up' in t:       assert row in B_rows, (row, t)
        if 'krzzt' in t:                   assert row in C_rows, (row, t)


# ── the three rites: each lesson is forced ───────────────────────────────────
def test_canonical_three_rites_win_two_stars():
    # The full lesson, end to end: :%s/moo/quack/g (Chamber A — the /g flag), then
    # 8G :s/down/up/ + jj & (Chamber B — surgical :s sparing the true line, & to
    # repeat across the gap), then :g/krzzt/d (Chamber C), then the walk out.
    for seed in (1, 42, 999, 12345, 1048583):
        d = dg.build_dungeon_spellwrights_forge(seed)
        assert d.room.par == dg._SPELLWRIGHTS_PAR
        keys = _replay(dg._SPELLWRIGHTS_ANSWER) + list(':wq') + ['\r']
        res, _ = _run('spellwrights_forge', keys, dungeon=d)
        assert res['won'] and res['stars'] == 2, (seed, res)
        assert _seal_open(d.room)


def test_admin_karaoke_tape_advances_through_the_ex_commands():
    # The answer sheet (admin only) must track the :s / :g rites, not stick at the first
    # ':'.  Typing the whole canonical tape consumes it exactly (playhead at the end, never
    # diverged); a player's own :wq finish afterward must not diverge the consumed tape.
    d = dg.build_dungeon_spellwrights_forge(1)
    keys = _replay(dg._SPELLWRIGHTS_ANSWER) + list(':wq') + ['\r']
    _run('spellwrights_forge', keys, player_name='admin', dungeon=d)
    plain = dg._SPELLWRIGHTS_ANSWER.replace(' ', '')
    assert d.room.answer_pos == len(plain), (d.room.answer_pos, len(plain))
    assert d.room.answer_diverged is False


def test_non_admin_has_no_answer_sheet():
    # The karaoke tape is admin-only; a real player never sees or tracks it (room.answer
    # is cleared on entry for non-admins, so the renderer draws no answer sheet).
    d = dg.build_dungeon_spellwrights_forge(1)
    keys = _replay(dg._SPELLWRIGHTS_ANSWER) + list(':wq') + ['\r']
    _run('spellwrights_forge', keys, player_name='Normand', dungeon=d)
    assert d.room.answer == ''
    assert d.room.answer_pos == 0 and d.room.answer_diverged is False


def test_chamber_A_requires_the_g_flag():
    # The moos repeat within the line; :%s/moo/quack (no /g) mends only the first
    # per line, so the mended phrase never appears and the seal stays shut.
    d = dg.build_dungeon_spellwrights_forge(1)
    keys = (list(':%s/moo/quack') + ['\r']                       # NO /g
            + list('8G') + list(':s/down/up/') + ['\r'] + list('jj&')
            + list(':g/krzzt/d') + ['\r']
            + list(':q!') + ['\r'])
    _run('spellwrights_forge', keys, dungeon=d)
    assert not _seal_open(d.room)
    assert any('moo' in t for t in _texts(d.room))               # remnants survive


def test_chamber_B_global_substitute_wrecks_the_protected_line():
    # The lazy whole-buffer down→up also hits the TRUE middle line ('the mouse ran
    # down' after the clock strikes), so its exact text goes missing and the seal
    # will not open — :%s is self-defeating here.
    d = dg.build_dungeon_spellwrights_forge(1)
    keys = (list(':%s/moo/quack/g') + ['\r']
            + list(':%s/down/up/g') + ['\r']                     # wrecks the protected line
            + list(':g/krzzt/d') + ['\r']
            + list(':q!') + ['\r'])
    _run('spellwrights_forge', keys, dungeon=d)
    assert not _seal_open(d.room)
    assert dg._FORGE_B_KEEP[1] not in ' || '.join(_texts(d.room))


def test_chamber_B_ampersand_is_the_par_route():
    # Repeating the verse fix with a second full :s instead of & still WINS but blows par
    # (1 star); only the canonical & route is 2-star.  So & is forced by par, not a gate.
    d = dg.build_dungeon_spellwrights_forge(1)
    keys = (list(':%s/moo/quack/g') + ['\r']
            + list('8G') + list(':s/down/up/') + ['\r']
            + list('jj') + list(':s/down/up/') + ['\r']          # 2nd full :s, not &
            + list(':g/krzzt/d') + ['\r'] + list('6G$')
            + list(':wq') + ['\r'])
    res, _ = _run('spellwrights_forge', keys, dungeon=d)
    assert res['won'] and res['stars'] == 1, res


def test_one_line_cannot_answer_two_of_the_seals_demands():
    """Chamber B's first verse is a SUBSTRING of its second — 'the mouse ran up
    the clock' inside 'the mouse ran up the clock again'. The seal used to ask
    only whether ANY line contained each mended text, so mending the second
    verse satisfied both demands and the first verse never had to be touched.

    That made `&` skippable on the level whose whole job is `:s` / `&` / `:g`:
    `M` instead of `8G` landed the cursor past the first verse and the level
    still opened, two keys under par. Found by `sharing jumpgolf`, which refuses
    to lower a par for a route that drops the lesson.
    """
    d = dg.build_dungeon_spellwrights_forge(1)
    keys = (list(':%s/moo/quack/g') + ['\r']
            + list('M') + list(':s/down/up/') + ['\r']    # lands past verse one
            + list('jj&')
            + list(':g/krzzt/d') + ['\r'] + list('6G$')
            + list(':wq') + ['\r'])
    res, _ = _run('spellwrights_forge', keys, dungeon=d)
    assert not res['won'], 'the seal opened with Chamber B half-mended'
    assert not _seal_open(d.room)


def test_chamber_C_strikes_the_static_and_keeps_the_rhyme():
    # :g/krzzt/d sweeps every line of static at once; the famous 2-liner
    # between them must survive (a blanket delete would lose it and bar the seal).
    d = dg.build_dungeon_spellwrights_forge(1)
    _run('spellwrights_forge', list(':g/krzzt/d') + ['\r'] + list(':q!') + ['\r'],
         dungeon=d)
    blob = ' || '.join(_texts(d.room))
    assert 'krzzt' not in blob
    for _r, keep in dg._FORGE_C_KEEP:              # the rhyme survives
        assert keep in blob


def test_sanctum_scroll_chest_present_and_survives_the_sweep():
    # The reward that balances the empty sanctum: an unassigned chest (→ a
    # random relic scroll) at row 10, last column — ABOVE every falling row,
    # so :g/krzzt/d never collapses it out of the buffer.
    from vimny.engine.world import CellType
    d = dg.build_dungeon_spellwrights_forge(1)
    room = d.room
    chest = [e for e in room.entities if e.kind == 'chest_scroll']
    assert len(chest) == 1
    assert (chest[0].row, chest[0].col) == dg._FORGE_CHEST == (10, dg._FORGE_COLS - 2)
    assert chest[0].scroll_id in (None, '')          # unassigned → random relic
    assert dg._FORGE_CHEST[0] < min(r for r, _ in dg._FORGE_C_CURSED)
    _run('spellwrights_forge', list(':g/krzzt/d') + ['\r'] + list(':q!') + ['\r'],
         dungeon=d)
    still = [e for e in room.entities if e.kind == 'chest_scroll']
    assert len(still) == 1                            # the sweep spared it
    assert room.cells[dg._FORGE_CHEST[0]][dg._FORGE_CHEST[1]] == CellType.FLOOR


def test_snip_mangle_cannot_open_the_seal():
    # The historical cheese: snip one letter from each word to defeat a bare substring
    # check.  The exact-text rule means a mangle never produces the mended phrases.
    d = dg.build_dungeon_spellwrights_forge(1)
    keys = (list(':%s/o//g') + ['\r'] + list(':%s/l//g') + ['\r']
            + list(':q!') + ['\r'])
    _run('spellwrights_forge', keys, dungeon=d)
    assert not _seal_open(d.room)


def test_seal_stays_shut_until_all_three_rites_done():
    d = dg.build_dungeon_spellwrights_forge(1)
    # Mend Chamber A only; Chambers B and C remain → seal stays shut.
    _run('spellwrights_forge', list(':%s/moo/quack/g') + ['\r'] + list(':q!') + ['\r'],
         dungeon=d)
    assert not _seal_open(d.room)


def test_par_and_budget():
    import math
    r = dg.build_dungeon_spellwrights_forge(1).room
    assert r.par == dg._SPELLWRIGHTS_PAR == 44
    assert r.budget == max(math.ceil(44 * 1.4), 60)


def test_par_is_what_the_engine_actually_charges():
    """The par constant used to be hand-tallied, and was 1 too high — nothing
    measured it, because this level is excluded outright from
    tests/test_answer_paths.py. Replay the canonical tape and let the budget
    say what it costs."""
    from vimny.sharing.replay import replay_tape
    from vimny.content.levels import known_commands
    r = dg.build_dungeon_spellwrights_forge(1).room
    res = replay_tape(dg.build_dungeon_spellwrights_forge(1),
                      'spellwrights_forge', r.answer,
                      known=known_commands('spellwrights_forge'))
    assert res.won, f'the canonical tape no longer wins: {res.error}'
    assert res.spent == dg._SPELLWRIGHTS_PAR, (
        f'the tape costs {res.spent} but par claims {dg._SPELLWRIGHTS_PAR}')


def test_hint_bar_surfaces_the_whole_subst_family():
    # The one 'subst' gate unlocks :s, :%s//g, :g/pat/d and & — but only the :s row
    # carries the token, so the bar must expand the family (like / → ? n N) or the
    # :g/pat/d global delete the falling lines NEED would be gated-in yet invisible.
    from vimny.render.hint_bar import hint_text
    from vimny.content.levels import known_commands
    bar = hint_text(known_commands('spellwrights_forge'), 'spellwrights_forge')
    assert ':g/pat/d' in bar       # the global delete is shown...
    assert 'global delete' in bar  # ...with its function named
    assert ':%s//g' in bar and '&' in bar


# ── gating: :s is refused before the Forge teaches it ────────────────────────
def test_substitute_gated_before_forge(monkeypatch):
    # On an early level a non-admin player has not learned 'subst'; :s is refused.
    from vimny.engine.world import Dungeon, Room, RoomType, CharRun, CellType
    d = Dungeon(name='t', seed=1)
    r = Room(room_type=RoomType.ENTRY, rows=1, cols=20)
    r.cells = [[CellType.FLOOR] * 20]
    r.char_runs = [CharRun(0, 1, tuple('foo'), 'ancient')]
    r.spawn_pos = (0, 0); r.budget = 99; r.par = 5; r.answer = ''
    r.rebuild_indexes(); d.rooms = [r]; d.current_room = 0
    _run('first_cave', list(':s/foo/bar/') + ['\r'] + list(':q!') + ['\r'],
         player_name='p', dungeon=d)
    assert 'bar' not in S.line_text(r, 0)[0]       # unchanged — the command was refused
