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
import os
import tempfile

import pytest
from blessed import Terminal


def pytest_configure(config):
    """Point every Vimny persistence path at a scratch home BEFORE any test
    module (and therefore any vimny import) is collected.

    The suite drives real `run_dungeon` sessions as real players — including
    `admin` — and a session that reaches any save point writes
    `~/.Vimny/saves/<player>.json`. Under xdist those writes happen from
    several processes at once; even serially, an admin replay can overwrite a
    real player's progress. One scratch home per worker makes the entire run
    touch nothing but temp files. Set VIMNY_HOME manually to opt out."""
    if os.environ.get('VIMNY_HOME'):
        return                      # an explicit home wins — no redirection
    worker = os.environ.get('PYTEST_XDIST_WORKER', 'master')
    base = os.path.join(tempfile.gettempdir(), 'vimny-test-home', worker)
    os.makedirs(base, exist_ok=True)
    os.environ['VIMNY_HOME'] = base
    # vimny.save.save_manager may already be imported (conftest imports game);
    # recompute its directory constants against the scratch home.
    try:
        from vimny.save import save_manager as _sm
        _sm._reset_paths()
        _sm.SAVE_DIR.mkdir(parents=True, exist_ok=True)
        # Refresh the by-value snapshots other modules took at import.
        import vimny.sharing.draft as _draft
        _draft.DRAFTS_DIR = _sm.DRAFTS_DIR
        import vimny.sharing.library as _lib
        _lib.LEVELS_DIR = _sm.SAVE_DIR / 'levels'
        _draft.LEVELS_DIR = _lib.LEVELS_DIR
    except Exception:
        pass                        # not imported yet — env alone is enough


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
