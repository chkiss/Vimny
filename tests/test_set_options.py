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

"""Block A — :set option grammar (vimny/engine/options.py).

Covers the plain/no forms (existing behaviour) plus the new toggle (!),
invert (inv), reset (&) and query (?) forms over the collapsed tri-state
number_mode ('none'|'number'|'relativenumber')."""
import pytest

from vimny.engine.options import apply_set, parse_modifier


# ── plain on / off (the pre-existing behaviour) ────────────────────────────
@pytest.mark.parametrize('start,arg,expect', [
    ('none', ' number',           'number'),
    ('none', ' nu',               'number'),
    ('number', ' nonumber',       'none'),
    ('number', ' nonu',           'none'),
    ('none', ' relativenumber',   'relativenumber'),
    ('none', ' rnu',              'relativenumber'),
    # turning off the shown option blanks the gutter
    ('relativenumber', ' nornu',  'none'),
    ('relativenumber', ' norelativenumber', 'none'),
    # turning off an option that isn't shown is a no-op
    ('number', ' nornu',          'number'),
    # the two options are mutually exclusive in the gutter
    ('relativenumber', ' number', 'number'),
    ('number', ' rnu',            'relativenumber'),
])
def test_plain_forms(start, arg, expect):
    assert apply_set(start, arg)[0] == expect


# ── toggle (!) and invert (inv) ────────────────────────────────────────────
@pytest.mark.parametrize('arg', [' nu!', ' invnu', ' invnumber', ' number!'])
def test_toggle_number_on(arg):
    assert apply_set('none', arg)[0] == 'number'

@pytest.mark.parametrize('arg', [' nu!', ' invnu'])
def test_toggle_number_off(arg):
    assert apply_set('number', arg)[0] == 'none'

def test_toggle_relativenumber():
    assert apply_set('none', ' rnu!')[0] == 'relativenumber'
    assert apply_set('relativenumber', ' invrnu')[0] == 'none'


# ── reset to default (&) ───────────────────────────────────────────────────
def test_reset_single_option():
    assert apply_set('number', ' nu&')[0] == 'none'
    assert apply_set('relativenumber', ' rnu&')[0] == 'none'

def test_reset_all():
    assert apply_set('relativenumber', ' all&')[0] == 'none'
    assert apply_set('number', ' all&')[0] == 'none'


# ── query (?) leaves the mode unchanged and echoes the state ───────────────
def test_query_does_not_mutate():
    mode, msg = apply_set('number', ' nu?')
    assert mode == 'number' and msg == 'number'
    mode, msg = apply_set('none', ' nu?')
    assert mode == 'none' and msg == 'nonumber'
    mode, msg = apply_set('relativenumber', ' rnu?')
    assert mode == 'relativenumber' and msg == 'relativenumber'


# ── unknown options are rejected without mutating ──────────────────────────
@pytest.mark.parametrize('arg', [' wrap', ' invwrap', ' nowrap', ' foo?'])
def test_unknown_option(arg):
    mode, msg = apply_set('number', arg)
    assert mode == 'number'
    assert msg.startswith('Unknown option:')


# ── parse_modifier (boolean options like hlsearch/incsearch, Block H) ───────
@pytest.mark.parametrize('arg,core,act', [
    ('hlsearch',     'hlsearch', 'on'),
    ('hls',          'hls',      'on'),
    ('nohlsearch',   'hlsearch', 'off'),
    ('nohls',        'hls',      'off'),
    ('invhls',       'hls',      'toggle'),
    ('hls!',         'hls',      'toggle'),
    ('hls&',         'hls',      'reset'),
    ('hls?',         'hls',      'query'),
    (' incsearch ',  'incsearch','on'),
    # ':set wrap' (The Archivist's Library) routes through the same generic grammar
    ('wrap',         'wrap',     'on'),
    ('nowrap',       'wrap',     'off'),
    ('invwrap',      'wrap',     'toggle'),
    ('wrap!',        'wrap',     'toggle'),
    ('wrap&',        'wrap',     'reset'),
    ('wrap?',        'wrap',     'query'),
])
def test_parse_modifier(arg, core, act):
    assert parse_modifier(arg) == (core, act)
