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

"""No shipped level may ask its player to change a line they cannot see.

REPLAY PLAYS BLIND. The par audit proves every tape wins and costs what it
claims; the round-trip probe proves every level rebuilds from its file. Neither
ever asks what the PLAYER could see — and two shipped levels failed exactly
there: six of the Shelving Room's verses were manipulated blind (invisible
until 2026-08-23), and a lit chest beckoned from behind three shut bolts.

THE LAW: between one rendered frame and the next, any row whose TEXT changed
must have been fully LEGIBLE before the change — every glyph cell out of the
fog (misted floor counts: ink shows through haze) and out from under a veil.
A row you cannot read is not a row you can edit. Scripted EVENTS that write in
the dark belong in `VISIBILITY_GAPS` below, with a reason, exactly like
KNOWN_GAPS: an unlisted violation is a regression, and a listed one that
stopped happening is a stale exemption.

Mechanism: `run_dungeon` renders once per processed action, so a capturing
`render_all` is a per-turn eye. Each frame records every row's glyphs plus
which of their cells were hidden; consecutive frames diff. One seed per level:
fog derives from geometry, not from fill words.
"""
import pytest
from blessed import Terminal
from blessed.keyboard import Keystroke

import vimny.game as main
import vimny.render.colors as C
from vimny.content.levels import LEVELS, NO_SINGLE_TAPE

SEED = 1

#: Scripted dark-writes, by slug, with the reason they are legal. Empty today;
#: an entry here is a claim about DESIGN, not a shrug.
VISIBILITY_GAPS: dict[str, str] = {}

#: The levels that live on darkness — watched twice: once in the sweep below,
#: once here as a named fast gate, because this family produced both real
#: sight bugs. Redundancy on purpose: if the sweep is ever gated for speed,
#: the family that taught us the law stays guarded in the inner loop.
_FOG_FAMILY = ['gauntlet', 'refrain_vault', 'shelving_room',
               'waypoint_sanctum']

_ANIMS = ('_fireworks_animation', '_win_animation', '_starfield_victory',
          '_heart_container_animation', '_unlock_animation',
          '_void_fall_animation', '_drown_animation',
          '_sc_twinkle_animation')


@pytest.fixture(autouse=True)
def _headless_loop(monkeypatch):
    """The drive is headless: no sleeps, no animations, no terminal."""
    monkeypatch.setattr(main.time, 'sleep', lambda *a, **k: None)
    for anim in _ANIMS:
        monkeypatch.setattr(main, anim, lambda *a, **k: None)
    monkeypatch.setattr(Terminal, 'height', property(lambda self: 45))
    monkeypatch.setattr(Terminal, 'width', property(lambda self: 120))


def _row_snapshot(room) -> dict:
    """One frame's text: row -> (glyphs, hidden glyph columns).

    A glyph cell is HIDDEN when the fog holds it without mist over it (plain
    fog draws blank until revealed) or when a veil covers it. Misted glyphs
    render through the haze — ink shows through weather — so they are seen."""
    fog, mist = room.fog_cells, room.underwater_cells
    veiled = getattr(room, 'veiled_cells', ())
    out: dict[int, tuple[str, tuple]] = {}
    for ru in room.char_runs:
        prev_text, prev_hidden = out.get(ru.row, ('', ()))
        syms, hidden = [], list(prev_hidden)
        for i, sym in enumerate(ru.symbols):
            c = ru.col + i
            syms.append(sym)
            if ((ru.row, c) in fog and (ru.row, c) not in mist) \
                    or (ru.row, c) in veiled:
                hidden.append(c)
        out[ru.row] = (prev_text + ''.join(syms), tuple(sorted(hidden)))
    return out


