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
    keys: int = 0
    register: list = field(default_factory=list)   # unnamed " register
    inventory: list = field(default_factory=list)
    marks: dict = field(default_factory=dict)   # 'a'-'z' -> (row, col)

    # command input buffer for gg, f{c}, m{c}, `{c}, '{c}
    input_buf: str = ''
    # command-mode line
    cmd_line: str = ''
    # statusline error (e.g. E37); cleared on next keypress
    error: str = ''

    def move(self, dr: int, dc: int, room_rows: int, room_cols: int) -> bool:
        nr, nc = self.row + dr, self.col + dc
        if 0 <= nr < room_rows and 0 <= nc < room_cols:
            self.row, self.col = nr, nc
            return True
        return False

    def take_damage(self, half_hearts: int = 2):
        """Reduce HP. amount is in half-hearts (2 = 1 full heart)."""
        self.hp = max(0, self.hp - half_hearts)

    @property
    def is_dead(self) -> bool:
        return self.hp <= 0
