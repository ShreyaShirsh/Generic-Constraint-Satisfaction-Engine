"""Backtracking search with pluggable hooks.

The engine never changes between problems. What changes is what we plug in:
  - select_var   : which unassigned variable to try next   (e.g. MRV)
  - order_values : which value to try first                 (e.g. LCV)
  - inference    : what to propagate after each assignment  (e.g. FC / MAC)
  - tracer       : optional observer told about every step  (the Studio's
                   "watch the AI think" replay)

Two entry points:
  - backtracking_search   -> the FIRST solution (or None)
  - find_all_solutions    -> EVERY distinct solution (optionally capped)

The defaults are deliberately naive -- this is the measurement baseline.
"""
from __future__ import annotations
from typing import Callable, Optional
from .model import CSP, Var, Value
from .metrics import SearchMetrics


class SearchAborted(Exception):
    """Raised (by the node budget or by a tracer) to stop a search early.
    The search catches it and reports metrics.timed_out = True. Domains are
    NOT restored after an abort -- callers rebuild or reset the CSP. (A search
    that finishes normally, with or without a solution, always leaves the
    domains exactly as it found them.)"""


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
    """Infer nothing. Returns (ok, pruned) where pruned is the list of
    (variable, value) pairs removed -- empty here, so nothing to restore."""
    return True, []


def _no_trace(event: str, var: Var, value: Value) -> None:
    pass


# ---- the shared recursive core ----------------------------------------------

class _Search:
    def __init__(self, csp, select_var, order_values, inference, metrics,
                 max_nodes, tracer, solutions=None, max_solutions=None, on_solution=None):
        self.csp = csp
        self.select_var = select_var
        self.order_values = order_values
        self.inference = inference
        self.metrics = metrics
        self.max_nodes = max_nodes
        self.trace = tracer or _no_trace
        self.solutions = solutions          # None -> stop at the first solution
        self.max_solutions = max_solutions
        self.on_solution = on_solution      # optional callback(solution) -> stop?

    def run(self, assignment: dict) -> bool:
        """Returns True when the search should stop (first solution found,
        or the all-solutions cap reached)."""
        csp, metrics, trace = self.csp, self.metrics, self.trace
        if csp.is_complete(assignment):
            trace("solution", None, None)
            if self.on_solution is not None:
                return bool(self.on_solution(dict(assignment)))
            if self.solutions is None:
                return True
            self.solutions.append(dict(assignment))
            return self.max_solutions is not None and len(self.solutions) >= self.max_solutions

        var = self.select_var(csp, assignment)

        for value in self.order_values(csp, var, assignment):
            if not csp.is_consistent(var, value, assignment):
                continue
            if self.max_nodes is not None and metrics.nodes >= self.max_nodes:
                raise SearchAborted()
            metrics.nodes += 1
            assignment[var] = value
            trace("assign", var, value)

            ok, pruned = self.inference(csp, var, value, assignment)
            metrics.pruned += len(pruned)
            for v, val in pruned:
                trace("prune", v, val)

            stop = ok and self.run(assignment)

            for v, val in pruned:            # undo inference, then the assignment
                csp.domains[v].add(val)
                if not stop:
                    trace("restore", v, val)
            if stop:                         # keep the solution, but leave the
                return True                  # domains exactly as we found them
            del assignment[var]
            metrics.backtracks += 1
            trace("unassign", var, value)

        return False


# ---- find the FIRST solution ------------------------------------------------

def backtracking_search(csp: CSP,
                        select_var: Callable = first_unassigned,
                        order_values: Callable = domain_order,
                        inference: Callable = no_inference,
                        metrics: Optional[SearchMetrics] = None,
                        max_nodes: Optional[int] = None,
                        tracer: Optional[Callable[[str, Var, Value], None]] = None):
    """`max_nodes` caps the number of assignments tried, so a runaway search
    (naive backtracking on a hard instance) can't hang a caller forever. On
    cutoff, returns (None, metrics) with metrics.timed_out = True.

    `tracer(event, var, value)` is called for every step: "assign", "prune",
    "restore", "unassign" and "solution". It may raise SearchAborted to stop."""
    metrics = metrics or SearchMetrics()
    metrics.start()
    assignment: dict = {}
    search = _Search(csp, select_var, order_values, inference, metrics, max_nodes, tracer)
    try:
        found = search.run(assignment)
    except SearchAborted:
        found = False
        metrics.timed_out = True
    metrics.stop()
    metrics.solved = found
    return (assignment if found else None), metrics


# ---- find ALL solutions -----------------------------------------------------

def find_all_solutions(csp: CSP,
                       select_var: Callable = first_unassigned,
                       order_values: Callable = domain_order,
                       inference: Callable = no_inference,
                       metrics: Optional[SearchMetrics] = None,
                       max_solutions: Optional[int] = None,
                       max_nodes: Optional[int] = None,
                       on_solution: Optional[Callable[[dict], bool]] = None):
    """Enumerate every distinct complete, consistent assignment.

    Same search as above, but each complete assignment is RECORDED and the
    search keeps going. `max_solutions` caps the count (the puzzle generator
    uses max_solutions=2 to ask "is the solution unique?").

    `on_solution(solution) -> stop?` is called for each solution instead of
    recording it -- branch-and-bound uses it to tighten its bound mid-search.
    """
    metrics = metrics or SearchMetrics()
    solutions: list[dict] = []
    metrics.start()
    search = _Search(csp, select_var, order_values, inference, metrics, max_nodes,
                     None, solutions, max_solutions, on_solution)
    try:
        search.run({})
    except SearchAborted:
        metrics.timed_out = True
    metrics.stop()
    metrics.solved = len(solutions) > 0
    return solutions, metrics
