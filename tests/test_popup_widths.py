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

"""The forge pickers' box: one width, and nothing cut mid-word.

Every forge command that takes an argument opens a menu when typed bare
(`:entity`, `:paint`, `:fill`, `:rune`, `:teaches`, `:requires`). They were 62
columns and their contents are PROSE — the brazier's palette note runs to 135
characters — so rows were sliced at the border and the reader was told less than
nothing: "…stand beside it and p (east) / P (".

Two rules, both asserted here. Every picker uses `POPUP_IW`, so they cannot
drift apart again. And no row is ever hard-sliced: `_popup_fit` cuts at a word
boundary and says so, with the full text under the cursor in the detail pane.
"""
import vimny.game as main


def _row_widths(rows, width):
    return [len(main._popup_fit(r, width)) for r in rows]


# ── one width ────────────────────────────────────────────────────────────────
def test_the_box_fits_the_narrowest_terminal_the_game_supports():
    """80 columns is the floor (`render.utils.inner_w`). The box is BOX_IW + 4
    including its borders and must sit INSIDE the game frame, not on top of it."""
    from vimny.render.utils import inner_w

    class _T:
        width = 80
    iw = inner_w(_T())
    box = main.POPUP_IW + 4
    col_off = max(1, (iw + 2 - box) // 2)
    assert box <= iw                      # inside the playfield
    assert col_off + box <= _T().width    # and on the screen


def test_every_picker_shares_the_one_width():
    """Three helpers had three separate literals. A width that is written down
    once cannot drift."""
    import inspect
    for fn in (main._pick_entity, main._pick_one, main._pick_many):
        src = inspect.getsource(fn)
        assert 'BOX_IW = POPUP_IW' in src, fn.__name__
        assert 'BOX_IW = 6' not in src and 'BOX_IW = 5' not in src


# ── nothing cut mid-word ─────────────────────────────────────────────────────
def test_a_row_that_fits_is_left_exactly_alone():
    assert main._popup_fit(' goblin  a chaser', 74) == ' goblin  a chaser'


def test_an_overlong_row_is_cut_at_a_word_and_says_so():
    text = ' brazier  ' + 'word ' * 40
    fit = main._popup_fit(text, 74)
    assert len(fit) <= 74
    assert fit.endswith('…')
    assert not fit[:-2].endswith('wor')     # never mid-word


def test_the_entity_palette_still_overflows_which_is_why_the_pane_exists():
    """This is not a wish: the palette is prose and outgrows any width. The test
    pins that the OVERFLOW IS HANDLED, not that it went away."""
    over = [k for k, v in main._ENTITY_PALETTE.items()
            if len(f' {k:<16}{v[1]}') > main.POPUP_IW]
    assert over, 'if this ever empties, the detail pane is dead code'
    for kind in over:
        note = main._ENTITY_PALETTE[kind][1]
        lines = main._popup_wrap(note, main.POPUP_IW - 3)
        assert lines and all(len(l) <= main.POPUP_IW - 3 for l in lines)


def test_no_palette_row_is_cut_below_its_kind_name():
    """The kind is the one thing a row may never lose — it is what the author
    types afterwards."""
    for kind, spec in main._ENTITY_PALETTE.items():
        fit = main._popup_fit(f' {kind:<16}{spec[1]}', main.POPUP_IW)
        assert kind in fit, kind


def test_wrapping_keeps_every_word_when_it_has_the_room():
    note = 'a standing flame that a pasted fire lights'
    assert ' '.join(main._popup_wrap(note, 40)) == note


def test_wrapping_elides_rather_than_dropping_the_tail_silently():
    lines = main._popup_wrap('word ' * 60, 30, limit=2)
    assert len(lines) == 2 and lines[-1].endswith('…')


def test_a_title_too_long_for_its_box_clips_rather_than_breaking_the_border():
    """The title was the one string in the box that could NOT clip: it is padded
    with `max(0, BOX_IW - len(title) - 1)`, so an over-long one padded by zero
    and pushed the right border out. A broken frame reads as the box being
    wrong; an ellipsis reads as the text being long."""
    long_title = 'brazier — ' + 'set what you need ' * 6
    assert len(long_title) > main.POPUP_IW
    assert len(main._popup_fit(long_title, main.POPUP_IW - 1)) <= main.POPUP_IW - 1


def test_the_reliquary_scroll_rows_all_come_out_the_same_width():
    """Its description column used to be a second magic number (25) that would
    not follow the box width. It is derived now, so this is the check that the
    arithmetic still lands: every row of the box, one width."""
    import contextlib
    import io
    import re

    from blessed import Terminal
    term = Terminal(force_styling=None)
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        main._show_reliquary_scroll(term, 78, 36, known=set())
    raw = re.sub(r'\x1b\[[0-9;?]*[a-zA-Z]', '', buf.getvalue())
    bars = [i for i, ch in enumerate(raw) if ch == '║']
    assert bars, 'the scroll drew no box at all'
    spans = {bars[i + 1] - bars[i] for i in range(0, len(bars) - 1, 2)}
    assert len(spans) == 1, f'ragged box: {sorted(spans)}'


def test_the_chosen_summary_wraps_instead_of_losing_its_tail():
    """`:teaches` with eight tokens overran the box and silently truncated — so
    the author could not see the very thing they were picking."""
    picked = ' '.join(['visual_block', 'visual_line', 'text_obj', 'ex_range',
                       'setwrap', 'writeas', 'reload', 'line_step', 'g_family',
                       'reg_named'])
    assert len(picked) > main.POPUP_IW
    lines = main._popup_wrap(picked, main.POPUP_IW - 1, limit=3)
    assert ' '.join(lines) == picked         # nothing lost
