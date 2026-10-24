"""Constraint propagation — reasoning about which values CAN'T be part of any
solution and removing them before the search ever has to guess.

Both techniques here are completely generic: neither knows what a variable
represents. They only use two things every CSP already provides —
`csp.neighbors(var)` and `csp.constraints_between(x, y)` — which is exactly
why the same two functions power Sudoku, N-Queens, map colouring and
cryptarithmetic without modification.

  forward_checking — cheap, local: after assigning var=value, prune values
                      from the domains of var's UNASSIGNED neighbours that
                      are now impossible. O(degree) work per assignment.

  ac3              — thorough, global: repeatedly enforces arc consistency
                      on every binary arc until no more pruning is possible
                      (or a domain empties). Strictly stronger than forward
                      checking; costs more per call.

Both return (ok, pruned) where pruned is a list of (variable, value) pairs
removed from domains — the search undoes exactly this list on backtrack.
"""
from __future__ import annotations
from collections import deque
from typing import Optional
from .model import CSP, Var, Value


def _binary_constraints(csp: CSP, x: Var, y: Var):
    """Constraints between x and y that support pairwise `.holds` testing
    (i.e. BinaryRelation instances — AllDifferent expands to these)."""
    return [c for c in csp.constraints_between(x, y) if hasattr(c, "holds")]


# ---- forward checking --------------------------------------------------

def forward_checking(csp: CSP, var: Var, value: Value, assignment: dict):
    pruned: list[tuple[Var, Value]] = []
    for nbr in csp.neighbors(var):
        if nbr in assignment:
            continue
        for c in _binary_constraints(csp, var, nbr):
            for val in list(csp.domains[nbr]):
                a, b = (value, val) if c.x == var else (val, value)
                if not c.holds(a, b):
                    csp.domains[nbr].remove(val)
                    pruned.append((nbr, val))
        if len(csp.domains[nbr]) == 0:
            return False, pruned
    return True, pruned


# ---- AC-3 (generic arc consistency) ------------------------------------

def _revise(csp: CSP, xi: Var, xj: Var) -> list[Value]:
    """Remove values from domain(xi) that have no supporting value in
    domain(xj) under every binary constraint between them. Returns the
    removed values."""
    removed = []
    for c in _binary_constraints(csp, xi, xj):
        for a in list(csp.domains[xi]):
            supported = False
            for b in csp.domains[xj]:
                x_val, y_val = (a, b) if c.x == xi else (b, a)
                if c.holds(x_val, y_val):
                    supported = True
                    break
            if not supported:
                csp.domains[xi].remove(a)
                removed.append(a)
    return removed


def ac3(csp: CSP, arcs: Optional[list[tuple[Var, Var]]] = None):
    """Enforce arc consistency over the given arcs (default: every arc in
    the CSP). Returns (ok, pruned) exactly like forward_checking, so it can
    be dropped in as the `inference` hook for backtracking_search (this is
    "MAC" — Maintaining Arc Consistency — when run after each assignment)."""
    queue = deque(arcs if arcs is not None else
                  [(xi, xj) for xi in csp.variables for xj in csp.neighbors(xi)])
    pruned: list[tuple[Var, Value]] = []

    while queue:
        xi, xj = queue.popleft()
        removed = _revise(csp, xi, xj)
        if removed:
            pruned.extend((xi, v) for v in removed)
            if len(csp.domains[xi]) == 0:
                return False, pruned
            for xk in csp.neighbors(xi):
                if xk != xj:
                    queue.append((xk, xi))
    return True, pruned


def mac(csp: CSP, var: Var, value: Value, assignment: dict):
    """AC-3 restricted to the arcs that could have changed because `var`
    was just assigned — the inference hook used during search ('Maintaining
    Arc Consistency'). Strictly more powerful than forward_checking at the
    cost of propagating further through the graph each step.

    The search records the assignment in `assignment` but never shrinks
    `csp.domains[var]` itself, so AC-3's domain-based consistency check
    would otherwise still see var's *whole* original domain. We first pin
    domain[var] down to exactly {value} (tracked as ordinary prunes, undone
    on backtrack like any other), then propagate outward from there.
    """
    pinned = [(var, v) for v in list(csp.domains[var]) if v != value]
    for _, v in pinned:
        csp.domains[var].remove(v)

    arcs = [(nbr, var) for nbr in csp.neighbors(var) if nbr not in assignment]
    ok, propagated = ac3(csp, arcs)
    return ok, pinned + propagated
