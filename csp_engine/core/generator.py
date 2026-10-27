"""Puzzle generation — for ANY CSP, not one puzzle type.

Given only a rule set (a CSP whose domains hold every allowed value), the
generator:
  1. grows a random complete solution (backtracking with shuffled values),
  2. starts from "every variable given" and removes givens one at a time,
     keeping a removal only if the puzzle still has exactly ONE solution
     (checked by the same search engine, capped at 2 solutions),
  3. grades the result with the human-style reasoner and, if it's harder
     than requested, adds givens back until it isn't.

Because steps 1-3 only talk to the CSP interface, the same code generates
Sudoku, Futoshiki, KenKen, Killer Sudoku -- and puzzle types a user invents
in the Studio's builder five minutes earlier.
"""
from __future__ import annotations
import random
import time
from typing import Optional
from .model import CSP, Var
from .backtracking import backtracking_search, find_all_solutions
from .inference import mac_plus
from .heuristics import mrv, shuffled
from .explain import grade as grade_puzzle, Grade

SOLVE_BUDGET = 60_000        # nodes; generous for puzzles up to 9x9
CHECK_BUDGET = 3_000         # nodes per uniqueness check while digging -- if
                             # uniqueness can't be proved quickly the given is
                             # simply kept, costing one extra clue, never a
                             # wrong (non-unique) puzzle


def _base_domains(csp: CSP) -> dict[Var, set]:
    return {v: set(csp.domains[v]) for v in csp.variables}


def _with_givens(csp: CSP, base: dict, givens: dict) -> None:
    csp.reset_domains({v: ({givens[v]} if v in givens else base[v]) for v in csp.variables})


def random_solution(csp: CSP, rng: random.Random) -> Optional[dict]:
    solution, _ = backtracking_search(csp, select_var=mrv, order_values=shuffled(rng),
                                      inference=mac_plus, max_nodes=SOLVE_BUDGET)
    return dict(solution) if solution else None


def count_solutions(csp: CSP, limit: int = 2, budget: int = SOLVE_BUDGET) -> Optional[int]:
    """Number of solutions, capped at `limit`. None if the search budget ran
    out before it could tell."""
    solutions, metrics = find_all_solutions(csp, select_var=mrv, inference=mac_plus,
                                            max_solutions=limit, max_nodes=budget)
    if metrics.timed_out and len(solutions) < limit:
        return None
    return len(solutions)


def dig(csp: CSP, base: dict, solution: dict, rng: random.Random,
        keep: frozenset = frozenset()) -> tuple[dict, int]:
    """Remove givens while the solution stays unique. Returns (givens, checks)."""
    givens = dict(solution)
    order = [v for v in csp.variables if v not in keep]
    rng.shuffle(order)
    checks = 0
    for v in order:
        trial = {u: x for u, x in givens.items() if u != v}
        _with_givens(csp, base, trial)
        checks += 1
        if count_solutions(csp, budget=CHECK_BUDGET) == 1:
            givens = trial
    return givens, checks


def _grade(csp: CSP, base: dict, givens: dict) -> Grade:
    _with_givens(csp, base, {})
    return grade_puzzle(csp, givens)


def generate(csp: CSP, target_level: Optional[int] = None,
             rng: Optional[random.Random] = None,
             time_budget: float = 8.0) -> dict:
    """Generate a uniquely-solvable puzzle from the rule set `csp`.

    `target_level` (1 Easy .. 4 Expert, None = whatever comes out) steers
    difficulty. Returns {"givens", "solution", "grade", "stats"}. The CSP's
    domains are left exactly as they were found.
    """
    rng = rng or random.Random()
    base = _base_domains(csp)
    deadline = time.perf_counter() + time_budget
    best = None
    attempts = checks = 0

    try:
        while True:
            attempts += 1
            _with_givens(csp, base, {})
            solution = random_solution(csp, rng)
            if solution is None:
                raise ValueError("these rules have no solution at all")

            givens, n = dig(csp, base, solution, rng)
            checks += n
            g = _grade(csp, base, givens)

            # Too hard for the request: hand back givens until it isn't.
            if target_level is not None and g.level > target_level:
                missing = [v for v in csp.variables if v not in givens]
                rng.shuffle(missing)
                for v in missing:
                    givens[v] = solution[v]
                    g = _grade(csp, base, givens)
                    if g.level <= target_level:
                        break

            distance = 0 if target_level is None else abs(g.level - target_level)
            if best is None or distance < best[0]:
                best = (distance, givens, solution, g)
            if distance == 0 or time.perf_counter() > deadline:
                break
    finally:
        csp.reset_domains(base)

    _, givens, solution, g = best
    return {
        "givens": givens,
        "solution": solution,
        "grade": g,
        "stats": {"attempts": attempts, "uniqueness_checks": checks},
    }
