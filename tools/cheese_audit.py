"""Cheese audit — can a key/door-gated level be solved under par with the FULL set
of motions the player has learned, not just the level's intended lesson subset?

par_audit.py answers this for pure-navigation levels but reports the key/door levels
as `gated` (its motion-only search can't pass a locked door). This tool extends that
exact, engine-faithful search with the key→door gating so the gated levels can be
checked too:

  state = (cell, has_key, doors_open)
  edges:
    * motions  — the real engine (par_audit._successors) on a room variant whose
                 doors_open are actually opened, so walls/fog/clamping behave as in play
    * x        — on a floor_key cell, not yet held: grab it (cost 1, key → register)
    * p        — standing one cell LEFT of a still-closed locked_door while holding the
                 key: unlock + step onto the door (cost 1)

A candidate route strictly under par is then driven through the REAL run_dungeon
(par_audit._replay_confirms) — only a replay-confirmed win under par is reported, so
an over-permissive search model can't produce a false finding.

Run:  PYTHONPATH=. python3 tools/cheese_audit.py
"""
from __future__ import annotations
import heapq
import itertools

import generation.dungeon_gen as dg
from content.levels import LEVELS, known_commands
from engine.motion import _reveal_from
import tools.par_audit as pa


def _game_h_for(room, slug):
    """The viewport height the level's par was computed with — screen_vault is built
    with 33 (its room is taller, so the viewport scrolls and H/M/L are window-relative);
    every other level's room fits, so any height ≥ rows gives the same H/M/L."""
    return 33 if slug == 'screen_vault' else max(room.rows, 25)


def _door_open_room(slug, open_doors):
    """A fresh build of `slug` (seed 42) with the locked_door entities at the cells in
    `open_doors` removed — i.e. those doors unlocked. Opening a door in the engine also
    clears the fog beyond it (`_reveal_from` after stepping onto the door), so we mirror
    that: remove the doors, then reveal from each opened door cell. Cached per set."""
    room = getattr(dg, f'build_dungeon_{slug}')(42).rooms[0]
    for (dr, dc) in open_doors:
        for e in list(room.entities):
            if e.kind == 'locked_door' and (e.row, e.col) == (dr, dc):
                room.remove_entity(e)
    room.rebuild_indexes()
    for (dr, dc) in open_doors:
        _reveal_from(room, dr, dc)
    return room


