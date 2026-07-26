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

"""The forge: authoring a level in-game and getting a shippable file out."""
from __future__ import annotations

import pytest
from blessed import Terminal
from blessed.keyboard import Keystroke

import engine.tape as T
import sharing.draft as DRAFT
import sharing.format as F
from engine.editor import _ed_cut, _ed_subst, in_fill
from engine.world import CellType


# ── A tiny level: walk four cells east onto the exit ──────────────────────────

def _tiny(**kw) -> F.Level:
    return F.Level(
        name=kw.pop('name', 'The Test Stair'), seed=7,
        rows=5, cols=10,
        cells=['10W', 'W8FW', 'W8FW', 'W8FW', '10W'],
        spawn=(1, 1), exit=(1, 5),
        solution=kw.pop('solution', 'llll'), **kw)


def _record_take(lvl: F.Level, tape: str) -> tuple:
    """Play `tape` through the real loop with the recorder attached.

    Deliberately built here rather than by adding a `record` argument to
    `replay_tape`: the replayer is a validation tool, and teaching it to record
    would put the forge's scaffolding in the path that judges every shipped
    level. Returns `(recorded_tape, result)`.
    """
    import main
    from sharing.replay import _headless

    term  = Terminal(force_styling=False)
    keys  = T.to_keys(tape, term) + [Keystroke(ch) for ch in ':wq\r']
    state = {'n': 0}

    def _inkey(*a, **k):
        if state['n'] >= len(keys):
            raise AssertionError('the take ran out of keys before it returned')
        state['n'] += 1
        return keys[state['n'] - 1]

    term.inkey = _inkey
    import render.colors as colors
    colors.init(term)

    rec = {'tape': [], 'error': ''}
    with _headless(main):
        result = main.run_dungeon(term, 'community', {}, player_name='Normand',
                                  _dungeon=F.build(lvl), _known=lvl.known,
                                  _record=rec)
    return ''.join(rec['tape']), result


def _forge_session(draft, script: str, player_name: str = 'admin'):
    """Drive a real forge session: open `draft` in the editor and type `script`."""
    import main
    from sharing.replay import _headless

    term = Terminal(force_styling=False)
    keys = T.to_keys(script, term, separators=False)
    state = {'n': 0}

    def _inkey(*a, **k):
        if state['n'] >= len(keys):
            raise AssertionError('the session ran out of keys before it returned')
        state['n'] += 1
        return keys[state['n'] - 1]

    term.inkey = _inkey
    import render.colors as colors
    colors.init(term)
    with _headless(main):
        return main.run_dungeon(term, 'community', {}, player_name=player_name,
                                _dungeon=draft.build(), _start_edit=True,
                                _known=draft.level.known, _draft=draft)


# ── Editing in the forge ──────────────────────────────────────────────────────

def test_the_editor_can_move_the_exit():
    """Neither spawn nor exit could be moved at all before the forge — the
    editor serialised both and mutated neither."""
    d = DRAFT.new('Probe', rows=8, cols=30)
    _forge_session(d, 'lll:exit\r:w\r:q!\r')
    assert d.level.exit == (1, 4)


def test_the_editor_can_move_the_spawn():
    d = DRAFT.new('Probe', rows=8, cols=30)
    _forge_session(d, 'jj:spawn\r:w\r:q!\r')
    assert d.level.spawn == (3, 1)


def test_a_visual_selection_becomes_a_fill():
    d = DRAFT.new('Probe', rows=8, cols=30)
    _forge_session(d, 'jjv' + 'l' * 5 + T.ESC + ':fill plain 3-4\r:w\r:q!\r')
    assert [f.region for f in d.level.fills] == [(3, 1, 3, 6)]
    assert d.level.fills[0].pool == 'plain'
    assert d.level.fills[0].length == (3, 4)


def test_adding_a_fill_does_not_wipe_the_fill_list():
    """The rebuild takes its fills from the ROOM, which is one build behind the
    level. Syncing after the append (rather than before) silently threw the new
    directive away and left the author looking at words with nothing behind
    them."""
    d = DRAFT.new('Probe', rows=8, cols=30)
    _forge_session(d, 'jjv' + 'l' * 5 + T.ESC + ':fill plain\r'
                      + 'jjv' + 'l' * 5 + T.ESC + ':fill proverbs\r:w\r:q!\r')
    assert len(d.level.fills) == 2
    assert [f.pool for f in d.level.fills] == ['plain', 'proverbs']


def test_dropping_a_fill_hands_its_words_to_the_author():
    d = DRAFT.new('Probe', rows=8, cols=30)
    _forge_session(d, 'jjv' + 'l' * 20 + T.ESC + ':fill plain 3-3\r'
                      + ':fill!\r:w\r:q!\r')
    assert d.level.fills == []
    assert d.level.char_runs, 'the words vanished with the directive'
    assert all(r['row'] == 3 for r in d.level.char_runs)


