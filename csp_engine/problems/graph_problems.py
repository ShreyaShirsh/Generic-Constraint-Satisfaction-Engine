"""Graphs & optimisation: random political maps, TSP, shortest paths,
knapsack, random exam timetables.

Optimisation problems are ordinary CSPs plus ONE extra predicate,
"better than the best solution found so far" (core/optimize.py); shortest
paths are planning CSPs with costs (core/planning.py).
"""
from __future__ import annotations
import heapq
import math
import random
from collections import deque
from ..core.model import CSP
from ..core.constraints import all_different, BinaryRelation, Predicate
from ..core.backtracking import first_unassigned
from ..core.optimize import branch_and_bound
from ..core.planning import PlanningProblem, solve_plan
from .graph_colouring import graph_colouring_csp

# ========================================================== political maps ====

def random_map(rows: int, cols: int, regions: int, rng: random.Random) -> dict:
    """Carve a grid into `regions` connected countries by random flood-fill."""
    owner = [[-1] * cols for _ in range(rows)]
    cells = [(r, c) for r in range(rows) for c in range(cols)]
    seeds = rng.sample(cells, regions)
    frontier = []
    for i, (r, c) in enumerate(seeds):
        owner[r][c] = i
        frontier.append((r, c))
    while frontier:
        k = rng.randrange(len(frontier))
        r, c = frontier[k]
        options = [(r + dr, c + dc) for dr, dc in ((1, 0), (-1, 0), (0, 1), (0, -1))
                   if 0 <= r + dr < rows and 0 <= c + dc < cols and owner[r + dr][c + dc] == -1]
        if not options:
            frontier.pop(k)
            continue
        nr, nc = rng.choice(options)
        owner[nr][nc] = owner[r][c]
        frontier.append((nr, nc))
    names = [f"R{i + 1}" for i in range(regions)]
    adjacency = {n: set() for n in names}
    for r in range(rows):
        for c in range(cols):
            for rr, cc in ((r + 1, c), (r, c + 1)):
                if rr < rows and cc < cols and owner[rr][cc] != owner[r][c]:
                    a, b = names[owner[r][c]], names[owner[rr][cc]]
                    adjacency[a].add(b)
                    adjacency[b].add(a)
    return {"grid": [[names[x] for x in row] for row in owner],
            "adjacency": {k: sorted(v) for k, v in adjacency.items()}}


AUSTRALIA_LAYOUT = {   # rough positions for drawing the classic map as a graph
    "WA": (15, 50), "NT": (42, 25), "SA": (45, 58), "Q": (72, 30),
    "NSW": (75, 62), "V": (68, 82), "T": (72, 97),
}

# ===================================================================== TSP ====

def tsp_instance(n: int, rng: random.Random) -> list:
    return [[round(rng.uniform(4, 96), 1), round(rng.uniform(4, 96), 1)] for _ in range(n)]


def _dist(a, b):
    return math.hypot(a[0] - b[0], a[1] - b[1])


def solve_tsp(cities: list, max_nodes: int = 400_000) -> dict:
    """variables pos_0..pos_n-1 = which city is visited k-th; all_different
    (each city exactly once) plus the branch-and-bound predicate."""
    n = len(cities)
    d = [[_dist(a, b) for b in cities] for a in cities]
    min_out = [min(d[i][j] for j in range(n) if j != i) if n > 1 else 0 for i in range(n)]
    pos = [("pos", k) for k in range(n)]
    domains = {p: list(range(n)) for p in pos}
    domains[pos[0]] = [0]                                        # tours are cycles: start at city 1
    constraints = list(all_different(pos, label="each city is visited exactly once"))
    if n > 2:                                                    # a tour and its reverse are the same
        constraints.append(BinaryRelation(pos[1], pos[-1], lambda a, b: a < b, name="Direction",
                                          label="count each tour in one direction only"))
    csp = CSP(pos, domains, constraints)

    def tour_len(sol):
        order = [sol[p] for p in pos]
        return sum(d[order[i]][order[(i + 1) % n]] for i in range(n))

    def bound(partial):
        order = []
        for p in pos:
            if p not in partial:
                break
            order.append(partial[p])
        done = sum(d[order[i]][order[i + 1]] for i in range(len(order) - 1))
        left = set(range(n)) - set(order)
        return done + (min_out[order[-1]] if order and left else 0) + sum(min_out[c] for c in left)

    def nearest_first(csp_, var, assignment):
        k = var[1]
        if k == 0:
            return [0]
        prev = assignment[pos[k - 1]]
        return sorted(csp_.domains[var], key=lambda c: d[prev][c])

    r = branch_and_bound(csp, tour_len, bound, select_var=first_unassigned,
                         order_values=nearest_first, max_nodes=max_nodes)
    tour = [r["solution"][p] for p in pos] if r["solution"] else None

    # nearest-neighbour tour for comparison
    nn, left = [0], set(range(1, n))
    while left:
        nxt = min(left, key=lambda c: d[nn[-1]][c])
        nn.append(nxt)
        left.discard(nxt)
    nn_len = sum(d[nn[i]][nn[(i + 1) % n]] for i in range(n))
    return {"tour": tour, "length": r["cost"], "optimal": r["optimal"],
            "improvements": r["improvements"], "metrics": r["metrics"],
            "nearest_neighbour": {"tour": nn, "length": nn_len}, "census_csp": csp}


