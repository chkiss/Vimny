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

"""Verify that all modules import without error under Python 3.9.

The X | None union syntax for runtime annotations (not inside string
annotations) requires Python 3.10+.  Using `from __future__ import
annotations` defers evaluation so the syntax is safe on 3.9.
"""
import importlib


MODULES = [
    'main',
    'engine.vim_parser',
    'render.title',
    'render.overworld',
    'generation.dungeon_gen',
]


def test_modules_importable():
    for name in MODULES:
        mod = importlib.import_module(name)
        assert mod is not None, f"Failed to import {name}"
