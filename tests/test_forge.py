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


def _forge_session(draft, script: str, player_name: str = 'admin', dungeon=None):
    """Drive a real forge session: open `draft` in the editor and type `script`.

    Pass `dungeon` to keep a handle on the object the chrome renders from — the
    only way to observe, from out here, what the status bar was showing."""
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
                                _dungeon=dungeon or draft.build(), _start_edit=True,
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
    floor_key, Enter chooses it, Enter opens `tag`, the value is typed, and the
    last row places it. A picker that could only place the DEFAULT of each kind
    would leave `:entity floor_key tag=red` as the only route to a red key."""
    import main
    d = DRAFT.new('Probe', rows=8, cols=30)
    _forge_session(d, 'jl:entity\rjjj\r\rred\rj\r:w\r:q!\r')
    key = [e for e in d.level.entities if e['kind'] == 'floor_key']
    assert key and key[0]['tag'] == 'red'
    # …and the fields are opt-in: Enter straight through still places a plain one
    d2 = DRAFT.new('Probe', rows=8, cols=30)
    _forge_session(d2, 'jl:entity\rjjj\rj\r:w\r:q!\r')
    key = [e for e in d2.level.entities if e['kind'] == 'floor_key']
    assert key and key[0].get('tag', '') == ''


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
    assert (s.match, s.mode, s.region[0], s.opens) == ('open sesame', 'exact', 2,
                                                       ((4, 4),))


def test_a_star_arms_the_looser_reading():
    d = DRAFT.new('Probe', rows=8, cols=30)
    _forge_session(d, 'jv' + 'l' * 6 + T.ESC
                      + 'jjlll:seal *sesame\r:bolt\r:w\r:q!\r')
    assert (d.level.seals[0].match, d.level.seals[0].mode) == ('sesame', 'contains')


def test_bolting_twice_widens_one_door_rather_than_making_two():
    d = DRAFT.new('Probe', rows=8, cols=30)
    _forge_session(d, 'jv' + 'l' * 6 + T.ESC
                      + 'jjlll:seal open sesame\r:bolt\rl:bolt\r:w\r:q!\r')
    assert len(d.level.seals) == 1
    assert d.level.seals[0].opens == ((4, 4), (4, 5))
