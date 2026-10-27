"""Adapter: Sudoku -> CSP. Universal: works for any N^2 x N^2 grid (4x4, 9x9,
16x9... any size whose box dimensions you give), not just a single hardcoded
9x9 puzzle.

Encoding:
  variables   = every cell (row, col)
  domains     = 1 .. size, trimmed to a single value for cells given as clues
  constraints = all_different(row), all_different(column), all_different(box)
                — literally the SAME all_different() helper graph colouring
                and N-Queens never needed, because here the "no two things
                the same" idea applies three times per cell instead of once.

This file contains no solving logic — only a description of the grid in the
engine's common (variables, domains, constraints) representation.
"""
from __future__ import annotations
from ..core.model import CSP
from ..core.constraints import all_different

Cell = tuple[int, int]


def sudoku_csp(grid: list[list[int]], box_rows: int, box_cols: int) -> CSP:
    """Build a Sudoku CSP from a partially-filled grid.

    `grid` is size x size, 0 (or any falsy value) meaning "blank". `size`
    is inferred as len(grid); box_rows * box_cols must equal size (9 = 3x3,
    4 = 2x2, 16 = 4x4, ...).
    """
    size = len(grid)
    if box_rows * box_cols != size:
        raise ValueError(f"box_rows*box_cols must equal grid size ({size})")

    variables: list[Cell] = [(r, c) for r in range(size) for c in range(size)]
    domains: dict[Cell, set[int]] = {}
    for r in range(size):
        for c in range(size):
            given = grid[r][c]
            domains[(r, c)] = {given} if given else set(range(1, size + 1))

    groups: list[tuple[str, list[Cell]]] = []
    for r in range(size):                                   # rows
        groups.append((f"row {r + 1}", [(r, c) for c in range(size)]))
    for c in range(size):                                   # columns
        groups.append((f"column {c + 1}", [(r, c) for r in range(size)]))
    k = 0
    for br in range(0, size, box_rows):                      # boxes
        for bc in range(0, size, box_cols):
            k += 1
            groups.append((f"box {k}", [(r, c) for r in range(br, br + box_rows)
                                        for c in range(bc, bc + box_cols)]))

    seen_pairs: set[frozenset] = set()
    constraints = []
    for label, group in groups:
        for rel in all_different(group, label=label):
            key = frozenset((rel.x, rel.y))
            if key not in seen_pairs:                        # a row/box overlap
                seen_pairs.add(key)                           # can repeat a pair
                constraints.append(rel)

    return CSP(variables, domains, constraints, groups=groups)


def grid_str(solution: dict, size: int) -> str:
    lines = []
    for r in range(size):
        lines.append(" ".join(str(solution.get((r, c), 0)) for c in range(size)))
    return "\n".join(lines)


EASY_9x9 = [
    [5, 3, 0, 0, 7, 0, 0, 0, 0],
    [6, 0, 0, 1, 9, 5, 0, 0, 0],
    [0, 9, 8, 0, 0, 0, 0, 6, 0],
    [8, 0, 0, 0, 6, 0, 0, 0, 3],
    [4, 0, 0, 8, 0, 3, 0, 0, 1],
    [7, 0, 0, 0, 2, 0, 0, 0, 6],
    [0, 6, 0, 0, 0, 0, 2, 8, 0],
    [0, 0, 0, 4, 1, 9, 0, 0, 5],
    [0, 0, 0, 0, 8, 0, 0, 7, 9],
]


if __name__ == "__main__":      # self-test (fixed input, known-solvable puzzle)
    from ..core.backtracking import backtracking_search
    from ..core.inference import mac
    from ..core.heuristics import mrv

    csp = sudoku_csp(EASY_9x9, 3, 3)
    solution, metrics = backtracking_search(csp, select_var=mrv, inference=mac)
    assert solution is not None and csp.is_solution(solution)
    print("sudoku self-test passed.")
    print(grid_str(solution, 9))
    print(metrics.summary())
