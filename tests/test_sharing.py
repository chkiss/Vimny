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


def test_rle_run_that_overruns_the_width_is_refused_before_expanding():
    # a hostile run count must fail fast, not allocate toward a billion cells
    with pytest.raises(F.LevelFormatError):
        F.expand_row_underwater('W99999999F', 10, 0)


def test_type_confused_json_is_a_named_format_error():
    # a top-level list (or any wrong-shaped JSON) is author error to report,
    # not an AttributeError traceback
    with pytest.raises(F.LevelFormatError):
        F.loads('[1, 2, 3]')


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


def test_an_empty_opens_seal_is_a_pure_predicate():
    """A seal with `match` but no `opens` reads the buffer and stands nowhere —
    other seals reach it by index through `requires` (the Named Vault's bays).
    The nothing-to-read guard still refuses a seal that neither reads nor opens.
    """
    spec = {'schema': 1, 'name': 't', 'seed': 1,
            'geometry': {'rows': 4, 'cols': 8,
                         'cells': ['W' * 8] * 4, 'spawn': [1, 1], 'exit': [2, 2]},
            'seals': [{'match': 'abba', 'region': [1, 0, 1, 7]},
                      {'requires': [0], 'opens': [2, 2]}]}
    lvl = F.parse(spec)
    assert lvl.seals[0].opens == ()          # parsed, not rejected
    data = json.loads(F.dumps(lvl))
    assert data['seals'][0]['opens'] == []
    back = F.loads(F.dumps(lvl))
    assert back.seals[0] == lvl.seals[0]
    with pytest.raises(F.LevelFormatError, match='nothing to read'):
        F.parse({'schema': 1, 'name': 't', 'seed': 1, 'geometry':
                 {'rows': 4, 'cols': 8, 'cells': ['W' * 8] * 4,
                  'spawn': [1, 1], 'exit': [2, 2]},
                 'seals': [{'opens': []}]})


def test_a_gone_seal_names_kinds_not_text():
    """mode='gone' is the legion rule in a file: `match` names ENTITY KINDS and
    the seal opens while none of them stands alive. It reads the whole room,
    so a region is refused — and so is a gone seal that names nothing."""
    geo = {'rows': 4, 'cols': 8, 'cells': ['W' * 8] * 4,
           'spawn': [1, 1], 'exit': [2, 2]}
    spec = {'schema': 1, 'name': 't', 'seed': 1, 'geometry': geo,
            'seals': [{'mode': 'gone', 'match': 'goblin', 'opens': [2, 2]}]}
    lvl = F.parse(spec)
    assert lvl.seals[0].mode == 'gone' and lvl.seals[0].match == ('goblin',)
    back = F.loads(F.dumps(lvl))
    assert back.seals[0] == lvl.seals[0]
    with pytest.raises(F.LevelFormatError, match='names'):
        F.parse({**spec, 'seals': [{'mode': 'gone'}]})
    with pytest.raises(F.LevelFormatError, match='whole room'):
        F.parse({**spec, 'seals': [{'mode': 'gone', 'match': 'goblin',
                                    'region': [0, 0, 1, 1]}]})


def test_a_seals_head_round_trips_and_is_refused_where_margins_do_not_exist():
    """`head` is the left-align law in a file: under anyrow scope a matched
    row's first glyph must sit at that exact column. It rides along any mode,
    but only the row reader has a margin — the region reader strips its lines
    before comparing, so a head beside region is refused, and so is any value
    that is not a column number."""
    geo = {'rows': 4, 'cols': 8, 'cells': ['W' * 8] * 4,
           'spawn': [1, 1], 'exit': [2, 2]}
    spec = {'schema': 1, 'name': 't', 'seed': 1, 'geometry': geo,
            'seals': [{'scope': 'anyrow', 'match': 'verse', 'head': 4,
                       'opens': [2, 2]}]}
    lvl = F.parse(spec)
    assert lvl.seals[0].head == 4 and lvl.seals[0].scope == 'anyrow'
    back = F.loads(F.dumps(lvl))
    assert back.seals[0] == lvl.seals[0]
    assert json.loads(F.dumps(lvl))['seals'][0]['head'] == 4
    # Absent head stays invisible on disk — the four-line seal stays four lines.
    plain = F.parse({**spec, 'seals': [{'scope': 'anyrow', 'match': 'verse',
                                        'opens': [2, 2]}]})
    assert json.loads(F.dumps(plain))['seals'][0] == {
        'opens': [[2, 2]], 'mode': 'exact', 'match': 'verse', 'scope': 'anyrow'}
    with pytest.raises(F.LevelFormatError, match='anyrow'):
        F.parse({**spec, 'seals': [{'match': 'verse', 'head': 4,
                                    'opens': [2, 2],
                                    'region': [1, 1, 1, 5]}]})
    for bad in (-3, 'x', True, 1.5):
        with pytest.raises(F.LevelFormatError, match='column'):
            F.parse({**spec, 'seals': [{'scope': 'anyrow', 'match': 'verse',
                                        'head': bad, 'opens': [2, 2]}]})