def _violations(slug: str, seed: int = SEED) -> list[str]:
    """Drive the canonical tape; report every blind edit as a finding.

    The drive mirrors `sharing.replay.replay_tape` exactly — same key feeding,
    same exhausted-tape unwind, same `_headless` silencing — so a tape the
    validator accepts terminates here too."""
    from vimny.sharing.replay import _TapeExhausted, _headless, tape_to_keys
    import vimny.generation.dungeon_gen as dg
    dungeon = getattr(dg, f'build_dungeon_{slug}')(seed)

    frames: list = []
    orig_render = main.render_all

    def eye(term, d, player, *a, **k):
        # run_dungeon renders once per processed action: a per-turn eye.
        frames.append((id(d.room), _row_snapshot(d.room)))

    term = Terminal(force_styling=False)
    keys = tape_to_keys(dungeon.room.answer or '', term)
    keys += [Keystroke(ch) for ch in ':wq\r']
    state = {'n': 0}

    def inkey(*a, **k):
        if state['n'] < len(keys):
            key = keys[state['n']]
            state['n'] += 1
            return key
        raise _TapeExhausted()       # unwind a stuck mode instead of spinning

    main.render_all = eye
    try:
        with _headless(main):
            C.init(Terminal(force_styling=True))
            term.inkey = inkey
            try:
                main.run_dungeon(term, slug, {}, player_name='Scribe',
                                 _dungeon=dungeon)
            except _TapeExhausted:
                pass                 # the frames we got are still evidence
    finally:
        main.render_all = orig_render

    bad = []
    for (prev_room, prev), (cur_room, cur) in zip(frames, frames[1:]):
        if prev_room != cur_room:
            continue                      # a door turned — new room, new eyes
        bad.extend(_blind_edits(prev, cur))
    return bad


def _blind_edits(prev: dict, cur: dict) -> list[str]:
    """Rows whose text changed while some of their glyphs were hidden."""
    bad = []
    for row, (text_now, _) in cur.items():
        text_before, hidden_before = prev.get(row, ('', ()))
        if text_now == text_before or not hidden_before:
            continue
        bad.append(f'row {row} rewritten with {len(hidden_before)} '
                   f'invisible glyph(s) ({text_before!r} -> {text_now!r})')
    return bad


@pytest.mark.parametrize('slug', sorted(
    l['slug'] for l in LEVELS if l['slug'] not in NO_SINGLE_TAPE))
def test_no_blind_edits_on_the_canonical_route(slug):
    bad = _violations(slug)
    surprise = [b for b in bad if slug not in VISIBILITY_GAPS]
    if surprise:
        raise AssertionError(
            f'{slug}: the canonical route edits lines the player cannot see:\n'
            '  ' + '\n  '.join(surprise)
            + '\nIf a scripted event genuinely writes in the dark, add the '
              'slug to VISIBILITY_GAPS with the reason — and say it out loud.')


@pytest.mark.parametrize('slug', sorted(VISIBILITY_GAPS))
def test_a_listed_gap_that_stopped_happening_is_stale(slug):
    bad = [b for b in _violations(slug)]
    assert bad, (f'{slug}: listed in VISIBILITY_GAPS but no longer violates — '
                 'delete the entry (and take the win).')


@pytest.mark.parametrize('slug', _FOG_FAMILY)
def test_the_fog_family_is_watched_by_name(slug):
    assert not _violations(slug)


def test_the_law_bites():
    """Guard the guard: the diff flags a rewrite of a hidden row and passes a
    rewrite of a visible one — without this, a refactor could hollow the audit
    out while it kept passing (the exact failure mode the par-optimum module
    documents)."""
    prev = {5: ('old text', (0, 1, 2)),          # row 5 fully hidden
            6: ('seen', ())}
    cur  = {5: ('new text', ()),
            6: ('seen!', ())}
    bad = _blind_edits(prev, cur)
    assert len(bad) == 1 and 'row 5' in bad[0], bad
    assert _blind_edits({6: prev[6]}, cur) == [], \
        'a fully-visible rewrite is lawful'
