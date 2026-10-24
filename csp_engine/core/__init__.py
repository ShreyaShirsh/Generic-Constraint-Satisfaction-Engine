"""The problem-agnostic engine: model, constraints, search, inference,
heuristics, local search, metrics. Nothing in this package imports from
`problems/` or `cli` — dependencies only ever point inward.
"""
from .model import CSP, Domain, Constraint, Var, Value
from .constraints import BinaryRelation, Predicate, NotEqual, all_different
from .backtracking import backtracking_search, find_all_solutions
from .inference import forward_checking, ac3, mac
from .heuristics import mrv, mrv_degree, lcv
from .local_search import min_conflicts
from .metrics import SearchMetrics

__all__ = [
    "CSP", "Domain", "Constraint", "Var", "Value",
    "BinaryRelation", "Predicate", "NotEqual", "all_different",
    "backtracking_search", "find_all_solutions",
    "forward_checking", "ac3", "mac",
    "mrv", "mrv_degree", "lcv",
    "min_conflicts",
    "SearchMetrics",
]
