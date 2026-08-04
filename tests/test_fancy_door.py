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

"""The fancy door — a door whose key is words you cut off the floor.

The gesture is the one the player already knows: stand beside a shut door and
paste. Only the key has changed. A locked door wants a `floor_key` you picked up
with `x`; a fancy door wants a REGISTER whose text reads its password, which
means the key is something you cut out of the level rather than something you
found lying in it.

WHY IT EXISTS. Levels that teach one operator+motion pair per corridor could
only ever punish a cut that took too LITTLE — leave a guard alive and he is
still standing at the exit. Nothing punished a cut that took too MUCH, because
every creature `dw` kills `d$` kills too. That is not a small gap: it let `d$`
and `d^` clear six of the Operator's Vault's ten corridors for less than par,
so six lessons were decorative. The fancy door is the missing half — overshoot
and the register carries extra words, and extra words are not the password.

Between a guard and a fancy door, exactly one motion fits: one sets the floor,
the other the ceiling.

THE RULE THIS FILE PINS HARDEST is that the check reads the REGISTER and never
the cells in front of the door. Without that, a player could reasonably conclude
they were meant to shove the right word into the doorway by inserting and
deleting whitespace — and worse, they would be right, which would make the
level solvable by an edit that has nothing to do with its lesson.
"""
import pytest

from vimny.engine.registers import clip_to_text
from vimny.engine.world import Entity, Room, RoomType, CellType, CARET_TRANSPARENT
from vimny.engine.motion import _FOG_BLOCK_KINDS, _SCAN_BLOCK


def _clip(*lines, linewise=False, width=40):
    """A register clip holding `lines`, laid out the way a cut produces one."""
    rows = []
    for text in lines:
        rows.append({'width': width, 'entities': (),
                     'char_runs': [{'dcol': 0, 'symbols': list(text)}]})
    return {'rows': rows, 'linewise': linewise}


# ── what the door reads ────────────────────────────────────────────────────

def test_a_word_reads_as_itself():
    assert clip_to_text(_clip('password')) == 'password'


def test_the_trailing_space_dw_drags_along_does_not_count():
    """`dw` takes the whitespace after the word and `de` does not. That is a
    difference in the motion, not in the answer, so the door must not care —
    otherwise half the corridors would be unsolvable by the very motion they
    teach."""
    assert clip_to_text(_clip('password ')) == clip_to_text(_clip('password'))


def test_a_linewise_cut_sheds_its_column_padding():
    """`dd` hands over a whole line, most of which is the blank floor either
    side of the words. A door comparing raw text would refuse every `dd`."""
    assert clip_to_text(_clip('     speak friend and enter        ',
                              linewise=True)) == 'speak friend and enter'


def test_an_over_wide_cut_keeps_its_extra_words():
    """THE POINT. Whitespace is collapsed; words are not. A cut that swept in
    one more word reads as one more word, and no trimming hides it."""
    assert clip_to_text(_clip('password  and  then  some')) == 'password and then some'


def test_an_empty_register_reads_as_nothing():
    assert clip_to_text(None) == ''
    assert clip_to_text({'rows': []}) == ''


def test_multi_line_cuts_read_as_one_utterance():
    assert clip_to_text(_clip('open', 'sesame')) == 'open sesame'


# ── what the door is ───────────────────────────────────────────────────────

def _room_with_door(password='p1g.sn0ut'):
    room = Room(room_type=RoomType.ENTRY, rows=5, cols=20)
    room.cells = [[CellType.FLOOR] * 20 for _ in range(5)]
    for c in range(20):
        room.cells[0][c] = room.cells[4][c] = CellType.WALL
    room.add_entity(Entity(kind='fancy_door', row=2, col=10, password=password))
    room.rebuild_indexes()
    return room


def test_a_fancy_door_blocks_feet():
    """If it did not block, it would be scenery. Every other gate kind in the
    engine is listed as impassable and this one has to be too."""
    room = _room_with_door()
    assert not room.is_passable(2, 10)


def test_a_fancy_door_stops_the_line_motions_that_would_walk_past_it():
    """`$` / `0` / `^` and `f`/`F`/`t`/`T` are segment-bounded — they stop at a
    gate. A fancy door that scans transparent would let `d$` reach straight
    through the thing meant to be judging `d$`."""
    assert 'fancy_door' in _SCAN_BLOCK


