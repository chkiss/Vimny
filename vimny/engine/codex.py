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

"""The Codex — Vim's `:help` made diegetic.

`:h {name}` opens the bound Codex read-only in a horizontal split (the pane
renders below the dungeon; focus moves INTO it, exactly as :help does), and
`:q` closes the window before it would ever quit the game — both Vim-true.
Every section is a FOLD: closed it renders as a single `+──  title` ridge,
so the book opens as its own table of contents. Reading is free — no pane
key spends budget.

The pane is a pure view: it never touches a dungeon buffer, so no par or
law elsewhere can be perturbed by anything done here.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class _Section:
    title: str
    start: int          # line index of the fold header
    end: int            # one past the section's last line
    open: bool = False
    depth: int = 0      # 0 = top-level fold; 1 = a fold nested inside a group


class CodexPane:
    """A foldable read-only buffer with a cursor over VISIBLE rows.

    Two constructions, both producing the same fold tree:

      * flat — ``CodexPane(sections)`` where ``sections`` is a list of
        ``(title, [body lines])``; each becomes one top-level fold.
      * grouped — ``CodexPane(groups=[(group_title, [(title, [body]), …]), …])``;
        each group is a top-level fold that CONTAINS its sections as nested
        (depth-1) folds. Closed, a group collapses to a single ridge; opened, it
        shows its sections' ridges, each of which opens to its body.

    Folds may nest: a line is hidden iff any *closed* fold strictly encloses it
    (``start < line < end``), so closing a group hides its section headers too —
    exactly Vim's nested-fold behaviour.
    """

    def __init__(self, sections=None, *, groups=None):
        self.lines: list[str] = []
        self.sections: list[_Section] = []
        if groups is not None:
            for gtitle, secs in groups:
                gstart = len(self.lines)
                self.lines.append(gtitle)
                group = _Section(gtitle, gstart, gstart, depth=0)
                self.sections.append(group)
                for title, body in secs:
                    start = len(self.lines)
                    self.lines.append(title)
                    self.lines.extend(body)
                    self.sections.append(_Section(title, start, len(self.lines), depth=1))
                group.end = len(self.lines)
        else:
            for title, body in (sections or ()):
                start = len(self.lines)
                self.lines.append(title)
                self.lines.extend(body)
                self.sections.append(_Section(title, start, len(self.lines)))
        self.cursor = 0             # index into self.lines (always visible)
        self.scroll = 0             # first visible-row index shown
        self.search_pat = ''
        self.search_input: str | None = None   # non-None while typing /pat
        self.cmd_input: str | None = None      # non-None while typing :cmd
        self.message = ''

    # ── folds ────────────────────────────────────────────────────────────────

    def _header_at(self, line: int) -> _Section | None:
        """The fold whose header row IS `line` (the deepest such, if two share)."""
        best = None
        for s in self.sections:
            if s.start == line and (best is None or s.depth > best.depth):
                best = s
        return best

    def _enclosing(self, line: int) -> list[_Section]:
        """Folds that strictly enclose `line` (header excluded)."""
        return [s for s in self.sections if s.start < line < s.end]

    def _is_hidden(self, line: int) -> bool:
        return any(not s.open for s in self._enclosing(line))

    def visible_lines(self) -> list[int]:
        return [i for i in range(len(self.lines)) if not self._is_hidden(i)]

    def toggle_fold(self):                       # za
        # On a fold header, toggle that fold; on a body line, the innermost
        # enclosing fold. Closing snaps the cursor up to the header.
        s = self._header_at(self.cursor)
        if s is None:
            enc = self._enclosing(self.cursor)
            s = max(enc, key=lambda x: x.depth) if enc else None
        if s is not None:
            s.open = not s.open
            if not s.open:
                self.cursor = s.start

    def open_all(self):                          # zR
        for s in self.sections:
            s.open = True

    def close_all(self):                         # zM
        for s in self.sections:
            s.open = False
        # Land on the top-level header enclosing the cursor (always visible).
        top = next((s for s in self.sections
                    if s.depth == 0 and s.start <= self.cursor < s.end), None)
        self.cursor = top.start if top is not None else 0

    # ── motion (over visible rows; a closed fold is ONE line, Vim-true) ─────

    def move(self, delta: int):
        vis = self.visible_lines()
        if not vis:
            return
        try:
            idx = vis.index(self.cursor)
        except ValueError:
            idx = 0
        idx = max(0, min(len(vis) - 1, idx + delta))
        self.cursor = vis[idx]

    def to_top(self):                            # gg
        vis = self.visible_lines()
        if vis:
            self.cursor = vis[0]

    def to_bottom(self):                         # G
        vis = self.visible_lines()
        if vis:
            self.cursor = vis[-1]

    # ── search (whole buffer; landing opens the containing fold, Vim-true) ──

    def search(self, pat: str, backward: bool = False) -> bool:
        if pat:
            self.search_pat = pat
        pat = self.search_pat
        if not pat:
            return False
        n = len(self.lines)
        order = (list(range(self.cursor + 1, n)) + list(range(0, self.cursor + 1))
                 if not backward else
                 list(range(self.cursor - 1, -1, -1)) + list(range(n - 1, self.cursor - 1, -1)))
        for i in order:
            if pat.lower() in self.lines[i].lower():
                # open every fold on the path to i (group then section) so the
                # landing row is actually visible.
                for s in self.sections:
                    if s.start <= i < s.end:
                        s.open = True
                self.cursor = i
                return True
        return False

    # ── :h {name} landing ────────────────────────────────────────────────────

    def jump_to(self, name: str) -> bool:
        name = name.strip().lower()
        if not name:
            return False
        for s in self.sections:
            if name in s.title.lower():
                # open the target and every fold enclosing its header (ancestors).
                for a in self.sections:
                    if a.start <= s.start < a.end:
                        a.open = True
                self.cursor = s.start
                return True
        return False

    # ── rendering support ────────────────────────────────────────────────────

    def render_rows(self, height: int, width: int):
        """Return `height` (text, is_cursor, is_ridge) rows, scrolled so the
        cursor stays inside the window."""
        vis = self.visible_lines()
        try:
            cidx = vis.index(self.cursor)
        except ValueError:
            cidx = 0
        if cidx < self.scroll:
            self.scroll = cidx
        elif cidx >= self.scroll + height:
            self.scroll = cidx - height + 1
        self.scroll = max(0, min(self.scroll, max(0, len(vis) - height)))
        rows = []
        for vi in range(self.scroll, min(self.scroll + height, len(vis))):
            li = vis[vi]
            s = self._header_at(li)
            ridge = s is not None
            if ridge:
                indent = '  ' * s.depth
                if not s.open:
                    # collapsed span = visible descendant headers + own body rows;
                    # for a group this reads as the count of nested sections.
                    body = s.end - s.start - 1
                    text = f'{indent}+──  {s.title}  ({body} lines)'
                else:
                    text = f'{indent}−──  {s.title}'
            else:
                text = self.lines[li]
            rows.append((text[:width], li == self.cursor, ridge))
        while len(rows) < height:
            rows.append(('', False, False))
        return rows


def scroll_sections(catalog, discovered):
    """The Codex's standing matter: one section per DISCOVERED catalog
    scroll, in catalog order, each rendered as plain text lines."""
    def flat(x):
        """Scroll fields may be rich segments — a list of (text, hl) tuples
        (e.g. the Numbered Ledger's ':set nu|mber'). The Codex is plain text."""
        if isinstance(x, str):
            return x
        return ''.join(seg[0] if isinstance(seg, (tuple, list)) else str(seg)
                       for seg in x)

    out = []
    have = set(discovered or ())
    for entry in catalog:
        if entry['id'] not in have:
            continue
        content, body = entry['content'], []
        if 'lines' in content:                     # the standard tagged shape
            for line in content['lines']:
                tag = line[0]
                if tag == 'blank':
                    body.append('')
                elif tag == 'cmd':
                    body.append(f'  {flat(line[1]):<9} ──>  {flat(line[2])}')
                elif tag == 'smudge':
                    body.append(f'  {flat(line[1]):<9} ──>  '
                                f'{flat(line[2])}{flat(line[3])}')
                else:                              # dim / amber
                    body.append(flat(line[1]))
        else:                                      # the kv shape (the Unnamed
            body.append(content.get('intro', ''))  # Register scroll)
            p = content.get('p_text')
            if p:
                body.append(f'  "{p.strip()}')
            body.append('')
            for key, desc, _gate in content.get('kv_rows', ()):
                body.append(f'  {key:<8} {desc.rstrip()}')
            body.append('')
            body.append(content.get('outro', ''))
        out.append((entry['title'], body))
    return out
