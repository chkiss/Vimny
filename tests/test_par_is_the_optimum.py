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

"""No shipped level may be beaten by a LINE JUMP its own tape does not take.

PAR IS THE OPTIMUM — the cheapest route that exists. Six levels shipped with a
par that was not, because the question was answered by reasoning instead of by
replaying: The Operator's Vault recorded 62 on the argument that a counted jump
only beats a walk when its count is a single digit (true, and beside the point —
the jump never needed a count), and the route that existed was 55.

This is that question asked automatically, so the next level cannot repeat it.
The work is in `vimny/sharing/jumpgolf.py`; this module is the gate.

WHY IT IS OPT-IN. A single level's golf replays its whole tape through the real
game loop once per candidate per terminal height. Standalone that is ten minutes;
UNDER PYTEST it is about one, because conftest's session build cache hands out
copies instead of rebuilding each dungeon. One minute on top of a two-minute
suite is still a half-again cost on every edit for a check that only moves when
a tape or a par does — cheap enough for CI, too dear for the inner loop. Run it
when tapes or par change:

    VIMNY_JUMPGOLF=1 python3 -m pytest tests/test_par_is_the_optimum.py

or, for the same answer with a nicer report:

    python3 -m sharing jumpgolf

The always-on tests below cost nothing and guard the GUARD — a rotted
acceptance rule would let the sweep pass while checking nothing, which is the
failure mode that matters when a check is this expensive to run.
"""
import os

import pytest

from vimny.sharing import jumpgolf as JG

RUN = os.environ.get('VIMNY_JUMPGOLF') in ('1', 'seeds')
WHY = ('slow (a full tape replay per candidate per height); run with '
       'VIMNY_JUMPGOLF=1, or `python3 -m sharing jumpgolf`')

#: SEED COVERAGE. `VIMNY_JUMPGOLF=1` golfs one build per level; `=seeds` golfs
#: every DISTINCT LAYOUT across the repo's seeds. The distinction matters
#: because most levels vary by seed — they pick different vocabulary, and the
#: tape carries those words, so `/vault<CR>` is not `/cellar<CR>` and a route's
#: cost can turn on a word's length. Only two thirds of the seed/level pairs are
#: genuinely different builds, so deduplicating by layout buys the same coverage
#: for a third less work.
if os.environ.get('VIMNY_JUMPGOLF') == 'seeds':
    from tests import SEEDS as _REPO_SEEDS
    SEEDS_TO_GOLF = [0] + list(_REPO_SEEDS)
else:
    SEEDS_TO_GOLF = [0]


def _cases():
    """(slug, seed) for every distinct layout under test."""
    out = []
    for slug in JG.golfable_levels():
        seeds = (JG.distinct_seeds(slug, SEEDS_TO_GOLF)
                 if len(SEEDS_TO_GOLF) > 1 else SEEDS_TO_GOLF)
        out += [(slug, s) for s in seeds]
    return out


# ── the gate ────────────────────────────────────────────────────────────────

@pytest.mark.skipif(not RUN, reason=WHY)
@pytest.mark.parametrize('slug,seed', _cases() if RUN else [('_', 0)])
def test_no_line_jump_beats_this_levels_par(slug, seed):
    """Parametrized per level (and per distinct layout) so a failure NAMES the
    level and its cheaper tape — a single assertion over the whole game would
    report the first offender and hide the rest, and these have historically
    come in groups."""
    res = JG.golf(slug, seed=seed)
    if res.canonical is None or not res.taught:
        pytest.skip('no jump taught yet, or the tape is not height-stable')
    assert not res.beats_par, (
        f'{slug}[seed {seed}]: par {res.par} but a jump route wins at '
        f'{res.best} — par is the optimum, so the recorded value is simply '
        f'wrong.\n  {res.tape}')


@pytest.mark.skipif(not RUN, reason=WHY)
@pytest.mark.parametrize('slug', sorted(JG._VERIFY))
def test_the_state_check_actually_bites(slug):
    """A `_VERIFY` predicate that is True of every room checks nothing. Assert
    the shipped tape SATISFIES it (or the level's own par is unreachable) — the
    predicate has to be a real property of a real solve."""
    import vimny.generation.dungeon_gen as dg
    res = JG.golf(slug)
    assert res.canonical is not None, (
        f'{slug}: its own tape fails the state check {JG._VERIFY[slug]!r} — '
        f'the predicate is wrong, or par records a route nobody can walk')


# ── guarding the guard (fast) ───────────────────────────────────────────────

def test_every_golfable_level_has_a_lesson_to_keep():
    """The acceptance rule is "a cheaper route counts only if the level still
    teaches its lesson". A level whose lesson resolves to NO keys accepts any
    route at all, so the rule silently stops applying there — which is how a
    sweep passes while checking nothing."""
    import vimny.generation.dungeon_gen as dg
    from vimny.content.levels import LEVELS

    from vimny.content.levels import known_commands

    toothless = []
    for slug in JG.golfable_levels():
        if not any(j in known_commands(slug) for j in JG.JUMPS):
            continue          # no jump taught yet — the rule cannot apply here
        room = getattr(dg, f'build_dungeon_{slug}')(0).room
        keys = tuple(k for k in JG.lesson_keys(slug)
                     if JG._pressed(k, room.answer.split(' ')))
        if not keys and slug not in JG._VERIFY and slug not in JG.NO_LESSON_KEYS:
            entry = next(l for l in LEVELS if l['slug'] == slug)
            toothless.append((slug, entry['commands']))
    # A level whose lesson genuinely is not a keystroke belongs in _VERIFY (a
    # state check) or NO_LESSON_KEYS (a reasoned exemption) — never silently.
    assert toothless == [], (
        'these levels advertise commands their own tape never presses, so the '
        'lesson-kept rule has nothing to hold them to: '
        + ', '.join(f'{s} ({c})' for s, c in toothless))


