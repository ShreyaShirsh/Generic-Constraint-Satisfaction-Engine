"""Constraint census: what a problem instance actually compiled into.

Every page of the demo shows this, because it is the direct, per-problem
answer to "what is the one constraint the engine is built on?": every row is
a BinaryRelation or a Predicate -- one predicate abstraction -- and for most
problems the single most common one is plain not-equal.
"""
from __future__ import annotations
from .model import CSP


def census(csp: CSP) -> dict:
    kinds: dict[tuple, dict] = {}
    for c in csp.constraints:
        shape = "BinaryRelation" if hasattr(c, "holds") else "Predicate"
        key = (shape, c.name)
        entry = kinds.setdefault(key, {"shape": shape, "name": c.name, "count": 0,
                                       "example": getattr(c, "label", None) or c.name,
                                       "arity": len(c.variables)})
        entry["count"] += 1
    total = len(csp.constraints)
    ne = sum(e["count"] for e in kinds.values() if e["name"] == "NotEqual")
    return {
        "variables": len(csp.variables),
        "constraints": total,
        "kinds": sorted(kinds.values(), key=lambda e: -e["count"]),
        "not_equal": ne,
        "not_equal_share": round(100 * ne / total, 1) if total else 0.0,
    }
