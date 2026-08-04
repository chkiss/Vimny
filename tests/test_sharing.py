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

"""The community level pipeline: format, validator, replayer, library.

The rules under test are the ones that keep the feature safe and honest — a
level is data and never code, par is derived and never declared, and a fill
resolves identically for the author and every player.
"""
import json
import math

import pytest

import vimny.generation.dungeon_gen as dg
from vimny.content.levels import known_commands
from vimny.engine.world import CellType
from vimny.sharing import format as F
from vimny.sharing import library, vocab
from vimny.sharing.replay import replay_tape, tape_to_keys
from vimny.sharing.validate import validate

SEED = 42


def _shipped_as_level(slug: str, seed: int = SEED) -> F.Level:
    """Export a shipped level into the community format — the worked example.

    Using a real level rather than a hand-written fixture means these tests
    exercise the format against geometry and tapes the game already trusts.
    """
    room    = dg.__dict__[f'build_dungeon_{slug}'](seed).room
    known   = known_commands(slug)
    teaches = ['w']
    return F.from_room(room, 'Test Level', author='tester',
                       teaches=teaches,
                       requires=[k for k in known if k not in teaches])


# ── The format ────────────────────────────────────────────────────────────────

def test_rle_rows_round_trip():
    cells = ([CellType.WALL] * 3 + [CellType.FLOOR] * 60 + [CellType.WATER]
             + [CellType.WALL] * 16)
    encoded = F.encode_row(cells)
    assert encoded == '3W60F A16W'.replace(' ', '')
    assert F.expand_row(encoded, len(cells), 0) == cells


def test_unknown_cell_code_names_the_row():
    with pytest.raises(F.LevelFormatError) as exc:
        F.expand_row('3W2Q', 5, 7)
    assert 'cells[7]' in str(exc.value) and 'Q' in str(exc.value)


def test_row_that_does_not_fill_the_width_is_refused():
    with pytest.raises(F.LevelFormatError) as exc:
        F.expand_row('3W', 10, 0)
    assert 'expands to 3 cells, expected 10' in str(exc.value)


def test_unknown_top_level_key_is_refused_not_ignored():
    """A silently dropped key is a level that plays differently from the one
    its author tested."""
    lvl = _shipped_as_level('rune_halls')
    data = json.loads(F.dumps(lvl))
    data['budget'] = 1                       # authors do not get to set this
    with pytest.raises(F.LevelFormatError) as exc:
        F.parse(data)
    assert 'budget' in str(exc.value)


def test_wrong_schema_version_is_refused():
    lvl = _shipped_as_level('rune_halls')
    data = json.loads(F.dumps(lvl))
    data['schema'] = 99
    with pytest.raises(F.LevelFormatError) as exc:
        F.parse(data)
    assert 'schema' in str(exc.value)


def test_shipped_level_round_trips_through_the_format():
    room = dg.build_dungeon_rune_halls(SEED).room
    rebuilt = F.build(F.loads(F.dumps(_shipped_as_level('rune_halls'))),
                      par=room.par).room
    assert rebuilt.cells == room.cells
    assert len(rebuilt.char_runs) == len(room.char_runs)
    assert rebuilt.answer == room.answer
    assert rebuilt.spawn_pos == room.spawn_pos and rebuilt.exit_pos == room.exit_pos


def test_entity_attributes_survive_the_format():
    """kind/row/col is not an entity — a goblin without its AI and tag is a
    different creature wearing the same letter."""
    lvl = _shipped_as_level('dummy')
    rebuilt = F.build(F.loads(F.dumps(lvl))).room
    echo = [e for e in rebuilt.entities if e.tag == 'echo']
    assert echo and echo[0].hp == 2 and echo[0].shade in (0, 3)
    assert any(e.ai == 'chase' for e in rebuilt.entities)
    assert any(e.swole for e in rebuilt.entities)


# ── Fills ─────────────────────────────────────────────────────────────────────

def _blank_level(**kw) -> F.Level:
    rows, cols = 8, 30
    cells = ['30W'] + [f'W{cols - 2}FW'] * (rows - 2) + ['30W']
    return F.Level(name='Fill Test', seed=7, rows=rows, cols=cols, cells=cells,
                   spawn=(1, 1), exit=(1, 2), solution='l', **kw)


