"""Backtracking search with pluggable hooks.

The engine never changes between phases. What changes is what we plug in:
  - select_var   : which unassigned variable to try next   (Phase 2: MRV)
  - order_values : which value to try first                 (Phase 2: LCV)
  - inference    : what to propagate after each assignment  (Phase 2: FC / MAC)

Two entry points:
  - backtracking_search   -> the FIRST solution (or None)
  - find_all_solutions    -> EVERY distinct solution (optionally capped)

Phase-1 defaults are deliberately naive -- this is the measurement baseline.
"""
from __future__ import annotations
from typing import Callable, Optional
from .model import CSP, Var, Value
from .metrics import SearchMetrics


class _NodeBudgetExceeded(Exception):
    """Internal signal used to unwind the recursion once max_nodes is hit."""


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
    of (variable, value) pairs removed -- empty here, so nothing to restore."""
    return True, []


# ---- find the FIRST solution ------------------------------------------------

def backtracking_search(csp: CSP,
                        select_var: Callable = first_unassigned,
                        order_values: Callable = domain_order,
                        inference: Callable = no_inference,
                        metrics: Optional[SearchMetrics] = None,
                        max_nodes: Optional[int] = None):
    """`max_nodes` caps the number of assignments tried, so a runaway search
    (naive backtracking on a hard instance) can't hang a caller such as the
    web demo forever. On cutoff, returns (None, metrics) with
    metrics.timed_out = True instead of raising."""
    metrics = metrics or SearchMetrics()
    metrics.start()
    try:
        result = _backtrack({}, csp, select_var, order_values, inference, metrics, max_nodes)
    except _NodeBudgetExceeded:
        result = None
        metrics.timed_out = True
    metrics.stop()
    metrics.solved = result is not None
    return result, metrics


def _backtrack(assignment, csp, select_var, order_values, inference, metrics, max_nodes=None):
    if csp.is_complete(assignment):
        return assignment

    var = select_var(csp, assignment)

    for value in order_values(csp, var, assignment):
        if csp.is_consistent(var, value, assignment):
            if max_nodes is not None and metrics.nodes >= max_nodes:
                raise _NodeBudgetExceeded()
            metrics.nodes += 1
            assignment[var] = value

            ok, pruned = inference(csp, var, value, assignment)
            metrics.pruned += len(pruned)
            if ok:
                result = _backtrack(assignment, csp, select_var,
                                    order_values, inference, metrics, max_nodes)
                if result is not None:
                    return result

            for (v, val) in pruned:      # undo inference, then the assignment
                csp.domains[v].add(val)
            del assignment[var]
            metrics.backtracks += 1

    return None


# ---- find ALL solutions -----------------------------------------------------

def find_all_solutions(csp: CSP,
                       select_var: Callable = first_unassigned,
                       order_values: Callable = domain_order,
                       inference: Callable = no_inference,
                       metrics: Optional[SearchMetrics] = None,
                       max_solutions: Optional[int] = None):
    """Enumerate every distinct complete, consistent assignment.

    Same search as above, but instead of returning at the first complete
    assignment we RECORD it and keep going, so no branch is skipped.
    `max_solutions` caps the count (useful when a problem has huge numbers
    of solutions); None means find them all.
    """
    metrics = metrics or SearchMetrics()
    solutions: list[dict] = []
    metrics.start()
    _backtrack_all({}, csp, select_var, order_values, inference,
                   metrics, solutions, max_solutions)
    metrics.stop()
    metrics.solved = len(solutions) > 0
    return solutions, metrics


def _backtrack_all(assignment, csp, select_var, order_values, inference,
                   metrics, solutions, max_solutions) -> bool:
    """Returns True to signal 'stop, the cap is reached' up the call stack."""
    if csp.is_complete(assignment):
        solutions.append(dict(assignment))          # store a COPY
        return max_solutions is not None and len(solutions) >= max_solutions

    var = select_var(csp, assignment)

    for value in order_values(csp, var, assignment):
        if csp.is_consistent(var, value, assignment):
            metrics.nodes += 1
            assignment[var] = value

            ok, pruned = inference(csp, var, value, assignment)
            metrics.pruned += len(pruned)
            stop = False
            if ok:
                stop = _backtrack_all(assignment, csp, select_var, order_values,
                                      inference, metrics, solutions, max_solutions)

            for (v, val) in pruned:
                csp.domains[v].add(val)
            del assignment[var]

            if stop:
                return True

    return False
