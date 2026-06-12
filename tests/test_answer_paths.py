"""Answer-path correctness: each token must be an atomic keystroke for the level.

Also home of the universal budget-formula test (budget == ceil(par × 1.4) for
every level with a keystroke par) — the per-level copies were removed in its
favour. Both universal tests read the shared build cache (tests.cached_room)."""
import inspect
import math
import re
import pytest
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
        # search: /pat⏎ or ?pat⏎ — '/' + len(pat) chars + ⏎ = len(pat)+2 (main.py)
        return len(token[1:-1]) + 2
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
    room = cached_room(builder.__name__, seed)
    assert room.budget == math.ceil(room.par * 1.4), (
        f"{builder.__name__} seed={seed}: budget={room.budget}, "
        f"ceil(par*1.4)={math.ceil(room.par * 1.4)}"
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
