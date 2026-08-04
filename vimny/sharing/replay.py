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

"""Headless replay of a keystroke tape — the keystone of the sharing pipeline.

A tape (`room.answer`) is a literal keystroke string. Replaying it through the
real game loop with rendering silenced yields two facts at once:

  * **solvability** — did the route reach the exit and win?
  * **cost** — how many keystrokes did it spend?

That is why one artifact does both jobs the pipeline needs. A community author
cannot write a Dijkstra solver, but they can play their own level; the replay
turns that recording into a par and a proof of solvability in the same pass.

Pointed at the SHIPPED curriculum instead, the same function audits the game's
central invariant. Every shipped par claims a hand-written solver found the
cheapest route; a tape that finishes under par falsifies that claim with its own
reproduction attached. See `docs/blueprints/level_sharing.md` §1a — a confirmed beat
is a solver bug report, not a score.

The honest limit: a replay measures THE ROUTE IT IS GIVEN. It proves an upper
bound on par, never an optimum. Community levels must say "author's par".
"""
from __future__ import annotations

import contextlib
from dataclasses import dataclass, field

from blessed import Terminal
from blessed.keyboard import Keystroke

from vimny.engine import tape as _tape

# H/M/L land relative to the VIEWPORT, so a replay in a short terminal walks a
# different route than the one the tape was recorded against — silently, and
# only on the levels that use them. 33 playable rows plus the 8 rows of chrome
# the renderer reserves is taller than the tallest room, so the whole map is on
# screen and H/M/L mean what the author meant. (Learned the hard way: at 30 the
# Screen Vault's tape "failed to win" and the level looked broken.)
REPLAY_TERM_HEIGHT = 33 + 8

# The animation and scroll entry points a replay must not enter. The scroll
# viewers matter most: they read their dismiss key through a direct
# `term.inkey()` that bypasses the main key loop, so an un-silenced one would
# swallow a tape keystroke and desync everything after it.
_SILENCED = (
    'render_all',
    # Every `_*_animation` in main.py. They write escape sequences straight to
    # stdout rather than through render_all, so silencing the renderer alone
    # still leaves a replay spraying cursor moves over the caller's output.
    '_unlock_animation', '_sc_twinkle_animation', '_explosion_animation',
    '_void_fall_animation', '_drown_animation', '_heart_container_animation',
    '_win_animation', '_fireworks_animation',
    '_combat_flash', '_death_animation', '_starfield_victory',
    '_show_scroll_by_id', '_render_standard_scroll',
    '_show_reliquary_scroll', '_show_catalog_scroll',
)


@dataclass
class ReplayResult:
    """What a tape did. `won` and `spent` are the two fields that matter."""
    won:    bool = False
    stars:  int = 0
    spent:  int = 0
    par:    int | None = None
    error:  str = ''            # why the replay could not finish, '' if it did
    keys:   int = 0             # tape keystrokes actually consumed

    @property
    def ok(self) -> bool:
        return self.won and not self.error


def tape_to_keys(tape: str, term=None) -> list:
    """Turn a tape string into the Keystrokes the game loop reads.

    The notation lives in `vimny/engine/tape.py` — plain spaces are DISPLAY separators
    and are stripped, which is why a typed space is `<Space>`, a typed Enter `<CR>`, and
    Esc `<Esc>`.
    """
    return _tape.to_keys(tape, term)


@contextlib.contextmanager
def _headless(main):
    """Silence rendering, sleeps and the scroll sub-loops for the duration.

    Patch-and-restore rather than a flag threaded through the game loop: the
    replayer is a tool standing outside the game, and making the loop itself
    aware of being replayed would put test scaffolding in the product path.
    """
    saved = {name: getattr(main, name) for name in _SILENCED if hasattr(main, name)}
    saved_sleep   = main.time.sleep
    saved_height  = Terminal.height
    noop = lambda *a, **k: None
    try:
        for name in saved:
            setattr(main, name, noop)
        main.time.sleep = noop
        Terminal.height = REPLAY_TERM_HEIGHT      # a property on the CLASS
        yield
    finally:
        for name, fn in saved.items():
            setattr(main, name, fn)
        main.time.sleep  = saved_sleep
        Terminal.height  = saved_height


def replay_tape(dungeon, slug: str, tape: str, *,
                known: list | None = None,
                player_name: str = 'Normand') -> ReplayResult:
    """Play `tape` through the real game loop and report what happened.

    `dungeon` is consumed — the loop mutates it — so pass a fresh build, never a
    cached one. `known` overrides the learned-command set for a community level,
    which has no curriculum position to derive one from.

    A tape that neither wins nor quits is the interesting failure: the route
    stranded, or an unterminated insert swallowed the trailing `:wq` as text. It
    is reported as an error rather than raised, because the validator's job is to
    tell an author WHICH rule they broke.
    """
    import main

    term = Terminal(force_styling=False)
    keys  = tape_to_keys(tape, term)
    keys += [Keystroke(ch) for ch in ':wq\r']   # :wq is what reports the real win
    state = {'n': 0, 'overrun': False}

    def _inkey(*a, **k):
        if state['n'] < len(keys):
            key = keys[state['n']]
            state['n'] += 1
            return key
        state['overrun'] = True
        # Escape, then quit without saving: unwinds a stuck INSERT/VISUAL mode so
        # the loop returns instead of hanging on a tape that never terminated.
        raise _TapeExhausted()

    term.inkey = _inkey
    import vimny.render.colors as colors
    colors.init(term)              # combat and key colour paths call color_rgb()

    with _headless(main):
        try:
            result = main.run_dungeon(term, slug, {}, player_name=player_name,
                                      _dungeon=dungeon, _known=known)
        except _TapeExhausted:
            return ReplayResult(
                error=('the tape and the trailing :wq ran out before the level '
                       'returned — the route never reached the exit, or an '
                       'unterminated insert swallowed the :wq as typed text'),
                keys=min(state['n'], len(_tape.strip_separators(tape))))

    return ReplayResult(
        won=bool(result.get('won')),
        stars=int(result.get('stars', 0)),
        spent=int(result.get('spent', 0)),
        par=result.get('par'),
        keys=len(_tape.strip_separators(tape)),
    )


class _TapeExhausted(Exception):
    """Internal: the loop asked for a key after the tape and :wq were spent."""
