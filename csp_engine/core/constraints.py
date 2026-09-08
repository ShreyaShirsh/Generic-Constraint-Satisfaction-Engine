"""Reusable constraint types. Problem adapters build constraints from these
instead of inventing their own, so the same shapes are reused everywhere.
"""
from __future__ import annotations
from typing import Callable
from .model import Constraint, Var, Value


class BinaryRelation(Constraint):
    """A constraint over exactly two variables, defined by a predicate
    rel(a, b) -> bool that says whether x=a together with y=b is allowed.

    Being explicitly binary matters: AC-3 (Phase 2) is defined over binary
    constraints and needs to test individual value pairs via `holds`.
    """
    def __init__(self, x: Var, y: Var, rel: Callable[[Value, Value], bool],
                 name: str | None = None):
        super().__init__((x, y))
        self.x, self.y, self.rel = x, y, rel
        self.name = name or "BinaryRelation"

    def is_satisfied(self, assignment: dict) -> bool:
        if self.x in assignment and self.y in assignment:
            return self.rel(assignment[self.x], assignment[self.y])
        return True                      # not both assigned yet -> not violated

    def holds(self, a: Value, b: Value) -> bool:
        """Direct predicate test for a value pair — used by AC-3 revise."""
        return self.rel(a, b)

    def __repr__(self):
        return f"{self.name}({self.x}, {self.y})"


def NotEqual(x: Var, y: Var) -> BinaryRelation:
    """Convenience: x and y must differ. The workhorse of graph colouring."""
    return BinaryRelation(x, y, lambda a, b: a != b, name="NotEqual")
