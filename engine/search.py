"""Block F — search (/ ? n N * #).

Searches character runs by **Vim regular expression** over the grid in reading
order (row-major), wrapping around. A match lands the cursor on the first cell
of the (effective) match. Plain words contain no regex metacharacters, so they
behave exactly like the substring search Vimny shipped before regex landed; a
pattern that can't be translated falls back to a literal substring too.

See engine/vimregex.py for the supported atoms (\\w \\d . ^ $ \\< \\> * \\+
[..] \\| \\(\\) \\zs \\ze \\c \\v …).
"""
from __future__ import annotations
from engine.vimregex import compile_vim


def _first_offset(s: str, pattern: str) -> int:
    """Column offset of the first match of `pattern` in `s`, or -1."""
    vp = compile_vim(pattern)
    if vp is not None:
        span = vp.first_in(s)
        return span[0] if span is not None else -1
    return s.find(pattern)                              # literal fallback


def _spans(s: str, pattern: str):
    """All non-overlapping (start, end) match spans of `pattern` in `s`."""
    vp = compile_vim(pattern)
    if vp is not None:
        return list(vp.finditer(s))
    out, start = [], 0                                  # literal fallback
    while True:
        i = s.find(pattern, start)
        if i < 0:
            return out
        out.append((i, i + len(pattern)))
        start = i + max(1, len(pattern))


def _match_positions(room, pattern: str) -> list:
    """All (row, col) of the first match of `pattern` within each cluster,
    sorted in reading order."""
    out = []
    for ru in room.char_runs:
        idx = _first_offset(''.join(ru.symbols), pattern)
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


def match_cells(room, pattern: str) -> set:
    """Every (row, col) covered by a NON-overlapping match of `pattern` in any
    character run — the cell set for hlsearch / incsearch highlighting."""
    cells: set = set()
    if not pattern:
        return cells
    for ru in room.char_runs:
        s = ''.join(ru.symbols)
        for start, end in _spans(s, pattern):
            for k in range(start, max(start + 1, end)):     # ≥1 cell even if zero-width
                cells.add((ru.row, ru.col + k))
    return cells


def word_under_cursor(room, player):
    """Full symbol string of the cluster under the cursor (for * / #), or None."""
    ru = room.char_run_at(player.row, player.col)
    return ''.join(ru.symbols) if ru is not None else None
