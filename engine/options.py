"""Block A — the :set option grammar (toggle, invert, reset, query).

The dungeon exposes two boolean display options — 'number' and
'relativenumber' — collapsed into a single tri-state `Player.number_mode`
('none' | 'number' | 'relativenumber'). Real Vim keeps them independent, but
the gutter can only render one style at a time, so turning one on turns the
other off, and turning 'relativenumber' off falls back to absolute 'number'
(Vim's own behaviour with both set).

`apply_set` parses ONE :set argument (the text after the leading ``set ``) and
returns ``(new_mode, message)``:
  * a plain/`inv`/`no`/`!`/`&` form changes the mode and echoes the new state;
  * a `?` query leaves the mode unchanged and echoes the current state;
  * an unrecognised option leaves the mode unchanged and returns an error
    message beginning with ``Unknown option:``.

This is the one place that knows the option grammar, so it is unit-testable
without the game loop.
"""
from __future__ import annotations

# abbreviation → canonical option name
_ALIASES = {
    'number': 'number', 'nu': 'number',
    'relativenumber': 'relativenumber', 'rnu': 'relativenumber',
}

# the default value of each option (both off by default, as in a bare Vim)
_DEFAULT_ON = {'number': False, 'relativenumber': False}


def parse_modifier(arg: str) -> tuple[str, str]:
    """Split a :set argument into (option_core, action), stripping the
    no/inv/!/&/? affixes. action ∈ {'on','off','toggle','reset','query'}.
    Used for plain boolean options (e.g. hlsearch) that live outside the
    number tri-state."""
    arg = arg.strip()
    if arg.endswith('?'):
        return arg[:-1], 'query'
    if arg.endswith('!'):
        return arg[:-1], 'toggle'
    if arg.endswith('&'):
        return arg[:-1], 'reset'
    if arg.startswith('inv'):
        return arg[3:], 'toggle'
    if arg.startswith('no'):
        return arg[2:], 'off'
    return arg, 'on'


def _is_on(mode: str, opt: str) -> bool:
    return mode == opt


def _set_on(mode: str, opt: str, on: bool) -> str:
    """Return the new tri-state mode after setting `opt` on/off.

    Turning an option ON switches the gutter to it (the two are mutually
    exclusive in this collapsed model). Turning the *currently shown* option
    off blanks the gutter ('none'); turning off an option that isn't shown is
    a no-op."""
    if on:
        return opt
    return 'none' if mode == opt else mode


def _echo(mode: str, opt: str) -> str:
    """Vim-style statusline echo of one option's state, e.g. 'number' / 'nonumber'."""
    return opt if _is_on(mode, opt) else 'no' + opt


def apply_set(number_mode: str, arg: str) -> tuple[str, str]:
    """Parse one :set argument. Returns (new_number_mode, message)."""
    arg = arg.strip()

    # :set all& — reset every option to its default
    if arg in ('all&', 'all&vi', 'all&vim'):
        return 'none', ':set all&'

    # Reuse the shared affix grammar (no/inv/!/&/? → core + action).
    core, action = parse_modifier(arg)
    opt = _ALIASES.get(core)
    if opt is None:
        return number_mode, f'Unknown option: :set {arg}'

    if action == 'query':
        return number_mode, _echo(number_mode, opt)
    if action == 'reset':
        new = _set_on(number_mode, opt, _DEFAULT_ON[opt])
        return new, f':set {opt}&'
    if action == 'toggle':
        new = _set_on(number_mode, opt, not _is_on(number_mode, opt))
        return new, _echo(new, opt)
    if action == 'off':
        new = _set_on(number_mode, opt, False)
        return new, f':set no{opt}'
    # action == 'on' — plain :set {opt}
    new = _set_on(number_mode, opt, True)
    return new, f':set {opt}'
