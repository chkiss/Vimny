"""Blocks B–F — translate a Vim 'magic' search pattern into a Python regex.

Vim search (``/pat``) is a regular-expression engine, not a literal substring.
This module turns the subset of Vim regex the scrolls teach into a compiled
``re`` pattern, wrapped in :class:`VimPattern` so callers can iterate matches
without caring about Python's API.

Supported atoms (default 'magic' level):
  .  any char            ^ $  line ends         [..] [^..] collections
  *  0+   \\+ 1+   \\? \\= 0/1   \\{n,m} counts
  \\( \\) groups   \\| alternation   \\< \\> word boundaries
  \\w \\W \\d \\D \\s \\S   \\a \\l \\u \\h  character classes
  \\zs \\ze  set the real start / end of the match
  \\c \\C    force case-insensitive / case-sensitive
  \\v \\V \\m \\M  magic levels (very magic … very nomagic)

A leading or mid-pattern ``\\v`` flips which of ``+ ? = ( ) { } | < >`` need a
backslash. Anything that fails to translate yields ``None`` so the caller can
fall back to a literal substring search (Vim-faithful for plain words and the
behaviour Vimny shipped before regex landed)."""
from __future__ import annotations
import re
from functools import lru_cache

# backslash-letter → Python class (magic-independent)
_CLASS = {
    'w': r'\w', 'W': r'\W', 'd': r'\d', 'D': r'\D', 's': r'\s', 'S': r'\S',
    'a': '[A-Za-z]', 'A': '[^A-Za-z]', 'l': '[a-z]', 'L': '[^a-z]',
    'u': '[A-Z]', 'U': '[^A-Z]', 'h': '[A-Za-z_]',
    'n': r'\n', 't': r'\t', '<': r'\b', '>': r'\b',
}

# bare chars that are "special" at each magic level (anchors handled separately)
_BARE_SPECIAL = {
    'v': set('.*[+?=(){}|<>~'),   # very magic
    'm': set('.*[~'),             # magic (default)
    'M': set(),                   # nomagic
    'V': set(),                   # very nomagic
}


class VimPattern:
    """A compiled Vim search pattern. ``\\zs`` / ``\\ze`` shift the *effective*
    match span (where the cursor lands and what hlsearch paints) away from the
    full regex match."""

    def __init__(self, regex, has_zs: bool, has_ze: bool):
        self._re = regex
        self.has_zs = has_zs
        self.has_ze = has_ze

    def finditer(self, s: str):
        """Yield (start, end) effective spans of non-overlapping matches."""
        for m in self.match_iter(s):
            yield self.eff_span(m)

    def first_in(self, s: str):
        for span in self.finditer(s):
            return span
        return None

    def match_iter(self, s: str):
        """Yield re.Match objects for non-overlapping matches (zero-width safe),
        so substitution can read capture groups. Same advance rule as finditer."""
        pos = 0
        while pos <= len(s):
            m = self._re.search(s, pos)
            if not m:
                return
            yield m
            pos = m.end() + 1 if m.end() == m.start() else m.end()

    def eff_span(self, m) -> tuple:
        """The effective (start, end) of a match, honouring \\zs / \\ze."""
        start = m.start('_zs') if self.has_zs else m.start()
        end   = m.start('_ze') if self.has_ze else m.end()
        return start, end


def _read_class(s: str, i: int):
    """Parse a ``[...]`` collection starting just after '['. Returns (py, idx)."""
    out = ['[']
    if i < len(s) and s[i] == '^':
        out.append('^'); i += 1
    if i < len(s) and s[i] == ']':                 # leading ] is literal in a class
        out.append(r'\]'); i += 1
    while i < len(s) and s[i] != ']':
        if s[i] == '\\' and i + 1 < len(s):
            out.append(s[i:i+2]); i += 2; continue
        out.append(s[i]); i += 1
    if i < len(s) and s[i] == ']':
        i += 1
    out.append(']')
    return ''.join(out), i


def _read_brace(s: str, i: int):
    """Parse a count ``{...}`` body starting just after the '{'. The body may be
    closed by '}' or '\\}'. Returns (py_quantifier, idx)."""
    body = ''
    while i < len(s) and s[i] != '}':
        if s[i] == '\\' and i + 1 < len(s) and s[i+1] == '}':
            break
        body += s[i]; i += 1
    if i < len(s) and s[i] == '\\':
        i += 1
    if i < len(s) and s[i] == '}':
        i += 1
    lazy = body.startswith('-')
    if lazy:
        body = body[1:]
    quant = '*' if body == '' else '{' + body + '}'
    return (quant + '?') if lazy else quant, i