def test_fill_lays_words_from_the_named_pool():
    lvl = _blank_level(fills=[F.Fill(region=(2, 2, 4, 25), pool='plain',
                                     length=(4, 4))])
    room = F.build(lvl).room
    assert room.char_runs, 'the fill laid no text'
    assert all(len(ru.symbols) == 4 for ru in room.char_runs)
    pool = vocab.word_table('plain')
    assert all(''.join(ru.symbols) in pool[4] for ru in room.char_runs)


def test_fill_is_deterministic_from_the_seed():
    """The tape was recorded against one arrangement of words. If a fill
    resolved differently for the next player, the level is not the one the
    tape solves."""
    lvl = _blank_level(fills=[F.Fill(region=(2, 2, 5, 25), pool='mixed')])
    a = [(r.row, r.col, ''.join(r.symbols)) for r in F.build(lvl).room.char_runs]
    b = [(r.row, r.col, ''.join(r.symbols)) for r in F.build(lvl).room.char_runs]
    assert a == b and a


def test_fill_never_paints_text_into_stone():
    lvl = _blank_level(fills=[F.Fill(region=(0, 0, 7, 29), pool='plain')])
    room = F.build(lvl).room
    for ru in room.char_runs:
        for i in range(len(ru.symbols)):
            assert room.cells[ru.row][ru.col + i] in (CellType.FLOOR,
                                                      CellType.CORRIDOR)


def test_custom_pool_uses_the_authors_own_words():
    lvl = _blank_level(fills=[F.Fill(region=(2, 2, 3, 25), pool='custom',
                                     length=(4, 4))],
                       vocabulary=['chat', 'chien', 'oui'])
    room = F.build(lvl).room
    assert room.char_runs
    assert all(''.join(ru.symbols) == 'chat' for ru in room.char_runs)


# ── The replayer ──────────────────────────────────────────────────────────────

def test_tape_notation_maps_typed_space_and_enter():
    keys = tape_to_keys('a b<Space>c<CR>')
    assert [str(k) for k in keys] == ['a', 'b', ' ', 'c', '\r']


@pytest.mark.parametrize('slug', ['counting_crypts', 'rune_halls', 'lineheads',
                                  'joiners_gate', 'operators_vault'])
def test_replaying_a_shipped_tape_costs_exactly_par(slug):
    """The replayer IS the par oracle — if it disagreed with the shipped
    solvers there would be no reason to trust a community par either."""
    builder = dg.__dict__[f'build_dungeon_{slug}']
    room = builder(SEED).room
    res  = replay_tape(builder(SEED), slug, room.answer, known=known_commands(slug))
    assert res.won, f'{slug}: canonical tape no longer wins: {res.error}'
    assert res.spent == room.par


def test_a_tape_that_strands_reports_why_rather_than_hanging():
    res = replay_tape(dg.build_dungeon_rune_halls(SEED), 'rune_halls', 'jjjj')
    assert not res.ok


# ── The validator ─────────────────────────────────────────────────────────────

def test_a_valid_level_derives_par_and_budget():
    room = dg.build_dungeon_rune_halls(SEED).room
    rep  = validate(_shipped_as_level('rune_halls'))
    assert rep.ok, rep.errors
    assert rep.par == room.par
    assert rep.budget == math.ceil(rep.par * 1.4)


def test_par_comes_from_the_replay_not_the_file():
    """Authors do not get to pick a budget — a declared one would let a level
    be tuned to hide a sloppy route."""
    lvl = _shipped_as_level('rune_halls')
    rep = validate(lvl)
    dungeon = F.build(lvl, par=rep.par)
    assert dungeon.room.budget == math.ceil(rep.par * 1.4)


def test_a_level_missing_a_tape_is_refused():
    lvl = _blank_level()
    lvl.solution = ''
    rep = validate(lvl)
    assert not rep.ok
    assert any('solution' in e for e in rep.errors)


