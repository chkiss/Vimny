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
from engine.editor import _ed_cut, _ed_paint, in_fill
from engine.world import CellType


# ── A tiny level: walk four cells east onto the exit ──────────────────────────

def _tiny(**kw) -> F.Level:
    return F.Level(
        name=kw.pop('name', 'The Test Stair'), seed=7,
        rows=5, cols=10,
        cells=['10W', 'W8FW', 'W8FW', 'W8FW', '10W'],
        spawn=(1, 1), exit=(1, 5),
        solution=kw.pop('solution', 'llll'), **kw)


def _sized(**kw) -> F.Level:
    """A level of an arbitrary shape — `_tiny` with nothing assumed about it."""
    kw.setdefault('name', 'The Wide Stair')
    kw.setdefault('seed', 7)
    kw.setdefault('spawn', (1, 1))
    kw.setdefault('exit', (1, 5))
    kw.setdefault('solution', 'llll')
    return F.Level(**kw)


def _record_take(lvl: F.Level, tape: str, player_name: str = 'Normand') -> tuple:
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
        result = main.run_dungeon(term, 'community', {}, player_name=player_name,
                                  _dungeon=F.build(lvl), _known=lvl.known,
                                  _record=rec)
    return ''.join(rec['tape']), result


def _forge_session(draft, script: str, player_name: str = 'admin', dungeon=None,
                   tally: dict | None = None):
    """Drive a real forge session: open `draft` in the editor and type `script`.

    Pass `dungeon` to keep a handle on the object the chrome renders from — the
    only way to observe, from out here, what the status bar was showing.

    Pass `tally` to learn how much of the script was actually read. A command
    that opens a RUN of its own (`:play`, `:record`) is invisible from here
    otherwise: the session ends either way, and the keys the inner run should
    have eaten are simply left on the floor. `tally['read'] == tally['total']`
    is the assertion that the second loop really took them."""
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
        result = main.run_dungeon(term, 'community', {}, player_name=player_name,
                                  _dungeon=dungeon or draft.build(), _start_edit=True,
                                  _known=draft.level.known, _draft=draft)
    if tally is not None:
        tally.update(read=state['n'], total=len(keys))
    return result


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


def test_colon_straight_from_visual_fills_the_selection():
    """`:` from VISUAL is how vim gets to the command line — it leaves visual
    mode and stamps the selection into `'<`/`'>` on the way. Requiring Esc first
    made the author hold the shape in their head across a keystroke that looks
    like it throws the shape away."""
    d = DRAFT.new('Probe', rows=8, cols=30)
    _forge_session(d, 'jjv' + 'l' * 5 + ':fill plain 3-4\r:w\r:q!\r')
    assert [f.region for f in d.level.fills] == [(3, 1, 3, 6)]


def test_a_ranged_entity_fills_the_whole_selection():
    """`:'<,'>entity goblin` is a RANK of goblins, not one at the cursor. The
    range is prefilled by `:` and it is real — the same region `:fill` takes."""
    d = DRAFT.new('Probe', rows=8, cols=30)
    _forge_session(d, 'jjv' + 'l' * 5 + ':entity goblin tag=echo\r:w\r:q!\r')
    gobs = sorted(tuple(e['at']) for e in d.level.entities if e['kind'] == 'goblin')
    assert gobs == [(3, 1), (3, 2), (3, 3), (3, 4), (3, 5), (3, 6)]
    assert {e['tag'] for e in d.level.entities if e['kind'] == 'goblin'} == {'echo'}


def test_without_a_range_entity_is_still_one_cell():
    """The cursor form is untouched: no range, no rank."""
    d = DRAFT.new('Probe', rows=8, cols=30)
    _forge_session(d, 'jjllll:entity goblin\r:w\r:q!\r')
    assert [tuple(e['at']) for e in d.level.entities if e['kind'] == 'goblin'] \
        == [(3, 5)]


def test_a_ranged_bang_sweeps_the_rank_away_again():
    """The eraser the ranged placement needs — put a rank down, look at it,
    `gv` and sweep it. Without `!` taking the range too, undoing a rank by hand
    is one `:entity!` per cell."""
    d = DRAFT.new('Probe', rows=8, cols=30)
    _forge_session(d, 'jjv' + 'l' * 5 + ':entity goblin\r'
                      + 'gv:entity!\r:w\r:q!\r')
    assert not [e for e in d.level.entities if e['kind'] == 'goblin']


def test_the_range_skips_masonry_rather_than_placing_into_it():
    """A selection swept across a room is drawn around what the author can see.
    The wall cells inside it were never the point — placing a goblin inside the
    stonework would be a creature that cannot be reached or fought."""
    d = DRAFT.new('Probe', rows=8, cols=30)
    # column 0 and the last column are the room's border wall
    _forge_session(d, 'jjV:entity goblin\r:w\r:q!\r')
    cols = sorted(e['at'][1] for e in d.level.entities if e['kind'] == 'goblin')
    assert cols and 0 not in cols and 29 not in cols


def test_a_draft_command_still_refuses_the_range():
    """`:w` is addressed to the DRAFT, not to any part of the map — there is no
    region it could mean, so it is caught rather than run with the range
    ignored. Esc, and the marks outlive it."""
    d = DRAFT.new('Probe', rows=8, cols=30)
    _forge_session(d, 'jjv' + 'l' * 5 + ':name Ranged\r'
                      + ':' + T.ESC + ':fill plain\r:w\r:q!\r')
    assert d.level.name == 'Probe', 'the ranged :name must not have landed'
    assert [f.region for f in d.level.fills] == [(3, 1, 3, 6)]


def test_colon_from_visual_leaves_visual_like_vim():
    """It is not a mode the command line runs UNDER: vim drops to normal, and so
    a `gv` afterwards is what brings the region back."""
    d = DRAFT.new('Probe', rows=8, cols=30)
    # V (linewise) then `:` — the fill must read the WHOLE row, which is only
    # true if the linewise mode was the one recorded at the `:`.
    _forge_session(d, 'jjV:fill plain\r:w\r:q!\r')
    assert [f.region for f in d.level.fills] == [(3, 0, 3, 29)]


def test_adding_a_fill_does_not_wipe_the_fill_list():
    """The rebuild takes its fills from the ROOM, which is one build behind the
    level. Syncing after the append (rather than before) silently threw the new
    directive away and left the author looking at words with nothing behind
    them."""
    d = DRAFT.new('Probe', rows=8, cols=30)
    # the second is a LINE pool, so its region has to be wide enough for a saying
    _forge_session(d, 'jjv' + 'l' * 5 + T.ESC + ':fill plain\r'
                      + 'jj0v' + 'l' * 20 + T.ESC + ':fill proverbs\r:w\r:q!\r')
    assert len(d.level.fills) == 2
    assert [f.pool for f in d.level.fills] == ['plain', 'proverbs']


def test_dropping_a_fill_hands_its_words_to_the_author():
    d = DRAFT.new('Probe', rows=8, cols=30)
    _forge_session(d, 'jjv' + 'l' * 20 + T.ESC + ':fill plain 3-3\r'
                      + ':fill!\r:w\r:q!\r')
    assert d.level.fills == []
    assert d.level.char_runs, 'the words vanished with the directive'
    assert all(r['row'] == 3 for r in d.level.char_runs)


def test_a_fill_can_be_retuned_in_place():
    """Changing a directive used to mean selecting the region again and
    `:fill`ing it, which APPENDS — two overlapping fills growing words over each
    other. `:fill length=4` retunes the one under the cursor, the way
    `:entity field=value` retunes an entity."""
    d = DRAFT.new('Probe', rows=8, cols=30)
    _forge_session(d, 'jjv' + 'l' * 20 + T.ESC + ':fill plain 3-6\r'
                      + ':fill length=4\r:w\r:q!\r')
    assert len(d.level.fills) == 1, 'a retune must not add a second directive'
    assert d.level.fills[0].length == (4, 4)
    assert d.level.fills[0].region == (3, 1, 3, 21), 'the region is untouched'


