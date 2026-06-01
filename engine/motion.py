"""Motion execution: apply_motion, move_player, and related helpers."""
from __future__ import annotations
import unicodedata
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
    ru = room.char_run_at(r, c)
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
    if ch.isalpha() or ch.isdigit() or ch == '_':
        return True
    # Vim's utf_class() treats So (Symbol,Other) as word chars; Po and Sm are punctuation.
    return unicodedata.category(ch) == 'So'


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


def _segment_left(room, row: int, col: int):
    """Leftmost floor cell contiguous with `col` on `row` — the left edge of the
    player's own segment. Bounded by terrain only (walls/water), so a paragraph
    jump stays out of separate rooms but still reaches the leftmost blank past a
    blocking ENTITY like the Warden's shield. None if `col` isn't on floor (the
    caller falls back to the row's global leftmost)."""
    def _floor(c: int) -> bool:
        return (room.cells[row][c] in (CellType.FLOOR, CellType.CORRIDOR)
                and (row, c) not in room.fog_cells)
    if not _floor(col):
        return None
    c = col
    while c - 1 >= 0 and _floor(c - 1):
        c -= 1
    return c


def _rightmost_passable(room, row: int):
    """Last passable column on a row, or None if the row has none — the end of the
    line (the corridor / ledge edge), used by `A` to append at the line's end."""
    for c in range(room.cols - 1, -1, -1):
        if room.is_passable(row, c):
            return c
    return None


def _first_non_blank_col(room, row: int):
    """First-non-blank column on a row: the first character if any, else the
    leftmost passable column. None if the row has no passable cell."""
    left = None
    for c in range(room.cols):
        if room.is_passable(row, c):
            if left is None:
                left = c
            if room.char_run_at(row, c) is not None:
                return c
    return left


def _bracket_at(room, row: int, c: int):
    """The bracket char ()[]{} at (row, c) if a character there is one, else None."""
    ru = room.char_run_at(row, c)
    if ru is not None:
        ch = ru.symbols[c - ru.col]
        if ch in _PAIRS_OPEN or ch in _PAIRS_CLOSE:
            return ch
    return None


def _row_has_rune(room, row: int) -> bool:
    return row in room._char_run_rows


def _sentence_terminates(room, row: int, c: int) -> bool:
    """A '.!?' at (row, c) ends a sentence only if followed by whitespace, the
    end of the line, or a single closing bracket/quote then whitespace/EOL —
    Vim-faithful. So a decimal point (the '.' in '17.3', followed by a digit)
    does NOT split the sentence."""
    nc = c + 1
    if nc < room.cols:
        ru = room.char_run_at(row, nc)
        if ru is not None and ru.symbols[nc - ru.col] in ')]}"\'':
            nc += 1                       # skip one closing bracket/quote
    if nc >= room.cols:
        return True                       # end of line
    ru = room.char_run_at(row, nc)
    return ru is None or ru.symbols[nc - ru.col] == ' '   # gap/floor or a space


def _sentence_starts(room, row: int) -> list:
    """Columns on `row` where a sentence begins. The first non-void rune starts
    a sentence; a '.!?' followed by whitespace/EOL ends one, so the next
    non-void rune after it starts the next. Row-scoped (cross-row flow can be
    added later)."""
    starts = []
    pending = True
    for c in range(room.cols):
        ent = room.entity_at(row, c)
        if ent is not None and ent.kind == 'dynamite':
            # a !-charge renders as '!' and ends a sentence when followed by space/EOL
            if _sentence_terminates(room, row, c):
                pending = True
            continue
        ru = room.char_run_at(row, c)
        if ru is None or ru.kind == 'void':
            continue
        if pending:
            starts.append(c)
            pending = False
        if ru.symbols[c - ru.col] in '.!?' and _sentence_terminates(room, row, c):
            pending = True
    return starts


