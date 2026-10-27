"""Flask demo server — the ONLY new code here is plumbing (HTTP in, JSON
out). Every /api/solve/* route does the same three things: build a CSP with
an adapter from `problems/`, call `backtracking_search` (or `min_conflicts`)
from `core/`, and serialize the result. No route contains search logic, and
no route is a special case the solver itself knows about — swap the adapter
and the handler is otherwise identical, which is the whole point of this
project made concrete.

Run:  python -m csp_engine.web.app        (then open http://127.0.0.1:5000)
"""
from __future__ import annotations
import json
import os
from flask import Flask, jsonify, request, render_template
from flask_cors import CORS

from ..core.backtracking import (backtracking_search, first_unassigned, domain_order,
                                 no_inference)
from ..core.inference import forward_checking, mac, mac_plus
from ..core.heuristics import mrv, mrv_degree, lcv
from ..core.local_search import min_conflicts
from ..problems import nqueens, graph_colouring, sudoku, cryptarithmetic, zebra, exam_scheduling
from .custom_csp import build_custom_csp, CustomCSPError
from .studio import bp as studio_bp
from .problems_api import bp as problems_bp
from .catalog import P as CATALOG, CATEGORIES, BY_ID

app = Flask(__name__)
CORS(app)
app.register_blueprint(studio_bp)
app.register_blueprint(problems_bp)

MAX_NODES = 150_000   # a live HTTP request should never hang the server

ALGORITHMS = {
    "naive":   ("Naive backtracking",           first_unassigned, domain_order, no_inference),
    "fc":      ("+ Forward checking",            first_unassigned, domain_order, forward_checking),
    "mac":     ("+ Arc consistency (MAC)",        first_unassigned, domain_order, mac),
    "mac_mrv": ("+ MAC + MRV",                    mrv,               domain_order, mac),
    "full":    ("+ MAC + MRV + Degree + LCV",     mrv_degree,        lcv,          mac),
    "smart":   ("+ MAC + MRV + pigeonhole groups", mrv,              domain_order, mac_plus),
}
DEFAULT_ALGO = "full"


def solve(csp, algorithm: str, max_nodes: int = MAX_NODES):
    label, select_var, order_values, inference = ALGORITHMS.get(algorithm, ALGORITHMS[DEFAULT_ALGO])
    solution, metrics = backtracking_search(
        csp, select_var=select_var, order_values=order_values,
        inference=inference, max_nodes=max_nodes,
    )
    return solution, {
        "algorithm": label,
        "solved": metrics.solved,
        "timed_out": metrics.timed_out,
        "nodes": metrics.nodes,
        "backtracks": metrics.backtracks,
        "pruned": metrics.pruned,
        "elapsed_ms": round(metrics.elapsed * 1000, 2),
    }


def error(message: str, status: int = 400):
    return jsonify({"error": message}), status


# ---- pages ---------------------------------------------------------------

@app.route("/")
def home():
    return render_template("home.html", categories=CATEGORIES, problems=CATALOG)


@app.route("/engine")
def index():
    return render_template("index.html", algorithms=ALGORITHMS)


@app.route("/p/<pid>")
def problem_page(pid):
    meta = BY_ID.get(pid)
    if meta is None:
        return render_template("home.html", categories=CATEGORIES, problems=CATALOG), 404
    cat = next(c for c in CATEGORIES if c[0] == meta["category"])
    return render_template("problem.html", meta=meta, category=cat)


@app.route("/studio")
def studio():
    return render_template("studio.html")


# ---- N-Queens -------------------------------------------------------------

@app.route("/api/solve/nqueens", methods=["POST"])
def api_nqueens():
    body = request.get_json(force=True) or {}
    n = int(body.get("n", 8))
    if not (1 <= n <= 60):
        return error("n must be between 1 and 60")
    algorithm = body.get("algorithm", DEFAULT_ALGO)

    if algorithm == "min_conflicts":
        csp = nqueens.nqueens_csp(n)
        solution, metrics = min_conflicts(csp, max_steps=50_000)
        meta = {
            "algorithm": "Min-conflicts (local search)",
            "solved": metrics.solved, "timed_out": not metrics.solved,
            "nodes": metrics.nodes, "backtracks": 0, "pruned": 0,
            "elapsed_ms": round(metrics.elapsed * 1000, 2),
        }
    else:
        csp = nqueens.nqueens_csp(n)
        solution, meta = solve(csp, algorithm)

    queens = [solution[c] for c in range(n)] if solution else None
    return jsonify({"n": n, "queens": queens, "metrics": meta})


# ---- Graph / map colouring -------------------------------------------------