def test_a_fancy_door_can_hide_what_is_behind_it():
    """It is in the fog-blocking set, so `opaque` works on it like any door and
    a corridor beyond a shut fancy door starts dark."""
    assert 'fancy_door' in _FOG_BLOCK_KINDS


def test_a_fancy_door_does_not_eat_the_caret_column():
    """Doors are caret-transparent: `^` finds the first real character on the
    row, not the masonry standing in front of it."""
    assert 'fancy_door' in CARET_TRANSPARENT


def test_the_password_survives_a_clone():
    """`clone_entity` is how every snapshot and paste copies an entity — a
    field that drops out of a copy is a door that forgets its password the
    first time the player presses `u`."""
    from vimny.engine.world import clone_entity
    door = _room_with_door().entity_at(2, 10)
    assert clone_entity(door).password == 'p1g.sn0ut'


def test_the_password_round_trips_through_a_saved_level():
    """The forge can place one, so a shared level has to carry it."""
    from vimny.engine.editor import _ENTITY_FIELDS
    assert 'password' in _ENTITY_FIELDS


# ── the forge ──────────────────────────────────────────────────────────────

def test_the_forge_can_place_one():
    import vimny.game as main
    assert 'fancy_door' in main._ENTITY_PALETTE
    assert 'password' in main._ENTITY_PALETTE['fancy_door'][2]
    assert 'password' in main._ENTITY_SETTABLE


def test_underscores_in_a_typed_password_become_spaces():
    """`:entity` splits on whitespace, so a phrase — the shape a line motion
    produces — could not otherwise be typed at all. The door stores the phrase,
    never the underscores, so what the author types and what the player must
    cut are the same words."""
    import vimny.game as main
    door = Entity(kind='fancy_door', row=1, col=1)
    assert main._entity_field(door, 'password', 'speak_friend_and_enter') == ''
    assert door.password == 'speak friend and enter'


def test_an_empty_password_is_refused():
    """A fancy door with no password is a door nothing opens. Better to
    complain in the forge than to ship a level with a dead end in it."""
    import vimny.game as main
    door = Entity(kind='fancy_door', row=1, col=1)
    assert main._entity_field(door, 'password', '')


# ── a shut door stops the CURSOR, not just the feet ─────────────────────────
#
# Every blocker in the game, not just this one: the hole was in the verbs that
# WRITE a cell and step to the next, which asked the CELL and never the entity
# standing on it. A door sits on ordinary floor, so a player could type — or
# paste — their way straight through any lock in the game while `l` refused.

_BLOCKERS = ('fancy_door', 'locked_door', 'seal_door', 'boss_seal', 'shield')


def _blocked_room(kind):
    room = Room(room_type=RoomType.ENTRY, rows=3, cols=20)
    room.cells = [[CellType.FLOOR] * 20 for _ in range(3)]
    for c in range(20):
        room.cells[0][c] = room.cells[2][c] = CellType.WALL
    room.add_entity(Entity(kind=kind, row=1, col=10, password='mellon'))
    room.rebuild_indexes()
    return room


@pytest.mark.parametrize('kind', _BLOCKERS)
@pytest.mark.parametrize('verb', ('insert', 'extend', 'replace_chars', 'overtype'))
def test_no_writing_verb_walks_the_cursor_through_a_shut_door(kind, verb):
    """i/a, A, r and R each write a cell and advance. None may advance ONTO a
    blocker — `l` will not, and a cursor is a cursor."""
    from vimny.engine.player import Player
    from vimny.engine import insert as I
    room = _blocked_room(kind)
    p = Player(row=1, col=9)
    {'insert':        lambda: I.insert_char(room, p, 'x'),
     'extend':        lambda: I.insert_char_extend(room, p, 'x'),
     'replace_chars': lambda: I.replace_chars(room, p, 'x', 3),
     'overtype':      lambda: I.replace_overtype(room, p, 'x')}[verb]()
    assert p.col == 9, f'{verb} stepped onto the {kind}'
    assert room.char_run_at(1, 10) is None, f'{verb} wrote ON the {kind}'


