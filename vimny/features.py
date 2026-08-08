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

"""What this build of Vimny offers. Everything is on unless a host turns it off.

Only the browser build turns anything off, and only where the browser cannot
honour the promise the feature makes:

- **The forge** authors a level and then submits it as a pull request. The
  submission needs a browser tab Vimny cannot open from a worker, and the file
  it writes lands in a virtual filesystem the author cannot reach — so authoring
  online is a road that ends in a wall. It belongs to the installed game, and
  the message says so.
- **The remote shelf** downloads community levels over HTTPS, which WebAssembly
  Python cannot do (`RuntimeError: TLS not supported in this environment`).

Read these at CALL time, never captured at import — the browser build flips them
after `vimny.game` is already imported.
"""
from __future__ import annotations

#: Author levels: the forge/ subtree, `%` to start a draft, `:publish`, `:submit`.
FORGE = True

#: Download community levels from the shelf repo over HTTPS.
REMOTE_SHELF = True

#: Shown when a player reaches for something this build does not carry. Keep it
#: pointing AT the thing that does carry it — a refusal with no next step reads
#: as a bug.
UNAVAILABLE = 'Not in the browser build — `pip install vimny` to {}.'


def message(what: str) -> str:
    """`what` completes "…to ___" — e.g. 'compose levels'."""
    return UNAVAILABLE.format(what)
