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

"""Answer-path correctness: each token must be an atomic keystroke for the level.

Also home of the universal budget-formula test (budget == ceil(par × 1.4) for
every level with a keystroke par) — the per-level copies were removed in its
favour. Both universal tests read the shared build cache (tests.cached_room)."""
import inspect
import math
import re
import pytest
from blessed import Terminal
from blessed.keyboard import Keystroke
import main
import generation.dungeon_gen as _dg
from tests import cached_room

SEEDS = [0, 1, 42, 999, 2**20 + 7]   # answer-path set: includes seed 0 by design; differs from tests.SEEDS

_COUNT_RE = re.compile(r'^\d+[hjkl]$')   # e.g. '44l', '3j', '2h'

# ── General keystroke-cost model ──────────────────────────────────────────────
# Matches engine/main.py _keystroke_cost and the Dijkstra cost model:
#   count=1 → 1 ks; count=N → len(str(N))+1 ks.
#   ge/gE add +1 base: 2 ks for n=1, len(str(n))+2 for n>1.

_GE_RE  = re.compile(r'^(\d*)g[eEg]$')  # 'ge', 'gE', 'gg', '2gE', '10ge', …
_FT_RE  = re.compile(r'^(\d*)[fFtTr].$')  # 'fr', 'Fw', 't!', '2fr' — and r{c}: 'ra', '2rs'
_CNT_RE = re.compile(r'^(\d+).')        # '4e', '18h', '2j', …


def _token_ks_cost(token: str) -> int:
    """Keystroke cost of a single answer token.

    Matches _keystroke_cost in main.py:
      - plain single key (j, ^, $, x, …): 1
      - count-N + motion (4j, 63l, 9e): len(str(N)) + 1
      - g-prefix 2-key (ge, gE, gg): base 2; with count N: len(str(N)) + 2
      - f/F/t/T + target char (fr, Fw, t!, T!): base 2; with count: len+2
    """
    if token and token[0] in '/?' and token.endswith('⏎'):
        # search: /pat⏎ or ?pat⏎ — '/' charged + len(pat) chars, closing ⏎ free = len(pat)+1 (main.py)
        return len(token[1:-1]) + 1
    if len(token) == 2 and token[0] in "m'`" and token[1].isalpha():
        return 2          # marks: m{a} set, '{a}/`{a} jump — two keys each (main.py)
    m = _GE_RE.match(token)
    if m:
        n_str = m.group(1)
        return 2 if not n_str else len(n_str) + 2
    m = _FT_RE.match(token)
    if m:
        n_str = m.group(1)
        return 2 if not n_str else len(n_str) + 2
    m = _CNT_RE.match(token)
    if m:
        return len(m.group(1)) + 1
    if len(token) >= 2 and token[0] in 'ia' and token[1:].isalpha():
        # insert tokens ('ica', 'agate'): the entry key + each typed char
        # spend 1; Esc spends NOTHING (main's INSERT loop only charges
        # insert_char). The Inscription Halls' answers use these.
        return len(token)
    return 1  # single key: 'j', '^', '$', 'v', ';', ',', etc.


def _answer_total_ks_cost(answer: str) -> int:
    """Total keystroke cost of a space-separated answer string."""
    return sum(_token_ks_cost(t) for t in answer.split())


def _answer_keystroke_cost(answer: str, has_count: bool) -> int:
    """Count keystrokes in an answer path under the given command model."""
    total = 0
    for token in answer.split():
        if has_count and _COUNT_RE.match(token):
            # count-N + motion key = len(digits) + 1
            total += len(token) - 1 + 1   # = len(token)
        else:
            total += 1
    return total


# ── Universal answer-cost == par test (auto-discovers all build_dungeon_*) ────
#
# Any new build_dungeon_N added to dungeon_gen is automatically tested.
# Add to _XFAIL_LEVELS when a level's answer is intentionally not a
# parseable Vim-command token sequence (document why).
# Add to _SKIP_LEVELS to EXCLUDE a level with no keystroke par (combat boss /
# reward room / placeholder, or genuine WIP) — excluded levels are not collected,
# so they are not reported as skips.

_BUILDER_RE = re.compile(r'^build_dungeon_\w+$')

