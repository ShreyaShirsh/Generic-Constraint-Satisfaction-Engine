"""Puzzle Studio API. Same rule as app.py: plumbing only. Every route turns
a grid-puzzle spec into a CSP with problems/grid_puzzle.py and hands it to
core/ -- the search (with a tracer for the replay), the human-style
reasoner (hints, pencil marks, grading) or the generic generator.
"""
from __future__ import annotations
import random
from flask import Blueprint, jsonify, request

from ..core.backtracking import (backtracking_search, first_unassigned, domain_order,
                                 no_inference, SearchAborted)
from ..core.inference import forward_checking, mac, mac_plus
from ..core.heuristics import mrv, mrv_degree, lcv
from ..core.explain import Reasoner, grade, LEVEL_NAMES
from ..core.generator import generate, count_solutions
from ..problems import nqueens
from ..problems.grid_puzzle import (grid_puzzle_csp, cell_name, givens_of, with_givens,
                                    generate_puzzle, validate)
from ..problems import puzzle_presets

bp = Blueprint("studio", __name__, url_prefix="/api/studio")

ALGORITHMS = {
    "naive":   ("Naive backtracking",            first_unassigned, domain_order, no_inference),
    "fc":      ("Forward checking",               first_unassigned, domain_order, forward_checking),
    "mac":     ("Arc consistency (MAC)",          first_unassigned, domain_order, mac),
    "mac_mrv": ("MAC + MRV",                      mrv,               domain_order, mac),
    "full":    ("MAC + MRV + degree + LCV",       mrv_degree,        lcv,          mac),
    "smart":   ("MAC + MRV + pigeonhole groups",  mrv,               domain_order, mac_plus),
}
TRACE_LIMIT = 40_000          # events sent to the browser for one replay
SOLVE_BUDGET = 200_000


class BadRequest(ValueError):
    pass


@bp.errorhandler(BadRequest)
@bp.errorhandler(ValueError)
def _bad_request(e):
    return jsonify({"error": str(e)}), 400


def _body() -> dict:
    return request.get_json(force=True) or {}


def _spec(body: dict) -> dict:
    spec = body.get("spec")
    if not isinstance(spec, dict):
        raise BadRequest("missing puzzle 'spec'")
    validate(spec)
    return spec


def _entries(body: dict) -> dict:
    return {(int(r), int(c)): int(v) for r, c, v in body.get("entries", [])}


def _key(var) -> str:
    return f"{var[0]},{var[1]}" if isinstance(var, tuple) else str(var)


def _cells(vars_) -> list:
    return [list(v) for v in vars_]


# ---- presets --------------------------------------------------------------

@bp.route("/presets")
def presets():
    return jsonify(puzzle_presets.load())


# ---- watch: a full, replayable trace of the search ---------------------------

@bp.route("/trace", methods=["POST"])
def trace():
    body = _body()
    algo_key = body.get("algorithm", "smart")
    if algo_key not in ALGORITHMS:
        raise BadRequest(f"unknown algorithm '{algo_key}'")
    label, select_var, order_values, inference = ALGORITHMS[algo_key]

    puzzle = body.get("puzzle") or {}
    if puzzle.get("kind") == "nqueens":
        n = int(puzzle.get("n", 8))
        if not 4 <= n <= 16:
            raise BadRequest("n must be between 4 and 16")
        csp = nqueens.nqueens_csp(n)
    else:
        csp = grid_puzzle_csp(_spec(puzzle))

    index = {v: i for i, v in enumerate(csp.variables)}
    initial = {_key(v): sorted(csp.domains[v]) for v in csp.variables}
    codes = {"assign": "a", "prune": "p", "restore": "r", "unassign": "u", "solution": "s"}
    events: list = []

    def tracer(event, var, value):
        if len(events) >= TRACE_LIMIT:
            raise SearchAborted()
        events.append([codes[event], index.get(var, -1), value])

    solution, metrics = backtracking_search(csp, select_var=select_var, order_values=order_values,
                                            inference=inference, tracer=tracer,
                                            max_nodes=SOLVE_BUDGET)
    return jsonify({
        "algorithm": label,
        "vars": [_key(v) for v in csp.variables],
        "initial": initial,
        "events": events,
        "truncated": metrics.timed_out,
        "metrics": {"solved": metrics.solved, "nodes": metrics.nodes,
                    "backtracks": metrics.backtracks, "pruned": metrics.pruned,
                    "elapsed_ms": round(metrics.elapsed * 1000, 2)},
    })


