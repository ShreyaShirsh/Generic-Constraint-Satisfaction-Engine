"""Problem adapters: each module only *describes* a problem as a CSP
(variables, domains, constraints) in the engine's common representation.
None of them contain search or inference code — that all lives in `core/`
and is never touched or duplicated here.
"""
from . import nqueens, graph_colouring, sudoku, cryptarithmetic, zebra, exam_scheduling

__all__ = [
    "nqueens", "graph_colouring", "sudoku",
    "cryptarithmetic", "zebra", "exam_scheduling",
]
