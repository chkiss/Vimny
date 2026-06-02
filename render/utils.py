from blessed import Terminal

def inner_w(term: Terminal) -> int:
    """Inner playfield width: terminal width clamped to [80, 120], minus 2 borders."""
    return min(max(term.width, 80), 120) - 2


def subtree_lines(label: str, items: list, entry_type: str, key: str = 'item') -> list[dict]:
    """Build a netrw-style subtree as flat row dicts: a 'subhdr' row carrying
    `label`, then one `entry_type` row per item (stored under `key`), each with
    a 'last' flag for the └/├ tree glyph. Empty `items` yields no rows.

    Shared by the overworld's custom/ section and the scroll library's
    codex//relics/ sections so the subtree shape lives in one place."""
    if not items:
        return []
    rows = [{'type': 'subhdr', 'label': label}]
    last = len(items) - 1
    for i, it in enumerate(items):
        rows.append({'type': entry_type, key: it, 'last': i == last})
    return rows


def tree_glyph(last: bool) -> str:
    """Branch character for a subtree entry: └ for the last item, ├ otherwise."""
    return '└' if last else '├'
