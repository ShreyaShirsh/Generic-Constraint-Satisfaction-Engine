"""Minesweeper's hidden information -> CSP.

  variables   = every covered cell that touches a revealed number
  domains     = {0 = safe, 1 = mine}
  constraints = one Predicate per revealed number N:
                    "the covered cells around me hold exactly N mines"

From that CSP the assistant gets three things, all from the generic engine:
  * certain moves -- the human-style reasoner finds cells that are safe (or
    mines) in every consistent arrangement, with the number that proves it;
  * exact probabilities -- the solver enumerates every arrangement of each
    independent group of cells, weighted by how many ways the remaining
    mines can sit in the untouched cells;
  * an autoplayer -- reveal what's certain, otherwise the least risky cell.

The game mechanics (placing mines, flood-revealing zeros) live here too, but
they are the world, not the reasoning.
"""
from __future__ import annotations
import random
from math import comb
from ..core.model import CSP
from ..core.constraints import Predicate
from ..core.backtracking import find_all_solutions
from ..core.inference import forward_checking
from ..core.heuristics import mrv
from ..core.explain import Reasoner


def neighbours(r, c, rows, cols):
    for dr in (-1, 0, 1):
        for dc in (-1, 0, 1):
            if (dr or dc) and 0 <= r + dr < rows and 0 <= c + dc < cols:
                yield (r + dr, c + dc)


def cell_name(cell) -> str:
    return f"R{cell[0] + 1}C{cell[1] + 1}"


# ---- the world -------------------------------------------------------------

def new_board(rows: int, cols: int, mines: int, first: tuple, rng: random.Random) -> list:
    safe = {first, *neighbours(*first, rows, cols)}
    cells = [(r, c) for r in range(rows) for c in range(cols) if (r, c) not in safe]
    if mines > len(cells):
        raise ValueError("too many mines for this board")
    return sorted(rng.sample(cells, mines))


def count_at(cell, mines: set, rows, cols) -> int:
    return sum(1 for n in neighbours(*cell, rows, cols) if n in mines)


def reveal(cell, mines: set, revealed: dict, rows, cols) -> bool:
    """Flood-reveal from cell; returns False if it was a mine."""
    if cell in mines:
        return False
    stack = [cell]
    while stack:
        cur = stack.pop()
        if cur in revealed:
            continue
        n = count_at(cur, mines, rows, cols)
        revealed[cur] = n
        if n == 0:
            stack.extend(x for x in neighbours(*cur, rows, cols) if x not in revealed)
    return True


# ---- the reasoning -----------------------------------------------------------

def _sum_fn(target: int, size: int):
    def fn(local):
        s = sum(local.values())
        return s <= target <= s + (size - len(local))
    return fn


def mines_csp(revealed: dict, rows: int, cols: int) -> CSP:
    frontier, constraints = [], []
    seen = set()
    for cell, n in sorted(revealed.items()):
        covered = [x for x in neighbours(*cell, rows, cols) if x not in revealed]
        if not covered:
            continue
        for x in covered:
            if x not in seen:
                seen.add(x)
                frontier.append(x)
        constraints.append(Predicate(covered, _sum_fn(n, len(covered)), name="MineCount",
                                     check_when_partial=True,
                                     label=f"the {n} at {cell_name(cell)}"))
    return CSP(frontier, {x: [0, 1] for x in frontier}, constraints)


def _components(csp: CSP) -> list[list]:
    left, out = set(csp.variables), []
    while left:
        start = left.pop()
        comp, stack = [start], [start]
        while stack:
            v = stack.pop()
            for n in csp.neighbors(v):
                if n in left:
                    left.discard(n)
                    comp.append(n)
                    stack.append(n)
        out.append(comp)
    return out


def analyse(revealed: dict, rows: int, cols: int, total_mines: int,
            max_solutions: int = 20_000) -> dict:
    """Exact mine probability for every covered cell (None if a group of
    cells has too many arrangements to enumerate quickly)."""
    csp = mines_csp(revealed, rows, cols)
    covered = [(r, c) for r in range(rows) for c in range(cols) if (r, c) not in revealed]
    interior = [x for x in covered if x not in set(csp.variables)]

    # per independent group: {mines in group: [arrangements, {cell: times it's a mine}]}
    groups = []
    for comp in _components(csp):
        sub = CSP(comp, {v: [0, 1] for v in comp},
                  [c for c in csp.constraints if c.variables[0] in comp])
        stats: dict = {}

        def record(sol, stats=stats):
            k = sum(sol.values())
            entry = stats.setdefault(k, [0, {}])
            entry[0] += 1
            for v, x in sol.items():
                if x:
                    entry[1][v] = entry[1].get(v, 0) + 1
            return sum(e[0] for e in stats.values()) >= max_solutions

        _, m = find_all_solutions(sub, select_var=mrv, inference=forward_checking,
                                  on_solution=record, max_nodes=400_000)
        if m.timed_out or sum(e[0] for e in stats.values()) >= max_solutions:
            return {"probabilities": None, "frontier": len(csp.variables)}
        groups.append(stats)

    # combine groups: distribution of total frontier mines -> weight
    dist = {0: 1}
    for stats in groups:
        nxt: dict = {}
        for t, w in dist.items():
            for k, (n, _) in stats.items():
                nxt[t + k] = nxt.get(t + k, 0) + w * n
        dist = nxt

    def ways_outside(frontier_mines):
        rest = total_mines - frontier_mines
        return comb(len(interior), rest) if 0 <= rest <= len(interior) else 0

    total = sum(w * ways_outside(t) for t, w in dist.items())
    if total == 0:
        return {"probabilities": None, "frontier": len(csp.variables), "inconsistent": True}

    prob: dict = {}
    for gi, stats in enumerate(groups):
        others = {0: 1}
        for gj, st in enumerate(groups):
            if gj == gi:
                continue
            nxt: dict = {}
            for t, w in others.items():
                for k, (n, _) in st.items():
                    nxt[t + k] = nxt.get(t + k, 0) + w * n
            others = nxt
        for k, (n, per_cell) in stats.items():
            weight = sum(w * ways_outside(k + t) for t, w in others.items())
            for v, times in per_cell.items():
                prob[v] = prob.get(v, 0) + times * weight
    probabilities = {}
    for v in csp.variables:
        probabilities[v] = prob.get(v, 0) / total
    if interior:
        expected_frontier = sum(t * w * ways_outside(t) for t, w in dist.items()) / total
        p_in = (total_mines - expected_frontier) / len(interior)
        for v in interior:
            probabilities[v] = p_in
    return {"probabilities": probabilities, "frontier": len(csp.variables)}


