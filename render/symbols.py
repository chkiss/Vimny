WOOD_WALL_DAMAGED = '░'

FLOOR        = ' '
CORRIDOR     = ' '

PLAYER       = '@'
ENEMY_WANDERER = '♟'

HEART_FULL   = '♥'
HEART_HALF   = '♡'
HEART_EMPTY  = '░'
KEY          = '🗝'
DYNAMITE     = '!'
CHEST        = '🞔'
DOOR_H       = '▬'
DOOR_V       = '▮'
DOOR_LOCKED  = '🔒'   # may be replaced by init() if terminal renders it as 2-wide
EXIT         = '◉'
SHIELD       = '⛨'   # may be replaced by init() if terminal renders it as 2-wide


def init(term) -> None:
    """Replace wide glyphs with single-width fallbacks when the terminal renders them as 2 columns."""
    global DOOR_LOCKED, SHIELD
    if term.length(DOOR_LOCKED) != 1:
        DOOR_LOCKED = '⊡'
    if term.length(SHIELD) != 1:
        SHIELD = '◆'

BOX_TL = '┌'; BOX_TR = '┐'; BOX_BL = '└'; BOX_BR = '┘'
BOX_H  = '─'; BOX_V  = '│'
BOX_LT = '├'; BOX_RT = '┤'
