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

"""Hint bar text, driven by vim_commands.md.

CMD is parsed once at import from the markdown table.  hint_text() shows the
current level's own `teaches` (or, for a community level, the set it declares),
so the bar names the lesson of the room the player is standing in.

HINT_TIERS is built by diffing known_commands() between consecutive curriculum
levels — no token lists are hardcoded.  It is the fallback, for a slug with no
lesson to read: hint_text() walks it newest-first and returns the first tier
whose sentinel is in the player's known_commands.
"""
from __future__ import annotations
import pathlib
import re

_MD = pathlib.Path(__file__).parent / 'vim_commands.md'

# ── Parse vim_commands.md ─────────────────────────────────────────────────────

def _parse(path: pathlib.Path) -> dict[str, tuple[str, str]]:
    cmd: dict[str, tuple[str, str]] = {}
    sep = re.compile(r'^\|[-| ]+\|')
    row = re.compile(r'^\|([^|]+)\|([^|]*)\|([^|]+)\|')
    with open(path, encoding='utf-8') as f:
        for line in f:
            line = line.rstrip()
            if not line.startswith('|') or sep.match(line):
                continue
            m = row.match(line)
            if not m:
                continue
            keys  = m.group(1).strip()
            token = m.group(2).strip()
            desc  = m.group(3).strip()
            if not keys or keys == 'keys':
                continue
            tok = token or keys
            cmd[tok] = (keys, desc)
    return cmd

CMD: dict[str, tuple[str, str]] = _parse(_MD)

# ── Build hint tiers from curriculum diffs ────────────────────────────────────

def _build_tiers() -> list[tuple[str, list[str]]]:
    """Derive tiers by diffing known_commands() across curriculum levels.

    Each tier = (sentinel, new_tokens) where sentinel is the first new token
    and new_tokens is the ordered list of commands introduced at that level.
    Levels that add no new commands (bosses, the reliquary) are skipped
    automatically. Walks LEVELS in curriculum order.
    """
    from vimny.content.levels import known_commands, LEVELS
    tiers: list[tuple[str, list[str]]] = []
    prev_known: set[str] = set(known_commands('first_cave'))   # seed with the First Cave base
    for lv in LEVELS:
        if lv['slug'] == 'first_cave' or lv.get('admin_only'):
            continue
        curr = known_commands(lv['slug'])
        new = [t for t in curr if t not in prev_known]
        if new:
            tiers.append((new[0], new))
            prev_known = set(curr)
    tiers.reverse()   # newest tier first
    return tiers

_HINT_TIERS: list[tuple[str, list[str]]] = _build_tiers()

# ── Constants ─────────────────────────────────────────────────────────────────

_SUFFIX  = '  :w write  :q quit'
_DEFAULT = 'h/j/k/l:move cursor  :w write (save)  :q quit  :q! quit without saving'

# ── Public API ────────────────────────────────────────────────────────────────

# Some single curriculum tokens unlock a whole keystroke family that shares one
# gate.  '/' (search) gates ? n N too — show them all on the hint bar.  Likewise the
# one 'subst' gate unlocks the whole :s family — :%s//g, the :g/pat/d global delete,
# and & — so the bar must show them all (otherwise :g/pat/d is gated-in but invisible,
# and the player can't find the line-delete the Forge's cursed verses require).
# 'mark' gates set (m) AND both jumps (` ') — without expansion only m{a} shows and
# the player can't see how to return to a mark.  'insert' gates a (append) alongside
# i; the linewise operator forms dd/yy bundle into the d/y keys cell in vim_commands.md
# (mirroring c{m}  cc), so they need no family entry.  '@' gates @@ (replay the last
# macro) as well as @{a}: same action, whose register the executor resolves to
# `macro_last` — so it worked from the day the Hall of Echoes shipped and the bar
# had never once said so.
_FAMILY = {'/':      ['/', '?{pat}', 'n', 'N'],
           'subst':  ['subst', ':%s//g', ':g/pat/d', '&'],
           'mark':   ['mark', '`{a}', "'{a}"],
           'insert': ['insert', 'a'],
           '@':      ['@', '@@']}


def _format(tokens) -> str:
    expanded: list = []
    for tok in tokens:
        for t in _FAMILY.get(tok, [tok]):
            if t not in expanded:
                expanded.append(t)
    parts = [f'{CMD[t][0]}:{CMD[t][1]}' for t in expanded if t in CMD]
    return ('  '.join(parts) + _SUFFIX) if parts else _DEFAULT


def hint_text(known: list, slug: str | None = None,
              teaches: list | None = None) -> str:
    """Return hint bar text for the level being played.

    The bar shows THIS LEVEL'S lesson — its own `teaches` — plus `:w`/`:q` and
    whatever family keys that lesson unlocks.  It deliberately does NOT show the
    newest tier the *player* owns: that is a property of the save file, not the
    room, so it painted every level of a replay with the same line.

    `teaches` overrides the curriculum lookup, for a level that has no
    curriculum position and declares its own set (community levels, forge
    drafts).  On a boss — which introduces nothing — the bar lists the whole act
    the boss caps, so the player is nudged to wield everything the act taught,
    never the next act's command the boss merely previews.  The newest-tier walk
    survives only as the fallback for a slug nothing else can answer for.
    """
    if teaches:
        text = _format(teaches)
        if text != _DEFAULT:
            return text
    if slug is not None:
        from vimny.content.levels import act_commands, teaches_for_slug  # noqa: PLC0415
        # A level that introduces nothing — a boss, or a revision level — is
        # revising its act, so the bar lists the act.
        tokens = teaches_for_slug(slug) or act_commands(slug)
        if tokens:
            text = _format(tokens)
            if text != _DEFAULT:
                return text
    for sentinel, tokens in _HINT_TIERS:
        if sentinel in known:
            return _format(tokens)
    return _DEFAULT
