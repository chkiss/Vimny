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

"""Suite-wide fixtures.

The suite drives the real game loop hard, and several long-standing tests
stub collaborators by RAW assignment (`main.render_all = cap`,
`Terminal.height = property(...)`) instead of monkeypatch — which leaks that
state into every alphabetically-later file. These autouse fixtures snapshot
the pristine module/class state at import time and put it back after each
test, making order-of-run irrelevant regardless of how a test patches.
"""
import pytest
from blessed import Terminal

import vimny.game as main

_PRISTINE_RENDER_ALL = main.render_all
_PRISTINE_SIZE_PROPS = {name: getattr(Terminal, name)
                        for name in ('height', 'width')}


@pytest.fixture(autouse=True)
def _no_stub_leaks():
    """Restore main.render_all and Terminal's size properties after each test."""
    yield
    if main.render_all is not _PRISTINE_RENDER_ALL:
        main.render_all = _PRISTINE_RENDER_ALL
    for name, pristine in _PRISTINE_SIZE_PROPS.items():
        if getattr(Terminal, name) is not pristine:
            setattr(Terminal, name, pristine)