_SKIP_LEVELS = {
    # par=None — not keystroke puzzles, so "answer cost == par" does not apply.
    # Excluded from parametrization entirely (not emitted as skipped cases).
    'build_dungeon_reliquary',     # The Reliquary (reward / chest room)
    'build_dungeon_wardens_keep',     # The Warden's Keep (boss)
    'build_dungeon_warden_surveyor',  # The Warden Surveyor (boss)
    'build_dungeon_warden_pathfinder',  # The Warden Pathfinder (boss; two rooms, no keystroke par)
    'build_dungeon_warden_manifold',  # The Warden Manifold (boss; round machine, no keystroke par)
    'build_dungeon_dummy',  # Dummy Dungeon (test scaffold)
    'build_dungeon_archivists_library',  # The Archivist's Library (contextual :e!/:w loop; no keystroke par)
    'build_dungeon_spellwrights_forge',  # The Spellwright's Forge (:s/:g rites; no foot-path par solver)
}
_XFAIL_LEVELS: dict = {}

# Levels whose canonical answer is the raw keystroke tape (admin karaoke), not a
# space-separated Vim-token string the generic cost model can read — e.g. the
# Change Annex's `ce`/`cc`/`s` tokens carry their typed text inline (`cerune`,
# `jccextern`), which `_token_ks_cost` does not parse. par is pinned instead by
# the level's own driven playthrough test.
_ANSWER_NOT_TOKENISED = {
    'build_dungeon_whole_line_annex',  # ce/cc/s keystroke tape; tests/test_whole_line_annex.py
    'build_dungeon_change_extension',  # S/C keystroke tape; tests/test_change_extension.py
    'build_dungeon_sculpting_chambers',  # O/I/o/A insert tape; tests/test_sculpting_chambers.py
    'build_dungeon_overwrite_halls',   # R overtype tape; tests/test_overwrite_halls.py
    'build_dungeon_case_chambers',     # $~/gUU/./G$ multi-command tokens; tests/test_case_chambers.py
}

# Levels with a documented NON-1.4 budget. The Change Annex / Extension use a
# TIGHT margin (S2 by volume — below the trigger count, so the all-old route
# overshoots); their exact budgets are pinned by their own playthrough tests.
_NONSTANDARD_BUDGET = {
    'build_dungeon_whole_line_annex',
    'build_dungeon_change_extension',
    'build_dungeon_overwrite_halls',   # TIGHT: par + _OH_SAVING − 1 bars the all-S route
}

from tests import SEEDS as _UNIVERSAL_SEEDS


def _all_builder_params():
    builders = sorted(
        (name, fn)
        for name, fn in inspect.getmembers(_dg, inspect.isfunction)
        if _BUILDER_RE.match(name)
    )
    params = []
    for name, fn in builders:
        if name in _SKIP_LEVELS:
            continue   # excluded entirely (no keystroke par) — not added as skipped params
        for seed in _UNIVERSAL_SEEDS:
            marks = []
            if name in _XFAIL_LEVELS:
                marks.append(pytest.mark.xfail(
                    strict=False, reason=_XFAIL_LEVELS[name]
                ))
            params.append(pytest.param(fn, seed, id=f"{name}[{seed}]", marks=marks))
    return params


@pytest.mark.parametrize("builder,seed", _all_builder_params())
def test_answer_cost_equals_par(builder, seed):
    """answer keystroke cost == par for every level with a parseable answer.

    Catches: stale hardcoded fallback strings, Dijkstra cost-model drift,
    and any future level whose answer was written by hand and mis-counted.
    New build_dungeon_* functions are discovered automatically; a discovered
    level with no par/answer fails here (add it to _SKIP_LEVELS if intentional).
    """
    if builder.__name__ in _ANSWER_NOT_TOKENISED:
        pytest.skip("answer is not a space-tokenised path (typed text has spaces); "
                    "par pinned by the level's own playthrough test")
    room = cached_room(builder.__name__, seed)
    if room.par is None or not room.answer.strip():
        pytest.fail(
            f"{builder.__name__}: par/answer not set. If this level has no "
            f"keystroke par (combat boss / reward / placeholder), add it to "
            f"_SKIP_LEVELS; otherwise give it a par and answer."
        )
    cost = _answer_total_ks_cost(room.answer)
    assert cost == room.par, (
        f"answer keystroke cost {cost} != par {room.par}\n"
        f"  answer: {room.answer!r}"
    )


