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

"""Performance benchmarks — establishes baseline for measuring future optimisations.

Run with:  python tests/bench.py
Re-run after each Phase to compare.

Sections:
  1. Dungeon generation
  2. Spatial index lookups  (O(1) after P2)
  3. Simulated render frame
  4. Undo snapshots         (deepcopy — target of P3)
  5. apply_motion
  6. rebuild_indexes        (P2 maintenance cost)
  7. Full render_all frame

Fixtures: the Counting Crypts (voids/doors) and the Rune Halls (dense word
corridors) are the two representative dungeons benchmarked; the dummy sandbox is
used for the rebuild_indexes cost.
"""

import copy, sys, timeit
from contextlib import redirect_stdout
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import vimny.render.colors as C
from vimny.generation.dungeon_gen import (
    build_dungeon_first_cave, build_dungeon_line_halls, build_dungeon_counting_crypts, build_dungeon_rune_halls,
    build_dungeon_dummy,
)
from vimny.engine.player import Player
from vimny.engine.budget import Budget
from vimny.engine.motion import apply_motion
from vimny.engine.editor import _ed_snapshot, _ed_restore

SEED = 42
_COL_W = 52          # label column width in output


# ── Helpers ───────────────────────────────────────────────────────────────────

def _section(title):
    bar = '─' * (60 - len(title) - 4)
    print(f"\n── {title} {bar}")


def _row(label, value_str):
    print(f"  {label:<{_COL_W}} {value_str}")


def bench_us(label, fn, n=2000):
    """Micro-benchmark: report µs per call."""
    t = timeit.timeit(fn, number=n)
    us = t / n * 1_000_000
    _row(label, f"{us:8.2f} µs   (n={n})")


def bench_ms(label, fn, n=100):
    """Macro-benchmark: report ms per call."""
    t = timeit.timeit(fn, number=n)
    ms = t / n * 1_000
    _row(label, f"{ms:8.3f} ms   (n={n})")


# ── Mock terminal for render benchmarks ──────────────────────────────────────

class _MockTerm:
    """Minimal blessed.Terminal stand-in for benchmarking."""
    width = 100; height = 24
    home = ''; normal = ''; bright_white = ''; bright_green = ''; white = ''

    def on_color_rgb(self, r, g, b): return ''
    def color_rgb(self, r, g, b):    return ''
    def move_yx(self, r, c):         return ''
    def __getattr__(self, name):     return ''


# ── Build fixtures once ───────────────────────────────────────────────────────

print("Building dungeons...", end=' ', flush=True)
d_crypts = build_dungeon_counting_crypts(SEED);  r_crypts = d_crypts.room
d_halls  = build_dungeon_rune_halls(SEED);  r_halls = d_halls.room
d_dummy  = build_dungeon_dummy(SEED); r_dummy = d_dummy.room
print("done.\n")

mterm = _MockTerm()
C.init(mterm)


# ─────────────────────────────────────────────────────────────────────────────
# 1. Dungeon generation
# ─────────────────────────────────────────────────────────────────────────────

_section("1. Dungeon generation")
bench_ms("build_dungeon_first_cave  (The First Cave)",     lambda: build_dungeon_first_cave(SEED), n=50)
bench_ms("build_dungeon_line_halls  (The Line Halls)",      lambda: build_dungeon_line_halls(SEED), n=50)
bench_ms("build_dungeon_counting_crypts  (The Counting Crypts)", lambda: build_dungeon_counting_crypts(SEED), n=50)
bench_ms("build_dungeon_rune_halls  (The Rune Halls)",      lambda: build_dungeon_rune_halls(SEED), n=20)


# ─────────────────────────────────────────────────────────────────────────────
# 2. Spatial index lookups  (O(1) after P2)
# ─────────────────────────────────────────────────────────────────────────────

_section("2. Spatial index lookups  [O(1) — P2]")

void_ru   = next(ru for ru in r_crypts.char_runs if ru.kind == 'void')
exit_ent  = next(e  for e  in r_crypts.entities if e.kind == 'exit')
halls_ru  = next(ru for ru in r_halls.char_runs if ru.kind != 'void')

bench_us("char_run_at   HIT  crypts (void wall cell)",
         lambda: r_crypts.char_run_at(void_ru.row, void_ru.col))
bench_us("char_run_at   MISS crypts (wall cell (0,0))",
         lambda: r_crypts.char_run_at(0, 0))
bench_us("char_run_at   HIT  halls (rune corridor)",
         lambda: r_halls.char_run_at(halls_ru.row, halls_ru.col))
bench_us("entity_at HIT  crypts (exit entity)",
         lambda: r_crypts.entity_at(exit_ent.row, exit_ent.col))
bench_us("entity_at MISS crypts (empty floor)",
         lambda: r_crypts.entity_at(5, 5))


# ─────────────────────────────────────────────────────────────────────────────
# 3. Simulated render frame  (the hot lookup path)
# ─────────────────────────────────────────────────────────────────────────────

_section("3. Simulated render frame  (17 rows × 78 cols = 1 326 cells)")

GAME_H, IW = 17, 78

bench_us("all entity_at calls  crypts  (1 326 lookups)",
         lambda: [r_crypts.entity_at(r, c) for r in range(GAME_H) for c in range(IW)],
         n=500)
