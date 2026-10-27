"""Planning as constraint satisfaction.

Search problems -- the 8-puzzle, Tower of Hanoi, river crossing, Sokoban,
mazes, the pocket cube -- look nothing like Sudoku: they ask for a SEQUENCE
of moves, not a filled-in grid. They still compile to the same CSP:

  variables   = step_1 .. step_T      (the action taken at each time step)
  domains     = the problem's action alphabet (e.g. {up, down, left, right})
  constraints = ONE Predicate over all the steps:
                  "executing these actions from the start is legal, never
                   revisits a state, can still reach the goal within the
                   budget, and finishes in a goal state"

The Predicate judges partial plans (it re-simulates the prefix), so the
ordinary backtracking search prunes an illegal or hopeless prefix the moment
it appears. Two budget rules turn plain backtracking into well-known
optimal planners -- without changing the search:

  * unit costs:  T = h(start), h(start)+1, ...  (iterative deepening on the
                 number of variables; with an admissible lower bound h this
                 is IDA*). The first T that has a solution is the optimum.
  * real costs:  a fixed number of steps plus a DONE action; the budget is a
                 cost bound raised to the smallest f-value that broke it.

The planning problem itself only describes the world (actions, result, goal,
lower bound). It never searches.
"""
from __future__ import annotations
import math
from typing import Any, Hashable, Iterable, Optional
from .model import CSP
from .constraints import Predicate
from .backtracking import backtracking_search, first_unassigned
from .inference import forward_checking
from .metrics import SearchMetrics

STEP = "step"
DONE = "DONE"


class PlanningProblem:
    """Describe a world; never search it."""
    alphabet: list = []           # every action label that can ever occur
    initial: Any = None

    def actions(self, state) -> Iterable:
        return self.alphabet

    def result(self, state, action):
        """The next state, or None if the action is illegal here."""
        raise NotImplementedError

    def is_goal(self, state) -> bool:
        raise NotImplementedError

    def h(self, state) -> float:
        """Admissible lower bound on the remaining cost (0 = no heuristic)."""
        return 0

    def key(self, state) -> Hashable:
        return state

    def cost(self, state, action, nxt) -> float:
        return 1


class PlanChecker:
    """The one constraint of every planning CSP (see module docstring).

    It keeps the simulated prefix as a stack, so consecutive checks during a
    depth-first search only simulate the one new step."""

    def __init__(self, problem: PlanningProblem, steps: int, budget: float,
                 allow_done: bool = False):
        self.p = problem
        self.steps = steps
        self.budget = budget
        self.allow_done = allow_done
        self.actions: list = []
        self.states: list = [problem.initial]
        self.costs: list = [0.0]
        self.keys: list = [problem.key(problem.initial)]
        self.seen: dict = {self.keys[0]: 1}
        self.min_exceeded = math.inf

    def _pop(self) -> None:
        self.actions.pop()
        self.states.pop()
        self.costs.pop()
        k = self.keys.pop()
        if k is not None:
            self.seen[k] -= 1
            if not self.seen[k]:
                del self.seen[k]

    def sync(self, prefix: list) -> bool:
        j, n = 0, min(len(prefix), len(self.actions))
        while j < n and prefix[j] == self.actions[j]:
            j += 1
        while len(self.actions) > j:
            self._pop()
        for a in prefix[j:]:
            state = self.states[-1]
            if a == DONE:
                if not self.allow_done or not self.p.is_goal(state):
                    return False
                nxt, step_cost, k = state, 0.0, None
            else:
                if self.actions and self.actions[-1] == DONE:
                    return False                      # nothing happens after DONE
                nxt = self.p.result(state, a)
                if nxt is None:
                    return False
                k = self.p.key(nxt)
                if k in self.seen:
                    return False                      # never revisit a state
                step_cost = self.p.cost(state, a, nxt)
            self.actions.append(a)
            self.states.append(nxt)
            self.costs.append(self.costs[-1] + step_cost)
            self.keys.append(k)
            if k is not None:
                self.seen[k] = self.seen.get(k, 0) + 1
        return True

    def __call__(self, local: dict) -> bool:
        prefix, t = [], 1
        while (STEP, t) in local:
            prefix.append(local[(STEP, t)])
            t += 1
        if not self.sync(prefix):
            return False
        state = self.states[-1]
        done = bool(self.actions) and self.actions[-1] == DONE
        f = self.costs[-1] + (0 if done else self.p.h(state))
        if f > self.budget + 1e-9:
            self.min_exceeded = min(self.min_exceeded, f)
            return False
        if len(prefix) == self.steps:
            return self.p.is_goal(state)
        return True


