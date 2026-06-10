"""The Mark Setter — probes m{a-z} / '{a-z} / `{a-z} edge cases.

Personality defined in agents/bug_testers.md. Marks are handled in run_dungeon, so
these drive the real keystroke loop (admin player bypasses gating) and inspect the
captured Player: the marks dict, exact (`) vs first-non-blank (') jumps, unset
marks, and the jumplist interaction.
"""
from blessed import Terminal
from blessed.keyboard import Keystroke

import main
from engine.world import Dungeon, Room, RoomType, CharRun, CellType, Entity


def _ks(c, name=None):
    return Keystroke(c, name=name)


def _dungeon(spawn=(2, 1), word_at=(2, 5), word='word', rows=5, cols=30):
    d = Dungeon(name='t', seed=1)
    r = Room(room_type=RoomType.ENTRY, rows=rows, cols=cols)
    r.cells = [[CellType.FLOOR if (0 < rr < rows - 1 and 0 < cc < cols - 1) else CellType.WALL
                for cc in range(cols)] for rr in range(rows)]
    if word:
        r.add_char_run(CharRun(word_at[0], word_at[1], tuple(word), 'ancient'))
    r.entities = [Entity(kind='exit', row=rows - 2, col=cols - 2)]
    r.exit_pos = (rows - 2, cols - 2)
    r.spawn_pos = spawn
    r.budget = 999
    r.par = 5
    r.answer = ''
    r.rebuild_indexes()
    d.rooms = [r]
    d.current_room = 0
    return d


def _play(d, keys):
    """Run keys through run_dungeon (admin); return the captured Player + messages."""
    term = Terminal(force_styling=False)
    it = iter([_ks(c) for c in keys] + [_ks(':'), _ks('q'), _ks('!'), _ks('\r')])
    term.inkey = lambda *a, **k: next(it, _ks(''))
    grab = {}
    msgs = []

    def cap(t, dn, pl, bg, message='', *a, **k):
        grab['player'] = pl
        if message:
            msgs.append(message)

    main.render_all = cap
    main.run_dungeon(term, 'waypoint_sanctum', {}, player_name='admin', _dungeon=d)
    return grab['player'], msgs


# ── m populates the marks dict ────────────────────────────────────────────────
def test_m_sets_a_mark_at_the_cursor():
    d = _dungeon(spawn=(2, 1))
    p, _ = _play(d, ['m', 'a'])
    assert p.marks.get('a') == (2, 1)


def test_two_marks_are_independent():
    d = _dungeon(spawn=(2, 1))
    # ma at (2,1); move right 4; mb at (2,5); then jump each.
    p, _ = _play(d, ['m', 'a'] + ['l'] * 4 + ['m', 'b'])
    assert p.marks.get('a') == (2, 1)
    assert p.marks.get('b') == (2, 5)


# ── ` jumps to the EXACT position; ' to first-non-blank of the row ────────────
def test_backtick_returns_to_exact_column():
    d = _dungeon(spawn=(2, 1))
    p, _ = _play(d, ['l'] * 9 + ['m', 'a'] + ['0'] + ['`', 'a'])
    assert (p.row, p.col) == (2, 10)


def test_apostrophe_lands_on_first_non_blank():
    # mark made at col 10 on row 2; 'a must land on the row's first glyph (col 5).
    d = _dungeon(spawn=(2, 1), word_at=(2, 5), word='word')
    p, _ = _play(d, ['l'] * 9 + ['m', 'a'] + ['0'] + ["'", 'a'])
    assert (p.row, p.col) == (2, 5)


# ── unset / bad marks are no-ops ──────────────────────────────────────────────
def test_jump_to_unset_mark_does_not_move():
    d = _dungeon(spawn=(2, 3))
    p, msgs = _play(d, ['`', 'z'])
    assert (p.row, p.col) == (2, 3)
    assert any("not set" in m for m in msgs)


def test_apostrophe_to_unset_mark_does_not_move():
    d = _dungeon(spawn=(2, 3))
    p, _ = _play(d, ["'", 'q'])
    assert (p.row, p.col) == (2, 3)


# ── a mark jump records the jumplist (Ctrl-o returns) ─────────────────────────
def test_mark_jump_records_jumplist_for_ctrl_o():
    d = _dungeon(spawn=(2, 1))
    # set mark at col 10, return to col 1, jump to the mark, then Ctrl-o back.
    p, _ = _play(d, ['l'] * 9 + ['m', 'a'] + ['0'] + ['`', 'a'] + ['\x0f'])
    assert (p.row, p.col) == (2, 1), "Ctrl-o should return to the pre-jump position"


# ── re-setting a mark overwrites it ───────────────────────────────────────────
def test_resetting_a_mark_overwrites_the_old_position():
    d = _dungeon(spawn=(2, 1))
    p, _ = _play(d, ['m', 'a'] + ['l'] * 5 + ['m', 'a'])
    assert p.marks.get('a') == (2, 6)
