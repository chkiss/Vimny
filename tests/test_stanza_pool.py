# Vimny — a Vim-teaching dungeon crawler.
# Copyright (C) 2026 Chas Kissick
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""The STANZA pool — verses whose LINE ORDER the player knows by heart.

The pool's whole job is to be a cue no plaque has to give, so what is asserted
here is the properties a level leans on when it scrambles a verse and asks for
one line back: three lines at least, all distinct, no line repeated between
stanzas, and a geometric filter that picks a verse by what fits the floor.
"""
import pytest
from vimny.content import proverbs as pv


def test_every_stanza_has_at_least_three_lines():
    """"The oldest of the cuts" means nothing with fewer than three."""
    assert pv.STANZAS
    for s in pv.STANZAS:
        assert len(s) >= 3, s


@pytest.mark.parametrize('stanza', pv.STANZAS)
def test_a_stanza_never_repeats_a_line(stanza):
    """A repeated line would make "which one came back" unanswerable — the
    player could not tell a correct retrieval from a lucky one."""
    assert len(set(stanza)) == len(stanza), stanza


def test_no_line_appears_in_two_stanzas():
    lines = [line for s in pv.STANZAS for line in s]
    assert len(set(lines)) == len(lines)


@pytest.mark.parametrize('stanza', pv.STANZAS)
def test_lines_are_carved_not_printed(stanza):
    """Lower case, unpunctuated, single-spaced — the house form for floor text."""
    for line in stanza:
        assert line == line.lower(), line
        assert line == ' '.join(line.split()), line
        assert all(ch.isalpha() or ch == ' ' for ch in line), line


def test_the_width_filter_keeps_only_verses_that_fit():
    lo, hi = 20, 30
    got = pv.stanzas_of_width(lo, hi)
    assert got, 'the pool must hold something for an ordinary floor'
    for s in got:
        assert all(lo <= len(line) <= hi for line in s), s
    for s in set(pv.STANZAS) - set(got):
        assert any(not lo <= len(line) <= hi for line in s), s


def test_an_impossible_width_draws_nothing_rather_than_guessing():
    assert pv.stanzas_of_width(1, 2) == ()