# ---- play: live rule checking, hints, pencil marks ------------------------------

def _violations(csp, assignment: dict) -> list[dict]:
    out, seen = [], set()
    for c in csp.constraints:
        if c.is_satisfied(assignment):
            continue
        cells = [v for v in c.variables if v in assignment]
        key = (getattr(c, "label", None), frozenset(cells))
        if key in seen:
            continue
        seen.add(key)
        out.append({"cells": _cells(cells), "label": getattr(c, "label", None) or c.name})
    return out


@bp.route("/check", methods=["POST"])
def check():
    body = _body()
    spec = _spec(body)
    csp = grid_puzzle_csp(spec)
    assignment = {**givens_of(spec), **_entries(body)}
    violations = _violations(csp, assignment)
    complete = len(assignment) == len(csp.variables)
    return jsonify({"conflicts": violations, "complete": complete,
                    "solved": complete and not violations})


def _solve(csp):
    solution, _ = backtracking_search(csp, select_var=mrv, inference=mac_plus,
                                      max_nodes=SOLVE_BUDGET)
    return dict(solution) if solution else None


@bp.route("/hint", methods=["POST"])
def hint():
    body = _body()
    spec = _spec(body)
    givens, entries = givens_of(spec), _entries(body)
    assignment = {**givens, **entries}
    rules = grid_puzzle_csp(spec, include_givens=False)

    violations = _violations(rules, assignment)
    if violations:
        v = violations[0]
        return jsonify({"kind": "conflict", "cells": v["cells"], "highlight": v["cells"],
                        "text": f"Something on the board already breaks {v['label']}. "
                                f"Fix that first — the highlighted cells clash."})

    solution = _solve(grid_puzzle_csp(spec))
    if solution is None:
        return jsonify({"kind": "unsolvable", "text": "This puzzle has no solution at all."})

    unique = count_solutions(grid_puzzle_csp(spec), budget=50_000) == 1
    if unique:
        wrong = [cell for cell, v in entries.items() if solution[cell] != v]
    else:
        trial = grid_puzzle_csp(spec)
        trial.reset_domains({v: ({assignment[v]} if v in assignment else trial.domains[v].values)
                             for v in trial.variables})
        wrong = [] if _solve(trial) else list(entries)
    if wrong:
        names = ", ".join(cell_name(c) for c in wrong[:4])
        return jsonify({"kind": "mistake", "cells": _cells(wrong), "highlight": _cells(wrong),
                        "text": f"{names} {'doesn' if len(wrong) == 1 else 'don'}'t fit the "
                                f"puzzle's solution. Nothing clashes yet, but "
                                f"{'it leads' if len(wrong) == 1 else 'they lead'} to a dead end."})

    step = Reasoner(rules, assignment, cell_name).next_step(3)
    if step is not None and step.kind != "contradiction":
        return jsonify({"kind": step.kind, "cell": list(step.var), "value": step.value,
                        "level": step.level, "level_name": LEVEL_NAMES[step.level],
                        "text": step.text, "highlight": _cells(step.highlight)})

    open_cells = [v for v in rules.variables if v not in assignment]
    if not open_cells:
        return jsonify({"kind": "done", "text": "The puzzle is already complete."})
    r = Reasoner(rules, assignment, cell_name)
    cell = min(open_cells, key=lambda v: len(r.cands.get(v, ())))
    return jsonify({"kind": "reveal", "cell": list(cell), "value": solution[cell],
                    "level": 4, "level_name": LEVEL_NAMES[4], "highlight": [],
                    "text": f"No logical step exists from here — this is exactly where the engine "
                            f"itself has to guess. Its search says {cell_name(cell)} is "
                            f"{solution[cell]} (that cell had the fewest options left)."})


