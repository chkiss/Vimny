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

"""`python3 -m sharing` — the command line behind the pipeline.

Three jobs:

  * **validate** — what CI runs on a submitted level. Exit code is the verdict.
  * **golf** — replay a proposed tape against a SHIPPED level. A tape that
    finishes under par has falsified that level's solver, and says so.
  * **audit** — run every shipped level's own tape against its own par, which
    is the same check pointed at the whole curriculum.

`golf` and `audit` are the point of the pipeline that needs no community at all:
every shipped par is a claim that a hand-written Dijkstra solver found the
cheapest route, and a shorter tape falsifies that claim with its own
reproduction attached. A confirmed beat is a SOLVER BUG REPORT, not a score —
par is a property of the level, and it changes because the old value was wrong,
not because somebody played well.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from sharing import format as F
from sharing.library import export, install, list_levels, load_level
from sharing.replay import replay_tape
from sharing.validate import validate


# Levels no single tape can replay end to end. The Grandmaster's Sanctum is TWO
# rooms, and the arena deliberately has no karaoke (shear six strands in any
# order — there is no fixed route), so its gallery tape cannot finish a level
# that does not end in the gallery. Printed, never dropped.
#
# It used to hold 21 entries — every level whose tape contained an insert verb —
# because the notation omitted Esc and the keys after one were typed into the
# buffer instead of executed. Writing <Esc> (engine/tape.py) closed that, and
# re-probing showed 5 of the 21 had never needed to be here at all: the list was
# copied from `_REPLAY_OWN_TEST` in tests/test_answer_paths.py, which is about
# answer COST tokenisation rather than replayability. Over-skipping is how a
# level passes an audit vacuously, so nothing joins this set unprobed.
_NO_SINGLE_TAPE = {
    'grandmasters_sanctum',
}


def _cmd_validate(args) -> int:
    worst = 0
    for name in args.files:
        shelf = load_level(Path(name))
        print(f'── {name}')
        if shelf.level is None:
            print(f'   cannot load this one: {shelf.error}')
            worst = 1
            continue
        rep = shelf.report
        for e in rep.errors:
            print(f'   error:   {e}')
        for w in rep.warnings:
            print(f'   warning: {w}')
        if rep.ok:
            print(f'   OK — "{shelf.level.name}" par {rep.par}, budget {rep.budget}')
        else:
            worst = 1
    return worst


def _cmd_golf(args) -> int:
    """Replay a proposed tape against a shipped level."""
    import generation.dungeon_gen as dg
    from content.levels import known_commands

    builder = getattr(dg, f'build_dungeon_{args.slug}', None)
    if builder is None:
        print(f'no such level: {args.slug}', file=sys.stderr)
        return 2
    tape = args.tape if args.tape else Path(args.tape_file).read_text().strip()
    par  = builder(args.seed).room.par
    res  = replay_tape(builder(args.seed), args.slug, tape,
                       known=known_commands(args.slug))

    if res.error:
        print(f'{args.slug}[{args.seed}]: the tape did not finish — {res.error}')
        return 1
    if not res.won:
        print(f'{args.slug}[{args.seed}]: the tape replays but does not win.')
        return 1
    print(f'{args.slug}[{args.seed}]: the tape wins in {res.spent} '
          f'(recorded par {par}).')
    if par is not None and res.spent < par:
        print()
        print(f'  CONFIRMED BEAT — {par - res.spent} keystroke(s) under par.')
        print(f'  This is a bug in _par_{args.slug}, not a high score: par means '
              f'defined as the cheapest route that exists, so the recorded value '
              f'is simply wrong.')
        print(f'  Fix: correct _par_{args.slug} to {res.spent} and re-derive '
              f'budget = ceil(par * 1.4).')
        return 3          # distinct code so CI can open an issue on it
    return 0


def _cmd_audit(args) -> int:
    """Every shipped level's own tape against its own par."""
    import generation.dungeon_gen as dg
    from content.levels import LEVELS, known_commands

    bad = 0
    for lv in LEVELS:
        slug = lv['slug']
        builder = getattr(dg, f'build_dungeon_{slug}', None)
        if builder is None:
            continue
        if slug in _NO_SINGLE_TAPE:
            print(f'{slug:26} — skipped: no single tape finishes it; '
                  f'par pinned by tests/test_{slug}.py')
            continue
        room = builder(args.seed).room
        if not room.answer:
            print(f'{slug:26} — no tape (combat/arena level); pinned by its own test')
            continue
        res = replay_tape(builder(args.seed), slug, room.answer,
                          known=known_commands(slug))
        if res.error or not res.won:
            print(f'{slug:26} FAIL  tape does not win: {res.error or "no win"}')
            bad = 1
        elif room.par is not None and res.spent < room.par:
            print(f'{slug:26} BEAT  {res.spent} < par {room.par} — solver bug')
            bad = 1
        elif room.par is not None and res.spent > room.par:
            print(f'{slug:26} OVER  {res.spent} > par {room.par} — tape drift')
            bad = 1
        else:
            print(f'{slug:26} ok    par {room.par}')
    return bad