def cheese_min(slug, game_h=25):
    """(cost, path) for the cheapest full-motion + key/door route spawn→exit, or
    (None, why). Handles tag-matched multi-key/door levels.

    State = (cell, held_tag, opened): the unnamed register holds at most ONE key,
    so `held_tag` is the tag of the key last grabbed (overwritten by the next `x`);
    `opened` is the set of door cells already unlocked (a key isn't consumed, so it
    keeps opening same-tag doors while held)."""
    base = getattr(dg, f'build_dungeon_{slug}')(42).rooms[0]
    if base.exit_pos is None:
        return None, 'no exit'
    key_at  = {(e.row, e.col): (getattr(e, 'tag', '') or '')
               for e in base.entities if e.kind == 'floor_key'}
    door_at = {(e.row, e.col): (getattr(e, 'tag', '') or '')
               for e in base.entities if e.kind == 'locked_door'}
    if not key_at or not door_at:
        return None, f'unsupported gating (keys={len(key_at)}, doors={len(door_at)})'

    motions, finds, has_count = pa._motions_for(slug)
    # par_audit omits screen-relative H/M/L; in a dungeon the viewport is a deterministic
    # function of the cursor row, so they ARE position-faithful — model them here.
    known = set(known_commands(slug))
    for m in ('H', 'M', 'L'):
        if m in known and m not in motions:
            motions.append(m)
    voids = pa._void_cells(base)
    max_n = max(base.rows, base.cols)
    goal  = base.exit_pos

    room_cache: dict = {}
    def room_for(opened):
        k = frozenset(opened)
        if k not in room_cache:
            room_cache[k] = _door_open_room(slug, k)
        return room_cache[k]

    start = (base.spawn_pos, None, frozenset())   # held=None → no key in the register yet
    dist  = {start: 0}
    prev  = {start: None}
    seq   = itertools.count()                     # tiebreaker so heap never compares states
    heap  = [(0, next(seq), start)]
    while heap:
        cost, _, state = heapq.heappop(heap)
        cell, held, opened = state
        if cell == goal:
            path, cur = [], state
            while prev[cur] is not None:
                pstate, lbl = prev[cur]
                path.append(lbl)
                cur = pstate
            return cost, ' '.join(reversed(path))
        if cost > dist.get(state, 1e9):
            continue

        def offer(ns, ec, lbl):
            g = cost + ec
            if g < dist.get(ns, 1e9):
                dist[ns] = g
                prev[ns] = (state, lbl)
                heapq.heappush(heap, (g, next(seq), ns))

        room = room_for(opened)
        # motion edges (engine-faithful, on the door-state-aware room)
        for ncell, ec, lbl in pa._successors(room, *cell, motions, finds, has_count,
                                              game_h, max_n, voids):
            offer((ncell, held, opened), ec, lbl)
        # x — grab the key on this cell (overwrites the held one)
        if cell in key_at and key_at[cell] != held:
            offer((cell, key_at[cell], opened), pa.main._keystroke_cost(1, 'x'), 'x')
        # p — unlock the door one cell to the right: must HOLD a key, and an untagged
        # door (dtag == '') takes any key while a tagged door needs the matching tag.
        r, c = cell
        dcell = (r, c + 1)
        if dcell in door_at and dcell not in opened and held is not None:
            dtag = door_at[dcell]
            if dtag == '' or dtag == held:
                offer((dcell, held, opened | {dcell}),
                      pa.main._keystroke_cost(1, 'p'), 'p')
    return None, 'gated (exit unreachable even with key/door modelled)'


def run():
    # par_audit's replay never reached a locked door, so it doesn't stub the
    # unlock/key animations; stub them here (they need a live terminal/colours).
    for fn in ('_unlock_animation', '_key_pickup_animation', '_door_crumble_animation'):
        if hasattr(pa.main, fn):
            setattr(pa.main, fn, lambda *a, **k: None)
    print(f"{'level':20} {'par':>4} {'cheese-min':>10}  verdict")
    print('-' * 78)
    findings = []
    for lv in LEVELS:
        slug = lv['slug']
        if not hasattr(dg, f'build_dungeon_{slug}') or slug == 'dummy':
            continue
        base = getattr(dg, f'build_dungeon_{slug}')(42).rooms[0]
        keys  = [e for e in base.entities if e.kind == 'floor_key']
        doors = [e for e in base.entities if e.kind == 'locked_door']
        if not keys or not doors:
            continue                                  # only key/door-gated levels
        par = base.par
        gh = _game_h_for(base, slug)
        cost, path = cheese_min(slug, game_h=gh)
        if cost is None:
            verdict = path
        elif par is None:
            verdict = f'(par=None) route={cost}'
        elif cost < par:
            win = pa._replay_confirms(slug, path, game_h=gh)
            if win is not None and win < par:
                findings.append((slug, par, win, path))
                verdict = f'*** UNDER PAR: replay won in {win} (par {par})  ::  {path}'
            else:
                verdict = f'candidate {cost}<par but did NOT replay-win (model gap)'
        elif cost == par:
            verdict = 'ok (== par)'
        else:
            verdict = f'min over modelled = {cost} > par (par route uses an unmodelled cmd)'
        print(f"{slug:20} {str(par):>4} {str(cost):>10}  {verdict}")
    print('-' * 78)
    if findings:
        print(f"\n{len(findings)} level(s) cheeseable under par:")
        for slug, par, won, path in findings:
            print(f"  {slug}: par={par}, won in {won}  →  {path}")
    else:
        print("\nNo single-key/door level has a replay-confirmed route under par.")


if __name__ == '__main__':
    run()
