class Budget:
    """Keystroke budget. Undo/redo of `spent` is handled by the game loop's snapshot
    history (main._pop_history_step restores `spent` directly), so Budget itself only
    needs to spend; it carries no per-action history."""

    def __init__(self, total: int):
        self.total  = total
        self.spent  = 0
        self.frozen = False             # when True, spend() is a no-op (macro replay)

    @property
    def remaining(self) -> int:
        return self.total - self.spent

    def spend(self, cost: int = 1):
        if self.frozen:                 # replayed macro keys don't re-charge budget
            return
        self.spent += cost

    @property
    def is_over(self) -> bool:
        return self.spent > self.total
