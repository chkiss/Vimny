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

"""The wizard's blessings, bound as a discoverable scroll catalogue.

Every poem the wizard recites (``vimny/art/wizard_wisdom.txt``) is a *blessing*.
Once heard it is bound into two places, exactly like a found scroll:

  * the scroll library's ``blessings/`` subtree (``run_scroll_library``), and
  * the Codex's ``blessings`` fold (``:h``).

Seen-state lives in ``progress['blessings_seen']`` — a list of blessing ids.
A blessing's id is derived from its poem ``name`` (``blessing_<kebab-name>``);
the poem's ``introduces_slug`` names the level it is recited before, which we
turn into the ``dropped_by`` provenance line shown in the library.

This module is the single source of truth for the blessing catalogue; both the
renderer and ``main.py``'s seen-tracking read from it. It loads the same
generated corpus as ``render.title`` rather than re-declaring the poems."""
from __future__ import annotations

import json
from pathlib import Path

from vimny.content.levels import LEVELS

_WISDOM_PATH = Path(__file__).parent.parent / 'art' / 'wizard_wisdom.txt'

# Provenance shown for the generic (non-level) poems, keyed by poem name. Every
# generic poem gets a hint of WHEN the wizard speaks it, mirroring a scroll's
# 'dropped_by' line.
_GENERIC_PROVENANCE = {
    'home row':      'The wizard, at the First Cave',
    'save and quit': "The wizard's counsel",
    'rhythm':        "The wizard's counsel",
    'philosophy':    "The wizard's counsel",
    'encouragement': "The wizard's counsel",
    'closing':       "The wizard's farewell",
    'final blessing': 'The Warden, unmasked',
}
_GENERIC_DEFAULT = "The wizard's counsel"


def _slugify(name: str) -> str:
    """A filesystem-safe stem from a poem name. Case is PRESERVED so poems that
    differ only in case (``w b e`` vs ``W B E``) stay distinct; runs of
    non-alphanumerics collapse to a single underscore."""
    out, prev_us = [], False
    for ch in name:
        if ch.isalnum():
            out.append(ch)
            prev_us = False
        elif not prev_us:
            out.append('_')
            prev_us = True
    return ''.join(out).strip('_')


def _blessing_id(name: str, slug: str | None = None) -> str:
    """`blessing_<stem>` — stable across reorders (keyed by poem name). Falls
    back to the introduced level's slug when a name is all punctuation
    (e.g. ``; ,``)."""
    stem = _slugify(name) or (slug or 'poem')
    return 'blessing_' + stem


def _load_poems() -> list[dict]:
    try:
        text  = _WISDOM_PATH.read_text(encoding='utf-8')
        start = text.index('{')
        end   = text.rindex('}') + 1
        return json.loads(text[start:end])['levels']
    except (OSError, ValueError, KeyError):
        return []


def _level_name(slug: str) -> str:
    for lvl in LEVELS:
        if lvl['slug'] == slug:
            return lvl['name']
    return ''


def _build_catalog() -> list[dict]:
    out = []
    used: set[str] = set()
    for poem in _load_poems():
        name = poem['name']
        slug = poem.get('introduces_slug')
        bid  = _blessing_id(name, slug)
        while bid in used:                 # last-resort uniqueness guard
            bid += '_'
        used.add(bid)
        if slug:
            lvl = _level_name(slug)
            dropped_by = f'Recited before {lvl}' if lvl else 'A wizard poem'
        else:
            dropped_by = _GENERIC_PROVENANCE.get(name, _GENERIC_DEFAULT)
        out.append({
            'id':         bid,
            'name':       name,
            'title':      name.title(),
            'dropped_by': dropped_by,
            'slug':       slug,
            # the poem body, de-centred (the corpus pads each line to the box
            # width); the scroll renderer re-centres its own way.
            'lines':      [l.strip() for l in poem['quote']],
        })
    return out


BLESSING_CATALOG: list[dict] = _build_catalog()

_BY_ID   = {b['id']: b for b in BLESSING_CATALOG}
_BY_NAME = {b['name']: b for b in BLESSING_CATALOG}


def blessing_by_id(bid: str) -> dict | None:
    return _BY_ID.get(bid)


def blessing_id_for_name(name: str) -> str | None:
    """Map a poem `name` (as passed to run_wizard_blessing) to its blessing id."""
    b = _BY_NAME.get(name)
    return b['id'] if b else None


def blessing_sections(seen) -> list[tuple[str, list[str]]]:
    """(title, [body lines]) for each SEEN blessing, in catalogue order — the
    shape CodexPane wants for the blessings fold. Body is the verse followed by
    its provenance, matching how scroll_sections renders a codex page."""
    have = set(seen or ())
    out = []
    for b in BLESSING_CATALOG:
        if b['id'] not in have:
            continue
        body = list(b['lines']) + ['', b['dropped_by']]
        out.append((b['title'], body))
    return out


def blessing_scroll_content(bid: str) -> dict | None:
    """A `_render_standard_scroll` content dict (title + tagged lines) for the
    blessing, or None if unknown. The poem body renders as centred amber verse."""
    b = _BY_ID.get(bid)
    if b is None:
        return None
    # The standard renderer left-aligns amber/dim rows; centre each verse line
    # (and the provenance) ourselves so the poem sits mid-scroll, box-width 54.
    BOX_IW = 54

    def _c(s: str) -> str:
        return s.center(BOX_IW).rstrip() if s else s

    lines = [('amber', _c(ln)) if ln else ('blank',) for ln in b['lines']]
    return {
        'title': b['title'],
        'lines': [('blank',), *lines, ('blank',),
                  ('dim', _c(b['dropped_by']))],
    }
