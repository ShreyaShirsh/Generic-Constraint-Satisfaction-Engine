"""Planning & coordination: robot treasure hunt, gridworld, resource-
constrained project scheduling, multi-agent path finding.

  Robot treasure hunt   planning CSPs for every leg (core/planning.py), then a
                        CSP over the ORDER of treasures -- all_different plus
                        the branch-and-bound predicate (core/optimize.py)
  Gridworld             a planning CSP: rewards become goals, pits are
                        illegal moves; the best plan maximises reward
  Resource planning     start-time variables, "A before B" BinaryRelations,
                        one capacity Predicate per resource, minimise the
                        makespan by branch and bound
  Multi-agent paths     position-at-time variables; agents may never share a
                        cell (NotEqual -- the most common constraint of all)
                        or swap places; AC-3 alone works out which cells each
                        agent can possibly be on at each time step
"""
from __future__ import annotations
import random
from ..core.model import CSP
from ..core.constraints import all_different, BinaryRelation, NotEqual, Predicate
from ..core.backtracking import backtracking_search, first_unassigned
from ..core.inference import mac, ac3
from ..core.heuristics import mrv
from ..core.optimize import branch_and_bound
from ..core.planning import solve_plan
from .search_puzzles import Maze, DIRS


def random_grid(rows: int, cols: int, wall_ratio: float, rng: random.Random, keep=()):
    """Random walls that never cut the free cells into pieces."""
    keep = set(map(tuple, keep))
    grid = [[False] * cols for _ in range(rows)]
    cells = [(r, c) for r in range(rows) for c in range(cols) if (r, c) not in keep]
    rng.shuffle(cells)
    target = int(len(cells) * wall_ratio)
    placed = 0
    for r, c in cells:
        if placed >= target:
            break
        grid[r][c] = True
        if _connected(grid):
            placed += 1
        else:
            grid[r][c] = False
    return grid


def _connected(grid) -> bool:
    free = [(r, c) for r, row in enumerate(grid) for c, w in enumerate(row) if not w]
    if not free:
        return True
    seen, stack = {free[0]}, [free[0]]
    while stack:
        r, c = stack.pop()
        for dr, dc in DIRS.values():
            n = (r + dr, c + dc)
            if 0 <= n[0] < len(grid) and 0 <= n[1] < len(grid[0]) and not grid[n[0]][n[1]] and n not in seen:
                seen.add(n)
                stack.append(n)
    return len(seen) == len(free)


# ======================================================== robot treasure hunt ====

def treasure_instance(rows: int, cols: int, treasures: int, rng: random.Random) -> dict:
    start, exit_ = (0, 0), (rows - 1, cols - 1)
    while True:
        spots = rng.sample([(r, c) for r in range(rows) for c in range(cols)
                            if (r, c) not in (start, exit_)], treasures)
        grid = random_grid(rows, cols, 0.22, rng, keep=[start, exit_, *spots])
        return {"grid": grid, "start": list(start), "exit": list(exit_),
                "treasures": [list(s) for s in spots]}


def solve_treasure(inst: dict) -> dict:
    grid = inst["grid"]
    points = [tuple(inst["start"])] + [tuple(t) for t in inst["treasures"]] + [tuple(inst["exit"])]
    n = len(points)
    legs, total_nodes = {}, 0
    for i in range(n):
        for j in range(i + 1, n):
            r = solve_plan(Maze(grid, points[i], points[j]), max_steps=len(grid) * len(grid[0]))
            total_nodes += r["metrics"].nodes
            legs[(i, j)] = r["states"]
            legs[(j, i)] = r["states"][::-1]
    d = {k: len(v) - 1 for k, v in legs.items()}

    k = n - 2
    order_vars = [("visit", i) for i in range(k)]
    csp = CSP(order_vars, {v: list(range(1, k + 1)) for v in order_vars},
              all_different(order_vars, label="each treasure is collected exactly once"))

    def route(sol):
        seq = [0] + [sol[v] for v in order_vars] + [n - 1]
        return seq

    def cost(sol):
        seq = route(sol)
        return sum(d[(seq[i], seq[i + 1])] for i in range(len(seq) - 1))

    def bound(partial):
        seq = [0]
        for v in order_vars:
            if v not in partial:
                break
            seq.append(partial[v])
        done = sum(d[(seq[i], seq[i + 1])] for i in range(len(seq) - 1))
        left = [t for t in range(1, k + 1) if t not in seq]
        if not left:
            return done + d[(seq[-1], n - 1)]
        return done + max(d[(seq[-1], t)] + d[(t, n - 1)] for t in left)

    r = branch_and_bound(csp, cost, bound, select_var=first_unassigned)
    seq = route(r["solution"])
    path = [points[0]]
    for a, b in zip(seq, seq[1:]):
        path += legs[(a, b)][1:]
    return {"order": seq, "path": [list(p) for p in path], "length": r["cost"],
            "metrics": r["metrics"], "leg_nodes": total_nodes, "census_csp": csp}


