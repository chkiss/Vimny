"""Relic ("safe") scroll pool: chests with no assigned scroll pull a random
not-yet-discovered scroll from this pool. Verifies catalog integrity and the
picker's no-repeat / exhaustion behaviour."""
import random
import pytest

from content.scrolls import SCROLL_CATALOG, RELIC_SCROLL_IDS, pick_relic_scroll

_CATALOG_IDS = {s['id'] for s in SCROLL_CATALOG}


def test_every_relic_id_is_in_the_catalog():
    for sid in RELIC_SCROLL_IDS:
        assert sid in _CATALOG_IDS, f'{sid} missing from SCROLL_CATALOG'

def test_catalog_ids_are_unique():
    ids = [s['id'] for s in SCROLL_CATALOG]
    assert len(ids) == len(set(ids))

def test_pick_skips_discovered():
    discovered = RELIC_SCROLL_IDS[:-1]               # all but the last
    assert pick_relic_scroll(discovered) == RELIC_SCROLL_IDS[-1]

def test_pick_returns_none_when_exhausted():
    assert pick_relic_scroll(RELIC_SCROLL_IDS) is None
    assert pick_relic_scroll(set(RELIC_SCROLL_IDS) | {'x'}) is None

def test_pick_is_deterministic_with_rng():
    a = pick_relic_scroll([], random.Random(7))
    b = pick_relic_scroll([], random.Random(7))
    assert a == b and a in RELIC_SCROLL_IDS

def test_collecting_all_via_repeated_picks():
    discovered: list = []
    while (sid := pick_relic_scroll(discovered, random.Random(len(discovered)))) is not None:
        assert sid not in discovered
        discovered.append(sid)
    assert set(discovered) == set(RELIC_SCROLL_IDS)
