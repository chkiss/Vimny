from enum import Enum, auto

class Mode(Enum):
    NORMAL  = auto()
    INSERT  = auto()
    REPLACE = auto()
    VISUAL  = auto()
    VISUAL_LINE  = auto()
    VISUAL_BLOCK = auto()
    COMMAND = auto()
    SEARCH       = auto()   # / and ? entry
    MACRO_RECORD = auto()   # q{char} recording

MODE_LABELS = {
    Mode.NORMAL:       '-- NORMAL --',
    Mode.INSERT:       '-- INSERT --',
    Mode.REPLACE:      '-- REPLACE --',
    Mode.VISUAL:       '-- VISUAL --',
    Mode.VISUAL_LINE:  '-- VISUAL LINE --',
    Mode.VISUAL_BLOCK: '-- VISUAL BLOCK --',
    Mode.COMMAND:      ':',
    Mode.SEARCH:       '/',
    Mode.MACRO_RECORD: '-- RECORDING --',
}
