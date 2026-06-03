"""The Archivist's Library (L17): one-line wrap_buffer + the :e!/:w reload loop and
the lethal-Archivist reckoning, driven through the real run_dungeon keystroke loop.

The suit order is seeded, so each test reads room.lib_seq to build its keystroke
script (which name to :w at which manuscript) rather than hard-coding the order.
"""
import pytest
from blessed.keyboard import Keystroke
from blessed import Terminal

import main
import generation.dungeon_gen as dg


def _ks(ch, name=None):
    return Keystroke(ch, name=name)


def _type(s):
    """A list of Keystrokes spelling out s (used for command-line text)."""
    return [_ks(c) for c in s]


def _cmd(s):
    """':' + text + Enter."""
    return [_ks(':')] + _type(s) + [_ks('\r')]


SEED = 42


def _dungeon():
    return dg.build_dungeon_archivists_library(SEED)


def _suit_slots(d):
    """Map suit-name -> the sequence index whose folio is that suit."""
    return {item['suit']: i for i, item in enumerate(d.room.lib_seq) if item['suit']}


# ── builder structure ───────────────────────────────────────────────────────
def test_archivist_is_findable_by_f():
    # The Archivist paces the hall (ai='wander') and fA must find him just like fg/fW
    # finds a goblin/Warden — his glyph wins over the library art under him.
    from engine.motion import _cell_char
    d = _dungeon()
    dg._lib_layout(d.room, 72)
    arch = next(e for e in d.room.entities if e.kind == 'archivist')
    assert arch.ai == 'wander'
    assert _cell_char(d.room, arch.row, arch.col) == 'A'


def test_unique_labels_folios_and_desk():
    import collections
    d = _dungeon()
    r = d.room
    dg._lib_layout(r, 72)
    line = ''.join(''.join(ru.symbols) for ru in r.char_runs)
    labelset = set(dg._LIB_FILLERS + dg._LIB_CHESS + list(dg._LIB_SUIT_GLYPH.values()))
    counts = collections.Counter(ch for ch in line if ch in labelset)
    assert all(c == 1 for c in counts.values())          # no duplicated stack labels
    assert line[521:524] == '╓─╖'                         # the desk sits at (0, 521)
    arch = next(e for e in r.entities if e.kind == 'archivist')
    assert arch.col == 521                                # ...and the Archivist spawns there
    # one-suit folios carry their suit (the answers); decoys carry none
    assert sorted(it['suit'] for it in r.lib_seq if it['suit']) == sorted(dg._LIB_SUITS)


def test_brief_dialogue_advances_by_steps_then_editing(monkeypatch):
    # Approaching starts the brief; each further step advances it; after the last
    # line the Archivist edits the buffer (books toggle) and Vim warns W11.
    d = _dungeon()
    seen = []

    def _cap(term, dungeon, player, budget, message='', *a, **k):
        seen.append(message)
        seen.append(getattr(player, 'error', '') or '')   # W11 rides the red statusline

    monkeypatch.setattr(main, 'render_all', _cap)
    term = Terminal()
    script = (_cmd('set wrap')
              + [_ks('f'), _ks('A'), _ks('f'), _ks('A')]      # approach → line 1
              + [_ks('h')] * 6                                  # steps → lines 2,3, then editing
              + _cmd('q'))
    it = iter(script)
    monkeypatch.setattr(term, 'inkey', lambda *a, **k: next(it, _ks('')))
    main.run_dungeon(term, 'archivists_library', {}, player_name='admin', _dungeon=d)

    blob = ' || '.join(seen)
    assert "you've fixed my library" in blob
    assert 'a vandal is about' in blob
    assert 'seek them out' in blob
    assert 'W11' in blob                 # the live editing warned the buffer changed
    assert d.room.lib_dlg >= 4


