"""Adapter: exam timetabling -> graph colouring -> CSP.

This file contains NO new solving logic and does not even build a CSP
itself — it reduces timetabling to a problem the engine can already solve.
Two exams that share a student can't be scheduled in the same slot, which
is EXACTLY the "two regions that share a border can't share a colour" rule
from map colouring: build a conflict graph (exams = nodes, edges = shared
students) and hand it to graph_colouring_csp with "colours" standing in for
"time slots".

This is the reduction the project abstract calls out explicitly: showing
that a structurally different-looking problem collapses onto one the engine
already handles, without touching the engine itself.
"""
from __future__ import annotations
from .graph_colouring import graph_colouring_csp
from ..core.model import CSP


def conflict_graph(enrollments: dict[str, list[str]]) -> dict[str, list[str]]:
    """enrollments: {student: [exams they're taking]} -> {exam: [conflicting exams]}
    Two exams conflict iff some student is enrolled in both."""
    exams = sorted({e for exs in enrollments.values() for e in exs})
    adjacency: dict[str, set[str]] = {e: set() for e in exams}

    for student, exs in enrollments.items():
        for i in range(len(exs)):
            for j in range(i + 1, len(exs)):
                a, b = exs[i], exs[j]
                adjacency[a].add(b)
                adjacency[b].add(a)

    return {e: sorted(nbrs) for e, nbrs in adjacency.items()}


def exam_scheduling_csp(enrollments: dict[str, list[str]], num_slots: int) -> CSP:
    """Build the timetabling CSP by reducing it to graph colouring:
    exams = nodes, shared-student pairs = edges, time slots = colours."""
    adjacency = conflict_graph(enrollments)
    slots = list(range(1, num_slots + 1))
    return graph_colouring_csp(adjacency, slots)


def timetable_str(solution: dict) -> str:
    by_slot: dict[int, list[str]] = {}
    for exam, slot in solution.items():
        by_slot.setdefault(slot, []).append(exam)
    lines = []
    for slot in sorted(by_slot):
        lines.append(f"Slot {slot}: {', '.join(sorted(by_slot[slot]))}")
    return "\n".join(lines)


# a small named instance, handy as a demo preset -- data only, like AUSTRALIA
SAMPLE_ENROLLMENTS = {
    "Alice":   ["AI", "DBMS", "OS"],
    "Bob":     ["AI", "Networks"],
    "Carol":   ["DBMS", "Networks", "Compilers"],
    "Dave":    ["OS", "Compilers"],
    "Eve":     ["AI", "OS"],
}


if __name__ == "__main__":      # self-test (fixed input, known-feasible instance)
    from ..core.backtracking import backtracking_search

    adjacency = conflict_graph(SAMPLE_ENROLLMENTS)
    assert set(adjacency["AI"]) == {"DBMS", "Networks", "OS"}

    csp = exam_scheduling_csp(SAMPLE_ENROLLMENTS, num_slots=4)
    solution, metrics = backtracking_search(csp)
    assert solution is not None and csp.is_solution(solution)
    print("exam_scheduling self-test passed  (reduced to graph colouring, 4 slots).")
    print(timetable_str(solution))
    print(metrics.summary())
