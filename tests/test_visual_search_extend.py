"""Search as a visual-mode motion: `v` then `/pattern<enter>` extends the selection
to the match (Vim's search-as-motion), staying in visual mode with the anchor fixed.

Driven through the real run_dungeon keystroke loop on a tiny hand-built dungeon, with
render_all patched to snapshot (mode, cursor, anchor) every frame."""
import pytest
from blessed.keyboard import Keystroke
from blessed import Terminal

import main
from engine.world import Dungeon, Room, RoomType, CellType, CharRun
from engine.modes import Mode


def _ks(ch, name=None):
    return Keystroke(ch, name=name)


# v · /cipher<enter> · Esc · :q<enter>
_SCRIPT = ([_ks('v'), _ks('/')] + [_ks(c) for c in 'cipher'] + [_ks('\r')]
           + [_ks('\x1b', name='KEY_ESCAPE'), _ks(':'), _ks('q'), _ks('\r')])


def _tiny_dungeon():
    room = Room(rows=5, cols=20, room_type=RoomType.ENTRY)
    room.cells = [[CellType.WALL] * 20 for _ in range(5)]
    for c in range(1, 19):
        room.cells[2][c] = CellType.CORRIDOR
    room.spawn_pos = (2, 2)
    room.exit_pos  = (2, 18)
    room.char_runs = [CharRun(row=2, col=10, symbols=tuple('cipher'), kind='ember')]
    room.par, room.budget, room.answer = 10, 40, ''
    room.rebuild_indexes()
    d = Dungeon(name='Test', seed=1)
    d.rooms, d.current_room = [room], 0
    return d


def test_visual_slash_search_extends_selection(monkeypatch):
    snaps = []

    def _capture(term, dungeon, player, budget, *a, **k):
        snaps.append((player.mode, (player.row, player.col), player.visual_anchor))

    monkeypatch.setattr(main, 'render_all', _capture)

    term = Terminal()
    it = iter(_SCRIPT)
    monkeypatch.setattr(term, 'inkey', lambda *a, **k: next(it, _ks('')))

    main.run_dungeon(term, 'dummy', {}, player_name='admin', _dungeon=_tiny_dungeon())

    # plain visual: anchor and cursor both at spawn (the selection is a single cell)
    assert (Mode.VISUAL, (2, 2), (2, 2)) in snaps
    # after /cipher<enter>: still VISUAL, anchor fixed at spawn, cursor ON the match
    # → the selection now spans spawn..match
    assert (Mode.VISUAL, (2, 10), (2, 2)) in snaps


def test_backward_question_search_also_extends(monkeypatch):
    """`?` from the right edge walks the selection back onto the match."""
    snaps = []
    monkeypatch.setattr(main, 'render_all',
                        lambda term, d, p, b, *a, **k: snaps.append((p.mode, (p.row, p.col), p.visual_anchor)))
    d = _tiny_dungeon()
    d.room.spawn_pos = (2, 17)                     # start right of the word
    term = Terminal()
    script = ([_ks('v'), _ks('?')] + [_ks(c) for c in 'cipher'] + [_ks('\r')]
              + [_ks('\x1b', name='KEY_ESCAPE'), _ks(':'), _ks('q'), _ks('\r')])
    it = iter(script)
    monkeypatch.setattr(term, 'inkey', lambda *a, **k: next(it, _ks('')))

    main.run_dungeon(term, 'dummy', {}, player_name='admin', _dungeon=d)

    assert (Mode.VISUAL, (2, 10), (2, 17)) in snaps   # cursor back on the match, anchor fixed
