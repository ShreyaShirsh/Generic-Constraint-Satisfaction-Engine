"""Core data model for the CSP engine — problem-agnostic.

A CSP is nothing more than: variables, a domain of possible values for each,
and constraints saying which value-combinations are allowed. Nothing in this
file knows about Sudoku, queens, or maps — that's the whole point.
"""
from __future__ import annotations
from itertools import permutations
from typing import Any, Hashable, Iterable

Var = Hashable          # a variable is any hashable id: a name, a (row, col), ...
Value = Any


class Domain:
    """The values a variable may currently take.

    A thin wrapper over a set, with remove/restore so inference (forward
    checking / AC-3) can prune values and put them back on backtrack.
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

    `label` is optional human-readable text ("row 3", "cage 12+") used only
    when the engine explains its reasoning; the solver never reads it.
    """
    label: str | None = None

    def __init__(self, variables: Iterable[Var]):
        self.variables: tuple[Var, ...] = tuple(variables)

    def is_satisfied(self, assignment: dict) -> bool:
        raise NotImplementedError


class CSP:
    """The container the solver actually works with.

    `groups` optionally lists all-different groups as (label, variables).
    The solver doesn't need them (all-different is already expanded into
    pairwise constraints); the explanation engine uses them to reason the
    way a person does ("7 can only go in one place in this row").
    """
    def __init__(self, variables: Iterable[Var],
                 domains: dict[Var, Iterable[Value]],
                 constraints: Iterable[Constraint],
                 groups: Iterable[tuple[str, Iterable[Var]]] | None = None):
        self.variables: list[Var] = list(variables)
        self.domains: dict[Var, Domain] = {v: Domain(domains[v]) for v in self.variables}
        self.constraints: list[Constraint] = list(constraints)
        self.groups: list[tuple[str, tuple[Var, ...]]] = [
            (label, tuple(vs)) for label, vs in (groups or [])
        ]
        self.groups_of: dict[Var, list[tuple[str, tuple[Var, ...]]]] = {}
        for g in self.groups:
            for v in g[1]:
                self.groups_of.setdefault(v, []).append(g)

        # The constraint graph never changes after construction, so every
        # lookup the search makes thousands of times is precomputed once.
        self._by_var: dict[Var, list[Constraint]] = {v: [] for v in self.variables}
        self._between: dict[tuple[Var, Var], list[Constraint]] = {}
        self._binary_between: dict[tuple[Var, Var], list[Constraint]] = {}
        for c in self.constraints:
            for v in c.variables:
                self._by_var[v].append(c)
            is_binary = hasattr(c, "holds")
            for x, y in permutations(set(c.variables), 2):
                self._between.setdefault((x, y), []).append(c)
                if is_binary:
                    self._binary_between.setdefault((x, y), []).append(c)

        self._neighbors: dict[Var, frozenset] = {
            v: frozenset(u for c in self._by_var[v] for u in c.variables if u != v)
            for v in self.variables
        }

    def neighbors(self, var: Var) -> frozenset:
        """Variables that share a constraint with `var`."""
        return self._neighbors[var]

    def constraints_on(self, var: Var) -> list[Constraint]:
        """Every constraint touching `var`."""
        return self._by_var[var]

    def constraints_between(self, x: Var, y: Var) -> list[Constraint]:
        """Constraints touching both x and y."""
        return self._between.get((x, y), [])

    def binary_constraints_between(self, x: Var, y: Var) -> list[Constraint]:
        """Only the pairwise (BinaryRelation) constraints between x and y —
        the ones forward checking / AC-3 can test value-pair by value-pair."""
        return self._binary_between.get((x, y), [])

    def is_consistent(self, var: Var, value: Value, assignment: dict) -> bool:
        """Would setting var=value break any constraint touching var, given
        what's already assigned? Temporarily writes into `assignment` instead
        of copying it — this check runs on every node of the search."""
        present = var in assignment
        old = assignment.get(var)
        assignment[var] = value
        try:
            for c in self._by_var[var]:
                if not c.is_satisfied(assignment):
                    return False
            return True
        finally:
            if present:
                assignment[var] = old
            else:
                del assignment[var]

    def is_complete(self, assignment: dict) -> bool:
        return len(assignment) == len(self.variables)

    def is_solution(self, assignment: dict) -> bool:
        return self.is_complete(assignment) and \
            all(c.is_satisfied(assignment) for c in self.constraints)

    def reset_domains(self, domains: dict[Var, Iterable[Value]]) -> None:
        """Replace every domain without rebuilding the constraint graph —
        lets the puzzle generator re-check the same rules with different
        givens thousands of times cheaply."""
        self.domains = {v: Domain(domains[v]) for v in self.variables}
