"""Min-conflicts — a completely different search paradigm from backtracking,
included to contrast "build a solution incrementally" with "repair a bad
one". Still 100% generic: it only calls `csp.constraints_on(var)` and
`Constraint.is_satisfied`, exactly like backtracking does.

Idea: start with EVERY variable assigned (often badly — many constraints
violated), then repeatedly pick a conflicted variable and reassign it to
whichever value in its domain violates the fewest constraints. For problems
like N-Queens at large n, this finds a solution in a near-constant number of
steps, vastly outperforming systematic backtracking search.
"""
from __future__ import annotations
import random
from typing import Optional
from .model import CSP, Var
from .metrics import SearchMetrics


def _conflicts(csp: CSP, var: Var, value, assignment: dict) -> int:
    trial = dict(assignment)
    trial[var] = value
    return sum(1 for c in csp.constraints_on(var) if not c.is_satisfied(trial))


def _conflicted_variables(csp: CSP, assignment: dict) -> list[Var]:
    return [v for v in csp.variables
            if any(not c.is_satisfied(assignment) for c in csp.constraints_on(v))]


def min_conflicts(csp: CSP, max_steps: int = 100_000,
                  initial: Optional[dict] = None,
                  rng: Optional[random.Random] = None,
                  metrics: Optional[SearchMetrics] = None):
    """Local-search solver. Returns (assignment_or_None, metrics).

    `initial` lets a caller seed a starting assignment (e.g. one value per
    variable chosen to minimise conflicts, the standard N-Queens trick);
    otherwise every variable starts at a uniformly random domain value.
    """
    rng = rng or random.Random()
    metrics = metrics or SearchMetrics()
    metrics.start()

    assignment = dict(initial) if initial else {
        v: rng.choice(list(csp.domains[v])) for v in csp.variables
    }

    for _ in range(max_steps):
        conflicted = _conflicted_variables(csp, assignment)
        if not conflicted:
            metrics.stop()
            metrics.solved = True
            return assignment, metrics

        var = rng.choice(conflicted)
        values = list(csp.domains[var])
        best = min(_conflicts(csp, var, v, assignment) for v in values)
        choices = [v for v in values if _conflicts(csp, var, v, assignment) == best]
        assignment[var] = rng.choice(choices)
        metrics.nodes += 1

    metrics.stop()
    metrics.solved = False
    return None, metrics