def test_a_retune_keeps_the_fill_where_it_was_in_the_list():
    """`<fill0.3>` in a solution points at a fill BY INDEX, so a retune that
    reordered the list would silently repoint every reference in the tape."""
    d = DRAFT.new('Probe', rows=8, cols=30)
    _forge_session(d, 'jjv' + 'l' * 20 + T.ESC + ':fill plain 3-6\r'
                      + 'jj0v' + 'l' * 20 + T.ESC + ':fill mixed 3-6\r'
                      + 'kk0:fill length=5\r:w\r:q!\r')
    assert [f.pool for f in d.level.fills] == ['plain', 'mixed']
    assert [f.length for f in d.level.fills] == [(5, 5), (3, 6)]


def test_retuning_where_there_is_no_fill_says_so():
    d = DRAFT.new('Probe', rows=8, cols=30)
    _forge_session(d, ':fill length=4\r:w\r:q!\r')
    assert d.level.fills == []


def test_a_bare_fill_also_asks_how_long_the_words_are():
    """The length is not a detail: one length is what lets a solution NAME one
    of these words, and an author who is never asked meets that as a refusal at
    `:check` instead."""
    d = DRAFT.new('Probe', rows=8, cols=30)
    #                    pool: plain (first row)   length: 4-4 (third row)
    _forge_session(d, 'jv' + 'l' * 20 + ':fill\r' + '\r' + 'jj\r' + ':w\r:q!\r')
    assert [f.pool for f in d.level.fills] == ['plain']
    assert d.level.fills[0].length == (4, 4)


def test_backing_out_of_the_length_step_grows_nothing():
    d = DRAFT.new('Probe', rows=8, cols=30)
    _forge_session(d, 'jv' + 'l' * 20 + ':fill\r' + '\r' + T.ESC + ':w\r:q!\r')
    assert d.level.fills == []


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


# ── The rehearsal (`:play`) ───────────────────────────────────────────────────
#
# `:record` was once the only way to walk your own level, and a take always
# overwrites the tape — so rehearsing cost the author the solution they had.
# `:play` is the same walk with the recorder off.

def _playable_draft(name='Playtest'):
    """A draft that is already a finished level: four cells east onto the exit."""
    d = DRAFT.new(name, rows=5, cols=10)
    lvl = _tiny()
    for f in ('rows', 'cols', 'cells', 'spawn', 'exit', 'solution'):
        setattr(d.level, f, getattr(lvl, f))
    DRAFT.save(d)
    return d


def _rehearse(draft, inside: str, cmd: str = ':play') -> dict:
    """Type `:play`, play `inside` in the run it opens, then leave the forge.

    The tally is the proof the run happened at all: if `:play` were not a command
    the editor would eat `inside` itself, quit on its `:q!`, and leave the
    session's own `:q!` unread."""
    tally: dict = {}
    _forge_session(draft, f'{cmd}\r{inside}:q!\r', tally=tally)
    assert tally['read'] == tally['total'], (
        'the rehearsal never opened — the editor read the route itself')
    return tally


def test_playing_a_level_does_not_touch_the_tape_even_when_it_wins():
    """The sharp one. A winning rehearsal that quietly became the tape would
    replace a deliberate route with whatever the author last wandered — so the
    rehearsal here deliberately wins by a WORSE route than the one on file."""
    d = _playable_draft()
    _rehearse(d, 'jllllk:wq\r')
    assert d.level.solution == 'llll', 'the rehearsal was written down'


def test_a_rehearsal_is_a_run_of_its_own_and_not_an_edit_to_the_draft():
    """The keys go to a FRESH build, not to the room on the bench: `x` in a
    rehearsal breaks nothing the author will find when the run ends."""
    d = _playable_draft()
    before = list(d.level.cells)
    _rehearse(d, 'xxxx:q!\r')
    assert d.level.cells == before


def test_a_rehearsal_that_loses_is_not_an_error():
    """Losing is the information you came for, so it is reported, not refused —
    and it still leaves the tape where it was."""
    d = _playable_draft()
    _rehearse(d, 'll:q!\r')
    assert d.level.solution == 'llll'


def test_a_rehearsal_never_writes_to_the_players_save(monkeypatch):
    """Same guard a take has: a rehearsal runs under the AUTHOR's own name, so
    an unguarded write would overwrite their real save."""
    import save.save_manager as SM
    calls = []
    monkeypatch.setattr(SM, 'save_progress', lambda data, who: calls.append(who))
    _rehearse(_playable_draft(), 'llll:wq\r')
    assert calls == []


def test_reloading_inside_a_run_reloads_the_level_being_played():
    """`:e` means START THIS AGAIN. The slug the forge was opened from is not
    this level — reloading it dropped the author into the First Cave, with their
    draft nowhere on screen (reported 2026-07-27)."""
    import main
    d = _playable_draft()
    curriculum, rebuilt = [], []
    real_slug, real_draft = main._build_dungeon, DRAFT.Draft.build
    main._build_dungeon = lambda slug, *a, **kw: curriculum.append(slug)
    DRAFT.Draft.build = lambda self, **kw: rebuilt.append(kw) or real_draft(self, **kw)
    try:
        _rehearse(d, ':e\rllll:wq\r')
    finally:
        main._build_dungeon, DRAFT.Draft.build = real_slug, real_draft
    assert curriculum == [], f'`:e` went looking for a shipped level: {curriculum}'
    assert len(rebuilt) >= 2, 'the reload never rebuilt the draft'


def test_a_rehearsal_runs_under_the_budget_the_tape_bought():
    """`:play` asks the question the author actually has — is it doable in the
    budget — so it builds with par, and `:play!` is the roam that does not."""
    d = _playable_draft()                    # tape 'llll' → par 4, budget 6
    dungeons = []
    real = DRAFT.Draft.build
    DRAFT.Draft.build = lambda self, **kw: dungeons.append(
        kw.get('par')) or real(self, **kw)
    try:
        dungeons.clear()
        _rehearse(d, 'llll:wq\r')
        assert 4 in dungeons, dungeons      # among the validator's own build and
        dungeons.clear()                    # the bench being put back afterwards
        _rehearse(d, 'llll:wq\r', cmd=':play!')
        assert 4 not in dungeons, dungeons
    finally:
        DRAFT.Draft.build = real


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
    assert _ed_paint(room, 2, 2, 'wall') is False
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


# ── Regressions from the first playtest ───────────────────────────────────────

def test_the_companion_horse_is_never_written_into_a_level():
    """The wizard's horse is placed into whatever room the player walks into, so
    an author who has finished the game finds him standing in their draft — and
    `from_room` used to write him into the file. He is not decoration there: a
    shipped horse re-fires the first-meeting naming PROMPT, which eats the keys
    after it, so the trailing `:wq` of a recorded tape is swallowed and a level
    that plays perfectly reports itself unsolvable."""
    from engine.world import Entity
    d = DRAFT.new('Stable', rows=8, cols=30)
    room = d.build().room
    room.entities.append(Entity(kind='horse', row=2, col=2, tag='Shadowfax'))
    DRAFT.sync(d, room)
    assert [e['kind'] for e in d.level.entities] == ['exit']


