"""Test suite package. Shared constants live here so they can't drift per-file."""

# Canonical seed set for parametrized dungeon tests (reachability, par, budget,
# command necessity, void safety) — see CLAUDE.md → Test conventions.
SEEDS = [1, 42, 999, 12345, 2**20 + 7]