@pytest.mark.parametrize("builder,seed", _all_builder_params())
def test_budget_is_ceil_par_times_1_4(builder, seed):
    """budget == ceil(par × 1.4) for every level with a keystroke par.

    THE budget-formula test: per-level copies were removed in favour of this
    auto-discovered one, so a new level is covered the day its builder lands."""
    if builder.__name__ in _NONSTANDARD_BUDGET:
        pytest.skip("documented non-1.4 budget (tight S2 volume forcing); "
                    "pinned by the level's own test")
    room = cached_room(builder.__name__, seed)
    assert room.budget == math.ceil(room.par * 1.4), (
        f"{builder.__name__} seed={seed}: budget={room.budget}, "
        f"ceil(par*1.4)={math.ceil(room.par * 1.4)}"
    )


# ── Universal replay-to-win test (drives each answer through run_dungeon) ─────
#
# test_answer_cost_equals_par proves answer_cost == par; it does NOT prove the
# tape actually REACHES THE EXIT.  A tape can cost par yet fail to win — a decor
# rune carrying a target glyph hijacks an f-scan (the goblin_gauntlet bug), or a
# layout change strands the route.  Cost-only checks slip these every time; only
# an end-to-end replay reveals the lost win.  This test replays every level's
# canonical tape key-for-key through the real engine and asserts a par-perfect
# 2-star win, across every answer-path seed.

# game_h = term.height - 8 (main.py's motion call); the dungeons are built for the
# default game height of 33 (dungeon_gen._SCREEN_VAULT_DEFAULT_GAME_H), so the
# Screen Vault's viewport-relative H/M/L land on their keys only at height 41.
_REPLAY_TERM_HEIGHT = 33 + 8

# Levels whose tape enters INSERT/CHANGE mode, where a token-separating space is
# an implicit <Esc> that the generic '⏎'→Enter / strip-spaces translation can't
# express.  Each has a dedicated full-playthrough win test that drives the engine
# with the right Esc placement, so they are win-covered there, not here.
_REPLAY_OWN_TEST = {
    'build_dungeon_inscription_halls': 'test_inscription_halls.py::test_full_playthrough_wins_par_perfect',
    'build_dungeon_whole_line_annex':  'test_whole_line_annex.py::test_full_change_route_wins_par_perfect',
    'build_dungeon_change_extension':  'test_change_extension.py::test_full_change_route_wins_par_perfect',
    'build_dungeon_sculpting_chambers': 'test_sculpting_chambers.py::test_full_votive_route_wins_par_perfect',
    'build_dungeon_overwrite_halls':   'test_overwrite_halls.py::test_full_R_route_wins_par_perfect',
    'build_dungeon_case_chambers':     'test_case_chambers.py::test_full_case_route_wins_par_perfect',
}


@pytest.fixture
def _replay_env(monkeypatch):
    """Headless engine for a faithful replay: silence rendering/animations, stub the
    mid-dungeon scroll dismissals that read keys outside the main loop, and pin the
    terminal height so viewport-relative motions (H/M/L) match real play."""
    monkeypatch.setattr(main, 'render_all', lambda *a, **k: None)
    monkeypatch.setattr(main.time, 'sleep', lambda *a, **k: None)
    monkeypatch.setattr(Terminal, 'height', _REPLAY_TERM_HEIGHT)
    for anim in ('_fireworks_animation', '_win_animation', '_combat_flash',
                 '_death_animation', '_starfield_victory'):
        if hasattr(main, anim):
            monkeypatch.setattr(main, anim, lambda *a, **k: None)
    # Mid-dungeon relic/reward scrolls read their dismiss key via a direct
    # term.inkey() that bypasses the key loop; stub them so a replay never loses a
    # tape key to a scroll sub-loop (the karaoke-audit artifact).
    for fn in ('_show_scroll_by_id', '_render_standard_scroll',
               '_show_reliquary_scroll', '_show_catalog_scroll'):
        if hasattr(main, fn):
            monkeypatch.setattr(main, fn, lambda *a, **k: None)


