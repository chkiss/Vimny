#!/usr/bin/env python3
"""Generate the curriculum table in LEVELS_PLAN.md Part 7 from content/levels.py.

`LEVELS` is the single source of truth. After renumbering (editing `display`
strings and/or reordering `LEVELS`), run:

    python3 content/_gen_curriculum_table.py

The table is spliced between the BEGIN/END markers in LEVELS_PLAN.md; the
surrounding prose is left untouched. Do not hand-edit between the markers.
"""
from __future__ import annotations
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from content.levels import LEVELS

_PLAN  = Path(__file__).parent.parent / 'LEVELS_PLAN.md'
_BEGIN = '<!-- BEGIN GENERATED CURRICULUM TABLE -->'
_END   = '<!-- END GENERATED CURRICULUM TABLE -->'


def _row(lv: dict) -> str:
    cmds = lv.get('commands', '')
    cmds = f'`{cmds}`' if cmds else '—'
    return (f"| {lv['display']} | `{lv['slug']}` | {lv['name']} | "
            f"{cmds} | {lv.get('type', '')} |")


def build_table() -> str:
    head = ('| # | slug | Name | commands | type |\n'
            '|---|------|------|----------|------|')
    return head + '\n' + '\n'.join(_row(lv) for lv in LEVELS)


def main() -> None:
    text  = _PLAN.read_text()
    block = f'{_BEGIN}\n{build_table()}\n{_END}'
    pat   = re.compile(re.escape(_BEGIN) + r'.*?' + re.escape(_END), re.DOTALL)
    if not pat.search(text):
        raise SystemExit(f'markers not found in {_PLAN.name}; add {_BEGIN} / {_END}')
    _PLAN.write_text(pat.sub(lambda _: block, text))
    print(f'Updated Part 7 curriculum table ({len(LEVELS)} rows) in {_PLAN.name}')


if __name__ == '__main__':
    main()