def test_a_seals_pin_round_trips_and_refuses_to_share_a_seal_with_a_margin():
    """`at` is the pin law in a file: the target's first glyph stands exactly
    at that column, whatever sits west of it — the plumb-line family. It is
    `head`'s sibling with the opposite verdict on the row's west end, so one
    seal may not name both: two margins is a promise nobody can keep."""
    geo = {'rows': 4, 'cols': 8, 'cells': ['W' * 8] * 4,
           'spawn': [1, 1], 'exit': [2, 2]}
    spec = {'schema': 1, 'name': 't', 'seed': 1, 'geometry': geo,
            'seals': [{'scope': 'anyrow', 'match': 'verse', 'at': 3,
                       'opens': [2, 2]}]}
    lvl = F.parse(spec)
    assert lvl.seals[0].at == 3
    back = F.loads(F.dumps(lvl))
    assert back.seals[0] == lvl.seals[0]
    assert json.loads(F.dumps(lvl))['seals'][0]['at'] == 3
    plain = F.parse({**spec, 'seals': [{'scope': 'anyrow', 'match': 'verse',
                                        'opens': [2, 2]}]})
    assert json.loads(F.dumps(plain))['seals'][0] == {
        'opens': [[2, 2]], 'mode': 'exact', 'match': 'verse', 'scope': 'anyrow'}
    with pytest.raises(F.LevelFormatError, match='not both'):
        F.parse({**spec, 'seals': [{'scope': 'anyrow', 'match': 'verse',
                                    'head': 2, 'at': 5, 'opens': [2, 2]}]})
    for bad in (-2, 'y', False, 2.5):
        with pytest.raises(F.LevelFormatError, match='column'):
            F.parse({**spec, 'seals': [{'scope': 'anyrow', 'match': 'verse',
                                        'at': bad, 'opens': [2, 2]}]})
    with pytest.raises(F.LevelFormatError, match='anyrow'):
        F.parse({**spec, 'seals': [{'match': 'verse', 'at': 3,
                                    'region': [1, 1, 1, 5],
                                    'opens': [2, 2]}]})


def test_underwater_off_the_water_rides_the_file_and_unions_with_inline_m():
    """Underwater ground was a property of WATER because the `M` code said it
    inline; the Shelving Room and the Refrain Vault sink plain floor, so the
    format learned the layer under its own name — `underwater`, a list of
    [row, col] pairs, the same move `veiled` made. Inline `M` stays water
    shorthand and the two sayings union: an author may write it either way,
    and a captured room writes floor-haze into the list while water keeps
    riding the compact code. (The key was `mist` until 2026-08-23.)"""
    geo = {'rows': 4, 'cols': 6,
           'cells': ['WWWWWW', 'W3MFW', 'WFFFFW', 'WWWWWW'],
           'spawn': [1, 1], 'exit': [2, 4]}
    spec = {'schema': 1, 'name': 't', 'seed': 1, 'geometry': geo,
            'underwater': [[2, 1], [2, 3]]}
    lvl = F.parse(spec)
    room = F.build(lvl).rooms[0]
    assert sorted(room.underwater_cells) == [(1, 1), (1, 2), (1, 3), (2, 1), (2, 3)]
    assert sorted(room.fog_cells) == sorted(room.underwater_cells), \
        'mist is always a subset of the fog'
    # Round trip: floor mist rides the list, water mist stays in the M code,
    # and the rebuilt room carries exactly what went in.
    back = F.loads(F.dumps(F.from_room(room, 't')))
    assert sorted(F.build(back).rooms[0].underwater_cells) == sorted(room.underwater_cells)
    file = json.loads(F.dumps(back))
    assert sorted(map(tuple, file['underwater'])) == [(2, 1), (2, 3)]
    assert 'M' in file['geometry']['cells'][1], 'water keeps its shorthand'
    # A room of several says it per room, like any content key.
    two = {**spec, 'then': [{'geometry': dict(geo, spawn=[1, 1], exit=[2, 4]),
                             'underwater': [[1, 5]]}]}
    parsed = F.parse(two)
    assert parsed.then[0].underwater == [(1, 5)]
    # Junk is refused at parse, not silently dropped.
    for bad in ([[1]], [[1, 2, 3]], ['x'], 'no'):
        with pytest.raises(Exception):
            F.parse({**spec, 'underwater': bad})


def test_the_legacy_mist_key_still_loads_and_dumps_as_underwater():
    """A format never orphans its own files: every level written before
    2026-08-23 says `mist`, and both names read — unioned when a file says
    both. What Vimny WRITES is the canonical new name, so generation two of
    any file speaks today's language."""
    geo = {'rows': 4, 'cols': 6,
           'cells': ['WWWWWW', 'W3MFW', 'WFFFFW', 'WWWWWW'],
           'spawn': [1, 1], 'exit': [2, 4]}
    legacy = {'schema': 1, 'name': 't', 'seed': 1, 'geometry': geo,
              'mist': [[2, 1], [2, 3]]}
    modern = {**legacy, 'mist': None}
    del modern['mist']
    modern['underwater'] = legacy['mist']
    both = {**modern, 'mist': [[3, 1]]}
    for spec, want in ((legacy, [(2, 1), (2, 3)]),
                       (modern, [(2, 1), (2, 3)]),
                       (both,   [(2, 1), (2, 3), (3, 1)])):
        lvl = F.parse(spec)
        assert sorted(map(tuple, lvl.underwater)) == want
    # What we write is always the new name.
    file = json.loads(F.dumps(F.parse(legacy)))
    assert 'underwater' in file and 'mist' not in file
