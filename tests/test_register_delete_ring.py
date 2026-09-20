# Vimny — a Vim-teaching dungeon crawler.
# Copyright (C) 2026 Chas Kissick
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""The Register III — The Delete Ring ("0 and "1-"9).

TWO CHAMBERS SAYING THE SAME THING FROM OPPOSITE ENDS.  Upstairs a YANK has to
outlive four deletes that follow it, and only "0 was never touched.  Downstairs
a DELETE has to outlive the two deletes that follow IT, and only the ring keeps
what "" has thrown away.  Between them they say the whole law: the unnamed
register is the one you can lose.

The read is four run seals and nothing else.  Chamber A is run 0 and must read
as the quarry word then the healed saying, which is what forces the spoil rows
to go with no seal of their own; each pedestal is its own run, so a verse line
left un-cut becomes an extra run and reads every pedestal below it false.
"""
import math
import pytest
from blessed.keyboard import Keystroke
from blessed import Terminal

import vimny.game as main
from vimny.content.levels import LEVELS, _BY_SLUG
from vimny.content import proverbs as pv
from vimny.generation.dungeon_gen import (
    build_dungeon_register_delete_ring as _build,
    _R3_PAR, _R3_GATE, _R3_EXIT, _R3_SPAWN, _R3_JUNK, _R3_SAYING,
    _R3_QUARRY_WORD, _R3_QUARRY_ROW, _R3_SPOIL_ROWS, _R3_BAY_ROW,
    _R3_LOOSE_ROWS, _R3_SCRAMBLE, _r3_verse, _r3_ring_slot)
from tests import SEEDS

# The horse rides with the player through the whole Registry wing, and the wing
# only exists once the Warden Eternal has fallen.
_PROGRESS = {'horse_name': 'Artax', 'warden_eternal': {'complete': True}}


def _K(s):
    return [Keystroke(ch) for ch in s]


def _tape(s):
    keys = []
    for tok in s.split():
        keys += _K(tok.replace('<CR>', '\r'))
    return keys


def _drive(keys, monkeypatch, finish=':wq\r', name='Scribe', seed=0,
           progress=None):
    dungeon = _build(seed)
    keys = list(keys) + _K(finish)
    monkeypatch.setattr(main, 'render_all', lambda *a, **k: None)
    monkeypatch.setattr(main.time, 'sleep', lambda *a, **k: None)
    monkeypatch.setattr(main, '_prompt_horse_name', lambda *a, **k: 'Artax')
    for anim in ('_fireworks_animation', '_win_animation', '_starfield_victory',
                 '_heart_container_animation', '_unlock_animation',
                 '_void_fall_animation', '_drown_animation', '_sc_twinkle_animation'):
        monkeypatch.setattr(main, anim, lambda *a, **k: None)
    monkeypatch.setattr(Terminal, 'height', property(lambda self: 41))
    term = Terminal()
    it = iter(keys)
    monkeypatch.setattr(term, 'inkey', lambda *a, **k: next(it, Keystroke('')))
    return main.run_dungeon(term, 'register_delete_ring',
                            dict(_PROGRESS if progress is None else progress),
                            player_name=name, _dungeon=dungeon)


def _drive_spent(keys, monkeypatch, **kw):
    box = {}
    orig = main._calc_stars
    monkeypatch.setattr(main, '_calc_stars',
                        lambda won, budget, room, player, level='':
                            (box.__setitem__('spent', budget.spent),
                             orig(won, budget, room, player, level))[1])
    result = _drive(keys, monkeypatch, **kw)
    return result['won'], box.get('spent')


_PAR_TAPE = _build(0).room.answer


def test_the_authored_tape_solves_the_level_at_two_stars(monkeypatch):
    result = _drive(_tape(_PAR_TAPE), monkeypatch)
    assert result['won'] and result['stars'] == 2, result


def test_par_equals_the_authored_tape(monkeypatch):
    won, spent = _drive_spent(_tape(_PAR_TAPE), monkeypatch)
    assert won and spent == _R3_PAR, (won, spent)


@pytest.mark.parametrize('seed', SEEDS)
def test_par_is_seed_invariant(seed, monkeypatch):
    """The verse is drawn per seed but every line costs one paste, so the tape
    is priced the same whatever the draw — the geometric-draw discipline."""
    won, spent = _drive_spent(_tape(_build(seed).room.answer), monkeypatch,
                              seed=seed)
    assert won and spent == _R3_PAR, (seed, won, spent)


# ── chamber A: the yank that outlives the deletes ────────────────────────────
def test_the_unnamed_register_cannot_heal_the_bay(monkeypatch):
    """THE LESSON, driven: the same tape with `P` in place of `"0P` pastes the
    junk word the `diw` just took, and the bay never reads true."""
    clobbered = _PAR_TAPE.replace('"0P', 'P')
    assert not _drive(_tape(clobbered), monkeypatch)['won']


#: The best chamber-A route for a player who does NOT know "0: protect the
#: yank instead of outliving the deletes — every cut aimed at the black hole so
#: "" is never taken.  It is the same lesson bought at four keys a cut, and the
#: point is that it is a REWARD for knowing "_, not a hole: it still wins.
_RIVAL = ('j w ye j "_3dd $ b "_diw P '
          '2j qq dd q 2@q "1p j j "3p j j "2p G l')


def test_protecting_the_yank_wins_but_drops_a_star(monkeypatch):
    """THE LAW, driven: the "0-free route must pay for the protection on every
    cut — 48 against par 42 — and must still come home.  Forcing is by par,
    never by budget."""
    result = _drive(_tape(_RIVAL), monkeypatch)
    assert result['won'] and result['stars'] == 1, result


def test_the_yank_register_is_strictly_cheaper_than_protecting_the_yank(monkeypatch):
    _w1, ring = _drive_spent(_tape(_PAR_TAPE), monkeypatch)
    _w2, rival = _drive_spent(_tape(_RIVAL), monkeypatch)
    assert _w1 and _w2 and ring < rival, (ring, rival)


def test_typing_the_quarry_word_costs_more_than_pasting_it():
    """The register has to beat the keyboard: `$b cw<word><Esc>` is 4 keys plus
    the word against a flat 8, so the quarry word is LONG on purpose."""
    assert 4 + len(_R3_QUARRY_WORD) > 8, _R3_QUARRY_WORD


def test_the_bay_ends_on_the_junk_word_so_every_route_must_cut():
    """The cut is what puts the unnamed register under fire a fourth time."""
    room = _build(0).room
    assert main._wla_floor_text(room, _R3_BAY_ROW).split()[-1] == _R3_JUNK


# ── chamber B: the ring ──────────────────────────────────────────────────────
def test_one_count_cut_cannot_serve_the_ring(monkeypatch):
    """The asymmetry the par tape is built on, driven.  `3dd` is free money on
    the SPOIL — nobody wants those lines back — but on the scramble it takes all
    three into ONE clip, so the ring holds the scramble rather than the lines
    and the verse comes back in the wrong order, as a block."""
    blocked = _PAR_TAPE.replace('qq dd q 2@q', '3dd')
    assert not _drive(_tape(blocked), monkeypatch)['won']


def test_the_par_tape_golfs_both_cuts_differently():
    """A count on the spoil, a macro on the scramble — the level's own argument
    said in keystrokes.  Pinned so a future tidy-up cannot make them match."""
    assert '3dd' in _PAR_TAPE and 'q' in _PAR_TAPE and '@' in _PAR_TAPE
    assert _PAR_TAPE.count('3dd') == 1


def test_the_pedestals_want_the_verse_in_its_true_order():
    room = _build(0).room
    verse = _r3_verse(0)
    assert [s.match[0] for s in room.seals[1:4]] == list(verse)


def test_the_scramble_puts_no_line_where_it_belongs():
    """If a verse line could be left where it lies, deleting the other two
    would be the whole solve and nothing would ever be pasted."""
    assert all(k != i for i, k in enumerate(_R3_SCRAMBLE)), _R3_SCRAMBLE


def test_the_ring_slots_are_read_off_the_scramble():
    """Cut top-down, the ring counts backwards from the newest cut."""
    assert [_r3_ring_slot(k) for k in range(3)] == [1, 3, 2]
    assert sorted(_r3_ring_slot(k) for k in range(3)) == [1, 2, 3]


def test_only_one_verse_line_is_reachable_without_the_ring(monkeypatch):
    """`""` holds the LAST cut and nothing else.  Driven: swap the two ring
    pastes that are not the newest for plain `p` and the level does not open."""
    newest = '"%dp' % _r3_ring_slot(_R3_SCRAMBLE[-1])
    unringed = ' '.join(tok if (not tok.startswith('"') or tok == newest)
                        else 'p' for tok in _PAR_TAPE.split())
    assert not _drive(_tape(unringed), monkeypatch)['won']


@pytest.mark.parametrize('seed', SEEDS)
def test_a_verse_line_left_uncut_falsifies_every_pedestal(seed, monkeypatch):
    """The run law doing the level's bookkeeping: cut only two of the three and
    the survivor is an extra run, so every index below it names a different
    thing and no pedestal reads true."""
    short = _PAR_TAPE.replace('qq dd q 2@q', 'dd dd')
    assert short != _PAR_TAPE
    assert not _drive(_tape(short), monkeypatch, seed=seed)['won']


# ── the shape of the room ────────────────────────────────────────────────────
@pytest.mark.parametrize('seed', SEEDS)
def test_layout_and_budget(seed):
    room = _build(seed).room
    assert room.par == _R3_PAR
    assert room.budget == math.ceil(_R3_PAR * 1.4)      # STANDARD
    assert main._wla_floor_text(room, _R3_QUARRY_ROW).strip() == _R3_QUARRY_WORD
    assert (main._wla_floor_text(room, _R3_BAY_ROW).strip()
            == ' '.join(_R3_SAYING[:-1] + (_R3_JUNK,)))
    verse = _r3_verse(seed)
    for lrow, k in zip(_R3_LOOSE_ROWS, _R3_SCRAMBLE):
        assert main._wla_floor_text(room, lrow).strip() == verse[k]


def test_the_room_is_open_from_the_spawn():
    """No gates and no fog: both chambers are visible from the door, which is
    what lets the player plan one walk instead of discovering a second."""
    room = _build(0).room
    assert not room.fog_cells
    assert room.spawn_pos == _R3_SPAWN if hasattr(room, 'spawn_pos') else True
    for r in list(_R3_SPOIL_ROWS) + list(_R3_LOOSE_ROWS) + [_R3_BAY_ROW]:
        assert room.cells[r][_R3_EXIT[1]] == main.CellType.FLOOR


def test_the_level_is_registered_in_the_registry_wing():
    lvl = _BY_SLUG['register_delete_ring']
    assert lvl['wing'] == 'registry'
    assert lvl['teaches'] == ['reg_numbered']
    slugs = [l['slug'] for l in LEVELS]
    assert slugs.index('register_delete_ring') > slugs.index('register_named_vault')


def test_the_audit_can_replay_a_saddle_register_tape():
    """The replayer plays a tape against a BLANK save, which for this level is a
    level no player can reach: "0 rides in the horse's saddle and the horse only
    follows a player who has beaten the last Warden and adopted him.  Pinned
    because the failure looks like a broken tape, not a missing companion."""
    from vimny.sharing.replay import replay_tape
    from vimny.content.levels import known_commands, replay_progress
    prog = replay_progress('register_delete_ring')
    assert prog.get('horse_name') and prog['warden_eternal']['complete']
    res = replay_tape(_build(0), 'register_delete_ring', _PAR_TAPE,
                      known=known_commands('register_delete_ring'),
                      progress=prog)
    assert res.won and res.spent == _R3_PAR, res


def test_the_wings_horseless_levels_keep_the_blank_save():
    """Their routes were authored with no horse standing in the room, and he is
    an obstacle like any other — so only a SADDLE lesson asks for him."""
    from vimny.content.levels import replay_progress
    assert replay_progress('register_unnamed_hold') == {}
    assert replay_progress('register_named_vault') == {}
    assert replay_progress('first_cave') == {}


def test_the_level_is_marked_unplayed():
    """Green is not played. Every claim this file makes is a claim about the
    tape; whether the verse reads as a cue, whether the two chambers land as one
    lesson, and whether the walk feels like one walk are things only a person
    can answer. The marker comes off when someone has actually sat with it."""
    from vimny.content.levels import playtest_pending
    pending = playtest_pending()
    assert 'register_delete_ring' in pending, (
        'clear the playtest key only when the level has been PLAYED — and fix '
        'whatever the play turned up in the same commit')
    assert set(pending) <= {l['slug'] for l in LEVELS}, pending


def test_the_verse_is_drawn_from_the_stanza_pool():
    verse = _r3_verse(0)
    assert any(tuple(s[:3]) == verse for s in pv.STANZAS), verse
