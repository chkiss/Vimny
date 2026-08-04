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

"""The admin karaoke answer-sheet tracker (main.run_dungeon + render.renderer).

As an admin types the canonical solve, the answer tape's playhead (room.answer_pos)
advances key-for-key.  The NORMAL/VISUAL and INSERT trackers were always there; this
suite guards the two modes that were added later and had silently never worked:

  * COMMAND mode  — `:s` / `:g` ex-commands (the Spellwright's Forge)
  * SEARCH  mode  — `/pat` and `?pat` (Seekers' Labyrinth, the Waypoint Sanctum)

The tape marks Enter with the glyph '<CR>' and separates tokens with spaces (stripped for
matching); _replay translates that to the raw keystrokes an admin would press.
"""
import pytest
from blessed import Terminal
from blessed.keyboard import Keystroke

import main
from vimny.engine.tape import to_keys
import vimny.generation.dungeon_gen as dg
import vimny.generation.dungeon_gen as dg
from vimny.engine.tape import literal_spans, ESC, ENTER, CTRL_V, SPACE


@pytest.fixture(autouse=True)
def _no_anim(monkeypatch):
    for fn in ('_win_animation', '_fireworks_animation', '_starfield_victory'):
        monkeypatch.setattr(main, fn, lambda *a, **k: None)
    # Mid-dungeon scrolls read their dismiss key via a direct term.inkey() that bypasses
    # the karaoke tracker; stub them so an automated replay doesn't consume a tape key.
    for fn in ('_show_scroll_by_id', '_render_standard_scroll',
               '_show_reliquary_scroll', '_show_catalog_scroll'):
        if hasattr(main, fn):
            monkeypatch.setattr(main, fn, lambda *a, **k: None)


def _replay(tape):
    """Karaoke tape → raw keystrokes, via the one shared translator (vimny/engine/tape.py)."""
    return to_keys(tape)


def _drive_admin(slug, dungeon):
    term = Terminal(force_styling=False)
    import vimny.render.colors as _colors
    _colors.init(term)                       # key/chest colour paths touch color_rgb()
    keys = _replay(dungeon.room.answer) + [Keystroke(c) for c in ':q!\r']
    it = iter(keys)
    term.inkey = lambda *a, **k: next(it, Keystroke(''))
    main.render_all = lambda *a, **k: None
    main.run_dungeon(term, slug, {}, player_name='admin', _dungeon=dungeon)


@pytest.mark.parametrize("slug", [
    'spellwrights_forge',   # COMMAND mode — :%s/.../g, :s/.../, :g/cursed/d
    'seekers_labyrinth',    # SEARCH forward — /vault<CR>
    'waypoint_sanctum',     # SEARCH backward — ?xyzzy<CR>
    'operators_vault',      # NORMAL operators + relic-chest scrolls (stubbed above)
    'cipher_cell',          # NORMAL r / D — a plain control
])
def test_karaoke_tape_advances_to_the_end(slug):
    d = dg.build_dungeon_spellwrights_forge(1) if slug == 'spellwrights_forge' \
        else getattr(dg, f'build_dungeon_{slug}')(1)
    room = d.room
    plain = room.answer.replace(' ', '')
    assert plain, f"{slug} has no answer tape"
    _drive_admin(slug, d)
    assert not room.answer_diverged, f"{slug}: tape diverged at {room.answer_pos}/{len(plain)}"
    assert room.answer_pos == len(plain), f"{slug}: stuck at {room.answer_pos}/{len(plain)}"


def test_non_admin_player_never_tracks_or_sees_the_tape():
    # The answer sheet is admin-only: room.answer is cleared on entry for real players.
    d = dg.build_dungeon_spellwrights_forge(1)
    term = Terminal(force_styling=False)
    keys = _replay(d.room.answer) + [Keystroke(c) for c in ':q!\r']
    it = iter(keys)
    term.inkey = lambda *a, **k: next(it, Keystroke(''))
    main.render_all = lambda *a, **k: None
    main.run_dungeon(term, 'spellwrights_forge', {}, player_name='Normand', _dungeon=d)
    assert d.room.answer == '' and d.room.answer_pos == 0


