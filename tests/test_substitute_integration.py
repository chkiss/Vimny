"""End-to-end :s / :g / & through the real run_dungeon loop: undo, the c (confirm)
flag, :v / :g! inversion, and budget. Driven on plain custom rooms (admin player)."""
import pytest
from blessed import Terminal
from blessed.keyboard import Keystroke

import main
import engine.substitute as S
from engine.world import Dungeon, Room, RoomType, CharRun, CellType


def _ks(c, name=None):
    return Keystroke(c, name=name)


def _dungeon(lines, cols=None):
    rows = len(lines)
    cols = cols or max(len(l) for l in lines) + 6
    d = Dungeon(name='t', seed=1)
    r = Room(room_type=RoomType.ENTRY, rows=rows, cols=cols)
    r.cells = [[CellType.FLOOR] * cols for _ in range(rows)]
    runs = []
    for ri, ln in enumerate(lines):
        for ci, ch in enumerate(ln):
            if ch != ' ':
                runs.append(CharRun(ri, ci, (ch,), 'ancient'))
    r.char_runs = runs
    r.spawn_pos = (0, 0); r.budget = 999; r.par = 5; r.answer = ''
    r.rebuild_indexes(); d.rooms = [r]; d.current_room = 0
    return d


def _run(d, keys):
    term = Terminal(force_styling=False)
    it = iter([_ks(c) for c in keys])
    term.inkey = lambda *a, **k: next(it, _ks(''))
    spent = {}
    main.render_all = lambda t, dn, pl, bg, message='', *a, **k: spent.update(v=bg.spent)
    main.run_dungeon(term, 'spellwrights_forge', {}, player_name='admin', _dungeon=d)
    return [S.line_text(d.room, r)[0] for r in range(d.room.rows)], spent.get('v')


def test_substitute_is_undoable():
    d = _dungeon(['foo foo'])
    lines, _ = _run(d, list(':s/foo/X/g') + ['\r'] + ['u'] + list(':q!') + ['\r'])
    assert lines == ['foo foo']                     # u restored the line


def test_substitute_charges_budget():
    d = _dungeon(['foo'])
    _lines, spent = _run(d, list(':s/foo/bar/') + ['\r'] + list(':q!') + ['\r'])
    assert spent == len(':s/foo/bar/')              # len(cmd)+1 (the ':' counts)


def test_confirm_flag_picks_matches():
    d = _dungeon(['old old old'])
    # :s/old/new/gc → confirm y, n, y  →  new old new
    keys = list(':s/old/new/gc') + ['\r'] + ['y', 'n', 'y'] + list(':q!') + ['\r']
    lines, _ = _run(d, keys)
    assert lines == ['new old new']


def test_confirm_quit_stops():
    d = _dungeon(['old old old'])
    keys = list(':s/old/new/gc') + ['\r'] + ['y', 'q'] + list(':q!') + ['\r']
    lines, _ = _run(d, keys)
    assert lines == ['new old old']                 # first replaced, then q halts


def test_v_inverts_global():
    d = _dungeon(['keep me', 'drop', 'keep me', 'drop'])
    lines, _ = _run(d, list(':v/keep/d') + ['\r'] + list(':q!') + ['\r'])
    assert lines == ['keep me', 'keep me']


def test_g_bang_inverts_global():
    d = _dungeon(['hit', 'miss', 'hit'])
    lines, _ = _run(d, list(':g!/hit/d') + ['\r'] + list(':q!') + ['\r'])
    assert lines == ['hit', 'hit']


def test_global_substitute_end_to_end():
    d = _dungeon(['a x', 'b y', 'a z'])
    lines, _ = _run(d, list(':g/a/s/ /-/') + ['\r'] + list(':q!') + ['\r'])
    assert lines == ['a-x', 'b y', 'a-z']