@app.route("/api/solve/graph-colouring", methods=["POST"])
def api_graph_colouring():
    body = request.get_json(force=True) or {}
    adjacency = body.get("adjacency") or graph_colouring.AUSTRALIA
    colours = body.get("colours") or ["red", "green", "blue"]
    algorithm = body.get("algorithm", DEFAULT_ALGO)

    if not adjacency:
        return error("adjacency must be a non-empty {node: [neighbours]} map")

    csp = graph_colouring.graph_colouring_csp(adjacency, colours)
    solution, meta = solve(csp, algorithm)

    return jsonify({
        "adjacency": adjacency, "colours": colours,
        "assignment": solution, "metrics": meta,
    })


# ---- Sudoku -----------------------------------------------------------------

@app.route("/api/solve/sudoku", methods=["POST"])
def api_sudoku():
    body = request.get_json(force=True) or {}
    grid = body.get("grid") or sudoku.EASY_9x9
    algorithm = body.get("algorithm", DEFAULT_ALGO)
    size = len(grid)
    box = int(size ** 0.5)
    if box * box != size:
        return error("grid size must be a perfect square (e.g. 9x9)")

    csp = sudoku.sudoku_csp(grid, box, box)
    solution, meta = solve(csp, algorithm)

    solved_grid = None
    if solution:
        solved_grid = [[solution[(r, c)] for c in range(size)] for r in range(size)]

    return jsonify({"grid": solved_grid, "metrics": meta})


# ---- Cryptarithmetic --------------------------------------------------------

@app.route("/api/solve/cryptarithmetic", methods=["POST"])
def api_cryptarithmetic():
    body = request.get_json(force=True) or {}
    a1 = (body.get("addend1") or "SEND").upper()
    a2 = (body.get("addend2") or "MORE").upper()
    res = (body.get("result") or "MONEY").upper()
    algorithm = body.get("algorithm", DEFAULT_ALGO)

    try:
        csp = cryptarithmetic.cryptarithmetic_csp(a1, a2, res)
    except ValueError as e:
        return error(str(e))

    solution, meta = solve(csp, algorithm, max_nodes=300_000)
    letters = None
    equation = None
    if solution:
        letters = {L: solution[L] for L in sorted(set(a1 + a2 + res))}
        equation = (f"{''.join(str(letters[c]) for c in a1)} + "
                   f"{''.join(str(letters[c]) for c in a2)} = "
                   f"{''.join(str(letters[c]) for c in res)}")

    return jsonify({"addend1": a1, "addend2": a2, "result": res,
                    "letters": letters, "equation": equation, "metrics": meta})


# ---- Zebra puzzle ------------------------------------------------------------

@app.route("/api/solve/zebra", methods=["POST"])
def api_zebra():
    body = request.get_json(force=True) or {}
    algorithm = body.get("algorithm", DEFAULT_ALGO)

    csp = zebra.zebra_csp()
    solution, meta = solve(csp, algorithm)

    houses = None
    if solution:
        by_house = {h: {} for h in zebra.HOUSES}
        for (cat, val), house in solution.items():
            by_house[house][cat] = val
        houses = [by_house[h] for h in zebra.HOUSES]

    return jsonify({"houses": houses, "metrics": meta})


# ---- Exam scheduling (reduction to graph colouring) --------------------------

@app.route("/api/solve/exam-scheduling", methods=["POST"])
def api_exam_scheduling():
    body = request.get_json(force=True) or {}
    enrollments = body.get("enrollments") or exam_scheduling.SAMPLE_ENROLLMENTS
    num_slots = int(body.get("num_slots", 4))
    algorithm = body.get("algorithm", DEFAULT_ALGO)

    adjacency = exam_scheduling.conflict_graph(enrollments)
    csp = exam_scheduling.exam_scheduling_csp(enrollments, num_slots)
    solution, meta = solve(csp, algorithm)

    return jsonify({
        "adjacency": adjacency, "num_slots": num_slots,
        "assignment": solution, "metrics": meta,
    })


# ---- Custom CSP playground ----------------------------------------------------

@app.route("/api/solve/custom", methods=["POST"])
def api_custom():
    body = request.get_json(force=True) or {}
    try:
        csp = build_custom_csp(body)
    except CustomCSPError as e:
        return error(str(e))

    algorithm = body.get("algorithm", DEFAULT_ALGO)
    solution, meta = solve(csp, algorithm, max_nodes=100_000)

    assignment = {str(k): v for k, v in solution.items()} if solution else None
    return jsonify({"assignment": assignment, "metrics": meta})


# ---- Benchmark / instrumentation study ----------------------------------------

@app.route("/api/benchmark")
def api_benchmark():
    path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "..", "benchmark_results.json")
    path = os.path.abspath(path)
    if not os.path.exists(path):
        from .. import benchmark as bench
        rows = bench.run()
        with open(path, "w") as f:
            json.dump(rows, f)
    else:
        with open(path) as f:
            rows = json.load(f)
    return jsonify(rows)


if __name__ == "__main__":
    app.run(debug=True, port=int(os.environ.get("PORT", 5000)))
