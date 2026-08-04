# Vimny — a Vim-teaching dungeon crawler.
# Copyright (C) 2026 Chas Kissick
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""The shared NetrwNav motion engine — the one the overworld and the scroll
library both drive. Exercised directly over a plain line buffer so the Vim
navigation (gg/G/{n}G, {/}, w, /-search, counts) is proven once, independent of
either screen's chrome."""
from blessed.keyboard import Keystroke

from vimny.engine.player import Player
from main import NetrwNav


def _K(s):
    return [Keystroke(ch) for ch in s]


def _nav(labels, sections=None, tokens=None):
    """A NetrwNav over `labels` (list of strings). `sections` gives each row's
    {/} group key (defaults to one group). Gating allows `tokens` (default all)."""
    lines = [{'text': t, 'sec': (sections[i] if sections else 'x')}
             for i, t in enumerate(labels)]
    allow = None if tokens is None else set(tokens)

    def _gate(tok, label):
        return allow is None or tok in allow

    player = Player(name='tester')
    nav = NetrwNav(player=player, get_lines=lambda: lines,
                   label=lambda ln: ln['text'], section_key=lambda ln: ln['sec'],
                   gate=_gate, avail=lambda: 10, marks={}, cursor=0)
    return nav, player


def _feed(nav, s):
    for k in _K(s):
        nav.feed(k)


def test_gg_and_G_jump_to_top_and_bottom():
    nav, _p = _nav(['alpha', 'bravo', 'charlie', 'delta'])
    _feed(nav, 'G')
    assert nav.cursor == 3
    _feed(nav, 'gg')
    assert nav.cursor == 0


def test_count_G_goes_to_line_n():
    nav, _p = _nav(['a', 'b', 'c', 'd', 'e'])
    _feed(nav, '3G')
    assert nav.cursor == 2                       # 1-indexed line 3


def test_count_j_and_k():
    nav, _p = _nav([str(i) for i in range(10)])
    _feed(nav, '4j')
    assert nav.cursor == 4
    _feed(nav, '2k')
    assert nav.cursor == 2


def test_slash_search_lands_on_the_match():
    nav, player = _nav(['alpha', 'bravo', 'charlie'])
    _feed(nav, '/charlie\r')
    assert nav.cursor == 2
    assert player.last_search == ('charlie', True)


def test_n_walks_matches_and_wraps():
    nav, _p = _nav(['xy', 'foo', 'bar', 'foo', 'baz'])
    _feed(nav, '/foo\r')
    assert nav.cursor == 1
    _feed(nav, 'n')
    assert nav.cursor == 3
    _feed(nav, 'n')
    assert nav.cursor == 1                        # wrapped back to the top


def test_brace_jumps_between_sections():
    nav, _p = _nav(['h1', 'a', 'b', 'h2', 'c', 'd'],
                   sections=['nav', 'g1', 'g1', 'h', 'g2', 'g2'])
    # from row 0, } advances to the next section boundary
    _feed(nav, '}')
    assert nav.cursor == 1
    _feed(nav, '}')
    assert nav.cursor == 3


def test_dollar_and_zero_move_the_column():
    nav, _p = _nav(['hello world'])
    _feed(nav, '$')
    assert nav.col() == len('hello world') - 1
    _feed(nav, '0')
    assert nav.col() == 0


def test_w_walks_words_in_the_label():
    nav, _p = _nav(['one two three'])
    _feed(nav, 'w')
    assert nav.col() == 4                          # start of 'two'


def test_command_bubbles_up_to_the_host():
    nav, _p = _nav(['a', 'b'])
    out = None
    for k in _K(':q\r'):
        out = nav.feed(k)
    assert out == ('cmd', 'q')


def test_unknown_key_bubbles_up_as_key():
    nav, _p = _nav(['a', 'b'])
    out = nav.feed(Keystroke('D'))
    assert out == ('key', 'D', Keystroke('D'))


def test_gating_blocks_G_when_not_learned():
    nav, _p = _nav(['a', 'b', 'c'], tokens=[])     # nothing learned
    _feed(nav, 'G')
    assert nav.cursor == 0                          # G refused


def test_colors_buffer_navigates_via_the_shared_engine():
    # the colors screen exposes the same row/label/section interface, so the
    # engine drives it identically (G to the end, /-search to a colour).
    import vimny.render.colors as C
    from blessed import Terminal
    from vimny.render.color_palette import palette_rows, row_label, row_section_key
    C._term = Terminal(force_styling=True)

    rows = palette_rows()
    player = Player(name='admin')
    nav = NetrwNav(player=player, get_lines=lambda: rows, label=row_label,
                   section_key=row_section_key, gate=lambda t, l: True,
                   avail=lambda: 10, marks={}, cursor=0)
    _feed(nav, 'G')
    assert nav.cursor == len(rows) - 1
    _feed(nav, 'gg')
    assert nav.cursor == 0
    _feed(nav, '/floor_bg\r')
    assert 'floor_bg' in row_label(rows[nav.cursor])


def test_marks_set_and_return():
    nav, _p = _nav(['a', 'b', 'c', 'd'])
    _feed(nav, 'G')          # to bottom (row 3)
    _feed(nav, 'ma')         # mark it
    _feed(nav, 'gg')         # back to top
    _feed(nav, '`a')         # jump to mark
    assert nav.cursor == 3