# ── Which part of the sheet is TEXT, not keys ─────────────────────────────────

def test_literal_spans_split_the_verb_from_the_words():
    """`O` is a command, `row row your boat` is a song. The sheet colours the
    two differently, so the split has to be exact."""
    tape = 'Orow<Space>row<Space>your<Space>boat<Esc> j Idown<Esc>'
    assert [tape[a:b] for a, b in literal_spans(tape)] == [
        'row', 'row', 'your', 'boat', 'down']


def test_a_typed_space_is_a_key_not_a_word():
    """`<Space>` is something the player PRESSES, so it stays a command and
    breaks the phrase around it rather than being swallowed into it."""
    tape = 'Orow<Space>boat<Esc>'
    assert [tape[a:b] for a, b in literal_spans(tape)] == ['row', 'boat']


def test_a_text_object_is_not_an_insert_verb():
    """The `i` in `diw` and the `a` in `daw` open nothing — reading them as
    verbs would paint the rest of the tape as prose."""
    assert literal_spans('j diw j . 2j daw j . G $') == []


def test_a_search_pattern_is_a_word():
    """`vault` is read off the map like any other word; `/` and `<CR>` are
    Vim. Note the `a` inside `vault` — it must not open INSERT either."""
    tape = '* n 0 x /vault<CR> $ p l'
    assert [tape[a:b] for a, b in literal_spans(tape)] == ['vault']


def test_a_substitution_marks_its_pattern_and_replacement():
    """`:%s/` and the trailing `/g` are syntax; `moo` and `quack` are words."""
    tape = ':%s/moo/quack/g<CR> 8G :s/down/up/<CR>'
    assert [tape[a:b] for a, b in literal_spans(tape)] == [
        'moo', 'quack', 'down', 'up']


def test_a_global_marks_only_its_pattern():
    """`:g`/`:v` carry a pattern and then a COMMAND — `d` is not a word."""
    tape = ':g/krzzt/d<CR> :2,19v/that/d<Space>_<CR>'
    assert [tape[a:b] for a, b in literal_spans(tape)] == ['krzzt', 'that']


def test_an_ex_line_with_no_pattern_marks_nothing():
    """`:set nu` and `:4,6&&` are all command — nothing was read off the map."""
    assert literal_spans(':set<Space>nu<CR> :4,6&&<CR> :1j|1y<CR>') == []


def test_the_verb_before_the_words_may_be_a_whole_change():
    tape = '2j ciw hot<Esc> j cithand<Esc> j^cEwell-to-do<Esc>'
    assert [tape[a:b] for a, b in literal_spans(tape)] == [
        'hot', 'hand', 'well-to-do']


def test_gi_opens_insert_though_it_starts_with_g():
    """`gU`/`g~` are operators, `gi` resumes INSERT. The g-atom rule is
    consulted before the verb table, so it must not swallow this one."""
    tape = '* 3b gU3e + gi<Space>and<Esc>'
    assert [tape[a:b] for a, b in literal_spans(tape)] == ['and']


def test_no_span_ever_contains_a_space_or_a_token():
    """Plain spaces are display spacing and `<Space>` is a keypress; neither
    belongs inside a white run."""
    for tape in ('2j ciw hot<Esc>', 'Orow<Space>boat<Esc>', ':%s/moo/quack/g<CR>'):
        for a, b in literal_spans(tape):
            span = tape[a:b]
            assert ' ' not in span and '<' not in span, span


@pytest.mark.parametrize("slug", ['sculpting_chambers', 'wet_ink',
                                  'inscription_halls', 'gauntlet'])
def test_every_span_is_text_a_player_types(slug):
    """Whatever the scanner marks must be free of tape tokens other than
    <Space> — an <Esc> or a <CR> inside a span means the run ran past its end."""
    room = getattr(dg, f'build_dungeon_{slug}')(42).room
    for a, b in literal_spans(room.answer):
        span = room.answer[a:b]
        assert ESC not in span and ENTER not in span and CTRL_V not in span, span
        assert SPACE not in span, span
