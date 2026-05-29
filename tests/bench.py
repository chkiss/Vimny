#!/usr/bin/env python3
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
"""

import copy, sys, timeit
from contextlib import redirect_stdout
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import render.colors as C
from generation.dungeon_gen import (
    build_dungeon_0, build_dungeon_1, build_dungeon_2, build_dungeon_3,
    build_dungeon_dummy,
)
from engine.player import Player
from engine.budget import Budget
from engine.motion import apply_motion
from engine.editor import _ed_snapshot, _ed_restore

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
d0 = build_dungeon_0(SEED);  r0 = d0.room
d1 = build_dungeon_1(SEED);  r1 = d1.room
d2 = build_dungeon_2(SEED);  r2 = d2.room
d3 = build_dungeon_3(SEED);  r3 = d3.room
dd = build_dungeon_dummy(SEED); rd = dd.room
print("done.\n")

mterm = _MockTerm()
C.init(mterm)


# ─────────────────────────────────────────────────────────────────────────────
# 1. Dungeon generation
# ─────────────────────────────────────────────────────────────────────────────

_section("1. Dungeon generation")
bench_ms("build_dungeon_0  (The First Cave)",     lambda: build_dungeon_0(SEED), n=50)
bench_ms("build_dungeon_1  (The Line Halls)",      lambda: build_dungeon_1(SEED), n=50)
bench_ms("build_dungeon_2  (The Counting Crypts)", lambda: build_dungeon_2(SEED), n=50)
bench_ms("build_dungeon_3  (The Rune Halls)",      lambda: build_dungeon_3(SEED), n=20)


# ─────────────────────────────────────────────────────────────────────────────
# 2. Spatial index lookups  (O(1) after P2)
# ─────────────────────────────────────────────────────────────────────────────

_section("2. Spatial index lookups  [O(1) — P2]")

void_ru   = next(ru for ru in r2.char_runs if ru.kind == 'void')
exit_ent  = next(e  for e  in r2.entities if e.kind == 'exit')
r3_ru     = next(ru for ru in r3.char_runs if ru.kind != 'void')

bench_us("char_run_at   HIT  L2 (void wall cell)",
         lambda: r2.char_run_at(void_ru.row, void_ru.col))
bench_us("char_run_at   MISS L2 (wall cell (0,0))",
         lambda: r2.char_run_at(0, 0))
bench_us("char_run_at   HIT  L3 (rune corridor)",
         lambda: r3.char_run_at(r3_ru.row, r3_ru.col))
bench_us("entity_at HIT  L2 (exit entity)",
         lambda: r2.entity_at(exit_ent.row, exit_ent.col))
bench_us("entity_at MISS L2 (empty floor)",
         lambda: r2.entity_at(5, 5))


# ─────────────────────────────────────────────────────────────────────────────
# 3. Simulated render frame  (the hot lookup path)
# ─────────────────────────────────────────────────────────────────────────────

_section("3. Simulated render frame  (17 rows × 78 cols = 1 326 cells)")

GAME_H, IW = 17, 78

bench_us("all entity_at calls  L2  (1 326 lookups)",
         lambda: [r2.entity_at(r, c) for r in range(GAME_H) for c in range(IW)],
         n=500)
bench_us("all char_run_at calls    L2  (1 326 lookups)",
         lambda: [r2.char_run_at(r, c) for r in range(GAME_H) for c in range(IW)],
         n=500)
bench_us("all entity_at calls  L3  (1 326 lookups)",
         lambda: [r3.entity_at(r, c) for r in range(GAME_H) for c in range(IW)],
         n=500)
bench_us("all char_run_at calls    L3  (1 326 lookups)",
         lambda: [r3.char_run_at(r, c) for r in range(GAME_H) for c in range(IW)],
         n=500)


# ─────────────────────────────────────────────────────────────────────────────
# 4. Undo snapshots  (deepcopy — target of P3)
# ─────────────────────────────────────────────────────────────────────────────

_section("4. Undo snapshots  [deepcopy — target of P3]")

player = Player(row=r2.spawn_pos[0], col=r2.spawn_pos[1])
snap2  = _ed_snapshot(r2, player)
snap3  = _ed_snapshot(r3, player)

_row("",
     f"  L2: {len(r2.entities)} entities, {len(r2.char_runs)} rune clusters, {len(r2._char_run_map)} indexed cells")
_row("",
     f"  L3: {len(r3.entities)} entities, {len(r3.char_runs)} rune clusters, {len(r3._char_run_map)} indexed cells")

bench_us("_ed_snapshot          L2",
         lambda: _ed_snapshot(r2, player))
bench_us("_ed_snapshot          L3",
         lambda: _ed_snapshot(r3, player))
bench_us("_ed_restore           L2",
         lambda: _ed_restore(r2, player, snap2))
bench_us("_ed_restore           L3",
         lambda: _ed_restore(r3, player, snap3))

bench_us("copy.deepcopy entities  L2",
         lambda: copy.deepcopy(r2.entities))
bench_us("copy.deepcopy runes     L2",
         lambda: copy.deepcopy(r2.char_runs))
bench_us("copy.deepcopy runes     L3",
         lambda: copy.deepcopy(r3.char_runs))

# Candidate P3 replacement: shallow tuple copy (symbols already immutable)
bench_us("tuple-copy runes        L2  [P3 candidate]",
         lambda: [type(ru)(ru.row, ru.col, ru.symbols, ru.kind) for ru in r2.char_runs])
bench_us("tuple-copy runes        L3  [P3 candidate]",
         lambda: [type(ru)(ru.row, ru.col, ru.symbols, ru.kind) for ru in r3.char_runs])


# ─────────────────────────────────────────────────────────────────────────────
# 5. apply_motion
# ─────────────────────────────────────────────────────────────────────────────

_section("5. apply_motion")

er, ec = r2.spawn_pos

bench_us("'l' count=1  no-op (at wall)",
         lambda: apply_motion(Player(row=er, col=0), 'l', 1, r2))
bench_us("'l' count=1  move  (open floor)",
         lambda: apply_motion(Player(row=er, col=ec), 'l', 1, r2))
bench_us("'l' count=10 move",
         lambda: apply_motion(Player(row=er, col=ec), 'l', 10, r2))
bench_us("'$' line-end L2",
         lambda: apply_motion(Player(row=er, col=ec), '$', 1, r2))
bench_us("'w' next-word L3",
         lambda: apply_motion(Player(row=r3.spawn_pos[0], col=r3.spawn_pos[1]), 'w', 1, r3))
bench_us("'b' prev-word L3",
         lambda: apply_motion(Player(row=r3.spawn_pos[0], col=r3.spawn_pos[1]+5), 'b', 1, r3))


# ─────────────────────────────────────────────────────────────────────────────
# 6. rebuild_indexes  (P2 maintenance cost)
# ─────────────────────────────────────────────────────────────────────────────

_section("6. rebuild_indexes  [P2 maintenance cost]")

bench_us("rebuild_indexes  L2",  lambda: r2.rebuild_indexes())
bench_us("rebuild_indexes  L3",  lambda: r3.rebuild_indexes())
bench_us("rebuild_indexes  dummy", lambda: rd.rebuild_indexes())


# ─────────────────────────────────────────────────────────────────────────────
# 7. Full render_all frame
# ─────────────────────────────────────────────────────────────────────────────

_section("7. Full render_all frame  (stdout → /dev/null)")

from render.renderer import render_all

budget2 = Budget(r2.budget or 20)
budget3 = Budget(r3.budget or 20)
p2 = Player(row=r2.spawn_pos[0], col=r2.spawn_pos[1])
p3 = Player(row=r3.spawn_pos[0], col=r3.spawn_pos[1])

_null = open('/dev/null', 'w')

def _render_l2():
    with redirect_stdout(_null):
        render_all(mterm, d2, p2, budget2)

def _render_l3():
    with redirect_stdout(_null):
        render_all(mterm, d3, p3, budget3)

bench_ms("render_all  L2  (100-col mock terminal)", _render_l2, n=300)
bench_ms("render_all  L3  (100-col mock terminal)", _render_l3, n=300)
_null.close()

print()
