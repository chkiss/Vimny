"""Block F — search (/ ? n N * #).

Searches rune clusters by **substring** (case-sensitive) over the grid in
reading order (row-major), wrapping around. A match lands the cursor on the
first matched character's column.
"""
from __future__ import annotations


def _match_positions(room, pattern: str) -> list:
    """All (row, col) of the first occurrence of `pattern` within each cluster,
    sorted in reading order."""
    out = []
    for ru in room.char_runs:
        idx = ''.join(ru.symbols).find(pattern)
        if idx >= 0:
            out.append((ru.row, ru.col + idx))
    out.sort()
    return out


def find_next(room, player, pattern: str, forward: bool):
    """Next match from the cursor (wrapping) → (row, col), or None if no match."""
    if not pattern:
        return None
    positions = _match_positions(room, pattern)
    if not positions:
        return None
    cur = (player.row, player.col)
    if forward:
        ahead = [p for p in positions if p > cur]
        return ahead[0] if ahead else positions[0]          # wrap to first
    behind = [p for p in positions if p < cur]
    return behind[-1] if behind else positions[-1]          # wrap to last


def word_under_cursor(room, player):
    """Full symbol string of the cluster under the cursor (for * / #), or None."""
    ru = room.char_run_at(player.row, player.col)
    return ''.join(ru.symbols) if ru is not None else None