def _drive_to_win(builder, seed):
    """Replay builder(seed)'s canonical answer tape through run_dungeon as a real
    (non-admin) player and return the {'won', 'stars', ...} result.  Builds fresh
    (never the shared cache) because run_dungeon mutates the dungeon."""
    dungeon = builder(seed)
    slug = builder.__name__[len('build_dungeon_'):]
    tape = dungeon.rooms[0].answer.replace(' ', '')          # spaces are visual separators
    keys = [Keystroke('\r' if c == '⏎' else c) for c in tape]
    keys += [Keystroke(c) for c in ':wq\r']                  # :wq returns the real win/stars
    term = Terminal(force_styling=False)
    import render.colors as _colors
    _colors.init(term)                                       # combat/key colour paths touch color_rgb()
    state = {'n': 0}
    def _inkey(*a, **k):
        if state['n'] < len(keys):
            key = keys[state['n']]
            state['n'] += 1
            return key
        raise AssertionError(
            f"{slug}[{seed}]: the tape + :wq were exhausted without run_dungeon "
            f"returning — the route never reached the exit and never quit (likely "
            f"stranded, or left in a non-NORMAL mode so :wq was typed as text)."
        )
    term.inkey = _inkey
    return main.run_dungeon(term, slug, {}, player_name='Normand', _dungeon=dungeon)


@pytest.mark.parametrize("builder,seed", _all_builder_params())
def test_answer_path_actually_wins(builder, seed, _replay_env):
    """The canonical answer tape, replayed through run_dungeon, reaches the exit
    and earns a par-perfect 2-star win.  Catches stranded routes, glyph-hijacked
    motions, and engine/solver cost drift (an over-par replay drops to 1 star)."""
    if builder.__name__ in _REPLAY_OWN_TEST:
        pytest.skip("insert/change tape carries implicit <Esc>; win-replayed by "
                    + _REPLAY_OWN_TEST[builder.__name__])
    result = _drive_to_win(builder, seed)
    assert result['won'] and result['stars'] == 2, (
        f"{builder.__name__}[{seed}]: replaying the canonical answer tape did not "
        f"yield a par-perfect 2-star win: {result}\n"
        f"  answer: {builder(seed).rooms[0].answer!r}"
    )


class TestLevel0AnswerPath:
    """The First Cave has only h/j/k/l.  Answer must not use count notation."""

    def test_no_count_notation(self):
        for seed in SEEDS:
            room = cached_room('build_dungeon_first_cave', seed)
            for token in room.answer.split():
                assert not _COUNT_RE.match(token), (
                    f"seed={seed}: count notation '{token}' in level-0 answer "
                    f"(player hasn't learned count motions)"
                )

    def test_token_count_equals_par(self):
        for seed in SEEDS:
            room = cached_room('build_dungeon_first_cave', seed)
            tokens = room.answer.split()
            assert len(tokens) == room.par, (
                f"seed={seed}: answer has {len(tokens)} tokens but par={room.par}"
            )


class TestLevel1AnswerPath:
    """The Line Halls has h/j/k/l + ^$0.  Answer must not use count notation."""

    def test_no_count_notation(self):
        for seed in SEEDS:
            room = cached_room('build_dungeon_line_halls', seed)
            for token in room.answer.split():
                assert not _COUNT_RE.match(token), (
                    f"seed={seed}: count notation '{token}' in level-1 answer"
                )

    def test_token_count_equals_par(self):
        for seed in SEEDS:
            room = cached_room('build_dungeon_line_halls', seed)
            tokens = room.answer.split()
            assert len(tokens) == room.par, (
                f"seed={seed}: answer has {len(tokens)} tokens but par={room.par}"
            )


def test_backward_vaults_fallback_answer_cost_matches_fallback_par():
    """The Backward Vaults fallback string and fallback par must agree.

    The universal test only exercises the live Dijkstra output; this test guards
    the hardcoded fallback used when Dijkstra returns None, catching stale
    hardcoding after a layout change.
    """
    fallback_answer = '4E 2j ^ 2j $ 2j ge 2j $ 2j gE j'
    fallback_par    = 20
    cost = _answer_total_ks_cost(fallback_answer)
    assert cost == fallback_par, (
        f"Fallback answer cost={cost} != fallback par={fallback_par} "
        f"(answer={fallback_answer!r}) — update one to match the other"
    )
