"""Unit tests for engine.substitute._sub_line_confirm — the per-match confirm
state machine (y / n / q / a / l). These pin the answer-flow behaviour so the
shared-core refactor of _sub_line / _sub_line_confirm can't regress it.

The function works on plain (text, kinds) and a compiled pattern — no Room."""
from engine.substitute import _sub_line_confirm, _sub_line
from engine.vimregex import compile_sub


def _answers(seq):
    """A confirm(row, col_start, col_end) that yields the given answers in order."""
    it = iter(seq)
    return lambda *a: next(it)


def _run_confirm(text, pattern, rep, answers, glob=True):
    vp = compile_sub(pattern, None)
    kinds = ['ember'] * len(text)
    return _sub_line_confirm(text, kinds, 'ember', vp, rep, glob,
                             _answers(answers), row=0, lo=0)


def test_confirm_y_n_y():
    new, _kinds, n = _run_confirm('old old old', 'old', 'new', ['y', 'n', 'y'])
    assert new == 'new old new' and n == 2


def test_confirm_quit_after_first():
    new, _kinds, n = _run_confirm('old old old', 'old', 'new', ['y', 'q'])
    assert new == 'new old old' and n == 1


def test_confirm_all_replaces_rest():
    new, _kinds, n = _run_confirm('old old old', 'old', 'new', ['a'])
    assert new == 'new new new' and n == 3


def test_confirm_last_does_one_then_stops():
    new, _kinds, n = _run_confirm('old old old', 'old', 'new', ['l'])
    assert new == 'new old old' and n == 1


def test_confirm_n_then_last():
    new, _kinds, n = _run_confirm('old old old', 'old', 'new', ['n', 'l'])
    assert new == 'old new old' and n == 1


def test_confirm_nonglobal_first_match_only():
    # glob=False: only the first match is ever offered.
    new, _kinds, n = _run_confirm('old old', 'old', 'new', ['y'], glob=False)
    assert new == 'new old' and n == 1


def test_confirm_no_match_leaves_text():
    new, _kinds, n = _run_confirm('abc abc', 'xyz', 'new', [])
    assert new == 'abc abc' and n == 0


def test_confirm_kinds_take_default_on_replacement():
    vp = compile_sub('o', None)
    text = 'oo'
    kinds = ['ancient', 'verdant']
    new, new_kinds, n = _sub_line_confirm(text, kinds, 'ember', vp, 'X', True,
                                          _answers(['y', 'n']), row=0, lo=0)
    assert new == 'Xo' and n == 1
    # first char replaced → default kind; second kept its original kind
    assert new_kinds == ['ember', 'verdant']


def test_sub_line_plain_global_and_count():
    vp = compile_sub('old', None)
    text = 'old old'
    kinds = ['ember'] * len(text)
    new, _k, n = _sub_line(text, kinds, 'ember', vp, 'new', True, False)
    assert new == 'new new' and n == 2
    # count_only keeps the text but still reports the match count
    same, _k2, cnt = _sub_line(text, kinds, 'ember', vp, 'new', True, True)
    assert same == text and cnt == 2