# ================================================================== gridworld ====

class GridworldPlan(Maze):
    """Like a maze, but pits are deadly (illegal) and the goal is one gem."""

    def __init__(self, grid, pits, start, gem):
        super().__init__(grid, start, gem)
        self.pits = set(map(tuple, pits))

    def result(self, s, a):
        n = super().result(s, a)
        return None if n is None or n in self.pits else n


def gridworld_instance(rows: int, cols: int, rng: random.Random) -> dict:
    start = (rows - 1, 0)
    cells = [(r, c) for r in range(rows) for c in range(cols) if (r, c) != start]
    rng.shuffle(cells)
    gems = [{"cell": list(cells[0]), "reward": 10}, {"cell": list(cells[1]), "reward": 4}]
    pits = [list(c) for c in cells[2:2 + max(2, rows * cols // 9)]]
    grid = random_grid(rows, cols, 0.1, rng, keep=[start] + [tuple(g["cell"]) for g in gems] + [tuple(p) for p in pits])
    return {"grid": grid, "start": list(start), "gems": gems, "pits": pits, "step_cost": 1}


def solve_gridworld(inst: dict) -> dict:
    """Plan to every gem (pits are illegal moves) and keep the plan with the
    best total: gem reward minus one point per step."""
    best, tried = None, []
    for gem in inst["gems"]:
        r = solve_plan(GridworldPlan(inst["grid"], inst["pits"], inst["start"], gem["cell"]),
                       max_steps=len(inst["grid"]) * len(inst["grid"][0]))
        if r["plan"] is None:
            tried.append({"gem": gem["cell"], "reachable": False})
            continue
        score = gem["reward"] - inst["step_cost"] * len(r["plan"])
        tried.append({"gem": gem["cell"], "reachable": True, "steps": len(r["plan"]), "score": score})
        if best is None or score > best["score"]:
            best = {"gem": gem["cell"], "path": [list(s) for s in r["states"]], "score": score,
                    "nodes": r["metrics"].nodes}
    return {"best": best, "tried": tried}


# ============================================================ resource planning ====

def project_instance(n_tasks: int, rng: random.Random) -> dict:
    names = ["Survey", "Design", "Permits", "Foundation", "Frame", "Plumbing", "Wiring", "Roof",
             "Walls", "Floors", "Paint", "Inspect", "Landscape", "Furnish"][:n_tasks]
    tasks = []
    for i, nm in enumerate(names):
        tasks.append({"name": nm, "duration": rng.randint(1, 5),
                      "crew": rng.randint(1, 3), "crane": rng.choice([0, 0, 1])})
    prec = []
    for j in range(1, n_tasks):
        for i in rng.sample(range(j), min(j, rng.choice([0, 1, 1, 2]))):
            prec.append([i, j])
    return {"tasks": tasks, "precedence": prec, "capacity": {"crew": 4, "crane": 1}}


def _greedy_makespan(tasks, prec, cap) -> int:
    """Serial schedule: place tasks in order at the earliest feasible time."""
    n = len(tasks)
    preds = {i: [a for a, b in prec if b == i] for i in range(n)}
    load: dict = {}
    finish = {}
    for i in range(n):
        t = max((finish[a] for a in preds[i]), default=0)
        while True:
            if all(load.get((res, x), 0) + tasks[i].get(res, 0) <= lim
                   for res, lim in cap.items() for x in range(t, t + tasks[i]["duration"])):
                break
            t += 1
        for res in cap:
            for x in range(t, t + tasks[i]["duration"]):
                load[(res, x)] = load.get((res, x), 0) + tasks[i].get(res, 0)
        finish[i] = t + tasks[i]["duration"]
    return max(finish.values())


def solve_project(inst: dict, max_nodes: int = 150_000) -> dict:
    tasks, prec, cap = inst["tasks"], inst["precedence"], inst["capacity"]
    n = len(tasks)
    horizon = _greedy_makespan(tasks, prec, cap)    # any schedule bounds the optimum
    S = [("start", i) for i in range(n)]
    dur = [t["duration"] for t in tasks]
    domains = {S[i]: list(range(0, horizon - dur[i] + 1)) for i in range(n)}

    constraints = []
    for a, b in prec:
        constraints.append(BinaryRelation(S[a], S[b], lambda x, y, d=dur[a]: x + d <= y,
                                          name="Before",
                                          label=f"{tasks[a]['name']} finishes before {tasks[b]['name']} starts"))
    for res, limit in cap.items():
        need = [t.get(res, 0) for t in tasks]
        users = [S[i] for i in range(n) if need[i]]

        def fits(local, need=need, limit=limit):
            load = {}
            for var, s in local.items():
                i = var[1]
                for time in range(s, s + dur[i]):
                    load[time] = load.get(time, 0) + need[i]
                    if load[time] > limit:
                        return False
            return True

        if users:
            constraints.append(Predicate(users, fits, name="Capacity", check_when_partial=True,
                                         label=f"never more than {limit} {res} in use at once"))
    csp = CSP(S, domains, constraints)

    succ = {i: [] for i in range(n)}
    for a, b in prec:
        succ[a].append(b)
    tail = {}

    def chain(i):                         # longest duration chain starting at task i
        if i not in tail:
            tail[i] = dur[i] + max((chain(j) for j in succ[i]), default=0)
        return tail[i]

    def makespan(sol):
        return max(sol[S[i]] + dur[i] for i in range(n))

    def bound(partial):
        b = max((partial[S[i]] + chain(i) for i in range(n) if S[i] in partial), default=0)
        return max(b, max(chain(i) for i in range(n)))

    topo = sorted(range(n), key=lambda i: -chain(i))
    order_vars = [S[i] for i in topo]
    ordered = CSP(order_vars, {v: domains[v] for v in order_vars}, constraints)
    r = branch_and_bound(ordered, makespan, bound, select_var=mrv, inference=mac,
                         max_nodes=max_nodes)
    starts = [r["solution"][S[i]] for i in range(n)] if r["solution"] else None
    return {"starts": starts, "makespan": r["cost"], "optimal": r["optimal"],
            "improvements": r["improvements"], "metrics": r["metrics"], "census_csp": csp,
            "critical_path": max(chain(i) for i in range(n))}


# ========================================================= multi-agent paths ====

AGENT_NAMES = "ABCDEFGH"


def mapf_instance(rows: int, cols: int, agents: int, rng: random.Random) -> dict:
    cells = [(r, c) for r in range(rows) for c in range(cols)]
    picks = rng.sample(cells, 2 * agents)
    starts, goals = picks[:agents], picks[agents:]
    grid = random_grid(rows, cols, 0.15, rng, keep=picks)
    return {"grid": grid, "starts": [list(s) for s in starts], "goals": [list(g) for g in goals]}


def _adjacent_or_same(a, b):
    return abs(a[0] - b[0]) + abs(a[1] - b[1]) <= 1


def mapf_csp(inst: dict, T: int) -> CSP:
    grid = inst["grid"]
    free = [(r, c) for r, row in enumerate(grid) for c, w in enumerate(row) if not w]
    k = len(inst["starts"])
    V = {(a, t): (a, t) for a in range(k) for t in range(T + 1)}
    variables = list(V)
    domains = {v: free for v in variables}
    constraints = []
    for a in range(k):
        s, g = tuple(inst["starts"][a]), tuple(inst["goals"][a])
        domains[(a, 0)] = [s]
        domains[(a, T)] = [g]
        for t in range(T):
            constraints.append(BinaryRelation((a, t), (a, t + 1), _adjacent_or_same, name="Step",
                                              label=f"agent {AGENT_NAMES[a]} moves at most one cell per tick"))
    for t in range(T + 1):
        for a in range(k):
            for b in range(a + 1, k):
                constraints.append(NotEqual((a, t), (b, t),
                                            label=f"agents {AGENT_NAMES[a]} and {AGENT_NAMES[b]} never share a cell"))
    for t in range(T):
        for a in range(k):
            for b in range(a + 1, k):
                constraints.append(Predicate(
                    [(a, t), (a, t + 1), (b, t), (b, t + 1)],
                    lambda l, a=a, b=b, t=t: not (l[(a, t)] == l[(b, t + 1)] and l[(b, t)] == l[(a, t + 1)]
                                                  and l[(a, t)] != l[(a, t + 1)]),
                    name="NoSwap", label=f"agents {AGENT_NAMES[a]} and {AGENT_NAMES[b]} never swap places"))
    return CSP(variables, domains, constraints)


def solve_mapf(inst: dict, max_T: int = 30) -> dict:
    k = len(inst["starts"])
    lower = 0
    for a in range(k):
        r = solve_plan(Maze(inst["grid"], inst["starts"][a], inst["goals"][a]), max_steps=200)
        if r["plan"] is None:
            return {"paths": None, "reason": f"agent {AGENT_NAMES[a]} can't reach its goal at all"}
        lower = max(lower, len(r["plan"]))
    attempts, nodes = [], 0
    for T in range(lower, max_T + 1):
        csp = mapf_csp(inst, T)
        ok, _ = ac3(csp)                    # propagation alone = reachability in time
        if not ok:
            attempts.append({"T": T, "found": False, "nodes": 0, "by": "propagation"})
            continue
        sol, m = backtracking_search(csp, select_var=mrv, inference=mac, max_nodes=200_000)
        nodes += m.nodes
        attempts.append({"T": T, "found": sol is not None, "nodes": m.nodes, "by": "search"})
        if sol:
            paths = [[list(sol[(a, t)]) for t in range(T + 1)] for a in range(k)]
            return {"paths": paths, "makespan": T, "attempts": attempts, "nodes": nodes,
                    "census_csp": csp}
    return {"paths": None, "attempts": attempts, "reason": "no plan within the time limit"}