@bp.route("/candidates", methods=["POST"])
def candidates():
    body = _body()
    spec = _spec(body)
    rules = grid_puzzle_csp(spec, include_givens=False)
    r = Reasoner(rules, {**givens_of(spec), **_entries(body)})
    if int(body.get("level", 1)) >= 3:
        r._propagate(); r._subsets(); r._intersections()
    return jsonify({"candidates": {_key(v): sorted(cs) for v, cs in r.cands.items()}})


# ---- generate / grade / analyze / make ---------------------------------------------

@bp.route("/generate", methods=["POST"])
def generate_route():
    body = _body()
    kind = body.get("type", "sudoku")
    size = int(body.get("size", 9))
    level = body.get("difficulty")
    level = int(level) if level not in (None, "", "any") else None
    result = generate_puzzle(kind, size, level, time_budget=float(body.get("time_budget", 8)))
    return jsonify({"spec": result["spec"], "grade": result["grade"].as_dict(),
                    "stats": result["stats"]})


def _compiled_summary(csp) -> dict:
    kinds: dict[str, int] = {}
    for c in csp.constraints:
        shape = "BinaryRelation" if hasattr(c, "holds") else "Predicate"
        key = f"{shape} ({c.name})"
        kinds[key] = kinds.get(key, 0) + 1
    return {"variables": len(csp.variables), "constraints": len(csp.constraints),
            "by_type": kinds, "groups": len(csp.groups)}


@bp.route("/analyze", methods=["POST"])
def analyze():
    """Everything the builder wants to know about a rule set + givens."""
    body = _body()
    spec = _spec(body)
    csp = grid_puzzle_csp(spec)
    summary = _compiled_summary(csp)
    count = count_solutions(grid_puzzle_csp(spec), limit=2, budget=SOLVE_BUDGET)
    out = {"compiled": summary, "solutions": count, "solution": None, "grade": None}
    if count:
        sol = _solve(grid_puzzle_csp(spec))
        out["solution"] = [[r, c, v] for (r, c), v in sorted(sol.items())]
    if count == 1:
        out["grade"] = grade(grid_puzzle_csp(spec, include_givens=False), givens_of(spec)).as_dict()
    return jsonify(out)


@bp.route("/make", methods=["POST"])
def make():
    """Turn a user's rule set into a real puzzle: same generator as the
    built-in types. Givens the user placed are kept as fixed."""
    body = _body()
    spec = _spec(body)
    level = body.get("difficulty")
    level = int(level) if level not in (None, "", "any") else None
    csp = grid_puzzle_csp(spec)          # user-placed givens restrict the solution
    if count_solutions(csp, limit=1, budget=SOLVE_BUDGET) == 0:
        raise BadRequest("These rules (with the givens you placed) have no solution — "
                         "nothing to make a puzzle from.")
    result = generate(csp, level, random.Random(), float(body.get("time_budget", 8)))
    merged = {**givens_of(spec), **result["givens"]}
    return jsonify({"spec": with_givens(spec, merged), "grade": result["grade"].as_dict(),
                    "stats": result["stats"]})


@bp.route("/solve", methods=["POST"])
def solve_route():
    body = _body()
    spec = _spec(body)
    sol = _solve(grid_puzzle_csp(spec))
    if sol is None:
        return jsonify({"solution": None})
    return jsonify({"solution": [[r, c, v] for (r, c), v in sorted(sol.items())]})
