from __future__ import annotations
from dataclasses import dataclass, field
from engine.modes import Mode

@dataclass
class Player:
    row: int = 0
    col: int = 0
    hp: int = 6       # stored in half-hearts (6 = 3 full hearts)
    max_hp: int = 6
    name: str = 'Normand'
    mode: Mode = Mode.NORMAL
    known_commands: list = field(default_factory=lambda: ['h','j','k','l'])
    registers: dict = field(default_factory=dict)  # vim registers: '"' unnamed, 'a'-'z', '0', etc.
    edit_clip: list = field(default_factory=list)  # admin map-editor clipboard (characters/entities/cells)
    marks: dict = field(default_factory=dict)   # 'a'-'z' -> (row, col)
    macros: dict = field(default_factory=dict)  # 'a'-'z' -> recorded keystroke string
    jump_list: list = field(default_factory=list)  # (row, col) positions for Ctrl-o/Ctrl-i
    jump_idx: int = 0                              # cursor index into jump_list

    last_f: tuple | None = None   # (motion, target) of most recent f/F/t/T; set by apply_motion
    last_change: dict | None = None  # last action that mutated the room; re-played by .
    insert_extend: bool = False   # True during an A-initiated INSERT: typing builds new floor (ledge) into the void
    visual_anchor: tuple | None = None       # (row, col) where v/V/Ctrl-v was pressed
    visual_start_spent: int = 0              # budget.spent before v/V/Ctrl-v was pressed
    last_visual_anchor: tuple | None = None   # saved on operator-apply, for gv
    last_visual_cursor: tuple | None = None
    last_visual_mode: object = None           # Mode of the last visual selection, for gv
    last_parry: bool = False                  # last visual-delete span covered an edit_immune boss (→ "shield defended" message)
    last_search: tuple | None = None  # (pattern, forward) of the most recent search; used by n/N
    last_sub: tuple | None = None     # (pattern, replacement, flags_str) of the last :s; for & / :s / g&
    pending_recost_f: int = 0  # >0: next ;/, re-pays this (its f/F/t/T was undone — anti-exploit)
    pending_recost_s: int = 0  # >0: next n/N re-pays this (its search was undone — anti-exploit)
    pending_recost_c: int = 0  # >0: next . re-pays this (its change was undone — anti-exploit)
    search_forward: bool = True   # direction of the in-progress / or ? entry (for rendering)
    number_mode: str = 'none'     # ':set number' gutter in dungeons: 'none'|'number'|'relativenumber'
    hlsearch: bool = True         # ':set hlsearch' — paint all matches of the last search
    incsearch: bool = True        # ':set incsearch' — preview matches while typing / or ?
    wrap: bool = False            # ':set wrap' — soft-wrap a single-line buffer across screen rows (The Archivist's Library). Off by default: only renders on Room.wrap_buffer rooms, which open nowrap.
    hl_suppressed: bool = False   # ':noh' cleared the current highlight (until the next search)

    # command-mode line
    cmd_line: str = ''
    # statusline error (e.g. E37); cleared on next keypress
    error: str = ''

    def take_damage(self, half_hearts: int = 2):
        """Reduce HP. amount is in half-hearts (2 = 1 full heart)."""
        self.hp = max(0, self.hp - half_hearts)

    def heal(self, half_hearts: int = 2):
        """Restore HP, capped at max_hp."""
        self.hp = min(self.max_hp, self.hp + half_hearts)

    @property
    def is_dead(self) -> bool:
        return self.hp <= 0
