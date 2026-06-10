"""Test suite package. Shared constants live here so they can't drift per-file."""
from functools import lru_cache

# Canonical seed set for parametrized dungeon tests (reachability, par, budget,
# command necessity, void safety) — see docs/ARCHITECTURE.md → Test conventions.
SEEDS = [1, 42, 999, 12345, 2**20 + 7]


@lru_cache(maxsize=None)
def cached_dungeon(builder_name: str, seed: int):
    """ONE shared build per (builder, seed), for READ-ONLY property tests.

    Building a dungeon can be expensive (the Screen Vault's answer Dijkstra runs
    seconds), and the property tests — par match, budget formula, structure,
    answer cost — all read the same build. NEVER mutate a cached room (no
    apply_motion / editing / kill_entity); a test that simulates play must call
    its builder directly for a private copy."""
    import generation.dungeon_gen as _dg
    return getattr(_dg, builder_name)(seed)


def cached_room(builder_name: str, seed: int):
    """First room of the shared build — see cached_dungeon's READ-ONLY rule."""
    return cached_dungeon(builder_name, seed).rooms[0]
