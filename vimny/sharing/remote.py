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

"""The remote shelf — browse and install community levels over the network.

A community level is INERT DATA (`docs/AUTHORING.md`: the game "runs none of
it"), so fetching one from the internet adds no code-execution risk: the only
thing downloaded is JSON, and it goes through the same `validate()` every local
shelf file does before it can be played. That is why this can be stdlib-only —
`urllib.request`, no third-party HTTP client — and still be safe.

The backend is a GitHub repo (chkiss/vimny-levels) served over raw.github-
usercontent.com: an `index.json` MANIFEST lists the levels, and each row names
the raw path of one level file. The manifest exists so the browser can show a
name/author/teaches listing WITHOUT downloading every level first — one request
to list, one more to install the one the player picked.
"""
from __future__ import annotations

import json
import tempfile
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path

from vimny.sharing.library import Shelved, install

#: Where the manifest and the level files live. Override with $VIMNY_LEVELS_URL
#: (e.g. to point the game at a fork) — it must be the raw base of a repo laid
#: out like chkiss/vimny-levels, with `index.json` at the root.
import os

DEFAULT_BASE_URL = 'https://raw.githubusercontent.com/chkiss/vimny-levels/main/'


def base_url() -> str:
    url = os.environ.get('VIMNY_LEVELS_URL', DEFAULT_BASE_URL).strip()
    return url if url.endswith('/') else url + '/'


_TIMEOUT = 10          # seconds — a hung fetch must never freeze the overworld
_MAX_BYTES = 512 * 1024  # a level file is a few KB; anything this big is wrong


@dataclass
class RemoteEntry:
    """One row of the manifest: enough to list a level without downloading it."""
    name:    str
    author:  str
    slug:    str
    teaches: list = field(default_factory=list)
    path:    str = ''           # repo-relative path of the level file

    @property
    def url(self) -> str:
        return base_url() + self.path.lstrip('/')

    @property
    def filename(self) -> str:
        """The name it takes on the local shelf — the slug, never the manifest's
        `path`, so a remote level and a hand-installed one collide by slug the
        way the rest of the game keys them."""
        return f'{self.slug}.json'


def _get(url: str) -> bytes:
    """One HTTPS GET, stdlib only. Raises urllib errors; the caller turns those
    into a message rather than letting them escape into the overworld loop."""
    req = urllib.request.Request(url, headers={'User-Agent': 'Vimny'})
    with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:   # noqa: S310 — https URL we built
        return resp.read(_MAX_BYTES + 1)


def _reason(exc: Exception) -> str:
    """A short, player-facing reason a fetch failed — never a stack trace."""
    if isinstance(exc, urllib.error.HTTPError):
        return f'server said {exc.code}'
    if isinstance(exc, urllib.error.URLError):
        return f'no connection ({exc.reason})'
    return str(exc)


def fetch_manifest() -> tuple[list[RemoteEntry], str]:
    """Read `index.json` and return (entries, error). On any failure the list is
    empty and the error is a one-line reason the browser can show — the overworld
    must open whether or not the network does."""
    try:
        raw = _get(base_url() + 'index.json')
    except Exception as exc:                       # noqa: BLE001 — all funnel to a message
        return [], f'could not reach the shelf — {_reason(exc)}'
    try:
        data = json.loads(raw.decode('utf-8'))
        rows = data['levels'] if isinstance(data, dict) else data
    except (ValueError, KeyError, UnicodeDecodeError) as exc:
        return [], f'the shelf index is malformed — {exc}'
    entries = []
    for r in rows:
        try:
            entries.append(RemoteEntry(
                name=str(r.get('name', r.get('slug', '?'))),
                author=str(r.get('author', '') or ''),
                slug=str(r['slug']),
                teaches=list(r.get('teaches', [])),
                path=str(r.get('path', '')),
            ))
        except (KeyError, TypeError):
            continue                                # skip a bad row, keep the rest
    entries.sort(key=lambda e: e.name.lower())
    return entries, ''


def install_entry(entry: RemoteEntry) -> Shelved:
    """Download one level and put it on the shelf, validating before it lands —
    exactly `library.install`, but the source is a URL instead of a local path.

    The download goes to a temp file that `install` then validates and copies:
    a level that fails validation never reaches `~/.Vimny/levels/`, so a broken
    or truncated download cannot leave a dead entry on the shelf."""
    try:
        raw = _get(entry.url)
    except Exception as exc:                       # noqa: BLE001
        return Shelved(path=Path(entry.filename),
                       error=f'download failed — {_reason(exc)}')
    if len(raw) > _MAX_BYTES:
        return Shelved(path=Path(entry.filename),
                       error='that file is suspiciously large — not installing')
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp) / entry.filename
        try:
            tmp_path.write_bytes(raw)
        except OSError as exc:
            return Shelved(path=Path(entry.filename), error=f'could not write: {exc}')
        return install(tmp_path)
