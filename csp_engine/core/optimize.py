"""Constraint optimisation = constraint satisfaction + ONE more predicate.

TSP, knapsack, scheduling and shortest paths don't ask "is there a
solution?" but "which solution is best?". Branch and bound answers that with
the machinery we already have: add a single Predicate over every variable,

    bound(partial assignment) < cost of the best solution found so far

and keep searching after each solution. Every time a better solution
appears, the predicate silently tightens, so the rest of the search only
explores branches that could still beat it. When the search ends, the last
solution recorded is optimal (provided `bound` never overestimates).
"""
from __future__ import annotations
import math
from typing import Callable, Optional
from .model import CSP
from .constraints import Predicate
from .backtracking import find_all_solutions, domain_order
from .inference import forward_checking
from .heuristics import mrv
from .metrics import SearchMetrics


def branch_and_bound(csp: CSP, cost: Callable[[dict], float],
                     bound: Optional[Callable[[dict], float]] = None,
                     select_var=mrv, order_values=domain_order,
                     inference=forward_checking,
                     max_nodes: Optional[int] = 500_000) -> dict:
    """Minimise `cost(solution)` over the CSP's solutions.

    `bound(partial)` must be a lower bound on the cost of any completion of
    the partial assignment (default: no pruning). Returns {"solution",
    "cost", "improvements", "metrics", "optimal"}; optimal is False if the
    node budget ran out first (the solution is then the best found).
    """
    best = {"cost": math.inf, "solution": None}
    improvements: list[dict] = []
    metrics = SearchMetrics()

    bound_fn = bound or (lambda partial: -math.inf)
    better = Predicate(csp.variables, lambda local: bound_fn(local) < best["cost"] - 1e-9,
                       name="Bound", check_when_partial=True,
                       label="better than the best solution found so far")
    full = CSP(csp.variables, {v: csp.domains[v].values for v in csp.variables},
               list(csp.constraints) + [better], groups=csp.groups)

    def on_solution(solution: dict) -> bool:
        c = cost(solution)
        if c < best["cost"]:
            best["cost"], best["solution"] = c, solution
            improvements.append({"cost": c, "nodes": metrics.nodes})
        return False                                # keep looking for better

    find_all_solutions(full, select_var=select_var, order_values=order_values,
                       inference=inference, metrics=metrics, max_nodes=max_nodes,
                       on_solution=on_solution)
    metrics.solved = best["solution"] is not None
    return {"solution": best["solution"], "cost": best["cost"] if best["solution"] else None,
            "improvements": improvements, "metrics": metrics,
            "optimal": not metrics.timed_out}
