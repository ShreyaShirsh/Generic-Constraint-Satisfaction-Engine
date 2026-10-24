"""Adapter: N-Queens -> CSP. Universal: works for any board size n.

Encoding (the standard one-queen-per-column trick):
  variables   = the columns 0 .. n-1
  domains      = the row (0 .. n-1) that column's queen sits on
  constraints = for every pair of columns, their queens must not share a
                row and must not share a diagonal

Placing exactly one queen per column makes "two queens in one column"
impossible by construction, so we only need row + diagonal safety.
"""
from __future__ import annotations
from ..core.model import CSP
from ..core.constraints import BinaryRelation


def _safe(row_i: int, row_j: int, col_gap: int) -> bool:
    """Two queens `col_gap` columns apart, on rows row_i / row_j: safe?"""
    return row_i != row_j and abs(row_i - row_j) != col_gap


def nqueens_csp(n: int) -> CSP:
    if n < 1:
        raise ValueError("n must be >= 1")

    variables = list(range(n))                        # one variable per column
    domains = {c: set(range(n)) for c in variables}   # candidate rows

    constraints = []
    for i in range(n):
        for j in range(i + 1, n):
            gap = j - i
            constraints.append(
                BinaryRelation(i, j,
                               lambda ri, rj, gap=gap: _safe(ri, rj, gap),
                               name="QueensSafe")
            )
    return CSP(variables, domains, constraints)


def board_str(solution: dict, n: int) -> str:
    """Minimal ASCII board. Real visuals live in the viz/ layer later."""
    rows = []
    for row in range(n):
        rows.append(" ".join("Q" if solution.get(col) == row else "."
                             for col in range(n)))
    return "\n".join(rows)


if __name__ == "__main__":      # self-test (fixed inputs, because a test needs a known answer)
    from ..core.backtracking import backtracking_search, find_all_solutions
    assert backtracking_search(nqueens_csp(8))[0] is not None
    assert len(find_all_solutions(nqueens_csp(4))[0]) == 2
    assert len(find_all_solutions(nqueens_csp(6))[0]) == 4
    assert len(find_all_solutions(nqueens_csp(8))[0]) == 92
    print("nqueens self-test passed  (4->2, 6->4, 8->92 solutions).")
