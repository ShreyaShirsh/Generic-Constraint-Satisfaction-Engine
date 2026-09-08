"""Search instrumentation. The spec makes this mandatory, not optional:
measuring how much each technique cuts search effort is a core deliverable,
so we thread a counter through the search from Phase 1 onward.
"""
from __future__ import annotations
from dataclasses import dataclass
import time


@dataclass
class SearchMetrics:
    nodes: int = 0          # variable assignments tried (consistent guesses)
    backtracks: int = 0     # times we undid an assignment
    pruned: int = 0         # domain values removed by inference (Phase 2+)
    elapsed: float = 0.0    # wall-clock seconds
    solved: bool = False

    def start(self) -> None:
        self._t0 = time.perf_counter()

    def stop(self) -> None:
        self.elapsed = time.perf_counter() - self._t0

    def summary(self) -> str:
        return (f"solved={self.solved}  nodes={self.nodes}  "
                f"backtracks={self.backtracks}  pruned={self.pruned}  "
                f"time={self.elapsed*1000:.2f} ms")