bench_us("all char_run_at calls    crypts  (1 326 lookups)",
         lambda: [r_crypts.char_run_at(r, c) for r in range(GAME_H) for c in range(IW)],
         n=500)
bench_us("all entity_at calls  halls  (1 326 lookups)",
         lambda: [r_halls.entity_at(r, c) for r in range(GAME_H) for c in range(IW)],
         n=500)
bench_us("all char_run_at calls    halls  (1 326 lookups)",
         lambda: [r_halls.char_run_at(r, c) for r in range(GAME_H) for c in range(IW)],
         n=500)


# ─────────────────────────────────────────────────────────────────────────────
# 4. Undo snapshots  (deepcopy — target of P3)
# ─────────────────────────────────────────────────────────────────────────────

_section("4. Undo snapshots  [deepcopy — target of P3]")

player      = Player(row=r_crypts.spawn_pos[0], col=r_crypts.spawn_pos[1])
snap_crypts = _ed_snapshot(r_crypts, player)
snap_halls  = _ed_snapshot(r_halls, player)

_row("",
     f"  crypts: {len(r_crypts.entities)} entities, {len(r_crypts.char_runs)} character runs, {len(r_crypts._char_run_map)} indexed cells")
_row("",
     f"  halls: {len(r_halls.entities)} entities, {len(r_halls.char_runs)} character runs, {len(r_halls._char_run_map)} indexed cells")

bench_us("_ed_snapshot          crypts",
         lambda: _ed_snapshot(r_crypts, player))
bench_us("_ed_snapshot          halls",
         lambda: _ed_snapshot(r_halls, player))
bench_us("_ed_restore           crypts",
         lambda: _ed_restore(r_crypts, player, snap_crypts))
bench_us("_ed_restore           halls",
         lambda: _ed_restore(r_halls, player, snap_halls))

bench_us("copy.deepcopy entities  crypts",
         lambda: copy.deepcopy(r_crypts.entities))
bench_us("copy.deepcopy char runs     crypts",
         lambda: copy.deepcopy(r_crypts.char_runs))
bench_us("copy.deepcopy char runs     halls",
         lambda: copy.deepcopy(r_halls.char_runs))

# Candidate P3 replacement: shallow tuple copy (symbols already immutable)
bench_us("tuple-copy char runs        crypts  [P3 candidate]",
         lambda: [type(ru)(ru.row, ru.col, ru.symbols, ru.kind) for ru in r_crypts.char_runs])
bench_us("tuple-copy char runs        halls  [P3 candidate]",
         lambda: [type(ru)(ru.row, ru.col, ru.symbols, ru.kind) for ru in r_halls.char_runs])


# ─────────────────────────────────────────────────────────────────────────────
# 5. apply_motion
# ─────────────────────────────────────────────────────────────────────────────

_section("5. apply_motion")

er, ec = r_crypts.spawn_pos

bench_us("'l' count=1  no-op (at wall)",
         lambda: apply_motion(Player(row=er, col=0), 'l', 1, r_crypts))
bench_us("'l' count=1  move  (open floor)",
         lambda: apply_motion(Player(row=er, col=ec), 'l', 1, r_crypts))
bench_us("'l' count=10 move",
         lambda: apply_motion(Player(row=er, col=ec), 'l', 10, r_crypts))
bench_us("'$' line-end crypts",
         lambda: apply_motion(Player(row=er, col=ec), '$', 1, r_crypts))
bench_us("'w' next-word halls",
         lambda: apply_motion(Player(row=r_halls.spawn_pos[0], col=r_halls.spawn_pos[1]), 'w', 1, r_halls))
bench_us("'b' prev-word halls",
         lambda: apply_motion(Player(row=r_halls.spawn_pos[0], col=r_halls.spawn_pos[1]+5), 'b', 1, r_halls))


# ─────────────────────────────────────────────────────────────────────────────
# 6. rebuild_indexes  (P2 maintenance cost)
# ─────────────────────────────────────────────────────────────────────────────

_section("6. rebuild_indexes  [P2 maintenance cost]")

bench_us("rebuild_indexes  crypts",  lambda: r_crypts.rebuild_indexes())
bench_us("rebuild_indexes  halls",  lambda: r_halls.rebuild_indexes())
bench_us("rebuild_indexes  dummy", lambda: r_dummy.rebuild_indexes())


# ─────────────────────────────────────────────────────────────────────────────
# 7. Full render_all frame
# ─────────────────────────────────────────────────────────────────────────────

_section("7. Full render_all frame  (stdout → /dev/null)")

from vimny.render.renderer import render_all

budget_crypts = Budget(r_crypts.budget or 20)
budget_halls  = Budget(r_halls.budget or 20)
p_crypts = Player(row=r_crypts.spawn_pos[0], col=r_crypts.spawn_pos[1])
p_halls  = Player(row=r_halls.spawn_pos[0], col=r_halls.spawn_pos[1])

_null = open('/dev/null', 'w')

def _render_crypts():
    with redirect_stdout(_null):
        render_all(mterm, d_crypts, p_crypts, budget_crypts)

def _render_halls():
    with redirect_stdout(_null):
        render_all(mterm, d_halls, p_halls, budget_halls)

bench_ms("render_all  crypts  (100-col mock terminal)", _render_crypts, n=300)
bench_ms("render_all  halls  (100-col mock terminal)", _render_halls, n=300)
_null.close()

print()