def test_a_level_carrying_a_horse_swallows_its_own_tape():
    """Why the rule above exists, stated as the failure it caused. Pin it so the
    horse cannot come back through some other door."""
    from sharing.replay import replay_tape
    lvl = _tiny()
    lvl.entities = [{'at': [1, 2], 'kind': 'horse', 'tag': ''}]
    res = replay_tape(F.build(lvl), 'community', lvl.solution,
                      known=lvl.known)
    assert not res.won, 'the naming prompt no longer eats the tape'
    # …and the identical level without him is solvable, so the horse is the
    # whole of the difference.
    ok = replay_tape(F.build(_tiny()), 'community', 'llll', known=_tiny().known)
    assert ok.won


def test_a_take_is_played_without_the_admin_override():
    """`admin` (from the player name or the Warden's hat) makes `action_allowed`
    say yes to everything. Left in place during a take it records a key the
    level never declared, which then fails for the first stranger who downloads
    it — destroying the one guarantee recording-by-playing offers."""
    # The forge's author IS the admin, so the take must be run as one or the
    # test proves nothing about the override it is meant to strip.
    tape, res = _record_take(_tiny(requires=['l']), 'llll', player_name='admin')
    assert res['won'] and tape == 'llll'

    # `$` is undeclared, and on THIS level it lands squarely on the exit — so a
    # take that wins is a take that was allowed to use it. As admin it used to
    # sail through and go onto the tape.
    def _dollar(requires):
        lv = _tiny(requires=requires, solution='$')
        lv.exit, lv.entities = (1, 8), [{'at': [1, 8], 'kind': 'exit'}]
        return lv

    assert _record_take(_dollar(['$']), '$', player_name='admin')[1]['won'], \
        'the $ route must win when the level declares $'
    tape, res = _record_take(_dollar(['l']), '$', player_name='admin')
    assert not res['won'], '$ was undeclared and should have been refused'


def test_a_linewise_selection_fills_the_whole_row():
    """`V` records only the columns the cursor sat between, so reading `'<,'>`
    literally turned a whole-line selection into `cols 1-1`."""
    d = DRAFT.new('Probe', rows=8, cols=30)
    _forge_session(d, 'jjV' + T.ESC + ':fill plain 3-4\r:w\r:q!\r')
    assert [f.region for f in d.level.fills] == [(3, 0, 3, 29)]


def test_a_fill_that_cannot_grow_is_refused_not_raised():
    """`:fill custom` with no `:vocab` behind it is legal to write and impossible
    to grow. It used to raise straight out of the command handler, taking the
    game down with the author's unsaved room inside it."""
    d = DRAFT.new('Probe', rows=8, cols=30)
    _forge_session(d, 'jjv' + 'l' * 5 + T.ESC + ':fill custom\r:w\r:q!\r')
    assert d.level.fills == [], 'the refused fill was kept anyway'


def test_a_fill_that_can_grow_after_vocab_is_accepted():
    d = DRAFT.new('Probe', rows=8, cols=30)
    _forge_session(d, ':vocab chat chien\r' + 'jjv' + 'l' * 5 + T.ESC
                      + ':fill custom\r:w\r:q!\r')
    assert [f.pool for f in d.level.fills] == ['custom']


def test_metadata_can_be_read_back():
    """`:field?` asks, the way `:set opt?` does. An authoring UI needs the read
    half more than most — you cannot correct what you cannot see."""
    d = DRAFT.new('Probe', rows=8, cols=30)
    res = _forge_session(d, ':author Chas\r:author?\r:q!\r')
    assert d.level.author == 'Chas'


def test_a_bare_metadata_command_asks_instead_of_clearing():
    """It used to CLEAR, so a mistyped query silently threw away the thing it
    was asking about. Destroying now takes the explicit `!`."""
    d = DRAFT.new('Probe', rows=8, cols=30)
    _forge_session(d, ':author Chas\r:author\r:q!\r')
    assert d.level.author == 'Chas'
    _forge_session(d, ':author!\r:q!\r')
    assert d.level.author == ''


def test_renaming_a_draft_renames_the_dungeon_on_screen():
    """The chrome names the level; a rename that did not reach it left the
    author looking at the old title and doubting the command took."""
    d   = DRAFT.new('Before', rows=8, cols=30)
    dng = d.build()
    assert dng.name == 'Before'
    _forge_session(d, ':name After\r:w\r:q!\r', dungeon=dng)
    assert dng.name == 'After', 'the chrome still names the level "Before"'
    assert d.level.name == 'After'
    assert DRAFT._path('After').exists()
    DRAFT._path('After').unlink()


def test_e_rereads_the_draft_rather_than_leaving_for_the_first_cave():
    """A draft's slug is the placeholder 'community', so the admin `:e` branch
    rebuilt THAT — landing the author in The First Cave with their draft never
    opened."""
    d = DRAFT.new('Probe', rows=8, cols=30)
    # The trailing :w is what makes this discriminating — without it the
    # unsaved spawn move was never synced to the level either way, and the
    # assertion held whether :e! reloaded anything or not.
    _forge_session(d, 'lll:exit\r:w\r' + 'jj:spawn\r' + ':e!\r:w\r:q!\r')
    assert d.level.exit == (1, 4), 'the saved edit did not survive the re-read'
    assert d.level.spawn == (1, 1), 'the unsaved edit survived a :e! reload'


def test_e_refuses_to_discard_unsaved_work():
    d = DRAFT.new('Probe', rows=8, cols=30)
    _forge_session(d, ':w\r' + 'lll:exit\r' + ':e\r:q!\r')
    assert d.level.exit == (1, 4), ':e threw away work without being forced'


def test_a_custom_pool_uses_the_authors_own_word_lengths():
    """`:vocab chat chien oiseau` then `:fill custom` must lay down THOSE words.

    The stock 3-6 length range is right for the shipped pools and wrong for a
    hand-written list: nothing in this vocabulary is 3 long, so the fill used to
    raise "vocabulary pool is empty" at an author who had just handed it three
    perfectly good words."""
    d = DRAFT.new('Probe', rows=8, cols=40)
    _forge_session(d, ':vocab chat chien oiseau\r'
                      + 'jjv' + 'l' * 30 + T.ESC + ':fill custom\r:w\r:q!\r')
    assert [f.length for f in d.level.fills] == [(4, 6)]
    words = {''.join(r.symbols) for r in d.build().room.char_runs}
    assert words and words <= {'chat', 'chien', 'oiseau'}, words


def test_a_pool_missing_a_length_reaches_for_the_nearest_one():
    """The old fallback was the 1-character table, which reads sensible and is
    not: `plain` has no 1-character words at all, so `:fill plain 1-2` raised
    "pool is empty" about the game's own stock vocabulary."""
    from sharing import vocab
    import random
    rng = random.Random(1)
    assert len(vocab.words('plain', 1, rng)) == 3     # nearest length plain has
    assert len(vocab.words('custom', 9, rng, vocab.by_length(['chat']))) == 4


def test_an_empty_vocabulary_still_says_so_plainly():
    """The nearest-length fallback must not paper over the one case that really
    is the author's mistake: naming `custom` with no words behind it."""
    import random
    from sharing import vocab
    with pytest.raises(ValueError, match='declares no `vocabulary` block'):
        vocab.words('custom', 4, random.Random(1), {})


# ── Entities as data: `drops`, `group`, and the `:set`-style :entity ───────────

def _room_with(*ents, rows=5, cols=12):
    """A tiny built room carrying the given entity specs."""
    lvl = _tiny()
    lvl.rows, lvl.cols = rows, cols
    lvl.cells = [f'{cols}W'] + [f'W{cols - 2}FW'] * (rows - 2) + [f'{cols}W']
    lvl.exit = (1, cols - 2)
    lvl.entities = list(ents)
    return F.build(lvl).room


