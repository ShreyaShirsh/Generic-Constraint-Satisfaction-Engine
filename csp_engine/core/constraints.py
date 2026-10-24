"""The engine's constraint vocabulary.

This is the answer to "what is the one constraint your engine is built on?":
every constraint, in every problem this engine solves, is ultimately an
instance of one idea —

    a constraint is a boolean predicate over a tuple of variables.

`Constraint.is_satisfied(assignment)` is the ONLY thing the solver ever calls.
It does not know or care whether the predicate means "these two queens don't
share a diagonal", "these nine cells hold nine different digits", or "M is
not zero". Sudoku, N-Queens, map colouring, cryptarithmetic and the Zebra
puzzle are not five different solvers; they are five different sets of
predicates plugged into the same evaluator.

Two concrete shapes cover every problem in this project:

  BinaryRelation  — a predicate over exactly 2 variables. This is the shape
                     AC-3 and forward checking reason about directly (they
                     need to test individual value *pairs*), so it is the
                     workhorse for "neighbours must differ"-style constraints
                     (queens, map colouring, Sudoku peers).

  Predicate       — a predicate over ANY number of variables (arity n).
                     Binary constraints are the special case n=2. This is
                     what arithmetic (cryptarithmetic's column sum) and
                     relational (Zebra puzzle) constraints are built from.

`AllDifferent` is not a new primitive — it is sugar that expands an n-ary
"all distinct" requirement into pairwise BinaryRelation(NotEqual) objects,
because that's what reuses the fast binary-constraint machinery instead of
needing a bespoke global-constraint algorithm.
"""
from __future__ import annotations
from itertools import combinations
from typing import Callable, Iterable
from .model import Constraint, Var, Value


class BinaryRelation(Constraint):
    """A constraint over exactly two variables, defined by a predicate
    rel(a, b) -> bool that says whether x=a together with y=b is allowed.

    Being explicitly binary matters: AC-3 and forward checking are defined
    over binary constraints and need to test individual value pairs via
    `holds`.
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


class Predicate(Constraint):
    """A constraint over ANY number of variables, defined by an arbitrary
    boolean function of the full assignment restricted to its scope.

    This is the general case BinaryRelation specializes: used wherever a
    constraint genuinely isn't reducible to pairwise relations — the
    column-sum equation in cryptarithmetic, a relational clue in the Zebra
    puzzle ("the Englishman lives in the red house"), a resource-capacity
    rule in scheduling.

    `fn` receives a dict {var: value} containing only the variables in
    `variables` that are currently assigned. `check_when_partial` controls
    whether fn is asked to judge a partial scope (default: only judge once
    every variable in scope is assigned, matching the "not violated yet"
    convention used elsewhere in the engine).
    """
    def __init__(self, variables: Iterable[Var],
                 fn: Callable[[dict], bool],
                 name: str | None = None,
                 check_when_partial: bool = False):
        super().__init__(variables)
        self.fn = fn
        self.name = name or "Predicate"
        self.check_when_partial = check_when_partial

    def is_satisfied(self, assignment: dict) -> bool:
        local = {v: assignment[v] for v in self.variables if v in assignment}
        if len(local) < len(self.variables) and not self.check_when_partial:
            return True
        return self.fn(local)

    def __repr__(self):
        return f"{self.name}{self.variables}"


def NotEqual(x: Var, y: Var) -> BinaryRelation:
    """Convenience: x and y must differ. The workhorse of graph colouring,
    N-Queens, and (via AllDifferent) every row/column/box in Sudoku."""
    return BinaryRelation(x, y, lambda a, b: a != b, name="NotEqual")


def all_different(variables: Iterable[Var]) -> list[BinaryRelation]:
    """The classic 'all-different' global constraint, expressed the way this
    engine expresses everything: as pairwise NotEqual binary constraints.

    AllDifferent(x1..xk) is logically equivalent to NotEqual on every pair,
    so instead of inventing a special global-constraint propagator we reuse
    the exact same BinaryRelation + AC-3 machinery every other constraint in
    the engine uses. One idea, applied uniformly.
    """
    variables = list(variables)
    return [NotEqual(a, b) for a, b in combinations(variables, 2)]
