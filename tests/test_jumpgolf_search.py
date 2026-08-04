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

"""THE POSITIVE CONTROL for jumpgolf's search.

Every sweep this tool has run came back clean, and a clean result from a search
nobody has tested is worth very little: "found nothing" and "cannot find
anything" produce identical output. The sweeps could only ever demonstrate the
absence of a beat, never the presence of the ability to find one.

So the search is exercised against cost landscapes with KNOWN answers, injected
through `measure` — no game, no replays, milliseconds. What it proves is that
the algorithm finds a win it is supposed to find, and fails to find one it is
not equipped for. What it does NOT prove is that Vimny's real tapes contain such
a case; that remains unknown, and unknowable without finding one.

The landscape below is the exact shape the beam was added for: a two-edit win
whose FIRST step costs more than where it started. Narrow settings cannot cross
that ridge — not because they are buggy, but because nothing dearer than the
current best is ever explored. Slack is what crosses it.
"""
import pytest

from vimny.sharing import jumpgolf as JG


# ── a landscape with a ridge ────────────────────────────────────────────────
#
# States are single letters. Costs:
#
#     A = 10   the start
#     B = 11   one key DEARER — the ridge
#     C =  8   the prize, reachable ONLY through B
#     D = 10   a tie with the start, going nowhere
#
# Every step is one edit. A->C does not exist: the only path to the prize
# climbs over B.
COSTS = {'A': 10, 'B': 11, 'C': 8, 'D': 10}
EDGES = {'A': ['B', 'D'], 'B': ['C'], 'C': [], 'D': []}


def _successors(state):
    for nxt in EDGES[''.join(state)]:
        yield [nxt], 'sub', 0, ''.join(state), nxt


def _measure(state):
    return COSTS.get(''.join(state))


def _run(**kw):
    best, cost, _parent, evals, capped = JG.beam_search(
        start=['A'], start_cost=COSTS['A'], successors=_successors,
        measure=_measure, **kw)
    return ''.join(best), cost, evals, capped


def _search(**kw):
    """beam_search's full 5-tuple, for the tests that read the tail of it."""
    return JG.beam_search(**kw)


def test_narrow_search_cannot_cross_a_ridge():
    """beam=1, slack=0 — the setting the tool sweeps with by default. B costs
    more than A, so it never enters the frontier and C is never reached. The
    blind spot, stated as a fact rather than as a worry."""
    state, cost, _e, _c = _run(beam=1, slack=0)
    assert (state, cost) == ('A', 10)


def test_slack_alone_is_not_enough_when_a_tie_competes_for_the_slot():
    """SLACK IS NECESSARY BUT NOT SUFFICIENT, which I had wrong until this test
    said so.

    At beam=1 exactly ONE state survives each round. Slack admits B (the ridge,
    11) into the candidates — but D ties the start at 10, sorts ahead of it, and
    takes the only slot. The prize behind B is never reached. Nothing is broken:
    a one-wide beam keeps the cheapest, and the cheapest is not always the one
    worth keeping. WIDTH is what buys the second opinion."""
    state, cost, _e, _c = _run(beam=1, slack=1)
    assert (state, cost) == ('A', 10)


def test_width_and_slack_together_cross_the_ridge():
    """THE CONTROL, and the reason `--deep` sets both. Four states alive means B
    survives alongside the tie; one key of slack is what let it be a candidate
    at all. Same successors, same costs, same code — only the willingness to
    keep more than one option and to stand somewhere worse for a step."""
    state, cost, _e, _c = _run(beam=JG.DEEP_BEAM, slack=JG.DEEP_SLACK)
    assert (state, cost) == ('C', 8)
    # and it is genuinely the two settings TOGETHER, not either alone
    assert _run(beam=JG.DEEP_BEAM, slack=0)[0] == 'A', 'width without slack'
    assert _run(beam=1, slack=JG.DEEP_SLACK)[0] == 'A', 'slack without width'


def test_a_tie_is_explored_even_at_zero_slack():
    """Plateau moves are the cheap half of not being greedy: D ties with A, and
    at slack=0 a tie must still enter the frontier, or flat ground is a wall."""
    seen = []
    def _succ(state):
        seen.append(''.join(state))
        yield from _successors(state)
    JG.beam_search(start=['A'], start_cost=10, successors=_succ,
                   measure=_measure, beam=4, slack=0)
    assert 'D' in seen, 'a tied state was never expanded'


# ── the guarantees the search makes to its caller ───────────────────────────

def test_the_budget_is_a_ceiling_and_says_when_it_was_hit():
    """A "no beat found" that stopped early must not read like an exhaustive
    one. `hit_cap` is how the caller can tell the difference."""
    wide = {c: 5 for c in 'ABCDEFGHIJ'}
    def _succ(state):
        for c in 'ABCDEFGHIJ':
            if c != ''.join(state):
                yield [c], 'sub', 0, ''.join(state), c
    _b, _cost, _p, evals, capped = JG.beam_search(
        start=['A'], start_cost=9, successors=_succ,
        measure=lambda s: wide.get(''.join(s)), beam=4, slack=1, max_evals=3)
    assert capped and evals >= 3


def test_an_unmeasurable_state_is_not_a_route():
    """measure() returning None means 'not a route at all' — a tape that does
    not win, or wins only at some terminal heights. It must never be chosen,
    however cheap the caller might wish it were."""
    def _succ(state):
        yield ['X'], 'sub', 0, 'A', 'X'
    best, cost, _p, _e, _c = JG.beam_search(
        start=['A'], start_cost=10, successors=_succ,
        measure=lambda s: None if ''.join(s) == 'X' else 10)
    assert (''.join(best), cost) == ('A', 10)


def test_keep_vetoes_a_cheaper_state_and_reports_it():
    """The lesson-kept rule, at the search level: a cheaper state the caller
    refuses must not be taken, and the caller must hear about it — that is how
    a cheese gets reported instead of silently lowering a par."""
    rejected = []
    def _succ(state):
        yield ['C'], 'sub', 0, 'A', 'C'
    best, cost, _p, _e, _c = JG.beam_search(
        start=['A'], start_cost=10, successors=_succ, measure=_measure,
        keep=lambda s: ''.join(s) != 'C',
        on_reject=lambda s, got: rejected.append((''.join(s), got)))
    assert (''.join(best), cost) == ('A', 10)
    assert rejected == [('C', 8)]
