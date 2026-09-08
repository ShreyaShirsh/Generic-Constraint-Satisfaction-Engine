"""Core data model for the CSP engine — problem-agnostic.

A CSP is nothing more than: variables, a domain of possible values for each,
and constraints saying which value-combinations are allowed. Nothing in this
file knows about Sudoku, queens, or maps — that's the whole point.
"""
from __future__ import annotations
from typing import Any, Callable, Hashable, Iterable

Var = Hashable          # a variable is any hashable id: a name, a (row, col), ...
Value = Any


class Domain:
    """The values a variable may currently take.

    It's a thin wrapper over a set, but giving it a class buys us two things
    we'll rely on in Phase 2: cheap copying, and remove/restore so inference
    (forward checking / AC-3) can prune values and put them back on backtrack.
    """
    def __init__(self, values: Iterable[Value]):
        self.values: set[Value] = set(values)

    def __iter__(self):          return iter(self.values)
    def __len__(self):           return len(self.values)
    def __contains__(self, v):   return v in self.values
    def remove(self, v):         self.values.discard(v)
    def add(self, v):            self.values.add(v)
    def copy(self) -> "Domain":  return Domain(self.values)
    def __repr__(self):          return f"Domain({sorted(self.values, key=str)})"


class Constraint:
    """Base class. A constraint knows which variables it touches and can say
    whether a (possibly partial) assignment violates it.

    Convention: is_satisfied returns False ONLY when the constraint is actually
    violated by the variables assigned so far. If some of its variables are
    still unassigned, it isn't violated yet, so we return True.
    """
    def __init__(self, variables: Iterable[Var]):
        self.variables: tuple[Var, ...] = tuple(variables)

    def is_satisfied(self, assignment: dict) -> bool:
        raise NotImplementedError


class CSP:
    """The container the solver actually works with."""
    def __init__(self, variables: Iterable[Var],
                 domains: dict[Var, Iterable[Value]],
                 constraints: Iterable[Constraint]):
        self.variables: list[Var] = list(variables)
        self.domains: dict[Var, Domain] = {v: Domain(domains[v]) for v in self.variables}
        self.constraints: list[Constraint] = list(constraints)

        # Index constraints by the variables they touch — used everywhere.
        self._by_var: dict[Var, list[Constraint]] = {v: [] for v in self.variables}
        for c in self.constraints:
            for v in c.variables:
                self._by_var[v].append(c)

    def neighbors(self, var: Var) -> set[Var]:
        """Variables that share a constraint with `var`."""
        out: set[Var] = set()
        for c in self._by_var[var]:
            out.update(v for v in c.variables if v != var)
        return out

    def constraints_between(self, x: Var, y: Var) -> list[Constraint]:
        """Constraints touching both x and y — used by AC-3's revise (Phase 2)."""
        return [c for c in self._by_var[x] if y in c.variables]

    def is_consistent(self, var: Var, value: Value, assignment: dict) -> bool:
        """Would setting var=value break any constraint touching var,
        given what's already assigned? We only check constraints on `var`."""
        trial = dict(assignment)
        trial[var] = value
        return all(c.is_satisfied(trial) for c in self._by_var[var])

    def is_complete(self, assignment: dict) -> bool:
        return len(assignment) == len(self.variables)

    def is_solution(self, assignment: dict) -> bool:
        return self.is_complete(assignment) and \
            all(c.is_satisfied(assignment) for c in self.constraints)
