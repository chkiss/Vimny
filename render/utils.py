from blessed import Terminal

def inner_w(term: Terminal) -> int:
    """Inner playfield width: terminal width clamped to [80, 120], minus 2 borders."""
    return min(max(term.width, 80), 120) - 2
