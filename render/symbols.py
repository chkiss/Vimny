WALL_SOLID        = '█'
WALL_SHADE1       = '▓'
WALL_SHADE2       = '▒'
WALL_SHADE3       = '░'
WOOD_WALL_DAMAGED = '░'

FLOOR        = ' '
CORRIDOR     = ' '

PLAYER       = '@'
ENEMY_WANDERER = '♟'
ENEMY_GUARD  = '♜'
BOSS         = '☠'

HEART_FULL   = '♥'
HEART_HALF   = '♡'
HEART_EMPTY  = '░'
KEY          = '🗝'
DYNAMITE     = '!'
EXPLOSION    = '*'
CHEST        = '🞔'
DOOR_LOCKED  = '▬'
DOOR_LOCKED_KEY = '🔒'   # may be replaced by init() if terminal renders it as 2-wide
DOOR_OPEN    = '░'
EXIT         = '◉'


def init(term) -> None:
    """Replace wide glyphs with single-width fallbacks when the terminal renders them as 2 columns."""
    global DOOR_LOCKED_KEY
    if term.length(DOOR_LOCKED_KEY) != 1:
        DOOR_LOCKED_KEY = '⊠'

RUNE_ANCIENT = ('∘', '∘', '∘')
RUNE_VERDANT = ('·', '·', '·')
RUNE_VOID    = ('○', '○')
RUNE_EMBER   = ('◦', '◦', '◦', '◦')

BOX_TL = '┌'; BOX_TR = '┐'; BOX_BL = '└'; BOX_BR = '┘'
BOX_H  = '─'; BOX_V  = '│'
BOX_LT = '├'; BOX_RT = '┤'; BOX_TT = '┬'; BOX_BT = '┴'; BOX_X = '┼'
