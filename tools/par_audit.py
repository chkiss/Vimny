"""Par-floor audit — is each level's `par` actually the minimum keystroke count?

A level's `par` is set by its bespoke `_par_<slug>` Dijkstra for the *intended* command
subset. This tool asks the complementary question: over the FULL set of motion commands
the player has learned by that level, is there a spawn→exit route that costs FEWER
keystrokes than par? If so, par is set above the true minimum.

Method (faithful by construction): a Dijkstra on cursor position whose edges are produced
by running the REAL `engine.motion.apply_motion` for every known command (with counts and,
for f/F/t/T, every target glyph on the row). Cost is the real `_keystroke_cost`. Because
edges come from the engine, walls / fog / void / clamping all behave exactly as in play.

Soundness:
  * A computed min STRICTLY BELOW par is a real finding — an actual cheaper route exists
    (the path is printed; re-walk it to confirm).
  * Modelled commands are a SUBSET (no search `/`·`n`, marks, `;`/`,`, H/M/L — these are
    screen/state-dependent). So an unmodelled command could only make the true min LOWER,
    never higher: `min == par` is reassuring but not a proof of optimality; `min > par`
    just means par's own route uses a command this tool doesn't model (e.g. search).
  * Levels whose exit is gated (keys / keystones / doors / combat) aren't pure-navigation;
    the motion-only search can't reach the exit and the level is reported as `gated`.

Run:  PYTHONPATH=. python3 tools/par_audit.py
"""
from __future__ import annotations
import heapq

from engine.player import Player
from engine.motion import apply_motion
from content.levels import LEVELS, known_commands
import generation.dungeon_gen as dg
import main  # for _keystroke_cost


# motion tokens that are themselves the motion name
_SIMPLE = {'^', '$', '0', 'w', 'b', 'e', 'W', 'B', 'E', '{', '}', '(', ')', '%', 'ge', 'gE'}
# motions worth trying with a count prefix
_COUNTABLE = {'h', 'j', 'k', 'l', 'w', 'b', 'e', 'W', 'B', 'E', 'ge', 'gE', '{', '}', '(', ')'}
_VOID_KINDS = {'void'}


def _void_cells(room):
    return {(ru.row, ru.col + i) for ru in room.char_runs
            if ru.kind in _VOID_KINDS for i in range(len(ru.symbols))}


def _motions_for(slug):
    """The cursor-motion commands available at `slug` that this tool models."""
    known = set(known_commands(slug))
    ms = ['h', 'j', 'k', 'l']
    ms += [t for t in _SIMPLE if t in known]
    if 'G' in known:
        ms += ['G', 'gg']
    finds = [t for t in ('f', 'F', 't', 'T') if t in known]
    return ms, finds, ('count' in known)


def _row_glyphs(room, row):
    out = set()
    for ru in room._char_runs_by_row.get(row, []):
        out.update(ru.symbols)
    return out


def _apply(room, r, c, motion, count, target, game_h, voids):
    p = Player(row=r, col=c)
    moved = apply_motion(p, motion, count, room, target=target,
                         count_given=(count > 1), game_h=game_h)
    if not moved or (p.row, p.col) in voids:   # don't LAND on a void rune (costs HP / can kill)
        return None
    if not room.is_passable(p.row, p.col):     # $/%/0/^ can overshoot onto WATER — landing drowns
        return None
    return (p.row, p.col)


def _successors(room, r, c, motions, finds, has_count, game_h, max_n, voids):
    """Yield (target_cell, cost, label) edges from (r, c), cheapest-per-target."""
    best = {}                                   # cell -> (cost, label)
    def offer(cell, cost, lbl):
        if cell and cell != (r, c) and cost < best.get(cell, (1e9,))[0]:
            best[cell] = (cost, lbl)

    for m in motions:
        # count 1 always
        cell = _apply(room, r, c, m, 1, None, game_h, voids)
        offer(cell, main._keystroke_cost(1, m), m)
        # count variants
        if has_count and m in _COUNTABLE:
            prev = None
            for n in range(2, max_n + 1):
                cell = _apply(room, r, c, m, n, None, game_h, voids)
                if cell is None or cell == prev:
                    if cell == prev:            # clamped — larger counts won't move further
                        break
                    continue
                prev = cell
                offer(cell, main._keystroke_cost(n, m), f'{n}{m}')
        # {N}G — go to line N (buffer-relative)
        if m == 'G' and has_count:
            for n in range(1, room.rows + 1):
                cell = _apply(room, r, c, 'G', n, None, game_h, voids)
                offer(cell, main._keystroke_cost(n, 'G'), f'{n}G')

    for fm in finds:
        for ch in _row_glyphs(room, r):
            cell = _apply(room, r, c, fm, 1, ch, game_h, voids)
            offer(cell, main._keystroke_cost(1, fm), f'{fm}{ch}')
            if has_count:
                prev = None
                for n in range(2, room.cols + 1):
                    cell = _apply(room, r, c, fm, n, ch, game_h, voids)
                    if cell is None or cell == prev:
                        if cell == prev:
                            break
                        continue
                    prev = cell
                    offer(cell, main._keystroke_cost(n, fm), f'{n}{fm}{ch}')

    for cell, (cost, lbl) in best.items():
        yield cell, cost, lbl