def test_a_fill_survives_a_save_and_reopen(tmp_path, monkeypatch):
    monkeypatch.setattr(DRAFT, 'DRAFTS_DIR', tmp_path)
    d = DRAFT.new('Probe', rows=8, cols=30)
    _forge_session(d, 'jjv' + 'l' * 5 + T.ESC + ':fill plain\r:wq\r')
    again = DRAFT.load(DRAFT._path('Probe'))
    assert [f.region for f in again.level.fills] == [(3, 1, 3, 6)]


def test_the_metadata_commands_reach_the_level():
    d = DRAFT.new('Probe', rows=8, cols=30)
    _forge_session(d, ':author Chas\r:teaches w b e\r:requires h j k l\r'
                      ':intro Salt on the stair.\r:w\r:q!\r')
    assert d.level.author == 'Chas'
    assert d.level.teaches == ['w', 'b', 'e']
    assert d.level.requires == ['h', 'j', 'k', 'l']
    assert d.level.intro == 'Salt on the stair.'


# ── Leaving VISUAL remembers the selection (what `:fill` reads) ───────────────

def test_escaping_a_visual_selection_still_remembers_it():
    """Vim's `gv` reselects the last visual area whether an operator was applied
    or not; the area was previously saved only on operator-apply, so `:fill`
    after an Esc read the selection BEFORE the one just made."""
    d = DRAFT.new('Probe', rows=8, cols=30)
    _forge_session(d, 'jjv' + 'l' * 5 + T.ESC + ':fill plain\r:w\r:q!\r')
    assert d.level.fills, 'the selection was forgotten on Esc'


# ── The tape a take writes ────────────────────────────────────────────────────

def test_recording_a_played_route_reproduces_the_tape():
    """The whole promise of :record — what you played is what gets written."""
    played, result = _record_take(_tiny(), 'llll')
    assert result['won']
    assert played == 'llll'


def test_the_take_stops_at_the_win_and_omits_the_closing_wq():
    """`replay_tape` appends its own `:wq`; recording the author's way out too
    would put a second one on the tape and replay it as a stray command."""
    played, _ = _record_take(_tiny(), 'llll')
    assert ':wq' not in played and ':' not in played


def test_a_recorded_tape_replays_and_sets_par():
    lvl = _tiny(solution='')
    played, _ = _record_take(lvl, 'llll')
    lvl.solution = played
    rep = DRAFT.Draft(path=None, level=lvl).report()
    assert rep.ok, rep.errors
    assert rep.par == 4 and rep.budget == 6          # ceil(4 * 1.4)


def test_a_take_that_never_reaches_the_exit_is_not_a_win():
    _, result = _record_take(_tiny(), 'll')
    assert not result['won']


def test_a_recording_take_never_writes_to_the_players_save(monkeypatch):
    """A take runs under the author's own name — an unguarded progress write
    would overwrite their real save with the forge's throwaway dict."""
    import save.save_manager as SM
    calls = []
    monkeypatch.setattr(SM, 'save_progress', lambda d, who: calls.append(who))
    _record_take(_tiny(), 'llll')
    assert calls == []


# ── Tape notation round-trip ──────────────────────────────────────────────────

@pytest.mark.parametrize('token', [T.ESC, T.ENTER, T.SPACE, T.CTRL_V, 'x', 'w'])
def test_every_written_key_round_trips_through_the_notation(token):
    term = Terminal(force_styling=False)
    keys = T.to_keys(token, term)
    assert [T.from_keystroke(k) for k in keys] == [token]


def test_a_key_the_notation_cannot_write_is_refused_not_skipped():
    """Silently dropping an arrow key would hand back a tape that replays as
    something other than what was played."""
    term = Terminal(force_styling=False)
    assert T.from_keystroke(Keystroke('\x1b[A', code=term.KEY_UP, name='KEY_UP')) is None


# ── Drafts ────────────────────────────────────────────────────────────────────

def test_a_new_draft_builds_a_room_you_can_stand_in():
    room = DRAFT.new('The Salt Stair').build().room
    assert room.cells[room.spawn_pos[0]][room.spawn_pos[1]] == CellType.FLOOR
    assert room.exit_pos and any(e.kind == 'exit' for e in room.entities)


def test_a_draft_seed_is_minted_once_and_never_drifts():
    """Every fill resolves from the seed; a seed that moved would rearrange the
    words under a tape recorded against the old arrangement."""
    d = DRAFT.new('The Salt Stair')
    seed = d.level.seed
    for _ in range(3):
        DRAFT.sync(d, d.build().room)
    assert d.level.seed == seed


def test_syncing_the_room_back_keeps_what_a_room_cannot_hold():
    d = DRAFT.new('The Salt Stair')
    d.level.fills = [F.Fill(region=(1, 2, 3, 40), pool='plain')]
    d.level.teaches, d.level.requires = ['e'], ['w', 'b']
    d.level.intro, d.level.vocabulary = 'Salt on the stair.', ['chat']
    d.level.alternate = 'rune_halls'
    DRAFT.sync(d, d.build().room)
    assert len(d.level.fills) == 1
    assert d.level.teaches == ['e'] and d.level.requires == ['w', 'b']
    assert d.level.intro == 'Salt on the stair.'
    assert d.level.vocabulary == ['chat'] and d.level.alternate == 'rune_halls'