def _sentence_starts_all(room) -> list:
    """Every sentence start in the buffer, in reading order — (row, col) tuples,
    top row to bottom and left to right within a row. Buffer-wide companion to
    _sentence_starts (which stays row-scoped for the is/as text objects)."""
    out = []
    for r in range(room.rows):
        for c in _sentence_starts(room, r):
            out.append((r, c))
    return out


def apply_motion(player, motion, count, room, target=None, count_given: bool = True, game_h: int = 0):
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
                if room.char_run_at(row, c):
                    target = c
                    break
            if target != player.col:
                player.col = target
                moved = True
        elif motion == 'w':
            row = player.row
            cur = room.char_run_at(row, player.col)
            if cur and cur.kind != 'void':
                ch   = cur.symbols[player.col - cur.col]
                wc   = _is_word_char(ch)
                scan = player.col + 1
                while scan < room.cols and room.is_passable(row, scan):
                    ru2 = room.char_run_at(row, scan)
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
                ru = room.char_run_at(row, nc)
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
            cur = room.char_run_at(row, player.col)
            if cur and cur.kind != 'void':
                ch  = cur.symbols[player.col - cur.col]
                wc  = _is_word_char(ch)
                run_start = player.col
                for sc in range(player.col - 1, -1, -1):
                    if not room.is_passable(row, sc):
                        break
                    ru2 = room.char_run_at(row, sc)
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
                ru = room.char_run_at(row, sc)
                if ru and ru.kind != 'void':
                    break
                sc -= 1
            if sc >= 0 and room.is_passable(row, sc):
                ru = room.char_run_at(row, sc)
                if ru and ru.kind != 'void':
                    ch2 = ru.symbols[sc - ru.col]
                    wc2 = _is_word_char(ch2)
                    rs  = sc
                    for sc2 in range(sc - 1, -1, -1):
                        if not room.is_passable(row, sc2):
                            break
                        ru2 = room.char_run_at(row, sc2)
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
            cur = room.char_run_at(row, player.col)
            if cur and cur.kind != 'void':
                ch   = cur.symbols[player.col - cur.col]
                wc   = _is_word_char(ch)
                pos  = player.col + 1
                while pos < room.cols and room.is_passable(row, pos):
                    ru2 = room.char_run_at(row, pos)
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
                ru = room.char_run_at(row, nc)
                if ru and ru.kind != 'void':
                    ch2  = ru.symbols[nc - ru.col]
                    wc2  = _is_word_char(ch2)
                    epos = nc + 1
                    while epos < room.cols and room.is_passable(row, epos):
                        ru3 = room.char_run_at(row, epos)
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
            cur = room.char_run_at(row, player.col)
            if cur and cur.kind != 'void':
                scan = cur.col + len(cur.symbols)
            else:
                scan = player.col + 1
            # skip rest of current WORD (adjacent non-void clusters, no floor gap)
            while scan < room.cols and room.is_passable(row, scan):
                ru = room.char_run_at(row, scan)
                if ru and ru.kind != 'void':
                    scan = ru.col + len(ru.symbols)
                else:
                    break
            # skip whitespace (floor gaps) — W stops at walls
            while scan < room.cols and room.is_passable(row, scan) and not room.char_run_at(row, scan):
                scan += 1
            found = None
            if scan < room.cols and room.is_passable(row, scan):
                ru = room.char_run_at(row, scan)
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
            cur = room.char_run_at(row, pos)
            if cur and cur.kind != 'void':
                # Find start of current WORD (leftmost adjacent cluster)
                word_start = cur.col
                check = cur.col - 1
                while check >= 0 and room.is_passable(row, check):
                    prev_ru = room.char_run_at(row, check)
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
            while pos >= 0 and room.is_passable(row, pos) and not room.char_run_at(row, pos):
                pos -= 1
            if pos >= 0 and room.is_passable(row, pos):
                ru = room.char_run_at(row, pos)
                if ru and ru.kind != 'void':
                    word_start = ru.col
                    check = ru.col - 1
                    while check >= 0 and room.is_passable(row, check):
                        prev_ru = room.char_run_at(row, check)
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
            cur = room.char_run_at(row, player.col)
            if cur and cur.kind != 'void':
                # Find end of current WORD (last char of last adjacent cluster)
                pos = cur.col + len(cur.symbols)
                while pos < room.cols and room.is_passable(row, pos):
                    ru = room.char_run_at(row, pos)
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
            while pos < room.cols and room.is_passable(row, pos) and not room.char_run_at(row, pos):
                pos += 1
            if pos < room.cols and room.is_passable(row, pos):
                ru = room.char_run_at(row, pos)
                if ru and ru.kind != 'void':
                    pos = ru.col + len(ru.symbols)
                    while pos < room.cols and room.is_passable(row, pos):
                        ru2 = room.char_run_at(row, pos)
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
            # nG → line n; bare G → last line. Always land on first non-blank.
            # Scan inward from the target row if it is a wall (no passable cells).
            if count_given:
                target_row = max(0, min(count - 1, room.rows - 1))
                direction = 1
            else:
                target_row = room.rows - 1
                direction = -1
            col = None
            r = target_row
            while 0 <= r < room.rows:
                col = _first_non_blank_col(room, r)
                if col is not None:
                    target_row = r
                    break
                r += direction
            if col is not None:
                player.row = target_row
                player.col = col
                moved = True
            break
        elif motion == 'gg':
            # {n}gg → line n (like {n}G); bare gg → first line. Always land on
            # first non-blank, scanning downward to the first passable row.
            # Mirror of the G branch; independent of spawn/exit (Vim-faithful).
            if count_given:
                target_row = max(0, min(count - 1, room.rows - 1))
            else:
                target_row = 0
            col = None
            r = target_row
            while 0 <= r < room.rows:
                col = _first_non_blank_col(room, r)
                if col is not None:
                    target_row = r
                    break
                r += 1
            if col is not None:
                player.row = target_row
                player.col = col
                moved = True
            break
        elif motion == 'ge':
            # Backward to the end of the previous word (a non-void CharRun).
            row = player.row
            best = None
            nc = player.col - 1
            while nc >= 0:
                if not room.is_passable(row, nc):
                    break
                ru = room.char_run_at(row, nc)
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
                ru = room.char_run_at(row, nc)
                if ru and ru.kind != 'void':
                    end = ru.col + len(ru.symbols) - 1   # extend right to WORD end
                    cc = end + 1
                    while cc < room.cols and room.is_passable(row, cc):
                        r2 = room.char_run_at(row, cc)
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
            # Viewport-relative when game_h is provided and room exceeds it;
            # otherwise room-relative (H=first, L=last, M=middle passable row).
            if game_h > 0 and room.rows > game_h:
                vr_s = max(0, min(player.row - game_h // 2, room.rows - game_h))
                row_range = range(vr_s, min(vr_s + game_h, room.rows))
            else:
                row_range = range(room.rows)
            prows = []
            for _r in row_range:
                if _first_non_blank_col(room, _r) is not None:
                    prows.append(_r)
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
            # Paragraph jump: a blank row = a passable row with no characters.
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
            # Land at the left edge of the player's OWN segment on that row, so
            # `}`/`{` can't vault a wall/moat into the entry or treasure room.
            tc = _segment_left(room, target_row, player.col)
            if tc is None:
                tc = _leftmost_passable(room, target_row)
            if (target_row, tc) != (player.row, player.col):
                player.row, player.col = target_row, tc
                moved = True
            else:
                break
        elif motion in ('(', ')'):
            # Sentence jump (buffer-wide): the next/previous sentence start
            # anywhere in the buffer — Vim-faithful, since sentences span lines.
            starts = _sentence_starts_all(room)
            cur = (player.row, player.col)
            if motion == ')':
                nxt = [s for s in starts if s > cur]
                if nxt:
                    player.row, player.col = nxt[0]
                    moved = True
                else:
                    break
            else:
                prev_s = [s for s in starts if s < cur]
                if prev_s:
                    player.row, player.col = prev_s[-1]
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
