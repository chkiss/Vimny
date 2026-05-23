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
        if ent and ent.kind in ('door', 'locked_door', 'seal_door', 'boss_seal'):
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
        if ent and ent.kind in ('door', 'locked_door', 'seal_door', 'boss_seal'):
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
        if ent.kind == 'dynamite':  return '!'
        if ent.kind == 'goblin':    return 'g'
        if ent.kind == 'warden':    return 'W'
        return '.'
    ct = room.cells[r][c]
    return '#' if ct in (CellType.WALL, CellType.WOOD_WALL) else '.'


def _is_word_char(ch: str) -> bool:
    return ch.isalpha() or ch.isdigit() or ch == '_'


def _cross_water(room, r: int, c: int) -> bool:
    """Like is_passable but also allows landing on water (for $, 0, ^ scans)."""
    if r < 0 or r >= room.rows or c < 0 or c >= room.cols:
        return False
    if room.cells[r][c] not in (CellType.FLOOR, CellType.CORRIDOR, CellType.WATER):
        return False
    if (r, c) in room.fog_cells:
        return False
    ent = room.entity_at(r, c)
    return ent is None or ent.kind not in ('locked_door', 'shield', 'boss_seal')


_PAIRS_OPEN  = {'(': ')', '[': ']', '{': '}'}
_PAIRS_CLOSE = {')': '(', ']': '[', '}': '{'}


def _leftmost_passable(room, row: int):
    """First passable column on a row, or None if the row has none."""
    for c in range(room.cols):
        if room.is_passable(row, c):
            return c
    return None


def _first_non_blank_col(room, row: int):
    """First-non-blank column on a row: the first rune start if any, else the
    leftmost passable column. None if the row has no passable cell."""
    left = None
    for c in range(room.cols):
        if room.is_passable(row, c):
            if left is None:
                left = c
            if room.rune_at(row, c) is not None:
                return c
    return left


def _bracket_at(room, row: int, c: int):
    """The bracket char ()[]{} at (row, c) if a rune symbol there is one, else None."""
    ru = room.rune_at(row, c)
    if ru is not None:
        ch = ru.symbols[c - ru.col]
        if ch in _PAIRS_OPEN or ch in _PAIRS_CLOSE:
            return ch
    return None


def _row_has_rune(room, row: int) -> bool:
    return any(room.rune_at(row, c) is not None for c in range(room.cols))


