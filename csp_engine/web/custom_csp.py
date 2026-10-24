"""Builds a CSP from a raw JSON spec the USER types in, at runtime, in the
browser -- the "Custom CSP" playground tab.

This is the direct, hands-on answer to "what is the one constraint your
engine is built on?": it does not special-case anything. It builds the CSP
out of exactly the same three primitives every adapter in `problems/` uses
(BinaryRelation / Predicate / all_different), wires it into the exact same
`core.model.CSP` container, and hands it to the exact same
`backtracking_search`. If a user can describe their puzzle as variables,
domains and constraints, this engine already solves it -- nothing about the
solver changes based on what the puzzle "is".

Spec shape:
{
  "variables": ["A", "B", "C"],
  "domains":   {"A": [1,2,3], "B": [1,2,3], "C": [1,2,3]},
  "constraints": [
    {"type": "not_equal",    "scope": ["A", "B"]},
    {"type": "equal",        "scope": ["B", "C"]},
    {"type": "less_than",    "scope": ["A", "C"]},
    {"type": "all_different","scope": ["A", "B", "C"]},
    {"type": "sum_equals",   "scope": ["A", "B", "C"], "target": 6}
  ]
}
"""
from __future__ import annotations
from ..core.model import CSP
from ..core.constraints import BinaryRelation, Predicate, all_different

_BINARY_OPS = {
    "not_equal":     lambda a, b: a != b,
    "equal":         lambda a, b: a == b,
    "less_than":     lambda a, b: a < b,
    "greater_than":  lambda a, b: a > b,
}


class CustomCSPError(ValueError):
    pass


def build_custom_csp(spec: dict) -> CSP:
    variables = spec.get("variables")
    domains = spec.get("domains")
    constraint_specs = spec.get("constraints", [])

    if not variables or not isinstance(variables, list):
        raise CustomCSPError("spec must include a non-empty 'variables' list")
    if not isinstance(domains, dict) or any(v not in domains for v in variables):
        raise CustomCSPError("spec must include a 'domains' entry for every variable")

    constraints = []
    for i, c in enumerate(constraint_specs):
        ctype = c.get("type")
        scope = c.get("scope")
        if not scope or any(v not in variables for v in scope):
            raise CustomCSPError(f"constraint #{i}: 'scope' must list known variables")

        if ctype in _BINARY_OPS:
            if len(scope) != 2:
                raise CustomCSPError(f"constraint #{i}: '{ctype}' needs a scope of exactly 2")
            x, y = scope
            constraints.append(BinaryRelation(x, y, _BINARY_OPS[ctype], name=ctype))

        elif ctype == "all_different":
            if len(scope) < 2:
                raise CustomCSPError(f"constraint #{i}: 'all_different' needs >= 2 variables")
            constraints.extend(all_different(scope))

        elif ctype == "sum_equals":
            target = c.get("target")
            if target is None:
                raise CustomCSPError(f"constraint #{i}: 'sum_equals' needs a 'target'")
            constraints.append(Predicate(
                scope, lambda local, target=target: sum(local.values()) == target,
                name="sum_equals",
            ))

        else:
            raise CustomCSPError(f"constraint #{i}: unknown type '{ctype}'")

    try:
        domain_map = {v: domains[v] for v in variables}
    except KeyError as e:
        raise CustomCSPError(f"missing domain for variable {e}") from None

    return CSP(variables, domain_map, constraints)
