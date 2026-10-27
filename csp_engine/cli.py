"""Interactive front-end -- the I/O layer.

Reads a problem from the user at runtime, builds a CSP through an adapter,
runs the solver, and prints results. There is NO fixed problem here and NO
solving logic -- every input (which pattern, the algorithm, the board size,
the graph, the grid) comes from the user. For a visual version of the same
engine, see `python -m csp_engine.web.app`.

Run:  python -m csp_engine.cli
"""
from __future__ import annotations
from .core.backtracking import (backtracking_search, find_all_solutions,
                                first_unassigned, domain_order, no_inference)
from .core.inference import forward_checking, mac, mac_plus
from .core.heuristics import mrv, mrv_degree, lcv
from .core.local_search import min_conflicts
from .problems import nqueens, graph_colouring, sudoku, cryptarithmetic, zebra, exam_scheduling

ALGORITHMS = {
    "1": ("Naive backtracking",          first_unassigned, domain_order, no_inference),
    "2": ("+ Forward checking",           first_unassigned, domain_order, forward_checking),
    "3": ("+ Arc consistency (MAC)",      first_unassigned, domain_order, mac),
    "4": ("+ MAC + MRV",                  mrv,               domain_order, mac),
    "5": ("+ MAC + MRV + degree + LCV",   mrv_degree,        lcv,          mac),
    "6": ("+ MAC + MRV + pigeonhole",     mrv,               domain_order, mac_plus),
}


def _ask_int(prompt: str, lo: int | None = None, hi: int | None = None) -> int:
    while True:
        try:
            val = int(input(prompt).strip())
        except ValueError:
            print("  Please enter a whole number.")
            continue
        if lo is not None and val < lo:
            print(f"  Must be >= {lo}."); continue
        if hi is not None and val > hi:
            print(f"  Must be <= {hi}."); continue
        return val


def _pick_algorithm():
    print("Algorithm:")
    for key, (label, *_rest) in ALGORITHMS.items():
        print(f"  {key}) {label}")
    choice = input("Choose [1-6, default 5]: ").strip() or "5"
    return ALGORITHMS.get(choice, ALGORITHMS["5"])


def _run(csp, build_note: str = ""):
    label, select_var, order_values, inference = _pick_algorithm()
    solution, metrics = backtracking_search(
        csp, select_var=select_var, order_values=order_values, inference=inference,
    )
    print(f"\n[{label}]  {metrics.summary()}")
    return solution


def solve_nqueens() -> None:
    n = _ask_int("Board size n: ", lo=1)
    mode = input("Find (f)irst solution, (a)ll solutions, or (m)in-conflicts? [f/a/m]: ").strip().lower()
    csp = nqueens.nqueens_csp(n)

    if mode == "a":
        if n >= 11:
            print(f"  Note: solution counts explode with size; n={n} may take a while.")
        label, select_var, order_values, inference = _pick_algorithm()
        solutions, metrics = find_all_solutions(csp, select_var=select_var,
                                                order_values=order_values, inference=inference)
        print(f"\n{n}-Queens has {len(solutions)} distinct solution(s).")
        print(metrics.summary())
        if solutions:
            k = _ask_int(f"Print how many boards? (0-{len(solutions)}): ", lo=0, hi=len(solutions))
            for idx in range(k):
                print(f"\nSolution {idx + 1}:")
                print(nqueens.board_str(solutions[idx], n))
    elif mode == "m":
        solution, metrics = min_conflicts(csp, max_steps=50_000)
        print(f"\n[Min-conflicts]  solved={metrics.solved}  steps={metrics.nodes}  time={metrics.elapsed*1000:.2f} ms")
        if solution:
            print(nqueens.board_str(solution, n))
    else:
        solution = _run(csp)
        if solution:
            print(nqueens.board_str(solution, n))
            print("valid?", csp.is_solution(solution))
        else:
            print("No solution exists for this board size.")