def plan_csp(problem: PlanningProblem, steps: int, budget: float,
             allow_done: bool = False) -> tuple[CSP, PlanChecker]:
    checker = PlanChecker(problem, steps, budget, allow_done)
    variables = [(STEP, t) for t in range(1, steps + 1)]
    alphabet = list(problem.alphabet) + ([DONE] if allow_done else [])
    constraint = Predicate(variables, checker, name="LegalPlan", check_when_partial=True,
                           label="the plan is legal and reaches the goal")
    return CSP(variables, {v: alphabet for v in variables}, [constraint]), checker


def _ordering(problem: PlanningProblem, checker: PlanChecker):
    """Value ordering: try the actions whose result looks closest to the goal
    first (a best-first flavour inside depth-first search)."""
    def order(csp, var, assignment):
        prefix = [assignment[(STEP, t)] for t in range(1, var[1])]
        if not checker.sync(prefix):
            return []
        state = checker.states[-1]
        options = []
        if checker.allow_done and problem.is_goal(state):
            options.append((-1, DONE))
        if checker.actions and checker.actions[-1] == DONE:
            return [DONE]
        for a in problem.actions(state):
            nxt = problem.result(state, a)
            if nxt is not None:
                options.append((problem.cost(state, a, nxt) + problem.h(nxt), a))
        options.sort(key=lambda x: x[0])
        return [a for _, a in options]
    return order


def solve_plan(problem: PlanningProblem, max_steps: int = 60,
               max_nodes: int = 400_000, weighted: bool = False) -> dict:
    """Find an optimal plan by solving a sequence of planning CSPs.

    Returns {"plan", "states", "cost", "iterations", "metrics"}; plan is None
    if nothing was found within max_steps / max_nodes.
    """
    total = SearchMetrics()
    total.start()
    iterations = []
    h0 = problem.h(problem.initial)
    budget = h0 if weighted else max(1, math.ceil(h0 - 1e-9))
    found = None

    if problem.is_goal(problem.initial):
        found = ([], [problem.initial], 0.0)

    while found is None:
        steps = max_steps if weighted else int(budget)
        if steps > max_steps:
            break
        csp, checker = plan_csp(problem, steps, budget, allow_done=weighted)
        left = max_nodes - total.nodes
        if left <= 0:
            total.timed_out = True
            break
        solution, m = backtracking_search(csp, select_var=first_unassigned,
                                          order_values=_ordering(problem, checker),
                                          inference=forward_checking, max_nodes=left)
        total.nodes += m.nodes
        total.backtracks += m.backtracks
        total.pruned += m.pruned
        iterations.append({"budget": round(budget, 3), "steps": steps, "nodes": m.nodes,
                           "found": solution is not None})
        if solution is not None:
            actions = [solution[(STEP, t)] for t in range(1, steps + 1)]
            checker.sync(actions)
            plan = [a for a in actions if a != DONE]
            found = (plan, checker.states[:len(plan) + 1], checker.costs[len(plan)])
            break
        if m.timed_out:
            total.timed_out = True
            break
        if weighted:
            if checker.min_exceeded == math.inf:
                break                               # nothing was cut off: no plan at all
            budget = checker.min_exceeded
        elif checker.min_exceeded == math.inf:
            budget += 1                             # only the horizon was too short
        else:
            budget = max(budget + 1, math.ceil(checker.min_exceeded - 1e-9))

    total.stop()
    total.solved = found is not None
    plan, states, cost = found if found else (None, None, None)
    return {"plan": plan, "states": states, "cost": cost,
            "iterations": iterations, "metrics": total}
