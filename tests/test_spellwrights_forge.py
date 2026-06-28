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
:s / :g family, driven through the real run_dungeon keystroke loop.

  A — Ember Wards    : 'old' repeats within each line → :%s/old/new/g (the /g flag).
  B — Selfsame Verses: two corrupt 'pale' verses flank a TRUE pale line → surgical
                       :s + & (a whole-buffer :%s would wreck the protected line).
  C — Cursed Litany  : cursed lines amid sacred keepers → :g/cursed/d.

The sanctum seal dissolves only when every line that must remain reads its exact text
and no cursed line survives."""
import pytest
from blessed import Terminal
from blessed.keyboard import Keystroke

import main
import generation.dungeon_gen as dg
import engine.substitute as S


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
    res = main.run_dungeon(term, level, {}, player_name=player_name, _dungeon=dungeon)
    return res, [m for m in seen if m]


def _texts(room):
    return [S.line_text(room, r)[0] for r in range(room.rows)]


def _seal_open(room):
    return room.cells[dg._FORGE_DOOR][dg._FORGE_DIV] == main.CellType.FLOOR


def _replay(tape):
    """Translate a karaoke answer tape to raw keystrokes: ⏎ → Enter, drop the visual
    space separators (no solve here ever types a literal space)."""
    return ['\r' if c == '⏎' else c for c in tape if c != ' ']


# ── structure ────────────────────────────────────────────────────────────────
def test_builder_structure():
    d = dg.build_dungeon_spellwrights_forge(1)
    r = d.room
    assert (r.rows, r.cols) == (dg._FORGE_ROWS, dg._FORGE_COLS)
    assert r._forge_seal == (dg._FORGE_DOOR, dg._FORGE_DIV)
    assert not _seal_open(r)                          # sealed shut at the start
    kinds = {e.kind for e in r.entities}
    assert 'exit' in kinds and 'entry_marker' in kinds
    txts = _texts(r)
    # Chamber A — three ember wards, each repeating the rot WITHIN the line (forces /g).
    assert sum('old' in t for t in txts) == 3
    assert all(t.count('old') >= 2 for t in txts if 'old' in t)
    # Chamber B — two corrupt 'pale' verses + one TRUE pale line between them.
    assert sum('pale' in t for t in txts) == 3
    # Chamber C — three cursed lines + two sacred keepers.
    assert sum('cursed' in t for t in txts) == 3
    assert sum('sacred' in t for t in txts) == 2


def test_vocabulary_is_chamber_separated():
    # Each chamber's global rite must never reach another's lines: 'old' lives ONLY in
    # Chamber A (no incidental cold/gold/holds/bond…), 'pale'/'pure' only in B, 'cursed'
    # only in C.  This is what lets :%s/old/new/g be surgical and the rites independent.
    r = dg.build_dungeon_spellwrights_forge(1).room
    A_rows = {rr for rr, _ in dg._FORGE_A_WARDS}
    B_rows = {rr for rr, _ in dg._FORGE_B_CORRUPT} | {dg._FORGE_B_KEEP[0]}
    C_cursed = {rr for rr, _ in dg._FORGE_C_CURSED}
    for row, t in enumerate(_texts(r)):
        if 'old' in t:                     assert row in A_rows, (row, t)
        if 'pale' in t or 'pure' in t:     assert row in B_rows, (row, t)
        if 'cursed' in t:                  assert row in C_cursed, (row, t)


# ── the three rites: each lesson is forced ───────────────────────────────────
def test_canonical_three_rites_win_two_stars():
    # The full lesson, end to end: :%s/old/new/g (Chamber A — the /g flag), then
    # 8G :s/pale/pure/ + jj & (Chamber B — surgical :s sparing the true line, & to
    # repeat across the gap), then :g/cursed/d (Chamber C), then the walk out.
    for seed in (1, 42, 999, 12345, 1048583):
        d = dg.build_dungeon_spellwrights_forge(seed)
        assert d.room.par == 45
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
    # The wards repeat 'old' within the line; :%s/old/new (no /g) mends only the first
    # per line, so the mended phrase never appears and the seal stays shut.
    d = dg.build_dungeon_spellwrights_forge(1)
    keys = (list(':%s/old/new') + ['\r']                         # NO /g
            + list('8G') + list(':s/pale/pure/') + ['\r'] + list('jj&')
            + list(':g/cursed/d') + ['\r']
            + list(':q!') + ['\r'])
    _run('spellwrights_forge', keys, dungeon=d)
    assert not _seal_open(d.room)
    assert any('old' in t for t in _texts(d.room))               # remnants survive


def test_chamber_B_global_substitute_wrecks_the_protected_line():
    # The lazy whole-buffer pale→pure also hits the TRUE middle line, so its exact text
    # goes missing and the seal will not open — :%s is self-defeating here.
    d = dg.build_dungeon_spellwrights_forge(1)
    keys = (list(':%s/old/new/g') + ['\r']
            + list(':%s/pale/pure/g') + ['\r']                   # wrecks the protected line
            + list(':g/cursed/d') + ['\r']
            + list(':q!') + ['\r'])
    _run('spellwrights_forge', keys, dungeon=d)
    assert not _seal_open(d.room)
    assert dg._FORGE_B_KEEP[1] not in ' || '.join(_texts(d.room))


def test_chamber_B_ampersand_is_the_par_route():
    # Repeating the verse fix with a second full :s instead of & still WINS but blows par
    # (1 star); only the canonical & route is 2-star.  So & is forced by par, not a gate.
    d = dg.build_dungeon_spellwrights_forge(1)
    keys = (list(':%s/old/new/g') + ['\r']
            + list('8G') + list(':s/pale/pure/') + ['\r']
            + list('jj') + list(':s/pale/pure/') + ['\r']        # 2nd full :s, not &
            + list(':g/cursed/d') + ['\r'] + list('6G$')
            + list(':wq') + ['\r'])
    res, _ = _run('spellwrights_forge', keys, dungeon=d)
    assert res['won'] and res['stars'] == 1, res


def test_chamber_C_strikes_the_cursed_and_keeps_the_sacred():
    # :g/cursed/d sweeps every cursed line at once; the sacred keepers between them must
    # survive (a blanket delete would lose them and bar the seal).
    d = dg.build_dungeon_spellwrights_forge(1)
    _run('spellwrights_forge', list(':g/cursed/d') + ['\r'] + list(':q!') + ['\r'],
         dungeon=d)
    blob = ' || '.join(_texts(d.room))
    assert 'cursed' not in blob
    assert 'a sacred vow' in blob and 'a sacred bond' in blob


def test_snip_mangle_cannot_open_the_seal():
    # The historical cheese: snip one letter from each word to defeat a bare substring
    # check.  The exact-text rule means a mangle never produces the mended phrases.
    d = dg.build_dungeon_spellwrights_forge(1)
    keys = (list(':%s/l//g') + ['\r'] + list(':%s/p//g') + ['\r']
            + list(':q!') + ['\r'])
    _run('spellwrights_forge', keys, dungeon=d)
    assert not _seal_open(d.room)


def test_seal_stays_shut_until_all_three_rites_done():
    d = dg.build_dungeon_spellwrights_forge(1)
    # Mend Chamber A only; Chambers B and C remain → seal stays shut.
    _run('spellwrights_forge', list(':%s/old/new/g') + ['\r'] + list(':q!') + ['\r'],
         dungeon=d)
    assert not _seal_open(d.room)


def test_par_and_budget():
    r = dg.build_dungeon_spellwrights_forge(1).room
    assert r.par == 45
    assert r.budget == 63               # max(ceil(45*1.4), 60)


def test_hint_bar_surfaces_the_whole_subst_family():
    # The one 'subst' gate unlocks :s, :%s//g, :g/pat/d and & — but only the :s row
    # carries the token, so the bar must expand the family (like / → ? n N) or the
    # :g/pat/d global delete the cursed lines NEED would be gated-in yet invisible.
    from render.hint_bar import hint_text
    from content.levels import known_commands
    bar = hint_text(known_commands('spellwrights_forge'), 'spellwrights_forge')
    assert ':g/pat/d' in bar       # the global delete is shown...
    assert 'global delete' in bar  # ...with its function named
    assert ':%s//g' in bar and '&' in bar


# ── gating: :s is refused before the Forge teaches it ────────────────────────
def test_substitute_gated_before_forge(monkeypatch):
    # On an early level a non-admin player has not learned 'subst'; :s is refused.
    from engine.world import Dungeon, Room, RoomType, CharRun, CellType
    d = Dungeon(name='t', seed=1)
    r = Room(room_type=RoomType.ENTRY, rows=1, cols=20)
    r.cells = [[CellType.FLOOR] * 20]
    r.char_runs = [CharRun(0, 1, tuple('foo'), 'ancient')]
    r.spawn_pos = (0, 0); r.budget = 99; r.par = 5; r.answer = ''
    r.rebuild_indexes(); d.rooms = [r]; d.current_room = 0
    _run('first_cave', list(':s/foo/bar/') + ['\r'] + list(':q!') + ['\r'],
         player_name='p', dungeon=d)
    assert 'bar' not in S.line_text(r, 0)[0]       # unchanged — the command was refused
