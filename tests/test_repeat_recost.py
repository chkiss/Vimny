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

"""Anti-exploit: a find/search establishes a cheap repeat register (;/, and n/N), and
undo refunds the establishing motion. Without accounting, `fx` (2) → `u` (−2) → `;` (1)
would reach the target for 1 budget. We tag the establishing motion's undo entry so that
undoing it arms a re-cost: the next repeat re-pays the full original cost. Legitimate
flows (repeat after a paid find, undo of a discounted repeat, redo) are unaffected.

Driven through the real run_dungeon keystroke loop on a hand-built one-line room.
"""
from blessed import Terminal
from blessed.keyboard import Keystroke

import main
from engine.world import Dungeon, Room, RoomType, CharRun, CellType


def _ks(c, name=None):
    return Keystroke(c, name=name)


def _build():
    """A 1×40 floor with two 'z' targets (cols 20 and 30); spawn at col 0."""
    d = Dungeon(name='T', seed=1)
    r = Room(room_type=RoomType.ENTRY, rows=1, cols=40)
    r.cells     = [[CellType.FLOOR] * 40]
    r.char_runs = [CharRun(0, 20, tuple('z'), 'ancient'),
                   CharRun(0, 30, tuple('z'), 'ancient')]
    r.spawn_pos = (0, 0)
    r.budget    = 999
    r.par       = 5
    r.answer    = ''
    r.rebuild_indexes()
    d.rooms = [r]
    d.current_room = 0
    return d


def _play(keys):
    """Run the keys (slug seekers_labyrinth → f/;/,/N/n/* all known); return (spent, col)."""
    d = _build()
    term = Terminal(force_styling=False)
    it = iter(list(keys) + [_ks(':'), _ks('q'), _ks('!'), _ks('\r')])
    term.inkey = lambda *a, **k: next(it, _ks(''))
    seen = {}

    def cap(term, dungeon, player, budget, message='', *a, **k):
        seen['spent'] = budget.spent
        seen['col']   = player.col

    main.render_all = cap
    main.run_dungeon(term, 'seekers_labyrinth', {}, player_name='admin', _dungeon=d)
    return seen.get('spent'), seen.get('col')


# ── find: ; / , ──────────────────────────────────────────────────────────────
def test_find_costs_two():
    assert _play([_ks('f'), _ks('z')]) == (2, 20)        # f{char} = 2 keystrokes


def test_undo_then_repeat_repays_full_find_cost():
    # The exploit: fx → u → ;  must cost 2 (re-pay), not 1.
    assert _play([_ks('f'), _ks('z'), _ks('u'), _ks(';')]) == (2, 20)


def test_legit_repeat_after_paid_find_is_one():
    # fz (2) then ; (1) to the second 'z' — the discount is intact for honest play.
    assert _play([_ks('f'), _ks('z'), _ks(';')]) == (3, 30)


def test_undoing_a_discounted_repeat_does_not_arm():
    # fz, ;, ;(no-op), u(undo the paid ;), ; — the find is still paid, so ; stays 1.
    assert _play([_ks('f'), _ks('z'), _ks(';'), _ks(';'),
                  _ks('u'), _ks(';')]) == (3, 30)


def test_redo_reclears_the_arm():
    # fz, u (arm), <C-r> (re-apply find, clear arm), ; (discounted) → 2 + 1 = 3.
    assert _play([_ks('f'), _ks('z'), _ks('u'),
                  _ks('\x12'), _ks(';')]) == (3, 30)


# ── search: n / N ────────────────────────────────────────────────────────────
def test_search_costs_pattern_plus_one():
    # '/' charged + len(pat) chars, closing Enter free → len('z') + 1 = 2
    assert _play([_ks('/'), _ks('z'), _ks('\r')]) == (2, 20)


def test_undo_then_n_repays_full_search_cost():
    # /z⏎ → u → n  must cost the full 2 (re-pay), not 1.
    assert _play([_ks('/'), _ks('z'), _ks('\r'), _ks('u'), _ks('n')]) == (2, 20)


def test_legit_n_after_paid_search_is_one():
    # /z⏎ (2) + n (1) = 3
    assert _play([_ks('/'), _ks('z'), _ks('\r'), _ks('n')]) == (3, 30)


def test_find_and_search_arms_are_independent():
    # A search undone arms only n/N; a following f{char} still costs its own 2.
    assert _play([_ks('/'), _ks('z'), _ks('\r'), _ks('u'),
                  _ks('f'), _ks('z')]) == (2, 20)


