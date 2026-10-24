"""Adapter: map / graph colouring -> CSP. Contains NO solving logic, only a
description of the problem in the engine's common representation.

Universal: graph_colouring_csp works for ANY graph and ANY set of colours.
Australia is just one named instance (data) built on top of it.

Encoding:
  variables   = nodes / regions
  domains     = the available colours
  constraints = adjacent nodes must differ  (NotEqual)
"""
from __future__ import annotations
from ..core.model import CSP
from ..core.constraints import NotEqual


def graph_colouring_csp(adjacency: dict[str, list[str]], colours: list[str]) -> CSP:
    """Build a colouring CSP from any adjacency map and any colour palette."""
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


# ---- a named instance (data only), handy as a demo preset ------------------
AUSTRALIA = {
    "WA":  ["NT", "SA"],
    "NT":  ["WA", "SA", "Q"],
    "SA":  ["WA", "NT", "Q", "NSW", "V"],
    "Q":   ["NT", "SA", "NSW"],
    "NSW": ["SA", "Q", "V"],
    "V":   ["SA", "NSW"],
    "T":   [],                 # Tasmania is an island: no land neighbours
}


def australia_csp(colours: list[str] | None = None) -> CSP:
    return graph_colouring_csp(AUSTRALIA, colours or ["red", "green", "blue"])


if __name__ == "__main__":      # self-test (fixed inputs, because a test needs a known answer)
    from ..core.backtracking import backtracking_search
    assert backtracking_search(australia_csp())[0] is not None            # 3 colours: solvable
    assert backtracking_search(australia_csp(["red", "green"]))[0] is None  # 2 colours: impossible
    print("graph_colouring self-test passed  (3 colours ok, 2 colours impossible).")
