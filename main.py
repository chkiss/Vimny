#!/usr/bin/env python3
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

"""`./main.py` or `python3 main.py` — the way to play from a checkout.

The game itself is `vimny/game.py`. This file exists so that running Vimny
from a checkout stays one obvious command, while an INSTALL adds only the
`vimny` package and the `vimny` script: a `pip install .` that dropped a
top-level module named `main` into site-packages would be claiming a name
half the Python world might want.
"""
import sys

from vimny.game import main

if __name__ == '__main__':
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        pass
