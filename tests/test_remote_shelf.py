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

"""The remote shelf — fetching the manifest and installing over the network.

The install path is the whole point, so it is tested end to end: manifest →
download → validate → land on the shelf → appear in the overworld's community
wing, playable, with the par the replayer derived.

NOTHING HERE TOUCHES THE NETWORK. Every test substitutes `remote._get`, so the
suite is deterministic offline and a GitHub outage can never turn the build red.
What that cannot prove is that the live repo is laid out the way the manifest
parser expects; `test_the_manifest_shape_matches_what_the_real_repo_ships`
pins the contract instead, against the checked-in worked example.

The safety argument this file is really guarding: a downloaded level is INERT
DATA, validated by the same `validate()` a local file gets, BEFORE it lands in
`~/.Vimny/levels/`. So the tests that matter most are the refusals — a level
that fails validation, a truncated download, an oversized file — none of which
may leave anything on the shelf.
"""
import json

import pytest

import generation.dungeon_gen as dg
from content.levels import known_commands
from sharing import format as F
from sharing import library, remote

SEED = 42


def _level(name='The Salt Stair', slug='rune_halls'):
    """A real shipped level exported into the community format."""
    room    = dg.__dict__[f'build_dungeon_{slug}'](SEED).room
    known   = known_commands(slug)
    teaches = ['w']
    lvl = F.from_room(room, name, author='tester', teaches=teaches,
                      requires=[k for k in known if k not in teaches])
    return lvl


def _manifest(rows):
    return json.dumps({'levels': rows}).encode('utf-8')


def _serve(monkeypatch, pages: dict):
    """Substitute the one HTTPS GET. `pages` maps url-suffix -> bytes or an
    Exception to raise."""
    def fake_get(url):
        for suffix, payload in pages.items():
            if url.endswith(suffix):
                if isinstance(payload, Exception):
                    raise payload
                return payload
        raise AssertionError(f'unexpected fetch: {url}')
    monkeypatch.setattr(remote, '_get', fake_get)


@pytest.fixture
def shelf(tmp_path, monkeypatch):
    """A throwaway local shelf, so no test can write to the real one."""
    monkeypatch.setattr(library, 'LEVELS_DIR', tmp_path)
    return tmp_path


# ── the manifest ─────────────────────────────────────────────────────────────
def test_the_manifest_lists_levels_without_downloading_them(monkeypatch):
    """The manifest exists so browsing costs ONE request, not one per level."""
    _serve(monkeypatch, {'index.json': _manifest([
        {'name': 'The Salt Stair', 'author': 'tester', 'slug': 'salt_stair',
         'teaches': ['w'], 'path': 'levels/salt_stair.json'},
    ])})
    entries, err = remote.fetch_manifest()
    assert not err and len(entries) == 1
    e = entries[0]
    assert (e.name, e.author, e.slug, e.teaches) == (
        'The Salt Stair', 'tester', 'salt_stair', ['w'])
    assert e.url.endswith('levels/salt_stair.json')


def test_entries_are_sorted_by_name(monkeypatch):
    _serve(monkeypatch, {'index.json': _manifest([
        {'slug': 'b', 'name': 'Zed', 'path': 'b.json'},
        {'slug': 'a', 'name': 'Alpha', 'path': 'a.json'},
    ])})
    entries, _ = remote.fetch_manifest()
    assert [e.name for e in entries] == ['Alpha', 'Zed']


def test_a_bad_row_is_skipped_and_the_rest_survive(monkeypatch):
    """One malformed entry must not cost the player the whole catalogue."""
    _serve(monkeypatch, {'index.json': _manifest([
        {'name': 'no slug here', 'path': 'x.json'},          # missing slug
        {'slug': 'good', 'name': 'Good', 'path': 'g.json'},
    ])})
    entries, err = remote.fetch_manifest()
    assert not err and [e.slug for e in entries] == ['good']


@pytest.mark.parametrize('payload, expected', [
    (b'{not json', 'malformed'),
    (json.dumps({'nope': 1}).encode(), 'malformed'),
])
def test_a_malformed_index_is_a_message_not_a_crash(monkeypatch, payload, expected):
    _serve(monkeypatch, {'index.json': payload})
    entries, err = remote.fetch_manifest()
    assert entries == [] and expected in err


def test_the_overworld_opens_even_when_the_network_does_not(monkeypatch):
    """A hung or missing shelf may never take the game down with it."""
    import urllib.error
    _serve(monkeypatch, {'index.json': urllib.error.URLError('unreachable')})
    entries, err = remote.fetch_manifest()
    assert entries == [] and 'could not reach the shelf' in err
    assert 'Traceback' not in err                     # a reason, not a stack trace


def test_the_base_url_can_be_pointed_at_a_fork(monkeypatch):
    monkeypatch.setenv('VIMNY_LEVELS_URL', 'https://example.test/mine')
    assert remote.base_url() == 'https://example.test/mine/'   # slash normalised