# ── cut (x): undo must restore the deleted character, not just refund ─────────
def _play_edit(keys):
    """Spawn ON a 5-char run ('abcde' at col 5) so x cuts it; slug echo_vault knows x and `.`.
    Returns (spent, lettering-of-the-run)."""
    d = Dungeon(name='T', seed=1)
    r = Room(room_type=RoomType.ENTRY, rows=1, cols=40)
    r.cells     = [[CellType.FLOOR] * 40]
    r.char_runs = [CharRun(0, 5, tuple('abcde'), 'ancient')]
    r.spawn_pos = (0, 5)
    r.budget    = 999
    r.par       = 5
    r.answer    = ''
    r.rebuild_indexes()
    d.rooms = [r]
    d.current_room = 0
    term = Terminal(force_styling=False)
    it = iter(list(keys) + [_ks(':'), _ks('q'), _ks('!'), _ks('\r')])
    term.inkey = lambda *a, **k: next(it, _ks(''))
    seen = {}

    def cap(term, dungeon, player, budget, message='', *a, **k):
        seen['spent'] = budget.spent

    main.render_all = cap
    main.run_dungeon(term, 'echo_vault', {}, player_name='admin', _dungeon=d)
    line = ''.join(''.join(ru.symbols) for ru in d.rooms[0].char_runs)
    return seen['spent'], line


def test_cut_then_undo_restores_the_character_and_refunds():
    # Regression: the cut snapshot was taken AFTER _ed_cut mutated, so 'u' refunded the
    # keystroke but left the character deleted (a free delete). Undo must restore it.
    assert _play_edit([_ks('x')])              == (1, 'bcde')
    assert _play_edit([_ks('x'), _ks('u')])    == (0, 'abcde')


def test_no_free_delete_via_undo():
    # x, u, x (or x, u, .) re-deletes for a full keystroke each — never 0.
    assert _play_edit([_ks('x'), _ks('u'), _ks('x')]) == (1, 'bcde')
    assert _play_edit([_ks('x'), _ks('u'), _ks('.')]) == (1, 'bcde')


def test_cut_redo_reapplies_the_delete():
    assert _play_edit([_ks('x'), _ks('u'), _ks('\x12')]) == (1, 'bcde')


# ── '.' (repeat change): one keystroke, but no undo-refund cheat ──────────────
def _play_dot(keys):
    """Four words ('aaa' 'bbb' 'ccc' 'ddd') spawned on the first; slug echo_vault knows
    d/w and `.`. dw costs 2 (a real >1 change). Returns (spent, remaining-letters)."""
    d = Dungeon(name='T', seed=1)
    r = Room(room_type=RoomType.ENTRY, rows=1, cols=60)
    r.cells     = [[CellType.FLOOR] * 60]
    r.char_runs = [CharRun(0, 5,  tuple('aaa'), 'ancient'),
                   CharRun(0, 10, tuple('bbb'), 'ancient'),
                   CharRun(0, 15, tuple('ccc'), 'ancient'),
                   CharRun(0, 20, tuple('ddd'), 'ancient')]
    r.spawn_pos = (0, 5)
    r.budget    = 999
    r.par       = 5
    r.answer    = ''
    r.rebuild_indexes()
    d.rooms = [r]
    d.current_room = 0
    term = Terminal(force_styling=False)
    it = iter(list(keys) + [_ks(':'), _ks('q'), _ks('!'), _ks('\r')])
    term.inkey = lambda *a, **k: next(it, _ks(''))
    seen = {}

    def cap(term, dungeon, player, budget, message='', *a, **k):
        seen['spent'] = budget.spent

    main.render_all = cap
    main.run_dungeon(term, 'echo_vault', {}, player_name='admin', _dungeon=d)
    line = ''.join(''.join(ru.symbols) for ru in d.rooms[0].char_runs)
    return seen['spent'], line


def test_dw_costs_two():
    assert _play_dot([_ks('d'), _ks('w')]) == (2, 'bbbcccddd')


def test_dot_repeats_a_change_for_one_keystroke():
    # dw (2) then . (1, not another 2) → 3 total; the dot's efficiency is rewarded.
    assert _play_dot([_ks('d'), _ks('w'), _ks('.')]) == (3, 'cccddd')
    assert _play_dot([_ks('d'), _ks('w'), _ks('.'), _ks('.')]) == (4, 'ddd')


def test_undo_then_dot_repays_full_change_cost():
    # The cheat: dw → u → . must re-pay the full 2, not the dot's 1.
    assert _play_dot([_ks('d'), _ks('w'), _ks('u'), _ks('.')]) == (2, 'bbbcccddd')


def test_undo_of_a_dot_rearms_its_own_cost():
    # dw(2) . (1) u(undo dot, arms 1) . (re-pays 1) → 3.
    assert _play_dot([_ks('d'), _ks('w'), _ks('.'),
                      _ks('u'), _ks('.')]) == (3, 'cccddd')


def test_redo_clears_the_change_arm():
    # dw u <C-r>(re-applies dw, clears arm) . (back to the 1-key discount) → 3.
    assert _play_dot([_ks('d'), _ks('w'), _ks('u'),
                      _ks('\x12'), _ks('.')]) == (3, 'cccddd')