def _player_at(row, col):
    from engine.player import Player
    return Player(row=row, col=col)


def test_a_single_creature_drops_what_it_carries():
    """`drops` is a field on the creature, not a rule about goblins — the game
    had this twice before (a `level == 'goblin_gauntlet'` branch and the vault's
    tick) and could express it in a level file zero times."""
    import main
    room = _room_with({'kind': 'goblin', 'at': [1, 3], 'drops': 'floor_key:gold'})
    gob  = room.entity_at(1, 3)
    assert not main._drop_tick(room, _player_at(1, 1))      # alive: nothing yet
    room.kill_entity(gob)
    assert main._drop_tick(room, _player_at(1, 1))
    key = room.entity_at(1, 3)
    assert (key.kind, key.tag) == ('floor_key', 'gold')


def test_the_drop_waits_for_the_last_of_a_group():
    import main
    room = _room_with({'kind': 'goblin', 'at': [1, 3], 'group': 'patrol',
                       'drops': 'floor_key'},
                      {'kind': 'goblin', 'at': [1, 5], 'group': 'patrol',
                       'drops': 'floor_key'})
    room.kill_entity(room.entity_at(1, 5))
    main._drop_tick(room, _player_at(1, 1))
    assert not [e for e in room.entities if e.kind == 'floor_key' and e.alive]
    room.kill_entity(room.entity_at(1, 3))
    main._drop_tick(room, _player_at(1, 1))
    keys = [e for e in room.entities if e.kind == 'floor_key' and e.alive]
    # ONE key, at the group's lowest (row, col) — derived from the file, so it
    # lands in the same cell for every player and after every undo, rather than
    # wherever the last one happened to be standing.
    assert [(e.row, e.col) for e in keys] == [(1, 3)]


def test_the_drop_is_a_reading_not_an_event():
    """The whole reason it is a tick: it may run any number of times and must
    say the same thing, because that is what makes undo safe."""
    import main
    room = _room_with({'kind': 'goblin', 'at': [1, 3], 'drops': 'floor_key'})
    room.kill_entity(room.entity_at(1, 3))
    for _ in range(4):
        main._drop_tick(room, _player_at(1, 1))
    assert len([e for e in room.entities if e.kind == 'floor_key' and e.alive]) == 1


def test_a_creature_cannot_drop_a_creature():
    """`drops` is the one field that CREATES an entity at runtime, so it is the
    one field a downloaded file could use to hatch something nobody counted."""
    import main
    from sharing import validate as V
    room = _room_with({'kind': 'goblin', 'at': [1, 3], 'drops': 'warden'})
    room.kill_entity(room.entity_at(1, 3))
    main._drop_tick(room, _player_at(1, 1))
    assert not [e for e in room.entities if e.kind == 'warden']

    lvl = _tiny()
    lvl.entities = [{'kind': 'goblin', 'at': [2, 3], 'drops': 'warden'}]
    rep = V.validate(lvl)
    assert not rep.ok and any('drops' in e for e in rep.errors)


def test_drops_and_group_survive_the_file():
    lvl = _tiny()
    lvl.entities = [{'kind': 'goblin', 'at': [2, 3], 'drops': 'floor_key:red',
                     'group': 'patrol'}]
    back = F.loads(F.dumps(lvl))
    room = F.build(back).room
    assert (room.entity_at(2, 3).drops, room.entity_at(2, 3).group) \
        == ('floor_key:red', 'patrol')


def test_entity_places_with_its_fields_set():
    """`:entity kind field=value` — the `:set` form. Before this the command
    placed a canned preset and there was no way to set `tag` at all, which meant
    coloured keys and coloured doors were unreachable from the forge despite
    working perfectly in the engine."""
    d = DRAFT.new('Probe', rows=8, cols=30)
    _forge_session(d, 'jl:entity goblin tag=echo hp=3 drops=floor_key:gold\r:w\r:q!\r')
    ent = [e for e in d.level.entities if e['kind'] == 'goblin'][0]
    assert (ent['tag'], ent['hp'], ent['drops']) == ('echo', 3, 'floor_key:gold')


def test_entity_retunes_what_is_already_there():
    d = DRAFT.new('Probe', rows=8, cols=30)
    _forge_session(d, 'jl:entity locked_door\r:entity tag=gold\r:w\r:q!\r')
    ent = [e for e in d.level.entities if e['kind'] == 'locked_door'][0]
    assert ent['tag'] == 'gold'


def test_entity_bang_removes_and_entity_refuses_a_bad_field():
    d = DRAFT.new('Probe', rows=8, cols=30)
    _forge_session(d, 'jl:entity goblin hp=lots\r:w\r:q!\r')
    gob = [e for e in d.level.entities if e['kind'] == 'goblin']
    assert gob and gob[0]['hp'] == 1, 'a bad value must not be stored'
    _forge_session(d, 'jl:entity!\r:w\r:q!\r')
    assert not [e for e in d.level.entities if e['kind'] == 'goblin']


def test_the_picker_builds_a_red_key_not_just_a_default_one():
    """The menu has to reach every field, or it cannot make the first thing
    anyone wants from it.

    Driven through the real key loop: `:entity` opens the palette, jjj walks to
    floor_key, Enter chooses it, Enter opens `tag`, jj picks red off the colour
    list, and the last row places it. A picker that could only place the DEFAULT
    of each kind would leave `:entity floor_key tag=red` as the only route."""
    import main
    d = DRAFT.new('Probe', rows=8, cols=30)
    _forge_session(d, 'jl:entity\rjjj\r\rjj\rj\r:w\r:q!\r')
    key = [e for e in d.level.entities if e['kind'] == 'floor_key']
    assert key and key[0]['tag'] == 'red'
    # …and the fields are opt-in: Enter straight through still places a plain one
    d2 = DRAFT.new('Probe', rows=8, cols=30)
    _forge_session(d2, 'jl:entity\rjjj\rj\r:w\r:q!\r')
    key = [e for e in d2.level.entities if e['kind'] == 'floor_key']
    assert key and key[0].get('tag', '') == ''


def test_the_picker_offers_only_colours_the_game_paints():
    """`tag=orange` pairs a key to a door perfectly well — pairing is string
    equality — but the renderer knows three colours, so an orange key comes out
    brass and nothing anywhere says why. The list is where that silent gap
    becomes visible."""
    import main
    from render import renderer

    offered = [c for c in main._entity_choices('floor_key', 'tag') if c]
    assert offered == list(main._KEY_COLOURS)
    # the claim under the list: these are exactly the tags the renderer branches
    # on, so nothing offered is cosmetically dead and nothing live is withheld
    import inspect
    src = inspect.getsource(renderer._ent_cell_str)
    for c in offered:
        assert f"ent.tag == '{c}'" in src
    assert 'orange' not in src


def test_a_tag_the_list_does_not_offer_is_still_reachable():
    """The narrow set is what the game PAINTS, not what it permits. An author
    pairing on `tag=vault_b` is doing nothing wrong, so the last row of every
    choice list opens the free text field."""
    d = DRAFT.new('Probe', rows=8, cols=30)
    # …\r opens tag, k wraps to the last row ("type something else"), then type
    _forge_session(d, 'jl:entity\rjjj\r\rk\rvault_b\rj\r:w\r:q!\r')
    key = [e for e in d.level.entities if e['kind'] == 'floor_key']
    assert key and key[0]['tag'] == 'vault_b'


def test_the_offered_scroll_ids_are_the_real_catalogue():
    """Read from SCROLL_CATALOG, not hand-copied: an id that matches no scroll
    shows no scroll at all, silently, and a hand-written list drifts the moment
    a scroll is added."""
    import main
    from content.scrolls import SCROLL_CATALOG

    offered = main._entity_choices('chest_scroll', 'scroll_id')
    assert offered[0] == ''          # unassigned → the relic pool
    assert set(offered[1:]) == {s['id'] for s in SCROLL_CATALOG}