def _cmd_export(args) -> int:
    """Turn a shipped level into an authored file — the worked example."""
    import generation.dungeon_gen as dg
    from content.levels import LEVELS, known_commands

    builder = getattr(dg, f'build_dungeon_{args.slug}', None)
    if builder is None:
        print(f'no such level: {args.slug}', file=sys.stderr)
        return 2
    room    = builder(args.seed).room
    entry   = next((lv for lv in LEVELS if lv['slug'] == args.slug), {})
    teaches = list(entry.get('teaches', []))
    known   = known_commands(args.slug)
    lvl = F.from_room(room, entry.get('name', args.slug),
                      author=args.author, teaches=teaches,
                      requires=[k for k in known if k not in teaches])
    print(export(lvl, Path(args.out)))
    return 0


def _cmd_list(args) -> int:
    shelved = list_levels()
    if not shelved:
        print('nothing on your shelf yet')
        return 0
    for s in shelved:
        status = f'par {s.report.par}' if s.ok else f'BROKEN: {s.error}'
        print(f'{s.name:32} {s.path.name:28} {status}')
    return 0


def _cmd_install(args) -> int:
    shelf = install(Path(args.file))
    if not shelf.ok:
        print(f'not installed — {shelf.error}', file=sys.stderr)
        return 1
    print(f'installed {shelf.name} → {shelf.path}')
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog='python3 -m sharing',
                                 description='Vimny community level tools')
    sub = ap.add_subparsers(dest='cmd', required=True)

    p = sub.add_parser('validate', help='check a level file before you share it')
    p.add_argument('files', nargs='+')
    p.set_defaults(fn=_cmd_validate)

    p = sub.add_parser('golf', help='try a shorter route against a shipped level')
    p.add_argument('slug')
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument('--tape')
    g.add_argument('--tape-file')
    p.add_argument('--seed', type=int, default=42)
    p.set_defaults(fn=_cmd_golf)

    p = sub.add_parser('audit', help="check every shipped level's own recorded route")
    p.add_argument('--seed', type=int, default=42)
    p.set_defaults(fn=_cmd_audit)

    p = sub.add_parser('export', help='write a shipped level out as a file you can edit')
    p.add_argument('slug')
    p.add_argument('out')
    p.add_argument('--seed', type=int, default=42)
    p.add_argument('--author', default='')
    p.set_defaults(fn=_cmd_export)

    p = sub.add_parser('list', help='show the levels on your shelf')
    p.set_defaults(fn=_cmd_list)

    p = sub.add_parser('install', help='check a level and add it to your shelf')
    p.add_argument('file')
    p.set_defaults(fn=_cmd_install)

    args = ap.parse_args(argv)
    return args.fn(args)


if __name__ == '__main__':
    sys.exit(main())
