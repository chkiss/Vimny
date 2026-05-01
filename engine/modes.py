from enum import Enum, auto

class Mode(Enum):
    NORMAL  = auto()
    INSERT  = auto()
    VISUAL  = auto()
    VISUAL_LINE  = auto()
    VISUAL_BLOCK = auto()
    COMMAND = auto()

MODE_LABELS = {
    Mode.NORMAL:       '-- NORMAL --',
    Mode.INSERT:       '-- INSERT --',
    Mode.VISUAL:       '-- VISUAL --',
    Mode.VISUAL_LINE:  '-- VISUAL LINE --',
    Mode.VISUAL_BLOCK: '-- VISUAL BLOCK --',
    Mode.COMMAND:      ':',
}