def test_a_red_chest_yields_a_red_key():
    """A `chest_key` carries its tag onto the key it gives up. Without this the
    pairing an author set on the chest dissolved at the moment of looting and
    the red door it was cut for never opened."""
    import main
    from engine.world import Entity
    room = _room_with({'kind': 'chest_key', 'at': [1, 3], 'tag': 'red'})
    chest = room.entity_at(1, 3)
    assert main._chest_loot('chest_key') == 'key'
    assert chest.tag == 'red'


def test_a_file_written_before_the_rename_still_loads():
    """`chest` became `chest_random`. A kind is written into every saved layout,
    every published level and every draft on disk, so a rename is a FORMAT
    change — files already in the wild name the old kind, and the only
    acceptable answer is to keep reading them.

    Both load paths, because they are separate code: the community format and
    the editor's own save. Nothing writes the old name back out, so a file heals
    itself the next time it is saved."""
    from engine.editor import _deserialize_room, _serialize_room
    from engine.world import Room, RoomType, Entity, canonical_kind

    lvl = _tiny()
    lvl.entities = [{'kind': 'chest', 'at': [1, 3]},
                    {'kind': 'goblin', 'at': [2, 3], 'drops': 'chest:red'}]
    room = F.build(lvl).room
    assert room.entity_at(1, 3).kind == 'chest_random'
    # `drops` names a kind too, so it renames with it — and the validator has to
    # agree with the parser or the file is refused for a rename nobody made
    assert room.entity_at(2, 3).drops == 'chest_random:red'
    from sharing import validate as V
    assert not [e for e in V.validate(lvl).errors if 'drops' in e]

    room = Room(room_type=RoomType.ENTRY, rows=4, cols=8)
    room.cells = [[CellType.FLOOR] * 8 for _ in range(4)]
    data = _serialize_room(room)
    data['entities'] = [{'kind': 'chest', 'row': 1, 'col': 3}]
    assert _deserialize_room(data).entity_at(1, 3).kind == 'chest_random'
    # a kind that was never renamed passes through untouched
    assert canonical_kind('goblin') == 'goblin'


def test_the_wanderer_chases_but_never_strikes():
    """The palette calls it a half-speed chaser that does no damage — pinning
    that here because it is a claim about the ENGINE made in a menu, and the two
    can drift apart silently."""
    import main
    from engine.world import Entity
    room = _room_with()
    pre  = dict(main._ENTITY_PALETTE['wanderer'][0])
    w    = Entity(kind='wanderer', row=1, col=5, **pre)
    room.add_entity(w)
    p = _player_at(1, 1)
    start, hp = w.col, p.hp
    for _ in range(8):
        main._enemy_tick(room, p)
    assert w.col < start, 'the wanderer never moved'
    assert p.hp == hp, 'the wanderer dealt damage'


# ── Sealed doors: a text-match condition an author can declare ────────────────

def _sealed(match='open sesame', mode='exact', opens=((2, 8),), text='open sesame'):
    lvl = _tiny()
    lvl.rows, lvl.cols = 5, 16
    lvl.cells = ['16W', 'W14FW', 'W14FW', 'W14FW', '16W']
    lvl.exit  = (3, 14)
    lvl.seals = [F.Seal(region=(1, 1, 1, 12), match=match, mode=mode, opens=opens)]
    if text:
        lvl.char_runs = [{'row': 1, 'col': 1, 'symbols': list(text), 'kind': 'ancient'}]
    return lvl


def test_a_seal_stands_open_exactly_while_its_region_reads_true():
    import main
    room = F.build(_sealed()).room
    p = _player_at(3, 1)
    main._seal_tick(room, p)
    assert room.cells[2][8] == CellType.FLOOR
    # …and re-shuts the moment it does not. This is the undo story: undo restores
    # the text, the tick re-reads it, and the door answers for what is there NOW.
    room.remove_char_run(room.char_run_at(1, 1))
    main._seal_tick(room, p)
    assert room.cells[2][8] == CellType.WALL


def test_exact_means_exact_and_contains_is_opt_in():
    import main
    p = _player_at(3, 1)
    near = F.build(_sealed(match='sesame', text='open sesame')).room
    main._seal_tick(near, p)
    assert near.cells[2][8] == CellType.WALL, 'exact must not match a substring'

    loose = F.build(_sealed(match='sesame', mode='contains',
                            text='open sesame')).room
    main._seal_tick(loose, p)
    assert loose.cells[2][8] == CellType.FLOOR


def test_a_seal_ships_shut_however_the_grid_was_saved():
    """An author tests their door, it opens, they save — and `cells` records the
    open cell as floor. Without re-shutting on both ends the level would arrive
    with its puzzle already solved."""
    lvl = _sealed()
    lvl.cells = ['16W', 'W14FW', 'W14FW', 'W14FW', '16W']   # (2,8) is FLOOR here
    room = F.build(lvl).room
    assert room.cells[2][8] == CellType.WALL

    # …and the export side holds the same line INDEPENDENTLY — asserted on the
    # written grid, not on a rebuild, because `build` re-shuts them too and would
    # cover for an export that wrote the door out standing open.
    room.cells[2][8] = CellType.FLOOR
    back = F.from_room(room, 'X', seals=list(room.seals))
    assert F.expand_row(back.cells[2], back.cols, 2)[8] == CellType.WALL


def test_a_seal_never_walls_the_player_in():
    import main
    room = F.build(_sealed()).room
    main._seal_tick(room, _player_at(3, 1))
    room.remove_char_run(room.char_run_at(1, 1))
    main._seal_tick(room, _player_at(2, 8))          # standing in the doorway
    assert room.cells[2][8] == CellType.FLOOR


def test_a_seal_reads_only_walkable_stone():
    """Every hardcoded text-match door in the game already ignores wall cells,
    because the target word is usually on a plaque set into the wall beside the
    door — and a scan that read the wall would find the door opened by its own
    label."""
    import main
    lvl = _sealed(text='')
    lvl.cells = ['16W', '16W', 'W14FW', 'W14FW', '16W']   # row 1 is solid stone
    lvl.char_runs = [{'row': 1, 'col': 1, 'symbols': list('open sesame'),
                      'kind': 'verdant'}]
    room = F.build(lvl).room
    assert room.cells[1][1] == CellType.WALL
    main._seal_tick(room, _player_at(3, 1))
    assert room.cells[2][8] == CellType.WALL

    # …and the same words on walkable stone DO open it, so the assertion above
    # is about the wall and not about the words being wrong.
    lvl.cells = ['16W', 'W14FW', 'W14FW', 'W14FW', '16W']
    ok = F.build(lvl).room
    main._seal_tick(ok, _player_at(3, 1))
    assert ok.cells[2][8] == CellType.FLOOR


def test_a_door_cannot_be_part_of_the_text_that_opens_it():
    from sharing import validate as V
    lvl = _sealed(opens=((1, 3),))               # inside region (1,1)-(1,6)
    rep = V.validate(lvl)
    assert not rep.ok and any('inside' in e for e in rep.errors)


def test_seals_survive_the_file():
    lvl = _sealed(mode='contains', opens=((2, 8), (2, 9)))
    back = F.loads(F.dumps(lvl))
    assert back.seals == lvl.seals


