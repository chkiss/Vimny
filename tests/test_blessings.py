# Vimny — a Vim-teaching dungeon crawler.
# Copyright (C) 2026 Chas Kissick
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""The wizard's blessings, bound as discoverable scrolls.

Covers the blessing catalogue, its scroll/codex renderings, the scroll
library's blessings/ subtree gating, and the CodexPane nested-fold model that
groups codex/relics/blessings under top-level folds."""
import content.blessings as B
from content.blessings import (BLESSING_CATALOG, blessing_by_id,
                               blessing_id_for_name, blessing_scroll_content,
                               blessing_sections)
from engine.codex import CodexPane
from render.scroll_library import library_rows, _viewport_top


# ── catalogue ────────────────────────────────────────────────────────────────

def test_catalogue_covers_the_wisdom_corpus():
    assert len(BLESSING_CATALOG) >= 1
    # every entry has the fields the library/codex read
    for b in BLESSING_CATALOG:
        assert b['id'].startswith('blessing_')
        assert b['title'] and b['dropped_by'] and b['lines']


def test_id_for_name_round_trips():
    for name in ('home row', 'final blessing'):
        bid = blessing_id_for_name(name)
        assert bid is not None
        assert blessing_by_id(bid)['name'] == name


def test_unknown_name_has_no_id():
    assert blessing_id_for_name('no such poem') is None


def test_level_poem_provenance_names_its_level():
    # a lesson poem's provenance references the level it precedes
    b = blessing_by_id(blessing_id_for_name('w b e'))
    assert 'Rune Halls' in b['dropped_by']


# ── rendering shapes ─────────────────────────────────────────────────────────

def test_scroll_content_is_standard_renderer_shape():
    c = blessing_scroll_content('blessing_home_row')
    assert c['title'] == 'Home Row'
    tags = {ln[0] for ln in c['lines']}
    assert tags <= {'amber', 'dim', 'blank'}       # only tags the renderer knows
    assert any(t == 'amber' for t, *_ in c['lines'])


def test_scroll_content_unknown_id_is_none():
    assert blessing_scroll_content('blessing_nope') is None


def test_blessing_sections_only_yields_seen():
    assert blessing_sections([]) == []
    secs = blessing_sections(['blessing_home_row'])
    assert len(secs) == 1
    title, body = secs[0]
    assert title == 'Home Row'
    assert body[-1] == blessing_by_id('blessing_home_row')['dropped_by']


# ── scroll library subtree ───────────────────────────────────────────────────

def test_library_has_a_blessings_subtree():
    rows = library_rows()
    labels = [r['label'] for r in rows if r['type'] == 'subhdr']
    assert 'blessings/' in labels
    groups = {r['group'] for r in rows if r['type'] == 'scroll'}
    assert groups == {'codex', 'relics', 'blessings'}


def test_library_scrolls_a_viewport_so_the_cursor_stays_visible():
    # with 64 blessings the navigable list outgrows any window; the viewport
    # must follow the cursor instead of clipping to the tail (regression).
    n = len(library_rows())
    avail = 20
    assert n > avail                              # the list really does overflow
    # cursor at top → offset 0; cursor past the window → it scrolls into view
    assert _viewport_top(0, 0, avail, n) == 0
    top = _viewport_top(n - 1, 0, avail, n)
    assert top <= n - 1 < top + avail             # last row is visible
    # a cursor already inside the window doesn't move the viewport
    assert _viewport_top(5, 3, avail, n) == 3


def test_every_blessing_appears_as_a_library_row():
    rows = [r for r in library_rows()
            if r['type'] == 'scroll' and r.get('group') == 'blessings']
    assert len(rows) == len(BLESSING_CATALOG)


# ── CodexPane nested folds (codex / relics / blessings) ──────────────────────

def _grouped():
    return CodexPane(groups=[
        ('codex',     [('A', ['a1', 'a2']), ('B', ['b1'])]),
        ('blessings', [('C', ['c1'])]),
    ])


def test_grouped_opens_as_top_level_folds_only():
    p = _grouped()
    # only the two group headers are visible when everything is closed
    assert p.visible_lines() == [0, 6]


def test_opening_a_group_reveals_its_section_headers():
    p = _grouped()
    p.cursor = 0
    p.toggle_fold()                     # open the codex group
    assert p.visible_lines() == [0, 1, 4, 6]   # group + its 2 section ridges + blessings
    p.cursor = 1
    p.toggle_fold()                     # open section A
    assert 2 in p.visible_lines() and 3 in p.visible_lines()


def test_closing_a_group_hides_nested_section_headers():
    p = _grouped()
    p.open_all()
    assert p.visible_lines() == list(range(9))
    p.cursor = 0
    p.toggle_fold()                     # close codex group again
    assert 1 not in p.visible_lines()   # section header hidden by closed parent
    assert 2 not in p.visible_lines()


def test_close_all_lands_on_a_visible_top_level_header():
    p = _grouped()
    p.open_all()
    p.cursor = 3                        # deep inside section A's body
    p.close_all()
    assert not p._is_hidden(p.cursor)


def test_render_indents_nested_ridges():
    p = _grouped()
    p.open_all()
    texts = [t for t, _c, ridge in p.render_rows(9, 60) if ridge]
    assert any(t.startswith('−──  codex') for t in texts)          # depth 0
    assert any(t.startswith('  −──  A') for t in texts)            # depth 1 indent