def test_every_level_that_veils_text_is_in_the_state_registry():
    """A level that HIDES readable content behind a mechanic cannot have its par
    measured by the tape alone.

    The Wet Ink is the case: its plaque's later quarters are veiled until the
    brazier beneath each one burns, so a route that never carries fire is one
    only a player who already knew the saying could walk. Par must assume the
    player who does not — which is a property of the finished ROOM, invisible to
    any reading of the keystrokes, hence `_VERIFY`.

    Today wet_ink is the only level with `veiled_cells` and it is registered.
    This is here so the next one cannot arrive unregistered and quietly have its
    par measured against a route that reads text it should not be able to see.
    (Plain `fog_cells` is darkness — unlit floor — not unreadable text, so it
    does not trip this.)
    """
    import vimny.generation.dungeon_gen as dg
    unregistered = []
    for slug in JG.golfable_levels():
        room = getattr(dg, f'build_dungeon_{slug}')(0).room
        if getattr(room, 'veiled_cells', None) and slug not in JG._VERIFY:
            unregistered.append(slug)
    assert unregistered == [], (
        'these levels veil text the route may depend on, but no _VERIFY '
        'predicate says what a real solve must reveal: ' + ', '.join(unregistered))


def test_heights_straddle_the_only_discontinuity():
    """H/M/L flip from room-relative to viewport-relative at
    `height == room.rows + 8` and are flat either side, so the sampled heights
    must sit on both sides of that line — otherwise a beat living only in the
    viewport-relative regime is invisible, which is what five arbitrary numbers
    risked."""
    import vimny.generation.dungeon_gen as dg
    for slug in ('operators_vault', 'hall_of_echoes', 'stair_rail'):
        room = getattr(dg, f'build_dungeon_{slug}')(0).room
        flip = room.rows + 8
        hs = JG.heights_for(room)
        assert any(h < flip for h in hs), (slug, hs, flip)
        assert any(h >= flip for h in hs), (slug, hs, flip)


def test_ex_command_lessons_are_matched_as_ex_commands():
    """`:m` must mean an ex command, not the letter m anywhere in the tape.

    The Shelving Room writes its lessons with ranges fused in (`:6m3`), so the
    check has to see through that — and held to the bare letter instead it saw
    through everything, matching a typed word or a macro register name."""
    real = ':set<Space>nu<CR> :6m3<CR> :6<<CR> :7t7<CR> :8><CR> $'.split(' ')
    assert all(JG._pressed(k, real) for k in (':m', ':t', ':>', ':<'))
    assert not JG._pressed(':d', real)
    assert not JG._pressed(':m', ['imellon<Esc>', 'qm', '@m'])


def test_the_verify_registry_names_real_levels():
    """A `_VERIFY` entry keyed on a slug that no longer exists is a check that
    quietly stopped running."""
    known = set(JG.golfable_levels())
    unknown = sorted(set(JG._VERIFY) - known)
    assert unknown == [], f'_VERIFY names levels that are not golfable: {unknown}'


def test_token_gating_is_enforced_when_proposing():
    """The candidates offered to a level must be ones it has TAUGHT. An ungated
    key is not a route — the game refuses it — and a sweep that proposed one
    would be measuring a route no player can walk. G/gg arrive at curriculum
    position 10 and H/M/L at 11, so the early levels must be offered nothing.

    Read off `known_commands` rather than by running the golf: this test is in
    the always-on set, and golf() replays."""
    from vimny.content.levels import known_commands
    for slug in ('first_cave', 'line_halls', 'counting_crypts'):
        assert not any(j in known_commands(slug) for j in JG.JUMPS), \
            f'{slug} sits before the jumps and must be offered none'
    for slug in ('operators_vault', 'wet_ink', 'spellwrights_forge'):
        known = known_commands(slug)
        assert all(j in known for j in JG.JUMPS), \
            f'{slug} should have every jump available by now'


def test_travel_and_collapse_patterns_cover_the_written_tapes():
    """The collapse pass only fires on runs of TRAVEL tokens, so a travel key
    the pattern does not recognise is invisible to the whole sweep. Assert the
    pattern actually matches the vertical keys the shipped tapes are written
    with — this is the blind spot that let the first sweep miss `0 3j` -> `G`."""
    for tok in ('3j', '2k', '2+', '2-', '4G', 'G', 'gg', 'H', 'M', 'L', '0', '^'):
        assert JG.TRAVEL.match(tok), f'TRAVEL does not recognise {tok!r}'
    for tok in ('dw', 'p', 'x', '$', 'qa', '@a', ':wq'):
        assert not JG.TRAVEL.match(tok), f'TRAVEL wrongly claims {tok!r}'
