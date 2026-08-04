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

# Presence of this file makes pytest add the project root to sys.path.
#
# It also installs a session-wide build cache (see pytest_configure below).
# The per-level par solvers run *inside* build_dungeon_* — e.g. the Screen
# Vault's H/M/L Dijkstra costs ~2.4s per build — so the same (slug, seed) was
# being re-solved by every property test (~35 screen-vault builds across the
# suite, all producing the identical seed-independent answer). We memoize each
# builder per call-args and hand back a deepcopy (~0.003s, ~700x cheaper than
# rebuilding) so tests can still mutate their dungeon freely. Test-only:
# production (vimny/game.py) imports the unwrapped module.
import copy
import functools


def _make_cached_builder(original):
    """Wrap a build_dungeon_* function: build once per call-args, return a copy."""
    cache: dict = {}

    @functools.wraps(original)            # keeps __name__ so inspect.isfunction
    def cached(*args, **kwargs):          # discovery in test_answer_paths still works
        key = (args, tuple(sorted(kwargs.items())))
        if key not in cache:
            cache[key] = original(*args, **kwargs)
        return copy.deepcopy(cache[key])  # never hand out the pristine cached object

    cached._build_cached = True
    return cached


def pytest_configure(config):
    """Install the build cache before any test module imports the builders.

    Runs after sys.path is set up and before collection, so test modules that do
    ``from vimny.generation.dungeon_gen import build_dungeon_x`` bind to the wrapped
    version.
    """
    import vimny.generation.dungeon_gen as dg

    for name in dir(dg):
        if not name.startswith('build_dungeon_'):
            continue
        fn = getattr(dg, name)
        if callable(fn) and not getattr(fn, '_build_cached', False):
            setattr(dg, name, _make_cached_builder(fn))
