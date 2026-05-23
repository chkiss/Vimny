"""Block J — the jump list (Ctrl-o / Ctrl-i).

Large-distance motions (G, gg, %, { } ( ), search, marks) record the position
they jump *from*. Ctrl-o walks to older positions, Ctrl-i back to newer.
`jump_idx` is where the cursor sits in the list; it equals len(jump_list) when
the cursor is at a fresh position past the newest entry.
"""
from __future__ import annotations

_CAP = 100


def record_jump(player, pos) -> None:
    """Record `pos` (the position being jumped from). Drops any forward history."""
    jl = player.jump_list
    if player.jump_idx < len(jl):
        del jl[player.jump_idx:]          # leaving the middle: discard newer entries
    if not jl or jl[-1] != pos:
        jl.append(pos)
    while len(jl) > _CAP:
        jl.pop(0)
    player.jump_idx = len(jl)


def jump_back(player):
    """Ctrl-o: move to an older position. Returns (row, col) or None."""
    jl = player.jump_list
    if not jl:
        return None
    cur = (player.row, player.col)
    if player.jump_idx >= len(jl):
        # First step back from a fresh position: stash current so Ctrl-i can return.
        if jl[-1] != cur:
            jl.append(cur)
            while len(jl) > _CAP + 1:
                jl.pop(0)
        player.jump_idx = len(jl) - 1
    if player.jump_idx <= 0:
        return None
    player.jump_idx -= 1
    return jl[player.jump_idx]


def jump_forward(player):
    """Ctrl-i: move to a newer position. Returns (row, col) or None."""
    jl = player.jump_list
    if player.jump_idx + 1 >= len(jl):
        return None
    player.jump_idx += 1
    return jl[player.jump_idx]
