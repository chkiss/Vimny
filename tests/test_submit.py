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

"""`:submit` — the prefilled pull request.

The whole feature is one URL, so these tests are mostly about that URL being
right: the correct repo, the path the shelf's manifest will look in, and the
author's actual file inside it. The rest guard the two promises the page makes
to a person about to publish under their own name — that nothing is sent
without an explicit keypress, and that Vimny opens no connection itself.
"""
from urllib.parse import parse_qs, urlparse

import pytest

import main
import vimny.sharing.format as F
import vimny.sharing.submit as SUBMIT


def _level(name='The Hollow Vault', author='Ren'):
    return F.Level(name=name, author=author, teaches=['dw'],
                   solution='dw0G', intro='')


class _Report:
    par, budget = 12, 17
    ok, errors, warnings = True, [], []


class _FakeTerm:
    """Enough terminal to render into and to answer one keypress."""
    def __init__(self, key='q'):
        self.printed, self.key, self.keys_read = [], key, 0
        self.height, self.width = 41, 100
        self.normal = self.home = self.clear = ''

    def on_color_rgb(self, *a):  return ''
    def color_rgb(self, *a):     return ''
    @property
    def bold(self):              return ''
    def move_yx(self, y, x):     return ''
    def inkey(self, *a, **k):
        self.keys_read += 1
        return self.key


@pytest.fixture
def term(monkeypatch):
    t = _FakeTerm()
    monkeypatch.setattr('builtins.print',
                        lambda *a, **k: t.printed.append(' '.join(map(str, a))))
    return t


@pytest.fixture(autouse=True)
def _sandbox_submit_dir(monkeypatch, tmp_path):
    """Never write into the player's real ~/.Vimny."""
    monkeypatch.setattr(main, 'submission_dir', lambda: tmp_path / 'submit')
    return tmp_path / 'submit'


# ── the URL ───────────────────────────────────────────────────────────────────

def test_the_url_carries_the_level_to_the_path_the_shelf_reads():
    lvl = _level()
    url, prefilled = SUBMIT.build_url(lvl, 'hollow-vault')
    assert prefilled
    parts = urlparse(url)
    assert parts.netloc == 'github.com'
    assert parts.path == f'/{SUBMIT.DEFAULT_REPO}/new/{SUBMIT.DEFAULT_BRANCH}'
    q = parse_qs(parts.query)
    # the path a submission must land on, or the manifest never finds it
    assert q['filename'] == ['levels/hollow-vault.json']
    # and the file itself, byte-for-byte what `:publish` would have shelved
    assert q['value'] == [F.dumps(lvl)]
    assert 'The Hollow Vault' in q['message'][0]


def test_an_oversized_level_still_gets_a_form_just_not_a_filled_one():
    """Degrading is not failing: the author still lands on the right page."""
    lvl = _level()
    lvl.intro = 'x' * (SUBMIT.URL_LIMIT * 2)
    url, prefilled = SUBMIT.build_url(lvl, 'hollow-vault')
    assert not prefilled
    assert len(url) < SUBMIT.URL_LIMIT
    assert 'value=' not in url
    assert parse_qs(urlparse(url).query)['filename'] == ['levels/hollow-vault.json']


def test_the_repo_can_be_pointed_at_a_fork(monkeypatch):
    monkeypatch.setenv('VIMNY_LEVELS_REPO', 'someone/their-levels')
    monkeypatch.setenv('VIMNY_LEVELS_BRANCH', 'trunk')
    url, _ = SUBMIT.build_url(_level(), 'x')
    assert urlparse(url).path == '/someone/their-levels/new/trunk'


def test_the_slug_matches_the_one_publish_would_use():
    from vimny.save.save_manager import _slug
    name = 'The Hollow Vault'
    assert SUBMIT.submit_slug(_level(name=name)) == _slug(name) == 'the_hollow_vault'


# ── the page ──────────────────────────────────────────────────────────────────

def test_nothing_opens_without_the_explicit_key(term, _sandbox_submit_dir):
    opened = []
    term.key = 'q'
    msg = main.run_submit(term, 80, 33, _level(), 'hollow-vault', _Report(),
                          opener=opened.append)
    assert opened == [], 'a browser opened on a key that was not `o`'
    assert 'Not sent' in msg
    # …but the link is written down either way, so the author can use it later
    assert (_sandbox_submit_dir / 'hollow-vault.url').exists()


def test_o_opens_exactly_the_built_url(term):
    opened = []
    term.key = 'o'
    main.run_submit(term, 80, 33, _level(), 'hollow-vault', _Report(),
                    opener=lambda u: opened.append(u) or True)
    assert opened == [SUBMIT.build_url(_level(), 'hollow-vault')[0]]


def test_the_page_names_the_repo_the_byline_and_who_sends_it(term):
    main.run_submit(term, 80, 33, _level(), 'hollow-vault', _Report(),
                    opener=lambda u: True)
    screen = '\n'.join(term.printed)
    assert SUBMIT.DEFAULT_REPO in screen
    assert 'by Ren' in screen              # the byline they will be credited under
    assert 'par 12' in screen
    assert 'pull request' in screen
    # the promise that makes this safe to press
    assert 'holds no account' in screen


def test_a_browser_that_refuses_says_where_the_link_is(term):
    term.key = 'o'
    msg = main.run_submit(term, 80, 33, _level(), 'hollow-vault', _Report(),
                          opener=lambda u: False)
    assert 'No browser' in msg and '.url' in msg


def test_a_browser_that_raises_does_not_escape_into_the_forge(term):
    term.key = 'o'
    def _boom(url):
        raise RuntimeError('no display')
    msg = main.run_submit(term, 80, 33, _level(), 'hollow-vault', _Report(),
                          opener=_boom)
    assert 'no display' in msg and '.url' in msg


def test_the_fallback_file_is_written_beside_the_link(term, _sandbox_submit_dir):
    """The oversized case tells the author to paste the file; it must be there."""
    main.run_submit(term, 80, 33, _level(), 'hollow-vault', _Report(),
                    opener=lambda u: True)
    saved = _sandbox_submit_dir / 'hollow-vault.json'
    assert F.loads(saved.read_text(encoding='utf-8')).name == 'The Hollow Vault'


# ── the gate ──────────────────────────────────────────────────────────────────

def test_submit_refuses_an_invalid_draft_and_an_empty_byline():
    """The two refusals live in `run_dungeon`'s dispatch; assert on its source
    so a reorder that drops either one is caught. A level that does not validate
    cannot be finished by a stranger, and a byline is never guessed from the
    save name — it is the author's to choose."""
    import inspect
    src = inspect.getsource(main.run_dungeon)
    branch = src.split("cmd == 'submit'")[1][:1400]
    assert 'Not shippable yet' in branch
    assert '_rep.ok' in branch
    assert '_draft.level.author.strip()' in branch
    assert ':author <name>' in branch


def test_submit_never_opens_a_connection_itself():
    """The safety story is "it is a link". If `sharing.submit` ever grew an HTTP
    client, the page's promise would become false."""
    import inspect
    src = inspect.getsource(SUBMIT)
    for banned in ('urlopen', 'urllib.request', 'requests', 'http.client', 'socket'):
        assert banned not in src, f'{banned} has no business in a URL builder'
