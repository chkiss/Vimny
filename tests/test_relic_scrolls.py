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

"""Relic ("safe") scroll pool: chests with no assigned scroll pull a random
not-yet-discovered scroll from this pool. Verifies catalog integrity and the
picker's no-repeat / exhaustion behaviour."""
import random

from content.scrolls import SCROLL_CATALOG, RELIC_SCROLL_IDS, pick_relic_scroll

_CATALOG_IDS = {s['id'] for s in SCROLL_CATALOG}


def test_every_relic_id_is_in_the_catalog():
    for sid in RELIC_SCROLL_IDS:
        assert sid in _CATALOG_IDS, f'{sid} missing from SCROLL_CATALOG'

def test_catalog_ids_are_unique():
    ids = [s['id'] for s in SCROLL_CATALOG]
    assert len(ids) == len(set(ids))

def test_archivist_reward_scrolls_are_renderable():
    # Regression: the Archivist's two reward scrolls crashed the codex (no dispatch
    # entry). They must be in the catalogue with standard 'lines' content so the
    # codex's standard-renderer fallback can show them.
    from content.scrolls import DISPLAY_LINE_SCROLL, EDIT_BY_NAME_SCROLL
    by_id = {s['id']: s for s in SCROLL_CATALOG}
    assert by_id['display_move']['content'] is DISPLAY_LINE_SCROLL
    assert by_id['edit_name']['content'] is EDIT_BY_NAME_SCROLL
    for d in (DISPLAY_LINE_SCROLL, EDIT_BY_NAME_SCROLL):
        assert isinstance(d.get('lines'), list) and d['lines']

def test_pick_skips_discovered():
    discovered = RELIC_SCROLL_IDS[:-1]               # all but the last
    assert pick_relic_scroll(discovered, known=['mark']) == RELIC_SCROLL_IDS[-1]

def test_prereq_relics_wait_for_their_token():
    from content.scrolls import _RELIC_PREREQ
    assert _RELIC_PREREQ['jump_back'] == 'mark'
    assert _RELIC_PREREQ['line_addr'] == 'G'
    # Before the prerequisite is learned, a gated relic never drops...
    for seed in range(20):
        assert pick_relic_scroll([], random.Random(seed)) not in _RELIC_PREREQ
    # ...and with everything else discovered, the pool reads empty until then.
    others = [sid for sid in RELIC_SCROLL_IDS if sid != 'jump_back']
    assert pick_relic_scroll(others) is None
    assert pick_relic_scroll(others, known=['mark']) == 'jump_back'
    others = [sid for sid in RELIC_SCROLL_IDS if sid != 'line_addr']
    assert pick_relic_scroll(others, known=['G']) == 'line_addr'

def test_pick_returns_none_when_exhausted():
    assert pick_relic_scroll(RELIC_SCROLL_IDS) is None
    assert pick_relic_scroll(set(RELIC_SCROLL_IDS) | {'x'}) is None

def test_pick_is_deterministic_with_rng():
    a = pick_relic_scroll([], random.Random(7))
    b = pick_relic_scroll([], random.Random(7))
    assert a == b and a in RELIC_SCROLL_IDS

def test_collecting_all_via_repeated_picks():
    discovered: list = []
    while (sid := pick_relic_scroll(discovered, random.Random(len(discovered)),
                                    known=['mark', 'G'])) is not None:
        assert sid not in discovered
        discovered.append(sid)
    assert set(discovered) == set(RELIC_SCROLL_IDS)


# ── every scroll line must fit the parchment box ─────────────────────────────
def test_every_scroll_line_fits_the_box():
    """The standard renderer's box is 54 visible columns; a cmd row costs
    indent(2) + key_w + arrow(9) + desc, where key_w is the scroll's longest
    key. Regression for The Lit Trail spilling past the parchment borders."""
    import content.scrolls as S

    BOX_IW, sep, ind = 54, '  ────>  ', '  '
    for nm in dir(S):
        obj = getattr(S, nm)
        if not (isinstance(obj, dict) and 'lines' in obj and 'title' in obj):
            continue
        lines = obj['lines']
        key_w = max(([len(s[1]) for s in lines
                      if s[0] in ('cmd', 'smudge', 'smudge_seg')]
                     + [sum(len(t) for t, _ in s[1])
                        for s in lines if s[0] == 'segs']), default=0)
        for s in lines:
            k = s[0]
            if k in ('dim', 'amber'):
                vis = len(s[1])
            elif k in ('cmd', 'segs'):
                vis = len(ind) + key_w + len(sep) + len(s[2])
            elif k == 'smudge':
                vis = len(ind) + key_w + len(sep) + len(s[2]) + len(s[3])
            elif k == 'smudge_seg':
                vis = len(ind) + key_w + len(sep) + len(s[3])
            else:
                continue
            assert vis <= BOX_IW, f'{nm}: line {s!r} is {vis} cols (box is {BOX_IW})'
        assert len(obj['title']) <= BOX_IW
