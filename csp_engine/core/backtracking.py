"""Backtracking search with pluggable hooks.

The engine never changes between phases. What changes is what we plug in:
  - select_var   : which unassigned variable to try next   (Phase 2: MRV)
  - order_values : which value to try first                 (Phase 2: LCV)
  - inference    : what to propagate after each assignment  (Phase 2: FC / MAC)

Phase-1 defaults are deliberately naive — this is the measurement baseline.
"""
from __future__ import annotations
from typing import Callable, Optional
from .model import CSP, Var, Value
from .metrics import SearchMetrics


# ---- default (naive) hooks --------------------------------------------------

def first_unassigned(csp: CSP, assignment: dict) -> Var:
    """Just take the next variable in declaration order."""
    for v in csp.variables:
        if v not in assignment:
            return v
    raise RuntimeError("no unassigned variable (should not happen)")


def domain_order(csp: CSP, var: Var, assignment: dict) -> list:
    """Try values in whatever order the domain gives."""
    return list(csp.domains[var])


def no_inference(csp: CSP, var: Var, value: Value, assignment: dict):
    """Phase 1: infer nothing. Returns (ok, pruned) where pruned is the list
    of (variable, value) pairs removed — empty here, so nothing to restore."""
    return True, []


# ---- the search itself ------------------------------------------------------

def backtracking_search(csp: CSP,
                        select_var: Callable = first_unassigned,
                        order_values: Callable = domain_order,
                        inference: Callable = no_inference,
                        metrics: Optional[SearchMetrics] = None):
    metrics = metrics or SearchMetrics()
    metrics.start()
    result = _backtrack({}, csp, select_var, order_values, inference, metrics)
    metrics.stop()
    metrics.solved = result is not None
    return result, metrics


def _backtrack(assignment, csp, select_var, order_values, inference, metrics):
    if csp.is_complete(assignment):
        return assignment

    var = select_var(csp, assignment)

    for value in order_values(csp, var, assignment):
        if csp.is_consistent(var, value, assignment):
            metrics.nodes += 1
            assignment[var] = value

            ok, pruned = inference(csp, var, value, assignment)
            metrics.pruned += len(pruned)
            if ok:
                result = _backtrack(assignment, csp, select_var,
                                    order_values, inference, metrics)
                if result is not None:
                    return result

            # dead end: undo inference's pruning, then undo the assignment
            for (v, val) in pruned:
                csp.domains[v].add(val)
            del assignment[var]
            metrics.backtracks += 1

    return None
