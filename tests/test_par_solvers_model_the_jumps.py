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

"""A par solver must model the line jumps its level has taught — and no others.

Two failures, opposite directions, both real:

  BLIND    A solver that omits `G` for a level that teaches `G` derives a par
           above the route that exists. Three did: The Bracket Vaults, The Runic
           Archives and The Sentence Corridor (fixed 2026-08-03 — all three kept
           the same par once taught, which is the outcome that says the tapes
           were already optimal and only the derivation was short).
  GENEROUS A solver that models `G` for a level that has NOT taught it derives a
           par no player can reach, because the game refuses the key. That one
           has never shipped, and this is what keeps it that way.

`H`/`M`/`L` are deliberately NOT modelled anywhere except The Screen Vault,
which teaches them: they are viewport-relative in a room taller than the game
area, so a par derived from one would be a par only some window sizes could hit.
They are covered from the other end by measurement — `vimny/sharing/jumpgolf.py`
replays every tape at heights 25..60 and reports only beats that hold at all of
them. Derived where derivation is sound, measured where it is not.

Read by the AST rather than by scanning text: a fixed-size text window ran off
the end of a short solver, and a window bounded by the next solver swallowed the
thousands of lines of level code between them. The two disagreed, and both were
wrong.
"""
import ast
from pathlib import Path

import pytest

from vimny.content.levels import LEVELS, known_commands

JUMPS  = ('gg', 'G', 'H', 'M', 'L')
#: Buffer-relative, so a solver may assume them — see the module docstring.
DERIVABLE = ('gg', 'G')
#: The shared helper that contributes gg / G / {n}G to a solver that calls it.
HELPER = '_line_jump_moves'

#: Levels whose par is a hand-tallied CONSTANT rather than a search. Nothing to
#: model — the number is pinned by the level's own driven playthrough instead.
_HAND_PINNED = {'spellwrights_forge'}

SRC  = (Path(__file__).resolve().parent.parent
        / 'vimny' / 'generation' / 'dungeon_gen.py')
TEXT = SRC.read_text()
TREE = ast.parse(TEXT)
SLUGS = {l['slug'] for l in LEVELS}


def _solvers():
    """(slug, models) for every `_par_<slug>` that belongs to a real level."""
    out = []
    for node in ast.walk(TREE):
        if not isinstance(node, ast.FunctionDef) or not node.name.startswith('_par_'):
            continue
        slug = node.name[len('_par_'):]
        if slug not in SLUGS:
            continue
        body = ast.get_source_segment(TEXT, node) or ''
        sub  = ast.parse(body)
        lits = {n.value for n in ast.walk(sub)
                if isinstance(n, ast.Constant) and isinstance(n.value, str)}
        calls = {n.func.id for n in ast.walk(sub)
                 if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)}
        models = set(j for j in JUMPS if j in lits)
        if HELPER in calls:
            models |= set(DERIVABLE)
        out.append((slug, models))
    return out


SOLVERS = _solvers()


def test_there_are_solvers_to_check():
    """If the AST walk stops finding them — a rename, a move — every assertion
    below passes vacuously and the guard is gone."""
    assert len(SOLVERS) >= 10, [s for s, _ in SOLVERS]


@pytest.mark.parametrize('slug,models', SOLVERS)
def test_no_solver_models_a_jump_its_level_has_not_taught(slug, models):
    taught = {j for j in JUMPS if j in known_commands(slug)}
    assert not (models - taught), (
        f'_par_{slug} models {sorted(models - taught)}, which this level has '
        f'not taught — the game refuses those keys, so a par derived with them '
        f'is a par no player can reach')


@pytest.mark.parametrize('slug,models', SOLVERS)
def test_every_solver_models_the_buffer_jumps_its_level_teaches(slug, models):
    if slug in _HAND_PINNED:
        pytest.skip('par is a hand-tallied constant, pinned by its own playthrough')
    taught = {j for j in DERIVABLE if j in known_commands(slug)}
    assert not (taught - models), (
        f'_par_{slug} is blind to {sorted(taught - models)} — its level teaches '
        f'them, so a route using them exists and par must account for it. Call '
        f'{HELPER}() from the solver\'s move generation.')
