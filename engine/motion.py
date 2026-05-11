"""Motion execution: apply_motion, move_player, and related helpers."""
from __future__ import annotations
from collections import deque
from engine.player import Player
from engine.modes import Mode
from engine.world import CellType


def _apply_esc(player: Player) -> None:
    player.mode = Mode.NORMAL


def move_player(player, dr, dc, room):
    nr, nc = player.row + dr, player.col + dc
    if not room.is_passable(nr, nc):
        return False
    player.row, player.col = nr, nc
    return True


def _fog_unreachable(room, start_r: int, start_c: int) -> None:
    """Initialise room.fog_cells: all floor/corridor cells not visible from start.

    Visibility is blocked at door and locked_door entities — BFS includes the
    door cell itself (it's visible) but does not expand through it.
    """
    foggable: set = set()
    for r in range(room.rows):
        for c in range(room.cols):
            if room.cells[r][c] in (CellType.FLOOR, CellType.CORRIDOR, CellType.WATER):
                foggable.add((r, c))

    reachable: set = set()
    q = deque([(start_r, start_c)])
    reachable.add((start_r, start_c))
    while q:
        r, c = q.popleft()
        ent = room.entity_at(r, c)
        if ent and ent.kind in ('door', 'locked_door'):
            continue
        for dr, dc in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            nb = (r + dr, c + dc)
            if nb not in reachable and nb in foggable:
                reachable.add(nb)
                q.append(nb)

    room.fog_cells = foggable - reachable


def _reveal_from(room, player_r: int, player_c: int) -> None:
    """After a door opens, remove all cells now visible from player from fog_cells."""
    if not room.fog_cells:
        return

    reachable: set = set()
    q = deque([(player_r, player_c)])
    reachable.add((player_r, player_c))
    while q:
        r, c = q.popleft()
        ent = room.entity_at(r, c)
        if ent and ent.kind in ('door', 'locked_door'):
            continue
        for dr, dc in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            nr, nc = r + dr, c + dc
            if (nr, nc) not in reachable:
                if room.cells[nr][nc] in (CellType.FLOOR, CellType.CORRIDOR, CellType.WATER):
                    reachable.add((nr, nc))
                    q.append((nr, nc))

    room.fog_cells -= reachable


def _cell_char(room, r: int, c: int) -> str:
    """Return the printable character at (r, c) for f/F/t/T target matching."""
    ru = room.rune_at(r, c)
    if ru:
        return ru.symbols[c - ru.col]
    ent = room.entity_at(r, c)
    if ent:
        if ent.kind == 'door':         return '+'
        if ent.kind == 'locked_door':  return '+'
        if ent.kind == 'exit':         return 'E'
        if ent.kind == 'entry_marker': return '@'
        if ent.kind == 'dynamite':     return '!'
        return '?'
    ct = room.cells[r][c]
    return '#' if ct in (CellType.WALL, CellType.WOOD_WALL) else '.'


def apply_motion(player, motion, count, room, target=None):
    moved = False
    for _ in range(count):
        if motion == 'h':
            moved |= move_player(player, 0, -1, room)
        elif motion == 'j':
            moved |= move_player(player, 1,  0, room)
        elif motion == 'k':
            moved |= move_player(player, -1, 0, room)
        elif motion == 'l':
            moved |= move_player(player, 0,  1, room)
        elif motion == '0':
            row = player.row
            left = player.col
            for c in range(player.col - 1, -1, -1):
                if not room.is_passable(row, c):
                    break
                left = c
            if left != player.col:
                player.col = left
                moved = True
        elif motion == '$':
            row = player.row
            best = None
            for c in range(player.col + 1, room.cols):
                if not room.is_passable(row, c):
                    break
                best = c
            if best is not None:
                player.col = best
                moved = True
        elif motion == '^':
            row = player.row
            left = player.col
            for c in range(player.col - 1, -1, -1):
                if not room.is_passable(row, c):
                    break
                left = c
            right = player.col
            for c in range(player.col + 1, room.cols):
                if not room.is_passable(row, c):
                    break
                right = c
            target = left
            for c in range(left, right + 1):
                if room.rune_at(row, c):
                    target = c
                    break
            if target != player.col:
                player.col = target
                moved = True
        elif motion == 'w':
            row = player.row
            cur = room.rune_at(row, player.col)
            if cur and cur.kind != 'void':
                scan = cur.col + len(cur.symbols)
            else:
                scan = player.col + 1
            best = None
            for nc in range(scan, room.cols):
                if not room.is_passable(row, nc):
                    break
                ru = room.rune_at(row, nc)
                if ru and ru.kind != 'void':
                    best = ru.col
                    break
            if best is not None:
                player.col = best
                moved = True
            else:
                break
        elif motion == 'b':
            row = player.row
            cur = room.rune_at(row, player.col)
            if cur and cur.kind != 'void' and cur.col < player.col:
                player.col = cur.col
                moved = True
            else:
                limit = cur.col if (cur and cur.kind != 'void') else player.col
                best  = None
                for nc in range(limit - 1, -1, -1):
                    if not room.is_passable(row, nc):
                        break
                    ru = room.rune_at(row, nc)
                    if ru and ru.kind != 'void':
                        best = ru.col
                        break
                if best is not None:
                    player.col = best
                    moved = True
                else:
                    break
        elif motion == 'e':
            row = player.row
            cur = room.rune_at(row, player.col)
            if cur and cur.kind != 'void':
                end_col = cur.col + len(cur.symbols) - 1
                if end_col > player.col:
                    player.col = end_col
                    moved = True
                    continue
                scan = end_col + 1
            else:
                scan = player.col + 1
            best = None
            for nc in range(scan, room.cols):
                if not room.is_passable(row, nc):
                    break
                ru = room.rune_at(row, nc)
                if ru and ru.kind != 'void':
                    best = ru.col + len(ru.symbols) - 1
                    break
            if best is not None:
                player.col = best
                moved = True
            else:
                break
        elif motion == 'G':
            if room.exit_pos:
                player.row, player.col = room.exit_pos
                moved = True
        elif motion == 'gg':
            player.row, player.col = room.entry
            moved = True
        elif motion in ('f', 'F', 't', 'T'):
            if target is None:
                break
            row = player.row
            fwd  = motion in ('f', 't')
            scan = range(player.col + 1, room.cols) if fwd else range(player.col - 1, -1, -1)
            for nc in scan:
                if room.cells[row][nc] in (CellType.WALL, CellType.WOOD_WALL):
                    break  # walls block the scan; water does not
                if _cell_char(room, row, nc) == target:
                    if motion == 'f':
                        dest = nc
                    elif motion == 'F':
                        dest = nc
                    elif motion == 't':
                        dest = nc - 1
                    else:  # T
                        dest = nc + 1
                    if dest != player.col and room.is_passable(row, dest):
                        player.col = dest
                        moved = True
                    break
    return moved