def test_the_forge_arms_a_seal_and_bolts_it():
    """`:seal <text>` over a selection, then `:bolt` on the door. Two commands
    because the condition and the door are in two places at once."""
    d = DRAFT.new('Probe', rows=8, cols=30)
    _forge_session(d, 'jv' + 'l' * 6 + T.ESC
                      + 'jjlll:seal open sesame\r:bolt\r:w\r:q!\r')
    assert len(d.level.seals) == 1
    s = d.level.seals[0]
    assert (s.match, s.mode, s.region[0], s.opens) == (('open sesame',), 'exact', 2,
                                                       ((4, 4),))


def test_a_ranged_bolt_wires_a_whole_wall_to_one_trigger():
    """A gate is rarely one cell. Bolting it a cell at a time is the same seal
    retyped as many times as the wall is wide — with the range, the wall the
    author selected IS the door."""
    d = DRAFT.new('Probe', rows=8, cols=30)
    # seal on row 2; drop to row 5, paint a five-cell wall over the selection,
    # bring the same selection back with gv, bolt once
    _forge_session(d, 'jv' + 'l' * 6 + ':seal open sesame\r'
                      + 'jjjv' + 'l' * 4 + ':paint wall\r'
                      + 'gv:bolt\r:w\r:q!\r')
    assert len(d.level.seals) == 1
    s = d.level.seals[0]
    assert s.match == ('open sesame',)     # one target, normalised to a tuple
    assert sorted(s.opens) == [(5, 7), (5, 8), (5, 9), (5, 10), (5, 11)]
    # and the wall is stone in the saved file — the tick is what swings it
    assert d.level.cells[5] == 'W6F5W17FW'


def test_a_ranged_bolt_takes_the_masonry_and_leaves_the_floor():
    """Walls only, where `:entity` takes the standable cells — each command
    takes the half of the selection it can mean anything about. A seal writes
    its opens cells out as STONE, so bolting floor would wall off squares the
    author was standing on."""
    d = DRAFT.new('Probe', rows=8, cols=30)
    # one painted wall cell in a nine-cell selection that is otherwise floor
    _forge_session(d, 'jv' + 'l' * 6 + ':seal open sesame\r'
                      + 'jjj' + 'lll' + ':paint wall\r'
                      + 'hhhv' + 'l' * 8 + ':bolt\r:w\r:q!\r')
    assert [tuple(c) for c in d.level.seals[0].opens] == [(5, 10)]


def test_a_ranged_bolt_refuses_to_swallow_its_own_condition():
    """Refused, not quietly trimmed: the selection is the author saying which
    cells they mean, and silently meaning fewer is how a wall ends up with a
    hole in it that nobody put there."""
    d = DRAFT.new('Probe', rows=8, cols=30)
    # a wall painted INSIDE the region the seal reads, then a whole-row bolt
    _forge_session(d, 'j' + 'll' + ':paint wall\r' + 'hh'
                      + 'v' + 'l' * 6 + ':seal open sesame\r'
                      + 'V:bolt\r:w\r:q!\r')
    assert d.level.seals == []


def test_a_star_arms_the_looser_reading():
    d = DRAFT.new('Probe', rows=8, cols=30)
    _forge_session(d, 'jv' + 'l' * 6 + T.ESC
                      + 'jjlll:seal *sesame\r:bolt\r:w\r:q!\r')
    assert (d.level.seals[0].match, d.level.seals[0].mode) == (('sesame',), 'contains')


def test_bolting_twice_widens_one_door_rather_than_making_two():
    d = DRAFT.new('Probe', rows=8, cols=30)
    _forge_session(d, 'jv' + 'l' * 6 + T.ESC
                      + 'jjlll:seal open sesame\r:bolt\rl:bolt\r:w\r:q!\r')
    assert len(d.level.seals) == 1
    assert d.level.seals[0].opens == ((4, 4), (4, 5))


def test_at_colon_replaces_the_same_entity_again():
    """`.` repeats the last CHANGE; an Ex command is not one, so vim answers
    `:entity goblin` again with `@:` — and `@@` after that. Placing a row of
    identical entities is the commonest thing an author does, and before this
    the only route was retyping the whole command each time."""
    d = DRAFT.new('Probe', rows=8, cols=30)
    _forge_session(d, 'jl:entity goblin tag=echo\rl@:l@@\r:w\r:q!\r')
    gobs = sorted((e['at'][1], e.get('tag')) for e in d.level.entities
                  if e['kind'] == 'goblin')
    assert gobs == [(2, 'echo'), (3, 'echo'), (4, 'echo')]


def test_the_colon_register_holds_the_bare_command_like_vim():
    """Vim's `:` register holds `entity goblin` — the text, without the colon or
    the <CR>. Those go back on at replay, so the register stays something you
    could read or paste rather than a keystroke soup."""
    from engine.registers import record_register, read_register, clip_to_keys

    class _P:
        registers = {}
    p = _P()
    record_register(p, ':', 'entity goblin tag=echo')
    assert clip_to_keys(read_register(p, ':')) == 'entity goblin tag=echo'


def test_paint_lays_terrain_down_by_name():
    d = DRAFT.new('Probe', rows=8, cols=30)
    _forge_session(d, 'jll:paint water\r:w\r:q!\r')
    assert F.expand_row(d.level.cells[2], d.level.cols, 2)[3] == CellType.WATER


def test_paint_takes_the_range_like_fill():
    """A river is one command, not a lap of the old cycle per cell."""
    d = DRAFT.new('Probe', rows=8, cols=30)
    _forge_session(d, 'jlv' + 'l' * 5 + ':paint water\r:w\r:q!\r')
    row = F.expand_row(d.level.cells[2], d.level.cols, 2)
    assert [i for i, ct in enumerate(row) if ct == CellType.WATER] == [2, 3, 4, 5, 6, 7]


def test_painted_mist_survives_the_round_trip():
    """Misted water is the terrain the `s` cycle could never reach — and the
    reason it could not be painted is the same reason it could not be SAVED: the
    grid had no code for it. `M` is water plus its permanent haze."""
    d = DRAFT.new('Probe', rows=8, cols=30)
    _forge_session(d, 'jll:paint mist\r:w\r:q!\r')
    assert 'M' in d.level.cells[2]
    room = F.build(d.level).room
    assert room.cells[2][3] == CellType.WATER
    assert (2, 3) in room.mist_cells
    assert (2, 3) in room.fog_cells


def test_paint_leaves_a_wall_plaque_standing():
    """`s` cut the text as it laid the stone. A plaque set INTO a wall is what
    the architecture asks for — uncuttable, unread by the floor scans — so the
    brush that could not paint one was the wrong brush."""
    d = DRAFT.new('Probe', rows=8, cols=30)
    _forge_session(d, 'jli' + 'plaque' + T.ESC + ':paint wall\r:w\r:q!\r')
    assert any(''.join(ru['symbols']).startswith('p') for ru in d.level.char_runs)


def test_a_bare_rune_opens_the_list():
    """Every forge command whose argument comes from a list the game already
    knows answers the bare form with that list — the question being asked is
    "which ones are there?"."""
    d = DRAFT.new('Probe', rows=8, cols=30)
    _forge_session(d, 'jl:rune\r' + 'jj\r' + ':w\r:q!\r')   # third row: void
    assert [(ru['kind'], ru['col']) for ru in d.level.char_runs] == [('void', 2)]


def test_a_bare_paint_opens_the_list():
    d = DRAFT.new('Probe', rows=8, cols=30)
    _forge_session(d, 'jl:paint\r' + 'j\r' + ':w\r:q!\r')   # second row: corridor
    assert F.expand_row(d.level.cells[2], d.level.cols, 2)[2] == CellType.CORRIDOR