def solve_colouring() -> None:
    print("Define the graph:")
    print("  1) use the Australia preset")
    print("  2) enter your own graph")
    choice = input("Choose [1/2]: ").strip()

    if choice == "1":
        adjacency = graph_colouring.AUSTRALIA
    else:
        print("Enter edges as space-separated pairs, e.g.:  A-B A-C B-C")
        adjacency: dict[str, list[str]] = {}
        for tok in input("Edges: ").strip().split():
            if "-" not in tok:
                print(f"  Skipping '{tok}' (use the form X-Y)."); continue
            u, v = tok.split("-", 1)
            adjacency.setdefault(u, []).append(v)
            adjacency.setdefault(v, []).append(u)
        if not adjacency:
            print("  No valid edges entered."); return

    colours = input("Colours (space-separated), e.g. red green blue: ").strip().split()
    if not colours:
        print("  No colours entered."); return

    csp = graph_colouring.graph_colouring_csp(adjacency, colours)
    solution = _run(csp)
    if solution:
        for v in csp.variables:
            print(f"  {v} = {solution[v]}")
        print("valid?", csp.is_solution(solution))
    else:
        print(f"No colouring exists with {len(colours)} colour(s).")


def solve_sudoku() -> None:
    print("1) solve the built-in easy 9x9 preset")
    print("2) enter a custom 9x9 grid (9 rows, digits with 0 for blank, space separated)")
    choice = input("Choose [1/2]: ").strip()

    if choice == "2":
        grid = []
        print("Enter 9 rows:")
        for r in range(9):
            row = [int(x) for x in input(f"  row {r+1}: ").strip().split()]
            if len(row) != 9:
                print("  Need exactly 9 numbers; aborting."); return
            grid.append(row)
    else:
        grid = sudoku.EASY_9x9

    csp = sudoku.sudoku_csp(grid, 3, 3)
    solution = _run(csp)
    if solution:
        print(sudoku.grid_str(solution, 9))
    else:
        print("No solution for this grid.")


def solve_cryptarithmetic() -> None:
    a1 = input("Addend 1 (e.g. SEND): ").strip().upper()
    a2 = input("Addend 2 (e.g. MORE): ").strip().upper()
    res = input("Result   (e.g. MONEY): ").strip().upper()
    try:
        csp = cryptarithmetic.cryptarithmetic_csp(a1, a2, res)
    except ValueError as e:
        print(f"  {e}"); return

    solution = _run(csp)
    if solution:
        print(cryptarithmetic.solution_str(solution, a1, a2, res))
    else:
        print("No solution exists for this puzzle.")


def solve_zebra() -> None:
    csp = zebra.zebra_csp()
    solution = _run(csp)
    if solution:
        print(zebra.describe(solution))
        print("\nThe zebra owner is:", zebra.who_owns_zebra(solution))
    else:
        print("No solution (shouldn't happen -- the clues are consistent).")


def solve_exam_scheduling() -> None:
    print("1) use the sample enrollment preset")
    print("2) enter your own (one student per line: Name: Exam1, Exam2, ...; blank line to stop)")
    choice = input("Choose [1/2]: ").strip()

    if choice == "2":
        enrollments: dict[str, list[str]] = {}
        print("Enter enrollments, blank line to finish:")
        while True:
            line = input("  ").strip()
            if not line:
                break
            if ":" not in line:
                print("  Use the form Name: Exam1, Exam2"); continue
            name, rest = line.split(":", 1)
            enrollments[name.strip()] = [e.strip() for e in rest.split(",") if e.strip()]
        if not enrollments:
            print("  No enrollments entered."); return
    else:
        enrollments = exam_scheduling.SAMPLE_ENROLLMENTS

    num_slots = _ask_int("Number of time slots: ", lo=1)
    csp = exam_scheduling.exam_scheduling_csp(enrollments, num_slots)
    solution = _run(csp)
    if solution:
        print(exam_scheduling.timetable_str(solution))
    else:
        print(f"No feasible timetable with {num_slots} slot(s).")


PATTERNS = {
    "1": ("N-Queens", solve_nqueens),
    "2": ("Graph / map colouring", solve_colouring),
    "3": ("Sudoku", solve_sudoku),
    "4": ("Cryptarithmetic", solve_cryptarithmetic),
    "5": ("Zebra / Einstein logic puzzle", solve_zebra),
    "6": ("Exam scheduling (reduces to graph colouring)", solve_exam_scheduling),
}


def main() -> None:
    print("=== CSP Engine ===")
    print("One solver, many problems. Patterns:")
    for key, (name, _) in PATTERNS.items():
        print(f"  {key}) {name}")
    choice = input("Choose a pattern: ").strip()
    entry = PATTERNS.get(choice)
    if entry is None:
        print("Unknown choice."); return
    print()
    entry[1]()


if __name__ == "__main__":
    main()