def test_builder_structure():
    d = _dungeon()
    r = d.room
    assert (r.rows, r.wrap_buffer) == (1, True)
    suits = [it['suit'] for it in r.lib_seq if it['suit']]
    assert sorted(suits) == sorted(dg._LIB_SUITS)         # all four present, once each
    assert r.lib_idx == -1 and r.lib_filed == {} and r.lib_done is None
    assert any(e.kind == 'archivist' for e in r.entities)


# ── correct play → finale (win) ─────────────────────────────────────────────
def _winning_script(d):
    """:set wrap, then leaf to each suit folio and file it under its true name,
    then walk onto the Archivist to present."""
    slots = _suit_slots(d)
    keys = _cmd('set wrap')
    cur = -1
    # visit suits in sequence order so :e! advances forward
    for suit in sorted(slots, key=lambda s: slots[s]):
        target = slots[suit]
        while cur != target:                              # :e! advances one manuscript
            keys += _cmd('e!')
            cur = (cur + 1) % len(d.room.lib_seq)
        keys += _cmd(f'w {suit}')
    # the Archivist paces the hall; fA·fA lands on him (past the title's A) to present
    keys += [_ks('f'), _ks('A'), _ks('f'), _ks('A')]
    return keys


def test_correct_play_restores_library(monkeypatch):
    d = _dungeon()
    snaps = []
    monkeypatch.setattr(main, 'render_all',
                        lambda *a, **k: snaps.append(getattr(a[1].room, 'lib_done', None)))

    term = Terminal()
    it = iter(_winning_script(d) + _cmd('q'))
    monkeypatch.setattr(term, 'inkey', lambda *a, **k: next(it, _ks('')))

    res = main.run_dungeon(term, 'archivists_library', {}, player_name='admin', _dungeon=d)
    assert d.room.lib_done == 'win'
    # the finale placed the two reward chests + an exit
    kinds = {e.kind for e in d.room.entities}
    assert 'chest_scroll' in kinds and 'exit' in kinds
    assert {e.scroll_id for e in d.room.entities if e.kind == 'chest_scroll'} == {
        'display_move', 'edit_name'}


# ── forgery → the Archivist kills the player ────────────────────────────────
def test_forgery_is_lethal(monkeypatch):
    d = _dungeon()
    slots = _suit_slots(d)
    # File every suit under the WRONG name: rotate the labels by one.
    names = sorted(slots, key=lambda s: slots[s])
    wrong = {names[i]: names[(i + 1) % len(names)] for i in range(len(names))}

    keys = _cmd('set wrap')
    cur = -1
    for suit in names:
        target = slots[suit]
        while cur != target:
            keys += _cmd('e!')
            cur = (cur + 1) % len(d.room.lib_seq)
        keys += _cmd(f'w {wrong[suit]}')   # file this folio under a different suit's name
    keys += [_ks('f'), _ks('A'), _ks('f'), _ks('A')]   # present forged folios

    monkeypatch.setattr(main, 'render_all', lambda *a, **k: None)
    term = Terminal()
    it = iter(keys + _cmd('e') + _cmd('q!'))   # :e to reload after death, then leave
    monkeypatch.setattr(term, 'inkey', lambda *a, **k: next(it, _ks('')))

    main.run_dungeon(term, 'archivists_library', {}, player_name='admin', _dungeon=d)
    # the library was never restored; the player was struck down (then :e reloaded fresh).
    assert d.room.lib_done != 'win'


# ── :e is blocked (E37); :e! is required ────────────────────────────────────
def test_plain_e_is_blocked(monkeypatch):
    d = _dungeon()
    monkeypatch.setattr(main, 'render_all', lambda *a, **k: None)
    term = Terminal()
    it = iter(_cmd('set wrap') + _cmd('e') + _cmd('q!'))
    monkeypatch.setattr(term, 'inkey', lambda *a, **k: next(it, _ks('')))
    main.run_dungeon(term, 'archivists_library', {}, player_name='admin', _dungeon=d)
    # plain :e never advanced the manuscript (still showing the catalogue, idx -1)
    assert d.room.lib_idx == -1