def test_a_fill_is_written_as_a_directive_not_as_the_words_it_grew():
    """Writing both would ship the level with the words AND the directive that
    lays them, so the next build would stack a second copy on top."""
    d = DRAFT.new('The Salt Stair')
    d.level.fills = [F.Fill(region=(1, 2, 3, 40), pool='plain')]
    room = d.build().room
    assert room.char_runs, 'the fill grew nothing to begin with'
    DRAFT.sync(d, room)
    assert d.level.char_runs == []
    assert len(d.level.fills) == 1


def test_a_hand_placed_word_outside_a_fill_survives_the_round_trip():
    d = DRAFT.new('The Salt Stair')
    d.level.fills     = [F.Fill(region=(1, 2, 1, 20), pool='plain')]
    d.level.char_runs = [{'row': 5, 'col': 3, 'symbols': list('salt'),
                          'kind': 'ancient'}]
    DRAFT.sync(d, d.build().room)
    assert [r['row'] for r in d.level.char_runs] == [5]


def test_a_draft_round_trips_through_disk_unchanged(tmp_path, monkeypatch):
    monkeypatch.setattr(DRAFT, 'DRAFTS_DIR', tmp_path)
    d = DRAFT.new('The Salt Stair', author='chas')
    d.level.fills = [F.Fill(region=(1, 2, 3, 40), pool='proverbs')]
    path = DRAFT.save(d)
    again = DRAFT.load(path)
    assert again.ok
    assert F.dumps(again.level) == F.dumps(d.level)


def test_an_unreadable_draft_comes_back_carrying_its_error(tmp_path):
    bad = tmp_path / 'broken.json'
    bad.write_text('{not json', encoding='utf-8')
    d = DRAFT.load(bad)
    assert not d.ok and d.error
    assert d.name == 'broken'          # still listable, so it can still be fixed


# ── The fill lock ─────────────────────────────────────────────────────────────

def _filled_room():
    lvl = _tiny()
    lvl.fills = [F.Fill(region=(2, 1, 2, 8), pool='plain', length=(3, 3))]
    return F.build(lvl).room


def test_a_fill_region_refuses_edits():
    """Text a fill grew is regenerated on every build, so an edit to it would be
    dropped at save time without a word — refusing is the honest answer."""
    room = _filled_room()
    assert in_fill(room, 2, 2) is not None
    before = len(room.char_runs)
    assert _ed_cut(room, 2, 2) is None
    assert _ed_subst(room, 2, 2) == []
    assert len(room.char_runs) == before


def test_a_range_delete_sweeping_a_fill_leaves_it_standing():
    from engine.editor import _ed_delete_range
    room = _filled_room()
    grown = len([ru for ru in room.char_runs if ru.row == 2])
    _ed_delete_range(room, 1, 0, 3, 9)
    assert len([ru for ru in room.char_runs if ru.row == 2]) == grown


def test_a_room_that_was_never_built_from_a_level_is_never_locked():
    """`in_fill` is duck-typed on `room.fills`, so every shipped level — whose
    rooms a generator built and which has no such attribute — is untouched."""
    from engine.world import Room, RoomType
    room = Room(room_type=RoomType.ENTRY, rows=5, cols=10)
    assert not hasattr(room, 'fills')
    assert in_fill(room, 2, 2) is None


# ── Publishing ────────────────────────────────────────────────────────────────

def test_publishing_refuses_a_draft_that_does_not_validate(tmp_path, monkeypatch):
    monkeypatch.setattr(DRAFT, 'LEVELS_DIR', tmp_path)
    d = DRAFT.Draft(path=tmp_path / 'x.json', level=_tiny(solution=''))
    dest, rep = DRAFT.publish(d)
    assert dest is None and not rep.ok
    assert list(tmp_path.glob('*.json')) == []


def test_publishing_writes_the_drafts_own_bytes(tmp_path, monkeypatch):
    """The level that ships is the one the author was playing, not a
    re-rendering of it that might differ."""
    monkeypatch.setattr(DRAFT, 'LEVELS_DIR', tmp_path)
    d = DRAFT.Draft(path=tmp_path / 'x.json', level=_tiny())
    dest, rep = DRAFT.publish(d)
    assert rep.ok and dest.exists()
    assert dest.read_text(encoding='utf-8') == F.dumps(d.level)


def test_a_published_draft_carries_no_par_or_budget(tmp_path, monkeypatch):
    """Par is derived by replaying the tape. A file that could declare one would
    let an author hand themselves a budget."""
    import json
    monkeypatch.setattr(DRAFT, 'LEVELS_DIR', tmp_path)
    dest, _ = DRAFT.publish(DRAFT.Draft(path=tmp_path / 'x.json', level=_tiny()))
    data = json.loads(dest.read_text(encoding='utf-8'))
    assert 'par' not in data and 'budget' not in data
