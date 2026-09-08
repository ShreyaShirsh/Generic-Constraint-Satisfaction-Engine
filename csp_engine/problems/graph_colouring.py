"""Adapter: map / graph colouring -> CSP. Contains NO solving logic, only a
description of the problem in the engine's common representation.

Encoding:
  variables   = nodes / regions
  domains     = the available colours
  constraints = adjacent nodes must differ  (NotEqual)
"""
from __future__ import annotations
from ..core.model import CSP
from ..core.constraints import NotEqual


def graph_colouring_csp(adjacency: dict[str, list[str]], colours: list[str]) -> CSP:
    variables = list(adjacency.keys())
    domains = {v: set(colours) for v in variables}

    constraints = []
    seen: set[frozenset] = set()
    for v, nbrs in adjacency.items():
        for u in nbrs:
            edge = frozenset((v, u))
            if edge not in seen:            # one constraint per edge, not two
                seen.add(edge)
                constraints.append(NotEqual(v, u))

    return CSP(variables, domains, constraints)


# Classic teaching instance: the states/territories of Australia.
AUSTRALIA = {
    "WA":  ["NT", "SA"],
    "NT":  ["WA", "SA", "Q"],
    "SA":  ["WA", "NT", "Q", "NSW", "V"],
    "Q":   ["NT", "SA", "NSW"],
    "NSW": ["SA", "Q", "V"],
    "V":   ["SA", "NSW"],
    "T":   [],                 # Tasmania is an island: no land neighbours
}


def australia_csp() -> CSP:
    return graph_colouring_csp(AUSTRALIA, ["red", "green", "blue"])


if __name__ == "__main__":      # smoke test: python3 -m csp_engine.problems.graph_colouring
    from ..core.backtracking import backtracking_search
    csp = australia_csp()
    solution, metrics = backtracking_search(csp)
    print("Solution:" if solution else "No solution.")
    for v in csp.variables:
        print(f"  {v:>4} = {solution[v]}")
    print("\nMetrics:", metrics.summary())
    print("Valid solution?", csp.is_solution(solution))
