"""The too-small terminal guard (`render.utils.print_size_notice`).

Below 80x24 an 80-column frame wraps into garbage, so every frame-flush site
bails into a plain notice instead. These tests pin the guard's decision table
(fail-open on unknown sizes, pass at exactly minimum, cramped one-line mode)
and one end-to-end run proving the dungeon loop paints the notice rather than
a wrapping frame.
"""
import pytest
from blessed import Terminal
from blessed.keyboard import Keystroke

import vimny.generation.dungeon_gen as dg
import vimny.game as main
import vimny.save.save_manager as SM
from vimny.render import colors
from vimny.render import symbols as S
from vimny.render.renderer import render_all
from vimny.render.utils import MIN_COLS, MIN_ROWS, print_size_notice


class _T:
    """Blessed-free stand-in: just the attributes the guard touches."""
    home = ''
    clear = ''

    def __init__(self, w, h):
        self.width, self.height = w, h


def test_big_enough_is_silent(capsys):
    assert print_size_notice(_T(100, 30)) is False
    assert capsys.readouterr().out == ''


def test_exactly_minimum_passes():
    assert (_T(MIN_COLS, MIN_ROWS)) and \
        print_size_notice(_T(MIN_COLS, MIN_ROWS)) is False


def test_narrow_reports_one_line(capsys):
    # 57 cols can't hold even the notice box -> cramped single-line mode.
    assert print_size_notice(_T(57, 24)) is True
    out = capsys.readouterr().out
    assert f'{MIN_COLS}x{MIN_ROWS}' in out
    assert all(len(line) <= 57 for line in out.splitlines())


def test_short_but_wide_gets_box(capsys):
    assert print_size_notice(_T(100, 10)) is True
    out = capsys.readouterr().out
    assert S.BOX_TL in out and f'{MIN_COLS}x{MIN_ROWS}' in out
    assert all(len(line) <= 100 for line in out.splitlines())


@pytest.mark.parametrize('w,h', [(None, None), (None, 30), (80, None)])
def test_unknown_size_fails_open(w, h, capsys):
    t = _T(w, h)
    assert print_size_notice(t) is False
    assert capsys.readouterr().out == ''


def test_missing_attrs_fails_open(capsys):
    assert print_size_notice(object()) is False   # getattr default None
    assert capsys.readouterr().out == ''


def test_dungeon_loop_paints_notice_not_frame(monkeypatch, capsys):
    """End to end at 57x20: the frame-flush path shows the size notice and
    never emits an 80-column border line that would wrap."""
    monkeypatch.setattr(main.time, 'sleep', lambda *a, **k: None)
    monkeypatch.setattr(SM, 'save_progress', lambda *a, **k: None)
    term = Terminal(force_styling=False)
    colors.init(term)
    # Class-level properties, reverted by monkeypatch: leaving these set
    # would poison every later test that renders through blessed.
    monkeypatch.setattr(Terminal, 'height', property(lambda self: 20))
    monkeypatch.setattr(Terminal, 'width', property(lambda self: 57))
    keys = [Keystroke(c) for c in 'j'] + [Keystroke(c) for c in ':q!\r']
    it = iter(keys)
    monkeypatch.setattr(term, 'inkey', lambda *a, **k: next(it, Keystroke('')))

    d = dg.build_dungeon_first_cave(0)
    main.run_dungeon(term, 'first_cave', {}, player_name='Tester', _dungeon=d)

    out = capsys.readouterr().out
    assert f'{MIN_COLS}x{MIN_ROWS}' in out
    assert S.BOX_TL + S.BOX_H * 78 not in out   # no unwrappable 80-wide frame


def test_utf8_stdout_guard(monkeypatch, capsys):
    """main() forces UTF-8 onto an ASCII-codec stdout (C-locale boxes would
    otherwise die on the first dungeon glyph)."""
    import io
    import vimny.game as game

    class AsciiStream(io.StringIO):
        encoding = 'ansi_x3.4-1968'

        def reconfigure(self, **kw):
            self.encoding = kw.get('encoding', self.encoding)

    out, err = AsciiStream(), AsciiStream()
    monkeypatch.setattr(game.sys, 'stdout', out)
    monkeypatch.setattr(game.sys, 'stderr', err)
    game._ensure_utf8_stdout()
    assert out.encoding == 'utf-8'
    assert err.encoding == 'utf-8'

    # Already-UTF-8 streams are left untouched (no reconfigure call).
    class Utf8Stream(AsciiStream):
        encoding = 'utf-8'
    fine = Utf8Stream()
    monkeypatch.setattr(game.sys, 'stdout', fine)
    game._ensure_utf8_stdout()
    assert fine.encoding == 'utf-8'