# =========================================================== shortest path ====

def random_road_graph(n: int, rng: random.Random, k: int = 3) -> dict:
    pts = [[round(rng.uniform(4, 96), 1), round(rng.uniform(4, 96), 1)] for _ in range(n)]
    edges = {}
    for i in range(n):
        near = sorted(range(n), key=lambda j: _dist(pts[i], pts[j]))[1:k + 1]
        for j in near:
            a, b = min(i, j), max(i, j)
            edges[(a, b)] = round(_dist(pts[a], pts[b]) * rng.uniform(1.0, 1.6), 1)
    # make sure the graph is connected
    comp = _components(n, edges)
    while len(comp) > 1:
        a, b = comp[0], comp[1]
        i, j = min(((i, j) for i in a for j in b), key=lambda p: _dist(pts[p[0]], pts[p[1]]))
        edges[(min(i, j), max(i, j))] = round(_dist(pts[i], pts[j]) * 1.2, 1)
        comp = _components(n, edges)
    return {"points": pts, "edges": [[a, b, w] for (a, b), w in sorted(edges.items())]}


def _components(n, edges):
    adj = {i: set() for i in range(n)}
    for a, b in edges:
        adj[a].add(b)
        adj[b].add(a)
    seen, out = set(), []
    for s in range(n):
        if s in seen:
            continue
        comp, q = [], deque([s])
        seen.add(s)
        while q:
            v = q.popleft()
            comp.append(v)
            for u in adj[v]:
                if u not in seen:
                    seen.add(u)
                    q.append(u)
        out.append(comp)
    return out


class RoadTrip(PlanningProblem):
    """state = current junction; action = the junction to drive to next."""

    def __init__(self, points, edges, source, target):
        self.pts = points
        self.adj = {i: {} for i in range(len(points))}
        for a, b, w in edges:
            self.adj[a][b] = w
            self.adj[b][a] = w
        self.alphabet = list(range(len(points)))
        self.initial, self.target = source, target

    def actions(self, s):
        return list(self.adj[s])

    def result(self, s, a):
        return a if a in self.adj[s] else None

    def cost(self, s, a, nxt):
        return self.adj[s][a]

    def is_goal(self, s):
        return s == self.target

    def h(self, s):
        return _dist(self.pts[s], self.pts[self.target])        # roads are never shorter


def dijkstra(points, edges, s, t):
    adj = {i: [] for i in range(len(points))}
    for a, b, w in edges:
        adj[a].append((b, w))
        adj[b].append((a, w))
    dist, prev, pq = {s: 0}, {}, [(0, s)]
    while pq:
        dv, v = heapq.heappop(pq)
        if v == t:
            break
        if dv > dist.get(v, math.inf):
            continue
        for u, w in adj[v]:
            if dv + w < dist.get(u, math.inf):
                dist[u], prev[u] = dv + w, v
                heapq.heappush(pq, (dv + w, u))
    path, v = [t], t
    while v != s:
        v = prev[v]
        path.append(v)
    return path[::-1], dist[t]


def solve_road(points, edges, s, t) -> dict:
    r = solve_plan(RoadTrip(points, edges, s, t), max_steps=len(points) - 1, weighted=True,
                   max_nodes=400_000)
    path = r["states"]
    return {"path": path, "cost": r["cost"], "iterations": r["iterations"], "metrics": r["metrics"]}


# ================================================================= knapsack ====