def nav_min(room, slug, game_h=25):
    """(cost, path) for the cheapest modelled motion route spawn→exit (avoiding void
    landings), or (None, why)."""
    if room.exit_pos is None:
        return None, 'no exit'
    motions, finds, has_count = _motions_for(slug)
    voids = _void_cells(room)
    max_n = max(room.rows, room.cols)
    start, goal = room.spawn_pos, room.exit_pos
    dist = {start: 0}
    prev = {start: None}
    heap = [(0, start)]
    while heap:
        cost, cell = heapq.heappop(heap)
        if cell == goal:
            path = []
            cur = goal
            while prev[cur] is not None:
                pcell, lbl = prev[cur]
                path.append(lbl)
                cur = pcell
            return cost, ' '.join(reversed(path))
        if cost > dist.get(cell, 1e9):
            continue
        for ncell, ec, lbl in _successors(room, *cell, motions, finds, has_count, game_h, max_n, voids):
            g = cost + ec
            if g < dist.get(ncell, 1e9):
                dist[ncell] = g
                prev[ncell] = (cell, lbl)
                heapq.heappush(heap, (g, ncell))
    return None, 'gated (exit unreachable by motion alone)'


def _replay_confirms(slug, path, game_h=None):
    """Drive `path` through the REAL run_dungeon (the oracle): return the budget.spent the
    player first reaches the exit, or None if it never wins (budget/HP/gating/model gap).
    Stubs the drawing paths; uses a non-admin player so command gating is realistic.
    `game_h` forces the replay terminal height (= game_h + 8) so H/M/L land exactly as
    the audit modelled them; None keeps the ambient terminal size."""
    import os
    from blessed import Terminal
    from blessed.keyboard import Keystroke
    if game_h is not None:
        os.environ['LINES'], os.environ['COLUMNS'] = str(game_h + 8), '200'
    for fn in ('render_all', '_win_animation', '_fireworks_animation', '_starfield_victory',
               '_void_fall_animation', '_drown_animation', '_heart_container_animation',
               '_play_void_falls'):
        setattr(main, fn, lambda *a, **k: None)
    # '⏎' in a token is the Enter that submits a / ? search; everything else is literal.
    keys = [Keystroke('\r') if ch == '⏎' else Keystroke(ch)
            for tok in path.split() for ch in tok]
    d = getattr(dg, f'build_dungeon_{slug}')(42)
    rec = {}
    def cap(t, dn, pl, bg, message='', *a, **k):
        # The win fires the moment the player steps on the exit (the par-perfect / cleared
        # banner). Record budget.spent at that frame; `:wq` then returns the real `won`.
        if 'spent' not in rec and any(s in message for s in
                ('Par-perfect', 'Dungeon cleared', 'VIM AD ASTRA', 'the way upward')):
            rec['spent'] = bg.spent
    main.render_all = cap
    it = iter(keys + [Keystroke(':'), Keystroke('w'), Keystroke('q'), Keystroke('\r')])
    term = Terminal(force_styling=False)
    term.inkey = lambda *a, **k: next(it, Keystroke(''))
    import render.colors as _C       # key/door paths read colours directly in run_dungeon
    _C.init(term)
    res = main.run_dungeon(term, slug, {}, player_name='p', _dungeon=d)
    return rec.get('spent') if (res and res.get('won')) else None


def main_run():
    findings = []
    print(f"{'level':22} {'par':>5} {'nav-min':>8}  verdict")
    print('-' * 78)
    for lv in LEVELS:
        slug = lv['slug']
        if not hasattr(dg, f'build_dungeon_{slug}') or slug == 'dummy':
            continue
        room = getattr(dg, f'build_dungeon_{slug}')(42).rooms[0]
        par = room.par
        cost, path = nav_min(room, slug)
        if cost is None:
            verdict = path                                  # 'gated' / 'no exit'
        elif par is None:
            verdict = f'(par=None) route={cost}'
        elif cost < par:
            win = _replay_confirms(slug, path)              # oracle: must actually win in-game
            if win is not None and win < par:
                findings.append((slug, par, win, path))
                verdict = f'*** UNDER PAR: replay won in {win} (par {par})  ::  {path}'
            else:
                verdict = f'candidate {cost}<par but did NOT replay-win (void/budget/model gap)'
        elif cost == par:
            verdict = 'ok (== par)'
        else:
            verdict = f'par-route uses an unmodelled cmd (min over modelled = {cost} > par)'
        print(f"{slug:22} {str(par):>5} {str(cost):>8}  {verdict}")
    print('-' * 78)
    if findings:
        print(f"\n{len(findings)} level(s) with a REPLAY-CONFIRMED route under par (par too high):")
        for slug, par, cost, path in findings:
            print(f"  {slug}: par={par}, won in {cost}  →  {path}")
    else:
        print("\nNo level has a replay-confirmed motion route under par.")


if __name__ == '__main__':
    main_run()
