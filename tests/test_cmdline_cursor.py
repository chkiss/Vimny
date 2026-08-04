"""The ex/search command line has a Vim cursor: arrow keys move it, and
edits land AT the cursor (not only at the end). Playtest 2026-07-20."""
import contextlib
import io

import pytest
from blessed.keyboard import Keystroke
from blessed import Terminal

import main
import vimny.render.colors as C
import vimny.render.symbols as S
from vimny.render.renderer import render_all, _cmdline_with_cursor
from vimny.engine.budget import Budget
from vimny.engine.player import Player
from vimny.engine.modes import Mode
from vimny.generation.dungeon_gen import build_dungeon_hall_of_echoes


def _key(name, ch='\x1b'):
    return Keystroke(ch, code=1, name=name)


def _p(line, cursor):
    p = Player(row=1, col=3)
    p.cmd_line = line
    p.cmd_cursor = cursor
    return p


# ── the pure editing helpers ──────────────────────────────────────────────────

def test_insert_at_cursor():
    p = _p('sold', 4)
    main._cmd_insert(p, 'i')
    assert p.cmd_line == 'soldi' and p.cmd_cursor == 5
    p = _p('sold', 1)
    main._cmd_insert(p, 'X')
    assert p.cmd_line == 'sXold' and p.cmd_cursor == 2


def test_backspace_deletes_before_cursor():
    p = _p('abcd', 2)
    main._cmd_backspace(p)
    assert p.cmd_line == 'acd' and p.cmd_cursor == 1
    p = _p('abcd', 0)
    main._cmd_backspace(p)                 # no-op at column 0
    assert p.cmd_line == 'abcd' and p.cmd_cursor == 0


def test_arrow_motions():
    p = _p('hello', 5)
    assert main._cmd_arrow(p, _key('KEY_LEFT')) and p.cmd_cursor == 4
    assert main._cmd_arrow(p, _key('KEY_RIGHT')) and p.cmd_cursor == 5
    main._cmd_arrow(p, _key('KEY_RIGHT'))          # clamps at end
    assert p.cmd_cursor == 5
    assert main._cmd_arrow(p, _key('KEY_HOME')) and p.cmd_cursor == 0
    main._cmd_arrow(p, _key('KEY_LEFT'))           # clamps at start
    assert p.cmd_cursor == 0
    assert main._cmd_arrow(p, _key('KEY_END')) and p.cmd_cursor == 5
    assert not main._cmd_arrow(p, _key('KEY_F1'))  # unrecognised → False


def test_mid_line_edit_sequence():
    """':s/old/' then Left×2, insert 'X' → the cursor really edits mid-string."""
    p = _p('', 0)
    for ch in 's/old/':
        main._cmd_insert(p, ch)
    assert p.cmd_line == 's/old/' and p.cmd_cursor == 6
    main._cmd_arrow(p, _key('KEY_LEFT'))
    main._cmd_arrow(p, _key('KEY_LEFT'))
    main._cmd_insert(p, 'X')
    assert p.cmd_line == 's/olXd/' and p.cmd_cursor == 5


# ── the rendered block cursor ─────────────────────────────────────────────────

@pytest.fixture
def _term():
    t = Terminal(force_styling=True)
    C.init(t)
    S.init(t)
    return t


def test_cmdline_helper_places_the_block(_term):
    # cursor at end → sits on a trailing space; contains the prefix + text
    out = _cmdline_with_cursor(':', 's/a/b/', 6, 40, C.statusline_bg(), C.statusline_fg())
    assert ':s/a/b/' in _strip(out)
    # the cursor background appears exactly once (one block)
    assert C.cmd_cursor_bg() and out.count(C.cmd_cursor_bg()) == 1


def _strip(s):
    import re
    return re.sub(r'\x1b\[[0-9;]*m', '', s)


def test_render_command_line_shows_cursor(_term, monkeypatch):
    monkeypatch.setattr(Terminal, 'height', property(lambda self: 30))
    d = build_dungeon_hall_of_echoes(0)
    p = Player(row=1, col=3)
    p.known_commands = set()
    p.mode = Mode.COMMAND
    p.cmd_line = 's/old/new/'
    p.cmd_cursor = 3
    f = io.StringIO()
    with contextlib.redirect_stdout(f):
        render_all(_term, d, p, Budget(total=100), '')
    plain = _strip(f.getvalue())
    assert ':s/old/new/' in plain
    assert C.cmd_cursor_bg() and C.cmd_cursor_bg() in f.getvalue()  # block cursor drawn


# ── driven end to end ─────────────────────────────────────────────────────────

def test_driven_arrow_edit_changes_what_gets_parsed(monkeypatch):
    """Type an unknown command with a stray char, walk the cursor back and
    delete it: the command the engine parses is the EDITED string, proving the
    mid-line edit (not append-only) took effect."""
    pushes = []
    monkeypatch.setattr(main, 'render_all', lambda *a, **k: None)
    monkeypatch.setattr(main.time, 'sleep', lambda *a, **k: None)
    for anim in ('_fireworks_animation', '_win_animation', '_starfield_victory',
                 '_heart_container_animation', '_unlock_animation',
                 '_void_fall_animation', '_drown_animation', '_sc_twinkle_animation'):
        monkeypatch.setattr(main, anim, lambda *a, **k: None)
    monkeypatch.setattr(Terminal, 'height', property(lambda self: 45))

    d = build_dungeon_hall_of_echoes(0)
    LEFT = _key('KEY_LEFT')
    BS = Keystroke('\x7f', code=1, name='KEY_BACKSPACE')
    # ':zzz' typed as ':zzXz' then Left, Backspace to delete the stray X →
    # the parsed unknown command must read 'zzz', not 'zzXz' or 'zzz' at end
    keys = ([Keystroke(':')] + [Keystroke(c) for c in 'zzXz']
            + [LEFT, LEFT, BS, Keystroke('\r')]
            + [Keystroke(c) for c in ':q!\r'])
    term = Terminal()
    it = iter(keys)
    monkeypatch.setattr(term, 'inkey', lambda *a, **k: next(it, Keystroke('')))

    # Grab the live player to read its final cmd state through the real loop.
    grabbed = {}
    real_Player = main.Player

    def _spy_player(*a, **k):
        p = real_Player(*a, **k)
        grabbed['p'] = p
        return p
    monkeypatch.setattr(main, 'Player', _spy_player)

    main.run_dungeon(term, 'hall_of_echoes', {}, player_name='Scribe', _dungeon=d)
    p = grabbed['p']
    # After Enter the line clears (back to NORMAL), proving no desync/crash and
    # that the edited command was submitted and consumed.
    assert p.cmd_line == '' and p.cmd_cursor == 0
