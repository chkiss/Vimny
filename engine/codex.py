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

from dataclasses import dataclass, field


@dataclass
class _Section:
    title: str
    start: int          # line index of the fold header
    end: int            # one past the section's last line
    open: bool = False


class CodexPane:
    """A foldable read-only buffer with a cursor over VISIBLE rows.

    `sections` is a list of (title, [body lines]). Line 0 of each section is
    its fold header; a closed fold collapses the whole section to that one
    rendered ridge row.
    """

    def __init__(self, sections):
        self.lines: list[str] = []
        self.sections: list[_Section] = []
        for title, body in sections:
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

    def _section_at(self, line: int) -> _Section | None:
        for s in self.sections:
            if s.start <= line < s.end:
                return s
        return None

    def _is_hidden(self, line: int) -> bool:
        s = self._section_at(line)
        return s is not None and not s.open and line != s.start

    def visible_lines(self) -> list[int]:
        return [i for i in range(len(self.lines)) if not self._is_hidden(i)]

    def toggle_fold(self):                       # za
        s = self._section_at(self.cursor)
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
        s = self._section_at(self.cursor)
        if s is not None:
            self.cursor = s.start

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
                s = self._section_at(i)
                if s is not None:
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
                s.open = True
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
            s = self._section_at(li)
            ridge = s is not None and li == s.start
            if ridge and not s.open:
                body = s.end - s.start - 1
                text = f'+──  {s.title}  ({body} lines)'
            elif ridge:
                text = f'−──  {s.title}'
            else:
                text = self.lines[li]
            rows.append((text[:width], li == self.cursor, ridge))
        while len(rows) < height:
            rows.append(('', False, False))
        return rows


def scroll_sections(catalog, discovered):
    """The Codex's standing matter: one section per DISCOVERED catalog
    scroll, in catalog order, each rendered as plain text lines."""
    out = []
    have = set(discovered or ())
    for entry in catalog:
        if entry['id'] not in have:
            continue
        body = []
        for line in entry['content']['lines']:
            tag = line[0]
            if tag == 'blank':
                body.append('')
            elif tag == 'cmd':
                body.append(f'  {line[1]:<8} {line[2]}')
            elif tag == 'smudge':
                body.append(f'  {line[1]:<8} {line[2]}{line[3]}')
            else:                                  # dim / amber
                body.append(line[1])
        out.append((entry['title'], body))
    return out