def _sentence_starts(room, row: int) -> list:
    """Columns on `row` where a sentence begins. The first non-void rune starts
    a sentence; a rune symbol in '.!?' ends one, so the next non-void rune
    after it starts the next. Row-scoped (cross-row flow can be added later)."""
    starts = []
    pending = True
    for c in range(room.cols):
        ru = room.rune_at(row, c)
        if ru is None or ru.kind == 'void':
            continue
        if pending:
            starts.append(c)
            pending = False
        if ru.symbols[c - ru.col] in '.!?':
            pending = True
    return starts


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
                if not _cross_water(room, row, c):
                    break
                left = c
            if left != player.col:
                player.col = left
                moved = True
        elif motion == '$':
            row = player.row
            best = None
            for c in range(player.col + 1, room.cols):
                if not _cross_water(room, row, c):
                    break
                best = c
            if best is not None:
                player.col = best
                moved = True
        elif motion == '^':
            row = player.row
            left = player.col
            for c in range(player.col - 1, -1, -1):
                if not _cross_water(room, row, c):
                    break
                left = c
            right = player.col
            for c in range(player.col + 1, room.cols):
                if not _cross_water(room, row, c):
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
                ch   = cur.symbols[player.col - cur.col]
                wc   = _is_word_char(ch)
                scan = player.col + 1
                while scan < room.cols and room.is_passable(row, scan):
                    ru2 = room.rune_at(row, scan)
                    if ru2 is None or ru2.kind == 'void':
                        break
                    ch2 = ru2.symbols[scan - ru2.col]
                    if _is_word_char(ch2) != wc:
                        break
                    scan += 1
            else:
                scan = player.col + 1
            best = None
            for nc in range(scan, room.cols):
                if not room.is_passable(row, nc):
                    break
                ru = room.rune_at(row, nc)
                if ru and ru.kind != 'void':
                    best = nc
                    break
            if best is not None:
                player.col = best
                moved = True
            else:
                break
        elif motion == 'b':
            row = player.row
            cur = room.rune_at(row, player.col)
            if cur and cur.kind != 'void':
                ch  = cur.symbols[player.col - cur.col]
                wc  = _is_word_char(ch)
                run_start = player.col
                for sc in range(player.col - 1, -1, -1):
                    if not room.is_passable(row, sc):
                        break
                    ru2 = room.rune_at(row, sc)
                    if ru2 is None or ru2.kind == 'void':
                        break
                    ch2 = ru2.symbols[sc - ru2.col]
                    if _is_word_char(ch2) != wc:
                        break
                    run_start = sc
                if run_start < player.col:
                    player.col = run_start
                    moved = True
                    continue
                prev_scan = player.col - 1
            else:
                prev_scan = player.col - 1
            sc = prev_scan
            while sc >= 0 and room.is_passable(row, sc):
                ru = room.rune_at(row, sc)
                if ru and ru.kind != 'void':
                    break
                sc -= 1
            if sc >= 0 and room.is_passable(row, sc):
                ru = room.rune_at(row, sc)
                if ru and ru.kind != 'void':
                    ch2 = ru.symbols[sc - ru.col]
                    wc2 = _is_word_char(ch2)
                    rs  = sc
                    for sc2 in range(sc - 1, -1, -1):
                        if not room.is_passable(row, sc2):
                            break
                        ru2 = room.rune_at(row, sc2)
                        if ru2 is None or ru2.kind == 'void':
                            break
                        ch3 = ru2.symbols[sc2 - ru2.col]
                        if _is_word_char(ch3) != wc2:
                            break
                        rs = sc2
                    player.col = rs
                    moved = True
                else:
                    break
            else:
                break
        elif motion == 'e':
            row = player.row
            cur = room.rune_at(row, player.col)
            if cur and cur.kind != 'void':
                ch   = cur.symbols[player.col - cur.col]
                wc   = _is_word_char(ch)
                pos  = player.col + 1
                while pos < room.cols and room.is_passable(row, pos):
                    ru2 = room.rune_at(row, pos)
                    if ru2 is None or ru2.kind == 'void':
                        break
                    ch2 = ru2.symbols[pos - ru2.col]
                    if _is_word_char(ch2) != wc:
                        break
                    pos += 1
                end = pos - 1
                if end > player.col:
                    player.col = end
                    moved = True
                    continue
                scan = pos
            else:
                scan = player.col + 1
            best = None
            for nc in range(scan, room.cols):
                if not room.is_passable(row, nc):
                    break
                ru = room.rune_at(row, nc)
                if ru and ru.kind != 'void':
                    ch2  = ru.symbols[nc - ru.col]
                    wc2  = _is_word_char(ch2)
                    epos = nc + 1
                    while epos < room.cols and room.is_passable(row, epos):
                        ru3 = room.rune_at(row, epos)
                        if ru3 is None or ru3.kind == 'void':
                            break
                        ch3 = ru3.symbols[epos - ru3.col]
                        if _is_word_char(ch3) != wc2:
                            break
                        epos += 1
                    best = epos - 1
                    break
            if best is not None:
                player.col = best
                moved = True
            else:
                break
        elif motion == 'W':
            row = player.row
            cur = room.rune_at(row, player.col)
            if cur and cur.kind != 'void':
                scan = cur.col + len(cur.symbols)
            else:
                scan = player.col + 1
            # skip rest of current WORD (adjacent non-void clusters, no floor gap)
            while scan < room.cols and room.is_passable(row, scan):
                ru = room.rune_at(row, scan)
                if ru and ru.kind != 'void':
                    scan = ru.col + len(ru.symbols)
                else:
                    break
            # skip whitespace (floor gaps) — W stops at walls
            while scan < room.cols and room.is_passable(row, scan) and not room.rune_at(row, scan):
                scan += 1
            found = None
            if scan < room.cols and room.is_passable(row, scan):
                ru = room.rune_at(row, scan)
                if ru and ru.kind != 'void':
                    found = ru.col
            if found is not None:
                player.col = found
                moved = True
            else:
                break
        elif motion == 'B':
            row = player.row
            pos = player.col
            cur = room.rune_at(row, pos)
            if cur and cur.kind != 'void':
                # Find start of current WORD (leftmost adjacent cluster)
                word_start = cur.col
                check = cur.col - 1
                while check >= 0 and room.is_passable(row, check):
                    prev_ru = room.rune_at(row, check)
                    if prev_ru and prev_ru.kind != 'void':
                        word_start = prev_ru.col
                        check = prev_ru.col - 1
                    else:
                        break
                if word_start < pos:
                    # Inside WORD: jump to its start
                    player.col = word_start
                    moved = True
                    continue
                # At start of WORD: jump to previous WORD
                pos = word_start - 1
            else:
                pos = pos - 1
            # Skip whitespace backward
            while pos >= 0 and room.is_passable(row, pos) and not room.rune_at(row, pos):
                pos -= 1
            if pos >= 0 and room.is_passable(row, pos):
                ru = room.rune_at(row, pos)
                if ru and ru.kind != 'void':
                    word_start = ru.col
                    check = ru.col - 1
                    while check >= 0 and room.is_passable(row, check):
                        prev_ru = room.rune_at(row, check)
                        if prev_ru and prev_ru.kind != 'void':
                            word_start = prev_ru.col
                            check = prev_ru.col - 1
                        else:
                            break
                    player.col = word_start
                    moved = True
                else:
                    break
            else:
                break
        elif motion == 'E':
            row = player.row
            cur = room.rune_at(row, player.col)
            if cur and cur.kind != 'void':
                # Find end of current WORD (last char of last adjacent cluster)
                pos = cur.col + len(cur.symbols)
                while pos < room.cols and room.is_passable(row, pos):
                    ru = room.rune_at(row, pos)
                    if ru and ru.kind != 'void':
                        pos = ru.col + len(ru.symbols)
                    else:
                        break
                end = pos - 1
                if end > player.col:
                    player.col = end
                    moved = True
                    continue
                pos = end + 1
            else:
                pos = player.col + 1
            # Skip whitespace
            while pos < room.cols and room.is_passable(row, pos) and not room.rune_at(row, pos):
                pos += 1
            if pos < room.cols and room.is_passable(row, pos):
                ru = room.rune_at(row, pos)
                if ru and ru.kind != 'void':
                    pos = ru.col + len(ru.symbols)
                    while pos < room.cols and room.is_passable(row, pos):
                        ru2 = room.rune_at(row, pos)
                        if ru2 and ru2.kind != 'void':
                            pos = ru2.col + len(ru2.symbols)
                        else:
                            break
                    player.col = pos - 1
                    moved = True
                else:
                    break
            else:
                break
        elif motion == 'G':
            if room.exit_pos:
                player.row, player.col = room.exit_pos
                moved = True
        elif motion == 'gg':
            player.row, player.col = room.entry
            moved = True
        elif motion == 'ge':
            # Backward to the end of the previous word (a non-void RuneCluster).
            row = player.row
            best = None
            nc = player.col - 1
            while nc >= 0:
                if not room.is_passable(row, nc):
                    break
                ru = room.rune_at(row, nc)
                if ru and ru.kind != 'void':
                    end_col = ru.col + len(ru.symbols) - 1
                    if end_col < player.col:
                        best = end_col
                        break
                    nc = ru.col - 1   # cursor at/within this word: skip left of its start
                    continue
                nc -= 1
            if best is not None:
                player.col = best
                moved = True
            else:
                break
        elif motion == 'gE':
            # Backward to the end of the previous WORD (maximal run of adjacent
            # non-void clusters, delimited by a floor gap or wall).
            row = player.row
            best = None
            nc = player.col - 1
            while nc >= 0:
                if not room.is_passable(row, nc):
                    break
                ru = room.rune_at(row, nc)
                if ru and ru.kind != 'void':
                    end = ru.col + len(ru.symbols) - 1   # extend right to WORD end
                    cc = end + 1
                    while cc < room.cols and room.is_passable(row, cc):
                        r2 = room.rune_at(row, cc)
                        if r2 and r2.kind != 'void':
                            end = r2.col + len(r2.symbols) - 1
                            cc = end + 1
                        else:
                            break
                    if end < player.col:
                        best = end
                        break
                    nc = ru.col - 1   # cursor within this WORD: skip left of its start
                    continue
                nc -= 1
            if best is not None:
                player.col = best
                moved = True
            else:
                break
        elif motion in ('H', 'M', 'L'):
            # Screen-relative row jump. In a room that fits the viewport this is
            # room-relative: H=top, L=bottom, M=middle passable row. Lands on the
            # first non-blank column of the target row (vim-faithful).
            prows = [r for r in range(room.rows)
                     if _first_non_blank_col(room, r) is not None]
            if not prows:
                break
            if motion == 'H':
                tr = prows[0]
            elif motion == 'L':
                tr = prows[-1]
            else:
                tr = prows[len(prows) // 2]
            tc = _first_non_blank_col(room, tr)
            if (tr, tc) != (player.row, player.col):
                player.row, player.col = tr, tc
                moved = True
            else:
                break
        elif motion == '%':
            # Jump to the matching bracket. If not on a bracket, scan right on the
            # row for the first one (vim behaviour). Row-scoped, nesting-aware.
            row = player.row
            bch = _bracket_at(room, row, player.col)
            start = player.col if bch is not None else None
            if start is None:
                for c in range(player.col + 1, room.cols):
                    if room.cells[row][c] in (CellType.WALL, CellType.WOOD_WALL):
                        break
                    b = _bracket_at(room, row, c)
                    if b is not None:
                        start, bch = c, b
                        break
            tgt = None
            if start is not None:
                forward = bch in _PAIRS_OPEN
                want    = _PAIRS_OPEN[bch] if forward else _PAIRS_CLOSE[bch]
                scan    = range(start, room.cols) if forward else range(start, -1, -1)
                depth = 0
                for c in scan:
                    if room.cells[row][c] in (CellType.WALL, CellType.WOOD_WALL):
                        break
                    b = _bracket_at(room, row, c)
                    if b == bch:
                        depth += 1
                    elif b == want:
                        depth -= 1
                        if depth == 0:
                            tgt = c
                            break
            if tgt is not None and tgt != player.col:
                player.col = tgt
                moved = True
            else:
                break
        elif motion in ('{', '}'):
            # Paragraph jump: a blank row = a passable row with no runes.
            row = player.row
            rng = range(row + 1, room.rows) if motion == '}' else range(row - 1, -1, -1)
            target_row = None
            for r in rng:
                if _leftmost_passable(room, r) is not None and not _row_has_rune(room, r):
                    target_row = r
                    break
            if target_row is None:
                # No blank row in that direction: fall to the extreme passable row.
                prows = [r for r in range(room.rows) if _leftmost_passable(room, r) is not None]
                if prows:
                    target_row = prows[-1] if motion == '}' else prows[0]
            if target_row is None:
                break
            tc = _leftmost_passable(room, target_row)
            if (target_row, tc) != (player.row, player.col):
                player.row, player.col = target_row, tc
                moved = True
            else:
                break
        elif motion in ('(', ')'):
            # Sentence jump (row-scoped): start of next/previous sentence.
            starts = _sentence_starts(room, player.row)
            if motion == ')':
                nxt = [s for s in starts if s > player.col]
                if nxt:
                    player.col = nxt[0]
                    moved = True
                else:
                    break
            else:
                prev = [s for s in starts if s < player.col]
                if prev:
                    player.col = prev[-1]
                    moved = True
                else:
                    break
        elif motion in ('f', 'F', 't', 'T'):
            if target is None:
                break
            if _apply_find(player, motion, target, room):
                player.last_f = (motion, target)
                moved = True
        elif motion == ';':
            if player.last_f:
                m, tgt = player.last_f
                moved |= _apply_find(player, m, tgt, room)
        elif motion == ',':
            if player.last_f:
                m, tgt = player.last_f
                rev = {'f': 'F', 'F': 'f', 't': 'T', 'T': 't'}[m]
                moved |= _apply_find(player, rev, tgt, room)
    return moved


def _apply_find(player, motion: str, target: str, room) -> bool:
    """Raw f/F/t/T scan without updating player.last_f. Used by ; and ,."""
    row = player.row
    fwd = motion in ('f', 't')
    scan = range(player.col + 1, room.cols) if fwd else range(player.col - 1, -1, -1)
    _SCAN_BLOCK = frozenset(('shield', 'locked_door', 'seal_door', 'boss_seal'))
    for nc in scan:
        if room.cells[row][nc] in (CellType.WALL, CellType.WOOD_WALL):
            break
        ent = room.entity_at(row, nc)
        if ent and ent.kind in _SCAN_BLOCK:
            break
        if _cell_char(room, row, nc) == target:
            if motion in ('f', 'F'):
                dest = nc
            elif motion == 't':
                dest = nc - 1
            else:  # T
                dest = nc + 1
            if dest != player.col and room.is_passable(row, dest):
                player.col = dest
                return True
            break
    return False