def test_a_bare_fill_opens_the_pool_list():
    """It used to mean `:fill plain` in silence — a default where a question
    was being asked."""
    d = DRAFT.new('Probe', rows=8, cols=30)
    _forge_session(d, 'jv' + 'l' * 20 + ':fill\r' + 'jj\r' + ':w\r:q!\r')
    assert [f.pool for f in d.level.fills] == ['proverbs']   # third row


def test_reopening_a_draft_regrows_its_fills():
    """`:e` is the author's window onto somebody else's copy.

    Every player who opens a shipped level grows their own words; an author who
    only ever sees the arrangement their seed happened to give them is judging
    one draw out of thousands. So `:e` — and only `:e`, never an incidental
    rebuild — re-rolls, the way entering the level does."""
    d = DRAFT.new('Probe', rows=8, cols=40)
    real, built, seeds = d.build, [], []

    def _spy(par=None, seed=None):
        seeds.append(seed)
        built.append(real(par=par, seed=seed))
        return built[-1]

    d.build = _spy
    _forge_session(d, 'jv' + 'jjj' + 'l' * 30 + ':fill plain 3-6\r'
                      + ':w\r:e\r:q!\r')
    assert seeds[0] is None        # opening the draft: the author's own room
    assert seeds[-1] is not None   # `:e`: a stranger's
    words = lambda dg: sorted(''.join(ru.symbols) for ru in dg.room.char_runs)
    assert words(built[-1]) and words(built[-1]) != words(built[-2])


def test_backing_out_of_a_picker_places_nothing():
    d = DRAFT.new('Probe', rows=8, cols=30)
    _forge_session(d, 'jl:rune\r' + T.ESC + ':w\r:q!\r')
    assert d.level.char_runs == []


def test_a_line_pool_lays_whole_sayings():
    """A proverb is a sentence. Taken apart into a bag of words by length it is
    word salad wearing a proverb's vocabulary — and for `misquotes`, whose whole
    point is one wrong word to spot and mend, there is nothing left to mend."""
    from sharing import vocab
    lvl = _sized(rows=8, cols=60,
                 cells=['60W'] + ['W58FW'] * 6 + ['60W'],
                 fills=[F.Fill(region=(2, 1, 5, 58), pool='proverbs',
                               length=(3, 6), spacing=1)])
    room = F.build(lvl).room
    laid = {}
    for ru in room.char_runs:
        laid.setdefault(ru.row, []).append((ru.col, ''.join(ru.symbols)))
    assert laid, 'the fill grew nothing at all'
    known = {' '.join(s) for s in vocab.sayings('proverbs')}
    for r, runs in laid.items():
        # words one space apart belong to the same saying; a wider gap ends it
        phrase, end = [], None
        for c, word in sorted(runs):
            if end is not None and c != end + 2:
                assert ' '.join(phrase) in known, f'row {r}: {phrase} is not a proverb'
                phrase = []
            phrase.append(word)
            end = c + len(word) - 1
        assert ' '.join(phrase) in known, f'row {r}: {phrase} is not a proverb'


def test_a_line_pool_refuses_a_region_too_narrow_to_hold_a_saying():
    """Nothing would grow — which reads, on screen, exactly like a fill that
    silently did not take."""
    d = DRAFT.new('Probe', rows=8, cols=30)
    _forge_session(d, 'jv' + 'l' * 5 + ':fill proverbs\r:w\r:q!\r')
    assert d.level.fills == []


def test_fill_reads_back_the_directive_under_the_cursor():
    d = DRAFT.new('Probe', rows=8, cols=30)
    # :fill? is a question, so nothing may change — the fill list is the proof
    _forge_session(d, 'jv' + 'l' * 20 + ':fill plain\r' + 'jl:fill?\r:w\r:q!\r')
    assert len(d.level.fills) == 1


def test_the_words_are_rerolled_for_every_player():
    """A fill is the author saying "a wall of words here", not "these words
    here". Built at two seeds it must read differently, the way every shipped
    level does when you enter it twice."""
    lvl = _sized(rows=8, cols=60,
                 cells=['60W'] + ['W58FW'] * 6 + ['60W'],
                 fills=[F.Fill(region=(2, 1, 5, 58), pool='plain',
                               length=(3, 6), spacing=1)])
    one = F.build(lvl, seed=11).room
    two = F.build(lvl, seed=12).room
    text = lambda room: sorted((ru.row, ru.col, ''.join(ru.symbols))
                               for ru in room.char_runs)
    assert text(one) != text(two)
    # …and one seed twice is still one room: nothing else is left to chance
    assert text(F.build(lvl, seed=11).room) == text(one)


def test_a_route_that_reads_its_own_scenery_is_refused():
    """The freedom to re-roll is only safe because this is proven, not hoped
    for: the tape must win at the same par whatever the words came out as.

    The level here puts its exit exactly where a word happened to start, and
    the route is `w` — word-hop onto it. That is a route reading its own
    scenery: at any other arrangement the eighth word begins somewhere else."""
    from sharing.validate import validate

    def _lvl(exit_col, tape):
        return _sized(rows=5, cols=60, seed=7,
                      cells=['60W'] + ['W58FW'] * 3 + ['60W'],
                      spawn=(1, 1), exit=(1, exit_col),
                      teaches=['w'], requires=[],
                      fills=[F.Fill(region=(1, 2, 1, 52), pool='plain',
                                    length=(3, 6), spacing=1)],
                      solution=tape)

    # where the 8th word starts at the file's own seed — the fill is grown from
    # the seed alone, so the exit can be placed after looking at it
    starts = sorted(ru.col for ru in F.build(_lvl(2, 'w')).room.char_runs
                    if ru.row == 1)
    rep = validate(_lvl(starts[7], 'w' * 8))
    assert not rep.ok
    assert any('words grew' in e for e in rep.errors), rep.errors


def test_publishing_trims_the_canvas_back_to_the_level():
    """The canvas is not the level. A 100x100 draft whose room is 20x80 ships as
    20x80 — cropping stone changes no motion, so par is untouched."""
    lvl = DRAFT.new('CropProbe').level
    tight = F.crop(lvl)
    assert (tight.rows, tight.cols) == (20, 80)
    assert tight.spawn == (1, 1)
    assert F.crop(tight) is tight          # idempotent: already tight


def test_cropping_carries_everything_with_it():
    lvl = _sized(rows=20, cols=40,
                 cells=['40W'] * 9 + ['20W18F2W'] + ['40W'] * 10,
                 spawn=(9, 21), exit=(9, 30),
                 char_runs=[{'row': 9, 'col': 25, 'symbols': list('door'),
                             'kind': 'ancient'}],
                 entities=[{'kind': 'goblin', 'at': [9, 28]}])
    tight = F.crop(lvl)
    assert (tight.rows, tight.cols) == (3, 20)
    assert tight.cells == ['20W', 'W18FW', '20W']
    assert tight.spawn == (1, 2) and tight.exit == (1, 11)
    assert tight.char_runs[0]['col'] == 6
    assert tight.entities[0]['at'] == [1, 9]


# ── Doors: what blocks feet, and what blocks the eye ──────────────────────────
#
# A door is a THING STANDING ON a cell, not a kind of ground, and the two facts
# about it are separate: `locked_door` blocks feet, `opaque` blocks sight. The
# fog law is stone-bounded on purpose — a caged specimen has to be an exhibit
# rather than a rumour — so a door that hides what is behind it has to say so.

def _corridor(**kw) -> F.Level:
    """One run of floor: spawn at the west end, exit at the east."""
    kw.setdefault('spawn', (1, 1))
    kw.setdefault('exit', (1, 10))
    kw.setdefault('solution', '$')
    kw.setdefault('teaches', ['$'])
    return _sized(rows=3, cols=12, cells=['12W', 'W10FW', '12W'], **kw)


