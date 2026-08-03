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

"""`:submit` — hand a finished level to the community repo as a pull request.

The whole mechanism is ONE URL. GitHub's "create new file" page accepts the
path and the file's contents as query parameters, so a link can arrive at a
form that is already filled in: the author signs in as themselves, reads what
they are about to send, and presses the green button. Their fork and their pull
request are made by GitHub, in their name.

That is why there is no API client here, and must not be one. Vimny holds no
token, asks for no password, and speaks to no server — `build_url` returns a
string. Everything that could go wrong is a browser tab the author can close.
It also means submitting works for anyone with a GitHub account and nothing
else installed, which `gh`-CLI delegation would not.

The cost is a length ceiling. The level file rides inside the URL, and a URL
has practical limits (see `URL_LIMIT`); a level big enough to blow past it gets
the same page WITHOUT the prefill, plus its file on disk to paste in by hand.
The submission still happens — it just takes one more step.
"""
from __future__ import annotations

import os
from urllib.parse import quote

from save.save_manager import _slug
from sharing import format as F

#: The repo that receives submissions. Override with $VIMNY_LEVELS_REPO to aim
#: a fork or a private collection at your own copy — the same escape hatch
#: `sharing.remote` gives the shelf you read FROM.
DEFAULT_REPO = 'chkiss/vimny-levels'
DEFAULT_BRANCH = 'main'

#: Where level files live inside that repo. Must match the `path` the manifest
#: hands out, or a level lands somewhere the shelf never looks.
LEVELS_SUBDIR = 'levels'

#: Beyond this, drop the prefill rather than send a link that 414s. GitHub has
#: no published maximum; this is well under the ~8 KB most servers accept on a
#: request line, and a level that exceeds it is a big one either way.
URL_LIMIT = 6000


def repo() -> str:
    return os.environ.get('VIMNY_LEVELS_REPO', DEFAULT_REPO).strip().strip('/')


def branch() -> str:
    return os.environ.get('VIMNY_LEVELS_BRANCH', DEFAULT_BRANCH).strip()


def file_path(slug: str) -> str:
    return f'{LEVELS_SUBDIR}/{slug}.json'


def build_url(level: F.Level, slug: str) -> tuple[str, bool]:
    """The prefilled submission link for one level. Returns `(url, prefilled)`.

    `prefilled` is False when the file was too long to carry, which is not an
    error: the URL still opens the right form at the right path, and the caller
    tells the author where the file is so they can paste it.
    """
    base = (f'https://github.com/{repo()}/new/{branch()}'
            f'?filename={quote(file_path(slug))}')
    # The commit subject doubles as the pull request's title, so it is the one
    # line a reviewer sees in a list of twenty. Name the level, not the act.
    msg  = quote(f'Add level: {level.name}')
    body = F.dumps(level)
    long_url = f'{base}&value={quote(body)}&message={msg}'
    if len(long_url) <= URL_LIMIT:
        return long_url, True
    return f'{base}&message={msg}', False


def submit_slug(level: F.Level) -> str:
    """The filename a submission takes in the repo, derived the same way the
    local shelf derives one — a level keeps its name wherever it is stored."""
    return _slug(level.name)
