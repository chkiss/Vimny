"""Hint bar text, driven by vim_commands.md.

CMD is parsed once at import from the markdown table.
HINT_TIERS is built by diffing known_commands() between consecutive curriculum
levels — no token lists are hardcoded.  hint_text() walks the list newest-first
and returns the first tier whose sentinel is in the player's known_commands.
"""
from __future__ import annotations
import pathlib
import re

_MD = pathlib.Path(__file__).parent / 'vim_commands.md'

# ── Parse vim_commands.md ─────────────────────────────────────────────────────

def _parse(path: pathlib.Path) -> dict[str, tuple[str, str]]:
    cmd: dict[str, tuple[str, str]] = {}
    sep = re.compile(r'^\|[-| ]+\|')
    row = re.compile(r'^\|([^|]+)\|([^|]*)\|([^|]+)\|')
    with open(path) as f:
        for line in f:
            line = line.rstrip()
            if not line.startswith('|') or sep.match(line):
                continue
            m = row.match(line)
            if not m:
                continue
            keys  = m.group(1).strip()
            token = m.group(2).strip()
            desc  = m.group(3).strip()
            if not keys or keys == 'keys':
                continue
            tok = token or keys
            cmd[tok] = (keys, desc)
    return cmd

CMD: dict[str, tuple[str, str]] = _parse(_MD)

# ── Build hint tiers from curriculum diffs ────────────────────────────────────

def _build_tiers() -> list[tuple[str, list[str]]]:
    """Derive tiers by diffing known_commands() across curriculum levels.

    Each tier = (sentinel, new_tokens) where sentinel is the first new token
    and new_tokens is the ordered list of commands introduced at that level.
    Levels that add no new commands (bosses, the reliquary) are skipped
    automatically. Walks LEVELS in curriculum order.
    """
    from content.levels import known_commands, LEVELS
    tiers: list[tuple[str, list[str]]] = []
    prev_known: set[str] = set(known_commands('first_cave'))   # seed with the First Cave base
    for lv in LEVELS:
        if lv['slug'] == 'first_cave' or lv.get('admin_only'):
            continue
        curr = known_commands(lv['slug'])
        new = [t for t in curr if t not in prev_known]
        if new:
            tiers.append((new[0], new))
            prev_known = set(curr)
    tiers.reverse()   # newest tier first
    return tiers

_HINT_TIERS: list[tuple[str, list[str]]] = _build_tiers()

# ── Constants ─────────────────────────────────────────────────────────────────

_SUFFIX  = '  :w write  :q quit'
_DEFAULT = 'h/j/k/l:move cursor  :w write (save)  :q quit  :q! quit without saving'

# ── Public API ────────────────────────────────────────────────────────────────

# Some single curriculum tokens unlock a whole keystroke family that shares one
# gate.  '/' (search) gates ? n N too — show them all on the hint bar.
_FAMILY = {'/': ['/', '?{pat}', 'n', 'N']}


def _format(tokens) -> str:
    expanded: list = []
    for tok in tokens:
        for t in _FAMILY.get(tok, [tok]):
            if t not in expanded:
                expanded.append(t)
    parts = [f'{CMD[t][0]}:{CMD[t][1]}' for t in expanded if t in CMD]
    return ('  '.join(parts) + _SUFFIX) if parts else _DEFAULT


def hint_text(known: list, slug: str | None = None) -> str:
    """Return hint bar text for the given known_commands list.

    On a boss level the bar lists the WHOLE act the boss caps (so the player is
    nudged to wield every command they've learned), never the next-act command
    the boss merely previews. Elsewhere it shows the newest tier the player owns.
    """
    if slug is not None:
        from content.levels import level_type, act_commands  # noqa: PLC0415
        if level_type(slug) == 'boss':
            return _format(act_commands(slug))
    for sentinel, tokens in _HINT_TIERS:
        if sentinel in known:
            return _format(tokens)
    return _DEFAULT