def test_a_plain_door_is_a_grille_the_eye_crosses():
    """Unchanged, and deliberately: fog derived from geometry is what stops a
    door being a fog exemption every builder has to remember."""
    lvl = _corridor(entities=[{'kind': 'door', 'at': [1, 5]}])
    assert not F.build(lvl).room.fog_cells


def test_an_opaque_door_fogs_everything_behind_it():
    """The thing a level file could not say: darkness where there is no wall."""
    lvl = _corridor(entities=[{'kind': 'door', 'at': [1, 5], 'opaque': True}])
    fog = F.build(lvl).room.fog_cells
    assert (1, 6) in fog and (1, 10) in fog, 'the far side is lit'
    assert (1, 5) not in fog, 'you can see the door itself'
    assert (1, 4) not in fog, 'the near side is where you are standing'


def test_opening_an_opaque_door_is_what_lifts_its_fog():
    """No scripted fog and nothing stored: kill the door and the law itself
    says the room beyond is visible."""
    from engine.motion import stone_law
    room = F.build(_corridor(
        entities=[{'kind': 'door', 'at': [1, 5], 'opaque': True}])).room
    room.kill_entity(room.entity_at(1, 5))
    assert not stone_law(room)


def test_a_locked_door_blocks_feet_and_a_plain_one_does_not():
    """The report: 'the door west of the Zombie doesn't block me'. It never
    did — that is `locked_door`'s job, and a plain door is walked onto and
    opened with x."""
    plain = F.build(_corridor(entities=[{'kind': 'door', 'at': [1, 5]}])).room
    shut  = F.build(_corridor(
        entities=[{'kind': 'locked_door', 'at': [1, 5]}])).room
    assert plain.is_passable(1, 5)
    assert not shut.is_passable(1, 5)


def test_opaque_survives_the_file():
    lvl = _corridor(entities=[{'kind': 'door', 'at': [1, 5], 'opaque': True}])
    back = F.loads(F.dumps(lvl))
    assert back.entities[0]['opaque'] is True
    assert F.build(back).room.fog_cells


# ── Furniture the level's own commands cannot work ────────────────────────────

def test_a_locked_door_in_a_level_that_never_taught_paste_is_flagged():
    """The second half of the report: the key would not open the door. It is
    opened by PASTING the key onto it, and the level declared no p — which the
    author cannot see, because the forge does not gate."""
    lvl = _corridor(entities=[{'kind': 'locked_door', 'at': [1, 5]},
                              {'kind': 'floor_key', 'at': [1, 3]}],
                    spawn=(1, 1), exit=(1, 2), solution='l')
    from sharing.validate import validate
    rep = validate(lvl)
    assert any('nobody can open it' in w for w in rep.warnings), rep.warnings


def test_declaring_the_paste_takes_the_warning_away():
    lvl = _corridor(entities=[{'kind': 'locked_door', 'at': [1, 5]},
                              {'kind': 'floor_key', 'at': [1, 3]}],
                    spawn=(1, 1), exit=(1, 2), solution='l', requires=['p'])
    from sharing.validate import validate
    assert not [w for w in validate(lvl).warnings if 'nobody can open' in w]


def test_paint_says_where_doors_actually_come_from():
    """`Unknown paint: door` beside a palette with no door in it reads as 'this
    game has no doors'."""
    import main
    assert ':entity door' in main._paint_complaint('door')
    assert ':paint wood' in main._paint_complaint('door')
    assert 'Unknown paint' in main._paint_complaint('marble')


# ── The canvas can grow (`:canvas`) ───────────────────────────────────────────
#
# Crop is silent because it only takes stone off. Growing cannot be — nothing in
# a level says how much room its author still wants — so it is a command.

def test_growing_the_canvas_moves_nothing_that_was_already_on_it():
    """The whole safety of it: new stone goes on the bottom and the right, so
    every coordinate — and therefore any tape recorded against them — holds."""
    lvl = _sized(rows=8, cols=30,
                 cells=['30W'] + ['W28FW'] * 6 + ['30W'],
                 spawn=(1, 1), exit=(6, 28),
                 char_runs=[{'row': 2, 'col': 5, 'symbols': list('door'),
                             'kind': 'ancient'}],
                 entities=[{'kind': 'goblin', 'at': [3, 9]}],
                 fills=[F.Fill(region=(4, 2, 4, 20), pool='plain',
                               length=(4, 4), spacing=1)])
    big = F.resize(lvl, 40, 120)
    assert (big.rows, big.cols) == (40, 120)
    assert big.spawn == lvl.spawn and big.exit == lvl.exit
    assert big.entities == lvl.entities and big.char_runs == lvl.char_runs
    assert big.fills[0].region == (4, 2, 4, 20)
    room = F.build(big).room
    assert [c.name for c in room.cells[1][:30]] == \
           [c.name for c in F.build(lvl).room.cells[1]]
    assert all(c == CellType.WALL for c in room.cells[39]), 'new ground is stone'


def test_growing_and_cropping_are_each_others_undo():
    lvl = DRAFT.new('CanvasProbe', rows=8, cols=30).level
    assert F.crop(F.resize(lvl, 60, 90)).cells == F.crop(lvl).cells


def test_the_canvas_will_not_shrink_over_something():
    """Refused, not silently trimmed: a level quietly missing its exit is worse
    than a level that would not resize."""
    lvl = _sized(rows=8, cols=30, cells=['30W'] + ['W28FW'] * 6 + ['30W'],
                 spawn=(1, 1), exit=(6, 28))
    with pytest.raises(F.LevelFormatError, match='cut it'):
        F.resize(lvl, 8, 10)
    assert F.resize(lvl, 8, 30) is lvl                 # no change is no work


def test_the_forge_can_grow_the_room_the_author_is_standing_in():
    """The report: an author was capped inside a rectangle they never chose, on
    a draft made before drafts opened on a canvas (2026-07-27)."""
    d = DRAFT.new('Probe', rows=8, cols=30)
    _forge_session(d, ':canvas 40x120\r:w\r:q!\r')
    again = DRAFT.load(d.path).level
    assert (again.rows, again.cols) == (40, 120)
    assert again.spawn == (1, 1), 'the room the author was standing in moved'


def test_a_canvas_the_format_would_refuse_is_refused_here_too():
    d = DRAFT.new('Probe', rows=8, cols=30)
    _forge_session(d, ':canvas 400x400\r:w\r:q!\r')
    assert (DRAFT.load(d.path).level.rows,
            DRAFT.load(d.path).level.cols) == (8, 30)


def test_s_is_vims_s_again_in_the_editor():
    """`s` walked a ring of cell types for as long as the forge has existed —
    the one thing `s` means nowhere else in this game. `:paint` took that job
    and the key went back to the buffer: cut what is here, then type."""
    d = DRAFT.new('Probe', rows=8, cols=30)
    _forge_session(d, 'jli' + 'cat' + T.ESC + 'hhhsb' + T.ESC + ':w\r:q!\r')
    row = ''.join(''.join(ru['symbols']) for ru in d.level.char_runs
                  if ru['row'] == 2)
    assert 'bat' in row
    # …and the cell it typed over is still floor: the ring would have walled it
    assert F.expand_row(d.level.cells[2], d.level.cols, 2)[2] == CellType.FLOOR


def test_an_unknown_paint_names_the_ones_that_exist():
    d = DRAFT.new('Probe', rows=8, cols=30)
    _forge_session(d, 'jll:paint lava\r:w\r:q!\r')
    row = F.expand_row(d.level.cells[2], d.level.cols, 2)
    assert row[3] == CellType.FLOOR      # nothing guessed at, nothing painted
