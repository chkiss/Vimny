"""
Simulate the Warden's Keep boss to find the actual optimal keystroke cost.
Run with:  python _sim_wardens_keep.py [-v]
"""
import random, sys
sys.path.insert(0, '/home/ch/Vimny')

from generation.dungeon_gen import build_dungeon_wardens_keep
from engine.player import Player
from engine.motion import apply_motion, _reveal_from
from main import (
    _enemy_tick, _try_warden_move,
    _spawn_goblin, _remove_warden_shields,
    _keystroke_cost, _WARDEN_SUMMON_INTERVAL,
)

MAX_STEPS = 500  # safety limit to prevent infinite loops


def simulate(seed=42, verbose=False):
    random.seed(seed)
    dungeon = build_dungeon_wardens_keep(seed)
    room = dungeon.rooms[0]
    player = Player(row=3, col=0)
    cost = [0]
    steps = [0]

    def log(msg):
        if verbose:
            gobs = [(e.row, e.col) for e in room.entities if e.alive and e.kind == 'goblin']
            w = next((e for e in room.entities if e.alive and e.kind == 'warden'), None)
            sh = next((e for e in room.entities if e.alive and e.kind == 'shield'), None)
            extra = f' | gobs={gobs} w={w and (w.row,w.col)} sh={sh and (sh.row,sh.col)}'
            print(f'  [{cost[0]:3d}] ({player.row},{player.col}) {msg}{extra}')

    def step(m, count=1, target=None):
        steps[0] += 1
        if steps[0] > MAX_STEPS:
            raise RuntimeError('step limit exceeded')
        c = _keystroke_cost(count, m)
        apply_motion(player, m, count, room, target)
        cost[0] += c
        log(f'{count if count>1 else ""}{m}{"="+target if target else ""} ({c}k)')
        _enemy_tick(room, player)

    def interact():
        steps[0] += 1
        if steps[0] > MAX_STEPS:
            raise RuntimeError('step limit exceeded')
        cur = room.entity_at(player.row, player.col)
        if cur is None:
            return False
        cost[0] += 1
        if cur.kind == 'seal_door':
            room.remove_entity(cur)
            _reveal_from(room, player.row, player.col)
            log('x seal_door')
        elif cur.kind == 'warden':
            cur.hp -= 1
            log(f'x warden HP {cur.hp+1}->{cur.hp}')
            if cur.hp > 0:
                side = random.choice((-1, 1))
                _spawn_goblin(room, cur.row, cur.col + side * 3, summoner_uid=cur.uid)
                cur.summon_timer = _WARDEN_SUMMON_INTERVAL
            else:
                room.kill_entity(cur)
                _remove_warden_shields(room)
                log('  Warden dead')
        elif cur.kind == 'goblin':
            cur.hp -= 1
            log(f'x goblin@({cur.row},{cur.col})')
            if cur.hp <= 0:
                room.kill_entity(cur)
                _try_warden_move(room, cur, player)
        _enemy_tick(room, player)
        return True

    def alive_goblins():
        return [e for e in room.entities if e.alive and e.kind == 'goblin']

    def warden():
        return next((e for e in room.entities if e.alive and e.kind == 'warden'), None)

    def shield():
        return next((e for e in room.entities if e.alive and e.kind == 'shield'), None)

    def move_to(target_row, target_col):
        """Navigate to (target_row, target_col), routing around the shield.
        Uses $ / 0 for long horizontal moves, count-move for short ones."""
        sh = shield()
        sh_row = sh.row if sh else -1
        sh_col = sh.col if sh else -1

        def col_blocked(row, from_col, to_col):
            if sh_row != row:
                return False
            lo, hi = min(from_col, to_col), max(from_col, to_col)
            return lo <= sh_col <= hi

        def row_blocked(from_row, to_row, at_col):
            """True if shield is at at_col on any row between from_row and to_row."""
            if sh_col != at_col:
                return False
            lo, hi = min(from_row, to_row), max(from_row, to_row)
            return lo <= sh_row <= hi and sh_row != from_row

        def h_move(from_col, to_col):
            """Horizontal move on current row using count-move."""
            dc = to_col - from_col
            if dc == 0:
                return
            step('l' if dc > 0 else 'h', count=abs(dc))

        # Step 1: reach target row, sidestepping first if shield blocks the path
        if player.row != target_row:
            if row_blocked(player.row, target_row, player.col):
                # Move one column away from the shield column before going vertical
                avoid = player.col + 1 if player.col < room.cols - 2 else player.col - 1
                h_move(player.col, avoid)
            dr = target_row - player.row
            step('j' if dr > 0 else 'k', count=abs(dr))

        # Step 2: reach target col, detouring via adjacent row if shield blocks
        if player.col == target_col:
            return
        if col_blocked(player.row, player.col, target_col):
            detour_row = player.row - 1 if player.row > 1 else player.row + 1
            step('k' if detour_row < player.row else 'j')
            h_move(player.col, target_col)
            step('j' if target_row > player.row else 'k')
        else:
            h_move(player.col, target_col)

    def kill_nearest_goblin():
        """Move to and kill the goblin nearest to the player."""
        gobs = alive_goblins()
        if not gobs:
            return
        g = min(gobs, key=lambda e: abs(e.row - player.row) + abs(e.col - player.col))
        move_to(g.row, g.col)
        interact()  # x goblin

    def kill_all_goblins():
        """Kill every live goblin one at a time, routing around shield as needed."""
        while alive_goblins():
            kill_nearest_goblin()

    def navigate_to_warden():
        """Reach warden's cell from the unshielded side."""
        w = warden()
        if w is None:
            return
        sh = shield()
        sh_col = sh.col if sh else None

        if sh_col is None or sh_col < w.col:
            # Shield LEFT or gone — approach from right, then step left onto warden col
            # Use move_to a column right of warden, then h onto warden
            safe_col = w.col + 2  # safely right of warden (shield is left)
            # Make sure safe_col is in bounds
            safe_col = min(safe_col, room.cols - 2)
            move_to(w.row, safe_col)
            # Step left onto warden
            while player.col > w.col:
                step('h')
        else:
            # Shield RIGHT — approach from left
            move_to(w.row, w.col - 1)
            step('l')  # step right onto warden

    # ─────────────────────────────────────────────────────────────────────────
    # Phase 1: Enter boss room.
    # $ from (3,0): fog stops at seal_door col 16 (last visible cell).
    # x seal_door: opens door, reveals boss room.
    # $ from (3,16): now reaches col 25 (before shield at col 26).
    # k/$/j/0: navigate via row 2 to land on warden's cell (3,27).
    # ─────────────────────────────────────────────────────────────────────────
    step('$')          # (3,0)  → (3,16)
    interact()         # x seal_door → reveals boss room
    step('$')          # (3,16) → (3,25)
    step('k')          # (3,25) → (2,25)
    step('$')          # (2,25) → (2,37)
    step('j')          # (2,37) → (3,37)
    step('0')          # (3,37) → (3,27) [warden cell; shield at 26 blocks 0 further]

    # ── Phase 2: Kill timer-spawned first wave, then combat loop ─────────────
    # By the time we reach (3,27), timer-spawned goblins are approaching.
    # Kill them first (before hitting warden) so we don't get double-batches.
    kill_all_goblins()   # kill first timer-wave; warden moves + shield flips
    navigate_to_warden()

    for hit_num in range(1, 6):
        log(f'--- Hit #{hit_num} ---')
        interact()            # x warden (spawns hit-triggered goblins if hp>0)
        kill_all_goblins()    # kill all; warden moves + shield flips after last kill
        if hit_num < 5:
            navigate_to_warden()

    # ── Phase 3: Reach exit ───────────────────────────────────────────────────
    w = warden()
    if w is not None:
        raise RuntimeError(f'warden still alive at ({w.row},{w.col})')

    # Remove boss_seal (done automatically by _check_boss_cleared in real game)
    boss_seal = next((e for e in room.entities if e.alive and e.kind == 'boss_seal'), None)
    if boss_seal:
        room.kill_entity(boss_seal)

    step('G')   # G: go to exit (3,39), 1 key
    return cost[0]


if __name__ == '__main__':
    verbose = '-v' in sys.argv
    results = []
    for seed in range(20):
        try:
            c = simulate(seed, verbose=verbose and seed == 0)
            results.append(c)
            print(f'seed={seed:2d}: cost={c}')
        except Exception as e:
            print(f'seed={seed:2d}: FAIL ({e})')
    if results:
        print(f'\nmin={min(results)}  max={max(results)}  '
              f'mean={sum(results)/len(results):.1f}  n={len(results)}/20')