def test_a_tape_that_does_not_win_is_refused():
    lvl = _blank_level()
    lvl.solution = 'jjj'
    rep = validate(lvl)
    assert not rep.ok
    assert any(e.startswith('[solvable]') for e in rep.errors)


def test_a_tape_using_an_undeclared_command_is_refused():
    """Rule 6 without a second implementation: the replay runs against the
    level's own declared token set, so a command it neither requires nor
    teaches is refused by the same gate the curriculum uses."""
    lvl = _shipped_as_level('rune_halls')
    lvl.requires = ['h', 'j', 'k', 'l']       # the real tape needs far more
    lvl.teaches  = ['w']
    rep = validate(lvl)
    assert not rep.ok
    assert any(e.startswith('[solvable]') for e in rep.errors)


def test_double_width_vocabulary_is_refused():
    """One glyph per cell is the whole model; a wide character silently
    corrupts every column downstream of it."""
    lvl = _blank_level(vocabulary=['日本語'])
    rep = validate(lvl)
    assert any('double-width' in e for e in rep.errors)


def test_control_characters_in_vocabulary_are_refused():
    lvl = _blank_level(vocabulary=['a\x07b'])
    rep = validate(lvl)
    assert any('control' in e for e in rep.errors)


def test_oversized_room_is_refused():
    lvl = _blank_level()
    lvl.rows = F.MAX_ROWS + 1
    rep = validate(lvl)
    assert any(e.startswith('[bounds]') for e in rep.errors)


def test_spawn_inside_stone_is_refused():
    lvl = _blank_level()
    lvl.spawn = (0, 0)
    rep = validate(lvl)
    assert any('spawn' in e for e in rep.errors)


def test_an_alternate_must_teach_exactly_the_same_lesson():
    lvl = _shipped_as_level('rune_halls')
    lvl.alternate = 'rune_halls'
    lvl.teaches = ['w', 'b']                 # rune_halls teaches w, b, e
    rep = validate(lvl)
    assert any(e.startswith('[alternate]') for e in rep.errors)


def test_an_alternate_may_not_require_a_command_taught_later():
    """The other half of "same place in the curriculum".

    Teaching the right lesson is not enough: an alternate that ASSUMES a command
    from further down the curriculum is unplayable at the point it sits, because
    the player has not met it yet.
    """
    lvl = _shipped_as_level('rune_halls')
    lvl.alternate = 'rune_halls'
    lvl.teaches   = ['w', 'b', 'e']
    lvl.requires  = ['h', 'j', 'k', 'l', 'f']    # f is taught much later
    rep = validate(lvl)
    assert any(e.startswith('[alternate]') and "'f'" in e for e in rep.errors)


def test_an_alternate_may_require_anything_taught_before_it():
    lvl = _shipped_as_level('rune_halls')
    lvl.alternate = 'rune_halls'
    lvl.teaches   = ['w', 'b', 'e']
    rep = validate(lvl)
    assert not any(e.startswith('[alternate]') for e in rep.errors), rep.errors


def test_alternate_must_name_a_real_slug():
    lvl = _blank_level()
    lvl.alternate = 'not_a_level'
    rep = validate(lvl)
    assert any('not a shipped level slug' in e for e in rep.errors)


def test_requires_and_teaches_may_not_overlap():
    lvl = _blank_level()
    lvl.requires = ['w']
    lvl.teaches = ['w']
    rep = validate(lvl)
    assert any(e.startswith('[scope]') for e in rep.errors)


def test_every_rejection_names_its_rule():
    """An authoring tool whose only error is 'invalid level' trains people to
    give up."""
    lvl = _blank_level()
    lvl.solution = ''
    lvl.rows = 999
    rep = validate(lvl)
    assert rep.errors
    for e in rep.errors:
        assert e.startswith('[') and ']' in e


# ── The library ───────────────────────────────────────────────────────────────

