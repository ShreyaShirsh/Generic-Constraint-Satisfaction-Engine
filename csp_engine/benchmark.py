"""Instrumentation study: measure how many search steps the SAME solver
needs as backtracking, forward checking, arc consistency and ordering
heuristics are progressively enabled -- the core deliverable the abstract
promises ("quantifies the contribution of each technique").

Every row below runs the identical `backtracking_search` on an identical
CSP; only the plugged-in hooks change. No problem-specific code appears
here at all -- this script only ever imports adapters, never writes a
solver.

Run:  python -m csp_engine.benchmark
"""
from __future__ import annotations
import json
from .core.backtracking import backtracking_search, first_unassigned, domain_order, no_inference
from .core.inference import forward_checking, mac, mac_plus
from .core.heuristics import mrv, mrv_degree, lcv
from .problems import nqueens, graph_colouring, sudoku, cryptarithmetic, exam_scheduling
from .problems import puzzle_presets
from .problems.grid_puzzle import grid_puzzle_csp


def _preset(pid: str):
    spec = next(p["spec"] for p in puzzle_presets.load() if p["id"] == pid)
    return lambda: grid_puzzle_csp(spec)

TECHNIQUES = [
    ("Naive backtracking",            first_unassigned, domain_order, no_inference),
    ("+ Forward checking",            first_unassigned, domain_order, forward_checking),
    ("+ Arc consistency (MAC)",       first_unassigned, domain_order, mac),
    ("+ MAC + MRV",                   mrv,               domain_order, mac),
    ("+ MAC + MRV + degree + LCV",    mrv_degree,        lcv,          mac),
    ("+ MAC + MRV + pigeonhole",      mrv,               domain_order, mac_plus),
]

# (label, csp-builder, max_nodes safety cap -- naive search can run away)
PROBLEMS = [
    ("N-Queens (n=8)",        lambda: nqueens.nqueens_csp(8),                         200_000),
    ("Map colouring (Australia)", lambda: graph_colouring.australia_csp(),            200_000),
    ("Sudoku (easy 9x9)",     lambda: sudoku.sudoku_csp(sudoku.EASY_9x9, 3, 3),        200_000),
    ("Sudoku (expert 9x9)",   _preset("sudoku-expert"),                                200_000),
    ("Killer Sudoku (9x9)",   _preset("killer-9"),                                     200_000),
    ("Exam scheduling (4 slots)", lambda: exam_scheduling.exam_scheduling_csp(
        exam_scheduling.SAMPLE_ENROLLMENTS, 4),                                        200_000),
    ("Cryptarithmetic (SEND+MORE=MONEY)",
        lambda: cryptarithmetic.cryptarithmetic_csp("SEND", "MORE", "MONEY"),         200_000),
]


def run() -> list[dict]:
    rows = []
    for problem_label, build_csp, cap in PROBLEMS:
        for tech_label, select_var, order_values, inference in TECHNIQUES:
            csp = build_csp()
            _, metrics = backtracking_search(
                csp, select_var=select_var, order_values=order_values,
                inference=inference, max_nodes=cap,
            )
            rows.append({
                "problem": problem_label,
                "technique": tech_label,
                "solved": metrics.solved,
                "timed_out": metrics.timed_out,
                "nodes": metrics.nodes,
                "backtracks": metrics.backtracks,
                "pruned": metrics.pruned,
                "elapsed_ms": round(metrics.elapsed * 1000, 2),
            })
    return rows


def print_table(rows: list[dict]) -> None:
    header = f"{'Problem':<36} {'Technique':<28} {'nodes':>8} {'backtracks':>11} {'pruned':>8} {'ms':>9}"
    print(header)
    print("-" * len(header))
    last_problem = None
    for r in rows:
        if r["problem"] != last_problem:
            if last_problem is not None:
                print()
            last_problem = r["problem"]
        status = "" if r["solved"] else ("  [TIMED OUT]" if r["timed_out"] else "  [NO SOLUTION]")
        print(f"{r['problem']:<36} {r['technique']:<28} {r['nodes']:>8} "
              f"{r['backtracks']:>11} {r['pruned']:>8} {r['elapsed_ms']:>9.2f}{status}")


if __name__ == "__main__":
    rows = run()
    print_table(rows)
    with open("benchmark_results.json", "w") as f:
        json.dump(rows, f, indent=2)
    print("\nSaved raw results to benchmark_results.json")
