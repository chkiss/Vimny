class Budget:
    def __init__(self, total: int):
        self.total   = total
        self.spent   = 0
        self._history: list[int] = []   # cost of each action, for undo

    @property
    def remaining(self) -> int:
        return self.total - self.spent

    def spend(self, cost: int = 1):
        self.spent += cost
        self._history.append(cost)

    def undo(self) -> bool:
        if not self._history:
            return False
        cost = self._history.pop()
        self.spent -= cost
        return True

    def redo(self, cost: int = 1):
        self.spend(cost)

    @property
    def is_over(self) -> bool:
        return self.spent > self.total

    def status_color(self) -> str:
        r = self.remaining
        if r <= 1:   return 'crit'
        if r <= 3:   return 'low'
        return 'ok'
