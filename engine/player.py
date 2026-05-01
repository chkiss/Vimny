from dataclasses import dataclass, field
from engine.modes import Mode

@dataclass
class Player:
    row: int = 0
    col: int = 0
    hp: int = 3
    max_hp: int = 3
    name: str = 'Normand'
    mode: Mode = Mode.NORMAL
    known_commands: list = field(default_factory=lambda: ['h','j','k','l'])
    inventory: list = field(default_factory=list)
    marks: dict = field(default_factory=dict)   # 'a'-'z' -> (row, col)

    # command input buffer for gg, f{c}, m{c}, `{c}, '{c}
    input_buf: str = ''
    # command-mode line
    cmd_line: str = ''

    def move(self, dr: int, dc: int, room_rows: int, room_cols: int) -> bool:
        nr, nc = self.row + dr, self.col + dc
        if 0 <= nr < room_rows and 0 <= nc < room_cols:
            self.row, self.col = nr, nc
            return True
        return False

    def take_damage(self, amount: int = 1):
        self.hp = max(0, self.hp - amount)

    @property
    def is_dead(self) -> bool:
        return self.hp <= 0