def _translate(pattern: str):
    """Vim magic regex → (python_regex, flags, has_zs, has_ze). Raises ValueError
    / re.error on anything unsupported."""
    out: list = []
    flags = 0
    magic = 'm'
    has_zs = has_ze = False
    i, n = 0, len(pattern)

    while i < n:
        c = pattern[i]

        if c == '\\' and i + 1 < n:
            nx = pattern[i+1]
            i += 2
            if nx == 'c':
                flags |= re.IGNORECASE; continue
            if nx == 'C':
                flags &= ~re.IGNORECASE; continue
            if nx in 'vVmM':
                magic = nx; continue
            if nx == 'z' and i < n and pattern[i] in 'se':
                marker = pattern[i]; i += 1
                if marker == 's':
                    out.append('(?P<_zs>)'); has_zs = True
                else:
                    out.append('(?P<_ze>)'); has_ze = True
                continue
            if nx in _CLASS:
                out.append(_CLASS[nx]); continue
            # quantifiers / groups: special when escaped in magic levels, literal in very-magic
            if magic != 'v':
                if nx in '+':
                    out.append('+'); continue
                if nx in '?=':
                    out.append('?'); continue
                if nx == '{':
                    q, i = _read_brace(pattern, i); out.append(q); continue
                if nx == '(':
                    out.append('('); continue
                if nx == ')':
                    out.append(')'); continue
                if nx == '|':
                    out.append('|'); continue
            out.append(re.escape(nx)); continue       # escaped → literal

        i += 1
        special = _BARE_SPECIAL[magic]

        if c == '^' and len(out) == 0 and magic in ('v', 'm', 'M'):
            out.append('^'); continue
        if c == '$' and i == n and magic in ('v', 'm', 'M'):
            out.append('$'); continue
        if c not in special:
            out.append(re.escape(c)); continue

        # bare special (magic-level dependent)
        if c == '.':
            out.append('.')
        elif c == '*':
            out.append('*')
        elif c == '~':
            out.append(re.escape('~'))               # last-sub-string: treat literal
        elif c == '[':
            cls, i = _read_class(pattern, i); out.append(cls)
        elif c == '+':
            out.append('+')
        elif c in '?=':
            out.append('?')
        elif c == '{':
            q, i = _read_brace(pattern, i); out.append(q)
        elif c == '(':
            out.append('(')
        elif c == ')':
            out.append(')')
        elif c == '|':
            out.append('|')
        elif c in '<>':
            out.append(r'\b')
        else:
            out.append(re.escape(c))

    return ''.join(out), flags, has_zs, has_ze


@lru_cache(maxsize=256)
def compile_vim(pattern: str):
    """Compile a Vim search pattern → VimPattern, or None if it can't be
    translated (caller should fall back to literal substring search).

    Memoized: the matcher calls this once per character-run, and the renderer
    re-highlights every frame while a search is active, so the same short
    pattern is compiled many times. A VimPattern is immutable (finditer holds
    no state), so sharing one across all callers is safe."""
    if not pattern:
        return None
    try:
        py, flags, has_zs, has_ze = _translate(pattern)
        return VimPattern(re.compile(py, flags), has_zs, has_ze)
    except (re.error, ValueError):
        return None


@lru_cache(maxsize=256)
def compile_sub(pattern: str, ignorecase=None):
    """Compile a pattern for :s / :g — like :func:`compile_vim` but ALWAYS returns a
    VimPattern (an untranslatable pattern falls back to a literal match) so the caller
    has capture groups via ``match_iter``. ``ignorecase`` forces the case of the match:
    True (the ``i`` flag), False (``I``), or None (honour the pattern's own \\c/\\C)."""
    if not pattern:
        return None
    vp = compile_vim(pattern)
    if vp is None:
        try:
            vp = VimPattern(re.compile(re.escape(pattern)), False, False)
        except re.error:
            return None
    if ignorecase is not None:
        flags = (vp._re.flags | re.IGNORECASE) if ignorecase else (vp._re.flags & ~re.IGNORECASE)
        vp = VimPattern(re.compile(vp._re.pattern, flags), vp.has_zs, vp.has_ze)
    return vp