def knapsack_instance(n: int, rng: random.Random) -> dict:
    names = ["tent", "stove", "rope", "camera", "laptop", "book", "water", "food", "jacket", "torch",
             "map", "knife", "radio", "first-aid", "boots", "drone", "guitar", "binoculars",
             "blanket", "phone", "charger", "snacks", "tripod", "hammock", "compass"]
    items = []
    for i in range(n):
        w = rng.randint(1, 12)
        items.append({"name": names[i % len(names)] + ("" if i < len(names) else f" {i}"),
                      "weight": w, "value": max(1, int(w * rng.uniform(0.6, 2.4) + rng.randint(0, 6)))})
    cap = max(5, int(sum(it["weight"] for it in items) * rng.uniform(0.35, 0.5)))
    return {"items": items, "capacity": cap}


def solve_knapsack(items: list, capacity: int) -> dict:
    """variables take_i in {1, 0}; ONE capacity predicate (total weight <=
    capacity) + the branch-and-bound predicate (value can still beat the
    best), whose bound is the fractional 'fill the rest greedily' relaxation."""
    order = sorted(range(len(items)), key=lambda i: -items[i]["value"] / items[i]["weight"])
    vars_ = [("take", i) for i in order]
    w = {("take", i): items[i]["weight"] for i in order}
    v = {("take", i): items[i]["value"] for i in order}

    capacity_ok = Predicate(vars_, lambda l: sum(w[x] for x, t in l.items() if t) <= capacity,
                            name="Capacity", check_when_partial=True,
                            label=f"the total weight stays within {capacity}")
    csp = CSP(vars_, {x: [1, 0] for x in vars_}, [capacity_ok])

    def cost(sol):
        return -sum(v[x] for x, t in sol.items() if t)

    def bound(partial):
        value = sum(v[x] for x, t in partial.items() if t)
        room = capacity - sum(w[x] for x, t in partial.items() if t)
        for x in vars_:
            if x in partial or room <= 0:
                continue
            take = min(1.0, room / w[x])
            value += take * v[x]
            room -= take * w[x]
        return -value

    r = branch_and_bound(csp, cost, bound, select_var=first_unassigned)
    chosen = sorted(x[1] for x, t in r["solution"].items() if t) if r["solution"] else []

    greedy, room = [], capacity
    for i in order:
        if items[i]["weight"] <= room:
            greedy.append(i)
            room -= items[i]["weight"]
    return {"chosen": chosen, "value": -r["cost"] if r["cost"] is not None else 0,
            "weight": sum(items[i]["weight"] for i in chosen), "optimal": r["optimal"],
            "improvements": [{"value": -x["cost"], "nodes": x["nodes"]} for x in r["improvements"]],
            "metrics": r["metrics"], "census_csp": csp,
            "greedy": {"chosen": sorted(greedy), "value": sum(items[i]["value"] for i in greedy)}}


# ========================================================== exam timetables ====

def random_enrollments(students: int, exams: int, per_student: int, rng: random.Random) -> dict:
    subjects = ["AI", "DBMS", "OS", "Networks", "Compilers", "Maths", "Physics", "Graphics", "Security",
                "ML", "Cloud", "IoT", "Robotics", "Economics", "Statistics", "Ethics"][:exams]
    names = ["Aarav", "Diya", "Kabir", "Meera", "Rohan", "Ishaan", "Ananya", "Vihaan", "Saanvi", "Arjun",
             "Kiara", "Reyansh", "Myra", "Aditya", "Tara", "Neel", "Zoya", "Dev", "Riya", "Kavya"]
    return {(names[i] if i < len(names) else f"Student {i + 1}"):
            rng.sample(subjects, min(per_student, len(subjects))) for i in range(students)}


def min_slots(adjacency: dict, max_k: int = 12):
    """Smallest number of slots (colours) that works: try k = 1, 2, ..."""
    from ..core.backtracking import backtracking_search
    from ..core.inference import mac
    from ..core.heuristics import mrv_degree
    attempts = []
    for k in range(1, max_k + 1):
        csp = graph_colouring_csp(adjacency, list(range(1, k + 1)))
        sol, m = backtracking_search(csp, select_var=mrv_degree, inference=mac, max_nodes=200_000)
        attempts.append({"slots": k, "found": sol is not None, "nodes": m.nodes})
        if sol:
            return k, sol, attempts
    return None, None, attempts
