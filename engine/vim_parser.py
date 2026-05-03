"""
Parse Vim-grammar keystrokes: [count][operator][motion] or [count][motion].
Returns action dicts consumed by the game loop.
"""
from __future__ import annotations
from engine.modes import Mode

MOTIONS  = set('hjklwbeGg0^${}')
OPERATORS = set('dyc')
COUNTS   = set('123456789')

def parse(buf: str, mode: Mode) -> tuple[dict | None, str]:
    """
    Returns (action, remaining_buf).
    action is None if input is incomplete (need more keys).
    action is {'type': 'unknown'} for unrecognised sequences.
    """
    if not buf:
        return None, buf

    if mode != Mode.NORMAL:
        return None, buf

    i = 0
    count = ''

    # Count prefix — '0' is only a count digit after a non-zero digit has started
    while i < len(buf) and (buf[i] in COUNTS or (count and buf[i] == '0')):
        count += buf[i]
        i += 1

    if i >= len(buf):
        return None, buf  # incomplete

    count_n = int(count) if count else 1
    ch = buf[i]

    # gg
    if ch == 'g':
        if i + 1 >= len(buf):
            return None, buf
        if buf[i+1] == 'g':
            return {'type': 'motion', 'motion': 'gg', 'count': count_n}, buf[i+2:]
        return {'type': 'unknown'}, buf[i+2:]

    # f/F/t/T — need one more char
    if ch in 'fFtT':
        if i + 1 >= len(buf):
            return None, buf
        target = buf[i+1]
        return {'type': 'motion', 'motion': ch, 'target': target, 'count': count_n}, buf[i+2:]

    # m/'/` — mark commands
    if ch in "m'`":
        if i + 1 >= len(buf):
            return None, buf
        reg = buf[i+1]
        return {'type': 'mark', 'cmd': ch, 'reg': reg}, buf[i+2:]

    # Operators
    if ch in OPERATORS:
        op = ch
        if i + 1 >= len(buf):
            return None, buf
        nch = buf[i+1]

        # Doubled operator: dd, yy, cc
        if nch == op:
            return {'type': 'operator', 'op': op, 'motion': 'line', 'count': count_n}, buf[i+2:]

        # D / C / Y (capitalised shortcuts)
        # handled below via capital branch

        # count before motion
        motion_count = ''
        j = i + 1
        while j < len(buf) and buf[j] in COUNTS:
            motion_count += buf[j]
            j += 1
        if j >= len(buf):
            return None, buf
        motion_ch = buf[j]
        if motion_ch == 'g':
            if j + 1 >= len(buf):
                return None, buf
            if buf[j+1] == 'g':
                mc = int(motion_count) if motion_count else 1
                return {'type': 'operator', 'op': op, 'motion': 'gg', 'count': count_n, 'motion_count': mc}, buf[j+2:]
            return {'type': 'unknown'}, buf[j+2:]
        if motion_ch in 'fFtT':
            if j + 1 >= len(buf):
                return None, buf
            tgt = buf[j+1]
            mc = int(motion_count) if motion_count else 1
            return {'type': 'operator', 'op': op, 'motion': motion_ch, 'target': tgt, 'count': count_n, 'motion_count': mc}, buf[j+2:]
        if motion_ch in MOTIONS:
            mc = int(motion_count) if motion_count else 1
            return {'type': 'operator', 'op': op, 'motion': motion_ch, 'count': count_n, 'motion_count': mc}, buf[j+1:]
        return {'type': 'unknown'}, buf[j+1:]

    # Capital D/C
    if ch in 'DC':
        op = ch.lower()
        return {'type': 'operator', 'op': op, 'motion': '$', 'count': count_n}, buf[i+1:]

    # p / P — paste (standalone commands, not operator+motion)
    if ch == 'p':
        return {'type': 'paste', 'before': False, 'count': count_n}, buf[i+1:]
    if ch == 'P':
        return {'type': 'paste', 'before': True, 'count': count_n}, buf[i+1:]

    # s — substitute (cut in place, game-loop decides behaviour)
    if ch == 's':
        return {'type': 'substitute', 'count': count_n}, buf[i+1:]

    # Plain motion
    if ch in MOTIONS:
        return {'type': 'motion', 'motion': ch, 'count': count_n}, buf[i+1:]

    # x — interact (open door / loot chest)
    if ch == 'x':
        return {'type': 'interact'}, buf[i+1:]

    # u / Ctrl-R
    if ch == 'u':
        return {'type': 'undo'}, buf[i+1:]
    if ch == '\x12':  # Ctrl-R
        return {'type': 'redo'}, buf[i+1:]

    # : — enter command mode
    if ch == ':':
        return {'type': 'enter_mode', 'mode': 'command'}, buf[i+1:]

    # i/a/o/I/A/O — enter insert mode
    if ch in 'iaoIAO':
        return {'type': 'enter_mode', 'mode': 'insert', 'variant': ch}, buf[i+1:]

    # v/V/Ctrl-V
    if ch == 'v':
        return {'type': 'enter_mode', 'mode': 'visual'}, buf[i+1:]
    if ch == 'V':
        return {'type': 'enter_mode', 'mode': 'visual_line'}, buf[i+1:]
    if ch == '\x16':  # Ctrl-V
        return {'type': 'enter_mode', 'mode': 'visual_block'}, buf[i+1:]

    return {'type': 'unknown'}, buf[i+1:]
