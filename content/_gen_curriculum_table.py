#!/usr/bin/env python3
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

"""Generate the level + command tables in LEVELS_PLAN.md and README.md from the
canonical sources — `content/levels.py` (the curriculum) and
`render/vim_commands.md` (the command reference).

Run after any curriculum or command change:

    python3 content/_gen_curriculum_table.py

Each table is spliced between its BEGIN/END markers; surrounding prose is left
untouched. Do not hand-edit between the markers.

Tables produced:
  - LEVELS_PLAN.md Part 7  — full mirror (#, slug, name, commands, type)
  - README.md Levels       — player-facing (#, name, commands, Playable/Planned)
  - README.md Commands     — command reference from render/vim_commands.md
"""
from __future__ import annotations
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from content.levels import LEVELS

_ROOT     = Path(__file__).parent.parent
_PLAN     = _ROOT / 'LEVELS_PLAN.md'
_README   = _ROOT / 'README.md'
_VIM_CMDS = _ROOT / 'render' / 'vim_commands.md'


def _code(s: str) -> str:
    """Inline-code a string, double-fencing when it itself contains a backtick."""
    return f'`` {s} ``' if '`' in s else f'`{s}`'


def _built_slugs() -> set[str]:
    import generation.dungeon_gen as dg
    return {n[len('build_dungeon_'):] for n in dir(dg) if n.startswith('build_dungeon_')}


def _level_cmds_cell(lv: dict) -> str:
    cmds = lv.get('commands', '')
    if cmds:
        return _code(cmds)
    return {'boss': '(boss)', 'reliquary': '(bonus)'}.get(lv.get('type', ''), '—')


def _plan_table() -> str:
    # Part 7 has a `type` column, so an empty commands cell is just '—'
    # (no need to repeat "(boss)").
    head = ('| # | slug | Name | commands | type |\n'
            '|---|------|------|----------|------|')
    rows = [f"| {lv['display']} | `{lv['slug']}` | {lv['name']} | "
            f"{_code(lv['commands']) if lv.get('commands') else '—'} | "
            f"{lv.get('type', '')} |" for lv in LEVELS]
    return head + '\n' + '\n'.join(rows)


def _readme_levels_table() -> str:
    built = _built_slugs()
    head = '| # | Name | Commands | Status |\n|---|---|---|---|'
    rows = [f"| {lv['display']} | {lv['name']} | {_level_cmds_cell(lv)} | "
            f"{'Playable' if lv['slug'] in built else 'Planned'} |"
            for lv in LEVELS if not lv.get('admin_only')]
    return head + '\n' + '\n'.join(rows)


def _readme_commands_table() -> str:
    sep    = re.compile(r'^\|[-| ]+\|')
    rowpat = re.compile(r'^\|([^|]+)\|([^|]*)\|([^|]+)\|')
    rows   = []
    for line in _VIM_CMDS.read_text().splitlines():
        if not line.startswith('|') or sep.match(line):
            continue
        m = rowpat.match(line)
        if not m:
            continue
        keys, desc = m.group(1).strip(), m.group(3).strip()
        if not keys or keys == 'keys':
            continue
        rows.append(f"| {_code(keys)} | {desc} |")
    return '| Command | Effect |\n|---|---|\n' + '\n'.join(rows)


def _splice(path: Path, name: str, block: str) -> None:
    begin, end = f'<!-- BEGIN GENERATED {name} -->', f'<!-- END GENERATED {name} -->'
    text = path.read_text()
    pat  = re.compile(re.escape(begin) + r'.*?' + re.escape(end), re.DOTALL)
    if not pat.search(text):
        raise SystemExit(f'markers for {name!r} not found in {path.name}')
    path.write_text(pat.sub(lambda _: f'{begin}\n{block}\n{end}', text))


def main() -> None:
    _splice(_PLAN,   'CURRICULUM TABLE', _plan_table())
    _splice(_README, 'LEVELS TABLE',     _readme_levels_table())
    _splice(_README, 'COMMANDS TABLE',   _readme_commands_table())
    print(f'Regenerated doc tables ({len(LEVELS)} levels): '
          'LEVELS_PLAN Part 7, README Levels, README Commands')


if __name__ == '__main__':
    main()