def test_library_validates_on_load_not_only_on_submission(tmp_path, monkeypatch):
    """A hand-edited file gets the same scrutiny as a reviewed one."""
    monkeypatch.setattr(library, 'LEVELS_DIR', tmp_path)
    good = _shipped_as_level('rune_halls')
    (tmp_path / 'good.json').write_text(F.dumps(good), encoding='utf-8')
    tampered = json.loads(F.dumps(good))
    tampered['solution'] = 'jjj'
    (tmp_path / 'bad.json').write_text(json.dumps(tampered), encoding='utf-8')

    shelved = {s.path.name: s for s in library.list_levels()}
    assert shelved['good.json'].ok
    assert not shelved['bad.json'].ok
    assert shelved['bad.json'].error


def test_a_broken_level_is_listed_with_its_reason_not_hidden(tmp_path, monkeypatch):
    """A file that vanishes from the list is a player wondering where their
    download went."""
    monkeypatch.setattr(library, 'LEVELS_DIR', tmp_path)
    (tmp_path / 'junk.json').write_text('{not json', encoding='utf-8')
    listed = library.list_levels()
    assert len(listed) == 1 and not listed[0].ok and listed[0].error


def test_community_slugs_cannot_collide_with_shipped_ones(tmp_path, monkeypatch):
    from vimny.content.levels import LEVELS
    monkeypatch.setattr(library, 'LEVELS_DIR', tmp_path)
    (tmp_path / 'rune_halls.json').write_text(
        F.dumps(_shipped_as_level('rune_halls')), encoding='utf-8')
    shelf = library.list_levels()[0]
    assert shelf.slug.startswith('community/')
    assert shelf.slug not in {lv['slug'] for lv in LEVELS}


def test_build_refuses_an_entry_that_did_not_validate(tmp_path, monkeypatch):
    monkeypatch.setattr(library, 'LEVELS_DIR', tmp_path)
    (tmp_path / 'junk.json').write_text('{not json', encoding='utf-8')
    with pytest.raises(ValueError):
        library.build_shelved(library.list_levels()[0])


# ── The bonus wing in the overworld ───────────────────────────────────────────

def _shelf_in(tmp_path, monkeypatch, name='The Salt Stair'):
    monkeypatch.setattr(library, 'LEVELS_DIR', tmp_path)
    lvl = _shipped_as_level('rune_halls')
    lvl.name = name
    (tmp_path / 'salt_stair.json').write_text(F.dumps(lvl), encoding='utf-8')
    return library.list_levels()


def test_community_levels_appear_in_the_overworld_buffer(tmp_path, monkeypatch):
    from vimny.content.levels import LEVELS
    from vimny.render.overworld import build_lines, line_search_text
    shelf = _shelf_in(tmp_path, monkeypatch)
    lines = build_lines(LEVELS[:2], [], shelf)
    assert [ln['type'] for ln in lines[-2:]] == ['subhdr', 'community']
    assert line_search_text(lines[-2]) == 'community/'
    # the author trails the name in column one, and search sees what is drawn
    assert line_search_text(lines[-1]) == 'The Salt Stair by tester'


def test_the_wing_sits_after_the_curriculum(tmp_path, monkeypatch):
    """Extra content, not part of the designed sequence."""
    from vimny.content.levels import LEVELS
    from vimny.render.overworld import build_lines
    shelf = _shelf_in(tmp_path, monkeypatch)
    lines = build_lines(LEVELS[:3], [], shelf)
    last_level = max(i for i, ln in enumerate(lines) if ln['type'] == 'level')
    first_comm = min(i for i, ln in enumerate(lines) if ln['type'] == 'community')
    assert first_comm > last_level


def test_a_shelved_level_builds_with_the_replayed_par(tmp_path, monkeypatch):
    room  = dg.build_dungeon_rune_halls(SEED).room
    shelf = _shelf_in(tmp_path, monkeypatch)[0]
    built = library.build_shelved(shelf).room
    assert built.par == room.par
    assert built.budget == math.ceil(built.par * 1.4)


def test_the_format_never_executes_anything():
    """The format is the security boundary: 'download a level' must never mean
    'run a stranger's Python'. Nothing in the loader path evaluates author input.
    """
    import inspect
    for mod in (F, library, vocab):
        src = inspect.getsource(mod)
        for danger in ('eval(', 'exec(', '__import__(', 'pickle', 'subprocess'):
            assert danger not in src, f'{mod.__name__} reaches for {danger}'