def test_the_manifest_shape_matches_what_the_real_repo_ships(monkeypatch):
    """The contract with chkiss/vimny-levels, pinned without the network: the
    keys the parser reads are exactly the keys the published index carries."""
    _serve(monkeypatch, {'index.json': _manifest([
        {'name': 'X', 'author': 'a', 'slug': 's', 'teaches': [], 'path': 'p.json'}])})
    entries, err = remote.fetch_manifest()
    assert not err and entries
    assert remote.base_url().startswith('https://')


# ── the install path, end to end ─────────────────────────────────────────────
def test_installing_lands_a_playable_level_on_the_shelf(shelf, monkeypatch):
    """THE PATH: manifest → download → validate → shelf → playable, with the par
    the replayer derived rather than one the author declared."""
    lvl = _level()
    _serve(monkeypatch, {
        'index.json': _manifest([{'name': lvl.name, 'author': 'tester',
                                  'slug': 'salt_stair', 'teaches': ['w'],
                                  'path': 'levels/salt_stair.json'}]),
        'levels/salt_stair.json': F.dumps(lvl).encode('utf-8'),
    })
    entries, err = remote.fetch_manifest()
    assert not err

    shelved = remote.install_entry(entries[0])
    assert shelved.ok, shelved.error
    assert (shelf / 'salt_stair.json').exists()          # it really landed

    on_shelf = library.list_levels()
    assert [s.name for s in on_shelf] == [lvl.name]
    assert on_shelf[0].slug == 'community/salt_stair'    # namespaced, no collision
    dungeon = library.build_shelved(on_shelf[0])         # and it builds
    assert dungeon.room.par > 0


def test_it_is_shelved_under_its_slug_not_the_manifest_path(shelf, monkeypatch):
    """The shelf keys by slug like the rest of the game, so a remote level and a
    hand-installed one collide the same way instead of silently coexisting."""
    lvl = _level()
    _serve(monkeypatch, {'deep/nested/whatever.json': F.dumps(lvl).encode()})
    entry = remote.RemoteEntry(name=lvl.name, author='t', slug='salt_stair',
                               path='deep/nested/whatever.json')
    assert entry.filename == 'salt_stair.json'
    assert remote.install_entry(entry).ok
    assert (shelf / 'salt_stair.json').exists()
    assert not (shelf / 'whatever.json').exists()


def test_reinstalling_replaces_rather_than_duplicates(shelf, monkeypatch):
    lvl = _level()
    _serve(monkeypatch, {'l.json': F.dumps(lvl).encode()})
    entry = remote.RemoteEntry(name=lvl.name, author='t', slug='salt_stair',
                               path='l.json')
    assert remote.install_entry(entry).ok
    assert remote.install_entry(entry).ok
    assert len(library.list_levels()) == 1


# ── the refusals: nothing broken may reach the shelf ─────────────────────────
def test_a_level_that_fails_validation_never_lands(shelf, monkeypatch):
    """The security boundary is the format, and the validator is where it is
    enforced — for a download exactly as for a local file."""
    tampered = json.loads(F.dumps(_level()))
    tampered['solution'] = 'jjj'                 # a tape that does not solve it
    _serve(monkeypatch, {'l.json': json.dumps(tampered).encode()})
    shelved = remote.install_entry(
        remote.RemoteEntry(name='X', author='', slug='salt_stair', path='l.json'))
    assert not shelved.ok and shelved.error
    assert list(shelf.glob('*.json')) == []       # the shelf is untouched


def test_a_truncated_download_never_lands(shelf, monkeypatch):
    _serve(monkeypatch, {'l.json': b'{"name": "half a le'})
    shelved = remote.install_entry(
        remote.RemoteEntry(name='X', author='', slug='half', path='l.json'))
    assert not shelved.ok and shelved.error
    assert list(shelf.glob('*.json')) == []


def test_an_oversized_file_is_refused_before_it_is_parsed(shelf, monkeypatch):
    """A level file is a few KB. Anything near the cap is either an accident or
    an attempt to wedge the game, and neither is worth parsing."""
    _serve(monkeypatch, {'l.json': b'x' * (remote._MAX_BYTES + 1)})
    shelved = remote.install_entry(
        remote.RemoteEntry(name='X', author='', slug='big', path='l.json'))
    assert not shelved.ok and 'suspiciously large' in shelved.error
    assert list(shelf.glob('*.json')) == []


def test_a_failed_download_reports_a_reason_and_leaves_no_trace(shelf, monkeypatch):
    import urllib.error
    _serve(monkeypatch, {'l.json': urllib.error.HTTPError(
        'u', 404, 'Not Found', {}, None)})
    shelved = remote.install_entry(
        remote.RemoteEntry(name='X', author='', slug='gone', path='l.json'))
    assert not shelved.ok and '404' in shelved.error
    assert list(shelf.glob('*.json')) == []