@pytest.mark.parametrize('kind', _BLOCKERS)
@pytest.mark.parametrize('before', (False, True))
def test_a_paste_neither_crosses_a_shut_door_nor_carries_the_cursor_over_it(kind, before):
    """The worst of the two: op_paste lands the cursor on the LAST pasted cell,
    so text laid across a door took the player with it — `5p` beside a gate
    walked them into the corridor beyond. The clip is deliberately CLUSTERED
    (two runs with a hole between them), because bounding each run on its own
    still lets the run that BEGINS past the door land there."""
    from vimny.engine.player import Player
    from vimny.engine.operator import op_paste
    room = _blocked_room(kind)
    p = Player(row=1, col=9)
    clip = {'linewise': False,
            'rows': [{'width': 5,
                      'char_runs': [{'dcol': 0, 'symbols': ('a', 'b'), 'kind': 'ancient'},
                                    {'dcol': 3, 'symbols': ('c', 'd'), 'kind': 'ancient'}],
                      'entities': []}]}
    op_paste(room, p, clip, before, 1)
    assert p.col < 10, f'the cursor rode the paste through the {kind}'
    assert all(room.char_run_at(1, c) is None for c in range(10, 20)), \
        f'the paste laid text at or past the {kind}'


def test_the_forge_offers_the_shared_password_pools():
    """An author placing a door by hand should be able to want the same words
    the built levels want — and the phrases must arrive underscored, because
    `:entity` splits its arguments on whitespace and the picker's answer is
    `:entity` text."""
    import vimny.game as main
    from vimny.content.passwords import POOLS, ALL
    offered = main._entity_choices('fancy_door', 'password')
    assert offered                                  # not free-text-only
    assert ' ' not in ''.join(offered)
    assert set(offered) == {w.replace(' ', '_') for w in ALL}
    # every offered word survives the trip back through the field setter
    door = Entity(kind='fancy_door', row=1, col=1)
    for v in offered:
        assert main._entity_field(door, 'password', v) == ''
        assert door.password in ALL
    # and each is noted by the POOL it came from — the shape, not the reference
    for name, words, _note in POOLS:
        v = words[0].replace(' ', '_')
        assert main._choice_note('password', v).startswith(f'{name} — ')


def test_the_forge_offers_the_levels_own_vocab_words_first():
    """An author's `:vocab` block is the level saying what its words are. The
    door's password is the one place that matters most, so its own words come
    FIRST, named as its own, with the shipped pools behind them."""
    import vimny.game as main
    from vimny.content.passwords import ALL
    mine = ('shibboleth', 'grimoire', 'lantern')     # one of them shipped too
    offered = main._entity_choices('fancy_door', 'password', mine)
    assert offered[:2] == ('grimoire', 'lantern')    # ahead of the shipped pools
    assert offered.count('shibboleth') == 1          # listed once, not twice
    assert set(offered) >= {w.replace(' ', '_') for w in ALL}
    assert main._choice_note('password', 'grimoire', mine) == \
        ":vocab — this level's own word"
    # a word in BOTH is noted by its shipped pool — the shape is the useful fact
    assert main._choice_note('password', 'shibboleth', mine).startswith('plain — ')
    # and with no vocabulary block, nothing changes
    assert main._entity_choices('fancy_door', 'password', ()) == \
        main._entity_choices('fancy_door', 'password')


def test_a_fancy_door_is_not_drawn_as_a_padlock():
    """It is a lock, in the lock colour — but a padlock sends a player hunting
    for something to pick up, and there is nothing to pick up."""
    import vimny.render.symbols as S
    assert S.DOOR_SPOKEN not in (S.DOOR_LOCKED, S.DOOR_H, S.DOOR_V)
    assert S.KEY_SPOKEN != S.KEY
    assert len(S.DOOR_SPOKEN) == len(S.KEY_SPOKEN) == 1


@pytest.mark.parametrize('spoken,opens', [
    ('p1g.sn0ut',  True),
    ('P1G.SN0UT',  True),      # the door hears words, not capitals
    ('p1g',        False),     # `dw` stopped at the punctuation — too little
    ('p1g.sn0ut and the rest', False),   # `d$` swept the row — too much
    ('',           False),
])
def test_only_the_password_opens_it(spoken, opens):
    """The comparison the paste branch makes, asserted at the level of words so
    it is readable: case-blind, whitespace-blind, and blind to nothing else."""
    door = _room_with_door()
    held = clip_to_text(_clip(spoken)) if spoken else ''
    assert bool(held and held.lower() == door.entity_at(2, 10).password.lower()) is opens
