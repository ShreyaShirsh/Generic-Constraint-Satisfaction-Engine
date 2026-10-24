"""Ordering heuristics — deciding which variable and which value to try
next. Like everything else in `core/`, these only look at domain sizes and
the constraint graph, never at what a variable "means".

  mrv            — Minimum Remaining Values: branch on the variable with the
                    fewest legal values left ("fail fast": if a branch is
                    doomed, find out immediately instead of after 10 more
                    assignments).
  mrv_degree     — MRV, breaking ties with the degree heuristic (prefer the
                    variable involved in the most constraints on other
                    unassigned variables — picking it prunes the most).
  lcv            — Least Constraining Value: try the value that rules out
                    the fewest options for neighbouring variables first,
                    keeping the rest of the search as flexible as possible.
"""
from __future__ import annotations
from .model import CSP, Var


def mrv(csp: CSP, assignment: dict) -> Var:
    unassigned = [v for v in csp.variables if v not in assignment]
    return min(unassigned, key=lambda v: len(csp.domains[v]))


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
            for c in csp.constraints_between(var, nbr):
                if not hasattr(c, "holds"):
                    continue
                for nval in csp.domains[nbr]:
                    a, b = (value, nval) if c.x == var else (nval, value)
                    if not c.holds(a, b):
                        count += 1
        return count

    return sorted(csp.domains[var], key=ruled_out)