def next_move(revealed: dict, rows: int, cols: int, total_mines: int,
              flags=()) -> dict:
    """The assistant's advice: a certain move with its reason if one exists,
    otherwise the least risky cell according to the exact probabilities.
    `flags` are cells already proved to be mines."""
    flags = {tuple(f) for f in flags}
    csp = mines_csp(revealed, rows, cols)
    known = {v: 1 for v in csp.variables if v in flags}
    if len(known) < len(csp.variables):
        step = Reasoner(csp, known, cell_name).next_step(3)
        if step is not None and step.kind != "contradiction":
            mine = step.value == 1
            reason = step.text.split("Everything else is ruled out: ", 1)[-1].rstrip(".")
            reason = reason.replace("1 would break", "a mine would break")                            .replace("0 would break", "a safe cell would break")                            .replace("1 can't work", "a mine can't work")                            .replace("0 can't work", "a safe cell can't work")
            if step.kind == "hidden":
                reason = step.text
            return {"kind": "certain", "cell": list(step.var), "mine": mine,
                    "text": f"{cell_name(step.var)} is {'a MINE' if mine else 'SAFE'} — {reason}.",
                    "highlight": [list(x) for x in step.highlight]}
    covered = [(r, c) for r in range(rows) for c in range(cols)
               if (r, c) not in revealed and (r, c) not in flags]
    if not covered:
        return {"kind": "done", "text": "Nothing left to reveal."}
    probs = analyse(revealed, rows, cols, total_mines).get("probabilities")
    if probs:
        options = {v: p for v, p in probs.items() if v not in flags}
        best = min(options, key=options.get)
        if options[best] < 1e-12:
            return {"kind": "certain", "cell": list(best), "mine": False, "probabilities": _jsonp(probs),
                    "text": f"{cell_name(best)} is SAFE: it holds no mine in any arrangement "
                            f"consistent with every number on the board."}
        return {"kind": "guess", "cell": list(best), "mine": False, "probabilities": _jsonp(probs),
                "text": f"No cell is certain — logic alone can't decide. Counting every consistent "
                        f"arrangement of mines, the least risky cell is {cell_name(best)} "
                        f"({options[best] * 100:.0f}% chance of a mine)."}
    v = covered[len(covered) // 2]
    return {"kind": "guess", "cell": list(v), "mine": False,
            "text": "Too many arrangements to count exactly here; taking an educated guess."}


def _jsonp(probs: dict) -> dict:
    return {f"{r},{c}": round(p, 4) for (r, c), p in probs.items()}


def autoplay(rows: int, cols: int, mines: int, seed: int | None = None) -> dict:
    """Let the assistant play a whole game. Returns the move list for replay."""
    rng = random.Random(seed)
    first = (rows // 2, cols // 2)
    layout = set(new_board(rows, cols, mines, first, rng))
    revealed: dict = {}
    reveal(first, layout, revealed, rows, cols)
    moves = [{"cell": list(first), "kind": "start"}]
    flags: set = set()
    lost = False
    for _ in range(rows * cols * 2):
        if len(revealed) == rows * cols - mines:
            break
        advice = next_move(revealed, rows, cols, mines, flags)
        if advice["kind"] == "done":
            break
        cell = tuple(advice["cell"])
        if advice.get("mine"):
            flags.add(cell)
            moves.append({"cell": list(cell), "kind": "flag", "reason": advice["text"]})
            continue
        ok = reveal(cell, layout, revealed, rows, cols)
        moves.append({"cell": list(cell), "kind": "reveal" if advice["kind"] == "certain" else "guess",
                      "reason": advice["text"], "boom": not ok})
        if not ok:
            lost = True
            break
    won = not lost and len(revealed) == rows * cols - mines
    return {"rows": rows, "cols": cols, "mines": sorted(map(list, layout)), "moves": moves, "won": won}
