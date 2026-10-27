"""Ordering heuristics — deciding which variable and which value to try
next. Like everything else in `core/`, these only look at domain sizes and
the constraint graph, never at what a variable "means".

  mrv            — Minimum Remaining Values: branch on the variable with the
                    fewest legal values left ("fail fast").
  mrv_degree     — MRV, breaking ties with the degree heuristic (prefer the
                    variable constraining the most other unassigned ones).
  lcv            — Least Constraining Value: try the value that rules out
                    the fewest options for neighbouring variables first.
  shuffled(rng)  — random value order; the puzzle generator uses it to grow
                    a different random solution every time.
"""
from __future__ import annotations
import random
from .model import CSP, Var


def mrv(csp: CSP, assignment: dict) -> Var:
    best, best_size = None, None
    for v in csp.variables:
        if v in assignment:
            continue
        size = len(csp.domains[v])
        if best_size is None or size < best_size:
            best, best_size = v, size
            if size <= 1:
                break
    return best


def mrv_degree(csp: CSP, assignment: dict) -> Var:
    unassigned = [v for v in csp.variables if v not in assignment]

    def degree(v: Var) -> int:
        return -sum(1 for n in csp.neighbors(v) if n not in assignment)

    return min(unassigned, key=lambda v: (len(csp.domains[v]), degree(v)))


def lcv(csp: CSP, var: Var, assignment: dict) -> list:
    """Order var's domain values by how many neighbour values they'd rule
    out, least-constraining first."""
    def ruled_out(value) -> int:
        count = 0
        for nbr in csp.neighbors(var):
            if nbr in assignment:
                continue
            for c in csp.binary_constraints_between(var, nbr):
                for nval in csp.domains[nbr]:
                    a, b = (value, nval) if c.x == var else (nval, value)
                    if not c.holds(a, b):
                        count += 1
        return count

    return sorted(csp.domains[var], key=ruled_out)


def shuffled(rng: random.Random):
    """Value-ordering hook that tries a variable's values in random order."""
    def order(csp: CSP, var: Var, assignment: dict) -> list:
        values = list(csp.domains[var])
        rng.shuffle(values)
        return values
    return order
